# Lessons learned (pitfalls log)

Each entry: **symptom → cause → fix → prevention**. Add new entries at the top of their section, with the date.
Mark how sure we are: **confirmed** (reproduced/fixed here) or **suspected** (likely cause, not proven).

## Device connection (adb)

### L1 · `unauthorized` that will not clear · 2026-10-18 → 10-21 · confirmed (fixed 2026-10-21)
- **Symptom:** `adb devices` shows `unauthorized` on two different phones (Samsung `<samsung-serial>`, Pixel 8
  `<pixel-serial>`). It stayed that way after accepting "Always allow", revoking authorisations, re-plugging, and
  restarting adb, both inside and outside the sandbox.
- **Cause:** the Mac's adb key pair (`~/.android/adbkey`, created 2026-10-18) was bad. The phones never accepted its
  signature. It was not a phone problem; the giveaway was that **both** phones failed the same way.
- **Fix:** with adb stopped, move the key aside (`mv ~/.android/adbkey{,.bak-DATE}` and the same for `adbkey.pub`), start
  adb so it generates a new pair, then accept the new prompt once. The new key's fingerprint was `<new-key-fingerprint>`.
  The phone was authorised 162 s later.
- **Prevention:** when two phones are both stuck as `unauthorized`, suspect the Mac's key first. Do not loop `adb kill-server`: each
  restart cancels the prompt on screen. Start one server and wait.
- Print the Mac's key fingerprint (it should match the phone's prompt):
  `cut -d' ' -f1 ~/.android/adbkey.pub | base64 -d | md5 | sed 's/../&:/g;s/:$//' | tr a-z A-Z`

### L2 · Phone not listed at all · 2026-10-20 · confirmed
- **Symptom:** `adb devices` is empty, even after an adb restart.
- **Cause:** charge-only cable or USB mode set to *Charging only*.
- **Fix:** use a data cable and set the USB mode to *File transfer*, then re-plug.

### L3 · Several devices / serial changes · 2026-10-20 · confirmed
- **Symptom:** a different serial appears (a second phone was plugged in). Commands without `-s` either fail
  with "more than one device" or hit the wrong phone.
- **Fix / prevention:** always pass `-s <serial>`. The script refuses to guess when more than one device is authorised.
  Set `ADB_SERIAL`.

### L4 · Another session shares the same adb server · 2026-10-20 · confirmed
- **Symptom:** the device list changes under you while another Claude session (the Unity port) is also using adb.
- **Prevention:** one adb owner at a time. Don't `kill-server` while another session might be installing.

## Web prototype

### L5 · Camera needs a secure context · confirmed
- `getUserMedia` is blocked on `http://<lan-ip>`. Use `adb reverse tcp:8080 tcp:8080` and open `http://localhost:8080`
  on the phone (localhost counts as secure), or serve HTTPS.

### L6 · Demo colouring with flood fill leaked into the background · 2026-10-18 · confirmed
- **Cause:** the line art is not closed: the robe and wings run off the page edge, so a flood fill escapes.
- **Fix:** colour zones are drawn as polygons and **multiplied** with the line art (`tools/make_template.py`).

### L7 · Front-projection UVs must be computed in the rest pose · confirmed (design rule)
- UVs are taken from vertex X/Y **before** any bone rotation, so the wing tilt/flap is animation, not geometry.
  If you give a wing a non-zero rest rotation and then compute UVs, the colours slide off the wing.

### L8 · Line erase threshold · 2026-10-18 · confirmed
- With `max(rgb) < 120`, anti-aliased grey line edges survived as ghost lines. `< 175` with low chroma removes them
  and still keeps light crayon colours. Dark crayon (navy, black) will be treated as ink. This is a known limit.

### L13 · Phone kept running old JS after an edit · 2026-10-21 · confirmed
- **Symptom:** desktop showed the new face and feathers, but the Pixel still rendered the old model.
- **Cause:** `python3 -m http.server` sends no `Cache-Control`, so Chrome caches ES modules heuristically. The `?t=` on
  the page URL does not reach the imported modules.
- **Fix / prevention:** serve with `scripts/serve.py` (`Cache-Control: no-store`). To flush a phone that already
  cached files, use DevTools: `Network.clearBrowserCache`, then `Page.reload {ignoreCache:true}`.

### L14 · Angel "looks up from the page", always showing the top of her head · 2026-10-21 · confirmed
- **Cause:** the first version stood her along the **paper normal**. On a monitor or a sheet held up, that points
  straight at the camera.
- **Fix:** "up" comes from gravity, never from the paper. WebXR mode uses ARCore world tracking (y = up). Paper mode
  uses `devicemotion` gravity and chooses between "stand on a flat sheet" and "lean out of an upright sheet".
- **Prevention:** any new placement code must take up from gravity or the AR world, not from an image pose.

### L15 · WebXR session waits on a permission sheet · 2026-10-21 · confirmed
- `navigator.xr.requestSession('immersive-ar')` does not resolve until the user answers Chrome's
  "create a 3D map of your surroundings" sheet. Automation sees a hang. The answer is the user's to give on the phone.
- Outside XR the camera uses px units (`near=10`). In XR, three.js passes `camera.near/far` to the session, so switch to
  metres (`0.02 / 50`) before `setSession`, or everything closer than 10 m is clipped.

### L16 · Tapped to place, nothing happened · 2026-10-21 · confirmed
- **Symptom:** WebXR session running, no gold ring, taps did nothing.
- **Cause:** ARCore was not tracking. Its log said `VisualInertialState is kNotTracking` with no feature points; the camera
  image was nearly black (mean 33/255, σ 5). Without tracking there are no hit results, so `select` was ignored silently.
- **Fix:** the status line now says what ARCore needs (light, texture, slow sideways motion), and a tap without a surface
  says so. Diagnose with `adb logcat | grep -i VisualInertialState` and a viewer-pose / hit-test probe over DevTools.

### L17 · Portrait phone cut the battle shots · 2026-10-21 · confirmed
- Cinematic shots framed for landscape lost the characters on a portrait phone (horizontal FOV ≈ 35°).
- Fix: in portrait, dolly the camera out by `min(1.9, 0.8/aspect)` along the look direction (`battle.js cinematic()`).

### L18 · Phone page went "Offline", every request failed · 2026-10-21 · confirmed
- **Symptom:** a reload showed Chrome's "Offline" chip. `fetch('localhost:8080/…')` failed although the Mac server
  answered and `adb reverse --list` looked fine.
- **Cause:** the phone had **no network at all** (`dumpsys connectivity`: `Active default network: none`), so
  `navigator.onLine === false`. Chrome then fails requests immediately, even to localhost through `adb reverse`.
  Wi-Fi without internet is fine; *no* network is not.
- **Wrong turns:** `adb reconnect`, `adb usb` (restarting adbd) and new ports changed nothing. Check
  `navigator.onLine` and `dumpsys connectivity` first.
- **Fix:** connect the phone to any Wi-Fi (internet not needed). This is a phone setting, so the user does it.

### L19 · Dialogue lines cut each other off · 2026-10-21 · confirmed
- `say()` called `speechSynthesis.cancel()` first, so David's reply killed Goliath's line (`error: interrupted`).
  The interrupted line's `onend` then cleared David's subtitle.
- Fix: dialogue uses `say(…, { queue: true })`. The subtitle appears on `start`, and only its own line can clear it.
  Measure line lengths on the device (Android TTS at pitch 0.35 / rate 0.82 ran ~6 s for 20 characters).

### L21 · Phone slept in the middle of an AR test · 2026-10-21 · confirmed
- Twice the page went `hidden` / the camera image went black (mean 3/255) while waiting for the user to place the angel,
  so rAF and ARCore stopped. Fix: `navigator.wakeLock.request('screen')` when scanning or entering AR, re-acquired on
  `visibilitychange`. For AR tests: the user must hold the phone. A phone lying on the desk never starts tracking.

### L22 · Unity batch build: "script class layout is incompatible between the editor and the player" · 2026-10-22 · confirmed
- **Symptom:** `SetupAndBuild` in one `-batchmode` run imported all packages, then failed (4 errors) on URP's
  `DebugActionDesc` fields (`buttonAction: InputAction` vs legacy axis strings).
- **Cause:** `Setup()` switches `activeInputHandler` to *Both*, which changes scripting defines, but the editor domain
  was compiled before the switch, so the editor's and the player's serialized layouts differ.
- **Fix / prevention:** two runs, `Setup` then `Build`, each in a fresh editor (`scripts/build-apk.sh`). Earlier the
  batch import also hung because Unity 2022.3's Package Manager is x86-only: install Rosetta 2 first
  (`softwareupdate --install-rosetta --agree-to-license`).

### L23 · Coloured / themed sheets never detected in the Unity app · 2026-10-23 · confirmed
- **Symptom:** on the phone, the plain angel sheet was found, but the fiery / wrath / holy sheets (and their coloured
  example pages) never triggered a scan.
- **Cause:** ARCore image tracking only recognises images in its reference library, and the library held only
  `doodlive-angel-A4`. The themed sheets add large decorations and backgrounds, so to ARCore they are different images.
  The web app was not affected: it looks for the 4 black squares, and `test.html?img=…` passes on all six themed pages
  (0.74 px).
- **Fix:** `DoodLiveSetup.Sheets` lists every printable sheet (plain + `*-p1` + `*-p2`) and all go into
  `ReferenceImages.asset` at A4 size. They share markers and the art rectangle, so the capture code is unchanged.
- **Prevention:** a new printable sheet must be added to `Sheets` in the same commit, then run `scripts/build-apk.sh`.

### L24 · Angel "drifts" instead of staying on the page · 2026-10-23 · fix built, on-device check pending
- **Symptom:** after placement the angel slowly floated away; walking around her made it worse.
- **Cause:** the L14 fix put her at a fixed **world** position with no parent and no anchor. ARCore keeps correcting
  its map, and unanchored content slides with those corrections. She also stood at 66% down the page, not the middle.
- **Fix:** parent her to the `ARTrackedImage` (an augmented image is an ARCore anchor: refined while seen, remembered at
  its last pose when out of view), at the centre of the drawing, up = gravity. If the trackable is removed, re-pin her to an
  `ARAnchor` at the same pose (`ARAnchorManager` added in setup). Show mode is anchored the same way.
- **Web app:** paper mode cannot do this. Without world tracking it can only follow the sheet while the markers are
  visible. Use **放到桌上（AR）** (WebXR hit-test, world-locked) for walk-around viewing.

### L25 · Still drifting on screens / tablets; app stuck in portrait · 2026-10-23 · fix built, on-device check pending
- **Symptom:** after the L24 anchoring the angel still slid against the drawing when the camera moved, especially with
  a sheet shown on a laptop or iPad screen. On the Akita tablet the app would not rotate to landscape.
- **Cause (suspected, strongest candidate):** every reference image was pinned to A4 (21 × 29.7 cm). A sheet on a
  screen is a different physical size, so ARCore placed the image, and the angel, at the wrong depth. Wrong depth means
  wrong parallax, so she slides as you move. The orientation was locked to Portrait in `SetupPlayer`.
- **Fix:** `SetSpecifySize(false)` lets ARCore estimate the real size. `FitToSheet` re-fits position and scale to the
  latest estimate every frame (smoothed), with rotation fixed gravity-up at the placement yaw. Capture waits 1.5 s.
  The app auto-rotates (portrait plus both landscapes), and the IMGUI sizes come from the short screen edge.
- **If it still drifts only on the Akita:** compare with the Pixel on the same sheet. Drift on the Akita alone points
  to the device's VIO/IMU calibration (the ARCore certification work), not to this app.

### L26 · Blender pivots exported with world offsets; glTFast mirrors X · 2026-10-24 · confirmed
- **Symptom:** Unity logged `wristR at (-0.76, 2.55, 0)` for the GLB rig (expected ≈ (+0.35, 0.33)). Stills looked
  right, so the bug only shows once bones rotate.
- **Cause 1:** empties were parented with `matrix_parent_inverse`; the glTF exporter wrote their `location` (a world
  point) as the local translation, so the chain accumulated. Meshes attached the same way got compensated and sat
  correctly, hiding the error. **Fix:** parent with an identity parent-inverse and set the real local offset
  (`pipeline/angel_build.py empty()/attach()`). Check with pygltflib: walk parents and sum translations.
- **Cause 2:** glTFast converts glTF→Unity by mirroring X; AngelBuilder/AngelPose mirror Z. They differ by a 180°
  turn about Y, so GLB clips conjugate every bone quaternion: (x, y, z, w) → (−x, y, −z, w) (`ForRig` in DoodLiveSetup).
- **Web:** three.js keeps glTF axes, but glTF UV v points down while our CanvasTexture flips Y: flip v once on load.

### L27 · Random `ERR_CONNECTION_RESET` on one JS module · 2026-10-24 · confirmed
- The page loads ~10 ES modules in parallel; `ThreadingHTTPServer` keeps Python's default listen backlog of 5, so a
  burst of connections gets reset (always a different file). Fix: `request_queue_size = 128` in `scripts/serve.py`.

### L28 · "Fixed" twice, phone still showed the old title · 2026-10-24 · confirmed
- **Symptom:** two rebuilds in a row, the mirrored 3D title never changed on the Pixel.
- **Cause:** a CS0819 compile error made `Setup` fail; `scripts/build-apk.sh … | tail -1` swallowed the non-zero exit,
  `Build` then packaged the stale prefab, and `adb install` happily installed it. Nothing checked that the APK on the
  phone was the code just written.
- **Fix (rule: 每次修改都要留指纹，install 要对指纹):** build fingerprint `<sha>[-dirty].<UTC>` in versionName,
  in `Resources/build_fingerprint.txt` and in the app's first log line; `scripts/install-apk.sh` compares the installed
  versionName and the running log against `Builds/DoodLive.apk.fingerprint` and exits non-zero on any mismatch.
  Shell chains use `set -o pipefail`. Web pages carry `build.json` the same way.

### L29 · Editing a shell script while it runs · 2026-10-24 · confirmed
- bash reads a script incrementally; I rewrote `build-apk.sh` while a build was running and it died with
  `line 23: ked: command not found` after the build step. Never edit a script that is executing; edit, then start.

### L30 · Mirrored 3D title: stop reasoning about axes, photograph all four options · 2026-10-24 · confirmed
- Three "sign fixes" by reasoning (flip scale, flip facing, marker nodes) all produced mirrored text on the Pixel.
- Decisive test: `DOODLIVE_TITLE_TEST=1 scripts/build-apk.sh` lays out the title in all four (mirror × facing)
  combinations at once; one device screenshot showed **no mirror + Billboard facing +Z** is the readable one.
  That is now the default (`DOODLIVE_TITLE_MIRROR`/`_FRONT` unset). Rule: when an orientation bug survives one
  reasoned fix, render every combination side by side and look, instead of a second guess (each guess costs a 5-min build).

### L33 · Printed faces vanish after the scan · 2026-10-27 · confirmed (simulation), on-device check pending
- **Symptom (Design role's numpy port of `eraseLines`):** on the David & Goliath demo sheet the line-erase keeps 18 of
  1,920 face-ink texels on David; a model textured only from the scan gets a blank face.
- **Cause:** the erase treats every dark, low-chroma pixel as line art, and a face is almost all line art.
- **Fix:** faces are decals: `docs/david-goliath/design/faces/<char>_<expr>.png` on UV1 (RIG.md §4), drawn by
  `DoodLive/DGPaperLit` inside 0..1 only; `DGActor.SetFace` swaps the expression per clip (design.json `clipExpression`).
- **Prevention:** any new character with a printed face needs a decal; check a scan simulation before trusting UV0.

### L34 · Two story sheets, one capture template · 2026-10-27 · confirmed
- `ARColoringController.Capture` warps with one `Resources/template.json`. A new sheet works only if its page, markers
  and art rectangle equal the angel's (artPixels may differ if the aspect is the same: 1000×1227 vs 1128×1384).
  `DGSetup.CheckTemplate` compares them on every Setup and logs an error otherwise. The mode is chosen by the reference
  image name prefix (`david-goliath`), so the image name in `ReferenceImages.asset` is part of the contract.

### L35 · `Resources.Load` by name with .wav + .mp3 twins · 2026-10-27 · confirmed (design rule)
- The production roles deliver every clip as WAV and MP3 with the same name. In a `Resources/` folder both would be
  built into the APK and `Resources.Load<AudioClip>("…/dg_01")` would pick one at random. `DGSetup.CopyInputs` copies
  WAV only and deletes stale WAVs in the target folder.

### L36 · Skinned characters stuck in their first pose in an editor preview · 2026-10-27 · confirmed
- **Symptom:** `DGPreview.Render` (batch mode, edit mode, manual `PlayableGraph.Evaluate` + `Camera.Render`): the bones
  were kneeling (logged hip / shin heights matched clips.json) but the rendered David stood straight.
- **Cause:** without a player loop, skinning is not recomputed between renders.
- **Fix:** `SkinnedMeshRenderer.forceMatrixRecalculationPerRender = true` in the preview only. On device the player
  loop skins every frame. **Prevention:** in an editor render, log a bone position and compare it with the picture.

### L37 · Subtitles need their glyphs in the font subsets · 2026-10-27 · confirmed
- The Unity fonts are subsets (`tools/make_fonts.py`) built from `strings.json`. Story lines are not UI strings, so
  their Chinese characters were missing. `make_fonts.py` now also reads `assets/david-goliath/timeline.json` (lines and
  shot titles). Re-run it whenever a timeline's text changes; check with fontTools that no character is missing.

## Tooling (this Mac)

### L9 · `java` on PATH is a stub · 2026-10-18 · confirmed
- `/usr/bin/java` → "Unable to locate a Java Runtime". Use Android Studio's JBR:
  `export JAVA_HOME="/Applications/Android Studio.app/Contents/jbr/Contents/Home"`.

### L10 · Unity not installed; disk is tight · 2026-10-18 / 10-21 · confirmed
- No Unity Hub or editor existed when the port started. Free space dropped from 21 GiB to 13 GiB while the Unity
  session worked. Unity 2022.3 + Android module needs roughly 10–15 GiB. Check `df -h /` before installing.
  Run the `disk-audit` skill first if space is short.

### L11 · Preview tool started the wrong project · 2026-10-18 · confirmed
- `preview_start {name}` read `.claude/launch.json` from the session's original folder (another repo) and launched
  that repo's dev server. Workaround: run `python3 -m http.server 8080 -d web` yourself, then open the URL.

### L12 · Browser-pane screenshots change coordinate frame under mobile emulation · confirmed
- After `resize_window mobile`, zoom regions must use the new frame reported by the last screenshot (750×1624), not
  the old one.

### L20 · Web Speech sounds robotic; pitch tricks make it worse · 2026-10-21 · confirmed
- **Symptom:** Goliath's line via `speechSynthesis` at `pitch 0.35` sounded like a broken robot; the Chinese voice on Android is a 2010-era formant voice.
- **Cause:** Web Speech uses whatever engine the phone has; quality is not ours to choose and extreme pitch values distort it.
- **Fix:** recorded English clips in `web/assets/voice/en/` from Microsoft neural voices (`tools/make_voice.sh`, edge-tts, no key), Goliath pitched down and widened with ffmpeg. `web/battle/voice.js` plays them queued with the same onstart/onend contract and falls back to Web Speech (English voice preferred) when a clip is missing or autoplay is blocked.
- **Prevention:** a spoken line is content, not a runtime effect: record it. Keep Goliath ≤ 6 s so David's cue at 9.0 s is not pushed into the fight (12.85 s). Re-run the script after editing `LINES`.

### L31 · Demo never started in a background tab: `img.decode()` never resolved · 2026-10-24 · confirmed
- **Symptom:** in the browser pane (hidden), pressing the demo hid the home screen and then nothing happened; no error.
- **Cause:** `HTMLImageElement.decode()` can stay pending while the page is not visible, so `await img.decode()` hung.
- **Fix:** load with an `onload`/`onerror` promise (`loadDemoTexture` in `web/app.js`).
- **Prevention:** don't gate the flow on `decode()`; when a flow "silently stops", log which `await` it is stuck on.

### L32 · Chinese idle greetings 404'd · 2026-10-24 · confirmed
- **Symptom:** `greet1.mp3` / `greet2.mp3` 404 in zh; the greeting fell back to robotic TTS.
- **Cause:** the zh recordings are named `fly / wow / laugh`, the en ones `greet0-2`; one name table served both.
- **Fix:** `ZH_GREET` map in `speak()`; Unity was already right (clips are wired by name in DoodLiveSetup).
- **Prevention:** check the network panel for 404s after any voice/asset change, in both languages.

### L38 · Offline C# compile check before a 5-minute Unity run · 2026-10-27 · confirmed
- Unity's own Roslyn compiles the project's scripts in seconds:
  `dotnet <Unity.app>/Contents/DotNetSdkRoslyn/csc.dll @refs.rsp` with `-r:` for `Managed/UnityEngine/*.dll`,
  `Library/ScriptAssemblies/*.dll`, `NetStandard/ref/2.1.0/netstandard.dll` (editor scripts also need
  `NetStandard/compat/2.1.0/shims/netfx/mscorlib.dll`). Use a response file: the Bash tool's zsh does not word-split
  an unquoted `$refs`, so csc gets one giant path (CS0006).

### L39 · `.venv-tts/bin/edge-tts`: bad interpreter after the repo moved · 2026-10-27 · confirmed (Voice role)
- The venv's launcher shebang points at the old path `…/workspace/doodlive`. `tools/make_dg_voice.sh` calls
  `python3 -m edge_tts` instead; `tools/make_voice.sh` / `make_voice_angel.sh` stay broken until `.venv-tts` is
  recreated (`python3 -m venv --clear .venv-tts && .venv-tts/bin/pip install edge-tts`).

### L40 · Printed figures standing on the art-rect edge leave open regions · 2026-10-27 · confirmed
- David's sandals sat on y = 0 = the art rectangle's bottom edge, so the 6 px outline under them fell outside the art
  and was never printed; crayon runs out of an open sandal. Fix: `design.json characters.<id>.sheetY` (0.015) lifts the
  *drawing* (and UV0: `v = (y + sheetY) / artH`) while the models keep their feet on y = 0.
- Prevention: `make_design.py` fails when a silhouette is < 0.012 from the art bottom; `make_dg_sheet.py` exits when
  any ink lies within 6 px of an art-rect edge; `qa_check.py` T10 measures the printed PNG.

### L41 · "On the page" checked against the wrong rectangle · 2026-10-27 · confirmed
- The storyboard validator allowed `acting.to` z up to ±0.6, but the paper only reaches 0.244 toward the viewer from
  the art bottom (page px 1510 → 1754). Two David marks ended on the tabletop in AR.
- Fix/prevention: derive bounds from `sheet/template.json` (page and art), minus a 0.024 margin: x ±0.596,
  z ∈ [−1.486, +0.22]. Never hard-code page bounds in a validator.

### L42 · Ink-only expressions vanish on a dark beard · 2026-10-27 · confirmed
- Goliath's mouths were ink on the (usually brown) beard, so grumpy / taunt / roar / down read the same at phone size.
- Fix: change all three cues per expression (eyes, brows, mouth) and give decal mouths a light rim + red interior
  (`Fig.paint`, decals only, never printed). Check expressions downscaled to a ~64 px head before shipping.

### L43 · Shot-list camera hints are absolute, not relative to the actor · 2026-10-27 · confirmed
- `DGDirector.DriveCamera` puts the camera at target + (sin yaw, cos yaw)·dist at an absolute height. A `follow stone`
  shot at dist 0.5 ended inside Goliath; a yaw-0 ending shot looked across the giant, who falls toward +Z (the
  viewer), so he covered David. Fix: S09 fixed two-shot square to the David–Goliath line (yaw 44, dist 1.6), S11 from
  the front-left (yaw −40). Prevention: render `DGPreview` and look at the frames after any camera or mark change.

### L44 · A graphics-enabled editor run flips the URP light flags back on · 2026-10-27 · confirmed
- `GraphicsSettings.asset` `m_LightsUseLinearIntensity` / `m_LightsUseColorTemperature` went 0 → 1 again right after
  `DGPreview.Render` (batch mode *with* graphics: URP initialises and the editor saves project settings on quit).
  `scripts/build-apk.sh` (`-nographics`) left them at 0.
- Prevention: after any DGPreview / interactive editor session, `git diff unity/ProjectSettings/GraphicsSettings.asset`
  and `git checkout` it before the release build, or decide once to keep the URP values.

### L45 · Characters cast no shadows: DGPaperLit had no ShadowCaster pass · 2026-10-27 · confirmed
- Renderers were set to `ShadowCastingMode.On`, but a URP shader without a `LightMode = ShadowCaster` pass is simply
  skipped in the shadow map (no error, no warning). The actors floated over the page and, after §11, over the dunes.
- Fix: a ShadowCaster pass in `DGPaperLit` (same CBUFFER for the SRP batcher). Include `ShaderLibrary/Lighting.hlsl`,
  not `Core.hlsl` + `Shadows.hlsl`: the latter fails with `undeclared identifier 'LerpWhiteTo'`, and that error only
  shows when the shader is compiled for a renderer (the Setup log stays clean, the DGPreview log has it).
- Prevention: grep the DGPreview log for `Shader error` after any shader edit.

### L46 · APK build failed in Burst: "No space left on device" · 2026-10-27 · confirmed
- `scripts/build-apk.sh` exited 1 with `BuildFailedException: Burst compiler (1.8.24) failed running`; the real cause
  is further up the Build log (`Disk full ... Temp/Burst/...o`). The data volume had 2.7 GB free. A second run with
  1.9 GB free succeeded (Burst reused part of `Library/Bee`), so this is marginal, not fixed.
- A build that fails half-way leaves `preloadedAssets` filled in `ProjectSettings.asset` (the XR build step's
  temporary list); `git checkout` that file before the next build.
- Prevention: `df -h /System/Volumes/Data` before a build; keep ≥ 5 GB free. Free space with a disk-cleanup tool,
  never by deleting `unity/Library` mid-session.

### L47 · Editor preview at 1 unit = 1 m hides how coarse shadows are on the phone · 2026-10-27 · confirmed
- On the phone the stage is 0.3 m (demo) or about 0.17 m (A4 art width) per art width, so a shadow texel is 3 to 6
  times larger relative to the actors than in a 1:1 preview. `DGPreview` now renders the stage at 0.3 scale, and the
  URP shadow distance went from 3 m to 1.5 m (the page is always closer than that).

### L48 · A multiplier set with Material.SetColor is gamma-converted · 2026-10-27 · avoided before it shipped (computed, not observed)
- The D&G ambient tint (`_AmbTint`, meant as linear factors 1.06 / 0.97 / 0.84) would reach the shader as about
  1.13 / 0.94 / 0.67: in a Linear-colour-space project `SetColor` treats the value as sRGB and converts it.
- Use `SetVector` for numbers that are factors, `SetColor` only for real colours (palette hex values such as the sand).
- Related: a scene-wide ambient change for one story would also recolour the angel; tint per material instead.

## 中文速览

- **手机一直显示 unauthorized：** 这次的真正原因是电脑上的 adb 密钥坏了，两台手机都一样连不上，这就是判断依据。解决办法：先把 `~/.android/adbkey*` 改名备份，让 adb 重新生成一对密钥，再在手机上点一次“始终允许”。不要反复执行 `adb kill-server`，每重启一次，屏幕上的弹窗就会被取消。
- **完全看不到手机：** 换成数据线，并把 USB 模式设为“文件传输”。
- **多台设备：** 每条 adb 命令都加 `-s 序列号`，脚本里用 `ADB_SERIAL` 指定。
- **相机打不开：** 必须用 localhost（`adb reverse`）或 HTTPS 访问。
- **手机还在跑旧代码：** 用 `scripts/serve.py` 启动服务（禁用缓存）。已经缓存了的，用 DevTools 清缓存后再刷新。
- **天使总是露出头顶：** “上”方向必须取重力或 AR 世界坐标，不能取纸面法线。
- **进入 AR 卡住：** 手机上在等用户回答“允许建 3D 地图”的权限弹窗。
- **手机页面显示 Offline：** 手机完全没有网络时，Chrome 连 localhost 都不请求。连上任意 Wi-Fi 就行，有没有外网都可以。
- **竖屏看战斗：** 竖屏时镜头要自动拉远。
- **机器人声音：** 对白改为预录的英文配音（微软神经网络语音，`tools/make_voice.sh`），不再靠手机自带 TTS；缺文件时才退回 TTS。歌利亚一句控制在 6 秒内。
- **其他：** 演示涂色不能用洪水填充，因为线稿不封闭；UV 必须在静止姿态下计算；深色蜡笔会被当成线条擦掉；Java 用 Android Studio 自带的 JBR；装 Unity 前先查磁盘空间。
- **大卫与歌利亚：** 扫描会把画在纸上的脸当成线条擦掉，所以脸用贴花（UV1）；新纸必须和天使纸的标记、画框完全一致；`Resources` 里只放 WAV；字幕用到的汉字要进字体子集（`make_fonts.py` 会读 timeline.json）。
- **大卫与歌利亚（修复轮）：** 人物不能站在画框边上（线会被裁掉，区域不封闭）；“在纸上”要按整张纸算；脸部表情要在 64 像素下也能分清；镜头参数是绝对位置，改完要看预览图；带图形的 Unity 运行会把灯光设置改回 1。
- **大卫与歌利亚（重画轮）：** 着色器没有 ShadowCaster 通道就不会投影（也不报错）；阴影通道要 include Lighting.hlsl；打包前先查磁盘空间（Burst 在空间不足时报“编译器失败”）；预览要按手机上的实际尺寸渲染，阴影才看得准。
- **沙漠加强轮：** 当作系数用的材质参数要用 `SetVector`，`SetColor` 在线性色彩空间会再做一次伽马换算；只给一个故事换环境光时按材质调，不要改全局设置。
- **升级 Unity 6（6000.3.27f1，2026-10-29）：** 2022.3 个人版关不掉开屏，Unity 6 个人版可以（`PlayerSettings.SplashScreen.show/showUnityLogo = false`）；URP 17 在 6.3 里不再支持兼容模式，要把 `UniversalRenderPipelineGlobalSettings.asset` 的 `m_EnableRenderCompatibilityMode` 改成 0（打开 Render Graph），否则打包直接报错；最低 Android API 变成 25；AR Foundation 6 用 `trackablesChanged`，旧的 `trackedImagesChanged` 已过时；Unity 6 默认用 GameActivity，我们固定成 Activity；包版本照编辑器自带的 `PackageManager/Editor/manifest.json` 填（AR Foundation / ARCore 6.3.5）。
- **旗子不飘（模拟器发现，2026-10-29）：** `AnimationClip.SampleAnimation` 对非 Legacy 动画只在编辑器里有效，打包后每帧报错、旗子不动；要像人物一样用 Animator + PlayableGraph 播放（每个旗子一层 `AnimationLayerMixerPlayable`）。编辑器预览（DGPreview）看不出这个 bug，只有真机或模拟器的日志能看出来。

### L49 · Blank colouring sheets are invisible to ARCore image tracking · 2026-11-13 · confirmed
- Symptom: after the Unity 6 build neither the David & Goliath sheet nor the angel sheet could be scanned.
- Cause: the reference library held the **blank** sheets. `arcoreimg eval-img` (the tool ARCore's build runs; its
  "Low scoring image report" is in the Build log) scored them: David & Goliath blank **0/100**, angel blank 15, themed
  p1 pages 0-5; the coloured demo page 90 and a fully coloured print 100 (Google asks for >= 75). A colouring page is
  white space and a few long outlines; colouring then changes the inside, so the inside can never be the anchor.
  Doodle borders in the margins did not help (still 0): the score wants texture spread over the whole image.
- Fix: find sheets by their 4 printed corner markers (`Scripts/Vision/MarkerDetector.cs`, pure C#), tell them apart by
  the title band (`SheetIdentifier.cs`, signatures from `tools/make_sheet_signatures.py`), pose from the marker rays
  plus a depth/plane hit for real size (`SheetFinder.cs`). ARCore image tracking stays as a second path, with the
  coloured versions added to its library.
- Test: `tests/vision` (dotnet) on synthetic frames from `make_synthetic.py` (perspective, any rotation, lighting,
  blur, noise, clutter, random colouring): 3 x 200-400 frames, ~97 % found and identified with corners within 2.5 %
  of the frame, 0 wrong stories, 0 false sheets on clutter, ~4 ms per detection.
- Pitfalls met on the way: markers near the frame edge were rejected because a ring sample fell off-frame; the top-24
  blob list dropped tiny markers next to big background shapes (fixed by trying the top-10 quads and letting the title
  decide); a mirrored corner order matched the title ~0.5 (fixed: the page can never be seen from behind, so mirrored
  orders are skipped); landscape frames must be downscaled by the short side, not the width.

### L50 · A child's recording squashed by the TTS level chain sounded unnatural in the app · 2026-11-13 · confirmed
- Symptom: David's lines recorded by a child sounded "changed, unnatural" in the app.
- Checked: the app does not change them. The phone's own output (recorded with `scrcpy --audio-codec=raw`) matched
  the clip: same pitch (400 vs 403 Hz), no effect in the playback path.
- Cause: the import chain was built for flat TTS: +2 dB presence EQ (added by hand), a fast 3:1 compressor (5 ms) and
  a 3 ms / 40 ms limiter to -16 LUFS. A child's voice has 15-19 dB crest factor, so the limiter ate 2-4 dB off every
  shout; dg_17 was also time-stretched 4 %.
- Fix: `tools/dg_voice_build.py` has a `natural` chain for recordings (1.8:1 soft knee, 25 ms attack, 8 ms / 200 ms
  limiter, -17 LUFS); no EQ boost; no time-stretch — give the line time in the timeline instead (dg_17 maxSec 3.0).

### L51 · Front projection printed the sheet through the body: "two-faced balloon people" · 2026-11-14 · confirmed (renders)
- Symptom: owner: "大卫和歌利亚都是双面气球人". The back of David's head showed his printed face, the back of Goliath's
  armour its scale lines and beard, the back of the shield its boss; side faces smeared outlines into stripes. In the
  home-screen demo every face also showed the printed closed eyes and mouth under the decal's eyes: two faces at once.
- Cause: (1) UV0 = front orthographic projection for EVERY face, so the back sampled the same front drawing (mirror);
  (2) the demo play put the raw sample colouring (`demo-colored.png`, ink lines included) on the models, while a real
  scan goes through `PageWarp.EraseLines` first.
- Fix: `pipeline/dg_build.py one_sided_uvs`: only faces that face the viewer (n.z > 0.22) and are not hidden behind
  another part in rest pose (BVH ray toward +Z) keep the projection; all others take one constant UV deep inside the
  clean paint of their own (piece, region) (anchor chosen off the line art's ink, ≥ 1-4 px clearance); faces under the
  face decal also go plain (the printed eyes are only a guide). The face decal is dropped on faces with n.z < 0.40.
  `ARColoringController.LineFree` erases the lines of every story's demo texture once (RenderTexture read-back).
- Prevention: any new story character built by front projection needs the same pass (Esther/Ruth use their own
  occlusion fix, `es_characters.py`); check a BACK view render, not only the front, before calling a model done.
