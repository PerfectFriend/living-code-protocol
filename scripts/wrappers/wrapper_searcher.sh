#!/bin/bash
# Искатель — обёртка движка Живого Кода (переведена из агентного режима 02.10.2026).
# Агентные задачи шли мимо движка: получали HTTP 429 на выжженной модели и падали,
# поэтому модель не ротировалась. Теперь роль идёт через living_code_agent_wrapper.py,
# который сам обходит исчерпанные квоты (см. FREE_POOL в движке).
set -o pipefail
export LIVING_CODE_ROLE="Искатель"
export LIVING_CODE_CRON_BUDGET=2700   # слот Искателя 45 мин (промпт, шаг 0)
DIR=/home/thomas/LivingCode/orchestration/scripts
PROMPT=$(cat "$DIR/wrappers/prompts/searcher.txt")

# Скиллы Искателя: agent-reach — интернет по 15 платформам (X/Reddit/GitHub/YouTube…),
# obsidian — работа с Хранилищем (vault). Предзагружаются движком (`hermes chat -s`),
# иначе агент не знает этими инструментами пользоваться.
# ВАЖНО: `note-taking/obsidian`, а НЕ `obsidian` — в ~/.hermes/skills есть
# ДВА скилла с именем obsidian, резолвер отказывается угадывать при коллизии имён
# и роняет запуск (см. комментарий в wrapper_professor.sh).
SKILLS="note-taking/obsidian,agent-reach"

# Искатель триггерит Профессора (LV-professor). Профессор сам по себе
# запускается каждый час (0 * * * *, H-step 2026-11-08) как источник тем — но и по триггеру тоже,
# поэтому здесь явная связка, а не пустой NEXT_JOB_ID.
NEXT_JOB_ID="3e18b5951ee5"

/usr/bin/python3 "$DIR/living_code_agent_wrapper.py" "$PROMPT" "$NEXT_JOB_ID" "mistralai/mistral-large-4-1t-a52b" "nvidia" "$SKILLS"
