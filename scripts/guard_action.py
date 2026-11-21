#!/usr/bin/env python3
"""guard_action.py — human-гейт на «линии разлома» действий протокола (Approval-Queue paper).

Гейт срабатывает ТОЛЬКО на необратимых/наружу действиях:
  push-protected  — git push в protected remotes (репозиторий протокола)
  delete          — удаление файлов/веток/репозиториев
  model-change    — смена модели/провайдера в слоях протокола
  ban-edit        — правка BANNED_MODEL_SUBSTRINGS / белого списка
  cron-disable    — отключение крон-джоб
Всё остальное — аудит постфактум (журнал + diff).

Разрешение: либо env LIVING_CODE_OWNER_APPROVED=1 (ручной запуск владельцем),
либо свежий маркер state/owner_approval.json (команда `approve`, живёт 1 час).

Команды:
  check <class> [detail]   — exit 0 разрешено, exit 2 заблокировано
  approve <class> [detail] — записать маркер одобрения владельцем
  selftest                 — проверка самого гейта
"""
import json
import os
import sys
import time
from pathlib import Path

LC = Path.home() / "LivingCode"
STATE = LC / "state"
MARKER = STATE / "owner_approval.json"
CLASSES = ("push-protected", "delete", "model-change", "ban-edit", "cron-disable")
TTL = 3600  # маркер живёт час


def _approved(cls: str, detail: str) -> tuple[bool, str]:
    if os.environ.get("LIVING_CODE_OWNER_APPROVED") == "1":
        return True, "env LIVING_CODE_OWNER_APPROVED=1"
    try:
        m = json.loads(MARKER.read_text(encoding="utf-8"))
        if m.get("action") == cls and time.time() - float(m.get("ts", 0)) < TTL:
            return True, f"маркер владельца от {time.strftime('%H:%M:%S', time.localtime(m['ts']))}"
    except (OSError, ValueError, KeyError):
        pass
    return False, ""


def check(cls: str, detail: str = "") -> int:
    if cls not in CLASSES:
        print(f"Неизвестный класс действия: {cls}. Допустимые: {', '.join(CLASSES)}")
        return 2
    ok, why = _approved(cls, detail)
    if ok:
        print(f"✅ guard_action: '{cls}' разрешено ({why}) {detail}")
        return 0
    print(f"⛔ guard_action: '{cls}' ЗАБЛОКИРОВАНО — действие на линии разлома. {detail}")
    print("   Разрешить может только владелец: guard_action.py approve "
          f"{cls} '<причина>'  или LIVING_CODE_OWNER_APPROVED=1. "
          "Записано в журнал аудита.")
    _audit(cls, detail, allowed=False)
    return 2


def approve(cls: str, detail: str = "") -> int:
    STATE.mkdir(parents=True, exist_ok=True)
    MARKER.write_text(json.dumps(
        {"action": cls, "detail": detail, "ts": time.time(), "by": "owner"},
        ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _audit(cls, detail, allowed=True)
    print(f"Маркер одобрения записан: {cls} {detail} (TTL {TTL}s)")
    return 0


def _audit(cls: str, detail: str, allowed: bool) -> None:
    journal = LC / "agents" / "journal.md"
    line = (f"[OWNER_APPROVED{' ' if allowed else '_BLOCKED'}] "
            f"{time.strftime('%Y-%m-%d %H:%M:%S %Z')} guard_action {cls} "
            f"{'разрешено' if allowed else 'ЗАБЛОКИРОВАНО'}: {detail[:200]}")
    try:
        with open(journal, "a", encoding="utf-8") as fh:
            fh.write(line + "\n")
    except OSError:
        pass


def selftest() -> int:
    import subprocess
    env_clean = {k: v for k, v in os.environ.items() if k != "LIVING_CODE_OWNER_APPROVED"}
    r1 = subprocess.run([sys.executable, __file__, "check", "delete", "selftest"],
                        capture_output=True, env=env_clean)
    r2 = subprocess.run([sys.executable, __file__, "check", "delete", "selftest"],
                        capture_output=True,
                        env={**env_clean, "LIVING_CODE_OWNER_APPROVED": "1"})
    if r1.returncode == 2 and r2.returncode == 0:
        print("SELFTEST OK: без одобрения блокирует (rc=2), с одобрением пропускает (rc=0)")
        return 0
    print(f"SELFTEST FAIL: без одобрения rc={r1.returncode}, с одобрением rc={r2.returncode}")
    return 1


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    cmd = sys.argv[1]
    if cmd == "check":
        return check(sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3] if len(sys.argv) > 3 else "")
    if cmd == "approve":
        return approve(sys.argv[2] if len(sys.argv) > 2 else "", sys.argv[3] if len(sys.argv) > 3 else "")
    if cmd == "selftest":
        return selftest()
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main())
