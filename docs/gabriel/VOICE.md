# Gabriel: voice (zh + en)

All 9 lines of `assets/gabriel/timeline.json` in Mandarin and English, 18 clips. Brief (CONTRACT.md §1, §7; STORY.md):
the narrator is the same storyteller as every other pack; Gabriel is a warm young heroic baritone, strong and gentle,
smiling, an archangel who kneels down to talk to a small child: never booming or scary, never robotic; **not**
`uncle_fu` (Esther's king, Boaz, King Darius) and **not** Daniel's voice. Method as Daniel (docs/daniel/VOICE.md):
Qwen3-TTS best-of-N with acting notes, real breaths, selection **by measurement, not by ear**. Nobody has listened
to these clips yet: read "Listen first".

## Files

```
tools/story/voice_gabriel.py   this pack's entry point: runs voice.py with run-time additions (below); the shared
                               voice.py / voice_extras.py stay byte-identical
tools/story/cast_gabriel.json  cast per language + role, per-line acting notes (m / m_en), pictures (d / d_en),
                               phrases, breaths, picks with reasons
assets/gabriel/audio/voice/
  zh/<id>.wav en/<id>.wav      44.1 kHz mono 16-bit, -16 LUFS, true peak <= -1.5 dBTP   (Unity)
  zh/<id>.mp3 en/<id>.mp3      96 kbps mono                                               (web)
  durations.json sources.json report.json zh.srt en.srt     report has whisper + Praat measures of every clip
  breaths/                     real in-breaths cut from this pack's own Qwen takes (breaths.json)
  record/zh/ record/en/        recording sheets for people (`voice_gabriel.py gabriel session`), book names in Chinese
```

`voice_gabriel.py` adds, only for this pack:

1. **Timbre pinning** `mfccRef` / `mfccTol` / `mfccWeight` (Daniel's; a weak measure, breaks ties only).
2. **`hnrMin`**: a clean-voice floor (mean harmonics-to-noise ratio, dB). Gabriel is young and clear; a husky take
   loses 1 point per dB under it. (`voice_extras.py` only has the opposite gate, for old voices.)
3. **`consistent`**: VoiceDesign invents the speaker again on every take, and `voice.py` picks each line on its own.
   This command looks at all cached takes of the role at once and returns the one-take-per-line set that is closest
   to one man (timbre fingerprint + pitch, livelier takes preferred, only takes that pass the words / pitch-window /
   pace / clean-voice gates). `--write` stores the picks (`pick`, `pickWhy`) and the set's fingerprint in the cast.
4. **Mandarin compared by sound**: whisper writes 加百列 as 加百烈, 马利亚 as 玛利亚, 他 as 她, 飞去 as 非去 (the same
   syllables and tones). The shared character error rate counts those as mistakes, and they were knocking correct
   takes out. Here the zh error rate is the edit distance over pinyin syllables **with tones** (pypinyin), so a
   homophone is no error and a real slip still is (the audition's 加倍力, or 看过 for 看顾).
5. **`refZh`**: 启示录 / 路加福音 / 但以理书 / 以赛亚书 / 诗篇 on the zh recording sheet.

## Cast

| Role | zh | en | fx |
|---|---|---|---|
| Narrator | Qwen CustomVoice **`vivian`**, best of 4 (the storyteller of every pack) | edge **en-US-AvaMultilingualNeural**, phrased (the narrator of every pack) | plain |
| Gabriel | Qwen **VoiceDesign** "二十八岁左右，高大的年轻人。醇厚、温暖、有磁性的男中音，声音干净明亮、不沙哑，阳光、真诚、爱笑，像英雄大哥哥蹲下来轻声跟小朋友说话，绝不吼叫", 16 takes per line, pinned 130-172 Hz, one-man set | Qwen **VoiceDesign** "about thirty, a young warrior. A low-pitched, deep, warm baritone with a full chest, clean and steady, never husky; noble and strong, he smiles as he speaks and is very gentle with little children; never shouting", 6-12 takes per line, pinned 105-150 Hz, one-man set | warm |

No voice plays two roles; Gabriel is neither `uncle_fu` nor Daniel's design (zh) nor `ryan` (Daniel en), William
(the kings, God), Andrew or Brian (Boaz, the two brothers).

Real breaths (harvested from this pack's takes): ga_01 before, both languages. Gabriel's lines are spoken whole (no
phrase splitting): with VoiceDesign every phrase would be a new speaker.

## How Gabriel's voice was chosen (2026-11-14)

Audition: each candidate spoke 3 real lines (ga_02, ga_05, ga_07), one take each, measured with mlx-whisper
large-v3-turbo + Praat; 93 clips, thrown away. Means over the 3 lines. F0 = lowest-highest clip median (one person
stays narrow); MFCC spread = mean distance of each clip's fingerprint from the candidate's mean (a fixed edge voice
gives 17-35); "to Daniel" = fingerprint distance from Daniel's zh voice (small = sounds like him).

| Lang | Candidate | F0 SD st | err | F0 median Hz | HNR dB | MFCC spread | to Daniel | Verdict |
|---|---|---|---|---|---|---|---|---|
| zh | **VoiceDesign E** (seeds 0 / 1 / 2) | 5.75 / 4.97 / 6.43 | 0.04 | 95-188 / **139-189** / 103-282 | 7.5 / 9.3 / 7.6 | 67 / 46 / 71 | 84 / 67 / 108 | kept, pinned: the only design with takes in a young-baritone range that are clean |
| zh | VoiceDesign A, B, C ("young hero", "knight", "warrior") | 5.2-5.8 | 0.05 | 135-278 | 7.4-9.3 | 43-76 | 84-116 | tenor most of the time, drifts an octave |
| zh | VoiceDesign D ("低沉、醇厚、音调低") | 6.15 / 4.40 | 0.05 | 86-113 / 84-101 | 6.7 / 7.1 | 57 / 35 | **61 / 49** | deep and husky: Daniel's register and the nearest to his timbre; "booming" |
| zh | Qwen eric | 4.53 | 0.07 | 137-159 | 14.2 | 48 | 103 | steady and clean, but says the hero's name wrong (加倍力) and ran away to 12 s on ga_07 |
| zh | edge Yunxi | 5.07 | 0.04 | 159-174 | 10.1 | 35 | 101 | one person, but one flat read per call (the "AI narrator" sound); not a baritone |
| zh | edge Yunjian / Yunyang | 4.84 / 5.59 | 0.02 | 107-121 / 104-123 | 7.6 / 7.2 | 28 / 30 | 85 / 153 | Daniel's pitch; Yunjian is Ruth's reaper, Yunyang is Mordecai |
| en | **VoiceDesign C** (seeds 0 / 1 / 2) | 4.01 / 4.13 / 4.81 | 0.00 | 110-162 / **117-136** / 110-138 | 11.1 / 14.0 / 12.8 | 45 / 44 / 51 | 40-74 | kept: the only designed voice that stayed in one register on every seed; warm, clean |
| en | VoiceDesign A, B, D | 3.9-5.7 | 0.00 | 123-269 | 12-14 | 32-71 | 56-95 | too high (171-269 Hz) or drifting |
| en | edge GB Ryan | 6.16 | 0.00 | 122-137 | 10.0 | 23 | 146 | the liveliest edge voice; kept as the fallback (see "Listen first" 2) |
| en | edge Guy / Andrew ML / Roger | 4.74 / 4.69 / 4.31 | 0.00 | 151-158 / 108-126 / 121-152 | 10.5-11.9 | 22-28 | 137-223 | flat per call; Andrew is Boaz and the elder brother |
| en | edge Steffan / Brian ML / Eric | 2.86 / 2.93 / 3.46 | 0.00 | 123-134 / 127-128 / 107-112 | 11-13 | 17-23 | 104-164 | the flattest (F0 SD under 3.5 st): robotic |

What the measurements say about VoiceDesign: it does not hold a pitch. On one line the same description gave
95 Hz and 264 Hz on two seeds, and the excited lines (ga_06, ga_08) come out at 210-315 Hz on most takes. So the
zh role got 16 takes per line, the pitch window, the clean-voice floor, and the `consistent` pick over all takes
at once. Passing takes per line (of 16): 4, 3, 5, 7, **1**, 4, **1** (ga_06 and ga_08 had exactly one).

## Final clips (`report.json`, `check --asr`)

| Role | lang | lines | F0 SD st | range st | err | median F0 Hz (min-max per line) | pace |
|---|---|---|---|---|---|---|---|
| narrator | zh | 2 | 5.39 | 16.7 | 0.000 | 279 (238-321) | 3.31 ch/s |
| gabriel | zh | 7 | 6.09 | 19.1 | 0.000 | **152 (141-183)** | 3.77 |
| narrator | en | 2 | 5.04 | 17.9 | 0.000 | 200 (190-211) | 2.81 syl/s |
| gabriel | en | 7 | 3.99 | 12.7 | 0.036* | **125 (112-142)** | 3.39 |

\* one line: whisper spells ga_08 "color ... favorite colors" (US), the script says "colour ... favourite colours":
3 of 12 words, not a speech error. Every other en line is 0.00.

| Line | zh s | zh F0 | en s | en F0 | zh take / en take |
|---|---|---|---|---|---|
| ga_01 narrator | 9.66 | 238 | 10.43 | 211 | vivian take 0 of 4 + breath / edge, 5 phrases + breath |
| ga_02 | 5.23 | 167 | 5.60 | 131 | 2 of 16 / 8 of 12 |
| ga_03 | 4.40 | 152 | 3.87 | 125 | 0 / 2 of 6 |
| ga_04 | 6.30 | 150 | 6.78 | 142 | 6 / 0 |
| ga_05 | 8.61 | 141 | 8.71 | 112 | 14 / 0 |
| ga_06 | 2.59 | 183 | 4.19 | 126 | 8 / 5 of 12 |
| ga_07 | 6.97 | 147 | 5.79 | 121 | 5 / 1 |
| ga_08 | 4.27 | 164 | 4.92 | 117 | 1 / 9 of 12 |
| ga_09 narrator | 6.24 | 321 | 5.85 | 190 | vivian take 3 of 4 / edge, 3 phrases |

One-man sets: zh F0 141-183 Hz across the 7 lines (4.4 semitones; without the excited ga_06, 141-167 = 2.9),
mean fingerprint distance to the set 54; en 112-142 Hz (4.1 semitones), distance 44. For scale (Daniel's
calibration): the same speaker on another line measures 25-73, another person 53-150.

Names, as whisper heard them: 加百列 exactly (ga_01, ga_02, ga_09), 但以理 exactly, 马利亚 as 玛利亚 (same sound),
耶稣 exactly, 看顾 exactly; Gabriel, Daniel, Mary, Jesus exactly. No `sayMap` was needed.

Loudness: every clip −16.0 to −16.2 LUFS, true peak −1.8 to −2.1 dBTP.

Totals: **zh 54.3 s, en 56.1 s** of speech. `build_timeline.py gabriel`: the play went from 86.63 s (estimate) to
**86.79 s** (timed from the voices); `voice_gabriel.py gabriel check`: all clips fit and leave ≥ 0.2 s.

## Listen first

1. **Is zh Gabriel one man?** He is 7 separately invented takes that passed the gates and were picked to be as
   alike as possible (141-183 Hz). Play ga_02 to ga_08 in a row. If he changes, the real fix is the Qwen3-TTS
   **Base** model (clone one good take, e.g. ga_02 or ga_07, for every line); it is not on this Mac (a download
   of a few GB, and the disk had 6 GB free), so it was not done.
2. **zh Gabriel is a light, young baritone** (median 152 Hz), not a deep one: the deep design (D) was Daniel's
   register and husky. If he should be deeper, lower `f0Hz` to [115, 150] and generate more takes.
3. **zh ga_06** "这是全世界最好的消息！听——" (2.6 s): the only take of 16 inside the window, and the breathiest clip
   (HNR 5.1 dB); the hushed, drawn-out 听 the note asks for may be a plain 听. `"seed": 16` under
   `lines.ga_06.zh` gives 16 new takes (remove its `pick` first).
4. **zh ga_08** (HNR 6.9 dB): also the only passing take; check it is not hoarse.
5. **en ga_05** is the lowest line (112 Hz) and ga_04 the highest (142 Hz): the two ends of his range, next to each
   other in the play.
6. **en Gabriel's liveliness** measures 4.0 semitones F0 SD, calmer than zh (6.1): warm and steady, but check he
   does not sound sleepy on ga_06 ("It's the best news in the whole world! Listen...", 4.2 s). Fallback with more
   movement and a fixed speaker: edge en-GB-RyanNeural, phrased.
7. **ga_01 narrator breaths** were added before the first word in both languages (the en one is borrowed from the
   zh narrator's takes, as in the other packs).

## Regenerate

```bash
export DOODLIVE_VOICE_CACHE=/tmp/gabriel_audio/cache             # raw Qwen takes (deleted after this run)
python3 tools/story/voice_gabriel.py gabriel gen                 # 18 clips, about 1 h on the 16 GB M1 Pro; one Qwen job at a time
python3 tools/story/voice_gabriel.py gabriel consistent --write  # re-pick Gabriel's one-man sets from the cached takes
python3 tools/story/voice_gabriel.py gabriel gen                 # renders the picks (cached, minutes)
python3 tools/story/voice_gabriel.py gabriel harvest             # breath library, then gen --only ga_01 again
python3 tools/story/build_timeline.py gabriel && python3 tools/story/voice_gabriel.py gabriel check --asr
python3 tools/story/music_gabriel.py                             # the score follows the new times
python3 tools/story/voice_gabriel.py gabriel session             # recording sheets; `import <dir> --lang zh` takes people's recordings
```

Take seeds are fixed, but MLX sampling is not bit-reproducible across machines: the `pick` numbers in the cast file
refer to this run's takes. After an uncached regeneration remove them (or run `consistent --write`, which
overwrites them).
