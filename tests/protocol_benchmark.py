#!/usr/bin/env python3
"""protocol_benchmark.py — held-out benchmark протокола («наш Claw-Eval», Фаза 1 плана v3).

10+ эталонных проверок, которые обязаны проходить после ЛЮБОЙ правки протокола.
Запуск: python3 tests/protocol_benchmark.py [--quick]
Exit 0 = все проверки зелёные. Каждая проверка печатает evidence (rc/вывод).
"""
import json
import re
import subprocess
import sys
from pathlib import Path

LC = Path.home() / "LivingCode"
ORC = LC / "orchestration"
SCRIPTS = ORC / "scripts"
WRAPPERS = SCRIPTS / "wrappers"
BANNED = ("nemotron",)
PROTOCOL_MODEL = "mistralai/mistral-large-4-1t-a52b"

ACTIVE_FILES = [
    SCRIPTS / "living_code_agent_wrapper.py",
    SCRIPTS / "check_roster.py",
    ORC / "jobs" / "jobs.json",
    Path.home() / ".hermes" / "cron" / "jobs.json",
    Path.home() / ".hermes" / "config.yaml",
    ORC / "hermes-config" / "config.yaml",
]


def run(cmd, timeout=240):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return 124, "timeout"


CHECKS = []


def check(fn):
    CHECKS.append(fn)
    return fn


@check
def banned_absent_in_active_layer():
    """Бан-детект в АКТИВНЫХ полях маршрутизации (model), а не в константах бана:
    BANNED_MODEL_SUBSTRINGS/HISTORICALLY_DEAD/комментарии/seguridad-строки — легитимны."""
    hits = []
    # JSON-реестры: только активное поле model (model_snapshot — исторический снимок)
    for f in (ORC / "jobs" / "jobs.json", Path.home() / ".hermes" / "cron" / "jobs.json"):
        if not f.exists():
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        jobs = data["jobs"] if isinstance(data, dict) and "jobs" in data else data
        for j in jobs:
            m = str(j.get("model") or "")
            if any(b in m.lower() for b in BANNED):
                hits.append(f"{f.name}: job {j.get('name')} model={m}")
    # YAML-конфиги: только значения model:
    for f in (Path.home() / ".hermes" / "config.yaml", ORC / "hermes-config" / "config.yaml"):
        if not f.exists():
            continue
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "model" in ln.lower() and any(b in ln.lower() for b in BANNED):
                hits.append(f"{f.name}: {ln.strip()[:80]}")
    # Python-движки: nemotron вне ban-контекста (комментарии, BANNED, HISTORICALLY_DEAD-блок, сообщения бана)
    ban_keys = ("BANNED", "HISTORICALLY_DEAD", "бан", "БАН", "саботаж", "запрещ", "#",
                "SECURITY_INCIDENT", "решение владельца", "решением владельца")
    for f in (SCRIPTS / "living_code_agent_wrapper.py", SCRIPTS / "check_roster.py"):
        if not f.exists():
            continue
        in_dead = False
        for ln in f.read_text(encoding="utf-8", errors="replace").splitlines():
            if "HISTORICALLY_DEAD =" in ln:
                in_dead = True
            if in_dead and ln.strip() in ("})", "})"):
                in_dead = False
            if any(b in ln.lower() for b in BANNED) and not in_dead:
                if not any(k in ln for k in ban_keys):
                    hits.append(f"{f.name}: {ln.strip()[:100]}")
            if in_dead and ln.strip() == "})":
                in_dead = False
    # Обёртки: nemotron только в не-комментарий строках (в шапке-истории бана — легитимно)
    for w in WRAPPERS.glob("*.sh"):
        for ln in w.read_text(encoding="utf-8", errors="replace").splitlines():
            s = ln.strip()
            if s.startswith("#"):
                continue
            if any(b in s.lower() for b in BANNED):
                hits.append(f"{w.name}: {s[:100]}")
    return not hits, f"запрещённые модели в активных полях маршрутизации: {hits if hits else 'нет'} " \
                     f"(константы бана BANNED/HISTORICALLY_DEAD исключены по дизайну)"


@check
def protocol_model_is_mistral():
    txt = (SCRIPTS / "living_code_agent_wrapper.py").read_text(encoding="utf-8")
    ok = f'PROTOCOL_MODEL = "{PROTOCOL_MODEL}"' in txt and 'BANNED_MODEL_SUBSTRINGS = ("nemotron",)' in txt
    return ok, f"PROTOCOL_MODEL={PROTOCOL_MODEL}, бан-проверка на месте"


@check
def py_compile_all():
    bad = []
    for f in sorted(SCRIPTS.glob("*.py")):
        if ".orig-" in f.name:
            continue
        rc, out = run([sys.executable, "-m", "py_compile", str(f)], 60)
        if rc != 0:
            bad.append(f.name)
    return not bad, f"py_compile: {'OK' if not bad else 'FAIL ' + ','.join(bad)}"


@check
def bash_n_all_wrappers():
    bad = []
    files = sorted(WRAPPERS.glob("*.sh")) + sorted(SCRIPTS.glob("*.sh"))
    for f in files:
        rc, _ = run(["bash", "-n", str(f)], 30)
        if rc != 0:
            bad.append(f.name)
    return not bad, f"bash -n: {'OK' if not bad else 'FAIL ' + ','.join(bad)} ({len(files)} скриптов)"


@check
def jobs_json_valid_and_clean():
    data = json.loads((ORC / "jobs" / "jobs.json").read_text(encoding="utf-8"))
    jobs = data["jobs"] if isinstance(data, dict) else data
    bad = [j.get("name", "?") for j in jobs
           if j.get("model") and any(b in str(j["model"]).lower() for b in BANNED)]
    return len(jobs) >= 31 and not bad, f"orchestration/jobs: {len(jobs)} джоб, бан-хиты: {bad if bad else 'нет'}"


@check
def live_cron_jobs_clean():
    jobs = json.loads((Path.home() / ".hermes" / "cron" / "jobs.json").read_text(encoding="utf-8"))["jobs"]
    bad = [j.get("name", "?") for j in jobs
           if j.get("model") and any(b in str(j["model"]).lower() for b in BANNED)]
    return not bad, f"live jobs: {len(jobs)} джоб, бан-хиты: {bad if bad else 'нет'}"


@check
def roster_gate_green():
    rc, out = run([sys.executable, str(SCRIPTS / "check_roster.py")], 120)
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return rc == 0, f"rc={rc} {tail}"


@check
def admission_gate_null_liar_tests():
    rc, out = run([sys.executable, str(ORC / "tests" / "test_admission_gate.py")], 120)
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return rc == 0, f"rc={rc} {tail}"


@check
def release_gate_green():
    rc, out = run([sys.executable, str(SCRIPTS / "release_gate.py")], 300)
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return rc == 0, f"rc={rc} {tail}"


@check
def condition_snapshot_fresh():
    rc, out = run([sys.executable, str(SCRIPTS / "condition_snapshot.py"), "check"], 60)
    return rc == 0, out.strip().splitlines()[0]


@check
def guard_action_selftest():
    rc, out = run([sys.executable, str(SCRIPTS / "guard_action.py"), "selftest"], 60)
    return rc == 0, out.strip().splitlines()[-1]


@check
def kg_schema_valid():
    rc, out = run([sys.executable, str(SCRIPTS / "kg_validate.py")], 60)
    return rc == 0, out.strip().splitlines()[-1]


@check
def l3_roles_registered():
    roster = json.loads((ORC / "roster.json").read_text(encoding="utf-8"))
    names = set(roster.get("roles", {}))
    need = {"LV-critic", "LV-proposer"}
    return need <= names, f"в ростере: {sorted(need & names) or 'НЕТ'} из {sorted(need)} (всего ролей: {len(names)})"


@check
def journal_provenance_info():
    rc, out = run([sys.executable, str(SCRIPTS / "journal_lint.py"), "--lines", "100"], 60)
    return True, "INFO " + (out.strip().splitlines()[0] if out.strip() else "")


def main() -> int:
    quick = "--quick" in sys.argv
    results = []
    for fn in CHECKS:
        if quick and fn.__name__ in ("release_gate_green", "condition_snapshot_fresh"):
            results.append((fn.__name__, True, "SKIP (--quick)"))
            continue
        try:
            ok, evidence = fn()
        except Exception as e:
            ok, evidence = False, f"{type(e).__name__}: {e}"
        results.append((fn.__name__, ok, evidence))
        print(f"  [{'✅' if ok else '⛔'}] {fn.__name__}: {evidence[:160]}")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\nLC-EVAL v1: {passed}/{len(results)} проверок зелёные")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
