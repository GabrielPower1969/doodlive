"""Blender (headless): Saul Sees the Light! story pack, the set -> assets/saul/model/damascus.glb

One tabletop page, three places (docs/saul/CONTRACT.md §6, DESIGN.md §2).
Left = Damascus inside its wall: `ananiasHouse` (front left, a small doll's-house room open at the front: stool,
lamp on a ledge, rolled mat, a window in the back wall), `synagogue` (facade with two engaged columns, a door, a lintel
with rosettes, three steps), `judasHouse` (the bigger doll's-house room against the city wall: children `judasDoor`
(a free-standing door frame on the open front), `prayerMat`, `breadBasket` (on the low table), `waterJar`), the pale
paved `straightStreet` and the `well` (bucket, two pots, a crate) at the back left.
Centre = `cityWall` (sand-stone wall at x = 0 from the back edge to the round front tower), children `cityGate` (the
gateway reveals, arch and the two open doors), `torch1` `torch2` (in iron holders on the outside face), `wallWindow`
(the basket window high in the outside face, shutter folded open).
Right = the desert `road` (porch -> right side -> front -> the gate), `rocks` (+ bushes), `milestone`, `palm`,
Jerusalem's `priestPorch` and `jerusalemHouse` (child `jerusalemDoor`, open, dark inside). The rest of the floor is
`ground` (extra node). Back edge reliefs: `hills` (behind Damascus) and `jerusalemWall`.
Contract: docs/saul/CONTRACT.md §6. Nodes, measured clearances, deviations: docs/saul/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `sa_page` = the scanned art rectangle): as He Is Risen! (pipeline/rs_garden.py). Each
piece belongs to one *drawing* on the colouring sheet, a linear view a = A.P, b = B.P (depth D.P) of its drawing model
P, and u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227. P is the vertex itself except in the `props`
drawing (each prop moved / scaled into one still life: bread basket, water jar, prayer mat, well, rocks, palm crown).
The city wall is printed from its outside (a side view from +x: `wall`), the two rooms and the synagogue from the
front (`street`: inside faces only, the outside of the rooms takes one limestone texel: LESSONS L51).

Modes (run from the repo root, one Blender at a time):
  nice -n 10 blender -b --factory-startup --python-exit-code 1 --python pipeline/sa_damascus.py -- build
  nice -n 10 blender -b --factory-startup --python-exit-code 1 --python pipeline/sa_damascus.py -- verify
  nice -n 10 blender -b --factory-startup --python-exit-code 1 --python pipeline/sa_damascus.py -- all
  nice -n 10 blender -b --factory-startup --python-exit-code 1 --python pipeline/sa_damascus.py -- check
Work files go to $SA_WORK (default /tmp/saul_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/saul/model")
GLB = os.path.join(MODEL, "damascus.glb")
BLEND = os.path.join(MODEL, "damascus.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/saul/design.json")
ENV = "SA_"
WORK = os.environ.get(ENV + "WORK", "/tmp/saul_set")
PAGE_MATERIAL = "sa_page"
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
BACK_Z = (-0.5875, -0.5845)                    # the back-edge reliefs (hills, jerusalemWall)
WB = (-0.584, -0.569)                          # back walls of the rooms, in front of the reliefs
# city wall
WT = 0.027                                     # half thickness: x -0.027..0.027 (contract +-0.03: SET.md)
WALL_Z0 = FLOOR[2]
WALL_BODY, MERLON_TOP = 0.282, 0.30            # body top, rounded battlements to 0.30
TOWER_C, TOWER_R, TOWER_BODY, TOWER_TOP = (0.0, -0.04), 0.05, 0.315, 0.34
GATE_Z = (-0.22, -0.10)                        # the opening (centre -0.16): open to the sky (contract: an arch
TOWER2_C = (0.0, -0.27)                        # 0.24 high; the actors are 0.30-0.41 tall: SET.md), between the
GATE_DOOR_H = 0.24                             # front tower and a second tower at the back side of the gate
DOOR_T = 0.004                                 # the open gate doors stand in the gateway's edges
WIN_Z, WIN_Y, WIN_BACK = (-0.495, -0.425), (0.20, 0.27), 0.010
SHUTTER_Z = (-0.571, -0.501)
TORCHES = {"torch1": (-0.25, math.sqrt(TOWER_R ** 2 - 0.02 ** 2)), "torch2": (-0.07, math.sqrt(TOWER_R ** 2 - 0.03 ** 2))}
TORCH_TOP = 0.222                              # flame anchor (contract y 0.20: above the low zone of ROAD_E: SET.md)
# Ananias's house (front left, across Straight Street from the synagogue: the back row has no room for a 0.20-wide
# room, SET.md). Built at the old back-row depth (front AH_ZF0) and moved forward by AH_DZ; on the sheet it keeps its
# back-row place left of the synagogue (drawing shift AH_DRAW_DX)
AH_X, AH_ZF0, AH_T = (-0.60, -0.33), -0.32, 0.015   # inside x -0.585..-0.345 = 0.24 (was 0.11: Ananias is ~0.13,
                                                     # his elbows in `startle` still touched walls 0.20 apart)
AH_ZF = 0.20                                   # the open front (the floor ends at 0.21)
AH_DZ = AH_ZF - AH_ZF0
AH_DRAW_DX = -0.118
ROOM_H, ROOF_Z0, ROOF_T = 0.26, -0.52, 0.015   # walls; the flat roof only over the back strip z < -0.52: SET.md
AH_WIN = (-0.58, -0.51, 0.12, 0.19)            # x0 x1 y0 y1 in the back wall
AH_LEDGE = (-0.506, -0.476, 0.122)             # x0 x1 top, on the back wall
AH_STOOL = (-0.565, -0.545)
AH_LIGHT = (-0.465, 0.30, -0.45 + AH_DZ)       # FX anchor (ananiasHouse origin)
# synagogue
SYN_X, SYN_ZF, SYN_H, SYN_TOP = (-0.44, -0.30), -0.412, 0.30, 0.32   # facade z -0.40 -> -0.412: SET.md
STEPS = ((-0.412, -0.34, 0.04), (-0.34, -0.32, 0.0267), (-0.32, -0.30, 0.0133))
STEP_Y = 0.04
SYN_DOOR = (-0.402, -0.338, STEP_Y, 0.215)
SYN_COLS = (-0.425, -0.315)
# Judas's house (against the city wall)
JH_X, JH_ZF, JH_LW = (-0.29, -WT), -0.30, (-0.29, -0.275)           # left wall inner face -0.275: SET.md
JDOOR_X, JDOOR_Z, JDOOR_TOP = (-0.20,), -0.305, ROOM_H    # one post; the back gate tower is the other jamb: SET.md
JH_IN_Z1 = TOWER2_C[1] - math.sqrt(TOWER_R ** 2 - WT ** 2)   # the room's right wall ends at the tower (-0.312)
TABLE, TABLE_R, TABLE_TOP = (-0.07, -0.525), 0.04, 0.04   # contract (-0.06, -0.53): inside the city wall: SET.md
BASKET_R = 0.022
JAR, JAR_R, JAR_TOP = (-0.23, -0.53), 0.035, 0.10         # contract (-0.24, -0.55): SET.md
MAT_C, MAT_W, MAT_D = (-0.15, -0.46), 0.14, 0.095
# front left
WELL, WELL_R, WELL_H = (-0.51, -0.44), 0.04, 0.05   # back left (was front left, now Ananias's house): SET.md
# outside
ROCKS = (0.18, -0.20)                          # contract (0.30, -0.02): 0.02 from the S03 short guard: SET.md
MILESTONE = (0.24, 0.19)                       # contract (0.26, 0.18): 0.049 from ROAD_STOP: SET.md
PALM = (0.58, 0.16)
# Jerusalem
PORCH_X, PORCH_ZF, PORCH_Y = (0.375, 0.60), -0.36, 0.04   # x0 0.36 -> 0.375: SET.md
PSTEPS = ((0.42, 0.54, -0.36, -0.33, 0.03), (0.42, 0.54, -0.33, -0.30, 0.02))   # steps only x 0.42..0.54: SET.md
PCOLS = ((0.39, -0.37), (0.58, -0.37), (0.39, -0.565), (0.58, -0.565))
PROOF = (0.43, 0.45)                           # contract roof 0.32: the priest's head is at 0.40: SET.md
JHOUSE_X, JHOUSE_ZF, JHOUSE_H = (0.16, 0.32), -0.423, 0.24
JDOOR2 = (0.195, 0.285, 0.20, -0.52)           # door x0 x1 top (0.09 wide; contract 0.08: SET.md), dark room to -0.52


# ============================================================================================ marks and paths
HEAD = {"saul": 0.37, "ananias": 0.33, "barnabas": 0.39, "judas": 0.35, "priest": 0.36, "tallguard": 0.41,
        "shortguard": 0.30, "peter": 0.38}
G = 0.0
# label: (x, z, floor y, actor)    every mark of docs/saul/storyboard/story.py (staging, 2026-11-18)
MARKS = {
    "S01 saul 0.44,-0.10": (0.44, -0.10, G, "saul"), "SAUL_PORCH": (0.42, -0.24, G, "saul"),
    "S01 saul 0.46,-0.12": (0.46, -0.12, G, "saul"), "PRIEST": (0.47, -0.42, PORCH_Y, "priest"),
    "ROAD_A": (0.46, -0.22, G, "saul"), "ROAD_B": (0.48, -0.02, G, "saul"), "ROAD_C": (0.40, 0.12, G, "saul"),
    "ROAD_STOP": (0.30, 0.13, G, "saul"), "LIGHT": (0.18, 0.08, G, "saul"),
    "S02 short 0.38,-0.26": (0.38, -0.26, G, "shortguard"), "short 0.44,-0.04": (0.44, -0.04, G, "shortguard"),
    "short 0.44,0.08": (0.44, 0.08, G, "shortguard"),
    "S02 tall 0.56,-0.25": (0.56, -0.25, G, "tallguard"), "tall 0.53,-0.02": (0.53, -0.02, G, "tallguard"),
    "tall 0.53,0.03": (0.53, 0.03, G, "tallguard"),
    "S01 PACE_B": (0.52, -0.17, G, "saul"), "S03 saul 0.27,0.10": (0.27, 0.10, G, "saul"),
    "S03 short 0.40,0.05": (0.40, 0.05, G, "shortguard"), "S03 short 0.33,0.03": (0.33, 0.03, G, "shortguard"),
    "S03 tall 0.45,0.13": (0.45, 0.13, G, "tallguard"), "S03 tall 0.38,0.12": (0.38, 0.12, G, "tallguard"),
    "S05 tall 0.27,-0.05": (0.27, -0.05, G, "tallguard"),
    "ROAD_D": (0.13, -0.01, G, "tallguard"), "ROAD_E": (0.10, -0.10, G, "tallguard"),
    "GATE_OUT": (0.09, -0.16, G, "tallguard"), "GATE_IN": (-0.09, -0.16, G, "tallguard"),
    "S05 saul in the gate 0.05,-0.16": (0.05, -0.16, G, "saul"),
    "short LIGHT": (0.18, 0.08, G, "shortguard"),
    "SAUL_MAT": (-0.15, -0.46, G, "saul"), "JUDAS_IN": (-0.21, -0.37, G, "judas"),
    "ANANIAS_HOME": (-0.465, 0.08, G, "ananias"),
    "S08 ananias -0.30,-0.20": (-0.30, -0.20, G, "ananias"), "ananias -0.20,-0.23": (-0.20, -0.23, G, "ananias"),
    "JUDAS_DOOR": (-0.13, -0.27, G, "ananias"), "ANANIAS_TOUCH": (-0.08, -0.42, G, "ananias"),
    "ANANIAS_POUR": (-0.22, -0.42, G, "ananias"),
    "judas -0.08,-0.43": (-0.08, -0.43, G, "judas"), "JUDAS_SIDE": (-0.22, -0.42, G, "judas"),
    "SYN_STEP": (-0.37, -0.36, STEP_Y, "saul"),
    "S10 tall -0.165,-0.20": (-0.165, -0.20, G, "tallguard"), "S10 short -0.07,-0.19": (-0.07, -0.19, G, "shortguard"),
    "BASKET_DOWN": (0.095, -0.46, G, "saul"), "SAUL_BASKET": (0.095, -0.38, G, "saul"),
    "TALL_GATE": (0.12, -0.04, G, "tallguard"), "SHORT_GATE": (0.19, -0.11, G, "shortguard"),
    "S11 saul 0.13,-0.33": (0.13, -0.33, G, "saul"),
    "S12 saul 0.40,-0.06": (0.40, -0.06, G, "saul"), "S12 saul 0.40,-0.24": (0.40, -0.24, G, "saul"),
    "S12 saul 0.335,-0.30": (0.335, -0.30, G, "saul"), "JHOUSE_DOOR": (0.24, -0.33, G, "peter"),
    "S12 barnabas 0.14,0.02": (0.14, 0.02, G, "barnabas"), "S12 barnabas 0.30,-0.22": (0.30, -0.22, G, "barnabas"),
    "S13 ananias": (-0.27, 0.08, G, "ananias"), "S13 judas": (-0.17, 0.10, G, "judas"),
    "S13 saul": (-0.07, 0.10, G, "saul"), "S13 barnabas": (0.06, 0.10, G, "barnabas"),
    "S13 peter": (0.18, 0.10, G, "peter"), "S13 tall": (0.32, 0.10, G, "tallguard"),
    "S13 short": (0.44, 0.10, G, "shortguard"),
}
PATHS = [   # story.py straight moves between consecutive marks of one actor
    ("S01 saul", ["S01 saul 0.44,-0.10", "SAUL_PORCH", "S01 PACE_B", "SAUL_PORCH", "S01 saul 0.46,-0.12"]),
    ("S03 saul", ["S03 saul 0.27,0.10", "LIGHT"]),
    ("S03 short", ["S03 short 0.40,0.05", "S03 short 0.33,0.03"]),
    ("S03 tall", ["S03 tall 0.45,0.13", "S03 tall 0.38,0.12"]),
    ("S02 saul", ["ROAD_A", "ROAD_B", "ROAD_C", "ROAD_STOP", "LIGHT"]),
    ("S02 short", ["S02 short 0.38,-0.26", "short 0.44,-0.04", "short 0.44,0.08"]),
    ("S02 tall", ["S02 tall 0.56,-0.25", "tall 0.53,-0.02", "tall 0.53,0.03"]),
    ("S05 tall", ["S05 tall 0.27,-0.05", "ROAD_D", "ROAD_E", "GATE_OUT", "GATE_IN"]),
    ("S05 saul", ["LIGHT", "ROAD_D", "ROAD_E", "GATE_OUT", "S05 saul in the gate 0.05,-0.16"]),
    ("S05 short", ["S03 short 0.33,0.03", "short LIGHT", "ROAD_D"]),
    ("S08 ananias", ["S08 ananias -0.30,-0.20", "ananias -0.20,-0.23", "JUDAS_DOOR", "ANANIAS_TOUCH"]),
    ("S11 saul", ["SAUL_BASKET", "S11 saul 0.13,-0.33"]),
    ("S12 saul", ["S12 saul 0.40,-0.06", "S12 saul 0.40,-0.24", "S12 saul 0.335,-0.30"]),
    ("S12 barnabas", ["S12 barnabas 0.14,0.02", "S12 barnabas 0.30,-0.22"]),
]
# mark changes this set needs from the lead: none (all applied in story.py at staging)
PROPOSED = {}
TERRAIN = {"ground", "road", "straightStreet"}
HARD_PTS = [(v[0], v[1]) for v in MARKS.values()]
HARD_SEGS = [((MARKS[a][0], MARKS[a][1]), (MARKS[b][0], MARKS[b][1])) for _, ls in PATHS for a, b in zip(ls[:-1], ls[1:])]
SOFT_SEGS = []
BASKET_DOWN = (0.095, -0.46)
ROPE_TOP = (BASKET_DOWN[0] - 0.065, 0.235, BASKET_DOWN[1])   # CONTRACT §3: ropeTop rig-local (-0.065, 0.235, 0)

# demo colouring (DESIGN.md §3; regions DESIGN does not name: chosen here, SET.md §5)
COLOURS = {
    "wallStone": "#D9C08A", "window": "#3A2E2A", "wood": "#8A5A32",
    "plaster": "#F3E6C9", "floor": "#C9A97A", "roof": "#EBD2A6", "column": "#EFE4C8", "synDoor": "#3E8E86",
    "limestone": "#E9D6A8", "doorway": "#3A2E2A",
    "ground": "#DCC79A", "road": "#E8C98A", "street": "#E8DCC0",
    "straw": "#D8B26E", "bread": "#C98A4A", "jar": "#C46A3E", "mat": "#8E5A8C", "wellStone": "#C9C0B0",
    "rock": "#B9AFA2", "leaf": "#6E9A48",
    "hills": "#B9A86E", "jwall": "#E6D2A2", "iron": "#4A4A4A",
}
REGION_HEX = {}


# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model), faces with region, smooth flag, a
    no-raster flag (bits that sample a named texel) (as He Is Risen!)"""

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


def qx(mb, x, z0, z1, h0, h1, reg, sgn):
    """quad in the plane x = const, facing +x (sgn 1) or -x"""
    quad(mb, [(x, h0, z0), (x, h0, z1), (x, h1, z1), (x, h1, z0)], reg, (sgn, 0, 0))


def qz(mb, z, x0, x1, h0, h1, reg, sgn):
    quad(mb, [(x0, h0, z), (x1, h0, z), (x1, h1, z), (x0, h1, z)], reg, (0, 0, sgn))


def qy(mb, h, x0, x1, z0, z1, reg, sgn):
    quad(mb, [(x0, h, z0), (x1, h, z0), (x1, h, z1), (x0, h, z1)], reg, (0, sgn, 0))


def nrbox(mb, *a, **k):
    old = mb.nr; mb.nr = True
    box(mb, *a, **k)
    mb.nr = old


def holed_x(mb, x, z0, z1, h0, h1, hole, reg, sgn):
    """the plane x = const over z0..z1, h0..h1 with a rectangular hole (hz0, hz1, hh0, hh1)"""
    hz0, hz1, hh0, hh1 = hole
    qx(mb, x, z0, z1, h0, hh0, reg, sgn)
    qx(mb, x, z0, z1, hh1, h1, reg, sgn)
    qx(mb, x, z0, hz0, hh0, hh1, reg, sgn)
    qx(mb, x, hz1, z1, hh0, hh1, reg, sgn)


def holed_z(mb, z, x0, x1, h0, h1, hole, reg, sgn):
    hx0, hx1, hh0, hh1 = hole
    if hh0 > h0:
        qz(mb, z, x0, x1, h0, hh0, reg, sgn)
    qz(mb, z, x0, x1, hh1, h1, reg, sgn)
    qz(mb, z, x0, hx0, hh0, hh1, reg, sgn)
    qz(mb, z, hx1, x1, hh0, hh1, reg, sgn)


def prism_x(mb, x0, x1, poly, reg, end_nr=(False, False), skip_edges=(), edge_mb=None, edge_set=(), edge_reg=None):
    """solid along x (x0..x1) with cross-section poly [(z, h)...]; the end faces at x0 / x1 get the no-raster flags
    end_nr (None = left out); side edge i (poly[i] -> poly[i + 1]) is left out when i in skip_edges, and goes to
    edge_mb (region edge_reg) when i in edge_set"""
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n)) / 2
    tris = tessellate_polygon([[Vector((z, h, 0)) for z, h in poly]])
    for k, (x, o) in enumerate(((x0, -1), (x1, 1))):
        if end_nr[k] is None:
            continue
        old = mb.nr; mb.nr = end_nr[k]
        ids = [mb.v(x, h, z) for z, h in poly]
        for t in tris:
            mb.fo([ids[i] for i in t], reg, (o, 0, 0))
        mb.nr = old
    for i in range(n):
        if i in skip_edges:
            continue
        m = edge_mb if (i in edge_set and edge_mb is not None) else mb
        r = edge_reg if (i in edge_set and edge_reg) else reg
        j = (i + 1) % n
        (za, ha), (zb, hb) = poly[i], poly[j]
        dz, dh = zb - za, hb - ha
        oz, oh = (dh, -dz) if area > 0 else (-dh, dz)
        m.fo([m.v(x0, ha, za), m.v(x1, ha, za), m.v(x1, hb, zb), m.v(x0, hb, zb)], r, (0, oh, oz))


def merlon_poly(zc, w, h0, top, n=8):
    """cross-section (z, h) of one rounded merlon: a block with a half-round top"""
    r = w / 2
    pts = [(zc - r, h0), (zc + r, h0)]
    for k in range(n + 1):
        a = math.pi * k / n
        pts.append((zc + r * math.cos(a), top - r + r * math.sin(a)))
    return pts


def lamp_mesh(mb, x, h, z, reg="jar", toward=1):
    """a small clay oil lamp, nozzle toward +x (toward=1) or -x; returns the wick point"""
    lathe(mb, [(0.0, 0.0), (0.007, 0.0), (0.010, 0.004), (0.009, 0.008), (0.004, 0.009), (0.0, 0.009)], reg,
          C=(x, h, z), seg=10, sx=1.4)
    tube(mb, [(x + toward * 0.009, h + 0.005, z), (x + toward * 0.017, h + 0.007, z)], 0.003, reg, seg=6)
    return (x + toward * 0.017, h + 0.010, z)


def flat_slab(mb, outline, h0, h1, reg):
    """flat polygon (x, z) slab from h0 to h1"""
    ngon_top(mb, outline, h1, reg, hb=h0)


# ============================================================================================ city wall
def tower(mb, c):
    """a round tower r 0.05 (body to 0.315, nine rounded merlons to 0.34)"""
    tx, tz = c
    lathe(mb, [(0.0, 0.0), (TOWER_R, 0.0), (TOWER_R, TOWER_BODY), (0.0, TOWER_BODY)], "wallStone",
          C=(tx, 0.0, tz), seg=28, smooth=True)
    for k in range(9):
        a = TAU * (k + 0.5) / 9
        cx, cz = tx + (TOWER_R - 0.012) * math.cos(a), tz + (TOWER_R - 0.012) * math.sin(a)
        lathe(mb, [(0.0, TOWER_BODY - 0.002), (0.011, TOWER_BODY - 0.002), (0.011, TOWER_TOP - 0.011),
                   (0.008, TOWER_TOP - 0.003), (0.0, TOWER_TOP)], "wallStone", C=(cx, 0.0, cz), seg=10, smooth=True)


def build_city_wall(root):
    """`cityWall` (the back segment with the window hole, two round towers flanking the open gateway, a short front
    segment, rounded battlements) with children `cityGate` (the two open doors standing in the gateway's edges),
    `wallWindow` (recess, dark back, shutter), `torch1`, `torch2`. Outside face (+x) printed in the `wall` drawing;
    the inside face is one wall-stone texel (except inside Judas's house: judasHouse)"""
    mb, gm = MB(), MB()
    z0b, z1b = WALL_Z0, TOWER2_C[1]
    # back segment: outside face with the window hole, top, back end; the inside face only in front of Judas's room
    holed_x(mb, WT, z0b, z1b, 0.0, WALL_BODY, (WIN_Z[0], WIN_Z[1], WIN_Y[0], WIN_Y[1]), "wallStone", 1)
    qy(mb, WALL_BODY, -WT, WT, z0b, z1b, "wallStone", 1)
    mb.nr = True
    qx(mb, -WT, z0b, JH_IN_Z1, ROOM_H, WALL_BODY, "wallStone", -1)              # above Judas's room walls
    qz(mb, z0b, -WT, WT, 0.0, WALL_BODY, "wallStone", -1)
    mb.nr = False
    n = int(round((z1b - z0b - TOWER_R) / 0.05))
    for k in range(n):
        zc = z0b + (k + 0.5) * (z1b - TOWER_R - z0b) / n
        prism_x(mb, -WT, WT, merlon_poly(zc, 0.028, WALL_BODY, MERLON_TOP), "wallStone", end_nr=(True, False),
                skip_edges=(0,))
    # front segment between the gateway and the front tower (its end face is the gateway's front edge)
    g0, g1 = GATE_Z
    box(mb, -WT, WT, 0.0, WALL_BODY, g1, TOWER_C[1], "wallStone", skip=("bottom", "front"))
    tower(mb, TOWER_C)
    tower(mb, TOWER2_C)
    # drawn lines (the region is decorOnly in `wall`): block courses, the top edge, tower courses and edges
    dec = DECOR.setdefault("wall", [])
    xf = WT + 0.0005
    zw1 = TOWER2_C[1] - math.sqrt(TOWER_R ** 2 - WT ** 2)                    # where the back tower meets the wall face
    rows = list(np.arange(0.0, WALL_BODY - 0.01, 0.047)) + [WALL_BODY]
    band = (WIN_Y[0] - 0.004, WIN_Y[1] + 0.004)
    blocked = (SHUTTER_Z[0] - 0.004, WIN_Z[1] + 0.004)                    # shutter + window
    for h in rows[1:-1]:
        segs = [(z0b + 0.003, blocked[0]), (blocked[1], zw1)] if band[0] < h < band[1] else [(z0b + 0.003, zw1)]
        for za, zb in segs:
            dec.append(((xf, h, za), (xf, h, zb)))
    for j, (ha, hb) in enumerate(zip(rows[:-1], rows[1:])):
        for z in np.arange(z0b + 0.03 + 0.035 * (j % 2), zw1 - 0.01, 0.07):
            if blocked[0] < z < blocked[1] and hb > band[0] and ha < band[1]:
                continue
            dec.append(((xf, ha + 0.003, z), (xf, hb - 0.003, z)))
    dec.append(((xf, WALL_BODY, z0b + 0.002), (xf, WALL_BODY, zw1)))
    for c in (TOWER_C, TOWER2_C):                                           # tower courses (front half, seen from +x)
        tx, tz = c
        for h in np.arange(0.06, TOWER_BODY - 0.02, 0.06):
            pts = [(tx + TOWER_R * 1.01 * math.cos(a), h, tz + TOWER_R * 1.01 * math.sin(a))
                   for a in np.linspace(-1.2, 1.2, 9)]
            for p0, p1 in zip(pts[:-1], pts[1:]):
                dec.append((p0, p1))
    dec.append(((xf + 0.002, 0.002, zw1), (xf + 0.002, TOWER_BODY, zw1)))   # back tower against the wall
    wall = make_obj("cityWall", mb, root, origin=(TOWER_C[0], TOWER_TOP, TOWER_C[1]), smooth_angle=35)
    # cityGate: the two open doors standing in the gateway's edges, iron straps (named texels)
    gm.nr = True
    for zr, s in ((g0 + DOOR_T, 1), (g1 - DOOR_T, -1)):
        za, zb = min(zr, zr - s * DOOR_T), max(zr, zr - s * DOOR_T)
        box(gm, -WT + 0.003, WT - 0.003, 0.0, GATE_DOOR_H, za, zb, "wood", skip=("bottom",))
        for h in (0.05, GATE_DOOR_H - 0.06):
            zs = (zb, zb + 0.0015) if s == 1 else (za - 0.0015, za)
            box(gm, -WT + 0.006, WT - 0.006, h, h + 0.012, zs[0], zs[1], "iron", skip=("bottom",))
    gm.nr = False
    gate = make_obj("cityGate", gm, wall, origin=(0.0, 0.0, (g0 + g1) / 2), smooth_angle=30)
    # wallWindow: reveals + dark back, shutter folded open on the outside face (printed wood)
    wm = MB()
    (wz0, wz1), (wy0, wy1) = WIN_Z, WIN_Y
    wm.nr = True
    qy(wm, wy0, WIN_BACK, WT, wz0, wz1, "window", 1)
    qy(wm, wy1, WIN_BACK, WT, wz0, wz1, "window", -1)
    qz(wm, wz0, WIN_BACK, WT, wy0, wy1, "window", 1)
    qz(wm, wz1, WIN_BACK, WT, wy0, wy1, "window", -1)
    wm.nr = False
    qx(wm, WIN_BACK, wz0, wz1, wy0, wy1, "window", 1)
    sz0, sz1 = SHUTTER_Z
    box(wm, WT, WT + 0.004, wy0 - 0.002, wy1 + 0.002, sz0, sz1, "wood", skip=("left",))
    for zz in (sz0 + 0.023, sz0 + 0.047):                                   # planks
        DECOR["wall"].append(((WT + 0.0045, wy0 + 0.002, zz), (WT + 0.0045, wy1 - 0.002, zz)))
    window = make_obj("wallWindow", wm, wall, origin=(WT, (wy0 + wy1) / 2, (wz0 + wz1) / 2), smooth_angle=30)
    torches = []
    for name, (z, xs) in TORCHES.items():
        t = MB(); t.nr = True
        xh = xs + 0.016
        tube(t, [(xs - 0.002, 0.186, z), (xh, 0.186, z)], 0.0028, "iron", seg=6)
        tube(t, [(xh, 0.180, z), (xh, TORCH_TOP - 0.012, z)], 0.0042, "wood", seg=8)
        lathe(t, [(0.0, TORCH_TOP - 0.016), (0.0075, TORCH_TOP - 0.014), (0.0085, TORCH_TOP - 0.006),
                  (0.006, TORCH_TOP - 0.001), (0.0, TORCH_TOP)], "straw", C=(xh, 0.0, z), seg=10)
        lathe(t, [(0.0058, 0.182), (0.0064, 0.190), (0.0, 0.1905)], "iron", C=(xh, 0.0, z), seg=8)   # cup
        t.nr = False
        torches.append(make_obj(name, t, wall, origin=(xh, TORCH_TOP, z), smooth_angle=40))
    return wall, gate, window, torches


# ============================================================================================ Ananias's house
def build_ananias(root):
    """`ananiasHouse`: the small doll's-house room x -0.60..-0.46, z -0.5875..-0.32, open front (no sill), walls
    0.015 thick, h 0.26, the flat roof only over the back strip; inside a stool, a lamp on a ledge, a rolled mat,
    a window in the back wall. Inside faces printed (`street`), outside faces one limestone texel"""
    mb = MB()
    x0, x1 = AH_X
    ix0, ix1 = x0 + AH_T, x1 - AH_T
    zf, zb = AH_ZF0, WB[1]
    nrbox(mb, x0, ix0, 0.0, ROOM_H, WB[0], zf, "limestone", skip=("right", "bottom"))
    nrbox(mb, ix1, x1, 0.0, ROOM_H, WB[0], zf, "limestone", skip=("left", "bottom"))
    nrbox(mb, ix0, ix1, 0.0, ROOM_H, WB[0], zb, "limestone", skip=("front", "bottom", "left", "right"))
    qx(mb, ix0, zb, zf, 0.0, ROOM_H, "plaster", 1)
    qx(mb, ix1, zb, zf, 0.0, ROOM_H, "plaster", -1)
    wx0, wx1, wy0, wy1 = AH_WIN
    holed_z(mb, zb, ix0, ix1, 0.0, ROOM_H, (wx0, wx1, wy0, wy1), "plaster", 1)
    wd = zb - 0.008                                                         # the window recess (dark)
    qz(mb, wd, wx0, wx1, wy0, wy1, "window", 1)
    qx(mb, wx0, wd, zb, wy0, wy1, "window", 1); qx(mb, wx1, wd, zb, wy0, wy1, "window", -1)
    qy(mb, wy0, wx0, wx1, wd, zb, "window", 1); qy(mb, wy1, wx0, wx1, wd, zb, "window", -1)
    qy(mb, 0.0025, ix0, ix1, zb, zf, "floor", 1)
    nrbox(mb, x0, x1, ROOM_H, ROOM_H + ROOF_T, WB[0], ROOF_Z0, "roof")
    mb.nr = True
    lx0, lx1, ltop = AH_LEDGE
    box(mb, lx0, lx1, ltop - 0.007, ltop, zb, zb + 0.014, "plaster", skip=("back",))
    lamp_mesh(mb, (lx0 + lx1) / 2 - 0.004, ltop, zb + 0.007, toward=1)
    sx, sz = AH_STOOL
    lathe(mb, [(0.0, 0.0), (0.011, 0.0), (0.010, 0.028), (0.015, 0.030), (0.015, 0.036), (0.0, 0.036)], "wood",
          C=(sx, 0.0, sz), seg=12)
    tube(mb, [(-0.535, 0.0095, zb + 0.012), (-0.492, 0.0095, zb + 0.012)], 0.0095, "mat", seg=10)
    mb.nr = False
    for i, (x, h, z) in enumerate(mb.V):                                    # move forward; the drawing keeps the
        mb.P[i] = (x + AH_DRAW_DX, h, z)                                    # back-row place left of the synagogue
        mb.V[i] = (x, h, z + AH_DZ)
    return make_obj("ananiasHouse", mb, root, origin=AH_LIGHT, smooth_angle=35)


# ============================================================================================ synagogue
def build_synagogue(root):
    """`synagogue`: facade x -0.44..-0.30 at z -0.412 (h 0.30, cornice to 0.32), two engaged columns, a door, a
    lintel with rosettes (no letters), three steps z -0.412..-0.30 (top step y 0.04)"""
    mb = MB()
    x0, x1 = SYN_X
    zf = SYN_ZF
    dx0, dx1, dy0, dy1 = SYN_DOOR
    holed_z(mb, zf, x0, x1, STEP_Y, SYN_H, (dx0, dx1, dy0, dy1), "column", 1)
    qx(mb, x0, WB[0], zf, 0.0, SYN_H, "column", -1); qx(mb, x1, WB[0], zf, 0.0, SYN_H, "column", 1)
    qy(mb, SYN_H, x0, x1, WB[0], zf, "column", 1)
    dd = zf - 0.007                                                         # the door, set back a little
    qz(mb, dd, dx0, dx1, dy0, dy1, "synDoor", 1)
    qx(mb, dx0, dd, zf, dy0, dy1, "column", 1); qx(mb, dx1, dd, zf, dy0, dy1, "column", -1)
    qy(mb, dy1, dx0, dx1, dd, zf, "column", -1)
    box(mb, x0 - 0.008, x1 + 0.008, SYN_H, SYN_TOP, WB[0], zf + 0.008, "column", skip=("bottom",))   # cornice
    box(mb, x0, x1, 0.232, 0.270, zf, zf + 0.005, "column", skip=("back",))                         # lintel band
    for k, xr in enumerate(np.linspace(-0.405, -0.335, 4)):                  # rosettes (no letters)
        lathe(mb, [(0.0, 0.0), (0.0085, 0.0), (0.0085, 0.0025), (0.004, 0.0035), (0.0, 0.0035)], "column",
              C=(xr, 0.251, zf + 0.005), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=10, smooth=False)
    for xc in SYN_COLS:                                                     # engaged columns
        lathe(mb, [(0.018, STEP_Y), (0.018, STEP_Y + 0.010), (0.0135, STEP_Y + 0.014), (0.0135, 0.215),
                   (0.018, 0.222), (0.018, 0.232)], "column", C=(xc, 0.0, zf), seg=16, smooth=True)
    for z0, z1, h in STEPS:
        box(mb, x0, x1, 0.0, h, z0, z1, "column", skip=("bottom", "back"))
    return make_obj("synagogue", mb, root, origin=(-0.37, STEP_Y, zf), smooth_angle=35)


# ============================================================================================ Judas's house
def build_judas(root, wall):
    """`judasHouse` (the room x -0.285..-0.027 against the city wall, open front with a threshold stripe, walls h
    0.26, the flat roof only over the back strip, a low table, the dark inside of the basket window) with children
    `judasDoor` (door frame), `prayerMat`, `breadBasket` (on the table), `waterJar`"""
    mb = MB()
    lw0, lw1 = JH_LW
    xr = -WT
    zf, zb = JH_ZF, WB[1]
    nrbox(mb, lw0, lw1, 0.0, ROOM_H, WB[0], zf, "limestone", skip=("right", "bottom"))
    nrbox(mb, lw1, xr, 0.0, ROOM_H, WB[0], zb, "limestone", skip=("front", "bottom", "left", "right"))
    qx(mb, lw1, zb, zf, 0.0, ROOM_H, "plaster", 1)
    qz(mb, zb, lw1, xr, 0.0, ROOM_H, "plaster", 1)
    qx(mb, xr, zb, JH_IN_Z1, 0.0, ROOM_H, "plaster", -1)                     # the city wall's inside face
    qx(mb, xr - 0.0006, WIN_Z[0], WIN_Z[1], WIN_Y[0], WIN_Y[1], "window", -1)  # the basket window from inside
    qy(mb, 0.0025, lw1, xr, zb, zf, "floor", 1)
    nrbox(mb, lw0, xr, ROOM_H, ROOM_H + ROOF_T, WB[0], ROOF_Z0, "roof", skip=("right",))
    mb.nr = True
    box(mb, lw1, xr, 0.0, 0.004, zf - 0.010, zf, "limestone", skip=("bottom",))   # threshold stripe
    tx, tz = TABLE                                                          # the low table
    lathe(mb, [(0.0, TABLE_TOP - 0.007), (TABLE_R, TABLE_TOP - 0.007), (TABLE_R, TABLE_TOP), (0.0, TABLE_TOP)], "wood",
          C=(tx, 0.0, tz), seg=20, smooth=False)
    for k in range(3):
        a = TAU * k / 3 + 0.5
        tube(mb, [(tx + 0.026 * math.cos(a), 0.0, tz + 0.026 * math.sin(a)),
                  (tx + 0.024 * math.cos(a), TABLE_TOP - 0.007, tz + 0.024 * math.sin(a))], 0.004, "wood", seg=6)
    mb.nr = False
    house = make_obj("judasHouse", mb, root, origin=(-0.155, 0.0, -0.44), smooth_angle=35)
    # judasDoor: posts and lintel on the open front (named wood texel)
    dm = MB(); dm.nr = True
    for x in JDOOR_X:
        box(dm, x - 0.006, x + 0.006, 0.0, JDOOR_TOP, JDOOR_Z - 0.006, JDOOR_Z + 0.006, "wood", skip=("bottom",))
        box(dm, x - 0.009, x + 0.009, JDOOR_TOP, JDOOR_TOP + 0.008, JDOOR_Z - 0.009, JDOOR_Z + 0.009, "wood")
    dm.nr = False
    door = make_obj("judasDoor", dm, house, origin=(JDOOR_X[0], 0.0, JDOOR_Z), smooth_angle=30)
    # prayerMat (props drawing): a flat rug with a border
    pm = MB()
    mx, mz = MAT_C
    rr = [(mx - MAT_W / 2, mz - MAT_D / 2), (mx + MAT_W / 2, mz - MAT_D / 2), (mx + MAT_W / 2, mz + MAT_D / 2),
          (mx - MAT_W / 2, mz + MAT_D / 2)]
    flat_slab(pm, rr, 0.0025, 0.0065, "mat")
    pm.remap((mx, 0.0, mz), PROPS["prayerMat"][0], PROPS["prayerMat"][1])
    mat = make_obj("prayerMat", pm, house, origin=(mx, 0.0, mz), smooth_angle=30)
    # breadBasket on the table: a round straw basket with three loaves (props drawing, enlarged)
    bm = MB()
    lathe(bm, [(0.0, 0.0), (0.016, 0.0), (BASKET_R, 0.015), (BASKET_R + 0.002, 0.024), (BASKET_R - 0.002, 0.025),
               (BASKET_R - 0.004, 0.021), (0.0, 0.021)], "straw", C=(tx, TABLE_TOP, tz), seg=20, smooth=True)
    for k, (dx, dz, a) in enumerate(((-0.007, 0.004, 0.3), (0.008, 0.002, -0.4), (0.0, -0.008, 1.3))):
        lumpy(bm, (tx + dx, TABLE_TOP + 0.023, tz + dz), 0.0085, "bread", seg=10, rings=6, sh=0.6, sx=1.45,
              amp=0.05, seed=k + 3)
    bm.remap((tx, TABLE_TOP, tz), PROPS["breadBasket"][0], PROPS["breadBasket"][1])
    at, kb = PROPS["breadBasket"]
    dec = DECOR.setdefault("props", [])
    for h, r in ((0.008, 0.0192),):                                          # one weave band on the front
        for a0 in np.linspace(math.radians(30), math.radians(150), 7)[:-1]:
            a1 = a0 + math.radians(11)
            p0 = (at[0] + kb * (r + 0.0006) * math.cos(a0), at[1] + kb * h, at[2] + kb * (r + 0.0006) * math.sin(a0))
            p1 = (at[0] + kb * (r + 0.0006) * math.cos(a1), at[1] + kb * h, at[2] + kb * (r + 0.0006) * math.sin(a1))
            dec.append((p0, p1))
    basket = make_obj("breadBasket", bm, house, origin=(tx, TABLE_TOP, tz), smooth_angle=50)
    # waterJar: a big terracotta jar, two handles
    jx, jz = JAR
    jm = MB()
    lathe(jm, [(0.0, 0.0), (0.017, 0.0), (0.030, 0.022), (JAR_R, 0.045), (0.030, 0.075), (0.016, 0.090),
               (0.013, 0.094), (0.0175, 0.098), (0.018, JAR_TOP), (0.0, JAR_TOP - 0.002)], "jar", C=(jx, 0.0, jz),
          seg=18)
    for s in (-1, 1):
        tube(jm, [(jx + s * 0.014, 0.090, jz), (jx + s * 0.030, 0.086, jz), (jx + s * 0.028, 0.068, jz)], 0.0035, "jar",
             seg=6)
    jm.remap((jx, 0.0, jz), PROPS["waterJar"][0], PROPS["waterJar"][1])
    jar = make_obj("waterJar", jm, house, origin=(jx, 0.0, jz), smooth_angle=50)
    return house, door, mat, basket, jar


# ============================================================================================ well, rocks, palm
def build_well(root):
    """`well` (round stone ring r 0.04, h 0.05, dark water inside, a bucket on the rim) + two pots and a crate"""
    mb = MB()
    wx, wz = WELL
    lathe(mb, [(0.0, 0.0), (WELL_R, 0.0), (WELL_R, WELL_H - 0.004), (WELL_R - 0.003, WELL_H), (0.0325, WELL_H),
               (0.030, WELL_H - 0.003), (0.030, 0.043), (0.0, 0.043)], "wellStone", C=(wx, 0.0, wz), seg=22)
    mb.nr = True
    lathe(mb, [(0.0, 0.044), (0.0302, 0.044), (0.0, 0.0441)], "window", C=(wx, 0.0, wz), seg=22, smooth=False)
    mb.nr = False
    mb.nr = True
    bx, bz = wx + 0.026, wz + 0.020                                         # bucket on the rim
    lathe(mb, [(0.0, WELL_H), (0.009, WELL_H), (0.011, WELL_H + 0.017), (0.0095, WELL_H + 0.017),
               (0.0, WELL_H + 0.016)], "wood", C=(bx, 0.0, bz), seg=10)
    for (px, pz, r, h) in ((wx - 0.068, wz + 0.028, 0.018, 0.045), (wx - 0.072, wz - 0.028, 0.014, 0.036)):
        lathe(mb, [(0.0, 0.0), (r * 0.6, 0.0), (r, h * 0.45), (r * 0.65, h * 0.85), (r * 0.5, h * 0.92),
                   (r * 0.6, h), (0.0, h * 0.97)], "jar", C=(px, 0.0, pz), seg=12)
    box(mb, wx - 0.035, wx + 0.005, 0.0, 0.04, wz - 0.10, wz - 0.065, "wood", skip=("bottom",))   # market crate
    mb.nr = False
    mb.remap((wx, 0.0, wz), PROPS["well"][0], PROPS["well"][1])
    return make_obj("well", mb, root, origin=(wx, 0.0, wz), smooth_angle=40)


def build_rocks(root):
    """`rocks`: low desert rocks at (0.18, -0.20) (h <= 0.05) and two small bushes beside them (h <= 0.04)"""
    mb = MB()
    rx, rz = ROCKS
    lumpy(mb, (rx, 0.012, rz), 0.035, "rock", seg=12, rings=7, sh=1.05, sz=0.8, amp=0.16, seed=2, flat_bottom=0.0)
    lumpy(mb, (rx - 0.03, 0.006, rz - 0.010), 0.018, "rock", seg=10, rings=6, sh=0.9, amp=0.18, seed=5, flat_bottom=0.0)
    mb.remap((rx, 0.0, rz), PROPS["rocks"][0], PROPS["rocks"][1])
    i0 = len(mb.V)
    for k, (bx, bz, r) in enumerate(((0.225, -0.25, 0.020), (0.195, -0.272, 0.016))):
        lumpy(mb, (bx, r * 0.8, bz), r, "leaf", seg=12, rings=7, sh=0.9, amp=0.22, seed=k + 8, flat_bottom=0.0)
    mb.remap((0.21, 0.0, -0.26), PROPS["bushes"][0], PROPS["bushes"][1], i0)
    return make_obj("rocks", mb, root, origin=(rx, 0.0, rz), smooth_angle=50)


def build_milestone(root):
    """`milestone`: a small round-topped stone (h 0.075), one rock texel"""
    mb = MB(); mb.nr = True
    mx, mz = MILESTONE
    lathe(mb, [(0.0, 0.0), (0.016, 0.0), (0.016, 0.05), (0.013, 0.064), (0.007, 0.073), (0.0, 0.075)], "rock",
          C=(mx, 0.0, mz), seg=14, sv=0.62)
    mb.nr = False
    return make_obj("milestone", mb, root, origin=(mx, 0.0, mz), smooth_angle=50)


def build_palm(root):
    """`palm` at the front-right corner (0.58, 0.16): trunk r <= 0.02 (wood texel), crown underside >= 0.30, crown
    only beyond x 0.50 (printed in `props`)"""
    mb = MB()
    px, pz = PALM
    top = (0.572, 0.355, 0.152)
    mb.nr = True
    tube(mb, [(px + 0.004, 0.0, pz + 0.004), (px + 0.002, 0.12, pz), (px - 0.004, 0.25, pz - 0.004), top],
         [0.018, 0.015, 0.012, 0.010], "wood", seg=10)
    for h in np.arange(0.04, 0.32, 0.045):                                  # trunk rings
        f = h / top[1]
        cx, cz = px + 0.004 + (top[0] - px - 0.004) * f, pz + 0.004 + (top[2] - pz - 0.004) * f
        r = 0.018 - 0.008 * f
        lathe(mb, [(r - 0.001, h - 0.004), (r + 0.0025, h + 0.002), (r - 0.001, h + 0.006)], "wood",
              C=(cx, 0.0, cz), seg=10)
    mb.nr = False
    i0 = len(mb.V)
    for k in range(8):                                                      # fronds
        a = TAU * k / 8 + 0.2
        dx, dz = math.cos(a), math.sin(a)
        L = 0.085
        if dx < 0:
            L = min(L, (top[0] - 0.542) / -dx)
        if dx > 0:
            L = min(L, (0.612 - top[0]) / dx)
        if dz > 0:
            L = min(L, (0.207 - top[2]) / dz)
        pts = [top, (top[0] + dx * L * 0.45, top[1] + 0.022, top[2] + dz * L * 0.45),
               (top[0] + dx * L * 0.80, top[1] - 0.006, top[2] + dz * L * 0.80),
               (top[0] + dx * L, top[1] - 0.040, top[2] + dz * L)]
        blade(mb, pts, [0.010, 0.030, 0.022, 0.0], "leaf", nrm=(0, 1, 0))
    lumpy(mb, (top[0], top[1] + 0.004, top[2]), 0.016, "leaf", seg=10, rings=6, sh=0.8, amp=0.1, seed=3)
    for i in range(len(mb.N)):
        mb.N[i] = True                                                      # crown: one leaf texel (the bushes)
    return make_obj("palm", mb, root, origin=(px, 0.0, pz), smooth_angle=55)


# ============================================================================================ Jerusalem
def build_porch(root):
    """`priestPorch`: raised porch x 0.375..0.60, z -0.5875..-0.36, floor 0.04, two steps (x 0.42..0.54, z
    -0.36..-0.30), four columns, a back wall, a flat roof 0.47..0.49"""
    mb = MB()
    x0, x1 = PORCH_X
    box(mb, x0, x1, 0.0, PORCH_Y, WB[0], PORCH_ZF, "limestone", skip=("bottom", "back"))
    for sx0, sx1, sz0, sz1, h in PSTEPS:
        box(mb, sx0, sx1, 0.0, h, sz0, sz1, "limestone", skip=("bottom", "back"))
    box(mb, x0, x1, PORCH_Y, PROOF[0], WB[0], WB[1], "limestone", skip=("bottom", "back", "top"))
    for cx, cz in PCOLS:
        lathe(mb, [(0.017, PORCH_Y), (0.017, PORCH_Y + 0.012), (0.012, PORCH_Y + 0.018), (0.012, PROOF[0] - 0.018),
                   (0.017, PROOF[0] - 0.010), (0.017, PROOF[0])], "limestone", C=(cx, 0.0, cz), seg=14)
    box(mb, x0 - 0.004, x1, PROOF[0], PROOF[1], WB[0], PORCH_ZF + 0.006, "roof", skip=("back",))
    dec = DECOR.setdefault("jerusalem", [])
    return make_obj("priestPorch", mb, root, origin=(0.48, PORCH_Y, -0.47), smooth_angle=35)


def build_jhouse(root):
    """`jerusalemHouse` (x 0.16..0.32, z -0.5875..-0.423, h 0.24, flat roof with a low parapet, a dark window in the
    right face) with child `jerusalemDoor` (the open doorway at x 0.20..0.28, top 0.20: dark room, the leaf folded
    back inside against the left reveal)"""
    mb = MB()
    x0, x1 = JHOUSE_X
    zf, H = JHOUSE_ZF, JHOUSE_H
    d0, d1, dt, dback = JDOOR2
    holed_z(mb, zf, x0, x1, 0.0, H, (d0, d1, 0.0, dt), "limestone", 1)
    qx(mb, x0, WB[0], zf, 0.0, H, "limestone", -1)
    wz = (-0.525, -0.470, 0.10, 0.16)
    holed_x(mb, x1, WB[0], zf, 0.0, H, wz, "limestone", 1)
    mb.nr = True
    qx(mb, x1 - 0.008, wz[0], wz[1], wz[2], wz[3], "doorway", 1)
    qy(mb, wz[2], x1 - 0.008, x1, wz[0], wz[1], "doorway", 1); qy(mb, wz[3], x1 - 0.008, x1, wz[0], wz[1], "doorway", -1)
    qz(mb, wz[0], x1 - 0.008, x1, wz[2], wz[3], "doorway", 1); qz(mb, wz[1], x1 - 0.008, x1, wz[2], wz[3], "doorway", -1)
    mb.nr = False
    qy(mb, H, x0, x1, WB[0], zf, "roof", 1)
    for (a0, a1, b0, b1) in ((x0, x1, zf - 0.010, zf), (x0, x0 + 0.010, WB[0], zf), (x1 - 0.010, x1, WB[0], zf)):
        box(mb, a0, a1, H, H + 0.012, b0, b1, "limestone", skip=("bottom",))
    house = make_obj("jerusalemHouse", mb, root, origin=((x0 + x1) / 2, 0.0, (WB[0] + zf) / 2), smooth_angle=35)
    dm = MB()
    qz(dm, dback, d0, d1, 0.0, dt, "doorway", 1)
    qy(dm, 0.0012, d0, d1, dback, zf, "doorway", 1)
    dm.nr = True
    qy(dm, dt, d0, d1, dback, zf, "doorway", -1)
    dm.nr = False
    qx(dm, d0, dback, zf, 0.0, dt, "doorway", 1); qx(dm, d1, dback, zf, 0.0, dt, "doorway", -1)
    dm.nr = True
    box(dm, d0 + 0.0015, d0 + 0.0055, 0.003, dt - 0.006, zf - 0.078, zf - 0.002, "wood")       # the open leaf
    dm.nr = False
    door = make_obj("jerusalemDoor", dm, house, origin=((d0 + d1) / 2, dt / 2, zf), smooth_angle=30)
    return house, door


# ============================================================================================ ground, road, street
def road_poly():
    cl = catmull([(0.485, -0.300), (0.492, -0.15), (0.490, -0.02), (0.462, 0.072), (0.385, 0.104), (0.28, 0.106),
                  (0.19, 0.096), (0.135, 0.060), (0.108, -0.020), (0.090, -0.100), (0.060, -0.160), (0.020, -0.160)],
                 0.012)
    return strip_poly(cl, 0.14, 0.14)


GAPS = ((SYN_X[1] - 0.001, JH_X[0] + 0.001),)   # thin gaps between buildings
STREET = np.array([(FLOOR[0], -0.28), (WT, -0.28), (WT, -0.08), (FLOOR[0], -0.08)])
FOOT = [np.array(p) for p in (
    [(AH_X[0], AH_ZF), (AH_X[1], AH_ZF), (AH_X[1], WB[0] + AH_DZ), (AH_X[0], WB[0] + AH_DZ)],
    [(SYN_X[0], STEPS[-1][1]), (SYN_X[1], STEPS[-1][1]), (SYN_X[1], FLOOR[2]), (SYN_X[0], FLOOR[2])],
    [(JH_X[0], JH_ZF), (WT, JH_ZF), (WT, FLOOR[2]), (JH_X[0], FLOOR[2])],
    [(-WT, GATE_Z[1]), (WT, GATE_Z[1]), (WT, -0.06), (-WT, -0.06)],
    [(PORCH_X[0], PORCH_ZF), (PORCH_X[1], PORCH_ZF), (PORCH_X[1], FLOOR[2]), (PORCH_X[0], FLOOR[2])],
    [(JHOUSE_X[0], JHOUSE_ZF), (JHOUSE_X[1], JHOUSE_ZF), (JHOUSE_X[1], FLOOR[2]), (JHOUSE_X[0], FLOOR[2])],
)] + [np.array([(c[0] + TOWER_R * math.cos(a), c[1] + TOWER_R * math.sin(a))
                for a in np.linspace(0, TAU, 24, endpoint=False)]) for c in (TOWER_C, TOWER2_C)]


def land_h(x, z, reg):
    base = {"street": 0.0030, "road": 0.0026, "ground": 0.0020}[reg]
    return base + 0.0004 * (nz(x * 7, z * 7) - 0.5)


def build_ground(root):
    """`ground`, `road`, `straightStreet` from one constrained triangulation of the floor (building footprints out)"""
    rp = road_poly()
    outlines = [_resample(np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]),
                                    (FLOOR[0], FLOOR[2])]), 0.02)]
    outlines += [_resample(p, 0.015) for p in FOOT] + [_resample(rp, 0.010), _resample(STREET, 0.012)]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    allo = np.concatenate(outlines)
    for j, z in enumerate(np.arange(FLOOR[2] + 0.01, FLOOR[3] - 0.005, 0.02)):
        for x in np.arange(FLOOR[0] + 0.01 + (j % 2) * 0.01, FLOOR[1] - 0.005, 0.02):
            p = np.array([x, z])
            if np.min(np.hypot(*(allo - p).T)) > 0.007:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def region(c):
        if any(in_poly(c, p) for p in FOOT):
            return None
        if in_poly(c, STREET):
            return "street"
        if in_poly(c, rp):
            return "road"
        return "ground"
    mbs = {k: MB() for k in ("street", "road", "ground")}
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
        mbs[reg].nr = reg == "ground" and c[1] < -0.29 and any(a < c[0] < b for a, b in GAPS)
        mbs[reg].fo(q, reg, UP, True)
        mbs[reg].nr = False
    dec = DECOR.setdefault("ground", [])
    for j, z in enumerate((-0.268, -0.092)):                                # street paving: joints along the edges
        for x in np.arange(FLOOR[0] + 0.03 + 0.04 * (j % 2), -WT - 0.03, 0.08):
            dec.append(((x, 0.0034, z), (x + 0.035, 0.0034, z)))
            dec.append(((x + 0.035, 0.0034, z), (x + 0.035, 0.0034, z + 0.012)))
    rng = random.Random(21)
    for k in range(70):                                                     # pebbles on the road, ticks on the ground
        x = rng.uniform(-0.58, 0.58); z = rng.uniform(-0.56, 0.20)
        c = (x, z)
        if any(in_poly((x + dx, z + dz), p) for p in FOOT for dx in (-0.012, 0.012) for dz in (-0.012, 0.012)):
            continue
        if in_poly(c, STREET):
            continue
        if in_poly(c, rp):
            if all(in_poly((x + dx, z + dz), rp) for dx in (-0.012, 0.012) for dz in (-0.012, 0.012)):
                dec.append(((x - 0.004, 0.0030, z), (x + 0.004, 0.0030, z + 0.002)))
            continue
        if any(in_poly((x + dx, z + dz), p) for p in (rp, STREET) for dx in (-0.014, 0.014) for dz in (-0.014, 0.014)):
            continue
        dec.append(((x - 0.005, 0.0024, z + 0.004), (x, 0.0024, z - 0.004)))
        dec.append(((x, 0.0024, z - 0.004), (x + 0.005, 0.0024, z + 0.004)))
    street = make_obj("straightStreet", mbs["street"], root, origin=(-0.30, 0.0, -0.18), smooth_angle=35)
    road = make_obj("road", mbs["road"], root, origin=(0.40, 0.0, 0.08), smooth_angle=35)
    ground = make_obj("ground", mbs["ground"], root, smooth_angle=35)
    return street, road, ground


# ============================================================================================ backdrop
def hills_top(x):
    t = (x - FLOOR[0]) / (-WT - FLOOR[0])
    return 0.385 + 0.030 * math.sin(TAU * 1.1 * t + 0.6) + 0.012 * math.sin(TAU * 2.7 * t + 1.3)


JW_TOP, JW_TOWERS = 0.355, ((0.07, 0.13, 0.415), (0.26, 0.31, 0.405))


def build_backdrop(root):
    """`hills` (relief behind Damascus, x -0.60..-0.027, with a few distant flat roofs drawn) and `jerusalemWall`
    (relief x 0.027..0.60, battlements 0.355, two towers)"""
    mb = MB()
    xs = np.linspace(FLOOR[0], -WT, 40)
    poly = [(x, 0.0) for x in xs[::-1]] + [(x, hills_top(x)) for x in xs]
    extrude(mb, poly[::-1], BACK_Z[0], BACK_Z[1], "hills")
    dec = DECOR.setdefault("skyline", [])
    zf = BACK_Z[1] + 0.0002
    for (cx, w, h) in ((-0.52, 0.05, 0.04), (-0.45, 0.04, 0.03), (-0.20, 0.05, 0.035), (-0.13, 0.035, 0.028)):
        y0 = hills_top(cx) - 0.050
        for a, b in (((cx - w / 2, y0), (cx + w / 2, y0)), ((cx - w / 2, y0), (cx - w / 2, y0 + h)),
                     ((cx + w / 2, y0), (cx + w / 2, y0 + h)), ((cx - w / 2, y0 + h), (cx + w / 2, y0 + h))):
            dec.append(((a[0], a[1], zf), (b[0], b[1], zf)))
        dec.append(((cx - 0.006, y0, zf), (cx - 0.006, y0 + h * 0.55, zf)))
        dec.append(((cx + 0.006, y0, zf), (cx + 0.006, y0 + h * 0.55, zf)))
        dec.append(((cx - 0.006, y0 + h * 0.55, zf), (cx + 0.006, y0 + h * 0.55, zf)))
    for x in (-0.57, -0.36, -0.30, -0.08):                                 # tufts
        h = hills_top(x) - 0.02
        dec.append(((x - 0.006, h - 0.004, zf), (x, h + 0.006, zf)))
        dec.append(((x, h + 0.006, zf), (x + 0.006, h - 0.004, zf)))
    hills = make_obj("hills", mb, root, origin=(-0.31, 0.0, BACK_Z[1]), smooth_angle=30)
    jm = MB()
    x0, x1 = WT, FLOOR[1]
    segs, cur = [], x0
    for tx0, tx1, ttop in JW_TOWERS:
        segs.append((cur, tx0, JW_TOP)); segs.append((tx0, tx1, ttop)); cur = tx1
    segs.append((cur, x1, JW_TOP))
    for a, b, top in segs:
        extrude(jm, [(a, 0.0), (b, 0.0), (b, top), (a, top)], BACK_Z[0], BACK_Z[1], "jwall")
        n = max(1, int(round((b - a) / 0.03)))
        w = (b - a) / n
        for k in range(n):
            m0 = a + k * w + w * 0.25
            extrude(jm, [(m0, top), (m0 + w * 0.5, top), (m0 + w * 0.5, top + 0.013), (m0, top + 0.013)],
                    BACK_Z[0], BACK_Z[1], "jwall")
    for y in (0.27, 0.31):
        dec.append(((x0 + 0.004, y, zf), (JW_TOWERS[0][0] - 0.003, y, zf)))
        dec.append(((JW_TOWERS[0][1] + 0.003, y, zf), (JW_TOWERS[1][0] - 0.003, y, zf)))
        dec.append(((JW_TOWERS[1][1] + 0.003, y, zf), (x1 - 0.004, y, zf)))
    for tx0, tx1, ttop in JW_TOWERS:
        cx = (tx0 + tx1) / 2
        for k in range(8):                                                  # a small arched window
            a0, a1 = math.pi * k / 8, math.pi * (k + 1) / 8
            dec.append(((cx + 0.009 * math.cos(a0), ttop - 0.05 + 0.009 * math.sin(a0), zf),
                        (cx + 0.009 * math.cos(a1), ttop - 0.05 + 0.009 * math.sin(a1), zf)))
        for s in (-1, 1):
            dec.append(((cx + s * 0.009, ttop - 0.075, zf), (cx + s * 0.009, ttop - 0.05, zf)))
        dec.append(((cx - 0.009, ttop - 0.075, zf), (cx + 0.009, ttop - 0.075, zf)))
    jw = make_obj("jerusalemWall", jm, root, origin=(0.31, 0.0, BACK_Z[1]), smooth_angle=30)
    return hills, jw


# ============================================================================================ drawings / UV
# the `props` still life: drawing-model place and scale of each prop (P = at + k * (V - centre))
PROPS = {"breadBasket": ((0.000, 0.0, 0.0), 3.7), "waterJar": ((0.150, 0.0, 0.0), 1.25),
         "prayerMat": ((0.300, 0.0, 0.020), 0.95), "well": ((0.000, 0.0, 0.0), 1.6),
         "rocks": ((0.145, 0.0, 0.0), 1.5), "bushes": ((0.285, 0.0, 0.0), 2.3)}


def P_RSIDE(k):
    """seen from +x and above (the city wall's outside face): right = further back (-z)"""
    return {"A": (0, 0, -1), "B": (-k, 1, 0), "D": (1, k, 0)}


def _chars_proposal():
    """CONTRACT §2 start slots; boxes guessed from the heights until regions_characters.json exists"""
    return {"ananias": {"sheetX": -0.32, "sheetY": 0.015, "height": 0.33, "box": [-0.455, 0.015, -0.185, 0.345]},
            "saul": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.37, "box": [-0.135, 0.015, 0.135, 0.385]},
            "barnabas": {"sheetX": 0.32, "sheetY": 0.015, "height": 0.39, "box": [0.18, 0.015, 0.46, 0.405]}}


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
    "skyline":   dict(P_FRONT(), scale=2.65, cx=-0.255, y0=1.050, decorOnly=["hills", "jwall"],
                      members=["hills", "jerusalemWall"]),
    "wall":      dict(P_RSIDE(0.30), scale=1.45, cx=0.275, y0=0.860, decorOnly=["wallStone"],
                      members=["cityWall", "cityGate", "wallWindow"]),
    "street":    dict(P_OBL(0.0, 0.40), scale=1.56, cx=-0.267, y0=0.712, members=["ananiasHouse", "synagogue",
                                                                                   "judasHouse"]),
    "jerusalem": dict(P_OBL(0.0, 0.45), scale=1.85, cx=0.362, y0=0.450, members=["priestPorch", "jerusalemHouse",
                                                                                 "jerusalemDoor"]),
    "ground":    dict(P_PLAN(), scale=3.20, cx=0.000, y0=0.450, decorOnly=["ground", "road", "street"],
                      members=["ground", "road", "straightStreet"]),
    "props":     dict(P_OBL(0.0, 0.8), scale=1.62, cx=-0.342, y0=0.470, decorOnly=["straw", "bread"],
                      members=["breadBasket", "waterJar", "prayerMat"]),
    "yard":      dict(P_OBL(0.0, 0.8), scale=1.62, cx=0.095, y0=0.716, decorOnly=["leaf"], members=["well", "rocks"]),
}
TEMPLATES = {}
LIME, WOOD, JARX = ("jerusalem", "limestone"), ("wall", "wood"), ("props", "jar")
CONSTS = {"ananiasHouse": {"limestone": LIME, "plaster": ("street", "plaster"), "wood": WOOD, "jar": JARX,
                           "mat": ("props", "mat"), "roof": ("jerusalem", "roof")},
          "ground": {"ground": ("ground", "ground")},
          "judasHouse": {"limestone": LIME, "wood": WOOD, "roof": ("jerusalem", "roof")},
          "judasDoor": {"wood": WOOD},
          "cityWall": {"wallStone": ("wall", "wallStone")},
          "cityGate": {"wood": WOOD, "iron": ("wall", "window")},
          "wallWindow": {"window": ("wall", "window")},
          "torch1": {"iron": ("wall", "window"), "wood": WOOD, "straw": ("props", "straw")},
          "torch2": {"iron": ("wall", "window"), "wood": WOOD, "straw": ("props", "straw")},
          "well": {"jar": JARX, "wood": WOOD, "window": ("wall", "window")},
          "milestone": {"rock": ("yard", "rock")},
          "palm": {"wood": WOOD, "leaf": ("yard", "leaf")},
          "jerusalemHouse": {"doorway": ("jerusalem", "doorway")},
          "jerusalemDoor": {"wood": WOOD, "doorway": ("jerusalem", "doorway")}}
# hidden props of the Characters role take their colour from these printed regions (CONTRACT §3, C7)
PROP_ANCHORS = {"saul/letters": ("street", "column"), "saul/bread": ("props", "bread"),
                "judas/bread": ("props", "bread"), "saul/basket": ("props", "straw"),
                "ananias/jug": ("props", "jar"), "tallguard/lantern": ("props", "jar")}
RS = [1]
ORDER = ["ground", "straightStreet", "road", "cityWall", "cityGate", "torch1", "torch2", "wallWindow", "ananiasHouse",
         "synagogue", "judasHouse", "judasDoor", "prayerMat", "breadBasket", "waterJar", "well", "rocks", "milestone",
         "palm", "priestPorch", "jerusalemHouse", "jerusalemDoor", "jerusalemWall", "hills"]
HIDDEN = []


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
                       "written by pipeline/sa_damascus.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)
    return const


# ============================================================================================ checks
LOW, OVER = 0.012, 0.17
R_STAND, R_HEAD = 0.05, 0.035
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


def run_clearance(pts, marks, paths):
    """CONTRACT §6 rule per mark and per straight walk, relative to the walker's floor y: nothing above y + 0.012
    within 0.05; overhead parts (y + 0.17 .. head top) need 0.035; above the actor's head ignored. Walking surfaces
    (ground, road, straightStreet) do not count."""
    hard, margins = {}, {}

    def zone_test(label, a, b, y, head):
        lo_min, ov_min = 9.0, 9.0
        for name, P in pts.items():
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
            sel = (lz & (d < R_STAND)) | (oz & (d < R_HEAD))
            if sel.any():
                hard.setdefault(label, []).append([name, round(float(d[sel].min()), 4), round(float(Hh[sel].max()), 4)])
        margins[label] = [round(lo_min, 3), round(ov_min, 3)]

    for label, (x, z, y, actor) in marks.items():
        zone_test("mark " + label, (x, z), (x, z), y, HEAD[actor])
    for label, ls in paths:
        for a, b in zip(ls[:-1], ls[1:]):
            (ax, az, ay, actor), (bx, bz, by, _) = marks[a], marks[b]
            zone_test("walk %s %s>%s" % (label, a, b), (ax, az), (bx, bz), ay, HEAD[actor])
    return hard, margins


def check_clearance(objs):
    pts = sampled_points(objs)
    hard, margins = run_clearance(pts, MARKS, PATHS)
    MARGINS.clear(); MARGINS.update(margins)
    pm = dict(MARKS)
    for k, (x, z) in PROPOSED.items():
        pm[k] = (x, z) + MARKS[k][2:]
    phard, pmarg = run_clearance(pts, pm, PATHS)
    info = {}
    # the basket at BASKET_DOWN: a 0.10 basket hanging on the wall face, from the window down to the ground
    bx, bz = BASKET_DOWN
    near = {}
    for name, P in pts.items():
        m = (P[:, 1] < 0.45) & (np.abs(P[:, 2] - bz) < 0.12)
        if not m.any():
            continue
        d = np.hypot(P[m, 0] - bx, P[m, 2] - bz)
        near[name] = round(float(d.min()), 4)
    wall_face = WT
    info["basket"] = {"wallFaceX": wall_face, "basketCentreX": bx, "basketHalf": 0.05,
                      "gapToWallFace": round(bx - 0.05 - wall_face, 4),
                      "nearestSetPointPlan(<0.45 high)": dict(sorted(near.items(), key=lambda kv: kv[1])[:4]),
                      "ropeTop": [round(c, 4) for c in ROPE_TOP],
                      "ropeTopInWindow": bool(WIN_Z[0] < ROPE_TOP[2] < WIN_Z[1] and WIN_Y[0] < ROPE_TOP[1] < WIN_Y[1]),
                      "window": {"z": list(WIN_Z), "y": list(WIN_Y), "recessBackX": WIN_BACK}}
    info["gate"] = {"opening": list(GATE_Z), "top": "open", "doorFaces": [GATE_Z[0] + DOOR_T, GATE_Z[1] - DOOR_T]}
    return hard, info, phard, pmarg


def region_cells(idb, regname, crease):
    """rough best printable cell per set region (mm): the largest disc inside the region with its creases as lines
    (make_sheet's checks.json is the real measure; this one only steers the layout)"""
    out = {}
    ink = dilate(crease, 2)
    for rid, key in regname.items():
        if not key:
            continue
        m = (idb == rid) & ~ink
        r = 0
        while m.any():
            nxt = m.copy()
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0), (1, 1), (-1, -1), (1, -1), (-1, 1)):
                nxt &= shift(m, dy, dx)
            m = nxt; r += 1
        if r:
            out["%s:%s" % key] = round(float((2 * r - 4.5) / 150 * 25.4), 1)
    small = {k: v for k, v in sorted(out.items(), key=lambda kv: kv[1]) if v < 7.0}
    print("SET_REGION_CELLS_MM", json.dumps(dict(sorted(out.items(), key=lambda kv: kv[1]))))
    print("SET_REGIONS_UNDER_7MM", json.dumps(small))
    return out


# ============================================================================================ build
STATE = {}


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    root = link(bpy.data.objects.new("damascus", None))
    objs = {}
    objs["straightStreet"], objs["road"], objs["ground"] = build_ground(root)
    wall, gate, window, torches = build_city_wall(root)
    objs.update(cityWall=wall, cityGate=gate, wallWindow=window, torch1=torches[0], torch2=torches[1])
    objs["ananiasHouse"] = build_ananias(root)
    objs["synagogue"] = build_synagogue(root)
    (objs["judasHouse"], objs["judasDoor"], objs["prayerMat"], objs["breadBasket"],
     objs["waterJar"]) = build_judas(root, wall)
    objs["well"] = build_well(root)
    objs["rocks"] = build_rocks(root)
    objs["milestone"] = build_milestone(root)
    objs["palm"] = build_palm(root)
    objs["priestPorch"] = build_porch(root)
    objs["jerusalemHouse"], objs["jerusalemDoor"] = build_jhouse(root)
    objs["hills"], objs["jerusalemWall"] = build_backdrop(root)
    bpy.context.view_layer.update()
    tmp = {}
    src = raster_sources(objs, tmp)
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("DAMASCUS_TRIS", total, json.dumps(tris))
    lay = check_layout()
    hard, info, phard, pmarg = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_PROPOSED", "OK" if not phard else json.dumps(phard), json.dumps(PROPOSED))
    print("CLEARANCE_MIN", json.dumps(MARGINS))
    print("CLEARANCE_PROPOSED_MIN", json.dumps({k: v for k, v in pmarg.items() if any(p in k for p in PROPOSED)}))
    print("CLEARANCE_INFO", json.dumps(info))
    if total > MAX_TRIS:
        print("OVER_BUDGET", total)
    STATE.update(objs=objs, root=root, hard=hard, info=info, phard=phard, pmarg=pmarg)
    if MODE == "check":
        return
    RS[0] = 2
    idb2, regname, crease2 = raster_drawings(src)
    RS[0] = 1
    idb = idb2[1::2, 1::2]
    crease = crease2.reshape(PAGE[1], 2, PAGE[0], 2).any(axis=(1, 3))
    fixed, missing, tex = fix_faces(objs, idb, regname, crease)
    region_cells(idb, regname, crease)
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
    write_design(objs, tris, total, hmax, const, hard, info, tex, phard, pmarg)
    STATE.update(tex=tex_img, demo=demo)
    print("BUILD_OK", GLB, total, "MISSING" if missing else "")
    if missing:
        raise SystemExit("named texels missing: %s" % missing)


TITLE = {"hanzi": "扫罗变了", "pinyin": "sǎo luó biàn le", "english": "Saul Sees the Light!", "box": 80, "gap": 16,
         "cy": 110, "label": "DoodLive · 涂上颜色，再用手机扫一扫",
         "note": "box / gap / cy from tools/story/sheet_saul.py title-search: worst NCC 0.459 (risen-A4) against "
                 "every other registered sheet"}


def write_design(objs, tris, total, hmax, const, hard, info, tex, phard, pmarg):
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
                                                            "使徒行传 9 · Acts 9"],
                   "note": "centred on the page (x 620); line 1 at rect y + 40, line 2 at y + 76"},
        "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge; "
                    "title cy keeps the pinyin >= 6 mm from the top"})
    if d["sheet"]["title"].get("note", "").startswith("placeholder") or not TITLE["note"].startswith("placeholder"):
        d["sheet"]["title"] = dict(TITLE)
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"height": v["height"], "sheetX": v["sheetX"], "sheetY": v["sheetY"]})
        if c == "saul":
            e["note"] = "cloak inside +-0.10 of his centre (CONTRACT §2)"
        if c == "barnabas":
            e["note"] = "the widest figure (mantle): A-pose hands inside +0.32 +- 0.14 (CONTRACT §2)"
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
        "generatedBy": "pipeline/sa_damascus.py", "doc": "docs/saul/SET.md",
        "contract": "docs/saul/CONTRACT.md §6", "root": "damascus",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {n: [round(c, 4) for c in D(objs[n].matrix_world.translation)] for n in ORDER},
        "footprints": {
            "floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]],
            "cityWall": {"x": [-WT, WT], "z": [WALL_Z0, -0.02], "body": WALL_BODY, "top": MERLON_TOP,
                         "towers": {"centres": [list(TOWER_C), list(TOWER2_C)], "r": TOWER_R, "top": TOWER_TOP},
                         "anchor": [TOWER_C[0], TOWER_TOP, TOWER_C[1]]},
            "cityGate": {"opening": list(GATE_Z), "top": "open (between the two towers)",
                         "doors": "standing in the gateway's edges, %.3f thick, %.2f high" % (DOOR_T, GATE_DOOR_H)},
            "torch1": [TORCHES["torch1"][1] + 0.016, TORCH_TOP, TORCHES["torch1"][0]],
            "torch2": [round(TORCHES["torch2"][1] + 0.016, 4), TORCH_TOP, TORCHES["torch2"][0]],
            "wallWindow": {"z": list(WIN_Z), "y": list(WIN_Y), "faceX": WT, "recessBackX": WIN_BACK,
                           "shutterZ": list(SHUTTER_Z)},
            "straightStreet": {"x": [FLOOR[0], WT], "z": [-0.28, -0.08]},
            "ananiasHouse": {"x": list(AH_X), "z": [round(WB[0] + AH_DZ, 4), AH_ZF], "walls": AH_T, "h": ROOM_H,
                             "room": {"x": [AH_X[0] + AH_T, AH_X[1] - AH_T], "z": [round(WB[1] + AH_DZ, 4), AH_ZF]},
                             "roofOver": [round(WB[0] + AH_DZ, 4), round(ROOF_Z0 + AH_DZ, 4)],
                             "anchor": [round(c, 4) for c in AH_LIGHT]},
            "synagogue": {"x": list(SYN_X), "facadeZ": SYN_ZF, "h": SYN_TOP, "steps": [list(s) for s in STEPS],
                          "topStepY": STEP_Y, "columns": list(SYN_COLS), "door": list(SYN_DOOR)},
            "judasHouse": {"x": [JH_X[0], -WT], "z": [FLOOR[2], JH_ZF], "leftWall": list(JH_LW), "h": ROOM_H,
                           "roofOver": [WB[0], ROOF_Z0], "threshold": [JH_ZF - 0.01, JH_ZF, 0.004],
                           "table": {"at": list(TABLE), "r": TABLE_R, "top": TABLE_TOP}},
            "judasDoor": {"posts": list(JDOOR_X), "z": JDOOR_Z, "top": JDOOR_TOP + 0.008,
                          "otherJamb": "the back gate tower (centre %s, r %.2f)" % (list(TOWER2_C), TOWER_R)},
            "prayerMat": {"at": list(MAT_C), "size": [MAT_W, MAT_D], "top": 0.0065},
            "breadBasket": {"at": list(TABLE), "r": BASKET_R, "top": round(TABLE_TOP + 0.031, 3)},
            "waterJar": {"at": list(JAR), "r": JAR_R, "top": JAR_TOP},
            "well": {"at": list(WELL), "r": WELL_R, "h": WELL_H},
            "road": "porch steps (0.485, -0.30) -> right side x ~0.43..0.55 -> front z ~0.04..0.17 -> (0.135, 0.06) -> "
                    "the gate (0.02, -0.16), 0.12 wide",
            "rocks": {"at": list(ROCKS), "r": 0.035, "bushes": [[0.225, -0.25], [0.195, -0.272]]},
            "milestone": {"at": list(MILESTONE), "h": 0.075},
            "palm": {"trunk": list(PALM), "crownUnderside": ">= 0.31", "crownX": ">= 0.505"},
            "priestPorch": {"x": list(PORCH_X), "z": [FLOOR[2], PORCH_ZF], "floor": PORCH_Y,
                            "steps": [list(s) for s in PSTEPS], "columns": [list(c) for c in PCOLS],
                            "roof": list(PROOF)},
            "jerusalemHouse": {"x": list(JHOUSE_X), "z": [FLOOR[2], JHOUSE_ZF], "h": JHOUSE_H},
            "jerusalemDoor": {"x": list(JDOOR2[:2]), "top": JDOOR2[2], "darkRoomTo": JDOOR2[3]},
            "hills": {"x": [FLOOR[0], -WT], "z": list(BACK_Z)},
            "jerusalemWall": {"x": [WT, FLOOR[1]], "z": list(BACK_Z), "top": JW_TOP, "towers": [list(t) for t in JW_TOWERS]}},
        "hiddenAtStart": list(HIDDEN),
        "propAnchors": anchors,
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227",
                   "drawingModel": "P = the vertex, except the props (moved / scaled into one still life)",
                   "edgeOn": "faces with |n . D| < 0.22 (n in drawing space) take one clean texel of their region",
                   "namedTexels": "no-raster bits take one texel of a named (drawing, region); constUV in "
                                  "model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard,
                      "proposedMarks": {"marks": {k: list(v) for k, v in PROPOSED.items()},
                                        "hard": "OK" if not phard else phard},
                      "nearest": {"note": "[low zone (y+0.012..0.17), overhead (y+0.17..head top)] nearest plan distance "
                                          "(needs >= 0.05 / 0.035)", **MARGINS},
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
    save_png(line, os.path.join(WORK, "damascus_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "damascus_drawings_demo.png"))
    tex = np.where(mask[..., None], grain, 0.0); got = mask.copy()
    for _ in range(10):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = shift(got, dy, dx); sv = shift(tex, dy, dx)
            take = sm & ~got
            tex[take] = sv[take]; got |= take
    tex[~got] = 1.0
    return tex, demo


# ============================================================================================ preview
PV_COL = {"skin": "#E9B48F", "saulR": "#B23A3A", "saulC": "#2F4A7A", "hairD": "#3E2A1E", "anaR": "#6E8F4E",
          "anaS": "#D9A93A", "grey": "#A8A8A0", "barR": "#D9773A", "barM": "#F1E3C4", "black": "#2A2420",
          "judT": "#E2C89A", "judH": "#4A78B0", "priR": "#F4F2EA", "priO": "#3D5FA0", "grdT": "#7F93A8",
          "capT": "#D9A93A", "capS": "#7A5532", "petR": "#B4502F", "hairP": "#231A16", "straw": "#D8B26E",
          "rope": "#C8B48A"}
PV_SPEC = {"saul": (0.37, "saulR", "saulC", "hairD"), "ananias": (0.33, "anaR", "anaS", "capS"),
           "barnabas": (0.39, "barR", "barM", "black"), "judas": (0.35, "judT", "judT", "judH"),
           "priest": (0.36, "priR", "priO", "priR"), "tallguard": (0.41, "grdT", "grdT", "capT"),
           "shortguard": (0.30, "grdT", "grdT", "capS"), "peter": (0.38, "petR", "petR", "hairP")}


def mannequins(layout):
    """preview stand-ins only (not shipped): simple figures in the demo colours at the actors' marks.
    layout: who -> (x, z, y, face (dx, dz), pose); pose '' standing, 'kneel', 'seat' (cross-legged on the floor),
    'basket' (Saul crouched in the basket, basket bottom 0.17 up, two ropes to the window)"""
    for k, v in PV_COL.items():
        if k not in REGION_MATS:
            REGION_MATS[k] = flat_mat("pvm_" + k, v, 0.6)
    for who, (x, z, y, fc, pose) in layout.items():
        mb = MB()
        H, body, top, hair = PV_SPEC[who]
        if pose in ("seat", "basket"):
            s0 = 0.0 if pose == "seat" else 0.17 + 0.012
            lathe(mb, [(0.0, s0), (0.055, s0), (0.050, s0 + 0.02), (0.0, s0 + 0.03)], body, seg=16)
            lathe(mb, [(0.0, s0 + 0.02), (0.040, s0 + 0.02), (0.038, s0 + 0.10), (0.030, s0 + 0.15), (0.0, s0 + 0.16)],
                  top, seg=16)
            sphere(mb, (0.0, s0 + 0.185, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, s0 + 0.196, -0.008), 0.026, hair, seg=10, rings=7)
            if pose == "basket":
                lathe(mb, [(0.0, 0.17), (0.045, 0.17), (0.050, 0.25), (0.046, 0.25), (0.040, 0.18), (0.0, 0.18)],
                      "straw", seg=18)
                rx, ry, rz = ROPE_TOP[0] - x, ROPE_TOP[1], ROPE_TOP[2] - z
                for s in (-1, 1):
                    tube(mb, [(-0.045, 0.25, s * 0.03), (rx, ry, rz + s * 0.012)], 0.0022, "rope", seg=5)
        elif pose == "kneel":
            lathe(mb, [(0.0, 0.0), (0.05, 0.0), (0.048, 0.03), (0.040, 0.10), (0.032, 0.16), (0.0, 0.17)], body, seg=16)
            sphere(mb, (0.0, 0.195, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, 0.205, -0.008), 0.026, hair, seg=10, rings=7)
        else:
            lathe(mb, [(0.0, 0.0), (0.048, 0.0), (0.046, 0.02), (0.040, 0.36 * H)], body, seg=18)
            lathe(mb, [(0.040, 0.36 * H), (0.044, 0.56 * H), (0.036, 0.75 * H), (0.0, 0.78 * H)], top, seg=18)
            sphere(mb, (0.0, H - 0.04, 0.0), 0.034, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, H - 0.05), (0.036, H - 0.04), (0.035, H - 0.010), (0.0, H)], hair, C=(0, 0, -0.006), seg=16)
        ob = make_obj("pv_" + who, mb, None, origin=(0, 0, 0), smooth_angle=60, merge=False)
        ob["pv"] = 1
        ob.location = B(x, y, z)
        if pose != "basket":
            ob.rotation_euler = (0, 0, math.atan2(fc[0], fc[1]))


def toward(a, b):
    return (b[0] - a[0], b[1] - a[1])


def mode_preview():
    if not STATE or "tex" not in STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "damascus_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "damascus_preview_sheet.png")); sheet.pack()
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

    V_ = (0, 1)
    cast({})
    phone = ((0.0, 1.30, 1.55), (0.0, 0.02, -0.22), 50, (720, 1280))
    shoot("damascus_preview_phone_set", *phone)
    # S01: the porch
    cast({"saul": (0.42, -0.24, 0.0, toward((0.42, -0.24), (0.47, -0.42)), ""),
          "priest": (0.47, -0.42, PORCH_Y, toward((0.47, -0.42), (0.42, -0.24)), "")})
    shoot("damascus_preview_phone", *phone)
    phone_shot("damascus_preview_s01", node_t("priestPorch"), 0.6, 0.24, 25)
    # S02: the road, the guards puffing behind
    cast({"saul": (0.30, 0.13, 0.0, (1, 0), ""), "shortguard": (0.44, 0.08, 0.0, (-1, 0), ""),
          "tallguard": (0.53, 0.03, 0.0, (-1, 0), "")})
    phone_shot("damascus_preview_s02", act_t("saul", 0.30, 0.13), 0.6, 0.2, 30)
    # S03 / S04: the light on the road
    s3 = {"saul": (0.18, 0.08, 0.0, V_, "seat"), "shortguard": (0.30, 0.04, 0.0, (-1, 0), ""),
          "tallguard": (0.34, 0.13, 0.0, (-1, 0), "")}
    cast(s3)
    phone_shot("damascus_preview_s03", act_t("saul", 0.18, 0.08), 0.7, 0.34, 15)
    phone_shot("damascus_preview_s04", act_t("saul", 0.18, 0.08), 0.5, 0.22, -20)
    # S05: led by the hand to the gate (the guard in the gateway)
    cast({"tallguard": (0.01, -0.16, 0.0, (-1, 0), ""), "saul": (0.09, -0.16, 0.0, (-1, 0), ""),
          "shortguard": (0.13, -0.01, 0.0, toward((0.13, -0.01), (0.09, -0.16)), "")})
    phone_shot("damascus_preview_s05", act_t("saul", 0.09, -0.16), 0.6, 0.2, 25)
    # S06: Judas's house, Saul praying on the mat
    cast({"saul": (-0.15, -0.46, 0.0, V_, "seat"), "judas": (-0.21, -0.37, 0.0, toward((-0.21, -0.37), (-0.15, -0.46)), "")})
    phone_shot("damascus_preview_s06", node_t("judasHouse"), 0.5, 0.22, 0)
    # S07: Ananias kneeling at home
    cast({"ananias": (-0.465, 0.08, 0.0, V_, "kneel")})
    phone_shot("damascus_preview_s07", node_t("ananiasHouse"), 0.5, 0.2, 10)
    cast({"ananias": (-0.465, 0.08, 0.0, V_, "")})
    phone_shot("damascus_preview_s07_standing", node_t("ananiasHouse"), 0.5, 0.2, 10)
    # S08: Ananias at the door, then beside the seated Saul
    cast({"saul": (-0.15, -0.46, 0.0, V_, "seat"), "ananias": (-0.13, -0.27, 0.0, (0, -1), ""),
          "judas": (-0.21, -0.37, 0.0, toward((-0.21, -0.37), (-0.13, -0.27)), "")})
    phone_shot("damascus_preview_s08", node_t("judasHouse"), 0.55, 0.22, -15)
    cast({"saul": (-0.15, -0.46, 0.0, V_, "seat"), "ananias": (-0.08, -0.42, 0.0, (-1, 0), ""),
          "judas": (-0.21, -0.37, 0.0, toward((-0.21, -0.37), (-0.15, -0.46)), "")})
    phone_shot("damascus_preview_s08b", node_t("judasHouse"), 0.55, 0.22, -15)
    # S09: baptism
    cast({"saul": (-0.15, -0.46, 0.0, V_, "kneel"), "ananias": (-0.22, -0.42, 0.0, (1, 0), ""),
          "judas": (-0.08, -0.43, 0.0, toward((-0.08, -0.43), (-0.15, -0.46)), "")})
    phone_shot("damascus_preview_s09", act_t("saul", -0.15, -0.46), 0.5, 0.2, 15)
    # S10: Saul on the synagogue step, listeners
    cast({"saul": (-0.37, -0.36, STEP_Y, V_, ""), "tallguard": (-0.165, -0.20, 0.0, toward((-0.165, -0.20), (-0.37, -0.36)), ""),
          "shortguard": (-0.07, -0.19, 0.0, toward((-0.07, -0.19), (-0.37, -0.36)), ""),
          })
    phone_shot("damascus_preview_s10", node_t("synagogue"), 0.6, 0.22, 10)
    # S11: night at the wall: the basket at the window, the guards at the gate
    cast({"saul": (0.095, -0.46, 0.0, V_, "basket"), "tallguard": (0.12, -0.04, 0.0, V_, ""),
          "shortguard": (0.19, -0.11, 0.0, V_, "")})
    phone_shot("damascus_preview_s11", node_t("wallWindow"), 0.6, 0.26, 50)
    cast({"saul": (0.095, -0.38, 0.0, V_, ""), "tallguard": (0.12, -0.04, 0.0, V_, ""),
          "shortguard": (0.19, -0.11, 0.0, V_, "")})
    phone_shot("damascus_preview_s11_down", node_t("wallWindow"), 0.6, 0.26, 50)
    cast({"saul": (0.095, -0.46, 0.0, V_, "basket"), "tallguard": (0.12, -0.04, 0.0, V_, ""),
          "shortguard": (0.19, -0.11, 0.0, V_, "")})
    phone_shot("damascus_preview_s11_yaw25", node_t("wallWindow"), 0.6, 0.26, 25)
    # S12: Jerusalem, the door of the believers' house
    cast({"peter": (0.24, -0.33, 0.0, toward((0.24, -0.33), (0.335, -0.30)), ""),
          "saul": (0.335, -0.30, 0.0, toward((0.335, -0.30), (0.24, -0.33)), ""),
          "barnabas": (0.30, -0.22, 0.0, toward((0.30, -0.22), (0.24, -0.33)), "")})
    phone_shot("damascus_preview_s12", node_t("jerusalemDoor"), 0.55, 0.2, 25)
    # S13: everyone in a row
    cast({"ananias": (-0.27, 0.08, 0.0, V_, ""), "judas": (-0.17, 0.10, 0.0, V_, ""), "saul": (-0.07, 0.10, 0.0, V_, ""),
          "barnabas": (0.06, 0.10, 0.0, V_, ""), "peter": (0.18, 0.10, 0.0, V_, ""),
          "tallguard": (0.32, 0.10, 0.0, V_, ""), "shortguard": (0.44, 0.10, 0.0, V_, "")})
    phone_shot("damascus_preview_s13", node_t("cityWall"), 0.95, 0.46, 0)
    cast({})
    shoot("damascus_preview_wall", (0.75, 0.32, -0.15), (0.0, 0.22, -0.30), 40, (1200, 900))
    shoot("damascus_preview_rooms", (-0.30, 0.32, 0.55), (-0.30, 0.12, -0.42), 42, (1400, 900))
    shoot("damascus_preview_jerusalem", (0.45, 0.35, 0.50), (0.38, 0.18, -0.42), 42, (1200, 900))
    shoot("damascus_preview_front", (0.0, 0.30, 2.3), (0.0, 0.18, -0.25), 22, (1600, 1000))
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "damascus_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["damascus", "cityWall", "cityGate", "torch1", "torch2", "wallWindow", "straightStreet", "ananiasHouse",
        "synagogue", "judasHouse", "judasDoor", "prayerMat", "breadBasket", "waterJar", "well", "road", "rocks",
        "milestone", "palm", "priestPorch", "jerusalemHouse", "jerusalemDoor", "jerusalemWall", "hills", "ground"]


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
           for n in ("cityWall", "torch1", "torch2", "wallWindow", "ananiasHouse", "judasHouse", "jerusalemDoor",
                     "priestPorch", "synagogue", "cityGate") if n in names}
    ok = not missing and tris <= MAX_TRIS and uv_bad == 0
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "parents": parents, "origins": org}))
    if not ok:
        raise SystemExit("VERIFY FAIL")


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
