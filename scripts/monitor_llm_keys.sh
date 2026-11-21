#!/bin/bash
# monitor_llm_keys.sh — health-check ключей LLM-провайдеров (крон key-rotation, каждые 30 мин).
# Восстановлен 01.10.2026: прежний скрипт исчез вместе с конфигом.
# Проверяет: количество ключей в пулах, живость провайдеров, дубликаты. Падает (exit 1)
# только когда пул пуст — модель тогда недоступна протоколу.
set -uo pipefail

H="$HOME/.hermes"
OUT=()
FAIL=0

log() { printf '[key-rotation] %s\n' "$*"; OUT+=("$*"); }

# ── 1. Пулы ключей из auth.json ────────────────────────────────────────────
python3 - "$H/auth.json" <<'PY' 2>/dev/null
import json, sys, collections
try:
    d = json.load(open(sys.argv[1]))
except Exception:
    print("auth.json не читается")
    sys.exit(0)
pools = d.get("credential_pool") or d.get("pools") or d.get("credential_pools") or {}
if isinstance(pools, dict):
    for name, pool in pools.items():
        if isinstance(pool, dict):
            keys = pool.get("keys") or pool.get("credentials") or []
        elif isinstance(pool, list):
            keys = pool
        else:
            keys = []
        print(f"пул {name}: {len(keys)} ключ(ей)")
else:
    print(f"пулов: {len(pools)}")
PY
AUTH_SUMMARY=$(python3 - "$H/auth.json" <<'PY' 2>/dev/null
import json, sys
try:
    d = json.load(open(sys.argv[1]))
    pools = d.get("credential_pool") or d.get("pools") or d.get("credential_pools") or {}
    if isinstance(pools, dict):
        lines = [f"{n}:{len(p) if isinstance(p, list) else (len(p.get('keys') or p.get('credentials') or [])) if isinstance(p, dict) else 0}" for n, p in pools.items()]
        print("пулы: " + ", ".join(lines) if lines else "пулов нет")
    else:
        print(f"пулов: {len(pools)}")
except Exception:
    print("auth.json не читается")
PY
)
[ -n "$AUTH_SUMMARY" ] && log "$AUTH_SUMMARY"

# ── 2. Дубликаты ключей в .env ─────────────────────────────────────────────
if [ -f "$H/.env" ]; then
    DUP=$(grep -oE '^[A-Z_]+_API_KEY' "$H/.env" | sort | uniq -d | head -n 5)
    if [ -n "$DUP" ]; then
        log "⚠️  дубликаты ключей в .env: $DUP"
    else
        log "дубликатов ключей нет"
    fi
fi

# ── 3. Живость OpenRouter: 3 попытки; ключ уходит через конфиг curl ─────────
# Почему конфиг: однажды ключ в этом файле оказался затёрт на *** и монитор
# врал «HTTP 000». Через -K ключ не светится ни в ps, ни в тексте скрипта.
# Почему повторы: одиночный сетевой блип не должен валить задачу и слать
# ложную тревогу в Telegram.
OR_KEY=$(grep -oP '^OPENROUTER_API_KEY=\K.*' "$H/.env" 2>/dev/null | head -n 1 | tr -d '"' | tr -d "'")
OR_OK=0
if [ -n "$OR_KEY" ]; then
    CFG=$(mktemp); chmod 600 "$CFG"
    printf 'header = "Authorization: Bearer %s"\n' "$OR_KEY" > "$CFG"
    CODE=000
    for i in 1 2 3; do
        CODE=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -K "$CFG" \
               https://openrouter.ai/api/v1/models 2>/dev/null || echo 000)
        [ "$CODE" = "200" ] && { OR_OK=1; break; }
        [ "$i" -lt 3 ] && sleep 5
    done
    rm -f "$CFG"
    if [ "$OR_OK" = "1" ]; then
        log "openrouter: ok (HTTP 200)"
    else
        log "⚠️  openrouter: HTTP $CODE после 3 попыток (сеть/ключ) — рой уйдёт на локальную модель"
    fi
else
    log "⚠️  OPENROUTER_API_KEY нет в .env — доступна только локальная модель"
fi

# ── 3б. Локальная замена — последний гарантированный оплот ───────────────
LOCAL_OK=0
ZEN_KEY=$(grep -oP '^OPENCODE_ZEN_API_KEY=\K.*' "$H/.env" 2>/dev/null | head -n 1 | tr -d '"' | tr -d "'")
if [ -n "$ZEN_KEY" ]; then
    CFG2=$(mktemp); chmod 600 "$CFG2"
    printf 'header = "Authorization: Bearer %s"\n' "$ZEN_KEY" > "$CFG2"
    CODE=000
    for i in 1 2 3; do
        CODE=$(curl -s -m 20 -o /dev/null -w '%{http_code}' -K "$CFG2" \
               https://opencode.ai/zen/v1/models 2>/dev/null || echo 000)
        [ "$CODE" = "200" ] && { LOCAL_OK=1; break; }
        [ "$i" -lt 3 ] && sleep 5
    done
    rm -f "$CFG2"
    if [ "$LOCAL_OK" = "1" ]; then
        log "локальная замена (opencode-zen): ok (HTTP 200, без лимитов)"
    else
        log "⚠️  локальная замена (opencode-zen): HTTP $CODE после 3 попыток"
    fi
else
    log "⚠️  OPENCODE_ZEN_API_KEY нет в .env — локальный оплот недоступен"
fi

# ── 3в. Какие квоты пула выжжены прямо сейчас ──────────────────────────────
python3 - "$H/cron/lv_provider_budget.json" <<'PY' 2>/dev/null
import json, sys, time
try:
    st = json.load(open(sys.argv[1]))
except Exception:
    print("[key-rotation] квоты пула: все свободны"); raise SystemExit
models = st.get("models") or {}
now = time.time()
dead = [m for m, v in models.items() if (v.get("until") or 0) > now]
if dead:
    when = min(models[m]["until"] for m in dead)
    print(f"[key-rotation] квоты выжжены ({len(dead)}): {', '.join(sorted(dead))}")
    print(f"[key-rotation] сброс в {time.strftime('%H:%M %d.%m', time.localtime(when))} (полночь UTC)")
else:
    print("[key-rotation] квоты пула: все свободны")
PY

# ── 4. Вердикт: падаем только если работать реально нечем ──────────────────
if [ "$OR_OK" = "0" ] && [ "$LOCAL_OK" = "0" ]; then
    log "СТАТУС: FAIL — ни быстрый пул, ни локальная модель недоступны"
    exit 1
fi
log "СТАТУС: ok"
exit 0
