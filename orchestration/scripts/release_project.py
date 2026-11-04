#!/usr/bin/env python3
"""
release_project.py — Авто-релиз Проекта Живого Кода (Фаза 3).

Назначение:
  При ВЕРДИКТЕ: ГОРЯЧИЙ от Владыки + l3_critic stabilen выполняет полный
  цикл релиза:
  1. Проверяет чек-лист релиза (код холодный, нет [СР], check_roster rc=0,
     ui_gate пройден, ассеты закоммичены)
  2. Определяет следующую версию по семантическому версионированию (vX.Y.Z)
  3. Тегирует коммит vX.Y.Z и пушит в GitHub
  4. Копирует свежие *.apk в ~/apkexport/ с именем <project>-vX.Y.Z-<имя>.apk
  5. Пишет отчёт reports/release-<project>-vX.Y.Z-<ts>.md
  6. Доставляет отчёт в топик 252 через Telegram Bot API

Выходные коды:
  0 — релиз выполнен успешно
  1 — чек-лист не пройден, релиз отменён
  2 — ошибка выполнения скрипта

Автор: Hermes Agent (Протокол Живого Кода, Фаза 3)
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
LIVING_CODE = HOME / "LivingCode"
PROJECTS_DIR = LIVING_CODE / "Projects"
REPORTS_DIR = LIVING_CODE / "reports"
AGENTS_DIR = LIVING_CODE / "agents"
JOURNAL = AGENTS_DIR / "journal.md"
ORCHESTRATION = LIVING_CODE / "orchestration"
CHECK_ROSTER = ORCHESTRATION / "scripts" / "check_roster.py"
APKEXPORT = HOME / "apkexport"
COMPLETE_PROJECTS_DIR = HOME / "LivingCode" / "CompleteProjects"

PROJECTS = ["superguard", "elemental-life", "cybertarot", "elemental-life-2"]

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
# Чек-лист релиза
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def check_release_checklist(proj: str) -> tuple[bool, list[str]]:
    """
    Проверяет чек-лист релиза для проекта.
    Возвращает (пройден, список_проблем).
    """
    problems = []
    proj_dir = PROJECTS_DIR / proj

    # 1. Код холодный — нет [СР] маркеров в коммитах
    log(f"Проверка [СР] маркеров в {proj}...")
    rc, stdout, _ = run(["git", "log", "--oneline", "-20"], cwd=proj_dir)
    if rc == 0:
        for line in stdout.splitlines():
            if "[СР]" in line:
                problems.append(f"Найден [СР] в коммите: {line[:80]}")

    # 2. Нет uncommitted-изменений
    log(f"Проверка git-чистоты {proj}...")
    rc, stdout, _ = run(["git", "status", "--porcelain"], cwd=proj_dir)
    if rc != 0:
        problems.append(f"git status упал (rc={rc})")
    elif stdout.strip():
        problems.append(f"Есть uncommitted-изменения:\n{stdout.strip()[:300]}")

    # 3. check_roster rc=0
    log("Запуск check_roster.py...")
    rc, stdout, _ = run([sys.executable, str(CHECK_ROSTER)], cwd=ORCHESTRATION)
    if rc != 0:
        problems.append(f"check_roster.py rc={rc}: {stdout[:200]}")

    # 3b. L2-гейт самого протокола (план v3, фаза 3): py_compile + bash -n + guard + kg_validate
    log("Запуск release_gate.py (L2-гейт протокола)...")
    rc, stdout, _ = run([sys.executable, str(ORCHESTRATION / "scripts" / "release_gate.py")],
                        cwd=ORCHESTRATION)
    if rc != 0:
        problems.append(f"release_gate.py rc={rc}: {stdout[-400:]}")

    # 4. Ассеты закоммичены (если есть директория assets/)
    assets_dir = proj_dir / "assets"
    if assets_dir.exists():
        rc, stdout, _ = run(["git", "status", "--porcelain", "assets/"], cwd=proj_dir)
        if stdout.strip():
            problems.append(f"Есть uncommitted-изменения в assets/:\n{stdout.strip()[:200]}")

    # 5. ui_gate пройден (проверяем наличие недавних ui_gate отчётов)
    log(f"Проверка ui_gate для {proj}...")
    ui_gate_ok = False
    for report_file in sorted(REPORTS_DIR.glob("ui_gate-*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        text = read_text(report_file)
        if "ship_decision.*pass" in text or "все оси ≥1.0" in text.lower():
            ui_gate_ok = True
            break
    if not ui_gate_ok:
        # Не блокирующий — предупреждение
        problems.append(f"ui_gate: не найдено недавних пройденных гейтов (предупреждение)")

    return len(problems) == 0, problems


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Вердикт Владыки
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_lord_verdict(proj: str) -> str | None:
    """Возвращает последний вердикт Владыки для проекта из journal.md."""
    text = read_text(JOURNAL)
    pattern = re.compile(
        rf"ВЕРДИКТ:\s*{re.escape(proj)}\s*[—-]\s*(ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ)",
        re.IGNORECASE,
    )
    for line in reversed(text.splitlines()):
        m = pattern.search(line)
        if m:
            return m.group(1).upper()
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Версия и теги
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_next_version(proj: str) -> str:
    """
    Определяет следующую версию по семантическому версионированию.
    Смотрит существующие теги vX.Y.Z для проекта и инкрементирует patch.
    """
    proj_dir = PROJECTS_DIR / proj
    rc, stdout, _ = run(["git", "tag", "--list", f"{proj}-v*"], cwd=proj_dir)
    if rc != 0:
        return "1.0.0"

    tags = stdout.splitlines()
    versions = []
    for tag in tags:
        m = re.search(r"v(\d+)\.(\d+)\.(\d+)", tag)
        if m:
            versions.append((int(m.group(1)), int(m.group(2)), int(m.group(3))))

    if not versions:
        return "1.0.0"

    # Берём последнюю версию и инкрементируем patch
    versions.sort()
    major, minor, patch = versions[-1]
    return f"{major}.{minor}.{patch + 1}"


def get_existing_tags(proj: str) -> list[str]:
    proj_dir = PROJECTS_DIR / proj
    rc, stdout, _ = run(["git", "tag", "--list"], cwd=proj_dir)
    if rc != 0:
        return []
    return stdout.splitlines()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# APK экспорт
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def export_apks(proj: str, version: str) -> list[str]:
    """
    Находит свежие *.apk в проекте и копирует в ~/apkexport/.
    Возвращает список скопированных файлов.
    """
    proj_dir = PROJECTS_DIR / proj
    APKEXPORT.mkdir(parents=True, exist_ok=True)

    copied = []
    rc, stdout, _ = run(["find", ".", "-name", "*.apk", "-type", "f"], cwd=proj_dir)
    if rc != 0:
        return copied

    apk_files = stdout.splitlines()
    for apk_path in apk_files:
        apk_full = proj_dir / apk_path
        if not apk_full.exists():
            continue
        apk_name = Path(apk_path).name
        dest_name = f"{proj}-v{version}-{apk_name}"
        dest_path = APKEXPORT / dest_name

        # Копируем
        rc, _, err = run(["cp", str(apk_full), str(dest_path)])
        if rc == 0:
            copied.append(str(dest_path))
            log(f"APK скопирован: {dest_path}")
        else:
            log(f"⚠️ Не удалось скопировать {apk_full}: {err[:100]}")

    return copied


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Тегирование и пуш
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def tag_and_push(proj: str, version: str) -> tuple[bool, str]:
    """
    Тегирует текущий коммит vX.Y.Z и пушит в origin.
    """
    proj_dir = PROJECTS_DIR / proj
    tag_name = f"{proj}-v{version}"

    # Проверяем, что тег ещё не существует
    existing = get_existing_tags(proj)
    if tag_name in existing:
        return False, f"Тег {tag_name} уже существует"

    # Создаём аннотированный тег
    rc, out, err = run(
        ["git", "tag", "-a", tag_name, "-m", f"Auto-release {proj} v{version}"],
        cwd=proj_dir,
    )
    if rc != 0:
        return False, f"Не удалось создать тег: {err[:200]}"

    # Пушим тег
    rc, out, err = run(["git", "push", "origin", tag_name], cwd=proj_dir)
    if rc != 0:
        return False, f"Не удалось пушить тег: {err[:200]}"

    return True, f"Тег {tag_name} создан и пушлен"


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Отчёт релиза
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def write_report(content: str) -> Path:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    path = REPORTS_DIR / f"release-{content.split()[2] if 'release-' in content else 'unknown'}-{ts}.md"
    path.write_text(content, encoding="utf-8")
    return path


def deliver_report(report_path: Path) -> None:
    """Доставляет отчёт в топик 252 через Telegram Bot API."""
    from _secrets import load_cathedral_token as _load_secrets
    _load_secrets()
    tg_token = os.environ.get("CATHEDRAL_BOT_TOKEN", "")
    if not tg_token:
        log("⚠️ CATHEDRAL_BOT_TOKEN не задан — отчёт не доставлен в Telegram")
        return
    rc, out, err = run([
        "curl", "-s", "-X", "POST",
        f"https://api.telegram.org/bot{tg_token}/sendDocument",
        "-F", "chat_id=-1004431090317",
        "-F", "message_thread_id=252",
        "-F", f"caption=Релиз {report_path.stem}",
        f"-F", f"document=@{report_path}",
    ])
    if rc == 0:
        try:
            resp = json.loads(out)
            if resp.get("ok"):
                log("Отчёт релиза доставлен в топик 252")
            else:
                log(f"⚠️ Доставка не удалась: {resp.get('description', 'unknown')[:200]}")
        except json.JSONDecodeError:
            log("Отчёт отправлен (ответ не JSON)")
    else:
        log(f"⚠️ Ошибка curl: {err[:200]}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Главная функция
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def migrate_to_complete_projects(proj: str) -> tuple[bool, str]:
    """Переносит завершённый (FROZEN) проект из Projects/ в CompleteProjects/.

    Шаги:
    1. Проверяет, что проект существует в Projects/
    2. Создаёт CompleteProjects/ если нужно
    3. Перемещает директорию проекта (включая .git) в архив
    4. Создаёт маркерный файл с датой замораживания
    5. Возвращает (ok, сообщение)
    """
    proj_dir = PROJECTS_DIR / proj
    dest_dir = COMPLETE_PROJECTS_DIR / proj

    if not proj_dir.exists():
        return False, f"Проект {proj} не найден в Projects/"

    if dest_dir.exists():
        return False, f"Проект {proj} уже есть в CompleteProjects/"

    try:
        COMPLETE_PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
        # Перемещаем всю директорию (включая .git, историю коммитов, теги)
        import shutil
        shutil.move(str(proj_dir), str(dest_dir))

        # Маркер замораживания
        marker = dest_dir / "FROZEN_AT.md"
        marker.write_text(
            f"# Проект {proj} заморожен (FROZEN)\n"
            f"Дата: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}\n"
            f"Причина: выполнен авто-релиз через release_project.py\n"
            f"Статус: архив, изменения не принимаются.\n",
            encoding="utf-8",
        )
        log(f"Проект {proj} перенесён в CompleteProjects/")
        return True, f"Проект {proj} перенесён в CompleteProjects/"
    except Exception as e:
        return False, f"Ошибка переноса {proj} в CompleteProjects/: {e}"

def release_project(proj: str) -> int:
    """Выполняет полный цикл релиза для проекта."""
    log(f"=== Авто-релиз проекта {proj} (Фаза 3) ===")

    report_lines = []
    report_lines.append(f"# Авто-релиз: {proj}")
    report_lines.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    report_lines.append("")

    # 1. Проверка вердикта Владыки
    verdict = get_lord_verdict(proj)
    report_lines.append(f"## Вердикт Владыки: {verdict or 'не найден'}")
    if verdict != "ГОРЯЧИЙ":
        report_lines.append("❌ Релиз отменён: Владыка не вынес ВЕРДИКТ: ГОРЯЧИЙ")
        write_text(REPORTS_DIR / f"release-{proj}-cancelled-{datetime.now().strftime('%Y%m%d-%H%M')}.md",
                   "\n".join(report_lines))
        return 1

    # 2. Чек-лист релиза
    log("Проверка чек-листа релиза...")
    checklist_ok, checklist_problems = check_release_checklist(proj)
    report_lines.append("## Чек-лист релиза")
    if checklist_ok:
        report_lines.append("✅ Все проверки пройдены")
    else:
        report_lines.append("❌ Чек-лист НЕ пройден:")
        for p in checklist_problems:
            report_lines.append(f"- {p}")
        report_lines.append("\nРелиз отменён.")
        write_text(REPORTS_DIR / f"release-{proj}-failed-checklist-{datetime.now().strftime('%Y%m%d-%H%M')}.md",
                   "\n".join(report_lines))
        return 1

    # 3. Определение версии
    version = get_next_version(proj)
    report_lines.append(f"\n## Версия: v{version}")

    # 4. Тегирование и пуш
    log(f"Тегирование v{version}...")
    tag_ok, tag_msg = tag_and_push(proj, version)
    report_lines.append(f"\n## Тег: {'✅ ' + tag_msg if tag_ok else '❌ ' + tag_msg}")
    if not tag_ok:
        write_text(REPORTS_DIR / f"release-{proj}-tag-failed-{datetime.now().strftime('%Y%m%d-%H%M')}.md",
                   "\n".join(report_lines))
        return 2

    # 5. APK экспорт
    log("Экспорт APK...")
    apk_files = export_apks(proj, version)
    report_lines.append(f"\n## APK экспорт ({len(apk_files)} файлов)")
    for apk in apk_files:
        report_lines.append(f"- {apk}")

    # 6. Составление отчёта
    report_lines.append("\n## Итог")
    report_lines.append(f"- Проект: {proj}")
    report_lines.append(f"- Версия: v{version}")
    report_lines.append(f"- Тег: {proj}-v{version}")
    report_lines.append(f"- APK файлов: {len(apk_files)}")
    report_lines.append(f"- Статус: ✅ Релиз выполнен")

    report_path = REPORTS_DIR / f"release-{proj}-v{version}-{datetime.now().strftime('%Y%m%d-%H%M')}.md"
    write_text(report_path, "\n".join(report_lines))
    log(f"Отчёт записан: {report_path}")

    # 7. Доставка в топик 252
    deliver_report(report_path)

    # 8. Миграция в CompleteProjects (FROZEN архив)
    migr_ok, migr_msg = migrate_to_complete_projects(proj)
    report_lines.append(f"\n## Архивация: {'✅ ' + migr_msg if migr_ok else '⚠️ ' + migr_msg}")

    return 0


def main() -> int:
    if len(sys.argv) < 2:
        print("Использование: release_project.py <проект>")
        print(f"Доступные проекты: {', '.join(PROJECTS)}")
        return 2

    proj = sys.argv[1]
    if proj not in PROJECTS:
        print(f"Неизвестный проект: {proj}")
        print(f"Доступные: {', '.join(PROJECTS)}")
        return 2

    return release_project(proj)


if __name__ == "__main__":
    sys.exit(main())
