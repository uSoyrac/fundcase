#!/usr/bin/env python3
"""🟠 ensemble_eval_bot.py — KULLANICI FİKRİ DOĞRULANDI: lam (fon botu) + lsx (en kârlı deneme botu)
TEK HESAPTA birleşik al-sat. ensemble_eval_mc: aynı riskte lam+lsx pass %49→62, blow %51→33
(dekorele +0.17 → çukurları doldurur). Gerçek HYRO 4/6 + cushion-then-protect, PAPER.

KARAR MOTORU (her 4H):
  • lam kolu: Donchian-20 + lam≥2 yükselen-kaskad → giriş, SL=2×ATR / TP=2.5R (trende bin)
  • lsx kolu: |lsx|≥1.2 (~%80 kalabalık positioning) → kontraryan, 24h hold (aşırılığı fade)
  • risk: cushion-then-protect (build %0.15 → +%8 yastıkta %0.05), 4/6 taban, gün-içi −%2 halt, 1×
  • likit-subset (Hyro low-cap ≤%5 uyumu): lsx yalnız metricsdata'daki 20 likit coinde
Python 3.6 uyumlu, cron --once."""
import json, os, sys, time
from datetime import datetime, timezone, timedelta
from tirad_core import latest_signal, conviction_risk, BotConfig, UNIVERSE, SL_ATR
from tirad_runner import fetch_klines
from lsx_bot import lsx_score, COINS as LSX_COINS

HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "ensemble_eval_state.json")
TRADES = os.path.join(HERE, "ensemble_eval_trades.jsonl")
LOG = os.path.join(HERE, "ensemble_eval_log.txt")

CFG = BotConfig(name="ENSEMBLE_EVAL", lam_min=2.0, base_risk=0.0015, max_risk=0.0060,
                cushion=0.08, protect_risk=0.0005, max_pos=12, daily_dd=0.04,
                total_dd=0.06, intraday_halt=0.02, tp_r=2.5, target=0.10)
LSX_THR, LSX_F, LSX_HOLD_H, COST = 1.2, 0.10, 24, 0.0014


def log(m):
    line = "[%s] ENS: %s" % (datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), m)
    print(line); open(LOG, "a").write(line + "\n")


def load():
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"equity": 100000.0, "start": 100000.0, "risk": {"start": 100000.0},
            "day": None, "day_start": 100000.0,
            "halted": False, "positions": {}, "closed": [], "passed": False}


def save(st):
    json.dump(st, open(STATE, "w"), ensure_ascii=False, indent=1)


def rec_trade(st, r):
    st["closed"].append(r)
    open(TRADES, "a").write(json.dumps(r, ensure_ascii=False) + "\n")
    log("KAPAT %s %s %s pnl %+.1f$ → eq %.0f" % (r["sleeve"], r["coin"], r["yon"], r["pnl"], st["equity"]))


def run_once():
    st = load(); now = datetime.now(timezone.utc); today = now.strftime("%Y-%m-%d")
    if st["day"] != today:
        st["day"] = today; st["day_start"] = st["equity"]; st["halted"] = False
    floor = st["start"] * (1 - CFG.total_dd)
    # cushion-then-protect taban riski
    base = CFG.protect_risk if st["equity"] >= st["start"] * (1 + CFG.cushion) else CFG.base_risk

    # ── 1) açık pozisyonları yönet ──
    for sym in list(st["positions"].keys()):
        p = st["positions"][sym]; px = None
        try:
            df = fetch_klines(sym, "4h", 3); px = float(df["close"].iloc[-1])
        except Exception:
            continue
        if px is None:
            continue
        exit_px = None; why = ""
        if p["sleeve"] == "lam":
            if p["dir"] == 1:
                if px <= p["sl"]: exit_px, why = p["sl"], "SL"
                elif px >= p["tp"]: exit_px, why = p["tp"], "TP"
            else:
                if px >= p["sl"]: exit_px, why = p["sl"], "SL"
                elif px <= p["tp"]: exit_px, why = p["tp"], "TP"
        else:  # lsx: 24h hold
            due = datetime.strptime(p["exit_due"], "%Y-%m-%dT%H:%M").replace(tzinfo=timezone.utc)
            if now >= due: exit_px, why = px, "24h"
        if exit_px is None:
            continue
        if p["sleeve"] == "lam":
            R = p["dir"] * (exit_px - p["entry"]) / abs(p["entry"] - p["sl"])
            pnl = p["risk_amt"] * R - p["risk_amt"] * COST
        else:
            net = p["dir"] * (exit_px / p["entry"] - 1.0) - COST
            pnl = p["notional"] * net
        st["equity"] += pnl
        rec_trade(st, {"sleeve": p["sleeve"], "coin": sym.replace("USDT", ""),
                       "yon": "LONG" if p["dir"] == 1 else "SHORT", "entry": p["entry"],
                       "exit": round(exit_px, 6), "pnl": round(pnl, 2), "why": why,
                       "opened": p["opened"], "closed": now.strftime("%Y-%m-%dT%H:%M"),
                       "equity": round(st["equity"], 2), "reason": p["reason"]})
        del st["positions"][sym]
        time.sleep(0.2)

    # ── floor / hedef / halt ──
    if st["equity"] <= floor:
        log("⛔ TABAN −%6 (eq %.0f)" % st["equity"]); save(st); return
    if st["equity"] >= st["start"] * (1 + CFG.target):
        st["passed"] = True; log("🏆 +%10 GEÇİLDİ eq %.0f" % st["equity"]); save(st); return
    if st["equity"] <= st["day_start"] * (1 - CFG.intraday_halt):
        st["halted"] = True
    if st["halted"]:
        log("gün-halt · eq %.0f · açık %d" % (st["equity"], len(st["positions"]))); save(st); return

    slots = CFG.max_pos - len(st["positions"])
    # ── 2) lam kolu (trend) ──
    lam_cands = []
    for c in UNIVERSE:
        sym = c if c.endswith("USDT") else c + "USDT"
        sym = sym.replace("USDTUSDT", "USDT")
        if sym in st["positions"]:
            continue
        try:
            df = fetch_klines(sym, "4h", 300)
            s = latest_signal(sym, df, CFG.tp_r)
        except Exception:
            s = None
        if s:
            lam_cands.append(s)
        time.sleep(0.05)
    lam_cands.sort(key=lambda s: s.lam, reverse=True)
    for s in lam_cands:
        if slots <= 0:
            break
        risk_pct = conviction_risk(s.lam, base, CFG.max_risk)
        st["positions"][s.symbol] = {"sleeve": "lam", "dir": s.direction, "entry": s.entry,
                                     "sl": s.sl, "tp": s.tp, "risk_amt": round(st["equity"] * risk_pct, 2),
                                     "opened": now.strftime("%Y-%m-%dT%H:%M"), "reason": s.reason}
        log("AÇ lam %s @%.6g · %s" % (s.symbol, s.entry, s.reason[:50])); slots -= 1

    # ── 3) lsx kolu (positioning kontraryan, likit-subset) ──
    for c in LSX_COINS:
        if slots <= 0:
            break
        sym = c + "USDT"
        if sym in st["positions"]:
            continue
        sc, lf = lsx_score(sym); time.sleep(0.15)
        if sc is None or abs(sc) < LSX_THR:
            continue
        try:
            df = fetch_klines(sym, "4h", 3); px = float(df["close"].iloc[-1])
        except Exception:
            continue
        d = 1 if sc > 0 else -1
        st["positions"][sym] = {"sleeve": "lsx", "dir": d, "entry": px,
                                "notional": round(st["equity"] * LSX_F, 2),
                                "exit_due": (now + timedelta(hours=LSX_HOLD_H)).strftime("%Y-%m-%dT%H:%M"),
                                "opened": now.strftime("%Y-%m-%dT%H:%M"),
                                "reason": "lsx=%+.2f (long%% %.0f aşırı) → kontraryan %s" % (
                                    sc, lf * 100, "LONG" if d == 1 else "SHORT")}
        log("AÇ lsx %s @%.6g · %s" % (sym, px, st["positions"][sym]["reason"])); slots -= 1

    save(st)
    log("döngü bitti · eq %.0f · açık %d (base %%%.2f%s)" % (
        st["equity"], len(st["positions"]), base * 100,
        " PROTECT" if base == CFG.protect_risk else " BUILD"))


if __name__ == "__main__":
    run_once()
