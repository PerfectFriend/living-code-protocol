"""Починка двух висячих рёбер прохода 8: kb:magpie -> kb:magpie-router, kb:hindsight -> kb:hindsight-memory."""
import json

G = "/home/thomas/LivingCode/knowledge-base/knowledge-graph.json"
d = json.load(open(G, encoding="utf-8"))
ids = {n["id"] for n in d["nodes"]}
fix = {"kb:magpie": "kb:magpie-router", "kb:hindsight": "kb:hindsight-memory"}
fixed = 0
for e in d["edges"]:
    if e["to"] in fix and fix[e["to"]] in ids:
        e["to"] = fix[e["to"]]
        fixed += 1
json.dump(d, open(G, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
d2 = json.load(open(G, encoding="utf-8"))
ids2 = {n["id"] for n in d2["nodes"]}
bad = [e for e in d2["edges"] if e["to"] not in ids2 and not e["to"].startswith(("protocol:", "artifact:", "kb:"))]
print("fixed:", fixed, "| nodes:", len(ids2), "| edges:", len(d2["edges"]))
print("remaining targets outside node set (expected: protocol:/artifact: refs):")
print(sorted({e["to"] for e in d2["edges"] if e["to"] not in ids2}))
