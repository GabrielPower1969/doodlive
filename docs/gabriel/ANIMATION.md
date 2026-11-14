# Gabriel — skeletal animation (Animation role)

Owner: Animation. Binding contract: [CONTRACT.md](CONTRACT.md) §3 (bones) and §4 (clip names). Rig: [RIG.md](RIG.md)
(§4 wing recipes and the trumpet solve). Pipeline adapted from Daniel (`pipeline/da_animate.py`): same clip-function
method, IK with rolling foot contact, spring chains, settle, loop closing, export, verify, contact sheet and freshness
check, plus a wing layer and a trumpet hold. Built 2026-11-14 with Blender 5.2.3.

```
python3 pipeline/ga_animate.py all        # build + verify + contact sheet + freshness check (~1 min)
python3 pipeline/ga_animate.py build      # 16 actions -> anim/gabriel.glb + anim/clips.json (with checks)
python3 pipeline/ga_animate.py verify     # re-import the GLB: animations, sampled joints, UV layer order, prop nodes
python3 pipeline/ga_animate.py contact    # anim/contact_sheet.png (key poses per clip + front / side / back rows)
python3 pipeline/ga_animate.py fresh      # GA_FRESH OK / STALE: are the model files newer than the anim export?
GA_PROBE="hover:0,9,18,27:front;blow_trumpet:15:q3#head" python3 pipeline/ga_animate.py probe   # $GA_ANIM_WORK/probe.png
GA_ONLY=hover,fly_down python3 pipeline/ga_animate.py build                                     # subset, no export
```

Inputs (read fresh on every run): `model/characters.blend` (rig, mesh, UVs, weights), `model/regions_characters.json`
(trumpet mouthpiece / bell rest points, demo colours, `clipExpression` decal per clip in renders), `timeline.json`
(travel table). Views for probes: `front q3 side back q3l lside q3b top low`, `#bone` for a close-up. Tuning knobs (env):
`GA_KW1Z / GA_KW1Y / GA_KW3Z` (kneeling wing lift), `GA_KY GA_KZ GA_TB GA_SS GA_FZ` (kneel geometry), `GA_BELL`
(trumpet bell direction in head space), `GA_WINGSPRING=0` (wing springs off), `GA_SET=1` (render with heaven.glb).
Work files: `$GA_ANIM_WORK` (default `/tmp/gabriel_anim`); delete after a run.

**Re-run rule.** The Character role may re-run `ga_character.py` (same bones and rest pose, new mesh / UVs). `all` ends
with `fresh`; if it prints `STALE`, run `all` again. Checked at the end of this run: `GA_FRESH OK` (model files
re-saved 22:00:10 by the Character polish; the export is newer).

## 1. Deliverables

| File | What |
|---|---|
| `assets/gabriel/anim/gabriel.glb` | mesh + skin (40 joints) + `gabriel_eyelids`, `gabriel_sword` (node `sword`), `gabriel_trumpet` (node `trumpet`, exported visible; Integration hides it outside S05), 16 animations `gabriel_<clip>` |
| `assets/gabriel/anim/clips.json` | per clip: action, frames, seconds, loop, rootMotion (false), **rootY** [first, last], markers {name: {frame, sec}}, loopSeamMaxErr, seamStep / maxStep, props, notes, naturalSpeed + stride (walk), sampled joints, checks (`meshMinY`, `plantedDriftMax` or `naturalSpeed` + `stanceSlipMax`, kneel clips `backFootToFeatherMin`, fly clips `footLowAtMarker`), trumpet clips `trumpet` {marker: mouthpiece, bell, bellDir}; top level `stage` (kneel geometry, hover height, fly_up travel, **trumpetBellAtBlow**), `travel`, `timelineMissing` (**empty**) |
| `assets/gabriel/anim/contact_sheet.png` | q3 key poses of every clip (demo colours, decal per `clipExpression`, markers in red, root height under each cell; the camera follows the root) + hover front / side, fly_down front / side, fold_wings back / side, kneel side / back-3/4, blow_trumpet front, fly_up side, spread_wings front |

The anim GLB carries the model GLB's mesh, skin and rest pose (`export_rest_position_armature`), so Integration loads it
instead of `model/gabriel.glb`. Character-local: root at the origin, feet on y = 0, facing +Z, 30 fps, linear, every
action keys rotation + location + scale on every bone (blink = local-Y scale of `eyelids`, 1 open / 20 closed).
UV layers: page first (TEXCOORD_0 in 0..1, checked in the binary), decal second. Verify: all 16 actions present,
sampled joints equal the build within 8e-6, no contract clip missing.

**Root travel.** `hover`, `fly_down` and `fly_up` carry their height on `root` inside the clip (CONTRACT §4); the
director adds none. `fly_up` also drifts 0.18 back (−z, toward the gate). Every other clip keeps root at 0.

## 2. Clips (30 fps; frame 0 = clip start; one-shots hold their last frame)

`meshMinY` = lowest deformed vertex over the clip (0 = the page; hidden trumpet left out). Drift = largest slide of a
planted toe. Seam = joint step across the loop seam / largest step inside the clip (every seam ≤ the largest inner
step; frame N = frame 0 exactly, spring chains closed).

| Action | Frames | s | Loop | Markers (frame) | root y | meshMinY | drift / speed | seam | Props |
|---|---:|---:|:---:|---|---|---:|---|---|---|
| `gabriel_idle` | 150 | 5.00 | yes | — | 0 | -0.0051 | 0.0 | 0.00174/0.00421 | — |
| `gabriel_hover` | 72 | 2.40 | yes | — | 0.547 (±0.016 bob) | 0.5042 | — | 0.03738/0.04329 | — |
| `gabriel_fly_down` | 144 | 4.80 | no | **land 125** (4.17 s) | 0.545 → 0 | -0.0022 | 0.0 | | — |
| `gabriel_fold_wings` | 66 | 2.20 | no | — | 0 | 0.0005 | 0.0 | | — |
| `gabriel_walk` | 44 | 1.47 | yes | contactL 0, contactR 22 | 0 | -0.0048 | **0.0814 u/s** (stance slip 0.015) | 0.01217/0.01296 | — |
| `gabriel_kneel_down` **extra** | 40 | 1.33 | no | knee_down 28 | 0 | -0.0020 | 0.0 | | — |
| `gabriel_kneel_talk` | 150 | 5.00 | yes | — | 0 | -0.0015 | 0.0 | 0.00198/0.03851 | — |
| `gabriel_stand_up` | 54 | 1.80 | no | stand 40 | 0 | -0.0015 | 0.0 | | — |
| `gabriel_talk` | 120 | 4.00 | yes | — | 0 | -0.0004 | 0.0 | 0.00669/0.04708 | — |
| `gabriel_point_up` | 72 | 2.40 | no | point 20, look_back 54 | 0 | 0.0005 | 0.0 | | — |
| `gabriel_raise_trumpet` | 60 | 2.00 | no | high 24 | 0 | 0.0005 | 0.0 | | trumpet |
| `gabriel_blow_trumpet` | 120 | 4.00 | yes | **blow 15** (0.50 s), blow2 75 | 0 | 0.0005 | 0.0 | 0.01156/0.03029 | trumpet |
| `gabriel_spread_wings` | 60 | 2.00 | no | spread 22 | 0 | 0.0005 | 0.0 | | trumpet |
| `gabriel_bless` | 150 | 5.00 | yes | heart 24, open 66 | 0 | 0.0005 | 0.0 | 0.00159/0.03548 | — |
| `gabriel_wave` | 60 | 2.00 | yes | — | 0 | -0.0005 | 0.0 | 0.01513/0.01623 | — |
| `gabriel_fly_up` | 105 | 3.50 | no | **takeoff 18** (0.60 s) | 0 → 1.202 | -0.0041 | 0.0 | | — |

`land` and `takeoff` are measured from the baked feet (first / last frame a foot point is within 1.5 mm of the page),
not typed in. Kneel clips: knee and tucked toes on the page, meshMinY ≥ −0.002 (contract ≥ −0.008), back foot ≥ 23.8 mm
from the nearest feather vertex in every checked frame (`backFootToFeatherMin`, 0 vertices within 4 mm).

### Trumpet (for Effects: `trumpet_notes`)

At the `blow` marker (blow_trumpet f15), character-local (root at the origin, +Z = viewer, y up):

- **bell** `(-0.0846, 0.6623, 0.3024)`, bell axis `(-0.268, 0.410, 0.872)` (up and forward, a little to his right);
  `blow2` (f75): bell `(-0.1047, 0.6616, 0.2965)`.
- mouthpiece `(-0.0033, 0.538, 0.0377)`; it stays on the lips within 1e-5 through the whole loop.
- Simplest for FX: attach `trumpet_notes` to node `trumpet` at `bellLocal` from `regions_characters.json`
  (`[-0.2907, 0.3251, -0.1743]` in rest space) so it follows the breathing / lean.

### Acting notes

- `idle` — tall and kind: three breaths with one deeper one (the half-open wings rise with it), weight shift with the
  hips leading, looks away and back, small nod; the wings breathe (right wing 4 frames behind the left) and once rouse
  their feathers (f118); irregular blinks.
- `hover` — two 1.2 s wing beats per loop. **Down-stroke** (55 %): wing fully extended, primaries spread, tips swept
  forward (pushing air), the feathers twisted back by the air; **up-stroke**: the forearm and hand fold in, the fan
  closes, the tips trail. wing1 → 2 → 3 → prim each lag (0.07 / 0.13 / 0.18 of a beat) so the tips whip through the
  turns; spring follow-through on top. The root rises 0.016 on each down-stroke, the chest crunches, the arms float
  and the dangling legs (toes pointed, right leg trailing) swing late.
- `fly_down` — frame 0 = hover; three big beats (down-strokes centred at 0.33 / 1.53 / 2.73 s ≈ the story's
  wing_flap at 0.4 / 1.6 / 2.8 s), each one slowing the fall; from 3.1 s the wings flare up and forward (primaries
  slotted open), the body leans back, the legs reach down, toes first; touchdown at `land` 125, the heels come down,
  knees absorb 0.03, a last soft push of the wings, then they rise to "open" and the feathers settle. Ends standing.
- `fold_wings` — small lift-and-spread anticipation, then wing1 leads and the forearm, hand and closing fan follow
  3–6 frames later into the RIG.md fold (a feather cloak, tips at the knees); a quick decaying ruffle with a shrug at
  f40; holds. Checked front / side / back / top for feathers through the body: none seen.
- `walk` — noble, ~82 steps/min, wings folded and bouncing late on each step.
- `kneel_down` (extra) → `kneel_talk` — left foot steps forward, down on the right knee; the folded wings lift 22° and
  sweep back (WKNEEL) so the inner tertials stay off the page and clear of the back foot; the scabbard swings back off
  the page. Talking: leans in, left forearm on the left knee, right hand opening palm up on stressed syllables, nods,
  head tilt, jaw syllables.
- `stand_up` — leans in, pushes on the knee, rises into a lunge (back foot on its toes), brings the right foot up,
  then the left back; wings back to the standing fold.
- `talk` — both hands open out palms up (giving), then the right sweeps out and the left comes to the chest; the
  folded wings lift a little with the big gesture.
- `point_up` — dip, right arm sweeps up (overshoot), looks up after it, holds the look, looks back at the child with
  a head tilt; the arm stays up. Fingers are one bone: an open hand, not an index finger.
- `raise_trumpet` — trumpet at his side, dip, lifts it high bell to the sky; the folded wings open to half with
  overlapping action.
- `blow_trumpet` — two phrases per 4 s loop: breath in (chest and shoulders up, wings gather), blow (lean back, bell
  lifts, chest empties), wings flare from half to wide with each phrase (right wing 2 frames late) with a feather
  shiver. Eyes: the `blow` decal draws them closed; the eyelid geometry stays open (1) so it does not cover the drawing.
- `spread_wings` — starts exactly as blow_trumpet frame 0, lowers the trumpet to his side (bell down-forward), the
  wings gather then sweep to a majestic spread raised above the rest pose, overshoot, settle; chest up, arms out.
- `bless` — wings wide and breathing; right hand to the heart, then the open palm raised toward the viewer, back to
  the heart; slow nod, jaw syllables.
- `wave` — right hand up by the head waving from the elbow, half-open wings fluttering along late.
- `fly_up` — crouch (hips −0.05, arms back, wings rise high), spring: one huge down-stroke, feet leave at `takeoff`
  18, two more beats at 0.9 s (down-strokes centred at 0.7 / 1.5 / 2.4 s), rising on an accelerating curve to 1.2 and
  0.18 back; looks up, legs trail with pointed toes.

## 3. Travel (in-place walk; the director moves the actor)

| t | Clip | Dist | Time | Needs u/s | Natural | Rate |
|---:|---|---:|---:|---:|---:|---:|
| 18.58 | `gabriel_walk` | 0.08 | 1.6 | 0.050 | 0.081 | 0.61 |

Inside the 0.6–1.6× range (play at rate 0.61 or switch to the next clip on arrival).

## 4. Notes for Story / Integration

1. **`kneel_talk` is a loop and cannot itself go down on the knee.** Play the extra `kneel_down` (1.33 s, ends exactly
   on kneel_talk frame 0) where the timeline now starts `kneel_talk`, then `kneel_talk` ~1.3 s later. Without it the
   0.25 s blend drops him from standing to kneeling in a quarter second.
2. `spread_wings` and `bless` start at the same time in the timeline (62.47): `bless` overrides, so the spread is never
   seen. Suggest `bless` ~1.4 s after `spread_wings` (its hold); both have wide wings, so the blend is soft.
3. `point_up` holds the arm up for the whole ga_05 line (~10 s until raise_trumpet). If that feels long, a `talk`
   after ~3 s would bring the arm down.
4. Trumpet: show it from `raise_trumpet` to the end of `spread_wings` (the timeline hides it at S06, matching).
5. hover → fly_down and spread_wings → bless are wing-state-compatible; talk / point_up (folded) → raise_trumpet
   (starts folded and opens) also. Avoid blending folded ↔ spread directly (quaternion blends of the fold can pass
   the primaries through the body).

## 5. How the motion is made

As Daniel §5 (clip = function frame → channels in design axes, Catmull-Rom keys, leg / arm IK, blinks, syllable jaw,
eased one-shots with anticipation / overshoot / settle). New here:

- **Wing layer**: poses as `"<seg>.<ch>"` dicts for the left wing (`seg` 1 / 2 / 3 / p, `ch` rz / ry / twist), right =
  mirrored; applied Z then Y (RIG.md §4 order). Named poses: `WSPREAD` (rest), `WOPEN`, `WHALF`, `WFOLD` (the RIG
  recipes), `WKNEEL`, `WWIDE`, `WGRAND`. `pmseg` blends with a separate eased weight per segment (overlap: the hand
  and fan arrive late), `ring()` adds decaying feather shakes and settles.
- **`flap(p)`**: the RIG.md up / down-stroke recipes as the ends of an eased stroke curve per segment with phase lags,
  an up-stroke fold hump (`UPFOLD`: forearm in, hand in, fan closed) and a feathering twist driven by stroke speed;
  `flight_body` makes the body rise and the chest crunch on the down-stroke; `flight_arms`, `dangle_legs` lag it.
- **Springs**: hair1-2 (95 / 8 / 0.25 / 22°), sash1-2 (80 / 7 / 0.30 / 26°) and per wing wing2-3-prim (420 / 17 / 0 /
  7°) for follow-through and settle. Unlike Daniel's copy, every loop pass springs toward the *keyed* rotation (not
  the previous pass's result), which closes the wing loops cleanly.
- **Trumpet hold**: the RIG.md arm solve gives the hand transform with the mouthpiece on the lips; it is turned about
  the mouthpiece so the bell points up-forward (`GA_BELL`, head space `(-0.20, 0.30, 0.93)`) and stored in head space.
  Each frame the right arm is IK'd to that hand transform (the forearm takes the wrist twist), so the trumpet stays
  on the lips while he breathes and leans. `trumpet.aim` turns the hand so the trumpet axis points a given way
  (raise, spread).
- **Kneel**: kneel geometry + a one-off settle of the hips on the skinned proxy of the kneeling leg (hips −0.1259).

## 6. Rough edges (honest list)

- Not seen in Unity or on a phone (glTFast skinning of 464 feathers, bone-scale blink, 40-joint blends).
- At the bottom of the biggest down-strokes (fly_up first beat, amp 1.18 → wing1 −40°) the innermost feathers of the
  two wings meet behind the spine (RIG.md §9.6); from the back it reads as one feather skirt, not as crossing.
- The flare and the up-stroke fold are angle blends, checked at the rendered frames only (front, side, back), not
  every in-between.
- `fly_up` f20–30: both arms swing forward at shoulder height on the spring; reads as a launch, a little stiff.
- Fingers are one bone per hand (no pointing index, no tight fist on the trumpet beyond the 72° curl).
- `idle` meshMinY −0.0051 (right toe on the weight-shift roll), `walk` −0.0048: within a few tenths of a mm, not visible.
