#!/usr/bin/env bash
# Автоматическая установка локального судьи Laya и optional warm-сервиса.
#
# Контракт:
#   * создаёт ~/LivingCode/venvs/laya (Python 3.12);
#   * ставит CPU torch + laya[serve,onnx];
#   * скачивает convaiinnovations/laya-multilingual в ~/LivingCode/models;
#   * ставит systemd --user unit, но НЕ включает и НЕ запускает его;
#   * идемпотентен: уже установленные части проверяются и переиспользуются.
set -euo pipefail

ROOT="${LIVING_CODE_ROOT:-/home/thomas/LivingCode}"
ORC="${ORC:-$ROOT/orchestration}"
VENV="$ROOT/venvs/laya"
MODEL_DIR="$ROOT/models/laya-multilingual"
MODEL_REPO="${LAYA_MODEL_REPO:-convaiinnovations/laya-multilingual}"
PYTHON_VERSION="${LAYA_PYTHON_VERSION:-3.12}"
UNIT_NAME="laya-warm.service"
UNIT_SOURCE="$ORC/systemd/laya-warm.service"
UNIT_TARGET="$HOME/.config/systemd/user/$UNIT_NAME"

log() { printf '[install-laya] %s\n' "$*"; }
die() { printf '[install-laya] ERROR: %s\n' "$*" >&2; exit 1; }

[ -d "$ORC" ] || die "нет каталога оркестрации: $ORC"
command -v uv >/dev/null || die "uv не найден в PATH"

mkdir -p "$ROOT/venvs" "$ROOT/models" "$HOME/.config/systemd/user"

# 1. Python + CPU torch + Laya.
if [ ! -x "$VENV/bin/python" ]; then
    log "создаю venv: $VENV (Python $PYTHON_VERSION)"
    uv venv -p "$PYTHON_VERSION" "$VENV"
else
    log "venv уже существует: $VENV"
fi

if ! "$VENV/bin/python" -c 'import torch' >/dev/null 2>&1; then
    log "ставлю CPU torch"
    uv pip install -p "$VENV/bin/python" \
        --index-url https://download.pytorch.org/whl/cpu torch
else
    log "torch уже установлен"
fi

if ! "$VENV/bin/python" -c 'import laya' >/dev/null 2>&1; then
    log "ставлю laya[serve,onnx]"
    uv pip install -p "$VENV/bin/python" 'laya[serve,onnx]'
else
    log "laya уже установлен"
fi

# 2. Checkpoint. Пустой/повреждённый каталог перекачиваем.
if [ -f "$MODEL_DIR/model.safetensors" ] && [ -f "$MODEL_DIR/encoder/config.json" ]; then
    log "чекпоинт уже существует: $MODEL_DIR"
else
    log "скачиваю чекпоинт: $MODEL_REPO → $MODEL_DIR"
    "$VENV/bin/hf" download "$MODEL_REPO" --local-dir "$MODEL_DIR"
fi

[ -f "$MODEL_DIR/model.safetensors" ] || die "чекпоинт не установлен: $MODEL_DIR/model.safetensors"
[ -x "$VENV/bin/python" ] || die "venv Python не найден: $VENV/bin/python"

# 3. Optional warm unit: только установить, не enable/start.
# Если target уже является symlink на source — оставляем как есть. Если unit
# ранее был enabled/active, installer не меняет это состояние: он лишь
# гарантирует наличие файла, а политику запуска решает владелец.
if command -v systemctl >/dev/null && [ -f "$UNIT_SOURCE" ]; then
    if [ -L "$UNIT_TARGET" ] && [ "$(readlink -f "$UNIT_TARGET")" = "$(readlink -f "$UNIT_SOURCE")" ]; then
        log "unit уже установлен: $UNIT_TARGET"
    else
        install -m 0644 "$UNIT_SOURCE" "$UNIT_TARGET"
        log "unit установлен: $UNIT_TARGET"
    fi
    systemctl --user daemon-reload
    log "warm-сервис намеренно НЕ включён и НЕ запущен; включение — отдельная ручная команда"
else
    log "systemd недоступен или unit отсутствует — тёплый сервис пропущен"
fi

log "Laya готова (cold path): $VENV/bin/python $ORC/scripts/laya_bridge.py"
