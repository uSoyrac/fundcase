#!/usr/bin/env python3
"""hyro2_mc.py — HYROTRADER TWO-STEP (%5 günlük / %10 STATİK total) + FUNDED PAYOUT optimizasyonu.
Eval Step1 (+10%): base taraması. Funded: base × çekim-tetiği → yıllık nakit + hayatta-kalma."""
import numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, conviction_risk, RT_COST_PRICE)
from monte_carlo import build_timeline
from hyro_mc import hyro_run   # eval için (total/daily/trailing parametrik)

N = 400


def funded_run(coins, tl, s, base, maxr, mp, trigger, window, daily=0.05, total=0.10, halt=0.03):
    """Funded: +trigger'da kârı çek (%80 trader), tabana dön. Döner: ('survived'/'blown', yıllık_net_$)."""
    start = 100000.0; equity = peak = day_start = start; baseline = start; vault = 0.0
    floor = start * (1 - total); cur_day = None; day_halted = False
    open_pos = {}; t0 = pd.Timestamp(tl[s][0]); days = 0
    for k in range(s, len(tl)):
        ts, c, j = tl[k]; days = (pd.Timestamp(ts) - t0).days
        if days > window:
            break
        day = str(ts)[:10]
        if day != cur_day: cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; H = cd["H"][j]; L = cd["L"][j]
        if c in open_pos:
            d, entry, sl, tp, ra = open_pos[c]
            ex = (sl if L <= sl else tp if H >= tp else None) if d == 1 else (sl if H >= sl else tp if L <= tp else None)
            if ex is not None:
                sld = abs(entry - sl) / entry
                R = (d * (ex - entry) / entry) / sld - RT_COST_PRICE / sld
                equity += ra * R; peak = max(peak, equity); del open_pos[c]
                if equity <= floor or equity <= day_start * (1 - daily):
                    return "blown", vault / (window / 365)
                if equity >= baseline * (1 + trigger):       # ÇEKİM
                    vault += (equity - baseline) * 0.80; equity = baseline
                if equity <= day_start * (1 - halt): day_halted = True
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < mp:
            if equity <= day_start * (1 - halt): day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, base, maxr))
    return "survived", vault / (window / 365)


def main():
    print("Veri + feature..."); dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl) * 0.6), size=N)

    print("=" * 92)
    print("  HYROTRADER TWO-STEP: %5 günlük / %10 STATİK total / sınırsız süre")
    print("=" * 92)
    print("  ── 🔵 EVAL Step1 (+%10) — base taraması (statik −%10) ──")
    print(f"  {'base':<10}{'P(pass)':>9}{'P(blown)':>10}{'medyan-gün':>12}")
    for base, maxr, mp in [(0.0010, 0.005, 6), (0.0015, 0.007, 6), (0.0020, 0.009, 6), (0.0030, 0.012, 8)]:
        P = dict(target=0.10, total=0.10, daily=0.05, trailing=False, max_days=1095, base=base, maxr=maxr, max_pos=mp)
        o = {}; pdays = []
        for s in starts:
            r, d = hyro_run(coins, tl, int(s), P); o[r] = o.get(r, 0) + 1
            if r == "pass": pdays.append(d)
        med = int(np.median(pdays)) if pdays else -1
        print(f"  %{base*100:<8.2f}{100*o.get('pass',0)/N:>8.0f}%{100*o.get('blown',0)/N:>9.0f}%{med:>12}")

    print("\n  ── 🟢 FUNDED PAYOUT: base × çekim-tetiği → YILLIK net $ ($100k hesap, 1-yıl pencere) ──")
    print(f"  {'base':<10}{'+%5 çek':>22}{'+%8 çek':>22}{'+%12 çek':>22}")
    print(f"  {'':10}" + "  ".join(["yıllık$ / P(iflas)"] * 3))
    for base, maxr, mp in [(0.0008, 0.004, 5), (0.0012, 0.006, 6), (0.0016, 0.008, 6)]:
        cells = []
        for trig in (0.05, 0.08, 0.12):
            inc = []; blown = 0
            for s in starts:
                r, net = funded_run(coins, tl, int(s), base, maxr, mp, trig, 365)
                if r == "blown": blown += 1
                inc.append(net)
            med_inc = np.median(inc)
            cells.append(f"${med_inc:>8,.0f} / {100*blown/N:>3.0f}%")
        print(f"  %{base*100:<8.2f}" + "  ".join(f"{c:>20}" for c in cells))
    print("=" * 92)
    print("  yıllık$=medyan trader-net çekim (80% split, $100k hesap) · P(iflas)=−%10 zemini")


if __name__ == "__main__":
    main()
