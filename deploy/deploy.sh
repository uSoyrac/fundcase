#!/usr/bin/env bash
# TIRAD sunucu kurulumu (Ubuntu/Debian). Kullanım: bash deploy/deploy.sh
set -e
DIR=${1:-/opt/fundcase}
echo "TIRAD deploy → $DIR"
mkdir -p "$DIR/logs"
cp -r tirad_core.py tirad_runner.py *_bot.py requirements.txt "$DIR/"
cd "$DIR"
python3 -m venv venv && ./venv/bin/pip install -q -r requirements.txt
echo "✓ kuruldu. Test (paper, tek döngü):"
./venv/bin/python prop_eval_bot.py --once --equity 10000
echo "Cron eklemek için: crontab -e  → deploy/tirad.cron içeriğini yapıştır (yolları düzelt)."
echo "Otonom başlatmak için (nohup):  nohup ./venv/bin/python prop_funded_bot.py --equity 100000 >> logs/funded.log 2>&1 &"
