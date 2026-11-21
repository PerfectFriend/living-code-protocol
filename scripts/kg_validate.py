#!/usr/bin/env python3
"""kg_validate.py — валидация knowledge-graph.json по схеме v3 (используется в release_gate и benchmark).

Проверки:
  1. все edge ссылаются на существующие node.id
  2. у каждой edge есть link_type из {semantic, temporal, causal, entity} и provenance{source, ts}
  3. у каждого node status из {DRAFT, STUDIED, DEPLOYED, RETIRED}; у RETIRED есть retire_reason
Exit 0 = схема соблюдена, 1 = нарушения (печатаются первые 20).
"""
import json
import sys
from pathlib import Path

KG = Path.home() / "LivingCode" / "knowledge-base" / "knowledge-graph.json"
LINK_TYPES = {"semantic", "temporal", "causal", "entity"}
STATUSES = {"DRAFT", "STUDIED", "DEPLOYED", "RETIRED"}


def main() -> int:
    if not KG.exists():
        print(f"Нет файла графа: {KG}")
        return 1
    g = json.loads(KG.read_text(encoding="utf-8"))
    errors = []
    ids = {n.get("id") for n in g.get("nodes", [])}
    for i, e in enumerate(g.get("edges", [])):
        if e.get("from") not in ids or e.get("to") not in ids:
            errors.append(f"edge[{i}]: ссылка на несуществующий узел {e.get('from')} -> {e.get('to')}")
        lt = e.get("link_type")
        if lt not in LINK_TYPES:
            errors.append(f"edge[{i}] ({e.get('from')}->{e.get('to')}): link_type '{lt}' вне {sorted(LINK_TYPES)}")
        pv = e.get("provenance")
        if not isinstance(pv, dict) or not pv.get("source") or not pv.get("ts"):
            errors.append(f"edge[{i}]: нет provenance[source, ts]")
    for i, n in enumerate(g.get("nodes", [])):
        st = str(n.get("status", "")).upper()
        if st not in STATUSES:
            errors.append(f"node[{i}] {n.get('id')}: status '{st}' вне {sorted(STATUSES)}")
        if st == "RETIRED" and not n.get("retire_reason"):
            errors.append(f"node[{i}] {n.get('id')}: RETIRED без retire_reason")
        pv = n.get("provenance")
        if not isinstance(pv, dict) or not pv.get("ts"):
            errors.append(f"node[{i}] {n.get('id')}: нет provenance.ts")
    if errors:
        print(f"kg_validate: {len(errors)} нарушений схемы v3:")
        for e in errors[:20]:
            print(f"  ⛔ {e}")
        return 1
    print(f"kg_validate: OK — {len(g.get('nodes', []))} узлов, {len(g.get('edges', []))} связей по схеме v3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
