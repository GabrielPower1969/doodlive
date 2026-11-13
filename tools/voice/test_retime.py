#!/usr/bin/env python3
"""Tests for runtime re-timing (docs/VOICE-SYSTEM.md section 5). Writes nothing in the repo.

  python3 tools/voice/test_retime.py            # Python checks only
  python3 tools/voice/test_retime.py --cs       # also run the C# port (StoryRetime.cs) via tools/voice/retime_harness

1. anchors: build_timeline's anchors reproduce every baked time (base + dt == t).
2. identity: retime() with the baked durations changes nothing, bit for bit.
3. agreement: for random duration changes (0.5x-1.8x, per language), retime(baked timeline) places every line, event,
   shot and the play's end where re-running build_timeline.py with those durations does (within its 0.01 s rounding).
4. same-cursor events: an event authored after a line (incl. negative dt) moves by exactly that line's shift.
5. legacy (David & Goliath, no anchors): identity; a longer clip pushes everything after it; a shorter one changes nothing.
6. C# port (--cs): StoryRetime.InferAnchors + Core give the same numbers as retime.py (float vs double: 2 ms).
"""
import copy, importlib.util, json, os, random, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tools", "voice"))
import retime as R  # noqa: E402

spec = importlib.util.spec_from_file_location("bt", os.path.join(ROOT, "tools", "story", "build_timeline.py"))
BT = importlib.util.module_from_spec(spec); spec.loader.exec_module(BT)
KINDS = R.KINDS
FAIL = []


def check(ok, msg):
    print(("PASS " if ok else "FAIL ") + msg)
    if not ok:
        FAIL.append(msg)


def body_key(e):
    return json.dumps({k: v for k, v in e.items() if k not in ("t", "anchor")}, sort_keys=True, ensure_ascii=False)


def grouped(tl, kind):
    g = {}
    for e in tl.get(kind) or []:
        g.setdefault(body_key(e), []).append(e["t"])
    return {k: sorted(v) for k, v in g.items()}


def compare(a, b, tol):
    """Max abs difference of every time in two timelines with the same elements (matched by content, not order)."""
    worst = 0.0
    la, lb = {l["id"]: l for l in a["lines"]}, {l["id"]: l for l in b["lines"]}
    for i in la:
        worst = max(worst, abs(la[i]["t"] - lb[i]["t"]), abs(la[i]["maxSec"] - lb[i]["maxSec"]))
    for k in KINDS:
        ga, gb = grouped(a, k), grouped(b, k)
        assert ga.keys() == gb.keys(), k
        for key in ga:
            worst = max([worst] + [abs(x - y) for x, y in zip(ga[key], gb[key])])
    for sa, sb in zip(a["shots"], b["shots"]):
        worst = max(worst, abs(sa["t0"] - sb["t0"]), abs(sa["t1"] - sb["t1"]))
    worst = max(worst, abs(a["duration"] - b["duration"]))
    return worst <= tol, worst


def langs_durs(tl):
    """Durations build_timeline used, as {lang: {id: sec}} (both languages = dur, so max() = dur)."""
    return {l: {x["id"]: x["dur"] for x in tl["lines"]} for l in ("zh", "en")}


def story_tests(sid, rng):
    baked = BT.build(sid, write=False)
    # 1. anchors reproduce baked times
    end, start, worst = {}, {}, 0.0
    for l in baked["lines"]:
        a = l["anchor"]; base = end.get(a["line"], 0.0) if a["line"] else 0.0
        worst = max(worst, abs(base + a["dt"] - l["t"])); start[l["id"]] = l["t"]; end[l["id"]] = l["t"] + l["dur"]
    for k in KINDS:
        for e in baked[k]:
            a = e["anchor"]; base = end[a["line"]] if a["line"] else 0.0
            worst = max(worst, abs(max(0.0, base + a["dt"]) - e["t"]))
    check(worst <= 0.0101, f"{sid}: anchors reproduce baked times (two 0.01 s roundings) (worst {worst:.4f} s)")
    # 2. identity
    same = R.retime(baked, lambda i: next(x["dur"] for x in baked["lines"] if x["id"] == i))
    ok = all(same[k] == sorted(baked[k], key=lambda e: e["t"]) for k in KINDS) and same["lines"] == baked["lines"] \
        and same["duration"] == baked["duration"] and same["shots"] == baked["shots"]
    check(ok, f"{sid}: identity with baked durations is exact")
    # 3. agreement with a rebuild, 20 random voice sets
    worst_all = 0.0
    for trial in range(20):
        durs = {lang: {l["id"]: round(l["dur"] * rng.uniform(0.5, 1.8), 2) for l in baked["lines"]} for lang in ("zh", "en")}
        if trial % 4 == 0:   # some lines with no clip in one language: build uses the other, retime gets max of present
            for l in rng.sample(baked["lines"], 3):
                durs["en"].pop(l["id"], None)
        rebuilt = BT.build(sid, write=False, durations=durs)
        mx = {l["id"]: max(v for v in (durs["zh"].get(l["id"]), durs["en"].get(l["id"])) if v) for l in baked["lines"]}
        got = R.retime(baked, mx.get)
        ok, w = compare(got, rebuilt, 0.0151)
        worst_all = max(worst_all, w)
        if not ok:
            check(False, f"{sid}: trial {trial} retime vs rebuild differ by {w:.3f} s"); break
    else:
        check(True, f"{sid}: retime == rebuild for 20 random voice sets (worst {worst_all:.4f} s, rounding)")
    # 4. same-cursor events move with their line (incl. negative dt); prefer the line with the most negative-dt events
    neg_count = {}
    for k in KINDS:
        for e in baked[k]:
            a = e["anchor"]
            if a["line"] and a["dt"] < 0:
                neg_count[a["line"]] = neg_count.get(a["line"], 0) + 1
    lid = max(neg_count, key=neg_count.get) if neg_count else baked["lines"][len(baked["lines"]) // 2]["id"]
    d0 = next(l["dur"] for l in baked["lines"] if l["id"] == lid)
    got = R.retime(baked, lambda i: d0 + 2.0 if i == lid else None)
    gl = {l["id"]: l for l in got["lines"]}
    sh = gl[lid]["t"] - next(l["t"] for l in baked["lines"] if l["id"] == lid)
    neg = [e for k in KINDS for e in baked[k] if e["anchor"]["line"] == lid]
    gb = {k: grouped(baked, k) for k in KINDS}; gg = {k: grouped(got, k) for k in KINDS}
    post = gl[lid]["post"]
    bad = [(k, e) for k in KINDS for e in baked[k] if e["anchor"]["line"] == lid and len(gb[k][body_key(e)]) == 1
           and abs(gg[k][body_key(e)][0] - e["t"] - (sh + 2.0)) > 1e-9]
    check(not bad and len(neg) > 0, f"{sid}: {len(neg)} events authored after {lid} move by its shift + 2.0 s "
                                    f"({sum(1 for e in neg if e['anchor']['dt'] < post - 1e-9)} with negative dt)" + (f" BAD {bad[:2]}" if bad else ""))
    return baked


def legacy_tests():
    tl = json.load(open(os.path.join(ROOT, "assets", "david-goliath", "timeline.json"), encoding="utf-8"))
    same = R.retime(tl, lambda i: None)
    ok, w = compare(same, tl, 0.0)
    check(ok, "david-goliath (no anchors): identity")
    lines = sorted(tl["lines"], key=lambda l: l["t"])
    L = lines[3]
    grow = R.retime(tl, lambda i: L["maxSec"] + 1.5 if i == L["id"] else None)
    after = [l for l in grow["lines"] if l["t"] > L["t"] + 0.01]
    ok = all(abs(g["t"] - o["t"] - 1.5) < 1e-9 for g, o in zip(sorted(after, key=lambda l: l["t"]), lines[4:]))
    check(ok and abs(grow["duration"] - tl["duration"] - 1.5) < 1e-9, f"david-goliath: {L['id']} 1.5 s longer pushes every later line and the end by 1.5 s")
    shrink = R.retime(tl, lambda i: 0.5 if i == L["id"] else None)
    check(compare(shrink, tl, 0.0)[0], "david-goliath: a shorter clip keeps the hand-timed slot")
    return tl


def cs_tests(cases):
    try:
        dll = subprocess.run([os.path.join(ROOT, "tools", "voice", "retime_harness", "build.sh")], check=True,
                             capture_output=True, text=True).stdout.strip().splitlines()[-1]
    except Exception as e:
        check(False, f"C# harness build failed: {e}"); return
    for name, tl, durs in cases:
        items = [e for k in KINDS for e in tl.get(k) or []] + [{"t": s["t0"], "anchor": s.get("anchor")} for s in tl["shots"]]
        inp = {"lines": [{k: l.get(k) for k in ("id", "t", "maxSec", "dur", "anchor") if l.get(k) is not None} for l in tl["lines"]],
               "items": [{"t": e["t"], **({"anchor": e["anchor"]} if e.get("anchor") else {})} for e in items],
               "duration": tl["duration"], "durs": durs}
        if tl.get("durationAnchor"):
            inp["durationAnchor"] = tl["durationAnchor"]
        out = json.loads(subprocess.run(["dotnet", dll], input=json.dumps(inp), check=True, capture_output=True, text=True).stdout)
        # python on the same flat structure
        py = R.retime(tl, lambda i: durs.get(i))
        ref = copy.deepcopy(tl); R.infer_anchors(ref)
        start, delta = {}, {}
        pl = {l["id"]: l for l in py["lines"]}
        w = max(abs(o["t"] - pl[o["id"]]["t"]) for o in out["lines"])
        w = max(w, max(abs(o["maxSec"] - pl[o["id"]]["maxSec"]) for o in out["lines"]), abs(out["duration"] - py["duration"]))
        # items: shift each original item by the python rule
        ritems = [e for k in KINDS for e in ref.get(k) or []] + [{"t": s["t0"], "anchor": s["anchor"]} for s in ref["shots"]]
        for l in sorted(ref["lines"], key=lambda l: l["t"]):
            start[l["id"]] = pl[l["id"]]["t"] - l["t"]
            d0, _ = R.baked_dur(l); delta[l["id"]] = pl[l["id"]]["maxSec"] - l["maxSec"]
        def shift(a):
            if not a or not a.get("line") or a["line"] not in start:
                return 0.0
            return start[a["line"]] + (delta[a["line"]] if a["edge"] == "end" else 0.0)
        exp = [max(0.0, e["t"] + shift(e["anchor"])) for e in ritems]
        w = max([w] + [abs(a - b) for a, b in zip(out["items"], exp)])
        check(w < 0.002, f"C# StoryRetime == retime.py on {name} ({len(out['items'])} items, worst {w * 1000:.2f} ms)")


def main():
    rng = random.Random(20261114)
    cases = []
    for sid in ("esther", "ruth"):
        if os.path.exists(os.path.join(ROOT, "docs", sid, "storyboard", "story.py")):
            b = story_tests(sid, rng)
            cases.append((sid + " +random", b, {l["id"]: round(l["dur"] * rng.uniform(0.5, 1.8), 2) for l in b["lines"]}))
            cases.append((sid + " identity", b, {l["id"]: l["dur"] for l in b["lines"]}))
    dg = legacy_tests()
    cases.append(("david-goliath +random", dg, {l["id"]: round(l["maxSec"] * rng.uniform(0.6, 1.5), 2) for l in dg["lines"]}))
    if "--cs" in sys.argv:
        cs_tests(cases)
    print(f"\n{'ALL PASS' if not FAIL else str(len(FAIL)) + ' FAILED'}")
    sys.exit(1 if FAIL else 0)


if __name__ == "__main__":
    main()
