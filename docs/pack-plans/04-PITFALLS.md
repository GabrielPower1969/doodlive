# Pitfalls — things that already went wrong once

From the Daniel, Gabriel, Exodus and Esther packs. Read your role's list before you start. More: `docs/LESSONS.md`.

## Characters
- **C1 Eyelids inside the head.** Lid rows took the head's depth at rest height, so closed eyes were invisible
  (Daniel's lions). Put the lids on the frontmost surface along their whole travel; test a pose with eyes closed.
- **C2 Hands overlap on the sheet.** Three A-pose figures fit at sheetX −0.34 / 0 / +0.34 and no closer. A fourth
  figure goes on a second row.
- **C3 Regions under 6 mm.** Sashes, collars, shoes, hair bands: make them detail lines or let them take a
  neighbour's or a set region's colour. Faces and hair are small on every sheet; that is known.
- **C4 Front projection prints through the body** ("two-faced balloon people", LESSONS L51). Back faces that would
  sample another region take a clean texel of their own region.
- **C5 Non-human in side view.** A lion or a fish is coloured in profile: UV0 is the side projection at the slot,
  and the far side mirrors it.
- **C6 A mouth that does not open.** If the jaw only moves the chin, the open mouth must be a face decal (the
  lion's yawn needed its own decal). Decide per expression which it is.
- **C7 Hidden props still need a colour.** A prop hidden on the sheet takes its UV from another printed region
  (`PROP_ANCHORS`); say which in `RIG.md`.
- **C8 Triangle budget.** 25k per human. Count after export, on the re-imported GLB.

## Set + sheet
- **S1 Marks blocked.** A wall 0.012 from an actor's path looked fine in the preview and failed on the phone.
  Print `CLEARANCE` for every mark and every straight path in `story.py`.
- **S2 Tall things in front.** Anything high between the camera and the actors hides faces. Keep palms and masts at
  the back or the side; crown bottoms above head height.
- **S3 The title band must be distinct.** Compare with every other sheet (the make_sheet check); change box size or
  spacing if the match score is high.
- **S4 Title fonts.** `pipeline/fonts/` is git-ignored: copy `kaiti.ttf` and `hiragino-sans-gb-bold.ttf` in before
  building a sheet in a fresh checkout.
- **S5 Hidden set props** (a plant state, a prison cell) share the place of something else; make sure only one is
  visible at a time and that each has sheet regions or a stated anchor.
- **S6 Coloured PDF.** After the sheet, run `make_colored_pdf.py <id>`; it must be true A4 like the blank one.
- **S7 Budget.** 60k triangles; spend them where the phone camera looks.

## Animation
- **A1 Two people too close.** Hug / lift / shake clips assume the partner 0.11 away; the timeline once had 0.08
  and bellies intersected. State the distance; the lead sets the marks.
- **A2 Glides.** An `idle` with a `to` slides the actor. Use a walk clip to move.
- **A3 Impossible speeds.** A stomp walk needed 3.5× its natural speed. Put each travel clip's speed in
  `clips.json`; list moves in `story.py` that need more than 1.6×.
- **A4 A loop cannot change posture.** `kneel_talk` could not kneel down by itself: add a one-shot lead-in clip and
  tell the lead.
- **A5 An arm across the face.** Gabriel's trumpet arm hid his face. Check every "hand to head" clip from the
  phone angle.
- **A6 Knees and seats on the floor.** Lowest mesh point ≥ −0.008; seated clips rest the hips on the ground.
- **A7 Models rebuilt under you.** Read the current model each run; at the end, check the anim export is newer
  than the model files.
- **A8 Starting two clips at the same instant** means only the second is seen. Say so in the staging notes.
- **A9 Pops, climbs and the "all" camera** (`tools/story/build_timeline.py` helpers). `prop(id, True, grow=0.4)`
  pops a prop in (scale ~0 → 1, ease-out-back); `prop(id, False, grow=0.3)` shrinks it away; without `grow` it
  appears at once. Best on a whole actor or a set node; on a bone the clip may own the scale. `act(..., to=..., y=...)`
  with a new `y` eases the height over the walk (a plank, a dais); `snap=True` and moves without `to` still jump.
  Camera target `all` skips actors hidden with `prop("<actor>", False)` and actors standing beyond the page
  (|x| > 0.7 or y > 0.45); park off-stage actors there.

## Voice
- **V1 One person per role.** Designed voices drift between lines. Pin pitch range; pick the takes that sound most
  alike; list the doubtful lines.
- **V2 Interjections read as words.** Generate 哼 / 嘿嘿 / 啊呜 / shrieks as separate short phrases and splice.
- **V3 Names.** Check the transcript for every proper name (约拿, 尼尼微, 约瑟, 雅各, 法老, 埃及); use `sayMap` if a
  character is misread.
- **V4 Whisper hallucinations.** Repeated subtitle-credit lines in a check transcript are not speech; re-run with
  `condition_on_previous_text=False`.
- **V5 Nobody has listened.** Measurements pick takes; a person must still listen. Always give the "listen first" list.

## Music + SFX
- **M1 Temp files filled the disk.** Delete stems as you go.
- **M2 Loops must be seamless** and at least 30 % longer than their section, so a longer voice does not run out.
- **M3 Re-time.** Render after the voices re-timed the timeline; refresh the preview mix after any later re-time.
- **M4 Creature sounds** (roar, moo, gulp) are the weakest part of synthesis: keep them short and comic.

## FX
- **F1 An id may already exist** under another name; alias it in the manifest, never redefine it.
- **F2 Effects that overlap in time** (sunset into night) muddy the picture: give durations that end at the shot change.
- **F3 An effect on a node that does not exist yet.** Use node names from CONTRACT §6 only.
- **F4 White on white** (feathers before wings, foam on sand): check contrast over the real set colours.

## Integration and device
- **I1 The app language** may have been left on English by another session: set it to 中文 before recording.
- **I2 Silent recording.** The first screen recordings after an install had a silent audio track once; measure
  loudness before using a demo.
- **I3 Covers.** Pick a frame where the faces are visible; crop by hand (`box`).
- **I3a No cover = no book on the shelf.** The home screen reads `unity/Assets/DoodLive/Resources/library.json`,
  which only `make_covers.py` writes. `record-demo.sh` starts the story directly, so a demo can play end to end while
  the shelf still ends at the previous book (happened to miracles / lastsupper / risen, 2026-11-18). After the first
  demo: cover step (stage 7.5), rebuild, then open the app by hand and scroll the shelf to the new book.
- **I4 Shared cast ids.** `king`, `pharaoh`, `people` exist in other packs. If the name differs in this story,
  add a per-story string `dg_<id>_<who>`.
- **I5 Generated files.** `L10n.cs`, fonts, `sheet_signatures.json`, `Resources/library.json` are regenerated;
  Unity's prefab / scene / ProjectSettings changes after a build are not committed.
