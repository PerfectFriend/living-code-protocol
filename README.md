# living-code — мозг «Протокола Живого Кода»

Репозиторий оркестрации роя агентов LivingCode: скрипты, реестр кронов Hermes, протокол,
журнал, отчёты и экспорт конфига Hermes. Смысл существования — **пережить переустановку
Hermes и потерю диска**: всё, что нужно для запуска роя, лежит здесь, а не в `~/.hermes`.

## Состав

| Каталог | Что внутри |
|---|---|
| `orchestration/scripts/` | канонические скрипты роя; сюда указывает симлинк `~/.hermes/scripts` |
| `orchestration/wrappers/` | обёртки запуска агентов (fallback-цепочка моделей) |
| `orchestration/jobs/jobs.json` | реестр кронов Hermes (копия `~/.hermes/cron/jobs.json`) |
| `orchestration/hermes-config/` | `config.yaml` **без секретов** + `KEYS.md` (откуда брать ключи) |
| `orchestration/skills-export/` | 1162 скилла Hermes (ключи вычищены, см. `hermes-config/KEYS.md`) |
| `orchestration/bin/` | `install.sh`, `backup-config.sh`, `restore-config.sh`, `verify.sh`, `e2e-cycle.sh` |
| `orchestration/systemd/` | `livingcode-watchdog.service` — событийный драйвер роя |
| `protocol/` | РОЛИ.md, КОНТРАКТЫ_АГЕНТОВ.md, ПРАВИЛА_АУДИТА.md, КЛАССЫ_РАЗМОРОЗКИ.md |
| `runtime/` | journal, reports (548 отчётов), events, state, metrics |

## Модели (пины заданы явно на задачах крона)

| Роль | Проект | Модель (провайдер `nvidia`) |
|---|---|---|
| Coder 1 | superguard | `deepseek-ai/deepseek-v4.1-flash` |
| Coder 2 | elemental-life | `z-ai/glm-5.3` |
| Coder 3 | cybertarot | `moonshotai/kimi-k3` |
| Coder 4 | elemental-life-2 | `z-ai/glm-5.3-flash` |
| остальные роли | — | `deepseek-ai/deepseek-v4.1-flash` |

Карта — в `orchestration/models.yaml`.

## Laya — внешний судья типизированных решений

Внешний модуль, **НЕ входит в контекст Hermes** (контексты агентов 64к+, Laya принимает ≤8к).
Гейт осмысленности UI (5 осей + ship_decision), триаж находок, вердикт, скоринг топиков —
через `orchestration/scripts/laya_bridge.py`. Чекпоинт: `~/LivingCode/models/laya-multilingual`
(647M, 100+ языков вкл. русский), venv: `~/LivingCode/venvs/laya` (torch 2.14.0+cpu, laya 0.3.20).
Детали и уроки валидации: [LAYA.md](LAYA.md).

## Восстановление с нуля

```bash
git clone https://github.com/DarkPushkin/living-code ~/LivingCode/orchestration
bash ~/LivingCode/orchestration/bin/install.sh     # симлинк ~/.hermes/scripts + конфиг + скиллы
hermes auth add nvidia <NVIDIA_API_KEY>            # ключи в git не хранятся
bash ~/LivingCode/orchestration/bin/restore-config.sh   # кроны восстанавливаются в paused
hermes cron list                                   # 14 задач, все paused — включать поэтапно
```

## Бэкап

`orchestration/bin/backup-config.sh` (крон `LV-config-backup`, 03:30):
git push + rsync на внешний диск `/run/media/thomas/F2DB-14E5/hermes-config/`;
если диск не смонтирован — локальный архив в `~/LivingCode/backups/` (ротация 7 копий).

## Проекты роя

Живут в `~/LivingCode/Projects/*` — у каждого **свой** репозиторий
(`DarkPushkin/elemental-life`, `-elemental-life-2`, `cybertarot`, `superguard-livingcode`),
в этот репозиторий не входят.

`upstream` = `PerfectFriend/GodModeCoder` — старая история, доступ только на чтение.
