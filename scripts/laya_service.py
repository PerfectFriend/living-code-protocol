#!/usr/bin/env python3
"""Тёплый сервис Laya: модель в памяти 24/7, ленивая выгрузка по простою.

Смысл: каждый холодный вызов `laya_bridge.py` платит загрузку чекпоинта
(4.6 с на пустой машине, до 100 с на нагруженной). Сервис держит `Router`
прогретым и обслуживает вызовы за десятки миллисекунд.

Политика памяти (по требованию владельца): держим модель, пока есть работа;
если простоев больше LAYA_IDLE_UNLOAD_S (по умолчанию 2 часа) — выгружаем и
возвращаем память ОС; следующий запрос снова прогревает (ленивая загрузка).

Запуск: venvs/laya/bin/python orchestration/scripts/laya_service.py
Переменные: LAYA_PORT (8731), LAYA_IDLE_UNLOAD_S (7200), LAYA_PRELOAD (1),
            LAYA_MAX_LEN (8192), LAYA_THREADS, LAYA_DEVICE (cpu), LAYA_MODEL_DIR.
"""
from __future__ import annotations

import ctypes
import gc
import importlib.util
import json
import os
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent                      # ~/LivingCode
MODEL_DIR = Path(os.environ.get("LAYA_MODEL_DIR", ROOT / "models" / "laya-multilingual"))
PORT = int(os.environ.get("LAYA_PORT", "8731"))
IDLE_UNLOAD_S = float(os.environ.get("LAYA_IDLE_UNLOAD_S", "7200"))   # 2 часа
PRELOAD = os.environ.get("LAYA_PRELOAD", "1") not in ("0", "false", "no")
MAX_LEN = int(os.environ.get("LAYA_MAX_LEN", "8192"))
DEVICE = os.environ.get("LAYA_DEVICE", "cpu")

if os.environ.get("LAYA_THREADS"):
    try:
        import torch
        torch.set_num_threads(int(os.environ["LAYA_THREADS"]))
    except Exception as exc:                                       # noqa: BLE001
        print(f"[warn] LAYA_THREADS: {exc}", file=sys.stderr)

# --- логика моста переиспользуется как единственный источник истины -----------
def _load_bridge():
    path = HERE / "laya_bridge.py"
    spec = importlib.util.spec_from_file_location("laya_bridge", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

bridge = _load_bridge()

STATE = {"router": None, "loaded_at": None, "last_use": time.time(),
         "calls": 0, "unloads": 0, "loads": 0}
LOCK = threading.RLock()


def _rss_mb() -> int:
    try:
        with open("/proc/self/status") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return int(line.split()[1]) // 1024
    except OSError:
        pass
    return -1


def _lock_memory(reason: str = "загрузка модели"):
    """Закрепляет уже загруженные страницы (mlockall MCL_CURRENT).

    Без этого ядро при нехватке RAM вытесняет веса модели, и каждый вызов заново
    читает чекпоинт с диска: наблюдались 9217 major page faults и 300+ с на вызов.
    """
    if os.environ.get("LAYA_MLOCK", "1").lower() in ("0", "false", "no"):
        return
    try:
        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        if libc.mlockall(1) != 0:                       # MCL_CURRENT
            print(f"[laya] mlockall не удался (errno {ctypes.get_errno()}), "
                  f"{reason}: веса могут вытесняться в своп", file=sys.stderr, flush=True)
        else:
            print(f"[laya] веса закреплены в RAM (mlockall): {reason}", file=sys.stderr, flush=True)
    except Exception as exc:                                     # noqa: BLE001
        print(f"[laya] mlockall недоступен: {exc}", file=sys.stderr, flush=True)


def load_router():
    """Поднимает Router и реально прогревает веса. Вызывать под LOCK."""
    if STATE["router"] is not None:
        return STATE["router"]
    t0 = time.time()
    from laya import Router
    router = Router(models={"multilingual": str(MODEL_DIR)}, device=DEVICE,
                    max_loaded=1, default="multilingual")
    # Router ленив: конструктор не читает safetensors. Греем настоящим predict,
    # иначе «тёплый» сервис платил бы за загрузку на первом живом вызове.
    router.predict("прогрев", bridge.UI_QUESTIONS, model="multilingual", lang="ru", max_len=256)
    STATE["router"] = router
    STATE["loaded_at"] = time.time()
    STATE["loads"] += 1
    _lock_memory("после прогрева")
    print(f"[laya] модель загружена за {time.time() - t0:.1f} с, RSS {_rss_mb()} МБ",
          file=sys.stderr, flush=True)
    return router


def unload_router(reason: str):
    """Отпускает модель и возвращает память ОС. Вызывать под LOCK."""
    if STATE["router"] is None:
        return False
    before = _rss_mb()
    STATE["router"] = None
    STATE["loaded_at"] = None
    gc.collect()
    try:                      # glibc не всегда отдаёт арену назад — просим явно
        ctypes.CDLL("libc.so.6").malloc_trim(0)
    except Exception:                                          # noqa: BLE001
        pass
    STATE["unloads"] += 1
    print(f"[laya] модель выгружена ({reason}): RSS {before} → {_rss_mb()} МБ",
          file=sys.stderr, flush=True)
    return True


def _idle_watchdog():
    while True:
        time.sleep(30)
        idle = time.time() - STATE["last_use"]
        if STATE["router"] is not None and IDLE_UNLOAD_S > 0 and idle > IDLE_UNLOAD_S:
            with LOCK:
                unload_router(f"простой {idle / 60:.0f} мин > {IDLE_UNLOAD_S / 60:.0f} мин")


# --- выполнение запроса: родной код моста против тёплого Router ---------------
def _exec_argv(argv: list[str], payload: str | None) -> dict:
    """Прогоняет `laya_bridge.main()` с подменённой сборкой Router.

    Логика режимов/постобработки остаётся в мосте — единственном источнике истины,
    поэтому сервис не может разойтись с локальным запуском.
    """
    tmp = None
    try:
        argv = list(argv)
        # Заслонка от самовызова: внутри сервиса мост НЕ должен идти по HTTP обратно
        # в сервис — иначе запрос ждёт сам себя на LOCK и всё виснет навсегда.
        if "--no-service" not in argv:
            argv.append("--no-service")
        if payload is not None:
            import tempfile
            fd, tmp = tempfile.mkstemp(prefix="laya_req_", suffix=".txt", dir="/tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as fh:
                fh.write(payload)
            if "raw" in argv[:1] or argv[:1] == ["raw"]:
                argv += ["--raw", tmp]
            else:
                argv += ["--file", tmp]

        import contextlib
        import io
        buf = io.StringIO()
        old_argv, old_build = sys.argv, bridge.build_router
        bridge.build_router = lambda _args: load_router()       # холод → тёплый
        t0 = time.perf_counter()
        try:
            sys.argv = ["laya_bridge"] + argv
            with contextlib.redirect_stdout(buf):
                rc = bridge.main()
        finally:
            sys.argv, bridge.build_router = old_argv, old_build
        took = time.perf_counter() - t0
        STATE["calls"] += 1
        raw = buf.getvalue()
        try:
            parsed = json.loads(raw.strip().splitlines()[-1]) if raw.strip() else {}
        except (ValueError, IndexError):
            parsed = None
        return {"ok": rc == 0, "rc": rc, "result": parsed, "stdout": raw,
                "took_ms": round(took * 1000, 1), "rss_mb": _rss_mb()}
    except Exception as exc:                                     # noqa: BLE001
        return {"ok": False, "rc": 3, "error": f"{type(exc).__name__}: {exc}"}
    finally:
        if tmp:
            try:
                os.unlink(tmp)
            except OSError:
                pass


def handle_call(body: dict) -> dict:
    """POST /call: либо {"argv": [...], "text": "..."}, либо удобная форма."""
    if "argv" in body:
        argv = [str(x) for x in body["argv"]]
        payload = body.get("text")
    else:
        mode = str(body.get("mode", "ui_gate"))
        payload = body.get("text", "")
        argv = [mode]
        if body.get("max_chars") is not None:
            argv += ["--max-chars", str(int(body["max_chars"]))]
        if body.get("lang"):
            argv += ["--lang", str(body["lang"])]
        if body.get("state_context"):
            argv += ["--state-context", str(body["state_context"])]
    wait_s = float(os.environ.get("LAYA_LOCK_WAIT_S", "300"))
    if not LOCK.acquire(timeout=wait_s):
        return {"ok": False, "rc": 5,
                "error": f"busy: очередь к модели не освободилась за {wait_s:.0f} с"}
    try:
        STATE["last_use"] = time.time()
        out = _exec_argv(argv, payload)
        STATE["last_use"] = time.time()
    finally:
        LOCK.release()
    if out.get("took_ms", 0) > 30000:
        print(f"[laya] медленный вызов: {out['took_ms']:.0f} мс, режим {' '.join(argv[:1])}",
              file=sys.stderr, flush=True)
    return out


# --- HTTP-обвязка -------------------------------------------------------------
def _health() -> dict:
    idle = time.time() - STATE["last_use"]
    return {
        "ok": True,
        "loaded": STATE["router"] is not None,
        "rss_mb": _rss_mb(),
        "idle_s": round(idle, 1),
        "unload_after_s": IDLE_UNLOAD_S,
        "unload_in_s": round(max(0.0, IDLE_UNLOAD_S - idle), 1) if STATE["router"] is not None else None,
        "calls": STATE["calls"], "loads": STATE["loads"], "unloads": STATE["unloads"],
        "device": DEVICE, "model_dir": str(MODEL_DIR), "pid": os.getpid(),
        "uptime_s": round(time.time() - STARTED, 1),
    }


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "laya-warm/1.0"

    def _send(self, code: int, obj: dict):
        data = json.dumps(obj, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _body(self) -> dict:
        n = int(self.headers.get("Content-Length") or 0)
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self):                                            # noqa: N802
        if self.path.split("?")[0] in ("/health", "/", "/status"):
            self._send(200, _health())
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def do_POST(self):                                           # noqa: N802
        path = self.path.split("?")[0]
        body = self._body()
        if path in ("/call", "/ui_gate", "/triage", "/verdict", "/score", "/raw"):
            if path != "/call":
                body.setdefault("mode", path.lstrip("/"))
            out = handle_call(body)
            self._send(200 if out.get("ok") else 200, out)
        elif path == "/warm":
            with LOCK:
                t0 = time.time()
                load_router()
            self._send(200, {"ok": True, "loaded": True, "took_ms": round((time.time() - t0) * 1000, 1),
                             "rss_mb": _rss_mb()})
        elif path == "/unload":
            with LOCK:
                done = unload_router("запрошено вручную")
            self._send(200, {"ok": True, "unloaded": done, "rss_mb": _rss_mb()})
        else:
            self._send(404, {"ok": False, "error": "not found"})

    def log_message(self, fmt, *args):                            # в stderr, не в stdout
        print(f"[http] {self.address_string()} {fmt % args}", file=sys.stderr, flush=True)


STARTED = time.time()


def _preload():
    """Прогрев в отдельном потоке, чтобы порт открылся сразу."""
    try:
        with LOCK:
            load_router()
    except Exception as exc:                                     # noqa: BLE001
        print(f"[laya] предзагрузка не удалась: {type(exc).__name__}: {exc}",
              file=sys.stderr, flush=True)


def main() -> int:
    print(f"[laya] сервис: порт {PORT}, устройство {DEVICE}, чекпоинт {MODEL_DIR}", file=sys.stderr, flush=True)
    print(f"[laya] политика памяти: выгрузка при простое > {IDLE_UNLOAD_S / 60:.0f} мин, "
          f"предзагрузка={'да' if PRELOAD else 'нет'}", file=sys.stderr, flush=True)
    os.environ["LAYA_IN_SERVICE"] = "1"      # заслонка от самовызова через мост
    threading.Thread(target=_idle_watchdog, daemon=True, name="idle-watchdog").start()
    if PRELOAD:
        threading.Thread(target=_preload, daemon=True, name="preload").start()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    srv.daemon_threads = True
    try:
        srv.serve_forever(poll_interval=0.5)
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
