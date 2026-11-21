#!/usr/bin/env python3
"""condition_snapshot.py — снимок условий протокола (stale-score rule, arXiv 2610.01073).

Каждая принятая метрика/оценка протокола должна хранить условия, при которых она
получена. При расхождении текущего состояния со снимком старые оценки считаются
протухшими (STALE) — это не «баг», это правило.

Команды:
  snapshot   — записать state/condition_snapshot.json
  check      — сравнить текущие условия со снимком; exit 1 при STALE
  show       — печать текущего снимка
"""
import datetime
import hashlib
import json
import sys
from pathlib import Path

LC = Path.home() / "LivingCode"
ORC = LC / "orchestration"
STATE = LC / "state"
SNAP = STATE / "condition_snapshot.json"

PROTOCOL_MODEL = "mistralai/mistral-large-4-1t-a52b"
PROTOCOL_PROVIDER = "nvidia"


def _sha(path) -> str | None:
    p = Path(path)
    try:
        return hashlib.sha256(p.read_bytes()).hexdigest()[:16]
    except OSError:
        return None


def _wrappers_sha() -> str:
    h = hashlib.sha256()
    d = ORC / "scripts" / "wrappers"
    for f in sorted(d.glob("*.sh")):
        h.update(f.name.encode())
        h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _live_jobs_stable_sha() -> str | None:
    """Хеш только семантически стабильных полей live-джоб (без таймстемпов next_run/last_dispatch —
    hermes перезаписывает их при каждом list/run, и снимок условий протухал бы сам по себе)."""
    p = Path.home() / ".hermes" / "cron" / "jobs.json"
    try:
        jobs = json.loads(p.read_text(encoding="utf-8"))["jobs"]
    except (OSError, ValueError, KeyError):
        return None
    stable = [
        {k: j.get(k) for k in ("id", "name", "model", "provider", "script", "enabled", "no_agent")}
        | {"schedule": (j.get("schedule") or {}).get("expr")}
        for j in jobs
    ]
    return hashlib.sha256(json.dumps(stable, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]


def collect() -> dict:
    return {
        "ts": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "model": PROTOCOL_MODEL,
        "provider": PROTOCOL_PROVIDER,
        "engine_sha": _sha(ORC / "scripts" / "living_code_agent_wrapper.py"),
        "check_roster_sha": _sha(ORC / "scripts" / "check_roster.py"),
        "roster_sha": _sha(ORC / "roster.json"),
        "jobs_sha": _sha(ORC / "jobs" / "jobs.json"),
        "live_jobs_sha": _live_jobs_stable_sha(),
        "hermes_config_sha": _sha(Path.home() / ".hermes" / "config.yaml"),
        "orch_config_sha": _sha(ORC / "hermes-config" / "config.yaml"),
        "wrappers_sha": _wrappers_sha(),
    }


def main() -> int:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "check"
    if cmd == "snapshot":
        STATE.mkdir(parents=True, exist_ok=True)
        snap = collect()
        SNAP.write_text(json.dumps(snap, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Снимок условий записан: {SNAP} (ts={snap['ts']})")
        return 0
    if cmd == "show":
        if SNAP.exists():
            print(SNAP.read_text(encoding="utf-8"))
        else:
            print("Снимка нет — выполни: condition_snapshot.py snapshot")
            return 1
        return 0
    if cmd == "check":
        if not SNAP.exists():
            print("STALE: снимка условий нет — выполни: condition_snapshot.py snapshot")
            return 1
        old = json.loads(SNAP.read_text(encoding="utf-8"))
        new = collect()
        stale = []
        for k, v in new.items():
            if k == "ts":
                continue
            if old.get(k) != v:
                stale.append((k, old.get(k), v))
        if stale:
            print(f"STALE: условия изменились со снимка {old.get('ts')}:")
            for k, o, n in stale:
                print(f"  {k}: {o} -> {n}")
            print("Старые оценки/scores по этим условиям считаются протухшими.")
            return 1
        print(f"OK: условия совпадают со снимком {old.get('ts')}")
        return 0
    print("Usage: condition_snapshot.py [snapshot|check|show]")
    return 2


if __name__ == "__main__":
    sys.exit(main())
