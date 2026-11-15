"""Blender (headless): Joseph story pack, the set `twolands` -> assets/joseph/model/twolands.glb

One page, two lands (docs/joseph/DESIGN.md §2, CONTRACT.md §6). Left = Canaan: Jacob's striped goat-hair tent (woven
strips, poles, guy ropes, a rug, clay jars); three woolly sheep by a low stone sheep-fold; a gnarled olive tree; the
dry well `pit` (four courses of rough stones, top h 0.08, a dark floor) with `bucket` and a coil of rope; the
`caravan` (camel, saddle-cloth, bundle, a hooded trader; hidden until S03). Right = Egypt: the `palace` front (a
four-step dais, two fat papyrus-bud columns painted in bands, a lintel with the winged sun-disc, a back wall, two
feather fans, a fire bowl, child `throne`); the `granary` (three beehive mud-brick stores, doors, a ladder),
`grainPiles` (hidden until S07), `sacks` (hidden until S09); the prison `cell` (wooden bars open toward the viewer,
child `cellBench` with a stone bench and a jug; hidden except S04-S06); two date `palms`. Between: a dune strip with
the caravan road (`ground`). Back: the `horizon` relief (Canaan hills, a golden dune, desert and three pyramids).
Floating, hidden: the dream cloud panels `dreamSheaves` (+ `dreamSheaves2`, same drawing), `dreamStars`, `dreamCows`,
`dreamGrain`: flat double-sided reliefs facing +z, tilted 15 degrees toward the camera.
Details, measured clearances and sheet regions: docs/joseph/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right. In
Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h); export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `js_page` = the scanned art rectangle), exactly as Ruth's set: each piece belongs to
one *drawing* on the colouring sheet, a linear view of its pieces (story_kit stage: P_FRONT / P_OBL / P_PLAN):
  u = a / scale + sheetX + 0.5,   v = (b / scale + sheetY) / 1.227,   a = A.P, b = B.P
P is the vertex's position in its drawing's model: the world position, or the template position for instanced
pieces (sheep, the dream panels: every instance wears its one drawing; dreamSheaves2 wears dreamSheaves').
Faces nearly edge-on to their drawing take one clean texel of their own region. Pieces without a drawing (ground,
cell, grainPiles, sacks, palms, bucket, poles, ropes, fans, fire bowl, jars, the trader) take one texel of a named
region (CONSTS -> constUV). Every printed set region is >= 6 mm (docs/joseph/SET.md).

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/js_twolands.py -- build     twolands.glb + .blend + set_id_2x
  blender -b --factory-startup --python pipeline/js_twolands.py -- verify    re-import twolands.glb and check it
  blender -b --factory-startup --python pipeline/js_twolands.py -- all       build, preview, verify
  blender -b --factory-startup --python pipeline/js_twolands.py -- check     build in memory, print the checks only
Work files go to $JS_WORK (default /tmp/joseph_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/joseph/model")
GLB = os.path.join(MODEL, "twolands.glb")
BLEND = os.path.join(MODEL, "twolands.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/joseph/design.json")
TIMELINE = os.path.join(ROOT, "assets/joseph/timeline.json")
WORK = os.environ.get("JS_WORK", "/tmp/joseph_set")
PAGE_MATERIAL = "js_page"
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
MAX_TRIS = 60000
TAU = 2 * math.pi
UP = (0.0, 1.0, 0.0)
FLOOR = (-0.60, 0.60, -0.5875, 0.21)          # x0 x1 zBack zFront
sys.path.insert(0, HERE)
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "stage")


# ============================================================================================ marks and paths
ACTOR_H = {"joseph": 0.36, "jacob": 0.33, "brother": 0.38, "pharaoh": 0.45}     # head top (Joseph with head-cloth)
CHAINS = {      # CONTRACT §6 marks (fallback only: the check uses timeline.json, i.e. story.py as the lead last left it)
    "jacob": [[(-0.46, -0.20), (-0.10, 0.12)]],
    "joseph": [[(-0.32, -0.16), (-0.26, 0.04), (-0.34, 0.08), (-0.80, 0.30)],
               [(0.16, 0.06), (0.10, -0.06), (0.22, -0.20), (0.42, 0.04), (0.34, 0.08), (0.02, 0.12)]],
    "brother": [[(-0.16, -0.12), (-0.20, 0.06)], [(-0.16, -0.12), (0.22, 0.13), (0.16, 0.14)]],
    "pharaoh": [[(0.38, -0.30)]],
}
WELL = (-0.35, 0.09)          # CONTRACT (-0.34, 0.08) moved 0.014 so Jacob's S11 walk clears the wall (SET.md)
WELL_RI, WELL_RO, WELL_H = 0.07, 0.09, 0.08
CELL = (0.10, -0.06)
HIDDEN = ["caravan", "cell", "grainPiles", "sacks", "dreamSheaves", "dreamSheaves2", "dreamStars", "dreamCows",
          "dreamGrain"]
NODE_OF = {"cellBench": "cell"}               # child -> the hidden node that shows / hides it
WALK_SPEED = 0.10                             # units/s, conservative (a walk's time window)


def _same(p, q, eps=2e-3):
    return abs(p[0] - q[0]) < eps and abs(p[1] - q[1]) < eps


def _timeline():
    try:
        return json.load(open(TIMELINE))
    except Exception as e:
        print("TIMELINE_WARN", e)
        return None


def _items():
    """every mark and straight walk to keep clear, with the times it is in use (from timeline.json)"""
    tl = _timeline()
    dur = float(tl["duration"]) if tl else 1e4
    stays, moves, last = {}, [], {}
    if tl:
        for a in tl["acting"]:
            if "to" not in a:
                continue
            w, p, t = a["who"], (float(a["to"][0]), float(a["to"][1])), float(a["t"])
            if w in last and not _same(last[w], p):
                L = math.hypot(p[0] - last[w][0], p[1] - last[w][1])
                moves.append((w, last[w], p, t, t + L / WALK_SPEED + 0.6))
                stays[w][-1][2] = t
            if w not in last or not _same(last[w], p):
                stays.setdefault(w, []).append([p, t, dur])
            last[w] = p
    items = []

    def on(p):
        return abs(p[0]) <= 0.62 and abs(p[1]) <= 0.62
    if tl:                          # the marks and walks the director really plays (story.py via timeline.json)
        seq, done = {}, set()
        for a in tl["acting"]:
            if "to" in a:
                seq.setdefault(a["who"], []).append(((float(a["to"][0]), float(a["to"][1])), float(a["t"]),
                                                     bool(a.get("snap"))))
        for who, lst in seq.items():
            for p, t, snap in lst:
                if on(p) and (who, p) not in done:
                    done.add((who, p))
                    win = [(s_, e_) for q, s_, e_ in stays.get(who, []) if _same(q, p)] or [(0.0, dur)]
                    items.append(dict(label="mark %s %.3f,%.3f" % (who, p[0], p[1]), who=who, a=p, b=p, hard=True,
                                      win=win))
            for (p, t0, _), (q, t1, snap) in zip(lst, lst[1:]):
                if _same(p, q) or snap:                     # a snap is a cut, not a walk
                    continue
                L = math.hypot(q[0] - p[0], q[1] - p[1])
                items.append(dict(label="walk %s %.3f,%.3f>%.3f,%.3f" % (who, p[0], p[1], q[0], q[1]), who=who, a=p,
                                  b=q, hard=on(p) and on(q), win=[(t1, t1 + L / WALK_SPEED + 0.6)]))
    else:                           # no timeline: the CONTRACT §6 list, always in use
        for who, chains in CHAINS.items():
            for ch in chains:
                for p in ch:
                    if on(p):
                        items.append(dict(label="mark %s %.3f,%.3f" % (who, p[0], p[1]), who=who, a=p, b=p,
                                          hard=True, win=[(0.0, dur)]))
                for a, b in zip(ch, ch[1:]):
                    items.append(dict(label="walk %s %.3f,%.3f>%.3f,%.3f" % (who, a[0], a[1], b[0], b[1]), who=who,
                                      a=a, b=b, hard=on(a) and on(b), win=[(0.0, dur)]))
    vis = {}
    if tl:
        for n in HIDDEN:
            ev = sorted((float(pe["t"]), bool(pe["show"])) for pe in tl["props"] if pe["node"] == "twolands/" + n)
            wins, on_t = [], None
            for t, show in ev:
                if show and on_t is None:
                    on_t = t
                elif not show and on_t is not None:
                    wins.append((on_t, t)); on_t = None
            if on_t is not None:
                wins.append((on_t, dur))
            vis[n] = wins
    return items, vis, dur


ITEMS, VIS, DURATION = _items()
HARD_PTS = sorted({it["a"] for it in ITEMS if it["hard"] and it["a"] == it["b"]})
HARD_SEGS = [(it["a"], it["b"]) for it in ITEMS if it["hard"] and it["a"] != it["b"]]
SOFT_SEGS = [(it["a"], it["b"]) for it in ITEMS if not it["hard"]]


def visible_during(node, win):
    if node not in VIS:
        return True
    return any(s < b - 0.05 and e > a + 0.05 for s, e in VIS[node] for a, b in win)


def exempt(it, name):
    """the well wall for Joseph's walk into and out of the well; the bench for Joseph sitting in the cell"""
    if it["who"] != "joseph":
        return False
    if name == "pit":
        return any(math.hypot(p[0] - WELL[0], p[1] - WELL[1]) < 0.125 for p in (it["a"], it["b"]))
    if name == "cellBench":
        return any(_same(p, CELL) for p in (it["a"], it["b"]))
    return False


def clear_for(node, x, z):
    """distance from (x, z) to the nearest hard mark or walk in use while `node` is shown (all of them for a node
    that is always shown)"""
    d = 9.0
    for it in ITEMS:
        if not it["hard"] or (node in HIDDEN and not visible_during(node, it["win"])):
            continue
        d = min(d, seg_dist((x, z), it["a"], it["b"]))
    return d


def pick_spot(cx, cz, reach, rmax=0.16, avoid=(), step=0.005, margin=0.004, shape=None, node=None):
    """nearest point to (cx, cz) that keeps a footprint (`reach` round it, or `shape` = [(dx, dz, r)] circles)
    clear of every hard mark and walk (+ 0.05), of `avoid` circles and inside the floor"""
    shape = shape or [(0.0, 0.0, reach)]
    cand = []
    for x in np.arange(cx - rmax, cx + rmax + 1e-9, step):
        for z in np.arange(cz - rmax, cz + rmax + 1e-9, step):
            ok = True
            for dx, dz, r in shape:
                px, pz = x + dx, z + dz
                if not (FLOOR[0] + r < px < FLOOR[1] - r and FLOOR[2] + r < pz < FLOOR[3] - r * 0.4) or \
                        (clear_for(node, px, pz) if node else clear_dist(px, pz)) < 0.05 + r + margin or \
                        any(math.hypot(px - ax, pz - az) < ar + r for ax, az, ar in avoid):
                    ok = False; break
            if ok:
                cand.append((math.hypot(x - cx, z - cz), float(x), float(z)))
    if not cand:
        raise SystemExit("no free spot near %.2f,%.2f (reach %.3f)" % (cx, cz, reach))
    cand.sort()
    return round(cand[0][1], 3), round(cand[0][2], 3)


# ============================================================================================ palette
COLOURS = {   # demo colouring (DESIGN.md §3; the rest chosen to sit with it)
    "hills": "#C9C27A", "desert": "#EAD9B0", "dunes": "#E3C98F", "pyramid": "#D6B98A",
    "tentA": "#7A5A40", "tentB": "#3A2E26", "rug": "#B8423A",
    "wool": "#F3ECDD", "sheepFace": "#4A3A30", "oliveCrown": "#8FA876", "oliveTrunk": "#7A6650",
    "wellStone": "#A39A8C",
    "camel": "#D9B47A", "saddleRed": "#B8423A", "saddleBlue": "#2E5FA8", "bundle": "#C9A26A",
    "dais": "#E3CFA3", "palaceWall": "#D9C9A0", "columnCream": "#F1E3C0", "bandBlue": "#2E5FA8", "bandRed": "#C8423A",
    "lintel": "#EBDDB8", "gold": "#E8B84A", "throne": "#E8B84A",
    "mudBrick": "#D8B07A", "storeDoor": "#8A5A3B",
    "cloud": "#FFFFFF", "daySky": "#CFE6F7", "nightSky": "#2E3F7A", "meadow": "#8DB36A",
    "sheafBig": "#E8B84A", "sheafSmall": "#F2D27A", "sun": "#F2C744", "moon": "#F7E7A1", "river": "#3B8FD0",
    "cowFat": "#A9743F", "cowCream": "#F3E2B8", "cowThin": "#8F7F6C", "earFat": "#E8B84A", "earThin": "#C9B98A",
}


# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model; `off` shifts it for pieces laid out apart
    on the sheet), faces with region, smooth flag and a no-raster flag (bits that sample a named texel).
    Same as the earlier packs' MB (pipeline/ru_bethlehem.py) plus `off`."""

    def __init__(self):
        self.V, self.P, self.F, self.R, self.S, self.N = [], [], [], [], [], []
        self.W = {}
        self.nr = False
        self.off = (0.0, 0.0, 0.0)

    def v(self, x, h, z, p=None):
        self.V.append((float(x), float(h), float(z)))
        if p is None:
            p = (x + self.off[0], h + self.off[1], z + self.off[2])
        self.P.append(tuple(float(c) for c in p))
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

    def add(self, src, fn):
        """instance of template `src`: world = fn(local); P = the template's own P (drawing model)"""
        base = len(self.V)
        for i, (x, h, z) in enumerate(src.V):
            self.V.append(tuple(float(c) for c in fn((x, h, z))))
            self.P.append(src.P[i])
        for f, r, s, nr in zip(src.F, src.R, src.S, src.N):
            self.F.append([base + i for i in f]); self.R.append(r); self.S.append(s); self.N.append(nr or self.nr)


REGION_MATS = {}
P_OF, NR_OF, REG_OF = {}, {}, {}
DECOR = {}                    # drawing -> [(p0, p1)] single drawn lines in drawing-model coords


# ============================================================================================ small helpers
def ell(cx, cy, rx, ry, n=20, rot=0.0):
    c, s = math.cos(rot), math.sin(rot)
    out = []
    for k in range(n):
        t = TAU * k / n
        x, y = rx * math.cos(t), ry * math.sin(t)
        out.append((cx + x * c - y * s, cy + x * s + y * c))
    return out


def xform(poly, cx=0.0, cy=0.0, rot=0.0, s=1.0, px=0.0, py=0.0):
    """rotate (about the pivot px, py), scale, then move by (cx, cy)"""
    c, sn = math.cos(rot), math.sin(rot)
    return [(cx + s * ((x - px) * c - (y - py) * sn), cy + s * ((x - px) * sn + (y - py) * c)) for x, y in poly]


def rrect(cx, cy, hw, hh, r, n=5):
    out = []
    for qx, qy, a0 in ((1, 1, 0.0), (-1, 1, 0.5 * math.pi), (-1, -1, math.pi), (1, -1, 1.5 * math.pi)):
        ox, oy = cx + qx * (hw - r), cy + qy * (hh - r)
        for k in range(n + 1):
            a = a0 + 0.5 * math.pi * k / n
            out.append((ox + r * math.cos(a), oy + r * math.sin(a)))
    return out


def star_poly(cx, cy, R, r, n=5, rot=0.0):
    return [(cx + (R if k % 2 == 0 else r) * math.cos(rot + math.pi / 2 + math.pi * k / n),
             cy + (R if k % 2 == 0 else r) * math.sin(rot + math.pi / 2 + math.pi * k / n)) for k in range(2 * n)]


def relief(mb, poly, z0, z1, reg, back=False):
    extrude(mb, poly, z0, z1, reg, back=back)


def puff2(mb, outer, holes, zc, half, reg, rad=0.008, edge=0.3, step=0.008, smooth=True):
    """pillow solid from a front polygon with holes (the dream cloud frames); like stage.puff"""
    loops = [np.array(outer, float)] + [np.array(h, float) for h in holes]
    bnds = [_resample(l, step) for l in loops]
    lo, hi = loops[0].min(0), loops[0].max(0)
    G = []
    for j, y in enumerate(np.arange(lo[1] + step * 0.5, hi[1], step * 0.87)):
        for x in np.arange(lo[0] + (j % 2) * step * 0.5 + step * 0.25, hi[0], step):
            G.append((x, y))
    G = np.array(G) if G else np.zeros((0, 2))

    def solid(Q):
        k = _inside(Q, loops[0])
        for h in loops[1:]:
            k &= ~_inside(Q, h)
        return k

    def edist(Q):
        return np.min([_edge_dist(Q, l) for l in loops], axis=0)
    if len(G):
        G = G[solid(G)]
        G = G[edist(G) > step * 0.45]
    verts, edges = [], []
    for b in bnds:
        o = len(verts)
        verts += [Vector((float(x), float(y))) for x, y in b]
        edges += [(o + i, o + (i + 1) % len(b)) for i in range(len(b))]
    verts += [Vector((float(x), float(y))) for x, y in G]
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-8, True)
    V = np.array([(v.x, v.y) for v in vs])
    T = [tuple(f) for f in fs if len(f) == 3]
    cen = np.array([V[list(t)].mean(0) for t in T])
    T = [t for t, k in zip(T, solid(cen)) if k]
    d = edist(V)
    off = half * (edge + (1 - edge) * np.sqrt(np.clip(d / rad, 0, 1)))
    fr = [mb.v(x, y, zc + o) for (x, y), o in zip(V, off)]
    bk = [mb.v(x, y, zc - o) for (x, y), o in zip(V, off)]
    for t in T:
        mb.fo([fr[i] for i in t], reg, (0, 0, 1), smooth)
        mb.fo([bk[i] for i in t], reg, (0, 0, -1), smooth)
    for li, b in enumerate(bnds):
        order = [int(np.argmin(((V - p) ** 2).sum(1))) for p in b]
        K = len(b)
        for i in range(K):
            a_, b_ = order[i], order[(i + 1) % K]
            mid = (V[a_] + V[b_]) / 2
            dx, dy = V[b_] - V[a_]
            nrm = np.array([dy, -dx]); L = np.linalg.norm(nrm) + 1e-12; nrm /= L
            if solid(np.array([mid + nrm * step * 0.3]))[0]:
                nrm = -nrm
            mb.fo([fr[a_], fr[b_], bk[b_], bk[a_]], reg, (nrm[0], nrm[1], 0), smooth)


def tilt_fn(cx, ch, cz, deg=15.0):
    """dream panel: local (a, b, depth) facing +z -> world, the face tilted `deg` up toward the camera"""
    t = math.radians(deg); c, s = math.cos(t), math.sin(t)

    def f(p):
        a, b, d = p
        return (cx + a, ch + b * c + d * s, cz - b * s + d * c)
    return f


# ============================================================================================ ground
def dune_edges(z):
    back = max(0.0, (-0.28 - z) / 0.30)                       # the strip widens toward the back
    xl = -0.065 + 0.012 * math.sin(7.0 * z + 1.0) - 0.035 * back
    xr = 0.045 + 0.010 * math.sin(6.0 * z + 0.3) + 0.030 * back
    return xl, xr


def road_polys():
    cl = catmull([(-0.62, 0.186), (-0.45, 0.192), (-0.30, 0.196), (-0.18, 0.170), (-0.07, 0.118), (0.05, 0.080),
                  (0.20, 0.062), (0.300, 0.020), (0.335, -0.080), (0.330, -0.200), (0.320, -0.335)], 0.012)
    return strip_poly(cl, 0.085, 0.070), cl


def build_ground(root):
    """page floor (no drawing: every face takes a named texel): green-ochre pasture left, pale sand right, the dune
    strip between (low ripples on the walk lines, bigger dunes at the back), the caravan road; grass tufts, pebbles,
    desert rocks, the low stone sheep-fold"""
    road, cl = road_polys()
    zs = np.linspace(FLOOR[2], FLOOR[3], 40)
    dune = [(dune_edges(z)[0], z) for z in zs] + [(dune_edges(z)[1], z) for z in zs[::-1]]
    dune = np.array(dune)
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    outlines = [_resample(rect, 0.03), _resample(road, 0.012), _resample(dune, 0.015)]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    allo = np.concatenate(outlines)
    for j, z in enumerate(np.arange(FLOOR[2] + 0.02, FLOOR[3] - 0.01, 0.034)):
        for x in np.arange(FLOOR[0] + 0.02 + (j % 2) * 0.017, FLOOR[1] - 0.01, 0.034):
            p = np.array([x + (nz(x, z) - 0.5) * 0.012, z + (nz(z, x) - 0.5) * 0.012])
            if np.min(np.hypot(*(allo - p).T)) > 0.009:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def in_dune(x, z):
        xl, xr = dune_edges(z)
        return xl <= x <= xr

    def height(x, z):
        h = 0.0012 + 0.0008 * (math.sin(17 * x + 3 * z) * math.sin(11 * z - 5 * x) * 0.5 + 0.5)
        if in_dune(x, z):
            xl, xr = dune_edges(z)
            u = (x - xl) / max(xr - xl, 1e-6)
            dr = min(seg_dist((x, z), tuple(cl[i]), tuple(cl[i + 1])) for i in range(0, len(cl) - 1, 2))
            fade = min(1.0, max(0.0, (dr - 0.045) / 0.035))          # flat where the road crosses
            h += 0.0075 * math.sin(math.pi * u) * (0.6 + 0.4 * math.sin(23 * z + 2 * x)) * fade
        if in_poly((x, z), road):
            h = min(h, 0.0007 + 0.0002 * nz(x, z))
        return h
    H = [height(x, z) for x, z in V]

    def region(c):
        if in_poly(c, road):
            return "road"
        if in_dune(*c):
            return "dunes"
        return "pasture" if c[0] < 0 else "sand"
    mb = MB(); mb.nr = True
    idx = {}
    for f in fs:
        if len(f) != 3:
            continue
        c = tuple(V[list(f)].mean(0))
        q = []
        for i in f:
            if i not in idx:
                idx[i] = mb.v(V[i][0], H[i], V[i][1])
            q.append(idx[i])
        mb.fo(q, region(c), UP, True)
    for (ax, az), (bx, bz) in zip(rect, np.roll(rect, -1, axis=0)):
        n = int(math.hypot(bx - ax, bz - az) / 0.05) + 1
        cx, cz = (ax + bx) / 2, (az + bz) / 2
        for i in range(n):
            x0, z0 = ax + (bx - ax) * i / n, az + (bz - az) * i / n
            x1, z1 = ax + (bx - ax) * (i + 1) / n, az + (bz - az) * (i + 1) / n
            reg = "pasture" if (x0 + x1) < 0 else "sand"
            mb.fo([mb.v(x0, height(x0, z0), z0), mb.v(x1, height(x1, z1), z1), mb.v(x1, -0.002, z1),
                   mb.v(x0, -0.002, z0)], reg, (cx, 0, cz - (FLOOR[2] + FLOOR[3]) / 2) if abs(az - bz) < 1e-6
                  else (cx, 0, 0))
    # back dunes: soft mounds between the two lands, behind every walk
    for i, (x, z, r, hh, sx) in enumerate(((0.050, -0.430, 0.045, 0.018, 1.6),)):
        if clear_dist(x, z, True) < 0.05 + r:
            continue
        prof = [(0.0, 0.0)] + [(r * (1 - u), hh * (1 - (1 - u) ** 2) ** 1.5) for u in np.linspace(0, 1, 9)]
        lathe(mb, prof, "dunes", C=(x, 0, z), seg=20, sx=sx, sv=0.85,
              rfun=lambda th, ii, k, s_=i: 1.0 + 0.06 * math.sin(3 * th + s_))
    rng = random.Random(23)
    blocked = [(-0.60, -0.28, -0.54, -0.30), (0.19, 0.57, -0.58, -0.33), (0.39, 0.60, -0.18, 0.09)]

    def free(x, z, pad=0.0):
        if not (FLOOR[0] + 0.01 < x < FLOOR[1] - 0.01 and FLOOR[2] + 0.03 < z < FLOOR[3] - 0.01):
            return False
        if any(x0 - pad < x < x1 + pad and z0 - pad < z < z1 + pad for x0, x1, z0, z1 in blocked):
            return False
        if math.hypot(x - WELL[0], z - WELL[1]) < WELL_RO + 0.01 or math.hypot(x - CELL[0], z - CELL[1]) < 0.13:
            return False
        return not in_poly((x, z), road)
    tufts, pebbles, rocks = [], [], []
    tries = 0
    while len(tufts) < 70 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, -0.08), rng.uniform(-0.55, 0.20)
        if not free(x, z) or in_dune(x, z) or any(math.hypot(x - a, z - b) < 0.03 for a, b in tufts):
            continue
        tufts.append((x, z))
    for x, z in tufts:
        tall = 0.016 if clear_dist(x, z, True) > 0.065 else 0.0105
        for k in range(5):
            a = TAU * k / 5 + rng.uniform(-0.4, 0.4)
            hh = tall * rng.uniform(0.7, 1.05); lean = rng.uniform(0.25, 0.5) * hh
            d = (math.cos(a), math.sin(a))
            blade(mb, [(x + d[0] * 0.0015, 0.0005, z + d[1] * 0.0015), (x + d[0] * lean, hh, z + d[1] * lean)],
                  [0.0036, 0.0], "tuft", nrm=(d[0], 0.0, d[1]))
    tries = 0
    while len(pebbles) < 40 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z) or any(math.hypot(x - a, z - b) < 0.02 for a, b in pebbles + tufts):
            continue
        pebbles.append((x, z))
    for i, (x, z) in enumerate(pebbles):
        r = rng.uniform(0.0035, 0.006)
        lumpy(mb, (x, r * 0.35, z), r, "stone" if x < 0 else "rock", seg=5, rings=3, sh=0.55,
              sx=rng.uniform(0.9, 1.4), amp=0.18, seed=i)
    tries = 0
    while len(rocks) < 10 and tries < 8000:
        tries += 1
        x, z = rng.uniform(0.06, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z, 0.01) or clear_dist(x, z, True) < 0.075:
            continue
        if any(math.hypot(x - a, z - b) < 0.06 for a, b in rocks):
            continue
        rocks.append((x, z))
    for i, (x, z) in enumerate(rocks):
        r = rng.uniform(0.009, 0.014)
        lumpy(mb, (x, r * 0.3, z), r, "rock", seg=7, rings=4, sh=0.6, sx=rng.uniform(1.0, 1.5), amp=0.2,
              seed=i + 700, smooth=False)
    # the low stone sheep-fold behind the sheep: two courses of rough stones on an arc
    fold = []
    for k in range(2):
        for j, a in enumerate(np.linspace(math.radians(195), math.radians(345), 15 - k)):
            x = -0.205 + 0.095 * math.cos(a) + (0.004 if k else 0.0)
            z = -0.375 + 0.060 * math.sin(a)
            r = 0.0105 - 0.0015 * k
            fold.append((x, z))
            lumpy(mb, (x, 0.008 + 0.014 * k, z), r, "stone", seg=7, rings=4, sh=0.8, sx=1.25, amp=0.2,
                  seed=k * 40 + j + 300, smooth=False)
    ob = make_obj("ground", mb, root, smooth_angle=35)
    return ob, {"tufts": len(tufts), "pebbles": len(pebbles), "rocks": len(rocks), "foldStones": len(fold)}


# ============================================================================================ horizon
HZ_F, HZ_B = -0.566, -0.585
PYRAMIDS = [(0.200, 0.24, 0.215), (0.395, 0.36, 0.279), (0.555, 0.20, 0.190)]   # x, base width, apex height


def hills_h(x):
    t = min(1.0, max(0.0, (0.05 - x) / 0.12))
    return t * (0.105 + 0.070 * math.exp(-((x + 0.42) / 0.13) ** 2) + 0.050 * math.exp(-((x + 0.15) / 0.11) ** 2)
                + 0.006 * math.sin(17 * x)) + (1 - t) * 0.05


def far_h(x):
    return 0.150 + 0.065 * math.exp(-((x + 0.28) / 0.16) ** 2) + 0.008 * math.sin(11 * x + 1)


def desert_h(x):
    return 0.126 + 0.009 * math.sin(9 * x + 1.0) + 0.004 * math.sin(23 * x) - 0.032 * math.exp(-((x - 0.40) / 0.09) ** 2)


def dune_h(x):
    return 0.070 + 0.085 * math.exp(-((x - 0.02) / 0.085) ** 2)


def build_horizon(root):
    """backdrop relief across the back (front z -0.566, top <= 0.28): Canaan's far blue hills and near green hills
    with round bushes, a golden dune in the middle, the Egyptian desert and three pyramids (two lit facets each)"""
    mb = MB()
    xs = np.linspace(-0.60, -0.02, 40)
    extrude(mb, [(-0.60, 0.0), (-0.02, 0.0)] + [(x, far_h(x)) for x in xs[::-1]], HZ_B, HZ_B + 0.006, "hills",
            back=False)
    xs = np.linspace(-0.60, 0.06, 48)
    extrude(mb, [(-0.60, 0.0), (0.06, 0.0)] + [(x, hills_h(x)) for x in xs[::-1]], HZ_F - 0.010, HZ_F, "hills",
            back=False)
    xs = np.linspace(-0.04, 0.60, 48)
    extrude(mb, [(-0.04, 0.0), (0.60, 0.0)] + [(x, desert_h(x)) for x in xs[::-1]], HZ_F - 0.010, HZ_F, "desert",
            back=False)
    # the golden dune between the lands: a real mound at the back (its front view is the dune_h silhouette)
    prof = [(0.0, 0.0)] + [(1.0 - u, (1 - (1 - u) ** 2) ** 1.6) for u in np.linspace(0, 1, 10)]
    rx, rz, top = 0.185, 0.055, dune_h(0.02)
    lathe(mb, [(r, hh * top) for r, hh in prof], "dunes", C=(0.02, 0, HZ_F + 0.012), seg=28, sx=rx, sv=rz,
          rfun=lambda th, ii, k: 1.0 + 0.05 * math.sin(3 * th))
    for x, w, hh in PYRAMIDS:                         # flat triangular slabs behind the desert line
        zc = HZ_F - 0.012
        extrude(mb, [(x - w / 2, 0.0), (x + w / 2, 0.0), (x, hh)], zc - 0.006, zc, "pyramid", back=False)
    rng = random.Random(3)
    for i in range(9):                                 # round bushes on the near hills
        x = rng.uniform(-0.57, -0.06)
        hb = hills_h(x) * rng.uniform(0.35, 0.8)
        r = rng.uniform(0.011, 0.017)
        lumpy(mb, (x, hb, HZ_F + 0.004), r, "hills", seg=9, rings=5, sh=0.85, sz=0.5, amp=0.14, seed=i + 20)
    for i, x in enumerate((-0.53, -0.47, -0.33, -0.21)):    # a few dark cypress-like trees on the far hills
        hb = far_h(x) - 0.03
        lathe(mb, [(0.0, hb), (0.008, hb + 0.01), (0.007, hb + 0.04), (0.0, hb + 0.062)], "hills",
              C=(x, 0, HZ_B + 0.008), seg=8, sv=0.5)
    return make_obj("horizon", mb, root, origin=(0.0, 0.0, HZ_F), smooth_angle=50)


# ============================================================================================ tent
TENT = (-0.575, -0.305, -0.51, -0.33)
TENT_POLES_X = (-0.555, -0.44, -0.325)


def tent_h(x, z):
    hz = float(np.interp(z, [-0.51, -0.42, -0.33], [0.106, 0.205, 0.122]))
    d = min(abs(x - p) for p in TENT_POLES_X)
    sag = 0.018 * min(1.0, d / 0.0575) ** 2
    out = max(0.0, TENT_POLES_X[0] - x, x - TENT_POLES_X[2])
    return hz - sag - 0.6 * out


def build_tent(root):
    """Jacob's goat-hair tent: a wide low roof of woven strips (brown and black, a raised seam between strips) on
    three rows of poles, sagging between them; closed back and back half of the sides, open front with a valance;
    a red rug inside, clay jars at the right; poles, guy ropes and pegs take a wood texel"""
    mb = MB()
    x0, x1, zb, zf = TENT
    xs = np.linspace(x0, x1, 28); zs = np.linspace(zb, zf, 13)
    g = [[mb.v(x, tent_h(x, z), z) for z in zs] for x in xs]
    gi = [[mb.v(x, tent_h(x, z) - 0.002, z) for z in zs] for x in xs]

    def stripe(z):
        if z > -0.375:
            return "tentA"
        if z > -0.42:
            return "tentB"
        return "tentA" if z > -0.465 else "tentB"
    for i in range(len(xs) - 1):
        for j in range(len(zs) - 1):
            r = stripe((zs[j] + zs[j + 1]) / 2)
            mb.fo([g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]], r, UP, True)
            mb.fo([gi[i][j], gi[i + 1][j], gi[i + 1][j + 1], gi[i][j + 1]], r, (0, -1, 0), True)
    for z in (-0.375, -0.465):                         # seams between the woven strips
        tube(mb, [(x, tent_h(x, z) + 0.0008, z) for x in np.linspace(x0 + 0.004, x1 - 0.004, 22)], 0.0024, "tentB",
             seg=4, smooth=False)
    for z in (-0.348, -0.398, -0.442, -0.488):        # weave ribs inside each strip
        tube(mb, [(x, tent_h(x, z) + 0.0004, z) for x in np.linspace(x0 + 0.004, x1 - 0.004, 22)], 0.0012,
             stripe(z), seg=3, smooth=False, caps=False)
    # front valance: a scalloped hanging strip
    vt = [(x, tent_h(x, zf)) for x in np.linspace(x0, x1, 28)]
    for i in range(len(vt) - 1):
        (xa, ha), (xb, hb) = vt[i], vt[i + 1]
        dr = 0.016 + 0.004 * math.cos(math.pi * (i % 4) / 2)
        a, b = mb.v(xa, ha, zf + 0.0012), mb.v(xb, hb, zf + 0.0012)
        c, d = mb.v(xb, hb - dr, zf + 0.0016), mb.v(xa, ha - dr, zf + 0.0016)
        mb.fo([a, b, c, d], "tentB", (0, 0, 1)); mb.fo([a, b, c, d], "tentB", (0, 0, -1))
    # back wall (inside face dark) and the back half of the side walls
    nb = 16
    for i in range(nb):
        xa, xb = x0 + (x1 - x0) * i / nb, x0 + (x1 - x0) * (i + 1) / nb
        o = [mb.v(xa, 0.0, zb), mb.v(xb, 0.0, zb), mb.v(xb, tent_h(xb, zb), zb), mb.v(xa, tent_h(xa, zb), zb)]
        mb.fo(o, "tentB", (0, 0, 1))
        o2 = [mb.v(xa, 0.0, zb - 0.002), mb.v(xb, 0.0, zb - 0.002), mb.v(xb, tent_h(xb, zb), zb - 0.002),
              mb.v(xa, tent_h(xa, zb), zb - 0.002)]
        mb.fo(o2, "tentA", (0, 0, -1))
    for x, s in ((x0, -1), (x1, 1)):
        zz = np.linspace(zb, -0.405, 7)
        for j in range(len(zz) - 1):
            za, zc = zz[j], zz[j + 1]
            q = [mb.v(x, 0.0, za), mb.v(x, 0.0, zc), mb.v(x, tent_h(x, zc), zc), mb.v(x, tent_h(x, za), za)]
            mb.fo(q, "tentB", (s, 0, 0))
            q2 = [mb.v(x - s * 0.002, 0.0, za), mb.v(x - s * 0.002, 0.0, zc), mb.v(x - s * 0.002, tent_h(x, zc), zc),
                  mb.v(x - s * 0.002, tent_h(x, za), za)]
            mb.fo(q2, "tentB", (-s, 0, 0))
    # rug with a fringe, two cushions
    box(mb, -0.530, -0.350, 0.0005, 0.0035, -0.480, -0.348, "rug", skip=("bottom",))
    for x in np.linspace(-0.526, -0.354, 16):
        box(mb, x - 0.0015, x + 0.0015, 0.0005, 0.0025, -0.348, -0.342, "rug", skip=("bottom",))
    for k, (x, z) in enumerate(((-0.505, -0.455), (-0.375, -0.458))):
        lumpy(mb, (x, 0.010, z), 0.016, "rug", seg=10, rings=5, sh=0.45, sx=1.3, amp=0.06, seed=k + 60)
    # clay jars outside the right front corner (no-raster: the rug's red)
    mb.nr = True
    for k, (x, z, s) in enumerate(((-0.282, -0.352, 1.0), (-0.268, -0.392, 0.85), (-0.292, -0.318, 0.7))):
        prof = [(0.0, 0.0), (0.009, 0.0), (0.015, 0.010), (0.017, 0.024), (0.014, 0.038), (0.007, 0.046),
                (0.0065, 0.051), (0.0085, 0.054), (0.0, 0.050)]
        lathe(mb, [(r * s, h * s) for r, h in prof], "clay", C=(x, 0, z), seg=12)
    # poles, ropes, pegs: no-raster (a wood texel)
    for z, hh in ((zf + 0.002, None), (-0.42, None), (zb + 0.003, None)):
        for x in TENT_POLES_X:
            tube(mb, [(x, 0.0, z), (x, tent_h(x, z) + 0.004, z)], 0.0042, "pole", seg=6)
    for (px, pz), (gx, gz) in (((x0, zf), (x0 - 0.022, -0.315)), ((x1, zf), (x1 + 0.030, -0.312)),
                               ((x0, -0.42), (x0 - 0.024, -0.43)), ((x1, -0.42), (x1 + 0.030, -0.44)),
                               ((x0, zb), (x0 - 0.02, zb - 0.02)), ((x1, zb), (x1 + 0.025, zb - 0.02))):
        tube(mb, [(px, tent_h(px, pz) - 0.004, pz), (gx, 0.004, gz)], 0.0011, "pole", seg=4)
        box(mb, gx - 0.002, gx + 0.002, 0.0, 0.008, gz - 0.002, gz + 0.002, "pole", skip=("bottom",))
    mb.nr = False
    return make_obj("tent", mb, root, origin=(-0.44, 0.0, -0.42), smooth_angle=55)


# ============================================================================================ sheep
SHEEP = [(-0.245, -0.352, 0.35, 1.0), (-0.172, -0.395, 2.6, 0.93), (-0.200, -0.318, -0.25, 0.88)]


def sheep_template():
    """one woolly sheep (local, facing +x): a cloud of wool, a dark face with floppy ears; legs take the face texel"""
    mb = MB()
    lumpy(mb, (0.0, 0.040, 0.0), 0.025, "wool", seg=14, rings=8, sh=0.82, sx=1.35, sz=0.95, amp=0.20, seed=1.0)
    for k, (dx, dh, dz) in enumerate(((-0.016, 0.058, 0.0), (0.004, 0.061, 0.004), (0.020, 0.055, -0.004),
                                      (-0.030, 0.045, 0.0))):
        lumpy(mb, (dx, dh, dz), 0.010, "wool", seg=8, rings=5, sh=0.9, amp=0.25, seed=k + 3.0)
    lumpy(mb, (0.047, 0.048, 0.0), 0.0182, "sheepFace", seg=12, rings=7, sh=0.95, sx=1.40, sz=0.85, amp=0.04, seed=9)
    for s in (-1, 1):
        lumpy(mb, (0.036, 0.056, s * 0.014), 0.0060, "sheepFace", seg=6, rings=4, sh=0.45, sx=1.6, amp=0.05)
    lumpy(mb, (0.030, 0.062, 0.0), 0.008, "wool", seg=8, rings=5, sh=0.8, amp=0.2, seed=12)
    for lx in (-0.017, 0.017):
        for lz in (-0.010, 0.010):
            tube(mb, [(lx, 0.026, lz), (lx, 0.0, lz)], 0.0046, "sheepFace", seg=6)
    return mb


def build_sheep(root, tpl):
    mb = MB()
    for x, z, yaw, s in SHEEP:
        mb.add(tpl, yaw_fn(x, z, yaw, s))
    return make_obj("sheep", mb, root, origin=(-0.21, 0.0, -0.36), smooth_angle=60)


# ============================================================================================ olive
OLIVE = (-0.555, -0.065)


def build_olive(root):
    """gnarled olive: three twisted strands round a crooked spine (a thick trunk), flaring roots, a broad crown of
    lumpy silver-green blobs leaning toward the page (crown bottom >= 0.20)"""
    ox, oz = OLIVE
    mb = MB()

    def axis(u):
        return (ox + 0.040 * u ** 1.3 + 0.010 * math.sin(math.pi * u), 0.205 * u - 0.002,
                oz + 0.008 * math.sin(2.1 * math.pi * u))
    ring = []
    for j in range(13):
        u = j / 12
        c = axis(u)
        ring.append((c, 0.038 * (1 - 0.42 * u) * (1.25 if u < 0.08 else 1.0)))
    tube(mb, [c for c, _ in ring], [r for _, r in ring], "oliveTrunk", seg=14)
    for k, (u, a, r) in enumerate(((0.25, 0.8, 0.012), (0.50, 3.4, 0.011), (0.70, 5.0, 0.010))):   # knots
        c = axis(u)
        rr = 0.030 * (1 - 0.42 * u)
        lumpy(mb, (c[0] + rr * 0.8 * math.cos(a), c[1], c[2] + rr * 0.8 * math.sin(a)), r, "oliveTrunk", seg=8,
              rings=5, amp=0.1, seed=k + 50)
    for k in range(5):
        a = TAU * k / 5 + 0.3
        d = (math.cos(a), math.sin(a))
        tube(mb, [(ox + d[0] * 0.010, 0.018, oz + d[1] * 0.010), (ox + d[0] * 0.030, 0.006, oz + d[1] * 0.030),
                  (ox + d[0] * 0.046, -0.002, oz + d[1] * 0.046)], [0.010, 0.007, 0.0035], "oliveTrunk", seg=6)
    top = Vector(axis(0.97))
    cc = Vector((ox + 0.050, 0.268, oz + 0.004))
    blobs = [((0.000, 0.026, 0.000), 0.060), ((-0.062, 0.000, 0.008), 0.050), ((0.064, -0.002, 0.000), 0.050),
             ((0.012, -0.004, 0.050), 0.046), ((-0.020, 0.006, -0.050), 0.048), ((0.040, 0.030, -0.034), 0.042),
             ((-0.042, 0.032, -0.012), 0.040), ((0.044, 0.012, 0.036), 0.040), ((-0.040, 0.004, 0.038), 0.038)]
    for i, (off, r) in enumerate(blobs):
        c = cc + Vector(off)
        sh = 0.70
        c.y = max(c.y, 0.205 + r * sh)
        end = c - Vector((0, r * 0.5, 0))
        if i in (1, 2, 3, 4):
            mid = top + (end - top) * 0.5 + Vector((0, 0.010, 0))
            tube(mb, [tuple(top), tuple(mid), tuple(end)], [0.0080, 0.006, 0.0038], "oliveTrunk", seg=6)
        lumpy(mb, tuple(c), r, "oliveCrown", seg=13, rings=7, sh=sh, amp=0.10, seed=i * 7 + 1)
    return make_obj("olive", mb, root, origin=(ox, 0.0, oz), smooth_angle=75)


# ============================================================================================ well
def build_pit(root, bucket_at):
    """the dry well: four courses of rough stone blocks (inner r 0.07, outer 0.09, top h 0.08), a dark floor; the
    printed drawing shows single joint lines (DECOR). Child `bucket`: a banded wooden bucket and a coil of rope."""
    wx, wz = WELL
    mb = MB()
    rng = random.Random(17)
    dec = DECOR.setdefault("pit", [])
    nc, nb = 4, 13
    ch = WELL_H / nc
    for k in range(nc):
        h0, h1 = ch * k, ch * (k + 1) - 0.0012
        if k == nc - 1:
            h1 = WELL_H
        ph = (0.5 if k % 2 else 0.0) * TAU / nb
        for j in range(nb):
            a0 = ph + TAU * j / nb + 0.010; a1 = ph + TAU * (j + 1) / nb - 0.010
            ri = WELL_RI + rng.uniform(-0.0012, 0.0008); ro = WELL_RO - rng.uniform(0.0, 0.0022)
            hb, ht = h0 + 0.0006, h1 - rng.uniform(0.0, 0.0015) * (k < nc - 1)
            A = np.linspace(a0, a1, 4)
            bump = [1.0 + 0.012 * math.sin(3 * a + j) for a in A]
            O = [[mb.v(wx + ro * bm * math.cos(a), h, wz + ro * bm * math.sin(a)) for a, bm in zip(A, bump)]
                 for h in (hb, ht)]
            I = [[mb.v(wx + ri * math.cos(a), h, wz + ri * math.sin(a)) for a in A] for h in (hb, ht)]
            for i in range(3):
                am = (A[i] + A[i + 1]) / 2; rd = (math.cos(am), 0, math.sin(am))
                mb.fo([O[0][i], O[0][i + 1], O[1][i + 1], O[1][i]], "wellStone", rd)
                mb.fo([I[0][i], I[0][i + 1], I[1][i + 1], I[1][i]], "wellStone", (-rd[0], 0, -rd[2]))
                mb.fo([O[1][i], O[1][i + 1], I[1][i + 1], I[1][i]], "wellStone", UP)
            for e, s in ((0, -1), (3, 1)):
                t = (-math.sin(A[e]) * s, 0, math.cos(A[e]) * s)
                mb.fo([O[0][e], O[1][e], I[1][e], I[0][e]], "wellStone", t)
            # print: the joint at a0 on the outer face, the course line under the block, top joints
            pa = lambda a, h, r=WELL_RO: (wx + r * math.cos(a), h, wz + r * math.sin(a))
            dec.append((pa(a0 - 0.010, h0), pa(a0 - 0.010, h1)))
            for i in range(3):
                dec.append((pa(A[i], h0), pa(A[i + 1], h0)))
            if k == nc - 1:
                dec.append((pa(a0 - 0.010, WELL_H, WELL_RI), pa(a0 - 0.010, WELL_H, WELL_RO)))
    for i in range(48):                               # the top's inner edge
        a, b = TAU * i / 48, TAU * (i + 1) / 48
        dec.append(((wx + WELL_RI * math.cos(a), WELL_H, wz + WELL_RI * math.sin(a)),
                    (wx + WELL_RI * math.cos(b), WELL_H, wz + WELL_RI * math.sin(b))))
    mb.nr = True
    lathe(mb, [(0.0, 0.0045), (WELL_RI + 0.001, 0.0045), (WELL_RI + 0.001, 0.0)], "wellDark", C=(wx, 0, wz), seg=24)
    mb.nr = False
    pit = make_obj("pit", mb, root, origin=(wx, 0.0, wz), smooth_angle=35)
    # bucket + rope coil
    bx, bz = bucket_at
    bm = MB(); bm.nr = True
    lathe(bm, [(0.0, 0.0), (0.0125, 0.0), (0.0150, 0.028), (0.0138, 0.028), (0.0118, 0.004), (0.0, 0.004)], "bucket",
          C=(bx, 0, bz), seg=14, smooth=True)
    for hh in (0.006, 0.022):
        lathe(bm, [(0.0128 + hh * 0.08, hh), (0.0136 + hh * 0.08, hh + 0.0005), (0.0136 + hh * 0.08, hh + 0.003),
                   (0.0128 + hh * 0.08, hh + 0.0035)], "bucket", C=(bx, 0, bz), seg=14)
    tube(bm, [(bx - 0.0148, 0.027, bz), (bx - 0.010, 0.040, bz), (bx, 0.044, bz), (bx + 0.010, 0.040, bz),
              (bx + 0.0148, 0.027, bz)], 0.0012, "rope", seg=4)
    coil = [(bx + 0.030 + (0.012 - 0.0006 * t) * math.cos(t), 0.0025 + 0.0005 * t, bz - 0.006 + (0.012 - 0.0006 * t)
             * math.sin(t)) for t in np.linspace(0, 3 * TAU, 54)]
    tube(bm, coil, 0.0022, "rope", seg=5)
    tube(bm, [coil[-1], (bx + 0.012, 0.030, bz - 0.004), (bx + 0.006, 0.043, bz)], 0.0018, "rope", seg=5)
    bm.nr = False
    bk = make_obj("bucket", bm, pit, origin=(bx, 0.0, bz), smooth_angle=50)
    return pit, bk


# ============================================================================================ caravan
CAMEL_SHAPE = [(-0.100, 0.0, 0.026), (-0.055, 0.0, 0.040), (-0.010, 0.0, 0.044), (0.035, 0.0, 0.044),
               (0.062, 0.0, 0.020)]        # footprint circles (dx, dz, r) of the camel facing -x


def build_caravan(root, at):
    """the traders' camel (facing -x): a red cloth over the shoulders and a blue one over the hump, a big bundle
    on its back; a small hooded trader beside its neck with the lead rope (fixed colours: named texels)"""
    cx, cz = at
    mb = MB()
    lumpy(mb, (cx, 0.106, cz), 0.036, "camel", seg=16, rings=8, sh=0.92, sx=1.52, sz=0.92, amp=0.03, seed=2)
    lumpy(mb, (cx + 0.006, 0.142, cz), 0.028, "camel", seg=12, rings=7, sh=0.85, sx=1.2, sz=0.8, amp=0.03, seed=3)
    tube(mb, [(cx - 0.044, 0.112, cz), (cx - 0.066, 0.118, cz), (cx - 0.082, 0.134, cz), (cx - 0.090, 0.150, cz)],
         [0.0165, 0.0145, 0.0125, 0.011], "camel", seg=10)
    lumpy(mb, (cx - 0.102, 0.156, cz), 0.0150, "camel", seg=12, rings=7, sh=0.85, sx=1.55, sz=0.85, amp=0.03, seed=4)
    for s in (-1, 1):
        lumpy(mb, (cx - 0.093, 0.169, cz + s * 0.007), 0.0038, "camel", seg=6, rings=4, sh=1.2, amp=0.05)
    for lx, kn in ((-0.036, 0.007), (0.036, -0.005)):
        for lz in (-0.015, 0.015):
            tube(mb, [(cx + lx, 0.095, cz + lz), (cx + lx + kn, 0.050, cz + lz), (cx + lx, 0.007, cz + lz)],
                 [0.0085, 0.0062, 0.0055], "camel", seg=7)
            lumpy(mb, (cx + lx - 0.002, 0.005, cz + lz), 0.0070, "camel", seg=7, rings=4, sh=0.6, sx=1.3, amp=0.05)
    tube(mb, [(cx + 0.055, 0.114, cz), (cx + 0.062, 0.094, cz), (cx + 0.063, 0.074, cz)], [0.0040, 0.0034, 0.0030],
         "camel", seg=6)
    # two saddle-cloths: arches swept along x (red over the shoulders, blue over the hump)
    arch = [(-0.041, 0.124), (-0.038, 0.138), (-0.030, 0.154), (-0.015, 0.167), (0.0, 0.171), (0.015, 0.167),
            (0.030, 0.154), (0.038, 0.138), (0.041, 0.124)]
    for reg, xa, xb in (("saddleRed", -0.044, -0.002), ("saddleBlue", 0.000, 0.044)):
        xs = np.linspace(cx + xa, cx + xb, 6)
        rows = [[mb.v(x, h + 0.003 * math.sin(9 * x) + (0.004 if reg == "saddleBlue" else 0.0), cz + dz *
                      (1.0 if reg == "saddleRed" else 1.03)) for dz, h in arch] for x in xs]
        for i in range(len(xs) - 1):
            for j in range(len(arch) - 1):
                dz = (arch[j][0] + arch[j + 1][0]) / 2
                mb.fo([rows[i][j], rows[i + 1][j], rows[i + 1][j + 1], rows[i][j + 1]], reg, (0, 0.3, dz), True)
    lumpy(mb, (cx + 0.022, 0.192, cz), 0.036, "bundle", seg=14, rings=7, sh=0.58, sx=1.25, sz=0.95, amp=0.05, seed=5)
    # the trader (no drawing: fixed colours from named texels)
    mb.nr = True
    tx, tz = cx - 0.060, cz - 0.050
    lathe(mb, [(0.0, 0.0), (0.026, 0.0), (0.024, 0.03), (0.018, 0.11), (0.015, 0.145), (0.0, 0.15)], "traderRobe",
          C=(tx, 0, tz), seg=12)
    lumpy(mb, (tx, 0.162, tz + 0.002), 0.0145, "traderFace", seg=10, rings=6, sh=1.1, amp=0.03)
    lathe(mb, [(0.0, 0.140), (0.021, 0.142), (0.020, 0.167), (0.013, 0.184), (0.0, 0.189)], "traderHood",
          C=(tx, 0, tz - 0.004), seg=12, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.45 else 0.55)
    for s in (-1, 1):
        tube(mb, [(tx + s * 0.016, 0.13, tz), (tx + s * 0.021, 0.092, tz + 0.009), (tx + s * 0.013, 0.081, tz + 0.017)],
             0.0048, "traderRobe", seg=6)
    tube(mb, [(tx + 0.013, 0.081, tz + 0.017), (cx - 0.084, 0.120, cz - 0.006), (cx - 0.104, 0.150, cz)], 0.0010,
         "rope", seg=4)
    mb.nr = False
    return make_obj("caravan", mb, root, origin=(cx, 0.0, cz), smooth_angle=55)


# ============================================================================================ palace
PAL = (0.215, 0.545, -0.555, -0.360)          # dais x0 x1 zBack zFront (step 1)
COLS = ((0.258, -0.430), (0.502, -0.430))
THRONE_AT = (0.380, -0.495)
DAIS_TOP = 0.050
FIRE = (0.540, -0.325)


def papyrus_column(mb, x, z, h0):
    """fat papyrus-bud column painted in bands (cream, blue, cream, red, cream), a closed-bud capital, abacus"""
    C = (x, 0, z)
    R = 0.031
    lathe(mb, [(0.0, h0), (R + 0.006, h0), (R + 0.006, h0 + 0.008), (R + 0.002, h0 + 0.011), (0.0, h0 + 0.011)],
          "columnCream", C=C, seg=20, smooth=False)
    rf = lambda th, i, k: 1.0 + 0.05 * abs(math.cos(4 * th))
    bands = [("columnCream", 0.011, 0.028), ("bandBlue", 0.028, 0.082), ("columnCream", 0.082, 0.132),
             ("bandRed", 0.132, 0.186)]
    rad = lambda hh: R - 0.012 * hh
    for reg, a, b in bands:
        lathe(mb, [(0.0, h0 + a), (rad(a), h0 + a), (rad(b), h0 + b), (0.0, h0 + b)], reg, C=C, seg=20, rfun=rf)
    for hh, reg in ((0.028, "bandBlue"), (0.082, "columnCream"), (0.132, "bandRed"), (0.186, "columnCream")):
        lathe(mb, [(rad(hh) + 0.0008, h0 + hh - 0.0018), (rad(hh) + 0.0016, h0 + hh), (rad(hh) + 0.0008, h0 + hh + 0.0018)],
              reg, C=C, seg=20)
    lathe(mb, [(0.0, h0 + 0.186), (0.029, h0 + 0.186), (0.039, h0 + 0.203), (0.045, h0 + 0.220), (0.043, h0 + 0.234),
               (0.031, h0 + 0.243), (0.0, h0 + 0.245)], "columnCream", C=C, seg=24,
          rfun=lambda th, i, k: 1.0 + (0.08 * math.cos(8 * th) if 1 < i < 5 else 0.0))
    box(mb, x - 0.033, x + 0.033, h0 + 0.243, h0 + 0.251, z - 0.033, z + 0.033, "lintel", skip=("bottom",))
    return h0 + 0.251


def build_palace(root):
    """Pharaoh's palace front: a four-step sandstone dais, a back wall, two painted papyrus columns, a lintel with
    the winged sun-disc, two feather fans behind the throne, a fire bowl at the front right; child `throne`"""
    mb = MB()
    x0, x1, zb, zf = PAL
    for i in range(4):
        box(mb, x0 + 0.004 * i, x1 - 0.004 * i, 0.0125 * i, 0.0125 * (i + 1), zb, zf - 0.016 * i, "dais",
            skip=("bottom",))
    zt = zf - 0.048                                   # the top step's front edge
    box(mb, x0 + 0.016, x1 - 0.016, DAIS_TOP, 0.255, zb, zb + 0.012, "palaceWall", skip=("bottom",))
    for k, x in enumerate(np.linspace(x0 + 0.03, x1 - 0.03, 9)):     # painted frieze panels on the wall (proud)
        box(mb, x - 0.012, x + 0.012, 0.205, 0.240, zb + 0.012, zb + 0.0145, "palaceWall", skip=("back", "bottom"))
    box(mb, 0.335, 0.425, 0.090, 0.200, zb + 0.012, zb + 0.0145, "palaceWall", skip=("back", "bottom"))
    top = 0.0
    for x, z in COLS:
        top = papyrus_column(mb, x, z, DAIS_TOP)
    box(mb, x0 - 0.005, x1 + 0.005, top, top + 0.056, COLS[0][1] - 0.022, COLS[0][1] + 0.022, "lintel")
    box(mb, x0 - 0.010, x1 + 0.010, top + 0.056, top + 0.062, COLS[0][1] - 0.026, COLS[0][1] + 0.026, "lintel")
    box(mb, x0 + 0.010, x1 - 0.010, top, top + 0.030, zb, COLS[0][1] - 0.022, "lintel", skip=("front", "bottom"))
    # the winged sun-disc on the lintel front: disc, two wings (three feather rows), two cobras
    zc = COLS[0][1] + 0.022
    hc = top + 0.028
    lathe(mb, [(0.0, 0.0), (0.0280, 0.0), (0.0272, 0.0026), (0.0, 0.0040)], "gold", C=(0.38, hc, zc), A=(0, 0, 1),
          U=(1, 0, 0), V=(0, 1, 0), seg=24)
    for s in (-1, 1):
        for row, (dh, L, dz) in enumerate(((0.0090, 0.108, 0.0026), (0.0005, 0.094, 0.0020), (-0.0080, 0.076, 0.0014))):
            poly = [(0.022, -0.0062), (L, -0.002 - 0.001 * row), (L + 0.007, 0.0034), (0.022, 0.0066)]
            poly = [(0.38 + s * a, hc + dh + b) for a, b in poly]
            extrude(mb, poly if s > 0 else poly[::-1], zc, zc + dz, "gold", back=False)
        lathe(mb, [(0.0, 0.0), (0.0028, 0.0), (0.0020, 0.010), (0.0, 0.011)], "gold", C=(0.38 + s * 0.0280, hc - 0.004,
                                                                                       zc + 0.002), seg=6)
    # fans: feather semicircles on poles (no-raster: cream and gold texels)
    mb.nr = True
    for fx in (0.318, 0.442):
        fz = THRONE_AT[1] - 0.030
        r = 0.038
        poly = [(fx, 0.185)] + [(fx + r * math.cos(a), 0.200 + r * math.sin(a))
                                for a in np.linspace(math.radians(-15), math.radians(195), 15)]
        extrude(mb, poly[::-1], fz - 0.003, fz + 0.003, "fan")
        for a in np.linspace(math.radians(10), math.radians(170), 7):      # feather ribs
            tube(mb, [(fx, 0.188, fz + 0.0035), (fx + r * 0.95 * math.cos(a), 0.2 + r * 0.95 * math.sin(a),
                                                  fz + 0.0035)], 0.0011, "fan", seg=3, smooth=False)
        tube(mb, [(fx, DAIS_TOP, fz), (fx, 0.190, fz)], 0.0032, "pole", seg=6)
    # fire bowl on a tripod stand, a lick of flame (no-raster: gold + sun texels)
    fx_, fz_ = FIRE
    for k in range(3):
        a = TAU * k / 3 + 0.4
        tube(mb, [(fx_ + 0.016 * math.cos(a), 0.0, fz_ + 0.016 * math.sin(a)), (fx_ + 0.004 * math.cos(a), 0.040,
                                                                                  fz_ + 0.004 * math.sin(a))],
             0.0022, "fireBowl", seg=5)
    lathe(mb, [(0.0, 0.040), (0.008, 0.040), (0.020, 0.052), (0.022, 0.058), (0.019, 0.058), (0.0, 0.054)],
          "fireBowl", C=(fx_, 0, fz_), seg=14)
    for k, (dx, dh, r) in enumerate(((0.0, 0.066, 0.011), (-0.006, 0.076, 0.007), (0.005, 0.080, 0.006))):
        lumpy(mb, (fx_ + dx, dh, fz_), r, "flame", seg=8, rings=5, sh=1.5, amp=0.15, seed=k + 80)
    mb.nr = False
    pal = make_obj("palace", mb, root, origin=(0.38, 0.0, -0.46), smooth_angle=45)
    # throne
    tm = MB()
    tx, tz = THRONE_AT
    h0 = DAIS_TOP
    box(tm, tx - 0.026, tx + 0.026, h0 + 0.026, h0 + 0.037, tz - 0.020, tz + 0.020, "throne")
    for sx in (-1, 1):
        for sz in (-1, 1):
            lx, lz = tx + sx * 0.020, tz + sz * 0.015
            tube(tm, [(lx, h0 + 0.027, lz), (lx, h0 + 0.012, lz + 0.002 * sz), (lx, h0 + 0.004, lz + 0.001),
                      (lx, h0 + 0.0015, lz + 0.004)], [0.0036, 0.003, 0.0032, 0.0038], "throne", seg=6)
    back = [(tx - 0.030, h0 + 0.037), (tx + 0.030, h0 + 0.037), (tx + 0.030, h0 + 0.104)] + \
        [(tx + 0.030 * math.cos(math.pi * k / 8), h0 + 0.104 + 0.016 * math.sin(math.pi * k / 8)) for k in range(1, 8)] + \
        [(tx - 0.030, h0 + 0.104)]
    extrude(tm, back, tz - 0.022, tz - 0.013, "throne")
    for sx in (-1, 1):
        box(tm, tx + sx * 0.026 - 0.004, tx + sx * 0.026 + 0.002 * sx, h0 + 0.037, h0 + 0.056, tz - 0.018, tz + 0.016,
            "throne")
        lumpy(tm, (tx + sx * 0.0245, h0 + 0.058, tz + 0.016), 0.005, "throne", seg=8, rings=5, sh=0.9, amp=0.05)
    lumpy(tm, (tx, h0 + 0.0395, tz - 0.001), 0.019, "throne", seg=12, rings=5, sh=0.16, sz=0.95, amp=0.04)
    throne = make_obj("throne", tm, pal, origin=(tx, h0, tz), smooth_angle=45)
    return pal, throne


# ============================================================================================ granary
STORES = [(0.465, -0.125), (0.552, -0.068), (0.532, 0.030)]
STORE_R, STORE_H = 0.050, 0.160


def store_prof():
    return [(0.0, 0.0), (STORE_R, 0.0), (STORE_R + 0.002, 0.030), (0.048, 0.075), (0.040, 0.110), (0.028, 0.135),
            (0.014, 0.152), (0.0, STORE_H)]


def store_r(h):
    pr = store_prof()
    for (r0, h0), (r1, h1) in zip(pr, pr[1:]):
        if h0 <= h <= h1 and h1 > h0:
            return r0 + (r1 - r0) * (h - h0) / (h1 - h0)
    return 0.0


def build_granary(root):
    """three beehive grain stores of mud brick (printed course lines, a few proud bricks), each with a little
    wooden door low on the front and a hatch at the top; a ladder (wood texel) against the middle store"""
    mb = MB()
    dec = DECOR.setdefault("granary", [])
    rng = random.Random(31)
    for si, (sx, sz) in enumerate(STORES):
        lathe(mb, store_prof(), "mudBrick", C=(sx, 0, sz), seg=24, smooth=True,
              rfun=lambda th, i, k, s=si: 1.0 + 0.012 * math.sin(5 * th + s))
        lathe(mb, [(0.0, STORE_H - 0.004), (0.010, STORE_H - 0.004), (0.011, STORE_H + 0.004), (0.0, STORE_H + 0.006)],
              "storeDoor", C=(sx, 0, sz), seg=12)
        face = math.atan2(0.9, 0.35 if si != 1 else -0.15)        # door direction (toward the camera, a little aside)
        dx, dz = math.cos(face), math.sin(face)
        for pa, ph in ((face - 0.95, 0.072), (face + 0.75, 0.100), (face + 0.15, 0.124)):   # a few bricks (print)
            for k in range(2):
                h = ph + 0.012 * k
                r = store_r(h) + 0.0006
                for j in range(3 - k):
                    a0 = pa + 0.17 * j + 0.085 * k; a1 = a0 + 0.17
                    for (b0, b1) in (((a0, h), (a1, h)), ((a0, h + 0.012), (a1, h + 0.012)), ((a0, h), (a0, h + 0.012)),
                                     ((a1, h), (a1, h + 0.012))):
                        dec.append(((sx + r * math.cos(b0[0]), b0[1], sz + r * math.sin(b0[0])),
                                    (sx + r * math.cos(b1[0]), b1[1], sz + r * math.sin(b1[0]))))
        for k in range(6):                                          # proud bricks here and there
            a = face + rng.uniform(-1.3, 1.3); h = rng.uniform(0.02, 0.11)
            r = store_r(h)
            c = (sx + r * math.cos(a), h, sz + r * math.sin(a))
            t = (-math.sin(a), 0, math.cos(a))
            box_pts = [(c[0] + t[0] * u + math.cos(a) * w, c[1] + v, c[2] + t[2] * u + math.sin(a) * w)
                       for u in (-0.008, 0.008) for v in (-0.004, 0.004) for w in (-0.001, 0.0025)]
            idx = [mb.v(*p) for p in box_pts]
            for q, o in (((1, 3, 7, 5), (math.cos(a), 0, math.sin(a))), ((0, 1, 5, 4), (0, -1, 0)),
                         ((2, 3, 7, 6), (0, 1, 0)), ((0, 2, 6, 4), (-t[0], 0, -t[2])), ((4, 5, 7, 6), (t[0], 0, t[2]))):
                mb.fo([idx[i] for i in q], "mudBrick", o)
        # door: an arched panel standing proud of the wall, with a frame
        r0 = store_r(0.02)
        cx_, cz_ = sx + (r0 + 0.003) * dx, sz + (r0 + 0.003) * dz
        tx, tz = -dz, dx
        door = [(-0.024, 0.004), (0.024, 0.004), (0.024, 0.046)] + \
            [(0.024 * math.cos(math.pi * k / 8), 0.046 + 0.020 * math.sin(math.pi * k / 8)) for k in range(1, 8)] + \
            [(-0.024, 0.046)]
        lean = 0.10
        P0 = [mb.v(cx_ + tx * a - dx * lean * b, b, cz_ + tz * a - dz * lean * b) for a, b in door]
        P1 = [mb.v(cx_ + tx * a + dx * (0.004 - lean * b), b, cz_ + tz * a + dz * (0.004 - lean * b)) for a, b in door]
        for t in tessellate_polygon([[Vector((a, b, 0)) for a, b in door]]):
            mb.fo([P1[i] for i in t], "storeDoor", (dx, 0, dz))
        for i in range(len(door)):
            j = (i + 1) % len(door)
            mb.fo([P0[i], P0[j], P1[j], P1[i]], "storeDoor", (tx * (door[i][0] + door[j][0]), 0.5, tz * (door[i][0] + door[j][0])))
        for b in (0.018, 0.040):                                     # planks: two battens
            bb = [mb.v(cx_ + tx * a + dx * (0.0052 - lean * b), b + db, cz_ + tz * a + dz * (0.0052 - lean * b))
                  for a, db in ((-0.021, -0.002), (0.021, -0.002), (0.021, 0.002), (-0.021, 0.002))]
            mb.fo(bb, "storeDoor", (dx, 0, dz))
    # ladder against the middle store (wood texel)
    mb.nr = True
    lx, lz = STORES[1][0] - 0.052, STORES[1][1] + 0.040
    topx, topz = STORES[1][0] - 0.020, STORES[1][1] + 0.016
    for s in (-1, 1):
        tube(mb, [(lx + s * 0.010 * 0.6, 0.0, lz + s * 0.010 * 0.8), (topx + s * 0.010 * 0.6, 0.150, topz + s * 0.010 * 0.8)],
             0.0022, "ladder", seg=5)
    for k in range(1, 9):
        u = k / 9
        px, ph, pz = lx + (topx - lx) * u, 0.150 * u, lz + (topz - lz) * u
        tube(mb, [(px - 0.006, ph, pz - 0.008), (px + 0.006, ph, pz + 0.008)], 0.0016, "ladder", seg=4)
    mb.nr = False
    return make_obj("granary", mb, root, origin=(0.50, 0.0, -0.04), smooth_angle=50)


def build_grain_piles(root, heaps, baskets):
    """golden grain heaps and full baskets between and behind the stores (named texels: dreamGrain fat ears, the
    caravan's bundle)"""
    mb = MB(); mb.nr = True
    for k, (x, z, r) in enumerate(heaps):
        lathe(mb, [(0.0, 0.0), (r, 0.0), (r * 0.82, r * 0.28), (r * 0.5, r * 0.6), (r * 0.18, r * 0.78), (0.0, r * 0.82)],
              "grain", C=(x, 0, z), seg=14, rfun=lambda th, i, kk, s=k: 1.0 + 0.06 * math.sin(3 * th + s))
    for k, (x, z) in enumerate(baskets):
        lathe(mb, [(0.0, 0.0), (0.012, 0.0), (0.017, 0.016), (0.018, 0.026), (0.016, 0.026), (0.0, 0.006)], "basket",
              C=(x, 0, z), seg=12)
        lumpy(mb, (x, 0.026, z), 0.0155, "grain", seg=10, rings=5, sh=0.5, amp=0.08, seed=k + 90)
    cx = sum(h[0] for h in heaps) / len(heaps); cz = sum(h[1] for h in heaps) / len(heaps)
    return make_obj("grainPiles", mb, root, origin=(round(cx, 3), 0.0, round(cz, 3)), smooth_angle=60)


def build_sacks(root, spots):
    """three tied grain sacks (named texels: the caravan's bundle, a wood tie)"""
    mb = MB(); mb.nr = True
    for k, (x, z) in enumerate(spots):
        lumpy(mb, (x, 0.020, z), 0.019, "sack", seg=12, rings=7, sh=1.15, sx=0.95, amp=0.07, seed=k + 70,
              flat_bottom=0.0)
        lathe(mb, [(0.0, 0.038), (0.0085, 0.038), (0.0062, 0.044), (0.0, 0.045)], "tie", C=(x, 0, z), seg=10)
        lumpy(mb, (x, 0.050, z), 0.0085, "sack", seg=8, rings=5, sh=0.8, amp=0.25, seed=k + 75)
    cx = sum(s[0] for s in spots) / len(spots); cz = sum(s[1] for s in spots) / len(spots)
    return make_obj("sacks", mb, root, origin=(round(cx, 3), 0.0, round(cz, 3)), smooth_angle=60)


# ============================================================================================ cell
CELL_X0, CELL_X1, CELL_ZB, CELL_ZF = 0.02, 0.18, -0.14, -0.04     # sides stop 0.06 short: the +z side is open
CELL_H = 0.20
BENCH = (0.10, -0.103, 0.062)                                       # centre x, centre z, top h


def build_cell(root):
    """the prison cell: a cage of square wooden bars (back and two sides, open toward the viewer and on top), rails at
    the foot and the top, corner posts; child `cellBench`: a stone bench behind Joseph's mark and a clay jug.
    No drawing: wood / stone / clay texels."""
    mb = MB(); mb.nr = True
    for x, z in ((CELL_X0, CELL_ZB), (CELL_X1, CELL_ZB), (CELL_X0, CELL_ZF), (CELL_X1, CELL_ZF)):
        box(mb, x - 0.0055, x + 0.0055, 0.0, CELL_H + 0.006, z - 0.0055, z + 0.0055, "wood")
    for h0, h1 in ((0.0, 0.011), (CELL_H - 0.012, CELL_H)):
        box(mb, CELL_X0, CELL_X1, h0, h1, CELL_ZB - 0.004, CELL_ZB + 0.004, "wood")
        for x in (CELL_X0, CELL_X1):
            box(mb, x - 0.004, x + 0.004, h0, h1, CELL_ZB, CELL_ZF, "wood")
    for x in np.arange(CELL_X0 + 0.020, CELL_X1 - 0.010, 0.020):
        box(mb, x - 0.0032, x + 0.0032, 0.011, CELL_H - 0.012, CELL_ZB - 0.0032, CELL_ZB + 0.0032, "wood")
    for x in (CELL_X0, CELL_X1):
        for z in np.arange(CELL_ZB + 0.020, CELL_ZF - 0.008, 0.020):
            box(mb, x - 0.0032, x + 0.0032, 0.011, CELL_H - 0.012, z - 0.0032, z + 0.0032, "wood")
    cell = make_obj("cell", mb, root, origin=(CELL[0], 0.0, CELL[1]), smooth_angle=40, bevel=0.0007)
    bm = MB(); bm.nr = True
    bx, bz, bh = BENCH
    box(bm, bx - 0.050, bx + 0.050, bh - 0.012, bh, bz - 0.018, bz + 0.018, "bench")
    for s in (-1, 1):
        box(bm, bx + s * 0.036 - 0.009, bx + s * 0.036 + 0.009, 0.0, bh - 0.012, bz - 0.014, bz + 0.014, "bench")
    jx, jz = 0.040, -0.122
    lathe(bm, [(0.0, 0.0), (0.008, 0.0), (0.013, 0.012), (0.012, 0.024), (0.006, 0.032), (0.0065, 0.036),
               (0.0, 0.034)], "jug", C=(jx, 0, jz), seg=12)
    tube(bm, [(jx + 0.006, 0.033, jz), (jx + 0.016, 0.030, jz), (jx + 0.012, 0.018, jz)], 0.0017, "jug", seg=5)
    bench = make_obj("cellBench", bm, cell, origin=(bx, 0.0, bz), smooth_angle=40, bevel=0.0008)
    return cell, bench


# ============================================================================================ palms
PALMS = [(0.580, -0.262, 1.0, 0.4), (0.140, -0.445, 0.94, 2.1)]


def palm_template(H=0.360):
    """a date palm (local, base at the origin): a curved ringed trunk, a crown of ten drooping fronds (lowest tip
    >= 0.28 in every instance), two date clusters (no-raster). After ex_egypt.palm_template, taller."""
    mb = MB(); mb.nr = True
    rng = random.Random(4)
    axis = lambda u: (0.014 * math.sin(1.5 * u) * u, H * u, 0.004 * u * u)
    rings = 20
    prof = []
    for i in range(rings + 1):
        u = i / rings
        r = 0.0085 * (1.25 - 0.35 * u) * (1.0 + (0.13 if i % 2 else 0.0)) + (0.005 * (1 - u / 0.1) if u < 0.1 else 0)
        prof.append((r, u))
    tube(mb, [axis(u) for _, u in prof], [r for r, _ in prof], "palmTrunk", seg=8)
    top = Vector(axis(1.0))
    for k in range(10):
        a = TAU * k / 10 + rng.uniform(-0.15, 0.15)
        d = Vector((math.cos(a), 0, math.sin(a)))
        up = 0.6 if k % 2 else 0.3
        L = rng.uniform(0.080, 0.092)
        P = [top + d * (L * t) + Vector((0, L * (up * t - (up + 0.45) * t * t), 0)) for t in np.linspace(0, 1, 7)]
        side = d.cross(Vector((0, 1, 0)))
        W = [0.006, 0.026, 0.032, 0.030, 0.024, 0.013, 0.0]
        Lf, Rt = [], []
        for i, p in enumerate(P):
            wv = W[i] / 2 * (1.0 + (0.3 if i % 2 else -0.12))
            dr = Vector((0, -0.006 * (i / 6), 0))
            Lf.append(mb.v(*(p - side * wv + dr))); Rt.append(mb.v(*(p + side * wv + dr)))
        mids = [mb.v(*p) for p in P]
        for i in range(6):
            for sgn in (1, -1):
                mb.fo([mids[i], Lf[i], Lf[i + 1], mids[i + 1]], "palmFrond", (0, sgn, 0))
                mb.fo([mids[i], mids[i + 1], Rt[i + 1], Rt[i]], "palmFrond", (0, sgn, 0))
    lumpy(mb, tuple(top + Vector((0, 0.004, 0))), 0.013, "palmFrond", seg=10, rings=6, sh=0.8, amp=0.1)
    for k in range(2):
        a = TAU * k / 2 + 0.6
        c = top + Vector((0.011 * math.cos(a), -0.014, 0.011 * math.sin(a)))
        lumpy(mb, tuple(c), 0.008, "dates", seg=8, rings=5, sh=1.3, amp=0.18, seed=k)
    return mb


def build_palms(root, tpl):
    mb = MB()
    for x, z, s, yaw in PALMS:
        mb.add(tpl, yaw_fn(x, z, yaw, s))
    return make_obj("palms", mb, root, origin=(PALMS[0][0], 0.0, PALMS[0][1]), smooth_angle=55)


# ============================================================================================ dream panels
DREAMS = {   # node: (template, centre x, h, z, width, height)
    "dreamSheaves": ("dreamSheaves", -0.32, 0.46, -0.16, 0.22, 0.135),
    "dreamStars": ("dreamStars", -0.32, 0.46, -0.16, 0.22, 0.135),
    "dreamSheaves2": ("dreamSheaves", 0.30, 0.50, 0.06, 0.22, 0.135),
    "dreamCows": ("dreamCows", 0.30, 0.52, -0.26, 0.24, 0.140),
    "dreamGrain": ("dreamGrain", 0.30, 0.52, -0.26, 0.24, 0.140),
}


def cloud_frame(mb, W, H, sky):
    """puffy white cloud ring round a sky panel (local, facing +z): small scallops along the edges, big puffs at
    the four corners (they give the cloud a colourable 6 mm cell on paper)"""
    hw, hh = W / 2, H / 2
    base = rrect(0.0, 0.0, hw - 0.008, hh - 0.008, 0.024, n=6)
    pts = _resample(np.array(base), 0.0025)
    L = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(pts, axis=0, append=pts[:1]), axis=1))])[:-1]
    outer = []
    for p, s in zip(pts, L):
        n = p / (np.linalg.norm(p) + 1e-9)
        corner = min(1.0, max(0.0, (abs(p[0]) - (hw - 0.050)) / 0.022)) * \
            min(1.0, max(0.0, (abs(p[1]) - (hh - 0.050)) / 0.022))
        bump = 0.0065 * abs(math.sin(math.pi * s / 0.030)) + 0.019 * corner
        outer.append(tuple(p + n * bump))
    hole = rrect(0.0, 0.0, hw - 0.020, hh - 0.020, 0.030, n=6)
    puff2(mb, outer, [hole[::-1]], 0.0030, 0.0055, "cloud", rad=0.010, edge=0.35, step=0.011)
    extrude(mb, rrect(0.0, 0.0, hw - 0.015, hh - 0.015, 0.030, n=6), -0.0035, -0.0005, sky, back=True)
    return hw - 0.020, hh - 0.020


def sheaf_poly(W, H, waist=0.24):
    """a sheaf of grain standing on its base (0, 0): flared foot, tied waist, a fan of ears at the top"""
    half = [(0.50, 0.0), (0.30 + (waist - 0.24) * 0.6, 0.20), (waist, 0.42), (0.40, 0.62), (0.58, 0.80), (0.52, 0.93),
            (0.30, 1.00), (0.10, 1.04), (0.0, 1.05)]
    right = [(W * a, H * b) for a, b in half]
    left = [(-x, y) for x, y in right[::-1][1:]]
    return right + left[:-1] + [(-W * 0.5, 0.0)]


def tpl_dream_sheaves(W=0.22, H=0.135):
    """Joseph's first dream: one tall sheaf standing up, eleven smaller sheaves bowing to it from both sides"""
    mb = MB()
    iw, ih = cloud_frame(mb, W, H, "daySky")
    base = -ih + 0.002
    big = sheaf_poly(0.050, 0.090)
    relief(mb, xform(big, 0.0, base), 0.003, 0.0165, "sheafBig")          # the tall sheaf stands in front
    relief(mb, [(-0.014, base + 0.033), (0.014, base + 0.033), (0.014, base + 0.043), (-0.014, base + 0.043)],
           0.0165, 0.0185, "sheafBig")
    for x in (-0.010, -0.0035, 0.0035, 0.010):
        relief(mb, [(x - 0.0007, base + 0.003), (x + 0.0007, base + 0.003), (x + 0.0007, base + 0.031),
                    (x - 0.0007, base + 0.031)], 0.0165, 0.0178, "sheafBig")
    small = sheaf_poly(0.036, 0.054, waist=0.36)
    dec = DECOR.setdefault("dreamSheaves", [])
    rows = [(-1, -0.052, 0.006, 0.0015), (-1, -0.074, 0.006, 0.0015), (1, 0.052, 0.006, 0.0015),
            (1, 0.074, 0.006, 0.0015), (1, 0.094, 0.006, 0.0015),                      # back row, raised
            (-1, -0.042, 0.0, 0.0085), (-1, -0.063, 0.0, 0.0085), (-1, -0.084, 0.0, 0.0085),
            (1, 0.042, 0.0, 0.0085), (1, 0.063, 0.0, 0.0085), (1, 0.084, 0.0, 0.0085)]  # front row
    for side, x, dy, z0 in rows:
        ang = side * math.radians(36 + 150 * (abs(x) - 0.042))       # bowing toward the tall sheaf
        poly = xform(small, x, base + dy, ang)
        relief(mb, poly, z0, z0 + 0.0040, "sheafSmall")
        n = len(poly)
        for i in range(n):                                          # printed: each sheaf's head (ears)
            if small[i][1] > 0.72 * 0.054 and small[(i + 1) % n][1] > 0.72 * 0.054:
                p0, p1 = poly[i], poly[(i + 1) % n]
                dec.append(((p0[0], p0[1], z0 + 0.0040), (p1[0], p1[1], z0 + 0.0040)))
    return mb


def tpl_dream_stars(W=0.22, H=0.135):
    """Joseph's second dream: a smiling sun, a crescent moon and eleven stars"""
    mb = MB()
    iw, ih = cloud_frame(mb, W, H, "nightSky")
    sx, sy = -0.046, -0.002
    relief(mb, star_poly(sx, sy, 0.045, 0.034, n=10, rot=0.1), 0.0005, 0.0045, "sun")
    relief(mb, ell(sx, sy, 0.034, 0.034, 32), 0.0045, 0.0085, "sun")
    dec = DECOR.setdefault("dreamStars", [])
    circ = ell(sx, sy, 0.0342, 0.0342, 40)
    dec += [((circ[i][0], circ[i][1], 0.0085), (circ[(i + 1) % 40][0], circ[(i + 1) % 40][1], 0.0085)) for i in range(40)]
    for ex in (-0.008, 0.008):
        relief(mb, ell(sx + ex, sy - 0.008, 0.0022, 0.0030, 10), 0.0085, 0.0100, "sun")
        e = ell(sx + ex, sy - 0.008, 0.0024, 0.0032, 8)
        dec += [((e[i][0], e[i][1], 0.0100), (e[(i + 1) % 8][0], e[(i + 1) % 8][1], 0.0100)) for i in range(8)]
    smile = [(sx + 0.009 * math.cos(a), sy - 0.014 + 0.009 * math.sin(a)) for a in np.linspace(math.radians(205),
                                                                                             math.radians(335), 9)]
    dec += [((smile[i][0], smile[i][1], 0.0100), (smile[i + 1][0], smile[i + 1][1], 0.0100)) for i in range(8)]
    smile = smile + [(sx + 0.0068 * math.cos(a), sy - 0.014 + 0.0068 * math.sin(a)) for a in
                     np.linspace(math.radians(335), math.radians(205), 9)]
    relief(mb, smile, 0.0085, 0.0100, "sun")
    mx, my, R = 0.054, 0.000, 0.040
    ts = np.linspace(-math.pi / 2, math.pi / 2, 19)
    moon = [(-R * math.cos(t), R * math.sin(t)) for t in ts] + [(-0.05 * R * math.cos(t) + 0.004, R * 0.92 * math.sin(t))
                                                               for t in ts[::-1]]
    relief(mb, xform(moon, mx, my, math.radians(-20)), 0.0005, 0.0075, "moon")
    stars = [(-0.001, 0.034), (0.010, 0.017), (0.000, -0.002), (0.010, -0.020), (-0.002, -0.036), (-0.088, 0.034),
             (-0.088, -0.034), (0.088, 0.036), (0.088, -0.036), (0.072, 0.040), (0.073, -0.041)]
    for k, (x, y) in enumerate(stars):
        relief(mb, star_poly(x, y, 0.0100, 0.0050, rot=0.2 * k), 0.0005, 0.0045, "moon")
    return mb


def cow_parts(cx, cy, fat, reg, z0):
    """a cartoon cow walking right (+a): body, head with horns, four legs, tail; parts stacked in depth"""
    rx, ry = (0.025, 0.0190) if fat else (0.024, 0.0152)
    out = []
    lw = 0.0070 if fat else 0.0050
    for lx in (-0.017, -0.011, 0.011, 0.017):
        top = cy - ry * 0.4
        out.append(([(cx + lx - lw / 2, cy - 0.030), (cx + lx + lw / 2, cy - 0.030), (cx + lx + lw / 2, top),
                     (cx + lx - lw / 2, top)], z0 + 0.0005, z0 + 0.0040))
    out.append(([(cx - rx * 0.95, cy + 0.002), (cx - rx - 0.008, cy - 0.013), (cx - rx - 0.005, cy - 0.014),
                 (cx - rx * 0.85, cy - 0.002)], z0 + 0.0005, z0 + 0.0040))
    if fat:
        body = ell(cx, cy, rx, ry, 24)
    else:                                              # bony: a sunken belly, hips and shoulders standing out
        body = []
        for k in range(24):
            t = TAU * k / 24
            y = ry * math.sin(t)
            if math.sin(t) < 0:
                y *= 0.80 + 0.20 * abs(math.cos(t)) ** 2
            else:
                y *= 1.0 + 0.22 * abs(math.cos(2 * t))
            body.append((cx + rx * math.cos(t), cy + y))
    out.append((body, z0 + 0.0005, z0 + 0.0080))
    hx, hy = cx + rx + 0.007, cy + 0.009
    out.append((ell(hx, hy, 0.0105 if fat else 0.0095, 0.0088 if fat else 0.0074, 16, rot=-0.35), z0 + 0.0005,
                z0 + 0.0085))
    for s in (-1, 1):
        out.append(([(hx - 0.002 + s * 0.004, hy + 0.006), (hx + s * 0.010, hy + 0.013), (hx + s * 0.0105, hy + 0.0115),
                     (hx + 0.001 + s * 0.004, hy + 0.0045)], z0 + 0.0005, z0 + 0.0040))
    return [(p, a, b, reg) for p, a, b in out]


def tpl_dream_cows(W=0.24, H=0.140):
    """Pharaoh's first dream: three fat cows (brown, cream, brown) and three skinny cows walking up out of the
    river (the narrator says seven)"""
    mb = MB()
    iw, ih = cloud_frame(mb, W, H, "cloud")
    river = [(-iw - 0.004, -ih - 0.004), (iw + 0.004, -ih - 0.004)] + \
        [(x, -ih + 0.047 + 0.0035 * math.sin(70 * x + 1)) for x in np.linspace(iw + 0.004, -iw - 0.004, 26)]
    relief(mb, river, -0.0005, 0.0015, "river")
    for k, y in enumerate((-ih + 0.010, -ih + 0.020)):           # ripples (creases)
        tube(mb, [(x, y + 0.002 * math.sin(90 * x + k), 0.0018) for x in np.linspace(-iw + 0.004, iw - 0.004, 30)],
             0.0009, "river", seg=3, smooth=False, caps=False)
    for k, (x, y, reg) in enumerate(((-0.086, 0.008, "cowFat"), (-0.056, 0.020, "cowFat"), (-0.026, 0.010, "cowCream"))):
        for poly, a, b, r in cow_parts(x, y, True, reg, 0.0012 + 0.0048 * k):
            relief(mb, poly, a, b, r)
    for k, (x, y) in enumerate(((0.018, 0.010), (0.048, 0.021), (0.078, 0.010))):
        z0 = 0.0012 + 0.0048 * k
        for poly, a, b, r in cow_parts(x, y, False, "cowThin", z0):
            relief(mb, poly, a, b, r)
    return mb


def ear_poly(L, w, n=8):
    """a grain ear from its foot (0, 0) up the +b axis: kernels as a wavy outline"""
    right = [(w * (0.5 + 0.18 * math.sin(math.pi * 2 * n * t / 2)) * math.sin(math.pi * min(1.0, t * 1.15)) + 0.0004,
              L * t) for t in np.linspace(0, 1, 2 * n + 1)]
    left = [(-x, y) for x, y in right[::-1]]
    return right + left[1:-1]


def ear_tips(ep, cx, cy, ang, z, above):
    """printed outline of an ear's upper part (the ears fuse into one colouring shape lower down)"""
    poly = xform(ep, cx, cy, ang)
    n = len(ep)
    for i in range(n):
        if ep[i][1] > above and ep[(i + 1) % n][1] > above:
            DECOR.setdefault("dreamGrain", []).append(((poly[i][0], poly[i][1], z), (poly[(i + 1) % n][0],
                                                                                     poly[(i + 1) % n][1], z)))


def tpl_dream_grain(W=0.24, H=0.140):
    """Pharaoh's second dream: a stalk with fat ears and a stalk with thin, drooping ears"""
    mb = MB()
    iw, ih = cloud_frame(mb, W, H, "cloud")
    meadow = [(-iw - 0.004, -ih - 0.004), (iw + 0.004, -ih - 0.004)] + \
        [(x, -ih + 0.030 + 0.003 * math.sin(55 * x)) for x in np.linspace(iw + 0.004, -iw - 0.004, 22)]
    relief(mb, meadow, -0.0005, 0.0015, "meadow")
    # two stalks: stems and leaves belong to the meadow (one region with the ground)
    for sx, lean, droop in ((-0.044, 0.10, 0.0), (0.046, 0.12, 1.0)):
        stem = [(sx - 0.0032, -ih + 0.010), (sx + 0.0032, -ih + 0.010), (sx + 0.0032 + lean * 0.06, 0.016 - 0.012 * droop),
                (sx - 0.0032 + lean * 0.06, 0.016 - 0.012 * droop)]
        relief(mb, stem, 0.0012, 0.0040, "meadow")
        for s, hy in ((-1, -0.026), (1, -0.012)):
            leaf = [(sx, hy), (sx + s * 0.020, hy + 0.013 - 0.010 * droop), (sx + s * 0.033, hy + 0.011 - 0.018 * droop),
                    (sx + s * 0.018, hy + 0.006 - 0.006 * droop), (sx, hy + 0.004)]
            relief(mb, leaf if s > 0 else leaf[::-1], 0.0012, 0.0040, "meadow")
    fx, fy = -0.044 + 0.006, -0.010
    for k, ang in enumerate((-0.24, 0.24, 0.0)):                     # seven fat ears (three drawn): long and plump
        ep = ear_poly(0.050, 0.024, 9)
        z1 = 0.0080 + 0.0012 * k
        relief(mb, xform(ep, fx, fy, ang), 0.0040 + 0.0012 * k, z1, "earFat")
        ear_tips(ep, fx, fy, ang, z1, 0.62 * 0.050)
        for j, t in enumerate((0.30, 0.48, 0.66, 0.84)):            # kernels: chevrons up the ear
            v = xform([(-0.0065, 0.050 * t - 0.004), (0.0, 0.050 * t), (0.0065, 0.050 * t - 0.004)], fx, fy, ang)
            tube(mb, [(q[0], q[1], z1 + 0.0004) for q in v], 0.0009, "earFat", seg=3, smooth=False, caps=False)
            if t > 0.8:
                DECOR.setdefault("dreamGrain", []).extend([((v[0][0], v[0][1], z1), (v[1][0], v[1][1], z1)),
                                                           ((v[1][0], v[1][1], z1), (v[2][0], v[2][1], z1))])
        tip = xform([(0.0, 0.050)], fx, fy, ang)[0]
        for da in (-0.22, 0.0, 0.22):                                # awns
            blade(mb, [(tip[0], tip[1], z1), (tip[0] - 0.017 * math.sin(ang + da), tip[1] + 0.017 * math.cos(ang + da),
                                              z1)], [0.0015, 0.0], "earFat", nrm=(0, 0, 1))
    relief(mb, ell(fx, fy + 0.006, 0.0150, 0.0145, 20), 0.0040, 0.0090, "earFat")
    tx, ty = 0.046 + 0.006, -0.004
    for k, ang in enumerate((-2.05, -2.45, -1.65)):                  # thin ears: limp, hanging over to the right
        ep = ear_poly(0.044, 0.0080, 7)
        z1 = 0.0075 + 0.0012 * k
        relief(mb, xform(ep, tx, ty, ang), 0.0040 + 0.0012 * k, z1, "earThin")
        tip = xform([(0.0, 0.044)], tx, ty, ang)[0]
        blade(mb, [(tip[0], tip[1], z1), (tip[0] - 0.012 * math.sin(ang), tip[1] + 0.012 * math.cos(ang), z1)],
              [0.0012, 0.0], "earThin", nrm=(0, 0, 1))
    relief(mb, ell(tx - 0.002, ty + 0.002, 0.0172, 0.0155, 18), 0.0040, 0.0085, "earThin")
    return mb


DREAM_TPL = {"dreamSheaves": tpl_dream_sheaves, "dreamStars": tpl_dream_stars, "dreamCows": tpl_dream_cows,
             "dreamGrain": tpl_dream_grain}


def build_dreams(root, tpls):
    out = {}
    for node, (tp, x, h, z, w, hh) in DREAMS.items():
        mb = MB()
        mb.add(tpls[tp], tilt_fn(x, h, z))
        out[node] = make_obj(node, mb, root, origin=(x, h, z), smooth_angle=50)
    return out


# ============================================================================================ drawings / UV
def _chars_proposal():
    """sheet slots (CONTRACT §2): three at the bottom line, Jacob on a second row above Joseph; boxes estimated
    until the Characters role's regions_characters.json gives the printed ones"""
    return {"joseph": {"sheetX": -0.34, "sheetY": 0.015, "height": 0.34, "box": [-0.465, 0.015, -0.215, 0.360]},
            "brother": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.38, "box": [-0.135, 0.015, 0.135, 0.400]},
            "pharaoh": {"sheetX": 0.34, "sheetY": 0.015, "height": 0.45, "box": [0.205, 0.015, 0.475, 0.470]},
            "jacob": {"sheetX": -0.34, "sheetY": 0.44, "height": 0.33, "box": [-0.465, 0.440, -0.215, 0.775]}}


def _chars():
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    rc = json.load(open(p))
    got = {c: {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"],
               "height": v.get("height", prop.get(c, {}).get("height", 0.3)), "box": v["bboxSheet"]}
           for c, v in rc["characters"].items() if c in rc.get("sheet", {}) and v.get("bboxSheet")}
    for c, v in prop.items():
        got.setdefault(c, v)
    return got, all(c in rc.get("characters", {}) for c in prop)


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
DRAWINGS = {   # cx, y0 = centre-x and bottom of the drawing's bbox on the sheet (x -0.5..0.5, y 0..1.227)
    # top row: the backdrop and Joseph's two dreams; row 2: Canaan then Egypt; middle column: Pharaoh's dreams
    # (between Jacob on the second row and the palace above Pharaoh)
    "horizon":      dict(P_FRONT(), scale=3.03, cx=-0.278, y0=1.118, members=["horizon"], decorOnly=["hills"]),
    "dreamSheaves": dict(P_FRONT(), scale=0.97, cx=0.071, y0=1.062, members=[], decorOnly=["sheafSmall"]),
    "dreamStars":   dict(P_FRONT(), scale=0.97, cx=0.344, y0=1.062, members=[], decorOnly=["sun"]),
    "sheep":        dict(P_FRONT(), scale=0.72, cx=-0.167, y0=0.988, members=[]),
    "tent":         dict(P_OBL(0.30, 0.50), scale=1.45, cx=-0.370, y0=0.829, members=["tent"]),
    "pit":          dict(P_OBL(0.0, 0.62), scale=1.30, cx=-0.160, y0=0.829, members=["pit"], decorOnly=["wellStone"]),
    "olive":        dict(P_FRONT(), scale=1.60, cx=-0.005, y0=0.829, members=["olive"], decorOnly=["oliveCrown"]),
    "caravan":      dict(P_FRONT(), scale=1.00, cx=0.175, y0=0.829, members=["caravan"]),
    "granary":      dict(P_OBL(0.25, 0.45), scale=1.20, cx=0.385, y0=0.829, members=["granary"],
                         decorOnly=["mudBrick"]),
    "palace":       dict(P_OBL(0.0, 0.42), scale=1.28, cx=0.340, y0=0.490, members=["palace", "throne"]),
    "dreamCows":    dict(P_FRONT(), scale=0.76, cx=-0.015, y0=0.413, members=[]),
    "dreamGrain":   dict(P_FRONT(), scale=0.76, cx=-0.015, y0=0.621, members=[], decorOnly=["earFat", "earThin"]),
}
TEMPLATES = {"sheep": ("sheep",), "dreamSheaves": ("dreamSheaves", "dreamSheaves2"),
             "dreamStars": ("dreamStars",), "dreamCows": ("dreamCows",), "dreamGrain": ("dreamGrain",)}
CONSTS = {
    "ground": {"pasture": ("horizon", "hills"), "sand": ("horizon", "desert"), "dunes": ("horizon", "dunes"),
               "road": ("horizon", "dunes"), "tuft": ("horizon", "hills"), "stone": ("pit", "wellStone"),
               "rock": ("horizon", "pyramid")},
    "tent": {"pole": ("olive", "oliveTrunk"), "clay": ("tent", "rug")},
    "pit": {"wellDark": ("tent", "tentB")},
    "sheep": {"sheepFace": ("sheep", "sheepFace")},
    "bucket": {"bucket": ("olive", "oliveTrunk"), "rope": ("caravan", "bundle")},
    "caravan": {"traderRobe": ("caravan", "saddleBlue"), "traderFace": ("caravan", "camel"),
                "traderHood": ("caravan", "bundle"), "rope": ("caravan", "bundle")},
    "palace": {"pole": ("palace", "gold"), "fan": ("palace", "columnCream"), "fireBowl": ("palace", "gold"),
               "flame": ("dreamStars", "sun")},
    "granary": {"ladder": ("granary", "storeDoor")},
    "grainPiles": {"grain": ("dreamGrain", "earFat"), "basket": ("caravan", "bundle")},
    "sacks": {"sack": ("caravan", "bundle"), "tie": ("granary", "storeDoor")},
    "cell": {"wood": ("granary", "storeDoor")},
    "cellBench": {"bench": ("pit", "wellStone"), "jug": ("tent", "rug")},
    "palms": {"palmFrond": ("olive", "oliveCrown"), "palmTrunk": ("olive", "oliveTrunk"), "dates": ("tent", "tentA")},
}
RS = [1]


def fix_faces(objs, idb, regname, crease):
    """faces nearly edge-on to their drawing's view (|n . d| < 0.22, n from P) take a clean texel deep inside their
    own region; no-raster faces take their named texel (CONSTS). As pipeline/ru_bethlehem.py."""
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
                    nn += np.cross(Q[i], Q[(i + 1) % len(Q)])
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
                       "written by pipeline/js_twolands.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)
    return const


# ============================================================================================ checks
def check_clearance(objs):
    """CONTRACT §6: nothing above 0.012 within 0.05 of a mark or on a straight walk between consecutive marks of one
    actor. Overhead parts (olive crown, palm fronds, dream panels) only need head room: between 0.17 and the actor's
    head + 0.03 they must stay 0.035 from the walk line, above that they are ignored. Hidden props count only while
    the timeline shows them; the well wall (Joseph into and out of the well) and the cell bench (Joseph sitting) are
    the contract's two allowed exceptions."""
    pts = {}
    for name, ob in objs.items():
        if ob.type == 'MESH':
            pts[name] = np.array(world_verts(ob))
    hard, soft, closest = {}, {}, {}
    for it in ITEMS:
        top = ACTOR_H[it["who"]] + 0.03
        ax, az = it["a"]; bx, bz = it["b"]
        bad, near = {}, 9.0
        for name, P in pts.items():
            node = NODE_OF.get(name, name)
            if node in HIDDEN and not visible_during(node, it["win"]):
                continue
            if exempt(it, name):
                continue
            X, Hh, Z = P[:, 0], P[:, 1], P[:, 2]
            dx, dz = bx - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
            t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
            d = np.hypot(X - ax - t * dx, Z - az - t * dz)
            low = (Hh > 0.012) & (Hh < 0.17)
            if low.any():
                near = min(near, float(d[low].min()))
            sel = (low & (d < 0.05)) | ((Hh >= 0.17) & (Hh < top) & (d < 0.035))
            if sel.any():
                bad[name] = [round(float(Hh[sel].max()), 4), round(float(d[sel].min()), 4)]
        closest[it["label"]] = round(near, 4)
        if bad:
            (hard if it["hard"] else soft)[it["label"]] = bad
    return hard, soft, closest


# ============================================================================================ build
STATE = {}
ORDER = ["ground", "horizon", "tent", "sheep", "olive", "pit", "bucket", "caravan", "palace", "throne", "granary",
         "grainPiles", "sacks", "cell", "cellBench", "palms", "dreamSheaves", "dreamStars", "dreamSheaves2",
         "dreamCows", "dreamGrain"]


def place_props():
    """free spots (clear of every hard mark and walk) for the loose props near their CONTRACT places"""
    sp = {}
    sp["bucket"] = pick_spot(-0.215, 0.150, 0.045, avoid=[(WELL[0], WELL[1], WELL_RO + 0.005)])
    sp["caravan"] = pick_spot(-0.48, 0.030, 0.06, shape=CAMEL_SHAPE, node="caravan", avoid=[(WELL[0], WELL[1], WELL_RO + 0.006),
                                                                         (OLIVE[0], OLIVE[1], 0.040)])
    stores = [(x, z, STORE_R + 0.004) for x, z in STORES]
    heaps = []
    for (tx, tz, r) in ((0.505, -0.010, 0.030), (0.410, -0.205, 0.034), (0.585, -0.165, 0.022), (0.395, -0.150, 0.026),
                        (0.585, -0.010, 0.020)):
        try:
            x, z = pick_spot(tx, tz, r, rmax=0.06, avoid=stores + [(a, b, c + 0.003) for a, b, c in heaps] +
                             [(PALMS[0][0], PALMS[0][1], 0.02)])
        except SystemExit:                      # no room left near this target: the heap is left out
            continue
        heaps.append((x, z, r))
    assert len(heaps) >= 2, heaps
    sp["heaps"] = heaps
    baskets = []
    for tx, tz in ((0.590, 0.085), (0.480, -0.215)):
        x, z = pick_spot(tx, tz, 0.019, rmax=0.06, avoid=stores + [(a, b, c + 0.004) for a, b, c in heaps] +
                         [(a, b, 0.022) for a, b in baskets])
        baskets.append((x, z))
    sp["baskets"] = baskets
    sacks = []
    for tx, tz in ((0.300, 0.180), (0.335, 0.170), (0.318, 0.150)):
        x, z = pick_spot(tx, tz, 0.020, rmax=0.08, avoid=[(a, b, 0.040) for a, b in sacks] + stores)
        sacks.append((x, z))
    sp["sacks"] = sacks
    return sp


def mode_build():
    sp = place_props()
    print("SPOTS", json.dumps(sp))
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = link(bpy.data.objects.new("twolands", None))
    objs = {}
    objs["ground"], scatter = build_ground(root)
    objs["horizon"] = build_horizon(root)
    objs["tent"] = build_tent(root)
    sheep_tpl = sheep_template()
    objs["sheep"] = build_sheep(root, sheep_tpl)
    objs["olive"] = build_olive(root)
    objs["pit"], objs["bucket"] = build_pit(root, sp["bucket"])
    objs["caravan"] = build_caravan(root, sp["caravan"])
    objs["palace"], objs["throne"] = build_palace(root)
    objs["granary"] = build_granary(root)
    objs["grainPiles"] = build_grain_piles(root, sp["heaps"], sp["baskets"])
    objs["sacks"] = build_sacks(root, sp["sacks"])
    objs["cell"], objs["cellBench"] = build_cell(root)
    palm_tpl = palm_template()
    objs["palms"] = build_palms(root, palm_tpl)
    dtpl = {k: f() for k, f in DREAM_TPL.items()}
    objs.update(build_dreams(root, dtpl))
    bpy.context.view_layer.update()
    tmp = {"tpl_sheep": make_obj("tpl_sheep", sheep_tpl, None, smooth_angle=60)}
    for k, m in dtpl.items():
        tmp["tpl_" + k] = make_obj("tpl_" + k, m, None, smooth_angle=50)
    src = raster_sources(objs, tmp)
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("TWOLANDS_TRIS", total, json.dumps(tris))
    print("SCATTER", json.dumps(scatter))
    assert total <= MAX_TRIS, "over budget %d" % total
    lay = check_layout()
    hard, soft, closest = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    for it in ITEMS:
        print("  CLEAR %-44s %s closest %.3f%s" % (it["label"], "hard" if it["hard"] else "soft",
                                                   closest[it["label"]], "  BLOCKED" if it["label"] in hard or
                                                   it["label"] in soft else ""))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_SOFT", json.dumps(soft))
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
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_yup=True, export_apply=False,
                              export_skins=False, export_animations=False, export_texcoords=True,
                              export_normals=True, export_materials='EXPORT', export_morph=False)
    hmax = {n: round(max(v[1] for v in world_verts(ob)), 4) for n, ob in objs.items()}
    hmin = {n: round(min(v[1] for v in world_verts(ob)), 4) for n, ob in objs.items()}
    write_design(objs, tris, total, hmax, hmin, const, hard, soft, closest, sp)
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root, sp=sp)
    print("BUILD_OK", GLB, total)


def write_design(objs, tris, total, hmax, hmin, const, hard, soft, closest, sp):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"height": v["height"], "sheetX": v["sheetX"], "sheetY": v["sheetY"]})
        ch[c] = e
    d["characters"] = ch
    pieces = []
    for name in ORDER:
        g = drawing_of(name)
        spd = DRAWINGS[g] if g else None
        fu = ({k: (round(spd[k], 5) if isinstance(spd[k], float) else spd[k]) for k in
               ("A", "B", "D", "scale", "sheetX", "sheetY")} if spd else None)
        pieces.append({"id": name, "drawing": g, "frontUV": fu, "instanced": name in sum(TEMPLATES.values(), ()),
                       "namedTexels": {r: list(k) for r, k in CONSTS.get(name, {}).items()} or None,
                       "regions": sorted(set(REG_OF[name])), "heightMin": hmin[name], "heightMax": hmax[name],
                       "tris": tris[name]})
    drawings = {g: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dsp.items()} for g, dsp in DRAWINGS.items()}
    nodes = {n: [round(c, 4) for c in D(objs[n].matrix_world.translation)] for n in ORDER}
    d["set"] = {
        "generatedBy": "pipeline/js_twolands.py", "doc": "docs/joseph/SET.md", "contract": "docs/joseph/CONTRACT.md §6",
        "root": "twolands",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer",
        "nodes": nodes,
        "footprints": {"floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]],
                       "tent": [TENT[0], TENT[2], TENT[1], TENT[3]],
                       "pit": {"centre": list(WELL), "innerRadius": WELL_RI, "outerRadius": WELL_RO, "top": WELL_H},
                       "bucket": list(sp["bucket"]), "caravan": list(sp["caravan"]), "olive": list(OLIVE),
                       "sheep": [[s[0], s[1]] for s in SHEEP],
                       "palace": {"dais": [PAL[0], PAL[2], PAL[1], PAL[3]], "daisTop": DAIS_TOP, "steps": 4,
                                  "columns": [list(c) for c in COLS], "throne": list(THRONE_AT), "fireBowl": list(FIRE)},
                       "granary": {"stores": [list(s) for s in STORES], "radius": STORE_R, "height": STORE_H},
                       "grainPiles": {"heaps": [list(h) for h in sp["heaps"]], "baskets": [list(b) for b in sp["baskets"]]},
                       "sacks": [list(s) for s in sp["sacks"]],
                       "cell": {"x": [CELL_X0, CELL_X1], "z": [CELL_ZB, CELL_ZF], "height": CELL_H, "openSide": "+z",
                                "bench": {"centre": [BENCH[0], BENCH[1]], "top": BENCH[2], "size": [0.10, 0.036]}},
                       "palms": [[p[0], p[1]] for p in PALMS]},
        "dreamPanels": {n: {"centre": [v[1], v[2], v[3]], "width": v[4], "height": v[5], "tiltDeg": 15,
                            "drawing": v[0]} for n, v in DREAMS.items()},
        "hiddenAtStart": list(HIDDEN),
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227; "
                             "P = world position, or the template position for instanced pieces",
                   "edgeOn": "faces with |n . D| < 0.22 (n in drawing space) take one clean texel of their region",
                   "namedTexels": "no-raster pieces take one texel of a named (drawing, region); constUV in "
                                  "model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard, "soft": soft, "closestLowGeometry": closest},
        "sheetLayout": {"characters": CHAR_PROPOSAL, "charactersFrom": "model/regions_characters.json"
                        if CHARS_FROM_FILE else "proposal (regions_characters.json not there yet)"},
        "demoColours": COLOURS, "tris": total, "budget": MAX_TRIS,
    }
    json.dump(d, open(DESIGN_JSON, "w"), indent=1, ensure_ascii=False)


def compose_sheets(idb, regname, crease):
    """quick-look line art + demo colouring of the set drawings, and the preview texture (as Ruth's set)"""
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
    for ch_, c in CHAR_PROPOSAL.items():
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
    save_png(line, os.path.join(WORK, "twolands_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "twolands_drawings_demo.png"))
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
        "skin": "#E9B48F", "cream": "#F1E7D0", "hair": "#4A2E1F", "c1": "#D9463A", "c2": "#F2C744", "c3": "#4FA65A",
        "c4": "#3B7FD0", "c5": "#8A5CC2", "grey": "#8F7F6C", "white": "#F4F1EA", "rust": "#A8562A", "olive": "#5E6B3A",
        "beard": "#231A16", "red": "#C8423A", "royal": "#2E5FA8", "gold": "#E8B84A", "kilt": "#FBF7EC",
        "staff": "#9B6B43"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    for who, (x, z, yaw) in layout.items():
        mb = MB()
        if who == "joseph":
            lathe(mb, [(0.0, 0.0), (0.045, 0.0), (0.042, 0.02), (0.035, 0.12), (0.030, 0.24), (0.0, 0.25)], "cream",
                  C=(x, 0, z), seg=18)
            for k, reg in enumerate(("c1", "c2", "c3", "c4", "c5")):
                h0 = 0.03 + 0.042 * k
                lathe(mb, [(0.049 - 0.003 * k, h0), (0.047 - 0.003 * k, h0 + 0.042)], reg, C=(x, 0, z - 0.004), seg=18,
                      rfun=lambda th, i, kk: 1.0 if math.sin(th) < 0.5 else 0.0001)
            sphere(mb, (x, 0.282, z), 0.031, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.293, z - 0.006), 0.031, "hair", seg=12, rings=7, sh=0.7)
        elif who == "jacob":
            lathe(mb, [(0.0, 0.0), (0.046, 0.0), (0.043, 0.02), (0.036, 0.12), (0.028, 0.22), (0.0, 0.23)], "grey",
                  C=(x, 0, z), seg=18)
            sphere(mb, (x, 0.258, z + 0.008), 0.029, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.243, z + 0.022), 0.020, "white", seg=10, rings=7, sh=1.2, sz=0.7)
            lathe(mb, [(0.0, 0.17), (0.040, 0.175), (0.038, 0.25), (0.032, 0.285), (0.0, 0.296)], "white",
                  C=(x, 0, z - 0.006), seg=16, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.35 else 0.0001)
            tube(mb, [(x + 0.048, 0.0, z + 0.02), (x + 0.048, 0.27, z + 0.02)], 0.004, "staff", seg=6)
        elif who == "brother":
            lathe(mb, [(0.0, 0.0), (0.052, 0.0), (0.050, 0.02), (0.044, 0.12), (0.041, 0.24), (0.036, 0.29),
                       (0.0, 0.295)], "rust", C=(x, 0, z), seg=18)
            lathe(mb, [(0.054, 0.12), (0.048, 0.20), (0.044, 0.28)], "olive", C=(x, 0, z - 0.003), seg=18,
                  rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.6 else 0.0001)
            sphere(mb, (x, 0.330, z), 0.034, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.312, z + 0.015), 0.021, "beard", seg=10, rings=7, sh=1.2, sz=0.8)
        else:
            lathe(mb, [(0.0, 0.0), (0.054, 0.0), (0.052, 0.02), (0.046, 0.14), (0.048, 0.26), (0.040, 0.31),
                       (0.0, 0.315)], "kilt", C=(x, 0, z), seg=18)
            lathe(mb, [(0.050, 0.14), (0.052, 0.16), (0.020, 0.16)], "royal", C=(x, 0, z), seg=18)
            lathe(mb, [(0.0, 0.27), (0.050, 0.275), (0.058, 0.29), (0.050, 0.305), (0.0, 0.31)], "gold", C=(x, 0, z),
                  seg=18)
            sphere(mb, (x, 0.345, z), 0.034, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, 0.36), (0.036, 0.362), (0.034, 0.40), (0.020, 0.43), (0.012, 0.455), (0.0, 0.46)], "red",
                  C=(x, 0, z), seg=16)
            lathe(mb, [(0.0, 0.40), (0.016, 0.40), (0.010, 0.44), (0.0, 0.445)], "kilt", C=(x, 0, z + 0.004), seg=12)
        ob = make_obj("pv_" + who, mb, None, origin=(x, 0.0, z), smooth_angle=60)
        ob["pv"] = 1
        ob.rotation_euler = (0, 0, math.radians(yaw))


def mode_preview():
    if not STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "twolands_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "twolands_preview_sheet.png")); sheet.pack()
    W, H = PAGE; px = ART[2]
    x0, x1 = -ART[0] / px - 0.5, (W - ART[0]) / px - 0.5
    ztop = -(ART[1] + ART[3]) / px; zbot = (H - ART[1] - ART[3]) / px
    me = bpy.data.meshes.new("paper")
    me.from_pydata([B(x0, -0.001, zbot), B(x1, -0.001, zbot), B(x1, -0.001, ztop), B(x0, -0.001, ztop)], [],
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
    tb.from_pydata([B(-4, -0.004, 4), B(4, -0.004, 4), B(4, -0.004, -4), B(-4, -0.004, -4)], [], [(0, 1, 2, 3)])
    tb.materials.append(flat_mat("pv_wood", "#6E4A33", 0.6))
    link(bpy.data.objects.new("pv_table", tb))
    sun = link(bpy.data.objects.new("pv_sun", bpy.data.lights.new("pv_sun", 'SUN')))
    sun.data.angle = math.radians(4); sun.data.energy = 3.1; sun.data.color = (1.0, 0.95, 0.86)
    sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-30))
    fill = link(bpy.data.objects.new("pv_fill", bpy.data.lights.new("pv_fill", 'AREA')))
    fill.data.size = 1.5; fill.data.energy = 6.0; fill.data.color = (1.0, 0.88, 0.72)
    fill.location = B(0.0, 0.8, 1.2)
    fill.rotation_euler = (B(0, 0.1, -0.2) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    sc.world = bpy.data.worlds.new("w")
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (0.80, 0.84, 0.90, 1); bg.inputs[1].default_value = 0.75
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    cam = link(bpy.data.objects.new("pv_cam", bpy.data.cameras.new("pv_cam"))); sc.camera = cam
    cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.005; cam.data.clip_end = 30

    def shoot(name, eye, tgt, vfov, res, out=MODEL):
        e = B(*eye); g = B(*tgt)
        cam.location = e; cam.rotation_euler = (g - e).to_track_quat('-Z', 'Y').to_euler()
        cam.data.angle_y = math.radians(vfov)
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.resolution_percentage = 100
        sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)

    def show(names, on):
        for n in names:
            objs[n].hide_render = not on
            for c in objs[n].children_recursive:
                c.hide_render = not on

    def cast(layout):
        for o in [o for o in bpy.data.objects if o.get("pv")]:
            bpy.data.objects.remove(o, do_unlink=True)
        if layout:
            mannequins(layout)
    show(HIDDEN, False)
    cast({})
    phone = ((-0.02, 0.95, 1.15), (-0.02, 0.05, -0.50), 55, (720, 1280))
    shoot("twolands_preview_phone_set", *phone)
    shoot("twolands_preview_phone_low", (0.02, 0.62, 0.95), (0.02, 0.06, -0.30), 52, (720, 1280))
    shoot("twolands_preview_front", (0.0, 0.26, 2.3), (0.0, 0.14, -0.25), 21, (1600, 1000))
    cast({"jacob": (-0.46, -0.20, 30), "joseph": (-0.32, -0.16, -60), "brother": (-0.16, -0.12, -100),
          "pharaoh": (0.38, -0.30, 0)})
    shoot("twolands_preview_phone", *phone)
    cast({"joseph": (-0.34, 0.08, 0), "brother": (-0.20, 0.06, -90), "jacob": (-0.46, -0.20, 20)})
    show(["caravan"], True)
    shoot("twolands_preview_canaan", (-0.10, 0.36, 0.55), (-0.38, 0.07, -0.18), 42, (1280, 720))
    show(["caravan"], False)
    cast({"joseph": (0.10, -0.06, 0)})
    show(["cell"], True)
    shoot("twolands_preview_cell", (0.24, 0.28, 0.40), (0.10, 0.08, -0.07), 38, (1280, 720))
    show(["cell"], False)
    cast({"pharaoh": (0.38, -0.30, 0), "joseph": (0.22, -0.20, 60)})
    show(["dreamCows"], True)
    shoot("twolands_preview_palace", (0.12, 0.36, 0.42), (0.38, 0.20, -0.38), 44, (1280, 720))
    show(["dreamCows"], False)
    cast({"joseph": (0.42, 0.04, -20), "brother": (0.22, 0.13, 40)})
    show(["grainPiles", "sacks"], True)
    shoot("twolands_preview_granary", (0.20, 0.30, 0.50), (0.46, 0.06, -0.06), 42, (1280, 720))
    show(["grainPiles", "sacks"], False)
    cast({"joseph": (-0.32, -0.16, 0), "pharaoh": (0.38, -0.30, 0), "brother": (0.22, 0.13, 40)})
    show(["dreamSheaves", "dreamCows", "dreamSheaves2"], True)
    shoot("twolands_preview_dreams", (0.0, 0.62, 1.05), (0.0, 0.32, -0.12), 46, (1280, 900))
    show(["dreamSheaves", "dreamCows", "dreamSheaves2"], False)
    show(["dreamStars", "dreamGrain"], True)
    shoot("twolands_preview_dreams2", (0.0, 0.62, 1.05), (0.0, 0.32, -0.12), 46, (1280, 900))
    show(["dreamStars", "dreamGrain"], False)
    cast({})
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "twolands_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    if os.environ.get("JS_CLOSEUPS", "1") == "1":
        shoot("close_tent", (-0.30, 0.22, -0.12), (-0.44, 0.10, -0.42), 42, (1000, 800), WORK)
        shoot("close_well", (-0.25, 0.20, 0.30), (-0.35, 0.04, 0.08), 40, (1000, 800), WORK)
        shoot("close_olive_sheep", (-0.15, 0.22, 0.12), (-0.38, 0.10, -0.25), 48, (1000, 800), WORK)
        shoot("close_palace", (0.38, 0.24, -0.05), (0.38, 0.16, -0.46), 46, (1000, 900), WORK)
        shoot("close_granary", (0.36, 0.16, 0.22), (0.51, 0.07, -0.05), 42, (1000, 800), WORK)
        shoot("close_horizon", (0.0, 0.25, -0.15), (0.0, 0.12, -0.57), 55, (1400, 700), WORK)
        show(["caravan"], True)
        cx_, cz_ = STATE["sp"]["caravan"]
        shoot("close_caravan", (cx_ + 0.10, 0.22, cz_ + 0.36), (cx_ - 0.02, 0.10, cz_), 40, (1000, 800), WORK)
        show(["caravan"], False)
        for n in ("dreamSheaves", "dreamStars", "dreamCows", "dreamGrain"):
            show([n], True)
            _, x, h, z, w, hh = DREAMS[n]
            shoot("close_" + n, (x, h + 0.10, z + 0.38), (x, h, z), 34, (1000, 700), WORK)
            show([n], False)
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["twolands", "ground", "horizon", "tent", "sheep", "olive", "pit", "bucket", "caravan", "palace", "throne",
        "granary", "grainPiles", "sacks", "cell", "cellBench", "palms", "dreamSheaves", "dreamSheaves2", "dreamStars",
        "dreamCows", "dreamGrain"]


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
    ok = not missing and tris <= MAX_TRIS and uv_bad == 0
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "parents": parents}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
