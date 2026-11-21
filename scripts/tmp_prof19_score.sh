#!/bin/bash
curl -s --max-time 5 http://127.0.0.1:8731/health
echo
/home/thomas/LivingCode/orchestration/scripts/laya_bridge.py score --state-context "Проекты Живого Кода: рой агентов-кодеров, локальные LLM, UI-гейты, самообучение роя" < /home/thomas/LivingCode/orchestration/scripts/tmp_prof19_topics.txt