#!/bin/bash
# Последовательный запуск ролей Протокола Живого Кода (без параллелизма моделей).
# Использование: run_lv_chain.sh <role:promptfile:model:provider> ...
# Каждый шаг: flock, затем living_code_agent_wrapper.py с пустым NEXT_JOB_ID
# (следующую роль запускаем мы сами — цепочка строго последовательная).
set -u
DIR=/home/thomas/LivingCode/orchestration/scripts
LOCK=/tmp/lv_chain.lock
LOG=/tmp/lv_chain.log
exec 9>"$LOCK"
flock -n 9 || { echo "[$(date -Is)] chain уже запущена, выход" >> "$LOG"; exit 0; }
echo "[$(date -Is)] === CHAINE START ===" >> "$LOG"
for spec in "$@"; do
  IFS='|' read -r role promptfile model provider <<< "$spec"
  echo "[$(date -Is)] >>> ROLE $role (model=$model)" >> "$LOG"
  PROMPT=$(cat "$DIR/wrappers/prompts/$promptfile")
  timeout 3600 /usr/bin/python3 "$DIR/living_code_agent_wrapper.py" "$PROMPT" "" "$model" "$provider" >> "$LOG" 2>&1
  rc=$?
  echo "[$(date -Is)] <<< ROLE $role rc=$rc" >> "$LOG"
done
echo "[$(date -Is)] === CHAIN DONE ===" >> "$LOG"
