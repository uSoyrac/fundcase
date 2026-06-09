#!/usr/bin/env python3
"""fast_funding_mc.py — FONU HIZLI/SIK ALMA: challenge geçiş-SÜRESİ dağılımı + kohort kadansı.
Agresif eval configleri × {1-step 4%/6%, 2-step 5%/10%} stres altında: P(pass), medyan-gün,
P(blow). Sonra: 'haftada/10-günde bir funded' için kaç paralel challenge + fee maliyeti."""
import numpy as np, pandas as pd
from prop_sim import load_with_micro, build_entries
from monte_carlo import build_timeline
from stress_mc import stressed_run

N = 400
MILD = (0.0015, 0.00007)
FEE = 200.0   # ~challenge ücreti (geçince iade); net maliyet = fee × başarısız-deneme


def run_cfg(coins, tl, starts, base, maxr, mp, total, daily, target, max_days):
    P = dict(start=10000.0, target=target, total=total, daily=daily, halt=min(daily-0.02, 0.03),
             max_days=max_days, base=base, maxr=maxr, max_pos=mp, payout=False)
    o = {}; pdays = []
    for s in starts:
        r, d, _ = stressed_run(coins, tl, int(s), P, *MILD)
        o[r] = o.get(r, 0) + 1
        if r == "pass": pdays.append(d)
    n = len(starts)
    p = o.get("pass", 0) / n; blow = o.get("blown", 0) / n
    med = int(np.median(pdays)) if pdays else -1
    p25 = int(np.percentile(pdays, 25)) if pdays else -1
    return p, blow, med, p25


def main():
    print("Veri..."); dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl) * 0.7), size=N)

    print("=" * 100)
    print("  FONU HIZLI ALMA — challenge geçiş hız/blow (stres dahil, 90g pencere)")
    print("=" * 100)
    print("  ── 1-STEP (4%/6%, +%10) — tek fazda funded (EN HIZLI yol) ──")
    print(f"  {'base':<8}{'P(pass)':>9}{'P(blow)':>9}{'medyan-gün':>12}{'hızlı-%25':>11}{'deneme/funded':>15}{'net-fee/funded':>16}")
    rows1 = []
    for base, maxr, mp in [(0.0020, 0.009, 6), (0.0035, 0.014, 7), (0.0050, 0.020, 8), (0.0070, 0.028, 8)]:
        p, blow, med, p25 = run_cfg(coins, tl, starts, base, maxr, mp, 0.06, 0.04, 0.10, 90)
        att = 1 / p if p > 0 else 99; rows1.append((base, p, med, att))
        print(f"  %{base*100:<6.2f}{100*p:>8.0f}%{100*blow:>8.0f}%{med:>12}{p25:>11}{att:>14.1f}{FEE*(att-1):>15.0f}$")

    print("\n  ── 2-STEP (5%/10%) Step1 (+%10) — daha geniş DD ama 2 faz (Step2 +%5 ~×0.6 süre) ──")
    print(f"  {'base':<8}{'P(pass)':>9}{'P(blow)':>9}{'medyan-gün':>12}{'hızlı-%25':>11}")
    for base, maxr, mp in [(0.0025, 0.011, 7), (0.0040, 0.016, 8), (0.0060, 0.024, 8)]:
        p, blow, med, p25 = run_cfg(coins, tl, starts, base, maxr, mp, 0.10, 0.05, 0.10, 90)
        print(f"  %{base*100:<6.2f}{100*p:>8.0f}%{100*blow:>8.0f}%{med:>12}{p25:>11}")

    print("\n" + "=" * 100)
    print("  KOHORT KADANSI — 'her 10 günde 1 funded' için kaç paralel challenge? (1-step)")
    print("=" * 100)
    print("  Mantık: steady-state funded-akış = (paralel-slot / medyan-gün) × P(pass).")
    print("  Hedef = 0.1 funded/gün (her 10g bir).  Gerekli paralel-slot = 0.1 × medyan-gün / P(pass)")
    for base, p, med, att in rows1:
        if med <= 0: continue
        slots_10g = 0.1 * med / p
        slots_7g = (1/7.0) * med / p
        print(f"  base %{base*100:.2f} (P={100*p:.0f}%, medyan {med}g): 10-günde-1 için ~{slots_10g:.0f} slot · haftada-1 için ~{slots_7g:.0f} slot")
    print("\n  NOT: HyroTrader tek-firma eşzamanlı sermaye tavanı $200k → ~2×$100k slot. Daha çok slot için")
    print("       ÇOKLU FIRMA gerekir. Fee geçince iade → net maliyet sadece BLOWN denemelerin ücreti.")
    print("=" * 100)


if __name__ == "__main__":
    main()
