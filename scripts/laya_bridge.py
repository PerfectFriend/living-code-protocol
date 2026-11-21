#!/home/thomas/LivingCode/venvs/laya/bin/python
"""laya_bridge — внешний модуль Laya AI для Протокола Живого Кода.

Запускается ТОЛЬКО питоном venv laya (не процессом Hermes): большие входы
никогда не входят в контекст агента. На вход — файл или stdin, на выход —
компактный JSON-вердикт (сотни байт) в stdout.

Мультlanguage чекпоинт лежит локально: ~/LivingCode/models/laya-multilingual.
Ограничение: вопрос+контекст ≤ max-chars (по умолчанию 4000 симв. ≈ 1000 токенов —
зона сильной точности модели до ~4000 токенов). Большие входы режутся head+tail.

Режимы:
  ui_gate   — гейт осмысленности UI: 5 осей (удобно/функционально/доступно/
              понятно/красиво) + noul «пропускать без доработки?»
  triage    — триаж находок: категория (choice), срочность (score), действие
  verdict   — вердикт по состоянию проекта: стабилен/регресс/нужна работа + noul
  score     — скоринг релевантности: список строк → score каждой (0..2)
  raw       — сырой прогон: state и questions передаются как JSON

Примеры:
  echo "Заменили кнопку Отправить на иконку без подписи" | laya_bridge.py ui_gate
  laya_bridge.py triage --file /home/thomas/LivingCode/runtime/events/last.json
  laya_bridge.py verdict --file /home/thomas/LivingCode/reports/coder-x.md
  echo -e "codegraph\\nhtmx 4.0\\nZod v4.5" | laya_bridge.py score
"""
import argparse
import json
import os
import sys

DEFAULT_MODEL_DIR = os.path.expanduser("~/LivingCode/models/laya-multilingual")
FALLBACK_REPO = "convaiinnovations/laya-multilingual"
DEFAULT_MAX_CHARS = 4000

UI_QUESTIONS = {
    "udobno": {"type": "score",
               "instructions": "Насколько этот интерфейс удобен для пользователя?",
               "criteria": ["неудобно", "терпимо", "удобно"]},
    "funkcionalno": {"type": "score",
                     "instructions": "Выполняет ли интерфейс все заявленные функции без лишних шагов?",
                     "criteria": ["нет", "частично", "да"]},
    "dostupno": {"type": "score",
                 "instructions": "Доступен ли интерфейс: контраст, навигация с клавиатуры, подписи для скринридера?",
                 "criteria": ["недоступен", "частично", "доступен"]},
    "ponyatno": {"type": "score",
                 "instructions": "Понятен ли интерфейс без объяснений и документации?",
                 "criteria": ["непонятно", "частично", "понятно"]},
    "krasivo": {"type": "score",
                "instructions": "Выглядит ли интерфейс аккуратно и красиво?",
                "criteria": ["некрасиво", "терпимо", "красиво"]},
    # Контракт-вопросы (Фаза 2, по паспорту UI Finish-Gate Reviewer): генеричность
    # и скрытый workflow — НЕ вкусовщина, а наблюдаемые признаки interchangeable-UI.
    "genericen": {"type": "noul",
                  "instructions": "Мог бы этот интерфейс принадлежать любому продукту (генеричные dashboard-карточки, декоративные градиенты, сетки без иерархии)?"},
    "skryt_workflow": {"type": "noul",
                       "instructions": "Скрывает ли интерфейс реальный workflow пользователя (заменяет доменное действие generic hero/dashboard/галереей)?"},
    "ship": {"type": "noul",
             "instructions": "Стоит ли доработать этот интерфейс перед выпуском в продакшн?"},
}

# Интерпретация noul для ship: noul = P(«да, стоит доработать»).
# ship-решение (Фаза 2): все score-оси ≥ 1.0 И dorabotka < 0.5 И контракт-вопросы < 0.5.
# Замечено при валидации: формулировки-одобрения («стоит ли пропускать?»)
# сатурируются в yes и ненадёжны; «стоит ли доработать?» различает корректно.

TRIAGE_QUESTIONS = {
    "kategoriya": {"type": "choice",
                   "instructions": "Какова категория этой находки?",
                   "criteria": {"kritichno": "блокирует работу, потеря данных, уязвимость",
                                "sredne": "реальный дефект, надо чинить в этом цикле",
                                "nizko": "косметика или на усмотрение оператора"}},
    "srochnost": {"type": "score",
                  "instructions": "Насколько срочно чинить эту находку?",
                  "criteria": ["не срочно", "скоро", "блокирует"]},
    "action": {"type": "choice",
               "instructions": "Что делать с этой находкой?",
               "criteria": {"chinit_seychas": "чинить немедленно в текущем цикле",
                            "otlozhit": "записать в план и отложить",
                            "operatoru": "решение за человеком-оператором"}},
}

VERDICT_QUESTIONS = {
    "verdict": {"type": "choice",
                "instructions": "Каков вердикт по состоянию этого кода?",
                "criteria": {"stabilen": "тесты зелёные, регрессов нет, всё закрыто",
                             "regress": "новый дефект или сломанное поведение",
                             "nuzhna_rabota": "незакрытые замечания или пробелы проверки"}},
    "uveren": {"type": "noul",
               "instructions": "Достаточно ли данных, чтобы быть уверенным в вердикте?"},
    "dorabotka": {"type": "noul",
                  "instructions": "Стоит ли доработать этот код перед закрытием цикла аудита?"},
}

# Замечено при валидации (26 сен 2026): choice-вердикт «nuzhna_rabota» и noul-подход
# («находится ли в стабильном состоянии?») работают зеркально не так: позитивный текст
# получает высокий «нужна работа» (0.86). Надёжная семантика — «стоит ли доработать?»
# (плохой код 0.59 да / хороший 0.24 да). Итог: dorabotka < 0.5 → стабилен.
# НЕ полагаться на verdict.choice как на единственный источник.


def head_tail(text: str, max_chars: int) -> str:
    """Компактный контекст: начало (заголовки/постановка) + конец (свежее)."""
    if len(text) <= max_chars:
        return text
    half = max_chars // 2
    marker = "\n[...]\n"
    return text[:half] + marker + text[-half:]


def read_input(args) -> str:
    if args.file:
        with open(args.file, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
    data = sys.stdin.read()
    return data


def build_router(args):
    from laya import Router
    model_dir = args.model_dir or DEFAULT_MODEL_DIR
    models = None
    if os.path.isdir(model_dir):
        models = {"multilingual": model_dir}
    router = Router(models=models, device="cpu", max_loaded=1, default="multilingual")
    return router


def pick_answer(ans: dict) -> dict:
    """Достаёт из словаря ответа компактный вердикт + уверенность."""
    out = {}
    for key in ("choice", "noul", "score", "value", "answer"):
        if key in ans:
            out[key] = ans[key]
            break
    if "answer_confidence" in ans:
        out["answer_confidence"] = ans["answer_confidence"]
    return out


def compact_result(result: dict) -> dict:
    answers = result.get("answers", {})
    out = {
        "answers": {name: pick_answer(a) for name, a in answers.items()},
        "routing": {k: result.get("routing", {}).get(k)
                    for k in ("model", "lang", "latency_ms") if k in result.get("routing", {})},
    }
    return out


def _warm_url() -> str:
    return os.environ.get("LAYA_WARM_URL") or f"http://127.0.0.1:{os.environ.get('LAYA_PORT', '8731')}"


def _try_warm(args) -> str | None:
    """Отдаёт запрос тёплому сервису Laya. None — если сервиса нет (тогда локальный путь).

    Сервис исполняет тот же `main()` против уже загруженной модели, поэтому результат
    побитово тот же, что при холодном запуске; на хосте экономится загрузка чекпоинта.
    """
    import urllib.error
    import urllib.request

    argv = [args.mode]
    if args.max_chars is not None:
        argv += ["--max-chars", str(args.max_chars)]
    if args.lang:
        argv += ["--lang", str(args.lang)]
    if args.state_context:
        argv += ["--state-context", str(args.state_context)]

    if args.mode == "raw":
        src = args.raw or args.file
        if not src:
            return None                      # пусть локальный путь выдаст ту же ошибку
        try:
            with open(src, "r", encoding="utf-8", errors="replace") as f:
                payload = f.read()
        except OSError:
            return None
    else:
        payload = read_input(args)

    body = json.dumps({"argv": argv, "text": payload}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(f"{_warm_url()}/call", data=body,
                                 headers={"Content-Type": "application/json; charset=utf-8"},
                                 method="POST")
    try:
        with urllib.request.urlopen(req, timeout=float(os.environ.get("LAYA_WARM_TIMEOUT", "300"))) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError):
        return None                          # сервис не поднят/упал → тихий фолбэк на локальный путь
    if not isinstance(data, dict) or not data.get("ok"):
        return data.get("stdout") if isinstance(data, dict) else None
    out = data.get("stdout") or ""
    return out if out.strip() else None


def _fallback_marker(mode: str) -> None:
    """[LAYA_FALLBACK] в журнал при падении тёплого сервиса (план v3, фаза 4)."""
    from datetime import datetime
    journal = os.path.join(os.path.expanduser("~"), "LivingCode", "agents", "journal.md")
    line = (f"[LAYA_FALLBACK] {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')} mode={mode} — "
            "тёплый сервис laya-warm не ответил, холодный локальный путь (план v3, фаза 4)")
    try:
        with open(journal, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def main() -> int:
    p = argparse.ArgumentParser(description="laya_bridge — внешний модуль Laya для Живого Кода")
    p.add_argument("mode", choices=["ui_gate", "triage", "verdict", "score", "raw"])
    p.add_argument("--file", help="файл с входом (иначе stdin)")
    p.add_argument("--model-dir", default=None, help="путь к чекпоинту (по умолчанию локальный multilingual)")
    p.add_argument("--max-chars", type=int, default=DEFAULT_MAX_CHARS,
                   help="макс. символов контекста на вопрос (head+tail)")
    p.add_argument("--lang", default="ru", help="подсказка языка")
    p.add_argument("--state-context", default=None,
                   help="для score: контекст, добавляемый к каждой строке (проекты, тема)")
    p.add_argument("--raw", help="для режима raw: JSON-файл с {state, questions}")
    p.add_argument("--no-service", action="store_true",
                   help="не обращаться к тёплому сервису Laya (LAYA_WARM=0 — то же самое)")
    args = p.parse_args()

    # Тёплый сервис (laya_service.py) — если поднят, считает он; иначе локальный путь.
    # LAYA_IN_SERVICE=1 выставляет сервис: тогда вложенный вызов не идёт по HTTP обратно
    # в сервис (это была причина вечного зависания на LOCK).
    service_expected = (not args.no_service and os.environ.get("LAYA_IN_SERVICE") != "1"
            and os.environ.get("LAYA_WARM", "1").lower() not in ("0", "false", "no"))
    if service_expected:
        warm = _try_warm(args)
        if warm is not None:
            print(warm, flush=True)
            return 0
        _fallback_marker(args.mode)  # план v3, фаза 4: алерт о cold-path в журнал

    try:
        router = build_router(args)
    except Exception as e:
        print(json.dumps({"error": f"model_load_failed: {e}"}), flush=True)
        return 2

    try:
        text = ""
        if args.mode == "raw":
            src = args.raw or args.file
            if not src:
                print(json.dumps({"error": "raw mode требует --raw или --file"}), flush=True)
                return 1
            with open(src, "r", encoding="utf-8", errors="replace") as f:
                payload = json.load(f)
            state = head_tail(str(payload.get("state", "")), args.max_chars)
            questions = payload["questions"]
            result = router.predict(state, questions, model="multilingual",
                                    lang=args.lang, max_len=8192)
        else:
            text = read_input(args).strip()
            if not text:
                print(json.dumps({"error": "пустой вход"}), flush=True)
                return 1
            state = head_tail(text, args.max_chars)
            if args.mode == "ui_gate":
                questions = UI_QUESTIONS
            elif args.mode == "triage":
                questions = TRIAGE_QUESTIONS
            elif args.mode == "verdict":
                questions = VERDICT_QUESTIONS
            else:  # score
                lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:30]
                if not lines:
                    print(json.dumps({"error": "нет строк для скоринга"}), flush=True)
                    return 1
                # Одинаковые вопросы в батче дают одинаковые ответы (замечено при
                # валидации) — поэтому построчно: строка = state, один вопрос.
                q = {"rel": {"type": "score",
                             "instructions": "Насколько релевантна эта запись для ИИ-инженерии и текущих проектов?",
                             "criteria": ["не релевантна", "слабо", "релевантна"]}}
                items = []
                ctx = (args.state_context or "").strip()
                for i, ln in enumerate(lines):
                    row = f"Контекст: {ctx}\nЗапись: {ln}" if ctx else ln
                    r = router.predict(head_tail(row, args.max_chars), q,
                                       model="multilingual", lang=args.lang, max_len=8192)
                    ans = r.get("answers", {}).get("rel", {})
                    items.append({"text": ln[:120],
                                  "score": ans.get("score"),
                                  "answer_confidence": ans.get("answer_confidence")})
                print(json.dumps({"items": items, "routing": {"model": "multilingual"}},
                                 ensure_ascii=False, separators=(",", ":")), flush=True)
                return 0
            result = router.predict(state, questions, model="multilingual",
                                    lang=args.lang, max_len=8192)

        out = compact_result(result)
        if args.mode == "ui_gate" and "answers" in out:
            a = out["answers"]
            axes = ["udobno", "funkcionalno", "dostupno", "ponyatno", "krasivo"]
            scores = {k: a[k].get("score") for k in axes if k in a and a[k].get("score") is not None}
            noul = a.get("ship", {}).get("noul")
            # Контракт-вопросы (Фаза 2, паспорт UI Finish-Gate Reviewer): noul = P(«да»).
            genericen = a.get("genericen", {}).get("noul")
            skryt = a.get("skryt_workflow", {}).get("noul")
            contract = {"genericen": genericen, "skryt_workflow": skryt}
            contract_violations = [k for k, v in contract.items() if v is not None and v >= 0.5]
            violations = [k for k, v in scores.items() if v < 1.0] + contract_violations
            # Гейт PASS/HOLD (формула плана): все 5 осей ≥ 1.0 И dorabotka < 0.5
            # И контракт-вопросы < 0.5; иначе HOLD с замечаниями-нарушителями.
            out["ship_decision"] = {
                "pass": bool(scores) and all(v >= 1.0 for v in scores.values())
                        and (noul is not None and noul < 0.5)
                        and not contract_violations,
                "violations": violations,
                "need_rework_p": noul,
                "contract": contract,
                "contract_verdict": "PASS" if not contract_violations else "HOLD",
            }
        if args.mode == "verdict" and "answers" in out:
            d = out["answers"].get("dorabotka", {}).get("noul")
            out["verdict_decision"] = {
                "stabilen": bool(d is not None and d < 0.5),
                "rework_p": d,
            }
        if args.mode == "score" and text and "answers" in out:
            lines = [ln.strip() for ln in text.splitlines() if ln.strip()][:30]
            out["items"] = [{"text": ln[:120], **out["answers"].get(f"item_{i}", {})}
                            for i, ln in enumerate(lines)]
        print(json.dumps(out, ensure_ascii=False, separators=(",", ":")), flush=True)
        return 0
    except Exception as e:
        print(json.dumps({"error": f"predict_failed: {e}"}), flush=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
