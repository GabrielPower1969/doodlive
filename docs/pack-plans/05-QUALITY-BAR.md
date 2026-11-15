# Quality bar — numbers to hit before a role is "done"

Paste the measured value next to each line in your report.

## Characters
- [ ] Bones on the re-imported GLB = the contract list exactly (names and parents); no animations in the model GLB.
- [ ] ≤ 25,000 triangles per human (non-humans: the pack's CONTRACT); ≤ 4 influences per vertex.
- [ ] Height within 2 % of CONTRACT §2; feet on y = 0.
- [ ] Every expression in DESIGN §1 exists as a decal and was looked at on the model.
- [ ] Eyes close visibly (pose test); the jaw opens.
- [ ] UV proof: the front view equals the sheet; back and 3/4 views keep each region's colour.
- [ ] Every printed region ≥ 6 mm, or listed as a detail line / anchored part in `RIG.md`.

## Set
- [ ] Every node named in CONTRACT §6 exists; hidden props are separate nodes.
- [ ] ≤ 60,000 triangles; no UV outside 0-1.
- [ ] `CLEARANCE` OK for every mark and every straight path in `story.py`.
- [ ] Looked at: phone view, top-down, each location close-up, each hidden prop shown.

## Sheet
- [ ] `checks.json`: all pass; no slivers; every anchor on its own region.
- [ ] Every set region ≥ 6 mm; cast regions under 6 mm are listed.
- [ ] Title band match score against every other sheet < 0.6.
- [ ] `print/<id>-A4.pdf` and `print/<id>-A4-colored.pdf` are 210 × 297 mm; the four markers sit where the blank
      reference has them.

## Animation
- [ ] Every clip in CONTRACT §4 exists with the exact name (count them).
- [ ] Loops: the seam step is no larger than the largest step inside the clip.
- [ ] Planted feet slide ≤ 0.002; walk slip ≤ 0.02 units/s.
- [ ] Kneeling / seated clips: lowest mesh point ≥ −0.008.
- [ ] Two-person clips probed as a pair at the stated distance: no intersection of bodies.
- [ ] `clips.json`: loop flags, markers, travel speeds.
- [ ] Anim export newer than the model files.

## Voice
- [ ] Every line in both languages; `voice.py <id> check` passes.
- [ ] −16.0 ± 0.4 LUFS; true peak ≤ −1.5 dBTP.
- [ ] Transcript error per line ≤ 0.1; every proper name heard correctly (or noted as a homophone).
- [ ] One pitch range per role (state the Hz range per line).
- [ ] `sources.json` names engine and licence for every clip; no `edge-tts`.

## Music + SFX
- [ ] Every cue and SFX id in CONTRACT §7 exists.
- [ ] Music −20.0 LUFS on the composed part; SFX peak −3.0 dBFS.
- [ ] Loop joins: no click; level difference between repeats 0 dB; file ≥ 1.3 × its section.
- [ ] `preview_mix.mp3` has all lines.

## FX
- [ ] Every id used in `story.py` resolves (existing, alias or new).
- [ ] New ids = the list in CONTRACT §8, nothing more.
- [ ] Contact sheet looked at; no effect covers a face.
- [ ] Compiles outside Unity with 0 errors.

## Integration
- [ ] `python3 tools/story/check.py <id>`: 0 FAIL.
- [ ] `python3 tools/story/merge_packs.py --check`: up to date.

## Device
- [ ] Installed build fingerprint confirmed by `install-apk.sh`.
- [ ] The story plays start to finish; log shows `0 missing` voices and no errors.
- [ ] Demo recorded in 中文; loudness measured; normalised copy at −16 LUFS.
- [ ] Every shot matches its `desc` in `story.py`; no actor inside scenery; no hidden face in a talking shot.
- [ ] Total length within the target in the pack's `STORY.md` (± 20 s), or the lead proposed cuts.
