# Gabriel — production contract (story pack, the archangel)

Same rules as `docs/daniel/CONTRACT.md` unless this file says otherwise: units, UV = page position, audio formats,
"only Integration runs Unity", nobody commits, nobody touches another role's files. Story: `docs/gabriel/STORY.md` +
`storyboard/story.py`; look: `docs/gabriel/DESIGN.md`. **Daniel (pack #4) and Ruth (#3) are the templates**: copy their
pipeline scripts, keep what works. Read `docs/LESSONS.md` first.

Quality bar: **the most finely sculpted character of the whole app** (owner, 2026-11-14). One hero, so spend
everything on him: a real sculpted body and face (subdivided, smooth shading, bevelled armour edges, sculpted chest /
abdomen on the cuirass, hair in big sculpted locks), and wings made of hundreds of individual feathers. Triangle
budget for Gabriel: **up to 90k** (Pixel 8 runs Ruth's ~76k set + 3 × 24k cast; this pack has one actor and a simpler
set). Set budget: 45k.

Other sessions work in the same repo (Exodus / Prodigal, Esther). Touch only your own files; shared files additive
only, re-read right before an edit. Disk is tight (~12 GB): scratch in `/tmp/gabriel_<role>/`, delete when done.

## 1. Roles and file ownership

| Role | Owns |
|---|---|
| Story + Integration (lead) | `docs/gabriel/STORY.md`, `storyboard/story.py`, `STORYBOARD.md`, `assets/gabriel/timeline.json`, `assets/gabriel/{pack,faces}.json`, registry / library entries, Unity, builds, device |
| Character (Blender) | `pipeline/ga_character.py`, `assets/gabriel/model/gabriel.glb`, `characters.blend`, `preview_*.png`, `regions_characters.json`, `id_characters_2x.*`, `docs/gabriel/RIG.md`, `docs/gabriel/design/faces/` |
| Set + sheet (Blender) | `pipeline/ga_heaven.py`, `assets/gabriel/model/heaven.{glb,blend}`, `heaven_preview_*.png`, `set_id_2x.*`, `tools/story/sheet_gabriel.py` (new; `make_sheet.py` untouched), `assets/gabriel/sheet/`, `print/gabriel-A4.*` and `print/gabriel-A4-colored.pdf`, `assets/gabriel/design.json`, `docs/gabriel/SET.md` |
| Animation | `pipeline/ga_animate.py`, `assets/gabriel/anim/`, `docs/gabriel/ANIMATION.md` |
| Effects | `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxGabriel*.cs` (+ one registration line in `DGFxEffects.cs`), `Fx/Preview~` additions, `docs/gabriel/FX.md` |
| Music & SFX | `tools/story/music_gabriel.py`, `assets/gabriel/audio/music/`, `assets/gabriel/audio/sfx/`, `docs/gabriel/MUSIC.md` |
| Voice | `tools/story/cast_gabriel.json`, `tools/story/voice_gabriel.py` (new; `voice.py` untouched), `assets/gabriel/audio/voice/`, `docs/gabriel/VOICE.md` |

## 2. The character

| Id | Height | Sheet slot |
|---|---|---|
| `gabriel` | 0.62 (feet to crown); wingspan spread ≈ 1.0, wing tips up to ≈ 0.80 | sheetX 0.0, sheetY 0.015 (feet line), front projection, wings spread; the set drawings use the art rectangle above and around him |

## 3. Skeleton

Humanoid bones exactly as Daniel (`root hips spine chest neck head jaw shoulderL/R upperArmL/R forearmL/R handL/R
thighL/R shinL/R footL/R toeL/R fingersL fingersR eyelids`), rest pose = the sheet pose (A-pose arms, **wings
spread**), facing +Z. Extras:
- Wings, per side (from `chest`, behind the shoulder blades): `wingL1 wingL2 wingL3` (shoulder / forearm / hand of
  the wing) and `wingL_prim` (child of `wingL3`, fans the primaries open / closed by its scale or rotation) — same for
  `R`. Feathers are skinned so that folding (wing1-3 rotate back and down, prim closes) tucks the wing neatly behind
  the back without feathers crossing through the body; flapping is a believable down-stroke / up-stroke.
- `hair1 hair2` (back locks, from `head`), `sash1 sash2` (the hanging front sash end, from `hips`).
- Props: `trumpet` (child of `handR`, hidden by default, mouthpiece near the lips when `handR` is at the mouth in
  `blow_trumpet`), `sword` (child of `hips`, sheathed at the left hip, always shown). Prop rule as before: node
  `gabriel_trumpet` under bone `trumpet`.

Faces: decals on UV1 as Daniel, one PNG per expression in `docs/gabriel/design/faces/gabriel_<expr>.png`
(DESIGN.md list), blink via `eyelids` (lids on the eye surface — the Daniel lion lesson).

## 4. Animation clips (names are the contract), actions `gabriel_<clip>`

| Clip | What |
|---|---|
| `idle` (loop) | standing, breathing, wings half-open and gently breathing, sash and hair drift, blinks |
| `hover` (loop) | in the air high above the page (root raised ≈ 0.55), slow powerful flaps, legs relaxed |
| `fly_down` (one-shot, ends standing, wings open) | from hover height comes down in 4-5 s with 3 big slow flaps, flares the wings to brake, lands softly on the page (feet planted at the end) |
| `fold_wings` (one-shot hold) | folds the wings behind the back with a little shake of the feathers |
| `walk` (loop) | calm noble walk, wings folded |
| `kneel_talk` (loop) | goes down on one knee and talks warmly with hand gestures (knee on the page, meshMinY ≥ -0.008) |
| `stand_up` (one-shot) | from the kneel to standing |
| `talk` (loop) | standing talk with open, generous gestures |
| `point_up` (one-shot hold) | right arm points up to heaven, looks up then back at the child |
| `raise_trumpet` (one-shot hold) | lifts the trumpet high, proud smile |
| `blow_trumpet` (loop) | trumpet at the lips, bell up-forward; big breath, body leans, wings flare open with each phrase |
| `spread_wings` (one-shot hold) | majestic full spread, chest up, arms slightly out |
| `bless` (loop) | hand on heart then open palm toward the viewer, kind |
| `wave` (loop) | friendly wave, wings half-open |
| `fly_up` (one-shot, ends off the top) | crouch, spring, 3 flaps, rises and leaves upward (root to ≈ 1.2 high) |

Loops seamless; one-shots end in blendable holds; talk clips move `jaw`; secondary motion on wings (feather lag),
hair, sash. In-clip vertical travel is on `root` (the director does not add height for this pack).

## 5. Timeline: as Daniel §5 (`tools/story/build_timeline.py gabriel`).

## 6. Set (`assets/gabriel/model/heaven.glb`, root node `heaven`)

Floor x ±0.60, z −0.5875…0.21. Nodes: `clouds` (the cloud floor, top ≤ 0.04 in the centre stage x ±0.35, z −0.30…0.21,
up to 0.10 at the edges), `gate` (back centre, wall front face z ≈ −0.50, top h ≤ 0.42, arch, rosette glow node
`gateGlow`, 5 steps down to z ≈ −0.36), `islandL` (≈ (−0.45, −0.30), floating 0.18-0.28 high), `islandR`
(≈ (0.45, −0.28)), `frontClouds` (puffs at the front corners, x beyond ±0.40). Looping action `cloudDrift` (slow, 8 s,
seamless) allowed on `clouds`. **Keep clear:** the centre stage (x ±0.30, z −0.20…0.21) and the wing sweep (nothing
above 0.04 within x ±0.55 of (0, 0.02) at z −0.15…0.20). UV0 = the colouring sheet, as Daniel's set.

## 7. Audio

Voice −16 LUFS, music −20 LUFS, SFX peak −3 dBFS, 44.1 kHz mono WAV + 96 kbps MP3. Cues:
`heaven descend gentle story fanfare finale` (`cues.json` with loop points). SFX: `wing_flap wing_fold whoosh_land
trumpet_call choir_ah sparkle`. `trumpet_call` = the Gabriel theme on a bright herald trumpet (≤ 5 s).

## 8. Effects ids

Reused: `sparkle`, `golden_rays`, `heart_glow` (Ruth). New: `heaven_rays` (stage: god rays from the gate glow
through haze, slowly moving, loop), `cloud_drift` (stage: low cloud wisps drifting across the page, loop),
`descend_light` (a column of warm light on a node from above, for the landing), `feather_fall` (white feathers
tumbling and swaying down from a node or the stage), `wing_gust` (ring of cloud puffs pushed out on the page at a
node), `trumpet_notes` (golden musical notes and soft sound rings streaming from the trumpet bell).
