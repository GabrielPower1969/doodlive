# The prodigal son: voice (zh + en)

All 29 lines of `assets/prodigal/timeline.json` in Mandarin and English, 58 clips, made 2026-11-14. Brief (CONTRACT.md
§7): the son changes across the story (cheeky, then small and broke, then sorry, then overjoyed) but stays one person;
the father warm and about sixty, never frail, a catch in his voice, and not Moses / Boaz / Esther's king; the brother
firm, grumbling, hurt, and not the son; friends 3-4 voices, servants 2-3; the narrator as the other packs. Takes were
kept **by measurement** (whisper word accuracy first, then liveliness, pace, a pitch pin and a timbre pin), as Exodus.
Nobody has listened yet: read "Listen first" before shipping.

## Files

```
tools/story/cast_prodigal.json   cast per language + role, acting note per line (m = zh note; en uses the line's dir),
                                 pitch pins, timbre pins (mfccRef) and keep-away pins (mfccAvoid), en phrasing for
                                 edge, `designs` = the descriptions tried and why they were replaced
tools/story/voice_prodigal.py    wrapper (voice.py / voice_extras.py / voice_exodus.py are NOT edited). Imports the
                                 Exodus wrapper (role reverb, line grid, mfccRef pin: story-agnostic) and adds:
                                 takes.json, role `f0Ceil` (octave-safe median F0 for the pitch pin), role `mfccAvoid`,
                                 a true-peak fallback, `audition`, `timbre`, `preview`, `prune`
assets/prodigal/audio/voice/
  zh/pr_XX.wav en/pr_XX.wav      44.1 kHz mono 16-bit, -16 LUFS (+-0.3; zh pr_05 -16.9, see below), true peak <= -1.7 dBTP
  zh/pr_XX.mp3 en/pr_XX.mp3      96 kbps mono
  durations.json report.json sources.json zh.srt en.srt   as Exodus (report: whisper + Praat measures per clip)
  takes.json                     every take: score, word error, pitch SD, pace, length, robust F0, timbre distance to the
                                 role's reference (and to the voice it must avoid), transcript; and the one kept
  timbre.json                    per role: spread of its own lines, distance between roles, distance to other packs
  preview_zh.mp3 preview_en.mp3  every clip at its timeline time, voices only (218.1 s)
```

## Cast

| Role | zh | en | fx |
|---|---|---|---|
| narrator | Qwen3-TTS CustomVoice `vivian`, best of 3, the Ruth / Esther / Exodus note | edge `en-US-AvaMultilingualNeural` -8 % | plain (same storyteller as every pack) |
| son | Qwen **VoiceDesign** "二十岁左右的小儿子，大男孩。声音年轻、明亮、清亮，音调中等偏高…有点调皮、爱耍宝，情绪变化大", best of 5, pitch pin 150-265 Hz, timbre pin to the audition take pr_02 seed 0 | edge `en-US-BrianMultilingualNeural` (young, casual); sad / crying lines phrased with slower rate and lower pitch | plain |
| father | Qwen **VoiceDesign** "六十岁左右的爸爸…温暖、圆润、干净的男中音，一点也不沙哑、不粗糙…常常带着笑意…一动情声音就有点哽咽。身体硬朗", best of 5, pin 110-210 Hz, timbre pin to audition pr_27 seed 0, kept >= 85 from Moses' timbre centroid | Qwen **VoiceDesign** "about sixty… a clear, smooth, warm and gentle baritone… not gravelly, not husky… his voice catches when he is moved", best of 4, pin 100-200 Hz, timbre pin to audition pr_21 seed 1, kept away from en Moses | warm |
| brother | Qwen **VoiceDesign** "二十八岁左右…庄稼汉，大个子。声音低沉、厚重、有点粗哑，鼻音重一点，说话闷声闷气…爱发牢骚，心里委屈", best of 4 (pr_05: 5, seeds 4-8), pin 95-185 Hz, timbre pin to audition pr_26 seed 0, kept >= 90 from the son | edge `en-US-AndrewMultilingualNeural` -4 Hz, phrased ("Hmph." / "Huh?" / "What?" as their own phrases) | plain |
| friends | crowd of 4: Yunxi (lead) + Xiaoyi + Qwen `dylan` + Xiaoxiao (+0.8 st), offsets 0-0.2 s, small room; pr_10 drifts away (tail fade 1.2 s) | crowd of 4: Eric (lead) + Libby + Liam + Aria (+0.8 st); same tail on pr_10 | plain |
| servants | crowd of 3: Yunjian (lead) + Yunyang (-1 st) + Xiaoyi | crowd of 3: Roger + Thomas + Natasha | plain |

Why these:

- **No CustomVoice speaker fits the son.** Of the nine Qwen speakers the young men are `dylan` (Esther's Haman, Beijing
  dialect), `eric` (Sichuan dialect), `ryan` / `aiden` (English; Daniel's en roles). `eric` was auditioned because a
  fixed speaker keeps one timbre: he read 饿 as 我, 做 as 住, 猪吃 as 竹子 / 主持 even when told to speak standard
  Mandarin (word error 0.15-0.43). So the son is designed, held by the pitch pin and the timbre pin.
- **The father was designed twice.** The first description (warm, "略带一点沙哑") measured 51 from Moses' timbre
  centroid in zh and 36 in en, inside Moses' own spread (117 / 120): the same kind of voice. The second description
  asks for a clean, round, smiling voice with no husk, and each take now loses points when it comes within 85 of Moses.
  Kept: zh father 80 from Moses, 79 from Boaz, 115 from Esther's king; en father 80 from Moses, 181 from Boaz (Andrew),
  139 from Esther's king (Christopher). Uncle_fu (Boaz, both kings) is not used.
- **The father is Qwen in English too, not edge**: he sighs (pr_03), gasps (pr_19) and laughs through tears (pr_21);
  edge does none of that, and the deep multilingual edge voices are taken (Andrew = Boaz, William = Exodus God /
  Daniel's king). Exodus did the same for Moses.
- **The brother was designed three times.** The first two descriptions came out as high as the son (184-215 Hz,
  timbre 50 from the son's centroid). The third (low, thick, a little nasal and gruff) is 81 from the son in zh. In en
  he is edge Andrew, which is also Ruth's Boaz: 146 from the son, but 42 from Boaz (the same voice). If that matters, see
  "Listen first".
- **English son on edge (Brian)** as the brief asks: the most natural young multilingual voice, but edge cannot cry or
  sigh; pr_13 / pr_14 / pr_20 carry the mood by slower phrases and a lower pitch only.

### Audition (2026-11-14, octave-safe median F0 = pitch ceiling 300 Hz; scratch, audio deleted)

| Candidate | line / seed | F0 Hz | F0 SD st | HNR dB | word error | note |
|---|---|---|---|---|---|---|
| son zh design | pr_02 s0 / s1, pr_13 s0 / s1, pr_20 s0 / s1 | 202 / 200 / 224 / 165 / 171 / 177 | 4.7-5.8 (pr_20 1.9) | 11.6-21.9 | 0-0.15 | kept; pr_02 s0 is the timbre reference |
| son zh `eric` | pr_02, pr_09, pr_13, pr_16, pr_20 | 125-181 | 2.5-8.4 | 8-20 | 0-0.43 | Sichuan accent: rejected |
| father zh design 1 (husky) | pr_03 s0 / s1, pr_21 s0 / s1 | 76 / 102 / 175 / 125 | 2.7-13 | 4.0-6.1 | 0 | close to Moses: replaced |
| **father zh design 2** (clean) | pr_27 s0 / s1, pr_21 s0 / s1 | **157** / 91 / 159 / 181 | 4.0-7.3 | **11.1** / 7.0 / 9.2 / 8.2 | 0 | pr_27 s0: 81 from Moses |
| brother zh design 1 / 2 | pr_26, pr_25, pr_24 | 173-215 | 4-7 | 5.5-10 | 0-0.2 | as high as the son |
| **brother zh design 3** | pr_26 s0 / s1, pr_24 s0 / s1 | **129** / 160 / 191 / 122 | 6.7-9.6 | 4.9-11.3 | 0 | pr_26 s0: 114 from the son |
| father en design 1 | pr_21, pr_27 | 182 / 204 / 153 / 88 | 3.4-5.8 | 10.7-14.3 | 0 | 36 from Moses: replaced |
| **father en design 2** | pr_27 s0 / s1, pr_21 s0 / s1 | 134 / 104 / 182 / **143** | 3.8-7.6 | 10.8-14.8 | 0 | pr_21 s1: 113 from Moses |

## Measurements of the kept clips (`voice.py prodigal check --asr`)

| Role | lang | lines | F0 SD st (mean) | word error (mean) | median F0 Hz* | pace |
|---|---|---|---|---|---|---|
| narrator | zh | 7 | 4.85 | 0.000 | 262 | 3.70 ch/s |
| son | zh | 10 | 4.79 | 0.020 | 237 | 3.89 |
| father | zh | 5 | 5.44 | 0.000 | 122 | 2.53 |
| brother | zh | 4 | 6.33 | 0.000 | 106 | 2.47 |
| friends | zh | 2 | | 0.567** | | |
| servants | zh | 1 | | 0.000 | | |
| narrator | en | 7 | 4.27 | 0.005 | 192 | 3.88 syl/s |
| son | en | 10 | 3.03 | 0.011 | 129 | 3.16 |
| father | en | 5 | 5.90 | 0.040 | 140 | 2.54 |
| brother | en | 4 | 5.20 | 0.062 | 121 | 4.12 |
| friends / servants | en | 2 / 1 | | 0.000 | | |

\* voice.py's 600 Hz ceiling: excited men read high (zh son 237 Hz here, 195-225 Hz octave-safe).
\** crowds: whisper writes zh pr_08 好耶 as 好练 and repeats half of pr_10 (layered voices); not a wrong read.

Timbre (mean MFCC 1-12; `timbre.json`): own-line spread zh son 115, father 83, brother 79; en son 71, father 64,
brother 54. Between roles: zh son-brother 81, son-father 108, father-brother 98 (zh: the brother 55 from Moses and 45
from Exodus God, the father 46 from Exodus God and 46 from Daniel; not in the brief, noted). en son-brother 146,
son-father 124.

Loudness -15.9 to -16.3 LUFS except **zh pr_05 at -16.9** (a 2.4 s line that starts with a loud 哼: the limiter holds
the peak, so the level-to-target loop stops 0.9 LU short; it sits just under the brother's other lines). True peak
-1.7 to -3.5 dBTP. en pr_03 first came out at -1.2 dBTP (inter-sample overs from energy above 10 kHz); the wrapper's
fallback rolled it off above 10 kHz and levelled it again: -1.9 dBTP.

Totals: **zh 152.4 s, en 144.1 s** of speech (zh: narrator 42.0, son 38.4, father 39.4, brother 23.4, friends 7.9,
servants 1.6; en: 43.6 / 41.4 / 35.7 / 14.9 / 6.9 / 1.5). `build_timeline.py prodigal` (timed from these voices):
**218.05 s** (the estimate was 217.35 s; the brief said about 4 minutes).

`voice.py prodigal check`: every clip fits; one flag, **en pr_20 -> pr_21 gap 0.10 s** (< 0.2 s). That is the
storyboard's own timing (pr_20 `post=0.0`, pr_21 `pre=0.1`: the father cuts in before the son finishes), not a voice
fault; Story owns `story.py` if the flag should go.

## Takes and choices worth knowing

| Line | Kept | Note |
|---|---|---|
| zh pr_05 | seed 5 (take 1 of seeds 4-8) | first run (seeds 0-3): the best score dropped the 哼 (就知道玩。); the re-run's five takes all have it |
| zh pr_21 | take 0 | closest to the father's timbre (26); no take of the clean father laughed (the first, husky design had one: 哈哈哈哈 + line, 201 Hz, 114 from its reference) |
| zh pr_23 | take 1 | take 4 (呵呵呵 + line) scored higher but word error 0.27 |
| zh pr_19 | take 2 | two takes opened with a real 哈哈哈哈 but were other men by timbre (121 / 158 from the reference); kept take 97, 206 Hz (excited) |
| zh pr_03 | take 0 | real 唉 sigh, catch before 要小心啊; 9.0 s for a short line (the note's pauses) |
| en pr_03 | take 0 | whisper writes "alright" for "all right" (error 0.2 on every take) |

Interjections heard by whisper in the kept clips: zh 唉 (pr_03), 哼 (pr_05, pr_25), 咦 (pr_09, pr_24), 嗯 (pr_17);
en "Huh?" (pr_09, pr_24), "Hmm" (pr_17); en "Hmph" is not transcribed in pr_05 and comes out as "Oomph" in pr_25
(edge reads the word; listen).

## Listen first (weakest, by measurement)

1. **zh son as one person.** His lines spread 115 in timbre (narrator 130 for comparison; father 83). pr_04 (114),
   pr_09 (105) and pr_20 (95) are furthest from his centre. If one sounds like another boy, re-pick with new seeds
   (`"seed": 10` under `lines.pr_XX.zh`) and `gen --only pr_XX`.
2. **zh father, does he sound like Moses or Exodus God?** 80 from Moses after the redesign (was 51), but 46 from Exodus
   God and from Daniel. Also check he is warm, not young: pr_19 is 206 Hz.
3. **en son crying (pr_20) and weak (pr_13, pr_14).** Edge Brian only slows and drops pitch; F0 SD 3.0 st is the
   flattest role. If it is not enough, the alternative is Qwen for the en son too (VoiceDesign, as the en father).
4. **en brother = Andrew = Ruth's Boaz.** Distinct from the son (146), but the same voice as Boaz in Ruth.
5. **en pr_05 / pr_25 "Hmph"** read by edge (whisper hears "Oomph" / nothing).
6. **zh pr_19 / pr_21** have no laugh through tears (the takes that laughed were other men by timbre).
7. **zh pr_05** is 0.9 LU under target.
8. **Crowds** (pr_08, pr_10, pr_22): chosen by ear-less rules; check the friends' 好耶 and that pr_10 drifts away.

## Regenerate

```bash
python3 tools/story/voice_prodigal.py gen [--lang zh|en] [--only pr_02,...]   # Qwen takes cached in ~/.cache/doodlive-voice
python3 tools/story/voice.py prodigal check --asr
python3 tools/story/build_timeline.py prodigal && python3 tools/story/voice.py prodigal check
python3 tools/story/voice_prodigal.py timbre --lang zh                          # and --lang en
python3 tools/story/voice_prodigal.py preview --lang zh                         # and --lang en
python3 tools/story/voice_prodigal.py prune                                     # drop this pack's rejected raw takes
python3 tools/story/voice_prodigal.py audition father zh pr_27 --seeds 0,1      # try a voice before committing to it
```

Only the 33 kept raw takes stay in the cache (`prune` deleted 167 rejected ones, 49 MB; it re-derives the kept takes'
cache keys from the cast file and only touches files this pack's runs made). On this shared machine a take took about
1 min; the generator was driven line by line with retries (`gen --only pr_XX`), no Metal error occurred this time.
