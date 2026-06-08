#!/usr/bin/env python3
"""
falsify.py — FALSIFICATION-FIRST EDGE HARNESS (fizik-tabanlı giriş/rejim/çıkış avı)
═══════════════════════════════════════════════════════════════════════════════
Felsefe (denetimden ders): mekanizmaları test setine bakıp SEÇMEK = seçim-yanlılığı
bugu. Burada her mekanizma ÖN-KAYITLI bir hipotez; baseline'a VE eşleşmiş RASTGELE-
REDDETME null'una karşı ölçülür. Edge = bağımsız olarak OOS'ta null'u yenen ne kalırsa.

Hepsi CAUSAL (signal_lab sözleşmesi: pos[i] yalnız ≤i kullanır, giriş i+1 açılışında).

Mekanizmalar bu turda (GİRİŞ TEYİDİ):
  base        : Donchian-20 ham breakout (referans)
  flowsign    : SIFIR-KNOB veto — kırılım yönünde taker-aggressor akışı şart (bull-trap eler)
  vpin        : VPIN-lite (tek-yön akış yoğunluğu) z>0.5 (Easley-LdP-O'Hara)
  hawkes      : öz-uyarımlı yoğunluk branching>1 (akış-şiddeti kümelenir: ölçülen autocorr 0.105)
  coil        : sıkışmış tabandan verimli impuls (Kaufman efficiency × düşük-ATR taban)

Her biri için: pool/train/test avgR, PF, WR, freq, per-coin+, ve eşleşmiş random-null.
BAŞARI KRİTERİ (ön-kayıt): filtered TEST avgR > base TEST avgR  VE  > random-null TEST avgR.
"""
import sys, os, json
import numpy as np
import pandas as pd
from signal_lab import (simulate, metrics, atr, donchian, sma, ema,
                        BARS_PER_YEAR, RT_COST_PRICE, load_all)

SEED = 7
RNG = np.random.default_rng(SEED)
N_NULL = 500          # null dağılımı için rastgele çekiliş sayısı
SL_ATR, TP_R = 2.0, 2.5


# ── veri: mktdata + microdata hizalı yükle ──────────────────────────────────
def load_with_micro(data="mktdata", micro="microdata", tf="4h"):
    """mktdata df'lerine taker_buy_ratio + num_trades kolonlarını hizalı ekle."""
    dfs = load_all(data, tf)
    out = {}
    for c, df in dfs.items():
        mpath = f"{micro}/{c}_micro.csv"
        if os.path.exists(mpath):
            m = pd.read_csv(mpath); m["ts"] = pd.to_datetime(m["ts"])
            m = m.set_index("ts").sort_index()
            df = df.join(m[["num_trades", "taker_buy_ratio"]], how="left")
            df["taker_buy_ratio"] = df["taker_buy_ratio"].ffill().fillna(0.5)
            df["num_trades"] = df["num_trades"].ffill().fillna(0.0)
        else:
            df["taker_buy_ratio"] = 0.5; df["num_trades"] = 0.0
        out[c] = df
    return out


# ── baseline breakout (causal, signal_lab konvansiyonu) ─────────────────────
def breakout_pos(df, n=20):
    """Donchian-n ham breakout: c[i] > önceki-bar üst bandı → +1, < alt → -1."""
    c = df["close"].to_numpy(float)
    h, l = donchian(df, n)
    pos = np.zeros(len(df))
    for i in range(max(n + 2, 200), len(df)):
        if c[i] > h[i - 1]:
            pos[i] = 1
        elif c[i] < l[i - 1]:
            pos[i] = -1
    return pos


# ── teyit terimleri: per-bar causal feature'lar ─────────────────────────────
def _features(df, L=60, beta=0.3):
    c = df["close"].to_numpy(float)
    tbr = df["taker_buy_ratio"].to_numpy(float)
    nt = df["num_trades"].to_numpy(float)
    a = atr(df, 14)
    signed = 2 * tbr - 1.0                       # -1..+1 aggressor yön
    imb = np.abs(signed)                          # tek-yönlülük şiddeti
    # VPIN-lite: 12-bar ortalama imbalance, sonra 60-bar z
    vpin = pd.Series(imb).rolling(12).mean().to_numpy()
    vp_mean = pd.Series(vpin).rolling(L).mean().to_numpy()
    vp_sd = pd.Series(vpin).rolling(L).std().to_numpy()
    vpin_z = (vpin - vp_mean) / (vp_sd + 1e-12)
    # Hawkes-lite branching: m=nt*imb, baseline=SMA60, lam ewma recursion
    m = nt * imb
    mu = pd.Series(m).rolling(L).mean().to_numpy()
    ratio = np.divide(m, mu, out=np.ones_like(m), where=(mu > 0))
    lam = np.ones(len(m))
    for i in range(1, len(m)):
        prev = lam[i - 1] if np.isfinite(lam[i - 1]) else 1.0
        lam[i] = (1 - beta) * prev + beta * (ratio[i] if np.isfinite(ratio[i]) else 1.0)
    # coil + efficiency: Kaufman ER (N=6) ve düşük-ATR taban percentile
    N = 6
    er = np.zeros(len(c))
    for i in range(N, len(c)):
        net = abs(c[i] - c[i - N])
        path = np.sum(np.abs(np.diff(c[i - N:i + 1]))) + 1e-12
        er[i] = net / path
    atrp = a / (c + 1e-12)
    coil = 1.0 - pd.Series(atrp).rolling(L).apply(
        lambda x: (x[:-1] <= x[-1]).mean(), raw=True).to_numpy()   # düşük-ATP → coil yüksek
    # ── TERMODİNAMİK: permütasyon entropisi (PE, D=3) + varyans oranı (VR) — causal ──
    pe = _perm_entropy(c, win=48)            # 0..1 (1=tam düzensiz/gaz, 0=düzenli/katı)
    vr = _variance_ratio(c, win=60, q=4)     # >1 süper-difüzyon/trend, ≈1 Brownian, <1 mean-rev
    return dict(signed=signed, vpin_z=vpin_z, lam=lam, er=er, coil=coil, pe=pe, vr=vr)


def _perm_entropy(c, win=48):
    """Bandt-Pompe permütasyon entropisi, D=3 (6 örüntü). Causal: pencere i'de biter."""
    c = np.asarray(c, float)
    patt = np.zeros(len(c), int)
    for i in range(2, len(c)):
        # 3 değerin sıralama-örüntüsü (0..5 arası tekil kod)
        r = np.argsort(np.argsort(c[i - 2:i + 1]))
        patt[i] = r[0] * 9 + r[1] * 3 + r[2]
    oh = pd.get_dummies(pd.Series(patt))
    roll = oh.rolling(win).sum()
    tot = roll.sum(axis=1)
    probs = roll.div(tot.where(tot > 0, 1), axis=0)
    ent = -(probs * np.log(probs + 1e-12)).sum(axis=1) / np.log(6)
    return ent.to_numpy()


def _variance_ratio(c, win=60, q=4):
    """Lo-MacKinlay VR(q): var(q-bar)/[q·var(1-bar)]. Causal rolling. >1 trend, <1 revert."""
    r = pd.Series(np.diff(np.log(np.asarray(c, float)), prepend=np.log(c[0])))
    var1 = r.rolling(win).var()
    Rq = r.rolling(q).sum()
    varq = Rq.rolling(win).var()
    vr = varq / (q * var1 + 1e-12)
    return vr.to_numpy()


# ── BAĞIMSIZ breakout-olayı sonucu (yol-bağımlılığı yok; saf giriş-kalitesi) ──
def _trade_outcome(O, H, L, C, A, i, d, sl_atr=SL_ATR, tp_r=TP_R):
    """i barında tespit, i+1 açılışında gir, SL/TP'ye kadar yürü. R-cinsinden sonuç (maliyet dahil)."""
    n = len(C)
    if i + 1 >= n:
        return None
    entry = O[i + 1]
    a = A[i] if A[i] > 0 else entry * 0.01
    risk = sl_atr * a
    if risk <= 0:
        return None
    sl = entry - d * risk; tp = entry + d * tp_r * risk
    sl_dist = risk / entry
    exit_p = None; j = i + 1
    while j < n:
        if d == 1:
            if L[j] <= sl: exit_p = sl; break
            if H[j] >= tp: exit_p = tp; break
        else:
            if H[j] >= sl: exit_p = sl; break
            if L[j] <= tp: exit_p = tp; break
        j += 1
    if exit_p is None: exit_p = C[n - 1]; j = n - 1
    r_price = d * (exit_p - entry) / entry
    r_mult = r_price / sl_dist - RT_COST_PRICE / sl_dist
    return r_mult, j


def collect_breakouts(dfs, n=20, L=60, beta=0.3):
    """Tüm coinlerde her breakout için: bağımsız r_mult + teyit feature'ları + exit_ts + coin."""
    rows = []
    for c, df in dfs.items():
        O = df["open"].to_numpy(float); H = df["high"].to_numpy(float)
        Lr = df["low"].to_numpy(float); Cc = df["close"].to_numpy(float)
        A = atr(df, 14); idx = df.index
        pos = breakout_pos(df, n)
        f = _features(df, L=L, beta=beta)
        bi = np.where(pos != 0)[0]
        for i in bi:
            d = int(pos[i])
            res = _trade_outcome(O, H, Lr, Cc, A, i, d)
            if res is None:
                continue
            r_mult, j = res
            rows.append(dict(coin=c, i=int(i), d=d, r=float(r_mult),
                             exit_ts=str(idx[min(j, len(idx) - 1)]),
                             signed=float(f["signed"][i]),
                             vpin_z=float(f["vpin_z"][i]) if np.isfinite(f["vpin_z"][i]) else 0.0,
                             lam=float(f["lam"][i]),
                             er=float(f["er"][i]),
                             coil=float(f["coil"][i]) if np.isfinite(f["coil"][i]) else 0.5,
                             pe=float(f["pe"][i]) if np.isfinite(f["pe"][i]) else np.nan,
                             vr=float(f["vr"][i]) if np.isfinite(f["vr"][i]) else np.nan))
    return pd.DataFrame(rows)


def mech_mask(bk, kind):
    """Mekanizmanın breakout'ları tutma maskesi (causal feature'lara dayalı)."""
    d, sgn = bk["d"].to_numpy(), bk["signed"].to_numpy()
    flow_ok = np.where(d == 1, sgn > 0, sgn < 0)
    if kind == "flowsign":
        return flow_ok
    if kind == "vpin":
        return flow_ok & (bk["vpin_z"].to_numpy() > 0.5)
    if kind == "hawkes":
        return flow_ok & (bk["lam"].to_numpy() > 1.0)
    if kind == "coil":
        return (bk["er"].to_numpy() > 0.30) & (bk["coil"].to_numpy() > 0.5)
    raise ValueError(kind)


def null_pctile(r_all, k, observed_mean):
    """k-boyutlu rastgele alt-kümelerin ortalama dağılımında observed_mean'in yüzdelik konumu."""
    if k <= 0 or k >= len(r_all):
        return float("nan"), float("nan")
    means = np.empty(N_NULL)
    n = len(r_all)
    for t in range(N_NULL):
        means[t] = r_all[RNG.choice(n, size=k, replace=False)].mean()
    pct = float((means < observed_mean).mean() * 100)   # observed bu kadar null'u yeniyor
    return pct, float(means.mean())


def analyze(bk, label):
    """Pool + OOS(60/40, exit_ts) + per-coin + null-dağılımı p-değeri."""
    bk = bk.sort_values("exit_ts").reset_index(drop=True)
    r_all = bk["r"].to_numpy()
    split = int(len(bk) * 0.6)
    test = bk.iloc[split:]
    pc = bk.groupby("coin")["r"].mean()
    return dict(label=label, n=len(bk),
                pool_r=float(r_all.mean()),
                wr=float((r_all > 0).mean() * 100),
                pf=float(r_all[r_all > 0].sum() / abs(r_all[r_all <= 0].sum()))
                   if (r_all <= 0).any() else float("inf"),
                test_r=float(test["r"].mean()) if len(test) else 0.0,
                pos_coins=int((pc > 0).sum()), tot=int(pc.size),
                r_all=r_all)


def main():
    print("=" * 100)
    print("  FALSIFY v2 — GİRİŞ TEYİDİ (bağımsız breakout + NULL-DAĞILIMI p-değeri)")
    print(f"  N_NULL={N_NULL} rastgele çekiliş · SL={SL_ATR}×ATR TP={TP_R}R · maliyet dahil · causal")
    print("=" * 100)
    dfs = load_with_micro()
    bk = collect_breakouts(dfs)
    base = analyze(bk, "base")
    base_r = base["r_all"]
    print(f"\nBASELINE  N={base['n']}  WR={base['wr']:.1f}%  poolR={base['pool_r']:+.4f}  "
          f"PF={base['pf']:.3f}  testR={base['test_r']:+.4f}  pc={base['pos_coins']}/{base['tot']}")

    print("\nMEKANİZMA            keep   poolR    PF    WR%   testR   pc     POOL-null%  →  verdict")
    print("-" * 100)
    verdict = []
    for kind in ["flowsign", "vpin", "hawkes", "coil"]:
        mask = mech_mask(bk, kind)
        sub = bk[mask]
        a = analyze(sub, kind)
        k = a["n"]
        # null: base breakout havuzundan k-boyutlu rastgele alt-kümeler
        pool_pct, null_mean = null_pctile(base_r, k, a["pool_r"])
        # test setinde de null konumu
        bk_s = bk.sort_values("exit_ts").reset_index(drop=True)
        split = int(len(bk_s) * 0.6)
        test_base_r = bk_s.iloc[split:]["r"].to_numpy()
        sub_s = sub.sort_values("exit_ts").reset_index(drop=True)
        tsplit = int(len(sub_s) * 0.6)
        k_test = len(sub_s) - tsplit
        test_pct, _ = null_pctile(test_base_r, k_test, a["test_r"])
        # ÖN-KAYIT: pool null %95 üstü VE test null %50 üstü (rastgele incelmeden iyi)
        ok = pool_pct >= 95.0 and test_pct >= 50.0
        keep = 100 * k / base["n"]
        print(f"  {kind:<11} {keep:>5.0f}% {a['pool_r']:+.4f} {a['pf']:>5.2f} {a['wr']:>5.1f} "
              f"{a['test_r']:+.4f} {a['pos_coins']:>2}/{a['tot']:<2}  "
              f"pool>{pool_pct:>4.0f}% test>{test_pct:>3.0f}%  "
              f"{'✅ GERÇEK SİNYAL' if ok else '❌ rastgeleden iyi değil'}")
        verdict.append((kind, ok, pool_pct, test_pct))

    print("-" * 100)
    print("  ÖN-KAYITLI KRİTER: pool avgR null-dağılımının ≥%95'ini yener VE test ≥%50 (rastgele incelmeden iyi)")

    # ── KARAR VERİCİ TANI: yıl-yıl seçim-avantajı (overfit mi rejim-çürümesi mi?) ──
    print("\n" + "=" * 100)
    print("  TANI — YIL-YIL seçim avantajı (base avgR vs mekanizma avgR, + yıl-içi null%)")
    print("  H1=overfit (yıllar arası rastgele) · H2=rejim-çürümesi (erken+ , geç−)")
    print("=" * 100)
    bk = bk.copy()
    bk["yr"] = bk["exit_ts"].str[:4]
    years = sorted(bk["yr"].unique())
    hdr = "  mekanizma   " + "".join(f"{y:>14}" for y in years)
    print(hdr)
    print(f"  {'base avgR':<11}" + "".join(
        f"{bk[bk.yr==y]['r'].mean():>+14.4f}" for y in years))
    print("  " + "-" * (len(hdr) - 2))
    for kind in ["flowsign", "vpin", "hawkes"]:
        mask = mech_mask(bk, kind)
        cells = []
        for y in years:
            yb = bk[bk.yr == y]; ym = bk[mask & (bk.yr == y)]
            if len(ym) < 20 or len(yb) < 30:
                cells.append(f"{'·':>14}"); continue
            pct, _ = null_pctile(yb["r"].to_numpy(), len(ym), ym["r"].mean())
            cells.append(f"{ym['r'].mean():>+9.4f}({pct:>3.0f})")
        print(f"  {kind:<11}" + "".join(cells))
    print("  (parantez = o yıl içinde rastgele-incelmenin yüzde-kaçını yendi; >95 = o yıl gerçek)")

    # ── ALTIN-STANDART: lam dose-response (monoton mu?) + attribution ──
    print("\n" + "=" * 100)
    print("  DOSE-RESPONSE — breakout'ları lam (Hawkes yoğunluğu) decile'ına böl → avgR monoton mu?")
    print("=" * 100)
    lam = bk["lam"].to_numpy(); r = bk["r"].to_numpy()
    qs = np.quantile(lam, np.linspace(0, 1, 11))
    print(f"  {'decile':<8}{'lam-aralık':<22}{'N':>7}{'avgR':>10}{'WR%':>8}")
    monoton = []
    for q in range(10):
        lo, hi = qs[q], qs[q + 1]
        m = (lam >= lo) & (lam <= hi if q == 9 else lam < hi)
        if m.sum() == 0: continue
        avgr = r[m].mean(); monoton.append(avgr)
        print(f"  D{q+1:<7}{f'[{lo:.2f},{hi:.2f})':<22}{m.sum():>7}{avgr:>+10.4f}{100*(r[m]>0).mean():>8.1f}")
    spearman = np.corrcoef(np.arange(len(monoton)), monoton)[0, 1]
    print(f"\n  decile-avgR trend (lin. korelasyon) = {spearman:+.3f}  "
          f"{'✅ MONOTON ARTAN → gerçek nedensel sinyal' if spearman > 0.5 else 'zayıf/monoton değil'}")

    print("\n  ATTRIBUTION — edge lam'dan mı flowsign'dan mı?")
    for name, m in [("lam>1 (saf)", bk["lam"].to_numpy() > 1.0),
                    ("flowsign (saf)", mech_mask(bk, "flowsign")),
                    ("lam>1 + flowsign", mech_mask(bk, "hawkes"))]:
        sub = bk[m]
        pct, _ = null_pctile(bk["r"].to_numpy(), len(sub), sub["r"].mean())
        # geç-dönem (2025-26) ayrı
        late = sub[sub["yr"].isin(["2025", "2026"])]
        lbase = bk[bk["yr"].isin(["2025", "2026"])]
        lpct, _ = null_pctile(lbase["r"].to_numpy(), len(late), late["r"].mean()) if len(late) > 20 else (float("nan"), 0)
        print(f"    {name:<18} keep={100*len(sub)/len(bk):>4.0f}%  poolR={sub['r'].mean():+.4f} "
              f"(null>{pct:>4.0f}%)  |  2025-26: avgR={late['r'].mean():+.4f} (null>{lpct:>4.0f}%)")
    # ── KURŞUN-GEÇİRMEZ: dose-response 2025-26 OOS diliminde de tutuyor mu? ──
    print("\n  OOS KİLİDİ — lam dose-response yalnız 2025-26 (ham edge negatif olan dönem):")
    oos = bk[bk["yr"].isin(["2025", "2026"])]
    lam_o, r_o = oos["lam"].to_numpy(), oos["r"].to_numpy()
    qo = np.quantile(lam_o, np.linspace(0, 1, 6))   # 5 dilim (örneklem küçük)
    cells = []
    for q in range(5):
        lo, hi = qo[q], qo[q + 1]
        m = (lam_o >= lo) & (lam_o <= hi if q == 4 else lam_o < hi)
        cells.append(r_o[m].mean() if m.sum() else float("nan"))
    sp = np.corrcoef(np.arange(5), cells)[0, 1]
    print("    Q1→Q5 avgR: " + "  ".join(f"{x:+.3f}" for x in cells) +
          f"   trend={sp:+.3f}  {'✅ OOS MONOTON — kurşun-geçirmez' if sp > 0.5 else 'OOS zayıf'}")
    print("=" * 100)
    return verdict


if __name__ == "__main__":
    main()
