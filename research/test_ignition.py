#!/usr/bin/env python3
"""test_ignition.py — brainstorm'un açtığı cepheyi ölç:
(1) ön-kapı: MFE ~ lam_entry (yüksek-lam daha büyük hareket mi?) + lam-yükseliyor gate.
(2) ANA: ignition-onaylı PULLBACK girişi vs breakout girişi (avg_win↑ ve WR↑ olur mu, yoksa
    gap-and-go runner'ları mı kaçırır?). Falsifiye: avg_win düşüşü < WR artışı, OOS dahil."""
import numpy as np, pandas as pd
from signal_lab import atr, RT_COST_PRICE
from falsify import load_with_micro, breakout_pos, _features

SL_ATR, TP_R, LAM_MIN, LAM_EXEMPT = 2.0, 2.5, 1.0, 2.2


def walk(O, H, Lw, C, A, sig_i, fill_j, entry_px, d, mfe=True):
    """fill_j barında entry_px'ten gir, SL/TP'ye yürü. Döner (r_mult, mfe_R)."""
    n = len(C)
    risk = SL_ATR * (A[sig_i] if A[sig_i] > 0 else entry_px * 0.01)
    sl = entry_px - d * risk; tp = entry_px + d * TP_R * risk
    sld = risk / entry_px
    best = 0.0; exit_p = None; j = fill_j + 1
    while j < n:
        hi, lo = H[j], Lw[j]
        fav = (d * ((hi if d == 1 else lo) - entry_px)) / entry_px / sld
        best = max(best, fav)
        if d == 1:
            if lo <= sl: exit_p = sl; break
            if hi >= tp: exit_p = tp; break
        else:
            if hi >= sl: exit_p = sl; break
            if lo <= tp: exit_p = tp; break
        j += 1
    if exit_p is None: exit_p = C[n - 1]
    r = (d * (exit_p - entry_px) / entry_px) / sld - RT_COST_PRICE / sld
    return r, best


def collect(dfs, PB=0.5, K=3):
    rows = []
    for c, df in dfs.items():
        O = df["open"].to_numpy(float); H = df["high"].to_numpy(float)
        Lw = df["low"].to_numpy(float); C = df["close"].to_numpy(float)
        A = atr(df, 14); idx = df.index
        f = _features(df); lam = f["lam"]; vr = f["vr"]
        pos = breakout_pos(df, 20)
        for i in np.where(pos != 0)[0]:
            if i + 1 >= len(C) or lam[i] <= LAM_MIN: continue
            fresh = (vr[i] < 1.0) if np.isfinite(vr[i]) else False
            if not (fresh or lam[i] >= LAM_EXEMPT): continue
            d = int(pos[i])
            # BREAKOUT girişi: i+1 açılışı
            ebk = O[i + 1]
            r_bk, mfe_bk = walk(O, H, Lw, C, A, i, i, ebk, d)
            # PULLBACK girişi: i+1..i+K arasında ebk - d*PB*ATR'ye değerse orada gir
            pb_px = ebk - d * PB * A[i]
            fill_j = None
            for j in range(i + 1, min(i + 1 + K, len(C))):
                if (d == 1 and Lw[j] <= pb_px) or (d == -1 and H[j] >= pb_px):
                    fill_j = j; break
            if fill_j is not None:
                r_pb, _ = walk(O, H, Lw, C, A, i, fill_j, pb_px, d)
            else:
                r_pb = None   # dolmadı (gap-and-go — kaçırıldı)
            rows.append(dict(coin=c, exit_ts=str(idx[min(i + 1, len(idx) - 1)]),
                             lam=float(lam[i]), lam_prev=float(lam[i - 1]),
                             r_bk=float(r_bk), mfe=float(mfe_bk),
                             r_pb=(float(r_pb) if r_pb is not None else np.nan),
                             filled=fill_j is not None))
    return pd.DataFrame(rows)


def stats(r):
    r = np.asarray(r, float); r = r[np.isfinite(r)]
    if len(r) == 0: return (0, 0, 0, 0)
    w = r[r > 0]
    return (len(r), r.mean(), 100 * (r > 0).mean(), w.mean() if len(w) else 0)


def main():
    print("Veri (43 coin)..."); dfs = load_with_micro()
    bk = collect(dfs)
    bk = bk.sort_values("exit_ts").reset_index(drop=True)
    split = int(len(bk) * 0.6); oos = bk.iloc[split:]

    print("=" * 92)
    print("  ÖN-KAPI 1: MFE ~ lam_entry  (yüksek-lam daha büyük hareket getiriyor mu?)")
    print("=" * 92)
    corr = np.corrcoef(bk["lam"], bk["mfe"])[0, 1]
    qs = bk["lam"].quantile([.2, .4, .6, .8]).to_numpy()
    print("  lam-decile → ort. MFE(R):")
    edges = [bk["lam"].min()] + list(qs) + [bk["lam"].max()]
    for a, b in zip(edges[:-1], edges[1:]):
        m = (bk["lam"] >= a) & (bk["lam"] <= b)
        print("    lam[%.2f,%.2f]  MFE=%.3fR  (n=%d)" % (a, b, bk[m]["mfe"].mean(), m.sum()))
    print("  corr(lam, MFE) = %+.3f  %s" % (corr, "→ yüksek-lam DAHA BÜYÜK hareket (conviction-target mantıklı)" if corr > 0.1 else "→ zayıf; conviction-target VOID"))

    print("\n" + "=" * 92)
    print("  ÖN-KAPI 2: lam-YÜKSELİYOR (eğim) gate — sadece yüksek değil, artan lam daha mı iyi?")
    print("=" * 92)
    rising = bk["lam"] > bk["lam_prev"]
    for name, sub in [("tüm breakout", bk), ("lam YÜKSELİYOR", bk[rising]), ("lam düşüyor", bk[~rising])]:
        n, avg, wr, aw = stats(sub["r_bk"]); no, ao, wo, awo = stats(oos[oos.index.isin(sub.index)]["r_bk"])
        print("  %-16s N=%-5d avgR=%+.3f WR=%.1f%% avgWin=%.2f | OOS avgR=%+.3f" % (name, n, avg, wr, aw, ao))

    print("\n" + "=" * 92)
    print("  ANA DENEY: PULLBACK girişi vs BREAKOUT girişi (ignition onaylı, lam>1)")
    print("=" * 92)
    nb, ab, wb, awb = stats(bk["r_bk"])
    filled = bk[bk["filled"]]
    npb, apb, wpb, awpb = stats(filled["r_pb"])
    skipped = bk[~bk["filled"]]            # pullback'in kaçırdığı (gap-and-go)
    ns, as_, ws, aws = stats(skipped["r_bk"])
    fill_rate = 100 * len(filled) / len(bk)
    print("  BREAKOUT (hepsi)     N=%-5d avgR=%+.3f WR=%.1f%% avgWin=%.2f" % (nb, ab, wb, awb))
    print("  PULLBACK (dolanlar)  N=%-5d avgR=%+.3f WR=%.1f%% avgWin=%.2f  (fill-rate %.0f%%)" % (npb, apb, wpb, awpb, fill_rate))
    print("  PULLBACK'in KAÇIRDIĞI (gap-and-go) N=%-5d avgR=%+.3f  ← bunlar runner mı?" % (ns, as_))
    # OOS
    oos_f = oos[oos["filled"]]
    _, abo, _, _ = stats(oos["r_bk"]); _, apo, _, _ = stats(oos_f["r_pb"])
    print("  [OOS] breakout avgR=%+.3f → pullback avgR=%+.3f" % (abo, apo))
    print("\n  FALSİFİKASYON (avg_win düşüşü < WR artışı VE net avgR↑?):")
    print("    avgWin: %.2f→%.2f (Δ%+.2f) · WR: %.1f→%.1f (Δ%+.1f) · avgR: %+.3f→%+.3f (Δ%+.3f)" % (
        awb, awpb, awpb - awb, wb, wpb, wpb - wb, ab, apb, apb - ab))
    verdict = "✅ PULLBACK KAZANDI" if apb > ab and apo > abo else ("kısmi" if apb > ab else "❌ pullback breakout'u yenemedi (gap-and-go kaçırılıyor)")
    print("    →", verdict)
    print("=" * 92)


if __name__ == "__main__":
    main()
