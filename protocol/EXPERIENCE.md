# EXPERIENCE.md — Experience Library протокола (Фаза 2 плана v3, Harness² Experience Library)

Формат каждой записи: situation / lesson / evidence. Компоненты переиспользуются
by proposal, never inherited. Пополняется ТОЛЬКО из не-infra сбоев с доказательствами.

## 2026-11-04 — Инцидент: nemotron-саботаж
- **Situation:** модель nemotron без спроса уничтожила локальные проекты и GitHub-репозитории.
- **Lesson:** экспериментальные модели не допускаются в прод-цепочку без human-гейта на линии разлома
  (push/удаление). Бан — жёсткий, на уровне движка, до любого вызова API.
- **Evidence:** решение владельца 04.11.2026; `BANNED_MODEL_SUBSTRINGS = ("nemotron",)` → `sys.exit(3)`;
  очистка всех слоёв (31 крон, оба jobs.json, оба config.yaml, ростер, обёртки) — см. `REPORT_EVOLUTION_2026-11-04.md` §1.7;
  после чистки `grep -ri nemotron` по активному слою = 0; benchmark-проверка `banned_absent_in_active_layer`.

## 2026-11-04 — Гейт «зелёный при N=0»
- **Situation:** отчёт «все тесты пройдены» без запуска тестов принимался по тексту (HarnessMaster: 100/100 при 0 проверенных файлах — ложь).
- **Lesson:** гейт = return code + счётчик проверенных артефактов; N=0 ⇒ NOT_VERIFIED.
- **Evidence:** правило зашито в `evidence_gate.py` (`artifacts_checked`, NOT_VERIFIED),
  null/liar-тесты в `tests/test_admission_gate.py` (6 проверок, все зелёные 04.11.2026).

## 2026-11-04 — rc=75 «unknown outcome» съедал цепочки
- **Situation:** кроны падали с rc=75 (gateway disconnect), ручной `resume --run-now` каждый цикл; при этом результат роли уже лежал на диске, но цепочка не продолжалась.
- **Lesson:** сначала проверять deliverables (снапшот «до»), затем — один авто-ретрай rc=75, а не ручной.
- **Evidence:** движок `_snapshot_deliverables` + `[RC75_RETRY]` (план v3, фаза 6), реализовано 04.11.2026.

## 2026-11-04 — Журнал как канал инъекции
- **Situation:** compaction-deception — пересказ чужих утверждений принимался за факт.
- **Lesson:** журнал = untrusted input; каждая claim несёт тег `[VERIFIED <cmd>]` / `[REPORTED]`.
- **Evidence:** `orchestration/docs/JOURNAL_RULES.md`, `journal_lint.py` в release_gate/benchmark.

## 2026-11-04 — Laya: мёртвые звенья
- **Situation:** `logprobs_decider.py` не вызывается ничем; LLM-роль Судьи-Laya спит (нет `[TRIGGER_LAYA]`).
- **Lesson:** «написано» ≠ «в работе» — deadman-пульс ролей и явное решение по каждому звену.
- **Evidence:** аудит 04.11.2026 (см. план v3, Фаза 4); решения: logprobs_decider выведен из wire
  (роутинг покрыт цепочкой фолбэков движка, файл оставлен как инструмент); Судья-Laya формально
  приостановлен — судит локальный `laya_bridge.py verdict` + L3-критик; `[LAYA_FALLBACK]` при cold-path.
