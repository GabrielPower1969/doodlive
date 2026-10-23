#!/usr/bin/env python3
"""tools/design/icons/*.svg -> unity/Assets/DoodLive/Resources/UI/*.png (transparent, 4x for crisp IMGUI),
plus the home-screen pictures (line-art sheet, angel cut-out). Rasterised with headless Chrome so the
result matches what the web app draws from the same SVG."""
import glob, os, re, subprocess, tempfile
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = f"{ROOT}/unity/Assets/DoodLive/Resources/UI"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
os.makedirs(OUT, exist_ok=True)
tmp = tempfile.mkdtemp()
for svg in sorted(glob.glob(f"{ROOT}/tools/design/icons/*.svg")):
    name = os.path.splitext(os.path.basename(svg))[0]
    src = open(svg).read()
    vb = [float(v) for v in re.search(r'viewBox="([^"]+)"', src).group(1).split()]
    scale = 256 / max(vb[2], vb[3])
    w, h = round(vb[2] * scale), round(vb[3] * scale)
    html = f"{tmp}/{name}.html"
    open(html, "w").write(f'<html><body style="margin:0;background:transparent">{src.replace("<svg ", f"<svg width=\"{w}\" height=\"{h}\" ", 1)}</body></html>')
    png = f"{OUT}/{name}.png"
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                    f"--window-size={w},{h}", f"--screenshot={png}", f"file://{html}"], check=True, capture_output=True)
    print(name, Image.open(png).size)
for src, name, size in (("web/assets/lineart-small.webp", "home-sheet", 420), ("web/assets/angel-cutout.webp", "home-angel", 400)):
    im = Image.open(f"{ROOT}/{src}").convert("RGBA"); im.thumbnail((size, size * 2)); im.save(f"{OUT}/{name}.png"); print(name, im.size)
