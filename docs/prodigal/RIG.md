# The prodigal son — character models, rig, weights, UVs, faces (Characters role)

Owner: Characters (Blender). Binding brief: [CONTRACT.md](CONTRACT.md) §2–§3, look: [DESIGN.md](DESIGN.md). Built by
`pipeline/pr_characters.py`, a copy of `pipeline/ex_characters.py` (Exodus) that keeps its method (procedural quad
cages, heads mapped from the D&G base head, box-modelled hands, face decals on UV1 + `eyelids` blink, UV0 = front page
projection + occlusion pass + ID-render fix, `hood()` drapes, Boaz's open abaya). `pipeline/story_mesh.py` is unchanged.

## Rebuild

`python3 pipeline/pr_characters.py all` runs every step (about 3 minutes) and prints the verify summary. One by one:

```
python3 pipeline/pr_characters.py faces                                          # 24 face decal PNGs + overview (Pillow)
blender -b --factory-startup --python pipeline/pr_characters.py -- build         # meshes, rig, stoop bake, UVs, ID render,
                                                                                  #   GLBs, characters.blend
python3 pipeline/pr_characters.py proof                                          # $PR_WORK/uvproof.png
blender -b --factory-startup --python pipeline/pr_characters.py -- preview       # EEVEE demo-palette renders
blender -b --factory-startup --python pipeline/pr_characters.py -- uvcheck       # models wearing uvproof.png via UV0
blender -b --factory-startup --python pipeline/pr_characters.py -- posetest      # bend / blink / jaw / cloth bones + robe test
blender -b --factory-startup --python pipeline/pr_characters.py -- verify        # re-import GLBs: bones, skins, tris
python3 pipeline/pr_characters.py compose                                        # model/preview_*.png contact sheets
```

`PR_WORK` (default `/tmp/pr_char_work`) holds intermediate renders. `PR_ONLY=son` builds a subset (finish with a full
build). `PR_NOBAKE=1` skips the father's stoop bake; `PR_NO_EXPR=1` skips the per-expression renders in `preview`.
Checked 2026-11-14 with Blender 5.2.3. The build reads `assets/prodigal/design.json` (`characters.<id>.sheetX/sheetY`,
optional `characters.<id>.propUV`) and the Set role's `model/set_id_2x.*` (for `set.<region>` prop anchors); rebuild
after either changes. Sheet positions used: father (−0.33, 0.015), son (0.0, 0.015), brother (0.33, 0.015)
(source: design.json, written by the Set role).

## 1. What is in the GLBs (`assets/prodigal/model/`)

| | son | father | brother |
|---|---|---|---|
| Triangles (target < 25k) | **24,048** (body 19,406 + robe 3,844, purse 538, ring 176, eyelids 84) | **24,426** (body 23,804, purse 538, eyelids 84) | **19,640** (body 19,284, hoe 272, eyelids 84) |
| Top of silhouette (verify) | 0.339 | 0.364 (stooped, head-cloth + cord) | 0.367 (head-cloth) |
| Skinned body (one mesh, ≤ 4 influences) | `son_body` | `father_body` | `brother_body` |
| Rigid props (child of one bone) | `son_purse` → `purse`, `son_ring` → `ring`, `son_robe` → `robe`, `son_robeL` → `robeL`, `son_robeR` → `robeR`, `son_eyelids` | `father_purse` → `purse`, `father_eyelids` | `brother_hoe` → `hoe`, `brother_eyelids` |
| Shown by default | none of the props | — | hoe |
| Bones | 31 | 32 | 29 |

- One material per GLB (`pr_page`). Attributes POSITION NORMAL TEXCOORD_0 (page) TEXCOORD_1 (face decal) JOINTS_0
  WEIGHTS_0; no animations. Character-local: root at the origin, feet on y = 0, facing +Z, 1 unit = art width.
- Prop nodes (Ruth / Exodus precedent): the joint node is the bone, the mesh under it is `<char>_<bone>`. Hidden props
  are exported **visible**; the timeline's t = 0 `prop` events hide them. `StoryDirector.Prop` disables every renderer
  under the node, so **`son/robe` hides and shows all three robe pieces** (`robeL`, `robeR` are children of `robe`).
- `characters.blend` holds the three rigs at their sheet positions (region ids in the scene property `pr_regions`).

## 2. Rest pose (for Animation)

- A-pose, arms 55° below horizontal, open hands (relaxed curl, palm toward the body), as Exodus.
- **Father: slight stoop baked into the rest pose** (degrees about design X, + = top toward the viewer): `chest` +6,
  `neck` +5, `head` −7, `upperArmL/R` −6. Do not straighten it in idle. Listed in
  `regions_characters.json restPose.bakedPose`.
- **Brother's right hand is a fist round the hoe** (wrist cocked 20° below horizontal): the handle stands vertical
  through the fist from the blade socket (y ≈ 0.024) to y 0.25. The iron blade sits at 55° to the handle, pointing
  forward (+Z) and down, its cutting edge on the page (y ≈ 0.003). `hoe` bone: grip → handle foot (points down);
  `hoeTip` (leaf, child of `hoe`): head at the middle of the cutting edge, 0.010 along the blade — use it to put the
  blade on the ground in `work_field` and for FX. To carry it on the shoulder (`walk_hoe`) rotate `handR` / the arm;
  the hoe follows rigidly. To let go, rotate `fingersR` the other way.
- **Purse** (son: left hand, father: right hand): a leather bag held by its gathered neck just in front of the
  fingers, hanging plumb at rest. `purse` bone: neck → bag centre (points down). Clips that show it should curl the
  fingers (`fingersL/R`) round the neck; at rest the bag body overlaps the open fingers a little.
- **Ring** (son, right hand): gold band with a red stone on the ring finger's first segment (`ring`, child of
  `handR`); it follows `handR` only, so a big `fingersR` curl lets the finger slide inside the band (small, hidden
  until S10).
- **Robe** (son, hidden until S10): the father's best robe, rigid, already in place round the son's rest body: a
  purple sleeveless over-robe from the neck to mid-shin (hem y ≈ 0.052), open in front (gap 13° at the neck to 25° at
  the hem) with a gold border down both front edges and round the hem, round armholes. `robe` bone: chest height,
  +Y, child of `chest`. `robeL` / `robeR`: the lower front panels below the hip line (y < ≈ 0.175), bones from the
  panel top (hinge) to the hem, children of `robe`: **swing = rotate about the bone's local X** (+ ≈ forward). Checked
  in `preview_robe.png`: rest A-pose, a hug pose (arms forward, hands at chest height) and arms-up dance: the arms
  leave through the armholes; the shoulder of the robe clips the top of the upper arm only when the arm is raised
  above ~60° (it is rigid on `chest`). The seam between `robe` and the panels shows as a faint line across the front
  at hip height.
- Knee pivots (`kneeY`): son 0.094, father 0.100, brother 0.102. Son and brother: bare shins below knee-length tunics
  (legs modelled from just above the knee); the brother's shins carry leg wraps (region `belt`). Robe / tunic skirts
  blend hips → thighs (→ shins) as Ruth.

## 3. Bones (CONTRACT §3)

Humanoid set exactly as Exodus / Ruth on all three. Extras:

| Bone | Parent | What follows it |
|---|---|---|
| `purse` (son, father) | `handL` (son) / `handR` (father) | rigid money bag |
| `ring` (son) | `handR` | rigid ring |
| `robe` → `robeL`, `robeR` (son) | `chest` → `robe` | rigid robe shell; lower front panels (follow-through) |
| `beard1` → `beard2` (father) | `jaw` → chain | the fuller grey beard hanging to the upper chest; top 24 % blends to jaw/head |
| `cloakL`, `cloakR` (father) | `chest` | the abaya's front panels below the chest (85 % at the hem); rotate about local X to swing / hitch up for `run` |
| `headcloth` (father) | `head` | the keffiyeh's back drape below the shoulder line |
| `headcloth` (brother) | `head` | the knot at the nape and the two tails down to the shoulder blades |
| `hoe` → `hoeTip` (brother) | `handR` | rigid hoe; `hoeTip` is a leaf with no mesh (blade edge) |
| `eyelids` | `head` | blink: scale local **Y**: 1 = open, **12.78 = closed** (all three), ~6 = half |
| `jaw` | `head` | chin, lower lip, lower half of the mouth decal, the beards below the mouth |

## 4. How the meshes are made

- **Son**: KING head × 0.935 / 0.86 wide (young, softer jaw), ears visible. Messy dark-brown hair shell (uneven,
  asymmetric fringe, lumpy curls) plus ten flat locks curling off the fringe, crown and back. Sky-blue knee-length
  tunic (sleeves just past the elbow), yellow sash with a knot and two tails, a short sleeveless red bolero vest (open
  front, cap shoulders, ends above the sash), bare shins, sandals. First-beard shadow is painted in the face decal.
- **Father**: Boaz's build at KING × 1.005 / 1.04: grey hair under a white keffiyeh-like head-cloth (`hood()`) with a
  blue double cord, grey facial beard + moustache and a fuller grey beard lofted from the chin to the upper chest
  (rounded tip), cream tunic, brown sash + tie, deep-green open abaya (Boaz's `open_front`), wide sleeves to the
  wrist, hem at the ankle, sandals.
- **Brother**: KING head × 1.02 / 1.13 wide, square jaw, ears visible; short dark hair at the temples, short dark
  beard + moustache; beige head-cloth as a snug cap tied at the nape (knot + two tails); rust knee-length tunic with
  sleeves rolled to the elbow (a fat roll), twisted rope belt with a knot and two tails, leg wraps with a spiral relief,
  sandals; hoe (wooden handle, iron socket and blade).
- New helpers: `split_cage` (one cage into rigid pieces by face centroid), `build_purse`, `aim_bone` / `robe_test`
  (posetest).

## 5. Regions (`model/regions_characters.json`)

| son | father | brother |
|---|---|---|
| skin, hair, tunic, sash, vest, sandals; props purse, robe, robeTrim, ring | skin, hair (hair + beards), tunic, robe, sash, headcloth, cord, sandals; prop purse | skin, hair (hair + beard), tunic, belt (rope belt + leg wraps), headcloth, sandals, hoe (handle), blade |

- Part anchors (slivers): hands → that character's face skin (all three); the father's feet → face skin. The son's and
  brother's shins are printed normally.
- Small regions: `father.cord` takes its own widest printed spot (self anchor).
- **Hidden props are not printed**: `son.purse` / `father.purse` → `father.sash` (brown), `son.robe` →
  `father.robe` (the father's best robe takes the colour the child gave the father's robe; the demo palette would say
  purple), `son.robeTrim` → `son.sash` (yellow), `son.ring` → `son.sash`. The first target tried is
  `set.<region>` (`set.purse`, `set.robe`, `set.robeTrim`, `set.ring`) in case the Set role prints one; override per
  region with `design.json characters.<id>.propUV.<region> = [u, v]`.
- ID render for the line art: `model/id_characters_2x.png/.json`, front ortho of the final (stooped) rest pose at the
  sheet positions, eyelids and hidden props hidden.

## 6. UVs

UV0 = page projection at the sheet position (rest pose after the stoop bake) + occlusion pass + ID-render fix, as
Exodus: back faces sample their own region, not the drawing through the body (L51; `preview_uvcheck.png` back view).
UV1 = face decal rect `faceDecal.rectLocal`. The father's and brother's beards / moustaches carry the decal (the mouth
sits on them, with a soft lip patch under closed mouths, LESSONS L42).

## 7. Faces (`docs/prodigal/design/faces/`, `overview.png` with a 64 px "phone distance" row)

| son (default `cheeky`) | father (default `kind`) | brother (default `neutral`) |
|---|---|---|
| cheeky, talk, joy, puzzled, shock, sad, hungry, cry, idea, amazed | kind, talk, sad, longing, surprise, joy, cry_joy, plead | neutral, talk, frown, angry, hurt, soft |

- Son: big dark brows carry the acting (one brow up for `cheeky` / `puzzled`), first-beard stubble, tears on `cry`,
  a drool drop on `hungry`, looking up with an "o" on `idea`.
- Father: bushy grey brows (light fill + soft edge), crow's feet, under-eye and laugh lines; `cry_joy` = crinkled
  laughing eyes with tears.
- Brother: thick dark brows set low; puffed cheeks on `angry`, wobbly lip and wet eyes on `hurt`, relaxed small
  smile on `soft`.
- `regions_characters.json clipExpression` maps every CONTRACT §4 clip to a suggested expression.

## 8. Checks done (2026-11-14)

- `verify`: bone sets equal CONTRACT §3 for all three, 0 actions, ≤ 4 influences, UV order OK, all < 25k triangles.
- `posetest` (`preview_pose.png`): elbows, finger curl, thigh + knee, spine, head turn, jaw, half blink, father
  cloakL / headcloth / beard1-2, son robeL, brother headcloth: no tearing at preview size.
- `preview_robe.png`: the robe on the son at rest, in a hug pose and arms up (see §2).
- `uvcheck` (`preview_uvcheck.png`): front ortho equals the sheet; 3/4 and back keep each region's colour.
- Previews: `preview_son.png`, `preview_father.png`, `preview_brother.png` (front, 3/4, side, back, face close-ups,
  hands, hidden props shown, every expression on the model), `preview_all.png` (line-up).

## 9. Not done / rough edges

1. Not tested in Unity or on a phone (prop show / hide of the three robe pieces, blink by joint scale).
2. The robe is rigid on `chest`: raised arms clip its shoulders, deep leg lifts (`dance`) can poke the back hem;
   swing `robeL/R` to clear the front. The hip-height seam to the panels is visible up close.
3. The hoe blade prints small (it is seen nearly edge-on from the front): about 7 × 3 mm on A4.
4. Hidden props float at their held place; clips must pose the hands to them (purse neck between the fingers).
5. Prop colours depend on the father's printed robe / sash and the son's sash; if those move, rebuild.
