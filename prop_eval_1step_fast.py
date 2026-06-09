#!/usr/bin/env python3
"""
🟠 prop_eval_1step_fast.py — HIZLI 1-STEP SINAV BOTU (kohort motoru: funded'ı SIK al)
═══════════════════════════════════════════════════════════════════════════════
HyroTrader 1-STEP (4%/6%, +%10, tek fazda funded). KOHORT için: paralel ~4-5 kopya
(çoklu firma) → her ~7-10 günde 1 funded. Monte-Carlo (stres, base %0.35):
  P(pass)=%45, medyan 17g, en hızlı %25 → 7g, %55 blow, net ~$247/funded.
GEÇMEK İÇİN HIZ — ama funded olunca hesabı prop_funded_bot (base %0.08) ile YÖNET
(agresif kalırsa funded −%10'u patlar). Geç-hızlı, tut-güvenli.

KULLANIM: her firma/hesap için ayrı state_file ile bir kopya çalıştır (kohort):
  python prop_eval_1step_fast.py --once --equity 10000     # state_file'ı düzenle
"""
from tirad_core import BotConfig, UNIVERSE
from tirad_runner import run_cli

# ── 🟠 HIZLI 1-STEP CONFIG (kohort motoru) ──────────────────────────────────
FAST1_CONFIG = BotConfig(
    name="PROP_EVAL_1STEP_FAST",
    base_risk=0.0035,      # %0.35 (MC: P45% / medyan 17g / %55 blow — kohortta sweet-spot)
    max_risk=0.0140,       # %1.40 tavan
    max_pos=7,
    daily_dd=0.04,         # HyroTrader 1-step günlük −%4
    total_dd=0.06,         # HyroTrader 1-step STATİK −%6
    intraday_halt=0.02,    # gün-içi −%2 → −%4 günlüğe değme
    trailing_floor=False,
    target=0.10,           # +%10 → tek fazda funded
    stop_on_target=True,   # geçince DUR → o hesabı prop_funded (%0.08) ile yönet
    symbols=UNIVERSE,
    live=False,
    state_file="prop_eval_1step_fast_state.json",
)

if __name__ == "__main__":
    run_cli(FAST1_CONFIG, default_equity=10000.0)
