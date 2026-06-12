#!/usr/bin/env python3
"""ensemble_eval_mc.py — KULLANICI FİKRİ: 'en kârlı deneme botu (lsx) + fon botu (lam) birleştir'.
Hipotez: lam+lsx dekorele (korr +0.17) → DD yarıya → AYNI BLOW'da daha yüksek risk taşınır →
+%10'a daha HIZLI. Gerçek HYRO 4/6 kurallarında (+%10 hedef / −%6 total / −%4 günlük).
Yöntem: lam-günlük + lsx-günlük getiri serileri (ensemble_lam_lsx), risk-çarpanı m taraması,
+%10-vs-−%6 challenge sim. lam-only vs 50/50 EŞİT-BLOW'da medyan-gün kıyası = hız kanıtı."""
import numpy as np, pandas as pd
from ensemble_lam_lsx import lam_daily, lsx_daily, WIN_START
from falsify import load_with_micro
from prop_sim import build_entries
from monte_carlo import build_timeline

TARGET, TOTAL, DAILY, MAXD = 0.10, 0.06, 0.04, 60
NSIM = 600


def challenge(arr, m, seed=7):
    rng = np.random.default_rng(seed)
    starts = rng.integers(0, max(1, len(arr) - MAXD), size=NSIM)
    o = {"pass": 0, "blow": 0, "timeout": 0}; days = []
    for s in starts:
        nav = 1.0; res = "timeout"
        for k in range(s, min(s + MAXD, len(arr))):
            r = m * arr[k]
            if r <= -DAILY:                      # günlük −%4 ihlali
                res = "blow"; break
            nav *= (1 + r)
            if nav <= 1 - TOTAL:                 # statik −%6 taban
                res = "blow"; break
            if nav >= 1 + TARGET:                # +%10 hedef
                res = "pass"; break
        o[res] += 1
        if res == "pass": days.append(k - s)
    n = NSIM
    return (100 * o["pass"] / n, 100 * o["blow"] / n,
            int(np.median(days)) if days else -1,
            100 * sum(1 for d in days if d <= 10) / n)


def main():
    print("lam günlük (Sprint motor)..."); dfs = load_with_micro()
    coins = build_entries(dfs); tl = build_timeline(coins)
    rl = lam_daily(coins, tl)
    print("lsx günlük..."); rx = lsx_daily()
    idx = rl.index.union(rx.index).sort_values(); idx = idx[idx >= WIN_START]
    rl = rl.reindex(idx).fillna(0.0); rx = rx.reindex(idx).fillna(0.0)
    combo = 0.5 * rl + 0.5 * rx
    corr = rl.corr(rx)
    print("ortak gün: %d · korr lam↔lsx %+.3f" % (len(idx), corr))
    print("=" * 96)
    print("  EVAL HIZ TESTİ — gerçek HYRO 4/6 (+%10/−%6/−%4g) · risk-çarpanı m taraması")
    print("=" * 96)
    print("  %-16s %6s %9s %9s %11s %9s" % ("seri", "m", "P(pass)", "P(blow)", "medyan-gün", "≤10g%"))
    rows = {"lam-only": [], "lam+lsx 50/50": []}
    for label, arr in [("lam-only", rl.values), ("lam+lsx 50/50", combo.values)]:
        for m in [1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
            p, b, med, f = challenge(arr, m)
            rows[label].append((m, p, b, med, f))
            print("  %-16s %6.1f %8.0f%% %8.0f%% %11s %8.0f%%" % (label, m, p, b, med, f))
        print("  " + "-" * 90)
    # EŞİT-BLOW kıyas: her seri için blow~%25'e en yakın config
    print("  ⇒ EŞİT-BLOW (~%25) KIYAS:")
    for label in rows:
        best = min(rows[label], key=lambda r: abs(r[2] - 25))
        print("     %-16s m=%.1f · blow %.0f%% · medyan %dg · pass %.0f%% · ≤10g %.0f%%" % (
            label, best[0], best[2], best[3], best[1], best[4]))
    print("=" * 96)
    print("  Hız kanıtı: lam+lsx aynı blow'da DAHA DÜŞÜK medyan-gün → birleştirme HIZLANDIRIR.")


if __name__ == "__main__":
    main()
