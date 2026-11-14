"""Blender (headless): Exodus story pack, Egypt and the sea -> assets/exodus/model/egypt.glb

A tabletop stage on the colouring sheet, back to front: a low backdrop (dunes, two pyramids with gold caps, the red
rock mountain with strata, a ledge path and dry shrubs); Pharaoh's palace (paved platform, back wall with a painted
frieze, four fat papyrus columns with open capitals, an architrave and cavetto cornice with the winged sun, a stepped
dais with a gilded throne, two obelisks, two palms); two Israelite mud-brick houses (doorways, windows, roof mats,
an outside stair, jars) with hidden `doorMarks`; the brick yard (single bricks: a half-built wall with a ramp,
cross-stacked piles, bricks drying in rows, wooden moulds, a straw pile, a trough) with a crowd of workers; the Nile
(water, papyrus clumps with lotus, lily pads, a reed boat); the thorn bush on a rocky rise (`bushFlame`); the sea
(rippled surface in three parts, a wet sand-bed with shells under the crossing lane, and the two standing water walls
with curling foamy crests and fish on their inner faces, modelled at full height, scaled flat and hidden at rest); the
far shore with three palms and rocks; hidden crowds on both shores and Pharaoh's loose wheel; `pillarWest`.
Contract: docs/exodus/CONTRACT.md §6. Details, nodes, marks and UV rules: docs/exodus/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `ex_page` = the scanned art rectangle): as Ruth (pipeline/ru_bethlehem.py). Each piece
belongs to one *drawing* on the colouring sheet, a linear view a = A.P, b = B.P (depth D.P), and
  u = a / scale + sheetX + 0.5,   v = (b / scale + sheetY) / 1.227
P = the world position, or the template position for instanced pieces (palms, papyrus clumps, people). Faces nearly
edge-on to their drawing take one clean texel of their own region; scattered bits and the sea walls take the texel
of a named (drawing, region).

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/ex_egypt.py -- build     egypt.glb + .blend + sheet drawings
  blender -b --factory-startup --python pipeline/ex_egypt.py -- verify    re-import egypt.glb and check it
  blender -b --factory-startup --python pipeline/ex_egypt.py -- all       build, preview, verify
  blender -b --factory-startup --python pipeline/ex_egypt.py -- check     build in memory, print the checks, write nothing
Work files go to $EX_WORK (default /tmp/ex_set_work).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/exodus/model")
GLB = os.path.join(MODEL, "egypt.glb")
BLEND = os.path.join(MODEL, "egypt.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/exodus/design.json")
TIMELINE = os.path.join(ROOT, "assets/exodus/timeline.json")
WORK = os.environ.get("EX_WORK", "/tmp/ex_set_work")
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
TARGET_TRIS = 75000                    # CONTRACT §6 said 65k; raised to 75k by the coordinator for the crowd (2026-11-14)
MAX_TRIS = 80000                       # hard ceiling
TAU = 2 * math.pi
UP = (0.0, 1.0, 0.0)
FLOOR = (-0.60, 0.60, -0.5875, 0.21)          # x0 x1 zBack zFront
def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def B(x, h, z):
    """design (x, h, z) -> Blender vector"""
    return Vector((x, -z, h))


def D(v):
    """Blender vector -> design (x, h, z)"""
    return (v.x, v.z, -v.y)


def box(mb, x0, x1, h0, h1, z0, z1, reg, skip=(), smooth=False):
    """axis box; z0 < z1 (z1 = front). skip: subset of 'front back top bottom left right'"""
    c = ((x0 + x1) / 2, (h0 + h1) / 2, (z0 + z1) / 2)
    v = {}
    for i, x in enumerate((x0, x1)):
        for j, h in enumerate((h0, h1)):
            for k, z in enumerate((z0, z1)):
                v[i, j, k] = mb.v(x, h, z)
    faces = {"front": [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)], "back": [(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)],
             "top": [(0, 1, 0), (1, 1, 0), (1, 1, 1), (0, 1, 1)], "bottom": [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)],
             "left": [(0, 0, 0), (0, 1, 0), (0, 1, 1), (0, 0, 1)], "right": [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)]}
    outs = {"front": (0, 0, 1), "back": (0, 0, -1), "top": (0, 1, 0), "bottom": (0, -1, 0), "left": (-1, 0, 0),
            "right": (1, 0, 0)}
    for name, q in faces.items():
        if name not in skip:
            mb.fo([v[k] for k in q], reg, outs[name], smooth)
    return c


def lathe(mb, prof, reg, C=(0, 0, 0), A=(0, 1, 0), U=(1, 0, 0), V=(0, 0, 1), seg=16, smooth=True, rfun=None,
          sx=1.0, sv=1.0, phase=0.0):
    """Surface of revolution. prof = [(r, a[, region])...] walked so the solid lies on the right (outer surface
    bottom -> top; r = 0 closes at the axis). A entry's region applies from that entry on."""
    C, A, U, V = Vector(C), Vector(A), Vector(U), Vector(V)
    rings = []
    for i, p in enumerate(prof):
        r, a = p[0], p[1]
        if r <= 1e-9:
            rings.append(mb.v(*(C + A * a)))
            continue
        ids = []
        for k in range(seg):
            th = phase + TAU * k / seg
            rr = r * (rfun(th, i, k) if rfun else 1.0)
            ids.append(mb.v(*(C + A * a + U * (rr * math.cos(th) * sx) + V * (rr * math.sin(th) * sv))))
        rings.append(ids)
    cur = reg
    for i in range(len(prof) - 1):
        if len(prof[i]) > 2:
            cur = prof[i][2]
        dr = prof[i + 1][0] - prof[i][0]; da = prof[i + 1][1] - prof[i][1]
        r0, r1 = rings[i], rings[i + 1]
        if isinstance(r0, int) and isinstance(r1, int):
            continue
        for k in range(seg):
            th = phase + TAU * (k + 0.5) / seg
            radial = U * math.cos(th) + V * math.sin(th)
            out = radial * da + A * (-dr)
            k1 = (k + 1) % seg
            if isinstance(r0, int):
                q = [r0, r1[k], r1[k1]]
            elif isinstance(r1, int):
                q = [r0[k], r0[k1], r1]
            else:
                q = [r0[k], r0[k1], r1[k1], r1[k]]
            mb.fo(q, cur, out, smooth)


def sphere(mb, c, r, reg, seg=12, rings=7, sx=1.0, sh=1.0, sz=1.0, smooth=True):
    prof = [(r * math.sin(math.pi * i / rings), -r * math.cos(math.pi * i / rings) * sh) for i in range(rings + 1)]
    prof[0] = (0.0, prof[0][1]); prof[-1] = (0.0, prof[-1][1])
    lathe(mb, prof, reg, C=c, seg=seg, smooth=smooth, sx=sx, sv=sz)


def tube(mb, pts, r, reg, seg=8, closed=False, smooth=True, caps=True, ref=None):
    pts = [Vector(p) for p in pts]; n = len(pts)
    rs = list(r) if isinstance(r, (list, tuple)) else [r] * n
    rings, prev = [], None
    for i in range(n):
        if closed:
            t = pts[(i + 1) % n] - pts[i - 1]
        else:
            t = pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]
        t.normalize()
        if ref is not None:
            nn = t.cross(Vector(ref)).normalized()
        elif prev is None:
            rv = Vector((0, 1, 0)) if abs(t.y) < 0.9 else Vector((1, 0, 0))
            nn = t.cross(rv).normalized()
        else:
            nn = (prev - t * prev.dot(t)).normalized()
        prev = nn; b = t.cross(nn)
        rings.append(([mb.v(*(pts[i] + (nn * math.cos(TAU * k / seg) + b * math.sin(TAU * k / seg)) * rs[i]))
                       for k in range(seg)], nn, b))
    m = n if closed else n - 1
    for i in range(m):
        (ra, na, ba), (rb, nb, bb) = rings[i], rings[(i + 1) % n]
        for k in range(seg):
            th = TAU * (k + 0.5) / seg
            out = na * math.cos(th) + ba * math.sin(th)
            k1 = (k + 1) % seg
            mb.fo([ra[k], ra[k1], rb[k1], rb[k]], reg, out, smooth)
    if caps and not closed:
        for i, sgn in ((0, -1), (n - 1, 1)):
            t = (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized() * sgn
            c = mb.v(*(pts[i] + t * rs[i] * 0.3))
            ring = rings[i][0]
            for k in range(seg):
                mb.fo([c, ring[k], ring[(k + 1) % seg]], reg, t, smooth)


def extrude(mb, poly, zb, zf, reg, X=lambda a, b: (a, b), back=True, side_reg=None, smooth=False):
    """front-facing relief: polygon (a, b) -> (x, h) by X, from z = zb (back) to z = zf (front)"""
    pts = []
    for a, b in poly:
        p = X(a, b)
        if not pts or (abs(p[0] - pts[-1][0]) + abs(p[1] - pts[-1][1])) > 1e-7:
            pts.append(p)
    if abs(pts[0][0] - pts[-1][0]) + abs(pts[0][1] - pts[-1][1]) < 1e-7:
        pts.pop()
    n = len(pts)
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n)) / 2
    fr = [mb.v(x, h, zf) for x, h in pts]
    bk = [mb.v(x, h, zb) for x, h in pts]
    tris = tessellate_polygon([[Vector((x, h, 0)) for x, h in pts]])
    for t in tris:
        mb.fo([fr[i] for i in t], reg, (0, 0, 1), smooth)
        if back:
            mb.fo([bk[i] for i in t], reg, (0, 0, -1), smooth)
    for i in range(n):
        j = (i + 1) % n
        dx, dh = pts[j][0] - pts[i][0], pts[j][1] - pts[i][1]
        o = (dh, -dx) if area > 0 else (-dh, dx)
        mb.fo([fr[i], fr[j], bk[j], bk[i]], side_reg or reg, (o[0], o[1], 0), smooth)


def _inside(P, poly):
    x, y = P[:, 0:1], P[:, 1:2]
    ax, ay = poly[:, 0][None], poly[:, 1][None]
    bx, by = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    cond = (ay > y) != (by > y)
    xint = ax + (y - ay) * (bx - ax) / np.where(by - ay == 0, 1e-12, by - ay)
    return (np.sum(cond & (x < xint), axis=1) % 2) == 1


def _edge_dist(P, poly):
    A = poly; Bp = np.roll(poly, -1, axis=0)
    AB = Bp - A
    t = np.clip(((P[:, None, :] - A[None]) * AB[None]).sum(-1) / np.maximum((AB * AB).sum(-1), 1e-12)[None], 0, 1)
    C = A[None] + t[..., None] * AB[None]
    return np.sqrt(((P[:, None, :] - C) ** 2).sum(-1)).min(1)


def _resample(poly, step):
    out = []
    n = len(poly)
    for i in range(n):
        a, b = np.array(poly[i]), np.array(poly[(i + 1) % n])
        L = np.linalg.norm(b - a); k = max(1, int(math.ceil(L / step)))
        for j in range(k):
            out.append(a + (b - a) * j / k)
    return np.array(out)


def puff(mb, poly, zc, half, reg, X=lambda a, b: (a, b), rad=0.010, edge=0.3, step=0.004, smooth=True):
    """pillow-shaped solid from a front polygon: thickness 2*half in the middle, rounding to 2*half*edge at the
    outline over `rad` (reads as a carved round form, keeps the exact front silhouette)"""
    from mathutils.geometry import delaunay_2d_cdt
    pts = np.array([X(a, b) for a, b in poly], float)
    keep = [0] + [i for i in range(1, len(pts)) if np.abs(pts[i] - pts[i - 1]).sum() > 1e-7]
    pts = pts[keep]
    if np.abs(pts[0] - pts[-1]).sum() < 1e-7:
        pts = pts[:-1]
    bnd = _resample(pts, step)
    lo, hi = pts.min(0), pts.max(0)
    G = []
    for j, y in enumerate(np.arange(lo[1] + step * 0.5, hi[1], step * 0.87)):
        for x in np.arange(lo[0] + (j % 2) * step * 0.5 + step * 0.25, hi[0], step):
            G.append((x, y))
    G = np.array(G) if G else np.zeros((0, 2))
    if len(G):
        G = G[_inside(G, pts)]
        G = G[_edge_dist(G, pts) > step * 0.45]
    K = len(bnd)
    verts = [Vector((float(x), float(y))) for x, y in bnd] + [Vector((float(x), float(y))) for x, y in G]
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, [(i, (i + 1) % K) for i in range(K)], [list(range(K))], 1, 1e-8, True)
    V = np.array([(v.x, v.y) for v in vs])
    T = [tuple(f) for f in fs if len(f) == 3]
    cen = np.array([V[list(t)].mean(0) for t in T])
    T = [t for t, k in zip(T, _inside(cen, pts)) if k]
    d = _edge_dist(V, pts)
    off = half * (edge + (1 - edge) * np.sqrt(np.clip(d / rad, 0, 1)))
    fr = [mb.v(x, y, zc + o) for (x, y), o in zip(V, off)]
    bk = [mb.v(x, y, zc - o) for (x, y), o in zip(V, off)]
    for t in T:
        mb.fo([fr[i] for i in t], reg, (0, 0, 1), smooth)
        mb.fo([bk[i] for i in t], reg, (0, 0, -1), smooth)
    # side band along the outline (boundary verts are the first K of the CDT output in order)
    bi = [i for i in range(len(V)) if d[i] < 1e-6]
    order = []
    for p in bnd:
        j = int(np.argmin(((V - p) ** 2).sum(1)))
        order.append(j)
    area = sum(bnd[i][0] * bnd[(i + 1) % K][1] - bnd[(i + 1) % K][0] * bnd[i][1] for i in range(K))
    for i in range(K):
        a, b = order[i], order[(i + 1) % K]
        dx, dy = V[b] - V[a]
        o = (dy, -dx) if area > 0 else (-dy, dx)
        mb.fo([fr[a], fr[b], bk[b], bk[a]], reg, (o[0], o[1], 0), smooth)


def ngon_top(mb, poly_xz, h, reg, hb=None, out=UP):
    """flat polygon (x, z) at height h (convex or simple), optional side walls down to hb"""
    top = [mb.v(x, h, z) for x, z in poly_xz]
    tris = tessellate_polygon([[Vector((x, z, 0)) for x, z in poly_xz]])
    for t in tris:
        mb.fo([top[i] for i in t], reg, out)
    if hb is not None:
        n = len(poly_xz)
        cx = sum(p[0] for p in poly_xz) / n; cz = sum(p[1] for p in poly_xz) / n
        bot = [mb.v(x, hb, z) for x, z in poly_xz]
        for i in range(n):
            j = (i + 1) % n
            mx = (poly_xz[i][0] + poly_xz[j][0]) / 2 - cx; mz = (poly_xz[i][1] + poly_xz[j][1]) / 2 - cz
            mb.fo([top[i], top[j], bot[j], bot[i]], reg, (mx, 0, mz))

def shift(m, dy, dx):
    out = np.zeros_like(m)
    H, W = m.shape[:2]
    ys = slice(max(dy, 0), H + min(dy, 0)); yd = slice(max(-dy, 0), H + min(-dy, 0))
    xs = slice(max(dx, 0), W + min(dx, 0)); xd = slice(max(-dx, 0), W + min(-dx, 0))
    out[ys, xs] = m[yd, xd]
    return out


def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + r:
                out |= shift(m, dy, dx)
    return out


def save_png(arr, path):
    H, W = arr.shape[:2]
    img = bpy.data.images.new(os.path.basename(path), W, H, alpha=True)
    a = np.ones((H, W, 4), np.float32); a[..., :arr.shape[2]] = arr
    img.pixels.foreach_set(a[::-1].ravel())
    img.filepath_raw = path; img.file_format = 'PNG'; img.save()
    return img


def nz(a, b=0.0, c=0.0):
    """cheap deterministic hash noise in [0, 1)"""
    s = math.sin(a * 12.9898 + b * 78.233 + c * 37.719) * 43758.5453
    return s - math.floor(s)




# ============================================================================================ marks and paths
# CONTRACT §6 marks (kept clear) and the actors' real moves from timeline.json (consecutive targets of one actor).
CONTRACT_MARKS = {
    "ph palace": (-0.36, -0.30), "ph step": (-0.18, -0.24), "ph chase": (-0.10, 0.05), "ph sea": (0.24, 0.07),
    "ph soggy": (0.12, 0.03), "mi brick": (-0.20, -0.06), "mi palace": (-0.10, -0.10), "mi door": (-0.02, -0.32),
    "mi shore": (0.02, 0.13), "mi mid": (0.27, 0.09), "mi far": (0.53, 0.12), "mo in": (0.64, -0.30),
    "mo path": (0.34, -0.30), "mo bush": (0.04, -0.28), "mo bush2": (0.07, -0.30), "mo palace": (-0.18, -0.22),
    "mo door": (0.08, -0.30), "mo shore": (0.12, 0.08), "mo mid": (0.30, 0.07), "mo far": (0.46, 0.04)}
WILD_LANE = (0.04, 0.62, -0.34, -0.26)          # x0 x1 z0 z1: the wilderness lane stays clear
SEA_X, SEA_Z = (0.20, 0.40), (-0.24, 0.21)
LANE_Z = (0.02, 0.13)                            # the crossing lane (dry when parted)
MOVE_SEC = 6.0                                   # a walk lasts at most this long after its act event


def _timeline():
    try:
        return json.load(open(TIMELINE))
    except Exception:
        return {"acting": [], "props": [], "duration": 0.0}


TL = _timeline()
TL_END = float(TL.get("duration", 0.0) or 0.0) + 1.0


def _paths():
    """(label, a, b, hard, t0, t1): a move between two stage marks (hard) during [t0, t1]; soft = a move from or to a
    park position off the page (reported, not enforced)"""
    out = []
    last = {}
    for a in TL["acting"]:
        if "to" not in a:
            continue
        w, p, t = a["who"], (float(a["to"][0]), float(a["to"][1])), float(a["t"])
        if w in last and math.hypot(p[0] - last[w][0], p[1] - last[w][1]) > 1e-4:
            off = max(abs(p[0]), abs(last[w][0])) > 0.62
            out.append(("%s %.2f,%.2f>%.2f,%.2f" % (w, last[w][0], last[w][1], p[0], p[1]), last[w], p, not off,
                        t, t + MOVE_SEC))
        last[w] = p
    return out


def _stands():
    """(label, point, t0, t1): where each actor stands and when (from its arrival to its next move)"""
    ev = {}
    for a in TL["acting"]:
        if "to" in a:
            ev.setdefault(a["who"], []).append((float(a["t"]), (float(a["to"][0]), float(a["to"][1]))))
    out = []
    for w, lst in ev.items():
        for i, (t, p) in enumerate(lst):
            t1 = lst[i + 1][0] + MOVE_SEC if i + 1 < len(lst) else TL_END
            out.append(("%s @%.2f,%.2f" % (w, p[0], p[1]), p, t, t1))
    return out


PATHS = _paths()
STANDS = _stands()
HARD_PTS = list(CONTRACT_MARKS.values())
HARD_SEGS = [(a, b) for _, a, b, hard, _, _ in PATHS if hard]
HIDDEN_AT_START = ["doorMarks", "crowdShore", "crowdFar", "looseWheel", "seaWallBack", "seaWallFront"]


def visible_windows(node):
    """[(t0, t1)] when set node `node` is shown, from the timeline's prop events (egypt/<node>)"""
    vis = node not in HIDDEN_AT_START
    t_on = 0.0 if vis else None
    out = []
    for e in sorted((p for p in TL.get("props", []) if p["node"] == "egypt/" + node), key=lambda p: p["t"]):
        if e["show"] and t_on is None:
            t_on = float(e["t"])
        elif not e["show"] and t_on is not None:
            out.append((t_on, float(e["t"]))); t_on = None
    if t_on is not None:
        out.append((t_on, TL_END))
    return out


def seg_dist(p, a, b):
    ax, az = a; bx, bz = b; px, pz = p
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    return math.hypot(px - ax - t * dx, pz - az - t * dz)


SOFT_SEGS = []                # filled by mode_build: off-page park moves and the first moves from the printed places


def clear_dist(x, z, soft=False):
    """distance from (x, z) to the nearest stage mark or hard path (soft: also the reported-only moves)"""
    d = min(math.hypot(x - a, z - b) for a, b in HARD_PTS)
    for a, b in HARD_SEGS + (SOFT_SEGS if soft else []):
        d = min(d, seg_dist((x, z), a, b))
    return d


def timed_clear(x, z, node, pad=0.0):
    """distance from (x, z) to every stand / move that happens while `node` is shown (timed props)"""
    win = visible_windows(node)
    over = lambda t0, t1: any(t0 < b and t1 > a for a, b in win)
    d = 9.0
    for _, p, t0, t1 in STANDS:
        if over(t0, t1):
            d = min(d, math.hypot(x - p[0], z - p[1]))
    for _, a, b, hard, t0, t1 in PATHS:
        if hard and over(t0, t1):
            d = min(d, seg_dist((x, z), a, b))
    return d - pad


def in_lane(x, z, pad=0.0):
    return WILD_LANE[0] - pad < x < WILD_LANE[1] + pad and WILD_LANE[2] - pad < z < WILD_LANE[3] + pad


# demo colouring (DESIGN.md table; the rest chosen to sit with it)
COLOURS = {
    # ground / water
    "sand": "#E8CC92", "track": "#F0DDB2", "wetSand": "#C8A97A", "beach": "#F0E0B6", "farSand": "#F3E6C4",
    "nile": "#3E8FC4", "sea": "#2C7FA8", "seaDeep": "#1F6690", "foam": "#E6F3F2", "seaBed": "#C8A97A",
    # backdrop
    "duneFar": "#E9C98C", "dune": "#EBD3A0", "pyramid": "#E2BE7A", "pyramidCap": "#E0B13A", "rock": "#B5643F",
    "ledgeTop": "#CF8A5C", "ledge": "#E0B184", "shrub": "#8C8A55",
    # palace
    "pave": "#E9D6AE", "stone": "#E3C998", "paint": "#2F5DA8", "column": "#EFE0BE", "capital": "#5FA58A",
    "gold": "#E0B13A", "dais": "#D8BB86", "throne": "#E8B83A", "cushion": "#C2413A", "obelisk": "#DDB08F",
    "wing": "#2F5DA8",
    # houses
    "mudWall": "#C99A6B", "roof": "#D9B26A", "doorway": "#4A3324", "wood": "#8A5E3A", "jar": "#B8653A",
    "doorMark": "#C2413A",
    # brick yard
    "brick": "#A9673F", "straw": "#E9D08A", "trough": "#8A5E3A", "water": "#6CB2DA", "mud": "#9C7650",
    # nile plants and boat
    "reed": "#6FA24A", "papyrusHead": "#A6C25E", "lotus": "#F4A6B8", "lotusPad": "#5E9A48", "boat": "#D9B26A",
    "rope": "#8A5E3A",
    # bush
    "bushWood": "#5E4330", "bushLeaf": "#8FA876", "bushRock": "#B39074",
    # palms
    "palmTrunk": "#8A6A44", "frond": "#4F8A3C", "dates": "#B5532E",
    # people and sheep
    "robeA": "#C98B3A", "robeB": "#8FA3B8", "robeC": "#B5532E", "cloth": "#F1E6CC", "skin": "#C68A5E",
    "bundle": "#B07A47", "wool": "#F4F1EA", "sheepFace": "#4A3A30",
}
# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model), faces with region, smooth flag, a
    no-raster flag (scattered bits that sample a named texel) and optional skin weights"""

    def __init__(self):
        self.V, self.P, self.F, self.R, self.S, self.N = [], [], [], [], [], []
        self.W = {}
        self.nr = False
        self.pmap = None
        self.xf = None                # optional pose deform applied to every new vertex (bent workers)

    def v(self, x, h, z, p=None):
        if self.xf is not None:
            x, h, z = self.xf((x, h, z))
        self.V.append((float(x), float(h), float(z)))
        if p is None and self.pmap is not None:
            p = self.pmap(self.V[-1])
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


def yaw_fn(x0, z0, yaw=0.0, s=1.0, lean=(0.0, 0.0), h0=0.0, sy=1.0):
    c, sn = math.cos(yaw), math.sin(yaw)

    def f(p):
        x, h, z = p
        x, z = x * c - z * sn, x * sn + z * c
        return (x0 + s * (x + lean[0] * h), h0 + s * sy * h, z0 + s * (z + lean[1] * h))
    return f


def blade(mb, pts, widths, reg, nrm=None):
    """double-sided ribbon along pts (a grass blade, leaf, awn); last width may be 0 (pointed)"""
    n = len(pts)
    L, R = [], []
    for i in range(n):
        p = Vector(pts[i]); t = (Vector(pts[min(i + 1, n - 1)]) - Vector(pts[max(i - 1, 0)])).normalized()
        side = t.cross(Vector(nrm) if nrm else Vector((0, 1, 0)))
        if side.length < 1e-6:
            side = t.cross(Vector((1, 0, 0)))
        side.normalize()
        w = widths[i] / 2
        L.append(mb.v(*(p - side * w))); R.append(mb.v(*(p + side * w)))
    for i in range(n - 1):
        fn = (Vector(mb.V[R[i]]) - Vector(mb.V[L[i]])).cross(Vector(mb.V[L[i + 1]]) - Vector(mb.V[L[i]]))
        for sgn in (1, -1):
            mb.fo([L[i], R[i], R[i + 1], L[i + 1]], reg, tuple(fn * sgn))


def lumpy(mb, c, r, reg, seg=10, rings=6, sh=1.0, sx=1.0, sz=1.0, amp=0.12, seed=0.0, smooth=True, flat_bottom=None):
    """noisy squashed sphere (stones, bushes, crown blobs)"""
    prof = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        prof.append((r * math.sin(th), -r * math.cos(th) * sh))
    prof[0] = (0.0, prof[0][1]); prof[-1] = (0.0, prof[-1][1])
    if flat_bottom is not None:
        prof = [(rr, max(a, flat_bottom - c[1])) for rr, a in prof]
    lathe(mb, prof, reg, C=c, seg=seg, smooth=smooth, sx=sx, sv=sz,
          rfun=lambda t, i, k: 1.0 + amp * (nz(i + seed, k, seed * 3.1) - 0.5) * 2)


# ============================================================================================ objects
REGION_MATS = {}
OBJ_DRAW = {}                 # object -> drawing it samples (None = named texels only)
CONST = {}                    # object -> {region: (drawing, region)} for no-raster faces / whole object
P_OF = {}                     # object -> np array (nv, 3) of P per final vertex
NR_OF = {}                    # object -> np bool per polygon
REG_OF = {}                   # object -> region per polygon
DECOR = {}                    # drawing -> [(p0, p1)] single drawn lines (mortar joints) in drawing-model coords


def region_mat(r):
    if r not in REGION_MATS:
        m = bpy.data.materials.new("rg_" + r)
        m.diffuse_color = (*lin(hex_rgb(COLOURS.get(r, "#FFFFFF"))), 1)
        REGION_MATS[r] = m
    return REGION_MATS[r]


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def make_obj(name, mb, parent=None, origin=(0, 0, 0), smooth_angle=40.0, bevel=None, bevel_angle=50.0, merge=True):
    ox, oh, oz = origin
    me = bpy.data.meshes.new(name)
    me.from_pydata([B(x - ox, h - oh, z - oz) for x, h, z in mb.V], [], mb.F)
    regs = []
    for r in mb.R:
        if r not in regs:
            regs.append(r)
    for r in regs:
        me.materials.append(region_mat(r))
    me.polygons.foreach_set("material_index", [regs.index(r) for r in mb.R])
    me.polygons.foreach_set("use_smooth", [bool(s) for s in mb.S])
    P = np.array(mb.P, float)
    for k, ax in enumerate(("px", "ph", "pz")):
        a = me.attributes.new(ax, 'FLOAT', 'POINT'); a.data.foreach_set("value", P[:, k].astype(np.float32))
    a = me.attributes.new("nr", 'INT', 'FACE'); a.data.foreach_set("value", [1 if n else 0 for n in mb.N])
    ob = link(bpy.data.objects.new(name, me))
    ob.location = B(*origin)
    if mb.W:
        groups = {}
        for vi, ws in mb.W.items():
            for bn, w in ws.items():
                if bn not in groups:
                    groups[bn] = ob.vertex_groups.new(name=bn)
                if w > 1e-4:
                    groups[bn].add([vi], w, 'REPLACE')
    bm = bmesh.new(); bm.from_mesh(me)
    if merge and not mb.W:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    if bevel:
        bm.edges.ensure_lookup_table()
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0) > math.radians(bevel_angle)]
        if edges:
            bmesh.ops.bevel(bm, geom=edges, offset=bevel, offset_type='OFFSET', segments=1, profile=0.5,
                            affect='EDGES', clamp_overlap=True)
    bm.normal_update()
    for e in bm.edges:
        if len(e.link_faces) != 2 or e.calc_face_angle(0) > math.radians(smooth_angle):
            e.smooth = False
        elif not (e.link_faces[0].smooth or e.link_faces[1].smooth) and e.calc_face_angle(0) > math.radians(12):
            e.smooth = False
    bm.to_mesh(me); bm.free()
    if parent is not None:
        parent_keep(ob, parent)
    read_attrs(ob)
    return ob


def read_attrs(ob):
    me = ob.data
    nv = len(me.vertices)
    P = np.zeros((nv, 3))
    for k, ax in enumerate(("px", "ph", "pz")):
        a = np.zeros(nv, np.float32); me.attributes[ax].data.foreach_get("value", a); P[:, k] = a
    nr = np.zeros(len(me.polygons), np.int32); me.attributes["nr"].data.foreach_get("value", nr)
    P_OF[ob.name] = P; NR_OF[ob.name] = nr.astype(bool)
    REG_OF[ob.name] = [me.materials[p.material_index].name[3:].split(".")[0] for p in me.polygons]


def parent_keep(ob, parent):
    bpy.context.view_layer.update()
    ob.parent = parent
    ob.matrix_parent_inverse = parent.matrix_world.inverted()


def empty(name, pos, parent):
    e = link(bpy.data.objects.new(name, None))
    e.empty_display_type = 'SPHERE'; e.empty_display_size = 0.01
    e.location = B(*pos)
    parent_keep(e, parent)
    return e


def world_verts(ob):
    mw = ob.matrix_world
    return [D(mw @ v.co) for v in ob.data.vertices]


# ============================================================================================ small helpers
def catmull(ctrl, step):
    """open Catmull-Rom through ctrl (x, z), resampled about every `step`"""
    P = [ctrl[0]] + list(ctrl) + [ctrl[-1]]
    out = []
    for i in range(1, len(P) - 2):
        p0, p1, p2, p3 = (np.array(P[j], float) for j in (i - 1, i, i + 1, i + 2))
        L = np.linalg.norm(p2 - p1); n = max(2, int(L / step))
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t +
                              (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(np.array(ctrl[-1], float))
    return np.array(out)


def strip_poly(cl, w0, w1):
    """polygon (x, z) of a strip of width w0 -> w1 along centreline cl"""
    n = len(cl); Lf, Rt = [], []
    for i in range(n):
        t = cl[min(i + 1, n - 1)] - cl[max(i - 1, 0)]; t = t / (np.linalg.norm(t) + 1e-12)
        nn = np.array([-t[1], t[0]]); w = (w0 + (w1 - w0) * i / (n - 1)) / 2
        Lf.append(cl[i] + nn * w); Rt.append(cl[i] - nn * w)
    poly = np.array(Lf + Rt[::-1])
    poly[:, 0] = np.clip(poly[:, 0], FLOOR[0], FLOOR[1]); poly[:, 1] = np.clip(poly[:, 1], FLOOR[2], FLOOR[3])
    return poly


def in_poly(p, poly):
    return bool(_inside(np.array([p], float), np.asarray(poly, float))[0])


def blob_poly(cx, cz, r, seed, n=16, amp=0.28):
    return np.array([(cx + r * (1 + amp * (nz(seed, k) - 0.5) * 2) * math.cos(TAU * k / n),
                      cz + r * 0.8 * (1 + amp * (nz(seed + 1, k) - 0.5) * 2) * math.sin(TAU * k / n)) for k in range(n)])



def sweep(mb, stations, reg_fn, out_fn, caps=True, cap_reg=None, smooth=True):
    """connect closed profile rings (same vertex count). stations: list of lists of 3D points; reg_fn(i, k) region of
    the quad from ring i to i+1 at profile edge k; out_fn(i, k) its outward normal (3D)"""
    n = len(stations[0])
    ids = [[mb.v(*p) for p in ring] for ring in stations]
    for i in range(len(ids) - 1):
        for k in range(n):
            k1 = (k + 1) % n
            mb.fo([ids[i][k], ids[i][k1], ids[i + 1][k1], ids[i + 1][k]], reg_fn(i, k), out_fn(i, k), smooth)
    if caps:
        for i, sgn in ((0, -1), (len(ids) - 1, 1)):
            ring = stations[i]
            t = Vector(stations[min(i + 1, len(ids) - 1)][0]) - Vector(stations[max(i - 1, 0)][0])
            tris = tessellate_polygon([[Vector(p) for p in ring]])
            for t3 in tris:
                mb.fo([ids[i][j] for j in t3], cap_reg or reg_fn(i, 0), tuple(t.normalized() * sgn), False)


def prof_normals(prof):
    """outward 2D normals (d, h) per edge of a CCW profile"""
    out = []
    n = len(prof)
    for k in range(n):
        (d0, h0), (d1, h1) = prof[k], prof[(k + 1) % n]
        out.append((h1 - h0, -(d1 - d0)))
    return out


# layout of the page (design x, z)
PALACE = (-0.55, -0.17, -0.56, -0.40)          # footprint x0 x1 z0 z1
PAL_C = (-0.36, -0.48)
COLS_X, COL_Z = (-0.530, -0.465, -0.255, -0.190), -0.430
DAIS_FRONT, DAIS_TOP = -0.36, 0.030
THRONE = (-0.36, -0.458)
OBELISKS = [(-0.577, -0.432), (-0.157, -0.383)]
HOUSES = [(-0.135, -0.027, -0.530, -0.415, 0.086), (-0.006, 0.096, -0.522, -0.408, 0.097)]   # x0 x1 zb zf h
YARD = (-0.48, -0.24, -0.20, -0.02)
BUSH = (0.14, -0.36)
PILLAR = (0.16, -0.12)
WHEEL = (0.28, 0.05)
MOUNT = (0.10, 0.60, -0.5875, -0.40)


def nile_poly():
    zs = np.linspace(0.21, -0.285, 34)
    bank = [(-0.500 + 0.007 * math.sin(z * 23 + 0.6) + 0.004 * math.sin(z * 57), z) for z in zs]
    tail = [(-0.512, -0.312), (-0.535, -0.330), (-0.565, -0.341), (-0.60, -0.346)]
    return np.array([(-0.60, 0.21)] + bank + tail)


def track_poly():
    xs = np.linspace(0.03, 0.60, 40)
    top = [(x, -0.329 + 0.005 * math.sin(x * 21)) for x in xs]
    bot = [(x, -0.271 + 0.005 * math.sin(x * 17 + 1.0)) for x in xs[::-1]]
    poly = np.array(top + bot)
    poly[0, 0] = poly[-1, 0] = 0.03
    return poly


# ============================================================================================ ground
def build_ground(root):
    """the page floor: a constrained triangulation of the plan regions (sand, the wilderness track, the west beach,
    the far shore, wet sand along the water), with holes where the Nile and the sea surfaces lie; gently uneven, with
    a skirt. Dry tufts, pebbles and stones are scattered on it (named texels)."""
    nile = nile_poly()
    track = track_poly()
    sea = np.array([(SEA_X[0], SEA_Z[0]), (SEA_X[1], SEA_Z[0]), (SEA_X[1], SEA_Z[1]), (SEA_X[0], SEA_Z[1])])
    beach = np.array([(0.115, -0.262), (SEA_X[0], -0.262), (SEA_X[0], 0.21), (0.115, 0.21)])
    far = np.array([(SEA_X[1], -0.40), (0.60, -0.40), (0.60, 0.21), (SEA_X[1], 0.21)])
    wet_w = np.array([(0.183, -0.262), (SEA_X[0], -0.262), (SEA_X[0], 0.21), (0.183, 0.21)])
    wet_e = np.array([(SEA_X[1], -0.262), (0.418, -0.262), (0.418, 0.21), (SEA_X[1], 0.21)])
    wet_b = np.array([(SEA_X[0], -0.262), (SEA_X[1], -0.262), (SEA_X[1], SEA_Z[0]), (SEA_X[0], SEA_Z[0])])
    bank = nile[1:35]
    wet_n = np.array(list(bank) + [(x + 0.017, z) for x, z in bank[::-1]])
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    outlines = [_resample(rect, 0.03), _resample(nile, 0.012), _resample(sea, 0.02), _resample(track, 0.012),
                _resample(beach, 0.02), _resample(far, 0.03), _resample(wet_w, 0.02), _resample(wet_e, 0.02),
                _resample(wet_n, 0.012)]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    allo = np.concatenate(outlines)
    for j, z in enumerate(np.arange(FLOOR[2] + 0.02, FLOOR[3] - 0.01, 0.03)):
        for x in np.arange(FLOOR[0] + 0.02 + (j % 2) * 0.015, FLOOR[1] - 0.01, 0.03):
            p = np.array([x + (nz(x, z) - 0.5) * 0.012, z + (nz(z, x) - 0.5) * 0.012])
            if np.min(np.hypot(*(allo - p).T)) > 0.009 and not in_poly(p, nile) and not in_poly(p, sea):
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def region(c):
        if in_poly(c, sea) or in_poly(c, nile):
            return None
        if in_poly(c, wet_n) or in_poly(c, wet_w) or in_poly(c, wet_e) or in_poly(c, wet_b):
            return "wetSand"
        if in_poly(c, track):
            return "track"
        if in_poly(c, beach):
            return "beach"
        if in_poly(c, far):
            return "farSand"
        return "sand"

    def height(x, z):
        h = 0.0011 + 0.0010 * (math.sin(19 * x + 3 * z) * math.sin(13 * z - 5 * x) * 0.5 + 0.5) + 0.0004 * nz(x, z)
        dw = min(abs(x - SEA_X[0]) if SEA_Z[0] - 0.03 < z else 1, abs(x - SEA_X[1]) if SEA_Z[0] - 0.03 < z else 1,
                 abs(x + 0.50) if z > -0.30 else 1)
        if dw < 0.03:
            h *= 0.3 + 0.7 * dw / 0.03
        return h
    H = [height(x, z) for x, z in V]
    mg = MB()
    idx = {}
    for f in fs:
        if len(f) != 3:
            continue
        reg = region(tuple(V[list(f)].mean(0)))
        if reg is None:
            continue
        q = []
        for i in f:
            if i not in idx:
                idx[i] = mg.v(V[i][0], H[i], V[i][1])
            q.append(idx[i])
        mg.fo(q, reg, UP)
    for (ax, az), (bx, bz) in zip(rect, np.roll(rect, -1, axis=0)):          # skirt round the page edge
        n = int(math.hypot(bx - ax, bz - az) / 0.05) + 1
        cx, cz = (ax + bx) / 2, (az + bz) / 2
        o = (cx, 0, cz - (FLOOR[2] + FLOOR[3]) / 2) if abs(az - bz) < 1e-6 else (cx, 0, 0)
        for i in range(n):
            x0, z0 = ax + (bx - ax) * i / n, az + (bz - az) * i / n
            x1, z1 = ax + (bx - ax) * (i + 1) / n, az + (bz - az) * (i + 1) / n
            if in_poly(((x0 + x1) / 2 + 0.002 * np.sign(-cx), (z0 + z1) / 2), sea) or \
                    in_poly(((x0 + x1) / 2 + 0.002, (z0 + z1) / 2 - 0.002), nile):
                continue
            mg.fo([mg.v(x0, height(x0, z0), z0), mg.v(x1, height(x1, z1), z1), mg.v(x1, -0.002, z1),
                   mg.v(x0, -0.002, z0)], "sand", o)
    # scattered bits (no-raster: they sample named texels)
    rng = random.Random(13)
    mg.nr = True
    blocked = [(PALACE[0] - 0.01, PALACE[1] + 0.01, PALACE[2], DAIS_FRONT + 0.01), (-0.15, 0.11, -0.56, -0.39),
               (YARD[0] - 0.01, YARD[1] + 0.01, YARD[2] - 0.01, YARD[3] + 0.01), (0.07, 0.21, -0.43, -0.32),
               (MOUNT[0], MOUNT[1], MOUNT[2], MOUNT[3] + 0.005), (-0.62, 0.62, -0.60, -0.54),
               (SEA_X[0] - 0.012, SEA_X[1] + 0.012, SEA_Z[0] - 0.012, SEA_Z[1] + 0.01)]

    def free(x, z, pad=0.0):
        if not (FLOOR[0] + 0.012 < x < FLOOR[1] - 0.012 and FLOOR[2] + 0.04 < z < FLOOR[3] - 0.012):
            return False
        if in_poly((x, z), nile) or in_poly((x - 0.02, z), nile):
            return False
        return not any(x0 - pad < x < x1 + pad and z0 - pad < z < z1 + pad for x0, x1, z0, z1 in blocked)
    tufts, tries = [], 0
    while len(tufts) < 70 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.54, 0.20)
        if not free(x, z) or in_poly((x, z), track) or any(math.hypot(x - a, z - b) < 0.03 for a, b in tufts):
            continue
        tufts.append((x, z))
    for x, z in tufts:
        tall = 0.016 if clear_dist(x, z, True) > 0.07 and not in_lane(x, z, 0.03) else 0.0105
        for k in range(5):
            a = TAU * k / 5 + rng.uniform(-0.4, 0.4)
            hh = tall * rng.uniform(0.7, 1.05); lean = rng.uniform(0.3, 0.55) * hh
            d = (math.cos(a), math.sin(a))
            blade(mg, [(x + d[0] * 0.0015, 0.0005, z + d[1] * 0.0015), (x + d[0] * lean, hh, z + d[1] * lean)],
                  [0.0034, 0.0], "tuft", nrm=(d[0], 0.0, d[1]))
    pebbles, tries = [], 0
    while len(pebbles) < 60 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z) or any(math.hypot(x - a, z - b) < 0.016 for a, b in pebbles + tufts):
            continue
        pebbles.append((x, z))
    for i, (x, z) in enumerate(pebbles):
        r = rng.uniform(0.003, 0.006)
        lumpy(mg, (x, r * 0.35, z), r, "pebble", seg=5, rings=3, sh=0.55, sx=rng.uniform(0.9, 1.4), amp=0.18, seed=i)
    rocks, tries = [], 0
    while len(rocks) < 16 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z, 0.01) or in_poly((x, z), track) or clear_dist(x, z, True) < 0.075 or in_lane(x, z, 0.02):
            continue
        if any(math.hypot(x - a, z - b) < 0.05 for a, b in rocks) or \
                any(math.hypot(x - a, z - b) < 0.02 for a, b in pebbles + tufts):
            continue
        rocks.append((x, z))
    for i, (x, z) in enumerate(rocks):
        r = rng.uniform(0.008, 0.013)
        lumpy(mg, (x, r * 0.30, z), r, "stone", seg=7, rings=4, sh=0.62, sx=rng.uniform(1.0, 1.5), amp=0.2,
              seed=i + 700, smooth=False)
    mg.nr = False
    ob = make_obj("ground", mg, root, smooth_angle=35)
    return ob, {"tufts": len(tufts), "pebbles": len(pebbles), "rocks": len(rocks)}


def water_grid(mb, x0, x1, z0, z1, step, hfun, rfun, out=UP):
    nx = max(2, int(round((x1 - x0) / step))); nzn = max(2, int(round((z1 - z0) / step)))
    g = [[mb.v(x0 + (x1 - x0) * i / nx, hfun(x0 + (x1 - x0) * i / nx, z0 + (z1 - z0) * j / nzn),
               z0 + (z1 - z0) * j / nzn) for j in range(nzn + 1)] for i in range(nx + 1)]
    for i in range(nx):
        for j in range(nzn):
            cx = x0 + (x1 - x0) * (i + 0.5) / nx; cz = z0 + (z1 - z0) * (j + 0.5) / nzn
            mb.fo([g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]], rfun(cx, cz), out, True)
    return g


def sea_h(x, z):
    """gentle ripples, <= 0.0092"""
    return (0.0068 + 0.0011 * math.sin(x * 61 + z * 23) * math.sin(z * 47 - x * 11)
            + 0.0006 * math.sin(x * 140 + z * 90))


def sea_region(x, z):
    if z < SEA_Z[0] + 0.024 + 0.006 * math.sin(x * 70) or z > SEA_Z[1] - 0.022 - 0.006 * math.sin(x * 63 + 1):
        return "foam"
    if abs(x - 0.30) < 0.042 + 0.010 * math.sin(z * 19 + 0.5):
        return "seaDeep"
    return "sea"


def build_nile(root):
    """`nile` (papyrus clumps from one template, lily pads with lotus flowers) with children `nileWater` (the river
    surface, own mesh so the FX can tint it) and `nileBoat` (a small papyrus-bundle boat)"""
    poly = nile_poly()
    mw = MB()
    pts = list(_resample(poly, 0.012))
    K = len(pts)
    inner = []
    for j, z in enumerate(np.arange(-0.34, 0.21, 0.016)):
        for x in np.arange(-0.595 + (j % 2) * 0.008, -0.49, 0.016):
            if in_poly((x, z), poly) and min(math.hypot(x - a, z - b) for a, b in pts) > 0.006:
                inner.append((x, z))
    verts = [Vector((float(x), float(z))) for x, z in pts + inner]
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, [(i, (i + 1) % K) for i in range(K)], [list(range(K))], 1, 1e-8,
                                             True)
    V = np.array([(v.x, v.y) for v in vs])
    hw = lambda x, z: 0.0045 + 0.0008 * math.sin(x * 80 + z * 31) * math.sin(z * 53)
    ids = [mw.v(x, hw(x, z), z) for x, z in V]
    for f in fs:
        if len(f) == 3 and in_poly(tuple(V[list(f)].mean(0)), poly):
            mw.fo([ids[i] for i in f], "nile", UP, True)
    for i in range(K):                                            # the bank edge down to the page
        (ax, az), (bx, bz) = pts[i], pts[(i + 1) % K]
        if ax <= -0.599 and bx <= -0.599 or (az >= 0.209 and bz >= 0.209):
            o = (-1, 0, 0) if ax <= -0.599 else (0, 0, 1)
        else:
            o = (bz - az, 0, -(bx - ax))
        mw.fo([mw.v(ax, hw(ax, az), az), mw.v(bx, hw(bx, bz), bz), mw.v(bx, -0.001, bz), mw.v(ax, -0.001, az)],
              "nile", o)
    dec = DECOR.setdefault("ground", [])
    for k, z in enumerate(np.arange(-0.31, 0.20, 0.042)):         # little wave marks on the river (print only)
        x = -0.575 + 0.03 * nz(k, 3)
        for s in range(3):
            a = (x + s * 0.006, 0.006, z + 0.004 * math.sin(s * 2.2))
            b = (x + s * 0.006 + 0.006, 0.006, z + 0.004 * math.sin(s * 2.2 + 1.6))
            dec.append((a, b))
    # papyrus clumps along the bank and in the shallows (instanced: they wear the one papyrus drawing)
    tpl = papyrus_template()
    mb = MB()
    rng = random.Random(31)
    spots = [(-0.505, -0.27, 1.05), (-0.512, -0.20, 0.85), (-0.490, -0.14, 1.0), (-0.507, -0.05, 0.9),
             (-0.493, 0.03, 1.1), (-0.510, 0.10, 0.92), (-0.498, 0.17, 1.0), (-0.585, -0.31, 0.8), (-0.588, 0.19, 0.8),
             (-0.588, -0.08, 0.75)]
    for i, (x, z, s) in enumerate(spots):
        mb.add(tpl, yaw_fn(x, z, rng.uniform(0, TAU), s, lean=(rng.uniform(-0.05, 0.05), 0.0)))
    mb.nr = True                                                  # lily pads and lotus flowers on the water
    for i, (x, z) in enumerate(((-0.552, -0.22), (-0.540, -0.17), (-0.560, -0.11), (-0.533, 0.00), (-0.556, 0.05),
                                (-0.545, 0.15), (-0.528, -0.255), (-0.566, 0.115))):
        r = 0.0105 + 0.003 * nz(i, 2)
        a0 = rng.uniform(0, TAU)
        ring = [(x + r * math.cos(a0 + 0.35 + (TAU - 0.7) * k / 10), 0.0064, z + r * math.sin(a0 + 0.35 + (TAU - 0.7) * k / 10))
                for k in range(11)]
        c = mb.v(x, 0.0066, z)
        rv = [mb.v(*p) for p in ring]
        for k in range(10):
            mb.fo([c, rv[k], rv[k + 1]], "lotusPad", UP)
        if i % 2 == 0:
            flower(mb, (x + 0.002, 0.0085, z + 0.001), 0.0062, "lotus", facing=(0, 1, 0))
    mb.nr = False
    ob = make_obj("nile", mb, root, origin=(-0.55, 0.0, -0.04), smooth_angle=60)
    water = make_obj("nileWater", mw, ob, origin=(-0.55, 0.0, -0.04), smooth_angle=60)
    # papyrus-bundle boat: a curved bundle with up-curled ends, binding rings, a pole lying in it (P offset: its
    # drawing sits beside the papyrus template on the sheet)
    bm = MB()
    bx, bz, ya = -0.556, 0.072, 0.18
    bm.pmap = lambda p: (p[0] - bx + 0.075, p[1], p[2] - bz)
    cpath = []
    for u in np.linspace(-1, 1, 13):
        L = 0.040
        cpath.append((bx + L * u * math.cos(ya), 0.0068 + 0.010 * u ** 6 + 0.001, bz + L * u * math.sin(ya)))
    rad = [0.0028 + 0.0045 * (1 - abs(u) ** 2.2) for u in np.linspace(-1, 1, 13)]
    tube(bm, cpath, rad, "boat", seg=8)
    for u in (-0.75, -0.4, 0.0, 0.4, 0.75):
        i = int(round((u + 1) * 6))
        p = Vector(cpath[i]); t = (Vector(cpath[min(i + 1, 12)]) - Vector(cpath[max(i - 1, 0)])).normalized()
        nn = t.cross(Vector((0, 1, 0))).normalized(); bb = t.cross(nn)
        r = rad[i] + 0.0006
        tube(bm, [tuple(p + (nn * math.cos(TAU * k / 9) + bb * math.sin(TAU * k / 9)) * r) for k in range(9)],
             0.0009, "rope", seg=4, closed=True)
    tube(bm, [(bx - 0.03, 0.0125, bz - 0.008), (bx + 0.035, 0.0155, bz + 0.012)], 0.0011, "rope", seg=4)
    bm.pmap = None
    boat = make_obj("nileBoat", bm, ob, origin=(bx, 0.0, bz), smooth_angle=60)
    return ob, water, boat, tpl


def papyrus_template():
    """one papyrus clump (local, base at the origin): seven triangular stalks of different heights with umbel heads
    (a fan of thin rays and a tuft), two sheath leaves, and a lotus flower on a tilted pad in front"""
    mb = MB()
    rng = random.Random(41)
    for k in range(7):
        a = TAU * k / 7 + rng.uniform(-0.3, 0.3)
        d = Vector((math.cos(a), 0, math.sin(a)))
        Hs = (0.070, 0.092, 0.080, 0.100, 0.064, 0.086, 0.076)[k]
        lean = 0.012 + rng.uniform(0, 0.012)
        pts = [d * (0.003 + lean * (u ** 1.5)) + Vector((0, Hs * u, 0)) for u in (0.0, 0.5, 1.0)]
        tube(mb, [tuple(p) for p in pts], [0.0016, 0.0013, 0.0010], "reed", seg=3, caps=False)
        top = pts[-1]
        ax = (d * 0.35 + Vector((0, 1, 0))).normalized()
        u_ = ax.cross(Vector((0, 0, 1)) if abs(ax.z) < 0.9 else Vector((1, 0, 0))).normalized(); v_ = ax.cross(u_)
        tips = []
        for j in range(6):                                             # rays of the umbel
            th = TAU * j / 6 + rng.uniform(-0.2, 0.2)
            dirv = (ax * 0.55 + (u_ * math.cos(th) + v_ * math.sin(th)) * 0.85).normalized()
            tip = top + dirv * rng.uniform(0.013, 0.017) + Vector((0, -0.002, 0))
            tips.append(tip)
            blade(mb, [tuple(top), tuple(top + dirv * 0.008 + Vector((0, 0.001, 0))), tuple(tip)],
                  [0.0010, 0.0024, 0.0], "papyrusHead", nrm=tuple(ax))
        lumpy(mb, tuple(top + ax * 0.002), 0.0028, "papyrusHead", seg=5, rings=3, sh=0.7, amp=0.1, seed=k)
    for s in (-1, 1):                                                  # sheath leaves at the foot
        a = 0.7 * s
        d = Vector((math.cos(a) * s, 0, math.sin(abs(a))))
        blade(mb, [(d * 0.002).to_tuple(), tuple(d * 0.010 + Vector((0, 0.020, 0))), tuple(d * 0.024 + Vector((0, 0.034, 0)))],
              [0.0120, 0.0100, 0.0], "reed", nrm=(0, 0, 1))
    # lotus on a tilted pad in front of the clump (the pad tilts so it has area in the front drawing)
    pc = Vector((0.012, 0.0045, 0.020))
    for k in range(10):
        a0, a1 = 0.3 + (TAU - 0.6) * k / 10, 0.3 + (TAU - 0.6) * (k + 1) / 10
        p0 = pc + Vector((0.011 * math.cos(a0), 0.006 * math.sin(a0), 0.011 * math.sin(a0) * 0.5))
        p1 = pc + Vector((0.011 * math.cos(a1), 0.006 * math.sin(a1), 0.011 * math.sin(a1) * 0.5))
        mb.fo([mb.v(*pc), mb.v(*p0), mb.v(*p1)], "lotusPad", (0, 0.5, 1))
    flower(mb, tuple(pc + Vector((0, 0.008, 0.002))), 0.0075, "lotus", facing=(0, 0.6, 0.8))
    return mb


def flower(mb, c, r, reg, facing=(0, 0, 1)):
    f = Vector(facing).normalized()
    u = f.cross(Vector((0, 1, 0)))
    if u.length < 1e-3:
        u = Vector((1, 0, 0))
    u.normalize(); v = f.cross(u)
    lathe(mb, [(0.0, -0.25 * r), (r * 0.55, -0.15 * r), (r * 0.8, 0.35 * r), (r, 0.75 * r), (r * 0.25, 0.35 * r),
               (0.0, 0.3 * r)], reg, C=c, A=tuple(f), U=tuple(u), V=tuple(v), seg=10, smooth=True,
          rfun=lambda th, i, k: 1.0 + (0.32 * math.cos(6 * th) if 1 < i < 4 else 0.0))


# ============================================================================================ backdrop
def dune_far(x):
    """the far desert panel across the whole back (like Ruth's far hill: it hides the top of the printed page from the
    phone); lower behind the small pyramid so both peaks keep their silhouette"""
    return (0.222 + 0.022 * math.sin(5.3 * x + 0.7) + 0.012 * math.sin(13 * x + 0.2)
            - 0.050 * math.exp(-((x + 0.455) / 0.07) ** 2) - 0.030 * math.exp(-((x + 0.115) / 0.06) ** 2))


def dune_near(x):
    return 0.030 + 0.016 * math.sin(7.5 * x + 0.8) + 0.008 * math.sin(17 * x)


def mount_h(x, z):
    """the mountain's height field: three peaks, steep red strata (terraced), a foot at z -0.40"""
    u = min(1.0, max(0.0, (z - MOUNT[3]) / (MOUNT[2] - MOUNT[3])))          # 0 at the foot, 1 at the back
    pk = (0.17 * math.exp(-((x - 0.40) / 0.13) ** 2) + 0.10 * math.exp(-((x - 0.545) / 0.07) ** 2)
          + 0.07 * math.exp(-((x - 0.22) / 0.08) ** 2) + 0.075 + 0.014 * math.sin(x * 37) + 0.008 * math.sin(x * 83))
    rise = min(1.0, u / 0.70) ** 0.75
    edge = min(1.0, max(0.0, (x - MOUNT[0]) / 0.06)) ** 0.8
    h = min(0.315, pk * rise * edge)
    q = 0.030
    k, f = divmod(h, q)
    f /= q
    h = q * (k + f ** 4.0)                                                     # strata: cliffs and shelves
    return max(0.0, h + 0.0025 * (nz(x * 9, z * 9) - 0.5))


LEDGE = [(0.165, -0.405), (0.260, -0.432), (0.205, -0.463), (0.320, -0.492), (0.250, -0.520), (0.355, -0.548)]


def build_backdrop(root):
    """low relief across the back: a far dune panel, near dunes with ripples, two pyramids (stepped courses, gold
    caps); children `pyramids` and `mountain` (red rock in terraced strata, a zigzag ledge path, dry shrubs)"""
    mb = MB()
    xs = np.linspace(-0.60, 0.60, 73)
    poly = [(-0.60, 0.0), (0.60, 0.0)] + [(x, dune_far(x)) for x in xs[::-1]]
    extrude(mb, poly, -0.5875, -0.5795, "duneFar", back=False)
    NX, NT = 40, 5
    xs = np.linspace(-0.60, 0.11, NX + 1); ts = np.linspace(0, 1, NT + 1)
    npt = lambda x, t: (x, dune_near(x) * math.sin(0.5 * math.pi * t) ** 1.3 * (1.0 if x < 0.05 else max(0.05, (0.11 - x) / 0.06)),
                        -0.548 + (-0.578 + 0.548) * t)
    g = [[mb.v(*npt(x, t)) for t in ts] for x in xs]
    for i in range(NX):
        for j in range(NT):
            mb.fo([g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]], "dune", (0, 0.5, 1), True)
    for i in range(NX):
        a, b = npt(xs[i], 1.0), npt(xs[i + 1], 1.0)
        mb.fo([g[i][NT], g[i + 1][NT], mb.v(b[0], b[1], -0.5795), mb.v(a[0], a[1], -0.5795)], "dune", UP, True)
    dec = DECOR.setdefault("backdrop", [])
    for k, x in enumerate(np.arange(-0.58, 0.08, 0.05)):           # wind ripples on the near dunes (print only)
        a, b = npt(x, 0.45), npt(x + 0.03, 0.55)
        dec.append(((a[0], a[1] + 0.001, a[2]), (b[0], b[1] + 0.001, b[2])))
    back = make_obj("backdrop", mb, root, origin=(0.0, 0.0, -0.57), smooth_angle=50)
    # pyramids
    pm = MB()
    for (cx, hw, H, zf) in ((-0.115, 0.118, 0.272, -0.547), (-0.455, 0.096, 0.228, -0.552)):
        zb, za = -0.5875, -0.584
        Hc = H - 0.030                                              # cap starts here
        k = Hc / H
        FL, FR, BL, BR = (cx - hw, 0.0, zf), (cx + hw, 0.0, zf), (cx - hw, 0.0, zb), (cx + hw, 0.0, zb)
        lerp = lambda p, t: (p[0] + (cx - p[0]) * t, p[1] + (H - p[1]) * t, p[2] + (za - p[2]) * t)
        tFL, tFR, tBL, tBR = lerp(FL, k), lerp(FR, k), lerp(BL, k), lerp(BR, k)
        for q, o in (([FL, FR, tFR, tFL], (0, 0.4, 1)), ([BL, FL, tFL, tBL], (-1, 0.3, 0.2)),
                     ([FR, BR, tBR, tFR], (1, 0.3, 0.2))):
            pm.fo([pm.v(*p) for p in q], "pyramid", o)
        ap = (cx, H, za)
        s = 1.04
        cfl = (cx + (tFL[0] - cx) * s, tFL[1] - 0.001, za + (tFL[2] - za) * s)
        cfr = (cx + (tFR[0] - cx) * s, tFR[1] - 0.001, za + (tFR[2] - za) * s)
        cbl = (cx + (tBL[0] - cx) * s, tBL[1] - 0.001, tBL[2]); cbr = (cx + (tBR[0] - cx) * s, tBR[1] - 0.001, tBR[2])
        for q, o in (([cfl, cfr, ap], (0, 0.4, 1)), ([cbl, cfl, ap], (-1, 0.3, 0.2)), ([cfr, cbr, ap], (1, 0.3, 0.2))):
            pm.fo([pm.v(*p) for p in q], "pyramidCap", o)
        dp = DECOR.setdefault("backdrop", [])
        for j in range(1, int(Hc / 0.019) + 1):                       # stone courses (print only)
            t = j * 0.019 / H
            a, b = lerp(FL, t), lerp(FR, t)
            dp.append(((a[0], a[1], a[2] + 0.0004), (b[0], b[1], b[2] + 0.0004)))
        dp.append((FL, tFL)); dp.append((FR, tFR))
    pyr = make_obj("pyramids", pm, back, origin=(-0.28, 0.0, -0.57), smooth_angle=20)
    # mountain: a height grid over its footprint, back face, right skirt
    mm = MB()
    NXm, NZm = 56, 22
    xg = np.linspace(MOUNT[0], MOUNT[1], NXm + 1); zg = np.linspace(MOUNT[3], MOUNT[2], NZm + 1)
    Hm = [[mount_h(x, z) for z in zg] for x in xg]
    gm = [[mm.v(xg[i], Hm[i][j], zg[j]) for j in range(NZm + 1)] for i in range(NXm + 1)]
    for i in range(NXm):
        for j in range(NZm):
            q = [gm[i][j], gm[i + 1][j], gm[i + 1][j + 1], gm[i][j + 1]]
            P = [Vector(mm.V[t]) for t in q]
            nrm = (P[1] - P[0]).cross(P[3] - P[0])
            nrm = nrm if nrm.y >= 0 else -nrm
            nrm.normalize()
            reg = "rock"
            mm.fo(q, reg, (0, 1, 0.3), True)
    for i in range(NXm):                                            # back face
        a, b = xg[i], xg[i + 1]
        mm.fo([gm[i][NZm], gm[i + 1][NZm], mm.v(b, 0.0, MOUNT[2]), mm.v(a, 0.0, MOUNT[2])], "rock", (0, 0, -1))
    for j in range(NZm):                                            # right edge skirt
        mm.fo([gm[NXm][j], gm[NXm][j + 1], mm.v(MOUNT[1], 0.0, zg[j + 1]), mm.v(MOUNT[1], 0.0, zg[j])], "rock",
              (1, 0, 0))
    # zigzag ledge path climbing the face
    cl = catmull(LEDGE, 0.006)
    mm.nr = True                                                   # the path takes the track's texel (too thin to print)
    for i in range(len(cl) - 1):
        (ax, az), (bx, bz) = cl[i], cl[i + 1]
        t = np.array([bx - ax, bz - az]); t /= np.linalg.norm(t) + 1e-9
        nn = np.array([-t[1], t[0]]) * 0.0105
        pa = [(ax + s * nn[0], az + s * nn[1]) for s in (-1, 1)]; pb = [(bx + s * nn[0], bz + s * nn[1]) for s in (-1, 1)]
        ha = mount_h(ax, az) + 0.0035; hb = mount_h(bx, bz) + 0.0035
        mm.fo([mm.v(pa[0][0], ha, pa[0][1]), mm.v(pa[1][0], ha, pa[1][1]), mm.v(pb[1][0], hb, pb[1][1]),
               mm.v(pb[0][0], hb, pb[0][1])], "ledge", UP)
    mm.nr = False
    rng = random.Random(51)
    for i, (x, z) in enumerate(((0.20, -0.425), (0.295, -0.448), (0.47, -0.43), (0.56, -0.47), (0.24, -0.50),
                                (0.38, -0.47), (0.52, -0.55), (0.14, -0.47))):
        h = mount_h(x, z); r = rng.uniform(0.008, 0.012)
        lumpy(mm, (x, h + r * 0.5, z), r, "shrub", seg=7, rings=4, sh=0.75, amp=0.3, seed=i + 60)
        for k in range(3):                                          # dry twigs poking out
            a = TAU * k / 3 + i
            tube(mm, [(x, h + r * 0.6, z), (x + 0.012 * math.cos(a), h + r * 1.5, z + 0.012 * math.sin(a))], 0.0009,
                 "shrub", seg=3)
    mtn = make_obj("mountain", mm, back, origin=(0.38, 0.0, -0.50), smooth_angle=40)
    return back, pyr, mtn


# ============================================================================================ palace
def papyrus_column(mb, x, z, H=0.200):
    """fat papyrus-bundle column: round base, swelling bundled shaft (eight stalks), three gold bands, an open
    papyrus capital with petal lobes, an abacus block"""
    lathe(mb, [(0.0, 0.0), (0.0205, 0.0), (0.0205, 0.0045), (0.0185, 0.0075), (0.0, 0.0078)], "stone", C=(x, 0, z),
          seg=16, smooth=True)
    lathe(mb, [(0.0, 0.0075), (0.0130, 0.0075), (0.0152, 0.022), (0.0150, 0.050), (0.0138, 0.100), (0.0124, 0.140),
               (0.0116, 0.148), (0.0, 0.149)], "column", C=(x, 0, z), seg=16, smooth=True,
          rfun=lambda th, i, k: 1.0 + 0.075 * abs(math.cos(4 * th)) if 0 < i < 7 else 1.0)
    for j, hb in enumerate((0.149, 0.154, 0.159)):
        lathe(mb, [(0.0, hb), (0.0128, hb), (0.0130, hb + 0.0034), (0.0, hb + 0.0035)], "gold", C=(x, 0, z), seg=16)
    lathe(mb, [(0.0, 0.162), (0.0118, 0.162), (0.0150, 0.170), (0.0200, 0.181), (0.0232, 0.190), (0.0236, 0.1935),
               (0.0, 0.1935)], "capital", C=(x, 0, z), seg=24, smooth=True,
          rfun=lambda th, i, k: 1.0 + (0.11 * math.cos(8 * th) if 1 < i < 6 else 0.0))
    box(mb, x - 0.0165, x + 0.0165, 0.1935, H, z - 0.0165, z + 0.0165, "stone", skip=("bottom",))


def build_palace(root):
    """Pharaoh's palace: paved platform, back wall with a painted frieze and a blue panel behind the throne, four
    papyrus columns, architrave with a gold roll and cavetto cornice, the winged sun disc, two obelisks with
    hieroglyph ticks, two lamp stands. Children `dais` (two steps) with `throne`, `palacePalms`."""
    mb = MB()
    x0, x1, zb, zf = PALACE
    dec = DECOR.setdefault("palace", [])
    box(mb, x0, x1, 0.0, 0.0075, zb, -0.395, "pave", skip=("bottom",))
    for z in np.arange(zb + 0.032, -0.40, 0.032):                     # flagstone joints (print only)
        dec.append(((x0, 0.0076, z), (x1, 0.0076, z)))
    for k, x in enumerate(np.arange(x0 + 0.03, x1, 0.042)):
        for z0_ in np.arange(zb, -0.40, 0.064):
            dec.append(((x + 0.021 * (k % 2), 0.0076, z0_), (x + 0.021 * (k % 2), 0.0076, z0_ + 0.032)))
    # back wall, frieze, panel
    box(mb, x0 + 0.006, x1 - 0.006, 0.0, 0.200, zb, zb + 0.015, "stone", skip=("bottom",))
    for k, x in enumerate(np.arange(x0 + 0.008, x1 - 0.012, 0.0115)):
        box(mb, x, x + 0.0085, 0.168, 0.190, zb + 0.015, zb + 0.0175, "paint" if k % 2 == 0 else "gold",
            skip=("back", "bottom"))
    box(mb, -0.405, -0.315, 0.070, 0.152, zb + 0.015, zb + 0.017, "paint", skip=("back", "bottom"))
    for j in range(5):                                                 # little gold stars on the panel
        sx = -0.395 + 0.0175 * j + 0.004
        lathe(mb, [(0.0, 0.0), (0.0035, 0.0), (0.0, 0.0012)], "gold", C=(sx, 0.135 - 0.03 * (j % 2), zb + 0.017),
              A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=5)
    for x in COLS_X:
        papyrus_column(mb, x, COL_Z)
    # architrave, roof slab, gold roll, cornice
    box(mb, x0 + 0.002, x1 - 0.002, 0.200, 0.224, COL_Z - 0.018, COL_Z + 0.018, "stone", skip=())
    box(mb, x0 + 0.004, x1 - 0.004, 0.204, 0.214, zb, COL_Z - 0.018, "stone", skip=("front",))
    tube(mb, [(x0, 0.2255, COL_Z + 0.0185), (x1, 0.2255, COL_Z + 0.0185)], 0.0030, "gold", seg=7)
    for s in (x0, x1):
        tube(mb, [(s, 0.2255, COL_Z + 0.0185), (s, 0.2255, zb + 0.004)], 0.0030, "gold", seg=7)
    cav = [(0.0, 0.0), (0.004, 0.003), (0.009, 0.009), (0.013, 0.016), (0.0145, 0.019), (0.0145, 0.0215),
           (-0.005, 0.0215), (-0.005, 0.0)]                               # cornice profile (d out, h up), CCW
    rings = []
    for x in (x0 - 0.004, x1 + 0.004):
        rings.append([(x, 0.2285 + h, COL_Z + 0.0185 + d) for d, h in cav])
    nrm = prof_normals(cav)
    sweep(mb, rings, lambda i, k: "stone", lambda i, k: (0, nrm[k][1], nrm[k][0]), cap_reg="stone", smooth=False)
    box(mb, x0 - 0.004, x1 + 0.004, 0.2285, 0.250, zb, COL_Z + 0.0135, "stone", skip=("bottom", "front"))
    # winged sun disc on the architrave front
    zc = COL_Z + 0.018
    lathe(mb, [(0.0, 0.0), (0.0090, 0.0), (0.0088, 0.0018), (0.0, 0.0030)], "gold", C=(PAL_C[0], 0.212, zc),
          A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=16)
    for s in (-1, 1):
        for row, (hh, L, reg) in enumerate(((0.0040, 0.070, "wing"), (-0.0010, 0.060, "gold"), (-0.0055, 0.048, "wing"))):
            poly = [(0.0085, -0.0024), (L, -0.0005 - 0.0012 * row), (L + 0.004, 0.0018), (0.0085, 0.0028)]
            extrude(mb, [(PAL_C[0] + s * a, 0.212 + hh + b) for a, b in (poly if s > 0 else poly[::-1])],
                    zc, zc + 0.0016 + 0.0004 * row, reg, back=False)
        lathe(mb, [(0.0, 0.0), (0.0022, 0.0), (0.0016, 0.006), (0.0, 0.0068)], "gold",
              C=(PAL_C[0] + s * 0.0085, 0.214, zc + 0.002), seg=6)               # the two cobras
    # obelisks
    for ox, oz in OBELISKS:
        box(mb, ox - 0.021, ox + 0.021, 0.0, 0.012, oz - 0.021, oz + 0.021, "stone", skip=("bottom",))
        b0, b1, H = 0.0135, 0.0088, 0.236
        q0 = [(ox - b0, oz - b0), (ox + b0, oz - b0), (ox + b0, oz + b0), (ox - b0, oz + b0)]
        q1 = [(ox - b1, oz - b1), (ox + b1, oz - b1), (ox + b1, oz + b1), (ox - b1, oz + b1)]
        for k in range(4):
            a, b = k, (k + 1) % 4
            mx = (q0[a][0] + q0[b][0]) / 2 - ox; mz = (q0[a][1] + q0[b][1]) / 2 - oz
            mb.fo([mb.v(q0[a][0], 0.012, q0[a][1]), mb.v(q0[b][0], 0.012, q0[b][1]), mb.v(q1[b][0], H, q1[b][1]),
                   mb.v(q1[a][0], H, q1[a][1])], "obelisk", (mx, 0.05, mz))
            mb.fo([mb.v(q1[a][0], H, q1[a][1]), mb.v(q1[b][0], H, q1[b][1]), mb.v(ox, H + 0.022, oz)], "gold",
                  (mx, 0.4, mz))
        for j in range(9):                                             # hieroglyph ticks on the front (print only)
            hh = 0.040 + j * 0.020
            w = b0 - (b0 - b1) * (hh - 0.012) / (H - 0.012)
            zz = oz + w + 0.0003
            if j % 3 == 0:
                dec.append(((ox - w * 0.5, hh, zz), (ox + w * 0.5, hh, zz)))
            elif j % 3 == 1:
                dec.append(((ox - w * 0.4, hh - 0.004, zz), (ox - w * 0.4, hh + 0.004, zz)))
                dec.append(((ox + w * 0.2, hh - 0.004, zz), (ox + w * 0.5, hh + 0.004, zz)))
            else:
                dec.append(((ox - w * 0.45, hh, zz), (ox, hh + 0.005, zz))); dec.append(((ox, hh + 0.005, zz), (ox + w * 0.45, hh, zz)))
    # two lamp stands at the front corners of the dais
    for lx in (-0.462, -0.258):
        lz = DAIS_FRONT - 0.012
        lathe(mb, [(0.0, 0.0), (0.0075, 0.0), (0.0035, 0.004), (0.0022, 0.010), (0.0018, 0.060), (0.0060, 0.064),
                   (0.0092, 0.070), (0.0, 0.069)], "gold", C=(lx, 0, lz), seg=10)
    pal = make_obj("palace", mb, root, origin=(PAL_C[0], 0.0, PAL_C[1]), smooth_angle=50, bevel=0.0006, bevel_angle=60)
    # dais: two steps with gold edges
    dm = MB()
    box(dm, -0.452, -0.268, 0.0075, 0.0185, -0.51, DAIS_FRONT, "dais", skip=("bottom",))
    box(dm, -0.435, -0.285, 0.0185, DAIS_TOP, -0.51, DAIS_FRONT - 0.018, "dais", skip=("bottom",))
    tube(dm, [(-0.452, 0.0187, DAIS_FRONT + 0.0005), (-0.268, 0.0187, DAIS_FRONT + 0.0005)], 0.0013, "gold", seg=5)
    tube(dm, [(-0.435, 0.0302, DAIS_FRONT - 0.0175), (-0.285, 0.0302, DAIS_FRONT - 0.0175)], 0.0013, "gold", seg=5)
    dais = make_obj("dais", dm, pal, origin=(-0.36, 0.0, -0.43), smooth_angle=40)
    # throne: block seat on lion legs, high back with a curved top, arm rests, red cushion, footstool
    tm = MB()
    tx, tz = THRONE
    h0 = DAIS_TOP
    box(tm, tx - 0.024, tx + 0.024, h0 + 0.024, h0 + 0.034, tz - 0.020, tz + 0.020, "throne")
    for sx in (-1, 1):
        for sz in (-1, 1):
            lx, lz = tx + sx * 0.019, tz + sz * 0.015
            tube(tm, [(lx, h0 + 0.025, lz), (lx, h0 + 0.012, lz + 0.002 * sz), (lx, h0 + 0.004, lz + 0.001),
                      (lx, h0 + 0.0015, lz + 0.004)], [0.0034, 0.0028, 0.0030, 0.0036], "throne", seg=6)
    back_poly = [(tx - 0.022, h0 + 0.034), (tx + 0.022, h0 + 0.034), (tx + 0.022, h0 + 0.098)] + \
        [(tx + 0.022 * math.cos(math.pi * k / 8), h0 + 0.098 + 0.012 * math.sin(math.pi * k / 8)) for k in range(1, 8)] + \
        [(tx - 0.022, h0 + 0.098)]
    extrude(tm, back_poly, tz - 0.021, tz - 0.013, "throne")
    for sx in (-1, 1):
        box(tm, tx + sx * 0.024 - 0.004, tx + sx * 0.024 + 0.002 * sx, h0 + 0.034, h0 + 0.052, tz - 0.018, tz + 0.016,
            "throne")
        lumpy(tm, (tx + sx * 0.0225, h0 + 0.054, tz + 0.016), 0.0045, "throne", seg=8, rings=5, sh=0.9, amp=0.05)
    lumpy(tm, (tx, h0 + 0.0365, tz - 0.001), 0.019, "cushion", seg=12, rings=5, sh=0.18, sz=0.95, amp=0.04)
    extrude(tm, [(tx - 0.012, h0 + 0.060), (tx + 0.012, h0 + 0.060), (tx + 0.012, h0 + 0.088), (tx - 0.012, h0 + 0.088)],
            tz - 0.0128, tz - 0.0120, "cushion", back=False)
    box(tm, tx - 0.016, tx + 0.016, h0, h0 + 0.009, tz + 0.026, tz + 0.040, "throne", skip=("bottom",))
    throne = make_obj("throne", tm, dais, origin=(tx, h0, tz), smooth_angle=45)
    return pal, dais, throne


# ============================================================================================ houses
def build_houses(root):
    """two flat-roofed mud-brick houses: plastered walls with patches of bare brick (printed as single lines), dark
    doorways under a wooden lintel, a small window, beam ends, low parapets, roof mats and jars, an outside stair,
    a bench and a water jar by the doors. Child `doorMarks` (red paint on lintels and posts, hidden until S07)."""
    mb = MB()
    dm = MB()
    rng = random.Random(61)
    dec = DECOR.setdefault("houses", [])
    for hi, (x0, x1, zb, zf, H) in enumerate(HOUSES):
        dx = x0 + (x1 - x0) * (0.38 if hi == 0 else 0.55)
        dw, dh = 0.0145, 0.052
        wx = x0 + (x1 - x0) * (0.80 if hi == 0 else 0.20)
        win = [(wx - 0.008, 0.050), (wx + 0.008, 0.050), (wx + 0.008, 0.064), (wx - 0.008, 0.064)]
        door = [(dx - dw, 0.0), (dx + dw, 0.0), (dx + dw, dh), (dx - dw, dh)]
        outer = [(x0, 0.0), (x1, 0.0), (x1, H), (x0, H)]
        tris = tessellate_polygon([[Vector((a, b, 0)) for a, b in outer], [Vector((a, b, 0)) for a, b in door],
                                   [Vector((a, b, 0)) for a, b in win]])
        allp = outer + door + win
        vi = [mb.v(a, b, zf) for a, b in allp]
        for t in tris:
            mb.fo([vi[i] for i in t], "mudWall", (0, 0, 1))
        for hole, depth in ((door, 0.010), (win, 0.008)):
            for i in range(4):
                a, b = hole[i], hole[(i + 1) % 4]
                if a[1] == 0.0 and b[1] == 0.0:
                    continue
                ddx, ddh = b[0] - a[0], b[1] - a[1]
                mb.fo([mb.v(a[0], a[1], zf), mb.v(b[0], b[1], zf), mb.v(b[0], b[1], zf - depth),
                       mb.v(a[0], a[1], zf - depth)], "mudWall", (-ddh, ddx, 0))
            box(mb, hole[0][0], hole[1][0], hole[0][1], hole[2][1], zf - depth - 0.001, zf - depth, "doorway",
                skip=("back",))
        box(mb, x0, x1, 0.0, H, zb, zf, "mudWall", skip=("front", "bottom", "top"))
        # roof, parapet, mats, beam ends
        box(mb, x0 + 0.005, x1 - 0.005, H - 0.003, H, zb + 0.005, zf - 0.005, "roof", skip=("bottom",))
        for (a0, a1, c0, c1) in ((x0 - 0.001, x1 + 0.001, zf - 0.005, zf + 0.001), (x0 - 0.001, x1 + 0.001, zb, zb + 0.005),
                                 (x0 - 0.001, x0 + 0.005, zb, zf), (x1 - 0.005, x1 + 0.001, zb, zf)):
            box(mb, a0, a1, H, H + 0.010, c0, c1, "mudWall", skip=("bottom",))
        mx0 = x0 + 0.012 + 0.01 * hi
        box(mb, mx0, mx0 + 0.045, H, H + 0.0025, zb + 0.020, zb + 0.070, "roof", skip=("bottom",))
        for k in range(1, 9):                                     # mat weave lines (print only)
            xx = mx0 + 0.005 * k
            dec.append(((xx, H + 0.0026, zb + 0.020), (xx, H + 0.0026, zb + 0.070)))
        for k, x in enumerate(np.linspace(x0 + 0.012, x1 - 0.012, 5)):
            if abs(x - dx) < 0.02 or abs(x - wx) < 0.012:
                continue
            lathe(mb, [(0.0, 0.0), (0.0032, 0.0), (0.0032, 0.010), (0.0, 0.0105)], "wood",
                  C=(x, H - 0.008, zf - 0.002), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=6)
        # lintel beam over the door, sill under the window
        box(mb, dx - dw - 0.007, dx + dw + 0.007, dh, dh + 0.0095, zf - 0.002, zf + 0.0035, "wood", skip=("back",))
        box(mb, wx - 0.011, wx + 0.011, 0.0465, 0.050, zf - 0.002, zf + 0.003, "wood", skip=("back",))
        # bare-brick patches: courses and head joints printed as single lines
        for (px0, px1, ph0, ph1) in ((x0 + 0.003, x0 + 0.040, 0.004, 0.034), (x1 - 0.034, x1 - 0.004, H - 0.032, H - 0.006)):
            if hi == 1:
                px0, px1 = px0 + 0.004, px1 - 0.002
            for r, hb in enumerate(np.arange(ph0, ph1, 0.0075)):
                dec.append(((px0, hb, zf + 0.0003), (px1, hb, zf + 0.0003)))
                for xx in np.arange(px0 + (r % 2) * 0.0075, px1, 0.015):
                    if abs(xx - dx) > dw + 0.002 or hb > dh:
                        dec.append(((xx, hb, zf + 0.0003), (xx, min(hb + 0.0075, ph1), zf + 0.0003)))
        # door marks: a smear along the lintel and down both posts (wobbly outlines), proud of the wall
        zm = zf + 0.0036
        poly = [(dx - dw - 0.008 + (2 * dw + 0.016) * k / 6, dh + 0.0105 + 0.0010 * math.sin(k * 2.1)) for k in range(7)]
        poly = poly + [(p[0], p[1] + 0.0085 + 0.0010 * math.sin(k * 3.3)) for k, p in enumerate(poly)][::-1]
        extrude(dm, poly, zf + 0.0002, zf + 0.0012, "doorMark", back=False)
        for s in (-1, 1):
            px = dx + s * (dw + 0.0045)
            post = [(px - 0.0042, 0.016), (px + 0.0040, 0.015), (px + 0.0046, 0.034), (px + 0.0040, dh),
                    (px - 0.0044, dh), (px - 0.0038, 0.033)]
            extrude(dm, post, zf + 0.0002, zf + 0.0012, "doorMark", back=False)
        # a bench and a water jar by the door
        bx0 = dx + dw + 0.010
        if bx0 + 0.026 < x1:
            box(mb, bx0, bx0 + 0.026, 0.0, 0.010, zf + 0.002, zf + 0.011, "mudWall", skip=("bottom",))
        jx = dx - dw - 0.012
        lathe(mb, [(0.0, 0.0), (0.0045, 0.0), (0.0078, 0.006), (0.0082, 0.012), (0.0052, 0.020), (0.0034, 0.022),
                   (0.0042, 0.0245), (0.0, 0.021)], "jar", C=(jx, 0, zf + 0.010), seg=12)
        for j in range(2):                                        # jars on the roof
            rx = x1 - 0.020 - 0.013 * j; rz = zb + 0.020 + 0.012 * j
            lathe(mb, [(0.0, H), (0.004, H), (0.0062, H + 0.006), (0.0058, H + 0.011), (0.0032, H + 0.016),
                       (0.0040, H + 0.018), (0.0, H + 0.0165)], "jar", C=(rx, 0, rz), seg=10)
    # outside stair up the left house's left side
    x0, x1, zb, zf, H = HOUSES[0]
    n = 7
    for k in range(n):
        h1 = H * (k + 1) / n
        za = zf - 0.006 - k * (zf - zb - 0.03) / n
        box(mb, x0 - 0.016, x0, h1 - H / n, h1, za - (zf - zb - 0.03) / n, za, "mudWall", skip=("bottom",))
    box(mb, x0 - 0.016, x0, 0.0, H * 0.86, zb + 0.004, zf - 0.006 - (zf - zb - 0.03) * (n - 1) / n, "mudWall",
        skip=("bottom",))
    hs = make_obj("houses", mb, root, origin=(-0.02, 0.0, -0.47), smooth_angle=45, bevel=0.0006, bevel_angle=60)
    marks = make_obj("doorMarks", dm, hs, origin=(-0.02, 0.0, -0.41), smooth_angle=45)
    return hs, marks


# ============================================================================================ brick yard
BRICK = (0.0150, 0.0062, 0.0075)              # length, height, width


def brick(mb, x, h, z, yaw, rng, reg="brick", s=1.0, dec=None):
    L, Hh, Wd = BRICK[0] * s, BRICK[1] * s, BRICK[2] * s
    c, sn = math.cos(yaw), math.sin(yaw)
    j = lambda: rng.uniform(-0.0004, 0.0004)
    corners = [(-L / 2, -Wd / 2), (L / 2, -Wd / 2), (L / 2, Wd / 2), (-L / 2, Wd / 2)]
    bot = [mb.v(x + a * c - b * sn, h, z + a * sn + b * c) for a, b in corners]
    top = [mb.v(x + (a + j()) * c - b * sn, h + Hh + j() * 0.5, z + (a + j()) * sn + b * c) for a, b in corners]
    mb.fo(top, reg, UP)
    if dec is not None:                               # printed as single outline lines (decorOnly brick)
        for k in range(4):
            dec.append((mb.V[top[k]], mb.V[top[(k + 1) % 4]]))
            dec.append((mb.V[bot[k]], mb.V[top[k]]))
            dec.append((mb.V[bot[k]], mb.V[bot[(k + 1) % 4]]))
    for k in range(4):
        a, b = corners[k], corners[(k + 1) % 4]
        mx, mz = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
        mb.fo([bot[k], bot[(k + 1) % 4], top[(k + 1) % 4], top[k]], reg, (mx * c - mz * sn, 0, mx * sn + mz * c))


def build_brickyard(root):
    """the brick yard: a trampled mud floor, a half-built wall of single bricks in running bond with a ragged top and
    an earth ramp, three cross-stacked piles, bricks drying in rows, wooden moulds, a water trough, a mud pit with a
    hoe; child `straw` (the straw pile). Low things only near Miriam's mark (-0.20, -0.06)."""
    rng = random.Random(71)
    mb = MB()
    x0, x1, z0, z1 = YARD
    yard = blob_poly(-0.36, -0.11, 0.115, 7, n=24, amp=0.10)
    yard[:, 1] = np.clip((yard[:, 1] + 0.11) * 0.86 - 0.11, z0, z1)
    yard[:, 0] = np.clip(yard[:, 0], x0, x1 - 0.002)
    ngon_top(mb, [tuple(p) for p in yard], 0.0024, "mud", hb=0.0)
    # half-built wall along the back, running bond, ragged top; ramp of earth up its right end
    wz = -0.186
    nrow = 10
    bdec = DECOR.setdefault("brickyard", [])
    for r in range(nrow):
        h = r * BRICK[1]
        top_x = -0.330 - 0.0075 * max(0, r - 5) ** 1.3                 # higher rows stop earlier: a stepped end
        x = -0.468 + (BRICK[0] / 2 if r % 2 else 0.0)
        while x + BRICK[0] <= top_x + 1e-4:
            if r == nrow - 1 and rng.random() < 0.35:
                x += BRICK[0] + 0.0012; continue
            brick(mb, x + BRICK[0] / 2, h, wz, 0.0, rng)
            if r % 2 == 0 and x > -0.468 + 1e-4:            # head joints on every other course (print only)
                bdec.append(((x - 0.0006, h, wz + BRICK[2] / 2), (x - 0.0006, h + BRICK[1], wz + BRICK[2] / 2)))
            x += BRICK[0] + 0.0012
        box(mb, -0.4675, top_x - 0.0012, h, h + BRICK[1], wz - BRICK[2] / 2 + 0.0012, wz + BRICK[2] / 2 - 0.0012, "brick",
            skip=("bottom",))                                 # mortar core: no paper shows between the bricks
        if r % 2 == 0 and r > 0:                            # a bed joint every other course
            bdec.append(((-0.468, h, wz + BRICK[2] / 2), (top_x, h, wz + BRICK[2] / 2)))
    ramp = [(-0.333, 0.0), (-0.268, 0.0), (-0.333, 0.050)]
    extrude(mb, [(a, b) for a, b in ramp], wz - 0.006, wz + 0.006, "mud",
            X=lambda a, b: (a, b), back=True)
    # cross-stacked piles
    for (sx, sz, layers) in ((-0.448, -0.112, 5), (-0.360, -0.150, 4), (-0.318, -0.135, 4)):
        for L_ in range(layers):
            yaw = 0.0 if L_ % 2 == 0 else math.pi / 2
            for k in range(3):
                off = (k - 1) * (BRICK[2] + 0.0011)
                bx, bz = (sx, sz + off) if L_ % 2 == 0 else (sx + off, sz)
                brick(mb, bx, 0.0024 + L_ * BRICK[1], bz, yaw + rng.uniform(-0.04, 0.04), rng, dec=bdec)
    # bricks drying in rows (flat, low: next to Miriam's mark)
    for r in range(3):
        for k in range(5):
            brick(mb, -0.296 + k * 0.0175, 0.0024, -0.118 + r * 0.030 + rng.uniform(-0.001, 0.001),
                  rng.uniform(-0.06, 0.06), rng, s=0.95, dec=bdec)
    # wooden moulds: double frames lying flat
    for (mx, mz, a) in ((-0.262, -0.162, 0.3), (-0.283, -0.040, -0.2)):
        c, s = math.cos(a), math.sin(a)
        P = lambda u, v: (mx + u * c - v * s, mz + u * s + v * c)
        for u0, u1, v0, v1 in ((-0.019, 0.019, -0.011, -0.0085), (-0.019, 0.019, 0.0085, 0.011),
                               (-0.019, -0.0165, -0.011, 0.011), (0.0165, 0.019, -0.011, 0.011),
                               (-0.0012, 0.0012, -0.011, 0.011), (0.019, 0.032, -0.0015, 0.0015)):
            ngon_top(mb, [P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1)], 0.0072, "trough", hb=0.0024)
    # trough with water
    tx, tz = -0.372, -0.040
    box(mb, tx - 0.033, tx + 0.033, 0.0024, 0.019, tz - 0.0165, tz + 0.0165, "trough", skip=("bottom", "top"))
    for (a0, a1, c0, c1) in ((tx - 0.033, tx + 0.033, tz - 0.0165, tz - 0.0135), (tx - 0.033, tx + 0.033, tz + 0.0135, tz + 0.0165),
                             (tx - 0.033, tx - 0.030, tz - 0.0165, tz + 0.0165), (tx + 0.030, tx + 0.033, tz - 0.0165, tz + 0.0165)):
        ngon_top(mb, [(a0, c0), (a1, c0), (a1, c1), (a0, c1)], 0.019, "trough")
    ngon_top(mb, [(tx - 0.030, tz - 0.0135), (tx + 0.030, tz - 0.0135), (tx + 0.030, tz + 0.0135), (tx - 0.030, tz + 0.0135)],
             0.0165, "water")
    for sx in (-1, 1):
        box(mb, tx + sx * 0.027 - 0.003, tx + sx * 0.027 + 0.003, 0.0, 0.0026, tz - 0.018, tz + 0.018, "trough")
    # mud pit and a hoe
    pit = blob_poly(-0.452, -0.168, 0.020, 3, n=14, amp=0.15)
    ngon_top(mb, [tuple(p) for p in pit], 0.0032, "mud", hb=0.0024)
    tube(mb, [(-0.468, 0.0045, -0.150), (-0.430, 0.0060, -0.140)], 0.0013, "trough", seg=5)
    box(mb, -0.433, -0.427, 0.0035, 0.0055, -0.1475, -0.1325, "trough")
    yd = make_obj("brickyard", mb, root, origin=(-0.36, 0.0, -0.11), smooth_angle=35)
    # straw pile: lumpy mound, loose stalks round it
    sm = MB()
    sx, sz = -0.452, -0.040
    lathe(sm, [(0.0, 0.0), (0.028, 0.0), (0.026, 0.008), (0.019, 0.019), (0.009, 0.026), (0.0, 0.028)], "straw",
          C=(sx, 0.0024, sz), seg=16, rfun=lambda th, i, k: 1.0 + (0.12 * (nz(i, k, 7) - 0.5) * 2 if 0 < i < 5 else 0.0))
    for k in range(22):
        a = rng.uniform(0, TAU); r = rng.uniform(0.010, 0.030); hgt = 0.026 * (1 - (r / 0.031) ** 2) + 0.003
        p0 = (sx + r * math.cos(a), 0.0024 + max(hgt, 0.002), sz + r * math.sin(a))
        b = rng.uniform(0, TAU)
        tube(sm, [p0, (p0[0] + 0.012 * math.cos(b), p0[1] + 0.002, p0[2] + 0.012 * math.sin(b))], 0.0008, "straw",
             seg=3, caps=False)
    straw = make_obj("straw", sm, yd, origin=(sx, 0.0, sz), smooth_angle=60)
    return yd, straw


# ============================================================================================ people (templates)
PEOPLE_OFF = {"man": 0.0, "jar": 0.052, "bundle": 0.104, "mother": 0.160, "bend": 0.232, "carry": 0.284,
              "sheep": 0.340}                                  # x offsets of the templates in the people drawing
PEOPLE_H = 0.122                                               # a grown-up's height (contract asked 0.11-0.13 now)


def _bend(theta, hip=0.050, ramp=0.016):
    """forward bend of everything above the hips (toward +z), ramped in over `ramp`"""
    def f(p):
        x, h, z = p
        if h <= hip:
            return p
        t = theta * min(1.0, (h - hip) / ramp)
        c, s_ = math.cos(t), math.sin(t)
        return (x, hip + (h - hip) * c - z * s_, (h - hip) * s_ + z * c)
    return f


def _figure(mb, s=1.0, robe="robeA", woman=False, beard=False, bend=0.0, arms=None, head_load=None):
    """a small background person (local, base at the origin, facing +z), about PEOPLE_H * s high: a robe flaring to
    the hem with a sash, sleeves and hands, a head-cloth framing the face (headband for men), eyes and nose as a hint
    of a face, sandalled feet. arms = ((hand L), (hand R)) in final (posed) coordinates; bend tilts the body forward."""
    H = PEOPLE_H * s
    k = H / 0.122
    xf = _bend(math.radians(bend)) if bend else (lambda p: p)
    mb.xf = xf if bend else None
    fl = 1.10 if woman else 1.0
    lathe(mb, [(0.0, 0.0), (0.0150 * k * fl, 0.0), (0.0146 * k * fl, 0.006 * k), (0.0118 * k, 0.040 * k),
               (0.0098 * k, 0.066 * k), (0.0104 * k, 0.082 * k), (0.0098 * k, 0.088 * k), (0.0056 * k, 0.093 * k),
               (0.0, 0.094 * k)], robe, seg=8, smooth=True,
          rfun=lambda th, i, kk: 1.0 + (0.05 * math.cos(3 * th + i) if 0 < i < 4 else 0.0))   # a few soft folds
    lathe(mb, [(0.0105 * k, 0.051 * k), (0.0113 * k, 0.058 * k), (0.0105 * k, 0.065 * k)], "cloth", seg=8)   # sash
    if not woman:                                       # a shawl over the shoulders (a colourable cloth patch)
        lathe(mb, [(0.0118 * k, 0.068 * k), (0.0120 * k, 0.078 * k), (0.0114 * k, 0.086 * k), (0.0090 * k, 0.0905 * k),
                   (0.0060 * k, 0.0935 * k)], "cloth", seg=8)
    hc = (0.0, 0.1035 * k, 0.001 * k)
    sphere(mb, hc, 0.0098 * k, "skin", seg=8, rings=5)
    sphere(mb, (hc[0], hc[1] - 0.0010 * k, hc[2] + 0.0098 * k), 0.0018 * k, "skin", seg=4, rings=2)      # nose
    cap = [(0.0, 0.0115 * k), (0.0075 * k, 0.0090 * k), (0.0112 * k, 0.0025 * k), (0.0116 * k, -0.0050 * k),
           (0.0120 * k, -0.0150 * k), (0.0128 * k, -0.0215 * k)]
    cap = cap[::-1]                                     # walked bottom -> top (lathe convention: outward normals)
    lathe(mb, cap, "cloth", C=hc, seg=8, smooth=True,
          rfun=lambda th, i, kk: 1.0 if (math.sin(th) < 0.30 or i >= len(cap) - 2) else 0.55)   # open over the face
    mb.nr = True
    for sx in (-1, 1):                                                                   # eyes (dark texel)
        sphere(mb, (hc[0] + sx * 0.0036 * k, hc[1] + 0.0012 * k, hc[2] + 0.0086 * k), 0.0013 * k, "eye", seg=4,
               rings=2)
    if not woman:
        tube(mb, [(hc[0] + 0.0105 * k * math.cos(TAU * j / 10), hc[1] + 0.0042 * k, hc[2] + 0.0105 * k * math.sin(TAU * j / 10))
                  for j in range(10)], 0.0011 * k, "band", seg=3, closed=True)                   # headband
    if beard:
        lumpy(mb, (hc[0], hc[1] - 0.0080 * k, hc[2] + 0.0062 * k), 0.0050 * k, "beard", seg=7, rings=4, sh=1.1,
              sz=0.7, amp=0.12, seed=5)
    for sx in (-1, 1):                                                                   # feet peeping out
        box(mb, sx * 0.0055 * k - 0.0028 * k, sx * 0.0055 * k + 0.0028 * k, 0.0, 0.0025 * k, 0.004 * k, 0.0175 * k,
            "band", skip=("bottom",))
    mb.nr = False
    if head_load == "bundle":
        lumpy(mb, (0.0, 0.120 * k, 0.0), 0.0085 * k, "bundle", seg=8, rings=5, sh=0.6, amp=0.14, seed=9)
    mb.xf = None
    sh = [xf((sx * 0.0100 * k, 0.0870 * k, 0.0)) for sx in (-1, 1)]
    if arms is None:
        arms = ((-0.0128 * k, 0.050 * k, 0.004 * k), (0.0128 * k, 0.050 * k, 0.004 * k))
    for sh_, hand in zip(sh, arms):
        hand = Vector(hand); sv = Vector(sh_)
        elbow = (sv + hand) / 2 + Vector((0.0040 * k * (1 if hand.x > 0 else -1), -0.002 * k, -0.002 * k))
        tube(mb, [tuple(sv), tuple(elbow), tuple(hand)], [0.0040 * k, 0.0034 * k, 0.0030 * k], robe, seg=5)
        sphere(mb, tuple(hand), 0.0029 * k, "skin", seg=5, rings=3)
    return hc, k


def person(kind, mb):
    """the people templates (P offset side by side in the one people drawing)"""
    off = PEOPLE_OFF[kind]
    mb.pmap = lambda p, o=off: (p[0] + o, p[1], p[2])
    if kind == "sheep":
        lathe(mb, [(0.0, -0.011), (0.0080, -0.0095), (0.0108, -0.003), (0.0108, 0.005), (0.0080, 0.0105), (0.0, 0.012)],
              "wool", C=(0, 0.024, 0), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=10,
              rfun=lambda th, i, k: 1.0 + 0.11 * math.cos(5 * th + 2 * i))
        for sx in (-1, 1):
            for sz in (-1, 1):
                tube(mb, [(sx * 0.0050, 0.018, sz * 0.0065), (sx * 0.0050, 0.0, sz * 0.0065)], 0.0014, "sheepFace", seg=4)
        lumpy(mb, (0, 0.032, 0.0150), 0.0070, "sheepFace", seg=8, rings=5, sh=0.95, sz=1.2, amp=0.05, seed=3)
        for sx in (-1, 1):
            blade(mb, [(sx * 0.004, 0.034, 0.012), (sx * 0.0095, 0.031, 0.0095)], [0.0032, 0.0], "sheepFace", nrm=(0, 1, 0))
        lumpy(mb, (0, 0.037, 0.0125), 0.0045, "wool", seg=7, rings=4, sh=0.7, amp=0.15, seed=4)
    elif kind == "man":                                       # a shepherd with a staff
        hc, k = _figure(mb, 1.0, "robeA", beard=True,
                        arms=((-0.0128, 0.050, 0.004), (0.0150, 0.068, 0.010)))
        tube(mb, [(0.0160, 0.0, 0.011), (0.0158, 0.128, 0.011), (0.0130, 0.134, 0.011)], 0.0013, "bundle", seg=5)
    elif kind == "jar":                                       # a woman with a water jar on her head
        hc, k = _figure(mb, 0.97, "robeB", woman=True,
                        arms=((-0.0128, 0.050, 0.004), (0.0060, 0.1215, 0.002)))
        mb.nr = True
        lathe(mb, [(0.0, 0.110), (0.0035, 0.110), (0.0058, 0.1155), (0.0055, 0.121), (0.0030, 0.126), (0.0040, 0.128),
                   (0.0, 0.127)], "jar", seg=10)
        mb.nr = False
    elif kind == "bundle":                                    # a man with a bundle over his shoulder
        hc, k = _figure(mb, 1.02, "robeC", beard=True,
                        arms=((-0.0128, 0.050, 0.004), (0.0105, 0.099, -0.003)))
        lumpy(mb, (0.0125, 0.094, -0.008), 0.0130, "bundle", seg=9, rings=5, sh=0.85, amp=0.14, seed=11)
        tube(mb, [(0.0105, 0.099, -0.003), (0.0110, 0.100, -0.008)], 0.0012, "band", seg=4)
    elif kind == "mother":                                    # a mother leading a child by the hand
        _figure(mb, 0.97, "robeB", woman=True, head_load="bundle",
                arms=((-0.0128, 0.050, 0.004), (0.0170, 0.053, 0.004)))
        cx = 0.026
        mb.pmap = lambda p, o=off: (p[0] + o, p[1], p[2])
        sub = MB()
        _figure(sub, 0.58, "robeC", arms=((-0.0090, 0.053, 0.004), (0.0074, 0.029, 0.003)))
        sub.pmap = None
        mb.add(sub, lambda q: (q[0] + cx, q[1], q[2]))
        for i in range(len(mb.P) - len(sub.V), len(mb.P)):           # the child's P follows the offset too
            q = mb.V[i]; mb.P[i] = (q[0] + off, q[1], q[2])
    elif kind == "bend":                                      # a worker bending to lift a brick
        hc, k = _figure(mb, 1.0, "robeA", beard=True, bend=48.0,
                        arms=((-0.0055, 0.0090, 0.040), (0.0055, 0.0090, 0.040)))
        mb.nr = True
        brick(mb, 0.0, 0.0, 0.041, 0.0, random.Random(3), reg="brick", s=0.80)
        mb.nr = False
    elif kind == "carry":                                     # a worker carrying a brick on his shoulder
        hc, k = _figure(mb, 1.0, "robeC", bend=8.0,
                        arms=((-0.0128, 0.050, 0.006), (0.0080, 0.1000, 0.004)))
        mb.nr = True
        brick(mb, 0.0115, 0.0915, 0.000, math.pi / 2, random.Random(4), reg="brick", s=0.80)
        mb.nr = False
    mb.pmap = None


def people_templates():
    t = {k: MB() for k in PEOPLE_OFF}
    for k, mb in t.items():
        person(k, mb)
    allm = MB()
    for k, mb in t.items():                                       # the drawing's raster source: all side by side
        allm.add(mb, lambda p: p)
    allm.V = list(allm.P)          # at their drawing places: stacked at the origin, merge-by-distance welded them
    return t, allm


def crowd(name, parent, tpls, spots, seed):
    rng = random.Random(seed)
    mb = MB()
    for i, (kind, x, z, yaw) in enumerate(spots):
        mb.add(tpls[kind], yaw_fn(x, z, math.radians(yaw), rng.uniform(0.92, 1.05),
                                  lean=(rng.uniform(-0.03, 0.03), rng.uniform(-0.04, 0.02))))
    cx = sum(s[1] for s in spots) / len(spots); cz = sum(s[2] for s in spots) / len(spots)
    return make_obj(name, mb, parent, origin=(round(cx, 3), 0.0, round(cz, 3)), smooth_angle=60)


# crowd spots (kind, x, z, yaw deg); all checked by CLEARANCE against the moves made while each crowd is shown
WEST_SPOTS = [("bend", -0.455, -0.150, 30), ("carry", -0.412, -0.158, -60), ("bend", -0.372, -0.098, 160),
              ("carry", -0.420, -0.078, 80), ("bend", -0.300, -0.168, -30), ("jar", -0.318, -0.090, 160),
              ("carry", -0.262, -0.132, -100), ("bend", -0.470, -0.092, 100)]
SHORE_SPOTS = [("jar", -0.088, -0.198, 30), ("man", 0.172, -0.228, -30), ("jar", 0.190, -0.198, -40),
               ("bundle", 0.176, -0.170, -20), ("sheep", 0.191, -0.140, -80), ("man", 0.188, -0.098, -60),
               ("mother", 0.190, -0.058, -50), ("bundle", 0.192, -0.026, -40)]
FAR_SPOTS = [("man", 0.470, -0.200, 10), ("jar", 0.500, -0.170, -10), ("mother", 0.476, -0.135, 20),
             ("bundle", 0.530, -0.125, -30), ("jar", 0.555, -0.092, -40), ("man", 0.505, -0.080, 0),
             ("bundle", 0.545, -0.050, -20), ("mother", 0.468, -0.058, 30), ("sheep", 0.535, -0.200, -70),
             ("sheep", 0.570, -0.150, -110)]


# ============================================================================================ palms (template)
def palm_template(H=0.235, seed=0):
    """a date palm (local, base at the origin): a gently curved ringed trunk, a crown of drooping serrated fronds,
    two date clusters"""
    mb = MB()
    rng = random.Random(seed)
    axis = lambda u: (0.012 * math.sin(1.6 * u) * u, H * u, 0.004 * u * u)
    rings = 18
    prof = []
    for i in range(rings + 1):
        u = i / rings
        r = 0.0068 * (1.25 - 0.35 * u) * (1.0 + (0.12 if i % 2 else 0.0)) + (0.004 * (1 - u / 0.12) if u < 0.12 else 0)
        prof.append((r, u))
    pts = [axis(u) for _, u in prof]
    tube(mb, pts, [r for r, _ in prof], "palmTrunk", seg=7)
    top = Vector(axis(1.0))
    for k in range(10):
        a = TAU * k / 10 + rng.uniform(-0.15, 0.15)
        d = Vector((math.cos(a), 0, math.sin(a)))
        up = 0.55 if k % 2 else 0.25
        L = rng.uniform(0.072, 0.088)
        P = [top + d * (L * t) + Vector((0, L * (up * t - (up + 0.55) * t * t), 0)) for t in np.linspace(0, 1, 7)]
        side = d.cross(Vector((0, 1, 0)))
        W = [0.004, 0.022, 0.026, 0.024, 0.018, 0.010, 0.0]
        L_, R_ = [], []
        for i, p in enumerate(P):
            wv = W[i] / 2 * (1.0 + (0.35 if i % 2 else -0.15))
            droop = Vector((0, -0.006 * (i / 6), 0))
            L_.append(mb.v(*(p - side * wv + droop))); R_.append(mb.v(*(p + side * wv + droop)))
            c = mb.v(*p) if i == 0 else None
        mids = [mb.v(*p) for p in P]
        for i in range(6):
            for sgn in (1, -1):
                mb.fo([mids[i], L_[i], L_[i + 1], mids[i + 1]], "frond", (0, sgn, 0))
                mb.fo([mids[i], mids[i + 1], R_[i + 1], R_[i]], "frond", (0, sgn, 0))
    for k in range(2):
        a = TAU * k / 2 + 0.6
        c = top + Vector((0.010 * math.cos(a), -0.012, 0.010 * math.sin(a)))
        lumpy(mb, tuple(c), 0.0075, "dates", seg=8, rings=5, sh=1.3, amp=0.18, seed=k + seed)
    return mb


PALACE_PALMS = [(-0.588, -0.535, 0.85, 0.3), (-0.158, -0.552, 0.95, 2.2)]
FAR_PALMS = [(0.468, -0.425, 1.0, 1.0, (0.0, -0.22)), (0.585, -0.168, 1.08, 2.6, (-0.03, 0.05)),
             (0.575, 0.005, 0.96, 4.4, (0.04, 0.04))]


# ============================================================================================ bush
def build_bush(root):
    """the thorn bush: a rocky rise (low in front), a gnarled acacia trunk that forks into an umbrella of thorny
    twigs spreading back and to the sides, a few leaf clusters; `bushFlame` at its centre top"""
    bx, bz = BUSH
    mb = MB()
    rng = random.Random(81)
    for i, (dx, dz, r, h) in enumerate(((0.0, -0.006, 0.032, 0.024), (-0.030, -0.018, 0.020, 0.018),
                                        (0.032, -0.016, 0.022, 0.020), (0.010, -0.040, 0.026, 0.028),
                                        (-0.020, 0.008, 0.014, 0.011), (0.022, 0.012, 0.012, 0.010),
                                        (0.048, -0.040, 0.016, 0.016), (-0.046, -0.042, 0.018, 0.017))):
        lumpy(mb, (bx + dx, 0.0, bz + dz), r, "bushRock", seg=9, rings=5, sh=h / r, sz=0.85, amp=0.18, seed=i + 90,
              smooth=False, flat_bottom=0.0)
    base = Vector((bx, 0.020, bz - 0.010))
    trunk = [base, base + Vector((0.004, 0.018, -0.004)), base + Vector((-0.002, 0.034, -0.008)),
             base + Vector((0.003, 0.046, -0.012))]
    tube(mb, [tuple(p) for p in trunk], [0.0058, 0.0050, 0.0044, 0.0038], "bushWood", seg=7)
    fork = trunk[-1]
    tips = []
    for k, (a, L, up) in enumerate(((2.6, 0.050, 0.030), (0.5, 0.048, 0.028), (1.55, 0.040, 0.036), (3.6, 0.042, 0.022),
                                    (5.6, 0.036, 0.020), (4.6, 0.030, 0.034))):
        d = Vector((math.cos(a), 0, -abs(math.sin(a)) * 0.9 - 0.15)).normalized()
        mid = fork + d * L * 0.5 + Vector((0, up * 0.7, 0))
        end = fork + d * L + Vector((0, up, 0))
        tube(mb, [tuple(fork), tuple(mid), tuple(end)], [0.0032, 0.0024, 0.0013], "bushWood", seg=5)
        tips.append((mid, end, d))
        for j in range(3):                                         # twigs off each branch
            t = 0.45 + 0.25 * j
            p = fork + (end - fork) * t
            b = Vector((math.cos(a + (j - 1) * 0.9), 0.0, -abs(math.sin(a + (j - 1) * 0.9)))).normalized()
            q = p + b * 0.018 + Vector((0, 0.012, 0))
            tube(mb, [tuple(p), tuple(q)], [0.0011, 0.0007], "bushWood", seg=3, caps=False)
            for th in range(2):                                    # thorns
                tp = p + (q - p) * (0.35 + 0.4 * th)
                tdir = Vector((rng.uniform(-1, 1), rng.uniform(0.2, 1), rng.uniform(-1, 0.3))).normalized()
                tube(mb, [tuple(tp), tuple(tp + tdir * 0.0045)], [0.0006, 0.00015], "bushWood", seg=3, caps=False)
            tips.append((p, q, b))
    for k, (p, q, d) in enumerate(tips[::2]):                      # a few leaf clusters
        c = q + Vector((0, 0.003, 0))
        if c.z > bz + 0.004:                                       # keep the front low (Moses's marks and walk)
            c.z = bz + 0.004
        lumpy(mb, tuple(c), 0.0085, "bushLeaf", seg=7, rings=4, sh=0.55, amp=0.28, seed=k + 120)
    top = max((Vector(mb.V[i]).y for i in range(len(mb.V))))
    flame = (bx, round(0.020 + 0.046 + 0.022, 4), round(bz - 0.020, 4))
    ob = make_obj("bush", mb, root, origin=(bx, 0.0, bz), smooth_angle=50)
    empty("bushFlame", flame, ob)
    return ob, flame, round(top, 4)


# ============================================================================================ the sea
# back wall profile (d toward the lane, h up), CCW: base, inner face, the hollow under the lip, the lip curling forward
# and down, over the crest, the long back slope of piled-up water down to the back of the sea
WALL_PROF = [(-0.250, 0.0), (-0.125, 0.0), (0.0, 0.0),
             (0.0015, 0.030), (0.0020, 0.070), (0.0010, 0.110), (-0.0010, 0.150), (-0.0020, 0.178), (-0.0030, 0.196),
             (-0.0015, 0.2065), (0.0030, 0.2130), (0.0090, 0.2145), (0.0135, 0.2115), (0.0165, 0.2070),
             (0.0185, 0.2120), (0.0195, 0.2205), (0.0180, 0.2290), (0.0135, 0.2365), (0.0070, 0.2415),
             (-0.0010, 0.2445), (-0.0120, 0.2445), (-0.0260, 0.2400), (-0.0450, 0.2290), (-0.0700, 0.2070),
             (-0.1000, 0.1750), (-0.1350, 0.1320), (-0.1700, 0.0880), (-0.2000, 0.0500), (-0.2250, 0.0240),
             (-0.2430, 0.0100)]
INNER = range(3, 10)          # inner face points (flow ripples)
LIP = range(10, 20)           # the curl


def wall_rings(front):
    """stations along x of the wall section: the lip swells and shrinks, the crest rises and falls, flow ripples run
    down the inner face; the ends taper. front = the lower wall on the lane's viewer side."""
    hs = 0.137 / 0.2445 if front else 0.232 / 0.2445
    out, prof_at = [], []
    xs = np.linspace(SEA_X[0], SEA_X[1], 51)
    for x in xs:
        s = (x - SEA_X[0]) / (SEA_X[1] - SEA_X[0])
        kh = 1.0 + 0.028 * math.sin(TAU * 1.7 * s + 0.4) + 0.014 * math.sin(TAU * 4.3 * s + 1.3)
        lip = 0.80 + 0.32 * (0.5 + 0.5 * math.sin(TAU * 2.2 * s + 1.1))
        e = min(1.0, min(s, 1 - s) / 0.13)
        er = math.sqrt(max(e, 0.0))
        lip *= 0.35 + 0.65 * er
        kh *= 0.62 + 0.38 * er                                   # the ends fall away, rounded, into the sea
        prof = []
        for k, (d, h) in enumerate(WALL_PROF):
            hh = h * (kh if h > 0.12 else 1.0 + (kh - 1.0) * h / 0.12)
            dd = d
            if k < 10 and h > 0:
                dd -= (1 - er) * 0.022 * (h / 0.20) ** 0.7       # the inner face bends back at the ends
            if 20 <= k:
                dd += 0.0028 * math.sin(h * 115 + x * 35) * min(1.0, h / 0.05)   # wave bands on the outer slope
            if k in INNER:
                dd += 0.0012 * math.sin(x * 210 + h * 45) + 0.0006 * math.sin(x * 470 - h * 90)
            if k in LIP and d > -0.002:
                dd = d * lip * (0.30 if front else 1.0)
            if d < -0.002 and front:
                dd = d * 0.32
            prof.append((dd, hh * hs))
        prof_at.append(prof)
        z0 = LANE_Z[1] if front else LANE_Z[0]
        sg = -1 if front else 1
        out.append([(x, h, z0 + sg * d) for d, h in prof])
    return xs, out, prof_at


def fish_poly(L):
    return [(u * L, v * L) for u, v in ((0.50, 0.0), (0.38, 0.13), (0.18, 0.20), (0.02, 0.24), (-0.06, 0.31),
                                        (-0.14, 0.20), (-0.30, 0.12), (-0.40, 0.05), (-0.53, 0.21), (-0.47, 0.0),
                                        (-0.53, -0.21), (-0.40, -0.05), (-0.30, -0.11), (-0.10, -0.17),
                                        (0.10, -0.17), (0.30, -0.13))]


BACK_FISH = [(0.226, 0.128, 1, 0.025, 0.10), (0.262, 0.172, -1, 0.020, -0.05), (0.300, 0.098, 1, 0.029, 0.04),
             (0.338, 0.152, -1, 0.022, 0.12), (0.372, 0.112, 1, 0.019, -0.10), (0.352, 0.197, 1, 0.015, 0.0),
             (0.278, 0.203, 1, 0.010, 0.05), (0.290, 0.210, 1, 0.009, 0.0), (0.284, 0.193, 1, 0.009, -0.05),
             (0.244, 0.082, -1, 0.017, 0.0)]
FRONT_FISH = [(0.250, 0.082, -1, 0.020, 0.0), (0.330, 0.062, 1, 0.022, 0.1), (0.372, 0.100, -1, 0.016, 0.0)]


def build_wall(front, rng):
    mb = MB()
    mb.nr = True                                     # whole wall: named texels of the sea drawing
    xs, rings, profs = wall_rings(front)
    nrm = [prof_normals(p) for p in profs]
    sg = -1 if front else 1
    hs = 0.137 / 0.2445 if front else 0.232 / 0.2445

    def reg(i, k):
        (d0, h0), (d1, h1) = profs[i][k], profs[i][(k + 1) % len(WALL_PROF)]
        hm = (h0 + h1) / 2 / hs
        if k in range(12, 18):
            return "foam"
        if hm < 0.055 and k < 10:
            return "seaDeep"
        return "sea"
    sweep(mb, rings, reg, lambda i, k: (0, nrm[i][k][1], sg * nrm[i][k][0]), cap_reg="sea")
    # foam along the crest and the curl, a foam skirt at the inner foot, spray over the crest
    for i in range(0, len(xs), 1):
        x = xs[i]
        p = profs[i]
        ck = max(LIP, key=lambda k: p[k][1])
        d, h = p[ck]
        z0 = LANE_Z[1] if front else LANE_Z[0]
        if i % 2 == 0:
            r = (0.0055 + 0.0030 * nz(i, 1)) * (0.7 if front else 1.0)
            lumpy(mb, (x + rng.uniform(-0.002, 0.002), h + r * 0.1, z0 + sg * (d - 0.003)), r * 0.8, "foam", seg=9,
                  rings=5, sh=0.55, amp=0.16, seed=i + (500 if front else 0))
        if rng.random() < 0.22:                                    # a few lumps of foam on the curl's face
            kk = rng.choice((14, 15, 16))
            dl, hl = p[kk]
            r = rng.uniform(0.0030, 0.0048) * (0.7 if front else 1.0)
            lumpy(mb, (x + rng.uniform(-0.002, 0.002), hl, z0 + sg * (dl + 0.0005)), r, "foam", seg=8, rings=4,
                  sh=0.7, amp=0.2, seed=i + 77)
        if i % 4 == 0:
            r = 0.0040
            lumpy(mb, (x + 0.002, 0.0015, z0 + sg * 0.0045), r, "foam", seg=6, rings=3, sh=0.55, sz=1.3, amp=0.3,
                  seed=i + 33)
    for k in range(26 if front else 42):                              # spray droplets over the crest
        i = rng.randrange(len(xs)); p = profs[i]
        ck = max(LIP, key=lambda kk: p[kk][1])
        d, h = p[ck]
        z0 = LANE_Z[1] if front else LANE_Z[0]
        r = rng.uniform(0.0011, 0.0024)
        sphere(mb, (xs[i] + rng.uniform(-0.003, 0.003), h + rng.uniform(0.008, 0.030) * hs ** 0.5,
                    z0 + sg * (d + rng.uniform(-0.010, 0.003 if front else 0.005))), r, "foam", seg=6, rings=4)
    # fish silhouettes slightly proud of the inner face (darker: seaDeep texel)
    for (fx, fh, dirn, L, tilt) in (FRONT_FISH if front else BACK_FISH):
        c, s = math.cos(tilt), math.sin(tilt)
        poly = [(fx + dirn * (u * c - v * s), fh + u * s * dirn + v * c) for u, v in fish_poly(L)]
        if dirn < 0:
            poly = poly[::-1]
        z0 = LANE_Z[1] if front else LANE_Z[0]
        za, zb_ = sorted((z0 + sg * 0.0034, z0 + sg * 0.0050))
        extrude(mb, poly, za, zb_, "fish", back=True)
    mb.nr = False
    name = "seaWallFront" if front else "seaWallBack"
    z0 = LANE_Z[1] if front else LANE_Z[0]
    return make_obj(name, mb, None, origin=(0.30, 0.0, z0), smooth_angle=80, merge=False)


def build_sea(root):
    """`sea` (empty at the band's centre) with `seaWater` (empty) -> seaWaterBack / seaWaterLane / seaWaterFront, the
    rippled surface in three parts (foam at the shores, a deeper band down the middle; walls of each cut so the lane
    can be hidden), `seaBed` (wet sand with ripples, shells, pebbles, seaweed, two starfish; flush with the page),
    `seaWallBack` / `seaWallFront` (standing water, scaled to y 0.02 at rest)"""
    rng = random.Random(91)
    sea = empty("sea", (0.30, 0.0, -0.015), root)
    water = empty("seaWater", (0.30, 0.0, -0.015), sea)
    parts = {}
    for name, (z0, z1) in (("seaWaterBack", (SEA_Z[0], LANE_Z[0])), ("seaWaterLane", LANE_Z),
                           ("seaWaterFront", (LANE_Z[1], SEA_Z[1]))):
        mb = MB()
        if name == "seaWaterLane":
            mb.nr = True
        water_grid(mb, SEA_X[0], SEA_X[1], z0, z1, 0.0085, sea_h, sea_region)
        n = int(round((SEA_X[1] - SEA_X[0]) / 0.0085))
        for x in (SEA_X[0], SEA_X[1]):                              # side walls down to the page
            m = max(2, int(round((z1 - z0) / 0.0085)))
            for j in range(m):
                za, zb_ = z0 + (z1 - z0) * j / m, z0 + (z1 - z0) * (j + 1) / m
                mb.fo([mb.v(x, sea_h(x, za), za), mb.v(x, sea_h(x, zb_), zb_), mb.v(x, 0.0, zb_), mb.v(x, 0.0, za)],
                      sea_region(x, (za + zb_) / 2), (1 if x > 0.3 else -1, 0, 0))
        for z, o in ((z0, -1), (z1, 1)):                            # cut / shore edges
            for i in range(n):
                xa = SEA_X[0] + (SEA_X[1] - SEA_X[0]) * i / n; xb = SEA_X[0] + (SEA_X[1] - SEA_X[0]) * (i + 1) / n
                mb.fo([mb.v(xa, sea_h(xa, z), z), mb.v(xb, sea_h(xb, z), z), mb.v(xb, 0.0, z), mb.v(xa, 0.0, z)],
                      sea_region((xa + xb) / 2, z), (0, 0, o))
        mb.nr = False
        parts[name] = make_obj(name, mb, water, origin=(0.30, 0.0, (z0 + z1) / 2), smooth_angle=60, merge=True)
    dec = DECOR.setdefault("sea", [])
    for k in range(26):                                             # wave marks on the water (print only)
        x = 0.215 + 0.17 * nz(k, 1); z = SEA_Z[0] + 0.035 + 0.40 * nz(k, 2)
        if LANE_Z[0] - 0.012 < z < LANE_Z[1] + 0.012:
            continue
        for s in range(2):
            dec.append(((x + 0.007 * s, 0.009, z + 0.003 * math.sin(s * 3)), (x + 0.007 * s + 0.007, 0.009, z + 0.003 * math.sin(s * 3 + 1.8))))
    # sea-bed under the lane
    bm = MB()
    bed_h = lambda x, z: 0.0007 + 0.0005 * (0.5 + 0.5 * math.sin(z * 240 + 8 * math.sin(x * 40)))
    water_grid(bm, SEA_X[0], SEA_X[1], LANE_Z[0], LANE_Z[1], 0.0065, bed_h, lambda x, z: "seaBed")
    bm.nr = True
    for i in range(14):                                             # shells: little ribbed fans
        x, z = rng.uniform(0.21, 0.39), rng.uniform(LANE_Z[0] + 0.006, LANE_Z[1] - 0.006)
        a = rng.uniform(0, TAU); r = rng.uniform(0.0035, 0.0055)
        c = bm.v(x, 0.0024, z)
        rim = [bm.v(x + r * math.cos(a + t), 0.0010 + 0.0012 * (k % 2), z + r * math.sin(a + t))
               for k, t in enumerate(np.linspace(-1.2, 1.2, 9))]
        for k in range(8):
            bm.fo([c, rim[k], rim[k + 1]], "shell", UP)
    for i in range(12):
        x, z = rng.uniform(0.21, 0.39), rng.uniform(LANE_Z[0] + 0.004, LANE_Z[1] - 0.004)
        r = rng.uniform(0.0025, 0.0045)
        lumpy(bm, (x, r * 0.3, z), r, "pebble", seg=5, rings=3, sh=0.55, sx=rng.uniform(1.0, 1.5), amp=0.18, seed=i + 5)
    for i in range(6):                                              # seaweed lying flat
        x, z = rng.uniform(0.21, 0.39), rng.uniform(LANE_Z[0] + 0.01, LANE_Z[1] - 0.01)
        a = rng.uniform(0, TAU)
        pts = [(x + 0.004 * t * math.cos(a) + 0.003 * math.sin(t * 1.7), 0.0016, z + 0.004 * t * math.sin(a))
               for t in range(6)]
        blade(bm, pts, [0.0035, 0.004, 0.0035, 0.003, 0.002, 0.0], "weed", nrm=(0, 1, 0))
    for i, (x, z) in enumerate(((0.352, 0.103), (0.228, 0.036))):    # two starfish
        a0 = rng.uniform(0, TAU)
        c = bm.v(x, 0.0026, z)
        ring = []
        for k in range(10):
            r = 0.0075 if k % 2 == 0 else 0.0028
            ring.append(bm.v(x + r * math.cos(a0 + TAU * k / 10), 0.0012, z + r * math.sin(a0 + TAU * k / 10)))
        for k in range(10):
            bm.fo([c, ring[k], ring[(k + 1) % 10]], "starfish", UP)
    bm.nr = False
    bed = make_obj("seaBed", bm, sea, origin=(0.30, 0.0, 0.075), smooth_angle=50)
    walls = {}
    for front in (False, True):
        w = build_wall(front, rng)
        parent_keep(w, sea)
        walls[w.name] = w
    return sea, water, parts, bed, walls


def set_wall_rest(walls, raised):
    for w in walls.values():
        w.scale = (1.0, 1.0, 1.0 if raised else 0.02)
    bpy.context.view_layer.update()


def build_far_shore(root, palm_tpl):
    """`farShore`: three date palms (one palm drawing) with child `farRocks` (rocks and a few shells, named texels)"""
    mb = MB()
    for (x, z, s, yaw, lean) in FAR_PALMS:
        mb.add(palm_tpl, yaw_fn(x, z, yaw, s, lean=lean))
    ob = make_obj("farShore", mb, root, origin=(0.53, 0.0, -0.19), smooth_angle=60)
    rm = MB()
    rm.nr = True
    for i, (x, z, r) in enumerate(((0.432, -0.372, 0.013), (0.505, -0.392, 0.016), (0.588, -0.378, 0.011),
                                   (0.430, 0.192, 0.010), (0.462, 0.199, 0.007), (0.594, 0.075, 0.008),
                                   (0.424, -0.195, 0.009))):
        lumpy(rm, (x, r * 0.35, z), r, "stone", seg=8, rings=4, sh=0.65, sx=1.3, amp=0.2, seed=i + 300, smooth=False)
    rm.nr = False
    rocks = make_obj("farRocks", rm, ob, origin=(0.50, 0.0, -0.10), smooth_angle=50)
    return ob, rocks


def build_loose_wheel(root):
    """Pharaoh's six-spoke chariot wheel lying flat on the sea-bed (hidden until S12; gold texel)"""
    mb = MB()
    mb.nr = True
    x, z = WHEEL
    R = 0.024
    tube(mb, [(x + R * math.cos(TAU * k / 20), 0.0030, z + R * math.sin(TAU * k / 20)) for k in range(20)], 0.0026,
         "gold", seg=6, closed=True)
    for k in range(6):
        a = TAU * k / 6 + 0.2
        tube(mb, [(x + 0.004 * math.cos(a), 0.0030, z + 0.004 * math.sin(a)),
                  (x + (R - 0.002) * math.cos(a), 0.0030, z + (R - 0.002) * math.sin(a))], 0.0012, "gold", seg=4,
             caps=False)
    lathe(mb, [(0.0, 0.0006), (0.0055, 0.0006), (0.0055, 0.0062), (0.0, 0.0068)], "gold", C=(x, 0, z), seg=10)
    mb.nr = False
    return make_obj("looseWheel", mb, root, origin=(x, 0.0, z), smooth_angle=50)
def P_FRONT():
    return {"A": (1, 0, 0), "B": (0, 1, 0), "D": (0, 0, 1)}


def P_OBL(kx, k):
    """front-right-above: further back = right and up"""
    return {"A": (1, 0, -kx), "B": (0, 1, -k), "D": (kx, k, 1)}


def P_PLAN():
    return {"A": (1, 0, 0), "B": (0, 0, -1), "D": (0, 1, 0)}


def P_SIDE(k):
    """seen from -x and above (the field wall's road side): right = +z"""
    return {"A": (0, 0, 1), "B": (k, 1, 0), "D": (-1, k, 0)}



def P_PLAN():
    return {"A": (1, 0, 0), "B": (0, 0, -1), "D": (0, 1, 0)}


def P_PLAN_R():
    """plan turned a quarter (not mirrored): right = toward the viewer (+z), up = +x"""
    return {"A": (0, 0, 1), "B": (1, 0, 0), "D": (0, 1, 0)}


def _chars():
    """the figures' sheet places and printed bboxes: pipeline/ex_characters.py output where it exists (authoritative),
    the proposal below for figures not drawn yet"""
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    rc = json.load(open(p))
    got = {c: {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"], "height": v["height"],
               "box": v["bboxSheet"]} for c, v in rc["characters"].items() if c in rc.get("sheet", {})}
    for c, v in prop.items():
        got.setdefault(c, v)
    return got, len(got) == len(rc.get("sheet", {})) == 3


def _chars_proposal():
    return {"pharaoh": {"sheetX": -0.33, "sheetY": 0.015, "height": 0.39, "box": [-0.45, 0.015, -0.21, 0.405]},
            "moses": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.37, "box": [-0.13, 0.015, 0.14, 0.415]},
            "miriam": {"sheetX": 0.33, "sheetY": 0.015, "height": 0.34, "box": [0.21, 0.015, 0.45, 0.355]}}


# sheet places the Set + sheet role sets in design.json (ex_characters.py reads them): Moses's staff foot sits 0.012
# below his feet, so at sheetY 0.015 it printed on the art rect's bottom edge (sheet check, 2026-11-14)
SHEET_PLACE = {"moses": (0.0, 0.027)}


def _apply_places(chars):
    pending = []
    for c, (sx, sy) in SHEET_PLACE.items():
        v = chars.get(c)
        if v is None:
            continue
        dx, dy = sx - v["sheetX"], sy - v["sheetY"]
        if abs(dx) > 1e-6 or abs(dy) > 1e-6:
            pending.append(c)
            v["box"] = [v["box"][0] + dx, v["box"][1] + dy, v["box"][2] + dx, v["box"][3] + dy]
            v["sheetX"], v["sheetY"] = sx, sy
    return pending


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
CHARS_PENDING = _apply_places(CHAR_PROPOSAL)          # characters whose ID render is not yet at the place set here
# kind, scale, centre-x and bottom of the bbox on the sheet (sheet coords: x -0.5..0.5, ys 0 = art rect bottom)
DRAWINGS = {
    "backdrop": dict(P_FRONT(), scale=1.62, cx=-0.105, y0=1.020, decorOnly=["pyramid", "dune"],
                     members=["backdrop", "pyramids", "mountain"]),
    "bush":     dict(P_FRONT(), scale=0.95, cx=0.413, y0=1.085, members=["bush"]),
    "papyrus":  dict(P_FRONT(), scale=0.85, cx=0.392, y0=0.630, members=["nileBoat"]),
    "palace":   dict(P_OBL(0.30, 0.42), scale=1.25, cx=-0.293, y0=0.735, decorOnly=["pave", "obelisk"],
                     members=["palace", "dais", "throne"]),
    "houses":   dict(P_OBL(0.30, 0.42), scale=1.00, cx=0.050, y0=0.843, decorOnly=["mudWall", "roof"],
                     members=["houses", "doorMarks"]),
    "palm":     dict(P_FRONT(), scale=1.10, cx=0.400, y0=0.790, members=[]),
    "brickyard": dict(P_OBL(0.0, 0.60), scale=0.85, cx=0.122, y0=0.625, decorOnly=["brick"], members=["brickyard", "straw"]),
    "people":   dict(P_FRONT(), scale=1.20, cx=0.3295, y0=0.435, members=[], creases=False),
    "ground":   dict(P_PLAN(), scale=3.10, cx=-0.288, y0=0.435, decorOnly=["nile"], members=["ground", "nileWater"]),
    "sea":      dict(P_PLAN_R(), scale=1.85, cx=0.041, y0=0.440, decorOnly=["sea", "seaDeep"],
                     members=["seaWaterBack", "seaWaterFront", "seaBed"]),
}
TEMPLATES = {"palm": ("palacePalms", "farShore"), "people": ("crowdWest", "crowdShore", "crowdFar"),
             "papyrus": ("nile",)}
PEOPLE_CONST = {"brick": ("brickyard", "brick"), "jar": ("houses", "jar"), "eye": ("houses", "doorway"),
                "band": ("brickyard", "trough"), "beard": ("houses", "doorway")}
SEA_CONST = {"sea": ("sea", "sea"), "seaDeep": ("sea", "seaDeep"), "foam": ("sea", "foam"), "fish": ("sea", "seaDeep")}
CONSTS = {"ground": {"tuft": ("palm", "frond"), "pebble": ("palace", "stone"), "stone": ("backdrop", "rock")},
          "nile": {"lotusPad": ("papyrus", "lotusPad"), "lotus": ("papyrus", "lotus")},
          "seaWaterLane": SEA_CONST, "seaWallBack": SEA_CONST, "seaWallFront": SEA_CONST,
          "seaBed": {"shell": ("sea", "foam"), "pebble": ("palace", "stone"), "weed": ("palm", "frond"),
                     "starfish": ("houses", "doorMark")},
          "farRocks": {"stone": ("backdrop", "rock")}, "looseWheel": {"gold": ("palace", "gold")},
          "crowdWest": PEOPLE_CONST, "crowdShore": PEOPLE_CONST, "crowdFar": PEOPLE_CONST,
          "mountain": {"ledge": ("ground", "track")}}
def dproj(sp, P):
    P = np.asarray(P, float)
    return P @ np.array(sp["A"], float), P @ np.array(sp["B"], float), P @ np.array(sp["D"], float)


def raster_sources(objs, tmp):
    """drawing -> [(object name, P array, list of (vertex idx triple, region))] (no-raster faces left out)"""
    src = {}
    for g, dsp in DRAWINGS.items():
        lst = []
        names = list(dsp["members"]) + (["tpl_" + g] if g in TEMPLATES else [])
        for name in names:
            ob = objs.get(name) or tmp.get(name)
            me = ob.data; me.calc_loop_triangles()
            nr = NR_OF[ob.name]; regs = REG_OF[ob.name]
            tris = [(tuple(t.vertices), regs[t.polygon_index]) for t in me.loop_triangles if not nr[t.polygon_index]]
            lst.append((ob.name, P_OF[ob.name], tris))
        src[g] = lst
    return src


def setup_maps(src):
    for g, dsp in DRAWINGS.items():
        A, Bv = [], []
        for name, P, tris in src[g]:
            used = sorted({i for t, _ in tris for i in t})
            a, b, _ = dproj(dsp, P[used]); A.append(a); Bv.append(b)
        A = np.concatenate(A); Bv = np.concatenate(Bv)
        a0, a1, b0, b1 = A.min(), A.max(), Bv.min(), Bv.max()
        s = dsp["scale"]
        dsp["sheetX"] = float(dsp["cx"] - (a0 + a1) / 2 / s)
        dsp["sheetY"] = float(dsp["y0"] - b0 / s)
        dsp["bboxSheet"] = [round(a0 / s + dsp["sheetX"], 4), round(b0 / s + dsp["sheetY"], 4),
                            round(a1 / s + dsp["sheetX"], 4), round(b1 / s + dsp["sheetY"], 4)]


def uv_of(sp, P):
    a, b, _ = dproj(sp, P)
    return np.stack([a / sp["scale"] + sp["sheetX"] + 0.5, (b / sp["scale"] + sp["sheetY"]) / ART_H], -1)


def drawing_of(name):
    for g, d in DRAWINGS.items():
        if name in d["members"]:
            return g
    for g, obs in TEMPLATES.items():
        if name in obs:
            return g
    return None


RS = [1]


def to_px(u, v):
    return (ART[0] + u * ART[2]) * RS[0], (ART[1] + (1.0 - v) * ART[3]) * RS[0]


def raster_drawings(src):
    """UV-space render of every drawing: region ids + depth, then visible sharp edges and depth steps as decor"""
    W, H = PAGE[0] * RS[0], PAGE[1] * RS[0]
    idb = np.zeros((H, W), np.int32); zb = np.full((H, W), -1e9)
    regid, regname = {}, {0: None}
    crease = np.zeros((H, W), bool)
    for g, dsp in DRAWINGS.items():
        for name, P, tris in src[g]:
            uv = uv_of(dsp, P)
            px = np.stack(to_px(uv[:, 0], uv[:, 1]), -1)
            dep = dproj(dsp, P)[2]
            for t, reg in tris:
                key = (g, reg)
                if key not in regid:
                    regid[key] = len(regid) + 1; regname[regid[key]] = key
                rid = regid[key]
                Pp = px[list(t)]; Z = dep[list(t)]
                x0, y0 = np.floor(Pp.min(0)).astype(int); x1, y1 = np.ceil(Pp.max(0)).astype(int)
                x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
                if x1 < x0 or y1 < y0:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                (ax, ay), (bx, by), (cx, cy) = Pp
                den = (by - cy) * (ax - cx) + (cx - bx) * (ay - cy)
                if abs(den) < 1e-9:
                    continue
                l1 = ((by - cy) * (gx - cx) + (cx - bx) * (gy - cy)) / den
                l2 = ((cy - ay) * (gx - cx) + (ax - cx) * (gy - cy)) / den
                l3 = 1 - l1 - l2
                ins = (l1 >= -1e-3) & (l2 >= -1e-3) & (l3 >= -1e-3)
                if not ins.any():
                    continue
                zz = l1 * Z[0] + l2 * Z[1] + l3 * Z[2]
                sub_z = zb[y0:y1 + 1, x0:x1 + 1]; sub_i = idb[y0:y1 + 1, x0:x1 + 1]
                upd = ins & (zz > sub_z)
                sub_z[upd] = zz[upd]; sub_i[upd] = rid
    for g, dsp in DRAWINGS.items():
        if g == "ground" or not dsp.get("creases", True):
            continue
        for name, P, tris in src[g]:
            ob = bpy.data.objects[name]; me = ob.data
            sharp = me.attributes.get("sharp_edge")
            if sharp is None:
                continue
            sv = np.zeros(len(me.edges), bool); sharp.data.foreach_get("value", sv)
            used = {i for t, _ in tris for i in t}
            uv = uv_of(dsp, P); dep = dproj(dsp, P)[2]
            for e in me.edges:
                if not sv[e.index]:
                    continue
                i0, i1 = e.vertices
                if i0 not in used or i1 not in used:
                    continue
                pa = np.array(to_px(*uv[i0])); pb = np.array(to_px(*uv[i1]))
                n = int(np.linalg.norm(pb - pa) / 0.6) + 2
                for t in np.linspace(0, 1, n):
                    p = pa + (pb - pa) * t
                    xi, yi = int(p[0]), int(p[1])
                    if 0 <= xi < W and 0 <= yi < H and idb[yi, xi] > 0:
                        d = dep[i0] + (dep[i1] - dep[i0]) * t
                        if d >= zb[yi, xi] - 0.0025:
                            crease[yi, xi] = True
    nocrease = np.isin(idb, [r for r, k in regname.items() if k and not DRAWINGS[k[0]].get("creases", True)])
    for dy, dx in ((0, 1), (1, 0)):
        sz = shift(zb, dy, dx); si = shift(idb, dy, dx)
        crease |= (idb > 0) & (si == idb) & (np.abs(zb - sz) > 0.004) & ~nocrease
    # regions drawn with single decor lines only (stone courses: the chamfers would print as dense double lines)
    for g, dsp in DRAWINGS.items():
        regs = dsp.get("decorOnly")
        if not regs:
            continue
        ids = [r for r, k in regname.items() if k and k[0] == g and k[1] in regs]
        m = np.isin(idb, ids)
        crease[m] = False
        for p0, p1 in DECOR.get(g, []):
            P2 = np.array([p0, p1], float)
            uv = uv_of(dsp, P2); dep = dproj(dsp, P2)[2]
            pa = np.array(to_px(*uv[0])); pb = np.array(to_px(*uv[1]))
            n = int(np.linalg.norm(pb - pa) / 0.6) + 2
            for t in np.linspace(0, 1, n):
                q = pa + (pb - pa) * t
                xi, yi = int(q[0]), int(q[1])
                if 0 <= xi < W and 0 <= yi < H and m[yi, xi]:
                    if dep[0] + (dep[1] - dep[0]) * t >= zb[yi, xi] - 0.0065:
                        crease[yi, xi] = True
    return idb, regname, crease


def apply_uvs(objs):
    for name, ob in objs.items():
        if ob.type != 'MESH':
            continue
        g = drawing_of(name)
        me = ob.data
        lay = me.uv_layers.new(name="UVMap")
        P = P_OF[name]
        if g is None:
            uvv = np.zeros((len(P), 2))
        else:
            uvv = uv_of(DRAWINGS[g], P)
        vi = np.zeros(len(me.loops), np.int32); me.loops.foreach_get("vertex_index", vi)
        lay.data.foreach_set("uv", uvv[vi].astype(np.float32).ravel())


def safe_texels(idb, regname, crease):
    out = {}
    for rid, key in regname.items():
        if not key:
            continue
        m = (idb == rid) & ~dilate(crease, 1)
        ys, xs = np.nonzero(m)
        if not len(ys):
            m = (idb == rid) & ~crease
            ys, xs = np.nonzero(m)
        if not len(ys):
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        cur = np.pad(m[y0:y1, x0:x1], 1)
        y0 -= 1; x0 -= 1
        step = 0
        while True:                                   # octagonal erosion (4- and 8-neighbour steps alternate): close
            nxt = cur.copy()                          # to the true distance, so thin diagonal shapes are not overrated
            nb = ((0, 1), (0, -1), (1, 0), (-1, 0)) + (((1, 1), (1, -1), (-1, 1), (-1, -1)) if step % 2 else ())
            step += 1
            for dy, dx in nb:
                nxt &= shift(cur, dy, dx)
            if not nxt.any():
                break
            cur = nxt
        cy, cx = np.nonzero(cur)
        k = int(np.argmin((cy - cy.mean()) ** 2 + (cx - cx.mean()) ** 2))
        px, py = x0 + cx[k] + 0.5, y0 + cy[k] + 0.5
        out[key] = ((px - ART[0]) / ART[2], 1.0 - (py - ART[1]) / ART[3])
    return out


def fix_faces(objs, idb, regname, crease):
    """faces nearly edge-on to their drawing's view or facing away from it (n . d < 0.22, n from P) take a clean texel
    deep inside their own region (LESSONS L51); no-raster faces take their named texel (CONSTS)"""
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
                if L < 1e-12 or nn @ dv / L >= 0.22:      # back faces too (L51: no face printed through the head)
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
                       "written by pipeline/ex_egypt.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)
    return const



# ============================================================================================ checks
def check_layout():
    msgs = []
    boxes = {g: d["bboxSheet"] for g, d in DRAWINGS.items()}
    for g, b in boxes.items():
        if b[0] < -0.485 or b[2] > 0.485 or b[1] < 0.012 or b[3] > ART_H - 0.012:
            msgs.append("drawing %s outside the art rect: %s" % (g, b))
        for c, cv in CHAR_PROPOSAL.items():
            cb = cv["box"]
            gx = max(cb[0] - b[2], b[0] - cb[2]); gy = max(cb[1] - b[3], b[1] - cb[3])
            if max(gx, gy) < 0.02:
                msgs.append("drawing %s too close to figure %s (%.3f)" % (g, c, max(gx, gy)))
    gs = list(boxes)
    for i in range(len(gs)):
        for j in range(i + 1, len(gs)):
            a, b = boxes[gs[i]], boxes[gs[j]]
            gx = max(b[0] - a[2], a[0] - b[2]); gy = max(b[1] - a[3], a[1] - b[3])
            if max(gx, gy) < 0.012:
                msgs.append("bbox overlap %s / %s (gap %.3f)" % (gs[i], gs[j], max(gx, gy)))
    return msgs


TIMED = ["crowdShore", "crowdFar", "doorMarks"]          # shown only part of the play: tested against those moments
EXEMPT = {"seaWallBack": "the walls stand only while the sea is parted; the lane between them is checked (SEA_LANE)",
          "seaWallFront": "as seaWallBack",
          "looseWheel": "lies at Pharaoh's feet on purpose (S12, while he stands at (0.24, 0.07))",
          "seaWaterLane": "the lane surface (<= 0.012) that Effects hide"}


def seg_dist_np(X, Z, a, b):
    ax, az = a; bx_, bz = b
    dx, dz = bx_ - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
    t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
    return np.hypot(X - ax - t * dx, Z - az - t * dz)


def check_clearance(objs):
    """CONTRACT §6: no geometry above 0.012 within 0.05 of a mark, nothing on the straight paths between consecutive
    marks of one actor, the wilderness lane clear. Overhead parts (palm crowns >= 0.17) only need head room: above 0.40
    they are ignored, between 0.17 and 0.40 they must stay 0.035 from the walk line (a head's radius). Props shown only
    part of the play are tested against the stands and moves made while they are shown."""
    pts, names = [], []
    for name, ob in objs.items():
        if ob.type != 'MESH' or name in EXEMPT:
            continue
        for x, h, z in world_verts(ob):
            pts.append((x, h, z)); names.append(name)
    P = np.array(pts); names = np.array(names)
    low = (P[:, 1] > 0.012) & (P[:, 1] < 0.17)
    over = (P[:, 1] >= 0.17) & (P[:, 1] < 0.40)
    timed = np.isin(names, TIMED)
    hard, soft = {}, {}

    def test(label, d, out, sel_names=None):
        sel = (low & (d < 0.05)) | (over & (d < 0.035))
        sel &= ~timed if sel_names is None else np.isin(names, sel_names)
        if sel.any():
            out[label] = (round(float(P[sel, 1].max()), 4), round(float(d[sel].min()), 4),
                          sorted(set(names[sel].tolist())))
    X, Z = P[:, 0], P[:, 2]
    for label, (x, z) in CONTRACT_MARKS.items():
        test("mark " + label, np.hypot(X - x, Z - z), hard)
    for label, a, b, is_hard, t0, t1 in PATHS:
        test(label, seg_dist_np(X, Z, a, b), hard if is_hard else soft)
    lane = (X > WILD_LANE[0]) & (X < WILD_LANE[1]) & (Z > WILD_LANE[2]) & (Z < WILD_LANE[3]) & (P[:, 1] > 0.012) & ~timed
    if lane.any():
        hard["wilderness lane"] = (round(float(P[lane, 1].max()), 4), sorted(set(names[lane].tolist())))
    for node in TIMED:                                   # timed props: the moments they are shown
        win = visible_windows(node)
        ov = lambda t0, t1: any(t0 < b and t1 > a for a, b in win)
        for label, p, t0, t1 in STANDS:
            if ov(t0, t1):
                test("%s / %s" % (node, label), np.hypot(X - p[0], Z - p[1]), hard, [node])
        for label, a, b, is_hard, t0, t1 in PATHS:
            if ov(t0, t1):
                test("%s / %s" % (node, label), seg_dist_np(X, Z, a, b), hard if is_hard else soft, [node])
    # first moves of the play: from the printed places (sheetX, 0) to the first mark (reported only)
    first = {}
    for a in TL["acting"]:
        if "to" in a and a["who"] not in first:
            first[a["who"]] = (float(a["to"][0]), float(a["to"][1]))
    for c, p in first.items():
        if c in CHAR_PROPOSAL:
            s = (CHAR_PROPOSAL[c]["sheetX"], 0.0)
            test("start %s %.2f,0>%.2f,%.2f" % (c, s[0], p[0], p[1]), seg_dist_np(X, Z, s, p), soft)
    return hard, soft


def check_sea(objs, walls):
    """the sea surface stays <= 0.012; with the walls raised, the crossing lane between them stays open: report how far
    each wall reaches into the lane, below and above head height"""
    out = {}
    for n in ("seaWaterBack", "seaWaterLane", "seaWaterFront", "seaBed"):
        out[n + "MaxH"] = round(max(v[1] for v in world_verts(objs[n])), 4)
    set_wall_rest(walls, True)
    for n, w in walls.items():
        V = np.array(world_verts(w))
        out[n + "H"] = round(float(V[:, 1].max()), 4)
        out[n + "Z"] = [round(float(V[:, 2].min()), 4), round(float(V[:, 2].max()), 4)]
        out[n + "X"] = [round(float(V[:, 0].min()), 4), round(float(V[:, 0].max()), 4)]
        reach = V[:, 2].max() - LANE_Z[0] if n == "seaWallBack" else LANE_Z[1] - V[:, 2].min()
        out[n + "IntoLane"] = round(float(reach), 4)
    set_wall_rest(walls, False)
    ok = all(out[n + "MaxH"] <= 0.012 for n in ("seaWaterBack", "seaWaterLane", "seaWaterFront", "seaBed")) and \
        out["seaWallBackIntoLane"] <= 0.027 and out["seaWallFrontIntoLane"] <= 0.012
    return ok, out


# ============================================================================================ build
def page_mat():
    m = bpy.data.materials.new("ex_page")
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.85
    return m


STATE = {}
ORDER = ["ground", "backdrop", "pyramids", "mountain", "palace", "dais", "throne", "palacePalms", "nile", "nileWater",
         "nileBoat", "brickyard", "straw", "crowdWest", "houses", "doorMarks", "bush", "seaWaterBack", "seaWaterLane",
         "seaWaterFront", "seaBed", "seaWallBack", "seaWallFront", "farShore", "farRocks", "crowdShore", "crowdFar",
         "looseWheel"]


def mode_build():
    SOFT_SEGS[:] = [(a, b) for _, a, b, hard, _, _ in PATHS if not hard]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = link(bpy.data.objects.new("egypt", None))
    objs = {}
    objs["ground"], scatter = build_ground(root)
    objs["backdrop"], objs["pyramids"], objs["mountain"] = build_backdrop(root)
    objs["palace"], objs["dais"], objs["throne"] = build_palace(root)
    palm_tpl = palm_template()
    m = MB()
    for (x, z, s, yaw) in PALACE_PALMS:
        m.add(palm_tpl, yaw_fn(x, z, yaw, s))
    objs["palacePalms"] = make_obj("palacePalms", m, objs["palace"], origin=(-0.37, 0.0, -0.54), smooth_angle=60)
    objs["nile"], objs["nileWater"], objs["nileBoat"], pap_tpl = build_nile(root)
    objs["brickyard"], objs["straw"] = build_brickyard(root)
    ptpl, pall = people_templates()
    objs["crowdWest"] = crowd("crowdWest", root, ptpl, WEST_SPOTS, 1)
    objs["houses"], objs["doorMarks"] = build_houses(root)
    objs["bush"], flame, bush_top = build_bush(root)
    sea, water, parts, objs["seaBed"], walls = build_sea(root)
    objs.update(parts); objs.update(walls)
    objs["farShore"], objs["farRocks"] = build_far_shore(root, palm_tpl)
    objs["crowdShore"] = crowd("crowdShore", root, ptpl, SHORE_SPOTS, 2)
    objs["crowdFar"] = crowd("crowdFar", root, ptpl, FAR_SPOTS, 3)
    objs["looseWheel"] = build_loose_wheel(root)
    pillar = empty("pillarWest", (PILLAR[0], 0.0, PILLAR[1]), root)
    bpy.context.view_layer.update()
    tmp = {"tpl_palm": make_obj("tpl_palm", palm_tpl, None, smooth_angle=60),
           "tpl_people": make_obj("tpl_people", pall, None, smooth_angle=60),
           "tpl_papyrus": make_obj("tpl_papyrus", pap_tpl, None, smooth_angle=60)}
    src = raster_sources(objs, tmp)
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("EGYPT_TRIS", total, json.dumps(tris))
    print("SCATTER", json.dumps(scatter))
    assert total <= MAX_TRIS, "over budget %d" % total
    set_wall_rest(walls, False)
    lay = check_layout()
    hard, soft = check_clearance(objs)
    sea_ok, sea_rep = check_sea(objs, walls)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_SOFT", json.dumps(soft))
    print("SEA_LANE", "OK" if sea_ok else "FAIL", json.dumps(sea_rep))
    print("CHAR_PLACES", json.dumps({c: [v["sheetX"], v["sheetY"]] for c, v in CHAR_PROPOSAL.items()}),
          "re-render needed (ex_characters.py): %s" % CHARS_PENDING if CHARS_PENDING else "in step with regions_characters.json")
    print("BUDGET", "%d / %d (target), %d hard ceiling" % (total, TARGET_TRIS, MAX_TRIS))
    if MODE == "check":
        STATE.update(objs=objs, walls=walls)
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
    set_wall_rest(walls, True)
    hmax = {n: round(max(v[1] for v in world_verts(ob)), 4) for n, ob in objs.items()}
    set_wall_rest(walls, False)
    write_design(objs, tris, total, flame, hmax, const, hard, soft, sea_rep, bush_top)
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root, walls=walls, flame=flame)
    print("BUILD_OK", GLB, total)


def write_design(objs, tris, total, flame, hmax, const, hard, soft, sea_rep, bush_top):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    d.setdefault("version", 1)
    d.setdefault("artHeightUnits", ART_H)
    d.setdefault("lines", {"outerPx": 4.5, "detailPx": 3.0,
                           "note": "same weights as David & Goliath, Esther and Ruth; faces come from decals (no face ink)"})
    d.setdefault("sheet", {
        "page": [1240, 1754], "dpi": 150, "art": [120, 283, 1000, 1227],
        "markers": [[62, 225], [1178, 225], [1178, 1568], [62, 1568]], "markerSize": 64,
        "title": {"hanzi": "出埃及", "pinyin": "chū āi jí", "english": "Let My People Go!", "box": 76, "gap": 12,
                  "cy": 100, "label": "DoodLive · 涂上颜色，再用手机扫一扫"},
        "footer": {"rect": [210, 1604, 820, 110], "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上", "出埃及记 · Exodus"],
                   "note": "centred on the page (x 620); line 1 at rect y + 40, line 2 at y + 76"},
        "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge; "
                    "title cy 100 puts the pinyin >= 6 mm from the top"})
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"height": v["height"], "sheetX": v["sheetX"], "sheetY": v["sheetY"]})
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
    hid = HIDDEN_AT_START
    d["set"] = {
        "generatedBy": "pipeline/ex_egypt.py", "doc": "docs/exodus/SET.md", "contract": "docs/exodus/CONTRACT.md §6",
        "root": "egypt",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {"bushFlame": list(flame), "bush": [BUSH[0], 0.0, BUSH[1]], "pillarWest": [PILLAR[0], 0.0, PILLAR[1]],
                  "sea": [0.30, 0.0, -0.015], "seaWater": [0.30, 0.0, -0.015], "seaWallBack": [0.30, 0.0, LANE_Z[0]],
                  "seaWallFront": [0.30, 0.0, LANE_Z[1]], "looseWheel": [WHEEL[0], 0.0, WHEEL[1]],
                  "palace": [PAL_C[0], 0.0, PAL_C[1]], "throne": [THRONE[0], DAIS_TOP, THRONE[1]],
                  "houses": [-0.02, 0.0, -0.47], "doorMarks": [-0.02, 0.0, -0.41], "nile": [-0.55, 0.0, -0.04],
                  "nileWater": [-0.55, 0.0, -0.04], "brickyard": [-0.36, 0.0, -0.11], "straw": [-0.452, 0.0, -0.040]},
        "footprints": {"floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]], "palace": [PALACE[0], PALACE[2], PALACE[1], PALACE[3]],
                       "daisFrontZ": DAIS_FRONT, "houses": [[h[0], h[2], h[1], h[3]] for h in HOUSES],
                       "brickyard": [YARD[0], YARD[2], YARD[1], YARD[3]], "nile": [-0.60, -0.345, -0.493, 0.21],
                       "sea": [SEA_X[0], SEA_Z[0], SEA_X[1], SEA_Z[1]], "crossingLane": list(LANE_Z),
                       "seaWaterParts": {"seaWaterBack": [SEA_Z[0], LANE_Z[0]], "seaWaterLane": list(LANE_Z),
                                         "seaWaterFront": [LANE_Z[1], SEA_Z[1]]},
                       "mountain": [MOUNT[0], MOUNT[2], MOUNT[1], MOUNT[3]], "wildernessLane": list(WILD_LANE),
                       "palms": {"palace": [[p[0], p[1]] for p in PALACE_PALMS], "farShore": [[p[0], p[1]] for p in FAR_PALMS]},
                       "obelisks": [list(o) for o in OBELISKS],
                       "crowdWest": [[s[1], s[2]] for s in WEST_SPOTS], "crowdShore": [[s[1], s[2]] for s in SHORE_SPOTS],
                       "crowdFar": [[s[1], s[2]] for s in FAR_SPOTS]},
        "heights": {"daisTop": DAIS_TOP, "columns": 0.200, "cornice": 0.250, "obelisk": 0.258,
                    "houses": [h[4] for h in HOUSES], "bushTop": bush_top, "mountainTop": hmax["mountain"],
                    "seaSurfaceMax": max(sea_rep["seaWaterBackMaxH"], sea_rep["seaWaterFrontMaxH"]),
                    "seaWallBack": sea_rep["seaWallBackH"], "seaWallFront": sea_rep["seaWallFrontH"]},
        "seaWalls": {"rest": "node scale (1, 0.02, 1) and hidden; Effects raise the scale to (1, 1, 1) for sea_part and "
                             "back for sea_close (origin at the wall's foot on the lane edge)",
                     "back": {"node": "seaWallBack", "faces": "+z (inner face at z %.2f)" % LANE_Z[0]},
                     "front": {"node": "seaWallFront", "faces": "-z (inner face at z %.2f)" % LANE_Z[1]},
                     "report": sea_rep},
        "hiddenAtStart": hid,
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227; "
                             "P = world position, or the template position for instanced pieces",
                   "edgeOn": "faces with n . D < 0.22 (n in drawing space: edge-on or facing away) take one clean texel of their region",
                   "namedTexels": "scattered bits, the lane water and the sea walls take one texel of a named "
                                  "(drawing, region); constUV in model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard, "soft": soft, "exempt": EXEMPT},
        "sheetLayout": {"characters": CHAR_PROPOSAL, "charactersFrom": "model/regions_characters.json" if CHARS_FROM_FILE
                        else "proposal (regions_characters.json not there yet)", "placesSetHere": SHEET_PLACE,
                        "awaitingCharacterRerender": CHARS_PENDING},
        "demoColours": COLOURS, "tris": total, "budget": TARGET_TRIS,
    }
    json.dump(d, open(DESIGN_JSON, "w"), indent=1, ensure_ascii=False)


def compose_sheets(idb, regname, crease):
    """quick-look line art + demo colouring of the set drawings, and the preview texture (colours, no lines)"""
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
    tooth = rng.random((H, W)) > 0.965
    grain = fill * (1.0 - 0.14 * (st - 0.5)[..., None])
    grain = np.where(tooth[..., None], grain * 0.8 + 0.2, grain)
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
    save_png(line, os.path.join(WORK, "egypt_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "egypt_drawings_demo.png"))
    tex = np.where(mask[..., None], grain, 0.0); got = mask.copy()
    for _ in range(10):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = shift(got, dy, dx); sv = shift(tex, dy, dx)
            take = sm & ~got
            tex[take] = sv[take]; got |= take
    tex[~got] = 1.0
    return tex, demo


# ============================================================================================ preview
def flat_mat(name, hexc, rough=0.7, emit=None, alpha=None):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (*lin(hex_rgb(hexc)), 1)
    b.inputs["Roughness"].default_value = rough
    if emit:
        b.inputs["Emission Color"].default_value = (*lin(hex_rgb(emit[0])), 1)
        b.inputs["Emission Strength"].default_value = emit[1]
    return m


def tex_mat(name, img, rough=0.85, gloss=False):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.25 if gloss else rough
    try:
        b.inputs["Specular IOR Level"].default_value = 0.6 if gloss else 0.2
    except KeyError:
        pass
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.extension = 'EXTEND'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    W, H = PAGE
    mp.inputs["Location"].default_value = (ART[0] / W, (H - ART[1] - ART[3]) / H, 0)
    mp.inputs["Scale"].default_value = (ART[2] / W, ART[3] / H, 1)
    nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], t.inputs[0])
    if gloss:                                    # preview only: the walls' inner light (the app's shader / FX does this)
        mix = nt.nodes.new("ShaderNodeMixRGB"); mix.blend_type = 'SCREEN'
        mix.inputs[0].default_value = 0.10
        mix.inputs[2].default_value = (0.75, 0.95, 1.0, 1)
        nt.links.new(t.outputs[0], mix.inputs[1]); nt.links.new(mix.outputs[0], b.inputs["Base Color"])
        b.inputs["Emission Color"].default_value = (0.20, 0.55, 0.65, 1)
        b.inputs["Emission Strength"].default_value = 0.10
    else:
        nt.links.new(t.outputs[0], b.inputs["Base Color"])
    return m


def mannequins(layout):
    """preview stand-ins only (not shipped): simple figures in the demo colours"""
    mats = {k: flat_mat("pvm_" + k, v, 0.6) for k, v in {
        "skin": "#C98E66", "white": "#F4F1EA", "cream": "#F1E6CC", "ochre": "#C98B3A", "brown": "#6B4426",
        "staff": "#8A5E3A", "lapis": "#2F5DA8", "gold": "#E8B83A", "kilt": "#FBF8EF", "teal": "#2E9C9A",
        "saffron": "#F2B33D", "rust": "#B5532E", "hair": "#4A2E1F", "turq": "#3FB8AF", "red": "#C2413A"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    for who, (x, z, yaw) in layout.items():
        mb = MB()
        if who == "moses":
            lathe(mb, [(0.0, 0.0), (0.045, 0.0), (0.043, 0.02), (0.035, 0.12), (0.030, 0.22), (0.026, 0.27),
                       (0.0, 0.275)], "cream", C=(x, 0, z), seg=18)
            lathe(mb, [(0.048, 0.04), (0.042, 0.14), (0.036, 0.24), (0.032, 0.27)], "ochre", C=(x, 0, z - 0.003),
                  seg=18, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.55 else 0.0001)
            sphere(mb, (x, 0.305, z), 0.031, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.288, z + 0.016), 0.022, "white", seg=10, rings=7, sh=1.5, sz=0.7)
            sphere(mb, (x, 0.318, z - 0.006), 0.033, "white", seg=12, rings=7, sh=0.8)
            tube(mb, [(x + 0.050, 0.0, z + 0.015), (x + 0.052, 0.36, z + 0.015), (x + 0.040, 0.38, z + 0.015)],
                 0.0045, "staff", seg=6)
        elif who == "pharaoh":
            lathe(mb, [(0.0, 0.0), (0.030, 0.0), (0.034, 0.03), (0.040, 0.10), (0.032, 0.14), (0.0, 0.145)], "kilt",
                  C=(x, 0, z), seg=18)
            lathe(mb, [(0.0, 0.14), (0.030, 0.145), (0.032, 0.24), (0.028, 0.27), (0.0, 0.275)], "skin", C=(x, 0, z),
                  seg=18)
            lathe(mb, [(0.0, 0.24), (0.045, 0.245), (0.044, 0.255), (0.0, 0.258)], "turq", C=(x, 0, z), seg=18)
            sphere(mb, (x, 0.305, z), 0.030, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, 0.345), (0.030, 0.338), (0.038, 0.31), (0.040, 0.27), (0.044, 0.25)], "lapis",
                  C=(x, 0, z - 0.004), seg=16, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.4 else 0.0001)
            lathe(mb, [(0.031, 0.33), (0.0395, 0.30), (0.0405, 0.29)], "gold", C=(x, 0, z - 0.003), seg=16,
                  rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.4 else 0.0001)
        else:
            lathe(mb, [(0.0, 0.0), (0.046, 0.0), (0.044, 0.02), (0.034, 0.10), (0.027, 0.19), (0.024, 0.23),
                       (0.0, 0.235)], "saffron", C=(x, 0, z), seg=18)
            lathe(mb, [(0.029, 0.150), (0.029, 0.162)], "rust", C=(x, 0, z), seg=18)
            sphere(mb, (x, 0.262, z), 0.029, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, 0.205), (0.034, 0.21), (0.036, 0.26), (0.033, 0.29), (0.0, 0.298)], "teal",
                  C=(x, 0, z - 0.006), seg=16, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.35 else 0.0001)
        ob = make_obj("pv_" + who, mb, None, origin=(x, 0.0, z), smooth_angle=60)
        ob["pv"] = 1
        ob.rotation_euler = (0, 0, math.radians(yaw))


def mode_preview():
    if not STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]; walls = STATE["walls"]
    img = save_png(STATE["tex"], os.path.join(WORK, "egypt_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    wmat = tex_mat("pv_wall", img, gloss=True)
    for n, ob in objs.items():
        ob.data.materials.clear(); ob.data.materials.append(wmat if n.startswith("seaWall") or n.startswith("seaWater")
                                                            else pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "egypt_preview_sheet.png")); sheet.pack()
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
    sun.data.angle = math.radians(4)
    fill = link(bpy.data.objects.new("pv_fill", bpy.data.lights.new("pv_fill", 'AREA')))
    fill.data.size = 1.5
    fill.location = B(0.0, 0.8, 1.2); fill.rotation_euler = (B(0, 0.1, -0.2) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    sc.world = bpy.data.worlds.new("w")
    bg = sc.world.node_tree.nodes["Background"]
    fl_l = bpy.data.lights.new("pv_flame_l", 'POINT'); fl_l.color = (1.0, 0.85, 0.55); fl_l.shadow_soft_size = 0.02
    fl_o = link(bpy.data.objects.new("pv_flame_l", fl_l)); fl_o.location = B(*STATE["flame"]) + Vector((0, 0, 0.01))
    flame_m = flat_mat("pv_flame", "#FFE6A0", 0.5, emit=("#FFD27A", 8.0))
    mbf = MB()
    fx, fh, fz = STATE["flame"]
    for k, (dx, s) in enumerate(((0.0, 1.0), (-0.018, 0.7), (0.020, 0.75), (0.008, 0.6))):
        lathe(mbf, [(0.0, fh - 0.03 * s), (0.012 * s, fh - 0.01 * s), (0.008 * s, fh + 0.02 * s), (0.0, fh + 0.05 * s)],
              "f", C=(fx + dx, 0, fz + 0.004 * k), seg=10)
    fob = make_obj("pv_flame", mbf, None); fob.data.materials[0] = flame_m
    win_l = []
    for (hx0, hx1, zb, zf, hh) in HOUSES:                      # warm doorway glow at night (preview only)
        l = bpy.data.lights.new("pv_door", 'POINT'); l.color = (1.0, 0.6, 0.3); l.shadow_soft_size = 0.01
        o = link(bpy.data.objects.new("pv_door", l)); o.location = B((hx0 + hx1) / 2, 0.03, zf + 0.02)
        win_l.append(l)

    def light(mode):
        fob.hide_render = mode != "dusk"; fl_l.energy = 0.0
        for l in win_l:
            l.energy = 0.0
        if mode == "day":
            sun.data.energy = 3.1; sun.data.color = (1.0, 0.95, 0.84)
            sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-30))
            fill.data.energy = 6.0; fill.data.color = (1.0, 0.88, 0.72)
            bg.inputs[0].default_value = (0.84, 0.86, 0.90, 1); bg.inputs[1].default_value = 0.75
        elif mode == "dusk":
            sun.data.energy = 1.6; sun.data.color = (1.0, 0.62, 0.38)
            sun.rotation_euler = (math.radians(72), math.radians(10), math.radians(70))
            fill.data.energy = 2.5; fill.data.color = (0.75, 0.55, 0.95)
            bg.inputs[0].default_value = (0.55, 0.40, 0.55, 1); bg.inputs[1].default_value = 0.6
            fl_l.energy = 0.6
        else:
            sun.data.energy = 0.45; sun.data.color = (0.55, 0.66, 1.0)
            sun.rotation_euler = (math.radians(55), math.radians(20), math.radians(40))
            fill.data.energy = 1.0; fill.data.color = (0.45, 0.55, 1.0)
            bg.inputs[0].default_value = (0.10, 0.13, 0.28, 1); bg.inputs[1].default_value = 0.5
            for l in win_l:
                l.energy = 0.25
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 48
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

    def orbit(target, dist, height, yaw):
        tx, th, tz = target; a = math.radians(yaw)
        return (tx + dist * math.sin(a), th + height, tz + dist * math.cos(a))

    def show(names, on):
        for n in names:
            objs[n].hide_render = not on

    def cast(layout):
        for o in [o for o in bpy.data.objects if o.get("pv")]:
            bpy.data.objects.remove(o, do_unlink=True)
        if layout:
            mannequins(layout)

    def parted(on):
        set_wall_rest(walls, on)
        show(["seaWallBack", "seaWallFront"], on); show(["seaWaterLane"], not on)
    light("day")
    show(HIDDEN_AT_START, False)
    parted(False)
    cast({})
    phone = ((-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280))
    shoot("egypt_preview_phone_set", *phone)
    shoot("egypt_preview_phone_low", (0.02, 0.62, 0.95), (0.02, 0.06, -0.30), 52, (720, 1280))
    shoot("egypt_preview_front", (0.0, 0.26, 2.3), (0.0, 0.14, -0.25), 21, (1600, 1000))
    cast({"pharaoh": (-0.36, -0.30, 0), "miriam": (-0.20, -0.06, 0), "moses": (0.64, -0.30, -90)})
    shoot("egypt_preview_phone", *phone)
    shoot("egypt_preview_orbit", orbit((0.0, 0.10, -0.18), 1.6, 0.55, -30), (0.0, 0.08, -0.18), 38, (1280, 720))
    shoot("egypt_preview_palace", (-0.12, 0.26, 0.10), (-0.36, 0.10, -0.42), 44, (1280, 720))
    shoot("egypt_preview_brickyard", (-0.20, 0.22, 0.16), (-0.37, 0.03, -0.11), 44, (1280, 720))
    light("dusk")
    cast({"moses": (0.07, -0.30, 160)})
    shoot("egypt_preview_bush", orbit((0.12, 0.06, -0.34), 0.62, 0.18, 30), (0.12, 0.07, -0.34), 34, (1280, 720))
    light("night")
    show(["doorMarks"], True)
    cast({})
    shoot("egypt_preview_night", (0.24, 0.22, -0.16), (-0.04, 0.05, -0.43), 44, (1280, 720))
    show(["doorMarks"], False)
    light("day")
    # the hero moment: the sea stands up in two walls
    show(["crowdShore"], True)
    cast({"moses": (0.12, 0.08, -90), "miriam": (0.02, 0.13, -90), "pharaoh": (-0.10, 0.05, 90)})
    shoot("egypt_preview_sea_rest", (0.42, 0.42, 0.75), (0.28, 0.06, -0.02), 40, (1280, 720))
    parted(True)
    show(["crowdShore"], False); show(["crowdFar"], True)
    cast({"moses": (0.30, 0.07, 90), "miriam": (0.27, 0.11, 90)})
    shoot("egypt_preview_sea_parted", (0.42, 0.42, 0.75), (0.28, 0.06, -0.02), 40, (1280, 720))
    shoot("egypt_preview_sea_phone", (0.15, 0.95, 1.15), (0.15, 0.05, -0.50), 55, (720, 1280))
    shoot("egypt_preview_sea_lane", (0.06, 0.13, 0.08), (0.36, 0.09, 0.07), 50, (1280, 720))
    shoot("egypt_preview_sea_back", orbit((0.30, 0.08, 0.05), 0.65, 0.30, 150), (0.30, 0.08, 0.05), 40, (1280, 720))
    cast({})
    shoot("close_wall_inner", (0.30, 0.11, 0.12), (0.30, 0.13, 0.02), 56, (1200, 800), WORK)
    shoot("close_wall_crest", (0.24, 0.30, 0.14), (0.32, 0.22, 0.02), 42, (1200, 800), WORK)
    parted(False); show(["crowdFar"], False)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "egypt_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    if os.environ.get("EX_CLOSEUPS", "1") == "1":
        shoot("close_houses", (0.06, 0.16, -0.25), (-0.02, 0.06, -0.46), 42, (1000, 800), WORK)
        shoot("close_nile", (-0.40, 0.14, 0.10), (-0.54, 0.03, -0.05), 46, (1000, 800), WORK)
        shoot("close_mountain", (0.30, 0.20, -0.15), (0.38, 0.14, -0.52), 50, (1200, 700), WORK)
        shoot("close_backdrop", (-0.20, 0.30, 0.0), (-0.20, 0.14, -0.57), 48, (1200, 700), WORK)
        shoot("close_bush", (0.16, 0.10, -0.22), (0.14, 0.05, -0.37), 40, (1000, 800), WORK)
        shoot("close_farshore", (0.42, 0.20, 0.20), (0.53, 0.12, -0.15), 48, (1000, 800), WORK)
        show(["crowdShore", "crowdFar"], True)
        shoot("close_crowd_west", (-0.30, 0.14, 0.02), (-0.38, 0.05, -0.12), 44, (1200, 800), WORK)
        shoot("close_crowd_shore", (0.06, 0.14, 0.02), (0.18, 0.05, -0.12), 44, (1200, 800), WORK)
        shoot("close_crowd_far", (0.40, 0.14, 0.12), (0.52, 0.05, -0.12), 44, (1200, 800), WORK)
        show(["crowdShore", "crowdFar"], False)
        shoot("close_column", (-0.30, 0.14, -0.30), (-0.255, 0.12, -0.43), 40, (900, 1000), WORK)
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["egypt", "ground", "backdrop", "pyramids", "mountain", "palace", "dais", "throne", "palacePalms", "nile",
        "nileWater", "nileBoat", "brickyard", "straw", "crowdWest", "houses", "doorMarks", "bush", "bushFlame", "sea",
        "seaWater", "seaWaterBack", "seaWaterLane", "seaWaterFront", "seaBed", "seaWallBack", "seaWallFront",
        "farShore", "farRocks", "crowdShore", "crowdFar", "looseWheel", "pillarWest"]


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
                nb = int(((uv < 0) | (uv > 1)).sum()); uv_bad += nb
                if nb:
                    print("UV_OUTSIDE", o.name, nb)
            else:
                uv_bad += 1
    parents = {n: (bpy.data.objects[n].parent.name if bpy.data.objects[n].parent else None) for n in NEED[1:]
               if n in names}
    fl = [round(c, 4) for c in D(bpy.data.objects["bushFlame"].matrix_world.translation)] if "bushFlame" in names else None
    wall = {n: [round(c, 4) for c in bpy.data.objects[n].scale] for n in ("seaWallBack", "seaWallFront") if n in names}
    wall_ok = all(abs(s[2] - 0.02) < 1e-4 and abs(s[0] - 1) < 1e-4 for s in wall.values())
    ok = not missing and tris <= MAX_TRIS and uv_bad == 0 and wall_ok
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "parents": parents, "bushFlame": fl,
                                                         "wallScaleBlender": wall}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
