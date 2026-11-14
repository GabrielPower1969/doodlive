# Exodus: voice (zh + en)

All 36 lines of `assets/exodus/timeline.json` in Mandarin and English, 72 clips, made 2026-11-14. Brief
(CONTRACT.md §7, Ruth §7): people telling a story to a 4-10-year-old; Moses old but strong, shy in S03-S04 and firm
from S05; Pharaoh a comic baritone with a big range; God calm, deep, warm, light hall; Miriam bright and quick, her
chant rhythmic; the people 4-6 voices together. Takes were kept **by measurement** (whisper word accuracy first, then
liveliness, pace and acting measures), as Ruth. Nobody has listened yet: read "Listen first" before shipping.

## Files

```
tools/story/cast_exodus.json   cast per language + role, acting note per line (m = zh note; en uses the line's dir),
                               pitch pins, timbre pin, picks with the reason (pickWhy), chant grid
tools/story/voice_exodus.py    Exodus wrapper around voice.py (voice.py / voice_extras.py are NOT edited; they are
                               shared with the Daniel pack being built at the same time). Adds at run time:
                               role `reverb` (God's hall), line `grid` (phrases on the song cue's bars, also for the
                               crowd), role `mfccRef` (timbre pin), and `preview`
assets/exodus/audio/voice/
  zh/ex_XX.wav en/ex_XX.wav    44.1 kHz mono 16-bit, -16 LUFS (+-0.2), true peak <= -1.6 dBTP
  zh/ex_XX.mp3 en/ex_XX.mp3    96 kbps mono
  durations.json report.json sources.json zh.srt en.srt   as Ruth (report: whisper + Praat measures per clip)
  takes.json                   every take's score / error / pitch SD / pace / transcript and the one kept
  breaths/                     real in-breaths cut from the Qwen takes (voice_extras.py harvest)
  preview_zh.mp3               all zh clips at their timeline times, voices only (293.6 s)
```

## Cast

| Role | zh | en | fx |
|---|---|---|---|
| narrator | Qwen3-TTS CustomVoice `vivian`, best of 3, Ruth's role note | edge `en-US-AvaMultilingualNeural` -8 % | plain (same voice as Ruth / Esther) |
| moses | Qwen3-TTS **VoiceDesign** "八十岁左右的老爷爷…声音偏低、苍老、粗糙，带点沙哑，说话踏实稳重，有力量", best of 4, pinned 90-185 Hz, husky gate `hnrMax` 9 dB, timbre pin to the audition take | Qwen **VoiceDesign** "Male, in his seventies, an old shepherd. Low, deep, slightly gravelly… strong and steady, not frail", best of 4, pinned 85-185 Hz | warm |
| pharaoh | Qwen **VoiceDesign** "四十多岁…卡通国王。低沉、洪亮、圆润的男中音，胸腔共鸣很足，拿腔拿调…", best of 4-5, pinned 100-300 Hz (100-420 on the frog / wheel lines) | Qwen **VoiceDesign** "a vain cartoon king. A low, rich, booming baritone with lots of chest resonance…", same pins | plain |
| miriam | Qwen **VoiceDesign** "三十岁左右的大姐姐。声音明亮、清脆，语速偏快，热情、温暖", best of 4, pinned 180-360 Hz | edge `en-GB-SoniaNeural` +4 % | plain |
| god | Qwen **VoiceDesign** "声音低沉、浑厚、温暖，非常平静、从容…绝不吼叫", best of 3, pinned 70-140 Hz | edge `en-AU-WilliamMultilingualNeural` -12 %, -2 Hz, phrased (pauses before 'and I have heard them crying', 'I will be with you') | warm + **hall** (convolution, RT60 1.4 s, 20 % wet, 25 ms pre-delay, tail cut 0.35 s after the voice) |
| people | crowd of 5: Yunjian (lead) + Qwen `eric` + Xiaoxiao + Yunxi (-1 st) + Xiaoyi, offsets 0-0.23 s, -0 to -8 dB, small room | crowd of 5: Guy (lead) + Natasha + Roger + Libby + Eric (+0.8 st), offsets 0-0.26 s | plain |

Why these: no stock voice is an old man, a comic king that is not Haman (Qwen `dylan`) / the king and Boaz (Qwen
`uncle_fu`, edge Christopher / Andrew), or a woman who is not Ruth / Esther (`serena`, Emma), so Moses, Pharaoh,
Miriam and God are designed from a description (Ruth's Naomi method). Pharaoh in English is Qwen, not edge, because
edge cannot laugh, squeal or sneeze. Moses in English is Qwen because no edge voice sounds old. Pharaoh's lines are
generated whole, with the acting sequence in the note (laugh -> mock -> sulk), not phrase by phrase: VoiceDesign
invents the voice per generation, so phrases generated separately could be different men inside one line.

### Audition (2026-11-14, numbers from `measure`; scratch, audio deleted)

| Candidate | line | median F0 | F0 SD st | HNR dB | note |
|---|---|---|---|---|---|
| moses zh design A (seventies, "中气很足") | ex_09 s0 / s1 / ex_27 | 107 / 160 / 171 | 9.0 / 9.0 / 7.1 | 5.3 / 10.4 / 5.1 | drifts a lot between seeds |
| **moses zh design B** (about eighty, rough) | ex_09 / ex_27 | 159 / 146 | 7.4 / 8.0 | 10.6 / **4.5** | rougher, kept; ex_27 take is the timbre reference |
| pharaoh zh A ("尖叫成高音" in the description) | ex_02 | **344** | 5.5 | 10.2 | the squeal in the description made the whole voice high: rejected |
| pharaoh zh B (plump, gravelly) | ex_02 | 266 | 7.2 | 7.8 | |
| **pharaoh zh/en C** (low, chest resonance; squeals only in line notes) | | | | | made after A/B, no audition; pinned |
| miriam zh A | ex_26 | 393 | 4.2 | 12.6 | |
| **god zh A** | ex_08 | **92** | 4.6 | 4.7 | calm and deep, kept; timbre reference |
| moses en A / B | ex_27 | 165 / 180 | 2.9 / 4.7 | 10.5 / 8.0 | A kept (lower) |
| pharaoh en A / B | ex_02 | 331 / 270 | 4.7 / 6.4 | 11.4 / 8.5 | both high: design C |
| miriam en edge: Aria / **Sonia** / Jenny / Libby / Clara / Emily / Maisie | ex_21 | 223 / 195 / 194 / 197 / 197 / 208 / 331 | 3.8 / **4.4** / 3.2 / 4.1 / 3.5 / **4.8** / 2.2 | | Sonia: lively and the quickest (5.1 s vs Emily 7.0 s) |
| god en edge: Brian ML / Guy / Ryan / Steffan / **William ML** / Roger / Eric / Liam | ex_08 | 120 / 157 / 126 / 126 / **105** / 143 / 105 / 101 | 3.6 / 5.3 / 6.5 / 2.5 / 4.8 / 4.9 / 3.5 / 6.4 | 12 / 11.6 / 10.2 / 13.8 / 8.7 / 11.9 / 10.5 / 7.8 | William ML: deep, a multilingual (natural) voice, calm but not flat |

The pitch tracker reads excited male voices high (Ruth's Boaz ru_09 measures 267 Hz median, Haman es_03 199 Hz), so the
first pins (Pharaoh 90-175 Hz) rejected every take; they were widened to the ranges above before the takes were chosen.

## Measurements of the kept clips (`voice.py exodus check --asr`)

| Role | lang | F0 SD st | range st | err | median F0 Hz | pace |
|---|---|---|---|---|---|---|
| narrator | zh | 4.64 | 14.3 | 0.009 | 255 | 3.38 ch/s |
| moses | zh | 7.15 | 22.9 | 0.007 | 149 | 2.48 |
| pharaoh | zh | 5.62 | 16.9 | 0.124* | 309 (calm ex_22: 160) | 2.18 |
| miriam | zh | 4.55 | 14.5 | 0.029 | 371 | 3.91 |
| god | zh | 6.33 | 19.9 | 0.012 | 94 | 2.86 |
| people | zh | | | 0.000 | | |
| narrator | en | 4.83 | 15.3 | 0.000 | 190 | 3.51 syl/s |
| moses | en | 4.16 | 13.1 | 0.000 | 128 | 2.12 |
| pharaoh | en | 4.97 | 16.5 | 0.050 | 282 | 2.04 |
| miriam | en | 4.24 | 13.2 | 0.000 | 203 | 3.04 |
| god | en | 4.37 | 13.9 | 0.000 | 108 | 2.79 |
| people | en | | | 0.000 | | |

\* ex_30 (冲啊……哇啊啊, whisper writes the wail as 这轮) and ex_19 (whisper counts the spoken 不放啦 against the written 了).

Every clip starts 0.04-0.06 s after its first sample and ends 0.05-0.08 s after its last sound (God 0.15-0.18 s: the
hall tail; ex_34 en 0.27 s: the crowd room). Loudness -15.8 to -16.2 LUFS, true peak -1.6 to -6.7 dBTP.

Timbre (mean MFCC 1-12 distance between role centroids; a role's own lines spread 77-120): zh Moses is 98 from Boaz and
100 from Esther's king; zh Pharaoh 175 from Boaz, king and Haman; en Pharaoh 109 from en Haman (spread 93: the closest
pair); zh God 69 from Boaz (inside the spread: God may sound related to Boaz / Esther's king in Chinese).

Totals: **zh 223.3 s, en 215.2 s** of speech. `build_timeline.py exodus` (timed from these voices): **293.65 s**
(the estimate was 274.85 s; the brief said about 4 minutes).

## Takes kept by a person's rule instead of the top score (`pick` + `pickWhy` in the cast file)

| Line | Kept | Why |
|---|---|---|
| zh ex_02 | take 3 | keeps the snooty 哼 (the top score dropped it) |
| zh ex_13 | take 0 | keeps the pause in 好……我去 (2.0 s); the top score rushed it (1.0 s); a real breath is added before |
| zh ex_19 | take 1 | has the 嘿嘿 chuckle; the "best by words" take said only 不放了 |
| zh ex_32 | take 1 | the only take whose last burst is unvoiced (a "嚏" hiss, voiced fraction 0.00 in the last 0.35 s); whisper cannot transcribe a sneeze |
| en ex_02 | take 1 | keeps "Hmph!" |
| en ex_15 | take 3 | opens with a real "Ha ha ha!" (laugh 3.6, verdict laugh) |
| en ex_19 | take 0 | the only take with "Heh heh" |
| en ex_32 | take 2 | "Ah! Ah! Achoo!"; the top score said "Oh, oh, oh..." |

Breaths (real Qwen in-breaths, `voice_extras.py harvest`): before ex_01, ex_13, ex_22, ex_29 and after
你听见我们在哭吗 / "crying" in ex_03, both languages (edge voices and English Qwen roles borrow the zh breaths).

## Miriam's chant and the people's echo (song cue grid, MUSIC.md: 6/8, dotted quarter 112, bar 1.071429 s)

Each phrase starts on its bar (the phrase's own speech end pushes the next one only when it overruns; never cut,
never stretched). Times are from the clip start; the clip's first sound is at **0.03 s** (voice.py's pad), so set
`pre` for the clip start 0.03 s before bar 2 / bar 10.

| Clip | Phrase starts (s) | Bars | Duration |
|---|---|---|---|
| zh ex_33 | 唱歌吧 0.00, 向上帝唱歌 1.07, 他大大得胜 3.21, 把马和兵车 5.36, 都抛在海里 6.45 (+0.02 late) | 2, 3, 5, 7, 8 | **7.68 s** (slot 8.57: bar 9 is the held last note) |
| en ex_33 | Sing to the Lord 0.00, sing! 1.07, He has won the victory 2.14, Horse and chariot 4.29, he threw into the sea 6.43 | 2, 3, 4, 6, 8 | **7.79 s** |
| zh ex_34 | 唱歌吧 0.00, 向上帝唱歌 1.10 (+0.03 late) | 10, 11 | **2.51 s** (slot 2.14: 0.37 s into bar 12) |
| en ex_34 | Sing to the Lord 0.00, Sing! 1.19 (+0.12 late) | 10, 11 | **2.03 s** |

## Listen first (weakest, by measurement)

1. **zh Pharaoh as one man.** His lines spread 120 in timbre (Moses 78, God 82) and his median pitch runs 160 Hz (sad
   ex_22) to 410 Hz (frog ex_17, wheel ex_30, sneeze ex_32). That may be acting or may be VoiceDesign drift. If he sounds
   like different men, re-pick from new seeds (`"seed": 10` under `lines.ex_XX.zh`) or switch to the Qwen3-TTS Base
   model (cloning from one designed take; not cached, a 1.7B download: ask first).
2. **zh Miriam is high** (295-413 Hz median; en Sonia ~200 Hz). Check she is a bright woman, not a girl.
3. **zh ex_30 / en ex_30** (the wheel): whisper error 0.6 / 0.33; zh may have lost 咦 and 哎哎哎. Acting measure says
   "wail" (3.5 / 4.0).
4. **Sneezes ex_32**: chosen acoustically, not by ear.
5. **zh ex_06 God "摩西，摩西！"**: two of three takes were wrong (one came out in Japanese, 申し申し); the kept one is
   correct by whisper but scored low on liveliness.
6. **ex_33 zh is not sung**, it is a rhythmic chant laid on the bars; VoiceDesign phrases are generated separately, so
   check it is one woman across the five phrases. en ex_33 (edge) is spoken in rhythm.
7. **zh ex_01** is 15.1 s (the line is long and the note asks for weight); it sets the opening's length.
8. zh God sits close to Boaz / the king in timbre; en Pharaoh is the closest to en Haman.

## Regenerate

```bash
python3 tools/story/voice_exodus.py gen [--lang zh|en] [--only ex_02,...]  # Qwen takes cached in ~/.cache/doodlive-voice
python3 tools/story/voice_extras.py harvest exodus                          # after new Qwen takes, then gen the breath lines
python3 tools/story/voice.py exodus check --asr
python3 tools/story/build_timeline.py exodus && python3 tools/story/voice.py exodus check
python3 tools/story/voice_exodus.py preview --lang zh
```

Only the kept raw takes are in the cache (the 165 rejected Exodus takes were deleted to save disk), so a re-run with
the same settings re-measures the kept take and regenerates the others. On this shared machine a take took 0.5-3 min;
one run once died with a Metal "Impacting Interactivity" error while another session used the GPU, so the generator
was driven line by line with retries.
