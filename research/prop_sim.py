#!/usr/bin/env python3
"""
prop_sim.py — UÇTAN-UCA PROP-CHALLENGE SİMÜLASYONU (compound, lam-Kelly sizing)
═══════════════════════════════════════════════════════════════════════════════
Doğrulanmış 3-adımlı edge'i compound_engine ile birleştirir:
  GİRİŞ : Donchian-20 breakout · lam>1 (Hawkes) · VR<1 (taze ateşleme, yüksek-lam muaf)
  SIZING: fractional-Kelly, conviction = lam → D10 (devasa kaskad) agresifleşir
  ÇIKIŞ : sabit 2.5R TP / −1R hard-SL (trail YOK — whipsaw'ı önler)
  RİSK  : compound_engine kill-switch (statik DD) + intraday-halt (−%3 acil fren)
  KASA  : CANLI equity üzerinden boyutlandır → geometrik büyüme (compound)

Firma profili: AGRESİF 1-STEP, STATİK drawdown (taban=başlangıç, zirveyi kovalamaz → kolay).
Portföy: tek kasa, 20 coin, kronolojik tek zaman-çizgisi, eşzamanlı-pozisyon tavanı (korelasyon).

Kullanım:  python prop_sim.py [başlangıç_$]   (varsayılan 10000; compound % ölçek-bağımsız)
"""
import sys, os
import numpy as np
import pandas as pd

from signal_lab import atr, RT_COST_PRICE
from falsify import load_with_micro, breakout_pos, _features
from compound_engine import kill_switch, intraday_halt   # SAĞLAM risk çekirdeği (aynı klasör)

# ── PROFİL & PARAMETRELER ────────────────────────────────────────────────────
FIRM = {"daily": 0.05, "total": 0.12, "trailing": False}   # statik −%12 taban, günlük −%5
TARGET = 0.10          # 1-step challenge hedefi: +%10 → funded
BASE_RISK = 0.004      # taban işlem-riski (lam=1'de)
MAX_RISK = 0.015       # işlem-başı risk tavanı (D10 kaskadında)
LAM_MIN = 1.0          # giriş eşiği (② edge)
LAM_EXEMPT = 2.2       # yüksek-lam: VR>1 olsa bile gir (balina istisnası, ② doğrulandı)
INTRADAY_HALT = 0.03   # gün-içi −%3 → o gün dur (EOD-uçurum emniyeti)
MAX_POS = 8            # eşzamanlı pozisyon tavanı (korelasyon riskini ehlileştir)
SL_ATR, TP_R = 2.0, 2.5


def conviction_risk(lam, base_risk=BASE_RISK, max_risk=MAX_RISK):
    """lam-conviction → işlem-riski. D10 (yüksek lam) agresifleşir, tavanlı (fractional-Kelly ruhu)."""
    mult = np.clip(lam, 1.0, 3.0)                 # lam 1→3 arası ölçek
    return float(np.clip(base_risk * mult, 0.0, max_risk))


def build_entries(dfs):
    """Her coin için: bar dizileri + giriş-execution barları (i+1) ve sl/tp/lam/yön."""
    coins = {}
    for c, df in dfs.items():
        O = df["open"].to_numpy(float); H = df["high"].to_numpy(float)
        L = df["low"].to_numpy(float); C = df["close"].to_numpy(float)
        A = atr(df, 14); ts = df.index.to_numpy()
        f = _features(df); lam = f["lam"]; vr = f["vr"]
        pos = breakout_pos(df, 20)
        entries = {}   # exec_bar j -> (d, entry, sl, tp, lam)
        for i in np.where(pos != 0)[0]:
            if i + 1 >= len(C): continue
            d = int(pos[i])
            if lam[i] <= LAM_MIN: continue
            fresh = (vr[i] < 1.0) if np.isfinite(vr[i]) else False
            if not (fresh or lam[i] >= LAM_EXEMPT): continue     # VR<1 ya da yüksek-lam muaf
            entry = O[i + 1]; risk = SL_ATR * (A[i] if A[i] > 0 else entry * 0.01)
            entries[i + 1] = (d, entry, entry - d * risk, entry + d * TP_R * risk, float(lam[i]))
        coins[c] = dict(O=O, H=H, L=L, C=C, ts=ts, entries=entries)
    return coins


def simulate(coins, start=10000.0, base_risk=BASE_RISK, max_risk=MAX_RISK, max_pos=MAX_POS,
             bank=False, bank_trigger=0.50, bank_split=0.50):
    # global kronolojik zaman-çizgisi: (ts, coin, bar_index)
    timeline = []
    for c, d in coins.items():
        for j in range(len(d["ts"])):
            timeline.append((d["ts"][j], c, j))
    timeline.sort(key=lambda x: x[0])

    equity = start; peak = start; max_dd = 0.0
    vault = 0.0; baseline = start          # kâr-bankalama (opsiyonel)
    day_start = start; cur_day = None; day_halted = False
    open_pos = {}                 # coin -> (d, entry, sl, tp, risk_amount)
    trades = []; eq_curve = []
    passed = False; passed_ts = None; failed = False; failed_ts = None
    min_eq = start
    t0 = timeline[0][0]; t1 = timeline[-1][0]

    for ts, c, j in timeline:
        if failed: break
        day = str(ts)[:10]
        if day != cur_day:
            cur_day = day; day_start = equity; day_halted = False
        cd = coins[c]; H = cd["H"][j]; L = cd["L"][j]

        # 1) açık pozisyonu güncelle (SL/TP gün-içi H/L ile)
        if c in open_pos:
            d, entry, sl, tp, ra = open_pos[c]
            exit_p = None
            if d == 1:
                if L <= sl: exit_p = sl
                elif H >= tp: exit_p = tp
            else:
                if H >= sl: exit_p = sl
                elif L <= tp: exit_p = tp
            if exit_p is not None:
                sl_dist = abs(entry - sl) / entry
                R = (d * (exit_p - entry) / entry) / sl_dist - RT_COST_PRICE / sl_dist
                equity += ra * R
                peak = max(peak, equity); min_eq = min(min_eq, equity)
                trades.append((str(ts), c, R, equity))
                del open_pos[c]
                # kapanış sonrası emniyet kontrolleri
                if intraday_halt(equity, day_start, INTRADAY_HALT): day_halted = True
                ks = kill_switch(equity, peak, day_start, FIRM)
                if ks and "TOPLAM" in ks: failed = True; failed_ts = str(ts)
                if equity <= start * (1 - FIRM["total"]): failed = True; failed_ts = str(ts)

        # 2) hedef/iflas
        if not passed and equity >= start * (1 + TARGET):
            passed = True; passed_ts = str(ts)
        # running peak-to-trough drawdown (GERÇEK risk ölçüsü)
        peak = max(peak, equity); min_eq = min(min_eq, equity)
        if peak > 0: max_dd = max(max_dd, (peak - equity) / peak)

        if failed:
            eq_curve.append((str(ts), equity)); continue

        # opsiyonel kâr-bankalama: yüksek-su üstünü korunaklı kasaya çek (giveback'i sınırla)
        if bank and equity >= baseline * (1 + bank_trigger):
            harvest = (equity - baseline) * bank_split
            vault += harvest; equity -= harvest; baseline = equity; peak = equity

        # 3) yeni giriş?
        if (j in cd["entries"]) and (c not in open_pos) and (not day_halted) and len(open_pos) < max_pos:
            if intraday_halt(equity, day_start, INTRADAY_HALT):
                day_halted = True
            elif kill_switch(equity, peak, day_start, FIRM):
                day_halted = True
            else:
                d, entry, sl, tp, lam = cd["entries"][j]
                ra = equity * conviction_risk(lam, base_risk, max_risk)   # CANLI equity → compound
                open_pos[c] = (d, entry, sl, tp, ra)
        eq_curve.append((str(ts), equity))

    yrs = (pd.Timestamp(t1) - pd.Timestamp(t0)).days / 365.25
    return dict(equity=equity + vault, book=equity, vault=vault, peak=peak, min_eq=min_eq,
                max_dd=max_dd * 100, trades=trades, eq_curve=eq_curve, passed=passed,
                passed_ts=passed_ts, failed=failed, failed_ts=failed_ts, start=start, yrs=yrs)


def report(r):
    start = r["start"]; eq = r["equity"]; tr = r["trades"]
    R = np.array([t[2] for t in tr]) if tr else np.array([0.0])
    n = len(tr); yrs = r["yrs"]
    cagr = ((eq / start) ** (1 / max(yrs, 0.1)) - 1) * 100
    maxdd = r["max_dd"]
    static_dd = (1 - r["min_eq"] / start) * 100
    print("=" * 92)
    print(f"  UÇTAN-UCA PROP SİM  ·  başlangıç ${start:,.0f}  ·  firma: statik −%{FIRM['total']*100:.0f} / günlük −%{FIRM['daily']*100:.0f}  ·  hedef +%{TARGET*100:.0f}")
    print("=" * 92)
    print(f"  Final equity   : ${eq:,.0f}   ({(eq/start-1)*100:+.1f}%)   ·   CAGR ≈ %{cagr:.0f}")
    print(f"  İşlem          : {n}   WR %{100*(R>0).mean():.1f}   avgR {R.mean():+.3f}   PF {R[R>0].sum()/abs(R[R<=0].sum()):.2f}" if (R<=0).any() else "")
    print(f"  Max DD (zirveden): %{maxdd:.1f}    ·    Max DD (statik/başlangıçtan): %{static_dd:.1f}")
    print(f"  CHALLENGE +%{TARGET*100:.0f}: {'GEÇTİ ✅ @ '+r['passed_ts'][:10] if r['passed'] else 'GEÇİLEMEDİ ❌'}"
          f"   ·   İFLAS: {'EVET ✗ @ '+r['failed_ts'][:10] if r['failed'] else 'HAYIR ✓ (taban korundu)'}")
    # geometrik büyüme: yıllık snapshot
    print("\n  GEOMETRİK BÜYÜME (yıl-sonu equity):")
    cur = None
    for ts, e in r["eq_curve"]:
        y = ts[:4]
        if y != cur:
            cur = y
            print(f"    {ts[:10]}   ${e:>12,.0f}   ({(e/start-1)*100:+.0f}%)")
    print(f"    {r['eq_curve'][-1][0][:10]}   ${r['eq_curve'][-1][1]:>12,.0f}   (SON)")
    print("=" * 92)


def sweep(coins, start):
    print("\n" + "=" * 92)
    print("  RİSK TARAMASI — hayatta-kalınabilir nokta (tavanlı MDD ararken büyümeyi koru)")
    print("=" * 92)
    print(f"  {'base%':>6}{'maxR%':>6}{'maxPoz':>7}{'bank':>6}{'final$':>14}{'CAGR%':>7}{'MaxDD%':>8}{'iflas':>7}")
    grid = [
        (0.004, 0.015, 8, False), (0.0025, 0.010, 8, False), (0.0015, 0.006, 6, False),
        (0.001, 0.004, 5, False), (0.004, 0.015, 8, True), (0.0025, 0.010, 6, True),
    ]
    for br, mr, mp, bk in grid:
        r = simulate(coins, start=start, base_risk=br, max_risk=mr, max_pos=mp, bank=bk)
        cagr = ((r["equity"] / start) ** (1 / max(r["yrs"], 0.1)) - 1) * 100
        print(f"  {br*100:>6.2f}{mr*100:>6.1f}{mp:>7}{('EVET' if bk else '—'):>6}"
              f"{r['equity']:>14,.0f}{cagr:>7.0f}{r['max_dd']:>8.1f}{('✗' if r['failed'] else '✓'):>7}")
    print("=" * 92)


if __name__ == "__main__":
    start = float(sys.argv[1]) if len(sys.argv) > 1 else 10000.0
    print("Veri + feature (lam/VR) hesaplanıyor...")
    dfs = load_with_micro()
    coins = build_entries(dfs)
    res = simulate(coins, start=start)
    report(res)
    sweep(coins, start)
