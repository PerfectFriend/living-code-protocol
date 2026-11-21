#!/usr/bin/env python3
"""kg_migrate.py — миграция knowledge-graph.json на схему плана v3 (Фаза 4/5):
  - у каждой связи (edge) появляется link_type из 4 типов Jev-Mem:
    semantic | temporal | causal | entity
  - у каждой связи и узла — provenance {source, ts, verified} (провенанс по умолчанию)
  - у узлов — жизненный цикл status: DRAFT | STUDIED | DEPLOYED | RETIRED (+ причина)
Перед записью — бэкап knowledge-graph.json.bak-<ts>.
Идемпотентно: существующие link_type/provenance не перетираются.
"""
import datetime
import json
import shutil
import sys
from pathlib import Path

KG = Path.home() / "LivingCode" / "knowledge-base" / "knowledge-graph.json"
LINK_TYPES = ("semantic", "temporal", "causal", "entity")
STATUSES = ("DRAFT", "STUDIED", "DEPLOYED", "RETIRED")
TS = datetime.datetime.now().astimezone().isoformat(timespec="seconds")


def classify_rel(rel: str) -> str:
    r = (rel or "").lower()
    if any(k in r for k in ("врем", "temporal", "date", "хронолог")):
        return "temporal"
    if any(k in r for k in ("причин", "causal", "because", "следств", "cause", "→", "->")):
        return "causal"
    if any(k in r for k in ("сущност", "entity", "agent", "автор", "actor")):
        return "entity"
    return "semantic"


def main() -> int:
    if not KG.exists():
        print(f"Нет файла графа: {KG}")
        return 1
    g = json.loads(KG.read_text(encoding="utf-8"))
    bak = KG.with_suffix(f".json.bak-{datetime.datetime.now().strftime('%Y%m%d-%H%M%S')}")
    shutil.copy2(KG, bak)

    migrated_edges = migrated_nodes = 0
    for e in g.get("edges", []):
        if "link_type" not in e:
            e["link_type"] = classify_rel(e.get("rel", ""))
            migrated_edges += 1
        e.setdefault("provenance", {
            "source": "kg_migrate", "ts": TS, "verified": False,
            "note": "провенанс по умолчанию, верифицируй перед DEPLOYED",
        })
        if e["link_type"] not in LINK_TYPES:
            e["link_type"] = "semantic"
    for n in g.get("nodes", []):
        st = str(n.get("status", "STUDIED")).upper()
        if st not in STATUSES:
            st = "STUDIED"
        n["status"] = st
        if "retire_reason" not in n and st == "RETIRED":
            n["retire_reason"] = "причина не указана — заполни вручную"
        n.setdefault("provenance", {"source": "kg_migrate", "ts": TS, "verified": False})
        migrated_nodes += 1

    # Висячие ссылки (pre-existing): создаём stub-узлы, чтобы граф был целым
    ids = {n.get("id") for n in g.get("nodes", [])}
    stubs = 0
    for e in g.get("edges", []):
        for end in ("from", "to"):
            ref = e.get(end)
            if ref and ref not in ids:
                g["nodes"].append({
                    "id": ref, "label": ref, "type": "stub", "priority": "P3",
                    "status": "DRAFT",
                    "studied": TS[:10],
                    "file": None,
                    "props": {"note": "stub создан kg_migrate 2026-11-04: висячая ссылка из ребра; заполни содержимым"},
                    "provenance": {"source": "kg_migrate", "ts": TS, "verified": False},
                })
                ids.add(ref)
                stubs += 1

    g.setdefault("meta", {})["updated"] = TS
    g["meta"]["schema_v3"] = {
        "link_types": list(LINK_TYPES), "statuses": list(STATUSES),
        "migrated": TS, "by": "kg_migrate.py (план v3, фаза 4/5)",
    }
    KG.write_text(json.dumps(g, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"kg_migrate: edges с link_type добавлено {migrated_edges}/{len(g.get('edges', []))}, "
          f"узлов с provenance/status {migrated_nodes}/{len(g.get('nodes', []))}, "
          f"stub-узлов для висячих ссылок: {stubs}; бэкап: {bak.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
