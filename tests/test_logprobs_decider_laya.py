"""Laya-совместимый интерфейс logprobs_decider.

Утилита сохраняет прежний CLI (`decide`/`score`), но источником решения и
вероятностей становится локальная Laya через `laya_bridge.py raw`.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "logprobs_decider.py"
SPEC = importlib.util.spec_from_file_location("logprobs_decider", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class _Completed:
    def __init__(self, stdout: str, returncode: int = 0):
        self.stdout = stdout
        self.stderr = ""
        self.returncode = returncode


def test_decide_uses_laya_choice_and_returns_compatible_probabilities(monkeypatch):
    calls: list[dict] = []

    def fake_raw(state: str, question: str, options: list[str], timeout: int = 60) -> dict:
        calls.append({"state": state, "question": question, "options": options})
        return {
            "answers": {
                "decision": {
                    "choice": "средне",
                    "answer_confidence": 0.8,
                }
            },
            "routing": {"model": "multilingual"},
        }

    monkeypatch.setattr(MODULE, "ask_laya", fake_raw)

    result = MODULE.decide(
        "состояние проекта",
        "Какова категория находки?",
        ["критично", "средне", "низко"],
    )

    assert result["choice"] == "средне"
    assert result["confidence"] == 0.8
    assert result["probs"]["средне"] == 0.8
    assert sum(result["probs"].values()) == 1.0
    assert result["model"] == "laya-multilingual"
    assert calls == [{
        "state": "состояние проекта",
        "question": "Какова категория находки?",
        "options": ["критично", "средне", "низко"],
    }]


def test_score_maps_laya_relevance_probability(monkeypatch):
    def fake_raw(state: str, question: str, options: list[str], timeout: int = 60) -> dict:
        relevant = "релевантная запись" in state
        return {
            "answers": {
                "decision": {
                    "choice": "relevant" if relevant else "irrelevant",
                    "answer_confidence": 0.9 if relevant else 0.2,
                }
            },
            "routing": {"model": "multilingual"},
        }

    monkeypatch.setattr(MODULE, "ask_laya", fake_raw)

    result = MODULE.score(
        ["релевантная запись", "мусор"],
        state_context="живой код",
        question="Подходит ли запись?",
    )

    assert result["items"][0]["p_relevant"] == 0.9
    assert result["items"][0]["choice"] == "relevant"
    assert result["items"][1]["p_relevant"] == 0.8
    assert result["items"][1]["choice"] == "irrelevant"
    assert result["model"] == "laya-multilingual"


def test_ask_laya_invokes_local_bridge_in_raw_mode(monkeypatch, tmp_path):
    bridge = tmp_path / "bridge.py"
    bridge.write_text("# test bridge\n", encoding="utf-8")
    payload = tmp_path / "payload.json"
    payload.write_text("{}", encoding="utf-8")
    captured: dict[str, object] = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return _Completed(json.dumps({
            "answers": {"decision": {"choice": "yes", "answer_confidence": 0.7}},
            "routing": {"model": "multilingual"},
        }))

    monkeypatch.setattr(MODULE, "BRIDGE_SCRIPT", bridge)
    monkeypatch.setattr(MODULE.subprocess, "run", fake_run)

    result = MODULE.ask_laya("state", "question?", ["yes", "no"])

    assert result["answers"]["decision"]["choice"] == "yes"
    cmd = captured["cmd"]
    assert cmd[0] == str(MODULE.LAYA_PYTHON)
    assert cmd[1] == str(bridge)
    assert "raw" in cmd
    assert "--raw" in cmd
    assert "--no-service" not in cmd
    assert isinstance(captured["kwargs"]["capture_output"], bool)
