"""Проход 8 Профессора: бэкап Учебника + добавление раздела с 5 разобранными темами."""
import re
import shutil
import time

TB = "/home/thomas/Documents/ObsidianVault/Учебник.md"
BAK = "/home/thomas/Documents/ObsidianVault/Учебник.md.bak-prof-20260927-2235"

src = open(TB, encoding="utf-8").read()
shutil.copy2(TB, BAK)

block = """

## 📚 Изучено Агентом-Профессором — 2026-09-27 (проход 8, cron 22:0x → 22:4x): 5 тем, 🔴 = 0 на входе

> **Замер на входе:** 🔴-тем в Учебнике — **0** (19 совпадений подстроки 🔴 — все служебные: легенда строк 12–13,
> заготовка-команда, вложенный текст, исторические разделы). Реальная работа прохода — **остаток очереди Искателя**:
> 🟡-пункты дайджеста `textbook/AI-Engineering-News-2026-09-27.md`, которые ни один проход ещё не разбирал
> (git-bug, codegraph, claude-mem, ECC, сравнение харнессов).
> **Laya-скоринг (живой прогон 22:25, локальный путь):** codegraph **1.4858** · claude-mem **1.3378** ·
> ландшафт харнессов **1.226** · git-bug **1.1769** · ECC **1.0872** — все пять ≥0.8, ниже порога ничего не отложено.
> **Аномалия прогона:** тёплый сервис Laya (`127.0.0.1:8731`, pid 674192, поднят 18:01) **заблокирован** параллельным
> прогоном другого агента (запрос от 22:28, `--file /home/thomas/tmp_search/findings_20260927.txt`) — HTTP-сервер
> одноthread-овый, мои запросы не обслуживались (420 с без ответа). Скоринг выполнен **локальным путём** скриптом
> `orchestration/scripts/score_topics_local.py` (одна загрузка модели, 5 предсказаний, 60–70 мс на решение после
> прогрева). Побочно: файл `laya_service.py` изменён **18:49**, то есть позже старта сервиса — работающий сервис
> исполняет старый код (класс «агент читает состояние, пока другой его меняет», уже фиксировался 27.09).
> Граф: `knowledge-graph.json` — **+5 узлов, +9 рёбер** (63/111). WIKI: новый раздел прохода.

- [x] [1. CodeGraph — pre-indexed граф кода; `codegraph install` сам вписывает MCP в Hermes Agent](CodeGraph-Code-Intelligence-Hermes-2026.md) — 🟢 #professor:2026-09-27 #priority:1 #laya:1.4858 #source:github/npm #kb:CodeGraph-Code-Intelligence-Hermes-2026.md
- [x] [2. Claude-Mem — память между сессиями: SQLite+FTS5, Chroma, адресуемые observation-ID](Claude-Mem-Persistent-Memory-2026.md) — 🟢 #professor:2026-09-27 #priority:2 #laya:1.3378 #source:github #kb:Claude-Mem-Persistent-Memory-2026.md
- [x] [3. Ландшафт харнессов-2026 по звёздам: ECC 268k, hermes-agent 249k, graphify 122k, deer-flow 83k](Agent-Harness-Landscape-2026-09.md) — 🟢 #professor:2026-09-27 #priority:3 #laya:1.226 #source:github #kb:Agent-Harness-Landscape-2026-09.md
- [x] [4. Git-Bug — баг-трекер внутри git (DAG-сущности, мосты в GitHub/Jira, GraphQL+webui)](Git-Bug-Git-Native-Tracker-2026.md) — 🟢 #professor:2026-09-27 #priority:4 #laya:1.1769 #source:github/hn #kb:Git-Bug-Git-Native-Tracker-2026.md
- [x] [5. ECC — «ОС харнесса»: 68 агентов / 292 скилла, инстинкты с confidence, AgentShield](ECC-Harness-OS-2026.md) — 🟢 #professor:2026-09-27 #priority:5 #laya:1.0872 #source:github #kb:ECC-Harness-OS-2026.md

**Главное прохода (для нас):**
- **Второй внешний инструмент, который сам встаёт в конфиг Hermes:** `codegraph install` «detects and auto-configures
  … **Hermes Agent** … wiring the CodeGraph MCP server into each». Первым был `codebase-memory-mcp` (проход 7). Правило
  Лорда подтверждается: любой такой установщик — только через снапшот конфига.
- **Торговля, которой раньше не было в KB:** codegraph сам измеряет цену своей скорости — **−62 % токенов и −88 %
  вызовов инструментов**, но **+80 % остаточного retrieval-контекста** к концу сессий (VS Code: 67k против 18k).
  Это прямая пара к `headroom` (сжатие): граф уменьшает *работу*, headroom уменьшает *след*. Ставить их надо вместе.
- **ECC дал готовую формулировку нашего правила изоляции:** его адаптер Kimi «safely merges project MCP entries …
  **and does not change the user-level config**», с dry-run и регресс-тестом на «все записи внутри проектного корня».
- **claude-mem — риск egress по умолчанию:** установщик ведёт в аккаунт (magic link, «observer» на 30 дней free),
  локальный режим только opt-in (`--provider host`, `CLAUDE_MEM_ONLINE_OPTIN=false`). У нас допустим только локальный.
- **Git-Bug — GPL-3.0** (копилефт): архитектуру можно брать, код в наши утилиты — нет.

**Честные границы прохода:** ни один из пяти инструментов **не устанавливался и не запускался** (установка правит
конфиги агентов и требует аппрува, которого в cron нет). Все числа — из живого GitHub API, README и HN Algolia API
(сняты 22:28–22:33), бенчмарки codegraph/ECC — самоотчёт авторов, мной не воспроизводились.
"""

open(TB, "a", encoding="utf-8").write(block)

after = open(TB, encoding="utf-8").read()
red_total = after.count("🔴")
red_real = len(re.findall(r"^- \[ \].*🔴", after, re.M))
heads = len(re.findall(r"^### ", after, re.M))
print(f"backup: {BAK}")
print(f"🔴 всего: {red_total} | 🔴 в строках-задачах: {red_real} | заголовков ###: {heads} | размер: {len(after)}")
