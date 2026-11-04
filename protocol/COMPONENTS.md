# COMPONENTS.md — редактируемое дерево слоёв протокола (Фаза 2 плана v3, c1..c8)

Каждый слой имеет владельца и гейт. Правки слоёв 1–3 (safety) — класс `ban-edit`/`model-change`
в `guard_action.py` и требуют одобрения владельца.

| # | Слой | Путь | Гейт |
|---|------|------|------|
| c1 | Движок ролей | `orchestration/scripts/living_code_agent_wrapper.py` | бан nemotron, rc=75 retry, `py_compile` + benchmark |
| c2 | Ростер/реестр джоб | `orchestration/roster.json`, `orchestration/jobs/jobs.json`, `~/.hermes/cron/jobs.json` | `check_roster.py` rc=0 |
| c3 | Обёртки ролей | `orchestration/scripts/wrappers/*.sh` | `bash -n` + `guard_action` на push-protected |
| c4 | Промпты ролей | `orchestration/scripts/wrappers/prompts/*.txt` | L3-критик + evidence_gate отчёта |
| c5 | Конфиги Hermes | `orchestration/hermes-config/config.yaml`, `~/.hermes/config.yaml` | модель из белого списка; `hermes config set` для live |
| c6 | Гейты | `evidence_gate.py`, `release_gate.py`, `guard_action.py`, `journal_lint.py`, `condition_snapshot.py`, `kg_validate.py` | null/liar-тесты, selftest, benchmark |
| c7 | Состояние | `state/` (orchestrator_state.json, condition_snapshot.json, state.db) | snapshot check; compact_state_db в окно без gateway |
| c8 | Память/граф знаний | `agents/journal.md`, `reports/`, `knowledge-base/`, `knowledge-base/knowledge-graph.json`, `protocol/EXPERIENCE.md` | journal_lint провенанс, kg_validate схема v3 |

Запрещено эволюции: ослаблять c1-бан, c3/c5 модель вне белого списка, c6-гейты.
