# Ruth — skeletal animation (Animation role)

Owner: Animation. Binding contract: [CONTRACT.md](CONTRACT.md) §3 (bones) and §4 (clip names). Rig: [RIG.md](RIG.md).
Stage: [SET.md](SET.md). Pipeline adapted from Esther (`pipeline/es_animate.py`, committed version) — same clip-function
method, IK, spring chains, export and verify. Built 2026-11-14 with Blender 5.2.3.

```
python3 pipeline/ru_animate.py all        # build + verify + contact sheet (~5 min, most of it the contact renders)
python3 pipeline/ru_animate.py build      # 43 actions -> anim/{ruth,naomi,boaz}.glb + anim/clips.json with checks (~20 s)
python3 pipeline/ru_animate.py verify     # re-import the GLBs: animations, sampled joints, UV layer order, prop nodes
python3 pipeline/ru_animate.py contact    # anim/contact_sheet.png (key poses + three two-actor rows)
RU_PROBE="ruth_glean:0,24:side;naomi_idle:0:q3" python3 pipeline/ru_animate.py probe        # $RU_ANIM_WORK/probe.png
RU_PROBE="pair:ruth_hug:naomi_hug:0.122:30:front,q3,top,back" python3 pipeline/ru_animate.py probe   # two actors facing
RU_ONLY=ruth_glean,naomi_hug /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python pipeline/ru_animate.py -- build                                                 # bake + check a subset, no export
```

Inputs (read at run time): `model/characters.blend` (Characters), `model/bethlehem.glb` (Set, renders only),
`timeline.json` (Story), `faces.json` (Integration, decal per clip in renders), `model/regions_characters.json` (demo
colours). Work files: `$RU_ANIM_WORK` (default `/tmp/ru_anim_work`); the temporary blend is deleted after export.

## 1. Deliverables

| File | What |
|---|---|
| `assets/ruth/anim/ruth.glb` | Ruth mesh + skin (30 bones) + `ruth_sheaf` / `ruth_stalks` / `ruth_eyelids`, 18 animations (17 contract + `kneel`) |
| `assets/ruth/anim/naomi.glb` | Naomi + `naomi_staff` / `naomi_baby` / `naomi_eyelids`, 13 animations |
| `assets/ruth/anim/boaz.glb` | Boaz + `boaz_stalks` / `boaz_eyelids`, 12 animations |
| `assets/ruth/anim/clips.json` | Per clip (D&G / Esther schema): action, char, clip, frames, seconds, loop, rootMotion (false), markers {name: {frame, sec}}, loopSeamMaxErr, rootMaxOffset, **props** (props the clip is posed for), notes, naturalSpeed + stride (locomotion), sampled joints, checks (`meshMinY`, `plantedToeDriftMax` or `naturalSpeed`, Naomi `staffFootY`); top level `stage` (the partner distances the two-actor clips are fitted to, kneel geometry), `naomiNoStaffClips`, `timelineMissing` (**empty**), `requestedClips` |
| `assets/ruth/anim/contact_sheet.png` | Key poses of every clip in Bethlehem (demo colours, face decal per `faces.json`, props shown only where posed; markers in red, `*` = extra) + three rows of two actors at their story distance (hug, hold_hands + listen_moved, cheer_up + sad) |

The anim GLBs carry the model GLBs' mesh, skin and rest pose (`export_rest_position_armature`), so Integration loads them
instead of `model/*.glb`. Character-local: root at the origin, facing +Z, sampled every frame at 30 fps, linear; every
action keys rotation + location + scale on every bone (the blink is a scale of `eyelids`). UV layers: page first
(TEXCOORD_0 in 0..1 for every primitive, `verify` reads the binary), decal second — `fix_uv_order()` as Esther (the
current characters.blend already has them in that order, so it is a no-op). Prop nodes in the GLB as RIG.md §1:
`ruth/sheaf`, `ruth/stalks`, `naomi/staff`, `naomi/baby`, `boaz/stalks` (bone node, mesh `<char>_<bone>` under it).

## 2. Clips (30 fps; frame 0 = clip start; one-shots hold their last frame)

`meshMinY` = lowest deformed vertex over the clip (0 = the page; hidden props left out). Drift = largest slide of a
planted toe in a non-locomotion clip (deliberate steps show up here); for locomotion the natural speed. All loop seams
are 0.000000 (frame N = frame 0, spring chains closed). GLB round trip: joints equal the build within 8e-6.

| Action | Frames | s | Loop | Markers (frame / s) | meshMinY | drift / speed | Props |
|---|---:|---:|:---:|---|---:|---:|---|
| `ruth_idle` | 150 | 5.00 | yes | — | -0.0027 | 0.0021 | — |
| `ruth_walk` | 34 | 1.13 | yes | contactL 0, contactR 17 / 0.57 | -0.0038 | **0.109 u/s** | — |
| `ruth_talk` | 96 | 3.20 | yes | — | 0.0010 | 0.0001 | — |
| `ruth_sad` | 120 | 4.00 | yes | — | -0.0025 | 0.0014 | — |
| `ruth_shake_head` | 36 | 1.20 | no | no 8 / 0.27 | 0.0015 | 0.0 | — |
| `ruth_hold_hands` | 90 | 3.00 | yes | — | 0.0015 | 0.0 | — |
| `ruth_hug` | 90 | 3.00 | yes | — | 0.0010 | 0.0001 | — |
| `ruth_cheer_up` | 66 | 2.20 | no | touch 30 / 1.00 | 0.0001 | 0.030 (step in) | — |
| `ruth_glean` | 120 | 4.00 | yes | — | **-0.0064** | 0.0 | stalks |
| `ruth_kneel` **extra** | 30 | 1.00 | no | knees_down 22 / 0.73 | -0.0055 | (planned step) | — |
| `ruth_stand_up` | 54 | 1.80 | no | stand 34 / 1.13 | -0.0068 | (planned step) | stalks |
| `ruth_bow_kneel` | 72 | 2.40 | no | knees_down 22 / 0.73, bow 40 / 1.33 | -0.0063 | (planned step) | stalks |
| `ruth_shy` | 120 | 4.00 | yes | — | -0.0035 | 0.0087 (toe twist) | stalks |
| `ruth_carry_walk` | 38 | 1.27 | yes | contactL 0, contactR 19 / 0.63 | -0.0036 | **0.074 u/s** | sheaf |
| `ruth_show_bundle` | 60 | 2.00 | no | up 26 / 0.87 | -0.0031 | 0.0059 | sheaf |
| `ruth_joy` | 72 | 2.40 | yes | twirl 8 / 0.27, hop 50 / 1.67 | -0.0030 | 0.053 (toe pivot) | — |
| `ruth_ask_humble` | 60 | 2.00 | no | ask 30 / 1.00 | 0.0 | 0.026 (step in) | — |
| `ruth_wave` | 48 | 1.60 | yes | — | -0.0001 | 0.0 | — |
| `naomi_idle` | 150 | 5.00 | yes | — | -0.0018 | 0.0014 | staff |
| `naomi_walk_tired` | 52 | 1.73 | yes | contactL 0, contactR 26 / 0.87, staffPlant 2 / 0.07 | -0.0031 | **0.037 u/s** | staff |
| `naomi_talk` | 96 | 3.20 | yes | — | 0.0 | 0.0 | staff |
| `naomi_sad` | 120 | 4.00 | yes | — | 0.0 | 0.0 | staff |
| `naomi_send_away` | 66 | 2.20 | no | go 26 / 0.87 | 0.0 | 0.0 | staff |
| `naomi_listen_moved` | 120 | 4.00 | yes | — | 0.0 | 0.0 | staff |
| `naomi_hug` | 90 | 3.00 | yes | — | 0.0 | 0.0001 | staff |
| `naomi_nod` | 40 | 1.33 | no | nod 10 / 0.33 | 0.0 | 0.0 | staff |
| `naomi_surprised` | 45 | 1.50 | no | oh 9 / 0.30 | -0.0010 | 0.0017 | staff (lifted) |
| `naomi_bless_up` | 80 | 2.67 | no | up 30 / 1.00 | 0.0015 | 0.0015 | staff (raised high) |
| `naomi_clap` | 40 | 1.33 | yes | clap1 7, clap2 19, clap3 31 | 0.0 | 0.0 | no staff |
| `naomi_hold_baby` | 120 | 4.00 | yes | — | 0.0009 | 0.0001 | baby, no staff |
| `naomi_joy` | 60 | 2.00 | yes | — | 0.0 | 0.0 | no staff |
| `boaz_idle` | 150 | 5.00 | yes | — | -0.0032 | 0.0018 | — |
| `boaz_walk` | 34 | 1.13 | yes | contactL 0, contactR 17 / 0.57 | -0.0055 | **0.128 u/s** | — |
| `boaz_talk` | 96 | 3.20 | yes | — | 0.0010 | 0.0001 | — |
| `boaz_greet` | 48 | 1.60 | no | hail 16 / 0.53 | -0.0004 | 0.0099 (small step) | — |
| `boaz_look_curious` | 90 | 3.00 | yes | — | -0.0017 | 0.0012 | — |
| `boaz_talk_kind` | 96 | 3.20 | yes | — | 0.0016 | 0.0 | — |
| `boaz_hand_on_heart` | 56 | 1.87 | no | heart 22 / 0.73 | 0.0017 | 0.0 | — |
| `boaz_sneaky_drop` | 136 | 4.53 | no | left 14 / 0.47, right 40 / 1.33, grin 64 / 2.13, **drop 104 / 3.47** | -0.0035 | 0.0031 | stalks |
| `boaz_chuckle` | 60 | 2.00 | no | heh 8 / 0.27 | 0.0007 | 0.0 | — |
| `boaz_listen` | 120 | 4.00 | yes | — | 0.0009 | 0.0001 | — |
| `boaz_joy` | 60 | 2.00 | yes | — | -0.0011 | 0.0 | — |
| `boaz_wave` | 48 | 1.60 | yes | — | -0.0007 | 0.0 | — |

Naomi's `staffFootY` (staff foot height over the clip) is 0.0000 in every clip where the staff stands on the page;
walk_tired lifts it to 0.018 in the swing; surprised / bless_up lift it with the hand (0.065 / 0.18).

### Acting notes

- **Ruth** — young, warm, quick. `idle`: breathes (one deeper breath), weight L→R→L with the hips leading and the chest
  late, hands loosely together, the left hand smooths the scarf end once, glances away and back (neck leads), blinks
  single / double / slow at irregular frames. `walk` ~106 steps/min, hip bob, counter-turn, lagging forearms.
  `talk`: irregular syllables with word gaps; phrase 1 the right hand opens palm-up, phrase 2 the left comes to her
  chest. `sad`: head low, slumped, a long sigh, one look up. `shake_head`: breath in, three shrinking firm shakes (the
  chest answers late, scarf whips), ends chin up with the hands rising (next: hold_hands). `hold_hands`: leans in,
  both hands forward palms-up at chest height, irregular pleading pushes, held-back sobs. `hug`: right arm over
  Naomi's left shoulder, left arm round her waist, head over Naomi's right shoulder, rocking in phase with
  `naomi_hug`, a squeeze and two pats. `cheer_up`: steps in, right hand to Naomi's left upper arm, squeeze, then a
  bright bounce with the left palm up. `glean`: see §4. `stand_up`: looks up, left foot forward, hand on the knee,
  rises, brushes the skirt. `bow_kneel`: kneels (right then left), hands together at the chest, bows low; holds.
  `shy`: hands clasped low, head down and aside, sway, right toe twisting on its tip, one quick peek up.
  `carry_walk`: leans back against the bundle, it bobs late, head peeks round it. `show_bundle`: dip, lifts the sheaf
  forward and out to her right (face stays clear), up on her toes, beaming tilt. `joy`: dip, twirl (scarf flies),
  hop with hands up. `ask_humble`: steps in, hands clasped at the chest, small bow, head tilted, looking up. `wave`.
- **Naomi** — older, slower, heavier; tired and stooped, then lifted by joy. The stoop is in the rest pose (RIG.md
  §2); breathing deepens / lifts it. `idle`: both hands stacked on the staff planted in front, leans on it, one long
  sigh, slow look round, heavy slow blinks. `walk_tired`: short low steps, heavy drop, head bob; the staff is set down
  with the left foot and stays still on the page while it carries her weight. `talk`: small tired palm-up gestures,
  once a hand to the chest. `sad`: hand pressed to her chest, sigh, slow head shake. `send_away`: palm out toward
  Ruth, two soft pushes, sinks half way and stays offered. `listen_moved`: hand at her mouth, irregular sobs, slow
  nods. `hug`: left arm round Ruth's back under Ruth's arms, staff planted at Ruth's side, head against Ruth's
  shoulder. `nod`: two nods, smile, the left hand joins the right on the staff. `surprised`: gasp, leans back with a
  hop on her heels, left hand up by her face, staff lifted. `bless_up`: gathers her hands to her chest, both arms rise
  (the staff held high), the stoop straightens, face up, happy tremble. `clap`, `hold_baby` (rocking, the baby rolls
  late, looks down at it, once up at the viewer), `joy` (laughs, arms open, stoop lifted) — no staff.
- **Boaz** — broad, hearty, fatherly, a little comic. `idle`: left hand on his hip/sash, weight shifts, looks over
  his field, nods to himself, strokes his beard. `walk` confident stride, the open robe's panels swing with the legs.
  `talk` both hands in turn. `greet` dip then the right arm high with an open hand, one small wave, held. `look_curious`
  hand shading his eyes, leaning and tilting. `talk_kind` open palms; on one phrase the right hand sweeps out to his
  right ("over there, the water jars"). `hand_on_heart` right hand to his heart, small bow, settles warm.
  `sneaky_drop` §4. `chuckle` hand on belly, uneven fading shoulder shakes, eyes crinkle. `listen` 'mm' nods.
  `joy` laughs with arms flung open. `wave`.

## 3. Natural speeds (in-place locomotion; the director moves the actor)

Speed = stride / stance time. "Needs" = distance / time until the actor's next clip in the current `timeline.json`.

| Clip | Stride | Duty | Natural | Timeline needs |
|---|---:|---:|---:|---|
| `ruth_walk` | 0.074 | 0.60 | **0.109 u/s** | S01 (from off-page) slow; S03 0.316 in 16.3 s → 0.019; **S04 0.412 in 2.6 s → 0.159**; S09 0.19 in 3.4 s → 0.056; **S10 0.306 in 2.2 s → 0.139**; S11 0.072 in 9.3 s |
| `ruth_carry_walk` | 0.058 | 0.62 | **0.074 u/s** | S08 0.505 in 5.3 s → 0.095 (1.3×, fine) |
| `naomi_walk_tired` | 0.042 | 0.66 | **0.037 u/s** | S03 0.374 in 9.3 s → 0.040; **S10 0.33 in 2.2 s → 0.150 (4×)** |
| `boaz_walk` | 0.084 | 0.58 | **0.128 u/s** | S05 0.30 in 7.3 s → 0.041; S06 0.104 in 1.6 s → 0.065; S07 0.106 in 1.0 s → 0.106; S08 off-camera 0.02 / 0.047; **S10 0.388 in 2.4 s → 0.162** |

Recommendation (as Esther): move at the natural speed, or scale the clip rate to the needed speed within about
0.6–1.6×, and switch to the next clip on arrival so feet do not skate. The bold rows are outside that range (Story:
give those moves more time — Naomi in S10 would need ~9 s at her tired pace; or Integration scales up to 1.6× and lets
them arrive late).

## 4. Staging the clips assume

- **Two-actor distances** (`clips.json stage`): hug / hold_hands / listen_moved at **0.122** (ROAD_A–ROAD_B),
  cheer_up / show_bundle at **0.126** (DOOR–DOOR_RUTH), ask_humble at 0.161, talk_kind / bow_kneel at 0.163. The
  director turns each actor to face the other (`face`). Ruth's and Naomi's hug arms are IK targets at those partner
  positions; `ruth_hug` and `naomi_hug` share length (90 f) and rocking phase — start them on the same frame (the
  timeline does, t 33.21) or the rocking drifts apart. Pair renders: contact sheet rows "pair: …" and probe `pair:`.
- **Gleaning (`glean`)**: both knees on the stubble (knee joint 0.022 above the page, shins sloping up behind 26°,
  toes tucked); the right fist holds the handful (`ruth/stalks`, ears aimed up-and-out) in front of her belly; two
  picks per loop at different spots — look, lean back a touch, lean and reach down, fingers close on a stalk, lift,
  add it to the handful (the fist opens a little), straighten, glance up at the field. **The prop is on `handR`,
  so the LEFT hand picks and the RIGHT holds** (the contract text says the other way round). meshMinY −0.0064 (the
  calf / skirt just behind the knee); `kneel`, `stand_up`, `bow_kneel` share the same kneel (≥ −0.0068).
- **Sneaky drop**: Boaz faces the viewer; glance to his left (f 14), right (f 40), grin + finger to lips (f 64), the
  fist slides behind his back (f 80–100) and opens at **`drop` = f 104 / 3.47 s** (hand behind his right buttock,
  root-local ≈ (−0.04, 0.20, −0.07)), then an innocent look up and heel rocking.
- **Naomi's staff**: planted at her side by default (foot (−0.08, 0, 0.04) root-local), in front for idle / nod (both
  hands on it), at Ruth's side in hug. Clips without the staff: clap, hold_baby, joy (`naomiNoStaffClips`).

## 5. Notes for Integration / Story (things the timeline should change or know)

1. **`ruth_kneel` (extra)** — stand → kneel in 1.0 s, ending in frame 0 of `glean`. S04 (t 59.94 walk → 62.54
   glean) needs it, otherwise the 0.25 s blend drops her to her knees. Play `kneel` then `glean`.
2. **S06 bow_kneel → shy → glean (t 104.5 / 117.29 / 117.79)**: bow_kneel ends kneeling, `shy` is standing, glean is
   kneeling again 0.5 s later: she would pop up and down. Suggest dropping the 0.5 s `shy` (stay in bow_kneel until
   glean), or play `stand_up` before `shy` and `kneel` before `glean`.
3. **S07 drop timing**: the timeline hides `boaz/stalks` and plays `stalks_fall` / `stalks_drop` at ~127.2–127.4,
   but `sneaky_drop` (start 118.99) opens his hand at 118.99 + 3.47 = **122.46**. With the current timeline the
   stalks stay in his open hand until 127.4 and come round to his belly in `chuckle` (126.0). Move the hide + fx +
   sfx to the `drop` marker (or start sneaky_drop ~5 s later so the drop lands on "留给她捡").
4. **Gliding clips**: `naomi idle` with `to` (S04 0.10 over 68 s — slow; **S08 0.10 in 5.6 s, 0.018 u/s, visible**),
   `ruth glean` with `to` (S07 0.10 in 10.8 s, a knee glide), `boaz idle` with `to` (S11), `naomi hold_baby` with
   `to` (S11 0.057). Insert a walk or teleport off-camera.
5. **S10 staff**: `naomi/staff` is hidden at 176.82 and she then plays `walk_tired` (2.2 s), whose right fist plants
   an invisible staff. Either hide the staff after the walk (at `clap`, 179.22) or accept the fist pumping.
6. Props per clip are listed in clips.json `props`; the timeline's prop events match them (stalks shown during
   glean … shy, sheaf during carry_walk / show_bundle, baby with hold_baby).
7. Lip sync overrides `jaw` in every talk clip; the jaw keys elsewhere (joy, chuckle, surprised) are small.
8. `ruth_joy`: the root bone turns 360° about Y during the twirl (no translation), as `esther_joy`.

## 6. How the motion is made

As Esther §5 (`pipeline/es_animate.py`): each clip is a function frame → channels in design axes, Catmull-Rom keys
(wrapped for loops), leg IK with heel / ball / toe contact, arm IK with targets in root space or in the space of any
bone (`chest`, `head`, `sheaf`, `baby`, `staff`), irregular blinks, syllable jaw rhythms with beats driving nods and
hand gestures, eased one-shot phases with anticipation, overshoot and settle, pulse trains for laughs and sobs. New:

- **Kneel geometry** (`kneel_geom`): knee joint height, thigh lean and shin slope define hips / ankle targets; the toe
  tuck pitch is solved so the foot's lowest point touches the page. Swept for meshMinY (knee 0.022 / shin 26°).
- **Staff solver** (`staff_solve`): given the staff foot on the page and its direction, the right wrist target is
  iterated (≤ 7×) until the foot is there (error < 2e-5); `left_on_staff` puts the left hand on top in staff space.
- **Prop aim** (`aim.<bone>` channel): the hand turns minimally so the stalk ears point a chosen way (axis = bone head
  → mesh centroid).
- **Spring chains**: Ruth `scarf1-2` (k 75, damping 7.5, 30 % rest hang, max 30°), Naomi `shawl1-2` (70 / 8 / 30 % /
  24°), Boaz `headcloth` (90 / 8.5), `cloakL` / `cloakR` (80 / 7, 22 %, max 16°, plus keyed swing with the legs in the
  walk), stalk handfuls wobble (≤ 5–6°). Loops simulate 3 cycles and close exactly; frame N copies frame 0.

## 7. Rough edges (honest list)

- **Weakest clips**: `naomi_hold_baby` (arms read as cradling but the hands are approximate around a small baby;
  the baby sits low at the sash because her stooped chest is low), `ruth_carry_walk` / `show_bundle` (the right
  forearm across the bundle is plausible, not a tight hug; the sheaf is smaller than "a great big bundle"),
  `naomi_send_away` (small, reads as a gentle wave-off more than "go home"), `boaz_joy` (the panels swing open and
  show the tunic edge).
- **Kneels**: the feet are tucked but the toes stay ~1.5 cm above the page (the shins must slope up for the skirt to
  stay above −0.008); from a low side camera the soles show in the air behind her.
- **Hug**: heads cheek to cheek over opposite shoulders; at the top view the two head-cloths touch / overlap a
  little. Arms pass close to the partner's sleeves (no collision solve).
- **hold_hands**: Ruth's hands stop just short of Naomi (wrists 0.05 in front of her) rather than touching, because
  Naomi's stooped chest is only ~0.08 in front of Ruth at 0.122.
- Hands are single-bone fingers: no pointing finger (Boaz's "over there" is an open-palm sweep).
- Not seen in Unity / on the phone (glTFast skinning, bone-scale blink, prop show / hide).
