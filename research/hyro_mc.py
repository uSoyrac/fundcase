#!/usr/bin/env python3
"""hyro_mc.py — HYROTRADER kurallarında (%4 günlük / %6 TRAILING total / +%10) config kanıtı.
Eval: P(pass) & P(blown). Funded: 180-gün P(survive). İflas=0 olan ultra-cerrahi config'i bul."""
import numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, conviction_risk, RT_COST_PRICE)
from monte_carlo import build_timeline

N = 500
HALT = 0.02   # gün-içi −%2 → dur (−%4 günlüğe ASLA değme)


def hyro_run(coins, tl, start_idx, P):
    start = 10000.0
    target = start * (1 + P["target"]) if P["target"] > 0 else None
    equity = peak = day_start = start; cur_day = None; day_halted = False
    open_pos = {}; t0 = pd.Timestamp(tl[start_idx][0]); days = 0
    for k in range(start_idx, len(tl)):
        ts, c, j = tl[k]; days = (pd.Timestamp(ts) - t0).days
        if days > P["max_days"]:
            return ("timeout" if target else "survived"), days
        day = str(ts)[:10]
        if day != cur_day:
            cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; H = cd["H"][j]; L = cd["L"][j]
        if c in open_pos:
            d, entry, sl, tp, ra = open_pos[c]
            exit_p = (sl if L <= sl else tp if H >= tp else None) if d == 1 \
                else (sl if H >= sl else tp if L <= tp else None)
            if exit_p is not None:
                sl_dist = abs(entry - sl) / entry
                R = (d * (exit_p - entry) / entry) / sl_dist - RT_COST_PRICE / sl_dist
                equity += ra * R; peak = max(peak, equity); del open_pos[c]
                if target and equity >= target: return "pass", days
                floor = peak * (1 - P["total"]) if P["trailing"] else start * (1 - P["total"])
                if equity <= floor: return "blown", days
                if equity <= day_start * (1 - P["daily"]): return "blown", days
                if equity <= day_start * (1 - HALT): day_halted = True
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < P["max_pos"]:
            if equity <= day_start * (1 - HALT):
                day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, P["base"], P["maxr"]))
    return ("timeout" if target else "survived"), days


def mc(coins, tl, P, starts):
    out = {}; pdays = []
    for s in starts:
        r, d = hyro_run(coins, tl, int(s), P)
        out[r] = out.get(r, 0) + 1
        if r == "pass": pdays.append(d)
    return out, pdays


def main():
    print("Veri + feature...")
    dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl) * 0.8), size=N)

    print("=" * 96)
    print(f"  HYROTRADER: %4 günlük / %6 TRAILING total / +%10 hedef · gün-içi-halt −%{HALT*100:.0f} · {N} sim")
    print("=" * 96)
    print("  ── 🔵 EVAL: P(pass)/P(blown) — TRAILING vs STATIC × 90/180/365 gün ──")
    print(f"  {'config':<14}{'trail@90':>13}{'trail@180':>13}{'static@90':>13}{'static@180':>13}{'static@365':>13}")
    for name, base, maxr, mp in [("%0.08", 0.0008, 0.0035, 5), ("%0.10", 0.0010, 0.0045, 6),
                                 ("%0.15", 0.0015, 0.0060, 6)]:
        cells = []
        for trail, md in [(True, 90), (True, 180), (False, 90), (False, 180), (False, 365)]:
            P = dict(target=0.10, total=0.06, daily=0.04, trailing=trail, max_days=md,
                     base=base, maxr=maxr, max_pos=mp)
            out, _ = mc(coins, tl, P, starts)
            cells.append(f"{100*out.get('pass',0)/N:>3.0f}/{100*out.get('blown',0)/N:>2.0f}b")
        print(f"  {name:<14}" + "".join(f"{x:>13}" for x in cells))
    print("  (hücre = P(pass)% / P(blown)%b · static = kâra geçince taban kilitlenir = KOLAY)")

    print("\n  ── 🟢 FUNDED (hedef YOK, 180-gün hayatta kalma) ──")
    print(f"  {'config':<24}{'P(survive)':>12}{'P(blown)':>10}")
    for name, base, maxr, mp in [("ultra %0.05", 0.0005, 0.0025, 5), ("%0.08", 0.0008, 0.0035, 5),
                                 ("%0.10", 0.0010, 0.0040, 6)]:
        P = dict(target=0.0, total=0.06, daily=0.04, trailing=True, max_days=180,
                 base=base, maxr=maxr, max_pos=mp)
        out, _ = mc(coins, tl, P, starts)
        print(f"  {name:<24}{100*out.get('survived',0)/N:>11.0f}%{100*out.get('blown',0)/N:>9.0f}%")
    print("=" * 96)
    print("  trailing −%6 = zirveyi kovalar (HyroTrader gerçeği, ZOR). İflas=0 + en yüksek P(pass) seç.")


if __name__ == "__main__":
    main()
