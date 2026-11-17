# He Is Risen!: voice (zh + en)

All 39 lines in Mandarin and English, 78 clips, every one Qwen3-TTS (Apache-2.0) run locally on this Mac; no
`edge-tts` (R7). Engine per clip: `assets/risen/audio/voice/sources.json`. Takes were picked by measurement
(transcript error first, then pitch pin, timbre pin, pitch movement and pace). **Nobody has listened yet** (V5): see
"Listen first".

## Files

```
tools/story/cast_risen.json   cast per language and role, per-line acting notes (zh `m`, en `m_en`), phrases
tools/story/voice_risen.py    copy of voice_lastsupper.py (runaway guard, crowd takes, f0 / timbre pins); voice.py untouched
assets/risen/audio/voice/     zh/ en/ (44.1 kHz mono WAV + 96 kbps MP3), durations.json, report.json, sources.json,
                              zh.srt, en.srt
assets/risen/timeline.json    re-timed from the real clips by build_timeline.py
```

Run: `python3 tools/story/voice_risen.py gen|check [--asr]`, then `python3 tools/story/build_timeline.py risen`.

## Guards

- **Runaway guard** fired twice: rs_18 zh "等……等等我！" (9.0 s and 4.6 s, re-spoken to 3.4 s and 1.5 s), and rs_31
  zh "鬼……鬼啊？" (7.5 s, re-spoken to 2.0 s).
- Interjections stay inside phrases with words: "哈哈，是我呀！" (rs_32), "哈哈，他在吃我们的鱼！" (rs_33), "等……等等我！" (rs_18).
  No bare-interjection phrase. No crowd in this pack.

## Cast (median F0 per line, Hz, parselmouth; min-max (median) over the role's lines; full numbers in report.json)

| Role | Engine / description | zh | en |
|---|---|---|---|
| narrator | `vivian` CustomVoice, best of 4, **copied unchanged from cast_lastsupper.json** | 204-366 (281) | 221-340 (300) |
| jesus | VoiceDesign, **copied unchanged from cast_lastsupper.json** (Miracles description, pin 120-160, timbre pin to Miracles' clips) | 122-162 (148) | 119-164 (157) |
| peter | VoiceDesign, **copied unchanged from cast_lastsupper.json** (deep bass, pin 95-135, timbre pin) | 100-249 (190) | 127-232 (186) |
| john | VoiceDesign, **copied unchanged from cast_lastsupper.json**, plus a timbre pin to lastsupper's chosen ls_16 (tol 65, weight 0.1) | 167-303 (226) | 157-300 (234) |
| mary | VoiceDesign: young woman, warm, sweet, soft, quick to tears and joy; pin 200-280 | 222-298 (254) | 317-423 (366) |
| joanna | VoiceDesign: woman in her forties, lower alto, brisk and practical; pin 160-230 | 221-255 (255) | 292-295 (295) |
| angel | VoiceDesign: young man, bright, clear, warm, calm; "not deep, not booming, no echo"; plain fx (no reverb); pin 135-190 | 156-183 (177) | 159-280 (221) |
| thomas | VoiceDesign: steady even baritone, sensible, "clearly different from a booming fisherman"; warm fx; pin 100-145 | 142-237 | 102-144 |

Peter compared with lastsupper (105-205 zh, 130-249 en): the same range, still above his pin, as in Miracles and The
King Who Serves. Jesus matches lastsupper (119-144 zh, 121-207 en). Joanna is lower than Mary in English (295 vs 366)
but only a little lower in Chinese (255 vs 254 median), so in zh only the timbre tells them apart. Thomas sits below
Peter in en; in zh his rs_37 sob rises to 237 Hz.

Timbre distance to the reference (mean MFCC 1-12; tolerance 65): Jesus 43-176, Peter 61-143, John 79-233. The
shortest clips are furthest away (rs_25 "Mary", rs_17 "Hurry up, Peter!"). lastsupper did not store its own distances,
so there is no baseline to compare against.

## Levels, length, transcript

Every clip −16.4 to −15.9 LUFS, true peak ≤ −1.6 dBTP (en rs_01 was −1.4 at first; re-spoken with seed 20). Clip totals
zh 178.2 s, en 184.7 s. `check`: every clip fits maxSec and leaves ≥ 0.2 s before the next line. Mean transcript error
zh 0.007, en 0.010. **Re-timed play: 247.42 s (4:07)**: under the 4:30 limit and under PLAN.md's 4:15; no cut needed.
PLAN.md's first cuts, if ever needed: rs_06, rs_21, rs_29, rs_12.

en rs_03 (0.13) and rs_39 (0.14) are over 0.1 only because the quoted words ('On … again!', 'I … always.') are counted
with their apostrophes; the transcripts hold every word.

Re-takes and hand picks:
- rs_25 zh "马利亚。": the first run gave 0.64 s and seven of ten takes misheard. Re-spoken with `say: "马利亚……"` and a
  tender, slow per-line instruct, best of 12; take 11 (0.92 s, transcript "马利亚", no error) is fixed with `pick: 11`.
  A third try asking for a falling contour came out worse (0.70 s, rising 123→224 Hz) and was thrown away.
- rs_38 zh: the first take sat at 474 Hz (shrill on the moral). Re-spoken with a per-line pitch pin 200-320: 204 Hz,
  10.0 s (slow).
- rs_08 en: whisper heard "A stone"; re-spoken (seed 30): "The stone... it's rolled away".

## Names (V3)

马利亚 heard as 玛利亚 / 马利亚 (the same sound) in rs_04, rs_25; 约亚拿 (rs_04), 彼得 and 约翰 (rs_13, rs_16), 耶稣 everywhere and
天使 (rs_07, rs_13) all correct. 多马 (rs_36) heard as 多玛: the same sound (duō mǎ), so the reading is right. rs_25 zh is
heard as "马利亚?" (see listen-first 1). No `sayMap` needed.

## Listen first (least trusted)

1. **rs_25 zh "马利亚。"** (the emotional peak). It is short (0.92 s) and its pitch **rises** at the end (128 → 147 → 206
   Hz by thirds). It may sound like a question instead of a tender call. If it does: regenerate with another `seed` and
   `pick` by ear. en rs_25 "Mary." falls (257 → 117 Hz), 0.68 s: is it soft enough?
2. **rs_01 / rs_02 zh + en, the cross lines** (PLAN risk 7): plain and gentle, no drama, no pause on 十字架 / "cross"?
3. **Mary vs Joanna in zh** (rs_05, rs_06, rs_11): almost the same pitch. Are they clearly two women, Joanna the older?
4. **Peter as one man**: zh rs_20 (100 Hz) vs rs_33 (249 Hz, the laugh); en rs_20 (127) vs rs_33 (232). The same big
   friendly bear as in Miracles? Does he go high when shouting (rs_18 zh, 190 Hz)?
5. **rs_37 zh Thomas "我的主！我的上帝！"** at 237 Hz against 142 Hz on rs_35: a heartfelt sob or a different man?
6. **The angel** (rs_09, rs_10, rs_12): bright and kind, not booming? en rs_12 rises to 280 Hz.
7. **rs_38 zh** (moral): 10.0 s at 2.1 chars/s. Slow and clear, or dragging?
8. **John**: rs_17 zh (303 Hz) is the furthest from his lastsupper timbre; is it the same young man? rs_31 zh came from the
   runaway re-speak: complete and comic "鬼……鬼啊？"
9. **en Mary** (317-423 Hz) is high; warm or squeaky?

## Not done / weak

- Nobody has listened (V5).
- Peter's pitch pin is unmet, by design parity with Miracles / The King Who Serves (same settings).
- Timbre distances for Jesus / Peter / John are mostly above the 65 tolerance and have no stored baseline from lastsupper.
- build_timeline warns: "mary run at 170.53s needs 1.3s … the next beat comes after 0.7s" (S10 staging: lead / Animation,
  not Voice).
- This run's raw Qwen takes were deleted from `~/.cache/doodlive-voice` (R11). Re-running a line costs full synthesis
  time (the whole pack took about 1 h).
