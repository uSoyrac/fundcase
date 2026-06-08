#!/usr/bin/env python3
"""
analyze.py — TIRAD bot DURUM ÇEKME & ANALİZ aracı ("ara ara çek, analiz et").
Botların state JSON'larını okur: equity, getiri, WR, açık poz, payout, son işlemler.

KULLANIM:
  python deploy/analyze.py                 # tüm botların özeti
  python deploy/analyze.py --trades 20     # son 20 işlemi de göster
"""
import json, os, sys, glob
from datetime import datetime, timezone

BOTS = {
    "sprint_state.json": "🔴 SPRINT",
    "prop_eval_state.json": "🔵 EVAL",
    "prop_eval_fast_state.json": "🟡 EVAL-FAST",
    "prop_funded_state.json": "🟢 FUNDED",
}


def summarize(path, label, n_trades=0):
    with open(path) as f:
        d = json.load(f)
    eq = d.get("equity", 0); start = d.get("risk", {}).get("start", eq) or eq
    peak = d.get("risk", {}).get("peak", eq)
    closed = d.get("closed", []); pos = d.get("positions", {})
    vault = d.get("vault", 0); payouts = d.get("payouts", [])
    n = len(closed)
    wins = [c for c in closed if c.get("R", 0) > 0]
    wr = 100 * len(wins) / n if n else 0
    ret = (eq / start - 1) * 100 if start else 0
    dd = (1 - eq / peak) * 100 if peak else 0
    sumR = sum(c.get("R", 0) for c in closed)

    print(f"\n{label}")
    print(f"  equity ${eq:,.2f}  ({ret:+.1f}%)  ·  peak ${peak:,.0f}  ·  anlık DD %{dd:.1f}")
    print(f"  işlem {n}  ·  WR %{wr:.0f}  ·  toplam {sumR:+.1f}R  ·  açık poz {len(pos)}")
    if vault:
        print(f"  💰 çekilen payout: ${vault:,.0f}  ({len(payouts)} çekim)")
    if pos:
        for sym, p in pos.items():
            d_ = "LONG" if p["direction"] == 1 else "SHORT"
            print(f"     açık: {sym} {d_} @{p['entry']:.4f} SL={p['sl']:.4f} TP={p['tp']:.4f}")
    if n_trades and closed:
        print(f"  son {min(n_trades, n)} işlem:")
        for c in closed[-n_trades:]:
            print(f"     {c.get('closed','')[:16]} {c['symbol']:<9} R={c['R']:+.2f} ${c['pnl']:+.0f} → ${c['equity']:,.0f}")


def main():
    n_trades = 0
    if "--trades" in sys.argv:
        n_trades = int(sys.argv[sys.argv.index("--trades") + 1])
    here = os.path.dirname(os.path.abspath(__file__))
    roots = [here, os.path.dirname(here), os.getcwd()]   # düz VEYA deploy/ yapısı
    print("=" * 70)
    print(f"  TIRAD DURUM RAPORU · {datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC")
    print("=" * 70)
    found = False
    for fname, label in BOTS.items():
        path = next((os.path.join(r, fname) for r in roots if os.path.exists(os.path.join(r, fname))), None)
        if path:
            found = True
            try:
                summarize(path, label, n_trades)
            except Exception as e:
                print(f"\n{label}: okuma hatası ({e})")
    if not found:
        print("\n  Henüz state dosyası yok — botlar en az 1 döngü koşmalı.")
    print("\n" + "=" * 70)


if __name__ == "__main__":
    main()
