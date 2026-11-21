#!/usr/bin/env python3
"""
Компактия state.db Протокола Живого Кода.

state.db (2.5 ГБ, WAL растёт при работающем gateway) раздувается из-за
дублирующихся копий сообщений и индекса инструментов в старом layout.
Этот скрипт выполняет `hermes sessions optimize-storage` — пересобирает
полнотекстовый индекс в компактном v23 layout и VACUUM-ит базу.

⚠️  ТРЕБУЕТСЯ: gateway должен быть остановлен (исключение lock на state.db).
   В окне простоя выполнить, затем перезапустить gateway.

Использование:
    python3 compact_state_db.py [--yes]

Без --yes запрашивает подтверждение (ディсковая операция).
"""

import argparse
import subprocess
import sys
from pathlib import Path

HERMES_BIN = "hermes"
STATE_DB = Path.home() / ".hermes" / "state.db"


def main() -> int:
    parser = argparse.ArgumentParser(description="Компактия state.db Живого Кода")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Пропустить подтверждение")
    args = parser.parse_args()

    if not STATE_DB.exists():
        print(f"❌ state.db не найден: {STATE_DB}")
        return 1

    size_gb = STATE_DB.stat().st_size / (1024 ** 3)
    print(f"📦 state.db: {size_gb:.2f} ГБ")
    print("⚠️  gateway должен быть остановлен перед компактией.")
    print("   Остановите gateway, запустите этот скрипт, затем перезапустите gateway.")
    print()

    if not args.yes:
        resp = input("Продолжить с компактией? (yes/NO): ").strip().lower()
        if resp != "yes":
            print("Отменено.")
            return 0

    print("🔄 Запуск hermes sessions optimize-storage ...")
    rc = subprocess.run(
        [HERMES_BIN, "sessions", "optimize-storage", "--yes"],
    ).returncode

    if rc == 0:
        new_size_gb = STATE_DB.stat().st_size / (1024 ** 3)
        saved_gb = size_gb - new_size_gb
        print(f"✅ Компактия завершена: {size_gb:.2f} ГБ → {new_size_gb:.2f} ГБ "
              f"(освобождено {saved_gb:.2f} ГБ)")
    else:
        print(f"❌ Компактия не удалась (rc={rc})")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
