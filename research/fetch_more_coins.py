#!/usr/bin/env python3
"""fetch_more_coins.py — Binance perp'ten 20 EK coin tarihsel 4H veri (breadth testi için).
mktdata/{SYM}_4h.csv + microdata/{SYM}_micro.csv yazar (mevcut formatla aynı). Paginated."""
import time, json, os
import pandas as pd
try:
    import requests
    def get(url, p): return requests.get(url, params=p, timeout=20).json()
except ImportError:
    import urllib.request, urllib.parse
    def get(url, p):
        with urllib.request.urlopen(f"{url}?{urllib.parse.urlencode(p)}", timeout=20) as r:
            return json.loads(r.read().decode())

FAPI = "https://fapi.binance.com/fapi/v1/klines"
# HyroTrader/Bybit'te de işlem gören, köklü, çok-yıllık likit perp'ler (mevcut 20 dışında)
NEW = ["TRX", "MATIC", "AAVE", "MKR", "ALGO", "EOS", "XLM", "SAND", "MANA", "GRT",
       "CRV", "RUNE", "GALA", "IMX", "DYDX", "CHZ", "COMP", "SNX", "AXS", "ENJ",
       "ZIL", "1INCH", "SUSHI", "ICP"]   # 24 aday → likit+geçmişi olanlar tutar
START_2021 = int(pd.Timestamp("2021-01-01").timestamp() * 1000)


def fetch_full(sym):
    rows = []; end = None
    for _ in range(10):                       # max 10 sayfa × 1500 = ~17k bar
        p = {"symbol": sym + "USDT", "interval": "4h", "limit": 1500}
        if end: p["endTime"] = end
        try:
            data = get(FAPI, p)
        except Exception as e:
            print(f"  {sym}: hata {e}"); break
        if not isinstance(data, list) or not data:
            break
        rows = data + rows
        earliest = data[0][0]
        if len(data) < 1500 or earliest <= START_2021:
            break
        end = earliest - 1
        time.sleep(0.25)
    return rows


def main():
    os.makedirs("mktdata", exist_ok=True); os.makedirs("microdata", exist_ok=True)
    ok = []
    for sym in NEW:
        if os.path.exists(f"mktdata/{sym}_USDT_4h.csv"):
            ok.append(sym); print(f"  {sym}: zaten var, atla"); continue
        raw = fetch_full(sym)
        if len(raw) < 2000:                   # yetersiz geçmiş → atla
            print(f"  {sym}: yetersiz ({len(raw)} bar), atlandı"); continue
        seen = set(); mk = []; mc = []
        for k in raw:
            ot = int(k[0])
            if ot in seen: continue
            seen.add(ot)
            ts = pd.to_datetime(ot, unit="ms")
            vol = float(k[5]); tbb = float(k[9])
            mk.append((ts, float(k[1]), float(k[2]), float(k[3]), float(k[4]), vol))
            mc.append((ts, float(k[8]), (tbb / vol) if vol > 0 else 0.5))
        dfm = pd.DataFrame(mk, columns=["ts", "open", "high", "low", "close", "volume"]).sort_values("ts")
        dfc = pd.DataFrame(mc, columns=["ts", "num_trades", "taker_buy_ratio"]).sort_values("ts")
        dfm.to_csv(f"mktdata/{sym}_USDT_4h.csv", index=False)
        dfc.to_csv(f"microdata/{sym}_micro.csv", index=False)
        ok.append(sym)
        print(f"  {sym}: {len(dfm)} bar ({dfm.ts.iloc[0].date()} → {dfm.ts.iloc[-1].date()}) ✓")
    print(f"\nTOPLAM eklenen: {len(ok)} coin → {ok}")


if __name__ == "__main__":
    main()
