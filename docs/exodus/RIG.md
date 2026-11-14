# Exodus — character models, rig, weights, UVs, faces (Characters role)

Owner: Characters (Blender). Binding brief: [CONTRACT.md](CONTRACT.md) §2–§3, look: [DESIGN.md](DESIGN.md). Built by
`pipeline/ex_characters.py`, a copy of `pipeline/ru_characters.py` (Ruth) that keeps its method (procedural quad cages,
heads mapped from the D&G base head, box-modelled hands, face decals on UV1 + `eyelids` blink, UV0 = front page
projection + occlusion pass + ID-render fix, `hood()` drapes). `pipeline/story_mesh.py` is unchanged.

## Rebuild

`python3 pipeline/ex_characters.py all` runs every step (faces ~5 min, the Blender steps ~2 min) and prints the verify
summary. One by one:

```
python3 pipeline/ex_characters.py faces                                          # 27 face decal PNGs + overview (Pillow)
blender -b --factory-startup --python pipeline/ex_characters.py -- build         # meshes, rig, stoop bake, UVs, ID render,
                                                                                  #   GLBs, characters.blend
python3 pipeline/ex_characters.py proof                                          # $EX_WORK/uvproof.png
blender -b --factory-startup --python pipeline/ex_characters.py -- preview       # EEVEE demo-palette renders
blender -b --factory-startup --python pipeline/ex_characters.py -- uvcheck       # models wearing uvproof.png via UV0
blender -b --factory-startup --python pipeline/ex_characters.py -- posetest      # bend / blink / jaw / cloth bones
blender -b --factory-startup --python pipeline/ex_characters.py -- verify        # re-import GLBs: bones, skins, tris
python3 pipeline/ex_characters.py compose                                        # model/preview_*.png contact sheets
```

`EX_WORK` (default `/tmp/ex_char_work`) holds intermediate renders. `EX_ONLY=moses` builds a subset (finish with a full
build). `EX_NOBAKE=1` skips Moses's stoop bake; `EX_NO_EXPR=1` skips the per-expression renders in `preview`.
Checked 2026-11-14 with Blender 5.2.3. The build reads `assets/exodus/design.json` (`characters.<id>.sheetX/sheetY`,
`sheet.art`, optional `characters.<id>.propUV`) and the Set role's `model/set_id_2x.*`; rebuild after either changes.
Sheet positions used: pharaoh (−0.33, 0.015), moses (0.0, 0.015), miriam (0.33, 0.015) (source: design.json).

## 1. What is in the GLBs (`assets/exodus/model/`)

| | moses | pharaoh | miriam |
|---|---|---|---|
| Triangles (target < 25k, as Ruth) | **24,772** | **24,884** | **22,872** |
| Skinned body (one mesh, ≤ 4 influences) | `moses_body` 24,004 | `pharaoh_body` 22,578 | `miriam_body` 22,108 |
| Rigid props (child of one bone) | `moses_staff` → `staff` (684), `moses_eyelids` → `eyelids` (84) | `pharaoh_chariot` → `chariot` (1,686), `pharaoh_wheelL` → `wheelL` (536), `pharaoh_eyelids` | `miriam_tambourine` → `tambourine` (680), `miriam_eyelids` |
| Top of silhouette (verify) | 0.371 (stooped; staff crook ~0.366) | 0.388 (cobra on the nemes) | 0.344 |
| Bones | 33 | 31 | 31 |

- One material per GLB (`ex_page`). Attributes POSITION NORMAL TEXCOORD_0 (page) TEXCOORD_1 (face decal) JOINTS_0
  WEIGHTS_0; the build asserts the UV order, `verify` re-checks it. No animations.
- Character-local: root at the origin, feet on y = 0, facing +Z, 1 unit = art width.
- Prop nodes (Ruth precedent): the joint node is the bone, the mesh under it is `<char>_<bone>`: `moses/staff`,
  `pharaoh/chariot`, `pharaoh/wheelL`, `miriam/tambourine` (and `*/eyelids`). Hidden-by-default props (chariot, wheelL,
  tambourine) are exported **visible**; the timeline's t = 0 `prop` events hide them (as Ruth's sheaf).
- `characters.blend` holds the three rigs at their sheet positions (region ids in the scene property `ex_regions`).

## 2. Rest pose (for Animation)

- A-pose, arms 55° below horizontal. Open hands as Ruth (relaxed curl, palm toward the body).
- **Moses is slightly stooped in the rest pose** (Naomi method): built straight (~0.38), then baked (degrees about
  design X, + = top toward the viewer): `chest` +8, `neck` +8, `head` −10, `upperArmL/R` −8. Do not straighten in idle.
  Listed in `regions_characters.json restPose.bakedPose`. After the bake the staff mesh is shifted so its foot sits at
  y = 0.003.
- **Moses's right hand is a fist round the staff** (wrist cocked 20° below horizontal, palm to the viewer); the staff
  stands vertical through the fist, foot on the page, crook knot at the top curling outward (−X). `staff` bone: grip →
  top of the straight shaft; `staffTip` (leaf, child of `staff`): head at the top of the crook, tail 0.013 up — use it
  for FX (sparkle, snake hand-off). To open the hand rotate `fingersR` the other way.
- **Pharaoh's chariot** sits round his feet in the rest pose: floor top y = 0.035 (his soles are at 0, inside the floor,
  until `ride` lifts the hips by 0.035), floor x ±0.044, z −0.026…+0.060, breastwork top 0.153 at the front sloping to
  0.085 at the open back, red sun disc on the front, pole forward to z ≈ 0.15. Wheels r = 0.034 at x ±0.060, axle
  y 0.034, z −0.004 (they touch the page). `chariot` bone: (0, 0.035, 0) → up 0.03, child of `root`. `wheelL` bone:
  wheel centre → +X along the axle (0.02), child of `chariot`: **spin = rotate about the bone's own Y (the axle)**; pop
  off = translate / rotate the bone, then the S12 `prop` event hides it (the set's `looseWheel` takes over).
- **Miriam's tambourine** floats where it is held: the frame passes through the left palm (grip), the drum extends past
  the fingers, drum axis ⟂ the palm width. `tambourine` bone: grip → drum centre, child of `handL`. Every clip that
  shows it poses the arm to it (`tambourine_dance`: raise `upperArmL`).
- Knee pivots (`kneeY`): moses 0.104, pharaoh 0.107, miriam 0.095. Pharaoh's shins are bare (legs modelled from just
  above the knee); Moses's and Miriam's robes cover all but the feet. Robe / kilt skirts blend hips → thighs (→ shins)
  as Ruth (hips / spine only below the waist).

## 3. Bones (CONTRACT §3)

Humanoid set exactly as Ruth on all three. Extras:

| Bone | Parent | What follows it |
|---|---|---|
| `beard1` → `beard2` (moses) | `jaw` → chain | the long beard hanging in front of the chest (beard1 chin → mid-beard, beard2 → tip). Top 22 % blends to jaw/head. A jaw opening swings the beard a little (natural); counter-rotate `beard1` if unwanted |
| `mantleL`, `mantleR` (moses) | `chest` | the open mantle's front panels below the chest (85 % at the hem, fading out by 80° round the side); rotate about local X to swing |
| `mantleBack` (moses) | `chest` | the mantle's back drape below the shoulder blades (|angle| > 105°, 85 % at the hem) |
| `staff` → `staffTip` (moses) | `handR` | rigid staff; `staffTip` is a leaf with no mesh (FX anchor) |
| `nemes1L`, `nemes1R` (pharaoh) | `chest` | the nemes lappets hanging on the chest (front, below the shoulder line). Parent `chest` (not `head`) so a head turn does not swing them through the chest. `soggy`: rotate them down/inward |
| `nemesBack` (pharaoh) | `head` | the nemes back drape below the shoulder line |
| `chariot` → `wheelL` (pharaoh) | `root` | rigid chariot body + right wheel + pole; left wheel |
| `scarf1` → `scarf2` (miriam) | `head` | the scarf's back drape, nape to hips (as Ruth) |
| `braid1` → `braid2` (miriam) | `head` | the thick braid from behind her left jaw over her left shoulder down the chest to the waist (head-weighted above the neck base) |
| `tambourine` (miriam) | `handL` | rigid tambourine |
| `eyelids` | `head` | blink: scale local **Y**: 1 = open, **12.78 = closed** (all three), ~6 = half |
| `jaw` | `head` | chin, lower lip, lower half of the mouth decal; Moses's beard below the mouth; Pharaoh's gold false beard (100 % jaw) |

## 4. How the meshes are made

- **Moses**: KING head × 1.04 (deep sockets, big nose, strong brow ridge, thin lips). Shoulder-length white hair shell,
  high receding forehead, covers the ears. Facial beard (`build_beard`), drooping moustache, and a separate **long
  beard** lofted from the chin to mid-chest (sections in front of the tunic, strand grooves, two-lobed tip, a slight
  wave). Cream tunic to the ankle (sleeves to the wrist), twisted two-strand **rope belt** under the mantle with a knot
  and two frayed tails in the opening. **Mantle**: Boaz's open abaya method (`open_front`), wide sleeves to mid-forearm,
  hem at mid-shin, solidified; stripes cut by vertical planes through the body axis (clean straight edges).
  Staff: gnarled tube with knots, crook curl and knot at the top.
- **Pharaoh**: KING head × 1.07 / 0.97 wide (long face, strong jaw, long nose, high cheekbones). Bare torso and arms
  (a skin "robe" whose sleeves are the upper arms, light pectoral / sternum shaping); forearms + hands from
  `build_forearm_hand`. **Nemes**: Ruth's `hood()` with a big flare (trapezoid wings), lappets pulled in front of the
  shoulders, back drape; cut into horizontal stripes by bisecting planes (gold forehead band, then lapis / gold every
  0.0114). Cobra (uraeus) rising from the band. **Collar**: laid on the torso surface by arc length from the neck
  (broad in front, narrower over the shoulders / back), two raised cords and a beaded edge. Pleated white kilt to above
  the knee, red belt, red apron with two gold bars (cut cleanly by planes). Gold arm-bands and bracelets, gold
  braided false beard, gold sandals, bare shins (`LEG_ROWS_KNEE`). Chariot as §2.
- **Miriam**: Esther head × 1.015 / 1.02 (fuller cheeks, softer jaw). Dark brown hair under a teal `hood()` scarf,
  thick three-strand braid (alternating tilted lobes round a core tube, a rust tie and a tuft). Saffron dress (Ruth's
  shell), three-quarter sleeves; the **hem border** (bottom 0.017, cut by a plane) and the **cuffs** are region `hem`,
  with a zig-zag embroidery relief. Rust woven belt + tie, 19-bead coral necklace on the neckline, bare feet.
  Tambourine: wooden frame, drum skin, four pairs of jingles, two ribbons.
- New generic helpers (all in ex_characters.py): `open_front`, `sleeve_sv`, `ring_rows_shell` (kilt), `shell_profile`
  / `at_arclen` (collar), `rope`; `make_part_object` gained a `cuts` + `retag` step (bisect the finished part by planes,
  re-tag faces by centroid and piece: 0 = garment body, 1 = sleeves); `build_leg` gained `rows_in` / `rk`.

## 5. Regions (`model/regions_characters.json`)

| moses | pharaoh | miriam |
|---|---|---|
| skin, hair (hair + beard + moustache), tunic, mantleA (front panels, sides-back, sleeves), mantleB (side stripes, back centre, cuffs, hem band), belt, sandals, staff | skin, nemesA, nemesB, collar, kilt, sash (belt + apron), bands (arm-bands, bracelets, apron bars, cobra, false beard), sandals; props chariot, chariotTrim | skin, hair (hair + braid), scarf, dress, hem (hem border + cuffs), belt (belt, tie, braid tie), necklace; props tambourine, ribbons |

- Part anchors (slivers): hands → that character's face skin (all three); Moses's and Miriam's feet → face skin.
  Pharaoh's legs are printed normally.
- Small regions: `miriam.necklace` takes its own widest printed spot (self anchor).
- **Hidden props are not printed**: `chariot` → `pharaoh.nemesB` (gold), `chariotTrim` → `pharaoh.sash` (red),
  `tambourine` → `moses.staff` (wood), `ribbons` → `miriam.belt` (rust). The first target tried is `set.<region>`
  (`set.chariot`, `set.chariotTrim`, `set.tambourine`, `set.ribbons`) in case the Set role prints one; override per
  region with `design.json characters.<id>.propUV.<region> = [u, v]`.
- ID render for the line art: `model/id_characters_2x.png/.json`, front ortho of the final (stooped) rest pose at the
  sheet positions, eyelids and hidden props hidden.

## 6. UVs

UV0 = page projection at the sheet position (rest pose after the stoop bake) + occlusion pass + ID-render fix, as Ruth.
UV1 = face decal rect `faceDecal.rectLocal`. Moses's beard / moustache carry the decal (the mouth sits on them, with a
soft lip patch under closed mouths, LESSONS L42).

## 7. Faces (`docs/exodus/design/faces/`, `overview.png` with a 64 px "phone distance" row)

| moses (default `calm`) | pharaoh (default `smug`) | miriam (default `calm`) |
|---|---|---|
| calm, talk, curious, amazed, worried, scared, brave, pray, joy | smug, talk, laugh, angry, shock, scared, sad, sneaky, soggy | calm, talk, sad, pray, worried, scared, wow, joy, sing |

- Moses: bushy **white** brows (white fill, soft grey edge, hair tufts) carry the acting; forehead lines (bent up when
  worried / scared), crow's feet, under-eye lines, cheek folds; sweat drop on `scared`.
- Pharaoh: **kohl** liner (heavy upper line, winged outer corner, dark lower line), thin high dark brows, comic range:
  half-lidded `smug`, puffed cheeks on `angry`, huge eyes on `shock`, wet eyes on `sad` (real sorrow), half-closed
  drippy `soggy` with water drops.
- Miriam: lashes, blush, wide `wow`, round singing mouth `sing`.
- `regions_characters.json clipExpression` maps every CONTRACT §4 clip to a suggested expression.

## 8. Checks done (2026-11-14)

- `verify`: bone sets equal CONTRACT §3 for all three, 0 actions, ≤ 4 influences, UV order OK, all < 25k.
- `posetest` (`preview_pose.png`): elbows, finger curl, thigh + knee, spine, head turn, jaw, half blink, mantleL /
  mantleBack / beard1-2, nemes1L / nemesBack, scarf2 / braid1-2: no tearing at preview size.
- `uvcheck` (`preview_uvcheck.png`): front ortho equals the sheet; 3/4 and back keep each region's colour.
- **Pitfall (fixed 2026-11-14):** the post-stoop staff correction first measured the foot in world space, which
  includes the sheet offset (rig at sheetY), so the staff foot sat at y = 0.003 − sheetY (below the page in the GLB)
  and printed on the art-rect bottom edge. Now the foot is character-local y = 0.003 (verified on the re-imported GLB)
  and prints 0.030 above the art bottom with sheetY = 0.027 (design.json, Set role).
- Previews: `preview_moses.png`, `preview_pharaoh.png`, `preview_miriam.png` (front, 3/4, side, back, face close-ups,
  hands, hidden props shown, every expression on the model), `preview_all.png` (line-up).

## 9. Not done / rough edges

1. Not tested in Unity or on a phone (prop show / hide, chariot / wheel pivots, blink by joint scale).
2. The nemes is a `hood()` drape, not a stiff pleated cloth: from behind it reads as a striped bell down to the upper
   back rather than a tight tail; stripes are horizontal planes (they mirror front-to-back through UV0, same colours).
3. Mantle stripes give only two visible front stripes per side (ochre panel + dark side stripe): with the mantle about
   2.2× wider than deep, more stripes would print narrower than ~2 mm.
4. Pharaoh stands inside the chariot floor at rest; only `ride` (hips +0.035) puts his soles on it. Feet / kilt vs.
   the breastwork in `ride` / `wobble` should be checked by Animation.
5. Hidden props float at their held place; clips must pose the arms to them. Weights are procedural; deep kneels
   (`kneel_bow`) and `soggy_sit` should be checked against the robe / kilt.
6. Prop colours depend on Pharaoh's printed nemes / sash, Moses's staff and Miriam's belt; if those move, rebuild.
