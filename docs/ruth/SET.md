# Ruth: Bethlehem at harvest (Set role)

A tabletop stage that stands on the colouring sheet, back to front: two layers of hills (stone terraces, olive bushes,
the hint of the town wall and houses) with six cypress trees; Naomi's stone house (stone courses, flat clay roof
inside a parapet with flax drying on it, beam ends, a plank door under a stone arch, a barred window, a ladder to the
roof, two storage jars, a basket of grain, a clay oven with firewood); the round threshing floor (flagstone paving, a
rim of boulders, the grain heap with straw round its foot, a winnowing fork leaning on it, sacks, straw bundles, an
oil lamp on a stone); the barley field (skinned clumps with drooping bearded ears that sway in a looping wind), its
stubble, three sheaves and a dry-stone field wall; a gnarled olive tree with three water jars and a cup in its shade;
the pale road from Moab with a footpath to the field; ochre ground with grass patches, tufts, pebbles, rocks and
shrubs. Hidden props: `dropped` (S07) and `canopy` (S10). Same Paper & Crayon family as Esther; Iron-Age Judah in
feel, original design. Binding brief: `CONTRACT.md` §6; look: `DESIGN.md`.

| What | Where |
|---|---|
| Script | `pipeline/ru_bethlehem.py` (Blender 5.2, headless) |
| Model | `assets/ruth/model/bethlehem.glb` (+ `bethlehem.blend`, region materials, for inspection only) |
| Previews | `assets/ruth/model/bethlehem_preview_{phone,phone_set,phone_low,front,orbit,field,night,wedding,topdown}.png` |
| Sheet | `tools/story/make_sheet.py ruth` → `assets/ruth/sheet/`, `print/ruth-A4.*` |
| Data | `assets/ruth/design.json` → `set` (+ `sheet`, `lines`, `characters` for the sheet tool) |
| Work files | `$RU_WORK` (default `/tmp/ru_set_work`): close-ups, preview texture, drawings quick-look |

## Rebuild

```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python pipeline/ru_bethlehem.py -- all
```

`all` = build + preview + verify (about 50 s). `build` writes the GLB, the .blend, `model/set_id_2x.*` (the set
drawings for the sheet) and the `set` key of design.json (other keys are kept; `sheet` / `lines` are only filled in
when missing; `characters.<id>` sheet places are refreshed from `model/regions_characters.json`). The build prints
`BETHLEHEM_TRIS`, `SHEAVES`, `LAYOUT` (drawings inside the art rect, ≥ 0.012 apart, ≥ 0.02 from the figures),
`CLEARANCE` (contract rule, must be `OK`) and `CLEARANCE_SOFT` (reported only, see below). Never hand-edit the GLB.
Rerun the set script whenever the Characters role moves a figure (`regions_characters.json`), then `make_sheet.py`.

## Coordinates and marks

Design / glTF `(x, h, z)`: art-width units, page = XZ plane at h 0, +z toward the viewer, z 0 = art rect's bottom edge.
Blender builds `(x, -z, h)`; `export_yup` converts back. Root `bethlehem` has no transform.

| Thing | Value |
|---|---|
| floor | x ±0.60, z −0.5875…0.21 (ground mesh with a skirt) |
| hills | foot of the near slope z −0.552, ridge z −0.589, far flat z −0.600…−0.590; top h 0.263 (far ridge), near ridge ≤ 0.17 |
| house | core x −0.44…−0.163, z −0.53…−0.333, walls h 0.20, parapet top 0.226; stone faces stand to z ≈ −0.329; door x −0.30 (opening ±0.035, arch top 0.145); node origin (−0.30, 0, −0.43) |
| threshing | centre (0.30, −0.44), paving radius 0.112, rim to 0.134; heap (0.306, −0.45) h 0.086; `lampFlame` (0.2205, 0.0295, −0.34) |
| field | barley in x 0.21…0.54, z −0.22…≈ −0.04 (the front strip stays stubble for Boaz's S08 walk), 112 clumps of five stalks, 0.05…0.09 high; `field` node at (0.37, 0, −0.11) |
| stubble | band x 0.10…0.54, z 0.00…0.08 and the field's front strip; stubs ≤ 0.0105 |
| sheaves | (0.58, 0.00), (0.58, −0.175), (0.58, −0.22) along the field's right edge (the only spots clear of every mark and move); h 0.08 |
| fieldWall | x 0.188, z −0.205…−0.02 (contract length), h ≤ 0.031; toward the back end the upper stones near Boaz's S08 walk are left out (a lower, tumbled end) |
| olive | trunk (−0.44, −0.10), crown centre ≈ (−0.476, −0.096), radius ≈ 0.09, crown bottom 0.17, top 0.317 |
| waterJars | three jars at (−0.430, −0.022), (−0.462, −0.040), (−0.476, −0.004) + a cup; node at their centre (−0.456, −0.022) |
| canopy | poles (±0.14, 0.0) to h 0.446 (finials 0.465); everything between the poles is ≥ 0.405 high |
| dropped | nine stalks within 0.04 of (0.24, 0.10), h ≤ 0.009 |

**Deviations from CONTRACT §6, all forced by its own clearance rule:**
1. `waterJars` stand at x ≈ −0.46, not −0.34: Naomi's walk from the road (−0.40, 0.16) to the door (−0.30, −0.20)
   crosses (−0.35, −0.02). They are still in the olive's shade. `WATER` in story.py is not an actor target.
2. (2026-11-14 follow-up) Boaz no longer crosses the field: the Story lead rerouted his S08 walk along the
   stubble front and up the left of the wall, so the field has full rows and the wall its contract length.
3. Olive crown radius ≈ 0.09 (not 0.10) and shifted 0.035 to the left: a 0.10 crown at (−0.44, −0.10) overhangs
   Naomi's mark (−0.40, −0.22) and her road-to-door walk at head height.
4. Canopy top 0.446 (≈ 0.42 asked): the cloth, valances, swag and flowers must clear Boaz's head (0.38) when he
   walks under it in S10.

`CLEARANCE OK` = no set geometry between h 0.012 and 0.17 within 0.05 of any CONTRACT §6 mark or of the straight
path between consecutive marks of one actor (from `timeline.json`, plus the contract's entrances from x ±0.62);
overhead parts (olive crown, canopy cloth) between 0.17 and 0.40 must stay 0.035 from the line (a head's radius),
above 0.40 they are ignored. The barley is tested at eight sway phases. `canopy` only counts for the wedding marks,
`dropped` for none (both hidden otherwise).

`CLEARANCE_SOFT` (the first moves of the play, from each actor's printed place (sheetX, 0), and off-page park
moves) is also clean since Boaz parks at (0.70, 0.18); the barley and the sheaves keep clear of those moves too.

## Nodes (`bethlehem.glb`)

```
bethlehem                     root, identity
├ ground                      plan regions + scattered tufts / pebbles / rocks / shrubs
│ └ road                      road from Moab + footpath to the field (own node, same drawing)
├ hills                       far flat, town hint, near slope with terraces, bushes, 6 cypresses
├ house                       walls, roof, parapet, arch, beam ends, threshold, window lintel, flax
│ ├ door  window  ladder  houseJars  basket  oven (with firewood)
├ threshing                   paving, rim, straw ring, sacks, straw bundles
│ ├ grainHeap  fork
│ └ lamp                      lamp stone + clay lamp
│   └ lampFlame               empty at the spout (lamp_flame FX)
├ field                       armature (action fieldSway) at the field centre
│ └ barley                    skinned clumps (112)
├ stubble                     stubs + loose straws
│ └ sheaves                   three sheaves (one mesh)
├ fieldWall  olive  waterJars
├ dropped                     hidden until S07
└ canopy                      hidden until S10
```

- Every mesh carries one material, `ru_page` (bind the scanned art rect, as the characters).
- `fieldSway`: 4 s loop at 24 fps (frame 1 = frame 97, loop error 0). Bones `field_root` + a 6 × 2 grid
  `sway_<i>_<j>`; each clump's vertices blend from the root (at the foot) to its nearest sway bone (at the ears,
  weight (h/0.075)^1.5). Sideways gust ±4.2° + 1.6° second harmonic running across the field left to right, plus a
  ±1.8° nod; largest movement 0.012 at the ears.
- Triangles **76,417 / 80,000** at build (budget raised from 60k on 2026-11-14; the re-imported GLB counts 73,785):
  barley 39.0k, ground 5.5k (+ road 0.5k), hills 5.4k, house 4.8k (+ door 0.4k, jars 0.7k, basket 0.4k, oven
  0.4k, ladder 0.2k), canopy 3.5k, stubble 3.2k, olive 3.0k, threshing 2.7k (+ heap, fork, lamp 0.7k), sheaves 2.5k,
  field wall 2.0k, water jars 1.0k, dropped 0.5k (`design.json set.pieces[].tris`).
- Barley ear (`barley_ear`): three kernel bulges that alternate left / right of the axis with waists between them
  (two-row barley), nodding from the stalk, and a beard of two long awns; stalk heights 0.060…0.081 within a clump,
  per-clump scale 0.86…1.04 and height 0.84…1.10, random yaw and lean.

## UV0 = the colouring sheet

Each piece belongs to one *drawing*: the piece seen in a linear view, rendered by the script as line art, so a
child's colour lands on the surface behind it. A drawing has row vectors A, B (sheet axes) and D (depth, nearer =
larger): `a = A·P`, `b = B·P`, `u = a / scale + sheetX + 0.5`, `v = (b / scale + sheetY) / 1.227`. P is the vertex
in its drawing's model: the world position, or the template position for instanced pieces (all 81 barley clumps
wear the one barley drawing, the three sheaves the one sheaf drawing). `design.json set.drawings` / `set.pieces[].frontUV`
hold A, B, D, scale, sheetX, sheetY.

| Drawing | View | Scale | bbox on the sheet (x0, ys0, x1, ys1) | Pieces |
|---|---|---|---|---|
| hills | front | 1.75 | −0.343, 1.050, 0.343, 1.201 | hills |
| sheaf | front | 0.62 | −0.481, 1.062, −0.369, 1.185 | sheaves (template) |
| barley | front, no detail lines | 0.60 | 0.357, 1.040, 0.483, 1.173 | barley (template) |
| house | oblique front-right-above (kx 0.30, k 0.42) | 1.22 | −0.482, 0.755, −0.076, 1.021 | house, door, window, ladder, houseJars, basket, oven |
| threshing | oblique from above (k 0.55) | 1.05 | −0.060, 0.830, 0.246, 1.013 | threshing, grainHeap, fork, lamp |
| olive | front | 1.30 | 0.260, 0.760, 0.384, 1.011 | olive |
| ground | plan | 2.80 | −0.482, 0.430, −0.054, 0.715 | ground, road |
| canopy | oblique from above (k 0.5), no detail lines | 1.35 | −0.040, 0.430, 0.206, 0.784 | canopy |
| waterJars | front | 0.62 | 0.268, 0.505, 0.392, 0.603 | waterJars |
| fieldWall | side-oblique, from the road side (−x, k 0.6) | 0.85 | 0.222, 0.430, 0.478, 0.477 | fieldWall |

- Faces nearly edge-on to their drawing's view (|n·D| < 0.22, n in drawing space) take one texel from deep inside
  their own region's printed area (as Esther's upward faces): the tops of things in front views, cylinder sides.
- Scattered bits that are not drawn take one texel of a named region (`CONSTS`, listed in `set_id_2x.json constUV`
  and checked by the sheet tool): stubble stubs → ground:stubble, tufts → ground:grass, pebbles and rocks →
  fieldWall:wallStone, shrubs → hills:bush, dropped stalks → barley:barley.
- Stone courses on the house are printed as single mortar lines (bed and head joints written by the masonry
  builder), not as the chamfer edges, which printed as dense double lines and were dropped by the sheet's density
  filter. Barley and canopy print without inner detail lines (they split the clump into specks too small to colour).
- Outlines lie outside each drawing's silhouette, so UVs need no inset; inner region lines and grey detail lines
  must be erased / filled from neighbours by the scan pipeline, as for the characters.

## Colouring sheet

Composed by `tools/story/make_sheet.py ruth` exactly like Esther: page 1240 × 1754 @150 dpi, four markers, art rect
[120, 283, 1000, 1227], 田字格 title 忠心的路得 / zhōng xīn de lù dé / Faithful Ruth, footer 路得记 · Ruth. Figures
at the bottom at the Characters role's places (`regions_characters.json`), the set drawings above them
(`model/set_id_2x.png/.json`: R = region id, G = detail lines), so print and UVs cannot drift.

```
python3 tools/story/make_sheet.py ruth                                                 # sheet + checks.json
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/story/make_sheet.py -- ruth render
STORY_OUT_ROOT=/tmp/x python3 tools/story/make_sheet.py esther                         # compare without touching the repo
```

Status 2026-11-14 (after the barley rework): `SHEET PASS`, anchors 13 / 13, 206 colourable pieces, no set slivers,
no set drawing over a figure, all five set texels on clean colour. Title band: `ruth-A4` appended to
`unity/Assets/DoodLive/Resources/sheet_signatures.json` (other entries untouched); most similar other title
esther-A4 at NCC 0.64 (Esther / D&G 0.40; a true match is about 0.9). Order after any change: `ru_characters.py`
→ `ru_bethlehem.py` → `make_sheet.py ruth` (the characters' prop anchors point into the set's sheaf and barley
drawings, so a moved set drawing needs the Characters script rerun too).

`make_sheet.py` takes the story id; additions for Ruth (Esther's output is byte-identical, PDF timestamp aside,
checked 2026-11-14 from copied inputs): `STORY_OUT_ROOT` output override, one story scene per pack in the textured
renders (`STORY_SCENE`: Esther's banquet, Ruth's field), and for packs other than Esther the set's
`hiddenAtStart` nodes stay hidden in the textured renders; an `anchoredTo` written `<char|set>.<region>` is checked
against that other drawing's region (Esther's anchors have no dot, so they are checked as before).

## Demo colours

`design.json set.demoColours`, from `DESIGN.md` (barley #E8B84A, stubble #E9D08A, sheaves #E2A93B, house stone
#D9C29A, door #8A5A3B, roof #C9A77A, olive crown #8FA876 / trunk #7A6650, hills #A7B86A / #8FA9A0, cypress #3F6B45,
road #E9D9B6, ground #D9B77A, jars #C8643C, canopy white / #F4A6B8 / #F7D154), plus: grass #B4C26C, field soil
#C9A065, bushes #7F9E5C, town #DCC79E, arch / threshold #C7AE84, wood #A47548, window #5A3D2A, flax #D9C27E,
basket #C9A05C, oven #B97E55, threshing floor #E4CD95, rim and lamp stone #BDAE93, grain #E6B24A, sacks #EBDDBF,
lamp #C8643C, barley leaves #B7B85A, sheaf tie #9A6A3E, field-wall stone #CDBB98, garland #8DB36A.

## Previews

`phone` / `phone_set` use the Esther phone eye (−0.08, 0.95, 1.15) → (−0.08, 0.05, −0.50), with and without
stand-ins (S04: Ruth gleaning, Naomi at the house, Boaz on his mark); `phone_low` is a closer, lower phone
(0.02, 0.62, 0.95), about a child's 40 cm over an A4 page; `front`; `orbit` is the S01 opening; `field` (S07 with
`dropped` shown); `night` (S09 light with the lamp); `wedding` (S10, canopy shown); `topdown`. The set is textured
with the demo colouring through its UVs (lines removed, crayon grain), so they check UV registration as well as
shape. The figures are simple stand-ins in the demo colours, not the real characters. The lamp flame is a
preview-only cone (the app plays `lamp_flame`).

## Known rough points

1. Up close the ears are stylised (three-sided, three kernels, two awns) to fit the budget; at phone distance the
   field reads as a golden mass rather than individual ears. The front ~0.04 of the field is stubble (Boaz's S08 walk).
2. Small printed regions (best cell below the 6 mm rule): window dark, flax on the roof, canopy cloth valance,
   poles, flowers and garland, barley leaves, sheaf tie, fork, lamp. They are pattern details a child may leave
   white; the anchored texels still give each 3D part a sensible colour.
3. The far hill is a flat, painted-flat panel (by design, like a theatre backdrop); seen low from the side its
   thickness shows. The town is a hint only (wall, houses, a tower in relief).
4. The budget is nearly used (76.4k of 80k): any new prop must save triangles elsewhere first (stubble stubs and
   tufts are the cheapest to thin out).
5. Not yet seen in Unity with DGPaperLit and a real scan.
