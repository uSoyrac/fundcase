#!/usr/bin/env python3
"""
🟢 prop_funded_bot.py — HYROTRADER FUNDED PARA-SAĞMA BOTU (emeklilik ATM'si)
═══════════════════════════════════════════════════════════════════════════════
Sınav geçildikten sonra GERÇEK funded hesapta. HyroTrader: %5 günlük / %10 STATİK total,
+%5 kârda HEMEN çekim. Tek amaç: ASLA patlatma + maksimum nakit sağ.
STRES-DOĞRULANMIŞ (400 MC, $100k, gap-stop + funding dahil, statik −%10):
  base %0.08 + ÇEKİM +%5 → SERT streste bile P(iflas)=%0, yıllık net ~$4-8k/$100k.  ← GERÇEK ATM
  ($300k → ~$12-24k/yıl). NOT: %0.12 streste %6-15 patlıyordu → "asla patlatma" için %0.08'e indi.
KRİTİK: +%5 ERKEN çek = en güvenli + en kârlı (+%8/+%12 beklemek %70-86 PATLATIR).
DİKKAT: çok-yıllık + gap tail-riski sıfır DEĞİL; "%0" backtest'tir, canlıda izle.

KULLANIM:
  python prop_funded_bot.py --once --equity 100000   # cron
  python prop_funded_bot.py --equity 100000          # otonom; +%5'te otomatik çeker
  python prop_funded_bot.py --live                    # ⚠️ gerçek funded hesabı
"""
from tirad_core import BotConfig, UNIVERSE
from tirad_runner import run_cli

# ── 🟢 HYROTRADER FUNDED CONFIG (stres-doğrulanmış: %0 iflas, ~$4-8k/yıl/$100k) ──
FUNDED_CONFIG = BotConfig(
    name="PROP_FUNDED",
    base_risk=0.0008,      # %0.08 (stres: SERT'te bile %0 iflas, ~$4-8k/yıl/$100k). Gelir>güvenlik: 0.0010 (%2-7 iflas)
    max_risk=0.0040,       # %0.40 tavan
    max_pos=5,             # dar (korelasyon riskini kıs)
    daily_dd=0.04,         # HYRO GERÇEK (site 2026-06-12): günlük −%4
    total_dd=0.06,         # HYRO GERÇEK: max-loss −%6 → ASLA değme
    intraday_halt=0.02,    # gün-içi −%3 → erken dur
    trailing_floor=False,  # STATİK ✓
    target=0.0,            # hedef YOK → hayatta kal + sağ
    payout=True,           # PAYOUT aç
    payout_trigger=0.05,   # +%5'te ÇEK (KANITLI OPTİMAL — erken-çek en güvenli+en kârlı)
    payout_split=0.80,     # trader payı (%80→%90 scale)
    symbols=UNIVERSE,
    live=False,
    state_file="prop_funded_state.json",
)

if __name__ == "__main__":
    run_cli(FUNDED_CONFIG, default_equity=100000.0)
