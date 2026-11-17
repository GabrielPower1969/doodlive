# Saul Sees the Light! — pack plan (this pack's index)

Shared instructions: `docs/pack-plans/00-INDEX.md`. This page holds only what is specific to this pack.

Ids: story `saul` · prefix `sa` · env `SA_` · set `damascus` · line ids `sa_01…sa_42` · 13 shots · voiced 4:12
(252.5 s on the voiced timeline; the estimate was 243.4 s). Real voices added 6 % in He Is Risen! (233 → 247 s) and 7 % in The King
Who Serves, so expect about 4:15-4:20, at the top of the 3:50-4:15 target. If it runs past 4:15, the first cuts are, in
order: `sa_12` (the tall guard's "I heard a voice... but there's nobody here!"; S04 then ends on Jesus), `sa_21` (the
narrator's "Ananias was a bit scared, but he went": the tiptoe and the music carry it), `sa_30` (the short guard's "He's
completely changed!"), `sa_27` (Saul's "Three days with nothing!", then S09 ends on the bread and a laugh). Each saves
3-5 s.

## State

| Stage | State |
|---|---|
| 1 Plan | done 2026-11-18: `STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md`, `assets/saul/manifest.json` |
| Gates 1-2 | the roles were started after them; the owner's answers are in Hours, not here |
| 3 Characters / Set + sheet | done: `RIG.md`, `SET.md` (Ananias's house moved to the front left and widened at staging, below) |
| 4 Animation / Voice / FX | done: `ANIMATION.md` (76 actions), `VOICE.md` (voiced timeline 252.5 s), `FX.md` (`road_light`, `scales_fall`) |
| 5 Music | done: `MUSIC.md`; `music_saul.py` re-run after staging (cues and SFX re-fitted to the staged timeline) |
| Staging | done 2026-11-18: `story.py` re-staged to the built rigs, set, clips and voices (below); blocking renders (real GLBs posed by a Python copy of the director's acting / move / face / camera logic, phone camera 1080 × 2340, vfov 60) looked at, not in Unity. Line text, order, ids and every line / shot time unchanged (252.52 s); `build_timeline.py saul` prints no warning |
| 6 Integration | done 2026-11-18 up to `check.py saul`: 12 checks, 0 FAIL, 0 WARN (`--all`: 144 checks, 0 FAIL, 0 WARN). `registry` order 12 (after risen), `library` (after risen), `fx.class` SaulFx, `faces.json` from `sa_characters.py` CLIP_EXPRESSION (Saul's idle changed, below); `merge_packs.py`, `make_fonts.py`, `pack.py saul`, `make_sheet_signatures.py` run |
| 7 Device | not started (lead: `scripts/build-apk.sh`, after asking the owner and the other sessions); then the cover step (I3a) |

## Staging (2026-11-18)

What was run, in order: set fixes in `pipeline/sa_damascus.py` → `-- all` (CLEARANCE OK for every mark and straight leg
of the staged `story.py`, 92 checks, tightest 0.050; LAYOUT OK; VERIFY PASS) → `sa_characters.py -- build` (prop
anchors re-sampled: the `street` drawing moved) → `pipeline/sa_animate.py all` (re-export on the rebuilt models;
SA_FRESH OK) → `tools/story/sheet_saul.py` (SHEET PASS, anchors 61 / 61, no set region under 6 mm) →
`make_colored_pdf.py saul` (A4, markers 0 px) → `build_timeline.py saul` → `music_saul.py` → integration (above).
Checks of my own: a director simulation over the whole play (who is shown / parked per shot, closest pair per shot,
walks running past a cut, effects past a cut, acts on hidden actors) and 55 + 21 blocking renders at the shot starts
and every line's middle.

## Lead decisions at staging (2026-11-18, for the owner)

- **Ananias's house moved to the front left of the page and widened to 0.24 inside** (was 0.11 in the back row: his
  arms and knees were inside both walls in all four S07 clips). The back row had no room (SET.md §1a); the front-left
  corner was empty. On the printed sheet the room keeps its old place left of the synagogue (the `street` drawing is
  ~13 % smaller). The well moved to the freed back-left corner. ANANIAS_HOME (−0.465, 0.08); the S07 camera is
  unchanged (yaw 10 on the house) and now looks straight into the open room. In S07 Saul can be seen far behind,
  praying in Judas's room: kept on purpose (the Lord says "he is praying").
- **Cost of that move**: from the front the house hides the left part of Straight Street. S06 / S08 / S09 cameras
  are now yaw 0 (at −10 / −15 / 15 the house or the front gate tower stood in front of the room); S10 is yaw 10.
- **Judas stands beside Saul, not between him and the camera**: JUDAS_SIDE (−0.22, −0.42) in S06 / S08 (JUDAS_IN put
  his back over Saul in both cameras), (−0.08, −0.43) in S09 (in front of the eating Saul at (−0.10, −0.40)).
  **Judas has no `walk` clip** (CONTRACT §4), so he never moves: `offer_bread` is played in place (S06 at 0.081, S09
  at 0.076 from Saul) instead of the requested walk-then-offer. If the owner wants him to step in, Animation must add
  `judas_walk` (a contract change).
- **S10**: only the two guards listen (they speak); Ananias and Judas are hidden. In Judas's doorway they stood right
  behind the guards and were never seen; on the left of the street the house hides them. All of them wave in S13.
- **Saul's idle face is `kind`** (faces.json; CLIP_EXPRESSION said `angry`). Faces are per clip, and after S07 Saul
  idles in S08-S12 (S12: 15 s waiting in Jerusalem). Before S06 he never idles longer than 0.85 s: in S01 he paces
  angrily up and down in front of the porch (`march`, 7 legs) through the narrator's line and starts `angry_talk` at
  its end; in S02 the march starts at the cut; in S03 he marches into the light (from (0.27, 0.10)) and falls.
- **S01**: the scroll shows at `take_letters` + 0.33 s (`grab`); the march off arrives before the cut.
- **S02 / S03**: the tall guard's puff ends at (0.53, 0.03) (at (0.50, 0.08) he stood 0.06 from the short guard); in
  S03 both guards puff in from behind ((0.40, 0.05) → (0.33, 0.03), (0.45, 0.13) → (0.38, 0.12)) instead of
  walk-on-the-spot.
- **S05**: on the cut the tall guard stands behind Saul at (0.27, −0.05) and walks round to ROAD_D (his old walk from
  (0.34, 0.13) passed 0.05 from Saul and the short guard). He leads by 0.14 (Saul's `walk_blind` starts 0.76 s after
  `lead_hand`); Saul's path gains a last leg into the gateway (0.05, −0.16), so he ends 0.14 behind the guard at
  GATE_IN. The short guard follows at walking pace from 2.6 s (≥ 0.12 behind Saul throughout).
- **S11**: Saul's basket mark SAUL_BASKET (0.095, −0.38) facing the viewer; `basket_down` is anchored to the end of
  `sa_34` (−6.0 s), so `land` (5.6 s) and `basket_land` come 0.4 s before "he's down" ends and `basket_out` starts as
  the clip ends; Saul then `wave`s up through `sa_35` and tiptoes (SAUL_BASKET → (0.13, −0.33), 1.0 s) to end at the
  cut. The short guard boasts / dozes at **(0.19, −0.11)** (at (0.11, −0.27) his arm was in the back tower; the
  requested x ≥ 0.14 next to the wall left no room for Saul to pass behind him).
- **S12**: camera yaw 25 → **−25** (from the right, Saul and Barnabas stood between the camera and Peter in all three
  Peter lines). JHOUSE_DOOR **(0.24, −0.33)**: at −0.35 Peter's arm was still in the house front (`setCheck`); at −0.33
  only the dark doorway box (an inward-facing shell) and one point of a bush. Saul stands at (0.40, −0.24) facing Peter
  from `sa_37`; Barnabas `arm_round` (face Peter) from 2.4 s after `sa_37` to 0.6 s after `sa_38`, then `laugh`; only
  then Saul walks to (0.335, −0.30) (0.0995 from Peter) for the hug at the end of `sa_39`. While he walks he passes
  0.083 from Barnabas.
- **F2**: `road_light` 31.59 (S03+S04 to the S05 cut), `prayer_glow` 11.82, `angel_light` 24.92, `heart_glow` (S08)
  4.06, `night` / `lamp_flame` ×3 30.6, `zzz` 18.69, `golden_rays` 21.31 — all end at their cut on the voiced
  timeline. Re-set them if the voices change.
- **Parking**: every actor not in a shot is hidden and parked (simulation: no act fires on a hidden actor, no walk
  runs past a cut).
- **Files outside the lead's own**: `pipeline/sa_animate.py` stage constants (ANANIAS_HOME, JHOUSE_DOOR, SHORT_GATE, the
  `offer_bread` stage) now mirror `story.py`, so `clips.json` `setCheck` describes the staged play; no clip changed.

### Open risks (look on the phone)

- S06 / S08 / S09 at yaw 0: the front gate tower fills the right third of the frame and the front-left house the
  bottom-left corner; Saul and the speaker are clear in the renders, but it is tight.
- S08 `hands_on`: `setCheck` still lists Ananias's back in the wall-window area (161 proxy points, unchanged from the
  Animation role's run); S08 `knock` lands on air (SET.md §4).
- S11: the guards fill the middle of the frame; the basket at the window is small at the top right.
- Saul's seated cloak on the S06-S09 mat and the S03 milestone touches (ANIMATION.md §3) are unchanged.
- Judas's bread offer is played at 0.08 from Saul without a probe of `offer_bread` at that distance.

## What is new or risky in this pack (read before you start your role)

| # | Thing | Who | What to do |
|---|---|---|---|
| 1 | **Jesus has no body**: a light and a voice in S03-S04 (`road_light`) and S07 (`angel_light`). His lines have `who="jesus"` but no actor in `CAST`. | Lead, Voice, FX | StoryDirector skips the talking head for a speaker with no actor (`StoryDirector.cs` `if (!A) return;`); check on the device that the subtitle still names him (`dg_jesus`) and nothing logs an error. Voice: copy the `jesus` entries of `cast_miracles.json` exactly (same design, f0, fx). |
| 2 | **`road_light` is the climax** and the only new big effect: a warm bloom, then a column round Saul for ~33 s across two shots. It must be wonderful, not scary, and Saul's face must read inside it. | FX, Lead | Try Gabriel's `descend_light` (+ a warm flash) as an alias first (F1); a new id only if that cannot be warm enough. Preview on the sand-gold road with Saul's red robe. F2: it ends at the S05 cut. |
| 3 | **The basket descent** (S11): Saul's own prop rig (`basket` on `hips`, ropes skinned between `basket` and a fixed `ropeTop` at the window), lowered inside the one-shot clip `basket_down`; the base never moves. | Characters, Animation, Set | Characters builds the rig and ropes (RIG.md); Animation keys the descent (6.0 s, small drops, a sway); Set puts the window at z −0.46, y 0.20-0.27 on the wall's outside face. Probe with `damascus.glb`: the basket clears the wall, the rope tops stay in the window. Fallback: no ropes, the basket alone comes down (say so at Gate 2). |
| 4 | **Saul is one design whose face carries the change** (angry → blind → kind), 22 clips, the biggest hero yet. | Characters, Animation, Lead | Faces per clip in `faces.json` (angry until S07, kind from S08); the brows are the key drawing. Count Saul's clips early; reuse kit motions where the clip table says "standing clips". |
| 5 | **Eight actors, five of them fixed paint**, two of them a comic pair (very tall 0.41 / very short 0.30) built from `build_friend`. | Characters | One `extras_paint.png` for `judas priest tallguard shortguard peter`; check that `build_friend` can stretch to 0.41 and 0.30 without breaking faces; else a small builder in `sa_characters.py`. Peter is the Miracles Peter, unchanged (R5). |
| 6 | **Moving pair: led by the hand** (S05): the tall guard (`lead_hand`) 0.08-0.10 ahead of Saul (`walk_blind`) on the same path at the same speed, round two corners and through the gate. | Animation, Lead | Same `V_BLIND` for both; probe the hand contact at the corners (ROAD_E, GATE_OUT). If the hands drift apart, the lead offsets the starts or gives the guard a shorter path. |
| 7 | **Close pairs at a seated / kneeling Saul**: `hands_on` (S08) and `pour` (S09) at 0.08; `hug` (S12) at 0.10; Barnabas `arm_round` at 0.10. | Animation, Lead | Probe each at its distance (A1); S08 camera must show both faces (Ananias beside, not behind). |
| 8 | **The city wall runs front-to-back through the middle of the page** (x 0). Seen edge-on from the front it hides nothing; from the side (S11 yaw 50) it is the backdrop. | Set, Lead | Keep the wall 0.06 thick and its front tower ≤ 0.34; check the S10 / S13 front cameras and the S11 side camera at staging. |
| 9 | **Two doll's houses side by side** (Ananias's small room and Judas's room against the wall) plus the synagogue steps, all in 0.60 of page width. Interior marks are 0.05-0.06 from walls. | Set | Print `CLEARANCE` for every interior mark (CONTRACT §6); if a mark fails, tell the lead before moving a wall. |
| 10 | **`dg_saul` is already King Saul** (David & Goliath). | Lead, Integration | Subtitle names use per-story strings `dg_saul_saul`, `dg_saul_judas`, etc. (I4); check the subtitle on the device says 扫罗, not 扫罗王. |
| 11 | **Effect durations end at the cut** (F2): `road_light` 32.7, `prayer_glow` 13.0, `angel_light` 23.2, `heart_glow` 3.7, `night` / `lamp_flame` ×3 28.8, `zzz` 17.4 from the estimate. | Lead | Re-set them after the voices re-time the play. |

## Lessons carried over from Real Miracles, The King Who Serves and He Is Risen! (2026-11-18)

- Hidden extras are parked beyond the page (`PARK`) as well as hidden (`hide()`), so the camera rule and fx anchors
  ignore them; every shot re-shows who it needs (`show()`).
- Multi-leg moves are timed per leg (`path()`), and **no path runs past its cut** (S11 keeps only the first leg of
  Saul's tiptoe: later legs would fire after the S12 snap and walk him through Jerusalem).
- Seats and pairs: Saul sits on the ground and on a mat (`fall_down`, `sit_pray`) with clips that end seated (A4, A6);
  the basket uses the clip-driven descent, the cousin of the `ride` seat method (the base stays planted, the clip owns
  the height).
- Props take their colour from printed regions (`breadBasket`, `waterJar`, `synagogue`).
- SFX are one-shots sized to their scene (no loops: StoryDirector stops a loop only at a music cue); `rope_creak` and
  `snore` are one-shots too.
- Interjections stay inside phrases with words (Qwen3-TTS reads a bare 哈哈 as a word); no line is a bare interjection
  (咦 opens a sentence, it is not a line).
- Cameras: start values only; staging moves them so the speaker is never behind someone else. Speaker-behind risks
  here: S05 (the guard leading), S08 (Ananias at the seated Saul), S10 (listeners round the steps), S12 (three at the
  door).
- Every actor that is neither speaking nor moving returns to `idle` / `listen` after a one-shot (no 13-second held last
  frame, risen S03).

## Decisions already made (do not reopen without the owner)

- Reference episode: Superbook S01E12 ("生命大翻转"). Used only for costume / set / light logic: a young man in a dark red
  robe and a darker cloak, the sunset desert road, a light from above, flat-roofed houses on a narrow street, an older
  believer in a pale shawl, the high wall with a window at night. Left out: the frame story and all its modern
  characters (Chris, Joy, Gizmo, the professor, the boy burglar), Stephen's stoning, every search and arrest scene, the
  horses, the episode's wording and music.
- On the sheet: Ananias (left), Saul (centre), Barnabas (right). Judas, the high priest, the two temple guards and Peter
  wear fixed colours.
- Jesus is a light and a voice only; His voice is the Real Miracles voice (`cast_miracles.json`).
- The two temple guards are the same comic pair all through (travel, lead him blind, puzzled at the synagogue, watch the
  gate, wave in the finale). No weapons anywhere.
- Baptism is water poured from Ananias's jug inside Judas's house (no pool, no undressing).
- Ananias and Judas lower the basket from inside Judas's house, which is built against the wall; on screen only the
  window and the basket are seen and Ananias's whisper is heard (`sa_34`, an off-screen line).
- Peter alone stands for the believers in Jerusalem (Galatians 1:18); John and the other apostles are left out.
- Two new effect ids at most (`road_light`, `scales_fall`); the lantern is `lamp_flame`.
- No donkey (the reference's horses are left out; walking keeps the comedy with the guards).
- English voices: Qwen3-TTS only.
- Owner to confirm at Gate 1: the title (扫罗变了！/ Saul Sees the Light!, theme verse 2 Corinthians 5:17; fallback
  *Saul Is Changed!*), the one arrest sentence (`sa_01`) and Jesus's "When you are against My friends, you are against
  Me" (`sa_10`), the guards as the same two men who later watch the gate and then wave in the finale, the off-screen
  Ananias in the basket scene, the "later he was called Paul" tag (`sa_40`), whether to add a donkey, and whether the
  length (≈ 4:15 voiced) is acceptable or the first cuts above should go now.
