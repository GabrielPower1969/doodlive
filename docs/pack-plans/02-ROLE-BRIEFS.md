# Role briefs

One brief per role. Copy the brief into the agent's prompt, replace `<id>` `<xx>` `<SET>`, and add nothing else.
Every role: read `03-RULES.md` first; touch only the files `docs/<id>/CONTRACT.md` §1 gives you; finish with a
report of at most 300 words: files made, measured checks, what you looked at, what is weak, any deviation from the
contract with exact names.

## Characters

Read: `docs/<id>/CONTRACT.md` §2-3, `docs/<id>/DESIGN.md` §1 and §3, the docstring of
`pipeline/story_kit/characters.py`, then `pipeline/ru_characters.py` (the example on the kit).
Do:
1. Create `pipeline/<xx>_characters.py`: pack constants (`CHARS`, `SPEC`, `PALETTE`, `REGIONS`, `FACES`, `PROPS`,
   `EXTRA_BONES`, `ENV`, `PAGE_MATERIAL` …) and one builder per character; `story_kit.include(globals(),
   "characters")` gives everything else. `story_kit.missing(globals(), "characters")` lists what you still lack.
2. Draw the face decals (every expression in DESIGN §1).
3. `python3 pipeline/<xx>_characters.py all`.
4. Look at every preview PNG with your eyes (front, 3/4, side, back, each face, UV check, pose test). Fix and re-run.
5. Write `docs/<id>/RIG.md`: bones, props, expressions, anything the animator must know.
Quality: `05-QUALITY-BAR.md` §Characters. Pitfalls: `04-PITFALLS.md` C1-C8.
A non-human (fish, lion) is not in the kit: read the lion in `pipeline/da_characters.py` and build it inside your
script; do not add it to the kit unless a second pack needs it.

## Set + sheet

Read: `CONTRACT.md` §2 and §6, `DESIGN.md` §2-3, `storyboard/story.py` (marks and paths), the docstring of
`pipeline/story_kit/stage.py`, then `pipeline/ru_bethlehem.py`, then the docstring of `tools/story/make_sheet.py`.
Do:
1. Create `pipeline/<xx>_<SET>.py`: the set's pieces from the kit's primitives, every node named in CONTRACT §6,
   hidden props as separate nodes. `-- check` prints `CLEARANCE` for every mark and path.
2. `-- all`; look at the previews (phone view first).
3. Write the cast's sheet slots and the set drawings into `assets/<id>/design.json`.
4. When the character files exist: `python3 tools/story/make_sheet.py <id>`, then
   `python3 tools/story/make_colored_pdf.py <id>`.
5. Write `docs/<id>/SET.md`: nodes, measured clearances, region sizes, final slots.
Quality: §Set and §Sheet. Pitfalls: S1-S7.

## Animation

Read: `CONTRACT.md` §3-4, `storyboard/story.py`, `docs/<id>/RIG.md`, the docstring of
`pipeline/story_kit/animation.py`, then `pipeline/ru_animate.py`.
Do:
1. Create `pipeline/<xx>_animate.py`: one function per clip in CONTRACT §4 (every clip, exact names).
2. `python3 pipeline/<xx>_animate.py all`; probe single clips while you work.
3. Look at the contact sheet and at probes of every two-person clip, every kneel / sit, every travel clip.
4. Write `docs/<id>/ANIMATION.md`: clip table with lengths and speeds, markers, and a **"staging" section for the
   lead**: distances the clips assume, moves in `story.py` that are too fast or glide, clips that need a lead-in.
Quality: §Animation. Pitfalls: A1-A8.

## Voice

Read: `CONTRACT.md` §7, `STORY.md` (cast), `storyboard/story.py` (lines and `dir` notes), `docs/ruth/VOICE.md`
(method), `tools/story/cast_ruth.json` (shape).
Do:
1. Write `tools/story/cast_<id>.json`: one voice per role and language, with acting notes; interjections (哼, 唉,
   哇, laughs, shrieks) as their own short phrases.
2. `python3 tools/story/voice.py <id> gen`; `python3 tools/story/voice.py <id> check`.
3. `python3 tools/story/build_timeline.py <id>` (the play is now timed by the real clips).
4. Write `docs/<id>/VOICE.md`: the voice chosen per role and why (measured), and a **"listen first" list** of the
   lines you trust least.
Engines: Qwen3-TTS for Chinese **and English** (R7). Quality: §Voice. Pitfalls: V1-V5.

## Music + SFX

Read: `CONTRACT.md` §7, `DESIGN.md` §5, `assets/<id>/timeline.json` (after the voices), the docstring of
`tools/story/music_kit.py`, then `tools/story/music_ruth.py`.
Do: create `tools/story/music_<id>.py` (`import music_kit as me`): one score function per cue, one recipe per SFX;
run it; read the printed loudness and loop checks. Write `docs/<id>/MUSIC.md` with a "listen first" list.
Every melody is original. Quality: §Music. Pitfalls: M1-M4.

## FX

Read: `CONTRACT.md` §8, `DESIGN.md` §4, `docs/STORY-KIT.md` ("Manifests"), `StoryFxDaniel.cs` (a small example).
Do:
1. For every id `story.py` uses, confirm it exists (`grep -rn 'Id => "<id>"' unity/Assets/DoodLive/DavidGoliath/Fx/`).
2. Reused under another name → `fx.aliases` in `assets/<id>/manifest.json`. No C#.
3. Only the new ids listed in CONTRACT §8 → `StoryFx<Id>.cs`; register through the manifest (`fx.class`).
4. `Fx/Preview~/run.sh <id>` with a stand-in set; look at `fx_contact_<id>.png`.
5. Write `docs/<id>/FX.md` with timing suggestions for the lead.
Do not run the Unity editor. Quality: §FX. Pitfalls: F1-F4.

## Integration (lead)

Read: `docs/NEW-STORY.md` §6, `CONTRACT.md` §9, `01-LIFECYCLE.md` stages 6-8.
Do stages 6-8 in order. Ask the owner and every other active session before Unity or the phone (R4).
