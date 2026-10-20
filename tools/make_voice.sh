#!/usr/bin/env bash
# Voice-over clips for the battle scene → web/assets/voice/en/*.mp3
# Microsoft neural voices through edge-tts (free, no key; the lines are sent to Microsoft's TTS
# endpoint — keep them free of anything private). Goliath is pitched down and given a small room
# with ffmpeg. Re-run after changing a line in web/battle/battle.js LINES.
#   python3 -m venv .venv-tts && .venv-tts/bin/pip install edge-tts && tools/make_voice.sh
set -euo pipefail
cd "$(dirname "$0")/.."
TTS="${TTS:-.venv-tts/bin/edge-tts}"; OUT=web/assets/voice/en; RAW="$(mktemp -d)"; trap 'rm -rf "$RAW"' EXIT
mkdir -p "$OUT"
gen() { "$TTS" --voice "$2" ${3:+--rate="$3"} ${4:+--pitch="$4"} --text "$5" --write-media "$RAW/$1.mp3"; }
gen goliath  en-US-ChristopherNeural "+8%" "-20Hz" "Am I a dog, that you come at me with a stick? I'll feed you to the birds!"
gen david    en-US-AnaNeural         "+4%" ""      "You come with a sword and a spear. I come in the name of the Lord of Hosts!"
gen narrator en-GB-SoniaNeural       "-6%" ""      "With one small stone, David brought down the giant Goliath. Courage matters more than size."
ffmpeg -y -loglevel error -i "$RAW/goliath.mp3"  -af "asetrate=24000*0.88,aresample=24000,atempo=1.14,aecho=0.8:0.5:35:0.2,loudnorm=I=-16:TP=-1.5" -ac 1 -b:a 96k "$OUT/goliath.mp3"
ffmpeg -y -loglevel error -i "$RAW/david.mp3"    -af "loudnorm=I=-16:TP=-1.5" -ac 1 -b:a 96k "$OUT/david.mp3"
ffmpeg -y -loglevel error -i "$RAW/narrator.mp3" -af "loudnorm=I=-16:TP=-1.5" -ac 1 -b:a 96k "$OUT/narrator.mp3"
for f in goliath david narrator; do printf "%-9s %5.2fs\n" "$f" "$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$OUT/$f.mp3")"; done
