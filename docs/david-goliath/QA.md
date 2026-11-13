# David & Goliath — independent QA

## R. Redraw QA, 2026-10-27 (CONTRACT §11: realistic proportions + desert set)

QA role. Everything below was measured from the shipped files, not taken from the role reports. Reproduce with
`python3 docs/david-goliath/qa/qa_check.py` (writes `qa/qa_results.json`). The new checks T11–T16 use
`qa/qa_blender_eval.py`, which `qa_check.py` runs headless (`blender -b --factory-startup`) when the GLBs are newer than
its cache in `$DG_WORK/qa/`. It imports `anim/*.glb` and `model/desert.glb` exactly as shipped. It then evaluates every
frame of every clip: the skinned body plus the bone-parented props, using all vertices with no subsampling. No phone was
connected, so nothing here was verified on a device.

Evidence: **A** = measured or recomputed from the file. **D** = my judgement.

### R.1 Pass / fail

Final run (after the fix in R.2 and the rebuild): **13 PASS, 2 WARN, 1 FAIL** (`qa/qa_results.json`).

| # | Check | Result | Evidence |
|---|---|---|---|
| T1–T4 | Timeline, ids, voice zh+en, loudness | **PASS** | unchanged from the first build; re-run [A] |
| T5 | Bones = §3 + §11.6 finger bones | **PASS** | model and anim GLBs: David 33 joints, Goliath 32. `fingersL/R`, `fingerTipsL/R` and `thumbL/R` are present, with parents hand → fingers → fingerTips and hand → thumb. No extra joints, no parent mismatches. [A] |
| T6 | 19 clips; Unity copies current | **PASS** | 9 + 10 animations. `Models/{david,goliath,desert}.glb` are md5-identical to `assets/` (after the rebuild). [A] |
| T7–T8 | Template ↔ PNG markers; Unity copies | **PASS** | All 4 markers on 4 sheet PNGs lie within 0.5 px of the template. The template equals the angel's. design/clips/timeline/demo/tracking copies are md5-equal. 11 clipExpression faces exist. [A] |
| T9 | UV0 = page projection | **PASS** | u offset per mesh is exactly design sheetX: −0.350 (David) and +0.130 (Goliath, all 7 meshes). Residual is ≤ 4.0 / 3.3 px. [A] |
| T10 | Art-edge margin | **PASS** | 13 / 42 / 29 / 29 px of paper between the ink and the art-rect edge. [A] |
| T11 | Triangle budgets (§11.5) | **PASS** | David 19,908 and Goliath 19,662 (limit 20,000); desert 14,536 (limit 15,000). Each character GLB has 1 material; the desert has 2 (`dg_page` and `dg_water`, as §11.9 implies). [A] |
| T12 | Stage band | **FAIL (data defect)** | Recomputed from `timeline.json` with the §11.9 rule, the band has **2 parts** (area 0.284). The `design.json` polygon covers only Goliath's part (66 % of the band). Every start mark, walk target and walk path lies inside the recomputed band. See R.4 #2. [A] |
| T13 | Every actor vertex on the paper, every frame, 0–89 s | **WARN** (was FAIL, fixed: R.2) | Simulated placement over all vertices. **Goliath's fall and down stay on the sheet**: body, spear and shield cover z −0.754…+0.200 and x −0.025…+0.377 on the page, and the whole fall hull (incl. the airborne spear) stays within x −0.554…+0.523. Something touches the table past the sheet edge in 1 frame only (53.10 s, walk → kneel cross-fade, 0.007 = 1.2 mm). David rests within D8's 0.024 margin, on the sheet, at z 0.234–0.240 (R.4 #3). His raised arms overhang the edge in the air. Lowest point: David −0.002, Goliath −0.013 (boot toe during the fall). [A] |
| T14 | desert.glb (§11.9) | **PASS** | All 21 piece nodes plus `stone1..5` are present; the root has no transform; the only animations are the 2 banner waves. All vertices, including every banner-wave frame, fit within x −0.472…0.467 and z −1.183…0.238 (page edge 0.244). **No vertex above 0.010 in either part of the recomputed stage band.** Every piece is under its heightMax. UV0 is in [0,1]. The top-down residual is ≤ 0.0043 on all projected pieces. Banners, poles, stones and the bank use a constant UV; the stones take design stoneUV (0.043, 0.0758). The brook has `dg_water` and no UV. [A] |
| T15 | Sheet regions closed; printable | **WARN** | A flood fill from the page border reaches **none of the 92 region ids**, and 0 coloured demo pixels lie outside an outline. All 12 desert palette regions are printed (plus the extra `tentDoor`). **Ink is 1.0 mm from the bottom edge** (the brook), and the sandal straps cannot be coloured. [A] |
| T16 | APK fresh | **PASS** | `.fingerprint`, `build_fingerprint.txt` and the aapt2 versionName are equal and match HEAD a6752d5. The build time is later than every GLB, sheet, face, shader and DGDirector input. `DGWater`, `fiveStones`, `stone5`, `fingerTipsR` and `bannerIsraelWave` are all found inside the APK data. [A] |

### R.2 What I fixed (QA, inside a pipeline script)

| Defect | Fix | Evidence |
|---|---|---|
| In `kneel_pick` David's front (right) foot was planted 0.040 ahead of his ankle. At the kneel mark z 0.20, his toes reached z 0.273, which is 0.029 (≈ 5 mm) past the sheet's front edge at z 0.244. For about 3 s his sandal stood on the table: 88 frames in the T13 simulation, and visible in `unity/Builds/dg-preview/side_55.9.png`. | `pipeline/dg_animate.py` `david_kneel`: the right foot is now planted beside him (x −0.022) and only +0.006 forward. I re-ran `dg_animate.py build`, `verify` (sample error ≤ 6e-6, 19/19 actions) and `contact`. The pick reach did not change: `pickHandToStone` is still 0.0159 / 0.007 / 0.0064 / 0.0088 / 0.0046. Toe drift fell from 0.042 to 0.032. | T13: 88 → 1 frame. The one left is at 53.10 s, during the walk → kneel cross-fade: the end of the walk stride overhangs by 0.007 (1.2 mm) for one frame. `qa/kneel-foot-fix.png` shows the new pose; the sandal ends on the paper. [A] |

The Unity copies were then stale, so I re-ran `scripts/build-apk.sh` (see T16).

**Rebuild:** `scripts/build-apk.sh` (Setup + Build, logs `unity/Logs/Setup-20261027-214548.log` and
`Build-20261027-214628.log`) exited 0 with "Succeeded, 0 errors" and 0 `error CS`. The result is
`unity/Builds/DoodLive.apk`, **39,719,519 B**, fingerprint **`a6752d5-dirty.20261027-0845`**, sha256 `6ca7da9e5928c980…`.
`GraphicsSettings.asset` light flags stayed 0/0 (no diff). The previous APK (`…-0829`) is backed up in `$DG_WORK/qa/apk_backup/`.
Disk had 1.9 GB free during the build. Free space before the next build (LESSONS L47).

### R.3 Look review: is it still a balloon toy? (D)

I viewed `model/preview_both.png`, `preview_details.png`, `anim/contact_sheet.png`, `sheet/textured_phone.png`,
`unity/Builds/dg-preview/{phone_00.5, phone_55.9, t_03.0, t_60.0, t_77.0, side_55.9}.png`, and `design/turnaround-*.png`.

- **The balloon look is gone.** Limbs taper. Elbows, knees, calves and ankle bones read in silhouette. Hands show a thumb and separate fingers, and David's open left hand reads as a hand rather than a mitten. Feet wear sandals and boots with soles. Heads have a jaw, a chin and ears, and with the in-app decals (t_03.0) both faces read clearly. The proportions are believable: David is a lean youth, and Goliath is broad and 2.7× his height. A parent would say "real figures", but more *wooden mannequin* than *Pixar*.
- **Still puffy or primitive-like in places:**
  - Goliath's armour is a smooth barrel with horizontal bands, like a quilted jacket rather than scales.
  - The red crest is a flat cushion.
  - The greaves are plain yellow tubes of nearly constant width; §11.2 forbids that look for limbs, and these are armour over limbs.
  - Goliath's boots are rounded clay lumps.
- **In-app texture artefacts:**
  - The front-projected UV0 smears printed outline ink along every side-facing surface. In side views, black stripes run along the tunic side, the bag strap and the greave edges, and the hands look dark.
  - David's face decal smears across his temple (side_55.9).
  - This comes from the §4 projection and is most visible in side and low shots. From the phone viewpoint it reads as cartoon outline.
- **Desert presence: clearly there, but modest.** From the phone (phone_00.5, t_77.0) you see two crescent dunes, rocks, a shrub, two camp hills with tents and blue and red banners, and the brook with five stones. A parent would say "the desert came up out of the page".
  - The dunes are low, about 11–12 mm, and from low angles (t_60.0) they look like small cones.
  - The tents are tiny white huts.
  - Goliath hides the Philistine camp most of the time.
- **The 3D figures stand beside their own printed drawings.** The printed line drawing of each character remains visible on the page next to the 3D figure (phone_00.5). This is by design (§4), but it doubles every character in the frame.

### R.4 Still weak (honest list)

1. **The brook strip prints into the printer's dead zone** (T15 WARN, `qa/print-bottom-margin.png`). The lowest ink is 1.0 mm from the bottom edge of the page. A home printer loses about 4–5 mm, so the brook's closing outline and the fifth printed stone will be clipped. Owner: Design (move or shorten zone B), then Desert, Sheet and Animation, because the stone positions feed `kneel_pick`. [A]
2. **`design.json desert.stageBand.polygonSheet` is incomplete** (T12 FAIL). `make_design.py coords()` keeps only the largest polygon, so the exported band covers Goliath's stage and **drops David's** (0.096 units², 34 % of the stage). Anything that checks heights against that field is not checking David's side, and `dg_desert.py verify` is one of them. My own recomputation from `timeline.json` finds **no desert vertex above 0.010 in either part**, so the shipped desert is fine. The data field is wrong. Fix (Design): export all parts, e.g. `polygonsSheet: [[...], [...]]`, and have Desert and Sheet read it. I did not change Design's schema because three roles consume it. [A]
3. **David stands at the sheet's front edge.** His marks at z 0.20 (kneel, victory, talk, pray) put his toes at z 0.234–0.240, which is inside the 0.244 sheet edge but within D8's 0.024 margin. His raised arms (victory, pray, talk gestures) overhang the edge in the air by up to 0.05. For real margin, Story should move those marks to z ≈ 0.17. That is a cross-role change: the kneel reach to the stones and the overlap with the fallen Goliath would both have to be re-checked. [A numbers, D judgement]
4. Goliath's armour, crest and greaves read as soft or tube-like (R.3). This is the weakest part of the "not a balloon" acceptance criterion. [D]
5. UV0 ink smears on side-facing surfaces, and David's face decal shows on his temple. [D, from renders]
6. **The printed sheet still has uncolourable parts.** David's sandal straps print as solid ink, so they cannot be coloured (`checks.json regionsWithoutColourableCell`). One 4.5 px strip of the bag flap is too thin to colour. The `tentDoor` region is not in `design.json palette`. [A]
7. **Not verified on a device:** the scan of the new sheet (earlier printouts will no longer track), scan colours landing on the desert, banner waving in the Android player, DGFx, and audio. `anim/preview.mp4` was not re-rendered after the kneel fix; it still shows the old forward foot. [A]

### R.5 Least sure

- **T13 simulates DGDirector in Python.** It reproduces the position lerp, the yaw LerpAngle (τ 0.12 s), the rate clamp and the cross-fade. The cross-fade is approximated: I check both clips' poses and count only the clip whose weight is ≥ 0.5. Unity's actual blended mesh could differ slightly. [D]
- The look verdicts are mine, from offline renders only. [D]

---

## Earlier QA (first build, before the redraw)

QA role, 2026-10-27. I checked the files myself and did not rely on the role reports. The checks are reproducible:
`python3 docs/david-goliath/qa/qa_check.py` (read-only; it writes `qa/qa_results.json`). The other checks below are
one-off shell commands, quoted next to their results. Screenshots and crops are in `docs/david-goliath/qa/`.
No phone was connected, so this report contains **no on-device verification**.

Evidence levels: **A** = I measured or recomputed it from the file. **D** = my judgement or inference.

## 0. Fix round, 2026-10-27 (after this QA)

A fix-round pass worked through §4 through the existing scripts (no generated file was hand-edited). `qa_check.py`
now also checks the paper bounds (T1) and closed regions (new T10), and it reads `sheetY` in T9.
**Re-run result: 10/10 PASS** (`python3 docs/david-goliath/qa/qa_check.py`, `qa/qa_results.json`). [A]

| # | Defect | Result | What changed / evidence |
|---|---|---|---|
| F1 | Sandals cut off by the art edge (T8b) | **PASS** | `make_design.py` `SHEET_Y = 0.015` → `design.json characters.*.sheetY`; `dg_build.py` places the rig there and writes UV0 `v = (y + sheetY)/artH`; `make_dg_sheet.py` translates the printed faces too and exits if ink lies within 6 px of the art edge. Re-ran `make_design.py`, `pipeline/dg_make_all.sh`, `dg_animate.py all`. Printed sheet: last ink row 1497, art bottom 1510 → 12 px paper; `checks.json inkWithin6pxOfArtEdge` all 0; closed pieces 53 → 55. `uv_check.png`: interior mean diff 0.011, >24: 0.006 %. T9 residual 4.1 / 3.3 px (unchanged). Unity Setup: "sheet template matches the angel's", Tracking PNG md5 = print PNG. Bone rest positions are character-local and did not change. [A] |
| F2 | David leaves the paper (T1b) | **PASS** | 51.4 s → `[-0.32, 0.20]`, 77.2 s → `[-0.20, 0.20]`. `build_storyboard.py validate` now reads `sheet/template.json` and allows x ±0.596, z [−1.486, +0.22]; tested: the old `[-0.32, 0.30]` is rejected. Stone check (DGPreview log, t 72.9): David (−0.120, 0.050) yaw 134°, Goliath (0.160, −0.220) yaw −46°, distance √(0.28² + 0.27²) = 0.389, bearings atan2(0.28, −0.27) = 134.0° and −46.0°, so they face each other at the baked flight distance. [A] |
| F3 | dg_13 "stick" David does not carry | **PASS** | zh 「小不点，你也想跟我打？」 / en "Little boy, you want to fight me?" (17:42, he looked down on him for being young). Regenerated with edge-tts (venv recreated: the old launcher pointed at `…/workspace/doodlive`): zh 2.19 s, en 1.93 s, maxSec 3.2, all 36 clips fit; SRTs rebuilt; fonts re-subset (no glyph missing for zh or en). [A] The new delivery has not been listened to. |
| F4 | Demo camera S09 / S11 | **PASS (offline render)** | S09: `fixed both dist 1.6 height 0.6 yaw 44` (square to the David–Goliath line); S11: `fixed david dist 0.8 height 0.4 yaw −40`. DGPreview `t_72.9`, `t_73.3`: both actors on the page, David left and Goliath right, stone beside Goliath's head; `t_75.0`: the fall toward the camera. `t_81.0`, `t_86.0`: David in front, the fallen Goliath behind him on the right. [A for the frames, D for "reads clearly"]. The FX are still not rendered in DGPreview. |
| F5 | spear_clang 8.1 vs taunt clang 8.3 | **PASS** | sfx moved to 8.3 s (taunt 8.0 + marker 0.30 s); `preview_mix.mp3` rebuilt. [A] |
| F6 | Goliath expressions look alike | **PASS (offline)** | Each expression now changes the eyes, brows and mouth: grumpy V brows + wide frown; taunt wink + one raised brow + lopsided open grin; roar white wide eyes + steep thick brows + big red oval; down closed drooping eyes + worried brows + small "o"; laugh ^^ + open D with tongue. The decal mouths get a light rim and a red interior so they read on a dark beard. `design/expressions.png`; checked downscaled to a 64 px head. [A for the files, D for phone readability] |
| F7 | DGFx mirroring (glTFast X flip) | **PASS, no change needed** | Effects work in stage-local Unity space. Bone anchors come in through `InverseTransformPoint`, and side offsets use `camRight` / `camUp` from `InverseTransformDirection` of the real camera (memory bubble: lion = screen left, bear = screen right). No effect hard-codes ±X. The ground sprites' axes (+X, +Z) are a 180° rotation on screen, not a mirror, and they are symmetric. [A, code reading; not seen in a render] |
| F8 | GraphicsSettings light flags 0 → 1 | **Reverted; Unity flips them again in one case** | `git checkout` restored 0/0. `scripts/build-apk.sh` (`-nographics`) keeps 0/0. **`DGPreview.Render` (batch with graphics) flips both back to 1**, reproduced twice (LESSONS L44). The flags were reverted again before the final build, and the final APK was built with 0/0; the file is at 0/0 now (git clean). [A] |
| F9 | CONTRACT deviations | **Done** | CONTRACT §10 D1–D8: viewer face, 40° A-pose, UV1 decals, sheetX/sheetY, dgDemo, Integration paths, preview_mix.mp3, paper-bounds rule. [A] |
| T10 | APK | **PASS** | `unity/Builds/DoodLive.apk` 38,477,741 B, sha256 `61061255…c3131`; fingerprint `23ef61c-dirty.20261027-0104` matches `.fingerprint`, `Resources/build_fingerprint.txt`, the Build log and the aapt2 versionName; "Succeeded, 0 errors", 0 `error CS`. [A] |

Still open: everything in T13 (no phone). The new Goliath faces, the S09/S11 framing, the dg_13 voice and the FX
have only been checked offline. Goliath falls toward +Z from z = −0.22, so his helmet ends past the page's front edge
(z ≈ +0.5; the preview log shows his head bone at y 0.085 from 77 s on). The play allows that, and so do the
contract and this fix round. If it should stay on the paper, the fall direction or his mark has to change (Story +
Animation). The figures are drawn 0.015 above the art bottom, while the AR holder stands them on the art bottom edge,
which puts them about 2.5 mm in front of their drawn feet. I judged that too small to matter (D).

## 1. Results

| # | Check | Result | Evidence |
|---|---|---|---|
| T1 | `timeline.json` schema (CONTRACT §6) | **PASS**, with one finding (see T1b) | `qa_check.py` T1: version 1, duration 89.0, 11 shots that tile 0–89 with no gap, all lists sorted and inside [0, 89], every clip is in §5, every `fx.at` is a §3 bone, line ids are unique, zh uses no half-width punctuation, `requestedClips` is `[]`, and all 19 clips are used. `face` uses `david`/`goliath`/`viewer`; `viewer` is a Story extension that DGDirector.cs:228 implements as +Z. [A] |
| T1b | Acting targets stay on the page | **FAIL** (minor) → fixed, see F2 | Story's validator reports that "`to` stays on the page", but two targets are past the page's front edge (z > +0.244 art units; art bottom = z 0, and the page extends 244 px below it): `t 51.4 david walk to [-0.32, 0.30]` and `t 77.2 david walk to [-0.10, 0.25]`. In AR, David kneels and celebrates on the table, off the paper. [A] |
| T2 | Every fx / sfx / music id has a handler or file | **PASS** | FX: 11 ids used and 11 `Id => "…"` classes in `Fx/DGFxEffects.cs` (e.g. :71 `dust_puff`, :455 `golden_rays`), with none missing and none extra. sfx: 19 ids, and each has `.wav`, `.mp3` and the Unity copy `Resources/DG/sfx/*.wav`. Music: 6 cues, likewise. [A] |
| T3 | Every voice line exists in zh **and** en and fits its slot | **PASS** | All 36 WAV, 36 MP3 and 36 Unity copies are present; the Unity copies are md5-identical to the sources. ffprobe: all are pcm_s16le, 44100 Hz, mono. Durations measured with ffprobe (I did not use durations.json) are all ≤ maxSec and leave ≥ 0.2 s before the next line. durations.json agrees within 0.02 s. Each SRT has 18 cues. The tightest are en dg_11 3.29/3.3 s (+0.01), zh dg_04 2.53/2.6 (gap 0.27), en dg_04 2.52/2.6 (gap 0.28), en dg_07 2.72/2.8. [A] |
| T4 | Loudness (CONTRACT §7) | **PASS** | ffmpeg ebur128: voice −16.5…−15.9 LUFS, max true peak −1.8 dBTP; all 6 music cues −20.0 LUFS. [A] I did not re-measure the SFX peak, which Music reports as −3.0 dBFS. |
| T5 | Bone names and hierarchy in both GLBs = CONTRACT §3 | **PASS** | I parsed the glTF JSON of `model/` and `anim/` for both characters. David has 27 joints, Goliath 26. No §3 bone is missing, there are no extra joints, and every parent matches §3 (including `slingCord1→2→Pouch` under `handR`, `stone` under `root`, `spear`/`shield`/`helmet`). [A] |
| T6 | Every §5 clip is in the anim GLBs | **PASS** | `anim/david.glb` has 9 animations and `anim/goliath.glb` has 10, all named `<char>_<clip>`, none missing. The Unity `Models/*.glb` files are md5-identical to `assets/.../anim/`. The Unity Setup log (Setup-20261027-133819.log:1015, :1037) lists the same 9 and 10 clips. [A] |
| T7 | UV proof image | **PASS** | I viewed `assets/david-goliath/model/uv_check.png`. The front ortho of the models textured through UV0 matches the coloured sheet, and the difference ×4 panel shows only outlines. I also recomputed it from the GLB vertices (`qa_check.py` T9): u − (x + 0.5) is a constant per mesh, −0.32 for David and +0.14 for Goliath, which equals `design.json` sheetX. Residual: ≤ 4.1 px in u and ≤ 3.3 px in v, over all 6 primitives. That is about the 3-texel inset Design recommended. [A] |
| T8 | Sheet `template.json` ↔ PNG | **PASS** | All 4 markers in `print/david-goliath-A4.png`, `sheet/reference.png`, `sheet/demo-sheet.png` and the Unity `Tracking/david-goliath-A4.png` measure 64 px and sit within 0.5 px of the template centres (pixel-centre convention). page, art and markers are identical to the angel's `web/assets/template.json`, which is required because the capture code is reused. [A] |
| T8b | Printed sheet: every region closed | **FAIL** → fixed, see F1 | No ink below y = 1509 (art bottom = 1510). David's sandal bottoms are cut off by the art rectangle edge, so the sandals are open shapes and crayon will run out of them. See `qa/crop-print-feet.png`. Goliath's feet are closed. [A] |
| T9 | Files that DGDirector / DGSetup reference exist; the Unity copies are current | **PASS** | `Resources/DG/{timeline,sfx_mix,music_cues}.json`, `Data/{clips,design,template}.json`, the demo textures and the Tracking PNG are all md5-identical to their sources. All 11 face decals named in `design.json faceDecals.*.clipExpression` exist in `Faces/`. `Fx/Resources/DGFx/DGFxUnlit.shader` is present. `ReferenceImages.asset` has 8 entries, including david-goliath. In the APK (unzipped `assets/bin/Data`), the strings `dg_18`, `theme_victory`, `golden_rays`, `DGPaperLit` and `DGFxUnlit` are all present. [A] |
| T10 | APK exists; fingerprint matches the latest build log | **PASS** | `unity/Builds/DoodLive.apk` is 38,411,569 B (13:39). `DoodLive.apk.fingerprint`, `Resources/build_fingerprint.txt`, `Logs/Build-20261027-133841.log:365` ("DoodLive build fingerprint: …") and the APK's `aapt2 dump badging` versionName all read `23ef61c-dirty.20261027-0038`. Log :4997 "Succeeded, … 0 errors"; 0 `error CS` lines. Both DG shaders are compiled in the log (:925 DGFxUnlit, :1743 DGPaperLit). [A] |
| T11 | Angel files unchanged except intended edits | **PASS**, with one open decision | `git diff --stat`: 26 files. After normalising fileIDs and sorting, the `Angel.prefab` and `Angel.controller` diffs are fileID reordering only (no property values changed). Font subsets: fontTools cmap comparison against HEAD shows **no glyph removed** from any of the 10 font files; ZCOOLKuaiLe gained 91 glyphs. All 202 subtitle and title characters are covered (zh → ZCOOL, en → Fredoka). `web/battle*` is untouched. The open decision: `ProjectSettings/GraphicsSettings.asset` has `m_LightsUseLinearIntensity` and `m_LightsUseColorTemperature` changed 0 → 1, which no role intended; this could change the angel's lighting. [A] |
| T12 | CONTRACT §9: "the existing battle entry opens the demo" | **DEVIATION** → recorded as CONTRACT §10 D5 | The Unity home had no battle entry, so Integration added a new `dgDemo` button (ARColoringController.UI.cs:445). This is reasonable, but it is a contract change the owner should accept. [A] |
| T13 | On-device: scan, placement, subtitles, FX size, audio by ear | **NOT VERIFIED** | No phone was connected. FX have **never been rendered inside Unity**: DGPreview runs with `fxEnabled = false` (DGDirector.cs `EditorInit`), and the FX preview is a .NET re-implementation outside Unity. |

## 2. Look and feel as a children's product (my judgement, D)

I looked at `storyboard/board.png`, `design/expressions.png`, `print/david-goliath-A4.png`, `model/uv_check.png`,
`anim/contact_sheet.png`, `Fx/Preview~/fx_contact.png` and all of `unity/Builds/dg-preview/` (see `qa/preview-4frames.png`).

- **Charm: good.** The chunky Paper & Crayon figures with thick outlines and big eyes look like a toy. David reads as brave and kind. The 3D models match the printed drawing closely, so the "my drawing stood up" moment should work.
- **Scariness: right for ages 4–9.** Goliath is grumpy and bearded, with no teeth, blood or weapon gore. The defeat is dizzy stars and lying still; the beheading is left out. The voice level ("scary but kid-safe") has not been listened to yet.
- **Readability: weak spots.**
  - Goliath's six expressions differ only in a small mouth under a big beard and moustache. At phone scale, *grumpy / taunt / roar / down* will look the same. Only *laugh* (open mouth) and *dizzy* (spirals) are clearly different.
  - The camera in the cinematic demo shots is poor:
    - At 72.9–73.3 s (the climax) the camera is inside Goliath's shoulder, and the stone is a grey dot.
    - From 81 to 89 s (the moral), the lying Goliath's back and helmet fill the foreground and David is half hidden. The ending scene is the least readable part of the play.
  - Most FX are pale on white paper in the offline render: dust_puff is faint and sling_trail is a short dash. hit_flash, memory_lion_bear, dizzy_stars and confetti read well.
- **Story/visual contradiction:** dg_13 has Goliath say "Little boy, you come with a stick?" / 拿根棍子, but Design deliberately gave David **no staff** (DESIGN, no bone). The children will hear about a stick they cannot see.
- **Words for 4-year-olds:** 机弦 (Chinese Union Version term) is unfamiliar to children. The en dg_01 drops "Israelites and Philistines", which the zh keeps. Both are acceptable, but the owner should choose.

## 3. The three weakest points

1. **The climax and the ending are not readable in the demo camera.** The stone hit happens off-camera or inside Goliath, and in the moral shot the lying giant covers David. This is the part children remember. [D, from the preview frames t_72.9, t_73.3, t_81–t_88.9]
2. **Nothing has been seen or heard on a real phone or by a human ear.** That covers the scan, sheet-aligned placement, subtitles, FX size, the voice and the synthetic SFX (lion, roar, crowd). The FX have never been rendered in Unity at all. [A: no device; DGPreview has FX disabled]
3. **The printed sheet has open sandal regions, and David leaves the paper.** The sandals are clipped by the art edge (T8b). Two David moves end past the page's front edge (T1b), so in AR he acts on the tabletop. Both break the "it lives on my drawing" promise. [A]

## 4. Prioritised fix list

| P | Fix | Owner | How to verify |
|---|---|---|---|
| P0 | Install and test on the phone: `scripts/install-apk.sh <serial>`, scan the printed sheet, and take screenshots with the SystemUI clock at S02 (10 s), S05 (40 s), S09 (73 s) and S11 (85 s), in zh and en. Judge FX size and subtitles, and listen to Goliath, en David and the SFX. | Integration + owner | The screenshots, plus an install log whose fingerprint matches `23ef61c-dirty.20261027-0038` |
| P0 | Decide on the GraphicsSettings light flags (0→1): revert them, or keep them after checking the angel on the device. | Owner | Angel screenshot before and after |
| P1 | Close David's sandals. Raise David (or the figure) so that the sandal bottom outline is inside the art rect, with a margin of at least 6 px. | Blender (`tools/make_dg_sheet.py`) + Design | `qa_check.py`, plus an ink row count above y = 1504 for the sandal bottoms |
| P1 | Fix the S09 and S11 demo cameras: put the S09 camera beside the pair at a larger `dist` so that pouch → forehead is in frame, and turn the S11 yaw so that David is in front of the lying Goliath. | Story | Rerun DGPreview; look at t_72.9, t_73.3 and t_86 |
| P1 | Keep the acting targets on the page: z ≤ 0.22 (51.4 s → [-0.32, 0.20]; 77.2 s → [-0.10, 0.20]). Make Story's validator use the page bounds (z ∈ [−1.51, +0.244]) instead of the art rect. | Story | `build_storyboard.py` + `qa_check.py` |
| P2 | dg_13: drop "with a stick" (e.g. "Little boy, *you* want to fight *me*?" / 小不点，你也想跟我打？), or give David a staff. | Story (or Design + Blender) | Re-voice dg_13 (zh and en), then `make_dg_voice.sh check` |
| P2 | Make Goliath's expressions distinct at phone size: a bigger open mouth for roar and taunt, brow angles, closed eyes for down. | Design | Look at the expressions at 64 px |
| P2 | FX contrast on white paper: darker dust, a longer sling arc (`span` in SlingTrail). | Effects | Render the FX in Unity (enable FX in DGPreview) |
| P3 | Move spear_clang from 8.1 to 8.3 s (taunt clang marker); give dg_04 more room (dg_05 → 22.6); en dg_11 has 0.01 s slack. | Story | `make_dg_voice.sh check` |
| P3 | Contract housekeeping: accept `face: "viewer"`, the 40° A-pose, face decals on UV1, sheetX −0.32/+0.14, the `dgDemo` home button and `preview_mix.mp3` under Music. Add the Integration paths (Scripts/, Shaders/, Editor/DGPreview.cs). | Owner (CONTRACT) | CONTRACT.md diff |

## 5. What I am least sure of

- **Marker check:** I measured the bounding box of the dark pixels around each template centre. That shows the squares are where the template says, but it does not run the app's own marker detector. `web/test.html` does that only for the angel sheet. [A for position, D for detectability]
- **UV residual of about 4 px:** I assumed it is the intended inset and not an error. The ×4 difference image supports this, but I have not traced it in `pipeline/dg_build.py`. [D]
- **Children's readability:** this is my judgement from offline renders. Only watching a child colour and watch the play can settle it.
