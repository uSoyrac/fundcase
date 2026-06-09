#!/usr/bin/env python3
"""test_1h.py — 1H frekans/cost-wall testi. lam-gate'li breakout 1H'de:
net avgR (maliyet otomatik 2.1x cost-in-R), dose-response, OOS, frekans, 4H ile kıyas.
Sentezci tahmini: dose-response tutar ama net edge maliyetten başabaşa iner."""
import os, glob
import numpy as np, pandas as pd
import falsify
from falsify import collect_breakouts, atr

LAM_MIN, LAM_EXEMPT = 1.0, 2.2


def load_1h():
    out = {}
    for f in sorted(glob.glob("mktdata_1h/*_1h.csv")):
        c = os.path.basename(f).split("_")[0]
        df = pd.read_csv(f); df["ts"] = pd.to_datetime(df["ts"]); df = df.set_index("ts").sort_index()
        mp = "microdata_1h/%s_micro.csv" % c
        if os.path.exists(mp):
            m = pd.read_csv(mp); m["ts"] = pd.to_datetime(m["ts"]); m = m.set_index("ts").sort_index()
            df = df.join(m[["num_trades", "taker_buy_ratio"]], how="left")
            df["taker_buy_ratio"] = df["taker_buy_ratio"].ffill().fillna(0.5)
            df["num_trades"] = df["num_trades"].ffill().fillna(0.0)
        else:
            df["taker_buy_ratio"] = 0.5; df["num_trades"] = 0.0
        out[c] = df
    return out


def gated(bk):
    """validated gate: lam>1 AND (vr<1 OR lam>=2.2). (lam-rising'i collect'te yok, ayrı bakarız)"""
    d, lam, vr = bk["d"].to_numpy(), bk["lam"].to_numpy(), bk["vr"].to_numpy()
    fresh = vr < 1.0
    return (lam > LAM_MIN) & (fresh | (lam >= LAM_EXEMPT))


def dose(sub):
    if len(sub) < 200: return float("nan")
    lam, r = sub["lam"].to_numpy(), sub["r"].to_numpy()
    qs = np.quantile(lam, np.linspace(0, 1, 11)); cells = []
    for q in range(10):
        lo, hi = qs[q], qs[q + 1]
        m = (lam >= lo) & (lam <= hi if q == 9 else lam < hi)
        if m.sum(): cells.append(r[m].mean())
    return float(np.corrcoef(np.arange(len(cells)), cells)[0, 1])


def main():
    print("1H veri yükleniyor..."); dfs = load_1h()
    if not dfs:
        print("HATA: mktdata_1h boş — fetch_1h.py bitmedi mi?"); return
    span = max(len(d) for d in dfs.values())
    print("  %d coin, ~%d bar (1H)" % (len(dfs), span))
    bk = collect_breakouts(dfs)
    bk = bk.sort_values("exit_ts").reset_index(drop=True)
    split = int(len(bk) * 0.6); oos = bk.iloc[split:]
    g = gated(bk); og = gated(oos)
    print("=" * 88)
    print("  1H lam-gate'li breakout (net avgR = maliyet DAHİL, cost-in-R 1H'de ~2.1x)")
    print("=" * 88)
    print("  %-22s %8s %8s %8s %8s" % ("set", "N", "avgR", "WR%", "OOS-avgR"))
    for name, m, om in [("base (tüm breakout)", np.ones(len(bk), bool), np.ones(len(oos), bool)),
                        ("lam-gate (validated)", g, og)]:
        s = bk[m]; o = oos[om]
        wr = 100 * (s["r"] > 0).mean() if len(s) else 0
        print("  %-22s %8d %+8.3f %8.1f %+8.3f" % (name, len(s), s["r"].mean(), wr, o["r"].mean() if len(o) else 0))
    print("  lam dose-response (full): %+.3f · OOS(son%%40): %+.3f" % (dose(bk), dose(oos)))
    # frekans: yıllık işlem (1H bar/yıl = 24*365)
    yrs = span / (24 * 365)
    print("  frekans: ~%.0f gated-işlem/yıl (1H) vs ~1850 (4H ensemble)" % (g.sum() / yrs if yrs else 0))
    print("=" * 88)
    print("  KIYAS: 4H lam-gate net avgR ~+0.10-0.12. 1H bunun ÜSTÜNDE mi (frekans kazancı net)")
    print("  yoksa ALTINDA/negatif mi (maliyet duvarı yedi) → karar bu.")


if __name__ == "__main__":
    main()
