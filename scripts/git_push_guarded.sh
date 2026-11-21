#!/bin/bash
# git_push_guarded.sh — пуш в репозиторий протокола ТОЛЬКО через гейт владельца
# (Approval-Queue fault line: push в protected remote — действие «наружу»).
# Использование: git_push_guarded.sh [args для git push]  (напр. origin main)
set -o pipefail
DIR=/home/thomas/LivingCode/orchestration/scripts
DETAIL="git push $* @ $(git -C "$(pwd)" rev-parse --short HEAD 2>/dev/null || echo '?')"
if ! /usr/bin/python3 "$DIR/guard_action.py" check push-protected "$DETAIL"; then
  echo "⛔ Пуш заблокирован гейтом владельца. Если это санкционировано — владелец выполняет:" >&2
  echo "   python3 $DIR/guard_action.py approve push-protected '<причина>'" >&2
  exit 2
fi
exec git push "$@"
