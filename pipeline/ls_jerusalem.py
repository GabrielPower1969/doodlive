"""Blender (headless): The King Who Serves story pack, Jerusalem -> assets/lastsupper/model/jerusalem.glb

One tabletop page, three places (docs/lastsupper/CONTRACT.md §6, DESIGN.md §2).
Front: the pale `road` from the front-right edge along the front, past the bend by the court gate, on to the front of
the house, with a branch up to the gate; `palmsRoad` (hidden: palm branches and three coats laid flat on the road) and
`stones` (the little roadside heap at the bend) are its children; the rest of the floor is `ground`.
Right back: the temple court `temple` (cream paving) with children `courtWall` (low front wall, gate gap), `templeFront`
(white temple front relief, gold pediment, bronze door; four columns and the architrave in front of it), `awnings` (two
striped awnings on poles), the stalls `table1` (children `cages`, hidden `cagesOpen`) and `table2` (coin chest, coin
stacks, a little scale), and the hidden `table2Tipped` and `coinsFloor`.
Left back: the two-storey `house`: the ground storey closed (door, shuttered window); the upstairs room (floor y 0.10)
a doll's house: front cut away to a 1 cm sill, side walls sloping down toward the front, a flat roof edge at the back and
the sides only. Children: `houseIn` (everything seen through the open front: inside walls, floor mats, the night-sky
window, the lamp shelf), `bench` (with cushions), `lowTable` (white cloth, five seat cushions, herbs, fruit; children
`breadLoaf`, `cupTable`, `lamp2`), `basinStand` (child `basinJug`: the basin on the stand, the jug on the floor beside
it), `lamp1` (on the back-wall shelf). `stair`: the outside stair up the house's right wall (decor).
The lane between house and court: `palmTree` (behind everything) and `oliveTree`. Above the house's back wall: `hills`.
The crowd: armature `crowd` (looping action `crowdSway`, 3 s) with skinned fixed-colour townsfolk `crowd1`...`crowd8`.
Contract: docs/lastsupper/CONTRACT.md §6. Nodes, measured clearances, deviations: docs/lastsupper/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `ls_page` = the scanned art rectangle): as Jonah / Real Miracles (pipeline/mi_galilee.py).
Each piece belongs to one *drawing* on the colouring sheet, a linear view a = A.P, b = B.P (depth D.P), and
  u = a / scale + sheetX + 0.5,   v = (b / scale + sheetY) / 1.227
Faces nearly edge-on to their drawing take one clean texel of their own region; scattered and thin bits (crowd, columns,
poles, legs, bench, stand, lamps, stones, hidden props) take the texel of a named (drawing, region). The room seen
through the open front is its own drawing (`room`), so the inside never samples the outside (LESSONS L51).

Modes (run from the repo root, one Blender at a time):
  nice -n 10 blender -b --factory-startup --python pipeline/ls_jerusalem.py -- build     jerusalem.glb + .blend + drawings
  nice -n 10 blender -b --factory-startup --python pipeline/ls_jerusalem.py -- verify    re-import jerusalem.glb, check it
  nice -n 10 blender -b --factory-startup --python pipeline/ls_jerusalem.py -- all       build, preview, verify
  nice -n 10 blender -b --factory-startup --python pipeline/ls_jerusalem.py -- check     build in memory, print checks
Work files go to $LS_WORK (default /tmp/lastsupper_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector, Quaternion, Euler
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/lastsupper/model")
GLB = os.path.join(MODEL, "jerusalem.glb")
BLEND = os.path.join(MODEL, "jerusalem.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/lastsupper/design.json")
TIMELINE = os.path.join(ROOT, "assets/lastsupper/timeline.json")
ENV = "LS_"
WORK = os.environ.get(ENV + "WORK", "/tmp/lastsupper_set")
PAGE_MATERIAL = "ls_page"
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
UPPER = 0.10                                   # upstairs room floor (story.py UPPER)
RIDE_Y = 0.12
# house
HOUSE_X, HOUSE_ZF = (-0.60, -0.06), -0.22
WL, WR = (-0.60, -0.58), (-0.08, -0.06)        # side walls (0.02 thick)
WB = (-0.584, -0.578)                          # back wall: the hills relief sits behind it at z -0.5875..-0.5845
IN_X, IN_Z = (WL[1], WR[0]), (WB[1], HOUSE_ZF)  # room interior x -0.58..-0.08, z -0.578..-0.22
BACK_TOP = 0.46
SLOPE_Z, SLOPE_LOW = (-0.42, HOUSE_ZF), UPPER + 0.04   # side walls: full height behind z -0.42, down to 0.14 at the front
SILL_Z, SILL_H = (-0.24, HOUSE_ZF), UPPER + 0.010      # the cut-away front (contract: <= UPPER + 0.04)
RIM_T, RIM_BACK_Z = 0.015, -0.55               # flat roof edge: back strip z -0.584..-0.55, side strips to z -0.42
DOOR = (-0.44, -0.35, 0.092)                   # ground storey door x0 x1 top
SHUTTER = (-0.22, -0.13, 0.035, 0.082)
UWIN = (-0.31, -0.21, 0.24, 0.36)              # upstairs back window (night sky)
SHELF = (-0.485, -0.435, 0.298)                # lamp1 shelf x0 x1 top (contract lamp1 (-0.46, -0.575), y UPPER + 0.20)
STAIR_X, STAIR_Z0, STAIR_D, STAIR_N = (-0.058, -0.022), -0.25, 0.039, 4
LANDING_Z = (-0.505, STAIR_Z0 - STAIR_N * STAIR_D)
BENCH_X, BENCH_Z, BENCH_TOP = (-0.58, -0.532), (-0.54, -0.24), UPPER + 0.04   # x0 narrowed from -0.50: SET.md
TABLE_X, TABLE_Z, TABLE_TOP = (-0.355, -0.202), (-0.50, -0.42), UPPER + 0.05  # x shortened from -0.36..-0.18: SET.md
BREAD, CUP = (-0.27, -0.46), (-0.24, -0.45)
LAMP2 = (-0.222, -0.484)                       # contract (-0.20, -0.47): moved inside the shortened table
HERBS, FRUIT = (-0.315, -0.446), (-0.333, -0.480)
STAND_C, STAND_TOP, STAND_R = (-0.115, -0.535), UPPER + 0.08, 0.028   # contract (-0.12, -0.53)
JUG = (-0.097, -0.561)                         # the jug stands on the floor beside the stand
LAMP1 = (-0.46, -0.570)
SUP = {"james": (-0.34, -0.54), "jesus": (-0.27, -0.54), "john": (-0.20, -0.54), "andrew": (-0.41, -0.46),
       "peter": (-0.41, -0.35)}
CUSHION_H = 0.0115                             # supper cushions (contract allows <= 0.02; under 0.012 they never count)
# court
COURT_X, COURT_Z1 = (0.02, 0.60), -0.12
CWALL_Z, CWALL_H, GATE_X = (-0.1285, -0.1115), 0.035, (0.08, 0.30)  # gate gap widened from 0.08..0.22: SET.md
COLS_X, COLS_Z, COL_R, COL_TOP = (0.07, 0.19, 0.48, 0.575), -0.52, 0.020, 0.40
ARCH = (0.050, 0.598, 0.400, 0.425, -0.535, -0.505)
TEMPLE_Z, TEMPLE_X, TEMPLE_WALL = (-0.5875, -0.577), (0.03, 0.60), 0.36
PEDIMENT = (0.19, 0.49, 0.372, 0.45)
TDOOR = (0.29, 0.39, 0.25)
AWNINGS = [(0.280, 0.455, 3), (0.095, 0.165, 2)]   # x0 x1 stripes; poles at x0 / x1, z -0.50
AWN_Z, AWN_Y = (-0.505, -0.445), (0.43, 0.39)
T1 = (0.350, 0.414, -0.447, -0.398)          # contract 0.34..0.46 x -0.45..-0.39: SET.md
T2 = (0.423, 0.494, -0.307, -0.253)          # contract 0.42..0.50: SET.md
T_TOP, T_APRON = 0.06, 0.022
# road and the lane
STONES = (0.05, 0.177)                         # heap centre (contract (0.05, 0.17)): SET.md
PALM = (-0.02, -0.56)
OLIVE, OLIVE_CROWN = (0.00, -0.30), (-0.015, -0.30)
HILLS_X, HILLS_Z = (HOUSE_X[0], HOUSE_X[1]), (-0.5875, -0.5845)


# ============================================================================================ marks and paths
G, U = 0.0, UPPER
HEAD = {"jesus": 0.365, "peter": 0.385, "john": 0.335, "james": 0.365, "andrew": 0.375, "seller1": 0.335,
        "seller2": 0.355, "donkey": 0.50}
# label: (x, z, floor y, kind, actor)   kinds: stand, kneel, seat (bench / cushion: radius 0.035), donkey (0.30 x 0.12
# box along -X), donkeyAny (both headings), stones8 (only `stones` within 0.08)
MARKS = {
    "DONKEY_START": (0.46, 0.13, G, "donkey", "donkey"), "DONKEY_MID": (0.26, 0.11, G, "donkey", "donkey"),
    "donkey 0.18,0.09": (0.18, 0.09, G, "donkey", "donkey"), "BEND": (0.10, 0.07, G, "donkey", "donkey"),
    "DONKEY_TIE": (-0.04, 0.07, G, "donkeyAny", "donkey"),
    "peter 0.56,0.06": (0.56, 0.06, G, "stand", "peter"), "peter 0.38,0.05": (0.38, 0.05, G, "stand", "peter"),
    "peter 0.30,0.04": (0.30, 0.04, G, "stand", "peter"), "PETER_STONES": (0.13, 0.18, G, "stones8", "peter"),
    "john 0.56,0.17": (0.56, 0.17, G, "stand", "john"), "john 0.38,0.17": (0.38, 0.17, G, "stand", "john"),
    "john 0.30,0.17": (0.30, 0.17, G, "stand", "john"), "john 0.24,0.17": (0.24, 0.17, G, "stand", "john"),
    "james 0.63,0.05": (0.63, 0.05, G, "stand", "james"), "james 0.46,0.04": (0.46, 0.04, G, "stand", "james"),
    "james 0.40,0.04": (0.40, 0.04, G, "stand", "james"), "james 0.30,0.03": (0.30, 0.03, G, "stand", "james"),
    "andrew 0.63,0.16": (0.63, 0.16, G, "stand", "andrew"), "andrew 0.46,0.17": (0.46, 0.17, G, "stand", "andrew"),
    "andrew 0.40,0.17": (0.40, 0.17, G, "stand", "andrew"), "andrew 0.34,0.15": (0.34, 0.15, G, "stand", "andrew"),
    "GATE": (0.14, -0.06, G, "stand", "jesus"), "J_T2": (0.36, -0.26, G, "stand", "jesus"),
    "J_T1": (0.28, -0.42, G, "stand", "jesus"), "P_COURT": (0.08, -0.22, G, "stand", "peter"),
    "JN_COURT": (0.14, -0.30, G, "stand", "john"), "JA_COURT": (0.05, -0.34, G, "stand", "james"),
    "SELLER1": (0.40, -0.50, G, "stand", "seller1"), "SELLER2": (0.46, -0.37, G, "stand", "seller2"),
    "SELLER2_SIDE": (0.56, -0.30, G, "stand", "seller2"), "COINS": (0.53, -0.18, G, "stand", "seller2"),
    "ROOM_J": (-0.15, -0.50, U, "stand", "jesus"), "STAND": (-0.15, -0.46, U, "stand", "jesus"),
    "ROUND": (-0.40, -0.36, U, "stand", "jesus"), "WASH andrew": (-0.43, -0.50, U, "kneel", "jesus"),
    "wash -0.43,-0.30": (-0.43, -0.30, U, "stand", "jesus"), "WASH peter": (-0.43, -0.27, U, "kneel", "jesus"),
    "ARGUE andrew": (-0.48, -0.32, U, "stand", "andrew"), "ARGUE james": (-0.39, -0.35, U, "stand", "james"),
    "ARGUE john": (-0.30, -0.33, U, "stand", "john"), "ARGUE peter": (-0.21, -0.36, U, "stand", "peter"),
    "BENCH andrew": (-0.54, -0.50, U, "seat", "andrew"), "BENCH james": (-0.54, -0.42, U, "seat", "james"),
    "BENCH john": (-0.54, -0.34, U, "seat", "john"), "BENCH peter": (-0.54, -0.27, U, "seat", "peter"),
    **{"SUP " + k: (v[0], v[1], U, "seat", k) for k, v in SUP.items()},
}
PATHS = [   # CONTRACT §6 straight walks between consecutive marks of one actor (label, [mark labels])
    ("donkey + Jesus", ["DONKEY_START", "DONKEY_MID", "donkey 0.18,0.09", "BEND"]),
    ("peter road", ["peter 0.56,0.06", "peter 0.38,0.05", "peter 0.30,0.04", "PETER_STONES"]),
    ("john road", ["john 0.56,0.17", "john 0.38,0.17", "john 0.30,0.17", "john 0.24,0.17"]),
    ("james road", ["james 0.63,0.05", "james 0.46,0.04", "james 0.40,0.04", "james 0.30,0.03"]),
    ("andrew road", ["andrew 0.63,0.16", "andrew 0.46,0.17", "andrew 0.40,0.17", "andrew 0.34,0.15"]),
    ("jesus court", ["GATE", "J_T2", "J_T1"]),
    ("seller2", ["SELLER2", "SELLER2_SIDE", "COINS"]),
    ("jesus room", ["STAND", "ROUND", "WASH andrew", "wash -0.43,-0.30", "WASH peter"]),
]
KNEEL_LANE = ((-0.46, -0.38), BENCH_Z, UPPER + 0.06)   # x, z, nothing above (except the table's corner at x -0.355)
TERRAIN = {"road", "ground", "temple"}                 # walking surfaces (temple = the court paving)
HARD_PTS = [(v[0], v[1]) for v in MARKS.values()]
HARD_SEGS = [((MARKS[a][0], MARKS[a][1]), (MARKS[b][0], MARKS[b][1])) for _, ls in PATHS for a, b in zip(ls[:-1], ls[1:])]
SOFT_SEGS = []

# demo colouring (DESIGN.md §3)
COLOURS = {
    "stone": "#E9D6A8", "door": "#8A5A3B", "plaster": "#EBD2A6", "mats": "#D8BE8E", "sky": "#2E4A86",
    "cloth": "#F5F1E6", "cushion": "#9C3A3A", "bread": "#C98A4A", "clay": "#C46A3E", "water": "#7FB6E0",
    "facade": "#F4EEDD", "gold": "#D9A93A", "bronze": "#A8743E", "red": "#C2453A", "cream": "#F1E3C4",
    "wood": "#8A5A3B", "wicker": "#D2AE74", "coins": "#E8C04A", "road": "#E8D5A8", "paving": "#EADFC4",
    "ground": "#C9C08A", "palmLeaf": "#5E9A48", "coatRed": "#C2453A", "coatBlue": "#4E7FB8", "coatYellow": "#E8C04A",
    "leaf": "#5E9A48", "olive": "#8AA06A", "hills": "#8E9E62",
}
# the temple front's wall region is called "facade" in the drawing "facade"
REGION_HEX = {}


# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model), faces with region, smooth flag, a
    no-raster flag (scattered bits that sample a named texel) and optional skin weights (as Jonah / Miracles)"""

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


def wall(mb_out, mb_in, x0, x1, h0, h1, z0, z1, inner, skip=(), reg="stone", ireg="plaster"):
    """axis box whose `inner` face (one of left right front back) goes to the interior mesh, the rest outside"""
    box(mb_out, x0, x1, h0, h1, z0, z1, reg, skip=tuple(skip) + (inner, "bottom"))
    if inner and mb_in is not None:
        q = {"left": [(x0, h0, z0), (x0, h1, z0), (x0, h1, z1), (x0, h0, z1)],
             "right": [(x1, h0, z0), (x1, h1, z0), (x1, h1, z1), (x1, h0, z1)],
             "front": [(x0, h0, z1), (x1, h0, z1), (x1, h1, z1), (x0, h1, z1)],
             "back": [(x0, h0, z0), (x1, h0, z0), (x1, h1, z0), (x0, h1, z0)]}[inner]
        o = {"left": (-1, 0, 0), "right": (1, 0, 0), "front": (0, 0, 1), "back": (0, 0, -1)}[inner]
        quad(mb_in, q, ireg, o)


def prism_x(mb, x0, x1, poly, reg, end_mbs=None, end_regs=None, skip_edges=()):
    """solid along x (x0..x1) with cross-section poly [(z, h)...]; the end faces at x0 / x1 go to end_mbs[0] / [1]
    (None = left out) with end_regs; side edge i (poly[i] -> poly[i + 1]) is left out when i in skip_edges"""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) / 2
    tris = tessellate_polygon([[Vector((z, h, 0)) for z, h in poly]])
    mbs = end_mbs or (mb, mb)
    regs = end_regs or (reg, reg)
    for k, (x, o) in enumerate(((x0, -1), (x1, 1))):
        m = mbs[k]
        if m is None:
            continue
        ids = [m.v(x, h, z) for z, h in poly]
        for t in tris:
            m.fo([ids[i] for i in t], regs[k], (o, 0, 0))
    for i in range(n):
        if i in skip_edges:
            continue
        j = (i + 1) % n
        (za, ha), (zb, hb) = poly[i], poly[j]
        dz, dh = zb - za, hb - ha
        oz, oh = (dh, -dz) if area > 0 else (-dh, dz)
        mb.fo([mb.v(x0, ha, za), mb.v(x1, ha, za), mb.v(x1, hb, zb), mb.v(x0, hb, zb)], reg, (0, oh, oz))


def flat_cushion(mb, cx, cz, rx, rz, base, half, reg, n=4.0, seg=24, rad=0.010, step=0.005):
    """a pillow lying flat: superellipse outline (n = 2 round, 4 squarish) in (x, z), thickness 2 * half from base"""
    outline = []
    for a in np.linspace(0, TAU, seg, endpoint=False):
        c, s = math.cos(a), math.sin(a)
        outline.append((cx + rx * math.copysign(abs(c) ** (2 / n), c), cz + rz * math.copysign(abs(s) ** (2 / n), s)))
    m = MB(); m.nr = mb.nr
    puff(m, outline, 0.0, half, reg, rad=rad, edge=0.35, step=step)
    off = len(mb.V)
    for (x, b, o) in m.V:
        mb.V.append((x, base + half + o, b)); mb.P.append((x, base + half + o, b))
    for f, r, s_, nr in zip(m.F, m.R, m.S, m.N):
        mb.F.append([i + off for i in f[::-1]]); mb.R.append(r); mb.S.append(s_); mb.N.append(nr)


def lamp_mesh(mb, x, h, z, reg="clay"):
    """a small clay oil lamp, nozzle toward +x; returns the wick point"""
    lathe(mb, [(0.0, 0.0), (0.008, 0.0), (0.011, 0.004), (0.010, 0.008), (0.004, 0.010), (0.0, 0.010)], reg,
          C=(x, h, z), seg=12, sx=1.45)
    tube(mb, [(x + 0.010, h + 0.006, z), (x + 0.019, h + 0.008, z)], 0.0032, reg, seg=6)
    return (x + 0.019, h + 0.011, z)


# ============================================================================================ house
def side_wall_poly():
    return [(WB[0], UPPER), (HOUSE_ZF, UPPER), (HOUSE_ZF, SLOPE_LOW), (SLOPE_Z[0], BACK_TOP), (WB[0], BACK_TOP)]


def build_house(root):
    """`house` (outside: ground storey, side and back walls, roof edge, sill, door, shutters) with child `houseIn`
    (inside wall faces, window reveals and night-sky pane, floor mats, lamp shelf)"""
    ex, inn = MB(), MB()
    # ground storey: a closed block under the room
    box(ex, HOUSE_X[0], HOUSE_X[1], 0.0, UPPER, WB[0], HOUSE_ZF, "stone", skip=("top", "bottom"))
    box(ex, DOOR[0], DOOR[1], 0.0, DOOR[2], HOUSE_ZF, HOUSE_ZF + 0.003, "door", skip=("bottom", "back"))
    s0, s1, s2, s3 = SHUTTER
    box(ex, s0, s1, s2, s3, HOUSE_ZF, HOUSE_ZF + 0.003, "door", skip=("back",))
    # side walls (inner faces to the room); edge 0 = bottom (on the ground storey)
    prism_x(ex, WL[0], WL[1], side_wall_poly(), "stone", end_mbs=(ex, inn), end_regs=("stone", "plaster"),
            skip_edges=(0,))
    prism_x(ex, WR[0], WR[1], side_wall_poly(), "stone", end_mbs=(inn, ex), end_regs=("plaster", "stone"),
            skip_edges=(0,))
    # back wall between the side walls, with the window
    w0, w1, y0, y1 = UWIN
    wall(ex, inn, IN_X[0], IN_X[1], UPPER, y0, WB[0], WB[1], "front", skip=("top", "left", "right"))
    wall(ex, inn, IN_X[0], w0, y0, y1, WB[0], WB[1], "front", skip=("top", "bottom", "left", "right"))
    wall(ex, inn, w1, IN_X[1], y0, y1, WB[0], WB[1], "front", skip=("top", "bottom", "left", "right"))
    wall(ex, inn, IN_X[0], IN_X[1], y1, BACK_TOP, WB[0], WB[1], "front", skip=("top", "bottom", "left", "right"))
    quad(inn, [(w0, y0, WB[0]), (w1, y0, WB[0]), (w1, y0, WB[1]), (w0, y0, WB[1])], "plaster", UP)
    quad(inn, [(w0, y1, WB[0]), (w1, y1, WB[0]), (w1, y1, WB[1]), (w0, y1, WB[1])], "plaster", (0, -1, 0))
    for x, o in ((w0, 1), (w1, -1)):
        quad(inn, [(x, y0, WB[0]), (x, y1, WB[0]), (x, y1, WB[1]), (x, y0, WB[1])], "plaster", (o, 0, 0))
    quad(inn, [(w0, y0, WB[0] + 0.001), (w1, y0, WB[0] + 0.001), (w1, y1, WB[0] + 0.001), (w0, y1, WB[0] + 0.001)],
         "sky", (0, 0, 1))
    # flat roof edge: the back strip and the side strips over the full-height part (none over the room's front half)
    box(ex, HOUSE_X[0], HOUSE_X[1], BACK_TOP, BACK_TOP + RIM_T, WB[0], RIM_BACK_Z, "stone")
    box(ex, HOUSE_X[0], HOUSE_X[0] + 0.03, BACK_TOP, BACK_TOP + RIM_T, RIM_BACK_Z, SLOPE_Z[0], "stone", skip=("back",))
    box(ex, HOUSE_X[1] - 0.03, HOUSE_X[1], BACK_TOP, BACK_TOP + RIM_T, RIM_BACK_Z, SLOPE_Z[0], "stone", skip=("back",))
    # the cut-away front: a 1 cm sill
    box(ex, IN_X[0], IN_X[1], UPPER, SILL_H, SILL_Z[0], SILL_Z[1], "stone", skip=("bottom", "left", "right"))
    # ---- inside: floor mats (printed strips) and the lamp shelf
    quad(inn, [(IN_X[0], UPPER + 0.0003, IN_Z[0]), (IN_X[1], UPPER + 0.0003, IN_Z[0]),
               (IN_X[1], UPPER + 0.0003, SILL_Z[0]), (IN_X[0], UPPER + 0.0003, SILL_Z[0])], "mats", UP)
    dec = DECOR.setdefault("room", [])
    for x in (-0.48, -0.38, -0.28, -0.18):
        dec.append(((x, UPPER + 0.0006, IN_Z[0] + 0.004), (x, UPPER + 0.0006, SILL_Z[0] - 0.002)))
    inn.nr = True                                                # lamp shelf: a sliver on paper, named texel
    box(inn, SHELF[0], SHELF[1], SHELF[2] - 0.006, SHELF[2], WB[1], WB[1] + 0.016, "plaster", skip=("back",))
    inn.nr = False
    house = make_obj("house", ex, root, origin=(-0.33, UPPER, -0.40), smooth_angle=30)
    house_in = make_obj("houseIn", inn, house, origin=(-0.33, UPPER, -0.40), smooth_angle=40)
    return house, house_in


def build_stair(root):
    """the outside stair up the house's right wall (decor): four steps from z -0.25 back to a landing at y 0.10"""
    mb = MB()
    x0, x1 = STAIR_X
    for i in range(STAIR_N):
        zf = STAIR_Z0 - i * STAIR_D
        box(mb, x0, x1, 0.0, 0.02 * (i + 1), zf - STAIR_D, zf, "stone", skip=("bottom", "back", "left"))
    box(mb, x0, x1, 0.0, UPPER, LANDING_Z[0], LANDING_Z[1], "stone", skip=("bottom", "left"))
    return make_obj("stair", mb, root, origin=(sum(STAIR_X) / 2, 0.0, (STAIR_Z0 + LANDING_Z[0]) / 2), smooth_angle=30)


def build_bench(house):
    """`bench` along the left wall: a plain wooden bench (x -0.58..-0.532) with three cushions; seat top UPPER + 0.04"""
    mb = MB(); mb.nr = True
    box(mb, BENCH_X[0], BENCH_X[1], UPPER, BENCH_TOP - 0.012, BENCH_Z[0], BENCH_Z[1], "wood", skip=("bottom", "left"))
    zs = np.linspace(BENCH_Z[0], BENCH_Z[1], 4)
    for za, zb in zip(zs[:-1], zs[1:]):
        flat_cushion(mb, (BENCH_X[0] + BENCH_X[1]) / 2 + 0.001, (za + zb) / 2, (BENCH_X[1] - BENCH_X[0]) / 2 - 0.002,
                     (zb - za) / 2 - 0.003, BENCH_TOP - 0.012, 0.006, "cushion", n=5.0)
    mb.nr = False
    return make_obj("bench", mb, house, origin=((BENCH_X[0] + BENCH_X[1]) / 2, UPPER, (BENCH_Z[0] + BENCH_Z[1]) / 2),
                    smooth_angle=50)


def build_table(house):
    """`lowTable`: the low table with a white cloth hanging 3 cm, four legs, the five seat cushions at the supper marks
    (the two left ones printed, the three behind the table named texels), a herb dish and a fruit bowl; children
    `breadLoaf`, `cupTable`, `lamp2`"""
    mb = MB()
    x0, x1 = TABLE_X; z0, z1 = TABLE_Z
    box(mb, x0, x1, TABLE_TOP - 0.030, TABLE_TOP, z0, z1, "cloth", skip=("bottom",))
    dec = DECOR.setdefault("table", [])
    mb.nr = True
    for x in (x0 + 0.012, x1 - 0.012):
        for z in (z0 + 0.012, z1 - 0.012):
            tube(mb, [(x, UPPER, z), (x, TABLE_TOP - 0.030, z)], 0.004, "wood", seg=6)
    mb.nr = False
    mb.nr = True                                 # seat cushions: under 6 mm on paper, named texel (awning red)
    for who, (cx, cz) in SUP.items():
        flat_cushion(mb, cx, cz, 0.030, 0.026, UPPER, CUSHION_H / 2, "cushion", n=2.6)
    lathe(mb, [(0.0, 0.0), (0.012, 0.0), (0.016, 0.005), (0.014, 0.006), (0.0, 0.003)], "clay",
          C=(HERBS[0], TABLE_TOP, HERBS[1]), seg=12)
    for k in range(4):
        a = TAU * k / 4 + 0.4
        lumpy(mb, (HERBS[0] + 0.006 * math.cos(a), TABLE_TOP + 0.005, HERBS[1] + 0.005 * math.sin(a)), 0.005, "herbs",
              seg=6, rings=4, sh=0.7, amp=0.3, seed=k)
    lathe(mb, [(0.0, 0.0), (0.008, 0.0), (0.015, 0.008), (0.016, 0.011), (0.013, 0.011), (0.0, 0.006)], "clay",
          C=(FRUIT[0], TABLE_TOP, FRUIT[1]), seg=12)
    for k, (dx, dz) in enumerate(((-0.005, 0.002), (0.005, 0.003), (0.0, -0.005))):
        sphere(mb, (FRUIT[0] + dx, TABLE_TOP + 0.013, FRUIT[1] + dz), 0.0065, "fruit", seg=8, rings=5)
    mb.nr = False
    table = make_obj("lowTable", mb, house, origin=((x0 + x1) / 2, UPPER, (z0 + z1) / 2), smooth_angle=45)
    bm = MB()
    lathe(bm, [(0.0, 0.0), (0.019, 0.0), (0.021, 0.004), (0.018, 0.010), (0.009, 0.0125), (0.0, 0.013)], "bread",
          C=(BREAD[0], TABLE_TOP, BREAD[1]), seg=18)
    bread = make_obj("breadLoaf", bm, table, origin=(BREAD[0], TABLE_TOP, BREAD[1]), smooth_angle=60)
    cm = MB()
    lathe(cm, [(0.0, 0.0), (0.009, 0.0), (0.009, 0.003), (0.0045, 0.006), (0.0045, 0.010), (0.012, 0.015),
               (0.014, 0.030), (0.012, 0.030), (0.0, 0.025)], "clay", C=(CUP[0], TABLE_TOP, CUP[1]), seg=16)
    cup = make_obj("cupTable", cm, table, origin=(CUP[0], TABLE_TOP, CUP[1]), smooth_angle=50)
    lm = MB(); lm.nr = True
    wick = lamp_mesh(lm, LAMP2[0], TABLE_TOP, LAMP2[1])
    lm.nr = False
    lamp2 = make_obj("lamp2", lm, table, origin=wick, smooth_angle=50)
    return table, bread, cup, lamp2


def build_basin(house):
    """`basinStand` (round wooden stand, top UPPER + 0.08) with child `basinJug` (the basin on the stand, water in it;
    the jug on the floor beside the stand, in the corner)"""
    sx, sz = STAND_C
    mb = MB(); mb.nr = True
    lathe(mb, [(0.0, STAND_TOP - 0.006), (STAND_R, STAND_TOP - 0.006), (STAND_R, STAND_TOP), (0.0, STAND_TOP)], "wood",
          C=(sx, 0.0, sz), seg=16)
    tube(mb, [(sx, UPPER + 0.010, sz), (sx, STAND_TOP - 0.006, sz)], 0.006, "wood", seg=8)
    for a in (math.radians(5), math.radians(125), math.radians(245)):
        tube(mb, [(sx, UPPER + 0.012, sz), (sx + 0.017 * math.cos(a), UPPER + 0.002, sz + 0.017 * math.sin(a))], 0.0035,
             "wood", seg=6)
    mb.nr = False
    stand = make_obj("basinStand", mb, house, origin=(sx, UPPER, sz), smooth_angle=50)
    bj = MB(); bj.nr = True                       # under 6 mm on paper: named texels (cup clay, coat blue water)
    lathe(bj, [(0.0, 0.0, "clay"), (0.017, 0.0), (0.025, 0.008), (0.027, 0.016), (0.024, 0.016),
               (0.024, 0.012, "water"), (0.0, 0.012)], "clay", C=(sx, STAND_TOP, sz), seg=20)
    jx, jz = JUG
    lathe(bj, [(0.0, 0.0), (0.009, 0.0), (0.0125, 0.013), (0.011, 0.030), (0.006, 0.042), (0.005, 0.050),
               (0.0075, 0.053), (0.0, 0.051)], "clay", C=(jx, UPPER, jz), seg=14)
    tube(bj, [(jx - 0.010, UPPER + 0.040, jz), (jx - 0.018, UPPER + 0.034, jz), (jx - 0.016, UPPER + 0.020, jz),
              (jx - 0.011, UPPER + 0.016, jz)], 0.0024, "clay", seg=6)
    bj.nr = False
    jugs = make_obj("basinJug", bj, stand, origin=(sx, STAND_TOP, sz), smooth_angle=50)
    return stand, jugs


def build_lamp1(house):
    mb = MB(); mb.nr = True
    wick = lamp_mesh(mb, LAMP1[0] - 0.004, SHELF[2], LAMP1[1])
    mb.nr = False
    return make_obj("lamp1", mb, house, origin=wick, smooth_angle=50)


# ============================================================================================ ground: road, paving
def road_polys():
    main = catmull([(0.64, 0.116), (0.45, 0.112), (0.28, 0.106), (0.12, 0.100), (-0.02, 0.100), (-0.14, 0.102),
                    (-0.26, 0.100)], 0.012)
    branch = catmull([(0.10, 0.075), (0.135, -0.020), (0.170, -0.095), (0.180, -0.150)], 0.012)
    return strip_poly(main, 0.14, 0.13), strip_poly(branch, 0.11, 0.13)


HOUSE_BLOCK = np.array([(HOUSE_X[0], HOUSE_ZF), (HOUSE_X[1], HOUSE_ZF), (HOUSE_X[1], FLOOR[2]), (HOUSE_X[0], FLOOR[2])])
COURT_POLY = np.array([(COURT_X[0], COURT_Z1), (COURT_X[1], COURT_Z1), (COURT_X[1], FLOOR[2]), (COURT_X[0], FLOOR[2])])


def land_h(x, z, reg):
    base = {"road": 0.0026, "paving": 0.0024, "ground": 0.0020}[reg]
    return base + 0.0004 * (nz(x * 7, z * 7) - 0.5)


def build_ground(root):
    """`road`, `temple` (the court paving) and `ground` from one constrained triangulation of the floor (the house
    block left out)"""
    main, branch = road_polys()
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    outlines = [_resample(rect, 0.02), _resample(HOUSE_BLOCK, 0.02), _resample(COURT_POLY, 0.02),
                _resample(main, 0.010), _resample(branch, 0.010)]
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
        if in_poly(c, HOUSE_BLOCK):
            return None
        if in_poly(c, main) or in_poly(c, branch):
            return "road"
        if in_poly(c, COURT_POLY):
            return "paving"
        return "ground"
    mbs = {k: MB() for k in ("road", "paving", "ground")}
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
    dec = DECOR.setdefault("ground", [])
    for x in np.arange(0.16, 0.59, 0.14):                       # paving joints (cells >= 6 mm at the plan's scale)
        dec.append(((x, 0.0030, FLOOR[2] + 0.004), (x, 0.0030, CWALL_Z[0] - 0.004)))
    for z in (-0.26, -0.40):
        dec.append(((COURT_X[0] + 0.004, 0.0030, z), (COURT_X[1] - 0.004, 0.0030, z)))
    rng = random.Random(21)
    for k in range(30):                                          # grass ticks on the ground
        x = rng.uniform(-0.58, 0.58); z = rng.uniform(-0.20, 0.20)
        if in_poly((x, z), COURT_POLY) or in_poly((x, z), HOUSE_BLOCK) or \
                any(in_poly((x + dx, z + dz), poly) for poly in (main, branch) for dx in (-0.012, 0.012)
                    for dz in (-0.012, 0.0, 0.012)):
            continue
        for s in (-1, 0, 1):
            dec.append(((x + s * 0.004, 0.0024, z), (x + s * 0.006, 0.0024, z - 0.008)))
    road = make_obj("road", mbs["road"], root, origin=(0.20, 0.0, 0.10), smooth_angle=35)
    temple = make_obj("temple", mbs["paving"], root, origin=(0.31, 0.0, -0.35), smooth_angle=35)
    ground = make_obj("ground", mbs["ground"], root, smooth_angle=35)
    return road, temple, ground


def build_palms_road(road):
    """`palmsRoad` (hidden at start): four palm branches (serrated leaf outlines) and three coats (red, blue, yellow)
    laid flat along the road, x 0.09..0.55, z 0.05..0.16, top <= 0.008"""
    mb = MB()
    y0, y1 = 0.0028, 0.0062
    items = [("branch", 0.130, 0.078, 0.08), ("coatRed", 0.190, 0.135, -0.06), ("branch", 0.255, 0.078, -0.08),
             ("coatBlue", 0.320, 0.135, 0.07), ("branch", 0.385, 0.078, 0.08), ("coatYellow", 0.450, 0.135, -0.05),
             ("branch", 0.510, 0.078, -0.08)]
    for kind, cx, cz, rot in items:
        c, s = math.cos(rot), math.sin(rot)
        if kind == "branch":
            pts = []
            n = 28
            for i in range(n):                                   # pointed oval with saw teeth (the leaflets)
                t = TAU * i / n
                r = 1.0 + (0.10 if i % 2 else 0.0)
                pts.append((0.056 * math.cos(t) * r, 0.0235 * math.sin(t) * abs(math.sin(t)) ** 0.15 * r))
            reg = "palmLeaf"
        else:
            pts = []
            for i in range(20):                                  # rounded oblong coat with short sleeves
                t = TAU * i / 20
                cc, ss = math.cos(t), math.sin(t)
                pts.append((0.036 * math.copysign(abs(cc) ** 0.45, cc), 0.0245 * math.copysign(abs(ss) ** 0.45, ss)))
            reg = kind
        poly = [(cx + px * c - pz * s, cz + px * s + pz * c) for px, pz in pts]
        ngon_top(mb, poly, y1, reg, hb=y0)
    return make_obj("palmsRoad", mb, road, origin=(0.32, 0.0, 0.105), smooth_angle=60)


def build_stones(road):
    """`stones`: five round roadside stones in a heap at (0.05, 0.17); heap radius <= 0.025, top <= 0.03"""
    mb = MB(); mb.nr = True
    sx, sz = STONES
    for k, (dx, dz, y, r) in enumerate(((-0.013, -0.007, 0.000, 0.0095), (0.008, -0.005, 0.000, 0.0090),
                                        (-0.004, 0.011, 0.000, 0.0095), (0.014, 0.011, 0.000, 0.0080),
                                        (0.000, 0.000, 0.013, 0.0080))):
        lumpy(mb, (sx + dx, y + r * 0.85, sz + dz), r, "stone", seg=10, rings=6, sh=0.85, amp=0.12, seed=k + 3,
              flat_bottom=0.0)
    mb.nr = False
    return make_obj("stones", mb, road, origin=(sx, 0.0, sz), smooth_angle=60)


# ============================================================================================ the temple court
def build_court(temple):
    """`courtWall`, `templeFront`, `awnings` (children of `temple`)"""
    wm = MB(); wm.nr = True
    for x0, x1 in ((COURT_X[0], GATE_X[0]), (GATE_X[1], COURT_X[1])):
        box(wm, x0, x1, 0.0, CWALL_H, CWALL_Z[0], CWALL_Z[1], "facade", skip=("bottom",))
    for x in (GATE_X[0], GATE_X[1]):                              # gate posts (still <= 0.04)
        x0, x1 = (x - 0.014, x) if x == GATE_X[0] else (x, x + 0.014)
        box(wm, x0, x1, 0.0, 0.040, CWALL_Z[0], CWALL_Z[1], "facade", skip=("bottom",))
    wm.nr = False
    cwall = make_obj("courtWall", wm, temple, origin=(0.31, 0.0, sum(CWALL_Z) / 2), smooth_angle=30)
    # temple front relief
    fm = MB()
    box(fm, TEMPLE_X[0], TEMPLE_X[1], 0.0, TEMPLE_WALL, TEMPLE_Z[0], TEMPLE_Z[1], "facade", skip=("bottom", "back"))
    box(fm, TEMPLE_X[0] - 0.004, TEMPLE_X[1], TEMPLE_WALL - 0.005, PEDIMENT[2], TEMPLE_Z[0], TEMPLE_Z[1] + 0.006, "gold",
        skip=("bottom", "back"))
    extrude(fm, [(PEDIMENT[0], PEDIMENT[2]), (PEDIMENT[1], PEDIMENT[2]), ((PEDIMENT[0] + PEDIMENT[1]) / 2, PEDIMENT[3])],
            TEMPLE_Z[0], TEMPLE_Z[1] + 0.004, "gold", back=False)
    box(fm, TDOOR[0], TDOOR[1], 0.0, TDOOR[2], TEMPLE_Z[1], TEMPLE_Z[1] + 0.003, "bronze", skip=("bottom", "back"))
    dec = DECOR.setdefault("facade", [])
    zf = TEMPLE_Z[1] + 0.0004
    for x in (0.12, 0.21, 0.47, 0.56):                            # pilasters (printed)
        dec.append(((x, 0.004, zf), (x, TEMPLE_WALL - 0.008, zf)))
    dec.append(((TEMPLE_X[0] + 0.004, 0.030, zf), (TDOOR[0] - 0.004, 0.030, zf)))      # plinth course
    dec.append(((TDOOR[1] + 0.004, 0.030, zf), (TEMPLE_X[1] - 0.004, 0.030, zf)))
    fm.nr = True
    for x in COLS_X:                                              # colonnade (named texel: the white stone)
        lathe(fm, [(0.0, 0.0), (0.027, 0.0), (0.027, 0.010), (0.022, 0.016), (COL_R, 0.024), (COL_R * 0.92, COL_TOP - 0.022),
                   (0.024, COL_TOP - 0.012), (0.027, COL_TOP - 0.004), (0.027, COL_TOP), (0.0, COL_TOP)], "facade",
              C=(x, 0.0, COLS_Z), seg=14)
    box(fm, ARCH[0], ARCH[1], ARCH[2], ARCH[3], ARCH[4], ARCH[5], "facade", skip=("back",))
    fm.nr = False
    front = make_obj("templeFront", fm, temple, origin=(0.31, 0.0, -0.55), smooth_angle=40)
    # awnings: striped canopies sloping from the architrave (y 0.43) to the front edge (y 0.39), a valance, two poles
    am = MB()
    zb, zf2 = AWN_Z; yb, yf = AWN_Y
    for x0, x1, n in AWNINGS:
        xs = np.linspace(x0, x1, n + 1)
        for i in range(n):
            reg = "red" if i % 2 == 0 else "cream"
            a0, a1 = xs[i], xs[i + 1]
            quad(am, [(a0, yb, zb), (a1, yb, zb), (a1, yf, zf2), (a0, yf, zf2)], reg, (0, 1, 0.66))
            quad(am, [(a0, yb - 0.004, zb), (a1, yb - 0.004, zb), (a1, yf - 0.004, zf2), (a0, yf - 0.004, zf2)], reg,
                 (0, -1, -0.66))
            quad(am, [(a0, yf - 0.016, zf2), (a1, yf - 0.016, zf2), (a1, yf, zf2), (a0, yf, zf2)], reg, (0, 0, 1))
            quad(am, [(a0, yf - 0.016, zf2 - 0.001), (a1, yf - 0.016, zf2 - 0.001), (a1, yf - 0.004, zf2 - 0.001),
                      (a0, yf - 0.004, zf2 - 0.001)], reg, (0, 0, -1))
        for x, o in ((x0, -1), (x1, 1)):
            quad(am, [(x, yb - 0.004, zb), (x, yb, zb), (x, yf, zf2), (x, yf - 0.016, zf2)], "red", (o, 0, 0))
        am.nr = True
        for x in (x0, x1):
            tube(am, [(x, 0.0, -0.50), (x, yb + 0.004, -0.50)], 0.004, "pole", seg=6)
        am.nr = False
    awn = make_obj("awnings", am, temple, origin=(0.31, 0.0, -0.50), smooth_angle=30)
    return cwall, front, awn


def stall_table(mb, x0, x1, z0, z1, legs_nr=True):
    """a market table: an apron-deep top (y 0.022..0.06) on four legs"""
    box(mb, x0, x1, T_APRON, T_TOP, z0, z1, "wood", skip=("bottom",) if False else ())
    keep = mb.nr
    mb.nr = keep or legs_nr
    for x in (x0 + 0.007, x1 - 0.007):
        for z in (z0 + 0.007, z1 - 0.007):
            tube(mb, [(x, 0.0, z), (x, T_APRON, z)], 0.0042, "wood", seg=6)
    mb.nr = keep


def cage(mb, cx, cz, base, rx=0.020, rz=0.019, h=0.033, reg="wicker"):
    lathe(mb, [(0.0, 0.0), (1.0, 0.0), (1.0, h * 0.70), (0.80, h * 0.92), (0.45, h), (0.0, h)], reg,
          C=(cx, base, cz), seg=14, sx=rx, sv=rz, rfun=None)


def build_stalls(temple):
    """`table1` (+ `cages`, hidden `cagesOpen`), `table2` (coin chest, coin stacks, scale), hidden `table2Tipped`,
    hidden `coinsFloor`"""
    m1 = MB()
    stall_table(m1, *T1)
    t1 = make_obj("table1", m1, temple, origin=((T1[0] + T1[1]) / 2, T_TOP, (T1[2] + T1[3]) / 2), smooth_angle=30)
    cz = (T1[2] + T1[3]) / 2
    spots = [(0.366, cz, T_TOP, 0.0155, 0.0165, 0.032), (0.3985, cz, T_TOP, 0.0155, 0.0165, 0.032),
             (0.382, cz, T_TOP + 0.033, 0.0150, 0.0160, 0.026)]
    cm = MB()
    for x, z, b, rx, rz, h in spots:
        cage(cm, x, z, b, rx, rz, h)
    dec = DECOR.setdefault("stall1", [])
    for x, z, b, rx, rz, h in spots[1:]:                          # bars on two cages (the first stays a big cell)
        for dx in (-rx * 0.45, rx * 0.45):
            dec.append(((x + dx, b + 0.003, z + rz + 0.0006), (x + dx, b + h * 0.80, z + rz + 0.0006)))
    x, z, b, rx, rz, h = spots[2]
    dec.append(((x - rx, b + 0.0005, z + rz + 0.0008), (x + rx, b + 0.0005, z + rz + 0.0008)))
    cm.nr = True                                                  # white doves peeping out of the tops
    for x, z, b, rx, rz, h in spots:
        sphere(cm, (x + 0.004, b + h + 0.004, z + 0.004), 0.0070, "dove", seg=8, rings=5)
        sphere(cm, (x + 0.009, b + h + 0.009, z + 0.006), 0.0045, "dove", seg=8, rings=5)
    cm.nr = False
    cages = make_obj("cages", cm, t1, origin=(0.382, T_TOP + 0.03, cz), smooth_angle=50)
    om = MB(); om.nr = True
    for x, z, b, rx, rz, h in spots:
        cage(om, x, z, b, rx, rz, h)
        d0 = (x - 0.008, b + 0.004, z + rz); d1 = (x + 0.008, b + 0.004, z + rz)      # door flap swung down and out
        quad(om, [d0, d1, (d1[0], d1[1] - 0.003, d1[2] + 0.016), (d0[0], d0[1] - 0.003, d0[2] + 0.016)], "wicker",
             (0, 1, 0.2))
        quad(om, [d0, d1, (d1[0], d1[1] - 0.003, d1[2] + 0.016), (d0[0], d0[1] - 0.003, d0[2] + 0.016)], "wicker",
             (0, -1, -0.2))
    om.nr = False
    cages_open = make_obj("cagesOpen", om, t1, origin=(0.382, T_TOP + 0.03, cz), smooth_angle=50)
    # table2 with the money
    m2 = MB()
    stall_table(m2, *T2)
    box(m2, 0.457, 0.491, T_TOP, T_TOP + 0.026, -0.300, -0.277, "coins")                     # coin chest
    m2.nr = True
    box(m2, 0.456, 0.492, T_TOP + 0.026, T_TOP + 0.031, -0.302, -0.275, "coins")              # lid
    for k, (x, z, h) in enumerate(((0.472, -0.262, 0.016), (0.485, -0.263, 0.010))):
        lathe(m2, [(0.0, 0.0), (0.0062, 0.0), (0.0062, h), (0.0, h)], "coins", C=(x, T_TOP, z), seg=10)
    bx, bz = 0.441, -0.266                                        # the little scale (left: the seller's walk passes right)
    tube(m2, [(bx, T_TOP, bz), (bx, T_TOP + 0.046, bz)], 0.0018, "coins", seg=6)
    tube(m2, [(bx - 0.013, T_TOP + 0.044, bz), (bx + 0.013, T_TOP + 0.044, bz)], 0.0014, "coins", seg=5)
    for s in (-1, 1):
        lathe(m2, [(0.0, 0.0), (0.0065, 0.0), (0.008, 0.003), (0.0, 0.002)], "coins",
              C=(bx + s * 0.013, T_TOP + 0.026, bz), seg=10)
        for dz in (-0.005, 0.005):
            tube(m2, [(bx + s * 0.013, T_TOP + 0.029, bz + dz), (bx + s * 0.013, T_TOP + 0.044, bz)], 0.0007, "coins",
                 seg=4, caps=False)
    m2.nr = False
    t2 = make_obj("table2", m2, temple, origin=((T2[0] + T2[1]) / 2, T_TOP, (T2[2] + T2[3]) / 2), smooth_angle=30)
    # table2Tipped: the same table on its side, tipped away (+x): top vertical at x ~0.50, legs pointing back at Jesus
    tm = MB(); tm.nr = True
    stall_table(tm, *T2)
    pivot_x = T2[1]
    shift = -0.064
    yaw = math.radians(-8.0)
    cxz = (0.474, (T2[2] + T2[3]) / 2)
    out = []
    for (x, h, z) in tm.V:
        # rotate -90 deg about the axis (x = pivot, h = 0) along z: (dx, h) -> (h, -dx)
        dx = x - pivot_x
        nx, nh = pivot_x + h + shift, -dx
        ex, ez = nx - cxz[0], z - cxz[1]
        out.append((cxz[0] + ex * math.cos(yaw) - ez * math.sin(yaw), nh, cxz[1] + ex * math.sin(yaw) + ez * math.cos(yaw)))
    tm.V = out; tm.P = list(out)
    tm.nr = False
    tipped = make_obj("table2Tipped", tm, temple, origin=(cxz[0], 0.0, cxz[1]), smooth_angle=30)
    # coinsFloor: scattered flat coins
    fm = MB(); fm.nr = True
    rng = random.Random(17)
    placed = []
    while len(placed) < 22:
        x, z = rng.uniform(0.405, 0.575), rng.uniform(-0.235, -0.155)
        if any(math.hypot(x - a, z - b) < 0.016 for a, b in placed):
            continue
        placed.append((x, z))
        lathe(fm, [(0.0, 0.0), (0.0058, 0.0), (0.0058, 0.0025), (0.0, 0.0025)], "coins", C=(x, 0.0022, z), seg=8)
    fm.nr = False
    coins = make_obj("coinsFloor", fm, temple, origin=(0.49, 0.0, -0.195), smooth_angle=50)
    return t1, cages, cages_open, t2, tipped, coins


# ============================================================================================ trees, hills
def build_palm(root):
    """palmTree in the lane behind everything: trunk r 0.015, crown of fat fronds y 0.44..0.52"""
    mb = MB(); mb.nr = True
    px, pz = PALM
    tube(mb, [(px, 0.0, pz), (px + 0.004, 0.14, pz - 0.002), (px, 0.30, pz), (px + 0.005, 0.47, pz)],
         [0.015, 0.013, 0.012, 0.010], "trunk", seg=8)
    mb.nr = False
    hub = (px + 0.005, 0.485, pz)
    lumpy(mb, hub, 0.024, "leaf", seg=10, rings=6, sh=0.9, amp=0.10, seed=2)
    fronds = [(0.0, 0.10, 0.012), (35, 0.095, 0.0), (150, 0.06, 0.03), (180, 0.058, 0.035), (215, 0.06, 0.03),
              (300, 0.09, 0.005), (250, 0.07, 0.02), (75, 0.085, 0.0)]   # angle in plan (0 = +x, 90 = -z), length, rise
    for k, (ang, L, rise) in enumerate(fronds):
        a = math.radians(ang)
        dx, dz = math.cos(a), -math.sin(a)
        p0 = (hub[0] + dx * 0.012, hub[1], hub[2] + dz * 0.012)
        p1 = (hub[0] + dx * L * 0.5, hub[1] + 0.018 + rise, hub[2] + dz * L * 0.5)
        p2 = (hub[0] + dx * L, hub[1] - 0.030 + rise, hub[2] + dz * L)
        blade(mb, [p0, p1, p2], [0.020, 0.034, 0.0], "leaf")
    return make_obj("palmTree", mb, root, origin=(px, 0.0, pz), smooth_angle=60)


def build_olive(root):
    """oliveTree: a short gnarled trunk under a small grey-green crown (r 0.035, underside >= 0.17), leaning toward
    the house so the court marks stay clear"""
    mb = MB(); mb.nr = True
    ox, oz = OLIVE
    cx, cz = OLIVE_CROWN
    tube(mb, [(ox, 0.0, oz), (ox - 0.004, 0.07, oz + 0.003), (ox + 0.002, 0.13, oz), (cx, 0.19, cz)],
         [0.012, 0.010, 0.009, 0.007], "trunk", seg=8)
    mb.nr = False
    for k, (dx, h, dz, r) in enumerate(((0.000, 0.215, 0.000, 0.022), (-0.016, 0.205, 0.006, 0.017),
                                         (0.015, 0.207, 0.004, 0.016), (0.000, 0.232, -0.006, 0.018),
                                         (-0.008, 0.200, -0.012, 0.015))):
        lumpy(mb, (cx + dx, h, cz + dz), r, "olive", seg=12, rings=7, sh=0.85, amp=0.14, seed=k + 6, flat_bottom=0.172)
    return make_obj("oliveTree", mb, root, origin=(ox, 0.0, oz), smooth_angle=60)


def hills_top(x):
    t = (x - HILLS_X[0]) / (HILLS_X[1] - HILLS_X[0])
    h = 0.60 + 0.045 * math.sin(TAU * 1.1 * t + 0.6) + 0.018 * math.sin(TAU * 2.7 * t + 1.3)
    return max(BACK_TOP + 0.03, h - 0.12 * max(0.0, t - 0.82) / 0.18)


def build_hills(root):
    """Mount of Olives: a low relief behind the house's back wall (front face z -0.5845), 0.12-0.20 above the wall"""
    mb = MB()
    xs = np.linspace(HILLS_X[0], HILLS_X[1], 48)
    poly = [(x, 0.42) for x in xs[::-1]] + [(x, hills_top(x)) for x in xs]
    extrude(mb, poly[::-1], HILLS_Z[0], HILLS_Z[1], "hills")
    dec = DECOR.setdefault("hills", [])
    rng = random.Random(8)
    for k in range(9):                                            # little olive-tree marks on the slope
        x = rng.uniform(HILLS_X[0] + 0.04, HILLS_X[1] - 0.06)
        h = hills_top(x) - rng.uniform(0.030, 0.060)
        z = HILLS_Z[1] + 0.0002
        dec.append(((x - 0.007, h - 0.004, z), (x, h + 0.008, z)))
        dec.append(((x, h + 0.008, z), (x + 0.007, h - 0.004, z)))
    return make_obj("hills", mb, root, origin=(-0.33, 0.0, HILLS_Z[1]), smooth_angle=30)


# ============================================================================================ crowd
R_OF = {"red": ("palms", "coatRed"), "blue": ("palms", "coatBlue"), "yellow": ("palms", "coatYellow"),
        "green": ("olive", "olive"), "brown": ("house", "door"), "straw": ("room", "mats"), "cream": ("facade", "facade"),
        "rose": ("awnings", "red"), "sky": ("room", "sky"), "bronze": ("facade", "bronze"), "gold": ("facade", "gold"),
        "earth": ("ground", "road")}
# name, x, z, head top, yaw (deg; facing (sin, cos) in x, z: 0 = toward the viewer), robe, head cloth / hair, raised hand
CROWD = [("crowd1", 0.300, -0.072, 0.235, 25, "blue", "cream", 1),
         ("crowd2", 0.353, -0.068, 0.228, 10, "rose", "straw", -1),
         ("crowd3", 0.406, -0.072, 0.240, 0, "green", "cream", 1),
         ("crowd4", 0.459, -0.068, 0.230, -10, "yellow", "brown", -1),
         ("crowd5", 0.512, -0.072, 0.238, -15, "bronze", "cream", 1),
         ("crowd6", 0.563, -0.068, 0.226, -25, "red", "straw", -1),
         ("crowd7", -0.300, 0.165, 0.145, 75, "sky", "brown", 1),        # the two children, at the road's end by the
         ("crowd8", -0.355, 0.183, 0.140, 62, "gold", "brown", -1)]      # house (SET.md: moved from the right front)
SWAY_DEG, SWAY_LEN = 4.0, 3.0


def person_mesh(H, raise_side, child):
    """a simple townsperson in the set's style, facing +z, feet at the origin (named texels only): robe, head cloth
    (adults) or hair (children), face, hands, a palm frond held up in one hand. Head top = H, frond tip ~ 1.17 H."""
    mb = MB(); mb.nr = True
    k = H / 0.30
    lathe(mb, [(0.0, 0.0), (0.040 * k, 0.0), (0.038 * k, 0.05 * k), (0.032 * k, 0.15 * k), (0.030 * k, 0.21 * k),
               (0.018 * k, 0.235 * k), (0.0, 0.24 * k)], "robe", seg=12)
    head_c, hr = (0.0, 0.262 * k, 0.0), 0.030 * k
    for s in (-1, 1):
        if s == raise_side:
            sh, el, hd = (s * 0.030 * k, 0.215 * k, 0.0), (s * 0.047 * k, 0.250 * k, 0.003 * k), (s * 0.050 * k, 0.285 * k, 0.003 * k)
            tube(mb, [sh, el, hd], 0.0085 * k, "robe", seg=8)
            sphere(mb, hd, 0.008 * k, "face", seg=8, rings=5)
            blade(mb, [(hd[0], hd[1] - 0.004 * k, hd[2]), (hd[0] + s * 0.008 * k, hd[1] + 0.035 * k, hd[2] - 0.004 * k),
                       (hd[0] + s * 0.020 * k, hd[1] + 0.065 * k, hd[2] - 0.008 * k)],
                  [0.004 * k, 0.024 * k, 0.0], "palm", nrm=(0, 0, 1))
        else:
            tube(mb, [(s * 0.030 * k, 0.215 * k, 0.0), (s * 0.040 * k, 0.17 * k, 0.008 * k),
                      (s * 0.036 * k, 0.13 * k, 0.016 * k)], 0.0085 * k, "robe", seg=8)
            sphere(mb, (s * 0.034 * k, 0.122 * k, 0.020 * k), 0.008 * k, "face", seg=8, rings=5)
    hx, hy, hz = head_c
    sphere(mb, (hx, hy, hz + hr * 0.15), hr, "face", seg=12, rings=8)
    if child:
        lathe(mb, [(0.0, hy + hr * 0.05), (hr * 1.04, hy + hr * 0.15), (hr * 0.95, hy + hr * 0.75), (0.0, hy + hr * 1.12)],
              "cloth", C=(hx, 0.0, hz - hr * 0.25), seg=12)
    else:
        lathe(mb, [(0.0, hy - hr * 0.1), (hr * 1.08, hy - hr * 0.2), (hr * 1.10, hy + hr * 0.45), (hr * 0.75, hy + hr * 0.95),
                   (0.0, hy + hr * 1.12)], "cloth", C=(hx, 0.0, hz - hr * 0.22), seg=12)
    for s in (-1, 1):
        sphere(mb, (hx + s * hr * 0.36, hy + hr * 0.18, hz + hr * 1.05), hr * 0.12, "eye", seg=6, rings=4)
    mb.nr = False
    return mb


def facing(yaw_deg):
    a = math.radians(yaw_deg)
    return (math.sin(a), 0.0, math.cos(a))


def build_crowd(root):
    """armature `crowd` (bones sway1..sway8 at the figures' feet; looping action crowdSway: 3 s at 24 fps, each figure
    rocks +-4 deg side to side about its feet, phases staggered) with skinned children crowd1..crowd8"""
    arm = bpy.data.armatures.new("crowd_arm")
    rig = link(bpy.data.objects.new("crowd", arm))
    parent_keep(rig, root)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    for i, c in enumerate(CROWD):
        b = arm.edit_bones.new("sway%d" % (i + 1))
        b.head = B(c[1], 0.0, c[2]); b.tail = B(c[1], 0.05, c[2]); b.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')
    obs = []
    for i, (name, x, z, H, yaw, robe, cloth, rs) in enumerate(CROWD):
        mb = person_mesh(H, rs, name in ("crowd7", "crowd8"))
        a = math.radians(yaw)
        mb.V = [(x + vx * math.cos(a) + vz * math.sin(a), vh, z - vx * math.sin(a) + vz * math.cos(a)) for vx, vh, vz in mb.V]
        mb.P = list(mb.V)
        mb.W = {j: {"sway%d" % (i + 1): 1.0} for j in range(len(mb.V))}
        ob = make_obj(name, mb, rig, origin=(x, 0.0, z), smooth_angle=60)
        mod = ob.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
        obs.append(ob)
    rig.animation_data_create()
    frames = int(SWAY_LEN * 24)
    for i, (name, x, z, H, yaw, robe, cloth, rs) in enumerate(CROWD):
        pb = rig.pose.bones["sway%d" % (i + 1)]
        pb.rotation_mode = 'QUATERNION'
        M3 = rig.data.bones[pb.name].matrix_local.to_3x3()
        f = facing(yaw)
        axis = Vector(B(*f)).normalized()
        ph = 1.7 * i
        for fr in range(1, frames + 2, 3):
            u = TAU * (fr - 1) / frames
            q = Quaternion(axis, math.radians(SWAY_DEG) * math.sin(u + ph))
            pb.rotation_quaternion = (M3.inverted() @ q.to_matrix() @ M3).to_quaternion()
            pb.keyframe_insert("rotation_quaternion", frame=fr)
    rig.animation_data.action.name = "crowdSway"
    bpy.context.scene.frame_set(1)
    for ob in obs:                                                # the GLB rest pose = the meshes as built
        pass
    return rig, obs


def sway_points(name, P):
    """design points of a crowd figure at the two sway extremes (+-4 deg about its feet, axis = facing)"""
    c = next(c for c in CROWD if c[0] == name)
    f = np.array(facing(c[4])); o = np.array([c[1], 0.0, c[2]])
    out = []
    for ang in (math.radians(SWAY_DEG), -math.radians(SWAY_DEG)):
        v = P - o
        cs, sn = math.cos(ang), math.sin(ang)
        r = v * cs + np.cross(f, v) * sn + np.outer(v @ f, f) * (1 - cs)
        out.append(r + o)
    return np.concatenate(out)


# ============================================================================================ drawings / UV
def _chars_proposal():
    """CONTRACT §2 start slots; Jesus and Peter boxes as printed in Real Miracles (the same figures), the donkey's side
    view guessed from its sizes (nose -X, tail +X) until regions_characters.json exists"""
    return {"donkey": {"sheetX": -0.32, "sheetY": 0.015, "height": 0.27, "box": [-0.47, 0.015, -0.16, 0.29]},
            "jesus": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.36, "box": [-0.1334, 0.0191, 0.1334, 0.3703]},
            "peter": {"sheetX": 0.32, "sheetY": 0.015, "height": 0.38, "box": [0.1715, 0.0193, 0.4685, 0.396]}}


def _chars():
    """kit _chars, tolerant of a cast file still being written"""
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    try:
        rc = json.load(open(p))
    except Exception:
        return prop, False
    got = {}
    for c, v in rc.get("characters", {}).items():
        if c not in rc.get("sheet", {}) or "bboxSheet" not in v:
            continue
        h = v.get("height") or prop.get(c, {}).get("height")
        got[c] = {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"], "height": h,
                  "box": v["bboxSheet"]}
    for c, v in prop.items():
        got.setdefault(c, v)
    return got, all(c in rc.get("sheet", {}) for c in prop)


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
DRAWINGS = {
    "hills":   dict(P_FRONT(), scale=2.0, cx=-0.330, y0=1.050, decorOnly=["hills"], members=["hills"]),
    "house":   dict(P_OBL(0.35, 0.5), scale=2.0, cx=-0.314, y0=0.700, members=["house", "stair"]),
    "room":    dict(P_OBL(0.0, 0.35), scale=2.3, cx=-0.375, y0=0.470, decorOnly=["mats"], members=["houseIn"]),
    "table":   dict(P_OBL(0.0, 0.7), scale=1.2, cx=-0.330, y0=0.320, members=["lowTable"]),
    "facade":  dict(P_FRONT(), scale=1.8, cx=0.030, y0=0.957, decorOnly=["facade"], members=["templeFront"]),
    "palm":    dict(P_FRONT(), scale=0.9, cx=0.290, y0=1.112, decorOnly=["leaf"], members=["palmTree"]),
    "olive":   dict(P_FRONT(), scale=0.9, cx=0.430, y0=1.125, decorOnly=["olive"], members=["oliveTree"]),
    "awnings": dict(P_OBL(0.0, 1.0), scale=1.3, cx=0.341, y0=0.995, members=["awnings"]),
    "ground":  dict(P_PLAN(), scale=3.0, cx=0.080, y0=0.675, decorOnly=["road", "paving", "ground"],
                    members=["road", "temple", "ground"]),
    "stall1":  dict(P_FRONT(), scale=0.7, cx=0.390, y0=0.830, decorOnly=["wicker"], members=["table1", "cages"]),
    "stall2":  dict(P_FRONT(), scale=0.6, cx=0.390, y0=0.690, members=["table2"]),
    "palms":   dict(P_PLAN(), scale=1.0, cx=0.135, y0=0.418, members=["palmsRoad"]),
    "supper":  dict(P_OBL(0.0, 0.6), scale=0.40, cx=0.060, y0=0.540, members=["breadLoaf", "cupTable"]),
}
TEMPLATES = {}
WOOD = ("stall1", "wood")
CONSTS = {"house": {}, "houseIn": {"plaster": ("room", "plaster")},
          "bench": {"wood": ("house", "door"), "cushion": ("awnings", "red")},
          "lowTable": {"wood": ("house", "door"), "cushion": ("awnings", "red"), "clay": ("supper", "clay"),
                       "herbs": ("palm", "leaf"), "fruit": ("palms", "coatRed")},
          "lamp1": {"clay": ("supper", "clay")}, "lamp2": {"clay": ("supper", "clay")},
          "basinStand": {"wood": ("house", "door")}, "basinJug": {"clay": ("supper", "clay"), "water": ("palms", "coatBlue")},
          "stones": {"stone": ("ground", "ground")},
          "courtWall": {"facade": ("facade", "facade")},
          "templeFront": {"facade": ("facade", "facade")},
          "awnings": {"pole": WOOD},
          "table1": {"wood": WOOD}, "cages": {"dove": ("facade", "facade")},
          "cagesOpen": {"wicker": ("stall1", "wicker")},
          "table2": {"wood": ("stall2", "wood"), "coins": ("stall2", "coins")},
          "table2Tipped": {"wood": ("stall2", "wood")},
          "coinsFloor": {"coins": ("stall2", "coins")},
          "palmTree": {"trunk": ("house", "door")}, "oliveTree": {"trunk": ("house", "door")},
          **{c[0]: {"robe": R_OF[c[5]], "cloth": R_OF[c[6]], "face": ("room", "plaster"), "eye": ("house", "door"),
                    "palm": ("palms", "palmLeaf")} for c in CROWD}}
# hidden props of the Characters role take their colour from these printed regions (CONTRACT §3, C7)
PROP_ANCHORS = {"jesus/towel": ("table", "cloth"), "peter/towel": ("table", "cloth"), "jesus/basin": ("supper", "clay"),
                "peter/jug": ("supper", "clay"), "jesus/cup": ("supper", "clay"), "jesus/bread": ("supper", "bread"),
                "peter/palm": ("palms", "palmLeaf")}
RS = [1]
ORDER = ["road", "palmsRoad", "stones", "ground", "temple", "courtWall", "templeFront", "awnings", "table1", "cages",
         "cagesOpen", "table2", "table2Tipped", "coinsFloor", "house", "houseIn", "stair", "bench", "lowTable",
         "breadLoaf", "cupTable", "lamp2", "basinStand", "basinJug", "lamp1", "palmTree", "oliveTree", "hills"] + \
    [c[0] for c in CROWD]
HIDDEN = ["palmsRoad", "table2Tipped", "coinsFloor", "cagesOpen"]


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
                       "written by pipeline/ls_jerusalem.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)
    return const


# ============================================================================================ checks
LOW, OVER = 0.012, 0.17
R_STAND, R_SEAT, R_HEAD = 0.05, 0.035, 0.035
MARGINS = {}


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
            uv = np.array([(i / n, j / n) for i in range(n + 1) for j in range(n + 1 - i)])
            a, b = uv[:, 0][None, :, None], uv[:, 1][None, :, None]
            P = A[sel][:, None] + a * (Bq[sel] - A[sel])[:, None] + b * (C[sel] - A[sel])[:, None]
            out.append(P.reshape(-1, 3))
    return np.concatenate(out)


def to_design(M, P):
    W = (np.array(M) @ np.c_[P, np.ones(len(P))].T).T[:, :3]
    return np.stack([W[:, 0], W[:, 2], -W[:, 1]], -1)


def sampled_points(objs):
    """{object: design points}: rest pose, plus the crowd at both sway extremes"""
    out = {}
    for n, ob in objs.items():
        if ob.type != 'MESH' or n in TERRAIN:
            continue
        P = to_design(ob.matrix_world, tri_points(ob))
        if n.startswith("crowd"):
            P = np.concatenate([P, sway_points(n, P)])
        out[n] = P
    return out


def check_clearance(objs):
    """CONTRACT §6 rule per mark and per straight walk, relative to the walker's floor y: nothing above y + 0.012
    within 0.05 (seated marks: 0.035, the body's half depth: SET.md); overhead parts (y + 0.17 .. head top) need 0.035;
    above the actor's head ignored. Donkey marks: a 0.30 x 0.12 box along -X (DONKEY_TIE: also along z), up to the
    rider's head (y 0.50). Walking surfaces (road, paving, ground) do not count; hidden props count everywhere
    (conservative). Seated marks ignore the bench (it is the seat) and the cushions (<= 0.02, allowed)."""
    pts = sampled_points(objs)
    hard, info = {}, {}
    MARGINS.clear()

    def zone_test(label, a, b, y, head, rad, ignore=()):
        lo_min, ov_min = 9.0, 9.0
        for name, P in pts.items():
            if name in ignore:
                continue
            X, Hh, Z = P[:, 0], P[:, 1], P[:, 2]
            ax, az = a; bx, bz = b
            dx, dz = bx - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
            t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
            d = np.hypot(X - ax - t * dx, Z - az - t * dz)
            rel = Hh - y
            lz = (rel > LOW) & (rel < OVER); oz = (rel >= OVER) & (rel < head)
            if lz.any():
                lo_min = min(lo_min, float(d[lz].min()))
            if oz.any():
                ov_min = min(ov_min, float(d[oz].min()))
            sel = (lz & (d < rad)) | (oz & (d < R_HEAD))
            if sel.any():
                hard.setdefault(label, []).append([name, round(float(d[sel].min()), 4), round(float(Hh[sel].max()), 4)])
        MARGINS[label] = [round(lo_min, 3), round(ov_min, 3)]

    def box_test(label, centres, y, alongs=("x",)):
        worst = 9.0
        for name, P in pts.items():
            X, Hh, Z = P[:, 0], P[:, 1], P[:, 2]
            m = (Hh - y > LOW) & (Hh - y < 0.50)
            if not m.any():
                continue
            Xm, Zm = X[m], Z[m]
            for cx, cz in centres:
                for al in alongs:
                    hx, hz = (0.15, 0.06) if al == "x" else (0.06, 0.15)
                    ex = np.maximum(np.abs(Xm - cx) - hx, 0); ez = np.maximum(np.abs(Zm - cz) - hz, 0)
                    gap = np.hypot(ex, ez)
                    g = float(gap.min())
                    worst = min(worst, g)
                    if g <= 0.0:
                        inside = (np.abs(Xm - cx) <= hx) & (np.abs(Zm - cz) <= hz)
                        hard.setdefault(label, []).append([name, "inside box along %s at (%.2f, %.2f)" % (al, cx, cz),
                                                           round(float(Hh[m][inside].max()), 4)])
        MARGINS[label] = round(worst, 3)
        if label in hard:                                      # one line per object
            seen, keep = set(), []
            for r in hard[label]:
                if r[0] not in seen:
                    seen.add(r[0]); keep.append(r)
            hard[label] = keep

    def kind_args(kind, actor):
        ignore = ()
        rad = R_STAND
        if kind == "seat":
            rad = R_SEAT
            ignore = ("bench", "lowTable") if False else ("bench",)
        return rad, ignore

    for label, (x, z, y, kind, actor) in MARKS.items():
        if kind in ("donkey", "donkeyAny"):
            box_test("mark " + label, [(x, z)], y, ("x", "z") if kind == "donkeyAny" else ("x",))
            continue
        rad, ignore = kind_args(kind, actor)
        head = 0.30 if kind == "seat" else (0.26 if kind == "kneel" else HEAD[actor])
        if kind == "seat":
            seat_test(label, (x, z), y, head, pts, hard)
            continue
        zone_test("mark " + label, (x, z), (x, z), y, head, rad, ignore)
        if kind == "stones8":                                  # only the stones within 0.08
            near = {}
            for name, P in pts.items():
                if name == "stones":
                    continue
                d = np.hypot(P[:, 0] - x, P[:, 2] - z)
                m = (d < 0.08) & (P[:, 1] - y > LOW)
                if m.any():
                    near[name] = round(float(d[m].min()), 4)
            if near:
                hard["mark %s (only stones within 0.08)" % label] = near
            sd = np.hypot(pts["stones"][:, 0] - x, pts["stones"][:, 2] - z)
            info["PETER_STONES"] = {"stonesNearest": round(float(sd.min()), 4),
                                    "stonesTop": round(float(pts["stones"][:, 1].max()), 4)}
    for label, ls in PATHS:
        for a, b in zip(ls[:-1], ls[1:]):
            (ax, az, ay, ka, actor), (bx, bz, by, kb, _) = MARKS[a], MARKS[b]
            lab = "walk %s %s>%s" % (label, a, b)
            if ka in ("donkey", "donkeyAny"):
                n = max(2, int(math.hypot(bx - ax, bz - az) / 0.01) + 1)
                box_test(lab, [(ax + (bx - ax) * t, az + (bz - az) * t) for t in np.linspace(0, 1, n)], ay)
            else:
                zone_test(lab, (ax, az), (bx, bz), ay, HEAD[actor], R_STAND)
    # the kneeling lane in front of the bench
    (lx0, lx1), (lz0, lz1), ltop = KNEEL_LANE
    lane = {}
    for name, P in pts.items():
        m = (P[:, 0] > lx0) & (P[:, 0] < lx1) & (P[:, 2] > lz0) & (P[:, 2] < lz1) & (P[:, 1] > ltop)
        if m.any():
            lane[name] = round(float(P[:, 1][m].max()), 4)
    if lane:
        hard["kneeling lane x -0.46..-0.38 above UPPER + 0.06"] = lane
    info["kneelingLane"] = "clear" if not lane else lane
    return hard, info


def seat_test(label, c, y, head, pts, hard):
    """seated marks: radius 0.035 (the seated body's half depth); the bench and the cushions are the seat"""
    lo_min = 9.0
    x, z = c
    for name, P in pts.items():
        if name == "bench":
            continue
        d = np.hypot(P[:, 0] - x, P[:, 2] - z)
        rel = P[:, 1] - y
        lim = LOW
        if name == "lowTable":                                    # its cushions (<= 0.02) are allowed
            lim = 0.02 if True else LOW
            m_cush = (d < 0.04) & (rel <= 0.021)
            rel = np.where(m_cush, -1.0, rel)
        m = (rel > LOW) & (rel < head)
        if m.any():
            lo_min = min(lo_min, float(d[m].min()))
        sel = m & (d < R_SEAT)
        if sel.any():
            hard.setdefault("mark " + label, []).append([name, round(float(d[sel].min()), 4),
                                                          round(float(P[:, 1][sel].max()), 4)])
    MARGINS["mark " + label] = [round(lo_min, 3), None]


# ============================================================================================ build
STATE = {}


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    root = link(bpy.data.objects.new("jerusalem", None))
    objs = {}
    objs["road"], objs["temple"], objs["ground"] = build_ground(root)
    objs["palmsRoad"] = build_palms_road(objs["road"])
    objs["stones"] = build_stones(objs["road"])
    objs["courtWall"], objs["templeFront"], objs["awnings"] = build_court(objs["temple"])
    (objs["table1"], objs["cages"], objs["cagesOpen"], objs["table2"], objs["table2Tipped"],
     objs["coinsFloor"]) = build_stalls(objs["temple"])
    objs["house"], objs["houseIn"] = build_house(root)
    objs["stair"] = build_stair(root)
    objs["bench"] = build_bench(objs["house"])
    objs["lowTable"], objs["breadLoaf"], objs["cupTable"], objs["lamp2"] = build_table(objs["house"])
    objs["basinStand"], objs["basinJug"] = build_basin(objs["house"])
    objs["lamp1"] = build_lamp1(objs["house"])
    objs["palmTree"] = build_palm(root)
    objs["oliveTree"] = build_olive(root)
    objs["hills"] = build_hills(root)
    rig, crowd = build_crowd(root)
    for ob in crowd:
        objs[ob.name] = ob
    bpy.context.view_layer.update()
    src = raster_sources(objs, {})
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("JERUSALEM_TRIS", total, json.dumps(tris))
    lay = check_layout()
    hard, info = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_MIN", json.dumps(MARGINS))
    print("CLEARANCE_INFO", json.dumps(info))
    if total > MAX_TRIS:
        print("OVER_BUDGET", total)
    STATE.update(objs=objs, root=root, rig=rig, hard=hard, info=info)
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
    write_design(objs, tris, total, hmax, const, hard, info, tex)
    STATE.update(tex=tex_img, demo=demo)
    print("BUILD_OK", GLB, total, "MISSING" if missing else "")


TITLE = {"hanzi": "服侍人的王", "pinyin": "fú shì rén de wáng", "english": "The King Who Serves", "box": 86, "gap": 60,
         "cy": 110, "label": "DoodLive · 涂上颜色，再用手机扫一扫",
         "note": "box / gap / cy from tools/story/sheet_lastsupper.py title-search plus Real Miracles' band (same 5 "
                 "boxes, not in the registry yet): worst NCC 0.412 (miracles-A4), 0.407 (daniel-A4)"}


def write_design(objs, tris, total, hmax, const, hard, info, tex):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    d.setdefault("version", 1)
    d.setdefault("artHeightUnits", ART_H)
    d.setdefault("lines", {"outerPx": 4.5, "detailPx": 3.0,
                           "note": "same weights as David & Goliath, Esther, Ruth, Jonah and Real Miracles; faces "
                                   "come from decals"})
    d.setdefault("sheet", {
        "page": [1240, 1754], "dpi": 150, "art": [120, 283, 1000, 1227],
        "markers": [[62, 225], [1178, 225], [1178, 1568], [62, 1568]], "markerSize": 64,
        "title": dict(TITLE),
        "footer": {"rect": [210, 1604, 820, 110], "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上",
                                                            "马太福音 21 · 约翰福音 13 · Matthew 21; John 13"],
                   "note": "centred on the page (x 620); line 1 at rect y + 40, line 2 at y + 76"},
        "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge; "
                    "title cy keeps the pinyin >= 6 mm from the top"})
    if d["sheet"]["title"].get("note", "").startswith("placeholder") or not TITLE["note"].startswith("placeholder"):
        d["sheet"]["title"] = dict(TITLE)
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"height": v["height"], "sheetX": v["sheetX"], "sheetY": v["sheetY"]})
        if c == "donkey":
            e["view"] = "side"
            e["note"] = ("drawn in side view, its left side: nose to -X, tail to +X (UV0 = side projection at the slot, "
                         "the far side mirrors it; CONTRACT §2); height = ear tips")
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
    anchors = {k: {"region": list(v), "uv": [round(c, 5) for c in tex[v]] if v in tex else None}
               for k, v in PROP_ANCHORS.items()}
    d["set"] = {
        "generatedBy": "pipeline/ls_jerusalem.py", "doc": "docs/lastsupper/SET.md",
        "contract": "docs/lastsupper/CONTRACT.md §6", "root": "jerusalem",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {n: [round(c, 4) for c in D(objs[n].matrix_world.translation)] for n in ORDER} |
                 {"crowd": [0.0, 0.0, 0.0]},
        "footprints": {
            "floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]],
            "house": {"x": list(HOUSE_X), "z": [FLOOR[2], HOUSE_ZF], "groundStorey": UPPER,
                      "room": {"x": list(IN_X), "z": list(IN_Z), "floor": UPPER},
                      "walls": {"left": list(WL), "right": list(WR), "back": list(WB),
                                "backTop": BACK_TOP, "sideTop": "%.2f behind z %.2f, sloping to %.2f at z %.2f" %
                                (BACK_TOP, SLOPE_Z[0], SLOPE_LOW, HOUSE_ZF)},
                      "sill": {"z": list(SILL_Z), "top": SILL_H},
                      "roofEdge": "back strip z %.3f..%.2f and side strips x 0.03 wide to z %.2f, top %.3f; no ceiling"
                                  % (WB[0], RIM_BACK_Z, SLOPE_Z[0], BACK_TOP + RIM_T),
                      "door": {"x": [DOOR[0], DOOR[1]], "top": DOOR[2]}, "window": {"x": list(UWIN[:2]), "y": list(UWIN[2:])},
                      "stair": {"x": list(STAIR_X), "z": [STAIR_Z0, LANDING_Z[0]], "top": UPPER}},
            "bench": {"x": list(BENCH_X), "z": list(BENCH_Z), "seat": BENCH_TOP},
            "lowTable": {"x": list(TABLE_X), "z": list(TABLE_Z), "top": TABLE_TOP, "breadLoaf": list(BREAD),
                         "cupTable": list(CUP), "lamp2": list(LAMP2),
                         "cushions": {k: list(v) + [CUSHION_H] for k, v in SUP.items()}},
            "basinStand": {"centre": list(STAND_C), "top": STAND_TOP, "radius": STAND_R, "jug": list(JUG)},
            "lamp1": {"shelf": list(SHELF), "at": list(LAMP1)},
            "court": {"x": list(COURT_X), "z": [FLOOR[2], COURT_Z1], "wall": {"z": list(CWALL_Z), "height": CWALL_H,
                                                                              "gate": list(GATE_X)},
                      "columns": {"x": list(COLS_X), "z": COLS_Z, "r": COL_R, "top": COL_TOP},
                      "architrave": list(ARCH), "templeFront": {"x": list(TEMPLE_X), "z": list(TEMPLE_Z),
                                                                "top": PEDIMENT[3], "door": list(TDOOR)},
                      "awnings": {"x": [list(a[:2]) for a in AWNINGS], "z": list(AWN_Z), "y": list(AWN_Y),
                                  "poles": "at both ends, z -0.50"},
                      "table1": list(T1) + [T_TOP], "table2": list(T2) + [T_TOP]},
            "road": "front strip z 0.04..0.18 from x 0.60 to -0.26 (house front), branch from the bend to the gate",
            "stones": list(STONES), "crowd": {c[0]: [c[1], c[2], c[3]] for c in CROWD},
            "palmTree": list(PALM), "oliveTree": {"trunk": list(OLIVE), "crown": list(OLIVE_CROWN)},
            "hills": {"x": list(HILLS_X), "z": list(HILLS_Z)}},
        "animations": {"crowdSway": {"node": "crowd", "meshes": [c[0] for c in CROWD], "length": SWAY_LEN, "fps": 24,
                                     "loop": True, "swayDeg": SWAY_DEG}},
        "hiddenAtStart": list(HIDDEN),
        "propAnchors": anchors,
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227",
                   "edgeOn": "faces with |n . D| < 0.22 (n in drawing space) take one clean texel of their region",
                   "namedTexels": "no-raster bits take one texel of a named (drawing, region); constUV in "
                                  "model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard,
                      "nearest": {"note": "[low zone (y+0.012..0.17), overhead (y+0.17..head top)] nearest plan distance "
                                          "(needs >= 0.05 / 0.035; seated 0.035); donkey marks: gap to the 0.30 x 0.12 box",
                                  **MARGINS},
                      "info": info},
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
    save_png(line, os.path.join(WORK, "jerusalem_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "jerusalem_drawings_demo.png"))
    tex = np.where(mask[..., None], grain, 0.0); got = mask.copy()
    for _ in range(10):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = shift(got, dy, dx); sv = shift(tex, dy, dx)
            take = sm & ~got
            tex[take] = sv[take]; got |= take
    tex[~got] = 1.0
    return tex, demo


# ============================================================================================ preview
PV_COL = {"skin": "#E9B48F", "jesusT": "#F2E8D2", "mantle": "#9A5B34", "hairJ": "#4A3020", "peterT": "#B4502F",
          "hairP": "#231A16", "johnT": "#7FB6E0", "jamesT": "#6FA552", "andrewT": "#D9A93A", "s1": "#E8843A",
          "s2": "#7E4A86", "donkey": "#9C9A96", "blanket": "#C2453A", "hairL": "#9A6B42"}
PV_SPEC = {"jesus": (0.36, "jesusT", "mantle", "hairJ"), "peter": (0.381, "peterT", "peterT", "hairP"),
           "john": (0.33, "johnT", "johnT", "hairL"), "james": (0.36, "jamesT", "jamesT", "hairP"),
           "andrew": (0.37, "andrewT", "andrewT", "hairP"), "seller1": (0.33, "s1", "s1", "hairP"),
           "seller2": (0.35, "s2", "s2", "hairP")}


def mannequins(layout):
    """preview stand-ins only (not shipped): simple figures in the demo colours at the actors' marks.
    layout: who -> (x, z, y, face (dx, dz), pose); pose '' standing, 'kneel', 'bench', 'cross' (cushion), 'ride',
    'donkey'"""
    for k, v in PV_COL.items():
        if k not in REGION_MATS:
            REGION_MATS[k] = flat_mat("pvm_" + k, v, 0.6)
    for who, (x, z, y, fc, pose) in layout.items():
        mb = MB()
        if pose == "donkey":
            sphere(mb, (0.0, 0.105, 0.0), 0.055, "donkey", seg=14, rings=8, sx=1.0, sz=2.3)
            box(mb, -0.045, 0.045, 0.125, 0.158, -0.06, 0.06, "blanket")
            for sx_ in (-0.03, 0.03):
                for sz_ in (-0.08, 0.08):
                    tube(mb, [(sx_, 0.0, sz_), (sx_, 0.09, sz_)], 0.011, "donkey", seg=8)
            sphere(mb, (0.0, 0.17, 0.15), 0.035, "donkey", seg=12, rings=8, sz=1.3)
            for s in (-1, 1):
                tube(mb, [(s * 0.015, 0.19, 0.14), (s * 0.022, 0.27, 0.13)], 0.007, "donkey", seg=6)
        elif pose == "ride":
            H, body, top, hair = PV_SPEC[who]
            s0 = 0.035
            lathe(mb, [(0.0, s0), (0.040, s0), (0.040, s0 + 0.08), (0.034, s0 + 0.16), (0.0, s0 + 0.17)], body, seg=16)
            for s in (-1, 1):
                tube(mb, [(s * 0.05, s0 + 0.01, 0.01), (s * 0.06, s0 - 0.09, 0.02)], 0.013, body, seg=8)
            sphere(mb, (0.0, s0 + 0.20, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, s0 + 0.21, -0.008), 0.026, hair, seg=10, rings=7)
        elif pose in ("bench", "cross"):
            H, body, top, hair = PV_SPEC[who]
            s0 = 0.04 if pose == "bench" else 0.012
            lathe(mb, [(0.0, s0), (0.040, s0), (0.038, s0 + 0.08), (0.032, s0 + 0.16), (0.0, s0 + 0.17)], body, seg=16)
            for s in (-1, 1):
                tube(mb, [(s * 0.018, s0 + 0.012, 0.0), (s * 0.018, s0 + 0.012, 0.055)], 0.014, body, seg=8)
                if pose == "bench":
                    tube(mb, [(s * 0.018, s0 + 0.008, 0.058), (s * 0.018, 0.006, 0.062)], 0.011, body, seg=8)
            sphere(mb, (0.0, s0 + 0.195, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, s0 + 0.205, -0.008), 0.026, hair, seg=10, rings=7)
        elif pose == "kneel":
            H, body, top, hair = PV_SPEC[who]
            lathe(mb, [(0.0, 0.0), (0.05, 0.0), (0.048, 0.03), (0.040, 0.10), (0.032, 0.16), (0.0, 0.17)], body, seg=16)
            sphere(mb, (0.0, 0.195, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, 0.205, -0.008), 0.026, hair, seg=10, rings=7)
        else:
            H, body, top, hair = PV_SPEC[who]
            lathe(mb, [(0.0, 0.0), (0.050, 0.0), (0.048, 0.02), (0.042, 0.36 * H)], body, seg=18)
            lathe(mb, [(0.042, 0.36 * H), (0.046, 0.56 * H), (0.038, 0.75 * H), (0.0, 0.78 * H)], top, seg=18)
            sphere(mb, (0.0, H - 0.04, 0.0), 0.034, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, H - 0.05), (0.036, H - 0.04), (0.035, H - 0.010), (0.0, H)], hair, C=(0, 0, -0.006), seg=16)
        ob = make_obj("pv_" + who, mb, None, origin=(0, 0, 0), smooth_angle=60)
        ob["pv"] = 1
        ob.location = B(x, y, z)
        ob.rotation_euler = (0, 0, math.atan2(fc[0], fc[1]))


def toward(a, b):
    return (b[0] - a[0], b[1] - a[1])


def mode_preview():
    if not STATE or "tex" not in STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "jerusalem_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "jerusalem_preview_sheet.png")); sheet.pack()
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
        sc.eevee.taa_render_samples = 24
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

    def phone_shot(name, tgt, dist, height, yaw):
        """StoryDirector.DriveCamera on a portrait phone (1080 x 2340): vfov 60, distance and height scaled up"""
        aspect = 1080 / 2340
        k = math.tan(math.radians(31)) / (math.tan(math.radians(30)) * aspect)
        a = math.radians(yaw)
        eye = (tgt[0] + math.sin(a) * dist * k, tgt[1] + height * k, tgt[2] + math.cos(a) * dist * k)
        shoot(name, eye, tgt, 60, (540, 1170))

    def show(names, on):
        for n in names:
            for o in [objs[n]] + list(objs[n].children_recursive):
                o.hide_render = not on

    def cast(layout):
        for o in [o for o in bpy.data.objects if o.get("pv")]:
            bpy.data.objects.remove(o, do_unlink=True)
        if layout:
            mannequins(layout)

    def act_t(who, x, z, y=0.0):                                  # the director's actor target point
        return (x, y + PV_SPEC[who][0] * 0.55, z)

    VIEWER, HOUSEDIR = (0, 1), (-1, 0)
    show(HIDDEN, False)
    # S01: the page from the phone, empty and with the procession
    cast({})
    phone = ((0.0, 1.30, 1.55), (0.0, 0.02, -0.22), 50, (720, 1280))
    shoot("jerusalem_preview_phone_set", *phone)
    road1 = {"donkey": (0.46, 0.13, 0.0, HOUSEDIR, "donkey"), "jesus": (0.46, 0.13, RIDE_Y, HOUSEDIR, "ride"),
             "peter": (0.56, 0.06, 0.0, HOUSEDIR, ""), "john": (0.56, 0.17, 0.0, HOUSEDIR, ""),
             "james": (0.63, 0.05, 0.0, HOUSEDIR, ""), "andrew": (0.63, 0.16, 0.0, HOUSEDIR, ""),
             "seller1": (0.40, -0.50, 0.0, VIEWER, ""), "seller2": (0.46, -0.37, 0.0, VIEWER, "")}
    cast(road1)
    shoot("jerusalem_preview_phone", *phone)
    # S02: follow the donkey at (0.22, 0.10), palm branches on the road
    show(["palmsRoad"], True)
    s2 = {"donkey": (0.22, 0.10, 0.0, HOUSEDIR, "donkey"), "jesus": (0.22, 0.10, RIDE_Y, HOUSEDIR, "ride"),
          "peter": (0.30, 0.04, 0.0, VIEWER, ""), "john": (0.30, 0.17, 0.0, VIEWER, ""),
          "james": (0.40, 0.04, 0.0, HOUSEDIR, ""), "andrew": (0.40, 0.17, 0.0, HOUSEDIR, "")}
    cast(s2)
    phone_shot("jerusalem_preview_s02", (0.22, 0.155, 0.10), 0.7, 0.22, -35)
    # S03: at the bend; Peter at the stones (fixed on Peter where S02 left him, (0.30, 0.04))
    s3 = {"donkey": (0.10, 0.07, 0.0, HOUSEDIR, "donkey"), "jesus": (0.10, 0.07, RIDE_Y, VIEWER, "ride"),
          "peter": (0.13, 0.18, 0.0, toward((0.13, 0.18), STONES), ""), "john": (0.24, 0.17, 0.0, HOUSEDIR, ""),
          "james": (0.30, 0.03, 0.0, HOUSEDIR, ""), "andrew": (0.34, 0.15, 0.0, HOUSEDIR, "")}
    cast(s3)
    phone_shot("jerusalem_preview_s03", act_t("peter", 0.30, 0.04), 0.5, 0.15, -25)
    show(["palmsRoad"], False)
    # S04: the court (camera on the temple node)
    s4 = {"jesus": (0.36, -0.26, 0.0, toward((0.36, -0.26), (0.46, -0.28)), ""),
          "peter": (0.08, -0.22, 0.0, (1, -0.3), ""), "john": (0.14, -0.30, 0.0, (1, 0.2), ""),
          "james": (0.05, -0.34, 0.0, (1, 0.3), ""), "seller1": (0.40, -0.50, 0.0, VIEWER, ""),
          "seller2": (0.46, -0.37, 0.0, VIEWER, ""), "donkey": (-0.04, 0.07, 0.0, VIEWER, "donkey")}
    cast(s4)
    phone_shot("jerusalem_preview_s04_crowd", (0.31, 0.08, -0.35), 0.62, 0.24, 20)
    crowd = [c[0] for c in CROWD]
    show(crowd, False)                                            # SET.md: the lead hides `crowd` from S04 on
    phone_shot("jerusalem_preview_s04", (0.31, 0.08, -0.35), 0.62, 0.24, 20)
    # S05: after the tables (tipped table, coins, open cages), fixed on Jesus at J_T2
    show(["table2"], False); show(["table2Tipped", "coinsFloor", "cagesOpen"], True); show(["cages"], False)
    s5 = dict(s4)
    s5.update({"jesus": (0.28, -0.42, 0.0, toward((0.28, -0.42), (0.40, -0.42)), ""),
               "seller2": (0.53, -0.18, 0.0, VIEWER, "")})
    cast(s5)
    phone_shot("jerusalem_preview_s05", act_t("jesus", 0.36, -0.26), 0.55, 0.20, 28)
    show(["table2", "cages"], True); show(["table2Tipped", "coinsFloor", "cagesOpen"], False)
    show(crowd, True)
    # S06: the four argue in the room, Jesus at ROOM_J
    U_ = UPPER
    s6 = {"jesus": (-0.15, -0.50, U_, (-1, 0.4), ""), "andrew": (-0.48, -0.32, U_, VIEWER, ""),
          "james": (-0.39, -0.35, U_, VIEWER, ""), "john": (-0.30, -0.33, U_, VIEWER, ""),
          "peter": (-0.21, -0.36, U_, VIEWER, "")}
    cast(s6)
    phone_shot("jerusalem_preview_s06", act_t("peter", -0.21, -0.36, U_), 0.55, 0.20, -15)
    # S07: the bench; Jesus kneels at WASH andrew (camera fixed on Jesus at STAND)
    bench = {k: (-0.54, v, U_, (1, 0), "bench") for k, v in (("andrew", -0.50), ("james", -0.42), ("john", -0.34),
                                                              ("peter", -0.27))}
    cast({**bench, "jesus": (-0.43, -0.50, U_, (-1, 0), "kneel")})
    phone_shot("jerusalem_preview_s07", act_t("jesus", -0.15, -0.46, U_), 0.60, 0.22, -30)
    show(["basinJug"], False)
    # S08: Jesus kneels in front of Peter (fixed on Peter on the bench)
    cast({**bench, "jesus": (-0.43, -0.27, U_, (-1, 0), "kneel")})
    phone_shot("jerusalem_preview_s08", act_t("peter", -0.54, -0.27, U_), 0.45, 0.15, -40)
    show(["basinJug"], True)
    # S10: the supper (fixed on Jesus at his cushion)
    sup = {k: (v[0], v[1], U_, toward(v, SUP["jesus"]) if k != "jesus" else VIEWER, "cross") for k, v in SUP.items()}
    cast(sup)
    phone_shot("jerusalem_preview_s10", act_t("jesus", *SUP["jesus"], U_), 0.50, 0.17, 0)
    # S12: Peter kneels where he sat, in front of Andrew (Andrew turned to the viewer)
    s12 = dict(sup)
    s12["peter"] = (-0.41, -0.35, U_, (0, -1), "kneel")
    s12["andrew"] = (-0.41, -0.46, U_, VIEWER, "cross")
    cast(s12)
    phone_shot("jerusalem_preview_s12", act_t("peter", -0.41, -0.35, U_), 0.50, 0.17, -40)
    # S13: the whole page at night (here in day light), the donkey by the house, supper at the table
    cast({**sup, "donkey": (-0.04, 0.07, 0.0, VIEWER, "donkey")})
    phone_shot("jerusalem_preview_s13", (0.0, 0.08, 0.0), 0.95, 0.48, 6)
    # hidden props close-up
    cast({})
    show(HIDDEN, True); show(["table2", "cages"] + crowd, False)
    shoot("jerusalem_preview_hidden", (0.62, 0.36, 0.12), (0.40, 0.04, -0.30), 46, (1200, 900))
    show(HIDDEN, False); show(["table2", "cages"] + crowd, True)
    shoot("jerusalem_preview_front", (0.0, 0.30, 2.3), (0.0, 0.18, -0.25), 22, (1600, 1000))
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "jerusalem_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["jerusalem", "road", "palmsRoad", "stones"] + ["crowd%d" % i for i in range(1, 9)] + \
    ["temple", "table1", "cages", "cagesOpen", "table2", "table2Tipped", "coinsFloor", "house", "bench", "lowTable",
     "breadLoaf", "cupTable", "basinStand", "basinJug", "lamp1", "lamp2", "palmTree", "oliveTree", "hills"]


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
    rig = bpy.data.objects.get("crowd")
    if rig is not None and "crowdSway" in bpy.data.actions and rig.type == 'ARMATURE':
        rig.animation_data_create()
        act = bpy.data.actions["crowdSway"]
        for t in list(rig.animation_data.nla_tracks):
            rig.animation_data.nla_tracks.remove(t)
        rig.animation_data.action = act
        try:
            rig.animation_data.action_slot = act.slots[0]
        except (AttributeError, IndexError):
            pass
    ob = bpy.data.objects.get("crowd3")
    if ob is not None:
        pos = []
        for f in (1, 19, 37, 55, 73):
            sc.frame_set(f); dg.update()
            me = ob.evaluated_get(dg).to_mesh()
            pos.append(np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices]))
            ob.evaluated_get(dg).to_mesh_clear()
        res["crowdSwayMax"] = round(float(max(np.abs(p - pos[0]).max() for p in pos[1:4])), 4)
        res["crowdLoopError"] = float(np.abs(pos[4] - pos[0]).max())
    sc.frame_set(1)
    ok = (not missing and tris <= MAX_TRIS and uv_bad == 0 and any("crowdSway" in a for a in acts)
          and 0.004 < res.get("crowdSwayMax", 0) < 0.05 and res.get("crowdLoopError", 1) < 1e-4)
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "actions": acts, "parents": parents, **res}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
