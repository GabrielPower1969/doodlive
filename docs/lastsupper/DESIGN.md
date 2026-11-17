# The King Who Serves — art direction (costume, make-up, props, set, light, music)

Same family as Ruth, Daniel, Jonah and Real Miracles: Paper & Crayon look, rounded readable shapes, decal faces, same
head-to-body ratio. **Every colourable region is a closed shape ≥ 6 mm on the A4 print.** Small parts (sandals, cords,
eyes, hooves) are fixed-colour detail lines, not regions. All designs are original; the reference viewing lent only the
logic below (Jerusalem limestone, a colonnaded temple court with traders' tables and dove cages, a lamp-lit upstairs
room with a low table, a basin and a towel).

Period: about AD 30, the week of Passover. Jerusalem.

## 1. Characters

### Jesus — height 0.36 (identical to Real Miracles)
- **Face, hair, costume, regions, colours: exactly `docs/miracles/DESIGN.md` §1 and §3** (cream tunic, warm brown
  mantle, tan belt, dark-brown hair and beard). The two packs must look like the same man.
- **New props** (hidden by default): `towel` (a white linen towel wrapped round the waist and tucked in, ends hanging at
  the right hip; child of `hips`), `basin` (a shallow terracotta bowl with water, 0.08 across; child of `root`, sits on
  the floor 0.06 in front of Him in the kneeling clips), `bread` (a round flat loaf, child of `handL`), `cup` (a plain
  clay cup with a foot, child of `handR`).
- **Expressions**: the Miracles drawings `kind` (default), `talk`, `smile`, `laugh`, `firm`, `gentle`, `look_up`, plus
  one new: `sad` (soft eyes, inner brows raised, mouth closed: the noisy temple). `sleep` is not used here.
- **Regions**: skin, hair+beard, tunic, mantle, belt (the towel, basin, bread and cup are not on the sheet; CONTRACT §3).

### Peter — height 0.38 (identical to Real Miracles)
- **Face, hair, costume, regions, colours: exactly `docs/miracles/DESIGN.md` §1 and §3** (rust-red tunic, sand vest,
  dark-brown waist cloth, blue-grey head cloth, curly black hair and beard).
- **Props** (all hidden except `palm` in S01-S03): `palm` (a green palm frond as tall as his arm, child of `handR`),
  `towel` (the same white towel draped over his left shoulder, child of `chest`), `jug` (a terracotta water jug with one
  handle, child of `handR`). The Miracles `bucket` bone stays in the skeleton with no mesh, so both packs share one rig.
- **Expressions**: from Miracles `jolly` (default), `talk`, `shock`, `laugh`, `amazed`; new: `proud` (chin up, smug
  grin, half-closed eyes), `sheepish` (eyes down and aside, a wobbly smile), `puzzled` (one brow up, mouth pushed to one
  side).
- **Regions**: skin, hair+beard, tunic, vest, waist cloth, head cloth.

### The donkey — withers 0.15, ear tips 0.27, nose to rump 0.28 (+ tail 0.06)
- A **young, small, round** donkey: big head, very long upright ears with dark tips, a soft cream muzzle and belly, a
  short dark mane standing up like a brush, a thin tail with a dark tuft, short sturdy legs with dark hooves. Big kind
  eyes with long lashes. Never a horse silhouette: short legs, big head, big ears.
- **Costume**: a **saddle blanket** folded over its back (a simple rectangle hanging to mid-belly on both sides, with a
  fringe line), on which Jesus sits.
- **Expressions**: `calm` (default, eyes half-lidded), `happy` (eyes curved), `heehaw` (eyes squeezed shut, nostrils
  wide; the jaw opens), `chew` (grazing, eyes down), `sleepy`.
- **Regions**: coat (body, head, legs, ears outside), muzzle (muzzle, eye rings, belly patch, inner ears where ≥ 6 mm),
  mane (mane, tail tuft, ear tips; if the ear tips are < 6 mm they take the mane colour as fixed detail), blanket.
  Hooves are a fixed dark detail line.

### The other three disciples (not on the sheet; fixed paint, Esther's guards / Miracles friends precedent)
Three silhouettes a child can tell apart; all with tan belts and sandals.
- `john` — 0.33, the youngest: beardless, round face, short wavy **light-brown** hair, a **sky-blue** tunic, a white sash.
- `james` — 0.36, John's big brother: broad, short **black** beard and hair, a **leaf-green** tunic with a **brown**
  short cloak over one shoulder (stands straight, chest out).
- `andrew` — 0.37, Peter's little brother: lanky and thin, a narrow face, Peter's **curly black** hair but a short
  neat beard, a **mustard** tunic and **the same blue-grey head cloth as Peter** (family look).
Expressions shared: `happy` (default), `talk`, `proud`, `amazed`, `sheepish`, `laugh`.

### The two sellers (not on the sheet; fixed paint)
- `seller1` — the dove seller, 0.33: round, bald with a black fringe, rosy cheeks, an **orange** tunic and a
  **cream-and-brown striped apron**.
- `seller2` — the money changer, 0.35: thin and long-nosed, a little pointed beard, a tall **felt cap**, a **plum**
  robe, a fat **money pouch** at the belt.
Expressions shared: `hawk` (default: big salesman smile), `talk`, `shock` (eyes huge), `wail` (mouth wide, brows up),
`fluster`. Comic, never mean-looking.

## 2. Set: `jerusalem` (one page, three places)

Front = the road into the city. Right back = the temple court. Left back = the house with the upstairs room.

- **Road** (`road`): packed pale earth from the front-right edge, running left along the front of the page to a bend in
  front of the court gate, then on to the front of the house. Along its back edge (between the road and the court
  wall) and at the right end: **the crowd** `crowd1`…`crowd8` (fixed-colour townsfolk and two children, height ≤ 0.28,
  each holding a palm frond; a looping `crowdSway` ±4°, palms swaying). `palmsRoad` (hidden at start): palm branches
  and **colourful coats** laid along the road (a flat layer, h ≤ 0.008). `stones`: a small heap of five round roadside
  stones at the bend (h ≤ 0.03), the ones Peter talks to.
- **Temple court** (`temple`): a paved court of **cream limestone** behind a low front wall (h ≤ 0.04) with a gate gap;
  at the back a **colonnade** (four round columns) and, behind it, the gleaming **temple front** (white stone, gold trim
  on the cornice, a tall bronze-coloured door) as a relief across the back right. Inside the court: `table1` (the dove
  seller's table with `cages`, three stacked wicker cages with white doves; `cagesOpen` = the same cages with doors
  open, empty, hidden), `table2` (the money changer's table with neat coin stacks and a little scale; `table2Tipped` = on
  its side, legs toward the back, hidden), `coinsFloor` (scattered coins on the paving, hidden), two **striped awnings**
  on poles at the back of the stalls (above head height, never in front of faces).
- **House** (`house`): a two-storey limestone house; the ground storey is closed (a wooden door, a window); the
  **upstairs room** sits on it and is a **doll's house**: its front wall is cut away to a low sill so the room is seen.
  Inside: a long **bench** along the left wall with cushions, a **low table** (`lowTable`) with a white cloth, a round
  flat loaf (`breadLoaf`), a clay cup (`cupTable`), a dish of herbs, a bowl of fruit; a **basin stand** (`basinStand`)
  in the back-right corner with a jug and a basin on it (`basinJug`); two **oil lamps** (`lamp1` in a wall niche,
  `lamp2` on the table); woven floor mats; a window in the back wall showing night sky. An **outside stair** up the
  house's right wall (decor; nobody walks it).
- Between the house and the court: a narrow lane with a **palm tree** at the back (behind the action) and an olive tree.
- Far back: the **Mount of Olives**, low olive-green hills, along the back edge on the left above the house.

## 3. Demo colouring

| Region | Colour | Hex |
|---|---|---|
| Jesus, Peter | exactly as `docs/miracles/DESIGN.md` §3 | — |
| Donkey coat / muzzle / mane / blanket | soft grey / cream / charcoal / red with gold | `#9C9A96` / `#EFE6D2` / `#3E3A38` / `#C2453A` |
| John tunic / sash / hair (fixed) | sky blue / white / light brown | `#7FB6E0` / `#F5F1E6` / `#9A6B42` |
| James tunic / cloak (fixed) | leaf green / brown | `#6FA552` / `#7A5236` |
| Andrew tunic / head cloth (fixed) | mustard / blue-grey | `#D9A93A` / `#6E8AA6` |
| Seller1 tunic / apron stripes (fixed) | orange / cream + brown | `#E8843A` / `#F1E3C4` + `#8A5A3B` |
| Seller2 robe / cap (fixed) | plum / dark red | `#7E4A86` / `#9C3A3A` |
| Road / palm branches / coats on the road | pale earth / green / red, blue, yellow | `#E8D5A8` / `#5E9A48` / `#C2453A`, `#4E7FB8`, `#E8C04A` |
| City and house stone / roof edges | warm limestone / darker stone | `#E9D6A8` / `#C9B285` |
| Temple front / gold trim / door | white stone / gold / bronze | `#F4EEDD` / `#D9A93A` / `#A8743E` |
| Court paving / columns | cream / white | `#EADFC4` / `#F2ECDD` |
| Tables / cages / awnings | brown wood / wicker / red-and-cream stripes | `#8A5A3B` / `#D2AE74` / `#C2453A` + `#F1E3C4` |
| Room inside wall / floor mats / bench cushions | warm plaster / straw / dark red | `#EBD2A6` / `#D8BE8E` / `#9C3A3A` |
| Low table cloth / bread / cup, jug, basin | white / golden brown / terracotta | `#F5F1E6` / `#C98A4A` / `#C46A3E` |
| Palm tree / olive tree / hills | green + brown / grey-green / olive green | `#5E9A48` + `#7A6650` / `#8AA06A` / `#8E9E62` |

## 4. Light and mood per shot

| Shots | Light | Effects |
|---|---|---|
| S01-S03 | bright spring morning, warm sun, long soft shadows | `palm_toss`, `dust_road`, `sparkle` (the stones) |
| S04 | midday, hot and busy; a little hazy in the court | — |
| S05 | the same; after the tables, a clean warm light on Jesus | `coins_spray`, `doves_fly`, `golden_rays`, `music_notes` (children singing) |
| S06 | golden-orange evening in the room | `sunset_glow` |
| S07-S12 | night, deep blue outside; inside warm amber from two oil lamps | `night`, `lamp_flame` ×2, `water_pour`, `heart_glow` (the cup) |
| S13 | night over the whole page; the lit room glows | `golden_rays` on the house |

## 5. Music (original score; warm acoustic band with a Jerusalem colour: oud, frame drum, flute, harp, strings, children's voices "ah")

Two themes: the **King theme** (a bright, marching 4-bar tune on trumpet-like flute and frame drum: the procession) and
the **servant theme** (the same melody slowed, in a lower, gentler key on solo flute and harp: the towel). The finale
plays them together.

| Cue | Character |
|---|---|
| `road` | morning journey, a donkey's clip-clop on woodblock under a light oud; the King theme hinted |
| `hosanna` | the King theme in full: drums, handclaps, tambourine, a children's "ah" choir |
| `stones` | comic: pizzicato tiptoe, a bassoon "hmm", one bright chime for the stone |
| `market` | busy and a bit too loud: fast oud, clinking percussion, a squawky shawm |
| `prayer_house` | a firm low string chord, then the King theme turned serious; ends tender with the children's choir |
| `argue` | squabble: three instruments interrupting each other (oud, clarinet, tuba), stop-start |
| `towel` | hush: the servant theme, solo flute over held strings and a single harp note per step |
| `not_my_feet` | comic: quick pizzicato for "Never!", a slide whistle up for "wash all of me!", a warm resolve |
| `serve` | the servant theme, warmer, strings joining |
| `supper` | very still and reverent: harp and soft strings, slow; no drums |
| `my_turn` | light and smiling: the servant theme played bouncy by the oud |
| `finale` | the King theme and the servant theme together, warm and full, ending on a bright held chord |

SFX: `crowd_far crowd_cheer hee_haw ding market_bustle coins_clink table_tip coins_scatter dove_flutter water_pour
splash_small` (see CONTRACT §7).
