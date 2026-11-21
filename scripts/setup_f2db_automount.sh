#!/bin/bash
# setup_f2db_automount.sh — автомонтирование флешки F2DB-14E5 при загрузке.
#
# Что делает:
#   1. Находит устройство (аргумент, либо по лейблу F2DB-14E5, либо /dev/sda1).
#   2. Пишет в /etc/fstab запись по UUID с nofail — без флешки загрузка НЕ виснет.
#   3. Монтирует в стабильную точку /mnt/F2DB-14E5 (systemd создаст её при загрузке).
#   4. Делает симлинк /run/media/thomas/F2DB-14E5 -> /mnt/F2DB-14E5 через
#      systemd-tmpfiles — все старые пути в скриптах/бэкапах продолжают работать.
#   5. Если сейчас примонтировано udisks'ом по UUID-пути — аккуратно перемонтирует.
#
# Идемпотентен: повторный запуск безопасен. Нужен sudo (спросит пароль один раз).
# Запуск:  bash ~/LivingCode/orchestration/scripts/setup_f2db_automount.sh [ /dev/sdX1 ]
set -euo pipefail

MOUNT=/mnt/F2DB-14E5
LEGACY=/run/media/thomas/F2DB-14E5
MARK="# F2DB-14E5 automount (living-code)"

# 1. Устройство
DEV="${1:-}"
if [[ -z "$DEV" ]]; then
    DEV="$(blkid -L F2DB-14E5 2>/dev/null || true)"
fi
if [[ -z "$DEV" ]]; then
    for d in /dev/sd[a-z]1; do
        [[ -e "$d" ]] || continue
        if udevadm info --query=property --name="$d" 2>/dev/null | grep -q "F2DB"; then
            DEV="$d"; break
        fi
    done
fi
if [[ -z "$DEV" ]]; then DEV=/dev/sda1; fi
[[ -e "$DEV" ]] || { echo "Устройство не найдено: $DEV. Укажи явно: $0 /dev/sdX1" >&2; exit 1; }

UUID="$(blkid -s UUID -o value "$DEV")"
FSTYPE="$(blkid -s TYPE -o value "$DEV")"
[[ -n "$UUID" && -n "$FSTYPE" ]] || { echo "Не удалось прочитать UUID/TYPE у $DEV" >&2; exit 1; }
echo "Устройство: $DEV  UUID=$UUID  fs=$FSTYPE"

# 2. fstab (идемпотентно)
if grep -q "UUID=$UUID" /etc/fstab; then
    echo "fstab: запись для UUID=$UUID уже есть — пропускаю"
else
    echo "UUID=$UUID  $MOUNT  $FSTYPE  defaults,nofail,x-systemd.device-timeout=10  0  0  $MARK" | sudo tee -a /etc/fstab >/dev/null
    echo "fstab: добавлена запись $UUID -> $MOUNT (nofail)"
fi

# 3. tmpfiles: симлинк legacy-пути на стабильную точку монтирования
sudo mkdir -p /etc/tmpfiles.d
printf 'd /run/media/thomas 0755 thomas thomas -\nL %s - - - - %s\n' "$LEGACY" "$MOUNT" \
    | sudo tee /etc/tmpfiles.d/f2db-automount.conf >/dev/null

# 4. Применяем конфиги
sudo systemctl daemon-reload
sudo systemd-tmpfiles --create /etc/tmpfiles.d/f2db-automount.conf
sudo mkdir -p "$MOUNT"

# 5. Если udisks уже примонтировал по UUID-пути — перемонтируем в нашу точку
CUR="$(findmnt -n -o TARGET "$DEV" 2>/dev/null | head -1 || true)"
if [[ -n "$CUR" && "$CUR" != "$MOUNT" ]]; then
    echo "udisks примонтировал в $CUR — перемонтирую в $MOUNT"
    udisksctl unmount -b "$DEV" 2>/dev/null || sudo umount "$CUR"
fi
sudo mount "$MOUNT" 2>/dev/null || true   # nofail: устройства нет прямо сейчас — ок, смонтируется при загрузке/подключении

# 6. Проверка
if findmnt "$MOUNT" 2>/dev/null | grep -q "$DEV"; then
    echo "OK: $DEV смонтирован в $MOUNT"
    echo "Legacy-путь: $LEGACY -> $(readlink -f "$LEGACY" 2>/dev/null || echo '(создастся при загрузке)')"
    ls "$LEGACY" 2>/dev/null | head -5 || true
else
    echo "Сейчас устройство не примонтировано — это нормально с nofail." >&2
    echo "При загрузке с воткнутой флешкой systemd примонтирует $MOUNT автоматически;" >&2
    echo "legacy-путь $LEGACY создастся через systemd-tmpfiles." >&2
fi
