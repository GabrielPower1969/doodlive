#!/usr/bin/env python3
"""Exodus (pack #4) wrapper around tools/story/voice.py: the same generator, plus two cast options and a preview.

Usage:  python3 tools/story/voice_exodus.py gen [--lang zh|en|all] [--only ex_02,...] [--force]   (as voice.py gen)
        python3 tools/story/voice_exodus.py preview [--lang zh|en]
        python3 tools/story/voice.py exodus check [--asr]                                         (unchanged)

Why a wrapper: voice.py / voice_extras.py are shared with packs being built at the same time, so Exodus-only logic
lives here and is attached to voice.py at run time (voice.py itself is not edited). Other packs are unaffected.

Cast options read here (tools/story/cast_exodus.json):
  cast.<lang>.<role>.reverb = {rt60, wet, predelay, tail}
        A light hall on a voice (God): convolution with a synthetic decaying-noise impulse response (the same kind of
        IR voice.py's crowd uses), `wet` share of the level, the decay cut `tail` s after the dry voice ends, so the
        clip has no long reverb trail. Applied to the chosen take, after the take was measured dry.
  lines.<id>.<lang>.grid = {beatSec, onsetsBeats: [...]}
        A rhythmic line (Miriam's chant, ex_33): phrase k starts on beat onsetsBeats[k] of the music's pulse instead
        of after a fixed gap (the phrase's own length decides the gap; at least 0.08 s).
  cast.<lang>.<role>.mfccRef / mfccTol / mfccWeight
        Timbre pinning for a VoiceDesign role (VoiceDesign invents the voice anew on every take): a take whose timbre
        fingerprint (mean MFCC 1-12 over the speech frames) is further than mfccTol from the audition reference loses
        mfccWeight points per unit beyond it, so Moses and Pharaoh stay one person across their lines.
Preview: every clip of one language placed at its timeline time, mixed to assets/exodus/audio/voice/preview_<lang>.mp3
(voices only, no music; the Music role's mix is the full preview).
"""
import os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENV = os.path.join(ROOT, ".venv-voice/bin/python")
SID = "exodus"


def _reexec():
    try:
        import edge_tts, numpy, scipy  # noqa: F401
    except ImportError:
        if os.path.exists(VENV) and os.path.realpath(VENV) != os.path.realpath(sys.executable):
            os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])
        raise


_reexec()
sys.path.insert(0, HERE)
import voice as V  # noqa: E402

_orig_render_line, _orig_join = V.render_line, V.join
_GRID = {}


def grid_join(parts, gaps, out):
    """voice.join, but with the gaps computed so that each phrase starts on its beat (only inside a `grid` line)."""
    g = _GRID.get("spec")
    if not g or len(parts) < 2:
        return _orig_join(parts, gaps, out)
    beat, on = float(g["beatSec"]), [float(x) for x in g["onsetsBeats"]]
    if len(on) != len(parts):
        sys.exit(f"grid: {len(on)} onsets for {len(parts)} phrases")
    # Each phrase (trimmed as join trims it) is laid on a silent track at its beat. A phrase that has not finished
    # speaking by then pushes the next one later (speech never overlaps: its end is where it falls 30 dB under its
    # peak); quieter tails (a crowd's room) may run under the next phrase. No gaps between phrases are cut.
    import numpy as np, soundfile as sf
    sr = V.SR_WORK
    xs = []
    for k, p in enumerate(parts):
        t = f"{out}.p{k}.wav"
        V.ffmpeg("-i", p, "-af", f"aresample={sr},{V.TRIM},afade=t=in:d=0.006,areverse,afade=t=in:d=0.006,areverse",
                 "-ac", "1", "-ar", str(sr), "-c:a", "pcm_f32le", t)
        x, _ = sf.read(t, dtype="float32"); os.remove(t)
        h = int(0.01 * sr)
        env = np.array([np.sqrt(np.mean(x[i:i + h] ** 2)) for i in range(0, max(1, len(x) - h), h)]) + 1e-9
        loud = np.where(20 * np.log10(env / env.max()) > -30)[0]
        xs.append((x, (loud[-1] + 1) * h if len(loud) else len(x)))
    starts, t = [], 0
    for k, (x, speech) in enumerate(xs):
        s = int(max(int(round(on[k] * beat * sr)), t + int(0.08 * sr) if k else 0))
        starts.append(s); t = s + speech
    y = np.zeros(max(s + len(x) for s, (x, _) in zip(starts, xs)), dtype=np.float32)
    for s, (x, _) in zip(starts, xs):
        y[s:s + len(x)] += x
    sf.write(out, y, sr)
    _GRID.setdefault("log", []).append([round(s / sr, 2) for s in starts])
    return None


def add_reverb(src, out, spec):
    import numpy as np, soundfile as sf
    from scipy.signal import fftconvolve, butter, sosfilt
    x, sr = sf.read(src, dtype="float32")
    rt60, wet = float(spec.get("rt60", 1.4)), float(spec.get("wet", 0.2))
    rng = np.random.default_rng(int(spec.get("seed", 5)))
    L = int(sr * rt60)
    t = np.arange(L) / sr
    ir = rng.standard_normal(L) * np.exp(-6.91 * t / rt60)
    ir = sosfilt(butter(2, [250, 4000], "band", fs=sr, output="sos"), ir)   # a soft hall: no boom, no hiss
    ir[: int(float(spec.get("predelay", 0.025)) * sr)] = 0
    ir /= np.sqrt(np.sum(ir ** 2))
    n = len(x)
    keep = n + int(float(spec.get("tail", 0.35)) * sr)
    w = fftconvolve(x, ir)[:keep]
    d = np.pad(x, (0, keep - n))
    w *= np.sqrt(np.mean(d ** 2)) / (np.sqrt(np.mean(w ** 2)) + 1e-9)
    y = (1 - wet) * d + wet * w
    f = keep - n                                        # fade the trail to silence over its whole length
    y[n:] *= np.linspace(1, 0, f) ** 2
    sf.write(out, y.astype(np.float32), sr)


def render_line(st, line, lang, tmp):
    ov = st.cast.get("lines", {}).get(line["id"], {}).get(lang, {})
    _GRID.clear()
    if ov.get("grid"):
        _GRID["spec"] = ov["grid"]
    role0 = st.cast["cast"][lang][line.get("voice") or line["who"]]
    try:
        if role0.get("engine") == "crowd" and ov.get("grid") and ov.get("phrases"):
            # the crowd speaks phrase by phrase, each phrase on its beat (voice.py's crowd takes the line whole)
            parts = []
            for k, ph in enumerate(ov["phrases"]):
                f = os.path.join(tmp, f"{lang}_{line['id']}_crowd_p{k}.wav")
                V.render_crowd(ph["text"], role0, ov, lang, f, tmp, f"{lang}_{line['id']}_p{k}")
                parts.append(f)
            joined = os.path.join(tmp, f"{lang}_{line['id']}_crowd.wav")
            grid_join(parts, [0.0] * (len(parts) - 1), joined)
            wav = joined[:-4] + "_fx.wav"
            V.ffmpeg("-i", joined, "-af", f"{V.TRIM},{V.FX[role0.get('fx', 'plain')]},{V.PAD}", "-ac", "1", wav)
            note = f"crowd:{len(role0['members'])} voices"
        else:
            wav, note = _orig_render_line(st, line, lang, tmp)
    finally:
        log = _GRID.get("log")
        _GRID.clear()
    if log:
        note += f" + on the beat (phrase starts {log[-1]} s)"
    role = st.cast["cast"][lang][line.get("voice") or line["who"]]
    if role.get("reverb"):
        out = wav[:-4] + "_hall.wav"
        add_reverb(wav, out, role["reverb"])
        wav, note = out, note + " + hall"
    return wav, note


V.render_line, V.join = render_line, grid_join


def mfcc_mean(wav):
    """Timbre fingerprint: mean MFCC 1-12 (c0 = loudness left out) over the frames within 25 dB of the loudest."""
    import numpy as np, parselmouth
    snd = parselmouth.Sound(wav)
    mf = snd.to_mfcc(number_of_coefficients=12)
    a = mf.to_array()[1:]
    it = snd.to_intensity(time_step=0.01)
    xs = np.array([mf.frame_number_to_time(k + 1) for k in range(a.shape[1])])
    lv = np.interp(xs, it.xs(), it.values[0])
    sel = lv > lv.max() - 25
    return [float(x) for x in (a[:, sel] if sel.any() else a).mean(axis=1)]


def timbre_dist(wav, ref):
    import numpy as np
    return float(np.linalg.norm(np.array(mfcc_mean(wav)) - np.array(ref)))


_X = V._extras()
if _X is not None:
    _orig_adjust = _X.score_adjust

    def score_adjust(role, ov, m, wav=None):
        pen = _orig_adjust(role, ov, m, wav)
        ref = ov.get("mfccRef", role.get("mfccRef"))
        if ref and wav:
            d = timbre_dist(wav, ref)
            m["timbreDist"] = round(d, 2)
            pen -= float(role.get("mfccWeight", 1.0)) * max(0.0, d - float(ov.get("mfccTol", role.get("mfccTol", 20.0))))
            print(f"   timbre distance {d:.1f}")
        return pen

    _X.score_adjust = score_adjust


def preview(lang):
    import numpy as np, soundfile as sf
    st = V.Story(SID)
    sr = 44100
    total = int((st.tl["duration"] + 1.0) * sr)
    mix = np.zeros(total, dtype=np.float32)
    n = 0
    for l in st.tl["lines"]:
        f = st.wav(lang, l["id"])
        if not os.path.exists(f):
            print("missing", f); continue
        x, r = sf.read(f, dtype="float32")
        assert r == sr
        a = int(l["t"] * sr)
        mix[a:a + len(x)] += x[: max(0, total - a)]
        n += 1
    tmp = os.path.join(st.out, f".preview_{lang}.wav")
    sf.write(tmp, mix, sr)
    out = os.path.join(st.out, f"preview_{lang}.mp3")
    V.ffmpeg("-i", tmp, "-ac", "1", "-b:a", "96k", out)
    os.remove(tmp)
    print(f"wrote {os.path.relpath(out, ROOT)}: {n} clips, {st.tl['duration']:.1f} s")


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "preview":
        preview(sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "zh")
    elif len(sys.argv) >= 2 and sys.argv[1] == "gen":
        sys.argv = [os.path.join(HERE, "voice.py"), SID, *sys.argv[1:]]
        V.main()
    else:
        sys.exit(__doc__)
