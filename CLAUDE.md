# CLAUDE.md — map for agents

Colour-in AR angel prototype. Static web app (three.js 0.170 vendored in `web/vendor/`, no bundler).

## Commands
| What | Command |
|---|---|
| Serve locally (no-cache) | `python3 scripts/serve.py` (never plain `http.server`: phones cache old modules, LESSONS L13) |
| Run on USB Android phone | `scripts/run-on-phone.sh` (`ADB_SERIAL=` when several devices) |
| Device state | `~/Library/Android/sdk/platform-tools/adb devices -l` |
| Rebuild sheet / line art / template.json | `python3 tools/make_template.py` |

## Map
```
source/                original line art (input) + target look reference
tools/make_template.py crop + clean line art, A4 sheet with 4 markers, template.json, demo colouring
web/app.js             UI + state machine + render loop + AR anchor
web/vision.js          markers, homography, warp, white balance, line erase, pose  (OpenCV replacement point)
web/angel.js           procedural rigged angel + animate()                          (GLB replacement point)
web/audio.js           WebAudio fanfare/chime, Web Speech voice                    (recorded audio replacement point)
web/fx.js              light pillar, magic circle, falling feathers, burst ring
web/test.html          synthetic scan-pipeline test (PASS/FAIL)
docs/UPGRADE.md        path to Unity + AR Foundation + OpenCV
docs/LESSONS.md        pitfalls log: symptom → cause → fix → prevention
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
7. When you hit a new pitfall, add it to `docs/LESSONS.md` in the same commit as the fix.

## Verify
Desktop: open the demo (看演示), confirm the angel renders and `window.__doodlive.action()` animates.
Scan pipeline: open http://localhost:8080/test.html — renders `assets/demo-sheet.png` in a tilted, warm-tinted fake
camera frame, runs `detectMarkers` → `warpArt` → `whiteBalance`, prints PASS when every marker is within 3 px.
Phone: `scripts/run-on-phone.sh`, then scan the printed sheet (or the sheet shown on a monitor).
