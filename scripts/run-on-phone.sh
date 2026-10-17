#!/usr/bin/env bash
# Serve web/ and open it in Chrome on the USB-connected Android phone.
# adb reverse makes the phone's http://localhost:8080 hit this Mac, so the camera works without HTTPS.
set -euo pipefail
cd "$(dirname "$0")/.."
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
PORT="${PORT:-8080}"
"$ADB" get-state >/dev/null || { echo "No authorised device. Unlock the phone and accept 'Allow USB debugging'."; exit 1; }
if ! lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  python3 -m http.server "$PORT" -d web >/dev/null 2>&1 &
  echo "server pid $!"
  sleep 1
fi
"$ADB" reverse tcp:"$PORT" tcp:"$PORT"
"$ADB" shell am start -a android.intent.action.VIEW -d "http://localhost:$PORT/index.html?t=$(date +%s)" com.android.chrome >/dev/null
echo "Opened http://localhost:$PORT on $("$ADB" shell getprop ro.product.model | tr -d '\r')"
