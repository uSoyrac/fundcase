#!/usr/bin/env python3
"""lsx_oivol_falsify.py — kalan 2 canlı-kazanan (③ adayı) 2yıl OOS testi.
  lsx   = -(long_frac-0.5)*4  (positioning aşırılık kontraryan; ls_ratio'dan)
  oivol = vol_chg - oi_chg - 0.5*price_chg  (hacim önde/OI-fiyat geride = erken-giriş LONG)
Test: dose-response (sinyal gücü → 24h getiri, yön gömülü) + L/S portföy full/OOS."""
import numpy as np, pandas as pd, glob, os
FEE = 0.0014; H = 6   # 24h forward (4h bar)


def load(pat, cols):
    d = {}
    for f in glob.glob(pat):
        c = os.path.basename(f).split("_")[0]
        df = pd.read_csv(f); df["ts"] = pd.to_datetime(df["ts"]); df = df.set_index("ts").sort_index()
        df = df[~df.index.duplicated()]
        if all(k in df for k in cols): d[c] = df[cols]
    return d


def test_signal(name, sigmat, fwd):
    s = sigmat.values.flatten(); r = (np.sign(sigmat) * fwd).values.flatten()
    m = np.isfinite(s) & np.isfinite(r) & (np.abs(s) > 1e-9)
    a, rr = np.abs(s[m]), r[m]
    qs = np.quantile(a, np.linspace(0, 1, 11)); cells = []
    for q in range(10):
        lo, hi = qs[q], qs[q + 1]
        mm = (a >= lo) & (a <= hi if q == 9 else a < hi)
        if mm.sum(): cells.append(rr[mm].mean() * 100)
    corr = np.corrcoef(np.arange(len(cells)), cells)[0, 1]
    # L/S portföy
    K = 5; rets = []; sv = sigmat.values; fv = fwd.values
    for i in range(len(sigmat)):
        row = sv[i]; fr = fv[i]; v = np.isfinite(row) & np.isfinite(fr)
        if v.sum() < 2 * K: rets.append(0.0); continue
        idx = np.where(v)[0]; o = idx[np.argsort(row[idx])]
        rets.append(0.5 * (fr[o[-K:]].mean() - fr[o[:K]].mean()) - FEE)
    rets = np.array([x for x in rets if np.isfinite(x)])
    def st(x):
        nav = np.cumprod(1 + x); pk = np.maximum.accumulate(nav)
        return (nav[-1] ** (6 * 365 / max(len(x), 1)) - 1) * 100, x.mean() / (x.std() + 1e-12) * (6 * 365) ** 0.5, ((nav - pk) / pk).min() * 100
    sp = int(len(rets) * 0.6)
    af, shf, ddf = st(rets); ao, sho, ddo = st(rets[sp:])
    print("=" * 80)
    print("  %s — dose-response korr %+.3f (D1 %+.2f%% → D10 %+.2f%%)" % (name, corr, cells[0], cells[-1]))
    print("  L/S FULL: yıllık %+.0f%% Sharpe %+.2f MaxDD %.1f%% · OOS: yıllık %+.0f%% Sharpe %+.2f MaxDD %.1f%%" % (
        af, shf, ddf, ao, sho, ddo))
    verdict = "✅ GERÇEK" if (corr > 0.5 and sho > 0) else "❌ ÇÜRÜK (5-gün serabı)"
    print("  VERDICT: %s" % verdict)


def main():
    met = load("metricsdata/*_metrics_4h.csv", ["oi", "ls_ratio"])
    mkt = load("mktdata/*_4h.csv", ["close", "volume"])
    coins = sorted([c for c in met if c in mkt])
    print("metrics+fiyat: %d coin (2024-2026 ~2y)" % len(coins))
    # ortak index
    idx = None
    for c in coins:
        j = met[c].index.intersection(mkt[c].index)
        idx = j if idx is None else idx.union(j)
    idx = idx.sort_values()
    close = pd.DataFrame({c: mkt[c]["close"].reindex(idx) for c in coins})
    vol = pd.DataFrame({c: mkt[c]["volume"].reindex(idx) for c in coins})
    oi = pd.DataFrame({c: met[c]["oi"].reindex(idx) for c in coins})
    lsr = pd.DataFrame({c: met[c]["ls_ratio"].reindex(idx) for c in coins})
    fwd = close.shift(-H) / close - 1.0
    # lsx
    longf = lsr / (1.0 + lsr); lsx = -(longf - 0.5) * 4.0
    # oivol: 24h chg'ler
    vc = vol / vol.shift(H) - 1.0; oc = oi / oi.shift(H) - 1.0; pf = close / close.shift(H) - 1.0
    oivol = vc - oc - 0.5 * pf
    test_signal("lsx (positioning aşırılık kontraryan)", lsx, fwd)
    test_signal("oivol (hacim>OI erken-giriş)", oivol, fwd)
    print("=" * 80)


if __name__ == "__main__":
    main()
