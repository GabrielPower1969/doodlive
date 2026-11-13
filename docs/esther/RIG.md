# Esther — character models, rig, weights, UVs, faces (Characters role)

Owner: Characters (Blender). Binding brief: [CONTRACT.md](CONTRACT.md) §2–§3 (ids, heights, bone names), look:
[DESIGN.md](DESIGN.md). Same family and method as David & Goliath ([../david-goliath/RIG.md](../david-goliath/RIG.md));
the generic mesh helpers now live in `pipeline/story_mesh.py` (copied from `pipeline/dg_build.py`, which is unchanged).

## Rebuild

`python3 pipeline/es_characters.py all` (or `blender -b --factory-startup --python pipeline/es_characters.py -- all`)
runs every step below in order and prints the verify summary. Steps one by one:

```
python3 pipeline/es_characters.py faces                                          # face decal PNGs + overview (Pillow)
blender -b --factory-startup --python pipeline/es_characters.py -- build         # ~12 s: meshes, rig, weights, UVs,
                                                                                  #   ID render, GLBs, characters.blend,
                                                                                  #   regions_characters.json
python3 pipeline/es_characters.py proof                                          # $ES_WORK/uvproof.png (perfect sheet)
blender -b --factory-startup --python pipeline/es_characters.py -- preview       # lit demo-palette renders (EEVEE)
blender -b --factory-startup --python pipeline/es_characters.py -- uvcheck       # models wearing uvproof.png via UV0
blender -b --factory-startup --python pipeline/es_characters.py -- posetest      # bend / blink / jaw test renders
blender -b --factory-startup --python pipeline/es_characters.py -- verify        # re-import GLBs: bones, skins, tris
python3 pipeline/es_characters.py compose                                        # model/preview_*.png contact sheets
```

`ES_WORK` (default `/tmp/es_work`) holds intermediate renders. `ES_ONLY=esther` (comma list) builds a subset for
iteration (the regions JSON then only lists that subset; run a full build before handing off). `ES_UV_TEXTURE=<png>`
makes `uvcheck` use another texture (e.g. the Sheet role's demo colouring once it exists). Checked 2026-11-14 with
Blender 5.2.3.

## 1. What is in the GLBs (`assets/esther/model/`)

| | esther | king | haman |
|---|---|---|---|
| Triangles (target < 25k) | **23,948** | **24,692** | **19,184** |
| Skinned body (one mesh, ≤ 4 influences) | `esther_body` 22,084 | `king_body` 21,560 | `haman_body` 18,156 |
| Rigid props (child of one bone) | `esther_necklace` → `chest` (1,220), `esther_diadem` → `diadem` (560), `esther_eyelids` → `eyelids` (84) | `king_crown` → `crown` (2,104), `king_sceptre` → `sceptre` (768), `king_ring` → `ring` (176), `king_eyelids` → `eyelids` | `haman_cap` → `cap` (768), `haman_ring` → `ring` (176), `haman_eyelids` → `eyelids` |
| Top of silhouette (local) | 0.3395 (diadem point) | 0.4001 (crown) | 0.3708 (cap) |
| Bones | 32 | 30 | 28 |

- One material per GLB (`es_page`, white; the app puts the scanned page on it). Attributes: POSITION NORMAL
  TEXCOORD_0 (page, Blender layer `UVMap` = layer 0) TEXCOORD_1 (face decal, layer `decal` = layer 1; the build asserts
  this order and `verify` checks it after re-import) JOINTS_0 WEIGHTS_0. No animations (verify: 0 actions).
- Character-local coordinates: root at the origin, feet on y = 0, facing +Z, 1 unit = art width. Heights are to the top
  of the silhouette including headwear (CONTRACT §2: 0.34 / 0.40 / 0.37).
- Props are joint children in glTF, so hiding a joint node hides its prop: `king/ring`, `haman/ring` (timeline `props`),
  `haman/cap` (slips in `shock`), `esther/diadem`, `king/crown`, `king/sceptre`.
- `characters.blend` holds the three rigs **at their sheet positions** with all meshes, for the Animation role
  (region ids stored in the scene property `es_regions`).

## 2. Rest pose and sheet placement

- A-pose with the **arms 55° below horizontal** (D&G used 45°): three robed figures must fit side by side on one art
  rectangle. Hands open and relaxed (palm toward the body, turned 28° backward, thumb forward), except the king's right
  hand: a fist round the sceptre, wrist cocked so the staff stands 26° off vertical.
- Sheet position: `assets/esther/design.json characters.<id>.sheetX/sheetY` when present, else the defaults
  esther −0.33, king +0.02, haman +0.34 (sheetY 0.015), written to `model/characters_layout.json`. The Set role's
  `design.json set.sheetProposal` (±0.30, boxes 0.20–0.22 wide) is **narrower than the figures**; rebuild after the
  Sheet role writes `characters.<id>`, the UVs follow automatically.
- Figure width in local x (arms, sleeves, sceptre): esther −0.119 … +0.119, king −0.213 … +0.136 (sceptre wings on
  the left), haman −0.127 … +0.127. With the defaults the gaps are esther↔king 0.018 (tight) and king↔haman 0.057.

## 3. Bones (CONTRACT §3)

Every character: `root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R
footL/R toeL/R fingersL fingersR eyelids`. Local Z of every bone points to the viewer where the bone is not along Z
(limb flexion = rotation about local X), as in D&G.

| Bone | Parent | Notes |
|---|---|---|
| `hand*` | `forearm*` | wrist → knuckles |
| `fingers*` | `hand*` | knuckles → fingertips; all four fingers, weights fade across the knuckles (one bone per hand). Rotate to close the hand; the king's right fist is curled at rest (rotate the other way to open it) |
| `jaw` | `head` | opens the mouth; chin, lower lip, the lower half of the mouth decal, the king's beard and Haman's goatee follow |
| `eyelids` | `head` | **blink**: the lid mesh is parked as a thin skin strip above the eyes. Scale the bone's **local Y** (along the bone, which points down): 1 = open (rest), **12.8 = closed**, ~6 = half. X and Z stay 1 |
| `braid1 braid2 braid3` (esther) | `head` → chain | follow the braid from behind the right ear over the right shoulder down to the waist; braid1 is parented to `head` as the contract says, so a head turn swings the braid (counter-rotate `braid1` if that is unwanted) |
| `cape1 cape2` (esther) | `chest` → chain | down the back from the shoulder line to below the waist |
| `diadem` (esther) | `head` | rigid diadem; FX `crown_sparkle` can use it |
| `crown` (king) | `head` | rigid crown |
| `sceptre` → `sceptreTip` (king) | `handR` | `sceptre` runs from the grip to the knob centre; `sceptreTip` is a leaf at the knob (FX `sceptre_beam`) |
| `ring` (king) | `handR` | signet ring on the ring finger; hide after S04 |
| `cap` (haman) | `head` | rigid cap; slips in `shock` |
| `ring` (haman) | `handL` | signet ring on the ring finger; shown from S04 |

## 4. How the meshes are made

All procedural (`pipeline/es_characters.py` + `pipeline/story_mesh.py`).

- **Heads**: the D&G base head mapped by landmarks (chin, mouth, nose, eye, brow, skull top) with per-character width,
  jaw, cheek and chin shaping; Subdivision level 1; modelled nose, brow ridge, shallow eye sockets, cheekbones, lips
  and chin. Head-to-body (skull top ÷ head height): esther 5.7, king 5.9, haman 6.2 (David 5.55). Ears for king and Haman; Esther's hair
  covers hers. Skin under hair, crown and cap is deleted.
- **Hair**: a shell over the skull whose rim follows the hairline; below eye level the side hair hangs straight down
  (not hugging the jaw); rolled inner lip; strand grooves and a centre parting (esther), curl rows (king), short
  grooves (haman). Esther's **braid** is 15 interlocking lobes tilted ±32° along a curve over the right shoulder,
  with a gathered knot at the nape, a gold tie and a tuft. King: rounded beard with curl rows (thin under the lower
  lip so the mouth reads) and a curled moustache. Haman: pointed goatee and thin moustache with upturned tips.
- **Hands**: forearm from inside the sleeve, palm, four fingers with three joints each grown out of knuckle ports,
  thumb grown from a side port (box-modelled, D&G method), Subdivision 1. Open hands relax 14°/22°/12° per joint.
- **Robes**: one shell per character, sleeves extruded from ports in the body, shoulders smoothed; flared skirt with
  folds that deepen toward the wavy hem, rolled neckline and hem. Esther: bell sleeves that sag and fold; king: wide
  sleeves; Haman: mustard front panel, hem band and cuffs (region `panels`). Long-robe skin weights blend from
  hips/spine into thighs and, below the knee, shins (left/right by x), so kneeling and walking pull the cloth.
- **Costume**: Esther — blue under-sash, gold sash with knot and two tails, crimson capelet over the shoulders that
  hangs plumb from the shoulder blades and flares with folds (solidified), two-strand bead necklace with a star
  pendant, diadem with a pointed front plate and jewel, slippers. King — scalloped gold collar with two grooves draped
  over the shoulders, gold belt with a round medallion, tall flat-topped crown (flares upward) with three raised
  bands and seven rosettes, sceptre (staff, collars, knob, two small wings), signet ring, shoes. Haman — round teal
  cap tipped back with a gold rim, mustard sash, signet ring, pointed upturned shoes.
- Garments are kept off the sleeves by `push_out_of_sleeves` (story-agnostic helper in es_characters.py).

## 5. Regions (`model/regions_characters.json`)

Face attribute `st_region` (global id) on every mesh; per character the JSON lists id, demo hex (DESIGN.md), zh/en
name, the mesh parts that carry it and its bbox on the sheet; also `faceDecal`, `blink` and `restPose`.

| esther | king | haman |
|---|---|---|
| skin, hair (incl. braid), robe, cape, sash (incl. braid tie), underSash, sandals; **anchored**: diadem → sash, necklace → sash, pendant → underSash | skin, beard (= beard, moustache and hair), robe, collar, belt, crown, shoes, sceptre (one colour, from the widest printed spot of the sceptre: knob/wings); **anchored**: crownBands → collar, ring → collar | skin, beard (= goatee, moustache, hair), robe, panels (panel, hem band, cuffs, sash), cap, shoes; **anchored**: capRim → panels, ring → panels |

**Part anchors (2026-11-14, after the first on-device run):** hands are slivers on the sheet that stay unpainted, so
they rendered paper-white. All hand faces (esther both hands, king left hand + right fist, haman both hands) now take
one UV0 texel from the same character's **face skin**: the deepest point of the face-skin region on the ID render after
masking out eyes, brows, nose and mouth (esther: mid-forehead; king and haman: right cheek above the beard line).
Esther's braid tie (region `sash` on the braid) takes the gold sash's texel; Haman's whole `beard` region (hair,
moustache, goatee) takes its own widest printed spot. Listed per character as `partAnchors` (uv + character-local
point) in `regions_characters.json`; `PART_ANCHORS` in es_characters.py.

Anchored regions are under ~2 mm on A4 and cannot be coloured: they take one constant UV deep inside the named
region (`anchorUV` in the JSON). The Sheet role can still draw them as detail lines. `ring` (king) is an extra region
not listed in DESIGN.md (the ring is gold, it borrows the collar's colour).

**ID render for the line art** (same scheme as D&G `id_2x`): `model/id_characters_2x.png` + `.json`, front
orthographic, 2000 px = art width, one colour per (piece, region), eyelids hidden, background alpha 0.

## 6. UVs

- **UV0 = page projection** at the sheet position: `u = x + sheetX + 0.5`, `v = (y + sheetY) / artHeight`
  (character-local x, y; artHeight 1.227 or design.json `artHeightUnits`), rest pose, small inward inset at
  silhouettes. Then two passes that D&G did not have:
  1. *Occlusion*: a corner whose front ray hits another part or region samples the nearest visible point of its own.
  2. *ID-render check* (`fix_uvs_by_id`): every face must sample its own character + region at least 5 px (2x render)
     inside the printed outline; faces that land elsewhere (back of the head on the face, the cape behind the robe, the
     robe behind the braid) move as a whole to the nearest interior pixel of their region.
  Proof: `model/preview_uvcheck.png` — the ID render in demo colours worn by the models; the front view reproduces the
  sheet, the 3/4 and back views keep every region's colour (hair on the back of the heads, red cape back).
- **UV1 = face decal**: square rect `faceDecal.rectLocal` (side max(1.76 hw, 0.72 head height), from just under the
  mouth to above the brows), front-projected on face, beard/goatee and moustache vertices; back and grazing vertices
  are pushed outside 0..1 (sample with clamp-to-transparent). Everything else has UV1 (−1, −1).

## 7. Faces (`docs/esther/design/faces/`)

512² RGBA PNGs drawn by `es_characters.py faces` (Pillow, 4x supersampled): almond eyes with white, two-tone iris,
pupil, two highlights, upper-lid shadow and lash line (Esther with lash flicks), brows, mouth (closed line with soft
lips for Esther, or open with teeth and tongue); Esther has a soft blush. `overview.png` shows all of them.

| esther | king | haman |
|---|---|---|
| calm (default), worried, pray (closed), brave, talk, joy (happy closed eyes, open smile) | stern (default), listen, smile, surprised, angry | smug (default), sly (side glance, one brow up), shocked, scared (sweat drop) |

`regions_characters.json` carries a suggested clip → expression map; Integration's `assets/esther/faces.json` is the
one the app uses (same names).

## 8. Checks done (2026-11-14)

- `verify`: bone sets equal CONTRACT §3 for all three (no missing / extra), 0 actions, ≤ 4 influences, all < 25k tris.
- `posetest` (`model/preview_pose.png`): elbows, finger curl, thigh + knee (robe follows), spine, head turn, jaw,
  half blink, braid and cape bend — no tearing seen at preview size.
- `uvcheck` as above; front ortho of the models equals the ID render.

## 9. Not done / rough edges

1. Not tested in Unity or on a phone (glTFast import, the app's lighting, the real scanned texture, blink by joint
   scale on device).
2. Weights are procedural; extreme poses (deep kneel in `pray`, `cower`) may need the Animation role to check the robe
   front against the shins. The finger bone folds straight fingers as one piece (contract: one bone per hand).
3. Esther's capelet shows as small red shoulder pieces from the front; most of it is behind her.
4. Sheet layout with the default positions leaves only 0.018 between Esther and the king's sceptre wings; the Sheet
   role should space the figures (widths in §2).
5. The braid is parented to `head` per the contract; head turns swing it across the chest unless counter-animated.
