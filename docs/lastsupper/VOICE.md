# The King Who Serves: voice (zh + en)

All 36 lines in Mandarin and English, 72 clips, every one Qwen3-TTS (Apache-2.0) run locally on this Mac; no
`edge-tts` (R7). Engine and licence per clip: `assets/lastsupper/audio/voice/sources.json`. Takes were picked by
measurement (transcript error first, then pitch pin, timbre pin, pitch movement and pace). **Nobody has listened yet**
(V5): see "Listen first".

## Files

```
tools/story/cast_lastsupper.json   cast per language and role, per-line acting notes (zh `m`, en `m_en`), phrases
tools/story/voice_lastsupper.py    wrapper: voice.py + Exodus add-ons (f0Weight, mfccRef) + Jonah crowd takes
                                   + runaway guard + crowd repetition check; voice.py untouched
assets/lastsupper/audio/voice/     zh/ en/ (44.1 kHz mono WAV + 96 kbps MP3), durations.json, report.json,
                                   sources.json, zh.srt, en.srt
assets/lastsupper/timeline.json    re-timed from the real clips by build_timeline.py
```

Run: `python3 tools/story/voice_lastsupper.py gen|check [--asr]`, then `python3 tools/story/build_timeline.py lastsupper`.

## Guards (lessons from Real Miracles)

- **Runaway guard** (every phrase, every crowd member): a raw take longer than 2.5x its expected length (0.28 s per Han
  character / 0.40 s per English word, + 0.6 s) is re-spoken with seed + 1000·i, up to 5 times. It fired once:
  ls_12 zh "我的鸽子……" ran 25.8 s, re-spoken to 1.3 s.
- **Crowd takes with a repetition check**: ls_03 was mixed 8 times; score = transcript error + (words heard / words
  written − 1.25) + a length penalty. zh take 2 looped "河嵩" ×37 and take 3 repeated a phrase ×3; both rejected.
- Interjections stay inside a phrase with words ("哈哈，大家都知道他是王啦！", "喂喂喂！我是第一个跟耶稣的，", "哎呀，我的钱！");
  no bare-interjection phrase.

## Cast (median F0 per line, Hz, parselmouth; min-max (median) over the role's lines; full numbers in report.json)

| Role | Engine / description | zh | en |
|---|---|---|---|
| narrator | `vivian` CustomVoice, best of 4, **copied from cast_miracles.json** | 187-394 (236) | 233-361 (263) |
| jesus | VoiceDesign, **Miracles description, pin 120-160, warm fx, best of 8** + timbre pin to the mean MFCC of Miracles' chosen Jesus clips (tol 65, weight 0.1) | 119-144 (135) | 121-207 (145) |
| peter | VoiceDesign, **Miracles "deep booming bass, stays low when he shouts", pin 95-135, best of 8** + timbre pin to Miracles' Peter | 105-205 (164) | 130-249 (207) |
| john | VoiceDesign: youngest, bright, quick, cheeky; pin 150-210 | 196 | 206 |
| james | VoiceDesign: confident full tenor, puffed up; pin 125-175 | 145-189 | 141-155 |
| andrew | VoiceDesign: mild, soft-spoken, low-key, deadpan, never loud; pin 105-150, warm fx | 106-129 | 139-147 |
| seller1 | VoiceDesign: round jolly market crier; pin 110-170, warm fx | 210-312 | 162-253 |
| seller2 | VoiceDesign: thin, nasal, fast patter; pin 150-230, nasal fx | 310 | 162 |
| people (ls_03) | Miracles/Jonah crowd: 10 Qwen voices incl. a boy of 7 (-3 dB) and a girl of 5 (-4 dB) raised for "a child's voice on top"; field fx (outdoors); best of 8 mixes | 320 | 284 |

Peter compared with Miracles (169-206 zh, 221-263 en): same range. He is still above his 95-135 pin, as in Miracles.
Andrew sits below Peter in both languages (zh 106-129 vs 164 median; en 139-147 vs 207). John is the highest disciple.

## Levels, length, transcript

Every clip −16.2 to −15.9 LUFS, true peak ≤ −1.8 dBTP. Clip totals zh 194.5 s, en 219.0 s. `check`: all clips fit
maxSec and leave ≥ 0.2 s before the next line. Mean transcript error 0.03. **Re-timed play: 260.47 s (4:20)**: under
the 4:30 limit; no cut needed. PLAN.md's first cuts, if ever needed: ls_22, ls_13, ls_04.

Picked by hand: en ls_19 `pick: 5`. The only zero-error take was 425 Hz, a squeak. Take 5 says every word ("Err" was
missing from asrIgnore) and measures 237 Hz.

## Names (V3)

耶路撒冷, 逾越节 (ls_01, ls_14), 犹大 (ls_27), 彼得 (ls_26) heard correctly. 安得烈 (ls_33) heard as 安德烈: the same
sound (ān dé liè), so the reading is right. 雅各 and 约翰 are not spoken in any line. **和散那 is uncertain**: whisper
hears 喝散的 (ls_13) and 何仔呢 / 和伞啊 (ls_03). 散 may come out sǎn instead of sàn: see listen-first. Homophones, not
misreadings: ls_22 在 → 再, ls_21 束 → 竖.

## Listen first (least trusted)

1. **ls_32 zh/en, the cup line** (PLAN risk 8). Is it gentle, calm and not sad? The owner listens to it first.
2. **ls_03 zh crowd**: the check transcript has error 0.69 ("何仔呢，欢迎我们的王。是上帝太来的。"). Can you hear 和散那 and
   派来? Are the two children on top? en is clean ("Hosanna! Hooray for our king! God has sent him!").
3. **和散那 tone** in ls_03 and ls_13 zh: hé sàn nà or hé sǎn nà? If it is wrong, add `sayMap` {"和散那": "和散纳"}
   (or try 和撒那) and regenerate those two lines.
4. **Peter as one man across the Miracles pack**: zh ls_07 (105 Hz) against ls_04 / ls_33 (199 / 205 Hz); en ls_23
   (130) against ls_25 (249). Is he the same big friendly bear as in Miracles?
5. **seller1 zh**: ls_08 is 312 Hz and ls_12 is 210 Hz, both above the 110-170 pin (every take was). Is he one round
   jolly man or a shrill one? seller2 is 310 Hz in zh but 162 Hz in en: is he a different character per language?
6. **Jesus en ls_26 laugh (207 Hz)**, against 121-156 Hz on his other lines. Is the laugh warm and real?
7. **ls_12 zh** came from the runaway re-speak. Is the wail comic and complete?
8. **en ls_16 John**: whisper hears "and I'll sit on his left" for "Then I'll". **zh ls_22 James**: is it a whisper?
9. **Narrator zh ls_13 (381 Hz)** lifts high into the children's 和散那. Is that fine or too shrill?

## Not done / weak

- Timbre distance to Miracles was printed during gen but is not stored in report.json; it is not tabulated here.
- Peter's pitch pin is unmet, by design parity with Miracles (same settings).
- The raw take cache (`~/.cache/doodlive-voice`) entries from this run were deleted (R11). A re-run of any line costs
  full synthesis time (the whole pack took about 3 h).
