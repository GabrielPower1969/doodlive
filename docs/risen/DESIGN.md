# He Is Risen! — art direction (costume, make-up, props, set, light, music)

Same family as Ruth, Daniel, Jonah, Real Miracles and The King Who Serves: Paper & Crayon look, rounded readable shapes,
decal faces, same head-to-body ratio. **Every colourable region is a closed shape ≥ 6 mm on the A4 print.** Small
parts (sandals, cords, eyes, jar handles) are fixed-colour detail lines, not regions. All designs are original; the
reference viewing lent only the logic below (a tomb cut into a reddish rock face with a round stone in a groove; a
green garden with olive trees and flowers; blue-violet pre-dawn light turning to a warm backlit sunrise; women in long
robes and head veils carrying small jars; a shining angel in white; the lamp-lit upstairs room in the evening).

Period: about AD 30, the Sunday after Passover and the week after. A garden just outside Jerusalem's wall.

## 1. Characters

### Jesus — height 0.36 (identical to Real Miracles and The King Who Serves)
- **Face, hair, costume, regions, colours: exactly `docs/miracles/DESIGN.md` §1 and §3** (cream tunic, warm brown
  mantle, tan belt, dark-brown hair and beard). The risen Jesus is the same man: no white robe, no halo drawn on the
  model, **no marks on the hands or feet**. Glory is light (FX), not costume.
- **New prop** (hidden by default): `fish` (a small grilled fish, 0.05 long, golden brown with dark grill lines;
  child of `handR`).
- **Expressions**: the Miracles drawings `kind` (default), `talk`, `smile`, `laugh`, `gentle`, `look_up`; new: `joy`
  (a wide open smile, eyes curved, brows up: "Mary." / "Peace be with you!") and `chew` (cheeks round, lips closed,
  eyes smiling: the fish).
- **Regions**: skin, hair+beard, tunic, mantle, belt.

### Mary Magdalene (`mary`) — height 0.34
- A young woman with a soft round face, big dark eyes, **wavy dark-brown hair** showing in front of a **head veil** that
  falls to her shoulders and back; a **long dress** to the ankles with wide sleeves; a **sash** tied at the waist with
  ends hanging at the left hip; sandals (detail).
- Prop: `jar` (a small round spice jar with a lid and a cord, 0.05 high; child of `handL`), shown S02-S04.
- **Expressions**: `gentle` (default), `talk`, `sad` (brows up in the middle, mouth small), `cry` (eyes squeezed,
  tears as two drawn drops, mouth wobbly; not ugly-crying), `gasp` (eyes round, mouth O), `joy` (laughing, eyes
  curved, a tear still on one cheek), `amazed`.
- **Regions**: skin, hair, veil, dress, sash (the sash ≥ 6 mm, else a detail line taking the dress colour).

### The angel (`angel`) — height 0.40 (wing tops 0.46 when folded)
- Tall, strong and kind, never a baby cherub and **not Gabriel** (no armour, no trumpet, no sword, short hair): a young
  face with a big friendly smile, **short golden curls**, a **long white robe** to the feet with a high round neck and
  long sleeves, a **broad gold sash** across the waist, bare feet (detail).
- **Wings**: two soft, rounded wings of simple layered feather rows (three rows each: coverts, secondaries,
  primaries), folded **half-open** behind the shoulders. On the sheet they rise above the shoulders and spread no more
  than ±0.14 from the body centre (C2: Jesus's A-pose hands end near −0.12).
- **Expressions**: `smile` (default), `talk`, `joy` (laughing), `kind` (closed-mouth smile, soft eyes).
- **Regions**: skin, hair, robe, sash, wings (one region for both wings; the feather rows are drawn lines).

### Peter (`peter`) — height 0.38 (Real Miracles design, fixed paint here)
- Exactly the Miracles Peter (rust-red tunic, sand vest, dark-brown waist cloth, blue-grey head cloth, curly black
  hair and beard), painted with the Miracles demo colours (`docs/miracles/DESIGN.md` §3) into `extras_paint.png`.
- **Expressions**: Miracles `jolly`, `talk`, `shock`, `laugh`, `amazed`; The King Who Serves `puzzled`; new: `sad`
  (head down, brows up), `puff` (red cheeks, mouth wide panting, eyes squeezed).

### John (`john`) — height 0.33 (The King Who Serves design, fixed paint)
- Exactly `docs/lastsupper/DESIGN.md` §1 (beardless, light-brown wavy hair, sky-blue tunic, white sash).
- **Expressions**: the disciples' group drawings from The King Who Serves (`happy`, `talk`, `amazed`, `laugh`) plus new
  `sad`, `shock` (eyes huge, mouth a wobbly zigzag: "a g-g-ghost?").

### Thomas (`thomas`) — height 0.36 (new, fixed paint)
- A sensible, solid man: a **short square beard**, straight dark hair to the ears, thick level brows, a **teal** tunic,
  a **rust** head band, a tan belt, a short **grey-brown** cloak over both shoulders. Silhouette clearly unlike Peter
  (straighter, no head cloth) and John (beard, cloak).
- **Expressions**: the disciples' group drawings (`happy`, `talk`, `amazed`, `shock`) plus new `doubt` (one brow down,
  mouth flat to one side) and `awe` (eyes wet and shining, mouth open in a soft smile: "My Lord and my God!").

### Joanna (`joanna`) — height 0.33 (new, fixed paint; Mary's body with another costume)
- Built by the same female builder as Mary with a different costume: an older, practical friend, a little rounder, a
  **mustard** dress, a **brick-red** veil, a **cream** apron-sash; grey-streaked hair in front of the veil.
- Prop: `jar` (the same spice jar, `handL`).
- **Expressions**: Mary's drawings re-coloured (`gentle`, `talk`, `sad`, `gasp`, `joy`).

## 2. Set: `garden` (one page, three places)

Left = the garden with the tomb. Front = the path. Right back = the house with the upstairs room. **No cross, no hill
with crosses, no soldiers anywhere on the page.**

- **Tomb** (`tombHill`): a rounded **reddish-tan rock** hill at the left back, up to 0.42 high, with ivy and two small
  bushes on top. In its front face, facing the viewer, the **door** (`tombDoor`): a dark rounded opening 0.13 wide,
  0.34 high. Inside, seen through the door: a short chamber with a stone **ledge** and the **folded linen cloths**
  (`cloths`, always there; seen only when the tomb is open). In front of the door a shallow **groove** in the rock
  floor runs to the right. `tombStone` = a **big round stone** (disc 0.39 across, 0.05 thick, lead-approved 2026-11-18) standing on its edge in
  the groove across the door, covering it. `tombStoneAside` (hidden at start) = the same stone rolled right and turned 40° back into an alcove;
  the angel sits on its top.
- **Garden**: soft green grass with a **flower bed** (`flowers`) in front of the tomb and along the left front edge
  (lilies, poppies, daisies: big readable blooms, top ≤ 0.04); two **olive trees** (`olive1` behind the hill's right
  shoulder, `olive2` at the far left edge; crowns high and at the back, never in front of faces); a gardener's **spade
  and watering jar** leaning against the rock at the hill's right end (`gardenTools`: why Mary thinks of a gardener);
  a **low stone garden wall** (`gardenWall`, h ≤ 0.03) between the garden and the path with a gap (`gate`).
- **Path** (`path`): pale packed earth from the house's ground-floor door (right) curving along the front to the
  garden gate and up to the front of the tomb.
- **House** (`house`): a two-storey limestone house at the right back, ground storey closed (a wooden door, a
  window); **upstairs room** as a doll's house: front wall cut away to a low sill. Inside: a long **bench** along the
  back wall with cushions (seated actors face the phone); a **low table** (`lowTable`) at the front right with a clay
  **plate of grilled fish** (`fishPlate`; the fish itself is `fishOnPlate`, hidden when Jesus takes it) and a bread
  basket; a **water jar** (`waterJar`) in the back-left corner; two **oil lamps** (`lamp1` in a back-wall niche,
  `lamp2` on the table); a **door** in the left wall (`roomDoor`, closed, a wooden bar across it: "the door was
  locked"); an outside **stair** up the house's left wall to that door (decor; nobody walks it on screen).
- Far back: a stretch of **Jerusalem's wall** with a small gate (right, behind the house) and low **hills** (left,
  behind the tomb).

## 3. Demo colouring

| Region | Colour | Hex |
|---|---|---|
| Jesus, Peter | exactly as `docs/miracles/DESIGN.md` §3 | — |
| John (fixed) | exactly as `docs/lastsupper/DESIGN.md` §3 | — |
| Mary dress / veil / sash / hair | rose / sky blue / cream / dark brown | `#D9775F` / `#8DB5D8` / `#F1E3C4` / `#4A3020` |
| Angel robe / sash / wings / hair | white with a blue tint / gold / cream-white / golden | `#F4F7FB` / `#E6B23E` / `#FFF6DE` / `#E2B85A` |
| Thomas tunic / cloak / head band (fixed) | teal / grey-brown / rust | `#3E8E86` / `#8A7A68` / `#B4502F` |
| Joanna dress / veil / apron (fixed) | mustard / brick red / cream | `#D9A93A` / `#A84A3A` / `#F1E3C4` |
| Spice jars / water jar / plate | terracotta | `#C46A3E` |
| Fish | golden brown | `#C98A4A` |
| Rock hill / door / stones | reddish tan / deep brown-violet / warm grey | `#C9946A` / `#4A3440` / `#B9AFA2` |
| Linen cloths | white | `#F5F1E6` |
| Grass / path | spring green / pale earth | `#8DBB5A` / `#E8D5A8` |
| Flowers | white lilies, red poppies, yellow daisies | `#FFFFFF`, `#D9483A`, `#F2C94C` |
| Olive trees / bushes / ivy | grey-green + brown trunk / green | `#8AA06A` + `#7A6650` / `#5E9A48` |
| House stone / room wall / bench cushions / floor mats | limestone / warm plaster / dark red / straw | `#E9D6A8` / `#EBD2A6` / `#9C3A3A` / `#D8BE8E` |
| City wall / hills | darker stone / olive green | `#C9B285` / `#8E9E62` |

The colour plan keeps the three printed figures apart at a glance: the angel white and gold, Jesus cream and brown,
Mary rose and blue. The tomb rock is warm, so the open door reads dark until `tomb_glow` lights it.

## 4. Light and mood per shot

| Shots | Light | Effects |
|---|---|---|
| S01 | dusk turning dark, cool and quiet (the "sad day"), never black | `tension_dim` |
| S02-S04 | dawn: pink and gold sky, low warm sun from the right behind the house, long soft shadows; the angel's light white-gold | `dawn_glow`, `dust_burst` (the stone), `angel_light`, `tomb_glow` |
| S05 | morning sun in the room | — |
| S06-S07 | bright morning on the path and at the tomb | `run_dust` ×2, `tomb_glow` |
| S08 | soft morning in the garden, a little hazy | `angel_light` (He appears) |
| S09 | full warm sunlight breaking through, butterflies | `butterflies`, `golden_rays` |
| S10-S11 | golden evening in the room, two lamps | `sunset_glow`, `lamp_flame` ×2, `angel_light` (He appears), `heart_glow` (Thomas) |
| S12 | bright clear morning over the whole page | `golden_rays` on the tomb door, `butterflies` |

## 5. Music (original score; the warm acoustic band of the Jesus packs: oud, flute, harp, strings, frame drum, a
children's "ah" choir)

Two themes: the **promise theme** (a short rising 4-note figure, first heard sad and slow on solo flute in S01 when the
narrator says "On the third day...") and the **morning theme** (the promise figure turned into a full, bright melody:
the resurrection). Every Easter-morning cue grows out of the promise figure; the finale is the morning theme with the
whole band and the choir.

| Cue | Character |
|---|---|
| `sad_day` | quiet and tender, low strings and a slow harp; the promise figure on flute at the very end, unresolved |
| `dawn` | birdsong-like flute trills over soft harp arpeggios; hopeful, walking pace |
| `stone` | a low drum roll swelling (the rumble), a shimmering string chord and a bright harp glissando for the light |
| `risen` | the morning theme for the first time: strings and choir, glowing, not loud; stays warm under the angel's words |
| `news` | breathless and excited: quick oud and hand drum, a rising flute |
| `race` | comic chase: fast pizzicato for John, a heavy tuba "oompah" for Peter, a slide whistle when he puffs |
| `empty` | hushed wonder: celesta and harp, the promise figure answered at last |
| `garden_tears` | gentle and slow: solo cello, the promise figure in a minor key, very soft |
| `mary` | the turn: one held note, then the morning theme bursts out on flute and strings; tender and joyful |
| `peace` | warm evening strings; a "ghost" pizzicato tiptoe for John's squeak, then laughter-light woodblocks for the fish |
| `thomas` | thoughtful clarinet for his doubt, then the morning theme, slow and heartfelt, for "My Lord and my God!" |
| `finale` | the morning theme in full: band, choir and hand claps, ending on a bright held chord |

SFX: `birds_dawn rumble stone_roll appear_chime run_steps munch sparkle_up` (see CONTRACT §7). All one-shots.
