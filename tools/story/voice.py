#!/usr/bin/env python3
"""Voice lines (zh + en) for any story pack: assets/<id>/timeline.json -> assets/<id>/audio/voice/.

Usage:  python3 tools/story/voice.py <story-id> <command> [options]

  gen     [--lang zh|en|all] [--only es_02,es_05] [--force]
          Speak every line with the voice cast in tools/story/cast_<id>.json, shape it per role, level it, then run
          `check`. Lines marked "own" in sources.json (a person's recording) are kept unless --force.
  import  DIR --lang zh|en [--only ...]
          Take <line-id>.wav files recorded by people (e.g. the voice-record skill's output), trim them, level them
          with the gentle "natural" chain (LESSONS L50: no EQ, no time-stretch) and mark them "own"; then `check`.
  check   [--asr]
          Rebuild durations.json, report.json, zh.srt, en.srt; print each clip against the timeline. With --asr, also
          transcribe every clip locally (mlx-whisper) and add pitch / pause / error-rate measurements to report.json.
  session Write the voice-record session (record/<lang>/lines.json + record.html) so people can re-record lines.

Cast file (tools/story/cast_<id>.json):
  cast.<lang>.<role> = {engine: "edge"|"qwen", voice, rate, pitch, fx, chain, instruct?, why}
  lines.<line-id> = {m, m_en, d, d_en,                          direction for human recorders (session)
                     <lang>: {rate, pitch, voice, instruct,       per-line overrides of the role
                              takes, seed,                        qwen: number of takes, the best is kept
                              phrases: [{text, rate, pitch, gap}]}}  speak in phrases, joined by `gap` s of silence
  names.<role> = {zh, en}                                       role names for the recording sheet
Text goes to Microsoft's TTS endpoint for the "edge" engine: it must stay public Bible content, nothing private.
The "qwen" engine runs Qwen3-TTS locally (mlx-audio) and sends nothing anywhere.

Output contract (docs/<id>/CONTRACT.md §7): 44.1 kHz mono 16-bit WAV + 96 kbps MP3, TTS at -16 LUFS, recordings at
-17 LUFS, true peak <= -1.5 dBTP. Clips are never time-stretched: build_timeline.py fits the play to the voices.
"""
import argparse, asyncio, hashlib, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
VENVS = [os.path.join(ROOT, ".venv-voice/bin/python"), os.path.join(ROOT, ".venv-tts/bin/python3")]


def _reexec_in_venv():
    """Run under the repo's voice venv when the current python lacks edge_tts (so `python3 tools/story/voice.py` works)."""
    try:
        import edge_tts  # noqa: F401
        return
    except ImportError:
        pass
    for py in VENVS:
        if os.path.exists(py) and os.path.realpath(py) != os.path.realpath(sys.executable):
            os.execv(py, [py, os.path.abspath(__file__), *sys.argv[1:]])
    sys.exit("edge-tts not found: python3 -m venv .venv-voice && .venv-voice/bin/pip install edge-tts")


LANGS = ("zh", "en")
LUFS_TTS, LUFS_OWN, TP = -16.0, -17.0, -1.5
GAP = 0.2                     # no two lines closer than 0.2 s
SR_WORK = 24000               # working rate before the final 44.1 kHz render
SKILL_HTML = os.path.join(ROOT, "../../.claude/skills/voice-record/assets/record.html")
QWEN_MODEL = "mlx-community/Qwen3-TTS-12Hz-1.7B-CustomVoice-8bit"
WHISPER = "mlx-community/whisper-large-v3-turbo"

TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
PAD = "adelay=30:all=1,apad=pad_dur=0.06"
FX = {
    "plain":   "highpass=f=70",
    # A deep voice: a little chest, nothing else. No pitch shifting (it is what makes a voice sound processed).
    "warm":    "highpass=f=55,equalizer=f=140:t=q:w=1.0:g=2",
    # Slightly nasal (comic): lift the 1 kHz "nose" band, thin the chest. Subtle on purpose.
    "nasal":   "highpass=f=140,equalizer=f=1100:t=q:w=1.4:g=4,equalizer=f=250:t=q:w=1.0:g=-2",
    # Off-stage, in the next room: lows and highs rolled off, a few early reflections, a short soft tail.
    "offstage": "highpass=f=160,lowpass=f=5200,equalizer=f=2500:t=q:w=1.5:g=-2,"
                "aecho=0.85:0.6:17|29|43|61:0.22|0.16|0.11|0.07",
}
# Level chains. "tts" is the firm chain of David & Goliath (flat voices). "expressive" keeps the soft-knee, slow
# compressor and gentle limiter of the "natural" chain (LESSONS L50) at the TTS level, so the peaks of an expressive
# read (a shout, a gasp, a laugh) survive. "natural" is for people's recordings.
CHAIN = {
    "tts":        dict(comp="acompressor=threshold=-24dB:ratio=3:attack=5:release=80", la=3, lr=40, lufs=LUFS_TTS),
    "expressive": dict(comp="acompressor=threshold=-30dB:ratio=1.8:knee=8:attack=25:release=250", la=8, lr=200, lufs=LUFS_TTS),
    "natural":    dict(comp="acompressor=threshold=-30dB:ratio=1.8:knee=8:attack=25:release=250", la=8, lr=200, lufs=LUFS_OWN),
}


class Story:
    def __init__(self, sid):
        self.id = sid
        self.timeline = os.path.join(ROOT, "assets", sid, "timeline.json")
        self.cast_path = os.path.join(ROOT, "tools", "story", f"cast_{sid}.json")
        self.out = os.path.join(ROOT, "assets", sid, "audio", "voice")
        self.sources_path = os.path.join(self.out, "sources.json")
        self.tl = json.load(open(self.timeline, encoding="utf-8"))
        self.cast = json.load(open(self.cast_path, encoding="utf-8")) if os.path.exists(self.cast_path) else {}
        self.src = (json.load(open(self.sources_path, encoding="utf-8")) if os.path.exists(self.sources_path)
                    else {l: {} for l in LANGS})

    def save_sources(self):
        os.makedirs(self.out, exist_ok=True)
        json.dump(self.src, open(self.sources_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)

    def wav(self, lang, lid):
        return os.path.join(self.out, lang, f"{lid}.wav")


# ---------------------------------------------------------------------------------------------------- audio helpers
def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def ffmpeg(*args):
    return run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args])


def duration(f):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).stdout)


def loudness(f):
    """Integrated LUFS and true peak (dBTP) by ebur128."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    s = err[err.rfind("Summary:"):]
    return (float(re.search(r"I:\s+([-\d.]+) LUFS", s).group(1)),
            float(re.search(r"Peak:\s+([-\d.inf]+) dBFS", s).group(1)))


def normalise(src, wav, mp3, chain):
    """Compressor, gain to the chain's LUFS, true-peak-safe limiter, 44.1 kHz mono s16 WAV, then a 96 kbps MP3."""
    c = CHAIN[chain]
    tmp = wav + ".pre.wav"
    ffmpeg("-i", src, "-af", f"{c['comp']},aresample=44100", "-ac", "1", "-c:a", "pcm_f32le", tmp)
    gain = c["lufs"] - loudness(tmp)[0]
    for _ in range(4):                           # the limiter eats a little loudness: re-aim until within 0.3 LU
        ffmpeg("-i", tmp, "-af", f"volume={gain:.2f}dB,alimiter=limit={10 ** ((TP - 0.6) / 20):.3f}"
               f":attack={c['la']}:release={c['lr']}:level=disabled", "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", wav)
        lu, pk = loudness(wav)
        if abs(c["lufs"] - lu) <= 0.3 and pk <= TP:
            break
        gain += c["lufs"] - lu
        if pk > TP:
            gain -= pk - TP + 0.1
    os.remove(tmp)
    ffmpeg("-i", wav, "-ac", "1", "-b:a", "96k", mp3)


def join(parts, gaps, out):
    """Concatenate trimmed phrase WAVs with exact silences between them (sample-accurate, 6 ms fades, no clicks)."""
    args, chains, labels = [], [], []
    for k, p in enumerate(parts):
        args += ["-i", p]
        chains.append(f"[{k}:a]aresample={SR_WORK},aformat=sample_fmts=fltp:channel_layouts=mono,{TRIM},"
                      f"afade=t=in:d=0.006,areverse,afade=t=in:d=0.006,areverse[p{k}]")
        labels.append(f"[p{k}]")
        if k < len(parts) - 1 and gaps[k] > 0:
            chains.append(f"anullsrc=r={SR_WORK}:cl=mono,atrim=duration={gaps[k]:.3f}[s{k}]")
            labels.append(f"[s{k}]")
    graph = ";".join(chains) + f";{''.join(labels)}concat=n={len(labels)}:v=0:a=1[out]"
    ffmpeg(*args, "-filter_complex", graph, "-map", "[out]", "-ac", "1", "-ar", str(SR_WORK), out)


# ---------------------------------------------------------------------------------------------------------- engines
async def _edge(text, voice, rate, pitch, out):
    import edge_tts
    await edge_tts.Communicate(text, voice, rate=rate, pitch=pitch).save(out)


def tts_edge(text, voice, rate, pitch, out):
    err = "?"
    for _ in range(4):
        try:
            asyncio.run(_edge(text, voice, rate, pitch, out))
            if os.path.getsize(out) > 1000:
                return
            err = "empty media"
        except Exception as e:                        # the service sometimes returns no audio: try again
            err = str(e)
    sys.exit(f"edge-tts failed for {voice}: {text!r}: {err}")


_QWEN = None


def tts_qwen(text, voice, instruct, lang, out, seed=None):
    global _QWEN
    import numpy as np, soundfile as sf, mlx.core as mx
    if _QWEN is None:
        from mlx_audio.tts.utils import load_model
        _QWEN = load_model(QWEN_MODEL)
    if seed is not None:
        mx.random.seed(int(seed))
    res = list(_QWEN.generate(text=text, voice=voice, instruct=instruct or None,
                              lang_code={"zh": "chinese", "en": "english"}[lang], verbose=False))
    sf.write(out, np.concatenate([np.array(r.audio) for r in res]), _QWEN.sample_rate)


TAKE_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "doodlive-voice")


def speak(text, role, ov, lang, out, seed=None):
    engine = ov.get("engine", role.get("engine", "edge"))
    voice = ov.get("voice", role["voice"])
    if engine == "qwen":
        instruct = " ".join(x for x in (role.get("instruct", ""), ov.get("instruct", "")) if x)
        # Local takes are slow (~30 s each): keep every raw take, keyed by everything that shapes it, so a re-run
        # with a different selection rule or fx costs nothing. The cache lives outside the repo.
        key = hashlib.sha1(json.dumps([QWEN_MODEL, voice, instruct, lang, text, seed]).encode()).hexdigest()[:16]
        cached = os.path.join(TAKE_CACHE, f"qwen_{key}.wav")
        if not os.path.exists(cached):
            os.makedirs(TAKE_CACHE, exist_ok=True)
            tts_qwen(text, voice, instruct, lang, cached + ".tmp.wav", seed)
            os.replace(cached + ".tmp.wav", cached)
        shutil.copyfile(cached, out)
    else:
        tts_edge(text, voice, ov.get("rate", role.get("rate", "+0%")), ov.get("pitch", role.get("pitch", "+0Hz")), out)
    return f"{engine}:{voice}"


# ------------------------------------------------------------------------------------------------ measurement (opt)
def analysis_available():
    try:
        import parselmouth, mlx_whisper, numpy  # noqa: F401
        return True
    except ImportError:
        return False


def transcribe(wav, lang):
    import mlx_whisper
    r = mlx_whisper.transcribe(wav, path_or_hf_repo=WHISPER, language=lang, word_timestamps=True,
                               condition_on_previous_text=False, verbose=None)
    return r["text"].strip(), [[w["word"], w["start"], w["end"]] for s in r["segments"] for w in s.get("words", [])]


def _units(word, lang):
    if lang == "zh":
        return len(re.findall(r"[\u4e00-\u9fff]", word))
    w = re.sub(r"[^a-z]", "", word.lower())
    n = len(re.findall(r"[aeiouy]+", w))
    if w.endswith("e") and not w.endswith(("le", "ee")) and n > 1:
        n -= 1
    return max(1, n) if w else 0


def _edit(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (x != y))
    return d[len(b)]


def error_rate(ref, hyp, lang):
    """Character error rate (zh, Han characters only) or word error rate (en)."""
    pat, f = (r"[\u4e00-\u9fff]", str) if lang == "zh" else (r"[a-z']+", str.lower)
    r, h = re.findall(pat, f(ref)), re.findall(pat, f(hyp))
    return _edit(r, h) / max(1, len(r))


def measure(wav, text, lang):
    """Pitch liveliness, pauses, per-phrase speech rate and intelligibility of one clip."""
    import numpy as np, parselmouth
    hyp, words = transcribe(wav, lang)
    snd = parselmouth.Sound(wav)
    f0 = snd.to_pitch_ac(time_step=0.01, pitch_floor=65, pitch_ceiling=600).selected_array["frequency"]
    f0 = f0[f0 > 0]
    st = 12 * np.log2(f0 / np.median(f0)) if len(f0) else np.zeros(1)
    it = snd.to_intensity(time_step=0.01)
    iv, ix = it.values[0], it.xs()
    idx = np.where(iv > iv.max() - 25)[0]
    pauses, segs = [], []
    if len(idx):
        start = prev = idx[0]
        for k in idx[1:]:
            if k - prev > 12:                                  # silence > 120 ms inside the line
                pauses.append(round((k - prev) * 0.01, 2)); segs.append((ix[start], ix[prev])); start = k
            prev = k
        segs.append((ix[start], ix[prev]))
    rates = []
    for a, b in segs:
        n = sum(_units(w, lang) for w, s, e in words if a - 0.05 <= (s + e) / 2 <= b + 0.05)
        if b - a > 0.4 and n >= 3:
            rates.append(round(n / (b - a), 2))
    return {"asr": hyp, "errorRate": round(error_rate(text, hyp, lang), 3), "f0MedianHz": round(float(np.median(f0)), 1) if len(f0) else 0,
            "f0SdSemitones": round(float(np.std(st)), 2), "f0RangeSemitones": round(float(np.percentile(st, 95) - np.percentile(st, 5)), 2),
            "pausesSec": pauses, "phraseRates": rates, "sec": round(snd.duration, 2),
            "speechSec": round(float(sum(b - a for a, b in segs)), 2),
            "pace": round(sum(_units(w, lang) for w in (list(text) if lang == "zh" else text.split())) / snd.duration, 2)}


def take_score(m, max_pause=1.0, min_pace=3.0):
    """Higher is better. Gates first (a local model sometimes drifts: wrong words, dead air, a runaway tail), then
    lively pitch and varied pacing."""
    import numpy as np
    r = m["phraseRates"]
    cv = float(np.std(r) / np.mean(r)) if len(r) > 1 else 0.0
    gate = 0.0                                          # wrong words are handled before scoring (render_line)
    gate -= 5 * max(0.0, max(m["pausesSec"] or [0]) - max_pause)
    gate -= 10 * max(0.0, 0.7 - m["speechSec"] / max(0.01, m["sec"]))
    gate -= 3 * max(0.0, min_pace - m["pace"])         # storytelling slow is fine; dragging is not
    # F0 SD capped at 6 st: above that it is mostly pitch-tracker octave jumps on creaky or breathy frames
    return gate + min(m["f0SdSemitones"], 6.0) + 0.3 * min(m["f0RangeSemitones"], 20.0) / 4 + 2 * cv


# --------------------------------------------------------------------------------------------------------- commands
def render_line(st, line, lang, tmp):
    """Speak one line (whole or in phrases, best of N takes), apply the role's fx; returns (pre-level wav, note)."""
    cast = st.cast
    role = cast["cast"][lang][line.get("voice") or line["who"]]
    ov = cast.get("lines", {}).get(line["id"], {}).get(lang, {})
    phrases = ov.get("phrases") or [{"text": line[lang]}]
    bare = lambda s: re.sub(r"[\W_]+", "", s).lower()
    if bare("".join(p["text"] for p in phrases)) != bare(line[lang]):   # phrases may re-punctuate, never re-word
        sys.exit(f"{line['id']} {lang}: phrases do not spell the line's words ({line[lang]!r}); fix the cast file")
    takes = int(ov.get("takes", role.get("takes", 1)))
    direction = cast.get("lines", {}).get(line["id"], {}).get("m" if lang == "zh" else "m_en") or line.get("dir", "")
    ov = {"instruct": direction, **ov}
    base = os.path.join(tmp, f"{lang}_{line['id']}")
    note, cands = "", []
    for k in range(takes):
        parts, gaps = [], []
        for j, ph in enumerate(phrases):
            pov = {**ov, **{x: ph[x] for x in ("rate", "pitch", "instruct", "voice") if x in ph}}
            raw = f"{base}_t{k}_p{j}." + ("wav" if pov.get("engine", role.get("engine")) == "qwen" else "mp3")
            note = speak(ph["text"], role, pov, lang, raw, seed=(ov.get("seed", 0) + k) if takes > 1 else ov.get("seed"))
            parts.append(raw); gaps.append(float(ph.get("gap", 0.0)))
        joined = f"{base}_t{k}.wav"
        join(parts, gaps, joined)
        shaped = f"{base}_t{k}_fx.wav"
        ffmpeg("-i", joined, "-af", f"{TRIM},{FX[role.get('fx', 'plain')]},{PAD}", "-ac", "1", shaped)
        if takes == 1:
            return shaped, note
        m = measure(shaped, line[lang], lang)
        s = take_score(m, float(ov.get("maxPause", role.get("maxPause", 1.0))),
                       float(ov.get("minPace", role.get("minPace", 3.0 if lang == "zh" else 2.8))))
        print(f"   take {k}: score {s:5.2f}  err {m['errorRate']:.2f}  f0sd {m['f0SdSemitones']:.2f}  "
              f"pace {m['pace']:.2f}/s  {m['sec']:.1f}s  {m['asr']}")
        cands.append((m["errorRate"], s, k, shaped))
    # The words come first: only takes whose transcript is as good as the best one (+0.04, whisper's own noise on
    # names such as 以斯帖) compete; among those the highest score wins.
    floor = min(c[0] for c in cands) + 0.04
    err, s, k, best = max((c for c in cands if c[0] <= floor), key=lambda c: c[1])
    print(f"   -> take {k}")
    return best, note + f" (take {k} of {takes})"


def cmd_gen(st, a):
    langs = LANGS if a.lang == "all" else (a.lang,)
    only = set(a.only.split(",")) if a.only else None
    with tempfile.TemporaryDirectory() as tmp:
        for lang in langs:
            os.makedirs(os.path.join(st.out, lang), exist_ok=True)
            for line in st.tl["lines"]:
                lid = line["id"]
                if only and lid not in only:
                    continue
                if st.src.get(lang, {}).get(lid, "").startswith("own") and not a.force:
                    print(f"{lang} {lid}: own recording kept (use --force to replace it with TTS)")
                    continue
                role = st.cast["cast"][lang][line.get("voice") or line["who"]]
                pre, note = render_line(st, line, lang, tmp)
                normalise(pre, st.wav(lang, lid), st.wav(lang, lid)[:-4] + ".mp3", role.get("chain", "expressive"))
                st.src.setdefault(lang, {})[lid] = note
                st.save_sources()
                print(f"{lang} {lid} {line['who']:9s} {duration(st.wav(lang, lid)):5.2f}s  {note}", flush=True)
    return cmd_check(st, a)


def cmd_import(st, a):
    only = set(a.only.split(",")) if a.only else None
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for line in st.tl["lines"]:
            lid = line["id"]
            f = os.path.join(a.dir, f"{lid}.wav")
            if (only and lid not in only) or not os.path.exists(f):
                continue
            pre = os.path.join(tmp, f"{lid}.wav")          # trim again: a take may carry room tone at the ends
            ffmpeg("-i", f, "-af", f"{TRIM},{PAD}", "-ac", "1", pre)
            os.makedirs(os.path.join(st.out, a.lang), exist_ok=True)
            normalise(pre, st.wav(a.lang, lid), st.wav(a.lang, lid)[:-4] + ".mp3", "natural")
            st.src.setdefault(a.lang, {})[lid] = f"own:{os.path.basename(os.path.abspath(a.dir))}"
            n += 1
            print(f"{a.lang} {lid}: imported {f}")
    print(f"{n} clip(s) imported; run `python3 tools/story/build_timeline.py {st.id}` so the play fits them")
    st.save_sources()
    return cmd_check(st, a)


def stamp(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cmd_check(st, a=None):
    asr = bool(getattr(a, "asr", False))
    if asr and not analysis_available():
        print("--asr needs parselmouth + mlx-whisper (.venv-voice); skipping measurements")
        asr = False
    tl = st.tl
    lines = sorted(tl["lines"], key=lambda l: l["t"])
    durs, report, bad = {l: {} for l in LANGS}, {l: {} for l in LANGS}, []
    old = {}
    rp = os.path.join(st.out, "report.json")
    if os.path.exists(rp):
        old = json.load(open(rp, encoding="utf-8"))
    print(f"\n{'id':6s} {'who':9s} {'t':>6s} {'max':>5s} | " + " | ".join(f"{l} dur  slack  gap   LUFS  peak" for l in LANGS))
    for i, line in enumerate(lines):
        nxt = lines[i + 1]["t"] if i + 1 < len(lines) else tl["duration"]
        row = []
        for lang in LANGS:
            wav = st.wav(lang, line["id"])
            if not os.path.exists(wav):
                row.append(f"{lang} MISSING".ljust(34)); bad.append((line["id"], lang, "missing", 0)); continue
            d = round(duration(wav), 2)
            lu, pk = loudness(wav)
            slack = round(line["maxSec"] - d, 2)
            gap = round(nxt - (line["t"] + d), 2)
            durs[lang][line["id"]] = d
            rec = {"sec": d, "maxSec": line["maxSec"], "slackSec": slack, "gapToNextSec": gap, "lufs": lu,
                   "truePeakDbtp": pk, "source": st.src.get(lang, {}).get(line["id"], "?")}
            prev = old.get(lang, {}).get(line["id"], {})
            if asr:
                rec["measure"] = measure(wav, line[lang], lang)
            elif prev.get("measure") and prev.get("sec") == d:
                rec["measure"] = prev["measure"]                 # keep measurements of an unchanged clip
            report[lang][line["id"]] = rec
            flag = ""
            if slack < 0:
                flag += "!MAX"; bad.append((line["id"], lang, "maxSec", -slack))
            if gap < GAP:
                flag += "!GAP"; bad.append((line["id"], lang, "next line", round(GAP - gap, 2)))
            if pk > TP:
                flag += "!TP"; bad.append((line["id"], lang, "true peak", round(pk - TP, 2)))
            row.append(f"{d:5.2f} {slack:+5.2f} {gap:+5.2f} {lu:6.1f} {pk:5.1f}{flag:7s}")
        print(f"{line['id']:6s} {line['who']:9s} {line['t']:6.1f} {line['maxSec']:5.1f} | " + " | ".join(row))
    json.dump(durs, open(os.path.join(st.out, "durations.json"), "w"), indent=1)
    json.dump(report, open(rp, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    for lang in LANGS:
        out = []
        for i, line in enumerate(lines):
            if line["id"] not in durs[lang]:
                continue
            nxt = lines[i + 1]["t"] if i + 1 < len(lines) else tl["duration"]
            t1 = min(max(line["t"] + durs[lang][line["id"]], line["t"] + 1.0), nxt - 0.05)
            out.append(f"{len(out) + 1}\n{stamp(line['t'])} --> {stamp(t1)}\n{line[lang]}\n")
        open(os.path.join(st.out, f"{lang}.srt"), "w", encoding="utf-8").write("\n".join(out))
    if tl.get("timedFrom", "voices") != "voices":
        print(f"\ntimeline.json is timed from an {tl['timedFrom']}: run `python3 tools/story/build_timeline.py {st.id}`")
    if bad:
        print("\nPROBLEMS (re-time with build_timeline.py, or re-record; never trim or stretch the audio):")
        for lid, lang, what, by in bad:
            print(f"  {lid} {lang}: {what} by {by:.2f}" + ("s" if what != "true peak" else " dB"))
        return 1
    print(f"\nall clips fit maxSec and leave >= {GAP:.1f}s before the next line")
    return 0


def cmd_session(st, a):
    names = st.cast.get("names", {})
    for lang in LANGS:
        d = os.path.join(st.out, "record", lang)
        os.makedirs(d, exist_ok=True)
        rows = []
        for line in st.tl["lines"]:
            c = st.cast.get("lines", {}).get(line["id"], {})
            who = names.get(line["who"], {}).get(lang, line["who"].capitalize())
            if lang == "zh":
                m = f"{who}｜{c.get('m', line.get('dir', ''))}｜不超过 {line['maxSec']:.1f} 秒"
                dd = c.get("d", "")
                ref = line["ref"].replace("Esther ", "以斯帖记 ")
                rows.append({"id": line["id"], "t": line[lang], "m": m, "d": f"{dd}（{ref}）"})
            else:
                m = f"{who} | {c.get('m_en', line.get('dir', ''))} | at most {line['maxSec']:.1f} s"
                rows.append({"id": line["id"], "t": line[lang], "m": m, "d": f"{c.get('d_en', '')} ({line['ref']})"})
        json.dump(rows, open(os.path.join(d, "lines.json"), "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        if os.path.exists(SKILL_HTML):
            shutil.copyfile(SKILL_HTML, os.path.join(d, "record.html"))
        print(f"wrote {os.path.relpath(d, ROOT)}/lines.json ({len(rows)} lines)"
              + ("" if os.path.exists(os.path.join(d, "record.html")) else "  [record.html missing: copy it from the voice-record skill]"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen"); g.add_argument("--lang", default="all", choices=("zh", "en", "all"))
    g.add_argument("--only"); g.add_argument("--force", action="store_true"); g.add_argument("--asr", action="store_true")
    i = sub.add_parser("import"); i.add_argument("dir"); i.add_argument("--lang", required=True, choices=LANGS)
    i.add_argument("--only"); i.add_argument("--asr", action="store_true")
    c = sub.add_parser("check"); c.add_argument("--asr", action="store_true")
    sub.add_parser("session")
    a = ap.parse_args()
    if a.cmd == "gen" or getattr(a, "asr", False):
        _reexec_in_venv()
    st = Story(a.story)
    sys.exit({"gen": cmd_gen, "import": cmd_import, "check": cmd_check, "session": cmd_session}[a.cmd](st, a))


if __name__ == "__main__":
    main()
