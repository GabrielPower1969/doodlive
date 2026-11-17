# The King Who Serves — rigs (Characters role)

Built by `pipeline/ls_characters.py` (`python3 pipeline/ls_characters.py all`: faces, build + extras, proof, preview,
uvcheck, posetest, verify, compose). Models: `assets/lastsupper/model/{donkey,jesus,peter,john,james,andrew,seller1,
seller2}.glb` (character-local, no animations), `characters.blend` (the cast at their sheet slots, the extras off the
page at x 0.80 / 1.00 / 1.20 / 1.40 / 1.60), sheet data `regions_characters.json` + `id_characters_2x.{png,json}`,
the extras' fixed paint `extras_paint.png`, previews `preview_{donkey,jesus,peter,extras,all,uvcheck,pose,ride}.png`,
face decals `docs/lastsupper/design/faces/` (overview in `overview.png`).

## 0. How Jesus and Peter are shared with Real Miracles

`ls_characters.py` runs `pipeline/mi_characters.py` in its own namespace (definitions only, like `story_kit.include`)
and calls `build_jesus` / `build_peter` unchanged, then adds this pack's props. Nothing was copied and nothing in
`mi_*` or the kit was edited. Same heights, proportions, regions, palette and faces as Miracles. Consequences:

- A change to Jesus or Peter in `mi_characters.py` reaches this pack on the next `ls_characters.py all`.
- The Miracles `draw_faces` is reused through a source patch in memory at six anchors (asserted: if
  `mi_characters.py` changes those lines, `faces` fails loudly and does not drift). The Miracles decals are copied, not
  redrawn. Only `jesus_sad`, `peter_proud`, `peter_sheepish` and `peter_puzzled` are new.
- The extras use the Miracles `build_friend` body (unchanged) with this pack's costume added on top.
- `side_uv` / `side_texels` / `side_rotate` (the side-view method) are copied from `jn_characters.py`. Daniel and
  Jonah already hold identical copies; moving them into the kit would mean regenerating those packs (R5). Not done.

## 1. Measured (re-imported GLBs, `verify`)

| | donkey | jesus | peter | john | james | andrew | seller1 | seller2 |
|---|---|---|---|---|---|---|---|---|
| Triangles (budget) | 19,648 (20k) | 25,000 (25k, props 352) | 24,560 (25k, props 312) | 17,168 (18k) | 18,000 (18k) | 17,860 (18k) | 17,100 (18k) | 17,980 (18k) |
| Top (contract) | 0.2729 ear tips (0.27, +1.1 %) | 0.3553 (0.36, −1.3 %) | 0.3810 (0.38, +0.3 %) | 0.3325 (0.33) | 0.3584 (0.36) | 0.3682 (0.37) | 0.3289 (0.33) | 0.3481 (0.35, cap tip) |
| Lowest point | 0.0004 (hoof soles) | 0.0002 | 0.0002 | 0.0002 | 0.0002 | 0.0002 | 0.0002 | 0.0002 |

All eight: bones = CONTRACT §3 exactly (names and parents), 0 animations, ≤ 4 influences per vertex, UV0 = page
(or paint) projection, UV1 = decal layer. Donkey: **seat (blanket top above the root) y = 0.1552**, nose z = +0.165,
rump z ≈ −0.121, tail tip z ≈ −0.165 (nose to rump 0.286, about 2 % over 0.28).

## 2. Skeletons and props

Humans: kit skeleton, A-pose (arms 55° below horizontal), facing +Z, feet on y = 0. Donkey: CONTRACT §3 list, facing
+Z, root on the ground under the belly centre (= under the seat).

| Char | Extra bone | Parent | What it moves / shows | Default |
|---|---|---|---|---|
| jesus | `mantle1`, `belt1` | chest, hips | Miracles: mantle back drape, belt end | — |
| jesus | `towel` | hips | `jesus_towel`: white linen band round the hips over the mantle, end at the right hip | hidden |
| jesus | `basin` | root | `jesus_basin`: terracotta bowl, 0.08 across, on the floor at (0, 0, 0.06) at rest | hidden |
| jesus | `bread` | handL | `jesus_bread`: round flat loaf in the left palm | hidden |
| jesus | `cup` | handR | `jesus_cup`: clay cup with a foot in the right hand | hidden |
| peter | `cloth1` | head | Miracles: head-cloth tails | — |
| peter | `bucket` | handR | Miracles bone kept for one shared rig; **no mesh** in this pack | — |
| peter | `palm` | handR | `peter_palm`: frond, held upright, 0.12 tall above the fist | **shown** |
| peter | `towel` | chest | `peter_towel`: white strip over the left shoulder, back to front | hidden |
| peter | `jug` | handR | `peter_jug`: terracotta jug hanging from the fist by its handle | hidden |
| john | `sash1` | hips | the white sash end | — |
| james | `cloak1` | chest | the lower back of the brown cloak (over the left shoulder, down the back to the right hip) | — |
| andrew | `cloth1` | head | the tail of the blue-grey head cloth | — |
| seller1 | `apron1` | hips | the lower half of the striped apron | — |
| seller2 | `pouch` | hips | the money pouch on the belt (front right) | — |

Props are rigid meshes `<char>_<bone>` parented to their bone; node `<char>/<bone>` (e.g. `jesus/towel`).

- **Blink**: scale `eyelids` local Y from 1.0 (open) to **12.78** (closed); X/Z stay 1 (all eight).
- **Jaw**: humans as Miracles (chin and beard move; every open mouth is a decal). Donkey: `jaw` moves the lower muzzle
  (a separate cream blob, weight 1) and the bottom of the upper muzzle; the open bray mouth is the `heehaw` decal (C6).
- **Donkey legs**: front `upperArm → forearm → paw` (from chest), back `thigh → shin → foot` (from hips); bones run
  along the legs, so flexion = rotation about design X. Hooves are flat on y = 0.0004.
- **Donkey ears / tail**: `earL/R` from the head, the ear skinned to its bone above the base; `tail1 → tail2` from the
  hips, the dark tuft on `tail2`.

## 3. Fit tests (posetest, `preview_ride.png`; test poses, not clips)

- **Ride** (`pose_ride` in the script): Jesus at base `RIDE_Y` 0.12 on the donkey's mark and heading; hips head moved
  to rig-local (0, 0.035, −0.008); thighs −52° about X then ±34° about Z (spread), shins +58°. Knees and feet sit
  outside the barrel on both sides; lowest point 0.026 above the donkey's ground at rest, 0.020 / 0.032 at the walk's
  low / high point (seat ∓0.006). The barrel is ±0.039 wide at the seat. **Not perfect**: Jesus's long tunic and
  mantle hang as a skirt over the donkey's shoulders and flanks (the Miracles robe is skinned for standing; it is not
  split for straddling). From the phone it reads as riding; side-on the robe covers the donkey's front. Gaps between
  seat and blanket were not measured per vertex; check in the animator's pair probe.
- **Kneel with the basin** (`pose_kneel`, at base UPPER): the Miracles `kneel_kind` stance (left knee down, right foot
  forward). The basin sits flat (min y 0.0004). **Two problems for Animation**: (1) the right foot forward lands in the
  basin 0.06 in front: put the forward foot to the side (or kneel on both knees with the hips lower); (2) the long robe
  hem goes through the floor behind the kneeling leg in my test (min y −0.037); Miracles' `kneel_kind` reached −0.002
  with its `kneel_legs` helper, so use that helper, not my test numbers.
- **Kneel pair**: Jesus 0.11 in front of a seated John (bench seat UPPER + 0.04, John facing Jesus) — rendered, no
  measurement.

## 4. Expressions (`docs/lastsupper/design/faces/<char>_<expr>.png`, 512 px)

- jesus: `kind` (default), talk, smile, laugh, firm, gentle, look_up (copied from Miracles), **sad** (new)
- peter: `jolly` (default), talk, shock, laugh, amazed (copied), **proud, sheepish, puzzled** (new)
- donkey: `calm` (default), happy, heehaw, chew, sleepy. Decal = front projection on the head, eyes on a small flat
  "socket" plateau so the rigid lids lie on the surface over their whole travel (C1).
- john / james / andrew: `happy` (default), talk, proud, amazed, sheepish, laugh — one drawing per expression for the
  group, brows re-coloured per person (files per person).
- seller1 / seller2: `hawk` (default), talk, shock, wail, fluster (seller1 with rosy cheeks).

Clip → decal suggestions: `CLIP_EXPRESSION` in the script and `regions_characters.json` `faceDecal.clipExpression`.

## 5. Colour: regions, fixed colours, anchors

| Char | Printed regions | Fixed colour (decal swatch; UV0 anchored) | Anchored to the set (`design.json set.propAnchors`) |
|---|---|---|---|
| donkey | coat, muzzle, mane (mane, forelock, tail tuft, ear tips), blanket | `hooves` → coat, `gold` stripe → blanket | — |
| jesus | as Miracles: skin, hair (+ beard), tunic, mantle, belt | `sandals` → tunic | towel → `cloth`, basin + cup → `clay`, bread → `bread` |
| peter | as Miracles: skin, hair (+ beard), headcloth, tunic, vest, waistcloth | `sandals` → tunic, `rope` → waistcloth | **palm** (printed with Peter as line art) → `palmLeaf`; towel → `cloth`; jug → `clay` |

Donkey sheet note: printed in side view (left side, nose to −X), UV0 = mirrored side projection; faces not seen from
the side (muzzle front, inner ears, blanket top, eyelids) take one texel of their own region. Legs, ears, neck and
tail coat parts are slivers → `PART_ANCHORS` give them a texel of the body coat. No cream belly patch on the sheet
(it printed under 3 mm). The extras are not printed: UV0 → `extras_paint.png` (material `ls_extras_paint`).

Sheet check (`tools/story/sheet_lastsupper.py`): **SHEET PASS, anchors 103 / 103**. Printed regions below 6 mm (best
inscribed cell, px at 150 dpi; 6 mm = 35.4 px): donkey tail tuft (mane) 8.2, donkey mane 17.9; the Jesus / Peter ones
are the Miracles numbers (hair 7.2 / 10.0, beards ~18, Peter head cloth and waist cloth 16.0, Jesus belt 27.9, faces
~30). Hair-like parts are small on every sheet (C3).

## 6. Notes for Animation

- Ride pair: the donkey `walk` seat must stay within ±0.006 of 0.155 (the 0.1552 rest seat is measured).
- Jesus's bread and cup sit in the A-pose palms; turn the forearm (palm up) to show them. The basin rests on the floor
  at the root; for `rise_towel` move the `basin` bone up into the hands.
- Peter's jug hangs below the fist like the Miracles bucket; tip the hand forward to pour. The palm is upright above
  the right fist; `cheer` waves it overhead.
- Cloth bones: James's `cloak1` swings backward (+X rotation); `apron1`, `sash1`, `pouch` swing forward (−X).
- The extras share the Miracles friend body: thin forearms, the same hands; seller1 is wide (bodyX 1.30, belly).

## 7. Weak / not verified

- Ride: the long robe drapes over the donkey (no split skirt); feet hang ~0.03 above the ground; judged from renders.
- Kneel: forward foot meets the basin; robe hem below the floor in the test pose (see §3).
- Donkey closed eyes: the lids are a little narrower than the drawn eye, so a lash tip can peek out at the outer
  corner; a faint plateau bump shows round the eyes in raking light.
- Donkey inner ears read mostly cream from the front; the tail tuft and mane are under 6 mm on the sheet.
- Jesus is at exactly 25,000 triangles (props squeezed low-poly: 12-sided towel, 10-sided basin); nothing more fits.
- James is exactly 18,000 and seller2 17,980: to fit, the extras other than John lost the friend belt's hanging end,
  Andrew has no moustache, and seller2's beard is a goatee only.
- Nothing was looked at in Unity or on the phone.
