#!/usr/bin/env python3
"""Reuse / uniqueness metrics for story packs (how much of a pack is new code and new content).

Usage: python3 tools/story/pack_metrics.py [id ...] [--json]      (no ids: every pack with assets/<id>/timeline.json)

Definitions (all measured on the files in the repo, not estimated):
  own lines        non-blank, non-comment lines in the pack's own scripts: pipeline/<xx>_*.py, tools/story/{music,voice,sheet}_<id>.py,
                   StoryFx<Id>*.cs (new C# only)
  kit lines used   non-blank, non-comment lines of the shared parts the pack actually pulls in (story_kit parts named in
                   story_kit.include(globals(), "<part>"), music_kit when imported)
  reuse rate       kit used / (kit used + own)              "how much of what runs is shared code"
  copy rate        own lines whose normalised text (story ids, prefixes and digits blurred) also occurs in another pack's own
                   scripts or in the kit                      "own code that is really copied"
  unique rate      1 - copy rate                              "own code that exists nowhere else"
  clip reuse       clip names (without the character prefix) used by the pack's timeline that already exist in an earlier pack
  fx / sfx / music reuse   same idea for effect ids, sfx ids and music cue ids
Film minutes come from the timeline (`duration`).
"""
import glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PREFIX = {"esther": "es", "ruth": "ru", "daniel": "da", "exodus": "ex", "prodigal": "pr", "gabriel": "ga",
          "jonah": "jn", "joseph": "js", "david-goliath": "dg"}
ORDER = ["david-goliath", "esther", "ruth", "daniel", "exodus", "prodigal", "gabriel", "jonah", "joseph"]


def rd(p):
    try:
        return open(p, encoding="utf-8", errors="replace").read()
    except OSError:
        return ""


def code_lines(text, cs=False):
    out = []
    for ln in text.splitlines():
        s = ln.strip()
        if not s or s.startswith(("#", "//", '"""', "'''", "/*", "*")):
            continue
        out.append(s)
    return out


def norm(s, ids):
    for i in ids:
        s = re.sub(i, "ID", s, flags=re.I)
    return re.sub(r"\d+(\.\d+)?", "0", re.sub(r"\s+", " ", s))


def own_files(pid):
    xx = PREFIX.get(pid, pid[:2])
    fs = glob.glob(f"{ROOT}/pipeline/{xx}_*.py")
    for kind in ("music", "voice", "sheet"):
        fs += glob.glob(f"{ROOT}/tools/story/{kind}_{pid}.py")
    cap = "".join(w.capitalize() for w in re.split(r"[-_]", pid))
    fs += glob.glob(f"{ROOT}/unity/Assets/DoodLive/DavidGoliath/Fx/StoryFx{cap}*.cs")
    return sorted(fs)


def kit_files(pid):
    used, kit = [], []
    for f in own_files(pid):
        t = rd(f)
        for part in re.findall(r'story_kit\.include\(globals\(\),\s*"(\w+)"\)', t):
            kit.append(f"{ROOT}/pipeline/story_kit/{part}.py")
        if re.search(r"import music_kit|music_kit\.py", t):
            kit.append(f"{ROOT}/tools/story/music_kit.py")
    return sorted(set(kit))


def ids_of(pid):
    xx = PREFIX.get(pid, pid[:2])
    return [re.escape(pid), re.escape(pid.replace("-", "_")), rf"\b{xx}_", rf"\b{xx.upper()}_", rf"\b{xx}\b"]


def timeline(pid):
    p = f"{ROOT}/assets/{pid}/timeline.json"
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def clip_names(pid):
    t = timeline(pid)
    if not t:
        return set()
    return {a["clip"] for a in t.get("acting", [])}


def metrics(pid, all_ids):
    ids = ids_of(pid)
    own = {f: code_lines(rd(f)) for f in own_files(pid)}
    n_own = sum(len(v) for v in own.values())
    kit = {f: code_lines(rd(f)) for f in kit_files(pid)}
    n_kit = sum(len(v) for v in kit.values())
    # pool of lines from other packs and the kit
    pool = set()
    for other in all_ids:
        if other == pid:
            continue
        for f in own_files(other):
            pool |= {norm(l, ids_of(other)) for l in code_lines(rd(f))}
    for f in glob.glob(f"{ROOT}/pipeline/story_kit/*.py") + [f"{ROOT}/tools/story/music_kit.py"]:
        pool |= {norm(l, []) for l in code_lines(rd(f))}
    flat = [l for v in own.values() for l in v]
    copied = sum(1 for l in flat if norm(l, ids) in pool)
    t = timeline(pid)
    r = dict(id=pid, own_files=len(own), own_lines=n_own, kit_files=len(kit), kit_lines_used=n_kit,
             reuse_rate=round(n_kit / (n_kit + n_own), 3) if (n_kit + n_own) else None,
             copy_rate=round(copied / n_own, 3) if n_own else None,
             unique_rate=round(1 - copied / n_own, 3) if n_own else None,
             film_minutes=round(t["duration"] / 60, 2) if t else None)
    # content reuse against EARLIER packs
    me = ORDER.index(pid) if pid in ORDER else len(ORDER)
    earlier = [o for o in ORDER[:me] if o != pid]
    def reuse(key, field):
        if not t:
            return None
        mine = {e[field] for e in t.get(key, []) if e.get(field)}
        prev = set()
        for o in earlier:
            to = timeline(o)
            if to:
                prev |= {e[field] for e in to.get(key, []) if e.get(field)}
        return (len(mine & prev), len(mine))
    for name, key, field in (("fx", "fx", "id"), ("sfx", "sfx", "id"), ("music", "music", "cue")):
        v = reuse(key, field)
        r[f"{name}_reused"] = v
    cl = clip_names(pid)
    prev = set()
    for o in earlier:
        prev |= clip_names(o)
    r["clips_reused"] = (len(cl & prev), len(cl)) if cl else None
    return r


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    ids = args or [p for p in ORDER if timeline(p)]
    allp = [p for p in ORDER if timeline(p) or os.path.isdir(f"{ROOT}/assets/{p}")]
    rows = [metrics(p, allp) for p in ids]
    if "--json" in sys.argv:
        print(json.dumps(rows, ensure_ascii=False, indent=1)); return
    print(f"{'pack':14}{'own':>7}{'kit':>7}{'reuse':>7}{'copy':>7}{'uniq':>7}{'min':>6}  clips fx sfx music (reused/used)")
    for r in rows:
        f = lambda v: f"{v[0]}/{v[1]}" if v else "-"
        pct = lambda v: "-" if v is None else f"{v*100:.0f}%"
        print(f"{r['id']:14}{r['own_lines']:>7}{r['kit_lines_used']:>7}{pct(r['reuse_rate']):>7}{pct(r['copy_rate']):>7}"
              f"{pct(r['unique_rate']):>7}{r['film_minutes'] or 0:>6}  {f(r['clips_reused'])} {f(r['fx_reused'])} "
              f"{f(r['sfx_reused'])} {f(r['music_reused'])}")


if __name__ == "__main__":
    main()
