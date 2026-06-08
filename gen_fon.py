#!/usr/bin/env python3
"""gen_fon.py — TIRAD FON sayfası üreticisi (Hawkes botları, tek sayfa).
4 botun state JSON'larını okur → stillenmiş fon.html + fon.json yazar (~/uploads/tirad/).
Saf stdlib (3.6-uyumlu). Cron'da botlardan sonra koşar → dashboard temalı tek-yer görünüm."""
import json, os, sys
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BOTS = [
    ("prop_funded_state.json", "🟢 FUNDED", "Para-sağma ATM (base %0.08, +%5 çekim)"),
    ("prop_eval_state.json",   "🔵 EVAL", "HyroTrader sınav (base %0.15)"),
    ("prop_eval_fast_state.json", "🟡 EVAL-FAST", "Hızlı sınav (base %0.25)"),
    ("sprint_state.json",      "🔴 SPRINT", "Agresif kendi-sermaye (base %0.80)"),
]


def load(fn):
    p = os.path.join(HERE, fn)
    if not os.path.exists(p): return None
    with open(p) as f: return json.load(f)


def spark(closed, w=260, h=40):
    eqs = [c.get("equity") for c in closed if c.get("equity") is not None]
    if len(eqs) < 2: return ""
    lo, hi = min(eqs), max(eqs); rng = (hi - lo) or 1
    pts = " ".join("%.1f,%.1f" % (w*i/(len(eqs)-1), h-(e-lo)/rng*h) for i, e in enumerate(eqs))
    col = "#2ecc71" if eqs[-1] >= eqs[0] else "#ff5d5d"
    return '<svg width="%d" height="%d"><polyline fill="none" stroke="%s" stroke-width="1.5" points="%s"/></svg>' % (w, h, col, pts)


def card(label, desc, d):
    if not d:
        return '<div class="card"><div class="bl">%s</div><div class="muted">veri yok (bot henüz koşmadı)</div></div>' % label
    eq = d.get("equity", 0); start = d.get("risk", {}).get("start", eq) or eq
    peak = d.get("risk", {}).get("peak", eq); closed = d.get("closed", [])
    pos = d.get("positions", {}); vault = d.get("vault", 0)
    ret = (eq/start-1)*100 if start else 0
    dd = (1-eq/peak)*100 if peak else 0
    n = len(closed); wr = 100*sum(1 for c in closed if c.get("R",0)>0)/n if n else 0
    sumr = sum(c.get("R",0) for c in closed)
    cls = "pos" if ret >= 0 else "neg"
    rows = ""
    for sym, p in list(pos.items())[:8]:
        dd_ = "LONG" if p["direction"]==1 else "SHORT"
        rows += '<tr><td>%s</td><td class="%s">%s</td><td>%.4f</td></tr>' % (sym, dd_.lower(), dd_, p["entry"])
    postbl = '<table><tr><th>coin</th><th>yön</th><th>giriş</th></tr>%s</table>' % rows if rows else '<div class="muted">açık pozisyon yok</div>'
    vlt = '<div class="kv"><span>💰 Çekilen Payout</span><b class="pos">$%s</b></div>' % format(int(vault), ",") if vault else ""
    last = ""
    for c in closed[-5:][::-1]:
        last += '<tr><td>%s</td><td>%s</td><td class="%s">%+.2fR</td></tr>' % (c.get("closed","")[5:16], c["symbol"], "pos" if c["R"]>0 else "neg", c["R"])
    lasttbl = '<table><tr><th>zaman</th><th>coin</th><th>R</th></tr>%s</table>' % last if last else ""
    return ('<div class="card"><div class="bl">%s</div><div class="sub">%s</div>'
            '<div class="nav %s">$%s <span class="r">(%+.1f%%)</span></div>%s'
            '<div class="kv"><span>İşlem / WR</span><b>%d · %%%.0f</b></div>'
            '<div class="kv"><span>Toplam R</span><b>%+.1fR</b></div>'
            '<div class="kv"><span>Anlık DD / Peak</span><b>%%%.1f · $%s</b></div>%s'
            '<div class="lbl">Açık Pozisyonlar</div>%s'
            '<div class="lbl">Son İşlemler</div>%s</div>') % (
        label, desc, cls, format(round(eq,2), ","), ret, spark(closed),
        n, wr, sumr, dd, format(int(peak), ","), vlt, postbl, lasttbl)


def main():
    cards = "".join(card(l, dsc, load(fn)) for fn, l, dsc in BOTS)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    html = '''<!doctype html><html lang=tr><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>TIRAD — FON (Hawkes)</title><style>
:root{--bg:#0c0f14;--card:#161c27;--line:#26303f;--txt:#e6edf3;--muted:#8a97a8;--pos:#2ecc71;--neg:#ff5d5d;--accent:#4da3ff}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px}
.wrap{max-width:1100px;margin:0 auto;padding:18px}h1{font-size:21px;margin:0 0 2px}.top{color:var(--muted);font-size:12px;margin-bottom:16px}
.banner{background:#10241a;border:1px solid #1f5b3a;color:#7fe0a8;padding:9px 13px;border-radius:8px;margin-bottom:16px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:14px}
.bl{font-size:15px;font-weight:600}.sub{color:var(--muted);font-size:11px;margin-bottom:8px}
.nav{font-size:22px;font-weight:700;margin:4px 0 6px}.nav .r{font-size:13px;font-weight:500}
.pos{color:var(--pos)}.neg{color:var(--neg)}.long{color:#3fb968}.short{color:#e06b6b}.muted{color:var(--muted);font-size:12px;padding:4px 0}
.kv{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:5px 0;font-size:13px}.kv span{color:var(--muted)}
.lbl{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin:10px 0 4px}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:3px 6px;border-bottom:1px solid var(--line);text-align:left}th{color:var(--muted);font-weight:500}
svg{margin:2px 0}a{color:var(--accent)}
</style></head><body><div class=wrap>
<h1>TIRAD — FON · Hawkes Botları</h1>
<div class=top>order-flow öz-uyarım (lam) edge · PAPER · canlı Binance · otomatik 4H · güncelleme: __NOW__</div>
<div class=banner>⚠️ Paper-trade (sahte para). Edge 43-coinde doğrulandı (dose-response +0.890 OOS) ama tek-tarihsel-veri; yatırım tavsiyesi değildir.</div>
<div class=grid>__CARDS__</div>
<div class=top style="margin-top:18px">TIRAD FON · otomatik üretim · <a href="/">🏠 Ana Dashboard</a></div>
</div></body></html>'''.replace("__NOW__", now).replace("__CARDS__", cards)

    with open(os.path.join(HERE, "fon.html"), "w") as f:
        f.write(html)
    # makine-okur özet (ingestion için)
    summary = {"as_of": now, "bots": []}
    for fn, l, dsc in BOTS:
        d = load(fn)
        if d:
            eq = d.get("equity",0); start = d.get("risk",{}).get("start",eq) or eq
            summary["bots"].append({"key": fn.replace("_state.json",""), "label": l,
                "nav": round(eq,2), "ret_pct": round((eq/start-1)*100,2),
                "trades": len(d.get("closed",[])), "vault": d.get("vault",0),
                "open": len(d.get("positions",{}))})
    with open(os.path.join(HERE, "fon.json"), "w") as f:
        json.dump(summary, f, indent=2)
    print("fon.html + fon.json yazıldı:", HERE)


if __name__ == "__main__":
    main()
