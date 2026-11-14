# Daniel — art direction

Same family as Esther and Ruth (`docs/esther/DESIGN.md`, `docs/ruth/DESIGN.md`): Paper & Crayon look, rounded
readable shapes, the same head-to-body ratio, line weight and face style. Every colourable region is a closed shape at
least 6 mm across on the A4 print (Haman's feathers and collar were below that: do not repeat it). Period: Babylon
under the Persian king Darius (6th century BC). All designs are original; the reference viewing only told us the
costume logic, the set's furniture and the light per scene.

Quality bar (owner, 2026-11-13/14): David's set was "average", lines stiff, voices "like AI". Esther and Ruth raised
the bar; Daniel must be at least Ruth's level: faces with life, cloth that hangs and moves, a set that feels like a
real place with many small details, and **lions a child will love** (big soft mane, round muzzle, expressive eyes,
never realistic-scary).

## Characters

### Daniel (the hero)
- A grown man about forty (not old, not a boy): long **dark-brown** hair tied back at the nape, short neat beard,
  kind eyes, straight eyebrows that lift when he smiles.
- Long **white / cream** linen robe to the ankles, short sleeves over long under-sleeves; a broad **gold** collar
  (yoke) with a simple woven pattern drawn as a few big bands (each band ≥ 6 mm); a **teal-blue** sash at the waist
  with a hanging end; brown sandals.
- Expressions: `calm`, `talk`, `smile`, `pray` (eyes closed, peaceful), `sure` (gentle, determined), `joy`.
- Regions: skin, hair+beard, robe, collar, sash, sandals.

### King Darius
- Tall and broad, round belly, big **black curly beard** in rows of curls and a curly moustache, thick eyebrows that
  carry every mood (proud, worried, sorry, overjoyed).
- Tall **purple** cylindrical crown-hat with a **gold** band and a row of small gold studs; long **lavender / purple**
  robe; a **deep-blue** cape over the shoulders; a big round **gold** medallion with a star on the chest; gold belt;
  gold signet ring on the right hand (`ring` prop, follows Esther's `king/ring`).
- Expressions: `smile`, `talk`, `proud` (chin up, eyes half closed), `worried`, `sorry` (brows up in the middle, close
  to tears), `tired` (bags under the eyes, for S10), `joy`.
- Regions: skin, beard, crown, crown band, robe, cape, medallion, belt, shoes.

### The jealous official
- Thin and tall-ish, long narrow face, pointy nose, a thin pointed black beard and a twirly moustache, narrow eyes
  that squint when he schemes; a **burnt-orange** robe with **red** stripes at the hem, a **gold** headband, a
  **green** sash, curly-toed slippers. Comic, never menacing: think sulky cat, not monster.
- Prop `scroll` (the law, a cream scroll with a red seal), child of `handR`.
- Expressions: `sulky`, `talk`, `sly` (one eye half shut, smirk), `flatter` (big fake smile), `gleeful`, `scared`
  (eyes huge, mouth wide), `nervous`.
- Regions: skin, beard, headband, robe, stripes, sash, slippers.

### The lion (on the sheet)
- A big friendly lion, quadruped, standing height to the shoulder ≈ 0.16, nose to tail-tip ≈ 0.42. Big round **mane**
  in chunky tufts (separate colour region), **golden** body, **cream** muzzle and belly, dark tail tuft, round ears,
  big amber eyes with clear pupils and eyebrows (so it can look sleepy, fierce, surprised, blissful).
- Expressions: `sleepy`, `fierce` (roar: mouth wide, teeth as soft white bumps, no fangs dripping), `curious`,
  `blissful` (eyes closed, smile, for the purr).
- Regions: body, mane, muzzle, tail tuft, nose.

### The lioness (`lion2`, not on the sheet)
- Same rig and proportions, no mane, slimmer neck, **sandy** coat with a cream muzzle, own painted texture
  (`assets/daniel/model/lion2_paint.png`), like Esther's guards.

## Set: Babylon (`babylon`)

From back to front on the page:
- **City wall** backdrop (relief across the back): mud-brick with crenellations, one big **blue-glazed gate** with
  original rosette and walking-lion relief bands (Ishtar-gate style, historical pattern, our own drawing), a hint of
  flat roofs and two date palms beyond.
- **Palace front** (back centre): a raised dais with three steps, two columns with palm-leaf capitals, a cloth canopy,
  a carved **throne**, a blue-tiled frieze; a wall **torch** on a pole (flame point `torch`).
- **Daniel's house** (back left): two-storey mud-brick house, an outside stair to the roof, wooden door, a small
  balcony; at the front left a short **window wall** with an arched lattice window that faces the left edge (west,
  toward Jerusalem), and a woven **prayer rug** in front of it.
- **Market corner** (front left edge): a little stall with a striped awning, pomegranates, melons, jars (keep the
  official's escape path clear).
- **Date palm** (middle left, the official's hiding place) and two more palms by the palace.
- **Lions' den** (middle right): a round sunken-looking enclosure of big stone blocks (wall top h ≈ 0.075, so the camera
  sees in), sandy floor with straw, two flat rocks for the lions to lie on, a water trough; the opening faces front-
  left; the **big round stone** beside it (`stoneOpen`) and a second copy across the opening (`stoneShut`, hidden
  until S08) with a cord and a red wax **seal** (`seal`, hidden until S08). No bones.
- **Courtyard**: big paving stones across the front, a few cracks and tufts, warm sand at the edges.

## Demo colouring

| Region | Colour | Hex |
|---|---|---|
| Daniel robe / collar / sash | cream white / gold / teal | `#F4EEDD` / `#E2B33C` / `#2F8F9D` |
| Daniel hair+beard / sandals | dark brown / brown | `#4A2E1F` / `#8A5A3B` |
| King robe / cape / crown | lavender / deep blue / purple | `#9E86C8` / `#3B4F9A` / `#6E4FA8` |
| King crown band / medallion / belt | gold | `#E8B84A` |
| King beard | near-black | `#2A1E1A` |
| Official robe / stripes / headband / sash | burnt orange / red / gold / green | `#D9773A` / `#B83A2E` / `#E8B84A` / `#5E8F3E` |
| Official beard | black | `#231A16` |
| Lion body / mane / muzzle / tail tuft | golden / rust-brown / cream / dark brown | `#E2A94A` / `#A8562A` / `#F3E2B8` / `#5A3420` |
| Lioness (fixed) | sandy / cream | `#D9B47A` / `#F1E3C4` |
| City wall / gate tiles / reliefs | mud-brick / lapis blue / gold | `#D8B07A` / `#2E5FA8` / `#E8C15A` |
| Palace columns / canopy / throne | sandstone / red / gold | `#E3CFA3` / `#B8423A` / `#D9A63A` |
| House walls / door / rug | warm adobe / brown wood / red + blue | `#D9A06A` / `#8A5A3B` / `#B8423A`, `#2E5FA8` |
| Den stones / floor / straw | grey-brown / sand / straw | `#9C8A72` / `#D9B77A` / `#E9D08A` |
| Palms | green / brown | `#4F8A3C` / `#8A6A44` |
| Paving | pale stone | `#E6D6B4` |

## Light and mood per part
- S01-S04 bright warm morning, clear blue-ish sky light, crisp shadows.
- S05 soft warm afternoon light through the window (`prayer_glow` on Daniel).
- S06-S07 the same afternoon, then `tension_dim`.
- S08 sunset orange (`sunset_glow`).
- S09 night: deep blue, stars, then the warm-white `angel_light` column inside the den.
- S10 night, one warm torch (`lamp_flame` on `torch`).
- S11 pink-gold dawn (`dawn_glow`), S12-S13 bright morning, golden rays, confetti.

## Music direction (original score)
Reference mood: warm cinematic orchestra with Middle-Eastern colour (oud-like plucks, ney/duduk-like reed, frame drum,
harp), a choir pad for the angel. All original, with a recurring **Daniel theme** (a calm, rising 5-note prayer motif):
- `babylon` grand opening: frame drum, low brass-like pad, harp runs, the Daniel theme on a reed.
- `king_friend` warm, stately strings; a cheerful lilt.
- `scheme` comic-sneaky: bassoon-like low reed, pizzicato, a woodblock; ends on a "dun-dun".
- `decree` pompous mini fanfare and drum roll; a little silly.
- `prayer` hushed harp and a single flute on the Daniel theme.
- `trouble` tense low strings, a slow heartbeat drum.
- `den` dark low drums and a sustained string tremolo, building (never horror-loud).
- `angel` choir pad and harp shimmer; the Daniel theme in major, glowing.
- `sleepless` comic-sad: plodding bassoon, a ticking clock, sighing slides.
- `dawn_run` quick bright strings and running drum.
- `rescue` joyful full ensemble, the theme triumphant.
- `finale` warm full statement of the theme, ends on a held chord.
