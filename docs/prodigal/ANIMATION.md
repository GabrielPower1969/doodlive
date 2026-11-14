# The prodigal son — skeletal animation (Animation role)

Owner: Animation. Binding contract: [CONTRACT.md](CONTRACT.md) §3 (bones) and §4 (clip names). Rig: [RIG.md](RIG.md).
Pipeline: `pipeline/pr_animate.py`, a copy of Exodus's `pipeline/ex_animate.py` (same clip-function method, IK, spring
chains, export, verify, contact sheet). Built 2026-11-14 with Blender 5.2.3 from the Characters files written 20:30.

```
python3 pipeline/pr_animate.py all        # build + verify + contact sheet (~75 s)
python3 pipeline/pr_animate.py build      # 47 actions -> anim/{son,father,brother}.glb + anim/clips.json with checks
python3 pipeline/pr_animate.py verify     # re-import the GLBs: animations, sampled joints, UV layer order, prop nodes
python3 pipeline/pr_animate.py contact    # anim/contact_sheet.png
PR_PROBE="father_run:0,6,12:lside;pair:father_hug:son_hug:0.102:20:front,q3,top" python3 pipeline/pr_animate.py probe
PR_ONLY=son_idle,father_run python3 pipeline/pr_animate.py build                      # bake + check a subset, no export
PR_CHARS=brother python3 pipeline/pr_animate.py build                                 # export one character only
```

Probe views: front q3 side back q3l lside top low (+`#bone` close-up), one view per item; `PR_PROBE_RES`,
`PR_PROBE_DIST`, `PR_SET=1` (render on the homeland set; default is a plain floor). Inputs read at run time:
`model/characters.blend`, `timeline.json`, `model/regions_characters.json` (demo colours, `clipExpression` for the face
per clip; Integration's `faces.json` wins once it exists). Work files: `$PR_ANIM_WORK` (default `/tmp/pr_anim_work`).
**Rebuild after any change to characters.blend** (the anim GLBs carry its mesh, UVs and skin).

## 1. Deliverables

| File | What |
|---|---|
| `assets/prodigal/anim/son.glb` | son + skin (31 bones) + `son_purse` / `son_robe` / `son_robeL` / `son_robeR` / `son_ring` / `son_eyelids`, 23 animations |
| `assets/prodigal/anim/father.glb` | father + skin (32 bones) + `father_purse` / `father_eyelids`, 14 animations |
| `assets/prodigal/anim/brother.glb` | brother + skin (29 bones) + `brother_hoe` / `brother_eyelids`, 10 animations |
| `assets/prodigal/anim/clips.json` | Exodus schema per clip: action, frames, seconds, loop, rootMotion (false), markers {name: {frame, sec}}, loopSeamMaxErr, props, notes, naturalSpeed (+ stride), samples, checks; new `propWindows` (per clip) and top-level `stage` / `propWindows`; `timelineMissing` is **empty** |
| `assets/prodigal/anim/contact_sheet.png` | key poses of every clip (demo colours, face decal per clip, props shown only where the timeline shows them) + five pair rows at story distances |

Character-local, root at the origin, facing +Z, 30 fps, every bone keyed (rotation, location, scale; the blink is a
scale of `eyelids`), UV0 = page (in 0..1, checked), UV1 = decal. Verify: all 47 sampled joint sets match the build
within 1e-5 (worst 8e-6); no contract clip missing; prop nodes present (RIG.md §1).

## 2. Clips

meshMinY = lowest deformed vertex with the clip's props (0 = page; limit −0.008). Drift = largest slide of a planted
toe in a non-locomotion clip (deliberate steps show up here); bold = natural speed. Seam / end = loopSeamVelErr (frame N
equals frame 0 exactly in every loop, `loopSeamMaxErr` 0.0) or, for one-shots, endVelMax (≈ 0 = a still end pose that
blends in 0.25 s). Props = shown in renders and checks (the timeline's prop events decide in the app).

| Action | Frames | s | Loop | Markers (name frame/s) | meshMinY | drift / speed | seam / end vel | Props |
|---|---:|---:|:---:|---|---:|---:|---:|---|
| `son_idle` | 150 | 5.0 | yes | — | -0.0003 | 0.006 | 0.00019 | — |
| `son_walk` | 32 | 1.0667 | yes | contactL 0/0.0, contactR 16/0.5333 | -0.0036 | **0.1 u/s** | 0.00554 | — |
| `son_talk` | 96 | 3.2 | yes | — | 0.001 | 0.0001 | 0.00224 | — |
| `son_laze` | 150 | 5.0 | yes | — | 0.0016 | 0.0015 | 0.00054 | — |
| `son_ask_money` | 96 | 3.2 | no | palm 40/1.3333 | -0.0009 | 0.0239 | 0.00013 | purse (purse f96-96) |
| `son_wave_bye` | 72 | 2.4 | no | wave1 22/0.7333, wave2 34/1.1333, wave3 46/1.5333 | -0.0017 | 0.016 | 0.00034 | purse |
| `son_strut` | 30 | 1.0 | yes | contactL 0/0.0, contactR 15/0.5 | -0.0034 | **0.1276 u/s** | 0.00802 | purse |
| `son_toss_coins` | 66 | 2.2 | no | toss 18/0.6 | -0.0 | 0.0082 | 0.00033 | purse |
| `son_party_dance` | 54 | 1.8 | yes | beat1 0/0.0, beat2 13.5/0.45, beat3 27/0.9, beat4 40.5/1.35 | -0.002 | 0.0261 | 0.00976 | purse |
| `son_empty_pockets` | 150 | 5.0 | no | shake 16/0.5333, upside 48/1.6, drop 78/2.6, pockets 96/3.2, shrug 124/4.1333 | -0.0005 | 0.006 | 6e-05 | purse (purse f0-77) |
| `son_sad_idle` | 150 | 5.0 | yes | — | -0.0005 | 0.0073 | 0.00074 | — |
| `son_sad_walk` | 40 | 1.3333 | yes | contactL 0/0.0, contactR 20/0.6667 | -0.0033 | **0.0605 u/s** | 0.00343 | — |
| `son_feed_pigs` | 90 | 3.0 | yes | scatter1 30/1.0, scatter2 75/2.5 | -0.0005 | 0.0 | 0.00116 | — |
| `son_hungry_look` | 120 | 4.0 | yes | lick 40/1.3333, rumble 84/2.8 | -0.0014 | 0.0 | 0.00145 | — |
| `son_sit_sad` | 150 | 5.0 | yes | — | 0.001 | 0.0 | 0.00174 | — |
| `son_idea_stand` | 66 | 2.2 | no | idea 14/0.4667, up 34/1.1333 | -0.0016 | 0.0155 | 0.00057 | — |
| `son_practise` | 120 | 4.0 | yes | heart 14/0.4667, bow 44/1.4667, no 76/2.5333, again 100/3.3333 | -0.0024 | **0.0197 u/s** | 0.00275 | — |
| `son_walk_tired` | 44 | 1.4667 | yes | contactL 0/0.0, contactR 22/0.7333 | -0.0029 | **0.049 u/s** | 0.00303 | — |
| `son_hug` | 90 | 3.0 | yes | — | 0.0005 | 0.0001 | 0.00049 | — |
| `son_sorry_head` | 60 | 2.0 | no | bow 30/1.0 | 0.0014 | 0.006 | 0.00017 | — |
| `son_amazed` | 96 | 3.2 | no | robe 10/0.3333, ring 42/1.4, spread 72/2.4 | 0.0015 | 0.0 | 0.00013 | robe, robeL, robeR, ring |
| `son_dance` | 66 | 2.2 | yes | beat1 0/0.0, beat2 16.5/0.55, beat3 33/1.1, beat4 49.5/1.65 | -0.0019 | 0.0268 | 0.00278 | robe, robeL, robeR, ring |
| `son_wave` | 48 | 1.6 | yes | — | -0.0004 | 0.0001 | 0.00196 | robe, robeL, robeR, ring |
| `father_idle` | 150 | 5.0 | yes | — | 0.0001 | 0.0013 | 0.00028 | — |
| `father_walk` | 40 | 1.3333 | yes | contactL 0/0.0, contactR 20/0.6667 | -0.0026 | **0.075 u/s** | 0.00379 | — |
| `father_talk` | 96 | 3.2 | yes | — | 0.0016 | 0.0 | 0.0035 | — |
| `father_sad_give` | 120 | 4.0 | no | out 30/1.0, give 66/2.2, heart 96/3.2 | 0.0016 | 0.008 | 0.0002 | purse (purse f0-65) |
| `father_wave_sad` | 120 | 4.0 | yes | — | 0.0016 | 0.0 | 0.00046 | — |
| `father_look_far` | 120 | 4.0 | yes | — | 0.0016 | 0.0018 | 0.00055 | — |
| `father_see_son` | 75 | 2.5 | no | gasp 6/0.2, open 52/1.7333 | -0.0006 | 0.012 | 0.00019 | — |
| `father_run` | 24 | 0.8 | yes | contactL 0/0.0, contactR 12/0.4 | -0.0009 | **0.1562 u/s** | 0.00938 | — |
| `father_hug` | 90 | 3.0 | yes | — | 0.0007 | 0.0001 | 0.00107 | — |
| `father_call_servants` | 90 | 3.0 | no | clap1 14/0.4667, clap2 24/0.8, point 42/1.4 | 0.0016 | 0.006 | 0.00067 | — |
| `father_feast_cheer` | 60 | 2.0 | no | up 16/0.5333 | -0.0003 | 0.0016 | 0.00028 | — |
| `father_dance` | 66 | 2.2 | yes | clap1 16.5/0.55, clap2 49.5/1.65 | -0.0009 | 0.0261 | 0.00635 | — |
| `father_plead` | 96 | 3.2 | yes | — | 0.0016 | 0.0 | 0.00102 | — |
| `father_arm_out` | 45 | 1.5 | no | out 26/0.8667 | 0.0016 | 0.008 | 0.00025 | — |
| `brother_idle` | 150 | 5.0 | yes | — | -0.0008 | 0.0017 | 0.00062 | hoe |
| `brother_walk_hoe` | 36 | 1.2 | yes | contactL 0/0.0, contactR 18/0.6 | -0.006 | **0.1 u/s** | 0.00511 | hoe |
| `brother_talk` | 96 | 3.2 | yes | — | 0.0017 | 0.0 | 0.00216 | hoe |
| `brother_work_field` | 60 | 2.0 | yes | strike 0/0.0, lift 40/1.3333 | -0.0051 | 0.0 | 0.00599 | hoe |
| `brother_shake_head` | 60 | 2.0 | no | shake 24/0.8 | -0.0059 | 0.006 | 0.00024 | hoe |
| `brother_listen_music` | 60 | 2.0 | no | ear 26/0.8667 | -0.0016 | 0.0001 | 0.00022 | hoe |
| `brother_stomp_cross` | 66 | 2.2 | no | stamp1 14/0.4667, stamp2 28/0.9333, cross 46/1.5333 | -0.0009 | 0.0009 | 0.0002 | hoe |
| `brother_complain` | 120 | 4.0 | yes | point 14/0.4667, me 52/1.7333, up 90/3.0 | 0.0015 | 0.0075 | 0.00464 | hoe |
| `brother_soften` | 75 | 2.5 | no | drop 24/0.8 | 0.0016 | 0.004 | 0.00036 | hoe |
| `brother_take_hand` | 66 | 2.2 | no | reach 30/1.0, take 52/1.7333 | 0.0014 | 0.008 | 0.00029 | hoe |

Extra checks: locomotion stance slip in a frame moving at the natural speed ≤ 0.0074 (son walk), 0.0058 (strut),
0.0057 (sad_walk), 0.0059 (practise), 0.005 (walk_tired), 0.0034 (father run), 0.0072 (father walk), 0.0065
(walk_hoe). Hoe blade edge (`hoeTip`) y: 0.002-0.006 when planted (idle, talk, shake_head, listen_music end), **0.0046
at the work_field strike** (the blade's corners touch the page: hoe meshMinY −0.005), 0.36 on the shoulder (walk_hoe),
0.015 hanging loose (soften, take_hand). Seated `sit_sad` meshMinY +0.001 (hip joint 0.034 up). Drifts of 0.016-0.027
are deliberate steps (ask_money's stroll, wave_bye's turn, the dances' side-steps); `idea_stand`'s feet come back under
him while in the air (toes > 0.012, not counted).

### Acting notes

- **Son** (cheeky → broke → sorry → overjoyed). `idle`: thumbs in his sash, hip drops, up on the toes, glances (arms low:
  fine with the robe). `walk`: easy, springy, 112 steps/min. `laze`: leans way back on nothing, hands behind his head,
  elbows out, right foot crossed tapping, a huge yawn with a stretch (eyes shut, mouth wide). `ask_money`: half-step
  stroll, right fist on hip, left palm up held out toward his father with a "come on" finger wiggle, chin up — the held
  end pose is where the purse appears (22.18 s). `wave_bye`: half turns to the road, three big waves back over his
  shoulder, purse in the left hand. `strut`: chest out, chin up, rolling hips and shoulders, floppy right wrist, the
  purse swings on its spring. `toss_coins`: purse up, right hand dips in, winds down, flings high at **toss 0.6 s**
  (the `coins_spray` FX on `son.handR` starts there), laughs, ends showing off (purse held up at his left, fist on hip).
  `party_dance`: knees bounce on every beat of `party` (13.5 frames), arms wave overhead in turn. `empty_pockets`: peers
  in, shakes by the ear, upside down over a cupped palm (the bag follows the hand there, not gravity), lets go at
  **drop 2.6 s**, pulls out his pockets, slumped palms-up shrug (holds). `sad_idle`: deep slump, sighs, a scuff.
  `sad_walk`: trudge, head down. `feed_pigs`: mimed sack at the left hip, flings pods to his left-front (the pigs' side
  at PIGPEN). `hungry_look`: bent toward the trough, rubs his tummy in circles, licks / chews, swallow, wipes his mouth,
  a rumble jolt. `sit_sad`: on the ground, knees up, face in hands, sobs, lifts his head once. `idea_stand`: frame 0 =
  sit_sad; head pops up, "finger" up by his face, crouches over his feet and springs up with a hop, ends standing with
  fists at his chest. `practise`: very slow pensive steps while rehearsing: hand on heart, deep bow, cringing head-shake
  with a hand wave, palms open "try again"; jaw moves. `walk_tired`: bent, heavy, low feet. `hug`: arms round the
  father's back under his arms, cheek on his chest, eyes shut, sobbing shoulders, rocking. `sorry_head`: lets go, hands
  clasped low, head bowed (holds; the father keeps hugging). `amazed` (robe + ring): looks down at the robe, ring hand up
  in front of his face, then both palms up toward his father (holds). `dance` (robe): bouncing side-steps at `feast`
  tempo (16.5 frames), hip turns so the robe panels swing, claps on 2 and 4 at chest height. `wave` (robe): hand up by
  his head, elbow forward so the upper arm stays under 60°.
- **Father** (warm, old, never frail; the baked stoop stays). `idle`: hands folded on his belly, slow breaths, a kind
  nod, strokes his beard. `walk`: hands behind his back, unhurried, panels swing. `talk`: palm-up offers, hand to heart.
  `sad_give`: right hand under the robe at the chest (purse shown from 0), draws it out, looks at it, hesitates, holds
  it out at chest height, opens the hand at **give 2.2 s**, then hand on heart, head bowed (holds). `wave_sad`: slow
  shoulder-height wave, the hand sinks, a sigh, again. `look_far`: hand shading his eyes, leaning, up on his toes, slow
  scan, the other hand on his back. `see_son`: gasp with both hands at his mouth, trembling, then arms flung wide
  (holds). **`run`**: 150 steps/min, short strides with a little float, pitched forward, a lopsided bob (one step lands
  harder) and lurch, the left fist hitches the robe's left front panel forward at the hip (`cloakL` keyed, gravity off),
  the right arm reaches high toward his son and wobbles, head-cloth and beard fly, the other panel flaps. **`hug`**:
  leans over his son, arms round the son's shoulders and upper back, head down on the son's head, eyes shut, rocking,
  pats on the back, a sob. `call_servants`: claps twice high above his head, flings the right arm out to his right
  (toward the house), then hands together at his chest beaming (a good pose to hold). `feast_cheer`: dip, both arms up
  in a V, laughing (holds). `dance`: claps on 2 and 4 at chin height, side-steps, shoulder shimmy, laughing eyes.
  `plead`: leaning in, both palms up, pumping on the beats, a hand to the heart. `arm_out`: right hand out at chest
  height, palm half up (wrist 0.068 in front), left hand on heart (holds).
- **Brother** (firm, hurt; the hoe is always in his right hand). `idle`: hoe planted at his side, left fist on hip,
  wipes his brow, stretches. `walk_hoe`: hoe on the right shoulder, blade behind, heavy steps. `talk`: chops the air,
  taps his chest. `work_field`: bent over, both hands on the handle (left lower), chop with the blade on the page at
  **strike f0**, drag back, swing up (**lift f40**) and forward. `shake_head`: leans on the hoe in front with both hands,
  three slow shakes, a tut. `listen_music`: swings the hoe down and plants it, hand cupped to the ear, head tilted to the
  house (holds). `stomp_cross`: two stamps (**stamp1 0.47 s, stamp2 0.93 s**: the timpani hits), arms crossed high with
  the hoe upright in the crook, chin up, head turned away (holds). `complain`: jabs a finger, thumps his chest, throws
  both hands up (hoe and all). `soften`: arms uncross and drop, shoulders sink, looks at his feet (holds).
  `take_hand`: a still pause, looks up, reaches his left hand to the father's (wrist 0.050 in front, at chest height,
  **take 1.73 s**), a squeeze (holds).

Faces per clip: `regions_characters.json clipExpression` (the son's hug face is `cry`, eyelids shut by the clip).

## 3. Props (follow the timeline's prop events; the clips pose the hands for them)

- **Purses** are spring-hung (chain on the `purse` bone, 75 % toward plumb) so they swing in strut / dance and hang
  plumb from a palm-up hand. A clip can switch gravity off per frame (`hang.purse`, used for the upside-down shake).
- `son_ask_money`: the purse shows only in the held end pose (it lands in the open left palm at 22.18 s).
  `father_sad_give`: purse f0-65 (released at give 2.2 s = the timeline's swap). `son_empty_pockets`: purse f0-77
  (drop 2.6 s).
- **Robe + ring** (`son/robe` hides / shows all three robe pieces): `amazed`, `dance`, `wave`, and `walk` / `idle`
  after S10. Every son clip keeps the upper arms under ~60° from hanging while the robe can show; the robe panels
  (`robeL/R`) swing with the legs in walk / strut / dance and follow through on springs.
- **Hoe**: never hidden; every brother clip poses it (planted with the blade edge solved onto the page, on the shoulder,
  in the crossed arms, or hanging with the blade 0.015 off the page).

## 4. Natural speeds (in-place locomotion; the director moves the actor)

| Clip | Stride | Duty | Natural | Timeline needs (current `timeline.json`, voices) |
|---|---:|---:|---:|---|
| `son_walk` | 0.064 | 0.60 | **0.100 u/s** | S02 0.06 in 1.4 s; S11 0.47 in 10.2 s; S14 0.45 in 9.6 s (all fine, arrives early) |
| `son_strut` | 0.074 | 0.58 | **0.128 u/s** | S03 legs 0.256 / 2.2 s (1.0×), 0.206 / 2.2 s (1.0×), **0.358 / 1.58 s → 1.77×** |
| `son_sad_walk` | 0.050 | 0.62 | **0.061 u/s** | S06 0.30 in 3.52 s → 1.41× (fine) |
| `son_practise` | 0.026 (gait cycle 60 f) | 0.66 | **0.020 u/s** | S08 0.161 in 12.5 s → arrives after 8.2 s |
| `son_walk_tired` | 0.046 | 0.64 | **0.049 u/s** | S09 0.057 in 10.6 s → arrives after 1.2 s |
| `father_run` | 0.060 | 0.48 | **0.156 u/s** | S09 0.20 in 2.4 s → arrives after 1.3 s |
| `father_walk` | 0.060 | 0.60 | **0.075 u/s** | S11 0.272 / 4.0 s (1.0×); S13 0.206 / 2.6 s (1.06×) |
| `brother_walk_hoe` | 0.072 | 0.60 | **0.100 u/s** | S12 0.442 / 4.0 s → 1.10× |

## 5. Notes for Story / Integration (`build_timeline.py prodigal` printed no WARNING; these are what the numbers show)

1. **S13 `take_hand` never reaches the hand.** `brother idle` (S14, t 199.78) starts 1.4 s into take_hand (198.38): the
   reach lands at 1.73 s, so the open ending (the hands meeting) is cut. The same act also drops the father's
   `arm_out`. Give S14's father / brother `idle` ≥ 2.5 s after take_hand, or drop those two acts (one-shots hold).
2. **S10 `amazed` is cut after 0.9 s** by the son's S11 `walk` (139.74 → 140.64): the ring look (1.4 s) and the spread
   hands (2.4 s) never play. Start the walk ≥ 2.6 s after amazed.
3. **S03 last strut leg** to TAVERN needs 1.77× (> 1.6 cap): he stops ~0.03 short when toss_coins starts (inside the
   tool's 0.3 s grace, so no WARNING). Move toss_coins ~0.2 s later or the leg's start earlier.
4. **Glides**: `father wave_sad to=FA_LOOK` (33.61) slides him 0.228 from the door to the lookout without stepping —
   add a `walk` first (0.075 u/s → 3 s) or keep him at the door; `son sit_sad to=PIG_SIT` (85.66) slides him 0.072
   while sitting — walk (sad_walk) to PIG_SIT first.
5. **The run arrives 1.1 s before the hug** and plays `idle` in between (the director hands a finished move to idle):
   the emotional peak goes run → stand → hug. Start the hug ~1.3 s after the run (both `hug` acts), or start the run
   ~1 s later.
6. **Long holds**: `toss_coins` holds its end pose 12.7 s (S04) and `party_dance` plays only 1.2 s before
   `empty_pockets` — consider starting party_dance right after the toss (dt ≈ 2.2). `son ask_money` holds 13 s and
   `father sad_give` 9.6 s (designed holds). `son walk_tired` arrives after 1.2 s and stands in `idle` (cheeky face)
   9.4 s while the father looks / sees / runs — start it from further back or use a longer leg. `practise` arrives
   after 8.2 s, then 4.3 s of idle.
7. **Distances**: `arm_out` + `take_hand` are designed for 0.12 apart (contract); FA_OUT / BRO_OUT are 0.102 apart, so
   the hands overlap by ~0.02 (reads as a clasp). The S11 dance has father and son 0.102 apart facing each other: the
   claps are kept close to the body but the heads come within ~0.03; `face="viewer"` for both (or 0.15 apart) would
   read better.
8. `call_servants` points to the father's right (stage left, toward the house where the servants are), not "off right"
   of the screen; say if the servants should come from screen right.
9. Lip sync overrides `jaw` in talk clips (`talk`, `plead`, `complain`, practise's mumbling); small keyed jaw elsewhere.

## 6. Staging the clips assume (`clips.json stage`)

- `sit_sad` / `idea_stand` f0: sitting on the page, hip joint (0, 0.034, −0.016) root-local, feet 0.092 in front.
- Hug: father and son 0.10 apart facing each other; both rocks are the same 3 s sine and sway to the same side of the
  stage (no crossing). `son_sorry_head` works inside the father's `hug`.
- `arm_out` wrist (−0.026, 0.212, 0.068); `take_hand` wrist (0.024, 0.220, 0.050): they meet at 0.10-0.12 apart.
- Pair rows in the contact sheet: hug + hug (0.102), hug + sorry_head, sad_give + ask_money (0.089), arm_out +
  take_hand (0.12), dance + dance (0.102).

## 7. How the motion is made

As Exodus §7 (clip functions → channels in design axes, Catmull-Rom keys, leg / arm IK, spring chains with seamless
loops, irregular blinks, syllable jaws, eased one-shots with anticipation / overshoot / settle). New here:

- **Layered arm IK**: every `arm_ik` call is a layer; later layers blend over earlier ones in world space by their
  weight (the first against FK), so a hand can go face → finger-up → fist, or hip → toss → hip, in different spaces.
- **Hoe solver** = Moses's staff solver on `hoeTip` (blade edge on the page, handle direction given), `aim.hoe` when
  held off the ground; the left hand can be IK'd in hoe space.
- **Spring chains**: father beard1-2 (k 85, c 8, 25 % hang, ≤ 22°), cloakL / cloakR (70 / 6.5 / 22 % / 18°), headcloth
  (80 / 7 / 25 % / 20°), purses (55 / 3.6 / 75 % / 75°), son robeL / robeR (80 / 7 / 25 % / 22°), brother headcloth
  (85 / 7.5 / 25 % / 22°); per-frame gravity scale `hang.<bone>` (run's hitched panel, the upside-down purse).
- Foot contact uses the sole under the ball / toe (not the toe bone), so toe-off no longer sinks the sandal.

## 8. Rough edges (honest list)

- **Weakest clips**: `practise` (gestures are clear in close-up, small at phone distance; the steps are very short by
  design for the 12 s leg); `hungry_look` (no tongue: the lick is a chewing jaw + head bob); `feed_pigs` (no sack prop:
  a cupped left hand at the hip); `son_talk` / `brother_talk` (generic). `work_field`'s hoe stays to his right-front,
  not dead centre (the rigid fist on the handle's upper third limits how far the blade swings up).
- **Hug**: reads as an embrace with heads together from the front and 3/4; from directly above the father's right
  hand pokes out past the son's back at the widest rock. The son's hug clip is on screen only 1 s before sorry_head.
- **Run**: the left panel is a single rigid bone, so "hitched up" is the panel swung forward from the chest with the
  fist on it; the cream under-tunic still reaches the ankles (legs barely show).
- Robe: rigid on the chest; legs can touch the back hem inside at the dance's knee lifts (not visible from the front).
- Hands are single-bone fingers: the "finger up" in idea_stand and the pointing hands are straight hands.
- Not seen in Unity / on the phone (glTFast skinning, bone-scale blink, prop show / hide of the three robe pieces).
