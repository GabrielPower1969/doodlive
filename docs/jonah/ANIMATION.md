# Jonah — animation (Animation role)

Script: `pipeline/jn_animate.py` (`python3 pipeline/jn_animate.py all` = build + verify + contact sheet + freshness
check). Outputs in `assets/jonah/anim/`: `jonah.glb` `captain.glb` `fish.glb` (character + skin + one glTF animation
per action `<char>_<clip>`), `clips.json` (per clip: frames, loop, seated, rootMotion, markers, naturalSpeed, checks,
sampled joints; top level `stage` and `travel`), `contact_sheet.png` (key poses on the coast set + two pair rows).

All 39 contract clips exist with the contract names (jonah 24, captain 9, fish 6) plus one extra, `jonah_lie_down`.
`verify`: every action re-imported from the GLBs, sampled joints match the build (error <= 8e-6), UV0 inside 0..1,
nothing from CONTRACT §4 missing. The exports are newer than `characters.blend` and the model GLBs (read fresh each
run; the Characters role re-exported at 01:07 during this work).

## How it is built

Same method as Ruth / Daniel (story_kit + pack code): every clip is a function frame -> channels, legs and arms by
two-bone IK, secondary motion by damped spring chains (coat panels, belt end, seaweed, head-wrap tail, sash end, the
fish's dorsal fin). New in this pack:

- **Fish rig**: no IK; the swim is a travelling body wave (yaw per segment body1 -> body2 -> body3 -> tail, each
  0.13 of a cycle later, amplitude 4 / 7 / 11 / 20 deg), the root counter-turns so the head holds the travel line.
  `jaw.rx` +55 = open (measured: 52 deg opening against the closed rest). Cheek puffs scale `body1` (x / z only,
  children compensated); the gulp's swallow lump runs down body2 -> body3.
- **settle**: seated, lying and kneeling poses put the lowest point of a skinned body proxy on the page every frame;
  a **foot settle** lifts an IK foot whose skinned toe / calf dips (the model's toes dip ~1 cm when the knees bend);
  **floor clamp** on the transition clips; chain bone tails never go under the page.
- **coat follow**: seated / lying / kneeling, the coat panels and belt end lie along the thighs, levelled and drooping
  (a single-bone panel along a raised thigh stuck out like a blade).
- **two-target arm IK**: a hand can travel between targets held in different bones' spaces (nose -> chest, cheek ->
  deck) without a pop; `mix()` uses it automatically.
- **partner-aware clips**: `captain_heave` reads Jonah's `fall_in` pose at the matching frame (lag 21) for its hand
  targets; `captain_shake_awake` reads Jonah's shoulder from `sleep_curl`.

## Clips

| Action | Frames / s | Type | Speed u/s | Markers (frame, s) | meshMinY | feet (drift / slip) | seam / max step |
|---|---|---|---|---|---|---|---|
| `jonah_idle` | 150 / 5.0 | loop | - | - | 0.0005 | drift 0.0019 | 0.0005 / 0.0063 |
| `jonah_walk` | 34 / 1.133 | loop | 0.1059 | `contactL` 0 (0.00), `contactR` 17 (0.57) | -0.0004 | slip 0.0052 | 0.0101 / 0.0112 |
| `jonah_talk` | 96 / 3.2 | loop | - | - | 0.0009 | drift 0.0001 | 0.0082 / 0.0228 |
| `jonah_tiptoe` | 40 / 1.333 | loop | 0.0779 | `contactL` 0 (0.00), `contactR` 20 (0.67) | 0.0004 | slip 0.0000 | 0.0035 / 0.0072 |
| `jonah_stomp_walk` | 30 / 1.0 | loop | 0.1143 | `stompL` 0 (0.00), `stompR` 15 (0.50) | -0.0011 | slip 0.0029 | 0.0120 / 0.0315 |
| `jonah_listen_up` | 54 / 1.8 | one-shot | - | `look` 20 (0.67) | 0.0016 | drift 0.0000 | - / 0.0174 |
| `jonah_refuse` | 66 / 2.2 | one-shot | - | `no` 10 (0.33), `snort` 36 (1.20) | -0.0004 | drift 0.0029 | - / 0.0356 |
| `jonah_sleep_curl` | 120 / 4.0 | loop seated | - | - | 0.0012 | drift 0.0000 | 0.0004 / 0.0108 |
| `jonah_lie_down` | 40 / 1.333 | one-shot seated EXTRA | - | `down` 30 (1.00) | -0.002 | drift 0.0782 | - / 0.0376 |
| `jonah_wake_startled` | 72 / 2.4 | one-shot | - | `jolt` 9 (0.30), `standing` 52 (1.73) | -0.0012 | drift 0.0999 | - / 0.0905 |
| `jonah_ashamed` | 120 / 4.0 | loop | - | - | -0.0 | drift 0.0056 | 0.0015 / 0.0062 |
| `jonah_fall_in` | 48 / 1.6 | one-shot root motion | - | `release` 23 (0.77), `splash` 42 (1.40) | -0.0934 | drift 0.0221 | - / 0.0595 |
| `jonah_sit_hold_nose` | 96 / 3.2 | loop seated | - | - | 0.0008 | drift 0.0000 | 0.0004 / 0.0064 |
| `jonah_kneel_pray` | 84 / 2.8 | one-shot seated | - | `knees_down` 30 (1.00), `bow` 52 (1.73) | -0.001 | drift 0.0000 | - / 0.0441 |
| `jonah_tumble_out` | 60 / 2.0 | one-shot seated root motion | - | `touch` 9 (0.30), `land` 40 (1.33) | -0.002 | drift 0.0542 | - / 0.0631 |
| `jonah_sit_dazed` | 90 / 3.0 | loop seated | - | - | -0.0015 | drift 0.0000 | 0.0020 / 0.0684 |
| `jonah_stand_up` | 60 / 2.0 | one-shot | - | `up` 40 (1.33) | -0.0021 | drift 0.0400 | - / 0.0199 |
| `jonah_nod_ok` | 50 / 1.667 | one-shot | - | `nod` 30 (1.00) | 0.0016 | drift 0.0000 | - / 0.0090 |
| `jonah_proclaim` | 96 / 3.2 | loop | - | `call1` 10 (0.33), `call2` 58 (1.93) | 0.0017 | drift 0.0000 | 0.0016 / 0.0087 |
| `jonah_surprised` | 48 / 1.6 | one-shot | - | `take` 16 (0.53) | 0.0016 | drift 0.0001 | - / 0.0703 |
| `jonah_sit_sulk` | 72 / 2.4 | one-shot seated | - | `plonk` 16 (0.53) | 0.0004 | drift 0.0570 | - / 0.0425 |
| `jonah_relax_happy` | 120 / 4.0 | loop seated | - | - | 0.0005 | drift 0.0000 | 0.0013 / 0.0013 |
| `jonah_wail` | 72 / 2.4 | loop seated | - | - | -0.0006 | drift 0.0000 | 0.0078 / 0.0131 |
| `jonah_look_city` | 120 / 4.0 | one-shot | - | `stand` 70 (2.33) | -0.0021 | drift 0.0405 | - / 0.0228 |
| `jonah_wave` | 48 / 1.6 | loop | - | - | -0.0007 | drift 0.0016 | 0.0029 / 0.0039 |
| `captain_idle` | 180 / 6.0 | loop | - | - | -0.0011 | drift 0.0002 | 0.0004 / 0.0018 |
| `captain_talk` | 96 / 3.2 | loop | - | - | 0.0006 | drift 0.0002 | 0.0026 / 0.0124 |
| `captain_walk` | 36 / 1.2 | loop | 0.1111 | `contactL` 0 (0.00), `contactR` 18 (0.60) | -0.003 | slip 0.0043 | 0.0122 / 0.0145 |
| `captain_greet` | 66 / 2.2 | one-shot | - | `sweep` 22 (0.73), `point` 40 (1.33) | 0.0006 | drift 0.0034 | - / 0.0345 |
| `captain_steer_hard` | 72 / 2.4 | loop | - | `heaveL` 14 (0.47), `heaveR` 50 (1.67) | -0.0022 | drift 0.0000 | 0.0025 / 0.0072 |
| `captain_shake_awake` | 48 / 1.6 | loop | - | `shake1` 8 (0.27), `shake2` 32 (1.07) | -0.001 | drift 0.0000 | 0.0043 / 0.0101 |
| `captain_refuse_hands` | 54 / 1.8 | one-shot | - | `no` 14 (0.47) | -0.0008 | drift 0.0044 | - / 0.0390 |
| `captain_heave` | 72 / 2.4 | one-shot | - | `grab` 21 (0.70), `release` 44 (1.47) | -0.0032 | drift 0.0034 | - / 0.0489 |
| `captain_amazed` | 60 / 2.0 | one-shot | - | `hands_up` 20 (0.67) | 0.0018 | drift 0.0002 | - / 0.0478 |
| `fish_idle` | 120 / 4.0 | loop | - | - | 0.0015 | - | 0.0015 / 0.0022 |
| `fish_swim` | 48 / 1.6 | loop | 0.12 | - | 0.0024 | - | 0.0039 / 0.0107 |
| `fish_gulp` | 96 / 3.2 | one-shot root motion | - | `open` 30 (1.00), `gulp` 38 (1.27) | 0.0032 | - | - / 0.0476 |
| `fish_burp` | 54 / 1.8 | one-shot | - | `burp` 22 (0.73) | -0.0002 | - | - / 0.0123 |
| `fish_spit` | 60 / 2.0 | one-shot root motion | - | `spit` 24 (0.80) | 0.0061 | - | - / 0.0530 |
| `fish_wave_fin` | 60 / 2.0 | loop | - | - | 0.0031 | - | 0.0050 / 0.0053 |

Checks: seated / kneel clips meshMinY >= -0.008 (all pass; the lowest is -0.0021). Walk slip <= 0.02 u/s (max 0.0052).
Loops: seam step <= the largest step inside the clip (all pass). `jonah_fall_in` -0.093 is root motion: at the splash
the body is 0.007 above the page (deck 0.10 - 0.093), under the sea surface (0.012) — intended.
Planted-foot drift > 0.002 is deliberate where it appears: a toe scuff (`ashamed` 0.006), heel lift (`refuse`),
a lifted step back (`captain_refuse_hands`), a step forward (`captain_greet`); the getting-up / sitting-down clips
reposition the feet on the ground (`wake_startled`, `tumble_out`, `stand_up`, `sit_sulk`, `look_city`, `lie_down`).
Fast moves (one-frame step > 0.05): `wake_startled` (the jolt), `surprised` (hands fly up), `sit_dazed` (hand to the
ear), `fall_in` (nose pinch), `tumble_out` (roll), `fish_spit` / `fish_gulp` (jaw snap) — intended snaps, looked at.

Faces: the contact sheet uses `regions_characters.json faceDecal.clipExpression` (there is no `assets/jonah/faces.json`
yet; the lead owns it).

## Staging notes for the lead

**Distances the two-person clips assume** (probed as pairs on the deck, renders in the contact sheet):

| Clips | Geometry | In story.py now | Change |
|---|---|---|---|
| `captain_heave` + `jonah_fall_in` | tandem: the captain 0.10 **behind** Jonah, both facing the same way (Jonah faces the viewer at the rail, the captain faces Jonah) | captain at (-0.36, -0.24), Jonah at RAIL (-0.22, -0.16): 0.16 apart, off-axis | walk the captain to **(-0.22, -0.26)** during jn_10 (`captain_walk`, 0.14 at 0.111 u/s = 1.3 s) |
| `captain_shake_awake` + `jonah_sleep_curl` | Jonah lies on his right side facing the viewer, **head toward -X**; the captain stands **0.19** from Jonah's root on the -X side and faces him (hands reach his upper shoulder) | captain walks to (-0.36, -0.24): 0.063 from Jonah at CARGO — he would stand on Jonah | captain mark **(-0.49, -0.26)**; check the clearance there (the steering oar / stern at x -0.51); a deck mark at (-0.30, -0.26) for Jonah needs the clear deck to x -0.53 |

**`fall_in` and `heave` timing**: `fall_in` must start 0.7 s (21 f) after `heave` (story.py already has dt=0.7).
`heave` grab 0.70 s, release 1.47 s; `fall_in` release 0.77 s, splash 1.40 s. Root motion: Jonah's root ends at
(0, -0.14, +0.10) — he lands 0.10 toward the viewer from RAIL, i.e. at about (-0.22, -0.06) in the water.

**Moves that glide** (not locomotion clips; StoryDirector glides at 0.12 u/s, visible):
- t 94.8 `jonah idle` RAIL -> PARK: 1.12 over the sea, 9.3 s glide.
- t 123.0 `captain idle` -> PARK: 1.28, 10.7 s. `jonah sit_hold_nose` PARK -> BELLY: 1.02, 8.5 s (he slides into the
  fish from off the page).
- t 151.7 `jonah idle` BELLY -> PARK: 1.02 in 7.3 s (does not finish before the next beat).
- t 159.0 `jonah tumble_out` PARK -> BEACH: 0.71, 5.9 s. `tumble_out` has its own root motion (starts 0.16 left of
  and 0.05 above its mark): it only works if Jonah is already at BEACH when it starts.
- All of these need a jump (teleport) to the mark, which the engine only does at t = 0. Suggest an `act(..., snap=True)`
  or doing the PARK moves at a camera cut; otherwise hide him first (e.g. after the splash FX).

**Locomotion speeds**: none needs more than 1.6x. Highest: fish FISH_FAR -> FISH_SHORE 0.96x, jonah walk to the
gate 0.91x, the walk RAIL 0.86x, stomp_walk to the hill 0.85x. Natural speeds: jonah walk 0.106, tiptoe 0.078,
stomp_walk 0.114, captain walk 0.111, fish swim 0.12 u/s. Slow moves just arrive early and switch to idle (tiptoe
at 0.27x arrives after 2.1 s of a 7.9 s beat; fine for the story).

**Lead-ins and posture changes**:
- S02 `walk` -> `sleep_curl`: standing -> lying in the 0.25 s blend. Play the extra **`jonah_lie_down`** (1.33 s, ends
  in sleep_curl frame 0) at CARGO, then `sleep_curl`.
- S12 `wail` (seated) -> `listen_up` (standing) pops. `look_city` starts seated (legs out, as wail) with a 1 s
  look-up first, then stands: either replace that `listen_up` by `look_city` at jn_28, or put `stand_up` before
  `listen_up` (then `look_city` would start seated again — avoid).
- S06 `kneel_pray` starts from `sit_hold_nose`'s pose (no lead-in needed). S07 `tumble_out` -> `sit_dazed` ->
  `stand_up` -> `nod_ok` chain without pops. S10 `sit_sulk` starts standing (after `stomp_walk`).
- S03 `wake_startled` starts from `sleep_curl` and ends standing at the root: `walk` can follow.
- One-shot clips that hold their last pose: listen_up, refuse, wake_startled, kneel_pray, tumble_out, surprised,
  sit_sulk, look_city, greet, refuse_hands, amazed, fish gulp. `fall_in`, `heave`, `stand_up`, `nod_ok`, burp, spit
  end in a pose the next clip blends from.

**Fish facing**: the fish model faces +Z; its mouth is ~0.24 ahead of its root and `gulp` lunges 0.08 forward. With
`face="viewer"` at FISH_SEA the gulp goes toward the viewer, away from Jonah's splash at (-0.22, -0.06). For the
spit, Jonah's `tumble_out` starts 0.16 left of BEACH at mouth height: the fish should face +X with its root near
**(-0.28, 0.10)** (mouth at the beach edge), not at FISH_SHORE (-0.04, 0.10) facing the viewer.

**Marker times for sound / FX** (seconds from the clip start): `fall_in` splash 1.40 (story sfx dt 1.5 — fine);
`fish_gulp` gulp 1.27 (story `gulp` sfx dt 0.9 — move to 1.27); `fish_burp` burp 0.73 (sfx dt 0.6 — 0.73);
`fish_spit` spit 0.80 (sfx dt 0.7 — 0.8); `tumble_out` touch 0.30, land 1.33; `captain_heave` release 1.47;
`kneel_pray` knees_down 1.00, bow 1.73; `refuse` snort 1.20; `proclaim` calls 0.33 / 1.93 per 3.2 s loop.

**A8**: no two clips of the same actor start at the same instant in story.py. `captain_idle` is 6.0 s = one
`shipRock` period; the captain's idle right hand rests on the oar handle at CAPT_DECK (-0.074, 0.172, 0.006 local).

**Other**: `y=DECK` is set at the start of the walk up the plank, so Jonah pops 0.10 up at BEACH (engine). The
steering oar is static: in `steer_hard` the hands slide +-0.02 along it.

## Fix 2026-11-15 (docs/jonah/FIXLOG-20261115.md)

- `kneel_pray`: kneeling upright his head top reached 0.279 and came out through the top of `belly` (inner height
  ~0.255 near the centre; phone demo 140-147 s). He now sits back on his heels (`KNEEL_PRAY` = thigh_back 72,
  shin_slope 4 for `kneel_legs`) and bows deeper (chest +12, spine +8, neck +12, head +20 deg): head top 0.249 while
  rising (frames 24-42), 0.238 held. meshMinY -0.001. Measured on the exported GLB (Blender, evaluated mesh).
- The travel notes above (PARK glides) are obsolete: story.py now hides an actor and moves it with `snap=True`.
