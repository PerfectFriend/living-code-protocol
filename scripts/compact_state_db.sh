#!/bin/bash
# compact_state_db.sh — обёртка для компактии state.db с остановкой gateway.
#
# Использование:
#   ./compact_state_db.sh
#
# Процедура:
#   1. Останавливает gateway (systemd / pkill)
#   2. Запускает hermes sessions optimize-storage --yes
#   3. Перезапускает gateway

set -euo pipefail

HERMES_BIN="${HERMES_BIN:-hermes}"
STATE_DB="${HOME}/.hermes/state.db"

echo "🛑 Остановка gateway..."
if systemctl list-units --type=service 2>/dev/null | grep -q hermes-gateway; then
    systemctl stop hermes-gateway || true
else
    pkill -f "gateway run" 2>/dev/null || true
fi
# cron.scheduler держит state.db не меньше gateway — optimize-storage без этого откажется
pkill -f "cron.scheduler" 2>/dev/null || true
# в '*'-шаблоне pkill -f "hermes.*gateway" не ловил; ловим явно
sleep 2

echo "🔄 Компактия state.db..."
python3 "${HOME}/LivingCode/orchestration/scripts/compact_state_db.py" --yes

echo "🚀 Перезапуск gateway..."
if systemctl list-units --type=service 2>/dev/null | grep -q hermes-gateway; then
    systemctl start hermes-gateway || true
else
    nohup hermes gateway start > /dev/null 2>&1 &
fi
sleep 3
# cron.scheduler поднимается вместе с gateway; если нет — пинаем ещё раз
pgrep -f "cron.scheduler" >/dev/null || nohup hermes gateway start >/dev/null 2>&1 &
echo "✅ Готово."
