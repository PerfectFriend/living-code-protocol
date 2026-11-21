#!/usr/bin/env python3
"""Конвейер Живого Кода — схема владельца (21.11.2026).

Смысл (дословно по постановке владельца):
  * `Projects/`        — ОЧЕРЕДЬ проектов. Отсюда берётся следующий проект.
  * `CompleteProjects/`— выпущенные проекты: 100% холодный код + финальная
                         сопроводительная документация.
  * `Project1..Project4`— РАБОЧИЕ папки текущей разработки (4 слота).

Правила:
  1. Проект считается готовым к релизу, когда он ОБЪЯВЛЕН В РЕЛИЗ:
     * completion_pct == 100 (STATE.json, чекбоксы PLAN.md),
     * 100% холодный код (все исходники помечены '# COLD' или старше 48ч),
     * вердикт Владыки «ГОРЯЧИЙ» (reports/lord*.md: "ВЕРДИКТ: <проект> — ГОРЯЧИЙ").
     Нет данных = нет релиза (VERIFICATION CONTRACT).
  2. Готовый рабочий проект переносится в CompleteProjects/<проект>_<timestamp>
     вместе с финальной сопроводительной документацией.
  3. Если проект был взят из очереди — его копия удаляется из Projects/,
     чтобы та же работа не повторилась.
  4. Освободившаяся рабочая папка заполняется следующим проектом из очереди:
     берётся САМЫЙ БОЛЬШОЙ по количеству кода и документации и копируется
     в рабочую папку.
  5. Очередь пополняется из QUEUE.json (catalog), когда в Projects/ не хватает
     проектов для свободных слотов.

Команды:
  conveyor.py scan              — таблица: очередь, слоты, готовность, размеры
  conveyor.py claim Project1 superguard — явно указать, какой проект в слоте
  conveyor.py run [--apply]     — прогон конвейера (по умолчанию dry-run)
  conveyor.py status            — краткий итог по манифесту

Тест:  test_conveyor.py (энд-to-end на временном дереве).
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
from datetime import datetime
from pathlib import Path

ROOT = Path(os.environ.get("LIVING_CODE_ROOT", "/home/thomas/LivingCode"))
QUEUE_DIR = ROOT / "Projects"
COMPLETE_DIR = ROOT / "CompleteProjects"
SLOT_NAMES = ["Project1", "Project2", "Project3", "Project4"]
MANIFEST = ROOT / "CONVEYOR.json"
QUEUE_JSON = ROOT / "QUEUE.json"
JOURNAL = ROOT / "agents" / "journal.md"
REPORTS = ROOT / "reports"

COLD_MARK = "# COLD"
HOT_MARK = "# HOT"
HOT_WINDOW = 48 * 3600  # файл считается горячим, если менялся за 48ч

CODE_EXT = {".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".kt", ".dart",
            ".c", ".h", ".cpp", ".hpp", ".cs", ".rb", ".php", ".swift", ".sh", ".sql"}
DOC_EXT = {".md", ".rst", ".txt", ".adoc", ".org"}
SKIP_DIRS = {".git", "node_modules", "build", ".dart_tool", "dist", "target", "vendor",
             "__pycache__", ".venv", "venv", ".gradle", ".idea", ".pytest_cache", "Pods"}
MAX_FILES_SCAN = 30000
MAX_COPY_BYTES = 4 * 1024**3          # не копируем в слот гигант > 4 ГБ
MIN_FREE_BYTES = 8 * 1024**3          # нужен запас на диске


# ---------------------------------------------------------------- манифест
def load_manifest() -> dict:
    if MANIFEST.exists():
        try:
            data = json.loads(MANIFEST.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                data.setdefault("slots", {})
                data.setdefault("released", [])
                return data
        except (OSError, ValueError):
            pass
    return {"slots": {}, "released": []}


def save_manifest(m: dict) -> None:
    MANIFEST.write_text(json.dumps(m, ensure_ascii=False, indent=2), encoding="utf-8")


# ---------------------------------------------------------------- метрики
def measure(path: Path) -> dict:
    """Количество кода и документации (строки) + размер на диске."""
    code_loc = doc_loc = 0
    files = 0
    total_bytes = 0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            ext = Path(name).suffix.lower()
            if ext not in CODE_EXT and ext not in DOC_EXT:
                continue
            fp = Path(dirpath) / name
            try:
                st = fp.stat()
            except OSError:
                continue
            total_bytes += st.st_size
            files += 1
            if files > MAX_FILES_SCAN:
                break
            if st.st_size > 2 * 1024 * 1024:
                continue
            try:
                with fp.open("r", encoding="utf-8", errors="replace") as fh:
                    n = sum(1 for _ in fh)
            except OSError:
                continue
            if ext in CODE_EXT:
                code_loc += n
            else:
                doc_loc += n
        if files > MAX_FILES_SCAN:
            break
    return {"code_loc": code_loc, "doc_loc": doc_loc, "files": files,
            "bytes": total_bytes,
            "score": code_loc + doc_loc}


def queue_items(m: dict) -> list[Path]:
    """Проекты в очереди Projects/, кроме уже выпущенных."""
    done = {r.get("project") for r in m.get("released", []) if isinstance(r, dict)}
    if not QUEUE_DIR.exists():
        return []
    out = []
    for p in sorted(QUEUE_DIR.iterdir()):
        if not p.is_dir() or p.name in done:
            continue
        out.append(p)
    return out


def cold_status(path: Path) -> dict:
    """Сколько кода горячего/холодного (маркер или mtime)."""
    hot = cold = 0
    for dirpath, dirnames, filenames in os.walk(path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for name in filenames:
            if Path(name).suffix.lower() not in CODE_EXT:
                continue
            fp = Path(dirpath) / name
            try:
                st = fp.stat()
            except OSError:
                continue
            marker = None
            try:
                with fp.open("r", encoding="utf-8", errors="replace") as fh:
                    first = fh.readline().strip()
                if first in (HOT_MARK, COLD_MARK):
                    marker = first
            except OSError:
                pass
            if marker == HOT_MARK or (marker is None and (time.time() - st.st_mtime) < HOT_WINDOW):
                hot += 1
            else:
                cold += 1
    return {"hot": hot, "cold": cold,
            "pct_cold": 100 if hot == 0 else round(cold * 100 / max(1, hot + cold), 1)}


def state_of(path: Path) -> dict:
    sf = path / "STATE.json"
    if not sf.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from generate_state import generate
            return generate(path)
        except Exception:
            return {}
    try:
        data = json.loads(sf.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def lord_verdict(project: str, also: str | None = None) -> tuple[bool, str]:
    """Вердикт Владыки по проекту из отчётов.

    Ищем по имени проекта; если отчёт называет слот (например «мой-проект»),
    подходит и совпадение по имени слота — иначе вердикт теряется.
    """
    if not REPORTS.exists():
        return False, "нет отчётов Владыки"
    names = {project.lower()}
    if also:
        names.add(also.lower())
    found = None
    for f in sorted(REPORTS.glob("lord*.md")):
        try:
            txt = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if not any(n in txt.lower() for n in names):
            continue
        m = re.search(r"ВЕРДИКТ:\s*([\w.-]+)\s*[—-]\s*(ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ)", txt, re.I)
        if m:
            found = (m.group(2).upper(), f.name)
    if not found:
        return False, "вердикт Владыки не найден"
    return found[0] == "ГОРЯЧИЙ", f"{found[0]} ({found[1]})"


def resolve_project(slot_name: str, slot_path: Path, m: dict) -> str:
    """Имя проекта, который сейчас разрабатывается в слоте.

    Порядок: маркер .queue_source → манифест → STATE.json["project"] → имя слота.
    """
    marker = slot_path / ".queue_source"
    if marker.exists():
        try:
            data = json.loads(marker.read_text(encoding="utf-8"))
            if isinstance(data, dict) and data.get("project"):
                return str(data["project"])
        except (OSError, ValueError):
            pass
    slot_meta = (m.get("slots") or {}).get(slot_name) or {}
    if isinstance(slot_meta, dict) and slot_meta.get("project"):
        return str(slot_meta["project"])
    st = state_of(slot_path)
    if st.get("project"):
        return str(st["project"])
    return slot_name


def slot_ready(slot: Path, project: str) -> tuple[bool, list[str]]:
    """Готов ли рабочий слот к релизу. Возвращает (готов, причины-блокеры)."""
    blockers = []
    st = state_of(slot)
    pct = st.get("completion_pct")
    if not isinstance(pct, (int, float)) or pct < 100:
        blockers.append(f"completion={pct} (<100)")
    cs = cold_status(slot)
    if cs["hot"] > 0:
        blockers.append(f"горячий код: {cs['hot']} файлов (нужен 100% холодный)")
    ok, vnote = lord_verdict(project, also=slot.name)
    if not ok:
        blockers.append(f"Владыка: {vnote}")
    return (not blockers), blockers


# ---------------------------------------------------------------- действия
def free_bytes(path: Path) -> int:
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize


def pick_next(m: dict, skip: set[str]) -> Path | None:
    """Следующий проект из очереди: самый большой по коду и документации."""
    best = None
    best_m = None
    for item in queue_items(m):
        if item.name in skip:
            continue
        metrics = measure(item)
        if best_m is None or metrics["score"] > best_m["score"]:
            best, best_m = item, metrics
    return best


def refill_queue(m: dict, wanted: int) -> list[str]:
    """Пополнить очередь Projects/ из каталога QUEUE.json (по priority)."""
    added = []
    try:
        data = json.loads(QUEUE_JSON.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return added
    catalog = sorted(data.get("queue") or [],
                     key=lambda x: (x.get("priority", 99), x.get("added_at", "")))
    existing = {p.name for p in queue_items(m)}
    for item in catalog:
        if len(queue_items(m)) + len(added) >= wanted:
            break
        name = item.get("name")
        src = Path(item.get("source") or "")
        if not name or name in existing or not src.exists():
            continue
        try:
            QUEUE_DIR.mkdir(parents=True, exist_ok=True)
            subprocess.run(["cp", "-a", "--reflink=auto", str(src), str(QUEUE_DIR / name)],
                           check=True, timeout=1800,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            added.append(name)
        except (subprocess.SubprocessError, OSError):
            continue
    return added


def write_final_docs(target: Path, slot_name: str, project: str, manifest: dict,
                     metrics: dict, cold: dict, verdict: str, state: dict) -> Path:
    """Финальная сопроводительная документация релиза."""
    def sh(*args, cwd=None):
        try:
            return subprocess.run(args, cwd=cwd, capture_output=True, text=True,
                                  timeout=60).stdout.strip()
        except (subprocess.SubprocessError, OSError):
            return ""

    readme = ""
    for cand in ("README.md", "docs/README.md", "Описание.md"):
        fp = target / cand
        if fp.exists():
            readme = fp.read_text(encoding="utf-8", errors="replace")[:4000]
            break
    commits = sh("git", "log", "--oneline", cwd=target) or ""
    n_commits = len(commits.splitlines()) if commits else 0
    span = sh("git", "log", "--format=%ad", "--date=format:%d.%m.%Y", cwd=target) or ""
    dates = [x for x in span.splitlines() if x]
    tree = sh("find", ".", "-maxdepth", "2", "-type", "d", "-not", "-path", "*/.git*", cwd=target)
    tests = [f.name for f in (target / "tests").glob("**/*.py")] if (target / "tests").exists() else []
    doc = f"""# Финальное досье проекта «{project}»

**Дата выпуска:** {datetime.now():%Y-%m-%d %H:%M}
**Из рабочего слота:** {slot_name}
**Состояние кода:** 100% холодный ({cold['cold']} файлов, горячих: {cold['hot']})
**Вердикт Владыки:** {verdict}
**Готовность (STATE.json):** completion_pct={state.get('completion_pct')}, hot_files={state.get('hot_files')}

## Состав релиза
| Метрика | Значение |
|---------|----------|
| Файлов (код+документация) | {metrics['files']} |
| Строк кода | {metrics['code_loc']} |
| Строк документации | {metrics['doc_loc']} |
| Объём | {round(metrics['bytes']/1024/1024, 1)} МБ |
| Коммитов в проекте | {n_commits} |
| Период разработки | {(dates[-1] + ' — ' + dates[0]) if dates else 'н/д'} |

## Структура (верхний уровень)
```
{tree[:1500] if tree else 'н/д'}
```

## Тесты
{f'Файлов тестов: {len(tests)}' if tests else 'Отдельного каталога tests/ нет — см. TEST_RUNNER/README проекта.'}

## Документация проекта
{readme[:2500] if readme else 'README отсутствует — основная документация в docs/ и CHRONICLE.md.'}

## Как это попало в релиз
1. Кодер довёл план до 100% (чекбоксы PLAN.md).
2. Все исходники промаркированы `# COLD` — код заморожен и не меняется.
3. Владыка Кода прогнал гейты и вынес вердикт: {verdict}.
4. Конвейер перенёс рабочую папку в CompleteProjects и удалил проект из очереди
   `Projects/`, чтобы та же работа не повторилась.
5. Освободившийся слот {slot_name} получил следующий проект из очереди.

---
Сгенерировано автоматически: conveyor.py, {datetime.now():%Y-%m-%d %H:%M}
"""
    out = target / "ФИНАЛЬНОЕ_ДОСЬЕ.md"
    out.write_text(doc, encoding="utf-8")
    return out


def finalize(slot_name: str, project: str, m: dict, apply: bool) -> str:
    """Релиз рабочего проекта + заполнение освободившегося слота."""
    slot = ROOT / slot_name
    COMPLETE_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    target = COMPLETE_DIR / f"{project}_{stamp}"

    metrics = measure(slot)
    cold = cold_status(slot)
    state = state_of(slot)
    ok, vnote = lord_verdict(project)

    if not apply:
        return (f"[DRY-RUN] {slot_name} → CompleteProjects/{target.name}; "
                f"очередь Projects/{project} удалить; слот заполнить следующим")

    # 1) перенос рабочей папки в CompleteProjects
    shutil.move(str(slot), str(target))

    # 2) финальная сопроводительная документация
    write_final_docs(target, slot_name, project, m, metrics, cold, vnote, state)

    # 3) проект выпущен — убираем его из очереди, чтобы не повторить работу
    queued = QUEUE_DIR / project
    removed_queue = False
    if queued.exists() and queued.is_dir():
        shutil.rmtree(queued, ignore_errors=True)
        removed_queue = True

    # 4) манифест: слот освобождён, проект выпущен
    m.setdefault("released", []).append({
        "project": project, "slot": slot_name, "released_at": stamp,
        "complete_dir": target.name, "code_loc": metrics["code_loc"],
        "doc_loc": metrics["doc_loc"], "removed_from_queue": removed_queue,
    })
    m.setdefault("slots", {})[slot_name] = {"project": None, "source": None,
                                            "freed_at": stamp}

    # 5) заполняем слот следующим проектом из очереди — самый большой
    filled = fill_slot(slot_name, m, apply=True)

    save_manifest(m)

    # 6) журнал
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with JOURNAL.open("a", encoding="utf-8") as fh:
        fh.write(f"\n---\n**[{datetime.now():%Y-%m-%d %H:%M}] [PROMOTION EVENT]** "
                 f"выпущен: {project} (слот {slot_name}) → CompleteProjects/{target.name}; "
                 f"из очереди удалён: {'да' if removed_queue else 'нет'}; "
                 f"в слот взят: {filled or 'очередь пуста'}\n")
    return (f"{slot_name}: {project} → CompleteProjects/{target.name}; "
            f"очередь очищена: {'да' if removed_queue else 'нет'}; "
            f"слот заполнен: {filled or '—'}")


def fill_slot(slot_name: str, m: dict, apply: bool) -> str | None:
    """Взять следующий проект из очереди и скопировать в рабочую папку."""
    skip = {s.get("project") for s in (m.get("slots") or {}).values()
            if isinstance(s, dict) and isinstance(s.get("project"), str)}
    nxt = pick_next(m, skip)
    if nxt is None:
        refill_queue(m, wanted=len(SLOT_NAMES))
        nxt = pick_next(m, skip)
    if nxt is None:
        return None

    metrics = measure(nxt)
    if metrics["bytes"] > MAX_COPY_BYTES:
        print(f"⚠️ {nxt.name}: {round(metrics['bytes']/1024**3,2)} ГБ > лимита — пропускаю")
        return None
    if free_bytes(ROOT) < MIN_FREE_BYTES:
        print("⚠️ мало свободного места на диске — копирование отменено")
        return None

    if not apply:
        return f"{nxt.name} (dry-run, {metrics['code_loc']} строк кода)"

    slot = ROOT / slot_name
    if slot.exists():
        shutil.rmtree(slot, ignore_errors=True)
    slot.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-a", "--reflink=auto", str(nxt) + "/.", str(slot)],
                   check=False, timeout=3600)
    (slot / ".queue_source").write_text(
        json.dumps({"project": nxt.name, "claimed_at": datetime.now().isoformat(timespec="seconds"),
                    "metrics": metrics}, ensure_ascii=False, indent=2), encoding="utf-8")
    st = slot / "STATE.json"
    if not st.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from generate_state import generate
            generate(slot)
        except Exception:
            st.write_text(json.dumps({"project": nxt.name, "completion_pct": 0,
                                      "hot_files": 0, "ready_for_publish": False},
                                     ensure_ascii=False, indent=2), encoding="utf-8")
    m.setdefault("slots", {})[slot_name] = {"project": nxt.name, "source": "queue",
                                            "claimed_at": datetime.now().isoformat(timespec="seconds")}
    return nxt.name


# ---------------------------------------------------------------- команды
def cmd_scan() -> int:
    m = load_manifest()
    print("=== ОЧЕРЕДЬ (Projects/) ===")
    items = queue_items(m)
    rows = []
    for p in items:
        met = measure(p)
        rows.append((met["score"], p.name, met))
    for score, name, met in sorted(rows, reverse=True):
        print(f"  {name:36s} код={met['code_loc']:8d} док={met['doc_loc']:7d} "
              f"файлов={met['files']:6d} {round(met['bytes']/1024/1024,1):8.1f} МБ")
    print(f"  всего в очереди: {len(items)}")
    print("\n=== РАБОЧИЕ СЛОТЫ (Project1..4) ===")
    for s in SLOT_NAMES:
        sp = ROOT / s
        if not sp.exists():
            print(f"  {s}: ОТСУТСТВУЕТ")
            continue
        slot_meta = (m.get("slots") or {}).get(s) or {}
        marker = sp / ".queue_source"
        if marker.exists():
            try:
                slot_meta = {**slot_meta, **json.loads(marker.read_text(encoding='utf-8'))}
            except (OSError, ValueError):
                pass
        project = resolve_project(s, sp, m)
        st = state_of(sp)
        cs = cold_status(sp)
        ready, blockers = slot_ready(sp, project)
        print(f"  {s}: проект={project} completion={st.get('completion_pct')} "
              f"холодный={cs['pct_cold']}% готов={'ДА' if ready else 'нет'}")
        for b in blockers:
            print(f"      блокер: {b}")
    print("\n=== ВЫПУЩЕНО ===")
    for r in m.get("released", []):
        print(f"  {r.get('released_at')} {r.get('project')} → {r.get('complete_dir')}")
    return 0


def cmd_claim(slot_name: str, project: str, apply: bool = False) -> int:
    """Вручную назначить проект слоту и (с --apply) скопировать его в папку."""
    m = load_manifest()
    src = QUEUE_DIR / project
    if not src.exists():
        print(f"в очереди Projects/ нет проекта «{project}»")
        return 2
    met = measure(src)
    if not apply:
        print(f"[DRY-RUN] {slot_name} ← {project} "
              f"(код={met['code_loc']}, док={met['doc_loc']}, {round(met['bytes']/1024/1024,1)} МБ)")
        return 0
    # освобождаем слот и копируем туда выбранный проект из очереди
    slot = ROOT / slot_name
    if slot.exists():
        shutil.rmtree(slot, ignore_errors=True)
    slot.mkdir(parents=True, exist_ok=True)
    subprocess.run(["cp", "-a", "--reflink=auto", str(src) + "/.", str(slot)],
                   check=False, timeout=3600)
    (slot / ".queue_source").write_text(
        json.dumps({"project": project, "claimed_at": datetime.now().isoformat(timespec="seconds"),
                    "metrics": met}, ensure_ascii=False, indent=2), encoding="utf-8")
    st = slot / "STATE.json"
    if not st.exists():
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        try:
            from generate_state import generate
            generate(slot)
        except Exception:
            st.write_text(json.dumps({"project": project, "completion_pct": 0,
                                      "hot_files": 0}, ensure_ascii=False, indent=2),
                          encoding="utf-8")
    m.setdefault("slots", {})[slot_name] = {"project": project, "source": "queue",
                                            "claimed_at": datetime.now().isoformat(timespec="seconds")}
    save_manifest(m)
    print(f"{slot_name} ← {project} (скопировано из Projects/, маркер .queue_source записан)")
    return 0


def cmd_run(apply: bool) -> int:
    m = load_manifest()
    done = []
    for s in SLOT_NAMES:
        sp = ROOT / s
        if not sp.exists():
            continue
        slot_meta = (m.get("slots") or {}).get(s) or {}
        marker = sp / ".queue_source"
        if marker.exists():
            try:
                slot_meta = {**slot_meta, **json.loads(marker.read_text(encoding='utf-8'))}
            except (OSError, ValueError):
                pass
        project = resolve_project(s, sp, m)
        ready, blockers = slot_ready(sp, project)
        if not ready:
            print(f"⏭ {s} ({project}): не готов — {'; '.join(blockers)}")
            continue
        print(f"🚀 {s} ({project}) → релиз")
        print("   ", finalize(s, project, m, apply))
        done.append(s)
    if not done:
        print("Релизов нет: ни один рабочий слот не объявлен готовым (100% холодный код + вердикт ГОРЯЧИЙ).")
    return 0


def cmd_status() -> int:
    m = load_manifest()
    print(json.dumps({"slots": m.get("slots"), "released_count": len(m.get("released", [])),
                      "queue": [p.name for p in queue_items(m)]},
                     ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="Конвейер Живого Кода")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("scan")
    sub.add_parser("status")
    p_run = sub.add_parser("run")
    p_run.add_argument("--apply", action="store_true")
    p_claim = sub.add_parser("claim")
    p_claim.add_argument("slot")
    p_claim.add_argument("project")
    p_claim.add_argument("--apply", action="store_true")
    args = ap.parse_args()
    if args.cmd == "scan":
        return cmd_scan()
    if args.cmd == "status":
        return cmd_status()
    if args.cmd == "claim":
        return cmd_claim(args.slot, args.project, args.apply)
    if args.cmd == "run":
        return cmd_run(args.apply)
    ap.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
