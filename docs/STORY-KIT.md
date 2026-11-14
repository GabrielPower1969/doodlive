# Story kit — a new story is mostly data, not copied code

Status: 2026-11-14, branch `story-kit`. Ruth (pack #3) is migrated as the proof; the other packs are untouched or
only gained a manifest. Why: every pack so far was made by copying the previous pack's scripts and editing them, so
each new pack cost ~3,000-line scripts per role that six role agents re-read and re-wrote, and every pack edited the
same shared files (`strings.json`, `stories.json`, `library.json`, `DGFxEffects.cs`), which caused edit races between
parallel sessions. Rules this follows: `docs/STORY-ARCHITECTURE.md` ("the app is an engine; every story is a data
pack"), `docs/LESSONS.md`, each pack's `CONTRACT.md`. How to add a story now: `docs/NEW-STORY.md`.

## 1. Measured first (before any change)

Method: for each role, every per-pack script was compared with the other packs' scripts at two levels: distinct
non-comment lines (with story ids such as `ru_`, `RU_`, `ruth`, `esther` normalised away) and whole top-level
functions whose normalised source is identical in at least one other pack. Committed packs: esther (es), ruth (ru),
daniel (da). In-progress packs read from the main checkout, not committed, marked `*`: exodus (ex), prodigal (pr),
gabriel (ga). Script: kept outside the repo with the process notes.

| Role | Lines per pack (es / ru / da / ex* / pr* / ga*) | Distinct lines also in another pack | ru functions identical elsewhere |
|---|---|---|---|
| Characters `pipeline/<xx>_characters.py` | 3378 / 2951 / 3813 / 3462 / 3414 / 3019 | es 60 %, **ru 86 %**, da 67 %, ex 78 %, pr 81 % | 61 of 71 (1,361 lines) |
| Animation `pipeline/<xx>_animate.py` | 3286 / 2656 / 3193 / 3112 / 3048 / — | es 36 %, ru 59 %, da 45 %, ex 52 %, pr 50 % | 60 of 124 (654 lines) |
| Set `pipeline/<xx>_<set>.py` | 1761 / 2524 / 2879 / 3018 / 2926 / 1862 | 44-59 % | 52 of 87 (637 lines) |
| Music `tools/story/music_<id>.py` | 1587 / 1109 / 1483 / 1460 / 1304 / 1023 | 9-37 % (ruth, daniel already import Esther's engine) | 5 (18 lines) |
| Sheet | `make_sheet.py` 440 shared; wrappers da 115, ex 40, pr 40, ga 603 | wrappers 65-68 % | already shared |
| Voice | `voice.py` 752 shared; wrappers da 154, ex 212, pr 366, ga 207 | 16-68 % | already shared |
| FX `StoryFx<Id>*.cs` | 832 / 746 / 406 / 1554 / 631 / 632 | 9-50 % (runtime files most) | — (C#: line level only) |

Committed per-story pipeline code (es + ru + da, all roles above): 34,065 lines; with the three in-progress packs:
65,998 lines.

What is truly shared (moved into the kit): rig skeleton and arm frames, head building and lathe, hair shells, box
hands, robes / waist bands / mantles / hoods and their weights, belts, sandals, beard / moustache, eyelid cage, part
objects, rest-pose bake, pixel anchors and ID-map UV fixes, workbench / camera / page material, preview lights,
turntables, posetest / uvcheck / verify modes; design-axis maths, Catmull-Rom keys, blink, syllable talk, beats,
two-bone IK, gait with planted ankles, kneel geometry, arm IK, prop aiming, staff solve, action bake and write, GLB
accessor checks, look-dev materials and cameras; set primitives (box, lathe, sphere, tube, extrude, puff, ngon_top,
blade, lumpy), raster masks and dilation, drawing projections, UV-from-drawing, page / flat / texture materials,
layout checks; the music engine (MIDI parts, renderer, rooms, DSP, loudness, synthesis, sparkle / cheer).

What is story-specific (stays in the pack): cast constants (ids, heights, palettes, regions, anchors, props),
proportions, face drawings, the builders of each character (`build_ruth`, `build_naomi`, `build_boaz`), every clip
function (`ruth_glean`, `boaz_sneaky_drop` ...: acting is per character), the set's pieces and layout, cues and SFX
recipes, story paths and env prefixes, the FX that only one story plays.

## 2. What exists now

```
pipeline/story_kit/__init__.py     include(globals(), part), defined(part), missing(globals(), part)
pipeline/story_kit/characters.py   61 shared character functions (from ru_characters.py, identical in es/da/ex/pr)
pipeline/story_kit/animation.py    60 shared animation functions (from ru_animate.py)
pipeline/story_kit/stage.py        52 shared set functions (from ru_bethlehem.py)
tools/story/music_kit.py           the music + SFX engine (moved out of music_esther.py unchanged)
tools/story/merge_packs.py         per-pack manifests -> stories.json, library.json, strings.json, DGFxEffects.cs
tools/story/check.py               pack validation (STORY-ARCHITECTURE rule 6; did not exist before)
assets/<id>/manifest.json          david-goliath, esther, ruth, daniel: their entries in the shared files
docs/NEW-STORY.md                  the add-a-story checklist with two review gates and a model per role
```

### How a pack uses the kit

```python
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import story_kit
story_kit.include(globals(), "characters")
```

`include` runs the part file inside the pack module's namespace. The functions behave exactly as if they were
written in the pack (same globals, defaults evaluated there, overridable by a later `def` of the same name). That is
what lets an existing pack move onto the kit with byte-identical output, and a new pack override one function
without forking the rest. Each part's docstring lists the names a pack must define (`CHARS`, `PALETTE`, `REGIONS`,
`WORK`, `ENV` ...); `story_kit.missing(globals(), "characters")` lists the ones a pack still lacks. Two story literals
became pack constants: `ENV` (env-var / log prefix, `"RU_"`) and `PAGE_MATERIAL` (`"ru_page"`).

`music_kit` is a normal module (`import music_kit as me`, as music_ruth.py now does); `music_esther.py` executes it in
its own namespace, so Esther's and Daniel's scripts (`import music_esther as me`) keep working unchanged.

### Manifests

Each pack's `assets/<id>/manifest.json` holds its registry entry, its library book (`"after"` places it on the
shelf), its subtitle names and its FX registration (`class`, and `aliases` to reuse any registered effect under a new
id with no C# at all — generated as `StoryFxAlias`, the class Daniel already uses). `python3 tools/story/merge_packs.py`
upserts them into the shared files: existing entries keep their place, unknown entries (packs not migrated yet, the
angel, UI strings) are left alone, so the in-progress packs keep working and can switch one at a time.
`--check` reports stale files; `check.py` runs it.

## 3. Proof: Ruth through the kit

The shared functions were moved **verbatim** (only `"RU_…"` → `ENV + "…"` and `"ru_page"` → `PAGE_MATERIAL`, which
give the same strings). The whole Ruth pipeline was then regenerated three times, with work dirs outside the repo:

- **A**: the original code.
- **A2**: the original code again, in a clean worktree, to see what changes from run to run anyway.
- **B**: the kit code.

Steps per run: `ru_characters.py all`, `ru_bethlehem.py -- all`, `ru_animate.py all`, `make_sheet.py ruth`,
`music_ruth.py` and `pack.py ruth`. Each run took about 6 minutes.

| Result | Files |
|---|---|
| **B byte-identical to A** (and to A2) | **242** of 261, among them every GLB (`ruth / naomi / boaz / bethlehem`, `anim/*.glb`), `anim/clips.json`, `regions_characters.json`, ID maps, the whole `sheet/` folder, `print/ruth-A4.png`, every music and SFX file, `cues.json`, `mix.json`, `preview_mix.mp3`, `pack.json`, face decals |
| B ≠ A, but A ≠ A2 as well (the pipeline is not deterministic there) | 19: `characters.blend`, `bethlehem.blend`, `print/ruth-A4.pdf` (embedded timestamps), 16 EEVEE preview renders. In those renders the B − A pixel difference is at most 2/255 on 0–4 % of pixels, the same size as A − A2 |
| B ≠ A while A = A2 (a regression) | **0** |

`music_esther.py` and `music_daniel.py` were run in a clean worktree on the original code and on this branch: all
outputs are byte-identical (the `music_kit` split changes nothing). `python3 tools/story/check.py ruth`:
12 checks, 0 FAIL. `python3 tools/story/merge_packs.py --check`: up to date. The four manifests reproduce
`stories.json`, `library.json` and `strings.json` exactly as JSON (same values, same key order).

Found on the way. These are true on main before this branch, and nothing here fixes them:
- Regenerating Ruth from committed code does not reproduce the committed `.blend` files, preview PNGs,
  `sheet/demo-sheet.png`, `sheet/reference.png` or `print/ruth-A4.*`. The sheet / print difference is only the title
  band: `pipeline/fonts/` (kaiti, hiragino) is git-ignored, so a fresh checkout or worktree draws the title with a
  fallback font. A worktree needs those two fonts copied in before it regenerates a sheet.
- The committed Esther (`truth` cue, `cues.json`, preview) and Daniel music no longer match what the committed
  scripts produce. The music was probably rendered before the last timeline re-time and never regenerated.
- `check.py daniel` first failed on fx `steam` / `sweat`. They are `StoryFxAlias` ids, so `check.py` now reads
  aliases. `check.py --all`: esther, ruth and daniel all pass.

## 4. Before / after line counts

| File | Before | After | Change |
|---|---|---|---|
| `pipeline/ru_characters.py` | 2,951 | 1,482 | −1,469 (−50 %) |
| `pipeline/ru_animate.py` | 2,656 | 1,888 | −768 (−29 %) |
| `pipeline/ru_bethlehem.py` | 2,524 | 1,790 | −734 (−29 %) |
| `tools/story/music_ruth.py` | 1,109 | 1,109 | 0 (imports `music_kit` instead of `music_esther`) |
| **Ruth's own pipeline code** | **9,240** | **6,269** | **−2,971 (−32 %)** |
| `tools/story/music_esther.py` | 1,587 | 1,188 | −399 (engine moved out) |
| `pipeline/story_kit/` (new, shared) | — | 3,110 | `__init__` 69, characters 1,498, animation 788, stage 755 |
| `tools/story/music_kit.py` (new, shared) | — | 557 | |
| `tools/story/merge_packs.py`, `check.py` (new) | — | 342 | |

The kit is code that every pack used to carry its own copy of. A new pack built on it writes roughly Ruth's
*after* size per role (characters ~1.5k lines instead of ~3-3.8k), and its role agents read the kit's docstring
(the names it needs) instead of the previous pack's whole script. As each further pack moves across, the counts fall
by about the size of their identical copies: Esther 1,140 lines, Daniel 2,321 lines, the in-progress exodus /
prodigal about 2.9k each (identical-function lines from §1 for characters + animation + set).

Token estimate (D, my inference, not measured): reading plus writing the three Blender scripts costs about
(9,240 + 9,240) lines × ~12 tokens/line ≈ 220k tokens per pack before; with the kit about (6,269 + 6,269) × 12 ≈
150k, plus ~3k tokens of kit docstrings: about one third less on these three roles. A role usually rereads a file
several times while it iterates, so in practice the saving is a multiple of this.

## 5. Not migrated / not done (honest list)

- **Only Ruth uses the Blender kit.** Esther, Daniel and David & Goliath still carry their own copies; the
  in-progress packs (exodus, prodigal, gabriel) were not touched (they are uncommitted work of other sessions). Each
  can move the same way: include the part, delete its identical copies, rerun and compare. Functions that differ
  slightly between packs (e.g. Esther's `build_robe`, Daniel's `gait`) need a diff-and-parametrise pass first.
- **No generic clip library.** Clips are written per character (`ruth_idle`, `naomi_walk_tired` ...) and mix shared
  machinery with acting choices; extracting `idle / walk / talk / bow / kneel / hug / wave` that any contract
  skeleton can play would change Ruth's motion, so it is not byte-identical work. The kit has the pieces those clips
  are built from (gait, kneel_legs, blink, syllables, beat_curve, ik_limb, bake_clip). The cloth springs are still
  per pack: `sim_chains` / `evaluate_primary` differ between packs and stayed in ru_animate.py.
- **No JSON-placed prop library for sets.** The set kit has the primitives and the drawing / UV machinery; the
  pieces (house, olive, field) and their placement are still code in ru_bethlehem.py.
- **Music:** only the engine moved. Ruth's loop / vamp logic (`add_vamp`, `render_split`, cue spans, preview, doc
  tables) and the score are still in music_ruth.py; Daniel and the in-progress packs copied variations of it. A
  "score description" format was not designed.
- **FX:** no parametrised C# effects. Manifest aliases cover reuse with no C#; effects that differ only in colour /
  count / timing still need a class. Changing C# needs a Unity compile, which this branch did not run.
- **Shared-file coupling left:** `Fx/Preview~/Harness.cs` + `run.sh` (FX preview harness), `DoodLiveSetup.cs`,
  `docs/LIBRARY.md`, `tools/make_fonts.py` inputs, `sheet_signatures.json` / `ReferenceImages.asset` (generated from
  the registry, but regenerated by every pack's integration run). The first manifest merge rewrapped
  `stories.json` / `library.json` into one canonical layout (same JSON, same key order; only whitespace).
- **Not run:** Unity, the phone, the APK. The only C# edit is comment / whitespace inside `DGFxEffects.cs`'s
  registration block (same three statements, now between generated markers).
- `pipeline/story_mesh.py` (861 lines, already shared since Esther) was left as it is.
