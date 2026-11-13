#!/usr/bin/env bash
# Record a story's home-screen demo on the phone (screen + app audio) with scrcpy, for review videos.
# The app starts straight into the demo through the "demo" intent extra (ARColoringController.AutoDemo).
#
# Usage: scripts/record-demo.sh <story-id|angel> [serial] [seconds]
#   Output: unity/Builds/demo-<id>-<fingerprint>.mp4 (git-ignored).  Needs: brew install scrcpy
set -euo pipefail
cd "$(dirname "$0")/.."
ID="${1:?story id}"; ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"; PKG=today.onemorething.doodlive
S="${2:-$($ADB devices | awk 'NR>1 && $2=="device"{print $1}' | head -1)}"
SECS="${3:-$(python3 -c "import json,sys; print(int(json.load(open('assets/$ID/timeline.json'))['duration'] + 6))" 2>/dev/null || echo 120)}"
FP=$(cat unity/Builds/DoodLive.apk.fingerprint 2>/dev/null || echo dev)
OUT="unity/Builds/demo-$ID-$FP.mp4"
"$ADB" -s "$S" shell input keyevent KEYCODE_WAKEUP; "$ADB" -s "$S" shell wm dismiss-keyguard 2>/dev/null || true
"$ADB" -s "$S" shell svc power stayon usb >/dev/null 2>&1 || true
"$ADB" -s "$S" shell am force-stop $PKG
"$ADB" -s "$S" shell am start -n $PKG/com.unity3d.player.UnityPlayerActivity --es demo "$ID" >/dev/null
sleep 1
ADB="$ADB" scrcpy -s "$S" --no-playback --record="$OUT" --audio-codec=aac --audio-bit-rate=192K \
  --video-bit-rate=12M --max-fps=30 --time-limit="$SECS" >/dev/null 2>&1
"$ADB" -s "$S" shell svc power stayon false >/dev/null 2>&1 || true
ls -la "$OUT"; echo "recorded $SECS s of '$ID' (build $FP) -> $OUT"
