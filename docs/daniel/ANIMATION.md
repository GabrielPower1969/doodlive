# Daniel — skeletal animation (Animation role)

Owner: Animation. Binding contract: [CONTRACT.md](CONTRACT.md) §3 (bones) and §4 (clip names). Rig: [RIG.md](RIG.md).
Pipeline adapted from Ruth (`pipeline/ru_animate.py`): same clip-function method, IK, spring chains, export, verify and
contact sheet, plus a quadruped layer for the lions. Built 2026-11-14 with Blender 5.2.3.

```
python3 pipeline/da_animate.py all        # build + verify + contact sheet + freshness check (~3 min)
python3 pipeline/da_animate.py build      # 61 actions -> anim/{daniel,king,officer,lion,lion2}.glb + anim/clips.json (~30 s)
python3 pipeline/da_animate.py verify     # re-import the GLBs: animations, sampled joints, UV layer order, prop nodes
python3 pipeline/da_animate.py contact    # anim/contact_sheet.png (key poses + two pair rows)
python3 pipeline/da_animate.py fresh      # DA_FRESH OK / STALE: are the model files newer than the anim exports?
DA_PROBE="lion_roll_over:0,60,100:q3;king_toss_sigh:0:side" python3 pipeline/da_animate.py probe     # $DA_ANIM_WORK/probe.png
DA_PROBE="pair:king_hug:daniel_hug:0.11:30:front,close,top" python3 pipeline/da_animate.py probe     # two actors facing
DA_PROBE="pair:daniel_pet_lion:lion_roll_over:pet:12:close" python3 pipeline/da_animate.py probe     # mane 0.12 ahead
DA_ONLY=lion_,daniel_kneel blender -b --factory-startup --python pipeline/da_animate.py -- build      # subset, no export
```

Inputs (read fresh on every run): `model/characters.blend` (Characters; rigs, meshes, UVs), `model/babylon.glb` (Set,
renders only), `timeline.json` (Story, travel table), `model/regions_characters.json` (demo colours + `clipExpression`
decal per clip in renders). Options: `DA_NOSET=1` renders without the set, `DA_KY / DA_TB / DA_SS` the kneel geometry.
Work files: `$DA_ANIM_WORK` (default `/tmp/daniel_anim`); the temporary blend is deleted after export.

**Re-run rule.** The Set + sheet role may re-run `da_characters.py` (new sheet slots = new UVs, same bones and rest pose).
`all` ends with `fresh`; if it prints `STALE`, run `all` again. Checked at the end of this run: `DA_FRESH OK`.

## 1. Deliverables

| File | What |
|---|---|
| `assets/daniel/anim/daniel.glb` | Daniel mesh + skin (29 bones) + `daniel_eyelids`, 11 animations |
| `assets/daniel/anim/king.glb` | King + `king_ring` (node `ring`) + `king_eyelids`, 16 animations |
| `assets/daniel/anim/officer.glb` | Official + `officer_scroll` (node `scroll`) + `officer_eyelids`, 14 animations |
| `assets/daniel/anim/lion.glb` / `lion2.glb` | Lion / lioness + `*_eyelids`, 10 animations each (same list); lion2 keeps its own `lion2_paint.png` material |
| `assets/daniel/anim/clips.json` | Ruth schema per clip (action, char, clip, frames, seconds, loop, rootMotion false, markers {name: {frame, sec}}, loopSeamMaxErr, **seamStep / maxStep**, rootMaxOffset, props, notes, naturalSpeed + stride for locomotion, sampled joints, checks: `meshMinY`, `plantedDriftMax` or `naturalSpeed` + `stanceSlipMax`); roll_over adds `loopRange` [70, 150] + `loopRangeSeamErr`; top level `stage` (hug 0.11, pet-lion mane 0.12 ahead at 0.07 high, stamp point, king seat, kneel geometry), `travel` (every `to` move in the timeline: distance, time, needed vs natural speed, rate), `timelineMissing` (**empty**) |
| `assets/daniel/anim/contact_sheet.png` | Key poses of every clip in Babylon (demo colours, decal per `clipExpression`, markers in red) + two pair rows (king_hug + daniel_hug at 0.11; daniel_pet_lion + lion_roll_over with the mane 0.12 ahead) |

The anim GLBs carry the model GLBs' mesh, skin and rest pose (`export_rest_position_armature`), so Integration loads them
instead of `model/*.glb`. Character-local: root at the origin, facing +Z, sampled every frame at 30 fps, linear; every
action keys rotation + location + scale on every bone (blink = scale of `eyelids`). UV layers: page first (TEXCOORD_0,
in 0..1 for every primitive, checked in the binary), decal second. Verify: all 61 actions present in the GLBs, sampled
joints equal the build within 8e-6, `DA_VERIFY_MISSING` empty for all five.

## 2. Clips (30 fps; frame 0 = clip start; one-shots hold their last frame)

`meshMinY` = lowest deformed vertex over the clip (0 = the page; hidden scroll left out). Drift = largest slide of a
planted toe / paw tip in a non-locomotion clip (planned steps show up here: kneel, point, lion transitions). For
locomotion the natural speed and the stance slip (how fast a planted contact point moves in world space when the
director moves the actor at that speed; 0 = glued). Seam = joint step across the loop seam / largest step inside the
clip (all seams ≤ the largest inner step; frame N = frame 0 exactly, spring chains closed).

| Action | Frames | s | Loop | Markers (frame) | meshMinY | drift / speed | seam | Props |
|---|---:|---:|:---:|---|---:|---|---|---|
| `daniel_idle` | 150 | 5.00 | yes | — | -0.0034 | 0.0018 | 0.00033/0.00346 | — |
| `daniel_walk` | 34 | 1.13 | yes | contactL 0, contactR 17 | -0.0058 | **0.1147 u/s** (stance slip 0.0133) | 0.00843/0.01251 | — |
| `daniel_talk` | 96 | 3.20 | yes | — | 0.0009 | 0.0001 | 0.00535/0.02075 | — |
| `daniel_bow` | 56 | 1.87 | no | bow 24 | 0.0015 | 0.0 |  | — |
| `daniel_kneel_pray` | 80 | 2.67 | no | knees_down 30 | -0.005 | 0.0193 |  | — |
| `daniel_stand_up` | 54 | 1.80 | no | stand 34 | -0.0046 | 0.0205 |  | — |
| `daniel_calm_nod` | 48 | 1.60 | no | nod 16 | 0.0015 | 0.0 |  | — |
| `daniel_pet_lion` | 96 | 3.20 | yes | — | -0.0022 | 0.0 | 0.0035/0.00962 | — |
| `daniel_wave_up` | 48 | 1.60 | yes | — | -0.002 | 0.002 | 0.00781/0.00882 | — |
| `daniel_hug` | 90 | 3.00 | yes | — | 0.0007 | 0.0001 | 0.00047/0.00118 | — |
| `daniel_wave` | 48 | 1.60 | yes | — | 0.0009 | 0.0001 | 0.00797/0.00863 | — |
| `king_idle` | 150 | 5.00 | yes | — | 0.0003 | 0.0002 | 0.00039/0.00312 | — |
| `king_walk_sad` | 48 | 1.60 | yes | contactL 0, contactR 24 | -0.0089 | **0.0473 u/s** (stance slip 0.0163) | 0.0036/0.00829 | — |
| `king_talk` | 96 | 3.20 | yes | — | 0.0006 | 0.0001 | 0.00152/0.03383 | — |
| `king_talk_happy` | 96 | 3.20 | yes | — | 0.0004 | 0.0 | 0.00101/0.01129 | — |
| `king_proud` | 120 | 4.00 | yes | — | 0.0002 | 0.0013 | 0.0005/0.00068 | — |
| `king_stamp` | 60 | 2.00 | no | stamp 30 | -0.0032 | 0.0001 |  | — |
| `king_worried` | 90 | 3.00 | yes | — | 0.0002 | 0.0001 | 0.00207/0.00396 | — |
| `king_pace` | 128 | 4.27 | yes | turn1 32, turn2 96 | -0.0068 | 0.0694 | 0.01099/0.01205 | — |
| `king_head_in_hands` | 60 | 2.00 | no | sob 34 | -0.0033 | 0.0001 |  | — |
| `king_reach_out` | 48 | 1.60 | no | reach 22 | 0.0003 | 0.0056 |  | — |
| `king_toss_sigh` | 180 | 6.00 | yes | up 74, sit 132 | -0.008 (in front of the dais; robe/cape inside the steps) | 0.0316 | 0.00981/0.03411 | — |
| `king_run` | 22 | 0.73 | yes | contactL 0, contactR 11 | -0.0085 | **0.1818 u/s** (stance slip 0.0131) | 0.02107/0.02129 | — |
| `king_call_out` | 72 | 2.40 | yes | call1 14, call2 48 | -0.0029 | 0.0013 | 0.00127/0.01682 | — |
| `king_joy_jump` | 54 | 1.80 | no | takeoff 16, land 30 | -0.0065 | 0.0002 |  | — |
| `king_hug` | 90 | 3.00 | yes | — | -0.0001 | 0.0001 | 0.00133/0.00131 | — |
| `king_proclaim` | 96 | 3.20 | yes | — | 0.0016 | 0.0 | 0.00072/0.01047 | — |
| `officer_idle` | 150 | 5.00 | yes | — | 0.0009 | 0.0001 | 0.00206/0.00602 | — |
| `officer_walk` | 32 | 1.07 | yes | contactL 0, contactR 16 | -0.0002 | **0.1125 u/s** (stance slip 0.0137) | 0.00846/0.01066 | — |
| `officer_talk` | 96 | 3.20 | yes | — | 0.0011 | 0.0001 | 0.00058/0.01709 | — |
| `officer_fold_arms` | 40 | 1.33 | no | huff 14 | 0.0008 | 0.002 |  | — |
| `officer_stomp_walk` | 30 | 1.00 | yes | stompL 0, stompR 15 | 0.0005 | **0.1143 u/s** (stance slip 0.007) | 0.03181/0.03181 | — |
| `officer_grumble` | 72 | 2.40 | yes | stamp 44 | 0.0012 | 0.0001 | 0.00806/0.01413 | — |
| `officer_sly_idea` | 50 | 1.67 | no | idea 24 | 0.0004 | 0.0023 |  | — |
| `officer_rub_hands` | 40 | 1.33 | yes | — | 0.0017 | 0.0 | 0.00578/0.00591 | — |
| `officer_bow_flatter` | 96 | 3.20 | yes | bow1 22, bow2 70 | 0.0017 | 0.0003 | 0.00786/0.02811 | scroll |
| `officer_tiptoe` | 40 | 1.33 | yes | contactL 0, contactR 20 | 0.0045 | **0.0808 u/s** (stance slip 0.0) | 0.01356/0.01356 | — |
| `officer_peek` | 90 | 3.00 | yes | out 20, back 60 | -0.0001 | 0.0071 | 0.00914/0.0266 | — |
| `officer_point` | 36 | 1.20 | no | point 14 | 0.0017 | 0.0219 |  | — |
| `officer_scared_jump` | 40 | 1.33 | no | jump 6, land 26 | -0.004 | 0.0018 |  | — |
| `officer_run_away` | 18 | 0.60 | yes | contactL 0, contactR 9 | 0.0023 | **0.4167 u/s** (stance slip 0.0485) | 0.03768/0.05244 | — |
| `lion_idle` | 150 | 5.00 | yes | — | -0.0064 | 0.0 | 0.00061/0.00276 | — |
| `lion2_idle` | 150 | 5.00 | yes | — | -0.007 | 0.0001 | 0.0006/0.00264 | — |
| `lion_sleep` | 180 | 6.00 | yes | — | -0.0054 | 0.0 | 0.00043/0.0013 | — |
| `lion2_sleep` | 180 | 6.00 | yes | — | -0.007 | 0.0 | 0.00037/0.00119 | — |
| `lion_wake_up` | 96 | 3.20 | no | head_up 22, up 76 | -0.0054 | 0.0231 |  | — |
| `lion2_wake_up` | 96 | 3.20 | no | head_up 22, up 76 | -0.0065 | 0.0243 |  | — |
| `lion_roar` | 80 | 2.67 | no | roar 22 | 0.0008 | 0.0002 |  | — |
| `lion2_roar` | 80 | 2.67 | no | roar 22 | 0.0005 | 0.0002 |  | — |
| `lion_growl` | 90 | 3.00 | yes | — | 0.0008 | 0.0015 | 0.00105/0.00697 | — |
| `lion2_growl` | 90 | 3.00 | yes | — | 0.0005 | 0.0013 | 0.00098/0.00654 | — |
| `lion_walk` | 40 | 1.33 | yes | hindL 0, frontL 10, hindR 20, frontR 30 | 0.0008 | **0.0726 u/s** (stance slip 0.0093) | 0.0072/0.01025 | — |
| `lion2_walk` | 40 | 1.33 | yes | hindL 0, frontL 10, hindR 20, frontR 30 | 0.0005 | **0.0726 u/s** (stance slip 0.0143) | 0.00671/0.00976 | — |
| `lion_prowl` | 60 | 2.00 | yes | hindL 0, frontL 15, hindR 30, frontR 45 | 0.0008 | **0.0357 u/s** (stance slip 0.0) | 0.00749/0.01323 | — |
| `lion2_prowl` | 60 | 2.00 | yes | hindL 0, frontL 15, hindR 30, frontR 45 | 0.0005 | **0.0357 u/s** (stance slip 0.0028) | 0.00704/0.01303 | — |
| `lion_yawn` | 120 | 4.00 | no | stretch 26, yawn 84 | -0.0064 | 0.0316 |  | — |
| `lion2_yawn` | 120 | 4.00 | no | stretch 26, yawn 84 | -0.007 | 0.0292 |  | — |
| `lion_lie_down` | 72 | 2.40 | no | down 44 | -0.0054 | 0.0385 |  | — |
| `lion2_lie_down` | 72 | 2.40 | no | down 44 | -0.0066 | 0.0356 |  | — |
| `lion_roll_over` | 150 | 5.00 | no | onBack 52, loopStart 70, loopEnd 150 | -0.0064 | 0.0345 |  | — |
| `lion2_roll_over` | 150 | 5.00 | no | onBack 52, loopStart 70, loopEnd 150 | -0.007 | 0.0329 |  | — |

Kneels (`kneel_pray`, `pet_lion`, `stand_up`): knee joint 0.023 above the page, thigh back 14°, shin sloping up 30°,
toes tucked; meshMinY ≥ −0.005 (contract ≥ −0.008). The king's `walk_sad` (−0.0089 at a toe, one frame) and `run`
(−0.0085) brush the slipper toe 1 mm past the −0.008 line during the heel roll — kept, not visible on the paving.

### Acting notes

- **Daniel** — calm, warm, steady. `idle` breathes with one deep breath, weight shift, looks away and back, small
  content nod. `walk` even, ~106 steps/min. `talk` right palm opens, left hand to chest, nods on stressed syllables.
  `bow` hand to chest, bows, comes half up and holds. `kneel_pray` right knee then left, hands raised a little in front,
  palms up, head bowed, eyes closed (eyelids), holds. `stand_up` from that kneel. `calm_nod` one slow deep nod, right
  hand opens a little ("don't worry"). `pet_lion` kneeling, two long strokes per loop on the mane 0.12 ahead at 0.07
  height, left hand on his thigh, slow happy blinks. `wave_up` chin up, right arm high waving, little bounces on his
  toes. `hug` arms round the king's waist, cheek turned to his left, eyes closed. `wave` friendly goodbye.
- **King** — big, round, comic. `idle` hands on the belly (two pats + belly jiggle). `walk_sad` slow, head low, heavy.
  `talk` left hand on belly, right hand broad gestures. `talk_happy` arms open, chuckle pulses, belly bounce, head back.
  `proud` hands on hips, chin up, sway, heel-toe rock. `stamp` fist rises, presses down at chest height
  (`stamp` = contact f30 / 1.0 s), satisfied nod, ends hands on belly. `worried` hands on cheeks, rocking, fast blinks.
  `pace` **in place**: hands behind his back (cape lifted off them), three steps to his left, turn, three back, turn —
  a real ±0.035 path about the root. `head_in_hands` sinks, hands to the face, one sob, holds. `reach_out` step in,
  both hands out palms up, holds. `toss_sigh` sits on the dais' second step (0.027 high, 0.078 behind the KING mark),
  chin in hands, long sigh, flops back, gets up restless, sits again with a bump. `run` waddle-run, cape flying, belly
  bouncing. `call_out` hands cupped at the mouth, two calls per loop on tiptoe. `joy_jump` crouch, hop with arms flung
  up, belly bounce on landing. `hug` over Daniel, arms round his shoulder blades, eyes closed, rocking in phase with
  `daniel_hug`. `proclaim` **left** arm raised, **right** hand on Daniel's near shoulder (Daniel is on the king's right
  in S12, 0.14 away), booming syllables.
- **Official** — thin, shifty, cartoon. `idle` fingertips tapping, eyes and head darting with frozen holds. `walk`
  prim and busy. `talk` wagging hand, other hand on chest. `fold_arms` huff, arms folded, head turned away, holds.
  `stomp_walk` high knees, feet slammed flat, body jolts, fists. `grumble` shaking fists, muttering, one stamp.
  `sly_idea` chin rub, then "aha!" hand pops up beside his face (open hand: fingers are one bone), sly tilt, holds.
  `rub_hands` hunched glee. `bow_flatter` two deep oily bows per loop with a left-hand flourish, the scroll held to his
  chest (`officer/scroll` posed). `tiptoe` on the tips of his slippers, high knees, paws up, head turning. `peek` leans
  far out to his left, rubs hands, ducks back, peeks again. `point` lean in, right arm straight at Daniel, left hand on
  hip, holds. `scared_jump` straight up 0.085, legs cycling twice in the air, arms flung up, lands crouched to run.
  `run_away` fast high-kneed panic, both arms flailing overhead, jaw open.
- **Lions** (`lion` and `lion2` share every clip; distances scale with the rig) — soft and cat-like. `idle` sits (rump
  on the page, front legs straight, hind feet flat, tail round the side), looks about with head tilts, tail-tip flicks,
  ear twitches. `sleep` lying curled in a C to its left, chin on the paw, tail round the front, slow 3 s breaths, a
  tiny snore in the jaw, one ear twitch. `wake_up` ear twitch, head lifts, sleepy look round and a little shake, front
  legs push up then the rump (paws step, not slide); ends standing. `roar` draws back, then thrusts the head forward
  (not up — the mane would hide the face) with the jaw at 28°, mane shakes, chest up, tail up stiff; closes with a
  head shake and a huff; ends standing. `growl` head low, lip curl tremble, slow rock side to side, each front paw
  lifted and set down on the same spot. `walk` lateral four-beat (LH, LF, RH, RF), duty 0.62. `prowl` low, head down,
  high careful paw lifts, slow low tail swish. `yawn` cat stretch (front paws step forward, chest down, rump up), back
  up, sits, huge yawn (jaw 36°, ears back), lip smacks; ends sitting = `idle` frame 0. `lie_down` front legs fold, rump
  down, head onto the paws with a sigh, holds. `roll_over` (the comic high point) from sitting: flops down, rolls onto
  its back (root roll 168°, front propped on the mane like a pillow), paws folded in the air, head tipped toward the
  viewer, blissful; frames 70..150 are a seamless wriggle loop (back scratch, paws kneading the air, tail wagging along
  the floor, one sleepy peek). The ground contact of every lying / sitting / rolled pose is solved per frame
  (`settle`: a skinned proxy of the body finds the lowest point), so nothing floats or sinks.

## 3. Travel speeds (in-place locomotion; the director moves the actor)

Natural speed = stride / stance time; moving the actor at this speed keeps the planted feet / paws still on the page.

| Clip | Stride | Duty | Natural speed |
|---|---:|---:|---:|
| `daniel_walk` | 0.078 | 0.60 | **0.115 u/s** |
| `king_walk_sad` | 0.050 | 0.66 | **0.047 u/s** |
| `king_run` | 0.060 | 0.45 | **0.182 u/s** |
| `officer_walk` | 0.072 | 0.60 | **0.112 u/s** |
| `officer_stomp_walk` | 0.064 | 0.56 | **0.114 u/s** |
| `officer_tiptoe` | 0.056 | 0.52 | **0.081 u/s** |
| `officer_run_away` | 0.100 | 0.40 | **0.417 u/s** |
| `lion_walk` / `lion2_walk` | 0.060 | 0.62 | **0.073 u/s** |
| `lion_prowl` / `lion2_prowl` | 0.050 | 0.70 | **0.036 u/s** |
| `king_pace` | in place (own ±0.035 path) | | 0 |

Every `to` move in the current `timeline.json` (`clips.json travel`; "time" = until the actor's next clip; rate =
needed / natural):

| t | Clip | Dist | Time | Needs u/s | Natural | Rate |
|---:|---|---:|---:|---:|---:|---:|
| 33.58 | `officer_stomp_walk` | 0.33 | 1.4 | 0.236 | 0.114 | 2.06 |
| 34.18 | `daniel_walk` | 0.165 | 37.86 | 0.004 | 0.115 | 0.03 |
| 51.61 | `officer_walk` | 0.33 | 2.4 | 0.137 | 0.112 | 1.22 |
| 72.04 | `officer_idle` (glide: no locomotion clip) | 0.367 | 25.81 | 0.014 | — | — |
| 72.04 | `daniel_walk` | 0.156 | 12.56 | 0.012 | 0.115 | 0.1 |
| 97.85 | `officer_tiptoe` | 0.534 | 2.6 | 0.205 | 0.081 | 2.54 |
| 107.51 | `officer_stomp_walk` | 0.394 | 1.0 | 0.394 | 0.114 | 3.45 |
| 109.71 | `daniel_idle` (glide: no locomotion clip) | 0.221 | 26.67 | 0.008 | — | — |
| 136.38 | `daniel_walk` | 0.407 | 13.31 | 0.031 | 0.115 | 0.27 |
| 136.38 | `king_walk_sad` | 0.383 | 7.62 | 0.05 | 0.047 | 1.06 |
| 136.98 | `officer_walk` | 0.416 | 24.77 | 0.017 | 0.112 | 0.15 |
| 154.15 | `daniel_walk` | 0.256 | 7.6 | 0.034 | 0.115 | 0.3 |
| 161.75 | `king_idle` (glide: no locomotion clip) | 0.393 | 24.59 | 0.016 | — | — |
| 161.75 | `officer_idle` (glide: no locomotion clip) | 0.526 | 56.11 | 0.009 | — | — |
| 161.75 | `lion_prowl` | 0.13 | 12.18 | 0.011 | 0.036 | 0.31 |
| 162.05 | `lion2_prowl` | 0.082 | 12.48 | 0.007 | 0.036 | 0.2 |
| 197.79 | `king_run` | 0.393 | 3.0 | 0.131 | 0.182 | 0.72 |
| 217.86 | `officer_idle` (glide: no locomotion clip) | 0.361 | 8.74 | 0.041 | — | — |
| 218.66 | `daniel_walk` | 0.298 | 2.8 | 0.107 | 0.115 | 0.93 |
| 226.6 | `officer_tiptoe` | 0.102 | 4.19 | 0.024 | 0.081 | 0.3 |
| 232.87 | `officer_run_away` | 0.241 | None | — | 0.417 | — |
| 234.27 | `king_proclaim` (glide: no locomotion clip) | 0.104 | None | — | — | — |
| 234.27 | `daniel_idle` (glide: no locomotion clip) | 0.253 | 9.49 | 0.027 | — | — |

Recommendation (as Ruth): move at the natural speed (or scale the clip rate within about 0.6–1.6×) and switch to the
next clip on arrival. Outside that range: **officer stomp_walk at 33.58 (2.1×) and 107.51 (3.5×), tiptoe at 97.85
(2.5×)** — the story gives the official 1.0–2.6 s for 0.33–0.53; Story should give those moves ~3–5 s or Integration
lets him arrive late. Rates below 0.6 just mean the walk ends early (switch to idle on arrival). Glides (idle with
`to`): officer 72.04 (0.37 in 25.8 s), Daniel 109.71 (0.22), king 161.75 (0.39), officer 161.75 / 217.86, king
proclaim 234.27, Daniel 234.27 — insert a walk or teleport off-camera.

## 4. Staging the clips assume (tell Story / Integration)

1. **Hug: 0.11 between the roots** (`stage.hugDistance`; the brief allows 0.10–0.13). The timeline puts the king at
   KING_DEN (0.05, 0.08) and Daniel at (0.13, 0.06): **0.082** — the king's belly and Daniel's robe would intersect.
   Move Daniel's hug mark to about (0.16, 0.06). `king_hug` and `daniel_hug` share length (90 f) and rocking phase:
   start them on the same frame (the timeline does, t 221.46).
2. **pet_lion: the hand strokes a mane 0.12 in front of Daniel at 0.07 height** = the lion lying / rolled over. With the
   lion facing Daniel in `roll_over`, the roots must be **0.207 apart** (contact sheet pair row). The timeline has
   Daniel at DEN_IN (0.36, −0.13) and the lion after its prowl at (0.44, −0.09): **0.089** — the lion's head would sit
   in Daniel's knees. Suggest, inside the den (centre (0.38, −0.17), inner radius 0.16): Daniel kneels at about
   (0.25, −0.08) just inside the opening, the lion prowls to about (0.44, −0.17), facing each other (0.21 apart, the
   rolled-over rump stays just inside the wall).
3. **King stamp**: the ring presses at `stage.stampAt` = (−0.01, 0.24, 0.092) king-local (his chest height, 0.09 in
   front); marker `stamp` = f30 / 1.0 s after the act. S05: `seal_stamp` at act + 0.9 s (0.1 s early, fine). S08: act
   at dt 5.6 → contact 6.6, seal + sfx at dt 6.5 (fine) — but there the stone is ~0.24 from KING_DEN, so he stamps in
   the air toward the den; a walk of ~0.15 toward the stone first (or a seal effect that flies over) would sell it.
4. **toss_sigh** is authored at the KING mark facing the viewer (the dais' second step 0.078 behind him). Played at
   (−0.05, −0.30) (the timeline's position at 191.47) it still lands on the same step (the dais is wider than 0.10).
5. **roll_over → sleep** (197.79): a 0.25 s blend flips the lion from its back to the curled sleep in one quarter
   second (comic, but abrupt). A 0.6–0.8 s blend reads better; or hold `roll_over` (it loops 70..150).
6. **Faces**: the lions' jaw only moves the chin and lower cheek puffs (RIG.md); the open mouth is the decal. The
   suggested `clipExpression` maps `yawn` → `sleepy` (closed "w" mouth): with it the yawn does not read as a yawn.
   Use `fierce`'s open mouth only for the `yawn` marker window (f 70–94) or add a `yawn` decal (Characters).
7. Props: `officer/scroll` is posed only in `bow_flatter` (timeline shows it 54.01–73.04, matching); `king/ring` is
   always shown.

## 5. How the motion is made

As Ruth §6: each clip is a function frame → channels in design axes, Catmull-Rom keys (wrapped for loops), leg IK with
heel / ball / toe contact, arm IK with targets in root space or any bone's space (`head` for cheeks / cupped hands /
chin, `chest` for folded arms and hands behind the back), irregular blinks, syllable jaw rhythms with beats driving
nods and hand gestures, eased one-shot phases with anticipation, overshoot and settle, pulse trains for laughs, sobs
and stamps. New in Daniel:

- **Rolling foot contact**: the human gait now pivots the ankle target about the heel (toes up) or the ball (heel up),
  so a planted foot does not skate while it rolls (stance slip ≤ 0.016 u/s, was ~0.06–0.19 with Ruth's gait).
- **Quadruped legs** (`ik_quad`): the paw / hind-foot bone gets a pitch, the paw TIP is placed exactly on its target
  and the upper + lower bone are solved by two-bone IK (front elbow bends back, hind knee forward). `quad_gait`:
  lateral four-beat sequence, stance slides back at constant speed, heel peels up at the end of the stance (tip stays),
  swing lifts with wrist / hock flexion. Planted paws: drift 0.0000–0.0015 in every standing clip.
- **Poses** `sit_pose`, `lie_pose`, `curl_pose`, `back_pose` blended per channel group (`mix_groups`: head, front legs,
  hind legs, tail, body each on their own ease) with paw step lifts so paws step rather than slide.
- **Settle**: a 1,500-vertex skinned proxy of the body (linear-blend skinning in python from the solved bones) finds the
  lowest point of chosen bones per frame and moves `hips` or `root` so it touches the page (sit: rump; lie: belly;
  roll: whole body). This is what keeps the rolled-over lion on the floor.
- **Spring chains** (k / damping / gravity / max lag): Daniel `hair1` (90 / 8 / 0.25 / 25°), `sash1-2` (80 / 7 / 0.30 /
  28°); king `cape1-2` (60 / 6.5 / 0.30 / 32°) and `belly` (170 / 5 / 0 / 10°, plus keyed `belly.ty` / `belly.s` for
  laughs, pats and landings); official `robe1` (85 / 7 / 0.30 / 22°); lions `tail1-4` (75 / 6.5 / 0 / 35°), `earL/R`
  (230 / 9 / 0 / 12°), `mane` (130 / 6 / 0 / 14°, lion only). Loops simulate 3 cycles and close exactly; roll_over's
  loop range 70..150 is closed the same way (`loopRangeSeamErr` 0.0).

## 6. Rough edges and things not done (honest list)

- **Lion eyelids do not show (Characters).** `lion_eyelids` / `lion2_eyelids` sit 5–21 mm *behind* the eyes inside the
  head (eyelid-bone local z −0.005…−0.021; Daniel's are at 0…+0.004): scaling `eyelids` Y to 12.78 changes nothing
  visible (rendered close-ups, 2026-11-14). Every lion blink, the closed eyes of `sleep`, `yawn` and `roll_over` are
  keyed correctly but invisible until Characters moves the lid strips onto the eye surface; meanwhile the decals
  (`sleepy`, `blissful`) carry the look.
- **lion2_eyelids had two stray vertices** (indices 0 and 60, left ~0.08 behind the eyes) drawing two long thin lines
  through the head whenever it turns. `da_animate.py` snaps such outliers onto their strip at load (`DA_FIX` line in
  the log) so the anim GLB is clean; the model GLB still has them (Characters should fix the source; the workaround is
  then a no-op).
- Not seen in Unity or on a phone (glTFast skinning, bone-scale blink, the roll's 168° root rotation blends).
- `king_pace`: the turns are stepping pivots with ~0.07 total foot slip spread over the two 24-frame turns; the straight
  legs are planted. Hands behind the back sit under the lifted cape; the cape is not collision-solved.
- `king_toss_sigh`: the robe below his seat and the cape go inside the dais steps (hidden by the steps; only −0.008 in
  front of the first step edge, a cape corner). Checked in the set render only from the side and 3/4.
- Hugs are not collision-solved: hands reach just past the partner's back at the top view; heads cheek to cheek.
- Fingers are one bone per hand: no index finger for `point` / `sly_idea` (open hand), no tight fists.
- `officer_scared_jump` leaves the contact cell at the top of the jump (0.085 high) — intended.
- Lions: the mane is half on `head`, so big head turns bend its back half (RIG.md §9); the roar keeps the head level
  for that reason. The male lion on its back props its shoulders on the mane (by design of the settle).
