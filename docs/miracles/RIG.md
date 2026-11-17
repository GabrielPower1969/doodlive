# Real Miracles — rigs (Characters role)

Built by `pipeline/mi_characters.py` (`python3 pipeline/mi_characters.py all`: faces, build + friends, proof, preview,
uvcheck, posetest, verify, compose). Models: `assets/miracles/model/{jesus,peter,man,friend1,friend2,friend3,friend4}.glb`
(character-local, no animations), `characters.blend` (the cast at their sheet slots, the friends off the page at
x 0.80 / 1.00 / 1.20 / 1.40), sheet data `regions_characters.json` + `id_characters_2x.{png,json}`, friends' fixed paint
`friend_paint.png`, previews `preview_{man,jesus,peter,friends,all,uvcheck,pose}.png`, face decals
`docs/miracles/design/faces/` (overview in `overview.png`).

## 1. Measured (re-imported GLBs, `verify`)

| | man | jesus | peter | friend1 | friend2 | friend3 | friend4 |
|---|---|---|---|---|---|---|---|
| Triangles (budget) | 23,344 (25k, incl. mat 2,104, ropes 720, matRoll 1,380) | 24,648 (25k) | 24,916 (25k, incl. bucket 668) | 17,128 (18k) | 17,560 (18k) | 17,776 (18k) | 17,808 (18k) |
| Top (contract) | 0.3378 (0.34, −0.65 %) | 0.3553 (0.36, −1.3 %) | 0.3810 (0.38, +0.3 %) | 0.3483 (0.35) | 0.3685 (0.37) | 0.3279 (0.33) | 0.3630 (0.36, tip of the cap) |
| Lowest point | 0.0015 (bare soles) | 0.0002 (sandal soles) | 0.0002 | 0.0002 | 0.0002 | 0.0002 | 0.0002 |

All seven: bones = CONTRACT §3 exactly (names and parents), 0 animations, ≤ 4 influences per vertex, UV0 = page
projection, UV1 = decal layer.

## 2. Skeletons

Kit skeleton, A-pose (arms 55° below horizontal), facing +Z, feet on y = 0:
`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids`.

| Char | Extra bone | Parent | What it moves |
|---|---|---|---|
| jesus | `mantle1` | chest | the mantle's hanging back drape |
| jesus | `belt1` | hips | the tan belt's hanging end (with fringe) |
| peter | `cloth1` | head | the head-cloth knot tails at the back of the head |
| peter | `bucket` | handR | prop `peter_bucket` (hidden), hangs from its rope handle in the right fist |
| man | `mat` | root | prop `man_mat` (pad + two poles, **shown**) |
| man | `ropes` | mat | prop `man_ropes` (four ropes from the mat corners rising 0.45, hidden) |
| man | `matRoll` | chest | prop `man_matRoll` (rolled mat with a cord, on the left shoulder, hidden) |
| man | `sash1` | hips | the mustard sash's hanging end |
| friend1-4 | `belt1` | hips | tan belt end |
| friend3 | `band1` | head | head-band tail |

- **Blink**: scale `eyelids` local Y from 1.0 (open) to **12.78** (closed); X/Z stay 1 (all seven; checked closed in
  `preview_pose.png`).
- **Jaw**: `jaw` rotates the chin and beard; every open mouth is a face decal (`talk`, `smile`, `laugh`, `shock`,
  `wail`, `amazed`, `wonder`, `joy`, `cheer`, `idea`, `oof`).
- Props are separate meshes `<char>_<prop>`, parented to their bone (not skinned). Show / hide by node
  (`regions_characters.json` `props.*.node`, e.g. `man/mat`).

## 3. The man's mat (CONTRACT §3)

- **Rest placement** (measured on the GLB): pad 0.30 × 0.12 centred at (0, 0, −0.02), long axis along X, top at
  y 0.025 (poles reach y 0.0276); poles along the long sides at z −0.02 ± 0.0675, ends at x ±0.20 (with the caps
  ±0.2036). The `mat` bone sits at the root; in every lying clip leave it there and move the body onto the mat.
- **Lying test** (`pose_lie` in the script, `preview_pose.png` "man lie / lieq / liephone"; not a clip): hips
  rotated so the head points to −X and the face up, hips head at (0.012, ≈0.046, −0.02) rig-local, neck +14° (head a
  little raised), upper arms in to the sides (Z −22° × side, X −22°), forearms flexed 100° and turned 70° inward so the
  hands lie folded on the chest, `sash1` +12° so its end rests on the thigh. The body then rests 1 mm above the mat top
  (lowest body point 0.026). Use these numbers as the start of `lie_mat`; `MI_LIE_ARM` / `-- lie` re-render only this test.
  The man is 0.34 long and the pad 0.30: his head and his toes reach a little past the pad ends (inside the poles).
- `carried`: the friends' hands are at the pole ends (x ±0.20, z −0.02 ± 0.0675) at y ≈ 0.15 when the mat bone is at
  local y 0.05 on base 0.10 (CONTRACT §4).
- `ropes`: four ropes from the pad corners straight up 0.45 (their tops are at the roof hole when the root is at
  local y 0); hidden by default, scale them in for `lowered`.
- `matRoll`: hidden; the switch `mat` → `matRoll` in `roll_mat` is a timeline event (props).
- **On the sheet** the mat prints as its own shape: its top, stood up to face the viewer, centred at
  `matSheet` = (−0.28, 0.47) (default; `design.json characters.man.matSheet = [x, y]` overrides it; the Set role has
  not set one yet). The GLB has it flat (the stand-up is only for the ID render and UV0).

## 4. Expressions (`docs/miracles/design/faces/<char>_<expr>.png`, 512 px)

- jesus: `kind` (default), talk, smile, laugh, sleep, firm, gentle, look_up
- peter: `jolly` (default), talk, shock, wail, laugh, scared, amazed, squint
- man: `shy` (default), talk, nervous, hope, wonder, joy, laugh
- friends (one shared set, files `friend_<expr>.png`, identical head proportions for all four): `happy` (default),
  talk, strain, oof, think, idea, cheer

Suggested clip → decal map: `CLIP_EXPRESSION` in the script and `regions_characters.json` `faceDecal`.

## 5. Colour: regions, fixed colours, anchors

| Char | Printed regions | Fixed colour (decal swatch; UV0 anchored, prints as detail lines) | Hidden-prop UV0 |
|---|---|---|---|
| man | skin, hair (+ beard), tunic, sash, mat, stripes | `poles` (dark wood) and `ropes` (hemp) → anchored to `mat` | `matRoll`: roll → `man.mat`, rollStripes → `man.stripes` |
| jesus | skin, hair (+ beard), tunic, mantle, belt | `sandals` → `tunic` | — |
| peter | skin, hair (+ beard), headcloth, tunic, vest, waistcloth | `sandals` → `tunic`, `rope` (belt) → `waistcloth` | `bucket` → `set.hull` (the boat hull) |

Hands, legs, knees and Peter's bare arms print as slivers; their UV0 takes the face skin (`PART_ANCHORS`). Jesus' belt
fringe takes the belt. In the uvcheck the anchored fixed-colour parts (poles, sandals, rope) therefore show the
anchor region's colour; in the app the swatch colour on UV1 wins.

The friends are not on the sheet: `friend_paint.png` (their own front ID render on a virtual page, Esther `GUARDS`
method) on UV0, material `mi_friend_paint`; they never take the child's colours.

Printed sizes below 6 mm (from the Set role's `assets/miracles/sheet/checks.json`, best inscribed cell, px at 150 dpi;
6 mm = 35.4 px): man hair 7.2 px, beard 8.2, face 32.0, sash 34.0; jesus hair 10.0, beard 17.9, belt 27.9, face 32.6;
peter hair 7.2, beard 18.1, headcloth 16.0, waistcloth 16.0, face 30.3. Heads and hair are small on every sheet (C3).
The mat (6.6 cm wide on A4) and each red stripe (0.04 wide) are above 6 mm.

## 6. Notes for Animation

- Hands: the man and the friends are thin; Peter has big forearms and hands. Grip point for props = `fingers*` head.
- Jesus' mantle panel covers the front and back of the body down to the shins; bend `mantle1` for the back drape
  only. The long cream tunic shows below the mantle and as the right sleeve.
- Peter's head-cloth tails (`cloth1`) hang behind the head; keep them clear of the neck in `shake_awake` / `bail`.
- Friend silhouettes: friend1 slim leader (orange, short black hair), friend2 big and round (teal, bald with a fringe,
  short beard, wide belly — leave room in `carry_*`), friend3 small (yellow, curly hair, red head band, `band1`),
  friend4 lanky (purple-blue, pointed red cap; the cap tip is the top 0.363).
- Lying / kneeling clips keep meshMinY ≥ −0.008 (the lying test above gives 0.026 on the mat).

## 7. Weak / not verified

- `jesus_look_up`: the eyes look up only a little; may need a stronger decal for `look_up_smile` from the phone view.
- friend4 reads "lanky" mostly by the cap; the body is only slightly narrower than friend1.
- The man's feet and head overhang the 0.30 pad slightly when lying (pad size is fixed by the contract).
- Peter's open-mouth decals sit small inside the thick beard.
- Nothing was looked at in Unity or on the phone; the lying pose is a test pose, not the `lie_mat` clip.
