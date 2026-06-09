#!/usr/bin/env python3
"""fund72_falsify.py — PROJE ③ sinyali: funding-72h-persistence (kontraryan) GERÇEK mi?
Sunucu canlı: fund72 PF 1.94, +$1733, broad (top3 %31). Ama 5-gün. Burada 4-5 YIL OOS test:
  signal = -mean(son 9×8h funding) × kalıcılık → ısrarlı(+)funding=SHORT, ısrarlı(−)=LONG.
Test: (A) dose-response |signal| decile → forward kontraryan getiri monoton mu, (B) L/S portföy
equity (Sharpe/DD/yıllık) full + OOS. Mean-reversion + funding-carry (short crowded → funding AL)."""
import numpy as np, pandas as pd, glob, os
FEE = 0.0014


def load_series(pat, col, idx=0):
    d = {}
    for f in glob.glob(pat):
        c = os.path.basename(f).split("_")[0]
        df = pd.read_csv(f); df["ts"] = pd.to_datetime(df["ts"]); df = df.set_index("ts").sort_index()
        if col in df: d[c] = df[col][~df.index.duplicated()]
    return d


def persist_sig(vals):
    out = np.full(len(vals), np.nan)
    for i in range(9, len(vals)):
        w = vals[i - 9:i]; m = w.mean()
        if not np.isfinite(m): continue
        pers = np.mean((w > 0) == (m > 0))
        out[i] = -m * pers * 1000.0
    return out


def main():
    fund = load_series("funddata/*_funding.csv", "funding")
    close = load_series("mktdata/*_4h.csv", "close")
    coins = sorted([c for c in fund if c in close])
    print("Funding+fiyat: %d coin" % len(coins))
    fmat = pd.DataFrame({c: fund[c] for c in coins}).sort_index().dropna(how="all")
    # 8h funding ts'e fiyatı hizala (ffill), 3×8h≈24h forward getiri
    clmat = pd.DataFrame({c: close[c] for c in coins}).reindex(fmat.index, method="ffill")
    sig = pd.DataFrame({c: persist_sig(fmat[c].values) for c in coins}, index=fmat.index)
    fwd = clmat.shift(-3) / clmat - 1.0
    # carry: short crowded-long (sig<0 yön SHORT) → funding AL; yön = sign(sig)
    pos = np.sign(sig)                      # +1 LONG / -1 SHORT (kontraryan, sinyalde gömülü)
    cret = pos * fwd                        # kontraryan getiri (fiyat)
    # ── A) dose-response: |signal| decile → ortalama kontraryan getiri ──
    s = sig.values.flatten(); r = cret.values.flatten()
    m = np.isfinite(s) & np.isfinite(r) & (np.abs(s) > 1e-9)
    s, r = np.abs(s[m]), r[m]; sgn = np.sign(sig.values.flatten()[m])
    n = len(s); split = int(n * 0.6)
    print("=" * 80)
    print("  A) DOSE-RESPONSE: funding-persistence gücü → 24h kontraryan getiri (n=%d)" % n)
    qs = np.quantile(s, np.linspace(0, 1, 11)); cells = []
    for q in range(10):
        lo, hi = qs[q], qs[q + 1]
        mm = (s >= lo) & (s <= hi if q == 9 else s < hi)
        if mm.sum(): cells.append(r[mm].mean() * 100)
    corr = np.corrcoef(np.arange(len(cells)), cells)[0, 1]
    print("  decile getiri%%: " + " ".join("%+.2f" % c for c in cells))
    print("  monotonluk korr = %+.3f  (D1 %+.2f%% → D10 %+.2f%%)" % (corr, cells[0], cells[-1]))
    # ── B) L/S portföy: her periyot top-K kontraryan-LONG / top-K kontraryan-SHORT ──
    print("=" * 80)
    print("  B) L/S PORTFÖY (her 8h rebalance, K=5, dollar-nötr, maliyet+):")
    K = 5; rets = []
    sv = sig.values; fv = fwd.values
    for i in range(len(fmat)):
        row = sv[i]; fr = fv[i]
        valid = np.isfinite(row) & np.isfinite(fr)
        if valid.sum() < 2 * K: rets.append(0.0); continue
        idx = np.where(valid)[0]; order = idx[np.argsort(row[idx])]
        longs = order[-K:]; shorts = order[:K]   # sig yüksek=LONG sinyali, düşük=SHORT
        lr = fr[longs].mean(); sr = fr[shorts].mean()
        rets.append(0.5 * (lr - sr) - FEE)
    rets = np.array(rets)
    rets = rets[np.isfinite(rets)]
    def stats(x, lbl):
        nav = np.cumprod(1 + x); peak = np.maximum.accumulate(nav)
        mdd = ((nav - peak) / peak).min() * 100
        ann = nav[-1] ** (3 * 365 / max(len(x), 1)) - 1   # 8h bar → 3/gün
        sh = x.mean() / (x.std() + 1e-12) * (3 * 365) ** 0.5
        print("  %-10s yıllık %+6.0f%% · Sharpe %+.2f · MaxDD %6.1f%% · n=%d" % (lbl, ann * 100, sh, mdd, len(x)))
    stats(rets, "FULL")
    sp = int(len(rets) * 0.6)
    stats(rets[sp:], "OOS(%40)")
    print("=" * 80)
    print("  GERÇEK mi: dose-response monoton (>0.5) VE OOS Sharpe>0 + MaxDD makul → ③ için kullan.")


if __name__ == "__main__":
    main()
