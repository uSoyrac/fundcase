#!/usr/bin/env python3
"""funded_harvest_mc.py — FABRİKA modelinin funded-kolu: +%5 payout'a HIZLI hasat.
Mantık: eval-fabrikası haftada ~1 funded üretiyorsa funded hesap YERİNE-KONULABİLİR →
funded'da ultra-temkin (%0.08, 8-14 ay/payout) yerine AGRESİF hasat denenebilir.
TEST: HyroTrader funded (+%5 çekim hedefi, −%10 statik taban, −%5 günlük), stres dahil:
base ∈ {0.08, 0.15, 0.25, 0.35} → P(+5%-önce), P(blow), medyan-gün, payout-EV.
EV/hesap = P(payout)×$5k×0.8 − P(blow)×(yeni-eval maliyeti ~$200). 43-coin taban
(genişlik genelleşirse süreler kısalır)."""
import numpy as np
from prop_sim import load_with_micro, build_entries
from monte_carlo import build_timeline
from stress_mc import stressed_run

N = 400
MILD = (0.0015, 0.00007)
PAYOUT_NET = 5000 * 0.8      # $100k hesap, +%5, %80 split
REPLACE_COST = 200.0


def main():
    print("Veri..."); dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl) * 0.7), size=N)
    print("=" * 100)
    print("  FUNDED HASAT — +%5 payout'a yarış (−%10 statik / −%5 günlük / 90g pencere, STRES)")
    print("=" * 100)
    print("  %-10s %10s %9s %12s %11s %14s %16s" % ("base", "P(payout)", "P(blow)", "P(süre-yok)", "medyan-gün", "EV/döngü($)", "EV/ay($)"))
    for base, maxr, mp in [(0.0008, 0.0035, 5), (0.0015, 0.006, 6), (0.0025, 0.010, 7), (0.0035, 0.014, 7)]:
        P = dict(start=100000.0, target=0.05, total=0.10, daily=0.05, halt=0.03,
                 max_days=90, base=base, maxr=maxr, max_pos=mp, payout=False)
        o = {}; days = []
        for s in starts:
            r, d, _ = stressed_run(coins, tl, int(s), P, *MILD)
            o[r] = o.get(r, 0) + 1
            if r == "pass": days.append(d)
        n = N; pp = o.get("pass", 0) / n; pb = o.get("blown", 0) / n; pt = o.get("timeout", 0) / n
        med = int(np.median(days)) if days else -1
        # döngü süresi: payout→devam (hesap yaşar), blow→hesap ölür. EV/döngü ve aylık akış:
        ev = pp * PAYOUT_NET - pb * REPLACE_COST
        cyc = (np.mean(days) if days else 60) * pp + 30 * pb + 90 * pt   # kaba döngü-gün
        evm = ev / (cyc / 30.0) if cyc else 0
        print("  %%%-9.2f %9.0f%% %8.0f%% %11.0f%% %11s %14.0f %16.0f" % (
            base * 100, 100 * pp, 100 * pb, 100 * pt, med, ev, evm))
    print("=" * 100)
    print("  EV/ay = tek funded hesabın aylık beklenen net çekimi (payout sonrası hesap YAŞAR,")
    print("  taban sıfırlanır → döngü tekrar). blow → fabrika yenisini ~1 haftada getirir.")


if __name__ == "__main__":
    main()
