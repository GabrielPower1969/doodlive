# Saul Sees the Light!: voice (zh + en)

All 42 lines in Mandarin and English, 84 clips, every one Qwen3-TTS (Apache-2.0) run locally; no `edge-tts` (R7).
Engine per clip: `assets/saul/audio/voice/sources.json`. Takes picked by measurement (transcript error, pitch pin,
timbre pin, pace). **Nobody has listened yet** (V5): see "Listen first".

## Files

```
tools/story/cast_saul.json    cast per language and role, per-line acting notes (en `m_en` = story.py dir)
tools/story/voice_saul.py     copy of voice_risen.py (runaway guard 2.5x, f0 / timbre pins); voice.py untouched
assets/saul/audio/voice/      zh/ en/ (44.1 kHz mono WAV + 96 kbps MP3), durations.json, report.json, sources.json, srt
assets/saul/timeline.json     re-timed from the real clips by build_timeline.py
```

Run: `python3 tools/story/voice_saul.py gen|check [--asr]`, then `python3 tools/story/build_timeline.py saul`.

## Cast (median F0 per line, Hz; min-max (median); full numbers in report.json)

| Role | Engine / description | zh | en |
|---|---|---|---|
| narrator | `vivian`, **copied unchanged** (same storyteller as every pack) | 196-321 (240) | 216-352 (275) |
| jesus | **copied unchanged** from Miracles (via cast_risen: same design / instruct, pin 120-160, timbre pin to Miracles' clips); no reverb | 98-134 (130) | 121-156 (145) |
| peter | **copied unchanged** (deep bass, pin 95-135, timbre pin) | 141-152 | 109-225 |
| saul | VoiceDesign: young man about 28, clear, strong tenor, sharp or warm with one voice; pin 150-215 | 163-275 (210) | 175-290 (219) |
| ananias | VoiceDesign: elderly, soft, a little quavery and fussy; pin 130-210 | 100-171 (146) | 125-213 (143) |
| barnabas | VoiceDesign: big warm smooth baritone, "never gravelly, not a shouting fisherman"; pin 105-150 | 146 | 164 |
| priest | VoiceDesign: old, dry, level, never sinister; pin 115-165 | 90 | 110 |
| tallguard | VoiceDesign: thin, high, curious; pin 175-260 | 199 | 195 |
| shortguard | VoiceDesign: short, round, gruff, puffing; pin 95-140 | 131-235 | 207-268 |

Every clip is -16.1 +- 0.4 LUFS, true peak <= -1.5 dBTP (zh sa_36 was -1.1; re-spoken with seed 21: -2.5). No take is
over 2.5x its expected length (worst: en sa_34 1.9x, zh sa_30 1.9x); the guard fired twice, on zh sa_20 "好……好吧，主，我去。"
(7.1 s and 6.2 s, re-spoken to 3.4 s). Clip totals zh 180.4 s, en 194.2 s. **Re-timed play: 252.52 s (4:12.5)**,
inside STORY.md's 3:50-4:15; no cut needed. `check`: every line fits after re-timing.

Mean ASR error is low; the only lines over 0.1 are homophones or apostrophes: zh sa_20 heard 朱 for 主 (zhu, same
sound), en sa_21 / sa_36 ("And Ananias"; "Jesus'" vs "Jesus's").

## Names (V3, tone)

扫罗 / 亚拿尼亚 / 巴拿巴 and 大马士革 / 耶路撒冷 / 保罗 / 彼得 all transcribed correctly; sa_17 heard 直接 for 直街 (the
same sound zhíjiē). Falling or level on the names, not rising: sa_08 扫罗，扫罗 131→157→143 Hz, then 123→163 into 你为什么
(a call, fine); sa_17 亚拿尼亚 158→133 falling; sa_22 扫罗弟兄 101→142 then falling to 114 (warm, not a question);
sa_39 扫罗弟兄 150 then falling to 120; sa_35 谢谢你们 falling. **One doubt: sa_38 彼得 rises 150→257 Hz** (a loud call,
not a question, but listen). "巴拿巴" is never spoken (no line says his name). No `sayMap` needed.

## Peter and Jesus

Both are the Miracles settings, unchanged (CONTRACT §7). Peter again sits above his 95-135 pin in these two lines
(zh 141-152, en 109-225: "big Peter, small voice" worried and then a glad welcome), as in risen. **A deeper Peter for
everyone** would be: pin 90-125 and add "his chest voice stays low even when he is frightened or whispering" to
`instruct`; I did not change the earlier casts. Jesus is slightly low in zh sa_17 (98 Hz at the end of the line).

## Listen first (least trusted)

1. **sa_38 zh 彼得 rise** (Barnabas) and Barnabas vs Peter vs Jesus: three warm low men in zh (146, 146, 130 Hz
   medians); is Barnabas clearly a friendly big brother, not Peter? (the weakest voice separation).
2. **Priest** (sa_03): 90 Hz zh, below his pin; too low and slow, or dry and calm? Neither kind nor cruel?
3. **Saul, one man**: sharp in sa_02 / sa_06 (zh) and warm from sa_24 / sa_28 / sa_41: the same voice? sa_35 zh is a
   whisper at 275 Hz; sa_09 "主啊，你是谁？" small and shaken, not a squeak?
4. **Ananias**: sa_18 and sa_20 zh (re-spoken, 3.4 s), sa_34 (5.3 s zh, 5.1 s en, long for a loud whisper); fussy and
   funny, or just slow?
5. **The guards**: sa_30 zh "他……他完全变了。" 4.25 s for 7 characters (slow, big gaps?); sa_05 round and puffing, sa_29
   thin.
6. **Narrator sa_42 en** (8.6 s, a hush at the end?) and sa_01 en (the arrest sentence plain and calm).
7. **Jesus's three lines** (sa_08, sa_10, sa_11): the same Jesus as Miracles; no reverb, as ordered.

## Not done / weak

- Nobody has listened (V5).
- Peter's pin unmet (parity with earlier packs).
- Timbre distances for new voices have no reference; Jesus / Peter distances are above the 65 tolerance as in earlier packs.
- Timing: build_timeline printed no warnings for the new lengths.
- Raw Qwen takes are in `~/.cache/doodlive-voice` (R11: delete when the pack is signed off). A rerun costs ~1.4 h (the
  Mac was loaded).
