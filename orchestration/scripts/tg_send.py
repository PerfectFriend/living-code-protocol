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
"""
import json
import mimetypes
import os
import sys
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
    """POST multipart (если files) или form-urlencoded. Возвращает распарсенный JSON."""
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
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.loads(resp.read().decode())


def main(argv):
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
        res = api_call(token, method, fields, files)
    else:
        fields = {'chat_id': chat_id, 'message_thread_id': thread_id,
                  'disable_web_page_preview': 'true', 'text': argv[1]}
        res = api_call(token, 'sendMessage', fields)

    if res.get('ok'):
        print(f"tg_send: ok → message_id={res['result']['message_id']} "
              f"chat={chat_id} thread={thread_id}")
        return 0
    print(f"tg_send: FAIL {res.get('error_code')} {res.get('description')}", file=sys.stderr)
    return 1


if __name__ == '__main__':
    sys.exit(main(sys.argv))
