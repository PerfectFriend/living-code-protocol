# 🧬 EVOLUTION PLAN v2 — Протокол Живого Кода (2026-11-02)

**Создан:** 2026-11-02, после ревизии 01.11 (миграция модели протокола, оживление роя).
**Статус прошлого плана:** EVOLUTION_PLAN.md (баннеры, covid-эра) — архив. Этот план — актуальный.
**Принципы (не менять):** один запуск агента = один пункт плана = один завершённый цикл (код + тест + коммит); все отчёты на русском; межролевой контракт — машиночитаемые маркеры (`[TRIGGER_*]`, `[ART_DONE]`, `ВЕРДИКТ: <проект> — ГОРЯЧИЙ|ХОЛОДНЫЙ|ВЕРНУТЬ`); перед правкой живого скрипта — бэкап `.orig-<дата>`.

## Контекст: что произошло 01.11.2026

- Замер моделей nvidia: `minimax-m3.1-flash` висит 39–120с (за гранью stale-guard 60с) → **весь протокол стоял**. Живые: `nvidia/nemotron-3-ultra-550b-a55b` (≈1с, content непустой), `nemotron-3.5-lightning-30b-a3b` (3–9с), `mistral-large-4-1t-a52b` (6–12с). Мёртвые: glm-5.3-flash (95–115с), gpt-oss-20b/deepseek-v4.1-flash (таймаут), super-120b/4-340b/codestral/kimi-k2.6/nano (404/410).
- Миграция применена во всех 4 слоях синхронно: движок `living_code_agent_wrapper.py`, `check_roster.py`, 19 обёрток, `orchestration/hermes-config/config.yaml`; реестр кронов — 31 задание на ultra; minimax внесён в `HISTORICALLY_DEAD`.
- Создано недостающее задание **LV-coder-cybertarot-full** (`e66796ccbbb4`) + обёртка — 4-й проект (2-я версия CyberTarot) теперь в рое.
- Пуш: `PerfectFriend/living-code@main = 3940d0c` (ветка-страховка `backup-revizija-20261101`).
- Доказательство жизни: 02.11 отчёты кодеров elemental-life-2 (00:42) и cybertarot-full (00:20, 61/61 тестов, build success), художника (00:45), Профессора (01:01–01:37, 5 тем), Инквизитора (01:50, knowledge-graph 164→169 узлов).

## Фаза 0 — Закрепить успех (оператор + движок, до 02.11 12:00)

- [x] 2026-11-02 ~03:05: рестарт gateway выполнен владельцем. `errors.log` после рестарта: stale/unresponsive = 0 (единственный stale — старый, до миграции); видны только известные ворнинги (Copilot token, MarkdownV2, Telegram flood 429 → retry 900s).
- [ ] Офлайн-компакция `~/.hermes/state.db` (2.5GB) при остановленном gateway (`hermes sessions optimize-storage`); `auto_prune: 90` уже включён. **WAL снова растёт при работающем gateway (6.5MB к 03:07)** — компакция только в окно с остановленным gateway.
- [x] 2026-11-02: `hermes cron resume f9365e6513e5 --run-now` — elemental-life перезапущен (next run 02:09:51).
- [ ] Прогнать `check_roster.py --update` после любого изменения jobs.json; гейт rc=0.
- [ ] Зеркало orchestration на флешку F2DB-14E5 после ремоунта (сверка SHA).

## Фаза 1 — Медиаслой: художник и музыкант по заданию кодеров (неделя 1)

- [x] 2026-11-02: **Контракт заявок:** создан `agents/TASK_CONTRACT.md`, шаблоны `agents/templates/art-task.md` + `snd-task.md`, каталоги `tasks/` с README во всех 4 игровых проектах. Кодер пишет в `agents/journal.md` строку `[TRIGGER_ARTIST] <проект> | tasks/art-<ts>.md` (и `[TRIGGER_MUSICIAN] <проект> | tasks/snd-<ts>.md`); заявка — файл `Projects/<проект>/tasks/*.md` (тип, размеры/форматы, референсы/палитра, путь назначения `assets/…`, критерии приёмки). Роль помечает `.done` и отвечает `[ART_DONE] <файл>` / `[SND_DONE] <файл>`.
- [x] 2026-11-02: промпты `LV-artist` (004fdb156a82) и `LV-dj-musician` (a1efc19ab826) переписаны под v2-контракт (чтение заявки-файла, ui_gate по скриншоту, ebur128, `.done` + `[ART_DONE]`/`[SND_DONE]`); skills расширены (artist += make-interfaces-feel-better, popular-web-designs; musician += ffmpeg-audio-enhance); deliver=failure-deliver=`telegram:-1004431090317:252`. Шедулер перечитывает jobs.json каждый тик — применилось без рестарта. (`comfyui, canvas-design, frontend-design, make-interfaces-feel-better, popular-web-designs` — арт; `songwriting-and-ai-music` — звук); `deliver`/`failure-deliver` в telegram-топик.
- [~] 2026-11-02: **Гейты качества** прописаны в промптах и контракте (ui_gate :8731 по скриншоту, vision-фолбэк, ebur128 −14/−16 LUFS, ≤3 попытки). **Проверено: LV-artist отработал 02:32 уже с новым промптом** (ответ `[SILENT]` — file-based заявок пока нет, старые prose-триггеры новый контракт игнорирует). Остаётся: первая реальная заявка art-*.md → проверить вызов laya_bridge в отчёте.
- [ ] **Локальные генераторы:** ComfyUI (:8188) — venv не найден, checkpoint только sd15; Voicebox — Tauri-app, не сервер :7860. Пока фолбэк: piper ru_RU-ruslan-medium, XTTS v2 (`.venv-tts11`), ACE-Step на 780M.
- [x] 2026-11-02: **Nano Banana 2 прикручен**: `image_gen.provider: nous` + `image_gen.model: fal-ai/nano-banana-2` (каталог Hermes, ~3с, PNG, 1:1/16:9/9:16, edit до 14 референсов). **Блокер — деньги, не код:** Nous gateway отвечает HTTP 402 insufficient_funds (проверено tool-вызовом), OpenRouter-ключ тоже без кредитов (402, зато там есть `google/gemini-nano-banana-2.1` ~$0.03/картинка и `google/gemini-3-pro-image` ~$0.12). FAL_KEY отсутствует. Как только баланс появится на любом из трёх — работает без правок. Промпт LV-artist обновлён: image_generate первичный, 402 → фолбэк ComfyUI.
- [ ] Ночные роли `LV-night-artist`/`LV-night-musician` остаются на паузе до починки пути скрипта.

## Фаза 2 — Модельный слой (постоянно)

- [ ] Еженедельный probe nvidia (`probe_provider_models.py`, max_tokens ≥ 1024, 2–3 раунда + сквозная проверка через `hermes chat`): искать новые живые модели, особенно творческие/кодовые.
- [ ] При нахождении новой — миграция по 4-слойной процедуре (движок → check_roster → обёртки → реестр) с замером и смоук-тестом; старая модель → `HISTORICALLY_DEAD`.
- [ ] Держать primary = ultra; фолбэк-цепочка ultra → lightning → mistral-large.
- [ ] LV-model-sync держать включённым; следить, чтобы `orchestration/jobs/jobs.json` не расходился с live-реестром.

## Фаза 3 — Четыре игровых проекта (непрерывно, по циклам кодеров)

Проекты в рое: `elemental-life`, `elemental-life-2`, `cybertarot`, `cybertarot-full` (+ Project1–4, superguard, paranoidx — отдельные слоты).

- [ ] Каждый кодер ведёт свой `Projects/<p>/EVOLUTION_PLAN.md`: один пункт за запуск, чекбокс + дата + отчёт.
- [ ] Кодеры могут заказывать арт/звук через контракт Фазы 1; принимают артефакты и коммитят их в своём цикле.
- [ ] Владыка (LV-lord-of-code) продолжает hot/cold-вердикты с детерминированной строкой `ВЕРДИКТ:`; заморозка только при тесты ✓ и нет [СР].
- [ ] Аудитор — laya-триаж находок (🔴/🟡/💭), ui_gate для UI-изменений.

## Фаза 4 — Надёжность и эксплуатация (неделя 1–2)

- [x] 2026-11-02: **Доставка отчётов в топик 252 файлом (MEDIA), не текстом:** script-роли (24 задания) уже шлют MD через `hermes send --to telegram:-1004431090317:252 MEDIA:<файл>` из `living_code_agent_wrapper.py` (`deliver_role_digest`); prompt-роли (LV-artist, LV-dj-musician, LV-inquisitor, LV-supervisor) получили `deliver=failure-deliver=telegram:-1004431090317:252` + в промпты добавлен шаг «в конце вывода строка `MEDIA:<путь к отчёту>`» — шедулер по ней шлёт документ (send_document).
- [x] 2026-11-02: **Аудит «кто не шлёт»:** prompt-роли имели deliver=local (inquisitor/supervisor — исправлено); script-роли шлют сами, но 9 были disabled/умерли: перевзведены resume --run-now → lord-of-code, coder-superguard, producer, ui-gate (next 15:13), 4 проектных кодера отработали 12:10–12:50 (elemental-life и cybertarot снова rc 75 — см. ниже), paranoidx — recurring, plain resume. night-artist/night-musician так и disabled (Script not found с 18.08). key-rotation, Topic252-конвейер — работают.
- [x] 2026-11-02: **APK-экспорт:** `~/apkexport/` (старая папка владельца, 5 apk/361M на момент редизайна) — туда слиты все найденные сборки, итого 28 apk / 1.9G, имена `<project>-<имя>.apk` (стиль владельца); ошибочная `~/apkexpor` удалена. LV-producer копит свежие *.apk в `/home/thomas/apkexport/` после пуша (шаг 6 промпта).
- [ ] Доставка отчётов: следить за HTTP 429 у tg_send.py (видели 02.11 01:37 и 03:05 — «Flood control exceeded. Retry in 900s») — retry с backoff; отчёты-«файлы на диске» дублировать в telegram-топик.
- [ ] rc 75 / unknown outcome: движок не ретраит — ручной re-arm каждый цикл. **02.11: elemental-life (f9365e6513e5) и cybertarot (ecc3105fe44d) снова rc 75 на ultra (запуски 02:17 и 12:10)** — оба раза этот исход у этих двух заданий; elemental-life-2/cybertarot-full при этом чистые. Смотреть attempt-лог: возможно, конфликт session/binding у конкретных wrapper-скриптов.
- [ ] `LV-config-backup`, `LV-vault-sync`, `LV-graph-pulse-export` — держать зелёными; state.db/WAL — чекпоинт каждую ночь.
- [ ] Бэкапы: флешка + `backups/revize-*` в ~/.hermes; `.orig-<дата>` перед любой правкой живых скриптов.

## Фаза 5 — База знаний (непрерывно)

- [ ] Профессор — очередь Искателя по laya-score; 5 тем за слот; конспекты в Obsidian vault + `knowledge-base/` с wikilinks.
- [ ] Инквизитор — промоушен STUDIED → DEPLOYED в knowledge-graph.json; [KNOWLEDGE_BASE_UPDATED] в журнал.
- [ ] Взять в работу находки из свежих конспектов 02.11: AG-UI gateway-паттерн (decide→audit→act для tool calls), Harness² Propose-Probe-Compose для цикла Кодер→Аудитор, visual QA loop (Gamma) в UI-гейт, MoE-на-CPU для 780M.

## Метрики успеха плана

- ≥ 1 успешный цикл на каждый из 4 игровых проектов в сутки (отчёт в reports/ + коммит в проекте).
- 0 падений ролей по stale/unresponsive за сутки.
- 100% доставляемость отчётов в telegram (или явный retry в журнале).
- Все гейты (check_roster, py_compile, ui_gate для UI) зелёные после каждого цикла.

## Открытые вопросы владельцу

1. Поднимать ли ComfyUI/Voicebox как постоянные сервисы (память 780M) или только по夜ам?
2. Нужны ли cookies для agent-reach (X и соцсети) — открытый пункт из PLAN.md.
3. Лимиты nvidia (429 видели) — заводить второй ключ в пул или снижать частоту ролей?
