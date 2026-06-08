#!/usr/bin/env python3
"""monte_carlo_10x.py — $100→$1000 (10x) NE KADAR SÜRER + iflas olasılığı? (KENDİ PARA)
Önemli: kendi-parada günlük −%5 = ELENME DEĞİL, sadece 'o gün dur'. Yalnız −%70 total = iflas."""
import numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, conviction_risk,
                      kill_switch, intraday_halt, RT_COST_PRICE)
from monte_carlo import build_timeline

N = 400
RUIN = 0.70   # −%70 total dip = 'öldü' (kendi-para, 10x peşinde)


def run_growth(coins, tl, start_idx, P):
    """KENDİ-PARA döngüsü: günlük/intraday = HALT (elenme değil); yalnız −%70 total = iflas."""
    start = 100.0
    target = start * (1 + P["target"]); floor = start * (1 - RUIN)
    equity = peak = day_start = start; cur_day = None; day_halted = False
    open_pos = {}; t0 = pd.Timestamp(tl[start_idx][0]); days = 0
    for k in range(start_idx, len(tl)):
        ts, c, j = tl[k]
        days = (pd.Timestamp(ts) - t0).days
        if days > P["max_days"]:
            return "timeout", days
        day = str(ts)[:10]
        if day != cur_day:
            cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; H = cd["H"][j]; L = cd["L"][j]
        if c in open_pos:
            d, entry, sl, tp, ra = open_pos[c]
            exit_p = (sl if L <= sl else tp if H >= tp else None) if d == 1 \
                else (sl if H >= sl else tp if L <= tp else None)
            if exit_p is not None:
                sl_dist = abs(entry - sl) / entry
                R = (d * (exit_p - entry) / entry) / sl_dist - RT_COST_PRICE / sl_dist
                equity += ra * R; peak = max(peak, equity); del open_pos[c]
                if equity >= target: return "win", days
                if equity <= floor:  return "ruin", days     # SADECE −%70 = iflas
                if intraday_halt(equity, day_start, P["halt"]): day_halted = True
                if equity <= day_start * (1 - P["daily"]):     day_halted = True   # HALT, elenme DEĞİL
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < P["max_pos"]:
            if intraday_halt(equity, day_start, P["halt"]):
                day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, P["base"], P["maxr"]))
    return "timeout", days


def main():
    print("Veri + feature...")
    dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rng = np.random.default_rng(7)
    starts = rng.integers(0, int(len(tl) * 0.55), size=N)   # 3-yıl runway

    configs = [
        ("Sprint  %0.40/max1.5", dict(base=0.0040, maxr=0.015, max_pos=8)),
        ("Agresif %0.60/max2.5", dict(base=0.0060, maxr=0.025, max_pos=8)),
        ("Vahşi   %0.80/max3.5", dict(base=0.0080, maxr=0.035, max_pos=10)),
        ("Manyak  %1.20/max5.0", dict(base=0.0120, maxr=0.050, max_pos=10)),
    ]
    base_P = dict(target=9.0, daily=0.05, halt=0.03, max_days=1095)
    print("=" * 98)
    print(f"  $100→$1000 (10x) · {N} rastgele başlangıç · 3-yıl pencere · iflas=−%{RUIN*100:.0f} · KENDİ PARA")
    print("=" * 98)
    print(f"  {'config':<22}{'P(10x)':>9}{'P(iflas)':>10}{'P(yavaş)':>10}{'medyan-süre':>14}{'en hızlı %10':>14}")
    print("-" * 98)
    for name, cfg in configs:
        P = {**base_P, **cfg}
        win = ruin = 0; d10 = []
        for s in starts:
            res, days = run_growth(coins, tl, int(s), P)
            if res == "win": win += 1; d10.append(days)
            elif res == "ruin": ruin += 1
        slow = N - win - ruin
        med = f"{np.median(d10)/30:.1f} ay" if d10 else "—"
        fast = f"{np.percentile(d10,10)/30:.1f} ay" if d10 else "—"
        print(f"  {name:<22}{100*win/N:>8.0f}%{100*ruin/N:>9.0f}%{100*slow/N:>9.0f}%{med:>14}{fast:>14}")
    print("-" * 98)
    print("  P(yavaş)=3 yılda ne 10x ne iflas · medyan=10x'e ulaşanların ortancası · NOT: tek 5.4y tarihsel veri")
    print("=" * 98)


if __name__ == "__main__":
    main()
