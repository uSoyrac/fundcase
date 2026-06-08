#!/usr/bin/env python3
"""stress_mc.py — GERÇEKÇİ SÜRTÜNME STRES-TESTİ (gap-stop slippage + funding).
'1 yılda %0' iyimser sayısını → 'gerçekçi sürtünmelerle %X iflas, $Y gelir'e çevirir.
Ayrıca HIZLI-EVAL taraması (%65-70 geçiş, daha çabuk). HyroTrader 2-step %5/%10 statik."""
import numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, conviction_risk, RT_COST_PRICE)
from monte_carlo import build_timeline

N = 400


def stressed_run(coins, tl, s, P, SLIP_STOP, FUND):
    """Gap-stop + funding'li tek koşu. Döner: (sonuç, gün, yıllık_net_$)."""
    start = P["start"]; target = start * (1 + P["target"]) if P["target"] > 0 else None
    equity = peak = day_start = start; baseline = start; vault = 0.0
    floor = start * (1 - P["total"]); cur_day = None; day_halted = False
    open_pos = {}; t0 = pd.Timestamp(tl[s][0]); days = 0
    for k in range(s, len(tl)):
        ts, c, j = tl[k]; days = (pd.Timestamp(ts) - t0).days
        if days > P["max_days"]:
            return ("timeout" if target else "survived"), days, vault / (P["max_days"] / 365)
        day = str(ts)[:10]
        if day != cur_day: cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; O = cd["O"][j]; H = cd["H"][j]; L = cd["L"][j]
        if c in open_pos:
            d, entry, sl, tp, ra, eb = open_pos[c]; exit_p = None
            if d == 1:
                if L <= sl:                                  # STOP (gap mi intrabar mı)
                    exit_p = O if O <= sl else sl * (1 - SLIP_STOP)   # gap→açılış, yoksa slip
                elif H >= tp:
                    exit_p = tp
            else:
                if H >= sl:
                    exit_p = O if O >= sl else sl * (1 + SLIP_STOP)
                elif L <= tp:
                    exit_p = tp
            if exit_p is not None:
                sld = abs(entry - sl) / entry
                fund = (j - eb) * FUND / sld                 # tutulan bar başına funding
                R = (d * (exit_p - entry) / entry) / sld - RT_COST_PRICE / sld - fund
                equity += ra * R; peak = max(peak, equity); del open_pos[c]
                if target and equity >= target: return "pass", days, 0
                if equity <= floor or equity <= day_start * (1 - P["daily"]):
                    return "blown", days, vault / (P["max_days"] / 365)
                if P.get("payout") and equity >= baseline * (1 + P["payout_trigger"]):
                    vault += (equity - baseline) * 0.80; equity = baseline
                if equity <= day_start * (1 - P["halt"]): day_halted = True
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < P["max_pos"]:
            if equity <= day_start * (1 - P["halt"]): day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, P["base"], P["maxr"]), j)
    return ("timeout" if target else "survived"), days, vault / (P["max_days"] / 365)


def run_mc(coins, tl, starts, P, slip, fund):
    o = {}; pdays = []; inc = []
    for s in starts:
        r, d, net = stressed_run(coins, tl, int(s), P, slip, fund)
        o[r] = o.get(r, 0) + 1
        if r == "pass": pdays.append(d)
        inc.append(net)
    return o, pdays, inc


def main():
    print("Veri + feature..."); dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl) * 0.6), size=N)
    # iki stres seviyesi: ILIMLI ve SERT (belirsizliği köşele)
    LEVELS = [("ILIMLI", 0.0015, 0.00007), ("SERT", 0.0030, 0.00015)]   # slip_stop, funding/bar

    print("=" * 98)
    print(f"  STRES-TEST · gap-stop + funding · {N} sim · HyroTrader 2-step %5/%10 statik")
    print("  ILIMLI: stop-slip 15bps, funding %0.007/bar · SERT: 30bps, %0.015/bar")
    print("=" * 98)

    print("\n  🔵 EVAL Step1 (+%10) — P(pass)/P(blown)/medyan-gün:")
    print(f"  {'base':<8}{'TEMİZ(ref)':>16}{'ILIMLI':>18}{'SERT':>18}")
    clean = {"0.15": "100/0 /110", "0.20": "98/2 /78", "0.25": "~88/~10", "0.30": "76/24 /32"}
    for base, maxr, mp in [(0.0015, 0.007, 6), (0.0020, 0.009, 6), (0.0025, 0.011, 7), (0.0030, 0.012, 8)]:
        cells = []
        for _, slip, fund in LEVELS:
            P = dict(start=10000.0, target=0.10, total=0.10, daily=0.05, halt=0.03, max_days=1095,
                     base=base, maxr=maxr, max_pos=mp)
            o, pd_, _ = run_mc(coins, tl, starts, P, slip, fund)
            med = int(np.median(pd_)) if pd_ else -1
            cells.append(f"{100*o.get('pass',0)/N:>3.0f}/{100*o.get('blown',0)/N:>2.0f}b /{med}")
        ref = clean.get(f"{base*100:.2f}", "—")
        print(f"  %{base*100:<6.2f}{ref:>16}{cells[0]:>18}{cells[1]:>18}")

    print("\n  🟢 FUNDED (base × +%5 çekim) — yıllık net $ / P(iflas):")
    print(f"  {'base':<8}{'TEMİZ(ref)':>18}{'ILIMLI':>20}{'SERT':>20}")
    cleanf = {"0.10": "$13k/0%", "0.12": "$16.5k/0%", "0.16": "$21k/19%"}
    for base, maxr, mp in [(0.0010, 0.005, 6), (0.0012, 0.006, 6), (0.0016, 0.008, 6)]:
        cells = []
        for _, slip, fund in LEVELS:
            P = dict(start=100000.0, target=0.0, total=0.10, daily=0.05, halt=0.03, max_days=365,
                     base=base, maxr=maxr, max_pos=mp, payout=True, payout_trigger=0.05)
            o, _, inc = run_mc(coins, tl, starts, P, slip, fund)
            cells.append(f"${np.median(inc):>7,.0f}/{100*o.get('blown',0)/N:>2.0f}%")
        ref = cleanf.get(f"{base*100:.2f}", "—")
        print(f"  %{base*100:<6.2f}{ref:>18}{cells[0]:>20}{cells[1]:>20}")
    print("=" * 98)
    print("  TEMİZ = sürtünmesiz eski sayı (ref). Gerçek canlı ILIMLI-SERT aralığında olacak.")


if __name__ == "__main__":
    main()
