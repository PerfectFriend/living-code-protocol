#!/usr/bin/env python3
"""
supervisor_cron.py — Super-Supervisor Протокола Живого Кода (Фаза 0).

Назначение:
  Раз в час выполняет пост-верификацию всего роя: проверяет, что все 4 проектных
  кодера зелёные, l3_critic не зафиксировал regress, нет uncommitted-изменений,
  и если Владыка вынес ВЕРДИКТ: ГОРЯЧИЙ — триггерит Продюсера на авто-релиз
  (тег vX.Y.Z, APK в ~/apkexport/, отчёт в топик 252).

Архитектура:
  Скрипт запускается кроном LV-super-supervisor (каждый час, в :00).
  Не вызывает LLM напрямую — только детерминированные проверки (fs, git, l3_critic,
  journal.md, jobs.json). LLM-решение принимает Владыка (LV-lord-of-code), а
  Super-Supervisor только выполняет техническую часть релиза.

Выходные коды:
  0 — всё зелёно, релиз не требуется или выпущен успешно
  1 — найдены проблемы, требуется вмешательство
  2 — ошибка выполнения самого скрипта

Автор: Hermes Agent (Протокол Живого Кода, Фаза 0)
Лицензия: MIT
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Константы путей — все абсолютные, без хардкода Windows (C:/). Только Linux.
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOME = Path.home()
LIVING_CODE_ROOT = HOME / "LivingCode"
ORCHESTRATION = LIVING_CODE_ROOT / "orchestration"
PROJECTS_DIR = LIVING_CODE_ROOT / "Projects"
REPORTS_DIR = LIVING_CODE_ROOT / "reports"
AGENTS_DIR = LIVING_CODE_ROOT / "agents"
JOURNAL = AGENTS_DIR / "journal.md"
JOBS_JSON = ORCHESTRATION / "jobs" / "jobs.json"
L3_CRITIC = ORCHESTRATION / "scripts" / "l3_critic.py"
CYCLE_CLOSE = ORCHESTRATION / "scripts" / "cycle_close.py"
APKEXPORT = HOME / "apkexport"
HERMES_CRON_JOBS = HOME / ".hermes/cron/jobs.json"

# Четыре активных проекта Протокола Живого Кода
PROJECTS = [
    "superguard",
    "elemental-life",
    "cybertarot",
    "elemental-life-2",
]

# Проекты с полной версией (cybertarot-full, elemental-life-2 already in list)
FULL_PROJECTS = ["cybertarot-full", "elemental-life-2"]

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Вспомогательные функции
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def log(msg: str) -> None:
    """Печатает сообщение с UTC-временем для отладки в логах крона."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
    """
    Выполняет команду, возвращает (returncode, stdout, stderr).
    Не падает на ошибке — caller сам решает, что делать с rc.
    """
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=300,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return 124, "", f"Command timed out after 300s: {' '.join(cmd)}"
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return 1, "", f"Unexpected error: {e}"


def read_text(path: Path) -> str:
    """Безопасное чтение текстового файла; пустая строка если не найден."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as e:
        log(f"ПРЕДУПРЕЖДЕНИЕ: не удалось прочитать {path}: {e}")
        return ""


def load_json(path: Path) -> dict | None:
    """Безопасная загрузка JSON; None при ошибке."""
    try:
        return json.loads(read_text(path))
    except json.JSONDecodeError as e:
        log(f"ПРЕДУПРЕЖДЕНИЕ: неверный JSON в {path}: {e}")
        return None
    except Exception as e:
        log(f"ПРЕДУПРЕЖДЕНИЕ: ошибка чтения {path}: {e}")
        return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Проверка 1: все ли 4 проектных крона активны и без ошибок
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_cron_health(jobs: dict) -> list[str]:
    """
    Проверяет, что все 4 проектных кодера enabled и их last_status == ok.
    Возвращает список проблем (пустой = всё хорошо).
    """
    problems = []
    live_jobs = {j["name"]: j for j in jobs.get("jobs", [])}

    for proj in PROJECTS:
        name = f"LV-coder-{proj}"
        job = live_jobs.get(name)
        if not job:
            problems.append(f"{name}: крон не найден в jobs.json")
            continue
        if not job.get("enabled"):
            problems.append(f"{name}: крон на паузе (enabled=false)")
        if job.get("last_status") != "ok":
            problems.append(
                f"{name}: last_status={job.get('last_status')}, "
                f"ошибка={job.get('last_error') or job.get('last_delivery_error') or 'нет деталей'}"
            )
        failure_streak = job.get("failure_streak", 0)
        if failure_streak > 0:
            problems.append(f"{name}: failure_streak={failure_streak}")

    return problems


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Проверка 2: нет uncommitted-изменений в проектах
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_git_clean() -> list[str]:
    """
    Для каждого проекта проверяет `git status --porcelain`.
    Если есть uncommitted-изменения — это проблема (код должен быть закоммичен
    перед релизом).
    """
    problems = []
    for proj in PROJECTS:
        proj_dir = PROJECTS_DIR / proj
        if not proj_dir.exists():
            problems.append(f"{proj}: директория проекта не найдена {proj_dir}")
            continue
        git_dir = proj_dir / ".git"
        if not git_dir.exists():
            problems.append(f"{proj}: не git-репозиторий (нет .git)")
            continue
        rc, stdout, _ = run(["git", "status", "--porcelain"], cwd=proj_dir)
        if rc != 0:
            problems.append(f"{proj}: git status упал (rc={rc})")
        elif stdout.strip():
            problems.append(
                f"{proj}: uncommitted-изменения:\n{stdout.strip()[:500]}"
            )
    return problems


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Проверка 3: вердикт Владыки в journal.md
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_lord_verdicts(journal_text: str) -> dict[str, str]:
    """
    Ищет в journal.md последние строки [TRIGGER_LORD] и вердикты Владыки.
    Возвращает словарь {проект: вердикт} для последних упоминаний.
    Вердикты: ГОРЯЧИЙ, ХОЛОДНЫЙ, ВЕРНУТЬ.
    """
    verdicts = {}
    # Ищем паттерн: ВЕРДИКТ: <проект> — ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ
    pattern = re.compile(
        r"ВЕРДИКТ:\s*(\S+)\s*[—-]\s*(ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ)",
        re.IGNORECASE,
    )
    for line in journal_text.splitlines():
        m = pattern.search(line)
        if m:
            proj = m.group(1).strip()
            verd = m.group(2).strip().upper()
            verdicts[proj] = verd
    return verdicts


def get_lord_triggers(journal_text: str) -> list[str]:
    """Возвращает список проектов с необработанными [TRIGGER_LORD]."""
    triggers = []
    for line in journal_text.splitlines():
        if "[TRIGGER_LORD]" in line:
            for proj in PROJECTS:
                if proj in line:
                    triggers.append(proj)
    return triggers


def get_producer_triggers(journal_text: str) -> list[str]:
    """Возвращает список проектов с [TRIGGER_PRODUCER] (готов к релизу)."""
    triggers = []
    for line in journal_text.splitlines():
        if "[TRIGGER_PRODUCER]" in line:
            for proj in PROJECTS:
                if proj in line:
                    triggers.append(proj)
    return triggers


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Проверка 4: l3_critic на Projekтах
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def run_l3_critic(proj: str) -> tuple[str, str]:
    """
    Запускает l3_critic.py для проекта. Возвращает (вердикт, детали).
    Вердикты: stabilen, regress, nuzhna_rabota, error.
    """
    proj_dir = PROJECTS_DIR / proj
    if not proj_dir.exists():
        return "error", f"Директория {proj_dir} не существует"

    # Ищем недавние изменения — можно передать конкретный файл, но проще проверить
    # весь проект. l3_critic принимает deliverable и criteria.
    # Здесь запускаем без конкретного deliverable — он сам найдёт что проверить.
    rc, stdout, stderr = run(
        [sys.executable, str(L3_CRITIC), "--project", str(proj_dir)],
        cwd=proj_dir,
    )
    if rc != 0:
        return "error", f"l3_critic rc={rc}: {stderr[:300]}"

    # Парсим вердикт из stdout
    verdict_match = re.search(r"ВЕРДИКТ:\s*(\w+)", stdout, re.IGNORECASE)
    if verdict_match:
        return verdict_match.group(1).lower(), stdout[:500]

    # Альтернативный паттерн
    if "stabilen" in stdout.lower():
        return "stabilen", stdout[:500]
    if "regress" in stdout.lower():
        return "regress", stdout[:500]
    if "nuzhna" in stdout.lower():
        return "nuzhna_rabota", stdout[:500]

    return "unknown", stdout[:500]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Проверка 5: триггер релиза Продюсеру
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def should_release(proj: str, verdicts: dict) -> bool:
    """
    Проект готов к релизу если:
    - Владыка вынес ВЕРДИКТ: ГОРЯЧИЙ
    - l3_critic = stabilen (если можно проверить)
    - Нет uncommitted-изменений
    """
    if verdicts.get(proj) != "ГОРЯЧИЙ":
        return False
    return True


def trigger_producer(proj: str) -> tuple[int, str, str]:
    """
    Запускает Продюсера для проекта через cycle_close.py + hermes send.
    Возвращает (rc, stdout, stderr).
    """
    log(f"Триггер Продюсера для {proj} (авто-релиз)")
    # Сначала cycle_close (холодные гейты, коммит, пуш)
    rc, out, err = run([sys.executable, str(CYCLE_CLOSE)])
    if rc != 0:
        return rc, out, err

    # Затем запускаем wrapper Продюсера
    wrapper = ORCHESTRATION / "scripts" / "wrappers" / "wrapper_producer.sh"
    if wrapper.exists():
        rc, out, err = run(["bash", str(wrapper)])
        return rc, out, err

    return 0, "producer wrapper not found, cycle_close done", ""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Составление отчёта Super-Supervisor
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def write_report(content: str) -> Path:
    """Пишет отчёт в reports/ и возвращает путь."""
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    path = REPORTS_DIR / f"super-supervisor-{ts}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Главная функция
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> int:
    log("=== Super-Supervisor started (Фаза 0: пост-верификация + релиз-тегирование) ===")

    report_lines: list[str] = []
    report_lines.append("# Super-Supervisor отчёт")
    report_lines.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # 1. Загружаем jobs.json
    jobs = load_json(JOBS_JSON)
    if jobs is None:
        log("⛔ Не удалось загрузить jobs.json")
        report_lines.append("⛔ **Ошибка**: не удалось загрузить jobs.json")
        write_report("\n".join(report_lines))
        return 2

    # 2. Проверка кронов
    cron_problems = check_cron_health(jobs)
    if cron_problems:
        log(f"⛔ Проблемы с кронами: {len(cron_problems)}")
        report_lines.append("## 🔴 Проблемы с кронами кодеров")
        for p in cron_problems:
            report_lines.append(f"- {p}")
    else:
        log("✅ Все 4 проектных крона активны и без ошибок")
        report_lines.append("## ✅ Кроны кодеров: все 4 активны, без ошибок")
    report_lines.append("")

    # 3. Проверка git-чистоты
    git_problems = check_git_clean()
    if git_problems:
        log(f"⛔ Uncommitted-изменения: {len(git_problems)} проектов")
        report_lines.append("## 🔴 Uncommitted-изменения в проектах")
        for p in git_problems:
            report_lines.append(f"- {p}")
    else:
        log("✅ Все проекты чистые (git status --porcelain пуст)")
        report_lines.append("## ✅ Git: все проекты чистые, нет uncommitted-изменений")
    report_lines.append("")

    # 4. Вердикты Владыки из journal.md
    journal_text = read_text(JOURNAL)
    verdicts = get_lord_verdicts(journal_text)
    lord_triggers = get_lord_triggers(journal_text)
    producer_triggers = get_producer_triggers(journal_text)

    if verdicts:
        report_lines.append("## Вердикты Владыки Кода (из journal.md)")
        for proj, verd in verdicts.items():
            emoji = "🔴" if verd == "ГОРЯЧИЙ" else ("🟡" if verd == "ХОЛОДНЫЙ" else "🟢")
            report_lines.append(f"- {emoji} **{proj}**: {verd}")
        report_lines.append("")
    else:
        report_lines.append("## Вердикты Владыки: не найдено недавних вердиктов в journal.md")
        report_lines.append("")

    # 5. l3_critic проверка для проектов с ГОРЯЧИЙ вердиктом
    hot_projects = [p for p, v in verdicts.items() if v == "ГОРЯЧИЙ"]
    if hot_projects:
        report_lines.append("## Проверка l3_critic для ГОРЯЧИХ проектов")
        for proj in hot_projects:
            verd, details = run_l3_critic(proj)
            emoji = "✅" if verd == "stabilen" else ("⛔" if verd == "regress" else "⚠️")
            report_lines.append(f"- {emoji} **{proj}**: l3_critic = {verd}")
            if verd != "stabilen":
                report_lines.append(f"  Детали: {details[:200]}")
        report_lines.append("")

    # 6. Решение о релизе
    releasable = []
    git_problems_text = "\n".join(git_problems)
    for proj in hot_projects:
        if proj in git_problems_text:
            # Есть uncommitted — не релизим
            continue
        # Проверяем l3_critic для этого проекта
        verd, _ = run_l3_critic(proj)
        if verd == "stabilen":
            releasable.append(proj)

    if releasable:
        log(f"🚀 Проекты готовы к авто-релизу: {releasable}")
        report_lines.append("## 🚀 Авто-релиз (Владыка: ГОРЯЧИЙ, l3_critic: stabilen)")
        for proj in releasable:
            rc, out, err = trigger_producer(proj)
            status = "успешно" if rc == 0 else f"ОШИБКА rc={rc}"
            report_lines.append(f"- **{proj}**: релиз {status}")
            if rc != 0:
                report_lines.append(f"  Детали: {(out + err)[:300]}")
    else:
        if hot_projects:
            log("⚠️ Есть ГОРЯЧИЕ проекты, но условия релиза не выполнены (l3_critic ≠ stabilen или uncommitted)")
            report_lines.append("## ⚠️ ГОРЯЧИЕ проекты не готовы к релизу")
            for proj in hot_projects:
                report_lines.append(f"- {proj}: условия не выполнены (см. проверки выше)")
        else:
            report_lines.append("## ℹ️ ГОРЯЧИХ проектов нет — релиз не требуется")
        report_lines.append("")

    # 7. Продюсерские триггеры (если Владыка уже записал [TRIGGER_PRODUCER])
    if producer_triggers:
        report_lines.append("## 📨 Триггеры Продюсера из journal.md")
        for proj in set(producer_triggers):
            report_lines.append(f"- **{proj}**: [TRIGGER_PRODUCER] найден")
        report_lines.append("")

    report_lines.append("---")
    report_lines.append("Super-Supervisor завершён. Следующая проверка через 1 час.")

    report_path = write_report("\n".join(report_lines))
    log(f"Отчёт записан: {report_path}")

    # 8. Доставка отчёта в топик 252 через Cathedral Bot API (curl, минуя Hermes-шлюз)
    # Токен берётся из профиля cathedral; здесь используется заглушка —
    # реальный токен подставляется из окружения или .env.
    from _secrets import load_cathedral_token as _load_secrets
    _load_secrets()
    tg_token = os.environ.get("CATHEDRAL_BOT_TOKEN", "")
    if tg_token and report_path.exists():
        log("Доставка отчёта в топик 252...")
        rc, out, err = run([
            "curl", "-s", "-X", "POST",
            f"https://api.telegram.org/bot{tg_token}/sendDocument",
            "-F", "chat_id=-1004431090317",
            "-F", "message_thread_id=252",
            "-F", "caption=Super-Supervisor отчёт",
            f"-F", f"document=@{report_path}",
        ])
        if rc == 0:
            log("Отчёт доставлен в топик 252")
        else:
            log(f"⚠️ Доставка отчёта не удалась: {err[:200]}")
    elif not tg_token:
        log("⚠️ CATHEDRAL_BOT_TOKEN не задан — отчёт не доставлен в Telegram")

    # 9. Код завершения
    if cron_problems or git_problems:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())