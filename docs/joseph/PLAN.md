# Joseph — pack plan (this pack's index)

Shared instructions: `docs/pack-plans/00-INDEX.md`. This page holds only what is specific to Joseph.

Ids: story `joseph` · prefix `js` · env `JS_` · set `twolands` · line ids `js_01…js_31` · 12 shots · estimate 4:17
(target ≤ 4:15: if the real voices run long, the first cuts are `js_07`, `js_14` and `js_21`).

## State

| Stage | State |
|---|---|
| 1 Plan | done: `STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md`; `build_timeline.py joseph` runs |
| Gate 1 (script) | **waiting for the owner** |
| 2-8 | not started |

## What is new or risky in this pack (read before you start your role)

| # | Thing | Who | What to do |
|---|---|---|---|
| 1 | **One Joseph, three looks** by props: `coat` (shown at start, printed on the sheet), `nemes` + `collar` (hidden at start). | Characters, Lead | CONTRACT §3. The coat is a prop mesh skinned to the body; it is the only prop in any pack that is visible on the sheet. Check how `PROPS` / hidden props work in `pipeline/story_kit/characters.py` and make the coat a prop that is *not* left out of the ID render. |
| 2 | **The head-cloth and collar wear the coat's colours** (hidden props take UVs from `coat1…coat5`). | Characters | This is intended (DESIGN §1). Show it in the UV proof. |
| 3 | **Five coat stripes as five regions**, each ≥ 6 mm on the sheet. | Characters, Sheet | Joseph is 0.34 tall; the coat front is about 0.12 wide on the sheet, so five stripes are tight: use wide sleeves and let stripes run onto them; measure. If five do not reach 6 mm, use four and tell the lead. |
| 4 | **Four humans on the sheet.** | Sheet | Three in the front row at −0.34 / 0 / +0.34; Jacob on a second row (CONTRACT §2). |
| 5 | **Dream clouds are set props**, colourable, hidden, floating at h ≈ 0.46-0.52. | Set | Flat reliefs facing the camera. `dreamSheaves2` reuses `dreamSheaves`' sheet regions. |
| 6 | **Walking into the well and the cell.** | Set, Lead | The director moves actors in straight lines: keep the well rim at 0.08 and leave the cell open toward the viewer. |
| 7 | **Two-person clips**: `give_coat`, `grab_coat`, `lift_up`, `hug` ×3 pairs, `crown_him`. | Animation | All assume 0.11-0.12 between the two; probe each pair. Markers `off` (coat, head-cloth) and `on` (crowning) drive the prop events: report their times so the lead aligns `story.py`. |
| 8 | **Joseph ages 20 years** with one face. | Voice | Same voice; lighter and quicker in S01-S03, calmer and lower from S04. Put it in the acting notes, not in two voices. |
| 9 | **One new effect** in C#. | FX | Only `dream_cloud`. Everything else exists. |
| 10 | **Pharaoh** shares the cast id of the Exodus pack's villain. | Voice, Lead | A different person: comic and generous. The name plate "法老 / Pharaoh" is the same and is fine. |

## Decisions already made (do not reopen without the owner)

- One `brother` stands for the ten.
- No Potiphar's wife, no baker, no silver cup, no blood on the coat.
- The dream of the cows shows three fat and three skinny cows (colourable size); the narrator says seven.
- 50:20 is spoken at the reveal.
- English voices: Qwen3-TTS only.

## Order of work for this pack

1. Gate 1 with the owner (script).
2. Characters (Joseph with the coat first: it is the risk) and Set drafts → Gate 2.
3. Characters final ‖ Set + sheet final.
4. Animation ‖ Voice ‖ FX. Then the lead applies the animator's staging notes and marker times.
5. Music + SFX.
6. Integration → 7. Device → Gate 3 → 8. Ship.
