#!/usr/bin/env python3
"""falsify_phase.py — ADIM ②: Termodinamik Faz Kapısı (PE+VR) MACRO-VETO olarak.
Kullanıcı tezi: lam zaten ateşi yakalıyor → PE/VR rutin filtre DEĞİL, nadir acil-fren.
Test: (1) lam×faz etkileşimi, (2) yüksek-lam gaz-fazında muaf mı?, (3) macro-veto artımsal değeri."""
import numpy as np
import pandas as pd
from falsify import load_with_micro, collect_breakouts, null_pctile

RNG = np.random.default_rng(7)


def avgr_grid(bk, row_q, col_cat, col_name):
    """lam-tercile (satır) × faz-kategori (sütun) avgR + N ızgarası."""
    print(f"\n  avgR ızgarası: lam-tercile × {col_name}  (hücre: avgR / N)")
    cats = ["gaz", "nötr", "katı"]
    lab = "lam\\faz"
    print(f"    {lab:<10}" + "".join(f"{c:>16}" for c in cats))
    for rl, (rlo, rhi) in zip(["düşük", "orta", "yüksek"], row_q):
        rm = (bk["lam"] >= rlo) & (bk["lam"] < rhi)
        cells = []
        for c in cats:
            m = rm & (col_cat == c)
            cells.append(f"{bk[m]['r'].mean():+.3f}/{m.sum():<5}" if m.sum() > 15 else f"{'·':>11}")
        print(f"    {rl:<10}" + "".join(f"{x:>16}" for x in cells))


def main():
    print("=" * 96)
    print("  ADIM ② — TERMODİNAMİK FAZ KAPISI (PE+VR) MACRO-VETO testi")
    print("  Tez: lam ateşi yakalar; PE/VR yalnız 'tam gaz fazı'nda acil-fren, yüksek-lam muaf")
    print("=" * 96)
    dfs = load_with_micro()
    bk = collect_breakouts(dfs).dropna(subset=["pe", "vr"]).reset_index(drop=True)
    bk["yr"] = bk["exit_ts"].str[:4]
    N = len(bk)
    print(f"\n  N={N} breakout (pe/vr geçerli)  ·  PE: 1=gaz/düzensiz 0=katı  ·  VR>1 trend, <1 mean-rev")

    # faz tanımı: PE tercile (gaz=yüksek PE) ; VR ile 'saf Brownian' rafine
    pe_t = bk["pe"].quantile([1/3, 2/3]).to_numpy()
    phase = np.where(bk["pe"] >= pe_t[1], "gaz", np.where(bk["pe"] <= pe_t[0], "katı", "nötr"))
    phase = pd.Series(phase, index=bk.index)
    lam_t = bk["lam"].quantile([1/3, 2/3]).to_numpy()
    row_q = [(-1e9, lam_t[0]), (lam_t[0], lam_t[1]), (lam_t[1], 1e9)]

    # ── (1) tek-değişkenli: PE ve VR avgR profili ──
    print("\n  TEK-DEĞİŞKENLİ avgR profili (faz tek başına ayırıyor mu?):")
    for name, key, thr in [("PE-gaz (yüksek)", "pe", pe_t[1]), ("PE-katı (düşük)", "pe", pe_t[0])]:
        m = bk[key] >= thr if "gaz" in name else bk[key] <= thr
        print(f"    {name:<18} N={m.sum():<6} avgR={bk[m]['r'].mean():+.4f}  WR={100*(bk[m]['r']>0).mean():.1f}%")
    print(f"    {'VR>1 (trend)':<18} N={(bk.vr>1).sum():<6} avgR={bk[bk.vr>1]['r'].mean():+.4f}")
    print(f"    {'VR<1 (mean-rev)':<18} N={(bk.vr<1).sum():<6} avgR={bk[bk.vr<1]['r'].mean():+.4f}")

    # ── (2) 2D ETKİLEŞİM: lam × faz ──
    avgr_grid(bk, row_q, phase, "PE-faz")

    # ── (3) KRİTİK: yüksek-lam, gaz-fazında MUAF mı? ──
    print("\n  İSTİSNA TESTİ — gaz fazındaki breakout'lar, lam'a göre:")
    gas = phase == "gaz"
    for rl, (rlo, rhi) in zip(["düşük-lam", "orta-lam", "yüksek-lam"], row_q):
        m = gas & (bk["lam"] >= rlo) & (bk["lam"] < rhi)
        if m.sum() > 15:
            print(f"    gaz & {rl:<11} N={m.sum():<5} avgR={bk[m]['r'].mean():+.4f}  "
                  f"WR={100*(bk[m]['r']>0).mean():.1f}%")
    print("    → yüksek-lam gazda hâlâ + ise: MUAF tut (Type-2 hatasından kaçın)")

    # ── (4) MACRO-VETO artımsal değeri (lam-conviction baseline ÜSTÜNE) ──
    print("\n  MACRO-VETO ARTIMSAL DEĞER (baseline = lam>1 conviction edge):")
    base = bk[bk["lam"] > 1.0]
    base_r = bk["r"].to_numpy()    # null havuzu = tüm breakout'lar
    # 'tam gaz' = yüksek PE VE Brownian-VR (|vr-1|<0.25) → saf rastgelelik
    pure_gas = (bk["pe"] >= pe_t[1]) & (bk["vr"].between(0.75, 1.25))
    lam_hi = bk["lam"] >= lam_t[1]
    # veto: tam-gaz VE yüksek-lam DEĞİL  (yüksek-lam muaf)
    veto = pure_gas & (~lam_hi)
    kept = bk[(bk["lam"] > 1.0) & (~veto)]
    dropped = bk[(bk["lam"] > 1.0) & veto]
    print(f"    baseline lam>1     : N={len(base):<6} avgR={base['r'].mean():+.4f}  WR={100*(base['r']>0).mean():.1f}%")
    print(f"    + macro-veto (kept): N={len(kept):<6} avgR={kept['r'].mean():+.4f}  WR={100*(kept['r']>0).mean():.1f}%  "
          f"(keep={100*len(kept)/len(base):.0f}% → nadir fren)")
    if len(dropped):
        pct, _ = null_pctile(base_r, len(dropped), dropped["r"].mean())
        print(f"    VETO EDİLEN işlemler: N={len(dropped):<6} avgR={dropped['r'].mean():+.4f}  "
              f"(null>{pct:.0f}% → düşükse gerçekten kötüleri atıyoruz ✅)")
    # OOS 2025-26 artımsal
    for tag, sl in [("FULL", bk.index), ("2025-26 OOS", bk[bk.yr.isin(["2025","2026"])].index)]:
        b = bk.loc[sl]; bb = b[b["lam"] > 1.0]; kk = b[(b["lam"] > 1.0) & (~veto.loc[sl])]
        if len(bb) and len(kk):
            print(f"    [{tag:<11}] lam>1 avgR={bb['r'].mean():+.4f} → +veto avgR={kk['r'].mean():+.4f}  "
                  f"(Δ={kk['r'].mean()-bb['r'].mean():+.4f})")

    # ── (5) VR keşfi: lam × VR ızgarası + VETO YARIŞMASI ──
    print("\n  lam × VR ızgarası (VR>1=geç/uzamış, VR<1=sıkışmadan taze ateşleme):")
    vr_cat = pd.Series(np.where(bk["vr"] > 1, "VR>1", "VR<1"), index=bk.index)
    lab = "lam\\VR"
    print(f"    {lab:<10}{'VR>1 (geç)':>16}{'VR<1 (taze)':>16}")
    for rl, (rlo, rhi) in zip(["düşük", "orta", "yüksek"], row_q):
        rm = (bk["lam"] >= rlo) & (bk["lam"] < rhi)
        cells = [f"{bk[rm&(vr_cat==c)]['r'].mean():+.3f}/{(rm&(vr_cat==c)).sum():<5}" for c in ["VR>1","VR<1"]]
        print(f"    {rl:<10}" + "".join(f"{x:>16}" for x in cells))

    def veto_eval(name, veto_mask):
        oos_idx = bk[bk.yr.isin(["2025","2026"])].index
        bb = bk[bk["lam"] > 1.0]; kk = bk[(bk["lam"] > 1.0) & (~veto_mask)]
        dd = bk[(bk["lam"] > 1.0) & veto_mask]
        ob = bk.loc[oos_idx]; obb = ob[ob["lam"]>1.0]; okk = ob[(ob["lam"]>1.0)&(~veto_mask.loc[oos_idx])]
        dpct = null_pctile(bk["r"].to_numpy(), len(dd), dd["r"].mean())[0] if len(dd)>20 else float("nan")
        print(f"    {name:<22} keep={100*len(kk)/len(bb):>3.0f}%  keptR={kk['r'].mean():+.4f} "
              f"(Δ{kk['r'].mean()-bb['r'].mean():+.4f})  dropR={dd['r'].mean():+.4f}(null>{dpct:.0f}%)  "
              f"OOSΔ={okk['r'].mean()-obb['r'].mean():+.4f}")

    print("\n  VETO YARIŞMASI (hepsi yüksek-lam MUAF; baseline=lam>1):")
    print(f"    {'baseline lam>1':<22} keep=100%  keptR={base['r'].mean():+.4f}  (referans)")
    veto_eval("PE-gaz veto",   pure_gas & (~lam_hi))
    veto_eval("VR>1 veto (geç)", (bk["vr"] > 1) & (~lam_hi))
    veto_eval("VR>1 & PE-gaz",  (bk["vr"] > 1) & (bk["pe"]>=pe_t[1]) & (~lam_hi))
    veto_eval("VR>1 VEYA PE-gaz", ((bk["vr"] > 1) | (bk["pe"]>=pe_t[1])) & (~lam_hi))
    print("=" * 96)


if __name__ == "__main__":
    main()
