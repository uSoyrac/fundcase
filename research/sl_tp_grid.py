#!/usr/bin/env python3
"""sl_tp_grid.py — trade-uzmanı #1: SL-genişliği × TP ızgarası (HİÇ test edilmemiş kaldıraç).
SL genişliği cost-in-R'yi + WR'yi + R-geometriyi aynı anda etkiler. İki kesit:
  R-anchored : tp = TP_R × SL_ATR × ATR  (sabit R-katı)
  PRICE-anchored: tp = k × ATR (SL'den BAĞIMSIZ) → SL seçimini TEMİZ izole eder (uzman önerisi).
lam-gate'li (yükselen) girişler, 43 coin, net maliyet, avgR/WR/OOS/MaxDD. Baz: SL2.0/TP2.5."""
import numpy as np, pandas as pd
from signal_lab import atr, RT_COST_PRICE
from falsify import load_with_micro, breakout_pos, _features

LAM_MIN, LAM_EXEMPT = 1.0, 2.2


def collect_entries(dfs):
    E = []
    for c, df in dfs.items():
        O = df["open"].to_numpy(float); H = df["high"].to_numpy(float)
        L = df["low"].to_numpy(float); C = df["close"].to_numpy(float)
        A = atr(df, 14); idx = df.index
        f = _features(df); lam = f["lam"]; vr = f["vr"]
        pos = breakout_pos(df, 20)
        for i in np.where(pos != 0)[0]:
            if i + 1 >= len(C) or lam[i] <= LAM_MIN or lam[i] <= lam[i - 1]: continue
            fresh = (vr[i] < 1.0) if np.isfinite(vr[i]) else False
            if not (fresh or lam[i] >= LAM_EXEMPT): continue
            E.append((O, H, L, C, int(i), int(pos[i]), A[i], str(idx[min(i + 1, len(idx) - 1)])))
    return E


def walk(O, H, L, C, i, d, atr_i, sl_atr, tp_r=None, tp_k=None):
    n = len(C); entry = O[i + 1]; risk = sl_atr * (atr_i if atr_i > 0 else entry * 0.01)
    sl = entry - d * risk
    tp = entry + d * (tp_r * risk if tp_r is not None else tp_k * atr_i)
    sld = risk / entry; j = i + 1; ex = None
    while j < n:
        if d == 1:
            if L[j] <= sl: ex = sl; break
            if H[j] >= tp: ex = tp; break
        else:
            if H[j] >= sl: ex = sl; break
            if L[j] <= tp: ex = tp; break
        j += 1
    if ex is None: ex = C[n - 1]
    return (d * (ex - entry) / entry) / sld - RT_COST_PRICE / sld


def run(E, **kw):
    rows = [(walk(*e[:7], **kw), e[7]) for e in E]
    r = np.array([x[0] for x in rows]); ts = [x[1] for x in rows]
    order = np.argsort(ts); r = r[order]
    split = int(len(r) * 0.6)
    # sequential pooled MaxDD (R equity)
    eq = np.cumsum(r); peak = np.maximum.accumulate(eq); dd = (eq - peak)
    return r.mean(), 100 * (r > 0).mean(), r[split:].mean(), dd.min()


def main():
    print("Veri + girişler..."); dfs = load_with_micro(); E = collect_entries(dfs)
    print("  lam-gate'li giriş: %d" % len(E))
    b_avg, b_wr, b_oos, b_dd = run(E, sl_atr=2.0, tp_r=2.5)
    print("  BAZ (SL2.0/TP2.5R): avgR %+.3f WR %.1f%% OOS %+.3f maxDD(R) %.1f" % (b_avg, b_wr, b_oos, b_dd))

    print("\n=== R-ANCHORED ızgara (tp = TP_R × SL_ATR × ATR) — avgR / OOS ===")
    print("  %-8s" % "SL\\TP" + "".join("%12s" % ("%.1fR" % t) for t in [1.5, 2.0, 2.5, 3.0, 4.0]))
    for sl in [1.5, 2.0, 2.5, 3.0]:
        cells = []
        for tp in [1.5, 2.0, 2.5, 3.0, 4.0]:
            a, w, o, dd = run(E, sl_atr=sl, tp_r=tp)
            cells.append("%+.3f/%+.2f" % (a, o))
        print("  %-8s" % ("%.1f" % sl) + "".join("%12s" % c for c in cells))

    print("\n=== PRICE-ANCHORED ızgara (tp = k×ATR, SL'den bağımsız) — SL'i izole eder ===")
    print("  %-8s" % "SL\\k" + "".join("%13s" % ("%dATR" % k) for k in [3, 4, 5, 6, 7]))
    best = (b_oos, "BAZ")
    for sl in [1.5, 2.0, 2.5, 3.0]:
        cells = []
        for k in [3, 4, 5, 6, 7]:
            a, w, o, dd = run(E, sl_atr=sl, tp_k=k)
            cells.append("%+.3f/%+.2f" % (a, o))
            if o > best[0]: best = (o, "SL%.1f/k%dATR (avgR%+.3f WR%.0f DD%.0f)" % (sl, k, a, w, dd))
        print("  %-8s" % ("%.1f" % sl) + "".join("%13s" % c for c in cells))
    print("\n  hücre = avgR / OOS-avgR · BAZ OOS %+.3f" % b_oos)
    print("  EN İYİ OOS:", best[1], "→ OOS %+.3f" % best[0])
    print("=" * 80)


if __name__ == "__main__":
    main()
