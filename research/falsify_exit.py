#!/usr/bin/env python3
"""falsify_exit.py — ADIM ③: BALİSTİK İVME-SÖNÜMÜ (Drag-Decay) ÇIKIŞ MOTORU.
Tez (kinetik uzmanı): traili ÖLÇÜLEN yavaşlamanın fonksiyonu yap → ivme≥0 iken geniş (sür),
ivme ölünce dar (tepeye klampla). Metrik: peak-capture = gerçekleşen / MFE (tepenin %kaçı).
Aynı lam-kapılı girişlerde çıkış-kuralı yarışı: sabit-TP vs ATR-chandelier vs drag-decay."""
import numpy as np
import pandas as pd
from signal_lab import atr, ema, RT_COST_PRICE, BARS_PER_YEAR
from falsify import load_with_micro, breakout_pos, _features

SL_ATR = 2.0
MAXBARS = 120   # çıkış simülasyonu üst sınırı


def _run_trade(O, H, L, C, A, vel, acc, jrk, drag, grav, i, d, rule):
    """i+1 açılışında gir, çıkış-kuralına göre yürü. Döner: (R, MFE_R, bars)."""
    n = len(C)
    entry = O[i + 1]
    a0 = A[i] if A[i] > 0 else entry * 0.01
    risk = SL_ATR * a0
    sl_dist = risk / entry
    hard_sl = entry - d * risk
    trail = hard_sl
    run_extreme = entry
    mfe = 0.0
    j = i + 1
    exit_p = None
    while j < n and (j - i) <= MAXBARS:
        hi, lo = H[j], L[j]
        # MFE (lehte max hareket, R cinsinden)
        fav = d * (hi - entry) / entry if d == 1 else d * (lo - entry) / entry  # not: short için ters
        fav = (d * ((hi if d == 1 else lo) - entry)) / entry
        mfe = max(mfe, fav / sl_dist)
        # run-extreme (chandelier çapası)
        run_extreme = max(run_extreme, hi) if d == 1 else min(run_extreme, lo)

        if rule == "fixed_tp":
            tp = entry + d * 2.5 * risk
            if d == 1:
                if lo <= hard_sl: exit_p = hard_sl; break
                if hi >= tp: exit_p = tp; break
            else:
                if hi >= hard_sl: exit_p = hard_sl; break
                if lo <= tp: exit_p = tp; break

        elif rule == "chandelier":
            m = 3.0
            new_stop = run_extreme - d * m * A[j]
            trail = max(trail, new_stop) if d == 1 else min(trail, new_stop) if trail != hard_sl else new_stop
            if d == 1 and lo <= trail: exit_p = trail; break
            if d == -1 and hi >= trail: exit_p = trail; break

        elif rule == "drag_decay":
            # ölçülen yavaşlama [0,1]: ivme<0, jerk<0, drag↑, gravity↑ → decel↑
            def sg(x, s=1.0):
                return 1.0 / (1.0 + np.exp(x / s)) if np.isfinite(x) else 0.5
            decel = np.clip(0.25*sg(acc[j], 0.005) + 0.25*sg(jrk[j], 0.005)
                            + 0.25*np.clip(drag[j], 0, 1) + 0.25*np.clip(grav[j], 0, 1), 0, 1)
            m = 4.0 - 3.0 * decel        # 4 ATR (sür) → 1 ATR (klampla)
            new_stop = run_extreme - d * m * A[j]
            trail = max(trail, new_stop) if d == 1 else (min(trail, new_stop) if trail != hard_sl else new_stop)
            if d == 1 and lo <= trail: exit_p = trail; break
            if d == -1 and hi >= trail: exit_p = trail; break

        elif rule == "hold20":
            if (j - (i + 1)) >= 20: exit_p = O[min(j+1, n-1)]; break
            if d == 1 and lo <= hard_sl: exit_p = hard_sl; break
            if d == -1 and hi >= hard_sl: exit_p = hard_sl; break
        j += 1
    if exit_p is None:
        exit_p = C[min(j, n - 1)]
    r_price = d * (exit_p - entry) / entry
    r = r_price / sl_dist - RT_COST_PRICE / sl_dist
    return float(r), float(mfe), int(j - i)


def main():
    print("=" * 96)
    print("  ADIM ③ — BALİSTİK DRAG-DECAY ÇIKIŞ (aynı lam-kapılı girişlerde çıkış yarışı)")
    print("  Metrik: avgR · peak-capture (gerçekleşen/MFE) · MFE-bırakılan")
    print("=" * 96)
    dfs = load_with_micro()
    rules = ["fixed_tp", "chandelier", "drag_decay", "hold20"]
    agg = {r: {"R": [], "mfe": [], "yr": []} for r in rules}

    for c, df in dfs.items():
        O = df["open"].to_numpy(float); H = df["high"].to_numpy(float)
        Lr = df["low"].to_numpy(float); Cc = df["close"].to_numpy(float)
        A = atr(df, 14); idx = df.index
        f = _features(df)
        lam = f["lam"]
        # kinetik alanlar
        r = pd.Series(np.diff(np.log(Cc), prepend=np.log(Cc[0])))
        vel = ema(r.to_numpy(), 3)
        acc = np.diff(vel, prepend=vel[0])
        jrk = np.diff(acc, prepend=acc[0])
        er = f["er"]
        vol = df["volume"].to_numpy(float)
        volmed = pd.Series(vol).rolling(60).median().to_numpy()
        drag = (vol / (volmed + 1e-9)) * (1 - np.clip(er, 0, 1))
        # gravity: funding yok → 0 (ileride funddata eklenir)
        grav = np.zeros(len(Cc))
        pos = breakout_pos(df, 20)
        bi = np.where(pos != 0)[0]
        for i in bi:
            if lam[i] <= 1.0 or i + 1 >= len(Cc):   # lam-kapılı giriş (② edge)
                continue
            for rule in rules:
                R, mfe, bars = _run_trade(O, H, Lr, Cc, A, vel, acc, jrk, drag, grav, i, int(pos[i]), rule)
                agg[rule]["R"].append(R); agg[rule]["mfe"].append(mfe)
                agg[rule]["yr"].append(str(idx[min(i+1, len(idx)-1)])[:4])

    print(f"\n  {'çıkış-kuralı':<14}{'N':>7}{'avgR':>9}{'WR%':>7}{'PF':>7}{'peak-cap':>11}{'medMFE':>9}")
    for rule in rules:
        R = np.array(agg[rule]["R"]); mfe = np.array(agg[rule]["mfe"])
        wins = R[R > 0]; loss = R[R <= 0]
        pf = wins.sum() / abs(loss.sum()) if loss.sum() != 0 else float("inf")
        # peak-capture: sadece MFE>0 olanlarda gerçekleşen/MFE
        valid = mfe > 0.05
        pcap = np.clip(R[valid] / mfe[valid], -1, 1).mean()
        print(f"  {rule:<14}{len(R):>7}{R.mean():>+9.4f}{100*(R>0).mean():>7.1f}{pf:>7.2f}"
              f"{pcap:>11.2f}{np.median(mfe):>9.2f}")

    # yıl-yıl avgR (çıkış kuralı rejim-sağlam mı?)
    print("\n  YIL-YIL avgR (çıkış kuralı):")
    yrs = sorted(set(agg["fixed_tp"]["yr"]))
    print(f"    {'kural':<14}" + "".join(f"{y:>9}" for y in yrs))
    for rule in rules:
        d = pd.DataFrame({"R": agg[rule]["R"], "yr": agg[rule]["yr"]})
        cells = [f"{d[d.yr==y]['R'].mean():+.3f}" if (d.yr==y).sum()>20 else "·" for y in yrs]
        print(f"    {rule:<14}" + "".join(f"{x:>9}" for x in cells))
    print("=" * 96)


if __name__ == "__main__":
    main()
