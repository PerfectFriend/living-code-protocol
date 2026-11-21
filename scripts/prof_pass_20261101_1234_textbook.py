#!/usr/bin/env python3
"""Проход Профессора 2026-11-01 12:34: атомарная правка Учебника — 4 изученные темы."""
import shutil, sys
sys.path.insert(0, "/home/thomas/LivingCode/orchestration/scripts")
from textbook_lock import TextbookLock

TB = "/home/thomas/Documents/ObsidianVault/Учебник.md"
BAK = "/home/thomas/Documents/ObsidianVault/Учебник.md.bak-prof-20261101-1258"

DONE = [
 (16, "skilled-agent-harness",
  "- [x] 🟢 **skilled-agent-harness: spec-driven loops с памятью и скиллами** (MichelKerkmeester/skilled-agent-harness_spec-driven-loops, MIT, JavaScript, ★39, push 2026-11-01) — **спека как папка на диске, а не текст в промпте**: скилл `system-spec-kit` обязателен для ЛЮБОГО изменения файла (запись → папка спецификации, чтение → нет), уровни 1–3+ по матрицам решения, 14 намерений-роутов с `UNKNOWN_FALLBACK` вместо молчаливого дефолта. **Живой разбор клона** (`third_party/skilled-agent-harness`, 2,6 ГБ; `specs/` 1,9 ГБ; HEAD `eed2dd61`, push 2026-11-01 08:55 UTC): индекс триггеров `runtime/data/trigger-index.json` — лексический lookup с кодами возврата **0 hit / 1 miss / 2 broken** (никакого сервера, БД и демона: «свежий клон отвечает до того, как что-то построено»); лестница непрерывности `handover.md → _memory.continuity → спеки`; **гейт-валидатор `runtime/cli/spec/validate.sh` сам не реализует ни одного правила** — решения принимает `dist/lib/validation/orchestrator.js` по реестру `validator-registry.json` («вторая реализация правил — второй ответ на тот же вопрос»); авторские документы пишутся **только** через `create.sh`/рендерер (контракт шаблона); зеркала контента в `.claude/ .codex/ .cursor/ .opencode/ .pi/ .devin/ .hermes/` — **Hermes поддерживается из коробки**. 14 скиллов, команды `create/deep/design/doctor/prompt/speckit`, встроенные гейты `compiled-route-guard.cjs`, `check-agent-mirror-sync.cjs`, `cli-offline-smoke.cjs`. laya=**1.4794** (живой замер) #Искатель #source:github #spec-driven #memory #skills #MIT #professor:2026-11-01 Конспект: [[skilled-agent-harness-Spec-Kit-Portal-2026]]. ⚠ **Живой стенд НЕ делал** (npm ci на 2,6 ГБ не запускал, тесты не гонял) — разбор только чтением; стек JS/TS не наш основной."),
 (12, "Harmony Harness",
  "- [x] 🟢 **Harmony Harness: Multi-Objective Self-Evolution of Agent Harnesses** (arXiv 2610.15150, Weichen Yu, Google Cloud AI Research / Google DeepMind / CMU, опубликовано 10.10.2026) — **эволюция харнесса как многокритериальная задача: безопасность — НЕЗАВИСИМАЯ ось, а не слагаемое в награде**. Источник: https://arxiv.org/abs/2610.15150 — laya=**1.0867** (живой замер; Искатель заявил 1.7177 — расхождение зафиксировано). **Механика (abstract + §1 arXiv HTML):** декомпозиционный эволюционный поиск ведёт **по одной инкумбентной популяции в разных регионах фронта Парето** — без рукописной «структурной метрики разнообразия», ломающейся на репозиторном масштабе; **факторизованные операторы** эволюционируют отдельно (а) общие механизмы `H_gen` и (б) средовые адаптации `H_env`; **динамическая композиция на инференсе** — отдельный composition agent строит задаче-специфичный **DAG** из пулов компонентов, **не изменяя** сами эволюционировавшие компоненты. **Цифры авторские (не перепроверены):** прирост **>10 %** на SecRepoBench и BaxBench. **Для нас:** наши два слоя (общие скарлеты память/план/действие/капабити vs подстройки под проект) прямо соответствуют `H_gen`/`H_env`; наш гейт релиза моно-объективен — успех и безопасность не сравниваются, и «лучше по успеху, хуже по безопасности» сейчас не выразить. ⚠ **Кода в природе нет**, стенда не делал. #Искатель #source:arxiv #harness #multi-objective #pareto #compositional #GoogleCloud #professor:2026-11-01 Конспект: [[Harmony-Harness-Multi-Objective-Evolution-2026]]."),
 (220, "Локальная модель",
  "- [x] 🟢 [Локальная модель не равна изолированному агенту](https://www.youtube.com/watch?v=3mx84MRj8lY) — laya **1.2186** (живой замер, conf 0.7084). Видео канала **Kai** от 2026-10-21, 26:00, **505 542 просмотра**. **Тезис:** модель-сканеры проверяют, запускает ли файл код при загрузке; **отравленные веса ничего не запускают — они инструктируют, и локальный агент сам отправляет данные**. 5 слоёв: (1) malware на Hugging Face (фейковый «OpenAI»-репозиторий в №1 trending — инфостилер на пароли браузера/кошельки/SSH); (2) **chat templates — это код**: отравленный шаблон режет точность с 90 % до 15 % и проходит все сканы HF; (3) **Bleeding Llama** в Ollama (утечка env, ключей, чужих чатов из памяти; исправлено в 0.17.1); (4) `OLLAMA_HOST=0.0.0.0` — **175 108 серверов Ollama** в интернете без аутентификации + NemoClaw (веб-страница переписывает шаблон модели); (5) **бэкдор ProjectDiscovery за ~$8 GPU-времени**: 1 % отравленных данных, триггер **75–98 %**, отравленный **Qwen 2.5 7B прошёл 50 из 50** чистых тестов в Codex CLI, пока слова **«bonsoir, Elliot»** не отправили `.env` проекта на чужой сервер. Sleeper agents (Anthropic): **250 отравленных документов** suffice для моделей 600M–13B. Честная часть автора: из 130 592 шаблонов HF опасны **24**, и все — исследовательские артефакты. **ЖИВОЙ АУДИТ НАШЕЙ МАШИНЫ:** ✅ Ollama/13305/8080 — на 127.0.0.1, `OLLAMA_HOST` не задан, `~/.hermes/.env` и `~/.ssh/*` — права 600; ⚠ **нарушен пункт «нет .env там, где агент их прочитает»:** `~/Projects/SuperGuard/.env` и `~/Projects/CatVanGogh/.env` — права **664** (читаемы всеми), плюс **4 копии** `.env.backup/.env.backup3/.env.backup_before_merge/.env.bak` тоже 664; ⚠ `:3000` (`node dist/server.cjs`) и `:8080` слушают **0.0.0.0**. Секреты **не читались**. **Владыке:** `chmod 600 ~/Projects/*/.env*`, вынести бэкапы из репозиториев, закрыть `:3000` на 127.0.0.1, sandbox для агентов (у нас есть sandlock/Landlock и bwrap). ⚠ субтитры недоступны (HTTP 429) ⇒ конспект по полному описанию видео с тайм-кодами, числа авторские. #Искатель #source:youtube #security #local-llm #ollama #sandbox #professor:2026-11-01 Конспект: [[Local-Local-AI-Isolation-Agent-Reach-2026]]."),
 (200, "Scout",
  "- [x] 🟢 [Scout: модель один раз, затем детерминированный Playwright](https://github.com/pcamarajr/scout) — laya **0.8472** (живой замер; Искатель заявил 1.5296). v0.18.0 (#79), MIT, npm `@pcamarajr/scout`. **Идея:** первый прогон — LLM-агент реально проходит сценарий в Playwright и **судит поведение**, записывая детерминированный скрипт; все последующие прогоны — **чистый replay без LLM** (секунды, ~нулевая цена, CI-ready); при поломке из-за изменения UI AI пере-записывает, человек ревьюит дифф. **ЖИВОЙ СТЕНД:** клон 3,7 МБ, `npm ci` rc=0, **`npm run test` — tests 331, pass 300, fail 0, skipped 31, 3529 мс**; 27 файлов тестов. **Механики:** **лестница селекторов** `testid → id → role+name → text → css` — записывается ступень, которая *уникально* матчится; позиционный CSS **не подставляется молча**, шаг помечается `fragile` и CLI предупреждает «add a data-testid or a unique role/name»; авто-id отбраковываются (`\\d{3,}|^radix-|^react-|^headlessui-|^mui-|^:[rR]`), id сериализуется как `[id=\"…\"]`; доступное имя **вычисляется** из живого DOM; 20 видов шагов, включая `assertNoConsoleErrors`, `assertNetwork` (по семейству кода), `assertNotVisible` **с областью** (target-контейнер), `failNetwork` (abort/status) и `setOffline`; `assertNetwork` **не может пройти до срабатывания сбоя** и падает с указанием ожидания; движок: кэш ⇒ replay ⇒ при падении heal через AI ⇒ пере-запись, `--ai` форсирует, `--viewport` даёт ephemeral-прогон **без сохранения** осиротевших файлов; `runWithFallback` при провале всех кандидатов перебрасывает **первичную** ошибку, а не последнюю; Chromium пулится и переиспользуется (клиент обязан вызвать `closeBrowsers()`). **Для нас:** «AI тратится на СОЗДАНИЕ проверки, реплей — на ИСПОЛНЕНИЕ» — прямая схема для нашего цикла кодер→аудитор; `fragileSteps` — третья категория гейта (зелёная, но хрупкая). ⚠ Chromium не ставил ⇒ 31 браузерный тест пропущен; AI-часть не запускал (нужен ключ). #Искатель #source:github #ui-gate #browser-qa #playwright #self-healing #MIT #professor:2026-11-01 Конспект: [[Scout-Self-Healing-Browser-QA-Replay-2026]]."),
]

with TextbookLock(TB) as lock:
    src = lock.read()
    lines = src.split("\n")
    shutil.copy2(TB, BAK)
    changed = []
    for lno, frag, new in DONE:
        i = lno - 1
        if i >= len(lines):
            print(f"MISS line {lno} (вне файла)"); continue
        old = lines[i]
        if frag not in old:
            print(f"MISS {lno}: маркер '{frag}' не найден"); continue
        if "🔴" not in old:
            print(f"SKIP {lno}: нет 🔴 в строке"); continue
        lines[i] = new
        changed.append((lno, old[:70]))
    if not changed:
        print("НЕТ ИЗМЕНЕНИЙ — запись не выполнена"); sys.exit(1)
    lock.write("\n".join(lines))
    print(f"ЗАПИСАНО строк: {len(changed)}")
    for lno, old in changed:
        print(f"  {lno}: {old}")

with TextbookLock(TB) as lock:
    after = lock.read().split("\n")
ok = True
for lno, frag, new in DONE:
    line = after[lno - 1]
    good = ("🟢" in line and "🔴" not in line and "[NEW]" not in line and frag.split()[0][:12] in line)
    print(f"ПРОВЕРКА {lno}: {'OK' if good else 'FAIL'} | {line[:80]}")
    if not good: ok = False
print("ИТОГ:", "ВСЕ 4 СТРОКИ ПОДТВЕРЖДЕНЫ" if ok else "ЕСТЬ ПРОВАЛЫ")
