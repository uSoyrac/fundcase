#!/usr/bin/env python3
"""cross_sectional_mc.py — MARKET-NÖTR cross-sectional momentum botu: +%10'a-süre / MaxDD / P(geçiş).
Canlı liderlik tablosu (xsec/xasset, ~%0 DD) hipotezini bizim 43-coin × 5.4y veride doğrula.
Her bar: momentum'a göre sırala → top-K LONG / bottom-K SHORT, dollar-nötr (lev 1). Sonra
rastgele başlangıçlı challenge sim: +%10 (geç) vs −%10 (patla) vs süre. Hawkes ile kıyas için."""
import numpy as np, pandas as pd
from falsify import load_with_micro

FEE = 0.0014  # round-trip maliyet (turnover'a uygulanır)
BARS_DAY = 6  # 4H → gün


def strat_returns(dfs, L=24, K=5, rebal=6, lev=1.0):
    closes = pd.DataFrame({c: df["close"] for c, df in dfs.items()}).sort_index()
    mom = closes.pct_change(L)
    rets = closes.pct_change()
    idx = closes.index
    out = []; lo = set(); sh = set()
    for i in range(L + 2, len(idx)):
        if (i % rebal == 0) or not lo:
            row = mom.iloc[i - 1].dropna()
            if len(row) < 2 * K:
                out.append(0.0); continue
            rk = row.sort_values()
            nsh = set(rk.index[:K]); nlo = set(rk.index[-K:])
            turn = ((len(nlo ^ lo) + len(nsh ^ sh)) / (4.0 * K)) if lo else 1.0
            lo, sh = nlo, nsh
            cost = turn * FEE
        else:
            cost = 0.0
        lr = rets.iloc[i][list(lo)].mean(); sr = rets.iloc[i][list(sh)].mean()
        if not np.isfinite(lr): lr = 0.0
        if not np.isfinite(sr): sr = 0.0
        out.append(lev * 0.5 * (lr - sr) - cost)   # dollar-nötr 1x
    return np.array(out), idx[L + 2:]


def challenge_mc(r, n=500, target=0.10, floor=0.10, max_days=90, seed=11):
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, max(1, len(r) - max_days * BARS_DAY), size=n)
    o = {"pass": 0, "fail": 0, "timeout": 0}; pdays = []
    for s in starts:
        nav = 1.0; peakdd = 0.0; res = "timeout"
        for k in range(s, min(s + max_days * BARS_DAY, len(r))):
            nav *= (1 + r[k])
            if nav >= 1 + target: res = "pass"; break
            if nav <= 1 - floor: res = "fail"; break
        o[res] += 1
        if res == "pass": pdays.append((k - s) / BARS_DAY)
    return o, pdays


def full_stats(r):
    nav = np.cumprod(1 + r); peak = np.maximum.accumulate(nav)
    mdd = ((nav - peak) / peak).min() * 100
    ann = (nav[-1]) ** (BARS_DAY * 365 / len(r)) - 1
    sh = r.mean() / (r.std() + 1e-12) * (BARS_DAY * 365) ** 0.5
    return ann * 100, mdd, sh


def main():
    print("Veri (43 coin)..."); dfs = load_with_micro()
    print("=" * 92)
    print("  MARKET-NÖTR CROSS-SECTIONAL momentum — +%10 challenge (HyroTrader 2-step ±%10)")
    print("=" * 92)
    print(f"  {'config':<22}{'P(geç)':>8}{'P(patla)':>9}{'P(süre)':>8}{'medyan-gün':>11}{'hızlı%25':>9}{'yıllıkR':>8}{'MaxDD':>7}")
    for L, K, lev in [(24, 5, 1.0), (12, 5, 1.0), (48, 5, 1.0), (24, 3, 1.0), (24, 5, 1.5), (24, 5, 2.0)]:
        r, _ = strat_returns(dfs, L=L, K=K, lev=lev)
        o, pd_ = challenge_mc(r)
        n = sum(o.values())
        med = np.median(pd_) if pd_ else -1
        p25 = np.percentile(pd_, 25) if pd_ else -1
        ann, mdd, sh = full_stats(r)
        print(f"  L{L} K{K} lev{lev:<10}{100*o['pass']/n:>7.0f}%{100*o['fail']/n:>8.0f}%{100*o['timeout']/n:>7.0f}%"
              f"{med:>11.0f}{p25:>9.0f}{ann:>+7.0f}%{mdd:>6.0f}%")
    print("=" * 92)
    print("  medyan-gün = +%10'a ulaşanların ortanca süresi · yıllıkR = stratejinin tam-dönem yıllık getirisi")


if __name__ == "__main__":
    main()
