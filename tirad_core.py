#!/usr/bin/env python3
"""
tirad_core.py — DOĞRULANMIŞ ÇEKİRDEK MOTOR (Sprint + Prop botları paylaşır)
═══════════════════════════════════════════════════════════════════════════════
Edge (falsify.py + monte_carlo.py ile doğrulanmış, OOS-sağlam):
  GİRİŞ : Donchian-20 breakout  ·  Hawkes lam>1  ·  VR<1 taze-ateşleme (yüksek-lam muaf)
  SIZING: fractional-Kelly, conviction = lam  (D10 kaskadında agresifleşir, tavanlı)
  ÇIKIŞ : sabit 2.5R TP / −1R hard-SL  (trailing YOK — whipsaw'ı önler)
  RİSK  : kill-switch (statik DD) + intraday-halt (−%3 acil fren) + eşzamanlı-poz tavanı

Bu dosya SAF mantıktır (ağ yok): indikatörler, sinyal, sizing, risk, paper-portföy.
Canlı veri/emir botlarda (sprint_bot.py / prop_bot.py). Matematik falsify.py ile AYNI.
"""
import json, math, os
from dataclasses import dataclass, field, asdict
from typing import Optional
import numpy as np
import pandas as pd

# ── maliyet (backtest ile aynı: taker+slippage round-trip) ──
FEE, SLIP = 0.0004, 0.0003
RT_COST_PRICE = (FEE + SLIP) * 2

# ── parametreler (② doğrulanmış) ──
DONCHIAN_N = 20
LAM_BETA, LAM_L = 0.3, 60
VR_WIN, VR_Q = 60, 4
SL_ATR, TP_R = 2.0, 2.5
LAM_MIN = 1.0       # giriş eşiği
LAM_EXEMPT = 2.2    # yüksek-lam: VR>1 olsa bile gir (balina istisnası)


# ══════════════════════════════════════════════════════════════════════════════
#  KONFİGÜRASYON
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class BotConfig:
    name: str = "TIRAD"
    # risk profili
    base_risk: float = 0.0040          # taban işlem-riski (lam=1)
    max_risk: float = 0.0150           # işlem-başı risk tavanı (D10)
    max_pos: int = 8                   # eşzamanlı pozisyon tavanı (korelasyon)
    # firma/DD koruması
    daily_dd: float = 0.05             # günlük kill-switch
    total_dd: float = 0.60             # statik toplam taban (Sprint geniş; Prop dar)
    intraday_halt: float = 0.03        # gün-içi −%3 → o gün dur
    trailing_floor: bool = False       # statik (False) / zirve-takip (True)
    # hedef (challenge); 0 → sınırsız compound (kendi sermaye)
    target: float = 0.0
    stop_on_target: bool = False       # eval: hedefe ulaşınca DUR (sınav geçti)
    # funded: tetik-bazlı payout (kâr-sağma). Kanıt: +%5 erken-çek = en güvenli+en kârlı
    payout: bool = False
    payout_trigger: float = 0.05       # +%5 kârda çek (MC: %0 iflas, ~$16.5k/yıl/$100k)
    payout_split: float = 0.80         # trader payı (funded firma split'i)
    # evren & yürütme
    symbols: tuple = ()
    timeframe: str = "4h"
    live: bool = False                 # False = PAPER (güvenli varsayılan)
    state_file: str = "tirad_state.json"


# ══════════════════════════════════════════════════════════════════════════════
#  İNDİKATÖRLER (causal, falsify/signal_lab ile birebir)
# ══════════════════════════════════════════════════════════════════════════════
def atr(df, n=14):
    h, l, c = df["high"].to_numpy(float), df["low"].to_numpy(float), df["close"].to_numpy(float)
    pc = np.roll(c, 1); pc[0] = c[0]
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    return pd.Series(tr).ewm(alpha=1 / n, adjust=False).mean().to_numpy()


def donchian(df, n=DONCHIAN_N):
    h = pd.Series(df["high"]).rolling(n).max().to_numpy()
    l = pd.Series(df["low"]).rolling(n).min().to_numpy()
    return h, l


def hawkes_lam(num_trades, taker_buy_ratio, L=LAM_L, beta=LAM_BETA):
    """Order-flow öz-uyarım yoğunluğu (DOĞRULANMIŞ EDGE). lam[i] yalnız ≤i kullanır."""
    nt = np.asarray(num_trades, float)
    signed = 2 * np.asarray(taker_buy_ratio, float) - 1.0
    m = nt * np.abs(signed)
    mu = pd.Series(m).rolling(L).mean().to_numpy()
    ratio = np.divide(m, mu, out=np.ones_like(m), where=(mu > 0))
    lam = np.ones(len(m))
    for i in range(1, len(m)):
        prev = lam[i - 1] if np.isfinite(lam[i - 1]) else 1.0
        r = ratio[i] if np.isfinite(ratio[i]) else 1.0
        lam[i] = (1 - beta) * prev + beta * r
    return lam


def variance_ratio(close, win=VR_WIN, q=VR_Q):
    """Lo-MacKinlay VR(q): >1 trend/geç, <1 sıkışma/taze-ateşleme."""
    c = np.asarray(close, float)
    r = pd.Series(np.diff(np.log(c), prepend=np.log(c[0])))
    var1 = r.rolling(win).var()
    Rq = r.rolling(q).sum()
    varq = Rq.rolling(win).var()
    return (varq / (q * var1 + 1e-12)).to_numpy()


# ══════════════════════════════════════════════════════════════════════════════
#  SİNYAL
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Signal:
    symbol: str
    direction: int        # +1 long, -1 short
    entry: float          # tahmini giriş (son kapanış ≈ piyasa)
    sl: float
    tp: float
    lam: float
    ts: str


def latest_signal(symbol: str, df: pd.DataFrame) -> Optional[Signal]:
    """En son KAPANMIŞ bar için giriş sinyali (yoksa None). df: open,high,low,close,volume,
    num_trades,taker_buy_ratio — kronolojik, son satır kapanmış bar."""
    if len(df) < max(LAM_L, VR_WIN, DONCHIAN_N) + 5:
        return None
    c = df["close"].to_numpy(float)
    a = atr(df, 14)
    dh, dl = donchian(df, DONCHIAN_N)
    lam = hawkes_lam(df["num_trades"], df["taker_buy_ratio"])
    vr = variance_ratio(c)
    i = len(df) - 1
    d = 0
    if c[i] > dh[i - 1]:   d = 1
    elif c[i] < dl[i - 1]: d = -1
    if d == 0:
        return None
    if not np.isfinite(lam[i]) or lam[i] <= LAM_MIN:
        return None
    fresh = (vr[i] < 1.0) if np.isfinite(vr[i]) else False
    if not (fresh or lam[i] >= LAM_EXEMPT):
        return None
    entry = c[i]
    risk = SL_ATR * (a[i] if a[i] > 0 else entry * 0.01)
    sl = entry - d * risk
    tp = entry + d * TP_R * risk
    return Signal(symbol, d, float(entry), float(sl), float(tp), float(lam[i]),
                  str(df.index[i]))


def conviction_risk(lam: float, base_risk: float, max_risk: float) -> float:
    """lam-conviction → işlem-riski (fractional-Kelly ruhu, tavanlı). D10 agresifleşir."""
    mult = min(3.0, max(1.0, lam))
    return float(min(max_risk, base_risk * mult))


# ══════════════════════════════════════════════════════════════════════════════
#  RİSK MOTORU (kill-switch + intraday-halt; compound_engine mantığı)
# ══════════════════════════════════════════════════════════════════════════════
class RiskEngine:
    def __init__(self, cfg: BotConfig, equity: float):
        self.cfg = cfg
        self.start = equity
        self.peak = equity
        self.day_start = equity
        self.cur_day = None
        self.day_halted = False

    def new_bar(self, equity: float, day: str):
        if day != self.cur_day:
            self.cur_day = day
            self.day_start = equity
            self.day_halted = False
        self.peak = max(self.peak, equity)

    def intraday_halt(self, equity: float) -> bool:
        return self.day_start and equity <= self.day_start * (1 - self.cfg.intraday_halt)

    def kill_switch(self, equity: float) -> Optional[str]:
        c = self.cfg
        if self.day_start and equity <= self.day_start * (1 - c.daily_dd):
            return f"GÜNLÜK kill-switch (−%{c.daily_dd*100:.0f})"
        base = self.peak if c.trailing_floor else self.start
        if base and equity <= base * (1 - c.total_dd):
            return f"TOPLAM kill-switch (−%{c.total_dd*100:.0f})"
        return None

    def can_enter(self, equity):   # -> (bool, str)
        if self.day_halted:
            return False, "gün durduruldu"
        if self.intraday_halt(equity):
            self.day_halted = True
            return False, "intraday-halt (−%3)"
        ks = self.kill_switch(equity)
        if ks:
            if "TOPLAM" in ks:
                return False, ks   # kalıcı (challenge fail / circuit-breaker)
            self.day_halted = True
            return False, ks
        return True, "ok"


# ══════════════════════════════════════════════════════════════════════════════
#  PAPER PORTFÖY (live broker botta; bu güvenli simülasyon + state-persist)
# ══════════════════════════════════════════════════════════════════════════════
@dataclass
class Position:
    symbol: str
    direction: int
    entry: float
    sl: float
    tp: float
    qty: float
    risk_amount: float
    opened_ts: str


class Portfolio:
    """Paper portföy: equity (compound), pozisyonlar, SL/TP yürütme, state-persist."""
    def __init__(self, cfg: BotConfig, start_equity: float):
        self.cfg = cfg
        self.equity = start_equity
        self.positions = {}
        self.closed = []
        self.risk = RiskEngine(cfg, start_equity)
        # funded payout takibi
        self.vault = 0.0                 # çekilen toplam payout (korunaklı)
        self.baseline = start_equity     # ay başı referansı
        self.cur_month = None
        self.payouts = []
        self.passed = False              # eval: hedef geçildi mi

    def check_payout(self):
        """Funded: equity, baseline×(1+trigger) üstündeyse kârı ÇEK (trader payı kasaya),
        hesabı baseline'a sıfırla. Kanıt: +%5 erken-çek = %0 iflas + en yüksek yıllık nakit
        (beklemek −%10 zeminine değme riskini katlıyor → %70-86 patlama)."""
        if not self.cfg.payout:
            return None
        if self.equity >= self.baseline * (1 + self.cfg.payout_trigger):
            profit = self.equity - self.baseline
            take = profit * self.cfg.payout_split
            self.vault += take
            self.equity = self.baseline          # kâr çekildi → hesap tabana döndü
            rec = dict(payout=round(take, 2), equity=round(self.equity, 2),
                       vault=round(self.vault, 2))
            self.payouts.append(rec); return rec
        return None

    def target_reached(self) -> bool:
        return self.cfg.target > 0 and self.equity >= self.risk.start * (1 + self.cfg.target)

    # ── pozisyon yönetimi: yeni barda SL/TP kontrolü ──
    def update_position(self, sym: str, high: float, low: float, ts: str):
        if sym not in self.positions:
            return None
        p = self.positions[sym]
        exit_p = None
        if p.direction == 1:
            if low <= p.sl: exit_p = p.sl
            elif high >= p.tp: exit_p = p.tp
        else:
            if high >= p.sl: exit_p = p.sl
            elif low <= p.tp: exit_p = p.tp
        if exit_p is None:
            return None
        sl_dist = abs(p.entry - p.sl) / p.entry
        R = (p.direction * (exit_p - p.entry) / p.entry) / sl_dist - RT_COST_PRICE / sl_dist
        pnl = p.risk_amount * R
        self.equity += pnl
        rec = dict(symbol=sym, R=round(R, 3), pnl=round(pnl, 2), exit=exit_p,
                   entry=p.entry, dir=p.direction, opened=p.opened_ts, closed=ts,
                   equity=round(self.equity, 2))
        self.closed.append(rec)
        del self.positions[sym]
        return rec

    # ── yeni giriş aç (sizing dahil) ──
    def open_position(self, sig: Signal) -> Optional[Position]:
        if sig.symbol in self.positions or len(self.positions) >= self.cfg.max_pos:
            return None
        risk_pct = conviction_risk(sig.lam, self.cfg.base_risk, self.cfg.max_risk)
        risk_amount = self.equity * risk_pct
        sl_dist_price = abs(sig.entry - sig.sl)
        if sl_dist_price <= 0:
            return None
        qty = risk_amount / sl_dist_price
        p = Position(sig.symbol, sig.direction, sig.entry, sig.sl, sig.tp,
                     qty, risk_amount, sig.ts)
        self.positions[sig.symbol] = p
        return p

    # ── state persist (cron/restart güvenli) ──
    def save(self):
        data = dict(equity=self.equity, vault=self.vault, baseline=self.baseline,
                    cur_month=self.cur_month, payouts=self.payouts, passed=self.passed,
                    positions={k: asdict(v) for k, v in self.positions.items()},
                    closed=self.closed[-200:],
                    risk=dict(start=self.risk.start, peak=self.risk.peak,
                              day_start=self.risk.day_start, cur_day=self.risk.cur_day,
                              day_halted=self.risk.day_halted))
        tmp = self.cfg.state_file + ".tmp"
        with open(tmp, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, self.cfg.state_file)

    def load(self):
        if not os.path.exists(self.cfg.state_file):
            return
        with open(self.cfg.state_file) as f:
            d = json.load(f)
        self.equity = d["equity"]
        self.vault = d.get("vault", 0.0)
        self.baseline = d.get("baseline", self.equity)
        self.cur_month = d.get("cur_month")
        self.payouts = d.get("payouts", [])
        self.passed = d.get("passed", False)
        self.positions = {k: Position(**v) for k, v in d.get("positions", {}).items()}
        self.closed = d.get("closed", [])
        r = d.get("risk", {})
        self.risk.start = r.get("start", self.equity)
        self.risk.peak = r.get("peak", self.equity)
        self.risk.day_start = r.get("day_start", self.equity)
        self.risk.cur_day = r.get("cur_day")
        self.risk.day_halted = r.get("day_halted", False)

    def summary(self) -> str:
        n = len(self.closed)
        wr = 100 * np.mean([c["R"] > 0 for c in self.closed]) if n else 0
        ret = (self.equity / self.risk.start - 1) * 100
        vault = f"  💰payout ${self.vault:,.0f}" if self.vault > 0 else ""
        return (f"equity ${self.equity:,.2f} ({ret:+.1f}%)  açık {len(self.positions)}  "
                f"kapalı {n}  WR %{wr:.0f}  peak ${self.risk.peak:,.0f}{vault}")


# evren: 42 coin (breadth_test ile doğrulandı — lam dose-response 23 yeni coinde +0.890,
# 22/23 pozitif → edge genel, BTC/ETH'e özel değil). Binance/Bybit perp; HyroTrader'da işlem görür.
# (MATIC hariç — Binance perp'te delist; live için POL'e geçilebilir.)
UNIVERSE = ("BTCUSDT", "ETHUSDT", "BNBUSDT", "SOLUSDT", "XRPUSDT", "ADAUSDT",
            "AVAXUSDT", "DOTUSDT", "DOGEUSDT", "LINKUSDT", "NEARUSDT", "INJUSDT",
            "ATOMUSDT", "ARBUSDT", "OPUSDT", "UNIUSDT", "FILUSDT", "LTCUSDT",
            "ETCUSDT", "APTUSDT",
            # breadth genişletme (edge doğrulanmış):
            "TRXUSDT", "AAVEUSDT", "MKRUSDT", "ALGOUSDT", "XLMUSDT", "SANDUSDT",
            "MANAUSDT", "GRTUSDT", "CRVUSDT", "RUNEUSDT", "GALAUSDT", "IMXUSDT",
            "DYDXUSDT", "CHZUSDT", "COMPUSDT", "SNXUSDT", "AXSUSDT", "ENJUSDT",
            "ZILUSDT", "1INCHUSDT", "SUSHIUSDT", "ICPUSDT")
