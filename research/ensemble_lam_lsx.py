#!/usr/bin/env python3
"""ensemble_lam_lsx.py — PROJE ③ ENSEMBLE: lam (order-flow trend) + lsx (positioning kontraryan).
İki DOĞRULANMIŞ, DEKORELE edge'i aynı $100 kasada birleştir. Soru: ensemble DD'yi düşürürken
getiriyi koruyor mu? Ortak pencere (2024-06→2026-06, lsx verisi kadar) — adil kıyas.
  lam kolu : Sprint sim (lam-gate girişler, conviction sizing, 2.5R/SL, compound)
  lsx kolu : |lsx|≥1.2 kontraryan, 24h hold, coin-başına tek aktif poz, f notional/işlem
Çıktı: her kol + 50/50 kombo için CAGR / MaxDD / Sharpe / korelasyon (günlük getiriler)."""
import numpy as np, pandas as pd, glob, os
from prop_sim import (load_with_micro, build_entries, conviction_risk,
                      kill_switch, intraday_halt, RT_COST_PRICE)
from monte_carlo import build_timeline

COST = 0.0014; H = 6
WIN_START = "2024-06-01"
LAM_BASE, LAM_MAXR, LAM_MAXPOS = 0.0080, 0.0250, 8     # Sprint agresif
FIRM = {"daily": 0.50, "total": 0.60, "trailing": False}; HALT = 0.50
LSX_THR, LSX_F, LSX_MAXCON = 1.2, 0.10, 8              # işlem başı %10 notional, max 8 eşzamanlı


def lam_daily(coins, tl):
    """Sprint tek-yol (pencere başından), günlük equity → günlük getiri serisi."""
    s0 = next(k for k in range(len(tl)) if str(tl[k][0]) >= WIN_START)
    equity = day_start = 100.0; peak = equity; cur_day = None; day_halted = False
    open_pos = {}; days = {}
    for k in range(s0, len(tl)):
        ts, c, j = tl[k]; day = str(ts)[:10]
        if day != cur_day:
            if cur_day: days[cur_day] = equity
            cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; HH = cd["H"][j]; LL = cd["L"][j]
        if c in open_pos:
            d, entry, sl, tp, ra = open_pos[c]
            ex = (sl if LL <= sl else tp if HH >= tp else None) if d == 1 \
                else (sl if HH >= sl else tp if LL <= tp else None)
            if ex is not None:
                sld = abs(entry - sl) / entry
                R = (d * (ex - entry) / entry) / sld - RT_COST_PRICE / sld
                equity += ra * R; peak = max(peak, equity); del open_pos[c]
                if intraday_halt(equity, day_start, HALT): day_halted = True
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < LAM_MAXPOS:
            if not (intraday_halt(equity, day_start, HALT) or kill_switch(equity, peak, day_start, FIRM)):
                d, entry, sl, tp, lam = cd["entries"][j]
                open_pos[c] = (d, entry, sl, tp, equity * conviction_risk(lam, LAM_BASE, LAM_MAXR))
    if cur_day: days[cur_day] = equity
    s = pd.Series(days).sort_index()
    return s.pct_change().fillna(0.0)


def lsx_daily():
    """lsx event'leri → günlük getiri (notional f, coin-başına tek poz, eşzamanlı cap)."""
    met = {}; mkt = {}
    for f in glob.glob("metricsdata/*_metrics_4h.csv"):
        c = os.path.basename(f).split("_")[0]
        df = pd.read_csv(f); df["ts"] = pd.to_datetime(df["ts"]); met[c] = df.set_index("ts").sort_index()
    for f in glob.glob("mktdata/*_4h.csv"):
        c = os.path.basename(f).split("_")[0]
        df = pd.read_csv(f); df["ts"] = pd.to_datetime(df["ts"]); mkt[c] = df.set_index("ts").sort_index()
    events = []   # (entry_idx_ts, exit_ts, net)
    for c in sorted(set(met) & set(mkt)):
        j = met[c].index.intersection(mkt[c].index)
        ls = met[c]["ls_ratio"].reindex(j).values; cl = mkt[c]["close"].reindex(j).values
        lf = ls / (1.0 + ls); sig = -(lf - 0.5) * 4.0
        last_exit = -1
        for i in range(len(cl) - H):
            if i <= last_exit or not np.isfinite(sig[i]) or abs(sig[i]) < LSX_THR: continue
            if not (np.isfinite(cl[i]) and cl[i] > 0): continue
            d = 1 if sig[i] > 0 else -1
            net = d * (cl[i + H] / cl[i] - 1.0) - COST
            events.append((j[i], j[i + H], net)); last_exit = i + H
    events.sort(key=lambda e: e[0])
    # günlük: aktif-cap'li basit defter
    daily = {}
    active = []   # exit_ts listesi
    for ent, ext, net in events:
        active = [x for x in active if x > ent]
        if len(active) >= LSX_MAXCON: continue
        active.append(ext)
        day = str(ext)[:10]
        daily[day] = daily.get(day, 0.0) + LSX_F * net
    s = pd.Series(daily).sort_index()
    return s


def stats(r, lbl):
    r = r.fillna(0.0)
    nav = (1 + r).cumprod(); peak = nav.cummax()
    mdd = ((nav - peak) / peak).min() * 100
    yrs = len(r) / 365.0
    cagr = (nav.iloc[-1] ** (1 / yrs) - 1) * 100 if yrs > 0 else 0
    sh = r.mean() / (r.std() + 1e-12) * np.sqrt(365)
    print("  %-18s CAGR %+7.0f%% · MaxDD %6.1f%% · Sharpe %+5.2f · final($100→) $%.0f" % (
        lbl, cagr, mdd, sh, 100 * nav.iloc[-1]))
    return nav


def main():
    print("lam kolu (Sprint, %s+)..." % WIN_START)
    dfs = load_with_micro(); coins = build_entries(dfs); tl = build_timeline(coins)
    rl = lam_daily(coins, tl)
    print("lsx kolu...")
    rx = lsx_daily()
    idx = rl.index.union(rx.index).sort_values()
    idx = idx[idx >= WIN_START]
    rl = rl.reindex(idx).fillna(0.0); rx = rx.reindex(idx).fillna(0.0)
    combo = 0.5 * rl + 0.5 * rx
    print("=" * 86)
    print("  ENSEMBLE ($100, ortak pencere %s → bugün, günlük seriler)" % WIN_START)
    print("=" * 86)
    stats(rl, "lam (Sprint)")
    stats(rx, "lsx (kontraryan)")
    stats(combo, "ENSEMBLE 50/50")
    corr = rl.corr(rx)
    print("-" * 86)
    print("  günlük korelasyon lam↔lsx: %+.3f  (≈0 = gerçek dekorelasyon → DD düşer)" % corr)
    print("=" * 86)


if __name__ == "__main__":
    main()
