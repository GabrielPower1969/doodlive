# Lifecycle of a story pack — eight stages

`<id>` = story id (`jonah`), `<xx>` = script prefix (`jn`), `<SET>` = set name (`coast`). Run every command from
the repo root. A stage is done only when its **Done** line is true. Write what happened (dates, decisions, dead
ends) in the owner's Hours vault, never in this repo (`03-RULES.md` R2).

```
1 Plan ──► GATE 1 ──► 2 Look ──► GATE 2 ──► 3 Characters ─► 4 Animation ─┐
(script)   (owner)    (drafts)   (owner)    3 Set + sheet ───────────────┤
                                            4 Voice ─► re-time ─► 5 Music┤
                                            4 FX ────────────────────────┴─► 6 Integrate ─► 7 Device ─► GATE 3 ─► 8 Ship
```

## Stage 1 — Plan (already done for jonah and joseph)

Outputs: `docs/<id>/STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md`, `PLAN.md`.
Check: `python3 tools/story/build_timeline.py <id>` prints shots / lines / seconds and writes
`assets/<id>/timeline.json` (timed by estimates until voices exist).
**Done:** the command runs without error.

### GATE 1 — the owner approves the script
Show the owner: `STORY.md` (beats table), the lines from `story.py`, the estimated length. Optional but cheap:
draft voices (stage 4 Voice with 1 take per line) and `assets/<id>/audio/preview_mix.mp3`.
**Nothing in Blender starts before the owner says yes.** Record the answer and any changed lines in Hours.

## Stage 2 — Look drafts

- Characters: `python3 pipeline/<xx>_characters.py faces`, then `blender -b --factory-startup --python
  pipeline/<xx>_characters.py -- build` and `-- preview` → `assets/<id>/model/preview_*.png`.
- Set: `blender -b --factory-startup --python pipeline/<xx>_<SET>.py -- all` → `<SET>_preview_*.png`.
- Sheet draft: `python3 tools/story/make_sheet.py <id>` → `print/<id>-A4.png`.
Before any sheet build in a fresh checkout or worktree, copy the two title fonts into `pipeline/fonts/`
(`kaiti.ttf`, `hiragino-sans-gb-bold.ttf`; the folder is git-ignored), or the title is drawn with a fallback font.
**Done:** previews exist for every character (front, 3/4, each face) and the set (phone view), and a sheet draft.

### GATE 2 — the owner approves the look
Show: the character previews, the face overview, the set from the phone view, the sheet PNG.
**No animation, final music, FX or final voices before the owner says yes**: animation and UVs follow the meshes.

## Stage 3 — Characters final, Set + sheet final (parallel)

- Characters: `python3 pipeline/<xx>_characters.py all` (faces, build, proof, preview, uvcheck, posetest, verify).
- Set + sheet: `-- all` on the set script, then `python3 tools/story/make_sheet.py <id>`, then
  `python3 tools/story/make_colored_pdf.py <id>`.
- The sheet needs the characters' `id_characters_2x.*` and `regions_characters.json`; the characters need the
  sheet slots in `assets/<id>/design.json`. If a slot changes, re-run the characters, then the sheet.
**Done:** `05-QUALITY-BAR.md` §Characters, §Set, §Sheet all pass; `RIG.md` and `SET.md` written.

## Stage 4 — Animation, Voice, FX (parallel; animation needs stage 3 characters)

- Animation: `python3 pipeline/<xx>_animate.py all` → `assets/<id>/anim/*.glb`, `clips.json`, `contact_sheet.png`.
  Look at single clips with the probe: `<XX>_PROBE="<char>_<clip>:0,40:side" python3 pipeline/<xx>_animate.py probe`.
- Voice: write `tools/story/cast_<id>.json`, then `python3 tools/story/voice.py <id> gen`,
  `python3 tools/story/voice.py <id> check`, then **`python3 tools/story/build_timeline.py <id>`** (re-times the play).
- FX: aliases go in `assets/<id>/manifest.json` (`fx.aliases`); new ids (only those in CONTRACT §8) in
  `StoryFx<Id>.cs`; preview with `unity/Assets/DoodLive/DavidGoliath/Fx/Preview~/run.sh <id>`.
**Done:** `05-QUALITY-BAR.md` §Animation, §Voice, §FX pass; `ANIMATION.md`, `VOICE.md`, `FX.md` written.
After animation: the lead reads the animator's "staging" notes and fixes marks / timings in `story.py`
(hug distance, travel speeds, a clip that needs a lead-in), then re-runs `build_timeline.py`.

## Stage 5 — Music + SFX (after the voices re-timed the play)

`python3 tools/story/music_<id>.py` → cues, `cues.json`, SFX, `mix.json`, `assets/<id>/audio/preview_mix.mp3`.
Re-run it with `--skip-music --skip-sfx` after any later re-time to refresh the preview mix.
**Done:** `05-QUALITY-BAR.md` §Music passes; `MUSIC.md` written.

## Stage 6 — Integration (lead)

1. `assets/<id>/faces.json` (face per clip; copy the shape of `assets/ruth/faces.json`).
2. `assets/<id>/manifest.json`: `registry`, `library`, `strings`, `fx` (CONTRACT §9), then
   `python3 tools/story/merge_packs.py`, `python3 tools/make_fonts.py`.
3. `python3 tools/story/pack.py <id>`, `python3 tools/make_sheet_signatures.py`.
4. `python3 tools/story/check.py <id>` → **0 FAIL**.
**Done:** check prints 0 FAIL and `git status` shows no hand edit in a generated shared file.

## Stage 7 — Device (lead; ask the owner and the other sessions before Unity or the phone)

1. `scripts/build-apk.sh` (never pipe it), `scripts/install-apk.sh <serial>` (checks the build fingerprint).
2. Make sure the app language is 中文, then `scripts/record-demo.sh <id> <serial>`.
3. Check the recording: frames every few seconds (every shot shows what `story.py` describes; nobody stands inside
   scenery; faces are not hidden), the log has no errors, `VoiceBank <id>/zh: N lines, N bundled, 0 missing`.
4. Loudness: `ffmpeg -i <demo> -af ebur128 -f null -`. If it is far below −23 LUFS the capture is silent: record again.
5. Cover: put the demo file name, a second and a crop box in the manifest's `library.cover`, run
   `python3 tools/story/merge_packs.py` and `python3 tools/story/make_covers.py <id>`; look at
   `assets/<id>/cover.png`; rebuild once so the shelf shows it.
**Done:** a demo video normalised to −16 LUFS and a progress page are in the owner's Hours folder.

### GATE 3 — the owner watches and listens
Give the owner the demo and the "listen first" list from `VOICE.md` and `MUSIC.md`. Fix what they name.

## Stage 8 — Ship

Commit only this pack's paths plus the generated shared files, with one plain-English message that says what the
pack contains. Push only when the owner says so. Update `00-INDEX.md` (state) and the pack's `PLAN.md`.
