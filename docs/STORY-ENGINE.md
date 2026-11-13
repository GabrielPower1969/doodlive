# Story engine — how a pack plays in the app

Companion to `docs/STORY-ARCHITECTURE.md`. Engine code: `unity/Assets/DoodLive/Story/` (+ the reused
`DavidGoliath/Scripts/DGActor.cs`, `DGTimeline.cs` and `DavidGoliath/Fx/`, which become `Story*` when David & Goliath
migrates).

## Pieces

| Piece | What it does |
|---|---|
| `IStoryPlayer` (Scripts/) | what the app needs from any story on the page: begin, pause, hold, replay, the current line and shot for the subtitles and titles. `DGDirector` (pack #1) and `StoryDirector` (every later pack) implement it. |
| `StoryDirector` | plays `timeline.json` on the cast (`DGActor`s) and the set: acting with cross-fades, moves and base heights (`acting.y`), lines (voice per app language + subtitle), lip sync (the speaker's `jaw` follows the voice's loudness, whatever clip is playing), props (show / hide nodes), fx (`DGFx.Play(id, node)`), sfx, music cues, the set's looping clips, and the shot-list camera in the home-screen demo. |
| `StorySetup` (Story/Editor/) | for each `engine: "story"` entry in `assets/stories.json`: copies the pack into `Assets/DoodLive/Stories/<id>/` (+ `Resources/Stories/<id>/`), sets import options, makes one page-coloured material per character and one for the set, and saves `Stories/<id>/<id>.prefab` with the director. |
| `DoodLiveSetup` | runs `StorySetup.SetupAll`, adds each pack's sheets (`<id>-A4`, `<id>-A4-demo`) to the ARCore library, puts every pack stage in the scene and on `ARColoringController.packs`. |
| `ARColoringController` | `active` = the story whose id prefixes the scanned sheet's name (markers path: the title band match; image path: the reference name). The home screen lists one demo button per pack. |
| `SheetFinder` + `Vision/` | finds and identifies any sheet by its markers and title band (`Resources/sheet_signatures.json`, built from the registry by `tools/make_sheet_signatures.py`). |

## A pack's inputs (what StorySetup reads)

```
assets/<id>/pack.json             tools/story/pack.py <id>  (cast heights, sheetX, face per clip, titles)
assets/<id>/timeline.json         tools/story/build_timeline.py <id>
assets/<id>/anim/<cast>.glb       model + skin + clips "<cast>_<clip>";  anim/clips.json (loop flags, markers)
assets/<id>/model/<set>.glb       the set, root node = set name, looping actions allowed
assets/<id>/sheet/reference.png   blank A4 (template geometry), demo-sheet.png (coloured A4), demo-colored.png (art rect)
assets/<id>/audio/voice/{zh,en}/<line>.wav, audio/music/<cue>.wav + cues.json, audio/sfx/<id>.wav + mix.json
docs/<id>/design/faces/<cast>_<expr>.png
```

## Adding a story

1. Registry entry in `assets/stories.json` (`engine: "story"`).
2. `docs/<id>/storyboard/story.py` (beats), `tools/story/voice.py <id> gen`, `tools/story/build_timeline.py <id>`.
3. Blender: characters, set, animation, sheet (see the pack's CONTRACT.md).
4. `tools/story/pack.py <id>`, `tools/make_sheet_signatures.py`, `tools/make_fonts.py` (subtitles use font subsets).
5. `scripts/build-apk.sh`; the home screen shows the new demo button; scan the printed sheet.
