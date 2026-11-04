#!/bin/bash
# Обёртка Super-Supervisor — пост-верификация и авто-релиз (Фаза 0).
# Запускается каждым часом кроном LV-super-supervisor.
# Проверяет здоровье кронов, git-чистоту проектов, вердикты Владыки,
# l3_critic и, при ГОРЯЧИЙ + stabilen, триггерит Продюсера на релиз.
set -o pipefail
export LIVING_CODE_ROLE="Super-Supervisor"
export LIVING_CODE_CRON_BUDGET=3600   # слот 60 мин (пост-верификация + релиз)
DIR=/home/thomas/LivingCode/orchestration/scripts

# Запуск Python-скрипта Super-Supervisora
/usr/bin/python3 "$DIR/supervisor_cron.py"
SUPER_RC=$?
echo "[super-supervisor] завершён rc=$SUPER_RC"

exit $SUPER_RC
