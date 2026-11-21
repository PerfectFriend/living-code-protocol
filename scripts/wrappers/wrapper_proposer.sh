#!/bin/bash
# Обёртка Proposer — предлагает правки самого протокола по PPC (план v3, Фаза 2).
# Применение изменений — отдельный probe/compose, не эта роль.
set -o pipefail
export LIVING_CODE_ROLE="Proposer протокола"
DIR=/home/thomas/LivingCode/orchestration/scripts
export LIVING_CODE_CRON_BUDGET=1200
PROMPT=$(cat "$DIR/wrappers/prompts/proposer.txt")

/usr/bin/python3 "$DIR/living_code_agent_wrapper.py" "$PROMPT" "" "mistralai/mistral-large-4-1t-a52b" "nvidia"
echo "[proposer] движок завершился rc=$?"
