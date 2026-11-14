# CLAUDE.md — map for agents

Colour-in AR angel prototype. Static web app (three.js 0.170 vendored in `web/vendor/`, no bundler).

## Commands
| What | Command |
|---|---|
| Serve locally (no-cache) | `python3 scripts/serve.py` (never plain `http.server`: phones cache old modules, LESSONS L13) |
| Run on USB Android phone | `scripts/run-on-phone.sh` (`ADB_SERIAL=` when several devices) |
| Device state | `~/Library/Android/sdk/platform-tools/adb devices -l` |
| Rebuild sheet / line art / template.json | `python3 tools/make_template.py` |
| UI strings (both apps) | edit `tools/i18n/strings.json` → `python3 tools/gen_i18n.py` → `python3 tools/make_fonts.py` (font subsets follow the strings and `assets/david-goliath/timeline.json`) |
| D&G editor preview (no phone) | `Unity -batchmode -quit -projectPath unity -executeMethod DoodLive.EditorTools.DGPreview.Render` → `unity/Builds/dg-preview/*.png`; then `git checkout unity/ProjectSettings/GraphicsSettings.asset` (L44) |
| D&G assets (models, desert, sheet, checks) | `pipeline/dg_make_all.sh` (Blender headless; `$DG_WORK` defaults to `/tmp/dg_work`) |
| Design tokens (both apps) | edit `tools/design/tokens.json` → `python3 tools/gen_tokens.py` (→ `web/tokens.css`, `DesignTokens.cs`) |
| UI icons for Unity | edit `tools/design/icons/*.svg` → `python3 tools/make_ui_icons.py` (headless Chrome → `Resources/UI/*.png`) |
| Unity APK, install, QA | `scripts/build-apk.sh` → `scripts/install-apk.sh <serial>` → `scripts/qa-shots.sh <serial> [--quick]` |

## Map
```
source/                original line art (input); the stock look reference stays local (git-ignored)
tools/make_template.py crop + clean line art, A4 sheet with 4 markers, template.json, demo colouring
web/app.js             UI + state machine + render loop + AR anchor
web/vision.js          markers, homography, warp, white balance, line erase, pose  (OpenCV replacement point)
web/angel.js           procedural rigged angel + animate()                          (GLB replacement point)
web/audio.js           WebAudio fanfare/chime, Web Speech voice                    (recorded audio replacement point)
web/fx.js              light pillar, magic circle, falling feathers, burst ring
web/style.css          Paper & Crayon UI (docs/DESIGN-DIRECTION.md); colours/sizes only via tokens.css vars
web/fonts/             OFL font subsets + each font's licence (generated)
unity/Assets/DoodLive/Scripts/ARColoringController.cs     state machine, tracking, capture, audio
unity/Assets/DoodLive/Scripts/ARColoringController.UI.cs  Paper & Crayon IMGUI (same screens as web)
unity/Assets/DoodLive/DavidGoliath/   David & Goliath play (M4): Scripts/DGDirector.cs plays assets/david-goliath/timeline.json,
                       DGActor.cs (glTF clips via PlayableGraph), Editor/DGSetup.cs (copies assets/david-goliath/** incl. the
                       desert set model/desert.glb), Shaders/ (DGPaperLit: scan + face decal + shadows; DGWater: brook;
                       DGGround: sand page, CONTRACT §12.4), Fx/ (DGFx)
pipeline/dg_*.py       Blender: dg_build (characters), dg_desert (desert set), dg_animate (19 clips); tools/make_dg_sheet.py the sheet;
                       binding brief docs/david-goliath/CONTRACT.md §11 (2026-10-27 redraw) + §12 (desert boost), how it runs: INTEGRATION.md
docs/david-goliath/    production contract + one doc per role; INTEGRATION.md = how the play runs, how to add a story
docs/DESIGN-DIRECTION.md  approved design (Figma link, 10 screens, sources); docs/UX-PLAN.md the state machine
unity/Assets/DoodLive/Scripts/ARColoringController.Library.cs  home screen = library (covers, keep reading, chapters); docs/LIBRARY.md
web/test.html          synthetic scan-pipeline test (PASS/FAIL)
docs/UPGRADE.md        path to Unity + AR Foundation + OpenCV
docs/LESSONS.md        pitfalls log: symptom → cause → fix → prevention
pipeline/story_kit/    shared Blender code of every story pack (characters / animation / stage), included by
                       pipeline/<xx>_*.py; tools/story/music_kit.py the shared music engine (docs/STORY-KIT.md)
assets/<id>/manifest.json  a pack's entries in stories.json / library.json / strings.json / DGFxEffects.cs;
                       merged by tools/story/merge_packs.py — never edit those shared files by hand
docs/NEW-STORY.md      add-a-story checklist (two review gates); tools/story/check.py <id> validates a pack
unity/, tools/make_audio.py   Unity port, owned by a separate session while in progress
```

## Invariants
1. Texture space = the line-art rectangle `template.json.art` (1128×1384 source px), stretched to 1024².
   Model UV = page position: `u = X + 0.5`, `v = Y / (1384/1128)` with X,Y in art-width units. Any new model must keep this.
2. Template coordinates (`markers`, `art`) come only from `tools/make_template.py`. Never hand-edit `template.json`.
3. Camera needs a secure context: serve on `localhost` via `adb reverse`, or HTTPS.
4. Bone names in `angel.js` (`hips spine neck head shoulderL/R elbowL/R wristL/R wingL/R(+mid,tip)`) are the contract for a future GLB rig.
5. Every adb command targets one device with `-s <serial>`. Never `adb kill-server` while another session may be
   using the phone; a restart also cancels the on-screen authorisation prompt (LESSONS L1, L4).
6. "Up" comes from gravity (devicemotion) or the WebXR world, never from the paper normal (LESSONS L14).
7. **Every build carries a fingerprint and every install verifies it.** `scripts/build-apk.sh` bakes
   `<git sha>[-dirty].<UTC time>` into the APK's versionName, `Resources/build_fingerprint.txt` and the first log line
   `DoodLive build <fp>`; `scripts/install-apk.sh` refuses to report success unless the installed versionName AND the
   running app's log match `Builds/DoodLive.apk.fingerprint`. Never `adb install` by hand; never pipe the build script
   into `tail` (it hides the exit code). Web: `scripts/stamp-web.sh` → `web/build.json`, shown bottom-right (LESSONS L28).
8. When you hit a new pitfall, add it to `docs/LESSONS.md` in the same commit as the fix.
9. **The angel is the button** (DESIGN-DIRECTION): in Live there is no button bar. Tap the 3D title = read it, tap
   anywhere else = trumpet. Only two chips stay on screen (new sheet, grown-up lock); settings live behind the 2 s hold.
10. No hard-coded colours or fonts in UI code: web uses `var(--c-*)`, Unity uses `DesignTokens.*` and `Resources/Fonts`.

## Verify
Desktop: open the demo (看演示), confirm the angel renders and `window.__doodlive.action()` animates.
Scan pipeline: open http://localhost:8080/test.html — renders `assets/demo-sheet.png` in a tilted, warm-tinted fake
camera frame, runs `detectMarkers` → `warpArt` → `whiteBalance`, prints PASS when every marker is within 3 px.
Phone: `scripts/run-on-phone.sh`, then scan the printed sheet (or the sheet shown on a monitor).

