#!/usr/bin/env python3
"""He Is Risen! (risen) voice: tools/story/voice.py with the Exodus add-ons (pitch / timbre pins), Jonah's
crowd re-takes, and two guards learned on Real Miracles (2026-11-18).

    python3 tools/story/voice_risen.py gen|check|session ...     same commands as `voice.py risen ...`

Guards (this pack only; voice.py is not edited):
  runaway  A raw Qwen take far longer than its text (a bare "哎！" once made Qwen talk for 15-45 s, and the transcript
           check ignored the junk) is re-spoken with seed + 1000*i, up to RETRIES times; if every retry runs away the
           shortest is kept and a warning printed. Limit: RUNAWAY x the expected length (0.28 s per Han character or
           0.40 s per English word, + 0.6 s). It applies to every phrase and every crowd member.
  crowd    A role with `takes: N` renders the crowd N times with shifted member seeds and keeps the mix with the lowest
           transcript error plus a repetition penalty (a looping chant: the transcript longer than the line, or the mix
           far longer than the line). Roles without `takes` behave as plain voice.py.
"""
import os, re, shutil, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENV = os.path.join(ROOT, ".venv-voice/bin/python")
SID = "risen"
try:                      # re-run under the voice venv *as this file* (voice_exodus would re-run itself)
    import edge_tts, numpy, scipy  # noqa: F401
except ImportError:
    os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])
sys.path.insert(0, HERE)
import voice_exodus  # noqa: F401,E402  (patches voice.render_line / voice_extras.score_adjust: f0Weight, mfccRef)
import voice as V    # noqa: E402
import tts_lock      # noqa: E402

RUNAWAY = 2.5         # a take longer than 2.5x its expected length is a runaway
RETRIES = 5


def expected_sec(text, lang):
    if lang == "zh":
        n = len(re.findall(r"[一-鿿]", text))
        return 0.28 * n + 0.6
    return 0.40 * len(re.findall(r"[A-Za-z']+", text)) + 0.6


def _sec(f):
    import soundfile as sf
    i = sf.info(f)
    return i.frames / i.samplerate


def _runaway_guard():
    orig = V.speak

    def speak(text, role, ov, lang, out, seed=None):
        note = orig(text, role, ov, lang, out, seed)
        if not str(ov.get("engine", role.get("engine", ""))).startswith("qwen"):
            return note
        lim = RUNAWAY * expected_sec(text, lang)
        d = _sec(out)
        if d <= lim:
            return note
        best = (d, out + ".best.wav")
        shutil.copyfile(out, best[1])
        base = int(seed or 0)
        for i in range(1, RETRIES + 1):
            s = base + 1000 * i
            orig(text, role, ov, lang, out, s)
            d2 = _sec(out)
            print(f"   runaway guard: {text[:24]!r} {d:.1f}s > {lim:.1f}s; retry seed {s}: {d2:.1f}s", flush=True)
            if d2 <= lim:
                return note
            if d2 < best[0]:
                best = (d2, out + ".best.wav")
                shutil.copyfile(out, best[1])
        shutil.copyfile(best[1], out)
        print(f"   WARNING runaway guard: every retry too long, kept the shortest ({best[0]:.1f}s)", flush=True)
        return note

    V.speak = speak


def _crowd_takes():
    orig = V.render_crowd

    def render_crowd(text, role, ov, lang, out, tmp, tag):
        n = int(ov.get("takes", role.get("takes", 1)))
        if n <= 1:
            return orig(text, role, ov, lang, out, tmp, tag)
        pat = r"[一-鿿]" if lang == "zh" else r"[a-z']+"
        nref = max(1, len(re.findall(pat, text.lower())))
        lim = RUNAWAY * expected_sec(text, lang) + 0.6        # + the members' stagger and the hall
        best = None
        for v in range(n):
            r = {**role, "seed": int(role.get("seed", 7)) + 31 * v,
                 "members": [{**m, "seed": int(m.get("seed", j)) + 100 * v} for j, m in enumerate(role["members"])]}
            f = os.path.join(tmp, f"{tag}_crowd_v{v}.wav")
            orig(text, r, ov, lang, f, tmp, f"{tag}_v{v}")
            hyp, _ = V.transcribe(f, lang)
            err = V.error_rate(text, hyp, lang, ov.get("asrIgnore"))
            nh = len(re.findall(pat, hyp.lower()))
            rep = max(0.0, nh / nref - 1.25)                   # the chant looped: more words heard than written
            d = _sec(f)
            long_ = max(0.0, d / lim - 1.0)
            score = err + rep + 2 * long_
            print(f"   crowd take {v}: score {score:.2f} (err {err:.2f} rep {rep:.2f} {d:.1f}s/{lim:.1f}s)  {hyp}", flush=True)
            if best is None or score < best[0]:
                best = (score, f)
        print(f"   -> crowd take with score {best[0]:.2f}")
        shutil.copyfile(best[1], out)

    V.render_crowd = render_crowd


_runaway_guard()
_crowd_takes()
try:
    import mlx.core as _mx
    _mx.set_cache_limit(768 * 1024 * 1024)
except Exception:
    pass
if __name__ == "__main__":
    sys.argv = [os.path.join(HERE, "voice.py"), SID, *sys.argv[1:]]
    if len(sys.argv) > 2 and sys.argv[2] == "gen":
        with tts_lock.held("voice_risen gen"):   # one local TTS run at a time (tools/story/tts_lock.py)
            V.main()
    else:
        V.main()
