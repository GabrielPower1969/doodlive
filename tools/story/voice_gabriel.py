#!/usr/bin/env python3
"""Gabriel (the archangel pack) voice: tools/story/voice.py plus two run-time additions, without editing the shared
files (the method of tools/story/voice_daniel.py; every other story keeps running its own entry point).

    python3 tools/story/voice_gabriel.py gabriel gen|check|import|session ...   same commands as voice.py
    python3 tools/story/voice_gabriel.py gabriel harvest                        voice_extras.py harvest (same cache)
    python3 tools/story/voice_gabriel.py gabriel consistent [--write]           one-person pick for the designed voice

What it adds:

1. Timbre pinning `mfccRef` / `mfccTol` / `mfccWeight` (cast role): VoiceDesign invents a voice per take; a take whose
   timbre fingerprint (mean MFCC 1-12 over the speech frames) is further than `mfccTol` from the audition reference
   loses `mfccWeight` points per unit beyond it. A weak measure (docs/daniel/VOICE.md), so it only breaks ties; the
   pitch window `f0Hz` and the clean-voice floor `hnrMin` do the real pinning.
2. `hnrMin` (cast role or line, dB): Gabriel is young and clear, never husky. A take whose mean harmonics-to-noise
   ratio is below it loses 1 point per dB (voice_extras has only the opposite gate, `hnrMax`, for old voices).
3. `consistent`: VoiceDesign invents the speaker anew on every take (the same description gave 95 Hz and 264 Hz on
   two seeds of one line), and voice.py picks every line on its own. This command looks at all cached takes of the
   role at once and finds the one-take-per-line set that is closest to being one man: for every possible anchor take
   it gives each line the take nearest to the anchor (timbre fingerprint + pitch, livelier takes preferred; only
   takes that pass the words / pitch-window / pace gates), and keeps the anchor with the smallest total. `--write`
   stores the picks (`pick`, `pickWhy`) and the set's mean fingerprint (`mfccRef`) in the cast file; then run `gen`.
4. Mandarin words are compared **by sound**: whisper writes 加百列 as 加百烈, 马利亚 as 玛利亚, 他 as 她 (the same
   syllables and tones), which the shared character error rate counts as mistakes and which knocked correct takes
   out of the running. Here the zh error rate is the edit distance over pinyin syllables with tones (pypinyin), so
   a homophone is no error and a real slip (加倍力, 看过 for 看顾) still is.
5. `refZh` (cast top level): Chinese book names on the zh recording sheet (Luke 1:19 -> 路加福音 1:19).

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
            os.execv(py, [py, os.path.abspath(sys.argv[0]), *sys.argv[1:]])
    sys.exit("edge-tts not found: python3 -m venv .venv-voice && .venv-voice/bin/pip install edge-tts")


sys.path.insert(0, HERE)
if __name__ != "__main__" or (len(sys.argv) > 2 and (sys.argv[2] in ("gen", "harvest", "consistent") or "--asr" in sys.argv)):
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


# ------------------------------------------------------------------------------------------- 4. zh words by sound
_error_rate = V.error_rate


def error_rate(ref, hyp, lang, ignore=None):
    if lang != "zh":
        return _error_rate(ref, hyp, lang, ignore)
    try:
        from pypinyin import lazy_pinyin, Style
    except ImportError:
        return _error_rate(ref, hyp, lang, ignore)
    import re
    out = []
    for txt in (ref, hyp):
        ch = re.findall(r"[\u4e00-\u9fff]", txt)
        if ignore:
            ch = [x for x in ch if not re.fullmatch(ignore, x)]
        out.append(lazy_pinyin("".join(ch), style=Style.TONE3, neutral_tone_with_five=True))
    return V._edit(out[0], out[1]) / max(1, len(out[0]))


V.error_rate = error_rate


# --------------------------------------------------------------------------------------- 1 + 2. timbre and clean voice
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
    """voice_extras with the timbre gate and the clean-voice floor added to score_adjust; the rest passes through."""
    def __getattr__(self, k):
        return getattr(VX, k)

    @staticmethod
    def score_adjust(role, ov, m, wav=None):
        pen = VX.score_adjust(role, ov, m, wav)
        print(f"     f0 {m.get('f0MedianHz', 0):.0f} Hz, adj {pen:+.1f}", end="")
        hmin = ov.get("hnrMin", role.get("hnrMin"))
        if hmin is not None and wav:
            h = VX.hnr_db(wav)
            m["hnrDb"] = round(h, 1)
            pen -= max(0.0, float(hmin) - h)
            print(f"     hnr {h:.1f} dB", end="")
        ref = ov.get("mfccRef", role.get("mfccRef"))
        if ref and wav:
            d = timbre_dist(wav, ref)
            m["timbreDist"] = round(d, 2)
            pen -= float(role.get("mfccWeight", 1.0)) * max(0.0, d - float(ov.get("mfccTol", role.get("mfccTol", 20.0))))
            print(f"     timbre dist {d:.1f}", end="")
        return pen


_EX = _Extras()
V._extras = lambda: _EX


# ------------------------------------------------------------------------------------------------- 5. refZh on sheets
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


# ------------------------------------------------------------------------------------- 3. one man across the lines
def consistent(story, write=False, role_id="gabriel", langs=V.LANGS):
    import hashlib, tempfile
    import numpy as np
    st = V.Story(story)
    for lang in langs:
        role = st.cast["cast"][lang].get(role_id, {})
        if role.get("engine") != "qwen_design":
            continue
        lo, hi = role.get("f0Hz", (0, 1e9)); rows = []
        with tempfile.TemporaryDirectory() as tmp:
            for line in st.tl["lines"]:
                if (line.get("voice") or line["who"]) != role_id:
                    continue
                lc = st.cast.get("lines", {}).get(line["id"], {})
                ov = {"instruct": lc.get("m" if lang == "zh" else "m_en") or line.get("dir", ""), **lc.get(lang, {})}
                takes = int(ov.get("takes", role.get("takes", 1)))
                for k in range(takes):
                    seed = (ov.get("seed", 0) + k) if takes > 1 else ov.get("seed")
                    instruct = " ".join(x for x in (ov.get("design", role.get("design", "")), role.get("instruct", ""),
                                                    ov.get("instruct", "")) if x)
                    key = hashlib.sha1(json.dumps([V.QWEN_DESIGN, None, instruct, lang, line[lang], seed]).encode()).hexdigest()[:16]
                    raw = os.path.join(V.TAKE_CACHE, f"qwen_{key}.wav")
                    if not os.path.exists(raw):
                        continue
                    memo = raw + f".{role.get('fx', 'plain')}.json"        # measurements are kept next to the take
                    if os.path.exists(memo):
                        c = json.load(open(memo))
                    else:
                        wav = os.path.join(tmp, f"{line['id']}_{k}.wav")
                        V.ffmpeg("-i", raw, "-af", f"{V.TRIM},{V.FX[role.get('fx', 'plain')]},{V.PAD}", "-ac", "1", wav)
                        c = dict(m=V.measure(wav, line[lang], lang, ov.get("asrIgnore")), hnr=VX.hnr_db(wav), mfcc=mfcc_mean(wav))
                        json.dump(c, open(memo, "w"), ensure_ascii=False)
                    m = c["m"]; m["errorRate"] = V.error_rate(line[lang], m["asr"], lang, ov.get("asrIgnore"))
                    sc = V.take_score(m, float(role.get("maxPause", 1.0)), float(role.get("minPace", 3.0 if lang == "zh" else 2.8)))
                    rows.append(dict(id=line["id"], k=k, err=m["errorRate"], f0=m["f0MedianHz"] or 1.0, score=sc,
                                     win=ov.get("f0Hz", (lo, hi)), hmin=float(ov.get("hnrMin", role.get("hnrMin", -99))),
                                     hnr=c["hnr"], mfcc=np.array(c["mfcc"]), sec=m["sec"], asr=m["asr"]))
        ids = sorted({r["id"] for r in rows})
        if not ids:
            print(f"{lang}: no cached takes (set DOODLIVE_VOICE_CACHE to the cache of the last gen)"); continue
        ok = {}
        for lid in ids:
            c = [r for r in rows if r["id"] == lid]; floor = min(r["err"] for r in c) + 0.04; top = max(r["score"] for r in c)
            for widen in (1.0, 1.06, 1.12, 9.0):                     # a line with no take in the window may reach a little outside
                g = [r for r in c if r["err"] <= floor and r["win"][0] / widen <= r["f0"] <= r["win"][1] * widen and r["hnr"] >= r["hmin"] - 1.5
                     and r["score"] >= top - 5]
                if g:
                    break
            ok[lid] = g
        dist = lambda r, a: float(np.linalg.norm(r["mfcc"] - a["mfcc"])) + 8 * abs(12 * np.log2(r["f0"] / a["f0"]))
        best = None
        for a in (r for g in ok.values() for r in g):
            sel = {lid: min(g, key=lambda r: dist(r, a) - 3 * r["score"]) for lid, g in ok.items()}
            tot = sum(dist(r, a) - 3 * r["score"] for r in sel.values())
            if best is None or tot < best[0]:
                best = (tot, a, sel)
        _, a, sel = best
        ref = np.mean([r["mfcc"] for r in sel.values()], axis=0)
        f0s = [r["f0"] for r in sel.values()]
        print(f"\n{lang} {role_id}: anchor {a['id']} take {a['k']}; set F0 {min(f0s):.0f}-{max(f0s):.0f} Hz "
              f"({12 * np.log2(max(f0s) / min(f0s)):.1f} st), mean timbre distance to the set "
              f"{np.mean([np.linalg.norm(r['mfcc'] - ref) for r in sel.values()]):.1f}")
        for lid in ids:
            r = sel[lid]
            print(f"  {lid}: take {r['k']}  f0 {r['f0']:.0f} Hz  hnr {r['hnr']:.1f}  err {r['err']:.2f}  score {r['score']:.2f}  "
                  f"{r['sec']:.1f}s  dist {np.linalg.norm(r['mfcc'] - ref):.1f}  (of {len(ok[lid])} passing)  {r['asr']}")
            if write:
                e = st.cast.setdefault("lines", {}).setdefault(lid, {}).setdefault(lang, {})
                e["pick"] = r["k"]
                e["pickWhy"] = (f"one-man set (voice_gabriel.py consistent): take {r['k']} is the take of this line nearest to the "
                                f"set's anchor ({a['id']} take {a['k']}) in timbre and pitch among the {len(ok[lid])} takes that "
                                f"pass the gates; f0 {r['f0']:.0f} Hz, HNR {r['hnr']:.1f} dB, err {r['err']:.2f}")
        if write:
            role["mfccRef"] = [round(float(x), 2) for x in ref]
    if write:
        json.dump(st.cast, open(st.cast_path, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
        print(f"\nwrote picks and mfccRef to {os.path.relpath(st.cast_path, ROOT)}; now run gen")


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[2] == "consistent":
        consistent(sys.argv[1], "--write" in sys.argv,
                   langs=[sys.argv[sys.argv.index("--lang") + 1]] if "--lang" in sys.argv else V.LANGS)
    elif len(sys.argv) == 3 and sys.argv[2] == "harvest":
        VX.harvest(sys.argv[1])
    else:
        V.main()
