# Jonah: the coast (Set + sheet role)

One tabletop page, three places. **Left**, the sea: two blues with printed wave marks, curling wave crests in the
back water, a white foam line at the shore and round the hull, all skinned to a bone grid that bobs (`seaWave`).
On it, back-left, the merchant **ship**: a round clinker-planked hull with a plank deck, a high stern post that curls
inboard, the steering oar, one mast at the back rail with a furled cream sail with two red stripes on its yard, a rope
ladder, stays, rope rails on posts, `cargo` (sacks and storage jars), and a gentle roll (`shipRock`). **Middle front**,
the beach: rippled sand that runs under the water, shells, two mooring posts in the shallows roped to the bow, a rope
coil, a rowing boat pulled up, and the `plank` from a stone on the sand up to the bow. **Right**, Nineveh: a
mud-brick wall on a stone plinth with stepped merlons, a corner tower, the `gate` (two towers, an arch ringed with
alternating lapis and gold blocks, bronze-banded doors), flat-roofed houses and a stepped temple behind, two date
palms; the pale road along the front with a branch and a small plaza at the gate; Jonah's low `hill` with rocks and
dry grass. Hidden props: `shelter`, `plantSmall` / `plantBig` / `plantDry` (one gourd vine in three states), `worm`,
`belly`. Binding brief: `CONTRACT.md` §6; look: `DESIGN.md` §2-4.

| What | Where |
|---|---|
| Script | `pipeline/jn_coast.py` (Blender 5.2, headless, on `story_kit/stage.py`) |
| Model | `assets/jonah/model/coast.glb` (+ `coast.blend`, region materials, for inspection only) |
| Previews | `assets/jonah/model/coast_preview_{phone_set,phone,phone_low,front,ship,city,beach,hill,hill_dry,belly,topdown}.png` |
| Set drawings | `assets/jonah/model/set_id_2x.png/.json` |
| Sheet | `tools/story/sheet_jonah.py` (wraps `make_sheet.py`, unchanged) → `assets/jonah/sheet/`, `print/jonah-A4.{png,pdf}`; `tools/story/make_colored_pdf.py jonah` → `print/jonah-A4-colored.pdf` |
| Data | `assets/jonah/design.json` → `set` (+ `sheet`, `lines`, `characters` slots) |

## Rebuild

```
nice -n 10 blender -b --factory-startup --python pipeline/jn_coast.py -- all      # build + previews + verify, ~35 s
python3 tools/story/sheet_jonah.py                                                # sheet + checks.json + print/
python3 tools/story/make_colored_pdf.py jonah
python3 tools/story/sheet_jonah.py signature                                      # title band vs every other sheet
```

`build` prints `COAST_TRIS`, `LAYOUT`, `BBOXES`, `CLEARANCE` (must be `OK`), `CLEARANCE_SOFT` (timeline walks that are
not contract walks, reported), `CLEARANCE_MIN` (nearest geometry per mark / walk) and `MARK_GROUND_H`. Rerun the set
script whenever the Characters role moves a figure (`regions_characters.json`), then the sheet. `sheet_jonah.py`
needs a stand-in registry entry until Integration adds `jonah` to `assets/stories.json` (it builds one from
design.json). It also prints part-anchored cast pieces as detail lines (as `sheet_daniel.py`).

## Nodes (root `coast`, glTF x, h, z)

| Node | Where / what |
|---|---|
| `sea` | armature at (−0.27, 0, −0.19), 30 bones on a 6 × 5 grid; children `seaWater` (surface x −0.60…0.06, all z, h ≈ 0.0045 ± 0.0012), `seaCrests` (22 crests, one template, 0.026–0.035 high, back water only), `seaFoam` (shore line + hull ring). Action **`seaWave`**: 4 s at 24 fps, frame 1 = 97, bones bob ≤ 3.2 mm (less near the shore) |
| `ship` | pivot (−0.34, 0.10, −0.22) = deck centre; hull x −0.535…−0.148 at the deck (the bow foot rakes 2.4 cm ahead under the plank), half beam 0.070; deck 0.100; gunwale lip 0.107 in the waist (rises to 0.16 at the stern, drops to 0.100 at the bow where the plank lands); mast foot (−0.405, −0.292) on the back rail, truck 0.455, pennant ≤ 0.459; yard 0.436, x −0.566…−0.334, sail hangs *behind* the mast; stern post to 0.268; oar loom top (−0.487, 0.205, −0.166). Action **`shipRock`**: 6 s at 24 fps, roll ±3.0° about the deck's long axis + pitch ±0.6°, frame 1 = 145 |
| `cargo` | child of `ship`: sacks (−0.327, −0.176), (−0.360, −0.172), (−0.504, −0.249); jars (−0.500, −0.190), (−0.515, −0.215); top ≤ 0.148 |
| `plank` | foot (0.08, 0.02, −0.20) on a stone, top (−0.165, 0.10, −0.22) on the deck; 5.2 cm wide, cleats |
| `beach` | sand x 0.03…≈0.22 (wavy edge), under the water at x < 0.06; children `boat` (0.128, −0.405), `beachProps` (posts (0.028, −0.272), (0.026, −0.128), ropes to the bow, coil, shells) |
| `road` | front road from (0.60, 0.18) to the beach (0.13, 0.10); branch from (0.23, 0.13) to the gate; plaza x 0.23…0.45, z −0.39…−0.27 |
| `ground` | the earth (sage) east of the beach |
| `hill` | mound centre (0.44, 0.06), radius 0.14, top 0.028 (+ ground 0.005); child `hillProps` (9 rocks, 34 dry-grass tufts) |
| `nineveh` | origin (0.40, 0, −0.40); wall front z −0.40, x 0.20…0.60, plinth 0.062, wall top 0.205, merlons to 0.229; right tower to 0.269; houses and temple behind (z −0.46…−0.586), top ≤ 0.299; palms (0.226, −0.576), (0.574, −0.482) |
| `gate` | child of `nineveh`, origin (0.34, 0, −0.40); gatehouse x 0.23…0.45, front z −0.378; arch opening 0.10 × 0.16; band of 2 jamb + 3 voussoir blocks (lapis / gold); towers to 0.289 |
| `shelter` | origin (0.52, 0, 0.02); poles (0.478, 0.050), (0.586, 0.048) to 0.27, cross-stick, cloth pegged at z ≈ −0.165 (a lean-to open to the viewer) |
| `plantSmall` `plantBig` `plantDry` | origin (0.34, 0, 0.06) (root on the hill). `plantBig`: crown x 0.30…0.50, leaves 0.31…0.432, gourds' bottoms ≈ 0.28; `plantDry`: same vine kept high (≥ 0.40 over the seat), limp leaves on the left, one shrivelled gourd at the tip, top 0.437 |
| `worm` | on the `plantBig` stem at h ≈ 0.14–0.25 (origin at its body), face toward the viewer |
| `belly` | centre (−0.20, 0, 0.08), inner radius 0.13, height 0.26 (superellipse profile: ≥ 0.255 within 0.05 of the centre), open over 120° toward +z (mouth arch up to ≈ 0.21), 5 wide ribs inside and out, floor disc at 0.0115 |

`hiddenAtStart` in design.json: shelter, plantSmall, plantBig, plantDry, worm, belly.

## Marks and clearances (measured)

Rule (CONTRACT §6, as Ruth): relative to the walker's floor y, nothing in y + 0.012…0.17 within 0.05 of a mark or
straight walk; y + 0.17…0.40 needs 0.035 (a head); higher is ignored. Walking surfaces (beach, road, ground, hill,
water, plank) do not count. Moving parts are tested at their extremes (crests and foam at 8 frames of `seaWave`, ship
and cargo at ±3° roll: the masthead swings 1.8 cm). Result: **`CLEARANCE OK`**. Nearest [low, overhead]:

| Mark / walk | nearest | Mark / walk | nearest |
|---|---|---|---|
| jonah road (0.28, 0.14) | 0.055 / — | captain deck (−0.44, −0.22) y 0.10 | 0.052 / 0.052 |
| jonah beach (0.12, 0.10) | 0.19 / — | captain deck2 (−0.36, −0.24) y 0.10 | 0.052 / 0.039 |
| plank foot (0.08, −0.20) y 0.02 | 0.078 / — | walk captain deck > deck2 | 0.051 / 0.037 |
| plank top (−0.16, −0.22) y 0.10 | 0.058 / 0.187 | jonah gate (0.32, −0.16) (moved 2026-11-15) | 0.119 / 0.214 |
| jonah deck (−0.26, −0.22) y 0.10 | 0.062 / 0.098 | jonah hill (0.42, 0.08), shelter shown | 0.053 / 0.055 |
| jonah cargo (−0.30, −0.26) y 0.10 | 0.061 / 0.042 | walk gate > hill, shelter shown | 0.053 / 0.050 |
| jonah rail (−0.22, −0.16) y 0.10 | 0.068 / 0.168 | hill seated, S11 plantSmall/Big/worm (head top 0.27) | 0.053 / 0.055 |
| walk jonah plank > deck | 0.051 / 0.098 | hill standing, S11-S12 plantDry | 0.053 / **0.035** |
| walks deck > cargo > rail | 0.055 / 0.042 | belly (−0.20, 0.08), sitting back on the heels (head top 0.249; was 0.279 kneeling upright, through the dome) | 0.109 / 0.063 |

Fish lane (x −0.60…0.02, z −0.06…0.21): nothing of the set but the water (the crests, posts, hull and foam all stay
out; `belly` is hidden while the fish swims). Ground height at the marks: road 0.005, beach 0.004, gate 0.005,
**hill 0.030** (see deviations).

## Deviations from CONTRACT §6 (all forced by its own clearance rule or by the timeline)

1. **Cargo is in front of Jonah's sleeping place, not behind it.** CONTRACT puts it round (−0.30, −0.29), 3 cm behind
   the CARGO mark (−0.30, −0.26); the hull's back edge is z −0.29, so nothing there can be 0.05 clear. The sacks now
   stand between the mark and the viewer (z ≈ −0.175), which is what `story.py` says ("behind the cargo sacks"),
   plus a stern group. The low sacks do not hide a lying Jonah from the phone's height.
2. **The mast stands on the back rail** (−0.405, −0.292), its yard and sail hang behind it. It is the only place clear
   of the captain's walk (−0.44, −0.22) → (−0.36, −0.24) and Jonah's deck marks (including the 1.8 cm sway of the
   roll). The yard is longer aft (to x −0.566) and stops at x −0.334 on Jonah's side.
3. **No forestay**: any stay to the bow crosses Jonah's walk to the rail at chest height.
4. **Gunwale lip only 7 mm** in the waist (0.107): the rail mark (−0.22, −0.16) is 1 cm from the hull side, and the
   roll lifts the side 3.5 mm. Rope rails on posts stand only where they are 0.056 clear of every deck mark and walk.
5. **Nineveh's wall starts at x 0.20, not 0.10**, so the rowing boat at (0.14, −0.40) lies on the sand beside it.
   The hill keeps its centre and radius; the front road runs over its front foot.
6. **Shelter** is a lean-to beside the seat (poles 0.06 from the mark), not over it; the plant shades Jonah.

## The sheet

Slots (design.json `characters`, unchanged from CONTRACT §2): jonah (−0.32, 0.015), captain (0.32, 0.015), fish
(0.0, 0.40) side view on the second row. Ten set drawings around them:

| Drawing | View | Scale | Sheet bbox | Members |
|---|---|---|---|---|
| ship | front-above (k 0.5) | 1.03 | x −0.479…−0.031, y 0.638…1.170 | ship (hull, deck, sail + stripes, mast, oar, stern post) |
| city | front-above (k 0.55) | 1.35 | 0.140…0.440, 0.900…1.192 | nineveh, gate |
| ground | plan | 3.20 | 0.103…0.478, 0.636…0.885 | seaWater, beach, road, ground, hill |
| sack | front-above | 0.75 | −0.002…0.078, 0.650…0.760 | template of every cargo sack |
| plantBig | front-above (k 0.35) | 1.27 | −0.477…−0.277, 0.394…0.530 | crown only (the stem below is a named texel) |
| belly | front-above (k 0.45) | 1.80 | 0.293…0.457, 0.414…0.622 | belly |
| plantDry | front-above (k 0.35) | 1.46 | −0.167…0.007, 0.012…0.212 | crown |
| plantSmall | front | 0.62 | −0.147…−0.021, 0.232…0.303 | sprout |
| shelter | front-above (k 0.8) | 0.95 | 0.026…0.150, 0.012…0.099 | cloth + patches |
| wave | front | 0.70 | 0.024…0.152, 0.200…0.293 | template of every crest |

Named texels (no printed shape): rigging, ladder, rails, rope, posts, sticks, stems, tendrils, palms → wood / leaf;
foam line, shells → wave foam; rocks → city stone; dry grass → plantDry dry; boat → ship hull / deck; jars → city roof
(clay); worm → plantSmall leaf + belly floor (eyes, smile). Printed detail lines are kept sparse (brick clusters, one
wale on the hull, sand ripples, wave marks, door planks and bronze bands, patch stitches) so every region keeps a
clean cell.

Checks (`assets/jonah/sheet/checks.json`): **every set region ≥ 6 mm** (31 set regions; smallest best cell 36 px =
6.1 mm: city roof, wave, wave foam); no set slivers; set over cast 0 px; ink 6 mm from every page edge. Title band:
box 74 / gap 28 / cy 108 (`sheet_jonah.py title-search`), most similar other sheet Daniel, NCC 0.35 (bar < 0.6;
checked on a copy, Integration owns `sheet_signatures.json`). `print/jonah-A4.pdf` and `-colored.pdf` are A4, markers
where the blank has them. Cast regions under 6 mm and the one failing cast anchor (`jonah.sandals`) belong to the
Characters role (RIG.md).

## Budget

50,077 triangles at build (49,949 in the re-imported GLB) of 60,000: water 7.1k, crests 13.0k, ship 7.7k, cargo
1.6k, land 5.9k, city 3.1k, props and hidden props the rest. No UV outside 0–1 (`verify`).

## Weak or unverified

- The timeline's walk from the beach (0.12, 0.10) straight to the deck (−0.26, −0.22) does not follow the plank: it
  crosses the bow's side at deck height (`CLEARANCE_SOFT`). It needs two waypoints, the plank foot (0.08, −0.20) and
  top (−0.16, −0.22), in `story.py` (lead).
- The hill is 0.030 high at Jonah's mark: give `HILL` y ≈ 0.03 in `story.py`, or seated clips sink 3 cm.
- `plantDry` over the seat leaves exactly 0.035 to a standing Jonah's head (S12 `look_city`); if his head is taller
  than 0.39 there, hide `plantDry` before `look_city`.
- Not seen on the phone; no Unity import. The hull reads as a tub more than a ship from straight in front (the bow
  cannot rise: the plank lands there).

## Round 3 (2026-11-15): the people of Nineveh

Nine new hidden nodes `folk1`…`folk9` (`FOLK` in `jn_coast.py`): simple kneeling figures, sackcloth robe and hood,
face, hands together, shut eyes; `folk2` wears a gold crown (the king), `folk6` / `folk7` are children (scale 0.68 /
0.70). All faces are named texels (robe = `sack` drawing / sack, face = shelter / patch, eyes = belly / bellyFloor,
crown = city / gold), so the colouring sheet is unchanged (sheet PNGs and `print/jonah-A4.png` byte-identical after
`sheet_jonah.py`, SHEET PASS). +7.3k triangles: 57,343 at build (57,215 re-imported) of 60,000. Clearance with them
shown: Jonah's gate mark 0.08 / 0.137; new mark `jonah gate side` (0.16, −0.10) 0.126 / 0.286 (S09: he steps aside
so they are not hidden behind him). `CLEARANCE OK`, `VERIFY PASS`. Unity must re-import `coast.glb` (new nodes).
