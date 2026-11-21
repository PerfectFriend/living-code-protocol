#!/bin/bash
# Отправка armeabi APK в топик 23616 через MTProto (telethon), с ожиданием slow mode.
PY=/home/thomas/.hermes/installs/tg-mtproto/venv/bin/python
SCRIPT=/home/thomas/Projects/TGSend/tg_send_file.py
APK=/home/thomas/apkexport/NeXX-android-foss-armeabi-v7a-debug.apk
umask 077
"$PY" "$SCRIPT" "$APK" "NeXX armeabi-v7a debug APK — сборка 08.11.2026, rustcore фазы 1-4 (19 JNI-символов), коммит c3bfedc"
