# Saul Sees the Light! — rigs (Characters role)

Built by `pipeline/sa_characters.py` (`python3 pipeline/sa_characters.py all`: faces, build + extras, proof, preview,
uvcheck, posetest, verify, compose). Models: `assets/saul/model/{ananias,saul,barnabas,judas,priest,tallguard,shortguard,peter}.glb`
(character-local, no animations), `characters.blend` (the cast at their sheet slots, the extras off the page at
x 0.80 / 1.00 / 1.20 / 1.40 / 1.60), sheet data `regions_characters.json` + `id_characters_2x.{png,json}`, the extras'
fixed paint `extras_paint.png`, previews `preview_{ananias,saul,barnabas,extras,all,uvcheck,pose,fit}.png`, face
decals `docs/saul/design/faces/` (overview in `overview.png`).

## 0. Reuse (CONTRACT §2)

`sa_characters.py` runs `pipeline/rs_characters.py` in its own namespace (definitions only); that file runs
`ls_characters.py`, which runs `mi_characters.py`, the same way. Nothing was copied from a builder, nothing in
`mi_*`, `ls_*`, `rs_*` or the kit was edited, nothing moved into `story_kit/` (no other pack regenerates).

| Actor | Builder |
|---|---|
| `peter` | He Is Risen! `build_peter_rs` = Miracles `build_peter`, unchanged; `bucket` mesh dropped, bone kept |
| `saul` `ananias` `barnabas` `judas` `priest` `tallguard` `shortguard` | Miracles `build_friend`, unchanged, + this pack's costume (`build_<id>` in the script) |

Costume parts on the friend body use kit / earlier-pack helpers: The King Who Serves `_extra_beard` (Saul neat, Barnabas
/ Judas / short guard short), kit `build_beard` (the priest's long beard), kit `head_lathe` (Ananias's cap, Judas's
striped cloth, the turban, the guards' caps), kit `waist_band` (the wide belts), kit `mantle_point` (cloak, shawl,
mantle, over-robe). Robes longer than the friend's knee tunic (Saul and Barnabas to the shins, Ananias and the priest
to the ankles) re-run kit `build_robe` with the friend's own rows, sleeves and fold numbers, only a lower hem
(`_long_robe`). The friend's hanging belt end (`belt1`) is merged into `hips` and its mesh dropped (as The King Who
Serves); Barnabas's curly-hair red band is dropped (`band1` merged into `head`).

## 1. Measured (re-imported GLBs, `verify`, 2026-11-18)

| | ananias | saul | barnabas | judas | priest | tallguard | shortguard | peter |
|---|---|---|---|---|---|---|---|---|
| Triangles (budget) | 18,920 (25k) | 19,952 (27k) | 18,268 (25k) | 17,892 (18k) | 17,950 (18k) | 17,978 (18k) | 17,574 (18k) | **24,248 (18k)** |
| Top (contract) | 0.3305 (0.33) | 0.3709 (0.37) | 0.3900 (0.39) | 0.3507 (0.35) | 0.3598 (0.36) | 0.4139 (0.41) | 0.2989 (0.30) | 0.3810 (0.38) |
| A-pose half width (sheet, contract) | 0.130 | 0.136 | 0.141 (≤ 0.14) | — | — | — | — | — |

All eight: bones = CONTRACT §3 exactly (names and parents), 0 animations, ≤ 4 influences per vertex, lowest point
0.0002, UV0 = page (printed) or paint (extras), UV1 = decal. Peter is over the 18k extras budget because he is the
unchanged Miracles Peter (same as He Is Risen!); reducing him means forking him: lead's call.

## 2. Skeletons and props

Humans: kit skeleton, A-pose (arms 55° below horizontal), facing +Z, feet on y = 0. Props are rigid meshes
`<char>_<bone>` parented to their bone; node `<char>/<bone>`.

| Char | Extra bone | Parent | What | Default |
|---|---|---|---|---|
| saul | `cloak1` | chest | lower back of the travel cloak (back hem at the calves) | — |
| saul | `letters` | handR | `saul_letters`: scroll 0.06 long, tied with a cord, across the fist | hidden |
| saul | `bread` | handR | `saul_bread`: round flat loaf 0.05 across, flat on the palm | hidden |
| saul | `basket` | hips | `saul_basket`: woven basket 0.10 across, 0.08 high, floor 0.05 below the hips head | hidden |
| saul | `ropeTop` | root | fixed at rig-local (−0.065, 0.235, 0); the window ends of the ropes | — |
| ananias | `jug` | handR | `ananias_jug`: terracotta jug 0.06 high, one handle, hangs from the fist by the handle | hidden |
| barnabas | `mantle1` | chest | the back of the cream mantle (left shoulder round the back to the right hip) | — |
| judas | `bread` | handR | `judas_bread`: the same loaf | hidden |
| tallguard | `lantern` | handR | `tallguard_lantern`: small clay lantern hanging 0.03 below the fist on a cord | hidden |
| peter | `cloth1`, `bucket` | head, handR | Miracles head-cloth tails; `bucket` bone only, **no mesh** | — |
| priest, shortguard | none | | | |

- **Blink**: scale `eyelids` local Y from 1.0 (open) to **12.78** (closed); X/Z stay 1 (all eight).
- **Jaw**: as Miracles (chin / beard move; every open mouth is a decal, C6).
- **Cloth bones** (pose test): `cloak1` +25° about X swings the cloak back, `mantle1` +20°.

### The basket rig (Saul, S11)

- `saul/basket` is one prop for the basket **and** the ropes. In the GLB the skinned node `saul_ropes` sits under the
  `basket` joint (`_ropes_under_basket`; glTF ignores a skinned node's own transform), so StoryDirector's prop
  (every renderer under the bone) shows / hides both. Blender's exporter only skins object-parented meshes, hence the
  JSON move after export. **Not checked in Unity** (glTFast should accept a skinned node inside the joint tree; the
  lead should look once).
- `saul_ropes`: two ropes (r 0.0018) from the rim on the −X side (toward the wall) to ropeTop ±0.007 in z. Skin:
  `basket` at the rim ends, `ropeTop` at the window ends, linear in between, so lowering the hips stretches them.
  Rope rings are horizontal: the ropes stay round when stretched vertically; in the rest pose (rim 0.015 below
  ropeTop) they are short and flat (hidden anyway).
- Posetest, Saul's base at BASKET_DOWN facing +Z, stand-in wall face at rig x −0.065:
  - `basket_wait` (basket floor 0.17 above the base): **hips +0.023** from rest. Basket nearest the wall at x −0.053
    (clears the face by 0.012). Rope tops x −0.064, y 0.233-0.251 (inside the window 0.20-0.27, below the wall top).
  - `basket_down` (floor on the ground): **hips −0.147** from rest; ropes stretch to 0.152, tops unchanged.
  - Hips offset for any floor height F: `hips.location.y = F − (hipsRestY − 0.05)`, hipsRestY = 0.1967 for Saul.
- **Fit**: the basket is the contract size (0.10 across). A crouched Saul does not fit inside it: in the test crouch
  (thighs −105°, shins +125°) the knees and feet stick out at the front and the feet go 0.04 below the basket floor.
  The clips need a tighter fold (knees up to the chest, feet tucked under) or the lead may widen the basket to 0.12
  (it then clears the wall face by only 0.005).

## 3. Fit tests (`posetest`, `preview_fit.png`; test poses, not clips)

- Props shown in hand: letters, bread (Saul, Judas), jug, lantern: all read; the jug and lantern hang below the fist.
- Saul seated on the ground (hips head 0.04): the robe and sandals of this crude test pose go to y −0.064; the
  `fall_down` / `sit_look_up` clips must place the hips higher (A6: ≥ −0.008).
- Saul / Peter at 0.10 in rest poses facing each other: the sandal toes touch; the hug clip must step in with
  bent knees, not slide (A1).
- The guards side by side read as the comic pair (0.41 with the cap / 0.30).

## 4. Expressions (`docs/saul/design/faces/<char>_<expr>.png`, 512 px)

- saul: `angry` (default S01-S04), shout, shock, look_up, blind, pray, see, `kind` (default from S08), talk, laugh,
  chew, whisper (all new)
- ananias: `gentle` (default), talk, look_up, fright, gulp, brave, joy, whisper (all new)
- barnabas: `happy` (default), talk, laugh, kind (new)
- priest: `grave` (default), talk (new)
- judas: `happy` (default), talk, amazed, laugh; tallguard / shortguard: `happy` (default), talk, amazed, shock, puff,
  sleepy, asleep, puzzled. The group drawings use the same parameters as the Miracles / The King Who Serves / He Is
  Risen! friend drawings, re-drawn per person with his own brow colour; puff, sleepy, asleep, puzzled are new.
- peter: `jolly` (default), talk, shock, laugh (copied, Miracles), sad (copied, He Is Risen!), **afraid** (new)

Clip → decal suggestions: `CLIP_EXPRESSION` in the script and `regions_characters.json` `faceDecal.clipExpression`.

## 5. Colour: regions, fixed colours, anchors

| Char | Printed regions | Fixed / anchored | Hidden props → (fallback until the set exists) |
|---|---|---|---|
| ananias | skin, hair (fringe + beard), cap, tunic (robe), shawl | sandals → tunic (swatch) | jug → set.waterJar (barnabas.tunic) |
| saul | skin, hair (+ beard), tunic (robe), cloak, belt (+ pouch) | sandals → tunic (swatch) | letters → set.synagogue (barnabas.mantle); bread, basket + ropes → set.breadBasket (ananias.shawl) |
| barnabas | skin, hair (+ beard), tunic (robe), mantle, belt (the sash) | sandals → tunic (swatch) | — |

Hands, bare arms, knees and legs take a texel of the face skin (PART_ANCHORS, as Miracles). The set regions are
looked up from `assets/saul/model/set_id_2x.*` + `design.json`; when the Set + sheet role writes
`design.json set.propAnchors` (`saul/letters`, `saul/bread`, `saul/basket`, `ananias/jug`) those win. **Re-run
`sa_characters.py build` after the set exists** so the props pick up the set colours (they currently use the
character fallbacks: the letters are cream from Barnabas's mantle, bread and basket mustard from Ananias's shawl, the
jug orange from Barnabas's robe). Extras (not printed): UV0 → `extras_paint.png` (material `sa_extras_paint`), props
shown in their ID render so bread and lantern get their colours. Region sizes on the A4 are for the sheet role to
measure; Saul's belt band is 0.030 tall and Barnabas's sash 0.028 (both meant to be ≥ 6 mm).

## 6. Notes for Animation

- Basket clips: move the **hips** (not the root) by the offsets in §2; the basket follows the hips, `ropeTop` never
  moves. Fold the legs tighter than the test crouch so knees and feet stay inside the basket.
- Cloak (Saul): the part below the hips is 25 % on the legs (skirt weights), the rest on `cloak1`; swing `cloak1`
  back (+X rotation) on `march`; in deep crouches and seated clips check the cloak hem against the legs.
- Long robes (Saul, Barnabas, Ananias, priest) use kit skirt weights; kneeling clips will need the usual robe check.
- Barnabas's mantle hangs from the left shoulder: `mantle1` is the back panel; the front-left part follows the chest.
- Peter's `peek_afraid`: the Miracles head cloth swings on `cloth1`; keep his face visible from the S12 camera.

## 7. Deviations from CONTRACT / DESIGN (recorded, not silent)

- Peter 24,248 triangles vs the 18k extras budget (unchanged Miracles Peter; same as He Is Risen!).
- `saul_ropes` is a skinned mesh whose GLB node was moved under the `basket` joint after export (§2); not verified in
  Unity.
- Basket kept at the CONTRACT size 0.10 × 0.08 (DESIGN §1 says 0.13 × 0.10); Saul does not fit it in a naive crouch.
- The hidden props use character-region fallbacks until the set's ID render and `design.json` exist (§5).
- Saul's and Barnabas's robes stop at the mid-shin, Ananias's and the priest's just above the sandals; Judas and the
  guards keep the friend's knee tunic (DESIGN says "tunic" for them).

## 8. Weak / not verified

- Nothing looked at in Unity or on the phone; the ropes-under-joint trick is the main risk.
- Saul's cloak flares out over the shoulders (pushed round the sleeve roots) like small epaulettes.
- Ananias's shawl reads more like a short vest from the front.
- Basket fit, seated height and hug spacing were measured with crude test poses, not clips.
- Regions under 6 mm on the A4 not measured here (sheet role); faces and hair are small as in every pack.
