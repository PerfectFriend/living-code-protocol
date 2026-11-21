#!/usr/bin/env bash
# Установка роя на чистой машине: симлинк скриптов + восстановление конфига + проверка.
set -euo pipefail

ORC="/home/thomas/LivingCode/orchestration"
log() { printf '[install] %s\n' "$*"; }

command -v hermes >/dev/null || { echo "[install] hermes не найден в PATH"; exit 1; }
[ -d "$ORC" ] || { echo "[install] нет $ORC"; exit 1; }

bash "$ORC/bin/restore-config.sh"
bash "$ORC/bin/install-laya.sh"

log "проверка состояния"
bash "$ORC/bin/verify.sh"

cat <<'EOF'

Дальше:
  • hermes auth add nvidia <NVIDIA_API_KEY>     (ключи в git не хранятся)
  • systemd-демон роя:  systemctl --user enable --now livingcode-watchdog
  • включать задачи поэтапно (см. README.md → «Восстановление с нуля»)
EOF
