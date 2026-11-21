#!/bin/bash
# LV-promote-check — ежечасный прогон конвейера Живого Кода.
# Схема владельца: Projects/ = очередь, Project1..4 = рабочие слоты,
# CompleteProjects/ = выпущенные проекты (100% холодный код + финальное досье).
set -o pipefail
cd /home/thomas/LivingCode
/usr/bin/python3 /home/thomas/LivingCode/orchestration/scripts/conveyor.py run --apply
