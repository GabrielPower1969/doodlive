# Real Miracles — production contract

Binding for every role. Story and lines: `STORY.md` + `storyboard/story.py`. Look: `DESIGN.md`. How to run each
step: `docs/pack-plans/01-LIFECYCLE.md`. Shared rules: `docs/pack-plans/03-RULES.md`. Kit: `docs/STORY-KIT.md`.
Template packs to copy from: **Jonah** (`pipeline/jn_*.py`, newest, on the kit: deck height, hidden actors, storm)
and **Ruth** (`pipeline/ru_*.py`). Fixed-paint extras: Esther's guards (`pipeline/es_characters.py`, `GUARDS`).

Ids: story `miracles`, script prefix `mi`, env prefix `MI_`, page material `mi_page`, set `galilee`.

## 1. Files and owners

| Role | Owns |
|---|---|
| Lead (story + integration) | `docs/miracles/*` (except the role docs below), `assets/miracles/timeline.json` (generated), `assets/miracles/manifest.json`, `assets/miracles/{pack,faces}.json`, Unity, builds, device |
| Characters | `pipeline/mi_characters.py`, `assets/miracles/model/{jesus,peter,man,friend1,friend2,friend3,friend4}.glb`, `friend_paint.png`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/miracles/RIG.md`, `docs/miracles/design/faces/` |
| Set + sheet | `pipeline/mi_galilee.py`, `assets/miracles/model/galilee.{glb,blend}`, `galilee_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_miracles.py` (only if `make_sheet.py` cannot do it as is), `assets/miracles/sheet/`, `print/miracles-A4.{png,pdf}`, `print/miracles-A4-colored.pdf`, `assets/miracles/design.json`, `docs/miracles/SET.md` |
| Animation | `pipeline/mi_animate.py`, `assets/miracles/anim/`, `docs/miracles/ANIMATION.md` |
| Voice | `tools/story/cast_miracles.json`, `assets/miracles/audio/voice/`, `docs/miracles/VOICE.md` |
| Music + SFX | `tools/story/music_miracles.py`, `assets/miracles/audio/music/`, `assets/miracles/audio/sfx/`, `docs/miracles/MUSIC.md` |
| FX | `manifest.json` `fx.aliases` first; `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxMiracles.cs` only for the new ids in §8; `docs/miracles/FX.md` |

Nobody edits `assets/stories.json`, `assets/library.json`, `tools/i18n/strings.json` or `DGFxEffects.cs` by hand.

## 2. Cast

Units: art-width units (1.0 = art rectangle width), Y up, page = XZ plane at y = 0, +Z toward the viewer, +X right.

| Id | Height | Sheet slot (start value; Set + sheet owns the final one in `design.json`) | Paint |
|---|---|---|---|
| `man` | 0.34 | sheetX −0.32, sheetY 0.015 (drawn standing, the mat as a separate shape beside / below him) | scanned |
| `jesus` | 0.36 | sheetX 0.0, sheetY 0.015 | scanned |
| `peter` | 0.38 | sheetX 0.32, sheetY 0.015 | scanned |
| `friend1`…`friend4` | 0.35 / 0.37 / 0.33 / 0.36 | not on the sheet: fixed paint `model/friend_paint.png` (Esther `GUARDS` method) | fixed |

Budget: each human ≤ 25k triangles (friends ≤ 18k), ≤ 4 bone influences. The man's `mat` prop counts in his budget.

## 3. Skeletons

All seven: the kit's contract bones, A-pose, facing +Z:
`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids`. Extras:
- `jesus`: `mantle1` (the mantle's hanging back drape, from `chest`), `belt1` (belt end, from `hips`).
- `peter`: `cloth1` (head-cloth tail, from `head`), `bucket` (prop bone, child of `handR`; mesh `peter_bucket`, hidden).
- `man`: `mat` (prop bone, child of `root`; mesh `man_mat` incl. poles; shown), `ropes` (child of `mat`; mesh
  `man_ropes`: four ropes from the mat corners rising 0.45; hidden except during `lowered`, the clip scales it in),
  `matRoll` (prop bone, child of `chest`; mesh `man_matRoll`, hidden), `sash1` (sash end, from `hips`).
- friends: `belt1` (from `hips`); `friend3` `band1` (head-band tail, from `head`).

**The mat in the rest pose** lies flat on the page under where the man lies in `lie_mat`: centre (0, 0, −0.02),
long axis along X (0.30 × 0.12, poles to ±0.20), top at y 0.025. The animator moves the man's body onto it; the mat
bone stays at root in every lying clip.

Faces: decals on UV1, one PNG per expression in `docs/miracles/design/faces/<char>_<expr>.png` (lists in DESIGN §1;
the four friends share one set of expression drawings, re-coloured hair per friend is fine).

## 4. Clips (names are the contract) — actions `<char>_<clip>`

"hold" = one-shot ending in a held pose. "lying" / "seated" / "kneeling" clips keep meshMinY ≥ −0.008.

| jesus (13) | what |
|---|---|
| `idle` (loop) | standing, relaxed, breathing, blink |
| `talk` (loop) | open-handed, warm gestures |
| `walk` (loop) | calm walk; speed in `clips.json` |
| `teach` (loop) | standing, turning to different sides of the room, one hand open, the other on the heart now and then |
| `look_up_smile` (one-shot hold) | dust falls: looks up at the ceiling, a little laugh, smiles |
| `kneel_kind` (one-shot hold) | walks 0 (in place), kneels on one knee, leans toward someone lying 0.12 in front, a hand toward them |
| `stand_talk` (one-shot hold) | rises from the kneel, turns to the room, one hand raised |
| `command_rise` (one-shot hold) | turns to the man, both palms sweep up: "Get up!" |
| `lie_sleep` (loop, lying) | lies on his side on the stern cushion, knees bent, slow breathing; head on the cushion (cushion top y ≈ 0.05 above the deck) |
| `wake_up` (one-shot hold) | from lying: opens eyes, sits up, stands, calm |
| `calm_storm` (one-shot hold) | stands firm, both arms stretched out over the water, palms down; then lowers them slowly (marker `calm` at 1.0 s) |
| `laugh` (one-shot) | a warm laugh, shoulders shaking |
| `wave` (loop) | friendly wave |

| peter (13) | what |
|---|---|
| `idle` (loop) | weight shifts, hands on hips now and then |
| `talk` (loop) | big gestures |
| `walk` (loop) | rolling fisherman's walk; speed in `clips.json` |
| `roof_shock` (one-shot hold) | dust hits him: flinches, looks up, both hands on his head, mouth wide |
| `dust_off` (one-shot hold) | brushes dust out of his hair and beard, shakes his head like a wet dog |
| `laugh` (loop) | big belly laugh, slaps his thigh |
| `steer` (loop) | holds the steering oar (to his right), calm |
| `steer_hard` (loop) | braced legs, heaves the oar left and right, leaning into the wind |
| `bail` (loop) | bends, scoops water with the bucket (prop shown), throws it over the side (to his left), fast and frantic |
| `shake_awake` (loop) | bends and shakes someone lying 0.10 in front, by the shoulder |
| `amazed` (one-shot hold) | slowly straightens, mouth open, hands half raised, looks around at the flat water |
| `cower` (loop) | crouches, hugging the mast / his knees, flinches at thunder |
| `wave` (loop) | big two-arm wave |

| man (12) | what |
|---|---|
| `lie_mat` (loop, lying) | lies on his back on the mat, head a little raised, hands on the chest; breathing, blink; mat flat |
| `carried` (loop, lying) | same lying pose but body and mat lifted as one: in the clip the mat sits at local y 0.05 so with base `CARRY_Y` (0.10) its poles are at y ≈ 0.15, the friends' hand height; a small up-down bob in walking rhythm (0.8 s), head turning to look around |
| `lowered` (one-shot) | 5.0 s: starts with the root at local y +0.40 (the roof), ropes shown and taut going up, the mat swinging ±4°; descends with small stops (ease) to local y 0 at 4.6 s; ropes go slack and hide at 4.8 s (marker `land`) |
| `sit_up` (one-shot hold) | from lying: sits up slowly, stares at his legs, wiggles toes |
| `stand_wobbly` (one-shot hold) | gets up onto wobbly legs like a newborn calf, arms out for balance, two tiny steps in place, then straightens |
| `jump_joy` (one-shot) | leaps up twice, arms high, lands laughing |
| `roll_mat` (one-shot hold) | bends, rolls up the mat (body only: the props switch `mat` → `matRoll` at 1.2 s by timeline events), heaves it onto his left shoulder |
| `dance_mat` (loop) | skipping, spinning dance with the rolled mat on his shoulder; travels: speed in `clips.json` |
| `walk_mat` (loop) | happy walk with the rolled mat |
| `talk` (loop) | lying-free talk, standing |
| `idle` (loop) | standing, holding the rolled mat |
| `wave` (loop) | waving with the free hand, mat on the shoulder |

| friends (each of friend1-4 gets all 12; one shared function set, small per-friend variation) | what |
|---|---|
| `idle` (loop) | standing |
| `walk` (loop) | walk; speed in `clips.json` |
| `carry_front` (loop) | walking, holding the mat's two front pole ends **behind him** at hand height y ≈ 0.15 (hands 0.04 behind the hips, arms back), leaning forward with effort; same speed as `walk` |
| `carry_back` (loop) | walking, holding the two back pole ends **in front of him** at y ≈ 0.15, arms forward; same speed as `walk` |
| `squeeze_bounce` (one-shot hold) | (friend3 only needs it, all may have it) walks 0.06 forward, wiggles shoulders as if squeezing, is bounced back 0.08, sits down hard, gets up (marker `boing` at 1.6 s) |
| `think` (loop) | hand on chin, tapping foot |
| `idea` (one-shot hold) | finger shoots up, jumps a little, big grin |
| `dig` (loop, kneeling) | kneels, pulls up clods with both hands and tosses them aside, fast |
| `lower_rope` (loop, kneeling) | kneels at the edge, paying out a rope hand over hand, leaning over the hole |
| `peek` (loop, kneeling) | kneels, leans far over the hole, looks down, little nods |
| `cheer` (loop) | jumps, arms up, high-fives the air |
| `wave` (loop) | wave |

Rules: loops seamless; one-shots end in poses the next clip can blend from in 0.25 s; talk clips move `jaw`;
secondary motion on mantle, belt ends, head cloth, sash; planted feet do not slide; kneeling clips put knees on the
ground (meshMinY ≥ −0.008) and work at base y ROOF (0.40) as well as 0; `clips.json` states each travel clip's speed.
The carry group (man `carried` + friend1 `carry_front` 0.16 ahead + friend2 `carry_back` 0.16 behind) must line up:
the animator checks it in one probe render with the three actors placed at those offsets.

## 5. Timeline

`python3 tools/story/build_timeline.py miracles` from `storyboard/story.py`, timed by
`assets/miracles/audio/voice/durations.json`. Actors on the roof use `y=ROOF` (0.40), on the boat `y=DECK` (0.06).
Actors not in a scene are parked at `PARK` (0.80, 0.30) and hidden. Cameras never target `all`.
Off-stage group voices: `people` (plate 众人 / The crowd), `friends` (plate 四个朋友 / The four friends).

## 6. Set (`assets/miracles/model/galilee.glb`, root node `galilee`)

Floor x ±0.60, z −0.5875…0.21. Node names are the contract.

| Node | Where / what |
|---|---|
| `house` | room interior x −0.46…−0.04, z −0.56…−0.26, floor y 0; walls 0.03 thick; back wall to y 0.44; **front cut away** to a sill ≤ 0.05; **roof top (walkable) y = 0.40**, slab 0.03 thick (underside 0.37), spans x −0.48…−0.02, z −0.58…−0.26, parapet ≤ 0.03 on the back and sides only (the front roof edge has none, so the friends at the hole are seen); side door in the right wall (x −0.04) centred z −0.40, 0.10 wide, 0.26 high; a window in the back wall; interior props stay at x ≤ −0.42 or z ≤ −0.52 |
| `roofPatch` | the intact roof square over `HOLE` (−0.24, −0.38), 0.14 × 0.14, flush with the roof; shown at start |
| `roofHole` | the same square opened: a ragged hole 0.12 × 0.12 with broken branch ends; hidden at start |
| `rubble` | a flat heap (h ≤ 0.02) of mud and twigs on the floor at (−0.30, −0.44) (beside the landing spot, not on it); hidden |
| `stair` | outside stair against the house's left wall, x −0.58…−0.48, from z −0.06 (y 0) rising evenly to z −0.44 (y 0.40); a landing on the roof's back-left corner. Its treads are the walkable surface (the timeline eases y linearly from the foot to the top) |
| `crowd1`…`crowd8` | fixed-colour townsfolk, height ≤ 0.30, static: four standing in front of the side door at (0.02…0.10, −0.46…−0.32) facing −X (backs to the yard), two sitting inside at (−0.43, −0.54) and (−0.08, −0.54) (back corners), two at the back window outside (z ≤ −0.58, only heads visible) |
| `yard` | packed earth x −0.04…0.20, z −0.50…−0.06; `figTree` at (0.16, −0.50) (trunk r 0.02, crown y ≥ 0.20); `olivePress` at (0.12, −0.22) (r ≤ 0.04, h ≤ 0.06) |
| `road` | pale dirt from (0.30, 0.21) to the yard (0.04, −0.10), and along the front to the stair foot |
| `lake` | x 0.14…0.60, z −0.5875…−0.12, surface y ≈ 0.012; looping `lakeWave` (4 s, seamless); a pebble `beach` strip z −0.12…0.0 with reeds at x ≥ 0.50 |
| `boat` | hull centre (0.36, −0.34), length 0.40 along X (x 0.16…0.56), beam 0.14, **deck top y = 0.06**; mast at (0.26, −0.34), top ≤ 0.42, furled sail; steering oar at the stern; `cushion` at the stern (0.50, −0.34), top y ≈ 0.10; net coil in the bow (x ≤ 0.22); looping `boatRock` (6 s, ±3° roll, seamless) |
| `hills` | far-shore hills, a low relief along the back edge right of the house (front face z ≈ −0.575, top h 0.12-0.20) |

**Marks that must stay clear** (nothing above the actor's base + 0.012 within 0.05; nothing on the straight path
between consecutive marks of one actor; print `CLEARANCE`):
- house floor (y 0): jesus (−0.36, −0.46) and (−0.34, −0.40); peter (−0.12, −0.46); man `LAND` (−0.24, −0.38).
- yard / road (y 0): (0.20, 0.14), (0.10, 0.08), (0.30, 0.20), (0.02, 0.14), (0.10, 0.20), (0.12, −0.04),
  (0.02, −0.10), (0.22, 0.02), (−0.04, 0.00), (0.08, 0.06), `YARD` (0.02, −0.12), (−0.40, −0.06), (−0.53, −0.08),
  (−0.26, −0.06), (−0.30, 0.02), (−0.20, 0.02), (−0.53, 0.0), `MAN_HOME` (−0.10, 0.14), `MAN_END` (−0.14, 0.10).
  Note the walk from the yard to the stair foot passes in front of the house at z ≥ −0.10: the sill must be outside
  that lane (sill front z −0.26).
- stair (y rising): (−0.53, −0.08) → (−0.53, −0.40), (−0.53, −0.24), (−0.53, −0.10), (−0.53, −0.36).
- roof (y 0.40): (−0.40, −0.46), (−0.40, −0.30), `STAIR_TOP` (−0.53, −0.46), (−0.24, −0.30), `R1` (−0.36, −0.38),
  `R2` (−0.12, −0.38), `R3` (−0.32, −0.50), `R4` (−0.16, −0.50). Nothing on the roof above 0.412 except the parapet.
- boat deck (y 0.06): (0.42, −0.34), `BOAT_PETER` (0.28, −0.32), `BOAT_STERN` (0.48, −0.34) (the cushion is the
  sleeper's pillow: only its 0.05 height is allowed there), `BOAT_WAKE` (0.38, −0.32).
- beach (y 0): `BEACH_J` (0.18, 0.04), `BEACH_P` (0.32, 0.06).
- The `lowered` path: a vertical shaft of radius 0.10 round `LAND` from y 0 to 0.45 must be empty except the
  `roofHole` rim.

Budget: set ≤ 70k triangles. UV0 = the colouring sheet, exactly as Jonah's set (front / plan projections, upward faces
take a clean texel from their own region). The interior seen through the open front needs its own sheet regions
(back wall inside, floor mat) or a plain colour from the house wall region (L51).

## 7. Audio

Voice −16 LUFS, music −20 LUFS, SFX peak −3 dBFS, 44.1 kHz mono WAV + 96 kbps MP3.

- **Voices** (`cast_miracles.json`): `narrator` = the family storyteller (Qwen `vivian` zh, same as every pack);
  `jesus`, `peter`, `man`, `friend1`, `friend2`, `friend3` new, chosen by audition; `friends` = the four friend voices
  layered; `people` = a crowd of 8-10 layered voices incl. two children (Jonah's `people` method). **English and
  Chinese: Qwen3-TTS only (Apache-2.0). Do not use `edge-tts`** (R7).
- **Music cues**: `capernaum friends no_way roof lowering heal joy evening storm calm finale` (+ `cues.json` loops).
- **SFX**: `crowd_murmur boing ding dig_loop crumble rope_creak sparkle cheer lake_lap thunder wind_loop wind_stop`
  (+ `mix.json`). `wind_loop` is a seamless loop; `wind_stop` ends `wind_loop` (and the rain). `dig_loop` ends at shot
  S05: since 2026-11-18 a one-shot sized to its scene (the engine stops loops only at a music cue; PLAN.md).

## 8. Effects

Already in the app (use as is): `golden_rays` `tension_dim` `heart_glow` `sparkle` `zzz` `sunset_glow` `night`
`storm_rain` (Jonah).
Alias in the manifest (no C#): `wave_splash` → `splash`.
New, in `StoryFxMiracles.cs` (3 ids, nothing else):
- `dig_dirt` (node): clods and brown dust puffs tossed up and sideways from the node at random, 2-3 per second,
  for `dur` (the existing `dust_puff` is one slow ground puff, FX review 2026-11-17).
- `dust_fall` (node): a thin column of falling dust and crumbs from the node downward to the floor (y 0) for `dur`,
  brown specks plus a soft light shaft.
- `calm_wave` (node): a ring of flattening ripples spreading out from the node over the lake, then a glassy sheen;
  must end the `storm_rain` and `tension_dim` effects that are still running (stage cleanup), so the night is clear.

## 9. Manifest (lead writes it at Integration)

Strings: `dg_jesus` 耶稣 / Jesus, `dg_peter` 彼得 / Peter, `dg_miracles_man` 躺褥子的人 / The man on the mat,
`dg_friend1`…`dg_friend4` 朋友 / Friend, `dg_miracles_friends` 四个朋友 / The four friends,
`dg_miracles_people` 众人 / The crowd. Library: pinyin `zhēn zhèng de shén jì`, minutes 4, `"after": "joseph"`.
