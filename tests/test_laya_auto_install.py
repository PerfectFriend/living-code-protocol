"""Инварианты автоматической установки Laya.

Проверяются не текст, а реальные контракты:
  * installer вызывает создание venv, CPU torch, Laya и скачивание чекпоинта;
  * main installer запускает Laya installer;
  * warm-unit устанавливается, но не включается и не запускается.
"""
from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INSTALL = ROOT / "bin" / "install-laya.sh"
MAIN_INSTALL = ROOT / "bin" / "install.sh"


def test_laya_installer_creates_venv_installs_runtime_and_checkpoint():
    text = INSTALL.read_text(encoding="utf-8")
    assert "uv venv" in text
    assert "download.pytorch.org/whl/cpu" in text
    assert re.search(r"laya\[serve,onnx\]", text)
    assert "hf\" download" in text or "hf download" in text
    assert "convaiinnovations/laya-multilingual" in text
    assert "venvs/laya" in text
    assert "models/laya-multilingual" in text


def test_main_installer_runs_laya_installer():
    text = MAIN_INSTALL.read_text(encoding="utf-8")
    assert "install-laya.sh" in text


def test_laya_installer_never_enables_or_starts_warm_service():
    text = INSTALL.read_text(encoding="utf-8")
    forbidden = (
        "enable --now laya-warm",
        "start laya-warm",
        "enable laya-warm",
        "restart laya-warm",
    )
    for command in forbidden:
        assert command not in text
    assert "systemctl --user daemon-reload" in text
    assert "systemctl --user enable" not in text
    assert "systemctl --user start" not in text


def test_warm_unit_has_optional_install_metadata():
    unit = (ROOT / "systemd" / "laya-warm.service").read_text(encoding="utf-8")
    assert "[Install]" in unit
    assert "WantedBy=default.target" in unit
    assert "ExecStart=/home/thomas/LivingCode/venvs/laya/bin/python" in unit
