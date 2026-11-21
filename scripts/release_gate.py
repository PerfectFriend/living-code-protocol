#!/usr/bin/env python3
"""release_gate.py — L2 completion gate перед релизом/приёмкой правки протокола.

Детерминированные проверки (без LLM), все обязаны быть зелёными:
  1. py_compile всех scripts/*.py (кроме *.orig-*)
  2. bash -n всех scripts/wrappers/*.sh и scripts/*.sh
  3. check_roster.py rc=0 (ростер целый)
  4. guard_action.py selftest rc=0
  5. kg_validate.py rc=0 (граф знаний по схеме)
  6. journal_lint.py --lines 100 — INFO (не падает, считает нарушения провенанса)
  7. condition_snapshot.py check — WARN по умолчанию, FATAL с --strict-snapshot

Exit 0 = можно принимать; 1 = блок.
"""
import subprocess
import sys
from pathlib import Path

ORC = Path.home() / "LivingCode" / "orchestration"
SCRIPTS = ORC / "scripts"
WRAPPERS = SCRIPTS / "wrappers"


def run(cmd, timeout=180):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        return r.returncode, (r.stdout + r.stderr)
    except subprocess.TimeoutExpired:
        return 124, "timeout"


def check_py_compile() -> tuple[bool, str]:
    bad = []
    for f in sorted(SCRIPTS.glob("*.py")):
        if ".orig-" in f.name:
            continue
        rc, out = run([sys.executable, "-m", "py_compile", str(f)], timeout=60)
        if rc != 0:
            bad.append(f"{f.name}: {out.strip()[-300:]}")
    return not bad, ("; ".join(bad) if bad else f"py_compile OK ({len(list(SCRIPTS.glob('*.py')))} файлов, .orig исключены)")


def check_bash_n() -> tuple[bool, str]:
    bad = []
    files = sorted(WRAPPERS.glob("*.sh")) + sorted(SCRIPTS.glob("*.sh"))
    for f in files:
        rc, out = run(["bash", "-n", str(f)], timeout=30)
        if rc != 0:
            bad.append(f"{f.name}: {out.strip()[-200:]}")
    return not bad, ("; ".join(bad) if bad else f"bash -n OK ({len(files)} скриптов)")


def check_roster() -> tuple[bool, str]:
    rc, out = run([sys.executable, str(SCRIPTS / "check_roster.py")], timeout=60)
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return rc == 0, f"check_roster rc={rc} {tail}"


def check_guard() -> tuple[bool, str]:
    rc, out = run([sys.executable, str(SCRIPTS / "guard_action.py"), "selftest"], timeout=60)
    return rc == 0, f"guard selftest rc={rc} {out.strip().splitlines()[-1] if out.strip() else ''}"


def check_kg() -> tuple[bool, str]:
    rc, out = run([sys.executable, str(SCRIPTS / "kg_validate.py")], timeout=60)
    tail = out.strip().splitlines()[-1] if out.strip() else ""
    return rc == 0, f"kg_validate rc={rc} {tail}"


def check_journal_lint() -> tuple[bool, str]:
    rc, out = run([sys.executable, str(SCRIPTS / "journal_lint.py"), "--lines", "100"], timeout=60)
    first = out.strip().splitlines()[0] if out.strip() else ""
    return True, f"INFO journal_lint: {first}"  # не блокирует


def check_snapshot(strict: bool) -> tuple[bool, str]:
    rc, out = run([sys.executable, str(SCRIPTS / "condition_snapshot.py"), "check"], timeout=60)
    first = out.strip().splitlines()[0] if out.strip() else ""
    if strict:
        return rc == 0, f"{'FATAL' if rc else 'OK'} snapshot: {first}"
    return True, f"WARN snapshot: {first}"  # не блокирует без --strict-snapshot


def main() -> int:
    strict_snap = "--strict-snapshot" in sys.argv
    checks = [
        ("py_compile", check_py_compile),
        ("bash -n", check_bash_n),
        ("check_roster", check_roster),
        ("guard selftest", check_guard),
        ("kg_validate", check_kg),
        ("journal_lint", check_journal_lint),
        ("condition_snapshot", lambda: check_snapshot(strict_snap)),
    ]
    failed = 0
    for name, fn in checks:
        try:
            ok, msg = fn()
        except Exception as e:
            ok, msg = False, f"{type(e).__name__}: {e}"
        print(f"  [{'✅' if ok else '⛔'}] {name}: {msg}")
        if not ok:
            failed += 1
    print(f"RELEASE_GATE: {'PASS' if failed == 0 else 'FAIL'} ({len(checks) - failed}/{len(checks)})")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
