# Saul Sees the Light! — set `damascus` and colouring sheet

Script: `pipeline/sa_damascus.py` (`-- check | build | all | verify`; run Blender with `--python-exit-code 1`).
Output: `assets/saul/model/damascus.glb` (+ `.blend`, `set_id_2x.*`, `damascus_preview_*.png`), the `set`, `characters`
and `sheet` blocks of `assets/saul/design.json`. Sheet: `tools/story/sheet_saul.py` (make_sheet.py unchanged; the
wrapper is needed only until Integration adds `saul` to `assets/stories.json`) → `assets/saul/sheet/`,
`print/saul-A4.{png,pdf}`; then `python3 tools/story/make_colored_pdf.py saul` → `print/saul-A4-colored.pdf`. Textured
check renders: `blender -b --factory-startup --python-exit-code 1 --python tools/story/sheet_saul.py -- render` →
`assets/saul/sheet/textured_*.png`.

## 1. Nodes (root `damascus` at the origin; origin = (x, h, z))

| Node | Parent | What | Origin |
|---|---|---|---|
| `ground` | root | desert / city earth, the rest of the floor (extra node; building footprints left out) | origin |
| `straightStreet` | root | pale paving x −0.60…0.027, z −0.28…−0.08 (also the gateway floor) | (−0.30, 0, −0.18) |
| `road` | root | sand-gold strip 0.14 wide: porch steps (0.485, −0.30) → right side → front (z ≈ 0.03…0.17) → (0.135, 0.06) → the gate (0.02, −0.16) | (0.40, 0, 0.08) |
| `cityWall` | root | wall x −0.027…0.027, z −0.5875…−0.27, body 0.282, rounded merlons to 0.30; **two** round towers r 0.05, top 0.34, at (0, −0.04) (front, contract) and (0, −0.27) (new, the gate's back side); short segment z −0.10…−0.04 | **(0, 0.34, −0.04)** = front tower top (FX anchor, `golden_rays`) |
| `cityGate` | cityWall | the gateway z −0.22…−0.10, **open to the sky** between the two towers; two open wooden doors (0.24 high, iron straps) standing in its edges (faces at z −0.216 / −0.104) | (0, 0, −0.16) |
| `torch1` | cityWall | torch in an iron holder on the back tower's outside face, z −0.25 | (0.062, 0.222, −0.25) (FX `lamp_flame`) |
| `torch2` | cityWall | the same on the front tower, z −0.07 | (0.056, 0.222, −0.07) |
| `wallWindow` | cityWall | opening in the outside face z −0.495…−0.425, y 0.20…0.27, dark recess to x 0.010; wooden shutter folded open behind it (z −0.571…−0.501) | (0.027, 0.235, −0.46) (S11 camera) |
| `ananiasHouse` | root | **front left** (staging 2026-11-18): room x −0.60…−0.33 (inside **0.24**), z −0.064…0.20, walls 0.015, h 0.26, open front toward the viewer, its back to Straight Street, roof slab over z < 0.0 only; inside: window in the back wall, lamp on a ledge, stool, rolled mat | **(−0.465, 0.30, 0.07)** (FX: the light) |
| `synagogue` | root | block x −0.44…−0.30, facade **z −0.412**, h 0.30, cornice to 0.32; two engaged columns at x −0.425 / −0.315; door x −0.402…−0.338, y 0.04…0.215; lintel band with four rosettes (no letters); steps z −0.412…−0.34 (top 0.04), −0.34…−0.32 (0.0267), −0.32…−0.30 (0.0133) | (−0.37, 0.04, −0.412) |
| `judasHouse` | root | room x −0.29…−0.027 (the right wall is the city wall), z −0.5875…−0.30, left wall −0.29…−0.275, h 0.26, roof only over z < −0.52, threshold stripe (h 0.004), low table at (−0.07, −0.525) r 0.04 top 0.04, the window's dark inside on the city wall | (−0.155, 0, −0.44) |
| `judasDoor` | judasHouse | **one** door post at x −0.20, z −0.305, h 0.268 (with cap); the back gate tower is the other jamb | (−0.20, 0, −0.305) |
| `prayerMat` | judasHouse | rug 0.14 × 0.095 at (−0.15, −0.46), top 0.0065 | (−0.15, 0, −0.46) |
| `breadBasket` | judasHouse | straw basket r 0.022 with three loaves on the table, top 0.071 | (−0.07, 0.04, −0.525) |
| `waterJar` | judasHouse | terracotta jar at (−0.23, −0.53), r 0.035, top 0.10, two handles | (−0.23, 0, −0.53) |
| `well` | root | stone ring r 0.04, h 0.05, dark inside, bucket on the rim; two pots and a market crate beside it (h ≤ 0.045); **back left**, where Ananias's house was | (−0.51, 0, −0.44) |
| `rocks` | root | two rocks at (0.18, −0.20) (r 0.035, h ≤ 0.05) and two bushes at (0.225, −0.25), (0.195, −0.272) (h ≤ 0.036) | (0.18, 0, −0.20) |
| `milestone` | root | round-topped stone at (0.24, 0.19), h 0.075 | (0.24, 0, 0.19) |
| `palm` | root | trunk r ≤ 0.018 from (0.584, 0.164), crown at 0.355, fronds only x ≥ 0.542, lowest frond tip 0.315 | (0.58, 0, 0.16) |
| `priestPorch` | root | platform x 0.375…0.60, z −0.5875…−0.36, floor 0.04; steps x 0.42…0.54 (z −0.36…−0.33 top 0.03, z −0.33…−0.30 top 0.02); columns (0.39 / 0.58, −0.37) and (0.39 / 0.58, −0.565); back wall; flat roof **0.43…0.45** | (0.48, 0.04, −0.47) (S01 camera) |
| `jerusalemHouse` | root | x 0.16…0.32, z −0.5875…−0.423, h 0.24, flat roof with a low parapet, a dark window in the right face | (0.24, 0, −0.5035) |
| `jerusalemDoor` | jerusalemHouse | the open doorway x 0.195…0.285, top 0.20, dark room behind to z −0.52, the leaf folded back inside against the left reveal | (0.24, 0.10, −0.423) (S12 camera) |
| `jerusalemWall` | root | back relief x 0.027…0.60 (front face z −0.5845), battlements 0.355, towers x 0.07…0.13 (0.415) and 0.26…0.31 (0.405) | (0.31, 0, −0.5845) |
| `hills` | root | back relief x −0.60…−0.027, top 0.36…0.42, distant flat roofs drawn | (−0.31, 0, −0.5845) |

Hidden at start: none (the set has no state props). Triangles **11,280** (re-imported GLB 11,260); budget 70,000.
Verify: all 25 nodes, 0 UV outside 0–1.

## 1a. Staging changes (2026-11-18, lead)

- **Ananias's house moved to the front left and widened** (inside 0.11 → 0.24). The Animation role's `setCheck` showed
  Ananias's arms and knees inside both side walls in all four S07 clips; at 0.20 inside his elbows in `startle` still
  touched (157 proxy points), at 0.24 nothing does. The back row (Ananias | synagogue | Judas) has no 0.13 to spare:
  Judas's room cannot narrow (ANANIAS_POUR / JUDAS_IN need 0.05 from its left wall) and a synagogue under 0.10 cannot
  hold Saul on its step. The front-left corner was empty (only the well). The house is the same room, built at its
  old depth and moved forward 0.52 (`AH_DZ`); on the sheet it keeps its back-row place left of the synagogue
  (`AH_DRAW_DX` −0.118 in the drawing model; `street` drawing scale 1.35 → 1.56, cx −0.267 so the wider room fits).
  ANANIAS_HOME (−0.465, 0.08). The well, its pots and crate moved into the freed back-left corner.
- Cost: from the front, the house hides the lower half of anyone standing on the left part of Straight Street behind
  it (x < −0.33, z −0.08…−0.28). S10's listeners now stand right of the synagogue; S13's row starts at x −0.27.
- The short guard's S11 mark is (0.19, −0.11) (his `boast` / `doze` arm went into the back tower at (0.11, −0.27));
  Peter's JHOUSE_DOOR is (0.24, −0.33) (his `peek_afraid` arm went into the house front at −0.37 and still at −0.35). Story marks, not
  geometry. Animation `setCheck` after the change: no contact left for Ananias at home, the short guard or Peter
  (see `assets/saul/anim/clips.json`).

## 2. Deviations from CONTRACT §6 (set geometry; story.py untouched)

| Contract | Built | Why |
|---|---|---|
| gate: round-topped arch 0.24 high | **open gateway** between the front tower and a second round tower at (0, −0.27); the doors 0.24 high | every actor is taller than 0.24 (0.30–0.41); the tall guard walks GATE_OUT → GATE_IN under it (head 0.41). A gatehouse with a 0.44 arch was built and looked like a chimney from the front, and broke "tower ≤ 0.34" (PLAN risk 8). Now nothing on the wall is above 0.34. **Lead decision**: keep this, or keep the 0.24 arch and end the S05 lead path at GATE_OUT (nobody passes through) |
| `judasDoor`: posts at x −0.20 and −0.06, lintel 0.24 | one post at −0.20 (h 0.268); the back gate tower is the right jamb; no lintel | Ananias (head 0.33) walks through the frame (lintel 0.24 is in his head); the S09 Judas mark (−0.08, −0.34) is 0.034 from a post at −0.06; a lintel raised to 0.38 above the 0.26 walls read as a gallows in the preview |
| porch roof 0.32 | 0.43…0.45 | the priest stands at PORCH_Y 0.04 with head 0.40 |
| porch x 0.36…; steps over the porch width | porch x 0.375…0.60; steps x 0.42…0.54 only | S12 Saul (0.40, −0.24) → (0.33, −0.33) crossed the step corner (0.005) and ended 0.03 from it |
| room roofs "only at the back half" | roof slabs only over z < −0.52 | standing Judas (−0.21, −0.41), Ananias at ANANIAS_TOUCH (−0.08, −0.42) and at ANANIAS_HOME (standing in `startle` / `nervous`) are under the back half with heads 0.33–0.35 above the 0.26 walls |
| wall x ±0.03 | ±0.027 | ANANIAS_TOUCH and Judas (−0.08, −0.34) were exactly 0.050 from the inner face |
| Judas left wall at x −0.28 | −0.29…−0.275 | ANANIAS_POUR (−0.22, −0.42) was 0.045 from the inner face |
| Ananias walls 0.02 | 0.015 | ANANIAS_HOME was exactly 0.05 from both inner faces |
| synagogue facade z −0.40 | −0.412 (top step −0.412…−0.34) | SYN_STEP (−0.37, −0.36) was 0.04 from the facade |
| table (−0.06, −0.53); water jar (−0.24, −0.55) | (−0.07, −0.525); (−0.23, −0.53) | the table cut 0.007 into the city wall; the jar cut into the left and back walls |
| rocks (0.30, −0.02) | (0.18, −0.20) | 0.02 from the S03 short guard (0.30, 0.04); the free spot between Barnabas's S12 walk and SHORT_GATE |
| milestone (0.26, 0.18) | (0.24, 0.19) | 0.049 from ROAD_STOP and from Saul's walk ROAD_STOP → LIGHT |
| palm crown "beyond x 0.50" | fronds only x ≥ 0.542 | the tall guard at (0.50, 0.08) (head 0.41) had fronds 0.025 away |
| torches y 0.20 | flame anchor 0.222, lowest part 0.177 | ROAD_E is 0.054 from torch2: in the low zone it needs 0.05 plus the torch radius |
| jerusalemHouse front z −0.42; door 0.08 wide | −0.423; 0.09 wide | JHOUSE_DOOR exactly 0.05 from the face; the dark doorway region on the sheet ≥ 6 mm |

## 3. Clearance (`-- check`; low zone y+0.012…0.17 needs 0.05, overhead to the head top 0.035)

**After staging (2026-11-18): every mark and straight leg of the staged `story.py` (92 checks) passes; tightest S10 Ananias in Judas's doorway (−0.225, −0.37) 0.050, Barnabas's S12 walk 0.052, ANANIAS_TOUCH 0.053, S10 short guard 0.053. The table below is the pre-staging state.**

All 55 marks and all 29 straight walk legs of `story.py` (2026-11-18) were checked; the gaps between buildings and the
terrain do not count. **CLEARANCE OK for everything except three places the set cannot fix.** With the proposed values
below, `CLEARANCE_PROPOSED` is OK.

**Mark changes the lead must make in `story.py`** (all checked by the script as `PROPOSED`):

| story.py | Now | Problem | Proposed |
|---|---|---|---|
| S02 short guard start (`_short_puff` first point, `show("shortguard", ..., (0.40, -0.30))`) | (0.40, −0.30) | 0.02 from the porch steps' front corner (0.42, −0.30) | **(0.38, −0.26)** (0.057; 0.089 from Saul at ROAD_A) |
| S02 tall guard start (`_tall_puff`, `show("tallguard", ..., (0.52, -0.30))`) | (0.52, −0.30) | stands on the steps' front edge (0.003) | **(0.56, −0.25)** (0.054; 0.104 from ROAD_A) |
| S11 Saul's tiptoe end (`_away`) | (0.22, −0.35) | the line from BASKET_DOWN cuts the believers' house corner (0.16, −0.423) at 0.015 | **(0.12, −0.36)** (0.054; tiptoes along the wall foot toward the dozing guard's back, 0.09 behind him; 0.10 long, 1.7 s at V_TIPTOE, so T_AWAY gets shorter) |

Tightest after the changes (low / overhead): S10 short guard (−0.22, −0.25) 0.051 / 0.047 (door post), Barnabas's
S12 walk 0.052 (rocks), ANANIAS_TOUCH 0.053 (city wall), Judas (−0.08, −0.34) 0.053 (back tower), Ananias JUDAS_DOOR
→ ANANIAS_TOUCH 0.053, S12 Saul → (0.33, −0.33) 0.053 / 0.060 (porch corner / column), GATE_OUT → GATE_IN 0.054 (door
faces), ANANIAS_HOME 0.055, ANANIAS_POUR 0.055, JUDAS_IN 0.059 / 0.056, SYN_STEP 0.059 / 0.044 (facade / lintel band),
SHORT_GATE 0.056 / 0.044 (torch1), ROAD_E 0.067 / 0.045 (torch2), SAUL_MAT 0.063, BASKET_DOWN 0.065 (believers' house
corner; wall face 0.068), JHOUSE_DOOR 0.068 / 0.053, PRIEST 0.077 / 0.082. Numbers per mark:
`design.json set.clearance.nearest`.

**The basket** (S11): BASKET_DOWN x 0.095, basket 0.10 across → its wall-side edge at x 0.045, the wall face at 0.027:
gap **0.018** in every frame (the base does not move). Nothing else within 0.065 in plan below 0.45 (the believers'
house corner). The shutter lies flat on the wall face (x 0.027…0.031) behind the window, not over the descent.
`ropeTop` (rig-local (−0.065, 0.235, 0)) lands at (0.030, 0.235, −0.46): inside the window opening (z −0.495…−0.425,
y 0.20…0.27; the recess goes back to x 0.010), 0.035 below the window top, 0.05 below the wall top. The rope tops
never show above the wall if the two rope ends stay within z ±0.035 of −0.46. Animation must still probe `basket_down`
with `damascus.glb`.

## 4. Looked at (phone camera = StoryDirector on a 1080 × 2340 portrait screen: dist and height × 2.26, vfov 60)

`damascus_preview_phone(_set)`, `_s01 … _s13` (+ `_s07_standing`, `_s08b`, `_s11_down`, `_s11_yaw25`), `_wall`,
`_rooms`, `_jerusalem`, `_front`, `_topdown`, with stand-in actors at the story's marks; textured (sheet demo colours
through UV0, real cast): `assets/saul/sheet/textured_*.png`. Colours land on the right parts. Notes for the lead
(story.py not touched; start cameras only):
- **S11** (wallWindow, yaw 50): the believers' house (h 0.24) stands between this camera and the lower half of the
  window and the descent; only the basket above its roof shows. At **yaw ≈ 25** the window, the basket and the
  ropes are all clear (`_s11_yaw25`; computed: the line of sight passes x 0.05 at the house front, the house starts
  at 0.16).
- **S12** (jerusalemDoor, yaw 25): the palm (front-right corner) is in the foreground; at yaw ≤ 15 it is out of frame.
- **S01** (priestPorch, yaw 25): the palm is at the frame edge; the front columns (0.39 / 0.58) are clear of the
  priest.
- **S06 / S08** (judasHouse): the front gate tower stands in front of the room's right end at yaw 0 / −15; Saul on
  the mat, Judas and Ananias at the door are clear.
- **S08**: Ananias's `knock` reaches 0.05 in front of JUDAS_DOOR (−0.13, −0.27); there is no post there (the post is
  0.078 to his left, the back tower 0.08 to his right), so the knock lands on air. A second post in front of him
  cannot pass the clearance of Judas (−0.08, −0.34) and of Ananias's own walk in; the lead either accepts it or turns
  him to the left post (needs a new JUDAS_DOOR and a re-check: ask the set role).
- The two towers stand in line from the front, so the S10 / S13 front cameras see one 0.10-wide tower, 0.34 high.

## 5. Sheet

Drawings (`design.json set.drawings`): `skyline` (hills + Jerusalem's wall, front), `wall` (the city wall's outside
face seen from +x and a little above: both towers, the open gateway, window, shutter; block courses drawn), `street`
(front-above: the inside of Ananias's room, the synagogue, the inside of Judas's room; the outsides of the rooms
take one limestone texel, L51), `jerusalem` (porch + believers' house, front-above), `ground` (plan: ground, road,
street), `props` (still life: bread basket ×3.7, water jar ×1.25, prayer mat ×0.95), `yard` (well ×1.6, rocks ×1.5,
bushes ×2.3). Named texels: room roofs → jerusalem:roof; room outsides, threshold → jerusalem:limestone; stool,
table, door post, gate doors, torch sticks, bucket, crate, palm trunk, jerusalemDoor leaf → wall:wood; lamp, pots →
props:jar; rolled mat → props:mat; Ananias's ledge → street:plaster; the well's inside, gate straps, torch holders →
wall:window (dark); torch heads → props:straw; milestone → yard:rock; palm crown → yard:leaf; the gaps between
buildings → ground:ground. Demo colours: DESIGN §3; regions DESIGN does not name were chosen here (plaster #F3E6C9,
floor #C9A97A, ground #DCC79A, rug #8E5A8C, well stone #C9C0B0, hills #B9A86E, Jerusalem wall #E6D2A2).

Prop anchors (`design.json set.propAnchors`, read by `sa_characters.py`): `saul/letters` → street:column (the
synagogue's cream stone) (0.1905, 0.82029); `saul/bread`, `judas/bread` → props:bread (0.0685, 0.45436);
`saul/basket` → props:straw (0.0755, 0.4128); `ananias/jug`, `tallguard/lantern` → props:jar (0.1645, 0.43073).

Set regions, best cell (make_sheet rule, measured on the printed sheet): smallest wall:window 7.1 mm, ground:road 7.1,
props:mat 7.5, wall:wood 7.8, street:synDoor 7.8, props:straw 7.8, jerusalem:doorway 7.8, props:jar 8.2; all others
8.5–30.5 mm. No slivers, no set region without a colourable cell, set over cast 0 px, all 30 set constant texels on
their regions. Final slots (unchanged from CONTRACT §2, as in `regions_characters.json`): ananias −0.32 / 0.015, saul
0.0 / 0.015, barnabas 0.32 / 0.015. Title 扫罗变了: box 80, gap 16, cy 110 (title-search; worst title-band NCC 0.459
against risen-A4, bar < 0.6; `signature`: DISTINCT). `print/saul-A4.pdf` and `-colored.pdf`: 210.0 × 297.0 mm, markers
0 px from the blank.

**Sheet status (after staging 2026-11-18): PASS, anchors 61 / 61, no set region under 6 mm by the make_sheet measure (the `street` drawing is 13 % smaller: street:synDoor and the room window are the smallest street regions; the build's rough estimator says 5.3-5.7 mm, the printed-sheet check passes them).** Earlier: FAIL on 3 cast anchors only (`checks.json`): `ananias.jug` (0.1475, 0.52771), `saul.bread`
(0.0545, 0.5383), `saul.basket` (0.0615, 0.5) in `regions_characters.json` were written by the Characters run of
08:59 against an earlier set layout and now sample paper (the textured render shows Saul's basket white). Fix:
re-run `pipeline/sa_characters.py` (it reads the anchors above from `design.json`), then
`python3 tools/story/sheet_saul.py` and `python3 tools/story/make_colored_pdf.py saul`. Cast regions under 6 mm
(Characters role): saul hair 1.2 mm, saul beard 1.7, barnabas hair 1.8, ananias beard 2.0, barnabas beard 2.1,
ananias cap 2.7, saul cloak 2.7, barnabas face 5.1, saul face 5.4, barnabas mantle 5.5, ananias face 5.8, barnabas belt
5.8, saul belt 5.8.

## 6. Weak or unverified

- No device or Unity check: the FX anchors (`cityWall`, `torch1`, `torch2`, `ananiasHouse`) and the open-gate staging
  are checked in Blender only.
- The open gateway replaces the contract's arch (§2): a lead decision. If the arch comes back, the S05 walk through
  it must go.
- Stand-ins are cylinders: the `walk_blind` / `lead_hand` pair through the 0.12 gateway (door faces 0.054 from the
  line), the seated / kneeling Saul with Ananias at 0.08, and the basket descent need the Animation role's probes with
  `damascus.glb`.
- The rooms' outsides, roofs and Ananias's furniture are single texels (not printed), as in He Is Risen!; the plan
  drawing shows the building footprints as paper holes.
- The textured `textured_house` frame is a quick check, not a story shot.
