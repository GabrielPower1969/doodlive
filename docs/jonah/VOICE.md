# Jonah: voice (zh + en)

All 29 lines in Mandarin and English, 58 clips, every one Qwen3-TTS (Apache-2.0) run locally; no `edge-tts` (R7).
Engine and licence per clip: `assets/jonah/audio/voice/sources.json`. Takes were picked by measurement (transcript
error first, then pitch movement and pace), **nobody has listened yet** (V5): see "Listen first".

## Files

```
tools/story/cast_jonah.json     cast per language and role, per-line acting notes, phrases (interjections), breaths
tools/story/voice_jonah.py      thin wrapper: voice.py plus the Exodus add-ons (hall on god, timbre pinning); voice.py untouched.
                                Run: python3 tools/story/voice_jonah.py gen|check [--asr]|harvest   (same as voice.py jonah ...)
assets/jonah/audio/voice/       zh/ en/ (44.1 kHz mono WAV + 96 kbps MP3), durations.json, report.json, sources.json,
                                zh.srt, en.srt, breaths/ (real in-breaths cut from the Qwen takes)
```

## Cast (median F0 over each role's lines, Hz; per-line spread in report.json)

| Role | zh | en | Measured |
|---|---|---|---|
| narrator | Qwen CustomVoice `vivian`, best of 4 (Esther / Ruth / Daniel narrator) | **Qwen `vivian` speaking English**, best of 4 | zh 214-411 (median 277), en 216-357 (271); mean transcript error zh 0.04, en 0.00 |
| god | Qwen VoiceDesign, the Exodus description, pitch and timbre pinned to the Exodus reference, soft hall | Qwen VoiceDesign from the same description in English, pinned 85-150 Hz, same hall (Exodus' English god was edge-tts, not allowed) | zh 101-112, en 112-133; err 0.07 / 0.06 |
| jonah | **VoiceDesign** (2026-11-15; was `dylan` = Haman in Esther), mid-pitch warm stubborn man, 8 takes, pinned 135-185 Hz | Qwen `aiden`, best of 5 (unchanged) | zh 135-217 (median 172), en 128-265 (204) |
| captain | **VoiceDesign** deep gravelly bear-like bass (2026-11-15; was `uncle_fu`, shared by Daniel / Esther / Ruth, 213-354 Hz), 14 takes, pinned 90-165 Hz, warm fx | **VoiceDesign** same description in English (was `ryan` = Daniel's hero, 227-251 Hz) | zh 110-148 (median 130), en 156-171 (165): lower than Jonah in both |
| people (jn_22) | crowd of 10 Qwen voices | crowd of 10 Qwen voices | see below |

Why fixed speakers were used for Jonah and the captain (until 2026-11-15, now both designed; see "Fix log"): VoiceDesign drifted on one description in the audition (157 Hz and 330 Hz
for "the captain", 160 and 234 for Jonah) and every spliced interjection is a separate synthesis, so a designed voice
would change person between the snort and the sentence. `dylan` stayed at 122-124 Hz and sounds gruff; `aiden` is the
liveliest English male. Jonah and the captain are different engines per language, so they cannot be confused.

Crowd (jn_22): lead `serena` (0 dB), then `uncle_fu`, `vivian` +2 st, `dylan`, `eric` (zh) / `ryan`, `aiden`, `uncle_fu`
(en), a 7-year-old boy and a 5-year-old girl (VoiceDesign), and three pitch-nudged copies (-3, +2.5, -3 semitones),
staggered 0-0.35 s, others 6-12 dB under the lead, "offstage" fx (behind a wall: lows and highs rolled off, a few early
reflections) and a light hall. First mix (members at -3 to -7 dB) transcribed as nonsense; with the lead clear and
the rest quieter English reads "We were wrong. Oh God, please forgive us." and Chinese "我们做了(错了)！上帝啊！求你原谅我们".

## What makes it sound told, not read

- Interjections are their own short phrases spliced in (jn_06 snore, jn_07 轰隆隆, jn_10 唉, jn_11 扑通, jn_13 啊呜,
  jn_14 呃, jn_18 呸, jn_24 哼, jn_26 咔嚓咔嚓, jn_27 wail), each with its own acting note, in both languages.
- Real breaths: in-breaths found in the roles' own Qwen takes (`harvest`) are placed before the opening lines and
  before the prayer lines. Jonah has none of his own, so he borrows the god voice's (male) breaths.
- Acting notes in the cast file say what to feel and stress, never "slowly". jn_27 is scored by the wail measure.

## Levels

Every clip -16 LUFS (+-0.4) and true peak <= -1.5 dBTP after two manual fixes (see deviations): zh jn_11's "扑通"
pop needed a harder limiter, en jn_14 was re-levelled. Re-timed play: **281.05 s (4:41)**, the voices decide it
(zh clips total 205.5 s, en 207.0 s).

## Listen first (least trusted)

1. **jn_22 zh crowd**: transcript error ~1, ragged by design but check the words are 我们错了 and 求你原谅我们; check the two children are audible and nobody is a pitch-shifted cartoon.
2. **jn_03 zh Jonah**: whisper heard 你你唯 for 尼尼微 (err 0.25); is the name clear? Beijing-accent `dylan`.
3. **Names in zh**: whisper writes 尼尼威 (same sound as 尼尼微, ignore) but also 约纳 (nà, wrong tone) in god's jn_02 / jn_28 and 天拿 / 别拿 at the start of jn_11 / jn_15 narrator: confirm every 约拿 is ná.
4. **jn_07 zh** 轰隆隆 (heard 红楼楼) and **jn_11 zh** 扑通 (heard 噗通): comic sounds, fine if they sound like thunder and a splash.
5. **God, both languages**: same fatherly person in all three lines? en jn_28 err 0.17 (numbers "120,000" are written out by whisper); hall tail not boomy?
6. **Captain en vs zh**: loud and jolly, but a tenor-ish bass; is it big enough? jn_08 zh err 0.12.
7. **Jonah en pitch**: median 128-264 across lines, widest of any role; is he one man on the grumpy vs the wail (jn_24, jn_27)?
8. **jn_14, jn_18, jn_24 splices** (both languages): the gap between the snort and the sentence, and a visible change of voice at the join.
9. **Breaths**: borrowed male breaths on Jonah at jn_09 / jn_16 / jn_20.

## Fix log 2026-11-15 (review: voice collisions, names, crowd, silences)

Pitch measured with parselmouth `to_pitch_ac` (voicing threshold 0.55, floor 60, ceiling 450), median per line, Hz.
Wrappers hold the GPU lock (tools/story/tts_lock.py): `python3 tools/story/voice_jonah.py gen|check`; post-pass
`tools/story/voice_polish.py jonah`. Owner brief: warm, clear, friendly for young children, never scary.

| Role | zh before | zh after | en before | en after |
|---|---|---|---|---|
| jonah | `dylan` 126-176 (median 145) | designed 135-217 (172) | `aiden` 128-264 (202) | unchanged |
| captain | `uncle_fu` 354 / 250 / 213 (higher than Jonah) | designed 148 / 110 / 130 (130) | `ryan` 227-251 | designed 156 / 171 / 165 |
| god | 101-112 | 96 / 101 / 87 (jn_02 re-taken for the name) | 112-133 | 135 / 112 / 107 |
| people jn_22 | `少年！少年！`, err 1.08 | 8 crowd mixes tried (member seeds shifted), best kept; heard 我们错了！上帝！求你原谅我们 | err 0.17 | heard "We were wrong. Oh God, please forgive us", err 0.13 |

- Names (final clips, whisper): jn_03 尼尼威 (same sound as 尼尼微, was 你你唯); 约拿 in jn_02 / jn_28 / jn_11 / jn_15 (was 约纳 / 天拿 / 别拿).
  jn_02 needed `pick` 10 because the best-scoring take was heard as 约纳; ASR cannot tell ná from nà, so this is still the ear's call.
- Five lines changed text (FIXLOG-20261115.md: jn_01, 07, 12, 28, 29): re-recorded in zh and en; jn_07's phrases in the cast follow the new text.
- Captain: all zh / en lines carry "deepest bass, loud but low, never shrill" acting notes; shouting lifts a designed voice a lot.
- Silence: no clip has leading / trailing digital silence over 0.25 s; mid-line digital zero is -74 dBFS room tone (a pause over 0.8 s is cut to 0.8 s);
  levels -16.2 to -15.9 LUFS, true peak at most -1.8 dBTP. Re-timed play: 233.2 s (voices only; the app retimes per language).
- Remaining: jn_22 zh transcript error 0.46 (the crowd repeats 求你原谅我们 on purpose-ish, words are right), jn_20 zh 0.125 (这次 for 这一次).

### Round 3 (2026-11-15, REVIEW2): God warmth, names, Jacob js_02

Tools: `hnrMin` (3 points per dB under it, measured on the dry take) and `nameContour` (first syllable pitch contour from whisper word
timestamps: a falling syllable, yuè, loses 6 points per semitone of fall; yuē is high and level) in tools/story/voice_exodus.py; God's hall
wet 0.20 -> 0.14 (reverb lowers HNR); the name is its own phrase "约拿，" with the direction "第一声 yuē，高而平".

| Item | Before | After |
|---|---|---|
| God zh HNR (jn_02 / 19 / 28), dB | 4.8 / 5.3 / 2.9 | 6.5 / 9.1 / 8.8 (jn_02 is under the 8 dB target) |
| God en HNR, dB | 5.4 / 6.8 / 8.6 | 10.4 / 9.5 / 8.5 |
| God zh median F0 | 96 / 101 / 87 | 120 / 127 / 128 (a warmer, clearer, slightly higher fatherly voice, 1.4 st spread) |
| God design | "deep, weighty, warm" | "warm, clear, smooth, clean, never hoarse or breathy, a smiling kind father"; mfccRef dropped (it pinned the Exodus timbre) |
| God's 约拿 (whisper) | 月娜 / 约纳 (jn_19, jn_28, jn_02) | 约拿 in all three |
| Jacob's 约瑟 (whisper) | 月色 (js_02, js_11, js_30) | 约瑟 in all three |
| Jacob F0 (js_02 / 11 / 30) | 143 / 86 / 100 | 105 / 85 / 105 |
| Jacob HNR (js_02 / 11 / 30) | 8.3 / 4.7 / 5.9 | 7.2 / 5.9 / 5.9 |

First-syllable contours of the chosen takes (slope = last third minus first third of the syllable, semitones; positive or near zero = level
or rising = yuē; yuè would be clearly negative): jn_02 +1.2 st (124 Hz), jn_19 +1.3 (148 Hz), jn_28 +3.8 (141 Hz), js_02 +3.8 (116 Hz),
js_11 +1.1 (87 Hz), js_30 +5.1 (209 Hz, the laugh). All six are level or rising. Whisper is a C-level witness for tone: listen to the six.
Levels -16.8..-15.9 LUFS, peak <= -1.5 dBTP, no silence over 0.25 s at the ends; durations.json rebuilt; build_timeline re-run
(Joseph 270.2 s, Jonah 232.4 s).
