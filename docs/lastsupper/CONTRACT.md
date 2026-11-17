# The King Who Serves — production contract

Binding for every role. Story and lines: `STORY.md` + `storyboard/story.py`. Look: `DESIGN.md`. How to run each
step: `docs/pack-plans/01-LIFECYCLE.md`. Shared rules: `docs/pack-plans/03-RULES.md`. Kit: `docs/STORY-KIT.md`.
Template packs to copy from: **Real Miracles** (`pipeline/mi_*.py`: Jesus and Peter, the doll's-house room, fixed-paint
friends) and **Jonah** (`pipeline/jn_*.py`, on the kit). Quadruped: **Daniel's lions** (`pipeline/da_characters.py`,
`docs/daniel/CONTRACT.md` §3). Fixed-paint extras: Esther's guards (`pipeline/es_characters.py`, `GUARDS`).

Ids: story `lastsupper`, script prefix `ls` (no other pack uses `ls_` / `LS_`; checked 2026-11-18), env prefix `LS_`,
page material `ls_page`, set `jerusalem`.

## 1. Files and owners

| Role | Owns |
|---|---|
| Lead (story + integration) | `docs/lastsupper/*` (except the role docs below), `assets/lastsupper/timeline.json` (generated), `assets/lastsupper/manifest.json`, `assets/lastsupper/{pack,faces}.json`, Unity, builds, device |
| Characters | `pipeline/ls_characters.py`, `assets/lastsupper/model/{jesus,peter,donkey,john,james,andrew,seller1,seller2}.glb`, `extras_paint.png`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/lastsupper/RIG.md`, `docs/lastsupper/design/faces/` |
| Set + sheet | `pipeline/ls_jerusalem.py`, `assets/lastsupper/model/jerusalem.{glb,blend}`, `jerusalem_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_lastsupper.py` (only if `make_sheet.py` cannot do it as is), `assets/lastsupper/sheet/`, `print/lastsupper-A4.{png,pdf}`, `print/lastsupper-A4-colored.pdf`, `assets/lastsupper/design.json`, `docs/lastsupper/SET.md` |
| Animation | `pipeline/ls_animate.py`, `assets/lastsupper/anim/`, `docs/lastsupper/ANIMATION.md` |
| Voice | `tools/story/cast_lastsupper.json`, `assets/lastsupper/audio/voice/`, `docs/lastsupper/VOICE.md` |
| Music + SFX | `tools/story/music_lastsupper.py`, `assets/lastsupper/audio/music/`, `assets/lastsupper/audio/sfx/`, `docs/lastsupper/MUSIC.md` |
| FX | `manifest.json` `fx.aliases` first; `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxLastSupper.cs` only for the new ids in §8; `docs/lastsupper/FX.md` |

Nobody edits `assets/stories.json`, `assets/library.json`, `tools/i18n/strings.json` or `DGFxEffects.cs` by hand.
**Nobody edits any `mi_*` file or `assets/miracles/`**: this pack reads them, it does not change them (R1, R5).

## 2. Cast

Units: art-width units (1.0 = art rectangle width), Y up, page = XZ plane at y = 0, +Z toward the viewer, +X right.

| Id | Height | Sheet slot (start value; Set + sheet owns the final one in `design.json`) | Paint |
|---|---|---|---|
| `donkey` | withers 0.15, ear tips 0.27, nose to rump 0.28 (+ tail 0.06) | sheetX −0.32, sheetY 0.015, **side view** (the donkey's left side, nose to −X, tail to +X; Daniel's lion rule: UV0 = its side projection at the slot, the far side mirrors it, faces not seen from the side take a clean texel of their own region) | scanned |
| `jesus` | 0.36 | sheetX 0.0, sheetY 0.015 | scanned |
| `peter` | 0.38 | sheetX 0.32, sheetY 0.015 | scanned |
| `john` `james` `andrew` | 0.33 / 0.36 / 0.37 | not on the sheet: fixed paint `model/extras_paint.png` (Esther `GUARDS` / Miracles friends method) | fixed |
| `seller1` `seller2` | 0.33 / 0.35 | not on the sheet: the same `extras_paint.png` | fixed |

**Jesus and Peter are the Real Miracles designs** (`docs/miracles/DESIGN.md` §1, §3; `pipeline/mi_characters.py`):
same heights, proportions (`SPEC`), faces, costume, regions and palette. `pipeline/ls_characters.py` reuses
`build_jesus` and `build_peter` from `mi_characters.py` **unchanged** and adds only this pack's props (§3). How: either
import them (the Miracles module run in the pack namespace, like `story_kit.include`), or, if the Characters role finds
that both packs now need them, move `build_jesus` / `build_peter` and their constants into `pipeline/story_kit/` with
`mi_characters.py` regenerating byte-identical GLBs (R5; say which in `RIG.md`). Do not copy and edit them.
Sheet slot note: Jesus and Peter keep the Miracles slots; the donkey replaces the man at −0.32 (its body 0.28 wide
spans about −0.46…−0.18; Jesus's A-pose hands end near −0.12, so there is a gap; C2).

Budget: each human ≤ 25k triangles (fixed-paint extras ≤ 18k); the donkey ≤ 20k; ≤ 4 bone influences. Props count in
their owner's budget.

## 3. Skeletons

Humans (all seven): the kit's contract bones, A-pose, facing +Z:
`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids`. Extras:
- `jesus`: the Miracles extras `mantle1`, `belt1`; props `towel` (child of `hips`, mesh `jesus_towel`), `basin` (child of
  `root`, mesh `jesus_basin`, sits on the floor 0.06 in front in the kneeling clips), `bread` (child of `handL`), `cup`
  (child of `handR`). All four hidden by default.
- `peter`: the Miracles extras `cloth1`, `bucket` (bone kept, no mesh here); props `palm` (child of `handR`; shown by
  default, the timeline hides it from S04), `towel` (child of `chest`), `jug` (child of `handR`); the last two hidden.
- `john`: `sash1` (from `hips`). `james`: `cloak1` (from `chest`). `andrew`: `cloth1` (head-cloth tail, from `head`).
- `seller1`: `apron1` (from `hips`). `seller2`: `pouch` (from `hips`, the money pouch swings).

Donkey, facing +Z (nose toward the viewer), standing on all fours, the Daniel lion skeleton with donkey ears and a
short tail:
`root hips spine chest neck head jaw eyelids earL earR tail1 tail2
 upperArmL forearmL pawL  upperArmR forearmR pawR   (front legs, from chest)
 thighL shinL footL  thighR shinR footR             (back legs, from hips)`
`root` at the ground under the belly centre. The **seat** (top of the blanket over the spine, centre) is at
y = 0.155 at rest, x/z = the root.

Props are rigid meshes parented to their bone; the director shows / hides them by `prop` events (`"jesus/towel"`):
the node name after the slash is the bone name **and** the mesh object (`jesus_towel` under bone `towel`). Hidden props
take their colour from a printed region (C7): `jesus/towel`, `peter/towel` → the set's `lowTable` cloth region (white);
`basin`, `jug`, `cup` → the set's `cupTable` region; `bread` → the set's `breadLoaf` region; `palm` → the set's
`palmsRoad` green. Say the anchors in `RIG.md`.

Faces: decals on UV1, one PNG per expression in `docs/lastsupper/design/faces/<char>_<expr>.png` (lists in DESIGN §1).
Jesus's and Peter's existing drawings are reused from `docs/miracles/design/faces/` (copy or read; do not redraw them);
only `jesus_sad`, `peter_proud`, `peter_sheepish`, `peter_puzzled` are new. The five extras share one set of drawings
per group (disciples, sellers), re-coloured hair per person.

## 4. Clips (names are the contract) — actions `<char>_<clip>`

"hold" = one-shot ending in a held pose. "seated" / "kneeling" clips keep meshMinY ≥ −0.008 at base y 0 **and** at
base y UPPER (0.10, the room floor).

| jesus (21) | what |
|---|---|
| `idle` (loop) | standing, relaxed, breathing, blink (reuse the Miracles clip if the rig is the same) |
| `talk` (loop) | open-handed, warm gestures (Miracles) |
| `walk` (loop) | calm walk (Miracles); speed in `clips.json` |
| `stand_talk` (one-shot hold) | rises from a kneel, turns to the room, one hand raised (Miracles) |
| `ride` (loop) | seated astride the donkey: base y RIDE_Y (0.12), hips at local y ≈ 0.035 so the seat touches the blanket (0.155); legs hang down both sides of the barrel (thighs spread ±0.05), hands rest on the knees; a small rock in the donkey's walk rhythm (0.9 s) |
| `ride_wave` (loop) | as `ride`, the right hand waving to the crowd, head turning left and right |
| `ride_talk` (loop) | as `ride`, turned a little to His left, the right hand open, speaking |
| `sad_look` (one-shot hold) | stops, looks slowly over the court, shoulders drop a little, face `sad` |
| `tip_table` (one-shot, 1.6 s) | steps in, takes the table's near edge (hands at y ≈ 0.07, 0.05 in front) and lifts it so it tips away from Him; marker `tip` at 0.9 s (the timeline swaps `table2` → `table2Tipped`); ends upright, firm |
| `firm_talk` (loop) | standing tall, one arm pointing up and out ("My Father's house"), firm face, not angry |
| `open_cage` (one-shot hold) | reaches to the cages on the table (0.05 in front, hands at y ≈ 0.10), opens the doors, lifts both hands up as the doves go; marker `open` at 1.6 s |
| `rise_towel` (one-shot, 3.0 s) | (standing at the basin stand, facing it) ties the towel round His waist (prop shown at 0.8 s), lifts the jug and pours into the basin (1.8-3.0 s), picks up the basin (prop `basin` shown at 1.6 s, the set's `basinJug` hidden) |
| `kneel_wash` (loop, kneeling) | kneels 0.11 in front of a seated person; the basin on the floor in front; scoops water over their feet, wipes with the towel end; gentle |
| `kneel_talk` (loop, kneeling) | same kneel, looks up, speaks gently, one hand open |
| `kneel_laugh` (one-shot hold, kneeling) | same kneel, a warm laugh, shoulders shaking |
| `sit_supper` (loop, seated) | sits cross-legged on a cushion at the low table (table top UPPER + 0.05), hands near the table, small breathing and look-arounds |
| `bless_bread` (one-shot hold, seated) | takes the loaf from the table (prop `bread` shown at 0.2 s, set `breadLoaf` hidden), lifts it a little, looks up (`look_up`), breaks it in two (marker `break` at 2.2 s), offers the halves to both sides |
| `lift_cup` (one-shot hold, seated) | takes the cup (prop shown at 0.4 s, set `cupTable` hidden), lifts it with both hands to chest height, holds it out a little |
| `smile` (loop, seated) | seated, warm smile, a small nod |
| `laugh` (one-shot) | standing warm laugh (Miracles) |
| `wave` (loop) | friendly wave (Miracles) |

| peter (18) | what |
|---|---|
| `idle` `talk` `walk` `laugh` | as in Miracles (reuse) |
| `amazed` (one-shot hold) | as in Miracles, but the timeline plays it **seated on the bench** (S07): it must work from the `sit_bench` pose without standing up (A4); a seated variant is fine if the standing one cannot |
| `cheer` (loop) | walks in place / stands, waving the palm frond high over his head, shouting |
| `listen_stone` (one-shot hold) | bends at the waist toward a heap of stones 0.08 in front (stone tops y ≈ 0.03), cups a hand to his ear, then taps a stone, puzzled (`puzzled`) |
| `boast` (loop) | chest out, thumbs at his chest, chin up (`proud`) |
| `argue` (loop) | flustered, waving his hands, turning away and back |
| `sit_bench` (loop, seated) | sits on a bench (seat UPPER + 0.04), hands on knees, feet on the floor |
| `refuse` (one-shot hold, seated) | jerks both feet back under the bench, both hands up, palms out, leaning away (`shock`) |
| `offer_all` (one-shot hold, seated) | thrusts both hands forward, palms up, then ducks his head forward as if under a tap (comic) |
| `sit_wash` (loop, seated) | seated, feet forward, looks down at his feet being washed, a happy sigh now and then |
| `ashamed` (one-shot hold, seated: the timeline plays it on the bench in S09) | eyes down, rubs the back of his neck (`sheepish`) |
| `sit_supper` (loop, seated) | cross-legged on a cushion at the low table |
| `serve_rise` (one-shot, 1.6 s, from seated) | gets up onto one knee, picks up the towel (shown at 0.8 s) and the jug (shown at 0.8 s) from beside him |
| `kneel_serve` (loop, kneeling) | kneels 0.11 in front of a seated person, pours from the jug and rubs with the towel, clumsy and careful |
| `wave` (loop) | big two-arm wave (Miracles) |

| donkey (6) | what |
|---|---|
| `idle` (loop) | standing, ear flicks, tail swish, a head bob; seat (blanket top) stays within ±0.004 of 0.155 |
| `walk` (loop) | short-stepping donkey walk, head nodding; the seat rises and falls ≤ 0.006 (Jesus's `ride` matches it); speed in `clips.json` |
| `hee_haw` (one-shot) | 2.0 s: head up, ears back, jaw opens wide (`heehaw`), ribs pump twice, then shakes its head and ears; marker `bray` at 0.3 s |
| `graze` (loop) | head down to the ground, nibbling (`chew`), an ear turning now and then |
| `sleepy` (loop) | head low, eyes closing (`sleepy`), slow ear droops (S13 option) |
| `happy` (one-shot) | a little hop with the front feet, ears up (spare, for the cover) |

| john / james / andrew (each gets all 14; one shared function set, small per-person variation) | what |
|---|---|
| `idle` `walk` `talk` `cheer` (with an empty waving hand) `boast` `argue` `laugh` | standing clips as Peter's |
| `sit_bench` `sit_wash` `sit_supper` `amazed` `ashamed` (seated) | as Peter's, seated (`sit_wash`: Andrew in S12 turns to face the viewer, feet forward) |
| `nudge` (loop, seated) | elbows the neighbour, grinning (S12) |
| `wave` (loop) | wave |

| seller1 / seller2 (each gets all 6) | what |
|---|---|
| `idle` (loop) | behind the table, rubbing hands / counting |
| `shout` (loop) | hawking: one hand cupped to the mouth, the other holding up a dove (seller1) or a coin (seller2) |
| `walk` (loop) | walk; speed in `clips.json` |
| `shock` (one-shot hold) | jumps back, hands up, eyes huge |
| `chase_coins` (loop; seller2) | bent double, scuttling forward, snatching at the floor; **travels**: speed in `clips.json` |
| `flap` (loop; seller1) | flaps both arms like a bird at the sky, wailing |

Rules: loops seamless; one-shots end in poses the next clip can blend from in 0.25 s; talk clips move `jaw`; secondary
motion on mantle, towel ends, head cloths, cloak, apron, pouch, donkey ears and tail; planted feet / hooves do not
slide; `clips.json` states each travel clip's speed. **The ride pair** (donkey `walk` / `idle` + Jesus `ride` /
`ride_wave` / `ride_talk` at base y RIDE_Y on the same mark and heading) must line up: the animator checks it in one
probe render with both actors on one mark, at rest and at the highest and lowest point of the walk (no gap between seat
and blanket, no leg inside the barrel). **The kneel pairs** (Jesus `kneel_wash` / `kneel_talk` 0.11 in front of a
seated disciple; Peter `kneel_serve` 0.11 in front of Andrew) are probed as pairs at that distance at base y UPPER.

## 5. Timeline

`python3 tools/story/build_timeline.py lastsupper` from `storyboard/story.py`, timed by
`assets/lastsupper/audio/voice/durations.json`. Actors in the upstairs room use `y=UPPER` (0.10); Jesus while riding
uses `y=RIDE_Y` (0.12). Actors not in a scene are parked at `PARK` (0.80, 0.30) and hidden. Cameras never target
`all`. Changes of place (dismount, entering the room, sitting at the bench, moving to the table) are snaps on shot cuts.
Off-stage group voice: `people` (plate 众人 / The crowd).

## 6. Set (`assets/lastsupper/model/jerusalem.glb`, root node `jerusalem`)

Floor x ±0.60, z −0.5875…0.21. Node names are the contract.

| Node | Where / what |
|---|---|
| `road` | pale earth: from the front-right edge (0.60, 0.06…0.18) left along the front (z 0.04…0.18) to the bend at (0.10, 0.07), on to the front of the house (−0.20, 0.04…0.16); a branch from the bend up to the court gate (0.14, −0.12) |
| `palmsRoad` | palm branches and coats laid flat on the road x 0.08…0.56, z 0.05…0.16, h ≤ 0.008; hidden at start (popped in S02) |
| `stones` | five round stones at (0.05, 0.17), heap radius ≤ 0.03, top ≤ 0.03 |
| `crowd1`…`crowd8` | fixed-colour townsfolk with palms, height ≤ 0.28: six along the road's back edge at z −0.04…0.00, x 0.24…0.56 (backs to the court wall, facing the road), two children at the right front corner (x ≥ 0.52, z ≥ 0.17, height ≤ 0.18); looping `crowdSway` (3 s, ±4°, seamless). None between the road marks and the camera at the bend. |
| `temple` | the court: paving x 0.02…0.60, z −0.5875…−0.12, y 0; low front wall at z −0.12 (h ≤ 0.04) with the gate gap x 0.08…0.22; colonnade (4 columns, r 0.02) at z −0.52; the temple front relief behind it (front face z ≈ −0.575, h ≤ 0.45); two striped awnings on poles at z −0.50 (underside ≥ 0.36) |
| `table1` | dove table, x 0.34…0.46, z −0.45…−0.39, top y 0.06; `cages` on it (three wicker cages, top ≤ 0.12); `cagesOpen` = the same with open doors, empty (hidden) |
| `table2` | money table, x 0.42…0.50, z −0.31…−0.25, top y 0.06, coin stacks and a little scale; `table2Tipped` = the same table on its side, tipped away (+X/−Z), footprint inside x 0.42…0.56, z −0.33…−0.24 (hidden) |
| `coinsFloor` | scattered coins, flat (h ≤ 0.006), x 0.40…0.58, z −0.24…−0.15 (hidden; popped in S05) |
| `house` | two storeys at the left back. Ground storey closed, x −0.60…−0.06, z −0.5875…−0.22, h 0.10 (door and window on its front). **Upstairs room**: floor y UPPER = 0.10, interior x −0.58…−0.08, z −0.58…−0.22; walls 0.02 thick; back wall to y 0.46; **front cut away** to a sill ≤ UPPER + 0.04; flat roof edge only at the back and sides (no ceiling over the front half, so the phone sees in). Outside stair (decor) against the right wall. |
| `bench` | along the room's left wall, x −0.58…−0.50, z −0.54…−0.24, seat y UPPER + 0.04, cushions |
| `lowTable` | x −0.36…−0.18, z −0.50…−0.42, top y UPPER + 0.05, white cloth; on it `breadLoaf` (round loaf at (−0.27, −0.46)), `cupTable` (clay cup at (−0.24, −0.45)), a herb dish, a fruit bowl; seat cushions at the supper marks |
| `basinStand` | a small wooden stand at (−0.12, −0.53), top y UPPER + 0.08; `basinJug` = the basin and jug on it (hidden in S07 when Jesus takes them) |
| `lamp1` `lamp2` | oil lamps: `lamp1` in a back-wall niche at (−0.46, −0.575), y UPPER + 0.20; `lamp2` on the table at (−0.20, −0.47) |
| `palmTree` `oliveTree` | lane between house and court: palm at (−0.02, −0.56) (trunk r 0.015, crown y ≥ 0.36, behind everything), olive at (0.00, −0.30) (r ≤ 0.05, crown underside ≥ 0.16) |
| `hills` | Mount of Olives, a low relief along the back edge above the house (front face z ≈ −0.585, h 0.12-0.20 above the back wall line) |

**Marks that must stay clear** (nothing above the actor's base + 0.012 within 0.05; nothing on the straight path between
consecutive marks of one actor; print `CLEARANCE`):
- road (y 0): donkey + Jesus (0.46, 0.13) → (0.26, 0.11) → (0.18, 0.09) → `BEND` (0.10, 0.07) — the donkey is 0.28 long:
  clear a 0.30 × 0.12 box along the heading (−X) round each mark; disciples (0.56…0.63, 0.04…0.17) → (0.38…0.46, …) →
  (0.30…0.40, …) → (0.24, 0.17), (0.30, 0.03), (0.34, 0.15); Peter `PETER_STONES` (0.13, 0.18) (only `stones` within
  0.08, top ≤ 0.03); `DONKEY_TIE` (−0.04, 0.07) (box 0.30 × 0.12).
- court (y 0): `GATE` (0.14, −0.06) → `J_T2` (0.36, −0.26) → `J_T1` (0.28, −0.42); `P_COURT` (0.08, −0.22), `JN_COURT`
  (0.14, −0.30), `JA_COURT` (0.05, −0.34); `SELLER1` (0.40, −0.50); `SELLER2` (0.46, −0.37) → `SELLER2_SIDE`
  (0.56, −0.30) → `COINS` (0.53, −0.18) (coins on the floor are allowed there: h ≤ 0.006). Tables sit 0.05-0.06 from the
  Jesus marks: they are what He reaches for.
- room (y UPPER): `ROOM_J` (−0.15, −0.50), `STAND` (−0.15, −0.46) → `ROUND` (−0.40, −0.36) → `WASH` (−0.43, −0.50) →
  (−0.43, −0.30) → (−0.43, −0.27); `ARGUE` (−0.48, −0.32), (−0.39, −0.35), (−0.30, −0.33), (−0.21, −0.36); `BENCH`
  seats (−0.54, −0.50 / −0.42 / −0.34 / −0.27) (the bench itself is the seat); supper seats (−0.34, −0.54), (−0.27,
  −0.54), (−0.20, −0.54), (−0.41, −0.46), (−0.41, −0.35) (cushions ≤ 0.02 are allowed). Nothing in the room above
  UPPER + 0.06 between x −0.46 and −0.38 (the kneeling lane in front of the bench) except the table's own corner at
  x −0.36.

Budget: set ≤ 70k triangles. UV0 = the colouring sheet, exactly as the Miracles set (front / plan projections, upward
faces take a clean texel from their own region). The room interior seen through the open front needs its own sheet
regions (inside wall, floor mats, bench cushions, table cloth) or a plain colour from the house stone region (L51).

## 7. Audio

Voice −16 LUFS, music −20 LUFS, SFX peak −3 dBFS, 44.1 kHz mono WAV + 96 kbps MP3.

- **Voices** (`cast_lastsupper.json`): `narrator` = the family storyteller (Qwen `vivian` zh, same as every pack);
  `jesus` and `peter` = **the same voice settings as `cast_miracles.json`** (same speaker, same pitch range: the two
  packs are one Jesus and one Peter); `john`, `james`, `andrew`, `seller1`, `seller2` new, chosen by audition (John
  clearly younger; Andrew softer and lower-key than Peter); `people` = a crowd of 8-10 layered voices incl. two children
  (Jonah's `people` method). **English and Chinese: Qwen3-TTS only (Apache-2.0). Do not use `edge-tts`** (R7).
  Names to check in the transcript (V3): 耶路撒冷, 逾越节, 和散那, 彼得, 安得烈, 雅各, 约翰, 犹大.
- **Music cues**: `road hosanna stones market prayer_house argue towel not_my_feet serve supper my_turn finale`
  (+ `cues.json` loops).
- **SFX**: `crowd_far crowd_cheer hee_haw ding market_bustle coins_clink table_tip coins_scatter dove_flutter water_pour
  splash_small` (+ `mix.json`). `market_bustle` and `crowd_far` are seamless loops; stop `market_bustle` at S06.
  `hee_haw` is a creature sound (M4): short, comic, a synthesized two-tone bray.

## 8. Effects

Already in the app (use as is): `golden_rays` (D&G), `sparkle` `heart_glow` `sunset_glow` `night` `dust_road`
`lamp_flame` (Ruth), `coins_spray` `music_notes` (Prodigal).
New, in `StoryFxLastSupper.cs`, class `LastSupperFx` (the FX role adds `"class": "LastSupperFx"` to the manifest in the same
change that adds the file) (3 ids, nothing else; if an existing effect already looks right, alias it in the
manifest instead and say so in `FX.md`, F1):
- `palm_toss` (node): green palm leaves and a few coloured cloth scraps tossed up along the node's length and settling
  on the ground, 3-5 per second, for `dur` (crowd joy on the road; not petals, not confetti colours).
- `doves_fly` (node): 6-8 white doves burst up out of the node, flapping, spiralling up and away off the top of the
  page within ~2.5 s, a few small feathers drifting down (check white on the cream court, F4).
- `water_pour` (node): a thin clear-blue stream from just above the node down into it for `dur`, with a small ripple
  ring and a few drops; works at the basin (on the floor) and at Peter's jug (hand height).

## 9. Manifest (lead writes it at Integration)

Strings: `dg_jesus` 耶稣 / Jesus, `dg_peter` 彼得 / Peter (same values as the Miracles manifest), `dg_lastsupper_donkey`
小驴 / The donkey, `dg_john` 约翰 / John, `dg_james` 雅各 / James (not `dg_jacob`: same Chinese name, different person),
`dg_andrew` 安得烈 / Andrew, `dg_lastsupper_seller1` 卖鸽子的 / The dove seller, `dg_lastsupper_seller2` 兑换银钱的 /
The money changer, `dg_lastsupper_people` 众人 / The crowd. Library: pinyin `fú shì rén de wáng`, minutes 4,
`"after": "miracles"`.
