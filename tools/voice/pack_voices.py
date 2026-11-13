#!/usr/bin/env python3
"""Portable voice packs (docs/VOICE-SYSTEM.md): one story x one language x one cast of voices, as a folder or a zip
with a voicepack.json manifest. The app installs the same zip (VoiceBank.ImportZip) and plays it without a rebuild.

Usage:  python3 tools/voice/pack_voices.py <command> ...

  export STORY --lang zh [--pack tts-default] [--src DIR] [--kind tts] [--licence ...] [--out DIR]
         Pack a story's voices (default: the repo's assets/<id>/audio/voice/<lang>/) into <out>/<story>-<lang>-<pack>.voicepack.zip.
         Durations, loudness and peaks are measured; roles come from the timeline; sources from sources.json.
  import STORY SRC --lang zh --pack family-2026 [--role king | --speaker dad[:role[:minor]] ...] [--only ...]
         [--consent-by NAME] [--minors] [--licence private-family] [--title ...] [--out DIR] [--zip]
         SRC = a folder or zip of <line-id>.wav recordings (e.g. the voice-record skill's process.py output).
         Each clip is trimmed and levelled by voice.py's gentle "natural" chain (LESSONS L50: -17 LUFS, no EQ, no
         time-stretch) into <out>/<story>/<lang>/<pack>/ with a manifest. Never writes into assets/ (use
         `tools/story/voice.py <id> import` to replace a bundled clip in the repo).
  check  PACK [--story STORY]
         Validate a pack folder or zip: manifest fields, flat file names, every file present, line ids in the
         timeline, loudness within 1.5 LU of the target, peak <= -1 dBFS, consent for family packs and children's
         voices; then print how the play re-times with it (tools/voice/retime.py).

Default --out: ~/.cache/doodlive-voicepacks (outside the repo: family recordings never go into git).
Needs ffmpeg / ffprobe. Sends nothing anywhere.
"""
import argparse, datetime, importlib.util, json, os, re, shutil, sys, tempfile, zipfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import retime as RT  # noqa: E402

FORMAT, FORMAT_VERSION, MANIFEST = "doodlive-voicepack", 1, "voicepack.json"
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
SAFE_FILE = re.compile(r"^[A-Za-z0-9_-]{1,64}\.(wav|ogg)$")
DEFAULT_OUT = os.path.expanduser("~/.cache/doodlive-voicepacks")
TARGET = {"tts": -16.0, "family": -17.0, "studio": -17.0}
RESERVED = {"mine", "bundled"}


def voice_module():
    """tools/story/voice.py as a module (its audio helpers and the natural chain); never edited from here."""
    spec = importlib.util.spec_from_file_location("story_voice", os.path.join(ROOT, "tools", "story", "voice.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m


def timeline(sid):
    return json.load(open(os.path.join(ROOT, "assets", sid, "timeline.json"), encoding="utf-8"))


def roles_of(tl):
    return {l["id"]: l.get("voice") or l["who"] for l in tl["lines"]}


def story_version(sid):
    try:
        reg = json.load(open(os.path.join(ROOT, "assets", "stories.json"), encoding="utf-8"))
        return next((s.get("version", 1) for s in reg["stories"] if s["id"] == sid), 1)
    except Exception:
        return 1


def measure(V, f):
    lu, pk = V.loudness(f)
    return round(V.duration(f), 3), round(lu, 2), round(pk, 2)


def write_zip(folder, out_zip):
    os.makedirs(os.path.dirname(out_zip), exist_ok=True)
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for name in sorted(os.listdir(folder)):
            if name == MANIFEST or SAFE_FILE.match(name):
                z.write(os.path.join(folder, name), name)
    return out_zip


# ------------------------------------------------------------------------------------------------------------ export
def cmd_export(a):
    V = voice_module()
    tl = timeline(a.story); roles = roles_of(tl)
    src = a.src or os.path.join(ROOT, "assets", a.story, "audio", "voice", a.lang)
    sources = {}
    sp = os.path.join(ROOT, "assets", a.story, "audio", "voice", "sources.json")
    if not a.src and os.path.exists(sp):
        sources = json.load(open(sp, encoding="utf-8")).get(a.lang, {})
    with tempfile.TemporaryDirectory() as tmp:
        lines = []
        for l in tl["lines"]:
            for ext in (".wav", ".ogg"):
                f = os.path.join(src, l["id"] + ext)
                if os.path.exists(f):
                    shutil.copy(f, os.path.join(tmp, l["id"] + ext))
                    sec, lu, pk = measure(V, f)
                    lines.append({"id": l["id"], "file": l["id"] + ext, "role": roles[l["id"]], "speaker": "",
                                  "source": sources.get(l["id"], "tts"), "sec": sec, "lufs": lu, "peak": pk})
                    break
            else:
                print(f"  {l['id']}: no clip in {src}")
        mf = {"format": FORMAT, "formatVersion": FORMAT_VERSION, "id": a.pack, "story": a.story, "lang": a.lang,
              "title": a.title or f"{a.story} {a.lang} {a.pack}", "kind": a.kind, "licence": a.licence,
              "created": datetime.date.today().isoformat(), "tool": "tools/voice/pack_voices.py",
              "storyVersion": story_version(a.story), "targetLufs": TARGET.get(a.kind, -17.0),
              "consent": {"by": "", "date": "", "scope": "public" if a.kind == "tts" else "device", "minors": False,
                          "parentConfirmed": False},
              "speakers": [], "lines": lines}
        json.dump(mf, open(os.path.join(tmp, MANIFEST), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        out = write_zip(tmp, os.path.join(a.out, f"{a.story}-{a.lang}-{a.pack}.voicepack.zip"))
    print(f"{len(lines)}/{len(tl['lines'])} lines -> {out}")
    return 0


# ------------------------------------------------------------------------------------------------------------ import
def parse_speakers(specs):
    out = []
    for s in specs or []:
        p = s.split(":")
        out.append({"id": p[0], "name": p[0], "role": p[1] if len(p) > 1 else "", "minor": len(p) > 2 and p[2] == "minor"})
    return out


def cmd_import(a):
    if not SAFE_ID.match(a.pack) or a.pack in RESERVED:
        sys.exit(f"pack id must match {SAFE_ID.pattern} and not be one of {sorted(RESERVED)}")
    V = voice_module()
    tl = timeline(a.story); roles = roles_of(tl)
    only = set(a.only.split(",")) if a.only else None
    speakers = parse_speakers(a.speaker)
    minors = a.minors or any(s["minor"] for s in speakers)
    if minors and not a.consent_by:
        sys.exit("a child's voice is in this pack: pass --consent-by <parent> (docs/VOICE-SYSTEM.md section 8)")
    dst = os.path.join(a.out, a.story, a.lang, a.pack)
    os.makedirs(dst, exist_ok=True)
    mp = os.path.join(dst, MANIFEST)
    mf = json.load(open(mp, encoding="utf-8")) if os.path.exists(mp) else {"lines": [], "speakers": []}
    by_id = {l["id"]: l for l in mf.get("lines", [])}
    with tempfile.TemporaryDirectory() as tmp:
        src = a.src
        if zipfile.is_zipfile(src):
            src = os.path.join(tmp, "in"); os.makedirs(src)
            with zipfile.ZipFile(a.src) as z:
                for n in z.namelist():
                    b = os.path.basename(n)
                    if SAFE_FILE.match(b):
                        open(os.path.join(src, b), "wb").write(z.read(n))
        n = 0
        for l in tl["lines"]:
            lid = l["id"]
            f = next((os.path.join(src, lid + e) for e in (".wav", ".ogg") if os.path.exists(os.path.join(src, lid + e))), None)
            if not f or (only and lid not in only):
                continue
            role = roles[lid]
            if a.role and a.role != role:
                continue
            pre = os.path.join(tmp, f"{lid}.pre.wav")
            V.ffmpeg("-i", f, "-af", f"{V.TRIM},{V.PAD}", "-ac", "1", pre)
            out = os.path.join(dst, f"{lid}.wav")
            V.normalise(pre, out, os.path.join(tmp, f"{lid}.mp3"), "natural")
            sec, lu, pk = measure(V, out)
            spk = next((s["id"] for s in speakers if s["role"] == role), speakers[0]["id"] if len(speakers) == 1 else "")
            by_id[lid] = {"id": lid, "file": f"{lid}.wav", "role": role, "speaker": spk,
                          "source": f"own:{os.path.basename(os.path.abspath(a.src))}", "sec": sec, "lufs": lu, "peak": pk}
            n += 1
            print(f"  {lid} {role:9s} {sec:5.2f}s {lu:6.1f} LUFS {pk:5.1f} dBTP")
    known = {s["id"]: s for s in mf.get("speakers", [])}
    known.update({s["id"]: s for s in speakers})
    mf.update({"format": FORMAT, "formatVersion": FORMAT_VERSION, "id": a.pack, "story": a.story, "lang": a.lang,
               "title": a.title or mf.get("title") or a.pack, "kind": "family", "licence": a.licence,
               "created": mf.get("created") or datetime.date.today().isoformat(), "tool": "tools/voice/pack_voices.py",
               "storyVersion": story_version(a.story), "targetLufs": TARGET["family"],
               "consent": {"by": a.consent_by or mf.get("consent", {}).get("by", ""),
                           "date": datetime.date.today().isoformat() if a.consent_by else mf.get("consent", {}).get("date", ""),
                           "scope": "device", "minors": minors or mf.get("consent", {}).get("minors", False),
                           "parentConfirmed": bool(a.consent_by) or mf.get("consent", {}).get("parentConfirmed", False)},
               "speakers": list(known.values()),
               "lines": [by_id[l["id"]] for l in tl["lines"] if l["id"] in by_id]})
    json.dump(mf, open(mp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{n} clip(s) -> {dst} ({len(mf['lines'])}/{len(tl['lines'])} lines in the pack)")
    if a.zip:
        print("zip:", write_zip(dst, os.path.join(a.out, f"{a.story}-{a.lang}-{a.pack}.voicepack.zip")))
    return check_pack(dst, a.story)


# ------------------------------------------------------------------------------------------------------------- check
def check_pack(path, story=None):
    V = voice_module()
    problems, warns = [], []
    with tempfile.TemporaryDirectory() as tmp:
        folder = path
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as z:
                for n in z.namelist():
                    if n != MANIFEST and not SAFE_FILE.match(n):
                        problems.append(f"unexpected entry '{n}' (flat: voicepack.json + <name>.wav/.ogg only)")
                    elif not problems:
                        open(os.path.join(tmp, n), "wb").write(z.read(n))
            folder = tmp
        mp = os.path.join(folder, MANIFEST)
        if not os.path.exists(mp):
            print("FAIL: no voicepack.json"); return 1
        mf = json.load(open(mp, encoding="utf-8"))
        if mf.get("format") != FORMAT: problems.append(f"format is not {FORMAT}")
        if mf.get("formatVersion", 0) > FORMAT_VERSION: problems.append("formatVersion newer than this tool")
        for k in ("id", "story", "lang"):
            if not SAFE_ID.match(str(mf.get(k, ""))): problems.append(f"{k} '{mf.get(k)}' is not a safe id")
        if mf.get("id") in RESERVED: problems.append(f"id '{mf['id']}' is reserved")
        if not mf.get("licence"): problems.append("no licence")
        sid = story or mf.get("story")
        tl = timeline(sid) if sid and os.path.exists(os.path.join(ROOT, "assets", sid, "timeline.json")) else None
        if story and mf.get("story") != story: problems.append(f"pack is for '{mf.get('story')}', not '{story}'")
        c = mf.get("consent") or {}
        kids = c.get("minors") or any(s.get("minor") for s in mf.get("speakers", []))
        if mf.get("kind") == "family" and not c.get("parentConfirmed"): problems.append("family pack without parentConfirmed consent")
        if kids and not c.get("parentConfirmed"): problems.append("a child's voice without parentConfirmed consent")
        if kids and c.get("scope") == "public": warns.append("a child's voice with scope 'public': only with explicit written consent")
        target = mf.get("targetLufs", -17.0)
        ids = {l["id"] for l in tl["lines"]} if tl else None
        durs = {}
        for l in mf.get("lines", []):
            f = os.path.join(folder, l.get("file", ""))
            if not SAFE_FILE.match(l.get("file", "")): problems.append(f"{l.get('id')}: bad file name '{l.get('file')}'"); continue
            if not os.path.exists(f): problems.append(f"{l['id']}: {l['file']} missing"); continue
            if ids is not None and l["id"] not in ids: warns.append(f"{l['id']}: not a line of {sid} (ignored by the app)")
            sec, lu, pk = measure(V, f)
            durs[l["id"]] = sec
            if abs(sec - l.get("sec", sec)) > 0.05: warns.append(f"{l['id']}: manifest says {l.get('sec')} s, file is {sec} s")
            if abs(lu - target) > 1.5: warns.append(f"{l['id']}: {lu:.1f} LUFS (target {target})")
            if pk > -1.0: problems.append(f"{l['id']}: peak {pk:.1f} dBTP > -1.0")
        if tl:
            missing = [l["id"] for l in tl["lines"] if l["id"] not in durs]
            if missing: warns.append(f"{len(missing)} line(s) not in this pack, they fall back: {', '.join(missing[:8])}{'...' if len(missing) > 8 else ''}")
            new = RT.retime(tl, durs.get)
            print(f"{sid}/{mf.get('lang')}/{mf.get('id')}: {len(durs)} clips; play {tl['duration']:.1f} s -> {new['duration']:.1f} s with this pack")
    for w in warns: print("  warn:", w)
    for p in problems: print("  FAIL:", p)
    print("OK" if not problems else f"{len(problems)} problem(s)")
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export"); e.add_argument("story"); e.add_argument("--lang", required=True)
    e.add_argument("--pack", default="tts-default"); e.add_argument("--src"); e.add_argument("--kind", default="tts")
    e.add_argument("--licence", default="DoodLive app content; TTS output, see docs/<id>/VOICE.md"); e.add_argument("--title")
    e.add_argument("--out", default=DEFAULT_OUT)
    i = sub.add_parser("import"); i.add_argument("story"); i.add_argument("src"); i.add_argument("--lang", required=True)
    i.add_argument("--pack", required=True); i.add_argument("--role"); i.add_argument("--only")
    i.add_argument("--speaker", action="append", help="id[:role[:minor]], repeatable")
    i.add_argument("--consent-by"); i.add_argument("--minors", action="store_true")
    i.add_argument("--licence", default="private-family"); i.add_argument("--title")
    i.add_argument("--out", default=DEFAULT_OUT); i.add_argument("--zip", action="store_true")
    c = sub.add_parser("check"); c.add_argument("pack"); c.add_argument("--story")
    a = ap.parse_args()
    if a.cmd == "check":
        sys.exit(check_pack(a.pack, a.story))
    sys.exit({"export": cmd_export, "import": cmd_import}[a.cmd](a))


if __name__ == "__main__":
    main()
