#!/usr/bin/env python3
"""Jonah (pack #5) voice: tools/story/voice.py with the Exodus add-ons (god's hall, timbre pinning) attached.

    python3 tools/story/voice_jonah.py gen|check|import|session ...     same commands as `voice.py jonah ...`
    python3 tools/story/voice_jonah.py harvest                          voice_extras.py harvest (real breaths)

voice.py is not edited. Importing voice_exodus only patches voice.py at run time (reverb on a role, grid, mfccRef);
Exodus' own files are untouched.
"""
import os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENV = os.path.join(ROOT, ".venv-voice/bin/python")
try:                      # re-run under the voice venv *as this file* (voice_exodus would re-run itself: Exodus lines!)
    import edge_tts, numpy, scipy  # noqa: F401
except ImportError:
    os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])
sys.path.insert(0, HERE)
import voice_exodus  # noqa: F401,E402  (patches voice.render_line / voice_extras.score_adjust)
import voice as V    # noqa: E402
import voice_extras as VX  # noqa: E402
import tts_lock  # noqa: E402


def _crowd_takes():
    """Crowd re-takes (2026-11-15): a role with `takes: N` renders the crowd N times with shifted member seeds and keeps
    the mix whose transcript is closest to the line (the first mix of jn_22 was heard as "少年！少年！"). Roles
    without `takes` behave exactly as before."""
    orig = V.render_crowd

    def render_crowd(text, role, ov, lang, out, tmp, tag):
        n = int(role.get("takes", 1))
        if n <= 1:
            return orig(text, role, ov, lang, out, tmp, tag)
        best = None
        for v in range(n):
            r = {**role, "seed": int(role.get("seed", 7)) + 31 * v,
                 "members": [{**m, "seed": int(m.get("seed", j)) + 100 * v} for j, m in enumerate(role["members"])]}
            f = os.path.join(tmp, f"{tag}_crowd_v{v}.wav")
            orig(text, r, ov, lang, f, tmp, f"{tag}_v{v}")
            hyp, _ = V.transcribe(f, lang)
            err = V.error_rate(text, hyp, lang, ov.get("asrIgnore"))
            print(f"   crowd take {v}: err {err:.2f}  {hyp}", flush=True)
            if best is None or err < best[0]:
                best = (err, f)
        print(f"   -> crowd take with err {best[0]:.2f}")
        import shutil
        shutil.copyfile(best[1], out)

    V.render_crowd = render_crowd


_crowd_takes()
try:
    import mlx.core as _mx
    _mx.set_cache_limit(768 * 1024 * 1024)
except Exception:
    pass
if __name__ == "__main__":
    if len(sys.argv) == 2 and sys.argv[1] == "harvest":
        VX.harvest("jonah")
    else:
        sys.argv = [os.path.join(HERE, "voice.py"), "jonah", *sys.argv[1:]]
        if len(sys.argv) > 2 and sys.argv[2] == "gen":
            with tts_lock.held("voice_jonah gen"):   # one local TTS run at a time (tools/story/tts_lock.py)
                V.main()
        else:
            V.main()
