"""Build the printable colouring sheet + the app's line-art asset from source/angel-lineart.webp.

Outputs
  web/assets/lineart.png        cropped, cleaned line art (texture space of the 3D model)
  web/assets/template.json      geometry the app needs (page size, art rect, marker centres)
  web/assets/demo-colored.png   auto-coloured sheet used by the in-app "demo" button
  print/doodlive-angel-A4.png / .pdf   sheet to print (A4 @150 dpi)
"""
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "source/angel-lineart.webp"

# White page area inside the screenshot's drop shadow (measured).
CROP = (40, 42, 1168, 1426)  # 1128 x 1384

art = Image.open(SRC).convert("L").crop(CROP)
art = art.point(lambda v: 255 if v > 200 else v)          # kill light-grey noise
ImageDraw.Draw(art).rectangle((1040, 1350, 1128, 1384), fill=255)  # stray watermark
art = art.convert("RGB")
(ROOT / "web/assets").mkdir(parents=True, exist_ok=True)
art.save(ROOT / "web/assets/lineart.png")

# ---- A4 sheet with 4 solid corner markers -------------------------------------------------
PW, PH = 1240, 1754
AW = 1000
AH = round(AW * art.height / art.width)
AX, AY = (PW - AW) // 2, (PH - AH) // 2 + 20
OFF, MS = 58, 64  # marker centre offset outside the art corner, marker size
markers = [(AX - OFF, AY - OFF), (AX + AW + OFF, AY - OFF),
           (AX + AW + OFF, AY + AH + OFF), (AX - OFF, AY + AH + OFF)]  # TL TR BR BL

def sheet(art_img):
    page = Image.new("RGB", (PW, PH), "white")
    page.paste(art_img.resize((AW, AH), Image.LANCZOS), (AX, AY))
    d = ImageDraw.Draw(page)
    for cx, cy in markers:
        d.rectangle((cx - MS // 2, cy - MS // 2, cx + MS // 2, cy + MS // 2), fill="black")
    # title block: 天 使 in 田字格 + "Angel" (kids learn the characters while colouring); markers/art untouched
    import sys; sys.path.insert(0, str(ROOT / "tools")); from tianzige import draw_title
    draw_title(page, "天使", "Angel", cy=84, box=100, label="DoodLive · 涂上颜色，再用手机扫一扫")
    try:
        f = ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", 26)
        d.text((PW // 2, PH - 50), "四个黑方块要完整拍进画面 · 不要涂到黑方块上", fill=(120, 120, 120), font=f, anchor="mm")
    except OSError:
        pass
    return page

page = sheet(art)
(ROOT / "print").mkdir(exist_ok=True)
page.save(ROOT / "print/doodlive-angel-A4.png")
page.save(ROOT / "print/doodlive-angel-A4.pdf", resolution=150)

json.dump({
    "page": [PW, PH],
    "art": [AX, AY, AW, AH],
    "markers": markers,
    "markerSize": MS,
    "artPixels": [art.width, art.height],
}, open(ROOT / "web/assets/template.json", "w"), indent=1)

# ---- Demo colouring: rough crayon zones multiplied with the line art --------------------
from PIL import ImageChops, ImageFilter
layer = Image.new("RGB", art.size, "white")
d = ImageDraw.Draw(layer)
d.polygon([(300, 1384), (390, 920), (800, 920), (880, 1384)], fill=(120, 160, 235))      # skirt
d.polygon([(370, 500), (800, 500), (830, 940), (380, 940)], fill=(150, 190, 245))        # blouse
d.ellipse((395, 170, 680, 460), fill=(235, 190, 80))                                     # hair
d.ellipse((450, 230, 590, 420), fill=(250, 214, 188))                                    # face
for poly in ([(10, 20), (420, 540), (440, 640), (300, 800), (0, 700)],
             [(1128, 20), (760, 560), (750, 680), (900, 860), (1128, 700)]):
    d.polygon(poly, fill=(255, 200, 225))                                                # wings
d.polygon([(860, 1384), (980, 1384), (1080, 520), (1060, 520)], fill=(245, 195, 60))     # trumpet
d.ellipse((60, 930, 230, 1060), fill=(250, 214, 188)); d.ellipse((900, 1000, 990, 1110), fill=(250, 214, 188))
layer = layer.filter(ImageFilter.GaussianBlur(3))
demo = ImageChops.multiply(art, layer)
demo.save(ROOT / "web/assets/demo-colored.png")
sheet(demo).save(ROOT / "web/assets/demo-sheet.png")
print("ok", art.size, (AX, AY, AW, AH), markers)
