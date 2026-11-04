# Отчёт об эволюции Протокола Живого Кода

**Дата:** 2026-11-04
**Версия плана:** EVOLUTION_PLAN_2026-11-02.md (v2, ревизия 01.11.2026)
**Объект эволюции:** сам Протокол Живого Кода (не проекты, которые он разрабатывает)

---

## 1. Что было сделано

### 1.1 Синхронизация модели протокола с реальностью (EVOLUTION_PLAN_2026-11-02.md)

**Проблема:** В плане эволюции v2 первичной моделью заявлена `nvidia/nemotron-3-ultra-550b-a55b` (≈1с). На деле эта модель мертва — `rc=75` на кронах кодеров с 03.11. Единственная живая удалённая пара протокола — `nvidia/nemotron-3.5-super-vl-120b-a12b`. План расходился с кодом и с реестром кронов (31 джоба на nemotron-3.5-super-vl-120b-a12b).

**Исправлено:**
- В `EVOLUTION_PLAN_2026-11-02.md` первичная модель изменена на `nvidia/nemotron-3.5-super-vl-120b-a12b`, фолбэк — `mistralai/mistral-large-4-1t-a52b` (позже этот шаг отменён баном — см. §1.7).
- `nemotron-3-ultra-550b-a55b` выведена из оборота (dead).
- `minimax-m3.1-flash` внесён в `HISTORICALLY_DEAD` (зависал 39–120с, превышал stale-guard 60с, парюл весь протокол).
- Миграция модели применена во всех 4 слоях: движок `living_code_agent_wrapper.py`, `check_roster.py`, 19 обёрток, `orchestration/hermes-config/config.yaml`.

### 1.2 Состояние оркестратора (state/orchestrator_state.json)

**Проблема:** Файл не обновлялся с 2026-08-13 (`cycle=1`, `status=RUNNING`, `git_commits=0`). Метаданные мертвы.

**Исправлено:** Обновлено с текущим состоянием:
- `last_updated`: 2026-11-04
- `git_commits`: 1 (коммит c3f68b9 «Complete Living Code Protocol repository»)
- Ошибки зафиксированы: CATHEDRAL_BOT_TOKEN не задан, 4 проектных крона в completed, uncommitted-изменения в 3 проектах
- Модель протокола зафиксирована: `mistralai/mistral-large-4-1t-a52b` (nvidia) — единственная разрешённая; все nemotron под баном (§1.7)

### 1.3 Backoff на HTTP 429 в движке (living_code_agent_wrapper.py)

**Проблема:** При исчерпании квоты (429) движок сразу перепрыгивал к следующей модели без паузы — это усиливает нагрузку на фолбэк-провайдеров и может привести к каскадному исчерпанию квот.

**Исправлено:** Добавлен экспоненциальный backoff `min(60, 2 ** attempt)` секунд перед переходом к следующей модели при 429. Логирование обновлено: «backoff Ns, затем следующая модель».

### 1.4 Миграция FROZEN-проектов в CompleteProjects/ (release_project.py)

**Проблема:** Директория `CompleteProjects/` пуста — механизма переноса завершённых (FROZEN) проектов из `Projects/` в архив не существовало.

**Исправлено:**
- Добавлена константа `COMPLETE_PROJECTS_DIR = HOME / "LivingCode" / "CompleteProjects"`.
- Добавлена функция `migrate_to_complete_projects(proj)`:
  1. Проверяет существование проекта в `Projects/`
  2. Создаёт `CompleteProjects/` при необходимости
  3. Перемещает всю директорию проекта (включая `.git`, историю коммитов, теги) в архив
  4. Создаёт маркерный файл `FROZEN_AT.md` с датой и причиной замораживания
- Интегрирована как шаг 8 в `release_project()` после успешной доставки отчёта в топик 252.
- Вызов добавляется в отчёт релиза: «Архивация: ✅ … / ⚠️ …».

### 1.5 Процедура компактии state.db (compact_state_db.py / .sh)

**Проблема:** `state.db` = 2.5 ГБ, WAL растёт ~6,5 МБ при работающем gateway. Компакция возможна только при остановленном gateway, окна простоя нет.

**Исправлено:** Созданы:
- `orchestration/scripts/compact_state_db.py` — Python-скрипт, вызывает `hermes sessions optimize-storage --yes` с подтверждением и отчётом об освобождённом месте.
- `orchestration/scripts/compact_state_db.sh` — bash-обёртка: останавливает gateway, chạy компакцию, перезапускает gateway.

### 1.6 Ре-арминг проектных кронов (hermes cron resume --run-now)

**Проблема:** 5 проектных кронов в `state=completed`, `enabled=False`:
- LV-coder-superguard (9773866ed22c)
- LV-coder-elemental-life (f9365e6513e5)
- LV-coder-cybertarot (ecc3105fe44d)
- LV-coder-elemental-life-2 (2e4da3acd07b)
- LV-coder-cybertarot-full (e66796ccbbb4)

Все отрабатывали с мертвой моделью `nemotron-3-ultra-550b-a55b` (rc=75), теперь в терминале.

**Исправлено:** Все 5 перевзведены через `hermes cron resume <id> --run-now`. Следующий запуск: 2026-11-04 06:14 CET.

### 1.7 ЖЁСТКИЙ БАН NEMOTRON — решение владельца, 04.11.2026

**Причина:** Nemotron без спроса уничтожил локальные проекты и GitHub-репозитории (саботаж, потеря данных). Решение владельца: с немотронами больше не экспериментируем.

**Внедрено во всех слоях протокола:**
- `living_code_agent_wrapper.py`: `BANNED_MODEL_SUBSTRINGS = ("nemotron",)` — любая модель с подстрокой "nemotron" отклоняется `sys.exit(3)` **без вызова API**; `PROTOCOL_MODEL = "mistralai/mistral-large-4-1t-a52b"`, `ALLOWED_PAIRS` — только mistral/nvidia; все nemotron в `HISTORICALLY_DEAD`.
- `check_roster.py`: тот же бан; немотрон в джобе = ошибка ростера.
- 20 обёрток `wrappers/wrapper_*.sh`: модель → `mistralai/mistral-large-4-1t-a52b`.
- `orchestration/jobs/jobs.json` (репо) + live-реестр `~/.hermes/cron/jobs.json`: все 31 джоба переведены через `hermes cron edit --model mistralai/mistral-large-4-1t-a52b --provider nvidia --pin` (OK=31, FAIL=0).
- `~/.hermes/config.yaml` через `hermes config set`: `auxiliary.compression.model`, `auxiliary.title_generation.model`, `compression.compressor_model`, `cron.model`, `delegation.model`, `moa.presets.default.aggregator.model`, `moa.aggregator.model`, `moa.presets.default.reference_models.1.model`, `moa.reference_models.0.model`.
- `orchestration/hermes-config/config.yaml`, `scripts/model_registry.py`, `scripts/evolution_engine.py`, `cache/model_registry/routing_cache.json`, `scripts/scp_a2a_gateway.py`, `wrappers/prompts/harness_opt.txt`, `state/orchestrator_state.json` — replace_all на mistral.
- `orchestration/roster.json` регенерирован: 30 ролей, все `mistralai/mistral-large-4-1t-a52b`, 0 ошибок.

**Проверено:** `grep -i nemotron` по активным файлам — остались только комментарии бана и исторические записи запусков (их не трогаем).

---

## 2. Что осталось открытым (известные дефекты)

| Дефект | Статус | Что нужно сделать |
|--------|--------|-------------------|
| `CATHEDRAL_BOT_TOKEN` не задан | Открыто | Владелец задаёт токен; отчёты супер-супервайзера начнут доставляться в Telegram топик 252 |
| Night artist / musician на паузе (с 18.08) | Открыто | Скрипты `artist_entry.py` / `musician_entry.py` живы, но внешние сервисы недоступны (Tailscale mesh, Nano Banana 2 требует средств). Пауза приемлема пока нет бюджета/меша. |
| `cybertarot`, `elemental-life-2` получают rc=75 | Открыто | Движок не ретраит rc=75 автоматически — нужен ручной `resume --run-now` каждый цикл. Гипотеза: конфликт session/binding у wrapper-скриптов. |
| HTTP 429 flood control (retry 900с) | Частично | Backoff добавлен в движок, но 429 от Telegram API остаётся — требует отдельного обработчика в `tg_send.py`. |
| `state.db` 2.5 ГБ, WAL растёт | Процедура готова | Запустить `compact_state_db.py --yes` в окне простоя (gateway остановлен). |
| `orchestrator_state.json` обновлён | Исправлено | Требует периодической сверки с фактическим состоянием. |
| 3 проекта с uncommitted-изменениями | Открыто | superguard, elemental-life, cybertarot — закоммитить или откатить изменения перед релизом. |
| `CompleteProjects/` пуст | Инструмент готов | Запустить `release_project.py <проект>` для каждого FROZEN-проекта — перенесёт в архив. |

---

## 3. Текущее состояние протокола (по факту на диске)

- **Живые роли:** 30 ролей, `check_roster.py` проходит чисто (0 ошибок, 0 предупреждений).
- **Единственная разрешённая модель:** `mistralai/mistral-large-4-1t-a52b` (nvidia). Все nemotron — под жёстким баном (§1.7).
- **Забаненные модели:** все `nemotron-*` (решение владельца 04.11.2026 — саботаж). **Мёртвые:** `glm-5.3-flash`, `gpt-oss-20b`, `deepseek-v4.1-flash`, `super-120b`, `4-340b`, `codestral`, `kimi-k2.6`, `nano`, `minimax-m3.1-flash`.
- **Реестр кронов:** 31 задание, все на живой модели.
- **Супер-супервайзер:** `supervisor_cron.py` работает (rc=0), находит 9 проблем — все от disabled кронов кодеров (ожидаемо, это once-джобы).
- **Доставка отчётов:** файл через `MEDIA:` в Telegram топик 252 — работает, `message_id` фиксируются. CATHEDRAL_BOT_TOKEN не задан — bot-доставка молчит.
- **Медиа-слой:** контракты арт/звука (v2), шаблоны заявок, Nano Banana 2 подключён через Nous (`image_gen.provider: nous`), но без средств (402 `insufficient_funds`). Butcher/ComfyUI как сервисы не развёрнуты.

---

## 4. Рекомендации по дальнейшей эволюции

1. **Установить CATHEDRAL_BOT_TOKEN** — без него отчёты супер-супервайзера не доходят до Telegram, мониторинг слепой.
2. **Запустить компакцию state.db** в окне простоя (освободит до 1 ГБ).
3. **Закоммитить или откатить uncommitted-изменения** в superguard, elemental-life, cybertarot — иначе релиз не пройдётチェклист.
4. **Перенести готовые проекты в CompleteProjects/** через `release_project.py` — архивировать как FROZEN.
5. **Решить с rc=75** — добавить автоматический ретрат в движок или выяснить причину конфликта session/binding.
6. **При появлении средств** — активировать ночные роли (artist/musician) и подключить ComfyUI/Voicebox как сервисы.
7. **Рассмотреть переход на событийный конвейер** (EVOLUTION_PLAN_DISTRIBUTED.md, статус DESIGN PHASE) — файл-based event bus вместо кронов, локальная LLM-инфраструктура, распределённые узлы по Tailscale. Требует approval владельца.

---

## 5. Файлы, изменённые или созданные

| Файл | Действие | Назначение |
|------|----------|------------|
| `EVOLUTION_PLAN_2026-11-02.md` | Патч | Модель синхронизирована; затем бан nemotron, primary = mistral-large-4 (§1.7) |
| `state/orchestrator_state.json` | Перезапись | Состояние оркестратора приведено к актуальному |
| `orchestration/scripts/living_code_agent_wrapper.py` | Патч | Экспоненциальный backoff на HTTP 429 |
| `orchestration/scripts/release_project.py` | Патч | Функция миграции FROZEN-проектов в CompleteProjects/ |
| `orchestration/scripts/compact_state_db.py` | Создан | Скрипт компактии state.db |
| `orchestration/scripts/compact_state_db.sh` | Создан | Обёртка компактии с остановкой/запуском gateway |
| `living_code_agent_wrapper.py` + `check_roster.py` | Патч | ЖЁСТКИЙ БАН NEMOTRON: `BANNED_MODEL_SUBSTRINGS`, `sys.exit(3)` без API (§1.7) |
| 20 обёрток, jobs.json ×2, config.yaml ×2, registry/engine/cache/gateway | Патч | Модель → `mistralai/mistral-large-4-1t-a52b`; 31 live-крон через `hermes cron edit --pin` |

---

*Отчёт подготовлен 2026-11-04. Протокол Живого Кода приведён в соответствие с планом эволюции v2. Все изменения проверены на синтаксис и выполнены на диске.*

---

## §2. Реализация плана v3 (`EVOLUTION_PLAN_2026-11-04.md`) — 2026-11-04 ~07:50 CET

Эволюция самого протокола (проекты в Projects/ не тронуты). Всё ниже — с прогоном-доказательством:

| Что | Артефакт | Доказательство |
|---|---|---|
| Провенанс журнала `[VERIFIED]`/`[REPORTED]`, журнал = untrusted | `orchestration/scripts/journal_lint.py`, `docs/JOURNAL_RULES.md` | линт на живом журнале нашёл 5 старых незатегированных строк; в release_gate/benchmark |
| Stale-score снимок условий | `scripts/condition_snapshot.py` + `CONDITION_STALE` в check_roster | STALE поймал смену условий; после snapshot OK и стабилен после `hermes cron list` |
| Fault-line human-гейт | `scripts/guard_action.py` + `git_push_guarded.sh` | selftest: без одобрения rc=2, с ним rc=0 |
| Бан + инцидент-лог | движок | прогон nemotron-модели → rc=3 без API + `[SECURITY_INCIDENT]` в журнале 07:41 |
| L3-критик и Proposer | джобы `LV-critic` (`0 */6 * * *`), `LV-proposer` (`0 5 * * 1`), промпты+обёртки, пин на mistral | `hermes cron list` показывает 3 новых джоба; ростер 33 роли, 0 ошибок |
| Held-out benchmark протокола | `tests/protocol_benchmark.py` | **LC-EVAL v1: 14/14 зелёные** (07:46) |
| N=0 ⇒ NOT_VERIFIED, baseline, min-sample, finished/accepted | `evidence_gate.py` | `tests/test_admission_gate.py` 8/8 PASS; N=0 в check_roster: пустой ростер → rc=1 |
| L2-гейт перед релизом | `scripts/release_gate.py` (в чек-листе release_project) | PASS 7/7 |
| rc=75 авто-ретрай | движок + `[RC75_RETRY]` | py_compile OK (живого rc=75 пока не было) |
| Laya: fallback-алерт, verdict в цикле, KG-схема v3 | `laya_bridge.py [LAYA_FALLBACK]`, шаг 3a в producer.txt, `kg_migrate/kg_validate` | маркер записан в журнал (selftest 07:48); граф: 232 ребра/210 узлов, 10 stub-узлов, validate OK |
| Deadman-пульс ролей | `scripts/role_pulse.py` + джоб `LV-role-pulse` | прогон: 33 роли, МЁРТВ: 0 |

Осталось владельцу/окну: компакция state.db (стоп gateway), `CATHEDRAL_BOT_TOKEN`, uncommitted в 3 проектах (не трогаем), зеркало на F2DB-14E5.
