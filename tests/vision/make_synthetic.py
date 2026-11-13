#!/usr/bin/env python3
"""Synthetic camera frames for the marker detector: every sheet (blank, randomly coloured, coloured example) under a
random perspective, rotation, lighting, blur and noise on cluttered backgrounds, plus frames with no sheet.
Writes OUT/<n>.pgm (8-bit luminance) and OUT/truth.json. Usage: make_synthetic.py OUT [count]"""
import json, math, random, sys, pathlib
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(sys.argv[1]); OUT.mkdir(parents=True, exist_ok=True)
N = int(sys.argv[2]) if len(sys.argv) > 2 else 200
R = random.Random(int(sys.argv[3]) if len(sys.argv) > 3 else 7)
MARK = [(62, 225), (1178, 225), (1178, 1568), (62, 1568)]
T = "unity/Assets/DoodLive/Tracking/"
SHEETS = [("doodlive-angel-A4", T + "doodlive-angel-A4.png"), ("fiery-p1", T + "fiery-p1.png"), ("fiery-p2", T + "fiery-p2.png"),
          ("wrath-p1", T + "wrath-p1.png"), ("wrath-p2", T + "wrath-p2.png"), ("holy-p1", T + "holy-p1.png"),
          ("holy-p2", T + "holy-p2.png"), ("david-goliath-A4", "print/david-goliath-A4.png"),
          ("david-goliath-A4", "assets/david-goliath/sheet/demo-sheet.png"),
          ("esther-A4", "print/esther-A4.png"), ("esther-A4", "assets/esther/sheet/demo-sheet.png")]
pages = {}
def page(name, path):
    if path not in pages: pages[path] = Image.open(ROOT / path).convert("RGB")
    return pages[path]

def kid_colour(img, seed):
    """Colour random enclosed regions of a blank sheet with crayon colours (some dark), like a child would."""
    from scipy import ndimage
    r = random.Random(seed); a = np.asarray(img).copy(); lab, n = ndimage.label(a.min(-1) > 200)
    sizes = ndimage.sum(np.ones_like(lab), lab, range(n + 1))
    cols = [(230, 60, 50), (60, 120, 230), (250, 200, 40), (60, 170, 70), (150, 80, 200), (40, 40, 40), (240, 140, 60), (120, 70, 40)]
    big = int(np.argmax(sizes[1:])) + 1                               # the paper background stays white
    for k in range(1, n + 1):
        if k != big and sizes[k] > 150 and r.random() < 0.6:
            a[lab == k] = r.choice(cols)
    return Image.fromarray(a)

def background(w, h, r):
    bg = Image.new("RGB", (w, h), tuple(r.randrange(40, 230) for _ in range(3)))
    d = ImageDraw.Draw(bg)
    for _ in range(r.randrange(10, 60)):
        x, y, s = r.randrange(w), r.randrange(h), r.randrange(5, 120)
        col = tuple(r.randrange(0, 255) for _ in range(3))
        if r.random() < 0.2: col = (20, 20, 20)                     # dark squares = distractors
        (d.rectangle if r.random() < 0.5 else d.ellipse)((x, y, x + s, y + s * r.uniform(0.5, 1.5)), fill=col)
    return bg.filter(ImageFilter.GaussianBlur(r.uniform(0, 3)))

def coeffs(src, dst):
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A.append([u, v, 1, 0, 0, 0, -x * u, -x * v]); b.append(x)
        A.append([0, 0, 0, u, v, 1, -y * u, -y * v]); b.append(y)
    return np.linalg.solve(np.array(A, float), np.array(b, float)).tolist()

truth = []
for n in range(N):
    W, H = R.choice([(720, 1600), (1080, 2400), (1600, 720), (1080, 1920)])
    bg = background(W, H, R)
    kind = R.random()
    entry = {"file": f"{n}.pgm", "w": W, "h": H}
    if kind < 0.15:
        entry["sheet"] = None
    else:
        name, path = R.choice(SHEETS); sheet = page(name, path)
        if "-p1" in name or name == "doodlive-angel-A4" or path.startswith("print/"):
            if R.random() < 0.5:
                key = (path, n % 4)                                  # 4 cached colourings per sheet (flood fill is slow)
                if key not in pages: pages[key] = kid_colour(sheet, n % 4)
                sheet = pages[key]
        # sheet size on screen 30-90 % of the shorter side, any rotation, some tilt; all 4 markers fully in frame
        corners = [(0, 0), (1240, 0), (1240, 1754), (0, 1754)]
        while True:
            S = min(W, H) * R.uniform(0.35, 0.9); ang = R.uniform(0, 2 * math.pi); cx, cy = W * R.uniform(0.3, 0.7), H * R.uniform(0.3, 0.7)
            tilt = R.uniform(0, 0.35); tdir = R.uniform(0, 2 * math.pi)
            def proj(x, y, S=S, ang=ang, cx=cx, cy=cy, tilt=tilt, tdir=tdir):
                u, v = (x / 1240 - 0.5) * S, (y / 1754 - 0.5) * S * 1754 / 1240
                u, v = u * math.cos(ang) - v * math.sin(ang), u * math.sin(ang) + v * math.cos(ang)
                k = 1 + tilt * (u * math.cos(tdir) + v * math.sin(tdir)) / S
                return (cx + u / k, cy + v / k)
            m = max(6, S * 64 / 1240)
            if all(m <= px <= W - m and m <= py <= H - m for px, py in (proj(x, y) for x, y in MARK)):
                break
        dst = [proj(x, y) for x, y in corners]
        lit = sheet.point(lambda v: int(v * R.uniform(0.75, 1.0)))
        warped = lit.transform((W, H), Image.PERSPECTIVE, coeffs(corners, dst), Image.BILINEAR, fillcolor=(0, 0, 0))
        mask = Image.new("L", (1240, 1754), 255).transform((W, H), Image.PERSPECTIVE, coeffs(corners, dst), Image.BILINEAR)
        bg.paste(warped, (0, 0), mask)
        entry["sheet"] = name; entry["markers"] = [proj(x, y) for x, y in MARK]
    g = bg.convert("L")
    # lighting gradient, blur, noise
    grad = np.linspace(R.uniform(0.6, 1.0), R.uniform(0.6, 1.0), W)[None, :] * np.linspace(R.uniform(0.7, 1.0), R.uniform(0.7, 1.0), H)[:, None]
    g = Image.fromarray((np.asarray(g, float) * grad).clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(R.uniform(0, 1.6)))
    a = np.asarray(g, float) + np.random.default_rng(n).normal(0, R.uniform(1, 7), (H, W))
    a = a.clip(0, 255).astype(np.uint8)
    (OUT / entry["file"]).write_bytes(f"P5 {W} {H} 255\n".encode() + a.tobytes())
    truth.append(entry)
json.dump(truth, open(OUT / "truth.json", "w"), indent=0)
print(len(truth), "frames ->", OUT)
