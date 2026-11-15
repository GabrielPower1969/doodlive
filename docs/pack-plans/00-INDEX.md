# Pack plans — start here

Production plans for new story packs, written so that a cheaper model can execute them one step at a time.
**Read only the file a step names. Do not read other packs' scripts unless a step says so.**

## Packs planned

| Pack | Folder | State (update this line when a stage ends) |
|---|---|---|
| Jonah and the Big Fish (`jonah`) | `docs/jonah/` | stage 1 done (story, design, contract); waiting for Gate 1 |
| Joseph the Dreamer (`joseph`) | `docs/joseph/` | stage 1 done (story, design, contract); waiting for Gate 1 |

## Files in this folder (shared by every pack)

| File | Read it when | Length |
|---|---|---|
| `01-LIFECYCLE.md` | always: it is the order of work, with commands, gates and "done" for each stage | 1 page per stage |
| `02-ROLE-BRIEFS.md` | you start a role (characters, set + sheet, animation, voice, music, FX, integration) | one brief per role |
| `03-RULES.md` | before your first edit; again before any commit, Unity run or phone use | 1 page |
| `04-PITFALLS.md` | before a role starts and when something looks wrong | checklist |
| `05-QUALITY-BAR.md` | before you say a role is finished | numbers to hit |

## Files in each pack folder (`docs/<id>/`)

| File | What it is | Who changes it |
|---|---|---|
| `PLAN.md` | the pack's own index: decisions, what is new or risky in this pack, per-stage notes | lead |
| `STORY.md` | cast, beats, child-friendly choices | lead, only after the owner asks |
| `storyboard/story.py` | every shot, move, line (zh + en), cue. **Single source of timing and words** | lead |
| `DESIGN.md` | costume, faces, props, set, palette, light, music direction | lead |
| `CONTRACT.md` | ids, sizes, bones, clip names, set nodes and marks, audio ids, FX ids, file ownership | lead |
| `RIG.md` `SET.md` `ANIMATION.md` `VOICE.md` `MUSIC.md` `FX.md` | each role writes its own when it finishes | the role |

## Who reads what (the whole map)

| You are doing | Read, in this order |
|---|---|
| Anything | `03-RULES.md`, then the stage in `01-LIFECYCLE.md` |
| Characters | `02-ROLE-BRIEFS.md` §Characters → pack `CONTRACT.md` §2-3 → pack `DESIGN.md` §1, §3 → `pipeline/story_kit/characters.py` docstring → `pipeline/ru_characters.py` |
| Set + sheet | brief §Set → `CONTRACT.md` §2, §6 → `DESIGN.md` §2-3 → `pipeline/story_kit/stage.py` docstring → `pipeline/ru_bethlehem.py` → `tools/story/make_sheet.py` docstring |
| Animation | brief §Animation → `CONTRACT.md` §3-4 → `storyboard/story.py` → pack `RIG.md` → `pipeline/story_kit/animation.py` docstring → `pipeline/ru_animate.py` |
| Voice | brief §Voice → `CONTRACT.md` §7 → `STORY.md` cast → `storyboard/story.py` → `docs/ruth/VOICE.md` |
| Music + SFX | brief §Music → `CONTRACT.md` §7 → `DESIGN.md` §5 → `assets/<id>/timeline.json` → `tools/story/music_kit.py` docstring → `tools/story/music_ruth.py` |
| FX | brief §FX → `CONTRACT.md` §8 → `DESIGN.md` §4 → `docs/STORY-KIT.md` "Manifests" → `StoryFxDaniel.cs` (small example) |
| Integration | brief §Integration → `docs/NEW-STORY.md` §6 → `CONTRACT.md` §9 → `docs/STORY-ENGINE.md` |

## Model per step (owner's rule: best model writes the plan, cheaper models execute)

| Step | Model class |
|---|---|
| Story, design, contract (done) | best |
| Character geometry and faces; acting clips; set modelling | best or mid; a cheaper model may try first and must show previews at Gate 2 |
| Sheet, voice generation, re-bakes, verify, manifests, checks, docs | cheaper |
| Music score | mid; the engine run is mechanical |
| FX C# (only the ids in CONTRACT §8) | mid |
| Unity build, device run | lead, and only after asking the owner |
