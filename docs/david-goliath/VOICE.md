# David & Goliath: voice (zh + en)

All 18 lines in `assets/david-goliath/timeline.json` are recorded in Chinese and English. The voices are Microsoft
neural voices called through edge-tts, then shaped per role with ffmpeg. Every clip can later be replaced by a
person's own recording (a parent or a child) without touching any code. The contract is CONTRACT.md §7.

## Files

```
tools/make_dg_voice.sh            entry point (picks the .venv-tts python, checks ffmpeg has rubberband)
tools/dg_voice_build.py           gen / import / check / session
tools/dg_voice_cast.json          cast per language + role, per-line mood and picture, per-line prosody overrides
assets/david-goliath/audio/voice/
  zh/<id>.wav  en/<id>.wav        44.1 kHz mono 16-bit PCM, -16 LUFS, true peak <= -1.5 dBTP   (Unity)
  zh/<id>.mp3  en/<id>.mp3        96 kbps mono copies                                           (web)
  durations.json                  {"zh": {"dg_01": 4.53, ...}, "en": {...}}  seconds, from the WAVs
  zh.srt  en.srt                  one cue per line: starts at line.t, ends when the clip ends (min 1.0 s,
                                  max = next line's t - 0.05 s)
  report.json                     per clip: sec, maxSec, slack, gap to next line, LUFS, peak, source
  sources.json                    per clip: "tts:<voice>" or "own:<folder>"; `gen` never overwrites "own"
  record/zh/  record/en/          voice-record session: lines.json + record.html
```

## Cast

| Role | zh voice | en voice | Processing (`fx`) | Direction (STORY.md) |
|---|---|---|---|---|
| Narrator | zh-CN-XiaoxiaoNeural, rate −4 % | en-GB-SoniaNeural, rate −4 % (same as the web battle narrator) | `plain`: 70 Hz high-pass | warm storyteller; dg_18 lifted +4 Hz for a bright ending |
| David | zh-CN-YunxiaNeural (boy, "cartoon / cute") | en-US-AnaNeural, pitch −6 Hz so it reads as a boy | `bright`: 90 Hz high-pass, +2 dB at 4 kHz | clear, light, brave, never shouting |
| Goliath | zh-CN-YunjianNeural, rate −4 %, pitch −4 Hz | en-US-ChristopherNeural, rate −2 %, pitch −6 Hz | `giant`: rubberband pitch ×0.84 (≈ −3 semitones, tempo kept), +3 dB at 120 Hz, two-tap 40/75 ms hall | big, booming, cartoon-scary, not nightmare-scary |
| Saul (off-screen) | zh-CN-YunyangNeural, rate −6 %, pitch −6 Hz | en-GB-ThomasNeural, rate −6 %, pitch −6 Hz | `offscreen`: 120 Hz–7.5 kHz band, small room | older king, kind but worried |
| Soldiers (off-screen) | YunxiNeural + zh-TW-YunJheNeural + YunyangNeural (+10 Hz), staggered 0 / 50 / 90 ms | GuyNeural + en-GB-RyanNeural + BrianNeural (+8 Hz), staggered 0 / 50 / 80 ms | `crowd`: 3 voices mixed (gains 1 / 0.7 / 0.55), band-limited, short room, decayed tail cut at −50 dB | nervous, overlapping, quick (rates +14 … +22 %) |

No voice is reused for two roles inside one language except Yunyang, which plays Saul and is pitched up and buried
third in the soldiers' mix.

Every clip goes through the same tail: trim silence at both ends (−45 dB), 30 ms lead-in and 60 ms tail pad,
compressor (−24 dB, 3:1), gain to −16 LUFS, peak limiter at −2.1 dBFS, then re-aim the gain until within 0.3 LU.
(Two-pass linear `loudnorm` was tried first: it never limits, so short peaky clips came out 2–10 dB quiet, Saul zh at
−26 LUFS.)

## Timing (verified 2026-10-27)

`tools/make_dg_voice.sh check` prints this table and exits 1 if any clip is longer than `maxSec` or ends less than
0.2 s before the next line starts. Current result: all 36 clips fit.

| id | maxSec | zh s | en s | smallest gap to next line, s |
|---|---|---|---|---|
| dg_01 | 5.2 | 4.53 | 3.52 | 3.37 |
| dg_02 | 4.0 | 3.82 | 3.71 | 0.38 |
| dg_03 | 4.4 | 3.98 | 3.24 | 3.02 |
| dg_04 | 2.6 | 2.53 | 2.52 | 0.27 |
| dg_05 | 3.0 | 2.79 | 2.87 | 1.33 |
| dg_06 | 5.0 | 4.39 | 4.35 | 0.81 |
| dg_07 | 2.8 | 2.39 | 2.72 | 0.48 |
| dg_08 | 3.4 | 2.23 | 2.93 | 0.67 |
| dg_09 | 4.3 | 3.70 | 3.69 | 0.80 |
| dg_10 | 3.9 | 2.64 | 3.78 | 0.52 |
| dg_11 | 3.3 | 2.44 | 3.29 | 0.91 |
| dg_12 | 4.0 | 3.57 | 3.29 | 3.63 |
| dg_13 | 3.2 | 2.77 | 2.14 | 0.63 |
| dg_14 | 6.0 | 3.35 | 4.73 | 1.67 |
| dg_15 | 3.0 | 2.57 | 2.54 | 5.43 |
| dg_16 | 3.9 | 2.83 | 3.63 | 1.17 |
| dg_17 | 2.6 | 2.13 | 2.00 | 0.77 |
| dg_18 | 4.3 | 3.62 | 3.10 | 1.08 |

Tight spots: dg_04 (0.07–0.08 s under maxSec, after speeding the soldiers up), en dg_07 (rate +8 % override,
0.08 s under), en dg_11 (0.01 s under). If Story lengthens any of these lines, re-run and read the table.

Intelligibility was checked by transcribing all 36 clips locally with mlx-whisper (large-v3-turbo): every line came
back with the right words, including the pitched Goliath and the three-voice soldiers. Whisper heard zh dg_16 「巨人」
as 「居然」 and 「机弦」 as 「姬弦」; both are homophone guesses, but listen to dg_16 zh once.

## Regenerate

```bash
python3 -m venv .venv-tts && .venv-tts/bin/pip install edge-tts   # once; needs ffmpeg with rubberband (Homebrew has it)
tools/make_dg_voice.sh                                 # session files + every line in both languages + check  (~2 min)
tools/make_dg_voice.sh gen --lang zh --only dg_02,dg_05
tools/make_dg_voice.sh check                           # durations.json, report.json, srt, overrun table
```

After Story edits a line in `timeline.json`, run `gen --only <id>` for that line and then `session` so the recording
sheet shows the new text. To change a voice, edit `tools/dg_voice_cast.json` (`cast.<lang>.<role>`); for one line only,
add `"prosody": {"en": {"rate": "+8%"}}` under `lines.<id>`. Voices: `.venv-tts/bin/python3 -m edge_tts --list-voices`.

The text goes to Microsoft's TTS endpoint. It must stay public Bible content: no names of real children, no
addresses, nothing private.

The venv's own `bin/edge-tts` launcher still points at the repo's old absolute path (before the 2026-10-25 workspace
move) and fails with "bad interpreter". `make_dg_voice.sh` calls `python3 -m edge_tts` instead, which works. The older
`tools/make_voice.sh` and `tools/make_voice_angel.sh` still call the broken launcher (and quote `$TTS`, so a
`python3 -m edge_tts` override does not work there); recreating `.venv-tts` fixes them.

## Replace a clip with your own voice

Uses the workspace `voice-record` skill (`.claude/skills/voice-record/`). Everything stays on the Mac.

1. Serve the session folder and open it in Chrome or Safari on the Mac (not in Claude's built-in browser, which has
   no microphone):
   ```bash
   cd assets/david-goliath/audio/voice/record/zh     # or record/en
   python3 -m http.server 8080                        # then open http://localhost:8080/record.html
   ```
   Each card shows the line, who says it, the mood, the time limit (「不超过 2.6 秒」) and a picture to hold in mind.
   Record 2–3 takes per line you want to replace; the page downloads `voice-raw.zip` with `<id>_<take>.wav`.
2. Pick and clean the takes with the skill's script (it chooses the loudest unclipped take unless `--pick`):
   ```bash
   unzip voice-raw.zip -d ~/dg-raw
   python3 ../../.claude/skills/voice-record/scripts/process.py ~/dg-raw --out ~/dg-clean   # path from the repo root
   ```
3. Bring them in. This trims, re-levels to −16 LUFS / 44.1 kHz mono, writes WAV + MP3, marks the clips `own` in
   `sources.json`, and rebuilds durations, subtitles and the overrun table:
   ```bash
   tools/make_dg_voice.sh import ~/dg-clean --lang zh            # all <id>.wav found there
   tools/make_dg_voice.sh import ~/dg-clean --lang zh --only dg_07,dg_14
   ```
   If `check` reports an overrun, record that line again a little quicker; do not cut the audio.
4. `gen` skips clips marked `own`. To go back to the TTS clip: `tools/make_dg_voice.sh gen --lang zh --only dg_07 --force`.

Kids' voices for David are a good fit (David is a boy of about 12–14). Goliath works best as an adult voice; the
`giant` chain is applied only to TTS, so a home-recorded Goliath stays natural unless you ask for it to be pitched.

## For Integration

- Clip path: `audio/voice/<lang>/<line id>.wav`; play at `line.t`. Subtitle text is `line.zh` / `line.en`; the
  `.srt` files carry the same timing if a ready-made cue list is easier.
- `durations.json` is the clip length to hold the speaker in `talk` (jaw flap) and to time the subtitle.
- Clips start with 30 ms of silence and end with about 60 ms; no fade is needed.
