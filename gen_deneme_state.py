#!/usr/bin/env python3
"""gen_deneme_state.py — botlarımızı TIRAD dashboard'unun (/deneme/state) TAM şemasına çevirir.
Bizim ~/uploads/tirad/<bot>_state.json + _trades.jsonl  →  ~/uploads/state/fon_<key>.json
Admin tek satırla bağlar:  cp /home/veri/uploads/state/*.json /deneme/state/  (root cron)
Sonra 4 botumuz dashboard'da 'fon' grubunda, kendi sayfaları + tam işlem tablosu (gerekçeyle) görünür.
Display için 1000-tabanına normalize edilir (dashboard konvansiyonu). Saf stdlib, 3.6-uyumlu."""
import json, os
from datetime import datetime, timezone

SRC = os.path.dirname(os.path.abspath(__file__))               # ~/uploads/tirad
OUT = os.path.join(os.path.dirname(SRC), "state")              # ~/uploads/state
BASE_NAV = 1000.0
# bizim bot-key → dashboard (key, signal-etiketi, başlık, açıklama)
MAP = [
    ("prop_funded", "fon_funded", "funded", "🟢 FON · Funded (Hawkes)",
     "HyroTrader funded para-sağma · order-flow lam · base %0.08 · +%5 çekim · −%10 statik DD"),
    ("prop_eval", "fon_eval", "eval", "🔵 FON · Eval (Hawkes)",
     "HyroTrader sınav · lam yükselen-kaskad + VR<1 · base %0.15 · +%10 hedef"),
    ("prop_eval_fast", "fon_eval_fast", "eval_fast", "🟡 FON · Eval-Fast (Hawkes)",
     "Hızlı sınav · base %0.25 · +%10 hedef"),
    ("sprint", "fon_sprint", "sprint", "🔴 FON · Sprint (Hawkes)",
     "Agresif kendi-sermaye · base %0.80 · sınırsız compound"),
]


def load_state(k):
    p = os.path.join(SRC, k + "_state.json")
    return json.load(open(p)) if os.path.exists(p) else None


def load_trades(k):
    p = os.path.join(SRC, k + "_trades.jsonl"); out = []
    if os.path.exists(p):
        for ln in open(p):
            ln = ln.strip()
            if ln:
                try: out.append(json.loads(ln))
                except Exception: pass
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    anchor = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    n_ok = 0
    for botkey, key, sig, title, desc in MAP:
        st = load_state(botkey)
        if not st:
            continue
        eq = st.get("equity", BASE_NAV); start = st.get("risk", {}).get("start", eq) or eq
        vault = st.get("vault", 0.0)
        scale = BASE_NAV / start if start else 1.0          # 1000-tabanına normalize
        nav = (eq + vault) * scale
        trades_raw = load_trades(botkey)

        # nav_hist: işlem equity serisinden (normalize)
        nav_hist = [{"ts": st.get("risk", {}).get("cur_day", anchor) or anchor, "v": BASE_NAV}]
        for t in trades_raw[-200:]:
            nav_hist.append({"ts": t.get("closed", "")[:16], "v": round(t.get("equity", start) * scale, 2)})
        nav_hist.append({"ts": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M"), "v": round(nav, 2)})

        # positions
        positions = []
        for sym, p in st.get("positions", {}).items():
            coin = sym.replace("USDT", "")
            positions.append({"sym": coin + "/USDT:USDT", "coin": coin, "side": p["direction"],
                              "entry_px": p["entry"], "entry_ts": p.get("opened_ts", ""),
                              "weight": round(1.0 / max(st.get("cfg_max_pos", 6), 1), 4),
                              "lev": 1.0, "margin": round(p.get("risk_amount", 0), 2),
                              "usd": round(p.get("risk_amount", 0), 2),
                              "reason": p.get("reason", ""),
                              "feat": {"lam": p.get("lam", 0), "vr": p.get("vr", 0)}})

        # trades (dashboard şeması)
        trades = []
        for t in trades_raw[-200:]:
            trades.append({"coin": t.get("symbol", "").replace("USDT", ""), "side": t.get("yon", ""),
                           "entry_px": t.get("entry", 0), "exit_px": t.get("exit", 0),
                           "usd": 100.0, "margin": 100.0, "lev": 1.0,
                           "pnl_pct": t.get("pct", 0), "pnl_usd": round(t.get("R", 0) * 100, 2),
                           "fund_pct": 0.0, "fee_usd": t.get("fee", 0),
                           "entry_ts": t.get("opened", "")[:16], "exit_ts": t.get("closed", "")[:16],
                           "reason": t.get("reason", "")})

        doc = {"key": key, "base": "fon", "signal": sig, "direction": "merged",
               "title": title, "desc": desc, "start_eq": BASE_NAV, "anchor": anchor,
               "nav": round(nav, 2), "base_nav": BASE_NAV, "positions": positions,
               "nav_hist": nav_hist, "trades": trades, "_lev": 1.0}
        with open(os.path.join(OUT, key + ".json"), "w") as f:
            json.dump(doc, f, ensure_ascii=False)
        n_ok += 1
    print("%d FON botu /deneme/state şemasında yazıldı → %s" % (n_ok, OUT))


if __name__ == "__main__":
    main()
