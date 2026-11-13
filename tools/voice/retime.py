#!/usr/bin/env python3
"""Reference implementation of runtime re-timing (docs/VOICE-SYSTEM.md section 5).

unity/Assets/DoodLive/Story/StoryRetime.cs is a line-for-line port of `retime()`; tools/voice/test_retime.py checks
that this function places every element where re-running tools/story/build_timeline.py with the new durations would.

    python3 tools/voice/retime.py <story-id> [--lang zh|en] [--voices DIR]   # print how a voice set would re-time the play

Rule (one sentence): every element moves by the shift of its anchor; a line's shift is the shift of its own anchor,
and the shift at a line's "end" edge is that shift plus (installed duration - baked duration).
"""
import argparse, copy, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
KINDS = ("acting", "fx", "sfx", "music", "props")


def baked_dur(line):
    """Voice length the play was timed to. Old timelines (no `dur`, e.g. David & Goliath) use the whole slot maxSec."""
    d = line.get("dur") or 0
    return (float(d), False) if d > 0 else (float(line["maxSec"]), True)


def infer_anchors(tl):
    """Anchors for a timeline built before anchors existed (David & Goliath, hand-placed times). In place.
    Line i -> end of line i-1 (+gap); anything else -> the latest line that started at or before it: "start" while
    inside the line's slot (t .. t+maxSec), "end" after it; before the first line -> origin."""
    lines = sorted(tl["lines"], key=lambda l: l["t"])
    for i, l in enumerate(lines):
        if l.get("anchor", {}).get("edge"):
            continue
        if i == 0:
            l["anchor"] = {"line": "", "edge": "origin", "dt": round(l["t"], 4)}
        else:
            p = lines[i - 1]
            l["anchor"] = {"line": p["id"], "edge": "end", "dt": round(l["t"] - (p["t"] + baked_dur(p)[0]), 4)}

    def at(x):
        prev = None
        for l in lines:
            if l["t"] <= x + 1e-6:
                prev = l
            else:
                break
        if prev is None:
            return {"line": "", "edge": "origin", "dt": round(x, 4)}
        end = prev["t"] + baked_dur(prev)[0]
        if x < end - 1e-6:
            return {"line": prev["id"], "edge": "start", "dt": round(x - prev["t"], 4)}
        return {"line": prev["id"], "edge": "end", "dt": round(x - end, 4)}

    for k in KINDS:
        for e in tl.get(k) or []:
            if not e.get("anchor", {}).get("edge"):
                e["anchor"] = at(e["t"])
    for s in tl.get("shots") or []:
        if not s.get("anchor", {}).get("edge"):
            s["anchor"] = at(s["t0"])
    if not tl.get("durationAnchor", {}).get("edge"):
        tl["durationAnchor"] = at(tl["duration"])
    return tl


def retime(tl, duration_of):
    """Return a copy of timeline `tl` re-timed to the installed clips. duration_of(line_id) -> seconds, or None / <= 0
    when that line has no clip (it keeps its baked length). Identity when every duration equals the baked `dur`."""
    tl = infer_anchors(copy.deepcopy(tl))
    start, delta = {}, {}                                   # per line: shift of its start, (new - baked) duration

    def shift(a):
        if not a or not a.get("line"):
            return 0.0
        lid = a["line"]
        if lid not in start:
            return 0.0                                      # unknown line (data error): stay put
        return start[lid] + (delta[lid] if a.get("edge") == "end" else 0.0)

    for l in sorted(tl["lines"], key=lambda l: l["t"]):    # anchors only point backwards, so one pass in time order
        s = shift(l.get("anchor"))
        d0, legacy = baked_dur(l)
        d1 = duration_of(l["id"])
        d1 = d0 if d1 is None or d1 <= 0 else float(d1)
        if legacy:
            d1 = max(d1, d0)                                # hand-timed slots only grow
        start[l["id"]], delta[l["id"]] = s, d1 - d0
        l["t"] = l["t"] + s
        l["maxSec"] = l["maxSec"] + (d1 - d0)
        if not legacy:
            l["dur"] = d1
    for k in KINDS:
        for e in tl.get(k) or []:
            e["t"] = max(0.0, e["t"] + shift(e.get("anchor")))
        (tl.get(k) or []).sort(key=lambda e: e["t"])       # stable, like StoryRetime.cs
    tl["duration"] = tl["duration"] + shift(tl.get("durationAnchor"))
    shots = tl.get("shots") or []
    for s in shots:
        s["t0"] = s["t0"] + shift(s.get("anchor"))
    for i, s in enumerate(shots):
        s["t1"] = shots[i + 1]["t0"] if i + 1 < len(shots) else tl["duration"]
    tl["lines"].sort(key=lambda l: l["t"])
    return tl


def probe(f):
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", f],
                                check=True, capture_output=True, text=True).stdout)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("story"); ap.add_argument("--lang", default="zh")
    ap.add_argument("--voices", help="folder of <line>.wav/.ogg (default: assets/<id>/audio/voice/<lang>)")
    a = ap.parse_args()
    tl = json.load(open(os.path.join(ROOT, "assets", a.story, "timeline.json"), encoding="utf-8"))
    vd = a.voices or os.path.join(ROOT, "assets", a.story, "audio", "voice", a.lang)

    def dur(lid):
        for ext in (".wav", ".ogg", ".m4a", ".mp3"):
            f = os.path.join(vd, lid + ext)
            if os.path.exists(f):
                return probe(f)
        return None

    new = retime(tl, dur)
    old = {l["id"]: l for l in tl["lines"]}
    for l in new["lines"]:
        o = old[l["id"]]
        print(f"{l['id']:8s} t {o['t']:7.2f} -> {l['t']:7.2f}  slot {o['maxSec']:5.2f} -> {l['maxSec']:5.2f}")
    print(f"duration {tl['duration']:.2f} -> {new['duration']:.2f} s")


if __name__ == "__main__":
    main()
