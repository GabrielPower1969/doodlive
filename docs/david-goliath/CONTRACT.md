# David & Goliath — production contract

The single brief every role works from. A kid colours one A4 sheet showing David and Goliath; the phone scans it;
both characters stand up on the page wearing the kid's colours and act out the story (about 60–90 s), with music,
effects, and voice in Chinese or English (following the app's language setting). This is milestone M4 in README
("David vs Goliath inside the state machine"). The older web-only theatre (`web/battle*`, procedural humanoids,
English-only) stays untouched; it is a reference for pacing, not a dependency.

Paths below are relative to the repo root (`4-business/doodlive`). Change this file only by agreement; if a role
needs a contract change, it writes the request into its report instead of editing other roles' files.

## 1. Roles and file ownership

Write only inside your own paths. Read anything.

| Role | Owns |
|---|---|
| Story & storyboard | `docs/david-goliath/STORY.md`, `STORYBOARD.md`, `docs/david-goliath/storyboard/`, `assets/david-goliath/timeline.json` |
| Design | `docs/david-goliath/DESIGN.md`, `docs/david-goliath/design/`, `assets/david-goliath/design.json` |
| Blender (model, rig, skin, sheet) | `pipeline/dg_*.py` except `dg_animate.py`, `tools/make_dg_sheet.py`, `assets/david-goliath/model/`, `print/david-goliath-A4.*`, `assets/david-goliath/sheet/`, `docs/david-goliath/RIG.md` |
| Skeletal animation | `pipeline/dg_animate.py`, `assets/david-goliath/anim/`, `docs/david-goliath/ANIMATION.md` |
| Effects | `unity/Assets/DoodLive/DavidGoliath/Fx/`, `docs/david-goliath/FX.md` |
| Music & SFX | `tools/make_dg_music.py`, `assets/david-goliath/audio/music/`, `assets/david-goliath/audio/sfx/`, `docs/david-goliath/MUSIC.md` |
| Voice (zh + en) | `tools/make_dg_voice.sh` (and helpers `tools/dg_voice_*`), `assets/david-goliath/audio/voice/`, `docs/david-goliath/VOICE.md` |
| Integration (Unity + APK) | everything else under `unity/Assets/DoodLive/DavidGoliath/`, edits to existing Unity scripts / `DoodLiveSetup.cs`, `tools/i18n/strings.json` + regenerated outputs, `docs/david-goliath/INTEGRATION.md`, new entries in `docs/LESSONS.md`, the map in `CLAUDE.md` |
| QA | `docs/david-goliath/QA.md`, `docs/david-goliath/qa/` |

Only the Integration role runs Unity. Nobody runs `adb kill-server`, nobody commits (the owner commits).

## 2. Characters

Ids: `david`, `goliath`. Units: **art-width units** (1.0 = width of the sheet's art rectangle), Y up, the page lies in
the XZ plane at y = 0, +Z points from the page toward the viewer holding the phone, +X to the viewer's right.
David stands height ≈ 0.30, Goliath ≈ 0.80 (Goliath about 2.7× David, as in 1 Samuel 17: "six cubits and a span").
Default marks: David at x = −0.25, Goliath at x = +0.22, both on z = 0, facing each other.

## 3. Skeleton (bone names are the contract)

Both characters use the same humanoid bone names (camelCase, L/R suffix, like the angel's rig):

```
root
└ hips
  ├ spine ─ chest ─ neck ─ head ─ jaw
  │          ├ shoulderL ─ upperArmL ─ forearmL ─ handL
  │          └ shoulderR ─ upperArmR ─ forearmR ─ handR
  ├ thighL ─ shinL ─ footL ─ toeL
  └ thighR ─ shinR ─ footR ─ toeR
```

Extra bones: David `slingCord1 slingCord2 slingPouch` (children of `handR`, a 3-bone chain), `stone` (free, child of
`root`, so it can fly). Goliath `spear` (child of `handR`), `shield` (child of `handL`), `helmet` (child of `head`).
Rest pose: A-pose, arms ~30° below horizontal, facing +Z. `jaw` opens the mouth for lip flap.

## 4. Colouring = texture, UV = page position

One scanned art rectangle textures both characters. Every mesh's UV0 is a front (−Z view) orthographic projection
onto the art rectangle: `u = (x − artLeft)/artWidth`, `v = (y − artBottom)/artHeight`, where the sheet's line art is
itself the Freestyle/outline render of the models in rest pose from that same camera. So whatever the kid paints at a
spot of the drawing lands on the 3D surface behind that spot. The art rectangle, marker centres and page size are
written by `tools/make_dg_sheet.py` to `assets/david-goliath/sheet/template.json` in the same format as
`web/assets/template.json` (`page art markers markerSize artPixels`). Never hand-edit it.

## 5. Animation clips (names are the contract)

Each clip is a Blender action exported in the GLB, named `<char>_<clip>`.

| David | Goliath |
|---|---|
| `idle` (loop), `walk` (loop), `talk` (loop, jaw), `kneel_pick` (picks stone), `sling_windup` (loop, cord spins), `sling_release`, `run`, `victory`, `pray` | `idle` (loop), `walk` (loop), `talk` (loop, jaw), `taunt`, `laugh`, `roar`, `charge` (loop), `hit_react`, `fall`, `down` (loop, lying) |

The story role may ask for at most three extra clips by listing them in `timeline.json` → `requestedClips`.

## 6. `assets/david-goliath/timeline.json` (Story writes, everyone reads)

```json
{
  "version": 1, "duration": 78.0, "fps": 30,
  "shots":  [{"id": "S01", "t0": 0.0, "t1": 6.0, "title_zh": "…", "title_en": "…",
              "camera": {"type": "orbit|fixed|follow", "target": "david|goliath|both|stone", "dist": 1.2, "height": 0.35, "yawDeg": 20},
              "desc": "what the viewer sees"}],
  "acting": [{"t": 0.0, "who": "goliath", "clip": "walk", "to": [0.22, 0.0], "face": "david", "blend": 0.25}],
  "lines":  [{"id": "dg_01", "t": 4.0, "who": "narrator|david|goliath|saul|soldiers",
              "zh": "…", "en": "…", "maxSec": 5.0, "ref": "1 Samuel 17:8"}],
  "fx":     [{"t": 40.2, "id": "sling_trail", "at": "david.slingPouch", "dur": 1.5}],
  "sfx":    [{"t": 41.0, "id": "stone_hit"}],
  "music":  [{"t": 0.0, "cue": "theme_tension"}],
  "requestedClips": []
}
```

`acting.to` is an XZ target in art-width units (omit to stay put). `fx.id`, `sfx.id`, `music.cue` are names the FX,
Music and Voice roles must deliver exactly. Times are seconds from the start of the performance.

## 7. Audio deliverables

44.1 kHz mono WAV for Unity (`.wav`), plus 96 kbps MP3 copies for web. Loudness: voice −16 LUFS, music −20 LUFS,
SFX peak −3 dBFS. Voice files `assets/david-goliath/audio/voice/{zh,en}/<line id>.wav` and
`assets/david-goliath/audio/voice/durations.json` (`{"zh": {"dg_01": 3.42}, "en": {...}}`). Subtitles
`assets/david-goliath/audio/voice/{zh,en}.srt`. TTS text goes to Microsoft via edge-tts (as in `tools/make_voice.sh`):
lines must contain nothing private. A real recorded voice can replace any clip later through the `voice-record` skill.

## 8. Effects deliverables

`unity/Assets/DoodLive/DavidGoliath/Fx/DGFx.cs`: `public static class DGFx { public static void Play(string id,
Transform at, float dur); }` building everything in code (ParticleSystem / LineRenderer / unlit materials, URP-safe,
no asset-store packages), so `timeline.json` `fx` entries play by id. Must include at least the ids the timeline uses.

## 9. Integration target

A third sheet in the AR reference library (`david-goliath`). When it is detected: warp the art rectangle exactly as
for the angel, put both characters on the page with the scanned texture, and run `DGDirector` over `timeline.json`
(acting → Animator / Animation clips, lines → voice + subtitle in the current language, fx, sfx, music). Tap = pause /
resume; finish → replay chip. The home screen's existing "battle" entry opens a demo run with the sample colouring.
Build with `scripts/build-apk.sh` only (fingerprint invariant). The angel flow must keep working unchanged.

## 10. Accepted deviations (recorded 2026-10-27, fix round after QA)

These differ from the text above and are now part of the contract. The sections above are left as written so the
original brief stays readable; where they disagree, this section wins.

| # | Topic | Contract text | Accepted as built |
|---|---|---|---|
| D1 | `acting.face` (§6) | `david` / `goliath` | also `"viewer"` = face +Z (toward the person holding the phone); `DGDirector` implements it |
| D2 | Rest pose (§3) | arms ~30° below horizontal | **40°** below horizontal, so both figures fit the art rectangle with margins (`design.json restPose`) |
| D3 | Faces (§4) | everything comes from the scan on UV0 | the app's line-erase wipes printed face ink, so faces are **decals on UV1** (`design.json faceDecals`, one PNG per expression, chosen per clip by `clipExpression`); UV0 stays the page projection |
| D4 | Sheet position (§2, §4) | default marks x = −0.25 / +0.22 | the *drawing* (and so UV0) puts David at sheet x = **−0.32** and Goliath at **+0.14** (`design.json characters.<id>.sheetX`); the stage marks of §2 are unchanged. Both figures are also drawn **0.015 above** the art rectangle's bottom edge (`sheetY`), so the outline under the feet is printed and every region is closed. UV0: `u = x + sheetX + 0.5`, `v = (y + sheetY) / artHeight` (character-local x, y) |
| D5 | Home entry (§9) | "the existing battle entry opens the demo" | the Unity home had no battle entry; a new **`dgDemo`** button ("大卫和歌利亚 · 看演示 / David & Goliath · demo") opens the demo. The web `battle` link is untouched |
| D6 | Integration paths (§1) | "everything else under `DavidGoliath/`" | Integration owns `DavidGoliath/Scripts/` (DGTimeline, DGActor, DGDirector), `DavidGoliath/Shaders/` (DGPaperLit), `DavidGoliath/Editor/` (DGSetup, DGPreview), the generated copies (`Models/ Faces/ Textures/ Tracking/ Data/ Materials/ Resources/DG/`) and `DavidGoliath.prefab`; Effects keeps `Fx/` |
| D7 | Music & SFX outputs (§1, §7) | `audio/music/`, `audio/sfx/` | also `assets/david-goliath/audio/preview_mix.mp3` (rough full-length mix for review, not used by the app), owned by Music |
| D8 | Staging (§6) | `to` "in art-width units" | every `acting.to` must stay on the **paper**, not just the art rectangle: x within ±0.596, z within [−1.486, +0.22] (page edge minus 0.024), checked by `build_storyboard.py validate` |

## 11. Redraw 2026-10-27: realistic proportions + desert set

The owner rejected the look of the first build ("最好不要吹气模型，要有沙漠，要有骨骼动画建模，重新画一下"): the models were
joined ellipsoids, capsules and balls (balloon toys, mitten hands, ball heads). This section is the binding brief for
the redraw. **Where it disagrees with §2–§10, this section wins.** Everything else stays: bone names (§3), clip names
(§5), `timeline.json`, story, voice, music, FX ids, UV0 = page projection for the characters, the angel flow.

Numbers live in `assets/david-goliath/design.json` (version 2), written by `docs/david-goliath/design/make_design.py`
(Design). Pictures to match: `docs/david-goliath/design/turnaround-david.png`, `turnaround-goliath.png` (front line
art, front, side, back), `lineup-scale.png`, `expressions.png`, `faces/*.png`, `sheet-mock-*.png`,
`sheet-layout-annotated.png`, `ar-mock-desert*.png` (desert seen from a phone). Rationale: `DESIGN.md`.

### 11.1 Roles and new file ownership

| Role | Owns (added by §11) |
|---|---|
| Design | unchanged (`DESIGN.md`, `design/`, `design.json`) |
| Blender (characters) | unchanged list; rebuilds `david.glb` / `goliath.glb` to this section |
| **Desert (new)** | `pipeline/dg_desert.py`, `assets/david-goliath/model/desert.glb`, `docs/david-goliath/DESERT.md` |
| **Sheet** | `tools/make_dg_sheet.py`, `assets/david-goliath/sheet/`, `print/david-goliath-A4.*` (split out of Blender; same files as before) |
| Skeletal animation | unchanged; re-authors every clip against the new rest pose and adds finger poses (§11.7) |
| Integration | unchanged; loads `desert.glb` (§11.12) |

### 11.2 Look

Realistic-proportion cartoon (Pixar-like): believable anatomy and head-to-body ratios; defined planes (jawline,
cheekbones, brow ridge, nose, collarbones, elbows, knees, ankles); real hands with four fingers and a thumb; real feet
in sandals / laced boots; clothing with thickness, hems and a few folds. **Not allowed:** a body part made from a
primitive (sphere, capsule, cylinder, torus) left visible as such, mitten hands, ball heads, tube limbs of constant
width. Goliath: bronze scale armour (rows), wide belt, kilt, leather bracers, bronze greaves, laced boots, bronze helmet
with neck guard and a transverse red crest (no face guard), round bronze shield, spear with a leaf iron head and a
bronze butt spike. Scary by size and posture only (no teeth, no blood).

### 11.3 Proportions (art-width units, character-local; full table in `design.json characters.<id>.proportions`)

| | David (youth) | Goliath |
|---|---|---|
| Total height | **0.300** (top of hair) | **0.800** (top of crest); helmet dome 0.768 |
| Skull top / chin | 0.294 / 0.241 | 0.746 / 0.645 |
| Heads tall (skull) | **5.55** | **7.39** |
| Shoulder joint (x, y) | (±0.031, 0.220) | (±0.092, 0.603) |
| Upper arm / forearm / hand | 0.053 / 0.043 / 0.031 | 0.138 / 0.112 / 0.082 |
| Hip joint / knee / ankle (x, y) | (±0.016, 0.153) / (±0.0185, 0.083) / (±0.018, 0.016) | (±0.050, 0.380) / (±0.054, 0.209) / (±0.052, 0.040) |
| Foot length (+Z) | 0.044 | 0.112 |
| Mouth line = jaw seam y | 0.2497 | 0.667 |
| Clothing | tunic hem 0.096 (knees show), sash 0.171–0.182, short sleeves | armour coat to 0.362, belt 0.438–0.463, kilt hem 0.262, greaves 0.053–0.199 |

David is 5.55 heads, not 6: at 0.30 units he is 51 mm tall on paper, and a 6-head face is too small to read on a phone
(Pixar teens are 5–5.5). Heights 0.30 / 0.80 are unchanged. Side depths are in `characters.<id>.depth`.

### 11.4 Rest pose and sheet placement (supersedes D2 and the x values of D4)

- **Arms 45° below horizontal** (was 40°, D2): realistic arm lengths do not fit side by side at 40°.
- **Hands at rest hold the props**, because UV0 and the printed line art are taken from the rest pose: David R = fist
  round the sling cords; David L = open, fingers together, thumb forward; Goliath R = fist round the spear shaft,
  knuckles toward +Z; Goliath L = fist on the shield grip, hidden behind the shield.
- **Sheet x: David −0.350, Goliath +0.130** (was −0.32 / +0.14). `sheetY` stays 0.015. UV0 formula of D4 unchanged.
  Measured: margins 0.030 / 0.031 to the art edge, gap 0.058 between the figures. Figure rects on the page (px):
  David `[150, 1191, 243, 305]`, Goliath `[434, 540, 655, 956]`. `DGDirector.davidSheetX/goliathSheetX` and the
  preview must take these values (Integration); the play starts with both actors at (sheetX, z 0).

### 11.5 Modelling method and budgets

- One **continuous box-modelled cage per body** (skin: head, neck, torso, arms, hands with 4 fingers + thumb, legs,
  feet). Clothing and armour are separate shells with real thickness (Solidify ≥ 0.0015 David / 0.003 Goliath),
  rolled hems and 2–5 folds. Hidden body under clothing is deleted. **Subdivision Surface level 1, applied before
  export.** No joined primitives for anatomy.
- Props are separate rigid meshes, each weighted 100 % to one bone: sling cords (slingCord1/2), pouch (slingPouch),
  stone, bag (hips), spear, shield, helmet + crest (helmet).
- Budgets after subdivision: **≤ 20,000 triangles per character** (props included), cage target ~2,200 (David) /
  ~2,600 (Goliath) quads; **≤ 15,000 triangles for `desert.glb`**. One material per GLB (the scanned page texture);
  per-vertex weights ≤ 4 bones.
- Rings of edge loops at every joint (shoulder, elbow, wrist, knuckles, hip, knee, ankle) so the joints bend cleanly.

### 11.6 Skeleton (extends §3)

All §3 names unchanged. **Added on both characters, both sides:** `fingersL fingerTipsL thumbL fingersR fingerTipsR
thumbR` (`fingers` and `thumb` are children of `hand`, `fingerTips` a child of `fingers`). The four fingers share
`fingers` → `fingerTips` (weights fade across the knuckles; no per-finger bones, mobile budget). `hand` now ends at
the knuckles. Head / tail / parent for every bone, rest pose, character-local and at sheet position:
`design.json characters.<id>.bonesLocal` / `bonesSheet` (David 33 bones, Goliath 32). Build the rest pose **exactly at
`bonesSheet`** (LESSONS L7). In a fist the finger bones are curled at rest; animation opens them.

### 11.7 Faces

- **Modelled** in the head mesh: brow ridge, shallow eye sockets, nose with nostrils, cheekbones, lips volume, chin,
  jaw line, ears. Goliath's beard and moustache are modelled volumes (UV0 region `beard`).
- **UV1 decals** (kept from D3, new art): eyes (white, iris, pupil, highlight, lids), brows, mouth. One 512² PNG per
  expression, `docs/david-goliath/design/faces/<char>_<expr>.png`, front-projected into `faceDecals.<id>.rectLocal`:
  David `[-0.0175, 0.2425, 0.0175, 0.2775]`, Goliath `[-0.034, 0.655, 0.034, 0.723]`. Expression names and
  `clipExpression` are unchanged, so DGActor keeps working. The mouth decal straddles the jaw seam (`mouthY`), so the
  part below it moves with `jaw`.

### 11.8 Props (sizes; details in `characters.<id>.props`)

Spear: 0.952 long (y 0.018–0.970 on the sheet), shaft Ø 0.019, leaf head 0.107 × 0.040, butt spike, vertical in the
right fist at sheet x −0.160. Shield: Ø 0.132, rim 0.011, boss Ø 0.034, dished 0.008, centre on the sheet
(0.403, 0.437), z +0.035, face +Z. Helmet: dome 0.096 wide, rim band, neck guard to x ±0.053, transverse crest
0.104 × 0.037. Sling: two cords drawn as one band from the bottom of David's right fist to the pouch (0.024 × 0.018),
stone Ø 0.011 at sheet (−0.457, 0.093). Bag 0.026 × 0.024 × 0.016 at the front of his left hip.

### 11.9 The desert set ("纸上立体沙漠")

**Coordinates.** Same as §2: the page is the XZ plane, y up, +Z toward the viewer, z = 0 at the art rectangle's
bottom edge. A point printed at sheet height `ys` (above that edge) lies on the page at **z = −ys**. Paper bounds from
D8 (x ±0.596, z −1.486 … +0.22). Every piece is defined once, as a footprint polygon in sheet coordinates, in
`design.json desert.pieces[]` (`id kind region geom heightMax zone uv bboxSheet` + extras). The Desert role builds the
3D from these polygons; the Sheet role prints the same polygons. One source, so print and 3D cannot drift.

**Zones and height caps** (sheet coordinates; `desert.zones`, `desert.zoneHeightCap`):

| Zone | Where (x, ys) | What | Max height |
|---|---|---|---|
| Stage | `desert.stageBand.polygonSheet`: every `timeline.json` acting position and walk path, buffered by David 0.075 / Goliath 0.170 | **flat**: nothing above 0.010 | 0.010 |
| L | −0.47…−0.235, 0.43…0.97 (behind David) | 2 barchan dunes, 2 rocks, 1 shrub | 0.10 |
| M | −0.11…−0.04, 0.77…0.92 (valley, between spear and Goliath's head) | 2 rocks | 0.05 |
| T | full width, 1.00…1.18 (far back) | Israel hill (left, behind David), Philistine hill (right, behind Goliath), 3 tents each, 1 banner each | hill 0.12; tent +0.035; banner pole +0.10 cloth 0.045 × 0.030 |
| R | 0.27…0.47, 0.68…1.00 | Philistine hill ridge running down toward the viewer (part of `hillPhil`) | 0.04 at its near end |
| FR | 0.40…0.47, 0.07…0.22 (under the shield) | 2 rocks | 0.05 |
| B | brook strip −0.47…−0.36, −0.236…−0.015 (z +0.015…+0.236), **outside the art rectangle** | brook + five smooth stones | water film 0.004, stones 0.008 |

**Slope rule (no mesas, no needles).** `heightMax ≤ k × inscribed radius of the footprint`, k = 1.0 dune, 0.9 hill,
1.1 rock, 1.3 shrub; the script already applied it. Resulting heights: dunes 0.064 / 0.070, hills 0.079 (Israel) /
0.110 (Philistine), rocks 0.017–0.026, shrub 0.019, tents 0.035. Dunes: gentle windward back from the far edge to the
crest, steep slip face (`duneShade` polygon, `slipFace`) facing +Z. Hills: smooth domes, tents sit on the surface.

**Why these heights keep the actors visible.** The viewer is at +Z, 0.4–0.7 above the page. Nothing between the viewer
and the actors rises above 0.026 (FR rocks, brook stones); everything taller is behind them (z ≤ −0.43) and lower than
David's shoulders. `ar-mock-desert.png` and `ar-mock-desert-low.png` show both views.

**Texturing (UV0) for the desert: top-down page projection.** For a desert vertex at (x, y, z):
`u = x + 0.5`, `v = −z / 1.227` (= `ys / artHeightUnits`), whatever its height. The 3D dune rises straight up out of the
patch the child painted, so its colour stays where it was painted when seen from above. Vertical faces repeat their
footprint edge colour (fine for dunes and rocks). Exceptions (`uv` field): `banner*` = **constant** UV at the centre of
its printed pennant swatch (the whole cloth takes that colour); `fiveStones` = **constant** UV
`desert.stoneUV` = (0.043, 0.0758), the print of David's sling stone, because the brook strip is outside the scanned
texture; `brook` = **no texture**: a transparent animated water film (ripple shine) over the printed brook, so the
real paper shows the child's colour through it in AR. In the demo the printed demo page shows through.

**What occupies which part of the sheet (no overlap).** Inside the art rectangle there are two kinds of drawing and
they never touch:
1. **Character drawings** (upright, UV0 = front projection, §4/D4): inside the two figure rects of §11.4.
2. **Desert drawings** (plan view from above, UV0 = top-down): the zones above. Every desert footprint is at least
   **0.030 (30 px) from both character silhouettes** (checked), so no texel is shared, and inside the art rectangle
   with 0.030 inset (zones L, M, T, R, FR).
The brook strip (zone B) is the only drawing outside the art rectangle. The sun and clouds are removed
(`sheet.decorSuggestion` is `null`). The footer text moves right to rect `[300, 1612, 820, 120]` so it clears the brook.

**Desert GLB contract (`assets/david-goliath/model/desert.glb`).** One node per piece, named exactly as `pieces[].id`
(`hillIsrael hillPhil tentIsrael1..3 tentPhil1..3 bannerIsrael bannerPhil dune1 dune2 rockL1 rockL2 rockM1 rockM2
rockFR1 rockFR2 shrubL brook fiveStones`), all children of one root `desert` at the page origin, same axes and units as
the characters (no scale on the root). Banners carry a simple 2-bone wave or a vertex shader flag; no other animation.
The five stones are separate small meshes under `fiveStones` (`stone1..5`) so the kneel clip can hide one.

**Tracking.** The sheet gains a lot of line art in areas that were empty (top, left), so the reference image has more
and better-spread features; this is good. The reference image changes, so Integration must rebuild the reference
library from the new `reference.png` (same physical width); sheets printed before §11 will no longer be recognised.

### 11.10 Sheet (Sheet role)

The printable sheet is still the outline render of the real rest-pose models for the characters (UV0 truth), plus
the desert polygons from `design.json desert.pieces` drawn in 2D with the same ink rules (outline 4.5 px, detail 3 px,
face strokes 2.2 px; all are removed by the app's line-erase). Regions in `regions.json` gain the desert ids of
`palette.desert` (`sand duneShade rock hillIsrael hillPhil tentIsrael tentPhil flagIsrael flagPhil water pebbles
bush`). The mock `design/sheet-mock-lineart.png` is the target layout.

### 11.11 Animation notes

Re-author every clip on the 45° rest pose. Finger poses per clip: grips stay closed in every clip except David
`kneel_pick` (open → pinch a stone → close), `sling_release` (right hand opens at release), `victory` (both open or
a raised fist), `pray` (both open, palms together); Goliath `taunt`/`laugh` (left stays on the shield, right may open
off the spear only if the spear stays in place), `fall`/`down` (both open). `kneel_pick` happens at (−0.32, z 0.20)
facing the viewer: the brook's right bank is at x ≈ −0.38 there, and the five stones lie at x −0.37…−0.40,
z 0.12…0.21, so the right hand reaches down and outward (−X). Timeline, clip names and timings do not change.

### 11.12 Integration notes

Load `desert.glb` under the same page anchor and `shake` pivot as the actors, with the same scanned-texture material
(DGPaperLit) except `brook` (transparent water, no texture). Take `sheetX` values from `design.json`. The demo page
uses the new demo sheet. `brook_ripple` FX now has a real brook under David's hand.

### 11.13 Acceptance

A parent looking at the turnaround and at the phone says "that is a real character, not a balloon toy", and "the
desert came up out of the page". Concretely: no visible primitive shapes; hands show four fingers and a thumb; knees,
elbows, ankles, collarbones and jaw read in silhouette or shading; desert colours match the child's painting from
above; actors are never hidden by the desert from the viewer's side; budgets of §11.5 met; `make_design.py` PASS.

## 12. Desert boost 2026-10-27

The owner looked at build v2 (APK `a6752d5-dirty.20261027-0845`) and asked: "做沙漠加强：纸面铺沙色地面、沙丘做大做高、营地放大、
涂色纸上沙丘改成看得懂的样子，再出一版 APK". v2 problems: the AR page stayed mostly white paper, dunes were ~12 mm mounds, the camps
were tiny and hidden behind Goliath, the sheet showed dunes as plan-view horseshoe blobs next to upright characters, the brook
printed 1 mm from the page bottom, and `design.json desert.stageBand` kept only Goliath's part (QA T12).
**Where §12 disagrees with §11.9 / §11.10, §12 wins.** Characters, rig, clips, timeline, story, voice, music and FX are unchanged.
Numbers: `assets/david-goliath/design.json` **version 3** (`desert.*`), written by `docs/david-goliath/design/make_design.py`
(PASS). Pictures: `design/sheet-mock-lineart.png`, `sheet-mock-demo-colour.png`, `sheet-layout-annotated.png`,
`ar-mock-desert.png` (DGPreview phone view), `ar-mock-desert-right.png`, `ar-mock-desert-low.png`, `ground-mask.png`,
`ground-sand-demo.png`. Rationale: `DESIGN.md` §6.

Coordinates as §2 / §11.9: page in XZ, y up, +Z toward the viewer, z = 0 at the art rect's bottom edge; `d = −z` = sheet `ys`.

### 12.1 Two kinds of desert piece

| Kind | Pieces | Drawn on the sheet as | UV0 (`mapping`) |
|---|---|---|---|
| **Front (upright)** | far panorama: `duneFar hillIsrael hillPhil tentIsrael1..3 tentPhil1..3 bannerIsrael bannerPhil`; midground: `dune1 dune2 dune3 rockL1 rockL2 rockM1 rockM2 shrubL rockFR1 rockFR2` | **side view** (front orthographic silhouette), like the characters | `front` |
| Ground | `brook`, `fiveStones` | plan view, below the art rect | `none` / `constant` (as §11.9) |

**Front UV rule** (same as the characters' D4 rule, which is the case scale = 1 with character-local x):

```
u = x / scale + sheetX + 0.5
v = (y / scale + sheetY) / 1.227          for a 3D vertex (x, y, z): x = page x, y = height; z is ignored
```

`frontUV` per piece in `design.json`. All desert pieces have `sheetX = 0`.
- **Far panorama: scale 2.5, sheetY 1.000** (one mapping for the whole group, so overlaps in the drawing equal overlaps in 3D).
- **Midground: scale 1, sheetY = −zFront** (each piece stands on its own drawing; its 3D front is the drawing at real size).

The 3D front orthographic silhouette of each front piece **equals** `silhouette3D` (x, y). Depth (`depthZ` front / crestFrom /
crestTo / back): `h(x, z) = top(x) · p(z)`, p rises with smoothstep from `front` to `crestFrom`, is 1 to `crestTo`, then falls as
1 − t² to `back` (back slope steeper than 35°, hidden from the viewer; nothing behind a tent is visible, so nothing smears).
Rocks: `p = sqrt(clamp(min(z − back, front − z) / 0.012, 0, 1))`, flat-shaded, steep walls. `topProfile3D` samples `top(x)`.

### 12.2 Pieces (3D footprint, height, where they are drawn)

| Piece | 3D x | 3D z (front → back) | Height max | Drawn on sheet (x / ys) |
|---|---|---|---|---|
| `hillIsrael` | −0.590 … −0.018 | −0.98, crest −1.28 … −1.42, −1.475 | **0.306** (plateau 0.30 from x −0.47 to −0.18) | −0.236 … −0.007 / 1.000 … 1.122 |
| `hillPhil` | −0.018 … 0.590 | same | **0.382** (plateau 0.37–0.38 from x 0.12 to 0.45) | −0.007 … 0.236 / 1.000 … 1.153 |
| `duneFar` (valley mouth) | −0.240 … 0.190 | −1.38, −1.43 … −1.445, −1.475 | 0.190 | −0.096 … 0.076 / 1.000 … 1.076 |
| `tentIsrael1/2/3` | centre −0.430 / −0.315 / −0.200 | gable −1.300, back −1.410 | base 0.278 / 0.304 / 0.283, top +0.095 | at /2.5 on the hill drawing |
| `tentPhil1/2/3` | centre 0.135 / 0.255 / 0.395 | gable −1.300, back −1.410 | base 0.344 / 0.381 / 0.365, top +0.095 (to 0.476) | at /2.5 |
| `bannerIsrael` | pole x −0.148 | −1.360 | pole base 0.284, pole 0.140, tip 0.430 | cloth (−0.062 … −0.022, 1.144 … 1.170) |
| `bannerPhil` | pole x 0.080 | −1.360 | pole base 0.344, tip 0.490 | cloth (−0.005 … 0.035, 1.168 … 1.194) |
| `dune1` | −0.470 … −0.228 | −0.37, −0.50 … −0.53, −0.60 | **0.172** (crest x −0.396) | same x / 0.370 … 0.542 |
| `dune2` | −0.470 … −0.226 | −0.60, −0.78 … −0.83, −0.92 | **0.246** (crest x −0.400) | same x / 0.600 … 0.846 |
| `dune3` | 0.225 … 0.470 | −0.72, −0.86 … −0.90, −0.98 | **0.240** (crest x 0.310) | same x / 0.720 … 0.960 |
| `rockL1` / `rockL2` / `shrubL` | −0.470…−0.366 / −0.276…−0.234 / −0.349…−0.295 | −0.935…−1.000 / −0.950…−0.985 / −0.940…−0.975 | 0.098 / 0.036 / 0.047 | same x / ys from −zFront |
| `rockM1` / `rockM2` | −0.105…−0.006 / 0.008…0.045 | −0.740…−0.800 / −0.760…−0.795 | 0.072 / 0.038 | same |
| `rockFR1` / `rockFR2` | 0.405…0.470 / 0.420…0.468 | −0.060…−0.130 / −0.160…−0.210 | 0.050 / 0.033 | same |
| `brook` (ground) | −0.469 … −0.377 | +0.012 … +0.190 | film 0.004 | plan view, outside the art rect |
| `fiveStones` (ground) | see 12.5 | | 0.008 | plan view |

Dunes: one wind from +X, so every slip face (`duneShade` part) faces −X: the phone sees the gentle sand backs of `dune1/2` and the
shaded slip face of `dune3` (the right valley wall). Exact polygons: `pieces[].silhouette3D`, `parts3D` (`duneShade`, `tentDoor`).

**Tents** (`pieces[].tent`): A-frame, **ridge along z, gable facing +Z** (the triangle the child sees, from the phone too), width
0.110, height 0.095 above `baseY`, depth 0.110 (gable z −1.300, back −1.410), skirt sinks 0.012 into the hill, cloth sag 0.006,
doorway in the gable 0.044 wide × 0.052 tall, recessed 0.012 (region `tentDoor`, palette `#7A4E2D`). Flat-shaded.
**Banners** (`pieces[].banner`): pole Ø 0.006, 0.140 tall, at z −1.360; swallow-tail cloth 0.090 × 0.060 hanging from the pole top
in the XY plane (front UV), Israel flies toward +X, Philistines toward −X; wave animation as §11.9; the pole keeps the constant
spear-shaft UV of §11.9.

**Camps vs Goliath from the phone** (eye ≈ (−0.08, 0.95, +1.15), Goliath at (0.22, z −0.25)): his head (x 0.17…0.27, to 0.80)
covers the back of the page at x ≈ 0.37…0.55, his shoulders (y 0.63) hide the panorama below y ≈ 0.38 for x ≈ 0.22…0.69. So
`tentPhil1` (x 0.08…0.19) and `bannerPhil` stand **left of his silhouette**, `tentPhil2` (0.20…0.31, top 0.476) shows over his
shoulder, `tentPhil3` (0.34…0.45) is behind his head from the default view (visible from the right, and after the fall). The Israel
camp is fully visible (David is 0.30 tall at z ≥ 0).

**Caps and visibility rules (checked):** hills ≤ 0.40, tents ≤ 0.50, banners ≤ 0.53, dunes ≤ 0.30, duneFar ≤ 0.20, rocks ≤ 0.10,
shrub ≤ 0.06; **any raised footprint reaching z > −0.30 stays ≤ 0.06** (only `rockFR1/2`); nothing above 0.010 in **either part**
of the stage band; all footprints on the paper (x ±0.596, z −1.486 … +0.22). Triangle budget for `desert.glb`: **≤ 20,000** (was
15,000; the set is 3–4× larger).

### 12.3 Sheet regions (Sheet role)

Print `design.json desert.print` in its order (`shapes`: region, piece, rings; `decor`: width px, points), same ink rules as §11.10.
Drawings with different UV mappings are ≥ 0.012 apart; all desert drawings are ≥ 0.030 from the character drawings and ≥ 0.020
inside the art rect; the panorama occupies sheet x −0.236 … 0.236, ys 1.000 … 1.196 (above Goliath's spear tip at 0.970).
**Every ink except the four markers is ≥ 6 mm (35.4 px) from every page edge**: desert ink left/right 147.8 px, bottom 51.8 px
(8.8 mm); `sheet.title.cy` 84 → **100** (pinyin top ≈ 36 px); `sheet.footer.rect` **[300, 1604, 820, 110]** (lines at y + 40 / + 76).
Markers are unchanged (5.1 mm from the side edges, by the template). Regions: palette `desert` gains `tentDoor`; `sand duneShade rock
hillIsrael hillPhil tentIsrael tentPhil flagIsrael flagPhil water pebbles bush` stay. The reference image changes again (rebuild
the tracking library).

### 12.4 Sand ground (Integration)

A ground layer over the **whole page** (x −0.62 … 0.62, z −1.51 … +0.244; page px `X = 620 + 1000·x`, `Y = 1510 + 1000·z`) at
y ≈ 0.0005, under the desert and actors, lit and shadow-receiving like DGPaperLit. Per fragment:

```
m      = groundMask(X / 1240, 1 − Y / 1754)            # docs/david-goliath/design/ground-mask.png (L8, page frame)
if m > 191: discard                                     # 255 = hole: the brook; the real paper (child's colour) shows
d      = −z
sand   = #E3C38C · (1 + 0.04·sin(φ) + 0.05·n2)
φ      = 2π · ( d / 0.020 + 0.45·sin(2π·x / 0.23) + 0.25·n1 )
n1     = valueNoise(x / 0.12, d / 0.12)                 # smooth value noise in [−1, 1], period 1 (64² texture is fine)
n2     = valueNoise(x / 0.30 + 7.3, d / 0.30)
if m < 64: albedo = sand                                # 0 = sand: outside the art rect, and the flat copies of the
                                                        #   characters and of every front piece (dilated 0.008)
else:                                                   # 128 = the rest of the art rect
    scan  = scanTex(x + 0.5, d / 1.227)                 # the line-erased, white-balanced scan DGPaperLit uses
    paper = smoothstep(0.60, 0.86, min(scan.r, scan.g, scan.b))
    albedo = lerp(scan, sand, paper)                    # painted ground keeps the child's colour
```

Desert front pieces use DGPaperLit with the front UV0 above and `_BaseColor` = palette `sand` `#F3D58E`, `_BaseAmt` 1, so unpainted
pieces are sand, not white. The brook keeps the DGWater film; with the ground hole the painted paper shows through it. In the demo
the demo page shows through the hole. Parameters also in `design.json desert.ground`.

### 12.5 Brook and stones (Desert, Animation)

Brook: centreline (−0.452, −0.012) (−0.433, −0.050) (−0.440, −0.090) (−0.422, −0.128) (−0.402, −0.165) (−0.392, −0.200) in
(x, ys), buffered 0.017, cut to ys −0.190 … −0.012 → **x −0.469 … −0.377, z +0.012 … +0.190** (was +0.015 … +0.236);
`brookStripPx` [147, 1518, 100, 186]. Right bank ≈ x −0.385 at z 0.16–0.19. **Five stones** (x, z) — `stone1` (−0.4292, +0.100),
`stone2` (−0.4173, +0.122), `stone3` (−0.4056, +0.143), `stone4` (−0.3955, +0.164), `stone5` (−0.4125, +0.152); 0.0136 × 0.0112,
0.008 high, constant UV `stoneUV` (0.043, 0.0758) unchanged. `kneel_pick` stays at (−0.32, z 0.20) (timeline unchanged); nearest
stones are `stone4` (0.084 away, reach −X and slightly −Z) then `stone5`, `stone3`. Animation re-aims the reach and updates
`clips.json desertEvents`.

### 12.6 Stage band (QA T12 fixed)

`design.json desert.stageBand.polygonsSheet` lists **every** part (now 2: Goliath's, 64 points; David's incl. the brook bank, 51
points), sheet coords (x, ys). The old single `polygonSheet` is **removed**; `dg_desert.py verify`, `qa_check.py` and
`qa_blender_eval.py` must read `polygonsSheet` (union of all parts). `make_design.py coords()` is unchanged for single shapes;
`coords_all()` exports every part.

### 12.7 Who does what

| Role | Work |
|---|---|
| Design | done: `make_design.py`, `design.json` v3, `DESIGN.md`, mocks, `ground-mask.png`, `ar_mock_blender.py` |
| Desert | rewrite `dg_desert.py` for front pieces (12.1–12.2), tents/banners, brook/stones (12.5), front UVs, ≤ 20k tris, verify with `polygonsSheet` |
| Sheet | print `desert.print`; title cy, footer rect; regions incl. `tentDoor`; ink ≥ 6 mm |
| Animation | `kneel_pick` reach and `desertEvents` for the new stones |
| Integration | ground layer + mask + shader (12.4), desert `_BaseColor`, new reference image, new `desert.glb`, APK |
| QA | re-run with `polygonsSheet`; check the phone view reads "desert valley with two camps" |

### 12.8 Acceptance

From the DGPreview phone view: the whole page reads as sand (no white paper left except under the brook film, where the
child's painted water shows), dunes rise to 0.17–0.25 behind David, the two camp hills fill the back with visible tents (gables with dark doors) and
banners above Goliath's shoulders, and nothing stands between the viewer and the actors above 0.06. A child shown
`sheet-mock-lineart.png` names the shapes as sand hills, tents and flags.
