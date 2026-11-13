# David & Goliath — art bible (Design role), redraw 2026-10-27

Owner: Design. Binding contract: [CONTRACT.md](CONTRACT.md) §11 (redraw) and §12 (desert boost, 2026-10-27); later sections win.
House style for UI: [../DESIGN-DIRECTION.md](../DESIGN-DIRECTION.md) (Paper & Crayon).

**Why a redraw.** The owner rejected the first build: "最好不要吹气模型，要有沙漠，要有骨骼动画建模，重新画一下". The models were
joined ellipsoids, capsules and balls. He chose (1) a **realistic-proportion cartoon** (Pixar-like) and (2) a **desert on the
paper** that rises in AR and wears the child's colours.

**Desert boost (§12).** The owner looked at build v2 and asked: "做沙漠加强：纸面铺沙色地面、沙丘做大做高、营地放大、涂色纸上沙丘改成看得懂的样子".
The desert is now drawn and built like the characters: upright, side-view drawings, front-projected (§6 below).

**Source of truth for numbers:** `assets/david-goliath/design.json` (version 3). Every number and picture here comes from one
script, so they always agree:

```
python3 docs/david-goliath/design/make_design.py           # full run (needs shapely, numpy, scipy, Pillow, Google Chrome, Blender)
python3 docs/david-goliath/design/make_design.py --quick   # skip expressions, face decals and the scan simulation
```

It writes `design.json` and every picture below, runs the checks in §8, and exits non-zero if one fails. Do not hand-edit
`design.json`.

| Picture | File |
|---|---|
| David: front line art, front colour, side, back | `design/turnaround-david.png` |
| Goliath: front line art, front colour, side, back | `design/turnaround-goliath.png` |
| Scale line-up with head rulers | `design/lineup-scale.png` |
| Expressions (6 per character, modelled face + decals) | `design/expressions.png` |
| Face decals, one per expression, transparent 512² | `design/faces/<char>_<expr>.png` (+ `.svg`) |
| Palette (characters + desert) | `design/palette.png` |
| A4 sheet: line art / demo colours / annotated (zones, stage, heights) | `design/sheet-mock-lineart.png`, `sheet-mock-demo-colour.png`, `sheet-layout-annotated.png` |
| The desert seen from a phone: Blender render of the real character GLBs (rest pose) + the §12 desert volumes, UV rules applied | `design/ar-mock-desert.png` (phone view of DGPreview), `ar-mock-desert-right.png` (phone moved right), `ar-mock-desert-low.png` (low) |
| Ground: mask (0 sand / 128 scan-or-sand / 255 hole) and the sand it gives on the demo page | `design/ground-mask.png`, `design/ground-sand-demo.png` (half size) |
| AR mock renderer (Blender, run by the script; work files in `$DG_WORK`) | `design/ar_mock_blender.py` |
| What the models wear after the app's line-erase | `design/scan-sim-texture.png` |

The sheet PNGs are mocks. The printable sheet is made by the Sheet role from the real rest-pose models plus the desert polygons.

## 1. Look

- **Realistic-proportion cartoon.** Believable anatomy and head-to-body ratios. Defined planes: jaw line, cheekbones, brow ridge,
  nose, collarbones, elbows, knees, ankles. Real hands (four fingers + thumb), real feet in sandals or laced boots, clothing with
  thickness, hems and a few folds. No visible primitive (ball, capsule, tube of constant width), no mitten hands.
- **Built the way the drawings are built.** Every outline in the turnarounds is a smooth spline through anatomical landmarks, and
  every limb is a tapered profile (deltoid → biceps → elbow → forearm → wrist; thigh → knee → calf → ankle). The Blender role should
  read the turnarounds as a sculpting guide, not as flat shapes to extrude.
- **One pencil ink colour** `#262019` on white. Sheet line weights at 150 dpi: outlines 4.5 px, interior detail 3 px, printed face
  strokes 2.2 px. All of them are thin enough for the app's line-erase (radius 4 texels), so the models wear colour only
  (`scan-sim-texture.png`: 61 of 77,479 ink texels survive, 0.1 %).
- **Every colourable region is closed.** Decorative lines (folds, fingers, scales, ripples) are trimmed to stay 4.5 px inside their
  region, so they never split it. The script checks this.
- **Colours a child picks survive the scan.** A pixel is ink when `max(rgb) < 175` and `max − min < 45` (`web/vision.js
  eraseLines`). Every demo colour passes. Dark grey or black crayon is erased like ink (LESSONS L8).

## 2. The characters

Story source: 1 Samuel 17. The verses are cited **from memory, not re-checked against a printed text this session** `[D]`; the
Story role owns wording.

### David (`david`) — a shepherd youth, brave and kind

- About 14, slim, **5.55 heads** tall (0.30 to the top of his hair). Ruddy, curly auburn hair (16:12, 17:42).
- Knee-length blue tunic with short sleeves, rolled hems and a few folds; red sash knotted at his left hip; shepherd's bag on a strap
  from his right shoulder (17:40); leather sandals. Sling in his **right** fist (viewer's left), stone in the pouch (17:40).
- Why 5.55 and not 6 heads: he is 51 mm tall on paper. At 6 heads his face is 8 mm and stops reading on a phone. Pixar teenagers are
  5–5.5 heads. `[D: design judgement]`
- Still left out: the staff (17:40). There is no bone for it and it would sit between the two figures.

### Goliath (`goliath`) — a giant warrior, scary by size, not by gore

- **7.39 heads**, 0.80 to the top of the crest (2.7× David; "six cubits and a span", 17:4). Massive shoulders and chest, a V-shaped
  torso, thick arms.
- Bronze helmet with a rim band, neck guard and a **transverse** red crest (wide from the front, so it is a colourable region); no
  face guard (17:5). Scale armour in rows to the upper thigh with short scale sleeves (17:5). Wide belt with a bronze plate. Purple
  pleated kilt. Leather bracers. Bronze greaves from below the knee to the ankle (17:6). Laced boots. Spear with a leaf-shaped iron
  head, a socket collar and a bronze butt spike, upright in his **right** fist (17:7). Round bronze shield on his left fist.
- Heavy brow ridge, broad nose, square full beard and moustache. No teeth, no scars, no blood. The defeat stays child-safe (stone to
  the forehead, wobble, fall, dizzy stars; no beheading shown).
- Simplified: in 17:7 a shield-bearer carries the shield, and the javelin of 17:6 is left out (one weapon reads better).

## 3. Proportions (art-width units, character-local; sheet x = local + `sheetX`)

| | David | Goliath |
|---|---|---|
| Total height | 0.300 (hair) | 0.800 (crest); helmet dome 0.768 |
| Skull top / chin / head height | 0.294 / 0.241 / 0.053 | 0.746 / 0.645 / 0.101 |
| Heads tall | 5.55 | 7.39 |
| Shoulder joint (x, y) | (±0.031, 0.220) | (±0.092, 0.603) |
| Upper arm / forearm / hand | 0.053 / 0.043 / 0.031 | 0.138 / 0.112 / 0.082 |
| Chest / waist y | 0.205 / 0.178 | 0.540 / 0.452 |
| Hip joint, knee, ankle (x, y) | (±0.016, 0.153), (±0.0185, 0.083), (±0.018, 0.016) | (±0.050, 0.380), (±0.054, 0.209), (±0.052, 0.040) |
| Foot length (+Z) | 0.044 | 0.112 |
| Eyes / brows / nose base / mouth (jaw seam) y | 0.267 / 0.272 / 0.256 / 0.2497 | 0.699 / 0.707 / 0.683 / 0.667 |
| Clothing | tunic hem 0.096, sash 0.171–0.182 | armour hem 0.362, belt 0.438–0.463, kilt hem 0.262 |
| Sheet x / y offset | **−0.350** / 0.015 | **+0.130** / 0.015 |
| Rest pose | arms 45° below horizontal; right fist on the sling, left hand open | arms 45°; right fist on the spear, left fist behind the shield |

Side depths: `design.json characters.<id>.depth`. Bones (head, tail, parent; local and at the sheet position) are in `bonesLocal` and
`bonesSheet`: all CONTRACT §3 names, the props' bones, and the six new finger bones `fingers*`, `fingerTips*`, `thumb*` (§11.6).

## 4. Colourable regions and demo palette

**David:** `skin #EDB98E` (face, ears, neck, arms, hands, legs, toes), `hair #B9562A`, `tunic #4BA3E3`, `belt #E8553D` (sash + knot),
`bag #C68B4E` (bag + strap), `sandals #A8693A`, `sling #D9A066` (cords + pouch), `stone #B9B4AA`.

**Goliath:** `skin #D99A6C`, `beard #6E4326` (beard + moustache), `helmet #E3B04B` (dome, rim, neck guard), `crest #E8553D`,
`armour #C8873A` (coat + scale sleeves), `belt #9C5B2E`, `bracers #B5733C` (new), `kilt #8A6FD1`, `greaves #E3B04B`, `feet #A8693A`
(boots), `spearShaft #B07A45`, `spearHead #BFC7CF` (head + butt spike), `shieldRim #C8873A`, `shield #E3B04B`, `shieldBoss #FFC93C`.

**Desert:** `sand #F3D58E` (dune backs), `duneShade #E3A857` (slip faces), `rock #B99B7A`, `hillIsrael #D9B77A`, `hillPhil #CFA36B`,
`tentIsrael #F4EEDC`, `tentPhil #E07B5A`, `flagIsrael #4B7BE5`, `flagPhil #C0392B`, `water #6EC1E4`, `pebbles #C9C3B6`, `bush #9BBF5A`.

Region bounding boxes on the sheet: `characters.<id>.regions.<region>.bboxSheet`. Hidden surfaces take the colour of what is in front
of them in the front projection (thighs under the tunic and kilt, Goliath's left fist behind the shield, backs and sides): the same
accepted rule as before.

## 5. Faces: modelled planes, decal eyes and mouths

The head is sculpted: brow ridge, shallow eye sockets, nose and nostrils, cheekbones, lips volume, chin, jaw, ears; Goliath's beard is
a modelled volume. Eyes, brows and mouth are **UV1 decals** (`design/faces/<char>_<expr>.png`, same front projection as UV0) inside
`faceDecals.<id>.rectLocal`: David `[-0.0175, 0.2425, 0.0175, 0.2775]`, Goliath `[-0.034, 0.655, 0.034, 0.723]`. Why decals and not
modelled eyeballs: the expression system (`clipExpression`) keeps working unchanged, eyelids and brows can change shape per clip
without blend shapes, and the app's line-erase would wipe printed eyes anyway (`scan-sim-texture.png`). The printed face on the sheet
is only for the child to colour around.

| David | Goliath |
|---|---|
| brave (default), kind, talk, pray, victory, wow | grumpy (default), taunt, laugh, roar, dizzy, down |

`clipExpression` is unchanged (David: idle/walk/kneel_pick/sling_windup/run → brave, talk → talk, sling_release → wow,
victory → victory, pray → pray; Goliath: idle/walk/talk → grumpy, taunt, laugh, roar, charge → roar, hit_react/fall → dizzy,
down → down).

## 6. The desert on the paper (§12, replaces the plan-view desert of §11.9)

**Idea.** The sheet shows the Valley of Elah **from the front, like the characters**: behind David two big sand dunes, at the top
a horizon with two camp hills (Israel left, Philistines right) with A-frame tents and banners on top, a far dune in the valley
between them, a few rocks, a shrub, and the brook with five stones at David's feet. A child sees "sand hills with tents" at once.
In AR every piece **stands up as a 3D volume behind the actors** and the whole page turns to sand.

**Why front view (and why the v2 plan view failed).** v2 drew dunes from above (horseshoe blobs) next to upright characters; on the
phone they rose 12 mm and the page stayed white. A side-view drawing is what a child recognises, and front projection
(`u = x / scale + sheetX + 0.5`, `v = (y / scale + sheetY) / 1.227`) puts the colour of every drawn spot on the 3D surface behind it,
exactly as for the characters (they are the case scale = 1). Two scales:

- **Far panorama, scale 2.5** (`duneFar`, `hillIsrael`, `hillPhil`, `tent*`, `banner*`): drawn small at the top of the art rect
  (sheet x −0.236…0.236, ys 1.000…1.196), built 2.5× bigger across the back of the page (x −0.59…0.59, z −0.98…−1.475, up to 0.49
  tall). It must be big in 3D (tents at 0.37–0.48) to show above Goliath's shoulders, and there is only a 0.2-tall strip of free
  paper above his spear; scale 2.5 is the smallest that does both.
- **Midground, scale 1** (`dune1..3`, rocks, `shrubL`): each stands on its own drawing (`sheetY` = its front foot), so its 3D front
  is the drawing at real size.

The brook and the five stones stay on the ground (top-down) at the front.

**Layout and heights** (`sheet-layout-annotated.png`; numbers in `design.json desert.pieces`, CONTRACT §12):

| Piece | Drawn (sheet x / ys) | 3D footprint x / z | Height |
|---|---|---|---|
| `hillIsrael` + `tentIsrael1..3` + `bannerIsrael` | −0.236…−0.007 / 1.000…1.170 | −0.59…−0.02 / −0.98…−1.475 | hill 0.306, tents to 0.40, banner 0.43 |
| `hillPhil` + `tentPhil1..3` + `bannerPhil` | −0.007…0.236 / 1.000…1.196 | −0.02…0.59 / −0.98…−1.475 | hill 0.382, tents to 0.48, banner 0.49 |
| `duneFar` | −0.096…0.076 / 1.000…1.076 | −0.24…0.19 / −1.38…−1.475 | 0.19 |
| `dune1`, `dune2` (behind David) | −0.47…−0.23 / 0.37…0.54, 0.60…0.85 | same x / −0.37…−0.60, −0.60…−0.92 | 0.17, 0.25 |
| `dune3` (Philistine side) | 0.225…0.47 / 0.72…0.96 | same x / −0.72…−0.98 | 0.24 |
| `rockL1`, `rockL2`, `shrubL` | top-left corner, ys 0.935…1.033 | z −0.935…−1.00 | 0.098, 0.036, 0.047 |
| `rockM1`, `rockM2` (valley) | −0.105…0.045 / 0.74…0.81 | z −0.74…−0.80 | 0.072, 0.038 |
| `rockFR1`, `rockFR2` (right of Goliath's feet) | 0.405…0.47 / 0.06…0.19 | z −0.06…−0.21 | 0.050, 0.033 |
| `brook`, `fiveStones` (ground) | −0.469…−0.377 / −0.190…−0.012 | z +0.012…+0.190 | film 0.004, stones 0.008 |

One wind (from +X) for the valley: every slip face (`duneShade`) faces −X. From the phone you see the gentle sand-coloured backs of
David's dunes and the shaded slip face of `dune3` (the valley wall on the right).

**Sand ground.** In AR the paper becomes sand: a ground layer over the whole page shows a warm sand with fine wind ripples wherever
the scan is unpainted, keeps the child's colour where the child painted the ground, turns the flat copies of the characters and
the scenery to sand (their 3D stands up instead), and leaves a hole over the brook so the real painted paper shows under the water
film. Numbers: CONTRACT §12.4; picture: `ground-sand-demo.png`.

## 7. A4 sheet

Same geometry as the angel sheet (art rect `[120, 283, 1000, 1227]`, four 64 px markers, 田字格 title). Figure rects (px): David
`[150, 1191, 243, 305]`, Goliath `[434, 540, 655, 956]`. **All ink except the markers is ≥ 6 mm from every page edge:** the title moves
down (`title.cy` 84 → 100, pinyin ≈ 36 px from the top), the footer rect is `[300, 1604, 820, 110]`, the brook ends 51.8 px (8.8 mm)
above the bottom edge (was 1 mm). The four markers stay where the template puts them (30 px = 5.1 mm from the side edges).
What to print, in order: `design.json desert.print` (shapes + decor lines). Page coordinates: `X = 120 + (x + 0.5)·1000`,
`Y = 1510 − ys·1000`.

## 8. Checks (run by the script; last run 2026-10-27, PASS)

| Check | Rule | Result |
|---|---|---|
| Fit inside the art rect | margin ≥ 0.030 | David 0.0303, Goliath 0.0310 ✔ |
| David ↔ Goliath | distance ≥ 0.040 | 0.0575 ✔ |
| No slivers | every colourable piece has an inscribed circle ≥ 6 px | ✔ 0. Smallest desert cells: stones 10.9 px, tent doors 11.3 px, tents 11.7 px |
| Decorative lines never split a region | trimmed 4.5 px inside | ✔ 0 |
| Palette survives line-erase | not `max < 175 && chroma < 45` | ✔ all 36 colours (new `tentDoor`) |
| Desert drawings | ≥ 0.030 from the characters, ≥ 0.020 inside the art rect (brook excepted), off the markers; drawings with different UV mappings ≥ 0.012 apart | ✔ 25 pieces |
| Desert 3D | footprints on the paper; nothing > 0.010 in either part of the stage band; anything reaching z > −0.30 ≤ 0.06; height caps | ✔ |
| Page edges | desert ink ≥ 35.4 px (6 mm) | left/right 147.8, top 313.7, bottom 51.8 px ✔ |
| Stones | inside the brook | ✔ |
| Ink left on the model after line-erase | measured | see `checks.scanSim` |

## 9. Notes for each role

- **Blender (characters):** unchanged (turnarounds, `bonesSheet`, ≤ 20k triangles).
- **Desert:** rebuild from `design.json desert.pieces` (version 3): front pieces from `silhouette3D` + `depthZ` + `depthProfile`, tents
  and banners from their blocks, front UVs with `frontUV`; ≤ 20,000 triangles; node names = ids (`rockL2`, `rockM2` kept; `dune3`,
  `duneFar` new). The stage band is now `stageBand.polygonsSheet` (two parts).
- **Sheet:** print `desert.print` in order (shapes + decor lines), regions get `tentDoor` from the palette; title `cy` 100; footer rect.
- **Animation:** `kneel_pick` stones moved (CONTRACT §12.5).
- **Integration:** the ground layer and mask (§12.4), `_BaseColor` sand on the desert material, the new reference image.
- **QA:** read `polygonsSheet` (all parts).

## 10. Weakest points (what I am least sure about, and how to check)

1. **The Philistine camp is half hidden by Goliath from the default phone view** `[D, from ar-mock-desert.png]`. With Goliath at
   (0.22, z −0.25), `tentPhil1` and `bannerPhil` show left of his head, `tentPhil2` shows its top half over his shoulder, `tentPhil3`
   is behind his head (it shows when the phone moves right, `ar-mock-desert-right.png`, and after he falls). The mock uses the rest
   pose with the arms spread, so the animated idle hides a little less. Check: DGPreview `phone_*.png` after the Desert rebuild.
2. **The panorama is small on paper** `[A, measured]`: tents 44 px (7.5 mm) wide, doors 18 px (3 mm), banner cloths 40 × 26 px. Big enough
   to colour with a crayon (inscribed circles 11–12 px) but fiddly for a 5-year-old. Unpainted pieces fall back to sand, so it still
   looks right if the child skips them.
3. **The hills can read as sand castles** `[D]`: flat plateau with a row of pointed tents on top. A rounder plateau or a second, lower
   ridge in front would soften it; it costs drawing space at the top of the sheet.
4. **Front projection smears along depth** `[D]`: the top and the +X/−X sides of every volume take the colour of the drawn spot in
   front of them. For one-colour regions (sand, hill, rock) this is invisible; the dune slip-face boundary shows as a straight
   band running back along each dune.
5. **The mock is not the app** `[D]`: rest-pose GLBs, no face decals, ground baked from the demo page, Blender lighting. Colour on a
   real scan, the ground shader on the phone and the frame rate are not verified.

## 中文速览

- **为什么重画：** 旧模型是椭球、胶囊拼起来的「吹气玩具」。这次改成**写实比例卡通**（像皮克斯）：大卫 5.55 头身（少年），歌利亚 7.39 头身（巨人武士），有下颌线、颧骨、眉骨、锁骨、肘、膝、踝，**四指加拇指的真手**，有厚度和褶的衣服；歌利亚有鳞甲、护胫、带颈护和横向盔缨的铜盔、圆盾、长枪。
- **建模方法（合同 §11）：** 每个身体一个连续的箱体建模笼 + 细分（导出前应用），道具单独刚体；每个角色 ≤ 2 万三角面，沙漠 ≤ 1.5 万。骨骼名不变，**新增手指骨**（fingers / fingerTips / thumb，左右各一套）。手臂静止姿势改为向下 45°。
- **脸：** 鼻子、耳朵、眉骨、颧骨、嘴唇体积建模；眼睛、眉毛、嘴仍是 UV1 表情贴花（12 张新图），所以每个动作对应表情的机制不变。
- **沙漠加强（合同 §12）：** 涂色纸上的沙漠改成和人物一样的**正面侧视图**：大卫身后两座大沙丘，纸最上方一条地平线——左边以色列山岗、右边非利士山岗，山顶上有能看出门的三角帐篷和旗子，中间远处一座沙丘，再加几块岩石、一丛灌木，大卫脚边一条小溪和五块石子。小孩一眼就认得「沙丘」「帐篷」。AR 里这些全部**竖起来、立在演员身后**：远景山岗最高约 0.38、帐篷到 0.48、旗子到 0.49（v2 才 0.07），沙丘 0.17–0.25。颜色用正面投影，和人物同一个公式，涂哪儿就在立体的哪儿。
- **纸面变沙地：** 整张纸在 AR 里铺一层沙色地面（细风纹 + 大块明暗），孩子涂过色的地面保留颜色，人物和景物的平面原稿变成沙子（它们已经立起来了），小溪那块挖空，露出真纸上孩子涂的水。
- **打印安全：** 除四个定位方块外，所有墨线离纸边 ≥ 6 毫米（小溪底边 8.8 毫米，原来只有 1 毫米）；标题下移。
- **最没把握的三点：** ① 默认手机视角下，非利士营地有一半被歌利亚挡住（两顶帐篷和红旗看得见，第三顶在他头后）；② 远景画得小，帐篷 7.5 毫米宽、门 3 毫米，5 岁孩子涂起来有点费劲；③ 平顶山岗加一排尖帐篷，可能有点像「沙堡」。
