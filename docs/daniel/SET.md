# Daniel: Babylon (Set + sheet role)

A tabletop stage on the colouring sheet, back to front: the mud-brick **city wall** (reed-mat courses, patches of
raised bricks, stepped Babylonian merlons, two buttress towers; flat roofs and a stepped ziggurat beyond, two flat
palm reliefs) with the blue-glazed **gate** (two glazed wings, two towers, an arched opening with studded wooden doors,
a gold brick arch, gold trims, rosettes with a big one over the arch, a walking lion on each wing facing the gate);
the **palace** front (a façade with pilasters, recessed panels and a blue rosette frieze, a gilded backdrop panel, a
three-step dais, two columns with palm-leaf capitals, a blue-tiled entablature with rosettes and a gilded winged-sun crest,
a red canopy that slopes down from the façade with side valances and gold tassels, incense stands, two jars, two pole
torches) with the carved **throne** (×1.28 of the base design: lion-paw legs, red cushions, a tall back with a round crest, lion-head arms,
footstool); **Daniel's house** (two storeys, arched plank door and shutters, beam ends, a terrace with a wooden
balcony, a striped cloth over it, plant pots and a water jar, a parapet with corner horns, the outside stair, a water
jar and a bench by the door); the **window wall** (pilasters, coping, an arched window with a wooden frame, a diagonal
lattice, open shutters, a pot of flowers on the inner sill) and the woven **rug** (blue border, red field, cream
medallion, fringe); three **date palms** (stacked leaf-base rings, serrated fronds, date clusters); the **lions' den**
(a ring of chamfered stone blocks on both faces with irregular coping, a sandy floor, a straw bed, two flat rocks, a
stone water trough), the big round **stone** (a hewn wheel with a carved ring) open beside the den and, hidden until
S08, shut in the opening with a cord and a red wax **seal**; the **market** stall (red and cream awning with a
scalloped edge, plank counter, pomegranates, a basket of dates, melons, two tall jars, a sack); the **courtyard**
(chamfered paving slabs in running bond, some tilted, a few cracked, warm sand round the edges, tufts, pebbles, rocks
and a bush at the main palm's foot). Original design, Paper & Crayon family of Esther and Ruth. Binding brief:
`CONTRACT.md` §6; look: `DESIGN.md`.

| What | Where |
|---|---|
| Script | `pipeline/da_babylon.py` (Blender 5.2, headless; started from `pipeline/ru_bethlehem.py`) |
| Model | `assets/daniel/model/babylon.glb` (+ `babylon.blend`, region materials, for inspection only) |
| Previews | `assets/daniel/model/babylon_preview_{phone,phone_set,phone_low,front,orbit,window,den,night,sealed,topdown}.png` |
| Sheet | `python3 tools/story/sheet_daniel.py` → `assets/daniel/sheet/`, `print/daniel-A4.*` |
| Data | `assets/daniel/design.json` → `set` (+ `sheet`, `lines`, `characters` slots) |
| Work files | `$DA_WORK` (default `/tmp/daniel_set`): close-ups, preview texture, drawings quick-look |

## Rebuild

```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python pipeline/da_babylon.py -- all
python3 tools/story/sheet_daniel.py                                               # sheet + checks.json
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/story/sheet_daniel.py -- render
python3 tools/story/sheet_daniel.py signature                                     # title band vs every other sheet
```

`all` = build + preview + verify (about 45 s). `build` writes the GLB, the .blend, `model/set_id_2x.*` and the `set`
key of design.json (other keys kept; `characters.<id>.sheetX/sheetY` refreshed from `model/regions_characters.json`).
It prints `BABYLON_TRIS`, `PALM` (the main palm's chosen yaw / scale), `STONES` (where `stoneOpen` went), `LAYOUT`,
one `CLEARANCE_MARK` line per contract mark (margin over the rule) and `CLEARANCE`. `check` prints the same and writes
nothing. Order after any change: (slots in design.json →) `da_characters.py all` → `da_babylon.py all` →
`sheet_daniel.py` → `sheet_daniel.py render`. `DA_TIMELINE=<file>` makes the set script read another timeline (used
2026-11-14 to build against the Story lead's new S05 walk before `timeline.json` was regenerated: all 28 moves of
`story.py` equal that file's).

`tools/story/sheet_daniel.py` runs `tools/story/make_sheet.py` unchanged (Esther and Ruth regenerate byte-identical,
checked 2026-11-14) and adds from outside: a stand-in registry entry while `assets/stories.json` (Integration) has no
`daniel` yet, the Daniel textured scene (`textured_den`), part-anchored cast pieces printed as detail lines (hands,
lower legs, the lion's ears and forelock: already one fixed texel in 3D, so on paper they are guide lines inside
their neighbour, fed to make_sheet's own `anchoredTo` mechanism through a patched copy of the cast inputs), and the
`signature` check, which never writes
`unity/Assets/DoodLive/Resources/sheet_signatures.json` (Integration runs `tools/make_sheet_signatures.py` once the
registry has the entry).

## Coordinates and nodes

Design / glTF `(x, h, z)`: art-width units, page = XZ plane at h 0, +z toward the viewer. Blender builds `(x, -z, h)`.
Root `babylon` has no transform.

```
babylon
├ ground          paving + sand (plan regions), slabs, tufts / pebbles / rocks / palm-foot bush
├ cityWall        mud-brick relief, towers, roofs + ziggurat beyond; front face z -0.560, top 0.215 (merlons 0.244),
│ │               max 0.300 (ziggurat)
│ └ gate          glazed section x 0.20…0.60, arch centre x 0.40 (half width 0.036), towers to 0.293
├ palace          origin (0, 0, -0.46): façade z -0.559…-0.541 (to 0.346), platform x ±0.165, z -0.541…-0.384,
│ │               top 0.040, steps x ±0.12 to z -0.352, columns (±0.135, -0.402), canopy 0.30…0.33
│ ├ throne        (0, 0.040, -0.497), 1.28 x the base design, seat 0.106, crest top ≈ 0.27
│ └ torch         empty at the left pole torch's flame point (-0.15, 0.210, -0.36); a second torch at (0.15, -0.36)
├ house           lower storey x -0.565…-0.325, z -0.545…-0.345, h 0.125; upper x -0.565…-0.415, z …-0.395,
│                 h 0.245 (parapet 0.261, horns 0.269); stair x -0.325…-0.297 rising toward the back
├ windowWall      x -0.5545…-0.5305, z -0.24…-0.04, h 0.160 (pilasters 0.170)
│ └ window        empty (-0.54, 0.10, -0.14)
├ rug             x -0.515…-0.365, z -0.195…-0.085, top ≤ 0.0055
├ palm            main palm trunk (-0.29, -0.07) (template x 1.24, yaw 12°, crown bottom 0.378, top 0.554);
│                 two more at (-0.222, -0.505) x 0.80 and (0.222, -0.505) x 0.82; all three 0.68 as wide as the
│                 template on x and z (the template is drawn with a 6 mm trunk; the 3D trunks stay slim enough)
├ den             centre (0.38, -0.17), inner radius 0.160 (0.182 toward (0.30, -0.26)), wall 0.030, top 0.076
├ stoneOpen       (0.208, 0, -0.291), radius 0.062, thickness 0.028
├ stoneShut       (0.260, 0, -0.043), in the opening; hidden at start
│ └ seal          wax at (0.246, 0.061, -0.029); hidden at start
└ market          (0.52, 0, 0.15): posts x 0.458…0.582, z 0.108…0.190, awning 0.132…0.154
```

- Every mesh carries one material, `da_page` (bind the scanned art rect). `hiddenAtStart`: `stoneShut`, `seal`.
- Triangles **42,431** at build (re-imported GLB 41,839), under the 60k target: gate 7.9k, palace 8.1k, palm (3
  palms) 7.6k, ground 5.2k, den 3.9k, house 2.2k, market 1.9k, city wall 1.7k, throne 1.5k, window wall 0.8k, rug
  0.5k, stones 0.7k, seal 0.3k (`design.json set.pieces[].tris`).

## Marks and clearance

`CLEARANCE` = no set geometry above h 0.012 within 0.05 of a CONTRACT §6 mark or of the straight path between
consecutive targets of one actor (timeline.json; off-page ends clipped to the floor edge). Overhead parts only need
head room: from h 0.17 up to the actor's height + 0.04 (daniel 0.34, king 0.44, officer 0.35, lions 0.22) they keep
0.035 from the line, above that they are ignored. The rug is flat and allowed (contract). Hidden props count for a
walk only while the timeline shows them (`stoneShut` and `seal` 158.75 s … 218.36 s, `stoneOpen` otherwise).

Result 2026-11-14 (after the Story lead moved the official's S05 walk to (0.12, -0.22) → (0.10, 0.06)):
**`CLEARANCE OK`**, every mark and every walk; smallest margins: official (0.12, -0.22) +0.004, lion marks +0.006,
daniel (-0.14, -0.20) +0.008 (all printed per mark). The old walk to (0.30, 0.10) crossed the den's mouth 0.012
from its wall. **`assets/daniel/timeline.json` must be regenerated by the Story lead** (`build_timeline.py daniel`);
until then a plain build reads the old walk and reports that one failure.

## Deviations from CONTRACT §6

1. **Den opening**: centred at (0.260, -0.043), facing 133.5° (direction (-0.69, 0.73)), inner chord 0.112 (mid-wall
   0.122) instead of (0.25, -0.05) / (-0.74, 0.67) / 0.11: the smallest opening that keeps Daniel's walks in and out
   0.05 from the wall ends.
2. **Den inner radius** 0.160 with a bulge to 0.182 toward (0.30, -0.26): the lioness's mark is 0.12 from the centre,
   so a round 0.16 wall stood 0.04 from it.
3. **`stoneOpen`** stands outside the ring at 215° (back-left of the den, by the palace's right torch), not right
   beside the opening: every place between there and the opening lies within 0.05 of Daniel's walk in or of the
   official's walks along x ≈ 0.11 (checked at 5° steps; `build_stones` takes the first clear place).
4. **Stone radius** 0.062 (≈ 0.055 asked): it stands in the opening and must cover the 0.122 mid-wall chord.
5. **Market** at the front-right corner per CONTRACT (DESIGN.md says front-left; the contract wins).
6. **Main palm** is tall (crown bottom 0.378, top 0.554): its fronds must clear the heads of Daniel and the official
   on four walks that pass under it; the yaw / scale search in `build_palms` makes this exact.
7. **Gate pennants** dropped so the wall node stays ≤ 0.30 (the palace façade and crest, 0.35, are not the wall).
8. **Palace frieze** (the entablature and the façade band, glazed tiles with rosettes) is not printed: as a band it
   was 2 mm on the sheet. It wears the gate's tile blue and gold (named texels), one glaze for palace and gate.

## UV0 = the colouring sheet

As Ruth (`docs/ruth/SET.md`): each piece belongs to one drawing, a linear view `a = A·P, b = B·P`,
`u = a / scale + sheetX + 0.5`, `v = (b / scale + sheetY) / 1.227` (`design.json set.drawings`, `pieces[].frontUV`).
P = world position, or the template position for instanced pieces: the three palms wear one palm drawing; both stones
and the seal wear one stone drawing.

New in this pack (LESSONS L51): a face takes one clean texel deep inside its own region not only when it is edge-on
to its drawing but whenever `n·D < 0.22` (facing away too), and when its centre lands on another region of its
drawing (hidden behind another part). So backs, undersides and occluded faces never wear mirrored or borrowed print.
Printed creases come only from sharp edges between exactly two faces (the rims of double-sided cloth, leaves and
awnings no longer print every grid edge). Thin or tiny bits are not drawn and take a named texel (`CONSTS`,
`set_id_2x.json constUV`, all checked by the sheet tool): tufts and leaves → palm frond, pebbles → den stone, torch
poles and the iron door ring → house wood, torch bowls / tassels / incense stands → throne gold, jars and pots →
market jar, lattice → shutter, flowers / cloth stripes → rug red / blue, fringe → rug cream, straw strands and the
seal's cord → den straw, water → gate tiles, palm dates → market dates, studs → gate gold, far palms → palm drawing,
palace frieze tiles / rosettes → gate tiles / gate gold. Merged into a same-colour neighbour region instead: the
palace's crest and backdrop panel print as one gold with the throne; the roofs beyond the wall are mud brick with
the wall.

| Drawing | View | Scale | bbox on the sheet (x0, y0, x1, y1) | Pieces |
|---|---|---|---|---|
| wall | front | 1.75 | −0.207, 1.040, 0.251, 1.211 | cityWall |
| gate | front | 1.35 | −0.188, 0.808, 0.108, 1.025 | gate |
| palace | oblique from above (k 0.34) | 1.65 | −0.199, 0.477, 0.014, 0.729 | palace, throne |
| palm | front, no detail lines | 1.60 | 0.026, 0.477, 0.221, 0.756 | palm (template) |
| house | oblique front-right-above (kx 0.30, k 0.55) | 1.38 | −0.483, 0.832, −0.245, 1.107 | house |
| den | oblique from above (k 0.72) | 1.50 | −0.485, 0.583, −0.225, 0.817 | den |
| stone | front | 0.98 | 0.310, 1.084, 0.434, 1.212 | stoneOpen, stoneShut, seal (template) |
| market | oblique (kx 0.25, k 0.35) | 0.92 | 0.235, 0.374, 0.484, 0.581 | market |
| windowWall | side, from +x (right on the sheet = −z) | 1.08 | 0.276, 0.612, 0.468, 0.769 | windowWall |
| rug | plan, no detail lines | 0.68 | 0.262, 0.782, 0.482, 0.944 | rug |
| ground | plan | 7.0 | 0.286, 0.957, 0.458, 1.071 | ground |

(Exact values: `design.json set.drawings.*.bboxSheet`.) Big flat regions print only chosen decor lines (patches of
bricks on the walls, a few slabs and cracks on the paving, the den's block joints), the cartoon way, so each region
keeps a large colourable cell.

## Colouring sheet

Page 1240 × 1754 @150 dpi, four markers, art rect [120, 283, 1000, 1227], 田字格 title 但以理与狮子 /
dàn yǐ lǐ yǔ shī zi / Daniel and the Lions, footer 但以理书 6 章 · Daniel 6.

**Slots (re-planned 2026-11-14; CONTRACT §2's slots overlapped in the A-pose):** daniel (−0.34, 0.015), king
(0, 0.015), official (0.34, 0.015) on the bottom line at Ruth-like spacing; the side-view lion (nose to −x) on a
second row above Daniel at (−0.361, 0.368). Set drawings in three columns round them: left (den, house), middle
(palace + palm, gate, wall), right (market, window wall, rug, ground, stone). `pipeline/da_characters.py all` was
re-run with these slots.

**Title band**: box 84 / gap 22 / cy 104 (not Esther/Ruth's 76 / 12 / 100): with those values the six boxes matched
David & Goliath's six-box title at NCC 0.80. Now the most similar other sheet is fiery-p2 at NCC 0.37 (a true match
is about 0.9; the closest pair among the existing sheets is 0.65). Pinyin top 38 px from the page edge (≥ 35.4).

Status 2026-11-14 (second round, owner: regions under 6 mm are too hard for children): `SHEET PASS`, 150 colourable
pieces, 53 detail parts, no slivers, no region without a cell, 64 / 64 anchors and constant texels on their region,
no ink within 6 mm of the page edge, no set drawing over a figure.

**Region minimums** (best inscribed cell per colourable region, measured on the print): all **35 set regions ≥ 6.2 mm**
(lowest: market pomegranate, gate relief, palace cushion 6.2 mm; dates, den stone, sand 6.3–6.4 mm). Cast regions
still under 6 mm: officer skin 4.1 mm, Daniel skin and king skin 4.4 mm (the faces between hairline and beard),
Daniel hair + beard 2.0 mm, king beard 4.1 mm, Daniel collar 5.4 mm. They are the faces and hair at the A-pose head
size and the main colours a child gives each person, so they were not made fixed-colour: the fix is a head-size
change by the Characters role (or an owner decision).

**Cast regions made fixed-colour** (edit to `pipeline/da_characters.py` `ANCHORS` / `PART_ANCHORS` / `PROP_ANCHORS`,
commented there; `da_characters.py all` re-run): each printed no cell of 6 mm anywhere, so it now prints as detail
lines inside its neighbour and wears a printed set region of the same or the nearest demo colour. Daniel: sandals
(no cell) → house wood, sash (2.0 mm) → rug blue. King: medallion (4.1), belt (2.0), crown band (1.7), ring → throne
gold; cape (2.0) → gate tiles; shoes (1.7) → house wood. Official: beard (1.0) → the king's beard; headband (0.7) →
gate gold; sash (1.7) → palm frond; stripes (1.7) → palace canopy red; slippers (2.4) → house wood; the hidden
scroll's seal → the stone's red wax. Lion: muzzle (2.4) and inner ears → rug cream; tail tuft (1.8) and nose (0.8) →
house wood. The hands, lower legs and the lion's forelock were already part-anchored by the Characters role; they now
print as detail lines too. Colouring the set therefore also colours these parts of the cast (the throne's gold is the
king's gold, Daniel's sash is his prayer rug's blue).

## Demo colours

`design.json set.demoColours`, from DESIGN.md (wall #D8B07A, gate tiles #2E5FA8, reliefs #E8C15A, columns #E3CFA3,
canopy #B8423A, throne #D9A63A, house #D9A06A, door / wood #8A5A3B, rug #B8423A + #2E5FA8, den stones #9C8A72, floor
#D9B77A, straw #E9D08A, palm #4F8A3C / #8A6A44, paving #E6D6B4), plus: sand #E2C389, roofs beyond #D9A06A, ziggurat
#C99A62, gate doors #8A5A3B, palace wall #EAD7AE, frieze #2E5FA8, cushion #B8423A, terrace roof #C98F5C, shutters
#8A5A3B, rug cream #F4EEDD, flat rocks #B5A68C, big stone #A79A86, wax #C0392B, awning #B8423A / #F4EEDD, stall
#A47548, pomegranate #C0392B, melon #7DAA4E, jars #C8643C, dates #B8682E.

## Previews

`phone` (S01 stand-ins: king at the dais, Daniel and the official at court, both lions asleep in the den) and
`phone_set` use the Esther / Ruth phone eye (−0.08, 0.95, 1.15) → (−0.08, 0.05, −0.50); `phone_low` a closer phone;
`front`; `orbit` (S01 opening); `window` (S05: Daniel on the rug, the official at the palm); `den` (S09 inside);
`night` (S09/S10 light, stone shut and sealed, the torch lit); `sealed` (the seal close up, night); `topdown`. The
set is textured with the demo colouring through its UVs (lines removed, crayon grain). The figures are stand-ins.
`assets/daniel/sheet/textured_*.png` show the real cast and set wearing the demo sheet (`textured_den`: Daniel in
the den with the lion, the king and the official outside).

## Known rough points

1. The official's S05 path vs the den (above) is a story fix; until then `CLEARANCE` reports it.
2. Cast faces, hair and beards and Daniel's collar are below 6 mm (above); every set region is at least 6.2 mm.
3. The relief lions on the gate are simple flat silhouettes (5 mm on the sheet); the far palms beyond the wall are
   not printed (they take the palm drawing's colours).
4. Not yet seen in Unity with DGPaperLit and a real scan.
