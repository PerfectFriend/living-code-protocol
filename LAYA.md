# Laya AI — внешний модуль Живого Кода

**Laya** ([NandhaKishorM/laya](https://github.com/NandhaKishorM/laya), 25.5k⭐, Apache 2.0) —
неавтогрессивный System-1 движок типизированных решений: choice / score / yes-no-вероятность
над любым текстом за один forward pass (~33 мс). Не генерирует текст → не галлюцинирует.

## Почему внешний модуль

Контексты агентов Живого Кода — 64к+ токенов; Laya принимает ≤8к (рабочая зона точности —
до ~4000 токенов). Подключить напрямую в Hermes нельзя. Поэтому Laya живёт как **внешний
судья**: агент дёргает bridge-скрипт, bridge вытягивает из большого входа компактный вопрос
(head+tail ≤4000 симв.), Laya судит, назад летит крошечный JSON-вердикт (сотни байт).
Большие тексты никогда не входят в контекст Hermes-процесса.

## Установка (узел totomoto)

- venv: `~/LivingCode/venvs/laya` (Python 3.12, torch 2.14.0+cpu, laya 0.3.20 `[serve,onnx]`)
- чекпоинт: `~/LivingCode/models/laya-multilingual` (647M, mmBERT 322M, 100+ языков вкл. русский)
- bridge: `~/LivingCode/orchestration/scripts/laya_bridge.py` (в git, симлинк `~/.hermes/scripts`)

Восстановление с нуля:
```bash
uv venv -p 3.12 ~/LivingCode/venvs/laya
uv pip install -p ~/LivingCode/venvs/laya/bin/python --index-url https://download.pytorch.org/whl/cpu torch
uv pip install -p ~/LivingCode/venvs/laya/bin/python "laya[serve,onnx]"
~/LivingCode/venvs/laya/bin/hf download convaiinnovations/laya-multilingual \
  --local-dir ~/LivingCode/models/laya-multilingual
```
Примечание: в huggingface_hub 1.x CLI — это бинарь `hf`, а не
`python -m huggingface_hub.commands.huggingface_cli` (его больше нет).

## Режимы laya_bridge

```bash
# Гейт осмысленности UI: 5 осей (удобно/функционально/доступно/понятно/красиво)
# + ship_decision (pass/violations/need_rework_p)
echo "<описание изменения UI>" | laya_bridge.py ui_gate

# Триаж находки: категория (kritichno/sredne/nizko), срочность, действие
echo "<находка аудитора>" | laya_bridge.py triage

# Вердикт по состоянию кода: verdict_decision (stabilen/rework_p)
echo "<состояние цикла>" | laya_bridge.py verdict

# Построчный скоринг релевантности строк (Нужен --state-context для дискриминации!)
printf "строка1\nстрока2" | laya_bridge.py score --state-context "контекст проектов"

# Сырой прогон: JSON-файл {state, questions}
laya_bridge.py raw --raw /tmp/questions.json
```

## Уроки валидации (26 сен 2026) — проверено реальными прогонами

1. **noul-формулировки-одобрения ненадёжны**: «стоит ли пропускать/заниматься?»
   сатурируются в yes (0.87–0.90) на любом входе. Надёжна только семантика
   **«стоит ли доработать?»**: плохое UI 0.59–0.62 да, хорошее 0.22–0.30 да.
2. **score-оси дискриминируют отлично**: удобство плохого UI 0.29–0.47 vs хорошего
   1.16–1.43; доступность 1.04 vs 1.60. Порог ship: все оси ≥1.0 И dorabotka < 0.5.
3. **Одинаковые вопросы в батче дают одинаковые ответы** (все item_X = 1.4338).
   Построчный скоринг: строка = state, один вопрос на вызов.
4. **score без контекста не дискриминирует** (краска забора 1.15 ≈ codegraph 1.19);
   с `--state-context` порядок осмысленный: релевантное 1.38 > нерелевантное 0.59.
5. **choice-вердикт зеркалит noul-подход**: позитивный текст → «nuzhna_rabota» 0.86.
   Итоговый вердикт брать из `verdict_decision.stabilen` (по dorabotka < 0.5),
   raw-choice не использовать как единственный источник.
6. Однородная гомоглифная кириллица в JSON-выводе — артефакт Security-скана Hermes,
   не дефект: `ensure_ascii=False` сохраняет настоящую кириллицу.

## Применение в Живом Коде (карта интеграции, 27 сен 2026)

**Вписано детерминированно:**
- **Владыка** (`~/LivingCode/lord_of_code.py`): перед отчётом строит сводку hot-файлов
  (`build_hot_summary`) и получает laya-вердикт (`verdict`) — блок «Laya-вердикт» в
  lord-отчёте, «Внимание Владыке» при stabilen=false. Деградация без падения: laya
  недоступен → отчёт как раньше.
- **Аудитор** (`~/LivingCode/wrappers/wrapper_auditor.sh`, шаг 5 промпта): laya-триаж
  каждой находки + ui_gate для UI-изменений. laya — первый фильтр, не замена аудита.
- **Искатель** (крон LV-searcher, шаг 6): laya-скоринг находок с --state-context,
  приоритет изучения по скору (1.2+/0.8-1.2/ниже 0.8).
- **Профессор** (крон LV-professor, шаг 3): laya-приоритизация 🔴-тем Учебника перед
  изучением; скоры попадают в журнал и отчёт.
- **Инквизитор** (крон LV-inquisitor, шаг 3): laya-триаж проблем перед решением —
  kritichno → немедленный фикс, otlozhit → план, operatoru → человеку.
- **Восстановлена непрерывность**: `living_code_agent_wrapper.py` вернулся в
  `~/.hermes/scripts` (wrapper_auditor.sh ссылался на отсутствующий файл).

**Общее для всех ролей:** триаж находок (triage), вердикт стабилен/нужна работа (verdict),
калиброванный скоринг топиков (score --state-context), гейт осмысленности UI (ui_gate).
Питание: CPU/iGPU узла (322M параметров), большие модели не тратятся на микрорешения.

## Границы

Laya не пишет код — она судит и решает. Писать UI по-прежнему будут большие модели,
но каждая правка проходит смысловой гейт. Для факта и файла мост — первый судья,
не замена аудита.
