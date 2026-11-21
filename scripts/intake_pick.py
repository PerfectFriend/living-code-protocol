#!/usr/bin/env python3
"""intake_pick.py — детерминированный отборщик входной очереди проектов.

Роль «Вербовщик» (приказ владельца 04.11.2026): владелец складывает заброшенные
проекты в ~/Projects и забывает о них; протокол сам берёт следующий (по
алфавиту), копирует в ~/LivingCode/Projects/, аудитует и запускает в работу.

Режимы:
  --pick          напечатать имя следующего кандидата (или NO_CANDIDATE), rc=0
  --copy NAME     скопировать проект NAME в ~/LivingCode/Projects/ + аудит-заметка
  --status        краткий статус очереди

Журнал решений: ~/.hermes/cron/intake_ledger.json — не берём уже взятые
(status=done/failed) и сорвавшиеся 3 раза.
"""
import json
import os
import shutil
import sys
import time
from pathlib import Path

HOME = Path.home()
SOURCE = HOME / "Projects"
DEST = HOME / "LivingCode" / "Projects"
ARCHIVE = HOME / "LivingCode" / "CompleteProjects"
LEDGER = HOME / ".hermes" / "cron" / "intake_ledger.json"
MAX_TRIES = 3
# Инфраструктура протокола — не проекты для эволюции (без учёта регистра).
EXCLUDE = {"godmodecoder", "hermesskills", "living-code", "livingcode",
           "lost+found"}
# Перестраиваемые артефакты — не тащим в рабочую копию.
IGNORE = shutil.ignore_patterns("node_modules", "__pycache__", ".gradle",
                                "build", "dist", ".venv", "venv",
                                "*.pyc", ".dart_tool")


def load_ledger() -> dict:
    try:
        return json.loads(LEDGER.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_ledger(d: dict) -> None:
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    LEDGER.write_text(json.dumps(d, ensure_ascii=False, indent=1), "utf-8")


def existing_names() -> set:
    """Имена, уже занятые протоколом (в нижнем регистре)."""
    names = set()
    for base in (DEST, ARCHIVE):
        try:
            names.update(p.name.lower() for p in base.iterdir() if p.is_dir())
        except OSError:
            pass
    return names


def candidates() -> list:
    taken = existing_names()
    ledger = load_ledger()
    out = []
    try:
        entries = sorted(SOURCE.iterdir(), key=lambda p: p.name.lower())
    except OSError:
        return out
    for p in entries:
        if not p.is_dir() or p.name.startswith(".") or p.name.lower() in EXCLUDE:
            continue
        if p.name.lower() in taken:
            continue
        rec = ledger.get(p.name, {})
        if rec.get("status") in ("done", "failed"):
            continue
        out.append(p.name)
    return out


def stack_audit(src: Path) -> str:
    """Грубый детерминированный аудит стека — заметка для агента-Вербовщика."""
    lines = [f"# Входной аудит (детерминированный): {src.name}", ""]
    git = "есть (история сохранена)" if (src / ".git").exists() else "нет"
    lines.append(f"- git-репозиторий: {git}")
    markers = [
        ("pubspec.yaml", "Flutter/Dart"),
        ("package.json", "Node.js/JS"),
        ("Cargo.toml", "Rust"),
        ("go.mod", "Go"),
        ("requirements.txt", "Python (pip)"),
        ("pyproject.toml", "Python (pyproject)"),
        ("build.gradle", "Android (Gradle)"),
        ("build.gradle.kts", "Android (Gradle KTS)"),
        ("*.sln", ".NET"),
        ("pom.xml", "Java (Maven)"),
    ]
    stacks = []
    for marker, label in markers:
        if "*" in marker:
            hits = list(src.glob(marker))
        else:
            hits = [src / marker] if (src / marker).exists() else []
        if hits:
            stacks.append(label)
    lines.append("- Стек(и): " + (", ".join(stacks) if stacks else "не определён — смотреть вручную"))
    try:
        top = sorted(p.name for p in src.iterdir())[:25]
        lines.append("- Верхний уровень: " + ", ".join(top))
    except OSError:
        pass
    return "\n".join(lines) + "\n"


def copy_project(name: str) -> int:
    src = SOURCE / name
    dst = DEST / name
    if dst.exists():
        print(f"[intake] {name}: в ~/LivingCode/Projects уже есть — пропускаю")
        return 1
    ledger = load_ledger()
    rec = ledger.get(name, {})
    tries = rec.get("tries", 0)
    if tries >= MAX_TRIES:
        rec["status"] = "failed"
        save_ledger(ledger)
        print(f"[intake] {name}: {MAX_TRIES} неудачных попыток — исключён из очереди")
        return 1
    try:
        shutil.copytree(src, dst, ignore=IGNORE)
    except Exception as e:  # noqa: BLE001
        rec["tries"] = tries + 1
        if rec["tries"] >= MAX_TRIES:
            rec["status"] = "failed"
        save_ledger(ledger)
        print(f"[intake] копирование не удалось ({e})")
        return 1
    (dst / "INTAKE_NOTES.md").write_text(stack_audit(src), encoding="utf-8")
    rec.update({"status": "copied", "copied_at": time.strftime("%Y-%m-%dT%H:%M:%S")})
    save_ledger(ledger)
    print(f"[intake] {name} скопирован в {dst} (без node_modules/build/dist)")
    return 0


def main() -> int:
    mode = sys.argv[1] if len(sys.argv) > 1 else "--pick"
    if mode == "--status":
        taken = existing_names()
        print(f"источники ~/Projects: {len(list(SOURCE.glob('*'))) if SOURCE.exists() else 0}")
        print(f"кандидаты: {candidates() or '— нет —'}")
        print(f"взяты протоколом: {sorted(taken)}")
        return 0
    if mode == "--copy":
        if len(sys.argv) < 3:
            print("usage: intake_pick.py --copy NAME")
            return 2
        return copy_project(sys.argv[2])
    # --pick (по умолчанию)
    cand = candidates()
    if not cand:
        print("NO_CANDIDATE")
        return 0
    print(cand[0])
    return 0


if __name__ == "__main__":
    sys.exit(main())
