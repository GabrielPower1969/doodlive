# Gabriel: the city of light (Set + sheet role)

A tabletop stage on the colouring sheet: a sea of soft cumulus puffs (`clouds`: a low peach base sheet under 33
sculpted clumps, flat where Gabriel stands, banked up at the back and round the wall ends), the **gate of heaven** at
the back centre (`gate`: a gatehouse with an arched portal of light, a proud archivolt, two fluted portico columns
that carry a gold cornice and gable with a ball finial, the sun-disc rosette `gateGlow` with 16 rays over the arch,
five wide steps down to the clouds with newel posts at the foot, wall wings with a scalloped crest and two lit
arched windows each, two towers with a lit window, a gold cornice and an onion dome), two **floating islets**
(`islandL`, `islandR`: a faceted upside-down rock, a scalloped grass cap, a pond, a waterfall wisp that ends in a
puff of mist, a tree — a round crown on the left, a three-tier one on the right — a bush, pebbles hanging under the
rock) and low cloud puffs at the front corners (`frontClouds`). Original design, Paper & Crayon family of Esther,
Ruth and Daniel. Binding brief: `CONTRACT.md` §6; look: `DESIGN.md`.

| What | Where |
|---|---|
| Script | `pipeline/ga_heaven.py` (Blender 5.2, headless; started from `pipeline/da_babylon.py`) |
| Model | `assets/gabriel/model/heaven.glb` (+ `heaven.blend`, region materials, for inspection only) |
| Previews | `assets/gabriel/model/heaven_preview_{phone,phone_set,front,orbit,gate,island,low,stage,topdown}.png` |
| Sheet | `tools/story/sheet_gabriel.py` → `assets/gabriel/sheet/`, `print/gabriel-A4.{png,pdf}`, `print/gabriel-A4-colored.pdf` |
| Data | `assets/gabriel/design.json` (`sheet`, `lines`, `characters` slot, `set`) |
| Work files | `/tmp/gabriel_set` (`$GA_WORK`, `$STORY_WORK`): preview texture, drawings quick-look, geometry pass |

## Rebuild

```
blender -b --factory-startup --python pipeline/ga_heaven.py -- all                 # set + previews + verify (~25 s)
blender -b --factory-startup --python tools/story/sheet_gabriel.py -- geometry     # depth + normals of gabriel.glb
python3 tools/story/sheet_gabriel.py                                               # sheet + checks.json + PDFs
python3 tools/story/sheet_gabriel.py signature                                     # title band vs every other sheet
blender -b --factory-startup --python tools/story/sheet_gabriel.py -- render       # textured_*.png
```

Order after any character build: `ga_character.py` → `ga_heaven.py` → `geometry` → sheet → `render`. The set script
reads the cast's printed pixels (`model/id_characters_2x.png`) to place its drawings, and the sheet reads the
geometry pass to draw the sculpt lines; a geometry pass older than `gabriel.glb` is refused (the sheet says so and
prints the figure from the ID render alone). `ga_heaven.py -- check` builds in memory and prints the checks only.
`ga_heaven.py` prints `HEAVEN_TRIS`, `AUTOFIT`, `CLEARANCE` (measured ceilings), `LAYOUT` and `VERIFY`.

`tools/story/make_sheet.py` is not touched (Esther, Ruth and Daniel regenerate from the same file as before).

## Coordinates and nodes

Design / glTF `(x, h, z)`: art-width units, page = XZ plane at h 0, +z toward the viewer, z 0 = the art rectangle's
bottom edge. Blender builds `(x, -z, h)`. Root `heaven` has no transform. Floor x ±0.60, z −0.5875…0.21.

```
heaven
├ clouds        origin (0, 0, -0.19): base sheet (h ≤ 0.012, scalloped rim) + 33 clumps of 9 round lobes each
├ gate          origin (0, 0, -0.50): x ±0.377, z -0.5855…-0.36 (foot of the stair), top 0.4195
│ │             wall wings x ±0.11…0.29, front face z -0.50, top 0.20 (+ scallops to 0.211)
│ │             towers x ±0.29…0.37, front z -0.488, body 0.25, cornice to 0.276, dome to 0.361, ball to 0.3755
│ │             gatehouse x ±0.11, front z -0.488, wall to 0.345, cornice to 0.369 (over the columns: z -0.44),
│ │             gable peak 0.410, finial 0.4195; door: half width 0.05, sill 0.06, top 0.208
│ │             columns (±0.089, -0.464), plinth on the threshold; newel posts (±0.172, -0.372)
│ │             steps (top h / front z / half width): 0.060 / -0.444 / 0.118, 0.048 / -0.423 / 0.130,
│ │             0.036 / -0.402 / 0.142, 0.024 / -0.381 / 0.154, 0.012 / -0.360 / 0.166
│ └ gateGlow    origin = the rosette centre (0, 0.296, -0.488): a shallow lens, radius 0.031 (rays to 0.0445 are
│               part of `gate`)
├ islandL       origin (-0.45, 0.23, -0.30): rock h 0.18…0.262 (radius 0.085 x 0.068), grass to 0.28, tree to 0.418,
│               waterfall on the stage side (x -0.418), mist puffs down to 0.046, pebbles 0.13…0.175
├ islandR       origin (0.45, 0.23, -0.28): the mirror, with the three-tier tree
└ frontClouds   origin (0, 0, 0.10): 3 clumps a side at (±0.475, 0.105), (±0.495, -0.035), (±0.385, 0.150)
```

All six are mesh nodes with one material `ga_page` (UV0 = the sheet). No animation is exported; a `cloudDrift`
action (CONTRACT: allowed) was left out: the Effects role's `cloud_drift` moves the wisps, and a moving `clouds`
node would slide under Gabriel's feet.

## Ceilings (CONTRACT §6), measured on the vertices at build time

| Rule | Limit | Built |
|---|---|---|
| clouds in the centre stage (x ±0.35, z −0.30…0.21) | ≤ 0.04 | 0.036 |
| anything in the wing sweep (x ±0.55, z −0.15…0.20) | ≤ 0.04 | 0.037 |
| keep-clear stage (x ±0.30, z −0.20…0.21) | clear | 0.027 (cloud floor only) |
| round the marks (0, 0.02) and (0, 0.10), radius 0.12 | — | 0.015: feet and the kneeling knee stay in sight |
| cloud tops anywhere | ≤ 0.10 | 0.076 |
| gate | ≤ 0.42 | 0.4195 |
| triangles | ≤ 45,000 | 41,518 (clouds 22,947, gate 6,883, gateGlow 270, islets 3,949 + 3,761, frontClouds 3,708) |

How: every cloud vertex is under `allowed_h(x, z)` (0.018 round the marks, 0.037 in the centre stage and the wing
sweep, rising over 0.10 to 0.096 at the back and the sides). A clump that would be taller sags smoothly toward the
stage (each vertex scaled by the height allowed at its own place, a different share per clump so that two clumps do
not lie in one surface) instead of being cut flat.

## Clouds: how they are made

The cartoon way: overlapping round lobes (ellipsoid domes down to the floor). One template per node, 9 lobes for the
floor clump (5 light tops behind, 4 smaller peach puffs as a skirt in front) and 8 for the corner cloud (a tower of
5 with a skirt of 3). Faces wholly inside another lobe are left out. The instances are low-poly (13 x 4 per dome);
the template that is printed is drawn exactly, per pixel, as a ray against each ellipsoid (`raster_lobes`), so the
sheet shows clean arcs. A lobe's faces are named `<region>#<i>`; `merge_lobes` turns them back into one region and
prints the border between two lobes of the same colour as a detail arc. The tree crowns and the mist are made the
same way.

## UV0 = the colouring sheet

One drawing per piece, a linear view `a = A.P, b = B.P`, `u = a / scale + sheetX + 0.5`,
`v = (b / scale + sheetY) / 1.227` (numbers in design.json `set.drawings`, per piece in `set.pieces[].frontUV`).

| Drawing | View | Scale | Pieces | Regions |
|---|---|---|---|---|
| `gate` | front | 1.34 | `gate`, `gateGlow` | `gateWall`, `gateGold` (columns, cornices, gable, domes, steps, newels), `gateLight` (door, windows), `gateGlow` (rosette) |
| `islandL`, `islandR` | from the front and 0.40 above | 1.12 | the islet | `rock` (and the trunk), `grass`, `tree`, `water`, `mist` |
| `clouds` | from the front and 0.50 above | 1.45 | every floor clump (template position) | `cloud`, `cloudShade` |
| `frontClouds` | from the front and 0.35 above | 1.20 | every corner clump (template position) | `cloud`, `cloudShade` |

- A face edge-on to its drawing or facing away from it (n · D < 0.22), or hidden or half hidden behind another part
  of the drawing, takes one clean texel deep inside its own region (LESSONS L51): no mirrored print on backs and
  undersides. Faces only partly on their own region (the wall behind the stair and the columns, the rock behind the
  waterfall) are first split to edges under 0.011 (`refine_half_hidden`, +4,718 triangles), so the flat patch stays
  within a few millimetres of the silhouette in front.
- Not drawn, one named texel (`constUV` in `model/set_id_2x.json`): the cloud base sheet (`clouds:cloudShade`), the
  rosette rays (`gate:gateGold`), the pebbles under the islets (their `rock`).
- Detail lines on paper are chosen, not derived: the gate, the rock and the water print only the lines listed in
  the script (`dline`: sills, string courses, the archivolt, the door star, the rays, step edges, two short flow
  strokes), so every region keeps a clear 6 mm.

## Colouring sheet

Gabriel fills the page (CONTRACT §2: height 0.62, slot (0, 0.015), front view; printed box x ±0.487, y 0.015…0.811,
wingspan 0.973: RIG.md §9). The set drawings take what is left: the gate in the middle above his head with an islet on each side above
the wing tips, and the two cloud drawings in the bottom corners beside his legs, under the wings.

- **Auto-fit.** His outline changes with every character build, so `ga_heaven.py` reads the real printed pixels:
  the gate and the islets slide down until 20 px (3.4 mm) above the figure, then up by 45 % of the height that is
  left (2026-11-14 build: gate y 0.768…1.081, islets 0.80…1.17). `LAYOUT` fails the build if any set pixel is within 15 px of the figure, a drawing leaves the art
  rectangle, or two drawings' boxes are closer than 0.012.
- **Figure line art** (`sheet_gabriel.py`, on a patched copy of the cast inputs; `model/` is not touched):
  pieces too thin to colour become their centre line (the feather shafts: hairlines, 1 px in the 2x raster; ear
  rims); lines that follow the sculpt come from the geometry pass (depth + normals of `gabriel.glb`, pixel-exact with
  the ID render, IoU 0.99999): where one part of a region covers another, folds sharper than 40°, grooves (hair
  locks) and broad soft grooves (the centre seam and the chest of the moulded cuirass). They are painted under
  `<region>~lines` pseudo ids and go through make_sheet's own detail mechanism (trimmed at region borders, dropped
  where too dense, counted in `checks.json`). Wings are left to their feather pieces.
- **Face guide.** The default decal (`gabriel_smile.png`) is printed at the decal's own place as a guide: its dark
  strokes (brows, lash lines, pupils, mouth), laid over the finished pages because make_sheet prints no face ink.
  The scan's line erase removes it and the 3D face is the decal (LESSONS L33, as David & Goliath).
- **Title band.** 大天使加百列 / Gabriel the Archangel, six boxes like David & Goliath and Daniel: box 80 / gap 50 /
  cy 102 (the most distinct of a grid of candidates that keep the pinyin 6 mm from the top edge). `signature`:
  most similar other sheet `daniel-A4` NCC 0.348 (a true match is about 0.9; the closest pair among the other sheets
  is esther / exodus at 0.729). Checked on a copy: `sheet_signatures.json` and `assets/stories.json` are
  Integration's.
- **Coloured PDF.** `print/gabriel-A4-colored.pdf` = `demo-sheet.png` at 150 dpi, 1240 x 1754 px = 209.97 x 297.01
  mm, the same page geometry as `print/gabriel-A4.pdf`.

### Checks (`assets/gabriel/sheet/checks.json`)

`SHEET PASS`: no set pixel over the figure, no sliver, no ink within 6 px of the art rectangle's edge, ink ≥ 6 mm
from every page edge (39 px at the top), 6 / 6 constant and anchor texels on clean colour of the right region.

Two size measures, both in the file:
- `regionInscribedMm(outline only, detail lines ignored)`: the largest circle inside each colour region's outline.
  Every **set** region is ≥ 6 mm (smallest: islet grass 6.4, rock 6.6, rosette 7.0).
- `regionsBelow6mm(best cell)`: make_sheet's own measure, the largest clear circle between ALL lines. No set region
  is on that list.

The figure's numbers come from the Character role's ID render (same file, 2026-11-14 build):
- outline only: wings 20.9 / 23.6 mm, sash 11.2, cuirass 10.4, skin 8.5, greaves 8.4, skirt 6.9, pauldrons 6.4,
  collar 6.1, leggings 6.1, hair 6.1; **under 6 mm: vambraces 5.9, belt 5.7, sleeves 5.0, hilt 2.7, scabbard 2.7**
  (the sword is a thin thing at his hip) and the gem 1.7 (anchored by the Character role to its own printed spot).
- between all lines: the widest feather cell is 4.1 mm (304 feathers a wing), so no single feather is a 6 mm
  cell; a child
  colours a wing region across its feather lines.

## Demo colours

DESIGN.md table: clouds `#FFF6E2` / `#F7DDB0`, gate wall `#F6EEDC`, gold `#EED48E`, rosette `#F2A43A`, islet rock
`#C9A47A`, trees `#7DAA55`; plus: portal and windows `#F8C56B`, grass `#A9CF72`, water `#BFE6F5`, mist `#FFF6E2`.

## Previews

`heaven_preview_*.png` use the demo texture and a golden-hour light (warm key from behind the gate, soft fill, a
glow at the rosette); `phone` and `stage` have a stand-in figure of Gabriel's size (not shipped). The sheet's
`textured_*.png` are the real `gabriel.glb` and the set wearing the demo colouring with the lines erased
(`cast`, `front`, `face`, `herald`, `phone`, `phone_play`, `top`).

## Known rough points

- The contract's wing sweep leaves the front corners only 0.04 of height inside x ±0.55, so `frontClouds` are low
  wide puffs (0.037), not towers; the tall banks are at the back (0.076).
- The scale is the hero's: Gabriel (0.62) is taller than the gate (0.42). The gate reads as the city behind him.
- The printed face is 10 mm wide; at 150 dpi the guide is small (eyes about 1.5 mm).
- Five cast regions (and the anchored gem) are under 6 mm at outline level (list above): that is the figure's geometry, not something the
  sheet tool can widen; RIG.md §9.7 names the Character script's `ANCHORS` as the place to anchor them.
- `textured_*.png` show the face without its decal (the decal is on UV1; these renders only test UV0).
- A flattened clump shows faint polygon steps at its rim from very low angles (13-sided domes).
