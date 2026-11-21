#!/usr/bin/env python3
"""journal_lint.py — правило провенанса журнала (compaction-deception, OpenAI 09.2026).

agents/journal.md — НЕДОВЕРЕННЫЙ вход (канал инъекции при компакции контекста).
Правило: любая строка-утверждение о завершении работы должна нести тег провенанса:
  [VERIFIED <команда/инструмент>]  — факт проверен прогоном в этом слоте
  [REPORTED]                      — пересказано, не перепроверено
Строки-маркеры ([TRIGGER_*], [*_RETURN], [VERDICT] и т.п.) тега не требуют.

По умолчанию проверяются только последние --lines строк (по умолчанию 150) —
исторические записи до 04.11.2026 не линтим задним числом.

Exit: 0 всегда в report-режиме; --strict → exit 1 при найденных нарушениях.
"""
import argparse
import re
import sys
from pathlib import Path

JOURNAL = Path.home() / "LivingCode" / "agents" / "journal.md"

CLAIM_RE = re.compile(
    r"(сделан\w*|готов\w*|исправлен\w*|запущен\w*|запушен\w*|верифицирован\w*|"
    r"проверен\w*|пройден\w*|собран\w*|отработал\w*|выполнен\w*|доставлен\w*|"
    r"закрыт\w*|принят\w*|релиз\b|готово)",
    re.IGNORECASE,
)
TAG_RE = re.compile(r"\[(VERIFIED\b[^\]]*|REPORTED)\]", re.IGNORECASE)
MARKER_RE = re.compile(r"^\s*\[[A-Z_]+\]")  # строка начинается с маркера-события
CODE_FENCE_RE = re.compile(r"^\s*```")


def lint_lines(lines: list[str]) -> list[tuple[int, str]]:
    violations = []
    in_code = False
    for i, ln in enumerate(lines, 1):
        if CODE_FENCE_RE.match(ln):
            in_code = not in_code
            continue
        if in_code:
            continue
        if MARKER_RE.match(ln):
            continue
        if CLAIM_RE.search(ln) and not TAG_RE.search(ln):
            violations.append((i, ln.strip()[:160]))
    return violations


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--lines", type=int, default=150, help="сколько последних строк проверять")
    ap.add_argument("--file", default=str(JOURNAL))
    ap.add_argument("--strict", action="store_true")
    args = ap.parse_args()

    p = Path(args.file)
    if not p.exists():
        print(f"Журнал не найден: {p}")
        return 0 if not args.strict else 1
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()[-args.lines:] if args.lines > 0 else text.splitlines()
    violations = lint_lines(lines)
    base = len(text.splitlines()) - len(lines)
    if violations:
        print(f"journal_lint: {len(violations)} утверждений без тега провенанса "
              f"(последние {len(lines)} строк, {p}):")
        for i, ln in violations[:20]:
            print(f"  +{base + i}: {ln}")
        print("Правило: добавь [VERIFIED <cmd>] или [REPORTED] (см. docs/JOURNAL_RULES.md).")
    else:
        print(f"journal_lint: OK — {len(lines)} последних строк, все утверждения с тегом провенанса.")
    return 1 if (args.strict and violations) else 0


if __name__ == "__main__":
    sys.exit(main())
