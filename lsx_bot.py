#!/usr/bin/env python3
"""🟠 lsx_bot.py — ③ ENSEMBLE'ın lsx KOLU (positioning kontraryan, PAPER).
DOĞRULANMIŞ (lsx_selective.py): |lsx|>=1.2 (≈%80 kalabalık) kontraryan + 24h hold
→ WR %52, net +%0.55/işlem (OOS +%0.95), lam'a dekorele (korr +0.17) → ensemble DD yarıya.
Kural: lsx = -(long_frac-0.5)*4, Binance globalLongShortAccountRatio(4h). |lsx|>=1.2 →
yön=sign(lsx) (aşırı-long=SHORT), notional %10/işlem, max 8 eşzamanlı, coin-başına tek poz,
24h (6 bar) hold sonra kapat. Maliyet %0.14 round-trip. Python 3.6 uyumlu, cron --once."""
import json, os, sys, time
from datetime import datetime, timezone, timedelta

try:
    import requests
    def get(url, params):
        return requests.get(url, params=params, timeout=15).json()
except ImportError:
    import urllib.request, urllib.parse
    def get(url, params):
        u = url + "?" + urllib.parse.urlencode(params)
        with urllib.request.urlopen(u, timeout=15) as r:
            return json.loads(r.read().decode())

FAPI = "https://fapi.binance.com"
COINS = ["ADA", "APT", "ARB", "ATOM", "AVAX", "BNB", "BTC", "DOGE", "DOT", "ETC",
         "ETH", "FIL", "INJ", "LINK", "LTC", "NEAR", "OP", "SOL", "UNI", "XRP"]
THR, NOTIONAL_F, MAX_CON, HOLD_H, COST = 1.2, 0.10, 8, 24, 0.0014
HERE = os.path.dirname(os.path.abspath(__file__))
STATE = os.path.join(HERE, "lsx_state.json")
TRADES = os.path.join(HERE, "lsx_trades.jsonl")
LOG = os.path.join(HERE, "lsx_log.txt")


def now_utc():
    return datetime.now(timezone.utc)


def log(msg):
    line = "[%s] LSX: %s" % (now_utc().strftime("%Y-%m-%d %H:%M"), msg)
    print(line)
    with open(LOG, "a") as f:
        f.write(line + "\n")


def load_state(equity0):
    if os.path.exists(STATE):
        return json.load(open(STATE))
    return {"equity": equity0, "vault": 0.0, "risk": {"start": equity0},
            "positions": {}, "closed": [], "passed": False}


def save_state(st):
    with open(STATE, "w") as f:
        json.dump(st, f, ensure_ascii=False, indent=1)


def price(sym):
    try:
        d = get(FAPI + "/fapi/v1/ticker/price", {"symbol": sym})
        return float(d["price"])
    except Exception:
        return None


def lsx_score(sym):
    try:
        d = get(FAPI + "/futures/data/globalLongShortAccountRatio",
                {"symbol": sym, "period": "4h", "limit": 1})
        lsr = float(d[-1]["longShortRatio"])
        lf = lsr / (1.0 + lsr)
        return -(lf - 0.5) * 4.0, lf
    except Exception:
        return None, None


def run_once(equity0):
    st = load_state(equity0)
    now = now_utc()
    # 1) süresi dolan pozisyonları kapat (24h hold)
    for sym in list(st["positions"].keys()):
        p = st["positions"][sym]
        due = datetime.strptime(p["exit_due"], "%Y-%m-%dT%H:%M") .replace(tzinfo=timezone.utc)
        if now < due:
            continue
        px = price(sym)
        if px is None:
            continue
        net = p["direction"] * (px / p["entry"] - 1.0) - COST
        pnl = p["notional"] * net
        st["equity"] += pnl
        rec = {"sym": sym, "yon": "LONG" if p["direction"] == 1 else "SHORT",
               "entry": p["entry"], "exit": px, "net_pct": round(net * 100, 3),
               "pnl": round(pnl, 4), "opened": p["opened"],
               "closed": now.strftime("%Y-%m-%dT%H:%M"), "equity": round(st["equity"], 2),
               "reason": p["reason"] + " → 24h hold doldu"}
        st["closed"].append(rec)
        with open(TRADES, "a") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        log("KAPAT %s %s net %+.2f%% pnl %+.2f$ → eq %.2f" % (
            sym, rec["yon"], net * 100, pnl, st["equity"]))
        del st["positions"][sym]
        time.sleep(0.3)
    # 2) yeni sinyaller: |lsx| >= 1.2, coin-başına tek poz, max 8
    for c in COINS:
        sym = c + "USDT"
        if sym in st["positions"] or len(st["positions"]) >= MAX_CON:
            continue
        sc, lf = lsx_score(sym)
        time.sleep(0.25)
        if sc is None or abs(sc) < THR:
            continue
        px = price(sym)
        if px is None:
            continue
        d = 1 if sc > 0 else -1
        reason = "lsx=%+.2f (long%% %.0f aşırı-%s) → kontraryan %s" % (
            sc, lf * 100, "short" if d == 1 else "long", "LONG" if d == 1 else "SHORT")
        st["positions"][sym] = {
            "direction": d, "entry": px, "notional": round(st["equity"] * NOTIONAL_F, 4),
            "opened": now.strftime("%Y-%m-%dT%H:%M"),
            "exit_due": (now + timedelta(hours=HOLD_H)).strftime("%Y-%m-%dT%H:%M"),
            "lsx": round(sc, 3), "reason": reason}
        log("AÇ %s @%.6g · %s" % (sym, px, reason))
    save_state(st)
    log("döngü bitti · eq %.2f · açık %d" % (st["equity"], len(st["positions"])))


if __name__ == "__main__":
    eq = 1000.0
    if "--equity" in sys.argv:
        eq = float(sys.argv[sys.argv.index("--equity") + 1])
    run_once(eq)
