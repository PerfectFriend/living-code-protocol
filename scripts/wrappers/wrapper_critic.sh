#!/bin/bash
# Обёртка L3-Критика — независимый review в чистом контексте (план v3, Фаза 1).
# next_job_id пустой: критик — конечная точка, его findings читает Продюсер.
set -o pipefail
export LIVING_CODE_ROLE="L3-Критик"
DIR=/home/thomas/LivingCode/orchestration/scripts
export LIVING_CODE_CRON_BUDGET=600
PROMPT=$(cat "$DIR/wrappers/prompts/critic.txt")

/usr/bin/python3 "$DIR/living_code_agent_wrapper.py" "$PROMPT" "" "mistralai/mistral-large-4-1t-a52b" "nvidia"
echo "[critic] движок завершился rc=$?"
