"""Extras for tools/story/voice.py that make a TTS line sound more like a person (first used by Ruth, pack #3).

voice.py calls `post_take(...)` on the chosen take of every line (a small hook, no other coupling), so stories whose
cast file does not use these options are unaffected (Esther, David & Goliath).

Breaths (cast file `lines.<id>.<lang>.breath`, or `lines.<id>.breath` for both languages):
    {"before": true}                     an in-breath right before the line starts
    {"after": "唉……"}                    (also) an in-breath inside the line, in the pause that follows this text
    {"gain": -2, "gap": 0.12}            breath level (dB, relative to the library breath) and silence after it
The breath is never synthetic noise: it is a real inhalation cut out of the same voice's own TTS takes
(`harvest`), so it has that speaker's timbre and room. If the chosen take already breathes there (the model sometimes
does), nothing is added.

    python3 tools/story/voice_extras.py harvest <story-id>   scan the cached takes of each role for real in-breaths
                                                             and keep the best few per role in assets/<id>/audio/voice/breaths/
"""
import json, os, re, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))


# ------------------------------------------------------------------------------------------------- breath detection
def find_breaths(wav, min_len=0.2, max_len=0.75):
    """In-breaths in a clip: unvoiced, quiet (20-42 dB under the clip's loud speech), mostly-above-1-kHz stretches of
    0.2-0.75 s (shorter ones are fricatives) that come out of silence, are not as bright as a sibilant
    (centroid < 3.5 kHz) and end within 0.3 s of voiced speech. Returns [(start, end, level_db_re_peak)]."""
    import numpy as np, parselmouth
    snd = parselmouth.Sound(wav)
    pitch = snd.to_pitch_ac(time_step=0.01, pitch_floor=65, pitch_ceiling=600)
    f0, fx = pitch.selected_array["frequency"], pitch.xs()
    it = snd.to_intensity(time_step=0.01, minimum_pitch=100)
    iv, ix = it.values[0], it.xs()
    loud = float(np.percentile(iv, 95))
    voiced = lambda t: f0[min(len(f0) - 1, max(0, int(round((t - fx[0]) / 0.01))))] > 0
    # spectral check: a breath is broadband hiss with most energy above 1 kHz
    x = snd.values[0]
    sr = snd.sampling_frequency
    out, k = [], 0
    cand = (iv < loud - 20) & (iv > loud - 42)
    while k < len(ix):
        if cand[k] and not voiced(ix[k]):
            j = k
            while j + 1 < len(ix) and cand[j + 1] and not voiced(ix[j + 1]):
                j += 1
            a, b = ix[k], ix[j]
            if min_len <= b - a <= max_len:
                nxt = [t for t in fx[f0 > 0] if t > b]
                seg = x[int(a * sr):int(b * sr)]
                if nxt and nxt[0] - b < 0.3 and len(seg) > 256:
                    spec = np.abs(np.fft.rfft(seg * np.hanning(len(seg)))) ** 2
                    fr = np.fft.rfftfreq(len(seg), 1 / sr)
                    hi = spec[fr > 1000].sum() / (spec.sum() + 1e-12)
                    cen = float((spec * fr).sum() / (spec.sum() + 1e-12))
                    pre = iv[(ix > a - 0.15) & (ix < a - 0.01)]
                    # a breath comes out of silence (or the clip start); a fricative (s, sh, x) sits right after
                    # speech and is brighter (centroid > 3.5 kHz)
                    quiet_before = len(pre) == 0 or float(pre.mean()) < loud - 35
                    if hi > 0.55 and cen < 3500 and quiet_before:
                        out.append((round(float(a), 2), round(float(b), 2), round(float(iv[k:j + 1].mean() - loud), 1)))
            k = j + 1
        else:
            k += 1
    return out


def breath_before(wav, t, window=0.6):
    """Is there already an in-breath ending within `window` s before time t?"""
    return any(t - window <= b <= t + 0.05 for a, b, _ in find_breaths(wav))


# -------------------------------------------------------------------------------------------------------- harvesting
def harvest(story):
    """Collect real in-breaths from every cached raw take of each role (keyed by the cast file) into a small library."""
    import numpy as np, soundfile as sf
    sys.path.insert(0, HERE)
    import voice as V
    st = V.Story(story)
    lib = os.path.join(st.out, "breaths")
    os.makedirs(lib, exist_ok=True)
    found = {}
    for lang in V.LANGS:
        for role_id, role in st.cast["cast"][lang].items():
            if not role.get("engine", "").startswith("qwen"):
                continue
            design = role["engine"] == "qwen_design"
            model = V.QWEN_DESIGN if design else V.QWEN_MODEL
            items = []
            for line in st.tl["lines"]:
                if (line.get("voice") or line["who"]) != role_id:
                    continue
                lc = st.cast.get("lines", {}).get(line["id"], {})
                ov = {"instruct": lc.get("m" if lang == "zh" else "m_en") or line.get("dir", ""), **lc.get(lang, {})}
                takes = int(ov.get("takes", role.get("takes", 1)))
                for k in range(takes):
                    seed = (ov.get("seed", 0) + k) if takes > 1 else ov.get("seed")
                    instruct = " ".join(x for x in ((ov.get("design", role.get("design", "")) if design else ""),
                                                    role.get("instruct", ""), ov.get("instruct", "")) if x)
                    voice = ov.get("voice", role["voice"])
                    key = V.hashlib.sha1(json.dumps([model, None if design else voice, instruct, lang, line[lang],
                                                     seed]).encode()).hexdigest()[:16]
                    f = os.path.join(V.TAKE_CACHE, f"qwen_{key}.wav")
                    if os.path.exists(f):
                        for a, b, lv in find_breaths(f):
                            items.append((f, a, b, lv))
            items.sort(key=lambda c: abs((c[2] - c[1]) - 0.38) + abs(c[3] + 24) / 20)
            keep = []
            for n, (f, a, b, lv) in enumerate(items[:4]):
                x, sr = sf.read(f, dtype="float32")
                # stop 50 ms short of the end: the next word's first consonant (sh, zh) can start inside it
                seg = x[max(0, int((a - 0.03) * sr)):int((b - 0.05) * sr)].copy()
                fade = int(0.04 * sr)
                seg[:fade] *= np.linspace(0, 1, fade); seg[-fade:] *= np.linspace(1, 0, fade)
                # store at its level relative to the take's loud speech, so it can be placed at the same relation
                ref = float(np.sqrt(np.mean(x[np.abs(x) > 0.05] ** 2))) if (np.abs(x) > 0.05).any() else 0.1
                name = f"{lang}_{role_id}_{n}.wav"
                sf.write(os.path.join(lib, name), seg / ref * 0.1, sr)
                keep.append({"file": name, "sec": round(b - a, 2), "levelDb": lv, "from": os.path.basename(f), "at": a})
            found[f"{lang}.{role_id}"] = keep
            print(f"{lang} {role_id:9s} {len(items):3d} breaths found, kept {len(keep)}")
    json.dump(found, open(os.path.join(lib, "breaths.json"), "w"), indent=1)
    return found


# --------------------------------------------------------------------------------------------------- the voice hook
def _anchor_end(words, anchor, lang):
    sys.path.insert(0, HERE)
    import voice as V
    return V._anchor_time(words, re.sub(r"[^\w\s']", "", anchor), lang, True)


def hnr_db(wav):
    """Mean harmonics-to-noise ratio of the voiced frames (dB): lower = breathier / huskier (an age cue)."""
    import parselmouth
    hv = parselmouth.Sound(wav).to_harmonicity_cc().values[0]
    return float(hv[hv > -50].mean())


def score_adjust(role, ov, m, wav=None):
    """Added to voice.py's take score. VoiceDesign invents the voice anew on every take (the same description gave a
    98 Hz and a 189 Hz median on two seeds), so a role may pin its voice with `f0Hz: [lo, hi]` (median F0 of the take):
    takes outside it lose 3 points per 10 % outside, which keeps one person across the lines. `hnrMax` keeps an old
    voice husky; `maxErr` keeps a key word."""
    # `maxErr` (per line): a key word must be heard (ru_03 "不，我不走": a livelier take that says 我……我不走 loses)
    pen = -200.0 * max(0.0, m.get("errorRate", 0) - float(ov.get("maxErr", 1.0)))
    lo, hi = (ov.get("f0Hz") or role.get("f0Hz") or (0, 1e9))
    f = m.get("f0MedianHz", 0) or 0
    if not f:
        return pen
    out = max(0.0, lo / f - 1, f / hi - 1)
    # `hnrMax` (dB): an old, husky voice (Naomi) must stay breathy; a clear, young-sounding take loses 1 point per dB
    hm = ov.get("hnrMax", role.get("hnrMax"))
    if hm is not None and wav:
        pen -= max(0.0, hnr_db(wav) - float(hm))
    return pen - 30.0 * out


def post_take(st, line, lang, wav, tmp):
    """Called by voice.py on the chosen (pre-level) take. Returns (wav, note); unchanged when the line asks for nothing."""
    lc = st.cast.get("lines", {}).get(line["id"], {})
    spec = lc.get(lang, {}).get("breath", lc.get("breath"))
    if not spec:
        return wav, ""
    import numpy as np, soundfile as sf
    lib = os.path.join(st.out, "breaths")
    idx = json.load(open(os.path.join(lib, "breaths.json"))) if os.path.exists(os.path.join(lib, "breaths.json")) else {}
    role_id = line.get("voice") or line["who"]
    role = st.cast["cast"][lang].get(role_id, {})
    # a voice that never breathes on its own (edge-tts) borrows the breaths of a similar Qwen voice: `breathFrom`
    pool = idx.get(role.get("breathFrom") or f"{lang}.{role_id}") or []
    if not pool:
        return wav, " (breath asked, none in library: run voice_extras.py harvest)"
    x, sr = sf.read(wav, dtype="float32")
    loud = x[np.abs(x) > 0.05]
    ref = float(np.sqrt(np.mean(loud ** 2))) if len(loud) else 0.1
    pick = pool[int(spec.get("pick", sum(map(ord, line["id"])) % len(pool)))]
    b, bsr = sf.read(os.path.join(lib, pick["file"]), dtype="float32")
    if bsr != sr:
        from scipy.signal import resample
        b = resample(b, int(len(b) * sr / bsr)).astype(np.float32)
    b = b / 0.1 * ref * 10 ** (float(spec.get("gain", 0.0)) / 20)
    gap = np.zeros(int(float(spec.get("gap", 0.1)) * sr), dtype=np.float32)
    notes = []
    if spec.get("after"):
        sys.path.insert(0, HERE)
        import voice as V
        _, words = V.transcribe(wav, lang)
        t = _anchor_end(words, spec["after"], lang)
        env = np.abs(x)
        if t is not None and (env[int(t * sr):] > 0.03).any():
            on = int(t * sr) + int(np.argmax(env[int(t * sr):] > 0.03))      # onset of the next word
            if not breath_before(wav, on / sr):
                keep = min(on, int(t * sr) + int(0.12 * sr))                     # a short bit of the old pause stays
                pre = max(0, on - int(0.03 * sr))
                x = np.concatenate([x[:keep], b, gap, x[pre:]])
                notes.append(f"breath after {spec['after']}")
            else:
                notes.append("own breath kept")
    if spec.get("before"):
        onset = int(np.argmax(np.abs(x) > 0.03))
        if not breath_before(wav, onset / sr + 0.05, 0.5):
            lead = x[:max(0, onset - int(0.02 * sr))]
            x = np.concatenate([lead[:int(0.03 * sr)], b, gap, x[max(0, onset - int(0.02 * sr)):]])
            notes.append("breath before")
        else:
            notes.append("own breath kept")
    out = wav[:-4] + "_br.wav"
    sf.write(out, x, sr)
    return out, (" + " + ", ".join(notes)) if notes else ""


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "harvest":
        harvest(sys.argv[2])
    else:
        sys.exit(__doc__)
