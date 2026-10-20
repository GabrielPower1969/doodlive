# DoodLive — colour-in AR angel (prototype)

Colour the printed angel sheet, scan it with an Android phone, and a 3D angel wearing your colours rises out
of the page, with skeletal animation, a trumpet fanfare and a spoken voice.

**Status:** web prototype (three.js in Chrome on the phone, no build step). The demo mode and the scan pipeline
are verified on desktop. Runs on a Pixel 8 (Android 17, Chrome 151): demo mode and the camera scan view checked on 2026-10-21; a full scan of a printed sheet is not yet tested. A Unity +
AR Foundation + OpenCV port is in progress under `unity/` ([docs/UPGRADE.md](docs/UPGRADE.md)).

## Requirements

| What | Version / note |
|---|---|
| Mac with Python 3 + Pillow | for the server and `tools/make_template.py` |
| Android platform-tools (adb) | `~/Library/Android/sdk/platform-tools` (Android Studio install) |
| Android phone with Chrome | USB debugging on; data cable; USB mode = File transfer |
| Optional: ARCore ("Google Play Services for AR") | only needed for the Unity version |

## Quick start

```bash
scripts/run-on-phone.sh
```

This serves `web/` on port 8080, runs `adb reverse`, and opens Chrome on the phone. Because the phone reaches the
Mac at `http://localhost`, the camera works without HTTPS. With more than one phone attached:

```bash
ADB_SERIAL=<pixel-serial> scripts/run-on-phone.sh
```

Desktop only (demo, no camera): `python3 scripts/serve.py`, open http://localhost:8080, press **看演示**.

## Use

1. Print `print/doodlive-angel-A4.pdf` (or open `/print.html`) and colour it in. Keep the 4 black squares clean.
2. Press **开始扫描涂色纸** and fit the whole sheet in the dashed frame. The scan fires by itself once all 4 squares
   are found and steady. **拍下识别** forces a shot using the frame corners.
3. The angel rises out of the page. Tap her for the trumpet, wing flaps and voice. **线条** shows or hides the ink lines.
4. **放到桌上（AR）** (ARCore phones): she leaves the page and stands on a real surface, world-locked (WebXR).
   Move the phone until a gold ring appears, then tap to place her. Tap her for the fanfare; tap elsewhere to move her.
   **纸上模式 / 展示模式** switches between following the sheet (upright by gravity) and a turntable (drag to spin).

## How it works

| Step | Where |
|---|---|
| Marker detection (4 solid squares, connected components) | `web/vision.js` `detectMarkers` |
| Homography + perspective warp to a 1024² texture | `homography`, `warpArt` |
| Paper white balance + saturation, ink-line removal | `whiteBalance`, `eraseLines` |
| Paper pose from the homography (planar PnP) | `poseFromH` |
| Rigged angel, 3D face (blink, lip flap), feathered skinned wings; UV = page position | `web/angel.js` |
| Light pillar, magic circle, falling feathers, burst ring | `web/fx.js` |
| World-locked placement (WebXR hit-test) / gravity-up paper placement | `web/app.js` `enterXR`, `placeOnPaper` |
| Unpainted paper → per-part default colour, rim light (shader patch) | `makeMaterial` |
| State machine: scan → bake → enter → idle ⇄ action | `web/app.js` |
| Trumpet / chime synth, zh-CN TTS voice | `web/audio.js` |

Regenerate the sheet and the assets: `python3 tools/make_template.py`.

## David vs Goliath (battle theatre)

`/battle.html`: a 33-second choreographed fight. Goliath marches in and taunts, then sends a ground shockwave, a flying spear
slash and a shield-slam ring. David jumps, ducks, charges and winds up the sling. The stone hits in bullet time, Goliath
topples, and victory light follows. Synth score (drums, D-minor ostinato, brass), synth SFX, TTS voices with
subtitles. Plays as a cinematic, or with **放到桌上看（AR）** on a real table (WebXR). Code: `web/battle/`.

## Themed colouring sheets

`print/angel-fiery.pdf`, `angel-wrath.pdf`, `angel-holy.pdf`: same angel and markers (they work with the AR app), three
styles, one shared 6-colour palette (`tools/palette.py`). Page 2 is a coloured example. Regenerate with
`python3 tools/make_theme_sheets.py`.

## Known limits

- Paper mode uses an assumed focal length (≈65° FOV), so alignment to the sheet is approximate. WebXR mode is world-locked
  but no longer tied to the sheet (WebXR image tracking is still behind a Chrome flag).
- Dark crayon colours (navy, black) are treated as ink by the line eraser.
- The voice uses the phone's TTS. Its quality depends on the installed Chinese voice.

## Project layout

```
source/   input line art + target-look reference     tools/    asset generators
web/      the app (served as-is)                     scripts/  run-on-phone.sh
print/    printable A4 sheet                         docs/     UPGRADE.md, LESSONS.md
unity/    Unity port (work in progress)
```

## Troubleshooting

See [docs/LESSONS.md](docs/LESSONS.md). The most common problem is a phone stuck as `unauthorized` (L1).

## 中文速览

- **运行：** 手机用数据线连接电脑，开启 USB 调试，然后运行 `scripts/run-on-phone.sh`，Chrome 会自动打开。连了多台手机时，用 `ADB_SERIAL=序列号` 指定其中一台。
- **玩法：** 打印 `print/doodlive-angel-A4.pdf` 并涂色，四个黑方块不要涂。扫描后天使会从纸上升起，点击她就会吹号角、扇翅膀、说话。
- **遇到问题：** 先看 `docs/LESSONS.md`，最常见的是手机一直显示 unauthorized。
- **升级路线：** Unity + AR Foundation + OpenCV，见 `docs/UPGRADE.md`。
