#!/usr/bin/env python3
"""
monte_carlo.py — PROP-CHALLENGE P(GEÇİŞ) DAĞILIMI (500 rastgele başlangıç)
═══════════════════════════════════════════════════════════════════════════════
Her deneme: taze hesap, rastgele tarihte başla, terminal duruma kadar yürü:
  PASS    : equity ≥ +TARGET (örn +%10) → funded
  FAIL    : equity ≤ −TOTAL (statik taban) VEYA gün-içi −DAILY ihlali
  TIMEOUT : max_days içinde ne geçti ne battı
Çıktı: P(pass)/P(fail)/P(timeout) + medyan geçiş süresi, config'lere göre.
Tarihsel rastgele-başlangıç MC (blok-bootstrap değil; gerçek fiyat yollarında).
"""
import sys, numpy as np, pandas as pd
from prop_sim import (load_with_micro, build_entries, conviction_risk,
                      kill_switch, intraday_halt, RT_COST_PRICE)

SEED = 11


def build_timeline(coins):
    tl = []
    for c, d in coins.items():
        for j in range(len(d["ts"])):
            tl.append((d["ts"][j], c, j))
    tl.sort(key=lambda x: x[0])
    return tl


def run_challenge(coins, tl, start_idx, P):
    """Tek challenge: terminal durum + gün + final equity döner."""
    start = 10000.0
    target = start * (1 + P["target"]); floor = start * (1 - P["total"])
    equity = peak = day_start = start; cur_day = None; day_halted = False
    open_pos = {}
    t0 = pd.Timestamp(tl[start_idx][0]); days = 0
    for k in range(start_idx, len(tl)):
        ts, c, j = tl[k]
        days = (pd.Timestamp(ts) - t0).days
        if days > P["max_days"]:
            return "timeout", days, equity
        day = str(ts)[:10]
        if day != cur_day:
            cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; H = cd["H"][j]; L = cd["L"][j]
        # açık pozisyonu yönet
        if c in open_pos:
            d, entry, sl, tp, ra = open_pos[c]
            exit_p = (sl if (L <= sl) else tp if (H >= tp) else None) if d == 1 \
                else (sl if (H >= sl) else tp if (L <= tp) else None)
            if exit_p is not None:
                sl_dist = abs(entry - sl) / entry
                R = (d * (exit_p - entry) / entry) / sl_dist - RT_COST_PRICE / sl_dist
                equity += ra * R; peak = max(peak, equity); del open_pos[c]
                if equity >= target: return "pass", days, equity
                if equity <= floor: return "fail", days, equity
                if equity <= day_start * (1 - P["daily"]): return "fail", days, equity
                if intraday_halt(equity, day_start, P["halt"]): day_halted = True
        # yeni giriş
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < P["max_pos"]:
            if intraday_halt(equity, day_start, P["halt"]) or kill_switch(equity, peak, day_start, P["firm"]):
                day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, P["base"], P["maxr"]))
    return "timeout", days, equity


def monte_carlo(coins, tl, P, n=500, seed=SEED):
    rng = np.random.default_rng(seed)
    hi = int(len(tl) * 0.85)
    starts = rng.integers(0, hi, size=n)
    out = {"pass": 0, "fail": 0, "timeout": 0}; pass_days = []
    for s in starts:
        res, days, eq = run_challenge(coins, tl, int(s), P)
        out[res] += 1
        if res == "pass": pass_days.append(days)
    return out, pass_days


def main():
    print("Veri + feature (lam/VR) hesaplanıyor...")
    dfs = load_with_micro()
    coins = build_entries(dfs)
    tl = build_timeline(coins)
    FIRM = {"daily": 0.05, "total": 0.12, "trailing": False}
    base_P = dict(firm=FIRM, target=0.10, total=0.12, daily=0.05, halt=0.03, max_days=90)

    configs = [
        ("PROP   (base0.15/max0.6/6poz)", dict(base=0.0015, maxr=0.006, max_pos=6)),
        ("SPRINT (base0.40/max1.5/8poz)", dict(base=0.0040, maxr=0.015, max_pos=8)),
        ("ORTA   (base0.25/max1.0/8poz)", dict(base=0.0025, maxr=0.010, max_pos=8)),
    ]
    N = 500
    print("=" * 92)
    print(f"  MONTE-CARLO P(GEÇİŞ) — {N} rastgele başlangıç · +%{base_P['target']*100:.0f} hedef / "
          f"−%{base_P['total']*100:.0f} statik taban / −%{base_P['daily']*100:.0f} günlük / {base_P['max_days']}g limit")
    print("=" * 92)
    print(f"  {'config':<32}{'P(pass)':>9}{'P(fail)':>9}{'P(timeout)':>12}{'medyan-gün':>12}")
    print("-" * 92)
    for name, cfg in configs:
        P = {**base_P, **cfg}
        out, pdays = monte_carlo(coins, tl, P, n=N)
        med = int(np.median(pdays)) if pdays else -1
        print(f"  {name:<32}{100*out['pass']/N:>8.1f}%{100*out['fail']/N:>8.1f}%"
              f"{100*out['timeout']/N:>11.1f}%{med:>12}")
    print("=" * 92)

    # ── SÜRE-LİMİTİ DUYARLILIĞI (firma süre kuralına göre config seçimi) ──
    print("\n" + "=" * 92)
    print("  SÜRE-LİMİTİ DUYARLILIĞI — P(pass) / P(fail) limit gününe göre")
    print("=" * 92)
    print(f"  {'config':<32}" + "".join(f"{str(d)+'g':>13}" for d in (60, 90, 180, 365)))
    for name, cfg in [("PROP   (base0.15)", dict(base=0.0015, maxr=0.006, max_pos=6)),
                      ("ORTA   (base0.25)", dict(base=0.0025, maxr=0.010, max_pos=8))]:
        cells = []
        for md in (60, 90, 180, 365):
            P = {**base_P, **cfg, "max_days": md}
            out, _ = monte_carlo(coins, tl, P, n=N)
            cells.append(f"{100*out['pass']/N:>4.0f}/{100*out['fail']/N:>3.0f}f")
        print(f"  {name:<32}" + "".join(f"{x:>13}" for x in cells))
    print("  (hücre = P(pass)% / P(fail)%f · limitsiz firmada düşük-risk daha üstün)")
    print("=" * 92)
    print("  Not: tarihsel rastgele-başlangıç; statik-taban başlangıçtan (firma trailing değil).")


if __name__ == "__main__":
    main()
