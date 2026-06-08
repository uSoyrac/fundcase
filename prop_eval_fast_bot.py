#!/usr/bin/env python3
"""
🟡 prop_eval_fast_bot.py — HIZLI SINAV BOTU (Cephe-2-hızlı: çabuk funded ol)
═══════════════════════════════════════════════════════════════════════════════
Güvenli Eval (%0.15, ~4 ay, %92-96 geçiş) yerine HIZLI rota: daha agresif, daha çabuk,
geçiş oranı biraz düşük ama HyroTrader ücreti iade-edilebilir → patlarsa tekrar dene.
STRES-DOĞRULANMIŞ (gap-stop + funding, 2-step %5/%10 statik):
  base %0.25 → ILIMLI %83 geçiş /48 gün, SERT %78 geçiş /52 gün (%17-22 iflas).
Felsefe: kötü piyasada bile ~%78 geç (amaca ulaş), iyi piyasada hızlı+çok kazan.
  (Maksimum hız istersen base %0.30 → ~%65-70 geçiş / ~32 gün, ama %31-38 iflas/ücret-tekrar.)
Beklenen-değer: ~1.3 deneme × ~1.5 ay ≈ güvenli rotanın yarısı sürede funded (ücret×1.3).

KULLANIM:
  python prop_eval_fast_bot.py --once --equity 10000
  python prop_eval_fast_bot.py --equity 10000          # +%10'da durur
"""
from tirad_core import BotConfig, UNIVERSE
from tirad_runner import run_cli

# ── 🟡 HIZLI SINAV CONFIG (stres: ~%78-83 geçiş / ~1.5 ay) ──────────────────
FAST_EVAL_CONFIG = BotConfig(
    name="PROP_EVAL_FAST",
    base_risk=0.0025,      # %0.25 (stres: %78-83 geçiş / ~48 gün). Max hız: 0.0030 (~%65-70 / 32 gün)
    max_risk=0.0110,       # %1.10 tavan
    max_pos=7,
    daily_dd=0.05,         # HyroTrader 2-step günlük −%5
    total_dd=0.10,         # HyroTrader 2-step STATİK −%10
    intraday_halt=0.03,    # gün-içi −%3 → o gün dur
    trailing_floor=False,  # STATİK ✓
    target=0.10,           # Step1 +%10 (Step2 için 0.05 yap)
    stop_on_target=True,
    symbols=UNIVERSE,
    live=False,
    state_file="prop_eval_fast_state.json",
)

if __name__ == "__main__":
    run_cli(FAST_EVAL_CONFIG, default_equity=10000.0)
