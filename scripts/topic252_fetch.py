#!/usr/bin/env python3
"""topic252_fetch.py — наполняет очередь (topic252_queue.py) сообщениями из топика 252.

Режимы:
  manual   — читает текст из stdin или --file PATH (работает без бота)
  bot      — long-poll отдельного бота-ловушки (НЕ TotoMoto99Bot!)
  webhook  — поднимает HTTP-сервер, принимает апдейты Telegram

Примеры:
  echo "текст https://ссылка" | python3 topic252_fetch.py manual
  python3 topic252_fetch.py manual --file /tmp/dump.txt
  SUPERVISOR_BOT_TOKEN=123:ABC TOPIC_CHAT_ID=-1004431090317 TOPIC_THREAD_ID=252 \\
      python3 topic252_fetch.py bot
  python3 topic252_fetch.py webhook --port 8899

Ограничения Bot API (см. references/telegram-topic-pipeline.md):
  * история чата недоступна (getChatHistory → 404), только live-захват;
  * один getUpdates на бота — второй инстанс получит Conflict;
  * webhook и long-poll взаимоисключающие.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from topic252_queue import add_message, extract_urls  # noqa: E402

API = "https://api.telegram.org/bot{token}/{method}"
DEFAULT_CHAT_ID = os.environ.get("TOPIC_CHAT_ID", "-1004431090317")
DEFAULT_THREAD_ID = os.environ.get("TOPIC_THREAD_ID", "252")


def _api(token: str, method: str, params: dict | None = None, timeout: int = 30):
    url = API.format(token=token, method=method)
    data = None
    if params:
        data = json.dumps(params).encode()
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json"} if data else {},
    )
    ctx = ssl.create_default_context()
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return json.loads(r.read().decode())


def ingest_update(update: dict, *, chat_id: str | None = None,
                  thread_id: str | None = None) -> int | None:
    """Разобрать один Telegram-апдейт и положить в очередь."""
    msg = update.get("message") or update.get("channel_post") or update.get("edited_message")
    if not msg:
        return None
    text = msg.get("text") or msg.get("caption") or ""
    urls = extract_urls(text)
    # entity-ссылки: text_link (скрытые URL) и url
    for ent in (msg.get("entities") or []) + (msg.get("caption_entities") or []):
        if ent.get("type") == "text_link" and ent.get("url"):
            if ent["url"] not in urls:
                urls.append(ent["url"])
    if not text and not urls:
        return None
    chat = str(msg.get("chat", {}).get("id", chat_id or ""))
    thread = str(msg.get("message_thread_id", thread_id or ""))
    if chat_id and chat != str(chat_id):
        return None
    if thread_id and thread and thread != str(thread_id):
        return None
    author = msg.get("from", {}).get("username") or msg.get("from", {}).get("first_name", "")
    from datetime import datetime, timezone
    ts = datetime.fromtimestamp(msg.get("date", 0) or time.time(),
                               tz=timezone.utc).astimezone().isoformat(timespec="seconds")
    return add_message(text, tg_msg_id=msg.get("message_id"), chat_id=chat,
                       thread_id=thread, author=author, ts=ts, urls=urls)


# ---------------------------------------------------------------- mode: manual
def mode_manual(args) -> int:
    if args.file:
        text = Path(args.file).expanduser().read_text(encoding="utf-8")
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()]
    else:
        text = sys.stdin.read()
        blocks = [b.strip() for b in text.split("\n\n") if b.strip()] or \
                 ([text.strip()] if text.strip() else [])
    added = 0
    for b in blocks:
        if add_message(b, chat_id=DEFAULT_CHAT_ID, thread_id=DEFAULT_THREAD_ID,
                       author="manual") is not None:
            added += 1
    print(f"manual: добавлено {added} из {len(blocks)} (остальное — дубли)")
    return 0


# ------------------------------------------------------------------- mode: bot
def mode_bot(args) -> int:
    token = args.token or os.environ.get("SUPERVISOR_BOT_TOKEN") or os.environ.get("TOPIC_BOT_TOKEN")
    if not token:
        print("нет токена: задай SUPERVISOR_BOT_TOKEN (отдельный бот-ловушка, "
              "НЕ TotoMoto99Bot — он занят polling'ом delivery)", file=sys.stderr)
        return 2
    offset = None
    print(f"bot: polling запущен, топик {args.chat_id}:{args.thread_id}")
    while True:
        try:
            params = {"timeout": 50, "allowed_updates": ["message", "channel_post"]}
            if offset:
                params["offset"] = offset
            resp = _api(token, "getUpdates", params, timeout=70)
            if not resp.get("ok"):
                print(f"api error: {resp}", file=sys.stderr)
                time.sleep(5)
                continue
            for upd in resp.get("result", []):
                offset = upd["update_id"] + 1
                rid = ingest_update(upd, chat_id=args.chat_id, thread_id=args.thread_id)
                if rid:
                    print(f"queued id={rid}", flush=True)
        except KeyboardInterrupt:
            print("bot: остановлен")
            return 0
        except Exception as exc:  # network hiccups, Conflict от чужого polling
            print(f"poll error: {exc}", file=sys.stderr)
            time.sleep(5)


# --------------------------------------------------------------- mode: webhook
def mode_webhook(args) -> int:
    token = args.token or os.environ.get("SUPERVISOR_BOT_TOKEN")
    chat_id, thread_id = args.chat_id, args.thread_id

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            try:
                upd = json.loads(raw.decode())
                rid = ingest_update(upd, chat_id=chat_id, thread_id=thread_id)
                print(f"webhook: update={upd.get('update_id')} queued={rid}", flush=True)
                body = b'{"ok":true}'
            except Exception as exc:
                print(f"webhook error: {exc}", file=sys.stderr)
                body = b'{"ok":false}'
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *a):  # тишина в stdout
            pass

    srv = ThreadingHTTPServer(("0.0.0.0", args.port), Handler)
    print(f"webhook: слушаю :{args.port} (chat={chat_id} thread={thread_id})")
    if token:
        hook = args.public_url or f"http://127.0.0.1:{args.port}/webhook"
        try:
            print(_api(token, "setWebhook", {"url": hook,
                                             "allowed_updates": ["message", "channel_post"]}))
        except Exception as exc:
            print(f"setWebhook failed: {exc}", file=sys.stderr)
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("webhook: остановлен")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="topic252 fetcher")
    p.add_argument("mode", choices=["manual", "bot", "webhook"])
    p.add_argument("--file", help="файл с текстом (manual)")
    p.add_argument("--token", help="токен бота-ловушки")
    p.add_argument("--chat-id", default=DEFAULT_CHAT_ID)
    p.add_argument("--thread-id", default=DEFAULT_THREAD_ID)
    p.add_argument("--port", type=int, default=8899)
    p.add_argument("--public-url", help="HTTPS-URL вебхука")
    args = p.parse_args()
    return {"manual": mode_manual, "bot": mode_bot, "webhook": mode_webhook}[args.mode](args)


if __name__ == "__main__":
    sys.exit(main())
