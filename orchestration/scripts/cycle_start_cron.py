#!/usr/bin/env python3
"""Живой Код — старт цикла (пульс роя). Задача LV-cycle-start, каждые 4 часа.

Делает то, что заявлено в задаче: синхронизация git, проверки здоровья, проверка
промоушена, запись в хронику, брифинг. Ничего не решает за роли и НЕ трогает
расписание кронов (правило роя: планировщик ролям не подчиняется).

Печатает короткий брифинг в stdout — его доставляет кроновая доставка (telegram).
"""
from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

ROOT = Path("/home/thomas/LivingCode")
STATE = ROOT / "agents" / "cycle_state.json"
REPORTS = ROOT / "reports"
JOURNAL = ROOT / "agents" / "journal.md"
VAULT = Path("/home/thomas/Documents/ObsidianVault")
CHRONICLE = VAULT / "Evolution" / "chronicle.md"
LAYA = os.environ.get("LAYA_WARM_URL") or f"http://127.0.0.1:{os.environ.get('LAYA_PORT', '8731')}"


def sh(cmd: str, cwd: Path | None = None, timeout: int = 90) -> tuple[int, str]:
    try:
        r = subprocess.run(cmd, shell=True, capture_output=True, text=True,
                           timeout=timeout, cwd=str(cwd or ROOT))
        return r.returncode, (r.stdout or r.stderr or "").strip()
    except Exception as exc:                                     # noqa: BLE001
        return 1, f"{type(exc).__name__}: {exc}"


def bump_cycle() -> int:
    """Номер цикла — единственный источник правды для роя."""
    data = {}
    if STATE.exists():
        try:
            data = json.loads(STATE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = {}
    n = int(data.get("cycle") or 0) + 1
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps({"cycle": n, "started_at": datetime.now().isoformat(timespec="seconds")},
                                ensure_ascii=False, indent=2), encoding="utf-8")
    return n


def active_projects() -> list[str]:
    try:
        q = json.loads((ROOT / "QUEUE.json").read_text(encoding="utf-8"))
        return [str(p) for p in (q.get("active") or [])]
    except (OSError, ValueError):
        return [p.name for p in (ROOT / "Projects").iterdir() if p.is_dir()][:6] if (ROOT / "Projects").exists() else []


def git_sync() -> list[str]:
    """git pull --rebase по активным проектам. Ошибка сети не ломает цикл."""
    notes = []
    for name in active_projects():
        path = ROOT / "Projects" / name
        if not (path / ".git").exists():
            notes.append(f"{name}: не git")
            continue
        rc, out = sh("git pull --rebase --autostash", cwd=path, timeout=90)
        if rc == 0:
            behind = "актуально" if "up to date" in out or "актуально" in out else out.splitlines()[0][:60]
            notes.append(f"{name}: ✓ {behind}")
        else:
            notes.append(f"{name}: ⚠️ {out.splitlines()[0][:70] if out else 'ошибка'}")
    return notes


def health() -> dict:
    h = {}
    # Laya — ускоритель принятия решений
    try:
        with urllib.request.urlopen(f"{LAYA}/health", timeout=8) as r:
            d = json.loads(r.read().decode("utf-8"))
        h["laya"] = (f"✓ порт живой, модель {'в памяти' if d.get('loaded') else 'выгружена'}, "
                     f"RSS {d.get('rss_mb')} МБ, вызовов {d.get('calls')}")
    except (urllib.error.URLError, OSError, ValueError) as exc:
        h["laya"] = f"✗ сервис недоступен ({type(exc).__name__}) — роли уйдут в локальный путь"
    # память и диск
    try:
        mi = {}
        for line in Path("/proc/meminfo").read_text().splitlines():
            k, _, v = line.partition(":")
            mi[k] = int(v.split()[0]) // 1024
        h["mem"] = f"доступно {mi.get('MemAvailable', 0)} МБ из {mi.get('MemTotal', 0)} МБ"
    except OSError:
        h["mem"] = "н/д"
    try:
        du = shutil.disk_usage("/")
        h["disk"] = f"свободно {du.free / 1024**3:.0f} ГБ из {du.total / 1024**3:.0f} ГБ"
    except OSError:
        h["disk"] = "н/д"
    tmp_used = sh("df -h /tmp | tail -n1 | awk '{print $3\" из \"$2}'")[1]
    h["tmp"] = f"{tmp_used} (tmpfs — это RAM)"
    h["laya_docs"] = "orchestration/LAYA_WARM_SERVICE.md"
    return h


def promotion_check() -> list[str]:
    """Кандидаты на промоушен: у проекта есть отчёт Владыки (код признан горячим)."""
    verdict_re = re.compile(r"ВЕРДИКТ:\s*([\w-]+)\s*[—-]\s*(ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ)",
                            re.IGNORECASE)
    out = []
    lords = sorted(REPORTS.glob("lord*.md"))[-3:]
    for f in lords:
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        m = verdict_re.search(txt)
        if m:
            verdict = f"{m.group(2).lower()} ({m.group(1)})"
        else:
            # Фолбэк на старые отчёты; «hot/cold» по-английски вердиктом не считать
            low = txt.lower()
            if "холодн" in low:
                verdict = "холодный (старый формат)"
            elif "горяч" in low:
                verdict = "горячий (старый формат)"
            elif re.search(r"\bhot/cold\b|\bhot cold\b", low):
                verdict = "неясно (Владыка не записал строку ВЕРДИКТ)"
            else:
                verdict = "неясно"
        out.append(f"{f.name}: {verdict}")
    return out or ["отчётов Владыки нет"]


def chronicle_entry(cycle: int, health_d: dict, sync: list[str]) -> str:
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    line = (f"- **Цикл {cycle}** ({stamp}): git — {len([s for s in sync if '✓' in s])}/{len(sync)} ок; "
            f"Laya — {health_d.get('laya', '')}; RAM — {health_d.get('mem', '')}\n")
    try:
        CHRONICLE.parent.mkdir(parents=True, exist_ok=True)
        with CHRONICLE.open("a", encoding="utf-8") as fh:
            fh.write(line)
        return "записано"
    except OSError as exc:
        return f"не записано ({exc})"


def journal_ping(cycle: int) -> str:
    try:
        with JOURNAL.open("a", encoding="utf-8") as fh:
            fh.write(f"\n---\n**[{datetime.now():%Y-%m-%d %H:%M}] Старт цикла {cycle}** "
                     f"(LV-cycle-start). Ждём роли: Кодеры → Аудитор → Владыка → Продюсер.\n")
        return "заметка в журнале"
    except OSError as exc:
        return f"журнал недоступен ({exc})"


def main() -> int:
    t0 = time.time()
    cycle = bump_cycle()
    projects = active_projects()
    sync = git_sync()
    h = health()
    promo = promotion_check()
    chron = chronicle_entry(cycle, h, sync)
    jour = journal_ping(cycle)

    report = REPORTS / f"cycle-{cycle}-{datetime.now():%Y%m%d-%H%M}.md"
    body = [f"# Цикл {cycle} — старт", f"\n**Проекты в очереди:** {', '.join(projects) or '—'}",
            f"\n## Синхронизация git"] + [f"- {s}" for s in sync] + \
           ["\n## Здоровье"] + [f"- {k}: {v}" for k, v in h.items()] + \
           ["\n## Промоушен"] + [f"- {p}" for p in promo] + \
           [f"\n## Служебное", f"- хроника: {chron}", f"- {jour}"]
    try:
        REPORTS.mkdir(parents=True, exist_ok=True)
        report.write_text("\n".join(body) + "\n", encoding="utf-8")
    except OSError:
        pass

    print(f"🔁 Цикл {cycle} — старт ({time.time() - t0:.1f} с)")
    print(f"Проекты: {', '.join(projects) or '—'}")
    print("git: " + "; ".join(sync))
    for k, v in h.items():
        print(f"{k}: {v}")
    print("промоушен: " + "; ".join(promo))
    print(f"отчёт: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
