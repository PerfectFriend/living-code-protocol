"""Инварианты единой модели Протокола Живого Кода.

Тест намеренно проверяет не отдельные строки, а реальные контуры маршрутизации:
реестр кронов, shell-обёртки, белый список движка, ростер и конфиг Hermes.
"""
from __future__ import annotations

import ast
import json
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
MODEL = "minimaxai/minimax-m3.1-flash"
PROVIDER = "nvidia"
PAIR = (MODEL, PROVIDER)


def _literal(node: ast.AST, env: dict[str, object] | None = None):
    env = env or {}
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "frozenset":
        return frozenset(_literal(node.args[0], env))
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        values = [_literal(item, env) for item in node.elts]
        return tuple(values) if isinstance(node, ast.Tuple) else values
    if isinstance(node, ast.Name) and node.id in env:
        return env[node.id]
    return ast.literal_eval(node)


def _wrapper_constants(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, object] = {}
    env: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            if isinstance(target, ast.Name):
                try:
                    env[target.id] = _literal(node.value, env)
                except (ValueError, TypeError):
                    pass
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name):
            continue
        if target.id in {"ALLOWED_PAIRS", "FREE_POOL", "DEFAULT_PAIR"}:
            values[target.id] = _literal(node.value, env)
    return values


def test_agent_wrapper_allows_only_minimax_m31():
    values = _wrapper_constants(SCRIPTS / "living_code_agent_wrapper.py")
    assert values["ALLOWED_PAIRS"] == frozenset({PAIR})
    assert values["FREE_POOL"] == (PAIR,)
    assert values["DEFAULT_PAIR"] == PAIR


def test_roster_gate_allows_only_minimax_m31():
    values = _wrapper_constants(SCRIPTS / "check_roster.py")
    assert values["ALLOWED_PAIRS"] == frozenset({PAIR})


def test_repository_cron_registry_pins_every_job_to_minimax():
    data = json.loads((ROOT / "jobs" / "jobs.json").read_text(encoding="utf-8"))
    jobs = data["jobs"]
    assert jobs
    offenders = [
        (job.get("name"), job.get("model"), job.get("provider"))
        for job in jobs
        if (job.get("model"), job.get("provider")) != PAIR
    ]
    assert offenders == []


def test_live_role_wrappers_pass_minimax_to_engine():
    offenders: list[str] = []
    for path in sorted((SCRIPTS / "wrappers").glob("wrapper_*.sh")):
        text = path.read_text(encoding="utf-8")
        if "living_code_agent_wrapper.py" not in text:
            continue
        if f'"{MODEL}" "{PROVIDER}"' not in text:
            offenders.append(path.name)
    assert offenders == []


def test_hermes_config_primary_and_fallback_are_minimax():
    config = yaml.safe_load((ROOT / "hermes-config" / "config.yaml").read_text(encoding="utf-8"))
    assert config["model"]["default"] == MODEL
    assert config["model"]["provider"] == PROVIDER
    fallbacks = config.get("fallback_providers", [])
    assert fallbacks == [{"provider": PROVIDER, "model": MODEL}]


def test_roster_snapshot_pins_every_role_to_minimax():
    data = json.loads((ROOT / "roster.json").read_text(encoding="utf-8"))
    roles = data["roles"]
    assert roles
    offenders = [
        (name, role.get("model"), role.get("provider"))
        for name, role in roles.items()
        if (role.get("model"), role.get("provider")) != PAIR
    ]
    assert offenders == []
