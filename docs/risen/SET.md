# He Is Risen! — set `garden` and colouring sheet

Script: `pipeline/rs_garden.py` (`-- check | build | all | verify`). Output: `assets/risen/model/garden.glb`
(+ `.blend`, `set_id_2x.*`, `garden_preview_*.png`), the `set`, `characters` and `sheet` blocks of
`assets/risen/design.json`. Sheet: `tools/story/sheet_risen.py` (make_sheet.py unchanged; the wrapper is needed only
until Integration adds `risen` to `assets/stories.json`) → `assets/risen/sheet/`, `print/risen-A4.{png,pdf}`; then
`tools/story/make_colored_pdf.py risen` → `print/risen-A4-colored.pdf`. Textured check renders:
`blender -b --factory-startup --python tools/story/sheet_risen.py -- render` → `assets/risen/sheet/textured_*.png`.

## 1. Nodes (root `garden` at the origin)

| Node | Parent | What | Origin (x, h, z) |
|---|---|---|---|
| `ground` | root | grass, the rest of the floor (extra node) | origin |
| `path` | root | pale earth: house door (0.30, −0.22) → front strip z ≈ 0.05…0.15 → gate → forecourt in front of the tomb (x −0.47…−0.06, z −0.26…−0.10) | (0, 0, 0.08) |
| `flowers` | root | 29 blooms (lily / poppy / daisy, tops 0.030…0.038) in the front-left bed x −0.60…−0.30, z 0.04…0.20 and the hill-foot bed x −0.60…−0.46, z −0.29…−0.20 | (−0.42, 0, 0.11) (butterflies) |
| `gardenWall` | root | blocks x −0.048…−0.032, h 0.026 (alternate 0.023), z −0.28…−0.008 and 0.128…0.21 | (−0.04, 0, 0) |
| `tombHill` | root | rock x −0.60…−0.04; front face z −0.312 for x ≤ −0.25, then an alcove 0.04 behind the rolled stone's back (face z −0.47 at x −0.17, −0.57 at x −0.05); face top 0.375 at the door; rounded top, crest 0.395; 3 bushes, ivy patch left of the door; top **0.410** | (−0.28, 0.04, −0.24) (S03 camera) |
| `tombDoor` | tombHill | the opening x −0.395…−0.265, top 0.34 (round top r 0.065): reveals + chamber x −0.42…−0.24, z −0.48…−0.32, ceiling 0.36, floor 0.0045 | **(−0.33, 0.15, −0.30)** (FX anchor) |
| `cloths` | tombHill | ledge on the back wall, left half, x −0.412…−0.30, z −0.478…−0.43, top 0.075; folded linen (two layers) + rolled head cloth | (−0.356, 0, −0.454) |
| `groove` | tombHill | stone track x −0.54…−0.05, z −0.31…−0.26, two rims top 0.006 | (−0.295, 0, −0.285) |
| `tombStone` | tombHill | **lead-approved 2026-11-18**: disc r 0.195 at mid-thickness (0.164 at the faces), 0.05 thick, centre (−0.33, 0.19, −0.285); x −0.525…−0.135; top cut flat at **0.38**: covers the whole 0.34 door | its centre |
| `tombStoneAside` | tombHill | **hidden**; lead-approved 2026-11-18: the same stone rolled right off the door (left end at (−0.262, −0.285)) and turned 40° back into the alcove; centre **(−0.1126, 0.19, −0.4103)**; flat seat on top at **0.38** (0.092 wide within 4 mm of the top) → **ANGEL_Y 0.311** (seat rig-local 0.069; ANIMATION.md §2) | its centre |
| `gardenTools` | tombHill | spade (top 0.156) leaning on the face + watering jar, at (−0.575, −0.25) | (−0.575, 0, −0.25) |
| `olive1` | root | trunk (0.00, −0.565), crown underside 0.24, top 0.36 | trunk |
| `olive2` | root | trunk (−0.57, −0.05) r 0.016, crown underside 0.21, crown x ≤ −0.53 | trunk |
| `house` | root | ground storey x 0.06…0.60, z −0.584…−0.22, h 0.10 (door x 0.25…0.35 top 0.096, shutters x 0.44…0.53); room walls 0.02 thick; back wall z −0.584…−0.580 to 0.46; right wall full height behind z −0.42, sloping to 0.14 at the front; left wall 0.46 behind z −0.40, **0.40 over the door part**, down to the sill; 1 cm sill (top 0.11); roof edge back and sides only | (0.33, 0.10, −0.38) (S05/S10 camera) |
| `houseIn` | house | inside wall faces, floor mats, lamp shelf (extra node) | as house |
| `stair` | root | x 0.022…0.058, 4 steps from z −0.155 to a landing at y 0.10, z −0.26…−0.345 | (0.04, 0, −0.25) |
| `roomDoor` | house | door leaf at the **outer** face of the left wall (x 0.060…0.064), z −0.34…−0.26, top 0.37; bar x 0.064…0.068 at y 0.22…0.234; the wall has a niche through it there | (0.06, 0.10, −0.30) |
| `bench` | house | x 0.14…0.50, z −0.56…−0.51, cushion tops 0.14 (3 cushions) | (0.32, 0.10, −0.535) |
| `lowTable` | house | x **0.462**…0.56, z −0.36…−0.26, top 0.15, 4 legs; bread basket at (0.537, −0.279) | (0.511, 0.10, −0.31) |
| `fishPlate` | lowTable | clay plate r 0.030 at (0.50, −0.31) | (0.50, 0.15, −0.31) |
| `fishOnPlate` | fishPlate | two grilled fish side by side, heads to the back | (0.50, 0.153, −0.31) |
| `lamp2` | lowTable | at **(0.542, −0.344)**, nozzle to −x | its wick (0.523, 0.161, −0.344) |
| `waterJar` | house | (0.12, −0.53), r ≤ 0.031, top 0.22, two handles | (0.12, 0.10, −0.53) |
| `lamp1` | house | on a back-wall shelf (x 0.30…0.34, top 0.32) at (0.32, −0.570) | its wick (0.335, 0.331, −0.570) |
| `hills` | root | relief x −0.60…0.06, z −0.5875…−0.5845, y 0.38 up to 0.47…0.54 | |
| `cityWall` | root | relief x 0.06…0.60, same z, y 0.44 to 0.575 (battlements 0.589), gate tower x 0.38…0.47 to 0.64 (0.654 with battlements), arched gate drawn | |

Hidden at start: `tombStoneAside`. Triangles **20,840** (re-imported GLB 20,732); budget 60,000 (quality bar) /
70,000 (contract). Verify: all 27 nodes, 0 UV outside 0-1.

## 2. Deviations from CONTRACT §6

| Contract | Built | Why |
|---|---|---|
| gate gap z 0.00…0.12 | z −0.008…0.128 | the walks (0.06, 0.11) → GATE, GATE → TOMB_DOOR and GATE → (−0.22, −0.14) passed 0.045 / 0.050 / 0.047 from the wall ends; now 0.053 / 0.055 / 0.052 |
| stone 0.22 across, rolled along the groove to (−0.17, −0.285) | **lead-approved 2026-11-18** (also in CONTRACT §6): 0.39 across, top 0.38; rolled aside = left end at the door edge, turned 40° back, centre (−0.1126, −0.4103); rim rounded | a sealed tomb must look sealed; a 0.39 stone rolled straight would hit the stair (x 0.022) and the house (x 0.06). Seat top 0.38 → ANGEL_Y 0.311 (the built clips' seat is rig-local 0.069; story.py and CONTRACT match, lead 2026-11-18) |
| front face "z ≈ −0.30" | −0.312 along the door and groove | the groove's back edge is −0.31; the stone (z −0.31…−0.26) must not cut into the rock |
| `gardenTools` (−0.52, −0.27), `olive1` (0.00, −0.50), groove x0 −0.45 | (−0.575, −0.25), (0.00, −0.565), −0.54 | the bigger closed stone reaches x −0.525; the rolled stone passes 0.03 in front of olive1's trunk |
| `lowTable` x 0.46…0.56 | x 0.462…0.56 | TABLE_J is 0.052 from the edge (0.05 is the limit) |
| `lamp2` (0.53, −0.33) | (0.542, −0.344) | it overlapped the plate |
| house door, window (unsized) | door 0.10 wide | the wood region on the sheet ≥ 6 mm |
| room left wall | 0.40 high over the door part (z −0.40…−0.24) | a 0.27 door cannot sit under a wall sloping to 0.14; seen from the S05 / S10 / S11 cameras the wall does not cover the room (checked) |
| room door in the wall | leaf flush with the wall's **outer** face, bar against it | ROOM_DOOR (0.12, −0.30) is 0.04 from the wall's inner face; with the niche the nearest set point is the jamb, 0.052 |

## 3. Clearance (`-- check`, measured; low zone y+0.012…0.17 needs 0.05, overhead to the head 0.035)

**CLEARANCE OK** for all 41 marks and all 30 straight walk legs of `story.py` (every move, including S12's places and the
women's S01 / S04 moves). `tombStone` (closed) is ignored at marks and walks used after it rolls (S04 on); everything
else, hidden props included, counts everywhere. Tightest (low / overhead): MARY_DOOR 0.077 / 0.075 (rolled stone),
JESUS_G 0.052 (wall), ROOM_DOOR 0.052 / 0.040 (jamb), TABLE_J 0.052 (table edge), walk ROOM_J → TABLE_J 0.052,
GATE → (−0.22, −0.14) 0.052, (0.06, 0.11) → GATE 0.053, S12 Thomas (0.06, −0.10) 0.055
(stair front), TOMB_DOOR 0.058 (rock face 0.072), (−0.10, 0.02) 0.059; seated BENCH thomas / john / peter 0.059 /
0.071 / 0.090 (radius 0.035; the jar is the nearest). STONE_ASIDE (−0.1126, −0.4103): nothing but the stone above
the 0.38 seat within 0.08 (nearest 0.173); TOMB_DOOR 0.083, JOANNA_DOOR 0.083, MARY_T 0.13, JOANNA_T 0.124. All other marks ≥ 0.06. Numbers per mark: `design.json
set.clearance.nearest`.

## 4. Looked at (phone camera = StoryDirector on a 1080 × 2340 portrait screen: dist and height × 2.26, vfov 60)

`garden_preview_phone(_set)`, `_s01 … _s12` (+ `_s10_table`, fish hidden) with stand-in actors at the story's marks,
`_tomb_closed`, `_tomb_open`, `_hidden` (table with plate, fish, basket, lamp2), `_front`, `_topdown`; textured
(sheet demo colours through UV0, real cast): `assets/risen/sheet/textured_*.png`. Colours land on the right parts.
Notes for the lead (story.py not touched):
- The stone (lead decision): closed it covers the whole door (`_tomb_closed`); rolled, the door, the chamber and the
  linen are fully visible and the stone stands in its alcove (`_tomb_open`). Where its left end meets the rock the
  face shows a small saw-tooth edge (the face triangulation at the alcove's start); hidden behind the stone from the
  shot cameras.
- S03 (fixed on `tombHill`, yaw 15): at MARY_T / JOANNA_T the two women stand between the camera and the rolled stone;
  the angel is seen above them. A camera yaw of about −25 (like S04) or the women 0.04 further left would clear it.
- Between the hill's right end and the house (x −0.04…0.06) the camera sees the paper behind the floor (the printed
  drawings), as in The King Who Serves' lane. Only `olive1` stands there.

## 5. Sheet

Drawings (`design.json set.drawings`): `skyline` (hills + city wall, front), `tomb` (front-above; the rock is drawn
with lines, not auto-creases, because the receding shoulder would print as hatching; the door is printed from a
raster-only pane so the chamber never samples the rock: L51), `house` (frontal), `room` (inside, L51), `props` (one
still life: table with plate, two fish and basket; water jar ×0.6; linen; the round stone ×0.245 — both stone nodes
print once), `ground` (plan), `olives` (both crowns), `flowers` (three template blooms + a leaf; every bloom in 3D is
an instance). Named texels: chamber and ledge → tomb:door; groove, garden wall, spade blade → props:stone; trunks,
spade handle, room door, bench frame → house:wood; bench cushions → flowers:poppy; lamps, watering jar → props:clay;
stems and leaves → flowers:leaf.

Prop anchors for the Characters role (`design.json set.propAnchors`): `jesus/fish` → props:fish (0.4955, 0.70864);
`mary/jar`, `joanna/jar` → props:clay (0.3905, 0.64914). The cast's current anchors in `regions_characters.json`
((0.4955, 0.67278), (0.3935, 0.62795)) are older but still land on the right regions (sampled); re-read on the next
Characters run.

Set regions, best cell (make_sheet rule): smallest skyline:cityStone 6.4 mm, tomb:leaf 6.8, props:fish 6.8,
house:wood 7.1, room:mats 7.1, flowers:lily 7.2, ground:path 7.5; all others 7.9-26 mm. No slivers, every region has a
colourable cell, 35 / 35 anchors on their regions. Final slots (unchanged from CONTRACT §2, also in
`regions_characters.json`): angel −0.32 / 0.015, jesus 0.0 / 0.015, mary 0.32 / 0.015. Title 他复活了: box 76,
gap 40, cy 110 (title-search; worst title-band NCC 0.402 against Daniel, bar < 0.6). `print/risen-A4.pdf` and
`-colored.pdf`: 210.0 × 297.0 mm, markers 0 px from the blank. **SHEET PASS.** Cast regions under 6 mm (Characters
role): mary hair 1.1 mm, jesus hair 1.7, angel hair 1.9, mary veil 2.3, jesus beard 3.0, jesus belt 4.7, jesus face
5.5, angel sash 5.8, mary face 6.0 (`assets/risen/sheet/checks.json`).

## 6. Weak or unverified

- No device or Unity check: hidden-prop swaps (`tombStone` / `tombStoneAside`, `fishOnPlate`) and the FX anchors are
  checked in Blender only.
- Stand-ins are cylinders; the angel on the 0.38 seat (wings against the alcove, legs along the turned stone's face) and the women's
  `peek` hands on the rock edge need the Animation role's probe with `garden.glb`.
- The house drawing shows the room as a blank paper hole (the room interior prints in its own `room` drawing), as in
  The King Who Serves; the stair prints as narrow steps (not colourable, limestone elsewhere).
- The tomb chamber, ledge and room cushions take colours from other drawings (door, poppy red), so a child colouring
  them differently would see that in 3D.
