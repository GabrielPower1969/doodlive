#!/usr/bin/env bash
# Install unity/Builds/DoodLive.apk and PROVE the phone runs exactly that build.
# The build stamps a fingerprint (git short sha + UTC time) into versionName and into the app's log line
# "DoodLive build <fingerprint>". This script refuses to call an install "done" unless the installed
# versionName and the running app's log both match the fingerprint recorded at build time (LESSONS L28).
#
# Usage: scripts/install-apk.sh [serial]        (default: the only authorised device)
set -euo pipefail
cd "$(dirname "$0")/.."
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"; APK=unity/Builds/DoodLive.apk; PKG=today.onemorething.doodlive
[ -f "$APK.fingerprint" ] || { echo "no $APK.fingerprint — run scripts/build-apk.sh first"; exit 1; }
FP=$(cat "$APK.fingerprint")
S="${1:-$($ADB devices | awk 'NR>1 && $2=="device"{print $1}' | head -1)}"
[ -n "$S" ] || { echo "no authorised device"; exit 1; }
echo "== installing build $FP on $S"
"$ADB" -s "$S" install -r "$APK" | tail -1
GOT=$("$ADB" -s "$S" shell dumpsys package $PKG | grep -m1 versionName | sed 's/.*versionName=//' | tr -d '\r')
[ "$GOT" = "$FP" ] || { echo "FINGERPRINT MISMATCH: installed '$GOT' but built '$FP'"; exit 2; }
"$ADB" -s "$S" shell am force-stop $PKG; "$ADB" -s "$S" logcat -c
"$ADB" -s "$S" shell input keyevent KEYCODE_WAKEUP; "$ADB" -s "$S" shell wm dismiss-keyguard 2>/dev/null   # an asleep phone never starts Unity (no log line); a PIN lock still needs a human
"$ADB" -s "$S" shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
for i in $(seq 1 20); do
  if "$ADB" -s "$S" logcat -d | grep -q "DoodLive build $FP"; then echo "== running build $FP confirmed on $S ($("$ADB" -s "$S" shell getprop ro.product.model | tr -d '\r'))"; exit 0; fi
  sleep 1
done
echo "app started but did not log 'DoodLive build $FP' within 20 s"; exit 3
