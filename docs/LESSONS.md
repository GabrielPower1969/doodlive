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
