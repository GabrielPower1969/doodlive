# Real Miracles: voice (zh + en)

All 33 lines in Mandarin and English, 66 clips, every one Qwen3-TTS (Apache-2.0) run locally on this Mac; no
`edge-tts` (R7). Engine and licence per clip: `assets/miracles/audio/voice/sources.json`. Takes were picked by
measurement (transcript error first, then pitch pin, pitch movement and pace). **Nobody has listened yet** (V5): see
"Listen first".

## Files

```
tools/story/cast_miracles.json   cast per language and role, per-line acting notes, phrases (interjections), crowds
assets/miracles/audio/voice/     zh/ en/ (44.1 kHz mono WAV + 96 kbps MP3), durations.json, report.json,
                                 sources.json, zh.srt, en.srt
assets/miracles/timeline.json    re-timed from the real clips by build_timeline.py
```

Run: `python3 tools/story/voice.py miracles gen|check [--asr]`, then `python3 tools/story/build_timeline.py miracles`.
The takes were made through Jonah's wrapper logic (crowd re-takes, `f0Hz` pitch pin from `voice_exodus.py` /
`voice_extras.py`) plus a scratch **runaway guard** (see "Re-running" below).

## Cast (median F0 per line, Hz; parselmouth `to_pitch_ac`; full numbers in report.json)

| Role | zh | en | Measured zh / en (min-max, median) |
|---|---|---|---|
| narrator | Qwen CustomVoice `vivian`, best of 4 (the family storyteller, every pack) | `vivian` speaking English, best of 4 | 192-301 (245) / 212-363 (293) |
| jesus | VoiceDesign: warm, clear, soft man ~30, a gentle teacher who never shouts; pinned 120-160 Hz, warm fx; best of 8 | same description in English | 108-147 (133) / 119-199 (128) |
| peter | VoiceDesign: burly fisherman, **deep booming bass, loud but low, never shrill**; pinned 95-135; best of 8 | same in English | 169-206 (202) / 221-263 (240) |
| man | VoiceDesign: shy, soft young man ~25 who turns joyful; pinned 150-210 | same in English | 161-191 / 200-259 |
| friend1 | VoiceDesign: bright, confident leader; pinned 140-190 | same in English | 239-261 / 273-299 |
| friend2 | VoiceDesign: big, slow, soft, deep; pinned 85-115 | same in English | 101 / 94 |
| friend3 | VoiceDesign: small, quick, high, flustered; pinned 190-250 | same in English | 305 / 274 |
| friends (mi_11) | the four friend designs layered (lead 0 dB, others -2 / -2 / -4 dB, one -2 st), tight 0-80 ms stagger, small room; best of 8 mixes | same | 165 / 323 |
| people (mi_07, mi_21) | Jonah's crowd: `serena uncle_fu vivian dylan eric`, a 7-year-old boy and a 5-year-old girl (VoiceDesign), three repeats; 6 dB+ under the lead, offstage fx, hall; best of 6 mixes | `serena ryan vivian aiden uncle_fu` + the two children | 288-291 / 260-287 |

Why: Jesus and Peter are the two roles children follow, so they got 8 takes and a pitch pin. Peter's first design
("loud, quick to shout") measured 237-362 Hz zh and 316-345 Hz en when shouting, higher than the narrator; re-described
as a low booming bass (the Jonah captain lesson) he dropped to 169-206 zh and 221-263 en. Still above the 95-135 pin:
a designed voice rises a lot when it shouts, and every Peter line is a shout except mi_31.

## Interjections

Own short phrases, each with its own acting note: mi_06 哎哟 / oof, mi_08 嗯…… / Hmm..., mi_09 有了, mi_12 哎！哎哎哎！ /
Hey! Hey, hey, HEY!, mi_13 哈哈 / Ha ha, mi_20 我……我的腿……, mi_23 哈哈哈 / Ha ha ha (added through `say`, the subtitle
keeps the written line), mi_27, mi_28, mi_29, mi_31 split into breaths. mi_12 zh "哎！" alone made Qwen talk for 15-45 s;
it is now one phrase "哎！哎哎哎！" (same words, re-punctuated).

## Levels and length

Every clip -16.5 to -16.0 LUFS, true peak at most -1.6 dBTP. mi_13 zh is -16.5 (0.1 dB outside the ±0.4 band).
Clip totals: zh 169.1 s, en 191.9 s. `voice.py check`: all clips fit maxSec and leave >= 0.2 s before the next line.
**Re-timed play: 226.86 s (3:47).**

## Names (V3)

耶稣, 彼得, 迦百农 heard correctly or as same-sound characters (迦百农 → 加百农, jiā). Homophones in the transcript, not
misreadings: mi_27 舀水 → 咬水 (yǎo), mi_23 值 → 直 (zhí), mi_32 骗 → 片 (piàn), mi_11 挖 → 哇 (wā), mi_07 挤 → 起/急
(jǐ vs qǐ/jí: **this one is a real difference**, see listen-first).

## Listen first (least trusted)

1. **mi_11 friends, both languages**: whisper hears 哇呀哇！哇呀哇！ (right sound) and ten "dig"s for six (the stagger
   doubles syllables, or whisper loops: V4). Earlier mixes looped for 20+ s. Is it a tidy, happy chant of four men?
2. **Peter's pitch, all lines**: 169-206 Hz zh, 221-263 en, above his 95-135 pin. Does he sound like a big friendly
   bear, or a tenor? Is he the same man in mi_12 (panic), mi_23 (laugh), mi_27-28 (storm), mi_31 (awe)?
3. **mi_12 zh** "哎！哎！哎！我的屋顶！": whisper hears three 哎 for four; is the rising panic there and the wail funny?
4. **mi_07 zh crowd** heard 别起啦 / 别急啦, not 别挤啦 (err 0.29); **mi_21 zh crowd** adds "对，这样的事" (err 0.5): are
   the words clear and the two children audible?
5. **friend1 and friend3** sit at 239-305 Hz: friend1 is above his pin, close to friend3. Can a child tell the leader
   from the small quick one (mi_04 / mi_09 vs mi_06)?
6. **Jesus en mi_19 (199 Hz) and mi_29 (170 Hz)**: higher than his other lines (119-128). Firm, not angry, at the storm?
7. **mi_23 both**: the added laugh before "好吧好吧" / "All right": a real laugh or read "ha ha ha"?
8. **mi_27 zh** 舀水 and **mi_28 zh** (7.7 s, longest Peter line): breathless comic panic, not scary (R8)?
9. **Narrator en** median 293 Hz, up to 363 Hz on mi_14: brighter than Jonah's 271; still the same storyteller?

## Re-running (for the lead)

A scratch wrapper (not in the repo, R1) added a runaway guard: when a raw Qwen take is longer than
0.5 s per Chinese character (0.7 s per English word) + 1.5 s, it re-speaks with seed + 1000·i (up to 5 times, else the
shortest). It fired on 哎！, Hey!, Teacher!, It's no good, 挖呀挖 and the friends' chant members. Plain `voice.py gen`
has no such guard and picks by transcript first, so it can again choose a 16 s runaway take whose junk whisper ignores
(the first mi_12 zh did exactly that). If these lines are ever regenerated, put the guard in a
`tools/story/voice_miracles.py` wrapper (Jonah shape) or add a duration gate to `take_score`; that is the lead's call.
Raw takes are cached in `~/.cache/doodlive-voice` (outside the repo, shared by every pack).
