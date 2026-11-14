# Daniel: voice (zh + en)

All 29 lines of `assets/daniel/timeline.json` in Mandarin and English, 58 clips. Brief (CONTRACT.md §7): people telling
a story to a 4-10-year-old, not text being read; distinct, consistent timbres; Daniel calm and warm and **not** Boaz's
or the Esther king's voice; King Darius big and round, comic when fretting; the official nasal, whiny, sly, **not**
Haman's `dylan`, with a cartoon shriek on da_27; interjections (哼, 嘿嘿, 唉, 嗯, 呃) performed as sounds. Ruth's
method (docs/ruth/VOICE.md) is the floor: Qwen3-TTS best-of-N with acting notes, VoiceDesign where no stock voice
fits, real breaths, selection **by measurement, not by ear**. So listen to "Listen first" before shipping.

## Files

```
tools/story/voice_daniel.py    Daniel's entry point: runs voice.py with three run-time additions (below), so the shared
                               voice.py / voice_extras.py stay byte-identical (Esther, Ruth, Exodus unaffected)
tools/story/cast_daniel.json   cast per language + role, per-line acting notes (m / m_en), pictures (d / d_en),
                               phrases, breaths, picks with reasons
assets/daniel/audio/voice/
  zh/<id>.wav en/<id>.wav      44.1 kHz mono 16-bit, -16 LUFS (+-0.4), true peak <= -1.5 dBTP   (Unity)
  zh/<id>.mp3 en/<id>.mp3      96 kbps mono                                                       (web)
  durations.json sources.json report.json zh.srt en.srt     as Ruth (report has whisper + Praat measures)
  breaths/                     real in-breaths cut from this pack's own Qwen takes (breaths.json)
  record/zh/ record/en/        recording sheets for people (`voice_daniel.py daniel session`), book names in Chinese
```

`voice_daniel.py` adds, only for this pack:

1. **`shriek` acting measure** (`lines.da_27.<lang>.acting`): pitch of the scream above the official's speaking voice
   (`baseHz`), longest held voiced scream, loudness of the scream against the "help" after it; score 0-5.
2. **Timbre pinning** `mfccRef` / `mfccTol` / `mfccWeight` on a VoiceDesign role: distance of a take's mean MFCC 1-12
   (speech frames) from the audition reference. Calibration showed it is a **weak** speaker measure (same speaker,
   other line: 25-73; another person: 53-150), so it only breaks ties (0.04 points per unit over 50); the pitch window
   `f0Hz` (voice_extras.py, Ruth's) does the real pinning.
3. **`refZh`**: 但以理书 / 诗篇 / 腓立比书 on the zh recording sheet.

It also caps MLX's buffer cache (768 MB) and honours `DOODLIVE_VOICE_CACHE` (where raw Qwen takes are kept).

## Cast

| Role | zh | en | fx |
|---|---|---|---|
| Narrator | Qwen CustomVoice **`vivian`**, best of 4 (the family storyteller of Esther and Ruth) | edge **en-US-AvaMultilingualNeural**, phrased (Esther / Ruth narrator) | plain |
| Daniel | Qwen **VoiceDesign** "三十五岁左右，温暖、沉稳的男中音……像一位温和的大哥哥", best of 6, pinned 95-150 Hz (95-200 on da_23) | Qwen CustomVoice **`ryan`**, calm-warm note, best of 4 | plain / warm |
| King Darius | Qwen CustomVoice **`uncle_fu`**, big-round-comic king note, best of 5; sighs, 嗯 and the whimper as their own phrases | edge **en-AU-WilliamMultilingualNeural**, phrased (comic beats in their own phrases), breaths borrowed from zh king | warm |
| Official | Qwen **VoiceDesign** "瘦高个大臣，嗓音尖细、鼻音很重、哼哼唧唧的男高音……滑稽的小坏蛋", best of 5-8, pinned 190-330 Hz | Qwen CustomVoice **`aiden`**, sly-whiny cartoon-villain note, best of 5-6 | nasal |

No voice plays two roles in a language; Daniel is neither uncle_fu (Boaz, Esther's king) nor Andrew / Christopher
(Boaz en, Esther king en); the official is neither dylan nor Yunxi / Ryan (Haman old and new).

Interjections are separate phrases with their own acting note (Haman's trick): da_04 哼 / "Hmph!", da_05 嘿嘿 /
"Heh heh.", da_10 嘿嘿嘿 / "Heh heh heh,", da_07 嗯…… / "Hmm...", da_14 and da_21 唉…… / "Oh..." / "Oh dear...", the
whimpered second 睡不着 / "I just can't sleep!", da_27 哇啊啊—— / "Waaah!" then 救命啊 / "Help!" with a 0.9 s tail that
carries the voice away (`tail`). Real breaths (harvested from the Qwen takes): da_01 / da_18 before, da_08 after
这条法令 / "new law", da_09 after 新法令 / "new law", da_16 and da_22 before (king, out of breath), da_19 en after
"mouths", da_29 after 祷告 / "praying".

## How the voices were chosen (2026-11-14)

Audition: each candidate spoke 3 real lines of its role (Daniel da_03 / da_17 / da_23, king da_07 / da_21 / da_28,
official da_04 / da_13 / da_27), one take each, measured with mlx-whisper large-v3-turbo + Praat. 99 clips, thrown away.
Means over the 3 lines; F0 range = lowest-highest clip median (one person stays narrow); MFCC spread = mean distance
of each clip's fingerprint from the candidate's mean (edge voices, one fixed person, give 18-25).

| Role, lang | Candidate | F0 SD st | err | F0 median Hz | HNR dB | MFCC spread | verdict |
|---|---|---|---|---|---|---|---|
| daniel zh | **VoiceDesign A seed 0** | 4.89 | 0.04 | **109-127** | 7.4 | 35 | kept: warm, breathy, narrow |
| | VoiceDesign A seed 1 | 5.26 | 0.01 | 88-116 | 7.3 | 37 | deeper, very rough on da_03 (HNR 4.3) |
| | Qwen eric | 4.36 | 0.09 | 144-184 | 11.2 | 43 | Sichuan accent: 封住→缝组, 狮子→十字 |
| | edge Yunjian / Yunyang | 6.25 / 5.44 | 0.01 | 108-134 / 119-136 | 7.2 | 19 / 25 | steady but one flat read per call (the "AI" sound); Yunjian is Ruth's reaper lead |
| king zh | **Qwen uncle_fu** | 6.88 | 0.21* | **146-161** | 7.6 | 40 | the only male that stayed one person |
| | VoiceDesign king seeds 0 / 1 | 5.46 / 7.10 | 0.10 / 0.12 | 123-262 / 119-245 | 9.7-11.3 | 65-73 | drifts an octave between lines |
| official zh | **VoiceDesign B seed 1** | 4.72 | 0.13* | 235-373 | 17.7 | 89 | nasal, high; kept |
| | VoiceDesign B seed 0 | 5.60 | 0.18* | 191-395 | 15.7 | 145 | |
| | edge Yunxi (Haman's old voice) | 4.99 | 0.25 | 160-356 | 9.2 | 100 | excluded anyway |
| daniel en | **Qwen ryan** | 4.10 | 0.00 | 114-226 | 13.9 | 56 | fixed speaker that acts |
| | Qwen aiden | 4.06 | 0.00 | 135-264 | 17.5 | 77 | taken for the official |
| | edge Brian ML / Steffan | 2.75 / 2.61 | 0.02 | 124-132 / 116-132 | 11.7 / 12.7 | 22 / 18 | flat |
| | VoiceDesign | 3.45 | 0.00 | 87-229 | 10.8 | 65 | drifts |
| king en | **edge William ML** | 4.42 | 0.03 | **100-113** | **6.4** | **19** | deepest, roundest, steadiest |
| | Qwen uncle_fu (en) | 6.57 | 0.03 | 126-268 | 9.4 | 69 | lively but not one pitch |
| | VoiceDesign seeds 0 / 1 | 4.61 / 4.77 | 0.00 / 0.03 | 100-248 / 182-275 | 12-15 | 79 / 39 | drift / not deep |
| official en | **Qwen aiden** | 4.80 | 0.17* | 161-311 | 18.3 | 79 | high, fixed speaker, shrieks |
| | VoiceDesign seeds 0 / 1 | 4.48 / 4.85 | 0.18* | 244-390 / 235-422 | 16-17 | 101 / 114 | drift |
| | edge Ryan / Roger | 5.55 / 4.15 | 0.17* | 128-135 / 132-193 | 8.2 / 11.5 | 54 / 56 | cannot shriek ("water, help" / "Why? Help.") |

\* da_27 (the shriek) counts 0.33-0.50 for everyone: whisper cannot spell a scream. Without it the official's error is
0.00-0.05. uncle_fu's 0.21 is one line: whisper hears 盖章 as 改上 / 改章 (all voices, see "Listen first").

## Final clips (`report.json`, `check --asr`; mean per role)

| Role | lang | lines | F0 SD st | range st | err | median F0 Hz (min-max) | pace |
|---|---|---|---|---|---|---|---|
| narrator | zh | 8 | 5.41 | 16.4 | 0.040 | 252 (196-399) | 3.45 ch/s |
| daniel | zh | 4 | 6.29 | 21.8 | 0.017 | **105 (100-132)** | 3.26 |
| king | zh | 9 | 7.14 | 24.8 | 0.049 | 208 (132-265)** | 2.71 |
| official | zh | 8 | 6.68 | 22.8 | 0.019 | 245 (214-444, 444 = the shriek) | 2.45 |
| narrator | en | 8 | 4.85 | 14.8 | 0.038 | 200 (180-207) | 3.08 syl/s |
| daniel | en | 4 | 4.49 | 13.8 | 0.000 | 156 (119-196) | 2.64 |
| king | en | 9 | 4.55 | 14.0 | 0.012 | **109 (94-116)** | 3.01 |
| official | en | 8 | 4.75 | 14.8 | 0.015 | 240 (144-262) | 2.63 |

\** uncle_fu's pitch track jumps octaves on creaky frames (Esther and Ruth saw the same); read as "lively".

Acting measures: shriek da_27 zh **3.78 shriek**, en **3.56 shriek** ("Waaaaaaaaaah! Help!"); laugh da_05 en **4.61
laugh**, da_10 en **4.0 laugh** ("Hehehehe"); da_05 zh 1.15 and da_10 zh 1.59 = **read** (see "Listen first").
Names: whisper hears 但以理 as 蛋以理 / 但以李 / 但伊犁 on 4 lines (same syllables dan-yi-li; 伊犁 on da_21 may be a
tone slip), 巴比伦 and 耶路撒冷 exactly; no `sayMap` was needed. Loudness: every clip -16.0 to -16.4 LUFS, true peak
-1.5 to -5.3 dBTP (en da_05 trimmed -0.15 dB by hand after levelling: it came out at -1.4 dBTP; noted in sources.json).

Totals: **zh 222.3 s, en 203.8 s** of speech. `build_timeline.py daniel`: the play went from 255.8 s (estimate) to
**295.6 s** (timed from the voices); `voice_daniel.py daniel check`: all clips fit and leave >= 0.2 s.

Hand picks (cast file `pick` + `pickWhy`; the automatic rule keeps only takes within 0.04 of the best word error, and
whisper's homophones knocked out the best acted takes): zh da_05 (real 嘿嘿, 7.4 s instead of an 11.8 s take with an
extra 哈哈哈哈), en da_04 (the auto pick had no "Hmph"), en da_05 (the only real giggle), en da_17 (5.7 s instead of a
dragged 6.7 s), en da_27 (the auto pick said only "Help!").

## Listen first

1. **zh da_27 shriek** (5.6 s): VoiceDesign screams are unstable (of 14 takes, 8 were gibberish or 10-28 s runaways);
   the kept take measures a shriek (3.78) but whisper hears only 哇~~救命啊. If it is ugly, `"seed": 20` under
   `lines.da_27.zh` gives 8 new takes, or record it (the sheet has it).
2. **zh official is VoiceDesign**: each line is a take that passed the 190-330 Hz window, not one recorded voice
   (line medians 214-260 Hz plus the shriek). Check he sounds like one man across da_04-da_26.
3. **zh da_05 / da_10 giggles** rated "read" (1.15 / 1.59): the 嘿嘿 may sound spoken, not laughed.
4. **zh 盖章** (da_07, da_13): whisper hears 改章 / 改上 on every voice; listen for gài zhāng.
5. **zh da_21 但以理** heard as 但伊犁: possible tone slip on 以理.
6. **zh king = uncle_fu**, the same speaker as Esther's king and Ruth's Boaz (only Daniel had to differ); the acting
   note makes him jollier, but a child who plays all packs will recognise the voice. The VoiceDesign kings drifted an
   octave between lines, so they were not used.
7. **en da_09 Daniel prayer** 14.5 s (every ryan take ran 12-19 s for the prayer); slow but measured lively enough.
8. **zh da_26** (6.0 s for 呃……这个……我先走了……): long trailing mumble; intended, but check it is not dead air.
9. **en king (edge William)** is the one edge voice in a comic role: phrased, but edge cannot sigh or whimper the way
   Qwen does (da_14 "Oh...", da_21).

## Regenerate

```bash
export DOODLIVE_VOICE_CACHE=/tmp/daniel_voice/cache            # raw Qwen takes (deleted after this run: a re-run regenerates them)
python3 tools/story/voice_daniel.py daniel gen                 # 58 clips (~2.5 h on the 16 GB M1 Pro; one Qwen job at a time)
python3 tools/story/voice_daniel.py daniel harvest             # breath library from the cached takes, then gen the breath lines again
python3 tools/story/voice_daniel.py daniel check --asr
python3 tools/story/build_timeline.py daniel && python3 tools/story/voice_daniel.py daniel check
python3 tools/story/voice_daniel.py daniel session             # recording sheets; `import <dir> --lang zh` takes people's recordings
```

Take seeds are fixed, but MLX sampling is not bit-reproducible across machines; picks (`pick`) refer to take numbers
of this run and must be re-checked after an uncached regeneration.
