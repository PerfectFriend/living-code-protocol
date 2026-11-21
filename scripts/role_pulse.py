#!/usr/bin/env python3
"""role_pulse.py — deadman-пульс всех ролей протокола (Фаза 5 плана v3).

Тишина ≠ здоровье: для каждой enabled-роли считаем возраст последнего запуска
относительно ожидаемого интервала расписания:
  ЖИВ    — age <= 1.5 × interval
  БОЛЕН  — age <= 4 × interval
  МЁРТВ  — иначе (или никогда не запускалась при давнем создании)

Exit 1, если есть хоть одна МЁРТВ- роль среди enabled.
Вывод: таблица + строка итога; --json для машинной проверки.
"""
import datetime as dt
import json
import sqlite3
import sys
from pathlib import Path

JOBS = Path.home() / ".hermes" / "cron" / "jobs.json"
EXEC_DB = Path.home() / ".hermes" / "cron" / "executions.db"
ROLE_PREFIXES = ("LV", "Профессор", "Искатель", "Topic")


def interval_seconds(expr: str) -> int | None:
    """Грубый парсер cron-выражения '*/N * * * *' / 'M H * * *' / 'M H * * D'."""
    parts = expr.split()
    if len(parts) != 5:
        return None
    min_f, hour_f, dom, mon, dow = parts
    if min_f.startswith("*/") and hour_f == "*":
        return int(min_f[2:]) * 60
    if min_f == "*" and hour_f == "*":
        return 60
    if dom == "*" and mon == "*" and dow == "*":
        return 86400
    if dom == "*" and mon == "*":
        return 604800
    return 86400


def parse_ts(s) -> dt.datetime | None:
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s))
    except ValueError:
        return None


def last_exec_from_db(job_id: str) -> dt.datetime | None:
    """Последний запуск из executions.db.

    jobs.json.last_run_at обновляется не при каждом успешном прогоне,
    из-за чего частые роли (*/1 мин) получали ложный МЁРТВ. База exécutions —
    источник правды; jobs.json остаётся фолбэком.
    """
    if not job_id or not EXEC_DB.is_file():
        return None
    try:
        con = sqlite3.connect(f"file:{EXEC_DB}?mode=ro", uri=True)
        try:
            row = con.execute(
                "SELECT MAX(COALESCE(finished_at, started_at)) FROM executions "
                "WHERE job_id = ? AND status IN "
                "('completed','failed','error','unknown','interrupted')",
                (job_id,),
            ).fetchone()
        finally:
            con.close()
        return parse_ts(row[0]) if row and row[0] else None
    except (sqlite3.Error, OSError):
        return None


def main() -> int:
    as_json = "--json" in sys.argv
    jobs = json.loads(JOBS.read_text(encoding="utf-8"))["jobs"]
    now = dt.datetime.now().astimezone()
    rows = []
    for j in jobs:
        name = str(j.get("name", ""))
        if not name.startswith(ROLE_PREFIXES):
            continue
        enabled = bool(j.get("enabled"))
        expr = (j.get("schedule") or {}).get("expr", "")
        interval = interval_seconds(expr) or 86400
        last = max(
            (c for c in (parse_ts(j.get("last_run_at")), last_exec_from_db(str(j.get("id", "")))) if c),
            default=None,
        )
        created = parse_ts(j.get("created_at"))
        age = (now - last).total_seconds() if last else None
        if not enabled:
            status = "PAUSED"
        elif age is None:
            status = "МЁРТВ" if (created and (now - created).total_seconds() > 2 * interval) else "НОВ"
        elif age <= 1.5 * interval:
            status = "ЖИВ"
        elif age <= 4 * interval:
            status = "БОЛЕН"
        else:
            status = "МЁРТВ"
        rows.append({
            "name": name, "enabled": enabled, "schedule": expr,
            "interval_s": interval,
            "last_run": last.isoformat(timespec="seconds") if last else None,
            "age_h": round(age / 3600, 1) if age is not None else None,
            "status": status,
        })
    dead = [r for r in rows if r["status"] == "МЁРТВ"]
    if as_json:
        print(json.dumps({"roles": rows, "dead": [r["name"] for r in dead]}, ensure_ascii=False, indent=2))
    else:
        for r in sorted(rows, key=lambda x: (x["status"] != "МЁРТВ", x["name"])):
            last = r["last_run"][5:16] if r["last_run"] else "никогда"
            age = f"{r['age_h']}ч" if r["age_h"] is not None else "—"
            print(f"  {r['status']:<7} {r['name']:<28} sched={r['schedule']:<14} last={last} age={age}")
        print(f"\nПульс: {len(rows)} ролей, ЖИВ/БОЛЕН/PAUSED — ок, МЁРТВ: {len(dead)}"
              + (f" — {', '.join(r['name'] for r in dead)}" if dead else ""))
    return 1 if dead else 0


if __name__ == "__main__":
    sys.exit(main())
