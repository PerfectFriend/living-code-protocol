#!/bin/bash
# Ночной Артист: --script в кроне не поддерживает аргументы (это путь, а не команда),
# поэтому аргументы живут здесь.
set -o pipefail
exec /usr/bin/python3 /home/thomas/LivingCode/scripts/artist_entry.py --project elemental-life --cycle 9999 --force
