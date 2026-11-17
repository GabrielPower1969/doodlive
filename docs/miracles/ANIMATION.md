# Real Miracles — animation (Animation role)

Built by `pipeline/mi_animate.py` (kit-based, same shape as `pipeline/jn_animate.py`):

    python3 pipeline/mi_animate.py all      # build + verify + contact sheet + freshness check (~3.5 min)
    MI_PROBE="man_stand_wobbly:0,60,90:front" python3 pipeline/mi_animate.py probe
    MI_PROBE="carry:0,12:side,q3" python3 pipeline/mi_animate.py probe                       # the carry group
    MI_PROBE="pair:peter_shake_awake:jesus_lie_sleep:0.10:8:front:q3,side" python3 pipeline/mi_animate.py probe

Outputs: `assets/miracles/anim/{jesus,peter,man,friend1,friend2,friend3,friend4}.glb` (character + skin + one glTF
animation per action `<char>_<clip>`), `clips.json` (lengths, loop flags, markers, natural speeds, root-motion notes,
stage numbers, per-clip checks, travel table), `contact_sheet.png`. The model GLBs in `assets/miracles/model/` are not
touched. 86 actions: jesus 13, peter 13, man 12, friend1-4 12 each — every clip of CONTRACT §4, exact names, no extras.
The four friends share one function per clip, baked on each friend's own rig; free loops (idle, think, dig, peek,
cheer, wave, lower_rope) are phase-shifted per friend so a group never moves in unison; walk and both carry clips are
never shifted.

## 1. Clips (30 fps)

`friendN` = friend1 … friend4 (identical lengths, markers and speeds). One-shots hold their last frame.

| Action | Frames | s | Type | Speed (u/s) | Markers (s) | Root motion |
|---|---|---|---|---|---|---|
| `jesus_idle` | 150 | 5.00 | loop | | | |
| `jesus_talk` | 96 | 3.20 | loop | | | |
| `jesus_walk` | 36 | 1.20 | loop | 0.097 | contactL 0, contactR 0.6 | |
| `jesus_teach` | 180 | 6.00 | loop | | | |
| `jesus_look_up_smile` | 60 | 2.00 | one-shot | | look 0.47, laugh 1.0 | |
| `jesus_kneel_kind` | 60 | 2.00 | one-shot | | down 1.0 | |
| `jesus_stand_talk` | 54 | 1.80 | one-shot | | up 0.87 | |
| `jesus_command_rise` | 50 | 1.67 | one-shot | | rise 0.8 | |
| `jesus_lie_sleep` | 150 | 5.00 | loop (lying) | | | |
| `jesus_wake_up` | 96 | 3.20 | one-shot | | eyes 0.33, kneel 1.33, stand 2.73 | |
| `jesus_calm_storm` | 72 | 2.40 | one-shot | | **calm 1.0** | |
| `jesus_laugh` | 54 | 1.80 | one-shot (ends neutral) | | laugh 0.4 | |
| `jesus_wave` | 60 | 2.00 | loop | | | |
| `peter_idle` | 180 | 6.00 | loop | | | |
| `peter_talk` | 96 | 3.20 | loop | | | |
| `peter_walk` | 36 | 1.20 | loop | 0.111 | contactL 0, contactR 0.6 | |
| `peter_roof_shock` | 50 | 1.67 | one-shot | | hit 0.13, hands 0.73 | |
| `peter_dust_off` | 78 | 2.60 | one-shot | | shake 1.53 | |
| `peter_laugh` | 48 | 1.60 | loop | | slap1 0.4, slap2 1.2 | |
| `peter_steer` | 120 | 4.00 | loop | | | |
| `peter_steer_hard` | 72 | 2.40 | loop | | heaveL 0.47, heaveR 1.67 | |
| `peter_bail` | 36 | 1.20 | loop | | scoop 0.3, throw 0.8 | |
| `peter_shake_awake` | 48 | 1.60 | loop | | shake1 0.27, shake2 1.07 | |
| `peter_amazed` | 66 | 2.20 | one-shot | | look 1.0 | |
| `peter_cower` | 60 | 2.00 | loop | | thunder 0.67 | |
| `peter_wave` | 48 | 1.60 | loop | | | |
| `man_lie_mat` | 120 | 4.00 | loop (lying) | | | |
| `man_carried` | 48 | 1.60 | loop (lying) | | stepL 0, stepR 0.8 | static lift + bob |
| `man_lowered` | 150 | 5.00 | one-shot | | **land 4.8** | +0.40 → 0 |
| `man_sit_up` | 84 | 2.80 | one-shot | | up 1.33, toes 1.87 | |
| `man_stand_wobbly` | 126 | 4.20 | one-shot | | up 1.73, step1 2.4, step2 2.93, straight 3.6 | |
| `man_jump_joy` | 66 | 2.20 | one-shot (ends neutral) | | hop1 0.53, hop2 1.27 | |
| `man_roll_mat` | 90 | 3.00 | one-shot | | **switch 1.2**, shoulder 1.87 | |
| `man_dance_mat` | 48 | 1.60 | loop | 0.134 | spin 1.07 | |
| `man_walk_mat` | 32 | 1.07 | loop | 0.116 | contactL 0, contactR 0.53 | |
| `man_talk` | 96 | 3.20 | loop | | | |
| `man_idle` | 120 | 4.00 | loop | | | |
| `man_wave` | 48 | 1.60 | loop | | | |
| `friendN_idle` | 120 | 4.00 | loop | | | |
| `friendN_walk` | 40 | 1.33 | loop | 0.090 | contactL 0, contactR 0.67 | |
| `friendN_carry_front` | 48 | 1.60 | loop | 0.090 | contactL 0, contactR 0.8 | |
| `friendN_carry_back` | 48 | 1.60 | loop | 0.090 | contactL 0, contactR 0.8 | |
| `friendN_squeeze_bounce` | 120 | 4.00 | one-shot | | **boing 1.6**, sit 1.93, up 3.33 | +0.06, then back to −0.02 |
| `friendN_think` | 90 | 3.00 | loop | | | |
| `friendN_idea` | 45 | 1.50 | one-shot | | idea 0.33 | |
| `friendN_dig` | 36 | 1.20 | loop (kneeling) | | tossR 0.4, tossL 1.0 | |
| `friendN_lower_rope` | 40 | 1.33 | loop (kneeling) | | handL 0, handR 0.67 | |
| `friendN_peek` | 60 | 2.00 | loop (kneeling) | | | |
| `friendN_cheer` | 30 | 1.00 | loop | | hop 0.27 | |
| `friendN_wave` | 48 | 1.60 | loop | | | |

Kneeling / lying clips are built in the actor's own space and work at base y ROOF (0.40) or DECK (0.06) as at 0.

## 2. Props and root motion

- **Ropes**: every man clip keeps the `ropes` bone scaled to 0.001; only `lowered` scales them in (frames 0-3) and out
  (frames 139-144, gone at `land`). The `man/ropes` node may therefore stay shown; hiding it outside S05 is harmless.
- **Mat**: at rest (flat, under the root) in `lie_mat`, `lowered`, `sit_up`, `stand_wobbly`, `jump_joy`, `roll_mat`.
  In the standing ones he stands *on* the 0.025 pad (feet raised by the pad). In `carried` the mat bone is turned 90°
  so the poles run along the facing, and moved +0.02 in z so the poles sit at x ±0.0675 on the actor's centre line.
- **matRoll**: the switch `mat` → `matRoll` must be a timeline prop event at `roll_mat` start + **1.2 s** (marker
  `switch`). `roll_mat` (after the switch), `dance_mat`, `walk_mat`, `idle`, `wave` pose the roll bone (rx 35°, ry 20°,
  tx +0.008) so it slants down-forward off the shoulder and its end disc no longer covers his face; the left hand
  holds it. `man_talk` has both hands free and does not pose the roll: do not show `matRoll` during `talk`.
- **Bucket**: only `peter_bail` is posed for it (prop shown at S10, as story.py does).
- **Root motion**: `carried` lifts the root 0.041 (pole centres at world 0.15 on base `CARRY_Y` 0.10; the contract's
  "mat at local 0.05" is the mat bone at 0.055) and bobs it 4 mm per step. `lowered` starts the root at +0.40 and
  lands it at 0 at 4.6 s. `squeeze_bounce` moves the root +0.06 then flings it back to −0.02.

## 3. Staging (for the lead: story.py)

1. **Carry spacing is 0.24, not 0.16.** The poles end at ±0.2036 (RIG.md §3) and the front carrier holds them with his
   hands 0.04 behind his hips (CONTRACT §4), so his root is 0.24 ahead of the man's; the back carrier mirrors it.
   At 0.16 the carriers stand inside the stretcher, through the man's head and feet (he is 0.34 long). Clips are
   fitted to `CARRY_D` = 0.24 (one constant in the script). Place friend1 = man + 0.24·d, friend2 = man − 0.24·d,
   where d is the unit facing vector; the current marks are 0.117 apart and not along the facing (S02: man (0.20, 0.14),
   friend1 (0.10, 0.08), friend2 (0.30, 0.20), facing "house"). Group length root-to-root 0.48.
2. **Start the three carry clips on the same frame** and move them with identical `dt` and identical displacement
   (48-frame cycle, 0.09 u/s; the man's bob is in step with the carriers' feet). Right now the S03 move (t 52.2) gives
   the man 0.52, friend1 0.55 and friend2 0.49 in 3.4 s: the group would stretch, and friend1 needs 1.8× the natural
   speed (cap 1.6). It needs ≥ 6.1 s at 0.09 u/s.
3. **The stair** is 0.38 long, the carry group 0.48: the carriers will be at different heights while the mat stays
   level in the clip (no pitch). With the current marks that may look fine from far away; check the S04 shot.
4. **carried → lie_mat** (S04, on the roof): `carried` lays the body along the facing (head to −Z, feet first);
   `lie_mat` lays it along local X (head to −X). Give `lie_mat` a facing 90° clockwise from the carried facing (seen from
   above: yaw_lie = yaw_carried − 90°) and the body and mat keep their world orientation; otherwise they spin 90° in the
   0.25 s blend.
5. **lowered**: play at `LAND`, `y=0`, `snap=True` (as story.py does); no lead-in needed. The mat is 0.30 × 0.12, the
   hole 0.12 × 0.12 and the ropes rise straight up from the pad corners (±0.15, ±0.06), outside the hole: the mat
   cannot visibly fit through the hole. Set / lead decision (a longer hole, or accept). Rope tops are held at local
   y 0.47; the friends' `lower_rope` hands are at their own feet + 0.035…0.11, 0.115 ahead, not at the rope tops.
6. **kneel_kind** assumes the man lies 0.12 in front of Jesus, both facing each other (man's right side toward Jesus).
   Story: Jesus (−0.34, −0.40) to LAND (−0.24, −0.38) = 0.102; at that distance his front foot reaches the near pole.
   Suggested Jesus mark (−0.36, −0.40) (0.122).
7. **sit_up / stand_wobbly**: sitting up he faces his feet = the actor's local +X; with `face="jesus"` at LAND that is
   the viewer, good for the camera. `stand_wobbly` turns his body back to the actor's local +Z (front) while standing
   up. Keep the same `face` for `sit_up` and `stand_wobbly` (the body then turns from the viewer to Jesus while rising);
   if `stand_wobbly` gets `face="viewer"` the director turns the root while the clip also turns the body: a double turn.
   Turn him to the viewer on `jump_joy`.
8. **lie_sleep / shake_awake**: Jesus lies on his left side facing the viewer, root under his shoulder, head toward his
   +X (the cushion is +0.025 x from BOAT_STERN), hips 0.115 toward −X, knees drawn toward +Z, feet at about −0.22 x.
   Peter at BOAT_WAKE (0.38, −0.32) would stand on Jesus's hips. `shake_awake` is fitted to Peter **in front of** the
   sleeper, facing him, his upper shoulder 0.10 ahead: e.g. Jesus at (0.47, −0.375) facing viewer, Peter at
   (0.47, −0.275) facing jesus (the hull's front edge is z −0.27, so Peter's toes are at the gunwale). Then
   `wake_up` (ends standing at Jesus's root) and Peter's `amazed` work from there.
9. **squeeze_bounce** has root motion; story.py gives it `to=YARD` (a glide on top). Walk friend3 to YARD first and
   play `squeeze_bounce` without `to`. He ends 0.02 behind the mark.
10. **dance_mat** travels at 0.134 u/s; the S07 move asks 0.54 in 13.4 s (0.04 u/s, rate 0.3: the feet would skate).
    Dance for ~4 s (0.54 / 0.134), then `wave` / `idle` on the mark, or shorten the dance move.
11. **peter_steer**: the right hand holds an imagined oar handle at his right side, waist high. At BOAT_PETER facing the
    viewer that hand is toward the bow, not at the boat's steering oar (stern, x ≈ 0.56).
12. **peter_bail** throws to his own left. Facing the viewer at BOAT_PETER his left is +x (along the boat); to throw
    over the front gunwale give him `face` toward the bow (−x).
13. A8: Jesus `look_up_smile` and Peter `dust_off` start 0.6 s apart in S05, fine. No clip here needs two clips of one
    actor at the same instant.

## 4. Checks (clips.json `checks`, last build)

- Contract: 86/86 actions present, exact names; re-imported GLB poses match the build (max sample error 8e-6).
- Loops: every seam step ≤ the clip's largest inner step (`seamOK` true for all 63 loop actions).
- Lying / kneeling / seated (`seated` flag): lowest mesh point ≥ −0.008 for all (lie_mat 0.0018 = the mat,
  lie_sleep +0.001, wake_up −0.002, kneel_kind −0.002, dig −0.0067 worst (friend4), peek −0.0038 worst).
- Locomotion stance slip ≤ 0.0042 u/s (walks, carries, walk_mat); planted feet ≤ 0.002 in all in-place loops except
  `peter_laugh` 0.0028 (the knee lift for the thigh slap).
  One-shots that step on purpose read as drift: kneel_kind / stand_talk / roll_mat 0.008 (lifted steps),
  squeeze_bounce 0.016-0.046 (flung back), stand_wobbly 0.134 (legs drawn in from sitting, dragged on the mat).
- Carry group probed in one render at 0.24 (side, q3, top): hands on the pole ends, poles at 0.15, no body contact.
  Pairs probed: shake_awake + lie_sleep (0.10, front mode), kneel_kind + lie_mat (0.12, front mode).
- Anim exports newer than the model files (`fresh` OK).

## 5. Weak / not verified

- Nothing was played in Unity or on the phone. Clip-to-clip blends (0.25 s) were not checked.
- Peter's vest flares out sideways whenever both arms are raised (roof_shock, wave, amazed): a skinning issue in the
  model (Characters role), not fixable from the clips.
- The comedy beats read in the contact sheet at 150 px, but the knock-knees of `stand_wobbly` are subtle; the
  arms-out lurches carry it.
- `dance_mat` spin and `idea` / `dig` arm snaps have large single-frame steps (0.09-0.10) by design (fast); they may
  strobe at 30 fps.
- `steer` / `steer_hard` hold an imagined handle; nothing in the set is at Peter's hands.
- The friends' `lower_rope` hands do not meet the man's rope tops (positions are the lead's).
