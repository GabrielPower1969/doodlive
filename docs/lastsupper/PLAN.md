# The King Who Serves — pack plan (this pack's index)

Shared instructions: `docs/pack-plans/00-INDEX.md`. This page holds only what is specific to this pack.

Ids: story `lastsupper` · prefix `ls` · env `LS_` · set `jerusalem` · line ids `ls_01…ls_36` · 13 shots · estimate
4:03 (243 s by `build_timeline.py`; real voices usually add 15-20 %; if it runs past 4:30, the first cuts are `ls_22`
(James's whisper), `ls_13` (the healing and the children) and `ls_04` (Peter's "we'll be important", but then `ls_17`
loses its set-up), in that order).

## State

| Stage | State |
|---|---|
| 1 Plan | done 2026-11-18: `STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md`, `assets/lastsupper/manifest.json` (no registry); `build_timeline.py lastsupper` runs |
| Gates 1-2 | the roles were started after them; the owner's answers are in Hours, not here |
| 3 Characters / Set + sheet | done: `RIG.md`, `SET.md` |
| 4 Animation / Voice / FX | done: `ANIMATION.md` (99 actions), `VOICE.md` (timeline 260.5 s), `FX.md` |
| 5 Music | `cues.json` and 12 cues present; `MUSIC.md` belongs to the music session |
| Staging | done 2026-11-18: `story.py` re-staged to the built rigs, set and clips (below); blocking renders (real GLBs posed by a copy of the director's move logic, phone camera) looked at, not in Unity. Line text, order and every line / music / sfx time unchanged (260.47 s) |
| 6 Integration | done 2026-11-18 up to `check.py lastsupper`: 12 checks, 0 FAIL, 0 WARN (`--all`: 120 checks, 0 FAIL). `registry` order 10, `faces.json` from `ls_characters.py` CLIP_EXPRESSION |
| 7 Device | not started (lead: `scripts/build-apk.sh`, after asking the owner and the other sessions) |

## Lead decisions at staging (2026-11-18, for the owner)

- **Riding without a director change.** StoryDirector walks the donkey at its naturalSpeed but glides the rider (ride
  clips have no naturalSpeed), so Jesus ran up to 0.061 ahead of the seat. `ride()` in `story.py` cuts each ride into
  equal 0.6 s steps (0.6875 s for the 0.0825 steps of S02 / S03) with the same mark, dt and face for both; the donkey
  plays at 1.25-1.34x so it ends each step on its next beat, then gets an `idle` beat; Jesus keeps his ride clip.
  Drift in a Python copy of the director: <= 0.008 (yaw <= 0.2 deg). Cleaner later: a `rideSpeed` travel mode in
  StoryDirector (linear, no idle hand-off), not done (C#, needs Unity). While the donkey stands (`idle`), the rider
  sinks up to 19 mm into the blanket at the worst phase (`rideCheck`).
- **S01 no longer walks on the spot**: everyone `idle` until the procession moves (it used to play `walk` in place for 8 s).
- **Faces on the donkey**: `ride_talk` and the S01 bray keep `face="house"` (the donkey's heading).
- **Cameras moved** so the speaker is not hidden: S03 `fixed jesus` yaw -95 (from the house side: donkey and Jesus
  face the camera, Peter at the stones beside them; at yaw -25 Peter stood between the camera and Jesus); S06 yaw 20
  (Jesus at the basin is beside Peter, not behind him); S07 `fixed lowTable` yaw 25 (bench row, the stand and the
  kneeling place all in view; Jesus has his back to the camera while he pours, which hides the missing jug); S08 yaw 5
  (the pair in profile); S09 height 0.35 / dist 0.6 (looks down over Peter at the bench row); S12 yaw 55.
- **S07 / S08 kneeling**: `kneel_wash` blend 0.8 (no kneel-down clip); the basin is hidden (grow 0.3) while Jesus walks
  and pops back (grow 0.4) when He kneels. S07 walk STAND -> WAY (-0.15, -0.36) -> ROUND -> WASH andrew (rate 1.03),
  S08 one straight move along the lane (0.23 in 2.2 s, 1.08x); Peter's `refuse` waits until Jesus kneels.
- **Set conflicts (SET.md §3)**: ROOM_J = STAND; SELLER2_SIDE (0.57, -0.38); `jerusalem/crowd` hidden from S04 on.
- **S05**: seller2 chases the coins in two moves (COINS, then COINS2 (0.58, -0.26)) so he scuttles through `ls_11`.
- **S12**: Peter scoots (eased glide during `serve_rise`) to Andrew's front-left, 0.11 from him at 30 deg, both turned
  to each other; nearer the bench his toes would reach it. `nudge` faces the viewer. Jesus takes `sit_supper` at the
  S12 cut (`lift_cup` held His empty hands up for 13 s). `water_pour` is on `andrew.footR`.
- **Not changed**: `tools/story/sheet_lastsupper.py` stays: besides the stand-in registry entry it prints the
  part-anchored pieces as detail lines and holds the textured-render scene (same role as `sheet_daniel.py`), and
  `ls_jerusalem.py` / SET.md / RIG.md / CONTRACT.md name it.

## What is new or risky in this pack (read before you start your role)

| # | Thing | Who | What to do |
|---|---|---|---|
| 1 | **Reused Jesus and Peter** from Real Miracles, which is itself paused mid-stage (its characters are not final yet). | Characters, Lead | Reuse `build_jesus` / `build_peter` unchanged (CONTRACT §2). If Miracles changes them later, this pack rebuilds; never fork them. Wait for Miracles' Gate 2 look on Jesus and Peter before stage 3 here. |
| 2 | **A donkey with a rider** (quadruped on the sheet in side view + the ride pair). | Characters, Animation, Lead | Daniel lion skeleton (CONTRACT §3); `ride` seat at 0.155; probe the pair at rest and mid-stride (CONTRACT §4). |
| 3 | **The upstairs room on a closed ground storey** (floor y 0.10), doll's-house front. | Set | Sill ≤ UPPER + 0.04; no ceiling over the front half; interior regions on the sheet or plain colour (L51). |
| 4 | **The kneeling lane** in the room: Jesus kneels 0.11 in front of the bench, close to the low table's corner. | Set, Animation, Lead | CONTRACT §6 room clearance; probe `kneel_wash` with a seated disciple at UPPER. If it does not fit, the lead moves the table, not the bench. |
| 5 | **Eight actors**, five of them fixed-paint extras in two groups (disciples, sellers). | Characters | One `extras_paint.png`; one shared clip set per group. |
| 6 | **Prop swaps** (table2 → tipped, cages → open, basin and jug, bread, cup). | Set, Characters, Lead | Hidden nodes in the GLBs; prop events in `story.py` S05, S07, S10-S12. |
| 7 | **The temple scene must read as firm, not violent.** | Animation, FX, Music | `tip_table` tips one table away from Him; no grabbing people, no whip; `doves_fly` is joyful; the music turns tender (DESIGN §5). |
| 8 | **The cup line** mentions His life given once; no blood, no cross. | Voice | Gentle delivery (`dir`); the owner listens to `ls_32` first. |

## Decisions already made (do not reopen without the owner)

- Reference episode: Superbook S01E10. Used: the donkey entry, the stones, the temple tables, the "who is greatest"
  squabble, the foot washing (Peter's "not my feet" → "wash all of me"), the bread and the cup. Left out: the frame
  story's modern characters, Mary's perfume at Bethany, Judas's bargain, the Roman officials, the arrest. Judas is one
  narrator sentence (`ls_27`).
- On the sheet: the donkey, Jesus, Peter. John, James, Andrew and the two sellers wear fixed colours.
- Jesus and Peter look and sound the same as in Real Miracles.
- English voices: Qwen3-TTS only.
