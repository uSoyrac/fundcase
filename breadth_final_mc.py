#!/usr/bin/env python3
"""breadth_final_mc.py — TEMİZ genişlik: eski-43 + yeni T1/T2 (≥$5M/gün, 75 coin) = 118 coin.
T3-ince katman (OOS −0.329) ATILDI. Akış + Step1 hız-MC (aynı config/risk) eski vs temiz-birleşik."""
import numpy as np, pandas as pd
from falsify import load_with_micro
from prop_sim import build_entries
from monte_carlo import build_timeline
from sprint_z_mc import mc

N = 300
MILD = (0.00007, 0.0); HARSH = (0.00015, 0.00010)


def flow1y(coins):
    n1y = 0; tmax = None
    for c, cd in coins.items():
        if len(cd["ts"]):
            t1 = pd.Timestamp(cd["ts"][-1]); tmax = t1 if tmax is None or t1 > tmax else tmax
    cut = tmax - pd.Timedelta(days=365)
    for c, cd in coins.items():
        n1y += sum(1 for j in cd["entries"] if pd.Timestamp(cd["ts"][j]) >= cut)
    return 10.0 * n1y / 365


def main():
    dfs_old = load_with_micro()
    dfs_new = load_with_micro("mktdata_breadth", "microdata_breadth")
    liq = {}
    for c, df in dfs_new.items():
        qv = (df["close"] * df["volume"]).tail(540)
        liq[c] = float(qv.groupby(np.arange(len(qv)) // 6).sum().median())
    thr = np.quantile(list(liq.values()), 1 / 3)
    keep = [c for c in dfs_new if liq[c] >= thr]
    print("T1+T2 tutulan yeni coin: %d (T3 atıldı: %d)" % (len(keep), len(dfs_new) - len(keep)))
    co = build_entries(dfs_old)
    cn = build_entries({c: dfs_new[c] for c in keep})
    comb = dict(co); comb.update(cn)
    f_old, f_comb = flow1y(co), flow1y(comb)
    print("akış SON-1Y: eski %.0f/10g → temiz-birleşik %.0f/10g (×%.1f)" % (f_old, f_comb, f_comb / f_old))
    print("=" * 100)
    print("  Step1 +%10 hız-MC (statik −%10/günlük−%5/60g) — AYNI config, N=300")
    P = dict(r_build=0.0030, r_protect=0.0005, cushion=0.08, maxr=0.012, max_pos=8)
    rng = np.random.default_rng(11)
    for label, coins in (("eski-43", co), ("TEMİZ-118", comb)):
        tl = build_timeline(coins)
        starts = rng.integers(int(len(tl) * 0.25), int(len(tl) * 0.7), size=N)
        p, b, med, fast = mc(coins, tl, starts, P, 1.5, *MILD)
        hp, hb, hmed, hfast = mc(coins, tl, starts, P, 1.5, *HARSH)
        print("  %-10s P(pass) %.0f/%.0f%% · blow %.0f/%.0f%% · medyan %d/%dg · ≤10g %.0f/%.0f%%  (MILD/HARSH)" % (
            label, p, hp, b, hb, med, hmed, fast, hfast))
    # hız için bir kademe yüksek base ile temiz evren (akış↑ → aynı blow'da daha hızlı mı?)
    P2 = dict(r_build=0.0045, r_protect=0.0005, cushion=0.08, maxr=0.018, max_pos=8)
    tl = build_timeline(comb)
    starts = rng.integers(int(len(tl) * 0.25), int(len(tl) * 0.7), size=N)
    p, b, med, fast = mc(comb, tl, starts, P2, 1.5, *MILD)
    hp, hb, hmed, hfast = mc(comb, tl, starts, P2, 1.5, *HARSH)
    print("  %-10s P(pass) %.0f/%.0f%% · blow %.0f/%.0f%% · medyan %d/%dg · ≤10g %.0f/%.0f%%  (base %%0.45)" % (
        "TEMİZ+hız", p, hp, b, hb, med, hmed, fast, hfast))
    print("=" * 100)


if __name__ == "__main__":
    main()
