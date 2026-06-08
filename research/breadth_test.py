#!/usr/bin/env python3
"""breadth_test.py — 20→43 coin BREADTH testi.
(1) lam dose-response YENİ coinlerde tutuyor mu? (edge genelleşiyor mu = robustluk)
(2) ortalama korelasyon düşüyor mu? (3) funded gelir/iflas 20 vs 43 coin (DD↓→risk↑?)."""
import numpy as np, pandas as pd
from falsify import load_with_micro, collect_breakouts
from prop_sim import build_entries
from monte_carlo import build_timeline
from stress_mc import stressed_run

ORIG20 = {"ADA","APT","ARB","ATOM","AVAX","BNB","BTC","DOGE","DOT","ETC",
          "ETH","FIL","INJ","LINK","LTC","NEAR","OP","SOL","UNI","XRP"}
N = 300
MILD = (0.0015, 0.00007)


def dose_corr(sub):
    if len(sub) < 200: return float("nan")
    lam, r = sub["lam"].to_numpy(), sub["r"].to_numpy()
    qs = np.quantile(lam, np.linspace(0, 1, 11))
    cells = []
    for q in range(10):
        lo, hi = qs[q], qs[q+1]
        m = (lam >= lo) & (lam <= hi if q == 9 else lam < hi)
        if m.sum(): cells.append(r[m].mean())
    return float(np.corrcoef(np.arange(len(cells)), cells)[0,1])


def avg_corr(dfs, coins):
    """Günlük getiri ortalama ikili korelasyonu (pozisyon eş-hareketinin vekili)."""
    rets = {}
    for c in coins:
        d = dfs[c]["close"].resample("1D").last().pct_change().dropna()
        rets[c] = d
    M = pd.DataFrame(rets).corr().to_numpy()
    iu = np.triu_indices_from(M, k=1)
    return float(np.nanmean(M[iu]))


def funded_mc(coins_subset_dfs, P):
    coins = build_entries(coins_subset_dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl)*0.6), size=N)
    inc = []; blown = 0
    for s in starts:
        r, d, net = stressed_run(coins, tl, int(s), P, *MILD)
        if r == "blown": blown += 1
        inc.append(net)
    return np.median(inc), 100*blown/N


def main():
    print("Veri yükleniyor (43 coin)..."); dfs = load_with_micro()
    allc = set(dfs.keys()); new = sorted(allc - ORIG20)
    print(f"  toplam {len(allc)} coin · orijinal {len(allc & ORIG20)} · YENİ {len(new)}: {new}")

    print("\n=== (1) lam DOSE-RESPONSE — YENİ coinlerde tutuyor mu? ===")
    bk = collect_breakouts(dfs)
    bk_new = bk[bk["coin"].isin(new)]; bk_old = bk[bk["coin"].isin(ORIG20)]
    print(f"  ORİJİNAL 20  : dose-corr {dose_corr(bk_old):+.3f}  (n={len(bk_old)})")
    print(f"  YENİ {len(new):<2}     : dose-corr {dose_corr(bk_new):+.3f}  (n={len(bk_new)})  ← edge genelleşiyor mu")
    # per-yeni-coin: lam>1 alt-kümesi pozitif mi (kaç coinde edge tutuyor)
    pos = 0
    for c in new:
        s = bk[(bk.coin==c) & (bk.lam>1)]
        if len(s) > 30 and s["r"].mean() > 0: pos += 1
    print(f"  YENİ coinlerin {pos}/{len(new)}'inde lam>1 alt-kümesi POZİTİF (genelleşme breadth'i)")

    print("\n=== (2) ORTALAMA KORELASYON — breadth düşürüyor mu? ===")
    c20 = avg_corr(dfs, [c for c in ORIG20 if c in dfs])
    c43 = avg_corr(dfs, list(allc))
    print(f"  20-coin ort. ikili korelasyon: {c20:.3f}")
    print(f"  43-coin ort. ikili korelasyon: {c43:.3f}   {'↓ DÜŞTÜ (breadth işe yarar)' if c43 < c20 else '~aynı (fayda sınırlı)'}")

    print("\n=== (3) FUNDED gelir/iflas — 20 vs 43 coin (stres, base %0.08, +%5 çek) ===")
    Pf = dict(start=100000.0, target=0.0, total=0.10, daily=0.05, halt=0.03, max_days=365,
              base=0.0008, maxr=0.004, max_pos=5, payout=True, payout_trigger=0.05)
    dfs20 = {c: dfs[c] for c in ORIG20 if c in dfs}
    i20, b20 = funded_mc(dfs20, Pf)
    i43, b43 = funded_mc(dfs, Pf)
    print(f"  20-coin: ${i20:>7,.0f}/yıl  iflas %{b20:.0f}")
    print(f"  43-coin: ${i43:>7,.0f}/yıl  iflas %{b43:.0f}   (aynı risk → DD↓ ise gelir↑ ve/veya iflas↓)")
    # 43-coin'de base'i yükselt → aynı iflasta daha çok gelir mi
    for base, maxr in [(0.0012, 0.006), (0.0016, 0.008)]:
        P2 = {**Pf, "base": base, "maxr": maxr, "max_pos": 6}
        i, b = funded_mc(dfs, P2)
        print(f"  43-coin base %{base*100:.2f}: ${i:>7,.0f}/yıl  iflas %{b:.0f}")
    print("=" * 80)


if __name__ == "__main__":
    main()
