#!/usr/bin/env python3
"""sprint_z_mc.py — TRADER MEKANIZMA TESTI: z-konsantrasyon + cushion-then-protect.
2-step Step1 (+%10): yalnIz yuksek-lam (top-decile, z>4 proxy) girislerinde YOGUNLAS,
buyuk size ile +%10 yastIgInI hIzlI kur; yastIk kurulunca riski sErt dusur (koru).
Statik -%10 taban, gunluk -%5, gun-ici -%3 halt. Stres (slip+funding) dahil.
Karsilastirma: (A) duz-base her-sinyal, (B) z-gate-only, (C) z-gate + cushion-then-protect."""
import numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, RT_COST_PRICE)
from monte_carlo import build_timeline

N = 500
S = 100000.0
DAILY, HALT, TOTAL = 0.05, 0.03, 0.10
FLOOR = S * (1 - TOTAL)


def run(coins, tl, s, P, lam_gate, slip, fund):
    """P: r_build, r_protect, cushion (yastik esigi), maxr, max_pos.
    lam_gate: bu lam-altI girisleri ATLA (z-konsantrasyon). Doner (sonuc, gun)."""
    target = S * (1 + 0.10)
    equity = day_start = S; cur_day = None; day_halted = False
    open_pos = {}; t0 = pd.Timestamp(tl[s][0]); days = 0
    cushion_lvl = S * (1 + P["cushion"])
    for k in range(s, len(tl)):
        ts, c, j = tl[k]; days = (pd.Timestamp(ts) - t0).days
        if days > 60:
            return "timeout", days
        day = str(ts)[:10]
        if day != cur_day: cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; O = cd["O"][j]; H = cd["H"][j]; L = cd["L"][j]
        if c in open_pos:
            d, entry, sl, tp, ra, eb = open_pos[c]; ex = None
            if d == 1:
                if L <= sl: ex = O if O <= sl else sl * (1 - slip)
                elif H >= tp: ex = tp
            else:
                if H >= sl: ex = O if O >= sl else sl * (1 + slip)
                elif L <= tp: ex = tp
            if ex is not None:
                sld = abs(entry - sl) / entry
                R = (d * (ex - entry) / entry) / sld - RT_COST_PRICE / sld - (j - eb) * fund / sld
                equity += ra * R; del open_pos[c]
                if equity >= target: return "pass", days
                if equity <= FLOOR or equity <= day_start * (1 - DAILY):
                    return "blown", days
                if equity <= day_start * (1 - HALT): day_halted = True
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < P["max_pos"]:
            if equity <= day_start * (1 - HALT): day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                if lam < lam_gate: continue                      # z-KONSANTRASYON: zayifi atla
                # CUSHION-THEN-PROTECT: yastik altinda buyuk size, ustunde koruma-risk
                base = P["r_build"] if equity < cushion_lvl else P["r_protect"]
                # lam-conviction: gate ustunde lam ne kadar yuksekse o kadar size (z>4 -> %88 WR)
                mult = np.clip(lam / max(lam_gate, 1e-9), 1.0, 2.5)
                ra = equity * float(np.clip(base * mult, 0.0, P["maxr"]))
                open_pos[c] = (d, entry, sl, tp, ra, j)
    return "timeout", days


def lam_quantile(coins, q):
    alllam = []
    for c, cd in coins.items():
        for j, e in cd["entries"].items(): alllam.append(e[4])
    alllam = np.array(alllam)
    return float(np.quantile(alllam, q)), alllam


def mc(coins, tl, starts, P, lam_gate, slip, fund):
    o = {}; pd_ = []
    for s in starts:
        r, d = run(coins, tl, int(s), P, lam_gate, slip, fund)
        o[r] = o.get(r, 0) + 1
        if r == "pass": pd_.append(d)
    med = int(np.median(pd_)) if pd_ else -1
    p10 = int(np.percentile(pd_, 10)) if pd_ else -1
    fast = 100 * sum(1 for d in pd_ if d <= 10) / len(starts)   # 10-gun-ici pass orani
    return (100 * o.get("pass", 0) / len(starts), 100 * o.get("blown", 0) / len(starts), med, fast)


def main():
    print("Veri + feature..."); dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl) * 0.7), size=N)
    MILD = (0.00007, 0.0); HARSH = (0.00015, 0.00010)  # (slip, fund/bar)
    q50, alllam = lam_quantile(coins, 0.5)
    q90, _ = lam_quantile(coins, 0.90)
    print(f"  toplam giris havuzu={len(alllam)}  lam medyan={q50:.2f}  lam-p90={q90:.2f}  max={alllam.max():.2f}")

    print("=" * 100)
    print(f"  2-STEP Step1 (+%10) — TRADER FAST-PASS · statik -%10 / gunluk -%5 / 60g pencere · {N} sim · STRES")
    print("=" * 100)
    print(f"  {'strateji':<44}{'P(pass)':>9}{'P(blown)':>10}{'med-gun':>9}{'<=10g%':>8}")
    print("-" * 100)
    cfgs = [
        ("A duz %0.30 her-sinyal (gate yok)",
         dict(r_build=0.0030, r_protect=0.0030, cushion=0.10, maxr=0.010, max_pos=8), 1.0),
        ("F gate>1.5 %0.30 cushion%8->protect %0.05",
         dict(r_build=0.0030, r_protect=0.0005, cushion=0.08, maxr=0.012, max_pos=8), 1.5),
        ("G gate>1.5 %0.45 cushion%8->protect %0.05",
         dict(r_build=0.0045, r_protect=0.0005, cushion=0.08, maxr=0.018, max_pos=8), 1.5),
        ("H gate>1.5 %0.45 NO-protect (yastik=hedef)",
         dict(r_build=0.0045, r_protect=0.0045, cushion=0.10, maxr=0.018, max_pos=8), 1.5),
        ("I gate>2.0 %0.45 cushion%8->protect %0.05",
         dict(r_build=0.0045, r_protect=0.0005, cushion=0.08, maxr=0.018, max_pos=8), 2.0),
        ("J gate>1.5 %0.60 cushion%8->protect %0.04",
         dict(r_build=0.0060, r_protect=0.0004, cushion=0.08, maxr=0.024, max_pos=8), 1.5),
    ]
    for name, P, gate in cfgs:
        mp_, mb, mmed, mfast = mc(coins, tl, starts, P, gate, *MILD)
        hp, hb, hmed, hfast = mc(coins, tl, starts, P, gate, *HARSH)
        print(f"  {name:<44}{mp_:>7.0f}%{mb:>9.0f}%{mmed:>9}{mfast:>7.0f}%   |MILD")
        print(f"  {'':44}{hp:>7.0f}%{hb:>9.0f}%{hmed:>9}{hfast:>7.0f}%   |HARSH")
    print("-" * 100)
    print("  <=10g% = TUM simlerin yuzde-kaci 10 gun-ICINDE +%10'u gordu (gercek fast-pass metrigi).")
    print("=" * 100)


if __name__ == "__main__":
    main()
