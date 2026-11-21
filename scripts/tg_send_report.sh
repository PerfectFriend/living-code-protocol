#!/usr/bin/env bash
# Отправка отчёта-документа в Telegram-чат владельца.
# Токен читается из ~/.hermes/.env и НИКОГДА не печатается.
set -euo pipefail
ENV_FILE="$HOME/.hermes/.env"
FILE_PATH="$1"
BOT_TOKEN=$(grep -E '^TELEGRAM_BOT_TOKEN=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'"'')
CHAT_ID=$(grep -E '^TELEGRAM_CHAT_ID=' "$ENV_FILE" | head -1 | cut -d= -f2- | tr -d '"'"'"'')
[ -n "$BOT_TOKEN" ] && [ -n "$CHAT_ID" ] || { echo "Нет токена/чата в .env"; exit 1; }
curl -s -F "chat_id=$CHAT_ID" -F "document=@$FILE_PATH" -F "caption=Аудит готовности CatVanGoghFlutter — 21.10.2026" "https://api.telegram.org/bot$BOT_TOKEN/sendDocument" | head -c 300
echo
