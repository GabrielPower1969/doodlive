# Joseph — rig notes (Characters role)

Built by `pipeline/js_characters.py` (on the shared kit `pipeline/story_kit/characters.py`).
Run `python3 pipeline/js_characters.py all`; previews in `assets/joseph/model/preview_*.png`.

## Models

| Id | File | Height (re-imported GLB, top) | Triangles before → after (all meshes, incl. hidden props) |
|---|---|---|---|
| joseph | `joseph.glb` | 0.340 (contract 0.34) | 24,470 → **40,418** (body 26.4k incl. hair locks 11.1k; coat incl. trims 9.8k; head-cloth 2.4k, collar 1.7k) |
| brother | `brother.glb` | 0.376 (0.38) | 24,864 → **45,624** (hair curls 11.4k, beard curls 7.2k) |
| pharaoh | `pharaoh.glb` | 0.454 crown top (0.45) | 24,450 → **37,502** (head-cloth 3.6k, collar beads + pendants 7.9k) |
| jacob | `jacob.glb` | 0.336 stooped (0.33) | 21,108 → **39,540** (beard strands 8.2k, cheek-beard locks 5.5k, shawl fringe 2.9k) |

Cast total 163k (was 95k) + set `twolands` 42k = 205k on screen, under the 300k cap the owner set on 2026-11-15
(the old 25k-per-human line of CONTRACT §2 / QUALITY-BAR was lifted by the owner for this pass).

### 2026-11-15 sculpt polish (owner: 精致、多面、儿童喜爱、精修)

Code: `pipeline/js_characters.py` section "sculpt polish" (`polish_<char>`, run after each builder; `JS_NOPOLISH=1`
builds the old models). **No bone, bone position, clip, prop socket, size or expression name changed**: the polish
only adds geometry weighted to existing bones; the anim GLBs were re-baked with `python3 pipeline/js_animate.py all`.

| Character | What changed |
|---|---|
| all | eyes ~8-11 % bigger in every decal (`EYE`), a third catch-light, rosier default cheeks; raised 3D sandal straps (ankle, instep, toe) and a visible sole on the painted sandal bands (`straps<L/R>`, same printed piece as the leg) |
| joseph | jaw-length bob as 22 sculpted locks combed from the centre parting, ends tucked under (`hairLocks`); neck 14 % thicker (mesh only); coat: gold rolled edging (region `trim` → takes `coat2`, DESIGN "gold edging line"), a two-cord hem band with 26 little diamonds, two gold bands on each bell cuff (`coatTrim`, `coatCuffs`, skinned into `joseph_coat`, coatL/R panel weights copied); cord round the tunic neckline |
| brother | ~150 round curls over the hair, curls over the beard (mouth left clear for the decal); bronze ring buckle + stitching on the belt; laced neckline slit (region `cord` → `brother.belt`); bag toggle + seam stitches; default `sour` a touch softer |
| pharaoh | striped gold / lapis head-cloth (nemes) under the double crown: forehead band, wings over the ears, lappets on the collar, short back (`pharaoh_nemes` part, skinned head → chest; regions `nemesA` → `pharaoh.collar`, `nemesB` → `pharaoh.apron`); ears removed (under the cloth); collar: three bead rows (gold / lapis / gold) and 48 drop pendants (`collarJewels`); lapis inlay + gold studs on the arm-bands, a gold-and-lapis cartouche buckle (`jewels`, region `inlay` → `pharaoh.apron`); default `grand` eyes open and friendly |
| jacob | the long beard carries 11 flowing strand locks with wavy tips (`beardStrands`), the cheek beard 9 soft locks (`beardLocks`); woven double border and 120-tassel fringe on the shawl hem (`shawlFringe`); staff: leather grip wrap under the hand and a carved ring under the knob (inside the rigid `jacob_stick` mesh, region `stick`); default `fond` eyes a little more open |

New regions (all anchored, printed as detail lines): joseph `trim`; brother `cord`; pharaoh `nemesA` `nemesB` `inlay`.
Sheet rebuilt (`python3 tools/story/sheet_joseph.py`): SHEET PASS, anchors 51/51, no slivers, detail parts 20 → 27,
pieces 155 → 156; title band still distinct (NCC 0.516 vs daniel); coloured PDF A4 OK; `check.py joseph` 0 FAIL.

All four: kit contract humanoid, A-pose (arms 55° below horizontal), facing +Z, feet on y = 0, ≤ 4 influences,
no animations in the model GLBs, UV0 = page (`UVMap`), UV1 = face decal (`decal`), one material `js_page`.

### 2026-11-15 3D eyes pilot (Joseph only; owner: "eyes like a doll's, fake, anime; make eyes, brows, nose 3D and alive")

Code: `pipeline/js_characters.py` section "3D eyes (pilot)" (`E3`, `eyes3d_apply`, `e3_json`); runtime
`unity/Assets/DoodLive/DavidGoliath/Scripts/DGFace3D.cs`, shader `DavidGoliath/Shaders/DGEye.shader`, wired by
`Story/Editor/StorySetup.cs`. **`JS_EYES3D=0` rebuilds the old decal-eyed Joseph byte for byte** (checked: model GLBs,
decals, regions, anim GLB, clips.json); brother, pharaoh and jacob never change (byte-identical GLBs either way).

| Part | What it is |
|---|---|
| bones `eyeL`, `eyeR` | new, children of `head`, at the eyeball centres (design x = ±0.405 hw, y = eye line); no weights; clips key them at rest; the runtime aims them |
| `joseph_eyeL`, `joseph_eyeR` | rigid eyeballs on those bones (radius 0.245 hw, a cornea bulge over the iris), material `js_eye` -> Unity `DoodLive/DGEye`, UV0 = `model/eyes_joseph.png` (sclera, iris, pupil) |
| body | face around the eyes / nose subdivided (3 local passes, blended smooth/linear so no seams), sculpted nose (tip, alae, nostrils, slimmer bridge), brow ridge, eye sockets (skin hides behind the eyeball / under the lids), upper + lower eyelids with a rounded margin and a crease tuck (page material; page UV = the face texel next to them, so they take the child's skin colour) |
| `joseph_eyeLines` | brows (soft tapered ribbons on the forehead) + upper lash line + three short lashes, skinned to `head`, material `js_eyeLines` (fixed colours from the atlas; kids do not colour eyes) |
| `joseph_eyelids` | removed (the `eyelids` bone stays: clips still key it, the runtime reads its scale as a lid closure) |
| decals | `joseph_*` keep mouth, blush, tears, sweat; eyes, brows and the nose hint are gone (3D now) |
| blend shapes | on `joseph_body` and `joseph_eyeLines`, same names: `blinkL_a/_b`, `blinkR_a/_b` (two halves = an in-between), `lidsWide`, `squint`, `lidsSad`, `cheekRaise`, `smile`, `frown`, `browUpL`, `browUpR`, `browDown`, `browInnerUp`; default weights 0 |
| `model/face3d_joseph.json` | controls -> blend shapes, face name -> control weights, gaze / blink settings; read by DGFace3D |

The sheet is unchanged: the 3D parts are built after the ID render and the UV fixes (`id_characters_2x.png` identical).
Mouth: kept as the decal (+ `jaw` bone + the `smile` / `frown` shapes move the skin it is painted on).
Clips (`pipeline/js_animate.py`): Joseph's short baked blinks are dropped (the runtime blinks); held lid levels and
eyes-closed holds (`eyelids.sy` 12, e.g. the hug) stay. Morph targets are exported only for meshes that have shape keys.

Face name -> controls (0..1; gaze in degrees, + = up):

| Face | Controls |
|---|---|
| bright | smile .40, cheekRaise .25, browUp L/R .15, squint .10 |
| talk | smile .12, browUp L/R .22 (+ brows lift with the voice loudness) |
| joy | smile .95, cheekRaise .90, squint .80, browUp L/R .45 |
| scared | lidsWide .95, browInnerUp .85, browUp L/R .40, frown .35 |
| sad | lidsSad .75, browInnerUp .90, frown .65, blink L/R .12, gaze −10 |
| pray | blink L/R 1 (eyes closed), browInnerUp .30, smile .20, gaze −12 |
| wise | squint .35, smile .32, blink L/R .18, browDown .08 |
| moved | browInnerUp .75, squint .25, smile .15, lidsSad .30, gaze +3 |
| tears_joy | smile .85, cheekRaise .85, squint .85, browInnerUp .55 |

Evidence: `model/preview_eyes3d_compare.png` (old vs new: front, 3/4, profile), `model/preview_eyes3d_expressions.png`
(the nine faces + half blink + two gazes). Render again: `blender -b --factory-startup --python
pipeline/js_characters.py -- eyes3d` (and once with `JS_E3_BLEND=<old characters.blend> JS_E3_FACES=<old faces dir>
JS_E3_TAG=old`), then `python3 pipeline/js_characters.py eyes3d`.

## Bones (contract §3) and what they move

| Character | Extra bones | Parent | Drives |
|---|---|---|---|
| joseph | `coatL`, `coatR` | chest | the coat's front panels below the waist (50 % panel bone, the rest follows hips / thighs so the tunic stays inside) |
| joseph | `coat` | chest | prop switch only (no weights). The coat mesh `joseph_coat` is skinned to the body bones + `coatL/R`; its GLB node is **nested under the `coat` joint**, so `prop("joseph/coat", …)` toggles it. glTF ignores the transform of a skinned mesh node, so skinning is unaffected. |
| joseph | `nemes` | head | rigid head-cloth `joseph_nemes` (hidden by default); lappets and wings move with the head |
| joseph | `collar` | chest | rigid broad collar `joseph_collar` (hidden by default) |
| jacob | `shawl1` → `shawl2` | head → shawl1 | the shawl's back drape (to the waist) |
| jacob | `stick` | handR | rigid walking stick (always shown); right hand is a fist round it |
| brother | `bag` | chest | the sling-bag pouch at his right hip (strap stays on chest / spine) |
| pharaoh | `apron1` | hips | the blue apron below the belt |
| pharaoh | `belly` | spine | front of the round belly (up to 95 %); rotate about design X to bounce it |

Jacob's stoop is **baked into the rest pose** (spine 6°, chest 16°, neck 14°, head −24°, upper arms −20° about design
X; `regions_characters.json` → `restPose.bakedPose`). Do not add the stoop again in clips.

## Props and looks (Joseph: one model, three looks)

| Look | Shown | Hidden |
|---|---|---|
| A, coat (S01-S03, printed on the sheet) | `coat` | `nemes`, `collar` |
| B, plain (S03-S06) | — | `coat`, `nemes`, `collar` |
| C, governor (S07 on) | `nemes`, `collar` | `coat` |

The base costume (cream sleeveless tunic, brown cord belt, sandals) is always there under the coat.

**Colour hand-over (intended, do not "fix"):** the hidden head-cloth and collar take their page UV from the coat's
printed stripes (`PROP_ANCHORS`): head-cloth stripes `nemesA` = `coat2`, `nemesB` = `coat4`; collar rings (inner to
outer) `collar1` = `coat1`, `collar3` = `coat3`, `collar5` = `coat5`. The coat the brothers took comes back as his
crown in the child's own colours. Proof: bottom row of `preview_uvcheck.png`.

## Coat stripes on the sheet

The coat is closed over the chest (a broad centre stripe) and opens below the waist over the tunic (a V). Viewer
order: `coat1` right sleeve (+ right back half), `coat2` right panel, `coat3` centre stripe, `coat4` left panel,
`coat5` left sleeve (+ left back half). Stripe edges are plane cuts (straight). Largest cell per stripe in the ID
render: 7.1 / 7.2 / 7.3 / 7.4 / 7.1 mm (before the ink line, about −0.5 mm). Five stripes kept. The coat is knee-length
with a rolled edge (a tube along both opening edges, the hem and the cuffs, joined into `joseph_coat`, same regions).

## Expressions (face decals, `docs/joseph/design/faces/<char>_<expr>.png`, 512 px, UV1)

| Character | Default | All | Mouth |
|---|---|---|---|
| joseph | bright | bright talk joy scared sad pray wise moved tears_joy | open shapes are in the decal (talk, joy, scared, tears_joy); the `jaw` bone also opens the chin |
| brother | sour | sour talk angry greedy humble shock sorry relief | on the beard: light lip rim / patch so it reads at phone distance |
| pharaoh | grand | grand talk sleepy panic curious delighted | kohl-lined eyes with a wing in every decal |
| jacob | fond | fond talk joy weep tears_joy | bushy white brows and forehead lines are in the decal; `weep` = eyes shut + tears |

Clip → expression suggestions: `regions_characters.json` → `faceDecal.clipExpression`. Blink: scale the `eyelids`
bone's local Y to `blink.closed` (closes visibly, checked in `preview_pose.png`).

## Regions under 6 mm (detail lines or anchored)

- joseph: `belt`, `sandals` → take the colour of `joseph.hair` (brown); hands, legs, bare upper arms → face skin.
- brother: `belt` (own small region, anchored to its own deepest pixel), `sandals` → `brother.belt`; `hair` (hair +
  beard, ~2.4 mm pieces) small as on every sheet; hands, legs, upper arms → face skin.
- pharaoh: `crownRed` 5.2 mm and `crownWhite` 5.7 mm (largest cell, before ink): the 0.45 crown height in the
  contract leaves no more room; `kilt` and `apron` 6.4 mm, `collar` 6.8 mm.
- pharaoh: `gold` (crown band, cobra, arm-bands, bracelets, belt, apron bars, sandals) → `pharaoh.collar`;
  `beard` (ceremonial chin beard) → `pharaoh.apron` (lapis blue).
- jacob: `belt` (own), `stick` → `jacob.belt`, `sandals` → `jacob.belt`; `shawl` is ~4 mm at its widest (the beard
  covers the front): known weak spot.

## Things the animator should know

- Two-person clips: arms reach as in other packs (Ruth / Exodus scale); partner 0.11 in front.
- Joseph's coat is a separate skinned mesh over the tunic with ~0.003 clearance: deep thigh bends can let the tunic
  show through the coat at the V (it is the same colour as the V, so it reads as the opening).
- `reveal` marker `off` removes the head-cloth (hide `joseph/nemes`); `crown_him` marker `on` shows it.
- Jacob's stick is rigid on `stick` (child of `handR`); plant it by posing the hand.
