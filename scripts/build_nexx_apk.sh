#!/bin/bash
# NeXX: full offline build of rustcore + foss debug APK, detached from chat tool windows.
cd /home/thomas/simplex-fork-work/simplex-chat/apps/multiplatform || exit 1
export ANDROID_HOME=/home/thomas/build/android-sdk
export ANDROID_NDK_HOME=$ANDROID_HOME/ndk/27.3.13750724
export JAVA_HOME=/home/thomas/build/jdk/current
export PATH=$JAVA_HOME/bin:$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH
LOG=/tmp/build_cron_apk.log
: > "$LOG"
./gradlew :rustcore:assembleDebug :android:assembleFossDebug --offline --max-workers=8 -Dorg.gradle.jvmargs=-Xmx6g >> "$LOG" 2>&1
ec=$?
echo "GRADLE_EXIT=$ec" >> "$LOG"
# copy APKs if build ok
if [ $ec -eq 0 ]; then
  mkdir -p /home/thomas/apkexport
  for f in android/build/outputs/apk/foss/arm64-v8a/debug/*.apk android/build/outputs/apk/foss/armeabi-v7a/debug/*.apk; do
    [ -f "$f" ] && cp -f "$f" /home/thomas/apkexport/
  done
  echo "APK_COPIED" >> "$LOG"
fi
echo "=== RESULT ==="
grep -E "BUILD (SUCCESSFUL|FAILED)|GRADLE_EXIT|APK_COPIED" "$LOG" | tail -5
grep -E "^e: " "$LOG" | head -10
exit $ec
