#!/usr/bin/env python3
"""lsx_selective.py — lsx (positioning aşırılık kontraryan) MALİYET-BİLİNÇLİ test (③ adayı).
dose-response +0.815 pozitifti ama her-4h-tam-kitap maliyet yedi. Burada EVENT-BASED:
sadece AŞIRI |lsx| girişlerde gir, ~24h HOLD, tek round-trip maliyet (her-bar churn YOK).
Soru: seçici + hold ile net-of-cost POZİTİF mi? Eşik taraması + OOS + per-coin/full."""
import numpy as np, pandas as pd, glob, os
COST = 0.0014; H = 6   # 24h hold (4h bar)


def load(pat, cols):
    d = {}
    for f in glob.glob(pat):
        c = os.path.basename(f).split("_")[0]
        df = pd.read_csv(f); df["ts"] = pd.to_datetime(df["ts"]); df = df.set_index("ts").sort_index()
        df = df[~df.index.duplicated()]
        if all(k in df for k in cols): d[c] = df
    return d


def main():
    met = load("metricsdata/*_metrics_4h.csv", ["ls_ratio"])
    mkt = load("mktdata/*_4h.csv", ["close"])
    coins = sorted([c for c in met if c in mkt])
    print("coin: %d (2024-2026 ~2y)" % len(coins))
    # tüm event'leri topla: (ts, |lsx|, dir*fwd_net)
    rows = []
    for c in coins:
        j = met[c].index.intersection(mkt[c].index)
        ls = met[c]["ls_ratio"].reindex(j).values
        cl = mkt[c]["close"].reindex(j).values
        lf = ls / (1.0 + ls)               # long fraction
        lsx = -(lf - 0.5) * 4.0            # kontraryan: aşırı-long→negatif(SHORT)
        for i in range(len(cl) - H):
            if not np.isfinite(lsx[i]) or not np.isfinite(cl[i]) or cl[i] <= 0: continue
            d = 1 if lsx[i] > 0 else -1
            fwd = cl[i + H] / cl[i] - 1.0
            net = d * fwd - COST
            rows.append((str(j[i]), abs(lsx[i]), net))
    rows.sort(key=lambda r: r[0])
    mag = np.array([r[1] for r in rows]); net = np.array([r[2] for r in rows])
    n = len(rows); sp = int(n * 0.6)
    print("=" * 84)
    print("  EŞİK TARAMASI: sadece |lsx|>eşik gir, 24h hold, net-of-cost (n_havuz=%d)" % n)
    print("  %-12s %9s %8s %10s %12s" % ("eşik", "n-işlem", "WR%", "avgNet%", "OOS-avgNet%"))
    for thr in [0.0, 0.4, 0.8, 1.2, 1.6, 2.0]:
        m = mag >= thr
        if m.sum() < 50: continue
        oos_m = m.copy(); oos_m[:sp] = False
        wr = 100 * (net[m] > 0).mean()
        print("  |lsx|>=%-6.1f %9d %7.0f %9.3f %11.3f" % (
            thr, m.sum(), wr, net[m].mean() * 100, net[oos_m].mean() * 100 if oos_m.sum() else 0))
    # dose-response net (decile)
    print("-" * 84)
    qs = np.quantile(mag, np.linspace(0, 1, 11)); cells = []
    for q in range(10):
        lo, hi = qs[q], qs[q + 1]
        mm = (mag >= lo) & (mag <= hi if q == 9 else mag < hi)
        if mm.sum(): cells.append(net[mm].mean() * 100)
    corr = np.corrcoef(np.arange(len(cells)), cells)[0, 1]
    print("  NET dose-response (decile avgNet%%): " + " ".join("%+.2f" % c for c in cells))
    print("  korr=%+.3f · en-aşırı decile net %+.3f%%/24h" % (corr, cells[-1]))
    print("=" * 84)
    print("  GERÇEK mi: aşırı-eşikte OOS-avgNet>0 + dose-response monoton → ③ için tradeable.")


if __name__ == "__main__":
    main()
