"""Локальный (без тёплого сервиса) скоринг тем Профессора: одна загрузка модели, N предсказаний.

Повторяет логику laya_bridge.py mode=score, но без HTTP-сервиса (он занят параллельным прогоном).
"""
import json
import sys
import time

sys.path.insert(0, "/home/thomas/LivingCode/orchestration/scripts")
import laya_bridge as B  # noqa: E402

CTX = ("Проекты Живого Кода: рой агентов-кодеров, локальные LLM, UI-гейты, самообучение роя")
TOPICS_FILE = sys.argv[1]
OUT = sys.argv[2]

topics = [ln.strip() for ln in open(TOPICS_FILE, encoding="utf-8") if ln.strip()]
t0 = time.time()
router = B.build_router(type("A", (), {"model_dir": None})())
print("model loaded in %.1fs" % (time.time() - t0), flush=True)

q = {"rel": {"type": "score",
             "instructions": "Насколько релевантна эта запись для ИИ-инженерии и текущих проектов?",
             "criteria": ["не релевантна", "слабо", "релевантна"]}}

items = []
for ln in topics:
    row = f"Контекст: {CTX}\nЗапись: {ln}"
    t1 = time.time()
    r = router.predict(B.head_tail(row, B.DEFAULT_MAX_CHARS), q, model="multilingual", max_len=8192)
    ans = r.get("answers", {}).get("rel", {})
    items.append({"text": ln, "score": ans.get("score"),
                  "answer_confidence": ans.get("answer_confidence"),
                  "ms": round((time.time() - t1) * 1000, 1)})
    print(json.dumps(items[-1], ensure_ascii=False), flush=True)

json.dump({"items": items, "model": "multilingual(local,no-service)"},
          open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved", OUT, flush=True)
