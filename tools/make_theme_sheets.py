"""Generate three themed A4 colouring sheets (2 pages each) around the DoodLive angel.

  python3 tools/make_theme_sheets.py            # all three
  python3 tools/make_theme_sheets.py holy       # one theme

Outputs (print/):
  angel-fiery.pdf  angel-wrath.pdf  angel-holy.pdf     A4 @150 dpi, page 1 = line art, page 2 = coloured example
  previews/<theme>-p1.png, <theme>-p2.png

Hard constraints (the AR app depends on them):
  * web/assets/lineart.png is pasted at EXACTLY template.json["art"], the 4 solid markers are drawn at
    template.json["markers"] with size template.json["markerSize"], exactly like tools/make_template.py.
  * Decorations only live in the background: they are clipped by the angel's silhouette (plus a small gap)
    and by a keep-out zone (>= 34 px white) around each marker and around the text lines.
  * Colours come only from tools/palette.py.
Reads web/assets/* but never writes to web/ or unity/.
"""
import json
import math
import random
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFont
from scipy import ndimage as ndi

sys.path.insert(0, str(Path(__file__).resolve().parent))
from palette import COL, PALETTE  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
TPL = json.load(open(ROOT / "web/assets/template.json"))
PW, PH = TPL["page"]
AX, AY, AW, AH = TPL["art"]
MARKERS = [tuple(m) for m in TPL["markers"]]
MS = TPL["markerSize"]
FONT = "/System/Library/Fonts/STHeiti Medium.ttc"
SS = 2  # supersampling for decorations
KEEP = 36  # white margin around markers beyond the marker square (>= 30 required)
BLACK, WHITE = 0, 255


def font(size):
    return ImageFont.truetype(FONT, size)


# ------------------------------------------------------------------------------------------------
# Geometry helpers
# ------------------------------------------------------------------------------------------------
def bez(p0, p1, p2, p3, n=22):
    pts = []
    for i in range(n + 1):
        t = i / n
        a, b, c, d = (1 - t) ** 3, 3 * (1 - t) ** 2 * t, 3 * (1 - t) * t * t, t ** 3
        pts.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
    return pts


def rot(pts, a, c=(0, 0)):
    ca, sa = math.cos(a), math.sin(a)
    return [(c[0] + (x - c[0]) * ca - (y - c[1]) * sa, c[1] + (x - c[0]) * sa + (y - c[1]) * ca) for x, y in pts]


def shift(pts, dx, dy):
    return [(x + dx, y + dy) for x, y in pts]


def polar(c, a, r):
    return (c[0] + r * math.cos(a), c[1] + r * math.sin(a))


def flame(cx, by, w, h, lean=0.0):
    """Classic flame tongue: base centre (cx, by), width w, height h, tip leaning by `lean`."""
    left = bez((cx - w / 2, by), (cx - w * 0.62, by - h * 0.30), (cx - w * 0.10 + lean * 0.4, by - h * 0.62),
               (cx + lean, by - h))
    right = bez((cx + lean, by - h), (cx + w * 0.30 + lean * 0.5, by - h * 0.55), (cx + w * 0.62, by - h * 0.30),
                (cx + w / 2, by))
    return left + right[1:]


def star(c, r_out, r_in, n, a0=-math.pi / 2):
    pts = []
    for i in range(2 * n):
        r = r_out if i % 2 == 0 else r_in
        pts.append(polar(c, a0 + i * math.pi / n, r))
    return pts


def jag(poly, amp, period, seed=1):
    """Turn a polygon outline into a sawtooth outline (angry, jagged edge)."""
    rnd = random.Random(seed)
    out = []
    for i in range(len(poly)):
        p, q = poly[i], poly[(i + 1) % len(poly)]
        L = math.hypot(q[0] - p[0], q[1] - p[1])
        n = max(2, int(L / period))
        nx, ny = -(q[1] - p[1]) / L, (q[0] - p[0]) / L
        for k in range(n):
            t = k / n
            x, y = p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t
            s = amp * (0.6 + 0.8 * rnd.random())
            out.append((x + nx * s, y + ny * s))
            t2 = (k + 0.5) / n
            out.append((p[0] + (q[0] - p[0]) * t2, p[1] + (q[1] - p[1]) * t2))
    return out


# ------------------------------------------------------------------------------------------------
# Layered drawing surface: a black line layer + a colour layer, both at SS x resolution
# ------------------------------------------------------------------------------------------------
class Art:
    def __init__(self):
        self.L = Image.new("L", (PW * SS, PH * SS), WHITE)
        self.C = Image.new("RGB", (PW * SS, PH * SS), "white")
        self.dl = ImageDraw.Draw(self.L)
        self.dc = ImageDraw.Draw(self.C)

    def _s(self, pts):
        return [(x * SS, y * SS) for x, y in pts]

    def poly(self, pts, fill=None, lw=4, dots=False):
        P = self._s(pts)
        if fill is not None:
            self.dc.polygon(P, fill=COL[fill])
            self.dl.polygon(P, fill=WHITE)
        self.dl.line(P + [P[0]], fill=BLACK, width=int(lw * SS), joint="curve")
        if dots:
            r = lw * SS / 2
            for x, y in P:
                self.dl.ellipse((x - r, y - r, x + r, y + r), fill=BLACK)

    def line(self, pts, lw=4, caps=True):
        P = self._s(pts)
        self.dl.line(P, fill=BLACK, width=int(lw * SS), joint="curve")
        if caps:
            r = lw * SS / 2
            for x, y in (P[0], P[-1]):
                self.dl.ellipse((x - r, y - r, x + r, y + r), fill=BLACK)

    def circle(self, c, r, fill=None, lw=4):
        x, y = c[0] * SS, c[1] * SS
        R = r * SS
        if fill is not None:
            self.dc.ellipse((x - R, y - R, x + R, y + R), fill=COL[fill])
            self.dl.ellipse((x - R, y - R, x + R, y + R), fill=WHITE)
        self.dl.ellipse((x - R, y - R, x + R, y + R), outline=BLACK, width=int(lw * SS))

    def ellipse(self, c, rx, ry, fill=None, lw=4, rotate=0.0):
        pts = []
        for i in range(60):
            a = i * 2 * math.pi / 60
            pts.append((rx * math.cos(a), ry * math.sin(a)))
        pts = shift(rot(pts, rotate), c[0], c[1])
        self.poly(pts, fill, lw)

    def blob(self, prims, fill, lw=4):
        """Union outline of circles ('c',x,y,r) and boxes ('r',x0,y0,x1,y1): clean cloud silhouettes."""
        for k in (0, 1):
            g = 0 if k == 0 else -lw
            for p in prims:
                if p[0] == "c":
                    _, x, y, r = p
                    R = (r + g) * SS
                    box = (x * SS - R, y * SS - R, x * SS + R, y * SS + R)
                    self.dl.ellipse(box, fill=BLACK if k == 0 else WHITE)
                    if k == 1:
                        R = r * SS
                        self.dc.ellipse((x * SS - R, y * SS - R, x * SS + R, y * SS + R), fill=COL[fill])
                else:
                    _, x0, y0, x1, y1 = p
                    box = (x0 * SS - g * SS, y0 * SS - g * SS, x1 * SS + g * SS, y1 * SS + g * SS)
                    self.dl.rectangle(box, fill=BLACK if k == 0 else WHITE)
                    if k == 1:
                        self.dc.rectangle((x0 * SS, y0 * SS, x1 * SS, y1 * SS), fill=COL[fill])

    def merge(self, other, mask):
        """Paint `other` over self wherever `mask` (L, SS-size) is white."""
        self.L.paste(other.L, (0, 0), mask)
        self.C.paste(other.C, (0, 0), mask)

    def down(self):
        return (self.L.resize((PW, PH), Image.LANCZOS), self.C.resize((PW, PH), Image.LANCZOS))


def mask_poly(pts):
    m = Image.new("L", (PW * SS, PH * SS), 0)
    ImageDraw.Draw(m).polygon([(x * SS, y * SS) for x, y in pts], fill=255)
    return m


def mask_ellipse(c, rx, ry):
    m = Image.new("L", (PW * SS, PH * SS), 0)
    ImageDraw.Draw(m).ellipse(((c[0] - rx) * SS, (c[1] - ry) * SS, (c[0] + rx) * SS, (c[1] + ry) * SS), fill=255)
    return m


# ------------------------------------------------------------------------------------------------
# Angel: silhouette mask + colour zones (all derived from web/assets/lineart.png, nothing is moved)
# ------------------------------------------------------------------------------------------------
def load_angel():
    art_src = Image.open(ROOT / "web/assets/lineart.png").convert("RGB")
    art = art_src.resize((AW, AH), Image.LANCZOS)  # identical to make_template.py
    a = np.array(art.convert("L"))
    dark = a < 150
    # --- silhouette: heavy closing merges the feather strokes, background is found from seeds ---
    P = 60
    d = np.pad(dark, P)
    d[:, P:P + 3] = True
    d[:, -P - 3:-P] = True
    d[-P - 3:-P, :] = True
    seeds = [(500, 10), (30, 790), (40, 1150), (990, 1000), (990, 1220), (80, 1220), (640, 200), (330, 200),
             (950, 100), (20, 10), (980, 10)]

    def fig_for(k):
        cl = ndi.binary_closing(d, structure=np.ones((3, 3)), iterations=k)[P:-P, P:-P]
        lab, _ = ndi.label(~cl)
        ids = {lab[y, x] for x, y in seeds}
        ids.discard(0)
        return ~np.isin(lab, list(ids))

    f16, f34 = fig_for(16), fig_for(34)
    reg = np.zeros_like(f16)
    reg[100:650, 660:] = True
    fig = f16 | (f34 & reg)
    # right wing's empty upper part (open feather area) is part of the figure too
    wing_top = Image.new("L", (AW, AH), 0)
    ImageDraw.Draw(wing_top).polygon(
        [(700, 150), (760, 100), (850, 70), (970, 12), (1000, 20), (1000, 330), (810, 340), (740, 250), (710, 240)],
        fill=255)
    fig |= np.array(wing_top) > 0
    fig[:, :4] = fig[:, :4] & False  # the artificial frame used for closing is not part of the figure
    fig[:, -4:] = False
    fig[-4:, :] = False

    # --- closed regions of the line art (for flat colour zones) ---
    lab, n = ndi.label(a >= 170)
    sizes = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
    open_ids = [i + 1 for i, s in enumerate(sizes) if s > 100000]
    open_mask = np.isin(lab, open_ids)
    return art, fig, lab, open_mask


def to_page(arr_bool_or_u8, fill=0):
    out = np.full((PH, PW), fill, dtype=arr_bool_or_u8.dtype)
    out[AY:AY + AH, AX:AX + AW] = arr_bool_or_u8
    return out


# seeds (art coordinates) of closed regions, by role
SEEDS = {
    "skin": [(470, 300), (455, 296), (470, 252), (440, 440), (200, 770), (95, 930), (740, 770), (860, 890), (855, 906),
             (855, 925), (112, 940)],
    "hair": [(380, 260), (380, 365), (500, 190), (560, 300)],
    "accent": [(400, 466), (545, 468), (320, 775), (230, 650), (270, 835), (698, 830), (625, 838), (370, 890),
               (460, 835), (690, 600)],
    "rope": [(452, 890), (515, 878), (557, 893), (520, 920), (462, 944), (355, 978), (278, 1013), (255, 1075),
             (595, 875)],
    "gold": [(900, 710), (810, 1120), (850, 860)],
    "robe2": [(500, 740), (440, 760)],
}
SRC_W, SRC_H = 1128, 1384  # lineart.png size; wing outlines below are traced in these coordinates
WING_L = [(8, 22), (60, 42), (110, 70), (155, 105), (195, 150), (225, 195), (250, 240), (275, 285), (310, 330), (345, 380), (385, 425), (425, 458), (400, 490), (370, 492), (330, 520), (302, 560), (300, 600), (292, 640), (262, 672), (240, 720), (225, 760), (213, 790), (195, 790), (150, 745), (100, 690), (50, 640), (0, 602), (0, 442), (28, 420), (69, 454), (87, 492), (135, 470), (138, 435), (145, 375), (170, 335), (195, 316), (240, 305), (245, 295), (215, 238), (165, 162), (110, 102), (60, 62)]
WING_R = [(1088, 16), (998, 50), (908, 95), (858, 125), (813, 160), (783, 200), (763, 250), (733, 320), (698, 380), (658, 430), (618, 470), (668, 500), (708, 545), (753, 615), (783, 680), (790, 690), (823, 730), (868, 745), (893, 722), (943, 660), (963, 600), (998, 550), (1038, 500), (1068, 455), (1108, 420), (1128, 412), (1128, 270), (1090, 284), (1035, 319), (990, 383), (972, 453), (945, 502), (907, 557), (877, 602), (868, 575), (885, 520), (905, 470), (915, 420), (912, 370), (905, 330), (885, 290), (850, 278), (800, 296), (783, 245), (796, 215), (833, 170), (888, 130), (948, 98), (1008, 72), (1068, 30)]
SKIRT = [(310, 930), (650, 840), (665, 880), (722, 1227), (235, 1227)]


def angel_colour_layer(theme, lab, open_mask, fig):
    """Return (RGB array page-sized, bool array 'angel-coloured') for the theme's angel palette."""
    cfg = theme["angel"]
    out = np.full((AH, AW, 3), 255, np.uint8)
    painted = np.zeros((AH, AW), bool)
    # closed components -> role colour (default: robe)
    role_of = {}
    for role, pts in SEEDS.items():
        for x, y in pts:
            l = lab[y, x]
            if l and l not in role_of:
                role_of[l] = role
    n = lab.max()
    colour_of = np.zeros((n + 1, 3), np.uint8)
    is_closed = np.zeros(n + 1, bool)
    for l in range(1, n + 1):
        pass
    sizes = ndi.sum(np.ones_like(lab), lab, range(1, n + 1))
    for l in range(1, n + 1):
        if sizes[l - 1] > 100000 or sizes[l - 1] < 3:
            continue
        role = role_of.get(l, "robe")
        colour_of[l] = COL[cfg[role]]
        is_closed[l] = True
    cm = is_closed[lab]
    out[cm] = colour_of[lab][cm]
    painted |= cm
    # open areas: wings (radial ramp) and skirt
    yy, xx = np.mgrid[0:AH, 0:AW]
    skirt = np.array(Image.new("L", (AW, AH), 0))
    sk = Image.new("L", (AW, AH), 0)
    ImageDraw.Draw(sk).polygon(SKIRT, fill=255)
    skirt = np.array(sk) > 0
    sk_zone = open_mask & skirt
    out[sk_zone] = COL[cfg["skirt"]]
    painted |= sk_zone
    # wings: hand-traced outline polygons (open hatch strokes make flood fill leak), grown a few px so the
    # edge hides under the ink, body regions carved out, then a base->tip gradient in the theme's palette
    alpha = painted.astype(np.float32)
    inside_any = np.zeros((AH, AW), bool)
    wing_a = np.zeros((AH, AW), np.float32)
    for poly, (rx, ry) in ((WING_L, (330, 470)), (WING_R, (650, 470))):
        im = Image.new("L", (AW, AH), 0)
        ImageDraw.Draw(im).polygon([(x * AW / SRC_W, y * AH / SRC_H) for x, y in poly], fill=255)
        inside = np.array(im) > 0
        frac = ndi.mean(inside.astype(np.float32), lab, range(1, n + 1))
        body = np.zeros(n + 1, bool)
        for l in range(1, n + 1):
            if is_closed[l] and frac[l - 1] < 0.5:
                body[l] = True
        body_m = body[lab]
        m = ndi.binary_dilation(inside, structure=np.ones((3, 3)), iterations=3) & ~(body_m & ~inside)
        m &= ~ndi.binary_dilation(body_m & ~inside, iterations=1) | inside
        # gradient t: 0 at the shoulder root, 1 at the farthest tip of this wing
        dist = np.hypot((xx - rx * AW / SRC_W), (yy - ry * AH / SRC_H))
        t = np.clip(dist / dist[m].max(), 0, 1)
        t = np.clip((t - 0.18) / 0.72, 0, 1)
        t = (t * t * (3 - 2 * t)) * 0.7
        c0 = np.array(COL[cfg["wings"][0]], np.float32)
        c1 = np.array(COL[cfg["wings"][-1]], np.float32)
        col = c0 + (c1 - c0) * t[..., None]
        w = ndi.gaussian_filter(m.astype(np.float32), 1.1)
        # fade where the art is cropped by its own rectangle (left/right edge) so no square edge shows
        edge = np.minimum(xx, AW - 1 - xx).astype(np.float32)
        w *= np.clip(edge / 14.0, 0, 1)
        out = (out * (1 - w[..., None]) + col * w[..., None]).astype(np.uint8)
        wing_a = np.maximum(wing_a, w)
    alpha = np.maximum(alpha, wing_a)
    painted |= wing_a > 0.02
    return out, painted, alpha


# ------------------------------------------------------------------------------------------------
# Context shared by the themes
# ------------------------------------------------------------------------------------------------
class Ctx:
    def __init__(self):
        self.art, self.fig, self.lab, self.open_mask = load_angel()
        fig_p = to_page(self.fig.astype(np.uint8)) > 0
        self.fig_page = fig_p
        dist = ndi.distance_transform_edt(~fig_p)
        self.near = dist  # px distance to the figure
        self.fig_clip = dist <= 9  # decorations are removed within 9 px of the figure ...
        inside = np.zeros_like(fig_p)
        inside[AY:AY + AH, AX:AX + AW] = True
        self.fig_clip &= inside  # ... but only inside the art rectangle (wings are cut by its edge)
        # keep-out zones: white around markers and text lines
        keep = np.zeros((PH, PW), bool)
        for cx, cy in MARKERS:
            h = MS // 2 + KEEP
            keep[max(0, cy - h):cy + h + 1, max(0, cx - h):cx + h + 1] = True
        keep[14:185, 330:910] = True  # 田字格 title block (pinyin above, English below)
        keep[1652:, :] = True  # footer / swatches
        self.keep = keep

    def free(self, x, y, r=0, gap=14):
        """True if a decoration of radius r at (x, y) stays clear of the figure, markers and page edges."""
        if not (30 + r < x < PW - 30 - r and 30 + r < y < PH - 30 - r):
            return False
        for dx, dy in ((0, 0), (r, 0), (-r, 0), (0, r), (0, -r)):
            xi, yi = int(x + dx), int(y + dy)
            if self.near[yi, xi] < gap + r * 0.3 or self.keep[yi, xi]:
                return False
        return True


# ------------------------------------------------------------------------------------------------
# THEME 1: fiery angel  -  bold, rounded, flame + sun mandala
# ------------------------------------------------------------------------------------------------
def theme_fiery(ctx):
    A = Art()
    C0 = (620, 912)
    RX, RY = 575, 742
    head = (600, 575)
    # --- sun burst, clipped by a big ellipse ---
    S = Art()
    S.dl.rectangle((0, 0, PW * SS, PH * SS), fill=WHITE)
    S.dc.rectangle((0, 0, PW * SS, PH * SS), fill=COL["ivory"])
    n = 36
    for i in range(n):
        am = i * 2 * math.pi / n
        if i % 2 == 0:  # straight gold wedge
            tri = [polar(head, am - 0.092, 200), polar(head, am, 1500), polar(head, am + 0.092, 200)]
            S.poly(tri, "gold", 4)
        else:  # wavy ember ray
            L, R = [], []
            for k in range(0, 41):
                r = 215 + k * 30
                w = 0.080 * 215 * (1 - k / 41) + 6
                off = 16 * math.sin(k * 0.55) * (k / 41 + 0.2)
                # lateral direction
                nx, ny = -math.sin(am), math.cos(am)
                cx, cy = polar(head, am, r)
                L.append((cx + nx * (w + off), cy + ny * (w + off)))
                R.append((cx - nx * (w - off), cy - ny * (w - off)))
            S.poly(L + R[::-1], "ember", 4)
    A.merge(S, mask_ellipse(C0, RX, RY))
    # ellipse rim: scalloped flame edge
    rim = []
    for i in range(72):
        a = i * 2 * math.pi / 72
        rim.append((C0[0] + RX * math.cos(a), C0[1] + RY * math.sin(a)))
    A.poly(rim, None, 7)
    # --- sun disc halo behind the head ---
    for i in range(28):
        a = i * 2 * math.pi / 28
        A.poly([polar(head, a - 0.11, 188), polar(head, a, 238), polar(head, a + 0.11, 188)], "ember", 4)
    A.circle(head, 196, "gold", 5)
    A.circle(head, 160, "indigo", 4)
    # --- bottom flames (two rows) ---
    rnd = random.Random(7)
    base = 1650
    xs = list(range(150, 1130, 110))
    for x in xs:
        d = abs(x - 620) / 500
        h = 250 + 200 * d ** 1.3 + rnd.randint(-30, 50)
        lean = (x - 620) * -0.07 + rnd.randint(-25, 25)
        A.poly(flame(x, base, 200, h, lean), "ember", 5)
        A.poly(flame(x, base, 120, h * 0.62, lean * 0.7), "gold", 4)
    for x in range(105, 1160, 88):
        d = abs(x - 620) / 500
        h = 120 + 120 * d ** 1.2 + rnd.randint(-15, 30)
        lean = (x - 620) * 0.05 + rnd.randint(-15, 15)
        A.poly(flame(x, base, 120, h, lean), "gold", 5)
        A.poly(flame(x, base, 60, h * 0.55, lean * 0.7), "ivory", 4)
    # --- embers (teardrops, sparkles, rings) in the corners and gaps ---
    rnd = random.Random(11)
    placed = []
    tries = 0
    while len(placed) < 46 and tries < 4000:
        tries += 1
        x, y = rnd.randint(40, PW - 40), rnd.randint(150, 1640)
        r = rnd.choice([16, 20, 24, 30])
        inside = ((x - C0[0]) / RX) ** 2 + ((y - C0[1]) / RY) ** 2
        if inside < 1.05 and rnd.random() < 0.8:
            continue  # keep the rays readable
        if not ctx.free(x, y, r + 6, gap=18):
            continue
        if any(math.hypot(x - px, y - py) < pr + r + 22 for px, py, pr in placed):
            continue
        placed.append((x, y, r))
        kind = rnd.choice(["tear", "tear", "spark", "ring"])
        col = rnd.choice(["ember", "gold"])
        if kind == "tear":
            A.poly(flame(x, y + r, r * 1.0, r * 2.6, rnd.randint(-8, 8)), col, 4)
        elif kind == "spark":
            A.poly(star((x, y), r * 1.3, r * 0.4, 4), col, 4)
        else:
            A.circle((x, y), r * 0.7, col, 4)
    return A


# ------------------------------------------------------------------------------------------------
# THEME 2: wrathful angel  -  angular shards, storm clouds, lightning, swords of light
# ------------------------------------------------------------------------------------------------
def bolt(x0, y0, x1, y1, w, seed=0, segs=6):
    rnd = random.Random(seed)
    dx, dy = x1 - x0, y1 - y0
    L = math.hypot(dx, dy)
    ux, uy = dx / L, dy / L
    nx, ny = -uy, ux
    cl = []
    for i in range(segs + 1):
        t = i / segs
        off = 0 if i in (0, segs) else (1 if i % 2 else -1) * w * (1.2 + 0.6 * rnd.random())
        cl.append((x0 + dx * t + nx * off, y0 + dy * t + ny * off, w * (1 - t * 0.85)))
    left = [(x + nx * ww * 0.5, y + ny * ww * 0.5) for x, y, ww in cl]
    right = [(x - nx * ww * 0.5, y - ny * ww * 0.5) for x, y, ww in cl]
    return left + right[::-1]


def sword(cx, cy, length, angle, bw=30):
    """Blade of light with a fuller, cross-guard, grip and pommel; hilt at (cx, cy), pointing along angle."""
    def T(pts):
        return shift(rot(pts, angle), cx, cy)
    blade = T([(0, -bw / 2), (length * 0.9, -bw / 2), (length, 0), (length * 0.9, bw / 2), (0, bw / 2)])
    fuller = T([(bw * 0.9, -bw * 0.14), (length * 0.82, -bw * 0.14), (length * 0.9, 0), (length * 0.82, bw * 0.14),
                (bw * 0.9, bw * 0.14)])
    guard = T([(-bw * 0.5, -bw * 1.5), (bw * 0.3, -bw * 1.2), (bw * 0.3, bw * 1.2), (-bw * 0.5, bw * 1.5),
               (-bw * 0.9, bw * 1.0), (-bw * 0.9, -bw * 1.0)])
    grip = T([(-bw * 2.4, -bw * 0.28), (-bw * 0.9, -bw * 0.28), (-bw * 0.9, bw * 0.28), (-bw * 2.4, bw * 0.28)])
    pom = T([(-bw * 3.1, 0), (-bw * 2.75, -bw * 0.45), (-bw * 2.4, 0), (-bw * 2.75, bw * 0.45)])
    return blade, fuller, guard, grip, pom


def draw_sword(A, cx, cy, length, angle, bw=30):
    blade, fuller, guard, grip, pom = sword(cx, cy, length, angle, bw)
    A.poly(blade, "ivory", 4)
    A.poly(fuller, "sky", 3)
    A.poly(grip, "ember", 3)
    A.poly(pom, "gold", 3)
    A.poly(guard, "gold", 4)


def cloud(A, x, y, s, fill, inner=None):
    prims = [("c", x - 90 * s, y + 20 * s, 42 * s), ("c", x - 40 * s, y - 14 * s, 58 * s), ("c", x + 28 * s, y - 28 * s, 64 * s),
             ("c", x + 92 * s, y - 4 * s, 50 * s), ("c", x + 140 * s, y + 24 * s, 36 * s),
             ("r", x - 90 * s, y + 20 * s, x + 140 * s, y + 60 * s)]
    A.blob(prims, fill, 4)


def lightning(A, x, y, w, h, tilt=0.0, fill="gold"):
    """Classic bold lightning-bolt icon, top-left corner at (x, y), size w x h, rotated by tilt (radians)."""
    unit = [(0.55, 0.0), (0.12, 0.46), (0.46, 0.46), (0.0, 1.0), (0.92, 0.36), (0.55, 0.36), (1.0, 0.0)]
    pts = [(x + ux * w, y + uy * h) for ux, uy in unit]
    pts = rot(pts, tilt, (x + w / 2, y + h / 2))
    A.poly(pts, fill, 5, dots=True)


def theme_wrath(ctx):
    A = Art()
    # region: big chamfers (keeps clear of the markers) with a saw-toothed edge
    reg = [(330, 160), (910, 160), (1200, 450), (1200, 1360), (910, 1650), (330, 1650), (40, 1360), (40, 450)]
    jreg = jag(reg, 11, 40, seed=5)
    S = Art()
    S.dc.rectangle((0, 0, PW * SS, PH * SS), fill=COL["indigo"])
    S.dl.rectangle((0, 0, PW * SS, PH * SS), fill=WHITE)
    # diagonal slash bands (about 58 degrees): violet bands, indigo gaps with ember-free hairline slashes
    ang = math.radians(-58)
    cx, cy = 620, 900
    ux, uy = math.cos(ang), math.sin(ang)
    nx, ny = -uy, ux
    pos = -1500
    i = 0
    rnd = random.Random(4)
    while pos < 1500:
        wd = rnd.choice([56, 84, 120]) if i % 2 == 0 else rnd.choice([40, 64, 90])
        if i % 2 == 0:
            quad = [(cx + nx * pos - ux * 2200, cy + ny * pos - uy * 2200), (cx + nx * pos + ux * 2200, cy + ny * pos + uy * 2200),
                    (cx + nx * (pos + wd) + ux * 2200, cy + ny * (pos + wd) + uy * 2200),
                    (cx + nx * (pos + wd) - ux * 2200, cy + ny * (pos + wd) - uy * 2200)]
            S.poly(quad, "violet", 4)
        pos += wd
        i += 1
    A.merge(S, mask_poly(jreg))
    A.poly(jreg, None, 6)
    # --- spiky angry halo behind the head ---
    head = (600, 575)
    spikes = []
    for k in range(36):
        a = k * 2 * math.pi / 36
        r = 285 if k % 2 == 0 else 205
        if k % 4 == 0:
            r = 330
        spikes.append(polar(head, a, r))
    A.poly(spikes, "ember", 5)
    A.poly(star(head, 205, 150, 18, a0=0.1), "gold", 4)
    A.circle(head, 150, "ivory", 4)
    # --- crossed swords of light along the bottom ---
    draw_sword(A, 250, 1597, 840, math.radians(-4), 34)
    draw_sword(A, 990, 1597, 840, math.radians(-176), 34)
    # --- storm clouds in the upper corners ---
    cloud(A, 270, 300, 1.05, "sky")
    cloud(A, 940, 296, 1.05, "sky")
    cloud(A, 120, 470, 0.62, "ivory")
    cloud(A, 1090, 470, 0.62, "ivory")
    # --- lightning bolts ---
    BOLTS = [(450, 172, 58, 150, 0.16), (712, 172, 58, 150, -0.16), (135, 960, 84, 220, 0.1), (205, 1235, 100, 250, 0.15),
             (1030, 1225, 100, 245, -0.15), (440, 1285, 70, 180, 0.2), (760, 1300, 70, 180, -0.2)]
    for (x, y, w, h, t) in BOLTS:
        lightning(A, x, y, w, h, t, "gold")
    # --- sword of light above the head (drawn last so the clouds never hide it) ---
    A.poly([(566, 445), (600, 168), (634, 445)], "ivory", 5)
    A.poly([(590, 270), (600, 245), (610, 270), (610, 440), (590, 440)], "sky", 3)
    A.line([(600, 168), (600, 150)], 4)
    # --- shard debris ---
    rnd = random.Random(21)
    placed = []
    tries = 0
    while len(placed) < 26 and tries < 6000:
        tries += 1
        x, y = rnd.randint(60, PW - 60), rnd.randint(300, 1500)
        r = rnd.choice([16, 22, 28, 34])
        if math.hypot(x - 600, y - 575) < 370:
            continue
        if not ctx.free(x, y, r + 8, gap=16) or not ctx_inside(reg, x, y):
            continue
        if any(math.hypot(x - px, y - py) < pr + r + 40 for px, py, pr in placed):
            continue
        if any(abs(x - bx) < 90 and by - 40 < y < by + 280 for bx, by in
               [(b[0], b[1]) for b in BOLTS]):
            continue
        placed.append((x, y, r))
        a0 = rnd.random() * math.pi
        pts = [polar((x, y), a0 + k * 2.2 + rnd.random() * 0.5, r * (0.6 + rnd.random() * 0.8)) for k in range(3)]
        A.poly(pts, rnd.choice(["ember", "ivory", "sky"]), 4, dots=True)
    return A


def ctx_inside(poly, x, y):
    m = Image.new("1", (PW, PH), 0)
    ImageDraw.Draw(m).polygon(poly, fill=1)
    return bool(m.getpixel((int(x), int(y))))


# ------------------------------------------------------------------------------------------------
# THEME 3: holy angel  -  gothic arch, rose window, rays, lilies, stars; mirror symmetry
# ------------------------------------------------------------------------------------------------
def lily(A, x, y, s, flip=1, tilt=0.0):
    """Lily seen from the side with three petals, stamens, stem and two leaves. Base of the flower at (x, y)."""
    def T(pts):
        return shift(rot([(flip * px * s, py * s) for px, py in pts], tilt, (0, 0)), x, y)

    # leaves first (behind)
    for sgn in (-1, 1):
        leaf = bez((0, 130), (sgn * 30, 90), (sgn * 70, 100), (sgn * 90, 150), 14) + bez((sgn * 90, 150), (sgn * 52, 128), (sgn * 20, 150), (0, 190), 14)
        A.poly(T(leaf), "violet", 3)
    A.line(T([(0, 0), (0, 40), (2, 120), (0, 240)]), 4)
    petals = []
    for ang, ln, wd in ((-52, 120, 26), (52, 120, 26), (-22, 150, 30), (22, 150, 30), (0, 170, 32)):
        a = math.radians(ang)
        tip = (math.sin(a) * ln, -math.cos(a) * ln)
        mid = (math.sin(a) * ln * 0.55, -math.cos(a) * ln * 0.55)
        nx, ny = math.cos(a), math.sin(a)
        l1 = (mid[0] - nx * wd, mid[1] - ny * wd)
        r1 = (mid[0] + nx * wd, mid[1] + ny * wd)
        # curl the tip outwards
        tip2 = (tip[0] + math.sin(a) * 14, tip[1] + 6)
        petal = bez((0, 0), l1, (l1[0] * 0.9 + tip2[0] * 0.2, l1[1] * 0.8 + tip2[1] * 0.3), tip2, 12) + \
            bez(tip2, (r1[0] * 0.9 + tip2[0] * 0.2, r1[1] * 0.8 + tip2[1] * 0.3), r1, (0, 0), 12)
        petals.append((ang, petal))
    for ang, p in sorted(petals, key=lambda t: -abs(t[0])):
        A.poly(T(p), "ivory", 3)
    for ang in (-18, 0, 18):
        a = math.radians(ang)
        tip = (math.sin(a) * 85, -math.cos(a) * 85)
        A.line(T([(0, -5), tip]), 3, caps=False)
        A.poly(T([(tip[0] - 5, tip[1] - 3), (tip[0] + 5, tip[1] - 3), (tip[0] + 5, tip[1] + 9), (tip[0] - 5, tip[1] + 9)]), "gold", 3)


def theme_holy(ctx):
    A = Art()
    W2 = 984.0
    xl, xr = 128.0, 1112.0
    r = 0.85 * W2
    ys = 960.0
    xm = (xl + xr) / 2

    def arch_pts(inset, n=60):
        """Two circular arcs meeting at the apex (pointed gothic arch), inset px inside the base arch."""
        rr = r - inset
        lx, rx_ = xl + inset, xr - inset
        # arcs: left arc centre at (lx + rr, ys); right arc centre at (rx_ - rr, ys)
        cxl, cxr = lx + rr, rx_ - rr
        dxm = xm - cxl
        h = math.sqrt(max(rr * rr - dxm * dxm, 1))
        la0, la1 = math.pi, math.atan2(-h, xm - cxl) % (2 * math.pi)  # angle from pi (leftmost) increasing to apex
        left = []
        for i in range(n + 1):
            a = la0 + (la1 - la0) * i / n  # from 180deg towards 270+deg
            left.append((cxl + rr * math.cos(a), ys + rr * math.sin(a)))
        right = [(2 * xm - x, y) for x, y in left][::-1]
        return left + right[1:]

    outer = arch_pts(0)
    inner = arch_pts(30)
    # interior = polygon of inner arch down to the floor line
    floor = 1515
    interior = inner[:]
    interior = [(inner[0][0], floor)] + inner + [(inner[-1][0], floor)]
    im_mask = mask_poly(interior)
    # --- spandrels (outside the arch) as a night sky ---
    top, bot = 170, floor + 130
    sp = Art()
    sp.dc.rectangle((0, 0, PW * SS, PH * SS), fill=COL["indigo"])
    sp.dl.rectangle((0, 0, PW * SS, PH * SS), fill=WHITE)
    box = [(128, top - 10), (1112, top - 10), (1112, floor), (128, floor)]
    A.poly(box, "indigo", 5)
    # --- interior: ivory with sky/ivory ray wedges from the halo ---
    head = (620, 575)
    I = Art()
    I.dc.rectangle((0, 0, PW * SS, PH * SS), fill=COL["sky"])
    I.dl.rectangle((0, 0, PW * SS, PH * SS), fill=WHITE)
    n = 32
    for i in range(n):
        am = i * 2 * math.pi / n
        if i % 2 == 0:
            I.poly([polar(head, am - 0.055, 250), polar(head, am, 1500), polar(head, am + 0.055, 250)], "ivory", 3)
        else:
            I.line([polar(head, am, 262), polar(head, am, 1500)], 3, caps=False)
            I.line([polar(head, am, 262), polar(head, am, 620)], 3, caps=False)
    A.merge(I, im_mask)
    A.poly(outer, None, 5)
    A.poly(inner, None, 3)
    # --- rose window halo behind the head ---
    A.circle(head, 262, "violet", 4)
    for k in range(12):
        a = k * math.pi / 6
        c = polar(head, a, 236)
        A.circle(c, 34, "gold" if k % 2 == 0 else "sky", 3)
    A.circle(head, 208, "ivory", 3)
    for k in range(12):
        a = k * math.pi / 6 + math.pi / 12
        A.poly([polar(head, a - 0.08, 208), polar(head, a, 252), polar(head, a + 0.08, 208)], "gold", 3)
    A.circle(head, 190, "ivory", 3)
    # --- stars in the spandrels (mirror symmetric) ---
    rnd = random.Random(3)
    pts = []
    for _ in range(400):
        x, y = rnd.randint(130, int(xm)), rnd.randint(185, floor - 60)
        r_ = rnd.choice([14, 18, 24, 30])
        # must be outside the arch interior and clear of the figure
        if im_mask.getpixel((x * SS, y * SS)) or im_mask.getpixel((int(min(PW - 1, (x + r_)) * SS), y * SS)):
            continue
        if not ctx.free(x, y, r_, gap=14) or not ctx.free(2 * xm - x, y, r_, gap=14):
            continue
        if any(math.hypot(x - px, y - py) < pr + r_ + 20 for px, py, pr in pts):
            continue
        pts.append((x, y, r_))
    for x, y, r_ in pts:
        for xx in (x, 2 * xm - x):
            A.poly(star((xx, y), r_, r_ * 0.42, 4 if r_ < 20 else 8), "gold", 3)
    # --- sparkles inside the sky panel (mirror symmetric) ---
    spk = []
    rnd2 = random.Random(9)
    for _ in range(600):
        x, y = rnd2.randint(150, int(xm)), rnd2.randint(900, floor - 60)
        r_ = rnd2.choice([12, 15, 18])
        if not (ctx.free(x, y, r_, gap=30) and ctx.free(2 * xm - x, y, r_, gap=30)):
            continue
        if x < 320 and y > 1180:
            continue  # keep the lily corner clear
        if any(math.hypot(x - px, y - py) < pr + r_ + 70 for px, py, pr in spk):
            continue
        spk.append((x, y, r_))
    for x, y, r_ in spk:
        for xx in (x, 2 * xm - x):
            A.poly(star((xx, y), r_, r_ * 0.38, 4), "gold", 3)
    # --- trefoil tracery in the upper spandrels ---
    for sgn in (-1, 1):
        cx = xm + sgn * 395
        for k in range(3):
            a = -math.pi / 2 + k * 2 * math.pi / 3
            A.circle(polar((cx, 330), a, 26), 24, "sky", 3)
        A.circle((cx, 330), 11, "gold", 3)
    # lilies in the lower corners (stems end behind the plinth)
    lily(A, 190, 1485 - 240 * 0.62, 0.62, 1, -0.1)
    lily(A, 285, 1485 - 240 * 0.5, 0.5, -1, 0.12)
    lily(A, 1060, 1293, 0.8, -1, 0.1)
    lily(A, 985, 1336, 0.62, 1, -0.15)
    # --- pillars + floor ---
    for x0 in (xl, xr - 30):
        A.poly([(x0, ys + 20), (x0 + 30, ys + 20), (x0 + 30, floor - 30), (x0, floor - 30)], "violet", 3)
    A.poly([(xl - 6, floor - 30), (xr + 6, floor - 30), (xr + 6, floor), (xl - 6, floor)], "violet", 4)
    A.poly([(xl - 14, floor), (xr + 14, floor), (xr + 14, floor + 36), (xl - 14, floor + 36)], "gold", 4)
    A.poly([(xl - 30, floor + 36), (xr + 30, floor + 36), (xr + 30, floor + 76), (xl - 30, floor + 76)], "sky", 4)
    # small lilies/quatrefoils along the base
    for i, x in enumerate(range(190, 1090, 100)):
        if abs(x - 620) < 20:
            continue
        for k in range(4):
            A.circle(polar((x, floor + 116), k * math.pi / 2 + math.pi / 4, 13), 12, "ivory" if k % 2 else "sky", 3)
        A.circle((x, floor + 116), 5, "gold", 2)
    return A


# ------------------------------------------------------------------------------------------------
# Themes registry
# ------------------------------------------------------------------------------------------------
THEMES = {
    "fiery": dict(
        key="fiery", file="angel-fiery", title="炙热的天使", hanzi="炙热天使", pinyin="zhì rè tiān shǐ", sub="Fiery Angel", draw=theme_fiery,
        angel=dict(wings=["gold", "ivory"], wing_cuts=[4], hair="ember", skin="ivory", robe="ivory",
                   robe2="gold", accent="ember", rope="gold", gold="ember", skirt="ivory"),
    ),
    "wrath": dict(
        key="wrath", file="angel-wrath", title="愤怒的天使", hanzi="愤怒天使", pinyin="fèn nù tiān shǐ", sub="Wrathful Angel", draw=theme_wrath,
        angel=dict(wings=["sky", "ivory"], wing_cuts=[4], hair="gold", skin="ivory", robe="ivory",
                   robe2="sky", accent="ember", rope="gold", gold="gold", skirt="ivory"),
    ),
    "holy": dict(
        key="holy", file="angel-holy", title="神圣的天使", hanzi="神圣天使", pinyin="shén shèng tiān shǐ", sub="Holy Angel", draw=theme_holy,
        angel=dict(wings=["ivory", "gold"], wing_cuts=[4], hair="gold", skin="ivory", robe="ivory",
                   robe2="sky", accent="gold", rope="violet", gold="gold", skirt="ivory"),
    ),
}


# ------------------------------------------------------------------------------------------------
# Page assembly
# ------------------------------------------------------------------------------------------------
def build(theme, ctx):
    A = theme["draw"](ctx)
    L, C = A.down()
    L = np.array(L).astype(np.uint8)
    C = np.array(C).astype(np.uint8)
    # clip decorations: remove near the figure, keep-out zones
    kill = ctx.fig_clip | ctx.keep
    L[kill] = 255
    C[ctx.keep] = 255
    # angel colours over the colour layer (page 2)
    ang, painted, alpha = angel_colour_layer(theme, ctx.lab, ctx.open_mask, ctx.fig)
    pa = np.zeros((PH, PW), np.float32)
    pa[AY:AY + AH, AX:AX + AW] = alpha
    pang = np.full((PH, PW, 3), 255, np.uint8)
    pang[AY:AY + AH, AX:AX + AW] = ang
    C = (C * (1 - pa[..., None]) + pang * pa[..., None]).astype(np.uint8)
    # page 1 content: angel line art + deco lines
    page = Image.new("RGB", (PW, PH), "white")
    page.paste(ctx.art, (AX, AY))
    deco = Image.fromarray(L, "L").convert("RGB")
    page = ImageChops.darker(page, deco)
    d = ImageDraw.Draw(page)
    for cx, cy in MARKERS:
        d.rectangle((cx - MS // 2, cy - MS // 2, cx + MS // 2, cy + MS // 2), fill="black")
    # 田字格 title: the theme's four characters (e.g. 炙 热 天 使) + English; see tools/tianzige.py
    import sys, os; sys.path.insert(0, os.path.dirname(os.path.abspath(__file__))); from tianzige import draw_title
    draw_title(page, theme["hanzi"], theme["sub"], cy=92, box=90, gap=14, pinyin=theme["pinyin"])
    p1 = page.copy()
    d1 = ImageDraw.Draw(p1)
    d1.text((PW // 2, 1708), "四个黑方块要完整拍进画面 · 不要涂到黑方块上", fill=(120, 120, 120), font=font(28), anchor="mm")
    # page 2: colour layer multiplied under the line art, plus palette swatches
    p2base = page.copy()
    colour = Image.fromarray(C, "RGB")
    p2 = ImageChops.multiply(p2base, colour)
    d2 = ImageDraw.Draw(p2)
    n = len(PALETTE)
    sw_w, gap = 150, 26
    total = n * sw_w + (n - 1) * gap
    x0 = (PW - total) // 2
    d2.text((PW // 2, 1668), "示范配色 · 本页只用这 6 种颜色", fill=(80, 80, 80), font=font(22), anchor="mm")
    for i, (key, hx, zh, en) in enumerate(PALETTE):
        x = x0 + i * (sw_w + gap)
        d2.rounded_rectangle((x, 1684, x + sw_w, 1716), 8, fill=hx, outline=(30, 30, 30), width=2)
        d2.text((x + sw_w // 2, 1731), f"{zh} {hx}", fill=(60, 60, 60), font=font(17), anchor="mm")
    return p1, p2


def verify_markers(p1, ctx):
    """Each marker is a pure black square; the 30 px ring around it is white except for pixels that belong to
    the fixed angel art itself (its top-left/-right corner reaches 4 px into the ring, as in make_template.py)."""
    a = np.pad(np.array(p1.convert("L")), 40, constant_values=255)
    art_only = Image.new("RGB", (PW, PH), "white")
    art_only.paste(ctx.art, (AX, AY))
    b = np.pad(np.array(art_only.convert("L")), 40, constant_values=255)
    ok = True
    for cx, cy in MARKERS:
        h = MS // 2
        cx, cy = cx + 40, cy + 40
        sq = a[cy - h:cy + h + 1, cx - h:cx + h + 1]
        win = (slice(cy - h - 30, cy + h + 31), slice(cx - h - 30, cx + h + 31))
        ring, ring_art = a[win].copy(), b[win].copy()
        ring[30:-30, 30:-30] = 255
        ring_art[30:-30, 30:-30] = 255
        ok &= bool(sq.max() == 0 and np.array_equal(ring, ring_art))
    return ok


def main(names):
    ctx = Ctx()
    out = ROOT / "print"
    (out / "previews").mkdir(parents=True, exist_ok=True)
    for nm in names:
        th = THEMES[nm]
        p1, p2 = build(th, ctx)
        p1.save(out / "previews" / f"{th['key']}-p1.png")
        p2.save(out / "previews" / f"{th['key']}-p2.png")
        p1.save(out / f"{th['file']}.pdf", save_all=True, append_images=[p2], resolution=150)
        print(th["file"], "markers ok:", verify_markers(p1, ctx))


if __name__ == "__main__":
    main(sys.argv[1:] or list(THEMES))
