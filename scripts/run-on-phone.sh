#!/usr/bin/env bash
# Serve web/ and open it in Chrome on a USB-connected Android phone.
#
# adb reverse makes the phone's http://localhost:$PORT reach this Mac, so getUserMedia (camera) works
# without HTTPS: localhost is a secure context.
#
# Usage:  scripts/run-on-phone.sh                 # the only authorised device
#         ADB_SERIAL=<pixel-serial> scripts/run-on-phone.sh
# Env:    ADB (path to adb), PORT (default 8080)
set -euo pipefail
cd "$(dirname "$0")/.."

ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"
PORT="${PORT:-8080}"
[ -x "$ADB" ] || { echo "adb not found at $ADB (set ADB=...)"; exit 1; }

# --- pick exactly one device; never guess between several ---------------------------------------
list=$("$ADB" devices | awk 'NR>1 && NF>=2 {print $1, $2}')
if [ -z "$list" ]; then
  echo "No device seen over USB. Check: data cable (not charge-only), USB mode = File transfer, USB debugging on."
  exit 1
fi
if [ -n "${ADB_SERIAL:-}" ]; then
  state=$(echo "$list" | awk -v s="$ADB_SERIAL" '$1==s {print $2}')
  [ -n "$state" ] || { echo "Device $ADB_SERIAL not connected. Seen:"; echo "$list"; exit 1; }
else
  ready=$(echo "$list" | awk '$2=="device" {print $1}')
  count=$(echo "$ready" | grep -c . || true)
  if [ "$count" -gt 1 ]; then echo "Several authorised devices, set ADB_SERIAL:"; echo "$ready"; exit 1; fi
  ADB_SERIAL=${ready:-$(echo "$list" | head -1 | awk '{print $1}')}
  state=$(echo "$list" | awk -v s="$ADB_SERIAL" '$1==s {print $2}')
fi
if [ "$state" = unauthorized ]; then
  cat <<EOF
Device $ADB_SERIAL is 'unauthorized'. On the phone:
  1. Unlock the screen and accept "Allow USB debugging?" (tick Always allow).
  2. No prompt? Developer options -> Revoke USB debugging authorisations, toggle USB debugging off/on,
     unplug + replug. Then run this script again.
EOF
  exit 1
fi
[ "$state" = device ] || { echo "Device $ADB_SERIAL is '$state'"; exit 1; }
adb_() { "$ADB" -s "$ADB_SERIAL" "$@"; }

# --- serve + forward + open ---------------------------------------------------------------------
if ! lsof -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
  nohup python3 scripts/serve.py "$PORT" >/tmp/doodlive-http.log 2>&1 &
  echo "http server pid $! (log /tmp/doodlive-http.log)"
  sleep 1
fi
adb_ reverse tcp:"$PORT" tcp:"$PORT"
adb_ shell pm path com.android.chrome >/dev/null || { echo "Chrome is not installed on the phone"; exit 1; }
adb_ shell am start -a android.intent.action.VIEW -d "http://localhost:$PORT/index.html?t=$(date +%s)" com.android.chrome >/dev/null
echo "Opened http://localhost:$PORT on $(adb_ shell getprop ro.product.model | tr -d '\r') ($ADB_SERIAL)"
