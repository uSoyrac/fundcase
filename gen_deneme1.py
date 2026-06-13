#!/usr/bin/env python3
"""gen_deneme1.py — FON botlarını deneme1 dashboard'ına (https://deneme1.../) yansıt.
Amaç: TÜM botların her kararını (işlem tablosu + gerekçe + açık pozisyonlar) deneme
domaininde de görmek. ~/uploads/tirad/<bot>_state.json → ~/uploads/deneme1_state/fon_*.json
(root cron /deneme1/state'e kopyalar). deneme1 şeması: key/title/desc/start_eq/nav/
nav_hist[{ts,v}]/trades[{coin,side,entry_px,exit_px,margin,usd,lev,pnl_pct,pnl_usd,
fund_pct,fee_usd,entry_ts,exit_ts,reason}]/positions[{sym,coin,side,entry_px,last_px,
entry_ts,weight,reason,lev,margin,usd}]. Python 3.6 uyumlu, saf stdlib."""
import json, os, glob
from datetime import datetime, timezone

SRC = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(os.path.dirname(SRC), "deneme1_state")
NOW = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
BOTS = [
    ("sprint",          "🔴 FON · Sprint (lam)",      "kendi-sermaye agresif · lam yükselen-kaskad · TP3R"),
    ("prop_eval",       "🔵 FON · Eval (lam)",        "HyroTrader sınav · base %0.15 · +%10"),
    ("prop_eval_fast",  "🟡 FON · Eval-Fast (lam)",   "hızlı sınav · base %0.25 · +%10"),
    ("prop_funded",     "🟢 FON · Funded (lam)",      "funded hasat · base %0.08 · +%5 çekim"),
    ("lsx",             "🟠 FON · LSX (positioning)", "aşırı-positioning kontraryan · |lsx|≥1.2 · 24h hold"),
    ("ensemble_eval",   "🎖️ TIRAD-4 KVARTET (4-edge)", "AMİRAL: 4 dekorele edge tek hesapta — lam(ateşleme)+lsx(positioning)+vwap(momentum)+regime · aile-cap+yön-netleme · MaxDD −6.3% · eval-pass ~%70 · gerçek 4/6"),
] + [("cohort_eval_acc%d" % i, "🟣 FON · Kohort-%d" % i,
      "fast-pass eval · lam≥2 + cushion→protect · 118-coin/16-slot") for i in range(1, 6)]


def jload(p):
    try:
        return json.load(open(p))
    except Exception:
        return None


def f(x, d=0.0):
    try:
        return float(x)
    except Exception:
        return d


def conv(st, key, title, desc):
    eq = f(st.get("equity"), 1000.0); vault = f(st.get("vault"))
    start = f((st.get("risk") or {}).get("start"), eq) or eq
    nav = eq + vault
    closed = st.get("closed") or []
    trades = []
    for t in closed[-400:]:
        pct = f(t.get("pct", t.get("net_pct")))
        usd = f(t.get("notional"), 0.0)
        if not usd and pct:
            usd = abs(f(t.get("pnl"))) / max(abs(pct) / 100.0, 1e-9)
        trades.append({
            "coin": str(t.get("sym", t.get("coin", "?"))).replace("USDT", "").replace("/", ""),
            "side": t.get("yon", t.get("side", "?")),
            "entry_px": f(t.get("entry")), "exit_px": f(t.get("exit")),
            "margin": round(usd, 2), "usd": round(usd, 2), "lev": 1,
            "pnl_pct": round(pct, 3), "pnl_usd": round(f(t.get("pnl")), 2),
            "fund_pct": 0.0, "fee_usd": round(f(t.get("fee")), 4),
            "entry_ts": str(t.get("opened", ""))[:16].replace("T", " "),
            "exit_ts": str(t.get("closed", ""))[:16].replace("T", " "),
            "reason": t.get("reason", "")})
    poss = []
    pdict = st.get("positions") or {}
    items = pdict.items() if isinstance(pdict, dict) else []
    for sym, p in items:
        coin = str(sym).replace("USDT", "")
        d = int(p.get("direction", 1))
        notional = f(p.get("notional"), eq * f(p.get("risk_pct"), 0.002) * 25)
        poss.append({
            "sym": "%s/USDT:USDT" % coin, "coin": coin, "side": d,
            "entry_px": f(p.get("entry")), "last_px": f(p.get("entry")),
            "entry_ts": str(p.get("opened", ""))[:16].replace("T", " "),
            "fund_cum": 0.0, "peak_r": 0.0,
            "weight": round(notional / max(eq, 1e-9), 4),
            "reason": p.get("reason", ""), "lev": 1,
            "margin": round(notional, 2), "usd": round(notional, 2)})
    nav_hist = [{"ts": "2026-06-08T00:00:00Z", "v": round(1000.0, 2)}]
    scale = 1000.0 / start if start else 1.0
    for t in closed[-300:]:
        v = f(t.get("equity"))
        if v:
            nav_hist.append({"ts": str(t.get("closed", ""))[:16], "v": round(v * scale, 2)})
    nav_hist.append({"ts": NOW, "v": round(nav * scale, 2)})
    return {"key": key, "title": title, "desc": desc + " · 12june",
            "start_eq": 1000.0, "nav": round(nav * scale, 2), "nav_hist": nav_hist,
            "trades": trades, "positions": poss,
            "base": "other", "signal": "other", "direction": "merged", "_lev": 1}


def main():
    if not os.path.isdir(OUT):
        os.makedirs(OUT)
    n = 0
    for botkey, title, desc in BOTS:
        st = jload(os.path.join(SRC, botkey + "_state.json"))
        if not st:
            continue
        out = conv(st, "fon_" + botkey, title, desc)
        with open(os.path.join(OUT, "fon_%s.json" % botkey), "w") as fh:
            json.dump(out, fh, ensure_ascii=False)
        n += 1
    print("%d FON botu deneme1 şemasında → %s" % (n, OUT))


if __name__ == "__main__":
    main()
