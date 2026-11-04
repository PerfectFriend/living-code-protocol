# CATHEDRAL — Autonomous Code Machine

Полное техническое описание Протокола Живого Кода (Living Code Protocol), новый план эволюции и интеграция с GodModeCoder в единую концепцию **Cathedral — Autonomous Code Machine**, а также инструкции по максимально автоматическому клонированию всей рабочей среды на любой новый хост (Ubuntu / Windows).

---

## Часть I. Как работает Протокол Живого Кода

### 1. Концепция и философия

Протокол Живого Кода — автономная эволюционная экосистема разработки ПО. Четыре независимых проекта эволюционируют параллельно в 4-часовых циклах. Каждый проект проходит 10 под-циклов эволюции (evolve → test → debug → checkpoint commit), за которыми следует верификация Filter Overlord.

**Ключевая философия:** *«Идеальный код рождается в споре. Код, выживший 10 под-циклов с ≥95% покрытием тестами и нулевым количеством незакоммиченных изменений — FROZEN: идеален, больше никогда не трогается.»*

---

### 2. Архитектура и структура каталогов

```
/home/thomas/LivingCode/
├── Projects/                 # 4 активных проекта (свои git-репозитории)
│   ├── superguard/          # Проект 1: AI Surveillance / видеонаблюдение
│   ├── elemental-life/      # Проект 2: Life Simulation
│   ├── cybertarot/          # Проект 3: Magic / Art / Telegram / TON / Android
│   └── elemental-life-2/    # Проект 4: Extended Life Simulation (Python + Flutter)
├── Project1..4/             # Дополнительные проектные папки (memory, отчёты, планы)
├── CompleteProjects/        # Архив FROZEN-проектов (пусто, готово к заполнению)
├── artifacts/               # Эволюционные отчёты, filter-отчёты, баннеры
├── orchestration/           # Мозг роя (рабочая директория этого репозитория)
│   ├── scripts/             # Канонические скрипты роя (~/.hermes/scripts → symlink)
│   ├── wrappers/            # Обёртки запуска агентов с fallback-цепочкой моделей
│   ├── jobs/jobs.json       # Реестр кронов Hermes (копия ~/.hermes/cron/jobs.json)
│   ├── hermes-config/       # config.yaml без секретов + KEYS.md (откуда брать ключи)
│   ├── skills-export/       # 1162 скилла Hermes (ключи вычищены)
│   ├── bin/                 # install.sh, backup-config.sh, restore-config.sh, verify.sh
│   ├── systemd/             # systemd юнит watchdog роя
│   ├── protocol/            # РОЛИ.md, КОНТРАКТЫ_АГЕНТОВ.md, ПРАВИЛА_АУДИТА.md (план)
│   ├── runtime/             # journal, reports (548 отчётов), events, state, metrics
│   ├── knowledge-base/      # knowledge-graph.json (200 узлов, 195 deployed)
│   ├── models/              # laya-multilingual чекпоинт (647M)
│   ├── venvs/laya/          # venv для Laya AI (torch 2.14.0+cpu, laya 0.3.20)
│   └── LAYA.md              # Документация по внешнему судье Laya
├── agents/                  # journal.md — общий журнал триггеров и вердиктов
├── reports/                 # 548+ отчётов ролей (.md файлы)
├── keys/                    # Ключи шифрования (не в git)
├── state/                   # orchestrator_state.json
├── cache/                   # Model Registry кэш
├── PLAN.md                  # Текущий план развития
├── EVOLUTION_PLAN_v3.md     # План эволюции v3 (актуальный)
├── Living_Code_Protocol_Report.md  # Технический отчёт протокола (английский/русский)
└── Protokol_Zhivogo_Koda_Otchet.md # Технический отчёт протокола (русский)
```

---

### 3. Пять ролей конвейера «код → релиз»

| Роль | Назначение | Тип |
|------|-----------|-----|
| **LV-coder-<проект>** | Эволюция кода проекта: читает план → берет 1 пункт → реализует → l3_critic → коммит → триггер артиста/музыканта | Кодер |
| **LV-artist** | Графика/UI по v2-контракту заявок (`tasks/art-*.md`) | Художник |
| **LV-dj-musician** | Аудио по v2-контракту заявок (`tasks/snd-*.md`) | Музыкант |
| **LV-lord-of-code** | Вердикт `ГОРЯЧИЙ` / `ХОЛОДНЫЙ` / `ВЕРНУТЬ`; `ГОРЯЧИЙ` + `l3_critic stabilen` = триггер релиза | Аудитор / Владыка |
| **LV-producer** | Авто-релиз: тег `vX.Y.Z`, APK в `~/apkexport/`, отчёт `reports/release-*.md`, пуш тега | Продюсер |

Дополнительные роли:
- **LV-searcher** — поиск в вебе/X.com/Reddit (теперь через скиллы `x-browse` + `reddit-browse`)
- **LV-professor** — изучение, конспекты, приоритизация Учебника через Laya
- **LV-inquisitor** — аудит, триаж проблем, kritichno → немедленный фикс
- **LV-harness-opt** (бывший LV-supervisor) — Self-HPO: оптимизация `jobs.json` и промптов раз в сутки
- **LV-config-backup, LV-node-health, LV-model-sync** — инфраструктурное обслуживание

---

### 4. Evolution Engine (ядро эволюции)

Скрипт `evolution_engine.py` выполняет для каждого проекта:
1. **Маршрутизацию проекта** — по имени или номеру (1–4)
2. **Model Registry integration** — маршрутизация на оптимальную модель
3. **Цикл из 10 под-циклов**: evolve → test → debug → checkpoint commit
4. **Checkpoint-коммиты** на под-циклах 3, 6, 10
5. **Запуск тестов** — pytest с авто-созданием конфига
6. **Статический анализ** — Ruff + MyPy
7. **Git-операции** — init, commit, push в приватные GitHub-репозитории
8. **Генерация отчёта** — JSON с метриками за цикл

Модели (по приказу 24.10.2026):
- **Primary:** `nvidia/nemotron-3.5-super-vl-120b-a12b` (провайдер `nvidia`, ~1с ответ)
- **Fallback:** `mistralai/mistral-large-4-1t-a52b` (nvidia)
- **HISTORICALLY_DEAD:** `minimaxai/minimax-m3.1-flash`, `gpt-6.1-sol/agentrouter` и др.

---

### 5. Filter Overlord (верификация)

Классифицирует каждый проект после цикла:

| Классификация | Критерии | Исход |
|---------------|----------|-------|
| **FROZEN** | Summary есть + coverage ≥95% + LOC >100 + нет незакоммиченных изменений | Код идеален, больше не трогается |
| **READY** | Summary есть + coverage ≥80% + LOC >50 | Прошёл верификацию, готов к деплою |
| **ARCHIVED** | Нет summary, coverage <80%, или не соответствует критериям | Мёртв/сломан — в архив |

Второй проход для READY: полный pytest с покрытием, security scan (bandit), проверка TODO/FIXME в продакшн-коде.

---

### 6. Laya AI — внешний судья

**Laya** (`NandhaKishorM/laya`, 25.5k⭐, Apache 2.0) — неавторегрессивный System-1 движок типизированных решений за один forward pass (~33 мс). Не генерирует текст → не галлюцинирует.

Живёт как внешний судья вне контекста Hermes (агенты 64к+ токенов, Laya принимает ≤8к). Bridge-скрипт `laya_bridge.py` вытягивает компактный вопрос (head+tail ≤4000 симв.), возвращает крошечный JSON-вердикт.

**Режимы:**
- `ui_gate` — гейт осмысленности UI (5 осей + ship_decision)
- `triage` — триаж находки (категория, срочность, действие)
- `verdict` — вердикт стабильности кода (stabilen / rework_p)
- `score` — скоринг релевантности (требует `--state-context`)

**Интеграция:** Владыка, Аудитор, Искатель, Профессор, Инквизитор используют Laya как первый фильтр, не замену аудиту.

---

### 7. Hermes Gateway и доставка отчётов

Все отчёты ролей доставляются в Telegram-топик `-1004431090317:252` через **Cathedral Bot API** (curl, минуя Hermes-шлюз, который нельзя перезапускать изнутри).

**Правило владельца (23.10.2026):** отчёты кронов — только MD-файлами, текстовые отчёты запрещены. Отправка через `sendDocument`.

Токен Cathedral хранится в `~/.hermes/profiles/cathedral/.env` (строки 390, 550), не в git.

---

### 8. Проверки целостности

- **`check_roster.py`** — CI-гейт реестра ролей: каждая роль в `roster.json` существует в `jobs.json`, скрипт на диске, модель в белом списке протокола
- **`verify.sh`** — проверка здоровья реестра кронов: нет хардкод-путей Windows, скрипты существуют, symlink на `~/.hermes/scripts`
- **`l3_critic.py`** — независимый критик: `stabilen` / `regress` / `nuzhna_rabota`, вызывается кодером ПЕРЕД каждым коммитом
- **`laya_bridge.py verdict`** — детерминированный внешний суд перед заморозкой HOT→COLD

---

## Часть II. Cathedral — Autonomous Code Machine (единая концепция)

### 1. Видение

Cathedral — это Autonomous Code Machine: полнос цикл разработки от идеи до релиза без участия человека между циклами. Объединяет:

- **Living Code Protocol** — ядро эволюции, Filter Overlord, авто-релиз, база знаний
- **GodModeCoder** — бот-доставка отчётов, инквизиторский надзор, fallback-инфраструктура

Единая точка входа: Hermes Agent с профилем `cathedral`, все роли роя, все кроны, все отчёты в один Telegram-топик 252.

### 2. Компонентная карта Cathedral

```
Cathedral Autonomous Code Machine
├── Hermes Agent (профиль cathedral)
│   ├── cron scheduler (30+ задач, nemotron-3.5-super-vl-120b-a12b)
│   ├── skills (x-browse, reddit-browse, laya, graphify, ...)
│   └── Telegram Bot API (Cathedral bot, топик 252)
├── Living Code Protocol
│   ├── Evolution Engine (4 проекта × 10 под-циклов × 4-ч циклы)
│   ├── Filter Overlord (FROZEN/READY/ARCHIVED)
│   ├── Model Registry (nvidia provider, белый список)
│   └── Laya AI (внешний судья, CPU/iGPU)
├── Agent Swarm
│   ├── LV-coder-* (4 проектных кодера)
│   ├── LV-artist, LV-dj-musician (v2-контракт задач)
│   ├── LV-lord-of-code (вердикт ГОРЯЧИЙ/ХОЛОДНЫЙ)
│   ├── LV-producer (авто-релиз vX.Y.Z, APK в ~/apkexport/)
│   ├── LV-searcher, LV-professor, LV-inquisitor (знания, аудит)
│   └── LV-harness-opt (Self-HPO, оптимизация_jobs.json)
├── Projects
│   ├── superguard (AI Surveillance)
│   ├── elemental-life (Life Simulation)
│   ├── cybertarot (Magic/Art/Telegram/TON)
│   └── elemental-life-2 (Extended Life Simulation, Python+Flutter)
└── Infrastructure
    ├── ~/.hermes/scripts → symlink к orchestration/scripts
    ├── ~/apkexport/ (28 APK, 1.9 GB)
    ├── /run/media/thomas/F2DB-14E5/ (бэкап, flash drive)
    └── CompleteProjects/ (архив FROZEN)
```

### 3. Поток данных (Cathedral flow)

```
Журнал agents/journal.md
    │
    ├─[TRIGGER_LORD]→ LV-lord-of-code → ВЕРДИКТ: ГОРЯЧИЙ/ХОЛОДНЫЙ/ВЕРНУТЬ
    │                        │
    │                        ├─ ГОРЯЧИЙ + l3_critic stabilen → [TRIGGER_PRODUCER]
    │                        │                                 │
    │                        │                                 ▼
    │                        │                          LV-producer
    │                        │                          → тег vX.Y.Z
    │                        │                          → APK в ~/apkexport/
    │                        │                          → отчёт в топик 252
    │                        │                          → пуш тега в GitHub
    │                        │
    │                        └─ ХОЛОДНЫЙ → cycle_close.py (гейты холодности)
    │                                                       → Releases/<project>
    │
    ├─[TRIGGER_ARTIST]→ LV-artist → tasks/art-*.md → .done → журнал
    ├─[TRIGGER_MUSICIAN]→ LV-dj-musician → tasks/snd-*.md → .done → журнал
    │
    └─[TRIGGER_PRODUCER]→ LV-producer → авто-релиз (если гейты зелёные)
```

### 4. Отличия от чистого Living Code

| Аспект | Living Code (исходный) | Cathedral (интегрированный) |
|--------|----------------------|----------------------------|
| Доставка отчётов | Hermes-шлюз (нестабилен) | Cathedral Bot API (curl, прямая) |
| Поиск X.com/Reddit | agent-reach (не работает) | Скиллы `x-browse` + `reddit-browse` (web_search + Jina/web_extract) |
| Эволюция протокола | Статические скрипты | Self-HPO + A-Evolve (3-слойная) |
| Релиз | Ручной тег | Авто-релиз по вердикту Лорда |
| База знаний | Obsidian Vault | knowledge-graph.json + Graphify |
| Внешний судья | Laya (частично) | Laya + l3_critic (все коммиты) |

---

## Часть III. Новый план эволюции Cathedral (v4)

### Фаза 0 — Фундамент и закаливание (неделя 1)

| Задача | Статус | Описание |
|--------|--------|----------|
| ✅ Модель на nemotron-3.5-super-vl-120b-a12b | Готово | Все 30 кронов переведены, rc=75 устранён |
| ✅ Доступ X.com без логина | Готово | Скилл `x-browse` (web_search site:x.com + Jina Reader) |
| ✅ Доступ Reddit без логина | Готово | Скилл `reddit-browse` (web_search site:reddit.com + web_extract) |
| ✅ Промпт Searcher обновлён | Готово | Убраны жалобы, добавлены рабочие цепочки |
| 🔧 Пути Windows → Linux | В плане | Заменить `C:/` на `/home/thomas/` во всех скриптах |
| 🔧 Отсутствующий wrapper Project 3 | В плане | Создать `evolution_elemental_life_2_cron.py` |
| 🔧 Super-Supervisor | В плане | 1-часовая пост-верификация + release tagging |

### Фаза 1 — Self-HPO циклharness (H-step ↔ P-step)

| Задача | Статус | Описание |
|--------|--------|----------|
| H-step | Планируется | `LV-harness-opt` раз в сутки оптимизирует `jobs.json` + промпты на основе метрик P-step |
| P-step | Планируется | Кодер/художник/музыкант работают по текущему промпту; результат фиксируется; следующий слот читает предыдущий отчёт |
| Гейт перехода | Планируется | 0 новых stale/unresponsive за сутки, все 4 проектных крона зелёные, ≥1 релизный артефакт |

### Фаза 2 — A-Evolve: 3-слойная эволюция протокола

| Слой | Статус | Описание |
|------|--------|----------|
| Layer 1 — Task-harness | ✅ Готово | `jobs.json`, `config.yaml`, промпты ролей, шаблоны `agents/templates/` — под версионным контролем |
| Layer 2 — Evolver | ✅ Готово | `living_code_agent_wrapper.py` + `check_roster.py` + шедулер |
| Layer 3 — Meta-evolver | Планируется | Эволюция самого кода эволюции (`wrapper.py`, `cycle_close.py`, `l3_critic.py`). Выход: PR в `orchestration` + ревью Лорда |

### Фаза 3 — Конвейер «код → релиз» (авто-выпуск изделий)

| Задача | Статус | Описание |
|--------|--------|----------|
| Вердикт Лорда → триггер релиза | ✅ Готово | `ВЕРДИКТ: ГОРЯЧИЙ` + `l3_critic stabilen` = авто-релиз |
| Release скрипт | Планируется | `release_project.py`: тег `vX.Y.Z`, APK в `~/apkexport/`, отчёт, пуш тега |
| APK-экспорт | ✅ Готово | Продюсер копирует APK в `~/apkexport/` |
| Чек-лист релиза | Планируется | Код холодный, нет `[СР]`, `check_roster` rc=0, ui_gate пройден, ассеты закоммичены |

### Фаза 4 — Визуализация и граф знаний

| Задача | Статус | Описание |
|--------|--------|----------|
| Graphify установлен | ✅ Готово | 0.9.97, граф elemental-life-2: 798 узлов / 1413 рёбер / 65 сообществ |
| Граф пульса | Планируется | `LV-graph-pulse-export` обновляет `knowledge-graph.json` после каждого цикла |
| Локальный Graphify MCP | Планируется | `graphify <path> --mcp` как локальный MCP-сервер для агентов |

### Фаза 5 — Мульти-агентный рой (Kimi K3 идея)

| Задача | Статус | Описание |
|--------|--------|----------|
| Суб-агенты по темам | Планируется | UI, тесты, backend, ассеты по PARL-масштабированию |
| HUDDLE-синхронизация | Планируется | Через общий `journal.md` проекта |

### Метрики успеха v4

1. 4 проектных крона зелёные (0 rc=75, 0 stale) 3 суток подряд
2. ≥ 1 релизный тег (vX.Y.Z) с APK в `~/apkexport/` на каждый проект в неделю
3. 0 ручных вмешательств владельца между циклами (кроме компакта `state.db`)
4. knowledge-graph растёт (+10% узлов в неделю), deployed = 100%
5. `l3_critic` вердикт `stabilen` перед каждым коммитом кодера

---

## Часть IV. Руководство по клонированию среды на новый хост

### 0. Предпосылки

| Компонент | Ubuntu | Windows |
|-----------|--------|---------|
| ОС | Ubuntu 22.04+ / 24.04 | Windows 10/11 + WSL2 (рекомендуется) или нативно |
| Python | 3.9–3.14 (через `uv`) | Python 3.9+ (через `uv` или 공식 установщик) |
| Git | `apt install git` | `git-scm.com` |
| Hermes | Собран из исходников ( store-python + bootstrap ) | Hermes desktop app (Electron) |
| Chrome (для agent-browser) | Chrome for Testing + Xvfb | Chrome +远程 debugging |
| Node.js | Для `agent-browser` CLI | Для `agent-browser` CLI |
| Rust/Cargo | Для NeXXus/Tauri (опционально) | Для NeXXus/Tauri (опционально) |
| Диск | `~/build/` с предустановленным тулчейном | `%USERPROFILE%\build` |

**Важно:** Всё, что нужно для запуска роя, лежит в `~/LivingCode/orchestration`, а не в `~/.hermes`. Это позволяет пережить переустановку Hermes и потерю диска.

---

### 1. Ubuntu — пошаговое клонирование

#### Шаг 1. Установка базового тулчейна

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget build-essential python3-pip python3-venv

# Установка uv (универсальный instalер Python)
curl -LsSf https://astral.sh/uv/install.sh | sh
export PATH="$HOME/.local/bin:$PATH"

# Установка múltiпльных версий Python (как в ~/build)
uv python install 3.9 3.10 3.11 3.12 3.13 3.14

# Установка Node.js (для agent-browser)
curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
sudo apt-get install -y nodejs

# Установка Rust (для NeXXus/Tauri, опционально)
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
source $HOME/.cargo/env
```

#### Шаг 2. Клонирование репозитория оркестрации

```bash
# Клонируем основной репозиторий (приватный, нужен токен GitHub)
git clone https://github.com/DarkPushkin/living-code ~/LivingCode/orchestration
cd ~/LivingCode/orchestration

# Или, если репозиторий недоступен — использовать локальный бэкап с флешки:
# cp -r /run/media/thomas/F2DB-14E5/backups/home_thomas/LivingCode ~/LivingCode
```

#### Шаг 3. Установка Hermes

```bash
# Hermes устанавливается отдельно (desktop app или CLI)
# После установки проверить:
hermes --version
```

#### Шаг 4. Восстановление конфига из репозитория

```bash
cd ~/LivingCode/orchestration
bash bin/restore-config.sh
```

Что делает скрипт:
1. Копирует скиллы из `skills-export/` в `~/.hermes/skills/`
2. Копирует `config.yaml` из `hermes-config/` в `~/.hermes/`
3. Восстанавливает `jobs.json` в `~/.hermes/cron/` (все задачи на паузе)
4. Создаёт симлинк `~/.hermes/scripts → ~/LivingCode/orchestration/scripts`

#### Шаг 5. Добавление API-ключей (КРАСНАЯ ЛИНИЯ — ключи не в git)

Ключи хранятся вне репозитория. Источники:
- `~/LLM-API-KEYS.md` (внешний носитель)
- Бэкап на внешнем диске `/run/media/thomas/F2DB-14E5/`

```bash
hermes auth add nvidia <NVIDIA_API_KEY>
hermes auth add openrouter <OPENROUTER_API_KEY>  # если нужно
hermes auth add telegram <TELEGRAM_BOT_TOKEN>     # Cathedral бот
hermes auth list
```

#### Шаг 6. Установка Laya AI (внешний судья)

```bash
cd ~/LivingCode/orchestration
bash bin/install-laya.sh
```

Или вручную:
```bash
uv venv -p 3.12 ~/LivingCode/venvs/laya
uv pip install -p ~/LivingCode/venvs/laya/bin/python --index-url https://download.pytorch.org/whl/cpu torch
uv pip install -p ~/LivingCode/venvs/laya/bin/python "laya[serve,onnx]"
~/LivingCode/venvs/laya/bin/hf download convaiinnovations/laya-multilingual \
  --local-dir ~/LivingCode/models/laya-multilingual
```

#### Шаг 7. Настройка Chrome для agent-browser (доступ к X.com/Reddit)

```bash
# Установка Chrome for Testing
wget https://storage.googleapis.com/chrome-for-testing-public/156.0.8078.47/linux64/chrome-linux64.zip
unzip chrome-linux64.zip -d ~/build/chrome/

# Для доступа к X.com нужен залогиненный профиль.
# Вариант A: Запустить Chrome с remote debugging:
~/build/chrome/chrome-linux64/chrome --headless=new --remote-debugging-port=9222 \
  --remote-allow-origins=* --user-data-dir=~/.config/google-chrome/Default --no-sandbox

# Проверить:
curl -s http://localhost:9222/json/version

# Установить agent-browser CLI:
npm install -g agent-browser

# Для входа в X.com (требуется один раз вручную):
agent-browser --headed open "https://x.com/login"
```

**Важно:** Куки и сессии пользователя импортировать запрещено (красная линия безопасности). Доступ к X.com возможен только через:
1. `web_search site:x.com` + `curl r.jina.ai/<URL>` (публичный контент)
2. `agent-browser` с залогиненным профилем на пользовательской машине

#### Шаг 8. Проверка целостности

```bash
cd ~/LivingCode/orchestration
bash bin/verify.sh
```

Должно показать: "нет проблем", symlink OK.

#### Шаг 9. Запуск кронов поэтапно

```bash
# Все задачи после restore-config на паузе. Включать поэтапно:
hermes cron list

# Включить критические сначала:
hermes cron enable LV-config-backup
hermes cron enable LV-node-health
hermes cron enable LV-model-sync
hermes cron enable LV-searcher

# Затем проектных кодеров:
hermes cron enable LV-coder-superguard
hermes cron enable LV-coder-elemental-life
hermes cron enable LV-coder-cybertarot
hermes cron enable LV-coder-elemental-life-2

# И остальные:
hermes cron enable LV-lord-of-code
hermes cron enable LV-producer
hermes cron enable LV-artist
hermes cron enable LV-dj-musician
```

#### Шаг 10. Финальная верификация

```bash
check_roster.py --update      # должен показать rc=0, 0 ошибок
hermes cron status            # все активные задачи ok
ls ~/apkexport/               # папка для APK (создать если нет)
mkdir -p ~/apkexport
```

---

### 2. Windows — пошаговое клонирование

#### Шаг 1. Установка WSL2 (рекомендуемый путь)

```powershell
# В PowerShell от имени администратора:
wsl --install
# Перезагрузка компьютера
```

После перезагрузки войти в Ubuntu из WSL2 и следовать инструкции для Ubuntu (раздел 1).

#### Шаг 2. Нативная установка (альтернатива, без WSL2)

```powershell
# Установка Python
winget install Python.Python.3.12

# Установка uv
powershell -c "irm https://astral.sh/uv/install.ps1 | iex"

# Установка Git
winget install Git.Git

# Установка Node.js
winget install OpenJS.NodeJS.LTS

# Установка Chrome
winget install Google.Chrome

# Установка Rust
winget install Rustlang.Rust
```

#### Шаг 3. Клонирование репозитория

```powershell
git clone https://github.com/DarkPushkin/living-code $env:USERPROFILE\LivingCode\orchestration
cd $env:USERPROFILE\LivingCode\orchestration
```

**Важное отличие:** Пути в скриптах жёстко заданы как `/home/thomas/...`. На Windows нужно либо:
- Использовать WSL2 (пути `/home/thomas/` работают естественно)
- Либо создать симлинки/переменные окружения для маппинга:
  ```powershell
  $env:HOME = "$env:USERPROFILE"
  New-Item -ItemType SymbolicLink -Path "/home/thomas" -Target "$env:USERPROFILE"  # требует прав администратора и режима разработчика
  ```

#### Шаг 4. Установка Hermes на Windows

Hermes Desktop App устанавливается через инсталлятор. После установки:
- Профиль `cathedral` создаётся в `%USERPROFILE%\.hermes\profiles\cathedral\`
- Ключи добавляются через `hermes auth add`

#### Шаг 5. Восстановление конфига

```powershell
# Адаптированные пути для Windows (через WSL2 предпочтительнее)
# Скрипты bin/restore-config.sh требуют bash — использовать WSL2 или Git Bash
bash bin/restore-config.sh
```

---

### 3. Чек-лист после клонирования (любой хост)

```
[ ] Hermes установлен и hermes --version работает
[ ] ~/.hermes/scripts → symlink на orchestration/scripts
[ ] ~/.hermes/cron/jobs.json восстановлен (все на паузе)
[ ] ~/.hermes/config.yaml скопирован из hermes-config/
[ ] API-ключи добавлены: hermes auth list показывает nvidia и др.
[ ] Laya venv установлен: ~/LivingCode/venvs/laya/bin/python работает
[ ] check_roster.py --update → rc=0, 0 ошибок
[ ] verify.sh → "нет проблем"
[ ] ~/apkexport/ существует
[ ] Chrome с --remote-debugging-port=9222 запущен (для agent-browser)
[ ] agent-browser CLI установлен (npm install -g agent-browser)
[ ] Кроны включены поэтапно, начиная с инфраструктурных
[ ] Первый отчёт Searcher доставлен в топик 252 через Cathedral Bot API
[ ] Telegram тест: hermes send --profile cathedral --to telegram:-1004431090317:252 "Тест" → sent (exit 0)
```

---

### 4. Бэкап и восстановление

Автоматический бэкап крона `LV-config-backup` (03:30):
- `git push` в origin (PerfectFriend/NeXXus-Node)
- `rsync` на внешний диск `/run/media/thomas/F2DB-14E5/hermes-config/`
- Если диск не смонтирован — локальный архив в `~/LivingCode/backups/` (ротация 7 копий)

Ручное восстановление с флешки:
```bash
cp -r /run/media/thomas/F2DB-14E5/backups/home_thomas/LivingCode ~/LivingCode
cp -r /run/media/thomas/F2DB-14E5/backups/home_thomas/.hermes ~/.hermes
```

---

## Часть V. Полный набор инструкций по запуску (краткая справка)

### Ежедневная эксплуатация Cathedral

```bash
# 1. Проверить состояние роя
hermes cron status
check_roster.py --update

# 2. Просмотреть последние отчёты
ls -lt ~/LivingCode/reports/ | head -10

# 3. Принудительный запуск роли (если нужен вне расписания)
hermes cron run <job_id>

# 4. Поиск новостей IT/AI (Searcher)
web_search query="site:x.com autonomous AI agent"
web_search query="site:reddit.com AI agent 2026"

# 5. Чтение поста X.com
curl -s "https://r.jina.ai/https://x.com/<username>/status/<id>"

# 6. Чтение поста Reddit
web_extract "https://www.reddit.com/r/<subreddit>/comments/<id>/"

# 7. Проверка вердикта лaya
echo "<описание>" | ~/LivingCode/orchestration/scripts/laya_bridge.py verdict

# 8. L3 критик перед коммитом
python3 ~/LivingCode/orchestration/scripts/l3_critic.py --project <path> --deliverable "<что>" --criteria '{"test_command":"pytest -q"}'
```

---

## Заключение

Cathedral — Autonomous Code Machine — это завершённая концепция автономной разработки ПО, в которой:

1. **Living Code Protocol** обеспечивает эволюцию кода, верификацию и авто-релиз
2. **GodModeCoder** обеспечивает надёжную доставку отчётов через Cathedral Bot API
3. **x-browse + reddit-browse** обеспечивают доступ к соцсетям без логина и кук
4. **Laya AI + l3_critic** обеспечивают независимую верификацию каждого коммита
5. **Клонирование среды** документировано для Ubuntu и Windows, позволяя развернуть идентичную рабочую среду на любом новом хосте за один сеанс

Система готова к полной автономной работе с нулевым участием владельца между циклами.

---

*Документ создан Hermes Agent на основе реального состояния репозитория /home/thomas/LivingCode (состояние на 04.11.2026).*

*Версия документа: 1.0 (Cathedral — Autonomous Code Machine)*