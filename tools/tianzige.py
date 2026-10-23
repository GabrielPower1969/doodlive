"""田字格 title block for the colouring sheets: each Chinese character in its own practice square (red dashed
mid-lines), the English name underneath. Kids colour AND meet the characters. Shared by make_template.py and
make_theme_sheets.py. Fonts: STKaiti (regular script, the style kids learn) extracted to pipeline/fonts/kaiti.ttf.
"""
import os
from PIL import ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAI = f"{ROOT}/pipeline/fonts/kaiti.ttf"
SANS = f"{ROOT}/pipeline/fonts/hiragino-sans-gb-bold.ttf"
RED = (205, 60, 60); GREY = (120, 120, 120)

def _font(path, size):
    try: return ImageFont.truetype(path, size)
    except OSError: return ImageFont.truetype("/System/Library/Fonts/STHeiti Medium.ttc", size)

def draw_title(page, hanzi, english, cy=80, box=104, gap=18, label=None):
    """Draw `hanzi` (one 田字格 per character) centred at y=cy, `english` below. Returns the block's bottom y."""
    d = ImageDraw.Draw(page); W = page.width
    n = len(hanzi); total = n * box + (n - 1) * gap; x0 = (W - total) // 2; top = cy - box // 2
    kai = _font(KAI, int(box * 0.78))
    for i, ch in enumerate(hanzi):
        x = x0 + i * (box + gap)
        d.rectangle((x, top, x + box, top + box), outline=RED, width=3)
        for k in range(0, box, 12):                                  # dashed cross: 田
            d.line((x + k, top + box // 2, x + min(k + 6, box), top + box // 2), fill=RED, width=1)
            d.line((x + box // 2, top + k, x + box // 2, top + min(k + 6, box)), fill=RED, width=1)
        d.text((x + box // 2, top + box // 2 + box * 0.04), ch, fill=(30, 30, 30), font=kai, anchor="mm")
    ey = top + box + 34
    d.text((W // 2, ey), english, fill=(40, 40, 40), font=_font(SANS, int(box * 0.34)), anchor="mm")
    if label: d.text((W // 2, ey + 30), label, fill=GREY, font=_font(SANS, 18), anchor="mm")
    return ey + (46 if label else 22)
