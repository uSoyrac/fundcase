#!/usr/bin/env python3
"""regime_gate_test.py — KULLANICI HİPOTEZİ: 'sunucu botları gün-gün kârlı, uzun-dönem batıyor;
ölene-kadar-açık bot istemiyoruz — fırsat penceresinde gir/kâr-al/çık.'
Bilimsel hali: fund72 kontraryan UZUN-DÖNEM TERS (-0.589) ama belki REJİM-YEREL kârlı:
kontraryan stratejiler TREND'de ezilir (squeeze devam eder), RANGE/chop'ta kazanır.
TEST: fund72 event'lerini (aşırı |sig|, 24h hold, maliyetli) BTC-rejimine göre ayır:
  RANGE = |BTC 10g getiri| medyan-altı · TREND = medyan-üstü
Kabul (ön-kayıt): RANGE'de avgNet>0 FULL VE OOS — o zaman 'fırsat-penceresi botu' meşru."""
import numpy as np, pandas as pd
from fund72_falsify import load_series, persist_sig

COST = 0.0014; H = 3      # 3×8h = 24h hold
EXT_Q = 0.85              # aşırı |sig| eşiği (üst %15)


def main():
    fund = load_series("funddata/*_funding.csv", "funding")
    close = load_series("mktdata/*_4h.csv", "close")
    coins = sorted([c for c in fund if c in close])
    fmat = pd.DataFrame({c: fund[c] for c in coins}).sort_index().dropna(how="all")
    clmat = pd.DataFrame({c: close[c] for c in coins}).reindex(fmat.index, method="ffill")
    # BTC rejimi: |10 günlük getiri| (30×8h bar) — funding index'inde
    btc = clmat["BTC"]
    ret10 = (btc / btc.shift(30) - 1.0).abs()
    thr_med = ret10.median()
    regime_range = ret10 < thr_med          # True = RANGE (yatay)
    sig = pd.DataFrame({c: persist_sig(fmat[c].values) for c in coins}, index=fmat.index)
    fwd = clmat.shift(-H) / clmat - 1.0
    # event havuzu (coin-bazında 24h dedupe)
    evs = []   # (ts_idx, |sig|, net, range?)
    for c in coins:
        s = sig[c].values; f = fwd[c].values; last = -1
        for i in range(len(s) - H):
            if i <= last or not np.isfinite(s[i]) or not np.isfinite(f[i]): continue
            if abs(s[i]) < 1e-9: continue
            d = 1 if s[i] > 0 else -1
            evs.append((i, abs(s[i]), d * f[i] - COST, bool(regime_range.iloc[i])))
            last = i + H if abs(s[i]) > 0 else last
    evs.sort(key=lambda e: e[0])
    mag = np.array([e[1] for e in evs]); net = np.array([e[2] for e in evs])
    rng = np.array([e[3] for e in evs]); n = len(evs)
    ext = mag >= np.quantile(mag, EXT_Q)
    sp = int(n * 0.6); oos = np.zeros(n, bool); oos[sp:] = True
    print("=" * 96)
    print("  fund72 KONTRARYAN × BTC-REJİMİ (24h hold, maliyetli, n=%d, aşırı-eşik üst %%15)" % n)
    print("=" * 96)
    print("  %-34s %8s %9s %9s %12s" % ("kesit", "n", "WR%", "avgNet%", "OOS-avgNet%"))
    for label, m in [
        ("TÜM (rejim yok — bilinen: TERS)", np.ones(n, bool)),
        ("TREND rejimi", ~rng),
        ("RANGE rejimi", rng),
        ("TREND × aşırı-sig", (~rng) & ext),
        ("RANGE × aşırı-sig", rng & ext),
    ]:
        mo = m & oos
        if m.sum() < 30: continue
        print("  %-34s %8d %8.0f %9.3f %12.3f" % (
            label, m.sum(), 100 * (net[m] > 0).mean(), net[m].mean() * 100,
            net[mo].mean() * 100 if mo.sum() > 20 else float("nan")))
    print("-" * 96)
    # ve ters yön: TREND'de kontraryanın TERSİ (= momentum/trend-takip) pozitif mi?
    print("  %-34s %8d %8.0f %9.3f %12.3f   <- kontraryanın TERSİ (trende katıl)" % (
        "TREND × aşırı: MOMENTUM yönü", ((~rng) & ext).sum(),
        100 * ((-net[(~rng) & ext] - 2 * COST) > 0).mean(),
        (-net[(~rng) & ext]).mean() * 100 - 2 * COST * 100,
        (-net[(~rng) & ext & oos]).mean() * 100 - 2 * COST * 100))
    print("=" * 96)
    print("  ÖN-KAYIT KABUL: 'RANGE × aşırı' avgNet>0 FULL VE OOS → fırsat-penceresi botu MEŞRU.")


if __name__ == "__main__":
    main()
