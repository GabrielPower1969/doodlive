# Real Miracles: Galilee (Set + sheet role)

One tabletop page, two places. **Left**: Peter's house in Capernaum, built like a doll's house (front cut away to a
1 cm sill), a reed-mat floor, two benches in the back corners, two water jars, a ledge with an oil lamp, three ceiling
beams, a back window, a side door in the right wall (leaf swung open into the yard), a flat walkable roof (top y 0.40)
with a parapet on the back and the right side, and the outside `stair` up the left wall. **Middle**: the packed-earth
`yard` with `figTree` and `olivePress`, the pale `road`, the townsfolk `crowd1`…`crowd8`. **Right back**: the `lake`
(two blues, `lakeWave`), Peter's `boat` (`boatRock`) with the stern `cushion`, the pebble `beach` with reeds, the
far-shore `hills`. Binding brief: `CONTRACT.md` §6; look: `DESIGN.md` §2-3.

| What | Where |
|---|---|
| Script | `pipeline/mi_galilee.py` (Blender 5.x, headless, on `story_kit/stage.py`) |
| Model | `assets/miracles/model/galilee.glb` (+ `galilee.blend`, for inspection only) |
| Previews | `assets/miracles/model/galilee_preview_{phone_set,phone,front,room_s01b,room_s05,room_s06,room_s07,roof,roof_hole,stair,yard,boat,boat_s11,beach,topdown}.png` |
| Set drawings | `assets/miracles/model/set_id_2x.png/.json` |
| Sheet | `tools/story/sheet_miracles.py` (wraps `make_sheet.py`, unchanged) → `assets/miracles/sheet/`, `print/miracles-A4.{png,pdf}`; `tools/story/make_colored_pdf.py miracles` → `print/miracles-A4-colored.pdf` |
| Data | `assets/miracles/design.json` → `set` (+ `sheet`, `lines`, `characters` slots) |

## Rebuild

```
nice -n 10 blender -b --factory-startup --python pipeline/mi_galilee.py -- all     # build + previews + verify, ~35 s
python3 tools/story/sheet_miracles.py                                              # sheet + checks.json + print/
python3 tools/story/make_colored_pdf.py miracles
python3 tools/story/sheet_miracles.py signature                                    # title band vs every other sheet
blender -b --factory-startup --python tools/story/sheet_miracles.py -- render       # textured_*.png (optional look)
```

`make_sheet.py miracles` alone stops with `StopIteration`: `assets/stories.json` has no `miracles` entry until
Integration runs `merge_packs.py`. `sheet_miracles.py` uses a stand-in entry until then (as `sheet_jonah.py`).
Rerun the set script whenever the Characters role moves a figure or the mat, then the sheet.

## Nodes (root `galilee`, glTF x, h, z)

| Node | Where / what |
|---|---|
| `house` | origin (−0.246, 0, −0.4225). Room x −0.452…−0.040, z −0.560…−0.260; walls 0.026 (left outer −0.478, right outer −0.014, back −0.585…−0.560 to 0.43). Sill z −0.285…−0.260, h 0.010. Roof top 0.40, **underside 0.385** (see deviations), roof x −0.478…−0.014, z −0.585…−0.260. Parapet: back wall to 0.43, right side 0.020 wide to 0.43; none on the left (stair landing) or front. Side door x −0.04, z −0.45…−0.35, h 0.26. Window x −0.30…−0.18, y 0.17…0.29. Child `houseIn`: interior (floor, back wall inside, benches x −0.452…−0.385 and −0.115…−0.040 at z −0.56…−0.52 h 0.05, jars (−0.312, −0.540) (−0.268, −0.544), ledge x −0.14…−0.09 at y 0.20, beams at z −0.270 / −0.505 / −0.545, bottom 0.377) |
| `roofPatch` | child of `house`, (−0.24, 0.40, −0.38), 0.14 × 0.14, flush; shown at start |
| `roofHole` | child of `house`, same place: ragged hole 0.12 × 0.12, broken branch ends, dangling twigs to y 0.361; hidden at start |
| `rubble` | child of `house`, (−0.30, 0, −0.44), h ≤ 0.02; hidden at start |
| `stair` | x −0.580…−0.478, 10 steps from z −0.06 (first tread 0.02) to z −0.44 (0.40), landing z −0.585…−0.44 at 0.40. The front steps (in front of the house) have closed right sides |
| `crowd1`…`crowd4` | standing at the side door: (0.020, −0.425) h 0.285, (0.080, −0.410) 0.300, (0.040, −0.355) 0.260, (0.095, −0.330) 0.290, facing −X |
| `crowd5` `crowd6` | sitting inside on the benches: (−0.424, −0.546), (−0.062, −0.548), h 0.23 |
| `crowd7` `crowd8` | heads at the back window outside: (−0.268, −0.600), (−0.208, −0.602) |
| `yard` | x −0.04…0.20, z −0.50…−0.06; children `figTree` (0.16, −0.50), trunk r 0.021, crown bottom ≥ 0.20, top ≈ 0.36; `olivePress` (0.12, −0.22), r ≤ 0.04, h ≤ 0.06 |
| `road`, `ground` | road from (0.30, 0.21) to the yard, and along the front to the stair foot; `ground` = the rest of the floor |
| `lake` | armature at (0.37, 0, −0.354), bone grid; child `lakeWater` x 0.14…0.60 (the shore bends out to x 0.225 behind z −0.47, round the fig tree), z −0.5875…−0.12, surface 0.012. Action **`lakeWave`**: 4 s, 24 fps, max bob 2.5 mm, loop error 0 |
| `beach` | z −0.12…0.0 along the lake, pebbles, reeds at x 0.535…0.59 (≤ 0.058 high) |
| `boat` | pivot (0.36, 0.06, −0.34); hull x 0.158…0.562, half beam 0.070, deck 0.06; mast (0.218, −0.34) to 0.415; yard + furled sail lowered from the masthead toward the bow; steering oar at the stern; net coil in the bow; two oars on the deck. Child `cushion` (0.505, −0.34), top ≈ 0.10. Action **`boatRock`**: 6 s, 24 fps, roll ±3.08° measured, pitch ±0.5°, loop error 0 |
| `hills` | front face z −0.575, x 0.0…0.60, top 0.12-0.20 |

`hiddenAtStart` in design.json: `roofHole`, `rubble`. Only one of `roofPatch` / `roofHole` should be visible at a time
(the timeline swaps them in S05).

## Marks and clearances (measured, `-- check`)

Rule (CONTRACT §6): relative to the walker's floor y, nothing in y + 0.012…0.17 within 0.05 of a mark or straight walk;
y + 0.17…head top needs 0.035; inside the house the head top is the actor's own height. Walking surfaces (yard, road,
ground, beach, water, stair treads) do not count; the boat and cushion are tested at both roll extremes; hidden props
count in the scenes that show them. Every walk between consecutive marks in `timeline.json` is tested too.
Result: **`CLEARANCE OK`** for all 41 marks and 30 walks (the contract stair walk + 29 from `timeline.json`). Nearest geometry [low zone, overhead]:

| Mark / walk | nearest | Mark / walk | nearest |
|---|---|---|---|
| jesus teach (−0.36, −0.46) | 0.056 / 0.076 | stair (−0.53, −0.24) y 0.20 | 0.056 / 0.056 |
| jesus kneel (−0.34, −0.40) | 0.112 / 0.112 | stair walk foot > (−0.53, −0.40) | 0.052 / 0.052 |
| peter in (−0.12, −0.46) | 0.060 / 0.041 | R3 / R4 (roof) | 0.060 / — |
| LAND (−0.24, −0.38), hole + rubble shown | 0.148 / 0.046 | R2 / STAIR_TOP | 0.086 / 0.113 |
| YARD (0.02, −0.12) | 0.102 / 0.144 | deck (0.42, −0.34) | 0.057 / 0.195 |
| STAIR_FOOT (−0.53, −0.08) | 0.187 / 0.187 | BOAT_PETER (0.28, −0.32) | 0.058 / 0.058 |
| walk man (−0.40, −0.06) > (−0.53, −0.24) | 0.054 / 0.143 | BOAT_STERN (0.48, −0.34) (cushion 0.05 allowed) | 0.052 / 0.25 |
| walk jesus (0.42, −0.34) > (0.48, −0.34) | 0.051 / 0.195 | BOAT_WAKE (0.38, −0.32) | 0.081 / 0.156 |
| road / beach / front marks | ≥ 0.10 | **`lowered` shaft** r 0.10 round LAND, y 0.012…0.45 | nearest 0.106 (only the `roofHole` rim inside) |

Roof: nothing above 0.412 except the parapet. Headroom inside: ceiling 0.385, beams' bottom 0.377 (beams at z −0.505
and −0.545, ≥ 0.045 behind the indoor marks); Jesus 0.355 → 0.025 free, Peter 0.381 → 0.004 free, man 0.34.

**For the lead (story.py, not a set fault):** the stair is the contract's even ramp (y 0 at z −0.06 to 0.40 at
z −0.44), but the timeline eases y from the foot to `y=ROOF` already at z −0.40 / −0.36. Tread height under those
marks: (−0.53, −0.40) tread 0.34 vs timeline y 0.40; (−0.53, −0.36) 0.30 vs 0.40 (friend2); (−0.53, −0.24) 0.18 vs
0.20; (−0.53, −0.10) 0.06 vs 0.04. Actors float up to 0.10 above the steps there; putting the stair-top waypoints at
z −0.44 (or y = tread) fixes it.

## Sheet

Layout (sheet units, art width 1.0; `design.json set.drawings`): figures at the contract slots (man −0.32, Jesus 0.0,
Peter 0.32, sheetY 0.015, unchanged); the man's mat at its default place, now pinned as `characters.man.matSheet`
[−0.28, 0.47] (box −0.484…−0.076 × 0.395…0.545); `room` (scale 2.36) and the fig crown above the mat; `ground` plan
(scale 3.0) right of the mat; `house` (1.62) raised to y 0.785…1.212; `boat` (1.10, scaled round Peter's bucket
anchor so it still lands on the hull) and `hills` in the right column.

Measured (`assets/miracles/sheet/checks.json`): **SHEET PASS**; anchors 76 / 76 on their regions; no slivers; set
over cast 0 px; no region without a colourable cell; ink ≥ 42 px (7.1 mm) from every page edge; title band
`box 88 gap 32 cy 110`, most similar sheet daniel-A4 NCC 0.359 (**DISTINCT**, bar < 0.6). Both PDFs 210.0 × 297.0 mm,
the four markers within 0 px of the blank.

Set regions, largest inscribed circle per region (regions.png, before ink; checks.json, after ink, has none under 6 mm):
road 6.7, hull 6.8, beach 7.1, room floor 7.8, sail 8.0, lakeFar 8.4, cushion 8.4, deck 8.8, yard 9.1, door 10.2,
ground 12.2, fig 13.8, room wall 14.9, roof 17.3, hills 18.7, lake 19.3, walls 25.9 mm.
Cast regions under 6 mm (Characters role, as on every sheet): hair / beards of all three, Peter's head cloth and waist
cloth, Jesus' belt, the three faces, the man's sash.

Named texels (not printed; they take another region's colour): ceiling, jars, roof-hole mud, rubble mud → house roof;
beams, benches, twigs, fig trunk and limbs, olive-press beam, mast, oars, crowd hair → boat hull; reeds, flame → fig;
pebbles → hills; press stone → beach; net → sail; crowd robes / cloths / faces → the regions in `CROWD`.

## Budget

21,170 triangles at build (21,196 on the re-imported GLB) of 70,000; no UV outside 0-1 (verify). Largest: lakeWater
3,087, boat 2,168, ground 1,956, figTree 1,792, beach 1,434.

## Deviations from CONTRACT §6

- **Ceiling underside 0.385, not 0.37** (slab 0.015 thick, beams' bottom 0.377): Peter's model is 0.381 tall and
  his head went 1 cm into the ceiling in the low S05 / S07 views. The walkable roof stays at 0.40.
- **Mast at (0.218, −0.34), not (0.26, −0.34)**: at 0.26 it is 0.028 from `BOAT_PETER` (0.28, −0.32).
- Lake shore bends out to x 0.225 behind z −0.47 so the fig tree (0.16, −0.50) stands on the yard, not in the water.
- `crowd6` sits at (−0.062, −0.548), 0.018 right of the contract's (−0.08, −0.54) (inherited from the earlier run; Peter's
  mark keeps 0.060).
- No parapet on the roof's left edge (the stair landing and the walks onto the roof cross it).

## Weak / unverified

- Only stand-in mannequins in the previews; the real animated actors on the set are not checked (Unity, device).
- Peter has 0.004 headroom; a head-up clip (`roof_shock`) or hair volume may still touch the ceiling.
- The fig tree prints as a crown only (the trunk is too thin to colour and takes the hull colour).
- A 1.4 mm strip of `ground` at the plan's left edge (x −0.60…−0.58, beside the stair) is too thin to colour.
- Peter's bucket anchor sits 5 px from an ink line on the hull; if the Characters role re-runs, it re-picks it.
