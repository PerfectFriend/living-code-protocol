#!/usr/bin/env bash
# Мост для крона LV-vault-sync: оригинал лежит вне scripts-каталога
# (крон-раннер блокирует симлинки, резолвящиеся наружу).
exec /home/thomas/LivingCode/scripts/vault_sync.sh "$@"
