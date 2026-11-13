#!/usr/bin/env python3
"""David & Goliath voice lines (zh + en) from assets/david-goliath/timeline.json.

Commands (run through tools/make_dg_voice.sh, which picks the edge-tts venv python):
  gen     [--lang zh|en|all] [--only dg_02,dg_05] [--force]   TTS every line (Microsoft neural voices via edge-tts),
                                                               post-process, then `check`. Lines marked "own" in
                                                               sources.json are skipped unless --force.
  import  DIR --lang zh|en [--only ...]                       Take <id>.wav files (e.g. the voice-record skill's
                                                               process.py output), re-normalise them to the contract
                                                               and mark them "own", then `check`.
  check                                                        Rebuild durations.json, report.json, zh.srt, en.srt and
                                                               print every line against maxSec and the next line.
  session                                                      Write the voice-record session (record/<lang>/lines.json
                                                               + record.html) so lines can be re-recorded by people.

Contract (docs/david-goliath/CONTRACT.md §7): 44.1 kHz mono 16-bit WAV + 96 kbps MP3, voice at -16 LUFS.
Text is sent to Microsoft's TTS endpoint: it must stay public Bible content, nothing private.
Exit status of `check` is 1 when any clip overruns its maxSec or the next line's start (minus GAP).
"""
import argparse, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TIMELINE = os.path.join(ROOT, "assets/david-goliath/timeline.json")
CAST = os.path.join(ROOT, "tools/dg_voice_cast.json")
OUT = os.path.join(ROOT, "assets/david-goliath/audio/voice")
SOURCES = os.path.join(OUT, "sources.json")
LANGS = ("zh", "en")
LUFS, TP = -16.0, -1.5
GAP = 0.2            # STORY.md: no two lines closer than 0.2 s
SKILL_HTML = os.path.join(ROOT, "../../.claude/skills/voice-record/assets/record.html")

TRIM = ("silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.03,areverse,"
        "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.05,areverse")
FX = {
    "plain":     "highpass=f=70",
    "bright":    "highpass=f=90,equalizer=f=4000:t=q:w=1.2:g=2",
    # Pitch (and formants) down to 0.84 with tempo kept, a little chest, a short hall. Big, not monstrous.
    "giant":     "rubberband=pitch=0.84,equalizer=f=120:t=q:w=1.0:g=3,aecho=0.8:0.55:40|75:0.22|0.12",
    "offscreen": "highpass=f=120,lowpass=f=7500,aecho=0.8:0.5:22|48:0.18|0.1",
    # Crowd: shorter room than Saul's and the decayed tail cut at -50 dB, so three staggered voices fit dg_04's 2.6 s.
    "crowd":     "highpass=f=120,lowpass=f=7000,aecho=0.8:0.5:20|40:0.2|0.1,"
                 "areverse,silenceremove=start_periods=1:start_threshold=-50dB:start_silence=0.04,areverse",
}
PAD = "adelay=30:all=1,apad=pad_dur=0.06"


def run(cmd, **kw):
    return subprocess.run(cmd, check=True, capture_output=True, text=True, **kw)


def ffmpeg(*args):
    return run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "info", *args])


def duration(f):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f]).stdout)


def loudness(f):
    """Integrated LUFS and true peak (dBTP) as measured by ebur128."""
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", f, "-af", "ebur128=peak=true", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summary = err[err.rfind("Summary:"):]
    i = float(re.search(r"I:\s+([-\d.]+) LUFS", summary).group(1))
    p = float(re.search(r"Peak:\s+([-\d.inf]+) dBFS", summary).group(1))
    return i, p


# Two level chains. TTS is flat and takes firm control. A real person (above all a child) is peaky: the firm chain
# squashed the peaks of the 2026-11-13 recording and it sounded pinched and unnatural in the app (LESSONS L50), so
# recordings get a slow, soft-knee compressor and a limiter that only catches the odd peak.
CHAIN = {
    "tts": dict(comp="acompressor=threshold=-24dB:ratio=3:attack=5:release=80", lim_attack=3, lim_release=40, lufs=LUFS),
    # -17 LUFS: one dB of headroom halves the peak limiting on a child's voice; music ducks under speech anyway
    "natural": dict(comp="acompressor=threshold=-30dB:ratio=1.8:knee=8:attack=25:release=250", lim_attack=8, lim_release=200, lufs=LUFS - 1),
}


def normalise(src, wav, mp3, chain="tts"):
    """Compression, gain to LUFS, peak limiter, 44.1 kHz mono s16 WAV, then a 96 kbps MP3 copy.
    (Two-pass linear loudnorm left short peaky clips 4-10 dB quiet because it never limits; this does.)"""
    c = CHAIN[chain]
    tmp = wav + ".pre.wav"
    ffmpeg("-i", src, "-af", f"{c['comp']},aresample=44100", "-ac", "1", "-c:a", "pcm_f32le", tmp)
    target = c["lufs"]
    gain = target - loudness(tmp)[0]
    for _ in range(3):                                  # the limiter eats a little loudness; re-aim until within 0.3 LU
        ffmpeg("-i", tmp, "-af", f"volume={gain:.2f}dB,alimiter=limit={10 ** ((TP - 0.6) / 20):.3f}:attack={c['lim_attack']}:release={c['lim_release']}:level=disabled",
               "-ac", "1", "-ar", "44100", "-c:a", "pcm_s16le", wav)
        err = target - loudness(wav)[0]
        if abs(err) <= 0.3:
            break
        gain += err
    os.remove(tmp)
    ffmpeg("-i", wav, "-ac", "1", "-b:a", "96k", mp3)


def tts(voice, rate, pitch, text, out):
    for attempt in range(3):
        try:
            run([sys.executable, "-m", "edge_tts", "--voice", voice, f"--rate={rate}", f"--pitch={pitch}",
                 "--text", text, "--write-media", out])
            if os.path.getsize(out) > 1000:
                return
        except subprocess.CalledProcessError as e:
            err = e.stderr
        else:
            err = "empty media"
    sys.exit(f"edge-tts failed for {voice}: {text!r}: {err}")


def load():
    tl = json.load(open(TIMELINE))
    cast = json.load(open(CAST))
    src = json.load(open(SOURCES)) if os.path.exists(SOURCES) else {l: {} for l in LANGS}
    return tl, cast, src


def save_sources(src):
    os.makedirs(OUT, exist_ok=True)
    json.dump(src, open(SOURCES, "w"), indent=1, ensure_ascii=False)


def render_line(line, lang, cast, tmp):
    """TTS + role chain for one line; returns a path to the pre-normalised 24 kHz mono WAV and a source note."""
    role = cast["cast"][lang][line["who"]]
    over = cast["lines"].get(line["id"], {}).get("prosody", {}).get(lang, {})
    text = line[lang]
    base = os.path.join(tmp, f"{lang}_{line['id']}")
    if "voices" in role:                                    # crowd: several voices, staggered and mixed
        parts = []
        for k, v in enumerate(role["voices"]):
            raw = f"{base}_{k}.mp3"
            tts(v["voice"], v["rate"], v["pitch"], text, raw)
            parts.append((raw, v))
        args, chains = [], []
        for k, (raw, v) in enumerate(parts):
            args += ["-i", raw]
            ms = int(v["delay"] * 1000)
            chains.append(f"[{k}:a]{TRIM},adelay={ms}:all=1,volume={v['gain']}[a{k}]")
        mix = "".join(f"[a{k}]" for k in range(len(parts)))
        graph = ";".join(chains) + f";{mix}amix=inputs={len(parts)}:duration=longest:normalize=0,{FX[role['fx']]},{PAD}[out]"
        ffmpeg(*args, "-filter_complex", graph, "-map", "[out]", "-ac", "1", f"{base}.wav")
        note = "tts:" + "+".join(v["voice"] for v in role["voices"])
    else:
        raw = f"{base}.mp3"
        tts(role["voice"], over.get("rate", role["rate"]), over.get("pitch", role["pitch"]), text, raw)
        ffmpeg("-i", raw, "-af", f"{TRIM},{FX[role['fx']]},{PAD}", "-ac", "1", f"{base}.wav")
        note = f"tts:{role['voice']}"
    return f"{base}.wav", note


def cmd_gen(a):
    tl, cast, src = load()
    langs = LANGS if a.lang == "all" else (a.lang,)
    only = set(a.only.split(",")) if a.only else None
    with tempfile.TemporaryDirectory() as tmp:
        for lang in langs:
            os.makedirs(os.path.join(OUT, lang), exist_ok=True)
            for line in tl["lines"]:
                lid = line["id"]
                if only and lid not in only:
                    continue
                if src.get(lang, {}).get(lid, "").startswith("own") and not a.force:
                    print(f"{lang} {lid}: own recording kept (use --force to replace with TTS)")
                    continue
                pre, note = render_line(line, lang, cast, tmp)
                normalise(pre, os.path.join(OUT, lang, f"{lid}.wav"), os.path.join(OUT, lang, f"{lid}.mp3"))
                src.setdefault(lang, {})[lid] = note
                print(f"{lang} {lid} {line['who']:9s} {duration(os.path.join(OUT, lang, lid + '.wav')):5.2f}s  {note}")
    save_sources(src)
    return cmd_check(a)


def cmd_import(a):
    tl, cast, src = load()
    only = set(a.only.split(",")) if a.only else None
    ids = [l["id"] for l in tl["lines"]]
    n = 0
    with tempfile.TemporaryDirectory() as tmp:
        for lid in ids:
            f = os.path.join(a.dir, f"{lid}.wav")
            if (only and lid not in only) or not os.path.exists(f):
                continue
            pre = os.path.join(tmp, f"{lid}.wav")       # trim again: a recorded take may carry room tone at the ends
            ffmpeg("-i", f, "-af", f"{TRIM},{PAD}", "-ac", "1", pre)
            normalise(pre, os.path.join(OUT, a.lang, f"{lid}.wav"), os.path.join(OUT, a.lang, f"{lid}.mp3"), chain="natural")
            src.setdefault(a.lang, {})[lid] = f"own:{os.path.basename(os.path.abspath(a.dir))}"
            n += 1
            print(f"{a.lang} {lid}: imported {f}")
    print(f"{n} clip(s) imported")
    save_sources(src)
    return cmd_check(a)


def stamp(t):
    ms = int(round(t * 1000))
    return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"


def cmd_check(a=None):
    tl, cast, src = load()
    lines = sorted(tl["lines"], key=lambda l: l["t"])
    durs, report, bad = {l: {} for l in LANGS}, {l: {} for l in LANGS}, []
    print(f"\n{'id':6s} {'who':9s} {'t':>6s} {'max':>5s} | " +
          " | ".join(f"{l} dur  slack  gap   LUFS   peak" for l in LANGS))
    for i, line in enumerate(lines):
        nxt = lines[i + 1]["t"] if i + 1 < len(lines) else tl["duration"]
        row = []
        for lang in LANGS:
            wav = os.path.join(OUT, lang, f"{line['id']}.wav")
            if not os.path.exists(wav):
                row.append(f"{lang} MISSING"); bad.append((line["id"], lang, "missing", 0)); continue
            d = round(duration(wav), 2)
            lu, pk = loudness(wav)
            slack = round(line["maxSec"] - d, 2)
            gap = round(nxt - (line["t"] + d), 2)          # time left before the next line (or the end)
            durs[lang][line["id"]] = d
            report[lang][line["id"]] = {"sec": d, "maxSec": line["maxSec"], "slackSec": slack, "gapToNextSec": gap,
                                        "lufs": lu, "peakDbfs": pk, "source": src.get(lang, {}).get(line["id"], "?")}
            flag = ""
            if slack < 0:
                flag += "!MAX"; bad.append((line["id"], lang, "maxSec", -slack))
            if gap < GAP:
                flag += "!GAP"; bad.append((line["id"], lang, "next line", round(GAP - gap, 2)))
            row.append(f"{d:5.2f} {slack:+5.2f} {gap:+5.2f} {lu:6.1f} {pk:6.1f}{flag:9s}")
        print(f"{line['id']:6s} {line['who']:9s} {line['t']:6.1f} {line['maxSec']:5.1f} | " + " | ".join(row))
    json.dump(durs, open(os.path.join(OUT, "durations.json"), "w"), indent=1)
    json.dump(report, open(os.path.join(OUT, "report.json"), "w"), indent=1, ensure_ascii=False)
    for lang in LANGS:                                      # subtitles: on with the clip, off when it ends
        out = []
        for i, line in enumerate(lines):
            if line["id"] not in durs[lang]:
                continue
            nxt = lines[i + 1]["t"] if i + 1 < len(lines) else tl["duration"]
            t1 = min(max(line["t"] + durs[lang][line["id"]], line["t"] + 1.0), nxt - 0.05)
            out.append(f"{len(out) + 1}\n{stamp(line['t'])} --> {stamp(t1)}\n{line[lang]}\n")
        open(os.path.join(OUT, f"{lang}.srt"), "w", encoding="utf-8").write("\n".join(out))
    if bad:
        print("\nOVERRUNS (fix in timeline.json or re-record; do not trim the audio):")
        for lid, lang, what, by in bad:
            print(f"  {lid} {lang}: over {what} by {by:.2f}s")
        return 1
    print("\nall clips fit maxSec and leave >= %.1fs before the next line" % GAP)
    return 0


def cmd_session(a):
    tl, cast, src = load()
    for lang in LANGS:
        d = os.path.join(OUT, "record", lang)
        os.makedirs(d, exist_ok=True)
        rows = []
        for line in tl["lines"]:
            c = cast["lines"].get(line["id"], {})
            who_zh = {"narrator": "旁白", "david": "大卫", "goliath": "歌利亚", "saul": "扫罗王", "soldiers": "士兵们"}[line["who"]]
            if lang == "zh":
                m = f"{who_zh}｜{c.get('m', '')}｜不超过 {line['maxSec']:.1f} 秒"
                dd = c.get("d", "")
            else:
                m = f"{line['who'].capitalize()} | {c.get('m_en', '')} | at most {line['maxSec']:.1f} s"
                dd = c.get("d_en", "")
            ref = line["ref"].replace("1 Samuel ", "撒母耳记上 ") if lang == "zh" else line["ref"]
            rows.append({"id": line["id"], "t": line[lang], "m": m, "d": f"{dd}（{ref}）" if lang == "zh" else f"{dd} ({ref})"})
        json.dump(rows, open(os.path.join(d, "lines.json"), "w"), indent=1, ensure_ascii=False)
        if os.path.exists(SKILL_HTML):
            shutil.copyfile(SKILL_HTML, os.path.join(d, "record.html"))
        print(f"wrote {os.path.relpath(d, ROOT)}/lines.json ({len(rows)} lines)"
              + ("" if os.path.exists(os.path.join(d, "record.html")) else "  [record.html not found: copy it from the voice-record skill]"))
    return 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen"); g.add_argument("--lang", default="all", choices=("zh", "en", "all"))
    g.add_argument("--only"); g.add_argument("--force", action="store_true")
    i = sub.add_parser("import"); i.add_argument("dir"); i.add_argument("--lang", required=True, choices=LANGS); i.add_argument("--only")
    sub.add_parser("check"); sub.add_parser("session")
    a = ap.parse_args()
    sys.exit({"gen": cmd_gen, "import": cmd_import, "check": cmd_check, "session": cmd_session}[a.cmd](a))


if __name__ == "__main__":
    main()
