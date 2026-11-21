#!/bin/bash
# Wrapper for LV-extinction-check job [9a0002295b51]
# Daily Extinction Check (03:00): ноды, мёртвые >7 дней → Evolution/Archive/ + graph.yaml + commit.
# Восстановлено: прежний workdir /home/thomas/GodModeCoder/scripts не существует,
# скрипт extinction.py живёт в /home/thomas/LivingCode/scripts.

set -o pipefail
ROOT=/home/thomas/LivingCode
EXT="$ROOT/scripts/extinction.py"
LOG_DIR="$ROOT/reports"
STAMP=$(date +%Y%m%d-%H%M)
REPORT="$LOG_DIR/extinction-$STAMP.md"

mkdir -p "$LOG_DIR"

if [ ! -f "$EXT" ]; then
  echo "❌ extinction.py не найден: $EXT"
  exit 1
fi

cd "$ROOT" || exit 1
{
  echo "# Extinction Check — $STAMP"
  echo
  echo '```'
  /usr/bin/python3 "$EXT" --min-days 7 2>&1
  echo '```'
} | tee "$REPORT"

# Кому, по правилам протокола, доставляется отчёт — задаёт кроновая доставка (deliver).
exit 0
