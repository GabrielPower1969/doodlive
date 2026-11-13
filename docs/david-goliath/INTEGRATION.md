# David & Goliath — Unity integration (Integration role)

Owner: Integration. Binding contract: [CONTRACT.md](CONTRACT.md) §9, §11 since the 2026-10-27 redraw
(realistic-proportion characters, the paper desert set) and §12 (desert boost: front-projected scenery, sand ground). This page explains how the play gets into the
Android app, how `DGDirector` runs `timeline.json`, and how to add the next story in the same way.

```
python3 tools/gen_i18n.py && python3 tools/make_fonts.py     # after editing UI strings or any timeline's text
scripts/build-apk.sh                                          # Setup (copies every input) + Build; exit code must be 0
scripts/install-apk.sh <serial>                               # install + fingerprint check (needs a phone)
```

## 1. What goes where

```
assets/david-goliath/                      (production roles, read-only for Integration)
  anim/{david,goliath}.glb, anim/clips.json        model + skin + 19 glTF clips (Animation role); clips.json also has
                                                   david_kneel_pick markers (pick5) and desertEvents (stones to hide)
  model/desert.glb                                 desert set: 21 piece nodes under `desert`, banner wave clips (Desert role)
  timeline.json, design.json                       Story, Design
  sheet/{reference,demo-colored,demo-sheet}.png, sheet/template.json   Blender (sheet)
  sheet/ground-mask.png                            sand-ground mask fitted to the print (Sheet role, CONTRACT §12.4)
  audio/voice/{zh,en}/dg_NN.wav, audio/music/*.wav (+cues.json), audio/sfx/*.wav (+mix.json)
docs/david-goliath/design/faces/<char>_<expr>.png  face decals (Design)
        │  DGSetup.CopyInputs (called by DoodLive > Setup Project / scripts/build-apk.sh), byte-compare, copy
        ▼
unity/Assets/DoodLive/DavidGoliath/
  Scripts/  DGTimeline.cs (JSON shapes)  DGActor.cs (one character)  DGDirector.cs (the play)
  Shaders/  DGPaperLit.shader             PaperLit + face decal on UV1 + ShadowCaster (characters, desert, demo page)
            DGWater.shader                transparent brook film (no texture; ripples from position and time)
            DGGround.shader               sand ground over the whole page (§12.4): mask + ripples + painted scan, lit
  Editor/   DGSetup.cs                    copy, import options, materials, stage prefab
  Fx/       DGFx*.cs                      Effects role (DGFx.Play)
  Models/ Faces/ Textures/ Tracking/ Data/ Materials/   generated copies (never edit)
  Resources/DG/  timeline.json sfx_mix.json music_cues.json voice/{zh,en}/ music/ sfx/   (WAV only)
  DavidGoliath.prefab                     stage: DGDirector ─ DGShake ─ David, Goliath, desert, Ground; DemoPage
```

Generated files are rebuilt from the repo on every Setup; nothing is edited in the Unity editor. Only WAVs go into
`Resources/DG` (an MP3 twin with the same name would make `Resources.Load` ambiguous and double the APK).

## 2. App flow

The angel's state machine (`ARColoringController`, docs/UX-PLAN.md) is unchanged; the play is a second "mode" of
the same states.

| State | Angel (unchanged) | David & Goliath (`dgMode`) |
|---|---|---|
| Scan | 7 angel sheets in the reference library | + `david-goliath-A4` (8th image, same markers and art rectangle) |
| Capture | warp art rect → 1024² → line-erase → `pageMaterials` | same warp (one template); texture goes to `dg_david` / `dg_goliath` / `dg_desert` too; mode chosen by the reference image name prefix `david-goliath` |
| Placement | holder at art centre, faces the viewer, ×0.75 when flat | `DGHolder` at the art rectangle's bottom edge (the drawing's feet line), yaw = page bottom direction (sheet −Z, projected on gravity), 1 unit = art width; upright sheet → faces the viewer, pushed 0.3 art widths forward |
| Reveal | angel Enter, hello, theme | `DGDirector.Begin()`, chime, star burst; angel theme stopped |
| Live tap | trumpet / read title | pause ↔ resume |
| Live.Lost / app paused / grown-ups panel open | angel keeps idling | `story.Hold = true` (play frozen) |
| End | — | "完 / The End" + replay button (`story.Replay()`) |
| Home | 看演示 (angel demo) | + **大卫和歌利亚 · 看演示 / David & Goliath · demo**: sample colouring on a printed page; without AR the shot list's camera hints drive the camera, in AR the stage stands 0.75 m in front of the phone |

The web app's "battle" link (`web/battle.html`, the old procedural theatre) is untouched (CONTRACT: reference only).
Its string key `battle` contains an emoji that the app's fonts do not have, so the Unity home button uses a new key
`dgDemo`.

## 3. Coordinates

- Timeline / design axes are glTF's: x = viewer's right, y up, +z toward the viewer, art-width units. The art rectangle
  covers x ∈ [−0.5, 0.5], z ∈ [−1.227, 0] (z = 0 is its bottom edge, page bottom margin to z = +0.244).
- glTFast turns glTF into Unity by negating X (LESSONS L26). The stage keeps that: design `(x, z)` → Unity local
  `(−x, 0, z)`, design yaw → `−yaw`. With the stage's +Z toward the viewer, Unity local −X is the viewer's right, so
  positions, models and the printed drawing agree. Nothing is mirrored by scale.
- `DGDirector`'s transform is `DGFx.Stage`; `DGShake` (identity) is `DGFx.ShakeTarget`; the AR holder above them is
  written only by the controller (`FitToSheet`).

## 4. How the director works

`DGDirector` owns performance time `now` (seconds). Each `Update`: `now += dt` unless frozen (`Paused || Hold`), then
every list of the timeline is walked with its own cursor and each entry whose `t <= now` fires once:

| Timeline | What happens |
|---|---|
| `acting` | `DGActor`: new clip index, previous clip kept for the cross-fade (`blend` s, smoothstep weights in an `AnimationMixerPlayable`). Re-entering the same loop clip keeps its phase (no pop). `to` → linear move from the current position to `to` until the actor's next acting entry; locomotion clips play at `distance / time / natural speed` (ANIMATION.md §5), clamped 0.5–1.5. Facing: travel direction while moving, else `face` (`david`, `goliath`, or `viewer` = +Z), 0.12 s turn. Face decal = `design.json faceDecals.clipExpression[clip]`. |
| `lines` | voice `Resources/DG/voice/<zh|en>/<id>` in the language active at that moment; `Line` is exposed until clip end + 0.35 s (or the next line). The UI draws it. |
| `fx` | `"david.slingPouch"` → that bone's Transform → `DGFx.Play(id, bone, dur)`. |
| `sfx` | one-shot at `mix.json gainDb`; a `loop: true` id (`sling_whoosh`) runs on its own source until the next sfx of the same family (`sling_snap`). |
| `music` | the cue starts at full level on the free source of two; the previous one fades out over `cues.json crossfadeSec` (0.6 s). Music is ducked to 0.5 (≈ −6 dB) while a voice plays and follows the grown-ups music slider. |

Animation: each `DGActor` builds a manual `PlayableGraph` (Animator without controller, one `AnimationClipPlayable`
per glTF clip into one mixer). The director sets the clip times itself (loops wrap, one-shots hold their last
frame) and calls `graph.Evaluate(0)`, so pause and replay are exact and nothing advances on its own. Root motion is
off: `goliath_fall`/`down` move the root *bone* (ANIMATION.md §7.3).

Desert (§11.9 / §11.12): `desert.glb` is instantiated once under `DGShake` at the page origin, unscaled, so it gets
the same X mirror as the actors and shakes with them. Every renderer gets `dg_desert` (DGPaperLit, same scan; since §12 the GLB's UV0 is the
front orthographic page projection the characters use, `u = x/scale + sheetX + 0.5`, `v = (y/scale + sheetY)/1.227`,
baked by `dg_desert.py` with the design.json `frontUV` values, so no shader variant is needed; brook bank and stones keep
plan-view / constant UVs; `_BaseColor` sand `#F3D58E`, `_BaseAmt` 1, so unpainted pieces are sand) except the brook film (`dg_water`,
`DoodLive/DGWater`, no shadows). While David is in `kneel_pick` the director hides `desert/fiveStones/stone1..5` at
`clips.json desertEvents[].sec` (1.13 … 2.73 s into the clip) and shows his own stone from the `pick5` marker
(2.73 s). The two banner clips (`bannerIsraelWave`, `bannerPhilWave`, 2 s loops) are sampled on the desert root with
`AnimationClip.SampleAnimation` every step (the importer's Animator is removed); they keep waving after the end card.

The stone (`david_stone` renderer) is hidden until `kneel_pick` reaches `pick5` and hidden again when David leaves
`sling_release`; its flight is baked in the clip to David-local (0, 0.69, 0.33), which meets Goliath's forehead at the
current marks (ANIMATION.md §4). Pause freezes `DGFx.Paused` and pauses every AudioSource; `Stop()` (new scan, home,
another demo) stops audio and calls `DGFx.StopAll()`.

UI (`ARColoringController.UI.StoryGUI`, Paper & Crayon): the shot's title in a sun-yellow pill for 2.6 s at each shot
start, the subtitle card at the bottom (current language big, the other one small; speaker tab for everyone but the
narrator), a paper "paused" card, and at the end "完 / The End" + "再看一遍 / Watch again". All glyphs come from the
subset fonts; `tools/make_fonts.py` now also reads `assets/david-goliath/timeline.json` (lines and shot titles).

Sand ground (§12.4): `DGShake/Ground` is a quad over the whole A4 page (x ±0.62, z −1.510 … +0.244) at y 0.0005, mesh
built by `DGDirector.BuildGround` with UV0 = design (x, z). `DoodLive/DGGround` reads `dg-ground-mask.png` (copied from
`sheet/ground-mask.png`, the Sheet role's mask fitted to the real print; Design's `docs/.../ground-mask.png` left coloured
outline specks on the sand): 0 = sand (outside the art rect and over every flat drawing, so the page never shows the
printed figures twice), 128 = scan colour where painted, else sand, 255 = discarded (the brook: the real paper in AR, the
demo page in the demo). Sand = `#E3C38C` with the contract's ripple and noise terms (procedural value noise, ripples faded
by `fwidth` where they would alias). It receives shadows, so in AR the actors now shadow the paper too; it casts none.
Only the D&G stage has it; the angel scene, its materials and `RenderSettings` are unchanged. The D&G materials (actors,
desert, ground) multiply the SH ambient by `_AmbTint` (1.06, 0.97, 0.84), set with `SetVector` (a linear multiplier;
`SetColor` would gamma-convert it): the scene's lavender trilight ambient made shadows on sand look violet.

Materials: `DoodLive/DGPaperLit` = `PaperLit` (scan on UV0, unpainted paper → warm white) + the face decal on UV1,
sampled only inside 0..1 (RIG.md §4: everything but the face is pushed outside). One material per character, so each
can wear its own expression; a third, `dg_desert`, has the decal off. `DGSetup.MakeMaterials` returns them in the order
david, goliath, desert, ground (`dg_ground`, DGGround), and `ARColoringController` sets `_BaseMap` on all four (scan or demo colouring). The shader has
a ShadowCaster pass, so the actors shade the dunes and each other. The demo page (`dg_demo_page`) also uses DGPaperLit
with `_BaseAmt` 0 (printed page unchanged, but lit), so it takes the shadows in the demo.

## 5. Adding another story the same way

1. Copy `CONTRACT.md` and give each role its paths under `assets/<story>/`, `docs/<story>/`,
   `unity/Assets/DoodLive/<Story>/Fx/`. Keep the sheet geometry (page, markers, art rectangle) identical to the angel
   sheet, or the shared capture template breaks (`DGSetup.CheckTemplate` logs an error).
2. Bone names, clip names `<char>_<clip>`, one GLB per character with every clip (Animation role); UV0 = page
   position, UV1 = face decal.
3. Timeline in the CONTRACT §6 shape. `DGTimeline`/`DGDirector`/`DGActor` are story-agnostic except for the two actor
   ids `david`/`goliath` and the stone rule; generalise `DGDirector.Actor(who)` to a list when a story has more cast.
4. In `DGSetup` (or a copy): inputs, import options, materials, prefab; add the sheet to the reference library and
   pick the mode by the reference image name prefix in `ARColoringController.Capture`.
5. Strings → `tools/i18n/strings.json`, `gen_i18n.py`, `make_fonts.py` (add the new timeline path there).
6. `scripts/build-apk.sh`, then check the Setup log lines starting `DG setup:` (clips per actor, faces, renderers,
   template check) and the Build result.

## 6. Checking without a phone

`Editor/DGPreview.cs` (menu DoodLive > David & Goliath > Render preview frames, or batch mode with graphics):
opens the generated scene, runs the real `DGDirector`/`DGActor` code over the timeline in 1/30 s steps and renders the
shot-list camera to `unity/Builds/dg-preview/t_<sec>.png`, `portrait_<sec>.png`, David side close-ups
`side_<sec>.png` and fixed "phone held over the page" views `phone_<sec>.png` / `low_<sec>.png` (whole desert set), logging each actor's clip, position, yaw and a few bone heights. Effects and the IMGUI overlay are
not drawn there (edit mode runs no LateUpdate / OnGUI). Skinning needs `forceMatrixRecalculationPerRender` in edit
mode (LESSONS L36).

Checked on 2026-10-27 (Unity 2022.3.62f3), first build: Setup log `DG setup:` lines (9 + 10 clips with the clips.json
lengths and loop flags, 9/9 and 10/10 face decals, stone renderer found, template identical to the angel's), the 18
preview frames, `scripts/build-apk.sh` exit 0.

Re-checked after the §11 redraw (2026-10-27, build `a6752d5-dirty.20261027-0829`, APK 39.7 MB): Setup log
`DG setup: desert renderers 27 page + 1 water, clips [2] bannerIsraelWave(2.04s) bannerPhilWave(2.04s), stones 5 hide
at [1.133, 1.533, 1.933, 2.333, 2.733] s, own stone from 2.733 s`; new character GLBs (David 9 clips / 2 renderers,
Goliath 10 clips / 7 renderers), 9/9 and 10/10 new face decals, template identical; reference library rebuilt from the
new `reference.png` (size still estimated by ARCore, L25). DGPreview at device scale (0.3): desert pieces on their
printed patches, brook film over the printed brook, desert stones 5/5 → 4/5 (54.5 s) → 0/5 (55.9 s) with David's stone
shown from pick5, actors' shadows on the page and dunes. Not checked (no phone): scanning the new printed sheet (old
prints no longer track), the scan colours on the desert, banner waving in the player (`SampleAnimation` on Mecanim
clips is only seen in the editor), DGFx on device, audio by ear.

Re-checked after the §12 desert boost (2026-10-27, build `a6752d5-dirty.20261027-1012`, APK 39.8 MB): Setup log
`DG setup: desert renderers 29 page + 1 water`, banner clips 2, stones 5 at the unchanged hide times, `david_kneel_pick`
3.20 s (its root motion is the root *bone*, played like the fall), template identical, reference library rebuilt from the
new `reference.png`. DGPreview (`phone_<t>` at 0.5 / 30 / 55.9 / 60 / 75 / 77 / 86 s, new `right_<t>` = phone moved to
the right, `low_<t>`): the whole page is sand with ripples, two dunes rise behind David and `dune3` to the right, both camp
hills with tents and banners fill the back; at the opening Goliath hides `tentPhil3` and part of `tentPhil2` (red banner
and two tent tops show), after the fall the Philistine camp is fully visible; the brook film shows through the ground hole;
actors' shadows fall warm brown on the sand. The demo uses `demo-colored.png`, which keeps the printed lines, so the
hills show their drawn decor strokes in the demo; a real scan is line-erased. Not checked (no phone): the ground on a real
scan, ground/paper registration error, frame rate with the extra full-page fragment pass.
