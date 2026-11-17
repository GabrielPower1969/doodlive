# Real Miracles — pack plan (this pack's index)

Shared instructions: `docs/pack-plans/00-INDEX.md`. This page holds only what is specific to this pack.

Ids: story `miracles` · prefix `mi` · env `MI_` · set `galilee` · line ids `mi_01…mi_33` · 16 shots (S04b added at staging) · 3:47 base / 3:19 zh / 3:42 en
(real voices usually add 15-20 %; if it runs past 4:30, the first cuts are `mi_02`, `mi_17` and `mi_22`).

## State

| Stage | State |
|---|---|
| 1 Plan | done: `STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md` |
| 3 Characters | done: `RIG.md` (7 GLBs) |
| 3 Set + sheet | done: `SET.md` (`galilee.glb`, sheet, PDFs) |
| 4 Animation | done: `ANIMATION.md` (86 actions) |
| 4 Voice | done: `VOICE.md` (zh + en, timeline 226.9 s base / 198.9 s zh / 221.7 s en) |
| 4 FX | done: `FX.md` (`dig_dirt`, `dust_fall`, `calm_wave`; Unity-side runtime untested) |
| 5 Music + SFX | done: `MUSIC.md`; `dig_loop` changed to a one-shot by the lead (below) |
| Staging | done 2026-11-18: `story.py` re-staged to the built rigs, set and clips (below); blocking renders looked at, not in Unity |
| 6 Integration | done 2026-11-18 up to `check.py miracles`: 12 checks, 0 FAIL, 0 WARN (`--all`: 108 checks, 0 FAIL). `registry` order 9 |
| 7 Device | not started (lead: `scripts/build-apk.sh`, after asking the owner and the other sessions) |

## Lead decisions at staging (2026-11-18, for the owner)

- **The carry group never climbs the stair on screen.** A level 0.48-long group on the 46° stair cannot hold the mat at
  both ends (one carrier's hands would be 0.25 above or below the pole). S04 shows friend3 / friend4 climbing first
  and the carriers bringing the man along the front road to the stair foot; a new cut **S04b** (between `mi_10` and
  `mi_11`, no line changed) opens on the roof with the man lying behind the patch and the friends digging.
- **The carry group never turns while carrying** and moves in 0.6 s steps (`carry()` in `story.py`): `man_carried`
  has no naturalSpeed, so StoryDirector glides it; the steps keep the man and the carriers together (drift < 0.006).
  Pick-up and set-down are short eased glides. A cleaner fix is a naturalSpeed on `man_carried` plus no idle hand-over
  for carriers (Animation / engine), not done.
- **Roof hole 0.12 vs mat 0.30**: not fixed in the set. S06's camera stays above the ceiling's height (0.42 landscape,
  ~0.60 portrait), so the ceiling's underside, where the ropes pass outside the hole, is never seen; for the first
  ~1 s of `lowered` the mat ends still cross the roof slab. Owner: accept, or ask Set for a 0.32 × 0.14 hole.
- **On the roof** only friend1 / friend2 kneel (left / right of the hole); friend3 / friend4 stand at the front
  corners: kneeling in front of the hole puts their feet over the roof's open front edge.
- **Boat**: Jesus sleeps at (0.48, −0.375) with his head on the cushion; Peter stands at (0.38, −0.28) on the front side
  and wakes Him from (0.455, −0.275), then steps back so S12 sees Jesus. S09 / S10 cameras moved to the right (yaw 40 /
  45) so Peter does not hide the sleeper; Jesus' legs are still partly behind Peter.
- **Peter's headroom** inside is 0.004 (ceiling 0.385, Peter 0.381). No clip raises his head above rest height. In
  S05 he stands under the roof patch (the dust falls on his head); elsewhere at `PETER_IN`.
- **`dig_loop`** is a one-shot sized to end at S05 (zh), because StoryDirector stops loops only at a music cue
  (`MUSIC.md`). Music cues were not re-rendered: every event they hit on kept its time.
- The friends' shared face drawings were copied to `friend1_…`–`friend4_<expr>.png` (StorySetup loads
  `<cast id>_<face>.png`, as Esther's guards).

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
