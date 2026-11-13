# David & Goliath: the paper desert (Desert role)

The 3D desert stands up out of the colouring sheet. Across the back are two sand hills, each with a camp: Israel on the
left (three tents and a blue banner) and the Philistines on the right (three tents and a red banner). A far dune closes
the valley between the hills. Two tall dunes stand behind David and one behind Goliath. There are sandstone rocks in
the valley and under Goliath's shield, a dry shrub, and in front of David the brook of the Valley of Elah with the five
smooth stones. The binding brief is `CONTRACT.md` §12 (desert boost), which supersedes §11.9. This file covers how the
set is built and what the other roles get.

| What | Where |
|---|---|
| Script | `pipeline/dg_desert.py` (Blender, headless) |
| Model | `assets/david-goliath/model/desert.glb` |
| As-built metadata | `assets/david-goliath/model/desert_lines.json` |
| Previews | `assets/david-goliath/model/desert_preview_*.png` |
| UV-space ID render (work file) | `$DG_WORK/desert_id.png` + `desert_id.json` |
| Verify report (work file) | `$DG_WORK/desert_verify.json` |

## Commands

Run from the repo root. `$DG_WORK` defaults to `/tmp/dg_work`.

```
blender -b --factory-startup --python pipeline/dg_desert.py -- all       # build + verify + preview
blender -b --factory-startup --python pipeline/dg_desert.py -- build     # desert.glb, desert_lines.json, desert_id.png
blender -b --factory-startup --python pipeline/dg_desert.py -- verify    # re-import desert.glb and check it
blender -b --factory-startup --python pipeline/dg_desert.py -- preview   # phone-view renders with the animated characters
```

`DG_DESERT_CLOSEUPS=1` adds close-ups of the camps, dunes and rocks to `$DG_WORK`. These are for judging detail and
are not shipped. The build is deterministic: random choices are seeded by piece id. A full `all` run takes about 11 s.

## Source of truth

Every piece comes from `assets/david-goliath/design.json` → `desert.pieces[]` (version 3, Design role):
`silhouette3D` (the front view), `depthZ` (front / crestFrom / crestTo / back), `frontUV`, `geomSheet` (the printed
drawing), `parts3D` (`duneShade`, `tentDoor`), `tent`, `banner`, `stonesSheet`. The Sheet role prints `desert.print`
from the same file, so the print and the 3D cannot drift. To move or reshape a piece, change `make_design.py`
(Design), then rerun the Sheet tool and this script. **Never hand-edit the GLB.**

Coordinates: a piece stands on the page at glTF `(x, h, z)`, with `z = −d` and d the sheet height above the art rect's
bottom edge. Blender builds directly in `(X, Y, Z) = (x, d, h)`, and `export_yup` converts.

## How each kind is built

All front pieces (§12.1) are height fields `h(x, d) = top(x) · p(d)`, where `top(x)` is the upper envelope of
`silhouette3D` and `p(d)` is the §12.1 depth profile. Columns are spaced by arc length along the silhouette top, and
every top vertex of the silhouette is kept, so **the front orthographic silhouette of the mesh equals
`silhouette3D`**. Verify measures this; the error is ≤ 0.0003 for everything except the shrub (0.006). Rows follow
the front foot, the crest band and the hidden back slope. Edges with zero height sink 0.002 under the page.

| Kind | Pieces | Method |
|---|---|---|
| hill | `hillIsrael`, `hillPhil` | Height field, 0.018 column spacing, 24 rows on the front slope. The front foot is rounded at the ends and meanders (up to 0.10 deeper), so the front reads as spurs and hollows rather than a straight wall. The crest line wobbles ±0.025. There are long, low wind ripples (wavelength 0.062, depth up to 0.007, crests across the slope) on the front slope. Smooth-shaded. |
| dune | `dune1`, `dune2`, `dune3`, `duneFar` | Same height field, 0.011 column spacing (0.014 for `duneFar`). The steep slip face is on −X (wind from +X), as drawn. The brink column is marked sharp, so the slip face meets the windward back at a crisp edge. Midground dunes have ripples (wavelength 0.044, depth up to 0.006) that fade at the foot and the crest. The front foot is rounded and meanders. |
| rock | `rockL1/2`, `rockM1/2`, `rockFR1/2` | Height field with the §12.1 rock profile `p = sqrt(min(d − front, back − d) / 0.012)`. The front foot is jittered per column, and the flat top tilts down 10 % toward the back, so the highest edge is the front brink. Flat-shaded sandstone facets, about 100–200 triangles each. |
| shrub | `shrubL` | Height field from the drawn bush outline (dome profile), interior crumpled, flat-shaded. |
| tent | `tentIsrael1..3`, `tentPhil1..3` | A-frame tent built from its gable polygon (= `silhouette3D`), facing +Z toward the viewer. It is extruded back from `zGable` to `zBack`, and the ridge sags 0.006 at mid-depth. A triangular doorway (`parts3D.tentDoor`) is cut into the gable and recessed 0.012. The skirt goes down to 0.006 below the lowest hill-top point under the tent, so no gap shows. Flat-shaded, 46 triangles. |
| banner | `bannerIsrael`, `bannerPhil` | A hexagonal pole (Ø 0.006, 0.140 tall, 0.006 knob) stands on the hill at `banner.poleBase3D` and sinks 0.010 into it. The cloth is the drawn swallow-tail outline in the XY plane, triangulated with interior points and two-sided. It is skinned to a 3-bone armature (`<id>_bPole`, `<id>_bCloth1`, `<id>_bCloth2`) and carries a looping glTF animation `<id>Wave` (2 s, 24 fps, frame 1 = frame 49) that swings the cloth about the vertical. |
| water | `brook` | A flat film at 0.004 over the printed brook (§12.5: x −0.469…−0.377, z +0.012…+0.190), material `dg_water`, no UV. The child node `brookBank` is a low rounded lip, up to 0.0052 high, on both long banks. |
| stones | `fiveStones` → `stone1..5` | Smooth pebbles about 0.0136 × 0.0112 × 0.008 at `stonesSheet` (§12.5). Each is a separate node, so `kneel_pick` can hide one. |

## GLB contract (`desert.glb`)

```
desert                         (root, page origin, no transform)
├ duneFar hillIsrael hillPhil dune1 dune2 dune3 rockL1 rockL2 rockM1 rockM2 rockFR1 rockFR2 shrubL
├ tentIsrael1..3 tentPhil1..3
├ bannerIsrael                 (armature) → bannerIsrael_pole, bannerIsrael_cloth (skinned)
├ bannerPhil                   (armature) → bannerPhil_pole, bannerPhil_cloth (skinned)
├ brook                        (water film, material dg_water) → brookBank
└ fiveStones                   → stone1..stone5
```

- Units and axes are the same as the characters' (art-width units, glTF Y up, +Z toward the viewer). The root is not
  scaled.
- Materials:
  - `dg_page` on everything except the water film. Integration binds the scanned page with DGPaperLit (`_UseMask`
    off), `_BaseColor` = sand `#F3D58E` and `_BaseAmt` 1 (§12.4), so unpainted pieces come out sand, not white.
  - `dg_water` on `brook` only: transparent (alpha 0.42, BLEND), no texture.
- Animations: `bannerIsraelWave`, `bannerPhilWave`. Nothing else moves.
- Triangles: **19,541 / 20,000**. By group: hills 9.1k, dunes 7.1k, rocks 0.9k, brook 0.7k, banners 0.6k, stones 0.5k,
  tents 0.3k, shrub 0.3k. Per mesh: `desert_lines.json → tris`.

## UV0

These rules follow §12.1. Blender writes v bottom-up; the glTF exporter flips it, as it does for the characters.

| Piece(s) | UV0 |
|---|---|
| hills, dunes, rocks, shrub, tents, banner cloths | **Front projection** `u = x / scale + sheetX + 0.5`, `v = (h / scale + sheetY) / 1.227` (`frontUV`). The result is then pulled `INSET` = 0.004 (sheet units) inside the piece's printed drawing (`geomSheet`), so the erased ink line is never sampled. Verify checks that 100 % of UVs fall inside their drawing; 99 % are within 0.017 of the plain formula. |
| tent doorway recess | Front projection into the printed door triangle (`tentDoor`, inset). The rest of the tent stays out of the door drawing, so a dark door lands only in the recess. |
| hill surface just in front of a tent | The hill's top strip would project into the tent drawing above it (tent colour smeared onto the hill). Those vertices sample the hill just below that tent instead (`uv_hill`). |
| banner pole | Constant: Goliath's printed spear shaft (sheet x −0.160, ys 0.50) → `(0.340, 0.4075)`, which is wood. |
| `stone1..5` | Constant `desert.stoneUV` (0.043, 0.0758), David's printed sling stone. |
| `brookBank` | Constant: one clean sand texel of `dune1`'s printed windward side (outside `duneShade`, away from the line art of `design/sheet-mock-lineart.png`): sheet (−0.393, 0.411), 0.036 clear → `desert_lines.json uv.sandBankUV`. **Sheet role: keep detail lines away from this point**, or tell me and I will re-pick it. |
| `brook` | None. The ground has a hole here (§12.4), and the real paper (the child's colour) shows through the film. |

Front projection repeats each drawn texel along depth. A colour edge in a drawing therefore becomes a straight band
running back along the 3D piece, such as the dune slip-face (`duneShade`) band along the −X side of each dune. This is
how §12.1 is meant to work and reads as the shaded slip face. Single-colour regions are unaffected.

## For the Sheet role

The Sheet role prints `design.json desert.print`. The build also exports:

- **`assets/david-goliath/model/desert_lines.json`**: per piece `kind`, `mapping`, `frontUV`, `region`. Plus per kind:
  - dunes: `brinkX`, `brinkH`
  - tents: `gableSheet`, `doorSheet` (sheet coords of the drawn gable and door), `skirtBottom3D`
  - banners: `poleBase3D`, `poleTop`, `clothSide`
  - brook: `footprintSheet`, `banks`
  - stones: `stonesSheet`

  Also the `uv` block (`sandBankUV`, `poleUV`, `stoneUV`, `inset`) and `tris`. The v2 top-down fields (`footprint`,
  `crest`, `facetEdges`, `ridge`, `door` in plan view) are **gone**. `tools/make_dg_sheet.py` must stop reading them
  when it switches to `desert.print`.
- **`$DG_WORK/desert_id.png`** (1240 × 1754, the page frame of `design.json sheet.page`). This is a **UV-space** ID
  render: each piece is painted where its UV0 samples the page. For front pieces that is their side-view drawing, so
  the image should match the printed drawings. The brook is shown at its top-down footprint. Banner poles and the
  brook bank are left out (constant UVs). The draw order follows `desert.print`. `desert_id.json` maps
  `id → {id, rgb}`, with the same colour encoding as before.

## For Integration

- Load `desert.glb` under the same page anchor and `shake` pivot as the actors. Use DGPaperLit on `dg_page` with
  `_BaseColor` #F3D58E, `_BaseAmt` 1, and the water shader on `dg_water`. Loop the two `*Wave` clips (sampled on the
  desert root, as now).
- The sand ground layer (§12.4) is yours. The desert assumes it: the pieces sink 0.002 into the page, so their feet meet
  the sand ground without a seam.
- Stones for `kneel_pick` (§12.5): the nearest to the reach point (−0.32, z 0.20) are `stone4` (−0.3955, z 0.164),
  `stone5` and `stone3`. Animation owns `clips.json desertEvents`.

## Verification

`verify` re-imports the GLB and checks:

- Every `design.json` piece id is present under `desert`, and the root has no transform.
- Triangles ≤ 20,000.
- Every vertex is on the paper (zone B is checked against the physical page edge).
- Heights are within each piece's `heightMax` (+0.0025) and the §12.2 caps.
- Nothing is above 0.010 inside **any** part of `stageBand.polygonsSheet`.
- Nothing is above 0.06 at z > −0.30 (`frontZone`).
- Front UVs: all inside their drawing, 99th-percentile error to the plain formula ≤ 0.025.
- Front silhouette of the mesh vs `silhouette3D` ≤ 0.012.
- Both wave animations are present.

Last run: **PASS**, 19,541 triangles.

Measured heights:
- `hillIsrael` 0.306, `hillPhil` 0.382, `duneFar` 0.190
- dunes 0.172 / 0.246 / 0.240
- tent tops 0.373–0.476
- banner tips 0.430 / 0.490
- rocks 0.033–0.098
- shrub 0.047
- brook bank 0.005, stones 0.008

## Previews

`desert_preview_phone.png` is the DGPreview phone eye (−0.08, 0.95, 1.15) with the actors where the Design mock puts
them. `desert_preview_start.png` uses the same eye with both actors on their sheet marks at z 0 (the opening).
`_right` and `_low` are the other two Design views, `_brook` is the brook and stones, and `_topdown` is the whole page
from above.

The characters are `assets/david-goliath/anim/*.glb` at frame 1 of their own `idle` clip. They are coloured with
Design's `sheet-mock-demo-colour.png`, with the printed lines (from `sheet-mock-lineart.png`) filled from their
neighbours. Desert pieces use lerp(scan, sand, paper) as DGPaperLit does. The page under everything is Design's baked
`ground-sand-demo.png`. These previews check composition, shape and UV registration. They do not check final colour.

## Known weak points

1. **Philistine camp vs Goliath.** At the opening (Goliath on his mark, x 0.13, z 0) he covers most of the Philistine
   camp from the phone eye: only the tips of `tentPhil1/2` show over his left shoulder, and his spear stands in front
   of `tentPhil1`. In the Design mock pose (Goliath at 0.22, z −0.25) `tentPhil1` and the red banner show left of him,
   `tentPhil2` shows its top half, and `tentPhil3` is behind his head. Moving the camp would be a Design change.
2. **The hills read a little like sand castles**: a smooth mound with a flat top and a row of pointed tents. The
   meandering foot and the ripples break up the front, but from the phone the ripples are faint.
3. **Front-projection smear**: colour edges in a drawing run straight back along the piece, such as the orange
   slip-face band on the dunes' −X side. It reads as shading, but a child who paints stripes on a dune will see
   stripes running into the page.
4. **Midground dunes are tall, smooth fins.** They read as dunes from the phone, but a real barchan's curved horns are
   not modelled. Their plan view is a rounded loaf because §12.1 fixes the silhouette and the depth band.
5. The previews use the Design mock colouring and Blender lighting, not the app's scan, shader and sand ground. The
   banner wave in Unity and the ground seam at the pieces' feet still need a DGPreview or phone check after Integration.
