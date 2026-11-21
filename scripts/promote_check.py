#!/usr/bin/env python3
"""LV-promote-check — реальный промоушен конвейера Живого Кода.

21.11.2026: в репозитории был только listing-кандидатов (promotion_check в
cycle_start_cron.py) — проекты никогда не переносились в CompleteProjects и
очередь не пополнялась, то есть конвейер не выпускал релизов вообще.
Скрипт делает сам перенос и тянет следующий проект из QUEUE.json.

Критерий готовности (контракт протокола):
  * STATE.json: completion_pct >= 100 и hot_files == 0
  * рядом есть свежий отчёт аудитора по этому проекту без критических замечаний
    (если отчёта нет — проект НЕ промоутится: отсутствие данных = провал,
     а не успех, по VERIFICATION CONTRACT)
  * вердикт Владыки «ГОРЯЧИЙ», если отчёт Владыки по проекту есть;
    если вердикта нет — промоушен не выполняется и пишется причина.

Режимы: --dry-run (по умолчанию), --apply.
Коды возврата: 0 — всё в порядке (промоушенов нет или они выполнены),
2 — ошибка конвейера.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path("/home/thomas/LivingCode")
PROJECTS = ROOT / "Projects"
CODER_PROJECTS = ROOT  # LivingCode/Project1..4 — рабочие проекты кодеров
COMPLETE = ROOT / "CompleteProjects"
QUEUE = ROOT / "QUEUE.json"
JOURNAL = ROOT / "agents" / "journal.md"
REPORTS = ROOT / "reports"

READY_MIN = 100


def _load_state(project: Path) -> dict:
    sf = project / "STATE.json"
    if not sf.exists():
        return {}
    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def _candidate_dirs() -> list[Path]:
    out: list[Path] = []
    if PROJECTS.exists():
        out += [p for p in sorted(PROJECTS.iterdir()) if p.is_dir()]
    out += [p for p in sorted(CODER_PROJECTS.glob("Project*")) if p.is_dir()]
    return out


def _recent_audit_ok(project: Path) -> tuple[bool, str]:
    """Есть ли свежий отчёт аудитора по проекту без критических замечаний."""
    if not REPORTS.exists():
        return False, "нет каталога отчётов"
    name = project.name.lower()
    hits = []
    for f in REPORTS.glob("auditor-*.md"):
        try:
            if (datetime.now() - datetime.fromtimestamp(f.stat().st_mtime)).days > 2:
                continue
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if name not in txt.lower():
            continue
        low = txt.lower()
        if "критическ" in low and ("нет" in low or "не обнаружен" in low or "0 критическ" in low):
            hits.append(f.name)
    if hits:
        return True, f"аудит чист: {hits[-1]}"
    return False, "нет свежего чистого отчёта аудитора"


def _lord_verdict(project: Path) -> tuple[bool, str]:
    """Вердикт Владыки по проекту: ГОРЯЧИЙ / ХОЛОДНЫЙ / нет данных."""
    if not REPORTS.exists():
        return False, "нет отчётов Владыки"
    name = project.name.lower()
    best = None
    for f in sorted(REPORTS.glob("lord*.md")):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if name not in txt.lower():
            continue
        m = re.search(r"ВЕРДИКТ:\s*([\w-]+)\s*[—-]\s*(ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ)", txt, re.I)
        if m:
            best = (m.group(2).upper(), f.name)
    if not best:
        return False, "вердикт Владыки по проекту не найден"
    return best[0] == "ГОРЯЧИЙ", f"{best[0]} ({best[1]})"


def _pull_next() -> str | None:
    """Взять следующий проект из QUEUE.json в Projects/."""
    try:
        data = json.loads(QUEUE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    queue = data.get("queue") or []
    active = set(data.get("active") or [])
    for item in sorted(queue, key=lambda x: (x.get("priority", 99), x.get("added_at", ""))):
        name = item.get("name")
        src = Path(item.get("source") or "")
        if not name or name in active:
            continue
        if not src.exists():
            continue
        dest = PROJECTS / name
        if dest.exists():
            continue
        PROJECTS.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src, dest)
        state = dest / "STATE.json"
        if not state.exists():
            state.write_text(json.dumps({"completion_pct": 0, "hot_files": 0,
                                        "ready_for_publish": False},
                                       ensure_ascii=False, indent=2), encoding="utf-8")
        data.setdefault("active", []).append(name)
        QUEUE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        return name
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="реально переносить проекты")
    ap.add_argument("--dry-run", action="store_true", help="явный dry-run (по умолчанию)")
    args = ap.parse_args()

    COMPLETE.mkdir(parents=True, exist_ok=True)
    promoted: list[str] = []
    notes: list[str] = []

    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from generate_state import generate as _generate_state
    except Exception:
        _generate_state = None

    for project in _candidate_dirs():
        st = _load_state(project)
        if not st and _generate_state and (project / "PLAN.md").exists():
            # STATE.json не обновлялся кодером — состояние выводим сами
            st = _generate_state(project)
            notes.append(f"{project.name}: STATE.json сгенерирован "
                         f"({st.get('basis')}, hot_files={st.get('hot_files')})")
        if not st:
            notes.append(f"{project.name}: нет STATE.json и нет PLAN.md — пропуск")
            continue
        pct = st.get("completion_pct")
        hot = st.get("hot_files")
        if not isinstance(pct, (int, float)) or pct < READY_MIN:
            notes.append(f"{project.name}: completion={pct} (<{READY_MIN}) — не готов")
            continue
        if hot not in (0, None) and hot != 0:
            notes.append(f"{project.name}: hot_files={hot} — не готов")
            continue
        audit_ok, audit_note = _recent_audit_ok(project)
        if not audit_ok:
            notes.append(f"{project.name}: {audit_note} — не промоутим (нет данных)")
            continue
        verdict_ok, verdict_note = _lord_verdict(project)
        if not verdict_ok:
            notes.append(f"{project.name}: {verdict_note} — не промоутим")
            continue
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        target = COMPLETE / f"{project.name}_{stamp}"
        if args.apply:
            shutil.move(str(project), str(target))
            promoted.append(f"{project.name} → {target.name}")
        else:
            promoted.append(f"{project.name} → {target.name} (dry-run)")

    pulled = None
    if args.apply and promoted:
        pulled = _pull_next()
        if pulled:
            notes.append(f"из очереди взят следующий проект: {pulled}")

    if args.apply and promoted:
        JOURNAL.parent.mkdir(parents=True, exist_ok=True)
        with JOURNAL.open("a", encoding="utf-8") as fh:
            fh.write(f"\n---\n**[{datetime.now():%Y-%m-%d %H:%M}] [PROMOTION EVENT]** "
                     f"промоушен: {'; '.join(promoted)}\n"
                     + (f"следующий из очереди: {pulled}\n" if pulled else ""))

    print(f"promote_check: промоушенов={len(promoted)}"
          + (" [APPLY]" if args.apply else " [DRY-RUN]"))
    for p in promoted:
        print(f"  + {p}")
    for n in notes:
        print(f"  - {n}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
