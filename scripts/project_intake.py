#!/usr/bin/env python3
"""Рекрутёр (Project Intake) — приём недоделанных проектов владельца.

Приказ владельца 04.11.2026:
  «добавить входную очередь проектов — брать следующий недоделанный проект
   из ~/Projects (в алфавитном порядке). Я закидываю в ту папку проекты,
   начатые в других системах, и просто забываю о них, пока они не готовы
   и не появились в CompleteProjects».

Контур:
  1. Найти опустевший слот: LV-coder-<X> с enabled=False (проект закрыт,
     перенесён в CompleteProjects, крон остановлен).
  2. Выбрать следующий кандидата из ~/Projects (алфавит), которого ещё нет
     в ~/LivingCode/Projects и который не в запретном списке владельца.
  3. Скопировать проект в ~/LivingCode/Projects/<имя> (без мусора).
  4. Запустить слот Рекрутёра (LLM): аудит состояния проекта + новый
     PLAN.md + ровно один MD-отчёт.
  5. Перепрофилировать опустевший крон: имя, промпт (generic-кодер с
     подставленным проектом) и resume --run-now.

Без кандидата или без свободного слота — тихий выход rc=0 (крон дешёвый).
"""
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

HOME = Path.home()
SRC_DIR = HOME / "Projects"                      # входная очередь владельца
LC_ROOT = HOME / "LivingCode"
DST_DIR = LC_ROOT / "Projects"
ORC = LC_ROOT / "orchestration"
JOBS_JSON = HOME / ".hermes/cron/jobs.json"
JOURNAL = LC_ROOT / "agents" / "journal.md"
ENGINE = ORC / "scripts" / "living_code_agent_wrapper.py"
INTAKE_PROMPT = ORC / "scripts" / "wrappers" / "prompts" / "intake.txt"
CODER_TEMPLATE = ORC / "scripts" / "wrappers" / "prompts" / "coder_generic.txt"
HERMES = "hermes"
PROTOCOL_MODEL = "mistralai/mistral-large-4-1t-a52b"
PROTOCOL_PROVIDER = "nvidia"

# Проекты владельца, которые Рекрутёру брать ЗАПРЕЩЕНО (его собственная
# активная разработка / системные) — приказ «не трогать» из профиля владельца.
DENYLIST = {
    "superguard", "paranoidx", "godmodecoder", "hermesskills",
    "catvangoghflutter", "catvangogh", "sgtest", "pxnode", "livingcode",
    "orchestration", "apkexport",
}
# Придержанные проекты: имена в orchestration/state/intake_holds.txt.
# ПРАВИЛО ВЛАДЕЛЬЦА 05.11.2026: ~/Projects только ЧИТАЕМ — никаких маркеров
# и записей в папке проектов; вся работа с КОПИЕЙ в ~/LivingCode/Projects.
HOLDS_FILE = ORC / "state" / "intake_holds.txt"
# Тяжёлый/регенерируемый мусор не копируем.
RSYNC_EXCLUDES = ["node_modules", "__pycache__", ".dart_tool", ".gradle",
                  "build", ".venv", "venv", "*.pyc", ".idea", ".vscode"]


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def load_jobs() -> list[dict]:
    try:
        d = json.loads(JOBS_JSON.read_text(encoding="utf-8"))
        return d.get("jobs", []) if isinstance(d, dict) else d
    except Exception as e:
        log(f"не удалось прочитать {JOBS_JSON}: {e}")
        return []


def vacant_slots(jobs: list[dict]) -> list[dict]:
    """Опустевшие кодер-кроны: LV-coder-* с enabled=False (проект закрыт)."""
    return sorted((j for j in jobs
                   if j.get("name", "").startswith("LV-coder-")
                   and not j.get("enabled")),
                  key=lambda j: j["name"])


def candidates() -> list[Path]:
    """Следующий недоделанный проект владельца (алфавит, без дублей)."""
    if not SRC_DIR.is_dir():
        return []
    existing = {p.name.lower() for p in DST_DIR.iterdir()} if DST_DIR.is_dir() else set()
    holds = set()
    if HOLDS_FILE.exists():
        holds = {ln.strip().lower() for ln in HOLDS_FILE.read_text(encoding="utf-8").splitlines() if ln.strip()}
    out = []
    for p in sorted(SRC_DIR.iterdir(), key=lambda x: x.name.lower()):
        if not p.is_dir() or p.name.startswith((".", "_")):
            continue
        if p.name.lower() in DENYLIST or p.name.lower() in existing or p.name.lower() in holds:
            continue
        # пустышки и мусор не берём
        try:
            if sum(1 for _ in p.rglob("*")) < 3:
                continue
        except OSError:
            continue
        out.append(p)
    return out


def copy_project(src: Path, name: str) -> Path:
    dst = DST_DIR / name
    cmd = ["rsync", "-a"]
    for ex in RSYNC_EXCLUDES:
        cmd += ["--exclude", ex]
    cmd += [str(src).rstrip("/") + "/", str(dst)]
    rc = subprocess.run(cmd, capture_output=True, text=True)
    if rc.returncode != 0:
        raise RuntimeError(f"rsync: {rc.stderr[:300]}")
    return dst


def run_recruiter_agent(project: str) -> tuple[int, str]:
    """Слот Рекрутёра: аудит проекта + новый PLAN.md + 1 MD-отчёт."""
    env = dict(os.environ)
    env["LIVING_CODE_ROLE"] = "Рекрутёр"
    env["LIVING_CODE_CRON_BUDGET"] = "1500"
    env.setdefault("LIVING_CODE_TELEGRAM", "telegram:-1004431090317:252")
    prompt = INTAKE_PROMPT.read_text(encoding="utf-8").replace("{PROJECT}", project)
    proc = subprocess.run(
        [sys.executable, str(ENGINE), prompt, "None",
         PROTOCOL_MODEL, PROTOCOL_PROVIDER],
        capture_output=True, text=True, timeout=1600, env=env)
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def rewire_cron(job_id: str, old_name: str, project: str) -> str:
    """Вписать новый проект в опустевший крон и запустить его.

    05.11.2026: осиротевшие once-джобы бывают в terminal-состоянии (прошедшее
    once-время), где cron edit/resume отказывает. Надёжный путь — пересоздать
    джобу заново с регулярным расписанием (каждые 2 ч, минута из имени
    проекта, чтобы не совпадать с intake :15 и инквизитором :35).
    """
    slug = re.sub(r"[^a-z0-9-]+", "-", project.lower()).strip("-")
    new_name = f"LV-coder-{slug}"
    minute = 20 + (sum(slug.encode("utf-8")) % 35)
    sched = f"{minute} */2 * * *"
    tpl = CODER_TEMPLATE.read_text(encoding="utf-8").replace("{PROJECT}", project)
    subprocess.run([HERMES, "-p", "default", "cron", "remove", job_id],
                   capture_output=True, text=True)
    r = subprocess.run([HERMES, "-p", "default", "cron", "create", sched,
                        "--name", new_name,
                        "--model", PROTOCOL_MODEL, "--provider", PROTOCOL_PROVIDER,
                        "--pin", "--workdir", str(LC_ROOT), "--deliver", "local", tpl],
                       capture_output=True, text=True)
    if r.returncode != 0:
        return f"create failed: {(r.stderr or r.stdout)[:200]}"
    return (f"{old_name} → {new_name}, расписание {sched} "
            f"(пересоздан: {(r.stdout or '').strip().splitlines()[0][:60]})")


def journal_note(line: str) -> None:
    try:
        with open(JOURNAL, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def main() -> int:
    # flock: два параллельных прогона (ручной + плановый) назначали один и
    # тот же слот дважды, а второй проект оставался без кодера (гон 02:31).
    import fcntl
    lock = open("/tmp/lc_intake.lock", "w")
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        log("предыдущий прогон ещё работает — тихий выход")
        return 0
    log("=== Рекрутёр: скан входной очереди ~/Projects ===")
    jobs = load_jobs()
    if not jobs:
        return 0
    slots = vacant_slots(jobs)
    cands = candidates()
    log(f"свободных слотов: {len(slots)} {[s['name'] for s in slots]}; "
        f"кандидатов: {len(cands)} {[c.name for c in cands[:5]]}")
    if not slots or not cands:
        log("нечего принимать — тихий выход")
        return 0

    slot, cand = slots[0], cands[0]
    log(f"принимаю «{cand.name}» в слот {slot['name']} ({slot['id']})")
    try:
        copy_project(cand, cand.name)
    except Exception as e:
        log(f"копирование не удалось: {e}")
        # источник ~/Projects не трогаем: придерживаем через holds-файл
        try:
            with open(HOLDS_FILE, "a", encoding="utf-8") as fh:
                fh.write(cand.name + "\n")
        except OSError:
            pass
        journal_note(f"[INTAKE_FAIL] {cand.name}: {str(e)[:120]}")
        return 0
    log(f"скопирован в {DST_DIR / cand.name}")

    rc, out = run_recruiter_agent(cand.name)
    log(f"слот Рекрутёра: rc={rc}, хвост: {out.strip()[-400:]}")

    msg = rewire_cron(slot["id"], slot["name"], cand.name)
    log(f"крон: {msg}")
    journal_note(f"[INTAKE] {datetime.now().strftime('%Y-%m-%d %H:%M')} — проект "
                 f"{cand.name} принят в слот {slot['name']}; {msg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
