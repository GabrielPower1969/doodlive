# He Is Risen! — production contract

Binding for every role. Story and lines: `STORY.md` + `storyboard/story.py`. Look: `DESIGN.md`. How to run each step:
`docs/pack-plans/01-LIFECYCLE.md`. Shared rules: `docs/pack-plans/03-RULES.md`. Kit: `docs/STORY-KIT.md`.
Template packs to copy from: **The King Who Serves** (`pipeline/ls_*.py`: reusing the Miracles Jesus and Peter by
running `mi_characters.py` in the pack namespace, fixed-paint disciples, the doll's-house upstairs room, `ride()`
seat method) and **Real Miracles** (`pipeline/mi_*.py`). Women: Ruth (`pipeline/ru_characters.py`, `build_ruth`,
`build_naomi`) as the reference for a female body, veil and long dress. Wings: Gabriel (`pipeline/ga_character.py`,
wing layout and feather rows) as a reference only (that hero is 90k triangles; this angel is not Gabriel, §2).

Ids: story `risen`, script prefix `rs` (no other pack uses `rs_` / `RS_`; checked 2026-11-18), env prefix `RS_`, page
material `rs_page`, set `garden` (no other pack uses it; checked 2026-11-18).

## 1. Files and owners

| Role | Owns |
|---|---|
| Lead (story + integration) | `docs/risen/*` (except the role docs below), `assets/risen/timeline.json` (generated), `docs/risen/STORYBOARD.md` (generated), `assets/risen/manifest.json`, `assets/risen/{pack,faces}.json`, Unity, builds, device |
| Characters | `pipeline/rs_characters.py`, `assets/risen/model/{jesus,mary,angel,peter,john,thomas,joanna}.glb`, `extras_paint.png`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/risen/RIG.md`, `docs/risen/design/faces/` |
| Set + sheet | `pipeline/rs_garden.py`, `assets/risen/model/garden.{glb,blend}`, `garden_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_risen.py` (only if `make_sheet.py` cannot do it as is), `assets/risen/sheet/`, `print/risen-A4.{png,pdf}`, `print/risen-A4-colored.pdf`, `assets/risen/design.json`, `docs/risen/SET.md` |
| Animation | `pipeline/rs_animate.py`, `assets/risen/anim/`, `docs/risen/ANIMATION.md` |
| Voice | `tools/story/cast_risen.json`, `assets/risen/audio/voice/`, `docs/risen/VOICE.md` |
| Music + SFX | `tools/story/music_risen.py`, `assets/risen/audio/music/`, `assets/risen/audio/sfx/`, `docs/risen/MUSIC.md` |
| FX | `manifest.json` `fx.aliases` first; `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxRisen.cs` only for the new ids in §8; `docs/risen/FX.md` |

Nobody edits `assets/stories.json`, `assets/library.json`, `tools/i18n/strings.json` or `DGFxEffects.cs` by hand.
**Nobody edits any `mi_*` / `ls_*` file, `assets/miracles/` or `assets/lastsupper/`**: this pack reads them, it does
not change them (R1, R5).

## 2. Cast

Units: art-width units (1.0 = art rectangle width), Y up, page = XZ plane at y = 0, +Z toward the viewer, +X right.

| Id | Height | Sheet slot (start value; Set + sheet owns the final one in `design.json`) | Paint |
|---|---|---|---|
| `angel` | 0.40 (wing tops 0.46) | sheetX −0.32, sheetY 0.015; wings spread ≤ ±0.14 from its centre (−0.46…−0.18) | scanned |
| `jesus` | 0.36 | sheetX 0.0, sheetY 0.015 (the Miracles slot) | scanned |
| `mary` | 0.34 | sheetX 0.32, sheetY 0.015 | scanned |
| `peter` | 0.38 | not on the sheet: fixed paint `model/extras_paint.png`, Miracles demo colours | fixed |
| `john` | 0.33 | not on the sheet: fixed paint (The King Who Serves colours) | fixed |
| `thomas` `joanna` | 0.36 / 0.33 | not on the sheet: fixed paint | fixed |

**Reuse, never fork** (R5):
- `jesus` and `peter`: `pipeline/rs_characters.py` gets `build_jesus` / `build_peter` from `pipeline/mi_characters.py`
  **unchanged**, the way `pipeline/ls_characters.py` does (`_run_miracles()`: the Miracles module run in the pack
  namespace, definitions only). Same heights, proportions (`SPEC`), faces, costume, regions, palette. This pack adds
  only the `fish` prop (§3). Peter is not printed here, so his front ID render on a virtual page becomes his part of
  `extras_paint.png` (Esther `GUARDS` / Miracles friends method), with the Miracles demo colours.
- `john`: `build_friend` with The King Who Serves' `FRIEND["john"]` costume (beardless, sky-blue tunic, white sash),
  taken from `pipeline/ls_characters.py` the same way (run it in the namespace, or import its `FRIEND` table). The
  Characters role chooses one of: (a) run `ls_characters.py` in the namespace (it already runs Miracles), or (b) if both
  packs now need the same thing, move `build_jesus` / `build_peter` / `build_friend` and their constants into
  `pipeline/story_kit/` with `mi_characters.py` and `ls_characters.py` regenerating byte-identical GLBs. Say which in
  `RIG.md`. Do not copy and edit them.
- `thomas`: `build_friend` with a new costume entry (square beard, head band, short cloak over both shoulders).
- `mary` (printed) and `joanna` (fixed): one new female builder `build_woman(costume)` in `rs_characters.py` (veil,
  long dress with wide sleeves, sash; Ruth's builders are the reference). Joanna = the same builder, another costume.
- `angel`: a new builder: the kit human body (robe to the feet, broad sash, short curls) plus two simple wings
  (three feather rows each, layered cards; Gabriel's wing layout as reference, not his code). ≤ 30k triangles with
  the wings.

Budget: each human ≤ 25k triangles (fixed-paint extras ≤ 18k; the angel ≤ 30k); ≤ 4 bone influences. Props count in
their owner's budget. Sheet slot note: three printed figures at −0.32 / 0 / +0.32 (C2); the angel's wings must stay
inside ±0.14 of its centre so they neither touch Jesus's A-pose hands nor run off the page.

## 3. Skeletons

Humans (all seven): the kit's contract bones, A-pose, facing +Z:
`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids`. Extras:
- `jesus`: the Miracles extras `mantle1`, `belt1`; prop `fish` (child of `handR`, mesh `jesus_fish`; hidden by default).
- `peter`: the Miracles extras `cloth1`, `bucket` (bone kept, no mesh, as in The King Who Serves).
- `john`: `sash1` (from `hips`), as in The King Who Serves.
- `thomas`: `cloak1` (from `chest`).
- `mary`, `joanna`: `veil1` (from `head`, the veil's back), `sash1` (from `hips`, the hanging sash ends); prop `jar`
  (child of `handL`, mesh `<who>_jar`; hidden by default).
- `angel`: `sash1` (from `hips`); wings `wingL1 wingL2 wingR1 wingR2` (`wing*1` from `chest`, `wing*2` from `wing*1`:
  the inner and the outer half; the outer half folds behind the inner one). Folded half-open at rest (sheet pose).

Props are rigid meshes parented to their bone; the director shows / hides them by `prop` events (`"jesus/fish"`): the
node name after the slash is the bone name **and** the mesh object (`jesus_fish` under bone `fish`). Hidden props take
their colour from a printed region (C7): `jesus/fish` → the set's `fishPlate` region (the fish on the plate is printed);
`mary/jar`, `joanna/jar` → the set's `waterJar` region (terracotta). Say the anchors in `RIG.md`.

Faces: decals on UV1, one PNG per expression in `docs/risen/design/faces/<char>_<expr>.png` (lists in DESIGN §1).
Jesus's and Peter's existing drawings are copied from `docs/miracles/design/faces/` (and Peter's `puzzled`, John's
group drawings from `docs/lastsupper/design/faces/`); do not redraw them. New drawings only: `jesus_joy`,
`jesus_chew`, `peter_sad`, `peter_puff`, the disciples' group `sad`, `shock`, `doubt`, `awe` (re-coloured brows per
person), all of Mary's and the angel's. Joanna shares Mary's drawings, re-coloured.

## 4. Clips (names are the contract) — actions `<char>_<clip>`

"hold" = one-shot ending in a held pose. "seated" clips keep meshMinY ≥ −0.008 at base y 0 **and** at base y UPPER
(0.10, the room floor). "travel" = a locomotion clip whose naturalSpeed goes in `clips.json`. Every clip below is used
in `story.py` except Mary's and John's `talk` (spares for staging) (count: jesus 10, mary 15, angel 6, peter 12, john 11,
thomas 6, joanna 8).

| jesus (10) | what |
|---|---|
| `idle` (loop) | standing, relaxed, breathing, blink (reuse Miracles if the rig is the same) |
| `talk` (loop) | open-handed, warm gestures (Miracles) |
| `walk` (loop, travel) | calm walk (Miracles) |
| `wave` (loop) | friendly wave (Miracles) |
| `appear` (one-shot hold, 1.5 s) | as He appears (the timeline pops Him in, grow 0.6): arms open slowly from the sides to a welcoming half-open pose, a small nod, face `joy` |
| `call_name` (one-shot hold) | a soft step toward her, one hand a little out, head tilted, face `gentle` ("Mary.") |
| `hold_hands` (loop, pair) | holds both of Mary's hands at chest height, 0.11 apart (A1), a small happy sway; face `joy` |
| `peace` (loop) | both hands raised to shoulder height, palms out, a warm greeting, slow look round the room |
| `show_hands` (loop) | both hands held out in front, palms up, at chest height, turning them slowly; a smile (the hands are drawn as always: no marks) |
| `eat_fish` (one-shot hold, 4.0 s) | (beside the table, facing it) takes the fish from the plate (prop shown at 0.6 s; the timeline hides the set's `fishOnPlate`), turns half to the viewer, takes a bite (marker `bite` at 1.6 s), chews happily (face `chew`), a laugh |

| mary (15) | what |
|---|---|
| `idle` `walk` (travel) `talk` | standing clips (Ruth-like) |
| `idle_jar` (loop) / `walk_jar` (loop, travel) | the same, the left hand holding the jar at the hip |
| `sad` (loop) | head bowed, hands folded, a slow breath (S01) |
| `gasp` (one-shot hold) | a step back, both hands to the mouth (the jar stays in the left), eyes round; ends looking up at the angel |
| `peek` (one-shot hold) | leans forward at a doorway 0.08 in front, one hand on the rock edge, looks in |
| `run` (loop, travel) | a light, joyful run, the veil bouncing |
| `tell` (loop) | excited talk, hands moving, little bounces on the toes |
| `cry` (loop) | head down, hands near the cheeks wiping tears, shoulders shaking softly; **the hands never cover the eyes for more than 0.5 s** (A5) |
| `talk_down` (loop) | speaks without looking up, head down and a little aside, one hand wiping a cheek |
| `turn_joy` (one-shot hold, 1.2 s) | looks up, knows Him: both hands fly to the cheeks, a gasp, then a big smile (face `joy`) |
| `hold_hands` (loop, pair) | the partner of Jesus's `hold_hands` at 0.11 |
| `cheer` (loop) | jumps a little, hands up, laughing |

| angel (6) — **seated only**: base y ANGEL_Y (0.311) puts the seat (rig-local 0.069) on the stone top (0.38), the `ride` method; every act `face="viewer"` (yaw 0) | what |
|---|---|
| `idle` (loop) | standing, wings folded (only for the parked pose and the cover; not seen in the play) |
| `sit_stone` (loop, seated) | sits on the round stone, legs dangling and swinging a little, hands on the stone's top edge, wings half-open breathing slowly; face `smile` |
| `wings_open` (one-shot, 1.6 s, seated) | from `sit_stone`: the wings spread wide (marker `open` at 0.5 s) and settle back to half-open; arms open; face `joy` |
| `sit_talk` (loop, seated) | leans a little toward the women, one hand open, warm talk |
| `sit_point` (one-shot hold, seated) | turns and points to the tomb door with a whole open arm ("come and see"), looks back at the women |
| `sit_wave` (loop, seated) | a big cheerful wave goodbye |

| peter (12) | what |
|---|---|
| `idle` `talk` `walk` `laugh` `amazed` `shock` | as in Miracles (reuse; `shock`, `amazed` standing) |
| `sit_sad` (loop, seated) | on the back bench (seat UPPER + 0.04), elbows on knees, head down |
| `jump_up` (one-shot, 0.9 s, from `sit_sad`) | jumps to his feet, ends standing (A4: this is how he gets off the bench) |
| `run_puff` (loop, travel) | a heavy, flat-footed run, arms pumping, cheeks puffed; slower than John's `run` (planned 0.17 / s) |
| `puff` (loop) | bent over, hands on his knees, catching his breath |
| `stoop_look` (one-shot hold) | ducks his head and shoulders into the doorway 0.08 in front (door top 0.34 < his height 0.38), looks round inside, then turns his head back out to John |
| `cheer` (loop) | both arms up, laughing (The King Who Serves `cheer` without the palm) |

| john (11) | what |
|---|---|
| `idle` `talk` `laugh` `amazed` | The King Who Serves' disciple clips (reuse the motion; re-bake on this rig if needed) |
| `sit_sad` (loop, seated) / `jump_up` (one-shot) | as Peter's |
| `run` (loop, travel) | a light, fast run (planned 0.24 / s), arms swinging |
| `wave_hurry` (loop) | jogging on the spot, beckoning with both arms ("come on!") |
| `peek` (one-shot hold) | as Mary's `peek`, a hand on the rock edge |
| `shock` (one-shot hold) | jumps back, hands up, knees knocking (comic, "a g-g-ghost?") |
| `cheer` (loop) | both arms up |

| thomas (6) | what |
|---|---|
| `idle` (loop) | standing |
| `doubt` (loop) | arms crossed, shakes his head slowly, looks away (face `doubt`) |
| `shock` (one-shot hold) | a step back, arms uncrossed, eyes wide |
| `reach` (one-shot hold, pair) | steps closer, gently touches Jesus's held-out hands with his fingertips, 0.11 from Him (A1) |
| `kneel_worship` (one-shot hold, ends kneeling) | sinks to both knees, hands to his chest, looks up at Jesus (face `awe`); meshMinY ≥ −0.008 at base y UPPER |
| `cheer` (loop) | arms up |

| joanna (8) | what |
|---|---|
| `idle` `walk` `idle_jar` `walk_jar` `sad` `gasp` `peek` `run` | Mary's clips on Joanna's body (one shared function set, small variation) |

Rules: loops seamless; one-shots end in poses the next clip can blend from in 0.25 s; talk clips move `jaw`; secondary
motion on mantle, veils, sashes, cloak, the angel's wings; planted feet do not slide; `clips.json` states each travel
clip's speed. **Pairs probed at their distance**: Jesus / Mary `hold_hands` at 0.11 (y 0); Jesus `show_hands` /
Thomas `reach` at 0.11 (y UPPER). **The angel on the stone** is probed with `garden.glb`: the hips touch the stone top
(0.38) at base y ANGEL_Y (0.311), the legs hang in front of the stone's face (not inside it), the wings clear the rock face
behind.

## 5. Timeline

`python3 tools/story/build_timeline.py risen` from `storyboard/story.py`, timed by
`assets/risen/audio/voice/durations.json` (an estimate until the voices exist: 233 s on 2026-11-18). Actors in the
upstairs room use `y=UPPER` (0.10); the angel uses `y=ANGEL_Y` (0.311) and always faces the viewer (turning it on the stone puts its legs through the stone). Actors not in a scene are parked at `PARK`
(0.80, 0.30) and hidden (`hide()`). Jesus appears and leaves by `prop("jesus", ...)` with `grow` under `angel_light`
(`appear()`). Cameras never target `all`. Changes of place are snaps on shot cuts. Multi-leg moves use `path()` with
the planned speeds `V_WALK V_RUN V_PUFF V_JOY`; after Animation the lead replaces them with the clips.json values.

## 6. Set (`assets/risen/model/garden.glb`, root node `garden`)

Floor x ±0.60, z −0.5875…0.21. Node names are the contract.

| Node | Where / what |
|---|---|
| `tombHill` | reddish-tan rock hill, x −0.60…−0.04, z −0.5875…−0.30, top ≤ 0.42 (rounded, bushes and ivy on top); its front face at z ≈ −0.30 |
| `tombDoor` | the door opening in the front face: x −0.395…−0.265 (centre −0.33), y 0…0.34, rounded top; a dark interior material; FX anchor at the door centre (−0.33, 0.15, −0.30) |
| `cloths` | inside the chamber (x −0.42…−0.24, z −0.48…−0.32, ceiling 0.36): a stone ledge on the left with folded white linen, visible through the door |
| `tombStone` | round stone, a disc **0.39 across** (r 0.195 at mid-thickness), 0.05 thick, standing on its edge in the groove in front of the door: centre (−0.33, 0.19, −0.285), x −0.525…−0.135, top 0.38; **covers the whole door** (lead-approved change 2026-11-18, was 0.22 across) |
| `tombStoneAside` | the same stone rolled right off the door and turned 40° back into an alcove in the rock (its left end at (−0.262, −0.285), just clear of the door): centre (−0.1126, 0.19, −0.4103), **top 0.38** (the angel's seat; a flat spot ≥ 0.06 wide on top); **hidden at start** (lead-approved change 2026-11-18: a 0.39 stone rolled straight along the groove would hit the stair and the house) |
| `groove` | the shallow track in front of the face, x −0.54…−0.05, z −0.31…−0.26, h ≤ 0.01 |
| `flowers` | flower beds: the front-left corner x −0.60…−0.30, z 0.04…0.20 and the hill foot x −0.60…−0.46, z −0.29…−0.20; blooms top ≤ 0.04 |
| `gardenTools` | a spade and a watering jar leaning on the rock at (−0.575, −0.25) (moved from (−0.52, −0.27) with the bigger stone), top ≤ 0.16 |
| `gardenWall` | low stone wall along x −0.04 from z −0.28 to 0.21, h ≤ 0.03, with the gap `gate` at z 0.00…0.12 |
| `olive1` `olive2` | `olive1` behind the hill's right shoulder at (0.00, −0.565) (moved back from −0.50 behind the rolled stone) (crown underside ≥ 0.22); `olive2` at the far left edge (−0.57, −0.05) (trunk r ≤ 0.02, crown underside ≥ 0.20, crown only beyond x −0.50) |
| `path` | pale earth from the house's ground-floor door (0.30, −0.22) down to (0.22, 0.08), left along the front (z 0.04…0.14) to the gate, then on (narrower) to the front of the tomb (−0.33, −0.20) |
| `house` | two storeys at the right back. Ground storey closed, x 0.06…0.60, z −0.5875…−0.22, h 0.10 (a door at x 0.30, a window). **Upstairs room**: floor y UPPER = 0.10, interior x 0.08…0.58, z −0.58…−0.22; walls 0.02 thick; back wall to y 0.46; **front cut away** to a sill ≤ UPPER + 0.04; flat roof edge only at the back and sides |
| `stair` | outside stair up the house's left wall (x 0.02…0.06) to `roomDoor` (decor; nobody walks it) |
| `roomDoor` | closed wooden door with a bar across it, in the room's left wall at z −0.34…−0.26 |
| `bench` | along the room's back wall, x 0.14…0.50, z −0.56…−0.51, seat y UPPER + 0.04, cushions |
| `lowTable` | x 0.46…0.56, z −0.36…−0.26, top y UPPER + 0.05; on it `fishPlate` (a clay plate at (0.50, −0.31)) with `fishOnPlate` (two grilled fish; hidden when Jesus takes one), a bread basket |
| `waterJar` | a big terracotta jar in the back-left corner of the room at (0.12, −0.53), top UPPER + 0.12 |
| `lamp1` `lamp2` | oil lamps: `lamp1` in a back-wall niche at (0.32, −0.575), y UPPER + 0.22; `lamp2` on the table at (0.53, −0.33) |
| `cityWall` | a stretch of Jerusalem's wall with a small gate, a low relief along the back edge behind the house (front face z ≈ −0.585, h ≤ 0.20 above the house's back wall line) |
| `hills` | low olive-green hills along the back edge behind the tomb (front face z ≈ −0.585) |

**Marks that must stay clear** (nothing above the actor's base + 0.012 within 0.05; nothing on the straight path between
consecutive marks of one actor; print `CLEARANCE`):
- garden (y 0): the women `MARY_T` (−0.30, −0.13), `JOANNA_T` (−0.42, −0.12), `NEAR_TOMB` (−0.26, −0.10),
  `MARY_DOOR` (−0.30, −0.22), `JOANNA_DOOR` (−0.40, −0.21), `TOMB_DOOR` (−0.33, −0.24) (only the groove, h ≤ 0.01,
  within 0.05; the door is what they look into), John (−0.40, −0.22), Peter (−0.22, −0.14), `MARY_CRY` (−0.24, −0.05),
  `JESUS_G` (−0.10, −0.12), `MARY_MEET` (−0.205, −0.075), S01 (−0.10, 0.02), (−0.18, 0.06); S12 (−0.12, −0.04),
  (−0.24, 0.02). The angel's seat `STONE_ASIDE` (−0.1126, −0.4103), seat top 0.38, `ANGEL_Y` = 0.311 (the clips'
  seat is rig-local 0.069 above the base; ANIMATION.md §2; lead 2026-11-18): nothing above 0.38 within 0.08
  except the rock behind it.
- path (y 0): `WOMEN_START` (0.36, 0.10), (0.44, 0.12) → `PATH_R` (0.22, 0.08) / (0.30, 0.11) → `PATH_L` (0.04, 0.08)
  / (0.06, 0.11) → `GATE` (−0.06, 0.06) → `NEAR_TOMB` / `JOANNA_T`; the race `HOUSE_DOOR` (0.30, −0.15) and
  `PETER_DOOR` (0.38, −0.13) → `PATH_R` → `PATH_L` → `GATE` → `TOMB_DOOR` / (−0.22, −0.14); Mary's run-off
  `MARY_MEET` → (−0.10, 0.04) → `PATH_L` → (0.30, 0.10); S12 (0.04, 0.04), (0.14, 0.08), (0.06, −0.10).
- room (y UPPER): `ROOM_DOOR` (0.12, −0.30), `MARY_ROOM` (0.14, −0.33), `BENCH` seats (0.20 / 0.30 / 0.40, −0.49) (the
  bench itself is the seat), `STAND` (0.20, −0.45), (0.40, −0.45), `ROOM_J` (0.30, −0.30), `TABLE_J` (0.41, −0.30)
  (the table's near edge 0.05 away is what He reaches for), `THOMAS_TOUCH` (0.19, −0.30).

Budget: set ≤ 70k triangles. UV0 = the colouring sheet, exactly as The King Who Serves' set (front / plan
projections, upward faces take a clean texel from their own region). The room interior seen through the open front
needs its own sheet regions (inside wall, bench cushions, table, fish plate, water jar) or a plain colour from the house
stone region (L51). The tomb interior (`cloths`, chamber walls) takes plain colours (rock dark, linen white).

## 7. Audio

Voice −16 LUFS, music −20 LUFS, SFX peak −3 dBFS, 44.1 kHz mono WAV + 96 kbps MP3.

- **Voices** (`cast_risen.json`): `narrator` = the family storyteller (Qwen `vivian` zh, same as every pack);
  `jesus` and `peter` = **the same voice settings as `cast_miracles.json`**; `john` = **the same as
  `cast_lastsupper.json`**; `mary`, `angel`, `thomas`, `joanna` new, chosen by audition (Mary young and warm; Joanna
  older and brisker, clearly a different woman; the angel strong, kind, calm, never booming or echoing; Thomas a steady
  baritone, clearly not Peter). **English and Chinese: Qwen3-TTS only (Apache-2.0). Do not use `edge-tts`** (R7).
  Interjections stay inside phrases with words (哈哈，是我呀 / 鬼……鬼啊), as The King Who Serves VOICE.md.
  Names to check in the transcript (V3): 耶稣, 马利亚, 约亚拿, 彼得, 约翰, 多马, 天使.
- **Music cues**: `sad_day dawn stone risen news race empty garden_tears mary peace thomas finale` (+ `cues.json`
  loops).
- **SFX** (all one-shots, sized to their scene: StoryDirector stops loops only at a music cue): `birds_dawn` (≤ 12 s,
  fades out), `rumble` (1.2 s, soft and low, never a crash), `stone_roll` (1.0 s, a heavy stone grinding then a soft
  thud), `appear_chime` (1.5 s, a warm shimmer), `run_steps` (≤ 7 s, two runners' footsteps, the second heavier),
  `munch` (0.6 s, a comic crunchy bite), `sparkle_up` (1.2 s) (+ `mix.json`).

## 8. Effects

Already in the app (use as is): `tension_dim` (Esther), `dawn_glow` `angel_light` (Daniel), `golden_rays`
`dust_burst` (D&G), `sunset_glow` `lamp_flame` `heart_glow` (Ruth), `run_dust` (Prodigal).
New, in `StoryFxRisen.cs`, class `RisenFx` (the FX role adds `"class": "RisenFx"` to the manifest in the same change
that adds the file) (2 ids, nothing else; if an existing effect already looks right, alias it in the manifest instead
and say so in `FX.md`, F1):
- `tomb_glow` (node): a soft warm-white light from inside the open tomb door: a glow filling the opening, a gentle pool
  on the ground in front of it, slow golden motes drifting out, for `dur`; never bright enough to hide the folded
  cloths or the faces of people peeking in (F4: check against the dark door and the reddish rock).
- `butterflies` (node): 6-8 butterflies in the flower colours (white, red, yellow) and one blue rise from the node's
  area, flutter in loops at 0.05-0.30 above the ground, a few settle on blooms, all fade by the end of `dur`; joyful,
  never a swarm, never in front of a face for more than a moment.

## 9. Manifest (lead writes the registry at Integration)

Strings: `dg_jesus` 耶稣 / Jesus, `dg_peter` 彼得 / Peter, `dg_john` 约翰 / John (same values as the Miracles and The
King Who Serves manifests), `dg_risen_mary` 马利亚 / Mary (per-story: other packs may have another Mary, I4),
`dg_risen_angel` 天使 / The angel, `dg_thomas` 多马 / Thomas, `dg_joanna` 约亚拿 / Joanna. Library: pinyin
`tā fù huó le`, minutes 4, `"after": "lastsupper"`. Registry (Integration only): cast as `story.py` `CAST`, `paint`
`extras_paint.png` for `peter john thomas joanna`, set `garden`, sheets `risen-A4`, `risen-A4-demo`.
