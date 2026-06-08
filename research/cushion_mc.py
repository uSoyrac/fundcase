#!/usr/bin/env python3
"""cushion_mc.py — CUSHION-CARRY + İKİ-FAZ DİNAMİK RİSK testi (funded gelir-artırma).
Tez: HyroTrader zemini STATİK $90k → çekilen kâr kalıcı güvende, TAŞINAN tampon zemini
uzaklaştırır. Yüksek riski (harvest) yalnız tampon varken bas; taze biriktirirken düşük risk.
Stres dahil (gap-stop + funding). Düz %0.08 baseline'a karşı."""
import numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, conviction_risk, RT_COST_PRICE)
from monte_carlo import build_timeline

N = 400
S = 100000.0
FLOOR = S * 0.90          # HyroTrader STATİK −%10
DAILY, HALT = 0.05, 0.03


def run(coins, tl, s, P, slip, fund):
    """P: risk_a, risk_b, phase_thr, carry, wd_trig, maxr, max_pos. Döner (sonuç, yıllık_net_$)."""
    carry = P["carry"] * S
    base_line = S + carry                 # çekimden sonra dönülen seviye (taşınan tampon)
    thr = P["phase_thr"] * S              # base_line üstü bu kadar → Faz-B (harvest)
    trig = P["wd_trig"] * S               # base_line üstü bu kadar → çek
    equity = day_start = S; vault = 0.0; cur_day = None; day_halted = False
    open_pos = {}; t0 = pd.Timestamp(tl[s][0]); window = P["max_days"]
    for k in range(s, len(tl)):
        ts, c, j = tl[k]; days = (pd.Timestamp(ts) - t0).days
        if days > window:
            break
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
                if equity <= FLOOR or equity <= day_start * (1 - DAILY):
                    return "blown", vault / (window / 365)
                if equity >= base_line + trig:                  # ÇEKİM (taşınan tampona kadar)
                    vault += (equity - base_line) * 0.80; equity = base_line
                if equity <= day_start * (1 - HALT): day_halted = True
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < P["max_pos"]:
            if equity <= day_start * (1 - HALT): day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                # İKİ-FAZ: tampon (base_line üstü) ≥ thr ise harvest-risk, değilse build-risk
                base = P["risk_b"] if (equity - base_line) >= thr else P["risk_a"]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, base, P["maxr"]), j)
    return "survived", vault / (window / 365)


def mc(coins, tl, starts, P, slip, fund):
    o = {}; inc = []
    for s in starts:
        r, net = run(coins, tl, int(s), P, slip, fund)
        o[r] = o.get(r, 0) + 1; inc.append(net)
    return np.median(inc), 100 * o.get("blown", 0) / len(starts)


def main():
    print("Veri + feature..."); dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(11); starts = rng.integers(0, int(len(tl) * 0.6), size=N)
    MILD = (0.0015, 0.00007); HARSH = (0.0030, 0.00015)

    print("=" * 96)
    print(f"  CUSHION-CARRY + İKİ-FAZ — yıllık net $ / P(iflas) · {N} sim · stres dahil · $100k funded")
    print("=" * 96)
    print(f"  {'strateji':<40}{'ILIMLI $/iflas':>22}{'SERT $/iflas':>22}")
    print("-" * 96)

    cfgs = [
        ("BASELINE düz %0.08 (çek→tabana)",
         dict(risk_a=0.0008, risk_b=0.0008, phase_thr=0.0, carry=0.0, wd_trig=0.05, maxr=0.004, max_pos=5)),
        ("İki-faz %0.06→%0.20 (carry 0)",
         dict(risk_a=0.0006, risk_b=0.0020, phase_thr=0.02, carry=0.0, wd_trig=0.05, maxr=0.010, max_pos=5)),
        ("Cushion-carry %2 + %0.06→%0.20",
         dict(risk_a=0.0006, risk_b=0.0020, phase_thr=0.02, carry=0.02, wd_trig=0.05, maxr=0.010, max_pos=5)),
        ("Cushion-carry %4 + %0.06→%0.20",
         dict(risk_a=0.0006, risk_b=0.0020, phase_thr=0.02, carry=0.04, wd_trig=0.05, maxr=0.010, max_pos=5)),
        ("Cushion-carry %4 + %0.06→%0.30 (agresif harvest)",
         dict(risk_a=0.0006, risk_b=0.0030, phase_thr=0.02, carry=0.04, wd_trig=0.05, maxr=0.014, max_pos=6)),
        ("Cushion-carry %6 + %0.06→%0.30",
         dict(risk_a=0.0006, risk_b=0.0030, phase_thr=0.02, carry=0.06, wd_trig=0.05, maxr=0.014, max_pos=6)),
    ]
    for name, P in cfgs:
        P = {**P, "max_days": 365}
        mi, mb = mc(coins, tl, starts, P, *MILD)
        hi, hb = mc(coins, tl, starts, P, *HARSH)
        print(f"  {name:<40}{f'${mi:>7,.0f}/{mb:>2.0f}%':>22}{f'${hi:>7,.0f}/{hb:>2.0f}%':>22}")
    print("-" * 96)
    print("  Hedef: gelir↑ (baseline ~$8k'dan), iflas %0'a yakın kalsın. Harvest yalnız zeminden uzakta.")
    print("=" * 96)


if __name__ == "__main__":
    main()
