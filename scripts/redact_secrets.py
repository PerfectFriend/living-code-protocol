#!/usr/bin/env python3
"""Вычищает реальные API-ключи из файлов экспорта перед публикацией в git.

Использование:
    redact_secrets.py <каталог> [<каталог> ...]

Реальные ключи распознаются по длине (>=40 символов после префикса), поэтому
примеры-заглушки вида sk-xxxx в документации не трогаются.
Код возврата 1 — если после обработки где-то остался живой ключ.
"""
from __future__ import annotations

import pathlib
import re
import sys

REAL_KEY = re.compile(r"\b(nvapi-|sk-|gho_|ghp_|AIza|xai-)[A-Za-z0-9_\-]{40,}\b")
PLACEHOLDER = r"\1<REDACTED_в_экспорте>"
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv"}
TEXT_SUFFIXES = {
    ".md", ".markdown", ".txt", ".json", ".jsonl", ".yaml", ".yml", ".sh", ".bash",
    ".py", ".js", ".ts", ".tsx", ".toml", ".ini", ".cfg", ".conf", ".env", ".sql", ".csv",
}


def scan_dir(root: pathlib.Path) -> tuple[int, list[str]]:
    total, leftovers = 0, []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES:
            continue
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        if not REAL_KEY.search(text):
            continue
        hits = len(REAL_KEY.findall(text))
        path.write_text(REAL_KEY.sub(PLACEHOLDER, text))
        total += hits
        print(f"  очищено {hits:3d} в {path.relative_to(root)}")
        if REAL_KEY.search(path.read_text(errors="ignore")):
            leftovers.append(str(path))
    return total, leftovers


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 2
    grand_total, grand_left = 0, []
    for arg in argv[1:]:
        root = pathlib.Path(arg).expanduser().resolve()
        print(f"Сканирую {root}")
        total, leftovers = scan_dir(root)
        grand_total += total
        grand_left += leftovers
        if not total:
            print("  чисто — ключей не найдено")
    print(f"\nВсего очищено: {grand_total}")
    if grand_left:
        print("ОСТАЛИСЬ КЛЮЧИ — публиковать нельзя:")
        for p in grand_left:
            print("  ", p)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
