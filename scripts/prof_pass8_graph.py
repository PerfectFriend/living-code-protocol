"""Проход 8 Профессора: +5 узлов, +9 рёбер в knowledge-graph.json (с бэкапом)."""
import json
import shutil

G = "/home/thomas/LivingCode/knowledge-base/knowledge-graph.json"
BAK = "/home/thomas/LivingCode/knowledge-base/knowledge-graph.json.bak-prof-20260927-2322"
shutil.copy2(G, BAK)

d = json.load(open(G, encoding="utf-8"))
before = (len(d["nodes"]), len(d["edges"]))

nodes = [
 {"id": "kb:codegraph", "label": "CodeGraph — pre-indexed граф кода (Hermes в списке агентов)", "type": "topic",
  "priority": 10, "status": "studied", "studied": "2026-09-27",
  "file": "knowledge-base/CodeGraph-Code-Intelligence-Hermes-2026.md",
  "props": {"repo": "colbymchenry/codegraph", "stars": 72181, "license": "MIT", "lang_api": "C",
            "created": "2026-01-18", "pushed": "2026-09-27", "laya": 1.4858,
            "killer_fact": "-62% токенов / -88% вызовов, но +80% остаточного контекста",
            "risk": "install.sh правит конфиг агента (Hermes) — только через снапшот"}},
 {"id": "kb:claude-mem", "label": "Claude-Mem — память между сессиями (SQLite+FTS5+Chroma)", "type": "topic",
  "priority": 9, "status": "studied", "studied": "2026-09-27",
  "file": "knowledge-base/Claude-Mem-Persistent-Memory-2026.md",
  "props": {"repo": "thedotmack/claude-mem", "stars": 94795, "license": "Apache-2.0", "version": "13.28.0",
            "created": "2025-08-31", "pushed": "2026-09-26", "laya": 1.3378,
            "egress_risk": "по умолчанию ведёт в аккаунт; локально только --provider host + CLAUDE_MEM_ONLINE_OPTIN=false"}},
 {"id": "kb:harness-landscape-2026-09", "label": "Ландшафт харнессов 2026-09 по звёздам", "type": "topic",
  "priority": 8, "status": "studied", "studied": "2026-09-27",
  "file": "knowledge-base/Agent-Harness-Landscape-2026-09.md",
  "props": {"laya": 1.226, "rows": 9, "finding": "звёзды не различают качество: ECC 268k/240 issues vs hermes-agent 249k/44415 issues"}},
 {"id": "kb:git-bug", "label": "Git-Bug — баг-трекер внутри git (DAG-сущности, мосты)", "type": "topic",
  "priority": 8, "status": "studied", "studied": "2026-09-27",
  "file": "knowledge-base/Git-Bug-Git-Native-Tracker-2026.md",
  "props": {"repo": "git-bug/git-bug", "stars": 10608, "license": "GPL-3.0", "lang": "Go",
            "created": "2018-07-12", "pushed": "2026-09-26", "laya": 1.1769, "hn": "358 pts / 108 c (25.09.2026)",
            "risk": "GPL-3.0 — архитектуру брать, код не встраивать"}},
 {"id": "kb:ecc", "label": "ECC — «ОС харнесса»: 68 агентов, 292 скилла, инстинкты с confidence", "type": "topic",
  "priority": 7, "status": "studied", "studied": "2026-09-27",
  "file": "knowledge-base/ECC-Harness-OS-2026.md",
  "props": {"repo": "affaan-m/ECC", "stars": 268334, "license": "MIT", "release": "2.2.2",
            "created": "2026-01-18", "pushed": "2026-09-24", "laya": 1.0872,
            "borrow": "instinct-based learning with confidence scoring; изоляция: не менять user-level конфиг"}},
]

edges = [
 {"from": "kb:codegraph", "to": "kb:headroom", "rel": "complements",
  "why": "граф сокращает число шагов (-62% токенов), но +80% остаточного контекста; headroom сжимает то, что вернулось"},
 {"from": "kb:codegraph", "to": "kb:codebase-memory-mcp", "rel": "same_niche",
  "why": "оба индексируют кодовую базу в граф; codegraph вдобавок авто-конфигурирует MCP в Hermes"},
 {"from": "kb:codegraph", "to": "kb:magpie", "rel": "same_risk_class",
  "why": "install-шаг правит конфиг агента ⇒ обязателен снапшот конфига перед запуском (правило Лорда)"},
 {"from": "kb:claude-mem", "to": "kb:hindsight", "rel": "same_niche",
  "why": "обе системы памяти агента; claude-mem добавляет адресуемые observation-ID и цену памяти в токенах"},
 {"from": "kb:claude-mem", "to": "protocol:snapshot", "rel": "requires",
  "why": "установщик по умолчанию уводит память в аккаунт (egress) — допустим только локальный режим"},
 {"from": "kb:git-bug", "to": "kb:gnap", "rel": "confirms_direction",
  "why": "вторая независимая реализация линии «git = база, а не только история»; мосты вместо внешнего трекера"},
 {"from": "kb:git-bug", "to": "kb:unreal-agent", "rel": "answers",
  "why": "отвечает на наш дефект параллельных писателей в один markdown: сущности как DAG-объекты в git + push/pull"},
 {"from": "kb:ecc", "to": "kb:aas-core", "rel": "same_niche",
  "why": "оба про «каталог скиллов + отбор»; ECC добавляет инстинкты с confidence scoring"},
 {"from": "kb:harness-landscape-2026-09", "to": "kb:codegraph", "rel": "surveys",
  "why": "сравнительный срез, в котором codegraph — единственный, называющий Hermes среди поддерживаемых агентов"},
]

have = {n["id"] for n in d["nodes"]}
d["nodes"] += [n for n in nodes if n["id"] not in have]
d["edges"] += edges
d["stats"] = {"nodes": len(d["nodes"]), "edges": len(d["edges"]),
              "updated": "2026-09-27T23:22:00+02:00", "pass": "professor-8"}
json.dump(d, open(G, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

after = json.load(open(G, encoding="utf-8"))
print(f"backup {BAK}")
print(f"nodes {before[0]} -> {len(after['nodes'])} | edges {before[1]} -> {len(after['edges'])}")
dangling = [e for e in after["edges"] if e["to"] not in {n["id"] for n in after["nodes"]} and not e["to"].startswith("protocol:")]
print("edges with non-node target (external/protocol refs):", len(dangling))
