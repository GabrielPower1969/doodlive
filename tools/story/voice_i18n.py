#!/usr/bin/env python3
"""Voice lines for the extra story languages (fr de ja es pt) with Qwen3-TTS VoiceDesign, run locally.

    python3 tools/story/voice_i18n.py [--stories esther,ruth] [--langs fr,de] [--takes 3] [--force] [--progress FILE]

Reads the translated lines from assets/<id>/i18n.json (written by tools/i18n/merge.py) and the voices from
tools/story/voice_i18n.json. Writes assets/<id>/audio/voice/<lang>/<line>.wav + .mp3 (same contract as voice.py:
44.1 kHz mono, -16 LUFS, true peak <= -1.5 dBTP) and assets/<id>/audio/voice/report-<lang>.json.

Each line: up to --takes takes (different seeds). A take is checked by transcribing it locally (mlx-whisper) and by its
length against the English clip; the first take that passes is kept, otherwise the one with the fewest wrong words.
A line already done with the same text and voice is skipped (sources-<lang>.json), so the script can be stopped and
re-run at any time. Arabic is not handled: Qwen3-TTS has no Arabic, the app shows Arabic subtitles only.
"""
import argparse, hashlib, json, os, re, shutil, sys, tempfile, time, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
VENV = os.path.join(ROOT, ".venv-voice/bin/python")
try:
    import mlx_audio  # noqa: F401
except ImportError:
    if os.path.exists(VENV) and os.path.realpath(VENV) != os.path.realpath(sys.executable):
        os.execv(VENV, [VENV, os.path.abspath(__file__), *sys.argv[1:]])
    sys.exit("mlx-audio not found: use the repo's .venv-voice")

sys.path.insert(0, HERE)
import voice as V          # noqa: E402  (audio helpers, FX chains, Qwen loader, whisper)
import tts_lock           # noqa: E402

CFG = json.load(open(os.path.join(HERE, "voice_i18n.json"), encoding="utf-8"))
CROWDS = {"crowd", "people", "friends", "servants", "reapers"}
ACCENT_RE = re.compile(r"\s*(Clear\s+)?(clear\s+)?[Ss]tandard (American|British) English\.?|\s*Standard American English[^.]*\.|\s*普通话标准。?")
OK_ERR = {"ja": 0.45}       # whisper writes kana as kanji and back: the character rate is noisy for Japanese
OK_ERR_DEFAULT = 0.22


def stories_in_order():
    ids = [s["id"] for s in sorted(json.load(open(f"{ROOT}/assets/stories.json", encoding="utf-8"))["stories"],
                                   key=lambda s: s.get("order", 99))]
    return [i for i in ids if os.path.exists(f"{ROOT}/assets/{i}/timeline.json")]


def role_voice(story, role):
    """(design, fx) for a role: story override, then the English cast's design, then the shared defaults."""
    over = CFG["stories"].get(story, {}).get(role)
    if over:
        return over["design"], over.get("fx", "plain")
    cast_p = f"{HERE}/cast_{story}.json"
    if os.path.exists(cast_p):
        en = json.load(open(cast_p, encoding="utf-8"))["cast"].get("en", {}).get(role, {})
        if en.get("design"):
            return ACCENT_RE.sub("", en["design"]).strip(), en.get("fx", "plain") if en.get("fx") in V.FX else "plain"
    if role in CFG["roles"]:
        r = CFG["roles"][role]
        return r["design"], r.get("fx", "plain")
    if role in CROWDS or story == "david-goliath" and role == "soldiers":
        r = CFG["roles"]["_crowd"]
        return r["design"], r["fx"]
    sys.exit(f"{story}: no voice for role {role!r}; add it to tools/story/voice_i18n.json")


def words(s, lang):
    s = unicodedata.normalize("NFKD", s.lower())
    s = "".join(c for c in s if not unicodedata.combining(c))
    if lang == "ja":
        return re.findall(r"[぀-ヿ一-鿿]", s)
    return re.findall(r"[^\W\d_]+", s)


def err_rate(ref, hyp, lang):
    r, h = words(ref, lang), words(hyp, lang)
    return V._edit(r, h) / max(1, len(r))


def transcribe(wav, lang):
    import mlx_whisper
    r = mlx_whisper.transcribe(wav, path_or_hf_repo=V.WHISPER, language=lang, condition_on_previous_text=False, verbose=None)
    return r["text"].strip()


def en_sec(story, lid):
    p = f"{ROOT}/assets/{story}/audio/voice/en/{lid}.wav"
    return V.duration(p) if os.path.exists(p) else None


def render(story, line, lang, text, design, fx, takes, tmp):
    accent = CFG["accent"][lang]
    note = (line.get("dir") or "").strip()
    instruct = f"{design} {accent}" + (f" This line: {note}" if note else "")
    ref_sec = en_sec(story, line["id"])
    best = None
    for k in range(takes):
        key = hashlib.sha1(json.dumps([V.QWEN_DESIGN, instruct, lang, text, k]).encode()).hexdigest()[:16]
        raw = os.path.join(V.TAKE_CACHE, f"qwen_i18n_{key}.wav")
        if not os.path.exists(raw):
            os.makedirs(V.TAKE_CACHE, exist_ok=True)
            V.tts_qwen(text, None, instruct, lang, raw + ".tmp.wav", seed=k, model=V.QWEN_DESIGN)
            os.replace(raw + ".tmp.wav", raw)
        shaped = os.path.join(tmp, f"{lang}_{line['id']}_t{k}.wav")
        V.ffmpeg("-i", raw, "-af", f"{V.TRIM},{V.FX.get(fx, V.FX['plain'])},{V.PAD}", "-ac", "1", shaped)
        sec = V.duration(shaped)
        hyp = transcribe(shaped, lang)
        e = err_rate(text, hyp, lang)
        too_long = ref_sec is not None and sec > 2.2 * ref_sec + 2.0      # a runaway take (babbling, repeats)
        score = e + (1.0 if too_long else 0.0)
        cand = dict(take=k, sec=round(sec, 2), err=round(e, 3), asr=hyp, file=shaped, tooLong=too_long, score=score)
        print(f"   {lang} {line['id']} take {k}: err {e:.2f} {sec:.1f}s" + (" TOO LONG" if too_long else "") + f"  {hyp[:70]}")
        if best is None or score < best["score"]:
            best = cand
        if e <= OK_ERR.get(lang, OK_ERR_DEFAULT) and not too_long:
            break
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stories", default="")
    ap.add_argument("--langs", default=",".join(CFG["langs"]))
    ap.add_argument("--takes", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--progress", default="")
    a = ap.parse_args()
    stories = [s for s in a.stories.split(",") if s] or stories_in_order()
    langs = [l for l in a.langs.split(",") if l in CFG["langs"]]
    total = sum(len(json.load(open(f"{ROOT}/assets/{s}/timeline.json", encoding="utf-8"))["lines"]) for s in stories) * len(langs)
    done = 0
    t0 = time.time()

    def progress(state, current=""):
        if not a.progress:
            return
        json.dump({"state": state, "done": done, "total": total, "current": current, "elapsed": round(time.time() - t0),
                   "updated": time.strftime("%Y-%m-%d %H:%M:%S")}, open(a.progress, "w"), ensure_ascii=False)

    for story in stories:
        tl = json.load(open(f"{ROOT}/assets/{story}/timeline.json", encoding="utf-8"))
        tr_p = f"{ROOT}/assets/{story}/i18n.json"
        if not os.path.exists(tr_p):
            print(f"{story}: no i18n.json yet, skipped"); done += len(tl["lines"]) * len(langs); continue
        tr = json.load(open(tr_p, encoding="utf-8"))
        for lang in langs:
            out = f"{ROOT}/assets/{story}/audio/voice/{lang}"
            os.makedirs(out, exist_ok=True)
            src_p = f"{ROOT}/assets/{story}/audio/voice/sources-{lang}.json"
            rep_p = f"{ROOT}/assets/{story}/audio/voice/report-{lang}.json"
            sources = json.load(open(src_p)) if os.path.exists(src_p) else {}
            report = json.load(open(rep_p)) if os.path.exists(rep_p) else {}
            with tts_lock.held(f"voice_i18n {story} {lang}"), tempfile.TemporaryDirectory() as tmp:
                for line in tl["lines"]:
                    lid = line["id"]
                    text = tr.get("lines", {}).get(lid, {}).get(lang, "").strip()
                    done += 1
                    if not text:
                        print(f"   {lang} {lid}: no translation, skipped"); continue
                    role = line.get("voice") or line.get("who") or "narrator"
                    design, fx = role_voice(story, role)
                    sig = hashlib.sha1(json.dumps([text, design, fx, a.takes]).encode()).hexdigest()[:12]
                    wav, mp3 = f"{out}/{lid}.wav", f"{out}/{lid}.mp3"
                    if not a.force and sources.get(lid, {}).get("sig") == sig and os.path.exists(wav):
                        continue
                    progress("running", f"{story} {lang} {lid}")
                    best = render(story, line, lang, text, design, fx, a.takes, tmp)
                    V.normalise(best["file"], wav, mp3, "expressive")
                    sources[lid] = {"sig": sig, "source": f"tts:qwen_design:{role}", "take": best["take"]}
                    report[lid] = {k: best[k] for k in ("take", "sec", "err", "asr", "tooLong")}
                    report[lid]["text"] = text
                    json.dump(sources, open(src_p, "w"), ensure_ascii=False, indent=1)
                    json.dump(report, open(rep_p, "w"), ensure_ascii=False, indent=1)
            bad = [k for k, v in report.items() if v["err"] > OK_ERR.get(lang, OK_ERR_DEFAULT) or v["tooLong"]]
            print(f"== {story} {lang}: {len(report)} lines, {len(bad)} to listen to: {', '.join(bad)}")
            progress("running", f"{story} {lang} done")
    progress("finished")


if __name__ == "__main__":
    main()
