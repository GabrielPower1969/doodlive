"""Blender (headless): Real Miracles story pack, Galilee -> assets/miracles/model/galilee.glb

One tabletop page, two places. Left: Peter's house in Capernaum, built like a doll's house: plastered walls, the
front cut away to a low sill so the room is seen from the front (reed mat floor, two short benches in the back
corners, two water jars under the back window, a ledge with an oil lamp, three ceiling beams), a side door in the right
wall (its leaf swung open into the yard), a flat walkable roof of packed mud (top y 0.40) with a low parapet on the back
and the right side, and the outside `stair` up the left wall to a landing on the roof's back-left corner. In the roof:
`roofPatch` (the intact square over the landing spot); hidden props `roofHole` (the opened ragged hole with broken
branch ends) and `rubble` (a flat heap of mud and twigs on the floor beside the landing spot). `crowd1`...`crowd8`:
fixed-colour townsfolk (four at the side door, two seated inside on the benches, two heads at the back window).
Middle: the packed-earth `yard` (with `figTree` and `olivePress`), the pale `road` from the front right to the yard and
along the front to the stair foot, the rest of the floor `ground`. Right back: the `lake` (an armature; skinned child
`lakeWater` in two blues, looping action `lakeWave`) with Peter's `boat` (round-bellied hull, deck at y 0.06, a low
mast with a furled sail on an athwartship yard, a steering oar on the stern quarter, a net coil in the bow, two oars on
the deck, the stern `cushion`; looping action `boatRock`), the pebble `beach` along the lake's front with reeds at the
right, and the far-shore `hills` along the back edge.
Contract: docs/miracles/CONTRACT.md §6. Nodes, marks, clearances and deviations: docs/miracles/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `mi_page` = the scanned art rectangle): as Jonah (pipeline/jn_coast.py). Each piece
belongs to one *drawing* on the colouring sheet, a linear view a = A.P, b = B.P (depth D.P), and
  u = a / scale + sheetX + 0.5,   v = (b / scale + sheetY) / 1.227
Faces nearly edge-on to their drawing take one clean texel of their own region; scattered and thin bits (mast, oars,
crowd, twigs, jars, ceiling) take the texel of a named (drawing, region). The room seen through the open front is its
own drawing (`room`: back wall inside, floor mat, benches), so the inside never samples the outside (LESSONS L51).

Modes (run from the repo root, one Blender at a time):
  nice -n 10 blender -b --factory-startup --python pipeline/mi_galilee.py -- build     galilee.glb + .blend + drawings
  nice -n 10 blender -b --factory-startup --python pipeline/mi_galilee.py -- verify    re-import galilee.glb, check it
  nice -n 10 blender -b --factory-startup --python pipeline/mi_galilee.py -- all       build, preview, verify
  nice -n 10 blender -b --factory-startup --python pipeline/mi_galilee.py -- check     build in memory, print checks
Work files go to $MI_WORK (default /tmp/miracles_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector, Quaternion, Euler
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/miracles/model")
GLB = os.path.join(MODEL, "galilee.glb")
BLEND = os.path.join(MODEL, "galilee.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/miracles/design.json")
TIMELINE = os.path.join(ROOT, "assets/miracles/timeline.json")
ENV = "MI_"
WORK = os.environ.get(ENV + "WORK", "/tmp/miracles_set")
PAGE_MATERIAL = "mi_page"
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
MAX_TRIS = 70000
TAU = 2 * math.pi
UP = (0.0, 1.0, 0.0)
FLOOR = (-0.60, 0.60, -0.5875, 0.21)          # x0 x1 zBack zFront
sys.path.insert(0, HERE)                                                             # noqa: E402
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "stage")


# ============================================================================================ layout (CONTRACT §6)
ROOF = 0.40                                    # walkable roof top
CEIL = 0.385                                   # roof slab underside (contract 0.37; raised: Peter is 0.381 tall, SET.md)
PARA = 0.43                                    # parapet top (back wall and right side)
DECK = 0.06
CARRY_Y = 0.10
IN_X = (-0.452, -0.040)                        # room interior
IN_Z = (-0.560, -0.260)
WL = (-0.478, -0.452)                          # left wall (outer face 0.052 from the stair walk at x -0.53)
WR = (-0.040, -0.014)                          # right wall
WB = (-0.585, -0.560)                          # back wall (to PARA)
HOUSE_C = (-0.246, -0.4225)                    # node origin (footprint centre)
DOOR_Z, DOOR_H = (-0.45, -0.35), 0.26          # side door in the right wall, centre z -0.40, 0.10 wide
WIN_X, WIN_Y = (-0.30, -0.18), (0.17, 0.29)    # back window
SILL_Z, SILL_H = (-0.285, -0.260), 0.010       # the cut-away front: a sill 1 cm high (contract: <= 0.05)
HOLE = (-0.24, -0.38)                          # = LAND
PATCH = 0.07                                   # roofPatch half size (0.14 x 0.14)
HOLE_R = 0.06                                  # ragged hole half size (0.12 x 0.12)
BEAMS_Z = (-0.270, -0.505, -0.545)             # ceiling beams along x (all >= 0.10 from LAND in z: the shaft)
BEAM_Y, BEAM_R = 0.381, 0.004
BENCHES = [(-0.452, -0.385), (-0.115, -0.040)]  # x ranges, z -0.56..-0.52, top 0.05
BENCH_Z, BENCH_H = (-0.560, -0.520), 0.050
JARS = [(-0.312, -0.540, 0.020, 0.066), (-0.268, -0.544, 0.018, 0.058)]
LEDGE = (-0.140, -0.090, 0.200)
STAIR_X = (-0.580, -0.478)
STAIR_Z = (-0.060, -0.440)
STAIR_N = 10
LANDING_Z = (-0.585, -0.440)
RUBBLE = (-0.30, -0.44)
# yard / road / lake / boat
LAKE_Y = 0.012
BEACH_Z = (-0.120, 0.000)
FIG = (0.16, -0.50)
PRESS = (0.12, -0.22)
BOAT_C = (0.36, -0.34)
BOAT_X = (0.158, 0.562)
BOAT_HB = 0.070
MAST = (0.218, -0.34)                          # moved from (0.26, -0.34): see SET.md (BOAT_PETER is 0.028 from it)
MAST_TOP = 0.415
YARD_A, YARD_B = (0.214, 0.392, -0.340), (0.158, 0.150, -0.340)   # the yard lowered from the mast head to the bow,
                                                                   # the sail furled along it
CUSHION = (0.505, -0.34)
HILLS_X, HILLS_Z = (0.000, 0.600), (-0.5875, -0.575)


def shore_x(z):
    """the lake's left (west) edge: straight at x 0.14, bending out round the fig tree's corner at the back"""
    t = min(1.0, max(0.0, (-0.40 - z) / 0.07))
    return 0.14 + 0.085 * t * t * (3 - 2 * t)


def beach_front(x):
    return BEACH_Z[1] + 0.006 * math.sin(23 * x + 0.7) + 0.003 * math.sin(57 * x)


# ============================================================================================ marks and paths
G = 0.0
MARKS = {                       # label: (x, z, floor y, head top or None)   CONTRACT §6 "Marks that must stay clear"
    "jesus teach": (-0.36, -0.46, G, 0.36), "jesus kneel": (-0.34, -0.40, G, 0.36),
    "peter in": (-0.12, -0.46, G, 0.381), "LAND": (-0.24, -0.38, G, None),
    "road 0.20,0.14": (0.20, 0.14, G, None), "road 0.10,0.08": (0.10, 0.08, G, None),
    "road 0.30,0.20": (0.30, 0.20, G, None), "road 0.02,0.14": (0.02, 0.14, G, None),
    "road 0.10,0.20": (0.10, 0.20, G, None), "yard 0.12,-0.04": (0.12, -0.04, G, None),
    "yard 0.02,-0.10": (0.02, -0.10, G, None), "road 0.22,0.02": (0.22, 0.02, G, None),
    "road -0.04,0.00": (-0.04, 0.00, G, None), "road 0.08,0.06": (0.08, 0.06, G, None),
    "YARD": (0.02, -0.12, G, None), "front -0.40,-0.06": (-0.40, -0.06, G, None),
    "STAIR_FOOT": (-0.53, -0.08, G, None), "front -0.26,-0.06": (-0.26, -0.06, G, None),
    "front -0.30,0.02": (-0.30, 0.02, G, None), "front -0.20,0.02": (-0.20, 0.02, G, None),
    "front -0.53,0.00": (-0.53, 0.00, G, None), "MAN_HOME": (-0.10, 0.14, G, None), "MAN_END": (-0.14, 0.10, G, None),
    "stair -0.53,-0.40": (-0.53, -0.40, ROOF, None), "stair -0.53,-0.24": (-0.53, -0.24, 0.20, None),
    "stair -0.53,-0.10": (-0.53, -0.10, 0.04, None), "stair -0.53,-0.36": (-0.53, -0.36, ROOF, None),
    "roof -0.40,-0.46": (-0.40, -0.46, ROOF, None), "roof -0.40,-0.30": (-0.40, -0.30, ROOF, None),
    "STAIR_TOP": (-0.53, -0.46, ROOF, None), "roof -0.24,-0.30": (-0.24, -0.30, ROOF, None),
    "R1": (-0.36, -0.38, ROOF, None), "R2": (-0.12, -0.38, ROOF, None), "R3": (-0.32, -0.50, ROOF, None),
    "R4": (-0.16, -0.50, ROOF, None),
    "deck 0.42,-0.34": (0.42, -0.34, DECK, None), "BOAT_PETER": (0.28, -0.32, DECK, None),
    "BOAT_STERN": (0.48, -0.34, DECK, None), "BOAT_WAKE": (0.38, -0.32, DECK, None),
    "BEACH_J": (0.18, 0.04, G, None), "BEACH_P": (0.32, 0.06, G, None)}
INDOOR = {"jesus teach", "jesus kneel", "peter in", "LAND"}
HEIGHTS = {"jesus": 0.36, "peter": 0.381, "man": 0.34}
CONTRACT_PATHS = [("stair walk", "STAIR_FOOT", "stair -0.53,-0.40")]     # the one walk CONTRACT §6 spells out
TERRAIN = {"yard", "road", "ground", "beach", "lakeWater", "stair"}


def _timeline_moves():
    """(label, (x, z, y) a, (x, z, y) b, who) for consecutive targets of one actor in timeline.json; jumps (snap) are
    not walks"""
    out = []
    try:
        tl = json.load(open(TIMELINE))
    except Exception:
        return out
    last = {}
    for a in tl["acting"]:
        if "to" not in a:
            continue
        w = a["who"]; p = (float(a["to"][0]), float(a["to"][1]), float(a.get("y") or 0.0))
        if w in last and not a.get("snap") and math.hypot(p[0] - last[w][0], p[1] - last[w][1]) > 1e-4 \
                and max(abs(p[0]), abs(last[w][0])) < 0.62:
            out.append(("%s %.2f,%.2f>%.2f,%.2f" % (w, last[w][0], last[w][1], p[0], p[1]), last[w], p, w,
                        a.get("clip")))
        last[w] = p
    return out


TL_MOVES = _timeline_moves()
HARD_PTS = [(x, z) for x, z, _, _ in MARKS.values()]
HARD_SEGS = [((MARKS[a][0], MARKS[a][1]), (MARKS[b][0], MARKS[b][1])) for _, a, b in CONTRACT_PATHS] + \
    [((a[0], a[1]), (b[0], b[1])) for _, a, b, _, _ in TL_MOVES]
SOFT_SEGS = []

# demo colouring (DESIGN.md §3; the rest chosen to sit with it)
COLOURS = {
    "walls": "#E6CFA0", "roof": "#B8875A", "door": "#4E8A86", "wallIn": "#EBD8B0", "floor": "#D9C08A",
    "wood": "#6B4A30", "yard": "#D8BE8E", "road": "#E8D5A8", "ground": "#C9C08A", "beach": "#CDBFA6",
    "lake": "#4A9AD8", "lakeFar": "#2C6BAE", "hull": "#8A5A3B", "deck": "#C9A77A", "sail": "#F3E9D2",
    "cushion": "#9C3A3A", "hills": "#8E86A8", "fig": "#5E9A48", "trunk": "#7A6650",
}


# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model), faces with region, smooth flag, a
    no-raster flag (scattered bits that sample a named texel) and optional skin weights (as Jonah)"""

    def __init__(self):
        self.V, self.P, self.F, self.R, self.S, self.N = [], [], [], [], [], []
        self.W = {}
        self.nr = False

    def v(self, x, h, z, p=None):
        self.V.append((float(x), float(h), float(z)))
        self.P.append(tuple(float(c) for c in p) if p is not None else self.V[-1])
        return len(self.V) - 1

    def fo(self, idx, reg, out, smooth=False):
        idx = list(idx)
        if len(set(idx)) < 3:
            return
        P = [Vector(self.V[i]) for i in idx]
        n = Vector((0, 0, 0))
        for i in range(len(P)):
            a, b = P[i], P[(i + 1) % len(P)]
            n.x += (a.y - b.y) * (a.z + b.z); n.y += (a.z - b.z) * (a.x + b.x); n.z += (a.x - b.x) * (a.y + b.y)
        if n.dot(Vector(out)) < 0:
            idx.reverse()
        self.F.append(idx); self.R.append(reg); self.S.append(smooth); self.N.append(self.nr)


REGION_MATS = {}
P_OF, NR_OF, REG_OF = {}, {}, {}
DECOR = {}                    # drawing -> [(p0, p1)] single drawn lines in drawing-model coords


def quad(mb, pts, reg, out, smooth=False):
    mb.fo([mb.v(*p) for p in pts], reg, out, smooth)


def wall(mb_out, mb_in, x0, x1, h0, h1, z0, z1, inner, skip=(), reg="walls", ireg="wallIn"):
    """axis box whose `inner` face (one of left right front back) goes to the interior mesh, the rest outside"""
    box(mb_out, x0, x1, h0, h1, z0, z1, reg, skip=tuple(skip) + (inner, "bottom"))
    if inner and mb_in is not None:
        q = {"left": [(x0, h0, z0), (x0, h1, z0), (x0, h1, z1), (x0, h0, z1)],
             "right": [(x1, h0, z0), (x1, h1, z0), (x1, h1, z1), (x1, h0, z1)],
             "front": [(x0, h0, z1), (x1, h0, z1), (x1, h1, z1), (x0, h1, z1)],
             "back": [(x0, h0, z0), (x1, h0, z0), (x1, h1, z0), (x0, h1, z0)]}[inner]
        o = {"left": (-1, 0, 0), "right": (1, 0, 0), "front": (0, 0, 1), "back": (0, 0, -1)}[inner]
        quad(mb_in, q, ireg, o)


def bilinear_weights(x, z, bx, bz, names):
    """skin weights of a point on a regular bone grid (<= 4 influences)"""
    fx = (x - bx[0]) / (bx[1] - bx[0]) if len(bx) > 1 else 0.0
    fz = (z - bz[0]) / (bz[1] - bz[0]) if len(bz) > 1 else 0.0
    i = int(min(max(math.floor(fx), 0), len(bx) - 2)); j = int(min(max(math.floor(fz), 0), len(bz) - 2))
    u = min(max(fx - i, 0.0), 1.0); w = min(max(fz - j, 0.0), 1.0)
    out = {}
    for (di, dj, k) in ((0, 0, (1 - u) * (1 - w)), (1, 0, u * (1 - w)), (0, 1, (1 - u) * w), (1, 1, u * w)):
        if k > 1e-4:
            out[names[i + di][j + dj]] = out.get(names[i + di][j + dj], 0.0) + k
    return out


# ============================================================================================ house
def build_house(root):
    """`house` (outside shell: walls, sill, roof slab, parapets, door leaf) with children `houseIn` (everything seen
    through the open front: inner wall faces, floor mat, benches, jars, ledge + lamp, ceiling and beams), `roofPatch`,
    `roofHole`, `rubble`"""
    ex, inn = MB(), MB()
    zf = IN_Z[1]
    # left wall (its outer face is hidden by the stair; kept for the gaps between the steps)
    wall(ex, inn, WL[0], WL[1], 0.0, CEIL, IN_Z[0], zf, "right", skip=("top", "back"))
    # right wall with the side door
    d0, d1 = DOOR_Z
    wall(ex, inn, WR[0], WR[1], 0.0, CEIL, IN_Z[0], d0, "left", skip=("top", "back"))
    wall(ex, inn, WR[0], WR[1], 0.0, CEIL, d1, zf, "left", skip=("top",))
    wall(ex, inn, WR[0], WR[1], DOOR_H, CEIL, d0, d1, "left", skip=("top", "front", "back"))
    # back wall (full width, to the parapet) with the window
    w0, w1 = WIN_X; y0, y1 = WIN_Y
    wall(ex, inn, WL[0], WR[1], 0.0, y0, WB[0], WB[1], "front", skip=("top",))
    wall(ex, inn, WL[0], w0, y0, y1, WB[0], WB[1], "front", skip=("top", "bottom", "left"))
    wall(ex, inn, w1, WR[1], y0, y1, WB[0], WB[1], "front", skip=("top", "bottom", "right"))
    wall(ex, inn, WL[0], WR[1], y1, CEIL, WB[0], WB[1], "front", skip=("top", "bottom"))
    box(ex, WL[0], WR[1], CEIL, PARA, WB[0], WB[1], "walls", skip=("bottom", "front"))
    quad(ex, [(WL[0], ROOF, WB[1]), (WR[1], ROOF, WB[1]), (WR[1], PARA, WB[1]), (WL[0], PARA, WB[1])], "walls", (0, 0, 1))
    # window reveals (sill up, head down, jambs) belong to the room
    quad(inn, [(w0, y0, WB[0]), (w1, y0, WB[0]), (w1, y0, WB[1]), (w0, y0, WB[1])], "wallIn", UP)
    quad(inn, [(w0, y1, WB[0]), (w1, y1, WB[0]), (w1, y1, WB[1]), (w0, y1, WB[1])], "wallIn", (0, -1, 0))
    for x, o in ((w0, 1), (w1, -1)):
        quad(inn, [(x, y0, WB[0]), (x, y1, WB[0]), (x, y1, WB[1]), (x, y0, WB[1])], "wallIn", (o, 0, 0))
    # sill: the cut-away front wall
    box(ex, WL[1], WR[0], 0.0, SILL_H, SILL_Z[0], SILL_Z[1], "walls", skip=("bottom", "left", "right"))
    # roof slab round the patch square: top + front + outer edges outside, the underside = ceiling (room, named texel)
    hx, hz = HOLE
    pieces = [(WL[0], hx - PATCH, WB[1], zf, ("right",)), (hx + PATCH, WR[1], WB[1], zf, ("left",)),
              (hx - PATCH, hx + PATCH, WB[1], hz - PATCH, ("left", "right")),
              (hx - PATCH, hx + PATCH, hz + PATCH, zf, ("left", "right"))]
    for x0, x1, z0, z1, sk in pieces:
        box(ex, x0, x1, CEIL, ROOF, z0, z1, "roof", skip=("bottom", "back") + sk)
        inn.nr = True
        quad(inn, [(x0, CEIL, z0), (x1, CEIL, z0), (x1, CEIL, z1), (x0, CEIL, z1)], "ceiling", (0, -1, 0))
        inn.nr = False
    # the hole's own walls (seen once the patch is gone)
    for x0, x1, z0, z1, o in ((hx - PATCH, hx + PATCH, hz - PATCH, hz - PATCH, (0, 0, 1)),
                              (hx - PATCH, hx + PATCH, hz + PATCH, hz + PATCH, (0, 0, -1))):
        quad(ex, [(x0, CEIL, z0), (x1, CEIL, z0), (x1, ROOF, z0), (x0, ROOF, z0)], "roof", o)
    for x, o in ((hx - PATCH, (1, 0, 0)), (hx + PATCH, (-1, 0, 0))):
        quad(ex, [(x, CEIL, hz - PATCH), (x, CEIL, hz + PATCH), (x, ROOF, hz + PATCH), (x, ROOF, hz - PATCH)], "roof", o)
    # right parapet (the back one is the back wall; no parapet on the left: the stair landing and the walks onto the
    # roof cross that edge, and none at the front)
    box(ex, WR[1] - 0.020, WR[1], ROOF, PARA, WB[1], zf, "walls", skip=("bottom", "back"))
    # door leaf, swung open 90 deg into the yard (hinge at the door's back jamb)
    box(ex, WR[1], WR[1] + 0.094, 0.004, DOOR_H - 0.006, d0 - 0.008, d0, "door")
    dec = DECOR.setdefault("house", [])
    for k in range(1, 4):                                       # door planks
        x = WR[1] + 0.094 * k / 4
        dec.append(((x, 0.006, d0 + 0.0001), (x, DOOR_H - 0.008, d0 + 0.0001)))
    # ---- inside
    # floor: reed mat (printed weave)
    quad(inn, [(IN_X[0], 0.003, IN_Z[0]), (IN_X[1], 0.003, IN_Z[0]), (IN_X[1], 0.003, zf), (IN_X[0], 0.003, zf)],
         "floor", UP)
    DECOR.setdefault("room", [])                                 # no printed weave: the floor strip is small
    inn.nr = True                                                # benches: named texel (under 6 mm on the sheet)
    for x0, x1 in BENCHES:                                       # benches in the back corners
        box(inn, x0, x1, 0.0, BENCH_H, BENCH_Z[0], BENCH_Z[1], "wood", skip=("bottom", "back"))
    inn.nr = False
    lx0, lx1, ly = LEDGE                                         # ledge (niche shelf) with an oil lamp
    box(inn, lx0, lx1, ly - 0.008, ly, IN_Z[0], IN_Z[0] + 0.014, "wallIn", skip=("back",))
    inn.nr = True
    for jx, jz, r, h in JARS:
        lathe(inn, [(0.0, 0.0), (r * 0.55, 0.0), (r, h * 0.35), (r * 0.92, h * 0.65), (r * 0.45, h * 0.86),
                    (r * 0.55, h), (r * 0.40, h), (0.0, h * 0.94)], "jar", C=(jx, 0.003, jz), seg=14)
    lathe(inn, [(0.0, 0.0), (0.010, 0.002), (0.012, 0.008), (0.006, 0.013), (0.0, 0.013)], "jar",
          C=((lx0 + lx1) / 2, ly, IN_Z[0] + 0.007), seg=10, sx=1.6)
    sphere(inn, ((lx0 + lx1) / 2 + 0.016, ly + 0.016, IN_Z[0] + 0.007), 0.004, "flame", seg=6, rings=4, sh=1.6)
    for z in BEAMS_Z:                                            # ceiling beams (round logs) along x
        tube(inn, [(IN_X[0], BEAM_Y, z), (IN_X[1], BEAM_Y, z)], BEAM_R, "beam", seg=8)
    inn.nr = False
    house = make_obj("house", ex, root, origin=(HOUSE_C[0], 0.0, HOUSE_C[1]), smooth_angle=30)
    house_in = make_obj("houseIn", inn, house, origin=(HOUSE_C[0], 0.0, HOUSE_C[1]), smooth_angle=40)
    # roofPatch: the intact square, flush with the roof
    pm = MB()
    box(pm, hx - PATCH, hx + PATCH, CEIL, ROOF, hz - PATCH, hz + PATCH, "roof", skip=("bottom", "left", "right",
                                                                                    "front", "back"))
    pm.nr = True
    quad(pm, [(hx - PATCH, CEIL, hz - PATCH), (hx + PATCH, CEIL, hz - PATCH), (hx + PATCH, CEIL, hz + PATCH),
              (hx - PATCH, CEIL, hz + PATCH)], "ceiling", (0, -1, 0))
    pm.nr = False
    for k in (-1, 1):                                            # printed: the patch is packed mud over branches
        dec.append(((hx - PATCH, ROOF + 0.0002, hz + k * 0.025), (hx + PATCH, ROOF + 0.0002, hz + k * 0.025)))
    patch = make_obj("roofPatch", pm, house, origin=(hx, ROOF, hz), smooth_angle=30)
    hole = build_roof_hole(house)
    rubble = build_rubble(house)
    return house, house_in, patch, hole, rubble


def build_roof_hole(parent):
    """roofHole: a ragged frame filling the 0.14 square down to a 0.12 hole, broken branch ends poking into the hole,
    a few dangling twigs (all named texels: mud = the roof, twigs = the room's wood)"""
    mb = MB(); mb.nr = True
    hx, hz = HOLE
    n = 48
    rng = random.Random(5)
    inner = []
    for k in range(n):
        a = TAU * k / n
        c, s = math.cos(a), math.sin(a)
        m = max(abs(c), abs(s))
        r = HOLE_R * (1.0 - 0.10 * rng.random()) / m        # square-ish, ragged
        inner.append((hx + c * r, hz + s * r))
    outer = []
    for k in range(n):
        a = TAU * k / n
        c, s = math.cos(a), math.sin(a)
        m = max(abs(c), abs(s))
        outer.append((hx + c * PATCH / m, hz + s * PATCH / m))
    for k in range(n):
        j = (k + 1) % n
        (ax, az), (bx, bz) = inner[k], inner[j]
        (cx, cz), (dx, dz) = outer[k], outer[j]
        top = ROOF + 0.0015
        mb.fo([mb.v(ax, top, az), mb.v(bx, top, bz), mb.v(dx, top, dz), mb.v(cx, top, cz)], "mud", UP)
        mb.fo([mb.v(ax, top, az), mb.v(bx, top, bz), mb.v(bx, CEIL - 0.004, bz), mb.v(ax, CEIL - 0.004, az)], "mud",
              (hx - (ax + bx) / 2, 0, hz - (az + bz) / 2))
        mb.fo([mb.v(cx, top, cz), mb.v(dx, top, dz), mb.v(dx, CEIL, dz), mb.v(cx, CEIL, cz)], "mud",
              ((cx + dx) / 2 - hx, 0, (cz + dz) / 2 - hz))
    for k in range(10):                                          # crumbs on the rim (<= 0.41: roof rule)
        a = TAU * (k + rng.random() * 0.5) / 10
        r = (HOLE_R + PATCH) / 2 / max(abs(math.cos(a)), abs(math.sin(a)))
        lumpy(mb, (hx + r * math.cos(a), ROOF + 0.002, hz + r * math.sin(a)), 0.0055, "mud", seg=6, rings=4, sh=0.9,
              amp=0.3, seed=k)
    for k in range(7):                                           # broken branch ends poking in, sagging a little
        a = TAU * (k + 0.3) / 7 + rng.uniform(-0.2, 0.2)
        c, s = math.cos(a), math.sin(a)
        m = max(abs(c), abs(s))
        r0, r1 = (PATCH + 0.004) / m, (HOLE_R - rng.uniform(0.010, 0.022)) / m
        y = CEIL + 0.004 + 0.007 * rng.random()
        tube(mb, [(hx + c * r0, y, hz + s * r0), (hx + c * r1, y - 0.006, hz + s * r1)], 0.0028, "twig", seg=5)
    for k in range(4):                                           # dangling twigs at the rim
        a = TAU * (k + 0.6) / 4
        c, s = math.cos(a), math.sin(a)
        m = max(abs(c), abs(s)); r = (HOLE_R - 0.004) / m
        x, z = hx + c * r, hz + s * r
        tube(mb, [(x, CEIL, z), (x - c * 0.004, CEIL - 0.014, z - s * 0.004), (x - c * 0.003, CEIL - 0.024, z - s * 0.003)],
             0.0018, "twig", seg=4)
    mb.nr = False
    return make_obj("roofHole", mb, parent, origin=(hx, ROOF, hz), smooth_angle=50)


def build_rubble(parent):
    """rubble: a flat heap of mud lumps and twigs beside the landing spot; kept under 0.012 so it never blocks a mark
    (contract: h <= 0.02). Origin on the floor at its centre, so a grow pops it up from the floor."""
    mb = MB(); mb.nr = True
    rx, rz = RUBBLE
    rng = random.Random(9)
    lumpy(mb, (rx, 0.0, rz), 0.032, "mud", seg=12, rings=6, sh=0.30, sx=1.1, sz=0.85, amp=0.25, seed=2,
          flat_bottom=0.0)
    for k in range(9):
        a = rng.uniform(0, TAU); r = rng.uniform(0.012, 0.040)
        lumpy(mb, (rx + r * math.cos(a), 0.002, rz + r * math.sin(a) * 0.8), rng.uniform(0.004, 0.008), "mud", seg=6,
              rings=4, sh=0.6, amp=0.3, seed=k + 4, flat_bottom=0.0)
    for k in range(5):
        a = rng.uniform(0, TAU); L = rng.uniform(0.025, 0.045)
        x, z = rx + rng.uniform(-0.02, 0.02), rz + rng.uniform(-0.015, 0.015)
        tube(mb, [(x - L / 2 * math.cos(a), 0.0045, z - L / 2 * math.sin(a)), (x + L / 2 * math.cos(a), 0.007,
                                                                               z + L / 2 * math.sin(a))],
             0.0022, "twig", seg=5)
    mb.nr = False
    ob = make_obj("rubble", mb, parent, origin=(rx, 0.0, rz), smooth_angle=50)
    return ob


def stair_top(i):
    return (i + 0.5) * ROOF / STAIR_N


def build_stair(root):
    """mud-brick steps up the left wall: STAIR_N steps from z -0.06 to -0.44 (tread midpoints on the straight line
    y 0 -> 0.40 the timeline eases along), then the landing block on the roof's back-left corner (top y 0.40)"""
    mb = MB()
    x0, x1 = STAIR_X
    d = (STAIR_Z[0] - STAIR_Z[1]) / STAIR_N
    for i in range(STAIR_N):
        zf = STAIR_Z[0] - i * d; zb = zf - d
        sk = ("bottom", "right", "back") if zf <= IN_Z[1] + 1e-6 else ("bottom", "back")   # in front of the house the
        box(mb, x0, x1, 0.0, stair_top(i), zb, zf, "walls", skip=sk)                       # right side is open air
    box(mb, x0, x1, 0.0, ROOF, LANDING_Z[0], LANDING_Z[1], "walls", skip=("bottom", "right"))
    dec = DECOR.setdefault("house", [])
    rng = random.Random(3)
    for i in range(STAIR_N):                                     # brick joints on the risers
        zf = STAIR_Z[0] - i * d; h = stair_top(i)
        for j in range(int(h / 0.04)):
            y = 0.02 + j * 0.04
            if y < h - 0.006:
                dec.append(((x0, y, zf + 0.0002), (x1, y, zf + 0.0002)))
        xm = x0 + (x1 - x0) * (0.3 + 0.4 * rng.random())
        dec.append(((xm, max(0.0, h - 0.04), zf + 0.0002), (xm, h - 0.002, zf + 0.0002)))
    return make_obj("stair", mb, root, origin=(sum(STAIR_X) / 2, 0.0, (STAIR_Z[0] + LANDING_Z[0]) / 2),
                    smooth_angle=30)


# ============================================================================================ crowd
# name, x, z, height, yaw (deg; 0 = facing +z, 90 = facing -x), pose, robe key, cloth key
ROBE = {"door": ("house", "door"), "hills": ("hills", "hills"), "sail": ("boat", "sail"), "fig": ("fig", "fig"),
        "cushion": ("boat", "cushion"), "lakeFar": ("ground", "lakeFar"), "hull": ("boat", "hull"),
        "yard": ("ground", "yard"), "deck": ("boat", "deck")}
CROWD = [("crowd1", 0.020, -0.425, 0.285, 95, "stand", "door", "sail"),
         ("crowd2", 0.080, -0.410, 0.300, 80, "stand", "cushion", "deck"),
         ("crowd3", 0.040, -0.355, 0.260, 100, "stand", "hills", "sail"),
         ("crowd4", 0.095, -0.330, 0.290, 85, "stand", "fig", "hull"),
         ("crowd5", -0.424, -0.546, 0.230, 0, "sit", "lakeFar", "sail"),
         ("crowd6", -0.062, -0.548, 0.230, 25, "sit", "hull", "door"),
         ("crowd7", -0.268, -0.600, 0.000, 0, "window", "deck", "cushion"),
         ("crowd8", -0.208, -0.602, 0.000, 0, "window", "door", "hills")]


def build_person(root, name, x, z, H, yaw, pose, robe, cloth):
    """a simple townsperson in the set's style (named texels only): robe, head cloth, face, hands. Standing figures
    are H tall; seated ones sit on a bench (seat 0.05) and are H tall seated; window figures are a head and shoulders
    leaning in at the back window."""
    mb = MB(); mb.nr = True
    if pose == "stand":
        k = H / 0.30
        lathe(mb, [(0.0, 0.0), (0.040 * k, 0.0), (0.038 * k, 0.05 * k), (0.032 * k, 0.15 * k), (0.030 * k, 0.21 * k),
                   (0.018 * k, 0.235 * k), (0.0, 0.24 * k)], "robe", seg=14)
        head_c, hr = (0.0, 0.262 * k, 0.0), 0.030 * k
        for s in (-1, 1):
            tube(mb, [(s * 0.030 * k, 0.215 * k, 0.0), (s * 0.040 * k, 0.17 * k, 0.010 * k),
                      (s * 0.036 * k, 0.13 * k, 0.022 * k)], 0.0085 * k, "robe", seg=8)
            sphere(mb, (s * 0.034 * k, 0.122 * k, 0.026 * k), 0.008 * k, "face", seg=8, rings=5)
    elif pose == "sit":
        k = H / 0.25
        seat = BENCH_H
        lathe(mb, [(0.0, seat), (0.034 * k, seat), (0.032 * k, seat + 0.06 * k), (0.028 * k, seat + 0.13 * k),
                   (0.016 * k, seat + 0.155 * k), (0.0, seat + 0.16 * k)], "robe", seg=14)
        for s in (-1, 1):                                        # thighs forward, shins down to the floor
            tube(mb, [(s * 0.015 * k, seat + 0.012, 0.0), (s * 0.016 * k, seat + 0.012, 0.040 * k)], 0.013 * k, "robe",
                 seg=8)
            tube(mb, [(s * 0.016 * k, seat + 0.010, 0.042 * k), (s * 0.016 * k, 0.006, 0.046 * k)], 0.011 * k, "robe",
                 seg=8)
            tube(mb, [(s * 0.028 * k, seat + 0.14 * k, 0.0), (s * 0.034 * k, seat + 0.09 * k, 0.014 * k),
                      (s * 0.020 * k, seat + 0.07 * k, 0.032 * k)], 0.0075 * k, "robe", seg=8)
            sphere(mb, (s * 0.014 * k, seat + 0.068 * k, 0.036 * k), 0.007 * k, "face", seg=8, rings=5)
        head_c, hr = (0.0, seat + 0.182 * k, 0.004), 0.027 * k
    else:                                                        # window: head and shoulders, leaning in
        lathe(mb, [(0.0, 0.14), (0.036, 0.14), (0.034, 0.19), (0.016, 0.205), (0.0, 0.21)], "robe", seg=12, sv=0.7)
        head_c, hr = (0.0, 0.228, 0.008), 0.026
        for s in (-1, 1):                                        # forearms on the window sill
            tube(mb, [(s * 0.030, 0.19, 0.0), (s * 0.026, WIN_Y[0] + 0.008 - 0.0, 0.018),
                      (s * 0.012, WIN_Y[0] + 0.007, 0.030)], 0.0075, "robe", seg=8)
            sphere(mb, (s * 0.010, WIN_Y[0] + 0.008, 0.034), 0.0075, "face", seg=8, rings=5)
    hx, hy, hz = head_c
    sphere(mb, (hx, hy, hz + hr * 0.15), hr, "face", seg=12, rings=8)
    lathe(mb, [(0.0, hy - hr * 0.1), (hr * 1.08, hy - hr * 0.2), (hr * 1.10, hy + hr * 0.45), (hr * 0.75, hy + hr * 0.95),
               (0.0, hy + hr * 1.12)], "cloth", C=(hx, 0.0, hz - hr * 0.22), seg=12)
    for s in (-1, 1):                                            # eyes (detail dots)
        sphere(mb, (hx + s * hr * 0.36, hy + hr * 0.18, hz + hr * 1.05), hr * 0.12, "hair", seg=6, rings=4)
    mb.nr = False
    for i, (vx, vh, vz) in enumerate(mb.V):                      # turn (yaw about the node's own vertical)
        a = math.radians(yaw)
        mb.V[i] = (x + vx * math.cos(a) + vz * math.sin(a), vh, z - vx * math.sin(a) + vz * math.cos(a))
    mb.P = list(mb.V)
    oh = 0.0
    return make_obj(name, mb, root, origin=(x, oh, z), smooth_angle=60)


# ============================================================================================ ground: yard, road, beach
def road_polys():
    main = catmull([(0.33, 0.215), (0.26, 0.15), (0.18, 0.085), (0.11, 0.025), (0.055, -0.04), (0.030, -0.110)], 0.012)
    west = catmull([(0.09, -0.030), (0.0, -0.045), (-0.12, -0.050), (-0.26, -0.046), (-0.40, -0.048), (-0.52, -0.040),
                    (-0.60, -0.036)], 0.012)
    return strip_poly(main, 0.11, 0.09), strip_poly(west, 0.10, 0.09)


def yard_poly():
    zs = np.linspace(-0.07, -0.50, 24)
    right = [(shore_x(z) + 0.002, z) for z in zs]
    return np.array([(-0.014, -0.07)] + right + [(0.06, -0.505), (-0.014, -0.505)])


def lake_poly():
    zs = np.linspace(BEACH_Z[0], FLOOR[2], 30)
    left = [(shore_x(z), z) for z in zs]
    return np.array(left + [(FLOOR[1], FLOOR[2]), (FLOOR[1], BEACH_Z[0])])


def beach_poly():
    xs = np.linspace(shore_x(BEACH_Z[0]), FLOOR[1], 30)
    return np.array([(x, beach_front(x)) for x in xs] + [(FLOOR[1], BEACH_Z[0]), (shore_x(BEACH_Z[0]), BEACH_Z[0])])


HOUSE_BLOCK = np.array([(STAIR_X[0], STAIR_Z[0]), (WL[0], STAIR_Z[0]), (WL[0], IN_Z[1]), (WR[1], IN_Z[1]),
                        (WR[1], FLOOR[2]), (STAIR_X[0], FLOOR[2])])


def land_h(x, z, reg):
    base = {"road": 0.0026, "yard": 0.0022, "beach": 0.0030, "ground": 0.0020}[reg]
    return base + 0.0004 * (nz(x * 7, z * 7) - 0.5)


def build_ground(root):
    """`yard`, `road`, `ground`, `beach` from one constrained triangulation of the floor (the house block and the
    lake left out); `beach` carries pebbles and reeds (named texels); `yard` carries `figTree` and `olivePress`"""
    main, west = road_polys()
    yp, lp, bp = yard_poly(), lake_poly(), beach_poly()
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    outlines = [_resample(rect, 0.02), _resample(HOUSE_BLOCK, 0.02), _resample(lp, 0.012), _resample(main, 0.010),
                _resample(west, 0.010), _resample(yp, 0.012), _resample(bp, 0.012)]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    allo = np.concatenate(outlines)
    for j, z in enumerate(np.arange(FLOOR[2] + 0.01, FLOOR[3] - 0.005, 0.02)):
        for x in np.arange(FLOOR[0] + 0.01 + (j % 2) * 0.01, FLOOR[1] - 0.005, 0.02):
            p = np.array([x, z])
            if np.min(np.hypot(*(allo - p).T)) > 0.008:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def region(c):
        if in_poly(c, HOUSE_BLOCK) or in_poly(c, lp):
            return None
        if in_poly(c, main) or in_poly(c, west):
            return "road"
        if in_poly(c, bp):
            return "beach"
        if in_poly(c, yp):
            return "yard"
        return "ground"
    mbs = {k: MB() for k in ("yard", "road", "ground", "beach")}
    idx = {k: {} for k in mbs}
    for f in fs:
        if len(f) != 3:
            continue
        c = tuple(V[list(f)].mean(0))
        reg = region(c)
        if reg is None:
            continue
        q = []
        for i in f:
            if i not in idx[reg]:
                idx[reg][i] = mbs[reg].v(V[i][0], land_h(V[i][0], V[i][1], reg), V[i][1])
            q.append(idx[reg][i])
        mbs[reg].fo(q, reg, UP, True)
    # printed detail: pebbles on the beach, cracks in the yard, ruts on the road, grass ticks on the ground
    dec = DECOR.setdefault("ground", [])
    rng = random.Random(21)
    for k in range(70):
        x = rng.uniform(0.16, 0.59); z = rng.uniform(BEACH_Z[0] + 0.008, beach_front(x) - 0.008)
        if k % 3 or z > BEACH_Z[0] + 0.035:                      # a few, along the water's edge: keep a 6 mm cell
            continue
        r = rng.uniform(0.004, 0.007)
        pts = [(x + r * math.cos(a), z + r * 0.8 * math.sin(a)) for a in np.linspace(0, TAU, 7)]
        for (a, b_), (c, d) in zip(pts[:-1], pts[1:]):
            dec.append(((a, 0.0034, b_), (c, 0.0034, d)))
    for k in range(10):
        x = rng.uniform(0.0, 0.12); z = rng.uniform(-0.48, -0.10)
        pts = [(x, z)]
        for j in range(3):
            pts.append((pts[-1][0] + rng.uniform(-0.012, 0.012), pts[-1][1] + rng.uniform(0.006, 0.014)))
        for (a, b_), (c, d) in zip(pts[:-1], pts[1:]):
            dec.append(((a, 0.0026, b_), (c, 0.0026, d)))
    for k in range(40):
        x = rng.uniform(-0.58, 0.58); z = rng.uniform(-0.03, 0.20)
        if any(in_poly((x, z + dz), poly) for poly in (main, west, bp) for dz in (-0.012, 0.0, 0.012)):
            continue
        for s in (-1, 0, 1):
            dec.append(((x + s * 0.004, 0.0022, z), (x + s * 0.006, 0.0022, z - 0.008)))
    beach = mbs["beach"]
    beach.nr = True
    for k in range(26):                                          # pebbles (low)
        x = rng.uniform(0.16, 0.58); z = rng.uniform(BEACH_Z[0] + 0.01, beach_front(x) - 0.01)
        lumpy(beach, (x, 0.003, z), rng.uniform(0.004, 0.007), "pebble", seg=6, rings=4, sh=0.45, amp=0.25, seed=k,
              flat_bottom=0.003)
    for k in range(9):                                           # reeds at the right (short: they stand in front of
        x = 0.535 + 0.055 * (k / 8) + rng.uniform(-0.006, 0.006)  # the stern in the low shots)
        z = rng.uniform(-0.10, -0.03)
        for j in range(3):
            a = rng.uniform(-0.5, 0.5); h = rng.uniform(0.035, 0.055)
            blade(beach, [(x, 0.003, z), (x + 0.006 * math.sin(a), 0.003 + h * 0.6, z + 0.004 * math.cos(a)),
                          (x + 0.012 * math.sin(a), 0.003 + h, z + 0.006 * math.cos(a))], [0.004, 0.003, 0.0], "reed")
    beach.nr = False
    yard = make_obj("yard", mbs["yard"], root, smooth_angle=35)
    road = make_obj("road", mbs["road"], root, smooth_angle=35)
    ground = make_obj("ground", mbs["ground"], root, smooth_angle=35)
    beach_ob = make_obj("beach", beach, root, smooth_angle=35)
    return yard, road, ground, beach_ob, (main, west)


def build_fig(yard):
    """figTree: a short trunk forking into three limbs under a crown of broad leaf clumps (crown bottom >= 0.20)"""
    mb = MB(); mb.nr = True                                      # trunk + limbs: named texel (under 6 mm printed)
    fx, fz = FIG
    tube(mb, [(fx, 0.0, fz), (fx - 0.004, 0.08, fz + 0.002), (fx + 0.003, 0.16, fz), (fx, 0.215, fz)],
         [0.021, 0.017, 0.014, 0.011], "trunk", seg=10)
    for dx, dz, h in ((-0.050, 0.010, 0.255), (0.050, 0.008, 0.250), (0.004, -0.030, 0.270)):
        tube(mb, [(fx + 0.002, 0.17, fz), (fx + dx * 0.6, 0.215, fz + dz * 0.6), (fx + dx, h, fz + dz)],
             [0.010, 0.008, 0.006], "trunk", seg=8)
    mb.nr = False
    blobs = [(-0.050, 0.262, 0.012, 0.050), (0.052, 0.258, 0.010, 0.050), (0.000, 0.300, -0.012, 0.058),
             (-0.028, 0.250, 0.040, 0.040), (0.030, 0.252, 0.040, 0.040), (0.000, 0.262, 0.030, 0.046),
             (-0.075, 0.288, -0.020, 0.036), (0.078, 0.282, -0.020, 0.036)]
    for k, (dx, h, dz, r) in enumerate(blobs):
        lumpy(mb, (fx + dx, h, fz + dz), r, "fig", seg=14, rings=8, sh=0.80, amp=0.16, seed=k + 1)
    return make_obj("figTree", mb, yard, origin=(fx, 0.0, fz), smooth_angle=60)


def build_press(yard):
    """olivePress: a round stone basin with an upright crushing wheel and its wooden beam (named texels)"""
    mb = MB(); mb.nr = True
    px, pz = PRESS
    lathe(mb, [(0.0, 0.0), (0.038, 0.0), (0.040, 0.026), (0.034, 0.030), (0.030, 0.022), (0.0, 0.022)], "stone",
          C=(px, 0.0, pz), seg=18)
    lathe(mb, [(0.0, -0.006), (0.022, -0.006), (0.022, 0.006), (0.0, 0.006)], "stone", C=(px - 0.008, 0.044, pz),
          A=(1, 0, 0), U=(0, 1, 0), V=(0, 0, 1), seg=16)
    tube(mb, [(px, 0.022, pz), (px, 0.058, pz)], 0.004, "beam", seg=6)
    tube(mb, [(px - 0.030, 0.044, pz), (px + 0.034, 0.050, pz)], 0.0035, "beam", seg=6)
    mb.nr = False
    return make_obj("olivePress", mb, yard, origin=(px, 0.0, pz), smooth_angle=50)


# ============================================================================================ lake
NBX, NBZ = 4, 3
LAKE_BX = list(np.linspace(0.20, 0.56, NBX))
LAKE_BZ = list(np.linspace(-0.54, -0.16, NBZ))
LAKE_BONES = [["wave_%d_%d" % (i, j) for j in range(NBZ)] for i in range(NBX)]
LAKE_C = (0.37, -0.354)


def lake_h(x, z):
    return LAKE_Y + 0.0009 * math.sin(31 * x + 7 * z) * math.sin(23 * z - 8 * x) + 0.0003 * math.sin(61 * x + 43 * z)


def lake_region(x, z):
    return "lakeFar" if z < -0.455 + 0.018 * math.sin(14 * x + 1.0) else "lake"


def build_lake(root):
    """armature `lake` (action lakeWave: the bone grid bobs, 4 s loop) with the skinned child `lakeWater` (the
    surface: printed wave marks, a deeper band at the back, skirts down to the page)"""
    cx, cz = LAKE_C
    arm = bpy.data.armatures.new("lake_arm")
    rig = link(bpy.data.objects.new("lake", arm))
    rig.location = B(cx, 0.0, cz)
    parent_keep(rig, root)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    O = B(cx, 0, cz)
    r0 = arm.edit_bones.new("lake_root"); r0.head = B(cx, 0, cz) - O; r0.tail = B(cx, 0.03, cz) - O
    for i in range(NBX):
        for j in range(NBZ):
            b = arm.edit_bones.new(LAKE_BONES[i][j])
            b.head = B(LAKE_BX[i], 0, LAKE_BZ[j]) - O; b.tail = B(LAKE_BX[i], 0.03, LAKE_BZ[j]) - O
            b.parent = r0
    for b in arm.edit_bones:
        b.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')
    lp = lake_poly()
    bnd = _resample(lp, 0.010)
    K = len(bnd)
    verts = [Vector((float(x), float(z))) for x, z in bnd]
    for j, z in enumerate(np.arange(FLOOR[2] + 0.006, BEACH_Z[0], 0.0125)):
        for x in np.arange(0.14 + (j % 2) * 0.006, FLOOR[1], 0.0125):
            p = np.array([x, z])
            if in_poly(p, lp) and np.min(np.hypot(*(bnd - p).T)) > 0.005:
                verts.append(Vector((float(x), float(z))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, [(i, (i + 1) % K) for i in range(K)], [list(range(K))], 1, 1e-8,
                                             True)
    V = np.array([(v.x, v.y) for v in vs])
    mb = MB()
    ids = [mb.v(x, lake_h(x, z), z) for x, z in V]
    for f in fs:
        if len(f) != 3:
            continue
        c = V[list(f)].mean(0)
        if not in_poly(c, lp):
            continue
        mb.fo([ids[i] for i in f], lake_region(*c), UP, True)
    for i in range(K):                                           # skirts down to the page
        (ax_, az), (bx, bz) = bnd[i], bnd[(i + 1) % K]
        mx, mz = (ax_ + bx) / 2, (az + bz) / 2
        o = (bz - az, 0, -(bx - ax_))
        if in_poly((mx + o[0] * 0.2, mz + o[2] * 0.2), lp):
            o = (-o[0], 0, -o[2])
        mb.fo([mb.v(ax_, lake_h(ax_, az), az), mb.v(bx, lake_h(bx, bz), bz), mb.v(bx, 0.0, bz), mb.v(ax_, 0.0, az)],
              lake_region(mx, mz), o)
    mb.W = {i: bilinear_weights(mb.V[i][0], mb.V[i][2], LAKE_BX, LAKE_BZ, LAKE_BONES) for i in range(len(mb.V))}
    water = make_obj("lakeWater", mb, None, origin=(cx, 0.0, cz), smooth_angle=60)
    rng = random.Random(4)                                       # printed wave marks: little double arcs
    dec = DECOR.setdefault("ground", [])
    for k in range(46):
        x = rng.uniform(0.17, 0.57); z = rng.uniform(FLOOR[2] + 0.02, BEACH_Z[0] - 0.015)
        if z < -0.43 or x < shore_x(z) + 0.02 or (BOAT_X[0] - 0.01 < x < BOAT_X[1] + 0.01 and abs(z - BOAT_C[1]) < BOAT_HB + 0.012):
            continue
        L = rng.uniform(0.020, 0.030)
        pts = [(x + L * u, z - 0.006 * math.sin(math.pi * u * 2) * (1 if u < 0.5 else 0.6)) for u in np.linspace(0, 1, 7)]
        for (a, b), (c, d) in zip(pts[:-1], pts[1:]):
            dec.append(((a, lake_h(a, b) + 0.0002, b), (c, lake_h(c, d) + 0.0002, d)))
    parent_keep(water, rig)
    mod = water.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
    # lakeWave: 4 s loop at 24 fps (frame 1 == frame 97); whole cycles per loop, so seamless
    rig.animation_data_create()
    for i in range(NBX):
        for j in range(NBZ):
            pb = rig.pose.bones[LAKE_BONES[i][j]]
            inv = rig.data.bones[pb.name].matrix_local.to_3x3().inverted()
            bx, bz = LAKE_BX[i], LAKE_BZ[j]
            for f in range(1, 98, 4):
                u = TAU * (f - 1) / 96
                ph = 10.0 * bx + 5.0 * bz
                dy = 0.0012 * math.sin(u + ph) + 0.0004 * math.sin(2 * u - 7.0 * bz + 1.3 * bx)
                dx = 0.0012 * math.cos(u + ph)
                dz = 0.0006 * math.sin(u + ph + 0.7)
                pb.location = inv @ B(dx, dy, dz)
                pb.keyframe_insert("location", frame=f)
    rig.animation_data.action.name = "lakeWave"
    return rig, water


# ============================================================================================ boat
def boat_w(x):
    u = (x - BOAT_C[0]) / ((BOAT_X[1] - BOAT_X[0]) / 2)
    return max(0.003, BOAT_HB * max(0.0, 1 - abs(u) ** 2.2) ** 0.5)


def boat_gun(x):
    """gunwale top: a 6 mm lip over the deck between the bow and stern rises (deck marks stay clear when rocking)"""
    g = DECK + 0.006
    if x < 0.226:
        g += 0.052 * ((0.226 - x) / 0.068) ** 2
    if x > 0.533:
        g += 0.062 * ((x - 0.533) / 0.029) ** 2
    return g


def boat_keel(x):
    u = (x - BOAT_C[0]) / ((BOAT_X[1] - BOAT_X[0]) / 2)
    return 0.002 + 0.030 * abs(u) ** 4


def build_boat(root):
    """`boat` (pivot = deck centre): round-bellied hull with a 6 mm gunwale lip, deck at 0.06, stem and curled stern
    post, mast + athwartship yard with the furled sail, steering oar on the stern quarter, net coil, two oars; child
    `cushion` at the stern"""
    mb = MB()
    zc = BOAT_C[1]
    xs = list(np.linspace(BOAT_X[0], BOAT_X[1], 33))
    M = 12
    T = 0.007                                                     # side thickness at the rim
    rows = []
    for x in xs:
        w = boat_w(x); g = boat_gun(x); k = boat_keel(x)
        ring = []
        for m in range(M + 1):
            th = math.pi * m / M
            s = math.sin(th)
            ring.append(mb.v(x, g - (g - k) * s ** 0.85, zc - w * math.cos(th)))
        wi = max(0.0, w - T)
        inner = (mb.v(x, g, zc - wi), mb.v(x, g, zc + wi), mb.v(x, DECK, zc - wi), mb.v(x, DECK, zc + wi))
        rows.append((ring, inner, wi))
    for r in range(len(xs) - 1):
        (ra, ia, wa), (rb, ib, wb) = rows[r], rows[r + 1]
        xm = (xs[r] + xs[r + 1]) / 2
        for m in range(M):
            th = math.pi * (m + 0.5) / M
            out = (0.0, -math.sin(th), -math.cos(th))
            mb.fo([ra[m], rb[m], rb[m + 1], ra[m + 1]], "hull", out, True)
        # rim strips, inner walls, deck
        mb.fo([ra[0], rb[0], ib[0], ia[0]], "hull", UP)
        mb.fo([ra[M], rb[M], ib[1], ia[1]], "hull", UP)
        if wa > 0.002 and wb > 0.002:
            mb.fo([ia[0], ib[0], ib[2], ia[2]], "hull", (0, 0, 1))
            mb.fo([ia[1], ib[1], ib[3], ia[3]], "hull", (0, 0, -1))
            mb.fo([ia[2], ib[2], ib[3], ia[3]], "deck", UP)
    for r, o in ((0, -1), (len(xs) - 1, 1)):                      # close the deck well at the ends
        ring, inner, wi = rows[r]
        if wi > 0.002:
            mb.fo([inner[0], inner[1], inner[3], inner[2]], "hull", (o, 0, 0))
    # printed: hull planks and deck boards
    dec = DECOR.setdefault("boat", [])
    for th in ():                                                 # no hull strakes: they cut the hull under 6 mm
        pts = []
        for x in np.linspace(BOAT_X[0] + 0.01, BOAT_X[1] - 0.01, 30):
            w = boat_w(x); g = boat_gun(x); k = boat_keel(x)
            t = math.pi * (1 - th / 2)
            pts.append((x, g - (g - k) * math.sin(t) ** 0.85, zc - w * math.cos(t) + 0.0004))
        for a, b in zip(pts[:-1], pts[1:]):
            dec.append((a, b))
    for x in np.arange(0.22, 0.53, 0.07):
        wi = boat_w(x) - T
        if wi > 0.01:
            dec.append(((x, DECK + 0.0003, zc - wi), (x, DECK + 0.0003, zc + wi)))
    mb.nr = True
    tube(mb, [(BOAT_X[1] - 0.006, DECK, zc), (0.572, 0.110, zc), (0.586, 0.152, zc), (0.580, 0.182, zc),
              (0.565, 0.188, zc), (0.556, 0.176, zc)], [0.009, 0.009, 0.008, 0.007, 0.006, 0.005], "wood", seg=8)
    tube(mb, [(BOAT_X[0] + 0.004, 0.030, zc), (0.152, 0.090, zc), (0.148, 0.128, zc), (0.152, 0.136, zc)],
         [0.008, 0.008, 0.007, 0.006], "wood", seg=8)
    mx, mz = MAST
    tube(mb, [(mx, DECK - 0.01, mz), (mx, MAST_TOP, mz)], [0.0065, 0.0050], "wood", seg=8)
    tube(mb, [YARD_A, YARD_B], 0.0040, "wood", seg=6)
    # steering oar on the stern quarter (front side, so the phone sees it)
    tube(mb, [(0.590, 0.004, -0.262), (0.546, 0.092, -0.278), (0.512, 0.170, -0.280)], [0.0055, 0.0055, 0.0045],
         "wood", seg=8)
    box(mb, 0.584, 0.606, 0.0, 0.045, -0.266, -0.258, "wood")
    tube(mb, [(0.548, boat_gun(0.548) - 0.004, -0.290), (0.546, 0.095, -0.282)], 0.004, "wood", seg=6)
    # two oars lying on the deck along the back side (>= 0.05 from every deck mark)
    for k in range(2):
        z = zc - 0.050 - k * 0.010
        tube(mb, [(0.270 + k * 0.02, DECK + 0.005, z), (0.470 + k * 0.02, DECK + 0.005, z)], 0.0042, "wood", seg=6)
        box(mb, 0.440 + k * 0.02, 0.495 + k * 0.02, DECK + 0.002, DECK + 0.006, z - 0.008, z + 0.008, "wood")
    # net coil in the bow
    for k in range(3):
        pts = [(0.192 + 0.020 * math.cos(a), DECK + 0.006 + k * 0.009, zc + 0.020 * math.sin(a))
               for a in np.linspace(0, TAU, 14, endpoint=False)]
        tube(mb, pts, 0.0065, "net", seg=6, closed=True)
    mb.nr = False
    # the furled sail under the yard (its own region: the cream bundle)
    sail = []
    for t in np.linspace(0.04, 0.92, 9):
        p = Vector(YARD_A).lerp(Vector(YARD_B), t)
        sail.append((p.x - 0.012 - 0.006 * math.sin(math.pi * t), p.y - 0.010, p.z))
    tube(mb, sail, [0.010, 0.017, 0.022, 0.025, 0.026, 0.025, 0.022, 0.017, 0.011], "sail", seg=12)
    for t in (0.25, 0.5, 0.75):                                  # the ties round the bundle (printed)
        p = Vector(YARD_A).lerp(Vector(YARD_B), 0.04 + 0.88 * t)
        r = 0.026 * math.sin(math.pi * (0.04 + 0.88 * t)) ** 0.5
        dec.append(((p.x - 0.012 - r * 0.8, p.y - 0.010 + r * 0.6, p.z + r + 0.0005),
                    (p.x - 0.012 + r * 0.8, p.y - 0.010 - r * 0.6, p.z + r + 0.0005)))
    boat = make_obj("boat", mb, root, origin=(BOAT_C[0], DECK, BOAT_C[1]), smooth_angle=45)
    cm = MB()
    cx, cz = CUSHION
    # puff builds a pillow from an outline in (x, h) with its thickness along z: build the outline in (x, z), then
    # swap h and z so it lies flat on the deck (the swap mirrors, so the faces are turned back)
    outline = [(cx + 0.041 * math.cos(a) * (1 + 0.12 * math.cos(2 * a)), cz + 0.033 * math.sin(a))
               for a in np.linspace(0, TAU, 28, endpoint=False)]
    puff(cm, outline, 0.0, 0.020, "cushion", rad=0.018, edge=0.30, step=0.006)
    cm.V = [(x, DECK + 0.020 + o, b) for x, b, o in cm.V]
    cm.P = list(cm.V)
    cm.F = [f[::-1] for f in cm.F]
    cushion = make_obj("cushion", cm, boat, origin=(cx, DECK, cz), smooth_angle=60)
    return boat, cushion


def boat_rock(boat):
    """boatRock: 6 s loop at 24 fps (frame 1 == frame 145): +-3 deg roll about the long axis, a little pitch"""
    boat.animation_data_create()
    boat.rotation_mode = 'XYZ'
    loc = boat.location.copy()
    for f in range(1, 146, 4):
        u = TAU * (f - 1) / 144
        boat.rotation_euler = (math.radians(3.0) * math.sin(u), math.radians(0.5) * math.sin(2 * u + 0.8), 0.0)
        boat.location = loc
        boat.keyframe_insert("rotation_euler", frame=f)
        boat.keyframe_insert("location", frame=f)
    boat.animation_data.action.name = "boatRock"
    boat.rotation_euler = (0, 0, 0)
    bpy.context.scene.frame_set(1)


# ============================================================================================ hills
def hills_top(x):
    return 0.150 + 0.034 * math.sin(9.5 * x + 0.4) + 0.016 * math.sin(23 * x + 1.1) - 0.02 * max(0.0, 0.08 - x) / 0.08


def build_hills(root):
    """far-shore hills: a low relief along the back edge (front face z -0.575), two ridges, tops 0.12-0.20"""
    mb = MB()
    xs = np.linspace(HILLS_X[0], HILLS_X[1], 60)
    back = [(x, 0.0) for x in xs[::-1]] + [(x, min(0.20, max(0.12, hills_top(x)))) for x in xs]
    extrude(mb, back[::-1], HILLS_Z[0], -0.5805, "hills")
    xs2 = np.linspace(0.06, 0.60, 44)
    front = [(x, 0.0) for x in xs2[::-1]] + \
        [(x, 0.085 + 0.022 * math.sin(13 * x + 2.2) + 0.010 * math.sin(31 * x)) for x in xs2]
    extrude(mb, front[::-1], -0.5805, HILLS_Z[1], "hills")
    dec = DECOR.setdefault("hills", [])
    rng = random.Random(8)
    for k in range(9):                                            # little tree / bush marks on the far shore
        x = rng.uniform(0.08, 0.58); h = 0.085 + 0.022 * math.sin(13 * x + 2.2) + 0.010 * math.sin(31 * x) - 0.012
        dec.append(((x - 0.006, h - 0.004, HILLS_Z[1] + 0.0002), (x, h + 0.008, HILLS_Z[1] + 0.0002)))
        dec.append(((x, h + 0.008, HILLS_Z[1] + 0.0002), (x + 0.006, h - 0.004, HILLS_Z[1] + 0.0002)))
    return make_obj("hills", mb, root, origin=(0.30, 0.0, HILLS_Z[1]), smooth_angle=30)


# ============================================================================================ drawings / UV
def _chars_proposal():
    """CONTRACT §2 start slots (sizes from the contract; widths guessed) until regions_characters.json exists"""
    return {"man": {"sheetX": -0.32, "sheetY": 0.015, "height": 0.34, "box": [-0.47, 0.015, -0.17, 0.36]},
            "jesus": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.36, "box": [-0.15, 0.015, 0.15, 0.38]},
            "peter": {"sheetX": 0.32, "sheetY": 0.015, "height": 0.38, "box": [0.17, 0.015, 0.47, 0.40]}}


def _chars():
    """kit _chars, tolerant of a cast file still being written"""
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    rc = json.load(open(p))
    got = {}
    for c, v in rc["characters"].items():
        if c not in rc.get("sheet", {}) or "bboxSheet" not in v:
            continue
        h = v.get("height") or prop.get(c, {}).get("height")
        got[c] = {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"], "height": h,
                  "box": v["bboxSheet"]}
    for c, v in prop.items():
        got.setdefault(c, v)
    ms = rc["characters"].get("man", {}).get("matSheet")       # the man's mat is printed apart from him (CONTRACT §2)
    if ms and "bboxSheet" in ms:
        got["man_mat"] = {"sheetX": ms["centre"][0], "sheetY": ms["centre"][1], "height": None, "box": ms["bboxSheet"]}
    return got, all(c in rc.get("sheet", {}) for c in prop)


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
MAT_SHEET = (-0.28, 0.47)        # the mat's printed centre (= the Characters role's default); the middle band is laid
                                 # out round its box (-0.484..-0.076 x 0.395..0.545)
DRAWINGS = {
    # middle band: the man's mat (Characters role, matSheet bbox -0.484..-0.076 x 0.395..0.545) sits under the room
    # and the fig tree on the left; the ground plan is right of the mat; the house is raised to make room
    "house":  dict(P_OBL(0.35, 0.5), scale=1.62, cx=-0.236, y0=0.785, members=["house", "stair", "roofPatch"]),
    "room":   dict(P_OBL(0.0, 0.35), scale=2.36, cx=-0.382, y0=0.565, decorOnly=["floor"], members=["houseIn"]),
    "ground": dict(P_PLAN(), scale=3.00, cx=0.146, y0=0.430, decorOnly=["lake", "lakeFar", "beach", "yard", "road",
                                                                         "ground"],
                   members=["yard", "road", "ground", "beach", "lakeWater"]),
    "boat":   dict(P_OBL(0.35, 0.5), scale=1.10, cx=0.249, y0=0.726, decorOnly=["hull", "deck"],
                   members=["boat", "cushion"]),
    "hills":  dict(P_FRONT(), scale=1.62, cx=0.262, y0=1.096, decorOnly=["hills"], members=["hills"]),
    "fig":    dict(P_FRONT(), scale=1.45, cx=-0.180, y0=0.620, members=["figTree"]),
}
TEMPLATES = {}
CONSTS = {"house": {},
          "houseIn": {"ceiling": ("house", "roof"), "beam": ("boat", "hull"), "jar": ("house", "roof"),
                      "wood": ("boat", "hull"),
                      "flame": ("fig", "fig")},
          "roofPatch": {"ceiling": ("house", "roof")},
          "figTree": {"trunk": ("boat", "hull")},
          "roofHole": {"mud": ("house", "roof"), "twig": ("boat", "hull")},
          "rubble": {"mud": ("house", "roof"), "twig": ("boat", "hull")},
          "beach": {"pebble": ("hills", "hills"), "reed": ("fig", "fig")},
          "olivePress": {"stone": ("ground", "beach"), "beam": ("boat", "hull")},
          "boat": {"wood": ("boat", "hull"), "net": ("boat", "sail")},
          **{c[0]: {"robe": ROBE[c[6]], "cloth": ROBE[c[7]], "face": ("house", "walls"), "hair": ("boat", "hull")}
             for c in CROWD}}
RS = [1]
ORDER = ["house", "houseIn", "roofPatch", "roofHole", "rubble", "stair"] + [c[0] for c in CROWD] + \
    ["yard", "figTree", "olivePress", "road", "ground", "beach", "lakeWater", "boat", "cushion", "hills"]
HIDDEN = ["roofHole", "rubble"]


def fix_faces(objs, idb, regname, crease):
    """(Ruth) faces nearly edge-on to their drawing's view (|n . d| < 0.22, n from P) take a clean texel deep inside
    their own region; no-raster faces take their named texel (CONSTS)"""
    tex = safe_texels(idb, regname, crease)
    count, missing = {}, set()
    for name, ob in objs.items():
        if ob.type != 'MESH':
            continue
        g = drawing_of(name)
        me = ob.data; lay = me.uv_layers["UVMap"].data
        P = P_OF[name]; nr = NR_OF[name]; regs = REG_OF[name]
        dv = np.array(DRAWINGS[g]["D"], float) / np.linalg.norm(DRAWINGS[g]["D"]) if g else None
        n = 0
        for p in me.polygons:
            reg = regs[p.index]
            if nr[p.index] or g is None:
                key = CONSTS.get(name, {}).get(reg)
                if key is None:
                    missing.add((name, reg)); continue
            else:
                Q = P[list(p.vertices)]
                nn = np.zeros(3)
                for i in range(len(Q)):
                    a, b = Q[i], Q[(i + 1) % len(Q)]
                    nn += np.cross(a, b)
                L = np.linalg.norm(nn)
                if L < 1e-12 or abs(nn @ dv) / L >= 0.22:
                    continue
                key = (g, reg)
            uv = tex.get(key)
            if uv is None:
                missing.add((name, reg)); continue
            for li in p.loop_indices:
                lay[li].uv = uv
            n += 1
        if n:
            count[name] = n
    return count, sorted(missing), tex


def write_set_id(idb2, regname, crease2, tex):
    H, W = idb2.shape
    a = np.zeros((H, W, 4), np.float32)
    a[..., 0] = idb2 / 255.0; a[..., 1] = crease2.astype(np.float32); a[..., 3] = 1.0
    save_png(a, os.path.join(MODEL, "set_id_2x.png"))
    ids = []
    for rid, key in regname.items():
        if not key:
            continue
        g, reg = key
        nodes = list(DRAWINGS[g]["members"]) + list(TEMPLATES.get(g, ())) + \
            sorted(n for n, c in CONSTS.items() if (g, reg) in c.values())
        ids.append({"id": rid, "char": "set", "part": g, "region": reg, "hex": COLOURS.get(reg, "#FFFFFF"),
                    "nodes": nodes})
    const = []
    for name, m in CONSTS.items():
        for reg, key in m.items():
            if key in tex:
                const.append({"node": "%s/%s" % (name, reg), "uv": [round(c, 5) for c in tex[key]], "region": key[1]})
    json.dump({"note": "set drawings at 2x of the page (1240 x 1754 @150 dpi): R = id, G = detail line mask; "
                       "written by pipeline/mi_galilee.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)
    return const


# ============================================================================================ checks
LOW, OVER, TOP = 0.012, 0.17, 0.40
MARGINS = {}                   # label -> [nearest low-zone geometry, nearest overhead geometry]
SHAFT_R, SHAFT_TOP = 0.10, 0.45


def tri_points(ob, step=0.008):
    """local points densely covering every triangle of the mesh (vertices alone miss the middle of big faces)"""
    me = ob.data; me.calc_loop_triangles()
    co = np.zeros(len(me.vertices) * 3); me.vertices.foreach_get("co", co); co = co.reshape(-1, 3)
    tri = np.zeros(len(me.loop_triangles) * 3, np.int32); me.loop_triangles.foreach_get("vertices", tri)
    tri = tri.reshape(-1, 3)
    out = [co]
    if len(tri):
        A, Bq, C = co[tri[:, 0]], co[tri[:, 1]], co[tri[:, 2]]
        L = np.maximum(np.maximum(np.linalg.norm(Bq - A, axis=1), np.linalg.norm(C - Bq, axis=1)),
                       np.linalg.norm(A - C, axis=1))
        nseg = np.ceil(L / step).astype(int)
        for n in np.unique(nseg):
            if n < 2:
                continue
            sel = nseg == n
            uv = [(i / n, j / n) for i in range(n + 1) for j in range(n + 1 - i)]
            uv = np.array(uv)
            a, b = uv[:, 0][None, :, None], uv[:, 1][None, :, None]
            P = A[sel][:, None] + a * (Bq[sel] - A[sel])[:, None] + b * (C[sel] - A[sel])[:, None]
            out.append(P.reshape(-1, 3))
    return np.concatenate(out)


def to_design(M, P):
    W = (np.array(M) @ np.c_[P, np.ones(len(P))].T).T[:, :3]
    return np.stack([W[:, 0], W[:, 2], -W[:, 1]], -1)


def sampled_points(objs):
    """{object: array of design points}: rest pose, plus the boat and cushion at the two roll extremes of boatRock"""
    out = {}
    sc = bpy.context.scene
    local = {n: tri_points(ob) for n, ob in objs.items() if ob.type == 'MESH' and n not in TERRAIN}
    for n, P in local.items():
        out[n] = to_design(objs[n].matrix_world, P)
    for f in (37, 109):
        sc.frame_set(f); bpy.context.view_layer.update()
        for n in ("boat", "cushion"):
            out[n] = np.concatenate([out[n], to_design(objs[n].matrix_world, local[n])])
    sc.frame_set(1); bpy.context.view_layer.update()
    return out


def check_clearance(objs):
    """CONTRACT §6 rule, per mark and per straight walk, relative to the walker's floor y: nothing above y + 0.012
    within 0.05; overhead parts (y + 0.17 .. head top) need only 0.035 (a head's radius); above the head top ignored
    (default head top y + 0.40; inside the house the actor's own height, the ceiling being 0.385). Walking surfaces
    (yard, road, ground, beach, water, stair treads) do not count; the stern cushion may stand 0.05 above the deck at
    BOAT_STERN. Hidden props count only in the scenes that show them."""
    pts = sampled_points(objs)
    hard, info = {}, {}
    MARGINS.clear()

    def test(label, a, b, ya, yb, shown=(), off=(), ztop=None, allow=None, low=LOW):
        lo_min, ov_min = 9.0, 9.0
        for name, P in pts.items():
            if (name in HIDDEN and name not in shown) or name in off:
                continue
            X, Hh, Z = P[:, 0], P[:, 1], P[:, 2]
            ax, az = a; bx, bz = b
            dx, dz = bx - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
            t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
            d = np.hypot(X - ax - t * dx, Z - az - t * dz)
            y = ya + (yb - ya) * t
            rel = Hh - y
            top = TOP if ztop is None else ztop
            lz = (rel > low) & (rel < OVER); oz = (rel >= OVER) & (rel < top)
            if allow and name in allow:
                lz &= rel > allow[name]
            if lz.any():
                lo_min = min(lo_min, float(d[lz].min()))
            if oz.any():
                ov_min = min(ov_min, float(d[oz].min()))
            sel = (lz & (d < 0.05)) | (oz & (d < 0.035))
            if sel.any():
                hard.setdefault(label, []).append([name, round(float(d[sel].min()), 4), round(float(Hh[sel].max()), 4)])
        MARGINS[label] = [round(lo_min, 3), round(ov_min, 3)]
    cush = {"cushion": DECK + 0.05 - 0.0}
    for label, (x, z, y, ht) in MARKS.items():
        shown, off = (), ()
        if label == "LAND":                                       # S06-S08: hole open, rubble down, patch gone
            shown, off = ("roofHole", "rubble"), ("roofPatch",)
        elif label in INDOOR:
            shown = ("rubble",) if label.startswith("jesus") else ()
        rel_allow = {"cushion": 0.05} if label in ("BOAT_STERN", "deck 0.42,-0.34") else None
        test("mark " + label, (x, z), (x, z), y, y, shown, off, ztop=ht, allow=rel_allow)
    for label, a, b in CONTRACT_PATHS:
        (ax, az, ay, _), (bx, bz, by, _) = MARKS[a], MARKS[b]
        test("walk " + label, (ax, az), (bx, bz), ay, by)
    for label, a, b, w, clip in TL_MOVES:
        def inside(p):
            return p[1] < IN_Z[1] and WL[1] < p[0] < WR[0] and p[2] < 0.05
        indoor = inside(a) or inside(b)                          # under the ceiling: up to the actor's head only
        ht = HEIGHTS.get(w, 0.36) + 0.005 if indoor else None
        shown = ("roofHole", "rubble") if w in ("jesus", "man") and indoor else ()
        off = ("roofPatch",) if shown else ()
        allow = {"cushion": 0.05} if w == "jesus" and a[2] == DECK else None
        if w == "man" and a == (HOLE[0], HOLE[1], 0.0):          # S08: dancing out of the house
            shown, off = ("roofHole", "rubble"), ("roofPatch",)
        test("walk " + label, (a[0], a[1]), (b[0], b[1]), a[2], b[2], shown, off,
             ztop=(ht if ht else None), allow=allow, low=(0.035 if clip == "carried" else LOW))
    # the `lowered` shaft: radius 0.10 round LAND, y 0.012..0.45, empty except the roofHole rim (S06)
    hx, hz = HOLE
    sh = {}
    for name, P in pts.items():
        if name in ("roofHole", "roofPatch"):
            continue
        d = np.hypot(P[:, 0] - hx, P[:, 2] - hz)
        m = (d < SHAFT_R) & (P[:, 1] > LOW) & (P[:, 1] < SHAFT_TOP)
        if name in ("house", "houseIn"):
            m &= P[:, 1] < CEIL - 0.001                          # the roof slab round the hole is the rim
        if m.any():
            sh[name] = [round(float(d[m].min()), 4), round(float(P[:, 1][m].min()), 4), round(float(P[:, 1][m].max()), 4)]
    if sh:
        hard["lowered shaft (r 0.10 round LAND)"] = sh
    MARGINS["lowered shaft"] = round(min(float(np.hypot(P[:, 0] - hx, P[:, 2] - hz)[
        (P[:, 1] > LOW) & (P[:, 1] < (CEIL - 0.001 if n in ("house", "houseIn") else SHAFT_TOP))].min())
        for n, P in pts.items() if n not in ("roofHole", "roofPatch") and
        ((P[:, 1] > LOW) & (P[:, 1] < (CEIL - 0.001 if n in ("house", "houseIn") else SHAFT_TOP))).any()), 4)
    # nothing on the roof above 0.412 except the parapet
    rx = (WL[0], WR[1] - 0.020); rz = (WB[1], IN_Z[1])
    top = {}
    for name, P in pts.items():
        m = (P[:, 0] > rx[0] + 1e-4) & (P[:, 0] < rx[1] - 1e-4) & (P[:, 2] > rz[0] + 1e-4) & (P[:, 2] < rz[1] + 0.02) & \
            (P[:, 1] > ROOF + 0.012) & (P[:, 1] < 0.7)
        if m.any():
            top[name] = round(float(P[:, 1][m].max()), 4)
    if top:
        hard["roof above 0.412"] = top
    # headroom inside: ceiling underside / beams over the indoor actors
    info["headroom"] = {w: {"height": HEIGHTS[w], "ceiling": CEIL, "beamsBottom": round(BEAM_Y - BEAM_R, 3),
                            "free": round(CEIL - HEIGHTS[w], 3)} for w in ("jesus", "peter", "man")}
    # stair tread height under each stair mark vs the mark's y
    d_ = (STAIR_Z[0] - STAIR_Z[1]) / STAIR_N
    st = {}
    for label, (x, z, y, _) in MARKS.items():
        if STAIR_X[0] <= x <= STAIR_X[1] and STAIR_Z[1] <= z <= STAIR_Z[0]:
            i = int((STAIR_Z[0] - z) / d_)
            st[label] = {"markY": y, "tread": round(stair_top(min(i, STAIR_N - 1)), 3)}
        elif STAIR_X[0] <= x <= STAIR_X[1] and LANDING_Z[0] <= z <= LANDING_Z[1]:
            st[label] = {"markY": y, "tread": ROOF}
    info["stairTreads"] = st
    return hard, info


# ============================================================================================ build
STATE = {}


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    root = link(bpy.data.objects.new("galilee", None))
    objs = {}
    objs["house"], objs["houseIn"], objs["roofPatch"], objs["roofHole"], objs["rubble"] = build_house(root)
    objs["stair"] = build_stair(root)
    for c in CROWD:
        objs[c[0]] = build_person(root, *c)
    objs["yard"], objs["road"], objs["ground"], objs["beach"], roads = build_ground(root)
    objs["figTree"] = build_fig(objs["yard"])
    objs["olivePress"] = build_press(objs["yard"])
    rig, objs["lakeWater"] = build_lake(root)
    objs["boat"], objs["cushion"] = build_boat(root)
    objs["hills"] = build_hills(root)
    boat_rock(objs["boat"])
    bpy.context.view_layer.update()
    src = raster_sources(objs, {})
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("GALILEE_TRIS", total, json.dumps(tris))
    lay = check_layout()
    hard, info = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_MIN", json.dumps(MARGINS))
    print("HEADROOM", json.dumps(info["headroom"]))
    print("STAIR_TREADS", json.dumps(info["stairTreads"]))
    if total > MAX_TRIS:
        print("OVER_BUDGET", total)
    if MODE == "check":
        return
    RS[0] = 2
    idb2, regname, crease2 = raster_drawings(src)
    RS[0] = 1
    idb = idb2[1::2, 1::2]
    crease = crease2.reshape(PAGE[1], 2, PAGE[0], 2).any(axis=(1, 3))
    fixed, missing, tex = fix_faces(objs, idb, regname, crease)
    const = write_set_id(idb2, regname, crease2, tex)
    print("FIXED_FACES", json.dumps(fixed), "MISSING", missing)
    tex_img, demo = compose_sheets(idb, regname, crease)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    pm = page_mat()
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pm)
        ob.data.polygons.foreach_set("material_index", [0] * len(ob.data.polygons))
        for an in ("px", "ph", "pz", "nr"):
            if an in ob.data.attributes:
                ob.data.attributes.remove(ob.data.attributes[an])
    bpy.ops.object.select_all(action='DESELECT')
    for ob in [root] + list(root.children_recursive):
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    sc.frame_set(1)
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_yup=True, export_apply=False,
                              export_skins=True, export_animations=True, export_def_bones=False,
                              export_texcoords=True, export_normals=True, export_materials='EXPORT',
                              export_morph=False, export_anim_single_armature=False)
    hmax = {n: round(float(max(v[1] for v in world_verts(ob))), 4) for n, ob in objs.items()}
    write_design(objs, tris, total, hmax, const, hard, info)
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root, rig=rig)
    print("BUILD_OK", GLB, total, "MISSING" if missing else "")


TITLE = {"hanzi": "真正的神迹", "pinyin": "zhēn zhèng de shén jì", "english": "Real Miracles", "box": 88, "gap": 32,
         "cy": 110, "label": "DoodLive · 涂上颜色，再用手机扫一扫",
         "note": "box / gap / cy from tools/story/sheet_miracles.py title-search (worst NCC 0.359, daniel-A4)"}


def write_design(objs, tris, total, hmax, const, hard, info):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    d.setdefault("version", 1)
    d.setdefault("artHeightUnits", ART_H)
    d.setdefault("lines", {"outerPx": 4.5, "detailPx": 3.0,
                           "note": "same weights as David & Goliath, Esther, Ruth and Jonah; faces come from decals"})
    d.setdefault("sheet", {
        "page": [1240, 1754], "dpi": 150, "art": [120, 283, 1000, 1227],
        "markers": [[62, 225], [1178, 225], [1178, 1568], [62, 1568]], "markerSize": 64,
        "title": dict(TITLE),
        "footer": {"rect": [210, 1604, 820, 110], "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上",
                                                            "马可福音 · Mark 2; 4"],
                   "note": "centred on the page (x 620); line 1 at rect y + 40, line 2 at y + 76"},
        "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge; "
                    "title cy keeps the pinyin >= 6 mm from the top"})
    if d["sheet"]["title"].get("note", "").startswith("placeholder"):
        d["sheet"]["title"] = dict(TITLE)
    ch = d.get("characters", {})
    ch.pop("man_mat", None)
    for c, v in CHAR_PROPOSAL.items():
        if c == "man_mat":                                       # the mat's printed place, pinned where the layout
            continue                                             # leaves room for it (mi_characters.py reads it)
        e = ch.get(c, {})
        e.update({"height": v["height"], "sheetX": v["sheetX"], "sheetY": v["sheetY"]})
        if c == "man":
            e["note"] = "drawn standing; the mat is a separate shape below-left of him (matSheet = its centre)"
            e["matSheet"] = list(MAT_SHEET)
        ch[c] = e
    d["characters"] = ch
    pieces = []
    for name in ORDER:
        g = drawing_of(name)
        sp = DRAWINGS[g] if g else None
        fu = ({k: (round(sp[k], 5) if isinstance(sp[k], float) else sp[k]) for k in ("A", "B", "D", "scale", "sheetX",
                                                                                   "sheetY")} if sp else None)
        pieces.append({"id": name, "drawing": g, "frontUV": fu, "instanced": False,
                       "namedTexels": {r: list(k) for r, k in CONSTS.get(name, {}).items()} or None,
                       "regions": sorted(set(REG_OF[name])), "heightMax": hmax[name], "tris": tris[name]})
    drawings = {g: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dsp.items()} for g, dsp in DRAWINGS.items()}
    d["set"] = {
        "generatedBy": "pipeline/mi_galilee.py", "doc": "docs/miracles/SET.md", "contract": "docs/miracles/CONTRACT.md §6",
        "root": "galilee",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {n: [round(c, 4) for c in D(objs[n].matrix_world.translation)] for n in ORDER} |
                 {"lake": [LAKE_C[0], 0.0, LAKE_C[1]]},
        "footprints": {"floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]],
                       "room": {"x": list(IN_X), "z": list(IN_Z)}, "wallsOuter": {"x": [WL[0], WR[1]], "zBack": WB[0]},
                       "roof": {"x": [WL[0], WR[1]], "z": [WB[1], IN_Z[1]], "top": ROOF, "underside": CEIL,
                                "parapet": "back (back wall to %.2f) and right side; none left (stair) or front" % PARA},
                       "door": {"x": WR[0], "z": list(DOOR_Z), "height": DOOR_H},
                       "window": {"x": list(WIN_X), "y": list(WIN_Y)}, "sill": {"z": list(SILL_Z), "height": SILL_H},
                       "hole": {"centre": list(HOLE), "patch": 2 * PATCH, "hole": 2 * HOLE_R},
                       "stair": {"x": list(STAIR_X), "z": list(STAIR_Z), "steps": STAIR_N,
                                 "landing": {"z": list(LANDING_Z), "top": ROOF}},
                       "beams": {"z": list(BEAMS_Z), "bottom": round(BEAM_Y - BEAM_R, 4)},
                       "lake": {"x": [0.14, FLOOR[1]], "z": [FLOOR[2], BEACH_Z[0]], "surface": LAKE_Y,
                                "shore": "x 0.14, bending out to 0.225 behind z -0.47 (the fig tree's corner)"},
                       "beach": {"z": list(BEACH_Z)},
                       "boat": {"centre": list(BOAT_C), "x": list(BOAT_X), "halfBeam": BOAT_HB, "deck": DECK,
                                "mast": list(MAST), "mastTop": MAST_TOP, "cushion": list(CUSHION)},
                       "crowd": {c[0]: [c[1], c[2], c[5]] for c in CROWD},
                       "figTree": list(FIG), "olivePress": list(PRESS)},
        "animations": {"lakeWave": {"node": "lake", "meshes": ["lakeWater"], "length": 4.0, "fps": 24, "loop": True},
                       "boatRock": {"node": "boat", "length": 6.0, "fps": 24, "loop": True, "rollDeg": 3.0,
                                    "pitchDeg": 0.5, "pivot": [BOAT_C[0], DECK, BOAT_C[1]]}},
        "hiddenAtStart": list(HIDDEN),
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227",
                   "edgeOn": "faces with |n . D| < 0.22 (n in drawing space) take one clean texel of their region",
                   "namedTexels": "no-raster bits (crowd, mast, oars, jars, ceiling, beams, twigs, pebbles, reeds, press) "
                                  "take one texel of a named (drawing, region); constUV in model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard,
                      "nearest": {"note": "[low zone (y+0.012..0.17), overhead (y+0.17..head top)] nearest plan distance; "
                                          "needs >= 0.05 / >= 0.035", **MARGINS},
                      "headroom": info["headroom"], "stairTreads": info["stairTreads"]},
        "sheetLayout": {"characters": CHAR_PROPOSAL, "charactersFrom": "model/regions_characters.json" if CHARS_FROM_FILE
                        else "proposal (regions_characters.json not there yet)"},
        "demoColours": COLOURS, "tris": total, "budget": MAX_TRIS,
    }
    json.dump(d, open(DESIGN_JSON, "w"), indent=1, ensure_ascii=False)


def compose_sheets(idb, regname, crease):
    """(Ruth) quick-look line art + demo colouring of the set drawings, and the preview texture (colours, no lines)"""
    H, W = idb.shape
    mask = idb > 0
    edge = np.zeros_like(mask)
    for dy, dx in ((0, 1), (1, 0)):
        s = shift(idb, dy, dx)
        edge |= (idb != s) & mask & (s > 0)
    inner = dilate(edge, 1)
    outer = dilate(mask, 4) & ~mask
    lut = np.ones((max(regname) + 1, 3), np.float32)
    for rid, key in regname.items():
        if key:
            lut[rid] = hex_rgb(COLOURS.get(key[1], "#FFFFFF"))
    fill = lut[idb]
    rng = np.random.default_rng(7)
    n = rng.random((H, W)).astype(np.float32)
    st = sum(shift(n, k, k) for k in range(-5, 6)) / 11.0
    grain = fill * (1.0 - 0.10 * (st - 0.5)[..., None])
    demo = np.where(mask[..., None], grain, np.ones((H, W, 3), np.float32))
    line = np.ones((H, W, 3), np.float32)
    for arr in (line, demo):
        arr[crease & mask & ~inner] = (0.55, 0.55, 0.55)
        arr[inner | outer] = (0.08, 0.08, 0.08)
    for ch, c in CHAR_PROPOSAL.items():
        x0, y0, x1, y1 = c["box"]
        X0, Y1 = to_px(x0 + 0.5, y0 / ART_H); X1, Y0 = to_px(x1 + 0.5, y1 / ART_H)
        X0, X1, Y0, Y1 = int(X0), int(X1), int(Y0), int(Y1)
        for arr in (line, demo):
            for xx in range(X0, X1, 12):
                arr[Y0:Y0 + 3, xx:xx + 6] = 0.6; arr[Y1 - 3:Y1, xx:xx + 6] = 0.6
            for yy in range(Y0, Y1, 12):
                arr[yy:yy + 6, X0:X0 + 3] = 0.6; arr[yy:yy + 6, X1 - 3:X1] = 0.6
    ax0, ay0 = ART[0], ART[1]; ax1, ay1 = ART[0] + ART[2], ART[1] + ART[3]
    for arr in (line, demo):
        arr[ay0:ay0 + 2, ax0:ax1] = 0.75; arr[ay1 - 2:ay1, ax0:ax1] = 0.75
        arr[ay0:ay1, ax0:ax0 + 2] = 0.75; arr[ay0:ay1, ax1 - 2:ax1] = 0.75
    save_png(line, os.path.join(WORK, "galilee_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "galilee_drawings_demo.png"))
    tex = np.where(mask[..., None], grain, 0.0); got = mask.copy()
    for _ in range(10):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = shift(got, dy, dx); sv = shift(tex, dy, dx)
            take = sm & ~got
            tex[take] = sv[take]; got |= take
    tex[~got] = 1.0
    return tex, demo


# ============================================================================================ preview
def mannequins(layout):
    """preview stand-ins only (not shipped): simple figures in the demo colours at the actors' marks.
    layout: who -> (x, z, y, yaw, pose); pose '' standing, 'kneel', 'lie' (on the mat), 'sleep' (on the side)"""
    mats = {k: flat_mat("pvm_" + k, v, 0.6) for k, v in {
        "skin": "#E9B48F", "jesusT": "#F2E8D2", "mantle": "#9A5B34", "hairJ": "#4A3020", "peterT": "#B4502F",
        "vest": "#D9C29A", "hairP": "#231A16", "cloth": "#6E8AA6", "manT": "#A9CF8E", "hairM": "#9A6B42",
        "mat": "#F1E3C4", "f1": "#E8843A", "f2": "#2E9A92", "f3": "#EFC53F", "f4": "#5A5FB8"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    spec = {"jesus": (0.36, "jesusT", "mantle", "hairJ"), "peter": (0.381, "peterT", "vest", "hairP"),
            "man": (0.34, "manT", "manT", "hairM"), "friend1": (0.35, "f1", "f1", "hairP"),
            "friend2": (0.37, "f2", "f2", "hairP"), "friend3": (0.33, "f3", "f3", "hairP"),
            "friend4": (0.36, "f4", "f4", "hairP")}
    for who, (x, z, y, yaw, pose) in layout.items():
        H, body, top, hair = spec[who.split("#")[0]]
        mb = MB()
        if pose in ("lie", "sleep"):
            if pose == "lie":
                box(mb, -0.15, 0.15, 0.0, 0.025, -0.06, 0.06, "mat")
            tube(mb, [(-0.13, 0.05, 0.0), (0.10, 0.05, 0.0)], 0.040, body, seg=12)
            sphere(mb, (0.15, 0.065, 0.0), 0.034, "skin", seg=12, rings=8)
            sphere(mb, (0.165, 0.075, 0.0), 0.030, hair, seg=10, rings=6)
        elif pose == "kneel":
            lathe(mb, [(0.0, 0.0), (0.05, 0.0), (0.048, 0.03), (0.040, 0.10), (0.032, 0.16), (0.0, 0.17)], body,
                  C=(0, 0, 0), seg=16)
            sphere(mb, (0.0, 0.195, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, 0.205, -0.008), 0.026, hair, seg=10, rings=7)
        else:
            lathe(mb, [(0.0, 0.0), (0.050, 0.0), (0.048, 0.02), (0.042, 0.36 * H)], body, C=(0, 0, 0), seg=18)
            lathe(mb, [(0.042, 0.36 * H), (0.046, 0.56 * H), (0.038, 0.75 * H), (0.0, 0.78 * H)], top, C=(0, 0, 0),
                  seg=18)
            sphere(mb, (0.0, H - 0.04, 0.0), 0.034, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, H - 0.05), (0.036, H - 0.04), (0.035, H - 0.010), (0.0, H)], hair, C=(0, 0, -0.006),
                  seg=16)
        ob = make_obj("pv_" + who, mb, None, origin=(0, 0, 0), smooth_angle=60)
        ob["pv"] = 1
        ob.location = B(x, y, z)
        ob.rotation_euler = (0, 0, math.radians(yaw))


def mode_preview():
    if not STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "galilee_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "galilee_preview_sheet.png")); sheet.pack()
    W, H = PAGE; px = ART[2]
    x0, x1 = -ART[0] / px - 0.5, (W - ART[0]) / px - 0.5
    ztop = -(ART[1] + ART[3]) / px; zbot = (H - ART[1] - ART[3]) / px
    me = bpy.data.meshes.new("paper")
    me.from_pydata([B(x0, -0.003, zbot), B(x1, -0.003, zbot), B(x1, -0.003, ztop), B(x0, -0.003, ztop)], [],
                   [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for li, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uvl.data[li].uv = uv
    link(bpy.data.objects.new("pv_paper", me))
    pm = bpy.data.materials.new("pv_paper_m")
    t = pm.node_tree.nodes.new("ShaderNodeTexImage"); t.image = sheet
    pm.node_tree.links.new(t.outputs[0], pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    me.materials.append(pm)
    tb = bpy.data.meshes.new("tabletop")
    tb.from_pydata([B(-4, -0.006, 4), B(4, -0.006, 4), B(4, -0.006, -4), B(-4, -0.006, -4)], [], [(0, 1, 2, 3)])
    tb.materials.append(flat_mat("pv_wood", "#6E4A33", 0.6))
    link(bpy.data.objects.new("pv_table", tb))
    sun = link(bpy.data.objects.new("pv_sun", bpy.data.lights.new("pv_sun", 'SUN')))
    sun.data.angle = math.radians(4)
    fill = link(bpy.data.objects.new("pv_fill", bpy.data.lights.new("pv_fill", 'AREA')))
    fill.data.size = 1.5
    fill.location = B(0.0, 0.8, 1.2); fill.rotation_euler = (B(0, 0.1, -0.2) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    sc.world = bpy.data.worlds.new("w")
    bg = sc.world.node_tree.nodes["Background"]
    sun.data.energy = 3.1; sun.data.color = (1.0, 0.95, 0.86)
    sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-30))
    fill.data.energy = 6.0; fill.data.color = (1.0, 0.88, 0.72)
    bg.inputs[0].default_value = (0.80, 0.84, 0.90, 1); bg.inputs[1].default_value = 0.75
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    cam = link(bpy.data.objects.new("pv_cam", bpy.data.cameras.new("pv_cam"))); sc.camera = cam
    cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.005; cam.data.clip_end = 30
    sc.frame_set(1)

    def shoot(name, eye, tgt, vfov, res, out=MODEL):
        e = B(*eye); g = B(*tgt)
        cam.location = e; cam.rotation_euler = (g - e).to_track_quat('-Z', 'Y').to_euler()
        cam.data.angle_y = math.radians(vfov)
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)

    def show(names, on):
        for n in names:
            for o in [objs[n]] + list(objs[n].children_recursive):
                o.hide_render = not on

    def cast(layout):
        for o in [o for o in bpy.data.objects if o.get("pv")]:
            bpy.data.objects.remove(o, do_unlink=True)
        if layout:
            mannequins(layout)
    R = ROOF
    act1 = {"jesus": (-0.36, -0.46, 0.0, 0, ""), "peter": (-0.12, -0.46, 0.0, -60, "")}
    roof = {"friend1": (-0.36, -0.38, R, 90, "kneel"), "friend2": (-0.12, -0.38, R, -90, "kneel"),
            "friend3": (-0.32, -0.50, R, 30, "kneel"), "friend4": (-0.16, -0.50, R, -30, "kneel")}
    show(HIDDEN, False)
    cast({})
    phone = ((-0.02, 0.95, 1.15), (-0.02, 0.05, -0.50), 55, (720, 1280))
    shoot("galilee_preview_phone_set", *phone)
    cast({**act1, **roof, "man": (-0.24, -0.30, R, 0, "lie")})
    shoot("galilee_preview_phone", *phone)
    cast({})
    shoot("galilee_preview_front", (0.0, 0.30, 2.3), (0.0, 0.16, -0.25), 22, (1600, 1000))
    # S01b / S05 / S06 / S07: low cameras into the house (0.15-0.22 high, 0.45-0.62 from the actor)
    cast({**act1, **roof})
    shoot("galilee_preview_room_s01b", (-0.27, 0.16, 0.08), (-0.36, 0.18, -0.46), 46, (1280, 800))
    shoot("galilee_preview_room_s05", (-0.24, 0.15, -0.03), (-0.12, 0.17, -0.46), 46, (1280, 800))
    show(["roofHole", "rubble"], True); show(["roofPatch"], False)
    cast({**act1, **roof, "man": (-0.24, -0.38, 0.0, 0, "lie")})
    shoot("galilee_preview_room_s06", (-0.17, 0.22, 0.13), (-0.36, 0.17, -0.46), 46, (1280, 800))
    cast({"jesus": (-0.34, -0.40, 0.0, 120, "kneel"), "peter": (-0.12, -0.46, 0.0, -60, ""), **roof,
          "man": (-0.24, -0.38, 0.0, 0, "lie")})
    shoot("galilee_preview_room_s07", (-0.30, 0.18, 0.15), (-0.24, 0.10, -0.38), 46, (1280, 800))
    cast({**roof})
    shoot("galilee_preview_roof_hole", (-0.10, 0.75, 0.05), (-0.26, 0.38, -0.40), 40, (1200, 900))
    show(["roofHole", "rubble"], False); show(["roofPatch"], True)
    cast({**roof, "man": (-0.24, -0.30, R, 0, "lie")})
    shoot("galilee_preview_roof", (-0.10, 0.75, 0.05), (-0.26, 0.38, -0.40), 40, (1200, 900))
    cast({"friend1": (-0.53, -0.40, R, 180, ""), "friend3": (-0.53, -0.08, 0.0, 180, ""),
          "friend4": (-0.53, -0.24, 0.19, 180, "")})
    shoot("galilee_preview_stair", (-0.05, 0.40, 0.30), (-0.50, 0.20, -0.28), 46, (1200, 900))
    cast({"friend1": (0.02, -0.10, 0.0, 200, ""), "friend3": (0.02, -0.12, 0.0, 200, ""),
          "friend4": (0.08, 0.06, 0.0, 200, "")})
    shoot("galilee_preview_yard", (0.30, 0.30, 0.35), (0.04, 0.12, -0.30), 46, (1200, 900))
    cast({"jesus": (0.48, -0.34, DECK, 90, "sleep"), "peter": (0.28, -0.32, DECK, 0, "")})
    shoot("galilee_preview_boat", (0.22, 0.30, 0.25), (0.37, 0.12, -0.34), 46, (1200, 900))
    cast({"jesus": (0.48, -0.34, DECK, 90, "sleep"), "peter": (0.38, -0.32, DECK, 90, "")})
    shoot("galilee_preview_boat_s11", (0.31, 0.16, 0.06), (0.47, 0.11, -0.34), 46, (1200, 800))
    cast({"jesus": (0.18, 0.04, 0.0, 0, ""), "peter": (0.32, 0.06, 0.0, 0, ""), "man": (-0.14, 0.10, 0.0, 0, "")})
    shoot("galilee_preview_beach", (0.10, 0.48, 0.95), (0.10, 0.10, -0.20), 40, (1280, 900))
    cast({})
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "galilee_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["galilee", "house", "roofPatch", "roofHole", "rubble", "stair"] + ["crowd%d" % i for i in range(1, 9)] + \
    ["yard", "road", "lake", "lakeWater", "beach", "boat", "cushion", "hills", "figTree", "olivePress"]


def mode_verify():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=GLB)
    names = {o.name for o in bpy.data.objects}
    missing = [n for n in NEED if n not in names]
    tris = 0; uv_bad = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles(); tris += len(o.data.loop_triangles)
            if o.data.uv_layers:
                uv = np.zeros(len(o.data.loops) * 2); o.data.uv_layers[0].data.foreach_get("uv", uv)
                nb = int(((uv < -1e-5) | (uv > 1 + 1e-5)).sum()); uv_bad += nb
                if nb:
                    print("UV_OUTSIDE", o.name, nb)
            else:
                uv_bad += 1
    acts = [a.name for a in bpy.data.actions]
    parents = {n: (bpy.data.objects[n].parent.name if bpy.data.objects[n].parent else None) for n in NEED[1:]
               if n in names}
    sc = bpy.context.scene
    dg = bpy.context.evaluated_depsgraph_get()
    res = {}
    for node, an in (("lake", "lakeWave"), ("boat", "boatRock")):  # the importer leaves one clip per object on NLA
        o = bpy.data.objects.get(node)
        if o is not None and an in bpy.data.actions and (not o.animation_data or not o.animation_data.action):
            o.animation_data_create()
            act = bpy.data.actions[an]
            for t in list(o.animation_data.nla_tracks):
                o.animation_data.nla_tracks.remove(t)
            o.animation_data.action = act
            try:
                o.animation_data.action_slot = act.slots[0]
            except (AttributeError, IndexError):
                pass
    ob = bpy.data.objects.get("lakeWater")
    if ob is not None:
        pos = []
        for f in (1, 25, 49, 73, 97):
            sc.frame_set(f); dg.update()
            me = ob.evaluated_get(dg).to_mesh()
            pos.append(np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices]))
            ob.evaluated_get(dg).to_mesh_clear()
        res["lakeWaveMax"] = round(float(max(np.abs(p - pos[0]).max() for p in pos[1:4])), 4)
        res["lakeLoopError"] = float(np.abs(pos[4] - pos[0]).max())
    bt = bpy.data.objects.get("boat")
    if bt is not None and bt.animation_data and not bt.animation_data.action and "boatRock" in bpy.data.actions:
        act = bpy.data.actions["boatRock"]                       # the importer puts a second object's clip on NLA
        for t in list(bt.animation_data.nla_tracks):
            bt.animation_data.nla_tracks.remove(t)
        bt.animation_data.action = act
        try:
            bt.animation_data.action_slot = act.slots[0]
        except (AttributeError, IndexError):
            pass
    if bt is not None:
        rots = []
        for f in (1, 37, 73, 109, 145):
            sc.frame_set(f); dg.update()
            rots.append(bt.matrix_world.to_quaternion())
        res["boatRollDeg"] = round(max(math.degrees(r.rotation_difference(rots[0]).angle) for r in rots), 2)
        res["boatLoopErrorDeg"] = round(math.degrees(rots[4].rotation_difference(rots[0]).angle), 4)
    sc.frame_set(1)
    ok = (not missing and tris <= MAX_TRIS and uv_bad == 0 and any("lakeWave" in a for a in acts)
          and any("boatRock" in a for a in acts) and 0.0006 < res.get("lakeWaveMax", 0) < 0.006
          and res.get("lakeLoopError", 1) < 1e-4 and 2.5 < res.get("boatRollDeg", 0) < 3.6
          and res.get("boatLoopErrorDeg", 1) < 0.01)
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "actions": acts, "parents": parents, **res}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
