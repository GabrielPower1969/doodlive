#!/usr/bin/env bash
# Acceptance screenshots per UI state (UX-PLAN §10). Drives the installed app over adb and saves
# docs/qa/<fingerprint>/<state>.png so a build can be reviewed state by state. Needs scripts/install-apk.sh done first.
# States the script can reach without a printed sheet: home, home-en, scan, help(30 s), demo-reveal, live, blow, read,
# more, greet(~20 s idle). Scanning a real sheet still needs a human.
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
a shell am force-stop $PKG; a shell input keyevent KEYCODE_WAKEUP; a shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1
shot home 6
tap 0.93 0.05;  shot home-en 1            # 中/EN toggle (top-right)
tap 0.93 0.05;  sleep 0.5                 # back to zh
tap 0.5 0.72;   shot scan 5               # 扫一扫 → permission (already granted) → Scan.Search
[ "$QUICK" = "--quick" ] || { shot help 31; }   # 30 s without a sheet → help card
a shell am force-stop $PKG; a shell monkey -p $PKG -c android.intent.category.LAUNCHER 1 >/dev/null 2>&1; sleep 5
tap 0.5 0.79;   shot demo-reveal 0.8      # 看演示 → Reveal (flash + enter)
shot live 4                               # Live.Idle with title + 3 buttons
tap 0.17 0.95;  shot blow 1.5             # 吹号角
sleep 3; tap 0.5 0.95; shot read 1.6      # 读一读 (mid sequence)
sleep 4; tap 0.93 0.86; shot more 1       # 更多 drawer
tap 0.93 0.86; tap 0.93 0.12; shot pinyin-abc 1   # close drawer, toggle ABC
[ "$QUICK" = "--quick" ] || { shot greet 22; }     # idle ≥ 20 s → greeting
a logcat -d | grep -oE "DoodLive state [A-Za-z]+ -> [A-Za-z]+" | uniq > "$OUT/states.log" || true
echo "== done: $(ls "$OUT" | wc -l | tr -d ' ') files; state log in $OUT/states.log"
