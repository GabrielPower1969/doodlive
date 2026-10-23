#!/usr/bin/env bash
# Acceptance screenshots per UI state (UX-PLAN §10). Drives the installed app over adb and saves
# docs/qa/<fingerprint>/<state>.png so a build can be reviewed state by state. Needs scripts/install-apk.sh done first.
# States the script can reach without a printed sheet: home, grown-ups panel, scan, help(30 s), demo-reveal, live,
# hint, blow, read, rescan. Scanning a real sheet still needs a human.
# Usage: scripts/qa-shots.sh [serial] [--quick]   (--quick skips the 30 s help and 20 s greet waits)
set -euo pipefail; cd "$(dirname "$0")/.."
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"; PKG=today.onemorething.doodlive
S="${1:-$($ADB devices | awk 'NR>1 && $2=="device"{print $1}' | head -1)}"; QUICK="${2:-}"
FP=$(cat unity/Builds/DoodLive.apk.fingerprint); OUT="docs/qa/$FP"; mkdir -p "$OUT"
a() { "$ADB" -s "$S" "$@"; }
shot() { sleep "${2:-1.5}"; a exec-out screencap -p > "$OUT/$1.png"; echo "  $1"; }
# screen geometry → tap points (fractions of the screen), portrait assumed
read -r W H < <(a shell wm size | sed -E 's/.*: ([0-9]+)x([0-9]+).*/\1 \2/')
tap() { a shell input tap $(python3 -c "print(int($1*$W), int($2*$H))"); }
echo "== QA shots for $FP on $S ($W x $H) -> $OUT"
a shell am force-stop $PKG; a shell input keyevent KEYCODE_WAKEUP; a shell wm dismiss-keyguard 2>/dev/null; a shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
shot home 6
# tap points follow ARColoringController.UI.cs (u = min(W,H)/12.5): lock chip top-right, home shutter at 0.69H,
# demo tag under it, new-sheet chip bottom-right. Fractions are for a portrait phone (Pixel 8 measured).
hold() { a shell input swipe $(python3 -c "print(int($1*$W), int($2*$H), int($1*$W), int($2*$H))") "${3:-2600}"; }
tap 0.5 0.5; sleep 0.3                    # wake the UI
hold 0.926 0.082; shot grownups 1.2       # hold the lock 2 s -> grown-ups panel (09)
tap 0.628 0.379; sleep 0.6                # 好了 / Done
tap 0.5 0.733;  shot scan 5               # shutter -> permission (granted) -> Scan.Search (02)
[ "$QUICK" = "--quick" ] || { shot help 31; }   # 30 s without a sheet -> help card (04)
a shell am force-stop $PKG; a shell input keyevent KEYCODE_WAKEUP; a shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 5
tap 0.5 0.862;  shot demo-reveal 0.6      # 看演示 -> Reveal: flash + crayon burst (05)
shot live 4                               # Live.Idle, speech bubble (06)
shot hint 7                               # 5 s without a touch -> dotted ring + hand (06)
tap 0.5 0.55;   shot blow 1.5             # tap the angel -> trumpet + line
sleep 4; tap 0.5 0.2; shot read 1.4       # tap the 3D title -> read it (07)
sleep 4; tap 0.926 0.936; shot rescan 2   # new-sheet chip -> back to scan / home
a logcat -d | grep -oE "DoodLive state [A-Za-z]+ -> [A-Za-z]+" | uniq > "$OUT/states.log" || true
echo "== done: $(ls "$OUT" | wc -l | tr -d ' ') files; state log in $OUT/states.log"
