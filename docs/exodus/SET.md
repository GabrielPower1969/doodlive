# Exodus: Egypt and the sea (Set role)

A tabletop stage on the colouring sheet, back to front: a low backdrop (a far dune panel, near dunes, two pyramids
with stone courses and gold caps, the red-rock mountain in terraced strata with a zigzag ledge path and dry shrubs);
Pharaoh's palace (paved platform, back wall with a painted frieze and a starred blue panel behind the throne, four fat
papyrus-bundle columns with gold bands and open capitals, architrave with a gold roll and cavetto cornice, the winged
sun with two cobras, a two-step dais with gold edges, a gilded throne on lion legs with a red cushion and footstool,
two lamp stands, two obelisks with gold pyramidions and hieroglyph ticks, two date palms); two Israelite mud-brick
houses (dark doorways under wooden lintels, windows, beam ends, low parapets, roof mats, jars on the roofs and by the
doors, a bench, an outside stair) with hidden red `doorMarks`; the brick yard (a trampled mud floor, a half-built
wall of single bricks in running bond with a stepped end and an earth ramp, three cross-stacked piles, bricks drying
in rows, two wooden moulds, a water trough, a mud pit with a hoe, the straw pile) with eight workers; the Nile
(rippled water, ten papyrus clumps, lily pads and lotus, a papyrus-bundle boat with rope bindings); the thorn bush on a
rocky rise; the sea (rippled surface in three parts, foam at both shores, a deeper band down the middle, a wet
sand-bed with ripples, shells, pebbles, seaweed and two starfish under the crossing lane) and the two standing water
walls; the far shore with three palms and rocks; hidden crowds on both shores and Pharaoh's loose wheel; ochre sand
with the wilderness track, a pale west beach, wet sand along the water, dry tufts, pebbles and stones. Same Paper &
Crayon family as Esther and Ruth; New Kingdom Egypt in feel, original design. Binding brief: `CONTRACT.md` §6; look:
`DESIGN.md`.

| What | Where |
|---|---|
| Script | `pipeline/ex_egypt.py` (Blender 5.2, headless; Ruth's `ru_bethlehem.py` machinery, Exodus builders) |
| Model | `assets/exodus/model/egypt.glb` (+ `egypt.blend`, region materials, for inspection only) |
| Previews | `assets/exodus/model/egypt_preview_{phone,phone_set,phone_low,front,orbit,palace,brickyard,bush,night,sea_rest,sea_parted,sea_phone,sea_lane,sea_back,topdown}.png` |
| Sheet | `tools/story/sheet_exodus.py` (runs the shared `make_sheet.py` unchanged) → `assets/exodus/sheet/`, `print/exodus-A4.*` |
| Data | `assets/exodus/design.json` → `set` (+ `sheet`, `lines`, `characters.<id>.sheetX/sheetY`) |
| Work files | `$EX_WORK` (default `/tmp/ex_set_work`): close-ups (`close_*.png`), preview texture, drawings quick-look |

## Rebuild

```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python pipeline/ex_egypt.py -- all
python3 tools/story/sheet_exodus.py                                                    # sheet + checks.json + print
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/story/sheet_exodus.py -- render
```

`all` = build + preview + verify (about 50 s); `check` builds in memory and prints the checks only. Use the same
`STORY_WORK` for the sheet and its `render` (the render reads the sheet's line-free fill from it). The build prints
`EGYPT_TRIS`, `LAYOUT`, `BBOXES`, `CLEARANCE` (must be `OK`), `CLEARANCE_SOFT` (reported only), `SEA_LANE`,
`CHAR_PLACES` and `BUDGET`. Never hand-edit the GLB. Order after any change: `ex_characters.py` → `ex_egypt.py` →
`sheet_exodus.py`.

`make_sheet.py` is not touched: the wrapper adds Exodus's textured story scene (`textured_sea`, S11 on the dry path)
and, until Integration adds `exodus` to `assets/stories.json`, a stand-in registry entry (set `egypt`, cast moses /
pharaoh / miriam). Ruth and Esther sheets were rebuilt from the shared tool after this work: byte-identical.

## Coordinates and nodes

Design / glTF `(x, h, z)`: art-width units, page = XZ plane at h 0, +z toward the viewer, z 0 = art rect's bottom edge.
Blender builds `(x, -z, h)`; `export_yup` converts back. Root `egypt` has no transform.

```
egypt                         root, identity
├ ground                      plan regions (sand, track, beach, farSand, wetSand) + tufts / pebbles / stones
├ backdrop                    far dune panel across the whole back (0.17-0.25 high), near dunes
│ ├ pyramids                  two pyramids, x -0.115 (h 0.272) and x -0.455 (h 0.200), gold caps
│ └ mountain                  height field x 0.10…0.60, z -0.5875…-0.40, top 0.26; ledge path, shrubs
├ palace                      platform, back wall, 4 columns, architrave + cornice, winged sun, obelisks, lamp stands
│ ├ dais                      two steps, front z -0.36, top 0.030
│ │ └ throne                  at (-0.36, 0.03, -0.458)
│ └ palacePalms               palms at (-0.588, -0.535), (-0.158, -0.552)
├ nile                        papyrus clumps (one drawing), lily pads, lotus
│ ├ nileWater                 the river surface (own mesh for river_red)
│ └ nileBoat
├ brickyard                   floor, wall + ramp, piles, drying rows, moulds, trough, mud pit, hoe
│ └ straw                     straw pile at (-0.452, -0.040)
├ crowdWest                   8 workers in the yard: four bend to lift bricks, three carry one on the shoulder, a woman with a jar (S01-S07)
├ houses                      two houses, fronts z -0.415 / -0.408
│ └ doorMarks                 red paint on both lintels (above the wooden beam) and both posts; hidden at start
├ bush                        rocky rise + acacia, top 0.113
│ └ bushFlame                 empty at (0.14, 0.088, -0.38)
├ sea                         empty at (0.30, 0, -0.015)
│ ├ seaWater                  empty
│ │ ├ seaWaterBack            z -0.24…0.02
│ │ ├ seaWaterLane            z 0.02…0.13 (Effects hide it)
│ │ └ seaWaterFront           z 0.13…0.21
│ ├ seaBed                    x 0.20…0.40, z 0.02…0.13, flush (max h 0.0036)
│ ├ seaWallBack               origin (0.30, 0, 0.02); rest scale (1, 0.02, 1); hidden at start
│ └ seaWallFront              origin (0.30, 0, 0.13); rest scale (1, 0.02, 1); hidden at start
├ farShore                    three palms (one drawing)
│ └ farRocks
├ crowdShore                  7 people (a mother leading a child, bundles, jars, shepherds) + a sheep; hidden at start (S08-S11)
├ crowdFar                    8 people + 2 sheep; hidden at start (S11 on)
├ looseWheel                  six-spoke wheel flat at (0.28, 0.05), h 0.0056; hidden at start
└ pillarWest                  empty at (0.16, 0, -0.12)
```

**Names confirmed for Effects / Integration** (exact glTF node names): `seaWaterBack`, `seaWaterLane`,
`seaWaterFront`, `seaBed`, `seaWallBack`, `seaWallFront`, `nileWater`, `doorMarks`, `bushFlame`, `pillarWest`, plus
`sea`, `bush`, `looseWheel`, `crowdShore`, `crowdFar`, `crowdWest`. `design.json set.hiddenAtStart` = `doorMarks
crowdShore crowdFar looseWheel seaWallBack seaWallFront`.

### The sea walls (the hero)

- Each wall's **origin is at its base** (h 0, on the page, at the lane edge of its footprint): `seaWallBack` at
  (0.30, 0, 0.02), `seaWallFront` at (0.30, 0, 0.13). Modelled at full height; the exported node carries the rest
  scale **(1, 0.02, 1)** (glTF Y), so scaling Y to 1 about the origin raises the wall from the sea-bed. Verified on
  re-import (`VERIFY wallScaleBlender` = (1, 1, 0.02) in Blender axes = glTF Y 0.02).
- `seaWallBack`: inner face at z 0.02 facing +z, x 0.20…0.40; body crest ≈ 0.23-0.24 (0.267 with spray droplets);
  a breaking lip that curls toward the lane and down, its size and the crest height swell and fall along x; the ends
  bend back and fall away round into the sea; flow ripples run down the inner face; the back slope is piled water with
  wave bands down to the back of the sea (z -0.23). Foam lumps along the crest and on the curl, a foam skirt at the
  inner foot, ~40 spray droplets. Ten fish silhouettes (one little school of three) stand 3.4-5 mm proud of the
  inner face.
- `seaWallFront`: same section at 0.56 scale (crest ≈ 0.14, 0.165 with spray), inner face at z 0.13 facing −z, its
  lip kept short (reaches 0.0095 into the lane), back slope down to the page's front edge (z 0.21); three fish.
- UV: the walls take named texels of the sea drawing: body `sea`, the lowest band `seaDeep`, crest and curl `foam`,
  fish `seaDeep` (darker than the body). No extra sheet region, as the contract asks. In the previews the walls get a
  light "inner glow" mix; in the app that is the shader / FX's job.
- `SEA_LANE` (printed by the build, walls raised): back wall reaches 0.023 into the lane (the curl and its foam, at
  h ≈ 0.20-0.24), front wall 0.0095; sea surfaces ≤ 0.0085, sea-bed ≤ 0.0036.

## Marks and clearance

`CLEARANCE OK` = no set geometry between h 0.012 and 0.17 within 0.05 of any CONTRACT §6 mark or of the straight
path between consecutive marks of one actor (from `timeline.json`), overhead parts (palm crowns) 0.17-0.40 at least
0.035 from the line, and nothing above 0.012 in the wilderness lane (x 0.04…0.62, z −0.34…−0.26). Props shown only
part of the play (`crowdShore`, `crowdFar`, `doorMarks`) are tested against every stand and move made while they are
shown (windows from the timeline's prop events). Exempt and why: the sea walls (they stand only while parted; the lane
is checked by `SEA_LANE`), `seaWaterLane` (≤ 0.012, Effects hide it), `looseWheel` (lies at Pharaoh's feet on
purpose in S12).

`CLEARANCE_SOFT` (reported only): the first moves from the printed places, `start moses (0,0) → (0.64,−0.30)` (passes
a far-shore palm crown and tufts) and `start pharaoh (−0.33,0) → (−0.36,−0.30)` (straight through the brick yard). In
the timeline both are `t = 0` placements, not walks.

**Deviations from CONTRACT §6, forced by its own clearance rule:**
1. `crowdShore` is not in x −0.08…0.12: Miriam's S08 walk (−0.02,−0.32)→(0.02,0.13) and Moses's
   (0.08,−0.30)→(0.12,0.08) cross that whole box while the crowd is shown (it appears before they walk), and a figure is
   ~0.025 wide. A woman with a jar stands at (−0.088, −0.198); the other six and the sheep wait on the west beach between
   Moses's walk and the water, x 0.17…0.20, z −0.23…−0.03 (beside the pillar spot, not on it). If the Story lead moves
   `prop crowdShore show` after the two walks, they can go back into the contract box.
2. The far-shore palms stand at (0.468, −0.425) (leaning back onto the mountain foot), (0.585, −0.168) and
   (0.575, 0.005): a palm nearer the wilderness lane puts fronds over Moses's S02 walk at head height.
3. Wilderness: the bush's thorny crown spreads back and sideways, its front (above 0.012) stays at z ≤ −0.34 because
   Moses's walk to (0.04, −0.28) passes 0.073 in front of the bush centre.

**Miriam's S11 mark** moved from (0.27, 0.11) to (0.27, 0.09) (story.py / CONTRACT, 2026-11-14): at z 0.11 her body
touched the front wall's inner face (z 0.13). The script's `CONTRACT_MARKS` uses 0.09; the moves come from
`timeline.json` (rebuilt by Story). Moses's (0.30, 0.07) clears the back wall's curl by ~0.027 at chest height.

## Triangles

**69,376 at build / 75,000 allowed** (raised from 65k by the coordinator for the crowd rework, 2026-11-14; the
re-imported GLB counts 67,548): sea walls 15.1k (back 8.1k, front 7.0k), crowds 15.8k (west 4.6k, shore 4.9k, far
6.2k), palace 6.8k (+ throne 0.5k, palms 1.6k), Nile 5.7k (+ water 0.8k, boat 0.6k), ground 4.9k, mountain 3.4k, sea
surfaces 3.0k, far shore 2.8k, houses 2.2k, brick yard 1.9k, bush 1.6k, sea-bed 1.5k, backdrop + pyramids 0.7k, wheel
0.3k (`design.json set.pieces[].tris`).

## Crowd people

Seven templates in the one `people` drawing (P offsets side by side), each about 0.12 high (instances scaled
0.92-1.05, so 0.11-0.13), facing +z: a robe flaring to the hem with soft folds, a sash, sleeves and hands, sandalled
feet, a head-cloth framing the face (headband for men), eyes and a nose as a hint of a face, beards on the men; men
also wear a shoulder shawl. Templates: `man` (shepherd with a staff), `jar` (a woman with a water jar on her head),
`bundle` (a man with a bundle over his shoulder), `mother` (a woman with a bundle on her head leading a child by the
hand), `bend` (a worker bent 48° forward, both hands on a brick at his feet), `carry` (a worker with a brick on his
shoulder), `sheep`. Eyes and beards take the doorway's dark texel, headbands and sandals the trough's wood, jars the
houses' jar, bricks the yard's brick (`PEOPLE_CONST`). Back faces of every drawing now take a clean texel of their own
region (LESSONS L51), so no face prints through the back of a head-cloth.

## UV0 = the colouring sheet

As Ruth (`docs/ruth/SET.md`): each piece belongs to one drawing (a linear view rendered by the script as line art), so
a child's colour lands on the surface behind it; edge-on faces take one clean texel of their own region; scattered bits
take named texels (`CONSTS`, `set_id_2x.json constUV`, checked by the sheet tool). Instanced pieces (palms, papyrus,
people) wear one template drawing each.

| Drawing | View | Scale | bbox on the sheet (x0, ys0, x1, ys1) | Pieces |
|---|---|---|---|---|
| backdrop | front | 1.62 | −0.475, 1.020, 0.265, 1.188 | backdrop, pyramids, mountain |
| bush | front | 0.95 | 0.345, 1.085, 0.481, 1.204 | bush |
| palace | oblique (kx 0.30, k 0.42) | 1.25 | −0.484, 0.735, −0.103, 1.001 | palace, dais, throne |
| houses | oblique (kx 0.30, k 0.42) | 1.00 | −0.089, 0.843, 0.189, 1.005 | houses, doorMarks |
| palm | front | 1.10 | 0.326, 0.790, 0.474, 1.012 | palacePalms, farShore (template) |
| brickyard | oblique from above (k 0.6) | 0.85 | −0.033, 0.625, 0.277, 0.821 | brickyard, straw |
| papyrus | front | 0.85 | 0.304, 0.630, 0.480, 0.761 | nile (template), nileBoat |
| ground | plan | 3.10 | −0.482, 0.435, −0.095, 0.692 | ground, nileWater |
| sea | plan turned a quarter (right = +z, up = +x) | 1.85 | −0.081, 0.440, 0.163, 0.548 | seaWaterBack, seaWaterFront, seaBed |
| people | front, no detail lines | 1.20 | 0.175, 0.435, 0.484, 0.548 | crowdWest, crowdShore, crowdFar (7 templates side by side) |

Named texels: tufts and seaweed → palm:frond; pebbles → palace:stone; stones and far rocks → backdrop:rock; lily
pads / lotus → papyrus; lane water and both walls → sea:sea / seaDeep / foam; shells → sea:foam; starfish →
houses:doorMark; the loose wheel → palace:gold; bricks carried by workers → brickyard:brick; the mountain's ledge
path → ground:track (too thin to print). Printed as single lines (decorOnly): pyramid courses and arrises, dune
ripples, paving joints, obelisk hieroglyphs, mud-brick patches and roof-mat weave, the yard wall's courses and the
brick outlines, wave marks on the river and the sea.

Changes from Ruth's UV code (in this script only): (1) the clean-texel search erodes octagonally (4- and 8-neighbour
steps alternate) with a 1 px margin round detail lines; Ruth's 4-neighbour erosion overrated thin diagonal shapes
(fronds, leaves) and put the tuft texel 2.8 px from ink; (2) faces with n . D < 0.22 (edge-on **or facing away**) take
the clean texel, not only |n . D| < 0.22 (L51); (3) a template drawing's raster source is built at its drawing places:
stacked at the origin, merge-by-distance welded coincident lathe-axis vertices of different templates and printed
long bars across the people drawing.

## Colouring sheet

Page 1240 × 1754 @150 dpi, four markers, art rect [120, 283, 1000, 1227], 田字格 title 出埃及 / chū āi jí /
Let My People Go!, footer 出埃及记 · Exodus. Figures at the bottom at the places in `design.json characters`
(pharaoh −0.33, moses 0.0, miriam 0.33), the set drawings above them.

Status 2026-11-14 (after the crowd rework, against the Characters role's 15:40 files): **SHEET PASS**, anchors
**44 / 44**, 320 colourable pieces, no set slivers, no set drawing over a figure, no ink on the art-rect edge, layout
OK. `design.json characters.moses.sheetY` = **0.027** (`SHEET_PLACE` in `ex_egypt.py`; `ex_characters.py` reads it):
at 0.015 his staff foot printed on the art rect's bottom edge. The build prints `CHAR_PLACES … in step with
regions_characters.json` when the Characters render matches.

Title band (`tools/make_sheet_signatures.py` measure, computed without writing the Unity file): most similar other
title esther-A4 at **NCC 0.73**, then ruth-A4 0.64, david-goliath 0.49, daniel 0.48 (a true match is about 0.9; Ruth
vs Esther is 0.64). Tried 出埃及记 (0.72 with Daniel), 摩西出埃及 (0.64 with Ruth), 让我的百姓走 (0.83 with Daniel):
出埃及 is the most distinct. `exodus-A4` is **not** yet in `unity/Assets/DoodLive/Resources/sheet_signatures.json`:
Integration runs `make_sheet_signatures.py` after adding Exodus to `assets/stories.json`.

## Demo colours

`design.json set.demoColours`, from `DESIGN.md` (sea #2C7FA8, sea-bed #C8A97A, Nile #3E8FC4, reeds #6FA24A, lotus
#F4A6B8, bricks #A9673F, straw #E9D08A, trough #8A5E3A, houses #C99A6B, door marks #C2413A, palace stone #E3C998,
columns #EFE0BE, gold #E0B13A, pyramids #E2BE7A, dunes #EBD3A0, rock #B5643F, bush #5E4330 / #8FA876, palms #4F8A3C /
#8A6A44), plus: sand #E8CC92, track #F0DDB2, beach #F0E0B6, far sand #F3E6C4, sea deep #1F6690, foam #E6F3F2, capital
#5FA58A, frieze / wings #2F5DA8, dais #D8BB86, throne #E8B83A, cushion #C2413A, obelisk #DDB08F, roof #D9B26A,
doorway #4A3324, jars #B8653A, trough water #6CB2DA, mud #9C7650, papyrus heads #A6C25E, boat #D9B26A, people robes
#C98B3A / #8FA3B8 / #B5532E, head-cloths #F1E6CC, skin #C68A5E, bundles #B07A47, wool #F4F1EA.

## Previews

`phone` / `phone_set` use the Ruth phone eye (S01 stand-ins: Pharaoh at his dais, Miriam at the yard, Moses parked);
`phone_low`; `front`; `orbit` (S01); `palace`; `brickyard`; `bush` (S03 dusk with a preview-only flame);
`night` (S07, door marks shown, warm doorway lights); `sea_rest` (S10, crowd on the beach); `sea_parted`, `sea_phone`,
`sea_lane`, `sea_back` (S11: walls raised, lane water hidden, far crowd shown); `topdown`. Close-ups in `$EX_WORK`
(`close_wall_inner` shows the fish, `close_wall_crest` the curl, `close_crowd_{west,shore,far}` the crowd people).
Moses, Pharaoh and Miriam in the previews are simple stand-ins; `assets/exodus/sheet/textured_*.png` show the real
characters.

## Known rough points

1. The crowd people are small and simple by design (robes, head-cloths, a hint of a face); up close their robes are
   smooth cones. Their printed figures are small (people drawing at scale 1.20); the sheep's face, skin and wool are
   below 6 mm.
2. Small printed regions without a colourable cell (left white or coloured from the neighbour by the line erase):
   palace wings, palm dates, papyrus heads and boat rope; door marks and the pyramid caps are below 6 mm.
3. The ground plan is mostly plain sand with the sea as a hole (the sea has its own, larger drawing).
4. The page beyond the stage floor (art rect z −1.227…−0.5875, the top of the printed sheet) is real paper in the app
   and was visible behind the low dunes in the phone preview. The far dune panel now spans the whole back at 0.17-0.25
   (lower behind the pyramids' peaks), as Ruth's far hill does; only a sliver of the bush drawing shows past the
   mountain's right shoulder. It was never a UV error: no set geometry reaches there.
5. The mountain is a height field seen from the front; from the back orbit its vertical back face shows.
6. Not yet seen in Unity with DGPaperLit, a real scan, or Effects' `sea_part` raising the walls.
