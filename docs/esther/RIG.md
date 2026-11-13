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
                                                                                  #   regions_characters.json; then runs
                                                                                  #   `guards` (below) unless ES_NO_GUARDS=1
blender -b --factory-startup --python pipeline/es_characters.py -- guards        # guard1/guard2: own ID render, paint,
                                                                                  #   GLBs, appended to characters.blend
python3 pipeline/es_characters.py proof                                          # $ES_WORK/uvproof.png (perfect sheet)
blender -b --factory-startup --python pipeline/es_characters.py -- preview       # lit demo-palette renders (EEVEE)
blender -b --factory-startup --python pipeline/es_characters.py -- uvcheck       # models wearing uvproof.png via UV0
blender -b --factory-startup --python pipeline/es_characters.py -- posetest      # bend / blink / jaw test renders
blender -b --factory-startup --python pipeline/es_characters.py -- verify        # re-import GLBs: bones, skins, tris
python3 pipeline/es_characters.py compose                                        # model/preview_*.png contact sheets
```

`ES_WORK` (default `/tmp/es_work`) holds intermediate renders. `ES_MODEL=<dir>` writes every model output (blend,
GLBs, JSON, previews) to a scratch folder instead of `assets/esther/model/` — use it while iterating, because the
Animation role and `tools/story/make_sheet.py` read the real files. `ES_ONLY=esther` (comma list) builds a subset for
iteration (the regions JSON then only lists that subset; run a full build before handing off). `ES_UV_TEXTURE=<png>`
makes `uvcheck` use another texture (e.g. the Sheet role's demo colouring once it exists). Checked 2026-11-14 with
Blender 5.2.3.

## 1. What is in the GLBs (`assets/esther/model/`)

| | esther | king | haman | guard1 / guard2 |
|---|---|---|---|---|
| Triangles (target < 25k) | **23,948** | **24,692** | **23,996** | **19,796** / **18,792** |
| Skinned body (one mesh, ≤ 4 influences) | `esther_body` 22,084 | `king_body` 21,560 | `haman_body` 22,496 (incl. the plume) | `guard1_body` 18,388 / `guard2_body` 17,384 |
| Rigid props (child of one bone) | `esther_necklace` → `chest` (1,220), `esther_diadem` → `diadem` (560), `esther_eyelids` → `eyelids` (84) | `king_crown` → `crown` (2,104), `king_sceptre` → `sceptre` (768), `king_ring` → `ring` (176), `king_eyelids` → `eyelids` | `haman_cap` → `cap` (1,240, cap + rims + brooch), `haman_ring` → `ring` (176), `haman_eyelids` → `eyelids` | `guardN_cap` → `head` (1,104), `guardN_spear` → `spear` (220), `guardN_eyelids` → `eyelids` |
| Top of silhouette (local) | 0.3395 (diadem point) | 0.4001 (crown) | 0.4284 (plume; cap top 0.393) | 0.380 cap, 0.398 spear tip |
| Bones | 32 | 30 | 30 | 27 |
| Material | `es_page` | `es_page` | `es_page` | `es_guard_paint` (guard_paint.png embedded) |

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
| `cap` (haman) | `head` | rigid cap; slips in `shock`, pops in `stunned`. Head and rotation unchanged by the rework; the bone is longer (tail at the new cap top 0.393) |
| `plume1 plume2` (haman) | `cap` → chain | the feather plume: plume1 from just above the brooch (his left front of the cap) up past the cap top, plume2 from there over the arch to the drooping tip (toward his left, +x). Bend about local Z (in the front plane) for bob and whip. The plume is skinned in `haman_body` (cap → plume1 → plume2 blend), so hiding the `cap` node does **not** hide it; move the bone instead |
| `spear` (guards) | `handR` (guard1) / `handL` (guard2) | from the grip in the fist to the spear-head tip; the outer hand is a fist at rest (like the king's right hand) |
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
  bands and seven rosettes, sceptre (staff, collars, knob, two small wings), signet ring, shoes. Haman (rework
  2026-11-14, HAMAN-REWORK.md) — a pompous cartoon peacock: round pot belly and puffed chest (robe rows; the skirt
  tucks in under the belly), long hooked nose (own part `nose`, skin), thin moustache rolled into a curl on each side,
  pointed goatee, wide gold collar with pointed scallops, mustard belt across the widest part of the belly, slippers
  whose toes curl up and back, a tall teal cap (0.393) tipped back with a gold rim, a gold band and a gold brooch, and a
  tall feather plume (region `plume`) springing from the brooch and arching over to his left into a curl.
- Garments are kept off the sleeves by `push_out_of_sleeves` (story-agnostic helper in es_characters.py).

## 5. Regions (`model/regions_characters.json`)

Face attribute `st_region` (global id) on every mesh; per character the JSON lists id, demo hex (DESIGN.md), zh/en
name, the mesh parts that carry it and its bbox on the sheet; also `faceDecal`, `blink` and `restPose`.

| esther | king | haman |
|---|---|---|
| skin, hair (incl. braid), robe, cape, sash (incl. braid tie), underSash, sandals; **anchored**: diadem → sash, necklace → sash, pendant → underSash | skin, beard (= beard, moustache and hair), robe, collar, belt, crown, shoes, sceptre (one colour, from the widest printed spot of the sceptre: knob/wings); **anchored**: crownBands → collar, ring → collar | skin (incl. the nose), beard (= goatee, moustache, hair), robe, panels (panel, hem band, cuffs, belly belt), **collar** (gold, new), cap, **plume** (demo `#2FA38A`, new), shoes; **anchored**: capRim (rims, band, brooch) → panels, ring → panels |

On A4 Haman's new parts are colourable but narrower than 6 mm: plume best cell 16 px (~2.7 mm), collar 30 px (~5 mm)
(`assets/esther/sheet/checks.json`); his cap (20 px) and panels (18 px) were already below 6 mm before the rework.

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
| calm (default), worried, pray (closed), brave, talk, joy (happy closed eyes, open smile) | stern (default), listen, smile, surprised, angry | proud (default), smug, sly, shocked, scared, laugh, furious, scheming, stunned, sulky, terrified, begging |

**Haman and the guards** use bold cartoon faces (`bold_face` in es_characters.py): 0.027 ink, eyes drawn 1.15–1.35x
the lid layout, every emotion pushed (proud: half-shut eyes looking down, brows high, long curled smirk; laugh: eyes
squeezed to arcs, huge open D mouth, crow's feet, rosy cheeks; furious: V brows, bulging eyes with small pupils,
clenched teeth, red hatched cheeks, anger mark; scheming: eyes slid to the side, wicked teeth grin; stunned: dot
eyes in big whites, jaw hanging; sulky: heavy lids, pout; terrified: huge eyes, screaming O, tear streams, sweat;
begging: big wet puppy eyes, wobbly mouth, welling tears and tear streams). Haman's decal rect is 1.25x larger and
reaches 0.32 H below the mouth (`faceDecal.rectLocal` [-0.02565, 0.28805, 0.02565, 0.33935], was
[-0.0205, 0.2983, 0.0205, 0.3393]); his mouths are drawn 1.35x so they read past the nose, moustache and goatee. UV1
in haman.glb follows the new rect; the eye positions and the blink lids are unchanged. Guards: `guard1_stern.png`,
`guard2_stern.png` (file name = cast id, as the Unity loader expects). `model/preview_haman_phone.png` shows three of
Haman's faces at phone size.

`regions_characters.json` carries a suggested clip → expression map; Integration's `assets/esther/faces.json` is the
one the app uses (same names).

## 8. Checks done (2026-11-14)

- `verify`: bone sets equal CONTRACT §3 for all three (no missing / extra), 0 actions, ≤ 4 influences, all < 25k tris.
- `posetest` (`model/preview_pose.png`): elbows, finger curl, thigh + knee (robe follows), spine, head turn, jaw,
  half blink, braid and cape bend — no tearing seen at preview size.
- `uvcheck` as above; front ortho of the models equals the ID render.

**Haman rework + guards (2026-11-14):** `verify` bones equal CONTRACT §3 + HAMAN-REWORK §3 for all five (haman
+ `plume1 plume2`, guards + `spear`), ≤ 4 influences, all < 25k; Haman's existing bones keep their rest transforms
(compared node by node with the previous haman.glb; only the `cap` bone is longer). esther.glb and king.glb are
byte-identical after the rebuild. Sheet: `make_sheet.py esther` PASS (no set drawing over a figure, anchors 10/10).
Vision (`tests/vision`, 3 x 300 frames, seeds 7 / 11 / 23, the Esther print and demo sheet now in the synthetic set,
story check per story pack): 93.9 / 96.5 / 96.0 % corners right, 0 false positives, one cross-story title misread per
run (David→wrath, Angel→Esther, Esther→holy). Seeds 7 and 11 give exactly the same misreads with the pre-rework
Esther sheets, so they are title-band identification limits, not the new art (the title band and the signatures are
unchanged).

## 9. Not done / rough edges

1. Not tested in Unity or on a phone (glTFast import, the app's lighting, the real scanned texture, blink by joint
   scale on device).
2. Weights are procedural; extreme poses (deep kneel in `pray`, `cower`) may need the Animation role to check the robe
   front against the shins. The finger bone folds straight fingers as one piece (contract: one bone per hand).
3. Esther's capelet shows as small red shoulder pieces from the front; most of it is behind her.
4. Sheet layout with the default positions leaves only 0.018 between Esther and the king's sceptre wings; the Sheet
   role should space the figures (widths in §2).
5. The braid is parented to `head` per the contract; head turns swing it across the chest unless counter-animated.
6. Haman's plume (2.7 mm) and collar (5 mm) are colourable but under the 6 mm rule on A4; the plume is skinned in
   `haman_body`, so hiding `haman/cap` leaves the plume visible (move the cap bone instead).
7. Guards: not tested in Unity; the stern face is the only guard decal; the cap flutes are shallow.

## 10. Palace guards `guard1`, `guard2` (HAMAN-REWORK.md §3)

- Same humanoid skeleton as the cast (contract bones + `fingersL/R` + `eyelids`) plus `spear`; height 0.38 (cap top),
  A-pose 55°, facing +Z, feet on y = 0. guard1 holds the spear in his **right** hand (`handR`; screen left when he
  faces the viewer), guard2 in his **left** (`handL`); that hand is a fist at rest, the other hand open. Inner hand =
  the open one. Look: Persian-inspired, tall fluted cap with a gold band, lapis tunic to below the knee with gold hem
  and cuffs and a terracotta belt, sand trousers, brown boots, short bronze spear with a gold leaf head. guard1 has a
  short square curly beard and a terracotta cap; guard2 a thick drooping moustache, no beard, and a glazed-teal cap.
- **Not on the colouring sheet.** UV0 samples `assets/esther/model/guard_paint.png` (fixed demo-palette paint, made
  from the guards' own front ID render on a virtual page, `GUARD_PAGE`). Every face of a region samples one texel deep
  inside that region, so the paint never bleeds across thin bands. The GLBs carry the material `es_guard_paint` with
  this PNG embedded; bind the same PNG to UV0 if the app replaces materials. UV1 = face decal as for the cast.
- `regions_characters.json` lists them under `offSheet` (decal rect, files, blink, colours, spear hand), not under
  `characters` (that list is what the sheet prints).
- **For `pipeline/es_animate.py`:** `characters.blend` holds `guard1_rig` and `guard2_rig` (armature objects) with
  their meshes as children (`guardN_body` skinned, `guardN_cap` on `head`, `guardN_spear` on `spear`,
  `guardN_eyelids` on `eyelids`), exactly the `<id>_rig` / `<id>_*` naming the script already uses for
  esther / king / haman, so adding `"guard1", "guard2"` to its `CHARS` (and `H_OF` 0.38) is enough to open them with
  `bpy.data.objects[f"{ch}_rig"]`. The rigs stand **off the page** at x 1.10 and 1.25 (z 0) in the blend; the export
  step moves each rig to the origin anyway. Their region table is the scene property `es_regions_guards` (not
  `es_regions`). Meshes use `es_guard_paint`, not `es_page`.

