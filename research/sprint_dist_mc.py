#!/usr/bin/env python3
"""sprint_dist_mc.py — $100 SPRINT (kendi-para, Binance) DAĞILIM Monte-Carlo.
Soru: $100 → $250/$500/$1000'e 3/6/12 ayda ulaşma olasılığı + medyan + iflas riski.
Sprint config: base %0.80 / max %2.5 / 8 poz / −%60 breaker, lam-gate'li (lam≥1), compound,
HEDEF YOK (kendi-sermaye), maliyet dahil. 500 rastgele başlangıç, gerçek 4H veri."""
import numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, conviction_risk,
                      kill_switch, intraday_halt, RT_COST_PRICE)
from monte_carlo import build_timeline

START = 100.0
HORIZONS = [90, 180, 365]          # 3 / 6 / 12 ay
N = 500
BASE, MAXR, MAXPOS = 0.0080, 0.0250, 8
FIRM = {"daily": 0.50, "total": 0.60, "trailing": False}   # −%60 statik breaker (kendi-para)
HALT = 0.50                                                # gün-içi halt ~kapalı (agresif)


def run_sprint(coins, tl, s):
    equity = peak = day_start = START; cur_day = None; day_halted = False
    open_pos = {}; t0 = pd.Timestamp(tl[s][0]); snap = {}; trough = START
    hmax = max(HORIZONS)
    for k in range(s, len(tl)):
        ts, c, j = tl[k]; days = (pd.Timestamp(ts) - t0).days
        for h in HORIZONS:
            if h not in snap and days >= h: snap[h] = equity
        if days > hmax: break
        day = str(ts)[:10]
        if day != cur_day: cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; H = cd["H"][j]; L = cd["L"][j]
        if c in open_pos:
            d, entry, sl, tp, ra = open_pos[c]
            exit_p = (sl if L <= sl else tp if H >= tp else None) if d == 1 \
                else (sl if H >= sl else tp if L <= tp else None)
            if exit_p is not None:
                sl_dist = abs(entry - sl) / entry
                R = (d * (exit_p - entry) / entry) / sl_dist - RT_COST_PRICE / sl_dist
                equity += ra * R; peak = max(peak, equity); trough = min(trough, equity)
                del open_pos[c]
                if intraday_halt(equity, day_start, HALT): day_halted = True
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < MAXPOS:
            if intraday_halt(equity, day_start, HALT) or kill_switch(equity, peak, day_start, FIRM):
                day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, BASE, MAXR))
    for h in HORIZONS:
        if h not in snap: snap[h] = equity
    mdd = (trough / peak - 1.0) if peak else 0.0
    return snap, mdd


def main():
    print("Veri + lam-gate'li girişler..."); dfs = load_with_micro()
    coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11)
    starts = rng.integers(0, int(len(tl) * 0.6), size=N)   # 365g önü olsun
    eqs = {h: [] for h in HORIZONS}; mdds = []
    for s in starts:
        snap, mdd = run_sprint(coins, tl, int(s))
        for h in HORIZONS: eqs[h].append(snap[h])
        mdds.append(mdd)
    print("=" * 88)
    print("  $100 SPRINT (kendi-para, base %0.80/max %2.5, lam≥1, compound) — 500 sim")
    print("=" * 88)
    print("  %-8s %10s %9s %9s %9s %9s %9s" % ("ufuk", "medyan$", "P≥$250", "P≥$500", "P≥$1000", "P≥$5000", "P<$30"))
    for h in HORIZONS:
        a = np.array(eqs[h])
        lbl = "%d ay" % round(h / 30)
        print("  %-8s %10.0f %8.0f%% %8.0f%% %8.0f%% %8.0f%% %8.0f%%" % (
            lbl, np.median(a),
            100 * (a >= 250).mean(), 100 * (a >= 500).mean(),
            100 * (a >= 1000).mean(), 100 * (a >= 5000).mean(), 100 * (a < 30).mean()))
    md = np.array(mdds)
    print("-" * 88)
    print("  yol-boyu MaxDD: medyan %.0f%% · p90 (en kötü) %.0f%% · ortalama %.0f%%" % (
        100 * np.median(md), 100 * np.percentile(md, 10), 100 * md.mean()))
    print("  P95 sonuç (12 ay): $%.0f · P05 (12 ay): $%.0f" % (
        np.percentile(eqs[365], 95), np.percentile(eqs[365], 5)))
    print("=" * 88)
    print("  NOT: kendi-para, −%60 breaker dışında taban yok; getiri YUMRULU (şişman-kuyruk).")


if __name__ == "__main__":
    main()
