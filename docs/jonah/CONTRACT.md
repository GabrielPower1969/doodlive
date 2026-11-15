# Jonah — production contract

Binding for every role. Story and lines: `STORY.md` + `storyboard/story.py`. Look: `DESIGN.md`. How to run each
step: `docs/pack-plans/01-LIFECYCLE.md`. Shared rules: `docs/pack-plans/03-RULES.md`. Kit: `docs/STORY-KIT.md`.
Template pack to copy from: **Ruth** (`pipeline/ru_*.py`, already on the kit). For the fish, read Daniel's lion
(`pipeline/da_characters.py`, `da_animate.py`: side-view UV, non-human rig).

Ids: story `jonah`, script prefix `jn`, env prefix `JN_`, page material `jn_page`, set `coast`.

## 1. Files and owners

| Role | Owns |
|---|---|
| Lead (story + integration) | `docs/jonah/*`, `assets/jonah/timeline.json` (generated), `assets/jonah/manifest.json`, `assets/jonah/{pack,faces}.json`, Unity, builds, device |
| Characters | `pipeline/jn_characters.py`, `assets/jonah/model/{jonah,captain,fish}.glb`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/jonah/RIG.md`, `docs/jonah/design/faces/` |
| Set + sheet | `pipeline/jn_coast.py`, `assets/jonah/model/coast.{glb,blend}`, `coast_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_jonah.py` (only if `make_sheet.py` cannot do it as is), `assets/jonah/sheet/`, `print/jonah-A4.{png,pdf}`, `print/jonah-A4-colored.pdf`, `assets/jonah/design.json`, `docs/jonah/SET.md` |
| Animation | `pipeline/jn_animate.py`, `assets/jonah/anim/`, `docs/jonah/ANIMATION.md` |
| Voice | `tools/story/cast_jonah.json`, `assets/jonah/audio/voice/`, `docs/jonah/VOICE.md` |
| Music + SFX | `tools/story/music_jonah.py`, `assets/jonah/audio/music/`, `assets/jonah/audio/sfx/`, `docs/jonah/MUSIC.md` |
| FX | `manifest.json` `fx.aliases` first; `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxJonah.cs` only for the 4 new ids in §8; `docs/jonah/FX.md` |

Nobody edits `assets/stories.json`, `assets/library.json`, `tools/i18n/strings.json` or `DGFxEffects.cs` by hand:
they are generated from the manifests by `tools/story/merge_packs.py`.

## 2. Cast

Units: art-width units (1.0 = art rectangle width), Y up, page = XZ plane at y = 0, +Z toward the viewer, +X right.

| Id | Size | Sheet slot (start value; Set + sheet owns the final one in `design.json`) | Projection |
|---|---|---|---|
| `jonah` | height 0.36 | sheetX −0.32, sheetY 0.015 | front |
| `captain` | height 0.38 | sheetX 0.32, sheetY 0.015 | front |
| `fish` | length 0.53 (nose to tail tip), height 0.21, width 0.205 with the side fins (changed from 0.50 / 0.20 / 0.16 after the polish round, 2026-11-15) | centre (0.0, 0.40), second row | **side view**, nose to −X |

`god` and `people` are voices only (no model). Budget: each human ≤ 25k triangles, fish ≤ 22k, ≤ 4 bone influences.

## 3. Skeletons

**Humans** (`jonah`, `captain`): the kit's contract bones, A-pose, facing +Z:
`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids`. Extras:
- `jonah`: `coatL coatR` (front panels of the open coat, from `chest`), `belt1` (hanging belt end, from `hips`),
  `seaweed` (prop bone, child of `head`; mesh `jonah_seaweed`, hidden by default).
- `captain`: `wrap1` (tail of the head-wrap, from `head`), `sash1` (hanging sash end, from `hips`).

**Fish** (new rig type), nose toward +Z in model space, belly on y = 0 when resting on the page:
`root body1 body2 body3 tail jaw finL finR dorsal eyelids`
- `body1` head and front third, `body2` middle, `body3` rear third, `tail` the tail fin (chain root→body1→body2→body3→tail).
- `jaw` (child of `body1`): the lower jaw; opens to 55° for the gulp. The mouth interior is modelled (pink).
- `finL finR` (children of `body2`), `dorsal` (child of `body2`), `eyelids` (child of `body1`; lids on the eye surface).

Faces: decals on UV1, one PNG per expression in `docs/jonah/design/faces/<char>_<expr>.png` (lists in DESIGN §1).
Eyelids must sit on the eye surface so a closed eye is visible (the Daniel lion bug).

## 4. Clips (names are the contract) — actions `<char>_<clip>`

"hold" = one-shot ending in a held pose. "seated" = on the ground / deck, hips down.

| jonah (24) | what |
|---|---|
| `idle` (loop) | standing, arms loosely crossed, weight shifting, grumpy breathing |
| `talk` (loop) | generic talk |
| `walk` (loop) | plain walk |
| `tiptoe` (loop) | exaggerated cartoon tiptoe, looking over the shoulder |
| `stomp_walk` (loop) | cross, heavy stamping walk |
| `listen_up` (one-shot hold) | looks up toward the sky, hand half raised |
| `refuse` (one-shot hold) | shakes head, crosses arms, turns a shoulder away |
| `sleep_curl` (loop, seated) | curled on the side, slow breathing (snore rhythm) |
| `wake_startled` (one-shot hold) | jerks up to sitting, then stands, wide-eyed |
| `ashamed` (loop) | head low, one hand on the back of the neck |
| `fall_in` (one-shot) | lifted and tipped backward over the rail: root travels +Z 0.10 and down to y −0.14 in 1.4 s (marker `splash` at the lowest point) |
| `sit_hold_nose` (loop, seated) | sits hugging knees, pinches nose, looks round |
| `kneel_pray` (one-shot hold) | kneels and sits back on his heels, hands together, head bowed (knees on the floor, meshMinY ≥ −0.008; head top ≤ 0.25 so it stays inside `belly`) |
| `tumble_out` (one-shot hold) | rolls in along +X for 0.16 and ends sitting, legs out (marker `land`) |
| `sit_dazed` (loop, seated) | sways, shakes water from an ear |
| `stand_up` (one-shot) | from seated to standing |
| `nod_ok` (one-shot) | deep breath, firm nod |
| `proclaim` (loop) | hands cupped round the mouth, leaning forward, turning left and right |
| `surprised` (one-shot hold) | double-take, jaw drops |
| `sit_sulk` (one-shot hold, seated) | plonks down, arms folded, chin on chest, foot tapping |
| `relax_happy` (loop, seated) | leans back on the hands, face up, contented |
| `wail` (loop, seated) | arms thrown up toward the plant, rocking |
| `look_city` (one-shot hold, seated → standing) | stands, turns to the city, hand slowly drops from the hip |
| `wave` (loop) | small, a bit shy wave |

| captain (9) | what |
|---|---|
| `idle` (loop) | hand on the steering oar, swaying with the ship |
| `talk` (loop) | big open gestures |
| `walk` (loop) | rolling sailor's walk |
| `greet` (one-shot hold) | arm sweeps wide "welcome", then points ahead |
| `steer_hard` (loop) | both hands heaving the oar left and right, braced legs |
| `shake_awake` (loop) | bends and shakes someone lying 0.10 in front |
| `refuse_hands` (one-shot hold) | both palms out, shakes head |
| `heave` (one-shot) | eyes shut, lifts and tips someone 0.10 in front over the rail (marker `release`) |
| `amazed` (one-shot hold) | hands on head, looks at the calm sea |

| fish (6) | what |
|---|---|
| `idle` (loop) | hovering in place, fins sculling, slow tail |
| `swim` (loop) | body wave travelling head to tail; state the speed in `clips.json` |
| `gulp` (one-shot hold) | rises (root y +0.10), jaw opens to 55°, lunges 0.08 forward, snaps shut, sinks back (marker `gulp`) |
| `burp` (one-shot) | cheeks puff, small hop, jaw pops open 10° |
| `spit` (one-shot) | rears, jaw wide, body recoils 0.05 (marker `spit`) |
| `wave_fin` (loop) | rolls a little to one side and flaps `finR` |

Rules: loops seamless; one-shots end in poses the next clip can blend from in 0.25 s; talk clips move `jaw`;
secondary motion on coat panels, belt end, head-wrap tail, sash end, fish fins and tail; planted feet do not slide;
`clips.json` states each travel clip's speed.

## 5. Timeline

`python3 tools/story/build_timeline.py jonah` from `storyboard/story.py`, timed by
`assets/jonah/audio/voice/durations.json`. Actors on the ship use `y=DECK` (0.10). An actor not in a scene is parked
at `PARK` (0.80, 0.30) **and hidden** with `prop("<actor>", show=False)` (Esther's precedent; parked but visible, the
fish and the captain floated over the table, review 2026-11-15). Cameras never target `all` (it averages hidden actors
too); see the header of `storyboard/story.py`.

## 6. Set (`assets/jonah/model/coast.glb`, root node `coast`)

Floor x ±0.60, z −0.5875…0.21. Node names are the contract.

| Node | Where / what |
|---|---|
| `sea` | x −0.60…0.06, all z; surface y ≈ 0.012; looping action `seaWave` (4 s, seamless) |
| `ship` | hull centre (−0.34, −0.22), length 0.38 along X, beam 0.14; deck top **y = 0.10**; mast top ≤ 0.46; furled sail; steering oar at the stern (−0.50); looping action `shipRock` (6 s, ±3° roll, seamless) |
| `cargo` | sacks and jars on deck around (−0.30, −0.29), top ≤ 0.16 (child of `ship`) |
| `plank` | gangplank from the beach (0.08, −0.20, y 0.02) to the deck edge (−0.16, −0.22, y 0.10) |
| `beach` | sand strip x 0.06…0.22, shells, mooring posts, small rowing boat at (0.14, −0.40) |
| `road` | pale track from (0.60, 0.16) to the gate and to the beach |
| `nineveh` | wall front face z ≈ −0.40 from x 0.10 to 0.60, top ≤ 0.30; towers; roofs and temple behind |
| `gate` | arch centre (0.34, −0.40), opening 0.10 wide, 0.16 high |
| `hill` | mound centre (0.44, 0.06), radius 0.14, top y ≤ 0.04 (a seated actor sits on it at y 0) |
| `shelter` | at (0.52, 0.02); hidden until S10 |
| `plantSmall` `plantBig` `plantDry` | all rooted at (0.34, 0.06); `plantBig` / `plantDry` crown spans x 0.30…0.50, bottom ≥ 0.26, top ≤ 0.44; all hidden at start |
| `worm` | on the stem at h ≈ 0.14; hidden |
| `folk1`…`folk9` | (added 2026-11-15) kneeling townsfolk in sackcloth in front of the gate (back row z −0.33 at x 0.25 / 0.34 king / 0.43 / 0.52; front row z −0.262 at x 0.205 / 0.272 child / 0.392 child / 0.475 / 0.555); origin at the knees on the ground; hidden until S09, popped in with `grow` |
| `belly` | ribbed dome centre (−0.20, 0.08), inner radius 0.13, height 0.26, open toward +Z over a 120° arc; hidden until S06 |

**Marks that must stay clear** (nothing above 0.012 within 0.05; nothing on the straight path between consecutive
marks of one actor; print `CLEARANCE`):
- jonah, ground: (0.28, 0.14) → (0.12, 0.10) → [plank] → deck; (0.12, 0.10) → (0.32, −0.16) → (0.42, 0.08) (gate mark moved forward 2026-11-15: from (0.34, −0.24)
  Jonah read as standing in the gatehouse).
- jonah, deck (y 0.10): (−0.26, −0.22), (−0.30, −0.26), (−0.22, −0.16).
- captain, deck: (−0.44, −0.22), (−0.36, −0.24).
- fish, sea: (−0.24, 0.02), (−0.04, 0.10), entry from x −0.80; the fish needs water depth for its belly: sea floor
  is the page, so the fish swims half out of the water (model y from −0.02 to 0.18; nothing of the set in its lane
  z −0.06…0.21, x −0.60…0.02).
- belly: (−0.20, 0.08) inside the dome.

Budget: set ≤ 60k triangles. UV0 = the colouring sheet, exactly as Ruth's set (front / plan projections, upward faces
take a clean texel from their own region).

## 7. Audio

Voice −16 LUFS, music −20 LUFS, SFX peak −3 dBFS, 44.1 kHz mono WAV + 96 kbps MP3.

- **Voices** (`cast_jonah.json`): `narrator` = the family storyteller (Qwen `vivian` zh); `god` = the same voice as
  Exodus' `god` (read `tools/story/cast_exodus.json`); `jonah`, `captain` new, chosen by audition; `people` = a crowd
  of 8-10 layered voices incl. two children. **English: Qwen3-TTS only (Apache-2.0). Do not use `edge-tts`** (no
  commercial licence; `docs/pack-plans/03-RULES.md` R7).
- **Music cues**: `call runaway storm deep prayer shore nineveh repent sulk plant mercy` (+ `cues.json` loop points).
- **SFX**: `soft_chime seagulls thunder rain_loop rain_stop splash_big bubbles gulp burp spit_pop grow_whoosh munch
  cicadas_heat` (+ `mix.json`). `rain_loop` is a seamless loop that `rain_stop` ends.

## 8. Effects

Already in the app (use as is): `golden_rays` `tension_dim` `prayer_glow` `heart_glow` `splash` `sea_wind` `zzz`
`steam` `sweat`.
Alias in the manifest (no C#): `plant_grow` → `sparkle`.
New, in `StoryFxJonah.cs` (4 ids, nothing else):
- `storm_rain` (stage): slanted rain streaks over the whole page, 2-3 lightning flashes (a brief cool-white stage
  tint), darker sky band; fades in 1 s, out 1.5 s.
- `bubbles` (node): round bubbles rising and wobbling from the node, popping at 0.25 above it.
- `deep_glow` (stage): deep teal tint, slow light ripples (caustics) on the page, a few drifting motes.
- `sun_scorch` (node): a small hot sun above the node, wavy heat lines, the node's surroundings tinted warm.

## 9. Manifest (lead writes it at Integration)

Strings: `dg_jonah` 约拿 / Jonah, `dg_captain` 船长 / Captain, `dg_jonah_people` 尼尼微人 / People of Nineveh
(`dg_people` already means the Israelites in Exodus; the name plate looks up `dg_<story>_<who>` first).
`dg_god` exists. Library: pinyin `yuē ná yǔ dà yú`, minutes 3.5, `"after": "daniel"`.
