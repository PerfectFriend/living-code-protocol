#!/usr/bin/env python3
"""Генератор STATE.json для проектов Живого Кода.

21.11.2026: у Project1–4 (рабочие проекты кодеров) STATE.json не было
вообще — конвейер промоушена не видел их работы, поэтому релизов не было
ни за месяц. Метрики берём из PLAN.md (чекбоксы) и git status (hot_files).

completion_pct = выполненные чекбоксы / все чекбоксы * 100
hot_files      = число изменённых отслеживаемых файлов (git status --porcelain)
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def _plan_completion(plan: Path) -> tuple[int, str]:
    try:
        txt = plan.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return 0, "нет PLAN.md"
    done = len(re.findall(r"^\s*[-*]\s*\[[xX✓✅]\]", txt, re.M))
    todo = len(re.findall(r"^\s*[-*]\s*\[\s?\]", txt, re.M))
    total = done + todo
    if total == 0:
        return 0, "в PLAN.md нет чекбоксов"
    return int(round(done * 100 / total)), f"{done}/{total} чекбоксов"


def _hot_files(project: Path) -> int:
    if not (project / ".git").exists():
        return 0
    try:
        out = subprocess.run(["git", "-C", str(project), "status", "--porcelain"],
                             capture_output=True, text=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return 0
    return len([l for l in out.splitlines() if l.strip()])


def generate(project: Path) -> dict:
    pct, basis = _plan_completion(project / "PLAN.md")
    hot = _hot_files(project)
    state = {
        "project": project.name,
        "completion_pct": pct,
        "hot_files": hot,
        "ready_for_publish": pct >= 100 and hot == 0,
        "basis": basis,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }
    (project / "STATE.json").write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    return state


if __name__ == "__main__":
    for arg in sys.argv[1:]:
        p = Path(arg)
        if p.is_dir():
            print(json.dumps(generate(p), ensure_ascii=False))
        else:
            print(f"нет такого проекта: {arg}", file=sys.stderr)
