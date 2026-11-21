#!/usr/bin/env python3
"""topic252_queue.py — sqlite-очередь сырых сообщений из Telegram-топика 252.

Схема:
  messages(id INTEGER PK AUTOINCREMENT,
           tg_msg_id INTEGER, chat_id TEXT, thread_id TEXT,
           text TEXT, urls TEXT (json list), author TEXT,
           ts TEXT, processed INTEGER DEFAULT 0, digest TEXT)

Идемпотентно: уникальный индекс (chat_id, thread_id, tg_msg_id), повторный
инсерт того же сообщения игнорируется (INSERT OR IGNORE).

Питон только stdlib. Путь к БД: env TOPIC252_DB, по умолчанию
~/.hermes/cron/topic252_queue.db
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(os.environ.get(
    "TOPIC252_DB", str(Path.home() / ".hermes" / "cron" / "topic252_queue.db")
)).expanduser()

URL_RE = re.compile(r"https?://[^\s)>\]\"']+")

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    tg_msg_id  INTEGER,
    chat_id    TEXT NOT NULL DEFAULT '',
    thread_id  TEXT NOT NULL DEFAULT '',
    text       TEXT NOT NULL,
    urls       TEXT NOT NULL DEFAULT '[]',
    author     TEXT DEFAULT '',
    ts         TEXT NOT NULL,
    processed  INTEGER NOT NULL DEFAULT 0,
    digest     TEXT DEFAULT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_tg ON messages(chat_id, thread_id, tg_msg_id);
CREATE INDEX IF NOT EXISTS idx_processed ON messages(processed);
"""


def connect(db_path: Path | None = None) -> sqlite3.Connection:
    path = Path(db_path or DB_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(path))
    con.executescript(SCHEMA)
    con.row_factory = sqlite3.Row
    return con


def extract_urls(text: str) -> list[str]:
    """Все ссылки из текста, нормализованные и без дублей (порядок сохранён)."""
    out: list[str] = []
    for m in URL_RE.findall(text or ""):
        u = m.rstrip(".,;:!?").strip()
        if u and u not in out:
            out.append(u)
    return out


def add_message(text: str, *, tg_msg_id: int | None = None,
                chat_id: str = "", thread_id: str = "",
                author: str = "", ts: str | None = None,
                urls: list[str] | None = None,
                db_path: Path | None = None) -> int | None:
    """Добавить сообщение. Возвращает rowid новой записи или None, если дубль."""
    text = (text or "").strip()
    if not text:
        return None
    if tg_msg_id is None:
        # manual-режим: синтетический id из хэша текста, чтобы дедуп работал
        tg_msg_id = -abs(hash(text)) % (10 ** 12)
    chat_id = str(chat_id or "")
    thread_id = str(thread_id or "")
    urls = urls if urls is not None else extract_urls(text)
    ts = ts or datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")
    con = connect(db_path)
    try:
        cur = con.execute(
            "INSERT OR IGNORE INTO messages"
            " (tg_msg_id, chat_id, thread_id, text, urls, author, ts)"
            " VALUES (?,?,?,?,?,?,?)",
            (tg_msg_id, chat_id, thread_id, text, json.dumps(urls, ensure_ascii=False),
             author, ts),
        )
        con.commit()
        return cur.lastrowid if cur.rowcount else None
    finally:
        con.close()


def pending(limit: int = 50, db_path: Path | None = None) -> list[sqlite3.Row]:
    con = connect(db_path)
    try:
        return list(con.execute(
            "SELECT * FROM messages WHERE processed=0 ORDER BY id ASC LIMIT ?",
            (limit,),
        ))
    finally:
        con.close()


def mark_processed(msg_id: int, digest: str = "", db_path: Path | None = None) -> None:
    con = connect(db_path)
    try:
        con.execute("UPDATE messages SET processed=1, digest=? WHERE id=?",
                    (digest, msg_id))
        con.commit()
    finally:
        con.close()


def stats(db_path: Path | None = None) -> str:
    con = connect(db_path)
    try:
        total = con.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
        unproc = con.execute(
            "SELECT COUNT(*) FROM messages WHERE processed=0").fetchone()[0]
        return f"queue: {total} всего, {unproc} необработано ({DB_PATH})"
    finally:
        con.close()


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stats"
    if cmd == "stats":
        print(stats())
    elif cmd == "add":
        text = sys.stdin.read() if len(sys.argv) < 3 else " ".join(sys.argv[2:])
        rid = add_message(text)
        print(f"added id={rid}" if rid else "duplicate — skipped")
    elif cmd == "pending":
        for r in pending():
            print(f"[{r['id']}] {r['ts']} {r['text'][:120]!r} urls={r['urls']}")
    else:
        print(f"unknown cmd: {cmd}", file=sys.stderr)
        sys.exit(2)
