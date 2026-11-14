# Exodus — art direction

Same family as David & Goliath, Esther and Ruth (`docs/ruth/DESIGN.md`): Paper & Crayon look, rounded readable shapes,
the same head-to-body ratio, line weight and face style. Every colourable region is a closed shape at least 6 mm across
on the A4 print. Period: New Kingdom Egypt and the Sinai wilderness. All designs are original.

Quality bar (owner, 2026-11-14, same as Ruth): the set must feel like a **place** with many small believable details,
faces with life, cloth that hangs and moves, voices that sound like people. This page holds the most "wow" of any pack
so far: **the sea standing up in two walls** is the hero moment; spend effort there.

## Characters

### Moses (the hero)
- About eighty but strong: **white** hair to the shoulders and a long full **white beard** (two-bone beard tip that
  sways), bushy white eyebrows that carry his expressions, kind crinkled eyes, sun-browned skin.
- A long **cream / undyed wool** tunic; over it a heavy **shepherd's mantle** in broad vertical stripes of
  **ochre-brown and dark brown** (two colourable stripe regions) that hangs from the shoulders to mid-shin and swings;
  a twisted **rope belt**; simple sandals.
- A tall gnarled **shepherd's staff** with a crook-knot at the top, as tall as he is (prop `staff`, child of `handR`).
- Expressions: `calm`, `talk`, `curious`, `amazed` (eyes wide, brows high), `worried` (brows tilted, mouth wobbly),
  `scared` (comic: eyes huge, mouth open), `brave` (brows down, firm smile), `pray` (eyes closed), `joy`.
- Regions: skin, hair+beard, tunic, mantle stripe A, mantle stripe B, belt, sandals, staff.

### Pharaoh (the comic villain)
- Younger, tall, thin, chin up; the royal striped **nemes head-cloth** with lappets on the shoulders (broad stripes of
  **lapis blue and gold**, two regions), a small **cobra** ornament on the brow; a broad **collar** necklace (bands of
  turquoise, gold, red); bare chest and arms with gold arm-bands; a pleated white **kilt** with a red-and-gold apron
  sash; gold sandals; dark kohl-lined eyes, thin raised eyebrows, a pointed false **beard** (gold, small).
- Character: vain and theatrical, Esther's Haman in Egyptian dress. Big gestures; sulks; stamps; when soaked his
  head-cloth droops flat (`soggy` clip lowers the lappets by bone).
- Expressions: `smug`, `talk`, `laugh`, `angry` (comic: cheeks puffed), `shock`, `scared`, `sad` (S07; real sorrow,
  not comic), `sneaky`, `soggy` (half-closed eyes, drippy, mouth pulled down).
- Bones beyond the humanoid set: `nemes1L nemes1R` (the lappets), `nemesBack` (the tail of the head-cloth).
- Regions: skin, nemes stripe A, nemes stripe B, collar, kilt, sash, arm-bands, sandals; prop `chariot`.
- Prop `chariot`: small golden two-wheeled chariot he stands in (child of `root`, hidden by default): a curved front
  with a sun disc, two six-spoke wheels (`wheelL` separate node so it can drop off), a short pole.

### Miriam (Moses's sister)
- A grown woman, lively and quick (younger looking than Moses, though in the story she is older; keep her about
  forty-five, never elderly); dark **brown** hair in a thick braid showing under a **teal** head-scarf;
  a long **saffron-yellow** dress with a **rust-red** woven belt-band and a little embroidered border at the hem
  (region); bead **necklace**; bare feet or simple sandals.
- Prop `tambourine` (child of `handL`, hidden until S13): wooden frame drum with little metal discs and ribbons.
- Expressions: `calm`, `talk`, `sad`, `pray`, `worried`, `scared`, `wow` (open delighted mouth), `joy`, `sing`.
- Bones beyond the humanoid set: `scarf1 scarf2` (scarf tail), `braid1 braid2`.
- Regions: skin, hair, scarf, dress, belt, hem border, necklace; prop `tambourine` (frame, ribbons).

## Set: Egypt and the sea (`egypt`)

From back to front on the page:
- **Backdrop** (low relief across the back): sand dunes with two **pyramids** behind the palace (left half) and the
  rocky **mountain** (right half, reddish rock, a few dry bushes, a ledge path).
- **Pharaoh's palace** (back left): a short colonnade of four fat **papyrus columns** with lotus capitals, a lintel
  with a winged sun disc, a stepped **dais** with a gilded **throne**, two tall **obelisks** or seated statues at the
  sides (original, simple), two **palm** trees.
- **The Nile** (left edge, front to back): a blue river band with papyrus **reeds**, lotus leaves and a small
  reed boat. The river turns red during the plagues (an FX tint), then back.
- **Brick yard** (middle left): stacks of mud **bricks** (individual blocks), wooden brick **moulds**, a **straw**
  pile, a water **trough**, a half-built wall with a ramp. A **crowd** of small simple Israelite workers here (`crowdWest`).
- **Israelite houses** (back centre): two small flat-roofed mud-brick houses with dark doorways; `doorMarks` are red
  painted marks on the lintels and door-posts (hidden until S07; they glow softly at night).
- **The burning bush** (centre-right, at the mountain's foot on a little rocky rise): a thorny acacia bush with no
  leaves to colour except a few; flame point `bushFlame`.
- **The sea** (right third, a band from back to front): deep blue-green water with gentle ripples, a pale beach strip
  on each side. Two **water walls** (`seaWallBack`, `seaWallFront`) lie hidden in the sea-bed and rise when the sea
  parts; when they rise, the sea surface (`seaWater`) opens along the crossing lane and shows the wet sand
  sea-bed (`seaBed`) with a few shells and pebbles.
- **Far shore** (right edge strip): pale sand, three palms, rocks; a hidden `crowdFar` (the people safe on the other
  side) and a hidden `pillar` (a soft cloud column that becomes a fire column at night; Effects drive it).
- Hidden props: `doorMarks` (S07), `crowdShore` (people waiting on the west beach, S10), `crowdFar` (S12-S14),
  `looseWheel` (Pharaoh's wheel lying in the sea-bed, S12).

## Demo colouring (the sample the app ships)

| Region | Colour | Hex |
|---|---|---|
| Moses tunic / mantle A / mantle B / belt | cream / ochre / dark brown / rope | `#F1E6CC` / `#C98B3A` / `#6B4426` / `#B89466` |
| Moses hair + beard / staff | white / gnarled wood | `#F4F1EA` / `#8A5E3A` |
| Pharaoh nemes A / B / collar | lapis / gold / turquoise | `#2F5DA8` / `#E8B83A` / `#3FB8AF` |
| Pharaoh kilt / sash / arm-bands | white / red / gold | `#FBF8EF` / `#C2413A` / `#E8B83A` |
| Miriam dress / scarf / belt / hem | saffron / teal / rust / blue | `#F2B33D` / `#2E9C9A` / `#B5532E` / `#3E6FB0` |
| Miriam hair / necklace / tambourine | dark brown / coral / wood | `#4A2E1F` / `#E86A5A` / `#B07A47` |
| Palace stone / columns / gold trims | sandstone / pale limestone / gold | `#E3C998` / `#EFE0BE` / `#E0B13A` |
| Pyramids / dunes / mountain rock | sand gold / warm sand / red rock | `#E2BE7A` / `#EBD3A0` / `#B5643F` |
| Nile / reeds / lotus | blue / green / pink | `#3E8FC4` / `#6FA24A` / `#F4A6B8` |
| Bricks / straw / trough | mud brown / straw / wood | `#A9673F` / `#E9D08A` / `#8A5E3A` |
| Houses / door marks | mud plaster / red | `#C99A6B` / `#C2413A` |
| Bush / bush leaves | dark wood / dusty green | `#5E4330` / `#8FA876` |
| Sea / sea walls / sea-bed | blue-green / turquoise / wet sand | `#2C7FA8` / `#4FB3C9` / `#C8A97A` |
| Palms | green / trunk brown | `#4F8A3C` / `#8A6A44` |

## Light and mood per part
- S01 hot hazy noon, dusty; S02-S04 dusk in the wilderness, warm orange sky then violet (`sunset_glow`, the bush
  glows white-gold with a soft violet halo: the flame never looks dangerous).
- S05-S06 bright palace gold; S06 the river tints red for a few seconds, then back.
- S07 deep blue night (`night`), the door marks and house windows glow warm; the palace is dark.
- S08-S10 cool clear morning; the cloud pillar glows softly.
- S11 wind: dust and spray streaks, a deep blue night-to-dawn shift (14:21 "all that night"), the sea walls glow
  inside with caustics and a few fish silhouettes.
- S12 dawn; big splash; then calm.
- S13-S14 bright morning, sparkles on the water, golden rays.

## Music direction (original score)
Reference mood: warm cinematic orchestra with Middle-Eastern / Egyptian colour (ney-like flute, oud plucks, frame
drum, darbuka, low strings, brass for the palace). Our cues are original compositions in that spirit, with one
**"freedom theme"** (a rising 5-note figure in D Phrygian-dominant → D major) that returns in S08, S11 and the finale.
- `slavery` D minor, heavy slow work rhythm on low drum + low strings, a sad ney line; a hammer-like accent per bar.
- `desert` A minor pastoral, solo flute over a drone, sheep-bell tinkles, wide and quiet.
- `bush` held shimmering strings + soft choir pad + glass harmonics; no beat; awe, not fear.
- `palace` pompous comic march: brass fanfare, big drum, slightly too grand (Pharaoh's theme, swaggering bassoon).
- `plagues` comic-tense pizzicato in Phrygian, woodblock "frog hops", quick stings for each plague.
- `passover` hushed night: harp arpeggios, a soft pad, a lone flute playing the freedom theme slowly.
- `exodus` joyful walking march: frame drums, handclaps, oud, the freedom theme in D major.
- `chase` urgent drums and low brass ostinato, Pharaoh's theme twisted minor.
- `sea` the big one: rising strings and choir, building over the parting, a full statement of the freedom theme when
  the walls stand.
- `song` Miriam's dance: tambourine, darbuka, clapping, a singable melody for her chant (6/8).
- `finale` warm full statement of the freedom theme, ends on a held chord.
