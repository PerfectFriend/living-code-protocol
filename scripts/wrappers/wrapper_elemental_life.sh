#!/bin/bash
# Роль закреплена за моделью: mistralai/mistral-large-4-1t-a52b (nvidia) — nemotron-3-ultra-550b-a55b мёртвая с 01.11.2026 (minimax висел 39-120с).
# Обслуживающие роли идут на живой mistralai/mistral-large-4-1t-a52b: судит Laya, а не LLM (см. orchestration/LAYA_WARM_SERVICE.md).
# Wrapper for LV-coder-elemental-life job [f9365e6513e5] — восстановлена из промпта задачи
# Laya-хуки: согласно карте интеграции роли кодер/продюсер Laya не решают
# (вердикты — у Владыки и Аудитора); здесь только движок с фолбэком моделей.

export LIVING_CODE_ROLE="Кодер Elemental Life"
PROMPT=$(cat <<'EOF'
Ты Агент-Кодер проекта Elemental Life в Протоколе Живого Кода. Твоё имя и отчество — придумай сам при первом запуске и запиши в журнал.

1. Прочитай /home/thomas/LivingCode/agents/journal.md — изучи заметки от Профессора, Искателя и Аудитора.
2. Прочитай и обнови план: /home/thomas/LivingCode/Projects/elemental-life/PLAN.md
3. Выбери 10 пунктов из плана.
4. Выполни 10 циклов эволюции проекта: код, тесты, комментарии. Не делай ошибок.
5. Составь отчёт: /home/thomas/LivingCode/reports/coder-elemental-life-$(date +%Y%m%d-%H%M).md
6. Отправь Инквизитору: curl -s -X POST "https://api.telegram.org/bot[REDACTED]/sendDocument" -F chat_id=-1004431090317 -F message_thread_id=252 -F caption="Отчёт кодера elemental-life" -F document="@/home/thomas/LivingCode/reports/coder-elemental-life-$(date +%Y%m%d-%H%M).md"
7. Оставь заметку в журнале переписки о проделанной работе.
8. Триггер Аудитора: запиши в журнал "[TRIGGER_AUDITOR] elemental-life".
EOF
)

NEXT_JOB_ID="f683abe80fb5"

/usr/bin/python3 /home/thomas/.hermes/scripts/living_code_agent_wrapper.py "$PROMPT" "$NEXT_JOB_ID" "mistralai/mistral-large-4-1t-a52b" "nvidia"
