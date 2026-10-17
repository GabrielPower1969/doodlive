# CLAUDE.md — map for agents

Colour-in AR angel prototype. Static web app (three.js 0.170 vendored in `web/vendor/`, no bundler).

## Commands
| What | Command |
|---|---|
| Serve locally | `python3 -m http.server 8080 -d web` |
| Run on USB Android phone | `scripts/run-on-phone.sh` (adb reverse → Chrome) |
| Rebuild sheet / line art / template.json | `python3 tools/make_template.py` |

## Map
```
source/                original line art (input) + target look reference
tools/make_template.py crop + clean line art, A4 sheet with 4 markers, template.json, demo colouring
web/app.js             UI + state machine + render loop + AR anchor
web/vision.js          markers, homography, warp, white balance, line erase, pose  (OpenCV replacement point)
web/angel.js           procedural rigged angel + animate()                          (GLB replacement point)
web/audio.js           WebAudio fanfare/chime, Web Speech voice                    (recorded audio replacement point)
docs/UPGRADE.md        path to Unity + AR Foundation + OpenCV
```

## Invariants
1. Texture space = the line-art rectangle `template.json.art` (1128×1384 source px), stretched to 1024².
   Model UV = page position: `u = X + 0.5`, `v = Y / (1384/1128)` with X,Y in art-width units. Any new model must keep this.
2. Template coordinates (`markers`, `art`) come only from `tools/make_template.py`. Never hand-edit `template.json`.
3. Camera needs a secure context: serve on `localhost` via `adb reverse`, or HTTPS.
4. Bone names in `angel.js` (`hips spine neck head shoulderL/R elbowL/R wristL/R wingL/R(+mid,tip)`) are the contract for a future GLB rig.

## Verify
Desktop: open the demo (看演示), confirm the angel renders and `window.__doodlive.action()` animates.
Scan pipeline: synthetic perspective test of `assets/demo-sheet.png` through `detectMarkers` → `warpArt` (see git history).
