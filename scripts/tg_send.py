#!/usr/bin/env python3
"""Отправка сообщений в телеграм-бот протокола Живого Кода — напрямую через Bot API.

Зачем не `hermes send`: профиль default (владелец крон-заданий протокола) не имеет
TELEGRAM_BOT_TOKEN, а шлюз уже держит поллинг этого токена в профиле cathedral.
sendMessage — метод отправки, он не требует getUpdates и не конфликтует с
работающим поллингом. Ноль изменений в конфигурации шлюза.

Токен ищется по порядку:
  1) переменная окружения TG_BOT_TOKEN
  2) ~/.hermes/profiles/thomas/.env      (TELEGRAM_BOT_TOKEN=...)
  3) ~/.hermes/.env                      (TELEGRAM_BOT_TOKEN=...)

Использование:
  tg_send.py "текст сообщения"
  tg_send.py MEDIA:/path/report.md "подпись к файлу"   (отправка документа)
  TG_CHAT_ID/-100..., TG_THREAD_ID/252 управляют целью.

Код выхода: 0 — доставлено (ok:true от Telegram), 1 — ошибка (детали в stderr).

04.11.2026, Инквизитор: добавлен send_with_retry — повтор при flood_control/429
с ожиданием retry_after (до 4 попыток). Раньше скрипт падал на первом же rate
limit топика 252 (HTTPError 429 не перехватывался) и отчёт терялся.
"""
import json
import mimetypes
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

HOME = os.path.expanduser('~')
ENV_CANDIDATES = [
    os.path.join(HOME, '.hermes/profiles/thomas/.env'),
    os.path.join(HOME, '.hermes/.env'),
]
# Канонический источник токена протокола — secrets-файл (600, вне git)
SECRETS_TOKEN_FILE = os.path.join(HOME, '.hermes/secrets/cathedral_bot_token')
DEFAULT_CHAT_ID = '-1004431090317'
DEFAULT_THREAD_ID = '252'


def find_token():
    tok = os.environ.get('TG_BOT_TOKEN')
    if tok:
        return tok.strip()
    try:
        with open(SECRETS_TOKEN_FILE, 'r') as f:
            tok = f.read().strip()
        if tok:
            return tok
    except OSError:
        pass
    for path in ENV_CANDIDATES:
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('#') or '=' not in line:
                        continue
                    key, _, val = line.partition('=')
                    if key.strip() == 'TELEGRAM_BOT_TOKEN' and val.strip():
                        return val.strip().strip('"').strip("'")
        except OSError:
            continue
    return None


def api_call(token, method, fields, files=None):
    """POST multipart (если files) или form-urlencoded. Возвращает распарсенный JSON.

    HTTPError (429 и др.) не выбрасывается: тело ошибки парсится и возвращается
    как обычный ответ {"ok": false, ...} — иначе терялся parameters.retry_after.
    """
    url = f'https://api.telegram.org/bot{token}/{method}'
    if files:
        boundary = uuid.uuid4().hex
        body = bytearray()
        for key, val in fields.items():
            body += f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{val}\r\n'.encode()
        for key, (filename, blob) in files.items():
            ctype = mimetypes.guess_type(filename)[0] or 'application/octet-stream'
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"; '
                     f'filename="{filename}"\r\nContent-Type: {ctype}\r\n\r\n').encode()
            body += blob + b'\r\n'
        body += f'--{boundary}--\r\n'.encode()
        req = urllib.request.Request(
            url, data=bytes(body),
            headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    else:
        req = urllib.request.Request(
            url, data=urllib.parse.urlencode(fields).encode(),
            headers={'Content-Type': 'application/x-www-form-urlencoded'})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        # Telegram на rate limit отвечает 429 + JSON {"ok":false,"error_code":429,
        # "description":"Too many requests: retry after N","parameters":{"retry_after":N}}
        try:
            return json.loads(e.read().decode())
        except Exception:
            return {"ok": False, "error_code": e.code, "description": str(e)}


def send_with_retry(token, method, fields, files=None, max_attempts=4):
    """Отправка с повтором при flood_control/429: ждём retry_after и пробуем снова.

    Без этого первая же 429 в топике 252 обрывала доставку отчёта (flood_control).
    """
    res = None
    for attempt in range(1, max_attempts + 1):
        res = api_call(token, method, fields, files)
        if res.get('ok'):
            return res
        desc = str(res.get('description', '')).lower()
        retry_after = (res.get('parameters') or {}).get('retry_after')
        is_flood = res.get('error_code') == 429 or 'flood' in desc or 'too many requests' in desc
        if not is_flood or attempt == max_attempts:
            return res
        try:
            wait = min(int(retry_after) + 1, 120) if retry_after else min(2 ** attempt, 30)
        except (TypeError, ValueError):
            wait = min(2 ** attempt, 30)
        print(f'tg_send: flood_control, попытка {attempt}/{max_attempts}, жду {wait}s', file=sys.stderr)
        time.sleep(wait)
    return res


def main(argv):
    # 04.11.2026: -h/--help перехватываем ДО отправки — раньше строка "--help"
    # уходила в топик 252 как обычное текстовое сообщение (message_id=31090).
    if len(argv) >= 2 and argv[1] in ('-h', '--help'):
        print('usage: tg_send.py "text" | tg_send.py MEDIA:/path "caption" | tg_send.py PHOTO:/path "caption"')
        print(__doc__)
        return 0
    if len(argv) < 2:
        print('usage: tg_send.py "text" | tg_send.py MEDIA:/path "caption"', file=sys.stderr)
        return 2
    token = find_token()
    if not token:
        print('tg_send: TELEGRAM_BOT_TOKEN не найден (проверены .env профилей)', file=sys.stderr)
        return 1
    chat_id = os.environ.get('TG_CHAT_ID', DEFAULT_CHAT_ID)
    thread_id = os.environ.get('TG_THREAD_ID', DEFAULT_THREAD_ID)

    if argv[1].startswith(('MEDIA:', 'PHOTO:')):
        photo = argv[1].startswith('PHOTO:')
        method = 'sendPhoto' if photo else 'sendDocument'
        filekey = 'photo' if photo else 'document'
        path = argv[1][len('PHOTO:') if photo else len('MEDIA:'):]
        caption = argv[2] if len(argv) > 2 else ''
        try:
            with open(path, 'rb') as f:
                blob = f.read()
        except OSError as e:
            print(f'tg_send: не читается файл {path}: {e}', file=sys.stderr)
            return 1
        fields = {'chat_id': chat_id, 'message_thread_id': thread_id, 'caption': caption}
        files = {filekey: (os.path.basename(path), blob)}
        res = send_with_retry(token, method, fields, files)
    else:
        fields = {'chat_id': chat_id, 'message_thread_id': thread_id,
                  'disable_web_page_preview': 'true', 'text': argv[1]}
        res = send_with_retry(token, 'sendMessage', fields)

    if res.get('ok'):
        print(f"tg_send: ok → message_id={res['result']['message_id']} "
              f"chat={chat_id} thread={thread_id}")
        return 0
    print(f"tg_send: FAIL {res.get('error_code')} {res.get('description')}", file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
