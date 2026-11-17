"""Blender (headless): He Is Risen! story pack, the garden -> assets/risen/model/garden.glb

One tabletop page, three places (docs/risen/CONTRACT.md §6, DESIGN.md §2).
Left back: the reddish rock hill `tombHill` (rounded top, bushes, ivy on its front face) with children `tombDoor` (the
dark chamber seen through the rounded door: reveals, walls, floor, ceiling), `cloths` (the stone ledge on the chamber's
back wall, left half, with the folded linen), `groove` (the stone track in front of the face), `tombStone` (the round
stone across the door) and `tombStoneAside` (hidden: the same stone rolled to the groove's right end, the angel's
seat), `gardenTools` (spade and watering jar leaning on the rock at the left). The face recedes behind the rolled
stone, so the seated angel's wings have room.
Front: the pale `path` (from the house door down to the front, left along the front to the garden gate, on to the
tomb's forecourt), the rest of the floor is `ground` (grass); `flowers` (two beds), `gardenWall` (low wall along
x -0.04 with the gate gap), `olive1`, `olive2`.
Right back: the two-storey `house`: ground storey closed (door, shuttered window); the upstairs room a doll's house,
front cut away to a 1 cm sill. Children: `houseIn` (inside wall faces, floor mats, lamp shelf), `roomDoor` (barred
door in the left wall's niche), `bench` (cushions), `lowTable` (bread basket; children `fishPlate` (child
`fishOnPlate`) and `lamp2`), `waterJar`, `lamp1`. `stair`: the outside stair up the house's left wall (decor).
Far back: `hills` (behind the tomb) and `cityWall` (behind the house), low reliefs at the back edge.
Contract: docs/risen/CONTRACT.md §6. Nodes, measured clearances, deviations: docs/risen/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `rs_page` = the scanned art rectangle): as The King Who Serves (pipeline/ls_jerusalem.py).
Each piece belongs to one *drawing* on the colouring sheet, a linear view a = A.P, b = B.P (depth D.P) of its drawing
model P, and u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227. P is the vertex itself except in the
`props` drawing (each prop moved / scaled into one compact still life: table with plate and fish, water jar, linen,
round stone; `tombStoneAside` has the same P as `tombStone`, so both print once), `olives` (olive2 beside olive1) and
`flowers` (every bloom is an instance of one of three template blooms printed once, the TEMPLATES method of
pipeline/ru_bethlehem.py). The tomb's door is printed from a raster-only pane (`tpl_tomb`): the chamber behind it
takes the door colour as a named texel, so it never samples the rock in front of it (LESSONS L51).

Modes (run from the repo root, one Blender at a time):
  nice -n 10 blender -b --factory-startup --python pipeline/rs_garden.py -- build     garden.glb + .blend + drawings
  nice -n 10 blender -b --factory-startup --python pipeline/rs_garden.py -- verify    re-import garden.glb, check it
  nice -n 10 blender -b --factory-startup --python pipeline/rs_garden.py -- all       build, preview, verify
  nice -n 10 blender -b --factory-startup --python pipeline/rs_garden.py -- check     build in memory, print checks
Work files go to $RS_WORK (default /tmp/risen_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector, Quaternion, Euler
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/risen/model")
GLB = os.path.join(MODEL, "garden.glb")
BLEND = os.path.join(MODEL, "garden.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/risen/design.json")
ENV = "RS_"
WORK = os.environ.get(ENV + "WORK", "/tmp/risen_set")
PAGE_MATERIAL = "rs_page"
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
STONE_TOP = 0.38                               # lead-approved 2026-11-18: the stone covers the whole 0.34 door
ANGEL_Y = STONE_TOP - 0.035                    # 0.345: the angel's hips on the flat seat (the `ride` offset)
# tomb
HILL_X = (-0.60, -0.04)
FACE_Z = -0.312                                # front face along the door and the groove (groove back edge -0.31)
DOOR = (-0.395, -0.265, 0.34)                  # x0 x1 top (rounded top: radius = half the width)
DOOR_C = (-0.33, 0.15, -0.30)                  # FX anchor (tombDoor origin)
CHAMBER = (-0.42, -0.24, -0.48, -0.32, 0.36)   # x0 x1 z0 z1 ceiling
LEDGE = (-0.412, -0.300, -0.478, -0.430, 0.075)  # back-wall ledge x0 x1 z0 z1 top (left half of the chamber)
STONE_R, STONE_T = 0.195, 0.05                 # round stone: radius at mid-thickness (top cut flat at 0.38), thickness
STONE_C = (-0.33, 0.19, -0.285)                # closed: x -0.525..-0.135, covers the door (top 0.34)
ASIDE_YAW = math.radians(40)                   # rolled right off the door and turned back into an alcove in the rock
ASIDE_LEFT = (-0.262, -0.285)                  # its left end just clears the door's right edge (-0.265)
STONE_ASIDE_C = (ASIDE_LEFT[0] + STONE_R * math.cos(ASIDE_YAW), 0.19, ASIDE_LEFT[1] - STONE_R * math.sin(ASIDE_YAW))
GROOVE = (-0.54, -0.05, -0.31, -0.26, 0.006)   # x0 -0.45 -> -0.54: under the bigger stone   # x0 x1 z0 z1 top
TOOLS = (-0.575, -0.25)                        # contract (-0.52, -0.27): under the bigger closed stone: SET.md
# garden
WALL_X, WALL_T, WALL_H = -0.04, 0.016, 0.026
WALL_Z, GATE_Z = (-0.28, 0.21), (-0.008, 0.128)   # contract gap 0.00..0.12: SET.md
OLIVE1, OLIVE2 = (0.00, -0.565), (-0.57, -0.05)   # olive1 contract (0.00, -0.50): behind the rolled stone: SET.md
BED_FRONT = (-0.60, -0.30, 0.04, 0.20)         # x0 x1 z0 z1
BED_HILL = (-0.60, -0.46, -0.29, -0.20)
FLOWERS_ORIGIN = (-0.42, 0.0, 0.11)
# house (mirror of The King Who Serves' house: here at the right back)
HOUSE_X, HOUSE_ZF = (0.06, 0.60), -0.22
WL, WR = (0.06, 0.08), (0.58, 0.60)            # side walls (0.02 thick)
WB = (-0.584, -0.580)                          # back wall: the city wall relief sits behind it at z -0.5875..-0.5845
IN_X, IN_Z = (WL[1], WR[0]), (WB[1], HOUSE_ZF)  # room interior x 0.08..0.58, z -0.58..-0.22
BACK_TOP = 0.46
SLOPE_Z, SLOPE_LOW = (-0.42, HOUSE_ZF), UPPER + 0.04   # right wall: full height behind z -0.42, down to 0.14 at the front
LEFT_TOP, LEFT_STEP = 0.40, (-0.40, -0.38)      # left wall: 0.46 behind z -0.40, 0.40 over the door part
SILL_Z, SILL_H = (-0.24, HOUSE_ZF), UPPER + 0.010
RIM_T, RIM_BACK_Z = 0.015, -0.55
GDOOR = (0.25, 0.35, 0.096)                    # ground storey door x0 x1 top (contract: door at x 0.30)
SHUTTER = (0.44, 0.53, 0.035, 0.082)
RDOOR_Z, RDOOR_TOP = (-0.34, -0.26), UPPER + 0.27   # room door in the left wall (niche through the wall)
STAIR_X, STAIR_Z0, STAIR_N = (0.022, 0.058), -0.155, 4
LANDING_Z = (-0.26, -0.345)
BENCH_X, BENCH_Z, BENCH_TOP = (0.14, 0.50), (-0.56, -0.51), UPPER + 0.04
TABLE_X, TABLE_Z, TABLE_TOP = (0.462, 0.56), (-0.36, -0.26), UPPER + 0.05   # x0 0.46 -> 0.462: SET.md
PLATE, PLATE_R = (0.50, -0.31), 0.030
BASKET = (0.537, -0.279)
LAMP2 = (0.542, -0.344)                        # contract (0.53, -0.33): moved off the plate: SET.md
JAR, JAR_TOP = (0.12, -0.53), UPPER + 0.12
LAMP1, SHELF = (0.32, -0.570), (0.300, 0.340, UPPER + 0.22)
# backdrop
HILLS_X, CITY_X, BACK_Z = (-0.60, 0.06), (0.06, 0.60), (-0.5875, -0.5845)


# ============================================================================================ marks and paths
G, U = 0.0, UPPER
HEAD = {"jesus": 0.365, "mary": 0.345, "joanna": 0.335, "peter": 0.385, "john": 0.335, "thomas": 0.365,
        "angel": 0.46}
# label: (x, z, floor y, kind, actor, ignored nodes)   kinds: stand, seat (bench: radius 0.035), stone (the angel's seat)
OPEN = ("tombStone",)                          # marks used after the stone has rolled away (S04 on)
MARKS = {
    "MARY_T": (-0.30, -0.13, G, "stand", "mary", ()), "JOANNA_T": (-0.42, -0.12, G, "stand", "joanna", ()),
    "NEAR_TOMB": (-0.26, -0.10, G, "stand", "mary", ()),
    "MARY_DOOR": (-0.30, -0.22, G, "stand", "mary", OPEN), "JOANNA_DOOR": (-0.40, -0.21, G, "stand", "joanna", OPEN),
    "TOMB_DOOR": (-0.33, -0.24, G, "stand", "peter", OPEN), "john -0.40,-0.22": (-0.40, -0.22, G, "stand", "john", OPEN),
    "peter -0.22,-0.14": (-0.22, -0.14, G, "stand", "peter", OPEN),
    "MARY_CRY": (-0.24, -0.05, G, "stand", "mary", OPEN), "JESUS_G": (-0.10, -0.12, G, "stand", "jesus", OPEN),
    "MARY_MEET": (-0.205, -0.075, G, "stand", "mary", OPEN),
    "mary -0.10,0.02": (-0.10, 0.02, G, "stand", "mary", ()), "joanna -0.18,0.06": (-0.18, 0.06, G, "stand", "joanna", ()),
    "joanna -0.18,0.08": (-0.18, 0.08, G, "stand", "joanna", OPEN),
    "S12 jesus -0.12,-0.04": (-0.12, -0.04, G, "stand", "jesus", OPEN),
    "S12 mary -0.24,0.02": (-0.24, 0.02, G, "stand", "mary", OPEN),
    "S12 peter 0.04,0.04": (0.04, 0.04, G, "stand", "peter", OPEN),
    "S12 john 0.14,0.08": (0.14, 0.08, G, "stand", "john", OPEN),
    "S12 thomas 0.06,-0.10": (0.06, -0.10, G, "stand", "thomas", OPEN),
    "STONE_ASIDE": (round(STONE_ASIDE_C[0], 4), round(STONE_ASIDE_C[2], 4), ANGEL_Y, "stone", "angel", OPEN),
    "WOMEN_START mary": (0.36, 0.10, G, "stand", "mary", ()), "WOMEN_START joanna": (0.44, 0.12, G, "stand", "joanna", ()),
    "PATH_R": (0.22, 0.08, G, "stand", "mary", ()), "joanna 0.30,0.11": (0.30, 0.11, G, "stand", "joanna", ()),
    "PATH_L": (0.04, 0.08, G, "stand", "mary", ()), "joanna 0.06,0.11": (0.06, 0.11, G, "stand", "joanna", ()),
    "GATE": (-0.06, 0.06, G, "stand", "peter", ()),
    "HOUSE_DOOR": (0.30, -0.15, G, "stand", "john", OPEN), "PETER_DOOR": (0.38, -0.13, G, "stand", "peter", OPEN),
    "mary -0.10,0.04": (-0.10, 0.04, G, "stand", "mary", OPEN), "mary 0.30,0.10": (0.30, 0.10, G, "stand", "mary", OPEN),
    "ROOM_DOOR": (0.12, -0.30, U, "stand", "mary", ()), "MARY_ROOM": (0.14, -0.33, U, "stand", "mary", ()),
    "BENCH thomas": (0.20, -0.49, U, "seat", "thomas", ()), "BENCH john": (0.30, -0.49, U, "seat", "john", ()),
    "BENCH peter": (0.40, -0.49, U, "seat", "peter", ()),
    "STAND john": (0.20, -0.45, U, "stand", "john", ()), "STAND peter": (0.40, -0.45, U, "stand", "peter", ()),
    "ROOM_J": (0.30, -0.30, U, "stand", "jesus", ()), "TABLE_J": (0.41, -0.30, U, "stand", "jesus", ()),
    "THOMAS_TOUCH": (0.19, -0.30, U, "stand", "thomas", ()),
}
PATHS = [   # story.py straight walks between consecutive marks of one actor (label, [mark labels], ignored): every move
    ("S01 mary", ["MARY_T", "mary -0.10,0.02"], ()),
    ("S01 joanna", ["JOANNA_T", "joanna -0.18,0.06"], ()),
    ("S02 mary", ["WOMEN_START mary", "PATH_R", "PATH_L", "GATE", "NEAR_TOMB"], ()),
    ("S02 joanna", ["WOMEN_START joanna", "joanna 0.30,0.11", "joanna 0.06,0.11", "GATE", "JOANNA_T"], ()),
    ("S04 mary", ["MARY_T", "MARY_DOOR", "mary -0.10,0.02"], OPEN),
    ("S04 joanna", ["JOANNA_T", "JOANNA_DOOR", "joanna -0.18,0.08"], OPEN),
    ("S05 mary", ["ROOM_DOOR", "MARY_ROOM"], ()),
    ("S06 john", ["HOUSE_DOOR", "PATH_R", "PATH_L", "GATE", "TOMB_DOOR"], OPEN),
    ("S06 peter", ["PETER_DOOR", "PATH_R", "PATH_L", "GATE", "peter -0.22,-0.14"], OPEN),
    ("S07 john", ["TOMB_DOOR", "john -0.40,-0.22"], OPEN),
    ("S07 peter", ["peter -0.22,-0.14", "TOMB_DOOR"], OPEN),
    ("S09 mary", ["MARY_CRY", "MARY_MEET", "mary -0.10,0.04", "PATH_L", "mary 0.30,0.10"], OPEN),
    ("S10 jesus", ["ROOM_J", "TABLE_J"], ()),
]
TERRAIN = {"path", "ground"}                   # walking surfaces
HARD_PTS = [(v[0], v[1]) for v in MARKS.values()]
HARD_SEGS = [((MARKS[a][0], MARKS[a][1]), (MARKS[b][0], MARKS[b][1])) for _, ls, _ in PATHS for a, b in zip(ls[:-1], ls[1:])]
SOFT_SEGS = []

# demo colouring (DESIGN.md §3)
COLOURS = {
    "rock": "#C9946A", "door": "#4A3440", "leaf": "#5E9A48", "stone": "#B9AFA2", "linen": "#F5F1E6",
    "grass": "#8DBB5A", "path": "#E8D5A8", "lily": "#FFFFFF", "poppy": "#D9483A", "daisy": "#F2C94C",
    "olive": "#8AA06A", "trunk": "#7A6650", "limestone": "#E9D6A8", "plaster": "#EBD2A6", "cushion": "#9C3A3A",
    "mats": "#D8BE8E", "wood": "#8A5A3B", "clay": "#C46A3E", "fish": "#C98A4A", "bread": "#D9A95E",
    "cityStone": "#C9B285", "hills": "#8E9E62", "metal": "#9A9590",
}
REGION_HEX = {}


# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model), faces with region, smooth flag, a
    no-raster flag (scattered bits that sample a named texel) (as The King Who Serves)"""

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

    def remap(self, c, at, k=1.0, i0=0):
        """drawing model of vertices i0..: P = at + k * (V - c) (a prop moved / scaled into a still-life drawing)"""
        for i in range(i0, len(self.V)):
            x, h, z = self.V[i]
            self.P[i] = (at[0] + k * (x - c[0]), at[1] + k * (h - c[1]), at[2] + k * (z - c[2]))


REGION_MATS = {}
P_OF, NR_OF, REG_OF = {}, {}, {}
DECOR = {}                    # drawing -> [(p0, p1)] single drawn lines in drawing-model coords


def quad(mb, pts, reg, out, smooth=False):
    mb.fo([mb.v(*p) for p in pts], reg, out, smooth)


def wall(mb_out, mb_in, x0, x1, h0, h1, z0, z1, inner, skip=(), reg="limestone", ireg="plaster"):
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


def lamp_mesh(mb, x, h, z, reg="clay", toward=1):
    """a small clay oil lamp, nozzle toward +x (toward=1) or -x; returns the wick point"""
    lathe(mb, [(0.0, 0.0), (0.008, 0.0), (0.011, 0.004), (0.010, 0.008), (0.004, 0.010), (0.0, 0.010)], reg,
          C=(x, h, z), seg=12, sx=1.45)
    s = toward
    tube(mb, [(x + s * 0.010, h + 0.006, z), (x + s * 0.019, h + 0.008, z)], 0.0032, reg, seg=6)
    return (x + s * 0.019, h + 0.011, z)


def relief_face(mb, poly, zfun, reg, step=0.012, smooth=False):
    """a front-facing surface over the (x, h) polygon (holes as notches in the outline), each vertex at z = zfun(x):
    constrained triangulation of the resampled outline plus an interior grid, so a curved z stays smooth"""
    pts = np.array(poly, float)
    bnd = _resample(pts, step)
    lo, hi = pts.min(0), pts.max(0)
    G_ = []
    for j, y in enumerate(np.arange(lo[1] + step * 0.5, hi[1], step * 0.87)):
        for x in np.arange(lo[0] + (j % 2) * step * 0.5 + step * 0.25, hi[0], step):
            G_.append((x, y))
    G_ = np.array(G_) if G_ else np.zeros((0, 2))
    if len(G_):
        G_ = G_[_inside(G_, pts)]
        G_ = G_[_edge_dist(G_, pts) > step * 0.45]
    K = len(bnd)
    verts = [Vector((float(x), float(y))) for x, y in bnd] + [Vector((float(x), float(y))) for x, y in G_]
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, [(i, (i + 1) % K) for i in range(K)], [list(range(K))], 1, 1e-8, True)
    V = np.array([(v.x, v.y) for v in vs])
    T = [tuple(f) for f in fs if len(f) == 3]
    cen = np.array([V[list(t)].mean(0) for t in T])
    T = [t for t, k in zip(T, _inside(cen, pts)) if k]
    ids = [mb.v(x, y, zfun(x)) for x, y in V]
    for t in T:
        mb.fo([ids[i] for i in t], reg, (0, 0, 1), smooth)


# ============================================================================================ the tomb
def smooth01(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def aside_z(x):
    """plan line of the rolled stone's front face"""
    return ASIDE_LEFT[1] - (x - ASIDE_LEFT[0]) * math.tan(ASIDE_YAW)


def face_z(x):
    """plan line of the rock's front face: flat along the door, then an alcove 0.04 behind the rolled stone's back"""
    if x <= -0.25:
        return FACE_Z
    back = aside_z(x) - STONE_T / math.cos(ASIDE_YAW) - 0.04
    return FACE_Z + (min(FACE_Z, back) - FACE_Z) * smooth01((x + 0.25) / 0.03)


def hill_f(x):
    """1 over the tomb, easing to 0 at the hill's right end (the shoulder runs down to the ground)"""
    return 1.0 - smooth01((x + 0.22) / (HILL_X[1] + 0.22))


def face_top(x):
    h = 0.375 - 0.045 * smooth01((-0.44 - x) / 0.16)
    return max(0.0, h * hill_f(x))


def crest(x):
    return 0.395 - 0.035 * smooth01((-0.46 - x) / 0.14)


def dome_h(x, t):
    """height of the hill top at depth fraction t (0 = face top, 1 = back edge)"""
    f = hill_f(x)
    hf, ht, hb = face_top(x), crest(x) * f, 0.30 * f
    tc = 0.40
    if t <= tc:
        h = hf + (ht - hf) * math.sin(t / tc * math.pi / 2)
    else:
        h = ht - (ht - hb) * ((t - tc) / (1 - tc)) ** 2
    return h + 0.004 * f * (nz(x * 9, t * 7) - 0.5) * (1 if 0.02 < t < 0.98 else 0)


def door_outline(n_arch=12):
    x0, x1, top = DOOR
    r = (x1 - x0) / 2; cx = (x0 + x1) / 2; spring = top - r
    pts = [(x0, 0.0), (x0, spring)]
    for k in range(1, n_arch):
        a = math.pi - math.pi * k / n_arch
        pts.append((cx + r * math.cos(a), spring + r * math.sin(a)))
    pts += [(x1, spring), (x1, 0.0)]
    return pts


def build_tomb(root):
    """`tombHill` (front face with the door notch, rounded top, left end cap, bushes, ivy) with children `tombDoor`
    (chamber, door reveals) and `cloths` (ledge + linen)"""
    mb = MB()
    xs = list(np.linspace(HILL_X[0], HILL_X[1], 30))
    # front face: outline with the door notch, top edge = face_top(x)
    door = door_outline()
    poly = [(HILL_X[0], 0.0)] + door + [(HILL_X[1], 0.0)] + [(x, max(face_top(x), 0.0)) for x in xs[::-1]][1:-1] + \
        [(HILL_X[0], face_top(HILL_X[0]))]
    relief_face(mb, poly, face_z, "rock", step=0.014)
    # rounded top: a loft of sections from the face top back to the back edge
    nt = 12
    grid = []
    for x in xs:
        zf = face_z(x)
        row = []
        for j in range(nt + 1):
            t = j / nt
            z = zf + (FLOOR[2] - zf) * t
            h = dome_h(x, t)
            if j == 0:
                h, z = h - 0.004, z - 0.002                   # tucked under the face's top edge
            row.append(mb.v(x, max(h, 0.0005), z))
        grid.append(row)
    for i in range(len(xs) - 1):
        for j in range(nt):
            mb.fo([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], "rock", (0, 1, 0.3), True)
    # left end cap at the page edge
    x = HILL_X[0]
    sec = [(FACE_Z, 0.0), (FACE_Z, face_top(x))] + \
        [(FACE_Z + (FLOOR[2] - FACE_Z) * (j / nt), dome_h(x, j / nt)) for j in range(1, nt + 1)] + [(FLOOR[2], 0.0)]
    tris = tessellate_polygon([[Vector((z, h, 0)) for z, h in sec]])
    ids = [mb.v(x, h, z) for z, h in sec]
    for t in tris:
        mb.fo([ids[i] for i in t], "rock", (-1, 0, 0))
    # bushes on the top (tops <= 0.42) and ivy on the face
    for k, (bx, bt, r) in enumerate(((-0.52, 0.32, 0.030), (-0.40, 0.45, 0.026), (-0.215, 0.36, 0.024))):
        z = face_z(bx) + (FLOOR[2] - face_z(bx)) * bt
        h = dome_h(bx, bt)
        lumpy(mb, (bx, h - r * 0.2, z), r, "leaf", seg=12, rings=7, sh=0.75, amp=0.16, seed=k + 2,
              flat_bottom=h - 0.006)
    for k, (cx, cy, rx, ry) in enumerate(((-0.515, 0.255, 0.042, 0.050),)):
        ivy = blob_poly(cx, cy, rx, 11 + k, n=18, amp=0.18)
        ivy[:, 1] = cy + (ivy[:, 1] - cy) * (ry / (rx * 0.8))
        puff(mb, [tuple(p) for p in ivy], face_z(cx) + 0.004, 0.0025, "leaf", rad=0.008, edge=0.4, step=0.006)
    # drawn lines on the rock (the region is decorOnly: glancing faces would otherwise print as hatching)
    dec = DECOR.setdefault("tomb", [])
    xs2 = np.linspace(HILL_X[0] + 0.004, -0.07, 60)
    for a, b in zip(xs2[:-1], xs2[1:]):                           # the face's top edge
        dec.append(((a, face_top(a), face_z(a) + 0.001), (b, face_top(b), face_z(b) + 0.001)))
    for t in (0.45,):                                             # a rock stratum across the top
        xs3 = np.linspace(-0.58, -0.20, 30)
        for a, b in zip(xs3[:-1], xs3[1:]):
            za = face_z(a) + (FLOOR[2] - face_z(a)) * t; zb = face_z(b) + (FLOOR[2] - face_z(b)) * t
            dec.append(((a, dome_h(a, t) + 0.002, za), (b, dome_h(b, t) + 0.002, zb)))
    for crack in (((-0.455, 0.02), (-0.44, 0.07), (-0.452, 0.12)), ((-0.56, 0.10), (-0.545, 0.15)),
                  ((-0.255, 0.04), (-0.245, 0.10), (-0.25, 0.14))):
        for a, b in zip(crack[:-1], crack[1:]):
            dec.append(((a[0], a[1], face_z(a[0]) + 0.001), (b[0], b[1], face_z(b[0]) + 0.001)))
    hill = make_obj("tombHill", mb, root, origin=(-0.28, 0.04, -0.24), smooth_angle=38)
    # tombDoor: reveals of the opening and the chamber (named texel: the printed door pane)
    dm = MB(); dm.nr = True
    x0, x1, z0, z1, ceil = CHAMBER
    zr = FACE_Z
    dpts = door_outline()
    for a, b in zip(dpts[:-1], dpts[1:]):                         # reveal from the face back to the chamber front
        quad(dm, [(a[0], a[1], zr + 0.001), (b[0], b[1], zr + 0.001), (b[0], b[1], z1), (a[0], a[1], z1)], "door",
             (((a[1] + b[1]) / 2 - 0.1) * 0 + (DOOR_C[0] - (a[0] + b[0]) / 2), DOOR_C[1] - (a[1] + b[1]) / 2, 0))
    quad(dm, [(x0, 0.0045, z0), (x1, 0.0045, z0), (x1, 0.0045, z1), (x0, 0.0045, z1)], "door", UP)       # floor
    quad(dm, [(x0, ceil, z0), (x1, ceil, z0), (x1, ceil, z1), (x0, ceil, z1)], "door", (0, -1, 0))       # ceiling
    quad(dm, [(x0, 0, z0), (x1, 0, z0), (x1, ceil, z0), (x0, ceil, z0)], "door", (0, 0, 1))              # back
    quad(dm, [(x0, 0, z0), (x0, ceil, z0), (x0, ceil, z1), (x0, 0, z1)], "door", (1, 0, 0))              # left
    quad(dm, [(x1, 0, z0), (x1, ceil, z0), (x1, ceil, z1), (x1, 0, z1)], "door", (-1, 0, 0))             # right
    # chamber front wall (inside face, around the door) so nothing shows the hollow hill from inside
    fpoly = [(x0, 0.0)] + dpts + [(x1, 0.0), (x1, ceil), (x0, ceil)]
    tri = tessellate_polygon([[Vector((a, b, 0)) for a, b in fpoly]])
    fid = [dm.v(a, b, z1) for a, b in fpoly]
    for t in tri:
        dm.fo([fid[i] for i in t], "door", (0, 0, -1))
    dm.nr = False
    tdoor = make_obj("tombDoor", dm, hill, origin=DOOR_C, smooth_angle=30)
    # cloths: the ledge (dark rock, named texel) and the folded linen (printed in `props`)
    cm = MB()
    lx0, lx1, lz0, lz1, ltop = LEDGE
    cm.nr = True
    box(cm, lx0, lx1, 0.0, ltop, lz0, lz1, "ledge", skip=("bottom", "back"))
    cm.nr = False
    i0 = len(cm.V)
    flat_cushion(cm, -0.377, -0.455, 0.030, 0.019, ltop, 0.0055, "linen", n=6.0, rad=0.006, step=0.004)
    flat_cushion(cm, -0.379, -0.456, 0.026, 0.016, ltop + 0.011, 0.005, "linen", n=6.0, rad=0.006, step=0.004)
    tube(cm, [(-0.338, ltop + 0.007, -0.462), (-0.322, ltop + 0.007, -0.452)], 0.0075, "linen", seg=10)   # head cloth
    cm.remap((-0.36, ltop, -0.455), PROPS_AT["cloths"], PROPS_K["cloths"], i0)
    cl = make_obj("cloths", cm, hill, origin=(-0.356, 0.0, -0.454), smooth_angle=50)
    return hill, tdoor, cl


def stone_mesh(mb, c):
    """the round stone: a disc on its edge in the groove (rolls along x), rim rounded, a shallow dish on the front"""
    R, T = STONE_R, STONE_T / 2
    prof = [(0.0, -T), (R * 0.84, -T), (R * 0.95, -T * 0.72), (R, 0.0), (R * 0.95, T * 0.72), (R * 0.84, T),
            (R * 0.55, T * 0.86), (0.0, T * 0.92)]
    i0 = len(mb.V)
    lathe(mb, prof, "stone", C=c, A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=48, smooth=True)
    for i in range(i0, len(mb.V)):                                # the flat seat on top (~0.10 wide)
        x, h, z = mb.V[i]
        if h > STONE_TOP - 0.003:
            mb.V[i] = (x, STONE_TOP, z); mb.P[i] = mb.V[i]


def build_stones(hill):
    """`tombStone` (across the door) and `tombStoneAside` (hidden: rolled to the groove's right end); same drawing
    model (props), so the stone prints once"""
    out = []
    for name, c in (("tombStone", STONE_C), ("tombStoneAside", STONE_ASIDE_C)):
        mb = MB()
        stone_mesh(mb, c)
        mb.remap(c, PROPS_AT["stone"], PROPS_K["stone"])
        if name == "tombStoneAside":                              # turn about its centre (P stays the closed stone's)
            cs, sn = math.cos(ASIDE_YAW), math.sin(ASIDE_YAW)
            mb.V = [(c[0] + (x - c[0]) * cs + (z - c[2]) * sn, h, c[2] - (x - c[0]) * sn + (z - c[2]) * cs)
                    for x, h, z in mb.V]
        out.append(make_obj(name, mb, hill, origin=c, smooth_angle=40))
    return out


def build_groove(hill):
    """`groove`: the shallow stone track in front of the face, x -0.45..-0.05, z -0.31..-0.26, top 0.006"""
    x0, x1, z0, z1, top = GROOVE
    mb = MB(); mb.nr = True
    box(mb, x0, x1, 0.0, top * 0.6, z0, z1, "stone", skip=("bottom",))
    for za, zb in ((z0, z0 + 0.010), (z1 - 0.010, z1)):                  # two rims, the channel between them
        box(mb, x0, x1, top * 0.6, top, za, zb, "stone", skip=("bottom",))
    mb.nr = False
    return make_obj("groove", mb, hill, origin=((x0 + x1) / 2, 0.0, (z0 + z1) / 2), smooth_angle=30)


def build_tools(hill):
    """`gardenTools`: a spade and a watering jar leaning on the rock at (-0.52, -0.27), top <= 0.16"""
    mb = MB(); mb.nr = True
    sx, sz = TOOLS
    base, top = (sx - 0.012, 0.0, sz + 0.006), (sx - 0.006, 0.156, FACE_Z + 0.006)
    tube(mb, [(base[0], 0.035, base[2] - 0.005), top], 0.0035, "wood", seg=6)
    tube(mb, [(top[0] - 0.010, top[1] - 0.004, top[2]), (top[0] + 0.010, top[1] - 0.004, top[2])], 0.003, "wood", seg=6)
    blade_pts = [(base[0] - 0.011, 0.0, base[2]), (base[0] + 0.011, 0.0, base[2]),
                 (base[0] + 0.011, 0.038, base[2] - 0.006), (base[0] - 0.011, 0.038, base[2] - 0.006)]
    quad(mb, blade_pts, "metal", (0, 0.1, 1)); quad(mb, blade_pts, "metal", (0, -0.1, -1))
    jx, jz = sx + 0.035, sz - 0.002
    lathe(mb, [(0.0, 0.0), (0.016, 0.0), (0.020, 0.018), (0.017, 0.036), (0.008, 0.046), (0.009, 0.052), (0.0, 0.052)],
          "clay", C=(jx, 0.0, jz), seg=12)
    tube(mb, [(jx + 0.016, 0.026, jz), (jx + 0.036, 0.046, jz + 0.004)], 0.0035, "clay", seg=6)
    tube(mb, [(jx - 0.012, 0.044, jz), (jx - 0.004, 0.064, jz), (jx + 0.006, 0.048, jz)], 0.0025, "clay", seg=6)
    mb.nr = False
    return make_obj("gardenTools", mb, hill, origin=(sx, 0.0, sz), smooth_angle=50)


# ============================================================================================ house
def right_wall_poly():
    return [(WB[0], UPPER), (HOUSE_ZF, UPPER), (HOUSE_ZF, SLOPE_LOW), (SLOPE_Z[0], BACK_TOP), (WB[0], BACK_TOP)]


def build_house(root):
    """`house` (outside: ground storey, side and back walls, roof edge, sill, door, shutters) with child `houseIn`
    (inside wall faces, floor mats, lamp shelf); the left wall carries the room door's niche"""
    ex, inn = MB(), MB()
    box(ex, HOUSE_X[0], HOUSE_X[1], 0.0, UPPER, WB[0], HOUSE_ZF, "limestone", skip=("top", "bottom"))
    box(ex, GDOOR[0], GDOOR[1], 0.0, GDOOR[2], HOUSE_ZF, HOUSE_ZF + 0.003, "wood", skip=("bottom", "back"))
    s0, s1, s2, s3 = SHUTTER
    box(ex, s0, s1, s2, s3, HOUSE_ZF, HOUSE_ZF + 0.003, "wood", skip=("back",))
    # right wall: as The King Who Serves (inner face to the room)
    prism_x(ex, WR[0], WR[1], right_wall_poly(), "limestone", end_mbs=(inn, ex), end_regs=("plaster", "limestone"),
            skip_edges=(0,))
    # left wall in three pieces around the door niche (z -0.34..-0.26, up to RDOOR_TOP)
    dz0, dz1 = RDOOR_Z; dt = RDOOR_TOP
    sz0, sz1 = LEFT_STEP
    a = [(WB[0], UPPER), (dz0, UPPER), (dz0, dt), (dz0, LEFT_TOP), (sz1, LEFT_TOP), (sz0, BACK_TOP), (WB[0], BACK_TOP)]
    b = [(dz0, dt), (dz1, dt), (dz1, LEFT_TOP), (dz0, LEFT_TOP)]
    c = [(dz1, UPPER), (HOUSE_ZF, UPPER), (HOUSE_ZF, SLOPE_LOW), (SILL_Z[0], LEFT_TOP), (dz1, LEFT_TOP), (dz1, dt)]
    for poly, skip in ((a, (0, 2)), (b, (1, 3)), (c, (0, 4))):
        prism_x(ex, WL[0], WL[1], poly, "limestone", end_mbs=(ex, inn), end_regs=("limestone", "plaster"),
                skip_edges=skip)
    # back wall between the side walls
    wall(ex, inn, IN_X[0], IN_X[1], UPPER, BACK_TOP, WB[0], WB[1], "front", skip=("left", "right"))
    # flat roof edge: the back strip and the side strips over the full-height parts
    box(ex, HOUSE_X[0], HOUSE_X[1], BACK_TOP, BACK_TOP + RIM_T, WB[0], RIM_BACK_Z, "limestone")
    box(ex, HOUSE_X[0], HOUSE_X[0] + 0.03, BACK_TOP, BACK_TOP + RIM_T, RIM_BACK_Z, sz0, "limestone", skip=("back",))
    box(ex, HOUSE_X[1] - 0.03, HOUSE_X[1], BACK_TOP, BACK_TOP + RIM_T, RIM_BACK_Z, SLOPE_Z[0], "limestone", skip=("back",))
    # the cut-away front: a 1 cm sill
    box(ex, IN_X[0], IN_X[1], UPPER, SILL_H, SILL_Z[0], SILL_Z[1], "limestone", skip=("bottom", "left", "right"))
    # inside: floor mats and the lamp shelf
    quad(inn, [(IN_X[0], UPPER + 0.0003, IN_Z[0]), (IN_X[1], UPPER + 0.0003, IN_Z[0]),
               (IN_X[1], UPPER + 0.0003, SILL_Z[0]), (IN_X[0], UPPER + 0.0003, SILL_Z[0])], "mats", UP)
    dec = DECOR.setdefault("room", [])
    for x in (0.18, 0.28, 0.38, 0.48):
        dec.append(((x, UPPER + 0.0006, IN_Z[0] + 0.004), (x, UPPER + 0.0006, SILL_Z[0] - 0.002)))
    inn.nr = True
    box(inn, SHELF[0], SHELF[1], SHELF[2] - 0.006, SHELF[2], WB[1], WB[1] + 0.016, "plaster", skip=("back",))
    inn.nr = False
    house = make_obj("house", ex, root, origin=(0.33, UPPER, -0.38), smooth_angle=30)
    house_in = make_obj("houseIn", inn, house, origin=(0.33, UPPER, -0.38), smooth_angle=40)
    return house, house_in


def build_room_door(house):
    """`roomDoor`: the closed door at the outer face of the left wall's niche, a wooden bar across it inside"""
    mb = MB(); mb.nr = True
    dz0, dz1 = RDOOR_Z
    box(mb, WL[0], WL[0] + 0.004, UPPER, RDOOR_TOP, dz0, dz1, "wood", skip=("bottom",))
    box(mb, WL[0] + 0.004, WL[0] + 0.008, UPPER + 0.120, UPPER + 0.134, dz0, dz1, "wood")
    mb.nr = False
    return make_obj("roomDoor", mb, house, origin=(WL[0], UPPER, (dz0 + dz1) / 2), smooth_angle=30)


def build_stair(root):
    """the outside stair up the house's left wall (decor): four steps from z -0.155 back to a landing at y 0.10
    in front of the room door"""
    mb = MB()
    x0, x1 = STAIR_X
    d = (LANDING_Z[0] - STAIR_Z0) / STAIR_N
    for i in range(STAIR_N):
        zf = STAIR_Z0 + i * d
        box(mb, x0, x1, 0.0, 0.02 * (i + 1), zf + d, zf, "limestone", skip=("bottom", "right"))
    box(mb, x0, x1, 0.0, UPPER, LANDING_Z[1], LANDING_Z[0], "limestone", skip=("bottom", "right"))
    return make_obj("stair", mb, root, origin=(sum(STAIR_X) / 2, 0.0, (STAIR_Z0 + LANDING_Z[1]) / 2), smooth_angle=30)


def build_bench(house):
    """`bench` along the back wall: x 0.14..0.50, z -0.56..-0.51, three cushions; seat top UPPER + 0.04"""
    mb = MB(); mb.nr = True
    box(mb, BENCH_X[0], BENCH_X[1], UPPER, BENCH_TOP - 0.012, BENCH_Z[0], BENCH_Z[1], "wood", skip=("bottom", "back"))
    xs = np.linspace(BENCH_X[0], BENCH_X[1], 4)
    for xa, xb in zip(xs[:-1], xs[1:]):
        flat_cushion(mb, (xa + xb) / 2, (BENCH_Z[0] + BENCH_Z[1]) / 2 + 0.001, (xb - xa) / 2 - 0.003,
                     (BENCH_Z[1] - BENCH_Z[0]) / 2 - 0.002, BENCH_TOP - 0.012, 0.006, "cushion", n=5.0)
    mb.nr = False
    return make_obj("bench", mb, house, origin=((BENCH_X[0] + BENCH_X[1]) / 2, UPPER, (BENCH_Z[0] + BENCH_Z[1]) / 2),
                    smooth_angle=50)


def build_table(house):
    """`lowTable` (top, four legs, bread basket) with children `fishPlate` (child `fishOnPlate`: two grilled fish)
    and `lamp2`"""
    at, k = PROPS_AT["table"], PROPS_K["table"]
    c = ((TABLE_X[0] + TABLE_X[1]) / 2, TABLE_TOP, (TABLE_Z[0] + TABLE_Z[1]) / 2)
    mb = MB()
    x0, x1 = TABLE_X; z0, z1 = TABLE_Z
    box(mb, x0, x1, TABLE_TOP - 0.012, TABLE_TOP, z0, z1, "wood", skip=("bottom",))
    mb.nr = True
    for x in (x0 + 0.010, x1 - 0.010):
        for z in (z0 + 0.010, z1 - 0.010):
            tube(mb, [(x, UPPER, z), (x, TABLE_TOP - 0.012, z)], 0.0045, "wood", seg=6)
    mb.nr = False
    bx, bz = BASKET
    lathe(mb, [(0.0, 0.0), (0.012, 0.0), (0.0170, 0.009), (0.0160, 0.013), (0.0110, 0.0165), (0.0, 0.0175)], "bread",
          C=(bx, TABLE_TOP, bz), seg=18)                       # a basket heaped with bread: one smooth shape
    mb.remap(c, at, k)
    table = make_obj("lowTable", mb, house, origin=(c[0], UPPER, c[2]), smooth_angle=45)
    px, pz = PLATE
    pm = MB()
    lathe(pm, [(0.0, 0.0), (PLATE_R * 0.55, 0.0), (PLATE_R * 0.62, 0.0025), (PLATE_R, 0.0060), (PLATE_R * 0.93, 0.0062),
               (PLATE_R * 0.60, 0.0030), (0.0, 0.0030)], "clay", C=(px, TABLE_TOP, pz), seg=24)
    pm.remap(c, at, k)
    plate = make_obj("fishPlate", pm, table, origin=(px, TABLE_TOP, pz), smooth_angle=50)
    fm = MB()
    for kk, (dx, dz, rot) in enumerate(((-0.0119, -0.004, math.pi / 2 + 0.05), (0.0119, -0.004, math.pi / 2 - 0.05))):
        # side by side, heads to the back: on the oblique sheet drawing each fish keeps its full width (>= 6 mm)
        cs, sn = math.cos(rot), math.sin(rot)
        body = []
        for i in range(22):
            t = TAU * i / 22
            body.append((0.0185 * math.cos(t), 0.0108 * math.sin(t) * (1 - 0.35 * max(0.0, math.cos(t)))))
        tail = [(0.0180, 0.0), (0.0275, 0.0080), (0.0275, -0.0080)]
        for poly in (body, tail):
            pts = [(px + dx + x * cs - z * sn, pz + dz + x * sn + z * cs) for x, z in poly]
            ngon_top(fm, pts, TABLE_TOP + 0.0068, "fish", hb=TABLE_TOP + 0.0030)
    fm.remap(c, at, k)
    fish = make_obj("fishOnPlate", fm, plate, origin=(px, TABLE_TOP + 0.003, pz), smooth_angle=50)
    lm = MB(); lm.nr = True
    wick = lamp_mesh(lm, LAMP2[0], TABLE_TOP, LAMP2[1], toward=-1)
    lm.nr = False
    lamp2 = make_obj("lamp2", lm, table, origin=wick, smooth_angle=50)
    return table, plate, fish, lamp2


def build_jar(house):
    """`waterJar`: a big terracotta jar in the back-left corner at (0.12, -0.53), top UPPER + 0.12"""
    jx, jz = JAR
    mb = MB()
    lathe(mb, [(0.0, 0.0), (0.016, 0.0), (0.028, 0.025), (0.031, 0.050), (0.027, 0.085), (0.016, 0.104), (0.013, 0.110),
               (0.0175, 0.116), (0.018, 0.120), (0.0, 0.118)], "clay", C=(jx, UPPER, jz), seg=18)
    for s in (-1, 1):                                             # two loop handles
        tube(mb, [(jx + s * 0.014, UPPER + 0.104, jz), (jx + s * 0.030, UPPER + 0.100, jz),
                  (jx + s * 0.027, UPPER + 0.082, jz)], 0.0035, "clay", seg=6)
    mb.remap((jx, UPPER, jz), PROPS_AT["jar"], PROPS_K["jar"])
    return make_obj("waterJar", mb, house, origin=(jx, UPPER, jz), smooth_angle=50)


def build_lamp1(house):
    mb = MB(); mb.nr = True
    wick = lamp_mesh(mb, LAMP1[0] - 0.004, SHELF[2], LAMP1[1])
    mb.nr = False
    return make_obj("lamp1", mb, house, origin=wick, smooth_angle=50)


# ============================================================================================ ground: path, grass
def path_polys():
    main = catmull([(0.64, 0.100), (0.44, 0.106), (0.30, 0.100), (0.20, 0.090), (0.08, 0.082), (-0.02, 0.070),
                    (-0.07, 0.058)], 0.012)
    house = catmull([(0.30, -0.225), (0.285, -0.12), (0.255, -0.02), (0.225, 0.08)], 0.012)
    tomb = catmull([(-0.06, 0.062), (-0.14, -0.02), (-0.24, -0.11), (-0.31, -0.18)], 0.012)
    fore = np.array([(-0.47, -0.262), (-0.06, -0.262), (-0.08, -0.17), (-0.16, -0.12), (-0.28, -0.095),
                     (-0.40, -0.11), (-0.46, -0.16)])
    return [strip_poly(main, 0.105, 0.105), strip_poly(house, 0.085, 0.10), strip_poly(tomb, 0.095, 0.085), fore]


HOUSE_BLOCK = np.array([(HOUSE_X[0], HOUSE_ZF), (HOUSE_X[1], HOUSE_ZF), (HOUSE_X[1], FLOOR[2]), (HOUSE_X[0], FLOOR[2])])


def land_h(x, z, reg):
    base = {"path": 0.0026, "grass": 0.0020}[reg]
    return base + 0.0004 * (nz(x * 7, z * 7) - 0.5)


def build_ground(root):
    """`path` and `ground` (grass) from one constrained triangulation of the floor (the house block left out)"""
    polys = path_polys()
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    outlines = [_resample(rect, 0.02), _resample(HOUSE_BLOCK, 0.02)] + [_resample(p, 0.010) for p in polys]
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
        if any(in_poly(c, p) for p in polys):
            return "path"
        return "grass"
    mbs = {k: MB() for k in ("path", "grass")}
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
    rng = random.Random(21)
    for k in range(40):                                          # grass ticks
        x = rng.uniform(-0.58, 0.58); z = rng.uniform(-0.30, 0.20)
        if in_poly((x, z), HOUSE_BLOCK) or any(in_poly((x + dx, z + dz), p) for p in polys for dx in (-0.012, 0.012)
                                                for dz in (-0.012, 0.0, 0.012)):
            continue
        if x < -0.05 and z < face_z(min(x, -0.05)) + 0.01:
            continue
        for s in (-1, 0, 1):
            dec.append(((x + s * 0.004, 0.0024, z), (x + s * 0.006, 0.0024, z - 0.008)))
    path = make_obj("path", mbs["path"], root, origin=(0.0, 0.0, 0.08), smooth_angle=35)
    ground = make_obj("ground", mbs["grass"], root, smooth_angle=35)
    return path, ground


def build_wall(root):
    """`gardenWall`: low stone wall along x -0.04 from z -0.28 to 0.21 (h 0.026), gap `gate` at z 0.00..0.12"""
    mb = MB(); mb.nr = True
    x0, x1 = WALL_X - WALL_T / 2, WALL_X + WALL_T / 2
    for za, zb in ((WALL_Z[0], GATE_Z[0]), (GATE_Z[1], WALL_Z[1])):
        n = max(1, int(round((zb - za) / 0.045)))
        zs = np.linspace(za, zb, n + 1)
        for i, (a, b) in enumerate(zip(zs[:-1], zs[1:])):
            h = WALL_H - 0.003 * (i % 2)
            box(mb, x0, x1, 0.0, h, a + 0.0008, b - 0.0008, "stone", skip=("bottom",))
    mb.nr = False
    return make_obj("gardenWall", mb, root, origin=(WALL_X, 0.0, 0.0), smooth_angle=30)


# ============================================================================================ flowers (template blooms)
TPL_AT = {"lily": (5.00, 0.0, 5.0), "poppy": (5.032, 0.0, 5.0), "daisy": (5.064, 0.0, 5.0), "leaf": (5.032, 0.0, 5.03)}
BLOOM_R = 0.0125


def bloom_shape(kind, r=BLOOM_R):
    if kind == "lily":                                           # six pointed petals
        return [(r * (1.0 if i % 2 == 0 else 0.66) * math.cos(TAU * i / 12 + 0.26),
                 r * (1.0 if i % 2 == 0 else 0.66) * math.sin(TAU * i / 12 + 0.26)) for i in range(12)]
    if kind == "poppy":                                          # four round petals
        return [(r * (0.86 + 0.14 * math.cos(4 * TAU * i / 24)) * math.cos(TAU * i / 24),
                 r * (0.86 + 0.14 * math.cos(4 * TAU * i / 24)) * math.sin(TAU * i / 24)) for i in range(24)]
    return [(r * (0.90 + 0.10 * math.cos(10 * TAU * i / 30)) * math.cos(TAU * i / 30),   # daisy: ten small petals
             r * (0.90 + 0.10 * math.cos(10 * TAU * i / 30)) * math.sin(TAU * i / 30)) for i in range(30)]


def add_bloom(mb, kind, x, h, z, rot=0.0):
    """one bloom (a thick flat flower facing up) at (x, h, z); its drawing model is the template bloom"""
    tx, th, tz = TPL_AT[kind]
    cs, sn = math.cos(rot), math.sin(rot)
    shp = [(a * cs - b * sn, a * sn + b * cs) for a, b in bloom_shape(kind)]
    i0 = len(mb.V)
    ngon_top(mb, [(x + a, z + b) for a, b in shp], h, kind, hb=h - 0.004)
    for i in range(i0, len(mb.V)):
        vx, vh, vz = mb.V[i]
        dx, dz = vx - x, vz - z
        ux, uz = dx * cs + dz * sn, -dx * sn + dz * cs            # back to the template's (unrotated) frame
        mb.P[i] = (tx + ux, th + (vh - h) + 0.035, tz + uz)


def flowers_template():
    mb = MB()
    for kind in ("lily", "poppy", "daisy"):
        tx, th, tz = TPL_AT[kind]
        ngon_top(mb, [(tx + a, tz + b) for a, b in bloom_shape(kind)], 0.035, kind, hb=0.031)
    lx, _, lz = TPL_AT["leaf"]
    leaf = [(lx + 0.040 * math.cos(t), lz + 0.010 * math.sin(t) * (1 if math.cos(t) < 0.9 else 0.6))
            for t in np.linspace(0, TAU, 24, endpoint=False)]
    ngon_top(mb, leaf, 0.010, "leaf", hb=0.008)
    return mb


def build_flowers(root):
    """`flowers`: the front-left bed (x -0.60..-0.30, z 0.04..0.20) and the hill-foot bed (x -0.60..-0.46,
    z -0.29..-0.20); bloom tops <= 0.04, stems and leaves named texels"""
    mb = MB()
    rng = random.Random(5)
    spots = []
    kinds = ["lily", "poppy", "daisy"]
    for (x0, x1, z0, z1), n in ((BED_FRONT, 22), (BED_HILL, 7)):
        tries = 0
        placed = []
        while len(placed) < n and tries < 4000:
            tries += 1
            x, z = rng.uniform(x0 + 0.016, x1 - 0.016), rng.uniform(z0 + 0.016, z1 - 0.016)
            if (x0, z0) == (BED_HILL[0], BED_HILL[2]) and math.hypot(x - TOOLS[0] - 0.02, z - TOOLS[1]) < 0.035:
                continue
            if any(math.hypot(x - a, z - b) < 0.034 for a, b in placed):
                continue
            placed.append((x, z))
        spots += placed
    for k, (x, z) in enumerate(spots):
        kind = kinds[k % 3]
        h = 0.030 + 0.008 * rng.random()
        mb.nr = True
        tube(mb, [(x, 0.0, z), (x + 0.002, h * 0.5, z), (x, h - 0.003, z)], 0.0018, "leaf", seg=5)
        for s in (-1, 1):
            a = rng.uniform(0, TAU)
            blade(mb, [(x, 0.002, z), (x + s * 0.010 * math.cos(a), 0.012, z + 0.010 * math.sin(a)),
                       (x + s * 0.018 * math.cos(a), 0.008, z + 0.018 * math.sin(a))], [0.004, 0.008, 0.0], "leaf")
        mb.nr = False
        add_bloom(mb, kind, x, h, z, rot=rng.uniform(0, TAU))
    return make_obj("flowers", mb, root, origin=FLOWERS_ORIGIN, smooth_angle=60)


# ============================================================================================ trees, backdrop
def olive_mesh(mb, trunk, crown, under, rs):
    tx, tz = trunk
    cx, cz = crown
    mb.nr = True
    tube(mb, [(tx, 0.0, tz), (tx + (cx - tx) * 0.2, 0.08, tz + (cz - tz) * 0.2 + 0.003),
              (tx + (cx - tx) * 0.6, 0.15, tz + (cz - tz) * 0.6), (cx, under + 0.03, cz)], [0.016, 0.012, 0.010, 0.008],
         "trunk", seg=8)
    mb.nr = False
    for k, (dx, h, dz, r) in enumerate(rs):
        lumpy(mb, (cx + dx, h, cz + dz), r, "olive", seg=12, rings=7, sh=0.85, amp=0.14, seed=k + 6, flat_bottom=under)


def build_olives(root):
    """`olive1` behind the hill's right shoulder at (0.00, -0.50), crown underside 0.24; `olive2` at the far left
    edge (-0.57, -0.05), trunk r 0.016, crown underside 0.21, crown only beyond x -0.50"""
    m1 = MB()
    olive_mesh(m1, OLIVE1, (0.0, -0.568), 0.24,
               ((0.0, 0.300, 0.0, 0.040), (-0.030, 0.285, 0.008, 0.030), (0.028, 0.288, 0.004, 0.028),
                (0.0, 0.330, -0.006, 0.032), (-0.012, 0.272, -0.016, 0.026)))
    o1 = make_obj("olive1", m1, root, origin=(OLIVE1[0], 0.0, OLIVE1[1]), smooth_angle=60)
    m2 = MB()
    olive_mesh(m2, OLIVE2, (-0.565, -0.06), 0.21,
               ((0.0, 0.255, 0.0, 0.034), (-0.015, 0.240, 0.015, 0.026), (0.012, 0.238, -0.012, 0.020),
                (0.0, 0.285, -0.005, 0.028)))
    # olive2 prints beside olive1 in the `olives` drawing
    m2.remap((OLIVE2[0], 0.0, OLIVE2[1]), (0.16, 0.0, -0.50), 1.0)
    o2 = make_obj("olive2", m2, root, origin=(OLIVE2[0], 0.0, OLIVE2[1]), smooth_angle=60)
    return o1, o2


def hills_top(x):
    t = (x - HILLS_X[0]) / (HILLS_X[1] - HILLS_X[0])
    return 0.50 + 0.035 * math.sin(TAU * 1.2 * t + 0.4) + 0.015 * math.sin(TAU * 2.9 * t + 1.1)


CITY_TOP, TOWER = 0.575, (0.38, 0.47, 0.64)


def build_backdrop(root):
    """`hills` (relief behind the tomb, x -0.60..0.06, 0.30 up to 0.47..0.55) and `cityWall` (relief behind the house,
    battlements at 0.575, a gate tower x 0.38..0.47 to 0.64 with a small arched gate)"""
    mb = MB()
    xs = np.linspace(HILLS_X[0], HILLS_X[1], 44)
    poly = [(x, 0.38) for x in xs[::-1]] + [(x, hills_top(x)) for x in xs]
    extrude(mb, poly[::-1], BACK_Z[0], BACK_Z[1], "hills")
    dec = DECOR.setdefault("skyline", [])
    rng = random.Random(8)
    zf = BACK_Z[1] + 0.0002
    for k in range(9):
        x = rng.uniform(HILLS_X[0] + 0.04, HILLS_X[1] - 0.04)
        h = hills_top(x) - rng.uniform(0.025, 0.045)
        dec.append(((x - 0.007, h - 0.004, zf), (x, h + 0.008, zf)))
        dec.append(((x, h + 0.008, zf), (x + 0.007, h - 0.004, zf)))
    hills = make_obj("hills", mb, root, origin=(-0.27, 0.0, BACK_Z[1]), smooth_angle=30)
    cm = MB()
    x0, x1 = CITY_X
    tx0, tx1, ttop = TOWER
    for a, b, top in ((x0, tx0, CITY_TOP), (tx0, tx1, ttop), (tx1, x1, CITY_TOP)):
        extrude(cm, [(a, 0.44), (b, 0.44), (b, top), (a, top)], BACK_Z[0], BACK_Z[1], "cityStone")
        n = max(1, int(round((b - a) / 0.03)))
        w = (b - a) / n
        for k in range(n):                                        # battlements
            m0 = a + k * w + w * 0.25
            extrude(cm, [(m0, top), (m0 + w * 0.5, top), (m0 + w * 0.5, top + 0.014), (m0, top + 0.014)],
                    BACK_Z[0], BACK_Z[1], "cityStone")
    gx, gw, gy = (tx0 + tx1) / 2, 0.026, 0.535                    # the gate arch and wall courses (drawn lines)
    for k in range(10):
        a0, a1 = math.pi * k / 10, math.pi * (k + 1) / 10
        dec.append(((gx + gw / 2 * math.cos(a0), gy + gw / 2 * math.sin(a0), zf),
                    (gx + gw / 2 * math.cos(a1), gy + gw / 2 * math.sin(a1), zf)))
    for s in (-1, 1):
        dec.append(((gx + s * gw / 2, 0.49, zf), (gx + s * gw / 2, gy, zf)))
    dec.append(((x0 + 0.004, 0.52, zf), (tx0 - 0.004, 0.52, zf)))
    dec.append(((tx1 + 0.004, 0.52, zf), (x1 - 0.004, 0.52, zf)))
    city = make_obj("cityWall", cm, root, origin=(0.33, 0.0, BACK_Z[1]), smooth_angle=30)
    return hills, city


# ============================================================================================ drawings / UV
# the `props` still life: drawing-model place and scale of each prop (P = at + k * (V - centre))
PROPS_AT = {"table": (0.00, 0.0, 0.0), "jar": (-0.090, -0.06, 0.0), "stone": (0.046, -0.1254, 0.0),
            "cloths": (-0.060, 0.0, 0.145)}
PROPS_K = {"table": 1.2, "jar": 0.60, "stone": 0.245, "cloths": 1.0}


def _chars_proposal():
    """CONTRACT §2 start slots; Jesus's box as printed in Real Miracles (the same figure), the angel's and Mary's
    guessed from their sizes until regions_characters.json exists"""
    return {"angel": {"sheetX": -0.32, "sheetY": 0.015, "height": 0.40, "box": [-0.46, 0.015, -0.18, 0.475]},
            "jesus": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.36, "box": [-0.1334, 0.0191, 0.1334, 0.3703]},
            "mary": {"sheetX": 0.32, "sheetY": 0.015, "height": 0.34, "box": [0.195, 0.015, 0.445, 0.36]}}


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
    "skyline": dict(P_FRONT(), scale=2.2, cx=-0.2025, y0=1.080, decorOnly=["hills", "cityStone"],
                    members=["hills", "cityWall"]),
    "tomb":    dict(P_OBL(0.0, 0.45), scale=1.9, cx=-0.330, y0=0.750, decorOnly=["rock"],
                    members=["tombHill", "tombDoor"]),
    "house":   dict(P_OBL(0.0, 0.5), scale=2.25, cx=0.340, y0=0.620, members=["house", "stair"]),
    "room":    dict(P_OBL(0.0, 0.35), scale=2.3, cx=0.358, y0=0.385, decorOnly=["mats"], members=["houseIn"]),
    "props":   dict(P_OBL(0.0, 0.8), scale=0.6, cx=0.028, y0=0.556,
                    members=["lowTable", "fishPlate", "fishOnPlate", "waterJar", "cloths", "tombStone",
                             "tombStoneAside"]),
    "ground":  dict(P_PLAN(), scale=3.8, cx=-0.315, y0=0.495, decorOnly=["path", "grass"], members=["path", "ground"]),
    "olives":  dict(P_FRONT(), scale=1.2, cx=0.350, y0=1.080, decorOnly=["olive"], members=["olive1", "olive2"]),
    "flowers": dict(P_PLAN(), scale=0.36, cx=0.000, y0=0.396, members=[]),
}
TEMPLATES = {"flowers": ("flowers",), "tomb": ()}
STONE = ("props", "stone")
CONSTS = {"tombDoor": {"door": ("tomb", "door")},
          "cloths": {"ledge": ("tomb", "door")},
          "groove": {"stone": STONE}, "gardenWall": {"stone": STONE},
          "gardenTools": {"wood": ("house", "wood"), "metal": STONE, "clay": ("props", "clay")},
          "flowers": {"leaf": ("flowers", "leaf")},
          "olive1": {"trunk": ("house", "wood")}, "olive2": {"trunk": ("house", "wood")},
          "houseIn": {"plaster": ("room", "plaster")},
          "roomDoor": {"wood": ("house", "wood")},
          "bench": {"wood": ("house", "wood"), "cushion": ("flowers", "poppy")},
          "lowTable": {"wood": ("props", "wood")},
          "lamp1": {"clay": ("props", "clay")}, "lamp2": {"clay": ("props", "clay")}}
# hidden props of the Characters role take their colour from these printed regions (CONTRACT §3, C7)
PROP_ANCHORS = {"jesus/fish": ("props", "fish"), "mary/jar": ("props", "clay"), "joanna/jar": ("props", "clay")}
RS = [1]
ORDER = ["ground", "path", "flowers", "gardenWall", "tombHill", "tombDoor", "cloths", "groove", "tombStone",
         "tombStoneAside", "gardenTools", "olive1", "olive2", "house", "houseIn", "stair", "roomDoor", "bench",
         "lowTable", "fishPlate", "fishOnPlate", "lamp2", "waterJar", "lamp1", "hills", "cityWall"]
HIDDEN = ["tombStoneAside"]


def tomb_template():
    """raster-only pane in the door opening: prints the door's dark region (the chamber samples it)"""
    mb = MB()
    pts = door_outline()
    tri = tessellate_polygon([[Vector((a, b, 0)) for a, b in pts]])
    ids = [mb.v(a, b, FACE_Z - 0.002) for a, b in pts]
    for t in tri:
        mb.fo([ids[i] for i in t], "door", (0, 0, 1))
    return mb


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
                       "written by pipeline/rs_garden.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
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
    out = {}
    for n, ob in objs.items():
        if ob.type != 'MESH' or n in TERRAIN:
            continue
        out[n] = to_design(ob.matrix_world, tri_points(ob))
    return out


def check_clearance(objs):
    """CONTRACT §6 rule per mark and per straight walk, relative to the walker's floor y: nothing above y + 0.012
    within 0.05 (seated marks: 0.035, the body's half depth); overhead parts (y + 0.17 .. head top) need 0.035; above
    the actor's head ignored. Walking surfaces (path, ground) do not count; hidden props count everywhere except
    `tombStone` (the closed stone) at marks used after it has rolled away. STONE_ASIDE: nothing above 0.22 within
    0.08 except the rock face behind it (z < -0.30) and the stone itself (the seat)."""
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

    for label, (x, z, y, kind, actor, ign) in MARKS.items():
        if kind == "seat":
            seat_test(label, (x, z), y, 0.30, pts, hard)
        elif kind == "stone":
            near, lo = {}, 9.0
            for name, P in pts.items():
                if name in ign or name in ("tombStoneAside",):
                    continue
                d = np.hypot(P[:, 0] - x, P[:, 2] - z)
                if name == "tombHill":                                # the rock behind the seat
                    continue
                m = P[:, 1] > STONE_TOP
                if m.any():
                    lo = min(lo, float(d[m].min()))
                    if (d[m] < 0.08).any():
                        near[name] = round(float(d[m].min()), 4)
            if near:
                hard["mark STONE_ASIDE (nothing above the seat within 0.08)"] = near
            MARGINS["mark STONE_ASIDE"] = [round(lo, 3), None]
            sa = pts["tombStoneAside"]
            info["STONE_ASIDE"] = {"stoneTop": round(float(sa[:, 1].max()), 4),
                                   "flatTop": "the rim's crown: %.3f wide within 0.004 of the top" %
                                   float(np.ptp(sa[sa[:, 1] > sa[:, 1].max() - 0.004][:, 0]))}
        else:
            zone_test("mark " + label, (x, z), (x, z), y, HEAD[actor], R_STAND, ign)
    for label, ls, ign in PATHS:
        for a, b in zip(ls[:-1], ls[1:]):
            (ax, az, ay, ka, actor, _), (bx, bz, by, kb, _, _) = MARKS[a], MARKS[b]
            zone_test("walk %s %s>%s" % (label, a, b), (ax, az), (bx, bz), ay, HEAD[actor], R_STAND, ign)
    # facts the contract names
    td = pts["tombStone"]
    info["tombStone"] = {"x": [round(float(td[:, 0].min()), 4), round(float(td[:, 0].max()), 4)],
                         "top": round(float(td[:, 1].max()), 4), "door": list(DOOR[:2])}
    hp = pts["tombHill"]
    info["tombHillTop"] = round(float(hp[:, 1].max()), 4)
    return hard, info


def seat_test(label, c, y, head, pts, hard):
    """seated marks: radius 0.035 (the seated body's half depth); the bench is the seat"""
    lo_min = 9.0
    x, z = c
    for name, P in pts.items():
        if name == "bench":
            continue
        d = np.hypot(P[:, 0] - x, P[:, 2] - z)
        rel = P[:, 1] - y
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
    root = link(bpy.data.objects.new("garden", None))
    objs = {}
    objs["path"], objs["ground"] = build_ground(root)
    objs["flowers"] = build_flowers(root)
    objs["gardenWall"] = build_wall(root)
    objs["tombHill"], objs["tombDoor"], objs["cloths"] = build_tomb(root)
    objs["groove"] = build_groove(objs["tombHill"])
    objs["tombStone"], objs["tombStoneAside"] = build_stones(objs["tombHill"])
    objs["gardenTools"] = build_tools(objs["tombHill"])
    objs["olive1"], objs["olive2"] = build_olives(root)
    objs["house"], objs["houseIn"] = build_house(root)
    objs["stair"] = build_stair(root)
    objs["roomDoor"] = build_room_door(objs["house"])
    objs["bench"] = build_bench(objs["house"])
    objs["lowTable"], objs["fishPlate"], objs["fishOnPlate"], objs["lamp2"] = build_table(objs["house"])
    objs["waterJar"] = build_jar(objs["house"])
    objs["lamp1"] = build_lamp1(objs["house"])
    objs["hills"], objs["cityWall"] = build_backdrop(root)
    bpy.context.view_layer.update()
    tmp = {"tpl_flowers": make_obj("tpl_flowers", flowers_template(), None, smooth_angle=60),
           "tpl_tomb": make_obj("tpl_tomb", tomb_template(), None, smooth_angle=60)}
    src = raster_sources(objs, tmp)
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("GARDEN_TRIS", total, json.dumps(tris))
    lay = check_layout()
    hard, info = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_MIN", json.dumps(MARGINS))
    print("CLEARANCE_INFO", json.dumps(info))
    if total > MAX_TRIS:
        print("OVER_BUDGET", total)
    STATE.update(objs=objs, root=root, hard=hard, info=info)
    if MODE == "check":
        return
    RS[0] = 2
    idb2, regname, crease2 = raster_drawings(src)
    RS[0] = 1
    for o in tmp.values():
        bpy.data.objects.remove(o, do_unlink=True)
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
                              export_skins=False, export_animations=False, export_texcoords=True,
                              export_normals=True, export_materials='EXPORT', export_morph=False)
    hmax = {n: round(float(max(v[1] for v in world_verts(ob))), 4) for n, ob in objs.items()}
    write_design(objs, tris, total, hmax, const, hard, info, tex)
    STATE.update(tex=tex_img, demo=demo)
    print("BUILD_OK", GLB, total, "MISSING" if missing else "")


TITLE = {"hanzi": "他复活了", "pinyin": "tā fù huó le", "english": "He Is Risen!", "box": 76, "gap": 40,
         "cy": 110, "label": "DoodLive · 涂上颜色，再用手机扫一扫",
         "note": "box / gap / cy from tools/story/sheet_risen.py title-search: worst NCC 0.402 (daniel-A4) against "
                 "every other registered sheet (incl. The King Who Serves and Real Miracles)"}


def write_design(objs, tris, total, hmax, const, hard, info, tex):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    d.setdefault("version", 1)
    d.setdefault("artHeightUnits", ART_H)
    d.setdefault("lines", {"outerPx": 4.5, "detailPx": 3.0,
                           "note": "same weights as every story pack; faces come from decals"})
    d.setdefault("sheet", {
        "page": [1240, 1754], "dpi": 150, "art": [120, 283, 1000, 1227],
        "markers": [[62, 225], [1178, 225], [1178, 1568], [62, 1568]], "markerSize": 64,
        "title": dict(TITLE),
        "footer": {"rect": [210, 1604, 820, 110], "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上",
                                                            "马太福音 28 · 约翰福音 20 · Matthew 28; John 20"],
                   "note": "centred on the page (x 620); line 1 at rect y + 40, line 2 at y + 76"},
        "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge; "
                    "title cy keeps the pinyin >= 6 mm from the top"})
    if d["sheet"]["title"].get("note", "").startswith("placeholder") and not TITLE["note"].startswith("placeholder"):
        d["sheet"]["title"] = dict(TITLE)
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"height": v["height"], "sheetX": v["sheetX"], "sheetY": v["sheetY"]})
        if c == "angel":
            e["note"] = ("height = head top 0.40; wing tops 0.46; wings spread <= +-0.14 from sheetX (CONTRACT §2), "
                         "so they clear Jesus's A-pose hands (~ -0.12) and the page edge")
        ch[c] = e
    d["characters"] = ch
    pieces = []
    for name in ORDER:
        g = drawing_of(name)
        sp = DRAWINGS[g] if g else None
        fu = ({k: (round(sp[k], 5) if isinstance(sp[k], float) else sp[k]) for k in ("A", "B", "D", "scale", "sheetX",
                                                                                   "sheetY")} if sp else None)
        pieces.append({"id": name, "drawing": g, "frontUV": fu, "instanced": name in sum(TEMPLATES.values(), ()),
                       "namedTexels": {r: list(k) for r, k in CONSTS.get(name, {}).items()} or None,
                       "regions": sorted(set(REG_OF[name])), "heightMax": hmax[name], "tris": tris[name]})
    drawings = {g: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dsp.items()} for g, dsp in DRAWINGS.items()}
    anchors = {k: {"region": list(v), "uv": [round(c, 5) for c in tex[v]] if v in tex else None}
               for k, v in PROP_ANCHORS.items()}
    d["set"] = {
        "generatedBy": "pipeline/rs_garden.py", "doc": "docs/risen/SET.md",
        "contract": "docs/risen/CONTRACT.md §6", "root": "garden",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {n: [round(c, 4) for c in D(objs[n].matrix_world.translation)] for n in ORDER},
        "footprints": {
            "floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]],
            "tombHill": {"x": list(HILL_X), "faceZ": "%.3f along the door and the groove (x <= -0.235), receding to "
                         "%.3f at x -0.17 and %.3f at the right end" % (FACE_Z, face_z(-0.17), face_z(HILL_X[1])),
                         "top": info.get("tombHillTop")},
            "tombDoor": {"x": list(DOOR[:2]), "top": DOOR[2], "anchor": list(DOOR_C),
                         "chamber": {"x": list(CHAMBER[:2]), "z": list(CHAMBER[2:4]), "ceiling": CHAMBER[4]}},
            "cloths": {"ledge": {"x": list(LEDGE[:2]), "z": list(LEDGE[2:4]), "top": LEDGE[4]}},
            "tombStone": {"centre": list(STONE_C), "radius": STONE_R, "thickness": STONE_T},
            "tombStoneAside": {"centre": [round(c, 4) for c in STONE_ASIDE_C], "top": STONE_TOP,
                               "yawDeg": round(math.degrees(ASIDE_YAW), 1), "angelY": round(ANGEL_Y, 4)},
            "groove": {"x": list(GROOVE[:2]), "z": list(GROOVE[2:4]), "top": GROOVE[4]},
            "gardenTools": list(TOOLS),
            "gardenWall": {"x": [WALL_X - WALL_T / 2, WALL_X + WALL_T / 2], "z": list(WALL_Z), "h": WALL_H,
                           "gate": list(GATE_Z)},
            "flowers": {"front": list(BED_FRONT), "hillFoot": list(BED_HILL), "bloomTop": 0.038},
            "olive1": {"trunk": list(OLIVE1), "crownUnderside": 0.24}, "olive2": {"trunk": list(OLIVE2),
                                                                                  "crownUnderside": 0.21},
            "house": {"x": list(HOUSE_X), "z": [FLOOR[2], HOUSE_ZF], "groundStorey": UPPER,
                      "room": {"x": list(IN_X), "z": list(IN_Z), "floor": UPPER},
                      "walls": {"left": list(WL), "right": list(WR), "back": list(WB), "backTop": BACK_TOP,
                                "leftTop": "%.2f behind z %.2f, %.2f over the door part, down to the sill at the front"
                                           % (BACK_TOP, LEFT_STEP[0], LEFT_TOP),
                                "rightTop": "%.2f behind z %.2f, sloping to %.2f at z %.2f" %
                                            (BACK_TOP, SLOPE_Z[0], SLOPE_LOW, HOUSE_ZF)},
                      "sill": {"z": list(SILL_Z), "top": SILL_H},
                      "door": {"x": list(GDOOR[:2]), "top": GDOOR[2]}, "window": list(SHUTTER),
                      "stair": {"x": list(STAIR_X), "z": [STAIR_Z0, LANDING_Z[1]], "top": UPPER}},
            "roomDoor": {"z": list(RDOOR_Z), "top": RDOOR_TOP, "x": [WL[0], WL[0] + 0.008]},
            "bench": {"x": list(BENCH_X), "z": list(BENCH_Z), "seat": BENCH_TOP},
            "lowTable": {"x": list(TABLE_X), "z": list(TABLE_Z), "top": TABLE_TOP, "fishPlate": list(PLATE),
                         "basket": list(BASKET), "lamp2": list(LAMP2)},
            "waterJar": {"at": list(JAR), "top": JAR_TOP},
            "lamp1": {"shelf": list(SHELF), "at": list(LAMP1)},
            "hills": {"x": list(HILLS_X), "z": list(BACK_Z)}, "cityWall": {"x": list(CITY_X), "z": list(BACK_Z),
                                                                          "top": TOWER[2]}},
        "hiddenAtStart": list(HIDDEN),
        "propAnchors": anchors,
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227",
                   "drawingModel": "P = the vertex, except props (moved / scaled into one still life), olive2 "
                                   "(beside olive1) and the blooms (template instances)",
                   "edgeOn": "faces with |n . D| < 0.22 (n in drawing space) take one clean texel of their region",
                   "namedTexels": "no-raster bits take one texel of a named (drawing, region); constUV in "
                                  "model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard,
                      "nearest": {"note": "[low zone (y+0.012..0.17), overhead (y+0.17..head top)] nearest plan distance "
                                          "(needs >= 0.05 / 0.035; seated 0.035; STONE_ASIDE 0.08 above the seat)",
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
    save_png(line, os.path.join(WORK, "garden_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "garden_drawings_demo.png"))
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
          "hairP": "#231A16", "johnT": "#7FB6E0", "hairL": "#9A6B42", "maryD": "#D9775F", "maryV": "#8DB5D8",
          "joD": "#D9A93A", "joV": "#A84A3A", "angelR": "#F4F7FB", "gold": "#E6B23E", "wing": "#FFF6DE",
          "thomT": "#3E8E86", "thomC": "#8A7A68"}
PV_SPEC = {"jesus": (0.36, "jesusT", "mantle", "hairJ"), "peter": (0.381, "peterT", "peterT", "hairP"),
           "john": (0.33, "johnT", "johnT", "hairL"), "mary": (0.34, "maryD", "maryD", "maryV"),
           "joanna": (0.33, "joD", "joD", "joV"), "angel": (0.40, "angelR", "angelR", "gold"),
           "thomas": (0.36, "thomT", "thomC", "hairP")}


def mannequins(layout):
    """preview stand-ins only (not shipped): simple figures in the demo colours at the actors' marks.
    layout: who -> (x, z, y, face (dx, dz), pose); pose '' standing, 'kneel', 'bench', 'stoop', 'seat' (the angel on
    the stone: hips at local y 0.035, legs hanging in front, wings half-open)"""
    for k, v in PV_COL.items():
        if k not in REGION_MATS:
            REGION_MATS[k] = flat_mat("pvm_" + k, v, 0.6)
    for who, (x, z, y, fc, pose) in layout.items():
        mb = MB()
        H, body, top, hair = PV_SPEC[who]
        if pose == "seat":
            s0 = 0.035
            lathe(mb, [(0.0, s0), (0.042, s0), (0.040, s0 + 0.09), (0.034, s0 + 0.18), (0.0, s0 + 0.19)], body, seg=16)
            for s in (-1, 1):
                tube(mb, [(s * 0.018, s0 + 0.01, 0.0), (s * 0.018, s0 + 0.01, 0.05), (s * 0.02, s0 - 0.10, 0.07)],
                     0.013, body, seg=8)
                blade(mb, [(s * 0.02, s0 + 0.17, -0.02), (s * 0.09, s0 + 0.22, -0.035), (s * 0.13, s0 + 0.15, -0.04)],
                      [0.05, 0.07, 0.0], "wing", nrm=(0, 0, 1))
            lathe(mb, [(0.043, s0 + 0.06), (0.044, s0 + 0.08), (0.0, s0 + 0.081)], "gold", seg=16)
            sphere(mb, (0.0, s0 + 0.22, 0.004), 0.032, "skin", seg=14, rings=9)
            sphere(mb, (0.0, s0 + 0.235, -0.008), 0.028, hair, seg=10, rings=7)
        elif pose == "bench":
            s0 = 0.04
            lathe(mb, [(0.0, s0), (0.040, s0), (0.038, s0 + 0.08), (0.032, s0 + 0.16), (0.0, s0 + 0.17)], body, seg=16)
            for s in (-1, 1):
                tube(mb, [(s * 0.018, s0 + 0.012, 0.0), (s * 0.018, s0 + 0.012, 0.055)], 0.014, body, seg=8)
                tube(mb, [(s * 0.018, s0 + 0.008, 0.058), (s * 0.018, 0.006, 0.062)], 0.011, body, seg=8)
            sphere(mb, (0.0, s0 + 0.195, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, s0 + 0.205, -0.008), 0.026, hair, seg=10, rings=7)
        elif pose == "kneel":
            lathe(mb, [(0.0, 0.0), (0.05, 0.0), (0.048, 0.03), (0.040, 0.10), (0.032, 0.16), (0.0, 0.17)], body, seg=16)
            sphere(mb, (0.0, 0.195, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, 0.205, -0.008), 0.026, hair, seg=10, rings=7)
        elif pose == "stoop":
            lathe(mb, [(0.0, 0.0), (0.050, 0.0), (0.048, 0.02), (0.042, 0.36 * H)], body, seg=18)
            tube(mb, [(0.0, 0.36 * H, 0.0), (0.0, 0.62 * H, 0.05)], 0.042, top, seg=14)
            sphere(mb, (0.0, 0.62 * H + 0.02, 0.09), 0.034, "skin", seg=14, rings=9)
        else:
            lathe(mb, [(0.0, 0.0), (0.050, 0.0), (0.048, 0.02), (0.042, 0.36 * H)], body, seg=18)
            lathe(mb, [(0.042, 0.36 * H), (0.046, 0.56 * H), (0.038, 0.75 * H), (0.0, 0.78 * H)], top, seg=18)
            sphere(mb, (0.0, H - 0.04, 0.0), 0.034, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, H - 0.05), (0.036, H - 0.04), (0.035, H - 0.010), (0.0, H)], hair, C=(0, 0, -0.006), seg=16)
            if who == "angel":
                for s in (-1, 1):
                    blade(mb, [(s * 0.02, 0.28, -0.03), (s * 0.09, 0.40, -0.045), (s * 0.13, 0.30, -0.05)],
                          [0.05, 0.07, 0.0], "wing", nrm=(0, 0, 1))
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
    img = save_png(STATE["tex"], os.path.join(WORK, "garden_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "garden_preview_sheet.png")); sheet.pack()
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
    sun.rotation_euler = (math.radians(42), math.radians(18), math.radians(30))
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

    def node_t(n):                                                # the director's set-node target point
        p = D(objs[n].matrix_world.translation)
        return (p[0], p[1] + 0.08, p[2])

    VIEWER = (0, 1)
    U_ = UPPER
    show(HIDDEN, False)
    # S01: the page from the phone, empty and with the sad day
    cast({})
    phone = ((0.0, 1.30, 1.55), (0.0, 0.02, -0.22), 50, (720, 1280))
    shoot("garden_preview_phone_set", *phone)
    s1 = {"mary": (-0.30, -0.13, 0.0, toward((-0.30, -0.13), STONE_C[::2]), ""),
          "joanna": (-0.42, -0.12, 0.0, toward((-0.42, -0.12), STONE_C[::2]), ""),
          "peter": (0.40, -0.49, U_, VIEWER, "bench"), "john": (0.30, -0.49, U_, VIEWER, "bench")}
    cast(s1)
    shoot("garden_preview_phone", *phone)
    phone_shot("garden_preview_s01", (0.0, 0.08, 0.0), 0.95, 0.45, -20)
    # S02: follow Mary on the path
    cast({"mary": (0.13, 0.085, 0.0, (-1, 0), ""), "joanna": (0.20, 0.11, 0.0, (-1, 0), "")})
    phone_shot("garden_preview_s02", act_t("mary", 0.13, 0.085), 0.6, 0.2, -30)
    # S03: the stone has rolled, the angel on it (fixed on tombHill)
    show(["tombStone"], False); show(["tombStoneAside"], True)
    s3 = {"mary": (-0.30, -0.13, 0.0, toward((-0.30, -0.13), (-0.17, -0.285)), ""),
          "joanna": (-0.42, -0.12, 0.0, toward((-0.42, -0.12), (-0.17, -0.285)), ""),
          "angel": (STONE_ASIDE_C[0], STONE_ASIDE_C[2], ANGEL_Y, VIEWER, "seat")}
    cast(s3)
    phone_shot("garden_preview_s03", node_t("tombHill"), 0.6, 0.22, 15)
    # S04: fixed on the angel; the women peek in at the door
    s4 = dict(s3)
    s4.update({"mary": (-0.30, -0.22, 0.0, toward((-0.30, -0.22), (-0.33, -0.31)), ""),
               "joanna": (-0.40, -0.21, 0.0, toward((-0.40, -0.21), (-0.33, -0.31)), "")})
    cast(s4)
    phone_shot("garden_preview_s04", act_t("angel", STONE_ASIDE_C[0], STONE_ASIDE_C[2], ANGEL_Y), 0.55, 0.2, -25)
    # S05: the room; Peter and John on the bench, Mary in from the door (fixed on house)
    cast({"peter": (0.40, -0.49, U_, VIEWER, "bench"), "john": (0.30, -0.49, U_, VIEWER, "bench"),
          "mary": (0.14, -0.33, U_, toward((0.14, -0.33), (0.40, -0.49)), "")})
    phone_shot("garden_preview_s05", node_t("house"), 0.55, 0.22, -10)
    # S06: the race (follow John at PATH_L)
    cast({"john": (0.04, 0.08, 0.0, (-1, 0), ""), "peter": (0.20, 0.08, 0.0, (-1, 0), "")})
    phone_shot("garden_preview_s06", act_t("john", 0.04, 0.08), 0.65, 0.2, -35)
    # S07: Peter stoops into the door, John beside (fixed on tombDoor)
    cast({"peter": (-0.33, -0.24, 0.0, (0, -1), "stoop"),
          "john": (-0.40, -0.22, 0.0, toward((-0.40, -0.22), (-0.33, -0.24)), "")})
    phone_shot("garden_preview_s07", node_t("tombDoor"), 0.5, 0.18, 20)
    # S08 / S09: Mary at the flowers, Jesus behind her right shoulder; then the meeting
    cast({"mary": (-0.24, -0.05, 0.0, VIEWER, ""), "jesus": (-0.10, -0.12, 0.0, toward((-0.10, -0.12), (-0.24, -0.05)), "")})
    phone_shot("garden_preview_s08", act_t("mary", -0.24, -0.05), 0.5, 0.17, 0)
    cast({"mary": (-0.205, -0.075, 0.0, toward((-0.205, -0.075), (-0.10, -0.12)), ""),
          "jesus": (-0.10, -0.12, 0.0, toward((-0.10, -0.12), (-0.205, -0.075)), "")})
    phone_shot("garden_preview_s09", act_t("jesus", -0.10, -0.12), 0.5, 0.17, 25)
    # S10: Jesus appears in the room, then eats the fish at the table
    s10 = {"mary": (0.14, -0.33, U_, toward((0.14, -0.33), (0.30, -0.30)), ""),
           "peter": (0.40, -0.45, U_, toward((0.40, -0.45), (0.30, -0.30)), ""),
           "john": (0.20, -0.45, U_, toward((0.20, -0.45), (0.30, -0.30)), ""),
           "jesus": (0.30, -0.30, U_, VIEWER, "")}
    cast(s10)
    phone_shot("garden_preview_s10", node_t("house"), 0.55, 0.24, -15)
    s10b = dict(s10); s10b["jesus"] = (0.41, -0.30, U_, (1, 0), "")
    show(["fishOnPlate"], False)
    cast(s10b)
    phone_shot("garden_preview_s10_table", node_t("house"), 0.55, 0.24, -15)
    show(["fishOnPlate"], True)
    # S11: Thomas kneels before Jesus (fixed on Thomas at THOMAS_TOUCH)
    cast({"thomas": (0.19, -0.30, U_, (1, 0), "kneel"), "jesus": (0.30, -0.30, U_, (-1, 0), ""),
          "peter": (0.40, -0.45, U_, toward((0.40, -0.45), (0.19, -0.30)), ""),
          "john": (0.20, -0.45, U_, toward((0.20, -0.45), (0.19, -0.30)), "")})
    phone_shot("garden_preview_s11", act_t("thomas", 0.19, -0.30, U_), 0.5, 0.2, -20)
    # S12: everyone in the garden, the angel gone
    cast({"jesus": (-0.12, -0.04, 0.0, VIEWER, ""), "mary": (-0.24, 0.02, 0.0, VIEWER, ""),
          "peter": (0.04, 0.04, 0.0, VIEWER, ""), "john": (0.14, 0.08, 0.0, VIEWER, ""),
          "thomas": (0.06, -0.10, 0.0, VIEWER, "")})
    phone_shot("garden_preview_s12", (0.0, 0.08, 0.0), 0.95, 0.48, 6)
    # close-ups: the two stone states, the open tomb, the table with and without the fish
    cast({})
    show(["tombStone"], True); show(["tombStoneAside"], False)
    shoot("garden_preview_tomb_closed", (-0.20, 0.30, 0.45), (-0.27, 0.15, -0.30), 40, (1200, 900))
    show(["tombStone"], False); show(["tombStoneAside"], True)
    shoot("garden_preview_tomb_open", (-0.20, 0.30, 0.45), (-0.27, 0.15, -0.30), 40, (1200, 900))
    shoot("garden_preview_hidden", (0.62, 0.40, 0.10), (0.48, 0.14, -0.36), 34, (1200, 900))
    show(HIDDEN, False); show(["tombStone"], True)
    shoot("garden_preview_front", (0.0, 0.30, 2.3), (0.0, 0.18, -0.25), 22, (1600, 1000))
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "garden_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["garden", "tombHill", "tombDoor", "cloths", "tombStone", "tombStoneAside", "groove", "flowers", "gardenTools",
        "gardenWall", "olive1", "olive2", "path", "ground", "house", "houseIn", "stair", "roomDoor", "bench",
        "lowTable", "fishPlate", "fishOnPlate", "waterJar", "lamp1", "lamp2", "cityWall", "hills"]


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
    parents = {n: (bpy.data.objects[n].parent.name if bpy.data.objects[n].parent else None) for n in NEED[1:]
               if n in names}
    org = {n: [round(c, 3) for c in (bpy.data.objects[n].matrix_world.translation.x,
                                     bpy.data.objects[n].matrix_world.translation.z,
                                     -bpy.data.objects[n].matrix_world.translation.y)]
           for n in ("tombDoor", "tombStone", "tombStoneAside", "lamp1", "lamp2", "flowers") if n in names}
    ok = not missing and tris <= MAX_TRIS and uv_bad == 0
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "parents": parents, "origins": org}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
