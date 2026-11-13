# Esther — skeletal animation (Animation role)

Owner: Animation. Binding contract: [CONTRACT.md](CONTRACT.md) §3 (bones) and §4 (clip names). Rig: [RIG.md](RIG.md).
Stage: [SET.md](SET.md). Pipeline adapted from David & Goliath ([../david-goliath/ANIMATION.md](../david-goliath/ANIMATION.md),
`pipeline/dg_animate.py`). Built 2026-11-14 with Blender 5.2.3.

```
python3 pipeline/es_animate.py all        # build + verify + contact sheet (~6 min, most of it the contact renders)
python3 pipeline/es_animate.py build      # 55 actions -> anim/{esther,king,haman,guard1,guard2}.glb + anim/clips.json with checks (~1 min)
python3 pipeline/es_animate.py verify     # re-import the GLBs: animations, frame ranges, sampled joints, UV layer order
python3 pipeline/es_animate.py contact    # anim/contact_sheet.png
ES_PROBE="esther_pray:0,45:side;scene:sceptre" python3 pipeline/es_animate.py probe   # work renders -> $ES_ANIM_WORK/probe.png
ES_PROBE="scene:drag:0:grab;scene:drag:12" python3 pipeline/es_animate.py probe   # S10 grab moment / exit at the story marks
ES_ONLY=king_sit python3 ...  (Blender build with ES_ONLY=prefix,prefix bakes + checks a subset without exporting)
```

Inputs: `model/characters.blend` (Characters role), `model/palace.glb` (Set role, renders only), `timeline.json` (Story),
`faces.json` (Integration; decal per clip in renders), `model/regions_characters.json` (demo colours in renders).
Intermediates: `$ES_ANIM_WORK`, default `$ES_WORK/anim` (`ES_WORK` default `/tmp/es_work`).

## 1. Deliverables

| File | What |
|---|---|
| `assets/esther/anim/esther.glb` | Esther mesh + skin (32 bones) + necklace / diadem / eyelids, 14 glTF animations |
| `assets/esther/anim/king.glb` | King + crown / sceptre / ring / eyelids, 10 animations |
| `assets/esther/anim/haman.glb` | Haman (rework mesh: belly, nose, tall cap) + cap / plume / ring / eyelids, 23 animations |
| `assets/esther/anim/guard1.glb`, `guard2.glb` | Guards + cap / spear / eyelids, 4 animations each (`idle march grab drag`); built automatically whenever `characters.blend` has `guard1_rig` / `guard2_rig` |
| `assets/esther/anim/clips.json` | Per clip (D&G schema): action, char, clip, frames, seconds, loop, rootMotion (false), markers {name: {frame, sec}} (a repeated event also has `frames` / `secs`: `haman_fume` `stomp`), loopSeamMaxErr, notes, naturalSpeed (locomotion), `backwards: true` (clip travels backwards relative to facing: `haman_led_away`, `haman_dragged`; the director turns the actor 180° from its travel), sampled joints, checks, `pendingChars` (cast members not in characters.blend yet); plus `stage` (marks the clips were fitted to) and `timelineMissing` (empty) |
| `assets/esther/anim/contact_sheet.png` | Key poses of every clip in the palace (demo colours by region, face decal per `faces.json`; markers in red, `*` = extra clip) |

The anim GLBs carry the model GLBs' mesh, skin and rest pose (`export_rest_position_armature`), so Integration can load
them instead of `model/*.glb`. Character-local: root at the origin, facing +Z, sampled every frame at 30 fps, linear.
Every action keys rotation + location + **scale** on every bone (the blink is a scale of `eyelids`).

**UV layer order (fixed in the export, 2026-11-14).** `model/*.glb` / `characters.blend` hold the UV maps as
`['decal', 'UVMap']`, so TEXCOORD_0 was the face decal (range -3..4) and TEXCOORD_1 the page. The anim GLBs rebuild the
layers as `UVMap` (page) first, `decal` second (`fix_uv_order()`, page layer found by name, else by the 0..1 range), as
David & Goliath and DGPaperLit expect. `verify` reads the GLB binary: TEXCOORD_0 lies in 0..1 for every primitive of
all three characters (`uv0InUnitSquare=True`), TEXCOORD_1 is the decal (body -3..4, props parked at (-1, 2)).
The model GLBs themselves are the Characters role's and are unchanged.

## 2. Clips (30 fps; frame 0 = clip start; one-shots hold their last frame)

Checks: `meshMinY` = lowest deformed vertex over the clip (0 = the page; the king's 0 = the dais top);
`drift` = largest horizontal slide of a planted toe (non-locomotion clips) — for locomotion the column gives the
natural speed instead. Loop seams are 0.000000 for every loop (frame N is frame 0; the spring chains close exactly).

| Action | Frames | s | Loop | Markers (frame / s) | meshMinY | drift / speed |
|---|---:|---:|:---:|---|---:|---:|
| `esther_idle` | 150 | 5.00 | yes | — | -0.0025 | 0.0018 |
| `esther_walk` | 36 | 1.20 | yes | contactL 0, contactR 18 / 0.60 | -0.0035 | **0.104 u/s** |
| `esther_talk` | 90 | 3.00 | yes | — | 0.0011 | 0.0001 |
| `esther_worried` | 120 | 4.00 | yes | — | -0.0026 | 0.0016 |
| `esther_pray` | 90 | 3.00 | yes | — | -0.0056 | 0.0 |
| `esther_kneel` **extra** | 36 | 1.20 | no | knees_down 24 / 0.80 | -0.0052 | (planned step) |
| `esther_rise_brave` | 84 | 2.80 | no | stand 46 / 1.53, chin_up 62 / 2.07 | -0.0072 | (planned step) |
| `esther_climb` | 48 | 1.60 | yes | contactL 0, contactR 24 / 0.80 | -0.0031 | **0.047 u/s** |
| `esther_bow` | 66 | 2.20 | no | down 34 / 1.13 | -0.0082 | 0.054 (foot glides back) |
| `esther_touch_sceptre` | 66 | 2.20 | no | **touch 36 / 1.20** | -0.0072 | 0.054 (foot glides back in) |
| `esther_invite` | 60 | 2.00 | no | open 24 / 0.80 | 0.0016 | 0.006 |
| `esther_point` | 45 | 1.50 | no | point 14 / 0.47 | 0.0016 | 0.012 (small lean step) |
| `esther_joy` | 72 | 2.40 | yes | twirl 8 / 0.27, hop 50 / 1.67 | -0.0029 | 0.055 (toe pivot) |
| `esther_wave` | 48 | 1.60 | yes | — | 0.0001 | 0.0 |
| `king_sit_idle` | 150 | 5.00 | yes | — | 0.0008 | 0.0 |
| `king_sit_talk` | 96 | 3.20 | yes | — | 0.0008 | 0.0 |
| `king_sit_listen` | 120 | 4.00 | yes | — | 0.0008 | 0.0 |
| `king_give_ring` | 60 | 2.00 | no | **release 30 / 1.00** | 0.0008 | 0.0 |
| `king_extend_sceptre` | 60 | 2.00 | no | **out 30 / 1.00** | 0.0008 | 0.0 |
| `king_sit_smile` | 120 | 4.00 | yes | — | 0.0008 | 0.0 |
| `king_stand_angry` | 54 | 1.80 | no | up 26 / 0.87 | -0.0016 | 0.009 |
| `king_angry_idle` | 90 | 3.00 | yes | — | 0.0016 | 0.0002 |
| `king_point_away` | 45 | 1.50 | no | point 16 / 0.53 | 0.0021 | 0.0001 |
| `king_celebrate` | 60 | 2.00 | yes | — | -0.0057 | 0.0001 |
| `haman_idle` | 120 | 4.00 | yes | — | 0.0006 | 0.0021 |
| `haman_strut` | 30 | 1.00 | yes | contactL 0, contactR 15 / 0.50 | 0.0006 | **0.125 u/s** |
| `haman_walk` **extra** | 24 | 0.80 | yes | contactL 0, contactR 12 / 0.40 | 0.0006 | **0.182 u/s** |
| `haman_talk` | 90 | 3.00 | yes | — | 0.0018 | 0.0 |
| `haman_demand` | 45 | 1.50 | no | wide 16 / 0.53 | 0.0006 | 0.005 |
| `haman_whisper` | 90 | 3.00 | yes | — | 0.0009 | 0.0 |
| `haman_take_ring` | 45 | 1.50 | no | **grab 20 / 0.67** | 0.0018 | 0.016 (lean step) |
| `haman_smug` | 120 | 4.00 | yes | — | 0.0011 | 0.002 |
| `haman_shock` | 36 | 1.20 | no | **slip 10 / 0.33** | -0.0029 | 0.002 |
| `haman_cower` | 48 | 1.60 | yes | — | 0.0006 | 0.0 |
| `haman_led_away` | 36 | 1.20 | yes | contactL 0, contactR 18 / 0.60 | -0.0002 | **0.067 u/s, backwards** |
| `haman_parade` | 44 | 1.47 | yes | contactL 0, contactR 22 / 0.73 | 0.0002 | **0.068 u/s** |
| `haman_preen` | 84 | 2.80 | no | admire 18, huff 42, cap 64 | 0.0006 | 0.0005 |
| `haman_laugh_proud` | 72 | 2.40 | yes | — | 0.0006 | 0.0001 |
| `haman_fume` | 60 | 2.00 | yes | **stomp 6 / 20 / 33 / 47** (0.20 / 0.67 / 1.10 / 1.57) | 0.0006 | 0.002 |
| `haman_scheme` | 60 | 2.00 | yes | — | 0.0006 | 0.0 |
| `haman_boast` | 60 | 2.00 | yes | hopL 6, hopR 18, jab 31, open 48 | -0.0008 | 0.007 (hops) |
| `haman_daydream` | 180 | 6.00 | no | robe 32, ride 60, shout 114, wide 154 | -0.0010 | 0.007 |
| `haman_stunned` | 60 | 2.00 | no | **pop 8 / 0.27** | 0.0006 | 0.002 |
| `haman_sulk` | 48 | 1.60 | yes | contactL 0, contactR 24 / 0.80 | 0.0002 | **0.061 u/s** |
| `haman_sulk_shout` | 72 | 2.40 | yes | shout 31 / 1.03 | 0.0006 | 0.0 |
| `haman_beg` | 48 | 1.60 | yes | please 22 / 0.73 | -0.0015 | **0.025 u/s** (knee shuffle) |
| `haman_dragged` | 36 | 1.20 | yes | — | 0.0061 | **0.160 u/s, backwards** (sync value) |
| `guard1_idle`, `guard2_idle` | 120 | 4.00 | yes | — | 0.0015 | 0.0001 |
| `guard1_march`, `guard2_march` | 20 | 0.67 | yes | contactL 0, contactR 10 / 0.33 | -0.0011 | **0.273 u/s** |
| `guard1_grab`, `guard2_grab` | 36 | 1.20 | no | **grab 20 / 0.67** | 0.0005 / 0.0007 | 0.0008 |
| `guard1_drag`, `guard2_drag` | 28 | 0.93 | yes | contactL 0, contactR 14 / 0.47 | -0.0033 | **0.160 u/s** (= haman_dragged) |

GLB round trip (`verify`, 2026-11-14 rework): 55 animations, nothing missing against §4 + HAMAN-REWORK §3, joints at frames 0,
N/2, N equal the build within 5e-5 units (the spine squash / stretch adds a little float noise), TEXCOORD_0 in 0..1 for every primitive. `timeline.json` `requestedClips` is empty; every `acting` clip exists (`timelineMissing []`).

### Acting notes (what each clip does)

- **Esther** — graceful. `idle`: breathes, weight L→R→L, the neck leads a look round and the head follows, blinks
  at frames 22 / 61+69 (double) / 120, fingers stir. `walk`: 100 steps/min, soft hip drop, chest counter-turn, arms
  swing with lagging forearms and wrists. `talk`: irregular syllables with word gaps; nods and the right hand's
  palm-up gesture open on the stressed ones. `worried`: small — shoulders up, chest sunk, head down, hands together
  at the chest and wringing, quick glances with holds, faster breathing, four blinks. `pray`: upright kneel, hands
  folded at the chest, head bowed, slow deep breaths. `rise_brave`: breath in, hands part, left foot steps forward,
  pushes up, feet together, then chin up, chest open, shoulders back, soft fists; holds. `climb`: careful slow steps,
  knees high, both hands gathering the skirt, looks down at the step and up at the king. `bow`: curtsey (rise and
  breath, right foot glides behind, knees bend, torso and head bow, skirt held); holds low. `touch_sceptre`: rises,
  reaches up with the left hand to the knob, holds, draws both hands to her chest with a sigh. `invite`: draws in,
  sweeps both arms open palms-up, settles with the right hand still offering. `point`: anticipation, snaps the right
  arm out straight, leans in, chin up; left fist. `joy`: dip, one twirl on her toes (arms out; braid and cape fly
  out and catch up), dip, hop with both arms up. `wave`: right hand by her head, forearm sways twice per loop with
  the wrist late, body sways and bounces.
- **King** — slow and heavy, kind when he smiles. Seated clips share one sitting pose; `sit_idle` has a slow sigh
  and slow heavy blinks (1.4× longer), a drum of the fingers on the knee; `sit_talk` lifts the left hand palm-up on
  the beats; `sit_listen` leans in, tilts the head and strokes the beard, "hmm" nods; `give_ring` leans back bored
  (half-lidded) and holds the right hand out; `extend_sceptre` leans back surprised, then leans forward and lowers
  the sceptre knob to Esther with a small overshoot and keeps it; `sit_smile` warm tilt and a three-bounce chuckle;
  `stand_angry` leans forward, pushes up onto his feet in front of the seat, chest swells, fists; `angry_idle` heaving
  breaths, fists clench, a snort; `point_away` flings the left arm out to his left, flat hand; `celebrate` both arms
  up, sceptre high, heavy knee bounces, laughing.
- **Haman** — comic, bouncy, never scary. `idle` rubs his hands, bounces on his toes twice, sly tilts, one slow sly
  blink; `strut` chest out, leaning back, knees high, big hip bounce, stiff wide arm swing with floppy hands;
  `walk` (extra) quick sneaky tiptoe scurry, hunched, rubbing hands; `talk` shrugs and palms-up on the beats, head
  waggle; `demand` crouch then springs onto his toes with arms thrown up in a V; `whisper` leans to his right and
  forward, hand cupped at his mouth, murmuring jaw, a sneaky glance back; `take_ring` snatches with the left hand,
  pulls it to his chest, gleeful hop; `smug` arms crossed, chin up, half-shut lids, taps his right foot, slow nod;
  `shock` dips, jumps high (stretched), arms fling up, cap pops high and slips back askew, lands squashed and
  knock-kneed; `cower` shrunk (squashed spine), knees together, hands up before his face, shivering fast, peeks out;
  `led_away` crouched backward shuffle, big glances over his shoulder.
- **Haman rework (HAMAN-REWORK.md, 2026-11-14)** — a pompous, cowardly peacock played big: anticipation, overshoot,
  squash and stretch through the spine, holds on the funny poses, uneven rhythms. Pushed: `strut` (belly first, nose
  up, snappy stretch-squash bounce, wider arms), `demand` (deeper crouch, stretch on the spring, overshoot bounce into
  the hold), `smug` (leans back belly-out, "mm-HM" nod with a squash, bigger foot tap), `shock` / `cower` /
  `led_away` (see above). New:
  `parade` exaggerated proud march, high knees, a snappy bounce (stretch at the top, squash on contact), stiff wide arm
  swing with floppy hands, hips and shoulders rolling; `preen` lifts the ring hand and admires it half-lidded, huffs on
  it, polishes it on his chest in circles, tweaks his cap, plants both fists on his hips (ends in the `laugh_proud` /
  `smug` stance); `laugh_proud` fists on hips, head thrown back, "HA-ha-ha-ha" bursts that slow and fade, a gasping
  breath in, another burst; the jaw opens with the laugh (the only new clip that keys the jaw beyond a gape: the
  voice RMS drives talk); `fume` fists shaking beside his head, hunched glare, four alternating stamps (knee high,
  slam, squash, fists pump down; markers `stomp`), trembling between; `scheme` hunched to the viewer, fast hand rub,
  head cocked with the eyes sliding sideways, uneven giggle bounces; `boast` two skip-hops, thumb jabs at his chest,
  arms flung open on his toes; `daydream` (6 s) dreamy clasp, sweeps an imaginary robe over his shoulders with a
  shimmy, gallops bow-legged on the imaginary horse, cups his mouth for the herald shout, anticipation dip, arms flung
  wide and held; `stunned` freezes in that pose, jaw drops, cap pops straight up (marker `pop`) and drops back,
  arms go limp and swing, totters on his heels, ends slumped with two slow blinks; `sulk` slouched trudge, scuffing
  feet, heavy drop on every step, right fist forward on the reins with a jerk, left arm dangling, one big sigh;
  `sulk_shout` breathes in, cups the left hand to his mouth, a grudging shout, then deflates with a head shake;
  `beg` on his knees, clasped hands raised, uneven please-please-PLEASE bows, wet-puppy head tilt, sobbing shoulders,
  shuffles forward on alternating knees; `dragged` upper arms held out at the sides at guard-hand height, forearms and
  hands flailing, legs kicking (L, R, L, R at different strengths), heels scraping in front, leaning back, head
  thrashing; cap askew.
- **Guards** — stern, crisp, few moves. The grabbing (inner) hand is the one without the spear: guard1 grabs with L (spear R), guard2 with R (spear L). `idle` at attention, spear upright,
  slow look round, regrips once; `march` brisk, knees up, crisp heel strikes, stiff inner-arm swing, spear bobbing;
  `grab` stamps the inner foot, leans in, clamps the inner hand on Haman's upper arm (fitted to the S10 marks, see §4;
  marker `grab`), one tug, holds; `drag` leans into the pull, inner hand on Haman's arm (guard1 behind it, guard2 in
  front of it, see §4), a tug on every step.

## 3. Natural speeds (in-place locomotion; the director moves the actor)

Speed = stride L / stance time (L / (duty × clip seconds)). Timeline needs (current `timeline.json`, distance /
time until the actor's next clip):

| Clip | Stride L | Duty | Natural | Timeline needs |
|---|---:|---:|---:|---|
| `esther_walk` | 0.075 | 0.60 | **0.104 u/s** | S02 0.209 in 8.1 s → 0.026; S09 0.228 in 2.1 s → 0.109 |
| `esther_climb` | 0.050 | 0.66 | **0.047 u/s** | S07 0.268 in 11.1 s → 0.024 |
| `haman_strut` | 0.070 | 0.56 | **0.125 u/s** | S03 0.126 in 1.3 s → 0.097; S09 0.394 in 2.0 s → 0.197 |
| `haman_walk` | 0.080 | 0.55 | **0.182 u/s** | S04 0.310 in 1.7 s → 0.183 |
| `haman_led_away` | 0.050 | 0.62 | **0.067 u/s backward** | not used by the timeline any more (S10 uses `dragged`) |
| `haman_parade` | 0.056 | 0.56 | **0.068 u/s** | S03 0.171 in 3.3 s → 0.052 |
| `haman_sulk` | 0.064 | 0.66 | **0.061 u/s** | S08d 0.580 in 8.1 s → 0.071 |
| `haman_beg` | 0.024 | 0.60 | **0.025 u/s** (knee shuffle) | S10 0.161 in 8.6 s → 0.019 |
| `haman_dragged` | (0.0576) | 0.60 | **0.160 u/s backward**, fixed sync value | S10 exit ≈ 0.80 (Integration: ~5 s) |
| `guard*_march` | 0.100 | 0.55 | **0.273 u/s** | S10 (new marks) guard2 ~0.54 in 2.6 s → 0.21; guard1 ~0.35 in 2.6 s → 0.13 |
| `guard*_drag` | 0.0448 | 0.60 | **0.160 u/s** (= haman_dragged) | S10 exit ≈ 0.80 |

Recommendation for Integration: move at the natural speed (or scale the clip rate to the needed speed within about
0.6–1.6×) and switch to the idle when the mark is reached, so feet do not skate. Note `esther wave` in S12 also has a
`to` (0.108 away): she would glide while waving unless a short `walk` is inserted.

## 4. Staging the clips assume (from SET.md / timeline marks)

- **King seated**: root on the dais top under the throne mark (0, −0.30), facing his target. Hips offset
  (0, −0.036, −0.012) → hip joints 0.154 above the root; the robe under the buttocks sits 0.010–0.015 into the
  cushion (top 0.116 above the root) — `checks.seatGap` (`[-0.015, -0.010]`); feet flat on the dais at z +0.078.
- **King standing** (`stand_angry`, `angry_idle`, `point_away`, `celebrate`): feet and hips **0.088 forward of the
  root** (in front of the seat edge at +0.074, toes over the top step edge at −0.19 by about 1 cm). He rises from
  the throne without root motion; going back to `sit_smile` (S12) blends him back onto the seat in 0.25 s.
- **Sceptre (S08)**: at the end of `king_extend_sceptre` the knob (`sceptreTip`) is at king-local
  **(−0.040, 0.270, 0.128)** (staff tilted toward Esther; measured −0.04, 0.27, 0.128). `esther_touch_sceptre` reaches
  her left hand to that point computed for Esther at the foot of the steps (0, −0.12) facing the king (yaw 180) and
  the king at the throne facing her (yaw 0). Probe `scene:sceptre` renders this staging: the fingertips meet the
  knob at `touch`. If the marks change, change `THRONE`/`STEP_FOOT` and rebuild.
- **Ring (S04)**: `give_ring` holds the right hand out at about 0.15 in front of the king (0.17 above the dais) from
  `release` (1.0 s) to its end; `haman_take_ring` reaches 0.175 forward / 0.26 up with the **left** hand (his ring
  bone is on `handL`) and closes at `grab` (0.67 s). Swap the ring props at `grab`.
- **Haman's cap**: slips in `shock` (marker `slip`) to (−42°, +22°, small offset) and **stays slipped in `cower`,
  `led_away`, `beg` and `dragged`**, so the blends never put it back. Other clips wear it straight (`preen` tweaks
  it, `stunned` pops it straight up and drops it back).
- **S10 grab and drag (fitted to the story marks, 2026-11-14)**: Haman kneels at (0.20, 0.12) facing the king;
  guard1 at (0.29, 0.055) (0.11 to his right, 0.02 ahead), guard2 at (0.092, 0.149) (0.11 to his left, 0.02 ahead),
  both facing Haman for `grab`; then all three translate by (0.75, 0.28) at 0.160 u/s, the guards facing the travel
  and Haman turned 180° from it by the director (`backwards: true`). The guards' inner-hand targets are computed
  from those marks and Haman's mean upper-arm point in `haman_dragged` (±0.076, 0.241, −0.016) by `s10_grips()`
  and written to clips.json `stage.s10`: `grab` guard1 (0.029, 0.241, 0.039), guard2 (−0.030, 0.241, 0.040);
  `drag` guard1 (−0.016, 0.241, −0.046) (his arm just behind guard1), guard2 (−0.011, 0.241, 0.107) (in front of
  guard2: the marks are symmetric about Haman's facing, not about the travel, so in the drag guard1 walks a little
  ahead pulling and guard2 behind pushing). If Haman keeps facing the king during the drag instead of −travel, the
  grips would be guard1 (−0.049, 0.241, 0.003) and guard2 (−0.001, 0.241, 0.050); change `s10_grips()` and rebuild.
  If the marks change, edit `S10_*` and rebuild. Probe `scene:drag:<f>[:grab]` renders the three at these marks.

## 5. How the motion is made

The script is the source; there are no hand-placed keys. Each clip is a function frame → channels (rotations in
design axes in the bone's rest frame: `rx ry rz bend raise swing twist curl`, offsets `tx ty tz`, `sy` = scale
along the bone), Catmull-Rom keys (`K`, wrapped for loops), then:

- **Legs** two-bone IK to ankle targets with heel / ball / toe ground contact (`gait()` for walks, backward for
  `led_away`); **arms** use the same IK where a hand must be somewhere (chest, mouth, beard, skirt, knob), with the
  target in root, chest or head space.
- **Squash and stretch** (Haman): `sq(c, k)` scales the `spine` bone volume-preservingly (local Y = k, X/Z = 1/√k,
  k ≈ 0.90–1.13). Chest, arms and head inherit it; the legs hang from `hips`, so the planted feet are not affected.
  This is non-uniform bone scale in the GLB (the eyelids already use bone scale).
- **Uneven rhythms**: `pulses()` builds laughs, giggles, sobs and stamps from irregular hits (sharp attack, decay),
  wrapped for loops; `seg()` gives eased phase weights for the long one-shots (`preen`, `daydream`, `stunned`).
- **Overlap**: children follow parents late (`KL` lag keys, phase-shifted sines: forearm and wrist after the upper
  arm, head after the neck); anticipation and overshoot are written into every one-shot.
- **Blinks**: `eyelids` local-Y scale 1 → 12.8 → 1 over 6 frames (fast close, slower open) at irregular frames;
  the king's are 1.3–1.5× slower; Haman's `smug` keeps the lids half down (3.5) and `give_ring` lowers the king's.
- **Talk**: `syllables(seed)` makes a non-repeating jaw rhythm (syllables 3–8 frames, 22 % weak, word gaps of
  5–13 frames); its strongest syllables drive the nods and the hand beats (fingers open on the beat).
- **Secondary**: braid (`braid1-3`) and cape (`cape1-2`) are damped spring chains on top of the keyed pose
  (k 70 / 90, damping 8 / 9, pulled 35 % / 25 % toward their rest hang, max lag 28° / 22°); the sceptre wobbles
  3° behind the fist. Loops simulate three cycles and spread the residual so the seam is exact. Haman's cap feather
  `plume1 plume2` (Characters role, chain from `cap`) is a soft spring chain (k 55, damping 4.5, 12 % toward its rest
  hang, max lag 50°) so it bobs and whips; it is skipped when the bones are not in a rig. Guard spears wobble like the
  sceptre (k 200, max 4°). Loops copy frame 0's basis to frame N after the chains are closed (under the spine
  squash a direction-only closure left the plume tip up to 1 mm off).
- **Spear aim** (guards): the outer hand turns minimally so the spear points along `spear.dir` (upright).
- **Sceptre aim**: the right hand turns minimally so the staff points along `sceptre.dir`; with `sceptre.tip` the
  wrist IK target is iterated (4×) until the knob is at the target (error < 1e-4).

## 6. Extras and notes for other roles

1. **`esther_kneel` (extra)** — stand → kneel in 1.2 s, ending in frame 0 of `pray`. `pray` is a loop (contract) and
   kneeling cannot happen inside a seamless loop; the timeline gives `pray` only 2 s before `rise_brave`. Without
   `kneel` the 0.25 s blend drops her to her knees. Story/Integration: play `kneel` then `pray` (or let the engine
   play `kneel` as an entry when `pray` follows a standing clip).
2. **`haman_walk` (extra)** — timeline S04 uses `haman walk`, which §4 does not list; added as a sneaky scurry.
3. No Haman sleeve bones exist: his sleeves lag only through forearm/wrist overlap (no cloth bones to simulate).
4. Faces in renders follow `faces.json`; `kneel` uses `pray`, `haman_walk` uses `sly`.

## 7. Rough edges (honest list)

- **Rework mesh**: built against the new Haman (belly, nose, tall cap + plume) and the guards as they were in
  `characters.blend` at 10:30 on 2026-11-14. Hands at the chest (`scheme`, `idle`, `smug`) were checked from the side
  and sit in front of the belly; a bigger belly later would need the chest-space hand targets moved forward.
- **Guard march speed**: natural 0.273 u/s; the new marks need ~0.21 (guard2) and ~0.13 (guard1) over 2.6 s.
  Integration: move at the natural speed and switch to `idle` on arrival (guard1 arrives early), rather than slowing
  the clip below ~0.6×.
- **Guard boots**: a big toe-off made the boot's ankle dip 5–6 mm into the page; toe-off is 14° and `drag` stands a
  little taller (meshMinY −0.0011 / −0.0033).
- **Faces**: the new Haman faces and `guard*_stern` exist; `FACE_FALLBACK` only matters if a face is missing again.
- **Beg kneel**: the ankles are raised (toes tucked, 0.066) so the robe stays at the page (`meshMinY` −0.0015 with the new mesh);
  from the side the shins slant up behind more than a real kneel.
- **Squash / stretch** is bone scale on `spine`: check in glTFast that non-uniform bone scale with rotated children
  skins the same as in Blender (it should; Unity transforms support it).

- **Kneeling robe**: in `pray` / `kneel` / `rise_brave` / `bow` the robe below the shins dips up to 6–8 mm below
  the page (`meshMinY` −0.0056 … −0.0082, behind the knees). To keep it small the ankles stay raised (toes tucked,
  shins slanting); it reads as cloth pooling but a very low camera would see it cut by the floor.
- **King seated**: robe 1–1.5 cm into the cushion (hidden by the robe itself; the cushion is under him). Standing
  clips put his toes about 1 cm over the top step edge; the back of his robe passes close to the seat front edge.
- **Foot glides** (not slides in place): `bow` / `touch_sceptre` the right foot glides back on its toe and returns
  (0.054), `joy` pivots on the toes for the twirl (0.055). Deliberate, but visible if inspected.
- The single-bone hands cannot make a pointing index finger; `point` / `point_away` use a straight flat hand.
- `esther_pray`: the braid hangs in front of the right shoulder and is biased slightly outward so the right forearm
  does not cut through it; from the side the braid and forearm are close.
- Not seen in Unity / on the phone (glTFast, DGPaperLit, bone-scale blink on device).
