#!/usr/bin/env python3
"""David & Goliath art bible generator (Design role), redraw 2026-10-27.

Look: realistic-proportion cartoon (Pixar-like). Believable anatomy and head-to-body ratios, defined planes (jaw,
cheekbones, brow ridge, nose, collarbones, elbows, knees, ankles), real hands (four fingers + thumb), clothing with
thickness, hems and folds. NOT joined balloons. Plus a paper desert set (dunes, rocks, brook, five stones, two camps).

One parametric description drives everything this role delivers, so the numbers the Blender / Desert / Sheet roles
read and the pictures people look at cannot disagree:

  assets/david-goliath/design.json               proportions, bones (incl. finger bones), props, palette, sheet rects,
                                                 desert layout (CONTRACT §11)
  docs/david-goliath/design/*.svg + *.png        turnarounds (front / side / back), expressions, palette, line-up,
                                                 desert plan, AR mock, A4 sheet mocks, face decals, scan simulation

Checks (exit non-zero on failure): figures inside the art rectangle, David-Goliath gap, no colouring slivers,
decorative lines never cut a region, palette survives the app's line-erase, desert pieces clear of the character
drawings and of the flat stage, desert inside the art rectangle (except the brook strip), heights within caps.

Units: art-width units (1.0 = width of the sheet's art rectangle), Y up, ground y = 0, +X = viewer's right, +Z toward
the viewer. A character's L side is +X (it faces the viewer). Run:  python3 make_design.py [--quick]
Needs: shapely, numpy, Pillow, Google Chrome (headless, for SVG -> PNG).
"""
import json, math, os, subprocess, sys
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape
from shapely.geometry import Point, LineString, Polygon, box, MultiPolygon
from shapely.ops import unary_union, polylabel
from shapely import affinity

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
OUT_JSON = os.path.join(ROOT, "assets", "david-goliath", "design.json")
TIMELINE = os.path.join(ROOT, "assets", "david-goliath", "timeline.json")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
QUICK = "--quick" in sys.argv

# ---------------------------------------------------------------------------------------------- sheet
PAGE = (1240, 1754)                       # A4 @ 150 dpi
ART = (120, 283, 1000, 1227)              # same art rect as the angel sheet -> capture code unchanged
MARKERS = [(62, 225), (1178, 225), (1178, 1568), (62, 1568)]
MARKER_SIZE = 64
PX = ART[2]                               # page px per art-width unit (1000)
ART_H = ART[3] / ART[2]                   # 1.227 art units tall
ART_BOTTOM_PX = ART[1] + ART[3]           # 1510: page row of y = 0 / z = 0
LINE_OUTER = 0.0045                       # 4.5 px silhouette / region border (erased by the app: <= 8 texels)
LINE_DETAIL = 0.0030                      # 3 px decorative interior lines (folds, fingers, scales)
LINE_FACE = 0.0022                        # 2.2 px printed face lines (for the child; the model wears decals)
MARGIN_MIN = 0.030                        # figure to art-rect edge (sides, top)
SHEET_Y = 0.015                           # figures stand 15 px above the art-rect bottom edge (closed outline under feet)
BOTTOM_MIN = 0.012
GAP_MIN = 0.040                           # David to Goliath, anywhere
REGION_MIN_D = 0.012                      # target: smallest colourable piece, inscribed circle diameter (12 px ~ 2 mm)
SLIVER_D = 0.006                          # anything visible below this is a defect
DESERT_CLEAR = 0.030                      # desert print to character print, minimum distance
INK = "#262019"
ARM_DEG = 45.0                            # rest A-pose, arms 45 deg below horizontal (§11; was 40, D2)

# palette: crayon tokens from DESIGN-DIRECTION where they fit, earth tones otherwise
PALETTE = {
    "david": {
        "skin":    ("#EDB98E", "皮肤", "skin"),
        "hair":    ("#B9562A", "红棕头发", "auburn hair"),          # "ruddy" 1 Sam 16:12, 17:42
        "tunic":   ("#4BA3E3", "外衣", "tunic"),                    # crayon sky
        "belt":    ("#E8553D", "腰带", "sash"),                     # crayon red
        "bag":     ("#C68B4E", "牧人袋", "shepherd bag"),           # 17:40
        "sandals": ("#A8693A", "凉鞋", "sandals"),
        "sling":   ("#D9A066", "机弦", "sling"),                    # 17:40
        "stone":   ("#B9B4AA", "石子", "stone"),
    },
    "goliath": {
        "skin":       ("#D99A6C", "皮肤", "skin"),
        "beard":      ("#6E4326", "胡子", "beard"),
        "helmet":     ("#E3B04B", "铜盔", "bronze helmet"),          # 17:5 (gold foil token)
        "crest":      ("#E8553D", "盔缨", "helmet crest"),
        "armour":     ("#C8873A", "鳞甲", "scale armour"),           # 17:5
        "belt":       ("#9C5B2E", "腰带", "belt"),
        "bracers":    ("#B5733C", "护腕", "leather bracers"),
        "kilt":       ("#8A6FD1", "短裙", "kilt"),                   # crayon grape
        "greaves":    ("#E3B04B", "护胫", "bronze greaves"),         # 17:6
        "feet":       ("#A8693A", "靴", "boots"),
        "spearShaft": ("#B07A45", "枪杆", "spear shaft"),            # 17:7
        "spearHead":  ("#BFC7CF", "铁枪头", "iron spear head"),      # 17:7
        "shield":     ("#E3B04B", "盾牌", "shield"),
        "shieldRim":  ("#C8873A", "盾边", "shield rim"),
        "shieldBoss": ("#FFC93C", "盾心", "shield boss"),
    },
    "desert": {
        "sand":       ("#F3D58E", "沙丘", "dune (windward)"),
        "duneShade":  ("#E3A857", "沙丘背风面", "dune slip face"),
        "rock":       ("#B99B7A", "岩石", "rock"),
        "hillIsrael": ("#D9B77A", "以色列山岗", "Israel hill"),
        "hillPhil":   ("#CFA36B", "非利士山岗", "Philistine hill"),
        "tentIsrael": ("#F4EEDC", "以色列帐篷", "Israel tents"),
        "tentPhil":   ("#E07B5A", "非利士帐篷", "Philistine tents"),
        "flagIsrael": ("#4B7BE5", "以色列旗", "Israel banner"),
        "flagPhil":   ("#C0392B", "非利士旗", "Philistine banner"),
        "water":      ("#6EC1E4", "溪水", "brook"),
        "pebbles":    ("#C9C3B6", "五块石子", "five smooth stones"),
        "bush":       ("#9BBF5A", "灌木", "desert shrub"),
        "tentDoor":   ("#7A4E2D", "帐篷门", "tent door"),
    },
}
SHADE_TO = "#4A2C1E"


def ink_safe(hx):
    """The app treats a pixel as ink when max(rgb) < 175 and max-min < 45 (web/vision.js eraseLines)."""
    r, g, b = (int(hx[i:i + 2], 16) for i in (1, 3, 5))
    return not (max(r, g, b) < 175 and max(r, g, b) - min(r, g, b) < 45)


def mix(a, b, t):
    ca = [int(a[i:i + 2], 16) for i in (1, 3, 5)]; cb = [int(b[i:i + 2], 16) for i in (1, 3, 5)]
    return "#" + "".join(f"{round(x + (y - x) * t):02X}" for x, y in zip(ca, cb))


# ---------------------------------------------------------------------------------------------- geometry helpers
def cr(pts, closed=True, n=8):
    """Catmull-Rom spline through pts (smooth organic outlines instead of ellipses and capsules)."""
    P = list(pts)
    P = ([P[-1]] + P + [P[0], P[1]]) if closed else ([P[0]] + P + [P[-1]])
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = P[i - 1], P[i], P[i + 1], P[i + 2]
        for k in range(n):
            t = k / n; t2 = t * t; t3 = t2 * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3) for j in (0, 1)))
    if not closed: out.append(P[-2])
    return out


def blob(pts, n=8):
    return Polygon(cr(pts, True, n)).buffer(0)


def mirror_blob(half, n=8):
    """half: points on the +X side from top-centre clockwise to bottom-centre; mirrored into a closed outline."""
    pts = half + [(-x, y) for x, y in reversed(half[1:-1])]
    return blob(pts, n)


def tube(ax, n=6, cap=0.6):
    """Limb from an axis polyline [(x, y, wl, wr)]: wl/wr = half-widths left/right of the travel direction."""
    L, R = [], []
    m = len(ax)
    for i, (x, y, wl, wr) in enumerate(ax):
        a = ax[max(i - 1, 0)]; b = ax[min(i + 1, m - 1)]
        dx, dy = b[0] - a[0], b[1] - a[1]; l = math.hypot(dx, dy) or 1
        dx, dy = dx / l, dy / l
        L.append((x - dy * wl, y + dx * wl)); R.append((x + dy * wr, y - dx * wr))
        if i == 0: d0 = (dx, dy)
        if i == m - 1: d1 = (dx, dy)
    x0, y0, a0, b0 = ax[0]; x1, y1, a1, b1 = ax[-1]
    e0 = (x0 - d0[0] * cap * (a0 + b0) / 2, y0 - d0[1] * cap * (a0 + b0) / 2)
    e1 = (x1 + d1[0] * cap * (a1 + b1) / 2, y1 + d1[1] * cap * (a1 + b1) / 2)
    return blob(L + [e1] + list(reversed(R)) + [e0], n)


def along(S, d, t, off=0.0):
    """point at distance t along direction d from S, offset `off` along the left normal of d."""
    return (S[0] + d[0] * t - d[1] * off, S[1] + d[1] * t + d[0] * off)


def ell(cx, cy, rx, ry, rot=0):
    g = affinity.scale(Point(0, 0).buffer(1, 48), rx, ry)
    if rot: g = affinity.rotate(g, rot, origin=(0, 0))
    return affinity.translate(g, cx, cy)


def rrect(cx, cy, w, h, r):
    return box(cx - w / 2 + r, cy - h / 2 + r, cx + w / 2 - r, cy + h / 2 - r).buffer(r, 16)


def arc(cx, cy, r, a0, a1, n=24, ry=None):
    ry = r if ry is None else ry
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def mx(pts):
    return [(-x, y) for x, y in pts]


def polys(g):
    if g is None or g.is_empty: return []
    if isinstance(g, Polygon): return [g]
    return [p for p in getattr(g, "geoms", []) if isinstance(p, Polygon) and not p.is_empty]


class Fig:
    """A figure = ordered list of filled shapes (back to front) + decorative strokes + printed face lines."""
    def __init__(self):
        self.shapes = []      # (region, geom, tag)
        self.decor = []       # (LineString, width, parent_geom or None)
        self.face = []        # printed face strokes (LineString, width) - for the child, erased by the app
        self.ink = []         # filled ink geoms (pupils etc., concept art only)
        self.paint = []       # (geom, colour) drawn last (concept art / decals only, never printed)
        self.hidden = []      # dashed outlines

    def s(self, region, geom, tag=""):
        self.shapes.append((region, geom, tag)); return geom

    def d(self, pts, w=LINE_DETAIL, parent=None, smooth=True):
        p = cr(pts, False, 6) if smooth and len(pts) > 2 else pts
        l = LineString(p)
        if parent is not None:                  # keep both ends inside the region: a decorative line never splits it
            l = l.intersection(parent.buffer(-0.0045))
            ls = [g for g in ([l] if isinstance(l, LineString) else getattr(l, "geoms", [])) if isinstance(g, LineString) and g.length > 0.002]
            if not ls: return
            l = max(ls, key=lambda g: g.length)
        self.decor.append((l, w, parent))

    def fl(self, pts, w=LINE_FACE, smooth=True):
        p = cr(pts, False, 6) if smooth and len(pts) > 2 else pts
        self.face.append((LineString(p), w))

    def xform(self, fn):
        f = Fig()
        f.shapes = [(r, fn(g), t) for r, g, t in self.shapes]
        f.decor = [(fn(l), w, fn(p) if p is not None else None) for l, w, p in self.decor]
        f.face = [(fn(l), w) for l, w in self.face]
        f.ink = [fn(g) for g in self.ink]; f.hidden = [fn(g) for g in self.hidden]
        f.paint = [(fn(g), c) for g, c in self.paint]
        return f

    def translate(self, dx, dy=0):
        return self.xform(lambda g: affinity.translate(g, dx, dy))

    def mirrored(self):
        return self.xform(lambda g: affinity.scale(g, -1, 1, origin=(0, 0)))

    def silhouette(self):
        return unary_union([g for _, g, _ in self.shapes])


# ---------------------------------------------------------------------------------------------- David
# A shepherd youth, ~14. 5.5 heads (skull) tall: Pixar-teen proportions, a touch more head than a real teen so the
# face still reads on a 51 mm figure (0.30 x 169 mm).
D = dict(height=0.300, hairTop=0.300, skullTop=0.294, chin=0.241, headHalfW=0.0198,
         eyeY=0.2672, browY=0.2722, noseY=0.2556, mouthY=0.2497, earY=(0.2575, 0.2705),
         neckBase=0.228, shoulder=(0.031, 0.220), upperArm=0.053, forearm=0.043, hand=0.031,
         chestY=0.205, waistY=0.178, hip=(0.016, 0.153), crotch=0.138, knee=(0.0185, 0.083), ankle=(0.018, 0.016),
         footLen=0.044, tunicHemY=0.096, beltY=(0.171, 0.182), sheetY=SHEET_Y)
D["headsTall"] = round(D["skullTop"] / (D["skullTop"] - D["chin"]), 2)


def arm_axis(P, sd, deg=ARM_DEG):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    d = (sd * c, -s)
    S = (sd * P["shoulder"][0], P["shoulder"][1])
    E = along(S, d, P["upperArm"]); W = along(E, d, P["forearm"]); H = along(W, d, P["hand"])
    return S, E, W, H, d


def david_head_shapes(f, back=False):
    """Back hair, ears, head (jaw, cheekbones), front hair. Front view (back=True: seen from behind, unmirrored)."""
    # curly auburn hair: outer silhouette = cap + curls
    cap = mirror_blob([(0, 0.3000), (0.0110, 0.2988), (0.0195, 0.2945), (0.0238, 0.2870), (0.0250, 0.2780),
                       (0.0236, 0.2690), (0.0222, 0.2610), (0.0170, 0.2560), (0, 0.2550)])
    curls = unary_union([Point(0.0236 * math.cos(math.radians(a)), 0.2770 + 0.0218 * math.sin(math.radians(a)))
                         .buffer(0.0050 + 0.0006 * math.sin(a * 3.1), 16) for a in range(-30, 211, 16)])
    hair_out = unary_union([cap, curls]).intersection(box(-1, 0.256 if not back else 0.252, 1, 1))
    if back:                                   # from behind: hair covers the whole head down to the nape
        f.s("skin", box(-0.0085, 0.236, 0.0085, 0.256), "neck")
        for sx in (-1, 1):
            f.s("skin", ell(sx * 0.0212, 0.2640, 0.0034, 0.0066, sx * 8), "ear")
        nape = mirror_blob([(0, 0.2585), (0.0120, 0.2570), (0.0185, 0.2560), (0.0200, 0.2520), (0.0110, 0.2490), (0, 0.2480)])
        f.s("hair", unary_union([hair_out, nape]), "hair")
        for a in (60, 100, 140):                # curl hints
            cx = 0.016 * math.cos(math.radians(a)); cy = 0.278 + 0.014 * math.sin(math.radians(a))
            f.d(arc(cx, cy, 0.0035, 200, 340, 8), LINE_DETAIL, None, smooth=False)
        return
    for sx in (-1, 1):
        ear = ell(sx * 0.0212, 0.2640, 0.0034, 0.0066, sx * 8)
        f.s("skin", ear, "ear")
        f.d([(sx * 0.0205, 0.2685), (sx * 0.0222, 0.2660), (sx * 0.0215, 0.2610)], LINE_DETAIL, None)
    head = mirror_blob([(0, D["skullTop"]), (0.0120, 0.2925), (0.0182, 0.2868), (0.0196, 0.2780), (0.0199, 0.2690),
                        (0.0193, 0.2620), (0.0170, 0.2545), (0.0122, 0.2462), (0.0058, 0.2418), (0, D["chin"])])
    f.s("skin", head, "face")
    hairline = [(-0.0215, 0.2600), (-0.0196, 0.2700), (-0.0170, 0.2770), (-0.0105, 0.2812), (-0.0030, 0.2800),
                (0.0040, 0.2822), (0.0110, 0.2808), (0.0172, 0.2768), (0.0197, 0.2700), (0.0215, 0.2600)]
    below = Polygon(cr(hairline, False, 6) + [(0.03, 0.2600), (0.03, 0.20), (-0.03, 0.20), (-0.03, 0.2600)]).buffer(0)
    front_hair = hair_out.intersection(box(-0.0222, 0.256, 0.0222, 1)).difference(below)
    f.s("hair", front_hair, "hair")
    for a, r in ((70, 0.0032), (115, 0.0034), (150, 0.0030), (30, 0.0030)):
        cx = 0.0150 * math.cos(math.radians(a)); cy = 0.2860 + 0.0060 * math.sin(math.radians(a))
        f.d(arc(cx, cy, r, 200, 330, 8), LINE_DETAIL, None, smooth=False)


def david_face_print(f):
    """Thin printed face for the child (the app's line-erase removes it; the model wears decals, §11)."""
    for sx in (-1, 1):
        f.fl([(sx * 0.0035, 0.2712), (sx * 0.0085, 0.2733), (sx * 0.0135, 0.2722)], LINE_FACE * 1.3)       # brows
        f.fl([(sx * 0.0040, 0.2672), (sx * 0.0078, 0.2690), (sx * 0.0122, 0.2675)])                        # upper lid
        f.fl([(sx * 0.0048, 0.2664), (sx * 0.0085, 0.2656), (sx * 0.0115, 0.2667)], LINE_FACE * 0.7)      # lower lid
        f.ink.append(Point(sx * 0.0080, 0.2671).buffer(0.0016))                                          # pupil
    f.fl([(0.0016, 0.2655), (0.0022, 0.2600), (0.0032, 0.2568), (0.0016, 0.2556)], LINE_FACE * 0.8)       # nose side
    f.fl([(-0.0030, 0.2560), (-0.0012, 0.2553), (0.0012, 0.2553), (0.0030, 0.2560)], LINE_FACE * 0.8)
    f.fl([(-0.0058, 0.2503), (-0.0020, 0.2492), (0.0020, 0.2492), (0.0058, 0.2503)], LINE_FACE * 1.1)     # mouth
    f.fl([(-0.0022, 0.2474), (0.0022, 0.2474)], LINE_FACE * 0.7)                                           # lower lip


def david_hand_open(f, W, d, sd, region="skin"):
    """Relaxed open hand, fingers together, thumb in front (palm faces the thigh in A-pose)."""
    h = D["hand"]
    o = sd                                      # left normal of d points up-out for sd=+1, down-in for sd=-1
    palm = tube([(*along(W, d, -0.002), 0.0046, 0.0044), (*along(W, d, 0.007), 0.0062, 0.0058),
                 (*along(W, d, 0.016), 0.0064, 0.0058), (*along(W, d, 0.024), 0.0055, 0.0050),
                 (*along(W, d, h - 0.001), 0.0040, 0.0036)], cap=0.7)
    thumb = tube([(*along(W, d, 0.003, o * 0.0045), 0.0026, 0.0026), (*along(W, d, 0.011, o * 0.0078), 0.0024, 0.0024),
                  (*along(W, d, 0.018, o * 0.0084), 0.0020, 0.0020)], cap=0.8)
    g = f.s(region, unary_union([palm, thumb]), "hand")
    for k in (-0.0030, 0.0002, 0.0032):          # finger separations: from the tip notch inward (one end only)
        f.d([along(W, d, h + 0.0005, k), along(W, d, h - 0.008, k * 1.05)], LINE_DETAIL * 0.8, g, smooth=False)
    f.d([along(W, d, 0.0155, -o * 0.0040), along(W, d, 0.0160, o * 0.0010)], LINE_DETAIL * 0.7, g, smooth=False)  # knuckles
    return g


def fist(f, C, d, sd, size, region="skin", tag="fist"):
    """Closed fist around a grip, knuckles toward the viewer. size = fist length along d."""
    w = size * 0.86
    pts = [along(C, d, -size * 0.50, 0), along(C, d, -size * 0.35, w * 0.52), along(C, d, size * 0.15, w * 0.56),
           along(C, d, size * 0.48, w * 0.40), along(C, d, size * 0.55, 0), along(C, d, size * 0.45, -w * 0.45),
           along(C, d, size * 0.05, -w * 0.55), along(C, d, -size * 0.40, -w * 0.48)]
    g = f.s(region, blob(pts), tag)
    for k in (-0.22, 0.02, 0.26):               # finger rows wrapped around the grip
        f.d([along(C, d, size * k, -w * 0.36), along(C, d, size * (k + 0.03), w * 0.02), along(C, d, size * k, w * 0.30)],
            LINE_DETAIL * 0.8, g)
    f.d([along(C, d, -size * 0.30, sd * w * 0.36), along(C, d, size * 0.20, sd * w * 0.28)], LINE_DETAIL * 0.8, g)  # thumb
    return g


def build_david(back=False):
    f = Fig(); P = D
    # legs (skin) with knees, calves, ankles
    for sd in (-1, 1):
        o, i = 1, 1
        hx, hy = sd * P["hip"][0], P["hip"][1]; kx, ky = sd * P["knee"][0], P["knee"][1]; ax_, ay = sd * P["ankle"][0], P["ankle"][1]
        def w(out, inn): return (out, inn) if sd > 0 else (inn, out)   # tube goes down: left normal = +X
        ax = [(hx, hy, *w(0.0165, 0.0115)), (sd * 0.0180, 0.122, *w(0.0135, 0.0098)), (sd * 0.0185, 0.098, *w(0.0105, 0.0085)),
              (kx, ky, *w(0.0088, 0.0078)), (sd * 0.0190, 0.068, *w(0.0094, 0.0086)), (sd * 0.0188, 0.055, *w(0.0092, 0.0077)),
              (sd * 0.0183, 0.036, *w(0.0068, 0.0058)), (ax_, ay + 0.002, *w(0.0053, 0.0050))]
        leg = f.s("skin", tube(ax), "leg")
        f.d([(kx - 0.0040, ky + 0.0010), (kx, ky - 0.0022), (kx + 0.0040, ky + 0.0010)], LINE_DETAIL * 0.8, leg)   # knee cap
        f.d([(sd * 0.0270, 0.0700), (sd * 0.0262, 0.0560)], LINE_DETAIL * 0.7, leg, smooth=False)                  # calf
    for sd in (-1, 1):                          # feet in sandals, toes toward the viewer
        fx = sd * 0.0192
        foot = mirror_blob([(0, 0.0170), (0.0050, 0.0168), (0.0072, 0.0120), (0.0088, 0.0050), (0.0092, 0.0010), (0, -0.0004)])
        foot = affinity.translate(affinity.rotate(foot, -sd * 6, origin=(0, 0.01)), fx, 0)
        f.s("skin", foot, "foot")
        sole = foot.intersection(box(-1, -1, 1, 0.0074)).union(
            LineString([(fx - 0.0072, 0.0118), (fx + 0.0072, 0.0118)]).buffer(0.0021).intersection(foot))
        f.s("sandals", sole, "sandal")
        for k in (-0.0045, -0.0015, 0.0015, 0.0045):
            f.d([(fx + k, 0.0072), (fx + k * 1.05, 0.0044)], LINE_DETAIL * 0.7, foot, smooth=False)          # toes
    # neck + trapezius
    f.s("skin", mirror_blob([(0, 0.2470), (0.0085, 0.2465), (0.0090, 0.2370), (0.0120, 0.2300), (0.0220, 0.2268),
                             (0.0200, 0.2250), (0, 0.2240)]), "neck")
    arms = {sd: arm_axis(P, sd) for sd in (-1, 1)}
    # arms: deltoid, biceps, elbow, forearm, wrist (skin)
    for sd, (S, E, W, H, d) in arms.items():
        o = 1 if sd > 0 else -1               # left normal of d: up-out for +X arm, down-in for -X arm
        def ww(out, inn): return (out, inn) if sd > 0 else (inn, out)
        ax = [(*along(S, d, -0.004), *ww(0.0090, 0.0068)), (*along(S, d, 0.008), *ww(0.0098, 0.0076)),
              (*along(S, d, 0.026), *ww(0.0074, 0.0084)), (*along(S, d, 0.046), *ww(0.0064, 0.0066)),
              (*E, *ww(0.0060, 0.0062)), (*along(E, d, 0.010), *ww(0.0074, 0.0068)), (*along(E, d, 0.026), *ww(0.0058, 0.0054)),
              (*W, *ww(0.0047, 0.0045))]
        arm = f.s("skin", tube(ax), "arm")
        f.d([along(E, d, -0.003, o * 0.0035), along(E, d, 0.001, o * 0.0010), along(E, d, 0.0045, o * 0.0030)],
            LINE_DETAIL * 0.7, arm)                                                                              # elbow
    # tunic: knee-length, belted, with hem thickness and folds
    tunic = mirror_blob([(0, 0.2280), (0.0080, 0.2312), (0.0170, 0.2300), (0.0280, 0.2262), (0.0335, 0.2210),
                         (0.0312, 0.2040), (0.0310, 0.1920), (0.0283, 0.1790), (0.0300, 0.1680), (0.0345, 0.1400),
                         (0.0395, 0.1150), (0.0425, 0.0975), (0.0280, 0.0950), (0.0100, 0.0942), (0, 0.0940)])
    if back:
        tunic = mirror_blob([(0, 0.2335), (0.0080, 0.2330), (0.0170, 0.2305), (0.0280, 0.2262), (0.0335, 0.2210),
                             (0.0312, 0.2040), (0.0310, 0.1920), (0.0283, 0.1790), (0.0300, 0.1680), (0.0345, 0.1400),
                             (0.0395, 0.1150), (0.0425, 0.0975), (0.0280, 0.0950), (0.0100, 0.0942), (0, 0.0940)])
    tg = f.s("tunic", tunic, "tunic")
    f.d([(-0.0410, 0.1010), (-0.0200, 0.0990), (0.0, 0.0985), (0.0200, 0.0990), (0.0410, 0.1010)], LINE_DETAIL * 0.8, None)  # hem
    for x0, x1, y0 in ((-0.016, -0.022, 0.166), (-0.004, -0.006, 0.164), (0.010, 0.013, 0.165), (0.022, 0.030, 0.160)):
        f.d([(x0, y0), ((x0 + x1) / 2 + 0.001, (y0 + 0.104) / 2), (x1, 0.104)], LINE_DETAIL * 0.8, tg)         # skirt folds
    if not back:
        f.d([(-0.0075, 0.2290), (-0.0030, 0.2235), (0.0030, 0.2235), (0.0075, 0.2290)], LINE_DETAIL, tg)        # neckline
        f.d([(-0.0140, 0.2120), (-0.0060, 0.2060), (0.0010, 0.1950)], LINE_DETAIL * 0.7, tg)                     # chest fold
    else:
        f.d([(-0.0010, 0.2280), (0.0, 0.2100), (0.0010, 0.1880)], LINE_DETAIL * 0.7, tg)                         # back seam
    # short sleeves with a hem
    for sd, (S, E, W, H, d) in arms.items():
        o = 1 if sd > 0 else -1
        def ww(out, inn): return (out, inn) if sd > 0 else (inn, out)
        sl = f.s("tunic", tube([(*along(S, d, -0.006), *ww(0.0098, 0.0080)), (*along(S, d, 0.010), *ww(0.0100, 0.0082)),
                                (*along(S, d, 0.023), *ww(0.0090, 0.0088))], cap=0.15), "sleeve")
        f.d([along(S, d, 0.019, o * 0.0080), along(S, d, 0.0205, 0), along(S, d, 0.019, -o * 0.0078)], LINE_DETAIL * 0.8, sl)
    # hands: right (−X) closes on the sling cords, left (+X) open
    S, E, W, H, d = arms[-1]
    fc = along(W, d, 0.0115)
    rf = fist(f, fc, d, -1, 0.0215)
    S2, E2, W2, H2, d2 = arms[1]
    david_hand_open(f, W2, d2, 1)
    # sash belt with a knot and hanging ends at his left hip
    belt = tunic.intersection(box(-1, P["beltY"][0], 1, P["beltY"][1]))
    bg = f.s("belt", belt, "sash")
    knot = f.s("belt", unary_union([ell(0.0215, 0.1765, 0.0050, 0.0045),
                                    tube([(0.0205, 0.1720, 0.0036, 0.0036), (0.0225, 0.1590, 0.0038, 0.0038), (0.0245, 0.1480, 0.0034, 0.0034)], cap=0.4),
                                    tube([(0.0245, 0.1720, 0.0034, 0.0034), (0.0290, 0.1610, 0.0036, 0.0036), (0.0310, 0.1530, 0.0034, 0.0034)], cap=0.4)]),
               "sashKnot")
    f.d([(-0.026, 0.1765), (-0.010, 0.1772), (0.010, 0.1760)], LINE_DETAIL * 0.7, bg)
    # shepherd's bag: strap from right shoulder to the left hip, bag at the front of the left hip
    strap = LineString(cr([(-0.0240, 0.2285), (-0.0080, 0.2100), (0.0120, 0.1880), (0.0270, 0.1660)], False, 6)).buffer(0.0033, cap_style=2)
    f.s("bag", strap.intersection(tunic.buffer(0.0015)), "strap")
    if not back:
        bag = mirror_blob([(0, 0.0130), (0.0100, 0.0122), (0.0128, 0.0050), (0.0122, -0.0060), (0.0080, -0.0105), (0, -0.0112)])
        bag = affinity.translate(bag, 0.0300, 0.1530)
        bgg = f.s("bag", bag, "bag")
        f.d(cr([(0.0185, 0.1590), (0.0240, 0.1540), (0.0300, 0.1525), (0.0360, 0.1540), (0.0415, 0.1590)], False, 6), LINE_DETAIL, bgg, smooth=False)
        f.d([(0.0300, 0.1525), (0.0300, 0.1485)], LINE_DETAIL * 0.8, bgg, smooth=False)            # toggle
    # sling: two cords from the fist to the pouch (one colourable band), pouch, stone
    cx, cy = fc[0], fc[1] - 0.0080
    cords = Polygon([(cx - 0.0020, cy), (cx + 0.0020, cy), (cx + 0.0068, 0.0840), (cx - 0.0068, 0.0840)]).buffer(0.0008)
    f.s("sling", cords, "slingCords")
    f.d([(cx, cy - 0.003), (cx, 0.0870)], LINE_DETAIL * 0.6, cords, smooth=False)
    pouch = mirror_blob([(0, 0.0090), (0.0080, 0.0085), (0.0120, 0.0020), (0.0100, -0.0050), (0.0050, -0.0080), (0, -0.0085)])
    f.s("sling", affinity.translate(pouch, cx, 0.0770), "slingPouch")
    f.s("stone", ell(cx, 0.0780, 0.0058, 0.0050), "stone")
    david_head_shapes(f, back)
    if not back:
        david_face_print(f)
    return f, arms, fc


# ---------------------------------------------------------------------------------------------- Goliath
# A giant warrior from Gath, 7.4 heads (skull), massive shoulders and chest. Total 0.80 to the top of the crest.
G = dict(height=0.800, crestTop=0.800, helmetTop=0.768, skullTop=0.746, chin=0.645, headHalfW=0.040,
         eyeY=0.699, browY=0.707, noseY=0.683, mouthY=0.667, earY=(0.680, 0.708),
         neckBase=0.628, shoulder=(0.092, 0.603), upperArm=0.138, forearm=0.112, hand=0.082,
         chestY=0.540, waistY=0.452, hip=(0.050, 0.380), crotch=0.350, knee=(0.054, 0.209), ankle=(0.052, 0.040),
         footLen=0.112, kiltHemY=0.262, armourHemY=0.362, beltY=(0.438, 0.463), sheetY=SHEET_Y,
         shieldR=0.066, spearX=None)
G["headsTall"] = round(G["skullTop"] / (G["skullTop"] - G["chin"]), 2)


def goliath_face_print(f):
    for sx in (-1, 1):
        f.fl([(sx * 0.0060, 0.7060), (sx * 0.0170, 0.7095), (sx * 0.0290, 0.7075)], LINE_FACE * 2.0)     # heavy brows
        f.fl([(sx * 0.0080, 0.6995), (sx * 0.0160, 0.7020), (sx * 0.0245, 0.6995)], LINE_FACE * 1.1)
        f.fl([(sx * 0.0095, 0.6975), (sx * 0.0165, 0.6962), (sx * 0.0230, 0.6978)], LINE_FACE * 0.8)
        f.ink.append(Point(sx * 0.0165, 0.6990).buffer(0.0030))
    f.fl([(0.0040, 0.6990), (0.0058, 0.6900), (0.0085, 0.6840), (0.0060, 0.6815)], LINE_FACE * 1.1)          # broad nose
    f.fl([(-0.0060, 0.6815), (-0.0030, 0.6800), (0.0030, 0.6800), (0.0060, 0.6815)], LINE_FACE)
    f.fl([(-0.0110, 0.6655), (-0.0040, 0.6640), (0.0040, 0.6640), (0.0110, 0.6655)], LINE_FACE * 1.4)       # frown line


def goliath_head_shapes(f, back=False, face=True):
    P = G
    # crest: transverse fan of red horsehair / feathers above the dome
    crest = mirror_blob([(0, 0.8000), (0.0180, 0.7990), (0.0360, 0.7930), (0.0500, 0.7810), (0.0520, 0.7700),
                         (0.0300, 0.7640), (0, 0.7630)])
    cg = f.s("crest", crest, "crest")
    for k in (-0.036, -0.018, 0.0, 0.018, 0.036):
        f.d([(k * 0.55, 0.7680), (k, 0.7930 - abs(k) * 0.2)], LINE_DETAIL, cg, smooth=False)
    # ears + neck guard flare behind them
    guard = mirror_blob([(0, 0.7300), (0.0420, 0.7280), (0.0490, 0.7100), (0.0530, 0.6880), (0.0500, 0.6800), (0, 0.6800)])
    if back:
        f.s("skin", mirror_blob([(0, 0.6900), (0.0280, 0.6880), (0.0300, 0.6400), (0.0450, 0.6280), (0.0700, 0.6250),
                                 (0.0680, 0.6180), (0, 0.6150)]), "neck")
        f.s("beard", mirror_blob([(0, 0.6700), (0.0350, 0.6680), (0.0400, 0.6500), (0.0280, 0.6420), (0, 0.6400)]).difference(box(-0.026, 0, 0.026, 1)), "beardSides")
        for sx in (-1, 1):
            f.s("skin", ell(sx * 0.0420, 0.6930, 0.0060, 0.0120, sx * 6), "ear")
        gg = f.s("helmet", unary_union([guard, mirror_blob([(0, 0.7700), (0.0300, 0.7660), (0.0450, 0.7480), (0.0480, 0.7250), (0, 0.7200)])]), "helmetBack")
        f.d([(-0.046, 0.7120), (-0.020, 0.7080), (0.020, 0.7080), (0.046, 0.7120)], LINE_DETAIL, gg)
        f.d([(0, 0.7650), (0, 0.6920)], LINE_DETAIL, gg, smooth=False)
        return
    f.s("helmet", guard.difference(box(-0.040, 0, 0.040, 1)), "_neckGuard")
    for sx in (-1, 1):
        ear = f.s("skin", ell(sx * 0.0420, 0.6930, 0.0060, 0.0120, sx * 6), "ear")
        f.d([(sx * 0.0405, 0.7010), (sx * 0.0440, 0.6960), (sx * 0.0425, 0.6870)], LINE_DETAIL * 0.8, ear)
    head = mirror_blob([(0, 0.7460), (0.0240, 0.7430), (0.0360, 0.7320), (0.0395, 0.7150), (0.0405, 0.6990),
                        (0.0398, 0.6860), (0.0378, 0.6720), (0.0330, 0.6600), (0.0230, 0.6500), (0.0110, 0.6455), (0, 0.6450)])
    hg = f.s("skin", head, "face")
    # cheekbone + brow ridge planes (printed as short open strokes)
    for sx in (-1, 1):
        f.d([(sx * 0.0335, 0.6880), (sx * 0.0280, 0.6830), (sx * 0.0230, 0.6845)], LINE_DETAIL * 0.7, hg)
    # beard: full, squared, covering jaw and chin; moustache over the mouth
    beard = mirror_blob([(0, 0.6720), (0.0120, 0.6735), (0.0260, 0.6790), (0.0360, 0.6840), (0.0395, 0.6740),
                         (0.0390, 0.6560), (0.0330, 0.6380), (0.0220, 0.6260), (0.0100, 0.6215), (0, 0.6210)])
    mouth_hole = mirror_blob([(0, 0.6690), (0.0090, 0.6680), (0.0110, 0.6640), (0.0070, 0.6605), (0, 0.6600)])
    bg = f.s("beard", beard.difference(mouth_hole), "beard")
    for k in (-0.024, -0.012, 0.0, 0.012, 0.024):
        f.d([(k, 0.6560), (k * 1.08, 0.6400), (k * 1.15, 0.6290)], LINE_DETAIL * 0.8, bg)                    # beard locks
    must = mirror_blob([(0, 0.6760), (0.0080, 0.6775), (0.0180, 0.6735), (0.0260, 0.6640), (0.0200, 0.6650),
                        (0.0100, 0.6690), (0, 0.6700)])
    f.s("beard", must, "moustache")
    # helmet: bronze dome with a rim band, brow just under the rim
    dome = mirror_blob([(0, 0.7680), (0.0250, 0.7650), (0.0400, 0.7540), (0.0465, 0.7370), (0.0478, 0.7200),
                        (0.0440, 0.7140), (0, 0.7130)])
    dg = f.s("helmet", dome, "helmetDome")
    rim = dome.intersection(box(-1, 0.7130, 1, 0.7235))
    f.d([(-0.0472, 0.7240), (-0.020, 0.7255), (0.020, 0.7255), (0.0472, 0.7240)], LINE_DETAIL, dg)
    f.d([(0, 0.7300), (0, 0.7600)], LINE_DETAIL, dg, smooth=False)                                          # ridge
    if face:
        goliath_face_print(f)


def build_goliath(back=False):
    f = Fig(); P = G
    sd_l = {}
    # spear (behind the right fist) first so the fist overlaps it
    arms = {sd: arm_axis(P, sd) for sd in (-1, 1)}
    S, E, W, H, d = arms[-1]
    grip = along(W, d, 0.030)
    sx = grip[0]; P["spearX"] = round(sx, 4)
    shaft = f.s("spearShaft", box(sx - 0.0095, 0.030, sx + 0.0095, 0.836), "spearShaft")
    f.d([(sx + 0.0030, 0.090), (sx + 0.0035, 0.300)], LINE_DETAIL * 0.7, shaft, smooth=False)               # wood grain
    f.d([(sx - 0.0030, 0.520), (sx - 0.0030, 0.760)], LINE_DETAIL * 0.7, shaft, smooth=False)
    f.s("spearShaft", rrect(sx, 0.840, 0.0260, 0.0160, 0.004), "spearCollar")
    head = blob([(sx, 0.9550), (sx + 0.0120, 0.9300), (sx + 0.0200, 0.8950), (sx + 0.0140, 0.8620), (sx + 0.0050, 0.8480),
                 (sx - 0.0050, 0.8480), (sx - 0.0140, 0.8620), (sx - 0.0200, 0.8950), (sx - 0.0120, 0.9300)])
    hgx = f.s("spearHead", head, "spearHead")
    f.d([(sx, 0.8600), (sx, 0.9400)], LINE_DETAIL, hgx, smooth=False)                                      # mid-rib
    f.s("spearHead", blob([(sx - 0.0085, 0.0310), (sx + 0.0085, 0.0310), (sx + 0.0040, 0.0120), (sx, 0.0030), (sx - 0.0040, 0.0120)]), "spearButt")
    # legs: thighs (skin) below the kilt, knees, then greaves; boots
    for sd in (-1, 1):
        def w(out, inn): return (out, inn) if sd > 0 else (inn, out)
        hx = sd * P["hip"][0]; kx, ky = sd * P["knee"][0], P["knee"][1]
        ax = [(hx, 0.330, *w(0.0400, 0.0300)), (sd * 0.0530, 0.280, *w(0.0360, 0.0275)), (sd * 0.0545, 0.240, *w(0.0300, 0.0240)),
              (kx, ky, *w(0.0245, 0.0215)), (sd * 0.0550, 0.170, *w(0.0275, 0.0235)), (sd * 0.0545, 0.130, *w(0.0255, 0.0205)),
              (sd * 0.0530, 0.080, *w(0.0190, 0.0160)), (sd * 0.0520, 0.050, *w(0.0160, 0.0145))]
        leg = f.s("skin", tube(ax), "leg")
        f.d([(kx - 0.011, ky + 0.004), (kx, ky - 0.006), (kx + 0.011, ky + 0.004)], LINE_DETAIL, leg)          # knee cap
        f.d([(sd * 0.072, 0.262), (sd * 0.066, 0.238)], LINE_DETAIL * 0.8, leg, smooth=False)                 # vastus
    for sd in (-1, 1):                          # boots: laced leather, toes toward the viewer
        bx = sd * 0.0545
        boot = mirror_blob([(0, 0.0620), (0.0170, 0.0610), (0.0200, 0.0400), (0.0255, 0.0150), (0.0265, 0.0030), (0, -0.0010)])
        boot = affinity.translate(affinity.rotate(boot, -sd * 5, origin=(0, 0.02)), bx, 0)
        bt = f.s("feet", boot, "boot")
        for yy in (0.050, 0.038, 0.026):
            f.d([(bx - 0.010, yy + 0.003), (bx, yy - 0.002), (bx + 0.010, yy + 0.003)], LINE_DETAIL * 0.8, bt)   # laces
    for sd in (-1, 1):                          # bronze greaves from below the knee to the ankle, with a shin ridge
        gx = sd * 0.0545
        gv = mirror_blob([(0, 0.1990), (0.0200, 0.1960), (0.0290, 0.1700), (0.0270, 0.1250), (0.0200, 0.0800),
                          (0.0175, 0.0560), (0, 0.0530)])
        gv = affinity.translate(gv, gx, 0)
        gg = f.s("greaves", gv, "greave")
        f.d([(gx, 0.1880), (gx + sd * 0.002, 0.1300), (gx, 0.0650)], LINE_DETAIL, gg)
    # kilt under the armour skirt: pleats, hem band
    kilt = mirror_blob([(0, 0.4000), (0.0880, 0.4000), (0.0960, 0.3500), (0.1060, 0.2950), (0.1110, 0.2640),
                        (0.0700, 0.2600), (0.0300, 0.2610), (0, 0.2600)])
    kg = f.s("kilt", kilt, "kilt")
    f.d([(-0.105, 0.2720), (-0.050, 0.2685), (0.0, 0.2680), (0.050, 0.2685), (0.105, 0.2720)], LINE_DETAIL, kg)
    for x0 in (-0.078, -0.052, -0.026, 0.0, 0.026, 0.052, 0.078):
        f.d([(x0 * 0.92, 0.352), (x0 * 1.0, 0.315), (x0 * 1.10, 0.280)], LINE_DETAIL * 0.8, kg)
    # arms: massive deltoids, biceps, elbows, forearms (skin), leather bracers
    for sd, (S, E, W, H, d) in arms.items():
        o = 1 if sd > 0 else -1
        def ww(out, inn): return (out, inn) if sd > 0 else (inn, out)
        ax = [(*along(S, d, -0.012), *ww(0.0290, 0.0230)), (*along(S, d, 0.020), *ww(0.0300, 0.0255)),
              (*along(S, d, 0.065), *ww(0.0250, 0.0275)), (*along(S, d, 0.115), *ww(0.0200, 0.0215)),
              (*E, *ww(0.0190, 0.0195)), (*along(E, d, 0.030), *ww(0.0230, 0.0215)), (*along(E, d, 0.070), *ww(0.0180, 0.0165)),
              (*W, *ww(0.0150, 0.0140))]
        arm = f.s("skin", tube(ax), "arm")
        f.d([along(E, d, -0.010, o * 0.012), along(E, d, 0.002, o * 0.004), along(E, d, 0.013, o * 0.010)], LINE_DETAIL, arm)  # elbow
        f.d([along(S, d, 0.050, -o * 0.012), along(S, d, 0.085, -o * 0.016)], LINE_DETAIL * 0.8, arm, smooth=False)       # biceps
        br = f.s("bracers", tube([(*along(E, d, 0.045), *ww(0.0215, 0.0200)), (*along(E, d, 0.080), *ww(0.0180, 0.0168)),
                                  (*along(W, d, 0.002), *ww(0.0158, 0.0150))], cap=0.1), "bracer")
        for t in (0.058, 0.074, 0.090):
            f.d([along(E, d, t, o * 0.013), along(E, d, t + 0.003, -o * 0.012)], LINE_DETAIL * 0.7, br, smooth=False)
    # neck + trapezius
    f.s("skin", mirror_blob([(0, 0.6700), (0.0270, 0.6690), (0.0300, 0.6450), (0.0450, 0.6340), (0.0760, 0.6250),
                             (0.0700, 0.6150), (0, 0.6100)]), "neck")
    if not back:
        f.d([(-0.0200, 0.6650), (-0.0150, 0.6400)], LINE_DETAIL * 0.8, None, smooth=False)
        f.d([(0.0200, 0.6650), (0.0150, 0.6400)], LINE_DETAIL * 0.8, None, smooth=False)
    # scale armour coat: shoulders to upper thighs, short scale sleeves
    coat = mirror_blob([(0, 0.6300 if not back else 0.6420), (0.0300, 0.6380), (0.0700, 0.6320), (0.1050, 0.6200), (0.1200, 0.6040),
                        (0.1020, 0.5650), (0.0990, 0.5250), (0.0870, 0.4780), (0.0815, 0.4500), (0.0900, 0.4100),
                        (0.0990, 0.3680), (0.0700, 0.3620), (0.0300, 0.3600), (0, 0.3600)])
    if not back:
        coat = coat.difference(mirror_blob([(0, 0.6420), (0.0240, 0.6400), (0.0180, 0.6200), (0, 0.6120)]))  # neck opening
    ag = f.s("armour", coat, "armourCoat")
    inner = coat.buffer(-0.010)
    for row, y in enumerate([0.598, 0.574, 0.550, 0.526, 0.502, 0.478, 0.418, 0.394, 0.372]):
        off = 0.0 if row % 2 == 0 else 0.0105
        for i in range(-10, 11):
            x = i * 0.021 + off
            a = arc(x, y + 0.006, 0.0095, 200, 340, 10, ry=0.0085)
            if all(inner.contains(Point(p)) for p in a):
                f.d(a, LINE_DETAIL * 0.8, ag, smooth=False)
    for sd, (S, E, W, H, d) in arms.items():
        def ww(out, inn): return (out, inn) if sd > 0 else (inn, out)
        o = 1 if sd > 0 else -1
        sl = f.s("armour", tube([(*along(S, d, -0.020), *ww(0.0330, 0.0270)), (*along(S, d, 0.020), *ww(0.0340, 0.0290)),
                                 (*along(S, d, 0.050), *ww(0.0310, 0.0300))], cap=0.12), "scaleSleeve")
        for t in (0.012, 0.034):
            f.d(arc(*along(S, d, t + 0.006), 0.0095, 200, 340, 10, ry=0.0085), LINE_DETAIL * 0.8, sl, smooth=False)
        f.d([along(S, d, 0.045, o * 0.031), along(S, d, 0.048, 0), along(S, d, 0.045, -o * 0.030)], LINE_DETAIL, sl)
    # wide belt with a bronze plate
    belt = coat.intersection(box(-1, P["beltY"][0], 1, P["beltY"][1])).union(rrect(0, sum(P["beltY"]) / 2, 0.172, P["beltY"][1] - P["beltY"][0], 0.003))
    blt = f.s("belt", belt, "belt")
    if not back:
        f.d([(-0.010, 0.4430), (-0.010, 0.4580), (0.010, 0.4580), (0.010, 0.4430), (-0.010, 0.4430)], LINE_DETAIL, blt, smooth=False)
    # fists: right around the spear, left behind the shield grip
    fist(f, grip, d, -1, 0.046)
    S2, E2, W2, H2, d2 = arms[1]
    lgrip = along(W2, d2, 0.030)
    fist(f, lgrip, d2, 1, 0.046)
    if not back:
        sc = along(W2, d2, 0.006)
        f.s("shieldRim", Point(sc).buffer(P["shieldR"], 64), "shieldRim")
        f.s("shield", Point(sc).buffer(P["shieldR"] - 0.0110, 64), "shield")
        sg = f.shapes[-1][1]
        f.d(arc(*sc, P["shieldR"] - 0.026, 0, 360, 48), LINE_DETAIL, None, smooth=False)                    # embossed ring
        for a in range(0, 360, 45):
            f.ink.append(Point(sc[0] + (P["shieldR"] - 0.0175) * math.cos(math.radians(a)),
                               sc[1] + (P["shieldR"] - 0.0175) * math.sin(math.radians(a))).buffer(0.0018))   # rivets (concept)
        f.s("shieldBoss", Point(sc).buffer(0.0170, 48), "shieldBoss")
    else:
        sc = along(W2, d2, 0.006)
        f.s("shieldRim", Point(sc).buffer(P["shieldR"], 64), "shieldRim")
        sb = f.s("shield", Point(sc).buffer(P["shieldR"] - 0.0060, 64), "shieldInside")
        f.s("belt", box(sc[0] - 0.050, sc[1] - 0.007, sc[0] + 0.050, sc[1] + 0.007).intersection(Point(sc).buffer(P["shieldR"] - 0.008)), "shieldStrap")
        fist(f, lgrip, d2, 1, 0.046)
    G["shieldCentre"] = [round(sc[0], 4), round(sc[1], 4)]
    goliath_head_shapes(f, back)
    return f, arms, grip, lgrip


# ---------------------------------------------------------------------------------------------- side views
def side_david():
    """Profile from the character's right (camera at -X), +Z to the image right."""
    f = Fig()
    # far leg + near leg (thigh, knee forward, calf back)
    for dz, reg in ((0.0035, "skin"), (0.0, "skin")):
        ax = [(dz + 0.000, 0.150, 0.0110, 0.0120), (dz + 0.002, 0.118, 0.0090, 0.0098), (dz + 0.0035, 0.083, 0.0068, 0.0072),
              (dz + 0.0005, 0.060, 0.0058, 0.0095), (dz - 0.0005, 0.036, 0.0050, 0.0060), (dz - 0.001, 0.018, 0.0045, 0.0045)]
        f.s(reg, tube(ax), "leg")
        foot = blob([(dz - 0.0060, 0.0170), (dz + 0.0040, 0.0170), (dz + 0.0200, 0.0080), (dz + 0.0330, 0.0040),
                     (dz + 0.0345, 0.0005), (dz - 0.0080, 0.0000), (dz - 0.0100, 0.0060)])
        f.s("skin", foot, "foot")
        f.s("sandals", foot.intersection(box(-1, -1, 1, 0.0045)).union(
            LineString([(dz + 0.004, 0.0135), (dz + 0.016, 0.0095)]).buffer(0.0020).intersection(foot)), "sandal")
    f.s("bag", blob([(0.0050, 0.1640), (0.0170, 0.1660), (0.0200, 0.1530), (0.0160, 0.1420), (0.0050, 0.1410)]), "bag (far hip)")
    f.s("skin", blob([(-0.0060, 0.2480), (0.0070, 0.2460), (0.0090, 0.2300), (-0.0080, 0.2270)]), "neck")
    tunic = blob([(-0.0100, 0.2300), (0.0080, 0.2300), (0.0135, 0.2170), (0.0140, 0.2000), (0.0120, 0.1790), (0.0140, 0.1650),
                  (0.0190, 0.1300), (0.0235, 0.0970), (0.0000, 0.0940), (-0.0220, 0.0970), (-0.0180, 0.1300),
                  (-0.0120, 0.1650), (-0.0100, 0.1800), (-0.0135, 0.2050), (-0.0130, 0.2200)])
    tg = f.s("tunic", tunic, "tunic")
    f.s("belt", tunic.intersection(box(-1, D["beltY"][0], 1, D["beltY"][1])), "sash")
    f.d([(0.008, 0.166), (0.012, 0.130), (0.016, 0.104)], LINE_DETAIL * 0.8, tg)
    f.d([(-0.006, 0.166), (-0.010, 0.130), (-0.014, 0.104)], LINE_DETAIL * 0.8, tg)
    # arm hangs (45 deg out of this plane): seen vertical, slight forward bend at the elbow
    arm = tube([(0.0, 0.222, 0.0075, 0.0075), (0.0005, 0.200, 0.0062, 0.0066), (0.0015, 0.1825, 0.0052, 0.0052),
                (0.0035, 0.1650, 0.0058, 0.0055), (0.0050, 0.1520, 0.0040, 0.0038)])
    f.s("skin", arm, "arm")
    f.s("tunic", tube([(0.0, 0.226, 0.0090, 0.0090), (0.0004, 0.2045, 0.0082, 0.0082)], cap=0.15), "sleeve")
    fist(f, (0.0060, 0.1420), (0.15, -0.99), -1, 0.0185)
    f.s("sling", Polygon([(0.0040, 0.1340), (0.0080, 0.1340), (0.0110, 0.0840), (0.0010, 0.0840)]).buffer(0.0008), "slingCords")
    f.s("sling", ell(0.0060, 0.0770, 0.0060, 0.0090), "slingPouch")
    # head: profile with brow ridge, nose, lips, chin, jaw angle, skull
    head = blob([(0.0, 0.2945), (0.0120, 0.2920), (0.0190, 0.2850), (0.0212, 0.2770), (0.0208, 0.2725), (0.0196, 0.2690),
                 (0.0215, 0.2620), (0.0242, 0.2575), (0.0215, 0.2552), (0.0218, 0.2525), (0.0208, 0.2500), (0.0212, 0.2470),
                 (0.0196, 0.2430), (0.0150, 0.2410), (0.0060, 0.2440), (0.0005, 0.2500), (-0.0050, 0.2560),
                 (-0.0170, 0.2620), (-0.0235, 0.2740), (-0.0215, 0.2860), (-0.0130, 0.2925)])
    f.s("skin", head, "head")
    hair = blob([(-0.0050, 0.3005), (0.0110, 0.2990), (0.0200, 0.2905), (0.0215, 0.2830), (0.0150, 0.2840), (0.0080, 0.2790),
                 (0.0040, 0.2700), (0.0015, 0.2610), (-0.0040, 0.2620), (-0.0090, 0.2580), (-0.0200, 0.2560), (-0.0265, 0.2660),
                 (-0.0275, 0.2800), (-0.0220, 0.2930)])
    f.s("hair", hair, "hair")
    f.s("skin", ell(-0.0020, 0.2640, 0.0040, 0.0065, -8), "ear")
    f.fl([(0.0125, 0.2735), (0.0170, 0.2750), (0.0200, 0.2735)], LINE_FACE * 1.3)
    f.ink.append(ell(0.0170, 0.2675, 0.0012, 0.0016))
    f.fl([(0.0130, 0.2690), (0.0170, 0.2700), (0.0195, 0.2685)])
    f.fl([(0.0205, 0.2495), (0.0180, 0.2497)], LINE_FACE)
    return f


def side_goliath():
    f = Fig()
    # spear on the near side, in front of the arm line
    sx = 0.010
    f.s("spearShaft", box(sx - 0.0095, 0.030, sx + 0.0095, 0.836), "spearShaft")
    f.s("spearShaft", rrect(sx, 0.840, 0.0260, 0.0160, 0.004), "spearCollar")
    f.s("spearHead", blob([(sx, 0.9550), (sx + 0.0050, 0.9000), (sx + 0.0040, 0.8550), (sx - 0.0040, 0.8550), (sx - 0.0050, 0.9000)]), "spearHead (edge-on)")
    for dz in (0.006, 0.0):
        ax = [(dz, 0.330, 0.0330, 0.0360), (dz + 0.004, 0.270, 0.0300, 0.0300), (dz + 0.008, 0.209, 0.0230, 0.0215),
              (dz + 0.002, 0.150, 0.0200, 0.0300), (dz - 0.002, 0.090, 0.0160, 0.0180), (dz - 0.003, 0.050, 0.0150, 0.0150)]
        f.s("skin", tube(ax), "leg")
        f.s("feet", blob([(dz - 0.0200, 0.0620), (dz + 0.0130, 0.0620), (dz + 0.0200, 0.0350), (dz + 0.0700, 0.0180),
                          (dz + 0.0880, 0.0100), (dz + 0.0880, 0.0000), (dz - 0.0260, 0.0000), (dz - 0.0270, 0.0250)]), "boot")
        f.s("greaves", blob([(dz + 0.0300, 0.1980), (dz + 0.0340, 0.1500), (dz + 0.0250, 0.0700), (dz + 0.0180, 0.0550),
                             (dz - 0.0100, 0.0560), (dz - 0.0060, 0.1200), (dz + 0.0050, 0.1950)]), "greave (front shell)")
    f.s("kilt", blob([(-0.0650, 0.4000), (0.0700, 0.4000), (0.0820, 0.3300), (0.0920, 0.2640), (0.0, 0.2600),
                      (-0.0880, 0.2640), (-0.0780, 0.3300)]), "kilt")
    f.s("skin", blob([(-0.0280, 0.6750), (0.0250, 0.6700), (0.0300, 0.6300), (-0.0380, 0.6250)]), "neck")
    coat = blob([(-0.0480, 0.6380), (0.0300, 0.6380), (0.0600, 0.6150), (0.0780, 0.5600), (0.0800, 0.5100), (0.0700, 0.4600),
                 (0.0700, 0.4100), (0.0820, 0.3650), (0.0000, 0.3600), (-0.0800, 0.3650), (-0.0700, 0.4200),
                 (-0.0680, 0.4800), (-0.0750, 0.5500), (-0.0700, 0.6100)])
    ag = f.s("armour", coat, "armourCoat")
    for row, y in enumerate([0.598, 0.574, 0.550, 0.526, 0.502, 0.478, 0.418, 0.394, 0.372]):
        off = 0.0 if row % 2 == 0 else 0.0105
        for i in range(-6, 7):
            a = arc(i * 0.021 + off, y + 0.006, 0.0095, 200, 340, 10, ry=0.0085)
            if all(coat.buffer(-0.008).contains(Point(p)) for p in a):
                f.d(a, LINE_DETAIL * 0.8, ag, smooth=False)
    f.s("belt", coat.intersection(box(-1, G["beltY"][0], 1, G["beltY"][1])), "belt")
    arm = tube([(0.0, 0.610, 0.0300, 0.0300), (0.002, 0.560, 0.0270, 0.0260), (0.005, 0.5054, 0.0200, 0.0200),
                (0.009, 0.470, 0.0230, 0.0215), (0.011, 0.4262, 0.0160, 0.0150)])
    f.s("skin", arm, "arm")
    f.s("bracers", tube([(0.008, 0.474, 0.0220, 0.0205), (0.011, 0.430, 0.0165, 0.0155)], cap=0.1), "bracer")
    f.s("armour", tube([(0.0, 0.628, 0.0330, 0.0330), (0.001, 0.570, 0.0320, 0.0320)], cap=0.12), "scaleSleeve")
    fist(f, (sx, 0.4040), (0.0, -1.0), -1, 0.046)
    f.hidden.append(box(-0.012, 0.37, 0.004, 0.52))                    # shield on the far side, hidden
    head = blob([(0.0, 0.7460), (0.0260, 0.7420), (0.0380, 0.7300), (0.0420, 0.7130), (0.0440, 0.7060), (0.0410, 0.6990),
                 (0.0450, 0.6900), (0.0505, 0.6830), (0.0460, 0.6790), (0.0440, 0.6700), (0.0420, 0.6600), (0.0360, 0.6480),
                 (0.0200, 0.6450), (0.0050, 0.6550), (-0.0050, 0.6700), (-0.0280, 0.6850), (-0.0440, 0.7050),
                 (-0.0420, 0.7300), (-0.0250, 0.7430)])
    f.s("skin", head, "head")
    f.s("beard", blob([(0.0380, 0.6780), (0.0470, 0.6720), (0.0460, 0.6500), (0.0400, 0.6330), (0.0250, 0.6220),
                       (0.0050, 0.6300), (-0.0020, 0.6550), (0.0000, 0.6780), (0.0150, 0.6800), (0.0300, 0.6740)]), "beard")
    f.s("skin", ell(-0.0030, 0.6930, 0.0070, 0.0120, -8), "ear")
    f.s("helmet", blob([(-0.0050, 0.7680), (0.0250, 0.7650), (0.0420, 0.7500), (0.0480, 0.7240), (0.0440, 0.7150),
                        (0.0, 0.7150), (-0.0300, 0.7100), (-0.0550, 0.6900), (-0.0600, 0.6820), (-0.0520, 0.7150),
                        (-0.0450, 0.7450), (-0.0280, 0.7620)]), "helmet + neck guard")
    f.s("crest", blob([(-0.0700, 0.7700), (-0.0450, 0.7920), (0.0000, 0.8000), (0.0300, 0.7930), (0.0350, 0.7720),
                       (0.0000, 0.7640), (-0.0400, 0.7600)]), "crest (seen side-on)")
    f.fl([(0.0280, 0.7085), (0.0360, 0.7100), (0.0420, 0.7070)], LINE_FACE * 2)
    f.ink.append(ell(0.0355, 0.6995, 0.0022, 0.0030))
    return f


# ---------------------------------------------------------------------------------------------- SVG
def path_d(g, T):
    out = []
    for p in polys(g):
        for ring in [p.exterior] + list(p.interiors):
            pts = [T(x, y) for x, y in ring.coords]
            out.append("M" + " L".join(f"{a:.2f},{b:.2f}" for a, b in pts) + " Z")
    return " ".join(out)


def line_d(l, T):
    return "M" + " L".join(f"{a:.2f},{b:.2f}" for a, b in (T(x, y) for x, y in l.coords))


def fig_svg(f, T, s, colours=None, outline=LINE_OUTER, detail=True, shade=0.0, face=True, ink=True, lw=1.0):
    """colours=None -> line art (white fills). s = px per unit. shade > 0 adds a soft form shadow (concept art only)."""
    out = []
    s0 = s
    outline = outline * lw
    for region, g, tag in f.shapes:
        fill = "#ffffff" if colours is None else colours[region][0]
        out.append(f'<path d="{path_d(g, T)}" fill="{fill}" fill-rule="evenodd" stroke="{INK}" '
                   f'stroke-width="{outline * s:.2f}" stroke-linejoin="round"/>')
        if shade and colours is not None:
            k = shade
            lit = affinity.translate(g, -k, k)
            sh = g.difference(lit)
            if not sh.is_empty:
                out.append(f'<path d="{path_d(sh, T)}" fill="{mix(fill, SHADE_TO, 0.30)}" fill-opacity="0.75" stroke="none"/>')
            hl = g.difference(affinity.translate(g, k * 0.6, -k * 0.6))
            if not hl.is_empty:
                out.append(f'<path d="{path_d(hl, T)}" fill="#ffffff" fill-opacity="0.22" stroke="none"/>')
            out.append(f'<path d="{path_d(g, T)}" fill="none" stroke="{INK}" stroke-width="{outline * s:.2f}" stroke-linejoin="round"/>')
    if detail:
        for l, w, _ in f.decor:
            out.append(f'<path d="{line_d(l, T)}" fill="none" stroke="{INK}" stroke-width="{w * s * lw:.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
    if face:
        for l, w in f.face:
            out.append(f'<path d="{line_d(l, T)}" fill="none" stroke="{INK}" stroke-width="{w * s * max(lw, 0.6):.2f}" stroke-linecap="round" stroke-linejoin="round"/>')
    if ink:
        for g in f.ink:
            out.append(f'<path d="{path_d(g, T)}" fill="{INK}"/>')
    for g, c in f.paint:
        out.append(f'<path d="{path_d(g, T)}" fill="{c}"/>')
    for g in f.hidden:
        out.append(f'<path d="{path_d(g, T)}" fill="none" stroke="{INK}" stroke-width="{0.003 * s:.2f}" stroke-dasharray="{0.008 * s:.1f} {0.006 * s:.1f}"/>')
    return "\n".join(out)


def svg_doc(w, h, body, bg="#FBF5E6"):
    bgr = f'<rect width="{w}" height="{h}" fill="{bg}"/>\n' if bg else ""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">\n{bgr}'
            '<style>text{font-family:"Hiragino Sans GB","PingFang SC","Helvetica Neue",sans-serif;fill:#2B2118}'
            '.kai{font-family:"Kaiti SC","STKaiti",serif}.small{font-size:20px;fill:#6B5B4A}</style>\n'
            f'{body}\n</svg>\n')


def write_svg_png(name, w, h, body, bg="#FBF5E6", transparent=False):
    svg = os.path.join(HERE, name + ".svg"); png = os.path.join(HERE, name + ".png")
    doc = svg_doc(w, h, body, None if transparent else bg)
    ET.fromstring(doc)                       # fail loudly on malformed SVG (Chrome would render an error box)
    open(svg, "w").write(doc)
    if os.path.exists(png): os.remove(png)
    args = [CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
            f"--window-size={w},{h}", f"--screenshot={png}"]
    if transparent: args.append("--default-background-color=00000000")
    subprocess.run(args + ["file://" + svg], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return png


def mapper(ox, oy, s):
    return lambda x, y: (ox + x * s, oy - y * s)


def text(x, y, t, size=24, anchor="middle", cls="", weight="normal", fill=None):
    f = f' fill="{fill}"' if fill else ""
    return f'<text x="{x}" y="{y}" font-size="{size}" text-anchor="{anchor}" font-weight="{weight}" class="{cls}"{f}>{escape(str(t))}</text>'


# ---------------------------------------------------------------------------------------------- turnarounds
def render_turnaround(name, front, side, back, char, title, sub, s, shade):
    """front line art | front demo colour | side | back. Back is drawn as seen from behind (mirrored)."""
    backm = back.mirrored()
    views = [(front, "正面 · 线稿 front line art", None), (front, "正面 · 示范上色 front", PALETTE[char]),
             (side, "侧面 · 朝右 side (faces +Z →)", PALETTE[char]), (backm, "背面 back", PALETTE[char])]
    bounds = [v[0].silhouette().bounds for v in views]
    y1 = max(b[3] for b in bounds)
    pad = 60; H = y1 * s
    widths = [(b[2] - b[0]) * s for b in bounds]
    W = int(pad * (len(views) + 1) + sum(widths)) + 40; Ht = int(H + 190)
    base = Ht - 64
    body = [text(pad, 50, title, 36, "start", weight="bold"), text(pad, 84, sub, 21, "start", "small")]
    x = pad
    for (f, label, col), b, w in zip(views, bounds, widths):
        T = mapper(x - b[0] * s, base, s)
        body.append(fig_svg(f, T, s, col, shade=shade if col else 0.0, lw=min(1.0, 1150 / s)))
        body.append(text(x + w / 2, base + 42, label, 20, "middle", "small"))
        x += w + pad
    body.append(f'<line x1="{pad / 2}" y1="{base}" x2="{W - pad / 2}" y2="{base}" stroke="#6B5B4A" stroke-width="2"/>')
    P = D if char == "david" else G
    hu = P["skullTop"] - P["chin"]
    rx = W - 30
    for i in range(int(P["skullTop"] / hu) + 2):
        yy = base - min(i * hu, P["skullTop"]) * s
        body.append(f'<line x1="{rx - 16}" y1="{yy:.1f}" x2="{rx}" y2="{yy:.1f}" stroke="#E8553D" stroke-width="2"/>')
    body.append(f'<line x1="{rx - 8}" y1="{base}" x2="{rx - 8}" y2="{base - P["skullTop"] * s:.1f}" stroke="#E8553D" stroke-width="2"/>')
    body.append(text(rx - 20, base - P["skullTop"] * s - 10, f'{P["headsTall"]} 头', 18, "end", fill="#E8553D"))
    write_svg_png(name, W, Ht, "\n".join(body))


# ---------------------------------------------------------------------------------------------- faces (decals, §11)
# The face is modelled (brow ridge, nose, cheekbones, lips volume, chin, ears). Eyes, brows and mouth are UV1 decals,
# one transparent PNG per expression, so clipExpression keeps working and the app's line-erase cannot wipe them.
FACE_DECAL = {"david": {"rect": [-0.0175, 0.2425, 0.0175, 0.2775], "px": 512},
              "goliath": {"rect": [-0.0340, 0.6550, 0.0340, 0.7230], "px": 512}}
CLIP_EXPR = {"david": {"idle": "brave", "walk": "brave", "talk": "talk", "kneel_pick": "brave", "sling_windup": "brave",
                       "sling_release": "wow", "run": "brave", "victory": "victory", "pray": "pray"},
             "goliath": {"idle": "grumpy", "walk": "grumpy", "talk": "grumpy", "taunt": "taunt", "laugh": "laugh",
                         "roar": "roar", "charge": "roar", "hit_react": "dizzy", "fall": "dizzy", "down": "down"}}
EXPRS = {"david": ["brave", "kind", "talk", "pray", "victory", "wow"],
         "goliath": ["grumpy", "taunt", "laugh", "roar", "dizzy", "down"]}
MOUTH_IN = "#7A2622"; TONGUE = "#D9675C"; IRIS = {"david": "#6B4A2B", "goliath": "#4A3524"}
BROW = {"david": "#6E3418", "goliath": "#3A2416"}


def face_decal(char, expr):
    """Paint layers (geom, colour) for one expression, character-local coordinates."""
    if char == "david":
        ex, ey, erx, ery = 0.0080, 0.2672, 0.0043, 0.0025; by, bth, bx0, bx1 = 0.2722, 0.0011, 0.0035, 0.0135
        my, mw = 0.2497, 0.0056; ir = 0.0021
    else:
        ex, ey, erx, ery = 0.0165, 0.6995, 0.0072, 0.0038; by, bth, bx0, bx1 = 0.7065, 0.0026, 0.0055, 0.0300
        my, mw = 0.6650, 0.0105; ir = 0.0031
    L = []
    lid = ery * 0.45

    def eye(sx, mode):
        cx = sx * ex
        if mode in ("open", "wide"):
            k = 1.35 if mode == "wide" else 1.0
            white = ell(cx, ey, erx, ery * k)
            L.append((white.buffer(lid * 0.5), INK)); L.append((white, "#FFFFFF"))
            L.append((Point(cx, ey - ery * 0.05).buffer(ir * (0.75 if mode == "wide" else 1.0)).intersection(white), IRIS[char]))
            L.append((Point(cx, ey - ery * 0.05).buffer(ir * (0.36 if mode == "wide" else 0.5)), INK))
            L.append((Point(cx + ir * 0.35, ey + ir * 0.35).buffer(ir * 0.28), "#FFFFFF"))
            L.append((LineString(cr(arc(cx, ey, erx * 1.05, 165, 15, 10, ry=ery * k * 1.05), False, 3)).buffer(lid * 0.9), INK))
        elif mode == "closed":
            L.append((LineString(arc(cx, ey + ery * 0.2, erx, 200, 340, 12, ry=ery * 0.8)).buffer(lid), INK))
        elif mode == "happy":
            L.append((LineString(arc(cx, ey - ery * 0.6, erx, 20, 160, 12, ry=ery * 1.3)).buffer(lid * 1.1), INK))
        elif mode == "swirl":
            pts = [(cx + erx * 0.12 * t * math.cos(t * 0.55), ey + erx * 0.12 * t * math.sin(t * 0.55)) for t in range(0, 9)]
            pts = [(cx + (x - cx) * 1.0, ey + (y - ey) * 0.9) for x, y in pts]
            L.append((LineString(cr(pts, False, 4)).buffer(lid * 0.8), INK))

    def brow(sx, yi, yo, th=bth):
        L.append((tube([(sx * bx0, by + yi, th * 0.55, th * 0.55), (sx * (bx0 + bx1) / 2, by + (yi + yo) / 2 + th * 0.4, th * 0.6, th * 0.6),
                        (sx * bx1, by + yo, th * 0.35, th * 0.35)], cap=0.6), BROW[char]))

    def mouth_line(pts, th):
        L.append((LineString(cr(pts, False, 6)).buffer(th), INK))

    def mouth_open(g, tongue=True):
        L.append((g.buffer(lid * 0.6), INK)); L.append((g, MOUTH_IN))
        if tongue:
            b = g.bounds
            L.append((ell((b[0] + b[2]) / 2, b[1] + (b[3] - b[1]) * 0.2, (b[2] - b[0]) * 0.3, (b[3] - b[1]) * 0.28).intersection(g), TONGUE))

    u = ery                                     # unit for brow offsets
    th = lid * 0.75
    if char == "david":
        if expr == "brave":
            for sx in (-1, 1): eye(sx, "open"); brow(sx, -0.6 * u, 0.3 * u)
            mouth_line([(-mw, my + 0.0004), (-mw * 0.4, my - 0.0003), (mw * 0.4, my - 0.0002), (mw * 1.05, my + 0.0010)], th)
        elif expr == "kind":
            for sx in (-1, 1): eye(sx, "open"); brow(sx, 0.5 * u, 0.0)
            mouth_line([(-mw, my + 0.0008), (-mw * 0.4, my - 0.0006), (mw * 0.4, my - 0.0006), (mw, my + 0.0008)], th)
        elif expr == "talk":
            for sx in (-1, 1): eye(sx, "open"); brow(sx, 0.2 * u, 0.2 * u)
            mouth_open(ell(0, my - 0.0012, mw * 0.65, 0.0020))
        elif expr == "pray":
            for sx in (-1, 1): eye(sx, "closed"); brow(sx, 0.6 * u, 0.0)
            mouth_line([(-mw * 0.6, my), (0, my - 0.0004), (mw * 0.6, my)], th * 0.9)
        elif expr == "victory":
            for sx in (-1, 1): eye(sx, "happy"); brow(sx, 0.9 * u, 0.5 * u)
            mouth_open(Polygon(arc(0, my + 0.0006, mw * 1.05, 180, 360, 16, ry=0.0034)))
        elif expr == "wow":
            for sx in (-1, 1): eye(sx, "wide"); brow(sx, 1.4 * u, 1.0 * u)
            mouth_open(ell(0, my - 0.0012, 0.0024, 0.0028), tongue=False)
    else:
        if expr == "grumpy":
            for sx in (-1, 1): eye(sx, "open"); brow(sx, -1.0 * u, 0.4 * u, bth * 1.15)
            mouth_line([(-mw, my - 0.0020), (-mw * 0.4, my + 0.0002), (mw * 0.4, my + 0.0002), (mw, my - 0.0020)], th * 1.2)
        elif expr == "taunt":
            eye(-1, "happy"); eye(1, "open"); brow(-1, -0.8 * u, 0.0); brow(1, 0.9 * u, 1.2 * u)
            m = affinity.translate(affinity.rotate(Polygon(arc(0, 0, mw * 1.05, 180, 360, 16, ry=0.0050)), 10, origin=(0, 0)), 0.0015, my + 0.0010)
            mouth_open(m)
        elif expr == "laugh":
            for sx in (-1, 1): eye(sx, "happy"); brow(sx, 0.7 * u, 0.5 * u)
            mouth_open(Polygon(arc(0, my + 0.0012, mw * 1.2, 180, 360, 16, ry=0.0090)))
        elif expr == "roar":
            for sx in (-1, 1): eye(sx, "wide"); brow(sx, -1.5 * u, 0.6 * u, bth * 1.35)
            mouth_open(ell(0, my - 0.0030, mw * 0.85, 0.0070))
        elif expr == "dizzy":
            for sx in (-1, 1): eye(sx, "swirl"); brow(sx, 0.6 * u, 0.2 * u)
            mouth_line([(-mw, my), (-mw * 0.4, my + 0.0016), (mw * 0.2, my - 0.0012), (mw, my + 0.0010)], th)
        elif expr == "down":
            for sx in (-1, 1): eye(sx, "closed"); brow(sx, 1.0 * u, -0.4 * u)
            mouth_open(ell(0, my - 0.0018, 0.0034, 0.0036), tongue=False)
    return L


def render_face_decals():
    os.makedirs(os.path.join(HERE, "faces"), exist_ok=True)
    for fn in os.listdir(os.path.join(HERE, "faces")):
        os.remove(os.path.join(HERE, "faces", fn))
    out = {}
    for char in ("david", "goliath"):
        x0, y0, x1, y1 = FACE_DECAL[char]["rect"]; n = FACE_DECAL[char]["px"]; s = n / (x1 - x0)
        T = mapper(-x0 * s, y1 * s, s)
        files = {}
        for ex in EXPRS[char]:
            body = "\n".join(f'<path d="{path_d(g, T)}" fill="{c}"/>' for g, c in face_decal(char, ex))
            name = f"faces/{char}_{ex}"
            write_svg_png(name, n, n, body, transparent=True)
            files[ex] = f"docs/david-goliath/design/{name}.png"
        out[char] = {"rectLocal": FACE_DECAL[char]["rect"], "px": n, "files": files, "clipExpression": CLIP_EXPR[char],
                     "default": EXPRS[char][0],
                     "layers": "eye whites, irises, pupils, highlights, lids, brows, mouth (closed line or open with interior); "
                               "NOT nose/ears/cheeks/lips volume (modelled)"}
    return out


def head_fig(char):
    f = Fig()
    if char == "david":
        f.s("skin", mirror_blob([(0, 0.2470), (0.0085, 0.2465), (0.0090, 0.2370), (0.0120, 0.2300), (0.0220, 0.2268),
                                 (0.0200, 0.2250), (0, 0.2240)]), "neck")
        f.s("tunic", mirror_blob([(0, 0.2280), (0.0080, 0.2312), (0.0170, 0.2300), (0.0280, 0.2262), (0.0300, 0.2200), (0, 0.2180)]), "tunic")
        david_head_shapes(f)
        f.d([(0.0016, 0.2655), (0.0022, 0.2600), (0.0032, 0.2568), (0.0016, 0.2556)], LINE_FACE * 0.8)        # nose (modelled)
        f.d([(-0.0030, 0.2560), (-0.0012, 0.2553), (0.0012, 0.2553), (0.0030, 0.2560)], LINE_FACE * 0.8)
    else:
        f.s("skin", mirror_blob([(0, 0.6700), (0.0270, 0.6690), (0.0300, 0.6450), (0.0450, 0.6340), (0.0760, 0.6250),
                                 (0.0700, 0.6150), (0, 0.6100)]), "neck")
        f.s("armour", mirror_blob([(0, 0.6300), (0.0300, 0.6380), (0.0700, 0.6320), (0.0900, 0.6200), (0.0900, 0.6000), (0, 0.6000)]), "armour")
        goliath_head_shapes(f, face=False)
        f.d([(0.0040, 0.6990), (0.0058, 0.6900), (0.0085, 0.6840), (0.0060, 0.6815)], LINE_FACE * 1.1)
        f.d([(-0.0060, 0.6815), (-0.0030, 0.6800), (0.0030, 0.6800), (0.0060, 0.6815)], LINE_FACE)
    return f


def render_expressions():
    labels = {"brave": "勇敢 brave（默认）", "kind": "温和 kind", "talk": "说话 talk", "pray": "祷告 pray", "victory": "得胜 victory",
              "wow": "惊讶 wow", "grumpy": "凶 grumpy（默认）", "taunt": "嘲笑 taunt", "laugh": "大笑 laugh", "roar": "吼 roar",
              "dizzy": "晕 dizzy", "down": "倒下 down"}
    cell = 300; W = cell * 6 + 80; Hh = 2 * (cell + 70) + 120
    body = [text(40, 50, "表情 Expressions — 鼻子/耳朵/颧骨/嘴唇体积是建模；眼睛、眉毛、嘴是 UV1 贴花（每个动作一个表情）", 26, "start", weight="bold")]
    for row, char in enumerate(("david", "goliath")):
        cyu, s = (0.270, 4300) if char == "david" else (0.708, 2050)
        for i, ex in enumerate(EXPRS[char]):
            f = head_fig(char)
            f.paint = face_decal(char, ex)
            if char == "goliath" and ex == "dizzy":
                for dx, dy in ((-0.052, 0.752), (0.054, 0.756), (-0.060, 0.728)):
                    st = Polygon([(dx + 0.009 * math.cos(math.radians(90 + 144 * j)), dy + 0.009 * math.sin(math.radians(90 + 144 * j))) for j in range(5)])
                    f.paint.append((st.convex_hull, "#FFC93C"))
            ox = 40 + i * cell + cell / 2; oy = 110 + row * (cell + 70) + cell / 2
            T = mapper(ox, oy + cyu * s, s)
            body.append(f'<clipPath id="c{row}{i}"><rect x="{ox - cell / 2 + 8}" y="{oy - cell / 2}" width="{cell - 16}" height="{cell}" rx="18"/></clipPath>')
            body.append(f'<rect x="{ox - cell / 2 + 8}" y="{oy - cell / 2}" width="{cell - 16}" height="{cell}" rx="18" fill="#ffffff" stroke="#E4D3AE" stroke-width="3"/>')
            body.append(f'<g clip-path="url(#c{row}{i})">' + fig_svg(f, T, s, PALETTE[char], shade=0.0012 if char == "david" else 0.0025, lw=0.35 if char == "david" else 0.7) + '</g>')
            body.append(text(ox, oy + cell / 2 + 36, labels[ex], 22))
    write_svg_png("expressions", W, Hh, "\n".join(body))


# ---------------------------------------------------------------------------------------------- desert set (§12)
# CONTRACT §12 (desert boost, 2026-10-27). Two kinds of desert pieces:
#   FRONT pieces (upright scenery: far hills with the camps, dunes, rocks, shrub) are drawn on the sheet as SIDE VIEWS,
#   like the characters, and wear the scan by FRONT projection:  u = x / scale + sheetX + 0.5,
#   v = (y / scale + sheetY) / artHeightUnits, for a 3D point (x, y, z) (page x, height), whatever its z.
#   The characters are the case scale = 1 (with character-local x). Far panorama: scale 2.5, sheetY 1.000.
#   Midground pieces: scale 1, sheetY = their front foot (they stand on their own drawing).
#   GROUND pieces (brook, five stones) stay top-down, as in §11.9.
# 3D coordinates here: x (page x), y (height), d = -z (distance behind the art rect's bottom edge, = sheet ys).
PANO = {"scale": 2.5, "sheetX": 0.0, "sheetY": 1.000}
PANO_DEPTH = {"front": 0.98, "crestFrom": 1.28, "crestTo": 1.42, "back": 1.475}
TENT = {"w": 0.110, "h": 0.095, "skirt": 0.012, "depth": [1.300, 1.410], "doorW": 0.044, "doorH": 0.052}
BANNER = {"pole": 0.140, "poleD": 1.360, "clothW": 0.090, "clothH": 0.060}
EDGE_MIN_PX = 6.0 / 25.4 * 150            # 6 mm at 150 dpi: lowest / outermost ink (markers excepted)


def sil_from_top(pts, n=10):
    """(n = 1: straight segments, for angular rocks)"""
    """Front silhouette from a list of top points (x, y), first and last on the ground (y = 0).
    Returns (polygon, (xs, ys) top curve sampled densely and sorted by x)."""
    curve = cr(pts, False, n) if n > 1 else list(pts)
    curve = [(x, max(0.0, y)) for x, y in curve]
    poly = Polygon(curve + [(pts[-1][0], 0.0), (pts[0][0], 0.0)]).buffer(0)
    xs = [p[0] for p in curve]; ys = [p[1] for p in curve]
    o = sorted(range(len(xs)), key=lambda i: xs[i])
    return poly, ([xs[i] for i in o], [ys[i] for i in o])


def top_at(top, x):
    xs, ys = top
    if x <= xs[0] or x >= xs[-1]: return 0.0
    for i in range(1, len(xs)):
        if xs[i] >= x:
            t = (x - xs[i - 1]) / max(1e-9, xs[i] - xs[i - 1]); return ys[i - 1] + (ys[i] - ys[i - 1]) * t
    return 0.0


def to_sheet(g, uvm):
    """3D front geometry (x, y) -> sheet (x, ys) for one front-UV mapping."""
    s = uvm["scale"]
    return affinity.translate(affinity.scale(g, 1 / s, 1 / s, origin=(0, 0)), uvm["sheetX"], uvm["sheetY"])


def build_desert():
    """Returns (fig in sheet coords, pieces). Each piece keeps its 3D description (Desert role) and its print."""
    f = Fig(); pieces = []
    order = []                                  # print order: (region, sheet geom, piece id)

    def front_piece(pid, kind, region, pts, uvm, depth, parts=None, decor=(), smooth=10, **kw):
        sil, top = sil_from_top(pts, smooth)
        g = to_sheet(sil, uvm)
        hmax = round(max(top[1]), 4)
        pc = dict(id=pid, kind=kind, region=region, mapping="front", frontUV=dict(uvm), sil3d=sil, top=top,
                  depth=dict(depth), geom=g, heightMax=hmax, parts={}, **kw)
        gs = f.s(region, g, pid)
        for preg, pg3 in (parts or {}).items():
            pg3 = pg3.intersection(sil)
            if pg3.is_empty: continue
            pc["parts"][preg] = pg3
            f.s(preg, to_sheet(pg3, uvm), pid)
        for line, w in decor:
            f.d([(x / uvm["scale"] + uvm["sheetX"], y / uvm["scale"] + uvm["sheetY"]) for x, y in line], w, gs)
        pieces.append(pc)
        return pc

    def slip_right(pts, crest_x, toe_dx):
        """lee (slip) face of a dune whose wind blows from the left: right of a line from the crest to the toe"""
        cy_ = max(y for _, y in pts)
        return Polygon([(crest_x, cy_ + 0.05), (crest_x, cy_), (crest_x + toe_dx * 0.4, cy_ * 0.45), (crest_x + toe_dx, -0.01),
                        (9, -0.01), (9, cy_ + 0.05)])

    def slip_left(pts, crest_x, toe_dx):
        cy_ = max(y for _, y in pts)
        return Polygon([(crest_x, cy_ + 0.05), (crest_x, cy_), (crest_x - toe_dx * 0.4, cy_ * 0.45), (crest_x - toe_dx, -0.01),
                        (-9, -0.01), (-9, cy_ + 0.05)])

    # ================= far panorama (scale 2.5): far dune in the valley mouth, two camp hills, tents, banners
    P = PANO; DP = PANO_DEPTH
    far_pts = [(-0.240, 0.0), (-0.170, 0.080), (-0.090, 0.160), (-0.020, 0.190), (0.050, 0.160), (0.120, 0.080), (0.190, 0.0)]
    front_piece("duneFar", "dune", "sand", far_pts, P,
                {"front": 1.380, "crestFrom": 1.430, "crestTo": 1.445, "back": 1.475}, group="pano",
                decor=[([(-0.10, 0.12), (-0.03, 0.15), (0.05, 0.12)], LINE_DETAIL)],
                note="far dune closing the valley between the two camp hills; only its middle shows")
    hi_pts = [(-0.590, 0.0), (-0.588, 0.070), (-0.578, 0.140), (-0.555, 0.205), (-0.515, 0.255), (-0.465, 0.288), (-0.400, 0.302),
              (-0.300, 0.306), (-0.210, 0.300), (-0.160, 0.290), (-0.122, 0.262), (-0.088, 0.200), (-0.058, 0.110), (-0.034, 0.040), (-0.018, 0.0)]
    hp_pts = [(-0.018, 0.0), (0.000, 0.060), (0.022, 0.170), (0.050, 0.280), (0.085, 0.350), (0.135, 0.376), (0.250, 0.382),
              (0.380, 0.378), (0.450, 0.365), (0.505, 0.330), (0.545, 0.275), (0.572, 0.200), (0.586, 0.110), (0.590, 0.0)]
    hI = front_piece("hillIsrael", "hill", "hillIsrael", hi_pts, P, DP, group="pano", camp="Israel (left, behind David)",
                     decor=[([(-0.55, 0.20), (-0.42, 0.235), (-0.30, 0.240), (-0.20, 0.225)], LINE_DETAIL),
                            ([(-0.50, 0.10), (-0.38, 0.13), (-0.26, 0.12)], LINE_DETAIL)])
    hP = front_piece("hillPhil", "hill", "hillPhil", hp_pts, P, DP, group="pano", camp="Philistines (right, behind Goliath)",
                     decor=[([(0.10, 0.25), (0.22, 0.30), (0.36, 0.305), (0.50, 0.29)], LINE_DETAIL),
                            ([(0.20, 0.14), (0.33, 0.17), (0.46, 0.16)], LINE_DETAIL)])
    T = TENT
    for camp, hill, reg, cxs in (("Israel", hI, "tentIsrael", (-0.430, -0.315, -0.200)), ("Phil", hP, "tentPhil", (0.135, 0.255, 0.395))):
        for k, cx in enumerate(cxs):
            w, th, sk = T["w"], T["h"], T["skirt"]
            base = round(min(top_at(hill["top"], cx + dx) for dx in (-w / 2, 0, w / 2)), 4)
            sag = 0.006
            tpts = [(cx - w / 2, base - sk), (cx + w / 2, base - sk), (cx + w / 2, base), (cx + w / 4 + sag * 0.3, base + th / 2 - sag),
                    (cx, base + th), (cx - w / 4 - sag * 0.3, base + th / 2 - sag), (cx - w / 2, base)]
            tri = Polygon(tpts).buffer(0)
            door = Polygon([(cx - T["doorW"] / 2, base), (cx + T["doorW"] / 2, base), (cx, base + T["doorH"])])
            pid = f"tent{camp}{k + 1}"
            g = to_sheet(tri, P)
            gs = f.s(reg, g, pid)
            f.s("tentDoor", to_sheet(door, P), pid)
            f.d([(cx / P["scale"], (base + T["doorH"] + 0.004) / P["scale"] + P["sheetY"]),
                 (cx / P["scale"], (base + th - 0.006) / P["scale"] + P["sheetY"])], LINE_DETAIL, gs, smooth=False)
            pieces.append(dict(id=pid, kind="tent", region=reg, mapping="front", frontUV=dict(P), sil3d=tri, group="pano",
                               top=([cx - w / 2, cx, cx + w / 2], [base, base + th, base]), geom=g, heightMax=round(base + th, 4),
                               parts={"tentDoor": door}, onHill=hill["id"],
                               tent={"centreX": cx, "baseY": base, "width": w, "height": th, "skirt": sk,
                                     "zGable": -T["depth"][0], "zBack": -T["depth"][1], "ridge": "along z (gable faces +Z)",
                                     "door": {"width": T["doorW"], "height": T["doorH"], "recess": 0.012}},
                               depth={"front": T["depth"][0], "crestFrom": T["depth"][0], "crestTo": T["depth"][1], "back": T["depth"][1]}))
    B = BANNER
    for camp, hill, reg, px, flip in (("Israel", hI, "flagIsrael", -0.148, 1), ("Phil", hP, "flagPhil", 0.080, -1)):
        base = round(top_at(hill["top"], px), 4)
        ty = base + B["pole"]
        cw, ch = B["clothW"], B["clothH"]
        cloth = blob([(px + flip * 0.004, ty - 0.002), (px + flip * cw, ty - 0.008), (px + flip * cw * 0.74, ty - ch * 0.5),
                      (px + flip * cw, ty - ch + 0.004), (px + flip * 0.004, ty - ch)], 6)
        g = to_sheet(cloth, P)
        f.s(reg, g, f"banner{camp}")
        f.d([(px / P["scale"], base / P["scale"] + P["sheetY"]), (px / P["scale"], (ty + 0.006) / P["scale"] + P["sheetY"])],
            LINE_DETAIL, None, smooth=False)
        pieces.append(dict(id=f"banner{camp}", kind="banner", region=reg, mapping="front", frontUV=dict(P), sil3d=cloth,
                           group="pano", top=None, geom=g, heightMax=round(ty + 0.006, 4), parts={}, onHill=hill["id"],
                           banner={"poleBase3D": [px, base, -B["poleD"]], "poleHeight": B["pole"], "poleDiameter": 0.006,
                                   "cloth": f"{cw} x {ch}, swallow tail, flies toward {'+X (the Philistines)' if flip > 0 else '-X (Israel)'}",
                                   "poleUV": "constant: Goliath's printed spear shaft (wood), as §11.9"},
                           depth={"front": B["poleD"], "crestFrom": B["poleD"], "crestTo": B["poleD"], "back": B["poleD"]}))

    # ================= midground (scale 1, each stands on its own drawing: sheetY = its front foot)
    def mid(pid, kind, region, pts, d0, dc, dp, d1, **kw):
        return front_piece(pid, kind, region, pts, {"scale": 1.0, "sheetX": 0.0, "sheetY": d0},
                           {"front": d0, "crestFrom": dc, "crestTo": dp, "back": d1}, group=pid, **kw)

    # one wind for the whole valley, blowing from +X: every slip face (duneShade) faces -X. The phone looks at the left
    # dunes' gentle windward side (sand) and at dune3's slip face (the shaded valley wall on the right).
    d1p = [(-0.470, 0.0), (-0.459, 0.055), (-0.446, 0.110), (-0.430, 0.150), (-0.412, 0.168), (-0.392, 0.172), (-0.365, 0.163),
           (-0.335, 0.140), (-0.300, 0.105), (-0.268, 0.062), (-0.245, 0.028), (-0.228, 0.0)]
    mid("dune1", "dune", "sand", d1p, 0.370, 0.500, 0.530, 0.600, parts={"duneShade": slip_left(d1p, -0.405, 0.040)},
        decor=[([(-0.37, 0.120), (-0.33, 0.100), (-0.295, 0.070)], LINE_DETAIL), ([(-0.36, 0.060), (-0.32, 0.045), (-0.285, 0.022)], LINE_DETAIL)],
        note="dune behind David, wind from +X: rounded windward back toward the valley, steep slip face (duneShade) facing -X")
    d2p = [(-0.470, 0.0), (-0.461, 0.075), (-0.450, 0.150), (-0.436, 0.205), (-0.418, 0.236), (-0.398, 0.246), (-0.372, 0.240),
           (-0.340, 0.218), (-0.305, 0.178), (-0.272, 0.120), (-0.248, 0.062), (-0.226, 0.0)]
    mid("dune2", "dune", "sand", d2p, 0.600, 0.780, 0.830, 0.920, parts={"duneShade": slip_left(d2p, -0.402, 0.045)},
        decor=[([(-0.36, 0.195), (-0.32, 0.165), (-0.285, 0.120)], LINE_DETAIL), ([(-0.35, 0.110), (-0.31, 0.085), (-0.275, 0.050)], LINE_DETAIL)],
        note="taller dune behind dune1")
    d3p = [(0.225, 0.0), (0.236, 0.075), (0.250, 0.150), (0.268, 0.205), (0.290, 0.232), (0.315, 0.240), (0.345, 0.232),
           (0.380, 0.205), (0.415, 0.160), (0.442, 0.105), (0.460, 0.050), (0.470, 0.0)]
    mid("dune3", "dune", "sand", d3p, 0.720, 0.860, 0.900, 0.980, parts={"duneShade": slip_left(d3p, 0.300, 0.040)},
        decor=[([(0.36, 0.195), (0.40, 0.160), (0.43, 0.110)], LINE_DETAIL), ([(0.37, 0.110), (0.41, 0.080), (0.44, 0.040)], LINE_DETAIL)],
        note="dune on the Philistine side behind Goliath; its slip face (duneShade) faces the valley (-X)")

    def rock_pts(x0, x1, h, seed):
        w = x1 - x0
        j = 0.04 * math.sin(seed * 1.7)
        return [(x0, 0.0), (x0 + 0.03 * w, h * 0.50), (x0 + 0.13 * w, h * (0.84 + j)), (x0 + 0.30 * w, h * 0.93), (x0 + 0.55 * w, h),
                (x0 + 0.68 * w, h * 0.94), (x0 + 0.74 * w, h * 0.70), (x0 + 0.90 * w, h * (0.64 - j)), (x0 + 0.97 * w, h * 0.32), (x1, 0.0)]

    def rock(pid, x0, x1, h, d0, d1, seed):
        pts = rock_pts(x0, x1, h, seed); w = x1 - x0
        crack = [(x0 + 0.42 * w, h * 0.88), (x0 + 0.50 * w, h * 0.55), (x0 + 0.46 * w, h * 0.22)]
        return mid(pid, "rock", "rock", pts, d0, d0 + 0.012, d1 - 0.012, d1, decor=[(crack, LINE_DETAIL)], smooth=1,
                   note="sandstone block: steep walls, flat tilted top (front view = this outline)")

    rock("rockL1", -0.470, -0.366, 0.098, 0.935, 1.000, 1)
    rock("rockL2", -0.276, -0.234, 0.036, 0.950, 0.985, 2)
    rock("rockM1", -0.105, -0.006, 0.072, 0.740, 0.800, 3)
    rock("rockM2", 0.008, 0.045, 0.038, 0.760, 0.795, 4)
    rock("rockFR1", 0.405, 0.470, 0.050, 0.060, 0.130, 5)
    rock("rockFR2", 0.420, 0.468, 0.033, 0.160, 0.210, 6)
    sh = unary_union([Point(-0.322 + dx, dy).buffer(r, 16) for dx, dy, r in
                      ((0, 0.024, 0.016), (-0.015, 0.016, 0.012), (0.015, 0.016, 0.012), (0.004, 0.036, 0.011))]).intersection(box(-1, 0, 1, 1))
    shp = [(x, y) for x, y in sh.exterior.coords]
    sh_poly = Polygon(shp).buffer(0)
    uvm = {"scale": 1.0, "sheetX": 0.0, "sheetY": 0.940}
    g = to_sheet(sh_poly, uvm); gs = f.s("bush", g, "shrubL")
    f.d([(-0.322, 0.944), (-0.326, 0.962), (-0.334, 0.972)], LINE_DETAIL, gs)
    xs_ = sorted(set(round(x, 4) for x, _ in shp)); top = (xs_, [max(y for x, y in shp if abs(x - xx) < 0.003) for xx in xs_])
    pieces.append(dict(id="shrubL", kind="shrub", region="bush", mapping="front", frontUV=uvm, sil3d=sh_poly, top=top, group="shrubL",
                       geom=g, heightMax=round(sh_poly.bounds[3], 4), parts={},
                       depth={"front": 0.940, "crestFrom": 0.950, "crestTo": 0.965, "back": 0.975}, note="dry desert shrub"))

    # ================= ground (top-down, §11.9 rule): the brook and the five smooth stones, >= 6 mm from the page edge
    cl = cr([(-0.452, -0.012), (-0.433, -0.050), (-0.440, -0.090), (-0.422, -0.128), (-0.402, -0.165), (-0.392, -0.200)], False, 8)
    brook = LineString(cl).buffer(0.017, cap_style=1).intersection(box(-0.5, -0.190, 0.5, -0.012))
    wg = f.s("water", brook, "brook")
    for k in range(4):
        y = -0.035 - k * 0.042
        x = -0.437 + 0.010 * math.sin(k)
        f.d([(x - 0.006, y), (x, y - 0.003), (x + 0.007, y)], LINE_DETAIL * 0.9, wg)
    def cl_x(ys):
        hit = LineString(cl).intersection(LineString([(-0.6, ys), (-0.2, ys)]))
        return hit.x if hit.geom_type == "Point" else min(p.x for p in hit.geoms)
    stones = [(round(cl_x(y) + dx, 4), y) for y, dx in ((-0.100, 0.008), (-0.122, 0.008), (-0.143, 0.008), (-0.164, 0.007), (-0.152, -0.004))]
    for k, (sx_, sy_) in enumerate(stones):
        f.s("pebbles", ell(sx_, sy_, 0.0068, 0.0056, 15 * k), "fiveStones")
    pieces.append(dict(id="brook", kind="water", region="water", mapping="none", geom=brook, heightMax=0.004, group="brook",
                       note="water film over the printed brook; the ground has a HOLE here (ground.mask 255) so the real paper "
                            "(the child's colour) shows through, as §11.9; outside the scanned art rectangle"))
    pieces.append(dict(id="fiveStones", kind="stones", region="pebbles", mapping="constant",
                       geom=unary_union([ell(x, y, 0.0068, 0.0056) for x, y in stones]), heightMax=0.008, group="brook",
                       stonesSheet=[[x, y] for x, y in stones],
                       note="five smooth stones (1 Sam 17:40) in the water by the right bank; constant UV = desert.stoneUV"))
    return f, pieces


def stage_band(sheetx):
    """Flat stage: every acting position and walk path, buffered by the actor's footprint. Sheet coords (ys = -z)."""
    tl = json.load(open(TIMELINE))
    R = {"david": 0.075, "goliath": 0.170}
    pos = {"david": (sheetx["david"], 0.0), "goliath": (sheetx["goliath"], 0.0)}
    geoms = [Point(pos[c][0], -pos[c][1]).buffer(R[c]) for c in pos]
    pts = []
    for a in sorted(tl["acting"], key=lambda a: a["t"]):
        if "to" in a:
            c = a["who"]; x0, z0 = pos[c]; x1, z1 = a["to"]
            geoms.append(LineString([(x0, -z0), (x1, -z1)]).buffer(R[c]))
            pos[c] = (x1, z1); pts.append((a["t"], c, x1, z1))
    return unary_union(geoms), pts


def footprint(pc):
    """3D ground footprint of a raised piece, in sheet coords (x, ys = -z)."""
    if pc.get("mapping") != "front": return pc["geom"]
    x0, _, x1, _ = pc["sil3d"].bounds
    d = pc["depth"]
    if pc["kind"] == "banner":
        bx = pc["banner"]["poleBase3D"][0]; return Point(bx, d["front"]).buffer(0.006)
    return box(x0, d["front"], x1, d["back"])


def heightfield(pieces, X, Dd):
    """Page heightfield H[d, x] and owner index (-1 = flat ground) from the front pieces' 3D description.
    Front slope: smoothstep from the front foot to the crest; plateau; steep back slope (hidden from the viewer)."""
    import numpy as np
    H = np.zeros((len(Dd), len(X)), np.float32); OWN = np.full(H.shape, -1, np.int16)
    xx, dd = np.meshgrid(X, Dd)
    for k, pc in enumerate(pieces):
        if pc.get("mapping") != "front" or pc["kind"] == "banner": continue
        d = pc["depth"]
        if pc["kind"] == "tent":
            t = pc["tent"]; cx, w = t["centreX"], t["width"]
            a = np.clip(1 - np.abs(xx - cx) / (w / 2), 0, 1)
            inside = (np.abs(xx - cx) <= w / 2) & (dd >= d["front"]) & (dd <= d["back"])
            h = np.where(inside, t["baseY"] - t["skirt"] + t["skirt"] + t["height"] * a, 0)
        else:
            topx = np.interp(xx, pc["top"][0], pc["top"][1], left=0, right=0)
            if pc["kind"] == "rock":
                e = np.minimum(dd - d["front"], d["back"] - dd)
                prof = np.clip(e / 0.012, 0, 1) ** 0.5
            else:
                t1 = np.clip((dd - d["front"]) / max(1e-6, d["crestFrom"] - d["front"]), 0, 1)
                rise = t1 * t1 * (3 - 2 * t1)
                t2 = np.clip((dd - d["crestTo"]) / max(1e-6, d["back"] - d["crestTo"]), 0, 1)
                fall = 1 - t2 * t2
                prof = np.where(dd < d["crestFrom"], rise, np.where(dd > d["crestTo"], fall, 1.0))
                prof = np.where((dd < d["front"]) | (dd > d["back"]), 0, prof)
            h = topx * prof
        m = h > H + 1e-6
        H = np.where(m, h, H); OWN = np.where(m, k, OWN)
    return H, OWN


# ---------------------------------------------------------------------------------------------- checks
def visible_pieces(f):
    res = []; n = len(f.shapes)
    for i, (region, g, tag) in enumerate(f.shapes):
        above = unary_union([h for _, h, _ in f.shapes[i + 1:]]) if i + 1 < n else None
        v = g.difference(above) if above is not None and not above.is_empty else g
        for p in polys(v):
            if p.area > 1e-9: res.append((region, tag, p))
    return res


def inscribed_d(p):
    c = polylabel(p, tolerance=0.0002)
    return 2 * p.exterior.distance(c) if p.contains(c) else 0.0


def check(name, fig, report):
    pieces = visible_pieces(fig)
    small = []
    for region, tag, p in pieces:
        if p.buffer(-LINE_OUTER / 2).is_empty: continue      # buried under the outline ink: not a colourable cell
        d = inscribed_d(p)
        if d < REGION_MIN_D: small.append((round(d * PX, 1), region, tag, round(p.area * PX * PX)))
    small.sort()
    slivers = [s for s in small if s[0] < SLIVER_D * PX]
    tiny = [s for s in small if s[0] >= SLIVER_D * PX]
    cutting = 0                                  # a decorative line cuts a region only if BOTH ends touch its edge
    for l, w, parent in fig.decor:
        if parent is None: continue
        ends = [parent.exterior.distance(Point(pt)) < 0.004 for pt in (l.coords[0], l.coords[-1])]
        if all(ends): cutting += 1
    report[name] = {"pieces": len(pieces), "slivers(<6px)": slivers, "small(6-12px)": tiny, "decorCuttingRegion": cutting}
    return slivers, cutting


# ---------------------------------------------------------------------------------------------- bones
def bones_for(P, arms, fists, extra, head_depth):
    b = {}
    def put(n, h, t, parent, z0=0.0, z1=0.0):
        b[n] = {"head": [round(h[0], 4), round(h[1], 4), round(z0, 4)], "tail": [round(t[0], 4), round(t[1], 4), round(z1, 4)], "parent": parent}
    hipY = P["hip"][1]; headH = P["skullTop"] - P["chin"]
    put("root", (0, 0), (0, P["height"] * 0.1), None)
    put("hips", (0, hipY), (0, P["waistY"]), "root")
    put("spine", (0, P["waistY"]), (0, P["chestY"]), "hips")
    put("chest", (0, P["chestY"]), (0, P["neckBase"]), "spine")
    hb = P["chin"] + headH * 0.25
    put("neck", (0, P["neckBase"]), (0, hb), "chest")
    put("head", (0, hb), (0, P["skullTop"]), "neck")
    put("jaw", (0, P["earY"][0] - headH * 0.02), (0, P["chin"] + headH * 0.03), "head", -head_depth * 0.05, head_depth * 0.40)
    for sd, suf in ((1, "L"), (-1, "R")):
        S, E, W, H, d = arms[sd]
        hl = P["hand"]
        put("shoulder" + suf, (sd * P["shoulder"][0] * 0.22, P["neckBase"] - headH * 0.05), S, "chest")
        put("upperArm" + suf, S, E, "shoulder" + suf)
        put("forearm" + suf, E, W, "upperArm" + suf)
        K = along(W, d, hl * 0.45)
        put("hand" + suf, W, K, "forearm" + suf)
        thumb0 = along(W, d, hl * 0.12)
        if fists.get(sd):                       # curled at rest: fingers wrap the grip, tips point back (-Z) under it
            put("fingers" + suf, K, along(K, d, hl * 0.22), "hand" + suf, 0.0, -hl * 0.06)
            put("fingerTips" + suf, along(K, d, hl * 0.22), along(K, d, hl * 0.18), "fingers" + suf, -hl * 0.06, -hl * 0.22)
            put("thumb" + suf, thumb0, along(K, d, hl * 0.10), "hand" + suf, hl * 0.12, hl * 0.18)
        else:                                   # open, fingers together and straight
            put("fingers" + suf, K, along(K, d, hl * 0.30), "hand" + suf)
            put("fingerTips" + suf, along(K, d, hl * 0.30), along(K, d, hl * 0.55), "fingers" + suf)
            put("thumb" + suf, thumb0, along(W, d, hl * 0.55), "hand" + suf, hl * 0.12, hl * 0.30)
        x = sd * P["hip"][0]; kx, ky = sd * P["knee"][0], P["knee"][1]; axx, ay = sd * P["ankle"][0], P["ankle"][1]
        put("thigh" + suf, (x, hipY), (kx, ky), "hips")
        put("shin" + suf, (kx, ky), (axx, ay), "thigh" + suf)
        put("foot" + suf, (axx, ay), (axx, ay * 0.25), "shin" + suf, 0.0, P["footLen"] * 0.62)
        put("toe" + suf, (axx, ay * 0.25), (axx, ay * 0.2), "foot" + suf, P["footLen"] * 0.62, P["footLen"] * 0.92)
    for n, (h, t, parent, z0, z1) in extra.items():
        put(n, h, t, parent, z0, z1)
    return b


def sheet_bones(bones, sx, sy=SHEET_Y):
    return {n: dict(v, head=[round(v["head"][0] + sx, 4), round(v["head"][1] + sy, 4)] + v["head"][2:],
                    tail=[round(v["tail"][0] + sx, 4), round(v["tail"][1] + sy, 4)] + v["tail"][2:]) for n, v in bones.items()}


def bbox(g):
    x0, y0, x1, y1 = g.bounds
    return [round(x0, 4), round(y0, 4), round(x1, 4), round(y1, 4)]


def to_page_rect(b):
    x0, y0, x1, y1 = b
    X0 = ART[0] + (x0 + 0.5) * PX; X1 = ART[0] + (x1 + 0.5) * PX
    Y0 = ART_BOTTOM_PX - y1 * PX; Y1 = ART_BOTTOM_PX - y0 * PX
    return [round(X0), round(Y0), round(X1 - X0), round(Y1 - Y0)]


def ring(p, nd=4, tol=0.0008):
    return [[round(x, nd), round(y, nd)] for x, y in p.simplify(tol).exterior.coords]


def coords(g, nd=4):
    """largest polygon only (kept for single-part geometry)"""
    return ring(max(polys(g), key=lambda q: q.area), nd)


def coords_all(g, nd=4, tol=0.0008):
    """EVERY polygon of g, largest first (QA T12: the stage band has two parts)"""
    return [ring(p, nd, tol) for p in sorted(polys(g), key=lambda q: -q.area)]


# ---------------------------------------------------------------------------------------------- sheet / lineup / palette
SHEET_T = mapper(ART[0] + 0.5 * PX, ART_BOTTOM_PX, PX)


def sheet_header(design, W, Hh):
    body = []
    for cx, cy in MARKERS:
        body.append(f'<rect x="{cx - MARKER_SIZE / 2}" y="{cy - MARKER_SIZE / 2}" width="{MARKER_SIZE}" height="{MARKER_SIZE}" fill="#000"/>')
    t = design["sheet"]["title"]; n = len(t["hanzi"]); bx, gp = t["box"], t["gap"]
    x0 = (W - (n * bx + (n - 1) * gp)) / 2; top = t["cy"] - bx / 2
    for i, (ch, py) in enumerate(zip(t["hanzi"], t["pinyin"].split())):
        x = x0 + i * (bx + gp)
        body.append(f'<rect x="{x}" y="{top}" width="{bx}" height="{bx}" fill="none" stroke="#CD3C3C" stroke-width="3"/>')
        body.append(f'<line x1="{x}" y1="{top + bx / 2}" x2="{x + bx}" y2="{top + bx / 2}" stroke="#CD3C3C" stroke-width="1" stroke-dasharray="6 6"/>')
        body.append(f'<line x1="{x + bx / 2}" y1="{top}" x2="{x + bx / 2}" y2="{top + bx}" stroke="#CD3C3C" stroke-width="1" stroke-dasharray="6 6"/>')
        body.append(text(x + bx / 2, top + bx * 0.80, ch, int(bx * 0.78), cls="kai", fill="#1E1E1E"))
        body.append(text(x + bx / 2, top - 9, py, 20, cls="kai", fill="#464646"))
    ey = top + bx + 36
    body.append(text(W / 2, ey, t["english"], 32, weight="bold"))
    body.append(text(W / 2, ey + 30, t["label"], 18, fill="#787878"))
    f1, f2 = design["sheet"]["footer"]["lines"]; fx, fy, fw, fh = design["sheet"]["footer"]["rect"]
    body.append(text(fx + fw / 2, fy + 48, f1, 24, fill="#787878"))
    body.append(text(fx + fw / 2, fy + 83, f2, 20, fill="#9A9A9A"))
    return body


def render_sheet(davS, golS, desert, design, name, colours, annotate=False, stage=None, pieces=None, acting=None):
    W, Hh = PAGE
    body = sheet_header(design, W, Hh)
    pal = lambda c: PALETTE[c] if colours else None
    body.append(fig_svg(desert, SHEET_T, PX, pal("desert")))
    body.append(fig_svg(davS, SHEET_T, PX, pal("david")))
    body.append(fig_svg(golS, SHEET_T, PX, pal("goliath")))
    if annotate:
        A = "#1F8FD6"; Rr = "#E8553D"; Gg = "#3FB36B"
        body.append(f'<rect x="{ART[0]}" y="{ART[1]}" width="{ART[2]}" height="{ART[3]}" fill="none" stroke="{A}" stroke-width="3" stroke-dasharray="14 8"/>')
        body.append(text(ART[0] + 8, ART[1] + 24, f"art rect {list(ART)} = scanned texture · 1.0 × {ART_H:.3f}", 19, "start", fill=A))
        body.append(f'<path d="{path_d(stage, SHEET_T)}" fill="{Rr}" fill-opacity="0.13" stroke="{Rr}" stroke-width="2" stroke-dasharray="8 5"/>')
        body.append(text(ART[0] + 560, ART_BOTTOM_PX + 120, "FLAT STAGE (nothing above 0.010)", 18, fill=Rr, weight="bold"))
        for t, c, x, z in acting:
            X, Y = SHEET_T(x, -z)
            body.append(f'<circle cx="{X:.1f}" cy="{Y:.1f}" r="6" fill="{Rr}"/>')
            body.append(text(X + 8, Y - 6, f"{t:g}s", 14, "start", fill=Rr))
        Pu = "#7A5BC7"
        for pc in pieces:                       # 3D ground footprints of the raised pieces (dashed)
            if pc.get("mapping") == "front" and pc["kind"] not in ("tent", "banner") and pc["group"] != "pano":
                body.append(f'<path d="{path_d(footprint(pc), SHEET_T)}" fill="none" stroke="{Pu}" stroke-width="1.6" stroke-dasharray="4 4"/>')
        body.append(f'<path d="{path_d(box(-0.59, PANO_DEPTH["front"], 0.59, PANO_DEPTH["back"]), SHEET_T)}" fill="{Pu}" fill-opacity="0.06" '
                    f'stroke="{Pu}" stroke-width="1.6" stroke-dasharray="4 4"/>')
        X_, Y_ = SHEET_T(0.33, 1.45)
        body.append(text(X_, Y_, "3D footprint of the far panorama (z -0.98..-1.475)", 14, fill=Pu))
        pb = box(-0.236, 1.0, 0.236, ART_H - 0.02)
        body.append(f'<path d="{path_d(pb, SHEET_T)}" fill="none" stroke="{Gg}" stroke-width="2"/>')
        body.append(text(ART[0] + 500, ART[1] - 6, "far panorama drawing (FRONT, scale 2.5, sheetY 1.000) - stands 3D at z -0.98...-1.475", 15, fill=Gg))
        for pc in pieces:
            if pc["kind"] in ("tent", "banner") or pc["id"] in ("hillIsrael", "hillPhil", "duneFar"): continue
            b = pc["geom"].bounds; X, Y = SHEET_T((b[0] + b[2]) / 2, b[1])
            if pc["group"] == "brook": X, Y = SHEET_T(b[2] + 0.075, (b[1] + b[3]) / 2 - (0.03 if pc["kind"] == "stones" else -0.05))
            lab = f'{pc["id"]} h{pc["heightMax"]:.2f}' + (f' z{-pc["depth"]["front"]:+.2f}..{-pc["depth"]["back"]:+.2f}' if pc.get("mapping") == "front" else "")
            body.append(f'<text x="{X:.1f}" y="{Y + 16:.1f}" font-size="13" text-anchor="middle" fill="#0B5A8C" font-weight="bold" '
                        f'stroke="#FFFFFF" stroke-width="4" paint-order="stroke">{escape(lab)}</text>')
        for pid, (lx, ly) in (("hillIsrael", (-0.14, 1.205)), ("hillPhil", (0.14, 1.205))):
            pc = [q for q in pieces if q["id"] == pid][0]
            X, Y = SHEET_T(lx, ly)
            body.append(f'<text x="{X:.1f}" y="{Y:.1f}" font-size="13" text-anchor="middle" fill="#0B5A8C" font-weight="bold" '
                        f'stroke="#FFFFFF" stroke-width="4" paint-order="stroke">{pid} h{pc["heightMax"]:.2f} (3D)</text>')
        for nm, r in design["sheet"]["figureRectsPx"].items():
            body.append(f'<rect x="{r[0]}" y="{r[1]}" width="{r[2]}" height="{r[3]}" fill="none" stroke="{Gg}" stroke-width="2"/>')
            body.append(text(r[0] + r[2] / 2, r[1] - 8, f"{nm} drawing (UV0 front projection)", 16, fill=Gg))
        bx = design["desert"]["brookStripPx"]
        body.append(f'<rect x="{bx[0]}" y="{bx[1]}" width="{bx[2]}" height="{bx[3]}" fill="none" stroke="#7A5BC7" stroke-width="2" stroke-dasharray="5 4"/>')
        body.append(text(bx[0] + bx[2] + 6, bx[1] + 28, "brook strip (outside the scan)", 14, "start", fill="#7A5BC7"))
        for z, lab in ((-1.0, "z = −1.0"), (-0.35, "z = −0.35")):
            Y = ART_BOTTOM_PX - (-z) * PX
            body.append(f'<line x1="{ART[0] - 30}" y1="{Y}" x2="{ART[0]}" y2="{Y}" stroke="{A}" stroke-width="2"/>')
            body.append(text(ART[0] - 34, Y + 5, lab, 14, "end", fill=A))
        for nm, sx in (("david", D["sheetX"]), ("goliath", G["sheetX"])):
            X = ART[0] + (sx + 0.5) * PX
            body.append(text(X, ART_BOTTOM_PX + 22, f"x={sx:+.3f}", 16, fill=A))
    write_svg_png(name, W, Hh, "\n".join(body), bg="#FFFFFF")


def render_chars_only(davS, golS):
    W, Hh = PAGE
    body = [fig_svg(davS, SHEET_T, PX, PALETTE["david"]), fig_svg(golS, SHEET_T, PX, PALETTE["goliath"])]
    return write_svg_png("_chars-only", W, Hh, "\n".join(body), transparent=True)


def render_lineup(davS, golS):
    s = 820; W = 1040; Hh = 900; base = 830; ox = W / 2 - 0.06 * s
    T = mapper(ox, base, s)
    body = [text(40, 48, "比例 Scale — 大卫 0.30（5.5 头身）· 歌利亚 0.80（7.4 头身）· 约 2.7 倍", 24, "start", weight="bold")]
    for f, c in ((davS, "david"), (golS, "goliath")):
        body.append(fig_svg(f.translate(0, -SHEET_Y), T, s, PALETTE[c], shade=0.004 if c == "david" else 0.006, lw=0.9))
    body.append(f'<line x1="20" y1="{base}" x2="{W - 20}" y2="{base}" stroke="#6B5B4A" stroke-width="3"/>')
    for hgt, lab in ((0.30, "0.30"), (0.80, "0.80")):
        y = base - hgt * s
        body.append(f'<line x1="40" y1="{y}" x2="{W - 40}" y2="{y}" stroke="#E8553D" stroke-width="2" stroke-dasharray="10 8"/>')
        body.append(text(W - 44, y - 8, lab, 22, "end", fill="#E8553D"))
    for P, sx in ((D, D["sheetX"]), (G, G["sheetX"])):
        hu = P["skullTop"] - P["chin"]; X = ox + (sx + (0.14 if P is D else 0.40)) * s
        for i in range(int(P["skullTop"] / hu) + 1):
            y = base - i * hu * s
            body.append(f'<line x1="{X - 8}" y1="{y:.1f}" x2="{X + 8}" y2="{y:.1f}" stroke="#1F8FD6" stroke-width="2"/>')
        body.append(f'<line x1="{X}" y1="{base}" x2="{X}" y2="{base - P["skullTop"] * s:.1f}" stroke="#1F8FD6" stroke-width="2"/>')
    write_svg_png("lineup-scale", W, Hh, "\n".join(body))


def render_palette():
    rows = [(c, r, v) for c in PALETTE for r, v in PALETTE[c].items()]
    W = 1640; rowh = 50; per = (len(rows) + 2) // 3; Hh = 110 + rowh * per
    body = [text(40, 56, "示范调色板 Demo palette — 每个区域一种蜡笔色（都通过 App 的去线规则）", 28, "start", weight="bold")]
    who = {"david": "大卫", "goliath": "歌利亚", "desert": "沙漠"}
    for i, (c, r, (hx, zh, en)) in enumerate(rows):
        col, rr = i // per, i % per
        x = 40 + col * 540; y = 86 + rr * rowh
        body.append(f'<rect x="{x}" y="{y}" width="74" height="38" rx="8" fill="{hx}" stroke="{INK}" stroke-width="3"/>')
        body.append(text(x + 88, y + 26, f"{who[c]} · {zh} {en}  {hx}", 18, "start"))
    write_svg_png("palette", W, Hh, "\n".join(body))


# ---------------------------------------------------------------------------------------------- ground + AR mock (§12)
GROUND = {"sand": "#E3C38C", "rippleWavelength": 0.020, "rippleWarpAmp": 0.45, "rippleWarpPeriod": 0.23,
          "rippleNoiseAmp": 0.25, "noisePeriod": 0.12, "rippleContrast": 0.04, "patchPeriod": 0.30, "patchContrast": 0.05,
          "paperLo": 0.60, "paperHi": 0.86, "maskDilate": 0.008}
WORK = os.environ.get("DG_WORK", "/tmp/dg_work")


def page_xd(Wp, Hp):
    import numpy as np
    jj, ii = np.meshgrid(np.arange(Wp) + 0.5, np.arange(Hp) + 0.5)
    return (jj - (ART[0] + 0.5 * PX)) / PX, (ART_BOTTOM_PX - ii) / PX          # x, d (= ys = -z)


def value_noise(x, y, seed):
    """smooth value noise in [-1, 1] (period 1 lattice), the same idea the shader may take from a noise texture"""
    import numpy as np
    rng = np.random.default_rng(seed); lat = rng.uniform(-1, 1, (64, 64)).astype(np.float32)
    xi = np.floor(x).astype(int); yi = np.floor(y).astype(int); fx = x - xi; fy = y - yi
    fx = fx * fx * (3 - 2 * fx); fy = fy * fy * (3 - 2 * fy)
    g = lambda a, b: lat[(b) % 64, (a) % 64]
    return (g(xi, yi) * (1 - fx) * (1 - fy) + g(xi + 1, yi) * fx * (1 - fy) + g(xi, yi + 1) * (1 - fx) * fy + g(xi + 1, yi + 1) * fx * fy)


def sand_rgb(x, d):
    """The ground sand of §12.4 (page units): ripples across the valley + low-frequency patches."""
    import numpy as np
    G = GROUND
    base = np.array([int(G["sand"][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
    n1 = value_noise(x / G["noisePeriod"], d / G["noisePeriod"], 11)
    n2 = value_noise(x / G["patchPeriod"] + 7.3, d / G["patchPeriod"], 12)
    ph = 2 * math.pi * (d / G["rippleWavelength"] + G["rippleWarpAmp"] * np.sin(2 * math.pi * x / G["rippleWarpPeriod"])
                        + G["rippleNoiseAmp"] * n1)
    k = 1 + G["rippleContrast"] * np.sin(ph) + G["patchContrast"] * n2
    return np.clip(base[None, None, :] * k[..., None], 0, 255)


def erase_lines(rgb, markers=True):
    """the app's line-erase, roughly (fills ink from its non-ink neighbours) at page resolution"""
    import numpy as np
    a = rgb.astype(np.float32); h, w, _ = a.shape
    mx_, mn = a.max(2), a.min(2); ink = (mx_ < 175) & (mx_ - mn < 45)
    ink = ink | np.roll(ink, 1, 0) | np.roll(ink, -1, 0) | np.roll(ink, 1, 1) | np.roll(ink, -1, 1)
    known = ~ink; out = a.copy()
    for _ in range(8):
        acc = np.zeros_like(out); cnt = np.zeros((h, w, 1), np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            acc += np.roll(np.roll(out * known[..., None], dy, 0), dx, 1); cnt += np.roll(np.roll(known, dy, 0), dx, 1)[..., None]
        fill = (~known) & (cnt[..., 0] > 0)
        out[fill] = acc[fill] / cnt[fill]; known = known | fill
    return out


def ground_mask(chars, pieces):
    """page-size L image: 0 = sand (procedural), 128 = scan colour where painted else sand, 255 = hole (real paper shows)."""
    from PIL import Image, ImageDraw
    W, Hh = PAGE
    m = Image.new("L", (W, Hh), 0); dr = ImageDraw.Draw(m)
    dr.rectangle([ART[0], ART[1], ART[0] + ART[2] - 1, ART[1] + ART[3] - 1], fill=128)
    sand = [chars.buffer(GROUND["maskDilate"])]
    for pc in pieces:
        if pc.get("mapping") == "front":
            sand.append(pc["geom"].buffer(GROUND["maskDilate"]))
    sand = unary_union(sand).intersection(box(-0.5, 0, 0.5, ART_H))
    for p in polys(sand):
        dr.polygon([SHEET_T(x, y) for x, y in p.exterior.coords], fill=0)
        for r in p.interiors: dr.polygon([SHEET_T(x, y) for x, y in r.coords], fill=128)
    hole = [pc for pc in pieces if pc["id"] == "brook"][0]["geom"].buffer(-0.002)
    for p in polys(hole):
        dr.polygon([SHEET_T(x, y) for x, y in p.exterior.coords], fill=255)
    m.save(os.path.join(HERE, "ground-mask.png"))
    return m, sand, hole


def render_ar_mock(pieces, mask, stage_pos, shots):
    """Bakes the ground + scanned-page images, writes the page heightfield, and has Blender render real 3D views
    (the character GLBs in rest pose on their marks, the desert volumes from design.json, front / top-down UV rules)."""
    import numpy as np
    from PIL import Image
    os.makedirs(WORK, exist_ok=True)
    demo = np.asarray(Image.open(os.path.join(HERE, "sheet-mock-demo-colour.png")).convert("RGB")).astype(np.float32)
    Hp, Wp, _ = demo.shape
    er = erase_lines(demo)
    x, d = page_xd(Wp, Hp)
    sand = sand_rgb(x, d)
    M = np.asarray(mask)
    lo, hi = GROUND["paperLo"], GROUND["paperHi"]
    t = np.clip((er.min(2) / 255 - lo) / (hi - lo), 0, 1); paper = (t * t * (3 - 2 * t))[..., None]
    ground = np.where((M == 128)[..., None], er * (1 - paper) + sand * paper, sand)
    ground = np.where((M == 255)[..., None], demo, ground)
    for (sx_, sy_) in [pc for pc in pieces if pc["id"] == "fiveStones"][0]["stonesSheet"]:   # the 3D stones (constant UV)
        X, Y = SHEET_T(sx_, sy_); r = 0.0068 * PX
        yy, xx = np.ogrid[:Hp, :Wp]; st = ((xx - X) / r) ** 2 + ((yy - Y) / (0.8 * r)) ** 2 < 1
        ground[st] = (201, 195, 182)
    Image.fromarray(ground.astype(np.uint8)).save(os.path.join(WORK, "ar_ground.png"))
    Image.fromarray(ground.astype(np.uint8)).resize((Wp // 2, Hp // 2), Image.LANCZOS).save(os.path.join(HERE, "ground-sand-demo.png"))
    sandF = np.array([int(PALETTE["desert"]["sand"][0][i:i + 2], 16) for i in (1, 3, 5)], np.float32)
    Image.fromarray((er * (1 - paper) + sandF * paper).astype(np.uint8)).save(os.path.join(WORK, "ar_front.png"))
    Image.fromarray(er.astype(np.uint8)).save(os.path.join(WORK, "ar_chars.png"))
    STEP = 0.0025
    X = np.arange(-0.62, 0.62 + 1e-9, STEP).astype(np.float32); Dd = np.arange(-0.244, 1.510 + 1e-9, STEP).astype(np.float32)
    H, OWN = heightfield(pieces, X, Dd)
    for (sx_, sy_) in [pc for pc in pieces if pc["id"] == "fiveStones"][0]["stonesSheet"]:
        xx, dd = np.meshgrid(X, Dd); r2 = ((xx - sx_) / 0.0068) ** 2 + ((dd - sy_) / 0.0056) ** 2
        H = np.maximum(H, np.where(r2 < 1, 0.008 * np.sqrt(np.clip(1 - r2, 0, 1)), 0)).astype(np.float32)
    maps = np.array([[pc["frontUV"]["scale"], pc["frontUV"]["sheetX"], pc["frontUV"]["sheetY"]] if pc.get("mapping") == "front"
                     else [1, 0, 0] for pc in pieces], np.float32)
    np.savez_compressed(os.path.join(WORK, "ar_mock_grid.npz"), X=X, D=Dd, H=H, OWN=OWN, MAPS=maps)
    banners = []
    for pc in pieces:
        if pc["kind"] == "banner":
            b = pc["banner"]
            banners.append({"cloth": [list(p) for p in pc["sil3d"].exterior.coords], "pole": b["poleBase3D"] + [b["poleHeight"]],
                            "map": pc["frontUV"]})
    scene = {"page": [Wp, Hp], "art": list(ART), "px": PX, "artBottomPx": ART_BOTTOM_PX, "banners": banners,
             "models": {c: os.path.join(ROOT, "assets", "david-goliath", "model", f"{c}.glb") for c in ("david", "goliath")},
             "stage": stage_pos, "shots": shots, "work": WORK, "out": HERE}
    json.dump(scene, open(os.path.join(WORK, "ar_mock_scene.json"), "w"))
    exe = os.environ.get("BLENDER", "blender")
    log = os.path.join(WORK, "ar_mock_blender.log")
    try:
        with open(log, "w") as lf:
            r = subprocess.run([exe, "-b", "--factory-startup", "--python", os.path.join(HERE, "ar_mock_blender.py"), "--",
                                os.path.join(WORK, "ar_mock_scene.json")], stdout=lf, stderr=subprocess.STDOUT, timeout=900)
        ok = r.returncode == 0 and "AR_MOCK_OK" in open(log).read()
    except (OSError, subprocess.TimeoutExpired) as e:
        ok = False; print("AR mock: Blender not run:", e)
    if not ok: print(f"WARN: AR mock render failed, see {log}")
    return ok


# ---------------------------------------------------------------------------------------------- scan simulation
def scan_sim():
    """Port of web/vision.js eraseLines(radius 4) on the demo sheet's art rect at 1024^2: what the models wear."""
    import numpy as np
    from PIL import Image
    sheet = Image.open(os.path.join(HERE, "sheet-mock-demo-colour.png")).convert("RGB")
    art = sheet.crop((ART[0], ART[1], ART[0] + ART[2], ART[1] + ART[3])).resize((1024, 1024), Image.LANCZOS)
    a = np.asarray(art).astype(np.int32); Hh, W, _ = a.shape
    mx_, mn = a.max(2), a.min(2); ink = (mx_ < 175) & (mx_ - mn < 45)
    best = np.full((Hh, W), -1); out = a.copy()
    pad = 4; ap = np.pad(a, ((pad, pad), (pad, pad), (0, 0)), constant_values=0)
    ip = np.pad(ink, pad, constant_values=True); sp = ap.sum(2)
    for r in range(1, 5):
        for dx, dy in ((r, 0), (-r, 0), (0, r), (0, -r), (r, r), (-r, -r), (r, -r), (-r, r)):
            sl = (slice(pad + dy, pad + dy + Hh), slice(pad + dx, pad + dx + W))
            cand = (~ip[sl]) & (sp[sl] > best) & ink
            best = np.where(cand, sp[sl], best)
            out[cand] = ap[sl][cand]
    left = ink & (best < 0)
    clean = Image.fromarray(out.astype(np.uint8))
    both = Image.new("RGB", (2048 + 30, 1024), "#FBF5E6"); both.paste(art, (0, 0)); both.paste(clean, (1054, 0))
    both.save(os.path.join(HERE, "scan-sim-texture.png"))
    return {"inkPixelsBefore": int(ink.sum()), "inkPixelsKept": int(left.sum()),
            "keptFraction": round(float(left.sum()) / max(1, int(ink.sum())), 3)}


# ---------------------------------------------------------------------------------------------- main
HEIGHT_CAP = {"hill": 0.40, "tent": 0.50, "banner": 0.53, "dune": 0.30, "duneFar": 0.20, "rock": 0.10, "shrub": 0.06,
              "rockFR1": 0.06, "rockFR2": 0.06, "water": 0.004, "stones": 0.008}
FRONT_ZONE_D = 0.30          # 3D footprints reaching closer than z = -0.30 stand beside / in front of the actors ...
FRONT_ZONE_CAP = 0.06        # ... and stay this low
GROUP_GAP = 0.012            # printed drawings with different UV mappings never share a texel
PLACE_MARGIN = 0.0305


def main():
    report = {}; fails = []
    dav, darms, dfist = build_david(); davB, _, _ = build_david(back=True)
    gol, garms, ggrip, glgrip = build_goliath(); golB, *_ = build_goliath(back=True)
    # sheet placement: David at the left margin, Goliath at the right margin
    dx0, _, dx1, _ = dav.silhouette().bounds; gx0, _, gx1, _ = gol.silhouette().bounds
    D["sheetX"] = round(-0.5 + PLACE_MARGIN - dx0, 3); G["sheetX"] = round(0.5 - PLACE_MARGIN - gx1, 3)
    davS = dav.translate(D["sheetX"], SHEET_Y); golS = gol.translate(G["sheetX"], SHEET_Y)
    D["bboxSheet"] = bbox(davS.silhouette()); G["bboxSheet"] = bbox(golS.silhouette())

    # ---- character checks
    for nm, f in (("david", davS), ("goliath", golS)):
        x0, y0, x1, y1 = f.silhouette().bounds
        m = min(x0 + 0.5, 0.5 - x1, ART_H - y1)
        report[nm + ".bounds"] = bbox(f.silhouette()); report[nm + ".marginToArtEdge"] = round(m, 4)
        if m < MARGIN_MIN - 1e-4: fails.append(f"{nm}: margin {m:.4f} < {MARGIN_MIN}")
        if y0 < BOTTOM_MIN: fails.append(f"{nm}: bottom margin {y0:.4f} < {BOTTOM_MIN}")
    gap = davS.silhouette().distance(golS.silhouette()); report["gapDavidGoliath"] = round(gap, 4)
    if gap < GAP_MIN: fails.append(f"gap {gap:.3f} < {GAP_MIN}")
    for nm, f in (("david", davS), ("goliath", golS)):
        sl, cut = check(nm, f, report)
        if sl: fails.append(f"{nm}: {len(sl)} sliver(s): {sl[:4]}")
        if cut: fails.append(f"{nm}: {cut} decorative line(s) cut a region")
    pal_bad = [(c, r, v[0]) for c in PALETTE for r, v in PALETTE[c].items() if not ink_safe(v[0])]
    if pal_bad: fails.append(f"palette colours read as ink by the app: {pal_bad}")
    report["paletteInkSafe"] = not pal_bad

    # ---- desert checks
    desert, pieces = build_desert()
    stage, acting = stage_band({"david": D["sheetX"], "goliath": G["sheetX"]})
    chars = unary_union([davS.silhouette(), golS.silhouette()])
    art = box(-0.5, 0.0, 0.5, ART_H)
    mk = unary_union([box((cx - 620) / PX - 0.032 - 0.02, (ART_BOTTOM_PX - cy) / PX - 0.032 - 0.02,
                          (cx - 620) / PX + 0.032 + 0.02, (ART_BOTTOM_PX - cy) / PX + 0.032 + 0.02) for cx, cy in MARKERS])
    dchk = {}
    inner = art.buffer(-0.020)
    paper3d = box(-0.596, -0.220, 0.596, 1.486)
    for pc in pieces:
        g = pc["geom"]; r = {}
        r["clearToCharacters"] = round(g.distance(chars), 4)
        if r["clearToCharacters"] < DESERT_CLEAR: fails.append(f"desert {pc['id']}: {r['clearToCharacters']:.3f} from a character drawing")
        if pc["group"] != "brook" and not inner.contains(g): fails.append(f"desert {pc['id']}: drawing not inside the art rect (inset 0.020)")
        if g.intersects(mk): fails.append(f"desert {pc['id']}: too close to a marker")
        fp = footprint(pc); r["footprintSheet"] = bbox(fp)
        if pc["heightMax"] > HEIGHT_CAP["water"] + 1e-9 and pc["group"] != "brook" and fp.intersects(stage):
            fails.append(f"desert {pc['id']}: raised 3D footprint on the flat stage")
        if not paper3d.contains(fp): fails.append(f"desert {pc['id']}: 3D footprint off the paper")
        cap = HEIGHT_CAP[pc["id"]] if pc["id"] in HEIGHT_CAP else HEIGHT_CAP[pc["kind"]]
        if pc["heightMax"] > cap + 1e-9: fails.append(f"desert {pc['id']}: height {pc['heightMax']} > cap {cap}")
        if pc["group"] != "brook" and fp.bounds[1] < FRONT_ZONE_D and pc["heightMax"] > FRONT_ZONE_CAP + 1e-9:
            fails.append(f"desert {pc['id']}: {pc['heightMax']} tall in front of / beside the actors (cap {FRONT_ZONE_CAP})")
        dchk[pc["id"]] = r
    groups = {}
    for pc in pieces:
        groups.setdefault(pc["group"], []).append(pc["geom"])
    gk = sorted(groups); gg = {k: unary_union(v) for k, v in groups.items()}
    for i in range(len(gk)):
        for j in range(i + 1, len(gk)):
            dd_ = gg[gk[i]].distance(gg[gk[j]])
            if dd_ < GROUP_GAP: fails.append(f"desert drawings {gk[i]} / {gk[j]} only {dd_:.3f} apart (different UV mappings need {GROUP_GAP})")
    ink = unary_union([g for _, g, _ in desert.shapes]).buffer(LINE_OUTER / 2)
    x0, y0, x1, y1 = ink.bounds
    edge = {"leftPx": round(ART[0] + (x0 + 0.5) * PX, 1), "rightPx": round(PAGE[0] - (ART[0] + (x1 + 0.5) * PX), 1),
            "topPx": round(ART_BOTTOM_PX - y1 * PX, 1), "bottomPx": round(PAGE[1] - (ART_BOTTOM_PX - y0 * PX), 1)}
    report["desertInkToPageEdgePx"] = edge
    if min(edge.values()) < EDGE_MIN_PX: fails.append(f"desert ink closer than 6 mm ({EDGE_MIN_PX:.1f} px) to a page edge: {edge}")
    br = [pc for pc in pieces if pc["id"] == "brook"][0]["geom"]
    for k, (x_, y_) in enumerate([pc for pc in pieces if pc["id"] == "fiveStones"][0]["stonesSheet"]):
        if not br.buffer(-0.004).contains(Point(x_, y_)): fails.append(f"stone{k + 1} not inside the brook")
    report["desert"] = dchk
    sl, cut = check("desertPrint", desert, report)
    if sl: fails.append(f"desert print: {len(sl)} sliver(s): {sl[:4]}")
    if cut: fails.append(f"desert print: {cut} decorative line(s) cut a region")

    # ---- bones
    hd = {"david": 0.046, "goliath": 0.092}
    cx_, cy_ = dfist
    d_extra = {"slingCord1": ((cx_, cy_ - 0.008), (cx_, 0.110), "handR", 0, 0),
               "slingCord2": ((cx_, 0.110), (cx_, 0.0855), "slingCord1", 0, 0),
               "slingPouch": ((cx_, 0.0855), (cx_, 0.0685), "slingCord2", 0, 0),
               "stone": ((cx_, 0.0780), (cx_, 0.0980), "root", 0.004, 0.004)}
    sc = G["shieldCentre"]
    g_extra = {"spear": (ggrip, (ggrip[0], 0.955), "handR", 0, 0),
               "shield": (tuple(sc), tuple(sc), "handL", 0.010, 0.060),
               "helmet": ((0, 0.713), (0, 0.800), "head", 0, 0)}
    dB = bones_for(D, darms, {-1: True, 1: False}, d_extra, hd["david"])
    gB = bones_for(G, garms, {-1: True, 1: True}, g_extra, hd["goliath"])

    def region_info(fig, char):
        regs = {}
        for region, g, tag in fig.shapes:
            r = regs.setdefault(region, {"parts": [], "geoms": []})
            if tag and not tag.startswith("_") and tag not in r["parts"]: r["parts"].append(tag)
            r["geoms"].append(g)
        return {k: {"hex": PALETTE[char][k][0], "zh": PALETTE[char][k][1], "en": PALETTE[char][k][2], "parts": r["parts"],
                    "bboxSheet": bbox(unary_union(r["geoms"]))} for k, r in regs.items()}

    def flat_props(P, keys):
        out = {}
        for k in keys:
            v = P[k]; out[k] = list(v) if isinstance(v, tuple) else v
        out["shoulderX"], out["shoulderY"] = P["shoulder"]; out["hipX"], out["hipY"] = P["hip"]
        out["kneeY"] = P["knee"][1]; out["ankleY"] = P["ankle"][1]
        hh = P["skullTop"] - P["chin"]; out["headH"] = round(hh, 4)
        out["faceC"] = [0, round(P["chin"] + hh * 0.5, 4)]; out["faceR"] = [P["headHalfW"], round(hh * 0.5, 4)]
        out["headTop"] = P["height"]
        return out

    common = ("height", "skullTop", "chin", "headHalfW", "eyeY", "browY", "noseY", "mouthY", "earY", "neckBase", "shoulder",
              "upperArm", "forearm", "hand", "chestY", "waistY", "hip", "crotch", "knee", "ankle", "footLen")
    stone_sheet = [round(cx_ + D["sheetX"], 4), round(0.0780 + SHEET_Y, 4)]
    stone_uv = [round(stone_sheet[0] + 0.5, 4), round(stone_sheet[1] / ART_H, 4)]
    def piece_json(pc):
        out = {"id": pc["id"], "kind": pc["kind"], "region": pc["region"], "mapping": pc["mapping"], "group": pc["group"],
               "heightMax": pc["heightMax"], "bboxSheet": bbox(pc["geom"]), "footprintSheet": bbox(footprint(pc))}
        gp = polys(pc["geom"])
        out["geomSheet"] = coords_all(pc["geom"]) if len(gp) > 1 else [coords(pc["geom"])]
        if pc["mapping"] == "front":
            out["frontUV"] = pc["frontUV"]
            out["silhouette3D"] = ring(pc["sil3d"], 4, 0.0004)
            if pc.get("top"): out["topProfile3D"] = [[round(x, 4), round(y, 4)] for x, y in zip(*pc["top"])][::2] if len(pc["top"][0]) > 6 else [[round(x, 4), round(y, 4)] for x, y in zip(*pc["top"])]
            d = pc["depth"]
            out["depthZ"] = {"front": round(-d["front"], 4), "crestFrom": round(-d["crestFrom"], 4), "crestTo": round(-d["crestTo"], 4),
                             "back": round(-d["back"], 4)}
            out["parts3D"] = {k: ring(v, 4, 0.0004) for k, v in pc["parts"].items() if not v.is_empty}
        for k in ("tent", "banner", "onHill", "camp", "note", "stonesSheet"):
            if k in pc: out[k] = pc[k]
        return out

    desert_json = {
        "contract": "CONTRACT §12 (desert boost 2026-10-27); supersedes §11.9 where they differ",
        "uvRule": {"front": "u = x / scale + sheetX + 0.5, v = (y / scale + sheetY) / artHeightUnits, for a 3D vertex (x, y, z) "
                            "(x = page x, y = height); z is ignored. Characters are the case scale = 1 (character-local x).",
                   "pageTopDown": "u = x + 0.5, v = -z / artHeightUnits (ground pieces, §11.9)",
                   "constant": "one UV for the whole piece", "none": "no texture (water film)"},
        "layers": {"pano": "far panorama: duneFar, hillIsrael, hillPhil, tents, banners; one mapping scale 2.5, sheetX 0, sheetY 1.000; "
                           "drawn at sheet x -0.236..0.236, ys 1.000..1.207; stands at z -0.98..-1.475 across x -0.59..0.59",
                   "midground": "dune1 dune2 dune3 rockL1 rockL2 rockM1 rockM2 shrubL rockFR1 rockFR2; scale 1, sheetX 0, sheetY = "
                                "its front foot (-zFront): each stands on its own drawing",
                   "ground": "brook (hole in the ground, water film) and fiveStones (constant UV), top-down"},
        "depthProfile": "front pieces: h(x, z) = top(x) * p(z); p rises with smoothstep from depthZ.front to depthZ.crestFrom, "
                        "stays 1 to crestTo, then falls as 1 - t^2 to back (back slope steeper than 35 deg: hidden from the "
                        "viewer). rocks: p = sqrt(clamp(min(z - back, front - z) / 0.012, 0, 1)). tents: A-frame, ridge along z, "
                        "gable at depthZ.front faces +Z. The front orthographic silhouette of the 3D equals silhouette3D.",
        "heightCap": HEIGHT_CAP, "frontZone": {"zBeyond": -FRONT_ZONE_D, "cap": FRONT_ZONE_CAP,
                                               "rule": "a raised footprint reaching z > -0.30 stays <= 0.06 (actors stay visible)"},
        "stageBand": {"polygonsSheet": coords_all(stage, 3), "rule": "no desert geometry higher than 0.010 inside ANY part; every "
                      "acting.to position and walk path from timeline.json buffered by David 0.075 / Goliath 0.170",
                      "note": "all parts (QA T12): David's and Goliath's; polygonSheet (largest part only) is removed"},
        "clearanceToCharacters": DESERT_CLEAR, "groupGap": GROUP_GAP,
        "brookStripPx": to_page_rect(bbox([pc for pc in pieces if pc["id"] == "brook"][0]["geom"].buffer(0.004))),
        "stoneUV": stone_uv,
        "pieces": [piece_json(pc) for pc in pieces],
        "print": {"note": "what the Sheet role prints, in draw order (later covers earlier); sheet coords (x, ys); outline 4.5 px "
                          "around every shape, decor lines at their width",
                  "shapes": [{"region": r, "piece": t, "rings": coords_all(g, 4, 0.0005)} for r, g, t in desert.shapes],
                  "decor": [{"widthPx": round(w * PX, 1), "points": [[round(x, 4), round(y, 4)] for x, y in l.coords]} for l, w, _ in desert.decor]},
        "ground": {"rule": "§12.4", "maskPng": "docs/david-goliath/design/ground-mask.png", "maskValues": {"0": "sand", "128": "scan colour where painted, else sand", "255": "hole: render nothing (real paper shows: the brook)"},
                   "maskFrame": "page pixels 1240 x 1754 (= design.json sheet.page), whole sheet; outside the art rect only 0 or 255",
                   "params": GROUND, "demo": "docs/david-goliath/design/ground-sand-demo.png (half size)"},
        "budget": {"maxTris": 20000, "note": "raised from 15,000: the set is 3-4x larger; hills ~3,000 each, midground dunes ~1,500, rocks ~150, tents ~120"},
        "camera": "phone eye about (-0.08, 0.95, +1.15) looking at (-0.08, 0.05, -0.50), 55 deg vertical FOV (DGPreview phone view)",
    }
    design = {
        "version": 3,
        "generatedBy": "docs/david-goliath/design/make_design.py",
        "style": "realistic-proportion cartoon (Pixar-like); CONTRACT §11",
        "units": "art-width units (1.0 = art rectangle width); Y up; ground y=0; +X viewer's right; +Z toward viewer",
        "uv": "characters: u = x + sheetX + 0.5, v = (y + sheetY) / artHeightUnits (front projection, rest pose); desert: see desert.uvRule",
        "artHeightUnits": round(ART_H, 5),
        "restPose": {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z",
                     "hands": {"david": {"R": "fist round the sling cords", "L": "open, fingers together, thumb forward"},
                               "goliath": {"R": "fist round the spear shaft (knuckles toward +Z)", "L": "fist on the shield grip, behind the shield"}},
                     "contractNote": "§11 supersedes D2 (40 deg): 45 deg so both realistic-length arms fit"},
        "lines": {"outerPx": LINE_OUTER * PX, "detailPx": LINE_DETAIL * PX, "facePx": LINE_FACE * PX,
                  "note": "all printed lines <= 8 px are removed by the app's line-erase; faces come from decals"},
        "modelling": {
            "method": "one continuous box-modelled cage per body (skin), clothing as separate shells with thickness (Solidify) and hems, "
                      "Subdivision Surface level 1 APPLIED before export; props are separate rigid meshes (one bone each)",
            "trisMax": {"david": 20000, "goliath": 20000, "desert": 15000},
            "cageQuadsTarget": {"david": 2200, "goliath": 2600},
            "fingerBones": ["fingersL", "fingerTipsL", "thumbL", "fingersR", "fingerTipsR", "thumbR"],
            "face": "modelled: brow ridge, nose, nostrils, cheekbones, lips volume, chin, ears, shallow eye sockets; decals (UV1): eyes, brows, mouth",
        },
        "characters": {
            "david": {"height": D["height"], "sheetX": D["sheetX"], "sheetY": SHEET_Y, "headsTall": D["headsTall"],
                      "proportions": flat_props(D, common) | {"tunicHemY": D["tunicHemY"], "beltY": list(D["beltY"])},
                      "depth": {"head": 0.046, "noseTipZ": 0.0235, "chinZ": 0.019, "chest": [-0.013, 0.014], "waist": [-0.010, 0.012],
                                "tunicHem": [-0.022, 0.0235], "upperArm": 0.014, "forearm": 0.012, "thigh": 0.022, "calf": [-0.0095, 0.0060],
                                "foot": [-0.010, 0.034], "hairBackZ": -0.0275, "bag": [0.000, 0.016]},
                      "bonesLocal": dB, "bonesSheet": sheet_bones(dB, D["sheetX"]),
                      "props": {"sling": {"cordLength": round(cy_ - 0.008 - 0.0855, 4), "cordBandWidth": [0.004, 0.0136], "pouch": [0.024, 0.018, 0.010],
                                          "note": "two cords as one colourable band, from the bottom of the right fist; pouch below"},
                                "stone": {"diameter": 0.011, "restCentre": stone_sheet + [0.004], "note": "smooth stone in the pouch (17:40)"},
                                "bag": {"size": [0.026, 0.024, 0.016], "centreLocal": [0.030, 0.153, 0.016], "strap": "right shoulder -> front of left hip, 0.0048 wide", "follows": "hips"}},
                      "regions": region_info(davS, "david"), "defaultExpression": "brave"},
            "goliath": {"height": G["height"], "sheetX": G["sheetX"], "sheetY": SHEET_Y, "headsTall": G["headsTall"],
                        "proportions": flat_props(G, common) | {"kiltHemY": G["kiltHemY"], "armourHemY": G["armourHemY"], "beltY": list(G["beltY"]),
                                                                "helmetTop": G["helmetTop"], "crestTop": G["crestTop"]},
                        "depth": {"head": 0.092, "noseTipZ": 0.051, "beardZ": [0.020, 0.047], "chest": [-0.075, 0.080], "waist": [-0.068, 0.070],
                                  "kiltHem": [-0.088, 0.092], "upperArm": 0.052, "forearm": 0.044, "thigh": 0.066, "calf": [-0.030, 0.030],
                                  "foot": [-0.027, 0.088], "helmet": [-0.060, 0.048]},
                        "bonesLocal": gB, "bonesSheet": sheet_bones(gB, G["sheetX"]),
                        "props": {"spear": {"length": round(0.955 - 0.003, 3), "shaftDiameter": 0.019, "head": {"length": 0.107, "width": 0.040},
                                            "collar": [0.026, 0.016], "butt": "bronze spike 0.028", "restX": round(ggrip[0] + G["sheetX"], 4),
                                            "y": [round(0.003 + SHEET_Y, 4), round(0.955 + SHEET_Y, 4)], "note": "vertical in the right fist; grip = fist centre"},
                                  "shield": {"diameter": round(2 * G["shieldR"], 3), "rim": 0.011, "bossDiameter": 0.034, "thickness": 0.010, "dish": 0.008,
                                             "centreSheet": [round(sc[0] + G["sheetX"], 4), round(sc[1] + SHEET_Y, 4), 0.035],
                                             "note": "round bronze shield on the left fist/forearm, face toward +Z; fist hidden behind it"},
                                  "helmet": {"dome": [0.096, 0.055], "rimBand": 0.0105, "neckGuard": "flares to x ±0.053 down to y 0.680",
                                             "crest": "transverse fan, 0.104 wide, 0.037 tall", "noFaceGuard": True}},
                        "regions": region_info(golS, "goliath"), "defaultExpression": "grumpy"},
        },
        "palette": {c: {r: v[0] for r, v in PALETTE[c].items()} for c in PALETTE},
        "sheet": {
            "page": list(PAGE), "dpi": 150, "art": list(ART), "markers": MARKERS, "markerSize": MARKER_SIZE,
            "titleBand": [120, 10, 1000, 262],
            "title": {"hanzi": "大卫与歌利亚", "pinyin": "dà wèi yǔ gē lì yà", "english": "David & Goliath", "box": 76, "gap": 12, "cy": 100,
                      "label": "DoodLive · 涂上颜色，再用手机扫一扫"},
            "footer": {"rect": [300, 1604, 820, 110], "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上", "撒母耳记上 17 章 · 1 Samuel 17"],
                       "note": "right of the brook (centre x = page 710); line 1 centre y = rect y + 40, line 2 = y + 76 "
                               "(make_dg_sheet.py); lowest glyph >= 6 mm from the page bottom"},
            "figureRectsPx": {"david": to_page_rect(D["bboxSheet"]), "goliath": to_page_rect(G["bboxSheet"])},
            "decorSuggestion": None,
            "decorNote": "sun and clouds are gone: the desert (design.json desert) fills the sheet instead",
            "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge; title cy 100 "
                        "puts the pinyin >= 6 mm from the top",
        },
        "desert": desert_json,
        "checks": report,
    }
    os.makedirs(os.path.dirname(OUT_JSON), exist_ok=True)

    # ---- pictures
    render_turnaround("turnaround-david", dav, side_david(), davB, "david", "大卫 David",
                      f"写实比例卡通 · {D['headsTall']} 头身 · 高 0.30 · 箱体建模 + 细分 · 四指 + 拇指", 2600, 0.0022)
    render_turnaround("turnaround-goliath", gol, side_goliath(), golB, "goliath", "歌利亚 Goliath",
                      f"写实比例卡通 · {G['headsTall']} 头身 · 高 0.80（含盔缨）· 鳞甲、护胫、铜盔、圆盾、长枪", 1000, 0.0055)
    render_lineup(davS, golS)
    render_palette()
    render_sheet(davS, golS, desert, design, "sheet-mock-lineart", colours=False)
    render_sheet(davS, golS, desert, design, "sheet-mock-demo-colour", colours=True)
    render_sheet(davS, golS, desert, design, "sheet-layout-annotated", colours=False, annotate=True, stage=stage, pieces=pieces, acting=acting)
    render_chars_only(davS, golS)
    mask, _, _ = ground_mask(chars, pieces)
    shots = [{"name": "ar-mock-desert.png", "eye": [-0.08, 0.95, 1.15], "target": [-0.08, 0.05, -0.50], "vfov": 55, "res": [720, 1280]},
             {"name": "ar-mock-desert-right.png", "eye": [0.30, 0.90, 1.10], "target": [0.10, 0.08, -0.55], "vfov": 55, "res": [720, 1280]},
             {"name": "ar-mock-desert-low.png", "eye": [0.15, 0.30, 0.95], "target": [-0.05, 0.18, -0.30], "vfov": 45, "res": [1280, 720]}]
    report["arMock"] = render_ar_mock(pieces, mask, {"david": [-0.30, 0.10, 35], "goliath": [0.22, -0.25, -35]}, shots)
    if not QUICK:
        render_expressions()
        design["faceDecals"] = render_face_decals()
        report["scanSim"] = scan_sim()
    else:
        old = json.load(open(OUT_JSON)) if os.path.exists(OUT_JSON) else {}
        if "faceDecals" in old: design["faceDecals"] = old["faceDecals"]
    os.remove(os.path.join(HERE, "_chars-only.png")); os.remove(os.path.join(HERE, "_chars-only.svg"))
    design["checks"] = report
    json.dump(design, open(OUT_JSON, "w"), indent=1, ensure_ascii=False)
    print(json.dumps({k: v for k, v in report.items() if k != "desert"}, indent=1, ensure_ascii=False))
    if fails:
        print("FAIL:\n  " + "\n  ".join(fails)); sys.exit(1)
    print("PASS: all design checks")


if __name__ == "__main__":
    main()
