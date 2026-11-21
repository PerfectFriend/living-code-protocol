#!/usr/bin/env bash
# Мост для крона LV-graph-pulse-export: экспортёр — реальная копия в scripts-каталоге
# (валидатор крона не резолвит скрипты вне каталога; оригинал в GodModeCoder).
cd "$(dirname "$0")" || exit 1
exec /home/thomas/build/bin/python3 export_graph_to_vault.py "$@"
