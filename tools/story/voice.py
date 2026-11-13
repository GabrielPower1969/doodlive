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
  engine "qwen_design": role `design` = who speaks (Qwen3-TTS VoiceDesign); engine "crowd": role `members` layered
  in a hall. Per line also: asrIgnore, acting {kind: laugh|tantrum|wail}, phrases[].instruct / gainDb, pick, tail.
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
QWEN_DESIGN = "mlx-community/Qwen3-TTS-12Hz-1.7B-VoiceDesign-8bit"   # voice from a description (engine qwen_design)
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
    # Across an open field (Ruth's reapers): no room, just distance: thin lows, softened highs.
    "field":   "highpass=f=150,lowpass=f=6000,equalizer=f=3000:t=q:w=1.2:g=-2",
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


_QWEN = {}


def tts_qwen(text, voice, instruct, lang, out, seed=None, model=QWEN_MODEL):
    """CustomVoice (voice = speaker, instruct = acting note) or VoiceDesign (voice None, instruct = the voice
    description followed by the acting note)."""
    import numpy as np, soundfile as sf, mlx.core as mx
    if model not in _QWEN:
        from mlx_audio.tts.utils import load_model
        _QWEN[model] = load_model(model)
    m = _QWEN[model]
    if seed is not None:
        mx.random.seed(int(seed))
    kw = {"voice": voice} if voice else {}
    res = list(m.generate(text=text, instruct=instruct or None, lang_code={"zh": "chinese", "en": "english"}[lang],
                          verbose=False, **kw))
    sf.write(out, np.concatenate([np.array(r.audio) for r in res]), m.sample_rate)


def _extras():
    """tools/story/voice_extras.py (breaths, VoiceDesign pitch pinning), or None. Inert for casts that do not use it."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        import voice_extras
        return voice_extras
    except ImportError:
        return None


TAKE_CACHE = os.path.join(os.path.expanduser("~"), ".cache", "doodlive-voice")


def speak(text, role, ov, lang, out, seed=None):
    engine = ov.get("engine", role.get("engine", "edge"))
    voice = ov.get("voice", role.get("voice", ""))
    if engine in ("qwen", "qwen_design"):
        design = engine == "qwen_design"
        # VoiceDesign: the role's `design` (who is speaking: the same words in every line and both languages, so it
        # stays one voice) comes first, then the role's instruct and the line's acting note.
        instruct = " ".join(x for x in ((ov.get("design", role.get("design", "")) if design else ""),
                                        role.get("instruct", ""), ov.get("instruct", "")) if x)
        model = QWEN_DESIGN if design else QWEN_MODEL
        # Local takes are slow (~30 s each): keep every raw take, keyed by everything that shapes it, so a re-run
        # with a different selection rule or fx costs nothing. The cache lives outside the repo.
        key = hashlib.sha1(json.dumps([model, None if design else voice, instruct, lang, text, seed]).encode()).hexdigest()[:16]
        cached = os.path.join(TAKE_CACHE, f"qwen_{key}.wav")
        if not os.path.exists(cached):
            os.makedirs(TAKE_CACHE, exist_ok=True)
            tts_qwen(text, None if design else voice, instruct, lang, cached + ".tmp.wav", seed, model)
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
                               condition_on_previous_text=False, verbose=None,
                               initial_prompt="以下是普通话的句子。" if lang == "zh" else None)   # simplified, not traditional
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


def error_rate(ref, hyp, lang, ignore=None):
    """Character error rate (zh, Han characters only) or word error rate (en). `ignore` (a regex) drops non-verbal
    tokens from both sides (a laugh, a wail, a "hmph": whisper writes a real laugh as anything or nothing)."""
    pat, f = (r"[\u4e00-\u9fff]", str) if lang == "zh" else (r"[a-z']+", str.lower)
    r, h = re.findall(pat, f(ref)), re.findall(pat, f(hyp))
    if ignore:
        r, h = [x for x in r if not re.fullmatch(ignore, x)], [x for x in h if not re.fullmatch(ignore, x)]
    return _edit(r, h) / max(1, len(r))


def measure(wav, text, lang, ignore=None, act=None):
    """Pitch liveliness, pauses, per-phrase speech rate and intelligibility of one clip; with `act` (a line's
    acting spec, see acting()) also whether the laugh / tantrum / wail is really acted."""
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
    out = {"asr": hyp, "errorRate": round(error_rate(text, hyp, lang, ignore), 3), "f0MedianHz": round(float(np.median(f0)), 1) if len(f0) else 0,
            "f0SdSemitones": round(float(np.std(st)), 2), "f0RangeSemitones": round(float(np.percentile(st, 95) - np.percentile(st, 5)), 2),
            "pausesSec": pauses, "phraseRates": rates, "sec": round(snd.duration, 2),
            "speechSec": round(float(sum(b - a for a, b in segs)), 2),
            "pace": round(sum(_units(w, lang) for w in (list(text) if lang == "zh" else text.split())) / snd.duration, 2)}
    if act:
        out["acting"] = acting(snd, words, act, lang)
    return out


def _clip01(x):
    return max(0.0, min(1.0, float(x)))


def _anchor_time(words, anchor, lang, after=True):
    """Time just after (or before) the last occurrence of `anchor` in whisper's word timeline, or None."""
    if not anchor:
        return None
    seq = []                                       # (unit, start, end): Han characters (zh) or words (en)
    for w, a, b in words:
        u = re.findall(r"[\u4e00-\u9fff]", w) if lang == "zh" else re.findall(r"[a-z']+", w.lower())
        for i, x in enumerate(u):
            seq.append((x, a + (b - a) * i / len(u), a + (b - a) * (i + 1) / len(u)))
    target = list(anchor) if lang == "zh" else anchor.lower().split()
    hits = [i for i in range(len(seq) - len(target) + 1) if [x for x, _, _ in seq[i:i + len(target)]] == target]
    if not hits:
        return None
    i = hits[-1] if after else hits[0]
    return seq[i + len(target) - 1][2] if after else seq[i][1]


def _pulses(iv, ix, lo, hi, prominence=4.0):
    """Syllable-like loudness pulses (intensity peaks) between lo and hi seconds."""
    import numpy as np
    from scipy.signal import find_peaks
    sel = (ix >= lo) & (ix <= hi)
    v, t = iv[sel], ix[sel]
    if len(v) < 5:
        return np.array([]), np.array([])
    pk, _ = find_peaks(v, prominence=prominence, distance=8)
    pk = pk[v[pk] > iv.max() - 30]
    return t[pk], v[pk]


def acting(snd, words, spec, lang):
    """Is the comic acting there? Heuristic measures, comparable between takes and voices, not absolute truths.

    laugh   (spec: kind, after, before = anchor words around the laugh, written = "ha"s in the text) in the laugh
            region: number of bursts and their rate, irregularity (interval CV), breathiness against the speech (HNR
            difference, dB), pitch rise above the speech (semitones) and length. A read "ha ha ha ha" is the written
            number of evenly spaced syllables; a laugh runs on: more bursts, irregular, longer.
    tantrum the last three pulses (the "hmph"s) get louder (dB rise), the pitch peaks high above the median
            (shrill), and loudness swings widely.
    wail    the longest held voiced sound in the last 45 % (seconds) and its pitch above the median, the held
            sound in the first 40 % (the long "no"), and the loudness slope of the last 1.2 s (dB/s; negative = fades).
    Each gives `score` (0-5, higher = more acted) and a one-word `verdict`."""
    import numpy as np
    kind = spec["kind"]
    pitch = snd.to_pitch_ac(time_step=0.01, pitch_floor=65, pitch_ceiling=900)
    f0, fx = pitch.selected_array["frequency"], pitch.xs()
    it = snd.to_intensity(time_step=0.01)
    iv, ix = it.values[0], it.xs()
    hn = snd.to_harmonicity_cc(time_step=0.01)
    hv, hx = hn.values[0], hn.xs()
    med = float(np.median(f0[f0 > 0])) if (f0 > 0).any() else 1.0
    st = lambda hz: 12 * np.log2(hz / med)
    dur = snd.duration
    res = {"kind": kind}
    if kind == "laugh":
        a = _anchor_time(words, spec.get("after"), lang, True)
        b = _anchor_time(words, spec.get("before"), lang, False)
        a = a if a is not None else (dur * 0.6 if not spec.get("before") else dur * 0.3)
        b = b if (b is not None and b > a + 0.3) else (dur if not spec.get("before") else min(dur, a + 2.0))
        tp, vp = _pulses(iv, ix, a, b)
        n = len(tp)
        iv_ = np.diff(tp) if n > 1 else np.array([0.0])
        rate = (n - 1) / (tp[-1] - tp[0]) if n > 1 and tp[-1] > tp[0] else 0.0
        icv = float(np.std(iv_) / np.mean(iv_)) if n > 2 else 0.0
        inr = lambda xs, lo, hi: (xs >= lo) & (xs <= hi)
        hr, hs = hv[inr(hx, a, b) & (hv > -50)], hv[(~inr(hx, a, b)) & (hv > -50)]
        dhnr = float(np.mean(hr) - np.mean(hs)) if len(hr) and len(hs) else 0.0
        fr, fs = f0[inr(fx, a, b) & (f0 > 0)], f0[(~inr(fx, a, b)) & (f0 > 0)]
        rise = float(np.median(st(fr)) - np.median(st(fs))) if len(fr) and len(fs) else 0.0
        fsd = float(np.std(st(fr))) if len(fr) else 0.0
        # Calibrated on edge-tts reading "哈哈哈哈" / "Ha ha ha ha": exactly the written bursts, evenly spaced
        # (interval CV 0.11-0.12). In Chinese 哈 is a high, aspirated syllable, so breathiness and pitch rise alone
        # do not tell a laugh from a read; burst count beyond the written ones, irregularity and length do.
        written = int(spec.get("written", 4))
        score = (2 * _clip01((n - written) / 4) + 1.5 * _clip01(icv / 0.35) + 0.5 * _clip01(-dhnr / 6)
                 + 0.5 * _clip01(rise / 8) + 0.5 * _clip01((b - a - 1.2) / 1.5))
        res.update(regionSec=[round(a, 2), round(b, 2)], bursts=n, burstRate=round(rate, 2), intervalCV=round(icv, 2),
                   hnrDiffDb=round(dhnr, 1), pitchRiseSt=round(rise, 1), pitchSdSt=round(fsd, 1))
        res["verdict"] = "laugh" if (n >= written + 2 and icv >= 0.2 and score >= 3.0) else ("half" if score >= 2.0 else "read")
    elif kind == "tantrum":
        tp, vp = _pulses(iv, ix, 0, dur, prominence=5.0)
        last = vp[-3:] if len(vp) >= 3 else vp
        rise = float(last[-1] - last[0]) if len(last) > 1 else 0.0
        steps = int(sum(np.diff(last) > 0)) if len(last) > 1 else 0
        top = float(np.percentile(st(f0[f0 > 0]), 95)) if (f0 > 0).any() else 0.0
        vi = iv[iv > iv.max() - 30]
        swing = float(np.percentile(vi, 95) - np.percentile(vi, 20)) if len(vi) else 0.0
        score = 2 * _clip01((rise + 1) / 5) + 0.5 * steps + _clip01((top - 4) / 6) + _clip01((swing - 10) / 10)
        res.update(lastPulsesDb=[round(float(x), 1) for x in last], hmphRiseDb=round(rise, 1), risingSteps=steps,
                   pitchTopSt=round(top, 1), loudSwingDb=round(swing, 1))
        res["verdict"] = "tantrum" if score >= 3.0 else ("half" if score >= 2.0 else "flat")
    elif kind == "wail":
        v = f0 > 0
        runs, start = [], None                      # held voiced sounds, 60 ms gaps bridged
        gap = 0
        for k in range(len(v) + 1):
            on = k < len(v) and v[k]
            if on:
                start = k if start is None else start; gap = 0
            elif start is not None:
                gap += 1
                if gap > 6 or k == len(v):
                    e = k - gap; runs.append((fx[start], fx[min(e, len(fx) - 1)], start, e)); start, gap = None, 0
        def longest(lo, hi):
            c = [(b - a, s, e) for a, b, s, e in runs if a >= lo and b <= hi + 0.05]
            if not c:
                return 0.0, 0.0
            d, s, e = max(c)
            return float(d), float(np.median(st(f0[s:e + 1][f0[s:e + 1] > 0])))
        hold_end, hi_end = longest(dur * 0.55, dur)
        hold_start, _ = longest(0, dur * 0.4)
        vend = (ix > dur - 1.2) & (iv > iv.max() - 40)
        slope = float(np.polyfit(ix[vend], iv[vend], 1)[0]) if vend.sum() > 5 else 0.0
        score = 2 * _clip01(hold_end / 1.2) + _clip01(hi_end / 5) + _clip01(hold_start / 0.8) + _clip01(-slope / 12)
        res.update(endHoldSec=round(hold_end, 2), endHoldPitchSt=round(hi_end, 1), startHoldSec=round(hold_start, 2),
                   tailSlopeDbPerSec=round(slope, 1))
        res["verdict"] = "wail" if score >= 3.0 else ("half" if score >= 2.0 else "read")
    res["score"] = round(float(score), 2)
    return res


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
    act = m.get("acting", {}).get("score", 0.0)        # the acted laugh / tantrum / wail outweighs plain liveliness
    return gate + min(m["f0SdSemitones"], 6.0) + 0.3 * min(m["f0RangeSemitones"], 20.0) / 4 + 2 * cv + 1.5 * act


# --------------------------------------------------------------------------------------------------------- commands
def render_line(st, line, lang, tmp):
    """Speak one line (whole or in phrases, best of N takes), apply the role's fx; returns (pre-level wav, note)."""
    cast = st.cast
    role = cast["cast"][lang][line.get("voice") or line["who"]]
    ov = cast.get("lines", {}).get(line["id"], {}).get(lang, {})
    # `say`: what the engine is given when the written line would be misread (路得 -> 路德: 得 is a polyphone). Per
    # line (lines.<id>.<lang>.say) or for every line (sayMap.<lang> = {written: spoken}); the subtitle keeps the
    # written text, the transcript check compares against the spoken one.
    say = ov.get("say") or line[lang]
    for a, b in cast.get("sayMap", {}).get(lang, {}).items():
        say = say.replace(a, b)
    phrases = ov.get("phrases") or [{"text": say}]
    if say != line[lang] and ov.get("phrases"):
        for a, b in cast.get("sayMap", {}).get(lang, {}).items():
            phrases = [{**ph, "text": ph["text"].replace(a, b)} for ph in phrases]
    bare = lambda s: re.sub(r"[\W_]+", "", s).lower()
    if bare("".join(p["text"] for p in phrases)) != bare(say):   # phrases may re-punctuate, never re-word
        sys.exit(f"{line['id']} {lang}: phrases do not spell the line's words ({say!r}); fix the cast file")
    if role.get("engine") == "crowd":
        out = os.path.join(tmp, f"{lang}_{line['id']}_crowd.wav")
        render_crowd(say, role, ov, lang, out, tmp, f"{lang}_{line['id']}")
        shaped = out[:-4] + "_fx.wav"
        ffmpeg("-i", out, "-af", f"{FX[role.get('fx', 'plain')]},{PAD}", "-ac", "1", shaped)
        return shaped, f"crowd:{len(role['members'])} voices"
    takes = int(ov.get("takes", role.get("takes", 1)))
    direction = cast.get("lines", {}).get(line["id"], {}).get("m" if lang == "zh" else "m_en") or line.get("dir", "")
    ov = {"instruct": direction, **ov}
    base = os.path.join(tmp, f"{lang}_{line['id']}")
    note, cands = "", []
    for k in range(takes):
        parts, gaps = [], []
        for j, ph in enumerate(phrases):
            pov = {**ov, **{x: ph[x] for x in ("rate", "pitch", "instruct", "voice") if x in ph}}
            raw = f"{base}_t{k}_p{j}." + ("wav" if str(pov.get("engine", role.get("engine"))).startswith("qwen") else "mp3")
            note = speak(ph["text"], role, pov, lang, raw, seed=(ov.get("seed", 0) + k) if takes > 1 else ov.get("seed"))
            if ph.get("gainDb"):                      # a phrase set louder / softer than its neighbours (escalating "hmph"s)
                ffmpeg("-i", raw, "-af", f"volume={float(ph['gainDb']):.1f}dB", "-ac", "1", "-c:a", "pcm_f32le", raw[:-4] + "_g.wav")
                raw = raw[:-4] + "_g.wav"
            parts.append(raw); gaps.append(float(ph.get("gap", 0.0)))
        joined = f"{base}_t{k}.wav"
        join(parts, gaps, joined)
        shaped = f"{base}_t{k}_fx.wav"
        ffmpeg("-i", joined, "-af", f"{TRIM},{FX[role.get('fx', 'plain')]},{PAD}", "-ac", "1", shaped)
        if takes == 1:
            return shaped, note
        m = measure(shaped, say, lang, ov.get("asrIgnore"), ov.get("acting"))
        s = take_score(m, float(ov.get("maxPause", role.get("maxPause", 1.0))),
                       float(ov.get("minPace", role.get("minPace", 3.0 if lang == "zh" else 2.8))))
        if _extras():
            s += _extras().score_adjust(role, ov, m, shaped)   # e.g. keep a VoiceDesign voice inside its pitch range
        ac = m.get("acting")
        print(f"   take {k}: score {s:5.2f}  err {m['errorRate']:.2f}  f0sd {m['f0SdSemitones']:.2f}  "
              f"pace {m['pace']:.2f}/s  {m['sec']:.1f}s  " + (f"{ac['kind']} {ac['score']:.1f} {ac['verdict']}  " if ac else "")
              + m["asr"])
        cands.append((m["errorRate"], s, k, shaped))
    # The words come first: only takes whose transcript is as good as the best one (+0.04, whisper's own noise on
    # names such as 以斯帖) compete; among those the highest score wins.
    floor = min(c[0] for c in cands) + 0.04
    err, s, k, best = max((c for c in cands if c[0] <= floor), key=lambda c: c[1])
    if "pick" in ov:                                    # a person listened and chose (cast file `pick`): obey
        err, s, k, best = next(c for c in cands if c[2] == int(ov["pick"]))
    print(f"   -> take {k}" + (" (picked in the cast file)" if "pick" in ov else ""))
    return best, note + f" (take {k} of {takes})"


def render_crowd(text, role, ov, lang, out, tmp, tag):
    """Many people at once: each member (any engine) speaks the line; members are offset in time, nudged in pitch
    (+-2 semitones by resampling, which also shifts the formants: different people, not one voice copied), set at
    different levels, summed, and put in a reverberant hall (a synthetic decaying-noise impulse response)."""
    import numpy as np, soundfile as sf
    from scipy.signal import resample, fftconvolve, butter, sosfilt
    sr = SR_WORK
    rng = np.random.default_rng(int(role.get("seed", 7)))
    tracks = []
    for j, mem in enumerate(role["members"]):
        raw = os.path.join(tmp, f"{tag}_m{j}." + ("wav" if mem.get("engine", "qwen").startswith("qwen") else "mp3"))
        mrole = {"engine": mem.get("engine", "qwen"), "voice": mem.get("voice", ""), "rate": mem.get("rate", "+0%"),
                 "pitch": mem.get("pitch", "+0Hz"), "design": mem.get("design", "")}
        instruct = mem.get("instruct", role.get("instruct", ""))
        speak(text, mrole, {"instruct": instruct}, lang, raw, seed=mem.get("seed", j))
        w = os.path.join(tmp, f"{tag}_m{j}.wav.trim.wav")
        ffmpeg("-i", raw, "-af", f"{TRIM},highpass=f=90", "-ac", "1", "-ar", str(sr), "-c:a", "pcm_f32le", w)
        x, _ = sf.read(w, dtype="float32")
        semis = float(mem.get("semitones", 0.0))
        if semis:
            x = resample(x, max(1, int(round(len(x) / 2 ** (semis / 12)))))
        x = x / (np.sqrt(np.mean(x ** 2)) + 1e-9) * 10 ** (float(mem.get("gainDb", 0.0)) / 20)
        delay = float(mem.get("delay", rng.uniform(0.0, 0.18)))
        tracks.append(np.concatenate([np.zeros(int(delay * sr), dtype=np.float32), x.astype(np.float32)]))
    n = max(len(t) for t in tracks)
    mix = sum(np.pad(t, (0, n - len(t))) for t in tracks) / np.sqrt(len(tracks))
    rt60 = float(role.get("rt60", 1.1))
    L = int(sr * rt60)
    t = np.arange(L) / sr
    ir = rng.standard_normal(L) * np.exp(-6.91 * t / rt60)
    ir = sosfilt(butter(2, 3500, "low", fs=sr, output="sos"), ir)
    ir[: int(0.012 * sr)] = 0
    ir = ir / np.sqrt(np.sum(ir ** 2))
    wet = fftconvolve(mix, ir)[: n + L // 2]
    dry = np.pad(mix, (0, len(wet) - n))
    mixw = float(role.get("wet", 0.45))
    y = (1 - mixw) * dry + mixw * wet * (np.sqrt(np.mean(dry ** 2)) / (np.sqrt(np.mean(wet ** 2)) + 1e-9))
    y = y / (np.abs(y).max() + 1e-9) * 0.8
    sf.write(out, y.astype(np.float32), sr)


def apply_tail(src, out, tail):
    """Carry a voice away: over the last `fade` seconds it crossfades into a darker, roomier copy of itself
    (low-pass + a few reflections) while the level falls ~30 dB on a curve, as if dragged off into the distance.
    Applied after the take is chosen, before levelling (levelling does not undo the fade)."""
    import numpy as np, soundfile as sf
    from scipy.signal import butter, sosfilt
    x, sr = sf.read(src, dtype="float32")
    n = len(x)
    f = int(min(float(tail.get("fade", 1.5)), n / sr * 0.6) * sr)
    far = sosfilt(butter(2, int(tail.get("lowpass", 2200)), "low", fs=sr, output="sos"), x)
    for dt, g in ((0.031, 0.35), (0.057, 0.25), (0.089, 0.16)):
        k = int(dt * sr); far[k:] += g * far[:-k]
    far = far * (np.sqrt(np.mean(x ** 2)) / (np.sqrt(np.mean(far ** 2)) + 1e-9))
    ramp = np.zeros(n); ramp[n - f:] = np.linspace(0, 1, f)
    gain = np.ones(n); gain[n - f:] = 10 ** (-30 * np.linspace(0, 1, f) ** 1.6 / 20)
    y = ((1 - ramp) * x + ramp * far) * gain
    sf.write(out, y.astype(np.float32), sr)


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
                if _extras():                                    # breaths etc. (tools/story/voice_extras.py)
                    pre, more = _extras().post_take(st, line, lang, pre, tmp)
                    note += more
                lc = st.cast.get("lines", {}).get(lid, {})
                tail = lc.get(lang, {}).get("tail") or lc.get("tail")
                if tail:
                    apply_tail(pre, pre[:-4] + "_tail.wav", tail)
                    pre = pre[:-4] + "_tail.wav"
                    note += " + tail fade"
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
                lov = st.cast.get("lines", {}).get(line["id"], {}).get(lang, {})
                say = lov.get("say") or line[lang]                 # compare with what the engine was told to say
                for x, y in st.cast.get("sayMap", {}).get(lang, {}).items():
                    say = say.replace(x, y)
                rec["measure"] = measure(wav, say if not st.src.get(lang, {}).get(line["id"], "").startswith("own") else line[lang],
                                         lang, lov.get("asrIgnore"), lov.get("acting"))
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
