#!/usr/bin/env python3
"""falsify_exit2.py — ADIM ③b: EN İYİ BASİT ÇIKIŞ (trail'ler öldü). TP × hold ızgarası.
Kural: i+1 gir; ilk gerçekleşen {TP-vur, hard-SL-vur, N-bar-dol}. lam-kapılı girişlerde."""
import numpy as np
import pandas as pd
from signal_lab import atr, RT_COST_PRICE
from falsify import load_with_micro, breakout_pos, _features

SL_ATR = 2.0


def simple_exit(O, H, L, C, A, i, d, tp_r, hold_n):
    n = len(C)
    entry = O[i + 1]
    risk = SL_ATR * (A[i] if A[i] > 0 else entry * 0.01)
    sl_dist = risk / entry
    hard_sl = entry - d * risk
    tp = entry + d * tp_r * risk if tp_r else None
    j = i + 1; exit_p = None
    while j < n:
        if d == 1:
            if L[j] <= hard_sl: exit_p = hard_sl; break
            if tp and H[j] >= tp: exit_p = tp; break
        else:
            if H[j] >= hard_sl: exit_p = hard_sl; break
            if tp and L[j] <= tp: exit_p = tp; break
        if hold_n and (j - (i + 1)) >= hold_n:
            exit_p = O[min(j + 1, n - 1)]; break
        j += 1
    if exit_p is None: exit_p = C[min(j, n - 1)]
    return (d * (exit_p - entry) / entry) / sl_dist - RT_COST_PRICE / sl_dist


def main():
    print("=" * 92)
    print("  ADIM ③b — EN İYİ BASİT ÇIKIŞ ızgarası (lam-kapılı girişler, trail YOK)")
    print("=" * 92)
    dfs = load_with_micro()
    trades = []   # (R-per-config) toplamak yerine config-bazlı topla
    configs = ([("TP%.1f" % t, t, None) for t in (1.5, 2.0, 2.5, 3.0, 4.0)]
               + [("hold%d" % h, None, h) for h in (10, 20, 30, 40)]
               + [("TP3+hold30", 3.0, 30), ("TP4+hold40", 4.0, 40), ("TP2.5+hold20", 2.5, 20)])
    agg = {name: {"R": [], "yr": []} for name, _, _ in configs}

    for c, df in dfs.items():
        O = df["open"].to_numpy(float); H = df["high"].to_numpy(float)
        Lr = df["low"].to_numpy(float); Cc = df["close"].to_numpy(float)
        A = atr(df, 14); idx = df.index
        lam = _features(df)["lam"]
        pos = breakout_pos(df, 20)
        for i in np.where(pos != 0)[0]:
            if lam[i] <= 1.0 or i + 1 >= len(Cc):
                continue
            yr = str(idx[min(i + 1, len(idx) - 1)])[:4]
            for name, tp_r, hold_n in configs:
                agg[name]["R"].append(simple_exit(O, H, Lr, Cc, A, i, int(pos[i]), tp_r, hold_n))
                agg[name]["yr"].append(yr)

    yrs = sorted(set(agg[configs[0][0]]["yr"]))
    print(f"\n  {'config':<14}{'N':>7}{'avgR':>9}{'WR%':>7}{'PF':>7}{'sumR':>9}   yıl-yıl avgR")
    rows = []
    for name, _, _ in configs:
        R = np.array(agg[name]["R"]); d = pd.DataFrame({"R": agg[name]["R"], "yr": agg[name]["yr"]})
        wins = R[R > 0]; loss = R[R <= 0]
        pf = wins.sum() / abs(loss.sum()) if loss.sum() != 0 else float("inf")
        yc = " ".join(f"{d[d.yr==y]['R'].mean():+.2f}" for y in yrs)
        oos = d[d.yr.isin(["2025", "2026"])]["R"].mean()
        rows.append((name, R.mean(), pf, oos))
        print(f"  {name:<14}{len(R):>7}{R.mean():>+9.4f}{100*(R>0).mean():>7.1f}{pf:>7.2f}{R.sum():>9.1f}   {yc}")

    best = max(rows, key=lambda x: x[1])
    best_oos = max(rows, key=lambda x: x[3])
    print(f"\n  EN İYİ avgR: {best[0]} (avgR={best[1]:+.4f} PF={best[2]:.2f})")
    print(f"  EN İYİ OOS : {best_oos[0]} (2025-26 avgR={best_oos[3]:+.4f})")
    print("=" * 92)


if __name__ == "__main__":
    main()
