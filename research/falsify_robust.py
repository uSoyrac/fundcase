#!/usr/bin/env python3
"""falsify_robust.py — lam edge'inin ROBUSTNESS kilidi: β/L duyarlılığı + long/short simetri.
Knife-edge mi yoksa sağlam mı? Tek yön mü yoksa simetrik mi?"""
import numpy as np
from falsify import load_with_micro, collect_breakouts


def dose_corr(bk, deciles=10):
    """lam decile → avgR lineer korelasyonu (monotonluk gücü)."""
    lam, r = bk["lam"].to_numpy(), bk["r"].to_numpy()
    if len(bk) < deciles * 20:
        return float("nan"), float("nan"), float("nan")
    qs = np.quantile(lam, np.linspace(0, 1, deciles + 1))
    cells = []
    for q in range(deciles):
        lo, hi = qs[q], qs[q + 1]
        m = (lam >= lo) & (lam <= hi if q == deciles - 1 else lam < hi)
        cells.append(r[m].mean() if m.sum() else np.nan)
    cells = np.array(cells)
    corr = np.corrcoef(np.arange(deciles), cells)[0, 1]
    return float(corr), float(cells[0]), float(cells[-1])   # korelasyon, D-low, D-high


def main():
    print("=" * 92)
    print("  ROBUSTNESS — β/L DUYARLILIK (knife-edge mi?) ve LONG/SHORT SİMETRİ")
    print("=" * 92)
    dfs = load_with_micro()

    print("\n  β/L taraması — dose-response korelasyonu (full + 2025-26 OOS):")
    print(f"  {'β':>5}{'L':>5}{'N':>8}{'full-corr':>12}{'Dlow→Dhigh':>20}{'OOS-corr':>12}")
    for beta in (0.2, 0.3, 0.4):
        for L in (40, 60, 90):
            bk = collect_breakouts(dfs, beta=beta, L=L)
            c, lo, hi = dose_corr(bk)
            oos = bk[bk["exit_ts"].str[:4].isin(["2025", "2026"])]
            co, _, _ = dose_corr(oos, deciles=5)
            print(f"  {beta:>5}{L:>5}{len(bk):>8}{c:>+12.3f}{f'{lo:+.3f}→{hi:+.3f}':>20}{co:>+12.3f}")

    print("\n  LONG/SHORT SİMETRİ (β=0.3,L=60) — lam dose-response her yönde tutuyor mu?")
    bk = collect_breakouts(dfs, beta=0.3, L=60)
    for side, d in [("LONG", 1), ("SHORT", -1)]:
        sub = bk[bk["d"] == d]
        c, lo, hi = dose_corr(sub)
        oos = sub[sub["exit_ts"].str[:4].isin(["2025", "2026"])]
        co, _, _ = dose_corr(oos, deciles=5)
        print(f"    {side:<6} N={len(sub):<6} full-corr={c:+.3f}  Dlow={lo:+.3f} Dhigh={hi:+.3f}  OOS-corr={co:+.3f}")
    print("=" * 92)


if __name__ == "__main__":
    main()
