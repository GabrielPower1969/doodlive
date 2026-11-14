# Daniel — character models, rigs, weights, UVs, faces (Characters role)

Owner: Characters (Blender). Binding brief: [CONTRACT.md](CONTRACT.md) §2–§3, look: [DESIGN.md](DESIGN.md). Built by
`pipeline/da_characters.py`, a copy of `pipeline/ru_characters.py` (Ruth) for the three humans plus a new quadruped
builder for the two lions. `pipeline/story_mesh.py` is unchanged (every new helper lives in da_characters.py), so
Esther's and Ruth's outputs cannot change.

## Rebuild

`python3 pipeline/da_characters.py all` runs every step (≈ 8 min) and prints the verify summary. One by one:

```
python3 pipeline/da_characters.py faces                                         # 30 face decal PNGs + overview (Pillow)
blender -b --factory-startup --python pipeline/da_characters.py -- build        # meshes, rigs, UVs, ID renders, lion2 paint,
                                                                                 #   GLBs, characters.blend (~2 min)
python3 pipeline/da_characters.py proof                                         # $DA_WORK/uvproof.png
blender -b --factory-startup --python pipeline/da_characters.py -- preview      # EEVEE demo-palette renders
blender -b --factory-startup --python pipeline/da_characters.py -- uvcheck      # models wearing uvproof.png via UV0
blender -b --factory-startup --python pipeline/da_characters.py -- posetest     # bends, blink, jaw, cloth, lion roar + sit
blender -b --factory-startup --python pipeline/da_characters.py -- verify       # re-import GLBs: bones, skins, tris, sizes
python3 pipeline/da_characters.py compose                                       # model/preview_*.png contact sheets
```

Blender: `$BLENDER`, else `blender` on PATH, else `/Applications/Blender.app`. `DA_WORK` (default
`/tmp/daniel_chars/work`) holds intermediate renders; delete it afterwards. `DA_ONLY=lion,lion2` builds a subset (debug
only; always finish with a full build, the ID render and regions JSON are only copied/complete from a full build).
Checked 2026-11-14 with Blender 5.2.3. The build reads `assets/daniel/design.json` (`characters.<id>.sheetX/sheetY`,
`artHeightUnits`, `characters.<id>.propUV`) and the Set role's `model/set_id_2x.png/.json` when they exist; rebuild
after either changes. Without design.json it uses the CONTRACT §2 slots.

## 1. What is in the GLBs (`assets/daniel/model/`)

| | daniel | king | officer | lion | lion2 |
|---|---|---|---|---|---|
| Triangles | **24,096** | **24,860** | **21,054** | **25,500** | **20,236** |
| Skinned body (≤ 4 influences) | `daniel_body` | `king_body` | `officer_body` | `lion_body` | `lion2_body` |
| Rigid props (child of one bone) | `daniel_eyelids` | `king_ring` → `ring` (shown), `king_eyelids` | `officer_scroll` → `scroll` (**hidden by default**, exported visible), `officer_eyelids` | `lion_eyelids` | `lion2_eyelids` |
| Size (verify, re-imported GLB) | top 0.333 (height 0.34) | top 0.441 with the crown-hat (0.40 without) | top 0.338 (height 0.35) | nose→rump 0.220, withers 0.126, top of mane 0.194, tail tip 0.039 behind the rump (tail path 0.10) | nose→rump 0.210, withers 0.116, top 0.169 |
| Bones | 29 | 30 | 28 | 27 | 27 |

- One material per GLB (`da_page`; lion2: `da_lion2_paint` with `lion2_paint.png` embedded). Attributes POSITION NORMAL
  TEXCOORD_0 (page / paint) TEXCOORD_1 (face decal) JOINTS_0 WEIGHTS_0; verify checks the UV order after re-import.
  No animations.
- Character-local: root at the origin, feet / paws on y = 0, facing +Z, 1 unit = art width.
- Prop nodes as Esther / Ruth: joint node = bone (`ring`, `scroll`), mesh under it = `<char>_<bone>`, so
  `prop("king/ring")` and `prop("officer/scroll")` find them. The timeline's t = 0 prop events hide the scroll.
- `characters.blend` holds the five rigs at their sheet slots (lion2 on her virtual page at x = 3.0); region ids in the
  scene property `da_regions`.

## 2. Rest pose (for Animation)

- Humans: A-pose, arms 55° below horizontal, open relaxed hands (as Ruth). No baked poses.
- Lions: standing on all fours, paws flat on the page, facing +Z, tail in an S-curve up behind the rump, head level.
  `root` on the ground under the belly centre. Leg bones point down (forelegs: shoulder → elbow → wrist → paw tip;
  hind legs: hip → knee → hock → toe), local Z toward the nose, so flexion is a rotation about local X.
- Knees: Daniel 0.093, king 0.100, officer 0.099 (`kneeY`); robes below are skinned to thigh / shin as Ruth.

## 3. Bones (CONTRACT §3)

Humans: `root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R
toeL/R fingersL fingersR eyelids` + extras. Lions: `root hips spine chest neck head jaw eyelids tail1..4 earL earR
upperArmL/R forearmL/R pawL/R thighL/R shinL/R footL/R mane`.

| Bone | Parent | What follows it |
|---|---|---|
| `hair1` (daniel) | `head` | the ponytail below the tie at the nape (rotate about X to swing it) |
| `sash1` → `sash2` (daniel) | `hips` → chain | the two hanging sash ends on his left front |
| `cape1` → `cape2` (king) | `chest` → chain | the cape's back drape below the shoulder line; shoulders stay on chest / shoulders |
| `belly` (king) | `spine` | front of the robe + belt round the belly (Gaussian, 80 % at the centre); scale it (1.1) or nudge it for laughs |
| `ring` (king) | `handR` | rigid signet ring on the ring finger, visible all play |
| `robe1` (officer) | `hips` | robe front below the knee (up to 85 % at the hem), for the hem swing |
| `scroll` (officer) | `handR` | rigid scroll across the open right palm (+ red seal); curl `fingersR` 60–75° to close the hand on it |
| `jaw` (all) | `head` | humans: chin, lower lip, lower mouth decal, beard below the mouth. Lions: chin + lower half of the cheek puffs; 25–30° = a full roar |
| `eyelids` (all) | `head` | blink: scale local **Y**: 1 = open, **12.78 = closed**, ~6 = half. Lions: each lid row sits on the most forward head point over its whole travel, so a closed lid lies on the eye, not inside the round head (checked: `preview_pose.png`, lion b, eyelids closed) |
| `earL/R` (lions) | `head` | the ear (incl. inner ear), fully rigid-weighted |
| `mane` (lion) | `neck` | the back and outer tufts of the mane (≈ 30–60 %); the front ring round the face stays on `head`. lion2 keeps the bone with no weights |
| `tail1..4` | `hips` → chain | the tail in four equal lengths; the tuft is all `tail4` |

## 4. How the meshes are made

- Humans as Ruth (heads mapped from the D&G base head; box-modelled hands; robe shells with folds). Daniel = Esther's
  king build ×0.93 (widths ×0.90): hair combed back to the nape + ponytail with a tie, trimmed beard + moustache, cream
  robe whose sleeve profile steps at the elbow (short over-sleeve on a long under-sleeve), gold yoke in three bands,
  teal sash with two hanging ends, sandals. King = Esther's king proportions: curly hair + big curl-row beard + curly
  moustache, lavender robe with a round belly, gold belt on it, gold medallion with a raised star, deep-blue cape open
  at the front with two gold clasps, tall purple crown-hat (top 0.44) with a raised gold band and 16 gold studs (skinned
  to `head`, region crown / crownBand), signet ring. Official = Haman's long face ×0.946 (widths ×0.88): black hair,
  gold headband with a boss, pointy nose, thin pointed goatee, moustache rolled into curls, thin burnt-orange robe with
  two red hem stripes and red cuffs, green sash, curly-toed slippers.
- Lions (`build_lion`): one bean-shaped torso tube (cream belly / chest underneath), soft haunch and shoulder masses,
  plump legs with round paws and three toe bumps (paws flattened on the page), a round head, a nose bridge, two cream
  cheek puffs and a chin (on `jaw`), a rounded triangular nose, round ears with a cream inner ear, an S-tail with a
  dark flame-tipped tuft. The lion's mane is a ruff of 11 scalloped tufts per ring (alternate rings offset, slight
  swirl), wrapped round the face, swelling back over the neck and shoulders and lower on the chest, plus three round
  forehead curls. lion2 = the same layout ×(0.90, 0.923, 0.905), slimmer neck, no mane.

## 5. Regions (`model/regions_characters.json`)

| daniel | king | officer | lion | lion2 (not printed) |
|---|---|---|---|---|
| skin, hair (hair + beard), robe, collar, sash, sandals | skin, beard (hair + beard), crown, crownBand (band + studs), robe, cape, medallion (+ clasps), belt, shoes; ring → anchored to medallion | skin, beard (hair + beard), headband, robe, stripes (hem + cuffs), sash, slippers; scroll → daniel.robe, seal → officer.stripes (hidden prop, not printed; `set.scroll` / `set.seal` win if the Set role prints them) | body, mane (+ forehead curls), muzzle (cheeks, chin, belly, chest, inner ears), tuft, nose (anchored to its own widest printed spot) | body, muzzle, tuft, nose |

Part anchors: hand and foot skin of the humans take one texel of their own face skin (Ruth's method).

## 6. UVs

- Humans: UV0 = front page projection at the slot + occlusion pass + ID-render check (Ruth). UV1 = face decal rect.
- **lion (side view, CONTRACT §2)**: UV0 = `u = -z + sheetX + 0.5, v = (y + sheetY) / artH` of the vertex mirrored to
  the lion's left side (|x|), so his right side wears the drawing of his left side. A face keeps that projection when
  all its (mirrored) corners face +X and nothing of another region lies between them and a camera at +X; every other
  face (front of the face, top of the back, under the belly, inner legs, eyelids) takes one clean texel of its own
  region (the deepest pixel of that region in the printed drawing). Then Ruth's ID-render check runs. The sheet's ID
  render (`id_characters_2x.png/.json`) shows the lion in that side view at his slot (side bbox x 0.203–0.462,
  y 0.016–0.209).
- **lion2**: built on a virtual page; her side ID render becomes `lion2_paint.png` (1024², flat demo colours, soft
  grain, slightly darker back / lighter belly, colours grown 14 px into the paper); UV0 = the same mirrored side
  projection into that image (`u = (-z - 0.02) / 0.34 + 0.5, v = (y - 0.105) / 0.34 + 0.5`), hidden faces take a texel.
  Integration: `assets/stories.json` `"paint": {"lion2": "lion2_paint.png"}` (Esther guard precedent).
- UV1 of the lions = the decal rect projected from the front onto the head, bridge and muzzle (faces with n.z ≥ 0.3);
  the nose is geometry and takes no decal.

## 7. Faces (`docs/daniel/design/faces/`, `overview.png` with a 64 px "phone distance" row)

| daniel | king | officer | lion / lion2 |
|---|---|---|---|
| calm (default), talk, smile, pray (closed), sure, joy | smile (default), talk, proud (half-closed, chin-up brows), worried, sorry (wet eyes), tired (heavy lids, bags), joy | sulky (default), talk, sly (one eye half shut, one brow up, smirk), flatter (big fake grin), gleeful, scared (huge eyes, shout, sweat drop), nervous (side look, wobbly mouth, sweat drop) | curious (default; big eyes, one brow up, little "o"), sleepy (heavy lids), fierce (V brows, big round open mouth with soft white bumps, pink tongue, no fangs), blissful (^ ^ eyes, wide "w" smile, blush), yawn (eyes squeezed shut, big round open mouth, a little tongue; pair with `jaw` open) |

Humans use Ruth's drawing kit (light lip rim on beards, LESSONS L42). Lions: big amber eyes with clear pupils and
highlights, thick soft brows, a philtrum + "w" mouth, whisker dots; lion2 has lashes and lighter brows. The roar
decal was checked on the model with the jaw at 30° (`preview_pose.png`): the stretch keeps the teeth round.
`regions_characters.json clipExpression` maps every CONTRACT §4 clip to a suggested decal.

## 8. Checks done (2026-11-14)

- `verify`: bone sets equal CONTRACT §3 for all five, 0 actions, ≤ 4 influences, UV order OK (sizes in §1).
- `preview_<char>.png`: front, 3/4, side, back, face close-ups, hands / paws, every expression on the model; lions
  also from a phone-like high angle. `preview_all.png`: the cast together, incl. a high angle.
- `preview_uvcheck.png`: the front ortho of the models (lion turned to its side) equals the perfectly coloured sheet;
  3/4, back and the lion's right side / top / front keep each region's colour.
- `preview_pose.png`: humans (elbows, fingers, thigh + knee, spine, head turn, jaw, half blink, hair1, sash1/2,
  cape1/2, belly, robe1); lions a (neck + head up, jaw 30°, mane, ears, tail, a front paw lifted, hind knee, half
  blink, roar close-up with the fierce decal) and b (sitting: hips −38°, hind legs folded, root not lowered so it
  floats). No tearing seen at preview size.

## 9. Not done / rough edges

1. Not tested in Unity or on a phone.
2. **Sheet slots (CONTRACT §2) are tight for A-pose humans**: Daniel's right hand reaches x = −0.503 (just outside the
   art rect, L40), Daniel's and the king's hands overlap (−0.284 … −0.257) and so do the king's and the official's
   (−0.045 … −0.016). The Set + sheet role should move the slots in `design.json` (e.g. spread them, or let the lion
   take less width) and both roles re-run; `da_characters.py` follows design.json automatically.
3. Weights are procedural. Lions: deep folds (sleep curled, roll_over on the back) and the sit were only checked at
   preview size; the mane is ~50 % head at the face ring, so a big head turn bends the mane's back half.
4. The lion's tail tuft and nose are small on the print (nose anchored to its own widest spot).
5. Hidden prop colours depend on the Set role's printed drawings (`set.scroll`, `set.seal`); rebuild if they appear.
