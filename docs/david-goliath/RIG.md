# David & Goliath — character models, rig, weights (Blender role)

Owner: Blender (characters). Binding contract: [CONTRACT.md](CONTRACT.md) §11 (redraw of 2026-10-27, "no balloon
models"). Numbers come from `assets/david-goliath/design.json` version 2 (Design role); the pictures to match are
`docs/david-goliath/design/turnaround-*.png`. Since §11.1 the colouring sheet (`tools/make_dg_sheet.py`, `sheet/`,
`print/`) belongs to the **Sheet** role and the desert (`desert.glb`) to the **Desert** role; this document covers the two
characters only.

```
DG_WORK=/tmp/dg_work   (default)
blender -b --factory-startup --python pipeline/dg_build.py -- build     # ~20 s: models, rig, weights, UVs, ID render,
                                                                        #   previews, pose test, GLBs, dg_characters.blend
python3 tools/make_dg_sheet.py                                          # Sheet role: line art etc. from the ID render
blender -b --factory-startup --python pipeline/dg_build.py -- uvcheck   # models wearing a texture through UV0 / UV1
blender -b --factory-startup --python pipeline/dg_build.py -- verify    # re-import GLBs: bones, skins, props, budgets
python3 pipeline/dg_compose.py                                          # model/preview_*.png, pose_test.png, uv_check.*
```

UV proof without the Sheet outputs (used for this redraw, because `make_dg_sheet.py` still reads the removed
`sheet.decorSuggestion` and stops):

```
python3 pipeline/dg_compose.py proof                                    # $DG_WORK/uvproof.png = ID render in palette colours
DG_UV_TEXTURE=$DG_WORK/uvproof.png blender -b --factory-startup --python pipeline/dg_build.py -- uvcheck
DG_UV_TEXTURE=$DG_WORK/uvproof.png python3 pipeline/dg_compose.py
```

(`model/` = `assets/david-goliath/model/`.) Checked 2026-10-27 with Blender 5.2.3.

## 1. What is in the GLBs

| | David | Goliath |
|---|---|---|
| Triangles (budget ≤ 20,000, §11.5) | **19,908** (body 19,628 + stone 280) | **19,662** (body 16,134 + helmet dome 1,120 + neck guard 596 + crest 300 + crest holder 72 + shield 960 + spear 480) |
| Skinned mesh | `david_body`, one mesh, 33-bone skin | `goliath_body`, one mesh, 32-bone skin |
| Rigid props (child nodes of one bone) | `david_stone` → `stone` | `goliath_helmetDome`, `goliath_helmetGuard`, `goliath_crest`, `goliath_crestHolder` → `helmet`; `goliath_spear` → `spear`; `goliath_shield` → `shield` |
| Armature node | `david_rig` | `goliath_rig` |
| Material | one, `dg_page` (white; the app puts the scanned page on it) | same |
| Vertex attributes | POSITION NORMAL TEXCOORD_0 (page) TEXCOORD_1 (face decal) JOINTS_0 WEIGHTS_0, ≤ 4 influences | same |
| Animations | none (0 actions after re-import) | none |

- **Character-local coordinates**: root bone at the origin, feet on y = 0, facing +Z, 1 unit = art width. Sheet position
  `design.json characters.<id>.sheetX/sheetY`: David (−0.350, 0.015), Goliath (+0.130, 0.015) (§11.4).
- **Rest pose** = `design.json bonesLocal` exactly: arms 45° below horizontal; David's right fist holds the sling, left
  hand open (fingers together, thumb forward); Goliath's right fist on the spear, left fist behind the shield.
- `model/dg_characters.blend` holds both rigs **at their sheet positions** with all meshes, for the Animation role.
- Front silhouettes match Design's figure rectangles (page px, from the ID render): David 151/1192, 239 × 302
  (design 150/1191, 243 × 305); Goliath 432/540, 656 × 952 (design 434/540, 655 × 956). David's hair top is 0.301.

## 2. How the meshes are made (§11.2, §11.5)

Everything is procedural in `pipeline/dg_build.py`; nothing is joined from visible primitives.

- **Cages with edge loops.** Each body part is a quad cage of rings: a ring at every joint (shoulder, above/at/below the
  elbow, wrist, knuckles, finger joints, hip, knee, ankle). Ring shapes come from the turnaround's front and side
  outlines (the same numbers `make_design.py` draws with), so limbs taper, with biceps, elbow point, forearm bulge,
  kneecap, calf, ankle bones and Achilles.
- **Box-modelled ports.** Hands: the knuckle end of the palm is a strip of five quads; four are extruded into fingers
  (index, middle, ring, little; lengths 0.94/1.0/0.94/0.76), the fifth closes the edge; a side quad of the palm is
  extruded into the thumb. Garments: a rectangle of faces on each side of the tunic/armour body is removed and the
  sleeve is extruded from that opening, so body and sleeve are one shell.
- **Heads.** Rows of a closed spline through front / front-side / side / back-side / back points (jaw angle, cheekbones,
  chin, nape), denser at the front. After subdivision the face gets nose (bridge, tip, alae, nostrils), brow ridge,
  shallow eye sockets, cheekbones, upper and lower lip and chin. Ears are separate small shells with a rim and a hollow,
  sunk into the head. David: curly hair shell (≈120 curls, fringe curls, sideburns, nape) tucked into the skin at its rim.
  Goliath: beard volume over jaw and chin that hangs below the chin with locks, a thinner patch under the lower lip so
  the mouth decal reads, and a separate drooping moustache.
- **Subdivision Surface level 1 is applied** to the head + neck, both arms with hands and fingers, the ears, the hair,
  the sandal soles, the bag, the sling pouch, the sash knot, the strap and the stone; weights are painted on the cage
  and interpolated by the modifier. **Deviation:** larger smooth shells are built directly at their final ring density
  without the modifier (legs and feet, tunic, armour, kilt, greaves, bracers, belt/sash/strap bands, helmet, crest,
  spear, shield). Applying level 1 to them as well puts Goliath at about 47k triangles (measured); building them at
  final density instead gives the same smoothness for about a quarter of the cost.
- **Hidden body removed.** There is no torso under the clothes; the skull under David's hair and Goliath's helmet, the
  back of Goliath's head inside the neck guard, his chin under the beard, the neck inside the collar, the shoulder
  caps inside the sleeves, the thighs inside tunic/kilt and Goliath's shins inside the greaves are culled. So the skin is
  five pieces per character (head + neck, two arms with hands, two legs with feet), each continuous, each closed or
  ending under cloth.
- **Clothes with thickness.** Tunic, armour and kilt have rolled hems (the edge turns 3–10 mm inward) at the neckline,
  sleeve ends and bottom hem, not a full Solidify (budget); the bag flap, sling pouch, Goliath's beard, greaves and
  helmet neck guard use Solidify. David's tunic has 12 soft skirt folds; Goliath's kilt has 18 knife pleats; his
  armour has 10 rows of overlapping bronze plates with staggered breaks. Armour and kilt are split-normal shaded
  ("sharp by angle" 24°) so ledges and pleats stay crisp.
- **Props:** sling = one colourable band (two cords, §11.8) from inside the right fist to the leather pouch, stone in the
  pouch; shepherd's bag with strap over the right shoulder, flap and toggle; red sash with knot and two hanging ends;
  sandals = sole + ankle strap + instep strap. Goliath: laced-boot cuff and welt; bronze greaves with knee flare and shin
  ridge; leather bracers; wide belt with bronze plate; helmet = dome with raised rim band and front ridge, flared neck
  guard (open at the face), transverse horsehair crest on a holder; leaf-bladed spear with socket collar and butt spike;
  dished round shield with rim, embossed ring and boss.
- Regions (face attribute → sheet colours) follow `design.json palette`: David `skin hair tunic belt bag sandals sling
  stone`; Goliath `skin beard helmet crest armour belt bracers kilt greaves feet spearShaft spearHead shield shieldRim
  shieldBoss` (the leg below y 0.0625 is `feet` = boots).

## 3. Bone table (§3 + §11.6)

Heads/tails are exactly `design.json characters.<id>.bonesLocal`. Blender roll is set so every bone's local Z points
toward the viewer (+Z glTF) where the bone is not itself along Z; for limbs flexion is a rotation about local X.

| Bone | Parent | Notes |
|---|---|---|
| `root` | — | at the origin |
| `hips` `spine` `chest` `neck` `head` | chain | |
| `jaw` | `head` | opens the mouth; chin, lower lip and Goliath's beard follow |
| `shoulderL/R` `upperArmL/R` `forearmL/R` `handL/R` | `chest` → chain | L = character's left = +X; `hand` ends at the knuckles |
| `fingersL/R` → `fingerTipsL/R` | `hand` | all four fingers share them (§11.6); fist hands are curled at rest |
| `thumbL/R` | `hand` | thumb incl. its palm root |
| `thighL/R` `shinL/R` `footL/R` `toeL/R` | `hips` → chain | |
| David `slingCord1` `slingCord2` `slingPouch` | `handR` → chain | sling band and pouch are skinned to it |
| David `stone` | `root` | free; rest = in the pouch at (−0.107, 0.078, 0.004) local |
| Goliath `spear` `shield` `helmet` | `handR` / `handL` / `head` | rigid props are child nodes |

Verified by `verify`: bone sets equal §3 + §11.6 + extras (David 33, Goliath 32), nothing missing or extra.

## 4. Weights

Deterministic, painted on the cage per part (`weigh()`): a vertex scores each candidate bone by how far it lies outside
that bone's span along the bone axis, Gaussian falloff 0.006 × (height / 0.30) (fingers and thumb 0.10 × hand length),
optional radial reach; then Subdivision interpolates, then the joined body is limited to 4 influences and normalised.

| Part | Bones |
|---|---|
| head + neck | `head` above a seam under the jaw that rises toward the nape; below it `neck`/`chest`; then `jaw` override below the mouth line on the front |
| arm | shoulder (reach), upperArm, forearm, hand; the forearm twists smoothly into the hand frame (fists: 90° pronation) |
| palm / fingers / thumb | forearm + hand / hand → fingers → fingerTips / hand → thumb |
| leg + foot | thigh, shin, foot, toe |
| tunic, armour | hips, spine, chest (+ neck, shoulders by reach); skirt below the hips blends up to 65 % into the thigh on its side; sleeves: chest → shoulder → upperArm |
| kilt / sash, belt, bag / strap | hips, spine (+ skirt rule) / hips, spine / chest → spine → hips |
| hair, ears, moustache / beard | head / head + jaw override |
| sandals / boot trims / greaves / bracers | foot, toe, shin (reach) / shin, foot / thigh, shin / forearm, hand |
| sling band / pouch | handR, slingCord1, slingCord2 / slingCord2, slingPouch |

**Pose test** (`model/pose_test.png`): forearms 60° forward, shins 60° back, spine 30° + chest 30° forward, fingers
50° + 50° (open hand curls, fists open), thumbs 25°. Elbows, knees, the open hand's curl and the bent torso deform without
tearing or candy-wrapper collapse. Edge stretch: worst ratio 9.0 (David) / 6.3 (Goliath); 127 of 19,839 and 384 of
16,458 edges change by more than 1.6×, nearly all in the knuckle/palm crease when fingers bend 100° (David hand/finger
bones 119 of 127) and on the inside of Goliath's folded armour (spine/chest/hips 199). Weak spots: opening a fist
from rest stretches the palm into a crumpled glove shape (fists are modelled closed; §11.11 keeps grips closed in most
clips), and greaves and kilt pass slightly into the thigh at a 60° knee bend.

## 5. UV contract (proof)

- **UV0** = front orthographic projection of the rest pose at the sheet position: `u = x + sheetX + 0.5`,
  `v = (y + sheetY) / 1.227`, computed per vertex before any posing (LESSONS L7), with a 4 px (0.004) inward inset at
  silhouettes (`INSET`) so the model samples the colour just inside an outline, not the erased line.
- The Sheet role's line art is the outline render of these meshes (ID render `$DG_WORK/id_2x.png` + `id_2x.json`, one
  colour per mesh piece × region; this build has 55 pieces), so every printed outline is a mesh edge.
- **Proof** (`model/uv_check.png`, `model/uv_check.json`, texture = `uvproof.png`, the ID render in palette colours):
  rendered front-ortho with that texture, the models reproduce it. Away from region borders (131,969 px) the mean
  absolute difference is **0.028 / 255**; 0.031 % of pixels differ by more than 24. Re-run `uvcheck` + `compose` with the
  real `sheet/demo-colored.png` once the Sheet role has rebuilt the sheet.
- **UV1 "decal"** = `faceDecals.<id>.rectLocal` (§11.7) on face, beard and moustache vertices that face the viewer;
  everything else is pushed outside 0..1. Sample with clamp-to-transparent. Shown in `uv_check.png`.

## 6. Open issues / requests

1. **Sheet role:** `tools/make_dg_sheet.py` stops on `design.json sheet.decorSuggestion = null` (sun/clouds removed in
   §11.9). Until it is updated, `sheet/`, `print/` and the reference image still show the **old** balloon models, and
   `pipeline/dg_make_all.sh` fails at step 2. The new ID render it needs is produced by `build`.
2. **Animation:** every clip must be re-authored on the new rest pose (45°, new bone positions, six finger bones); the old
   `anim/*.glb` no longer match. Fist fingers are curled at rest; open them only where §11.11 says.
3. **Integration:** take `sheetX` from design.json (−0.350 / +0.130); rebuild the AR reference library from the Sheet
   role's new reference image; Goliath now has four helmet nodes (dome, guard, crest, crest holder) under `helmet`.
4. Not tested: the GLBs inside Unity / on a phone, glTFast's handling of the split normals on armour and kilt, and how
   the faces look with the real decals in the app's lighting.
