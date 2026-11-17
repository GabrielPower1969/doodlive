# He Is Risen! — pack plan (this pack's index)

Shared instructions: `docs/pack-plans/00-INDEX.md`. This page holds only what is specific to this pack.

Ids: story `risen` · prefix `rs` · env `RS_` · set `garden` · line ids `rs_01…rs_39` · 12 shots · estimate 3:53
(233 s by `build_timeline.py`, no voices yet; real voices added 7 % in The King Who Serves and up to 15-20 % before).
If it runs past 4:15, the first cuts are `rs_06` (Mary's "I just want to be near Jesus"), `rs_21` (John's "He said He
would rise", but then S07 ends on Peter), `rs_29` (Mary tells the room; S10 then opens on the narrator) and `rs_12`
(Joanna's "It's empty!"), in that order.

## State

| Stage | State |
|---|---|
| 1 Plan | done 2026-11-18: `STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md`, `assets/risen/manifest.json` (no registry, no fx class); `build_timeline.py risen` runs (12 shots, 39 lines, 111 acting beats, 233.1 s estimate). `merge_packs.py` not run (it would add the library book to the shared files before Gate 1) |
| Gates 1-2 | the roles were started after them; the owner's answers are in Hours, not here |
| 3 Characters / Set + sheet | done: `RIG.md`, `SET.md` (stone enlarged to 0.39, rolled-aside centre (−0.113, −0.410), seat top 0.38) |
| 4 Animation / Voice / FX | done: `ANIMATION.md` (68 actions), `VOICE.md` (timeline 247.4 s), `FX.md` (`tomb_glow`, `butterflies`) |
| 5 Music | `cues.json` and 12 cues present; `MUSIC.md` belongs to the music session |
| Staging | done 2026-11-18: `story.py` re-staged to the built rigs, set and clips (below); blocking renders (real GLBs posed by a Python copy of the director's acting / move / camera logic, phone camera) looked at, not in Unity. Line text, order and every line / shot / music time unchanged (247.42 s); `build_timeline.py risen` prints no warning |
| 6 Integration | done 2026-11-18 up to `check.py risen`: 12 checks, 0 FAIL, 0 WARN (`--all`: 132 checks, 0 FAIL). `registry` order 11, `faces.json` from `rs_characters.py` CLIP_EXPRESSION |
| 7 Device | not started (lead: `scripts/build-apk.sh`, after asking the owner and the other sessions) |

## Lead decisions at staging (2026-11-18, for the owner)

- **Speeds** from `clips.json`: V_WALK 0.090, V_RUN 0.241, V_PUFF 0.166, V_JOY 0.197. Every move now runs at ≤ 1.19x
  (Joanna's S04 run-off; she and Mary start running 0.5 s before the end of `rs_12`, so both arrive by the cut).
- **The angel never turns**: every angel act is `face="viewer"`; ANGEL_Y 0.311 (seat rig-local 0.069 on the 0.38
  top). CONTRACT §4-§6, SET.md and DESIGN.md now say 0.311 / 0.39-across stone. After `wings_open` it returns to
  `sit_stone` (it used to hold the last frame for 13 s).
- **S03 stone swap**: two `angel_light` columns, one on the closed stone (from 0.8 s) and one on the rolled-aside
  place (from 1.2 s), so the closed stone shrinks away (2.0, grow 0.3) and the rolled stone (2.2) and the angel (2.4)
  grow inside bright light; `dust_burst` + `rumble` unchanged. Camera yaw −25 → **40**: at −25 the women had their
  backs to the camera and hid the door; at 40 they are in profile, the open door and the angel both show.
- **S06 race in stages** (the old one was over 5 s into a 15.6 s shot, so Peter said "wait for me" standing at the
  tomb): John runs to the gate and waits, looking back; Peter puffs to a stop at PATH_R (`puff`) while the narrator
  says "faster than Peter"; John waves him on (`wave_hurry`, `rs_17`) and runs on to the door; Peter runs on during
  `rs_18` and puffs at his mark. Same marks and straight legs as before; both start from `idle` (no run on the spot).
- **S07**: John steps aside with `run` (no glide) to JOHN_ASIDE (−0.42, −0.15); at (−0.40, −0.22) he stood 0.073
  from Peter and their bodies touched in `amazed`. Clearance (own check against `garden.glb`): 0.084.
- **S09**: hands let go together when Jesus starts `rs_27`; Mary `cheer`s 1.6 s through "I am alive!", then runs
  only the first leg (0.8 s, MARY_MEET → (−0.10, 0.04)) before the cut. Jesus `wave`s and is **not** removed on screen:
  the cut hides Him (S10 starts with `hide("jesus")`). `butterflies` anchored on `mary.root` (the flower beds are out of
  the S09 frame), `butterflies` / `golden_rays` end at the cut.
- **Appearing** (`appear()`): Jesus is placed while hidden 1.0 s early, `angel_light` starts on Him 0.9 s early (it
  fades in over 1 s), and He grows in over 1.0 s (was 0.6) inside the bright column. Leaving is always on a cut.
- **S10**: `show_hands` faces the viewer (facing John it put His back to the camera); Mary cheers 3.4 s (was 18.6 s),
  John / Peter / Mary go back to `idle` after the shock; Jesus `idle` facing the viewer after `eat_fish`.
- **S11**: John stands right of Peter (JOHN_S11 (0.51, −0.45), clearance 0.061 to the bench) instead of right behind
  Thomas; Peter stops talking when Thomas speaks; Thomas `idle` after `shock`; `reach` 0.4 s earlier so the touch
  (1.13 s) is held before `kneel_worship`.
- **S12**: one row, nobody behind another: Thomas (−0.36, −0.08), Mary, Jesus, Peter (0.06, 0.02), John (0.20, 0.06)
  (Thomas used to stand right behind Peter). Clearance ≥ 0.098.
- **S01** camera `orbit` → `fixed` yaw −10: at 6 deg/s a 28.6 s orbit ended looking at the page from behind.
- **Parking**: every actor not in a shot is hidden and parked (`hide()`), also Peter and John in S02-S04.
- **F2 durations** set from the voiced timeline: `dawn_glow` 55.2 (S02-S04), `tomb_glow` S07 19.3, lamps / sunset
  31.9 (S10) and 26.6 (S11), `heart_glow` 2.6 — all end at a cut.
- Small one-shot holds fixed (John after `jump_up`, Jesus after `call_name`, Mary `talk` after `turn_joy`).
- **Not changed**: `tools/story/sheet_risen.py` stays (it also holds the textured-render scene; SET.md names it).

## What is new or risky in this pack (read before you start your role)

| # | Thing | Who | What to do |
|---|---|---|---|
| 1 | **Three reused designs from two packs**: Jesus and Peter (Real Miracles), John (The King Who Serves). Peter is printed in Miracles and The King Who Serves but **fixed paint here**. | Characters | Reuse the builders unchanged (CONTRACT §2: run `mi_characters.py` / `ls_characters.py` in the namespace, or move them into the kit byte-identically). Peter's paint = his Miracles demo colours rendered into `extras_paint.png`. Never fork. |
| 2 | **An angel seated on a round stone** for two shots, with wings. | Characters, Set, Animation | The `ride` method: base y ANGEL_Y 0.311, seat on the stone top 0.38, always `face="viewer"`; probe with `garden.glb` (legs in front of the stone, wings clear of the rock). The angel never stands up on screen. Wings ≤ ±0.14 on the sheet (C2). |
| 3 | **The stone swap** (`tombStone` → `tombStoneAside`) happens under `angel_light` + `dust_burst`; nobody sees it roll. | Set, FX, Lead | Two hidden-state nodes (S5). If the owner wants to see it roll, the stone must become an actor (a one-bone `stone` with a `roll_aside` clip, coloured from the `tombStone` region): ask at Gate 1, not later. |
| 4 | **The tomb door must read**: dark when closed, glowing and empty when open; Peter (0.38) stoops into a 0.34 door. | Set, Animation, FX | Door faces the viewer; chamber shallow; `stoop_look` keeps Peter's back from filling the whole door (S07 camera from the right, yaw 20). `tomb_glow` must not hide the cloths. |
| 5 | **Jesus appears and disappears** (S08, S10, S11) instead of walking in. | Lead, FX | `appear()`: hidden → snap → `prop("jesus", True, grow=0.6)` under `angel_light`. Check on the device that the pop does not look like a glitch; fallback: a longer grow (1.0) with `golden_rays`. |
| 6 | **Close pairs** in three shots: Mary and Jesus `hold_hands` (S09), Thomas `reach` (S11), the women peeking side by side at the door (S04). | Animation, Lead | Probe each pair at its distance (CONTRACT §4). Staging re-checks the cameras so no face is behind another (S03 / S04: the women must not stand between the camera and the angel). |
| 7 | **The cross is words only.** `rs_01` / `rs_02` are the only mention; no prop, no set piece, no shadow of a cross. | Everyone | Voice: plain, soft, no pause on 十字架 / "cross"; Music: `sad_day` tender, not tragic; Set: no crosses, no Golgotha hill. The owner listens to `rs_01` first. |
| 8 | **The race** is the comedy and depends on two travel speeds (John 0.24 / s, Peter 0.17 / s planned). | Animation, Lead | Write the real naturalSpeeds in `clips.json`; the lead updates `V_RUN` / `V_PUFF` in `story.py` and re-runs `build_timeline.py` (warns on walks that stop short). |
| 9 | **Effect durations end at the cut** (F2): `sunset_glow` / `lamp_flame` are set per room shot (30 s, 24 s) from the estimate. | Lead | Re-set them after the voices re-time the play. |

## Lessons carried over from Real Miracles and The King Who Serves (2026-11-18)

- Hidden extras are parked beyond the page (`PARK`) as well as hidden, so the `all` camera rule and fx anchors ignore them.
- Multi-leg moves are timed per leg (`path()`, the cousin of `ride()` / `carry()`), so StoryDirector never cuts a walk
  short; the angel uses the ride seat method instead of a sitting-down clip.
- Props take their colour from printed regions (`fishPlate`, `waterJar`).
- SFX are one-shots sized to their scene (no loops: StoryDirector stops a loop only at a music cue).
- Interjections stay inside phrases with words (Qwen3-TTS reads a bare 哈哈 as a word).
- Cameras: start values only; staging moves them so the speaker is never behind someone else.

## Decisions already made (do not reopen without the owner)

- Reference episode: Superbook S01E11 ("He Is Risen", its own title). Used only for costume / set / light logic: a
  rock tomb with a round stone, a garden at dawn, women with spice jars, a shining angel in white, the evening room.
  Left out: the frame story's modern characters, Gethsemane, Judas, the arrest, Pilate, the crowd, the crucifixion and
  everything on screen about it, the guards.
- On the sheet: the angel, Jesus, Mary Magdalene. Peter, John, Thomas and Joanna wear fixed colours.
- Jesus, Peter and John look and sound the same as in Real Miracles / The King Who Serves; the risen Jesus wears His
  usual clothes and has no marks drawn.
- English voices: Qwen3-TTS only.
- Owner to confirm at Gate 1: the title (他复活了！/ He Is Risen!, Matthew 28:6), the two cross sentences, the ghost
  joke, Thomas touching the hands, and whether the stone may roll on screen (risk 3).
