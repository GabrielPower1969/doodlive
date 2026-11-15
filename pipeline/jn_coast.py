"""Blender (headless): Jonah story pack, the coast -> assets/jonah/model/coast.glb

One tabletop page, three places. Left: the sea (two blues, printed wave marks, curling wave crests in the back water,
a white foam line at the shore and round the hull; skinned to a bone grid, looping action `seaWave`) with the
merchant ship at the back-left (clinker-planked round hull, plank deck, a high curled stern post, the steering oar,
one mast at the back rail with a furled cream sail with two red stripes on its yard, a rope ladder, stays, rope rails
on posts; looping action `shipRock`, +-3 deg roll about the deck) and its `cargo` (sacks and jars). Middle front: the
beach (sand with ripples, shells, two mooring posts in the shallows with a rope to the bow, a rope coil, a rowing boat
pulled up) and the `plank` from the sand to the bow. Right: Nineveh (mud-brick wall on a stone plinth with stepped
battlements, towers, flat-roofed houses and a stepped temple behind, two date palms) with its `gate` (two towers, an
arch ringed with lapis and gold blocks, bronze-banded doors), the pale `road` to the gate and the beach, Jonah's low
`hill` (rocks, dry grass). Hidden props: `shelter` (sticks and a patched cloth), `plantSmall` / `plantBig` /
`plantDry` (one gourd vine in three states at one root), `worm`, and `belly` (the ribbed dome inside the fish).
Contract: docs/jonah/CONTRACT.md §6. Nodes, marks, clearances and deviations: docs/jonah/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `jn_page` = the scanned art rectangle): as Ruth (pipeline/ru_bethlehem.py). Each piece
belongs to one *drawing* on the colouring sheet, a linear view a = A.P, b = B.P (depth D.P), and
  u = a / scale + sheetX + 0.5,   v = (b / scale + sheetY) / 1.227
P = the world position, or the template position for instanced pieces (the wave crests). Faces nearly edge-on to their
drawing take one clean texel of their own region; scattered and thin bits (rigging, foam, shells, rocks, sticks, the
worm) take the texel of a named (drawing, region).

Modes (run from the repo root, one Blender at a time):
  nice -n 10 blender -b --factory-startup --python pipeline/jn_coast.py -- build     coast.glb + .blend + set drawings
  nice -n 10 blender -b --factory-startup --python pipeline/jn_coast.py -- verify    re-import coast.glb and check it
  nice -n 10 blender -b --factory-startup --python pipeline/jn_coast.py -- all       build, preview, verify
  nice -n 10 blender -b --factory-startup --python pipeline/jn_coast.py -- check     build in memory, print checks only
Work files go to $JN_WORK (default /tmp/jonah_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector, Quaternion, Euler
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/jonah/model")
GLB = os.path.join(MODEL, "coast.glb")
BLEND = os.path.join(MODEL, "coast.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/jonah/design.json")
TIMELINE = os.path.join(ROOT, "assets/jonah/timeline.json")
WORK = os.environ.get("JN_WORK", "/tmp/jonah_set")
PAGE_MATERIAL = "jn_page"
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
MAX_TRIS = 60000
TAU = 2 * math.pi
UP = (0.0, 1.0, 0.0)
FLOOR = (-0.60, 0.60, -0.5875, 0.21)          # x0 x1 zBack zFront
sys.path.insert(0, HERE)                                                             # noqa: E402
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "stage")


# ============================================================================================ layout (CONTRACT §6)
DECK = 0.10
SEA_X = (-0.60, 0.06)                          # water surface x range (all z)
SEA_LEVEL = 0.0045                             # mean water height; animated +-0.0018
LANE = (-0.60, 0.02, -0.06, 0.21)              # the fish's lane: x0 x1 z0 z1 (nothing of the set in it)
SHIP_C = (-0.34, -0.22)                        # hull centre
SHIP_X = (-0.535, -0.148)                      # stern tip, bow tip
SHIP_HB = 0.070                                # half beam
MAST = (-0.405, -0.292)                        # mast foot at the back rail (see SET.md: the only place clear of
MAST_TOP = 0.455                               #   every deck mark and walk)
YARD_H, YARD_X = 0.436, (-0.566, -0.334)
PLANK_FOOT, PLANK_TOP = (0.08, 0.02, -0.20), (-0.165, DECK, -0.22)
BEACH_X = (0.03, 0.22)
BOAT = (0.128, -0.405)
POSTS = [(0.028, -0.272), (0.026, -0.128)]
HILL_C, HILL_R, HILL_TOP = (0.44, 0.06), 0.14, 0.028
SHELTER = (0.52, 0.02)
PLANT = (0.34, 0.06)
BELLY_C, BELLY_R, BELLY_H = (-0.20, 0.08), 0.13, 0.26
WALL_X, WALL_Z, WALL_T, WALL_H = (0.20, 0.60), -0.40, 0.04, 0.205
GATE_X, GATE_W, GATE_H = 0.34, 0.10, 0.16
TOWERS = [(0.245, 0.290, 0.265, "gate"), (0.390, 0.435, 0.265, "gate"), (0.555, 0.600, 0.245, "nineveh")]


# ============================================================================================ marks and paths
# deck marks stand at y = DECK; walks between marks of one actor are straight lines in the engine
G, Dk = 0.0, DECK
MARKS = {                                                     # label: (x, z, floor y)
    "jonah road": (0.28, 0.14, G), "jonah beach": (0.12, 0.10, G), "plank foot": (0.08, -0.20, 0.02),
    "plank top": (-0.16, -0.22, Dk), "jonah deck": (-0.26, -0.22, Dk), "jonah cargo": (-0.30, -0.26, Dk),
    "jonah rail": (-0.22, -0.16, Dk), "captain deck": (-0.44, -0.22, Dk), "captain deck2": (-0.36, -0.24, Dk),
    "jonah gate": (0.32, -0.16, G), "jonah hill": (0.42, 0.08, G),
    "jonah gate side": (0.16, -0.10, G)}   # S09 (round 3)   # gate mark moved forward 2026-11-15 (FIXLOG)
CONTRACT_PATHS = [                                            # CONTRACT §6 walks (label, a, b): a/b = MARKS labels
    ("jonah road>beach", "jonah road", "jonah beach"), ("jonah beach>plank", "jonah beach", "plank foot"),
    ("jonah up the plank", "plank foot", "plank top"), ("jonah plank>deck", "plank top", "jonah deck"),
    ("jonah deck>cargo", "jonah deck", "jonah cargo"), ("jonah cargo>rail", "jonah cargo", "jonah rail"),
    ("captain deck>deck2", "captain deck", "captain deck2"), ("jonah beach>gate", "jonah beach", "jonah gate"),
    ("jonah gate>hill", "jonah gate", "jonah hill")]
FISH_MARKS = {"fish gulp": (-0.34, 0.04), "fish shore": (-0.30, 0.10), "fish end": (-0.34, 0.08)}   # story.py (side-on, facing +X)
TERRAIN = {"beach", "road", "ground", "hill", "seaWater", "plank", "bellyFloorOnly"}


def _timeline_moves():
    """(label, (x, z, y) a, (x, z, y) b) for consecutive targets of one actor in timeline.json"""
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
        if w in last and math.hypot(p[0] - last[w][0], p[1] - last[w][1]) > 1e-4:
            out.append(("%s %.2f,%.2f>%.2f,%.2f" % (w, last[w][0], last[w][1], p[0], p[1]), last[w], p, w))
        last[w] = p
    return out


TL_MOVES = _timeline_moves()
HARD_PTS = [(x, z) for x, z, _ in MARKS.values()]
HARD_SEGS = [((MARKS[a][0], MARKS[a][1]), (MARKS[b][0], MARKS[b][1])) for _, a, b in CONTRACT_PATHS]
SOFT_SEGS = [((a[0], a[1]), (b[0], b[1])) for _, a, b, w in TL_MOVES if w != "fish"
             and max(abs(a[0]), abs(b[0])) < 0.62]
DECK_PTS = [(x, z) for x, z, y in MARKS.values() if y == Dk]
DECK_SEGS = [((MARKS[a][0], MARKS[a][1]), (MARKS[b][0], MARKS[b][1])) for _, a, b in CONTRACT_PATHS
             if MARKS[a][2] == Dk and MARKS[b][2] == Dk]


def deck_clear(x, z):
    d = min(math.hypot(x - a, z - b) for a, b in DECK_PTS)
    for a, b in DECK_SEGS:
        d = min(d, seg_dist((x, z), a, b))
    return d


def ground_clear(x, z, soft=True):
    """distance to the nearest ground mark / ground walk (the deck ones are 0.10 up and do not count)"""
    pts = [(x_, z_) for x_, z_, y in MARKS.values() if y < 0.05]
    d = min(math.hypot(x - a, z - b) for a, b in pts)
    for _, a, b in CONTRACT_PATHS:
        if MARKS[a][2] < 0.05 or MARKS[b][2] < 0.05:
            d = min(d, seg_dist((x, z), MARKS[a][:2], MARKS[b][:2]))
    if soft:
        for a, b in SOFT_SEGS:
            d = min(d, seg_dist((x, z), a, b))
    return d


def in_lane(x, z, pad=0.0):
    return LANE[0] - pad <= x <= LANE[1] + pad and LANE[2] - pad <= z <= LANE[3] + pad


# demo colouring (DESIGN.md §3; the rest chosen to sit with it)
COLOURS = {
    "sea": "#3B8FD0", "seaFar": "#2B6FB0", "foam": "#FFFFFF", "wave": "#2E7CC4",
    "hull": "#8A5A3B", "deck": "#C9A77A", "wood": "#A47548", "sail": "#F3E9D2", "stripe": "#B8423A",
    "sack": "#EBDDBF", "sackTie": "#8A5A3B", "jar": "#C8643C",
    "sand": "#EAD9B0", "road": "#E3CFA3", "earth": "#B9BE7E", "hill": "#D9B77A", "stone": "#9C8A72",
    "brick": "#D8B07A", "lapis": "#2E5FA8", "gold": "#E8C15A", "roof": "#C9A77A", "door": "#8A5A3B",
    "house": "#E6C895", "palmTrunk": "#8A6A44", "palmLeaf": "#6E9F4A",
    "boatHull": "#5E8FA8", "boatInside": "#C9A77A",
    "leaf": "#5FA844", "gourd": "#B9C85A", "dry": "#8A6A44", "dryGourd": "#B39060",
    "cloth": "#C98F8F", "patch": "#E3B9A0",
    "ribs": "#D9A9A6", "bellyWall": "#ECC6C0", "bellyFloor": "#17444A",
}


# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model), faces with region, smooth flag, a
    no-raster flag (scattered bits that sample a named texel) and optional skin weights (copied from Ruth)"""

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

    def add(self, src, fn, weight=None):
        """instance of template `src`: world = fn(local); P = the template's own P (drawing model)"""
        base = len(self.V)
        for i, (x, h, z) in enumerate(src.V):
            self.V.append(tuple(float(c) for c in fn((x, h, z))))
            self.P.append(src.P[i])
            if weight is not None:
                self.W[base + i] = weight(src.V[i], self.V[-1])
        for f, r, s, nr in zip(src.F, src.R, src.S, src.N):
            self.F.append([base + i for i in f]); self.R.append(r); self.S.append(s); self.N.append(nr or self.nr)


REGION_MATS = {}
P_OF, NR_OF, REG_OF = {}, {}, {}
DECOR = {}                    # drawing -> [(p0, p1)] single drawn lines in drawing-model coords


def grid_surface(mb, xs, zs, hfun, regfun, out=UP, smooth=True):
    g = [[mb.v(x, hfun(x, z), z) for z in zs] for x in xs]
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            reg = regfun((xs[i] + xs[i + 1]) / 2, (zs[j] + zs[j + 1]) / 2)
            if reg is None:
                continue
            mb.fo([g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]], reg, out, smooth)
    return g


def leaf_blade(mb, base, tip, width, reg, nrm=(0, 0, 1), fold=0.25, n=9, droop=0.0, heart=True, thick=0.0008):
    """a broad leaf: outline from base to tip with a heart-shaped base, slightly folded along the midrib; two layers
    (top and underside) on their own vertices, so the leaf's edges are ordinary manifold edges"""
    base, tip = Vector(base), Vector(tip)
    ax = tip - base; L = ax.length; t = ax.normalized()
    nn = Vector(nrm); side = t.cross(nn)
    if side.length < 1e-6:
        side = t.cross(Vector((1, 0, 0)))
    side.normalize(); up = side.cross(t).normalized()
    if up.dot(nn) < 0:
        up = -up
    pts = []
    for k in range(n + 1):
        u = k / n
        w = width * (math.sin(math.pi * min(1.0, u * 1.08)) ** 0.8 if u < 0.93 else (1 - u) * 1.4) * 0.5
        if heart and u < 0.18:
            w = max(w, width * 0.5 * (0.55 + 2.0 * u))
        c = base + t * (L * u) + up * (droop * L * (u * u))
        pts.append((c, c - side * w - up * (fold * w), c + side * w - up * (fold * w)))
    for sgn in (1, -1):
        off = up * (thick / 2 * sgn)
        rows = [[mb.v(*(p + off)) for p in trip] for trip in pts]           # mid, left, right
        for k in range(n):
            for j in (1, 2):
                mb.fo([rows[k][0], rows[k + 1][0], rows[k + 1][j], rows[k][j]], reg, tuple(up * sgn))


def bilinear_weights(x, z, bx, bz, names):
    """skin weights of a point on a regular bone grid (<= 4 influences)"""
    fx = (x - bx[0]) / (bx[1] - bx[0]) if len(bx) > 1 else 0.0
    fz = (z - bz[0]) / (bz[1] - bz[0]) if len(bz) > 1 else 0.0
    fx = min(max(fx, 0.0), len(bx) - 1.0001); fz = min(max(fz, 0.0), len(bz) - 1.0001)
    i, j = int(fx), int(fz); u, v = fx - i, fz - j
    w = {}
    for di, dj, ww in ((0, 0, (1 - u) * (1 - v)), (1, 0, u * (1 - v)), (0, 1, (1 - u) * v), (1, 1, u * v)):
        if ww > 1e-4:
            w[names[i + di][j + dj]] = w.get(names[i + di][j + dj], 0.0) + ww
    return w


# ============================================================================================ sea
NBX, NBZ = 6, 5
SEA_BX = list(np.linspace(SEA_X[0] + 0.05, SEA_X[1] - 0.05, NBX))
SEA_BZ = list(np.linspace(FLOOR[2] + 0.06, FLOOR[3] - 0.04, NBZ))
SEA_BONES = [["wave_%d_%d" % (i, j) for j in range(NBZ)] for i in range(NBX)]


def sea_h(x, z):
    """rest height of the water: gentle cross ripples, a little lower at the shore"""
    h = SEA_LEVEL + 0.0011 * math.sin(29 * x + 6 * z) * math.sin(21 * z - 9 * x) + 0.0004 * math.sin(57 * x + 41 * z)
    if x > 0.0:
        h -= 0.0012 * min(1.0, x / 0.05)
    return h


def sea_region(x, z):
    return "seaFar" if z < -0.335 + 0.022 * math.sin(11 * x + 1.0) else "sea"


def hull_halfbeam(x):
    u = (x - SHIP_C[0]) / ((SHIP_X[1] - SHIP_X[0]) / 2)
    return SHIP_HB * max(0.0, 1 - abs(u) ** 5) ** 0.45


def wave_template():
    """one curling wave crest, modelled large (length 0.09, height 0.063): a ridge swept along x with a breaking lip.
    Seen from the front (its drawing, and the phone) the curl's face is foam, the body below it blue."""
    mb = MB()
    # cross-section (z, h) back -> crest -> curl -> under the curl -> front foot
    prof = [(-0.044, 0.000), (-0.028, 0.018), (-0.013, 0.039), (-0.002, 0.054), (0.008, 0.063), (0.019, 0.061),
            (0.028, 0.049), (0.028, 0.036), (0.021, 0.028), (0.015, 0.032), (0.012, 0.020), (0.016, 0.007),
            (0.026, 0.000)]
    NX = 14
    xs = np.linspace(-0.045, 0.045, NX + 1)
    rows = []
    for x in xs:
        u = (x + 0.045) / 0.09
        env = math.sin(math.pi * u) ** 0.6
        lean = 0.008 * math.sin(math.pi * u)
        rows.append([mb.v(x, h * env, z * (0.6 + 0.4 * env) + lean) for z, h in prof])
    for i in range(NX):
        for k in range(len(prof) - 1):
            (za, ha), (zb_, hb) = prof[k], prof[k + 1]
            reg = "foam" if (ha + hb) / 2 > 0.034 and (za + zb_) / 2 > -0.006 else "wave"
            out = (0.0, zb_ - za, -(hb - ha))                         # left normal of the walk = the air side
            mb.fo([rows[i][k], rows[i + 1][k], rows[i + 1][k + 1], rows[i][k + 1]], reg, out, True)
    for k, x in enumerate(np.linspace(-0.026, 0.026, 4)):            # foam blobs along the lip
        u = (x + 0.045) / 0.09
        env = math.sin(math.pi * u) ** 0.6
        lumpy(mb, (x, 0.060 * env, 0.020 + 0.008 * math.sin(math.pi * u)), 0.0100 * (0.6 + 0.4 * env), "foam",
              seg=8, rings=5, sh=0.7, amp=0.2, seed=k + 3)
    return mb


def crest_spots():
    """instances of the wave template: the back water and the far left, clear of the hull, the plank, the lane"""
    rng = random.Random(23)
    out = []
    tries = 0
    while len(out) < 22 and tries < 5000:
        tries += 1
        x = rng.uniform(-0.57, 0.02); z = rng.uniform(-0.575, -0.10)
        if in_lane(x, z, 0.05):
            continue
        if SHIP_X[0] - 0.05 < x < SHIP_X[1] + 0.04 and SHIP_C[1] - SHIP_HB - 0.045 < z < SHIP_C[1] + SHIP_HB + 0.045:
            continue
        if x > -0.16 and -0.30 < z < -0.12:                   # under / beside the plank and the mooring rope
            continue
        if x > -0.02:
            continue
        if any(math.hypot(x - a, (z - b) * 1.6) < 0.075 for a, b, _, _ in out):
            continue
        out.append((x, z, rng.uniform(-0.35, 0.35), rng.uniform(0.40, 0.52)))
    return out


def build_sea(root):
    """armature `sea` (action seaWave: the bone grid bobs and rolls, 4 s loop) with skinned children `seaWater`
    (the surface: printed wave marks, a deeper band at the back), `seaCrests` (curling crests, one template) and
    `seaFoam` (the white line at the shore and round the hull)"""
    cx, cz = (SEA_X[0] + SEA_X[1]) / 2, (FLOOR[2] + FLOOR[3]) / 2
    arm = bpy.data.armatures.new("sea_arm")
    rig = link(bpy.data.objects.new("sea", arm))
    rig.location = B(cx, 0.0, cz)
    parent_keep(rig, root)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    O = B(cx, 0, cz)
    r0 = arm.edit_bones.new("sea_root"); r0.head = B(cx, 0, cz) - O; r0.tail = B(cx, 0.03, cz) - O
    for i in range(NBX):
        for j in range(NBZ):
            b = arm.edit_bones.new(SEA_BONES[i][j])
            b.head = B(SEA_BX[i], 0, SEA_BZ[j]) - O; b.tail = B(SEA_BX[i], 0.03, SEA_BZ[j]) - O
            b.parent = r0
    for b in arm.edit_bones:
        b.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')

    def wt(_lv, wv):
        return bilinear_weights(wv[0], wv[2], SEA_BX, SEA_BZ, SEA_BONES)

    # surface
    mb = MB()
    step = 0.0125
    xs = list(np.arange(SEA_X[0], SEA_X[1] + 1e-6, step))
    zs = list(np.arange(FLOOR[2], FLOOR[3] + 1e-6, step))
    if zs[-1] < FLOOR[3] - 1e-6:
        zs.append(FLOOR[3])
    grid_surface(mb, xs, zs, sea_h, sea_region)
    for x, o in ((SEA_X[0], -1), (SEA_X[1], 1)):                  # skirts down to the page
        for j in range(len(zs) - 1):
            za, zb_ = zs[j], zs[j + 1]
            mb.fo([mb.v(x, sea_h(x, za), za), mb.v(x, sea_h(x, zb_), zb_), mb.v(x, -0.003, zb_), mb.v(x, -0.003, za)],
                  sea_region(x, (za + zb_) / 2), (o, 0, 0))
    for z, o in ((FLOOR[2], -1), (FLOOR[3], 1)):
        for i in range(len(xs) - 1):
            xa, xb = xs[i], xs[i + 1]
            mb.fo([mb.v(xa, sea_h(xa, z), z), mb.v(xb, sea_h(xb, z), z), mb.v(xb, 0.0, z), mb.v(xa, 0.0, z)],
                  sea_region((xa + xb) / 2, z), (0, 0, o))
    mb.W = {i: wt(None, mb.V[i]) for i in range(len(mb.V))}
    water = make_obj("seaWater", mb, None, origin=(cx, 0.0, cz), smooth_angle=60)
    # printed wave marks: little double arcs (print only, they wear the page)
    rng = random.Random(4)
    dec = DECOR.setdefault("ground", [])
    for k in range(70):
        x = rng.uniform(SEA_X[0] + 0.03, SEA_X[1] - 0.03); z = rng.uniform(FLOOR[2] + 0.03, FLOOR[3] - 0.03)
        if SHIP_X[0] - 0.02 < x < SHIP_X[1] + 0.02 and abs(z - SHIP_C[1]) < SHIP_HB + 0.02:
            continue
        L = rng.uniform(0.022, 0.034)
        pts = [(x + L * u, z - 0.007 * math.sin(math.pi * u * 2) * (1 if u < 0.5 else 0.6)) for u in np.linspace(0, 1, 7)]
        for (a, b), (c, d) in zip(pts[:-1], pts[1:]):
            dec.append(((a, sea_h(a, b) + 0.0002, b), (c, sea_h(c, d) + 0.0002, d)))
    # crests (template)
    tpl = wave_template()
    cm = MB()
    spots = crest_spots()
    for (x, z, yaw, s) in spots:
        def w2(lv, wv, x=x, z=z):
            return bilinear_weights(x, z, SEA_BX, SEA_BZ, SEA_BONES)
        cm.add(tpl, yaw_fn(x, z, yaw, s * 1.15, h0=SEA_LEVEL - 0.0012), weight=w2)
    crests = make_obj("seaCrests", cm, None, origin=(cx, 0.0, cz), smooth_angle=70)
    # foam: the shore line (scalloped ribbon) and a ring round the hull at the waterline
    fm = MB()
    fm.nr = True
    zz = np.linspace(FLOOR[2] + 0.004, FLOOR[3] - 0.004, 120)
    for k in range(len(zz) - 1):
        za, zb_ = zz[k], zz[k + 1]
        def edge(z, s):
            return SEA_X[1] - 0.006 + 0.004 * math.sin(z * 70) + s * (0.010 + 0.004 * abs(math.sin(z * 37)))
        ha, hb = 0.0052, 0.0052
        q = [fm.v(edge(za, -1), ha, za), fm.v(edge(za, 1), ha - 0.001, za), fm.v(edge(zb_, 1), hb - 0.001, zb_),
             fm.v(edge(zb_, -1), hb, zb_)]
        fm.fo(q, "foam", UP)
    for k in range(18):                                           # foam flecks along the line
        z = FLOOR[2] + 0.02 + (FLOOR[3] - FLOOR[2] - 0.04) * (k + 0.5) / 18
        lumpy(fm, (SEA_X[1] - 0.022 + 0.006 * math.sin(k * 2.3), 0.0046, z), 0.0042, "foam", seg=6, rings=3, sh=0.25,
              amp=0.25, seed=k)
    n = 64
    ring = []
    for k in range(n):                                            # hull outline at the waterline, 8 mm out
        a = TAU * k / n
        c = math.cos(a)
        x = SHIP_C[0] + ((SHIP_X[1] - SHIP_X[0]) / 2 + 0.006) * c
        w = hull_halfbeam(min(max(x, SHIP_X[0] + 1e-4), SHIP_X[1] - 1e-4)) * 0.84 + 0.006
        x += hull_rake(x, 0.06) * (1.0 if abs(c) > 0.3 else abs(c) / 0.3)
        ring.append((x, SHIP_C[1] + w * math.sin(a)))
    for k in range(n):
        (xa, za), (xb, zb_) = ring[k], ring[(k + 1) % n]
        oa = Vector(((xa - SHIP_C[0]) * 0.4, 0, za - SHIP_C[1])).normalized() * 0.0065
        ob = Vector(((xb - SHIP_C[0]) * 0.4, 0, zb_ - SHIP_C[1])).normalized() * 0.0065
        fm.fo([fm.v(xa, 0.0060, za), fm.v(xb, 0.0060, zb_), fm.v(xb + ob.x, 0.0052, zb_ + ob.z),
               fm.v(xa + oa.x, 0.0052, za + oa.z)], "foam", UP)
    fm.nr = False
    fm.W = {i: wt(None, fm.V[i]) for i in range(len(fm.V))}
    foam = make_obj("seaFoam", fm, None, origin=(cx, 0.0, cz), smooth_angle=60)
    for ob in (water, crests, foam):
        parent_keep(ob, rig)
        mod = ob.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
    # seaWave: 4 s loop at 24 fps (frame 1 == frame 97); a swell runs right-to-left across the water with a second
    # shorter one from the back; every term is a whole number of cycles per loop, so the loop is seamless
    bpy.context.scene.render.fps = 24
    rig.animation_data_create()
    for i in range(NBX):
        for j in range(NBZ):
            pb = rig.pose.bones[SEA_BONES[i][j]]
            inv = rig.data.bones[pb.name].matrix_local.to_3x3().inverted()
            bx, bz = SEA_BX[i], SEA_BZ[j]
            amp = 1.0 if not in_lane(bx, bz) else 0.75
            shore = max(0.35, min(1.0, (SEA_X[1] - bx) / 0.12))
            for f in range(1, 98, 4):
                u = TAU * (f - 1) / 96
                ph = 9.0 * bx + 4.0 * bz
                dy = (0.0013 * math.sin(u + ph) + 0.0005 * math.sin(2 * u - 6.0 * bz + 1.1 * bx)) * amp * shore
                dx = 0.0016 * math.cos(u + ph) * amp * shore
                dz = 0.0008 * math.sin(u + ph + 0.7) * amp * shore
                pb.location = inv @ B(dx, dy, dz)
                pb.keyframe_insert("location", frame=f)
    act = rig.animation_data.action
    act.name = "seaWave"
    return rig, water, crests, foam, tpl, spots


# ============================================================================================ ship
STRAKES = 7
GUNWALE = 0.107                       # gunwale top in the waist: a 7 mm lip, so the deck marks stay clear


def gunwale_h(x):
    g = GUNWALE
    if x < -0.470:                                                  # the stern sweeps up into the stern post
        g += 0.052 * ((-0.470 - x) / (-0.470 - SHIP_X[0])) ** 1.6
    if x > -0.180:                                                  # the bow: low where the plank comes aboard
        g -= 0.007 * min(1.0, (x + 0.180) / 0.02)
    return g


def hull_rake(x, t):
    """the ends lean out toward the top: a raked bow (its foot 3.4 cm ahead of the deck edge, under the plank) and an
    overhanging stern"""
    wb = max(0.0, (x + 0.25) / (SHIP_X[1] + 0.25)) ** 3
    ws = max(0.0, (-0.44 - x) / (-0.44 - SHIP_X[0])) ** 3
    return (0.024 * wb + 0.022 * ws) * max(0.0, 1.0 - t) ** 1.4


def hull_section(t, k_strake=True):
    """outward offset factor of the hull at height fraction t (0 page .. 1 gunwale): round belly + clinker steps"""
    f = 0.80 + 0.20 * math.sin(0.5 * math.pi * min(1.0, t / 0.62))
    return f


def build_ship(root):
    """`ship` (pivot at the deck centre; action shipRock): clinker hull, plank deck, gunwale, stern post, steering
    oar, mast + yard + furled sail, rope ladder, stays and rope rails. Child `cargo`."""
    mb = MB()
    sx0, sx1 = SHIP_X
    zc = SHIP_C[1]
    NX = 46
    xs = [sx0 + (sx1 - sx0) * (0.5 - 0.5 * math.cos(math.pi * i / NX)) for i in range(NX + 1)]
    # outer skin, both sides: rows of strakes (each strake: proud 1.3 mm at its lower edge, flush at its top)
    ts = []
    for k in range(STRAKES):
        a, b = k / STRAKES, (k + 1) / STRAKES
        ts += [(a, 0.0013), (b - 0.0001, 0.0)]
    ts = [(-0.06, 0.0)] + ts
    for side in (1, -1):
        rows = []
        for x in xs:
            w = hull_halfbeam(x); g = gunwale_h(x)
            ring = []
            for t, o in ts:
                h = max(-0.006, g * t)
                ring.append(mb.v(x + hull_rake(x, t), h, zc + side * (w * hull_section(max(t, 0.0)) + o * min(1.0, w / 0.035))))
            rows.append(ring)
        for i in range(NX):
            for k in range(len(ts) - 1):
                mb.fo([rows[i][k], rows[i + 1][k], rows[i + 1][k + 1], rows[i][k + 1]], "hull", (0, 0.1, side),
                      True)
    # gunwale cap (5 mm wide) and the inner bulwark down to the deck
    cap_w = 0.0055
    for side in (1, -1):
        top_o, top_i, dk = [], [], []
        for x in xs:
            w = hull_halfbeam(x); g = gunwale_h(x)
            wo = w * hull_section(1.0)
            wi = max(0.0, wo - cap_w)
            top_o.append(mb.v(x, g, zc + side * wo)); top_i.append(mb.v(x, g, zc + side * wi))
            dk.append(mb.v(x, min(g, DECK), zc + side * wi))
        for i in range(NX):
            mb.fo([top_o[i], top_o[i + 1], top_i[i + 1], top_i[i]], "hull", UP, False)
            mb.fo([top_i[i], top_i[i + 1], dk[i + 1], dk[i]], "hull", (0, 0, -side), False)
    # deck: flat at DECK inside the bulwarks, planks with shallow grooves between them (they catch the light)
    seams = list(np.arange(zc - SHIP_HB + 0.012, zc + SHIP_HB - 0.006, 0.0165))
    for i in range(NX):
        xa, xb = xs[i], xs[i + 1]
        wa = max(0.0, hull_halfbeam(xa) * hull_section(1.0) - cap_w)
        wb = max(0.0, hull_halfbeam(xb) * hull_section(1.0) - cap_w)
        cuts = [-1.0] + [s_ - zc for s_ in seams] + [1.0]
        for k in range(len(cuts) - 1):
            lo, hi = cuts[k] + (0.0006 if k else 0.0), cuts[k + 1] - (0.0006 if k < len(cuts) - 2 else 0.0)
            za0, za1 = max(lo, -wa), min(hi, wa); zb0, zb1 = max(lo, -wb), min(hi, wb)
            if za1 - za0 < 1e-4 and zb1 - zb0 < 1e-4:
                continue
            mb.fo([mb.v(xa, DECK, zc + za0), mb.v(xb, DECK, zc + zb0), mb.v(xb, DECK, zc + zb1), mb.v(xa, DECK, zc + za1)],
                  "deck", UP)
        for s_ in seams:                                              # the groove: two little walls and a floor
            d = s_ - zc
            if abs(d) + 0.0006 > min(wa, wb):
                continue
            for e0, e1 in ((d - 0.0006, d - 0.0002), (d + 0.0002, d + 0.0006)):
                mb.fo([mb.v(xa, DECK, zc + e0), mb.v(xb, DECK, zc + e0), mb.v(xb, DECK - 0.0008, zc + e1),
                       mb.v(xa, DECK - 0.0008, zc + e1)], "deck", (0, 0.3, 1 if e0 < d else -1))
            mb.fo([mb.v(xa, DECK - 0.0008, zc + d - 0.0002), mb.v(xb, DECK - 0.0008, zc + d - 0.0002),
                   mb.v(xb, DECK - 0.0008, zc + d + 0.0002), mb.v(xa, DECK - 0.0008, zc + d + 0.0002)], "deck", UP)
    dec = DECOR.setdefault("ship", [])
    # printed: one wale line along the viewer side of the hull (the strakes and deck planks are relief only, so the
    # printed hull and deck stay big enough to colour)
    t = 0.55
    pts = []
    for x in xs[1:-1]:
        o = 0.0013 * 0.6
        pts.append((x + hull_rake(x, t), gunwale_h(x) * t, zc + hull_halfbeam(x) * hull_section(t) + o + 0.0006))
    for a_, b_ in zip(pts[:-1], pts[1:]):
        dec.append((a_, b_))
    # stern post: rises from the stern and curls inboard like a fern
    sp = [(sx0 + 0.004, 0.02), (sx0 - 0.008, 0.10), (sx0 - 0.016, 0.165), (sx0 - 0.016, 0.215), (sx0 - 0.004, 0.252),
          (sx0 + 0.016, 0.268), (sx0 + 0.033, 0.258), (sx0 + 0.036, 0.238), (sx0 + 0.026, 0.226), (sx0 + 0.016, 0.234)]
    tube(mb, [(x, h, zc) for x, h in sp], [0.0125, 0.0125, 0.0115, 0.0105, 0.0095, 0.0085, 0.0075, 0.0065, 0.0055,
                                           0.0045], "wood", seg=10, smooth=True, ref=(0, 0, 1))
    # steering oar on the viewer side of the stern: blade in the water, loom up past the gunwale, a lashing
    ob, ot = Vector((-0.566, 0.004, zc + 0.098)), Vector((-0.487, 0.205, zc + 0.054))
    tube(mb, [tuple(ob + (ot - ob) * 0.22), tuple(ot)], [0.0052, 0.0045], "wood", seg=8)
    sphere(mb, tuple(ot + (ot - ob).normalized() * 0.002), 0.0062, "wood", seg=8, rings=5)
    ax = (ot - ob).normalized(); sd_ = ax.cross(Vector((0, 0, 1))).normalized()
    bl = [ob + ax * 0.0, ob + ax * 0.095]
    poly = []
    for u in np.linspace(0, 1, 9):
        c = bl[0] + (bl[1] - bl[0]) * u
        w = 0.024 * (0.75 + 0.25 * math.sin(math.pi * min(1.0, u * 1.3))) * (1 - 0.55 * max(0.0, u - 0.7) / 0.3)
        poly.append((c, w))
    L_, R_ = [], []
    for c, w in poly:
        L_.append((mb.v(*(c - sd_ * w + Vector((0, 0, 0.0025)))), mb.v(*(c - sd_ * w - Vector((0, 0, 0.0025))))))
        R_.append((mb.v(*(c + sd_ * w + Vector((0, 0, 0.0025)))), mb.v(*(c + sd_ * w - Vector((0, 0, 0.0025))))))
    for i in range(len(poly) - 1):
        for f, o in ((0, (0, 0, 1)), (1, (0, 0, -1))):
            mb.fo([L_[i][f], R_[i][f], R_[i + 1][f], L_[i + 1][f]], "wood", o)
        mb.fo([L_[i][0], L_[i + 1][0], L_[i + 1][1], L_[i][1]], "wood", tuple(-sd_))
        mb.fo([R_[i][0], R_[i + 1][0], R_[i + 1][1], R_[i][1]], "wood", tuple(sd_))
    mb.fo([L_[0][0], R_[0][0], R_[0][1], L_[0][1]], "wood", tuple(-ax))
    mb.fo([L_[-1][0], R_[-1][0], R_[-1][1], L_[-1][1]], "wood", tuple(ax))
    # mast, partner block on the back rail, truck, pennant
    mx, mz = MAST
    box(mb, mx - 0.012, mx + 0.012, DECK - 0.03, GUNWALE + 0.016, mz - 0.010, mz + 0.006, "wood", skip=("bottom",))
    lathe(mb, [(0.0, DECK - 0.02), (0.0092, DECK - 0.02), (0.0088, 0.30), (0.0074, MAST_TOP - 0.008),
               (0.0, MAST_TOP - 0.004)], "wood", C=(mx, 0, mz), seg=12)
    sphere(mb, (mx, MAST_TOP - 0.004, mz), 0.0072, "wood", seg=10, rings=6)
    pen = [(mx - 0.006, MAST_TOP - 0.008, mz), (mx - 0.026, MAST_TOP - 0.012, mz + 0.002), (mx - 0.048, MAST_TOP - 0.010, mz),
           (mx - 0.066, MAST_TOP - 0.016, mz + 0.002)]                # streams aft, away from the deck marks
    blade(mb, pen, [0.016, 0.012, 0.007, 0.0], "stripe", nrm=(0, 0, 1))
    # yard + furled sail: the cloth gathered under the yard in three swags, two red stripes
    y0, y1 = YARD_X
    yz = mz - 0.011                                                   # yard and sail hang behind the mast
    tube(mb, [(y0, YARD_H, yz), ((y0 + y1) / 2, YARD_H + 0.003, yz), (y1, YARD_H, yz)],
         [0.0040, 0.0058, 0.0040], "wood", seg=8)
    sx_a, sx_b = -0.556, -0.337
    stripes = [(-0.514, -0.470), (MAST[0] + 0.0080, sx_b)]          # cream | red | cream | mast | red (big cells)
    NU, NV = 44, 7
    rowsS = []
    for i in range(NU + 1):
        u = i / NU; x = sx_a + (sx_b - sx_a) * u
        sw = abs(math.sin(math.pi * 3 * u))                       # three swags
        drop = 0.050 + 0.018 * sw
        ring = []
        for j in range(NV + 1):
            v = j / NV
            a = math.pi * v
            h = YARD_H - 0.004 - drop * (0.5 - 0.5 * math.cos(a)) ** 0.9
            bulge = (0.013 + 0.006 * sw) * math.sin(a) ** 0.8
            ring.append(mb.v(x, h, yz - 0.002 + bulge * 0.55))
        rowsS.append(ring)
    for i in range(NU):
        xm = sx_a + (sx_b - sx_a) * (i + 0.5) / NU
        reg = "stripe" if any(a <= xm <= b for a, b in stripes) else "sail"
        for j in range(NV):
            mb.fo([rowsS[i][j], rowsS[i + 1][j], rowsS[i + 1][j + 1], rowsS[i][j + 1]], reg, (0, -0.2, 1), True)
    for i in (0, NU):
        c = mb.v(sx_a + (sx_b - sx_a) * i / NU, YARD_H - 0.03, yz)
        for j in range(NV):
            mb.fo([c, rowsS[i][j], rowsS[i][j + 1]], "sail", (-1 if i == 0 else 1, 0, 0), True)
    # rope rails: posts on the gunwale where they are clear of every deck mark and walk (rope = named texel)
    mb.nr = True
    posts = []
    for side in (1, -1):
        run = []
        for x in np.arange(sx0 + 0.035, sx1 - 0.030, 0.026):
            w = hull_halfbeam(x) * hull_section(1.0) - cap_w / 2
            z = zc + side * w
            ok = deck_clear(x, z) >= 0.05 + 0.006 and gunwale_h(x) < GUNWALE + 0.02
            if ok:
                run.append((x, z))
            elif run:
                posts.append(run); run = []
        if run:
            posts.append(run)
    for run in posts:
        if len(run) < 2:
            continue
        for x, z in run:
            g = gunwale_h(x)
            lathe(mb, [(0.0, g - 0.002), (0.0032, g - 0.002), (0.0030, g + 0.026), (0.0040, g + 0.030),
                       (0.0, g + 0.033)], "wood", C=(x, 0, z), seg=6, smooth=False)
        pts = [(x, gunwale_h(x) + 0.026, z) for x, z in run]
        sag = []
        for (xa, ha, za), (xb, hb, zb_) in zip(pts[:-1], pts[1:]):
            for u in (0.0, 0.5):
                sag.append((xa + (xb - xa) * u, ha + (hb - ha) * u - (0.003 if u == 0.5 else 0.0), za + (zb_ - za) * u))
        sag.append(pts[-1])
        tube(mb, sag, 0.0017, "wood", seg=5, caps=False)
    # rope ladder (shrouds with ratlines) from the back rail left of the mast up to the masthead
    la, lb = Vector((-0.470, GUNWALE + 0.002, mz + 0.002)), Vector((-0.432, GUNWALE + 0.002, mz + 0.002))
    ta, tb = Vector((mx - 0.007, MAST_TOP - 0.03, mz)), Vector((mx - 0.003, MAST_TOP - 0.03, mz))
    tube(mb, [tuple(la), tuple(ta)], 0.0016, "wood", seg=5)
    tube(mb, [tuple(lb), tuple(tb)], 0.0016, "wood", seg=5)
    for u in np.arange(0.07, 0.95, 0.075):
        tube(mb, [tuple(la + (ta - la) * u), tuple(lb + (tb - lb) * u)], 0.0013, "wood", seg=4, caps=False)
    # stays: backstay to the stern post, lifts to the yard ends, a forestay-less rig (the walk to the rail is free)
    top = Vector((mx, MAST_TOP - 0.01, mz))
    tube(mb, [tuple(top), (sx0 + 0.006, 0.262, zc - 0.004)], 0.0014, "wood", seg=4)
    for xe in (y0 + 0.004, y1 - 0.004):
        tube(mb, [tuple(top), (xe, YARD_H + 0.003, yz)], 0.0012, "wood", seg=4)
    tube(mb, [tuple(top), (mx + 0.002, GUNWALE + 0.004, mz - 0.006)], 0.0013, "wood", seg=4)
    # a mooring cleat on the bow quarter and a coil of rope on the stern deck
    for k in range(3):
        a = 0.6 * k
        tube(mb, [(-0.512 + 0.009 * math.cos(a + t), DECK + 0.0018 + 0.0012 * k, zc + 0.004 + 0.009 * math.sin(a + t))
                  for t in np.linspace(0, TAU, 14)], 0.0018, "wood", seg=4, closed=True)
    mb.nr = False
    ob = make_obj("ship", mb, root, origin=(SHIP_C[0], DECK, SHIP_C[1]), smooth_angle=50)
    return ob


def cargo_spots():
    """sacks and jars: in front of Jonah's sleeping place (he sleeps *behind* them, seen from the viewer) and at
    the stern, each clear of every deck mark and walk by 0.05 + its radius"""
    want = [("sack", -0.334, -0.174, 0.0190), ("sack", -0.368, -0.172, 0.0140), ("jar", -0.310, -0.168, 0.0105),
            ("sack", -0.500, -0.248, 0.0170), ("jar", -0.495, -0.192, 0.0140), ("sack", -0.474, -0.262, 0.0130),
            ("sack", -0.360, -0.172, 0.0120), ("jar", -0.305, -0.167, 0.0100), ("sack", -0.480, -0.262, 0.0115),
            ("jar", -0.515, -0.215, 0.0100)]
    out = []
    for kind, x0, z0, r in want:                       # nearest free spot to the wanted one (1 mm grid, 2 cm round)
        best = None
        for x in np.arange(x0 - 0.02, x0 + 0.0201, 0.001):
            for z in np.arange(z0 - 0.02, z0 + 0.0201, 0.001):
                if deck_clear(x, z) < 0.05 + r + 0.003:          # + the roll of shipRock
                    continue
                if abs(z - SHIP_C[1]) + r > hull_halfbeam(x) * hull_section(1.0) - 0.0065:
                    continue
                if any(math.hypot(x - a, z - b) < r + rr + 0.001 for _, a, b, rr in out):
                    continue
                d = math.hypot(x - x0, z - z0)
                if best is None or d < best[0]:
                    best = (d, round(float(x), 3), round(float(z), 3))
        if best:
            out.append((kind, best[1], best[2], r))
    return out


def sack_template():
    """one plump tied sack, modelled at 2x (radius 0.030): every sack on the ship wears its drawing"""
    mb = MB()
    r = 0.030
    lumpy(mb, (0.0, r * 0.95, 0.0), r, "sack", seg=14, rings=8, sh=1.05, amp=0.06, seed=40, flat_bottom=0.0005)
    lathe(mb, [(0.0, r * 1.80), (r * 0.46, r * 1.82), (r * 0.30, r * 2.02), (r * 0.46, r * 2.34), (0.0, r * 2.40)],
          "sack", C=(0, 0, 0), seg=10)
    mb.nr = True
    tube(mb, [(r * 0.33 * math.cos(a), r * 1.96, r * 0.33 * math.sin(a)) for a in np.linspace(0, TAU, 12)], 0.0022,
         "sackTie", seg=5, closed=True)
    mb.nr = False
    return mb


def build_cargo(ship):
    """`cargo` (child of the ship): sacks (instances of one sack drawing) and storage jars (clay texel)"""
    mb = MB()
    tpl = sack_template()
    spots = cargo_spots()
    for i, (kind, x, z, r) in enumerate(spots):
        if kind == "sack":
            mb.add(tpl, yaw_fn(x, z, 0.7 * i, r / 0.030, h0=DECK))
        else:                                                         # a storage jar with a lip and two handles
            mb.nr = True
            H = r * 3.3
            lathe(mb, [(0.0, DECK), (r * 0.55, DECK), (r * 0.95, DECK + H * 0.25), (r, DECK + H * 0.55),
                       (r * 0.62, DECK + H * 0.84), (r * 0.42, DECK + H * 0.9), (r * 0.5, DECK + H), (r * 0.36, DECK + H),
                       (0.0, DECK + H * 0.96)], "jar", C=(x, 0, z), seg=14)
            for s in (-1, 1):
                tube(mb, [(x + s * r * 0.45, DECK + H * 0.86, z), (x + s * r * 0.95, DECK + H * 0.82, z),
                          (x + s * r * 0.9, DECK + H * 0.62, z)], 0.0018, "jar", seg=5)
            mb.nr = False
    hmax = max(v[1] for v in mb.V)
    assert hmax <= 0.16 + 1e-6, hmax
    return make_obj("cargo", mb, ship, origin=(SHIP_C[0], DECK, SHIP_C[1]), smooth_angle=55), spots, tpl


def build_plank(root):
    """the gangplank from the sand (on a stone) up to the bow: a board with cross cleats and a rope hand-loop"""
    mb = MB()
    a, b = Vector(PLANK_FOOT), Vector(PLANK_TOP)
    ax = (b - a); L = ax.length; t = ax.normalized()
    side = t.cross(Vector((0, 1, 0))).normalized()
    up = side.cross(t).normalized()
    if up.y < 0:
        up = -up
    W, T = 0.026, 0.0055
    n = 12
    rows = []
    for k in range(n + 1):
        c = a + ax * (k / n) - up * 0.0005
        sag = -0.004 * math.sin(math.pi * k / n)
        c = c + up * sag
        rows.append([mb.v(*(c + side * s * W - up * d)) for s, d in ((-1, 0), (1, 0), (1, T), (-1, T))])
    for k in range(n):
        for q in range(4):
            mb.fo([rows[k][q], rows[k + 1][q], rows[k + 1][(q + 1) % 4], rows[k][(q + 1) % 4]], "deck",
                  tuple((side * [-1, 1, 1, -1][q] * 0.0) + up * [1, 0, -1, 0][q] + side * [0, 1, 0, -1][q]))
    for e in (0, n):
        mb.fo(rows[e], "deck", tuple(t * (1 if e else -1)))
    for u in np.arange(0.08, 0.95, 0.105):                            # cleats
        c = a + ax * u + up * (-0.004 * math.sin(math.pi * u))
        box_pts = [c + side * s * (W - 0.002) + t * dt + up * dh for s in (-1, 1) for dt in (-0.003, 0.003)
                   for dh in (0.0, 0.0028)]
        V = [mb.v(*p) for p in box_pts]
        for f, o in (((0, 1, 3, 2), -side), ((4, 5, 7, 6), side), ((1, 5, 7, 3), t), ((0, 4, 6, 2), -t),
                     ((2, 3, 7, 6), up)):
            mb.fo([V[i] for i in f], "deck", tuple(o))
    # the stone under the foot
    mb.nr = True
    lumpy(mb, (a.x + 0.006, 0.007, a.z), 0.014, "stone", seg=9, rings=5, sh=0.55, sx=1.3, amp=0.15, seed=77,
          flat_bottom=0.0)
    mb.nr = False
    return make_obj("plank", mb, root, origin=tuple(a), smooth_angle=40)


# ============================================================================================ land: beach, road, ground, hill
def shore_x(z):
    """the sand / earth boundary"""
    return BEACH_X[1] + 0.010 * math.sin(13 * z + 0.4) + 0.006 * math.sin(31 * z)


def road_polys():
    main = catmull([(0.605, 0.184), (0.52, 0.182), (0.44, 0.186), (0.36, 0.174), (0.29, 0.150), (0.225, 0.124),
                    (0.17, 0.108), (0.13, 0.098)], 0.012)
    branch = catmull([(0.232, 0.128), (0.244, 0.03), (0.262, -0.08), (0.29, -0.18), (0.316, -0.265),
                      (0.334, -0.32)], 0.012)
    plaza = np.array([(0.245, -0.371), (0.292, -0.373), (0.292, -0.393), (0.388, -0.393), (0.388, -0.373),
                      (0.437, -0.371), (0.452, -0.320), (0.418, -0.268), (0.262, -0.268), (0.232, -0.320)])
    return strip_poly(main, 0.074, 0.050), strip_poly(branch, 0.066, 0.082), plaza, main, branch


def hill_poly():
    return np.array([(HILL_C[0] + HILL_R * (1 + 0.06 * math.sin(3 * a + 0.5) + 0.03 * math.sin(7 * a)) * math.cos(a),
                      HILL_C[1] + HILL_R * (1 + 0.06 * math.sin(3 * a + 0.5) + 0.03 * math.sin(7 * a)) * math.sin(a))
                     for a in np.linspace(0, TAU, 48, endpoint=False)])


def hill_h(x, z):
    a = math.atan2(z - HILL_C[1], x - HILL_C[0])
    R = HILL_R * (1 + 0.06 * math.sin(3 * a + 0.5) + 0.03 * math.sin(7 * a))
    rr = math.hypot(x - HILL_C[0], z - HILL_C[1]) / R
    if rr >= 1.0:
        return 0.0
    return HILL_TOP * (1 - rr * rr) ** 1.7 * (1 + 0.06 * math.sin(9 * x + 5 * z))


def land_h(x, z):
    if x < shore_x(z):
        if x < 0.07:
            h = 0.0040 - (0.07 - x) * 0.12
        else:
            h = 0.0040 + 0.0010 * min(1.0, (x - 0.07) / 0.10) + 0.00045 * math.sin(x * 170 + 3 * math.sin(z * 25))
    else:
        h = 0.0050 + 0.0006 * (nz(x * 3, z * 3) - 0.5)
    return h + hill_h(x, z)


def build_land(root):
    """`beach` (sand, rippled, under the water at its edge), `road` (main road along the front + branch and plaza
    at the gate), `ground` (earth), `hill` (the low mound): one constrained triangulation, four meshes"""
    main, branch, plaza, _, _ = road_polys()
    hp = hill_poly()
    x0 = BEACH_X[0]
    rect = np.array([(x0, FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (x0, FLOOR[2])])
    zz = np.linspace(FLOOR[2], FLOOR[3], 70)
    shore = np.array([(shore_x(z), z) for z in zz])
    outlines = [_resample(rect, 0.02), _resample(main, 0.010), _resample(branch, 0.010), _resample(plaza, 0.010),
                _resample(hp, 0.010)]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    b = len(verts)
    verts += [Vector((float(x), float(z))) for x, z in shore]
    edges += [(b + i, b + i + 1) for i in range(len(shore) - 1)]
    allo = np.concatenate(outlines + [shore])
    for j, z in enumerate(np.arange(FLOOR[2] + 0.01, FLOOR[3] - 0.005, 0.016)):
        for x in np.arange(x0 + 0.008 + (j % 2) * 0.008, FLOOR[1] - 0.005, 0.016):
            p = np.array([x + (nz(x, z) - 0.5) * 0.005, z + (nz(z, x) - 0.5) * 0.005])
            if np.min(np.hypot(*(allo - p).T)) > 0.006:
                verts.append(Vector((float(p[0]), float(p[1]))))
    for x in np.arange(HILL_C[0] - HILL_R, HILL_C[0] + HILL_R, 0.009):         # denser on the mound
        for z in np.arange(HILL_C[1] - HILL_R, HILL_C[1] + HILL_R, 0.009):
            p = np.array([x + 0.004, z + 0.002])
            if in_poly(p, hp) and np.min(np.hypot(*(allo - p).T)) > 0.005:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def region(c):
        if in_poly(c, main) or in_poly(c, branch) or in_poly(c, plaza):
            return "road"
        if in_poly(c, hp):
            return "hill"
        return "sand" if c[0] < shore_x(c[1]) else "earth"
    H = [land_h(x, z) for x, z in V]
    mbs = {k: MB() for k in ("beach", "road", "ground", "hill")}
    node = {"sand": "beach", "road": "road", "earth": "ground", "hill": "hill"}
    idx = {k: {} for k in mbs}
    for f in fs:
        if len(f) != 3:
            continue
        c = tuple(V[list(f)].mean(0))
        reg = region(c); k = node[reg]
        q = []
        for i in f:
            if i not in idx[k]:
                hh = H[i] + (0.0003 if reg == "road" else 0.0)
                idx[k][i] = mbs[k].v(V[i][0], hh, V[i][1])
            q.append(idx[k][i])
        mbs[k].fo(q, reg, UP, True)
    # skirts round the land's page edges (right, front, back)
    for (ax_, az), (bx, bz) in ((rect[0], rect[1]), (rect[1], rect[2]), (rect[2], rect[3])):
        n = int(math.hypot(bx - ax_, bz - az) / 0.02) + 1
        for i in range(n):
            xa, za = ax_ + (bx - ax_) * i / n, az + (bz - az) * i / n
            xb, zb_ = ax_ + (bx - ax_) * (i + 1) / n, az + (bz - az) * (i + 1) / n
            reg = region(((xa + xb) / 2 - (0.003 if abs(bx - ax_) < 1e-6 else 0), (za + zb_) / 2))
            k = node[reg]
            o = (1, 0, 0) if abs(bx - ax_) < 1e-6 else (0, 0, 1 if abs(az - FLOOR[3]) < 1e-6 else -1)
            mbs[k].fo([mbs[k].v(xa, land_h(xa, za), za), mbs[k].v(xb, land_h(xb, zb_), zb_), mbs[k].v(xb, -0.002, zb_),
                       mbs[k].v(xa, -0.002, za)], reg, o)
    # printed sand ripples (parallel to the water's edge) and a few cracks in the earth
    dec = DECOR.setdefault("ground", [])
    rng = random.Random(12)
    for k in range(16):
        x = rng.uniform(0.075, 0.20); z = rng.uniform(FLOOR[2] + 0.03, FLOOR[3] - 0.03)
        if any(in_poly((x, z + dz), poly) for poly in (main, branch) for dz in (-0.02, 0.0, 0.02)):
            continue
        L = rng.uniform(0.025, 0.045)
        pts = [(x + 0.004 * math.sin(u * 6), z - L / 2 + L * u) for u in np.linspace(0, 1, 6)]
        if max(p[0] for p in pts) > shore_x(z) - 0.008:
            continue
        for (a, b_), (c, d) in zip(pts[:-1], pts[1:]):
            dec.append(((a, land_h(a, b_) + 0.0003, b_), (c, land_h(c, d) + 0.0003, d)))
    beach = make_obj("beach", mbs["beach"], root, smooth_angle=35)
    road = make_obj("road", mbs["road"], root, smooth_angle=35)
    ground = make_obj("ground", mbs["ground"], root, smooth_angle=35)
    hill = make_obj("hill", mbs["hill"], root, origin=(HILL_C[0], 0.0, HILL_C[1]), smooth_angle=35)
    return beach, road, ground, hill


def build_beach_props(beach):
    """children of `beach`: `boat` (its own drawing) and `beachProps` (posts, ropes, coil, shells: named texels)"""
    # rowing boat, pulled up with its bow to the water, a little heeled over (named texels: hull, deck, wood)
    mb = MB()
    mb.nr = True
    L, Wb, Dp = 0.112, 0.024, 0.024
    NX = 18
    xs = [-L / 2 + L * (0.5 - 0.5 * math.cos(math.pi * i / NX)) for i in range(NX + 1)]
    hw = lambda x: Wb * max(0.0, 1 - abs(2 * x / L) ** 2.6) ** 0.5
    sheer = lambda x: Dp + 0.008 * (2 * x / L) ** 2
    rows_o, rows_i = [], []
    for side in (1, -1):
        ro, ri = [], []
        for x in xs:
            w = hw(x); g = sheer(x)
            ro.append([mb.v(x, g * t, side * w * (0.55 + 0.45 * math.sin(0.5 * math.pi * min(1, t / 0.7))))
                       for t in np.linspace(0, 1, 6)])
            ri.append([mb.v(x, 0.004 + (g - 0.004) * t, side * max(0.0, w - 0.003) * (0.45 + 0.55 * math.sin(0.5 * math.pi * min(1, t / 0.7))))
                       for t in np.linspace(0, 1, 6)])
        for i in range(NX):
            for k in range(5):
                mb.fo([ro[i][k], ro[i + 1][k], ro[i + 1][k + 1], ro[i][k + 1]], "boatHull", (0, -0.2, side), True)
                mb.fo([ri[i][k], ri[i + 1][k], ri[i + 1][k + 1], ri[i][k + 1]], "boatInside", (0, 0.4, -side), True)
            mb.fo([ro[i][5], ro[i + 1][5], ri[i + 1][5], ri[i][5]], "boatHull", UP)
        rows_o.append(ro); rows_i.append(ri)
    for i in range(NX):                                              # bottom boards inside
        mb.fo([rows_i[0][i][0], rows_i[0][i + 1][0], rows_i[1][i + 1][0], rows_i[1][i][0]], "boatInside", UP)
    for xt in (-0.022, 0.024):                                       # thwarts
        w = hw(xt) - 0.003
        box(mb, xt - 0.007, xt + 0.007, Dp - 0.008, Dp - 0.004, -w, w, "boatInside")
    for s, (xa, xb) in ((1, (-0.045, 0.050)), (-1, (-0.040, 0.046))):  # two oars lying across the thwarts
        tube(mb, [(xa, Dp - 0.002, s * 0.006), (xb, Dp - 0.001, s * 0.003)], 0.0022, "boatInside", seg=6)
        blade(mb, [(xa, Dp - 0.002, s * 0.006), (xa - 0.022, Dp - 0.004, s * 0.007)], [0.010, 0.012], "boatInside",
              nrm=(0, 1, 0))
    yaw, heel = math.radians(-24), math.radians(7)
    bx, bz = BOAT
    q = Euler((0, 0, 0)); M = Quaternion((0, 1, 0), yaw) @ Quaternion((1, 0, 0), heel)
    for i, v in enumerate(mb.V):
        p = M @ Vector(v)
        mb.V[i] = (bx + p.x, max(p.y, -0.002) + 0.0045, bz + p.z)
        mb.P[i] = mb.V[i]
    mb.nr = False
    boat = make_obj("boat", mb, beach, origin=(bx, 0.0, bz), smooth_angle=50)
    # posts, ropes, coil, shells
    pm = MB()
    pm.nr = True
    for i, (x, z) in enumerate(POSTS):
        lathe(pm, [(0.0, -0.002), (0.0078, -0.002), (0.0075, 0.050), (0.0060, 0.056), (0.0, 0.057)], "wood",
              C=(x, 0, z), seg=10)
        for k in range(3):
            tube(pm, [(x + 0.0088 * math.cos(t), 0.040 + 0.0028 * k + 0.0012 * math.sin(t * 2), z + 0.0088 * math.sin(t))
                      for t in np.linspace(0, TAU, 12)], 0.0019, "wood", seg=4, closed=True)
    ends = [(-0.168, 0.097, -0.258), (-0.168, 0.097, -0.183)]
    for (x, z), e in zip(POSTS, ends):
        a, b = Vector((x, 0.043, z)), Vector(e)
        pts = [tuple(a + (b - a) * u - Vector((0, 0.022 * math.sin(math.pi * u), 0))) for u in np.linspace(0, 1, 14)]
        tube(pm, pts, 0.0017, "wood", seg=5)
    cx_, cz_ = 0.072, -0.312                                          # a coil of rope on the sand
    for k in range(4):
        r = 0.0125 - 0.0022 * k
        tube(pm, [(cx_ + r * math.cos(t), land_h(cx_, cz_) + 0.0018 + 0.0006 * k, cz_ + r * math.sin(t))
                  for t in np.linspace(0, TAU, 16)], 0.0019, "wood", seg=4, closed=True)
    rng = random.Random(31)
    shells = []
    while len(shells) < 16:
        x, z = rng.uniform(0.075, 0.205), rng.uniform(FLOOR[2] + 0.02, FLOOR[3] - 0.02)
        if any(math.hypot(x - a, z - b) < 0.03 for a, b in shells) or math.hypot(x - BOAT[0], z - BOAT[1]) < 0.07:
            continue
        shells.append((x, z))
    for i, (x, z) in enumerate(shells):
        a = rng.uniform(0, TAU); r = rng.uniform(0.0045, 0.0065); h0 = land_h(x, z)
        c = pm.v(x, h0 + 0.0028, z)
        rim = [pm.v(x + r * math.cos(a + t), h0 + 0.0006 + 0.0010 * (k % 2), z + r * math.sin(a + t))
               for k, t in enumerate(np.linspace(-1.25, 1.25, 11))]
        for k in range(10):
            pm.fo([c, rim[k], rim[k + 1]], "foam", UP)
        if i % 4 == 0:                                                # a spiral snail shell now and then
            lumpy(pm, (x + 0.012, h0 + 0.002, z + 0.004), 0.0035, "foam", seg=7, rings=4, sh=0.8, amp=0.1, seed=i)
    pm.nr = False
    props = make_obj("beachProps", pm, beach, origin=(0.08, 0.0, -0.20), smooth_angle=50)
    return boat, props


def build_hill_props(hill):
    """child `hillProps` of `hill`: rocks and dry grass on the mound and the earth round it (named texels)"""
    rng = random.Random(41)
    mb = MB()
    mb.nr = True
    hp = hill_poly()
    rocks = []
    tries = 0
    while len(rocks) < 9 and tries < 4000:
        tries += 1
        a = rng.uniform(0, TAU); d = rng.uniform(0.55, 1.05) * HILL_R
        x, z = HILL_C[0] + d * math.cos(a), HILL_C[1] + d * math.sin(a)
        if not (FLOOR[0] < x < FLOOR[1] - 0.012 and z < FLOOR[3] - 0.012):
            continue
        r = rng.uniform(0.008, 0.015)
        if ground_clear(x, z) < 0.05 + r + 0.004 or math.hypot(x - PLANT[0], z - PLANT[1]) < 0.05:
            continue
        if any(math.hypot(x - sx, z - sz) < 0.03 for sx, sz in SHELTER_STICKS) or (0.45 < x and -0.09 < z < 0.07):
            continue
        if any(math.hypot(x - a_, z - b_) < 0.04 for a_, b_, _ in rocks):
            continue
        rocks.append((x, z, r))
    for i, (x, z, r) in enumerate(rocks):
        lumpy(mb, (x, land_h(x, z) + r * 0.25, z), r, "stone", seg=8, rings=5, sh=0.62, sx=rng.uniform(1.0, 1.4),
              amp=0.2, seed=i + 60, smooth=False)
    tufts = []
    tries = 0
    while len(tufts) < 34 and tries < 6000:
        tries += 1
        if rng.random() < 0.6:
            a = rng.uniform(0, TAU); d = rng.uniform(0.2, 1.1) * HILL_R
            x, z = HILL_C[0] + d * math.cos(a), HILL_C[1] + d * math.sin(a)
        else:
            x, z = rng.uniform(0.23, 0.59), rng.uniform(-0.36, 0.20)
        if not (0.23 < x < FLOOR[1] - 0.01 and FLOOR[2] < z < FLOOR[3] - 0.01):
            continue
        main, branch, plaza, _, _ = ROADS
        if in_poly((x, z), main) or in_poly((x, z), branch) or in_poly((x, z), plaza):
            continue
        if any(math.hypot(x - a_, z - b_) < 0.022 for a_, b_ in tufts) or math.hypot(x - PLANT[0], z - PLANT[1]) < 0.03:
            continue
        if ground_clear(x, z) < 0.058:
            continue
        tufts.append((x, z))
    for x, z in tufts:
        tall = 0.018 if ground_clear(x, z) > 0.07 else 0.0075
        h0 = land_h(x, z)
        for k in range(5):
            a = TAU * k / 5 + rng.uniform(-0.4, 0.4)
            hh = tall * rng.uniform(0.7, 1.05); lean = rng.uniform(0.3, 0.6) * hh
            d = (math.cos(a), math.sin(a))
            blade(mb, [(x + d[0] * 0.0015, h0, z + d[1] * 0.0015), (x + d[0] * lean, h0 + hh, z + d[1] * lean)],
                  [0.0034, 0.0], "dry", nrm=(d[0], 0.0, d[1]))
    mb.nr = False
    return make_obj("hillProps", mb, hill, origin=(HILL_C[0], 0.0, HILL_C[1]), smooth_angle=50), rocks, tufts


ROADS = road_polys()
SHELTER_STICKS = [(0.478, 0.050), (0.586, 0.048)]                  # the two poles (the third stick is the cross-stick)


# ============================================================================================ Nineveh
GATEHOUSE = (0.230, 0.450, -0.455, -0.378)     # x0 x1 zBack zFront (the gate node: two towers + the arch block)
GH_MID, GH_TOWER = 0.225, 0.265                # heights: block between the towers, towers
PLINTH = 0.062                                 # stone plinth height (one course of big blocks)
ARCH_C, ARCH_R = (GATE_X, GATE_H - GATE_W / 2), GATE_W / 2
HOUSES = [(0.212, 0.262, -0.548, -0.462, 0.238), (0.276, 0.360, -0.586, -0.466, 0.272),
          (0.360, 0.420, -0.525, -0.465, 0.246)]
TEMPLE = (0.432, 0.556, -0.585, -0.478)
PALMS = [(0.226, -0.576, 0.0), (0.574, -0.482, 1.3)]
MERLON = [(-0.011, 0.0), (0.011, 0.0), (0.011, 0.008), (0.0075, 0.008), (0.0075, 0.016), (0.004, 0.016),
          (0.004, 0.024), (-0.004, 0.024), (-0.004, 0.016), (-0.0075, 0.016), (-0.0075, 0.008), (-0.011, 0.008)]


def brick_decor(dec, x0, x1, h0, h1, z, course=0.014, brick=0.028, holes=(), density=1.0):
    """printed bricks in small clusters (a few courses of two or three bricks), so the wall reads as mud-brick while
    leaving plain areas big enough to colour (the full relief is in the 3D wall)"""
    rng = random.Random(int(abs(x0 * 1000 + z * 7000 + h0 * 300)))
    area = (x1 - x0) * (h1 - h0)
    n = max(1, int(round(area / 0.0045 * density)))
    for _ in range(n):
        nb, nc = rng.choice((2, 3)), rng.choice((2, 3))
        w, hh = nb * brick, nc * course
        if x1 - x0 < w + 0.01 or h1 - h0 < hh + 0.01:
            continue
        cx = rng.uniform(x0 + 0.004, x1 - w - 0.004); cy = rng.uniform(h0 + 0.004, h1 - hh - 0.004)
        if any(hx0 - 0.004 < cx + w and cx < hx1 + 0.004 and hh0 - 0.004 < cy + hh and cy < hh1 + 0.004
               for hx0, hx1, hh0, hh1 in holes):
            continue
        for r in range(nc + 1):
            dec.append(((cx + (0.4 * brick if r in (0, nc) else 0.0), cy + r * course, z),
                        (cx + w - (0.4 * brick if r in (0, nc) else 0.0), cy + r * course, z)))
        for r in range(nc):
            off = 0.0 if r % 2 == 0 else brick / 2
            for k in range(nb + 1):
                x = cx + off + k * brick
                if cx + 0.002 < x < cx + w - 0.002:
                    dec.append(((x, cy + r * course, z), (x, cy + (r + 1) * course, z)))


def brick_relief(mb, rng, x0, x1, h0, h1, z, course=0.0135, brick=0.027, blocked=None, n_proud=10):
    """real relief for the 3D wall (the printed lines are erased on the phone): every other course stands 1 mm
    proud, and a few single bricks 1.6 mm. blocked(h) -> list of (x0, x1) to leave out (the arch)."""
    k = 0
    h = h0
    while h < h1 - 0.004:
        hb = min(h + course, h1)
        segs = [(x0, x1)]
        for bx0, bx1 in (blocked(h, hb) if blocked else []):
            nxt = []
            for a, b in segs:
                if bx1 <= a or bx0 >= b:
                    nxt.append((a, b)); continue
                if bx0 > a:
                    nxt.append((a, bx0))
                if bx1 < b:
                    nxt.append((bx1, b))
            segs = nxt
        for a, b in segs:
            if b - a < 0.004:
                continue
            if k % 2 == 1:
                box(mb, a, b, h + 0.0004, hb - 0.0004, z - 0.001, z + 0.0010, "brick", skip=("back",))
            for _ in range(n_proud if k % 2 == 0 else 0):
                if rng.random() < 0.12 and b - a > brick * 1.2:
                    xs_ = a + rng.uniform(0.0, b - a - brick)
                    xs_ = a + round((xs_ - a) / brick) * brick + (brick / 2 if (k // 2) % 2 else 0.0)
                    if xs_ + brick <= b:
                        box(mb, xs_ + 0.0005, xs_ + brick - 0.0005, h + 0.0005, hb - 0.0005, z - 0.001, z + 0.0016,
                            "brick", skip=("back",))
        k += 1
        h += course


def outline_decor(dec, pts, z):
    for a, b in zip(pts, pts[1:] + pts[:1]):
        dec.append(((a[0], a[1], z), (b[0], b[1], z)))


def merlons(mb, dec, x0, x1, h, zf, depth=0.010, reg="brick"):
    n = max(1, int(round((x1 - x0) / 0.030)))
    for k in range(n):
        cx = x0 + (x1 - x0) * (k + 0.5) / n
        poly = [(cx + a, h + b) for a, b in MERLON]
        extrude(mb, poly, zf - depth, zf, reg)
        outline_decor(dec, poly, zf + 0.0003)


def tower(mb, dec, x0, x1, H, zb, zf, slit=True, rng=None):
    box(mb, x0, x1, PLINTH, H, zb, zf, "brick", skip=("bottom",))
    if rng is not None:
        sx = (x0 + x1) / 2
        brick_relief(mb, rng, x0, x1, PLINTH, H, zf,
                     blocked=lambda ha, hb: [(sx - 0.007, sx + 0.007)] if any(h0 - 0.002 < hb and ha < h0 + 0.03
                                                                              for h0 in (0.115, 0.190)) else [])
    box(mb, x0 - 0.004, x1 + 0.004, 0.0, PLINTH, zb - 0.004, zf + 0.006, "stone", skip=("bottom",))
    holes = []
    if slit:
        sx = (x0 + x1) / 2
        for h0 in (0.115, 0.190):
            box(mb, sx - 0.0035, sx + 0.0035, h0, h0 + 0.028, zf - 0.004, zf + 0.0002, "brick", skip=("front", "back"))
            holes.append((sx - 0.006, sx + 0.006, h0, h0 + 0.028))
            outline_decor(dec, [(sx - 0.0035, h0), (sx + 0.0035, h0), (sx + 0.0035, h0 + 0.028), (sx - 0.0035, h0 + 0.028)],
                          zf + 0.0003)
    brick_decor(dec, x0, x1, PLINTH, H, zf + 0.0003, holes=holes)
    outline_decor(dec, [(x0, PLINTH), (x1, PLINTH), (x1, H), (x0, H)], zf + 0.0003)
    stone_decor(dec, x0 - 0.004, x1 + 0.004, zf + 0.0063)
    merlons(mb, dec, x0, x1, H, zf)


def stone_decor(dec, x0, x1, z, h=PLINTH):
    dec.append(((x0, h, z), (x1, h, z)))
    x, k = x0 + 0.064, 0
    while x < x1 - 0.03:                                              # big ashlar blocks, one course
        dec.append(((x, 0.0, z), (x, h, z)))
        x += 0.066 + 0.006 * math.sin(k * 1.7); k += 1


def palm(mb, x, z, seed):
    rng = random.Random(seed)
    mb.nr = True                                          # thin trunk and fronds: named texels (wood, leaf)
    top = Vector((x + 0.010, 0.272, z + 0.004))
    pts = [Vector((x, 0.0, z)) + (top - Vector((x, 0.0, z))) * u + Vector((0.006 * math.sin(math.pi * u), 0, 0))
           for u in np.linspace(0, 1, 15)]
    rad = [0.0075 - 0.0025 * u + (0.0012 if k % 2 else 0.0) for k, u in enumerate(np.linspace(0, 1, 15))]
    tube(mb, [tuple(p) for p in pts], rad, "palmTrunk", seg=8, smooth=False)
    for k in range(10):
        a = TAU * k / 10 + rng.uniform(-0.2, 0.2)
        d = Vector((math.cos(a), 0, math.sin(a)))
        L = rng.uniform(0.042, 0.054)
        up = rng.uniform(0.010, 0.020)
        curve = [top + d * (L * u) + Vector((0, up * math.sin(math.pi * u * 0.8) - 0.040 * u ** 2.2, 0))
                 for u in np.linspace(0, 1, 7)]
        widths = [0.004, 0.013, 0.016, 0.015, 0.012, 0.007, 0.0]
        side_n = d.cross(Vector((0, 1, 0)))
        blade(mb, [tuple(c) for c in curve], widths, "palmLeaf", nrm=tuple(Vector((0, 1, 0)) + d * 0.3))
    for k in range(3):                                                # date clusters under the crown
        a = TAU * k / 3 + 0.5
        lumpy(mb, (top.x + 0.008 * math.cos(a), top.y - 0.010, top.z + 0.008 * math.sin(a)), 0.0055, "palmTrunk",
              seg=7, rings=4, sh=1.2, amp=0.25, seed=seed * 10 + k)
    mb.nr = False


def build_city(root):
    """`nineveh` (wall on a stone plinth with stepped merlons, the right tower, houses, the stepped temple, two date
    palms) and its child `gate` (two towers and the block between them, the arch ringed with lapis and gold blocks,
    bronze-banded doors)"""
    mb = MB()
    rng = random.Random(53)
    dec = DECOR.setdefault("city", [])
    zf, zb = WALL_Z, WALL_Z - WALL_T
    for x0, x1 in ((WALL_X[0], GATEHOUSE[0] + 0.01), (GATEHOUSE[1] - 0.01, TOWERS[2][0] + 0.01)):
        box(mb, x0, x1, PLINTH, WALL_H, zb, zf, "brick", skip=("bottom",))
        brick_relief(mb, rng, x0, x1, PLINTH, WALL_H, zf)
        box(mb, x0, x1, 0.0, PLINTH, zb - 0.002, zf + 0.006, "stone", skip=("bottom",))
        brick_decor(dec, x0, x1, PLINTH, WALL_H, zf + 0.0003)
        stone_decor(dec, x0, x1, zf + 0.0063)
        dec.append(((x0, WALL_H, zf + 0.0003), (x1, WALL_H, zf + 0.0003)))
        merlons(mb, dec, x0 + 0.002, x1 - 0.002, WALL_H, zf)
    x0, x1, H, _ = TOWERS[2]
    tower(mb, dec, x0, x1, H, -0.455, -0.385, rng=rng)
    # houses: plastered walls, flat roofs inside a low parapet, a dark door and window, roof beams
    for i, (hx0, hx1, hz0, hz1, hh) in enumerate(HOUSES):
        box(mb, hx0, hx1, 0.0, hh, hz0, hz1, "house", skip=("bottom", "top"))
        ngon_top(mb, [(hx0 + 0.004, hz1 - 0.004), (hx1 - 0.004, hz1 - 0.004), (hx1 - 0.004, hz0 + 0.004),
                      (hx0 + 0.004, hz0 + 0.004)], hh - 0.003, "roof")
        for (a, b, c, d) in ((hx0, hx1, hz1 - 0.004, hz1), (hx0, hx1, hz0, hz0 + 0.004), (hx0, hx0 + 0.004, hz0, hz1),
                             (hx1 - 0.004, hx1, hz0, hz1)):
            box(mb, a, b, hh - 0.003, hh + 0.005, c, d, "house", skip=("bottom",))
        for k in range(3):                                            # beam ends under the roof
            bx = hx0 + (hx1 - hx0) * (k + 0.5) / 3
            mb.nr = True
            box(mb, bx - 0.003, bx + 0.003, hh - 0.016, hh - 0.010, hz1, hz1 + 0.005, "palmTrunk")
            mb.nr = False
        wx = hx0 + 0.012 if i % 2 else hx1 - 0.012
        box(mb, wx - 0.008, wx + 0.008, hh - 0.045, hh - 0.027, hz1 - 0.003, hz1 + 0.0004, "door", skip=("back",))
    # the stepped temple (three tiers and a shrine)
    tx0, tx1, tz0, tz1 = TEMPLE
    for k, (ins, h0, h1) in enumerate(((0.0, 0.0, 0.212), (0.016, 0.212, 0.246), (0.032, 0.246, 0.272))):
        box(mb, tx0 + ins, tx1 - ins, h0, h1, tz0 + ins, tz1 - ins, "brick", skip=("bottom",))
        brick_decor(dec, tx0 + ins, tx1 - ins, max(h0, 0.15), h1, tz1 - ins + 0.0003, course=0.012)
        outline_decor(dec, [(tx0 + ins, h0), (tx1 - ins, h0), (tx1 - ins, h1), (tx0 + ins, h1)], tz1 - ins + 0.0003)
    sx0, sx1 = (tx0 + tx1) / 2 - 0.030, (tx0 + tx1) / 2 + 0.030
    box(mb, sx0, sx1, 0.272, 0.292, tz0 + 0.044, tz1 - 0.044, "house", skip=("bottom",))
    box(mb, sx0 - 0.005, sx1 + 0.005, 0.292, 0.299, tz0 + 0.040, tz1 - 0.040, "roof", skip=("bottom",))
    box(mb, (sx0 + sx1) / 2 - 0.008, (sx0 + sx1) / 2 + 0.008, 0.272, 0.287, tz1 - 0.044, tz1 - 0.0436, "door",
        skip=("back",))
    for k in range(9):                                                # the ramp stair up the front of the temple
        h = 0.212 + 0.034 * k / 8
        box(mb, (tx0 + tx1) / 2 - 0.011, (tx0 + tx1) / 2 + 0.011, h, h + 0.0045, tz1 - 0.016 - 0.0021 * k, tz1 - 0.012 - 0.0021 * k,
            "brick", skip=("bottom",))
    for x, z, s in PALMS:
        palm(mb, x, z, int(s * 10) + 3)
    city = make_obj("nineveh", mb, root, origin=(0.40, 0.0, WALL_Z), smooth_angle=40)
    # ---- gate
    gm = MB()
    gx0, gx1, gzb, gzf = GATEHOUSE
    t0, t1 = TOWERS[0], TOWERS[1]
    cx, ch = ARCH_C
    # front face with the arch notch (brick, above the plinth); the plinth is cut by the arch too
    face = [(gx0, PLINTH), (GATE_X - GATE_W / 2, PLINTH)] + [(cx + ARCH_R * math.cos(math.pi * (14 - k) / 14),
                                                          ch + ARCH_R * math.sin(math.pi * (14 - k) / 14)) for k in range(15)]
    face += [(GATE_X + GATE_W / 2, PLINTH), (gx1, PLINTH), (gx1, GH_TOWER), (t1[0], GH_TOWER), (t1[0], GH_MID),
             (t0[1], GH_MID), (t0[1], GH_TOWER), (gx0, GH_TOWER)]
    # the face polygon walks round the arch, so it is one simple polygon: front relief, z gzf - 0.08 .. gzf
    tris = tessellate_polygon([[Vector((a, b, 0)) for a, b in face]])
    fv = [gm.v(a, b, gzf) for a, b in face]
    for t in tris:
        gm.fo([fv[i] for i in t], "brick", (0, 0, 1))
    n = len(face)
    for i in range(n):                                                # side walls / arch reveal back to gzb
        a, b = face[i], face[(i + 1) % n]
        if a[1] <= PLINTH + 1e-4 and b[1] <= PLINTH + 1e-4:
            continue
        mx, mh = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        inside_arch = GATE_X - GATE_W / 2 - 1e-6 <= mx <= GATE_X + GATE_W / 2 + 1e-6 and mh < GH_MID - 0.01
        o = (cx - mx, ch - mh, 0) if inside_arch else (mx - (gx0 + gx1) / 2, mh - 0.12, 0)
        gm.fo([gm.v(a[0], a[1], gzf), gm.v(b[0], b[1], gzf), gm.v(b[0], b[1], gzb), gm.v(a[0], a[1], gzb)], "brick", o)
    for (a0, a1, hh) in ((gx0, t0[1], GH_TOWER), (t0[1], t1[0], GH_MID), (t1[0], gx1, GH_TOWER)):    # tops
        ngon_top(gm, [(a0, gzf), (a1, gzf), (a1, gzb), (a0, gzb)], hh, "brick")
    for (a0, a1) in ((gx0 - 0.004, GATE_X - GATE_W / 2), (GATE_X + GATE_W / 2, gx1 + 0.004)):        # plinth
        box(gm, a0, a1, 0.0, PLINTH, gzb - 0.004, gzf + 0.006, "stone", skip=("bottom",))
        stone_decor(dec, a0, a1, gzf + 0.0063)
    # passage floor (paving) and the doors set back in the arch
    ngon_top(gm, [(GATE_X - GATE_W / 2, gzf), (GATE_X + GATE_W / 2, gzf), (GATE_X + GATE_W / 2, gzb),
                  (GATE_X - GATE_W / 2, gzb)], 0.0055, "stone")
    dz = gzf - 0.048
    door = [(GATE_X - GATE_W / 2, 0.0055), (GATE_X + GATE_W / 2, 0.0055)] + \
           [(cx + ARCH_R * math.cos(math.pi * k / 14), ch + ARCH_R * math.sin(math.pi * k / 14)) for k in range(15)]
    extrude(gm, door, dz - 0.006, dz, "door")
    dec.append(((GATE_X, 0.0055, dz + 0.0003), (GATE_X, GATE_H, dz + 0.0003)))                  # the leaves' meeting line
    for x in np.arange(GATE_X - GATE_W / 2 + 0.0125, GATE_X + GATE_W / 2, 0.0125):              # planks
        top = ch + math.sqrt(max(0.0, ARCH_R ** 2 - (x - cx) ** 2))
        dec.append(((x, 0.0055, dz + 0.0003), (x, top, dz + 0.0003)))
    for hb in (0.030, 0.075, 0.115):                                                            # bronze bands
        for e in (-0.003, 0.003):
            dec.append(((GATE_X - GATE_W / 2, hb + e, dz + 0.0003), (GATE_X + GATE_W / 2, hb + e, dz + 0.0003)))
    gm.nr = True
    for s in (-1, 1):                                                                           # ring handles
        tube(gm, [(GATE_X + s * 0.012 + 0.006 * math.cos(t), 0.075 + 0.006 * math.sin(t), dz + 0.002)
                  for t in np.linspace(0, TAU, 12)], 0.0013, "gold", seg=4, closed=True)
    gm.nr = False
    # the band round the arch: alternating lapis and gold blocks, 4 mm proud
    r0, r1 = ARCH_R + 0.001, ARCH_R + 0.060
    blocks = []
    for side in (-1, 1):                                              # jamb blocks
        xa, xb = (cx - r1, cx - r0) if side < 0 else (cx + r0, cx + r1)
        blocks.append([(xa, ch - 0.052), (xb, ch - 0.052), (xb, ch - 0.002), (xa, ch - 0.002)])
    for k in range(3):
        a0, a1 = math.pi * k / 3 + 0.006, math.pi * (k + 1) / 3 - 0.006
        pts = [(cx + r0 * math.cos(a), ch + r0 * math.sin(a)) for a in np.linspace(a0, a1, 5)]
        pts += [(cx + r1 * math.cos(a), ch + r1 * math.sin(a)) for a in np.linspace(a1, a0, 5)]
        blocks.append(pts)
    order = [0, 4, 3, 2, 1]                                           # left jamb, three voussoirs left->right, right jamb
    for k, bi in enumerate(order):
        reg = "lapis" if k % 2 == 0 else "gold"
        extrude(gm, blocks[bi], gzf - 0.001, gzf + 0.0045, reg)
    for tx0_, tx1_ in ((t0[0], t0[1]), (t1[0], t1[1])):
        brick_decor(dec, tx0_, tx1_, PLINTH, GH_TOWER, gzf + 0.0003,
                    holes=[(cx - r1 - 0.003, cx + r1 + 0.003, 0.0, ch + r1 + 0.003)])
        merlons(gm, dec, tx0_, tx1_, GH_TOWER, gzf)
        sx = (tx0_ + tx1_) / 2 + (-0.004 if tx0_ < GATE_X else 0.004)
        for h0 in (0.205,):
            box(gm, sx - 0.0035, sx + 0.0035, h0, h0 + 0.028, gzf - 0.004, gzf + 0.0002, "brick", skip=("front", "back"))
            outline_decor(dec, [(sx - 0.0035, h0), (sx + 0.0035, h0), (sx + 0.0035, h0 + 0.028), (sx - 0.0035, h0 + 0.028)],
                          gzf + 0.0003)
    brick_decor(dec, t0[1], t1[0], PLINTH, GH_MID, gzf + 0.0003, holes=[(cx - r1 - 0.003, cx + r1 + 0.003, 0.0, ch + r1 + 0.003)])

    def arch_block(ha, hb):
        out = [(cx - r1 - 0.002, cx + r1 + 0.002)] if ha < ch else []
        if not out:
            hh = ha - ch
            if hh < r1 + 0.002:
                w = math.sqrt(max(0.0, (r1 + 0.002) ** 2 - hh * hh))
                out = [(cx - w, cx + w)]
        for tx0_, tx1_ in ((t0[0], t0[1]), (t1[0], t1[1])):          # tower slits
            sx = (tx0_ + tx1_) / 2 + (-0.004 if tx0_ < GATE_X else 0.004)
            if hb > 0.203 and ha < 0.235:
                out.append((sx - 0.007, sx + 0.007))
        return out
    grng = random.Random(54)
    brick_relief(gm, grng, gx0, t0[1], PLINTH, GH_TOWER, gzf, blocked=arch_block)
    brick_relief(gm, grng, t0[1], t1[0], PLINTH, GH_MID, gzf, blocked=arch_block)
    brick_relief(gm, grng, t1[0], gx1, PLINTH, GH_TOWER, gzf, blocked=arch_block)
    merlons(gm, dec, t0[1] + 0.002, t1[0] - 0.002, GH_MID, gzf)
    outline_decor(dec, [(gx0, PLINTH), (gx1, PLINTH), (gx1, GH_TOWER), (t1[0], GH_TOWER), (t1[0], GH_MID), (t0[1], GH_MID),
                        (t0[1], GH_TOWER), (gx0, GH_TOWER)], gzf + 0.0003)
    for x in (t0[1], t1[0]):
        dec.append(((x, PLINTH, gzf + 0.0003), (x, GH_MID, gzf + 0.0003)))
    gate = make_obj("gate", gm, city, origin=(GATE_X, 0.0, WALL_Z), smooth_angle=40)
    return city, gate


# ============================================================================================ hidden props
def build_shelter(root):
    """`shelter` (S10): a lean-to. Two poles and a cross-stick lashed at the top (named texel); a patched cloth hangs
    from the cross-stick and is pegged to the ground behind, so it shades the slope of the hill"""
    mb = MB()
    (ax, az), (bx, bz) = SHELTER_STICKS
    TOPH = 0.262
    mb.nr = True
    tops = []
    for k, (x, z) in enumerate(SHELTER_STICKS):
        h0 = land_h(x, z)
        t = (x + (0.004 if k else -0.004), TOPH + 0.004 * k, z - 0.006)
        tube(mb, [(x, h0 - 0.004, z), ((x + t[0]) / 2, (h0 + t[1]) / 2, (z + t[2]) / 2), (t[0], t[1] + 0.012, t[2])],
             [0.0044, 0.0038, 0.0032], "wood", seg=7)
        tops.append(Vector(t))
    tube(mb, [tuple(tops[0] + Vector((-0.010, 0.002, 0))), tuple((tops[0] + tops[1]) / 2 + Vector((0, 0.003, 0))),
              tuple(tops[1] + Vector((0.010, 0.002, 0)))], 0.0034, "wood", seg=7)
    for t in tops:                                                    # lashings
        for k in range(3):
            tube(mb, [(t.x + 0.0058 * math.cos(a), t.y - 0.003 + 0.0022 * k, t.z + 0.0058 * math.sin(a))
                      for a in np.linspace(0, TAU, 9)], 0.0011, "wood", seg=4, closed=True)
    pegs = [Vector((ax - 0.006, 0.0, az - 0.215)), Vector((bx + 0.004, 0.0, bz - 0.212))]
    for pg in pegs:
        pg.y = land_h(pg.x, pg.z)
        tube(mb, [tuple(pg + Vector((0, -0.004, 0))), tuple(pg + Vector((0.0, 0.016, 0.004)))], 0.0026, "wood", seg=5)
    mb.nr = False
    # cloth: from the cross-stick (front, high) down to the pegs (back, low), sagging, a ragged front valance
    NU, NV = 12, 10
    front = [tops[0] + (tops[1] - tops[0]) * (i / NU) + Vector((0, 0.002, 0.004)) for i in range(NU + 1)]
    back = [pegs[0] + (pegs[1] - pegs[0]) * (i / NU) + Vector((0, 0.014, 0)) for i in range(NU + 1)]
    grid = []
    for i in range(NU + 1):
        row = []
        for j in range(NV + 1):
            v = j / NV
            p = front[i] * (1 - v) + back[i] * v
            p = p + Vector((0, -0.020 * math.sin(math.pi * v) * (0.6 + 0.4 * math.sin(math.pi * i / NU)), 0))
            row.append(p)
        grid.append(row)
    vid = [[mb.v(*p) for p in row] for row in grid]
    vbk = [[mb.v(*(p + Vector((0, -0.0012, 0)))) for p in row] for row in grid]
    patches = [(0.10, 0.45, 0.14, 0.56), (0.55, 0.92, 0.44, 0.88)]
    for i in range(NU):
        for j in range(NV):
            u, v = (i + 0.5) / NU, (j + 0.5) / NV
            reg = "patch" if any(a <= u <= b and c <= v <= d for a, b, c, d in patches) else "cloth"
            mb.fo([vid[i][j], vid[i + 1][j], vid[i + 1][j + 1], vid[i][j + 1]], reg, (0, 1, 0.6), True)
            mb.fo([vbk[i][j], vbk[i + 1][j], vbk[i + 1][j + 1], vbk[i][j + 1]], reg, (0, -1, -0.6), True)
    for i in range(NU):                                               # ragged valance hanging from the cross-stick
        p0, p1 = grid[i][0], grid[i + 1][0]
        m = (p0 + p1) * 0.5 + Vector((0, -0.016 - 0.006 * (i % 2), 0.003))
        for sgn in (1, -1):
            mb.fo([mb.v(*p0), mb.v(*p1), mb.v(*m)], "cloth", (0, 0, sgn))
    dec = DECOR.setdefault("shelter", [])

    def at(u, v):
        i = min(int(u * NU), NU - 1); j = min(int(v * NV), NV - 1)
        fu, fv = u * NU - i, v * NV - j
        p = (grid[i][j] * (1 - fu) * (1 - fv) + grid[i + 1][j] * fu * (1 - fv) + grid[i][j + 1] * (1 - fu) * fv
             + grid[i + 1][j + 1] * fu * fv)
        return tuple(p + Vector((0, 0.0007, 0.0004)))
    for a, b, c, d in patches:                                        # running stitches round the patches
        ring = [(a, c), (b, c), (b, d), (a, d)]
        for (u0, v0), (u1, v1) in zip(ring, ring[1:] + ring[:1]):
            for t in (0.2, 0.6):
                dec.append((at(u0 + (u1 - u0) * t, v0 + (v1 - v0) * t),
                            at(u0 + (u1 - u0) * (t + 0.14), v0 + (v1 - v0) * (t + 0.14))))
    return make_obj("shelter", mb, root, origin=(SHELTER[0], 0.0, SHELTER[1]), smooth_angle=60)


def plant_root():
    return (PLANT[0], land_h(*PLANT) - 0.002, PLANT[1])


VINE = [(0.0, 0.0), (0.004, 0.08), (-0.004, 0.17), (-0.010, 0.26), (0.000, 0.34), (0.025, 0.405), (0.065, 0.430),
        (0.110, 0.427), (0.145, 0.408), (0.162, 0.385)]                 # (dx, h) from the root, in the x-h plane


VINE_LIFT = {"big": -0.066, "dry": -0.007}      # plantBig arches low (crown top <= 0.44 with its leaves up);
                                                # plantDry stays high: over the seat it must clear a standing Jonah


def vine_pts(droop=0.0, lift=0.0):
    rx, rh, rz = plant_root()
    out = []
    for k, (dx, h) in enumerate(VINE):
        u = k / (len(VINE) - 1)
        out.append((rx + dx, rh + (h + lift) * (1.0 if k else 1.0) - droop * max(0.0, u - 0.55) ** 1.5,
                    rz + 0.010 * math.sin(math.pi * u)))
    out[0] = (out[0][0], rh, out[0][2])
    return out


def build_plant_small(root):
    mb = MB()
    rx, rh, rz = plant_root()
    mb.nr = True
    tube(mb, [(rx, rh, rz), (rx + 0.002, rh + 0.030, rz), (rx - 0.001, rh + 0.052, rz + 0.002)], [0.0032, 0.0026, 0.0020],
         "leaf", seg=6)
    mb.nr = False
    top = (rx - 0.001, rh + 0.052, rz + 0.002)
    leaf_blade(mb, top, (rx - 0.044, rh + 0.070, rz + 0.012), 0.040, "leaf", nrm=(-0.1, 0.4, 1), fold=0.05)
    leaf_blade(mb, top, (rx + 0.034, rh + 0.074, rz - 0.026), 0.038, "leaf", nrm=(0.1, 0.4, 1), fold=0.05)
    leaf_blade(mb, top, (rx + 0.004, rh + 0.084, rz + 0.004), 0.014, "leaf", nrm=(0, 0.3, 1), fold=0.08)
    return make_obj("plantSmall", mb, root, origin=(rx, 0.0, rz), smooth_angle=50)


CROWN_TOP = 0.437
LEAVES_BIG = [(0.48, 160, 0.060), (0.46, 35, 0.068), (0.58, 120, 0.072), (0.66, -60, 0.064), (0.74, 75, 0.074),
              (0.84, -115, 0.066), (0.92, 30, 0.070), (1.0, -40, 0.060)]                # (u on the vine, fan angle, size)


def vine_at(pts, u):
    f = u * (len(pts) - 1); i = min(int(f), len(pts) - 2); t = f - i
    a, b = Vector(pts[i]), Vector(pts[i + 1])
    return a + (b - a) * t, (b - a).normalized()


def build_plant(root, dry):
    """`plantBig` (a broad-leafed gourd vine arching over Jonah's seat, two gourds) or `plantDry` (the same vine,
    brown: leaves hanging limp on the left, a bare arch over the seat, shrivelled gourds)"""
    mb = MB()
    pts = vine_pts(0.010 if dry else 0.0, VINE_LIFT["dry" if dry else "big"])
    leaf_reg, gourd_reg = ("dry", "dryGourd") if dry else ("leaf", "gourd")
    rad = [0.0066, 0.0062, 0.0058, 0.0054, 0.0050, 0.0046, 0.0042, 0.0038, 0.0034, 0.0030]
    mb.nr = True                                          # the stem below the crown is not printed (named texel)
    tube(mb, pts[:5], rad[:5], leaf_reg, seg=8, caps=False)
    mb.nr = False
    tube(mb, pts[4:], rad[4:], leaf_reg, seg=8)
    mb.nr = True
    for k, u in enumerate((0.45,) if dry else (0.45, 0.62, 0.80)):    # curly tendrils
        c, t = vine_at(pts, u)
        tube(mb, [tuple(c + Vector((0.010 * math.cos(a) * (1 - a / 12), -0.012 * a / 12 - 0.002, 0.010 * math.sin(a) * (1 - a / 12) + 0.003)))
                  for a in np.linspace(0, 10, 12)], 0.0011, leaf_reg, seg=4)
    mb.nr = False
    rng = random.Random(77 if dry else 66)
    for k, (u, ang, size) in enumerate(LEAVES_BIG):
        c, t = vine_at(pts, u)
        if dry:
            if 0.47 < u < 0.90:                                       # over the seat the dry vine is bare
                continue
            d = Vector((0.25 * math.cos(math.radians(ang)), -1.0, 0.25)).normalized()      # hanging limp
            leaf_blade(mb, tuple(c + Vector((0, -0.002, 0.006))), tuple(c + d * size * 1.05), size * 0.92, leaf_reg,
                       nrm=(0.0, 0.25, 1), fold=0.06, droop=0.04)
        else:
            a = math.radians(ang + rng.uniform(-8, 8))
            d = Vector((math.cos(a), math.sin(a), 0.22)).normalized()                      # fanned out, facing the viewer
            if d.y > 0 and c.y + d.y * size * 1.08 > CROWN_TOP:                           # keep the crown top <= 0.44
                size = max(0.04, (CROWN_TOP - c.y) / (d.y * 1.08))
            leaf_blade(mb, tuple(c + Vector((0, 0.0, 0.007))), tuple(c + d * size), size * 0.92, leaf_reg,
                       nrm=(0.0, 0.45, 1), fold=0.08, droop=-0.04)
    if not dry:                                                       # leaves down the stem (3D only: named texel)
        mb.nr = True
        for k, (u, ang, size) in enumerate(((0.12, 165, 0.040), (0.22, 200, 0.044), (0.31, 150, 0.046), (0.38, 215, 0.042))):
            c, t = vine_at(pts, u)
            a = math.radians(ang)
            d = Vector((math.cos(a), math.sin(a) + 0.3, -0.35)).normalized()
            leaf_blade(mb, tuple(c + Vector((0, 0.0, -0.004))), tuple(c + d * size), size * 0.9, leaf_reg,
                       nrm=(0.0, 0.5, 1), fold=0.08, droop=-0.03)
        mb.nr = False
    if dry:                                                           # three limp leaves dangling from the left side
        for k, (u, side) in enumerate(((0.36, 1), (0.44, -1), (0.28, -1))):
            c, t = vine_at(pts, u)
            leaf_blade(mb, tuple(c + Vector((0.004 * side, -0.004, 0.010))), tuple(c + Vector((0.036 * side, -0.066, 0.024))),
                       0.068, leaf_reg, nrm=(0.0, 0.2, 1), fold=0.05, droop=0.05)
    for k, u in enumerate((0.95,) if dry else (0.62, 0.92)):          # gourds on short stalks (dry: off Jonah's head)
        c, t = vine_at(pts, u)
        g = c + Vector((0.004 * (1 if k else -1), -0.050 if not dry else -0.044, 0.010))
        mb.nr = True
        tube(mb, [tuple(c), tuple(g + Vector((0, 0.022, 0)))], 0.0018, leaf_reg, seg=4)
        mb.nr = False
        if dry:
            lathe(mb, [(0.0, -0.030), (0.024, -0.025), (0.036, -0.007), (0.034, 0.008), (0.021, 0.019), (0.012, 0.028),
                       (0.0, 0.031)], gourd_reg, C=tuple(g + Vector((0, 0.0, 0))), seg=18, sx=1.0, sv=0.8,
                  rfun=lambda th, i, kk: 1.0 + 0.04 * math.sin(5 * th))  # shrivelled: squashed, five soft wrinkles
        else:
            lathe(mb, [(0.0, -0.028), (0.019, -0.024), (0.0275, -0.010), (0.0265, 0.005), (0.0155, 0.015), (0.011, 0.024),
                       (0.0, 0.029)], gourd_reg, C=tuple(g), seg=18)
    name = "plantDry" if dry else "plantBig"
    rx, rh, rz = plant_root()
    return make_obj(name, mb, root, origin=(rx, 0.0, rz), smooth_angle=50)


def build_worm(root):
    """`worm` (S11): a little green worm with a happy face, curled on the stem at h ~ 0.14 (named texels)"""
    mb = MB()
    mb.nr = True
    pts = vine_pts(0.0, VINE_LIFT["big"])
    c, t = vine_at(pts, 0.36)
    seg = []
    for k in range(7):
        a = -1.2 + 0.42 * k
        seg.append(c + Vector((0.0098 * math.cos(a), -0.012 + 0.0042 * k, 0.0098 * math.sin(a) + 0.003)))
    for k, p in enumerate(seg):
        sphere(mb, tuple(p), 0.0052 if k < 6 else 0.0062, "leaf", seg=10, rings=6)
    head = seg[-1]
    for s in (-1, 1):
        sphere(mb, tuple(head + Vector((s * 0.0025, 0.0018, 0.0052))), 0.0013, "bellyFloor", seg=6, rings=4)
        tube(mb, [tuple(head + Vector((s * 0.002, 0.005, 0.001))), tuple(head + Vector((s * 0.004, 0.0095, 0.002)))],
             0.0006, "bellyFloor", seg=4)
    tube(mb, [tuple(head + Vector((0.0024 * math.cos(a), -0.0012 + 0.0016 * math.sin(a), 0.0058)))
              for a in np.linspace(math.pi + 0.5, TAU - 0.5, 6)], 0.0005, "bellyFloor", seg=4, caps=False)
    mb.nr = False
    rx, rh, rz = plant_root()
    return make_obj("worm", mb, root, origin=(c.x, c.y, c.z), smooth_angle=60)


RIB_TOP = math.radians(70)


def rib_proud(e, reg):
    if reg != "ribs":
        return 0.0
    return 0.010 * max(0.0, min(1.0, (RIB_TOP + math.radians(4) - e) / math.radians(8)))


def build_belly(root):
    """`belly` (S06): inside the fish. A ribbed dome of pink-grey arcs on a dark-teal floor, open toward the viewer
    over a 120 deg arc (an arched mouth up to h ~0.21), big enough for a kneeling man"""
    mb = MB()
    cx, cz = BELLY_C
    R, H, T = BELLY_R, BELLY_H, 0.012
    NP, NE = 40, 12

    def e_open(phi):                                                  # opening edge elevation for |phi| < 60 deg
        q = abs(phi) / math.radians(60)
        return math.radians(56) * max(0.0, 1 - q ** 2.2) ** 0.55 if q < 1 else -1.0

    def P(phi, e, r):                                                 # superellipse dome (p = 3): a roomy top
        c, s_ = max(0.0, math.cos(e)) ** (2 / 3), max(0.0, math.sin(e)) ** (2 / 3)
        return (cx + r * c * math.sin(phi), H * (r / R) * s_, cz + r * c * math.cos(phi))
    ribs = [math.radians(a) for a in (-127, -83, 83, 127, 180)]
    rib_w = math.radians(30)

    def region(phi):
        d = min(abs((phi - r + math.pi) % TAU - math.pi) for r in ribs)
        return "ribs" if d < rib_w / 2 else "bellyWall"
    phis = [-math.pi + TAU * i / NP for i in range(NP + 1)]
    for i in range(NP):
        p0, p1 = phis[i], phis[i + 1]
        pm = (p0 + p1) / 2
        lo0, lo1 = max(0.0, e_open(p0)), max(0.0, e_open(p1))
        reg0 = region(pm)
        es0 = [lo0 + (math.pi / 2 - lo0) * j / NE for j in range(NE + 1)]
        es1 = [lo1 + (math.pi / 2 - lo1) * j / NE for j in range(NE + 1)]
        inner = [[mb.v(*P(p0, e, R - rib_proud(e, reg0))) for e in es0], [mb.v(*P(p1, e, R - rib_proud(e, reg0))) for e in es1]]
        outer = [[mb.v(*P(p0, e, R + T + 0.6 * rib_proud(e, reg0))) for e in es0],
                 [mb.v(*P(p1, e, R + T + 0.6 * rib_proud(e, reg0))) for e in es1]]
        reg = reg0
        for j in range(NE):
            rj = reg0 if (es0[j] + es0[j + 1]) / 2 < RIB_TOP else "bellyWall"
            mb.fo([inner[0][j], inner[1][j], inner[1][j + 1], inner[0][j + 1]], rj,
                  (-math.sin(pm), -0.4, -math.cos(pm)), True)
            mb.fo([outer[0][j], outer[1][j], outer[1][j + 1], outer[0][j + 1]], "bellyWall",
                  (math.sin(pm), 0.4, math.cos(pm)), True)
        if lo0 > 0 or lo1 > 0 or abs(pm) < math.radians(60):         # the cut edge of the mouth
            mb.fo([inner[0][0], inner[1][0], outer[1][0], outer[0][0]], reg, (math.sin(pm), -1, math.cos(pm)), True)
        else:
            mb.fo([inner[0][0], inner[1][0], outer[1][0], outer[0][0]], "bellyWall", (0, -1, 0), True)
    # rib edges: side faces where a rib stands proud of the wall
    for r in ribs:
        for s in (-1, 1):
            ph = r + s * rib_w / 2
            ph = (ph + math.pi) % TAU - math.pi
            lo = max(0.0, e_open(ph))
            es = [lo + (math.pi / 2 - lo) * j / NE for j in range(NE + 1)]
            a = [mb.v(*P(ph, e, R - rib_proud(e, "ribs"))) for e in es]; b = [mb.v(*P(ph, e, R)) for e in es]
            ao = [mb.v(*P(ph, e, R + T + 0.6 * rib_proud(e, "ribs"))) for e in es]; bo = [mb.v(*P(ph, e, R + T)) for e in es]
            for j in range(NE):
                if (es[j] + es[j + 1]) / 2 >= RIB_TOP + math.radians(4):
                    continue
                mb.fo([a[j], a[j + 1], b[j + 1], b[j]], "ribs", (s * math.cos(ph), 0, -s * math.sin(ph)), True)
                mb.fo([ao[j], ao[j + 1], bo[j + 1], bo[j]], "bellyWall", (s * math.cos(ph), 0, -s * math.sin(ph)), True)
    # floor disc (dark teal) with a lip
    n = 40
    ctr = mb.v(cx, 0.0115, cz)
    ring = [mb.v(cx + (R + 0.004) * math.sin(TAU * k / n), 0.0115, cz + (R + 0.004) * math.cos(TAU * k / n)) for k in range(n)]
    low = [mb.v(cx + (R + 0.010) * math.sin(TAU * k / n), 0.002, cz + (R + 0.010) * math.cos(TAU * k / n)) for k in range(n)]
    for k in range(n):
        mb.fo([ctr, ring[k], ring[(k + 1) % n]], "bellyFloor", UP)
        mb.fo([ring[k], low[k], low[(k + 1) % n], ring[(k + 1) % n]], "bellyFloor",
              (math.sin(TAU * (k + 0.5) / n), 0.5, math.cos(TAU * (k + 0.5) / n)))
    dec = DECOR.setdefault("belly", [])
    for k in range(5):                                                # puddle ripples on the floor (printed)
        rr = 0.03 + 0.016 * k
        a0 = 0.6 * k
        pts = [(cx + rr * math.sin(a), 0.0118, cz + rr * math.cos(a) * 0.7 - 0.01) for a in np.linspace(a0 - 0.9, a0 + 0.9, 8)]
        for p, q in zip(pts[:-1], pts[1:]):
            dec.append((p, q))
    return make_obj("belly", mb, root, origin=(cx, 0.0, cz), smooth_angle=50)


# ============================================================================================ drawings / UV
def _chars_proposal():
    """CONTRACT §2 start slots (sizes from the contract; widths guessed) until regions_characters.json exists"""
    return {"jonah": {"sheetX": -0.32, "sheetY": 0.015, "height": 0.36, "box": [-0.43, 0.015, -0.21, 0.375]},
            "captain": {"sheetX": 0.32, "sheetY": 0.015, "height": 0.38, "box": [0.21, 0.015, 0.43, 0.395]},
            "fish": {"sheetX": 0.0, "sheetY": 0.40, "height": 0.20, "box": [-0.25, 0.40, 0.25, 0.60]}}


def _chars():
    """kit _chars, tolerant of a cast file still being written (an entry without `height`: the fish has `size`)"""
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    rc = json.load(open(p))
    got = {}
    for c, v in rc["characters"].items():
        if c not in rc.get("sheet", {}) or "bboxSheet" not in v:
            continue
        h = v.get("height") or (v.get("size") or {}).get("height") or prop.get(c, {}).get("height")
        got[c] = {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"], "height": h,
                  "box": v["bboxSheet"]}
    for c, v in prop.items():
        got.setdefault(c, v)
    return got, all(c in rc.get("sheet", {}) for c in prop)


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
# kind, scale, centre-x and bottom of the bbox on the sheet (sheet coords: x -0.5..0.5, y 0 = art rect bottom)
# S09 (fix 2026-11-15, docs/jonah/FIXLOG-20261115.md): the people of Nineveh, kneeling in sackcloth in front of the
# gate (Jonah 3:5-8: "from the greatest to the least", the king too). Simple figures in the set's style: a sackcloth
# robe and hood, a face, hands together, eyes shut. All named texels (no printed shape: the sheet is unchanged): robe
# = the cargo sack's colour (sackcloth), face = the shelter's patch, eyes = the belly floor, the king's crown = gold.
# Hidden at start; story.py pops them in one by one with prop(..., grow=...). Each node's origin is at its knees on
# the ground, so a grow pops it up from the ground.
FOLK = [  # name, x, z, scale, king
    ("folk1", 0.250, -0.330, 1.00, False), ("folk2", 0.340, -0.330, 1.05, True), ("folk3", 0.430, -0.330, 1.00, False),
    ("folk4", 0.520, -0.330, 0.97, False), ("folk5", 0.205, -0.262, 0.98, False), ("folk6", 0.272, -0.262, 0.68, False),
    ("folk7", 0.392, -0.262, 0.70, False), ("folk8", 0.475, -0.262, 1.00, False), ("folk9", 0.555, -0.262, 0.96, False)]


def build_folk(root, name, x, z, k, king):
    mb = MB()
    mb.nr = True
    h0 = land_h(x, z)
    C = Vector((x, h0, z))

    def P(dx, dy, dz):
        return tuple(C + Vector((dx * k, dy * k, dz * k)))
    # kneeling robe: wide at the knees, narrowing to the shoulders, leaning a little forward (bowing)
    lathe(mb, [(0.0, 0.0), (0.036 * k, 0.002 * k), (0.038 * k, 0.030 * k), (0.030 * k, 0.080 * k),
               (0.024 * k, 0.118 * k), (0.012 * k, 0.132 * k), (0.0, 0.136 * k)], "sack", C=tuple(C), seg=12,
          sv=0.85)
    sphere(mb, P(0.0, 0.150, 0.010), 0.021 * k, "patch", seg=12, rings=7)                       # face, bowed forward
    sphere(mb, P(0.0, 0.156, 0.000), 0.0235 * k, "sack", seg=12, rings=7, sz=0.92)              # hood over the back
    for s in (-1, 1):                                                                         # shut eyes
        tube(mb, [P(s * 0.0105, 0.153, 0.0285), P(s * 0.0065, 0.1515, 0.0300), P(s * 0.0025, 0.153, 0.0290)],
             0.0012 * k, "bellyFloor", seg=4)
        tube(mb, [P(s * 0.020, 0.118, 0.000), P(s * 0.026, 0.104, 0.012), P(s * 0.024, 0.098, 0.026),
                  P(s * 0.014, 0.106, 0.038), P(s * 0.008, 0.110, 0.041)],
             [0.0080 * k, 0.0078 * k, 0.0074 * k, 0.0070 * k, 0.0068 * k], "sack", seg=10)     # sleeves: hands together
        sphere(mb, P(s * 0.0045, 0.113, 0.044), 0.0072 * k, "patch", seg=8, rings=5)          # hands
    if king:
        lathe(mb, [(0.0215 * k, 0.170 * k), (0.0215 * k, 0.188 * k), (0.0, 0.188 * k)], "gold",
              C=(x, h0, z), seg=10)
        for i in range(5):
            a = TAU * i / 5 + 0.3
            sphere(mb, (x + 0.0215 * k * math.cos(a), h0 + 0.192 * k, z + 0.0215 * k * math.sin(a)), 0.0038 * k,
                   "gold", seg=6, rings=4)
    mb.nr = False
    return make_obj(name, mb, root, origin=(x, h0, z), smooth_angle=60)


DRAWINGS = {
    "ground":     dict(P_PLAN(), scale=3.20, cx=0.290, y0=0.636, decorOnly=["sea", "seaFar", "sand"],
                       members=["seaWater", "beach", "road", "ground", "hill"]),
    "ship":       dict(P_OBL(0.0, 0.5), scale=1.03, cx=-0.255, y0=0.638, decorOnly=["deck", "hull"],
                       members=["ship"]),
    "city":       dict(P_OBL(0.0, 0.55), scale=1.35, cx=0.290, y0=0.900, decorOnly=["brick", "stone"],
                       members=["nineveh", "gate"]),
    "plantBig":   dict(P_OBL(0.0, 0.35), scale=1.27, cx=-0.377, y0=0.394, members=["plantBig"]),
    "belly":      dict(P_OBL(0.0, 0.45), scale=1.80, cx=0.384, y0=0.414, decorOnly=["bellyFloor"], members=["belly"]),
    "plantDry":   dict(P_OBL(0.0, 0.35), scale=1.46, cx=-0.077, y0=0.012, members=["plantDry"]),
    "plantSmall": dict(P_FRONT(), scale=0.62, cx=-0.084, y0=0.232, members=["plantSmall"]),
    "shelter":    dict(P_OBL(0.0, 0.8), scale=0.95, cx=0.086, y0=0.012, members=["shelter"]),
    "wave":       dict(P_FRONT(), scale=0.70, cx=0.084, y0=0.226, members=[]),
    "sack":       dict(P_OBL(0.0, 0.5), scale=0.75, cx=0.038, y0=0.650, members=[]),
}
TEMPLATES = {"wave": ("seaCrests",), "sack": ("cargo",)}
CONSTS = {"seaFoam": {"foam": ("wave", "foam")},
          "ship": {"wood": ("ship", "wood")},
          "cargo": {"jar": ("city", "roof"), "sackTie": ("ship", "wood")},
          "plank": {"deck": ("ship", "deck"), "stone": ("city", "stone")},
          "beachProps": {"wood": ("ship", "wood"), "foam": ("wave", "foam")},
          "hillProps": {"stone": ("city", "stone"), "dry": ("plantDry", "dry")},
          "shelter": {"wood": ("ship", "wood")},
          "gate": {"gold": ("city", "gold")},
          "nineveh": {"palmTrunk": ("ship", "wood"), "palmLeaf": ("plantBig", "leaf")},
          "boat": {"boatHull": ("ship", "hull"), "boatInside": ("ship", "deck"), "wood": ("ship", "wood")},
          "plantSmall": {"leaf": ("plantSmall", "leaf")},
          "plantBig": {"leaf": ("plantBig", "leaf")},
          "plantDry": {"dry": ("plantDry", "dry")},
          "worm": {"leaf": ("plantSmall", "leaf"), "bellyFloor": ("belly", "bellyFloor")},
          **{f[0]: {"sack": ("sack", "sack"), "patch": ("shelter", "patch"), "bellyFloor": ("belly", "bellyFloor"),
                    "gold": ("city", "gold")} for f in FOLK}}
RS = [1]
ORDER = ["sea", "seaWater", "seaCrests", "seaFoam", "ship", "cargo", "plank", "beach", "boat", "beachProps", "road",
         "ground", "hill", "hillProps", "nineveh", "gate", "shelter", "plantSmall", "plantBig", "plantDry", "worm", "belly"] + \
    [f[0] for f in FOLK]
HIDDEN = ["shelter", "plantSmall", "plantBig", "plantDry", "worm", "belly"] + [f[0] for f in FOLK]


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
                       "written by pipeline/jn_coast.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)
    return const


# ============================================================================================ checks
LOW, OVER, TOP = 0.012, 0.17, 0.40
MARGINS = {}                                  # label -> [nearest low-zone geometry, nearest overhead geometry]            # above the floor y: low zone r 0.05, overhead zone r 0.035, ignored


def sampled_points(objs):
    """{object: array of design points}: rest pose, plus the animated extremes of the moving pieces (the sea's
    crests and foam at 8 frames of seaWave, the ship and cargo at the two roll extremes of shipRock)"""
    out = {}
    dg = bpy.context.evaluated_depsgraph_get()
    sc = bpy.context.scene
    for name, ob in objs.items():
        if ob.type != 'MESH':
            continue
        out[name] = np.array(world_verts(ob))
    for frames, names in (((1, 13, 25, 37, 49, 61, 73, 85), ("seaCrests", "seaFoam")), ((37, 109), ("ship", "cargo"))):
        extra = {n: [] for n in names}
        for f in frames:
            sc.frame_set(f); dg.update()
            for n in names:
                ob = objs[n]
                me = ob.evaluated_get(dg).to_mesh()
                extra[n].append(np.array([D(ob.matrix_world @ v.co) for v in me.vertices]))
                ob.evaluated_get(dg).to_mesh_clear()
        for n in names:
            out[n] = np.concatenate([out[n]] + extra[n])
    sc.frame_set(1); dg.update()
    return out


def check_clearance(objs):
    """CONTRACT §6 rule, per mark and per straight walk, relative to the walker's floor y: nothing above y + 0.012
    within 0.05; overhead parts (y + 0.17 .. y + 0.40) need only 0.035 (a head's radius); above y + 0.40 ignored.
    Walking surfaces (beach, road, ground, hill, water, plank) do not count. Hidden props count only in the scenes
    that show them. Also the fish lane: nothing of the set (but the water) in x -0.60..0.02, z -0.06..0.21."""
    pts = sampled_points(objs)
    hard, soft, info = {}, {}, {}
    MARGINS.clear()

    def test(label, a, b, ya, yb, shown=(), out=hard, ztop=None):
        worst = None
        lo_min, ov_min = 9.0, 9.0
        for name, P in pts.items():
            if name in TERRAIN or (name in HIDDEN and name not in shown):
                continue
            X, Hh, Z = P[:, 0], P[:, 1], P[:, 2]
            ax, az = a; bx, bz = b
            dx, dz = bx - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
            t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
            d = np.hypot(X - ax - t * dx, Z - az - t * dz)
            y = ya + (yb - ya) * t
            rel = Hh - y
            top = TOP if ztop is None else ztop
            lz = (rel > LOW) & (rel < OVER); oz = (rel >= OVER) & (rel < top)
            if lz.any():
                lo_min = min(lo_min, float(d[lz].min()))
            if oz.any():
                ov_min = min(ov_min, float(d[oz].min()))
            sel = (lz & (d < 0.05)) | (oz & (d < 0.035))
            if sel.any():
                m = float(d[sel].min())
                if worst is None or m < worst[0]:
                    worst = (m, name, round(float(Hh[sel][np.argmin(d[sel])]), 4))
                out.setdefault(label, []).append([name, round(m, 4), round(float(Hh[sel].max()), 4)])
        MARGINS[label] = [round(lo_min, 3), round(ov_min, 3)]
        return worst
    # every mark (as a zero-length walk) and every contract walk
    for label, (x, z, y) in MARKS.items():
        shown = ("shelter",) if label == "jonah hill" else ()
        test("mark " + label, (x, z), (x, z), y, y, shown)
    for label, a, b in CONTRACT_PATHS:
        (ax, az, ay), (bx, bz, by) = MARKS[a], MARKS[b]
        shown = ("shelter",) if label == "jonah gate>hill" else ()
        test("walk " + label, (ax, az), (bx, bz), ay, by, shown)
    # the scenes with hidden props: S06 belly, S10 shelter, S11 plants + worm (seated: head top ~0.27), S12 dry plant
    bx, bz = BELLY_C
    test("mark belly (S06, sitting back on the heels: head top 0.249, jn_animate KNEEL_PRAY)", (bx, bz), (bx, bz), 0.0, 0.0, ("belly",), ztop=0.25)
    hx, hz, _ = MARKS["jonah hill"]
    test("mark hill seated (S11 plantSmall/plantBig/worm)", (hx, hz), (hx, hz), 0.0, 0.0,
         ("shelter", "plantSmall", "plantBig", "worm"), ztop=0.27)
    test("mark hill standing (S11-S12 plantDry)", (hx, hz), (hx, hz), 0.0, 0.0, ("shelter", "plantDry"))
    # fix 2026-11-15: S09 townsfolk kneel behind Jonah at the gate; S12 Jonah stands up clear of the dry vine
    gx, gz, _ = MARKS["jonah gate"]
    test("mark jonah gate, S09 townsfolk shown", (gx, gz), (gx, gz), 0.0, 0.0, tuple(f[0] for f in FOLK))
    for f in FOLK:
        info["folk " + f[0]] = round(min(math.hypot(f[1] - a_[0], f[2] - a_[1]) for a_ in
                                         [(gx, gz)] + [(g[1], g[2]) for g in FOLK if g[0] != f[0]]), 3)
    # S12: Jonah stays seated under plantDry (standing there, its limp leaves come within 0.035 of his axis, through
    # his shoulders; no free standing spot nearby: hill rocks / tufts and the shelter poles); story.py hides plantDry
    # (shrink) before he stands up in S12b
    # fish lane
    bad = {}
    for name, P in pts.items():
        if name in ("seaWater",) or name in HIDDEN:
            continue
        m = (P[:, 0] >= LANE[0]) & (P[:, 0] <= LANE[1]) & (P[:, 2] >= LANE[2]) & (P[:, 2] <= LANE[3]) & (P[:, 1] > 0.012)
        if m.any():
            bad[name] = int(m.sum())
    if bad:
        hard["fish lane"] = bad
    # timeline walks that are not contract walks (reported): the engine walks straight between consecutive targets
    for label, a, b, w in TL_MOVES:
        if w == "fish" or max(abs(a[0]), abs(b[0])) > 0.62:
            continue
        key = ((round(a[0], 3), round(a[1], 3)), (round(b[0], 3), round(b[1], 3)))
        known = {((round(MARKS[p][0], 3), round(MARKS[p][1], 3)), (round(MARKS[q][0], 3), round(MARKS[q][1], 3)))
                 for _, p, q in CONTRACT_PATHS}
        if key in known:
            continue
        test("timeline " + label, (a[0], a[1]), (b[0], b[1]), a[2], b[2], (), soft)
    # heights at the marks (for the timeline's y)
    for label, (x, z, y) in MARKS.items():
        if y < 0.05:
            info[label] = round(land_h(x, z), 4)
    return hard, soft, info


# ============================================================================================ build
STATE = {}


def ship_rock(ship):
    """shipRock: 6 s loop at 24 fps (frame 1 == frame 145): +-3 deg roll about the deck's long axis, a little pitch"""
    ship.animation_data_create()
    ship.rotation_mode = 'XYZ'
    loc = ship.location.copy()
    for f in range(1, 146, 4):
        u = TAU * (f - 1) / 144
        ship.rotation_euler = (math.radians(3.0) * math.sin(u), math.radians(0.6) * math.sin(2 * u + 0.8), 0.0)
        ship.location = loc
        ship.keyframe_insert("rotation_euler", frame=f)
        ship.keyframe_insert("location", frame=f)
    ship.animation_data.action.name = "shipRock"
    ship.rotation_euler = (0, 0, 0)
    bpy.context.scene.frame_set(1)


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.render.fps = 24
    root = link(bpy.data.objects.new("coast", None))
    objs = {}
    rig, objs["seaWater"], objs["seaCrests"], objs["seaFoam"], wave_tpl, crests = build_sea(root)
    objs["ship"] = build_ship(root)
    objs["cargo"], cargo, sack_tpl = build_cargo(objs["ship"])
    objs["plank"] = build_plank(root)
    objs["beach"], objs["road"], objs["ground"], objs["hill"] = build_land(root)
    objs["boat"], objs["beachProps"] = build_beach_props(objs["beach"])
    objs["hillProps"], rocks, tufts = build_hill_props(objs["hill"])
    objs["nineveh"], objs["gate"] = build_city(root)
    objs["shelter"] = build_shelter(root)
    objs["plantSmall"] = build_plant_small(root)
    objs["plantBig"] = build_plant(root, False)
    objs["plantDry"] = build_plant(root, True)
    objs["worm"] = build_worm(root)
    objs["belly"] = build_belly(root)
    for f in FOLK:
        objs[f[0]] = build_folk(root, *f)
    ship_rock(objs["ship"])
    bpy.context.view_layer.update()
    tmp = {"tpl_wave": make_obj("tpl_wave", wave_tpl, None, smooth_angle=70),
           "tpl_sack": make_obj("tpl_sack", sack_tpl, None, smooth_angle=55)}
    src = raster_sources(objs, tmp)
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("COAST_TRIS", total, json.dumps(tris))
    print("PLACED", json.dumps({"crests": len(crests), "cargo": [c[:3] for c in cargo], "rocks": len(rocks),
                                "tufts": len(tufts)}))
    lay = check_layout()
    hard, soft, info = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_SOFT", json.dumps(soft))
    print("MARK_GROUND_H", json.dumps(info))
    print("CLEARANCE_MIN", json.dumps(MARGINS))
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
    for o in tmp.values():
        bpy.data.objects.remove(o, do_unlink=True)
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
    write_design(objs, tris, total, hmax, const, hard, soft, info, cargo)
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root, rig=rig)
    print("BUILD_OK", GLB, total, "MISSING" if missing else "")


TITLE = {"hanzi": "约拿与大鱼", "pinyin": "yuē ná yǔ dà yú", "english": "Jonah and the Big Fish", "box": 74, "gap": 28,
         "cy": 108, "label": "DoodLive · 涂上颜色，再用手机扫一扫",
         "note": "box 74 / gap 28 / cy 108: the most distinct of a grid of candidates that keep the pinyin 6 mm from the "
                 "top edge (tools/story/sheet_jonah.py title-search; most similar other title: Daniel, NCC 0.35)"}


def write_design(objs, tris, total, hmax, const, hard, soft, info, cargo):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    d.setdefault("version", 1)
    d.setdefault("artHeightUnits", ART_H)
    d.setdefault("lines", {"outerPx": 4.5, "detailPx": 3.0,
                           "note": "same weights as David & Goliath, Esther and Ruth; faces come from decals"})
    d.setdefault("sheet", {
        "page": [1240, 1754], "dpi": 150, "art": [120, 283, 1000, 1227],
        "markers": [[62, 225], [1178, 225], [1178, 1568], [62, 1568]], "markerSize": 64,
        "title": dict(TITLE),
        "footer": {"rect": [210, 1604, 820, 110], "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上", "约拿书 · Jonah"],
                   "note": "centred on the page (x 620); line 1 at rect y + 40, line 2 at y + 76"},
        "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge; "
                    "title cy keeps the pinyin >= 6 mm from the top"})
    d["sheet"]["title"] = dict(TITLE)
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"height": v["height"], "sheetX": v["sheetX"], "sheetY": v["sheetY"]})
        if c == "fish":
            e["projection"] = "side (nose to -x), second row"
        ch[c] = e
    d["characters"] = ch
    pieces = []
    for name in ORDER:
        if name == "sea":
            continue
        g = drawing_of(name)
        sp = DRAWINGS[g] if g else None
        fu = ({k: (round(sp[k], 5) if isinstance(sp[k], float) else sp[k]) for k in ("A", "B", "D", "scale", "sheetX",
                                                                                   "sheetY")} if sp else None)
        pieces.append({"id": name, "drawing": g, "frontUV": fu, "instanced": name in sum(TEMPLATES.values(), ()),
                       "namedTexels": {r: list(k) for r, k in CONSTS.get(name, {}).items()} or None,
                       "regions": sorted(set(REG_OF[name])), "heightMax": hmax[name], "tris": tris[name]})
    drawings = {g: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dsp.items()} for g, dsp in DRAWINGS.items()}
    rx, rh, rz = plant_root()
    d["set"] = {
        "generatedBy": "pipeline/jn_coast.py", "doc": "docs/jonah/SET.md", "contract": "docs/jonah/CONTRACT.md §6",
        "root": "coast",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {"sea": [round((SEA_X[0] + SEA_X[1]) / 2, 4), 0.0, round((FLOOR[2] + FLOOR[3]) / 2, 4)],
                  "ship": [SHIP_C[0], DECK, SHIP_C[1]], "cargo": [SHIP_C[0], DECK, SHIP_C[1]],
                  "plank": list(PLANK_FOOT), "beach": [0.0, 0.0, 0.0], "boat": [BOAT[0], 0.0, BOAT[1]],
                  "road": [0.0, 0.0, 0.0], "ground": [0.0, 0.0, 0.0], "hill": [HILL_C[0], 0.0, HILL_C[1]],
                  "nineveh": [0.40, 0.0, WALL_Z], "gate": [GATE_X, 0.0, WALL_Z],
                  "shelter": [SHELTER[0], 0.0, SHELTER[1]], "plantSmall": [rx, 0.0, rz], "plantBig": [rx, 0.0, rz],
                  "plantDry": [rx, 0.0, rz], "worm": [round(c, 4) for c in D(objs["worm"].matrix_world.translation)],
                  "belly": [BELLY_C[0], 0.0, BELLY_C[1]]},
        "footprints": {"floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]], "sea": [SEA_X[0], FLOOR[2], SEA_X[1], FLOOR[3]],
                       "fishLane": list(LANE), "ship": {"centre": list(SHIP_C), "x": list(SHIP_X), "halfBeam": SHIP_HB,
                                                         "deck": DECK, "gunwale": GUNWALE, "mast": list(MAST)},
                       "cargo": [[c[0], c[1], c[2], c[3]] for c in cargo],
                       "beach": [BEACH_X[0], BEACH_X[1]], "wall": {"x": list(WALL_X), "frontZ": WALL_Z},
                       "gate": {"centre": [GATE_X, WALL_Z], "opening": GATE_W, "height": GATE_H,
                                "gatehouse": list(GATEHOUSE)},
                       "hill": {"centre": list(HILL_C), "radius": HILL_R}, "belly": {"centre": list(BELLY_C),
                                                                                    "innerRadius": BELLY_R, "height": BELLY_H},
                       "shelterSticks": [list(s) for s in SHELTER_STICKS], "posts": [list(p) for p in POSTS]},
        "heights": {"seaLevel": SEA_LEVEL, "deck": DECK, "gunwale": GUNWALE, "mastTop": MAST_TOP, "wallTop": WALL_H + 0.024,
                    "gateTowers": GH_TOWER + 0.024, "hillTop": HILL_TOP, "groundAtMarks": info},
        "animations": {"seaWave": {"node": "sea", "meshes": ["seaWater", "seaCrests", "seaFoam"], "length": 4.0,
                                   "fps": 24, "loop": True},
                       "shipRock": {"node": "ship", "length": 6.0, "fps": 24, "loop": True, "rollDeg": 3.0,
                                    "pitchDeg": 0.6, "pivot": [SHIP_C[0], DECK, SHIP_C[1]]}},
        "hiddenAtStart": list(HIDDEN),
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227; "
                             "P = world position, or the template position for the wave crests",
                   "edgeOn": "faces with |n . D| < 0.22 (n in drawing space) take one clean texel of their region",
                   "namedTexels": "no-raster bits (rigging, rails, foam, shells, rocks, grass, sticks, stems, worm) take "
                                  "one texel of a named (drawing, region); constUV in model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard, "timelineMoves": soft,
                      "nearest": {"note": "[low zone (y+0.012..0.17), overhead (y+0.17..0.40)] nearest plan distance; "
                                          "needs >= 0.05 / >= 0.035", **MARGINS}},
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
    save_png(line, os.path.join(WORK, "coast_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "coast_drawings_demo.png"))
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
    """preview stand-ins only (not shipped): simple figures in the demo colours at the actors' marks"""
    mats = {k: flat_mat("pvm_" + k, v, 0.6) for k, v in {
        "skin": "#E9B48F", "cream": "#F1E7D0", "coat": "#8A5A3B", "hair": "#4A3526", "wrap": "#4FA58A",
        "tunic": "#EFE3C8", "navy": "#2F4F8A", "sash": "#B5532E", "beard": "#231A16", "back": "#1F7F86",
        "belly": "#BFE9E2", "fin": "#17666C", "eye": "#FFFFFF", "pupil": "#202020"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    for who, (x, z, y, yaw, pose) in layout.items():
        mb = MB()
        if who == "fish":
            sphere(mb, (0.0, 0.08, 0.0), 0.10, "back", seg=20, rings=12, sx=1.0, sh=0.85, sz=0.75)
            sphere(mb, (0.0, 0.055, 0.004), 0.085, "belly", seg=18, rings=10, sx=0.95, sh=0.62, sz=0.72)
            blade(mb, [(0.09, 0.08, 0.0), (0.16, 0.12, 0.0), (0.20, 0.17, 0.0)], [0.03, 0.06, 0.08], "fin", nrm=(0, 0, 1))
            blade(mb, [(0.09, 0.08, 0.0), (0.16, 0.06, 0.0), (0.20, 0.02, 0.0)], [0.03, 0.05, 0.07], "fin", nrm=(0, 0, 1))
            for s in (-1, 1):
                sphere(mb, (-0.055, 0.115, s * 0.058), 0.017, "eye", seg=10, rings=6)
                sphere(mb, (-0.062, 0.117, s * 0.070), 0.008, "pupil", seg=8, rings=5)
        elif pose == "kneel":
            lathe(mb, [(0.0, 0.0), (0.05, 0.0), (0.048, 0.03), (0.040, 0.10), (0.032, 0.16), (0.0, 0.17)], "cream",
                  C=(0, 0, 0), seg=16)
            sphere(mb, (0.0, 0.195, 0.004), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (0.0, 0.180, 0.020), 0.020, "hair", seg=10, rings=7, sh=1.2, sz=0.7)
        else:
            body, top = ("cream", "coat") if who == "jonah" else ("navy", "tunic")
            H = 0.36 if who == "jonah" else 0.38
            lathe(mb, [(0.0, 0.0), (0.050, 0.0), (0.048, 0.02), (0.042, 0.13 * H / 0.36)], body, C=(0, 0, 0), seg=18)
            lathe(mb, [(0.042, 0.13 * H / 0.36), (0.044, 0.20 * H / 0.36), (0.038, 0.27 * H / 0.36), (0.0, 0.28 * H / 0.36)],
                  top, C=(0, 0, 0), seg=18)
            sphere(mb, (0.0, H - 0.04, 0.0), 0.034, "skin", seg=14, rings=9)
            sphere(mb, (0.0, H - 0.058, 0.016), 0.022, "beard" if who == "captain" else "hair", seg=10, rings=7, sh=1.2,
                   sz=0.8)
            if who == "captain":
                lathe(mb, [(0.0, H - 0.05), (0.038, H - 0.045), (0.037, H - 0.012), (0.0, H)], "wrap", C=(0, 0, -0.004),
                      seg=16)
                lathe(mb, [(0.046, 0.13 * H / 0.36), (0.046, 0.15 * H / 0.36)], "sash", C=(0, 0, 0), seg=18)
            else:
                lathe(mb, [(0.0, H - 0.05), (0.036, H - 0.04), (0.035, H - 0.010), (0.0, H - 0.002)], "hair",
                      C=(0, 0, -0.006), seg=16)
        ob = make_obj("pv_" + who, mb, None, origin=(0, 0, 0), smooth_angle=60)
        ob["pv"] = 1
        ob.location = B(x, y, z)
        ob.rotation_euler = (0, 0, math.radians(yaw))


def mode_preview():
    if not STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "coast_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "coast_preview_sheet.png")); sheet.pack()
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

    def light(mode):
        if mode == "day":
            sun.data.energy = 3.1; sun.data.color = (1.0, 0.95, 0.86)
            sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-30))
            fill.data.energy = 6.0; fill.data.color = (1.0, 0.88, 0.72)
            bg.inputs[0].default_value = (0.80, 0.84, 0.90, 1); bg.inputs[1].default_value = 0.75
        else:                                                         # inside the fish: deep teal
            sun.data.energy = 0.9; sun.data.color = (0.55, 0.85, 0.85)
            sun.rotation_euler = (math.radians(55), math.radians(20), math.radians(40))
            fill.data.energy = 3.0; fill.data.color = (0.5, 0.9, 0.85)
            bg.inputs[0].default_value = (0.05, 0.20, 0.22, 1); bg.inputs[1].default_value = 0.5
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 48
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
    light("day")
    show(HIDDEN, False)
    cast({})
    phone = ((-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280))
    shoot("coast_preview_phone_set", *phone)
    cast({"jonah": (-0.26, -0.22, DECK, 20, ""), "captain": (-0.44, -0.22, DECK, 30, ""),
          "fish": (-0.24, 0.02, -0.02, 0, "")})
    shoot("coast_preview_phone", *phone)
    cast({"jonah": (0.28, 0.14, 0.0, -30, ""), "captain": (-0.36, -0.24, DECK, 10, "")})
    shoot("coast_preview_phone_low", (0.02, 0.62, 0.95), (0.02, 0.06, -0.30), 52, (720, 1280))
    cast({})
    shoot("coast_preview_front", (0.0, 0.26, 2.3), (0.0, 0.14, -0.25), 21, (1600, 1000))
    cast({"jonah": (-0.30, -0.26, DECK, 30, ""), "captain": (-0.44, -0.22, DECK, 40, "")})
    shoot("coast_preview_ship", (-0.12, 0.66, 0.44), (-0.33, 0.16, -0.24), 44, (1280, 900))
    cast({"jonah": (0.34, -0.24, 0.0, 0, "")})
    shoot("coast_preview_city", (0.18, 0.40, 0.30), (0.40, 0.12, -0.42), 46, (1280, 900))
    cast({})
    shoot("coast_preview_beach", (0.28, 0.24, 0.26), (0.02, 0.04, -0.22), 50, (1280, 900))
    show(["shelter", "plantBig", "worm"], True)
    cast({"jonah": (0.42, 0.08, 0.0, 0, "kneel")})
    shoot("coast_preview_hill", (0.12, 0.55, 0.80), (0.45, 0.20, 0.0), 44, (1280, 900))
    show(["plantBig", "worm"], False); show(["plantDry"], True)
    cast({"jonah": (0.42, 0.08, 0.0, 0, "")})
    shoot("coast_preview_hill_dry", (0.12, 0.55, 0.80), (0.45, 0.20, 0.0), 44, (1280, 900))
    show(["plantDry", "shelter"], False); show(["plantBig", "worm"], True)
    cast({})
    shoot("close_plant_big", (0.28, 0.30, 0.38), (0.42, 0.30, 0.06), 40, (1000, 900), WORK)
    show(["plantBig", "worm"], False)
    show(["plantDry", "shelter"], False); show(["plantSmall"], True)
    cast({})
    shoot("close_plant_small", (0.38, 0.12, 0.20), (0.34, 0.05, 0.06), 30, (900, 700), WORK)
    show(["plantSmall"], False)
    show(["belly"], True)
    light("deep")
    cast({"jonah": (-0.20, 0.08, 0.0, 0, "kneel")})
    shoot("coast_preview_belly", (-0.14, 0.42, 0.75), (-0.20, 0.10, 0.06), 40, (1280, 900))
    show(["belly"], False)
    light("day")
    cast({})
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "coast_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    shoot("close_sea", (-0.66, 0.20, -0.20), (-0.30, 0.0, -0.46), 50, (1200, 800), WORK)
    shoot("close_deck", (-0.30, 0.30, -0.10), (-0.33, 0.12, -0.24), 50, (1000, 1000), WORK)
    shoot("close_gate", (0.34, 0.12, -0.20), (0.34, 0.10, -0.40), 46, (1000, 900), WORK)
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["coast", "sea", "seaWater", "seaCrests", "seaFoam", "ship", "cargo", "plank", "beach", "boat", "road",
        "ground", "hill", "nineveh", "gate", "shelter", "plantSmall", "plantBig", "plantDry", "worm", "belly"]


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
    ob = bpy.data.objects.get("seaWater")
    if ob is not None:
        pos = []
        for f in (1, 25, 49, 73, 97):
            sc.frame_set(f); dg.update()
            me = ob.evaluated_get(dg).to_mesh()
            pos.append(np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices]))
            ob.evaluated_get(dg).to_mesh_clear()
        res["seaWaveMax"] = round(float(max(np.abs(p - pos[0]).max() for p in pos[1:4])), 4)
        res["seaLoopError"] = float(np.abs(pos[4] - pos[0]).max())
    sh = bpy.data.objects.get("ship")
    if sh is not None and sh.animation_data and not sh.animation_data.action and "shipRock" in bpy.data.actions:
        act = bpy.data.actions["shipRock"]                          # the importer puts a second object's clip on NLA
        for t in list(sh.animation_data.nla_tracks):
            sh.animation_data.nla_tracks.remove(t)
        sh.animation_data.action = act
        try:
            sh.animation_data.action_slot = act.slots[0]
        except (AttributeError, IndexError):
            pass
    if sh is not None:
        rots = []
        for f in (1, 37, 73, 109, 145):
            sc.frame_set(f); dg.update()
            q = sh.matrix_world.to_quaternion()
            rots.append(q)
        res["shipRollDeg"] = round(max(math.degrees(r.rotation_difference(rots[0]).angle) for r in rots), 2)
        res["shipLoopErrorDeg"] = round(math.degrees(rots[4].rotation_difference(rots[0]).angle), 4)
    sc.frame_set(1)
    ok = (not missing and tris <= MAX_TRIS and uv_bad == 0 and any("seaWave" in a for a in acts)
          and any("shipRock" in a for a in acts) and 0.0008 < res.get("seaWaveMax", 0) < 0.006
          and res.get("seaLoopError", 1) < 1e-4 and 2.5 < res.get("shipRollDeg", 0) < 3.6
          and res.get("shipLoopErrorDeg", 1) < 0.01)
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "actions": acts, "parents": parents, **res}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
