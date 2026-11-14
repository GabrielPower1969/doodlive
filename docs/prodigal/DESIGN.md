# The prodigal son — art direction

Same family as the other packs (`docs/ruth/DESIGN.md`, `docs/exodus/DESIGN.md`): Paper & Crayon look, rounded readable
shapes, the same head-to-body ratio, line weight and face style. Every colourable region is a closed shape at least 6 mm
across on the A4 print. Period: first-century Galilee (home) and a Hellenistic city across the sea (the far country).
All designs are original.

Quality bar (owner, 2026-11-14, same as Ruth / Exodus): faces with life, cloth that hangs and moves, a set that feels
like a real place, voices that sound like people. This story's heart is **the father's run and the hug**: spend
acting and music effort there.

## Characters

### The son (the hero)
- Young man (about 18), slim, quick; dark brown messy hair, a short first beard shadow, big expressive eyebrows (cheeky
  → miserable → overjoyed).
- At home and leaving: a **sky-blue** tunic to the knee with a **yellow** sash, a short sleeveless **red** over-vest
  (his "fancy" touch), sandals. In the far country the same clothes get dirty by the pig scene (the texture stays; the
  FX/anim can add mud splashes only as decals if cheap, otherwise not).
- Props: `purse` (leather money bag with a drawstring, handL, hidden by default), `robe` (the father's best robe: a long
  **purple** sleeveless over-robe with a gold border that drapes over his shoulders to the shins; a rigid shell on
  `chest` with two short follow bones, hidden until S10), `ring` (small gold ring with a red stone on the right hand,
  hidden until S10).
- Expressions: `cheeky`, `talk`, `joy`, `puzzled`, `shock`, `sad`, `hungry` (eyes on the pods, mouth watering),
  `cry`, `idea` (eyes wide, mouth "o"), `amazed`.

### The father
- About sixty, warm and dignified; **grey** hair and a **grey** full beard (beard tip sways), kind eyes, laugh lines.
- A long **cream** tunic, a **deep-green** outer robe (abaya) with front panels that swing (he hitches it up to run), a
  **brown** sash, a **white** head-cloth with a **blue** cord; sandals.
- Prop `purse` (same bag as the son's, handR, hidden by default).
- Expressions: `kind`, `talk`, `sad`, `longing` (eyes searching, brows up), `surprise`, `joy` (laughing, eyes
  crinkled), `cry_joy` (tears and smile), `plead`.

### The big brother
- Mid-twenties, broad-shouldered farmer, short dark beard, thick eyebrows (often frowning), sun-tanned.
- A **rust-brown** short tunic belted with a rope, rolled sleeves, a **beige** head-cloth tied back, leg wraps; sandals.
- Prop `hoe` (wooden handle, iron blade; handR; carried on the shoulder when walking).
- Expressions: `neutral`, `talk`, `frown`, `angry` (puffed, brows down), `hurt` (lip wobble), `soft` (brows relax,
  small smile).

## Set: home and the far country (`homeland`)

From back to front on the page:
- **Backdrop** (low relief across the back): left half green rolling Galilean hills with cypress and olive trees; right
  half dry tawny hills and the far-off sea glinting (the far country "across the sea"); the road winding away between.
- **The farmhouse** (back left): two-storey-ish stone house with a flat roof, an outside staircase, a wooden door
  (front face z ≈ −0.37), small windows, a vine over the door; empty `lampsFlame` points at hidden lamps.
- **The courtyard** (left middle): paved stones in front of the house, a round **well**, a **fig tree**, a low
  dry-stone wall on the west and back only (front and east open), clay jars, a bench.
- **The field** (back centre): ploughed furrows and young wheat rows behind the courtyard, with a bare strip where the
  brother hoes.
- **The road** (centre): a pale dirt road from the courtyard winding to the far country and to the front edge.
- **The far country** (back right): a Hellenistic tavern with two columns, a striped **awning**, colourful **bunting**,
  tables and stools, amphorae; a small market stall with fruit. Node `tavern` for the party lights.
- **The pig pen** (front right): a wooden fence pen with two gaps (north and west), mud puddles, a trough, a pile of
  carob **pods**, and four round **pigs** that wiggle and root (looping set clip).
- Hidden props: `feast` (a long low table in the courtyard with bread, grapes, figs, a big dish, cups, cushions; S11),
  `lamps` (oil lamps on the table and hanging lanterns on the house, with `lampsFlame` empties).

## Demo colouring (the sample the app ships)

| Region | Colour | Hex |
|---|---|---|
| Son tunic / sash / vest | sky blue / yellow / red | `#6FB3E0` / `#F2C230` / `#D2483A` |
| Son hair / skin | dark brown / tan | `#4A2E1F` / `#E2A878` |
| Son robe (prop) / border / ring | purple / gold / gold-red | `#7B4FA6` / `#E8B83A` / `#E8B83A` |
| Father tunic / robe / sash | cream / deep green / brown | `#F1E6CC` / `#3F7A55` / `#8A5A3B` |
| Father hair+beard / head-cloth / cord | grey / white / blue | `#B9B4AE` / `#FBF8EF` / `#3E6FB0` |
| Brother tunic / belt / head-cloth | rust brown / rope / beige | `#A8582E` / `#B89466` / `#E9D9B6` |
| Brother beard / hoe | dark brown / wood + iron | `#3A2418` / `#9B6B43`, `#7A7F86` |
| House stone / door / roof | limestone / wood / clay | `#E3D3B0` / `#8A5A3B` / `#C9A77A` |
| Courtyard paving / well / fig | sand stone / grey stone / green | `#D9C29A` / `#A9A49A` / `#5E9A4A` |
| Field soil / wheat | brown / green-gold | `#9A6A43` / `#B7C25A` |
| Hills home / far | green / tawny | `#A7C26A` / `#D9B77A` |
| Tavern / awning / bunting | white stone / red-white / rainbow | `#F1EADB` / `#D2483A` / mixed |
| Pig pen fence / mud / pigs / pods | wood / mud / pink / brown | `#9B6B43` / `#7A5638` / `#F2A7A0` / `#6B4426` |
| Road | pale dirt | `#E9D9B6` |

## Light and mood per part
- S01-S03 fresh morning, birds.
- S04 the tavern glows with coloured party lights in a dusk light.
- S05-S07 famine: a hot, dry, desaturated haze; dust; a wilted look.
- S08-S10 golden evening (`sunset_glow`) for the walk home and the run.
- S11-S13 night with stars, warm lamps and lanterns, music notes floating from the house (`night`, `lamp_flame`).
- S14 soft bright morning, golden rays.

## Music direction (original score)
Warm cinematic folk orchestra with Middle-Eastern colour (oud, ney-like flute, frame drum, strings). One **"father's
theme"** (a warm, simple 6-note tune) returns at home, sadly when the son leaves, in minor when he is homesick, huge
when the father runs, and as the finale.
- `home` pastoral morning, father's theme on flute, oud plucks.
- `leaving` bouncy, cocky walking tune for the son (whistle-like), father's theme faint underneath.
- `party` lively comic dance (tambourine, clapping, a slightly too-fast fiddle).
- `broke` deflating: a sliding trombone "wah-wah", then thin strings.
- `pigs` comic tuba/bassoon oom-pah with snorts in rhythm.
- `homesick` slow, lonely; father's theme in minor on a single flute.
- `road_home` steady walking strings, hopeful, a little shaky.
- `run` the big one: father's theme bursts out full orchestra as he runs; held warm chord for the hug.
- `feast` night celebration dance (frame drums, oud, clapping), joyful.
- `brother` grumpy low bassoon/cello walk, feast music faint and muffled behind the wall.
- `finale` warm full father's theme, ends on a held chord.
