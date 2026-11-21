#!/usr/bin/env bash
# Экспорт конфига Hermes в репозиторий оркестрации: git push + внешний диск.
# Это предохранитель против повторной потери конфига (авария Plasma → переустановка).
set -euo pipefail

ORC="/home/thomas/LivingCode/orchestration"
DISK="/run/media/thomas/F2DB-14E5"
DEST="$DISK/hermes-config"
BACKUPS="/home/thomas/LivingCode/backups"
STAMP="$(date +%F_%H%M)"
KEEP_TARBALLS=7

log() { printf '[backup-config] %s\n' "$*"; }

# 1. Слепки конфига (без секретов — ключи вычищаются шагом 3)
mkdir -p "$ORC/hermes-config" "$ORC/jobs" "$ORC/skills-export"
cp "$HOME/.hermes/config.yaml" "$ORC/hermes-config/config.yaml"
cp "$HOME/.hermes/cron/jobs.json" "$ORC/jobs/jobs.json"
rsync -a --delete "$HOME/.hermes/skills/" "$ORC/skills-export/"
log "слепки сняты: config.yaml, jobs.json, скиллы"

# 2. Вычистить реальные ключи из всего, что уходит в git
python3 "$ORC/scripts/redact_secrets.py" \
    "$ORC/skills-export" "$ORC/hermes-config" "$ORC/jobs" "$ORC/runtime"

# 3. Коммит и пуш
cd "$ORC"
git add -A
if git diff --cached --quiet; then
    log "изменений нет — коммит не нужен"
else
    git commit -q -m "backup: hermes config + cron registry $STAMP"
    log "коммит создан"
fi
if git push -q; then
    log "git push: OK"
else
    log "git push: ОШИБКА (проверь сеть/токен)"
fi

# 4. Копия на внешний диск (лучшее усилие: основной бэкап — git-резерв выше,
#  он уже сделан; сбой копии не должен мутировать статус джоба)
if mountpoint -q "$DISK"; then
    mkdir -p "$DEST"
    if rsync -a --delete "$ORC/jobs/" "$ORC/hermes-config/" "$DEST/"; then
        log "внешний диск: OK ($DEST)"
    else
        log "внешний диск: rsync сбой (код $?), джобу не сбрасываем"
    fi
else
    mkdir -p "$BACKUPS"
    TAR="$BACKUPS/hermes-config-$STAMP.tar.gz"
    if tar czf "$TAR" --ignore-failed-read --warning=no-file-changed -C "$HOME/.hermes" cron config.yaml skills 2>/dev/null; then
        ls -1t "$BACKUPS"/hermes-config-*.tar.gz 2>/dev/null | tail -n +$((KEEP_TARBALLS + 1)) | xargs -r rm --
        log "локальный архив: $TAR (держим $KEEP_TARBALLS копий)"
    else
        log "локальный архив: tar сбой (код $?), джобу не сбрасываем"
    fi
fi

log "готово"
