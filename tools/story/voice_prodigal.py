#!/usr/bin/env python3
"""The prodigal son (pack #6) wrapper around tools/story/voice.py, built on the Exodus wrapper.

Usage:  python3 tools/story/voice_prodigal.py gen [--lang zh|en|all] [--only pr_02,...] [--force]   (as voice.py gen)
        python3 tools/story/voice_prodigal.py audition ROLE LANG LINE [LINE...] [--seeds 0,1] [--design N]
        python3 tools/story/voice_prodigal.py timbre [--lang zh|en]
        python3 tools/story/voice_prodigal.py preview [--lang zh|en]
        python3 tools/story/voice_prodigal.py prune
        python3 tools/story/voice.py prodigal check [--asr]                                          (unchanged)

Why a wrapper: voice.py / voice_extras.py are shared by every pack and stay untouched. Importing voice_exodus.py
attaches its run-time options to voice.py (role `reverb`, line `grid`, role `mfccRef` timbre pin: see its docstring);
they read the cast file of whichever story runs, so they work here unchanged. Added here:

  takes.json   every take of every line `gen` makes (score, error, pitch SD, pace, length, transcript) and the one
               kept, merged into assets/prodigal/audio/voice/takes.json (lines not re-made keep their record).
  audition     speak lines with one role's settings (or an alternative `designs[N]` from the cast file) under several
               seeds, print median F0 / F0 SD / HNR / whisper error and the timbre fingerprint (mean MFCC 1-12).
               Scratch only: nothing is written to the pack.
  timbre       per role: the spread of its own lines (largest distance of a line from the role's centroid) and the
               distance between role centroids, plus the distance of each prodigal male role from the male voices of
               the other packs (Moses, Boaz, Esther's king, Haman, Pharaoh, Daniel's king): the father must not sound
               like them, the son and the brother must not sound like each other.
  prune        delete the raw Qwen takes of this pack that were not kept (the take cache is shared; see prune()).
  mfccAvoid    (role) [{who, ref, min, weight}]: keep away from another voice (refs: centroids at the 24 kHz working rate).
  f0Ceil       (role) pitch ceiling used for the median F0 that the `f0Hz` pin reads (octave-safe for men).
  preview      every clip of one language at its timeline time, voices only (as voice_exodus.py preview).
"""
import io, json, os, re, sys, contextlib

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENV = os.path.join(ROOT, ".venv-voice/bin/python")
SID = "prodigal"


def _reexec():
    try:
        import edge_tts, numpy, scipy  # noqa: F401
    except ImportError:
        if os.path.exists(VENV) and os.path.realpath(VENV) != os.path.realpath(sys.executable):
            os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])
        raise


_reexec()
sys.path.insert(0, HERE)
import voice as V            # noqa: E402
import voice_exodus as E     # noqa: E402  (patches V.render_line / V.join / score_adjust; story-agnostic)

_render = V.render_line
TAKES = {}


class _Tee(io.TextIOBase):
    def __init__(self, a):
        self.a, self.buf = a, []

    def write(self, s):
        self.a.write(s); self.a.flush(); self.buf.append(s)
        return len(s)


TAKE_RE = re.compile(r"take (\d+): score\s+(-?[\d.]+)\s+err ([\d.]+)\s+f0sd ([\d.]+)\s+pace ([\d.]+)/s\s+([\d.]+)s\s+(.*)$")


def render_line(st, line, lang, tmp):
    """The Exodus render_line, with its take printout captured into takes.json."""
    tee = _Tee(sys.stdout)
    with contextlib.redirect_stdout(tee):
        wav, note = _render(st, line, lang, tmp)
    takes, extra = [], {}
    for ln in "".join(tee.buf).splitlines():          # score_adjust prints before the take's own line
        if "timbre distance" in ln:
            extra["timbre"] = float(ln.split()[-1])
        if "distance from" in ln:
            extra["from_" + ln.split()[2]] = float(ln.split()[-1])
        if "robust F0" in ln:
            extra["f0Hz"] = float(ln.split()[-2])
        m = TAKE_RE.search(ln)
        if m:
            k, s, e, sd, p, sec, rest = m.groups()
            takes.append({"take": int(k), "score": float(s), "err": float(e), "f0sd": float(sd), "pace": float(p),
                          "sec": float(sec), **extra, "asr": rest.strip()})
            extra = {}
    kept = re.search(r"take (\d+) of", note)
    TAKES.setdefault(lang, {})[line["id"]] = {"kept": note, "takes": takes}
    # remember which raw Qwen takes this run made and which one was kept (`prune` deletes the others)
    k = int(kept.group(1)) if kept else 0
    tag = f"{lang}_{line['id']}_t"
    for out, cached in list(_COPIES.items()):
        if os.path.basename(out).startswith(tag) or os.path.basename(out).startswith(f"{lang}_{line['id']}_m"):
            keep = not os.path.basename(out).startswith(tag) or os.path.basename(out).startswith(f"{tag}{k}_")
            _CACHE_LOG.setdefault(cached, keep or _CACHE_LOG.get(cached, False))
            if keep:
                _CACHE_LOG[cached] = True
            del _COPIES[out]
    _save_cache_log()
    return wav, note


_COPIES, _CACHE_LOG = {}, {}
CACHE_LOG = os.path.join(V.TAKE_CACHE, "prodigal_takes.json")
if os.path.exists(CACHE_LOG):
    _CACHE_LOG.update(json.load(open(CACHE_LOG)))
_copy = V.shutil.copyfile


class _Sh:                       # voice.py copies each cached raw take with shutil.copyfile(cached, out): note the pair
    def __getattr__(self, k):
        return getattr(__import__("shutil"), k)

    @staticmethod
    def copyfile(a, b):
        if os.path.dirname(os.path.abspath(a)) == os.path.abspath(V.TAKE_CACHE):
            _COPIES[b] = a
        return _copy(a, b)


V.shutil = _Sh()


def _save_cache_log():
    json.dump(_CACHE_LOG, open(CACHE_LOG, "w"), indent=0)


def kept_cache_files(st):
    """The raw Qwen takes behind the clips now in the pack: the cache key of voice.speak (model, voice, instruct,
    lang, text, seed) re-derived from the cast file and the take number recorded in sources.json."""
    import hashlib
    keep = set()
    for lang in V.LANGS:
        for line in st.tl["lines"]:
            note = st.src.get(lang, {}).get(line["id"], "")
            role = st.cast["cast"][lang][line.get("voice") or line["who"]]
            ov = st.cast.get("lines", {}).get(line["id"], {}).get(lang, {})
            say = ov.get("say") or line[lang]
            if role.get("engine") == "crowd":
                for j, mem in enumerate(role["members"]):
                    if str(mem.get("engine", "qwen")).startswith("qwen"):
                        ins = " ".join(x for x in ("", mem.get("instruct", role.get("instruct", ""))) if x)
                        keep.add((V.QWEN_MODEL, mem.get("voice", ""), ins, lang, say, mem.get("seed", j)))
                continue
            if not str(role.get("engine")).startswith("qwen"):
                continue
            design = role["engine"] == "qwen_design"
            takes = int(ov.get("takes", role.get("takes", 1)))
            m = re.search(r"take (\d+) of", note)
            k = int(m.group(1)) if m else 0
            direction = st.cast.get("lines", {}).get(line["id"], {}).get("m" if lang == "zh" else "m_en") or line.get("dir", "")
            lov = {"instruct": direction, **ov}
            for ph in ov.get("phrases") or [{"text": say}]:
                pov = {**lov, **{x: ph[x] for x in ("instruct",) if x in ph}}
                ins = " ".join(x for x in ((role.get("design", "") if design else ""), role.get("instruct", ""),
                                           pov.get("instruct", "")) if x)
                seed = (lov.get("seed", 0) + k) if takes > 1 else lov.get("seed")
                keep.add((V.QWEN_DESIGN if design else V.QWEN_MODEL, None if design else role.get("voice", ""), ins, lang,
                          ph["text"], seed))
    return {os.path.join(V.TAKE_CACHE, "qwen_" + hashlib.sha1(json.dumps(list(t)).encode()).hexdigest()[:16] + ".wav")
            for t in keep}


def prune():
    """Delete the raw Qwen takes this pack's runs made (listed in prodigal_takes.json; the cache is shared with other
    packs, nothing else is touched) that are not behind a clip now in the pack."""
    st = V.Story(SID)
    keep = kept_cache_files(st)
    missing = [f for f in keep if not os.path.exists(f)]
    n = b = 0
    for f in list(_CACHE_LOG):
        if f not in keep:
            if os.path.exists(f):
                b += os.path.getsize(f); os.remove(f); n += 1
            del _CACHE_LOG[f]
        else:
            _CACHE_LOG[f] = True
    _save_cache_log()
    print(f"deleted {n} rejected takes ({b / 1e6:.0f} MB); {len(keep) - len(missing)} kept takes stay cached"
          + (f"; {len(missing)} kept takes not found in the cache (key mismatch?)" if missing else ""))


# robust pitch for the f0Hz pin: role `f0Ceil` = pitch ceiling for the median (the 600 Hz ceiling of voice.measure
# doubles an excited or creaky male voice: the son's pr_20 measured 343 Hz at 600 and 177 Hz at 300)
_adj = V._extras().score_adjust


def score_adjust(role, ov, m, wav=None):
    ceil = ov.get("f0Ceil", role.get("f0Ceil"))
    if ceil and wav:
        import numpy as np, parselmouth
        f = parselmouth.Sound(wav).to_pitch_ac(time_step=0.01, pitch_floor=60, pitch_ceiling=float(ceil)).selected_array["frequency"]
        f = f[f > 0]
        if len(f):
            m["f0MedianHz600"] = m.get("f0MedianHz")
            m["f0MedianHz"] = round(float(np.median(f)), 1)
            print(f"   robust F0 {m['f0MedianHz']:.0f} Hz")
    pen = _adj(role, ov, m, wav)
    # `mfccAvoid` (role): [{who, ref, min, weight}] = keep this voice away from another voice's timbre centroid (the
    # father from Moses, the brother from the son); a take closer than `min` loses `weight` points per unit
    for av in role.get("mfccAvoid", []):
        if wav:
            d = E.timbre_dist(wav, av["ref"])
            pen -= float(av.get("weight", 0.15)) * max(0.0, float(av["min"]) - d)
            print(f"   distance from {av['who']} {d:.1f}")
    return pen


V._extras().score_adjust = score_adjust

# A clip whose energy above 10 kHz makes inter-sample overs (the father's "Oh..." in en pr_03: sample peak held at
# -2.1 dBFS by the limiter, true peak -1.2 dBTP) cannot pass voice.normalise's check. Only then, roll the source off
# above 10 kHz (a 4th-order low-pass; nothing a child hears in a voice) and level it again with the same chain;
# every other clip is levelled exactly as voice.py does it.
_normalise = V.normalise


def normalise(src, wav, mp3, chain):
    _normalise(src, wav, mp3, chain)
    lu, pk = V.loudness(wav)
    if pk > V.TP:
        soft = src[:-4] + "_lp.wav"
        V.ffmpeg("-i", src, "-af", "lowpass=f=10000:p=2,lowpass=f=10000:p=2", "-c:a", "pcm_f32le", soft)
        _normalise(soft, wav, mp3, chain)
        print(f"   true peak {pk:.1f} dBTP: rolled off above 10 kHz and re-levelled -> LUFS, dBTP {V.loudness(wav)}")


V.normalise = normalise


V.render_line = render_line


def save_takes(st):
    p = os.path.join(st.out, "takes.json")
    old = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    for lang, d in TAKES.items():
        for lid, rec in d.items():
            f = st.wav(lang, lid)
            rec["sec"] = round(V.duration(f), 2) if os.path.exists(f) else None
            old.setdefault(lang, {})[lid] = rec
    for lang in old:
        old[lang] = dict(sorted(old[lang].items()))
    json.dump(old, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


# -------------------------------------------------------------------------------------------------------- audition
def audition(role_id, lang, lids, seeds, design_idx=None):
    import tempfile
    st = V.Story(SID)
    lines = {l["id"]: l for l in st.tl["lines"]}
    role = dict(st.cast["cast"][lang][role_id])
    if design_idx is not None:
        role.update(st.cast.get("designs", {}).get(f"{lang}.{role_id}", [])[design_idx])
    out = os.path.join(V.TAKE_CACHE, "audition")              # outside the repo; scratch
    os.makedirs(out, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        for lid in lids:
            line = lines[lid]
            lc = st.cast.get("lines", {}).get(lid, {})
            ov = {"instruct": lc.get("m" if lang == "zh" else "m_en") or line.get("dir", ""), **lc.get(lang, {})}
            for sd in seeds:
                raw = os.path.join(tmp, f"{lid}_{sd}." + ("wav" if role.get("engine", "").startswith("qwen") else "mp3"))
                for attempt in range(4):
                    try:
                        V.speak(ov.get("say") or line[lang], role, ov, lang, raw, seed=sd)
                        break
                    except Exception as e:  # Metal contention with another session: retry
                        print("   retry:", str(e)[:120]); import time; time.sleep(20)
                w = os.path.join(out, f"{lang}_{role_id}_{design_idx}_{lid}_{sd}.wav")
                V.ffmpeg("-i", raw, "-af", f"{V.TRIM},{V.FX[role.get('fx', 'plain')]},{V.PAD}", "-ac", "1", w)
                m = V.measure(w, line[lang], lang, ov.get("asrIgnore"))
                X = V._extras()
                print(f"{role_id} {lang} d{design_idx} {lid} seed {sd}: F0 {m['f0MedianHz']:.0f} Hz  sd {m['f0SdSemitones']:.2f}"
                      f"  HNR {X.hnr_db(w):.1f}  err {m['errorRate']:.2f}  {m['sec']:.1f}s  {m['asr']}")
                print("   mfcc", [round(x, 2) for x in E.mfcc_mean(w)], flush=True)


# ---------------------------------------------------------------------------------------------------------- timbre
OTHERS = {  # male voices of the other packs (story, role) -> line ids are read from their timelines
    "moses": ("exodus", "moses"), "pharaoh": ("exodus", "pharaoh"), "god": ("exodus", "god"),
    "boaz": ("ruth", "boaz"), "king(esther)": ("esther", "king"), "haman": ("esther", "haman"),
    "daniel": ("daniel", "daniel"), "king(daniel)": ("daniel", "king"),
}


def _centroid(files):
    import numpy as np
    vs = [np.array(E.mfcc_mean(f)) for f in files]
    c = np.mean(vs, axis=0)
    return c, max(float(np.linalg.norm(v - c)) for v in vs), vs


def _role_files(sid, role, lang):
    tl = json.load(open(os.path.join(ROOT, "assets", sid, "timeline.json"), encoding="utf-8"))
    fs = [os.path.join(ROOT, "assets", sid, "audio", "voice", lang, f"{l['id']}.wav") for l in tl["lines"]
          if (l.get("voice") or l["who"]) == role]
    return [f for f in fs if os.path.exists(f)]


def timbre(lang):
    import numpy as np
    st = V.Story(SID)
    roles = [r for r, v in st.cast["cast"][lang].items() if v.get("engine") != "crowd"]
    cs, res = {}, {"lang": lang, "spread": {}, "between": {}, "perLine": {}, "others": {}}
    for r in roles:
        fs = _role_files(SID, r, lang)
        if not fs:
            continue
        c, spread, vs = _centroid(fs)
        cs[r] = c
        res["spread"][r] = round(spread, 1)
        res["perLine"][r] = {os.path.basename(f)[:-4]: round(float(np.linalg.norm(v - c)), 1) for f, v in zip(fs, vs)}
        print(f"{lang} {r:9s} {len(fs):2d} lines, spread {spread:6.1f}  " +
              " ".join(f"{k}:{v}" for k, v in res["perLine"][r].items()))
    for i, a in enumerate(cs):
        for b in list(cs)[i + 1:]:
            d = round(float(np.linalg.norm(cs[a] - cs[b])), 1)
            res["between"][f"{a}-{b}"] = d
            print(f"{lang} {a} <-> {b}: {d}")
    for name, (sid, role) in OTHERS.items():
        fs = _role_files(sid, role, lang)
        if not fs:
            continue
        c, spread, _ = _centroid(fs)
        for r in ("father", "son", "brother"):
            if r in cs:
                d = round(float(np.linalg.norm(cs[r] - c)), 1)
                res["others"][f"{r}-{name}"] = d
                print(f"{lang} {r} <-> {name} ({sid}, spread {spread:.0f}): {d}")
    p = os.path.join(st.out, "timbre.json")
    old = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    old[lang] = res
    json.dump(old, open(p, "w", encoding="utf-8"), indent=1, ensure_ascii=False)


if __name__ == "__main__":
    E.SID = SID
    cmd = sys.argv[1] if len(sys.argv) >= 2 else ""
    lang = sys.argv[sys.argv.index("--lang") + 1] if "--lang" in sys.argv else "zh"
    if cmd == "preview":
        E.preview(lang)
    elif cmd == "timbre":
        timbre(lang)
    elif cmd == "prune":
        prune()
    elif cmd == "audition":
        args = [a for a in sys.argv[2:] if not a.startswith("--")]
        seeds = [int(x) for x in sys.argv[sys.argv.index("--seeds") + 1].split(",")] if "--seeds" in sys.argv else [0]
        di = int(sys.argv[sys.argv.index("--design") + 1]) if "--design" in sys.argv else None
        args = [a for a in args if a not in (",".join(map(str, seeds)), str(di))]
        audition(args[0], args[1], args[2:], seeds, di)
    elif cmd == "gen":
        sys.argv = [os.path.join(HERE, "voice.py"), SID, *sys.argv[1:]]
        st_holder = {}
        _orig_gen = V.cmd_gen

        def cmd_gen(st, a):
            st_holder["st"] = st
            try:
                return _orig_gen(st, a)
            finally:
                save_takes(st)
        V.cmd_gen = cmd_gen
        V.main()
    else:
        sys.exit(__doc__)
