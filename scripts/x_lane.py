#!/usr/bin/env python3
"""X/Twitter-конвейер для Агента-Искателя (Living Code).

Два слоя, верхний включается сам, если у машины есть логин в x.com:

  слой 1 (站内, нужен логин)  agent-reach twitter search|thread|tweets
                              -> OpenCLI в выделенном браузере Reach
  слой 2 (без логина)          поиск:  Brave HTML, запрос вида site:x.com <q>
                              чтение: api.fxtwitter.com  (JSON одного поста)
                                      r.jina.ai/<URL>      (тред/профиль)

Слой 2 нужен потому, что слой 1 требует, чтобы Владыка один раз вошёл в
x.com в окне `agent-reach login twitter`. Пока этого не сделано, Искатель
должен всё равно находить и читать посты X - иначе канал дайджеста слепой.

Команды:
    x_lane.py search "<запрос>" [--limit N] [--json]
    x_lane.py read <URL|ID> [--json]
    x_lane.py profile <handle> [--limit N] [--json]
    x_lane.py doctor [--json]

Каждая находка помечена источником (backend), чтобы Искатель не выдавал
публичный веб-поиск за выдачу X站内. Никаких ключей и cookies скрипт не
печатает и не хранит.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

UA = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36")

FX = "https://api.fxtwitter.com"
JINA = "https://r.jina.ai/"
BRAVE = "https://search.brave.com/search?q="

# Живой пост для зондов «канал читается?». Музейные посты (x.com/jack/status/20)
# не годятся: jina отдаёт на них логин-волл, и зонд врёт про весь канал.
PROBE_POST = "https://x.com/karpathy/status/2106806571321966793"

# Последний HTTP-код Brave - чтобы отличать «лимит 429» от «не работает».
LAST_BRAVE_CODE = 0

# Кэш результатов Brave: часовой крон не должен дёргать индекс каждый запуск.
CACHE_DIR = os.environ.get(
    "X_LANE_CACHE_DIR", os.path.expanduser("~/.cache/x_lane"))
BRAVE_TTL = int(os.environ.get("X_LANE_BRAVE_TTL", "1800"))
# Паузы бэкоффа между попытками при 429/503 (одиночный запрос после 60s проходит).
BRAVE_PAUSES = (60, 150)

STATUS_RE = re.compile(r"(?:x|twitter)\.com/([A-Za-z0-9_]+)/status/(\d+)")
# «x.com › ClaudeDevs › status › 2113328528536305718»
CITE_RE = re.compile(r"x\.com\s*<span[^>]*>›\s*([A-Za-z0-9_]+)\s*›\s*status\s*›\s*(\d+)</span>")


# ─────────────────────────────── утилиты ────────────────────────────────
def log(msg: str) -> None:
    print(msg, file=sys.stderr)


def http_get(url: str, timeout: int = 30, headers: dict | None = None) -> tuple[int, str]:
    """Вернуть (код, текст). Сетевые ошибки не роняют процесс."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", "replace")
    except urllib.error.HTTPError as e:
        try:
            body = e.read().decode("utf-8", "replace")
        except Exception:
            body = ""
        return e.code, body
    except Exception as e:
        log(f"HTTP fail {url}: {type(e).__name__}: {e}")
        return 0, ""


def clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text)
    text = html.unescape(text)
    return re.sub(r"\s+", " ", text).strip()


def as_int(value) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


# ───────────────────────── слой 1: agent-reach ───────────────────────────
def reach_available() -> bool:
    return shutil.which("agent-reach") is not None


def reach_json(args: list[str], timeout: int = 120) -> dict | None:
    """Запустить agent-reach и разобрать его JSON-конверт."""
    if not reach_available():
        return None
    try:
        p = subprocess.run(["agent-reach", *args], capture_output=True,
                           text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        log("agent-reach timeout")
        return None
    except Exception as e:
        log(f"agent-reach fail: {type(e).__name__}: {e}")
        return None
    raw = (p.stdout or "").strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        log(f"agent-reach non-JSON: {raw[:200]}")
        return None


def reach_items(payload: dict | None) -> list[dict]:
    if not payload or not payload.get("ok"):
        return []
    items = payload.get("items") or []
    return [i for i in items if isinstance(i, dict)]


def reach_error(payload: dict | None) -> str:
    if not payload:
        return "agent-reach недоступен"
    err = payload.get("error") or {}
    return f"{err.get('code', 'ERROR')}: {err.get('message', '')[:160]}"


def layer1_search(query: str, limit: int, timeout: int = 180) -> list[dict]:
    payload = reach_json(["twitter", "search", query, "--limit", str(limit)], timeout=timeout)
    items = reach_items(payload)
    if not items:
        log(f"слой1 search не дал результатов ({reach_error(payload)})")
        return []
    out = []
    for it in items:
        out.append({
            "backend": "agent-reach/opencli",
            "url": it.get("url") or "",
            "author": it.get("author") or "",
            "title": (it.get("title") or "")[:300],
            "text": (it.get("text") or "")[:1200],
            "published_at": it.get("published_at"),
        })
    return out


def layer1_thread(target: str, timeout: int = 180) -> dict | None:
    payload = reach_json(["twitter", "thread", target], timeout=timeout)
    items = reach_items(payload)
    if not items:
        log(f"слой1 thread не дал результатов ({reach_error(payload)})")
        return None
    texts = []
    for it in items:
        texts.append({
            "author": it.get("author") or "",
            "url": it.get("url") or "",
            "text": (it.get("text") or "")[:2000],
        })
    return {"backend": "agent-reach/opencli", "thread": texts}


# ───────────────────────── слой 2: без логина ─────────────────────────────
def _cache_path(key: str) -> str:
    digest = hashlib.sha1(key.encode("utf-8")).hexdigest()[:16]
    return os.path.join(CACHE_DIR, f"brave_{digest}.json")


def _cache_get(key: str, ttl: int) -> list[dict] | None:
    try:
        with open(_cache_path(key), encoding="utf-8") as fh:
            blob = json.load(fh)
    except (OSError, json.JSONDecodeError):
        return None
    if time.time() - float(blob.get("ts") or 0) > ttl:
        return None
    items = blob.get("items")
    return items if isinstance(items, list) and items else None


def _cache_put(key: str, items: list[dict]) -> None:
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(_cache_path(key), "w", encoding="utf-8") as fh:
            json.dump({"ts": time.time(), "items": items}, fh, ensure_ascii=False)
    except OSError:
        pass


def brave_search(query: str, limit: int, attempts: int = 3,
                 use_cache: bool = True) -> list[dict]:
    """Поиск по индексу веба с site:x.com - находит посты X без логина.

    Brave отдаёт 429 на частые запросы, поэтому:
      1) результат кэшируется на BRAVE_TTL секунд - часовой крон не душит индекс;
      2) между попытками бэкофф BRAVE_PAUSES - иначе крон начнёт «не находить»
         посты X просто из-за лимита, и это будет выглядеть как поломка канала.
    Устаревший кэш отдаётся только при X_LANE_ALLOW_STALE=1 и помечается
    stale=true, чтобы вызывающая сторона не приняла старое за свежее.
    """
    global LAST_BRAVE_CODE
    key = f"{query}|{limit}"
    if use_cache:
        cached = _cache_get(key, BRAVE_TTL)
        if cached:
            log("Brave: ответ из кэша")
            return cached[:limit]
    q = urllib.parse.quote(f"site:x.com {query}")
    code, body = 0, ""
    for attempt in range(attempts):
        code, body = http_get(BRAVE + q, timeout=30)
        LAST_BRAVE_CODE = code
        if code == 200 and body:
            break
        if code in (429, 503) and attempt < attempts - 1:
            pause = BRAVE_PAUSES[min(attempt, len(BRAVE_PAUSES) - 1)]
            log(f"Brave HTTP {code}, пауза {pause}s")
            time.sleep(pause)
            continue
        log(f"Brave HTTP {code}")
        break
    out: list[dict] = []
    if code == 200 and body:
        seen: set[str] = set()
        for block in body.split('class="snippet ')[1:]:
            m = re.search(r'<a href="(https?://(?:x|twitter)\.com/[^"]+)"', block)
            if not m:
                continue
            url = html.unescape(m.group(1)).split("?")[0].split("#")[0]
            # Только настоящие посты (/{user}/status/{id}): в выдаче попадаются
            # /i/trending/... и /{user}/article/... - это не твиты.
            sm = STATUS_RE.search(url)
            if not sm:
                continue
            sid = sm.group(2)
            if sid in seen:
                continue
            seen.add(sid)
            tm = re.search(r'class="title[^"]*"[^>]*title="([^"]*)"', block)
            cm = re.search(r'class="content[^"]*"[^>]*>(.*?)</div>', block, re.S)
            out.append({
                "backend": "brave/site:x.com",
                "url": f"https://x.com/{sm.group(1)}/status/{sid}",
                "id": sid,
                "author": sm.group(1),
                "title": clean(tm.group(1)) if tm else "",
                "text": clean(cm.group(1)) if cm else "",
            })
            if len(out) >= limit:
                break
    if out:
        if use_cache:
            _cache_put(key, out)
        return out
    if use_cache and os.environ.get("X_LANE_ALLOW_STALE") == "1":
        stale = _cache_get(key, 10 ** 9)
        if stale:
            log("Brave: лимит, отдаю устаревший кэш (stale)")
            return [{**item, "stale": True} for item in stale[:limit]]
    log("Brave не вернул ссылок x.com")
    return []


def fx_post(target: str) -> dict | None:
    """JSON одного поста из api.fxtwitter.com (без логина)."""
    ident = target
    m = STATUS_RE.search(target)
    if m:
        ident = m.group(2)
    elif not re.fullmatch(r"\d+", target):
        return None
    code, body = http_get(f"{FX}/status/{ident}", timeout=30)
    if code != 200:
        log(f"fxtwitter HTTP {code}")
        return None
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return None
    tw = (data or {}).get("tweet") or {}
    if not tw.get("text"):
        return None
    author = tw.get("author") or {}
    return {
        "backend": "api.fxtwitter.com",
        "id": tw.get("id"),
        "url": tw.get("url") or f"https://x.com/i/status/{tw.get('id')}",
        "author": author.get("screen_name") or "",
        "author_name": author.get("name") or "",
        "text": tw.get("text") or "",
        "created_at": tw.get("created_at"),
        "likes": as_int(tw.get("likes")),
        "retweets": as_int(tw.get("retweets")),
        "replies": as_int(tw.get("replies")),
        "views": as_int(tw.get("views")),
        "quote_url": tw.get("quote_url") or "",
    }


def jina_read(url: str) -> dict | None:
    """Текст страницы X через r.jina.ai - работает для треда и профиля."""
    code, body = http_get(JINA + url, timeout=45)
    if code != 200 or not body.strip():
        log(f"jina HTTP {code}")
        return None
    text = body.strip()
    if len(text) < 120:
        return None
    if re.search(r"log in or sign up for X|see what's happening", text, re.I):
        log("jina: login-wall, а не контент")
        return None
    return {"backend": "r.jina.ai", "url": url, "text": text[:20000]}


def layer2_read(target: str) -> dict | None:
    post = fx_post(target)
    if post:
        page = jina_read(post["url"])
        if page:
            post["thread_text"] = page["text"]
            post["thread_backend"] = page["backend"]
        return post
    url = target if target.startswith("http") else f"https://x.com/i/status/{target}"
    page = jina_read(url)
    if page:
        return {"backend": page["backend"], "url": url,
                "author": "", "text": page["text"][:4000],
                "thread_text": page["text"], "thread_backend": page["backend"]}
    return None


def layer2_profile(handle: str) -> dict | None:
    handle = handle.lstrip("@")
    page = jina_read(f"https://x.com/{handle}")
    if not page:
        return None
    return {"backend": page["backend"], "handle": handle,
            "url": f"https://x.com/{handle}", "text": page["text"][:8000]}


# ───────────────────────────── команды ──────────────────────────────────
def cmd_search(args) -> int:
    results = layer1_search(args.query, args.limit)
    source = "agent-reach/opencli"
    if not results:
        results = brave_search(args.query, args.limit,
                               use_cache=not args.no_cache)
        source = "brave/site:x.com"
    payload = {
        "ok": bool(results),
        "query": args.query,
        "backend": source,
        "count": len(results),
        "items": results,
    }
    if not results:
        # Разные причины - разные сообщения: иначе «лимит» выглядит как «сломано».
        if LAST_BRAVE_CODE == 429:
            payload["error"] = ("публичный поиск упёрся в лимит Brave (429), "
                                "даже после бэкоффа")
        elif LAST_BRAVE_CODE:
            payload["error"] = (f"публичный поиск недоступен "
                                f"(HTTP {LAST_BRAVE_CODE} от Brave)")
        else:
            payload["error"] = "публичный поиск Brave не дал ссылок x.com"
        payload["layer1"] = "недоступен (нужен логин x.com в окне Reach)"
    emit(payload, args.json)
    return 0 if results else 1


def cmd_read(args) -> int:
    thread = layer1_thread(args.target)
    if thread:
        emit({"ok": True, **thread}, args.json)
        return 0
    data = layer2_read(args.target)
    if not data:
        emit({"ok": False, "error": "контент не получен ни одним слоем",
              "target": args.target}, args.json)
        return 1
    emit({"ok": True, **data}, args.json)
    return 0


def cmd_profile(args) -> int:
    data = layer2_profile(args.handle)
    if not data:
        emit({"ok": False, "error": "профиль не прочитан",
              "handle": args.handle}, args.json)
        return 1
    emit({"ok": True, **data}, args.json)
    return 0


def cmd_doctor(args) -> int:
    info = {"agent_reach": None, "opencli": bool(shutil.which("opencli")),
            "twitter_login": None, "public_web": {}}
    payload = reach_json(["channels"], timeout=120)
    if payload:
        for ch in payload.get("channels") or []:
            if isinstance(ch, dict) and ch.get("name") == "twitter":
                info["twitter_login"] = (ch.get("login") or {}).get("logged_in")
                info["twitter_actions"] = [a.get("name") for a in ch.get("actions") or []]
    else:
        info["agent_reach"] = "не найден или не отвечает"
    # Живая проверка: кэш тут врёт - он может быть свежим, пока канал лежит.
    probe = brave_search("openai", 1, use_cache=False)
    if probe:
        info["public_web"]["brave_site_x"] = "ok"
    elif LAST_BRAVE_CODE == 429:
        info["public_web"]["brave_site_x"] = "лимит 429 (бэкофф не помог)"
    else:
        info["public_web"]["brave_site_x"] = "не работает"
    post = fx_post(PROBE_POST)
    info["public_web"]["fxtwitter"] = "ok" if post else "не работает"
    page = jina_read(PROBE_POST)
    info["public_web"]["jina"] = "ok" if page else "не работает"
    info["layer1_ready"] = bool(info["twitter_login"])
    # поиск и чтение - разные каналы: поиск живёт на Brave, чтение на fxtwitter
    info["layer2_search_ready"] = info["public_web"]["brave_site_x"] == "ok"
    info["layer2_read_ready"] = (info["public_web"]["fxtwitter"] == "ok"
                                 or info["public_web"]["jina"] == "ok")
    info["layer2_ready"] = info["layer2_search_ready"] and info["layer2_read_ready"]
    emit({"ok": True, **info}, args.json)
    return 0


def emit(payload: dict, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if not payload.get("ok"):
        print(f"X-СЛОЙ НЕ РАБОТАЕТ: {payload.get('error', 'неизвестно')}")
        return
    if "items" in payload:
        print(f"X-поиск [{payload['backend']}] «{payload.get('query')}»: "
              f"{payload['count']} результатов")
        for i, it in enumerate(payload["items"], 1):
            print(f"{i}. {it.get('url')}")
            if it.get("author"):
                print(f"   @{it['author']}")
            if it.get("title"):
                print(f"   {it['title'][:200]}")
            if it.get("text"):
                print(f"   {it['text'][:400]}")
        return
    if "text" in payload:
        print(f"X-контент [{payload.get('backend')}] {payload.get('url', '')}")
        print(payload["text"][:4000])
        return
    for k, v in payload.items():
        print(f"{k}: {v}")


def main(argv=None) -> int:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--json", action="store_true", help="вывод в JSON")
    ap = argparse.ArgumentParser(description="X/Twitter-конвейер Искателя")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("search", parents=[common], help="поиск постов по запросу")
    s.add_argument("query")
    s.add_argument("--limit", type=int, default=10)
    s.add_argument("--no-cache", action="store_true",
                   help="игнорировать кэш Brave и идти в индекс заново")
    s.set_defaults(func=cmd_search)

    r = sub.add_parser("read", parents=[common], help="прочитать пост/тред по URL или ID")
    r.add_argument("target")
    r.set_defaults(func=cmd_read)

    p = sub.add_parser("profile", parents=[common], help="прочитать ленту профиля")
    p.add_argument("handle")
    p.add_argument("--limit", type=int, default=10)
    p.set_defaults(func=cmd_profile)

    d = sub.add_parser("doctor", parents=[common], help="проверить готовность слоёв")
    d.set_defaults(func=cmd_doctor)

    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
