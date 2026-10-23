#!/usr/bin/env bash
# Write web/build.json = {sha, time}; app.js logs "DoodLive web build <sha>.<time>" and shows it in the HUD corner,
# so a phone page can be matched to the commit it came from (same rule as the APK fingerprint, LESSONS L28).
set -euo pipefail; cd "$(dirname "$0")/.."
sha="$(git rev-parse --short HEAD)$(git diff --quiet HEAD -- web assets tools ':!web/build.json' 2>/dev/null || echo -dirty)"
printf '{"sha":"%s","time":"%s"}\n' "$sha" "$(date -u +%Y%m%d-%H%M)" > web/build.json
echo "web build: $sha  $(cat web/build.json)"
