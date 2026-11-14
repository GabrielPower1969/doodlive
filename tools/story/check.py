#!/usr/bin/env python3
"""Validate a story pack before a build (docs/STORY-ARCHITECTURE.md rule 6). Read-only; exit 1 on any FAIL.

  python3 tools/story/check.py <id> [<id> ...]      e.g. python3 tools/story/check.py ruth
  python3 tools/story/check.py --all                every pack in assets/stories.json with engine "story"

Checks (each line prints PASS / FAIL / WARN):
  registry   the pack is in assets/stories.json, its manifest (if any) is merged (tools/story/merge_packs.py --check)
  timeline   assets/<id>/timeline.json exists; every acting entry names a cast member
  clips      every (who, clip) the timeline plays is in assets/<id>/anim/clips.json
  fx         every timeline fx id is defined by some FxDef (`Id => "<id>"`) under unity/Assets/DoodLive
  sfx/music  every sfx id is in audio/sfx/mix.json and has a file; every music cue is in audio/music/cues.json
  lines      every line fits its slot (dur <= maxSec + 0.05) and has zh + en text
  voice      every line has a zh and an en clip (audio/voice/<lang>/<line id>.wav or .mp3)
  loudness   music cues sit within 1 LU of the contract's -20 LUFS (cues.json lufs), when measured
  models     model/<cast>.glb and anim/<cast>.glb for every cast member drawn on the sheet, set model/<set>.glb
  sheet      sheet/{reference,demo-sheet,lineart,regions}.png + regions.json + template.json; print/<id>-A4.png
"""
import glob, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
results = []


def rep(status, what, detail=""):
    results.append(status)
    print(f"  {status:4s} {what}{(': ' + detail) if detail else ''}")


def load(p):
    with open(os.path.join(ROOT, p), encoding="utf-8") as f:
        return json.load(f)


def exists(p):
    return os.path.exists(os.path.join(ROOT, p))


def fx_ids():
    ids = set()
    for p in glob.glob(os.path.join(ROOT, "unity/Assets/DoodLive/**/*.cs"), recursive=True):
        with open(p, encoding="utf-8", errors="replace") as f:
            src = f.read()
            ids |= set(re.findall(r'string\s+Id\s*=>\s*"([^"]+)"', src))
            ids |= set(re.findall(r'new\s+StoryFxAlias\(\s*"([^"]+)"', src))       # aliases (StoryFxDaniel.cs)
    return ids


def check(sid):
    print(f"== {sid}")
    reg = next((s for s in load("assets/stories.json")["stories"] if s["id"] == sid), None)
    if not reg:
        rep("FAIL", "registry", f"{sid} not in assets/stories.json"); return
    rep("PASS", "registry")
    if exists(f"assets/{sid}/manifest.json"):
        r = subprocess.run([sys.executable, os.path.join(ROOT, "tools/story/merge_packs.py"), "--check"],
                           capture_output=True, text=True)
        rep("PASS" if r.returncode == 0 else "FAIL", "manifest merged", r.stdout.strip().replace("\n", "; "))
    else:
        rep("WARN", "manifest", f"assets/{sid}/manifest.json missing (pack still edits shared files by hand)")

    tlp = f"assets/{sid}/timeline.json"
    if not exists(tlp):
        rep("FAIL", "timeline", tlp + " missing"); return
    tl = load(tlp)
    cast = set(tl.get("cast", []))
    bad = [a for a in tl.get("acting", []) if a["who"] not in cast]
    rep("FAIL" if bad else "PASS", "timeline cast", f"{len(bad)} acting entries name an unknown actor" if bad else "")

    if exists(f"assets/{sid}/anim/clips.json"):
        have = {(c["char"], c["clip"]) for c in load(f"assets/{sid}/anim/clips.json")["clips"]}
        need = {(a["who"], a["clip"]) for a in tl.get("acting", [])}
        miss = sorted(need - have)
        rep("FAIL" if miss else "PASS", "clips", f"missing {miss}" if miss else f"{len(need)} used, all built")
    else:
        rep("FAIL", "clips", f"assets/{sid}/anim/clips.json missing")

    ids = fx_ids()
    miss = sorted({f["id"] for f in tl.get("fx", [])} - ids)
    rep("FAIL" if miss else "PASS", "fx", f"no FxDef for {miss}" if miss else f"{len(tl.get('fx', []))} cues")

    audio = f"assets/{sid}/audio"
    if exists(f"{audio}/sfx/mix.json"):
        mix = load(f"{audio}/sfx/mix.json")
        known = set(mix.get("sfx", mix).keys()) if isinstance(mix.get("sfx", mix), dict) else {s.get("id") for s in mix["sfx"]}
        need = {s["id"] for s in tl.get("sfx", [])}
        miss = sorted(i for i in need if i not in known or not (exists(f"{audio}/sfx/{i}.wav") or exists(f"{audio}/sfx/{i}.mp3")))
        rep("FAIL" if miss else "PASS", "sfx", f"missing {miss}" if miss else f"{len(need)} ids")
    else:
        rep("FAIL", "sfx", f"{audio}/sfx/mix.json missing")
    if exists(f"{audio}/music/cues.json"):
        cj = load(f"{audio}/music/cues.json")
        cues = cj.get("cues", {})
        names = set(cues) if isinstance(cues, dict) else {c.get("cue", c.get("id")) for c in cues}
        need = {m["cue"] for m in tl.get("music", [])}
        files = {os.path.splitext(os.path.basename(p))[0] for p in glob.glob(os.path.join(ROOT, audio, "music", "*.*"))}
        miss = sorted(c for c in need if c not in names and c not in files)
        rep("FAIL" if miss else "PASS", "music", f"missing {miss}" if miss else f"{len(need)} cues")
        lufs = [(k, v.get("lufs")) for k, v in (cues.items() if isinstance(cues, dict) else [])
                if isinstance(v, dict) and isinstance(v.get("lufs"), (int, float))]
        off = [(k, v) for k, v in lufs if abs(v + 20.0) > 1.0]
        if lufs:
            rep("FAIL" if off else "PASS", "loudness", f"off -20 LUFS: {off}" if off else f"{len(lufs)} cues at -20±1 LUFS")
    else:
        rep("FAIL", "music", f"{audio}/music/cues.json missing")

    lines = tl.get("lines", [])
    long_ = [l["id"] for l in lines if l.get("dur") and l.get("maxSec") and l["dur"] > l["maxSec"] + 0.05]
    notext = [l["id"] for l in lines if not (l.get("zh") and l.get("en"))]
    rep("FAIL" if long_ or notext else "PASS", "lines",
        (f"over slot {long_} " if long_ else "") + (f"no zh/en text {notext}" if notext else "") or f"{len(lines)} lines")
    for lang in ("zh", "en"):
        miss = [l["id"] for l in lines if not any(exists(f"{audio}/voice/{lang}/{l['id']}.{e}") for e in ("wav", "mp3"))]
        rep("FAIL" if miss else "PASS", f"voice {lang}", f"no clip for {miss}" if miss else "")

    paint = reg.get("paint", {})
    need = [f"assets/{sid}/model/{c}.glb" for c in reg.get("cast", []) if c not in paint]
    need += [f"assets/{sid}/anim/{c}.glb" for c in reg.get("cast", []) if c not in paint]
    if reg.get("set"):
        need.append(f"assets/{sid}/model/{reg['set']}.glb")
    miss = [p for p in need if not exists(p)]
    rep("FAIL" if miss else "PASS", "models", f"missing {miss}" if miss else f"{len(need)} GLBs")

    need = [f"assets/{sid}/sheet/{n}" for n in ("reference.png", "demo-sheet.png", "lineart.png", "regions.png",
                                                "regions.json", "template.json")] + [f"print/{sid}-A4.png"]
    miss = [p for p in need if not exists(p)]
    rep("FAIL" if miss else "PASS", "sheet", f"missing {miss}" if miss else "")


def main(argv):
    ids = argv
    if argv == ["--all"] or not argv:
        ids = [s["id"] for s in load("assets/stories.json")["stories"] if s.get("engine") == "story"]
    for sid in ids:
        check(sid)
    fails = results.count("FAIL")
    print(f"{len(results)} checks, {fails} FAIL, {results.count('WARN')} WARN")
    sys.exit(1 if fails else 0)


if __name__ == "__main__":
    main(sys.argv[1:])
