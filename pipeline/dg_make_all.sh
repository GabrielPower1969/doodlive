#!/usr/bin/env bash
# Rebuild everything David & Goliath produces from assets/david-goliath/design.json, in dependency order:
# characters -> desert -> colouring sheet (rendered from both) -> proofs that the models wear the sheet correctly.
# Logs go to $DG_WORK/<step>.log; a failing step prints the end of its log and stops the run.
set -euo pipefail
cd "$(dirname "$0")/.."
export DG_WORK="${DG_WORK:-/tmp/dg_work}"
mkdir -p "$DG_WORK"

fail() { echo "FAILED: $1 (log: $2)"; tail -30 "$2"; exit 1; }
run_blender() {  # <log name> <script> <mode>
  local log="$DG_WORK/$1.log"
  blender -b --factory-startup --python "$2" -- "$3" > "$log" 2>&1 || fail "$1" "$log"
  if grep -q "Traceback" "$log"; then grep -A12 Traceback "$log"; fail "$1" "$log"; fi
}

echo "1/8 characters: meshes, rig, weights, UVs, ID render, previews, GLBs"
run_blender build pipeline/dg_build.py build
grep -E "^\[(david|goliath)\]" "$DG_WORK/build.log" || true

echo "2/8 desert: desert.glb, desert_lines.json, UV-space ID render (print = 3D check); re-import check"
run_blender desert_build pipeline/dg_desert.py build
run_blender desert_verify pipeline/dg_desert.py verify
python3 -c "import json,sys; r=json.load(open('$DG_WORK/desert_verify.json')); print('desert verify', 'PASS' if r['pass'] else 'FAIL', r['tris'], 'tris'); sys.exit(0 if r['pass'] else 1)"

echo "3/8 sheet: line art, regions, template, demo colouring, A4 PNG+PDF, reference, checks"
python3 tools/make_dg_sheet.py > "$DG_WORK/sheet.log" 2>&1 || fail sheet "$DG_WORK/sheet.log"
tail -1 "$DG_WORK/sheet.log"

echo "4/8 uvcheck: characters textured with the demo colouring"
run_blender uvcheck pipeline/dg_build.py uvcheck

echo "5/8 verify: re-import the character GLBs"
run_blender verify pipeline/dg_build.py verify

echo "6/8 compose review images"
python3 pipeline/dg_compose.py > "$DG_WORK/compose.log" 2>&1 || fail compose "$DG_WORK/compose.log"

echo "7/8 desert previews (Desert role's views)"
run_blender desert_preview pipeline/dg_desert.py preview

echo "8/8 textured renders: characters + desert wearing the demo sheet on the sand ground, phone view"
run_blender sheet_render tools/make_dg_sheet.py render
ls assets/david-goliath/sheet/textured_*.png
echo "ALL DONE"
