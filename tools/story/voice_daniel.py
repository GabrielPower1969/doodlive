#!/usr/bin/env python3
"""Daniel (pack #4) voice: tools/story/voice.py plus three Daniel-only additions, without editing the shared files.

    python3 tools/story/voice_daniel.py daniel gen|check|import|session ...   same commands as voice.py
    python3 tools/story/voice_daniel.py daniel harvest                        voice_extras.py harvest (same cache)

What it adds (patched into voice.py / voice_extras.py at run time; Esther, Ruth and every other story keep running
voice.py directly and are unaffected):

1. Acting measure `shriek` (cast `lines.<id>.<lang>.acting = {kind: "shriek", before: "救命", baseHz}`): the
   official's cartoon shriek (da_27). How far the pitch flies above his speaking voice (`baseHz`, the role's median
   on ordinary lines), how long a voiced scream is held, how loud it is against the words after it.
2. Timbre pinning `mfccRef` / `mfccTol` / `mfccWeight` (cast role): VoiceDesign invents a voice per take; a take whose
   timbre fingerprint (mean MFCC 1-12 over the speech frames) is further than `mfccTol` from the audition reference
   loses `mfccWeight` points per unit beyond it. Keeps a designed voice one person across lines.
3. `refZh` (cast top level): Chinese book names on the recording sheet (Daniel 6:4 -> 但以理书 6:4).

Raw Qwen takes go to $DOODLIVE_VOICE_CACHE when set (default ~/.cache/doodlive-voice, as voice.py).
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENVS = [os.path.join(ROOT, ".venv-voice/bin/python"), os.path.join(ROOT, ".venv-tts/bin/python3")]


def _reexec():
    try:
        import edge_tts  # noqa: F401
        return
    except ImportError:
        pass
    for py in VENVS:
        if os.path.exists(py) and os.path.realpath(py) != os.path.realpath(sys.executable):
            os.execv(py, [py, os.path.abspath(__file__), *sys.argv[1:]])
    sys.exit("edge-tts not found: python3 -m venv .venv-voice && .venv-voice/bin/pip install edge-tts")


sys.path.insert(0, HERE)
if len(sys.argv) > 2 and (sys.argv[2] in ("gen", "harvest") or "--asr" in sys.argv):
    _reexec()
import voice as V            # noqa: E402
import voice_extras as VX    # noqa: E402

try:                          # keep MLX's buffer cache small: two Qwen models + whisper share 16 GB with other jobs
    import mlx.core as _mx
    _mx.set_cache_limit(768 * 1024 * 1024)
except Exception:
    pass

if os.environ.get("DOODLIVE_VOICE_CACHE"):
    V.TAKE_CACHE = os.environ["DOODLIVE_VOICE_CACHE"]


# ------------------------------------------------------------------------------------------------- 1. shriek measure
_acting = V.acting


def acting(snd, words, spec, lang):
    if spec.get("kind") != "shriek":
        return _acting(snd, words, spec, lang)
    import numpy as np
    pitch = snd.to_pitch_ac(time_step=0.01, pitch_floor=65, pitch_ceiling=1100)
    f0, fx = pitch.selected_array["frequency"], pitch.xs()
    it = snd.to_intensity(time_step=0.01)
    iv, ix = it.values[0], it.xs()
    dur = snd.duration
    med = float(np.median(f0[f0 > 0])) if (f0 > 0).any() else 1.0
    b = V._anchor_time(words, spec.get("before"), lang, False)
    b = b if (b is not None and b > 0.4) else dur * 0.6
    base = float(spec.get("baseHz", med))
    sel = (fx <= b) & (f0 > 0)
    top = float(12 * np.log2(np.percentile(f0[sel], 90) / base)) if sel.sum() > 3 else 0.0
    hold = run = 0
    for on in sel:
        run = run + 1 if on else 0
        hold = max(hold, run)
    hold *= 0.01
    la, lb = iv[(ix <= b) & (iv > iv.max() - 40)], iv[(ix > b) & (iv > iv.max() - 40)]
    lift = float(np.percentile(la, 90) - np.percentile(lb, 90)) if len(la) and len(lb) else 0.0
    score = (2 * V._clip01((top - 5) / 9) + 1.5 * V._clip01(hold / 0.9) + 0.5 * V._clip01((b - 0.6) / 1.0)
             + V._clip01((lift + 2) / 6))
    return {"kind": "shriek", "regionSec": [0.0, round(b, 2)], "pitchTopSt": round(top, 1), "holdSec": round(hold, 2),
            "loudLiftDb": round(lift, 1), "baseHz": round(base, 1), "score": round(float(score), 2),
            "verdict": "shriek" if score >= 3.0 else ("half" if score >= 2.0 else "read")}


V.acting = acting


# ------------------------------------------------------------------------------------------------ 2. timbre pinning
def mfcc_mean(wav):
    """Mean MFCC 1-12 (c0, the loudness, left out) over frames within 25 dB of the loudest: a timbre fingerprint."""
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


class _Extras:
    """voice_extras with the timbre gate added to score_adjust; everything else passes through."""
    def __getattr__(self, k):
        return getattr(VX, k)

    @staticmethod
    def score_adjust(role, ov, m, wav=None):
        pen = VX.score_adjust(role, ov, m, wav)
        print(f"     f0 {m.get('f0MedianHz', 0):.0f} Hz, adj {pen:+.1f}", end="")
        ref = ov.get("mfccRef", role.get("mfccRef"))
        if ref and wav:
            d = timbre_dist(wav, ref)
            m["timbreDist"] = round(d, 2)
            pen -= float(role.get("mfccWeight", 1.0)) * max(0.0, d - float(ov.get("mfccTol", role.get("mfccTol", 20.0))))
            print(f"     timbre dist {d:.1f}", end="")
        return pen


_EX = _Extras()
V._extras = lambda: _EX


# ------------------------------------------------------------------------------------------------- 3. refZh on sheets
_session = V.cmd_session


def cmd_session(st, a):
    r = _session(st, a)
    f = os.path.join(st.out, "record", "zh", "lines.json")
    rows = json.load(open(f, encoding="utf-8"))
    for row in rows:
        for x, y in st.cast.get("refZh", {}).items():
            row["d"] = row["d"].replace(x, y)
    json.dump(rows, open(f, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    return r


V.cmd_session = cmd_session


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[2] == "harvest":
        VX.harvest(sys.argv[1])
    else:
        V.main()
