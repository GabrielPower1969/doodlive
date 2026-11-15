# Jonah — art direction (costume, make-up, props, set, light, music)

Same family as Ruth and Daniel: Paper & Crayon look, rounded readable shapes, decal faces, same head-to-body ratio.
**Every colourable region is a closed shape ≥ 6 mm on the A4 print.** Small parts (sandals, cords, eyes, teeth) are
fixed-colour detail lines, not regions. All designs are original; the reference viewing lent only the logic below.

Period: about 760 BC. Israel's coast (Joppa) and Assyria (Nineveh).

## 1. Characters

### Jonah (hero) — height 0.36
- **Face**: about forty-five; long face, big nose, thick expressive eyebrows (they carry the comedy), tired eyes,
  full short beard. Dark-brown hair to the nape with **grey streaks at the temples**, a little messy.
- **Costume**: long **cream** tunic to the shins with a ragged hem; over it an open, knee-length **brown outer coat
  with wide tan vertical stripes** (three stripes per front panel, each stripe ≥ 6 mm on the sheet); a **tan cloth
  belt** wrapped twice; leather sandals. Sleeves of the tunic show at the forearm.
- **Props** (hidden by default): `seaweed` (a green clump on the head, child of `head`).
- **Expressions**: `grumpy` (default), `talk`, `shock`, `ashamed`, `yuck` (nose wrinkled), `pray` (eyes closed),
  `sorry`, `sulk` (pout, brows down), `happy`, `wail` (mouth wide, tears), `soft` (understanding, small smile).
- **Regions**: skin, hair+beard, tunic, coat, coat stripes, belt.

### The captain — height 0.38
- **Face**: fifty, weathered, round cheeks, big grin, short curly black beard, bushy brows.
- **Costume**: a **sea-green head-wrap** (bandana knotted at the back, a short tail), bare forearms, a **cream
  sleeveless tunic** to the knee, a wide **rust-red sash**, a short **dark-blue** wrap-skirt over the tunic, bare
  feet. Broad chest and big hands.
- **Expressions**: `jolly` (default), `talk`, `shout`, `worried`, `torn` (brows up, mouth pulled), `amazed`.
- **Regions**: skin, beard, head-wrap, tunic, sash, skirt.

### The great fish — length 0.50, height 0.20 (a new rig type, see CONTRACT §3)
- **Shape**: a huge, plump, friendly fish (not a shark, not a realistic whale): big rounded head with a wide mouth
  that opens very far, small kind eyes with eyebrows, a low dorsal fin, two round side fins, a broad tail.
- **Colours**: **deep teal** back, **pale aqua** belly, slightly darker fins, a few big round spots on the back
  (each spot ≥ 6 mm, its own region), pink mouth interior (fixed colour), soft white rounded teeth (fixed).
- **Expressions**: `calm` (default), `hungry` (eyes wide, licking look), `gulp` (eyes shut tight), `oops` (after the
  burp, embarrassed), `happy`.
- **Regions**: back, belly, fins, spots. Drawn on the sheet in **side view** (nose to −X), like Daniel's lion.

## 2. Set: `coast` (one page, three places)

Left = the sea with the ship. Middle front = the beach. Right = Nineveh (back) and Jonah's hill (front).

- **Sea** (left 55 % of the page): stylised waves in two blues, looping wave action. White foam line at the beach.
- **Ship** (on the sea, back-left): a round-bellied wooden merchant ship, hull planks, a curved prow and stern, one
  mast with a **furled cream sail with two red stripes**, rope ladder, a steering oar at the stern, **cargo sacks
  and jars** on deck (Jonah sleeps behind them), a **gangplank** from the beach to the deck. Deck height 0.10.
- **Beach**: pale sand, shells, a rope coil, two wooden mooring posts, a small rowing boat pulled up.
- **Nineveh** (back right): a long **mud-brick wall with stepped battlements**, a big arched **gate** flanked by
  two towers, a blue-and-gold band over the arch, flat roofs and a stepped temple behind, two date palms.
- **Hill** (front right): a low sandy mound with rocks and dry grass. On it:
  - `shelter`: three sticks and a patched cloth (hidden until S10);
  - the plant in three states: `plantSmall` (a sprout), `plantBig` (a broad-leafed gourd vine, big enough to shade a
    seated man, with two round gourds), `plantDry` (the same, brown and drooping);
  - `worm`: a little green worm with a happy face on the stem (hidden; shown for a few seconds in S11).
- **Inside the fish** = `belly`: a ribbed dome of soft pink-grey arcs with a dark-teal floor disc, open toward the
  viewer, big enough for a kneeling man (hidden until S06). It stands on the sea area at the front left.
- **Road**: a pale track from the right edge to the gate and down to the beach.

## 3. Demo colouring

| Region | Colour | Hex |
|---|---|---|
| Jonah tunic / coat / stripes / belt | cream / brown / tan / tan | `#F1E7D0` / `#8A5A3B` / `#D9B57A` / `#C9A26A` |
| Jonah hair+beard | dark brown (grey streaks are fixed) | `#4A3526` |
| Captain head-wrap / tunic / sash / skirt | sea green / cream / rust / navy | `#4FA58A` / `#EFE3C8` / `#B5532E` / `#2F4F8A` |
| Captain beard | black | `#231A16` |
| Fish back / belly / fins / spots | deep teal / pale aqua / dark teal / light teal | `#1F7F86` / `#BFE9E2` / `#17666C` / `#6CC3BE` |
| Sea near / far / foam | blue / deep blue / white | `#3B8FD0` / `#2B6FB0` / `#FFFFFF` |
| Ship hull / deck / sail / stripes | brown wood / light wood / cream / red | `#8A5A3B` / `#C9A77A` / `#F3E9D2` / `#B8423A` |
| Beach / road | pale sand / pale dirt | `#EAD9B0` / `#E3CFA3` |
| City wall / gate band / roofs | mud-brick / lapis + gold / clay | `#D8B07A` / `#2E5FA8`, `#E8C15A` / `#C9A77A` |
| Hill / rocks | ochre / grey-brown | `#D9B77A` / `#9C8A72` |
| Plant leaves / gourds / dry | fresh green / yellow-green / brown | `#5FA844` / `#B9C85A` / `#8A6A44` |
| Shelter cloth | faded rose | `#C98F8F` |
| Belly ribs / floor | pink-grey / dark teal | `#D9A9A6` / `#17444A` |

## 4. Light and mood per shot

| Shots | Light | Effects |
|---|---|---|
| S01-S02 | bright warm morning | `golden_rays` on Jonah when God speaks; `sea_wind`; `zzz` |
| S03-S04 | dark storm: grey-blue, flashes | `storm_rain`, `tension_dim`, `splash` |
| S05 | calm, overcast, soft | `bubbles` |
| S06 | deep teal, almost dark, then a warm glow on Jonah | `deep_glow`, `prayer_glow` |
| S07-S09 | clean bright day; gold over the city at the end | `splash`, `golden_rays` |
| S10-S11 | hot afternoon; harsh sun after the worm | `steam`, `plant_grow`, `sun_scorch`, `sweat` |
| S12 | golden hour | `golden_rays`, `heart_glow` |

## 5. Music (original score; mood: warm cinematic orchestra with Middle-Eastern colour, comic where the story is)

Two themes: the **call theme** (God's voice: a calm rising 4-note figure on a warm horn / cello) and the **Jonah
theme** (a grumpy, plodding bassoon tune that turns gentle in S12).

| Cue | Character |
|---|---|
| `call` | the call theme, soft strings and harp; reused in S08 |
| `runaway` | comic tiptoe: pizzicato, woodblock, the Jonah theme sneaking |
| `storm` | fast low strings, timpani rolls, cymbal swells; exciting, never horror |
| `deep` | after the splash: slow, underwater, low pad and a single harp; continues under S05 |
| `prayer` | hushed; the call theme answered by a solo cello |
| `shore` | bright morning, flute and plucked strings, a comic slide on the "pfft" |
| `nineveh` | a broad march with frame drum and reed, Mesopotamian colour |
| `repent` | warm strings swelling, choir pad |
| `sulk` | the Jonah theme at its grumpiest: bassoon and tuba, a sour clarinet |
| `plant` | playful growing figure (rising harp), then a "wah-wah" droop |
| `mercy` | the call theme in full, the Jonah theme joins it in major; ends on a held chord |

SFX: `soft_chime seagulls thunder rain_loop rain_stop splash_big bubbles gulp burp spit_pop grow_whoosh munch
cicadas_heat` (see CONTRACT §7).
