# Saul Sees the Light! — effects

Owner: Effects role ([CONTRACT.md](CONTRACT.md) §8, [DESIGN.md](DESIGN.md) §4). Engine and look rules: same as the
earlier packs ([../risen/FX.md](../risen/FX.md)). Code: `unity/Assets/DoodLive/DavidGoliath/Fx/StoryFxSaul.cs`, class `SaulFx`.

**Not rendered.** No Unity and no preview contact sheet this time: the code was written against the APIs in
`DGFxCore.cs`, `DGFxEffects.cs`, `StoryFxEsther.cs` (StoryLight) and `StoryFxGabriel.cs` (`DescendLight`), and read through
for compile errors only. Nobody has looked at it. Run `Fx/Preview~/run.sh saul` (needs a `SaulPreview.cs` stand-in) or look on the device.

## Ids

| id | Where it comes from |
|---|---|
| `night` `dust_road` `heart_glow` `lamp_flame` | Ruth |
| `angel_light` `sparkle` `zzz` | Daniel |
| `golden_rays` `dust_burst` | D&G |
| `prayer_glow` | Esther |
| `water_pour` | The King Who Serves |
| **`road_light` `scales_fall`** | new, `StoryFxSaul.cs`, class `SaulFx` |

No aliases (F1). Reason for building `road_light` instead of aliasing: `descend_light` is a column that follows a falling
angel and has no bloom; `truth_flash` is an ice-blue flash (cold, forbidden by DESIGN §4). `road_light` reuses `descend_light`'s
ribbon-column recipe and Esther's `StoryLight` dim, nothing else.

## Effects

- **`road_light`** (node `saul.root`, default 33 s, no follow: it stays on the spot where it started, the LIGHT mark).
  0-1.5 s one soft warm-white whole-frame bloom (a big additive sprite between camera and stage; up in 0.3 s, away by
  1.5 s; monotone, no second pulse, no cold colour). From 0.2 s (full by 1.4 s) a column from 1.8 above: a wide gold
  layer (0.27 at the ground), three slow amber / gold shafts, a bright warm-white additive core, a gold + white pool on
  the road (0.46 / 0.28), a soft halo behind Saul, and 16 gold motes falling (every third a slow sparkle). The rest of
  the stage is dimmed gently by posting 30 % (`SaulFx.DimShare`) of Esther's `StoryLight.DimStrength` (a deep-blue veil,
  about 13 % opaque): this is the only cold element; set `DimShare = 0` if it reads cold on the phone. Fades out over the last 1.5 s,
  and everything is gone at `dur`.
  **Face rule:** column, halo and motes stand 0.06-0.14 behind the node (away from the camera) so Saul and the guards cover
  them (depth-tested, as `DescendLight`); motes skip the head band (height 0.05-0.40, ±0.09 across). The only thing in front
  of the face is the 1.5 s bloom.
- **`scales_fall`** (node `saul.head`, 1.6 s, follows the head). 0-0.55 s: a small warm glow at the eyes (gone by 0.4 s) and five
  gold sparkles flying out. Eight pale silver flakes (outlined Pebble cell, dark ink edge, so they read on skin: F4) leave
  the two eyes alternately every 0.09 s from 0.05 s, drift outward 0.05-0.09 to the sides, fall 0.10-0.14 in 0.85 s, turn,
  glint once mid-fall and fade before the ground. Last one gone by 1.55 s. After 0.5 s none is in front of the eyes (they
  are to the side and below).

## Timing suggestions for the lead

| Shot | Call in `story.py` | Suggestion |
|---|---|---|
| S03-S04 | `fx("road_light", "saul.root", dur=32.7, dt=0.9)` | Right as written: the bloom (0.9-2.4 s) lands with `light_whoosh` and the fall (`fall_down` at 1.3). It ends at the S05 cut (F2). If the S03+S04 total changes after re-timing, set `dur` to cut − start. The column holds for ~30 s, so the breathing and falling motes are the only motion: if that feels static on the phone, shorten `dur` to end when Jesus finishes speaking. |
| S08 | `fx("scales_fall", "saul.head", dur=1.6, dt=0.2)` | Fine. Keep `heart_glow` clear of the eyes for the first 0.6 s. |

## Weak / unverified

- **Never seen.** Sizes assume art units like Gabriel's `descend_light` (ribbon width = full width; `Streak` cell soft-edged). If the column
  looks too thin or too wide, change `WTop` / `WBottom`.
- **Bloom size** assumes `FxBatch.Sprite` size is the full diameter and the camera field of view is under ~110°; at S03 (dist 0.7)
  it should cover the frame. It is depth-tested like any sprite: if the stage geometry hides part of it, nudge `0.6` toward 0.8.
- **Dim is blue.** Reused from Esther because there is no warm dim; at 30 % it is meant to be a soft dusk, check it is not cold.
- **`saul.head` anchor** is guessed to be the head centre: the eye offset (`up 0.012`, `toward camera 0.03`, ±0.02 across) may need tuning.
- Face band 0.05-0.40 assumes Saul 0.22 tall sitting plus the guard at 0.41; not measured on the final model.
