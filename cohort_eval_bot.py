#!/usr/bin/env python3
"""
🟣 cohort_eval_bot.py — KOHORT FAST-PASS EVAL (10-agent workflow + sprint_z_mc.py doğrulaması)
═══════════════════════════════════════════════════════════════════════════════
HEDEF: 2-step challenge'ı hızlı geç + kohortla sürekli funded akışı. "Tek hesap 1-10g
kesin geç" FANTEZİ (~%5 kuyruk); GERÇEK yol = lam≥2 filtre + cushion-then-protect +
4-6 PARALEL hesap. Doğrulanan demir-kanun: HIZ↔BLOW süper-lineer (base %0.30→%0.60 =
blow %16→%40). Bu config hız-tarafında ama lam≥2 blow-tavanı + protect ile dengeli.

MEKANİZMA:
  • lam≥2.0 GİRİŞ FİLTRESİ — OOS-robust tek eşik (avgR +0.174 full/+0.154 OOS, frekans yeter).
    z>4 yoğunlaşma ÇÜRÜTÜLDÜ (lam≥4: WR%37/OOS-edge-yok/10g'de ~1.7 işlem = hızı öldürür).
  • cushion-then-protect: build %0.30 → equity +%8 yastıkta protect %0.05 (statik −%10 tabanı koru).
  • 1× kaldıraç (TEK iflas sebebi kaldıraç), TP 2.5R (sıklık=hedefe hızlı), günlük-halt %3.

KOHORT KULLANIM (4-6 paralel hesap, her biri ayrı state):
  for n in 1 2 3 4 5; do python cohort_eval_bot.py --once --account $n; done
  → P(en az 1 hesap Step1 ≤10g) ≈ %61 (5 slot), ~haftada 1 yeni funded akışı.
"""
from tirad_core import BotConfig, UNIVERSE
from tirad_runner import run_cli

# ── 🟣 KOHORT FAST-PASS CONFIG ──────────────────────────────────────────────
COHORT_CONFIG = BotConfig(
    name="COHORT_EVAL",
    lam_min=2.0,           # OOS-robust giriş filtresi (blow-tavanı + frekans yeterli)
    base_risk=0.0030,      # BUILD fazı %0.30 (hız kolu; %0.45'e çekilebilir, blow %25'e çıkar)
    max_risk=0.0090,       # conviction tavanı (lam→3x clip)
    cushion=0.08,          # equity +%8 → PROTECT'e geç
    protect_risk=0.0005,   # PROTECT %0.05 (yastığı koru, statik −%10'a çarpma ~0)
    max_pos=6,             # eşzamanlı poz (korelasyon kapağı; aynı-yön doğal sınır)
    daily_dd=0.05,         # HyroTrader 2-step günlük −%5
    total_dd=0.10,         # HyroTrader 2-step STATİK −%10
    intraday_halt=0.03,    # gün-içi −%3 → o gün dur (EOD-uçurum emniyeti)
    trailing_floor=False,
    tp_r=2.5,              # sıklık = +%10 yastığına hızlı varış
    target=0.10,           # Step1 +%10
    stop_on_target=True,   # geçince DUR (Step2'ye/funded'a geç)
    symbols=UNIVERSE,
    live=False,
    state_file="cohort_eval_state.json",
)

if __name__ == "__main__":
    run_cli(COHORT_CONFIG, default_equity=100000.0)
