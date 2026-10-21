#!/usr/bin/env bash
# Build the native Unity APK: unity/Builds/DoodLive.apk (ARM64, IL2CPP, ARCore required).
# Needs Unity 2022.3 LTS + Android module (SDK/NDK/OpenJDK) on THIS machine only; phones just `adb install` the APK.
# Two batch runs on purpose: Setup changes scripting defines, so Build must start in a fresh editor (LESSONS L22).
#
# Usage: scripts/build-apk.sh [--skip-setup]     Env: UNITY=/path/to/Unity (default: Hub 2022.3.62f3)
set -euo pipefail
cd "$(dirname "$0")/../unity"
UNITY="${UNITY:-/Applications/Unity/Hub/Editor/2022.3.62f3/Unity.app/Contents/MacOS/Unity}"
[ -x "$UNITY" ] || { echo "Unity not found at $UNITY (set UNITY=...)"; exit 1; }
if pgrep -f "projectPath $PWD" >/dev/null; then echo "Another Unity has this project open; close it first"; exit 1; fi
rm -f Temp/UnityLockfile   # left behind by a crashed editor; safe when no editor is running (checked above)
mkdir -p Logs Builds
run() {
  local method=$1 log="Logs/$1-$(date +%Y%m%d-%H%M%S).log"
  echo "== $method (log: unity/$log)"
  "$UNITY" -batchmode -nographics -quit -projectPath "$PWD" -buildTarget Android \
    -executeMethod "DoodLive.EditorTools.DoodLiveSetup.$method" -logFile "$PWD/$log" || {
      grep -E "error CS|Error building|BuildFailedException|DoodLive build" "$log" | head -20; exit 1; }
}
[ "${1:-}" = "--skip-setup" ] || run Setup
run Build
ls -la Builds/DoodLive.apk
echo "Install on a phone:  adb install -r unity/Builds/DoodLive.apk"
