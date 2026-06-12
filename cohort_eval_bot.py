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

HYRO UYUM (site taraması 2026-06-12): custom bot İZİNLİ (kendi API key, Bybit);
SL girişten ≤5dk (bizde anında ✓); tek-işlem ≤%40 kâr-konsantrasyonu (küçük-TP'li bizde ✓);
low-cap konsantrasyon ≤%5 (CANLIda likit-subset kullan!); martingale/hedging yasak (bizde yok ✓);
min 5 işlem-günü; fee geçince İADE. 2-step fiyatlar: $59/5K (EN UCUZ) · $119/10K · $249/25K.

KOHORT KULLANIM (4-6 paralel hesap, her biri ayrı state):
  for n in 1 2 3 4 5; do python cohort_eval_bot.py --once --account $n; done
  → P(en az 1 hesap Step1 ≤10g) ≈ %61 (5 slot), ~haftada 1 yeni funded akışı.
"""
from tirad_core import BotConfig, UNIVERSE
from tirad_runner import run_cli

# GENİŞLİK-75 (breadth_tier_test: T1/T2 likit katman, lam≥2 OOS avgR +0.175/+0.123;
# T3-ince ATILDI OOS −0.329). 118-coin evren + 16slot/%0.20 → P(pass) 53→63%, blow benzer.
BREADTH75 = (
    "1000BONKUSDT",
    "1000FLOKIUSDT",
    "1000LUNCUSDT",
    "1000PEPEUSDT",
    "1000SHIBUSDT",
    "AEROUSDT",
    "AIXBTUSDT",
    "APEUSDT",
    "ARUSDT",
    "ARCUSDT",
    "ARKMUSDT",
    "BCHUSDT",
    "BIOUSDT",
    "BLURUSDT",
    "BOMEUSDT",
    "CAKEUSDT",
    "CFXUSDT",
    "DASHUSDT",
    "DEXEUSDT",
    "DUSKUSDT",
    "EDUUSDT",
    "EIGENUSDT",
    "ENAUSDT",
    "ENSUSDT",
    "ETHFIUSDT",
    "FARTCOINUSDT",
    "FETUSDT",
    "GRASSUSDT",
    "HBARUSDT",
    "JTOUSDT",
    "JUPUSDT",
    "KASUSDT",
    "LDOUSDT",
    "MOODENGUSDT",
    "MORPHOUSDT",
    "NEIROUSDT",
    "ONDOUSDT",
    "ONTUSDT",
    "ORCAUSDT",
    "ORDIUSDT",
    "PENDLEUSDT",
    "PENGUUSDT",
    "PIPPINUSDT",
    "PIXELUSDT",
    "PNUTUSDT",
    "POLUSDT",
    "PYTHUSDT",
    "RENDERUSDT",
    "ROSEUSDT",
    "SUSDT",
    "SAGAUSDT",
    "SEIUSDT",
    "SPXUSDT",
    "STRKUSDT",
    "STXUSDT",
    "SUIUSDT",
    "SWARMSUSDT",
    "TAOUSDT",
    "THETAUSDT",
    "TIAUSDT",
    "TONUSDT",
    "TRBUSDT",
    "TRUMPUSDT",
    "TURBOUSDT",
    "VETUSDT",
    "VIRTUALUSDT",
    "WUSDT",
    "WIFUSDT",
    "WLDUSDT",
    "XMRUSDT",
    "ZECUSDT",
    "ZENUSDT",
    "ZEREBROUSDT",
    "ZKUSDT",
    "ZROUSDT",
)

# ── 🟣 KOHORT FAST-PASS CONFIG ──────────────────────────────────────────────
COHORT_CONFIG = BotConfig(
    name="COHORT_EVAL",
    lam_min=2.0,           # OOS-robust giriş filtresi (blow-tavanı + frekans yeterli)
    base_risk=0.0015,      # BUILD %0.15 × 16 slot — HYRO GERÇEK limitlerde (4/6) MC: pass %50/60g, blow %26-32
                           # (%0.20 → blow %41-46 = fazla; %0.12 → blow %13-19 ama medyan 37g+timeout)
    max_risk=0.0060,       # conviction tavanı (lam→3x clip)
    cushion=0.08,          # equity +%8 → PROTECT'e geç
    protect_risk=0.0005,   # PROTECT %0.05 (yastığı koru, statik −%10'a çarpma ~0)
    max_pos=16,            # GENİŞLİK: 118 coin → 16 bağımsız slota dağıt (çeşitlendirme=güvenilirlik)
    daily_dd=0.04,         # HYRO GERÇEK (site 2026-06-12): günlük −%4 (eski %5 varsayımı YANLIŞTI)
    total_dd=0.06,         # HYRO GERÇEK: max-loss −%6 (eski −%10 varsayımı YANLIŞTI)
    intraday_halt=0.02,    # gün-içi −%2 → dur (−%4 günlüğe EOD-uçurumla değmemek için)
    trailing_floor=False,
    tp_r=2.5,              # sıklık = +%10 yastığına hızlı varış
    target=0.10,           # Step1 +%10
    stop_on_target=True,   # geçince DUR (Step2'ye/funded'a geç)
    symbols=tuple(UNIVERSE) + BREADTH75,
    live=False,
    state_file="cohort_eval_state.json",
)

if __name__ == "__main__":
    run_cli(COHORT_CONFIG, default_equity=100000.0)
