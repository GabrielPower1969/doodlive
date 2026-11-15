# Joseph: voice (zh + en)

All 31 lines in Mandarin and English (62 clips), Qwen3-TTS only (Apache-2.0, run locally; no `edge-tts`, R7).
Cast: `tools/story/cast_joseph.json` (best of 4 takes per line, 8 for four re-done lines; no extra logic, so no
`voice_joseph.py`). Clips: `assets/joseph/audio/voice/{zh,en}/`. Timeline re-timed: **271.0 s** (STORY.md target
3:45-4:15, so about 16 s over the top: the lead should decide on cuts or shorter pre-pauses).

## Voices (measured: median F0 per line, Hz; parselmouth `to_pitch_ac`, voicing threshold 0.55, floor 60, ceiling 450)

Fix pass 2026-11-15 (review: Pharaoh two kings, Jacob two octaves, Joseph 13 semitones, brother too high). Method:
VoiceDesign invents a new voice per take, so each affected line got 6-14 takes (new seeds), a hard pitch pin per role and per
line (`f0Hz` + `f0Weight`, tools/story/voice_exodus.py), deeper design texts, acting notes that no longer ask for "high",
and a friendly-for-children clause in every designed role (owner, 2026-11-15: warm, clear, never scary). Wrapper with the
GPU lock: `python3 tools/story/voice_joseph.py gen|check`; post-pass `tools/story/voice_polish.py joseph`.

| Role | Engine | zh before | zh after | en before | en after |
|---|---|---|---|---|---|
| narrator | Qwen `vivian` (unchanged) | 186-360 | unchanged (js_07 / js_29 re-taken for the name) | 215-359 | unchanged |
| joseph young (js_03/05/09) | VoiceDesign tenor | 205 / 189 / 285 | 187 / 198 / 218 | 194 / 235 / 274 | 208 / 234 / 225 |
| joseph adult (js_13/18/19/25/26/28) | same | 119-181 (median 133) | 135-208 (median 175) | 157-261 | 143-244 (median 168) |
| jacob (js_02/11/30) | VoiceDesign old, husky | 102 / 75 / 75 (a 22-semitone jump) | 143 / 86 / 100 | 128 / 101 / 138 | 111 / 131 / 144 |
| brother (js_04/06/23/27) | VoiceDesign baritone, not scary | 150 / 180 / 133 / 124 | 140 / 132 / 138 / 121 | 199 / 264 / 133 / 137 | 144 / 187 / 126 / 119 |
| pharaoh (js_16/17/20) | VoiceDesign, deep jolly bass | 283 / 125 / 289 (13 st) | 145 / 112 / 112 (4.6 st) | 233 / 178 / 269 | 179 / 120 / 141 |

Young to adult Joseph is now about 2-5 semitones (was 13): one person, a little lower and steadier. Pharaoh sits clearly below
adult Joseph (js_17 112 Hz then js_18 167 Hz, 7 semitones, was 125 vs 119). Jacob's remaining spread is mostly the tracker on the
creaky weeping line js_11. Pitch is the weakest cue between designed voices; timbre was not pinned (no `mfccRef`): listen.

Interjections (哼 / Hmph, 啊 / Aah, "做梦!" / "Dream on!") are separate phrases with their own acting note. The script
has no written chuckle or sob, and phrases may not add words, so Jacob's laugh (js_02, js_30) and weeping (js_11)
are only acted inside the neighbouring phrase: they may sound like plain speech.

### Fix log 2026-11-15

- js_19: NOT a stale file. `unity/Assets/DoodLive/Stories/joseph/Resources/Stories/joseph/voice/{zh,en}/*.wav` (what the build bundles) was
  byte-identical to `assets/joseph/audio/voice` for all 62 clips before this pass (cmp), and js_19's three phrases correlate with the
  demo audio at one consistent start (135.13 s; per-phrase correlation 0.87 / 0.62 / 0.93). The low whole-clip score (0.33-0.45) came
  from the music / SFX under the middle phrase and a 20 ms drift, not from another take. After this pass the Unity copies are stale
  by design: the normal build step (DGSetup / the copy the build does) refreshes them; the build was not run.
- Names: js_07 and js_29 re-taken (10 takes, new seeds) until the final clip transcribes 约瑟 (js_29 pick 7: takes 2, 5, 7 passed the
  final check, take 4 passed the in-loop check only). js_02 (Jacob's first word) is still heard as 月色 in every take.
- Silence: no clip has leading / trailing digital silence over 0.25 s; mid-line digital zero (the js_13 "dropouts" and every phrase
  gap) is now -74 dBFS room tone (`voice_polish.py`; a pause over 0.8 s is cut to 0.8 s); 0 clips have a zero run over 60 ms.
  (-66 dBFS made whisper hear "呼呼呼" in Jonah jn_13, hence -74.)
- No line text changed for Joseph (FIXLOG-20261115.md); timeline re-timed by build_timeline.py: 270.14 s.

## Checks (`voice.py joseph check --asr`)

- All 62 clips: -16.6 to -15.9 LUFS (zh), -16.2 to -16.0 (en); true peak at most -1.5 dBTP.
- Transcript error: zh max 0.074, en max 0.059 (limit 0.1). Names heard right everywhere after re-takes:
  约瑟 (js_30 first came out 月色: short word at the start; re-take fixed), 雅各, 法老, 埃及. Homophone risk only
  for the ears: 约瑟 yuē sè, 雅各 yǎ gè.
- Check table shows `MAX`/`GAP` overruns on about 20 clips: expected, build_timeline.py re-timed the play to the
  real clips. It warned: `joseph carry_work at 84.19s needs 6.9s ... next beat after 0.1s` (animation, lead).

## Listen first (trusted least)

1. **Pharaoh en js_16** (179 Hz, the startled "Aah!" line) against js_17 120 Hz: the one pitch gap left. Pharaoh zh is now 112-145 Hz.
2. **Jacob zh**: js_02 (143 Hz) against js_11 (86) and js_30 (100): same old man? Timbre not pinned.
3. **js_11 and js_30 weeping / laughing** in both languages (acted only, see above).
4. **Joseph young vs governor**: js_09 (285 Hz, frightened) against js_13 (123 Hz) in zh: one person?
5. **Brother en js_06** (261 Hz, shouting) next to js_23 (131 Hz).
6. **Narrator en** (vivian speaking English): accent and warmth; js_21 (359 Hz) and zh js_29 (360 Hz) read high.
7. **js_28** (the heart of the story) both languages: slow enough?
Nobody has listened yet (V5).

### Round 3 (2026-11-15, REVIEW2): names and Jacob js_02 (Joseph part)

Tools: `hnrMin` (3 points per dB under it, measured on the dry take) and `nameContour` (first syllable pitch contour from whisper word
timestamps: a falling syllable, yuè, loses 6 points per semitone of fall; yuē is high and level) in tools/story/voice_exodus.py; God's hall
wet 0.20 -> 0.14 (reverb lowers HNR); the name is its own phrase "约拿，" with the direction "第一声 yuē，高而平".

| Item | Before | After |
|---|---|---|

Joseph part: see the table of the Jonah VOICE.md round 3: Jacob F0 143 / 86 / 100 -> 105 / 85 / 105, 约瑟 heard right in js_02 / 11 / 30 (was 月色), contours js_02 +3.8, js_11 +1.1, js_30 +5.1 st.
