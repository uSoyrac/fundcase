#!/usr/bin/env python3
"""all_signals_falsify.py — deneme_engine'in TÜM sinyallerini tek standart bataryada falsify.
Her sinyal: dir=sign(sig), |sig|-decile dose-response (full+OOS), aşırı-uç (üst %15) seçici
net-of-cost (full+OOS), frekans. Kabul: |OOS dose-korr|>0.5 VE aşırı-uç OOS net>0.
GROUP-A (mktdata 43c×5y): price,hl,vwap,vp,fvg,cvd,taker · GROUP-B (metricsdata 20c×2y):
oi,ls,lsx,regime,oivol · GROUP-C (funddata): funding,fund72. lsx referans (+0.815 bekleniyor)."""
import numpy as np, pandas as pd, glob, os
COST = 0.0014; H = 6; EXTQ = 0.85


def load(pat, cols):
    d = {}
    for f in glob.glob(pat):
        c = os.path.basename(f).split("_")[0]
        df = pd.read_csv(f); df["ts"] = pd.to_datetime(df["ts"]); df = df.set_index("ts").sort_index()
        df = df[~df.index.duplicated()]
        if all(k in df for k in cols): d[c] = df
    return d


def sma(a, w):
    return pd.Series(a).rolling(w, min_periods=max(2, w // 2)).mean().values


def std(a, w):
    return pd.Series(a).rolling(w, min_periods=max(2, w // 2)).std().values


# ── sinyal hesaplayıcılar: df → (signal_array, fwd_return_array) ──
def sig_price(df):
    c = df["close"].values; return (c / np.roll(c, H) - 1.0), None

def sig_hl(df):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    rng = h - l; return np.where(rng > 0, (c - l) / np.where(rng > 0, rng, 1) * 2 - 1, 0.0), None

def sig_vwap(df, W=30):
    h, l, c, v = df["high"].values, df["low"].values, df["close"].values, df["volume"].values
    tp = (h + l + c) / 3.0
    vw = pd.Series(tp * v).rolling(W).sum().values / (pd.Series(v).rolling(W).sum().values + 1e-9)
    sd = np.sqrt(pd.Series(v * (tp - vw) ** 2).rolling(W).sum().values / (pd.Series(v).rolling(W).sum().values + 1e-9))
    return (c - vw) / (sd + c * 1e-4), None

def sig_cvd(df, K=20):
    v = df["volume"].values; tbr = df["taker_buy_ratio"].values; c = df["close"].values
    delta = (2 * tbr - 1) * v; cvd = np.cumsum(np.nan_to_num(delta))
    vol_k = pd.Series(v).rolling(K).sum().values + 1e-9
    cv = (cvd - np.roll(cvd, K)) / vol_k
    pr = c / np.roll(c, K) - 1.0
    div = np.where((pr > 0) != (cv > 0), pr - cv, (pr + cv) * 0.5)
    return div, None

def sig_taker(df):
    return (df["taker_buy_ratio"].values - 0.5) * 2.0, None

def sig_fvg(df, K=10):
    h, l, c = df["high"].values, df["low"].values, df["close"].values
    out = np.zeros(len(c))
    for t in range(3, len(c)):
        for i in range(t, max(2, t - K) - 1, -1):
            if l[i] > h[i - 2]: out[t] = (l[i] - h[i - 2]) / c[t]; break
            if h[i] < l[i - 2]: out[t] = -(l[i - 2] - h[i]) / c[t]; break
    return out, None

def sig_oi(df):
    oi = df["oi"].values; return oi / np.roll(oi, H) - 1.0, None

def sig_ls(df):
    ls = df["ls_ratio"].values; return ls / np.roll(ls, H) - 1.0, None

def sig_lsx(df):
    ls = df["ls_ratio"].values; lf = ls / (1.0 + ls); return -(lf - 0.5) * 4.0, None

def sig_oivol(df):
    v = df["volume"].values; oi = df["oi"].values; c = df["close"].values
    return (v / np.roll(v, H) - 1) - (oi / np.roll(oi, H) - 1) - 0.5 * (c / np.roll(c, H) - 1), None

def sig_regime(df):
    c = df["close"].values; oi = df["oi"].values; ls = df["ls_ratio"].values
    p = c / np.roll(c, H) - 1; oc = oi / np.roll(oi, H) - 1
    lf = ls / (1.0 + ls); lsx = -(lf - 0.5)
    s = np.where((p > 0) & (oc > 0), 1.5, np.where((p > 0) & (oc < 0), 1.0,
        np.where((p < 0) & (oc > 0), -1.5, np.where((p < 0) & (oc < 0), -0.5, 0.0))))
    return s + np.clip(lsx * 2, -0.5, 0.5), None

def sig_funding(df):
    return df["funding"].values, None    # +=long kalabalık (kontraryan beklenir)


def battery(name, dfs, fn, price_from="close", group=""):
    """dose-response + aşırı-uç seçici net + frekans, full & OOS (zaman 60/40)."""
    mags = []; nets = []; tss = []
    for c, df in dfs.items():
        if "close" in df:
            px = df["close"].values
        else:
            continue
        sig, _ = fn(df)
        fwd = np.roll(px, -H) / px - 1.0
        n = len(px)
        for t in range(H + 30, n - H):
            s = sig[t]
            if not np.isfinite(s) or abs(s) < 1e-9 or not np.isfinite(fwd[t]):
                continue
            d = 1 if s > 0 else -1
            mags.append(abs(s)); nets.append(d * fwd[t] - COST); tss.append(df.index[t])
    if len(mags) < 300:
        return (name, group, len(mags), float("nan"), float("nan"), float("nan"), float("nan"))
    mag = np.array(mags); net = np.array(nets)
    order = np.argsort(tss); mag, net = mag[order], net[order]
    sp = int(len(mag) * 0.6)
    def dose(m, r):
        qs = np.quantile(m, np.linspace(0, 1, 11)); cells = []
        for q in range(10):
            lo, hi = qs[q], qs[q + 1]
            mm = (m >= lo) & (m <= hi if q == 9 else m < hi)
            if mm.sum() > 5: cells.append(r[mm].mean())
        return np.corrcoef(np.arange(len(cells)), cells)[0, 1] if len(cells) > 3 else float("nan")
    dose_full = dose(mag, net); dose_oos = dose(mag[sp:], net[sp:])
    ext = mag >= np.quantile(mag, EXTQ)
    eo = ext.copy(); eo[:sp] = False
    ext_full = net[ext].mean() if ext.sum() else float("nan")
    ext_oos = net[eo].mean() if eo.sum() > 20 else float("nan")
    return (name, group, len(mag), dose_full, dose_oos, ext_full, ext_oos)


def main():
    A = load("mktdata/*_4h.csv", ["close"])
    for c, df in A.items():
        mp = "microdata/%s_micro.csv" % c
        if os.path.exists(mp):
            m = pd.read_csv(mp); m["ts"] = pd.to_datetime(m["ts"]); m = m.set_index("ts").sort_index()
            A[c] = df.join(m[["num_trades", "taker_buy_ratio"]], how="left").fillna(method="ffill").fillna(0.5)
    B0 = load("metricsdata/*_metrics_4h.csv", ["oi", "ls_ratio"])
    B = {}
    for c, df in B0.items():
        if c in A:
            j = df.index.intersection(A[c].index)
            B[c] = df.reindex(j).join(A[c][["close", "volume"]].reindex(j))
    C0 = load("funddata/*_funding.csv", ["funding"])
    C = {}
    for c, df in C0.items():
        if c in A:
            ca = A[c]["close"].reindex(df.index, method="ffill")
            C[c] = df.assign(close=ca.values)
    tests = [
        ("price", A, sig_price, "A-trend"), ("hl", A, sig_hl, "A-konum"),
        ("vwap", A, sig_vwap, "A-konum"), ("cvd", A, sig_cvd, "A-akış"),
        ("taker", A, sig_taker, "A-akış"), ("fvg", A, sig_fvg, "A-yapı"),
        ("oi", B, sig_oi, "B-türev"), ("ls", B, sig_ls, "B-türev"),
        ("lsx*", B, sig_lsx, "B-positioning"), ("oivol*", B, sig_oivol, "B-türev"),
        ("regime", B, sig_regime, "B-rejim"), ("funding", C, sig_funding, "C-carry"),
    ]
    rows = [battery(n, d, f, group=g) for n, d, f, g in tests]
    print("=" * 104)
    print("  TÜM SİNYALLER — uzun-tarih OOS falsifikasyonu (dir=sign(sig), 24h fwd, net maliyet)")
    print("  (* = daha önce test edildi · KABUL: |OOS-dose|>0.5 VE aşırı-uç OOS-net>0)")
    print("=" * 104)
    print("  %-9s %-14s %9s %11s %11s %12s %12s  %s" % (
        "sinyal", "grup", "n", "dose-FULL", "dose-OOS", "uç-net-FULL", "uç-net-OOS", "VERDICT"))
    rows.sort(key=lambda r: (r[6] if np.isfinite(r[6]) else -9), reverse=True)
    for nm, g, n, df_, do, ef, eo in rows:
        real = (np.isfinite(do) and abs(do) > 0.5 and np.isfinite(eo) and eo > 0)
        v = "✅ GERÇEK" if real else "❌ serap/zayıf"
        print("  %-9s %-14s %9d %+11.3f %+11.3f %+11.3f%% %+11.3f%%  %s" % (
            nm, g, n, df_, do, (ef or 0) * 100, (eo or 0) * 100, v))
    print("=" * 104)


if __name__ == "__main__":
    main()
