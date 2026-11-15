# Joseph — animation (Animation role)

Built by `pipeline/js_animate.py` on the shared kit (`pipeline/story_kit/animation.py`), in the same way as
`pipeline/ru_animate.py`. Run `python3 pipeline/js_animate.py all` (build, verify, contact sheet, staging check).
Outputs: `assets/joseph/anim/{joseph,jacob,brother,pharaoh}.glb` (character, skin, one glTF animation per action
`<char>_<clip>`, no root motion), `clips.json` (loop flags, markers, travel speeds, checks, sample poses),
`contact_sheet.png` (key poses per clip on the twolands set, plus pair rows at the fitted distances).

The models are read fresh from `assets/joseph/model/characters.blend` on every run. Joseph's skinned coat mesh is
moved under its `coat` joint in the exported GLB (as `js_characters.py` does for the model GLB), so
`prop("joseph/coat", …)` still reaches it.

## Clips (CONTRACT §4: joseph 19, jacob 6, brother 13, pharaoh 8 = 46, all present, exact names)

Speed = natural travel speed in art-width units per second (stride ÷ stance time); the director may play a travel clip
up to 1.6× faster. Min y = lowest mesh point over the clip (with the props shown in that clip's look).

| Action | Frames | Seconds | Type | Speed | Markers | Min y |
|---|---|---|---|---|---|---|
| `joseph_idle` | 150 | 5.00 | loop |  |  | -0.0028 |
| `joseph_talk` | 96 | 3.20 | loop |  |  | +0.0011 |
| `joseph_walk` | 32 | 1.07 | loop | 0.1125 | `contactL` f0 (0.00 s), `contactR` f16 (0.53 s) | -0.0030 |
| `joseph_run` | 22 | 0.73 | loop | 0.4665 | `contactL` f0 (0.00 s), `contactR` f11 (0.37 s) | -0.0028 |
| `joseph_walk_sad` | 44 | 1.47 | loop | 0.0490 | `contactL` f0 (0.00 s), `contactR` f22 (0.73 s) | -0.0027 |
| `joseph_twirl` | 60 | 2.00 | one-shot |  | `spin` f10 (0.33 s), `front` f40 (1.33 s) | -0.0030 |
| `joseph_tell_dream` | 150 | 5.00 | loop |  |  | -0.0016 |
| `joseph_in_pit` | 96 | 3.20 | one-shot |  | `sit` f40 (1.33 s) | -0.0040 |
| `joseph_carry_work` | 38 | 1.27 | loop | 0.0764 | `contactL` f0 (0.00 s), `contactR` f19 (0.63 s) | -0.0028 |
| `joseph_sit_cell` | 90 | 3.00 | one-shot |  | `seated` f26 (0.87 s), `up` f64 (2.13 s) | +0.0005 |
| `joseph_bow_point_up` | 80 | 2.67 | one-shot |  | `bow` f22 (0.73 s), `point` f54 (1.80 s) | +0.0016 |
| `joseph_explain` | 120 | 4.00 | loop |  |  | +0.0016 |
| `joseph_stand_proud` | 60 | 2.00 | one-shot |  | `collar` f22 (0.73 s) | +0.0017 |
| `joseph_recognise` | 60 | 2.00 | one-shot |  | `start` f4 (0.13 s), `turn` f30 (1.00 s) | +0.0016 |
| `joseph_ask_gently` | 90 | 3.00 | loop |  |  | +0.0017 |
| `joseph_reveal` | 80 | 2.67 | one-shot |  | `off` f27 (0.90 s) | +0.0005 |
| `joseph_lift_up` | 90 | 3.00 | one-shot |  | `grip` f36 (1.20 s), `up` f78 (2.60 s) | +0.0005 |
| `joseph_hug` | 90 | 3.00 | loop |  |  | +0.0011 |
| `joseph_wave` | 48 | 1.60 | loop |  |  | -0.0026 |
| `jacob_idle` | 150 | 5.00 | loop |  |  | -0.0023 |
| `jacob_talk` | 96 | 3.20 | loop |  |  | -0.0000 |
| `jacob_give_coat` | 96 | 3.20 | one-shot |  | `offer` f24 (0.80 s), `pat` f60 (2.00 s) | -0.0000 |
| `jacob_weep` | 120 | 4.00 | loop |  |  | -0.0010 |
| `jacob_walk_old` | 48 | 1.60 | loop | 0.0488 | `contactL` f0 (0.00 s), `contactR` f24 (0.80 s), `stickPlant` f2 (0.07 s) | -0.0054 |
| `jacob_hug` | 90 | 3.00 | loop |  |  | -0.0000 |
| `brother_idle` | 150 | 5.00 | loop |  |  | -0.0041 |
| `brother_talk` | 96 | 3.20 | loop |  |  | +0.0009 |
| `brother_walk` | 36 | 1.20 | loop | 0.1167 | `contactL` f0 (0.00 s), `contactR` f18 (0.60 s) | -0.0062 |
| `brother_fold_arms` | 50 | 1.67 | one-shot |  | `folded` f20 (0.67 s) | -0.0007 |
| `brother_grumble` | 120 | 4.00 | loop |  |  | +0.0008 |
| `brother_angry_point` | 45 | 1.50 | one-shot |  | `jab` f12 (0.40 s) | +0.0016 |
| `brother_grab_coat` | 54 | 1.80 | one-shot |  | `grab` f16 (0.53 s), `off` f24 (0.80 s) | +0.0016 |
| `brother_take_coins` | 75 | 2.50 | one-shot |  | `coins` f22 (0.73 s), `fist` f30 (1.00 s) | +0.0017 |
| `brother_bow_low` | 75 | 2.50 | one-shot |  | `knees` f24 (0.80 s), `bow` f44 (1.47 s) | -0.0071 |
| `brother_fall_back_scared` | 45 | 1.50 | one-shot |  | `jerk` f4 (0.13 s), `sit` f20 (0.67 s) | -0.0075 |
| `brother_stand_up` | 66 | 2.20 | one-shot |  | `grip` f12 (0.40 s), `up` f54 (1.80 s) | -0.0052 |
| `brother_hug` | 90 | 3.00 | loop |  |  | -0.0021 |
| `brother_wave` | 48 | 1.60 | loop |  |  | -0.0031 |
| `pharaoh_idle` | 150 | 5.00 | loop |  |  | +0.0007 |
| `pharaoh_talk` | 96 | 3.20 | loop |  |  | +0.0019 |
| `pharaoh_doze` | 150 | 5.00 | loop |  |  | +0.0008 |
| `pharaoh_wake_jump` | 54 | 1.80 | one-shot |  | `jump` f6 (0.20 s), `land` f20 (0.67 s) | -0.0020 |
| `pharaoh_lean_ask` | 50 | 1.67 | one-shot |  | `ask` f20 (0.67 s) | +0.0019 |
| `pharaoh_delighted` | 60 | 2.00 | loop |  | `clap1` f8 (0.27 s), `clap2` f20 (0.67 s), `clap3` f32 (1.07 s) | -0.0023 |
| `pharaoh_crown_him` | 96 | 3.20 | one-shot |  | `lift` f18 (0.60 s), `on` f36 (1.20 s) | +0.0017 |
| `pharaoh_wave` | 60 | 2.00 | loop |  |  | +0.0013 |
Joseph's look per clip in the renders (the engine shows what `story.py` props say): coat = idle, talk, walk, twirl,
tell_dream; plain = walk_sad, in_pit, carry_work, sit_cell, bow_point_up, explain; governor (head-cloth + collar) =
run, stand_proud, recognise, ask_gently, reveal, lift_up, hug, wave.

## Checks (05-QUALITY-BAR §Animation)

| Check | Result |
|---|---|
| Every contract clip, exact names | 46 / 46; `verify` re-imports the GLBs: none missing, sampled pose error ≤ 7e-6 |
| Loop seams | frame N = frame 0 exactly (seam 0); every loop's seam step ≤ its largest inner step |
| Planted feet | ≤ 0.002 drift in every standing clip, except where the feet really move: `twirl` (the root bone spins 360°, the feet turn with it, 0.066), `in_pit` (stumble step, then the feet go forward as he sits, 0.012), `bow_low` (feet tuck back as he kneels, 0.053), `fall_back_scared` (feet come out from under him, 0.014) |
| Walk slip | the point that touches the page moves at the stance speed: ≤ 0.015 u/s (the kit's gait is overridden so the foot rolls about its heel and its ball) |
| Kneel / sit, lowest mesh point ≥ −0.008 | in_pit −0.0040, sit_cell +0.0005, bow_low −0.0071, fall_back_scared −0.0075, stand_up −0.0052 |
| Two-person clips probed as pairs | rendered (contact sheet pair rows, probes from front, top, back, phone) and measured: `paircheck` mode counts vertices of one actor inside the other's body (ray parity) |
| `clips.json` | loop flags, markers, natural speeds, stride and duty, per-clip checks |
| Export newer than models | anim GLBs written after `characters.blend` / model GLBs (checked at the end of the run) |

Pair results (deepest point of one body inside the other, body / hands):

| Pair | Distance | Body | Hands / forearms |
|---|---|---|---|
| joseph_hug + brother_hug | 0.11 / 0.115 / 0.12 | 0.010 (Joseph's collar against the brother's beard and chest, between them) | 0.016-0.019 (Joseph's forearms under the brother's arms) |
| joseph_hug + jacob_hug | 0.11 / 0.115 / 0.12 | 0.006 | 0.009-0.017 (Jacob's left hand on the waist) |
| lift_up + stand_up (B 24 f later) | 0.11 / 0.115 / 0.12 | 0.000 | 0.007 (the gripping fingers) |
| brother_grab_coat + joseph_idle | 0.11 / 0.12 | 0.002 | 0.006 (gripping fingers) |
| jacob_give_coat + joseph_idle | 0.12 | 0.003 | 0.010 |
| pharaoh_crown_him + joseph_explain, then + stand_proud (48 f later) | 0.12 | 0.005 | 0.001 after f 48 (explain's open palms would touch the belly after f 60, but Joseph is in stand_proud then) |
| brother_bow_low + joseph_recognise | 0.11 / 0.12 | 0.001 / 0.000 | 0.006 |

## What I looked at

The whole contact sheet; probes of every pair above from front, top, back and the phone angle; every kneel / sit
(in_pit inside the well at the PIT mark, sit_cell on the cell bench, bow_low, fall_back_scared, stand_up);
Joseph's coat forced visible in the deep bends (sit_cell, in_pit, bow_point_up, lift_up); jacob_weep from the
front (the hand is over the eyes, mouth and beard stay visible: it reads as weeping); the run from the front and
side; pharaoh's doze nods and the wake_jump belly from the side.

## Weak spots (not fixed here)

- **Coat in deep bends**: the coat itself follows the thighs (panels track 70 % of the thigh swing), but when
  sitting the panels splay sideways and the white tunic shows between the knees; it reads as the coat's V opening.
  The wide sleeves show skin at the elbow when the elbow bends past ~100° (sit_cell, in_pit). In the story the coat
  is not worn in any of these clips (it is taken in S03 before in_pit).
- **Tunic and knees**: in `run` and `sit_cell` the knee pokes through the tunic skirt for a few frames (a skin patch
  on the thigh). It is the body mesh's skirt weighting; the Characters role could weight the skirt hem more to the
  hips.
- **Hugs** overlap by up to 1 cm at the chest and 2 cm at the forearms under the arms (hidden between the two
  bodies from the phone view). Jacob's stooped robe sticks out 0.068 in front of him, so at 0.11 Joseph and Jacob
  already touch before anyone leans: keep their marks at 0.12 (S11 is).
- **twirl** spins the root bone 360° (like `ruth_joy`); the last frame's root rotation is the quaternion −1 (same
  rotation as +1). If Unity blends the next clip through a full turn, tell me and I will end the spin at 359.9°.
- **give_coat**: the right fist holds the stick upright while offering, so only the left palm is turned up; it
  reads as "offering" from the front, less so from behind.
- The head-cloth (`nemes`) is rigid: when Joseph bows his head in `recognise` the back of the cloth rises; I kept
  the head bow small (9°) and let the turn carry the "hiding".

## Staging notes for the lead

Read from `assets/joseph/timeline.json` (estimated timing; re-check after the voices) with
`python3 pipeline/js_animate.py staging`.

**Distances the two-person clips assume** (root to root, facing each other):

| Clip(s) | Fitted | In story.py now | Suggestion |
|---|---|---|---|
| `jacob_give_coat` → Joseph (S01) | 0.12 | JACOB_HOME ↔ JOSEPH_HOME = 0.146 (the pat falls 2.6 cm short) | JOSEPH_HOME = (−0.345, −0.167) |
| `brother_grab_coat` → Joseph (S03) | 0.11 | (−0.26, 0.04) ↔ PIT_EDGE (−0.20, 0.06) = **0.063: bodies intersect** | PIT_EDGE = (−0.156, 0.075) (0.11 on the same line; check it with the set's CLEARANCE) |
| `pharaoh_crown_him` → Joseph (S07) | 0.12 | THRONE ↔ COURT = 0.189 (hands would place the cloth in the air) | COURT = (0.278, −0.236), or a short Joseph `walk` to it before `crown_him` |
| `brother_bow_low` before Joseph (S09) | ≥ 0.11 (head clearance) | BRO_EGYPT ↔ (0.34, 0.08) = 0.130 | fine; 0.115 also fine (see next row) |
| `joseph_lift_up` + `brother_stand_up` (S10) | 0.115 (works 0.11-0.12) | 0.130 (hands miss by 1.5 cm) | BRO_EGYPT = (0.234, 0.124) → 0.115 for S09 and S10 |
| `joseph_hug` + `brother_hug` (S10) | 0.115 (0.11-0.12) | 0.130 | same fix as above |
| `joseph_hug` + `jacob_hug` (S11) | 0.115 (keep 0.12) | MEET ↔ MEET_JACOB = 0.120 | fine |

**Moves that glide** (a `to` on a clip that does not walk; A2):
- S03 `joseph in_pit to=PIT` (0.089). The clip stumbles back a step and sits down; let the glide run over its first
  0.5 s, or walk him in first (`act("joseph", "walk", to=PIT)`) and then `in_pit` without `to`.
- S04 `joseph sit_cell to=CELL` (0.134 from the carry_work mark): end `carry_work` at CELL instead, or add a `walk` to
  CELL before `sit_cell`. sit_cell assumes he stands on CELL facing the viewer with the bench behind him.
- S04 `brother idle to=PARK_L` (0.65) and `jacob idle to=PARK_L` (0.61); S08 `jacob idle to=JACOB_HOME` (0.61) and
  `brother idle to=BRO_HOME` (0.77, visible: S08 follows the brother). Place them at the shot change or use `walk`.
- S11 `joseph idle to=MEET` (0.32): use `run` for the travel (the later `run to=MEET` at dt −0.6 then has no
  distance left); `brother idle to=(0.16, 0.14)` (0.06): small, use `walk`.

**Moves near or above the speed limit** (needed ÷ natural speed, max 1.6): none above. Closest: S04 `carry_work`
PARK_L → (0.16, 0.06), 0.99 in 8.7 s = 1.49×; S11 `jacob walk_old` JACOB_HOME → MEET_JACOB, 0.48 in 6.7 s = 1.47×;
S03 `walk_sad` to PARK_L = 1.19×. If the real voices are shorter these go over: start Jacob nearer (he is off camera
at the S11 cut) and let carry_work start at the left page edge (x −0.60) instead of PARK_L.

**Clips that need a lead-in** (A4):
- `brother_fall_back_scared` starts from the `bow_low` end pose; `brother_stand_up` starts from the
  `fall_back_scared` end pose; `brother_hug` from standing (story order S09 → S10 is right).
- `joseph_walk_sad` (S03, he is led away) follows `in_pit`, which ends sitting in the well: the 0.25 s blend pops him
  up. Cut away at that moment, or ask for an extra `joseph_climb_out` clip.
- `joseph_sit_cell` and `joseph_in_pit` must start standing (they do).
- `joseph_stand_proud` gets only 1.4 s before the next `walk` (the clip is 2.0 s): the look-out over the land is cut;
  lengthen the `pause(3.0)` after it by 0.6 s, or accept.
- No actor has two clips starting at the same instant in the current timeline (A8). `joseph_hug` / `brother_hug`
  and `joseph_hug` / `jacob_hug` must start on the same frame (they rock in phase).

**Marker times** (all match story.py's prop `dt` as written):

| Clip | Marker | Frame | Seconds | story.py |
|---|---|---|---|---|
| `brother_grab_coat` | `off` (hide joseph/coat) | 24 | 0.80 | coat hidden at dt 3.4, grab_coat at dt 2.6 → 0.8 ✓ |
| `joseph_reveal` | `off` (hide joseph/nemes) | 27 | 0.90 | nemes hidden at dt 0.9 ✓ |
| `pharaoh_crown_him` | `on` (show joseph/nemes + collar) | 36 | 1.20 | shown at dt 1.2 ✓ |
| `joseph_lift_up` / `brother_stand_up` | `grip` | 36 / 12 | 1.20 / 0.40 | stand_up at dt 0.8 after lift_up ✓ |

Other markers in `clips.json` (contacts, claps, jab, coins, sit, bow, point …) are for FX / SFX timing only.
