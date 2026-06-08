#!/usr/bin/env python3
"""
🔴 sprint_bot.py — AGRESİF SPRINT BOTU (Cephe-1: kendi sermaye, $100→$1k avı)
═══════════════════════════════════════════════════════════════════════════════
Doğrulanmış çekirdek (tirad_core) + agresif risk. Monte-Carlo: P(+%10)=72%, medyan
24 gün, %35 DD kabul (kendi para). Vahşi-ama-tavanlı lam-Kelly. Sadece Binance Futures.

KULLANIM:
  python sprint_bot.py --once --equity 100   # tek döngü (cron: 1 4 9 13 17 21 * * *)
  python sprint_bot.py --equity 100          # otonom (4H boundary'de uyanır)
  python sprint_bot.py --live                # ⚠️ gerçek emir (BINANCE_KEY/SECRET env)
"""
from tirad_core import BotConfig, UNIVERSE
from tirad_runner import run_cli

# ── 🔴 SPRINT KONFİGÜRASYONU (buradan ayarla) ──────────────────────────────
SPRINT_CONFIG = BotConfig(
    name="SPRINT",
    base_risk=0.0080,      # %0.80 taban (VAHŞİ — MC: %88 ihtimalle ~2.3y'da 10x)
    max_risk=0.0250,       # %2.50 tavan (D10 devasa kaskad)
    max_pos=8,             # 8 eşzamanlı pozisyon
    daily_dd=0.05,         # günlük −%5 kill-switch
    total_dd=0.60,         # geniş −%60 devre-kesici (kendi para)
    intraday_halt=0.03,    # gün-içi −%3 acil fren
    trailing_floor=False,
    target=0.0,            # 0 = sınırsız compound ($100→$1k→devam)
    symbols=UNIVERSE,
    live=False,            # ⚠️ güvenli varsayılan: PAPER
    state_file="sprint_state.json",
)

if __name__ == "__main__":
    run_cli(SPRINT_CONFIG, default_equity=100.0)
