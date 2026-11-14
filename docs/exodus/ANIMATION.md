# Exodus — skeletal animation (Animation role)

Owner: Animation. Binding contract: [CONTRACT.md](CONTRACT.md) §3 (bones) and §4 (clip names). Rig: [RIG.md](RIG.md).
Pipeline: `pipeline/ex_animate.py`, a copy of Ruth's `pipeline/ru_animate.py` (same clip-function method, IK, spring
chains, export, verify). Built 2026-11-14 with Blender 5.2.3 from the Characters files written 15:40:33 (Moses's new
UVs, staff foot on the floor).

```
python3 pipeline/ex_animate.py all        # build + verify + contact sheet (~6 min, most of it the contact renders)
python3 pipeline/ex_animate.py build      # 47 actions -> anim/{moses,pharaoh,miriam}.glb + anim/clips.json with checks
python3 pipeline/ex_animate.py verify     # re-import the GLBs: animations, sampled joints, UV layer order, prop nodes
python3 pipeline/ex_animate.py contact    # anim/contact_sheet.png
EX_PROBE="moses_throw_staff:8,16,39:lside" python3 pipeline/ex_animate.py probe     # $EX_ANIM_WORK/probe.png
EX_ONLY=moses_idle,pharaoh_ride python3 pipeline/ex_animate.py build                 # bake + check a subset, no export
EX_CHARS=miriam python3 pipeline/ex_animate.py build                                 # export one character only
```

Views for probes: front q3 side back q3l lside top low (+`#bone` close-up); `EX_PROBE_DIST`, `EX_PROBE_RES`,
`EX_SET=1` (render on the set; by default only sad_sit / tantrum show the set, for the dais seat).
Inputs read at run time: `model/characters.blend`, `model/egypt.glb` (renders only), `timeline.json`,
`model/regions_characters.json` (demo colours and `faceDecal.clipExpression` for the face per clip; Integration's
`faces.json` wins once it exists). Work files: `$EX_ANIM_WORK` (default `/tmp/ex_anim_work`).
**Rebuild after any change to characters.blend** (the anim GLBs carry its mesh, UVs and skin).

## 1. Deliverables

| File | What |
|---|---|
| `assets/exodus/anim/moses.glb` | Moses mesh + skin (33 bones) + `moses_staff` / `moses_eyelids`, 18 animations |
| `assets/exodus/anim/pharaoh.glb` | Pharaoh + `pharaoh_chariot` / `pharaoh_wheelL` / `pharaoh_eyelids`, 17 animations (16 contract + `ride_idle`) |
| `assets/exodus/anim/miriam.glb` | Miriam + `miriam_tambourine` / `miriam_eyelids`, 12 animations |
| `assets/exodus/anim/clips.json` | Ruth schema per clip: action, frames, seconds, loop, rootMotion (false), markers {name: {frame, sec}}, loopSeamMaxErr, props, notes, naturalSpeed (+ stride), samples, checks. New: `timeScale` + `designFrames` (see §3), checks `loopSeamVelErr` / `endVelMax` / `stanceSlipMax` / `staffPlantSlipMax` / `bodyMinY`; top level `stage` and `staffHidden`; `timelineMissing` is **empty** |
| `assets/exodus/anim/contact_sheet.png` | Key poses of every clip (demo colours, face decal per clip, props shown only where posed, the staff hidden while it is the snake) + three pair rows at story distances |

Character-local, root at the origin, facing +Z, 30 fps, every bone keyed (rotation, location, scale; the blink is a
scale of `eyelids`), UV0 = page (in 0..1, checked), UV1 = decal. Prop nodes as RIG.md §1. Verify: all 47 sampled joint
sets match the build within 1e-5; no contract clip missing.

## 2. Clips

meshMinY = lowest deformed vertex (hidden props left out; 0 = page; limit −0.008). Drift = largest slide of a planted
toe in a non-locomotion clip (deliberate steps show up here); bold = natural speed. Seam = loopSeamVelErr (velocity
change across the loop seam; frame N equals frame 0 exactly in every loop, `loopSeamMaxErr` 0.0) or, for one-shots,
endVelMax (joint motion in the last frame; ≈ 0 = a still end pose to blend from).

| Action | Frames | s | Loop | Markers (name frame/s) | meshMinY | drift / speed | seam / end vel | Props |
|---|---:|---:|:---:|---|---:|---:|---:|---|
| `moses_idle` | 150 | 5.0 | yes | — | -0.0013 | 0.0013 | 0.00017 | staff |
| `moses_walk_staff` | 44 | 1.4667 | yes | contactL 0/0.0, contactR 22/0.7333, staffPlant 0/0.0 | -0.0059 | **0.066 u/s** | 0.00683 | staff |
| `moses_talk` | 96 | 3.2 | yes | — | 0.0 | 0.0 | 0.00304 | staff |
| `moses_look_curious` | 120 | 4.0 | yes | — | -0.0 | 0.0016 | 0.00067 | staff |
| `moses_startle` | 36 | 1.2 | no | jump 8/0.2667 | -0.0018 | 0.0006 | 0.00073 | staff |
| `moses_kneel_bow` | 66 | 2.2 | no | knee_down 24/0.8, bow 44/1.4667 | -0.003 | 0.0203 | 0.00061 | staff |
| `moses_who_me` | 96 | 3.2 | yes | — | 0.0 | 0.0114 | 0.00017 | staff |
| `moses_throw_staff` | 40 | 1.3333 | no | release 16.5/0.55 | -0.0026 | 0.016 | 0.0003 | staff |
| `moses_jump_back` | 54 | 1.8 | no | hop 8/0.2667, land 20/0.6667 | -0.0027 | 0.0097 | 0.00032 | — |
| `moses_grab_tail` | 48 | 1.6 | no | grab 20/0.6667, staff 27/0.9 | -0.007 | 0.0125 | 0.00396 | staff |
| `moses_nod_brave` | 50 | 1.6667 | no | nod 26/0.8667 | -0.0 | 0.004 | 0.00018 | staff |
| `moses_staff_raise` | 40 | 1.3333 | no | up 16/0.5333 | -0.002 | 0.0179 | 0.00089 | staff |
| `moses_sigh_head` | 54 | 1.8 | no | sigh 16/0.5333 | 0.0 | 0.0 | 0.00024 | staff |
| `moses_brave_talk` | 96 | 3.2 | yes | — | 0.0 | 0.0 | 0.00111 | staff |
| `moses_staff_over_sea` | 270 | 9.0 | no | reach 30/1.0, gust 120/4.0 | -0.0046 | 0.034 | 0.00555 | staff |
| `moses_clap` | 32 | 1.0714 | yes | clap1 0/0.0, clap2 16/0.5357 | -0.0002 | 0.0 | 0.00734 | staff |
| `moses_talk_warm` | 120 | 4.0 | yes | — | 0.0 | 0.0 | 0.00139 | staff |
| `moses_wave` | 48 | 1.6 | yes | — | 0.0 | 0.0 | 0.00179 | staff |
| `pharaoh_idle` | 150 | 5.0 | yes | — | -0.0025 | 0.0022 | 0.00089 | — |
| `pharaoh_walk` | 36 | 1.2 | yes | contactL 0/0.0, contactR 18/0.6 | -0.0025 | **0.1121 u/s** | 0.00395 | — |
| `pharaoh_talk` | 96 | 3.2 | yes | — | 0.002 | 0.0118 | 0.00837 | — |
| `pharaoh_smug` | 120 | 4.0 | yes | — | 0.0011 | 0.0001 | 0.00033 | — |
| `pharaoh_point_order` | 36 | 1.2 | no | point 12/0.4 | 0.002 | 0.0159 | 0.00021 | — |
| `pharaoh_laugh` | 75 | 2.5 | no | ha 10/0.3333 | 0.0014 | 0.004 | 0.00011 | — |
| `pharaoh_arms_crossed` | 120 | 4.0 | yes | — | 0.002 | 0.0009 | 0.00098 | — |
| `pharaoh_frog_panic` | 150 | 5.0 | no | freeze 6/0.2, swat 36/1.2, allright 110/3.6667 | 0.0007 | 0.0026 | 3e-05 | — |
| `pharaoh_sneaky_no` | 80 | 2.6667 | no | rub 8/0.2667, no 44/1.4667 | -0.0025 | 0.0018 | 5e-05 | — |
| `pharaoh_sad_sit` | 180 | 6.0 | yes | — | 0.0007 | 0.0 | 0.00749 | — |
| `pharaoh_tantrum` | 105 | 3.5 | no | stamp1 36/1.2, stamp2 50/1.6667, stamp3 64/2.1333, point 84/2.8 | 0.0007 | 0.0394 | 6e-05 | — |
| `pharaoh_ride` | 48 | 1.6 | yes | — | -0.0004 | **0.1335 u/s** | 0.00402 | chariot, wheelL |
| `pharaoh_ride_idle` **extra** | 90 | 3.0 | yes | — | -0.0001 | 0.0 | 0.00022 | chariot, wheelL |
| `pharaoh_wobble` | 84 | 2.8 | no | tilt 6/0.2, crouch 64/2.1333 | -0.0005 | 0.0 | 0.0002 | chariot |
| `pharaoh_soggy_sit` | 120 | 4.0 | yes | — | 0.0018 | 0.0 | 0.0028 | — |
| `pharaoh_sneeze` | 72 | 2.4 | no | ah1 10/0.3333, ah2 26/0.8667, achoo 40/1.3333 | 0.0018 | 0.0 | 0.00018 | — |
| `pharaoh_angry` | 90 | 3.0 | yes | — | 0.002 | 0.0001 | 0.00067 | — |
| `miriam_idle` | 150 | 5.0 | yes | — | -0.0028 | 0.0026 | 0.00019 | — |
| `miriam_walk` | 28 | 0.9333 | yes | contactL 0/0.0, contactR 14/0.4667 | -0.0034 | **0.1182 u/s** | 0.00637 | — |
| `miriam_talk` | 96 | 3.2 | yes | — | 0.0004 | 0.0 | 0.00198 | — |
| `miriam_carry_brick` | 90 | 3.0 | yes | — | 0.0001 | 0.0021 | 0.00065 | — |
| `miriam_pray_stand` | 120 | 4.0 | yes | — | 0.0011 | 0.0 | 0.00048 | — |
| `miriam_hurry_wave` | 72 | 2.4 | yes | — | 0.0004 | 0.0021 | 0.00605 | — |
| `miriam_joy` | 60 | 2.0 | yes | hop 16/0.5333 | 0.0001 | 0.0021 | 0.00178 | — |
| `miriam_scared` | 90 | 3.0 | yes | — | -0.0024 | 0.0 | 0.00296 | — |
| `miriam_wow` | 45 | 1.5 | no | wow 14/0.4667 | 0.0016 | 0.0019 | 0.00031 | — |
| `miriam_tambourine_dance` | 128 | 4.2857 | yes | hit1 0/0.0, hit2 16/0.5357, hit3 32/1.0714, hit4 48/1.6071, hit5 64/2.1429, hit6 80/2.6786, hit7 96/3.2143, hit8 112/3.75 | 0.0002 | 0.0708 | 0.03635 | tambourine |
| `miriam_wave` | 48 | 1.6 | yes | — | 0.0004 | 0.0001 | 0.00163 | — |
| `miriam_clap` | 40 | 1.3333 | yes | clap1 7/0.2333, clap2 19/0.6333, clap3 31/1.0333 | 0.0004 | 0.0 | 0.00028 | — |

Extra checks: Moses `staffFootY` is 0.000 wherever the staff stands (walk_staff lifts it to 0.020 in the swing); the
planted staff in `walk_staff` slides 0.0028 on the page at the natural speed, the feet 0.007 (`stanceSlipMax`;
Pharaoh walk 0.005, Miriam walk 0.008). Pharaoh `bodyMinY` in ride / ride_idle is 0.0356 (soles on the 0.035 floor).

### Acting notes

- **Moses** — old but steady; the baked stoop stays (breaths lift it, `nod_brave` and `brave_talk` stand taller).
  `idle`: both hands stacked on the staff planted front-right, one sigh, slow look round, a beard stroke.
  `walk_staff`: 82 steps/min, the staff swings with the left foot and is planted with it (still on the page while
  it carries weight), mantle panels swing with the legs. `look_curious`: leans in, left hand shading the eyes, head
  tilts, up on the toes. `startle`: small jump, hands fly up, the staff lifts and is planted again, hand to chest.
  `kneel_bow`: steps the left foot forward and goes down on the right knee, staff upright at his side, hand on heart,
  deep bow. `who_me`: pats his chest, head shakes, a big helpless shrug with the palm out. `throw_staff`: wind-up,
  the staff is flung down in front, the fist opens at **`release` = 16.5 / 0.55 s** (pose marker rounded to f17),
  staff horizontal at hip height there. `jump_back`: comic hop **0.06 back** (body only, the root stays), arms flung
  up, lands in a crouch pointing at the snake. `grab_tail`: steps back in, bends low, right hand to y 0.02 in front
  (grab f20), the staff reappears upright in the rising fist at **f27 = 0.9 s**, planted at his side. `nod_brave`:
  deep breath, firm nod, pulls the staff upright, chin up. `staff_raise`: fist and staff high above the head, left arm
  out with an open hand. `sigh_head`: long sigh, three slow shakes, rubs his brow. `brave_talk`: tall, palm out,
  steadying pushes on the beats. **`staff_over_sea`** (9 s, covers the 9 s `sea_wind`): breath, step onto the left
  foot, both arms forward-up holding the staff level across above his head, chin up; gusting wind blows the beard to
  his right and flares / flaps the mantle back (per-bone wind on the spring chains); arms brace on the gusts.
  `clap`: left palm claps onto the right fist on the staff on the song's dotted beats. `talk_warm`, `wave`.
- **Pharaoh** — vain and theatrical; chest out, chin up in every clip except the sad one. `idle`: fist on hip, admires
  his bracelet. `walk`: strut, high knees, stiff arm swings. `smug`: fists on hips, sway, heavy lids. `point_order`:
  arm shoots out pointing, other fist on the hip, jab. `laugh`: leans back, head back, hands on belly, fading
  shoulder-shake pulses, wipes an eye, ends exactly in `smug` frame 0. `arms_crossed`: arms folded high, nose in the
  air turned away, foot taps, one peek back. `frog_panic` (5 s): freezes, eyes up, swats at his head while hopping
  three times, then both palms out pushing twice ("all right, all right"). `sneaky_no`: hunched hand-rubbing, then a
  finger-wag by his face. **`sad_sit`** (no comedy): sits on the dais step edge, elbows on knees, face in hands, slow
  heavy breaths with a shudder, lifts his face once to stare, sinks back. `tantrum`: frame 0 = the sad_sit pose; leaps
  up, fists shaking, three big stamps (L R L, markers), flings the arm forward pointing. **`ride`**: hips +0.035
  (soles on the chariot floor), fists forward with invisible reins, springy knees, chariot jiggles with both wheels on
  the page, the left wheel turns once per loop, lappets blown back. **`wobble`**: the chariot tips onto its wheel-less
  left side about the right wheel's contact (up to 14°, rocks twice), arms windmill, then he crouches clinging to the
  front rail (soles stay on the tilted floor). **`soggy_sit`**: legs straight out on the sand, toes up, slumped, hands
  on the sand, lappets pulled down flat, bursts of shivers with chattering jaw, a big sigh, a sulky look up.
  `sneeze`: two growing inhales back, a big forward ACHOO (f40), slumps back to exactly soggy_sit frame 0. `angry`.
- **Miriam** — lively, quick. `idle`: weight shifts, glances, tucks her braid. `walk`: quick springy steps (129/min).
  `carry_brick`: bent under a mimed brick held at the chest, shuffling in place, hitches it up. `pray_stand`: hands
  clasped, head bowed, a held-back sob, looks up once. `hurry_wave`: both arms scoop "come on" in turn, looking left and
  right, bouncing. `joy`: dip, hop, arms up, laughing. `scared`: hands at mouth, shrunk back, trembling, two quick
  glances behind. `wow`: gasp, hands to cheeks, leans back on her toes; holds. **`tambourine_dance`**: see §3.

## 3. The song clips (`tambourine_dance`, `moses_clap`)

`song` is 6/8 at dotted quarter = 112: bar = 15/14 s = 1.071429 s, dotted beat = 0.535714 s; bar 1 starts at the cue
start, which is also the act start of both clips (t 245.27). 4 bars = 30/7 s = 128.571 frames at 30 fps, not a whole
frame count, so the clips are designed on whole frames and **time-scaled in the GLB**:

- `miriam_tambourine_dance`: 128 design frames, every key time × **1.004464** → 4.285714 s = exactly 4 bars. Beats every
  16 design frames: markers `hit1`..`hit8` at design frames 0, 16 … 112 (`sec` in clips.json is the scaled time:
  0, 0.5357, 1.0714 …). The tambourine is shaken high in the left hand between beats and brought in to meet the right
  palm on each dotted beat (louder on the downbeats); step-hops on every beat; bar 3 is a turning hop (the **root turns
  360°** about Y, no translation); bar 4 shaken higher with a kick. Frame 0 is a downbeat hit.
- `moses_clap`: 32 design frames × 1.004464 = one bar (1.071429 s), claps on design frames 0 and 16 = the two dotted
  beats.

clips.json: `frames` = design frames, `seconds` = scaled length, `timeScale` 1.004464. The patch (`patch_timescale`)
appends new time accessors for those two animations only; `verify` samples them at the scaled times. Over the 12.4 s
scene there is no drift against the music if both start at t 245.27 (the timeline does).

## 4. Natural speeds (in-place locomotion; the director moves the actor)

| Clip | Stride | Duty | Natural | Timeline needs (current `timeline.json`) |
|---|---:|---:|---:|---|
| `moses_walk_staff` | 0.060 | 0.62 | **0.066 u/s** | S02 0.30 in 12.6 s (0.024, fine); **S03 0.27 in 1.35 s → 0.20 (3×)**; **S05 0.262 in 2.0 s → 0.131 (2×)**; S07 0.27 / 28.8 s; S08 0.38 / 27 s; S11 0.18 in 5.6 s and 0.16 in 23.6 s (fine) |
| `miriam_walk` | 0.064 | 0.58 | **0.118 u/s** | S07 0.23 / 14.7 s; S08 0.45 in 4.04 s → 0.111 (fine); S11 0.25 (new mark (0.27, 0.09)) in 5.3 s and 0.26 / 23 s (fine) |
| `pharaoh_ride` | wheel r 0.034, one turn per 1.6 s loop | — | **0.134 u/s** | S09 0.19 in 2.8 s (fine), 0.30 to PH_CHASE (fine); S12 0.34 in 2.19 s → 0.155 (1.16×, fine) |
| `pharaoh_walk` | 0.078 | 0.58 | **0.112 u/s** | not used by the timeline |

The ride's natural speed matches the left wheel's spin (2π·0.034 / 1.6 s); at another speed the wheel slips a little.

## 5. Staging the clips assume (`clips.json stage`)

- **sad_sit / tantrum frame 0**: hip joint (0, 0.062, −0.072) root-local = sitting on the edge of the dais's upper
  step (top 0.030, front edge z −0.378 world) with the root at PH_PALACE (−0.36, −0.30) facing the viewer. Anywhere
  else he sits on air.
- **soggy_sit / sneeze**: on the page, hip joint (0, 0.0305, −0.010), legs out to z ≈ +0.17.
- **jump_back** ends with the body 0.06 behind the root; **grab_tail** starts there and steps back to the root.
- **ride / ride_idle / wobble**: chariot floor y 0.035; the chariot bone moves only in wobble (tips about the right wheel
  contact (−0.060, 0, −0.004)) and jiggles ≤ 0.8° in ride. `wheelL` spins in ride only.
- **Staff hidden** (`staffHidden`): throw_staff after 0.55 s, all of jump_back, grab_tail before 0.9 s — exactly the
  timeline's prop events; renders and checks hide it there too.
- Pair rows in the contact sheet: brave_talk + miriam scared (S10, 0.112), staff_raise + pharaoh laugh (S05, 0.197),
  clap + tambourine_dance (S13, 0.106).

## 6. Notes for Story / Integration (things the timeline should change or know)

1. **Pharaoh sinks into the chariot after every ride move.** The director hands a finished locomotion move to `idle`
   (StoryDirector `Move`), and `idle` stands on the page, 0.035 below the chariot floor — S09 from ~183.0 s, and
   **from ~186.6 s to 225.0 s at PH_CHASE** (38 s, in view during S10/S11). Fix: an `act("pharaoh", "ride_idle")` right
   after each ride move (extra clip, built for this), or a director rule "after ride, play ride_idle".
2. **S02→S03 Moses never walks to the bush**: `walk_staff to MO_BUSH` and `look_curious` share t 38.28; the second act
   stops the move, so he stays at MO_PATH (0.34, −0.30). The next walk (46.22 → startle 47.57) then needs 0.27 in 1.35 s
   = 3× his pace: at the 1.6× cap he covers ~0.14 and startle stops him ~0.13 short of (0.07, −0.30). Start look_curious
   after the walk (≈ 4.5 s later), or move the mark.
3. **S05 walk to the palace** needs 0.131 u/s (2×); at 1.6× he stops ~0.05 short when staff_raise starts. Give it ~2 s more.
4. **sad_sit at 155.62** blends from a standing pose in 0.25 s (he drops onto the step). The camera is on Miriam then;
   fine unless the shot changes.
5. **Miriam glides** in `idle` with `to` at 92.86 (0.108, eased glide) — insert a `walk`.
6. **wobble → soggy_sit**: wobble ends crouched in the chariot at PH_SEA; soggy_sit glides him 0.126 to PH_SOGGY while
   sitting (reads as "washed back", hidden by the splash FX at 0.4 s). OK as staged.
7. `throw_staff` release is 16.5 frames = 0.55 s exactly in clips.json (`frame` 16.5); the Blender pose marker is f17.
8. **No brick prop** exists in the rig: `carry_brick` mimes a 0.045-wide block at her chest. A `miriam/brick` prop
   (child of a hand) from Characters would make S01 read much better; the clip already holds the hands for it.
9. Lip sync overrides `jaw` in talk clips; small keyed jaw elsewhere (laugh, sneeze, joy, tambourine_dance, clap).
10. Root rotation: `miriam_tambourine_dance` turns the root 360° in bar 3 (as Ruth's joy).

## 7. How the motion is made

As Ruth §6 (clip functions → channels in design axes, Catmull-Rom keys, leg / arm IK with targets in any bone's
space, irregular blinks, syllable jaw rhythms with beats driving nods and gestures, eased one-shots with anticipation,
overshoot and settle, pulse trains for laughs, sobs, hits and shivers). New in Exodus:

- **Moses's staff solver** (Naomi's): staff foot + direction on the page → right wrist iterated until the foot is
  there; without a foot the staff follows the hand (`staff.aim`). The left hand can be IK'd in staff space.
- **Chariot** (`chariot_xf`): rotation about any pivot by the bone's rotation + compensating translation; Pharaoh's
  feet targets are transformed with it so his soles stay on the tilted floor.
- **Wind on spring chains**: `wind.<bone>` = a direction × strength the chain's target is pulled toward (gusts are
  sums of incommensurate sines; seamless versions for loops).
- **Spring chains**: beard1-2 (k 85, c 8, 25 % rest hang, ≤ 22°), mantleL / mantleR (80 / 7 / 22 % / 16°), mantleBack
  (70 / 7 / 25 % / 18°), nemes1L / nemes1R (110 / 9 / 20 % / 14°), nemesBack (90 / 8), scarf1-2 (75 / 7.5 / 30 % / 30°),
  braid1-2 (95 / 8 / 25 % / 24°). Loops simulate 3 cycles and close exactly.
- **Time-scaled clips** (`timescale`, `patch_timescale`), §3.
- **Checks**: loop seam velocity, one-shot end velocity, stance slip vs. natural speed (feet and planted staff, in a
  world frame moving at the natural speed), meshMinY with per-frame prop visibility, bodyMinY on the chariot.

## 8. Rough edges (honest list)

- **Weakest clips**: `carry_brick` (no brick, see §6.8); `brave_talk` (the palm-out reads as a hand held at chest
  height more than a clear "stop / be calm" palm); `startle` (small, as the contract asks; at phone distance the jump
  barely reads, the hands-up does); `moses_clap` (left hand slapping the staff fist: reads as clapping only from the
  front); `pharaoh_angry` (fists at the hips look like bowed arms; not used by the timeline).
- **tambourine_dance**: Miriam's arms are short (wrist reach 0.109), so the right palm can only meet the tambourine up
  front just left of her head; at each hit her right forearm crosses her face for ~2 frames. The mid-beat poses
  (tambourine high, right arm flung out) read well. `loopSeamVelErr` 0.036 is the strike itself: the same velocity
  change happens at every hit (measured 0.0365 at hit 2 and 3), not a seam fault.
- **staff_over_sea** ends with a gentle wind still on the beard / mantle (endVelMax 0.0055): the held last frame is
  still, so the beard simply stops; the 9 s clip covers the `sea_wind` FX.
- **Robes in deep poses**: kneel_bow −0.003, grab_tail −0.007 (robe front at the deepest bend, f24), walk_staff −0.006
  (hem at toe-off) — all above −0.008. Pharaoh's kilt in sad_sit / soggy_sit / wobble crouch stays above the page /
  floor (meshMinY ≥ 0.0007; wobble bodyMinY 0.011 is his crouched soles on the tilted floor's low side).
- The wheel spins only on the left (the right wheel is part of the chariot mesh, RIG.md §2).
- Hands are single-bone fingers: "pointing" is a straight hand.
- Not seen in Unity / on the phone (glTFast skinning, bone-scale blink, time-scaled accessors, prop show / hide).
