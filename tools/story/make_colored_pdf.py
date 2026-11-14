#!/usr/bin/env python3
"""Coloured sample PDFs: print/<sheet>-colored.pdf for every book, next to the blank print/<sheet>.pdf.

The book page offers both files to save / share / print (docs/LIBRARY.md "Sheet actions"); Editor/SheetPdfSetup.cs
bundles them. The page is the full coloured A4 image at 100 % (1240 x 1754 px at 150 dpi = 210 x 297 mm), written
the same way as the blank PDF (tools/story/make_sheet.py), so it prints at true size and the corner markers land
where the blank sheet's do. Both are checked here: the page size against A4 and the image against print/<sheet>.png.

Source image, first that exists:
  print/<sheet>-colored.png             a hand-kept coloured print (david-goliath: the bright print)
  assets/<id>/sheet/demo-sheet.png      the demo colouring on the page (tools/story/make_sheet.py, make_dg_sheet.py)
  web/assets/demo-sheet.png             the angel only (tools/make_template.py)
Books: the angel, every story in assets/stories.json (sheet = sheets[0]) and any other assets/<id>/sheet/ folder
(sheet = <id>-A4). A book with no coloured image is skipped and named.
Usage: python3 tools/story/make_colored_pdf.py [id ...]
"""
import json, os, sys
from PIL import Image
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DPI = 150
A4_PX = (1240, 1754)             # 210 x 297 mm at 150 dpi (to the nearest pixel)
A4_PT = (595.276, 841.890)       # 210 x 297 mm in PDF points
ANGEL = ("angel", "doodlive-angel-A4")


def books():
    """[(book id, sheet name)] in shelf order; packs not in the registry yet come last."""
    out = [ANGEL]
    with open(os.path.join(ROOT, "assets/stories.json"), encoding="utf-8") as f:
        for s in json.load(f)["stories"]:
            if s.get("sheets"): out.append((s["id"], s["sheets"][0]))
    known = {b for b, _ in out}
    for d in sorted(os.listdir(os.path.join(ROOT, "assets"))):
        if d not in known and os.path.isdir(os.path.join(ROOT, "assets", d, "sheet")): out.append((d, d + "-A4"))
    return out


def source(book, sheet):
    cands = [f"print/{sheet}-colored.png", f"assets/{book}/sheet/demo-sheet.png"]
    if book == ANGEL[0]: cands.append("web/assets/demo-sheet.png")
    return next((c for c in cands if os.path.exists(os.path.join(ROOT, c))), None)


def markers(img):
    """Bounding box of the black corner markers' pixels in each page corner (a 12 % box), for the blank comparison."""
    g = np.asarray(img.convert("L")); h, w = g.shape; bw, bh = int(w * 0.12), int(h * 0.12); out = []
    for y0, x0 in ((0, 0), (0, w - bw), (h - bh, 0), (h - bh, w - bw)):
        ys, xs = np.nonzero(g[y0:y0 + bh, x0:x0 + bw] < 60)
        out.append(None if len(ys) < 50 else (x0 + xs.min(), y0 + ys.min(), x0 + xs.max(), y0 + ys.max()))
    return out


def pdf_page_pt(path):
    """MediaBox of page 1 in points, read from the file PIL wrote (no PDF library needed)."""
    import re
    m = re.search(rb"/MediaBox\s*\[\s*([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s*\]", open(path, "rb").read())
    x0, y0, x1, y1 = (float(v) for v in m.groups())
    return x1 - x0, y1 - y0


def make(book, sheet):
    src = source(book, sheet)
    if not src: print(f"SKIP {book}: no coloured A4 image (assets/{book}/sheet/demo-sheet.png)"); return False
    img = Image.open(os.path.join(ROOT, src)).convert("RGB")
    if img.size != A4_PX: print(f"SKIP {book}: {src} is {img.size[0]}x{img.size[1]}, not A4 at {DPI} dpi {A4_PX}"); return False
    out = os.path.join(ROOT, f"print/{sheet}-colored.pdf")
    img.save(out, resolution=DPI, quality=90)
    w, h = pdf_page_pt(out)
    if abs(w - A4_PT[0]) > 0.5 or abs(h - A4_PT[1]) > 0.5: raise SystemExit(f"{out}: page {w} x {h} pt is not A4")
    note = "no blank PNG to compare"
    blank = os.path.join(ROOT, f"print/{sheet}.png")
    if os.path.exists(blank):
        a, b = markers(Image.open(blank)), markers(img)
        worst = max((abs(p - q) for m, n in zip(a, b) if m and n for p, q in zip(m, n)), default=0)
        if any(m is None or n is None for m, n in zip(a, b)) or worst > 2:
            raise SystemExit(f"{out}: corner markers differ from {blank}: blank {a}, coloured {b}")
        note = f"4 markers within {worst} px of the blank"
    print(f"{book}: {src} -> print/{sheet}-colored.pdf  {w * 25.4 / 72:.1f} x {h * 25.4 / 72:.1f} mm, {os.path.getsize(out) // 1024} KB, {note}")
    return True


def main():
    all_books = books(); want = sys.argv[1:]
    unknown = [w for w in want if w not in {b for b, _ in all_books}]
    if unknown: raise SystemExit(f"unknown book id: {', '.join(unknown)} (known: {', '.join(b for b, _ in all_books)})")
    missing = [b for b, s in all_books if (not want or b in want) and not make(b, s)]
    if missing: print(f"no coloured PDF for: {', '.join(missing)}")


if __name__ == "__main__":
    main()
