# 🚀 EVOLUTION PLAN v3 — Полная автономная эволюция до релиза (2026-11-02)

**Цель:** полностью автономный процесс «кодер → аудитор → художник/музыкант → продюсер → релиз» для всех 4 игровых проектов (elemental-life, elemental-life-2, cybertarot, cybertarot-full) без участия владельца между циклами. Выпуск готовых изделий (APK, ассеты, отчёты) происходит автоматически. **Авто-релиз включён.**

**Основание:** планы v1 (2026-10-23) и v2 (2026-11-02) + находки Искателя и Профессора в Obsidian/knowledge-base (A-Evolve 3-слойная эволюция, Self-HPO H↔P, Kimi K3 swarm, Graphify, Spec-Kit/SDD) + то, что уже работает в репозитории.

---

## Что уже работает (база для v3)

### Протокол Живого Кода — текущее состояние (02.11.2026)
- 30 заданий на `nvidia/nemotron-3-ultra-550b-a55b` (provider nvidia), minimax → HISTORICALLY_DEAD.
- Роли: 4 проектных кодера, `LV-artist`, `LV-dj-musician`, `LV-producer`, `LV-lord-of-code`, `LV-inquisitor`, `LV-professor`, `LV-searcher`, `LV-config-backup`, `LV-node-health`, `LV-model-sync`.
- `hermes cron status`: rc=0, 29 ролей, 0 ошибок.
- Отчёты пишутся в `reports/*.md` и доставляются в топик `telegram:-1004431090317:252` через `hermes send MEDIA:` (файлом, не текстом).

### v2-контракт (уже внедрён)
- `agents/TASK_CONTRACT.md`, `agents/templates/art-task.md`, `agents/templates/snd-task.md`.
- Каталоги `tasks/` в 4 проектах. Кодер/продюсер пишут `[TRIGGER_ARTIST]` / `[TRIGGER_MUSICIAN]` в `journal.md`.
- Роли берут первую заявку без `[ART_DONE]`/`[SND_DONE]`, переименовывают в `.done`, отвечают в журнал.

### Находки Искателя и Профессора (Obsidian / knowledge-base)
| Находка | Суть | Статус |
|---|---|---|
| A-Evolve / A-EVO-Lab | 3-слойная эволюция: task-harness → evolver → meta-evolver | Изучено, laya 1.37-1.47 |
| Self-HPO | Цикл H-step (оптимизация харнесса) ↔ P-step (политика агента), +7% resolve rate | Изучено |
| Kimi K3 Agent Swarm | Горизонтальное масштабирование до 300 суб-агентов, PARL | Изучено, laya 1.36 |
| Graphify | Knowledge graph кода без векторов; MCP-сервер, 10 инструментов | Установлен (0.9.97), граф elemental-life-2: 798 узлов / 1413 рёбер / 65 сообществ |
| Spec-Kit / SDD | spec → plan → tasks → implement → verify | Изучено |

### Инструменты в репозитории (LivingCode/orchestration/scripts)
- `l3_critic.py` — независимая проверка deliverable + criteria → вердикт `stabilen` / `regress` / `nuzhna_rabota`
- `scp_a2a_gateway.py` — адаптер SCP ↔ A2A для межсервисного взаимодействия агентов
- `cycle_close.py`, `prof_graph_update.py`, `prof_pass8_graph.py` — закрытие цикла и обновление графа знаний
- `knowledge-base/knowledge-graph.json` — 200 узлов, 195 deployed

---

## Nueva структура роя (v3) — Self-HPO + A-Evolve

### Слой Harness (H-step — оптимизация инфраструктуры)
- **`LV-harness-opt`** (бывший `LV-supervisor`) — раз в сутки analysiert `attempt_*.json`, `errors.log`, результаты `l3_critic`, правит `jobs.json` (модели, расписание, skills, deliver) + промпты ролей. Выход: `reports/harness-opt-*.md` + коммит в `orchestration/jobs/jobs.json`.

### Слой Evolver (P-step — выполнение, политика агентов)
- **`LV-coder-elemental-life`**, **`LV-coder-elemental-life-2`**, **`LV-coder-cybertarot`**, **`LV-coder-cybertarot-full`** — по одному на проект. Конвейер: прочитать план проекта → взять 1 пункт → реализовать → запустить `l3_critic.py` ПЕРЕД коммитом → если `stabilen`, закоммитить → триггер артиста/музыканта если нужны ассеты → отчёт.
- **`LV-artist`** — графика/UI по v2-контракту заявок (`tasks/art-*.md`).
- **`LV-dj-musician`** — аудио по v2-контракту заявок (`tasks/snd-*.md`).
- **`LV-producer`** — **авто-релиз**: по `ВЕРДИКТ: ГОРЯЧИЙ` от Лорда + `l3_critic stabilen` → тег `vX.Y.Z`, APK в `~/apkexport/`, отчёт `reports/release-*.md`, пуш тега.

### Независимая проверка (L3 critic)
- `l3_critic.py` вызывается кодером ПЕРЕД каждым коммитом. Вердикт `stabilen` / `regress` / `nuzhna_rabota`. Если `regress` — не коммитить, исправить.

### Владычество
- **`LV-lord-of-code`** — `ВЕРДИКТ: <проект> — ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ`. `ГОРЯЧИЙ` + `l3_critic stabilen` = автоматический триггер релиза продюсеру.

### База знаний
- **`LV-professor`** + **`LV-searcher`** — изучение, конспекты.
- **`LV-inquisitor`** — аудит, триаж проблем.
- **`LV-graph-pulse-export`** — обновляет `knowledge-base/knowledge-graph.json` после каждого цикла.

### Инфраструктура
- **`LV-config-backup`**, **`LV-node-health`**, **`LV-model-sync`** — обслуживание.

### Удалено (избыточно / не работает)
- `LV-night-artist`, `LV-night-musician` — `Script not found` с 18.08.
- `LV-ui-gate` — встроено в кодера/артиста через `laya_bridge.py ui_gate`, отдельная роль не нужна.
- `LV-coder-project1..4`, `LV-coder-paranoidx` — пустые/короткие промпты, не в активном конвейере.

---

## Фаза 1 — Харнесс эволюции: Self-HPO цикл (H-step ↔ P-step)

- [x] **H-step:** `LV-harness-opt` раз в сутки оптимизирует `jobs.json` + промпты на основе метрик P-step.
- [ ] **P-step:** кодер/художник/музыкант работают по текущему промпту; результат фиксируется в отчёте; следующий слот читает предыдущий отчёт и корректирует действия.
- [ ] **Гейт перехода:** цикл успешен, если за сутки 0 новых `stale/unresponsive`, все 4 проектных кроны зелёные, хотя бы 1 релизный артефакт собран.

---

## Фаза 2 — A-Evolve: 3-слойная эволюция протокола

- [x] **Layer 1 — Task-harness:** `orchestration/jobs/jobs.json`, `hermes-config/config.yaml`, промпты ролей, шаблоны `agents/templates/`. Живёт в репо под версионным контролем.
- [x] **Layer 2 — Evolver:** `living_code_agent_wrapper.py` + `check_roster.py` + шедулер. Цикл: вызов модели → отчёт → проверка → коммит.
- [ ] **Layer 3 — Meta-evolver:** расширение `LV-harness-opt` — эволюция самого кода эволюции (`living_code_agent_wrapper.py`, `cycle_close.py`, `l3_critic.py`). Выход: PR в `orchestration` + ревью Лорда.

---

## Фаза 3 — Конвейер «код → релиз» (автоматический выпуск изделий)

- [x] **Вердикт Лорда → триггер авто-релиза:** `ВЕРДИКТ: <проект> — ГОРЯЧИЙ` + `l3_critic stabilen` = продюсер запускает релиз без участия владельца.
- [ ] **Release скрипт:** `orchestration/scripts/release_project.py` — тегирует `vX.Y.Z`, копирует APK в `~/apkexport/` как `<project>-vX.Y.Z-<имя>.apk`, пишет `reports/release-<project>-vX.Y.Z.md`, пушит тег.
- [x] **APK-экспорт:** шаг продюсера — `find . -name '*.apk'` → `cp` в `/home/thomas/apkexport/` как `<project>-<имя>.apk`.
- [ ] **Чек-лист релиза:** код холодный, нет `[СР]`, `check_roster` rc=0, ui_gate пройден, артефакты художника/музыканта закоммичены.

---

## Фаза 4 — Визуализация процессов разработки (Graphify, опционально)

- [x] **Graphify установлен** — `uv tool install graphifyy` (0.9.97), скилл в `/home/thomas/.hermes/skills/graphify/`, команда `--mcp` для MCP stdio. Граф `elemental-life-2` собран (798 узлов / 1413 рёбер / 65 сообществ, 0 токенов).
- [ ] **Граф пульса:** `LV-graph-pulse-export` обновляет `knowledge-base/knowledge-graph.json` после каждого цикла.
- [ ] **Локальный Graphify MCP:** `graphify <path> --mcp` — можно добавить в Hermes как локальный MCP-сервер для доступа агентов к графу кода.

---

## Фаза 5 — Мульти-агентный рой (Kimi K3 идея, на spätere итерацию)

- [ ] Суб-агенты по темам (UI, тесты, backend, ассеты) по PARL-масштабированию.
- [ ] ХUDDLE-синхронизация через общий `journal.md` проекта.

---

## Критические исправления перед запуском

- [ ] `elemental-life` и `cybertarot` получают rc 75 (запуски 02:17, 12:10) — смотреть `~/.hermes/cron/output/<id>/attempt_*.json`, возможно конфликт session/binding у wrapper'ов.
- [x] Image-модели не финансируются — художник через ComfyUI/image_generate фолбэк.
- [x] Второй Telegram-токен не нужен — GOdModeCoder бот.
- [ ] `state.db` WAL растёт — офлайн-компакция только при остановленном gateway.

---

## Метрики успеха v3

- 4 проектных крона зелёные (0 rc=75, 0 stale) 3 суток подряд.
- ≥ 1 релизный тег (vX.Y.Z) с APK в `~/apkexport/` на каждый проект в неделю.
- 0 ручных вмешательств владельца между циклами (кроме компакта state.db).
- knowledge-graph растёт (узлы +10% в неделю), deployed = 100%.
- `l3_critic` вердикт `stabilen` перед каждым коммитом кодера.

---

## Авто-релиз — включён

Когда Владыка Кода выносит `ВЕРДИКТ: <проект> — ГОРЯЧИЙ` и `l3_critic` выносит `stabilen`, Продюсер сам:
1. Тегирует коммит `vX.Y.Z`.
2. Копирует APK в `~/apkexport/` как `<project>-vX.Y.Z-<имя>.apk`.
3. Пишет отчёт `reports/release-<project>-vX.Y.Z.md`.
4. Пушит тег в GitHub.
