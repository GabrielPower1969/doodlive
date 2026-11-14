# The prodigal son — production contract (story pack #6)

The brief every role works from. **Same rules as `docs/exodus/CONTRACT.md`** (units, UV = page position, audio formats,
only Integration runs Unity, nobody commits, nobody touches another role's files, shared files additive only) unless
this file says otherwise. Story and lines: `docs/prodigal/STORY.md` + `docs/prodigal/storyboard/story.py`; look:
`docs/prodigal/DESIGN.md`.

**Exodus (pack #5, made today) is the template**: `pipeline/ex_*.py`, `tools/story/{music,voice,sheet}_exodus.py`,
`StoryFxExodus*.cs`, `docs/exodus/*.md` are the newest working, device-tested examples (Ruth is the older one). Copy and
adapt with the prefix `pr_` / `_prodigal`. Read `docs/LESSONS.md` first (L44 onward, especially L51 back faces and L52
adb). Other sessions may be working in this repo; never run Unity, adb, or a build.

Quality bar: at least Exodus. The heart of this story is **the father seeing his son far off and running to hug him**.

## 1. Roles and file ownership

| Role | Owns |
|---|---|
| Story (lead) | `docs/prodigal/STORY.md`, `storyboard/story.py`, `STORYBOARD.md`, `assets/prodigal/timeline.json` |
| Characters | `pipeline/pr_characters.py`, `assets/prodigal/model/{son,father,brother}.glb`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/prodigal/RIG.md`, `docs/prodigal/design/faces/` |
| Set + sheet | `pipeline/pr_homeland.py`, `assets/prodigal/model/homeland.{glb,blend}`, `homeland_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_prodigal.py`, `assets/prodigal/sheet/`, `print/prodigal-A4.*`, `assets/prodigal/design.json`, `docs/prodigal/SET.md` |
| Animation | `pipeline/pr_animate.py`, `assets/prodigal/anim/`, `docs/prodigal/ANIMATION.md` |
| Effects | `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxProdigal*.cs` (+ one registration line in `DGFxEffects.cs`), `Fx/Preview~` additions, `docs/prodigal/FX.md` |
| Music & SFX | `tools/story/music_prodigal.py`, `assets/prodigal/audio/music/`, `assets/prodigal/audio/sfx/`, `docs/prodigal/MUSIC.md` |
| Voice | `tools/story/cast_prodigal.json`, `tools/story/voice_prodigal.py`, `assets/prodigal/audio/voice/`, `docs/prodigal/VOICE.md` |
| Integration (lead) | engine, `Stories/prodigal/`, `assets/stories.json`, `assets/library.json`, `assets/prodigal/{pack,faces}.json`, builds, device, demo |

## 2. Characters

| Id | Height | Notes |
|---|---|---|
| `son` | 0.34 | slim young man; hero |
| `father` | 0.36 (slight stoop) | grey beard, head-cloth, swinging outer robe |
| `brother` | 0.37 | broad farmer |

## 3. Skeleton

Humanoid bones exactly as Exodus / Ruth (`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R
handL/R thighL/R shinL/R footL/R toeL/R fingersL fingersR eyelids`), A-pose, facing +Z. Extras:
- `son`: `purse` (child of `handL`, hidden), `robe` (child of `chest`, the rigid over-robe shell, hidden) with
  `robeL robeR` (children of `robe`, the lower front edges, for follow-through), `ring` (child of `handR`, hidden).
- `father`: `beard1 beard2` (from `jaw`), `cloakL cloakR` (from `chest`, outer robe front panels), `headcloth` (from
  `head`, back drape), `purse` (child of `handR`, hidden).
- `brother`: `headcloth` (from `head`), `hoe` (child of `handR`; tip leaf `hoeTip`).

Props are rigid meshes named `<char>_<bone>` under their bone (Ruth's `ruth_sheaf` precedent). Faces: decals per
expression in `docs/prodigal/design/faces/<char>_<expr>.png` (DESIGN.md lists them) plus `eyelids` blink.

## 4. Animation clips (names are the contract; • = used by the timeline)

| son | father | brother |
|---|---|---|
| • `idle` (loop) | • `idle` (loop) | • `idle` (loop) |
| • `walk` (loop) | • `walk` (loop, dignified) | • `walk_hoe` (loop, hoe on the shoulder) |
| `talk` (loop) | `talk` (loop) | `talk` (loop) |
| • `laze` (loop: leaning back against the wall-less air, arms behind head, foot tapping, yawning) | • `sad_give` (one-shot hold: slow reach into robe, holds the purse out, purse shown from 0, released at marker `give` 2.2 s, then hand on heart) | • `work_field` (loop: hoeing, the hoe blade reaches the ground in front, y ≈ 0) |
| • `ask_money` (one-shot hold: strolls a step, palm up, cheeky grin, other hand on hip) | • `wave_sad` (loop: slow wave, then hand drops, then again) | • `shake_head` (one-shot: leans on hoe, slow head shake) |
| • `wave_bye` (one-shot: big over-the-shoulder wave) | • `look_far` (loop: hand shading eyes, leaning, rising on toes) | • `listen_music` (one-shot hold: stops, hand to ear, head tilted toward the house) |
| • `strut` (loop: swaggering walk, purse swinging; natural speed similar to walk) | • `see_son` (one-shot hold: freezes, hands to mouth, then arms open) | • `stomp_cross` (one-shot: stamps twice, then arms crossed hold, chin up) |
| • `toss_coins` (one-shot: reaches into purse, flings a handful up high with the right hand; marker `toss` 0.6 s) | • `run` (loop: an old man's joyful run, robe hitched up in the left hand, right arm reaching forward; fast) | • `complain` (loop: points, then at himself, then throws hands up) |
| • `party_dance` (loop: silly dance, arms waving) | • `hug` (loop: wraps both arms round someone 0.10 in front, rocking slightly) | • `soften` (one-shot hold: arms uncross, shoulders drop, looks at his feet) |
| • `empty_pockets` (one-shot hold: shakes the purse, turns it upside down, pulls out empty pockets, purse dropped at 2.6 s) | • `call_servants` (one-shot: claps twice above his head, points off right) | • `take_hand` (one-shot hold: after a pause, reaches out and takes the hand in front at chest height) |
| • `sad_idle` (loop: shoulders slumped) | • `feast_cheer` (one-shot hold: both arms up, laughing) | |
| • `sad_walk` (loop: slow, head down) | • `dance` (loop: an old man's happy folk dance, clapping) | |
| • `feed_pigs` (loop: scatters pods from a sack held at the hip; the sack is part of the clip pose, no prop needed — mime with a cupped left hand if no sack) | • `plead` (loop: open palms, leaning in, gentle) | |
| • `hungry_look` (loop: stares at the trough, licks lips, hand on tummy) | • `arm_out` (one-shot hold: holds out his right hand at chest height toward someone 0.12 in front) | |
| • `sit_sad` (loop: sits on the ground, knees up, head in hands; seat on the page) | | |
| • `idea_stand` (one-shot: looks up, finger up, springs to his feet) | | |
| • `practise` (loop: walking while rehearsing: hand on heart, then bowing, then shaking head, then trying again; locomotion at a slow walk speed) | | |
| • `walk_tired` (loop: slow, weary) | | |
| • `hug` (loop, same reach as the father's) | | |
| • `sorry_head` (one-shot hold: head bowed, hands clasped, still close to the father) | | |
| • `amazed` (one-shot hold: looks at the robe, then the ring, hands spread) | | |
| • `dance` (loop: joyful dance, robe swirling) | | |
| • `wave` (loop) | | |

Every loop seamless; every one-shot ends in a pose blendable in 0.25 s; idles breathe and blink; follow-through on
beard, cloak panels, head-cloths, robe edges. Seated / kneeling clips: meshMinY ≥ −0.008. Report each locomotion clip's
natural speed (u/s) in `clips.json` (`walk`, `strut`, `sad_walk`, `practise`, `walk_tired`, `run`, `walk_hoe`).

## 5. Timeline

Same format as Exodus §5, generated by `tools/story/build_timeline.py prodigal`. Off-stage group voices `friends`
(plate "朋友们 / Friends") and `servants` (plate "仆人 / Servants").

## 6. Set (`assets/prodigal/model/homeland.glb`, root node `homeland`)

Coordinates `(x, z)`; floor x ±0.60, z −0.5875…0.21. Nodes (names are the contract):

| Node | Where / what |
|---|---|
| `ground` | grassy sand at home (left), dry earth in the far country (right), small stones and tufts |
| `backdrop` | relief across the back (front face z ≈ −0.56, top h 0.17-0.30 so the page beyond is hidden, Exodus lesson): home hills left, dry hills + a glint of sea right |
| `house` | centre (−0.38, −0.47), footprint ≈ 0.28 × 0.16, wall h ≈ 0.20, flat roof, outside stair, `door` (front face z ≈ −0.37), windows, vine; empties `lampsFlame` at the lamp points |
| `courtyard` | paving x −0.52…−0.08, z −0.36…0.02; `well` at (−0.46, −0.04) (r ≈ 0.04), `figTree` at (−0.50, −0.28) (crown ≥ 0.20 up), low wall on the west (x ≈ −0.54) and along the back only, jars, bench at (−0.46, −0.32) |
| `field` | x −0.06…0.24, z −0.52…−0.40 furrows and young wheat (h ≤ 0.05), plus the hoeing strip z −0.40…−0.28 that is bare soil (flat) |
| `road` | pale road (flat) from (−0.10, −0.06) via (0.04, 0.02), (0.16, 0.08) to the front edge, and a branch to the tavern at (0.30, −0.22) |
| `tavern` | the far-country tavern, centre (0.40, −0.47), footprint ≈ 0.30 × 0.14: two columns, awning (h ≤ 0.22, front edge z ≤ −0.36), bunting, tables and stools behind z −0.36, amphorae; market stall at (0.54, −0.32) |
| `pigpen` | wooden fence (h ≈ 0.05) around x 0.26…0.56, z −0.06…0.18 with two gaps: north x 0.29…0.40 and west z 0.05…0.16; mud puddles, a trough at (0.48, 0.10); `pods` (a pile of carob pods on the trough) |
| `pigs` | four round pigs inside the pen at x ≥ 0.42 (keep clear of the marks), with a looping action `pigsWiggle` (4 s, seamless: snouts rooting, tails twitching, one pig trotting a little circle) |
| `feast` | long low table at (−0.38, −0.16) (≈ 0.20 × 0.07, h ≤ 0.05) with food, cups and cushions; hidden at rest |
| `lamps` | oil lamps on the table and two hanging lanterns at the door; hidden at rest |

**Marks that must stay clear** (as Exodus: nothing above 0.012 within 0.05 of a mark, nothing on the straight paths
between one actor's consecutive marks; print `CLEARANCE`): father (−0.30, −0.24), (−0.16, −0.06), (0.00, 0.06),
(−0.22, −0.10), (−0.12, 0.08); son (−0.16, −0.20), (−0.22, −0.20), (−0.02, −0.04), (0.16, 0.06), (0.32, −0.26),
(0.34, 0.04), (0.30, 0.10), (0.14, 0.12), (0.10, 0.08), (−0.32, −0.12), (0.06, 0.12); brother (0.02, −0.34), (0.20, −0.32),
(−0.02, 0.10). The feast table is shown only from S11, when the son and father are at (−0.32, −0.12) and (−0.22, −0.10):
keep the table ≥ 0.06 from both.

Triangle budget ≈ 70k (Exodus 69k). Spend it on the house, the fig tree, the tavern awning and bunting, the pigs.
UV0 = the colouring sheet exactly as Exodus (back faces take a plain colour from their own region, L51).

## 7. Audio

As Exodus §7. Voices: the son must change across the story (cheeky → broke and small → sorry → overjoyed); the father
warm and old (never frail), a catch in his voice; the brother firm, grumbling, hurt. `friends` 3-4 voices, `servants`
2-3 voices. Narrator as the other packs.

Music cues: `home leaving party broke pigs homesick road_home run feast brother finale` (`cues.json` with loop points).
SFX: `birds coins cheer wind_dry oink tummy sparkle footsteps_run` plus ambience beds `crickets_night` (from S11, stop
at `finale`) (`mix.json`).

## 8. Effects (`StoryFxProdigal.cs`, registered like `ExodusFx.Defs`)

Reused: `sparkle`, `heart_glow`, `golden_rays`, `night`, `sunset_glow`. New (timeline uses `lamps_flames` on `homeland.lamps`):
- `coins_spray` (from a hand: a fountain of ~12 gold coins arcing up and bouncing on the ground, glints).
- `party_lights` (node: warm coloured string-light glows and bobbing confetti specks around the tavern for `dur`).
- `famine_haze` (stage: hot dry tint, desaturate, drifting dust motes, a faint heat shimmer; fades in/out; must survive
  `BeginAt` fast-forward like `night`).
- `run_dust` (on a bone: dust puffs kicked up behind a running actor for `dur`).
- `music_notes` (node: little music notes floating up and drifting from the house for `dur`).
- `lamp_flame` on `homeland.lampsFlame` must light every lamp empty under `lamps` (several flames, one call) — if the
  existing Ruth effect only lights one point, add a `lamps_flames` variant that finds all children named `lampsFlame*`.
