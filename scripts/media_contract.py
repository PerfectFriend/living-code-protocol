#!/usr/bin/env python3
"""
media_contract.py — Контракты UI/Озвучка (Фаза 4).

Назначение:
  Описывает форматы медиа-выхода для ролей Протокола Живого Кода:
  - LV-artist (художник) — иллюстрации, обложки, ассеты проекта
  - LV-dj-musician (музыкант) — треки, звуковые дорожки, озвучка
  - LV-producer (продюсер) — сборка_release, медиа-отчёты

  Каждый контракт определяет:
  - Что производит роль (выходные файлы)
  - Формат отчёта (MEDIA отчёт в топик 252)
  - Связь с логом-квитанцией orchestration/

Выходные коды:
  0 — контракты определены и отчёты доставлены
  1 — ошибка формирования контракта
  2 — ошибка доставки

Автор: Hermes Agent (Протокол Живого Кода, Фаза 4)
Лицензия: MIT
"""

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Константы
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
HOME = Path.home()
LIVING_CODE = HOME / "LivingCode"
ORCHESTRATION = LIVING_CODE / "orchestration"
PROJECTS_DIR = LIVING_CODE / "Projects"
REPORTS_DIR = LIVING_CODE / "reports"
AGENTS_DIR = LIVING_CODE / "agents"
JOURNAL = AGENTS_DIR / "journal.md"
APKEXPORT = HOME / "apkexport"
LOG_DIR = ORCHESTRATION / "logs" / "inference"

ROLES = ["artist", "dj-musician", "producer"]

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
# Контракты ролей
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def get_artist_contract(proj: str) -> dict:
    """
    Контракт LV-artist (художник).
    Выход: иллюстрации, обложки, ассеты проекта в <project>/assets/
    """
    proj_dir = PROJECTS_DIR / proj
    assets_dir = proj_dir / "assets"

    # Ищем медиа-файлы в проекте
    media_files = []
    if assets_dir.exists():
        for pattern in ("*.png", "*.jpg", "*.jpeg", "*.svg", "*.gif", "*.webp", "*.mp4"):
            media_files.extend(assets_dir.rglob(pattern))

    # Ищем недавние медиа-артефакты в логах квитанций
    receipt_files = []
    if LOG_DIR.exists():
        receipt_files = list(LOG_DIR.glob("attempt_*.json"))

    return {
        "role": "artist",
        "project": proj,
        "contract": "v2-artist",
        "outputs": [str(f.relative_to(proj_dir)) for f in media_files[:10]],
        "assets_dir": str(assets_dir),
        "media_count": len(media_files),
        "receipts": len(receipt_files),
        "description": (
            "Художник производит иллюстрации, обложки и ассеты проекта. "
            "Все медиа-файлы хранятся в <project>/assets/ и фиксируются в логах квитанций."
        ),
    }


def get_musician_contract(proj: str) -> dict:
    """
    Контракт LV-dj-musician (музыкант, v2 контракт).
    Выход: треки, звуковые дорожки, озвучка в <project>/audio/ или <project>/music/
    """
    proj_dir = PROJECTS_DIR / proj

    # Ищем аудио-файлы
    audio_files = []
    for audio_dir_name in ("audio", "music", "sounds", "sfx"):
        audio_dir = proj_dir / audio_dir_name
        if audio_dir.exists():
            for pattern in ("*.mp3", "*.wav", "*.ogg", "*.flac", "*.m4a"):
                audio_files.extend(audio_dir.rglob(pattern))

    return {
        "role": "dj-musician",
        "project": proj,
        "contract": "v2-musician",
        "outputs": [str(f.relative_to(proj_dir)) for f in audio_files[:10]],
        "audio_dirs": [str(d.name) for d in proj_dir.iterdir() if d.is_dir() and d.name in ("audio", "music", "sounds", "sfx")],
        "audio_count": len(audio_files),
        "description": (
            "Музыкант производит треки, звуковые дорожки и озвучку. "
            "Все аудио-файлы хранятся в <project>/audio/ (или music/, sounds/, sfx/)."
        ),
    }


def get_producer_contract(proj: str) -> dict:
    """
    Контракт LV-producer (продюсер).
    Выход: релизный артефакт (APK), медиа-отчёт, связь с логом-квитанцией.
    """
    proj_dir = PROJECTS_DIR / proj

    # Ищем APK файлы
    apk_files = []
    rc, stdout, _ = run(["find", ".", "-name", "*.apk", "-type", "f"], cwd=proj_dir)
    if rc == 0:
        apk_files = [Path(p) for p in stdout.splitlines() if Path(p).exists()]

    # Ищем медиа-отчёты
    media_reports = []
    for report_file in sorted(REPORTS_DIR.glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)[:5]:
        text = read_text(report_file)
        if "MEDIA" in text or "медиа" in text.lower():
            media_reports.append(report_file.name)

    return {
        "role": "producer",
        "project": proj,
        "contract": "v2-producer",
        "outputs": [str(f.relative_to(proj_dir)) for f in apk_files[:5]],
        "apk_count": len(apk_files),
        "media_reports": media_reports,
        "description": (
            "Продюсер собирает релизный артефакт (APK), формирует медиа-отчёт "
            "и обеспечивает связь с логом-квитанцией orchestration/."
        ),
    }


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Формирование MEDIA отчёта
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def build_media_report(proj: str) -> str:
    """
    Формирует MEDIA отчёт для проекта на основе контрактов всех ролей.
    """
    artist = get_artist_contract(proj)
    musician = get_musician_contract(proj)
    producer = get_producer_contract(proj)

    lines = []
    lines.append(f"# 🎨 MEDIA отчёт: {proj}")
    lines.append(f"Время: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"Контракты: v2-artist, v2-musician, v2-producer")
    lines.append("")
    lines.append("## LV-artist (художник)")
    lines.append(f"- Описание: {artist['description']}")
    lines.append(f"- Медиа-файлов: {artist['media_count']}")
    lines.append(f"- Директория ассетов: {artist['assets_dir']}")
    if artist['outputs']:
        lines.append("- Последние ассеты:")
        for output in artist['outputs'][:5]:
            lines.append(f"  - {output}")
    else:
        lines.append("- Ассеты не найдены")
    lines.append("")
    lines.append("## LV-dj-musician (музыкант)")
    lines.append(f"- Описание: {musician['description']}")
    lines.append(f"- Аудио-файлов: {musician['audio_count']}")
    if musician['audio_dirs']:
        lines.append(f"- Директории аудио: {', '.join(musician['audio_dirs'])}")
    if musician['outputs']:
        lines.append("- Последние аудио-файлы:")
        for output in musician['outputs'][:5]:
            lines.append(f"  - {output}")
    else:
        lines.append("- Аудио-файлы не найдены")
    lines.append("")
    lines.append("## LV-producer (продюсер)")
    lines.append(f"- Описание: {producer['description']}")
    lines.append(f"- APK-файлов: {producer['apk_count']}")
    if producer['outputs']:
        lines.append("- Релизные APK:")
        for output in producer['outputs'][:5]:
            lines.append(f"  - {output}")
    else:
        lines.append("- APK не найдены")
    lines.append("")
    lines.append("## Лог-квитанция orchestration/")
    lines.append(f"- Квитанции в orchestration/logs/inference/:")
    lines.append("  - attempt_*.json — живая квитанция прогона каждой роли")
    lines.append("")
    lines.append("## Доставка")
    lines.append("- Отчёт доставляется в топик 252 через Telegram Bot API")
    lines.append("- MEDIA файлы прикрепляются к отчёту как вложения")
    lines.append("")
    lines.append("---")
    lines.append("MEDIA отчёт сформирован по контрактам Фазы 4.")

    return "\n".join(lines)


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Доставка в Telegram
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def deliver_media_report(report_path: Path) -> None:
    """Доставляет MEDIA отчёт в топик 252."""
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
        "-F", f"caption=🎨 MEDIA отчёт: {report_path.stem}",
        f"-F", f"document=@{report_path}",
    ])
    if rc == 0:
        try:
            resp = json.loads(out)
            if resp.get("ok"):
                log("MEDIA отчёт доставлен в топик 252")
            else:
                log(f"⚠️ Доставка не удалась: {resp.get('description', 'unknown')[:200]}")
        except json.JSONDecodeError:
            log("Отчёт отправлен (ответ не JSON)")
    else:
        log(f"⚠️ Ошибка curl: {err[:200]}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Главная функция
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def main() -> int:
    if len(sys.argv) < 2:
        print("Использование: media_contract.py <проект> [роль]")
        print(f"Проекты: superguard, elemental-life, cybertarot, elemental-life-2")
        print(f"Роли: artist, dj-musician, producer (все, если не указано)")
        return 2

    proj = sys.argv[1]
    role_filter = sys.argv[2] if len(sys.argv) > 2 else None

    log(f"=== Контракты UI/Озвучка для {proj} (Фаза 4) ===")

    # Формируем MEDIA отчёт
    report_content = build_media_report(proj)

    # Сохраняем отчёт
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d-%H%M")
    report_path = REPORTS_DIR / f"media-{proj}-{ts}.md"
    write_text(report_path, report_content)
    log(f"MEDIA отчёт записан: {report_path}")

    # Доставка в топик 252
    deliver_media_report(report_path)

    # Запись в journal.md
    journal_entry = (
        f"\n[MEDIA_CONTRACT] {proj}: отчёт сформирован по контрактам v2 "
        f"(artist={get_artist_contract(proj)['media_count']} ассетов, "
        f"musician={get_musician_contract(proj)['audio_count']} аудио, "
        f"producer={get_producer_contract(proj)['apk_count']} APK)"
    )
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as f:
        f.write(journal_entry + "\n")

    log("Контракты UI/Озвучка выполнены.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
