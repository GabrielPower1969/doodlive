"""Joseph colouring sheet: runs the shared tools/story/make_sheet.py for story `joseph` without changing it.

Why a wrapper: make_sheet.py looks the story up in assets/stories.json, which only Integration writes (merge_packs.py);
until Joseph is wired in, `python3 tools/story/make_sheet.py joseph` stops with StopIteration. This file supplies a
stand-in registry entry in its own process (the real entry is used as soon as it exists), the Joseph story scene for
the textured renders, and `signature`: the title-band distinctness check of tools/make_sheet_signatures.py for this
sheet against every other sheet, without writing unity/Assets/DoodLive/Resources/sheet_signatures.json (Integration's
file). The shared tool and every other story's output stay untouched.

  python3 tools/story/sheet_joseph.py                       sheet + checks.json + print/joseph-A4.*
  python3 tools/story/sheet_joseph.py signature             title band vs every other sheet (NCC, a true match ~0.9)
  blender -b --factory-startup --python tools/story/sheet_joseph.py -- render     textured_*.png
Same STORY_OUT_ROOT / STORY_WORK overrides as make_sheet.py.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_sheet as ms                                          # noqa: E402

SID = "joseph"
# S09 the dream comes true: the brother bows before the governor by the sacks, Pharaoh at his throne
ms.STORY_SCENE.setdefault(SID, ("textured_bow", {"joseph": (0.34, 0.08, 0.0, -70), "brother": (0.22, 0.13, 0.0, 110),
                                                 "pharaoh": (0.38, -0.30, 0.0, 0), "jacob": (-0.46, -0.20, 0.0, 20)},
                                (0.02, 0.40, 0.80), (0.30, 0.10, -0.10), 42, (1280, 720)))


def setup():
    try:
        ms.setup(SID)
    except StopIteration:                                        # not in assets/stories.json yet
        d = json.load(open(ms.ROOT / "assets" / SID / "design.json"))
        ms.STORY = {"id": SID, "engine": "story", "title_zh": d["sheet"]["title"]["hanzi"],
                    "title_en": d["sheet"]["title"]["english"], "set": d["set"]["root"],
                    "cast": ["joseph", "jacob", "brother", "pharaoh"], "sheets": ["%s-A4" % SID]}
        print("note: assets/stories.json has no 'joseph' entry yet; using a stand-in entry")


def signature():
    """NCC of this sheet's title band against every other sheet's (make_sheet_signatures.py method)"""
    sys.path.insert(0, str(ms.ROOT / "tools"))
    import make_sheet_signatures as sg
    import numpy as np
    from PIL import Image
    mine_png = ms.OUT_ROOT / "assets" / SID / "sheet" / "reference.png"
    others = [s for s in sg.ANGEL + sg.story_sheets() if s[1] != SID]

    def sig(path):
        im = Image.open(path).convert("L")
        x, y, w, h = sg.REGION
        return np.asarray(im.crop((x, y, x + w, y + h)).resize(sg.GRID, Image.BOX), dtype=np.uint8)

    def ncc(a, b):
        a = a.astype(float) - a.mean(); b = b.astype(float) - b.mean()
        return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
    me = sig(mine_png)
    rows = sorted(((ncc(me, sig(ms.ROOT / p)), n) for n, _, p in others), reverse=True)
    for v, n in rows:
        print(f"  {SID}-A4 vs {n:22s} NCC {v:.3f}")
    print(f"most similar to {SID}-A4: {rows[0][1]} NCC {rows[0][0]:.3f} (a true match is ~0.9; bar < 0.6)")
    print("SIGNATURE", "DISTINCT" if rows[0][0] < 0.6 else "TOO SIMILAR")
    return rows[0][0]


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    setup()
    if argv[:1] == ["render"]:
        ms.render()
    elif argv[:1] == ["signature"]:
        signature()
    else:
        ms.build()
