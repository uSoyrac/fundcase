#!/usr/bin/env python3
"""fetch_1h.py — 43 coin için 1H veri (frekans/cost-wall testi). mktdata_1h/ + microdata_1h/.
~2024-01'den (dose-response + 2025-26 OOS için yeter). fetch_more_coins ile aynı paginated mantık."""
import time, json, os, glob
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
START = int(pd.Timestamp("2024-01-01").timestamp() * 1000)
COINS = sorted({os.path.basename(f).split("_")[0] for f in glob.glob("mktdata/*_4h.csv")})


def fetch(sym):
    rows = []; end = None
    for _ in range(30):
        p = {"symbol": sym + "USDT", "interval": "1h", "limit": 1500}
        if end: p["endTime"] = end
        try:
            d = get(FAPI, p)
        except Exception:
            time.sleep(1); continue
        if not isinstance(d, list) or not d: break
        rows = d + rows
        if len(d) < 1500 or d[0][0] <= START: break
        end = d[0][0] - 1; time.sleep(0.2)
    return [r for r in rows if r[0] >= START]


def main():
    os.makedirs("mktdata_1h", exist_ok=True); os.makedirs("microdata_1h", exist_ok=True)
    ok = 0
    for c in COINS:
        if os.path.exists("mktdata_1h/%s_USDT_1h.csv" % c):
            ok += 1; continue
        raw = fetch(c)
        if len(raw) < 3000: print("  %s atla (%d)" % (c, len(raw))); continue
        seen = set(); mk = []; mc = []
        for k in raw:
            ot = int(k[0])
            if ot in seen: continue
            seen.add(ot); ts = pd.to_datetime(ot, unit="ms"); vol = float(k[5]); tbb = float(k[9])
            mk.append((ts, float(k[1]), float(k[2]), float(k[3]), float(k[4]), vol))
            mc.append((ts, float(k[8]), (tbb / vol) if vol > 0 else 0.5))
        pd.DataFrame(mk, columns=["ts", "open", "high", "low", "close", "volume"]).to_csv("mktdata_1h/%s_USDT_1h.csv" % c, index=False)
        pd.DataFrame(mc, columns=["ts", "num_trades", "taker_buy_ratio"]).to_csv("microdata_1h/%s_micro.csv" % c, index=False)
        ok += 1
    print("1H veri: %d coin" % ok)


if __name__ == "__main__":
    main()
