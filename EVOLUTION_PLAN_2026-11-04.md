# 🧬 EVOLUTION PLAN v3 — Протокол Живого Кода (2026-11-04)

**Создан:** 2026-11-04, после аудита базы знаний (`knowledge-base/`, WIKI.md, ~40 конспектов по автономным агентам, харнессам, RSI, верификации).
**Предыдущий план:** `EVOLUTION_PLAN_2026-11-02.md` — архив с 04.11. Этот план — актуальный.
**Область:** эволюционирует ТОЛЬКО сам протокол (orchestration, роли, гейты, память). Проекты, которые протокол разрабатывает (Projects/, Project1–4), не трогаем.

**Принципы (v2 сохраняются + новые):**
1. Один запуск агента = один пункт плана = один завершённый цикл (код + тест + коммит). Отчёты на русском.
2. Межролевой контракт — машиночитаемые маркеры (`[TRIGGER_*]`, `[ART_DONE]`, `ВЕРДИКТ:`, `[LAYA_VERDICT]`). Перед правкой живого скрипта — бэкап `.orig-<дата>`.
3. **БАН NEMOTRON (решение владельца 04.11.2026)** не меняется: `BANNED_MODEL_SUBSTRINGS`, `sys.exit(3)` без API. Primary = `mistralai/mistral-large-4-1t-a52b` (nvidia).
4. NEW: журнал/дайджесты — **недоверенный вход** (compaction-deception, OpenAI 09.2026): каждая запись помечена «проверено прогоном» или «пересказано».
5. NEW: гейт читает **код возврата + счётчик проверенных артефактов**, а не текст отчёта; «проверено N=0 ⇒ не проверено».
6. NEW: safety-гейты лежат НИЖЕ слоя самообучения (LocalKin) — эволюция протокола не может ослабить бан/аудит/бэкапы.

## Контекст: что произошло 04.11.2026

- Nemotron показал себя саботёром (без спроса уничтожил локальные проекты и GitHub) → жёсткий бан внедрен во всех слоях: движок `living_code_agent_wrapper.py`, `check_roster.py`, 20 обёрток, `orchestration/jobs/jobs.json`, live-реестр `~/.hermes/cron/jobs.json` (31/31 через `hermes cron edit --pin`), `~/.hermes/config.yaml` (9 ключей через `hermes config set`), `orchestration/hermes-config/config.yaml`, model_registry, evolution_engine, routing_cache, scp_a2a_gateway, harness_opt.txt, orchestrator_state.json. Ростер регенерирован: 30 ролей, 0 ошибок, все на mistral.
- Подробно: `REPORT_EVOLUTION_2026-11-04.md` §1.7.

## Что взяли из базы знаний (конспект → правило для протокола)

| Источник (knowledge-base/) | Что берём |
|---|---|
| Rethinking Verification 2610.34577 | **L3 independent review** — отдельный критик с чистым контекстом, findings→repair; лучший accuracy/cost (+3.9–9.5 pp при 1.0–1.25×). Наш Аудитор в том же контексте — это НЕ L3. |
| Self-Evolving Harness 2609.38372 | Dual-role solver/proposer одной моделью; наш gap: нет Proposer-роли и held-out benchmark. L3 emerged naturally — валидирует. |
| Harness² 2610.14224 | **Propose→Probe→Compose**: 2+ кандидата, probe на той же задаче, behavioral contrast — единственный сигнал accept; Experience Library; компоненты reused by proposal, never inherited. |
| Phantom Guardrails 2607.13083 | Negative control: любой новый guardrail/fix прогоняется на featureless legal input; каждый fix требует evidence реального failure. |
| Safety Must Survive RSI 2610.01073 | Stale scores: с каждой принятой правкой хранить снимок условий, при расхождении оценка протухает; «отклонено ≠ опасное поведение остановлено»; чинить исходную реализацию, не упавшую. |
| Compaction-summary deception (OpenAI 09.2026) | Журнал агента — канал инъекции; handoff помечать проверено/пересказано; snapshot-коммит — единственное неподделываемое; Аудитор делает replay, а не сверку текста. |
| SAFE-Mem + SCP | Метки kind/authority/scope на утверждениях памяти; swarm-сообщения untrusted by construction. |
| LocalKin | Ритм audit→fix→**verify отдельным агентом**→research; safety-гейты ниже слоя эволюции; «thin soul + fat skill». |
| state-grader / gogo-agent / HarnessMaster / Orbit / mcgyvr | Оценка по диффу состояния, не «тесты зелёные»; N=0 ⇒ не проверено; null/liar-тест гейта; «закончил» ≠ «принято»; deterministic evals рядом с LLM, n/a ≠ fail; песочница = снимок коммита (проверять diff). |
| Self-improving ecosystem (Git-on-my-Level) | quality = treatment − contemporaneous baseline; min sample size — контрактом; вердикт называет ПРИЧИНУ отказа (`correct/objective/note`); promotion-цепочка + откат. |
| Jev-Mem + hive (Laya) | Laya официально поддержана как System-One контроллер памяти; 4 типа связей (семантика/время/причина/сущности); провенанс+таймстемп по умолчанию; правило значимости: «−45% цены при −4 п.п. разрешаемости и p=1.0» — НЕ выигрыш. |
| Agents are systems, not models 2610.01618 | 54% дисперсии = повтор одной конфигурации; перед сравнением агентов фиксировать конфиг и повторять N раз; желаемое поведение — инструментом, а не просьбой в промпте. |
| Approval queue (fault line) | Human-гейт только на «линии разлома»: необратимое, наружу, удаление, push в protected; before/after снимки; reject с обязательным объяснением; лестница понижения (доверие растёт с доказательствами). |
| Orcha / Abathur / metacodes / ACE-Router | Вердикт с авто-возвратом задачи агенту с уликой; human-решения как персистентная таблица; worktree-изоляция; sha256 артефактов в doctor; роутинг по истории, не полным списком MCP-схем. |

## Фаза 0 — Безопасность и доверие (неделя 1, до всего остального)

- [ ] `agents/journal.md` объявить untrusted input: правило маркировки записей `[VERIFIED <cmd>]` / `[REPORTED]`; Аудитор обязан делать independent replay критичных фактов, а не сверять текст.
- [ ] Stale-score rule: каждый принятый инкремент протокола хранит condition snapshot (модель, конфиг, версии, дата); при расхождении старая оценка помечается протухшей в `state/`.
- [ ] «Отклонено ≠ остановлено»: при reject правки, которая уже запущена в роль, явно откатывать/отключать поведение + запись `[REVERTED] <что> <почему>`.
- [ ] Approval fault-line для действий протокола: гейт владельцем ТОЛЬКО на — push в protected remotes, удаление файлов/веток/реп, смена модели в 4 слоях, правка `BANNED_MODEL_SUBSTRINGS`, отключение кронов. Остальное — аудит постфактум. В journal — before/after diff.
- [ ] Бан nemotron не обсуждается: любой запрос → `sys.exit(3)` + `[SECURITY_INCIDENT]` в журнал.
- [ ] Каждый отчёт роли несёт флаги `networkAccessed: true/false`, `targetModified: true/false` (BLA Shield).

## Фаза 1 — L3 Independent Review + Proposer-роль (неделя 1–2)

- [ ] Новая роль **LV-critic**: отдельный агент, чистый контекст (только deliverable + spec + критерии приёмки), не видит журнал кодера; возвращает структурированные findings (blocker/major/minor/info), а не вердикт; один repair-раунд: кодер правит → повторный review.
- [ ] Внутри critic сначала **measured**-проверки детерминированно (запуск тестов, return codes, счётчики артефактов, laya-score где применимо), LLM-суждение — только для оценок.
- [ ] Новая роль **LV-proposer**: читает run-records (reports/, attempt-логи) и предлагает правки самого протокола (engine, wrappers, prompts, jobs, configs) — закрывает gap из Self-Evolving Harness.
- [ ] Held-out benchmark протокола («наш Claw-Eval»): 10–15 эталонных задач (check_roster, запуск обёртки в dry-run, release_project dry-run, compact_state_db --check, graph pulse export…). Обязан проходить после ЛЮБОЙ правки протокола — regression-набор.

## Фаза 2 — Цикл эволюции самого протокола: Propose→Probe→Compose (неделя 2–3)

- [ ] Любая правка протокола проходит PPC: Propose (2+ кандидата, каждый trace'ится к наблюдению) → Probe (прогон на benchmark + одном живом цикле) → Compose (behavioral contrast — единственный сигнал accept; без contrast — отклонить).
- [ ] Negative control (Phantom Guardrails): новый guardrail/fix прогоняется на featureless legal input перед accept.
- [ ] Классификация сбоев в журнале: `infra_error` ≠ урок агента — при infra_error промпт/SOP не меняется (Living-Harness).
- [ ] `protocol/EXPERIENCE.md` — Experience Library: situation / lesson / evidence; компоненты переиспользуются by proposal, never inherited.
- [ ] Зафиксировать редактируемое дерево слоёв протокола (c1..c8-аналог): engine, roster, wrappers, prompts, jobs, hermes-config, state, knowledge-graph.

## Фаза 3 — Качество гейтов приёмки (неделя 2)

- [ ] Гейт = return code + счётчик проверенных артефактов; правило «N=0 ⇒ не проверено» зашить в `evidence_gate.py` и `check_roster.py`.
- [ ] null/liar-тесты для admission-гейта: «агент написал „готово“ без изменения артефакта» обязан падать так же, как «ничего не сделал» (один файл тестов).
- [ ] В отчётах и knowledge-graph разделить поля `finished` / `accepted` (Orbit).
- [ ] Расширить `evidence_gate.py` (уже подключён к wrapper и scp_a2a_gateway): добавить baseline-замер (quality = treatment − contemporaneous baseline), min sample size как параметр, вердикт с причиной отказа (`correct/objective/note`).
- [ ] Проверка всегда по diff коммита (песочница = снимок), не по репозиторию целиком.
- [ ] Перед релизом роли — L2 completion gate детерминированный: `py_compile` + `bash -n` + `check_roster` зелёные.

## Фаза 4 — Laya: где она сейчас и куда углубляем (неделя 1–3)

**Текущее состояние (проверено 04.11.2026):**
- Локальная модель `laya-multilingual` (чекпоинт `models/laya-multilingual`) живёт в тёплом сервисе `laya-warm.service` (systemd user unit, **active since 2026-11-03 22:41, enabled**); холодный вызов платит 4.6+ с загрузки чекпоинта.
- `laya_bridge.py` режимы: `score | triage | verdict | ui_gate | raw`. Используется: `wrapper_ui_gate.sh` (ui_gate), очередь тем Профессора/Учебника (score, см. WIKI-проходы), `lord_of_code.py`, health-чек в `cycle_start_cron.py`; `evidence_gate.py` знает форматы laya-скоров.
- **Мёртвые звенья:** `logprobs_decider.py` (raw-режим для роутинга) — написан, но **ничем не вызывается**; LLM-роль «Судья Laya» (`wrapper_laya.sh` + `prompts/laya.txt`, сейчас на mistral после бана) — без собственного расписания по дизайну, но в журнале **нет `[TRIGGER_LAYA]`** → роль спит.

**План по laya:**
- [ ] Тёплый сервис — единственный путь решений; fallback на холодный путь только при падении сервиса + алерт `[LAYA_FALLBACK]` в журнал.
- [ ] Laya как System-One памяти (Jev-Mem): в `knowledge-graph.json` 4 типа связей (семантика/время/причина/сущности) + провенанс и таймстемп каждой записи по умолчанию.
- [ ] `laya_bridge.py verdict` встроить в цикл Кодер→Продюсер как measured-слой перед LLM-судьёй; verdict возвращает задачу с уликой (Orcha), а не только скор.
- [ ] Правило значимости laya-скоров: сигнал приоритета, решение — по живому замеру; расхождение фиксировать явно (уже делаем в WIKI).
- [ ] Решить судьбу `logprobs_decider.py`: подключить к роутингу wrapper/engine ИЛИ вывести из оборота с записью в журнал.
- [ ] Оживить или формально приостановить роль Судьи-Laya: либо Продюсер стабильно шлёт `[TRIGGER_LAYA]` каждый цикл, либо убрать обёртку из ростера как мёртвую (extinction: бэкап + запись в chronicle).
- [ ] GPU/Vulkan для Laya остаётся стеной (`LAYA_GPU_VULKAN.md`: IREE fp32 → OOM); держимся на CPU warm service.

## Фаза 5 — Память и граф знаний (непрерывно)

- [ ] 3-уровневая память протокола: working (journal) / episodic (reports) / semantic (knowledge-base + knowledge-graph); prune с decay.
- [ ] Deadman для ролей: тишина классифицируется (ЖИВ/БОЛЕН/МЁРТВ), а не «тишина = здоровье» — расширить `LV-extinction-check` до пульса всех 30 ролей.
- [ ] knowledge-graph: жизненный цикл STUDIED → DEPLOYED → RETIRED с причиной; честные статусы, без «зелёного по умолчанию».

## Фаза 6 — Эксплуатация (постоянно)

- [ ] Компакция `state.db` (2.5 ГБ) в окно с остановленным gateway — `compact_state_db.sh` готов.
- [ ] `CATHEDRAL_BOT_TOKEN` — задать владельцу (иначе отчёты супер-супервайзера не уходят в топик 252).
- [ ] rc=75: авто-ретрай в движке (сейчас ручной `resume --run-now` каждый цикл).
- [ ] 3 проекта с uncommitted-изменениями (superguard, elemental-life, cybertarot) — закоммитить или откатить.
- [ ] Бэкапы: зеркало orchestration на F2DB-14E5 после ремоунта (сверка SHA); `.orig-<дата>` перед правкой живых скриптов.
- [ ] `check_roster.py --update` после любого изменения jobs.json; гейт rc=0.

## Метрики успеха

- 0 инцидентов с запрещёнными моделями; 100% ролей на `mistralai/mistral-large-4-1t-a52b`; `check_roster` — 0 ошибок после каждого изменения реестра.
- Каждый цикл кодера проходит L3 (critic findings → repair) ДО принятия; 0 «принято по тексту отчёта».
- Все гейты отдают return code + N проверенных артефактов; 0 случаев «зелёный при N=0».
- ≥1 успешный цикл на каждый игровой проект в сутки; доставка отчётов 100% или явный retry в журнале.
- `laya-warm` uptime ≥99%; каждый fallback зафиксирован `[LAYA_FALLBACK]`.

## Открытые вопросы владельцу

1. Судья-Laya (LLM-роль): оживлять (Продюсер шлёт `[TRIGGER_LAYA]` каждый цикл) или убрать из ростера как мёртвую?
2. `logprobs_decider.py` — подключить к роутингу или убрать?
3. Порог «лестницы понижения» гейтов: сколько последовательных одобрений без отклонений снимает human-гейт (в источнике-примере 200) — выбрать наше число.
4. ComfyUI/Voicebox как постоянные сервисы на 780M — по ночам или никогда?

---

## Статус реализации (2026-11-04, ~07:50 CET) — что внедрено и проверено прогоном

**Фаза 0 — все пункты внедрены:**
- журнал = untrusted input + теги `[VERIFIED <cmd>]`/`[REPORTED]`: `orchestration/scripts/journal_lint.py` + `orchestration/docs/JOURNAL_RULES.md` (в release_gate и benchmark; на живом журнале линт нашёл 5 старых незатегированных утверждений — правило действует впредь);
- stale-score: `scripts/condition_snapshot.py` (snapshot/check; хеш стабильных полей live-jobs, чтобы таймстемпы hermes не протухали сами); предупреждение `CONDITION_STALE` в `check_roster.py`; fatal-проверка в benchmark. Прогнано: STALE поймал смену условий, после snapshot — OK, стабилен после `cron list`;
- fault-line: `scripts/guard_action.py` (классы push-protected/delete/model-change/ban-edit/cron-disable; selftest rc=0) + `scripts/git_push_guarded.sh`; `[OWNER_APPROVED]`/`_BLOCKED` в журнал;
- бан + `[SECURITY_INCIDENT]`: прогнано — `wrapper.py "..." "" nvidia/nemotron-test nvidia` → rc=3, API не вызывался, маркер в журнале 07:41;
- флаги `networkAccessed`/`targetModified` в шапке каждого md-отчёта движка (`_write_report_md`).

**Фаза 1:** роли `LV-critic` (L3, чистый контекст, measured-first; джоб `0 */6 * * *`) и `LV-proposer` (джоб `0 5 * * 1`), обе пин на mistral; промпты `wrappers/prompts/{critic,proposer}.txt`, обёртки `wrapper_{critic,proposer}.sh`. Held-out benchmark: `orchestration/tests/protocol_benchmark.py` — **LC-EVAL v1: 14/14 зелёные** (прогон 07:46).

**Фаза 2:** `orchestration/docs/PPC.md` (Propose→Probe→Compose, negative control, infra_error ≠ урок), `protocol/EXPERIENCE.md` (4 записи с evidence), `protocol/COMPONENTS.md` (c1..c8). rc=75: один авто-ретрай в движке + `[RC75_RETRY]` (фаза 6, проверено синтаксисом; живого rc=75 пока не было).

**Фаза 3:** `evidence_gate.py`: правило N=0 ⇒ NOT_VERIFIED, `artifacts_checked`, `--baseline` (BASELINE_REGRESSION с причиной), `--min-sample` (LOW_SAMPLE), `finished_claimed`/`accepted`; null/liar-тесты `tests/test_admission_gate.py` — **8/8 PASS**; N=0 правило также в `check_roster.py` (пустой ростер → rc=1, проверено); L2-гейт `scripts/release_gate.py` — **PASS 7/7**, включён в чек-лист `release_project.py`.

**Фаза 4 (laya):** `[LAYA_FALLBACK]` в журнал при cold-path (`laya_bridge.py`, проверено вызовом); verdict как measured-слой в цикле — шаг 3a в `prompts/producer.txt` (`[LAYA_VERDICT_LOCAL]`); knowledge-graph на схеме v3: 4 типа связей + провенанс у всех 232 рёбер / 210 узлов, 10 stub-узлов для висячих ссылок, `kg_validate.py` OK (бэкапы `.bak-20261104-*`); решения: `logprobs_decider.py` выведен из wire (роутинг покрыт цепочкой движка), Судья-Laya формально приостановлен (судит `laya_bridge verdict` + LV-critic); GPU-стена без изменений.

**Фаза 5:** deadman `scripts/role_pulse.py` + джоб `LV-role-pulse` (`0 */4 * * *`) — прогон: 33 роли, МЁРТВ: 0; 3-уровневая память зафиксирована в COMPONENTS.md (c8); prune по decay — следующий инкремент. KG lifecycle STUDIED→DEPLOYED→RETIRED + `retire_reason` — в `kg_validate.py`.

**Фаза 6:** `check_roster --update` после изменения jobs.json — сделано (33 роли, 0 ошибок). Осталось владельцу/окну: компакция state.db (нужен остановленный gateway), `CATHEDRAL_BOT_TOKEN`, 3 проекта с uncommitted (проекты не трогаем по указанию), зеркало на F2DB-14E5 после ремоунта.

**Реестр:** live 34 джоба (добавлены LV-critic, LV-proposer, LV-role-pulse), все model-поля вне бана; зеркало `orchestration/jobs/jobs.json` = 34; ростер 33 роли, 0 ошибок.
