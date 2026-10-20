# Lessons learned (pitfalls log)

Each entry: **symptom → cause → fix → prevention**. Add new entries at the top of their section, with the date.
Mark how sure we are: **confirmed** (reproduced/fixed here) or **suspected** (likely cause, not proven).

## Device connection (adb)

### L1 · `unauthorized` that will not clear · 2026-10-18 → 10-21 · confirmed symptom, suspected cause
- **Symptom:** `adb devices` lists the phone as `unauthorized`. It stays that way after "I tapped Allow",
  after `adb kill-server`, and after a re-plug (Samsung `<samsung-serial>`; later Pixel 8 `<pixel-serial>`).
- **Cause (suspected):** the RSA prompt was dismissed or timed out on a locked screen, or it was accepted for an
  older key. The Mac's key fingerprint was `<old-key-fingerprint>`. The phone shows this
  number in the prompt; if it differs, the prompt is for another computer's key.
- **Fix:** unlock the phone → Developer options → *Revoke USB debugging authorisations* → toggle USB debugging
  off/on → unplug and replug → accept the prompt with *Always allow*. Then wait until `adb get-state` prints `device`.
- **Prevention:** `scripts/run-on-phone.sh` checks the state and prints these steps instead of failing later. Do not
  loop `adb kill-server` either: every restart cancels the prompt that is on screen.

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

## 中文速览

- **手机显示 unauthorized：** 先解锁手机。进入开发者选项，点“撤销 USB 调试授权”，再把 USB 调试关一下、开一下，拔插数据线，最后在弹窗里勾选“始终允许”。不要反复执行 `adb kill-server`，每重启一次，屏幕上的弹窗就会被取消。
- **完全看不到手机：** 换成数据线，并把 USB 模式设为“文件传输”。
- **多台设备：** 每条 adb 命令都加 `-s 序列号`，脚本里用 `ADB_SERIAL` 指定。
- **相机打不开：** 必须用 localhost（`adb reverse`）或 HTTPS 访问。
- **其他：** 演示涂色不能用洪水填充，因为线稿不封闭；UV 必须在静止姿态下计算；深色蜡笔会被当成线条擦掉；Java 用 Android Studio 自带的 JBR；装 Unity 前先查磁盘空间。
