# He Is Risen! — animation (Animation role)

Built by `pipeline/rs_animate.py` (same shape as `pipeline/ls_animate.py`, on the kit):

    python3 pipeline/rs_animate.py all      # build + verify + contact sheet + freshness check (~2 min)
    RS_PROBE="angel_sit_stone:0,60:wfront,wtop" python3 pipeline/rs_animate.py probe   # staged clips on the real set
    RS_PROBE="mary_cry:30:wfront" RS_PROBE_AIM=0.8 RS_PROBE_DIST=0.6 python3 pipeline/rs_animate.py probe  # face close-up
    RS_PROBE="pair:jesus_hold_hands:mary_hold_hands:0.11:0,30:meet:side,q3" python3 pipeline/rs_animate.py probe
    RS_PROBE="pair:jesus_show_hands:thomas_reach:0.11:60:touch:side,top" python3 pipeline/rs_animate.py probe
    RS_ONLY=angel_,peter_stoop RS_SETCHECK=1 python3 pipeline/rs_animate.py build   # subset + set check, no export

Views: actor-relative `front q3 side back ...`, world-fixed `wfront wfl wfr wtop wleft wright` (use these on the set:
walls block actor-relative cameras), `phone` (about the play's camera). Scratch: `$RS_ANIM_WORK` (default
`/tmp/risen_anim`).

Outputs: `assets/risen/anim/{jesus,mary,angel,peter,john,thomas,joanna}.glb` (character + skin + one glTF animation per
action `<char>_<clip>`), `clips.json` (lengths, loop flags, markers, natural speeds, props, per-clip checks, travel
table, A8 list, `pairCheck`, `setCheck`), `contact_sheet.png`. The model GLBs are not touched. **68 actions = CONTRACT
§4 exactly** (jesus 10, mary 15, angel 6, peter 12, john 11, thomas 6, joanna 8; asserted at build; `timelineMissing`
[]).

## 0. Reuse (not copies)

`rs_animate.py` runs `pipeline/ls_animate.py` in its own namespace (definitions only; its final dispatch line is cut
at an asserted anchor), and that file runs `pipeline/mi_animate.py` the same way. The clip lists are dropped and this
pack registers its own. Nothing in `mi_*` / `ls_*` was edited. Reused functions, baked on this pack's rigs:

- Real Miracles: jesus `idle` `talk` `walk` `wave`; peter `idle` `talk` `walk` `laugh` `amazed`; the friends' `idle`
  for John and Thomas; `peter_laugh` for John (as The King Who Serves did); `friend_cheer` for Mary.
- The King Who Serves: John's `talk` (`d_talk`), `cheer` for Peter / John / Thomas (`cheer_fn` with an open right hand:
  no palm frond here), the bench sit (`bench_legs`, seat UPPER + 0.04) under `sit_sad`.
- `john_amazed` is Miracles `peter_amazed` with its opening crouch mostly removed (John comes from `peek`, standing);
  Peter keeps the original (he comes from `stoop_look`, crouched, so it continues).
- Miracles has no standing Peter `shock` (its `roof_shock` is the hands-on-head dust gag), so Peter shares John's new
  `shock`. Joanna shares every one of Mary's functions (phase / amplitude per person).

## 1. Clips (30 fps)

One-shots hold their last frame. Columns: speed = naturalSpeed (u/s) of travel clips; minY = lowest mesh point in
rig space (the angel's is its hanging feet, 0.287 in the world: not a floor contact); drift / slip = planted-foot
drift (in place) or stance slip (travel); seam = loop seam step (all 41 loops `seamOK`).

| Action | Frames | s | Type | Speed | Markers (s) | minY | drift / slip | seam |
|---|---|---|---|---|---|---|---|---|
| `jesus_idle` | 150 | 5.00 | loop |  |  | -0.0006 | 0.0001 | 0.0004 |
| `jesus_talk` | 96 | 3.20 | loop |  |  | -0.0005 | 0.0001 | 0.007 |
| `jesus_walk` | 36 | 1.20 | loop | 0.0972 | contactL 0.0, contactR 0.6 | -0.001 | 0.0 | 0.0076 |
| `jesus_wave` | 60 | 2.00 | loop |  |  | -0.0006 | 0.0001 | 0.004 |
| `jesus_appear` | 45 | 1.50 | one-shot |  | open 1.0 | 0.0002 | 0.0 |  |
| `jesus_call_name` | 40 | 1.33 | one-shot |  | name 0.6 | -0.0001 | 0.0035 |  |
| `jesus_hold_hands` | 60 | 2.00 | loop |  |  | -0.0005 | 0.0001 | 0.0006 |
| `jesus_peace` | 120 | 4.00 | loop |  |  | 0.0002 | 0.0 | 0.0035 |
| `jesus_show_hands` | 96 | 3.20 | loop |  |  | 0.0002 | 0.0 | 0.0003 |
| `jesus_eat_fish` | 120 | 4.00 | one-shot |  | take 0.6, show 1.2, bite 1.6, laugh 3.067 | -0.0004 | 0.0 |  |
| `mary_idle` | 120 | 4.00 | loop |  |  | 0.001 | 0.0001 | 0.0004 |
| `joanna_idle` | 120 | 4.00 | loop |  |  | 0.001 | 0.0001 | 0.0007 |
| `mary_idle_jar` | 120 | 4.00 | loop |  |  | 0.001 | 0.0001 | 0.0004 |
| `joanna_idle_jar` | 120 | 4.00 | loop |  |  | 0.001 | 0.0001 | 0.0007 |
| `mary_walk` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | 0.0006 | 0.0036 | 0.0058 |
| `joanna_walk` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | 0.0006 | 0.0037 | 0.0056 |
| `mary_walk_jar` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | 0.0006 | 0.0036 | 0.0058 |
| `joanna_walk_jar` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | 0.0006 | 0.0037 | 0.0056 |
| `mary_run` | 20 | 0.67 | loop | 0.1974 | contactL 0.0, contactR 0.333 | 0.0008 | 0.0 | 0.0218 |
| `joanna_run` | 20 | 0.67 | loop | 0.1974 | contactL 0.0, contactR 0.333 | 0.0007 | 0.0 | 0.0212 |
| `mary_sad` | 120 | 4.00 | loop |  |  | 0.0012 | 0.0 | 0.0004 |
| `joanna_sad` | 120 | 4.00 | loop |  |  | 0.0011 | 0.0 | 0.0002 |
| `mary_gasp` | 36 | 1.20 | one-shot |  | gasp 0.2, look 0.8 | 0.0016 | 0.0021 |  |
| `joanna_gasp` | 36 | 1.20 | one-shot |  | gasp 0.2, look 0.8 | 0.0016 | 0.0021 |  |
| `mary_peek` | 54 | 1.80 | one-shot |  | in 0.667 | 0.0016 | 0.0078 |  |
| `joanna_peek` | 54 | 1.80 | one-shot |  | in 0.667 | 0.0016 | 0.0078 |  |
| `mary_talk` | 96 | 3.20 | loop |  |  | 0.0016 | 0.0 | 0.0027 |
| `mary_tell` | 72 | 2.40 | loop |  |  | 0.0001 | 0.0001 | 0.0034 |
| `mary_cry` | 120 | 4.00 | loop |  | wipeL 1.0, wipeR 3.0 | 0.0012 | 0.0 | 0.0006 |
| `mary_talk_down` | 96 | 3.20 | loop |  |  | 0.0016 | 0.0 | 0.0022 |
| `mary_turn_joy` | 36 | 1.20 | one-shot |  | know 0.2, smile 0.733 | -0.0001 | 0.0001 |  |
| `mary_hold_hands` | 60 | 2.00 | loop |  |  | 0.0002 | 0.0001 | 0.0008 |
| `mary_cheer` | 30 | 1.00 | loop |  | hop 0.267 | 0.0008 | 0.0017 | 0.0084 |
| `angel_idle` | 120 | 4.00 | loop |  |  | 0.0018 | 0.0 | 0.0008 |
| `angel_sit_stone` | 120 | 4.00 | loop (seated) |  |  | -0.0241 | 0.0223 | 0.0014 |
| `angel_wings_open` | 48 | 1.60 | one-shot (seated) |  | open 0.5 | -0.0094 | 0.0 |  |
| `angel_sit_talk` | 96 | 3.20 | loop (seated) |  |  | -0.0173 | 0.0108 | 0.0009 |
| `angel_sit_point` | 54 | 1.80 | one-shot (seated) |  | point 0.667, back 1.2 | -0.0156 | 0.0085 |  |
| `angel_sit_wave` | 48 | 1.60 | loop (seated) |  |  | -0.0286 | 0.0543 | 0.0099 |
| `peter_idle` | 180 | 6.00 | loop |  |  | -0.003 | 0.0003 | 0.0007 |
| `peter_talk` | 96 | 3.20 | loop |  |  | -0.0023 | 0.0002 | 0.0026 |
| `peter_walk` | 36 | 1.20 | loop | 0.1111 | contactL 0.0, contactR 0.6 | -0.0038 | 0.0 | 0.0128 |
| `peter_laugh` | 48 | 1.60 | loop |  | slap1 0.4, slap2 1.2 | -0.0011 | 0.0028 | 0.0037 |
| `peter_amazed` | 66 | 2.20 | one-shot |  | look 1.0 | -0.003 | 0.0001 |  |
| `john_idle` | 120 | 4.00 | loop |  |  | -0.0002 | 0.0001 | 0.0008 |
| `john_talk` | 96 | 3.20 | loop |  |  | 0.0002 | 0.0 | 0.003 |
| `john_laugh` | 48 | 1.60 | loop |  | slap1 0.4, slap2 1.2 | 0.0006 | 0.0028 | 0.004 |
| `john_amazed` | 66 | 2.20 | one-shot |  | look 1.0 | 0.0001 | 0.0001 |  |
| `peter_cheer` | 40 | 1.33 | loop |  | bounce 0.333 | -0.0031 | 0.0 | 0.0071 |
| `john_cheer` | 40 | 1.33 | loop |  | bounce 0.333 | -0.0001 | 0.0001 | 0.0057 |
| `thomas_cheer` | 40 | 1.33 | loop |  | bounce 0.333 | 0.0 | 0.0001 | 0.0125 |
| `peter_sit_sad` | 120 | 4.00 | loop (seated) |  |  | 0.0008 | 0.0 | 0.0005 |
| `john_sit_sad` | 120 | 4.00 | loop (seated) |  |  | 0.0008 | 0.0 | 0.0004 |
| `peter_jump_up` | 27 | 0.90 | one-shot |  | up 0.4 | -0.0001 | 0.0089 |  |
| `john_jump_up` | 27 | 0.90 | one-shot |  | up 0.4 | 0.0003 | 0.0417 |  |
| `peter_run_puff` | 24 | 0.80 | loop | 0.1658 | contactL 0.0, contactR 0.4 | -0.0034 | 0.0 | 0.0233 |
| `peter_puff` | 60 | 2.00 | loop |  | breath1 0.333, breath2 1.333 | -0.0018 | 0.0 | 0.001 |
| `peter_stoop_look` | 84 | 2.80 | one-shot |  | in 0.667, look 1.467, out 2.2 | -0.0027 | 0.001 |  |
| `peter_shock` | 54 | 1.80 | one-shot |  | jump 0.1, land 0.5 | -0.0031 | 0.0053 |  |
| `john_shock` | 54 | 1.80 | one-shot |  | jump 0.1, land 0.5 | -0.0002 | 0.0054 |  |
| `john_run` | 18 | 0.60 | loop | 0.2407 | contactL 0.0, contactR 0.3 | 0.0002 | 0.0 | 0.0347 |
| `john_wave_hurry` | 32 | 1.07 | loop |  | beckon1 0.2, beckon2 0.733 | -0.0003 | 0.0 | 0.0153 |
| `john_peek` | 54 | 1.80 | one-shot |  | in 0.667 | 0.0002 | 0.0078 |  |
| `thomas_idle` | 120 | 4.00 | loop |  |  | 0.0001 | 0.0001 | 0.0009 |
| `thomas_doubt` | 120 | 4.00 | loop |  | shake 1.667 | 0.0006 | 0.0 | 0.0002 |
| `thomas_shock` | 36 | 1.20 | one-shot |  | jump 0.133 | 0.0002 | 0.0028 |  |
| `thomas_reach` | 60 | 2.00 | one-shot |  | touch 1.133 | 0.0005 | 0.0239 |  |
| `thomas_kneel_worship` | 60 | 2.00 | one-shot (seated) |  | down 0.933, look 1.333 | 0.0001 | 0.0103 |  |
Props inside clips: `jesus_eat_fish` shows `fish` from frame 18 (0.6 s, marker `take`); story.py shows `jesus/fish`
and hides `garden/fishOnPlate` at exactly that time (act dt 1.0, props dt 1.6) and `munch` lands on `bite` (1.6 s).
The jar (`idle_jar`, `walk_jar`, `gasp`, `peek`) always hangs straight down from the left fist (solved per frame);
in S04 `run` it dangles from the swinging left hand.

## 2. Stage numbers the clips are fitted to

| What | Number | Where it matters |
|---|---|---|
| Angel seat | base y **ANGEL_Y 0.311**, yaw **0** (face viewer) at STONE_ASIDE (−0.1126, −0.4103); the lowest hips / thigh point over the stone's top footprint is put on 0.38 every frame (`seatGapMin/Max` 0.000 / 0.000) | S03, S04 |
| Angel stone | disc plane 40° off X (left end front-left), half thickness 0.025; hands on the top edge 0.052 along the disc from the hips (the left hand back, the right in front) | all `sit_*` |
| Pair distance | 0.11 root to root, facing (A1) | `hold_hands` ×2, `show_hands` / `reach` / `kneel_worship` |
| hold_hands | joined hands at y 0.185, Jesus's wrists 0.043 and Mary's 0.047 in front of their roots | S09 |
| show_hands | wrists 0.05 in front, 0.056 to the sides (beside the bellies), y 0.20 above the floor | S10, S11 |
| Bench | seat UPPER + 0.04, feet ~0.066 ahead of the BENCH mark (The King Who Serves `bench_legs`) | S01, S05 |
| Tomb door | door plane z −0.312, top 0.34; TOMB_DOOR 0.072 in front; hands on the rock face left of the door (−0.418, −0.298) and on the rolled stone's left end (−0.273, −0.277) | `stoop_look`, `peek` |
| Fish plate | TABLE_J facing `lowTable` (yaw 95.7): the plate 0.09 in front, top UPPER + 0.056 | `eat_fish` |
| Travel | women walk 0.090, Mary / Joanna run 0.197, John run 0.241, Peter run_puff 0.166, Jesus walk 0.097, Peter walk 0.111 | V_* in story.py |

## 3. Checks (last build; `clips.json` `checks`, `pairCheck`, `setCheck`)

- Contract: 68 actions, the exact set per character; verify re-imports all seven GLBs: every action present, sampled
  bone positions = build (max error 8e-06), UV0 in the unit square. `RS_FRESH OK` (exports newer than the models).
- Loops: 47 / 47 `seamOK`. Travel stance slip max 0.0037 u/s (limit 0.02). Floor: lowest standing point −0.0038
  (peter_walk, the Miracles clip); seated / kneeling ≥ 0.0000 (thomas_kneel_worship 0.0000, sit_sad 0.0008).
- Planted feet ≤ 0.002 except deliberate steps: john_jump_up 0.042 / peter 0.009 (they jump off the bench),
  thomas_reach 0.024 and kneel 0.010 (step, knees down), peeks 0.008 (a lean step), shock 0.005 (hop back), call_name
  0.0035 (step to Mary), Miracles laugh 0.0028, gasp 0.0021 (step back). Angel rows: its feet hang (not counted).
- Pairs (bodies without arms / hands): hold_hands 0.020 apart, hands touching (0.0002); show_hands + reach 0.0074
  apart, Thomas's fingertips 0.007 from Jesus's palm (the wrist target is solved; the arm is cramped at 0.11, residual
  0.0095); show_hands + kneel_worship 0.0074.
- Set (real `garden.glb`, staged marks, points inside set meshes above the floor): angel seat on the 0.38 top
  exactly, no leg point behind the stone's front face in any seated clip; wings: right outer wing ≤ 0.008 into the
  alcove rock (wings_open: inner right wing 0.013 at the spread), left inner wing ≤ 0.006 into the stone's back half,
  sit_point fingertips 0.012 into the rock at full point. Peter `stoop_look`: top beyond the door plane **0.319**
  (< 0.34), head / chest / shoulders clear of the rock; only his bracing hands touch (fingers ≤ 0.02 into the rock
  face, the right hand ≤ 0.04 into the stone rim / jamb corner). Peeks: fingertips on the rock 0.004-0.005 (John,
  Joanna), Mary's right hand 0.010 into the stone rim. Bench, room, table (eat_fish), gasp marks: nothing inside.
- A8: no actor gets two clips at the same instant.

## 4. Staging (for the lead: story.py)

1. **The angel must keep yaw 0 on the stone (must fix).** S04 gives it `face="mary"` (sit_talk ×2, sit_wave) and
   `face="tombDoor"` (sit_point). Turning the seated actor puts its legs through the stone (the top runs diagonally;
   at the door's yaw −63 the legs point into the stone's back). Use `face="viewer"` for every angel act: the clips
   already turn the chest / head to the women (to its right) and point the right arm at the door (−63°).
2. **ANGEL_Y stays 0.311.** The clips put the seat (lowest robe point) at rig-local 0.069 = 0.38 − 0.311, so
   story.py's value is right for these clips; CONTRACT §4 / §5 (0.185 / 0.22) and SET.md / CONTRACT §6 (0.345) are
   stale. If you change it, change `ANGEL_Y` in rs_animate.py and rebuild (one constant).
3. **Mary runs out of the upstairs room (must fix).** S09's run-off `path()` takes ~2.9 s, but S10 cuts 1.0 s after
   rs_27: legs 2-3 (t 170.53 → PATH_L, 171.26 → (0.30, 0.10)) fire after S10's snap to MARY_ROOM. Either keep only the
   first leg (MARY_MEET → (−0.10, 0.04)) or lengthen the S09 pause to ≥ T of `_mary_off`. Also `cheer` (169.45) is
   replaced by `run` 0.3 s later: barely seen; give it ≥ 1.0 s.
4. **John glides aside in S07 (A2).** `act("john", "idle", to=(-0.40, -0.22))` slides him 0.073 sideways; John has
   no walk clip in the contract. Use `run` for that step (0.3 s at 0.241), or start John's S07 at (−0.40, −0.22)
   already (his `peek` hand target is fitted to TOMB_DOOR, so then he peeks from the side; tell me and I refit).
5. **Joanna's S04 run-off is 1.76×** (JOANNA_DOOR → (−0.18, 0.08), 0.364 in 1.05 s before the S05 cut): she
   will not arrive before the cut (fine if accepted) or start her run ~0.8 s earlier.
6. **Speeds** (after the voices): V_WALK 0.090 (women; Jesus 0.097, Peter 0.111), V_RUN 0.241, V_PUFF 0.166, V_JOY
   0.197. All other moves with a `to` are ≤ 1.32× (S04 Mary run 1.32, S07 Peter walk 1.12, S10 Jesus walk 1.13).
7. **Peek / stoop marks.** Mary peeks with her right hand on the rolled stone's left end (her left holds the jar);
   John and Joanna put the left hand on the rock face left of the door. Peter's stoop is fitted to TOMB_DOOR facing
   `tombDoor` (hands on both edges); John must be out of TOMB_DOOR before Peter's `walk` arrives (story.py: 0.2 s
   apart — fine once note 4 is fixed).
8. **hold_hands** assumes the pair 0.11 apart (MARY_MEET ↔ JESUS_G is 0.114: OK) and both started on the same beat
   (story.py does: dt 0.6 both). **show_hands / reach** assume Jesus at ROOM_J facing Thomas and Thomas at
   THOMAS_TOUCH facing Jesus (0.11). `reach` reads at 0.11 but tight (one hand touches; the bodies are 0.007 apart);
   if S11's camera does not show the touch, THOMAS_TOUCH 0.03 further away and a rebuild would give the arm room.
9. **Lead-ins (A4):** `jump_up` takes Peter / John off the bench; `kneel_worship` sinks from standing (from `reach`'s
   end pose); `wings_open` starts and ends on `sit_stone` frame 0; `amazed` (Peter) continues from `stoop_look`'s
   crouch. `turn_joy` starts from `talk_down`'s head-down pose.
10. `eat_fish`: keep `face="lowTable"` from TABLE_J (the reach is fitted to that yaw); He turns to the viewer (His
    right) inside the clip.

## 5. Weak / not verified

- Nothing was played in Unity or on the phone; clip-to-clip blends (0.25 s) were not checked.
- The angel's wings still touch the rock / stone by ≤ 0.013 (behind the body from the play's front cameras); the
  hands "on the stone" are at full arm reach: the wrists hover ~0.01 over the top, fingers curled over the edge.
- Thomas's touch: his fingertips stop 0.007 short of the palm; at 0.11 the reaching arm is cramped against his body.
- Peter's bracing right hand sinks up to 0.04 into the stone rim / jamb corner (seen from the front-left it reads as
  a hand on the stone); Mary's right hand 0.01 into the rim.
- `eat_fish`: Jesus's mantle bulges over His knees in the deep reach (0.4-0.8 s).
- Women's walk / run legs are under the long dress: the gait reads only from the hem and the body bob.
- `mary_cry` / `talk_down`: hands at the jaw and lower cheeks, eyes always clear (A5); checked at about phone size
  in renders, not on a phone.
- Joanna was checked through the numbers and her `gasp` / `peek` rows only (shared functions with Mary).
