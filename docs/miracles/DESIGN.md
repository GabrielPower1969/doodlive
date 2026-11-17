# Real Miracles — art direction (costume, make-up, props, set, light, music)

Same family as Ruth, Daniel and Jonah: Paper & Crayon look, rounded readable shapes, decal faces, same head-to-body
ratio. **Every colourable region is a closed shape ≥ 6 mm on the A4 print.** Small parts (sandals, cords, eyes) are
fixed-colour detail lines, not regions. All designs are original; the reference viewing lent only the logic below
(Galilean fishermen's clothes, a flat mud roof on beams, a wooden fishing boat with one mast, an evening lake).

Period: about AD 30. Capernaum on the north shore of the Sea of Galilee.

## 1. Characters

### Jesus — height 0.36
- **Face**: about thirty, kind open face, warm brown eyes, smile lines; shoulder-length wavy **dark-brown hair**
  parted in the middle, short full beard. Never pale or "glowing": an ordinary Galilean man.
- **Costume**: long **cream** tunic to the ankles with a V neck; a **warm brown mantle** worn over the left shoulder
  and wrapped round the waist (one big panel, front and back); a narrow **tan** cloth belt; sandals.
- **Expressions**: `kind` (default), `talk`, `smile` (open smile), `laugh`, `sleep` (eyes closed, peaceful), `firm`
  (brows level, mouth set: talking to the storm), `gentle` (soft eyes, small smile), `look_up` (eyes up).
- **Regions**: skin, hair+beard, tunic, mantle, belt.

### Peter — height 0.38
- **Face**: about thirty-five, broad, weathered, big nose, bushy brows, thick **curly black hair and beard**, laugh
  lines; very expressive (the comedy).
- **Costume**: knee-length **rust-red** tunic, sleeves rolled to the elbow; a short **sand-coloured** sleeveless
  over-vest; a thick **rope belt** (fixed colour, too thin to colour) with a **dark-brown** waist cloth under it; a
  **blue-grey** head cloth tied back (a band round the head, short tail); bare legs, sandals. Big forearms and hands.
- **Props** (hidden by default): `bucket` (a small wooden bucket, child of `handR`).
- **Expressions**: `jolly` (default), `talk`, `shock` (eyes huge, mouth wide), `wail`, `laugh`, `scared`, `amazed`
  (mouth open in wonder), `squint` (rain in his eyes).
- **Regions**: skin, hair+beard, tunic, vest, waist cloth, head cloth.

### The man on the mat — height 0.34
- **Face**: about twenty-five, thin face, big hopeful eyes, short **light-brown** hair, a scruffy short beard.
- **Costume**: a plain **pale green** tunic to the knee, a **mustard** waist sash; barefoot.
- **Props**: `mat` (his sleeping mat: a flat padded mat 0.30 × 0.12 with **two carrying poles** along the long
  sides that stick out 0.05 at each end, and four ropes at the corners that are hidden except in `lowered`; child of
  `root`; shown by default) and `matRoll` (the same mat rolled up with a cord, on his left shoulder, child of
  `chest`; hidden). The mat has **red-and-cream stripes**: the mat is its own sheet region (`mat`), the stripes a
  second region (`stripes`, each stripe ≥ 6 mm).
- **Expressions**: `shy` (default), `talk`, `nervous`, `hope` (looking up), `wonder` (gasp), `joy` (huge smile),
  `laugh`.
- **Regions**: skin, hair, tunic, sash, mat, stripes.

### The four friends (not on the sheet; fixed paint, Esther's guards precedent) — height 0.33-0.37
Four different silhouettes so a child can tell them apart: `friend1` the leader (slim, **orange** tunic, short black
hair, tall 0.35), `friend2` big and round (0.37, **teal** tunic, bald with a fringe, short beard), `friend3` small
and quick (0.33, **yellow** tunic, curly hair, a head band), `friend4` lanky (0.36, **purple-blue** tunic, a pointed
cap). All with tan belts, sandals. Expressions shared: `happy` (default), `talk`, `strain` (effort), `oof`,
`think`, `idea`, `cheer`.

## 2. Set: `galilee` (one page, two places)

Left = Peter's house and the yard. Right back = the lake with Peter's boat. Front = a dusty road and a strip of beach.

- **House** (`house`): a mud-brick and stone house, plastered **sand-coloured** walls, flat roof. Built like a
  **doll's house**: the front wall is cut away to a low sill (≤ 0.05) so the room is seen from the front. Inside:
  a reed mat floor, a low bench at the back, two water jars, a niche with an oil lamp, a beam ceiling (seen from below).
  The **side door** is in the right wall, facing +X. The **flat roof**: wooden beams under a layer of branches and
  packed mud, a low parapet (h ≤ 0.03) round the edge. In the roof: `roofPatch` (the intact patch over the landing
  spot) and `roofHole` (the opened hole with ragged edges and dangling twigs, hidden at start); `rubble` (a little
  heap of mud and twigs on the floor under the hole, hidden at start).
- **Outside stair** (`stair`): mud-brick steps up the house's left wall, from the front to the back corner of the roof.
- **Crowd** (`crowd1`…`crowd8`): small fixed-colour townsfolk (like Jonah's folk): four standing at the side door
  with their backs to the viewer, two sitting inside at the back corners, two leaning in at the window. They never
  move (an optional `crowdSway` loop, ±2°). Inside ones must not hide Jesus, the landing spot or Peter.
- **Yard and road**: packed earth, a fig tree at the back right of the yard, a stone olive press, the road from the
  front right edge to the side door.
- **Lake** (`lake`): stylised waves in two blues, a looping `lakeWave` action (4 s); a pebble beach along its front
  edge with reeds.
- **Boat** (`boat`): a Galilee fishing boat, round-bellied wooden hull, curved stern, a low mast with a **furled
  sail**, two oars, a **steering oar** at the stern, a coil of net in the bow, a **cushion** (`cushion`) at the stern
  (the one Jesus sleeps on); looping `boatRock` (6 s, ±3° roll).
- Far shore: a low line of **purple-grey hills** across the back of the lake.

## 3. Demo colouring

| Region | Colour | Hex |
|---|---|---|
| Jesus tunic / mantle / belt | cream / warm brown / tan | `#F2E8D2` / `#9A5B34` / `#D2AE74` |
| Jesus hair+beard | dark brown | `#4A3020` |
| Peter tunic / vest / waist cloth / head cloth | rust red / sand / dark brown / blue-grey | `#B4502F` / `#D9C29A` / `#5A3A26` / `#6E8AA6` |
| Peter hair+beard | black | `#231A16` |
| Man tunic / sash / hair | pale green / mustard / light brown | `#A9CF8E` / `#D9A93A` / `#9A6B42` |
| Mat / stripes | cream / red | `#F1E3C4` / `#C2453A` |
| Friends (fixed) tunics | orange / teal / yellow / purple-blue | `#E8843A` / `#2E9A92` / `#EFC53F` / `#5A5FB8` |
| House walls / roof mud / beams | sand plaster / clay / dark wood | `#E6CFA0` / `#B8875A` / `#6B4A30` |
| Door / jars | blue-green / terracotta | `#4E8A86` / `#C46A3E` |
| Yard / road | packed earth / pale dirt | `#D8BE8E` / `#E8D5A8` |
| Fig tree crown / trunk | green / grey-brown | `#5E9A48` / `#7A6650` |
| Lake near / far / foam | blue / deep blue / white | `#4A9AD8` / `#2C6BAE` / `#FFFFFF` |
| Boat hull / deck / sail | brown wood / light wood / cream | `#8A5A3B` / `#C9A77A` / `#F3E9D2` |
| Cushion | dark red | `#9C3A3A` |
| Beach / reeds / far hills | pebble grey-beige / reed green / purple-grey | `#CDBFA6` / `#8AA65A` / `#8E86A8` |

## 4. Light and mood per shot

| Shots | Light | Effects |
|---|---|---|
| S01-S04 | bright warm late morning | `dust_puff` while digging |
| S05-S06 | inside: warm shade, a shaft of daylight through the hole | `dust_fall` |
| S07-S08 | the shaft of light on the man, joyful | `heart_glow`, `golden_rays`, `sparkle` |
| S09 | golden-orange evening on the lake | `sunset_glow`, `zzz` |
| S10-S11 | dark storm: grey-blue, flashes, rain | `storm_rain`, `tension_dim`, `wave_splash` |
| S12 | the storm stops at once; a still, deep-blue night with stars, the lake flat as glass | `calm_wave`, `night`, `sparkle` |
| S13 | night, then a clean golden morning on the beach | `golden_rays` |

## 5. Music (original score; warm acoustic band with Galilean colour: oud, frame drum, flute, strings)

Two themes: the **friends theme** (a bouncy, determined 4-bar tune on plucked oud and handclaps: four friends who
will not give up) and the **Jesus theme** (a calm, warm rising melody on flute and strings, the same in both acts).

| Cue | Character |
|---|---|
| `capernaum` | busy little-town morning: frame drum, murmuring strings; the Jesus theme on flute at the end |
| `friends` | the friends theme, walking pace, carrying feel (a "heave-ho" lilt) |
| `no_way` | comic stop-start: pizzicato, a tuba "bonk" for the bounce, a thinking clarinet |
| `roof` | the friends theme climbing (rising sequence), then a digging rhythm (woodblock, shaker) |
| `lowering` | suspense, very soft: held strings, a single harp note per step, slowly descending |
| `heal` | the Jesus theme, tender, solo flute over strings; swells on "Get up!" |
| `joy` | dance: fast oud, handclaps, tambourine, the friends theme in major and the Jesus theme together |
| `evening` | calm evening on the water: slow 6/8, harp, soft strings, lapping rhythm |
| `storm` | fast low strings, timpani rolls, cymbal swells, wind-like flute runs; exciting, never horror |
| `calm` | sudden hush, then the Jesus theme very soft on solo flute; a held chord like still water |
| `finale` | morning: both themes together in full, ending on a bright held chord |

SFX: `crowd_murmur boing ding dig_loop crumble rope_creak sparkle cheer lake_lap thunder wind_loop wind_stop`
(see CONTRACT §7).
