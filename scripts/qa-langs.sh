#!/usr/bin/env bash
# Screenshots of every language (docs/I18N.md): the bookshelf, a book page and a story's subtitles in each of the
# eight languages, saved to docs/qa/<fingerprint>/lang-<code>-*.png. Needs scripts/install-apk.sh done first.
# The app is started with `--es lang <code>` (Platform.Native.Args), so no tapping through the picker is needed.
# Usage: scripts/qa-langs.sh [serial] [story-id] [langs...]   (defaults: first device, gabriel, all eight)
set -euo pipefail; cd "$(dirname "$0")/.."
ADB="${ADB:-$HOME/Library/Android/sdk/platform-tools/adb}"; PKG=today.onemorething.doodlive
S="${1:-$($ADB devices | awk 'NR>1 && $2=="device"{print $1}' | head -1)}"; STORY="${2:-gabriel}"
LANGS=(zh en fr de ja es ar pt); [ $# -gt 2 ] && LANGS=("${@:3}")
FP=$(cat unity/Builds/DoodLive.apk.fingerprint); OUT="docs/qa/$FP"; mkdir -p "$OUT"
a() { "$ADB" -s "$S" "$@"; }
shot() { sleep "${2:-1.5}"; a exec-out screencap -p > "$OUT/$1.png"; echo "  $1"; }
start() { a shell am force-stop $PKG; a shell input keyevent KEYCODE_WAKEUP; a shell wm dismiss-keyguard 2>/dev/null || true
          a shell am start -n $PKG/com.unity3d.player.UnityPlayerActivity "$@" >/dev/null; }
echo "== language shots for $FP on $S -> $OUT"
for L in "${LANGS[@]}"; do
  a logcat -c
  start --es lang "$L"; shot "lang-$L-home" 7
  start --es lang "$L" --es demo "$STORY"; shot "lang-$L-story-a" 14; shot "lang-$L-story-b" 8
  a logcat -d | grep -E "DoodLive (platform|voice|stage)|Exception" | head -8 > "$OUT/lang-$L.log" || true
done
a shell am force-stop $PKG
echo "== done: $(ls "$OUT"/lang-* | wc -l | tr -d ' ') files"
