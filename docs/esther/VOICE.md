# Esther: voice (zh + en)

All 18 lines of `assets/esther/timeline.json` in Mandarin and English, 36 clips. The brief (CONTRACT.md §7,
owner review 2026-11-13): David & Goliath's voices "sound like AI, no human touch"; these must sound like people telling a
story to a 4-10-year-old. Voices were chosen without listening, by measurement (below), so **listen to the clips
flagged under "Listen first" before shipping**.

## Files

```
tools/story/voice.py              generic tool for any story: gen / import / check / session
tools/story/cast_esther.json      cast per language + role, per-line phrasing / prosody / acting notes
assets/esther/audio/voice/
  zh/<id>.wav  en/<id>.wav        44.1 kHz mono 16-bit PCM, TTS -16 LUFS, true peak <= -1.5 dBTP   (Unity)
  zh/<id>.mp3  en/<id>.mp3        96 kbps mono                                                       (web)
  durations.json                  {"zh": {"es_01": 8.91, ...}, "en": {...}} seconds; build_timeline.py reads it
  sources.json                    per clip: "edge:<voice>", "qwen:<speaker> (best of 4)" or "own:<folder>"
  report.json                     per clip: seconds, slack, gap to next line, LUFS, true peak, source, and
                                  (after `check --asr`) pitch / pause / pace / whisper transcript + error rate
  zh.srt  en.srt                  one cue per line
  record/zh/  record/en/          voice-record session (lines.json + record.html) for people to re-record lines
```

## Cast

| Role | zh voice | en voice | fx | Brief |
|---|---|---|---|---|
| Narrator | **Qwen3-TTS `vivian`** (local), best of 4 takes, acting note per line | **en-US-AvaMultilingualNeural**, rate -8 %, phrased | plain | warm female storyteller |
| Esther | **Qwen3-TTS `serena`** (local), best of 4 | **en-US-EmmaMultilingualNeural**, rate -4 %, phrased | plain | young woman, warm, brave |
| King Xerxes | **Qwen3-TTS `uncle_fu`** (local), best of 4 | **en-US-ChristopherNeural**, rate -10 %, pitch -2 Hz, phrased | warm | deep, slow, kind when calm |
| Haman | **zh-CN-YunxiNeural**, pitch +2 Hz, phrased | **en-GB-RyanNeural**, pitch +4 Hz, phrased | nasal | sly, comic, slightly nasal, never scary |
| Mordecai (off-stage) | **zh-CN-YunyangNeural**, rate -8 %, pitch -4 Hz, phrased | **en-GB-ThomasNeural**, rate -8 %, pitch -4 Hz, phrased | offstage | gentle older man from the next room |

No voice plays two roles in one language. The narrator is no longer David & Goliath's (Xiaoxiao / Sonia): that pair is
what was judged "AI" (STORY.md still says "same voice as David & Goliath"; this file supersedes it for Esther).

Engines:

- **edge**: Microsoft neural voices through edge-tts (text goes to Microsoft; it is public Bible paraphrase only).
  Deterministic. Natural sentence prosody, but one flat read per call, so `voice.py` speaks a line in **phrases**
  (`lines.<id>.<lang>.phrases` in the cast file), each with its own rate and pitch, joined by a chosen silence
  (`gap`, 0.12-0.55 s). That is where the direction goes: slower on a name, a held beat before a question, a quicker
  happy ending. Phrases may re-punctuate a line ("His name was... King Xerxes.") but never change its words;
  `voice.py` refuses a phrase list that does not spell the line.
- **qwen**: Qwen3-TTS 1.7B CustomVoice (8-bit MLX, `mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit`, 3.1 GB in
  the Hugging Face cache) run locally on the Mac; nothing leaves the machine. It takes an acting note: the role's
  `instruct` plus the line's Chinese direction (`lines.<id>.m`, the same words the human recording sheet shows).
  It is stochastic and sometimes drags, leaves dead air or swaps a word, so every line is spoken **4 times**
  (seeds 0-3) and `voice.py` keeps the best take: a whisper transcript must match the text, no internal silence
  longer than `maxPause` (1.0 s, 1.2-1.4 s where the direction asks for a held beat), no dragging below `minPace`
  (3.3 characters/s over the clip), then the liveliest pitch and the most varied phrase pace wins. Takes and scores
  are printed during `gen`.

Role processing (`fx`, before levelling): `plain` 70 Hz high-pass; `warm` (king) +2 dB at 140 Hz; `nasal` (Haman)
+4 dB at 1.1 kHz, -2 dB at 250 Hz, 140 Hz high-pass (comic, not a filter effect); `offstage` (Mordecai) 160 Hz-5.2 kHz
band, -2 dB presence and four early reflections at 17-61 ms: a voice from the next room. No pitch shifting anywhere:
it is the first thing that makes a voice sound processed.

Level chain: every TTS clip goes through the `expressive` chain, which is the gentle `natural` chain of LESSONS L50
(1.8:1 soft-knee compressor, 25 ms attack, 8/200 ms limiter) aimed at -16 LUFS, so a shout or a gasp keeps its
peak. Silence trimmed at both ends (-45 dB), 30 ms lead-in, 60 ms tail. No time-stretching: the timeline adapts.

## How the voices were chosen (2026-11-14)

Every candidate spoke **all of its character's real lines** (228 edge-tts clips: 6-7 candidates per role and
language, including the Multilingual voices speaking Chinese; 65 Qwen3-TTS clips with acting notes). Each clip was
transcribed locally with mlx-whisper large-v3-turbo and measured with Praat (parselmouth):

| Measure | What it shows |
|---|---|
| F0 SD (semitones, voiced frames) and F0 5-95 % range | intonation liveliness; flat = robotic |
| phrase-rate CV (syllables/s per phrase between pauses) | pace varies like speech, not a metronome |
| pauses per internal punctuation mark, pause-length CV | breaths where the text breathes, not all the same length |
| whisper error rate (CER zh / WER en) and mean token log-probability (zh) | intelligible; the log-probability exposes a foreign accent that the error rate forgives |
| clip length, longest silence, speech fraction | (Qwen) runaway takes and dead air |

Scores are z-scores inside each role/language group (F0 SD + ½ range + rate CV + ½ pause CV + pause/punctuation
closeness to 1), with clips above 12 % error rejected. Full tables: `report.json` holds the final clips' measurements (`check --asr`).
The audition itself (293 clips) was a throw-away run; its numbers are summarised here.

Mean over each role's lines (F0 SD and range in semitones; CV = coefficient of variation; err = CER zh / WER en):

| Role, lang | Candidate | F0 SD | range | phrase-rate CV | pause CV | err | zh log-prob |
|---|---|---|---|---|---|---|---|
| narrator zh | **Qwen vivian (final, best takes)** | **4.89** | **15.1** | **0.17** | **0.61** | 0.045 | |
| | Xiaoxiao, phrased | 4.25 | 12.0 | 0.14 | 0.24 | 0.06 | |
| | Xiaoxiao, one call per line (David & Goliath style) | 3.84 | 11.8 | 0.12 | 0.42 | 0.04 | -0.146 |
| | Emma Multilingual speaking zh | 5.05 | 15.6 | 0.14 | 0.46 | 0.05 | -0.163 |
| esther zh | **Qwen serena (final)** | **3.56** | **11.1** | **0.30** | **0.61** | 0.027 | |
| | Xiaoyi, phrased | 3.41 | 9.5 | 0.12 | 0.25 | 0.04 | -0.107 |
| | Ava / Emma Multilingual speaking zh | 3.9-4.9 | 11.7-15.6 | 0.14-0.19 | 0.13-0.27 | 0.04 | -0.21 / -0.22 (accent) |
| king zh | **Qwen uncle_fu (final)** | **6.61** | **21.7** | **0.23** | 0.47 | 0.014 | |
| | Yunjian, phrased | 4.81 | 15.3 | 0.13 | 0.37 | 0.07 | -0.100 |
| haman zh | **Yunxi, phrased (final)** | 5.17 | 16.2 | 0.15 | 0.32 | 0.016 | |
| | Qwen dylan | 6.06 | 17.4 | 0.11 | 0.80 | 0.02 | (es_16 "fast panic" came out 7.7 s with a 2.2 s gap) |
| mordecai zh | **Yunyang, phrased (final)** | 9.5* | 28* | 0.18 | 0.35 | 0.08 | |
| narrator en | **Ava Multilingual, phrased (final)** | **5.04** | **19.1** | 0.19 | 0.21 | 0.00 | |
| | Sonia (David & Goliath) | 3.73 | 12.0 | 0.19 | 0.40 | 0.00 | |
| | Qwen vivian | 3.91 | 12.4 | 0.25 | 0.59 | 0.00 | (two takes with 1.1 s dead air) |
| esther en | **Emma Multilingual, phrased (final)** | **5.65** | **16.4** | 0.13 | 0.28 | 0.00 | |
| | Qwen vivian | 4.06 | 12.8 | 0.25 | 0.47 | 0.03 | |
| king en | **Christopher, phrased (final)** | 4.21 | 12.8 | 0.17 | 0.61 | 0.00 | median F0 113 Hz |
| | Ryan / Qwen aiden | 7.6 / 5.1 | 21.9 / 16.4 | | | 0.00 | median F0 160 / 267 Hz: not deep |
| haman en | **Ryan, phrased (final)** | 6.79 | 20.7 | 0.08 | 0.44 | 0.02 | |
| mordecai en | **Thomas, phrased (final)** | 4.17 | 13.8 | 0.10 | 0.21 | 0.00 | |

\* Mordecai's numbers are measured after the off-stage reflections, which make the pitch tracker jump octaves; read
them as "not flat", nothing more.

What decided it:

- **Chinese female voices and the king: Qwen3-TTS.** Against the Microsoft voices it reads the line as acting, not
  as text: phrase pace varies 1.2-2.5x as much (rate CV 0.17-0.30 vs 0.12-0.17) and pause lengths vary twice as much
  (pause CV 0.61 vs 0.24-0.42), which is the "human touch" the old voices lacked, with as much or more pitch movement and
  no loss of intelligibility once the best take is kept. Raw, it is unreliable: one narrator take of es_01 ran 28.9 s
  for an 8 s line, others dragged at 2.3 characters/s or swapped a word; hence 4 takes and the gates.
- **Multilingual voices speaking Chinese were rejected** although their pitch numbers look good: whisper's confidence
  on them is much lower (log-prob -0.21 to -0.22 vs -0.11 for Xiaoyi on Esther's lines), i.e. a foreign accent.
- **Haman and Mordecai in Chinese stay with Microsoft** (Yunxi, Yunyang): their scores beat or tie Qwen's `dylan`
  and `uncle_fu` is taken by the king; Qwen's dylan dragged the "fast, squeaky panic" line to 7.7 s.
- **English: Microsoft voices, phrased.** Ava and Emma Multilingual have the widest pitch movement of all English
  candidates (F0 SD 5.0-5.7 st vs 3.7 for Sonia, the David & Goliath narrator) and zero word errors; Qwen's
  English speakers were flatter (3.1-4.1 st), slower and left dead air. The king needs a deep voice: Christopher
  (113 Hz median) over Ryan and Qwen `aiden`, which score livelier but sit at 160-267 Hz.
- **Phrasing helps the Microsoft voices, partly**: splitting lines and directing each phrase raised F0 SD in 9 of 10
  role/language groups against one call per line (Xiaoyi 2.74 -> 3.41, Yunxi 3.95 -> 5.17, Ava 4.66 -> 5.07; Emma en
  5.73 -> 5.65 the exception). It did **not** make pacing more varied: phrase-rate CV moved both ways and pause CV fell
  in 7 of 10, because the inserted gaps are similar in length. Next step if English still sounds even: vary the
  `gap` values more (0.15-0.7 s) rather than adding more phrases.

## Listen first

Measured, not heard. These are the clips most likely to disappoint:

1. **zh es_04, es_08, es_18 (Qwen)**: whisper heard 只拜 / 召见 / 以斯帖 slightly differently in some takes
   (a mispronounced polyphone would sound like this). If one is wrong, set `"seed": 4` under `lines.<id>.zh` (four
   new takes) or `"takes": 6`, and run `gen --lang zh --only <id>`.
2. **zh es_01, es_02, es_10 (narrator, 8.7-8.9 s)**: slower than the English (5.6-8.6 s). The direction asks for an
   unhurried, hushed read, and the takes kept are the fastest of four; if they drag, raise `minPace` (now 3.3).
3. **Haman (both languages)**: "nasal" is an EQ lift on an ordinary voice; edge-tts cannot whisper (es_05) or
   squeak (es_16), so those are pitch/rate approximations.
4. **Esther zh vs en**: two different engines for one character; the timbres are not the same woman.

Where zh and en differ in length, the line gets the longer one (es_08: zh 7.2 s, en 4.1 s), so English has a 3 s
silence there; the music carries it.

## Regenerate

```bash
python3 -m venv .venv-voice && .venv-voice/bin/pip install edge-tts praat-parselmouth mlx-whisper mlx-audio "misaki[zh,en]"
python3 tools/story/voice.py esther gen                 # all 36 clips + check (~45 min the first time: 14 Qwen lines x 4 takes; raw takes are cached in ~/.cache/doodlive-voice, so a re-run takes ~3 min)
python3 tools/story/voice.py esther gen --lang en --only es_05,es_07
python3 tools/story/voice.py esther check --asr         # durations, report (with transcripts + measurements), srt
python3 tools/story/build_timeline.py esther            # re-time the play from durations.json
python3 tools/story/voice.py esther check               # every clip now fits its slot
python3 tools/story/voice.py esther session             # recording sheets for people
```

`voice.py` re-runs itself under `.venv-voice` (or `.venv-tts`) when the system python lacks edge-tts. `.venv-voice/`
carries its own `.gitignore`, so git ignores it. After Story changes a line in `story.py`: `build_timeline.py esther`,
`voice.py esther gen --only <id>`, `build_timeline.py esther` again, then `session`. To change a voice, edit
`cast.<lang>.<role>` in the cast file; to direct one line, edit `lines.<id>.<lang>` (`phrases`, `rate`, `pitch`,
`instruct`, `takes`, `maxPause`, `minPace`). For another story, write `tools/story/cast_<id>.json` the same way.

## A family recording replaces a clip

1. `python3 tools/story/voice.py esther session` and open `assets/esther/audio/voice/record/<lang>/record.html`
   (voice-record skill): each line shows the text, the mood (`m`) and a picture to hold in mind (`d`).
2. Record, then run the skill's `process.py` to pick takes; it writes `<line-id>.wav` files into a folder.
3. `python3 tools/story/voice.py esther import <folder> --lang zh` (or `en`, `--only es_09`): trimmed, levelled by the
   `natural` chain (-17 LUFS, no EQ, no time-stretch, LESSONS L50) and marked `own:<folder>` in sources.json.
   `gen` never overwrites an `own` clip unless `--force`.
4. `python3 tools/story/build_timeline.py esther`: the play re-times itself to the person's pace.
