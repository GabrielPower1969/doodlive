# Ruth: voice (zh + en)

All 27 lines of `assets/ruth/timeline.json` in Mandarin and English, 54 clips. Brief (CONTRACT.md §7): people telling a
story to a 4-10-year-old, not text being read; real breaths, varied pauses, moving pitch, interjections that sound
like sounds; Naomi clearly older than Ruth; Boaz a warm baritone; the reapers 3-4 ragged voices across a field.
Voices were chosen and takes kept **by measurement, not by ear** (Esther's method, docs/esther/VOICE.md), so listen to
the clips under "Listen first" before shipping.

## Files

```
tools/story/voice.py           generic tool (gen / import / check / session); Ruth added small hooks only:
                               `say` / `sayMap`, the voice_extras hooks, a "field" fx, whisper prompted to simplified
                               Chinese, VoiceDesign engine `qwen_design` (added by the Esther session)
tools/story/voice_extras.py    Ruth's extras, inert for casts that do not use them: real breaths, VoiceDesign pitch
                               pinning (f0Hz), husky-voice gate (hnrMax), key-word gate (maxErr)
tools/story/cast_ruth.json     cast per language + role, per-line acting notes, phrases, breaths, overrides
assets/ruth/audio/voice/
  zh/<id>.wav en/<id>.wav      44.1 kHz mono 16-bit, -16 LUFS (+-0.4), true peak <= -1.5 dBTP   (Unity)
  zh/<id>.mp3 en/<id>.mp3      96 kbps mono                                                       (web)
  durations.json sources.json report.json zh.srt en.srt     as Esther (report has whisper + Praat measures)
  breaths/                     real in-breaths cut from the Qwen takes (breaths.json says which take and where)
  record/zh/ record/en/        recording sheets for people (`voice.py ruth session`)
```

## Cast

| Role | zh | en | fx |
|---|---|---|---|
| Narrator | **Qwen3-TTS CustomVoice `vivian`**, best of 4, acting note per line | **en-US-AvaMultilingualNeural**, phrased | plain |
| Ruth | **Qwen `serena`**, best of 4 | **en-US-EmmaMultilingualNeural**, phrased | plain |
| Naomi | **Qwen3-TTS VoiceDesign** ("女性，六十多岁的老奶奶…略带沙哑和气声"), best of 6, pitch-pinned 140-205 Hz (140-250 on her happy lines) | **Qwen VoiceDesign** ("Female, around seventy… husky, breathy, slightly creaky"), best of 6, pinned 130-185 Hz (130-210 happy), `hnrMax` 12 dB | plain |
| Boaz | **Qwen `uncle_fu`**, best of 4 | **en-US-AndrewMultilingualNeural**, phrased | warm |
| Reapers (ru_10) | crowd of 4: Yunjian (lead) + Qwen `eric` + Xiaoyi + Qwen `dylan`, staggered 0 / 0.08 / 0.14 / 0.22 s, -0 / -6 / -6 / -8 dB, light field room | crowd of 4: Guy + Natasha + Roger + Thomas, staggered 0-0.33 s | field |

Same engines as Esther where they were proven (Qwen CustomVoice for zh, phrased Multilingual edge voices for en), so
the narrator, Ruth and Boaz in Chinese share timbres with Esther's narrator, Esther and king. Naomi is new in both
languages: no stock voice is an old woman, so she is designed from a written description.

`sayMap.zh` = {路得: 路德, 俄备得: 俄备德}: the engine is given 德 (dé) so 得 cannot be read de/děi (whisper heard
路逮 / 路的 / 陆的 on the first pass); subtitles keep 路得. Per-line `say`: ru_01 zh (commas instead of …… for the
synthesis only, before Story shortened the line), ru_11 en ("Hmm?": edge read "Hm?" as the letters H-M).

## What is new compared with Esther

- **Real breaths, never synthetic.** `voice_extras.py harvest` finds in-breaths that the Qwen voices produced
  themselves (unvoiced, 20-42 dB under the speech, 0.2-0.75 s, out of silence, centroid < 3.5 kHz so a sibilant is not
  mistaken for one; cut 50 ms short of the next word) and keeps 3-4 per voice. Lines whose `dir` asks for a breath or a
  sigh get one before the line or in the pause after an anchor phrase, at the voice's own level relation: ru_01 (after
  两个儿子 / two sons, -4 dB), ru_02, ru_03 (after 我也住在哪里 / I will stay), ru_05, ru_13, ru_17, ru_19 (after
  感谢上帝 / Thank God), ru_21 (after 您是我们的亲人 / our family), ru_22, ru_25, in both languages (all 20 placed; the
  edge voices borrow the matching Qwen voice's breaths, `breathFrom`). If a take already breathes there it is kept.
- **VoiceDesign drift is measured and pinned.** The same description gives a different person on each seed (smoke
  test: 98 Hz vs 189 Hz median; Naomi zh audition 153-258 Hz over 4 takes). `f0Hz` penalises takes outside the role's
  range (-3 points per 10 % outside), so the kept takes stay one woman. English Naomi also has `hnrMax`: on the first
  English design her voice was *clearer* than Ruth's (HNR 14.9 vs 13.2 dB); the redesign plus the gate brought her to
  11.0 dB.
- **Key words win over liveliness.** `maxErr` (ru_03 zh: the liveliest take said 我……我不走 instead of 不，我不走) and
  the laugh measure on ru_15 / ru_17 zh.
- **Acting notes without 慢.** The first zh pass, with "慢慢地说 / 放慢" in the notes, gave 23-26 s takes for an 11 s line;
  the notes now say what to stress, not to slow down.
- **The crowd is intelligible.** Members alone were clear, but the edge members were ~1 s slower than the Qwen ones
  and the first mix transcribed as noise (CER 1.25); pace-matched, a clear lead voice and 0.08-0.22 s offsets it
  transcribes exactly while staying ragged.

## How it was chosen (2026-11-14)

Audition (throw-away, killed early because 16 GB was shared with Blender and the Esther session; numbers are what it
reached): edge narrators on 4 real lines each, edge Boaz candidates on 2 lines (F0 only), Naomi VoiceDesign zh 4 takes.

| Candidate | F0 SD st | range st | pause CV | err | median F0 | note |
|---|---|---|---|---|---|---|
| narrator en: **Ava ML** | 4.11 | 11.7 | **0.43** | 0 | 198 | most breaths/pause variety, consistent (192-202 Hz) |
| narrator en: Emma ML | 4.63 | 14.6 | 0.24 | 0 | 175 | kept for Ruth instead |
| narrator en: Jenny | 2.85 | 9.1 | 0.78 | 0 | 180 | flat |
| ruth en: **Emma ML** | **5.86** | 17.1 | 0.35 | 0.03 | 208 | most consistent timbre of all (MFCC spread 19.9) |
| ruth en: Michelle | 3.21 | 8.4 | | 0 | 189 | flat |
| boaz en: **Andrew ML** | **5.8 / 4.2** | 18.4 / 13.6 | | | 116-125 | deep and the liveliest |
| boaz en: Christopher (Esther's king) | 3.8 / 3.7 | 12.7 / 11.7 | | | 109-112 | |
| boaz en: Brian ML / Guy / William ML | 3.1 / 5.2 / 4.4 | | | | 122 / 160 / 101-119 | Guy not deep |

Final clips (`report.json`, `check --asr`; mean per role; err = CER zh / WER en; HNR lower = breathier):

| Role | lang | F0 SD st | range st | phrase-rate CV | pause CV | err | median F0 Hz | HNR dB | pace |
|---|---|---|---|---|---|---|---|---|---|
| narrator | zh | 4.67 | 14.7 | 0.11 | 0.45 | 0.037 | 240 | 13.4 | 3.49 ch/s |
| ruth | zh | 3.37 | 10.1 | 0.13 | 0.33 | 0.035 | 254 | 13.5 | 3.65 |
| naomi | zh | 5.09 | 13.9 | 0.13 | 0.44 | 0.018 | **177** | **9.6** | 2.41 |
| boaz | zh | 7.17* | 22.7* | 0.12 | 0.34 | 0.023 | 192* | 8.8 | 3.08 |
| reapers | zh | | | | | 0.000 | | | |
| narrator | en | 4.50 | 14.5 | 0.13 | 0.38 | 0.014 | 194 | 13.6 | 3.39 syl/s |
| ruth | en | 6.14 | 17.5 | 0.12 | 0.34 | 0.051 | 206 | 13.2 | 3.47 |
| naomi | en | 5.11 | 14.2 | **0.26** | **0.53** | 0.000 | 203 | **11.0** | 1.88 |
| boaz | en | 5.10 | 16.3 | 0.13 | 0.36 | 0.073 | **124** | 10.5 | 4.06 |
| reapers | en | | | | | 0.000 | | | |

\* uncle_fu's pitch track jumps octaves on creaky frames (Esther saw the same); read as "lively", not as 192 Hz.

Naomi vs Ruth: zh Naomi is 77 Hz lower, 3.9 dB breathier and has more jitter (2.09 vs 1.51 %): measurably older.
en Naomi is breathier (11.0 vs 13.2 dB) and slower but **not lower** in pitch than Emma's Ruth (203 vs 206 Hz).
Most remaining "errors" are whisper homophones (路得→路德/鲁德, 拾→石, 啦→了, 田→天, Boaz→Boas), not misreadings.

Totals: **zh 184.7 s, en 166.1 s** of speech; the play is 229.1 s (`build_timeline.py ruth`, timed from the voices; the
longer language sets each slot, so English has extra music under some lines, e.g. ru_01 zh 11.7 s / en 9.4 s).
(The table above was measured before Story's ru_01 / ru_15 rewrite; those three clips changed little.)

## Listen first

1. **en Naomi (ru_02, 05, 17, 19, 25)**: VoiceDesign has no fixed speaker, so each line is a take that passed the pitch
   and breathiness gates, not one recorded voice. ru_19 measured very rough (HNR ~2 dB: crying or a glitch), ru_02 is
   slow (11.5 s). If she sounds like different women, the fix is the Qwen3-TTS **Base** model (voice cloning from one
   designed reference take; not in the local cache, needs a 1.7B download) or a person's recording (`import`).
2. **zh Naomi ru_17 (哇！这么多呀)**: the kept take is the liveliest but trails off (哇……这么多呀……你今天……, 8.2 s); ru_19
   zh likewise. Alternative: `"seed": 6` under `lines.ru_17.zh`.
3. **en ru_15 Boaz**: edge-tts could not make a pure "psst" (every spelling had a vowel: "Pussed", the letters
   P-S-S-S-T), so Story changed the line to open with "Listen..."; whisper now hears every word. Still no stage
   whisper or real chuckle in English (edge reads "Heh heh"); zh ru_15 has 嘘 and 嘿嘿 from Qwen but the laugh measure
   rated it "read", not a laugh.
4. **zh ru_01 (11.7 s, shortened line)**: on the final clip whisper hears the first words as 等就以前 (CER 0.13), although
   it heard 很久以前 on the same take before levelling and the opening breath is not the cause (removing it changed
   nothing). Listen to the first syllable; if 很 is mumbled, `"seed": 4` under `lines.ru_01.zh` gives four new takes.
5. **zh ru_10 reapers**: the mix is now clear; check it still sounds like people across a field and not one voice
   with an echo.
6. **Breaths**: 20 inserted; each is a real Qwen in-breath, but placement is automatic (anchor from whisper's word
   times). ru_01 zh/en and ru_03 zh are the ones to hear.
7. zh Ruth and Boaz are Esther's Esther and king voices (serena, uncle_fu): fine within Ruth, but a child who plays both
   packs will hear the same people.

## Clips changed after the 12:30 commit (3d0090b)

Second round (Story rewrote ru_01 both languages and ru_15 en; same voices, breaths before and inside ru_01):

| Clip | Why | Length then -> now |
|---|---|---|
| zh/ru_01 | new shorter line | 14.55 -> 11.65 s |
| en/ru_01 | new shorter line | 11.95 -> 9.37 s |
| en/ru_15 | new line ("Listen..." instead of "Psst...") | 6.15 -> 6.12 s |

First round:

| Clip | Why | Duration then -> now |
|---|---|---|
| zh/ru_10 | reapers mix was unintelligible (whisper CER 1.25 -> 0.00) | 2.41 -> 2.23 s |
| en/ru_11 | edge read "Hm?" as the letters H-M; now "Hmm?" | 2.49 -> 2.27 s |
| en/ru_02, ru_05, ru_17, ru_19, ru_25 | English Naomi was not older than Ruth (HNR 14.9 vs 13.2 dB); redesigned + husky gate (now 11.0 dB) | 9.09 -> 11.53, 6.04 -> 8.79, 4.53 -> 6.73, 5.83 -> 7.28, 4.39 -> 7.03 s |

`build_timeline.py ruth` was re-run after each round (play 228.05 -> 232.04 -> 229.14 s); `voice.py ruth check`: all
clips fit.

## Regenerate

```bash
python3 tools/story/voice.py ruth gen                       # 54 clips; Qwen takes are cached in ~/.cache/doodlive-voice
python3 tools/story/voice_extras.py harvest ruth            # after new Qwen takes: refresh the breath library, then gen again
python3 tools/story/voice.py ruth check --asr
python3 tools/story/build_timeline.py ruth && python3 tools/story/voice.py ruth check
python3 tools/story/voice.py ruth session                   # recording sheets for a family recording (`import` replaces a clip)
```

Uncached, the zh pass is ~27 lines x 4-6 takes at 30-60 s each (about 1.5 h on the 16 GB M1 Pro while other jobs run);
run one Qwen job at a time: two at once swapped the machine to a crawl.
