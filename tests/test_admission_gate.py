#!/usr/bin/env python3
"""test_admission_gate.py — null/liar-тесты для admission-гейта (Фаза 3 плана v3).

Правило (HarnessMaster / state-grader): «агент написал 'готово' без изменения
артефакта» обязан падать так же, как «ничего не сделал». N=0 ⇒ не проверено.

Запуск: python3 tests/test_admission_gate.py   (exit 0 = все тесты зелёные)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from evidence_gate import EvidenceGate  # noqa: E402

PASS = []
FAIL = []


def t(name, cond, detail=""):
    (PASS if cond else FAIL).append(name)
    print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")


def main() -> int:
    # 1. LIAR: заявил «все тесты пройдены: 42 passed», артефактов проверено 0 → NOT_VERIFIED
    liar = ("Отчёт кодера.\nВсе тесты пройдены: 42 passed, exit code: 0. Готово к релизу.\n"
            "artifacts_checked: 0\n")
    r = EvidenceGate().validate(liar, "coder-project1")
    t("liar N=0 падает", not r["passed"] and any("NOT_VERIFIED" in v for v in r["violations"]),
      str([v[:60] for v in r["violations"]])[:120])

    # 2. LIAR без явного счётчика: claim есть, artifacts_checked отсутствует → тоже NOT_VERIFIED
    liar2 = "Сделано. Все тесты пройдены: 42 passed, rc=0. Запушено.\n"
    r = EvidenceGate().validate(liar2, "coder-project2")
    t("liar без счётчика падает", not r["passed"] and any("NOT_VERIFIED" in v for v in r["violations"]))

    # 3. NULL: вообще ничего не сделал, но сказал «готово» → падает
    null_report = "Готово.\n"
    r = EvidenceGate().validate(null_report, "coder-project3")
    t("null-отчёт падает", not r["passed"])

    # 4. HONEST: claim + artifacts_checked: 5 + receipts → проходит, accepted=True
    honest = ("# Отчёт\nartifacts_checked: 5\n"
              "Запущено: pytest tests/ -q → ```\n5 passed in 1.2s\n``` exit code: 0\n"
              "Все тесты пройдены, коммит kommit: abc1234.\n")
    r = EvidenceGate(min_sample=1).validate(honest, "coder-project4")
    t("честный отчёт проходит", r["passed"], str(r["violations"])[:120])
    t("accepted == passed", r.get("accepted") == r["passed"])
    t("finished_claimed=True", r.get("finished_claimed") is True)

    # 5. BASELINE: регрессия относительно contemporaneous baseline → падает с причиной
    #    (baseline=1.01 выше любого возможного ratio ≤ 1.0 — детерминированная регрессия)
    r = EvidenceGate(min_grounded_ratio=0.0, min_sample=0, baseline=1.01).validate(honest, "x")
    t("baseline-регрессия падает с причиной",
      not r["passed"] and any("BASELINE_REGRESSION" in v for v in r["violations"]),
      f"ratio={r['metrics']['grounded_numbers_ratio']:.2f} delta={r['metrics'].get('delta_vs_baseline')} "
      + str([v[:80] for v in r["violations"]])[:160])

    # 6. LOW_SAMPLE: чисел меньше min_sample → предупреждение, но не падение
    r = EvidenceGate(min_sample=50).validate(honest, "x")
    t("min_sample → LOW_SAMPLE warning", any("LOW_SAMPLE" in w for w in r["warnings"]))

    print(f"\ntest_admission_gate: {len(PASS)} passed, {len(FAIL)} failed")
    if FAIL:
        print("FAILED:", FAIL)
    return 0 if not FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
