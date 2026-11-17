# Saul Sees the Light! — animation (Animation role)

Built by `pipeline/sa_animate.py` (same shape as `pipeline/rs_animate.py`, on the kit):

    python3 pipeline/sa_animate.py all      # build + verify + contact sheet + freshness check (~10 min)
    SA_PROBE="saul_basket_down:0,90,170:wbasket" python3 pipeline/sa_animate.py probe     # staged clips on the set
    SA_PROBE="pair:hug:0,30:side,q3" python3 pipeline/sa_animate.py probe                 # a pair (keys below)
    SA_ONLY=saul_basket,ananias_pour SA_PAIRCHECK=1 python3 pipeline/sa_animate.py build   # subset + checks, no export

Views: actor-relative `front q3 side back ...`, world-fixed `wfront wfl wfr wtop wleft wright wbasket wback`, `phone`.
Pair keys: `lead hug hands_on hands_on_see pour arm_round letters`. Scratch: `$SA_ANIM_WORK` (default
`/tmp/saul_animation`). Blender always runs with `--python-exit-code 1`.

Outputs: `assets/saul/anim/{saul,ananias,barnabas,judas,priest,tallguard,shortguard,peter}.glb` (character + skin +
one glTF animation per action `<char>_<clip>`), `clips.json` (lengths, loop flags, markers, natural speeds, props,
per-clip checks, travel table, A8 list, `pairCheck`, `basketCheck`, `setCheck`, `stage`), `contact_sheet.png`. The
model GLBs are not touched. In `saul.glb` the skinned `saul_ropes` node is moved under the `basket` joint after export
(the Characters role's `_ropes_under_basket`, compiled from `sa_characters.py` by name, not copied). **76 actions =
CONTRACT §4 exactly** (saul 22, ananias 14, barnabas 6, judas 5, priest 2, tallguard 12, shortguard 11, peter 4;
asserted at build; `timelineMissing` []). Verify: every GLB re-imported, sampled pose error ≤ 8e-6.

## 0. Reuse (not copies)

`sa_animate.py` runs `pipeline/rs_animate.py` in its own namespace (definitions only; its final dispatch line is cut
at an asserted anchor); that file runs `ls_animate.py`, which runs `mi_animate.py`. Their clip lists are dropped and
this pack registers its own. Nothing in `mi_*` / `ls_*` / `rs_*` / `sa_characters.py` was edited. Reused functions,
baked on this pack's rigs (every man here is the Miracles friend body):

- Real Miracles: `friend_idle` (idle of all seven men but the priest), `friend_walk` (walk, 0.09 u/s), `friend_wave`
  (Saul, Ananias, Barnabas, Judas, short guard), `friend_cheer` (Saul), Peter's `idle` / `wave`, `peter_laugh`
  (Barnabas, Judas, as The King Who Serves did).
- The King Who Serves: `d_talk` (Saul, Ananias, Barnabas, short guard), `cheer_fn` (Ananias: feet planted beside the
  kneeling Saul), `boast_fn` (short guard), the cross-legged sit (`cross_legs`) under `sit_pray` / `see_again`,
  `kneel_both` under the kneels.
- He Is Risen!: `peter_puff` (both guards' `puff`).
- New here: everything else (march, the letters hand-off, the fall and the blind walk, the basket, the tiptoes, the
  hug, Ananias's scene, the guards' comedy).

Pack-level extensions (in `sa_animate.py`): `solve_pose` places the `basket` bone and the ropes' `ropeTop` from
channels (`basket.at`, `ropeTop.at`, root space) whatever the hips do, and keeps the `jug` / `lantern` hanging in their
rest orientation (Ananias pours by `jug.tilt`); `evaluate_primary` adds `liftmin` (see §4, Saul's cloak); `mix`
carries it.

## 1. Clips (30 fps)

One-shots hold their last frame. speed = naturalSpeed (u/s) of travel clips; minY = lowest real mesh point (rig
space; the basket clips are hung at their basket height, so basket_wait's is ~0.17); drift / slip = planted-foot drift
(in place) or stance slip (travel); seam = loop seam step (all loops `seamOK`).

| Action | Frames | s | Type | Speed | Markers (s) | minY | drift / slip | seam |
|---|---|---|---|---|---|---|---|---|
| `saul_idle` | 120 | 4.00 | loop |  |  | -0.0003 | 0.0001 | 0.0009 |
| `saul_walk` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | -0.0005 | 0.0037 | 0.0099 |
| `saul_wave` | 48 | 1.60 | loop |  |  | -0.0003 | 0.0001 | 0.0051 |
| `saul_cheer` | 30 | 1.00 | loop |  | hop 0.267 | 0.0 | 0.0019 | 0.0083 |
| `saul_talk` | 96 | 3.20 | loop |  |  | 0.0002 | 0.0 | 0.003 |
| `saul_march` | 30 | 1.00 | loop | 0.11 | contactL 0.0, contactR 0.5 | -0.0012 | 0.0 | 0.0201 |
| `saul_angry_talk` | 72 | 2.40 | loop |  | stamp 1.4 | 0.0005 | 0.0001 | 0.0009 |
| `saul_take_letters` | 72 | 2.40 | one-shot |  | grab 0.333, up 1.067, tuck 1.933 | 0.0005 | 0.0 |  |
| `saul_sit_look_up` | 90 | 3.00 | loop (seated) |  |  | -0.0047 | 0.0 | 0.0004 |
| `saul_fall_down` | 42 | 1.40 | one-shot (seated) |  | shield 0.2, bump 0.7 | -0.0042 | 0.0102 |  |
| `saul_get_up_blind` | 48 | 1.60 | one-shot (seated) |  | push 0.333, up 1.133 | -0.002 | 0.0158 |  |
| `saul_walk_blind` | 48 | 1.60 | loop | 0.05 | contactL 0.0, contactR 0.8 | -0.0006 | 0.0017 | 0.0017 |
| `saul_sit_pray` | 120 | 4.00 | loop (seated) |  | shake 3.2 | -0.008 | 0.0 | 0.0004 |
| `saul_see_again` | 48 | 1.60 | one-shot (seated) |  | rub 0.2, open 0.667, joy 1.067 | -0.0079 | 0.0 |  |
| `saul_kneel` | 120 | 4.00 | loop (seated) |  |  | -0.001 | 0.0 | 0.0004 |
| `saul_eat_bread` | 90 | 3.00 | one-shot (seated) |  | take 0.2, bite 1.2, laugh 2.2 | -0.002 | 0.0 |  |
| `saul_preach` | 120 | 4.00 | loop |  |  | -0.0002 | 0.0002 | 0.0007 |
| `saul_basket_wait` | 90 | 3.00 | loop (seated) |  |  | 0.169 | 0.0 | 0.0003 |
| `saul_basket_down` | 180 | 6.00 | one-shot (seated) |  | drop1 0.267, drop2 1.267, drop3 2.267, drop4 3.267, drop5 4.267, drop6 5.267, land 5.6 | -0.0003 | 0.0 |  |
| `saul_basket_out` | 42 | 1.40 | one-shot |  | stand 0.333, stepL 0.7, stepR 1.0, wave 1.067 | -0.0008 | 0.0005 |  |
| `saul_tiptoe` | 48 | 1.60 | loop | 0.06 | contactL 0.0, contactR 0.8 | -0.0001 | 0.0 | 0.0027 |
| `saul_hug` | 60 | 2.00 | loop |  |  | 0.0 | 0.0001 | 0.0005 |
| `peter_hug` | 60 | 2.00 | loop |  |  | -0.0 | 0.0001 | 0.0006 |
| `ananias_idle` | 120 | 4.00 | loop |  |  | -0.0007 | 0.0001 | 0.0006 |
| `ananias_walk` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | -0.0018 | 0.0 | 0.0085 |
| `ananias_wave` | 48 | 1.60 | loop |  |  | -0.0008 | 0.0001 | 0.0012 |
| `ananias_talk` | 96 | 3.20 | loop |  |  | 0.0001 | 0.0 | 0.0006 |
| `ananias_cheer` | 40 | 1.33 | loop |  | bounce 0.333 | -0.0007 | 0.0001 | 0.0026 |
| `ananias_kneel_pray` | 120 | 4.00 | loop (seated) |  |  | -0.0017 | 0.0 | 0.0003 |
| `ananias_kneel_look_up` | 96 | 3.20 | loop (seated) |  |  | -0.0017 | 0.0 | 0.0005 |
| `ananias_startle` | 30 | 1.00 | one-shot (seated) |  | jump 0.2, land 0.533 | -0.0017 | 0.0052 |  |
| `ananias_nervous` | 60 | 2.00 | loop |  | gulp 1.333 | 0.0002 | 0.0 | 0.0009 |
| `ananias_tiptoe` | 36 | 1.20 | loop | 0.06 | contactL 0.0, contactR 0.6 | -0.001 | 0.0 | 0.0025 |
| `ananias_knock` | 30 | 1.00 | one-shot |  | knock 0.2 | 0.0002 | 0.0009 |  |
| `ananias_hands_on` | 90 | 3.00 | loop |  |  | 0.0006 | 0.0 | 0.0002 |
| `ananias_pour` | 72 | 2.40 | one-shot |  | lift 0.2, pour 0.6, stop 2.0 | -0.0014 | 0.0003 |  |
| `ananias_listen` | 96 | 3.20 | loop |  |  | -0.0006 | 0.0002 | 0.0012 |
| `judas_listen` | 96 | 3.20 | loop |  |  | -0.0001 | 0.0001 | 0.0003 |
| `tallguard_listen` | 96 | 3.20 | loop |  |  | -0.0006 | 0.0001 | 0.0003 |
| `shortguard_listen` | 96 | 3.20 | loop |  |  | -0.0002 | 0.0002 | 0.0003 |
| `barnabas_idle` | 120 | 4.00 | loop |  |  | 0.0 | 0.0001 | 0.0007 |
| `barnabas_walk` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | 0.0007 | 0.004 | 0.0097 |
| `barnabas_wave` | 48 | 1.60 | loop |  |  | 0.0001 | 0.0001 | 0.0022 |
| `barnabas_laugh` | 48 | 1.60 | loop |  | slap1 0.4, slap2 1.2 | 0.0006 | 0.0027 | 0.002 |
| `barnabas_talk` | 96 | 3.20 | loop |  |  | 0.0003 | 0.0 | 0.002 |
| `barnabas_arm_round` | 90 | 3.00 | loop |  |  | 0.0003 | 0.0001 | 0.0011 |
| `judas_idle` | 120 | 4.00 | loop |  |  | -0.0001 | 0.0001 | 0.0092 |
| `judas_wave` | 48 | 1.60 | loop |  |  | -0.0001 | 0.0001 | 0.0014 |
| `judas_laugh` | 48 | 1.60 | loop |  | slap1 0.4, slap2 1.2 | 0.0006 | 0.0028 | 0.007 |
| `judas_offer_bread` | 60 | 2.00 | loop |  | bow 0.667 | 0.0003 | 0.0 | 0.003 |
| `priest_idle` | 150 | 5.00 | loop |  |  | 0.0001 | 0.0 | 0.0001 |
| `priest_give_letters` | 36 | 1.20 | one-shot |  | out 0.6, give 1.0 | 0.0001 | 0.0 |  |
| `tallguard_idle` | 120 | 4.00 | loop |  |  | -0.0007 | 0.0001 | 0.0002 |
| `tallguard_walk` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | -0.001 | 0.0 | 0.0105 |
| `shortguard_idle` | 120 | 4.00 | loop |  |  | -0.0003 | 0.0001 | 0.0008 |
| `shortguard_walk` | 40 | 1.33 | loop | 0.09 | contactL 0.0, contactR 0.667 | -0.0006 | 0.0 | 0.008 |
| `shortguard_wave` | 48 | 1.60 | loop |  |  | -0.0003 | 0.0001 | 0.0032 |
| `shortguard_talk` | 96 | 3.20 | loop |  |  | 0.0002 | 0.0 | 0.0027 |
| `shortguard_boast` | 72 | 2.40 | loop |  |  | -0.0011 | 0.0002 | 0.0009 |
| `tallguard_puff` | 60 | 2.00 | loop |  | breath1 0.333, breath2 1.333 | 0.0019 | 0.0 | 0.0006 |
| `shortguard_puff` | 60 | 2.00 | loop |  | breath1 0.333, breath2 1.333 | 0.0003 | 0.0 | 0.0003 |
| `tallguard_walk_puff` | 24 | 0.80 | loop | 0.085 | contactL 0.0, contactR 0.4 | 0.0009 | 0.0 | 0.0034 |
| `shortguard_walk_puff` | 20 | 0.67 | loop | 0.085 | contactL 0.0, contactR 0.333 | -0.0003 | 0.0 | 0.0036 |
| `tallguard_shrug` | 36 | 1.20 | one-shot |  | shrug 0.467 | 0.0003 | 0.0 |  |
| `tallguard_duck` | 45 | 1.50 | one-shot |  | duck 0.267, peep 1.0 | 0.0007 | 0.0001 |  |
| `shortguard_duck` | 45 | 1.50 | one-shot |  | duck 0.267, peep 1.0 | 0.0002 | 0.0002 |  |
| `tallguard_amazed` | 90 | 3.00 | loop |  |  | 0.0004 | 0.0 | 0.0003 |
| `shortguard_amazed` | 90 | 3.00 | loop |  |  | 0.0006 | 0.0 | 0.0009 |
| `tallguard_lead_hand` | 48 | 1.60 | loop | 0.05 | contactL 0.0, contactR 0.8 | -0.0015 | 0.0009 | 0.0071 |
| `tallguard_scratch_head` | 72 | 2.40 | loop |  |  | -0.0001 | 0.0 | 0.0046 |
| `tallguard_lantern_peer` | 120 | 4.00 | loop |  |  | 0.0004 | 0.0 | 0.0002 |
| `tallguard_wave` | 48 | 1.60 | loop |  |  | -0.0005 | 0.0001 | 0.0015 |
| `shortguard_doze` | 120 | 4.00 | loop |  | jerk1 1.733, jerk2 3.933 | -0.0002 | 0.0002 | 0.0008 |
| `peter_idle` | 180 | 6.00 | loop |  |  | -0.003 | 0.0003 | 0.0007 |
| `peter_wave` | 48 | 1.60 | loop |  |  | -0.0041 | 0.0002 | 0.012 |
| `peter_peek_afraid` | 45 | 1.50 | one-shot |  | peek 0.333, back 0.867 | -0.0016 | 0.0001 |  |

**Travel speeds for story.py** (replace the planned V_*): `V_MARCH` 0.110 (saul_march), `V_WALK` 0.090 (every
walk), `V_BLIND` 0.050 (saul_walk_blind = tallguard_lead_hand), `V_TIPTOE` 0.060 (saul_tiptoe = ananias_tiptoe),
`V_PUFF` 0.085 (both walk_puff). They equal the planned values, so the timeline needs no re-time for speed.

## 2. Stage numbers the clips assume

| What | Value | Where it comes from |
|---|---|---|
| Hand-in-hand walk | the tall guard **0.14** ahead of Saul on the same line, same speed, both facing the travel | Saul's belly (front 0.053) + the guard's back (0.041) + two hands do not fit in 0.08-0.10 on one line; at 0.14 the hands meet (gap 0.001); at 0.12 they miss by 0.014 |
| Joined hands | Saul-local (0.004, 0.190, 0.085) | `HOLD_PT` |
| Hug | Saul / Peter **0.10**, facing, both started at the same instant | CONTRACT; bodies touch (43 proxy points < 4 mm, belly to belly, no visible pass-through on the probes) |
| hands_on | Ananias on ANANIAS_TOUCH facing Saul, Saul on SAUL_MAT `sit_pray` facing the viewer | palms on the top of the skull of sit_pray frame 0 (gap 0.002) |
| pour | Ananias on ANANIAS_POUR facing Saul, Saul on SAUL_MAT `kneel` facing the viewer | the jug over the crown of kneel frame 0; Ananias goes on tiptoe (he is 0.33, the kneeling Saul's crown is high) |
| arm_round | Saul **0.10 to Barnabas's right** (his −X), both facing Peter | an arm round the shoulders of someone *beside* him |
| take_letters / give_letters | priest on PRIEST (y 0.04) facing Saul, Saul on SAUL_PORCH facing the priest | hand-off point on the line between them, 0.095-0.110 from the priest, y 0.235 |
| knock | Ananias on JUDAS_DOOR facing `judasHouse` (origin (−0.155, −0.44)) | the left knuckles aimed at SET.md's one post (−0.20, −0.305) |
| Basket | Saul's mark **SAUL_BASKET = BASKET_DOWN + (0, 0.08) = (0.095, −0.38)**, face viewer, y 0 | the basket hangs 0.08 behind his root at BASKET_DOWN; `ropeTop` is keyed to rig-local (−0.065, 0.235, −0.08) = the window (0.030, 0.235, −0.46) |

## 3. Staging — for the lead (story.py changes needed)

1. **S11 basket mark** (required): `basket_wait` / `basket_down` / `basket_out` must play with Saul at
   **(0.095, −0.38)**, face viewer, not at BASKET_DOWN. The basket and the ropes are still drawn at BASKET_DOWN and the
   window. Reason: he climbs out over the **front** rim (toward the viewer: the believers' house at x 0.16 leaves no
   room at +X as CONTRACT §4 planned) and must end standing on his root, so the tiptoe can start there without a slide.
   The tiptoe then goes from (0.095, −0.38) (SET.md's end (0.12, −0.36) is only 0.03 away: pick a new end, e.g.
   (0.13, −0.33), behind the dozing guard's back, and re-check clearance).
2. **S11 timing**: `basket_down` touches down at **5.6 s** (`land`, frame 168), not 6.0; `basket_land` sfx at
   clip + 5.6 s. `basket_out` climbs out by 1.0 s and waves from 1.07 s; the basket shrink at 1.4 s is right.
3. **S05 hand in hand**: the guard must lead by **0.14**, not ~0.10. Easiest: start Saul's `walk_blind` path
   **0.76 s after** the guard's `lead_hand` path (both at 0.05 u/s; LIGHT→ROAD_D is 0.102). At the corners (ROAD_E,
   GATE_OUT) the two turn at different moments, so for ~1 s per corner the hands drift apart (not probed in motion:
   StoryDirector does the turning).
4. **S01 letters**: show `saul/letters` at `take_letters` + **0.33 s** (marker `grab`), not 0.1 s before the clip
   starts (it would pop into his pointing angry_talk hand). The priest's hand stays out to the end of give_letters,
   so the 1.1 s offset between the two clips is fine.
5. **S12 arm_round**: give Barnabas `face="peter"` (not saul) and have Saul **stand still at (0.40, −0.24) facing
   Peter** while Barnabas has his arm round him (that mark is 0.018 from the exact spot the clip assumes,
   (0.393, −0.257)). Today Saul walks off to the hug 1.0 s after arm_round starts: let the arm stay at least through
   sa_38's end, then switch Barnabas to `talk`/`laugh` before Saul walks.
6. **S06 / S09 Judas**: `offer_bread` with a `to` glides (0.04 in S06, 0.063 in S09): use `walk` for the move, then
   `offer_bread` in place.
7. **Speeds**: the V_* values stand (table above). `travel` in clips.json lists every move; ones the build flags as
   glides are all snaps on cuts except Judas's two above.
8. **A8**: none (no actor gets two clips at the same instant).
9. Markers for sync: `fall_down` bump 0.7 s (sit_thud), `knock` first tap 0.2 s, `pour` 0.6-2.0 s, `eat_bread` bite
   1.2 s, `sit_pray` head shake 3.2 s after the S06 cut (Judas offers at +3.0 s), `doze` head jerks 1.73 s / 3.93 s.

**Set problems the lead must route to the set role** (`setCheck` in clips.json, real `damascus.glb`, proxy points
inside set meshes):
- **Ananias's room is too narrow for Ananias.** Inner width 0.11 (x −0.585…−0.475); Ananias with his arms down is
  ~0.13 wide, so in `kneel_pray`, `kneel_look_up`, `startle` and `nervous` his arms and knees go into the side walls
  (thousands of proxy points; plainly visible on the contact sheet from the S07 camera). The elbows are already tucked.
  Widen the room to ≥ 0.17 inside, or start the S07 camera where the side walls do not show the arms.
- **SHORT_GATE (0.11, −0.27)**: the short guard's right arm and hand go into the back gate tower / torch1 in `boast`
  and `doze`. Move him to x ≥ 0.14.
- **JHOUSE_DOOR (0.24, −0.37)**: Peter turned toward Saul (`peek_afraid`, face saul) puts his left arm and hand into
  the believers' house face beside the doorway. z −0.35 would clear it.
- **Basket landing**: Saul is ~0.16 wide at the shoulders with the cloak; the gap between the wall face (0.027) and the
  believers' house (0.16) is 0.133. Facing the viewer he does not fit, so in the basket he kneels **turned to face +X**
  (back to the wall), turning to the viewer as he stands to climb out. Fits now: body ≥ 0.015 from the wall face,
  basket edge 0.013-0.015 from it; the left forearm comes within ~0.003 of the house corner on the last drop. A wider
  gap (house moved right ~0.03) would remove the risk.
- **S03 milestone** (0.24, 0.19): Saul's raised left knee / foot touches it in `sit_look_up` / `fall_down` (≤ 23 proxy
  points). Minor; LIGHT 0.02 left or the milestone 0.02 further out.
- Saul's cloak hem behind him on the S06/S09 mat touches the room's back-wall area (judasHouse, ≤ 240 proxy points of
  the cloak panel only): hidden behind him from the S06/S08/S09 cameras. Not fixed.
- (`jerusalemDoor` hits on the basket clips are the doorway's dark inner box, whose faces point inward; they are not
  real contacts. `priestPorch` hits on give_letters are the priest's fingers near the porch's front edge at y 0.20.)

## 4. Hard spots (RIG.md "For Animation") — what was done

- **The basket.** A crouched or seated Saul does not fit a 0.10 basket (RIG.md §2); tried: knees to the chest
  (knees end 0.07 outside the rim), legs over the rim (dangle into the house). Done: he **kneels upright** in it
  (knees on the floor, toes tucked, `BASKET_KNEEL`), hands on the rim, turned +X; the robe skirt still bulges
  ~0.02 past the basket wall below the rim (visible only very close; the house hides the lower basket from the S11
  camera). The basket is placed by its own channel (not by the hips: it is their child in the skeleton), the rope tops
  stay at the window in every frame (`basketCheck`: ropeTop (0.030, 0.235, −0.46) in all frames, inside the window,
  below the wall top). The cloak's back panel is folded (cloak1 scaled 0.45 along the bone) so it does not hang out of
  the basket bottom. **DESIGN asked for a 0.13 basket; at 0.12-0.13 Saul could sit**: lead + Characters decision.
- **Seated clips below the ground** (fall_down, sit_look_up, sit_pray, see_again, get_up_blind): Saul's cloak sides
  are skinned 65-86 % to `shoulderL/R` down to the hip line (RIG.md says the skirt part is on cloak1 / the legs; the
  side panels are on the shoulders), so seated they went 0.02 through the page. `liftmin` raises the hips until every
  cloak-side vertex is ≥ −0.003: meshMinY now −0.0047…−0.008, the seat floats ≤ ~0.015 inside the cloak's drape.
  **Characters fix**: re-weight the cloak's side panels below the waist to hips / thighs / cloak1.
- **The hug at 0.10**: hips back 0.014 and chests leaning in, Saul's arms over Peter's shoulders, Peter's round his
  back, heads to each one's own right; bodies touch, no deep pass-through on the probes; sandals 0.006 back.
- **Cloak swing on Saul**: `cloak1` is a spring chain (70 / 7 / 0.3 / 16°); `march` adds a back swing of 14° ± 8°
  on the primary; seated clips swing it back 70-75° over the ground, kneeling 35°, heels 55°.
- **Hand in hand** (S05): see §2/§3 (0.14).

## 5. Weak / not verified

- Nothing looked at in Unity or on the phone. The ropes-under-joint GLB trick is the Characters role's; repeated
  here on export (`SA_ROPES_UNDER_BASKET True`) but not checked in glTFast.
- Planted-foot drift above 0.002 in the transitions `fall_down` (0.010) and `get_up_blind` (0.016) (the legs fly out
  / are drawn in, lifted, but the ends of the move still skate a little), `ananias_startle` (0.005), and the reused
  `peter_laugh` on Barnabas / Judas (0.003, as in The King Who Serves).
- Pairs are probed standing still at their marks; the S05 corners and the S12 walk-off are not.
- The basket kneel and the robe through the basket wall are the weakest pictures in the pack; the S11 shot should be
  looked at in Unity with the lead's yaw-25 camera.
- `priest_give_letters`: the priest has no scroll prop, so his outstretched fist is empty; `take_letters` relies on
  the timeline showing `saul/letters` at the grab.
- The `get_up_blind` lids stay open (the line says "my eyes are open"); CONTRACT said eyes closed: the `blind` decal
  decides.
- Ananias in his room (S07) is the one clearly visible defect left on the contact sheet (set width, §3).
