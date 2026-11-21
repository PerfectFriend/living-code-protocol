#!/usr/bin/env bash
# Проверка здоровья реестра кронов и обвязки роя.
set -euo pipefail

ORC="/home/thomas/LivingCode/orchestration"
H="$HOME/.hermes"

python3 - "$ORC" "$H" <<'PY'
import json, os, re, subprocess, sys
from pathlib import Path

orc, home = Path(sys.argv[1]), Path(sys.argv[2])
jobs_file = home / "cron" / "jobs.json"
problems, notes = [], []

if not jobs_file.exists():
    print("НЕТ ~/.hermes/cron/jobs.json — сначала bin/restore-config.sh")
    sys.exit(1)

jobs = json.loads(jobs_file.read_text()).get("jobs", [])
scripts_dir = home / "scripts"

print(f"Задач в реестре: {len(jobs)}")
paused = sum(1 for j in jobs if not j.get("enabled"))
print(f"На паузе: {paused} | активных: {len(jobs) - paused}")

bad_paths = re.compile(r"C:\\\\Users|GodModeCoder|\.hermes/scripts/python")
for j in jobs:
    name = j.get("name", j.get("id"))
    script = j.get("script")
    if script:
        target = scripts_dir / script
        if not target.exists():
            problems.append(f"{name}: скрипт не найден — {target}")
    if not j.get("no_agent"):
        if not j.get("model") or not j.get("provider"):
            problems.append(f"{name}: не задана модель/провайдер (уйдёт в drift_skip)")
    wd = j.get("workdir")
    if wd and not Path(wd).exists():
        problems.append(f"{name}: workdir не существует — {wd}")
    prompt = (j.get("prompt") or "")
    if bad_paths.search(prompt):
        problems.append(f"{name}: в промпте хардкод пути (C:\\Users / GodModeCoder / python-в-script)")
    if str(script or "") and (" " in str(script) or str(script).startswith("/")):
        problems.append(f"{name}: --script должен быть путём внутри ~/.hermes/scripts, а не '{script}'")

print("\nСимлинк ~/.hermes/scripts:", "OK" if scripts_dir.is_symlink() else "НЕ СИМЛИНК (скрипты вне git!)")
if not scripts_dir.is_symlink():
    problems.append("~/.hermes/scripts не является симлинком — обвязка снова может потеряться")

for extra in [orc / "models.yaml"]:
    if not extra.exists():
        notes.append(f"нет {extra} (карта моделей — Фаза 3)")

print("\n=== проблемы ===")
if problems:
    for p in problems:
        print(" -", p)
else:
    print(" нет")
if notes:
    print("\n=== замечания ===")
    for n in notes:
        print(" -", n)

# размеры
print("\n=== размеры ===")
for p in [orc, orc / "skills-export", orc / "runtime", orc / ".git"]:
    if p.exists():
        out = subprocess.run(["du", "-sh", str(p)], capture_output=True, text=True).stdout.split()[0]
        print(f"  {out:>7}  {p}")

print("\nВердикт:", "готово к восстановлению на чистой машине" if not problems else "ЕСТЬ ПРОБЛЕМЫ (см. выше)")
sys.exit(0 if not problems else 1)
PY
