#!/usr/bin/env python3
"""gen_fon.py — TIRAD FON dashboard (çok-sayfa: index + bot-bot detay + TAM işlem tablosu).
Her botun state JSON + _trades.jsonl (kalıcı tam geçmiş) okunur → fon.html + fon_<key>.html.
Her işlem tek tek GEREKÇESİYLE görünür (lam/VR/yön) → sonradan analiz/geliştirme için.
Saf stdlib, 3.6-uyumlu. Cron'da botlardan sonra koşar."""
import json, os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
BOTS = [
    ("prop_funded", "🟢 FUNDED", "Para-sağma ATM · base %0.08 · +%5 çekim · −%10 statik"),
    ("prop_eval", "🔵 EVAL", "HyroTrader sınav · base %0.15 · +%10 hedef"),
    ("prop_eval_fast", "🟡 EVAL-FAST", "Hızlı sınav · base %0.25 · +%10 hedef"),
    ("sprint", "🔴 SPRINT", "Agresif kendi-sermaye · base %0.80"),
]
CSS = """
:root{--bg:#0c0f14;--bg2:#11161f;--card:#161c27;--line:#26303f;--txt:#e6edf3;--muted:#8a97a8;--pos:#2ecc71;--neg:#ff5d5d;--accent:#4da3ff;--long:#3fb968;--short:#e06b6b}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--txt);font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;font-size:14px;line-height:1.5}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.wrap{max-width:1300px;margin:0 auto;padding:18px}h1{font-size:21px;margin:0 0 2px}.top{color:var(--muted);font-size:12px;margin-bottom:14px}
.banner{background:#10241a;border:1px solid #1f5b3a;color:#7fe0a8;padding:9px 13px;border-radius:8px;margin:10px 0 16px;font-size:12px}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(250px,1fr));gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:14px}
.bl{font-size:16px;font-weight:600}.sub{color:var(--muted);font-size:11px;margin-bottom:8px}
.nav{font-size:23px;font-weight:700;margin:4px 0 6px}.nav .r{font-size:13px;font-weight:500}
.pos{color:var(--pos)}.neg{color:var(--neg)}.long{color:var(--long);font-weight:600}.short{color:var(--short);font-weight:600}
.muted{color:var(--muted)}
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:14px 0}
.kpi{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:13px}
.kpi .l{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em}.kpi .v{font-size:22px;font-weight:700;margin-top:3px}
.kv{display:flex;justify-content:space-between;border-top:1px solid var(--line);padding:5px 0;font-size:13px}.kv span{color:var(--muted)}
.lbl{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.04em;margin:14px 0 6px}
table{width:100%;border-collapse:collapse;font-size:12px}td,th{padding:5px 8px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}
th{color:var(--muted);font-weight:500}td:first-child,th:first-child,td.l,th.l{text-align:left}
.sec{background:var(--card);border:1px solid var(--line);border-radius:11px;padding:14px;margin-top:14px;overflow-x:auto}
.rsn{color:var(--muted);font-size:11px;max-width:340px;white-space:normal}
svg{display:block}
"""
HEAD = "<!doctype html><html lang=tr><head><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>{T}</title><style>" + CSS + "</style></head><body><div class=wrap>"
FOOT = "<div class=top style='margin-top:18px'>TIRAD FON · otomatik 4H · <a href='fon.html'>🏠 Tüm Botlar</a></div></div></body></html>"


def load_state(key):
    p = os.path.join(HERE, key + "_state.json")
    if not os.path.exists(p): return None
    try:
        with open(p) as f: return json.load(f)
    except Exception: return None


def load_trades(key):
    p = os.path.join(HERE, key + "_trades.jsonl")
    out = []
    if os.path.exists(p):
        for line in open(p):
            line = line.strip()
            if line:
                try: out.append(json.loads(line))
                except Exception: pass
    return out


def nav_area(eqs, start, w=1000, h=180):
    if len(eqs) < 2: return "<div class='muted'>yeterli işlem yok</div>"
    lo, hi = min(eqs + [start]), max(eqs + [start])
    rng = (hi - lo) or 1
    xs = [w * i / (len(eqs) - 1) for i in range(len(eqs))]
    ys = [h - (e - lo) / rng * h for e in eqs]
    line = " ".join("%.1f,%.1f" % (x, y) for x, y in zip(xs, ys))
    area = "0,%.1f " % h + line + " %.1f,%.1f" % (w, h)
    col = "#2ecc71" if eqs[-1] >= start else "#ff5d5d"
    base_y = h - (start - lo) / rng * h
    return ("<svg viewBox='0 0 %d %d' width='100%%' height='%d' preserveAspectRatio='none'>"
            "<polygon points='%s' fill='%s22'/>"
            "<line x1=0 y1='%.1f' x2='%d' y2='%.1f' stroke='#888' stroke-dasharray='3 3' stroke-width='0.6'/>"
            "<polyline points='%s' fill='none' stroke='%s' stroke-width='1.5'/></svg>"
            ) % (w, h, h, area, col, base_y, w, base_y, line, col)


def metrics(state, trades):
    eq = state.get("equity", 0) if state else 0
    start = (state.get("risk", {}).get("start", eq) if state else 0) or eq or 1
    vault = state.get("vault", 0) if state else 0
    total = eq + vault
    pnl = total - start
    n = len(trades)
    wins = sum(1 for t in trades if t.get("R", 0) > 0)
    wr = 100 * wins / n if n else 0
    open_n = len(state.get("positions", {})) if state else 0
    return dict(nav=eq, vault=vault, pnl=pnl, pnl_pct=(total / start - 1) * 100,
                n=n, wins=wins, wr=wr, open=open_n, start=start)


def kpi(l, v, cls=""):
    return "<div class=kpi><div class=l>%s</div><div class='v %s'>%s</div></div>" % (l, cls, v)


def trade_table(trades, limit=200):
    rows = []
    for t in trades[-limit:][::-1]:
        ycls = "long" if t.get("dir") == 1 else "short"
        pcls = "pos" if t.get("pnl", 0) >= 0 else "neg"
        rows.append(
            "<tr><td class=l>%s</td><td class=l>%s</td><td class='l %s'>%s</td>"
            "<td>%.4f→%.4f</td><td class=%s>%+.2f%%</td><td class=%s>%+.2f$</td>"
            "<td class=muted>%.2f$</td><td>%.2f</td><td>%s·%db</td>"
            "<td class=l rsn>%s</td></tr>" % (
                t.get("closed", "")[5:16], t.get("symbol", ""), ycls, t.get("yon", ""),
                t.get("entry", 0), t.get("exit", 0), pcls, t.get("pct", 0),
                pcls, t.get("pnl", 0), t.get("fee", 0), t.get("lam", 0),
                t.get("exit_type", ""), t.get("bars", 0), t.get("reason", "")))
    hdr = ("<tr><th class=l>kapanış</th><th class=l>coin</th><th class=l>yön</th>"
           "<th>giriş→çıkış</th><th>%</th><th>P/Z</th><th>fee</th><th>lam</th>"
           "<th>tip</th><th class=l>gerekçe</th></tr>")
    return "<table>" + hdr + "".join(rows) + "</table>"


def open_table(state):
    pos = state.get("positions", {}) if state else {}
    if not pos: return "<div class=muted>açık pozisyon yok</div>"
    rows = ""
    for sym, p in pos.items():
        ycls = "long" if p["direction"] == 1 else "short"
        rows += ("<tr><td class=l>%s</td><td class='l %s'>%s</td><td>%.4f</td>"
                 "<td>%.4f</td><td>%.4f</td><td>%.2f</td><td class=l rsn>%s</td></tr>" % (
                     sym, ycls, "LONG" if p["direction"] == 1 else "SHORT", p["entry"],
                     p["sl"], p["tp"], p.get("lam", 0), p.get("reason", "")))
    return ("<table><tr><th class=l>coin</th><th class=l>yön</th><th>giriş</th><th>SL</th>"
            "<th>TP</th><th>lam</th><th class=l>gerekçe</th></tr>" + rows + "</table>")


def detail_page(key, label, desc, state, trades):
    m = metrics(state, trades)
    eqs = [t.get("equity") for t in trades if t.get("equity") is not None]
    pcls = "pos" if m["pnl"] >= 0 else "neg"
    vault_kpi = kpi("ÇEKİLEN PAYOUT", "$%s" % format(int(m["vault"]), ","), "pos") if m["vault"] else ""
    html = HEAD.replace("{T}", "FON · " + label)
    html += "<div class=top><a href='fon.html'>← Tüm botlar</a></div>"
    html += "<h1>%s</h1><div class=top>%s</div>" % (label, desc)
    html += ("<div class=kpis>"
             + kpi("CANLI NAV", "$%s" % format(round(m["nav"], 2), ","))
             + kpi("TOPLAM K/Z $", "%+.2f$" % m["pnl"], pcls)
             + kpi("TOPLAM K/Z %", "%+.2f%%" % m["pnl_pct"], pcls)
             + kpi("AÇIK POZİSYON", str(m["open"]))
             + kpi("KAPANAN İŞLEM", str(m["n"]))
             + kpi("KAZANÇ ORANI", "%.1f%% (%d/%d)" % (m["wr"], m["wins"], m["n"]))
             + vault_kpi + "</div>")
    html += "<div class=sec><div class=lbl>NAV Eğrisi ($%s başlangıç)</div>%s</div>" % (
        format(int(m["start"]), ","), nav_area(eqs, m["start"]))
    html += "<div class=sec><div class=lbl>Açık Pozisyonlar</div>%s</div>" % open_table(state)
    html += "<div class=sec><div class=lbl>İşlem Geçmişi (son %d · toplam %d) — her işlem gerekçesiyle</div>%s</div>" % (
        min(200, m["n"]), m["n"], trade_table(trades))
    return html + FOOT


def index_page(data, now):
    cards = ""
    for key, label, desc, state, trades in data:
        m = metrics(state, trades)
        rcls = "pos" if m["pnl_pct"] >= 0 else "neg"
        vault = "<div class=kv><span>💰 Payout</span><b class=pos>$%s</b></div>" % format(int(m["vault"]), ",") if m["vault"] else ""
        cards += ("<div class=card><div class=bl><a href='fon_%s.html'>%s →</a></div><div class=sub>%s</div>"
                  "<div class='nav %s'>$%s <span class=r>(%+.1f%%)</span></div>"
                  "<div class=kv><span>İşlem · WR</span><b>%d · %%%.0f</b></div>"
                  "<div class=kv><span>Açık poz</span><b>%d</b></div>%s"
                  "<div class=kv><span>Detay</span><b><a href='fon_%s.html'>tüm işlemler →</a></b></div></div>") % (
            key, label, desc, rcls, format(round(m["nav"], 2), ","), m["pnl_pct"],
            m["n"], m["wr"], m["open"], vault, key)
    html = HEAD.replace("{T}", "TIRAD — FON")
    html += "<h1>TIRAD — FON · Hawkes Order-Flow Botları</h1>"
    html += "<div class=top>lam (öz-uyarım) edge · PAPER · canlı Binance · 42 coin · otomatik 4H · güncelleme: " + now + "</div>"
    html += "<div class=banner>⚠️ Paper-trade. Edge 43-coinde doğrulandı (dose-response +0.890 OOS) ama tek-tarihsel-veri; yatırım tavsiyesi değildir. Her bota tıkla → tüm işlemler + gerekçeleri.</div>"
    html += "<div class=grid>" + cards + "</div>"
    return html + FOOT


def main():
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    data = []
    for key, label, desc in BOTS:
        state = load_state(key); trades = load_trades(key)
        data.append((key, label, desc, state, trades))
        with open(os.path.join(HERE, "fon_%s.html" % key), "w") as f:
            f.write(detail_page(key, label, desc, state, trades))
    with open(os.path.join(HERE, "fon.html"), "w") as f:
        f.write(index_page(data, now))
    # makine-okur özet
    summary = {"as_of": now, "bots": [dict(key=k, label=l, **{x: metrics(s, t)[x] for x in ("nav", "pnl_pct", "n", "wr", "open", "vault")}) for k, l, d, s, t in data]}
    with open(os.path.join(HERE, "fon.json"), "w") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print("fon.html + 4 detay sayfası + fon.json yazıldı")


if __name__ == "__main__":
    main()
