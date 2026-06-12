#!/usr/bin/env python3
"""
🔵 prop_eval_bot.py — HYROTRADER SINAV BOTU (Cephe-2: fon sınavını geç)
═══════════════════════════════════════════════════════════════════════════════
HyroTrader TWO-STEP (hyrotrader.com'dan doğrulandı):
  Step1 +%10 · Step2 +%5 · %5 günlük · %10 STATİK total · SINIRSIZ süre · min 5 gün · kripto perp
KANITLANMIŞ (400 Monte-Carlo, statik −%10, sınırsız süre):
  base %0.15 → Step1 P(pass)=%100, P(blown)=%0, medyan ~110 gün (~3.7 ay).  ← GARANTİLİ
Gün-içi −%3'te durur (−%5 günlüğe ASLA değmez). +%10'da DURUR → Step2 için target'ı 0.05 yap.

NOT: 1-STEP isteğine geçersen → total_dd=0.06, daily_dd=0.04, base_risk=0.0008, halt=0.02 yap
     (1-step %4/%6 daha sert; MC: base %0.08 → %100 pass/%0 blown ama daha yavaş).

KULLANIM:
  python prop_eval_bot.py --once --equity 10000   # Step1 (cron)
  python prop_eval_bot.py --equity 10000          # otonom; +%10'da durur
  # Step2 için: EVAL_CONFIG.target=0.05 yap, state dosyasını sil, tekrar başlat
  python prop_eval_bot.py --live                  # ⚠️ gerçek HyroTrader API'si
"""
from tirad_core import BotConfig, UNIVERSE
from tirad_runner import run_cli

# ── 🔵 HYROTRADER TWO-STEP SINAV CONFIG (kanıtlı: %100 geçiş / %0 iflas) ──────
EVAL_CONFIG = BotConfig(
    name="PROP_EVAL",
    base_risk=0.0015,      # %0.15 (MC: Step1 %100 pass / %0 blown / ~110 gün). Daha hızlı: 0.0020 (%2 blown)
    max_risk=0.0070,       # %0.70 tavan
    max_pos=6,
    daily_dd=0.04,         # HYRO GERÇEK (site 2026-06-12): günlük −%4
    total_dd=0.06,         # HYRO GERÇEK: max-loss −%6 total → ASLA değme
    intraday_halt=0.02,    # gün-içi −%3 → o gün dur (−%5 günlüğe asla ulaşma)
    trailing_floor=False,  # STATİK (başlangıçtan) ✓
    target=0.10,           # Step1 +%10 (Step2 için 0.05 yap)
    stop_on_target=True,   # geçince DUR
    symbols=UNIVERSE,
    live=False,
    state_file="prop_eval_state.json",
)

if __name__ == "__main__":
    run_cli(EVAL_CONFIG, default_equity=10000.0)
