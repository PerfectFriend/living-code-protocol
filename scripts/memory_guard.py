#!/usr/bin/env python3
"""Memory guard: сторож памяти узла. Следит за tmpfs-памятью и мусором в /tmp.

Зачем: 27 сен 2026 система ушла в глобальный OOM и ядро убило Hermes. Разбор показал,
что «забита видеопамять» на самом деле означала: `/tmp` смонтирован как tmpfs (в RAM!),
и в нём лежал брошенный venv на 6.1 ГБ. VRAM при этом была свободна (1.2 ГБ).

Что делает (по возрастанию агрессивности):
  1. Наблюдает: MemAvailable, Shmem, занятость /tmp, PSI-давление, топ-RSS процессы.
  2. Чистит /tmp: удаляет чужие файлы старше TMP_MAX_AGE_H (по умолчанию 24 ч), кроме
     защищённых шаблонов; если /tmp занят больше TMP_MAX_GB — срезает самое старое.
  3. При нехватке памяти (MemAvailable < MIN_AVAIL_MB) — просит сервис Laya выгрузить
     модель (POST /unload, мгновенно освобождает ~1.6 ГБ), это дешевле, чем OOM-kill.
  4. Пишет кандидатов в мусор (осиротевшие процессы наших каталогов) в лог; убивает
     их только при KILL_ORPHANS=1 — по умолчанию только докладывает.

По умолчанию работает в режиме отчёта. Запись/удаление — только с --apply.
Запуск: python3 memory_guard.py --apply   (под systemd-таймером memory-guard.timer)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

HOME = Path.home()
LOG = Path(os.environ.get("GUARD_LOG", HOME / ".hermes" / "logs" / "memory_guard.log"))
TMP = Path(os.environ.get("GUARD_TMP", "/tmp"))

TMP_MAX_AGE_H = float(os.environ.get("TMP_MAX_AGE_H", "24"))       # возраст мусора
TMP_MAX_GB = float(os.environ.get("TMP_MAX_GB", "1.5"))            # порог занятости /tmp
MIN_AVAIL_MB = float(os.environ.get("MIN_AVAIL_MB", "1200"))       # тревога по RAM
WARN_TMP_MB = float(os.environ.get("WARN_TMP_MB", "512"))          # доклад о /tmp
LAYA_URL = os.environ.get("LAYA_WARM_URL") or f"http://127.0.0.1:{os.environ.get('LAYA_PORT', '8731')}"
KILL_ORPHANS = os.environ.get("KILL_ORPHANS", "0").lower() in ("1", "true", "yes")
ORPHAN_MIN_MB = float(os.environ.get("ORPHAN_MIN_MB", "200"))
ORPHAN_MIN_AGE_MIN = float(os.environ.get("ORPHAN_MIN_AGE_MIN", "120"))

# Ничего из этого не удаляем: чужие приватные каталоги и живые сокеты сессии
PROTECTED = (
    "systemd-private-*", "snap-private-tmp", ".X11-unix", ".ICE-unix", ".XIM-unix",
    ".font-unix", ".Test-unix", "tmp*.X11-unix", "pulse-*", "ssh-*", "systemd-*",
    ".hermes-*", "hermes-*",
)
# Каталоги, процессы из которых считаем нашими (кандидаты в сироты)
OUR_MARKERS = ("/home/thomas/LivingCode", "/home/thomas/.hermes", "/home/thomas/SuperGuard",
               "/home/thomas/Projects")


def log(msg: str, *, to_stderr: bool = False):
    stamp = datetime.now(timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{stamp} {msg}"
    try:
        LOG.parent.mkdir(parents=True, exist_ok=True)
        with LOG.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass
    if to_stderr:
        print(line, file=sys.stderr, flush=True)


def meminfo() -> dict:
    out = {}
    try:
        with open("/proc/meminfo") as fh:
            for line in fh:
                k, _, v = line.partition(":")
                out[k] = int(v.split()[0]) // 1024        # в МБ
    except OSError:
        pass
    return out


def psi() -> dict:
    res = {}
    for name in ("memory", "io", "cpu"):
        try:
            with open(f"/proc/pressure/{name}") as fh:
                for field in fh.read().split():
                    if field.startswith("avg60=") or field.startswith("total="):
                        key, _, val = field.partition("=")
                        res[f"{name}.{key}"] = val
        except OSError:
            pass
    return res


def tmp_usage() -> tuple[float, int]:
    """Занятость /tmp в МБ и число элементов верхнего уровня."""
    try:
        st = os.statvfs(TMP)
        used = (st.f_blocks - st.f_bfree) * st.f_frsize / 1048576
    except OSError:
        used = 0.0
    try:
        entries = len(os.listdir(TMP))
    except OSError:
        entries = 0
    return used, entries


def is_protected(name: str) -> bool:
    import fnmatch
    return any(fnmatch.fnmatch(name, pat) for pat in PROTECTED)


def entry_size(path: Path) -> float:
    """Размер записи в МБ (без падения на правах и битых ссылках)."""
    try:
        if path.is_symlink():
            return 0.0
        if path.is_file():
            return path.stat().st_size / 1048576
        total = 0
        for root, dirs, files in os.walk(path, onerror=lambda _e: None):
            for f in files:
                try:
                    total += os.path.getsize(os.path.join(root, f))
                except OSError:
                    pass
            if total > 8 * 1024**3:
                break
        return total / 1048576
    except OSError:
        return 0.0


def sweep_tmp(apply: bool) -> dict:
    """Убирает из /tmp чужой мусор: по возрасту, затем по порогу занятости."""
    now = time.time()
    freed_mb = 0.0
    removed: list[str] = []
    candidates = []
    try:
        names = sorted(os.listdir(TMP))
    except OSError as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}

    for name in names:
        if is_protected(name):
            continue
        path = TMP / name
        try:
            age_h = (now - path.stat().st_mtime) / 3600
        except OSError:
            continue
        size_mb = entry_size(path)
        candidates.append((age_h, size_mb, path))

    used_mb, _ = tmp_usage()
    # 1) всё, что старше TMP_MAX_AGE_H
    for age_h, size_mb, path in sorted(candidates, key=lambda c: -c[0]):
        if age_h >= TMP_MAX_AGE_H:
            if apply:
                _remove(path)
            removed.append(f"{path.name} ({size_mb:.0f} МБ, {age_h:.0f} ч)")
            freed_mb += size_mb
    # 2) если всё ещё перебор — срезаем самое старое (но не свежее часа)
    left = [(a, s, p) for a, s, p in candidates if p.name not in {r.split(" ")[0] for r in removed}]
    projected = used_mb - freed_mb
    for age_h, size_mb, path in sorted(left, key=lambda c: -c[0]):
        if projected <= TMP_MAX_GB * 1024:
            break
        if age_h < 1.0:
            continue
        if apply:
            _remove(path)
        removed.append(f"{path.name} ({size_mb:.0f} МБ, {age_h:.0f} ч, по порогу)")
        freed_mb += size_mb
        projected -= size_mb
    return {"removed": removed, "freed_mb": round(freed_mb, 1),
            "tmp_used_mb": round(used_mb, 1)}


def _remove(path: Path):
    try:
        if path.is_dir() and not path.is_symlink():
            shutil.rmtree(path, ignore_errors=True)
        else:
            path.unlink(missing_ok=True)
    except OSError as exc:
        log(f"[tmp] не удалось удалить {path}: {exc}")


def find_orphans() -> list[dict]:
    """Процессы наших каталогов, осиротевшие (PPID=1), крупные и немолодые."""
    try:
        out = subprocess.run(["ps", "-eo", "pid,ppid,etimes,rss,pcpu,args", "--no-headers"],
                             capture_output=True, text=True, check=True).stdout
    except (OSError, subprocess.CalledProcessError):
        return []
    found = []
    for line in out.splitlines():
        m = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\S+)\s+(.*)", line)
        if not m:
            continue
        pid, ppid, et, rss, pcpu, args = m.groups()
        rss_mb = int(rss) / 1024
        if int(ppid) != 1 or rss_mb < ORPHAN_MIN_MB or int(et) / 60 < ORPHAN_MIN_AGE_MIN:
            continue
        if not any(marker in args for marker in OUR_MARKERS):
            continue
        if float(pcpu) > 5.0:                       # живой и работающий — не трогаем
            continue
        found.append({"pid": int(pid), "rss_mb": round(rss_mb), "age_min": int(et) // 60,
                      "args": args[:120]})
    return found


def kill_orphans(procs: list[dict]) -> list[int]:
    killed = []
    for p in procs:
        try:
            os.kill(p["pid"], 15)
            killed.append(p["pid"])
        except OSError as exc:
            log(f"[orphans] не смог убить {p['pid']}: {exc}")
    return killed


def laya_unload() -> dict:
    """Просит Laya отпустить модель: 1.6 ГБ освобождаются мгновенно и без потерь."""
    req = urllib.request.Request(f"{LAYA_URL}/unload", data=b"{}", method="POST",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}"}


def main() -> int:
    ap = argparse.ArgumentParser(description="Сторож памяти: tmpfs-мусор, сироты, давление на RAM")
    ap.add_argument("--apply", action="store_true", help="действовать (по умолчанию только отчёт)")
    ap.add_argument("--json", action="store_true", help="распечатать отчёт одним JSON")
    args = ap.parse_args()

    mi, pr = meminfo(), psi()
    used_mb, entries = tmp_usage()
    avail_mb = mi.get("MemAvailable", 0)
    shmem_mb = mi.get("Shmem", 0)

    report = {
        "mem_available_mb": avail_mb,
        "shmem_mb": shmem_mb,
        "tmp_used_mb": round(used_mb, 1),
        "tmp_entries": entries,
        "psi": pr,
        "applied": args.apply,
        "thresholds": {"min_avail_mb": MIN_AVAIL_MB, "tmp_max_gb": TMP_MAX_GB,
                       "tmp_max_age_h": TMP_MAX_AGE_H, "warn_tmp_mb": WARN_TMP_MB},
    }

    # 1) /tmp: мусор по возрасту и по порогу занятости
    if used_mb > WARN_TMP_MB:
        sweep = sweep_tmp(args.apply)
        report["tmp_sweep"] = sweep
        if sweep.get("removed"):
            log(f"[tmp] {'удалено' if args.apply else 'к удалению'}: {len(sweep['removed'])} записей, "
                f"{sweep.get('freed_mb', 0)} МБ; занято было {sweep.get('tmp_used_mb')} МБ")
            if args.apply and avail_mb < MIN_AVAIL_MB:
                report["mem_available_mb"] = meminfo().get("MemAvailable", avail_mb)

    # 2) Память на пределе — сначала отпускаем модель Laya (дешевле, чем OOM-kill)
    if avail_mb < MIN_AVAIL_MB:
        log(f"[ram] ВНИМАНИЕ: доступно {avail_mb} МБ < {MIN_AVAIL_MB} МБ "
            f"(shmem {shmem_mb} МБ, /tmp {used_mb:.0f} МБ)")
        if args.apply:
            un = laya_unload()
            report["laya_unload"] = un
            log(f"[ram] Laya unload: {un}")
            time.sleep(2)
            report["mem_available_after_mb"] = meminfo().get("MemAvailable", 0)

    # 3) Осиротевшие процессы наших каталогов
    orphans = find_orphans()
    report["orphans"] = orphans
    if orphans:
        log(f"[orphans] кандидатов {len(orphans)}: "
            + "; ".join(f"pid {p['pid']} {p['rss_mb']}МБ {p['age_min']}мин" for p in orphans))
        if args.apply and KILL_ORPHANS:
            report["orphans_killed"] = kill_orphans(orphans)
            log(f"[orphans] убиты: {report['orphans_killed']}")

    summary = (f"итог: доступно {report.get('mem_available_after_mb', avail_mb)} МБ, "
               f"/tmp {used_mb:.0f} МБ/{entries} записей, shmem {shmem_mb} МБ, "
               f"psi.memory.avg60={pr.get('memory.avg60', '?')}")
    log(summary, to_stderr=True)
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

