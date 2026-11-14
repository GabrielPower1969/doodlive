"""The prodigal son colouring sheet: runs the shared tools/story/make_sheet.py for story `prodigal` without changing it.

make_sheet.py looks the story up in assets/stories.json (Integration adds the prodigal son there when the pack is
wired in) and has one textured "story scene" per pack in STORY_SCENE. This wrapper supplies both in its own process, so
the shared tool (and every other story's output) stays untouched.

  python3 tools/story/sheet_prodigal.py                                                sheet + checks.json + print/
  blender -b --factory-startup --python tools/story/sheet_prodigal.py -- render        textured renders
Same STORY_OUT_ROOT / STORY_WORK overrides as make_sheet.py.
"""
import json, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import make_sheet as ms                                          # noqa: E402

SID = "prodigal"
# S09/S10 the run and the hug: the father reaches his son on the road, the brother hoes the field behind
ms.STORY_SCENE.setdefault(SID, ("textured_hug", {"father": (0.00, 0.06, 0.0, 90), "son": (0.10, 0.08, 0.0, -90),
                                                 "brother": (0.02, -0.34, 0.0, 10)},
                                (-0.30, 0.36, 0.70), (0.02, 0.10, -0.10), 40, (1280, 720)))


def setup():
    try:
        ms.setup(SID)
    except StopIteration:                                        # not in assets/stories.json yet
        d = json.load(open(ms.ROOT / "assets" / SID / "design.json"))
        ms.STORY = {"id": SID, "set": d["set"]["root"], "cast": ["son", "father", "brother"],
                    "sheets": ["%s-A4" % SID]}


if __name__ == "__main__":
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else sys.argv[1:]
    setup()
    if argv[:1] == ["render"]:
        ms.render()
    else:
        ms.build()
