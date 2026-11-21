#!/usr/bin/env bash
# Бэкап конфига Живого Кода: git push + rsync на внешний диск F2DB-14E5.
# Фаза 0 плана эволюции (EVOLUTION_PLAN_AGENCY_AGENTS_20260927.md): блокер, до всего остального.
# Бэкапит: orchestration (git), ~/.hermes/config.yaml, jobs.json, PLAN_AUDIT, journal роя.
set -euo pipefail

ORC="/home/thomas/LivingCode/orchestration"
H="$HOME/.hermes"
DISK="/run/media/thomas/F2DB-14E5"
DEST="$DISK/backups/living-code"
STAMP="$(date +%F_%H%M%S)"

log() { printf '[backup-config] %s\n' "$*"; }

[ -d "$ORC/.git" ] || { echo "нет $ORC/.git — не git-репозиторий"; exit 1; }
[ -d "$DISK" ] || { echo "диск $DISK не примонтирован — бэкап только git-push, rsync пропущен"; DISK_OK=0; }
DISK_OK="${DISK_OK:-1}"

# ── 1. git: коммит незакреплённого + push ──────────────────────────────────
cd "$ORC"
if ! git diff --quiet || ! git diff --cached --quiet || [ -n "$(git ls-files --others --exclude-standard)" ]; then
    git add -A
    git commit -q -m "chore(backup): автоснимок перед эволюцией $STAMP" || log "нечего коммитить"
fi
BRANCH="$(git branch --show-current)"
if git push -q origin "$BRANCH" 2>/dev/null; then
    log "git push origin/$BRANCH: ok"
else
    log "git push origin/$BRANCH: НЕ УДАЛСЯ (remote недоступен?) — git bundle обязателен"
fi

# ── 2. git bundle — страховка, если remote заблокирован ────────────────────
mkdir -p "$DEST"
git bundle create "$DEST/orchestration-$STAMP.bundle" --all 2>/dev/null \
    && log "bundle: orchestration-$STAMP.bundle" \
    || log "bundle: НЕ УДАЛСЯ"

# ── 3. rsync ключевых файлов на диск ───────────────────────────────────────
if [ "$DISK_OK" = "1" ]; then
    # Клоны с вложенным .git копируем БЕЗ .git (решение владельца: gitlink/сабмодуль
    # в бэкапе не нужен — паспорт-материал важнее истории клонирования).
    rsync -a --exclude='.git' "$ORC/" "$DEST/orchestration/"
    log "rsync orchestration → $DEST/orchestration/ (без .git)"
    rsync -a --exclude='.git' "$HOME/LivingCode/knowledge-base/" "$DEST/knowledge-base/"
    log "rsync knowledge-base → $DEST/knowledge-base/ (без .git)"
    # Копия PLAN_AUDIT, journal, QUEUE
    mkdir -p "$DEST/state-$STAMP"
    for f in "$HOME/LivingCode/PLAN_AUDIT.md" "$HOME/LivingCode/agents/journal.md" "$HOME/LivingCode/QUEUE.md" "$HOME/LivingCode/EVOLUTION_PLAN.md"; do
        [ -f "$f" ] && cp "$f" "$DEST/state-$STAMP/" && log "копия: $(basename "$f")"
    done
    # jobs.json + config.yaml (свежие, из живого ~/.hermes)
    [ -f "$H/cron/jobs.json" ] && cp "$H/cron/jobs.json" "$DEST/state-$STAMP/jobs.json" && log "копия: jobs.json (живой)"
    [ -f "$H/config.yaml" ] && cp "$H/config.yaml" "$DEST/state-$STAMP/config.yaml" && log "копия: config.yaml (живой)"
    # Скиллы — полный слепок (45 МБ), раз в сутки может быть тяжело, но надёжно
    if [ -d "$H/skills" ]; then
        mkdir -p "$DEST/hermes-skills"
        rsync -a --delete "$H/skills/" "$DEST/hermes-skills/"
        log "скиллы: $(find "$DEST/hermes-skills" -name SKILL.md | wc -l) SKILL.md → $DEST/hermes-skills/"
    fi
fi

# ── 4. Итог ────────────────────────────────────────────────────────────────
log "ГОТОВО. Содержимое $DEST:"
ls -lt "$DEST" 2>/dev/null | head -n 8 || true
