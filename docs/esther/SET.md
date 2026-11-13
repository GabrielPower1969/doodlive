# Esther: the palace throne room (Set role)

A tabletop stage that stands on the colouring sheet: a three-step dais with a lion-footed throne, two fluted columns
with twin-bull capitals, crimson curtains tied back with gold cords (gentle looping sway), two bronze braziers for the
fire FX, a carpet runner, pale stone floor tiles, a low back wall with two winged guardians and glazed bricks, and a
banquet table that appears in S09. Same Paper & Crayon family as the David & Goliath desert; Achaemenid in feel,
original design. Binding brief: `CONTRACT.md` §6; look: `DESIGN.md`.

| What | Where |
|---|---|
| Script | `pipeline/es_palace.py` (Blender 5.2, headless) |
| Model | `assets/esther/model/palace.glb` (+ `palace.blend`, region materials, for inspection only) |
| Previews | `assets/esther/model/palace_preview_{phone,phone_set,front,orbit,banquet,topdown}.png` |
| Sheet | `tools/story/make_sheet.py esther` → `assets/esther/sheet/`, `print/esther-A4.*` |
| Data | `assets/esther/design.json` → `set` |
| Work files | `$ES_WORK` (default `/tmp/es_work`): close-ups, preview texture |

## Rebuild

```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python pipeline/es_palace.py -- all
```

`all` = build + preview + verify (about 40 s). `build` writes the GLB, the .blend, `model/set_id_2x.*` (set drawings for the sheet) and the `set`
key of design.json (other keys are kept); `verify` re-imports the GLB. `preview` needs a build in the same run.
The build prints `PALACE_TRIS`, `LAYOUT` (sheet drawings inside their zone, ≥ 0.012 apart) and `CLEARANCE` (nothing
above 6 mm-scale height near the actors' marks and paths). Never hand-edit the GLB: change the script and rerun.

## Coordinates and marks

Design / glTF `(x, h, z)`: art-width units, page = XZ plane at h 0, +z toward the viewer, z 0 = art rect's bottom
edge (as David & Goliath). Blender builds `(x, -z, h)`; `export_yup` converts back. Root `palace` has no transform.

| Mark | Value |
|---|---|
| `daisTop` | 0.07 (platform top; the king's base height) |
| throne seat | (0, −0.30); cushion top h **0.186**; seat front edge z −0.226; back panel front z −0.379 |
| foot of the steps | (0, −0.12); bottom riser at z −0.150 (toes reach it), risers −0.150 / −0.170 / −0.190 |
| table | (0.22, 0.08); footprint x 0.145…0.295, z 0.045…0.115, top h 0.049 |
| flames | `flameL` (−0.29, 0.148, −0.13), `flameR` (0.29, 0.148, −0.13) |
| columns / braziers | (±0.28, −0.43) / (±0.29, −0.13) |
| dais footprint | half-width 0.135 / 0.125 / 0.115, back z −0.50 (keeps Haman's whisper mark (0.16, −0.24) on the floor) |
| floor / wall | x ±0.60, z −0.5875…0.21 / wall front z −0.58, top of crenellations h 0.319 |

`CLEARANCE OK`: Esther's walk (−0.32, 0.18) → (−0.12, 0.12) → (0, −0.12), her banquet and wave marks, Haman's
marks and his walk to (0.16, −0.24) are clear (the table is ignored while it is hidden).

## Nodes (`palace.glb`)

```
palace                      root, identity
├ floor carpet dais throne columnL columnR brazierL brazierR wallRelief
├ flameL flameR             empties at the flame points (brazier_fire FX)
├ curtains                  armature (action curtainSway) → curtainL, curtainR (skinned), curtainRod (static)
└ table                     origin at (0.22, 0, 0.08), hidden until S09 → goblet1 goblet2 bowl bread
```

- Every mesh carries one material, `es_page` (bind the scanned art rect, as the characters).
- `throne` origin = seat mark on the dais top (0, 0.07, −0.30); columns and braziers at their base centres; `table`
  at its mark, so Integration can slide it in by moving one node.
- `curtainSway`: 4 s loop at 24 fps (frame 1 = frame 97). Upper drape swings ±2.6° about the rod, the part below the
  tie ±2.2° plus 1.4° sideways; left and right out of phase. Largest movement 0.013 at the hem. Bones:
  `curtain_root`, `curtainL_upper/lower`, `curtainR_upper/lower`.
- Triangles **36,537 / 40,000**: wall 5.7k, columns 5.1k each, throne 4.1k, curtains 3.5k each, dais 1.7k, floor
  1.8k, braziers 1.4k each, table + items 2.9k, carpet 0.2k (`design.json set.pieces[].tris`).

## UV0 = the colouring sheet

Each piece belongs to one *drawing* on the sheet: the piece seen in its projection, rendered by the script as line
art, so a child's colour lands on the surface behind it. `design.json set.drawings` holds scale / sheetX / sheetY /
bbox; `set.pieces[].frontUV` holds each piece's mapping.

| Kind | Formula | Used by |
|---|---|---|
| front | `u = m·x / scale + sheetX + 0.5`, `v = ((h + k·(zRef − z)) / scale + sheetY) / 1.227` | wall, columns, curtains, throne, braziers, table group; dais with k 0.30 (oblique view so treads get their own band) |
| plan | `u = x / scale + sheetX + 0.5`, `v = ((zRef − z) / scale + sheetY) / 1.227` | carpet |
| tile | each tile samples one cell of a 2 × 2 tile swatch (checker A / B) | floor |
| const | one texel: the middle of the curtain's gold valance | curtainRod |

`m = −1` for a mirrored copy. Shared drawings: `columnR` = `columnL`'s drawing (shifted), `curtainR` = `curtainL`'s
(mirrored), `brazierR` = `brazierL`'s, so the child colours one of each pair. The table and its four children share
one mapping (one still-life drawing). Outlines are drawn outside each drawing's silhouette, so UVs need no inset;
inner region lines and grey detail lines (flutes, folds, bricks, feathers, depth steps) are inside and must be
erased / filled from neighbours by the scan pipeline, as for the characters.

## Colouring sheet (final, 2026-11-14)

Composed by `tools/story/make_sheet.py esther` (generic for story packs with the same inputs), exactly like David &
Goliath: page 1240 x 1754 @150 dpi, four markers, art rect [120, 283, 1000, 1227], 田字格 title 以斯帖 / yǐ sī tiě /
Esther. Figures at the bottom at the Characters role's places (`design.json characters`: Esther −0.33, king +0.02,
Haman +0.34, sheetY 0.015); the set drawings above them. The set's ID map comes from this script
(`model/set_id_2x.png/.json`: R = region id, G = detail lines), so print and UVs cannot drift.

```
python3 tools/story/make_sheet.py esther                                                 # sheet + checks.json
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup --python tools/story/make_sheet.py -- esther render
```

Outputs: `assets/esther/sheet/{reference,demo-sheet,demo-colored,lineart,regions}.png`, `regions.json`,
`template.json`, `checks.json`, `textured_*.png` (set + cast wearing the demo colouring); `print/esther-A4.png/.pdf`.
To move a drawing: edit `DRAWINGS` in `es_palace.py`, rerun it (UVs follow), then rerun `make_sheet.py`.

| Drawing | Scale | bbox (x0, ys0, x1, ys1) |
|---|---|---|
| wall | 1.5 | -0.403, 0.997, 0.403, 1.211 |
| column | 1.05 | -0.481, 0.445, -0.329, 0.979 |
| curtain | 1.0 | -0.312, 0.452, -0.118, 0.859 |
| throne | 1.05 | -0.096, 0.598, 0.096, 0.979 |
| dais | 1.3 | -0.104, 0.445, 0.104, 0.581 |
| brazier | 0.8 | 0.161, 0.765, 0.259, 0.946 |
| banquet | 0.72 | 0.247, 0.445, 0.463, 0.567 |
| carpet | 1.25 | 0.289, 0.600, 0.481, 0.866 |
| floor | 1.3 | 0.157, 0.605, 0.273, 0.717 |

## Demo colours

`design.json set.demoColours`, from `DESIGN.md` (curtains #B5283A, columns #E8D3A8 / gold #E8B53C, carpet #3B4A8C /
#C8643C, floor #EFE6D4, brazier #A8682E), plus: glazed bricks #7CC0CC, frieze and throne panel lapis #2F5FD0,
rosettes #F2C14E, guardian body gold / wing #8CC8F0 / mane #C8643C, cushion #C8323F, table cloth #F6EEDC.

## Previews

`phone` and `phone_set` use the David & Goliath phone eye (−0.08, 0.95, 1.15) → (−0.08, 0.05, −0.50), with and
without stand-ins; `front`; `orbit` is the S01 camera (dist 1.7, height 0.55, yaw −25); `banquet` is S09 (table
shown); `topdown` shows the page. The set is textured with the demo colouring through its UVs (lines removed,
crayon grain), so they check UV registration as well as shape. The figures are simple stand-ins in the demo
colours at the timeline marks (not the real characters); flames are preview-only cones (the app plays the FX).

## Known rough points

1. The bull capitals read as bulls from the phone, but in the line art they are small (about 25 mm across) and
   the horns are thin lines.
2. Region size: carpet diamonds, rosette studs on the risers, goblets and fruit are below the 6 mm rule; they are
   pattern details a child may leave white.
3. Esther's toes touch the bottom riser at the steps foot (riser at z −0.150, mark −0.12): fine for `climb` on the
   spot, but a longer foot will clip a little.
4. The back wall's centre (bricks) is mostly hidden behind the throne and curtains from the phone; the guardians
   outside the columns carry the relief.
5. Not yet seen in Unity with DGPaperLit and a real scan.
