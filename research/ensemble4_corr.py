#!/usr/bin/env python3
"""ensemble4_corr.py — 4 survivor edge'in GERÇEK korelasyon matrisi + eşit-ağırlık kombo DD.
Adversaryel'in 'hepsi kripto-beta, dekorelasyon yanılsaması' endişesini ampirik test.
Her edge günlük getiri: lam=Sprint-motor (ensemble_lam_lsx.lam_daily); lsx/regime/vwap=
aşırı-uç(üst%15) seçici, dir=sign(sig), 24h hold, dollar-nötr top/bottom, maliyetli.
Ortak pencere. Çıktı: 4×4 korr + eşit-ağırlık kombo Sharpe/MaxDD vs en-iyi-tek."""
import numpy as np, pandas as pd, glob, os
from ensemble_lam_lsx import lam_daily, WIN_START
from falsify import load_with_micro
from prop_sim import build_entries
from monte_carlo import build_timeline
from all_signals_falsify import sig_lsx, sig_regime, sig_vwap, load as aload

COST = 0.0014; H = 6; EXTQ = 0.85; K = 5


def daily_xsec(dfs, fn, label):
    """her bar: |sig| üst-%15 evreninde top-K LONG / bottom-K SHORT (dir=sign), 24h fwd, günlük."""
    # tüm coin-zaman sig + fwd
    recs = {}
    for c, df in dfs.items():
        if "close" not in df: continue
        px = df["close"].values; sig, _ = fn(df); fwd = np.roll(px, -H) / px - 1.0
        for t in range(H + 30, len(px) - H):
            if np.isfinite(sig[t]) and np.isfinite(fwd[t]) and abs(sig[t]) > 1e-9:
                recs.setdefault(str(df.index[t])[:10], []).append((sig[t], fwd[t]))
    daily = {}
    for day, lst in recs.items():
        if len(lst) < 2 * K: continue
        lst.sort(key=lambda x: x[0])
        longs = lst[-K:]; shorts = lst[:K]
        lr = np.mean([f for _, f in longs]); sr = np.mean([f for _, f in shorts])
        daily[day] = 0.5 * (lr - sr) - COST
    return pd.Series(daily).sort_index()


def main():
    print("lam günlük..."); dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rl = lam_daily(coins, tl)
    rl.index = [str(x)[:10] for x in rl.index]; rl = rl.groupby(level=0).sum()
    print("metricsdata sinyalleri...")
    B0 = aload("metricsdata/*_metrics_4h.csv", ["oi", "ls_ratio"])
    A = aload("mktdata/*_4h.csv", ["close", "volume"])
    B = {}
    for c, df in B0.items():
        if c in A:
            j = df.index.intersection(A[c].index)
            B[c] = df.reindex(j).join(A[c][["close", "volume"]].reindex(j))
    rx = daily_xsec(B, sig_lsx, "lsx")
    rg = daily_xsec(B, sig_regime, "regime")
    rv = daily_xsec(A, sig_vwap, "vwap")
    df = pd.DataFrame({"lam": rl, "lsx": rx, "regime": rg, "vwap": rv}).dropna(how="all")
    df = df[df.index >= WIN_START[:10]].fillna(0.0)
    print("ortak gün: %d" % len(df))
    print("=" * 70)
    print("  4 EDGE GÜNLÜK KORELASYON MATRİSİ (≈0 = gerçek dekorelasyon)")
    print("=" * 70)
    cm = df.corr()
    print(cm.round(2).to_string())
    print("-" * 70)
    def st(s):
        nav = (1 + s).cumprod(); pk = nav.cummax()
        return s.mean() / (s.std() + 1e-12) * np.sqrt(365), ((nav - pk) / pk).min() * 100
    print("  %-16s %8s %8s" % ("edge/kombo", "Sharpe", "MaxDD%"))
    for c in df.columns:
        sh, dd = st(df[c]); print("  %-16s %+8.2f %8.1f" % (c, sh, dd))
    eq = df.mean(axis=1)   # eşit-ağırlık
    sh, dd = st(eq); print("  %-16s %+8.2f %8.1f  <- 4'lü eşit-ağırlık" % ("ENSEMBLE-4", sh, dd))
    print("=" * 70)
    print("  ort-ikili-korr: %.2f · kombo Sharpe tek-edge ort'sından yüksek + DD düşükse → gerçek." % (
        cm.values[np.triu_indices(4, 1)].mean()))


if __name__ == "__main__":
    main()
