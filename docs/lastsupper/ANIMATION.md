# The King Who Serves — animation (Animation role)

Built by `pipeline/ls_animate.py` (same shape as `pipeline/mi_animate.py`, on the kit):

    python3 pipeline/ls_animate.py all      # build + verify + contact sheet + freshness check (~3 min)
    LS_PROBE="peter_refuse:0,20,44:front,side" python3 pipeline/ls_animate.py probe        # single clip, no set, y 0
    LS_PROBE_SET=1 LS_PROBE="donkey_hee_haw:9:phone" python3 pipeline/ls_animate.py probe  # with the jerusalem set
    LS_PROBE="pair:jesus_ride:donkey_walk:0:0,7,14:ride:side,q3" python3 pipeline/ls_animate.py probe
    LS_PROBE="pair:jesus_kneel_wash:andrew_amazed:0.11:30:bench:side,q3" python3 pipeline/ls_animate.py probe
    LS_PROBE="pair:peter_kneel_serve:andrew_sit_wash:0.11:14:front:side,q3" python3 pipeline/ls_animate.py probe
    LS_ONLY=donkey_,jesus_ride python3 pipeline/ls_animate.py build     # bake + check a subset, no export

Outputs: `assets/lastsupper/anim/{jesus,peter,donkey,john,james,andrew,seller1,seller2}.glb` (character + skin + one
glTF animation per action `<char>_<clip>`), `clips.json` (lengths, loop flags, markers, natural speeds, props shown
per clip, per-clip checks, travel table, ride and kneel pair checks), `contact_sheet.png`. The model GLBs are not
touched. **99 actions = CONTRACT §4 exactly**: jesus 21, peter 18, donkey 6, john / james / andrew 14 each,
seller1 / seller2 6 each (the build asserts the set per character; no extras).

## 0. What is shared with Real Miracles (not copied)

`ls_animate.py` runs `pipeline/mi_animate.py` in its own namespace (definitions only; its final mode dispatch is cut
off at an asserted anchor), keeps the Miracles clip functions and helpers, empties the Miracles clip list and
registers this pack's clips. Reused **unchanged** (same function, length, markers, speed):

- jesus `idle` `talk` `walk` `laugh` `wave`; peter `idle` `talk` `walk` `laugh` `wave` (Peter's first four get one
  extra channel: the palm frond is aimed upright after the arm is solved, because the frond is on his right hand
  in S01-S03);
- the Miracles friends' `idle`, `walk`, `wave` for John / James / Andrew (the extras share the friend body) and
  `walk` for both sellers; Peter's Miracles `laugh` for the three disciples ("standing clips as Peter's");
- `peter_amazed`'s upper body inside the seated `amazed` (legs replaced by the bench sit, A4).

A change to those clips in `mi_animate.py` reaches this pack on the next build. Nothing in `mi_*` was edited.
`stand_talk` is **not** the Miracles clip: it must rise from this pack's two-knee kneel (Miracles' one-knee
`kneel_kind` would put the forward foot in the basin, RIG.md §3); it copies its shape (rise via a half-kneel, right
hand up). The donkey's quadruped layer (`quad_gait`, `ik_quad`) is adapted from `da_animate.py` (the lions; not on
the kit) with donkey poles (front knee forward, hind hock back).

## 1. Clips (30 fps)

One-shots hold their last frame. "seated" = meshMinY ≥ −0.008 checked (all pass); they are built in the actor's own
space, so they work at base y 0 and at UPPER (0.10). Disciple / seller rows hold for all of that group (one shared
function each; free loops are phase-shifted per person so a group never moves in unison).

| Action | Frames | s | Type | Speed (u/s) | Markers (s) |
|---|---|---|---|---|---|
| `jesus_idle` | 150 | 5.00 | loop |  |  |
| `jesus_talk` | 96 | 3.20 | loop |  |  |
| `jesus_walk` | 36 | 1.20 | loop | 0.097 | contactL 0.0, contactR 0.6 |
| `jesus_laugh` | 54 | 1.80 | one-shot |  | laugh 0.4 |
| `jesus_wave` | 60 | 2.00 | loop |  |  |
| `peter_idle` | 180 | 6.00 | loop |  |  |
| `peter_talk` | 96 | 3.20 | loop |  |  |
| `peter_walk` | 36 | 1.20 | loop | 0.111 | contactL 0.0, contactR 0.6 |
| `peter_laugh` | 48 | 1.60 | loop |  | slap1 0.4, slap2 1.2 |
| `peter_wave` | 48 | 1.60 | loop |  |  |
| `john/james/andrew_idle` | 120 | 4.00 | loop |  |  |
| `john/james/andrew_walk` | 40 | 1.33 | loop | 0.090 | contactL 0.0, contactR 0.667 |
| `john/james/andrew_wave` | 48 | 1.60 | loop |  |  |
| `seller1/2_walk` | 40 | 1.33 | loop | 0.090 | contactL 0.0, contactR 0.667 |
| `jesus_ride` | 27 | 0.90 | loop | ride 0.090 |  |
| `jesus_ride_wave` | 81 | 2.70 | loop | ride 0.090 |  |
| `jesus_ride_talk` | 81 | 2.70 | loop | ride 0.090 |  |
| `jesus_sad_look` | 66 | 2.20 | one-shot |  | look 1.0 |
| `jesus_tip_table` | 48 | 1.60 | one-shot |  | tip 0.9 |
| `jesus_firm_talk` | 96 | 3.20 | loop |  |  |
| `jesus_open_cage` | 66 | 2.20 | one-shot |  | open 1.6 |
| `jesus_rise_towel` | 90 | 3.00 | one-shot |  | towel 0.8, basin 1.6, pourStart 1.8, pourEnd 3.0 |
| `jesus_kneel_wash` | 72 | 2.40 | loop (seated) |  | scoop1 0.433, scoop2 1.633 |
| `jesus_kneel_talk` | 96 | 3.20 | loop (seated) |  |  |
| `jesus_kneel_laugh` | 54 | 1.80 | one-shot (seated) |  | laugh 0.333 |
| `jesus_stand_talk` | 54 | 1.80 | one-shot |  | up 0.867 |
| `jesus_sit_supper` | 120 | 4.00 | loop (seated) |  |  |
| `jesus_bless_bread` | 96 | 3.20 | one-shot (seated) |  | bread 0.2, break 2.2 |
| `jesus_lift_cup` | 66 | 2.20 | one-shot (seated) |  | cup 0.4, high 1.333 |
| `jesus_smile` | 90 | 3.00 | loop (seated) |  |  |
| `peter_cheer` | 40 | 1.33 | loop |  | bounce 0.333 |
| `john/james/andrew_cheer` | 40 | 1.33 | loop |  | bounce 0.333 |
| `peter_listen_stone` | 96 | 3.20 | one-shot |  | ear 1.0, tap 2.2 |
| `peter_boast` | 72 | 2.40 | loop |  |  |
| `john/james/andrew_boast` | 72 | 2.40 | loop |  |  |
| `peter_argue` | 60 | 2.00 | loop |  |  |
| `john/james/andrew_argue` | 60 | 2.00 | loop |  |  |
| `john/james/andrew_laugh` | 48 | 1.60 | loop |  | slap1 0.4, slap2 1.2 |
| `john/james/andrew_talk` | 96 | 3.20 | loop |  |  |
| `peter_sit_bench` | 120 | 4.00 | loop (seated) |  |  |
| `john/james/andrew_sit_bench` | 120 | 4.00 | loop (seated) |  |  |
| `peter_amazed` | 66 | 2.20 | one-shot (seated) |  | look 1.0 |
| `john/james/andrew_amazed` | 66 | 2.20 | one-shot (seated) |  | look 1.0 |
| `peter_refuse` | 44 | 1.47 | one-shot (seated) |  | jerk 0.2 |
| `peter_offer_all` | 54 | 1.80 | one-shot (seated) |  | thrust 0.333, duck 1.0 |
| `peter_sit_wash` | 120 | 4.00 | loop (seated) |  |  |
| `peter_ashamed` | 66 | 2.20 | one-shot (seated) |  | down 0.667 |
| `john/james/andrew_ashamed` | 66 | 2.20 | one-shot (seated) |  | down 0.667 |
| `peter_sit_supper` | 120 | 4.00 | loop (seated) |  |  |
| `john/james/andrew_sit_supper` | 120 | 4.00 | loop (seated) |  |  |
| `peter_serve_rise` | 48 | 1.60 | one-shot (seated) |  | pick 0.8, down 1.467 |
| `peter_kneel_serve` | 72 | 2.40 | loop (seated) |  | pour 0.467, rub 1.533 |
| `john/james/andrew_sit_wash` | 120 | 4.00 | loop (seated) |  |  |
| `john/james/andrew_nudge` | 60 | 2.00 | loop (seated) |  | jab1 0.4, jab2 1.333 |
| `seller1/2_idle` | 90 | 3.00 | loop |  |  |
| `seller1/2_shout` | 48 | 1.60 | loop |  | cry 0.267 |
| `seller1/2_shock` | 40 | 1.33 | one-shot |  | jump 0.133, land 0.533 |
| `seller1/2_chase_coins` | 24 | 0.80 | loop | 0.073 | contactL 0.0, contactR 0.4, snatchR 0.2, snatchL 0.6 |
| `seller1/2_flap` | 40 | 1.33 | loop |  | flap 0.333 |
| `donkey_idle` | 120 | 4.00 | loop |  |  |
| `donkey_walk` | 27 | 0.90 | loop | 0.090 | hindL 0.0, frontL 0.233, hindR 0.467, frontR 0.667 |
| `donkey_hee_haw` | 60 | 2.00 | one-shot |  | bray 0.3, shake 1.4 |
| `donkey_graze` | 90 | 3.00 | loop |  | bite 0.667 |
| `donkey_sleepy` | 120 | 4.00 | loop |  |  |
| `donkey_happy` | 36 | 1.20 | one-shot |  | hop 0.4 |

Props shown inside a clip (the timeline must show / hide the node at the same moment):
`jesus_rise_towel` towel 0.8 s, basin 1.6 s; `jesus_bless_bread` bread 0.2 s; `jesus_lift_cup` cup 0.4 s;
`peter_serve_rise` towel + jug 0.8 s. story.py already uses exactly these times (tip 0.9 s and open 1.6 s too).

## 2. Stage numbers the clips are fitted to

| What | Number | Where it matters |
|---|---|---|
| Ride | Jesus at base `RIDE_Y` 0.12 on the donkey's mark and heading; hips over the seat (0.155) | S01-S03 |
| Ride cycle | 27 frames = one donkey `walk` cycle (0.9 s); `ride_wave` / `ride_talk` = 81 frames (3 cycles) | the rider's hips follow the walk seat frame by frame, so start `ride` with `donkey walk` on the same beat (story.py does) |
| Donkey walk | 0.0896 u/s (stride 0.05, duty 0.62) | S01-S03 |
| Kneel | the seated person's root `KNEEL_D` 0.11 in front, facing each other; basin bone 0.06 in front of Jesus on the floor (its rest) | WASH marks, PETER_SERVE |
| Bench | seat (cushion top) 0.04; feet planted ~0.066 ahead of the BENCH mark | S07-S09 |
| Supper | cross-legged on the cushion (0.0115), hands on the low table edge (top 0.05, ~0.04-0.05 ahead) | S10-S12 |
| Stones | heap 0.08 in front, tops 0.03 | `listen_stone` at PETER_STONES facing `stones` |
| Tables | near edge 0.06 in front (hands at 0.07 for table2, 0.11 for the cages) | `tip_table` at J_T2 facing table2, `open_cage` at J_T1 facing table1 |
| Basin stand | 0.083 in front of STAND facing `basinStand` (stand top UPPER + 0.08) | `rise_towel` |

## 3. Checks (last build; `clips.json` `checks`, `rideCheck`, `kneelCheck`)

- Contract: 99 actions, the exact CONTRACT §4 set per character (asserted at build); `timelineMissing` []; verify re-imports every GLB and compares sampled bone positions with the build.
- Loops: `seamOK` (seam step ≤ the clip's largest inner step) for 74 / 74 loop actions.
- Seated / kneeling (meshMinY ≥ −0.008): lowest -0.0065 (peter_serve_rise); all 34 pass. Standing clips' lowest: donkey_graze -0.0058, seller2_walk -0.0042, peter_wave -0.0041.
- Walk slip (humans) max 0.0049 u/s (john_walk); donkey walk hoof slip 0.0059 u/s (limit 0.02).
- Planted feet ≤ 0.002 in every in-place clip except these deliberate steps: jesus_stand_talk 0.0308, peter_refuse 0.0184, jesus_tip_table 0.0045, seller1_shock 0.004, seller2_shock 0.0039, peter_laugh 0.0028, john_laugh 0.0028, andrew_laugh 0.0028 (the ride clips' feet hang in the air and are not counted).
- Donkey seat (blanket top): idle 0.1553-0.1554, walk 0.1522-0.1566, hee_haw 0.1551-0.1554, graze 0.1542-0.1542, sleepy 0.1553-0.1554, happy 0.1541-0.1662 (rest 0.1552; walk ±0.0022, idle ±0.0001; `happy` hops 0.011, spare clip).
- Ride pair (one mark, `rideCheck`): rider's seat minus blanket top -0.0051…-0.0051 with `walk` in phase, -0.0192…-0.0039 against `idle` at any phase (negative = sinks into the blanket); rider proxy points inside the donkey's body sections per 9 frames: 129 with walk ({'hips': 70, 'thighL': 13, 'thighR': 32, 'shinR': 8, 'mantle1': 6}). They are the robe and mantle hanging over the withers and the buttocks pressing into the blanket (RIG.md: the robe is not split for straddling); no leg goes through the barrel. Probed side / front / q3 / phone at the walk's high and low seat.
- Kneel pair `kneel_wash + andrew amazed (bench)` at 0.11: closest proxy points 0.0003 (hands on the feet / knees touching), 131 point pairs < 4 mm at frame 18; probed by eye: no body passes through the other.
- Kneel pair `kneel_wash + peter sit_wash (bench)` at 0.11: closest proxy points 0.0003 (hands on the feet / knees touching), 122 point pairs < 4 mm at frame 102; probed by eye: no body passes through the other.
- Kneel pair `kneel_talk + peter refuse (bench)` at 0.11: closest proxy points 0.0009 (hands on the feet / knees touching), 97 point pairs < 4 mm at frame 0; probed by eye: no body passes through the other.
- Kneel pair `kneel_talk + peter offer_all (bench)` at 0.11: closest proxy points 0.0004 (hands on the feet / knees touching), 87 point pairs < 4 mm at frame 48; probed by eye: no body passes through the other.
- Kneel pair `kneel_serve + andrew sit_wash (floor)` at 0.11: closest proxy points 0.0002 (hands on the feet / knees touching), 50 point pairs < 4 mm at frame 96; probed by eye: no body passes through the other.
- Anim exports newer than the model files (`LS_FRESH OK`).

## 4. Staging (for the lead: story.py)

1. **The rider does not move like the donkey (must fix).** The director moves the donkey at its walk speed
   (linear) but Jesus's `ride` clips have no speed, so he glides (eased, dist / 0.12 s): over the S01 move
   (0.20 in 2.2 s for the donkey, 1.7 s for the glide) he runs **up to 0.061 ahead of the seat**, 0.025 on the S02
   and S03 moves (`clips.json` `rideTravel`). Giving the ride clips `naturalSpeed` would make them move together,
   but then the director's arrival hand-off switches Jesus to his standing `idle` on the donkey's back. I wrote
   `rideSpeed` (= the donkey walk speed) and `rideWith` into the three ride clips in `clips.json` instead. Needs a
   small StoryDirector change (lead / Unity): travel at `rideSpeed` like a locomotion clip but without the idle
   hand-off; or parent the rider to the donkey's root while a ride clip plays.
2. **Keep the rider's heading = the donkey's.** `ride_talk` (S03, t 34.4) has `face="viewer"`: the director would
   turn Jesus 90° on the donkey's back (legs through the barrel). Use `face="house"`: the clip already turns His
   chest and head to His left, which is toward the viewer when the donkey faces the house. Same for the S01
   `hee_haw` (`face="viewer"`, t 10.0): either keep the donkey facing `house` (the head-up bray reads in profile)
   or give Jesus `act("jesus", "ride", face="viewer")` on the same beat so both turn on the same root.
3. **Kneeling down needs a lead-in (A4).** `kneel_wash` is a loop; from `walk` the default 0.25 s blend drops Him
   onto His knees. There is no `kneel_down` clip in the contract. Cheapest: `act("jesus", "kneel_wash", ...,
   blend=0.8)` in S07 and S08 (the act's own blend). If that still pops on the phone, the contract needs a one-shot
   `jesus_kneel_down` (≈1 s); I did not add it (R13).
4. **The basin slides along the floor while He walks.** The `basin` bone rests on the floor 0.06 in front of His
   root in every clip except `rise_towel` (which carries it at the waist). Hide `jesus/basin` (`grow=0.3`) when the
   walk to ROUND starts in S07 and when He walks to Peter in S08; show it again (`grow=0.4`) at `kneel_wash`.
5. **The jug vanishes in `rise_towel`.** `jerusalem/basinJug` is the basin *and* the jug; hiding it at 1.6 s also
   removes the jug, and Jesus has no jug prop, so the pour (1.8-3.0 s) is water falling into the basin He holds.
   Either the Set role splits `basinJug` (basin only), or accept.
6. **Peter hides Andrew in S12.** Peter kneels 0.11 in front of Andrew, who faces the viewer, so Peter's back is
   between Andrew and the S12 camera (yaw −40 from Peter). Proposal: PETER_SERVE ≈ (−0.48, −0.38) (Andrew's
   front-left, still ~0.08 from his feet) with `face="andrew"`, or turn Andrew `face` toward the camera's side.
   Pair checked at the contract geometry (0.11, facing): hands on the feet, no body contact.
7. **`nudge` faces.** The clip leans and jabs toward the neighbour *beside* him: James to his left, John to his
   right (they sit side by side at the table, John at +x). Use `face="viewer"` for both in S12; with `face="john"` /
   `face="james"` they turn to each other and the elbows point away.
8. **Speeds (A3).** Over the 1.6× cap: S08 `jesus walk` (−0.43, −0.50) → (−0.43, −0.30), 0.20 in 1.2 s = 1.72×.
   Close: S07 STAND → ROUND 1.54×, S05 J_T2 → J_T1 1.32×. SET.md: the STAND → ROUND line crosses the low table;
   add the waypoint (−0.15, −0.36).
9. **`chase_coins` ends early.** SELLER2_SIDE → COINS is 0.124 at 0.073 u/s = 1.7 s; then the director hands
   seller2 to `idle` while `ls_11` ("Stop rolling!") is still playing. Add a second `chase_coins` move back
   toward SELLER2_SIDE (or a third mark), so he scuttles through the whole line.
10. **Seated `amazed`.** All four play `amazed` on the bench in S07: it starts from the `sit_bench` pose and never
    stands up (A4). `ashamed` (S09) is seated too.
11. **`stand_talk` (S09)** rises from `kneel_laugh`'s last pose through a half-kneel; the right foot steps where the
    basin was, so keep the basin hidden from S09 (story.py does).
12. **`serve_rise` → `kneel_serve`** chain is seamless (serve_rise ends on kneel_serve frame 0). `serve_rise` starts
    from `sit_supper`; with `face="andrew"` the director turns him in place while he is still cross-legged.
13. A8: no actor gets two clips at the same instant in the current timeline.

## 5. Weak / not verified

- Nothing was played in Unity or on the phone; clip-to-clip blends (0.25 s) were not checked. Comedy beats were
  judged in probe renders at phone size: the bray (head up, mouth wide), `refuse` (leans back, palms up) then
  `offer_all` (head ducked toward Jesus) read; Peter washing Andrew does not read at the current marks (staging 6).
- Riding: Jesus's long robe and mantle hang over the donkey's withers and through the top of the blanket (RIG.md:
  the robe is skinned for standing). From the phone it reads as riding; side-on the robe covers the donkey's
  shoulders. The rider sinks ~5 mm into the blanket at the walk's seat, up to ~19 mm against `idle` at the worst
  phase (ride follows the walk seat).
- The rider/donkey travel mismatch (staging 1) and the heading turns (staging 2) are lead / director work; until
  then S01-S03 will show the rider sliding along the donkey.
- `jesus_rise_towel`: the pour has no jug in His hands (staging 5). The basin is carried at the waist; it was not
  checked against the stand mesh at the 1.6 s pick-up beyond the probe render.
- Kneel pairs: hands touch the seated person's feet / shins (min distance < 1 mm by design); the basin rim and the
  seated feet overlap a little (feet "in the basin"); the bench front was taken from SET.md, not measured.
- `nudge`'s elbow jab is small at phone size; the side lean and giggle carry it.
- Peter's palm frond is aimed upright by turning the wrist; in `walk` the wrist turn is visible close up.
- The disciples' and sellers' shared clips were checked on John and seller1 (contact sheet), Andrew / James only on
  `sit_wash` / `nudge` and through the numbers.
- Long-robe floor contact: Jesus's cross-legged clips keep the mantle end up by a chain floor (0.034); his robe hem
  in the kneel clips reaches −0.0009.
