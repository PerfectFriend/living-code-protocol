#!/home/thomas/LivingCode/venvs/laya/bin/python
"""agency_router — второй внешний модуль Протокола Живого Кода (Фаза 4 плана The Agency).

По образцу integrations/hermes из The Agency: малый фиксированный вход → полный
каталог 259 промпт-паспортов из ~/LivingCode/knowledge-base/agency-agents/ →
ленивая загрузка (паспорт читается с диска только по request).

Запускается питоном venv laya (не процессом Hermes): большие тела паспортов
никогда не входят в контекст агента. На выход — компактный JSON в stdout.

Режимы:
  search   query [--division DIV] [--limit N]  — найти специалистов (по описанию/имени)
  inspect  slug                                 — метаданные паспорта (без тела)
  load     slug [--task TASK]                   — готовый промпт-паспорт под задачу
  list                                          — дивизионы со счётчиками

Примеры:
  agency_router.py search "code review"
  agency_router.py search "dashboard" --division design --limit 5
  agency_router.py inspect design-ui-finish-gate-reviewer
  agency_router.py load design-ui-finish-gate-reviewer --task "Проверь экран настроек"
"""
import argparse
import json
import os
import re
import sys

AGENCY_ROOT = os.environ.get(
    "AGENCY_ROOT",
    os.path.expanduser("~/LivingCode/knowledge-base/agency-agents"),
)


def _frontmatter(text: str) -> dict:
    m = re.match(r"^---\n(.*?)\n---\n", text, re.DOTALL)
    fm = {}
    if not m:
        return fm
    for line in m.group(1).splitlines():
        if ":" in line:
            k, _, v = line.partition(":")
            fm[k.strip()] = v.strip().strip("'\"")
    return fm


def _scan() -> list:
    """Единый проход по каталогу: паспорт → {slug, name, description, division, path}."""
    out = []
    if not os.path.isdir(AGENCY_ROOT):
        return out
    for root, _dirs, files in os.walk(AGENCY_ROOT):
        for f in files:
            if not f.endswith(".md") or f in ("README.md", "CONTRIBUTING.md", "SECURITY.md"):
                continue
            p = os.path.join(root, f)
            try:
                with open(p, "r", encoding="utf-8", errors="replace") as fh:
                    text = fh.read(4096)  # frontmatter в первых байтах
            except OSError:
                continue
            fm = _frontmatter(text)
            if not fm.get("name"):
                continue
            division = os.path.relpath(root, AGENCY_ROOT).split(os.sep)[0]
            out.append({
                "slug": f.removesuffix(".md"),
                "name": fm.get("name", ""),
                "description": fm.get("description", ""),
                "division": division,
                "path": p,
            })
    return out


def cmd_search(args) -> dict:
    agents = _scan()
    q = (args.query or "").lower().strip()
    terms = re.findall(r"\w+", q)
    div = (args.division or "").lower().strip()

    def score(a) -> int:
        hay = f"{a['slug']} {a['name']} {a['description']}".lower()
        return sum(1 for t in terms if t in hay)

    hits = [a for a in agents if score(a) > 0 and (not div or a["division"] == div)]
    hits.sort(key=lambda a: (-score(a), a["slug"]))
    return {"count": len(hits), "items": [
        {"slug": a["slug"], "name": a["name"], "division": a["division"],
         "description": a["description"][:160]}
        for a in hits[: args.limit]]}


def cmd_inspect(args) -> dict:
    for a in _scan():
        if a["slug"] == args.slug:
            return {"found": True, **{k: a[k] for k in ("slug", "name", "division", "path")},
                    "description": a["description"]}
    return {"found": False, "error": f"паспорт не найден: {args.slug}"}


def cmd_load(args) -> dict:
    for a in _scan():
        if a["slug"] == args.slug:
            with open(a["path"], "r", encoding="utf-8", errors="replace") as fh:
                body = fh.read()
            task = (args.task or "").strip()
            header = (f"Ниже — промпт-паспорт специалиста '{a['name']}'. "
                      f"Задача: {task}\n\n") if task else ""
            return {"found": True, "slug": a["slug"], "name": a["name"],
                    "division": a["division"], "prompt": header + body}
    return {"found": False, "error": f"паспорт не найден: {args.slug}"}


def cmd_list(_args) -> dict:
    agents = _scan()
    divs = {}
    for a in agents:
        divs.setdefault(a["division"], []).append(a["slug"])
    return {"total": len(agents), "divisions": {d: len(v) for d, v in sorted(divs.items())}}


def main() -> int:
    p = argparse.ArgumentParser(description="agency_router — каталог 259 паспортов The Agency")
    sub = p.add_subparsers(dest="mode", required=True)
    ps = sub.add_parser("search"); ps.add_argument("query"); ps.add_argument("--division"); ps.add_argument("--limit", type=int, default=8)
    pi = sub.add_parser("inspect"); pi.add_argument("slug")
    pl = sub.add_parser("load"); pl.add_argument("slug"); pl.add_argument("--task")
    sub.add_parser("list")
    args = p.parse_args()

    fn = {"search": cmd_search, "inspect": cmd_inspect, "load": cmd_load, "list": cmd_list}[args.mode]
    try:
        out = fn(args)
    except Exception as e:
        print(json.dumps({"error": f"agency_router_failed: {e}"}), flush=True)
        return 1
    print(json.dumps(out, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0 if "error" not in out else 1


if __name__ == "__main__":
    sys.exit(main())
