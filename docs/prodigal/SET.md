# The prodigal son: home and the far country (Set role)

A tabletop stage on the colouring sheet, back to front: a low backdrop (far green Galilean hills on the left, a far
tawny headland on the right with the sea in front of it, a sailing boat and a little white town; near green hills with
six cypresses and five olive trees; near dry hills; the valley between them where the road goes away); the farmhouse
(limestone, wall 0.20, quoins and stone courses printed as lines, a string course, four small windows with wooden
lattices, beam ends, a flat roof with a parapet, jars and a reed booth on the roof, an outside stair up the east side,
an arched stone door frame and step, the wooden `door`, a grapevine with two grape bunches on a pergola over the door);
the courtyard (paving with flagstone lines, the round `well` with a windlass, rope and bucket, the `figTree`, dry-stone
walls with capstones on the west and along the back only, five storage jars, a bench, a clay oven); the field (planted
furrows with young wheat behind the bare hoeing strip); the pale `road` with wheel ruts and its branch to the tavern;
the far-country `tavern` (a marble stoa on a platform with a painted band, a pediment with terracotta coping, two
fluted Doric columns, an architrave with triglyphs, a red and white striped awning with a scalloped valance on two
poles, two tables with cups and stools, four amphorae, a market stall with oranges and melons under a yellow canopy,
bunting on two cords); the `pigpen` (rough fence with two rails, mud puddles, a trough with a heap of carob `pods`, a
straw heap) with four round `pigs` that root, twitch their tails and trot (`pigsWiggle`); hidden `feast` and `lamps`.
Same Paper & Crayon family as Exodus and Ruth; original design. Binding brief: `CONTRACT.md` §6; look: `DESIGN.md`.

| What | Where |
|---|---|
| Script | `pipeline/pr_homeland.py` (Blender 5.2, headless; Exodus's `ex_egypt.py` machinery, new builders) |
| Model | `assets/prodigal/model/homeland.glb` (+ `homeland.blend`, region materials, for inspection only) |
| Previews | `assets/prodigal/model/homeland_preview_{phone,phone_set,phone_low,front,orbit,home,tavern,pigpen,run,night,night_front,night_phone,back,topdown}.png` |
| Sheet | `tools/story/sheet_prodigal.py` (runs the shared `make_sheet.py` unchanged) -> `assets/prodigal/sheet/`, `print/prodigal-A4.{png,pdf}` |
| Data | `assets/prodigal/design.json` -> `set` (+ `sheet`, `lines`, `characters.<id>.sheetX/sheetY`) |
| Work files | `$PR_WORK` (default `/tmp/pr_set_work`): close-ups (`close_*.png`), pig loop frames (`pigs_f01/25/49/73.png`), drawings quick-look |

## Rebuild

```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python pipeline/pr_homeland.py -- all
STORY_WORK=/tmp/pr_set_work/story python3 tools/story/sheet_prodigal.py                       # sheet + checks + print
STORY_WORK=/tmp/pr_set_work/story /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
    --python tools/story/sheet_prodigal.py -- render                                          # textured_*.png
```

`all` = build + preview + verify (about 35 s); `check` builds in memory and prints the checks only. The build prints
`HOMELAND_TRIS`, `LAYOUT`, `BBOXES`, `CLEARANCE` (must be `OK`), `CLEARANCE_SOFT` (reported only), `FEAST_TABLE`,
`CHAR_PLACES`, `BUDGET`; verify prints `PIGS … loopError` and `VERIFY PASS`. Never hand-edit the GLB. Order after any
change: `pr_characters.py` -> `pr_homeland.py` -> `sheet_prodigal.py`. Until Integration adds `prodigal` to
`assets/stories.json`, the wrapper uses a stand-in registry entry (set `homeland`, cast son / father / brother) and
adds the story scene `textured_hug` (S09: father and son meeting on the road, the brother in the field).

## Coordinates and nodes

Design / glTF `(x, h, z)`: art-width units, page = XZ plane at h 0, +z toward the viewer, z 0 = art rect's bottom edge.
Blender builds `(x, -z, h)`; `export_yup` converts back. Root `homeland` has no transform.

```
homeland                      root, identity
├ ground                      grass (home, left) / earth (far country, right) + tufts, flowers, scrub, pebbles, stones
├ backdrop                    far hills 0.24-0.30 high, sea strip (top 0.172), near hills, trees, town, boat
├ house                       footprint x -0.52…-0.24, z -0.55…-0.39, wall 0.20 (parapet 0.213), stair x -0.240…-0.205
│ ├ door                      origin = hinge (-0.355, 0, -0.3815); panel front z -0.378, 0.050 wide, top 0.093
│ └ roofBooth                 reed booth on the roof (top 0.254)
├ courtyard                   paving x -0.545…-0.08, z -0.39…0.02 (flat, h 0.0036)
│ ├ well                      (-0.46, -0.04), r 0.040, rim 0.042, windlass 0.110
│ ├ figTree                   (-0.50, -0.28), crown 0.12…0.29
│ └ yard                      west wall (x -0.556…-0.530), back wall (x -0.203…-0.072, z -0.390…-0.364), h 0.03; jars, bench (-0.46, -0.32), oven (-0.505, -0.125)
├ field                       x -0.06…0.24, z -0.52…-0.28; wheat rows behind z -0.402 (blades <= 0.049), hoeing strip flat
├ road                        flat (h 0.003), main road to the front edge + branch to the tavern
├ tavern                      platform x 0.255…0.545, z -0.535…-0.395; columns at x 0.31 / 0.49, z -0.418; stall (0.54, -0.32)
├ pigpen                      fence round x 0.26…0.56, z -0.06…0.18 (h 0.058), mud, trough (0.48, 0.10), straw
│ └ pods                      heap of carob pods on the trough (origin (0.48, 0, 0.10))
├ pigs                        armature; action pigsWiggle (4 s, 24 fps, frame 1 == frame 97)
│ └ pigBodies                 four skinned pigs
├ feast                       table centre (-0.42, -0.215), 0.18 x 0.065, top 0.034; hidden at start
└ lamps                       hidden at start
  └ lampsFlame, lampsFlame2 … lampsFlame8      empties at the 8 flame points (no mesh)
```

**Confirmed for Effects (coordinator's request, 2026-11-14):**
- Under the hidden `lamps` node there is one empty per flame point, named `lampsFlame`, `lampsFlame2` … `lampsFlame8`
  (all start with `lampsFlame`, no mesh): three oil lamps on the feast table (h 0.041), two lanterns hanging from the
  pergola by the door (h 0.0975, z -0.364) and three lanterns on a cord from the pergola to the fig tree (h 0.10-0.12).
  Positions: `design.json set.nodes.lampsFlame`.
- The tavern awning's front edge stays clear for `party_lights`: x 0.262…0.538 at z -0.365, h 0.168 (valance tongues
  hang to h 0.148; poles at x 0.266 / 0.534). Bunting does **not** run along it; it hangs from the left pole to a mast
  at (0.232, -0.300) and from the right pole to the stall canopy. `design.json set.footprints.awningFrontEdge`.
- Other nodes Effects may use: `tavern` (centre (0.40, 0, -0.47)), `house` (centre (-0.38, 0, -0.47); for
  `music_notes`), `pods` (the son's `hungry_look` target).

`design.json set.hiddenAtStart` = `feast lamps`. `pods` is shown at rest.

### Pigs and `pigsWiggle`

Four round pigs (barrel body, round head, snout disc with nostrils, floppy ears, four legs, curly tail; ~0.07 long,
0.048 high): two eating at the trough ((0.462, 0.048) facing +z, (0.445, 0.140)), one rooting in the mud at
(0.452, -0.022), and pig 4 trotting a clockwise circle of r 0.017 round (0.522, 0.020) once per loop (legs in diagonal
pairs, 4 steps a second). Bones: `pigs_root`, `pig1…pig4` (body), `pigN_head`, `pigN_tail`, `pig4_legFL/FR/BL/BR`. Every
motion is a whole number of cycles per 4 s: loop error 0.0 (verify re-imports the GLB and compares frame 1 with frame
97). The clearance test runs on the evaluated pigs at eight frames of the loop.

## Marks and clearance

`CLEARANCE OK` = no set geometry between h 0.012 and 0.17 within 0.05 of any CONTRACT §6 mark or of the straight path
between consecutive marks of one actor (from `timeline.json`), overhead parts (fig crown, awning, roofs) 0.17-0.40 at
least 0.035 from a walk line. `feast` and `lamps` are tested against every stand and move made while they are shown
(from S11). The feast table keeps **0.063** from the S11 marks (-0.32, -0.12) and (-0.22, -0.10) (>= 0.06 required).
Nothing is exempt. `CLEARANCE_SOFT` (reported only): the first placements from the printed places (`start father`,
`start brother`) cross a few ground tufts; in the timeline both are `t = 0` placements, not walks.

**Deviations from CONTRACT §6, forced by its own clearance rule:**
1. **Feast table** centre (-0.42, -0.215) instead of (-0.38, -0.16): a 0.20 x 0.07 table at (-0.38, -0.16) reaches x
   -0.28 and z -0.125, i.e. onto the son's S11 mark (-0.32, -0.12). It is 0.18 x 0.065 now, under the fig tree's crown.
2. **Pig pen gaps**: the north-west corner is open. The son's strut (0.16, 0.06) -> (0.32, -0.26) passes 0.036 from the
   corner post (0.26, -0.06), and his walk (0.32, -0.26) -> (0.34, 0.04) needs the north fence at x <= 0.283 or >= 0.383.
   Posts are dropped automatically where they would come within 0.058 of a mark or path, so the west side starts at
   z ≈ 0.0 and the north side at x 0.40 (gate post). West gap z 0.05…0.16 as asked (gate posts at 0.045 / 0.165).
3. **Door**: the stone frame stands proud of the wall to z -0.367; the door panel's front face is z -0.378 (≈ -0.37).
4. The courtyard paving reaches the house front (z -0.39) so there is no strip of grass at the door.

## Triangles

**46,401 at build / 70,000 target** (the re-imported GLB counts 45,309): ground 7.7k, tavern 8.0k (with stall,
awning, bunting), house 5.8k (+ door 0.2k, booth 0.1k), backdrop 4.9k, pigs 3.4k, yard pieces 3.0k, fig tree 2.9k,
field 2.5k, feast 2.1k, pen 1.8k (+ pods 1.1k), lamps 1.5k, well 0.7k, road 0.7k (`design.json set.pieces[].tris`).
There is room left (~24k) if the owner wants more detail.

## UV0 = the colouring sheet

As Exodus (`docs/exodus/SET.md`): each piece belongs to one drawing (a linear view rendered by the script as line art);
faces edge-on to their drawing or facing away (n . D < 0.22) take one clean texel of their own region (LESSONS L51,
so no back face prints the front drawing); parts too small to colour take named texels (`CONSTS`, forced by
`FORCE_NR`; `set_id_2x.json constUV`, checked by the sheet tool). New here: **packed drawings** (`pack()`): in the
yard, tavern, pen and feast drawings the parts are drawn side by side (their drawing position P is shifted) so nothing
hides behind anything else: e.g. the awning is drawn next to the stoa, not over the tables, and the house's roof booth
next to the house. The jars and the four pigs are instanced and wear one drawing each.

| Drawing | View | Scale | bbox on the sheet (x0, ys0, x1, ys1) | Pieces |
|---|---|---|---|---|
| backdrop | front | 1.78 | -0.477, 1.030, 0.197, 1.206 | backdrop |
| fig | front | 1.55 | 0.237, 1.020, 0.363, 1.204 | figTree |
| pig | front (the pig's side) | 0.76 | 0.377, 1.110, 0.483, 1.173 | pigBodies (4 instances) |
| house | oblique (kx 0.30, k 0.42) | 1.25 | -0.483, 0.700, -0.111, 0.941 | house, door, roofBooth |
| tavern | oblique (kx 0.30, k 0.42), packed | 1.97 | -0.097, 0.725, 0.245, 0.944 | tavern (stoa, awning, tables, amphora, stall) |
| yard | oblique (kx 0.30, k 0.42), packed | 1.50 | 0.258, 0.700, 0.482, 0.876 | well, yard (walls, jar, bench, oven) |
| ground | plan | 3.50 | -0.481, 0.410, -0.139, 0.638 | ground, courtyard, road, field |
| pen | oblique (kx 0.10, k 0.55), packed | 1.60 | -0.123, 0.410, 0.183, 0.613 | pigpen (fence, trough, straw, mud), pods |
| feast | oblique (kx 0.10, k 0.55), packed | 0.85 | 0.245, 0.420, 0.465, 0.608 | feast (table + food, cushions) |

Named texels: home tufts -> fig:figLeaf; dry scrub -> backdrop:olive; pebbles -> yard:well; stones -> yard:wallStone;
flowers -> tavern:stallCloth / feast:cushion; wheat blades -> ground:wheat; the town and its dome -> tavern:marble;
boat hull -> house:door; door ring and pig eyes -> tavern:windowDark (the tavern doorway); figs -> feast:food; well
rope, bunting and lantern cords -> pen:straw; bunting flags -> feast:cushion, tavern:stallCloth, backdrop:sea,
fig:figLeaf; awning poles, mast, stools, table legs -> pen:trough; tavern and feast cups, lantern glass ->
tavern:stallCloth; fruit -> tavern:amphora; melons -> fig:figLeaf; pediment coping -> tavern:amphora; loose pods ->
pen:pods; oil lamps -> feast:dish; lantern frames -> tavern:windowDark (all `lamps` are named texels: it is never
printed). Printed as single lines (decorOnly): stone courses and quoins, flagstones, furrows, hoed clods, wheel ruts,
platform slabs, meander, triglyphs, mud ripples, sea glints.

## Colouring sheet

Page 1240 x 1754 @150 dpi, four markers, art rect [120, 283, 1000, 1227], 田字格 title 浪子回家 / làng zǐ huí jiā /
The Son Who Came Home (STORY.md), footer 浪子的比喻 · The Prodigal Son. Figures at the bottom at the places in
`design.json characters` (father -0.33, son 0.0, brother 0.33, sheetY 0.015; the Characters role's
`regions_characters.json` agrees), the set drawings above them.

Status 2026-11-14 (against the Characters role's 20:19 files): **SHEET PASS**, anchors **37 / 37**, no set slivers, no
set drawing over a figure, no ink on the art-rect edge, layout OK.

Title band (`tools/make_sheet_signatures.py` `signature()`, computed without writing the Unity file): most similar
other title david-goliath-A4 at **NCC 0.63**, then exodus-A4 0.53, wrath-p1 0.50, ruth-A4 0.48, esther-A4 0.44 (a
true match is about 0.9; Exodus's worst was 0.73). `prodigal-A4` is **not** in
`unity/Assets/DoodLive/Resources/sheet_signatures.json`: Integration runs `make_sheet_signatures.py` after adding the
story to `assets/stories.json`.

## Demo colours

`design.json set.demoColours`, from `DESIGN.md` (house #E3D3B0 / door #8A5A3B / roof #C9A77A, paving #D9C29A, well
#A9A49A, fig #5E9A4A, soil #9A6A43, wheat #B7C25A, hills #A7C26A / #D9B77A, tavern #F1EADB, awning #D2483A / #F6F0E2,
fence #9B6B43, mud #7A5638, pigs #F2A7A0, pods #6B4426, road #E9D9B6), plus: grass #A9C46C, earth #D8B98A, sea
#4E9CC9, cypress #3F6E43, olive #8FA876, vine #5E9A4A, grapes #6B3F7A, wall stone #BFB49E, oven #C9875A, painted
band #3E6FB0, stall cloth #F2C230, snout #E07F86, cushions #D2483A / #3E6FB0, table #8A5A3B, cloth #FBF8EF.

## Previews

`phone` (S01 stand-ins: father at his door, son lazing, brother in the field), `phone_set`, `phone_low`, `front`,
`orbit`, `home` (courtyard), `tavern` (dusk), `pigpen`, `run` (S09 meeting, dusk), `night` and `night_front` (S11:
feast + lamps shown, preview-only flames and lamp light), `night_phone`, `back` (back faces plain), `topdown`. The
figures in the previews are stand-ins; `assets/prodigal/sheet/textured_*.png` show the real characters wearing the demo
colouring (`textured_hug` = the story scene).

## Known rough points

1. Packed drawings: the tavern's awning, tables, amphora and stall are coloured as separate pieces on the sheet (a
   child colours the awning stripes beside the building, not over it). Same idea for the pen (fence / mud / trough) and
   the yard (walls / well / jar / bench / oven).
2. Many small things are named texels and take a colour from elsewhere on the sheet (list above): e.g. figs take the
   feast food's colour, the oil lamps the feast dish's.
3. The pigs are big for "small background animals" (~0.07 long next to the 0.34 son) and crowd the trough; the
   trotter passes 0.007 from pig 1.
4. The sea's left end slopes down behind the near dry hills (a cliff coast); from far left orbits the valley between
   the far panels is 0.19-0.20 high, so a sliver of the page beyond can show there.
5. The courtyard is a big open paved space on purpose (the actors' marks and walks); only low things stand in it.
6. Not yet seen in Unity with DGPaperLit, a real scan, `pigsWiggle` playing in the engine, or the Effects.
