#!/usr/bin/env bash
# Восстановление конфига Hermes из репозитория оркестрации.
# Все задачи после восстановления принудительно ставятся на паузу — ничего не стартует само.
set -euo pipefail

ORC="/home/thomas/LivingCode/orchestration"
H="$HOME/.hermes"
STAMP="$(date +%F_%H%M%S)"

log() { printf '[restore-config] %s\n' "$*"; }

[ -f "$ORC/jobs/jobs.json" ] || { echo "нет $ORC/jobs/jobs.json — сначала клонируй репозиторий"; exit 1; }

# 1. Скиллы
if [ -d "$ORC/skills-export" ]; then
    mkdir -p "$H/skills"
    rsync -a "$ORC/skills-export/" "$H/skills/"
    log "скиллы: $(find "$H/skills" -name SKILL.md | wc -l) SKILL.md"
fi

# 2. config.yaml (старый сохраняем)
if [ -f "$ORC/hermes-config/config.yaml" ]; then
    [ -f "$H/config.yaml" ] && cp "$H/config.yaml" "$H/config.yaml.bak-$STAMP" && log "старый конфиг → config.yaml.bak-$STAMP"
    cp "$ORC/hermes-config/config.yaml" "$H/config.yaml"
    log "config.yaml восстановлен"
fi

# 3. Кроны — все на паузу
mkdir -p "$H/cron"
if [ -f "$H/cron/jobs.json" ]; then
    cp "$H/cron/jobs.json" "$H/cron/jobs.json.bak-$STAMP"
    log "старый реестр кронов → jobs.json.bak-$STAMP"
fi
cp "$ORC/jobs/jobs.json" "$H/cron/jobs.json"
python3 - "$H/cron/jobs.json" <<'PY'
import json, sys, datetime
p = sys.argv[1]
d = json.load(open(p))
now = datetime.datetime.now().astimezone().isoformat()
n = 0
for j in d.get("jobs", []):
    j["enabled"] = False
    j["state"] = "paused"
    j["next_run_at"] = None
    j["paused_at"] = now
    j["paused_reason"] = "восстановлено из living-code: не запускать до поэтапного включения"
    n += 1
json.dump(d, open(p, "w"), ensure_ascii=False, indent=2)
print(f"[restore-config] кроны: {n} задач, все paused")
PY

# 4. Симлинк скриптов
if [ ! -L "$H/scripts" ]; then
    [ -e "$H/scripts" ] && mv "$H/scripts" "$H/scripts.old-$STAMP"
    ln -s "$ORC/scripts" "$H/scripts"
    log "симлинк ~/.hermes/scripts → $ORC/scripts"
else
    log "симлинк ~/.hermes/scripts уже есть"
fi

cat <<'EOF'

Что нужно доделать руками:
  1) ключи провайдеров — в git их нет (см. hermes-config/KEYS.md):
       hermes auth add nvidia <NVIDIA_API_KEY>
  2) проверить: hermes cron list  (все задачи должны быть paused)
  3) сверить:   bash bin/verify.sh
  4) включать задачи поэтапно, начиная с LV-config-backup и LV-maintenance
EOF
