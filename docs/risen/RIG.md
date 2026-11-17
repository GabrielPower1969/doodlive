# He Is Risen! — rigs (Characters role)

Built by `pipeline/rs_characters.py` (`python3 pipeline/rs_characters.py all`: faces, build + extras, proof, preview,
uvcheck, posetest, verify, compose). Models: `assets/risen/model/{angel,jesus,mary,peter,john,thomas,joanna}.glb`
(character-local, no animations), `characters.blend` (the cast at their sheet slots, the extras off the page at
x 0.80 / 1.00 / 1.20 / 1.40), sheet data `regions_characters.json` + `id_characters_2x.{png,json}`, the extras' fixed
paint `extras_paint.png`, previews `preview_{angel,jesus,mary,extras,all,uvcheck,pose,fit}.png`, face decals
`docs/risen/design/faces/` (overview in `overview.png`).

## 0. Reuse (CONTRACT §2 choice: option (a))

`rs_characters.py` runs `pipeline/ls_characters.py` in its own namespace (definitions only); that file itself runs
`pipeline/mi_characters.py` the same way. Nothing was copied, nothing in `mi_*`, `ls_*` or the kit was edited, and
nothing was moved into `story_kit/` (so no other pack has to regenerate).

- `jesus` = Miracles `build_jesus` unchanged + the `fish` prop. `peter` = Miracles `build_peter` unchanged, `bucket`
  mesh dropped (bone kept, as The King Who Serves). `john` = The King Who Serves `build_extra("john")` unchanged.
- `thomas` = Miracles `build_friend` unchanged + this pack's costume. `mary` / `joanna` = new `build_woman(costume)`
  (Ruth's female body numbers, kit `hood` veil). `angel` = new `build_angel` (King body, robe, sash, curls, wings).
- A change to Jesus / Peter in `mi_characters.py` or to John in `ls_characters.py` reaches this pack on the next
  `rs_characters.py all`. The patched Miracles face drawer is reused through the name hooks The King Who Serves
  exposes (`ls_face_params`, `LS_LOOK`, `LS_FACE_CHARS`, ...), rebound here.

## 1. Measured (re-imported GLBs, `verify`, 2026-11-18)

| | angel | jesus | mary | peter | john | thomas | joanna |
|---|---|---|---|---|---|---|---|
| Triangles (budget) | 22,344 (30k) | 24,794 (25k) | 20,710 (25k) | **24,248 (18k extra)** | 17,168 (18k) | 17,976 (18k) | 17,286 (18k) |
| Top (contract) | 0.3982 head (0.40); wings 0.460 (0.46) | 0.3553 (0.36, −1.3 %) | 0.3396 (0.34) | 0.3810 (0.38) | 0.3325 (0.33) | 0.3584 (0.36) | 0.3288 (0.33) |
| Lowest point | 0.0018 | 0.0002 | 0.0015 | 0.0002 | 0.0002 | 0.0002 | 0.0015 |

All seven: bones = CONTRACT §3 exactly (names and parents), 0 animations, ≤ 4 influences per vertex, UV0 = page (or
paint), UV1 = decal. **Peter is over the 18k extras budget** because he is the unchanged Miracles Peter (24.2k, as in
The King Who Serves where he was printed); reducing him would mean forking him. Lead's call.

## 2. Skeletons and props

Humans: kit skeleton, A-pose (arms 55° below horizontal), facing +Z, feet on y = 0. Props are rigid meshes
`<char>_<bone>` parented to their bone; node `<char>/<bone>`.

| Char | Extra bone | Parent | What it moves / shows | Default |
|---|---|---|---|---|
| jesus | `mantle1`, `belt1` | chest, hips | Miracles: mantle back drape, belt end | — |
| jesus | `fish` | handR | `jesus_fish`: grilled fish 0.05 long across the right palm, V tail | hidden |
| peter | `cloth1`, `bucket` | head, handR | head-cloth tails; `bucket` bone only, **no mesh** | — |
| john | `sash1` | hips | the white sash end | — |
| thomas | `cloak1` | chest | the lower back of the short cloak (both shoulders, down the back to the waist) | — |
| mary, joanna | `veil1` | head | the back of the veil (to the upper back) | — |
| mary, joanna | `sash1` | hips | the knot + hanging sash end at her left hip | — |
| mary, joanna | `jar` | handL | `<who>_jar`: round spice jar with lid, hanging by a cord from the left fist | hidden |
| angel | `sash1` | hips | the hanging end of the broad gold sash (his right hip) | — |
| angel | `wingL1` `wingR1` | chest | inner half of each wing (root at the shoulder blade) | — |
| angel | `wingL2` `wingR2` | wing*1 | outer half; fold it behind the inner half by rotating about its head (Y) | — |

- **Blink**: scale `eyelids` local Y from 1.0 (open) to **12.78** (closed); X/Z stay 1 (all seven).
- **Jaw**: as Miracles (chin / beard move; every open mouth is a decal, C6).
- **Wings**: rest = half-open, the sheet pose. `preview_pose.png` angel b: wing*1 −18°, wing*2 −95° about Y folds the
  outer half behind. `fit_angel_open`: wing*1 +30° about Z and +25° about Y, wing*2 +18° about Z spreads them wide
  (wings_open peak). Signs are for the left wing; mirror for the right.

## 3. Fit tests (`posetest`, `preview_fit.png`; test poses, not clips)

- **Angel on the stone** (stand-in disc 0.22 × 0.05 at (−0.17, 0.11, −0.285) + rock face at z −0.30; `garden.glb` not
  used): base y ANGEL_Y 0.185, rig at z **−0.263** (front half of the stone's flat top). Thighs −86° about X, shins
  +80°. To rest the seat on the stone top (lowest point over the stone 0.2205) the **hips head goes to rig-local
  y 0.069 (world 0.254)**, not 0.035: the robe and buttocks hang below the hip joint. Legs hang in front of the stone
  face (front-most z −0.098). **The wings touch the rock at rest**; swinging both wing*1 **8° forward** about Y (left
  −8°, right +8°) clears it (back of the wings z −0.294 > −0.30). Use that in every seated clip. Hands-on-the-edge was
  not refined (arms just hang a little outward).
- **Mary crying / turn_joy end**: a coarse arm search puts the finger roots 8-9 mm from the cheek point below the eyes;
  the eyes stay visible (A5) in both renders. Elbows flare out a lot with the wide sleeves; the animator may tuck them.
- **Peter stooping** (door top 0.34 at 0.08 in front, stand-in frame): hips down 0.03, knees bent, spine 30° + chest
  18°: top 0.323, the part beyond the door plane 0.320 < 0.34. His head-cloth tail lifts up over his back in this
  pose (cloth1 follows the head).
- **hold_hands spacing** Jesus / Mary at 0.11: rendered only, hands meet; not measured.

## 4. Expressions (`docs/risen/design/faces/<char>_<expr>.png`, 512 px)

- jesus: `kind` (default), talk, smile, laugh, gentle, look_up (copied from Miracles), **joy, chew** (new)
- peter: `jolly` (default), talk, shock, laugh, amazed (copied, Miracles), puzzled (copied, The King Who Serves),
  **sad, puff** (new)
- john: `happy` (default), talk, amazed, laugh (copied, The King Who Serves), **sad, shock** (new)
- thomas: `happy` (default), talk, amazed (the group drawings with Thomas's brows), **shock, doubt, awe** (new)
- mary: `gentle` (default), talk, sad, cry (two tear drops), gasp, joy (a tear on one cheek), amazed
- joanna: `gentle` (default), talk, sad, gasp, joy (Mary's drawings, re-coloured brows, older lashes / crow lines)
- angel: `smile` (default), talk, joy, kind

Clip → decal suggestions: `CLIP_EXPRESSION` in the script and `regions_characters.json` `faceDecal.clipExpression`.

## 5. Colour: regions, fixed colours, anchors

| Char | Printed regions | Fixed / anchored | Hidden props → set (`design.json set.propAnchors`) |
|---|---|---|---|
| angel | skin, hair, robe, sash, wings (feather rows are piece lines) | bare feet + hands → face skin | — |
| jesus | as Miracles: skin, hair (+ beard), tunic, mantle, belt | sandals → tunic (swatch) | fish → `props/fish` |
| mary | skin, hair, veil, dress | **sash → dress** (prints < 6 mm; detail line, DESIGN §1), sandals → dress | jar → `props/clay` |

Extras (not printed): UV0 → `extras_paint.png` (material `rs_extras_paint`), their ID render includes Joanna's jar so
it gets terracotta. Sheet (`tools/story/sheet_risen.py`): **SHEET PASS, anchors 35 / 35**. Printed regions below 6 mm
(best cell px at 150 dpi; 6 mm = 35.4 px): mary hair 6.3, jesus hair 10.0, angel hair 11.3, **mary veil 13.4** (seen
from the front the veil is two bands framing the face), jesus beard 17.9, jesus belt 27.9, jesus face 32.6.

## 6. Notes for Animation

- Seated angel: hips head to rig-local y ≈ 0.069 at base ANGEL_Y and wing*1 swung 8° forward (§3).
- Cloth bones: `veil1` swings back (−X), `sash1` forward (−X on the women, hanging end at the left hip), `cloak1`
  backward (+X).
- Jar hangs below the left fist on its cord; Mary's `gasp` keeps it in the left hand.
- The fish sits across the right palm; turn the forearm palm-up to show it, bring the hand to the mouth for the bite.

## 7. Weak / not verified

- Peter 24.2k vs the 18k extras budget (unchanged Miracles Peter).
- Mary's veil prints at 13.4 px (2.3 mm) best cell; her sash prints as a detail line in the dress colour.
- The faint horizontal line of the parked eyelid strip shows on all faces in raking light (also on the unchanged
  Miracles Jesus; kit behaviour).
- Angel seat, wing clearance and the stoop were measured against stand-ins, not `garden.glb`; the clips will differ.
- Wing shading shows soft dark streaks where the rows overlap (reads as feather rows); not judged on the phone.
- Nothing was looked at in Unity or on the phone.
