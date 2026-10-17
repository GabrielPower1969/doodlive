# DoodLive — colour-in AR angel (prototype)

Colour the printed angel sheet, scan it with an Android phone, and a 3D angel wearing your colours
rises out of the page, with skeletal animation, a trumpet fanfare and a spoken voice.

This is the **fast path**: a web app (three.js) running in Chrome on the phone, with no build step.
`docs/UPGRADE.md` maps every piece to the Unity + AR Foundation + OpenCV version.

## Run on a USB-connected Android phone

```bash
scripts/run-on-phone.sh
```

The script serves `web/` on port 8080, runs `adb reverse`, and opens Chrome on the phone. Because the phone reaches the Mac at
`http://localhost`, camera access works without HTTPS.

Desktop only: `python3 -m http.server 8080 -d web`, then open http://localhost:8080 and press **看演示** (demo).

## Use

1. Print `print/doodlive-angel-A4.pdf` (or open `/print.html`). Colour it in. Keep the 4 black squares clean.
2. Press **开始扫描涂色纸** and fit the whole sheet in the dashed frame. The scan triggers by itself once all 4 squares
   are found and steady. **拍下识别** forces a shot using the frame corners.
3. The angel enters. Tap her for the trumpet, wing flaps and voice. **展示模式 / AR 模式** switches between
   tracking the paper and a turntable view (drag to spin). **线条** shows or hides the ink lines on the model.

## How it works

| Step | File |
|---|---|
| Marker detection (4 solid squares, connected components) | `web/vision.js` `detectMarkers` |
| Homography + perspective warp to a 1024² texture | `homography`, `warpArt` |
| Paper white balance + saturation, ink-line removal | `whiteBalance`, `eraseLines` |
| Paper pose from the homography (planar PnP) | `poseFromH` |
| Rigged angel; UV = position on the page (front projection) | `web/angel.js` |
| Unpainted paper → per-part default colour, rim light (shader patch) | `makeMaterial` |
| State machine: scan → bake → enter → idle ⇄ action | `web/app.js` |
| Trumpet / chime synth, zh-CN TTS voice | `web/audio.js` |

Regenerate the sheet and assets: `python3 tools/make_template.py` (needs Pillow).

## 中文速览

- 手机用 USB 连上电脑，并在手机上允许“USB 调试”，然后运行 `scripts/run-on-phone.sh`，Chrome 会自动打开。
- 打印 `print/doodlive-angel-A4.pdf` 并涂色，四个黑方块不要涂。扫描后天使会从纸上升起，点击她就会吹号角、扇翅膀、说话。
- 这是“最快可跑”的网页版。要升级成 Unity + AR Foundation + OpenCV 原生 App，路线见 `docs/UPGRADE.md`。
