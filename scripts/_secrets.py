#!/usr/bin/env python3
"""_secrets.py — загрузка секретов из ~/.hermes/secrets (файлы 600) в os.environ.

Секреты НЕ хранятся в plaintext-конфигах и git: только в ~/.hermes/secrets/.
Вызов: load_cathedral_token() — подхватит CATHEDRAL_BOT_TOKEN, если env пуст.
"""
import os

SECRETS_DIR = os.path.expanduser("~/.hermes/secrets")


def _read(name: str) -> str:
    try:
        with open(os.path.join(SECRETS_DIR, name), encoding="utf-8") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def load_cathedral_token() -> None:
    if not os.environ.get("CATHEDRAL_BOT_TOKEN"):
        t = _read("cathedral_bot_token")
        if t:
            os.environ["CATHEDRAL_BOT_TOKEN"] = t
