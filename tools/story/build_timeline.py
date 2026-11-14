#!/usr/bin/env python3
"""Place a story's beats on a timeline: docs/<id>/storyboard/story.py -> assets/<id>/timeline.json + STORYBOARD.md.

Lines get the time their voices really need: each line lasts the longer of its zh / en clip
(assets/<id>/audio/voice/durations.json); before the voices exist, an estimate (zh 4.2 characters/s, en 2.6 words/s)
stands in, and `maxSec` in the output is that duration, so the voice check (tools/story/voice.py check) and the
director both read the same numbers. Usage: python3 tools/story/build_timeline.py <id> [--estimate]

Retime anchors (docs/VOICE-SYSTEM.md): every line, event and shot also carries `anchor` = {line, edge, dt}, the cursor
segment it was authored in: `line` = the last line before it in story.py ("" = the start of the play), `edge` = "end"
(that line's voice end) or "origin", `dt` = its offset from there (includes the line's `post`, any pauses, the event's
own dt, the next line's `pre`). Lines also carry `dur` (the voice length the play was timed to) and `pre` / `post`;
the top level carries `durationAnchor`. The app (StoryRetime.cs) and tools/voice/retime.py move every element by the
shift of its anchor when an installed clip is longer or shorter than `dur`, so a new voice never needs a rebuild.
Only keys are added: every older field and every absolute `t` is unchanged.
"""
import json, math, os, re, sys, types

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class Ev(dict):
    pass


def _ev(kind, **kw):
    e = Ev(kw); e["_kind"] = kind; return e


def shot(id, title_zh, title_en, cam_type, target, dist=1.0, height=0.3, yawDeg=0.0, desc=""):
    return _ev("shot", id=id, title_zh=title_zh, title_en=title_en, desc=desc,
               camera={"type": cam_type, "target": target, "dist": dist, "height": height, "yawDeg": yawDeg})


def line(id, who, zh, en, ref, dir="", pre=0.25, post=0.35):
    return _ev("line", id=id, who=who, zh=zh, en=en, ref=ref, dir=dir, pre=pre, post=post)


def act(who, clip, to=None, y=None, face=None, blend=0.25, dt=0.0):
    e = _ev("act", who=who, clip=clip, blend=blend, dt=dt)
    if to is not None: e["to"] = [float(to[0]), float(to[1])]
    if y is not None: e["y"] = float(y)
    if face is not None: e["face"] = face
    return e


def fx(id, at, dur=1.0, dt=0.0, to=None):
    e = _ev("fx", id=id, at=at, dur=dur, dt=dt)
    if to: e["to"] = to
    return e
def sfx(id, dt=0.0): return _ev("sfx", id=id, dt=dt)
def music(cue, dt=0.0): return _ev("music", cue=cue, dt=dt)
def prop(node, show, dt=0.0): return _ev("prop", node=node, show=bool(show), dt=dt)
def pause(sec): return _ev("pause", sec=float(sec))


def estimate(zh, en):
    zc = len(re.sub(r"[^一-鿿]", "", zh)); ew = len(en.split())
    return max(zc / 4.2 + 0.25 * zh.count("……") + 0.15 * len(re.findall(r"[，、？！。—]", zh)), ew / 2.6) + 0.3


def _anchor(base_line, base_t, x):
    """Anchor of something at raw time x, authored in the cursor segment that starts at base_t (end of base_line's voice)."""
    return {"line": base_line or "", "edge": "end" if base_line else "origin", "dt": round(x - base_t, 4)}


def build(sid, use_estimate=False, write=True, durations=None):
    """write=False: return the timeline without writing files; durations: {lang: {line: sec}} instead of durations.json."""
    sys.modules["tools_story"] = types.SimpleNamespace(shot=shot, line=line, act=act, fx=fx, sfx=sfx, music=music,
                                                       prop=prop, pause=pause)
    src = os.path.join(ROOT, "docs", sid, "storyboard", "story.py")
    mod = types.ModuleType("story_" + sid); mod.__file__ = src
    exec(compile(open(src, encoding="utf-8").read(), src, "exec"), mod.__dict__)
    dur_path = os.path.join(ROOT, "assets", sid, "audio", "voice", "durations.json")
    durs = json.load(open(dur_path)) if os.path.exists(dur_path) and not use_estimate else {}
    if durations is not None:
        durs = durations
    base_line, base_t = "", 0.0          # retime anchor: the cursor segment we are in (docs/VOICE-SYSTEM.md)
    shot_anchors = []
    t = 0.0; shots, acting, lines, fxs, sfxs, mus, props = [], [], [], [], [], [], []
    measured = 0
    for e in mod.SEQUENCE:
        k = e["_kind"]
        if k == "shot":
            if shots: shots[-1]["t1"] = round(t, 2)
            s = {kk: e[kk] for kk in ("id", "title_zh", "title_en", "camera", "desc")}; s["t0"] = round(t, 2); shots.append(s)
            shot_anchors.append(_anchor(base_line, base_t, t))
        elif k == "line":
            got = [durs.get(l, {}).get(e["id"]) for l in ("zh", "en")]
            got = [g for g in got if g]
            d = max(got) if got else estimate(e["zh"], e["en"]); measured += bool(got)
            t += e["pre"]
            lines.append({"id": e["id"], "t": round(t, 2), "who": e["who"], "voice": e["who"], "maxSec": round(d + 0.05, 2),
                          "ref": e["ref"], "zh": e["zh"], "en": e["en"], "dir": e["dir"],
                          "dur": round(d, 4), "pre": e["pre"], "post": e["post"], "anchor": _anchor(base_line, base_t, t)})
            t += d
            base_line, base_t = e["id"], t
            t += e["post"]
        elif k == "pause":
            t += e["sec"]
        else:
            at = round(max(0.0, t + e.get("dt", 0.0)), 2)
            body = {kk: v for kk, v in e.items() if kk not in ("_kind", "dt")}
            {"act": acting, "fx": fxs, "sfx": sfxs, "music": mus, "prop": props}[k].append(
                {"t": at, **body, "anchor": _anchor(base_line, base_t, t + e.get("dt", 0.0))})
    shots[-1]["t1"] = round(t, 2)
    for s, a in zip(shots, shot_anchors):
        s["anchor"] = a
    for L in (acting, fxs, sfxs, mus, props): L.sort(key=lambda x: x["t"])
    tl = {"version": 1, "story": sid, "cast": mod.CAST, "set": mod.SET, "duration": round(t, 2), "fps": 30,
          "shots": shots, "acting": acting, "lines": lines, "fx": fxs, "sfx": sfxs, "music": mus, "props": props,
          "requestedClips": [], "timedFrom": "voices" if measured == len(lines) else f"estimate ({measured}/{len(lines)} voiced)",
          "durationAnchor": _anchor(base_line, base_t, t), "retime": 1}
    # checks: lines never overlap, every cue starts inside the play
    for a, b in zip(lines, lines[1:]):
        assert a["t"] + a["maxSec"] <= b["t"] + 1e-6, f"{a['id']} runs into {b['id']}"
    if not write:
        return tl
    out = os.path.join(ROOT, "assets", sid, "timeline.json"); os.makedirs(os.path.dirname(out), exist_ok=True)
    json.dump(tl, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    md = [f"# {sid} — storyboard (generated by tools/story/build_timeline.py; edit docs/{sid}/storyboard/story.py)", "",
          f"Duration {tl['duration']} s, timed from {tl['timedFrom']}.", "", "| Shot | Time | Title | Camera | What happens |",
          "|---|---|---|---|---|"]
    for s in shots:
        c = s["camera"]; md.append(f"| {s['id']} | {s['t0']:.1f}–{s['t1']:.1f} | {s['title_zh']} / {s['title_en']} | {c['type']} {c['target']} | {s['desc']} |")
    md += ["", "| Line | Time | Who | zh | en | Delivery |", "|---|---|---|---|---|---|"]
    for l in lines:
        md.append(f"| {l['id']} | {l['t']:.1f} (+{l['maxSec']:.1f}) | {l['who']} | {l['zh']} | {l['en']} | {l['dir']} |")
    open(os.path.join(ROOT, "docs", sid, "STORYBOARD.md"), "w", encoding="utf-8").write("\n".join(md) + "\n")
    print(f"{sid}: {len(shots)} shots, {len(lines)} lines, {len(acting)} acting, {tl['duration']} s ({tl['timedFrom']}) -> {os.path.relpath(out, ROOT)}")
    warn_short_walks(sid, tl)
    return tl


def warn_short_walks(sid, tl):
    """StoryDirector stops a walk where it is when the same actor's next beat starts, and plays a locomotion clip at
    most 1.6x its clips.json naturalSpeed. Warn when a walk cannot reach its mark in time: the actor would stop short
    and may stand inside someone else (Esther S09/S10, 2026-11-14)."""
    try:
        clips = json.load(open(os.path.join(ROOT, "assets", sid, "anim", "clips.json"), encoding="utf-8"))["clips"]
    except (OSError, KeyError, ValueError):
        return
    speed = {c.get("action"): c["naturalSpeed"] for c in clips if c.get("naturalSpeed")}
    pos, rows = {}, tl["acting"]
    for i, a in enumerate(rows):
        if "to" not in a:
            continue
        p0 = pos.get(a["who"], tuple(a["to"])); p1 = tuple(a["to"]); pos[a["who"]] = p1
        v = speed.get(f"{a['who']}_{a['clip']}", 0)
        d = math.dist(p0, p1)
        if a["t"] <= 0.01 or d < 1e-4 or not v:
            continue
        nxt = next((b["t"] for b in rows[i + 1:] if b["who"] == a["who"]), tl["duration"])
        need = d / v / 1.6
        if need > (nxt - a["t"]) + 0.3:
            print(f"  WARNING {sid}: {a['who']} {a['clip']} at {a['t']:.2f}s needs {need:.1f}s to reach {list(p1)} "
                  f"but the next beat comes after {nxt - a['t']:.1f}s; it stops short (move the next beat later)")


if __name__ == "__main__":
    build(sys.argv[1], "--estimate" in sys.argv)
