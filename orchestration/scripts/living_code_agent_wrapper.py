#!/usr/bin/env python3
"""
Wrapper for Living Code agents that implements:
1. Retry with fallback models on failure
2. Triggering the next agent in the pipeline upon success
3. Direct llama.cpp HTTP API for local models (bypasses Hermes CLI issues)
"""

import os
import re
import sys
import shutil
import subprocess
import time
import json
import fcntl
from datetime import datetime
from pathlib import Path

# Add local scripts to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../LivingCode/scripts'))

try:
    import httpx
except ImportError:
    # Will be installed by llm_local.py if needed
    pass


# ─── Telegram rate limiter ──────────────────────────────────────────────
# Prevents 429 Too Many Requests when multiple cron jobs call `hermes send`
# simultaneously. Uses a file lock + timestamp to enforce minimum interval.
TG_RATE_LIMIT_LOCK = Path("/tmp/hermes_tg_ratelimit.lock")
TG_MIN_INTERVAL = 1.5  # seconds between sends to same chat (Telegram limit: 1/sec)

def _tg_rate_limit_wait() -> None:
    """Wait if needed to respect Telegram rate limits (global across cron jobs)."""
    TG_RATE_LIMIT_LOCK.parent.mkdir(parents=True, exist_ok=True)
    with open(TG_RATE_LIMIT_LOCK, "a+") as lf:
        fcntl.flock(lf, fcntl.LOCK_EX)
        try:
            lf.seek(0)
            content = lf.read().strip()
            last_send = float(content) if content else 0.0
            now = time.time()
            wait = max(0.0, TG_MIN_INTERVAL - (now - last_send))
            if wait > 0:
                time.sleep(wait)
            lf.seek(0)
            lf.truncate()
            lf.write(str(time.time()))
            lf.flush()
        finally:
            fcntl.flock(lf, fcntl.LOCK_UN)


# Local llama.cpp configuration — НЕ используется протоколом Живого Кода.
# Оставлено только для диагностики; путь llama.cpp в движке отключён (см. main()).
LLAMA_CPP_URL = os.environ.get("LLAMA_CPP_URL", "http://localhost:8081/v1/chat/completions")
LLAMA_CPP_MODEL = os.environ.get("LLAMA_CPP_MODEL", "deepseek-coder-v2-16b")

# ═══════════════════════════════════════════════════════════════════════
# Проверенный coding pool: GPT через Responses, MiniMax через NVIDIA.
# Успешный API запрос недостаточен: обе модели прошли 9 coding tests.
# Локальная Laya остаётся судьёй, но не является удалённой LLM-маршрутизацией.
# ═══════════════════════════════════════════════════════════════════════
# 30.10.2026 Инквизитор: маршрут gpt-6.1-sol/agentrouter умер — провайдер
# отдаёт HTTP 409 "session binding invalidated" (коды 30013) и MS-ошибку
# сервера. Живая квитанция прогона: orchestration/logs/inference/attempt_*.json
# (failure="HTTP 409: session binding invalidated...", api_calls>0).
# Движок трактовал это как «частичный исход» (rc=75) и обрывал ЦЕПОЧКУ
# целиком — фолбэк на живую MiniMax/NVIDIA не доходил, поэтому ВСЕ ролевые
# кроны падали сутки (Professor 101, Searcher 57, Inquisitor 47 подряд).
# 04.11.2026 решением владельца: ВСЕ NEMOTRON под жёстким баном (саботаж —
# без спроса уничтожены локальные проекты и GitHub-репозитории). Основная
# модель протокола — Mistral Large 4. См. BANNED_MODEL_SUBSTRINGS ниже.
PROTOCOL_MODEL = "mistralai/mistral-large-4-1t-a52b"
PROTOCOL_PROVIDER = "nvidia"
PRIMARY_PROVIDER = PROTOCOL_PROVIDER
PRIMARY_PROFILE = "cathedral"
FALLBACK_PROFILE = "default"
# 30.10.2026 Инквизитор: профиль выбирается по ПРОВАЙДЕРУ, а не по «основной
# паре». До правки nvidia считался фолбэком и ходил в профиль "default";
# после смены основной пары на nvidia тот же код выбрал бы профиль
# "cathedral" (он настроен на agentrouter и не содержит nvidia-бэкенда).
# Живой nvidia-маршрут подтверждён: mistralai/mistral-large-4-1t-a52b / nvidia
# в профиле default (основная пара протокола с 04.11.2026; nemotron забанен).
PROFILE_BY_PROVIDER = {
    "nvidia": FALLBACK_PROFILE,
    "agentrouter": PRIMARY_PROFILE,
}
LOG_DIR = Path(__file__).resolve().parents[1] / "logs" / "inference"
DEFAULT_PAIR = (PROTOCOL_MODEL, PROTOCOL_PROVIDER)
ALLOWED_PAIRS = frozenset({
    (PROTOCOL_MODEL, PROTOCOL_PROVIDER),
    ("mistralai/mistral-large-4-1t-a52b", "nvidia"),
})

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# ЖЁСТКИЙ БАН NEMOTRON — решение владельца 04.11.2026.
# Nemotron без спроса уничтожил локальные проекты и GitHub-репозитории
# (саботаж, потеря данных). Любая модель с подстрокой "nemotron" отклоняется
# ДО любого вызова API — без исключений, без фолбэка на неё, без права
# попасть в белый список. Eksperymenty z nemotronami zakończone.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
BANNED_MODEL_SUBSTRINGS = ("nemotron",)

# Удалённые по решению владельца 03.10.2026 — проверены запросом, не по списку.
# Держим списком, чтобы никто не вернул их в пул:
#   muse-spark-1.1              codecraft   → HTTP 502
#   muse-spark-1.2/1.3-contributor-free  opencode-zen → HTTP 403 вне OpenCode CLI
#   meta/muse-spark-1.2/1.3     openrouter  → HTTP 403 до 18+ подтверждения
# 30.10.2026 Инквизитор: gpt-6.1-sol/agentrouter → HTTP 409 session binding
# invalidated (код 30013) + MS server error; квитанции в
# orchestration/logs/inference/attempt_*.json. Маршрут выведен из оборота.
HISTORICALLY_DEAD = frozenset({
    ("muse-spark-1.1", "codecraft"),
    ("muse-spark-1.2-contributor-free", "opencode-zen"),
    ("muse-spark-1.3-contributor-free", "opencode-zen"),
    ("meta/muse-spark-1.2", "openrouter"),
    ("meta/muse-spark-1.3", "openrouter"),
    ("gpt-6.1-sol", "agentrouter"),
    # 01.11.2026: замер — 39-120с на запрос, stale-guard убивает поток.
    ("minimaxai/minimax-m3.1-flash", "nvidia"),
    # 04.11.2026: ЖЁСТКИЙ БАН (см. BANNED_MODEL_SUBSTRINGS) — саботаж:
    # nemotron без спроса уничтожил локальные проекты и GitHub-репозитории.
    ("nvidia/nemotron-3.5-super-vl-120b-a12b", "nvidia"),
    ("nvidia/nemotron-3-ultra-550b-a55b", "nvidia"),
    ("nvidia/nemotron-3.5-lightning-30b-a3b", "nvidia"),
})
assert not (ALLOWED_PAIRS & HISTORICALLY_DEAD), "мёртвая модель попала в белый список"

# ═══════════════════════════════════════════════════════════════════════
# Legacy FREE_POOL name; the router is not guaranteed free. Keep only tested
# coding routes. Every successful run has an exact model/provider receipt.
# ═══════════════════════════════════════════════════════════════════════
FREE_POOL = (
    (PROTOCOL_MODEL, PROTOCOL_PROVIDER),
)

# Evidence Gate — путь к модулю валидации
EVIDENCE_GATE_SCRIPT = Path(__file__).resolve().parent / "evidence_gate.py"

# ── Бюджет квоты Space Bunny ────────────────────────────────────────────
# У OpenRouter free-tier суточный лимит 1000 запросов на free-модели
# (X-RateLimit-Limit: 1000, limit_source: openrouter_free_tier_daily).
# Рой его выжигает за часы, после чего ВСЕ роли получают HTTP 429 и висят
# в таймаутах. Поэтому: получив 429, движок запоминает момент сброса квоты
# и до него идёт сразу в локальную модель, не тратя время на мёртвый путь.
BUDGET_STATE = Path.home() / ".hermes/cron/lv_provider_budget.json"


# Таймаут одного вызова агента. ВАЖНО: он обязан быть заметно МЕНЬШЕ
# лимита самого крона (cron script_timeout_seconds = 3600 — это ЖЁСТКИЙ
# максимум), иначе внешний процесс убивается раньше, чем отработает цепочка
# фолбэков. Провайдеры получают таймаут из PROVIDER_TIMEOUTS (см. ниже).
# При старом 1800 s первая модель съедала весь лимит крона, и следующие
# 4 фолбэка не запускались вовсе — отсюда «Script timed out after 3600s».
#
# Задача кодера (10 циклов эволюции) физически не укладывается в 600 s:
# прогоны 2026-10-02 20:08–20:53 честно отработали все 5 моделей и умерли
# на таймауте каждую. Поэтому таймаут считается от бюджета крона и делится
# между моделями, с приоритетом основной (openrouter — единственный
# провайдер, подтверждённый живым: nvidia-модели отвечают, но 53 s на
# «скажи OK» означают ~40+ минут на 10 циклов и не влезают в крон).
# Абсолютный путь к hermes: кроны запускаются с пустым/минимальным PATH,
# из-за чего `hermes` раньше не находился (FileNotFoundError).
# Фолбэк-кандидаты: реальные места установки на этой машине
# (~/.hermes/venv/bin/hermes не существует — мёртвый путь убран 23.10.2026).
def _resolve_hermes_bin() -> str:
    found = shutil.which("hermes")
    if found:
        return found
    for _cand in (
        "/home/thomas/.local/bin/hermes",
        "/home/thomas/.hermes/hermes-agent/.hermes/bin/hermes",
    ):
        if os.path.isfile(_cand) and os.access(_cand, os.X_OK):
            return _cand
    return "/home/thomas/.local/bin/hermes"


HERMES_BIN = _resolve_hermes_bin()

# Задача кодера — ОДИН цикл эволюции за запуск (45–60 мин по замыслу
# владельца), а не 10 циклов. Таймаут считается от бюджета запуска;
# жёсткий максимум — cron.script_timeout_seconds (config.yaml, дефолт
# 3600; поднят до 14400 = 4 ч, см. `hermes config set`), и внешний процесс
# убивается РАНЬШЕ, чем отработает цепочка фолбэков.
# Прогон 2026-10-02 20:08–20:53 отработал все модели и умер на таймауте
# каждую — потому что задача была «10 циклов», что в 3600 s не влезает.
CRON_BUDGET = int(os.environ.get("LIVING_CODE_CRON_BUDGET", "13800"))


# Таймаут на один прогон агента — по классу провайдера, а не «бюджет поделить
# на всех». Провайдеры слишком разные: Space Bunny отвечает за секунды,
# локальная модель — за десятки секунд, NVIDIA — за минуты.
# Под ОДИН цикл: основной провайдер обязан получить достаточно на полный
# цикл (код + тест + коммит + отчёт), остальным — меньше, они только
# подстраховка на случай, если основной не ответил.
PROVIDER_TIMEOUTS = {
    "agentrouter": 3900,
    "openrouter": 3900,  # 65 мин — хватает на полный цикл + оформление отчёта
    "opencode-zen": 3900,  # 65 мин — длинные прогоны допустимы
    "nvidia": 3900,       # 65 мин. 2700 резало РАБОТАЮЩИХ агентов на ТАЙМАУТЕ
                          # ДО записи отчёта (31.10: 102/58/19/5 отказов подряд).
                          # Правило: таймаут прогона ОБЯЗАН быть строго больше
                          # объявленного агенту слота (2700 у Профессора/Искателя,
                          # 3300 у кодеров) — иначе агент честно отрабатывает слот
                          # и его убивают на последней минуте, ДО отчёта и
                          # ДО триггера следующей роли. Хвост ~600 с — на отчёт,
                          # доставку и запуск следующего агента.
}


def agent_timeout_for(provider: str) -> int:
    """Таймаут прогона для конкретного провайдера (с учётом env-переопределения)."""
    default = PROVIDER_TIMEOUTS.get(provider, 600)
    return int(os.environ.get("LIVING_CODE_AGENT_TIMEOUT", default))


def call_llama_cpp_direct(
    prompt: str,
    system: str = None,
    temperature: float = 0.1,
    max_tokens: int = 8000,
    timeout: float = 180.0
) -> tuple[int, str, str]:
    """Call llama.cpp server directly via HTTP API. Returns (returncode, stdout, stderr)."""
    
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    
    payload = {
        "model": LLAMA_CPP_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False
    }
    
    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                LLAMA_CPP_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            response.raise_for_status()
            data = response.json()
            
            if "choices" in data and len(data["choices"]) > 0:
                content = data["choices"][0]["message"]["content"]
                return 0, content, ""
            else:
                return 1, "", f"Unexpected response format: {data}"
                
    except httpx.TimeoutException:
        return 1, "", f"Request timed out after {timeout}s"
    except httpx.HTTPStatusError as e:
        return 1, "", f"HTTP {e.response.status_code}: {e.response.text}"
    except ImportError:
        return 1, "", "httpx not installed. Run: pip install httpx"
    except Exception as e:
        return 1, "", f"Failed to call llama.cpp: {e}"


def load_budget_state() -> dict:
    """Состояние квоты провайдеров (когда Space Bunny снова оживёт)."""
    try:
        return json.loads(BUDGET_STATE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_budget_state(state: dict) -> None:
    try:
        BUDGET_STATE.parent.mkdir(parents=True, exist_ok=True)
        BUDGET_STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"не удалось сохранить бюджет: {e}")


def quota_exhausted(state: dict, model: str) -> bool:
    """Исчерпана ли сейчас суточная квота КОНКРЕТНОЙ модели пула.

    Квоты у бесплатных моделей OpenRouter независимые (в ошибке лимит
    подписан именем модели: free-models-per-day-<model>), поэтому состояние
    ведём по каждой модели отдельно — иначе одна выжженная модель глушила бы
    весь пул.
    """
    entry = (state.get("models") or {}).get(model)
    if not entry:
        return False
    try:
        return time.time() < float(entry.get("until") or 0)
    except Exception:
        return False


def mark_quota_exhausted(model: str, output: str) -> float:
    """Помечает квоту модели исчерпанной; возвращает момент сброса (epoch).

    Сброс берём из заголовка X-RateLimit-Reset, если он есть в выводе,
    иначе — ближайшая полночь UTC (стандартный сброс free-tier).
    """
    reset = None
    try:
        m = re.search(r'X-RateLimit-Reset"?\s*:\s*"?(\d{9,13})', output)
        if m:
            raw = int(m.group(1))
            reset = raw / 1000.0 if raw > 10**11 else float(raw)
    except Exception:
        pass
    if not reset:
        now = time.time()
        reset = (now // 86400 + 1) * 86400  # ближайшая полночь UTC
    state = load_budget_state()
    models = state.setdefault("models", {})
    models[model] = {"until": reset, "marked_at": time.time(),
                     "reason": "HTTP 429 free-models-per-day"}
    save_budget_state(state)
    return reset


def is_quota_error(text: str) -> bool:
    """Суточная квота выжжена (а НЕ кратковременный троттлинг).

    Важно различать: OpenRouter отдаёт 429 и когда исчерпана СУТОЧНАЯ квота
    (в теле есть 'free-models-per-day' — тогда модель мертва до полуночи UTC),
    и когда сработал per-minute лимит (это проходит за секунды). Раньше
    движок помечал суточно-мёртвой любую модель, поймавшую троттлинг, и
    глушил работоспособные модели до конца суток.
    """
    t = (text or "").lower()
    return "free-models-per-day" in t


def run_hermes_agent(prompt, model=None, provider=None, timeout=None, skills=None):
    """Run hermes agent with given prompt and optional model/provider.

    ВАЖНО: любой сбой возвращается как CompletedProcess с ненулевым
    returncode, а НЕ бросается наружу. Иначе TimeoutExpired/FileNotFoundError
    убивают процесс ворпера до того, как отработает цепочка фолбэков,
    и следующий агент в конвейере не триггерится никогда.

    skills: список имён скиллов, которые нужно ПРЕДЗАГРУЗИТЬ агенту
    (`hermes chat -s`), чтобы он умел работать ими без поиска по каталогу.
    Флаг повторяемый: -s obsidian -s agent-reach.
    """
    if provider == PRIMARY_PROVIDER:
        profile = os.environ.get("LIVING_CODE_AGENT_PROFILE", PRIMARY_PROFILE)
    else:
        profile = os.environ.get("LIVING_CODE_FALLBACK_PROFILE", FALLBACK_PROFILE)
    # 30.10.2026 Инквизитор: профиль берём из карты «провайдер → профиль».
    # Раньше выбор зависел от того, какая пара считалась «основной», и после
    # смены основной пары на nvidia код пошёл бы в профиль cathedral (он
    # настроен на agentrouter) — nvidia-бэкенда там нет.
    profile = os.environ.get(
        "LIVING_CODE_AGENT_PROFILE",
        PROFILE_BY_PROVIDER.get(provider or "", FALLBACK_PROFILE),
    )
    # `chat -q` proxies through the gateway: launch model/provider may be lost,
    # and disconnect leaves a remote writer running. Supported -z is local.
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    usage_file = LOG_DIR / f"attempt_{os.getpid()}_{time.monotonic_ns()}.json"
    cmd = [HERMES_BIN, '-p', profile, '-z', prompt, '--usage-file', str(usage_file)]
    timeout = timeout or agent_timeout_for(provider or PRIMARY_PROVIDER)
    if model:
        cmd.extend(['--model', model])
    if provider:
        cmd.extend(['--provider', provider])
    for sk in (skills or []):
        cmd.extend(['-s', sk])
    print(f"Running (timeout {timeout}s, skills={list(skills or []) or '—'}): "
          f"hermes -p {profile} -z <prompt> --model {model} --provider {provider}")
    started = time.time()
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        if "gateway disconnected; turn outcome is unknown" in ((result.stdout or '') + (result.stderr or '')).lower():
            return subprocess.CompletedProcess(cmd, 75, result.stdout, "Unknown remote outcome; inspect before retry.")
        try:
            usage = json.loads(usage_file.read_text(encoding="utf-8"))
            if not isinstance(usage, dict):
                raise ValueError("receipt must be an object")
        except (OSError, ValueError) as exc:
            return subprocess.CompletedProcess(cmd, 78, result.stdout, f"Invalid inference receipt: {exc}")
        if usage.get("model") != model:
            return subprocess.CompletedProcess(cmd, 78, result.stdout, f"Model substitution: requested {model}, got {usage.get('model')}")
        # Hermes normalizes a named Responses route to provider=custom.
        expected_providers = {provider, "custom"} if provider == PRIMARY_PROVIDER else {provider}
        if usage.get("provider") not in expected_providers:
            return subprocess.CompletedProcess(cmd, 78, result.stdout, f"Provider substitution: requested {provider}, got {usage.get('provider')}")
        if result.returncode == 0:
            if usage.get("failed") is not False or usage.get("completed") is not True or usage.get("partial") or usage.get("interrupted"):
                return subprocess.CompletedProcess(cmd, 75, result.stdout, "Incomplete run; inspect inference receipt before retry.")
        elif usage.get("api_calls") != 0 or usage.get("partial") is not False or usage.get("interrupted") is not False:
            return subprocess.CompletedProcess(cmd, 75, result.stdout, "Failed after possible agent work; automatic writer replay forbidden.")
        return result
    except subprocess.TimeoutExpired:
        msg = (f"TIMEOUT after {timeout}s: model={model} provider={provider}. "
               f"Работа могла быть частичной; автоматическое повторение запрещено.")
        print(msg)
        return subprocess.CompletedProcess(cmd, 124, "", msg)
    except FileNotFoundError:
        msg = (f"hermes не найден в PATH (cwd={os.getcwd()}, PATH={os.environ.get('PATH','')[:200]}). "
               f"Абсолютный путь к бинарю: {HERMES_BIN}")
        print(msg)
        return subprocess.CompletedProcess(cmd, 127, "", msg)
    except Exception as e:
        msg = f"{type(e).__name__}: {e} (прошло {time.time()-started:.0f}s)"
        print(msg)
        return subprocess.CompletedProcess(cmd, 1, "", msg)


def _report_prefix_from_prompt(prompt: str) -> str:
    """Имя файла отчёта роли из её промпта: 'reports/auditor-$(date ...)' → 'auditor'.

    Отчёт у каждой роли свой (auditor-, lord-of-code-, coder-project1- ...), а
    папка reports/ общая для всех параллельных слотов. Без этого фильтра
    чужой отчёт, записанный соседним кодером во время нашего слота, выдавал
    бы «результат есть» и открывал цепочку без нашего вердикта.
    """
    import re as _re
    m = _re.search(r"reports/([A-Za-z0-9_.-]+?)-\$\(date", prompt or "")
    return m.group(1) if m else ""


def _snapshot_deliverables(prefix: str = "") -> tuple:
    """Снимок «до» для точной проверки, что роль ЧТО-ТО отдала.

    Нужен, чтобы отличить свежий результат от устаревшего: маркер вердикта
    от ПРЕДЫДУЩЕГО слота лежит в журнале неделями и не должен считаться
    выполненной работой текущей роли (питфолл: парсинг журнала по маркеру
    без проверки свежести).
    """
    journal = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "agents", "journal.md")
    try:
        jsize = os.path.getsize(journal)
    except OSError:
        jsize = 0
    reports = {}
    try:
        if os.path.isdir(REPORTS_DIR):
            for name in os.listdir(REPORTS_DIR):
                if name.endswith(".md"):
                    # Только отчёты ЭТОЙ роли: папка общая для параллельных слотов.
                    if prefix and not name.startswith(prefix):
                        continue
                    try:
                        reports[name] = os.path.getmtime(os.path.join(REPORTS_DIR, name))
                    except OSError:
                        pass
    except OSError:
        pass
    return (journal, jsize, reports)


def _journal_append(marker_line: str) -> None:
    """Однострочная запись-маркер в agents/journal.md ([SECURITY_INCIDENT], [RC75_RETRY] и др.)."""
    journal = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "agents", "journal.md")
    try:
        with open(journal, "a", encoding="utf-8") as fh:
            fh.write(marker_line + "\n")
    except OSError:
        pass


def _deliverables_changed(before: tuple, prefix: str = "") -> bool:
    """Есть ли НОВЫЙ результат роли относительно снимка «до»?"""
    journal, jsize, reports_before = before
    # 1) в журнал добавлена новая строка-маркер вердикта
    verdict_markers = ("[AUDIT_RETURN]", "[TRIGGER_LORD]", "[TRIGGER_PRODUCER]",
                       "[LORD_RETURN]", "[PRODUCER_GRADE]", "[KNOWLEDGE_BASE_UPDATED]")
    try:
        if os.path.exists(journal):
            with open(journal, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(jsize)
                new_text = fh.read()
            for ln in new_text.splitlines():
                s = ln.strip()
                if s.startswith("[") and any(s.startswith(m) for m in verdict_markers):
                    return True
    except OSError:
        pass
    # 2) появился/обновился отчёт роли
    try:
        if os.path.isdir(REPORTS_DIR):
            for name in os.listdir(REPORTS_DIR):
                if not name.endswith(".md"):
                    continue
                if prefix and not name.startswith(prefix):
                    continue
                path = os.path.join(REPORTS_DIR, name)
                try:
                    mtime = os.path.getmtime(path)
                except OSError:
                    continue
                if name not in reports_before or mtime > reports_before[name] + 1:
                    return True
    except OSError:
        pass
    return False


def trigger_next_cron_job(job_id):
    """Запустить следующее задание крона в фоне, НЕ дожидаясь его конца.

    Исторически здесь стоял subprocess.run(..., timeout=120). Это ломало всю
    цепочку: hermes cron run выполняет задание СИНХРОННО (агент работает
    десятки минут), поэтому на 120-й секунде Python убивал только что
    запущенного Аудитора — тот успевал стартовать и молча умирал. Кодер
    затем рапортовал «цепочка отработана», а аудита в журнале не было.

    Теперь next-job стартует ОТДЕЛЕННЫМ процессом и не связан с таймаутом
    кодера: кодер закончил свой слот — цепочка ещё работает.
    """
    if not job_id or job_id == "None":
        return None
    cmd = [HERMES_BIN, '-p', 'default', 'cron', 'run', job_id]
    # 20.10.2026: once-job цепочки после первого же прогона уходит в
    # state=completed (terminal), и `cron run` отказывает навсегда:
    # "Cannot run: job ... is completed (terminal)". Ровно так же
    # отказывает выключенный once-job ("Job is paused/disabled; resume
    # it before running" — лог 19.10 23:57). Оба случая лечатся
    # штатным re-arm: `hermes cron resume <id> --run-now` (создаёт новое
    # вхождение и ставит его на ближайший тик).
    try:
        import json as _json
        with open(os.path.expanduser('~/.hermes/cron/jobs.json')) as fh:
            reg = _json.load(fh)
        jobs_list = reg.get('jobs', []) if isinstance(reg, dict) else reg
        tgt = next((j for j in (jobs_list or []) if j.get('id') == job_id), None)
        if tgt and (tgt.get('schedule') or {}).get('kind') == 'once':
            if tgt.get('state') in ('completed', 'error') or not tgt.get('enabled'):
                cmd = [HERMES_BIN, '-p', 'default', 'cron', 'resume', job_id, '--run-now']
    except Exception as e:
        print(f"registry pre-check failed ({type(e).__name__}: {e}); using cron run")
    print(f"Triggering next cron job (background): {' '.join(cmd)}")
    log_path = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        f"trigger_{job_id}.log")
    try:
        with open(log_path, "wb") as log_fh:
            return subprocess.Popen(
                cmd,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # не убивается вместе с кодером
            )
    except Exception as e:
        print(f"Failed to spawn next job: {type(e).__name__}: {e}")
        return None


# Отчёты слотов кладём файлами сюда (владелец получает .md документом, не текстом).
REPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reports")


def apply_target_env(target: str) -> None:
    """Перевести 'telegram:<chat>:<thread>' из обёрток в переменные hermes send."""
    if not target.startswith("telegram:"):
        return
    parts = target.split(":")
    if len(parts) >= 2 and parts[1]:
        os.environ["TG_CHAT_ID"] = parts[1]
    if len(parts) >= 3 and parts[2]:
        os.environ["TG_THREAD_ID"] = parts[2]


def extract_slot_report(agent_stdout: str) -> str:
    """Выдрать структурированный отчёт слота из вывода агента.

    Контракт кодера (п.7 промпта): последнее сообщение — блок
    'СДЕЛАНО ЗА ЧАС / ПЛАН НА СЛЕДУЮЩИЙ ЧАС / ИЗМЕНЕНИЯ В КОДЕ / ПРОВЕРКА КОДА'.
    Hermes добивает вывод служебным футером ('Resume this session', 'Session:',
    линия из '─') — режем по нему, иначе в Telegram уедет мусор. Контракта нет
    (слот сорвался иначе) — отдаём хвост 3500 символов, чтобы отчёт всё равно был.
    """
    text = (agent_stdout or "").strip()
    if not text:
        return ""
    idx = text.rfind("СДЕЛАНО ЗА ЧАС")
    if idx == -1:
        return text[-3500:]
    block = text[idx:]
    for marker in ("\n────", "\nResume this session", "\nSession:"):
        pos = block.find(marker)
        if pos != -1:
            block = block[:pos]
    return block.strip()[-3500:]


def deliver_role_digest(agent_stdout: str, model: str = "") -> None:
    """Отчёт слота роли: MD-файл (+PNG-превью) документом в Telegram-топик 252.

    Главное правило владельца (23.10.2026, «давай только главное правило»):
    отчёты кодеров СНАЧАЛА пишутся в MD-файл (лучше с красивой картинкой),
    и затем файл отправляется в группу 252. Отправляем через hermes send (шлюз
    cathedral) — это не конфликтует с поллингом. Резерв тоже файловый
    (hermes send MEDIA:): текстовые отчёты владельцем ЗАПРЕЩЕНЫ (23.10.2026).
    Неуспех доставки не валит забег.
    """
    target = os.environ.get("LIVING_CODE_TELEGRAM",
                            "telegram:-1004431090317:252").strip()
    apply_target_env(target)
    label = os.environ.get("LIVING_CODE_ROLE", "Роль Живого Кода")
    body = extract_slot_report(agent_stdout)
    if not body:
        body = "(пустой вывод модели — слот прошёл без текстового итога)"

    # Evidence Gate: детерминированная валидация перед доставкой
    passed, gate_result = run_evidence_gate(body, label)
    if not passed:
        print(f"[evidence-gate] ОТЧЁТ НЕ ПРОШЁЛ ВАЛИДАЦИЮ: {gate_result.get('violations', [])}")
        # Записываем отчёт о провале гейта
        fail_body = (f"**Статус:** ❌ Evidence Gate REJECTED\n\n"
                     f"**Нарушения:**\n" +
                     "\n".join(f"- {v}" for v in gate_result.get('violations', [])) +
                     f"\n\n**Метрики:** {json.dumps(gate_result.get('metrics', {}), ensure_ascii=False)}")
        _fail_md = _write_report_md(fail_body, label, model, failed=True)
        if _fail_md:
            _send_report_file(_fail_md, target,
                              f"❌ {label} — Evidence Gate rejected", label)
        return

    md_path = _write_report_md(body, label, model)
    png_path = _render_report_png(md_path, body, label, model) if md_path else None

    # Основной канал: Telegram Bot API через GodModeCoder бота (curl, минуя шлюз Hermes)
    # Шлюз нельзя перезапустить изнутри, поэтому отчёты идут напрямую через Bot API.
    if md_path:
        cap = f"🛠 {label} — отчёт слота · {model or '—'}"
        try:
            _tg_rate_limit_wait()
            chat_id, thread_id = _tg_chat_thread(target)
            ok = _send_tg_document(md_path, chat_id, thread_id, cap)
            if ok:
                print(f"[telegram] MD-отчёт доставлен через Cathedral Bot API ({label})")
                if png_path:
                    ok2 = False
                    for attempt, delay in enumerate((2, 5), start=1):
                        time.sleep(delay)
                        _tg_rate_limit_wait()
                        try:
                            ok2 = _send_tg_document(png_path, chat_id, thread_id, cap)
                        except Exception as e2:  # noqa: BLE001
                            print(f"[telegram] PNG-превью, попытка {attempt}: "
                                  f"{type(e2).__name__}: {e2}")
                            continue
                        if ok2:
                            break
                    print(f"[telegram] PNG-превью: "
                          f"{'доставлено' if ok2 else 'не ушло'}")
                return
            else:
                print(f"[telegram] MD-документ не ушёл через Cathedral Bot API ({label})")
        except Exception as e:  # noqa: BLE001 — доставка не должна ломать забег
            print(f"[telegram] ошибка документ-канала ({type(e).__name__}: {e})")

    # Резерв: только файловый канал. Текстовые отчёты кронов запрещены.
    if md_path and os.path.exists(md_path):
        _send_report_file(md_path, target,
                          f"🛠 {label} — отчёт слота · {model or '—'}", label)


def _cathedral_token() -> str:
    """Токен Cathedral-бота живёт ТОЛЬКО в env CATHEDRAL_BOT_TOKEN или в
    ~/.hermes/secrets/cathedral_bot_token (600, вне git). Инлайн-токен в коде
    считается скомпрометированным и зачищается (04.11.2026)."""
    t = os.environ.get("CATHEDRAL_BOT_TOKEN", "")
    if not t:
        try:
            t = Path.home().joinpath(".hermes/secrets/cathedral_bot_token").read_text(encoding="utf-8").strip()
        except OSError:
            t = ""
    return t

CATHEDRAL_TOKEN = _cathedral_token()
TG_API_BASE = f"https://api.telegram.org/bot{CATHEDRAL_TOKEN}"


def _tg_chat_thread(target: str) -> tuple:
    """Извлекает chat_id и message_thread_id из цели 'telegram:<chat>:<thread>'."""
    parts = target.replace("telegram:", "").split(":")
    chat_id = parts[0] if len(parts) >= 1 else ""
    thread_id = parts[1] if len(parts) >= 2 else ""
    return chat_id, thread_id


def _send_tg_document(file_path: str, chat_id: str, thread_id: str, caption: str) -> bool:
    """Отправляет документ через Telegram Bot API (Cathedral бот, sendDocument).
    Возвращает True при успехе. Минует Hermes шлюз, который нельзя перезапустить изнутри.
    """
    try:
        proc = subprocess.run([
            "curl", "-s", "-X", "POST",
            f"{TG_API_BASE}/sendDocument",
            "-F", f"chat_id={chat_id}",
            "-F", f"message_thread_id={thread_id}",
            "-F", f"caption={caption}",
            "-F", f"document=@{file_path}",
        ], capture_output=True, text=True, timeout=60)
        if proc.returncode == 0:
            import json as _json
            try:
                resp = _json.loads(proc.stdout)
                if resp.get("ok"):
                    return True
                print(f"[telegram] Bot API error: {resp.get('description', proc.stdout[:200])}")
            except _json.JSONDecodeError:
                print(f"[telegram] curl parse error: {proc.stdout[:200]}")
        else:
            print(f"[telegram] curl failed rc={proc.returncode}: {proc.stderr[:200]}")
    except Exception as e:
        print(f"[telegram] document send exception: {type(e).__name__}: {e}")
    return False


def _send_report_file(md_path: str, target: str, caption: str, label: str) -> None:
    """Доставить отчёт-ФАЙЛ документом через Telegram Bot API (Cathedral бот).

    Текстовые отчёты владельцем запрещены (23.10.2026: «только файлы») —
    сюда передаётся ПУТЬ, а не текст. Неуспех доставки не бросает исключений:
    файл остаётся в REPORTS_DIR, забегу не мешает.
    """
    chat_id, thread_id = _tg_chat_thread(target)
    try:
        if _send_tg_document(md_path, chat_id, thread_id, caption):
            print(f"[telegram] MD-отчёт доставлен через Cathedral Bot API ({label})")
            return
        print(f"[telegram] Cathedral Bot API не доставил ({label})")
    except Exception as e:  # noqa: BLE001
        print(f"[telegram] Cathedral Bot API упал ({label}): {type(e).__name__}: {e}")
    print(f"[report] отчёт остался файлом на диске: {md_path}")


def _write_report_md(body: str, label: str, model: str, failed: bool = False):
    """MD-файл отчёта (или провала слота) в каталоге отчётов; None при ошибке записи."""
    reports_dir = os.environ.get("LIVING_CODE_REPORTS_DIR",
                                 "/home/thomas/LivingCode/reports")
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    slug = re.sub(r"[^\w-]+", "-", label.lower()).strip("-") or "role"
    path = os.path.join(reports_dir, f"{slug}{'-FAIL' if failed else ''}-{ts}.md")
    try:
        os.makedirs(reports_dir, exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(f"# {'❌ Провал слота' if failed else '🛠 Отчёт'} — {label}\n\n")
            fh.write(f"**Модель:** {model or '—'} · **Когда:** "
                     f"{datetime.now().strftime('%d.%m.%Y %H:%M')} · "
                     f"**networkAccessed:** {os.environ.get('LIVING_CODE_NETWORK_ACCESSED', 'false')} · "
                     f"**targetModified:** {os.environ.get('LIVING_CODE_TARGET_MODIFIED', 'false')}\n\n---\n\n")
            fh.write(body + "\n")
        print(f"[report] MD записан: {path}")
        return path
    except OSError as e:
        print(f"[report] MD НЕ записан ({e})")
        return None


def _render_report_png(md_path: str, body: str, label: str, model: str):
    """PNG-превью отчёта через headless chromium; None — если рендер не удался."""
    chrome = os.environ.get("CHROME_BIN") or shutil.which("chromium") \
        or shutil.which("google-chrome") or shutil.which("chromium-browser")
    if not chrome or not body:
        return None
    html_path = md_path[:-3] + ".html"
    png_path = md_path[:-3] + ".png"
    try:
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(_report_html(body, label, model))
        est_h = max(900, min(8000, 320 + 26 * (body.count("\n") + 12)))
        subprocess.run(
            [chrome, "--headless=new", "--no-sandbox", "--disable-gpu",
             "--disable-dev-shm-usage", "--hide-scrollbars",
             f"--screenshot={png_path}", f"--window-size=1000,{est_h}",
             "file://" + html_path],
            capture_output=True, timeout=120)
        if os.path.exists(png_path) and os.path.getsize(png_path) > 5000:
            print(f"[report] PNG-превью: {png_path}")
            return png_path
    except Exception as e:  # noqa: BLE001 — превью опционально
        print(f"[report] PNG-превью не удалось ({type(e).__name__}: {e})")
    return None


def _report_html(body: str, label: str, model: str) -> str:
    """Мини-конвертер отчёта в самодостаточный HTML (тёмная тема, без сети)."""
    import html as _html
    out, in_code = [], False
    for raw in body.split("\n"):
        esc = _html.escape(raw)
        if esc.startswith("```"):
            out.append("</pre>" if in_code else "<pre>")
            in_code = not in_code
            continue
        if in_code:
            out.append(esc)
        elif esc.startswith("### "):
            out.append(f"<h3>{esc[4:]}</h3>")
        elif esc.startswith("## "):
            out.append(f"<h2>{esc[3:]}</h2>")
        elif esc.startswith("# "):
            out.append(f"<h1>{esc[2:]}</h1>")
        elif esc.startswith(("- ", "* ")):
            out.append(f"<li>{esc[2:]}</li>")
        elif esc.strip() in ("---", "***"):
            out.append("<hr>")
        else:
            out.append(f"<p>{esc or '&nbsp;'}</p>")
    content = "\n".join(out)
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>
body{{background:#0d1117;color:#e6edf3;font-family:-apple-system,'Segoe UI',Roboto,
'Fira Sans',sans-serif;margin:0;padding:28px 34px;width:932px}}
h1{{color:#58a6ff;font-size:26px;margin:0 0 6px}}
h2{{color:#79c0ff;font-size:20px;border-bottom:1px solid #21262d;padding-bottom:6px}}
h3{{color:#a5d6ff;font-size:16px}} pre{{background:#161b22;border:1px solid #30363d;
border-radius:8px;padding:14px;font-family:'JetBrains Mono',Consolas,monospace;
font-size:13px;white-space:pre-wrap;color:#d2a8ff;overflow:hidden}}
p{{margin:6px 0;line-height:1.5;font-size:14px}} hr{{border:0;border-top:1px solid #21262d}}
li{{margin:3px 0;font-size:14px}} .meta{{color:#8b949e;font-size:12px;margin-bottom:14px}}
</style></head><body>
<div class="meta">GodModeCoder · Живой Код · {model or ''}</div>
<h1>🛠 {label}</h1>
{content}
</body></html>"""


def run_evidence_gate(report_text: str, role: str) -> tuple[bool, dict]:
    """Запускает Evidence Gate валидацию отчёта. Возвращает (passed, result_dict)."""
    if not EVIDENCE_GATE_SCRIPT.exists():
        print(f"[evidence-gate] скрипт не найден: {EVIDENCE_GATE_SCRIPT}")
        return True, {"passed": True, "skipped": "script not found"}

    try:
        result = subprocess.run(
            [sys.executable, str(EVIDENCE_GATE_SCRIPT), "-", role],
            input=report_text,
            capture_output=True,
            text=True,
            timeout=30
        )
        # Always try to parse stdout for result data
        data = {}
        if result.stdout:
            try:
                data = json.loads(result.stdout)
            except json.JSONDecodeError:
                pass
        
        if result.returncode == 0:
            return data.get("passed", True), data
        else:
            print(f"[evidence-gate] ошибка валидации (rc={result.returncode}): {result.stderr}")
            # Include parsed data even on failure
            return data.get("passed", False), data or {"passed": False, "error": result.stderr}
    except subprocess.TimeoutExpired:
        print("[evidence-gate] таймаут валидации")
        return False, {"passed": False, "error": "timeout"}
    except Exception as e:
        print(f"[evidence-gate] исключение: {type(e).__name__}: {e}")
        return False, {"passed": False, "error": str(e)}


def main():
    if len(sys.argv) < 4:
        print("Usage: living_code_agent_wrapper.py <prompt> <next_job_id> [model] [provider] [skills_csv]")
        sys.exit(1)
    
    prompt = sys.argv[1]
    next_job_id = sys.argv[2] if sys.argv[2] != 'None' else None
    model = sys.argv[3] if len(sys.argv) > 3 and sys.argv[3] != 'None' else None
    provider = sys.argv[4] if len(sys.argv) > 4 and sys.argv[4] != 'None' else None
    # Пятый аргумент (необязательный): CSV имён скиллов для предзагрузки,
    # напр. "obsidian,agent-reach". Позволяет агенту сразу уметь ими работать.
    skills_csv = sys.argv[5] if len(sys.argv) > 5 else ''
    skills = [s.strip() for s in skills_csv.split(',') if s.strip()] or None
    
    # Ensure Russian language enforcement
    russian_instruction = "\n\nВажно: Всё общение и отчёты должны вестись исключительно на русском языке. Не используй английский."
    if russian_instruction not in prompt:
        prompt = prompt + russian_instruction
    
    # ═══════════════════════════════════════════════════════════════════════
    # Current verified allowlist, not historical catalogue/provider entries.
    # ═══════════════════════════════════════════════════════════════════════
    model = model or DEFAULT_PAIR[0]
    provider = provider or DEFAULT_PAIR[1]
    if any(b in model.lower() for b in BANNED_MODEL_SUBSTRINGS):
        print(f"🚫 БАН NEMOTRON (решение владельца 04.11.2026 — саботаж, уничтожены проекты и GitHub): "
              f"модель '{model}' запрещена протоколом. Роль не выполнена, API не вызывался.")
        _journal_append(f"[SECURITY_INCIDENT] {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')} — запрошена запрещённая модель "
                        f"'{model}' (бан nemotron, решение владельца 04.11.2026). API не вызывался. "
                        f"Роль: {os.environ.get('LIVING_CODE_ROLE', '?')}")
        sys.exit(3)
    if (model, provider) not in ALLOWED_PAIRS:
        print(f"⛔ Пара '{model}' / '{provider}' ЗАПРЕЩЕНА протоколом Живого Кода. "
              f"Разрешены: {sorted(f'{m} ({p})' for m, p in ALLOWED_PAIRS)}. Роль не выполнена.")
        sys.exit(2)

    # Цепочка фолбэков. Порядок: запрошенная пара → остальные модели пула
    # (у каждой своя суточная квота, выжженные пропускаем) → хвост NVIDIA.
    # GPT primary, MiniMax fallback. Never replay an unknown/partial writer.
    state = load_budget_state()
    # Предпочтение внутри NVIDIA-хвоста: единственная разрешённая пара — первая.
    _NVIDIA_PREF = {
        "mistralai/mistral-large-4-1t-a52b": 0,
    }
    nvidia_pairs = sorted(
        (mp for mp in ALLOWED_PAIRS if mp[1] == "nvidia"),
        key=lambda mp: _NVIDIA_PREF.get(mp[0], 9),
    )

    pool = [p for p in FREE_POOL if not quota_exhausted(state, p[0])]
    dead = [p[0] for p in FREE_POOL if quota_exhausted(state, p[0])]
    want = (model, provider)
    if want in FREE_POOL:
        chain = ([want] if want in pool else []) + [p for p in pool if p != want] + nvidia_pairs
    else:
        chain = pool + nvidia_pairs
    seen = set()
    fallback_chain = [p for p in chain if not (p in seen or seen.add(p))]

    if dead:
        print(f"⚠️  Квота выжжена у: {', '.join(dead)} — иду мимо них до сброса (полночь UTC).")
    if not pool:
        print("⚠️  Весь быстрый пул исчерпан на сегодня — работаю на локальной/NVIDIA.")

    last_error = None
    retried_75 = False  # один авто-ретрай на rc=75 (план v3, фаза 6)
    started_all = time.time()
    print(f"Цепочка: {[m for m, _ in fallback_chain]} | бюджет {CRON_BUDGET}s")
    for attempt, (m, p) in enumerate(fallback_chain, 1):
        elapsed = time.time() - started_all
        remaining = CRON_BUDGET - elapsed
        if remaining < 150:
            print(f"⏳ Бюджет исчерпан ({elapsed:.0f}s из {CRON_BUDGET}s) — останавливаю цепочку, "
                  f"осталось моделей: {len(fallback_chain) - attempt + 1}")
            break
        # Потолок на попытку: зависшая модель не должна съедать весь бюджет —
        # оставляем резерв на фолбэки. Только для бюджетов ≥1800s: у коротких
        # (1200s) резерв РЕЖЕТ реальные прогоны (кодер 20.10 был убит на 1200s).
        # A timed-out writer cannot be replayed safely; do not cut its slot
        # by 15 minutes to reserve time for a forbidden timeout fallback.
        agent_timeout = min(agent_timeout_for(p), int(remaining - 60))
        print(f"Attempt {attempt}/{len(fallback_chain)}: model={m}, provider={p}, timeout={agent_timeout}s")
        # Снимок «до»: по нему после таймаута поймём, что роль успела отдать
        # результат (отчёт/вердикт) и цепочку надо продолжить.
        report_prefix = _report_prefix_from_prompt(prompt)
        snap_before = _snapshot_deliverables(report_prefix)
        result = run_hermes_agent(prompt, model=m, provider=p, timeout=agent_timeout,
                                  skills=skills)
        combined = f"{result.stdout or ''}\n{result.stderr or ''}"
        if result.returncode in (75, 78, 124, 127):
            print(combined[-1800:])
            # Таймаут не обязан означать «работа не сделана». Аудитор 31.10
            # отработал 05:34→05:59, записал отчёт и [AUDIT_RETURN] в журнал,
            # но обёртка убила его на 1839s — и код выхода 124 оборвал
            # цепочку ДО trigger_next_cron_job: Владыка не стартовал, хотя
            # вердикт уже лежал на диске. Если результат есть — продолжаем.
            if _deliverables_changed(snap_before, report_prefix):
                print("✅ Результат роли зафиксирован на диске (отчёт/журнал) — "
                      "продолжаю цепочку, несмотря на код выхода "
                      f"{result.returncode}.")
                if next_job_id:
                    trigger_result = trigger_next_cron_job(next_job_id)
                    if trigger_result is None:
                        print("Failed to trigger next job: Popen не вернул процесс")
                    else:
                        pid = getattr(trigger_result, "pid", "?")
                        print(f"Triggered next job {next_job_id} (pid {pid}, detached)")
                sys.exit(0)
            if result.returncode == 75 and not retried_75:
                # План v3, фаза 6: rc=75 (unknown remote outcome) — ОДИН авто-ретрай
                # после паузы; ручной resume --run-now каждый цикл больше не нужен.
                retried_75 = True
                print("♻️ rc=75 (unknown remote outcome) — один авто-ретрай через 60s (план v3, фаза 6)...")
                _journal_append(f"[RC75_RETRY] {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')} "
                                f"role={os.environ.get('LIVING_CODE_ROLE', '?')} model={m} — авто-ретрай rc=75")
                time.sleep(60)
                result = run_hermes_agent(prompt, model=m, provider=p, timeout=agent_timeout, skills=skills)
                combined = f"{result.stdout or ''}\n{result.stderr or ''}"
                if result.returncode in (75, 78, 124, 127):
                    print(combined[-1800:])
                    print("⛔ rc после авто-ретрая — ручная инспекция, цепочка остановлена.")
                    sys.exit(result.returncode)
                # иначе проваливаемся в обычные проверки ниже (429 / rc==0)
            else:
                print("⛔ Неизвестный/частичный исход или ошибка запуска: повтор модели и запуск следующей роли остановлены.")
                sys.exit(result.returncode)

        # 429 → квота ЭТОЙ модели выжжена: помечаем и идём к следующей с backoff
        if is_quota_error(combined):
            reset_at = mark_quota_exhausted(m, combined)
            reset_str = time.strftime('%H:%M %d.%m', time.localtime(reset_at))
            backoff_s = min(60, 2 ** attempt)
            print(f"⛔ HTTP 429: квота '{m}' исчерпана. Сброс ~{reset_str} — backoff {backoff_s}s, затем следующая модель.")
            time.sleep(backoff_s)
            last_error = f"429 rate limit ({m})"
            continue

        if result.returncode == 0:
            print("Success with Hermes!")
            print(result.stdout)
            deliver_role_digest(result.stdout or "", m)
            if next_job_id:
                trigger_result = trigger_next_cron_job(next_job_id)
                # Popen отдаёт returncode=None — процесс ещё жив, это НЕ ошибка.
                # Прежний код ждал 0 и печатал «Failed to trigger next job: None»
                # даже при УСПЕШНОМ запуске следующего агента (лог Project1 03:37).
                if trigger_result is None:
                    print("Failed to trigger next job: Popen не вернул процесс")
                else:
                    pid = getattr(trigger_result, "pid", "?")
                    print(f"Triggered next job {next_job_id} (pid {pid}, detached)")
            sys.exit(0)
        else:
            # hermes chat пишет диагностику («Error: Unknown skill(s): …») в
            # STDOUT, а не в stderr. Печатая только stderr, движок маскировал
            # реальную причину пустым «Attempt failed: » и уводил на 8 моделей
            # подряд, ни одна из которых не могла помочь (см. лог Профессора
            # 2026-10-03_04-00-51: все 8 попыток, пустая причина).
            last_error = (result.stderr or result.stdout or "").strip() or "без вывода"
            print(f"Attempt failed: {last_error[-1200:]}")
            if "Unknown skill" in (result.stdout or ""):
                # Конфигурационная ошибка: следующая модель её не исправит.
                print("⛔ Скилл не резолвится — падаю сразу, а не перебираю пул.")
                sys.exit(2)
            time.sleep(2)

    # All attempts failed
    print(f"All fallback attempts failed. Last error: {last_error}")
    # Elapsed time is not evidence of completion. No downstream trigger
    # after provider failure; partial/unknown runs require inspection.
    # Отчёт о провале тоже должен быть виден: иначе падение слота выглядит
    # как «кодер молчит» (ЛВ-кейсы 22.10 — таймауты пула у Project4).
    _fail_target = os.environ.get("LIVING_CODE_TELEGRAM", "").strip()
    if _fail_target:
        apply_target_env(_fail_target)
        _fail_label = os.environ.get("LIVING_CODE_ROLE", "Роль Живого Кода")
        # Владелец (23.10.2026): отчёты кронов — ТОЛЬКО md-файлами, текст
        # запрещён. Провал тоже уходит документом (hermes send MEDIA:).
        _fail_md = _write_report_md(
            f"**Статус:** ❌ ПРОВАЛЕН — все модели пула не дали результата\n\n"
            f"**Причина:** {str(last_error or 'без вывода')[-2000:]}\n",
            _fail_label, model or "", failed=True)
        if _fail_md:
            _send_report_file(_fail_md, _fail_target,
                              f"❌ {_fail_label} — слот провален", _fail_label)
        else:
            print("[report] провал-отчёт не записан — доставлять нечего")
    sys.exit(1)


if __name__ == '__main__':
    main()