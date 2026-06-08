# FUNDCASE — TIRAD Order-Flow Trading System

> Kripto perp futures için **fizik-temelli, falsification-doğrulanmış** trend-takip sistemi.
> Amaç: prop-firm (HyroTrader) sınavını geçip funded hesaptan düzenli gelir + kendi sermayeyi büyütme.

Bu repo, sıfırdan — fantezi botları eleştirip çöpe atarak — **acımasız ölçümle** inşa edilmiş bir edge ve onun üzerine kurulu 4 üretim botunu içerir. Her iddia, ön-kayıtlı bir testle (null-dağılımı, OOS, Monte-Carlo, stres) kanıtlanmıştır.

---

## 🧠 Sistem nasıl karar verir? (Tek bakışta)

Her **4 saatte bir**, 20 coin için:

```
1. KIRILIM?     → Fiyat son 20 mumun tepesini/dibini kırdı mı? (Donchian-20)
2. GERÇEK ATEŞ? → Order-flow öz-uyarımlı mı? (Hawkes lam > 1)  ← ÇEKİRDEK EDGE
3. TAZE Mİ?     → Sıkışmadan taze ateşleme mi? (Variance Ratio < 1) [yüksek-lam muaf]
4. BOYUT        → conviction = lam (büyük balina → büyük poz, tavanlı lam-Kelly)
5. ÇIKIŞ        → Sabit +2.5R kâr-al / −1R stop. Trailing YOK.
6. GÜVENLİK     → Günlük DD + gün-içi −%3 halt + statik total DD kill-switch
```

**Tek cümle:** *Çoğu kırılım sahtedir (fakeout). Onları ayıran şey fiyat değil, order-flow'un kümelenmesidir — gerçek balina girdiğinde alımlar zincirleme tetiklenir (Hawkes kaskadı).*

---

## 🔬 Çekirdek Keşif: Hawkes `lam`

`lam` = order-flow öz-uyarım yoğunluğu (EWMA):
```
m[i]   = num_trades[i] × |2·taker_buy_ratio[i] − 1|   (tek-yönlü agresyon şiddeti)
lam[i] = (1−β)·lam[i−1] + β·(m[i] / SMA(m, 60)[i]),   β = 0.3
```
**Veri-temelli sezgi:** 4H'de akış YÖNÜ persist etmez (autocorr 0.027 ≈ gürültü) ama ŞİDDETİ kümelenir (autocorr 0.105 = Hawkes imzası). Avcı yönü değil, **kaskadı** koklar.

### Kanıt karnesi
| Test | Sonuç | Anlam |
|---|---|---|
| Dose-response (19.811 işlem) | korelasyon **+0.896** | lam↑ → kâr↑ monoton = gerçek nedensel sinyal |
| **OOS kilidi (2025-26)** | **+0.960** | Ham edge negatifken bile çalışır (rejimden bağımsız) |
| Null-dağılımı (500 çekiliş) | **null>%100** | Şans değil; rastgeleyi hep yener |
| β/L duyarlılık (9 kombo) | +0.86…+0.98 | Knife-edge değil, yapısal |
| Long/Short simetri | her iki yön + | Beta artefaktı değil |
| Causality | lam farkı = **0.0** | Look-ahead yok; **canlı = backtest** |

> Düşük-lam kırılım (içi boş) **−0.145R** kaybeder; yüksek-lam (gerçek ateşleme) **+0.205R** kazanır.

---

## 🤖 Botlar (stres-doğrulanmış configler)

Tümü `tirad_core.py` (saf motor) + `tirad_runner.py` (canlı makine) paylaşır.

| Bot | base risk | Stres sonucu | Rol |
|---|---|---|---|
| 🔴 `sprint_bot.py` | %0.80 | ~%88 ihtimalle ~2.3y'da 10x | Kendi sermaye, agresif ($100→$1k) |
| 🔵 `prop_eval_bot.py` | %0.15 | %92-96 geçiş / %4-8 iflas, ~4 ay | Güvenli HyroTrader sınavı |
| 🟡 `prop_eval_fast_bot.py` | %0.25 | %78-83 geçiş / %17-22 iflas, ~1.5 ay | Hızlı sınav (ücret iade-edilebilir) |
| 🟢 `prop_funded_bot.py` | %0.08 + %5-çekim | **%0 iflas (SERT streste bile)**, ~$4-8k/yıl/$100k | Funded para-sağma ATM'si |

### HyroTrader kuralları (doğrulandı, hyrotrader.com)
- **1-Step:** +%10 hedef, %4 günlük, %6 STATİK max-loss, sınırsız süre.
- **2-Step:** +%10 / +%5 hedef, %5 günlük, %10 STATİK max-loss, sınırsız süre.
- Funded: +%5 kârda hemen çekim, %80→%90 split, kripto USDT perp.
- **STATİK + sınırsız süre bizim için piyango** — trailing olsaydı imkânsızdı (%18-31 iflas).

---

## 📉 Dürüst Limitler (Reality Check)

Stres-testi (`research/stress_mc.py`) ile modellenmiş/modellenmemiş:
- ✅ **Repainting/look-ahead:** sıfır (rigörlü, doğrulandı).
- ✅ **Komisyon+slippage:** sabit 14bps + gap-stop + funding (stres-testte).
- ⚠️ **"İflas=%0" iyimser:** gerçekçi sürtünmelerle Eval %4-8, Funded(0.12) %6-15 iflas → bu yüzden Funded %0.08'e indirildi (%0).
- ❌ **Survivorship:** 20 coin = bugünün hayatta kalanları (düzeltilmedi).
- ❌ **Korelasyonlu ekstrem gap:** tek 5.4y veride tam görülemez → gerçek tail-risk > 0.
- ⚠️ **Tek tarihsel veri (2021-2026):** canlı muhtemelen biraz daha kötü.

**Kural:** Gerçek paraya basmadan önce → 2-3 hafta PAPER → HyroTrader demo → küçük sermaye → ölçek.

---

## 🚀 Çalıştırma

```bash
pip install -r requirements.txt          # ccxt sadece --live için
# PAPER (güvenli varsayılan), tek döngü:
python prop_funded_bot.py --once --equity 100000
# Otonom (4H boundary'de uyanır):
python prop_eval_bot.py --equity 10000
# Cron (deploy/tirad.cron'a bak):
#   1 0,4,8,12,16,20 * * *  python prop_eval_bot.py --once >> eval.log 2>&1
```
**Canlı veri Binance public REST'ten gelir (API anahtarı GEREKMEZ).** `--live` için `BINANCE_KEY`/`BINANCE_SECRET` env + ccxt.

## 📁 Yapı
```
tirad_core.py        # saf motor: indikatör + sinyal + sizing + risk + paper-portföy
tirad_runner.py      # canlı makine: Binance fetch + broker + 4H döngü + payout/target
sprint/eval/fast/funded_bot.py  # 4 ince config (tek doğruluk-kaynağı paylaşır)
research/            # tüm deneyler (falsify, monte_carlo, hyro, stress) + 5.4y veri
deploy/              # deploy.sh, cron, analyze.py (durum çekme/analiz)
```

## 🔁 Araştırmayı yeniden üret
```bash
cd research
python falsify.py          # ① giriş edge'i (dose-response + null)
python falsify_phase.py    # ② faz kapısı (PE/VR macro-veto)
python prop_sim.py 10000   # uçtan-uca compound
python monte_carlo.py      # P(geçiş) dağılımı
python stress_mc.py        # gerçekçi sürtünme (gap+funding)
```

---
*Disiplin: acımasız doğrulama, sonra ölçek. Holy Grail değil — onu kovalayan dürüst bir süreç.*
