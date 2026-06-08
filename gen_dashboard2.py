#!/usr/bin/env python3
"""gen_dashboard2.py — botlarımızı /root/tirad/dashboard2.py'nin (TIRAD — Trading Dashboard,
PAPER_DIR=/root/tirad/paper) ŞEMASINA çevirir. ~/uploads/tirad/<bot>_state.json → ~/uploads/paper/<key>.json
Şema: key/name/title/family/desc/start_eq/as_of/deploy/weights/stats{sharpe,cagr,maxdd,navnow,days}/
nav[{ts,v}]/ref{oos_*}/targets{LONG,SHORT}. 1000-tabanına normalize. Saf stdlib, 3.6-uyumlu."""
import json, os, statistics
from datetime import datetime, timezone

SRC = os.path.dirname(os.path.abspath(__file__))            # ~/uploads/tirad
OUT = os.path.join(os.path.dirname(SRC), "paper")           # ~/uploads/paper
BASE = 1000.0
DEPLOY = "2026-06-08"
TODAY = datetime.now(timezone.utc).strftime("%Y-%m-%d")
META = [
    ("prop_funded", dict(key="fon_funded", name="bot_fon_funded", title="🟢 FON · Funded (Hawkes)",
        family="FON (Hawkes lam)", desc="HyroTrader funded para-sağma · order-flow lam · base %0.08 · +%5 çekim · −%10 statik",
        ref=dict(oos_sharpe=0.9, oos_cagr=0.06, oos_maxdd=-0.04))),
    ("prop_eval", dict(key="fon_eval", name="bot_fon_eval", title="🔵 FON · Eval (Hawkes)",
        family="FON (Hawkes lam)", desc="HyroTrader sınav · lam yükselen-kaskad + VR<1 · base %0.15 · +%10 hedef",
        ref=dict(oos_sharpe=1.0, oos_cagr=0.30, oos_maxdd=-0.06))),
    ("prop_eval_fast", dict(key="fon_eval_fast", name="bot_fon_eval_fast", title="🟡 FON · Eval-Fast (Hawkes)",
        family="FON (Hawkes lam)", desc="Hızlı sınav · base %0.25 · +%10 hedef · ~1.5 ay",
        ref=dict(oos_sharpe=1.0, oos_cagr=0.50, oos_maxdd=-0.10))),
    ("sprint", dict(key="fon_sprint", name="bot_fon_sprint", title="🔴 FON · Sprint (Hawkes)",
        family="FON (Hawkes lam)", desc="Agresif kendi-sermaye · base %0.80 · sınırsız compound",
        ref=dict(oos_sharpe=1.1, oos_cagr=0.89, oos_maxdd=-0.36))),
]


def load_state(k):
    p = os.path.join(SRC, k + "_state.json")
    return json.load(open(p)) if os.path.exists(p) else None


def build(st, m):
    eq = st.get("equity", BASE); start = st.get("risk", {}).get("start", eq) or eq
    vault = st.get("vault", 0.0); scale = BASE / start if start else 1.0
    closed = st.get("closed", [])
    nav = [{"ts": DEPLOY, "v": BASE}]
    for t in closed[-300:]:
        nav.append({"ts": (t.get("closed", "") or DEPLOY)[:10], "v": round(t.get("equity", start) * scale, 2)})
    navnow = round((eq + vault) * scale, 2)
    nav.append({"ts": TODAY, "v": navnow})
    vs = [h["v"] for h in nav]
    peak = vs[0]; mdd = 0.0
    for v in vs:
        peak = max(peak, v); mdd = min(mdd, v / peak - 1.0) if peak else mdd
    rets = [vs[i] / vs[i - 1] - 1 for i in range(1, len(vs)) if vs[i - 1] > 0]
    sharpe = (statistics.mean(rets) / statistics.pstdev(rets) * (365 ** 0.5)) if len(rets) > 1 and statistics.pstdev(rets) > 1e-9 else 0.0
    try:
        days = max((datetime.strptime(TODAY, "%Y-%m-%d") - datetime.strptime(DEPLOY, "%Y-%m-%d")).days, 1)
    except Exception:
        days = 1
    cagr = (navnow / BASE) ** (365.0 / days) - 1.0 if navnow > 0 else 0.0
    tgt = {"LONG": [], "SHORT": []}
    for sym, p in st.get("positions", {}).items():
        tgt["LONG" if p["direction"] == 1 else "SHORT"].append(sym.replace("USDT", ""))
    return {"start_eq": BASE, "as_of": TODAY, "deploy": DEPLOY, "family": m["family"],
            "key": m["key"], "name": m["name"], "title": m["title"], "desc": m["desc"],
            "weights": {"hawkes_lam": 1.0}, "stats": {"sharpe": round(sharpe, 2), "cagr": round(cagr, 4),
            "maxdd": round(mdd, 4), "navnow": navnow, "days": days},
            "nav": nav, "ref": m["ref"], "targets": tgt}


def main():
    os.makedirs(OUT, exist_ok=True); n = 0
    for botkey, m in META:
        st = load_state(botkey)
        if not st: continue
        with open(os.path.join(OUT, m["key"] + ".json"), "w") as f:
            json.dump(build(st, m), f, ensure_ascii=False)
        n += 1
    print("%d FON botu dashboard2 şemasında → %s" % (n, OUT))


if __name__ == "__main__":
    main()
