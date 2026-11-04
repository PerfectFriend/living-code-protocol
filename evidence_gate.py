#!/usr/bin/env python3
"""Evidence Gate — детерминированная валидация отчётов перед доставкой.
Паттерн из Xenon 0.9.5: каждый claim должен иметь receipt, grounded_numbers ≥ 90%,
prose без diff не становится патчар, Finalizer — единственный владелец сдачи.
"""

import re
import json
import sys
from pathlib import Path
from typing import Optional


class EvidenceGate:
    """Детерминированные проверки качества отчёта (ноль LLM)."""

    # PATTERN: числа в тексте (IGNORE метаданные)
    NUMBER_PATTERN = re.compile(
        r"(?<!\w)(?:"
        r"\d{1,3}(?:[,\s]\d{3})*(?:\.\d+)?"
        r"|\d+\.\d+"
        r"|\d+%"
        r")(?!\\w)"
    )

    # PATTERNS metadata — числа, которые НЕ требуют receipts
    # (таймстемпы, laya-скоры, счётчики с единицами, даты, версии, номера строк в ссылках, JSON-структура, списки, пороги, таблицы, ADR)
    METADATA_NUMBER_PATTERNS = [
        r"\d{4}-\d{2}-\d{2}",  # 2026-11-02 (dates anywhere)
        r"\d{2}:\d{2}(?::\d{2})?",  # 11:01 or 11:01:07 (timestamps)
        r"\d\.\d{4}",  # 1.1225 (laya scores - 1.xxxx format)
        r"0\.\d{3,4}",  # 0.9169 (confidence/laya scores)
        r"\d\.\d{1,3}(?!\\d)",  # 1.64, 1.52, 0.8 (laya scores/thresholds - 1-3 decimals, not part of longer)
        r"\d+\.\d+\.\d+",  # 1.2.3 (version numbers)
        r"v\d+\.\d+(?:\.\d+)?",  # v1.3.0
        r"ADR-\d+",  # ADR-050
        r"(?:стро(?:ka|ki|ke|kam|k)|line)\s+\d+",  # "строка 168", "строке 188", "line 42"
        r"^[\\s-]*\d+[.)]\s",  # "5. " or "5) " list markers at line start
        r"|\s*\d+\s*|",  # "| 1 |" table row numbers
        r"(\s*\d+\s*)",  # "(5)" parenthetical refs
        r"(\s*\d+\s*)",  # "[5]" bracket refs
        r"#\d+\b",  # "#5" issue numbers (not in URLs)
        r"PR\s*#\d+",  # "PR #123"
        r'issue\s*#\d+',  # "issue #123"
        r"commit\s+[a-f0-9]{7,}",  # commit hashes
        r"\d+\s*(?:teMA|tem|min|sek|ch|GB|MB|KB|B|test|teST|pass|fail|tok|tok/s)",  # "5 tem", "14 min", "54/4.5 tok/s"
        r"$\d+",  # "$59" prices
        r"\d+\.\d+%",  # "16.28%" percentages
        r"\d+/\d+(?:-\d+)?",  # "54/4.5", "290/10-14" tok/s ratios
        r"\d+\.\d+\.\d+-\d+",  # "7.0.0-15" kernel versions
        r"|\s*\d+\s*|\s*|",  # table cells like "| 0 |" or "| 601 |" (second cell)
        r"(?:zadach|minut|naKhodok|ustanovok|izveshchen|testST|stROka|teST|STRANIC|simvolov|kB|MB|GB)\s*[:|]\s*\d+",  # "zadach: 4", "minut: 22", "naKhodok: 10", "ustanovok: 0"
        r"(?:vsego|vsego chisel|vsego testST|vsego strok|vsego simvolov)\s*[:|]\s*\d+",  # "vsego: 39"
        r"(?:punkT|punkTOv|faza|cikl|slot|proKhod|zapis|zapisey)\s+\d+",  # "punkT 5", "faza 3"
        r"(?:obNoven|dobavl|ispravl|sozdan|udalen|Zakryt)\s+\d+",  # "obNoveno 5", "sozdano 3"
        r"\d+\s*(?:stROK|stROKI|teST|teSTov|teSTa|zadach|punkT|punkTOv|faza|cikl|slot|proKhod|zapis|zapisey|simvol|simvolA|simvolov|kB|MB|GB)",  # "3 strokI", "5 testST"
        r"\d+\s*(?:incidents|otvetov|views|pts|sub-agents|tool calls|speedup|x|K|M|%)",  # common report units
        r"\d+\s*(?:teST[a-z]*|pass|fail|error)",  # "42 testST", "12405 pass"
        r"(?:commit|kommit)[\\s:]*[a-f0-9]{7,}",  # commit hashes
        r"[a-f0-9]{7,40}",  # standalone commit hashes
        r"^\s*\d+[.)]\s",  # list markers at line start (after markdown processing)
        r"^#{1,6}\s+\d+[.)]\s",  # section headers like "### 1. " "## 2. "
        r"^\s*[-*]\s+\d+[.)]\s",  # bullet lists with numbers "- 1. " "* 2. "
        r"#{1,6}\s+\d+[.)]",  # section headers anywhere in line
        r"\b\d+(?:\.\d+)?\s*(?:tok/s|tok|tek|TPS|RPS|QPS|ops/s)",  # throughput units
        # Technical terms with numbers that should be excluded
        r"RDNA\d+[/+\\-]\d+",  # RDNA1+/2+/3
        r"gfx\d+(?:/\\d+)?",  # gfx1103, gfx1103/128GB
        r"RDNA\d+",  # RDNA1, RDNA2, RDNA3
        # Table cells where number is followed by text (not just "| N |")
        r"|\s*\d+\s*\(",
        r"|\s*\d+\s*[^|\\d]",  # "| 4 " followed by non-pipe, non-digit
        # Plan references: punkt N, fazA N, phase N, point N (with Russian case variations)
        r"punkT\\w*\s+\d+",
        r"punkTOv\\w*\s+\d+",
        r"faza\\w*\s+\d+",
        r"phase\\w*\s+\d+",
        r"point\\w*\s+\d+",
        r"\d+[–-]\d+",  # ranges like "3–5", "3-5"
        # Laya bridge output patterns
        r"kategoriya.*?\d+\.\d+",  # "kategoriya: 1.6402"
        r"srochnost.*?\d+\.\d+",  # "srochnost: 1.5226"
        r"action.*?(?:chinit_seychas|otlozhit|operatoru)",  # action choice
        r"answer_confidence.*?\d\.\d+",  # answer_confidence: 0.5768
        r"latency_ms.*?\d+",  # latency_ms: 123
        r"ratio.*?\d\.\d+",  # ratio: 0.95
        # Role-specific metadata patterns
        r"kolichestvo[^:]*\s*\d+",  # "kolichestvo tem: 5"
        r"vsego[^:]*\s*\d+",  # "vsego chisel: 39"
        r"propusk[^:]*\s*\d+",  # "propusk: 0"
        r"verdict[^:]*\d+",  # "verdict 1"
        r"slot\s+\d+",  # "slot 1"
        r"proKhod\s+\d+",  # "proKhod 1"
        r"cikl\s+\d+",  # "cikl 88"
        r"pass\s+\d+",  # "pass 10"
        r"fail\s+\d+",  # "fail 2"
        r"error\s+\d+",  # "error 0"
        # Additional count patterns from Nov 2026 fixes
        r"(?:teMA|teMY|naKhodka|naKhodOK|stROka|stROK|teST|teSTov|teSTa)\s*[:|]\s*\d+",  # "5 tem", "10 naKhodok", "3 testST"
        r"(?:vsego|vsego chisel|vsego testST|vsego strok|vsego simvolov)\s*[:|]\s*\d+",  # "vsego: 39"
        # Numbers in square brackets or parentheses that are clearly references
        r"(\s*\d+\s*)",  # "[5]"
        r"(\s*\d+\s*)",  # "(5)"
        # General: standalone number that could be a count in summary context
        r"(?:total|summa|kol-vo|kolichestvo)\s*[:|]\s*\d+",  # "total: 5", "kol-vo: 3"
        # JSON/metrics structure keys (not values)
        r"grounded_numbers_ratio",
        r"grounded_count",
        r"total_numbers",
        r"receipt_count",
        r"ungrounded_numbers",
        r"answer_confidence",
        r"latency_ms",
        r"model",
        r"lang",
        r"score",
        r"choice",
        r"noul",
        r"value",
        r"ratio",
        r"conf",
        r"srochnost",
        r"kategoriya",
        r"action",
        r"min",
        r"max",
        r"passed",
        r"failed",
        r"skipped",
        r"count",
        r"total",
        # Numbers inside JSON arrays in metrics output
        r"(\s*\"\\d+\")",
        r",\s*\"\\d+\"",
        r"\"\\d+\"\s]",
        # Comma-separated numbers in violation lists
        r",\s*\d{1,2}(?:,\s|\s*$)",
    ]

    # PATTERNS для инструментальных выводов (receipts)
    RECEIPT_PATTERNS = [
        r"```(?:json|bash|sh|python|text|diff)\n.*?```",  # код-блоки включая diff
        r"exit code\s*\d+",  # exit code: 0
        r"returncode\s*\d+",  # returncode: 0
        r"passed\s*\d+",  # passed: 576
        r"failed\s*\d+",  # failed: 0
        r"vse teSTY (?:proynedO|passed|zелёные)",  # vse testy proyDENo
        r"\d+\s+passed",  # 576 passed
        r"sha256[:]\s*[a-f0-9]{64}",  # sha256: ...
        r"kommit[:]\s*[a-f0-9]{7,40}",  # kommit: abc1234
        r"файл[:]\s*\S+\.md",  # файл: report.md
        r"delivered|доставлен|sent|успех|success\b",  # доставлен
        r"rc=\d+",  # rc=0
        r"status.*?(?:200|201|0)",  # status 200
        r"@@\s*-\d+,\d+\s*\+\d+,\d+\s*@@",  # diff hunk header
        r"^\+\d+",  # diff added line numbers
        r"^\-\d+",  # diff removed line numbers
    ]

    # PATTERNS "пустых обещаний" (hollow patterns) — из Xenon, адаптированы под русский
    HOLLOW_PATTERNS = [
        r"\bgotovo\\.",  # gotovo.
        r"\bispravlENo\\.",  # ispravlENo.
        r"vse testy (?:proynedO|proshli|zелёные)",  # vse testy prosli
        r"ya ispravil(?: bag)?[,.]?\s*testy (?:zелёные|proshli)",  # ya ispravil bag, testy prosli
        r"\bdone\\.\\s*all tests pass",  # done. all tests pass
        r"\bcompleted\\.",  # completed.
        r"\bfixed\\.",  # fixed.
        r"\breshENo\\.",  # reshenENo.
        r"gotovo,?\s*otpravlju",  # gotovo, otpravlju
    ]

    def __init__(self, min_grounded_ratio: float = 0.9):
        self.min_grounded_ratio = min_grounded_ratio
        self.hollow_regex = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.HOLLOW_PATTERNS]
        self.receipt_regex = [re.compile(p, re.IGNORECASE | re.MULTILINE) for p in self.RECEIPT_PATTERNS]
        # Compile metadata patterns with MULTILINE so ^ matches line starts in context substrings
        self.metadata_regex = [re.compile(p, re.MULTILINE) for p in self.METADATA_NUMBER_PATTERNS]
        # Context window for metadata detection (chars before/after number)
        self.context_window = 100

    def extract_numbers(self, text: str) -> list[str]:
        """Извлекает все числа из текста, исключая метаданные."""
        # Удаляем строку с метриками Evidence Gate
        text = re.sub(r"\*\*Метрики:\*\*\s*\{.*?\}", "", text, flags=re.DOTALL)
        # Удаляем блок нарушений (генерируется самим гейтом, не claims агента)
        text = re.sub(r"\*\*Нарушения:\*\*.*?(?=\n\*\*|\Z)", "", text, flags=re.DOTALL)
        # Также удаляем любые JSON-блоки с ключами метрик
        text = re.sub(r"\{grounded_numbers_ratio[^}]+\}", "", text)
        # Удаляем markdown-форматирование, чтобы числа не разбивались (например, **1.1225** → 1.1225)
        text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold**
        text = re.sub(r"\*([^*]+)\*", r"\1", text)      # *italic*
        text = re.sub(r"`([^`]+)`", r"\1", text)        # `code`
        text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [link](url)

        # Используем finditer для получения точных позиций каждого числа
        filtered = []
        for match in self.NUMBER_PATTERN.finditer(text):
            num = match.group()
            start, end = match.span()
            # Проверяем контекст вокруг ЭТОЙ конкретной позиции
            context = text[max(0, start-self.context_window):end+self.context_window]
            is_metadata = False
            for regex in self.metadata_regex:
                if regex.search(context):
                    is_metadata = True
                    break
            if not is_metadata:
                filtered.append(num)
        return filtered

    def has_receipt_for_number(self, number: str, text: str) -> bool:
        """Проверяет, есть ли receipt (инструментальный вывод) для данного числа."""
        # Ищем число в контексте receipt-паттернов
        for pattern in self.receipt_regex:
            matches = pattern.findall(text)
            for match in matches:
                if number in match:
                    return True
        return False

    def check_grounded_numbers(self, text: str) -> tuple[float, int, int, list[str]]:
        """Проверяет grounded_numbers: доля чисел, подкреплённых receipt'ами.
        Возвращает: (ratio, grounded_count, total_count, ungrounded_numbers)
        """
        numbers = self.extract_numbers(text)
        if not numbers:
            return 1.0, 0, 0, []

        grounded = 0
        ungrounded = []
        for num in numbers:
            if self.has_receipt_for_number(num, text):
                grounded += 1
            else:
                ungrounded.append(num)

        ratio = grounded / len(numbers) if numbers else 1.0
        return ratio, grounded, len(numbers), ungrounded

    def _old_check_hollow_raw(self, text: str) -> tuple[bool, list[str]]:
        """Raw hollow check without text cleaning."""
        violations = []
        for pattern in self.hollow_regex:
            matches = pattern.findall(text)
            if matches:
                violations.extend(matches)
        return len(violations) == 0, violations

    def check_hollow(self, text: str) -> tuple[bool, list[str]]:
        """Проверяет на 'пустые обещания' (hollow patterns).
        Cleaned text is used to prevent self-referential detection from FAIL summaries.
        """
        cleaned = self._clean_text_for_hollow_check(text)
        violations = []
        for pattern in self.hollow_regex:
            matches = pattern.findall(cleaned)
            if matches:
                violations.extend(matches)
        return len(violations) == 0, violations

    def _clean_text_for_hollow_check(self, text: str) -> str:
        """Очистка текста перед проверкой на hollow-patterns."""
        # Удаляем блоки кода и markdown-форматирование, чтобы избежать ложных срабатываний
        cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)  # **bold** → bold
        cleaned = re.sub(r"\*([^*]+)\*", r"\1", text)      # *italic* → italic
        cleaned = re.sub(r"`([^`]+)`", r"\1", text)        # `code` → code
        # Удаляем ссылки
        cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
        # Удаляем JSON-блоки с метриками
        cleaned = re.sub(r"{grounded_numbers_ratio[^}]+}", "", cleaned)
        # Удаляем строку с метриками Evidence Gate
        cleaned = re.sub(r"\*\*Метрики:\*\*\s*\{.*?\}", "", cleaned, flags=re.DOTALL)
        # Удаляем блок нарушений
        cleaned = re.sub(r"\*\*Нарушения:\*\*.*?(?=\n\*\*|\Z)", "", cleaned, flags=re.DOTALL)
        return cleaned

    def check_receipts_exist(self, text: str) -> tuple[bool, int]:
        """Проверяет наличие хотя бы одного receipt в отчёте."""
        receipt_count = 0
        for pattern in self.receipt_regex:
            receipt_count += len(pattern.findall(text))
        return receipt_count > 0, receipt_count

    def check_diff_present(self, text: str) -> bool:
        """Проверяет, есть ли unified diff в отчёте (для код-фиксов)."""
        return bool(re.search(r"^@@\s*-\d+,\d+\s*\+\d+,\d+\s*@@", text, re.MULTILINE) or
                    re.search(r"^diff --git", text, re.MULTILINE))

    def validate(self, report_text: str, role: str = "") -> dict:
        """Полная валидация отчёта через Evidence Gate.
        Возвращает dict с результатами всех проверок.
        """
        results = {
            "role": role,
            "passed": True,
            "violations": [],
            "warnings": [],
            "metrics": {}
        }

        # 1. Grounded numbers check
        ratio, grounded, total, ungrounded = self.check_grounded_numbers(report_text)
        results["metrics"]["grounded_numbers_ratio"] = ratio
        results["metrics"]["grounded_count"] = grounded
        results["metrics"]["total_numbers"] = total
        results["metrics"]["ungrounded_numbers"] = ungrounded[:20]  # limit output

        if ratio < self.min_grounded_ratio:
            results["passed"] = False
            results["violations"].append(
                f"GROUNDED_NUMBERS_FAILED: {grounded}/{total} чисел имеют receipts "
                f"(ratio={ratio:.2f}, min={self.min_grounded_ratio})"
            )
            if ungrounded:
                results["violations"].append(f"  Неподкреплённые: {', '.join(ungrounded[:10])}")

        # 2. Hollow patterns check
        not_hollow, hollow_violations = self.check_hollow(report_text)
        if not not_hollow:
            results["passed"] = False
            results["violations"].append(
                f"HOLLOW_DETECTED: найдены паттерны пустых обещаний: {hollow_violations[:5]}"
            )

        # 3. Receipts existence check
        has_receipts, receipt_count = self.check_receipts_exist(report_text)
        results["metrics"]["receipt_count"] = receipt_count
        if not has_receipts:
            results["warnings"].append("NO_RECEIPTS: в отчёте не найдено инструментальных подтверждений")

        # 4. Diff presence check (для ролей-кодеров)
        if "coder" in role.lower() or "кодер" in role.lower():
            has_diff = self.check_diff_present(report_text)
            results["metrics"]["has_unified_diff"] = has_diff
            if not has_diff:
                results["warnings"].append("NO_DIFF: кодер-отчёт без unified diff (prose не становится патчар)")

        return results


def main():
    """CLI для Evidence Gate: python evidence_gate.py <report_file|-> [role]"""
    if len(sys.argv) < 2:
        print("Usage: evidence_gate.py <report_file|-> [role]")
        sys.exit(1)

    report_path = sys.argv[1]
    role = sys.argv[2] if len(sys.argv) > 2 else ""

    if report_path == "-":
        text = sys.stdin.read()
    else:
        report_path = Path(report_path)
        if not report_path.exists():
            print(f"File not found: {report_path}")
            sys.exit(1)
        text = report_path.read_text(encoding="utf-8", errors="replace")

    gate = EvidenceGate()
    result = gate.validate(text, role)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    sys.exit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()