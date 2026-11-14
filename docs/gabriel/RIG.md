# Gabriel — character model, rig, weights, UVs, faces (Character role)

Owner: Character (Blender). Binding brief: [CONTRACT.md](CONTRACT.md) §2–§3, look: [DESIGN.md](DESIGN.md). Built by
`pipeline/ga_character.py`: the Daniel pack's method (`pipeline/da_characters.py`; the helpers it needs are copied into
the script, `pipeline/story_mesh.py` is unchanged) with a new full-body builder, plate armour, sculpted hair locks and
feather-by-feather wings. Nothing of Esther / Ruth / Daniel is read or written.

## Rebuild

`python3 pipeline/ga_character.py all` runs every step (≈ 2.5 min) and prints the verify summary. One by one:

```
python3 pipeline/ga_character.py faces                                         # 8 face decal PNGs + overview (Pillow)
blender -b --factory-startup --python pipeline/ga_character.py -- build        # mesh, rig, UVs, ID render, GLB, blend (~10 s)
python3 pipeline/ga_character.py proof                                         # $GA_WORK/uvproof.png
blender -b --factory-startup --python pipeline/ga_character.py -- preview      # EEVEE demo-palette renders (GA_VIEWS=front,head,… for a subset)
blender -b --factory-startup --python pipeline/ga_character.py -- uvcheck      # the model wearing uvproof.png via UV0
blender -b --factory-startup --python pipeline/ga_character.py -- posetest     # wings folded / half / flapping, kneel, trumpet, bends, blink
blender -b --factory-startup --python pipeline/ga_character.py -- verify       # re-import the GLB: bones, skin, tris, size
python3 pipeline/ga_character.py compose                                       # model/preview_*.png contact sheets
```

Blender: `$BLENDER`, else `blender` on PATH, else `/Applications/Blender.app`. `GA_WORK` (default
`/tmp/gabriel_char/work`) holds intermediate renders; delete it afterwards. Checked 2026-11-14 with Blender 5.2.3.
The build reads `assets/gabriel/design.json` (`characters.gabriel.sheetX/sheetY`, `artHeightUnits`,
`characters.gabriel.propUV`) when it exists; without it the CONTRACT §2 slot (0.0, 0.015) is used. Rebuild after it
changes.

## 1. What is in the GLB (`assets/gabriel/model/gabriel.glb`)

| | gabriel |
|---|---|
| Triangles | **89,992** (budget 90,000): body 87,692 + sword 1,316 + trumpet 864 + eyelids 120 |
| Skinned body (≤ 4 influences) | `gabriel_body` |
| Rigid props (child of one bone) | `gabriel_sword` → `sword` (shown), `gabriel_trumpet` → `trumpet` (**hidden by default**, exported visible), `gabriel_eyelids` → `eyelids` |
| Size (verify, re-imported GLB) | crown 0.626 (hair), wing tips 0.796, wingspan 0.973, feet 0.000, depth −0.133 … +0.061 |
| Bones | 40 |

- One material (`ga_page`). Attributes POSITION NORMAL TEXCOORD_0 (page) TEXCOORD_1 (face decal) JOINTS_0 WEIGHTS_0.
  No animations.
- Character-local: root at the origin, feet on y = 0, facing +Z, 1 unit = art width.
- Prop nodes as the other packs: joint node = bone (`sword`, `trumpet`), mesh under it = `gabriel_<bone>`.
- `characters.blend` holds the rig at the sheet slot; region ids in the scene property `ga_regions`.
- Largest parts (triangles): wings 2 × 13,290, torso 7,344, face 6,076, hair locks 5,840 + cap 2,184, pauldrons
  2 × 3,844, skirt 3,248, legs 2 × 3,204, gorget 2,304, hands 2 × 2,144, greaves 2 × 2,016, vambraces 2 × 1,728.

## 2. Rest pose (for Animation) = the sheet pose

A-pose, arms 55° below horizontal, open relaxed hands, **wings spread** in the frontal plane behind the back (swept
back about 0.06 toward the tips), sword sheathed. Proportions: about 7 heads; head 0.518–0.6045 (hair to 0.620),
shoulders 0.478 (joints at x ±0.086), waist 0.385, hips 0.335, knees 0.170, ankles 0.035.

## 3. Bones (CONTRACT §3)

`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids` as Daniel, plus:

| Bone | Parent | Head → tail (character-local x, y, z) | What follows it |
|---|---|---|---|
| `wingL1` | `chest` | (0.040, 0.455, −0.066) → (0.135, 0.515, −0.070) | wing upper arm: the six tertials, the coverts over them, the root of the leading edge. Feathers next to the body are up to 55 % `chest` so they do not swing through the spine |
| `wingL2` | `wingL1` | → (0.250, 0.562, −0.089) | wing forearm: the twelve secondaries and their coverts |
| `wingL3` | `wingL2` | → (0.322, 0.603, −0.104) | wing hand: the innermost primaries; parent of `wingL_prim` |
| `wingL_prim` | `wingL3` | (0.250, 0.562, −0.089) → (0.360, 0.562, −0.112) | fans the twelve primaries: primary *i* of 12 has weight *i*/11 (innermost 0, outermost 1), the hand coverts and the tip of the leading edge the same by their place. **Rotate it about the wing's normal (its local Z): −96° (L) / +96° (R) closes the fan** onto the innermost primary; rest = fully open (fan 96°) |
| `wingR*` | | mirror | |
| `hair1` → `hair2` | `head` | (0, 0.536, −0.013) → (0, 0.520, −0.043) → (0, 0.505, −0.051) | the hanging ends of the back and side locks (below the nape); rotate about X to swing |
| `sash1` → `sash2` | `hips` | (0, 0.362, 0.049) → (0, 0.272, 0.058) → (0, 0.184, 0.059) | the hanging front panel of the sash (upper / lower half) |
| `sword` | `hips` | (0.080, 0.370, 0.024) → (0.101, 0.120, −0.051) | rigid sheathed sword at the left hip (head = scabbard mouth, tail = tip) |
| `trumpet` | `handR` | (−0.217, 0.274, −0.005) → 0.10 toward the bell | rigid trumpet across the right palm: mouthpiece 0.112 from the grip on the thumb side, bell 0.192 beyond the little finger. Rest ends: `regions_characters.json` `trumpet.mouthpieceLocal / bellLocal` |
| `jaw` | `head` | | chin and lower lip (as Daniel) |
| `eyelids` | `head` | | blink: scale local **Y**: 1 = open, **20 = closed**, 10 = half. Each lid is a 1/20 miniature of the closed almond lid tucked under the brow, placed on the most forward face point over its travel |

Local axes as the other packs (`story_mesh.make_armature`): Y along the bone, Z toward the viewer where the bone is
not along Z, so limb flexion is a rotation about local X and a wing bone's local Z is the wing's normal.

Every feather has **one weight set for all its vertices**, so feathers stay stiff; a feather between two bones is a
blend of two rigid motions (it shrinks a little in between: up to 33 % for the middle primaries when the fan is fully
closed, hidden in the closed bundle).

## 4. Wing recipes (checked in `preview_pose.png`)

Rotations per wing bone as (axis, degrees) about **character axes carried along by the parent's pose** (X right, Y up,
Z toward the viewer), applied in the listed order, for the LEFT wing; the right wing uses the opposite sign for Y and
Z. `ga_character.rot()` is this recipe as code. Blender pose quaternions (w, x, y, z) for the left wing in brackets
(right wing: negate y and z).

| Pose | `wingL1` | `wingL2` | `wingL3` | `wingL_prim` |
|---|---|---|---|---|
| **folded** behind the back (bottom edge at mid-calf, y 0.092; a feather cloak; nothing crosses the body) | Y +35 [0.9537, −0.2542, 0.1605, 0.0063] | Y +115 [0.5373, −0.7807, 0.3156, 0.0468] | Z −40 then Y −130 [0.3971, 0.8935, −0.1233, −0.1697] | Z −96 [0.6691, 0, 0.1526, −0.7273] |
| **half open** (idle, wave) | Y +16, Z −6 | Y +38 | Z −30 then Y −42 | Z −60 |
| flap, **down-stroke** | Z −34, Y −10 | Z −14, Y −8 | Z −10 | Z −8 |
| flap, **up-stroke** | Z +24, Y +8 | Z +12 | Z +10 | Z +6 |

How the fold works: the feathers hang down from the wing arm, so only rotations about the vertical (Y) keep them
hanging. The arm folds like a Z seen from above (upper arm out and back, forearm back in behind it, hand out again);
the hand first turns down in the wing plane (Z −40) and `prim` closes the fan. **Order matters on `wing?3`**: Z before
Y; the other way round the primaries stick out sideways. Flapping is a rotation about Z at `wing?1` with `wing?2`,
`wing?3` following a little later; a touch of Y brings the tips forward on the down-stroke. Keep `wing?1` Z above
about −40°: further down the two wings meet behind the legs.

**Kneeling** (on the right knee): the folded wings would reach the floor, so the kneel uses the fold with `wing?1`
tilted back: `wingL1` Y +35 then X +50 [0.8644, −0.0152, 0.4810, 0.1460] (X keeps its sign on the right wing; the
other three bones as folded). The bundle then sweeps back and clears the floor (lowest feather 0.079) and the back
foot. Legs: thighL X −86, shinL X +88, thighR X +6, shinR X +98, footR X +42, toeR X −58; `root` lowered by 0.119
puts the knee and toes on y = 0; `sash1` X −62, `sash2` X +58 lay the panel over the thigh. Blend into / out of it
from `fold` by animating only that X tilt.

**Trumpet at the lips** (solved in posetest): quaternions upperArmR [0.0950, −0.3096, −0.7460, −0.5819], forearmR
[0.0929, 0.0929, 0.7010, −0.7010], handR [0.9447, 0.0715, 0.3150, −0.0558], fingersR curled 72°; the mouthpiece then
sits on the lips within 0.0002, the bell points forward and slightly up and to his right. Show the `blow` decal.

Numeric check in `posetest` (`pose_info.json`): `wingMinY` = lowest feather point, `wingInside` = feather vertices
inside the rest of the body (about 90–125 in every pose and at rest: the roots of the feathered wing arm sit in the
back by design; a pose that crosses the body jumps well above that). `wingtry` mode (`GA_TRIES`) measures recipes
without rendering.

## 5. How the mesh is made

- **Head**: the D&G base head mapped to Gabriel's landmarks (eyes at 0.495 of the head height, strong jaw 0.15, chin
  forward, straight nose 0.0096 high), a denser cage than the other packs (32 points round × 32 rings, one subdivision,
  one smoothing pass), ears. Neck 0.019 wide. Face = decals (UV1).
- **Hair**: thick, wavy, swept back to the shoulders: a cap over the skull + 16 big sculpted locks (flattened tubes
  with a flat underside, full rounded ends) that keep one height over the skull, so the silhouette is clean from
  every side: seven top locks combed straight back from the hairline with a soft lift at the front, fanning out over
  the crown and down onto the upper back (ends at y 0.484–0.496, alternating waves); three side locks per side from
  the temple back over the top of the ear and down behind it onto the collar, ends flicking out; three back locks
  under them to the nape.
- **Build**: broad chest (half width 0.090 at the pectorals), narrow waist (0.051), strong deltoids and upper arms,
  thighs with quadriceps and a vastus-medialis bulge above the knee, full calves (the greaves follow them), hands
  12 % larger than first built (fingers 7 % longer).
- **Torso**: a 36-sided shell with the cuirass relief displaced on the subdivided surface (`cuirass_h`): pectorals with
  a clear lower edge, sternum, centre seam, rib arch, three pairs of abdominals, flank line; spine channel and
  shoulder blades on the back.
- **Armour** (all with real thickness, 0.0036–0.0044, and soft bevels from one subdivision): V gorget following the
  chest relief with a standing collar, a centre ridge and a beaded rim; per shoulder four plates: the big top plate
  with a round boss lying on a second, 7.5 % larger plate whose rim shows all round it (a stepped double edge; both
  62 % `shoulder`, 38 % `upperArm`), then two lames stepping down the arm (78 % and 100 % `upperArm`); every plate has
  a rolled bead along its rim and a bevelled edge. Vambraces pointed toward the elbow with a point over the back of
  the hand and a keel (`forearm`); greaves with a pointed knee cop, a keel (`shin`); both have rolled rims and an
  embossed line (a raised line with a groove either side) running round inside each rim. Boots with a sole welt.
- **Sash, belt, skirt**: a wound sash with soft diagonal folds, a belt with a round stepped buckle, the hanging front
  panel (a plate with thickness, pointed end), seven tongue-shaped skirt panels round the hips (they follow the
  thighs up to 62 %).
- **Hands**: Daniel's box-modelled hand scaled up: palm, four separate three-joint fingers (`fingers?`), thumb.
- **Wings**: per wing 195 separate closed feather meshes (390 in all) + the feathered arm (leading edge):
  6 tertials, 12 secondaries, 12 primaries (10 stations, a raised shaft ridge, soft round tip, each rolled 11° so
  they overlap like louvres; the tertials and inner secondaries are long enough that the folded wing reaches the
  calves), then on the front a row of 22 greater coverts (with shaft), 22 median and 68 lesser coverts in three
  staggered lines, and on the back three coarser rows (53 feathers). Median, lesser and back coverts are lancet
  shaped: widest at 40 %, a low centre ridge, a soft point that tucks under the row in front.
- **Props**: sword (ivory scabbard with gold locket and chape, curved cross-guard with a round boss and a blue gem
  on both faces, ribbed grip, pommel); herald trumpet 0.304 long (cup mouthpiece, two bosses, flared bell).

## 6. Regions (`model/regions_characters.json`) and UVs

skin (face, ears, hands), hair, cuirass, sleeves, vambraces, pauldrons, collar (gorget), sash (band + front panel),
belt (+ buckle), skirt, leggings (hips, thighs, shins under the greaves), greaves (+ boots), hilt (+ locket, chape),
gem → its own widest printed spot, scabbard, **wingCoverts** (coverts + the wing arm), **wingFeathers** (tertials,
secondaries, primaries), trumpet → a clean texel of `pauldrons` (hidden prop, not printed; override
`design.json characters.gabriel.propUV.trumpet`).

- UV0 = front page projection at the slot (`u = x + sheetX + 0.5`, `v = (y + sheetY) / artH`). A corner hidden in the
  front view behind **another region** takes the nearest visible point of its own region; then every face is checked
  against the ID render and any face that would sample another region (back of the head, back coverts, hidden thigh)
  moves to one texel of its own region at least 4 px (2000 px render) away from every outline. Faces hidden behind
  their own region keep the projection (the back of the cuirass, the back of a long feather).
- UV1 = the face decal rect (character-local x −0.0311 … 0.0311, y 0.5220 … 0.5843). The eyelids take one clean
  texel of the face skin.
- `id_characters_2x.png/.json` (85 ids): feathers cycle through four piece ids per row, so neighbours always differ
  and the sheet gets an outline round every feather; the shaft of every flight feather and greater covert is its own
  thin piece (a quill line on the sheet). Sheet bbox: x ±0.487, y 0.015 … 0.811.

## 7. Faces (`docs/gabriel/design/faces/`, `overview.png` with a 64 px "phone distance" row)

`calm`, `smile` (default), `talk`, `kind` (inner brows up, soft smile), `joy` (open grin), `announce` (mouth wide
open, eyes bright), `blow` (eyes closed, cheeks puffed with two arcs, small round mouth), `wink` (his right eye).
Warm hazel eyes, chestnut brows, no fold lines (a young face). `regions_characters.json clipExpression` maps every
CONTRACT §4 clip to a suggested decal.

## 8. Checks done (2026-11-14, polish round after the lead's review)

- `verify`: bone set equals CONTRACT §3 (40, unchanged by the polish round, same rest pose), 0 actions,
  ≤ 4 influences, UV order OK, 89,992 triangles. Region names unchanged.
- `preview_gabriel.png`: front, 3/4, side, back, 3/4 back, phone-like high angle; all eight expressions on the model.
- `preview_details.png`: face 3/4 / front / side, hair back and from above, cuirass + gorget, pauldron, both hands,
  belt + sash + sword, greaves + boots, wing front / close / back, trumpet shown.
- `preview_pose.png`: wings folded, half open, down-stroke, up-stroke, kneeling with folded wings, trumpet at the
  lips (+ close-up), limb bends with jaw / half blink / hair / sash, eyelids fully closed.
- `preview_uvcheck.png`: front ortho of the model equals the perfectly coloured sheet; 3/4 and back keep each
  region's colour.

## 9. Not done / rough edges

1. Not tested in Unity or on a phone.
2. **Wingspan is 0.973, not 1.0**: the tips stop 0.013 inside the art rectangle so their outline is not cut
   (LESSONS L40). Wing tips reach 0.796; the inner flight feathers now hang to y 0.092 behind the calves at rest.
3. The long hair is skinned to `head` above the nape and `hair1` / `hair2` below; a big head turn bends the hair
   that lies on the collar. From the front the hair frames the face down to the collar.
4. Weights are procedural. Shoulder: the pauldron plates are stiff and ride on `shoulder` + `upperArm`; with the arm
   straight up the top plate comes close to the hair. The knee cop is rigid on `shin` and swings forward off the
   thigh in a deep bend (as a real one).
5. The closed eyelids show their rim as a faint outline at close range (thin shells on the face).
6. At rest the two wings touch behind the spine; a down-stroke beyond `wing?1` Z −40 lets the inner feathers cross.
7. `skirt` and `leggings` are two regions (DESIGN lists them together); the sword gem is too small to colour and
   keeps its own printed spot. The Set + sheet role can anchor small regions via `ANCHORS` in the script.
