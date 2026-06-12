#!/usr/bin/env python3
"""breadth_tier_test.py — genişlik İNCELTME: 113 yeni coinin edge'i pooled ~sıfır (OOS +0.005).
Mekanik hipotez (ön-kayıt): maliyet/etki likiditeyle ters ölçeklenir → YÜKSEK-likidite
katmanında edge korunur, düşükte ölür. Tercile testi: medyan günlük quote-hacim → 3 katman →
katman başına lam≥2 avgR FULL/OOS + dose-korr. Kabul: üst-katman OOS avgR ≥ +0.05."""
import numpy as np, pandas as pd, glob, os
from falsify import load_with_micro, collect_breakouts


def main():
    dfs = load_with_micro("mktdata_breadth", "microdata_breadth")
    # likidite: medyan günlük quote-hacim (close×volume, 6 bar/gün)
    liq = {}
    for c, df in dfs.items():
        qv = (df["close"] * df["volume"]).tail(540)        # son ~90 gün
        liq[c] = float(qv.groupby(np.arange(len(qv)) // 6).sum().median())
    bk = collect_breakouts(dfs)
    bk["liq"] = bk["coin"].map(liq) if "coin" in bk.columns else np.nan
    if "coin" not in bk.columns:
        print("HATA: collect_breakouts 'coin' kolonu yok"); print(bk.columns.tolist()); return
    qs = np.quantile(list(liq.values()), [1 / 3, 2 / 3])
    def tier(v): return "T1-likit" if v >= qs[1] else ("T2-orta" if v >= qs[0] else "T3-ince")
    bk["tier"] = bk["liq"].map(tier)
    bk = bk.sort_values("exit_ts").reset_index(drop=True)
    sp = int(len(bk) * 0.6)
    bk["oos"] = np.arange(len(bk)) >= sp
    print("=" * 96)
    print("  113 YENİ COİN × LİKİDİTE KATMANI — lam≥2 net avgR (kabul: T1 OOS ≥ +0.05)")
    print("=" * 96)
    print("  %-10s %8s %10s %12s %12s %14s" % ("katman", "coin", "medyan$V", "n(lam≥2)", "avgR-FULL", "avgR-OOS"))
    for t in ["T1-likit", "T2-orta", "T3-ince"]:
        sub = bk[(bk["tier"] == t) & (bk["lam"] >= 2.0)]
        so = sub[sub["oos"]]
        coins_t = [c for c in liq if tier(liq[c]) == t]
        mv = np.median([liq[c] for c in coins_t]) / 1e6
        print("  %-10s %8d %9.0fM %12d %+12.3f %+14.3f" % (
            t, len(coins_t), mv, len(sub), sub["r"].mean() if len(sub) else float("nan"),
            so["r"].mean() if len(so) > 30 else float("nan")))
    # eski-43 referans
    old = collect_breakouts(load_with_micro()).sort_values("exit_ts").reset_index(drop=True)
    osp = int(len(old) * 0.6)
    g = old[old["lam"] >= 2.0]; go = old.iloc[osp:]; go = go[go["lam"] >= 2.0]
    print("  %-10s %8d %10s %12d %+12.3f %+14.3f   <- referans" % ("eski-43", 43, "-", len(g), g["r"].mean(), go["r"].mean()))
    print("=" * 96)


if __name__ == "__main__":
    main()
