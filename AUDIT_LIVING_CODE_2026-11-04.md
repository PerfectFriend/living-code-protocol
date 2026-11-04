# Аудит Протокола Живого Кода — 04.11.2026

## 1. Структура работы
- **34 cron-задания** (реестр `~/.hermes/cron/jobs.json`), **33 роли** (`orchestration/roster.json`), все на модели `mistralai/mistral-large-4-1t-a52b` / провайдер `nvidia`. Исключение: `LV-role-pulse` — модель не задана (косметика).
- **Движок**: `orchestration/scripts/living_code_agent_wrapper.py` (симлинк `~/.hermes/scripts/`) — фолбэк-пул из одной живой пары, жёсткий бан `nemotron` (`sys.exit(3)` до API), whitelist пар, авто-ретрай rc=75, Evidence Gate, доставка отчётов.
- **Обёртки ролей**: `orchestration/scripts/wrappers/wrapper_*.sh` → промпты `wrappers/prompts/*.txt`. Слот-цепочки (кодер → аудитор → владыка → продюсер) триггерятся через `cron run`/`resume --run-now`.
- **Прочие скрипты**: `check_roster.py` (CI-гейт ростера), `evidence_gate.py` (валидация отчётов, N=0⇒отказ), `release_gate.py` (L2-приёмка), `lord_of_code.py` (HOT/COLD-маркеры), `condition_snapshot.py`, `meta_evolver.py`, `cycle_start_cron.py`, `topic252_to_textbook.py`, `media_contract.py` (без вызывающих — мёртвый код).

## 2. Состояние проектов (все коммиты 04.11.2026)
| Проект | Последний коммит | Изменения | Примечание |
|---|---|---|---|
| superguard | c5c51f7 — цикл 12531 | чисто | активен |
| elemental-life | bac85e5 — 10 циклов, smoke 10/10, 406 тестов | чисто | активен |
| elemental-life-2 | b593d22 — цикл 31, SSE-стриминг | чисто | активен (rc=75 изредка) |
| cybertarot | e3c1985 — Item 13 Burn Mechanics | чисто | активен |
| cybertarot-full | da87ffa — цикл 5, S4 | dirty=1 | активен |
| ParanoidX | 692ead6 — HTTP-тесты admin-хендлеров | чисто | активен |
| LivingCode-main_menu_ui-001 | 17.08.2026 | dirty=39 | заброшенная копия — кандидат на архивацию |

## 3. Индекс эффективности (executions.db, 927 завершённых прогонов)
- **Успех: 93.2%** (864 completed / 92 failed / 13 missed / 31 unknown).
- Надёжные роли: node-health 597/597, artist 11/11, musician 11/11, graph-pulse 5/5, cycle-start 5/5, key-rotation 37/39, vault-sync 37/39.
- Агентные слоты (медиана): professor 823 c (26/31), inquisitor 1393 c (16/20), searcher 1655 c (15/20), coder-project1 2165 c (5/6), coder-project2 2529 c (3/5).
- Проблемные: **super-supervisor 0/18** (все ошибки — смотреть `cron_incidents`), coder-elemental-life 0/4 и coder-elemental-life-2 0/3 (rc=75, нужен ручной resume — авто-ретрай в движке уже добавлен), role-pulse 1/4.
- Параллелизм: 3 одновременных воркера ≈ 390 МБ RAM, ~0% CPU (инференс удалённый).

## 4. Найдено и исправлено (04.11.2026)
**Причина дублей «professor»/«профессор»**: каждый слот давал 2–3 отчёта — (а) агент сам писал и слал свой MD (`professor-*.md`, 351 шт/7д), (б) движок досылал свой дайджест с русским slug (`профессор-*.md`, 67 шт), (в) движок рендерил PNG-превью через headless chromium (213 картинки). Searcher писал ~20 файлов за слот (395 шт/7д).
**Исправлено (коммит orchestration `e22cfab`, запушен origin+backup):**
1. PNG/HTML-генерация отчётов **полностью удалена** из движка (`_render_report_png`/`_report_html`). Существующие 216 png + 216 html убраны в `reports/_superseded/`.
2. Движок доставляет **ровно один MD**: агентский файл отчёта (приоритет), при его отсутствии — один дайджест. Свежие дубли роли автоматически убираются в `reports/_superseded/`.
3. В промпт каждой роли добавлен контракт: «ровно один файл, коротко (5–15 строк), по делу, только по-русски, сам не отправляй».
4. Из промптов профессора/искателя/аудитора **удалены шаги самостоятельной отправки** с инлайн-токеном бота в тексте (утечка секрета в git-истории — токен в промптах больше не фигурирует; рекомендуется ревокать старый через @BotFather).
5. Юнит-проверка выбора отчёта пройдена; `py_compile` движка — OK.

## 5. Остатки
- `super-supervisor` — 18 подряд ошибок, требует разбора лога.
- Инлайн-токен бота остаётся в git-истории промптов — ревок через @BotFather.
- `media_contract.py` — мёртвый код (никто не вызывает).
- `LivingCode-main_menu_ui-001` — заброшен с 39 несохранёнными файлами.
- Следующий VACUUM state.db соберёт ~224 МБ из freelist.
