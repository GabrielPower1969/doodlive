# Ruth — art direction

Same family as David & Goliath and Esther (`docs/esther/DESIGN.md`): Paper & Crayon look, rounded readable shapes, the
same head-to-body ratio, line weight and face style. Every colourable region is a closed shape at least 6 mm across on
the A4 print. Period: Iron-Age Judah, barley harvest (April-May) at Bethlehem. All designs are original.

Quality bar (owner, 2026-11-14): "David's set modelling was average". This set must feel like a **place**: depth
(foreground stubble, mid field, background hills), many small believable details (stones in the wall, wood grain on
the door, a ladder to the flat roof, jars, a gnarled olive trunk), and readable silhouettes from the phone camera.

## Characters

### Ruth (the hero)
- Long **sage-green** dress (soft mint-green, not emerald) with three-quarter sleeves, gathered at the waist by a
  woven **brown** belt with a hanging tie; a **cream** head-scarf worn loosely over the head, falling over the
  shoulders and down the back (two-bone tail), dark brown hair showing at the front.
- Simple leather sandals; small bead bracelet (accent colour).
- Young, kind, slightly shy; big expressive eyes, soft eyebrows, a little blush.
- Expressions: `calm`, `sad`, `talk`, `shy`, `joy`, `pray` (eyes closed, soft), `brave`.
- Regions: skin, hair, dress, scarf, belt, bracelet, sandals; props `sheaf` (golden barley bundle), `stalks`.

### Naomi (older, Ruth's mother-in-law)
- Long **dusty-rose / mauve** robe with a **grey-blue** outer shawl that covers the head and wraps the shoulders
  (two-bone tail at the back); grey hair showing at the temples; a **wooden walking staff**.
- Slight stoop, kind smile lines, softer rounder face, small nose; she is about sixty, never frail-scary.
- Expressions: `sad`, `tired`, `talk`, `surprised`, `joy`, `tender`.
- Regions: skin, hair, robe, shawl, sash, staff, sandals; prop `baby` (swaddled in cream with a little face, own region).

### Boaz (owner of the field)
- **Olive-green** open outer robe (abaya, front panels hang and swing) over a **cream** long tunic; a **cream**
  head-cloth with a dark **olive/brown** cord band (agal); brown sash; full short dark-brown beard, warm eyes,
  laughing lines. Tall and broad, fatherly, a bit playful.
- Expressions: `smile`, `talk`, `curious`, `kind`, `sneaky` (one eyebrow up, grin), `laugh`, `joy`.
- Regions: skin, beard, hair, robe, tunic, headcloth, cord, sash, sandals; prop `stalks`.

## Set: Bethlehem at harvest (`bethlehem`)

From back to front on the page:
- **Hills** backdrop (low relief wall across the back): two rolling hill layers, a few **cypress** trees and round
  olive bushes, a hint of the town wall on one hill.
- **Naomi's house** (back left): rough stone block walls, flat roof with a parapet, a wooden **ladder** to the roof,
  a plank **door** with an arch lintel, a small window, two big clay **jars** by the door, a basket.
- **Threshing floor** (back right): a round stone-edged floor with a golden **grain heap**, a wooden winnowing
  **fork** leaning on it, an **oil lamp** on a stone (flame point `lampFlame`) and a few straw bundles.
- **Barley field** (middle right): rows of golden barley clumps (stylised: stalk bundles with drooping bearded ears),
  that **sway** in a looping wind; the front edge is cut **stubble** with two or three standing **sheaves**; a low
  dry-stone **field wall** on its left side.
- **Olive tree** (middle left): gnarled twisted trunk, round silver-green crown; three **water jars** in its shade.
- **Road** (front, left to centre): a pale dirt track with a few stones, coming in from the left edge (the road from Moab).
- Ground: warm ochre earth with tufts of grass and small stones (colourable patches).
- Hidden props: `dropped` (barley stalks lying where Boaz dropped them, S07), `canopy` (a wedding flower arch: two
  poles with a cloth top and flower garlands, centre front, S10).

## Demo colouring (the sample the app ships)

| Region | Colour | Hex |
|---|---|---|
| Ruth dress / scarf / belt | sage green / cream / brown | `#9CC5A1` / `#F3E9D2` / `#8A5A3B` |
| Ruth hair / bracelet | dark brown / turquoise | `#4A2E1F` / `#3FB8AF` |
| Naomi robe / shawl / sash | dusty rose / grey-blue / ochre | `#B98A9E` / `#8FA3B8` / `#D9A63A` |
| Naomi hair / staff | silver grey / wood | `#C9C4BE` / `#9B6B43` |
| Boaz robe / tunic / headcloth / cord | olive / cream / cream / dark brown | `#6E7F3A` / `#EFE3C8` / `#EDE2C6` / `#4B3A26` |
| Boaz beard / sash | dark brown / rust | `#3A2418` / `#B5532E` |
| Barley / stubble / sheaves | gold / straw / gold | `#E8B84A` / `#E9D08A` / `#E2A93B` |
| House stone / door / roof | sandstone / brown wood / clay | `#D9C29A` / `#8A5A3B` / `#C9A77A` |
| Olive tree crown / trunk | silver green / grey-brown | `#8FA876` / `#7A6650` |
| Hills near / far, cypress | warm green / blue-green / dark green | `#A7B86A` / `#8FA9A0` / `#3F6B45` |
| Road / ground | pale dirt / ochre | `#E9D9B6` / `#D9B77A` |
| Jars | terracotta | `#C8643C` |
| Wedding arch cloth / flowers | white / pink, yellow | `#FFFFFF` / `#F4A6B8`, `#F7D154` |

## Light and mood per part
- S01-S03 pale dawn, slightly cool, long shadows; dust on the road.
- S04-S07 bright warm morning; chaff drifting over the field.
- S08 golden-hour sunset glow (`sunset_glow`).
- S09 night: deep blue, stars, warm little oil-lamp light (`night`, `lamp_flame`).
- S10-S12 bright morning, petals, golden rays.

## Music direction (original score)
Reference mood: warm cinematic orchestra with Middle-Eastern colour (solo reed and flute over strings, frame drum,
plucked oud-like lines). Our cues are original compositions in that spirit:
- `road_sad` D minor, solo reed (duduk-like) over a low string pad, very slow.
- `journey` D Dorian walking ostinato (plucked), flute answers, hopeful.
- `field` G major pastoral, flute + plucked strings + light frame drum, morning birds feel.
- `boaz` warm strings, low clarinet-like melody, kind and steady.
- `sneaky` comic pizzicato tiptoe with a little woodblock, ends on a cheeky flourish.
- `home` golden-hour warmth, strings swell, the "Ruth theme" from S02 in major.
- `night` harp/plucked arpeggios, soft pad, a single flute line; hushed.
- `wedding` D major celebration: hand drums, tambourine, clapping, flute melody.
- `lullaby` music-box/harp 3/4 lullaby on the Ruth theme.
- `finale` full statement of the Ruth theme, warm and bright, ends on a held chord.
