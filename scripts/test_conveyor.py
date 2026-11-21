#!/usr/bin/env python3
"""Энд-to-end тест конвейера Живого Кода (21.11.2026).

Проверяет ровно схему владельца на временном дереве:
  Projects/ (очередь) → Project1 (рабочий слот) → CompleteProjects/ (релиз)
  + проект удаляется из очереди
  + освободившийся слот получает САМЫЙ БОЛЬШОЙ оставшийся проект из очереди
  + рядом с релизом лежит финальная сопроводительная документация
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = "/home/thomas/LivingCode/orchestration/scripts/conveyor.py"
ROOT = Path(tempfile.mkdtemp(prefix="lv-conveyor-test-"))
FAIL = []


def check(name: str, cond: bool, detail: str = "") -> None:
    print(("  PASS  " if cond else "  FAIL  ") + name + (f" — {detail}" if detail else ""))
    if not cond:
        FAIL.append(name)


def make_project(base: Path, name: str, code_files: int, doc_files: int) -> Path:
    p = base / name
    (p / "src").mkdir(parents=True, exist_ok=True)
    (p / "docs").mkdir(parents=True, exist_ok=True)
    for i in range(code_files):
        (p / "src" / f"mod_{i}.py").write_text("\n".join(f"# строка {j}" for j in range(50)) + "\n",
                                                encoding="utf-8")
    for i in range(doc_files):
        (p / "docs" / f"doc_{i}.md").write_text("\n".join(f"строка {j}" for j in range(20)) + "\n",
                                                encoding="utf-8")
    (p / "PLAN.md").write_text("- [x] готово\n- [x] тоже готово\n", encoding="utf-8")
    return p


def run(args, env=None):
    e = dict(os.environ)
    e["LIVING_CODE_ROOT"] = str(ROOT)
    if env:
        e.update(env)
    return subprocess.run([sys.executable, SCRIPT] + args, capture_output=True, text=True,
                          env=e, timeout=600)


print(f"временное дерево: {ROOT}")
(ROOT / "Projects").mkdir(parents=True)
(ROOT / "CompleteProjects").mkdir(parents=True)
(ROOT / "reports").mkdir(parents=True)
(ROOT / "agents").mkdir(parents=True)

# очередь: три проекта разного размера
make_project(ROOT / "Projects", "маленький", code_files=2, doc_files=1)
make_project(ROOT / "Projects", "средний", code_files=20, doc_files=5)
make_project(ROOT / "Projects", "большой", code_files=60, doc_files=10)

# рабочий слот с «готовым» проектом: 100% холодный код + вердикт ГОРЯЧИЙ
slot = ROOT / "Project1"
(slot / "src").mkdir(parents=True)
(slot / "PLAN.md").write_text("- [x] всё\n", encoding="utf-8")
(slot / "src" / "a.py").write_text("# COLD\nprint('готово')\n", encoding="utf-8")
(slot / "src" / "b.py").write_text("# COLD\nprint('готово')\n", encoding="utf-8")
(slot / "STATE.json").write_text(json.dumps({"project": "мой-проект", "completion_pct": 100,
                                              "hot_files": 0}, ensure_ascii=False), encoding="utf-8")
(ROOT / "reports" / "lord-тест.md").write_text(
    "Отчёт Владыки по проекту мой-проект\nВЕРДИКТ: мой-проект — ГОРЯЧИЙ (все гейты пройдены)\n",
    encoding="utf-8")
# копия проекта в очереди — её обязаны удалить при релизе
make_project(ROOT / "Projects", "мой-проект", code_files=3, doc_files=2)

print("\n1) scan: конвейер видит очередь и слот")
r = run(["scan"])
check("scan отработал", r.returncode == 0, r.stderr[-120:])
check("очередь посчитана", "большой" in r.stdout and "маленький" in r.stdout)
check("слот Project1 найден", "Project1" in r.stdout)

print("\n2) dry-run ничего не меняет")
r = run(["run"])
check("dry-run без --apply", r.returncode == 0)
check("релиз не создан в dry-run", not any((ROOT / "CompleteProjects").iterdir()))

print("\n3) реальный прогон: релиз + очистка очереди + заполнение слота")
r = run(["run", "--apply"])
print("   " + "\n   ".join(r.stdout.strip().splitlines()[-6:]))
complete = list((ROOT / "CompleteProjects").iterdir())
check("релиз создан", len(complete) == 1, complete[0].name if complete else "нет")
if complete:
    rel = complete[0]
    check("в релизе есть исходники", (rel / "src" / "a.py").exists())
    check("есть финальное досье", (rel / "ФИНАЛЬНОЕ_ДОСЬЕ.md").exists())
    txt = (rel / "ФИНАЛЬНОЕ_ДОСЬЕ.md").read_text(encoding="utf-8")
    check("досье описывает холодный код", "100% холодный" in txt)
    check("досье описывает вердикт", "ГОРЯЧИЙ" in txt)
check("проект удалён из очереди", not (ROOT / "Projects" / "мой-проект").exists())
check("очередь не потеряла других", (ROOT / "Projects" / "маленький").exists()
      and (ROOT / "Projects" / "средний").exists())
check("слот заполнен снова", (ROOT / "Project1").exists() and (ROOT / "Project1" / "src").exists())
marker = ROOT / "Project1" / ".queue_source"
check("маркер источника записан", marker.exists())
if marker.exists():
    picked = json.loads(marker.read_text(encoding="utf-8"))["project"]
    check("в слот взят самый большой проект", picked == "большой", f"взяли {picked}")

print("\n4) повторный прогон идемпотентен (повторной работы нет)")
r = run(["run", "--apply"])
check("второй прогон без падений", r.returncode == 0)
check("релиз не продублирован", len(list((ROOT / "CompleteProjects").iterdir())) == 1)

print("\n5) манифест и журнал")
man = json.loads((ROOT / "CONVEYOR.json").read_text(encoding="utf-8"))
check("релиз записан в манифест", len(man.get("released", [])) == 1)
jrn = (ROOT / "agents" / "journal.md").read_text(encoding="utf-8")
check("[PROMOTION EVENT] в журнале", "[PROMOTION EVENT]" in jrn)

shutil.rmtree(ROOT, ignore_errors=True)
print("\n" + ("ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ" if not FAIL else f"ПРОВАЛЕНО: {FAIL}"))
sys.exit(1 if FAIL else 0)
