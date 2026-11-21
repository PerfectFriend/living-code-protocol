# PPC — цикл эволюции самого протокола (Propose→Probe→Compose, Фаза 2 плана v3)

Основание: Harness² (arXiv 2610.14224), Self-Evolving Harness (2609.38372), Phantom Guardrails (2607.13083).

## Процедура любой правки протокола (engine/roster/wrappers/prompts/jobs/configs/state/knowledge-graph)

1. **Propose** — роль LV-proposer (или ручной отчёт) даёт ≥2 кандидата, каждый trace'ится
   к наблюдению (отчёт, метрика, инцидент). Запись: `[PROPOSER_CANDIDATES]` в журнале
   + `reports/proposer-*.md`. Компоненты переиспользуются по предложению, never inherited.
2. **Probe** — каждый кандидат прогоняется на:
   - held-out benchmark: `python3 orchestration/tests/protocol_benchmark.py` (должен быть зелёным ДО и ПОСЛЕ);
   - один живой цикл роли в dry-run, если затрагивается обёртка;
   - **negative control**: featureless legal input (легальный вход без «фичи») — гейт обязан
     пройти и без, и с правкой; fix без evidence реального failure отклоняется.
3. **Compose** — accept ТОЛЬКО по behavioral contrast (разница поведения на benchmark/живом цикле),
   текст отчёта не является сигналом. Без contrast — отклонить с причиной
   (`correct/objective/note` в вердикте).

## Классификация сбоев

- `infra_error` (rc=75 unknown outcome, таймауты сети, 429 квоты) ≠ урок агента:
  при infra_error промпт/SOP **не меняется**. rc=75 имеет один авто-ретрай в движке (`[RC75_RETRY]`).
- Урок в `protocol/EXPERIENCE.md` попадает только из не-infra сбоев с evidence.

## Safety-гейты ниже слоя эволюции (LocalKin)

Никакая эволюция протокола не может ослабить: бан nemotron (`BANNED_MODEL_SUBSTRINGS`),
`guard_action.py` на линии разлома, бэкапы `.orig-<дата>`, `check_roster` гейт,
`evidence_gate` N=0-правило. Правки этих файлов — класс `ban-edit`/`model-change` и требуют
одобрения владельца через `guard_action.py approve`.

## Снимок условий

После каждой принятой правки: `python3 orchestration/scripts/condition_snapshot.py snapshot`.
При расхождении условий старые оценки/scores помечаются STALE (`condition_snapshot.py check` → exit 1).
