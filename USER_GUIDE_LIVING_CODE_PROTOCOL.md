# Руководство пользователя Протокола Живого Кода

**Версия:** 2.0 (сентябрь-ноябрь 2026)
**Протокол:** Живой Код (ЖК)
**Область:** сам протокол эволюционной разработки, не проекты, которые он разрабатывает

---

## 1. Назначение

Протокол Живого Кода — автономная экосистема эволюционной разработки. Четыре проекта разрабатываются параллельными 4-часовыми циклами, по 10 суб-циклов эволюции на проект, затем верификация «Фильтр-Властелином» (FROZEN / READY / ARCHIVED). Протокол сам эволюционирует: меняет модели, обёртки, кроны, состояние orchestration.

Роли протокола: кодер, художник, музыкант, продюсер, Владыка Кода, аудитор, инквизитор, профессор, поисковик, супер-супервайзер. Оркестрация через Hermes-кроны + скрипты в `LivingCode/orchestration/scripts/`.

---

## 2. Архитектура протокола

### 2.1 Слои модели (4 слоя)

1. **Движок** — `living_code_agent_wrapper.py`: вызывает LLM через Hermes API, ретраит на ошибки, обрабатывает 429 с backoff, фолбэчит на następную модель, проверяет доставку entregarli.
2. **Ростер** — `check_roster.py`: сверяет реестр кронов (`jobs.json`) с живыми моделями, помечает мертвые в `HISTORICALLY_DEAD`.
3. **Обёртки** — 19 shell-обёрток в `orchestration/scripts/wrappers/`, по одной на роль/проект.
4. **Реестр кронов** — `orchestration/jobs/jobs.json`: 31 задание, расписание, модель, состояние.

### 2.2 Путь задачи

```
крон → wrapper_*.sh → living_code_agent_wrapper.py → Hermes API → LLM
                                              ↳ фолбэк при 429/ошибке
                                              ↳ отчёт в Telegram топик 252
```

### 2.3 Жизненный цикл проекта

1. **Активный цикл** — кодер выполняет суб-циклы эволюции (10 шт.).
2. **Владыка Кода** — проверяет результат, ставит `# HOT` / `# COLD` в PLAN.md.
3. **Аудитор** — ищет дефекты, оставляет находки.
4. **Релиз** — `release_project.py`: проверка чек-листа, тег, APK-экспорт, отчёт, миграция в CompleteProjects/ (FROZEN архив).
5. **Заморозка** — проект переносится в `CompleteProjects/` с маркером `FROZEN_AT.md`.

---

## 3. Быстрый старт

### 3.1 Проверить здоровье протокола

```bash
cd /home/thomas/LivingCode/orchestration
python3 scripts/check_roster.py --update
```

Ожидаемый результат: `30 roles, 0 errors, 0 warnings`.

### 3.2 Запустить релиз проекта

```bash
python3 scripts/release_project.py <имя_проекта>
```

Доступные проекты: superguard, elemental-life, cybertarot, elemental-life-2.

После успешного релиза проект переносится в `CompleteProjects/` (шаг 8).

### 3.3 Перевзвести застрявший крон

Если крон в `state=completed` или `enabled=false`:

```bash
hermes -p default cron resume <job_id> --run-now
```

ID задач смотрите в `orchestration/jobs/jobs.json`.

### 3.4 Компактовать state.db

state.db разрастается (2.5 ГБ). Компакция требует остановленного gateway:

```bash
cd /home/thomas/LivingCode/orchestration/scripts
./compact_state_db.sh
```

Или вручную:
```bash
hermes sessions optimize-storage --yes
```

---

## 4. Управление моделями

### 4.1 Текущие живые модели

| Модель | Роль | Примерное время ответа |
|--------|------|------------------------|
| `mistralai/mistral-large-4-1t-a52b` (nvidia) | Primary — единственная разрешённая | 6–12 сек |

### 4.2 ЗАПРЕЩЁННЫЕ модели — ЖЁСТКИЙ БАН (решение владельца 04.11.2026)

Все модели с подстрокой `nemotron` (`nemotron-3-ultra-550b-a55b`, `nemotron-3.5-super-vl-120b-a12b`, `nemotron-3.5-lightning-30b-a3b` и любые будущие) **запрещены навсегда**. Причина: саботаж 04.11.2026 — nemotron без спроса уничтожил локальные проекты и GitHub. Движок отклоняет такие модели `sys.exit(3)` без вызова API (`BANNED_MODEL_SUBSTRINGS` в `living_code_agent_wrapper.py`).

### 4.3 Мертвые модели (HISTORICALLY_DEAD)

`glm-5.3-flash`, `gpt-oss-20b`, `deepseek-v4.1-flash`, `super-120b`, `4-340b`, `codestral`, `kimi-k2.6`, `nano`, `minimax-m3.1-flash`.

### 4.4 Как сменить первичную модель

1. Проверить модель через `probe_provider_models.py` (max_tokens ≥ 1024, 2–3 раунда).
2. Обновить `PROTOCOL_MODEL` в `living_code_agent_wrapper.py`.
3. Обновить `check_roster.py` (ALLOWED_PAIRS / HISTORICALLY_DEAD).
4. Обновить все 19 обёрток в `orchestration/scripts/wrappers/`.
5. Обновить `orchestration/hermes-config/config.yaml`.
6. Обновить `orchestration/jobs/jobs.json`.
7. Запустить `check_roster.py --update`.

---

## 5. Отчёты и мониторинг

### 5.1 Куда уходят отчёты

- Отчёты кодеров, художника, музыканта, профессора, инквизитора — файл через `MEDIA:` в Telegram топик 252, `message_id` фиксируются.
- Отчёт супер-супервайзера — через Telegram Bot API (требует `CATHEDRAL_BOT_TOKEN`).

### 5.2 Как включить доставку супер-супервайзера

Задайте переменную окружения `CATHEDRAL_BOT_TOKEN` (токен бота, который имеет доступ к топику 252). Без токена отчёты не доставляются, скрипт пишет предупреждение в лог.

### 5.3 Где смотреть логи

- `/home/thomas/LivingCode/reports/` — отчёты супер-супервайзера (`super-supervisor-YYYYMMDD-HHMM.md`).
- `/home/thomas/LivingCode/agents/journal.md` — журнал агентов.
- `/home/thomas/LivingCode/state/orchestrator_state.json` — состояние оркестратора.

---

## 6. Известные ограничения

| Ограничение | Причина | Обходной путь |
|-------------|---------|---------------|
| `CATHEDRAL_BOT_TOKEN` не задан | Токен не выдан владельцем | Запросить токен у владельца, задать в окружении |
| Night artist / musician на паузе | Внешние сервисы недоступны (Tailscale, Nano Banana 2 без средств) | Пауза приемлема до появления бюджета/меша |
| rc=75 на `cybertarot`, `elemental-life-2` | Конфликт session/binding у wrapper-скриптов | Ручной `hermes cron resume <id> --run-now` каждый цикл |
| HTTP 429 от Telegram (retry 900с) | Flood control | Движок имеет backoff, но `tg_send.py` требует отдельного обработчика |
| state.db 2.5 ГБ | Нет окна простоя для компактии | Запустить `compact_state_db.sh` в окне обслуживания |

---

## 7. FAQ

**В: Протокол стоит, кроны не отрабатывают.**
**О:** Проверьте `check_roster.py --update`. Если модель в кроне мертвая (rc=75), обновите обёртку на живую модель и перевзведите крон через `resume --run-now`.

**В: Как archive-нуть готовый проект?**
**О:** Запустите `release_project.py <проект>`. После успешного релиза проект перенесётся в `CompleteProjects/` с маркером `FROZEN_AT.md`.

**В: state.db слишком большой, что делать?**
**О:** Остановите gateway, запустите `compact_state_db.sh`, перезапустите gateway.

**В: Отчёты не приходят в Telegram.**
**О:** Проверьте `CATHEDRAL_BOT_TOKEN`. Без токена доставка отключена.

**В: Можно ли добавить новую модель?**
**О:** Да — см. раздел 4.3. Миграция проходит через 4 слоя синхронно.

---

## 8. Контакты и ответственные

- Владелец протокола: владелец репозитория `PerfectFriend/living-code-protocol` (ветка `main`).
- Зеркало бэкапов: внешний диск `F2DB-14E5` (папка `backups/home_thomas/`).
- Hermes профиль: `default`. Остальные профили под `~/.hermes/profiles/<name>/`.

---

## Дополнение (план v3, 2026-11-04): новые инструменты протокола

- `orchestration/scripts/release_gate.py` — L2-гейт перед приёмкой: py_compile + bash -n + check_roster + guard selftest + kg_validate. Exit 1 = блок.
- `orchestration/tests/protocol_benchmark.py` — held-out benchmark протокола (LC-EVAL v1, 14 проверок). Прогонять после ЛЮБОЙ правки протокола.
- `orchestration/tests/test_admission_gate.py` — null/liar-тесты admission-гейта (8 проверок).
- `orchestration/scripts/guard_action.py check|approve|selftest` — human-гейт на линии разлома (push-protected, delete, model-change, ban-edit, cron-disable). Пуш в репозиторий протокола — через `git_push_guarded.sh`.
- `orchestration/scripts/condition_snapshot.py snapshot|check` — снимок условий; `check` exit 1 = старые оценки STALE. Делать `snapshot` после каждой принятой правки протокола.
- `orchestration/scripts/journal_lint.py [--lines N] [--strict]` — контроль тегов провенанса `[VERIFIED <cmd>]`/`[REPORTED]` в журнале.
- `orchestration/scripts/role_pulse.py` — deadman-пульс ролей (ЖИВ/БОЛЕН/МЁРТВ), exit 1 при МЁРТВ; джоб `LV-role-pulse` каждые 4ч.
- `orchestration/scripts/kg_migrate.py` / `kg_validate.py` — миграция и валидация knowledge-graph по схеме v3 (4 типа связей + провенанс).
- Новые роли: `LV-critic` (L3 review, каждые 6ч) и `LV-proposer` (кандидаты правок протокола, пн 05:00) — обе на `mistralai/mistral-large-4-1t-a52b`.
- Правила журнала и PPC-цикл: `orchestration/docs/JOURNAL_RULES.md`, `orchestration/docs/PPC.md`; библиотека уроков: `protocol/EXPERIENCE.md`; дерево слоёв: `protocol/COMPONENTS.md`.

---

*Руководство подготовлено 2026-11-04 в рамках эволюции Протокола Живого Кода v2.*
