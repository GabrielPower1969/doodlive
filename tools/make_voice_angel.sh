#!/usr/bin/env bash
# Angel voice lines (zh-CN, Microsoft neural voice via edge-tts; free, no key) → web/assets/voice/zh/*.mp3
# and unity/Assets/DoodLive/Audio/voice_*.wav (replaces the macOS `say` clips from tools/make_audio.py).
# Lines mirror web/app.js (hello + LINES). Keep them free of anything private: they are sent to Microsoft's TTS.
#   python3 -m venv .venv-tts && .venv-tts/bin/pip install edge-tts && tools/make_voice_angel.sh
set -euo pipefail
cd "$(dirname "$0")/.."
TTS="${TTS:-.venv-tts/bin/edge-tts}"; VOICE="${VOICE:-zh-CN-XiaoyiNeural}"   # young, bright; XiaoxiaoNeural = warmer alt
OUT=web/assets/voice/zh; UOUT=unity/Assets/DoodLive/Audio; RAW="$(mktemp -d)"; trap 'rm -rf "$RAW"' EXIT
mkdir -p "$OUT" "$UOUT"
gen() { "$TTS" --voice "$VOICE" --rate="+4%" --pitch="+6Hz" --text "$2" --write-media "$RAW/$1.mp3"; }
gen voice_hello "哇！我活过来啦！谢谢你给我涂上这么漂亮的颜色！"
gen voice_0     "听！天堂的号角为你吹响！"
gen voice_1     "你画得真好看，我好喜欢这些颜色！"
gen voice_2     "愿你今天平安、快乐！"
gen voice_3     "再给我画一件新衣服吧！"
for f in voice_hello voice_0 voice_1 voice_2 voice_3; do
  ffmpeg -y -loglevel error -i "$RAW/$f.mp3" -af "loudnorm=I=-16:TP=-1.5" -ac 1 -b:a 96k "$OUT/$f.mp3"
  ffmpeg -y -loglevel error -i "$RAW/$f.mp3" -af "loudnorm=I=-16:TP=-1.5" -ac 1 -ar 44100 "$UOUT/$f.wav"
  printf "%-12s %5.2fs\n" "$f" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$f.mp3")"
done
