"""Saul Sees the Light! colouring sheet: tools/story/make_sheet.py, unchanged, with the pack-specific bits added from outside
(so the shared tool and every other story's output stay untouched).

What this adds (the same three things as tools/story/sheet_daniel.py):
  * a stand-in registry entry while `assets/stories.json` (Integration's file) has no "saul" yet; once it has one,
    the registry entry is used as is
  * the story scene for the textured renders (`textured_house`: Saul on the mat in Judas's house, Ananias beside
    him, Barnabas on Straight Street)
  * part-anchored pieces print as detail lines: a (part, region) the Characters role anchors at part level
    (`regions_characters.json partAnchors`) is one fixed texel in 3D, so on paper it becomes detail line art inside
    its neighbour (make_sheet's own `anchoredTo` mechanism, fed a patched copy of the cast inputs)
  * copied from tools/story/sheet_risen.py (docs/saul/CONTRACT.md §1: "only if make_sheet.py cannot do it as is": it cannot
    until Integration adds the registry entry)
  * `signature`: the title-band distinctness check of tools/make_sheet_signatures.py for this sheet against every
    other sheet, without writing Integration's unity/Assets/DoodLive/Resources/sheet_signatures.json
  * `title-search`: draws candidate title bands (box / gap / cy) on a blank page and scores them against every other
    sheet's band, to pick values for design.json sheet.title

Run from the repo root:
  python3 tools/story/sheet_saul.py                       sheet + checks.json + print/saul-A4.*
  python3 tools/story/sheet_saul.py signature             title band vs every other sheet (NCC, a true match ~0.9)
  python3 tools/story/sheet_saul.py title-search          best title box / gap / cy candidates
  blender -b --factory-startup --python-exit-code 1 --python tools/story/sheet_saul.py -- render     textured_*.png
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_sheet as ms                                   # noqa: E402

SID = "saul"
ms.STORY_SCENE.setdefault(SID, (
    "textured_house", {"saul": (-0.15, -0.44, 0.0, 0), "ananias": (-0.06, -0.40, 0.0, -50),
                       "barnabas": (-0.30, -0.16, 0.0, 30)},
    (-0.10, 0.45, 0.60), (-0.17, 0.14, -0.38), 42, (1280, 720)))


def setup():
    try:
        ms.setup(SID)
    except StopIteration:                                 # not in the registry yet
        d = json.load(open(ms.ROOT / "assets" / SID / "design.json"))
        ms.STORY = {"id": SID, "engine": "story", "title_zh": d["sheet"]["title"]["hanzi"],
                    "title_en": d["sheet"]["title"]["english"], "sheets": [f"{SID}-A4", f"{SID}-A4-demo"],
                    "cast": ["saul", "ananias", "barnabas", "judas", "priest", "tallguard", "shortguard", "peter"], "set": d["set"]["root"]}
        print("note: assets/stories.json has no 'saul' entry yet; using a stand-in entry", ms.STORY)


def build_with_part_details():
    """make_sheet.build() on a patched copy of the cast inputs (files in model/ are not touched); copied from
    tools/story/sheet_daniel.py via sheet_jonah.py"""
    import os, shutil
    model = ms.MODEL
    rc = json.load(open(model / "regions_characters.json"))
    ct = json.load(open(model / "id_characters_2x.json"))
    tmp = ms.WORK / f"{SID}_model_patched"
    shutil.rmtree(tmp, ignore_errors=True); tmp.mkdir(parents=True)
    for f in model.iterdir():
        os.symlink(f, tmp / f.name)
    n = 0
    for ch, v in rc["characters"].items():
        for key, an in (v.get("partAnchors") or {}).items():
            part, reg = key.split(".", 1)
            tgt = an["target"]
            if isinstance(tgt, list):                     # a list of candidates (Characters role): take the first
                print(f"note: {ch}.{key} anchor target is a list {tgt}; using {tgt[0]}")
                tgt = tgt[0]
            tch, treg = tgt.split(".", 1)
            treg = "skin" if treg == "FACE" else treg
            pseudo = f"{reg}@{part}"
            hit = [e for e in ct["ids"] if e["char"] == ch and e["part"] == part and e["region"] == reg]
            if not hit:
                continue
            for e in hit:
                e["region"] = pseudo
            base = v["regions"].get(reg, {})
            v["regions"][pseudo] = {"id": base.get("id"), "hex": base.get("hex"), "parts": [part],
                                    "anchoredTo": treg if tch == ch else f"{tch}.{treg}", "anchorUV": an["uv"],
                                    "printNote": "part anchored by the Characters role: printed as detail lines"}
            n += 1
    for name, obj in (("regions_characters.json", rc), ("id_characters_2x.json", ct)):
        (tmp / name).unlink()
        json.dump(obj, open(tmp / name, "w"), indent=1, ensure_ascii=False)
    print(f"part-anchored pieces printed as detail lines: {n}")
    ms.MODEL = tmp
    try:
        ms.build()
    finally:
        ms.MODEL = model
        shutil.rmtree(tmp, ignore_errors=True)


def _others():
    sys.path.insert(0, str(ms.ROOT / "tools"))
    import make_sheet_signatures as sg
    return sg, [s for s in sg.ANGEL + sg.story_sheets() if s[1] != SID]


def _ncc(a, b):
    import numpy as np
    a = a.astype(float) - a.mean(); b = b.astype(float) - b.mean()
    return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))


def signature():
    sg, others = _others()
    mine = (f"{SID}-A4", SID, f"assets/{SID}/sheet/reference.png")
    sigs = {n: sg.signature(p) for n, _, p in others + [mine]}
    me = sigs[mine[0]]
    rows = sorted(((_ncc(me, v), n) for n, v in sigs.items() if n != mine[0]), reverse=True)
    for v, n in rows:
        print(f"  {mine[0]} vs {n:22s} NCC {v:.3f}")
    print(f"most similar to {mine[0]}: {rows[0][1]} NCC {rows[0][0]:.3f} (a true match is ~0.9; quality bar < 0.6)")
    print("SIGNATURE", "DISTINCT" if rows[0][0] < 0.6 else "TOO SIMILAR")


def title_search():
    """score candidate title bands (no files written): the worst NCC against every other sheet, lower is better"""
    import numpy as np
    from PIL import Image
    sys.path.insert(0, str(ms.ROOT / "tools"))
    from tianzige import draw_title
    sg, others = _others()
    sigs = [(n, sg.signature(p)) for n, _, p in others]
    t = ms.SH["title"]
    x, y, w, h = sg.REGION
    res = []
    for box in range(70, 95, 2):
        for gap in range(8, 62, 4):
            n = len(t["hanzi"]); total = n * box + (n - 1) * gap
            if total > 900:
                continue
            for cy in range(96, 112, 2):
                top = cy - box // 2
                if top - 16 - box * 0.15 < 36 or top + box + 34 + 30 + 12 > 240:
                    continue
                page = Image.new("RGB", (1240, 1754), "white")
                draw_title(page, t["hanzi"], t["english"], cy=cy, box=box, gap=gap, label=t["label"], pinyin=t["pinyin"])
                g = page.convert("L").crop((x, y, x + w, y + h)).resize(sg.GRID, Image.BOX)
                a = np.asarray(g, dtype=np.uint8)
                worst = max((_ncc(a, b), nm) for nm, b in sigs)
                res.append((round(worst[0], 3), box, gap, cy, worst[1]))
    res.sort()
    for r in res[:10]:
        print("worst NCC %.3f  box %d gap %d cy %d  (closest: %s)" % r)
    cur = [r for r in res if (r[1], r[2], r[3]) == (t["box"], t["gap"], t["cy"])]
    print("current", t["box"], t["gap"], t["cy"], cur[:1])


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    setup()
    if argv[:1] == ["render"]:
        ms.render()
    elif argv[:1] == ["signature"]:
        signature()
    elif argv[:1] == ["title-search"]:
        title_search()
    else:
        build_with_part_details()
