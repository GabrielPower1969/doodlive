"""Daniel colouring sheet: tools/story/make_sheet.py, unchanged, with the Daniel-specific bits added from outside
(so the shared tool and Esther's / Ruth's output are not touched while other packs edit it).

What this adds:
  * a stand-in registry entry while `assets/stories.json` (Integration's file) has no "daniel" yet; once it has one,
    the registry entry is used as is
  * the Daniel story scene for the textured renders (`textured_den`: Daniel in the den with the lions, the king at
    the opening)
  * part-anchored pieces print as detail lines: a (part, region) the Characters role anchors at part level (hands,
    lower legs, the lion's ears and forelock, the official's moustache: `regions_characters.json partAnchors`) is
    already one fixed texel in 3D, so on paper it becomes detail line art inside its neighbour (make_sheet's own
    `anchoredTo` mechanism, fed a patched copy of the cast inputs) instead of a closed shape too small to colour
  * `signature`: the title-band distinctness check of tools/make_sheet_signatures.py for this sheet against every
    other sheet, without writing unity/Assets/DoodLive/Resources/sheet_signatures.json (Integration's file)

Run from the repo root:
  python3 tools/story/sheet_daniel.py                       sheet + checks.json + print/daniel-A4.*
  python3 tools/story/sheet_daniel.py signature             title band vs every other sheet (NCC, a true match ~0.9)
  blender -b --factory-startup --python tools/story/sheet_daniel.py -- render     textured_*.png
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_sheet as ms                                   # noqa: E402

SID = "daniel"
ms.STORY_SCENE.setdefault(SID, (
    "textured_den", {"daniel": (0.36, -0.13, 0.0, -20), "lion": (0.44, -0.09, 0.0, -110),
                     "king": (0.05, 0.08, 0.0, 40), "officer": (-0.12, 0.12, 0.0, 60)},
    (0.02, 0.48, 0.62), (0.28, 0.06, -0.12), 42, (1280, 720)))


def setup():
    try:
        ms.setup(SID)
    except StopIteration:                                 # not in the registry yet: everything else is set by now
        d = json.load(open(ms.ROOT / "assets" / SID / "design.json"))
        ms.STORY = {"id": SID, "engine": "story", "title_zh": d["sheet"]["title"]["hanzi"],
                    "title_en": d["sheet"]["title"]["english"], "sheets": [f"{SID}-A4", f"{SID}-A4-demo"],
                    "cast": ["daniel", "king", "officer", "lion", "lion2"], "set": d["set"]["root"]}
        print("note: assets/stories.json has no 'daniel' entry yet; using a stand-in entry", ms.STORY)


def build_with_part_details():
    """make_sheet.build() on a patched copy of the cast inputs (files in model/ are not touched)"""
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


def signature():
    sys.path.insert(0, str(ms.ROOT / "tools"))
    import make_sheet_signatures as sg
    import numpy as np
    mine = ("daniel-A4", SID, f"assets/{SID}/sheet/reference.png")
    sheets = [s for s in sg.ANGEL + sg.story_sheets() if s[1] != SID] + [mine]

    def ncc(a, b):
        a = a.astype(float) - a.mean(); b = b.astype(float) - b.mean()
        return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
    sigs = {n: sg.signature(p) for n, _, p in sheets}
    me = sigs["daniel-A4"]
    rows = sorted(((ncc(me, v), n) for n, v in sigs.items() if n != "daniel-A4"), reverse=True)
    for v, n in rows:
        print(f"  daniel-A4 vs {n:22s} NCC {v:.3f}")
    worst_other = max((ncc(sigs[a], sigs[b]), a, b) for i, a in enumerate(sigs) for b in list(sigs)[i + 1:]
                      if a.split("-")[0] != b.split("-")[0] and "daniel-A4" not in (a, b))
    print(f"most similar to daniel-A4: {rows[0][1]} NCC {rows[0][0]:.3f}; most similar pair among the others: "
          f"{worst_other[1]} / {worst_other[2]} NCC {worst_other[0]:.3f} (a true match is ~0.9)")
    print("SIGNATURE", "DISTINCT" if rows[0][0] < 0.8 else "TOO SIMILAR")


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    setup()
    if argv[:1] == ["render"]:
        ms.render()
    elif argv[:1] == ["signature"]:
        signature()
    else:
        build_with_part_details()
