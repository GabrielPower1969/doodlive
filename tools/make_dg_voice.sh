#!/usr/bin/env bash
# David & Goliath voice lines, zh + en → assets/david-goliath/audio/voice/{zh,en}/<id>.{wav,mp3},
# durations.json, report.json, zh.srt, en.srt, and the voice-record session under record/.
# Microsoft neural voices through edge-tts (free, no key; the lines are sent to Microsoft's TTS endpoint,
# so they must stay public Bible text). Cast and per-line direction: tools/dg_voice_cast.json. Docs: docs/david-goliath/VOICE.md.
#   python3 -m venv .venv-tts && .venv-tts/bin/pip install edge-tts      (once)
#   tools/make_dg_voice.sh                      # all lines, both languages, then check + session
#   tools/make_dg_voice.sh gen --lang en --only dg_14
#   tools/make_dg_voice.sh import ~/voice-out --lang zh      # your own recordings replace TTS
#   tools/make_dg_voice.sh check
# Exit status 1 = some clip overruns its maxSec or the next line (see the table it prints).
set -euo pipefail
cd "$(dirname "$0")/.."
# Call edge-tts as a module: the venv's bin/edge-tts shebang can point at an old absolute path after the repo moves.
PY="${PY:-.venv-tts/bin/python3}"
"$PY" -c 'import edge_tts' 2>/dev/null || { echo "edge-tts missing: python3 -m venv .venv-tts && .venv-tts/bin/pip install edge-tts" >&2; exit 2; }
case "$(ffmpeg -hide_banner -filters 2>/dev/null || true)" in *rubberband*) ;; *) echo "need ffmpeg with rubberband (brew install ffmpeg)" >&2; exit 2;; esac
if [ $# -eq 0 ]; then
  "$PY" tools/dg_voice_build.py session
  exec "$PY" tools/dg_voice_build.py gen --lang all
fi
exec "$PY" tools/dg_voice_build.py "$@"
