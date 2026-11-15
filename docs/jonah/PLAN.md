# Jonah — pack plan (this pack's index)

Shared instructions: `docs/pack-plans/00-INDEX.md`. This page holds only what is specific to Jonah.

Ids: story `jonah` · prefix `jn` · env `JN_` · set `coast` · line ids `jn_01…jn_29` · 12 shots · estimate 4:00
(target ≤ 3:45: if the real voices run long, the first cuts are `jn_06`, `jn_15` and the second half of `jn_26`).

## State

| Stage | State |
|---|---|
| 1 Plan | done: `STORY.md`, `storyboard/story.py`, `DESIGN.md`, `CONTRACT.md`; `build_timeline.py jonah` runs |
| Gate 1 (script) | **waiting for the owner** |
| 2-8 | not started |

## What is new or risky in this pack (read before you start your role)

| # | Thing | Who | What to do |
|---|---|---|---|
| 1 | **The fish**: a new rig type (no legs, body chain, a jaw that opens 55°, fins). Not in the kit. | Characters, Animation | Model it on Daniel's lion (`pipeline/da_characters.py`: side-view UV, own builder). Bones in CONTRACT §3. Build it inside `jn_characters.py`. |
| 2 | **Actors on a raised deck** (y = 0.10) on a ship that rocks. | Set, Animation, Lead | The ship's `shipRock` action must be gentle (±3°) because actors do not follow it. Deck marks in CONTRACT §6. |
| 3 | **Three places on one page** (sea + ship, beach, city + hill). | Set | Keep the ship and its mast at the back-left, the hill at the front-right, the middle open. The fish needs a clear lane in the front-left water. |
| 4 | **Jonah is swallowed**: he must vanish and come back. | Lead | He is parked off the page (`PARK`) after `fall_in` and reappears with `tumble_out`. No engine change. |
| 5 | **Inside the fish** is a set prop (`belly`) plus a stage tint (`deep_glow`), not a second set. | Set, FX | The dome is open toward the viewer; the tint hides the rest of the page. |
| 6 | **The plant has three states** as three nodes at one place, plus a `worm`. | Set, Lead | Only one state visible at a time (prop events in `story.py` S11). |
| 7 | **Jonah has 24 clips**, eight of them seated. | Animation | Do the seated family from one base pose. Seated clips rest the hips on the ground / hill (top y ≤ 0.04). |
| 8 | **God's voice** must match the Exodus pack's `god` in Chinese; the English one there used `edge-tts`. | Voice | Chinese: reuse the design in `tools/story/cast_exodus.json`. English: design a Qwen voice from the same description. |
| 9 | **A crowd line** (`people`, `jn_22`). | Voice | 8-10 layered voices incl. two children, staggered; see how Ruth's reapers were done (`docs/ruth/VOICE.md`). |
| 10 | **Four new effects** in C#. | FX | Only `storm_rain`, `bubbles`, `deep_glow`, `sun_scorch`. Everything else exists or is an alias. |

## Decisions already made (do not reopen without the owner)

- Cast on the sheet: Jonah, the captain, the fish. No king, no sailors' crowd, no worm on the sheet.
- The fish is friendly and comic, not a whale and not a shark.
- The story ends on God's question plus one narrator sentence.
- English voices: Qwen3-TTS only.

## Order of work for this pack

1. Gate 1 with the owner (script).
2. Characters (the fish first: it is the risk) and Set drafts → Gate 2.
3. Characters final ‖ Set + sheet final.
4. Animation ‖ Voice ‖ FX. Then the lead applies the animator's staging notes.
5. Music + SFX.
6. Integration → 7. Device → Gate 3 → 8. Ship.
