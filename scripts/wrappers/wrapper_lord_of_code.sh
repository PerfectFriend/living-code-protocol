#!/bin/bash
# Владыка Кода — обёртка движка Живого Кода (переведена из агентного режима 02.10.2026).
# Агентные задачи шли мимо движка: получали HTTP 429 на выжженной модели и падали,
# поэтому модель не ротировалась. Теперь роль идёт через living_code_agent_wrapper.py,
# который сам обходит исчерпанные квоты (см. FREE_POOL в движке).
set -o pipefail
export LIVING_CODE_ROLE="Владыка Кода"
DIR=/home/thomas/LivingCode/orchestration/scripts
export LIVING_CODE_CRON_BUDGET=600  # Ψ-FIX 19.10.2026: слот 15 минут, дальше Продюсер
PROMPT=$(cat "$DIR/wrappers/prompts/lord_of_code.txt")

NEXT_JOB_ID="90f76ccbbdab"  # LV-producer — конец цепочки аудитор→владыка→продюсер

/usr/bin/python3 "$DIR/living_code_agent_wrapper.py" "$PROMPT" "$NEXT_JOB_ID" "mistralai/mistral-large-4-1t-a52b" "nvidia"
