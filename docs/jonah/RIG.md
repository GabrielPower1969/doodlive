# Jonah — rigs (Characters role)

Built by `pipeline/jn_characters.py` (`python3 pipeline/jn_characters.py all`). Models: `assets/jonah/model/{jonah,captain,fish}.glb`
(character-local, no animations), `characters.blend` (all three at their sheet slots), sheet data
`regions_characters.json` + `id_characters_2x.{png,json}`, previews `preview_*.png`, face decals `docs/jonah/design/faces/`.

## 1. Measured (re-imported GLBs)

| | jonah | captain | fish |
|---|---|---|---|
| Triangles (budget) | **52,680** (was 24,224; polish target 45-60k) | **48,620** (was 20,040; 45-60k) | **38,168** (was 16,488; 30-40k) |
| Size (re-imported GLB, 2026-11-15) | top 0.3569 (contract 0.36, -0.9 %) | top 0.3775 (0.38) | length 0.533, height 0.2105, width 0.207 with the side fins (CONTRACT 0.53 / 0.21 / 0.205) |
| Bones = CONTRACT §3 | yes | yes | yes |
| Max influences | 4 | 4 | 3 |
| Lowest point | 0.0002 (sandal soles) | 0.0002 (sandal soles) | 0.0028 (belly) |

## 2. Humans (`jonah`, `captain`)

Kit skeleton, A-pose (arms 55° below horizontal), facing +Z, same conventions as Ruth / Daniel.

- **Blink**: scale `eyelids` local Y from 1.0 (open) to **12.78** (closed); X/Z stay 1.
- **Jaw**: `jaw` rotates the chin + beard; open mouths are face decals (`talk`, `shock`, `wail`, `shout`, `amazed`).
- **jonah extras**: `coatL` / `coatR` (open coat front panels below the belt, from `chest`), `belt1` (hanging belt end,
  from `hips`), `seaweed` (prop bone, child of `head`; mesh `jonah_seaweed`, **hidden by default**; its colour is
  anchored to `fish.fins` until the Set + sheet role gives a green set region via `design.json characters.jonah.propUV.seaweed`
  or a set region named `leaves` / `plantLeaves` / `plant`).
- **captain extras**: `wrap1` (tail of the head-wrap knot, from `head`), `sash1` (hanging sash end, from `hips`).
- Jonah's belt is over the coat at the hips, so the coat panels swing freely only below it.
- Jonah's coat: open, knee length, rolled hem, long sleeves with rolled tan cuffs; **six tan stripes** (three per side:
  one down the middle of each front panel — the one the sheet shows —, one at the side seam, one on the back), below
  the chest. The grey temple streaks are faces of the hair shell (one soft band per temple), fixed colour.
- The captain: broad chest and a round belly (the sash and skirt follow it), thick bare arms, big hands, a wide sash
  with diagonal folds and a knot with a hanging end, a short pleated navy wrap skirt with a raised front flap edge and
  a rolled hem, head-wrap knot with two tails (`wrap1`).

## 3. The fish (new rig type)

Model space: nose to **+Z**, belly on y = 0, root under the middle of the length. On the sheet it is drawn in **side
view** (its left side, nose to −X); both sides share the drawing (UV0 mirrored).

| Bone | Parent | Where |
|---|---|---|
| `root` | — | (0, 0, 0), points up |
| `body1` | root | head and front third: (0, 0.10, 0.115) → (0, 0.10, 0.035) |
| `body2` | body1 | middle → z −0.06 |
| `body3` | body2 | rear third → z −0.154 |
| `tail` | body3 | tail fin → z −0.252 |
| `jaw` | body1 | hinge (y 0.0895, z 0.146) → chin (0.05, 0.236) |
| `finL` / `finR` | body2 | side fins, root at (±0.064, 0.058, 0.090), pointing back / out / down |
| `dorsal` | body2 | (0, 0.172, 0.055) → (0, 0.184, −0.060) |
| `eyelids` | body1 | **points UP** from under the eyes (see below) |

The spine chain points backward (nose → tail): bending `body1` swings everything behind it. Body wave = small
alternating yaw on body1 / body2 / body3 / tail (see `preview_pose.png`, "fish swim").

- **Jaw**: rotate `jaw` about design X by **+55°** (chin down) for the gulp; 10° for the burp. The mouth is real
  geometry: pink roof and floor, dark throat, tongue, 10 soft teeth. Shut at rest it shows only a hair line.
  Points of the belly just behind the corner are partly on `jaw`, so the throat bulges forward as the jaw opens (pelican pouch).
- **Blink**: same channel as the humans (`eyelids.sy`), but the fish blinks with **lower lids**: they rest as a thin strip
  under each eye and rise over it. Closed = **13.06**. They lie on the cheek surface over the whole travel (checked in
  `preview_pose.png`, "fish closed"). The `gulp` decal also draws the eyes shut.
- Face decals project from the **side** onto both cheeks (eye, brow, blush, smile curl at the mouth corner, gill line).
  Expressions: `calm` (default), `hungry` (wide eyes, tongue licking over the lip), `gulp`, `oops` (blush, sweat drop), `happy`.

## 4. Expressions and suggested clip faces

Files `docs/jonah/design/faces/<char>_<expr>.png` (512 px, overview in `overview.png`). Suggested clip → decal map is in
`regions_characters.json` (`faceDecal.clipExpression`).

- jonah: grumpy (default), talk, shock, ashamed, yuck, pray, sorry, sulk, happy, wail, soft
- captain: jolly (default), talk, shout, worried, torn, amazed
- fish: calm (default), hungry, gulp, oops, happy

## 5. Fixed colours (decal swatches) and anchors

Every decal of a character carries small colour swatches in a corner that no surface projects onto (Naomi's baby-face
method). Fixed-colour parts point their UV1 there, so the child's colouring never changes them:

| Part | Swatch | UV0 (prints as) |
|---|---|---|
| Jonah's grey temple streaks (`streaks`) | grey | anchored to `jonah.hair` (detail lines) |
| Jonah's sandals (`sandals`) | leather brown | anchored to `jonah.tunic` (detail lines) |
| Captain's rope belt, hip coil, wrist bracelets (`rope`) | hemp tan | anchored to `captain.tunic` (detail lines) |
| Captain's sandals (`sandals`, new 2026-11-15) | leather brown | anchored to `captain.tunic` (detail lines) |
| Fish mouth inside / tongue / teeth (`mouth`) | dark throat → pink, tongue pink, teeth white | anchored to `fish.belly`; in the ID render the mouth draws as the lower-jaw belly |

Anything that redraws the decals must keep the swatch rectangles (`SWATCHES` in the script, also in
`regions_characters.json faceDecal.swatches`).

## 6. Printed sizes (inscribed cell on the ID render at 150 dpi, measured after a 1 px line allowance)

Re-measured 2026-11-15 after the polish (`assets/jonah/sheet/checks.json`, best inscribed cell): no slivers; every
region not listed below is >= 6 mm, including Jonah's coat stripes (the tan front bands, were 3.2 mm) and the
captain's new vest. Below 6 mm: jonah hair 1.5, beard 3.5, belt 5.4, coat 5.8 (was 4.8), face 5.8; captain wrap 2.0,
beard 2.1, face 5.4, sash 5.8; fish dorsal 6.0. The captain's knot and moustache (0.3 mm slivers) now merge into the
wrap / beard shapes.

Earlier (before the polish):
Below 6 mm (detail lines / known small): jonah coat stripes ~3.2 (cuffs anchored to the stripes) and coat ~5.2, belt ~5.6, hair 1.7, beard 2.7, hands,
legs; captain face 5.6, wrap 2.2, beard 2.4, arms / knees / legs / hands (skin anchored to the face);
fish dorsal now 6.3, side fin 8.3, tail 12.8. Heads and hair are small on every sheet (pitfall C3).

## 7. Notes for Animation

- Hands, legs, bare arms and knees print as slivers; their colour comes from the face skin (PART_ANCHORS).
- The captain's wrap tail and sash end, Jonah's belt end and coat panels are separate bones for secondary motion.
- Jonah is parked off the page while swallowed (lead's timeline); nothing in the rig depends on that.

## 8. Polish 2026-11-15 ("精致、多面、声音合适、儿童喜爱，精修")

Skeleton, bone names, prop sockets, clip names, face-shape (expression) names and the blink values (humans 12.78, fish
13.06) are unchanged; sizes are within CONTRACT §2. All new parts either merge into a printed shape (`piece_as`) or
print as detail lines (`PART_ANCHORS` / fixed-colour swatches), so the sheet gained no sliver.

| | What changed | Triangles |
|---|---|---|
| all faces | bigger, rounder, warmer eyes (EYE jonah 0.33 x 0.228, captain 0.30 x 0.214 of hw), three highlights, warm irises, soft cheek blush on every Jonah expression, fewer age lines, brows lifted clear of the parked lid strip; face mesh subdivided twice (smoother cheeks / nose in close-ups); Jonah's head sculpt softer (cheek +0.12, smaller sockets / cheekbones) | face 2.8k / 3.1k -> 11.2k / 12.2k |
| jonah | 19 sculpted hair locks combed from a centre parting to the nape (one grey lock per temple = `streaks`; the old grey shell bands are gone); 9 beard locks; a twisted tan head cloth across the forehead knotted at the back with two tails (`headband`, belt colour, detail lines); coat: wider A-line skirt, narrower opening, each lower front panel one wide tan band (>= 6 mm on the sheet) framed by brown piping (`coatTrim`), side and back stripes, plain brown above the belt, rolled shawl collar (`coatCollar`), rolled hem; belt wound twice with diagonal folds and a fringed hanging end (`beltFringe`); sandals with real soles, ankle ring, instep / toe straps and a T-strap (`sandalL/R`) | 24,224 -> 52,680 |
| captain | moustache and head-wrap knot merged into the beard / wrap shapes (sheet slivers fixed); rolled hem round the head-wrap; about 25 small beard curls; open ochre **vest** (new region `vest`, sleeveless, V-neck, rolled front edges, tucked under the sash); rolled cap-sleeve hems; denser sash folds and skirt pleats; sailor's **rope** (fixed hemp colour): rope belt under the sash, a coil at his left hip, rope bracelets on both wrists; sandals like Jonah's (fixed leather colour) | 20,040 -> 48,620 |
| fish | eyes 30 % bigger with blue-brown irises and three highlights, softer arched brows, a longer smile curl, blush; twice the body stations and denser rings (smoother silhouette); soft lengthwise throat / belly pleats (`belly`); domed spots; fins and tail with more rays and rounder profiles. The mouth (jaw 55 deg, roof, floor, teeth, tongue) is unchanged and checked open in `preview_fish.png` / `preview_pose.png` | 16,488 -> 38,168 |

Scene: 52,680 + 48,620 + 38,168 = 139,468 character triangles + the coast set. Animation was rebaked from the new
models (`python3 pipeline/jn_animate.py all`: verify OK, 0 missing, FRESH OK; `jn_animate.py` itself untouched).
`jonah_kneel_pray` head top, measured on the rebaked `anim/jonah.glb`: max 0.2483 (frame 42), held 0.2414 (before the
polish 0.2486 / 0.2384), under the `belly` dome (~0.255). To keep it there the crown hair is 1.7 mm flatter and the
head-cloth knot sits low on the back of the head; the sandal straps and the wider coat lift him ~1 mm when he sits
on his heels. Do not raise the crown or the knot without re-measuring this clip. New part names: `locks headband
beardLocks coatTrim coatCollar beltFringe sandalL sandalR` (jonah), `wrapHem beardCurls sleeveHem vest vestEdge rope
bracelets sandalL sandalR` (captain); all are skinned into the `<char>_body` mesh, no new bones.

Weak / not done: the captain's rope coil reads a little like a ring from the front; Jonah's beard locks are a slightly
scaly pattern; the fish's belly pleats are subtle from the phone angle; the open-mouth decals (talk / shout) still
draw over the beard, as before; the captain's sash fell from 6.1 to 5.8 mm (the vest above it) and Jonah's face
from 6.1 to 5.8 mm (the head cloth over the forehead). Nothing was looked at on the phone or in Unity.

