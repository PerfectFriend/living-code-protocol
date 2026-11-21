#!/bin/bash
# Обёртка Аудитора — слот 20 минут, триггерится кодером через LV-auditor (f683abe80fb5).
# Ψ-FIX 19.10.2026: промпт вынесен в файл wrappers/prompts/auditor.txt; маркер теперь
# несёт ИМЯ проекта "[TRIGGER_LORD] ProjectN" (было "[TRIGGER_LORD] lord-of-code" —
# Владыка не понимал, какой проект аудирован); мёртвый hermes send вырезан; бюджет 1200с.
set -o pipefail
export LIVING_CODE_ROLE="Аудитор"
DIR=/home/thomas/LivingCode/orchestration/scripts
export LIVING_CODE_CRON_BUDGET=900
PROMPT=$(cat "$DIR/wrappers/prompts/auditor.txt")
NEXT_JOB_ID="80487bc08a9c"  # LV-lord-of-code

/usr/bin/python3 "$DIR/living_code_agent_wrapper.py" "$PROMPT" "$NEXT_JOB_ID" "mistralai/mistral-large-4-1t-a52b" "nvidia"
