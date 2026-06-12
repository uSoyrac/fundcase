#!/usr/bin/env python3
"""breadth500_test.py — GENİŞLİK kaldıracı (43→~500 evren): fona-girişi risk ARTIRMADAN hızlandır.
3 adım: (1) YENİ kohort (mktdata_breadth) lam dose-response doğrulaması (genelleme — 22-coin
genişlemesinde +0.890 çıkmıştı), (2) sinyal-akışı: eski-43 vs birleşik (lam-gate giriş/10g),
(3) Step1 hız-MC: AYNI config (gate1.5 %0.30 cushion-protect) eski vs birleşik —
medyan-gün & blow & ≤10g%. Hipotez: ~3-4× akış → medyan-gün ~1/3, blow AYNI (risk değişmedi)."""
import numpy as np, pandas as pd
from falsify import load_with_micro, collect_breakouts
from prop_sim import build_entries
from monte_carlo import build_timeline
from sprint_z_mc import run, mc

N = 300
MILD = (0.00007, 0.0); HARSH = (0.00015, 0.00010)


def dose(bk, label):
    bk = bk.sort_values("exit_ts").reset_index(drop=True)
    sp = int(len(bk) * 0.6); oos = bk.iloc[sp:]
    lam, r = bk["lam"].to_numpy(), bk["r"].to_numpy()
    qs = np.quantile(lam, np.linspace(0, 1, 11)); cells = []
    for q in range(10):
        lo, hi = qs[q], qs[q + 1]
        m = (lam >= lo) & (lam <= hi if q == 9 else lam < hi)
        if m.sum(): cells.append(r[m].mean())
    corr = np.corrcoef(np.arange(len(cells)), cells)[0, 1]
    g = bk[bk["lam"] >= 2.0]; go = oos[oos["lam"] >= 2.0]
    print("  %-22s N=%-7d dose-korr %+.3f · lam≥2 avgR FULL %+.3f (n=%d) · OOS %+.3f (n=%d)" % (
        label, len(bk), corr, g["r"].mean(), len(g),
        go["r"].mean() if len(go) else float("nan"), len(go)))
    return corr, (go["r"].mean() if len(go) else -9)


def flow(coins, label):
    n1y = 0; tmax = None
    for c, cd in coins.items():
        ts = cd["ts"]
        if len(ts):
            t1 = pd.Timestamp(ts[-1])
            tmax = t1 if tmax is None or t1 > tmax else tmax
    cut = tmax - pd.Timedelta(days=365)
    for c, cd in coins.items():
        ts = cd["ts"]
        n1y += sum(1 for j in cd["entries"] if pd.Timestamp(ts[j]) >= cut)
    print("  %-12s lam-gate giriş SON-1Y: %.1f/10gün" % (label, 10.0 * n1y / 365))
    return 10.0 * n1y / 365


def main():
    print("ESKİ evren (43)..."); dfs_old = load_with_micro()
    print("YENİ kohort (breadth)...")
    dfs_new = load_with_micro("mktdata_breadth", "microdata_breadth")
    print("  yeni coin: %d" % len(dfs_new))
    print("=" * 102)
    print("  ① GENELLEME: yeni kohort lam dose-response (kabul: korr>0.5 VE lam≥2 OOS avgR>0)")
    corr, oosr = dose(collect_breakouts(dfs_new), "YENİ kohort")
    ok = corr > 0.5 and oosr > 0
    print("  KARAR: %s" % ("✅ GENELLEŞİYOR → evrene kat" if ok else "❌ genelleşmiyor → genişletme İPTAL"))
    if not ok:
        return
    print("=" * 102)
    print("  ② SİNYAL AKIŞI")
    co = build_entries(dfs_old); cn = build_entries(dfs_new)
    f_old = flow(co, "eski-43")
    comb = dict(co); comb.update(cn)
    f_comb = flow(comb, "BİRLEŞİK")
    print("  akış çarpanı: ×%.1f" % (f_comb / f_old if f_old else 0))
    print("=" * 102)
    print("  ③ HIZ-MC: Step1 +%10 (statik −%10 / günlük −%5 / 60g) — AYNI config, eski vs birleşik")
    P = dict(r_build=0.0030, r_protect=0.0005, cushion=0.08, maxr=0.012, max_pos=8)
    rng = np.random.default_rng(11)
    for label, coins in (("eski-43", co), ("BİRLEŞİK", comb)):
        tl = build_timeline(coins)
        starts = rng.integers(int(len(tl) * 0.25), int(len(tl) * 0.7), size=N)
        p, b, med, fast = mc(coins, tl, starts, P, 1.5, *MILD)
        hp, hb, hmed, hfast = mc(coins, tl, starts, P, 1.5, *HARSH)
        print("  %-10s gate1.5 %%0.30: P(pass) %.0f/%.0f%% · blow %.0f/%.0f%% · medyan %d/%dg · ≤10g %.0f/%.0f%%  (MILD/HARSH)" % (
            label, p, hp, b, hb, med, hmed, fast, hfast))
    print("=" * 102)


if __name__ == "__main__":
    main()
