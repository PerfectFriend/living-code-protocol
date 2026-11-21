#!/usr/bin/env python3
"""
meta_evolver.py — Layer 3: Meta-evolver Протокола Живого Кода (Фаза 2, A-Evolve).

Назначение:
  Эволюция самого кода эволюции. Анализирует living_code_agent_wrapper.py,
  cycle_close.py, l3_critic.py на предмет проблем, предложенных l3_critic и
  отчётами кодеров, и готовит改良-коммиты в репозиторий orchestration.
  Выход: новая ветка + коммит + уведомление Владыке для ревью.

Архитектура A-Evolve (3 слоя):
  Layer 1 — Task-harness: jobs.json, config.yaml, промпты ролей, шаблоны
             agents/templates/ — под версионным контролем (уже готово)
  Layer 2 — Evolver: living_code_agent_wrapper.py + check_roster.py + шедулер
             (уже готово)
  Layer 3 — Meta-evolver: этот скрипт — эволюция самого кода эволюции

Выходные коды:
  0 — всё хорошо, изменений не требуется или коммит создан
  1 — найдены проблемы, требуется вмешательство
  2 — ошибка выполнения скрипта

Автор: Hermes Agent (Протокол Живого Кода, Фаза 2)
Лицензия: MIT
"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Константы
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOME = Path.home()
ORCHESTRATION = HOME / "LivingCode" / "orchestration"
SCRIPTS = ORCHESTRATION / "scripts"
REPORTS = HOME / "LivingCode" / "reports"
JOURNAL = HOME / "LivingCode" / "agents" / "journal.md"

# Файлы эволюции, которые подлежат мета-эволюции
EVOLUTION_FILES = [
    SCRIPTS / "living_code_agent_wrapper.py",
    SCRIPTS / "cycle_close.py",
    SCRIPTS / "l3_critic.py",
    SCRIPTS / "check_roster.py",
]

# Ветка для мета-эволюции
META_BRANCH = "meta-evolver-layer3"

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Вспомогательные функции
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def log(msg: str) -> None:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    print(f"[{ts}] {msg}", flush=True)


def run(cmd: list[str], cwd: Path | None = None) -> tuple[int, str, str]:
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
        return 124, "", f"Command timed out: {' '.join(cmd)}"
    except FileNotFoundError:
        return 127, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return 1, "", f"Unexpected error: {e}"


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
    except Exception as e:
        log(f"ПРЕДУПРЕЖДЕНИЕ: не удалось прочитать {path}: {e}")
        return ""


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Анализ файлов эволюции
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_evolution_file(path: Path) -> dict:
    """
    Анализирует один файл эволюции на предмет:
    - наличие TODO/FIXME/HACK
    - длины функций (потенциальная необходимость рефакторинга)
    - отсутствия docstrings
    - хардкод-путей Windows (C:/)
    Возвращает словарь с находками.
    """
    text = read_text(path)
    if not text:
        return {"file": str(path), "error": "не удалось прочитать"}

    findings = []

    # TODO / FIXME / HACK / XXX
    for i, line in enumerate(text.splitlines(), start=1):
        for marker in ("TODO", "FIXME", "HACK", "XXX", "STUB", "TEMP"):
            if marker in line.upper():
                findings.append({
                    "line": i,
                    "marker": marker,
                    "content": line.strip()[:100],
                })

    # Хардкод Windows-путей
    for i, line in enumerate(text.splitlines(), start=1):
        if re.search(r"C:/|C:\\\\|AppData|\\\\Users", line):
            findings.append({
                "line": i,
                "marker": "WINDOWS_PATH",
                "content": line.strip()[:100],
            })

    # Функции без docstring (упрощённо: def без следующей строки с """ или '')
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"\s*(def\s+\w+)\s*\(.*\)\s*:", line)
        if m:
            # Проверяем следующие 2 строки на docstring
            next_lines = lines[i+1:i+3]
            has_docstring = any('"""' in nl or "'''" in nl for nl in next_lines)
            if not has_docstring:
                func_name = m.group(1).split()[-1]
                findings.append({
                    "line": i + 1,
                    "marker": "MISSING_DOCSTRING",
                    "content": f"Функция {func_name} без docstring",
                })

    return {
        "file": str(path),
        "size_lines": len(lines),
        "findings": findings,
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Сбор логов и отчётов для анализа
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def collect_recent_errors() -> list[str]:
    """Собирает недавние ошибки из логов крона и отчётов."""
    errors = []

    # errors.log шедерлера
    errors_log = HOME / ".hermes/cron/errors.log"
    if errors_log.exists():
        text = read_text(errors_log)
        lines = text.splitlines()
        # Берём последние 20 строк с ошибками
        for line in lines[-20:]:
            if "error" in line.lower() or "fail" in line.lower() or "traceback" in line.lower():
                errors.append(line[:200])

    # Отчёты кодеров с regress
    reports_dir = REPORTS
    if reports_dir.exists():
        for report_file in sorted(reports_dir.glob("coder-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:10]:
            text = read_text(report_file)
            if "regress" in text.lower():
                errors.append(f"{report_file.name}: найден regress в отчёте кодера")

    return errors


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Генерация предложений по улучшению
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_improvements(file_analyses: list[dict], recent_errors: list[str]) -> list[str]:
    """
    Генерирует список предложений по улучшению на основе анализов.
    """
    improvements = []

    for analysis in file_analyses:
        filepath = analysis["file"]
        for finding in analysis.get("findings", []):
            marker = finding["marker"]
            content = finding["content"]
            line = finding["line"]

            if marker == "WINDOWS_PATH":
                improvements.append(
                    f"{filepath}:{line} — Windows-путь ({content}). Заменить на Linux-путь."
                )
            elif marker == "MISSING_DOCSTRING":
                improvements.append(
                    f"{filepath}:{line} — отсутствует docstring ({content}). Добавить документацию."
                )
            elif marker in ("TODO", "FIXME", "HACK", "XXX", "STUB", "TEMP"):
                improvements.append(
                    f"{filepath}:{line} — {marker}: {content}. Рассмотреть устранение."
                )

    for error in recent_errors[:5]:
        improvements.append(f"Ошибка из логов: {error}")

    return improvements


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Создание ветки и коммита
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def ensure_git_repo() -> bool:
    """Проверяет, что мы в git-репозитории orchestration."""
    rc, _, _ = run(["git", "rev-parse", "--git-dir"], cwd=ORCHESTRATION)
    return rc == 0


def create_meta_branch() -> tuple[bool, str]:
    """Создаёт ветку мета-эволюции если её нет."""
    rc, out, err = run(["git", "branch", "--list", META_BRANCH], cwd=ORCHESTRATION)
    if META_BRANCH in out:
        return True, f"Ветка {META_BRANCH} уже существует"

    rc, out, err = run(["git", "checkout", "-b", META_BRANCH], cwd=ORCHESTRATION)
    if rc != 0:
        return False, f"Не удалось создать ветку: {err}"
    return True, f"Ветка {META_BRANCH} создана"


def apply_improvements(improvements: list[str]) -> list[str]:
    """
    Применяет автома miglior-ения к файлам эволюции.
    Пока что только простые текстовые замены (Windows-пути -> Linux).
    Возвращает список изменённых файлов.
    """
    changed_files = []

    for analysis in []:  # Заглушка — фактические изменения требуют ручного ревью
        pass

    # Автоматические исправления: Windows-пути -> Linux
    for ev_file in EVOLUTION_FILES:
        text = read_text(ev_file)
        original = text

        # Замена C:/... на /home/thomas/...
        text = re.sub(r"C:/Users/thomas/", "/home/thomas/", text)
        text = re.sub(r"C:/LivingCode", "/home/thomas/LivingCode", text)
        text = re.sub(r"C:/Vault", "/home/thomas/Documents/ObsidianVault", text)

        if text != original:
            write_text(ev_file, text)
            changed_files.append(str(ev_file))

    return changed_files


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Составление отчёта мета-эволюции
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def write_report(content: str) -> Path:
    REPORTS.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    path = REPORTS / f"meta-evolver-{ts}.md"
    path.write_text(content, encoding="utf-8")
    return path


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Главная функция
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> int:
    log("=== Meta-evolver Layer 3 started (A-Evolve, Фаза 2) ===")

    report_lines: list[str] = []
    report_lines.append("# Meta-evolver отчёт (Layer 3: эволюция кода эволюции)")
    report_lines.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # 1. Проверка git-репозитория
    if not ensure_git_repo():
        log("⛔ Не в git-репозитории orchestration")
        report_lines.append("⛔ **Ошибка**: не в git-репозитории orchestration")
        write_report("\n".join(report_lines))
        return 2

    # 2. Анализ файлов эволюции
    log("Анализ файлов эволюции...")
    report_lines.append("## Анализ файлов эволюции")
    file_analyses = []
    for ev_file in EVOLUTION_FILES:
        if ev_file.exists():
            analysis = analyze_evolution_file(ev_file)
            file_analyses.append(analysis)
            findings_count = len(analysis.get("findings", []))
            log(f"  {ev_file.name}: {findings_count} находок")
            report_lines.append(f"- **{ev_file.name}**: {analysis.get('size_lines', 0)} строк, {findings_count} находок")
            for f in analysis.get("findings", [])[:5]:  # показываем первые 5
                report_lines.append(f"  - строка {f['line']}: [{f['marker']}] {f['content'][:80]}")
        else:
            log(f"  {ev_file.name}: не найден")
            report_lines.append(f"- **{ev_file.name}**: НЕ НАЙДЕН")
    report_lines.append("")

    # 3. Сбор недавних ошибок
    log("Сбор недавних ошибок...")
    recent_errors = collect_recent_errors()
    report_lines.append("## Недавние ошибки из логов")
    if recent_errors:
        for err in recent_errors[:10]:
            report_lines.append(f"- {err[:120]}")
    else:
        report_lines.append("- Нет недавних ошибок")
    report_lines.append("")

    # 4. Предложения по улучшению
    improvements = generate_improvements(file_analyses, recent_errors)
    report_lines.append("## Предложения по улучшению (Layer 3)")
    if improvements:
        for imp in improvements:
            report_lines.append(f"- {imp}")
    else:
        report_lines.append("- Предложений не найдено — код эволюции в хорошем состоянии")
    report_lines.append("")

    # 5. Автоматические исправления
    changed_files = apply_improvements(improvements)
    report_lines.append("## Автоматические исправления")
    if changed_files:
        for f in changed_files:
            report_lines.append(f"- Исправлен: {f}")
    else:
        report_lines.append("- Автоматических исправлений не требуется (только ручной ревью)")
    report_lines.append("")

    # 6. Создание ветки и коммит
    branch_ok, branch_msg = create_meta_branch()
    report_lines.append("## Ветка мета-эволюции")
    report_lines.append(f"- {branch_msg}")
    if branch_ok:
        # Добавляем изменения и коммитим
        run(["git", "add", "-A"], cwd=ORCHESTRATION)
        rc, out, err = run(
            ["git", "commit", "-m", f"Meta-evolver Layer 3: автоматические улучшения ({datetime.now().strftime('%Y-%m-%d')})"],
            cwd=ORCHESTRATION,
        )
        if rc == 0:
            log("Коммит мета-эволюции создан")
            report_lines.append("- Коммит создан успешно")
        else:
            log(f"Коммит не создан (возможно, нет изменений): {err[:200]}")
            report_lines.append(f"- Коммит не создан: {err[:200]}")

    report_lines.append("")
    report_lines.append("## Дальнейшие шаги")
    report_lines.append("1. Владыка Кода проводит ревью изменений в ветке meta-evolver-layer3")
    report_lines.append("2. При одобрении — слияние в main")
    report_lines.append("3. При отклонении — ветка удаляется, правки дорабатываются")

    report_path = write_report("\n".join(report_lines))
    log(f"Отчёт записан: {report_path}")

    # 7. Триггер Владыке
    journal_text = read_text(JOURNAL)
    if "[TRIGGER_LORD]" not in journal_text:
        # Добавляем триггер
        with open(JOURNAL, "a", encoding="utf-8") as f:
            f.write(f"\n[TRIGGER_LORD] meta-evolver-layer3 — ревью изменений кода эволюции\n")
        log("Триггер [TRIGGER_LORD] добавлен в journal.md")

    return 0


if __name__ == "__main__":
    sys.exit(main())
