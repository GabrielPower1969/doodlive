#!/usr/bin/env python3
"""Title-band signatures of every printable sheet -> unity/Assets/DoodLive/Resources/sheet_signatures.json.

The app finds a sheet by its 4 corner markers (Scripts/Vision/MarkerDetector.cs) and then tells which sheet it is by
the title band, which is never coloured (SheetIdentifier.cs). Run after any sheet changes (make_template.py,
make_theme_sheets.py, make_dg_sheet.py); DoodLiveSetup refuses to build when a tracked sheet has no signature.
Names = ARCore reference image names, so both detection paths report the same sheet name.
"""
import base64, json, pathlib
import numpy as np
from PIL import Image

ROOT = pathlib.Path(__file__).resolve().parents[1]
REGION = [160, 10, 920, 184]          # template px: x, y, w, h (田字格 + pinyin + English title, above the markers)
GRID = (92, 18)                       # 10 template px per cell
ANGEL = [                              # (reference name, story, source png at template size 1240 x 1754)
    ("doodlive-angel-A4", "angel", "unity/Assets/DoodLive/Tracking/doodlive-angel-A4.png"),
    ("fiery-p1", "angel", "unity/Assets/DoodLive/Tracking/fiery-p1.png"),
    ("fiery-p2", "angel", "unity/Assets/DoodLive/Tracking/fiery-p2.png"),
    ("wrath-p1", "angel", "unity/Assets/DoodLive/Tracking/wrath-p1.png"),
    ("wrath-p2", "angel", "unity/Assets/DoodLive/Tracking/wrath-p2.png"),
    ("holy-p1", "angel", "unity/Assets/DoodLive/Tracking/holy-p1.png"),
    ("holy-p2", "angel", "unity/Assets/DoodLive/Tracking/holy-p2.png"),
]


def story_sheets():
    """Every story's blank sheet from the registry (assets/stories.json): one title band per story is enough."""
    out = []
    for st in json.load(open(ROOT / "assets/stories.json", encoding="utf-8"))["stories"]:
        sid = st["id"]
        png = "print/david-goliath-A4.png" if sid == "david-goliath" else f"assets/{sid}/sheet/reference.png"
        if (ROOT / png).exists():
            out.append((st["sheets"][0], sid, png))
        else:
            print(f"warning: {sid} has no sheet yet ({png}); it cannot be scanned by its markers")
    return out


SHEETS = ANGEL + story_sheets()


def signature(png):
    im = Image.open(ROOT / png).convert("L")
    assert im.size == (1240, 1754), (png, im.size)
    x, y, w, h = REGION
    g = im.crop((x, y, x + w, y + h)).resize(GRID, Image.BOX)
    return np.asarray(g, dtype=np.uint8)


def main():
    out = []
    for name, story, png in SHEETS:
        a = signature(png)
        out.append({"name": name, "story": story, "region": REGION, "w": GRID[0], "h": GRID[1],
                    "lum": base64.b64encode(a.tobytes()).decode()})
    dst = ROOT / "unity/Assets/DoodLive/Resources/sheet_signatures.json"
    dst.write_text(json.dumps(out, indent=1) + "\n")
    # distinctness report: NCC between different stories/themes must stay well below a true match (~0.9)
    def ncc(a, b):
        a = a.astype(float) - a.mean(); b = b.astype(float) - b.mean()
        return float((a * b).sum() / np.sqrt((a * a).sum() * (b * b).sum()))
    sigs = [(n, signature(p)) for n, _, p in SHEETS]
    worst = max((ncc(a, b), n1, n2) for i, (n1, a) in enumerate(sigs) for n2, b in sigs[i + 1:]
                if n1.split("-")[0] != n2.split("-")[0])
    print(f"{len(out)} signatures -> {dst.relative_to(ROOT)}; most similar different titles: {worst[1]} / {worst[2]} NCC {worst[0]:.2f}")


if __name__ == "__main__":
    main()
