# Real Miracles — pack plan (this pack's index)

Shared instructions: `docs/pack-plans/00-INDEX.md`. This page holds only what is specific to this pack.

Ids: story `miracles` · prefix `mi` · env `MI_` · set `galilee` · line ids `mi_01…mi_33` · 15 shots · estimate 3:30
(real voices usually add 15-20 %; if it runs past 4:30, the first cuts are `mi_02`, `mi_17` and `mi_22`).

## State

| Stage | State |
|---|---|
| 1 Plan | done: `STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md`; `build_timeline.py miracles` runs |
| 2-8 | started 2026-11-17, **paused the same evening by the owner** (disk nearly full). Resume after disk space is freed. |
| FX | done: `StoryFxMiracles.cs` (`dust_fall`, `calm_wave`, `dig_dirt`) + `StoryFxMiraclesRuntime.cs`, preview only, `FX.md` |
| Voice | partial: `cast_miracles.json` written, zh takes up to about `mi_10`; no English yet. Resume with `voice.py miracles gen` |
| Characters | partial: `pipeline/mi_characters.py` started, not run to the end; no GLBs yet |
| Set + sheet | partial: `pipeline/mi_galilee.py` started, not run; no GLB, no `design.json`, no sheet |
| Animation, Music, Integration, Device | not started |

## What is new or risky in this pack (read before you start your role)

| # | Thing | Who | What to do |
|---|---|---|---|
| 1 | **A doll's-house interior**: the house's front is cut away so the room is seen; the roof (y 0.40) is walkable. | Set | Roof slab, parapet only at back and sides. Interior regions on the sheet or plain colours (L51). |
| 2 | **The carry group**: three actors (man `carried` + two friends) move as one along the road and up the stair. | Animation, Lead | Same speed for `walk`, `carry_front`, `carry_back`; hands at y 0.15; probe them together (CONTRACT §4). |
| 3 | **Lowering through the roof**: `lowered` drops the root 0.40 with ropes from the mat corners. | Characters (ropes mesh), Animation, Set (empty shaft) | CONTRACT §3 `ropes`, §4 `lowered`, §6 shaft. |
| 4 | **Seven actors**, four of them fixed-paint extras. | Characters | Esther `GUARDS` method; four different silhouettes; one shared clip set. |
| 5 | **Two places on one page** (house left, lake right). | Set | The yard / road lanes at the front stay clear. |
| 6 | **The roof hole** swaps `roofPatch` → `roofHole` + `rubble`. | Set, Lead | Hidden nodes in the GLB; prop events in `story.py` S05. |
| 7 | **The storm stops at once.** | FX | `calm_wave` ends `storm_rain` / `tension_dim` early (CONTRACT §8). |

## Decisions already made (do not reopen without the owner)

- Reference episode: Superbook S01E09; only two of its miracles are used (Mark 2 roof, Mark 4 storm); no demon
  story, no sower parable.
- On the sheet: Jesus, Peter, the man (with his mat). The four friends wear fixed colours.
- English voices: Qwen3-TTS only.
