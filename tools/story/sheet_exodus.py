"""Exodus colouring sheet: runs the shared tools/story/make_sheet.py for story `exodus` without changing it.

make_sheet.py looks the story up in assets/stories.json (Integration adds Exodus there when the pack is wired in) and
has one textured "story scene" per pack in STORY_SCENE. This wrapper supplies both for Exodus in its own process, so
the shared tool (and Esther / Ruth / Daniel output) stays untouched.

  python3 tools/story/sheet_exodus.py                                                  sheet + checks.json + print/
  blender -b --factory-startup --python tools/story/sheet_exodus.py -- render          textured renders
Same STORY_OUT_ROOT / STORY_WORK overrides as make_sheet.py.
"""
import json, os, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_sheet as ms                                          # noqa: E402

SID = "exodus"
# S11 on the dry path: Moses and Miriam between the walls' footprints, Pharaoh on the west beach
ms.STORY_SCENE.setdefault(SID, ("textured_sea", {"moses": (0.30, 0.07, 0.0, 90), "miriam": (0.27, 0.11, 0.0, 70),
                                                 "pharaoh": (0.12, 0.03, 0.0, 60)},
                                (-0.05, 0.45, 0.95), (0.22, 0.08, -0.05), 40, (1280, 720)))


def setup():
    try:
        ms.setup(SID)
    except StopIteration:                                        # not in assets/stories.json yet
        d = json.load(open(ms.ROOT / "assets" / SID / "design.json"))
        ms.STORY = {"id": SID, "set": d["set"]["root"], "cast": ["moses", "pharaoh", "miriam"],
                    "sheets": ["%s-A4" % SID]}


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    setup()
    if argv[:1] == ["render"]:
        ms.render()
    else:
        ms.build()
