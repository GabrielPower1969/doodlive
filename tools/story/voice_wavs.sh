#!/usr/bin/env bash
# Rebuild the WAV files of the extra-language voices (fr de ja es pt) from the MP3s that git keeps (docs/I18N.md §4).
# The WAVs are about 1 GB, so they stay out of git; Unity's StorySetup imports WAVs. Run once after a fresh clone.
# Usage: tools/story/voice_wavs.sh [langs...]   (default: fr de ja es pt). Skips WAVs that already exist.
set -euo pipefail; cd "$(dirname "$0")/../.."
LANGS=(fr de ja es pt); [ $# -gt 0 ] && LANGS=("$@")
n=0
for L in "${LANGS[@]}"; do
  for mp3 in assets/*/audio/voice/"$L"/*.mp3; do
    [ -e "$mp3" ] || continue
    wav="${mp3%.mp3}.wav"; [ -e "$wav" ] && continue
    ffmpeg -v error -y -i "$mp3" -ac 1 -ar 44100 -c:a pcm_s16le "$wav"; n=$((n+1))
  done
done
echo "voice_wavs: $n WAV files written"
