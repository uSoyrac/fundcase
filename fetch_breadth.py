#!/usr/bin/env python3
"""fetch_breadth.py — GENİŞLİK kaldıracı: 486 yeni Binance USDT perp için 4H veri.
Hız = işlem-akışı × avgR × risk; risk yasak (blow), GENİŞLİK serbest. lam edge'i 23 yeni
coine genelleşmişti (+0.890) → tüm evrene aç. Filtre: ≥3000 bar (~1.4y, OOS payı) +
medyan günlük quote-hacim ≥ $3M (likidite/maliyet). → mktdata_breadth/ + microdata_breadth/"""
import time, json, os
import pandas as pd
try:
    import requests
    def get(u, p): return requests.get(u, params=p, timeout=20).json()
except ImportError:
    import urllib.request, urllib.parse
    def get(u, p):
        with urllib.request.urlopen("%s?%s" % (u, urllib.parse.urlencode(p)), timeout=20) as r:
            return json.loads(r.read().decode())

FAPI = "https://fapi.binance.com/fapi/v1/klines"
START = int(pd.Timestamp("2020-06-01").timestamp() * 1000)
MIN_BARS = 3000          # ~1.4y → OOS payı kalsın
MIN_QVOL = 3e6           # medyan günlük quote hacim $3M (maliyet gerçekçiliği)


def fetch(sym):
    rows = []; end = None
    for _ in range(12):
        p = {"symbol": sym, "interval": "4h", "limit": 1500}
        if end: p["endTime"] = end
        try:
            d = get(FAPI, p)
        except Exception:
            time.sleep(1); continue
        if not isinstance(d, list) or not d: break
        rows = d + rows
        if len(d) < 1500 or d[0][0] <= START: break
        end = d[0][0] - 1; time.sleep(0.12)
    return [r for r in rows if r[0] >= START]


def main():
    os.makedirs("mktdata_breadth", exist_ok=True); os.makedirs("microdata_breadth", exist_ok=True)
    syms = [s.strip() for s in open("/tmp/new_perps.txt") if s.strip()]
    ok = skip_hist = skip_liq = 0
    for i, sym in enumerate(syms):
        c = sym.replace("USDT", "")
        f_mk = "mktdata_breadth/%s_USDT_4h.csv" % c
        if os.path.exists(f_mk):
            ok += 1; continue
        raw = fetch(sym)
        if len(raw) < MIN_BARS:
            skip_hist += 1; continue
        qvols = [float(k[7]) for k in raw[-180 * 6:]]          # son ~180 gün quote hacim
        s = pd.Series(qvols)
        if s.groupby(s.index // 6).sum().median() < MIN_QVOL:  # günlük medyan
            skip_liq += 1; continue
        seen = set(); mk = []; mc = []
        for k in raw:
            ot = int(k[0])
            if ot in seen: continue
            seen.add(ot); ts = pd.to_datetime(ot, unit="ms"); vol = float(k[5]); tbb = float(k[9])
            mk.append((ts, float(k[1]), float(k[2]), float(k[3]), float(k[4]), vol))
            mc.append((ts, float(k[8]), (tbb / vol) if vol > 0 else 0.5))
        pd.DataFrame(mk, columns=["ts", "open", "high", "low", "close", "volume"]).to_csv(f_mk, index=False)
        pd.DataFrame(mc, columns=["ts", "num_trades", "taker_buy_ratio"]).to_csv("microdata_breadth/%s_micro.csv" % c, index=False)
        ok += 1
        if ok % 25 == 0:
            print("...%d kabul / %d kısa-tarih / %d likidite-red (i=%d/%d)" % (ok, skip_hist, skip_liq, i + 1, len(syms)), flush=True)
    print("BİTTİ: %d yeni coin kabul · %d kısa-tarih · %d düşük-likidite" % (ok, skip_hist, skip_liq))


if __name__ == "__main__":
    main()
