# David & Goliath — skeletal animation (Animation role)

Owner: Animation. Binding contract: [CONTRACT.md](CONTRACT.md) §3 (bones), §5 (clip names) and §11 (redraw of
2026-10-27: realistic proportions, 45° rest, finger bones, desert set). Rig: [RIG.md](RIG.md). Desert: [DESERT.md](DESERT.md).
Re-authored on 2026-10-27 for the new rigs, with Blender 5.2.3.

```
python3 pipeline/dg_animate.py all       # build + verify + contact sheet + preview (about 10 min, most of it the preview)
python3 pipeline/dg_animate.py build     # 19 actions -> anim/{david,goliath}.glb + anim/clips.json with checks (~20 s)
python3 pipeline/dg_animate.py verify    # re-import both GLBs, list animations, compare joint positions with the build
python3 pipeline/dg_animate.py contact   # anim/contact_sheet.png
python3 pipeline/dg_animate.py preview   # anim/preview.mp4 (timeline.json performance, 640x360, desert set, preview_mix.mp3)
DG_PROBE="goliath_fall:0,36,54:q3l@0.16,-0.22" python3 pipeline/dg_animate.py probe   # work close-ups ($DG_WORK/anim/probe.png)
```

Inputs: `model/dg_characters.blend` (Blender role), `model/desert.glb` (Desert role), `timeline.json` (Story),
`design.json` (Design), `audio/preview_mix.mp3` (Music). Intermediates: `$DG_ANIM_WORK`, default `$DG_WORK/anim`
(`DG_WORK` default `/tmp/dg_work`). Render textures (CONTRACT §12.4 look, approximated; `prepare_textures()` writes
`$DG_ANIM_WORK/tex_chars.png` and `tex_desert.png` before contact / preview / probe): the source is
`sheet/demo-colored.png` once it is newer than `design.json` (Sheet role rebuilt it for v3), otherwise Design's
`design/sheet-mock-demo-colour.png`; printed lines are erased; for the desert pieces unpainted paper becomes sand
`#F3D58E`; the page wears Design's baked sand ground `design/ground-sand-demo.png`. Overrides: `DG_CHAR_TEXTURE`
(art-rectangle image, e.g. `$DG_WORK/uvproof.png`), `DG_PAGE_TEXTURE` (desert), `DG_GROUND_TEXTURE` (page).

## 1. Deliverables

| File | What |
|---|---|
| `assets/david-goliath/anim/david.glb` | David mesh + skin (33 bones) + stone, 9 glTF animations (one per action), 30 fps, sampled every frame |
| `assets/david-goliath/anim/goliath.glb` | Goliath mesh + skin (32 bones) + helmet/crest/spear/shield nodes, 10 glTF animations |
| `assets/david-goliath/anim/clips.json` | Per clip: frames, seconds, loop, root motion, markers, loop seam error, sampled joint positions, **checks** (§3), desert events |
| `assets/david-goliath/anim/contact_sheet.png` | Key poses of every clip (EEVEE, page + desert, face decal of the clip's expression; markers in red) |
| `assets/david-goliath/anim/preview.mp4` | Whole 89 s performance of `timeline.json` on the page with the desert set, faces switching per clip, with `preview_mix.mp3` |

The anim GLBs carry the same mesh, skin and rest pose as `model/*.glb` (`export_rest_position_armature`), so Integration
can load the anim GLB instead of the model GLB. Character-local: root at the origin, facing +Z.

## 2. Clip table (30 fps; frame 0 = clip start; one-shots hold their last frame)

Frame counts, loops and markers are **unchanged** from the first build, so `timeline.json` timing still holds.

| Action | Frames | Seconds | Loop | Markers (frame / s) | Notes (fingers per §11.11) |
|---|---:|---:|:---:|---|---|
| `david_idle` | 60 | 2.00 | yes | — | breathing, weight shift, looks around; sling sways; left hand relaxed (slight curl), right fist on the sling |
| `david_walk` | 24 | 0.80 | yes | contactL 0, contactR 12 / 0.40 | light quick steps, arms swing with lagging forearms, left hand loosely curled |
| `david_talk` | 36 | 1.20 | yes | — | jaw flap, open left hand opens wider on the beats, nods |
| `david_kneel_pick` | 96 | 3.20 | no | kneel 16, pick1 34 / 1.13, pick2 46, pick3 58, pick4 70, pick5 82 / 2.73, stone_in_pouch 88 / 2.93 | **Root motion (v3, CONTRACT §12.5):** while going down he turns 45° to his right (root yaw −45°, 0→14) and shifts (−0.015, −0.025) back from the page edge; both feet step (right 2–11, left 5–16) instead of sliding; **kneels on the left knee at the brook** with the stones on his right side; right hand reaches down and out to each of the five `desert.glb` stones: opens → pinch → closes; stones 1–4 into the bag, stone 5 shows in the hand and drops into the pouch at 88; turns back and stands 84–96, root back to zero at 96 |
| `david_sling_windup` | 36 | 1.20 | yes | — | 3 spins per loop overhead, left hand points (fingers straight), right fist closed on the cords |
| `david_sling_release` | 45 | 1.50 | no | **release 2 / 0.067**, hit 14 / 0.467 (exact hit 0.450 s) | whip; right hand opens at the release and closes on the cord again by ~0.7 s; follow-through; stone flies (§4) |
| `david_run` | 16 | 0.53 | yes | contactL 0, contactR 8 / 0.27 | flight phase, arms pump, left hand a loose fist |
| `david_victory` | 45 | 1.50 | no | takeoff 10 / 0.33, land 22 / 0.73 | jump with **two raised fists** (the right one still holding the sling) |
| `david_pray` | 90 | 3.00 | no | knees_down 34 / 1.13, hands_together 50 / 1.67 | right knee, left knee; both hands open, palms together in front of the chest; head bowed |
| `goliath_idle` | 90 | 3.00 | yes | — | heavy breathing, weight shift, grumpy head turns; both fists closed (spear, shield) |
| `goliath_walk` | 66 | 2.20 | yes | contactL 9 / 0.30, contactR 42 / 1.40 | heavy: hips drop on each contact, chest/head nod after it |
| `goliath_talk` | 48 | 1.60 | yes | — | chin up, jaw flap, spear-arm beats |
| `goliath_taunt` | 48 | 1.60 | no | clang 9 / 0.30 | lifts the spear and brings it down by the shield, sneer (grips stay closed) |
| `goliath_laugh` | 60 | 2.00 | no | — | head back, belly bounces ~3.3 ha/s (grips stay closed) |
| `goliath_roar` | 54 | 1.80 | no | roar 16 / 0.53 | crouch + inhale, roar with arms out and the spear high, settle |
| `goliath_charge` | 60 | 2.00 | yes | contactL 0, contactR 30 / 1.00 | leaning lumbering run, **spear levelled forward** at David (was sideways), shield forward |
| `goliath_hit_react` | 28 | 0.93 | no | **impact 0** | head snaps back (peak frame 3), steps back with the right foot, wobbles |
| `goliath_fall` | 54 | 1.80 | no | knees 16 / 0.53, **ground 36 / 1.20** | dizzy sway and **two stagger steps back (0.20)**, knees buckle, pivots about the knees onto his face toward +Z, arms come to rest on the page beside the chest, head turns onto the right cheek; hands open at 20/22 and **spear and shield fall free** and lie beside him. **Root motion** |
| `goliath_down` | 60 | 2.00 | yes | — | lying (= last frame of `fall`, same root offset 0.259), slow breathing |

Pose markers are Blender `pose_markers`; glTF has no markers, so the times above (also in `clips.json`) are the
reference for Integration / FX / SFX. `timeline.json requestedClips` is empty.

## 3. Measured (build / verify, 2026-10-27)

All numbers are in `clips.json → clips[].checks` and are recomputed on every `build`.

- **Loop seams:** 0.000000 for all 10 loops. **GLB round trip:** 19 animations, frame ranges as above, nothing missing
  against §5; joint positions at frames 0, N/2, N differ from the build by at most **8e-6** units.
- **Ground contact** (`meshMinY`, lowest deformed vertex of all meshes over the clip, sampled every 2–3 frames;
  0 = the page): David −0.001…−0.002 in every clip; Goliath −0.004…−0.010 (deepest: boot toes at toe-off in `walk`
  −0.0095 and `charge` −0.0089, i.e. ≤ 1.6 mm on the printed page; the lying body in `down` −0.003).
  The first build had a root-frame bug that tilted the planted feet and sank the heels by 0.021 (David) / 0.049
  (Goliath); fixed (IK targets and foot orientation now use the posed root delta, not the root bone's rest frame).
- **Foot sliding** (`plantedToeDriftMax`, horizontal drift of a planted toe): 0.000 in idle/talk/windup/victory/taunt/
  laugh/hit_react; roar 0.012 (wider stance on the roar, deliberate step), release 0.012 (the follow-through step).
  Kneel/pray/fall report the planned foot moves (kneeling foot sliding back; stagger steps), not slides.
  In-place locomotion slides by design: the Director moves the actor (§5).
- **Kneel at the brook** (v3 stones of §12.5, `pickHandToStone`, nearest of knuckles / finger / thumb joints to the
  stone top at each pick): **0.016, 0.010, 0.010, 0.013, 0.013** (`pickWristIkError` 0.012–0.022). Facing the viewer
  without the turn the hand stopped 0.032 short of stone 1 (0.13 away, behind his hip), hence the turn. The planted right
  foot is kept off the stone line (a bigger step toward the stones put it on stone 4). `kneelOnPage`: lowest points
  reach z ≤ 0.236 (page front edge 0.244) and x ≥ −0.423 (the hand at the stones); `desertPenetration` only the
  pinching fingers inside stones 3 / 5 by ≤ 6 mm (those stones are hidden at their pick).
- **Desert collision** (new): `desert_penetration()` ray-casts the real `desert.glb` meshes. `goliath_fall` / `down`
  lying body: **no penetration** (`fallFootprint.desertPenetration {}`); `desertOverlap` (design footprints, now the
  3D `footprintSheet`, ±0.01) lists `rockM2` because his boots end within 6 mm in front of it, not in it. The preview
  checks every 6th frame of the whole performance (`preview.json stageViolations`).
- **Goliath on the paper** (`fallFootprint`, every vertex of the last frame of `fall` / `down`, at the timeline mark
  (0.16, −0.22), facing the viewer): x −0.037…0.472, z −0.754…+0.200, inside the D8 paper (x ±0.596,
  z −1.486…+0.22): **onPaper true**, and no desert footprint touched (`desertOverlap {}`). The first build put the
  helmet at z ≈ +0.5, off the page.

## 4. How the motion is made

The script is the source; there are no hand-placed keys. Each clip is a Python function frame → channels (rotations in
design axes applied in the bone's rest frame, Catmull-Rom keys, wrapped for loops), then:

- **Legs** are a two-bone IK to ankle targets with heel / ball / toe ground contact. **Arms** use the same IK when a
  clip asks for it (kneel reach, prayer, lying arms), with targets in root space or in a bone's frame (`ikspace`).
- **Fingers** (§11.6): channel `curl` on `fingers*`, `fingerTips*`, `thumb*` (+ = toward the palm, about the hand's
  hinge axis). `fist(side, open)` opens a modelled fist (0 = closed grip at rest, 1 = straight);
  `open_hand(side, curl)` curls David's modelled-open left hand.
- **Sling**: Verlet chain hanging from the hand (gravity 2.0 units/s², damping 5/s; 16/s while kneeling so the cords
  do not flail while the hand moves), or a whirl circle with lagging segments; after the release the chain is simulated
  again, seeded with the whirl velocity.
- **Spear**: damped spring lagging the hand; upright like a staff in idle/walk/talk/laugh (`spear.up`), aimed in
  `charge` (`spear.aim`), free in `fall`. The grip slides along the shaft so the butt spike never goes under the page.
- **Fall**: stagger by root translation, then root rotation pivoting about the knee midpoint; the body is lifted so the
  armour rests on the page. Spear and shield leave the hands at frames 20 / 22 and drop (ease-in) to their resting
  places (`SPEAR_REST`, `SHIELD_REST` in the script): spear along his right side (world x ≈ 0.03, z −0.74…+0.20),
  shield face up beside his left hip (world ≈ (0.40, −0.52)).
- Sampled at 30 fps, one key per frame per bone (quaternion, location, scale), linear.

## 5. The stone and the five brook stones

- Bone `stone` (child of `root`) sits in the pouch every frame (rest offset to `slingPouch`), including idle/walk.
- `kneel_pick`: scale 0 until **pick5 (frame 82)**, in the right hand 82–87, in the pouch from 88.
- `clips.json → david_kneel_pick.desertEvents`: hide `desert/fiveStones/stone1..5` at pick1..pick5 (frames 34, 46, 58,
  70, 82; unchanged frames, the hand targets follow the §12.5 stone positions). The hand targets are read from `desert.glb` itself, relative to David's kneel mark from `timeline.json`, so
  if the Desert role moves a stone or Story moves the mark, `build` follows.
- `sling_release`: leaves the pouch at frame 2, ballistic (g = 2.0) to David-local (0, 0.69, 0.33), arriving at 0.450 s
  (timeline release 72.60 → `stone_hit` 73.05), pops back, bounces once and lies on the page. 0.69 is Goliath's brow
  line on the new model (chin 0.645, helmet rim ≈ 0.713).

## 6. Natural locomotion speeds (in-place clips; the Director moves the actor)

| Clip | Stride / cycle | Speed (units/s) | Needed by the timeline (preview log) |
|---|---|---:|---|
| `david_walk` | 0.060 / 0.80 s, duty 0.58 | 0.129 | 1.0 s: 0.056 · 26.6 s: 0.040 · 51.4 s: 0.119 · 56.2 s: 0.110 · 77.2 s: 0.077 |
| `david_run` | 0.070 / 0.53 s, duty 0.40 | 0.328 | 68.6 s: 0.064 |
| `goliath_walk` | 0.100 / 2.20 s, duty 0.64 | 0.071 | 1.0 s: 0.074 (matches) |
| `goliath_charge` | 0.150 / 2.00 s, duty 0.60 | 0.125 | 69.0 s: 0.019 |

Feet do not skate when the actor moves at the natural speed; otherwise scale the clip rate by `actual / natural`. The
preview clamps that rate to 0.5–1.5, so the run at 68.6 s and the charge at 69.0 s still slide (unchanged Story issue).

## 7. Preview

`anim/preview.mp4`: 640×360, 30 fps, 89.0 s, H.264 + AAC (`preview_mix.mp3`). EEVEE (8 samples, sun + sky), the A4 page
with the desert set from `desert.glb` standing on it (water film on the brook), characters with the face decal that
`design.json faceDecals.clipExpression` gives for the current clip. A small stand-in Director: actors start at
`design.json sheetX` (−0.350 / +0.130), move linearly to `acting.to`, face the travel direction while moving and the
`face` target otherwise (0.12 s turn), cross-fade clips over `blend`, play locomotion clips at `actual/natural` speed
clamped to 0.5–1.5. Desert stones disappear at the picks; David's stone shows from pick5 until `sling_release` is left.
No FX. The camera follows the shot list. `$DG_ANIM_WORK/preview.json` logs every locomotion speed.

## 8. Open issues and requests to other roles

1. **Integration — expressions and stones.** Switch the face decal per clip (`clipExpression`); hide
   `desert/fiveStones/stoneK` at the `desertEvents` times; show `david_stone` from `kneel_pick` pick5 (2.73 s) and hide
   it again when `sling_release` is left (otherwise it pops back into the pouch).
2. **Integration — kneel root motion (new in v3).** `david_kneel_pick` now has root motion (yaw to −45° and a 0.03
   shift, back to zero by its last frame). Play the root bone as is, keep the actor transform at the mark facing the
   viewer, do not "apply root motion". Not checked in Unity.
3. **Integration — fall root motion.** Keep the actor transform fixed during `fall` → `down`; the root bone carries the
   stagger and the topple (do not "apply root motion"). The on-paper result assumes Goliath stands at (0.16, −0.22)
   and **faces the viewer (yaw 0)** when `fall` starts, as `timeline.json` says (`face: viewer`). Lying, he occupies
   x −0.04…0.47, z −0.75…+0.20. If the mark or the facing changes, re-run `build` and read `fallFootprint`.
4. **Integration — stone target.** The flight is baked to David-local (0, 0.69, 0.33); it meets the brow only if the
   actors are 0.39 apart facing each other at 72.6 s (true for the current timeline).
5. **Integration — glTFast mirrors X** (LESSONS L26): conjugate quaternions as for the angel. Not checked in Unity.
6. **Story — locomotion speeds** (§6): the run (68.6 s) and the charge (69.0 s) cover far less ground than their clips
   do, so feet slide. Shorten those windows, lengthen the moves, or accept the slide.
7. **Story — scripture vs. stage.** 1 Sam 17:49 "fell upon his face" is kept, toward the viewer. To fit the paper he now
   staggers back 0.20 first (a dizzy stumble). Falling back-first would need no stagger and would show the dizzy face
   from above, but contradicts the verse; that choice is the owner's.
8. **Sheet role.** Renders use Design's v3 demo mock until `sheet/demo-colored.png` is rebuilt for v3; then re-run
   `contact` and `preview` (picked up automatically by modification time).
9. **Blender role (seen in the renders).** The hands and fingers sample white from `uvproof.png` (the hands of both
   characters render white/very pale): check UV0 of the hands against the ID render. Fists opened fully (Goliath's fall,
   David's pray) look slightly glove-like (RIG.md §4).
10. **Not checked:** Unity / phone; whether glTFast plays the banner wave clips in `desert.glb` (Desert role).

## 9. What still looks weak (honest)

- Opening a modelled fist (David's right hand in `kneel_pick` and `pray`, Goliath's hands in `fall`) stretches the palm
  a little; pinch poses read at preview size but are not anatomically precise. Fingers are one shared bone chain (§11.6),
  so there are no individual finger gestures (no pointing index finger).
- `kneel_pick` stone 1 is at the edge of reach: the hand stops ~1.6 cm (units) above it at full stretch.
- The transition blend from `kneel_pick` into `walk` (56.2 s) passes through a wide-legged in-between for ~0.3 s.
- Goliath's fall reads as "stumbles back, then falls forward", which is a cartoon beat, not physics.
- In the preview the fallen Goliath and David are 0.16–0.22 apart; from some shot angles David appears to stand on
  him (depth overlap only).
