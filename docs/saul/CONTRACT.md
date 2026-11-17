# Saul Sees the Light! — production contract

Binding for every role. Story and lines: `STORY.md` + `storyboard/story.py`. Look: `DESIGN.md`. How to run each step:
`docs/pack-plans/01-LIFECYCLE.md`. Shared rules: `docs/pack-plans/03-RULES.md`. Kit: `docs/STORY-KIT.md`.
Template packs to copy from: **He Is Risen!** (`pipeline/rs_*.py`: reusing the Miracles Peter by running
`mi_characters.py` in the pack namespace, fixed-paint extras, the `ride()` seat method, `path()` / `hide()` staging) and
**The King Who Serves** (`pipeline/ls_*.py`: the doll's-house room, fixed-paint disciples). Men: Real Miracles
(`pipeline/mi_characters.py`, `build_friend`) as the reference body for every man in this pack.

Ids: story `saul`, script prefix `sa` (no other pack uses `sa_` / `SA_`; checked 2026-11-18), env prefix `SA_`, page
material `sa_page`, set `damascus` (no other pack uses it; checked 2026-11-18). **The cast id `saul` is not new**: the
string `dg_saul` is David & Goliath's King Saul (扫罗王), so this pack's subtitle name is the per-story string
`dg_saul_saul` (I4, §9).

## 1. Files and owners

| Role | Owns |
|---|---|
| Lead (story + integration) | `docs/saul/*` (except the role docs below), `assets/saul/timeline.json` (generated), `docs/saul/STORYBOARD.md` (generated), `assets/saul/manifest.json`, `assets/saul/{pack,faces}.json`, Unity, builds, device |
| Characters | `pipeline/sa_characters.py`, `assets/saul/model/{saul,ananias,barnabas,judas,priest,tallguard,shortguard,peter}.glb`, `extras_paint.png`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/saul/RIG.md`, `docs/saul/design/faces/` |
| Set + sheet | `pipeline/sa_damascus.py`, `assets/saul/model/damascus.{glb,blend}`, `damascus_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_saul.py` (only if `make_sheet.py` cannot do it as is), `assets/saul/sheet/`, `print/saul-A4.{png,pdf}`, `print/saul-A4-colored.pdf`, `assets/saul/design.json`, `docs/saul/SET.md` |
| Animation | `pipeline/sa_animate.py`, `assets/saul/anim/`, `docs/saul/ANIMATION.md` |
| Voice | `tools/story/cast_saul.json`, `assets/saul/audio/voice/`, `docs/saul/VOICE.md` |
| Music + SFX | `tools/story/music_saul.py`, `assets/saul/audio/music/`, `assets/saul/audio/sfx/`, `docs/saul/MUSIC.md` |
| FX | `manifest.json` `fx.aliases` first; `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxSaul.cs` only for the new ids in §8; `docs/saul/FX.md` |

Nobody edits `assets/stories.json`, `assets/library.json`, `tools/i18n/strings.json` or `DGFxEffects.cs` by hand.
**Nobody edits any `mi_*` / `rs_*` / `ls_*` file, `music_miracles.py`, `cast_miracles.json`, `assets/miracles/`,
`assets/risen/` or `assets/lastsupper/`**: this pack reads them, it does not change them (R1, R5).

## 2. Cast

Units: art-width units (1.0 = art rectangle width), Y up, page = XZ plane at y = 0, +Z toward the viewer, +X right.

| Id | Height | Sheet slot (start value; Set + sheet owns the final one in `design.json`) | Paint |
|---|---|---|---|
| `ananias` | 0.33 | sheetX −0.32, sheetY 0.015 | scanned |
| `saul` | 0.37 | sheetX 0.0, sheetY 0.015 (cloak inside ±0.10 of his centre) | scanned |
| `barnabas` | 0.39 | sheetX 0.32, sheetY 0.015 | scanned |
| `judas` `priest` | 0.35 / 0.36 | not on the sheet: fixed paint `model/extras_paint.png` | fixed |
| `tallguard` `shortguard` | 0.41 / 0.30 | not on the sheet: fixed paint | fixed |
| `peter` | 0.38 | not on the sheet: fixed paint, the Miracles demo colours (as in He Is Risen!) | fixed |

There is **no `jesus` actor** in this pack: `jesus` is a voice id only (§7). Lines with `who="jesus"` have no actor;
StoryDirector skips the talking head for a speaker with no actor (`StoryDirector.cs`, `if (!A) return;`).

**Reuse, never fork** (R5):
- `peter`: `pipeline/sa_characters.py` gets `build_peter` from `pipeline/mi_characters.py` **unchanged**, the way
  `pipeline/rs_characters.py` does (the Miracles module run in the pack namespace, definitions only). His front ID render
  on a virtual page becomes his part of `extras_paint.png` with the Miracles demo colours.
- Every other man (`saul`, `ananias`, `barnabas`, `judas`, `priest`, `tallguard`, `shortguard`) is `build_friend`
  (Miracles) with a new costume entry, **or** a new builder in `sa_characters.py` where `build_friend` cannot make the
  shape (Saul's cloak, Ananias's round body and cap, Barnabas's mantle, the guards' very tall / very short proportions,
  the priest's turban). The Characters role says in `RIG.md` which actor uses what. If a builder from `rs_characters.py`
  (`build_thomas`'s cloak) fits, run that module in the namespace the same way; if two packs now need the same new code,
  move it into `pipeline/story_kit/` with the old packs regenerating byte-identical GLBs. Do not copy and edit.
- No donkey (Owner question at Gate 1; if wanted, it is `build_donkey` from `ls_characters.py` in the namespace, fixed
  paint, walking beside the guards in S02 only).

Budget: each printed human ≤ 25k triangles; fixed-paint extras ≤ 18k; Saul ≤ 27k with the basket rig; ≤ 4 bone
influences. Props count in their owner's budget. Sheet slot note: three printed figures at −0.32 / 0 / +0.32 (C2);
Barnabas is the widest (big body, mantle): his A-pose hands must stay inside +0.32 ± 0.14.

## 3. Skeletons

Humans (all eight): the kit's contract bones, A-pose, facing +Z:
`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R thighL/R shinL/R footL/R toeL/R
fingersL fingersR eyelids`. Extras:
- `saul`: `cloak1` (from `chest`, the cloak's back); props `letters` (child of `handR`, mesh `saul_letters`), `bread`
  (child of `handR`, mesh `saul_bread`); the **basket rig**: bone `basket` (child of `hips`; mesh `saul_basket`, a round
  woven basket 0.10 across, 0.08 high, Saul crouched inside it) and bone `ropeTop` (child of `root`, fixed at rig-local
  (−0.065, 0.235, 0): the window when Saul stands at BASKET_DOWN facing the viewer), and the mesh `saul_ropes` (two
  ropes from the basket rim to the window) skinned to `basket` (bottom ends) and `ropeTop` (top ends), so the ropes
  stretch as the clip lowers the hips. `saul/basket` shows and hides the basket and ropes together. All hidden by default.
- `ananias`: prop `jug` (child of `handR`, mesh `ananias_jug`; hidden by default).
- `barnabas`: `mantle1` (from `chest`).
- `judas`: prop `bread` (child of `handR`, mesh `judas_bread`; hidden by default).
- `priest`: none (the scroll he hands over is Saul's `letters`).
- `tallguard`: prop `lantern` (child of `handR`, mesh `tallguard_lantern`; hidden by default). `shortguard`: none.
- `peter`: the Miracles extras `cloth1`, `bucket` (bone kept, no mesh, as in He Is Risen!).

Props are rigid meshes parented to their bone; the director shows / hides them by `prop` events (`"saul/basket"`): the
node name after the slash is the bone name **and** the mesh object (`saul_basket` under bone `basket`). Hidden props
take their colour from a printed region (C7): `saul/letters` → the set's `synagogue` column region (cream);
`saul/bread`, `judas/bread` → the set's `breadBasket` region; `saul/basket` → `breadBasket` (straw); `ananias/jug` →
`waterJar` (terracotta); `tallguard/lantern` → `waterJar`. Say the anchors in `RIG.md`.

Faces: decals on UV1, one PNG per expression in `docs/saul/design/faces/<char>_<expr>.png` (lists in DESIGN §1).
Peter's existing drawings are copied from `docs/miracles/design/faces/` and `docs/risen/design/faces/` (`peter_sad`);
the Miracles friends' group drawings (`happy`, `talk`, `amazed`, `shock`, `laugh`) are copied and re-coloured for
Judas and the guards. New drawings: all of Saul's, Ananias's, Barnabas's and the priest's; `peter_afraid`; the guards'
`puff`, `sleepy`, `asleep`, `puzzled`.

## 4. Clips (names are the contract) — actions `<char>_<clip>`

"hold" = one-shot ending in a held pose. "seated" / "kneeling" clips keep meshMinY ≥ −0.008 at base y 0 (A6).
"travel" = a locomotion clip whose naturalSpeed goes in `clips.json`. Every clip below is used in `story.py` (count:
saul 22, ananias 14, barnabas 6, judas 5, priest 2, tallguard 12, shortguard 11, peter 4).

| saul (22) | what |
|---|---|
| `idle` (loop) | standing; face `angry` until S08, `kind` after (the face table in `faces.json`, not the clip, decides) |
| `walk` (loop, travel) | an ordinary, easy walk (S12) |
| `march` (loop, travel) | a stiff, stomping march, chin up, arms swinging hard, the cloak flapping (planned 0.11 / s) |
| `angry_talk` (loop) | talks with a pointing finger and a fist, stamps once; face `shout` |
| `take_letters` (one-shot hold) | takes the scroll from the priest's hand (prop shown at 1.0 s by the timeline), holds it up proudly, tucks it in his belt |
| `fall_down` (one-shot hold, 1.4 s) | an arm flies up to shield his eyes from the light above, knees give, sits down hard on the ground (bump at 0.7 s); ends seated, leaning back on one hand, looking up; meshMinY ≥ −0.008 |
| `sit_look_up` (loop, seated on the ground) | seated, one hand shading his eyes, looking up into the light; small trembling breaths; face `look_up` |
| `get_up_blind` (one-shot hold, 1.6 s) | from `sit_look_up`: gets up slowly, eyes closed, both hands reaching out in front, turns his head searching; face `blind` |
| `walk_blind` (loop, travel, pair) | slow, careful steps, the right hand forward holding the guard's hand at 0.08-0.10 ahead, the left hand out a little (planned 0.05 / s) |
| `sit_pray` (loop, seated cross-legged on the mat) | hands folded at the chest, head a little bowed, eyes closed, slow breathing; once in a while a small gentle head shake (no food, thank you); face `pray` |
| `see_again` (one-shot hold, 1.6 s, seated) | blinks, rubs his eyes with both hands (≤ 0.5 s over the eyes, A5), the eyes open wide, both hands open with joy; face `see` |
| `kneel` (loop) | on both knees, head bowed, hands folded (S09, the jug above him) |
| `eat_bread` (one-shot hold, 3.0 s, from `kneel` to sitting back on the heels) | takes the loaf (shown by the timeline), a big happy bite (marker `bite` at 1.2 s), chews (face `chew`), laughs |
| `preach` (loop) | on the top step (base y 0.04), arms opening wide to everyone, one hand to his heart, warm and strong |
| `talk` (loop) | friendly talk, open hands (S13) |
| `basket_wait` (loop, seated in the basket) | crouched in the basket hanging at the window (basket bottom 0.17 above the base), holding the rim, peeking down; the basket sways a little on its ropes; face `whisper` |
| `basket_down` (one-shot hold, 6.0 s) | the descent: hips and basket go from the `basket_wait` height down to the ground in small jerky drops (rope hand over hand above), a sway, a soft bump at 6.0 s; the ropes stretch (`ropeTop` stays still) |
| `basket_out` (one-shot hold, 1.4 s) | climbs out over the rim to the right (+X, away from the wall), stands, waves up at the window with a finger to his lips (the timeline shrinks the basket away at 1.4 s) |
| `tiptoe` (loop, travel) | big careful tiptoe steps, knees high, arms out for balance, a finger to the lips (planned 0.06 / s) |
| `hug` (loop, pair) | a warm two-armed hug with Peter at 0.10, a small sway |
| `wave` `cheer` (loops) | a friendly wave; both arms up, laughing |

| ananias (14) | what |
|---|---|
| `idle` `walk` (travel) `talk` | standing clips (Miracles friend-like, a slightly waddling round man) |
| `kneel_pray` (loop, kneeling) | kneels, hands folded, eyes closed |
| `kneel_look_up` (loop, kneeling) | looks up into the light, hands open, rapt; face `look_up` |
| `startle` (one-shot hold, 1.0 s) | from kneeling: jumps up to his feet in alarm, hands up by his face, knees knocking; face `fright` |
| `nervous` (loop) | wringing his hands, knees knocking, glancing about; face `gulp` |
| `tiptoe` (loop, travel) | as Saul's tiptoe but nervous: little steps, shoulders up, peering ahead (planned 0.06 / s) |
| `knock` (one-shot hold, 1.0 s) | a timid knock on the door post at 0.05 in front (marker `knock` at 0.2 s), steps back a little |
| `hands_on` (loop, pair) | stands beside the seated Saul at 0.08 and rests both hands gently on his head; face `brave` |
| `pour` (one-shot hold, 2.4 s) | lifts the jug (`ananias/jug`) over the kneeling Saul at 0.08 and pours (marker `pour` 0.6-2.0 s, the timeline plays `water_pour` at the jug) |
| `listen` (loop) | stands listening, nodding, a happy smile |
| `cheer` `wave` (loops) | |

| barnabas (6) | what |
|---|---|
| `idle` `walk` (travel) `talk` `laugh` `wave` | standing clips, big and warm |
| `arm_round` (loop, pair) | an arm round the shoulders of the person beside him (Saul at 0.10), the other hand open toward Peter |

| judas (5) | what |
|---|---|
| `idle` `listen` `laugh` `wave` | standing clips (Miracles friends) |
| `offer_bread` (loop, travel-free) | holds the loaf out with both hands, a hopeful little bow; used with a `to` only for a 1-2 step move (≤ 0.05; if that glides, the lead swaps it for `walk` then `offer_bread`) |

| priest (2) | what |
|---|---|
| `idle` (loop) | stands calmly on the porch, hands folded in his sleeves |
| `give_letters` (one-shot hold, 1.2 s) | holds out a rolled scroll (Saul takes it at 1.0 s; the priest's hand is empty after) |

| tallguard (12) | what |
|---|---|
| `idle` `walk` (travel) | standing clips, gangly |
| `walk_puff` (loop, travel) | a tired trot carrying the bags, the long neck bobbing (planned 0.085 / s) |
| `puff` (loop) | bent over, hands on his knees, panting |
| `shrug` (one-shot hold) | a big shrug at the short guard, palms up |
| `duck` (one-shot hold) | crouches, both arms over his head (comic, a child hiding from thunder), then peeps out between his arms |
| `amazed` (loop) | looks round for the voice, mouth open |
| `lead_hand` (loop, travel, pair) | walks slowly forward, the left arm reaching back to hold Saul's hand at 0.08-0.10 behind (planned 0.05 / s) |
| `listen` `scratch_head` (loops) | listening; scratching his cap, puzzled (face `puzzled`) |
| `lantern_peer` (loop) | holds the lantern up high, peers down the road, turns his head slowly left and right |
| `wave` (loop) | a shy wave |

| shortguard (11) | what |
|---|---|
| `idle` `walk` (travel) `talk` `listen` `amazed` | standing clips, round |
| `walk_puff` (loop, travel) / `puff` / `duck` | as the tall guard's |
| `boast` (loop) | chest out, thumbs in his sash, rocking on his heels |
| `doze` (loop) | falls asleep standing, head nodding down and jerking up, a little sway (face `asleep`); the timeline adds `zzz` |
| `wave` (loop) | |

| peter (4) | what |
|---|---|
| `idle` | as in Miracles (reuse) |
| `peek_afraid` (one-shot hold) | peeks round the door post, then shrinks back half behind it, hands up; face `afraid`; **his face stays visible from the S12 camera** |
| `hug` (loop, pair) | the partner of Saul's `hug` at 0.10 |
| `wave` (loop) | as in Miracles |

Rules: loops seamless; one-shots end in poses the next clip can blend from in 0.25 s; talk clips move `jaw`; secondary
motion on cloaks, mantles, shawls, sashes and the ropes; planted feet do not slide; `clips.json` states each travel
clip's speed. **Pairs probed at their distance**: Saul `walk_blind` / tall guard `lead_hand` at 0.08-0.10 (moving, same
speed; probe the corners at ROAD_E and GATE_OUT); Ananias `hands_on` on the seated Saul at 0.08; Ananias `pour` over the
kneeling Saul at 0.08; Barnabas `arm_round` at 0.10; Peter / Saul `hug` at 0.10. **The basket** is probed with
`damascus.glb`: at BASKET_DOWN facing the viewer the basket clears the wall face (x 0.03) in every frame of
`basket_down`, the rope tops sit in the window opening (y 0.20-0.27) and never show above the wall top.

## 5. Timeline

`python3 tools/story/build_timeline.py saul` from `storyboard/story.py`, timed by
`assets/saul/audio/voice/durations.json` (an estimate until the voices exist: 243.4 s on 2026-11-18). Saul on the
synagogue step uses `y=STEP_Y` (0.04); the priest on the porch `y=PORCH_Y` (0.04). Actors not in a scene are parked at
`PARK` (0.80, 0.30) and hidden (`hide()`). Jesus is a voice with a light (`road_light`, `voice_light()` = `angel_light`
+ `appear_chime`), never an actor. Cameras never target `all`. Changes of place are snaps on shot cuts. Multi-leg moves
use `path()` with the planned speeds `V_MARCH V_PUFF V_WALK V_BLIND V_TIPTOE`; after Animation the lead replaces them
with the clips.json values. No path runs past its shot's cut (S11 keeps only the first leg of Saul's tiptoe).

## 6. Set (`assets/saul/model/damascus.glb`, root node `damascus`)

Floor x ±0.60, z −0.5875…0.21. Node names are the contract.

| Node | Where / what |
|---|---|
| `cityWall` | sand-stone wall x −0.03…0.03, z −0.5875…−0.02, top 0.30 (rounded battlements), ending at the front in a round tower centre (0.00, −0.04), r 0.05, top 0.34; FX anchor at the tower top |
| `cityGate` | the gateway through the wall at z −0.22…−0.10 (centre −0.16), round top 0.24, open wooden doors folded back on the inside face |
| `torch1` `torch2` | torches in holders on the outside face (x 0.04) at z −0.25 and −0.07, y 0.20 (FX anchors for `lamp_flame`) |
| `wallWindow` | a small window high in the outside face at z −0.46 (0.07 wide), y 0.20…0.27, a dark opening with a shutter folded open; it opens into the back-right corner of Judas's house; camera target S11 |
| `straightStreet` | pale paving with drawn stones, z −0.28…−0.08, from the gate (x −0.03) to the left edge |
| `ananiasHouse` | a small flat-roofed limestone room x −0.60…−0.46, z −0.5875…−0.32, **open front** (no sill), walls 0.02, h 0.26, roof only at the back half; inside a stool, a lamp on a ledge, a rolled mat; FX anchor (the light) at the room centre (−0.53, 0.30, −0.45) |
| `synagogue` | a facade x −0.44…−0.30 at z −0.40 (h 0.32) with two round columns, a door, a lintel with a simple pattern (no letters); **three steps** z −0.40…−0.30, top step y STEP_Y 0.04 (z −0.40…−0.34) |
| `judasHouse` | the bigger room x −0.28…−0.03 (its right wall is the city wall), z −0.5875…−0.30, **open front** with only a threshold stripe (h ≤ 0.01) and a **door frame** (`judasDoor`: posts at x −0.20 and −0.06, lintel 0.24, nothing between); walls h 0.26, roof only at the back half; inside `prayerMat` at (−0.15, −0.46) (flat, h ≤ 0.01), a low table at (−0.06, −0.53) (r 0.04, top 0.04) with `breadBasket` on it, a big `waterJar` in the back-left corner at (−0.24, −0.55) (r 0.035, top 0.10) |
| `well` | a round well with a bucket at (−0.48, 0.14), r 0.04, h ≤ 0.06; two pots and a crate beside it (h ≤ 0.05) |
| `road` | pale sand-gold earth from the porch steps (0.46, −0.30) down the right side (x 0.44…0.54) to the front, along the front (z 0.04…0.16) to x 0.15, then back to the gate (0.09, −0.16) |
| `rocks` | low desert rocks at (0.30, −0.02), r 0.04, h ≤ 0.05; small bushes beside them (h ≤ 0.04) |
| `milestone` | a small round-topped stone at (0.26, 0.18), h ≤ 0.08 |
| `palm` | one palm at the front-right corner (0.58, 0.16), trunk r ≤ 0.02, crown underside ≥ 0.30, crown only beyond x 0.50 |
| `priestPorch` | Jerusalem: a raised porch x 0.36…0.60, z −0.5875…−0.36, floor y PORCH_Y 0.04, two steps z −0.36…−0.30 (lower step 0.02); four columns (front pair only at x 0.38 and 0.58, z −0.37), a flat roof 0.32; camera target S01 |
| `jerusalemHouse` | a small limestone house x 0.16…0.32, z −0.5875…−0.42, h 0.24; `jerusalemDoor` a wooden door in its front face centred at x 0.24 (0.08 wide, 0.20 high), shown open (dark inside) |
| `jerusalemWall` `hills` | low relief along the back edge (front face z ≈ −0.585): Jerusalem's wall behind the porch and house (h ≤ 0.12 above the roofs), low hills and distant flat roofs behind Damascus |

**Marks that must stay clear** (nothing above the actor's base + 0.012 within 0.05; nothing on the straight path between
consecutive marks of one actor; print `CLEARANCE`):
- Jerusalem (y 0, the priest y 0.04): `PRIEST` (0.47, −0.42) on the porch (the front columns at x 0.38 / 0.58 not
  between him and the S01 camera), `SAUL_PORCH` (0.42, −0.24), S01 (0.44, −0.10), (0.46, −0.12); `JHOUSE_DOOR`
  (0.24, −0.37) (the door itself 0.05 behind is what Peter peeks round), S12 Saul (0.40, −0.06) → (0.40, −0.24) →
  (0.33, −0.33), Barnabas (0.14, 0.02) → (0.30, −0.22).
- Road (y 0): `ROAD_A` (0.46, −0.22) → `ROAD_B` (0.48, −0.02) → `ROAD_C` (0.40, 0.12) → `ROAD_STOP` (0.30, 0.13) →
  `LIGHT` (0.18, 0.08); guards (0.40, −0.30) → (0.44, −0.04) → (0.44, 0.08) and (0.52, −0.30) → (0.53, −0.02) →
  (0.50, 0.08); S03 (0.30, 0.04), (0.34, 0.13); S05 `LIGHT` → `ROAD_D` (0.13, −0.01) → `ROAD_E` (0.10, −0.10) →
  `GATE_OUT` (0.09, −0.16) → `GATE_IN` (−0.09, −0.16) (through the gateway: its jambs are 0.06 either side).
- Outside the wall at night: `BASKET_DOWN` (0.095, −0.46) (the wall face 0.065 away is what the basket hangs on),
  `TALL_GATE` (0.12, −0.04), `SHORT_GATE` (0.11, −0.27), Saul's tiptoe `BASKET_DOWN` → (0.22, −0.35).
- Damascus (y 0; the step y 0.04): `ANANIAS_HOME` (−0.53, −0.44) (kneeling), `SYN_STEP` (−0.37, −0.36), S10 listeners
  (−0.48, −0.25), (−0.22, −0.25), (−0.10, −0.18), (−0.56, −0.16); S08 Ananias (−0.30, −0.20) → (−0.20, −0.23) →
  `JUDAS_DOOR` (−0.13, −0.27) (the post at x −0.20 / −0.06 is what he knocks on) → `ANANIAS_TOUCH` (−0.08, −0.42)
  through the door frame; `SAUL_MAT` (−0.15, −0.46) (seated / kneeling), `JUDAS_IN` (−0.21, −0.37), Judas
  (−0.21, −0.41), (−0.08, −0.34), (−0.10, −0.40); `ANANIAS_POUR` (−0.22, −0.42). Keep the water jar, table and bread
  basket out of these.
- S13 row (y 0): (−0.34, 0.08), (−0.22, 0.10), (−0.08, 0.10), (0.06, 0.10), (0.18, 0.10), (0.32, 0.10), (0.44, 0.10).

Budget: set ≤ 70k triangles. UV0 = the colouring sheet, exactly as He Is Risen!'s set (front / plan projections, upward
faces take a clean texel from their own region). The house interiors seen through the open fronts need their own sheet
regions (inside walls, mat, bread basket, water jar) or a plain colour from the house stone region (L51). The wall's
outside face (seen in S11 from the right) takes the wall region; the window opening is a plain dark colour.

## 7. Audio

Voice −16 LUFS, music −20 LUFS, SFX peak −3 dBFS, 44.1 kHz mono WAV + 96 kbps MP3.

- **Voices** (`cast_saul.json`): `narrator` = the family storyteller (Qwen `vivian` zh, same as every pack); `jesus` and
  `peter` = **exactly the entries in `tools/story/cast_miracles.json`** (`jesus`: `qwen_design`, f0Hz [120, 160], fx
  `warm`, the same `design` and `instruct` text, zh and en; copy them, do not re-audition). No reverb or "voice from
  heaven" effect on the Jesus voice files; if the light needs it, the music cue carries the shimmer. `saul`, `ananias`,
  `barnabas`, `priest`, `tallguard`, `shortguard` new, chosen by audition (Saul: young and clear, able to be sharp in
  S01-S02 and warm from S08 with the same voice, pinned pitch, V1; Ananias older and softer than Barnabas; Barnabas a
  big warm baritone, clearly not Peter; the priest old and dry, calm, never sinister; the guards a comic pair: thin and
  high / round and gruff). `judas` has no lines. **English and Chinese: Qwen3-TTS only (Apache-2.0). Do not use
  `edge-tts`** (R7). Interjections stay inside phrases with words (咦，这不是…); no line is a bare interjection.
  Names to check in the transcript (V3): 扫罗, 亚拿尼亚, 巴拿巴, 犹大, 大马士革, 耶路撒冷, 保罗, 彼得, 大祭司.
  犹大 here is the host on Straight Street, not Judas Iscariot: plain, no special colour in the narration.
- **Music cues**: `angry_march road light dark_walk three_days ananias brother baptism new_saul basket barnabas finale`
  (+ `cues.json` loops). The Jesus theme is reused from `tools/story/music_miracles.py` (import or copy its note data
  into `music_saul.py`; do not edit the Miracles file).
- **SFX** (all one-shots, sized to their scene: StoryDirector stops loops only at a music cue): `march_steps` (≤ 5 s,
  stomping steps fading), `light_whoosh` (1.5 s, a rising warm shimmer, **not** a bang or thunder), `sit_thud` (0.4 s, a
  soft comic bump), `appear_chime` (1.5 s, a warm shimmer; may be copied from `assets/risen/audio/sfx/`), `knock` (0.8 s,
  three timid knocks), `sparkle_up` (1.2 s), `water_splash` (0.8 s, a gentle pour and splash), `munch` (0.6 s, a happy
  bite), `snore` (≤ 3 s, one comic snore and a whistle), `rope_creak` (≤ 6 s, slow creaks and a basket's wicker
  rustle), `basket_land` (0.4 s, a soft wicker bump) (+ `mix.json`).

## 8. Effects

Already in the app (use as is): `angel_light` (Daniel), `golden_rays` `dust_burst` (D&G), `heart_glow` `lamp_flame`
`night` `dust_road` (Ruth), `prayer_glow` (Esther), `sparkle`, `zzz` (Daniel), `water_pour` (The King Who Serves).
New, in `StoryFxSaul.cs`, class `SaulFx` (the FX role adds `"class": "SaulFx"` to the manifest in the same change that
adds the file) (**2 ids, nothing else**; if an existing effect already looks right, alias it in the manifest instead and
say so in `FX.md`, F1):
- `road_light` (node, ~33 s): the light from heaven. A short whole-frame warm bloom as it comes (≤ 1.5 s, the
  brightest moment; no strobe, no cold flash), then a strong column of warm white-gold light from far above onto the
  node (about 0.25 wide at the ground, soft edges, slow gold motes falling in it), the rest of the stage gently dimmed
  for `dur`, fading out over the last 1.5 s. Saul's face must stay readable inside it (F4: check against his skin and the
  sand-gold road). Candidates to build from or alias first: Gabriel's `descend_light` (a column from 1.8 above) +
  Esther's `truth_flash` (one flash via StoryLight; but it is cold: retint or do not use).
- `scales_fall` (node, 1.6 s): from the node (Saul's head), 6-10 tiny pale silver-white flakes drop from the eyes, glint
  once as they fall, and vanish before the ground; a small warm sparkle burst at the start. Gentle, never a medical
  picture, never in front of the eyes after 0.5 s.
- No `lantern_glow`: the guard's lantern and the gate torches are `lamp_flame` on `tallguard.lantern`, `damascus.torch1`,
  `damascus.torch2` (check that `lamp_flame` reads at lantern size; if not, alias or ask the lead before adding an id).

## 9. Manifest (lead writes the registry at Integration)

Strings: `dg_saul_saul` 扫罗 / Saul (per-story: `dg_saul` is King Saul in David & Goliath, I4), `dg_ananias` 亚拿尼亚 /
Ananias, `dg_barnabas` 巴拿巴 / Barnabas, `dg_saul_judas` 犹大 / Judas (per-story, so it never collides with a future
Judas Iscariot string), `dg_saul_priest` 大祭司 / The high priest, `dg_saul_tallguard` 高个子卫兵 / Tall guard,
`dg_saul_shortguard` 矮个子卫兵 / Short guard, and `dg_jesus` 耶稣 / Jesus, `dg_peter` 彼得 / Peter (same values as the
Miracles manifest). Library: pinyin `sǎo luó biàn le`, minutes 4, `"after": "risen"`; at stage 1 it is stored as `_library_after_gate1`
(merge_packs ignores it) and the lead renames it to `library` at Integration. Registry (Integration only):
order 12, cast as `story.py` `CAST`, `paint` `extras_paint.png` for `judas priest tallguard shortguard peter`, set
`damascus`, sheets `saul-A4`, `saul-A4-demo`.
