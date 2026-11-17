# The King Who Serves — set `jerusalem` and colouring sheet

Script: `pipeline/ls_jerusalem.py` (`-- check | build | all | verify`). Output: `assets/lastsupper/model/jerusalem.glb`
(+ `.blend`, `set_id_2x.*`, `jerusalem_preview_*.png`), the `set` and `characters` blocks of
`assets/lastsupper/design.json`. Sheet: `tools/story/sheet_lastsupper.py` (make_sheet.py unchanged; the wrapper is
needed only until Integration adds `lastsupper` to `assets/stories.json`) → `assets/lastsupper/sheet/`,
`print/lastsupper-A4.{png,pdf}`; then `tools/story/make_colored_pdf.py lastsupper` → `print/lastsupper-A4-colored.pdf`.

## 1. Nodes (root `jerusalem` at the origin)

| Node | Parent | What | Origin (x, h, z) |
|---|---|---|---|
| `road` | root | pale earth strip z 0.04…0.18 from x 0.60 to −0.26, branch from the bend to the gate | (0.20, 0, 0.10) |
| `palmsRoad` | road | **hidden**: 4 palm branches (z 0.055…0.10) + red, blue, yellow coats (z 0.11…0.16), x 0.07…0.57, top 0.0062 | (0.32, 0, 0.105) |
| `stones` | road | 5 stones, heap centre (0.05, 0.177), radius ≤ 0.025, top 0.027 | (0.05, 0, 0.177) |
| `ground` | root | the rest of the floor (extra node) | — |
| `temple` | root | the court paving x 0.02…0.60, z −0.5875…−0.12 | (0.31, 0, −0.35) |
| `courtWall` | temple | low wall z −0.1285…−0.1115, h 0.035, gate gap x 0.08…0.30, posts h 0.04 (extra node) | |
| `templeFront` | temple | relief z −0.5875…−0.577, x 0.03…0.60, wall 0.36, gold cornice + pediment to 0.45, bronze door x 0.29…0.39 h 0.25; 4 columns r 0.02 at z −0.52, x 0.07 / 0.19 / 0.48 / 0.575; architrave y 0.40…0.425 (extra node) | |
| `awnings` | temple | two striped canopies, x 0.28…0.455 and 0.095…0.165, from y 0.43 (z −0.505) to 0.39 (z −0.445); poles at both ends, z −0.50 (extra node) | |
| `table1` | temple | dove table x 0.350…0.414, z −0.447…−0.398, top 0.06 | (0.382, 0.06, −0.4225) |
| `cages` / `cagesOpen` | table1 | 3 wicker cages, top 0.119; doves peep out / doors open, empty (**hidden**) | (0.382, 0.09, −0.4225) |
| `table2` | temple | money table x 0.423…0.494, z −0.307…−0.253, top 0.06: coin chest, 2 coin stacks, a little scale | (0.4585, 0.06, −0.28) |
| `table2Tipped` | temple | **hidden**: the same table on its side, top facing +x, legs toward Jesus, yaw −8°, footprint x 0.433…0.497 | (0.474, 0, −0.28) |
| `coinsFloor` | temple | **hidden**: 22 flat coins x 0.405…0.575, z −0.235…−0.155, top 0.0047 | (0.49, 0, −0.195) |
| `house` | root | ground storey x −0.60…−0.06, z −0.584…−0.22, h 0.10 (door, shutters); upstairs walls: left/right 0.02 thick, back z −0.584…−0.578 to 0.46; side walls full height behind z −0.42, sloping to 0.14 at the front; 1 cm sill (top 0.11); roof edge only at the back (z −0.584…−0.55) and sides (to z −0.42) | (−0.33, 0.10, −0.40) |
| `houseIn` | house | inside wall faces, night-sky window x −0.31…−0.21 y 0.24…0.36, floor mats, lamp shelf (extra node) | |
| `stair` | root | outside stair x −0.058…−0.022, 4 steps from z −0.25 to a landing at y 0.10 (z −0.445…−0.505) (extra node) | |
| `bench` | house | x −0.58…−0.532, z −0.54…−0.24, seat (cushion tops) UPPER + 0.04 | (−0.556, 0.10, −0.39) |
| `lowTable` | house | x −0.355…−0.202, z −0.50…−0.42, top UPPER + 0.05, cloth hanging 3 cm; seat cushions at the 5 supper marks (r 0.03 × 0.026, **h 0.0115**); herb dish, fruit bowl | (−0.2785, 0.10, −0.46) |
| `breadLoaf` / `cupTable` / `lamp2` | lowTable | loaf r 0.021 at (−0.27, −0.46); cup r 0.014 h 0.03 at (−0.24, −0.45); lamp at (−0.222, −0.484) | at each; lamp2 at its wick |
| `basinStand` | house | round stand at (−0.115, −0.535), r 0.028, top UPPER + 0.08 | (−0.115, 0.10, −0.535) |
| `basinJug` | basinStand | basin r 0.027 with water on the stand; the jug on the floor beside it at (−0.097, −0.561) | (−0.115, 0.18, −0.535) |
| `lamp1` | house | clay lamp on a back-wall shelf at (−0.46, −0.570), y 0.298 | at its wick (−0.445, 0.309, −0.570) |
| `palmTree` | root | at (−0.02, −0.56), trunk r 0.015, crown 0.44…0.52 | |
| `oliveTree` | root | trunk at (0.00, −0.30); crown centre (−0.015, −0.30), r ≈ 0.035, underside 0.172 | |
| `hills` | root | relief x −0.60…−0.06, z −0.5875…−0.5845, y 0.42 to 0.57…0.65 (0.11…0.19 above the back wall) | |
| `crowd` | root | armature, bones `sway1…8`; action **`crowdSway`** 3 s, 24 fps, ±4° side to side about the feet, staggered phases | origin |
| `crowd1…6` | crowd | adults, head top 0.226…0.240, palm tips ≤ 0.28, z −0.072…−0.068, x 0.300…0.563 | at their feet |
| `crowd7`, `crowd8` | crowd | children, head 0.145 / 0.140 (palm tips ≤ 0.17), at (−0.300, 0.165) and (−0.355, 0.183), facing +x | at their feet |

Hidden at start: `palmsRoad`, `table2Tipped`, `coinsFloor`, `cagesOpen`. Triangles **23,214** (re-imported GLB 23,246);
budget 70,000. Verify: all nodes present, 0 UV outside 0-1, `crowdSway` sway 0.024, loop error 0.

## 2. Deviations from CONTRACT §6 (all to keep marks clear or regions ≥ 6 mm)

| Contract | Built | Why |
|---|---|---|
| `bench` x −0.58…−0.50 | x −0.58…−0.532 | ARGUE andrew (−0.48, −0.32) was 0.02 from the bench front; now 0.052 |
| `lowTable` x −0.36…−0.18 | x −0.355…−0.202 | STAND (−0.15, −0.46) was 0.03 from the table end; now 0.052. SUP andrew 0.055 |
| `lamp2` (−0.20, −0.47) | (−0.222, −0.484) | stays on the shortened table |
| `basinStand` (−0.12, −0.53) | (−0.115, −0.535), r 0.028; jug on the floor beside it | STAND 0.052 from the stand; the jug cannot stand on it without blocking STAND |
| `table1` x 0.34…0.46, z −0.45…−0.39 | x 0.350…0.414, z −0.447…−0.398 | SELLER2 (0.46, −0.37) was 0.023 from table1; the J_T2 → J_T1 walk was 0.044 from its corner. Now 0.054 / 0.053. J_T1 is 0.07 from the table (contract: 0.05-0.06) |
| `table2` x 0.42…0.50 | x 0.423…0.494, scale on the left, chest right | the SELLER2_SIDE → COINS walk; now 0.052 |
| `table2Tipped` footprint ≤ x 0.56 | x 0.433…0.497 (lying where it stood) | SELLER2_SIDE is inside the contract footprint; now 0.066 |
| court wall gate gap x 0.08…0.22, wall at z −0.12 | gap x 0.08…0.30, wall z −0.1285…−0.1115 | the GATE → J_T2 walk passed 0.009 from the gate post (now 0.057); COINS was 0.045 from the wall (now 0.052) |
| crowd z −0.04…0.00 | z −0.072…−0.068 | James walks at z 0.03…0.05; at z ≥ −0.04 the figures were inside his 0.05 |
| two children at x ≥ 0.52, z ≥ 0.17 | at the road's end by the house, (−0.30, 0.165), (−0.355, 0.183) | that corner is John's and Andrew's start marks and inside the donkey box at DONKEY_START |
| `stones` at (0.05, 0.17) | heap centre (0.05, 0.177), stones kept at z ≥ 0.16 | the donkey's 0.30 × 0.12 box sweeps to z 0.16 between DONKEY_MID and (0.18, 0.09) |
| seat cushions ≤ 0.02 | 0.0115 | below the 0.012 rule, so they never block a walk |
| room back wall 0.02 | 0.006 (z −0.584…−0.578) | the floor ends at −0.5875 and the hills relief sits behind it |
| seated marks (BENCH ×4, SUP ×5) | checked at radius 0.035, not 0.05 | a seated body's half depth; the wall / table they sit against is 0.038-0.04 away by contract |

## 3. Clearance (`-- check`, measured; low zone y+0.012…0.17 needs 0.05, overhead to the head 0.035)

OK (nearest low / overhead): DONKEY_START box gap 0.104, DONKEY_MID 0.045, (0.18, 0.09) 0.012, BEND 0.032,
DONKEY_TIE (both headings) 0.008; all disciples' road marks and walks ≥ 0.062; PETER_STONES 0.062 (stones 0.059, top
0.027, nothing else within 0.08); GATE 0.079, J_T2 0.060, J_T1 0.070, P_COURT 0.092, JN_COURT 0.129, JA_COURT 0.054 /
0.051 (olive crown), SELLER1 0.052, SELLER2 0.054, SELLER2_SIDE 0.066, COINS 0.052; walks GATE→J_T2 0.057,
J_T2→J_T1 0.053, SELLER2_SIDE→COINS 0.052; STAND 0.052, ROUND 0.075, WASH andrew 0.075, (−0.43, −0.30) 0.102,
WASH peter 0.102, ARGUE 0.052 / 0.078 / 0.090 / 0.060; BENCH ×4 0.040; SUP 0.038 / 0.038 / 0.038 / 0.055 / 0.089;
walks ROUND→WASH andrew→(−0.43, −0.30)→WASH peter ≥ 0.057 (overhead 0.050). Kneeling lane: clear.

**Not clear — the contract's own marks conflict; the lead decides (story.py not touched):**

| Mark / walk | Blocked by | Measured | Suggestion |
|---|---|---|---|
| `ROOM_J` (−0.15, −0.50) | `basinStand`, `basinJug` (the stand centre is 0.042 from the mark) | 0.021 | use STAND (−0.15, −0.46) for S06 too |
| walk `STAND` → `ROUND` | `lowTable` (the straight line crosses the table from x −0.20 to −0.25), bread, cup, lamp2 | 0.000 | add a waypoint (−0.15, −0.36) before ROUND: both legs then clear by ≥ 0.05 |
| walk `SELLER2` → `SELLER2_SIDE` | `table2` / `table2Tipped` back-right corner | 0.032 / 0.035 | SELLER2_SIDE → (0.57, −0.38) |

## 4. Looked at (phone camera = StoryDirector on a 1080 × 2340 portrait screen: dist and height × 2.26, vfov 60)

`jerusalem_preview_s02 … s13` with stand-in actors at the story's marks, `_phone(_set)`, `_front`, `_topdown`,
`_hidden` (tipped table, coins, open cages). Room shots S06-S12: the sloping side walls keep the bench and the kneeling
pair visible from yaw −30…−40. **S04 / S05: the crowd line (contract place, heads 0.23) stands between the camera
and the court and hides both tables and the sellers' lower bodies** (`jerusalem_preview_s04_crowd.png`). The `_s04` and
`_s05` previews show the court with `crowd` hidden. Recommendation for story.py: `prop("jerusalem/crowd", show=False)`
at S04 (the armature node hides all eight; the procession is over and the court is "quiet" in S13).

## 5. Sheet

Drawings (`design.json set.drawings`): hills, house (outside, P_OBL 0.35/0.5), room (inside, L51), table (cloth),
facade, palm, olive, awnings, ground plan, stall1 (table1 + cages), stall2 (table2 + chest), palms (palmsRoad),
supper (bread + cup). Named texels for everything thin or hidden. Prop anchors for the Characters role:
`design.json set.propAnchors` (towels → table:cloth (0.1695, 0.30114); basin, jug, cup → supper:clay (0.6055, 0.51222);
bread → supper:bread (0.5315, 0.47311); palm → palms:palmLeaf (0.5715, 0.40791)).

Set regions, best cell (make_sheet rule): smallest facade:gold 6.4 mm, supper:clay 6.4, stall1:wicker 6.8,
stall2:coins 6.8, room:sky 6.8, olive 7.0; all others 7.1-13.0 mm. No set slivers; every set constant UV on its region.
Final slots (unchanged from CONTRACT §2, also in `regions_characters.json`): donkey −0.32 / 0.015 (side view),
jesus 0.0 / 0.015, peter 0.32 / 0.015. Title 服侍人的王: box 86, gap 60, cy 110 (worst title-band NCC 0.412 against
Real Miracles, 0.407 Daniel; bar < 0.6). `print/lastsupper-A4.pdf` and `-colored.pdf`: 210.0 × 297.0 mm, markers
0 px from the blank.

**Sheet check: FAIL on the cast only** — 7 anchors in `regions_characters.json` point at paper (old set UVs):
`jesus.towel`, `peter.towel` (0.15025, 0.34006), `jesus.basin`, `jesus.cup`, `peter.jug` (0.47075, 0.48513),
`jesus.bread` (0.42075, 0.46597), `peter.palm` (0.84725, 0.38325; its target is a list, the wrapper takes the first).
The Characters role re-reads `set.propAnchors`, rebuilds, then the sheet is run again. Cast regions under 6 mm are in
`assets/lastsupper/sheet/checks.json` (hair, tail, mane, belt, blanket, faces).

## 6. Weak or unverified

- No device or Unity check: the crowd's skinned sway and the hidden-prop swaps are verified in Blender only.
- The house drawing shows two blank paper holes (the room floor and the window seen from outside), as in Real Miracles.
- Room cushions and bench cushions take the awning red (no printed cushion region ≥ 6 mm).
- Stand-in actors are cylinders; real clips (kneel, ride) may reach further than the mark radii assume.
