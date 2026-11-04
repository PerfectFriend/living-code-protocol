#!/usr/bin/env python3
"""
L3 Independent Review Layer — отдельный критик-агент с чистым контекстом.

Принцип: Аудитор работает в том же контексте, что и Кодеры.
L3 критик получает ТОЛЬКО:
- deliverable (что проверяем)
- criteria (критерии приёмки)

И выдаёт независимый вердикт: stabilen / regress / nuzhna_rabota
"""

import os
import sys
import json
import subprocess
import re
from pathlib import Path
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime


@dataclass
class CriticVerdict:
    """Вердикт L3 критика."""
    verdict: str  # stabilen | regress | nuzhna_rabota
    confidence: float  # 0.0 - 1.0
    evidence: List[str]  # конкретные доказательства
    blockers: List[str]  # что блокирует stabilen
    recommendations: List[str]  # что сделать для стабилизации


class L3Critic:
    """L3 Independent Review — измеренная верификация без LLM-глотания."""
    
    def __init__(self, project_path: str):
        self.project_path = Path(project_path).resolve()
        self.evidence = []
        self.blockers = []
        self.recommendations = []
    
    def run_verification(self, deliverable: str, criteria: Dict) -> CriticVerdict:
        """Запускает полную верификацию доставленного артефакта."""
        self.evidence = []
        self.blockers = []
        self.recommendations = []
        
        # 1. Прогон тестов
        self._run_tests(criteria)
        
        # 2. CLI smoke test
        self._run_cli_smoke(criteria)
        
        # 3. Рендер UI (если применимо)
        self._check_ui_render(criteria)
        
        # 4. Проверка артефактов (файлы, отчёты)
        self._check_artifacts(deliverable, criteria)
        
        # 5. Формируем вердикт
        return self._form_verdict()
    
    def _run_tests(self, criteria: Dict):
        """Прогоняет тесты проекта."""
        test_cmd = criteria.get('test_command', 'pytest -q')
        expected_pass = criteria.get('min_tests_pass', 0)
        
        try:
            # Use python -m pytest to ensure correct Python environment
            if test_cmd.startswith('pytest'):
                test_cmd = test_cmd.replace('pytest', 'python -m pytest', 1)
            result = subprocess.run(
                test_cmd,
                shell=True,
                cwd=self.project_path,
                capture_output=True,
                text=True,
                timeout=300
            )
            # Парсим количество пройденных тестов
            passed_match = re.search(r'(\d+)\s+passed', result.stdout)
            failed_match = re.search(r'(\d+)\s+failed', result.stdout)
            error_match = re.search(r'(\d+)\s+error', result.stdout)
            
            passed = int(passed_match.group(1)) if passed_match else 0
            failed = int(failed_match.group(1)) if failed_match else 0
            errors = int(error_match.group(1)) if error_match else 0
            
            if result.returncode == 0 and failed == 0 and errors == 0:
                self.evidence.append(f"✅ Тесты: {passed} passed, 0 failed (команда: {test_cmd})")
                if passed >= expected_pass:
                    self.evidence.append(f"✅ Минимум тестов ({expected_pass}) достижен")
                else:
                    self.blockers.append(f"❌ Тестов мало: {passed} < {expected_pass} (min_tests_pass)")
            else:
                self.blockers.append(f"❌ Тесты упали: {passed} passed, {failed} failed, {errors} errors")
                self.evidence.append(f"stdout: {result.stdout[-500:]}")
                self.evidence.append(f"stderr: {result.stderr[-500:]}")
        except subprocess.TimeoutExpired:
            self.blockers.append(f"❌ Тесты таймаут (>300s): {test_cmd}")
        except Exception as e:
            self.blockers.append(f"❌ Ошибка прогона тестов: {type(e).__name__}: {e}")
    
    def _run_cli_smoke(self, criteria: Dict):
        """Проверяет CLI команды."""
        cli_checks = criteria.get('cli_checks', [])
        for check in cli_checks:
            cmd = check.get('command')
            expected_exit = check.get('expected_exit', 0)
            expected_in_output = check.get('expected_in_output', [])
            forbidden_in_output = check.get('forbidden_in_output', [])
            
            try:
                result = subprocess.run(
                    cmd,
                    shell=True,
                    cwd=self.project_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == expected_exit:
                    self.evidence.append(f"✅ CLI: {cmd} → exit {result.returncode}")
                else:
                    self.blockers.append(f"❌ CLI: {cmd} → exit {result.returncode} (ожидался {expected_exit})")
                    self.evidence.append(f"stdout: {result.stdout[-300:]}")
                    self.evidence.append(f"stderr: {result.stderr[-300:]}")
                
                for expected in expected_in_output:
                    if expected in result.stdout or expected in result.stderr:
                        self.evidence.append(f"  ✓ найдено в выводе: '{expected}'")
                    else:
                        self.blockers.append(f"  ✗ НЕ найдено в выводе: '{expected}'")
                
                for forbidden in forbidden_in_output:
                    if forbidden in result.stdout or forbidden in result.stderr:
                        self.blockers.append(f"  ✗ ЗАПРЕЩЁННОЕ найдено в выводе: '{forbidden}'")
                    else:
                        self.evidence.append(f"  ✓ запрещённое отсутствует: '{forbidden}'")
                        
            except Exception as e:
                self.blockers.append(f"❌ CLI ошибка: {cmd} — {type(e).__name__}: {e}")
    
    def _check_ui_render(self, criteria: Dict):
        """Проверяет рендеринг UI (если есть веб-дашборд)."""
        ui_checks = criteria.get('ui_checks', [])
        for check in ui_checks:
            url = check.get('url')
            expected_status = check.get('expected_status', 200)
            expected_content = check.get('expected_content', [])
            
            try:
                import urllib.request
                req = urllib.request.Request(url)
                with urllib.request.urlopen(req, timeout=10) as response:
                    status = response.getcode()
                    content = response.read().decode('utf-8', errors='replace')
                
                if status == expected_status:
                    self.evidence.append(f"✅ UI: {url} → HTTP {status}")
                else:
                    self.blockers.append(f"❌ UI: {url} → HTTP {status} (ожидался {expected_status})")
                
                for expected in expected_content:
                    if expected in content:
                        self.evidence.append(f"  ✓ UI содержит: '{expected}'")
                    else:
                        self.blockers.append(f"  ✗ UI НЕ содержит: '{expected}'")
                        
            except Exception as e:
                self.blockers.append(f"❌ UI проверка ошибка: {url} — {type(e).__name__}: {e}")
    
    def _check_artifacts(self, deliverable: str, criteria: Dict):
        """Проверяет наличие и корректность артефактов."""
        artifact_checks = criteria.get('artifacts', [])
        for check in artifact_checks:
            path = check.get('path')
            should_exist = check.get('should_exist', True)
            min_size = check.get('min_size', 0)
            expected_content = check.get('expected_content', [])
            
            full_path = self.project_path / path if not os.path.isabs(path) else Path(path)
            
            if should_exist:
                if full_path.exists():
                    size = full_path.stat().st_size
                    if size >= min_size:
                        self.evidence.append(f"✅ Артефакт: {path} ({size} байт)")
                    else:
                        self.blockers.append(f"❌ Артефакт слишком мал: {path} ({size} < {min_size} байт)")
                    
                    if expected_content:
                        try:
                            content = full_path.read_text(encoding='utf-8', errors='replace')
                            for expected in expected_content:
                                if expected in content:
                                    self.evidence.append(f"  ✓ Артефакт содержит: '{expected}'")
                                else:
                                    self.blockers.append(f"  ✗ Артефакт НЕ содержит: '{expected}'")
                        except Exception as e:
                            self.blockers.append(f"❌ Не удалось прочитать артефакт: {path} — {e}")
                else:
                    self.blockers.append(f"❌ Артефакт отсутствует: {path}")
            else:
                if not full_path.exists():
                    self.evidence.append(f"✅ Артефакт отсутствует (как и ожидалось): {path}")
                else:
                    self.blockers.append(f"❌ Артефакт должен отсутствовать, но существует: {path}")
    
    def _form_verdict(self) -> CriticVerdict:
        """Формирует финальный вердикт на основе собранных доказательств."""
        has_blockers = len(self.blockers) > 0
        has_evidence = len(self.evidence) > 0
        
        if has_blockers:
            verdict = "regress"
            confidence = 0.9
        elif has_evidence:
            verdict = "stabilen"
            confidence = 0.85
        else:
            verdict = "nuzhna_rabota"
            confidence = 0.5
        
        return CriticVerdict(
            verdict=verdict,
            confidence=confidence,
            evidence=self.evidence,
            blockers=self.blockers,
            recommendations=self.recommendations
        )


def main():
    """CLI для L3 критика."""
    import argparse
    
    ap = argparse.ArgumentParser(description='L3 Independent Review Critic')
    ap.add_argument('--project', required=True, help='Путь к проекту')
    ap.add_argument('--deliverable', required=True, help='Что проверяем (описание)')
    ap.add_argument('--criteria', required=True, help='JSON с критериями приёмки')
    ap.add_argument('--output', help='Файл для записи вердикта (JSON)')
    args = ap.parse_args()
    
    criteria = json.loads(args.criteria)
    critic = L3Critic(args.project)
    verdict = critic.run_verification(args.deliverable, criteria)
    
    result = asdict(verdict)
    out_text = json.dumps(result, ensure_ascii=False, indent=2)
    print(out_text)

    out_path = args.output
    if not out_path:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        slug = "".join(c if c.isalnum() else "_" for c in args.deliverable).strip("_")[:60] or "verdict"
        out_path = Path(f"/home/thomas/LivingCode/runtime/l3_verdicts/{stamp}_{slug}.json")
        out_path.parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(out_text, encoding="utf-8")
    print(f"[l3_critic] сохранено: {out_path}", file=sys.stderr)
    
    # Exit code для CI
    if verdict.verdict == "stabilen":
        sys.exit(0)
    elif verdict.verdict == "regress":
        sys.exit(1)
    else:
        sys.exit(2)


if __name__ == '__main__':
    main()