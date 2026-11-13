# Ruth — character models, rig, weights, UVs, faces (Characters role)

Owner: Characters (Blender). Binding brief: [CONTRACT.md](CONTRACT.md) §2–§3, look: [DESIGN.md](DESIGN.md). Built by
`pipeline/ru_characters.py`, which started as a copy of `pipeline/es_characters.py` (Esther) and keeps its method;
`pipeline/story_mesh.py` is unchanged (every new helper lives in ru_characters.py).

## Rebuild

`python3 pipeline/ru_characters.py all` runs every step and prints the verify summary. One by one:

```
python3 pipeline/ru_characters.py faces                                          # 20 face decal PNGs + overview (Pillow)
blender -b --factory-startup --python pipeline/ru_characters.py -- build         # ~15 s: meshes, rig, stoop bake, UVs,
                                                                                  #   ID render, GLBs, characters.blend
python3 pipeline/ru_characters.py proof                                          # $RU_WORK/uvproof.png
blender -b --factory-startup --python pipeline/ru_characters.py -- preview       # EEVEE demo-palette renders
blender -b --factory-startup --python pipeline/ru_characters.py -- uvcheck       # models wearing uvproof.png via UV0
blender -b --factory-startup --python pipeline/ru_characters.py -- posetest      # bend / blink / jaw / cloth bones
blender -b --factory-startup --python pipeline/ru_characters.py -- verify        # re-import GLBs: bones, skins, tris
python3 pipeline/ru_characters.py compose                                        # model/preview_*.png contact sheets
```

`RU_WORK` (default `/tmp/ru_work`) holds intermediate renders. `RU_ONLY=ruth` builds a subset for iteration (it then
writes a blend and regions JSON with that subset only, and cross-character anchors fall back; always finish with a full
build). `RU_NOBAKE=1` skips Naomi's stoop bake (debug only). Checked 2026-11-14 with Blender 5.2.3.

The build reads `assets/ruth/design.json` (`characters.<id>.sheetX/sheetY`, `sheet.art`, optional
`characters.<id>.propUV`) and the Set role's `model/set_id_2x.png/.json`; rebuild after either changes.

## 1. What is in the GLBs (`assets/ruth/model/`)

| | ruth | naomi | boaz |
|---|---|---|---|
| Triangles (target < 25k) | **23,436** | **23,480** | **24,380** |
| Skinned body (one mesh, ≤ 4 influences) | `ruth_body` 20,692 | `naomi_body` 22,340 | `boaz_body` 23,196 |
| Rigid props (child of one bone) | `ruth_sheaf` → `sheaf` (2,060), `ruth_stalks` → `stalks` (600), `ruth_eyelids` → `eyelids` (84) | `naomi_staff` → `staff` (408), `naomi_baby` → `baby` (648), `naomi_eyelids` | `boaz_stalks` → `stalks` (1,100), `boaz_eyelids` |
| Top of silhouette (verify) | 0.327 | 0.314 (stooped; 0.32 straight) | 0.3805 |
| Bones | 30 | 30 | 30 |

- One material per GLB (`ru_page`). Attributes POSITION NORMAL TEXCOORD_0 (page) TEXCOORD_1 (face decal) JOINTS_0
  WEIGHTS_0; the build asserts the UV order and `verify` checks it after re-import. No animations.
- Character-local: root at the origin, feet on y = 0, facing +Z, 1 unit = art width.
- **Prop nodes** (Esther's `king/ring` precedent): the joint node is the bone (`sheaf`), the mesh object under it is
  `<char>_<bone>` (`ruth_sheaf`), so `prop("ruth/sheaf")` finds the joint and hides / shows the renderers under it.
  Nodes: `ruth/sheaf`, `ruth/stalks`, `naomi/staff`, `naomi/baby`, `boaz/stalks` (also `*/eyelids`). Hidden-by-default
  props (sheaf, stalks, baby) are exported **visible**; the timeline's t = 0 `prop` events hide them (story.py does).
- `characters.blend` holds the three rigs at their sheet positions (region ids in the scene property `ru_regions`).

## 2. Rest pose (for Animation)

- A-pose, arms 55° below horizontal (as Esther). Open hands relax 14° / 22° / 12° per finger joint, palm toward the
  body turned 28° backward, thumb forward.
- **Naomi is stooped in the rest pose.** Built straight, then posed and baked as the new rest skeleton (design-X
  degrees, + = top toward the viewer): `chest` +15, `neck` +14, `head` −17 (face tipped back up), `upperArmL/R` −15
  (arms hang plumb again). So her rest `neck` / `head` bones lean forward; do not "straighten" them in idle — that is
  her posture. Listed in `regions_characters.json restPose.bakedPose`.
- **Naomi's right hand is a fist round the staff** (wrist cocked 20° below horizontal, palm to the viewer). The staff
  stands vertical and runs diagonally through the fist (a real walking-stick grip); bottom at y ≈ 0.003, top knob
  0.05 × S above the grip. `staff` bone: grip → top. To open the hand rotate `fingersR` the other way.
- Hidden props sit where they will be held, so arms must be posed to them: `sheaf` floats in front of the chest
  (bundle axis tilted up to her right, centre ≈ (0.002, chestY − 0.018, front + 0.024)); `baby` lies across the chest
  in front of the robe, head toward her left (+X); `stalks` cross the right palm at the grip point of the open hand
  (curl `fingersR` ~60–75° to close round them).
- Knees / kneeling: legs are modelled only below y ≈ 0.05 (shin, ankle, foot, sandal); the robes cover the rest.
  Skirt weights blend from hips into thighL/R and, below the knee, shinL/R (left / right by x), as Esther. Since this
  build the skirt below the waist takes only hips / spine before the leg blend (see §8, fixed pitfall), so posing the
  chest or shoulders never moves the hem. Knee pivot heights (`kneeY`): ruth 0.091, naomi 0.088, boaz 0.105.
- Hands: forearm from inside the sleeve, palm, four 3-joint fingers + thumb, one `fingers` bone per hand (all four
  fingers fold as one; weights fade across the knuckles). Ruth's forearms show below the three-quarter sleeves (with a
  bead bracelet on the left wrist, skinned to forearmL / handL).

## 3. Bones (CONTRACT §3)

Every character: `root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R
footL/R toeL/R fingersL fingersR eyelids` (local Z to the viewer where the bone is not along Z, as Esther). Extras:

| Bone | Parent | What follows it |
|---|---|---|
| `scarf1` → `scarf2` (ruth) | `head` → chain | the scarf's back drape from the nape to below the waist. Parented to `head` per contract: a head turn swings the tail (counter-rotate `scarf1` if unwanted) |
| `shawl1` → `shawl2` (naomi) | `head` → chain | the shawl's back drape, nape to hips |
| `headcloth` (boaz) | `head` | the head-cloth's back drape (nape to shoulder blades) |
| `cloakL`, `cloakR` (boaz) | `chest` | the open robe's front panels from the chest to the hem (85 % at the hem, fading out by 80° round the side); rotate about local X to swing them |
| `sheaf` (ruth) | `chest` | rigid sheaf |
| `stalks` (ruth, boaz) | `handR` | rigid handful (grip → up along the palm) |
| `staff` (naomi) | `handR` | rigid staff |
| `baby` (naomi) | `chest` | rigid baby, across the chest |
| `eyelids` | `head` | blink: scale local **Y**: 1 = open, **12.78 = closed** (all three), ~6 = half |
| `jaw` | `head` | chin, lower lip, lower half of the mouth decal, Boaz's beard below the mouth |

Head-cloth weights (all three): head above the chin, neck / chest / shoulders (+ a little upperArm) below, the back
drape on the chain bones below the shoulder line.

## 4. How the meshes are made

- Heads: D&G base head mapped by landmarks; Ruth from Esther's spec × 0.965 (softer jaw, fuller cheeks), Naomi
  Esther × 0.94 / 0.97 wide (rounder fuller face, thinner lips, small round nose, low cheekbones), Boaz from the
  king × 1.05 / 1.09 wide (S fixed at 1.40).
- **`hood()`** (new): Ruth's cream scarf, Naomi's grey-blue shawl and Boaz's keffiyeh are one generic surface: rings
  from the free edge up to the crown; on the hair above eye level, hanging plumb from the widest part of the head
  below, settling onto the shoulders / chest (front ends pulled toward the chest centre) and lying down onto the back
  below the shoulder line; pushed out of the sleeves; folds deepen below the chin, the hem waves; solidified. Ruth's
  scarf leaves a band of dark hair at the front; Naomi's shawl is set back so grey hair shows at forehead and temples.
- Robes: Esther's torso shell with sleeves extruded from ports, flared folds, rolled hems (`build_robe`, now with a
  region / name / solidify). Ruth: sage dress, three-quarter sleeves, woven brown belt with a two-tail tie. Naomi:
  rose robe with fuller waist and long slightly belled sleeves, wide ochre sash with knot and tails. Boaz: cream tunic
  (sleeves to the wrist, shows as cuffs and at the hem) under the olive abaya — a larger shell whose front is opened
  cleanly in superellipse angle space (narrow at the neck, 30° half-angle at the hem), solidified; rust sash on the
  tunic between the panels; head-cloth with a two-ring dark cord (agal).
- Beards: Boaz full short beard with curl rows and a moustache (decal + jaw).
- Props: sheaf = tied bundle (tie band region `sheafTie`) with 22 bearded ears fanning from the top and cut ends below;
  stalks = thin stalks with bearded ears; staff = slightly crooked stick with knots and a round knob; baby = swaddle
  with a wrap band and a head whose front faces are region `babyFace`.
- Sandals: sole + toe strap + instep strap + ankle strap; skin between (all three).

## 5. Regions (`model/regions_characters.json`)

| ruth | naomi | boaz |
|---|---|---|
| skin, hair, dress, scarf, belt (incl. tie), bracelet, sandals; props sheaf, sheafTie, stalks | skin, hair, robe, shawl, sash (incl. tie), staff, sandals; props baby, babyFace | skin, beard (beard + moustache), hair, robe, tunic, headcloth, cord, sash (incl. tie), sandals; prop stalks |

- Part anchors: hands and feet skin (slivers on the sheet) take one UV0 texel from the same character's face skin.
- Small regions: `bracelet` and `cord` take their own widest printed spot (self anchors, printed normally).
- **Hidden props are not in the printed drawing** (left out of the ID render). Their regions sample a printed region:
  sheaf → the set's `sheaf` drawing, sheafTie → set `sheafTie`, stalks (Ruth and Boaz) → set `barley`, baby → Ruth's
  scarf (cream), babyFace → `ruth.skin` (a texel of Ruth's printed face skin, clear of the features; the build picks it as `ruth.FACE` and records the real region). Fallbacks when the set drawings are missing: Naomi's sash (gold) / Ruth's
  belt. Override per region with `design.json characters.<id>.propUV.<region> = [u, v]`. Listed per region as
  `anchoredTo` + `anchorUV` + `printNote`.
- The baby's face is a decal too: its UV1 points at `BABY_CORNER` (0.012–0.112 square) of the **naomi** decal, where
  every naomi expression PNG carries a small sleeping face. Integration: the baby mesh must use the same face-decal
  texture as Naomi's body (one material per GLB, as Esther).
- ID render for the line art: `model/id_characters_2x.png/.json`, front ortho of the final (stooped) rest pose at the
  sheet positions, eyelids and hidden props hidden.

## 6. UVs

UV0 = page projection at the sheet position (rest pose after the stoop bake) + occlusion pass + ID-render check, as
Esther. UV1 = face decal rect `faceDecal.rectLocal` (Naomi: the rect is in her straight head frame; UV1 was baked
before the stoop, so it is correct on the mesh).

## 7. Faces (`docs/ruth/design/faces/`, `overview.png` with a 64 px "phone distance" row)

| ruth | naomi | boaz |
|---|---|---|
| calm (default), sad (wet eyes), talk, shy (side-down glance, strong blush), joy, pray (closed), brave | tender (default), sad, tired (heavy lids), talk, surprised, joy | smile (default), talk, curious (one brow up, side look), kind, sneaky (brow up, side glance, smirk), laugh, joy |

New compared with Esther: brows shaped per expression, a soft nose hint (tip curve + nostril ticks), cheek blush,
upper-lid crease, smile / crow's-feet lines (Naomi and Boaz), Naomi's under-eye lines, soft cheek folds and grey brows,
Boaz's mouths with a light lip rim / patch so they read on the dark beard (LESSONS L42). Integration's
`assets/ruth/faces.json` uses the same names; `regions_characters.json clipExpression` is only a suggestion.

## 8. Checks done (2026-11-14) and pitfalls met

- `verify`: bone sets equal CONTRACT §3 for all three, 0 actions, ≤ 4 influences, UV order OK, all < 25k.
- `posetest` (`preview_pose.png`): elbows, finger curl, thigh + knee, spine, head turn, jaw, half blink, scarf2 / shawl2
  / cloakL / headcloth bends: no tearing at preview size. `uvcheck` (`preview_uvcheck.png`): front ortho equals the
  sheet; 3/4 and back keep each region's colour.
- **Pitfall (fixed here, still present in Esther):** `skirt_weights` used a weight spec with shoulder bones for the
  whole robe; below the waist every bone is far away, the normalisation let the shoulders win (~0.2 shoulderL/R weight
  at knee height). Invisible at rest, but Naomi's baked stoop dented her skirt. ru_characters.py uses hips / spine only
  below the waist. Esther's `es_characters.py` has the same weights (a shoulder shrug would pull her hem).

## 9. Not done / rough edges

1. Not tested in Unity or on a phone (prop show / hide, the baby's decal corner, blink by joint scale).
2. Shoulders of the shawl and the head-cloth end in fairly stiff corners where the cloth meets the arm (A-pose); in
   motion they follow chest / shoulders / a little upperArm, not a cloth sim.
3. Hidden props float at their held place in the rest pose; every clip that shows them must pose the arms to them.
4. The staff is rigid to the fist: Naomi's `idle` (both hands on the staff) must bring the left hand to it.
5. Weights are procedural; deep kneels (`glean`, `bow_kneel`) should be checked for the dress front against the shins.
6. Prop colours depend on the Set role's printed `sheaf` / `barley` drawings; if those move, rebuild.
