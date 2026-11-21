#!/usr/bin/env python3
"""logprobs_decider — типизированные решения через локального судью Laya.

Исторически утилита считала вероятности опций через ``logprobs`` удалённой
модели. Единая удалённая модель протокола — MiniMax M3.1 Flash — ``logprobs``
не возвращает, поэтому источником решения стал локальный Laya.

Публичный CLI и ключи ответа сохранены:
  * ``decide`` → ``choice``, ``confidence``, ``probs``;
  * ``score``  → ``items[].p_relevant``, ``choice``, ``confidence``.

Laya выдаёт выбранный вариант и уверенность в выборе, а не полное
распределение. Поэтому распределение детерминированно восстанавливается:
выбранный вариант получает ``answer_confidence``, остальные делят остаток
поровну. Это НЕ logprobs и не фабрикация вероятностей API: поле
``probability_source`` явно сообщает источник.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


HERE = Path(__file__).resolve().parent
# В worktree репозитория корнем является его родитель, но живой Laya всегда
# живёт в ~/LivingCode/venvs/laya. Поддерживаем оба layout явно.
ROOT = Path(os.environ.get("LAYA_ROOT", "/home/thomas/LivingCode"))
BRIDGE_SCRIPT = HERE / "laya_bridge.py"
LAYA_PYTHON = Path(os.environ.get(
    "LAYA_PYTHON",
    str(ROOT / "venvs" / "laya" / "bin" / "python"),
))
DEFAULT_MODEL = "laya-multilingual"
DEFAULT_MAX_CHARS = 4000


def ask_laya(state: str, question: str, options: list[str], timeout: int = 60) -> dict:
    """Запрашивает локальную Laya через raw-режим ``laya_bridge.py``."""
    payload = {
        "state": state,
        "questions": {
            "decision": {
                "type": "choice",
                "instructions": question,
                "criteria": {option: option for option in options},
            }
        },
    }

    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", suffix=".json", prefix="decider_",
        delete=False,
    ) as handle:
        json.dump(payload, handle, ensure_ascii=False)
        payload_path = handle.name

    cmd = [
        str(LAYA_PYTHON),
        str(BRIDGE_SCRIPT),
        "raw",
        "--raw",
        payload_path,
        "--max-chars",
        str(DEFAULT_MAX_CHARS),
    ]
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"laya_timeout: {exc}") from exc
    finally:
        try:
            os.unlink(payload_path)
        except OSError:
            pass

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(f"laya_failed rc={completed.returncode}: {detail}")

    output = (completed.stdout or "").strip()
    if not output:
        raise RuntimeError("laya_empty_response")
    try:
        return json.loads(output.splitlines()[-1])
    except (ValueError, IndexError) as exc:
        raise RuntimeError(f"laya_invalid_response: {output[:200]}") from exc


def _decision_from_laya(response: dict) -> tuple[str, float]:
    answer = response.get("answers", {}).get("decision", {})
    choice = answer.get("choice")
    if not choice:
        raise RuntimeError("laya_missing_choice")
    confidence = answer.get("answer_confidence")
    if confidence is None:
        confidence = answer.get("noul")
    try:
        confidence = float(confidence)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("laya_missing_confidence") from exc
    confidence = min(1.0, max(0.0, confidence))
    return str(choice), confidence


def _probabilities(choice: str, confidence: float, options: list[str]) -> dict[str, float]:
    """Совместимое распределение из выбора Laya и уверенности в выборе."""
    if choice not in options:
        raise RuntimeError(f"laya_unknown_choice: {choice}")
    if len(options) == 1:
        return {choice: 1.0}

    remainder = (1.0 - confidence) / (len(options) - 1)
    probs = {
        option: (confidence if option == choice else remainder)
        for option in options
    }
    last = options[-1]
    probs[last] = round(1.0 - sum(probs[o] for o in options[:-1]), 10)
    return {option: round(value, 4) for option, value in probs.items()}


def decide(state: str, question: str, options: list[str], timeout: int = 60) -> dict:
    response = ask_laya(state, question, options, timeout=timeout)
    choice, confidence = _decision_from_laya(response)
    probs = _probabilities(choice, confidence, options)
    routing = response.get("routing", {})
    return {
        "choice": choice,
        "confidence": confidence,
        "probs": probs,
        "raw_first_token": None,
        "model": DEFAULT_MODEL,
        "routing_model": routing.get("model"),
        "probability_source": "laya_answer_confidence",
    }


def score(
    lines: list[str],
    state_context: str = "",
    question: str = "Which option fits best?",
    timeout: int = 60,
) -> dict:
    items = []
    for line in lines:
        state = f"Контекст: {state_context}\nЗапись: {line}" if state_context else line
        try:
            result = decide(
                state,
                question,
                ["irrelevant", "relevant"],
                timeout=timeout,
            )
            items.append({
                "text": line[:120],
                "p_relevant": result["probs"].get("relevant"),
                "choice": result["choice"],
                "confidence": result["confidence"],
            })
        except Exception as exc:  # noqa: BLE001 — ошибка одной строки не роняет batch
            items.append({"text": line[:120], "error": str(exc)})
    return {
        "items": items,
        "model": DEFAULT_MODEL,
        "probability_source": "laya_answer_confidence",
    }


def _read_lines(args) -> list[str]:
    if args.file:
        text = Path(args.file).read_text(encoding="utf-8", errors="replace")
    else:
        text = sys.stdin.read()
    return [line.strip() for line in text.splitlines() if line.strip()][:30]


def main() -> int:
    parser = argparse.ArgumentParser(description="Типизированный decider через локальную Laya")
    parser.add_argument("mode", choices=["decide", "score"])
    parser.add_argument("--state", default="")
    parser.add_argument("--state-context", default="")
    parser.add_argument("--question", default="Which option fits best?")
    parser.add_argument("--options", default="yes,no")
    parser.add_argument("--model", default=os.environ.get("DECIDER_MODEL", DEFAULT_MODEL))
    parser.add_argument("--timeout", type=int, default=60)
    parser.add_argument("--file", default=None)
    args = parser.parse_args()

    if not LAYA_PYTHON.exists():
        print(json.dumps({
            "error": f"laya_python_not_found: {LAYA_PYTHON}",
            "model": DEFAULT_MODEL,
        }))
        return 2

    if args.mode == "decide":
        options = [option.strip() for option in args.options.split(",") if option.strip()]
        if len(options) < 2:
            print(json.dumps({"error": "нужно минимум две опции"}))
            return 2
        try:
            result = decide(args.state, args.question, options, timeout=args.timeout)
        except Exception as exc:  # noqa: BLE001
            print(json.dumps({"error": str(exc), "model": DEFAULT_MODEL}))
            return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0

    lines = _read_lines(args)
    if not lines:
        print(json.dumps({"error": "нет строк"}))
        return 1
    result = score(
        lines,
        state_context=args.state_context,
        question=args.question,
        timeout=args.timeout,
    )
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
