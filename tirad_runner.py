#!/usr/bin/env python3
"""
tirad_runner.py — ORTAK CANLI MAKİNE (3 bot da paylaşır: Sprint / Eval / Funded)
═══════════════════════════════════════════════════════════════════════════════
Veri katmanı (Binance Futures public klines, anahtar gerekmez) + LiveBroker (ccxt,
opsiyonel) + TradeBot döngüsü. Bot-özel davranış config ile: target-stop (eval),
aylık-payout (funded). tirad_core ile birlikte tüm sistemi yürütür. Canlı=backtest.
"""
import os, time, json
from datetime import datetime, timezone, timedelta
import pandas as pd

import tirad_core as tc
from tirad_core import Portfolio, latest_signal

try:
    import requests
    _HTTP = "requests"
except ImportError:
    import urllib.request, urllib.parse
    _HTTP = "urllib"

BINANCE_FAPI = "https://fapi.binance.com/fapi/v1/klines"


# ── VERİ: Binance perp 4H klines (kapanmış barlar) ──────────────────────────
def _http_get(url, params):
    if _HTTP == "requests":
        return requests.get(url, params=params, timeout=15).json()
    q = urllib.parse.urlencode(params)
    with urllib.request.urlopen(f"{url}?{q}", timeout=15) as r:
        return json.loads(r.read().decode())


def fetch_klines(symbol, interval="4h", limit=300):
    """→ DataFrame(open,high,low,close,volume,num_trades,taker_buy_ratio). Oluşan bar atılır."""
    raw = _http_get(BINANCE_FAPI, dict(symbol=symbol, interval=interval, limit=limit))
    if not isinstance(raw, list) or len(raw) < 80:
        raise RuntimeError(f"{symbol}: yetersiz veri")
    now_ms = int(time.time() * 1000)
    rows = []
    for k in raw:
        open_t, o, h, l, c, vol, close_t, qv, ntr, tbb, tbq, _ = k
        if int(close_t) > now_ms:
            continue
        vol = float(vol); tbr = (float(tbb) / vol) if vol > 0 else 0.5
        rows.append((pd.to_datetime(int(open_t), unit="ms"), float(o), float(h),
                     float(l), float(c), vol, float(ntr), tbr))
    df = pd.DataFrame(rows, columns=["ts", "open", "high", "low", "close",
                                     "volume", "num_trades", "taker_buy_ratio"])
    return df.set_index("ts")


# ── LIVE BROKER (opsiyonel, ccxt) — varsayılan kapalı ───────────────────────
class LiveBroker:
    def __init__(self):
        import ccxt
        key, sec = os.getenv("BINANCE_KEY"), os.getenv("BINANCE_SECRET")
        if not (key and sec):
            raise RuntimeError("BINANCE_KEY / BINANCE_SECRET env gerekli (live)")
        self.ex = ccxt.binanceusdm({"apiKey": key, "secret": sec,
                                    "options": {"defaultType": "future"}})

    def market_entry(self, symbol, direction, qty, sl, tp):
        side = "buy" if direction == 1 else "sell"
        opp = "sell" if direction == 1 else "buy"
        sym = symbol.replace("USDT", "/USDT")
        self.ex.create_order(sym, "market", side, qty)
        self.ex.create_order(sym, "STOP_MARKET", opp, qty, None,
                             {"stopPrice": sl, "reduceOnly": True})
        self.ex.create_order(sym, "TAKE_PROFIT_MARKET", opp, qty, None,
                             {"stopPrice": tp, "reduceOnly": True})

    def equity(self):
        return float(self.ex.fetch_balance()["USDT"]["total"])


# ── BOT ──────────────────────────────────────────────────────────────────────
class TradeBot:
    def __init__(self, cfg: tc.BotConfig, start_equity: float):
        self.cfg = cfg
        self.pf = Portfolio(cfg, start_equity)
        self.pf.load()
        self.live = None
        if cfg.live:
            self.live = LiveBroker()
            self.pf.equity = self.live.equity()
            self.pf.risk.start = self.pf.risk.start or self.pf.equity

    def log(self, msg):
        line = f"[{datetime.now(timezone.utc):%Y-%m-%d %H:%M}] {self.cfg.name}: {msg}"
        print(line, flush=True)
        with open(f"{self.cfg.name.lower()}_log.txt", "a") as f:
            f.write(line + "\n")

    def _manage(self, data):
        for sym in list(self.pf.positions.keys()):
            df = data.get(sym)
            if df is None or df.empty:
                continue
            opened = pd.to_datetime(self.pf.positions[sym].opened_ts)
            for ts, bar in df[df.index > opened].iterrows():
                rec = self.pf.update_position(sym, bar["high"], bar["low"], str(ts))
                if rec:
                    self.log(f"ÇIKIŞ {sym} R={rec['R']:+.2f} ${rec['pnl']:+.0f} → {self.pf.summary()}")
                    break

    def _scan_and_enter(self, data, latest_day):
        self.pf.risk.new_bar(self.pf.equity, latest_day)
        sigs = []
        for sym, df in data.items():
            if df is None or sym in self.pf.positions:
                continue
            s = latest_signal(sym, df)
            if s:
                sigs.append(s)
        sigs.sort(key=lambda s: s.lam, reverse=True)     # en yüksek conviction önce
        for s in sigs:
            ok, why = self.pf.risk.can_enter(self.pf.equity)
            if not ok:
                self.log(f"{'⛔ DEVRE-KESİCİ' if 'TOPLAM' in why else '⏸'}: {why}"); break
            p = self.pf.open_position(s)
            if p:
                rp = tc.conviction_risk(s.lam, self.cfg.base_risk, self.cfg.max_risk)
                self.log(f"GİRİŞ {s.symbol} {'LONG' if s.direction==1 else 'SHORT'} @{s.entry:.4f} "
                         f"SL={s.sl:.4f} TP={s.tp:.4f} lam={s.lam:.2f} risk=%{rp*100:.2f}")
                if self.live:
                    try:
                        self.live.market_entry(s.symbol, s.direction, p.qty, s.sl, s.tp)
                    except Exception as e:
                        self.log(f"⚠️ LIVE emir hatası {s.symbol}: {e}")

    def run_once(self):
        self.log(f"döngü · {'🔴LIVE' if self.live else 'PAPER'} · {self.pf.summary()}")
        data = {}
        for sym in self.cfg.symbols:
            try:
                data[sym] = fetch_klines(sym, self.cfg.timeframe)
            except Exception as e:
                self.log(f"veri hatası {sym}: {e}")
        if not data:
            self.log("veri yok"); return
        latest_day = max(str(df.index[-1])[:10] for df in data.values() if df is not None and not df.empty)
        self._manage(data)
        # funded: +%5 tetikte payout (erken-çek = en güvenli + en kârlı, MC kanıtlı)
        pr = self.pf.check_payout()
        if pr:
            self.log(f"💰 PAYOUT ÇEKİLDİ: ${pr['payout']:,.0f} → toplam kasa ${pr['vault']:,.0f}")
        # eval: hedef geçildi mi
        if self.pf.target_reached() and not self.pf.passed:
            self.pf.passed = True
            self.log(f"🏆 HEDEF +%{self.cfg.target*100:.0f} GEÇİLDİ! equity ${self.pf.equity:,.0f}")
        if not (self.pf.passed and self.cfg.stop_on_target):
            self._scan_and_enter(data, latest_day)
        else:
            self.log("✅ sınav geçildi — yeni giriş yok (stop_on_target)")
        self.pf.save()
        self.log(f"bitti · {self.pf.summary()}")
        return self.pf.passed and self.cfg.stop_on_target

    def run(self):
        self.log(f"OTONOM başladı · {self.cfg.name} (Ctrl-C ile dur)")
        while True:
            done = self.run_once()
            if done:
                self.log("🏁 görev tamam — döngü durduruldu."); break
            now = datetime.now(timezone.utc)
            nxt_h = (now.hour // 4 + 1) * 4
            base = now.replace(minute=0, second=30, microsecond=0)
            nxt = (base.replace(hour=0) + timedelta(hours=nxt_h)) if nxt_h >= 24 else base.replace(hour=nxt_h)
            if nxt <= now:
                nxt += timedelta(hours=4)
            wait = (nxt - now).total_seconds()
            self.log(f"sonraki bar: {nxt:%H:%M} UTC ({wait/3600:.1f}s)")
            time.sleep(max(60, wait))


def run_cli(cfg: tc.BotConfig, default_equity: float):
    """Ortak CLI: --once / --live / --equity."""
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true", help="tek döngü (cron)")
    ap.add_argument("--live", action="store_true", help="⚠️ GERÇEK emir")
    ap.add_argument("--equity", type=float, default=default_equity, help="başlangıç kasası")
    args = ap.parse_args()
    if args.live:
        cfg.live = True
        print("⚠️  LIVE mod! 5sn içinde Ctrl-C ile iptal...")
        time.sleep(5)
    bot = TradeBot(cfg, start_equity=args.equity)
    bot.run_once() if args.once else bot.run()
