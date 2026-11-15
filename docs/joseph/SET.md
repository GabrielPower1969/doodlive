# Joseph: the two lands (Set + sheet role)

One page, two countries. **Canaan (left):** Jacob's goat-hair tent (brown and black woven strips with raised seams,
three rows of poles sagging the roof, guy ropes and pegs, a scalloped front valance, a red rug with a fringe and two
cushions, clay jars); three woolly sheep by a low stone sheep-fold; a stout gnarled olive; the dry well `pit` (four
courses of rough stone blocks, a dark floor) with `bucket` and a coil of rope; the `caravan` (camel with a red and a
blue saddle-cloth and a big bundle, a hooded trader with the lead rope). **Egypt (right):** the `palace` front (a
four-step sandstone dais, a back wall with painted panels, two fat papyrus-bud columns painted cream / blue / cream /
red, a lintel with the winged sun-disc and two cobras, two feather fans, a fire bowl, child `throne`); the `granary`
(three beehive mud-brick stores with plank doors, hatches and a ladder); `grainPiles`; `sacks`; the prison `cell`
(square wooden bars on three sides, open toward the viewer, child `cellBench` with a stone bench and a jug); two date
`palms`. Between: the dune strip and the caravan road (`ground`). Back: the `horizon` (Canaan hills, a real golden
dune mound, the desert and three pyramids). Floating: the four dream clouds. Binding brief: `CONTRACT.md` §6; look:
`DESIGN.md` §2-3.

| What | Where |
|---|---|
| Script | `pipeline/js_twolands.py` (Blender 5.2, headless; story_kit `stage` + this pack's builders) |
| Model | `assets/joseph/model/twolands.glb` (+ `twolands.blend`, region materials, for inspection only) |
| Previews | `assets/joseph/model/twolands_preview_{phone,phone_set,phone_low,front,canaan,cell,palace,granary,dreams,dreams2,topdown}.png` |
| Set drawings | `assets/joseph/model/set_id_2x.{png,json}` (R = region id, G = detail lines; `constUV` = named texels) |
| Sheet | `python3 tools/story/sheet_joseph.py` → `assets/joseph/sheet/`, `print/joseph-A4.{png,pdf}`; then `python3 tools/story/make_colored_pdf.py joseph` → `print/joseph-A4-colored.pdf` |
| Data | `assets/joseph/design.json` → `sheet`, `lines`, `characters` (slots), `set` |

## Rebuild

```
blender -b --factory-startup --python pipeline/js_twolands.py -- all        # build + previews + verify, ~30 s
python3 tools/story/sheet_joseph.py                                          # sheet + checks.json + print/
python3 tools/story/make_colored_pdf.py joseph
python3 tools/story/sheet_joseph.py signature                               # title band vs every other sheet
blender -b --factory-startup --python tools/story/sheet_joseph.py -- render  # textured_*.png (colours on the right parts)
```

`-- check` builds in memory and prints the checks only. The build prints `TWOLANDS_TRIS`, `SPOTS` (free spots found
for the loose props), `LAYOUT`, `BBOXES`, one `CLEAR` line per mark / walk and `CLEARANCE` (must be `OK`).
Rerun the set script, then the sheet, whenever the Characters role moves a figure.

**Why `sheet_joseph.py`:** `make_sheet.py joseph` stops with `StopIteration` until Integration adds Joseph to
`assets/stories.json`. The wrapper supplies a stand-in registry entry in its own process (the real entry wins once it
exists), the Joseph textured scene and the signature check. `make_sheet.py` is unchanged; Esther / Ruth / Daniel prints
and `unity/.../sheet_signatures.json` were checked byte-identical after the run.

## Nodes (root `twolands`, no transform; design (x, h, z))

| Node | Origin | Notes |
|---|---|---|
| `ground` | 0, 0, 0 | pasture x < dune strip, sand x > strip; strip x ≈ −0.07…0.05 (wider at the back); road from the left front edge across the strip to the dais; ripples ≤ 0.009 and flat where the road crosses; one low dune mound at (0.05, −0.43); tufts, pebbles, rocks, the sheep-fold (stones h ≤ 0.03). No drawing: named texels |
| `horizon` | 0, 0, −0.566 | front z −0.566, top 0.279 (big pyramid); golden dune mound centre (0.02, −0.554), 0.37 × 0.11, h 0.155 |
| `tent` | −0.44, 0, −0.42 | footprint x −0.575…−0.305, z −0.51…−0.33; ridge h 0.205, front eave 0.122; open toward +z |
| `sheep` | −0.21, 0, −0.36 | three instances of one sheep at (−0.245, −0.352), (−0.172, −0.395), (−0.200, −0.318); h 0.07. No `sheepNod` action (optional; not made) |
| `olive` | −0.555, 0, −0.065 | trunk radius 0.038 at the foot; crown bottom ≥ 0.205, top 0.336 |
| `pit` | **−0.35**, 0, **0.09** | inner r 0.07, outer 0.09, top h 0.08, dark floor at 0.0045 (see Deviations) |
| `bucket` (child of `pit`) | **−0.215**, 0, **0.155** | bucket h 0.045 + rope coil |
| `caravan` | **−0.39**, 0, **−0.05** | camel facing −x, head to x −0.49, hump/bundle top 0.213; trader at (−0.45, −0.10) |
| `palace` | 0.38, 0, −0.46 | dais x 0.215…0.545, z −0.555…−0.36 (step 1 front), 4 steps, top h 0.05; columns at (0.258, −0.43) and (0.502, −0.43); lintel top 0.363; fire bowl (0.54, −0.325) |
| `throne` (child of `palace`) | 0.38, 0.05, −0.495 | gold; seat top h ≈ 0.09 |
| `granary` | 0.50, 0, −0.04 | stores at (0.465, −0.125), (0.552, −0.068), (0.532, 0.030), r 0.05, h 0.16; ladder on the middle store (moved 2026-11-15 for the new COURT→GRANARY walk) |
| `grainPiles` | 0.493, 0, −0.185 | heaps (0.41, −0.205) (0.575, −0.165), baskets (0.58, 0.085) (0.48, −0.215); hidden (two heaps left out: no room clear of the new walk) |
| `sacks` | 0.299, 0, 0.178 | (0.30, 0.18) (0.355, 0.155) (0.243, 0.20), h 0.057; hidden |
| `cell` | 0.10, 0, −0.06 | bars x 0.02…0.18, back z −0.14, sides run to z −0.04 (open +z side), h 0.20; hidden |
| `cellBench` (child of `cell`) | 0.10, 0, −0.103 | stone bench 0.10 wide × 0.036 deep, **top h 0.062, front edge z −0.085**; jug at (0.04, −0.122) |
| `palms` | 0.58, 0, −0.262 | two palms (0.58, −0.262) and (0.14, −0.445); lowest frond tip ≥ 0.28, top 0.374 |
| `dreamSheaves`, `dreamStars` | −0.32, 0.46, −0.16 | 0.22 wide × 0.135 high (+ cloud puffs), h 0.39…0.53 |
| `dreamSheaves2` | 0.30, 0.50, 0.06 | same mesh and drawing as `dreamSheaves`; h 0.43…0.57 |
| `dreamCows`, `dreamGrain` | 0.30, 0.52, −0.26 | 0.24 wide × 0.14 high, h 0.45…0.59 |

Dream panels: double-sided reliefs facing +z, tilted 15° up toward the camera (top leans back). `hiddenAtStart` in
design.json lists every hidden node. Children hide with their parent (`cellBench` with `cell`, `bucket` stays shown).

### Deviations from CONTRACT §6 (for the lead)

| Item | Contract | Built | Why |
|---|---|---|---|
| well centre | (−0.34, 0.08) | (−0.35, 0.09) | Jacob's S11 walk (−0.46,−0.20)→(−0.10,0.12) passes 0.13 from the contract centre: the 0.09 wall would sit 0.04 from it. Moved 0.014: now 0.053. Joseph's PIT mark is 0.014 off the centre, well inside the 0.07 radius |
| rope and bucket | (−0.46, 0.12) | (−0.215, 0.16) | at the contract spot it sits 0.016 from Joseph's exit walk (−0.34,0.08)→(−0.80,0.30) |
| caravan | (−0.52, 0.17) | (−0.39, −0.05), behind the well | the contract spot was on Joseph's exit walk (0.003 away; that exit is now a snap, the spot was kept so the sheet and previews stay stable). Nearest spot clear of every walk in use while it is shown (S03) and inside the page |
| cell | 0.16 square | 0.16 wide, sides 0.10 deep | the front posts of full-depth sides would be 0.036 from Joseph's walk (0.16,0.06)→(0.10,−0.06) |
| dream panels | width only | heights 0.135 / 0.14 | `dreamSheaves` bottom 0.39 = Joseph's head + 0.03; `dreamCows` bottom 0.449 is above and 0.06 in front of Pharaoh's crown |

## Clearance (CONTRACT §6 rule, printed by the build)

The marks and walks come from `assets/joseph/timeline.json` (story.py as the lead last built it; the CONTRACT §6 list
is only a fallback when there is no timeline): every on-page `to` of an actor is a mark, every move between two of
its consecutive marks is a straight walk, except `snap=True` moves (a cut, no walk). Nothing above 0.012 within 0.05
of a mark or walk; overhead parts between 0.17 and the actor's head + 0.03 must stay 0.035 from the walk line (olive
crown, fronds, dream panels). Hidden props count only while the timeline shows them (walk time = length / 0.10 +
0.6 s). Allowed by the contract: the well wall for Joseph's walks into and out of the well (marks within 0.125 of the
well) and the bench for Joseph's cell mark. **Result (story.py of 2026-11-15, after the lead's staging moves):
`CLEARANCE OK` for all 28 marks and on-page walks.** Closest low geometry:

| Mark / walk | Closest | Mark / walk | Closest |
|---|---|---|---|
| jacob (−0.46,−0.20) | 0.068 | joseph (0.42,0.04) granary | 0.061 |
| jacob walk →(−0.10,0.12) | **0.053** (well) | joseph (0.34,0.08) | 0.057 |
| joseph home (−0.345,−0.167) | 0.082 | joseph walk COURT (0.278,−0.236)→(0.42,0.04) | 0.061 (store moved) |
| joseph rim (−0.26,0.04) | 0.108 (well exempt) | joseph S11 (0.14,0.12)→(0.02,0.12) | 0.113 |
| joseph (0.16,0.06)→(0.10,−0.06) cell | 0.273 (bench exempt) | brother pit edge (−0.156,0.075) | 0.076 |
| joseph (0.10,−0.06)→COURT | 0.139 | brother walk →(0.234,0.124) | 0.057 (sacks) |
| pharaoh (0.38,−0.30) | 0.082 | brother (0.234,0.124) | 0.057 |

**Still blocked, off page (reported, not enforced):** Joseph's S04 entry PARK_L (−0.80,0.30)→(0.16,0.06)
(`carry_work`, not a snap) runs through the well and the bucket. Make it `snap=True` or enter from `PARK` (0.80, 0.30).
All other park moves are now snaps.

## Notes for Animation

* `sit_cell`: the bench top is h 0.062, its front edge z −0.085 (0.025 behind the CELL mark), 0.10 wide.
* `in_pit`: well inner radius 0.07, wall top 0.08, floor h 0.0045; the PIT mark (−0.34, 0.08) is 0.014 from the
  centre (−0.35, 0.09).
* The well rim mark (−0.26, 0.04) is 0.013 outside the wall; the brother's pit-edge mark (−0.156, 0.075) is 0.105 outside it.

## Sheet

Slots (`design.json characters`, the Characters role reads them): Joseph (−0.34, 0.015), brother (0, 0.015),
Pharaoh (0.34, 0.015), Jacob on a second row (−0.34, 0.44). Printed boxes from `regions_characters.json`.

| Drawing | View | Scale | Place (cx, y0) | Members (regions) |
|---|---|---|---|---|
| horizon | front | 3.03 | −0.278, 1.118 | `horizon` (hills, dunes, desert, pyramid) |
| dreamSheaves | front | 0.97 | 0.071, 1.062 | `dreamSheaves`, `dreamSheaves2` (cloud, daySky, sheafBig, sheafSmall) |
| dreamStars | front | 0.97 | 0.344, 1.062 | `dreamStars` (cloud, nightSky, sun, moon + the stars) |
| sheep | front | 0.72 | −0.167, 0.988 | `sheep` (wool, sheepFace) |
| tent | oblique | 1.45 | −0.370, 0.829 | `tent` (tentA, tentB, rug) |
| pit | oblique | 1.30 | −0.160, 0.829 | `pit` (wellStone, joints as single lines) |
| olive | front | 1.60 | −0.005, 0.829 | `olive` (oliveCrown, oliveTrunk) |
| caravan | front | 1.00 | 0.175, 0.829 | `caravan` (camel, saddleRed, saddleBlue, bundle) |
| granary | oblique | 1.20 | 0.385, 0.829 | `granary` (mudBrick, storeDoor) |
| palace | oblique | 1.28 | 0.340, 0.490 | `palace`, `throne` (dais, palaceWall, columnCream, bandBlue, bandRed, lintel, gold, throne) |
| dreamCows | front | 0.76 | −0.015, 0.413 | `dreamCows` (cloud, river, cowFat, cowCream, cowThin) |
| dreamGrain | front | 0.76 | −0.015, 0.621 | `dreamGrain` (cloud, meadow, earFat, earThin) |

Pieces with no drawing take a named texel (`constUV`): ground → horizon hills / desert / dunes (road = dunes), stones
→ well stone, rocks → pyramid; palms → olive crown / trunk; cell → granary door wood, bench → well stone, jug and tent
jars → rug red; grainPiles → fat ears (grain) and the camel's bundle (baskets); sacks → bundle; bucket → olive trunk;
fans → column cream; fire bowl → gold, flame → sun; the trader → saddle blue / camel / bundle; well floor → tent black.
Three fat + three skinny cows are drawn (the narrator says seven); eleven small sheaves bow to the tall one (on paper
two colouring shapes with each sheaf's head drawn); three ears per stalk.

**Checks (`assets/joseph/sheet/checks.json`):** `SHEET PASS`; 43 set regions, **smallest 6.1 mm** (dreamGrain
earFat, palace columnCream); no set region under 6 mm, no slivers, set over cast 0 px, 46/46 anchors on their
regions, ink ≥ 40 px from the top page edge. Cast regions under 6 mm are listed in checks.json (Characters role).
**Title:** 约瑟的梦 / Joseph the Dreamer, box 84 / gap 60 / cy 106; most similar other title band Daniel, NCC 0.52
(bar < 0.6); the title search also compared Jonah's work-in-progress sheet (below the Daniel score); checked on copies, the registry file is untouched.
**Print:** `print/joseph-A4.pdf` and `print/joseph-A4-colored.pdf` are 210 × 297 mm; markers within 0 px of the blank.
Triangles: 42,217 built (41,847 on re-import), budget 60,000; UV0 all inside 0…1.

## Weak or unverified

* Not seen on a phone or in Unity; previews only (EEVEE, mannequin stand-ins).
* `dreamSheaves` on paper: the eleven bowing sheaves print as two masses with their heads outlined (6 mm rule); in 3D
  each sheaf is a separate relief. `dreamGrain` thin ears read as wilted rather than as wheat.
* The caravan stands behind the well, not on the road at the front (see Deviations).
* `sheepNod` (optional) not made. Several regions sit just above 6 mm (6.1-6.4 mm): any later shrink of the dream
  panels or the palace will push them under.
