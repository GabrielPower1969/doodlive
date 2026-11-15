# Joseph — production contract

Binding for every role. Story and lines: `STORY.md` + `storyboard/story.py`. Look: `DESIGN.md`. How to run each
step: `docs/pack-plans/01-LIFECYCLE.md`. Shared rules: `docs/pack-plans/03-RULES.md`. Kit: `docs/STORY-KIT.md`.
Template pack to copy from: **Ruth** (`pipeline/ru_*.py`, already on the kit; Ruth's hood, open robe, stooped rest
pose and hidden props are exactly what this pack needs).

Ids: story `joseph`, script prefix `js`, env prefix `JS_`, page material `js_page`, set `twolands`.

## 1. Files and owners

| Role | Owns |
|---|---|
| Lead (story + integration) | `docs/joseph/*`, `assets/joseph/timeline.json` (generated), `assets/joseph/manifest.json`, `assets/joseph/{pack,faces}.json`, Unity, builds, device |
| Characters | `pipeline/js_characters.py`, `assets/joseph/model/{joseph,jacob,brother,pharaoh}.glb`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/joseph/RIG.md`, `docs/joseph/design/faces/` |
| Set + sheet | `pipeline/js_twolands.py`, `assets/joseph/model/twolands.{glb,blend}`, `twolands_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_joseph.py` (only if `make_sheet.py` cannot do it as is), `assets/joseph/sheet/`, `print/joseph-A4.{png,pdf}`, `print/joseph-A4-colored.pdf`, `assets/joseph/design.json`, `docs/joseph/SET.md` |
| Animation | `pipeline/js_animate.py`, `assets/joseph/anim/`, `docs/joseph/ANIMATION.md` |
| Voice | `tools/story/cast_joseph.json`, `assets/joseph/audio/voice/`, `docs/joseph/VOICE.md` |
| Music + SFX | `tools/story/music_joseph.py`, `assets/joseph/audio/music/`, `assets/joseph/audio/sfx/`, `docs/joseph/MUSIC.md` |
| FX | `manifest.json` `fx.aliases` first; `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxJoseph.cs` only for the 1 new id in §8; `docs/joseph/FX.md` |

Nobody edits `assets/stories.json`, `assets/library.json`, `tools/i18n/strings.json` or `DGFxEffects.cs` by hand:
they are generated from the manifests by `tools/story/merge_packs.py`.

## 2. Cast

Units: art-width units (1.0 = art rectangle width), Y up, page = XZ plane at y = 0, +Z toward the viewer, +X right.

| Id | Height | Sheet slot (start value; Set + sheet owns the final one in `design.json`) |
|---|---|---|
| `joseph` | 0.34 | sheetX −0.34, sheetY 0.015 — **printed wearing the coat** |
| `brother` | 0.38 | sheetX 0.0, sheetY 0.015 |
| `pharaoh` | 0.40 (0.45 with the crown) | sheetX 0.34, sheetY 0.015 |
| `jacob` | 0.33 stooped | second row, sheetX −0.34, sheetY 0.44 |

Four A-pose figures do not fit in one row (Daniel's lesson: three at ±0.34 is the limit), so Jacob goes on a second
row and the set drawings use the top-centre and top-right. Budget: each human ≤ 25k triangles, ≤ 4 bone influences.

## 3. Skeletons

All four are the kit's contract humanoid, A-pose, facing +Z:
`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids`. Extras:

- `joseph`: `coatL coatR` (front panels of the open coat, from `chest`) and three prop bones:
  `coat` (child of `chest`; mesh `joseph_coat`, **shown by default and printed on the sheet**; skinned to the body
  bones and `coatL/R`, shown / hidden as one prop), `nemes` (child of `head`; mesh `joseph_nemes`, hidden by
  default), `collar` (child of `chest`; mesh `joseph_collar`, hidden by default).
  Hidden props take their UV0 from the coat's printed regions (`PROP_ANCHORS`): `nemes` stripes alternate
  `coat2` / `coat4`, `collar` rings use `coat1`, `coat3`, `coat5`.
- `jacob`: `shawl1 shawl2` (back drape, from `head`), `stick` (child of `handR`; always shown). Stooped rest pose
  baked into mesh and bones (Ruth's Naomi: `bake_rest_pose`).
- `brother`: `bag` (sling bag, from `chest`, a small swing).
- `pharaoh`: `apron1` (front apron, from `hips`), `belly` (jiggle, from `spine`; Daniel's king precedent).

Faces: decals on UV1, one PNG per expression in `docs/joseph/design/faces/<char>_<expr>.png` (lists in DESIGN §1).
Eyelids on the eye surface.

## 4. Clips (names are the contract) — actions `<char>_<clip>`

"hold" = one-shot ending in a held pose.

| joseph (19) | what |
|---|---|
| `idle` (loop) | light on his feet, looking around, smiling |
| `talk` (loop) | generic |
| `walk` (loop), `run` (loop) | plain walk; eager run with arms out |
| `walk_sad` (loop) | slow, head down, wrists together in front |
| `twirl` (one-shot) | spins once showing the coat, arms out, ends facing front |
| `tell_dream` (loop) | acts it out: ties a bundle, then mimes things bowing with both hands |
| `in_pit` (one-shot hold) | stumbles back, sits down inside the well, then reaches up with one arm |
| `carry_work` (loop) | walks in place carrying a jar on the shoulder (the jar is part of the clip's hands-only pose; no prop) |
| `sit_cell` (one-shot hold) | sits on the bench, elbows on knees, then looks up |
| `bow_point_up` (one-shot hold) | bows, then lifts one hand to point to heaven |
| `explain` (loop) | counts on his fingers, open palms |
| `stand_proud` (one-shot hold) | straightens, touches the collar, looks out |
| `recognise` (one-shot hold) | small start, hand to the chest, turns half away to hide his face |
| `ask_gently` (loop) | hands clasped, leaning in |
| `reveal` (one-shot hold) | both hands lift the head-cloth off (marker `off` when it leaves the head), arms open |
| `lift_up` (one-shot) | bends, takes someone 0.11 in front by the arms and raises them |
| `hug` (loop) | arms round someone 0.11 in front |
| `wave` (loop) | big happy wave |

| jacob (6) | what |
|---|---|
| `idle` (loop) | both hands on the stick, gentle sway |
| `talk` (loop) | one hand gesturing, the other on the stick |
| `give_coat` (one-shot hold) | holds both arms out as if offering cloth, then pats a shoulder 0.12 in front |
| `weep` (loop) | face in one hand, shoulders shaking |
| `walk_old` (loop) | slow, the stick plants every other step |
| `hug` (loop) | one arm round someone 0.11 in front, the stick still in the other hand |

| brother (13) | what |
|---|---|
| `idle` (loop), `talk` (loop), `walk` (loop) | generic; heavy, sure of himself |
| `fold_arms` (one-shot hold) | folds arms, looks away |
| `grumble` (loop) | mutters, kicks a pebble |
| `angry_point` (one-shot hold) | jabs a finger at someone, leans in |
| `grab_coat` (one-shot) | grabs at shoulder height 0.11 in front and yanks back (marker `off`) |
| `take_coins` (one-shot hold) | holds out a palm, closes the fist, glances sideways |
| `bow_low` (one-shot hold) | kneels and bows with the forehead near the ground (knees on the page) |
| `fall_back_scared` (one-shot hold) | from the bow: jerks up, falls back onto his hands |
| `stand_up` (one-shot) | from the ground to standing, helped |
| `hug` (loop) | arms round someone 0.11 in front, head on the shoulder |
| `wave` (loop) | awkward, shy wave |

| pharaoh (8) | what |
|---|---|
| `idle` (loop) | hands on hips, chin up |
| `talk` (loop) | grand gestures |
| `doze` (loop) | standing, head nodding lower and lower, jerks up, repeats |
| `wake_jump` (one-shot hold) | jumps, arms up, belly bounces |
| `lean_ask` (one-shot hold) | leans forward, one hand out |
| `delighted` (loop) | claps, bounces |
| `crown_him` (one-shot hold) | takes something from his own neck and places it at head height 0.12 in front (marker `on`) |
| `wave` (loop) | regal wave |

Rules: loops seamless; one-shots end in poses the next clip can blend from in 0.25 s; talk clips move `jaw`;
secondary motion on the coat panels, shawl, bag, apron, belly; planted feet do not slide; `clips.json` states each
travel clip's speed; two-person clips assume the partner **0.11** away (story.py marks are set for that).

## 5. Timeline

`python3 tools/story/build_timeline.py joseph` from `storyboard/story.py`, timed by
`assets/joseph/audio/voice/durations.json`. An actor not in a scene is parked off the page (`PARK` / `PARK_L`).

## 6. Set (`assets/joseph/model/twolands.glb`, root node `twolands`)

Floor x ±0.60, z −0.5875…0.21. Node names are the contract.

| Node | Where / what |
|---|---|
| `ground` | left half green-ochre pasture, right half pale sand, a dune strip between x −0.06 and 0.04 with a road |
| `horizon` | backdrop relief across the back (front face z ≈ −0.56, top ≤ 0.28): hills on the left, small pyramids on the right |
| `tent` | centre (−0.44, −0.42), footprint 0.26 × 0.18, ridge h ≤ 0.24, open toward +Z |
| `sheep` | three, around (−0.20, −0.36); optional looping action `sheepNod` |
| `olive` | tree at (−0.56, −0.06), crown bottom ≥ 0.20 |
| `pit` | dry well ring centre (−0.34, 0.08), inner radius 0.07, wall 0.02 thick, top h 0.08; rope and bucket outside at (−0.46, 0.12) |
| `caravan` | camel + trader at (−0.52, 0.17), facing −X; hidden until S03 |
| `palace` | centre (0.38, −0.46), footprint 0.34 × 0.20: dais 4 steps (top h 0.05, front edge z ≈ −0.36), two columns, lintel with sun-disc, `throne`, fans, fire bowl |
| `granary` | three stores around (0.50, −0.04), each radius 0.05, h 0.16; ladder |
| `grainPiles` | heaps and baskets around (0.40, −0.06) and between the stores; hidden until S07 |
| `sacks` | three sacks at (0.28, 0.16); hidden until S09 |
| `cell` | cage of bars, 0.16 square, centre (0.10, −0.06), h 0.20, open top, bench inside; hidden except S04-S06 |
| `palms` | two date palms at (0.58, −0.26) and (0.14, −0.44), crown bottom ≥ 0.28 |
| `dreamSheaves` | cloud panel centre (−0.32, h 0.46, z −0.16), 0.22 wide; hidden |
| `dreamStars` | same place as `dreamSheaves`; hidden |
| `dreamSheaves2` | copy of `dreamSheaves` at (0.30, h 0.50, z 0.06); hidden |
| `dreamCows`, `dreamGrain` | cloud panels centre (0.30, h 0.52, z −0.26), 0.24 wide; hidden |

Dream panels are flat double-sided reliefs that face +Z, tilted 15° toward the camera, so they read from the phone.

**Marks that must stay clear** (nothing above 0.012 within 0.05; nothing on the straight path between consecutive
marks of one actor; print `CLEARANCE`):
- jacob: (−0.46, −0.20) → (−0.10, 0.12); parked at x −0.80.
- joseph: (−0.32, −0.16) → (−0.26, 0.04) → (−0.34, 0.08) [inside the well: the wall is allowed] → exit x −0.80;
  (0.16, 0.06) → (0.10, −0.06) [inside the cell] → (0.22, −0.20) → (0.42, 0.04) → (0.34, 0.08) → (0.02, 0.12).
- brother: (−0.16, −0.12) → (−0.20, 0.06); (−0.16, −0.12) → (0.22, 0.13) → (0.16, 0.14).
- pharaoh: (0.38, −0.30) only.
The cell and the well are walked into "through the wall": the director moves actors in straight lines, so make the
cell's bars and the well's rim low enough to read as stepped over (cell: leave the +Z side open; well: h 0.08).

Budget: set ≤ 60k triangles. UV0 = the colouring sheet, exactly as Ruth's set.

## 7. Audio

Voice −16 LUFS, music −20 LUFS, SFX peak −3 dBFS, 44.1 kHz mono WAV + 96 kbps MP3.

- **Voices** (`cast_joseph.json`): `narrator` = the family storyteller (Qwen `vivian` zh); `joseph`, `jacob`,
  `brother`, `pharaoh` new, chosen by audition. Jacob must sound clearly older than everyone; Pharaoh must not be
  the voice of Exodus' Pharaoh's exact take if that sounds harsh (he is comic and generous here): audition both.
  **English: Qwen3-TTS only (Apache-2.0). Do not use `edge-tts`** (`docs/pack-plans/03-RULES.md` R7).
- **Music cues**: `home dream betrayal prison pharaoh reveal plenty famine brothers iam reunion finale`
  (+ `cues.json` loop points).
- **SFX**: `sheep_baa sparkle harp_gliss camel_grunt coins cell_door moo fanfare wind_desert soft_chime`
  (+ `mix.json`). `harp_gliss` is the dream motif's glissando; keep it identical every time.

## 8. Effects

Already in the app (use as is): `sparkle` `steam` `tension_dim` `coins_spray` `prayer_glow` `night` `zzz`
`golden_rays` `famine_haze` `sweat` `heart_glow` `confetti`.
New, in `StoryFxJoseph.cs` (1 id, nothing else):
- `dream_cloud` (node): a soft ring of slowly turning cloud puffs around the node (radius from the node's bounds),
  a few twinkling stars, a gentle bob; fades in 0.8 s, out 0.8 s. It frames a dream panel; it never covers it.

## 9. Manifest (lead writes it at Integration)

Strings: `dg_joseph` 约瑟 / Joseph, `dg_jacob` 雅各 / Jacob, `dg_brother` 哥哥 / Brother. `dg_pharaoh` exists
(Exodus) and fits. Library: pinyin `yuē sè de mèng`, minutes 4, `"after": "jonah"` (or `"daniel"` if Jonah is not
in yet).
