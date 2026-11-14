#!/usr/bin/env python3
"""Merge every story pack's own manifest into the shared files, so no pack edits a shared file by hand.

Each pack carries `assets/<id>/manifest.json` (docs/STORY-KIT.md §Manifests):

  {"id": "ruth",
   "registry": {...},            the pack's entry in assets/stories.json (id, engine, order, titles, sheets, cast, set ...)
   "library":  {...},            its book in assets/library.json (pinyin, blurbs, minutes, cover); "after": "<id>" places
                                 a new book on the shelf after that one (default: at the end)
   "strings":  {"dg_ruth": {"zh": "路得", "en": "Ruth"}, ...}   subtitle names etc. in tools/i18n/strings.json
   "fx":       {"class": "RuthFx", "note": "Ruth (pack #3, StoryFxRuth.cs)",     registration line in DGFxEffects.cs
                "aliases": {"steam": "anger_steam"}}   reuse any registered effect under a new id (no C# needed;
                                                       a pack that only reuses effects has no "class" and no .cs file)
  }

Every section is optional. The merge is an upsert: an entry already in a shared file is replaced in place, a new one is
added, entries that no manifest names (packs still edited by hand, the angel, UI strings) are left exactly as they are.
So packs can move onto manifests one at a time, and two sessions building two packs never touch the same file: each
edits its own manifest and runs this script (it is idempotent; run it again after a merge).

  python3 tools/story/merge_packs.py            write the shared files, then run tools/gen_i18n.py if strings changed
  python3 tools/story/merge_packs.py --check    exit 1 if any shared file is out of date (CI / check.py)
  python3 tools/story/merge_packs.py --extract <id> [--strings k1,k2]   write a manifest from the current shared files

Shared files: assets/stories.json, assets/library.json (one entry per line block, rewrapped canonically),
tools/i18n/strings.json (key order kept; new keys appended), unity/.../Fx/DGFxEffects.cs (the lines between
`// story-fx:start` and `// story-fx:end`, one per pack with an fx section, in registry order).
"""
import glob, json, os, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
STORIES = os.path.join(ROOT, "assets/stories.json")
LIBRARY = os.path.join(ROOT, "assets/library.json")
STRINGS = os.path.join(ROOT, "tools/i18n/strings.json")
FX_CS = os.path.join(ROOT, "unity/Assets/DoodLive/DavidGoliath/Fx/DGFxEffects.cs")
FX_START, FX_END = "// story-fx:start", "// story-fx:end"
WIDTH = 118


def load_json(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def manifests():
    out = []
    for p in sorted(glob.glob(os.path.join(ROOT, "assets/*/manifest.json"))):
        m = load_json(p)
        m.setdefault("id", os.path.basename(os.path.dirname(p)))
        out.append(m)
    return out


# ------------------------------------------------------------------------------------------------ canonical writers
def entry_lines(e, indent="  "):
    """One dict as a block: '{"k": v, ...}' greedily wrapped at WIDTH, continuation lines indented one more space."""
    parts = [f"{json.dumps(k, ensure_ascii=False)}: {json.dumps(v, ensure_ascii=False)}" for k, v in e.items()]
    lines, cur = [], indent + "{"
    for i, p in enumerate(parts):
        piece = p + ("}" if i == len(parts) - 1 else ",")
        sep = "" if cur.endswith("{") else " "
        if len(cur) + len(sep) + len(piece) > WIDTH and not cur.endswith("{"):
            lines.append(cur)
            cur = indent + " " + piece
        else:
            cur += sep + piece
    lines.append(cur)
    return lines


def list_file(doc, key, entries):
    blocks = [entry_lines(e) for e in entries]
    body = []
    for i, b in enumerate(blocks):
        if i < len(blocks) - 1:
            b = b[:-1] + [b[-1] + ","]
        body += b
    return "{\n" + f" \"_doc\": {json.dumps(doc, ensure_ascii=False)},\n \"{key}\": [\n" + "\n".join(body) + "\n ]\n}\n"


def strings_file(d):
    return json.dumps(d, ensure_ascii=False, indent=1) + "\n"


# ------------------------------------------------------------------------------------------------ merges
def upsert(items, new, after=None):
    for i, it in enumerate(items):
        if it.get("id") == new["id"]:
            items[i] = new
            return
    pos = len(items)
    if after:
        pos = next((i + 1 for i, it in enumerate(items) if it.get("id") == after), pos)
    items.insert(pos, new)


def merged(ms):
    """{path: new text} for every shared file."""
    out = {}
    reg = load_json(STORIES)
    stories = list(reg["stories"])
    for m in ms:
        if "registry" in m:
            e = dict(m["registry"]); e.setdefault("id", m["id"])
            upsert(stories, e)
    stories.sort(key=lambda s: s.get("order", 1e9))          # stable: equal orders keep their place
    out[STORIES] = list_file(reg["_doc"], "stories", stories)

    lib = load_json(LIBRARY)
    books = list(lib["books"])
    for m in ms:
        if "library" in m:
            e = dict(m["library"]); after = e.pop("after", None); e.setdefault("id", m["id"])
            upsert(books, e, after)
    out[LIBRARY] = list_file(lib["_doc"], "books", books)

    s = load_json(STRINGS)
    for m in ms:
        for k, v in m.get("strings", {}).items():
            s[k] = v                                          # dict keeps the position of an existing key
    out[STRINGS] = strings_file(s)

    order = {st["id"]: i for i, st in enumerate(stories)}
    fx = [m for m in ms if "fx" in m]
    fx.sort(key=lambda m: order.get(m["id"], 1e9))
    with open(FX_CS, encoding="utf-8") as f:
        cs = f.read()
    a, b = cs.find(FX_START), cs.find(FX_END)
    if a < 0 or b < 0:
        raise SystemExit(f"{FX_CS}: markers {FX_START} / {FX_END} not found")
    line_start = cs.rfind("\n", 0, a) + 1
    pad = cs[line_start:a]
    gen = ""
    for m in fx:
        f = m["fx"]
        if f.get("class"):
            gen += (f"{pad}foreach (var d in {f['class']}.Defs) if (!map.ContainsKey(d.Id)) map[d.Id] = d;"
                    f"   // {f.get('note', m['id'])}\n")
        if f.get("aliases"):                 # reuse registered effects under the pack's own ids: no new C#
            al = ", ".join(f'new StoryFxAlias({json.dumps(k)}, {json.dumps(v)})' for k, v in f["aliases"].items())
            gen += (f"{pad}foreach (var d in new FxDef[] {{ {al} }}) if (!map.ContainsKey(d.Id)) map[d.Id] = d;"
                    f"   // {m['id']}: aliases\n")
    head = cs[:cs.find("\n", a) + 1]
    tail = cs[cs.rfind("\n", 0, b) + 1:]
    out[FX_CS] = head + gen + tail
    return out


def extract(sid, string_keys):
    """Write assets/<sid>/manifest.json from what the shared files say today (one-time migration of a pack)."""
    m = {"_doc": "This pack's entries in the shared files; tools/story/merge_packs.py merges them (docs/STORY-KIT.md).",
         "id": sid}
    st = next((s for s in load_json(STORIES)["stories"] if s["id"] == sid), None)
    if st: m["registry"] = st
    books = load_json(LIBRARY)["books"]
    for i, bk in enumerate(books):
        if bk["id"] == sid:
            m["library"] = dict(bk, after=books[i - 1]["id"]) if i else dict(bk)
    if string_keys:
        s = load_json(STRINGS)
        m["strings"] = {k: s[k] for k in string_keys}
    with open(FX_CS, encoding="utf-8") as f:
        cs = f.read()
    import re
    for cls in re.findall(r"foreach \(var d in (\w+)\.Defs\)", cs):
        if cls.lower().startswith(sid.replace("-", "")[:5].lower()):
            note = re.search(rf"{cls}\.Defs\).*?//\s*(.*)", cs)
            m["fx"] = {"class": cls, "note": note.group(1).strip() if note else sid}
    p = os.path.join(ROOT, f"assets/{sid}/manifest.json")
    with open(p, "w", encoding="utf-8") as f:
        f.write(json.dumps(m, ensure_ascii=False, indent=1) + "\n")
    print("wrote", os.path.relpath(p, ROOT), "sections:", [k for k in m if not k.startswith("_") and k != "id"])


def main(argv):
    if argv[:1] == ["--extract"]:
        keys = argv[argv.index("--strings") + 1].split(",") if "--strings" in argv else []
        return extract(argv[1], keys)
    check = "--check" in argv
    new = merged(manifests())
    stale = []
    for p, text in new.items():
        with open(p, encoding="utf-8") as f:
            old = f.read()
        if old != text:
            stale.append(p)
            if not check:
                with open(p, "w", encoding="utf-8") as f:
                    f.write(text)
    for p in stale:
        print(("STALE " if check else "wrote ") + os.path.relpath(p, ROOT))
    if check:
        sys.exit(1 if stale else 0)
    if STRINGS in stale and "--no-gen" not in argv:
        subprocess.run([sys.executable, os.path.join(ROOT, "tools/gen_i18n.py")], check=True)
        print("ran tools/gen_i18n.py (then tools/make_fonts.py if the new strings use new characters)")


if __name__ == "__main__":
    main(sys.argv[1:])
