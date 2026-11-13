# Esther — Haman rework (2026-11-14)

Owner review of the first Esther build: Haman, the villain, has no presence. "No super-proud scene, no cowardly
screaming when he is dragged away; his lines and his body language are both weak. Rework him thoroughly."

Everything in `CONTRACT.md` still holds unless this file says otherwise. The play itself is already rewritten in
`storyboard/story.py` (single source; run `python3 tools/story/build_timeline.py esther` to regenerate
`assets/esther/timeline.json` and `STORYBOARD.md`). Read the S03, S04, S08b, S08c, S08d and S10 blocks there first.

## 1. Who Haman is now

A pompous, vain, cowardly peacock — a cartoon villain children laugh at, never fear. Every emotion is played big:
he swaggers belly-first with his nose in the air, preens over his ring, laughs too long at his own greatness, throws a
stamping tantrum when Mordecai will not bow, gloats to the audience rubbing his hands, acts out his own imagined
parade, collapses when the honour goes to Mordecai, sulks through the streets, then blubbers on his knees and is
dragged off by two guards kicking and wailing. Comic timing matters more than realism: anticipation, overshoot,
squash and stretch, holds on the funny poses.

## 2. New beats (see story.py for exact lines and timing)

| Shot | What Haman does | Clips |
|---|---|---|
| S03 | fanfare; herald off-stage "哈曼大人驾到——！"; parades in; crowd "拜见哈曼大人！"; preens over his ring; laughs at his own greatness; hears Mordecai will not bow; tantrum with steam from his head and three stamps | `parade` `preen` `laugh_proud` `smug` `fume` |
| S04 | (as before) whispers, takes the ring; then turns to the audience and gloats, rubbing his hands | `whisper` `take_ring` `scheme` |
| S08b | invited to the queen's banquet: skips and hops, thumps his chest, laughs | `boast` `laugh_proud` |
| S08c | the king asks how to honour a man; aside to the audience "who but me?"; acts out the grand parade (robe, horse, herald shout); the king: "do it for Mordecai!"; he freezes, jaw drops, cap pops | `scheme` `daydream` `stunned` |
| S08d | trudges across the page leading the (unseen) horse, shouting through gritted teeth | `sulk` `sulk_shout` |
| S10 | jumps when exposed (cap flies), begs on his knees shuffling toward Esther, the king calls the guards; two guards march in, grab his arms, drag him off the page backwards while he kicks and wails | `shock` `beg` `dragged`; guards `march` `grab` `drag` |

## 3. New and changed ids (the contract)

**Characters.** `haman` keeps every bone of `CONTRACT.md` §3 (names and hierarchy unchanged so existing clips still
work) and gains `plume1 plume2` (chain from `cap`: a tall feather on his cap that bobs and whips). New cast members
`guard1`, `guard2`: palace guards (Persian-inspired: tall fluted cap, tunic with a belt, trousers, boots, a short
spear in the outer hand), the same humanoid skeleton as the others, height 0.38, plus `spear` (child of the outer
hand). They are **not on the colouring sheet**: they wear a fixed painted texture in the demo palette
(`assets/esther/model/guard_paint.png`, UV0) instead of the child's colours. guard1 and guard2 may share one mesh;
vary them a little (cap colour, beard or no beard).

**Haman faces** (`docs/esther/design/faces/haman_<expr>.png`, UV1 decal, same layout as the existing four), all
pushed further than before:
`proud` (eyes half-shut, nose up, curled smirk), `laugh` (eyes squeezed to arcs, huge open laughing mouth),
`furious` (V brows, bulging eyes, gritted teeth, red cheeks), `scheming` (eyes slid sideways, wicked grin),
`stunned` (dot eyes, jaw hanging), `sulky` (heavy lids, pout), `terrified` (huge eyes with tears, screaming
O mouth), `begging` (wet puppy eyes, wobbly mouth). Keep `smug sly shocked scared`. Guards: `guard_stern`.

**Haman clips** (`assets/esther/anim/haman.glb`, add to the existing ten; `naturalSpeed` in clips.json for every
locomotion loop):

| Clip | Loop | Description |
|---|---|---|
| `parade` | loop, locomotion | exaggerated proud march: belly and chest out, chin high, high knees, arms swinging wide, a bounce; plume whips |
| `preen` | one-shot ~2.5 s, holds | holds the ring hand up to admire it, huffs on it, polishes it on his chest, adjusts his cap |
| `laugh_proud` | loop | hands on hips, head thrown back, belly and shoulders shaking in a "ha-ha-ha" rhythm (not even) |
| `fume` | loop | red-faced tantrum: fists shaking, alternating stamps (markers `stomp`), whole body trembling |
| `scheme` | loop | hunched toward the viewer, rubbing his hands, eyes sideways, giggling shoulder bounces |
| `boast` | loop | happy skip-hop in place, thumb jabbing his chest, then arms opening "look at me" |
| `daydream` | one-shot ~6 s, holds | grand gestures: sweeps a robe over his shoulders, mimes riding a horse, cups his mouth to shout, arms wide |
| `stunned` | one-shot, holds | freezes mid-gesture, jaw drops, arms go limp, cap pops up (marker `pop`) and drops back, a small topple |
| `sulk` | loop, locomotion | slouched, dragging feet, one arm forward holding imaginary reins, head hanging |
| `sulk_shout` | loop | standing slouched, cupping one hand to his mouth, a grudging shout every ~2 s |
| `beg` | loop, slow locomotion | on his knees, hands clasped, bobbing and pleading, shuffling forward on his knees |
| `dragged` | loop, locomotion, travels **backwards** | arms held out and up at the sides (guards hold his upper arms), legs kicking wildly, heels dragging, head thrashing, body leaning back |

**Guard clips** (`assets/esther/anim/guard1.glb`, `guard2.glb`, actions `guard1_<clip>` / `guard2_<clip>`):
`idle` (loop, at attention, spear upright), `march` (loop, locomotion, brisk), `grab` (one-shot: steps in and clamps
the inner hand on Haman's upper arm, marker `grab`, holds), `drag` (loop, locomotion, leaning forward pulling, inner
hand back at Haman's arm height). In S10 guard1 stands at Haman's right (screen left), guard2 at his left; inner hand
= the hand toward Haman.

**Sync rule:** `haman_dragged`, `guard1_drag`, `guard2_drag` have the same `naturalSpeed` (0.11 art/s) so the three
travel together. Haman faces the king and moves backwards; the guards face the way they walk.

**Faces per clip** (`assets/esther/faces.json`, Integration): parade/preen/smug → proud, laugh_proud/boast → laugh,
fume → furious, scheme/whisper → scheming, daydream → proud, stunned → stunned, sulk/sulk_shout → sulky,
shock → shocked, beg → begging, dragged → terrified.

**Voices.** New ids: `es_03a` (herald), `es_03b` (crowd), `es_04b`, `es_06b`, `es_12b`–`es_12i`, `es_16b`, `es_16c`;
changed text: `es_03`, `es_04`, `es_16`. New roles `herald` (off-stage court crier) and `crowd` (many people at once,
off-stage). Haman must sound like a real comic actor in a children's radio play: big pitch swings, a real laugh,
a real tantrum, a real wail that fades — not a newsreader reading "哈哈哈". Same voice in zh and en if possible.

**Music / SFX.** New cues `haman_fanfare` (pompous oom-pah brass and timpani, swaggering, comic), `sulk_march`
(slow, droopy tuba march, comic-sad, with a cheerful crowd feel under it). New SFX `fanfare` (short herald
trumpets), `steam` (kettle-like hiss + puffs, ~3 s), `wah_wah` (descending muted-trombone "fail" sting),
`armor_march` (brisk boots + metal clink, ~2 s), `grab` (cloth grab + small yelp-free thump).

**Effects.** New ids `anger_steam` (cartoon steam puffs from both sides of the head, puffing in bursts, reddish
tint), `sweat_drops` (cartoon sweat drops flying off the head), `dust_drag` (little dust puffs along the ground at the
feet while dragged). Child-friendly: comic, not violent.

**Sheet.** Haman's new silhouette (belly, nose, plume, curled shoes) changes his outline on the colouring sheet, so the
sheet, regions, demo colouring, `print/esther-A4.pdf` and the sheet signatures are rebuilt. The guards are not
drawn on the sheet.
