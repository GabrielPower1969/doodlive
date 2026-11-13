"""Blender (headless): Ruth story pack, Bethlehem at harvest -> assets/ruth/model/bethlehem.glb

A tabletop stage on the colouring sheet, back to front: two layers of hills (terraces, olive bushes, a hint of the
town wall) with cypress trees; Naomi's stone house (stone courses, flat roof with parapet and beam ends, ladder, plank
door under a stone arch, window, storage jars, basket, clay oven and firewood); the round threshing floor (paving, a
stone rim, grain heap, winnowing fork, sacks, an oil lamp on a stone with the empty `lampFlame`); the barley field
(skinned clumps with drooping bearded ears, looping action `fieldSway`), its stubble, sheaves and dry-stone field wall;
a gnarled olive tree with water jars in its shade; the road from Moab; ochre ground with grass, tufts and stones;
hidden `dropped` (stalks Boaz lets fall) and `canopy` (wedding arch).
Contract: docs/ruth/CONTRACT.md §6. Details, nodes, marks and UV rules: docs/ruth/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge (as Esther and David & Goliath). In Blender (Z up) a design point (x, h, z)
is (X, Y, Z) = (x, -z, h); export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `ru_page` = the scanned art rectangle). Each piece belongs to one *drawing* on the
colouring sheet. A drawing is a linear view of its pieces: a = A.P, b = B.P (depth D.P, nearer = larger), and
  u = a / scale + sheetX + 0.5,   v = (b / scale + sheetY) / 1.227
front (A x, B h), plan (A x, B -z), oblique (front-right-above: a = x - kx z, b = h - k z) and side-oblique (the
field wall, seen from -x). P is the vertex's position in its drawing's model: the world position for ordinary pieces,
the template position for instanced ones (barley clumps, sheaves), so every clump wears the one barley drawing.
Faces nearly edge-on to their drawing's view take one clean texel deep inside their own region instead (as Esther's
upward faces); small scattered things (stubble, stones, tufts, dropped stalks) take a texel of a named region.

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/ru_bethlehem.py -- build     bethlehem.glb + .blend + sheet drawings
  blender -b --factory-startup --python pipeline/ru_bethlehem.py -- verify    re-import bethlehem.glb and check it
  blender -b --factory-startup --python pipeline/ru_bethlehem.py -- preview   lit renders (needs a build in this run)
  blender -b --factory-startup --python pipeline/ru_bethlehem.py -- all       build, preview, verify
  blender -b --factory-startup --python pipeline/ru_bethlehem.py -- check     build in memory, print the checks, write nothing
Work files go to $RU_WORK (default /tmp/ru_set_work).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/ruth/model")
GLB = os.path.join(MODEL, "bethlehem.glb")
BLEND = os.path.join(MODEL, "bethlehem.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/ruth/design.json")
TIMELINE = os.path.join(ROOT, "assets/ruth/timeline.json")
WORK = os.environ.get("RU_WORK", "/tmp/ru_set_work")
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
MAX_TRIS = 80000                       # raised from 60k (coordinator, 2026-11-14): spent on barley
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
    "road A": (-0.40, 0.16), "road B": (-0.28, 0.14), "door": (-0.30, -0.20), "door ruth": (-0.18, -0.16),
    "door naomi": (-0.40, -0.22), "glean": (0.14, 0.10), "glean2": (0.24, 0.12), "boaz A": (0.40, 0.16),
    "boaz talk": (0.30, 0.13), "boaz drop": (0.38, 0.06), "night boaz": (0.14, -0.30), "night ruth": (0.00, -0.22),
    "wed boaz": (0.06, 0.08), "wed ruth": (-0.06, 0.08), "wed naomi": (-0.22, 0.12), "fin ruth": (-0.02, 0.14),
    "fin boaz": (0.14, 0.08), "fin naomi": (-0.18, 0.08)}
ENTRANCES = [("ruth in", (-0.62, 0.20), (-0.28, 0.14)), ("naomi in", (-0.62, 0.20), (-0.40, 0.16)),
             ("boaz in", (0.62, 0.18), (0.40, 0.16))]


def _paths():
    """(label, a, b, hard): hard = a move between two stage marks; soft = the first move of the play, from the
    actor's printed place (sheetX, 0) or a park position off the page (reported, not enforced)"""
    out = [(n, a, b, True) for n, a, b in ENTRANCES]
    try:
        tl = json.load(open(TIMELINE))
    except Exception:
        return out
    last = {}
    for a in tl["acting"]:
        if "to" not in a:
            continue
        w, p = a["who"], (float(a["to"][0]), float(a["to"][1]))
        if w in last and math.hypot(p[0] - last[w][0], p[1] - last[w][1]) > 1e-4:
            off = max(abs(p[0]), abs(last[w][0])) > 0.62
            out.append(("%s %.2f,%.2f>%.2f,%.2f" % (w, last[w][0], last[w][1], p[0], p[1]), last[w], p, not off))
        last[w] = p
    return out


PATHS = _paths()
HARD_PTS = list(CONTRACT_MARKS.values())
HARD_SEGS = [(a, b) for _, a, b, hard in PATHS if hard]


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


def pick_sheaf_spots(n=3, reach=0.036, soft=0.05):
    """standing places for the sheaves: the stubble band first, then beside the field; never in the barley; clear of every mark and
    path (hard by 0.05 + reach, soft by 0.04 + reach), at least 0.045 apart"""
    cands = []
    for z in np.arange(FIELD[2], STUBBLE[3] - 0.01, 0.005):
        for x in np.arange(0.12, STUBBLE[1] + 0.04, 0.005):
            if FIELD[0] - 0.01 < x < FIELD[1] + 0.012 and z < FIELD[3] + 0.012:
                continue                                    # the barley stands there
            if clear_dist(x, z) < 0.05 + reach or (soft is not None and clear_dist(x, z, True) < soft + reach):
                continue
            pref = 0 if z > FIELD[3] else 1
            cands.append((pref, -clear_dist(x, z), x, z))
    cands.sort()
    out = []
    for _, _, x, z in cands:
        if all(math.hypot(x - a, z - b) > 0.045 for a, b in out):
            out.append((round(float(x), 3), round(float(z), 3)))
        if len(out) == n:
            break
    if len(out) < 2 and soft is not None:              # not enough room off the reported-only moves: hard rule only
        more = [q for q in pick_sheaf_spots(n + 3, reach, None) if all(math.hypot(q[0] - a, q[1] - b) > 0.045
                                                                      for a, b in out)]
        out += more[:2 - len(out)]
    return out


# demo colouring (DESIGN.md table; the rest chosen to sit with it)
COLOURS = {
    "earth": "#D9B77A", "road": "#E9D9B6", "grass": "#B4C26C", "stubble": "#E9D08A", "fieldSoil": "#C9A065",
    "hillNear": "#A7B86A", "hillFar": "#8FA9A0", "cypress": "#3F6B45", "bush": "#7F9E5C", "town": "#DCC79E",
    "houseStone": "#D9C29A", "doorArch": "#C7AE84", "roof": "#C9A77A", "door": "#8A5A3B", "wood": "#A47548",
    "windowDark": "#5A3D2A", "flax": "#D9C27E", "jar": "#C8643C", "basket": "#C9A05C", "oven": "#B97E55",
    "threshFloor": "#E4CD95", "rimStone": "#BDAE93", "grain": "#E6B24A", "straw": "#E9D08A", "sack": "#EBDDBF",
    "lamp": "#C8643C", "barley": "#E8B84A", "barleyLeaf": "#B7B85A", "sheaf": "#E2A93B", "sheafTie": "#9A6A3E",
    "wallStone": "#CDBB98", "oliveCrown": "#8FA876", "oliveTrunk": "#7A6650", "waterJar": "#C8643C",
    "canopyCloth": "#FFFFFF", "canopyPole": "#A47548", "flowerPink": "#F4A6B8", "flowerYellow": "#F7D154",
    "garland": "#8DB36A",
}


# ============================================================================================ mesh builder
class MB:
    """vertices (design coords) + P (the vertex in its drawing's model), faces with region, smooth flag, a
    no-raster flag (scattered bits that sample a named texel) and optional skin weights"""

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


# layout of the page (design x, z)
HOUSE = (-0.44, -0.163, -0.53, -0.333)        # core x0 x1 zb zf ; stones stand 3-5 mm proud of it
HOUSE_H = 0.200
DOOR_X, DOOR_HW, DOOR_SPRING, DOOR_R = -0.30, 0.035, 0.110, 0.035
WIN_X, WIN_HW, WIN_H0, WIN_H1 = -0.212, 0.020, 0.118, 0.156
THR_C, THR_R = (0.30, -0.44), 0.112
FIELD = (0.20, 0.54, -0.22, 0.00)             # barley x0 x1 z0 z1
STUBBLE = (0.10, 0.54, 0.00, 0.08)
WALL_X = 0.188
OLIVE = (-0.44, -0.10)
CANOPY_X, CANOPY_TOP = 0.14, 0.446
SHEAF_SPOTS = [(0.225, -0.040), (0.255, -0.004), (0.44, 0.02)]
WATER = [(-0.430, -0.022, 0.060, 0.0), (-0.462, -0.040, 0.052, 1.0), (-0.476, -0.004, 0.047, 2.0)]


def road_polys():
    road = catmull([(-0.60, 0.176), (-0.50, 0.170), (-0.40, 0.160), (-0.30, 0.140), (-0.235, 0.100), (-0.205, 0.030),
                    (-0.212, -0.060), (-0.245, -0.150), (-0.283, -0.240), (-0.300, -0.300), (-0.300, -0.336)], 0.012)
    path = catmull([(-0.225, 0.075), (-0.10, 0.088), (0.02, 0.080), (0.105, 0.062)], 0.012)
    return strip_poly(road, 0.105, 0.078), strip_poly(path, 0.052, 0.040), road


GRASS = [(-0.53, -0.25, 0.055, 1), (-0.07, -0.48, 0.06, 2), (0.07, -0.37, 0.045, 3), (0.54, -0.22, 0.04, 4),
         (-0.54, 0.06, 0.045, 5), (-0.02, 0.17, 0.04, 6), (0.50, 0.15, 0.045, 7), (-0.12, -0.04, 0.05, 8),
         (-0.56, -0.47, 0.035, 9), (0.53, -0.53, 0.035, 10)]


# ============================================================================================ ground
def build_ground(root):
    """the page floor: a constrained triangulation of the plan regions (earth, road + footpath, grass patches, field
    soil, stubble band), gently uneven, with a skirt; `road` is its own node. Tufts (grass texel) and pebbles
    (field-wall stone texel) are scattered on it."""
    road, path, cl = road_polys()
    grass = []
    for cx, cz, r, s in GRASS:
        g = blob_poly(cx, cz, r, s)
        if min(seg_dist((cx, cz), tuple(cl[i]), tuple(cl[i + 1])) for i in range(len(cl) - 1)) < r + 0.065:
            continue
        grass.append(g)
    field = np.array([(FIELD[0], FIELD[2]), (FIELD[1], FIELD[2]), (FIELD[1], FIELD[3]), (FIELD[0], FIELD[3])])
    stub = np.array([(STUBBLE[0], STUBBLE[2]), (STUBBLE[1], STUBBLE[2]), (STUBBLE[1], STUBBLE[3]),
                     (STUBBLE[0], STUBBLE[3])])
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    outlines = [_resample(rect, 0.03), _resample(road, 0.012), _resample(path, 0.012), _resample(field, 0.02),
                _resample(stub, 0.02)] + [_resample(g, 0.01) for g in grass]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    allo = np.concatenate(outlines)
    for j, z in enumerate(np.arange(FLOOR[2] + 0.02, FLOOR[3] - 0.01, 0.032)):
        for x in np.arange(FLOOR[0] + 0.02 + (j % 2) * 0.016, FLOOR[1] - 0.01, 0.032):
            p = np.array([x + (nz(x, z) - 0.5) * 0.012, z + (nz(z, x) - 0.5) * 0.012])
            if np.min(np.hypot(*(allo - p).T)) > 0.009:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def height(x, z):
        h = 0.0012 + 0.0011 * (math.sin(17 * x + 3 * z) * math.sin(11 * z - 5 * x) * 0.5 + 0.5) + 0.0004 * nz(x, z)
        if in_poly((x, z), road) or in_poly((x, z), path):
            h = 0.0005 + 0.0002 * nz(x, z)
        return h
    H = [height(x, z) for x, z in V]

    def region(c):
        if in_poly(c, road) or in_poly(c, path):
            return "road"
        if in_poly(c, stub):
            return "stubble"
        if in_poly(c, field):
            return "fieldSoil"
        for g in grass:
            if in_poly(c, g):
                return "grass"
        return "earth"
    mg, mr = MB(), MB()
    idx_g, idx_r = {}, {}
    for f in fs:
        if len(f) != 3:
            continue
        c = tuple(V[list(f)].mean(0))
        reg = region(c)
        mb, idx = (mr, idx_r) if reg == "road" else (mg, idx_g)
        q = []
        for i in f:
            if i not in idx:
                idx[i] = mb.v(V[i][0], H[i], V[i][1])
            q.append(idx[i])
        mb.fo(q, reg, UP)
    # skirt round the page edge
    for (ax, az), (bx, bz) in zip(rect, np.roll(rect, -1, axis=0)):
        n = int(math.hypot(bx - ax, bz - az) / 0.05) + 1
        out = (az - bz, 0, bx - ax) if False else None
        cx, cz = (ax + bx) / 2, (az + bz) / 2
        o = (cx, 0, cz - (FLOOR[2] + FLOOR[3]) / 2) if abs(az - bz) < 1e-6 else (cx, 0, 0)
        for i in range(n):
            x0, z0 = ax + (bx - ax) * i / n, az + (bz - az) * i / n
            x1, z1 = ax + (bx - ax) * (i + 1) / n, az + (bz - az) * (i + 1) / n
            mg.fo([mg.v(x0, height(x0, z0), z0), mg.v(x1, height(x1, z1), z1), mg.v(x1, -0.002, z1),
                   mg.v(x0, -0.002, z0)], "earth", o)
    # scattered bits: tufts and pebbles (no-raster: they sample named texels)
    rng = random.Random(11)
    mg.nr = True
    blocked = [HOUSE, (0.16, 0.44, -0.59, -0.30)]

    def free(x, z, pad=0.0):
        if not (FLOOR[0] + 0.01 < x < FLOOR[1] - 0.01 and FLOOR[2] + 0.04 < z < FLOOR[3] - 0.01):
            return False
        for x0, x1, z0, z1 in blocked:
            if x0 - pad < x < x1 + pad and z0 - pad < z < z1 + pad + 0.03:
                return False
        if FIELD[0] - 0.02 < x < FIELD[1] + 0.01 and FIELD[2] - 0.01 < z < STUBBLE[3] + 0.005:
            return False
        if math.hypot(x - OLIVE[0], z - OLIVE[1]) < 0.035:
            return False
        return True
    tufts = []
    tries = 0
    while len(tufts) < 96 and tries < 6000:
        tries += 1
        if rng.random() < 0.55 and grass:
            g = grass[rng.randrange(len(grass))]; c = g.mean(0)
            x, z = c[0] + rng.uniform(-0.05, 0.05), c[1] + rng.uniform(-0.04, 0.04)
            if not in_poly((x, z), g):
                continue
        else:
            x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z) or in_poly((x, z), road) or in_poly((x, z), path):
            continue
        if any(math.hypot(x - a, z - b) < 0.026 for a, b in tufts):
            continue
        tufts.append((x, z))
    for x, z in tufts:
        tall = 0.016 if clear_dist(x, z, True) > 0.064 else 0.0105
        nb = 5
        for k in range(nb):
            a = TAU * k / nb + rng.uniform(-0.4, 0.4)
            hh = tall * rng.uniform(0.7, 1.05); lean = rng.uniform(0.25, 0.5) * hh
            d = (math.cos(a), math.sin(a))
            pts = [(x + d[0] * 0.0015, 0.0005, z + d[1] * 0.0015), (x + d[0] * lean, hh, z + d[1] * lean)]
            blade(mg, pts, [0.0036, 0.0], "grass", nrm=(d[0], 0.0, d[1]))
    pebbles = []
    tries = 0
    while len(pebbles) < 62 and tries < 6000:
        tries += 1
        if rng.random() < 0.4:                          # along the road's edges
            i = rng.randrange(len(cl) - 1); p = cl[i]; t = cl[i + 1] - p; t /= np.linalg.norm(t)
            s = rng.choice((-1, 1)) * rng.uniform(0.042, 0.058)
            x, z = p[0] - t[1] * s, p[1] + t[0] * s
        else:
            x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.56, 0.20)
        if not free(x, z) or any(math.hypot(x - a, z - b) < 0.016 for a, b in pebbles + tufts):
            continue
        pebbles.append((x, z))
    for i, (x, z) in enumerate(pebbles):
        r = rng.uniform(0.0035, 0.0065)
        lumpy(mg, (x, r * 0.35, z), r, "stone", seg=5, rings=3, sh=0.55, sx=rng.uniform(0.9, 1.4), amp=0.18, seed=i)
    rocks = []                                         # a few bigger rocks and thorny shrubs near the page edges
    tries = 0
    while len(rocks) < 18 and tries < 6000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.56, 0.20)
        cd = clear_dist(x, z, True)
        if not free(x, z, 0.01) or in_poly((x, z), road) or in_poly((x, z), path) or cd < 0.078:
            continue
        if any(math.hypot(x - a, z - b) < 0.05 for a, b, _ in rocks) or \
                any(math.hypot(x - a, z - b) < 0.02 for a, b in pebbles + tufts):
            continue
        rocks.append((x, z, cd))
    for i, (x, z, cd) in enumerate(rocks):
        if i % 3 == 2:
            r = rng.uniform(0.013, 0.019)
            lumpy(mg, (x, r * 0.55, z), r, "bush", seg=8, rings=5, sh=0.72, amp=0.22, seed=i + 500)
        else:
            r = rng.uniform(0.008, 0.013)
            lumpy(mg, (x, r * 0.30, z), r, "stone", seg=7, rings=4, sh=0.62, sx=rng.uniform(1.0, 1.5), amp=0.2,
                  seed=i + 700, smooth=False)
    mg.nr = False
    ob = make_obj("ground", mg, root, smooth_angle=35)
    rd = make_obj("road", mr, ob, smooth_angle=35)
    return ob, rd, {"tufts": len(tufts), "pebbles": len(pebbles), "rocksShrubs": len(rocks)}


# ============================================================================================ hills
def near_ridge(x):
    return (0.082 + 0.078 * math.exp(-((x + 0.38) / 0.21) ** 2) + 0.066 * math.exp(-((x - 0.30) / 0.20) ** 2)
            + 0.008 * math.sin(13 * x + 1.0))


def far_ridge(x):
    return (0.165 + 0.105 * math.exp(-((x + 0.15) / 0.22) ** 2) + 0.072 * math.exp(-((x - 0.45) / 0.16) ** 2)
            + 0.010 * math.sin(9 * x + 0.5))


NEAR_ZB, NEAR_ZR, FAR_Z = -0.552, -0.589, -0.590


def near_pt(x, t):
    s = math.sin(0.5 * math.pi * t) ** 1.25
    return (x, near_ridge(x) * s, NEAR_ZB + (NEAR_ZR - NEAR_ZB) * (t ** 0.8))


def build_hills(root):
    """backdrop relief: a far blue-green ridge (flat, like a painted flat) with the hint of a town wall and houses,
    a near warm-green slope with three stone terrace lines, round olive bushes, and six cypress trees"""
    mb = MB()
    # far ridge
    xs = np.linspace(-0.60, 0.60, 61)
    poly = [(-0.60, 0.0), (0.60, 0.0)] + [(x, far_ridge(x)) for x in xs[::-1]]
    extrude(mb, poly, FAR_Z - 0.010, FAR_Z, "hillFar", back=False)
    # town on the far hill's left shoulder: wall with crenels, houses stepping up, one tower
    tz = FAR_Z
    for i, x in enumerate(np.arange(-0.265, -0.035, 0.0115)):
        hb = far_ridge(x) - 0.052
        box(mb, x, x + 0.0118, hb - 0.012, hb + (0.006 if i % 2 == 0 else 0.0), tz - 0.004, tz + 0.0045, "town",
            skip=("back", "bottom"))
    for j, (x, w, hgt) in enumerate(((-0.25, 0.024, 0.018), (-0.222, 0.020, 0.024), (-0.196, 0.026, 0.016),
                                     (-0.168, 0.022, 0.026), (-0.140, 0.024, 0.020), (-0.112, 0.020, 0.023),
                                     (-0.086, 0.026, 0.017), (-0.058, 0.020, 0.021))):
        hb = far_ridge(x + w / 2) - 0.046
        box(mb, x, x + w, hb, hb + hgt, tz - 0.004, tz + 0.0032, "town", skip=("back", "bottom"))
        if j % 2 == 0:
            box(mb, x + w * 0.3, x + w * 0.6, hb + hgt * 0.35, hb + hgt * 0.75, tz + 0.0032, tz + 0.0040, "town",
                skip=("back", "bottom"))
    box(mb, -0.212, -0.192, far_ridge(-0.2) - 0.058, far_ridge(-0.2) - 0.006, tz - 0.004, tz + 0.006, "town",
        skip=("back", "bottom"))
    # near slope (grid)
    NX, NT = 64, 9
    xs = np.linspace(-0.60, 0.60, NX + 1); ts = np.linspace(0, 1, NT + 1)
    g = [[mb.v(*near_pt(x, t)) for t in ts] for x in xs]
    for i in range(NX):
        for j in range(NT):
            mb.fo([g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]], "hillNear", (0, 0.5, 1), True)
    # ridge top lip back to the far panel (closes the silhouette from above)
    for i in range(NX):
        a, b = near_pt(xs[i], 1.0), near_pt(xs[i + 1], 1.0)
        mb.fo([g[i][NT], g[i + 1][NT], mb.v(b[0], b[1], FAR_Z + 0.0005), mb.v(a[0], a[1], FAR_Z + 0.0005)],
              "hillNear", UP, True)
    # terrace lines: low stone ledges along the contours
    for t in (0.34, 0.58, 0.80):
        pts = [near_pt(x, t) for x in np.linspace(-0.585, 0.585, 48)]
        pts = [(x, h + 0.0015, z + 0.0022) for x, h, z in pts]
        tube(mb, pts, 0.0028, "hillNear", seg=3, smooth=False, caps=False)
    # bushes on the slope and at its foot
    rng = random.Random(5)
    for i in range(14):
        x = rng.uniform(-0.58, 0.58); t = rng.uniform(0.12, 0.7)
        if HOUSE[0] - 0.02 < x < HOUSE[1] + 0.02 and t < 0.75:
            t = rng.uniform(0.80, 0.92)
        px, ph, pz = near_pt(x, t)
        r = rng.uniform(0.010, 0.016)
        lumpy(mb, (px, ph + r * 0.55, pz + 0.006), r, "bush", seg=9, rings=5, sh=0.8, amp=0.16, seed=i + 20)
    # cypress trees standing at the slope's foot
    for i, (x, H, rm) in enumerate(((-0.565, 0.19, 0.020), (-0.085, 0.235, 0.022), (-0.040, 0.18, 0.018),
                                    (0.075, 0.205, 0.020), (0.475, 0.17, 0.018), (0.565, 0.215, 0.021))):
        z = NEAR_ZB - 0.010
        prof = []
        n = 15
        for k in range(n + 1):
            u = k / n
            r = rm * (u / 0.16) ** 0.55 if u < 0.16 else rm * ((1 - u) / 0.84) ** 0.8
            r *= 1.0 + 0.10 * math.cos(TAU * u * 5.5)
            prof.append((max(r, 0.0), H * u))
        prof[0] = (0.0, -0.002); prof[-1] = (0.0, H)
        lathe(mb, prof, "cypress", C=(x, 0, z), seg=11, smooth=True,
              rfun=lambda th, ii, k, s=i: 1.0 + 0.16 * (nz(ii, k, s) - 0.5) * 2)
    return make_obj("hills", mb, root, smooth_angle=55)


# ============================================================================================ house
def masonry(mb, L, H, W, holes, rng, reg="houseStone", rows=None, decor=None):
    """stone courses on a wall: s along the wall (0..L), h up (0..H); W(s, h, d) -> world, d = out of the wall.
    holes(h0, h1) -> list of blocked (s0, s1). Each stone is a chamfered block 2.5-5 mm proud."""
    rows = rows or [0.020, 0.024, 0.021, 0.023, 0.022, 0.020, 0.024, 0.022, 0.024]
    sc = H / sum(rows)
    h = 0.0
    for ri, rh in enumerate(rows):
        rh *= sc
        h0, h1 = h, h + rh
        h = h1
        blocked = sorted(holes(h0, h1))
        if decor is not None and ri > 0:               # the bed joint under this course, cut at the openings
            segs, a0 = [], 0.0
            for bs0, bs1 in blocked:
                if bs0 > a0:
                    segs.append((a0, bs0))
                a0 = max(a0, bs1)
            if a0 < L:
                segs.append((a0, L))
            for a, b in segs:
                decor.append((W(a, h0, 0.0), W(b, h0, 0.0)))
        s = -rng.uniform(0.0, 0.02) if ri % 2 else 0.0
        while s < L - 1e-4:
            w = rng.uniform(0.026, 0.046)
            a, b = max(s, 0.0), min(s + w, L)
            s += w
            for bs0, bs1 in blocked:                   # cut the stone at a hole
                if a < bs1 and b > bs0:
                    if a >= bs0 and b <= bs1:
                        a = b
                    elif a < bs0:
                        b = bs0
                    else:
                        a = bs1
            if b - a < 0.008:
                continue
            if decor is not None and b < L - 1e-4:     # head joint at the stone's end
                decor.append((W(b, h0, 0.0), W(b, h1, 0.0)))
            g, c = 0.0013, 0.0016
            dp = rng.uniform(0.0025, 0.005)
            sa, sb, ha, hb = a + g, b - g, h0 + g, h1 - g
            o = [mb.v(*W(sa, ha, 0)), mb.v(*W(sb, ha, 0)), mb.v(*W(sb, hb, 0)), mb.v(*W(sa, hb, 0))]
            j = lambda: rng.uniform(-0.0006, 0.0006)
            n = [mb.v(*W(sa + c + j(), ha + c, dp)), mb.v(*W(sb - c + j(), ha + c, dp + j())),
                 mb.v(*W(sb - c + j(), hb - c, dp)), mb.v(*W(sa + c + j(), hb - c, dp + j()))]
            out = Vector(W(0, 0, 1)) - Vector(W(0, 0, 0))
            mb.fo(n, reg, tuple(out))
            sides = [(Vector(W(0, -1, 0)) - Vector(W(0, 0, 0))), (Vector(W(1, 0, 0)) - Vector(W(0, 0, 0))),
                     (Vector(W(0, 1, 0)) - Vector(W(0, 0, 0))), (Vector(W(-1, 0, 0)) - Vector(W(0, 0, 0)))]
            for k in range(4):
                mb.fo([o[k], o[(k + 1) % 4], n[(k + 1) % 4], n[k]], reg, tuple(sides[k] + out * 0.3))


def door_outline(n=10):
    """the door opening: a rectangle with a round arch top (x, h)"""
    pts = [(DOOR_X - DOOR_HW, 0.0), (DOOR_X + DOOR_HW, 0.0)]
    for k in range(n + 1):
        a = math.pi * k / n
        pts.append((DOOR_X + DOOR_HW * math.cos(a), DOOR_SPRING + DOOR_R * math.sin(a)))
    return pts


def build_house(root):
    """Naomi's house: stone-course walls round a core, flat clay roof inside a parapet, wooden beam ends, a stone
    arch over the door opening, a window with a lintel and bars, a threshold slab, flax drying on the roof.
    Children: door, window, ladder, houseJars, basket, oven (with firewood)."""
    rng = random.Random(3)
    mb = MB()
    x0, x1, zb, zf = HOUSE
    H = HOUSE_H
    # core: front face with the door and window openings, reveals, plain sides/back, roof slab
    win = [(WIN_X - WIN_HW, WIN_H0), (WIN_X + WIN_HW, WIN_H0), (WIN_X + WIN_HW, WIN_H1), (WIN_X - WIN_HW, WIN_H1)]
    dr = door_outline()
    outer = [(x0, 0.0), (x1, 0.0), (x1, H), (x0, H)]
    tris = tessellate_polygon([[Vector((a, b, 0)) for a, b in outer], [Vector((a, b, 0)) for a, b in dr],
                               [Vector((a, b, 0)) for a, b in win]])
    allp = outer + dr + win
    vi = [mb.v(a, b, zf) for a, b in allp]
    for t in tris:
        mb.fo([vi[i] for i in t], "houseStone", (0, 0, 1))
    for hole, depth, reg in ((dr, 0.013, "houseStone"), (win, 0.015, "houseStone")):
        n = len(hole)
        area = sum(hole[i][0] * hole[(i + 1) % n][1] - hole[(i + 1) % n][0] * hole[i][1] for i in range(n))
        for i in range(n):
            a, b = hole[i], hole[(i + 1) % n]
            if a[1] == 0.0 and b[1] == 0.0:
                continue
            dx, dh = b[0] - a[0], b[1] - a[1]
            o = (-dh, dx) if area > 0 else (dh, -dx)
            mb.fo([mb.v(a[0], a[1], zf), mb.v(b[0], b[1], zf), mb.v(b[0], b[1], zf - depth),
                   mb.v(a[0], a[1], zf - depth)], reg, (o[0], o[1], 0))
    ngon_top(mb, [(WIN_X - WIN_HW, zf - 0.015), (WIN_X + WIN_HW, zf - 0.015), (WIN_X + WIN_HW, zf - 0.0151),
                  (WIN_X - WIN_HW, zf - 0.0151)], WIN_H0, "houseStone")
    box(mb, x0, x1, 0.0, H, zb, zf, "houseStone", skip=("front", "bottom", "top"))
    # roof slab inside the parapet, parapet walls with a rough top
    PT, PH = 0.012, 0.026
    box(mb, x0 + PT, x1 - PT, H - 0.004, H, zb + PT, zf - PT, "roof", skip=("bottom",))
    for (ax0, ax1, az0, az1) in ((x0 - 0.002, x1 + 0.002, zf - PT, zf + 0.002), (x0 - 0.002, x1 + 0.002, zb, zb + PT),
                                 (x0 - 0.002, x0 + PT, zb, zf), (x1 - PT, x1 + 0.002, zb, zf)):
        box(mb, ax0, ax1, H, H + PH - 0.004, az0, az1, "houseStone", skip=("bottom",))
    for i, x in enumerate(np.arange(x0, x1 - 0.01, 0.031)):        # cap stones along the front parapet
        box(mb, x + 0.001, min(x + 0.030, x1 + 0.002) - 0.001, H + PH - 0.004, H + PH, zf - PT - 0.001, zf + 0.004,
            "houseStone", skip=("bottom",))
    for i, z in enumerate(np.arange(zb, zf - 0.01, 0.033)):          # and along the right parapet
        box(mb, x1 - PT - 0.001, x1 + 0.004, H + PH - 0.004, H + PH, z + 0.001, min(z + 0.032, zf) - 0.001,
            "houseStone", skip=("bottom",))

    def holes_front(h0, h1):
        out = []
        top = DOOR_SPRING + DOOR_R + 0.016
        if h0 < top:
            hm = min(max(DOOR_SPRING, h0), h1)
            if h1 <= DOOR_SPRING:
                hw = DOOR_HW + 0.002
            else:
                R = DOOR_R + 0.016
                hh = max(h0, DOOR_SPRING)
                hw = math.sqrt(max(0.0, R * R - (hh - DOOR_SPRING) ** 2)) + 0.002
                if h0 < DOOR_SPRING:
                    hw = max(hw, DOOR_HW + 0.002)
            out.append((DOOR_X - hw - x0, DOOR_X + hw - x0))
        if h0 < WIN_H1 + 0.010 and h1 > WIN_H0 - 0.004:
            out.append((WIN_X - WIN_HW - 0.006 - x0, WIN_X + WIN_HW + 0.006 - x0))
        return out
    dec = DECOR.setdefault("house", [])
    masonry(mb, x1 - x0, H, lambda s, h, d: (x0 + s, h, zf + d), holes_front, rng, decor=dec)
    masonry(mb, zf - zb, H, lambda s, h, d: (x1 + d, h, zf - s), lambda a, b: [], rng, decor=dec)
    # voussoir arch over the door
    nv = 7
    for k in range(nv):
        a0 = math.pi * k / nv + 0.012; a1 = math.pi * (k + 1) / nv - 0.012
        r0, r1 = DOOR_R + 0.001, DOOR_R + 0.0155
        poly = [(DOOR_X + r0 * math.cos(a0), DOOR_SPRING + r0 * math.sin(a0)),
                (DOOR_X + r1 * math.cos(a0), DOOR_SPRING + r1 * math.sin(a0)),
                (DOOR_X + r1 * math.cos(a1), DOOR_SPRING + r1 * math.sin(a1)),
                (DOOR_X + r0 * math.cos(a1), DOOR_SPRING + r0 * math.sin(a1))][::-1]
        extrude(mb, poly, zf, zf + 0.0065, "doorArch", back=False)
    for s in (-1, 1):                                            # jamb blocks at the springing
        box(mb, DOOR_X + s * DOOR_HW - (0.0 if s > 0 else 0.016), DOOR_X + s * DOOR_HW + (0.016 if s > 0 else 0.0),
            DOOR_SPRING - 0.016, DOOR_SPRING, zf, zf + 0.0055, "doorArch", skip=("back",))
    # threshold slab, window lintel and sill
    box(mb, DOOR_X - 0.046, DOOR_X + 0.046, 0.0, 0.0065, zf - 0.013, zf + 0.026, "doorArch", skip=("bottom",))
    box(mb, WIN_X - WIN_HW - 0.010, WIN_X + WIN_HW + 0.010, WIN_H1, WIN_H1 + 0.0085, zf, zf + 0.0075, "wood",
        skip=("back",))
    box(mb, WIN_X - WIN_HW - 0.005, WIN_X + WIN_HW + 0.005, WIN_H0 - 0.006, WIN_H0, zf - 0.004, zf + 0.008,
        "doorArch", skip=("back",))
    # beam ends under the roof line
    for i, x in enumerate(np.linspace(x0 + 0.022, x1 - 0.020, 7)):
        if abs(x - DOOR_X) < 0.012:
            continue
        lathe(mb, [(0.0, 0.0), (0.0058, 0.0), (0.0058, 0.016), (0.0, 0.0165)], "wood",
              C=(x + (nz(i) - 0.5) * 0.004, H - 0.013, zf - 0.002), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=7,
              smooth=True)
    # flax drying on the roof
    for (cx, cz, L, a) in ((-0.36, -0.47, 0.070, 0.15), (-0.29, -0.44, 0.062, -0.25), (-0.235, -0.48, 0.05, 0.6)):
        d = (math.cos(a) * L / 2, math.sin(a) * L / 2)
        pts = [(cx - d[0], H + 0.006, cz - d[1]), (cx, H + 0.0075, cz), (cx + d[0], H + 0.006, cz + d[1])]
        tube(mb, pts, [0.0055, 0.0068, 0.005], "flax", seg=7)
    house = make_obj("house", mb, root, origin=(-0.30, 0.0, -0.43), bevel=0.0009, bevel_angle=60)
    kids = {}
    # door: planks (each with grain ridges), two battens, a diagonal brace, nails, an iron ring
    m = MB()
    zd = zf - 0.013
    xs = np.linspace(DOOR_X - DOOR_HW, DOOR_X + DOOR_HW, 5)

    def top_at(x):
        return DOOR_SPRING + math.sqrt(max(0.0, DOOR_R ** 2 - (x - DOOR_X) ** 2))
    for i in range(4):
        for j in range(3):
            xa = xs[i] + (xs[i + 1] - xs[i]) * j / 3 + (0.0006 if j == 0 else 0.0)
            xb = xs[i] + (xs[i + 1] - xs[i]) * (j + 1) / 3 - (0.0006 if j == 2 else 0.0)
            tp = [(x, top_at(x) - 0.0004) for x in np.linspace(xb, xa, 4)]
            poly = [(xa, 0.0015), (xb, 0.0015)] + tp
            dz = 0.0035 + (0.0006 if j == 1 else 0.0) + 0.0005 * nz(i, j)
            extrude(m, poly, zd, zd + dz, "door", back=False)
    for hb in (0.030, 0.088):
        box(m, DOOR_X - DOOR_HW + 0.004, DOOR_X + DOOR_HW - 0.004, hb - 0.0055, hb + 0.0055, zd + 0.004, zd + 0.0075,
            "door", skip=("back",))
    br = [(DOOR_X - DOOR_HW + 0.006, 0.033), (DOOR_X - DOOR_HW + 0.016, 0.033), (DOOR_X + DOOR_HW - 0.006, 0.083),
          (DOOR_X + DOOR_HW - 0.016, 0.083)][::-1]
    extrude(m, [br[0], br[1], br[2], br[3]], zd + 0.004, zd + 0.0068, "door", back=False)
    for hb in (0.030, 0.088):
        for x in np.linspace(DOOR_X - DOOR_HW + 0.008, DOOR_X + DOOR_HW - 0.008, 4):
            box(m, x - 0.0012, x + 0.0012, hb - 0.0012, hb + 0.0012, zd + 0.0075, zd + 0.0088, "wood", skip=("back",))
    tube(m, [(DOOR_X + 0.019 + 0.0055 * math.cos(TAU * k / 12), 0.060 + 0.0055 * math.sin(TAU * k / 12),
              zd + 0.0082) for k in range(12)], 0.0011, "wood", seg=5, closed=True, ref=(0, 0, 1))
    kids["door"] = make_obj("door", m, house, origin=(DOOR_X, 0.0, zd))
    # window: dark back, two wooden bars and a shutter half open
    m = MB()
    box(m, WIN_X - WIN_HW, WIN_X + WIN_HW, WIN_H0, WIN_H1, zf - 0.016, zf - 0.0145, "windowDark", skip=("back",))
    for x in (WIN_X - 0.0068, WIN_X + 0.0068):
        box(m, x - 0.0018, x + 0.0018, WIN_H0, WIN_H1, zf - 0.009, zf - 0.006, "wood")
    box(m, WIN_X - WIN_HW, WIN_X + WIN_HW, (WIN_H0 + WIN_H1) / 2 - 0.0016, (WIN_H0 + WIN_H1) / 2 + 0.0016,
        zf - 0.009, zf - 0.006, "wood")
    kids["window"] = make_obj("window", m, house, origin=(WIN_X, WIN_H0, zf))
    # ladder against the right wall, up past the parapet
    m = MB()
    foot, top = (-0.084, 0.0), (-0.1575, H + PH + 0.016)
    zs = (-0.404, -0.452)
    for k, zr in enumerate(zs):
        pts = []
        for j in range(5):
            u = j / 4
            pts.append((foot[0] + (top[0] - foot[0]) * u + 0.0012 * math.sin(3.1 * u + k), top[1] * u,
                        zr + 0.0008 * math.sin(5 * u + k)))
        tube(m, pts, 0.0030, "wood", seg=5, smooth=True)
    for j in range(1, 8):
        u = j / 8.3
        x = foot[0] + (top[0] - foot[0]) * u
        tube(m, [(x, top[1] * u, zs[0] + 0.004), (x, top[1] * u - 0.0015, zs[1] - 0.004)], 0.0022, "wood", seg=5,
             caps=False)
    kids["ladder"] = make_obj("ladder", m, house, origin=(foot[0], 0.0, sum(zs) / 2))
    # two storage jars by the door, a basket
    m = MB()
    for (jx, jz, s) in ((-0.372, -0.306, 1.0), (-0.404, -0.318, 0.86)):
        prof = [(0.0, 0.0), (0.0085, 0.0), (0.016, 0.010), (0.0205, 0.024), (0.0205, 0.036), (0.0155, 0.050),
                (0.0085, 0.057), (0.0085, 0.061), (0.0108, 0.0635), (0.0075, 0.064), (0.0, 0.056)]
        lathe(m, [(r * s, a * s) for r, a in prof], "jar", C=(jx, 0, jz), seg=16)
        for sg in (-1, 1):
            tube(m, [(jx + sg * 0.0085 * s, 0.058 * s, jz), (jx + sg * 0.016 * s, 0.059 * s, jz),
                     (jx + sg * 0.0185 * s, 0.048 * s, jz)], 0.0019 * s, "jar", seg=5)
    kids["houseJars"] = make_obj("houseJars", m, house, origin=(-0.388, 0.0, -0.312))
    m = MB()
    bx, bz = -0.218, -0.305
    lathe(m, [(0.0, 0.0), (0.011, 0.0), (0.0145, 0.008), (0.0168, 0.018), (0.0178, 0.024), (0.0186, 0.0255),
              (0.0168, 0.0262), (0.0160, 0.022), (0.0, 0.020)], "basket", C=(bx, 0, bz), seg=18, smooth=False,
          rfun=lambda th, i, k: 1.0 + (0.045 if (i + k) % 2 else -0.02) * (1 if 0 < i < 6 else 0))
    lumpy(m, (bx, 0.0205, bz), 0.0150, "basket", seg=12, rings=5, sh=0.28, amp=0.08, seed=4)
    tube(m, [(bx - 0.016, 0.025, bz), (bx - 0.008, 0.041, bz), (bx + 0.008, 0.041, bz), (bx + 0.016, 0.025, bz)],
         0.0016, "basket", seg=5)
    kids["basket"] = make_obj("basket", m, house, origin=(bx, 0.0, bz))
    # clay oven (tabun) and firewood beside the house
    m = MB()
    ox, oz = -0.497, -0.372
    lathe(m, [(0.0, 0.0), (0.031, 0.0), (0.031, 0.008), (0.027, 0.022), (0.019, 0.034), (0.0095, 0.040),
              (0.0075, 0.0405), (0.0072, 0.036), (0.0, 0.035)], "oven", C=(ox, 0, oz), seg=16,
          rfun=lambda th, i, k: 1.0 + 0.04 * (nz(i, k) - 0.5))
    lathe(m, [(0.0, 0.0), (0.0095, 0.0), (0.0, 0.0012)], "windowDark", C=(ox + 0.003, 0.0105, oz + 0.0295),
          A=(0.1, 0.0, 1.0), U=(1, 0, 0), V=(0, 1, 0), seg=10, sv=0.85)
    for i, (dx, dh, dz, a) in enumerate(((0.0, 0.003, 0.0, 0.1), (0.0, 0.003, 0.007, -0.05), (0.0, 0.003, 0.014, 0.08),
                                         (0.0, 0.0085, 0.0035, 0.0), (0.0, 0.0085, 0.0105, 0.12))):
        cx, cz = -0.506 + dx, -0.322 + dz
        tube(m, [(cx - 0.026, dh, cz - 0.026 * a), (cx + 0.026, dh + 0.0005, cz + 0.026 * a)], 0.0031, "wood",
             seg=6)
    kids["oven"] = make_obj("oven", m, house, origin=(ox, 0.0, oz))
    return house, kids


# ============================================================================================ threshing floor
def build_threshing(root):
    """round threshing floor: flagstone paving, a rim of boulders, the grain heap with straw round its foot, a
    winnowing fork leaning on it, two sacks, straw bundles, and an oil lamp on a stone (`lampFlame` at the spout)"""
    cx, cz = THR_C
    mb = MB()
    rings = [(0.0, 0.034, 1), (0.034, 0.074, 7), (0.074, THR_R, 11)]
    for ri, (r0, r1, n) in enumerate(rings):
        for k in range(n):
            ph = 0.35 * ri
            a0 = TAU * k / n + ph; a1 = TAU * (k + 1) / n + ph
            gap = 0.0016
            h = 0.0034 + 0.0009 * nz(ri, k)
            if n == 1:
                poly = [(cx + (r1 - gap) * math.cos(TAU * j / 12), cz + (r1 - gap) * math.sin(TAU * j / 12))
                        for j in range(12)]
            else:
                da0 = gap / max(r0, 0.02); da1 = gap / r1
                arc1 = [(cx + (r1 - gap) * math.cos(a), cz + (r1 - gap) * math.sin(a))
                        for a in np.linspace(a0 + da1, a1 - da1, 4)]
                arc0 = [(cx + (r0 + gap) * math.cos(a), cz + (r0 + gap) * math.sin(a))
                        for a in np.linspace(a1 - da0, a0 + da0, 3)]
                poly = arc1 + arc0
            ngon_top(mb, poly, h, "threshFloor", hb=0.0012)
    for k in range(27):
        a = TAU * k / 27 + 0.05 * nz(k)
        r = 0.0115 + 0.003 * nz(k, 2)
        lumpy(mb, (cx + (THR_R + 0.010) * math.cos(a), r * 0.55, cz + (THR_R + 0.010) * math.sin(a)), r, "rimStone",
              seg=7, rings=4, sh=0.75, sx=1.25, amp=0.14, seed=k + 40, smooth=False)
    hx, hz = cx + 0.006, cz - 0.010
    poly = [(hx + (0.073 + 0.010 * nz(k, 9)) * math.cos(TAU * k / 22), hz + (0.068 + 0.010 * nz(k, 8)) *
             math.sin(TAU * k / 22)) for k in range(22)]
    ngon_top(mb, poly, 0.0055, "straw", hb=0.003)
    heap = MB()
    lathe(heap, [(0.0, 0.004), (0.064, 0.004), (0.059, 0.013), (0.049, 0.034), (0.035, 0.056), (0.020, 0.073),
               (0.008, 0.083), (0.0, 0.086)], "grain", C=(hx, 0, hz), seg=22,
          rfun=lambda th, i, k: 1.0 + (0.07 * (nz(i, k, 5) - 0.5) * 2 if 0 < i < 7 else 0.0))
    # winnowing fork: tines on the floor, handle resting on the heap
    fk = MB()
    H0, H1 = Vector((0.245, 0.022, -0.385)), Vector((0.327, 0.107, -0.459))
    d = (H1 - H0).normalized(); perp = d.cross(Vector((0, 1, 0))).normalized()
    tube(fk, [tuple(H0 - d * 0.004), tuple(H0 + (H1 - H0) * 0.5 + Vector((0, 0.0012, 0))), tuple(H1)], 0.0042,
         "wood", seg=6)
    tube(fk, [tuple(H0 + perp * 0.016), tuple(H0 - perp * 0.016)], 0.0030, "wood", seg=5)
    for o in np.linspace(-0.013, 0.013, 5):
        a = H0 + perp * o
        b = H0 + perp * o * 1.25 - d * 0.033 + Vector((0, 0.002, 0))
        tube(fk, [tuple(a), tuple((a + b) / 2 - Vector((0, 0.0015, 0))), tuple(b)], [0.0022, 0.0019, 0.0014], "wood",
             seg=4)
    # sacks and straw bundles
    for i, (sx, sz, s) in enumerate(((0.446, -0.364, 1.0), (0.463, -0.405, 0.88), (0.452, -0.445, 0.8))):
        lathe(mb, [(0.0, 0.0), (0.017 * s, 0.0), (0.022 * s, 0.011 * s), (0.021 * s, 0.028 * s), (0.013 * s, 0.040 * s),
                   (0.0062 * s, 0.045 * s), (0.0058 * s, 0.049 * s), (0.0095 * s, 0.053 * s), (0.0, 0.054 * s)], "sack",
              C=(sx, 0, sz), seg=14, rfun=lambda th, ii, k, i=i: 1.0 + 0.06 * (nz(ii, k, i) - 0.5) * 2)
        tube(mb, [(sx + 0.0068 * s * math.cos(TAU * k / 10), 0.0465 * s, sz + 0.0068 * s * math.sin(TAU * k / 10))
                  for k in range(10)], 0.0016, "sack", seg=4, closed=True, ref=(0, 1, 0))
    for (bx, bz, a) in ((0.205, -0.515, 0.5), (0.232, -0.536, 0.3)):
        dd = (math.cos(a) * 0.028, math.sin(a) * 0.028)
        tube(mb, [(bx - dd[0], 0.008, bz - dd[1]), (bx, 0.0085, bz), (bx + dd[0], 0.008, bz + dd[1])],
             [0.0075, 0.0068, 0.0078], "straw", seg=8)
        tube(mb, [(bx + 0.0071 * math.cos(TAU * k / 10) * math.sin(a), 0.008 + 0.0071 * math.sin(TAU * k / 10),
                   bz - 0.0071 * math.cos(TAU * k / 10) * math.cos(a)) for k in range(10)], 0.0012, "straw", seg=4,
             closed=True)
    # lamp stone and clay oil lamp
    lx, lz = 0.203, -0.340
    lp = MB()
    box(lp, lx - 0.015, lx + 0.015, 0.0, 0.021, lz - 0.012, lz + 0.012, "rimStone", skip=("bottom",))
    lathe(lp, [(0.0, 0.021), (0.0075, 0.021), (0.0098, 0.0235), (0.0096, 0.0262), (0.0062, 0.0285),
               (0.0040, 0.0288), (0.0036, 0.0275), (0.0, 0.0272)], "lamp", C=(lx, 0, lz), seg=14, sx=1.25)
    tube(lp, [(lx + 0.009, 0.0255, lz), (lx + 0.0165, 0.0268, lz)], [0.0034, 0.0024], "lamp", seg=6)
    tube(lp, [(lx - 0.010, 0.0255, lz), (lx - 0.0145, 0.0285, lz), (lx - 0.0115, 0.031, lz)], 0.0013, "lamp", seg=4)
    flame = (lx + 0.0175, 0.0295, lz)
    ob = make_obj("threshing", mb, root, origin=(cx, 0.0, cz), smooth_angle=50)
    parts = {"grainHeap": make_obj("grainHeap", heap, ob, origin=(hx, 0.0, hz), smooth_angle=50),
             "fork": make_obj("fork", fk, ob, origin=tuple(H0), smooth_angle=50),
             "lamp": make_obj("lamp", lp, ob, origin=(lx, 0.021, lz), smooth_angle=50)}
    empty("lampFlame", flame, parts["lamp"])
    return ob, parts, flame


# ============================================================================================ barley
def barley_ear(mb, top, ed, L, side, reg="barley", n_k=3, r_k=0.0041, awn=0.014, seed=0):
    """a bearded two-row barley ear hanging from `top` along `ed`: n_k kernel bulges that alternate left / right of
    the axis (waists between them), a beard of long awns pointing on along the ear"""
    down = Vector((0, -1, 0))
    nr = 2 * n_k + 1
    pts, rad = [], []
    for i in range(nr + 1):
        t = i / nr
        q = top + ed * L * t + down * 0.0035 * t * t
        env = math.sin(math.pi * (0.10 + 0.86 * t)) ** 0.6
        if i == 0:
            r = 0.0014
        elif i == nr:
            r = 0.0007
        elif i % 2 == 1:                                # a kernel, pushed to its row
            r = r_k * env
            q = q + side * (0.0016 if (i // 2) % 2 == 0 else -0.0016)
        else:
            r = r_k * env * 0.42
        pts.append(tuple(q)); rad.append(r)
    tube(mb, pts, rad, reg, seg=3, smooth=True)
    up = side.cross(ed).normalized()
    for j, t in enumerate((0.55, 0.97)):
        q = Vector(pts[int(round(t * nr))])
        sp = side * (0.0022 if j % 2 else -0.0022)
        tip = q + ed * awn + sp * 1.4 + up * 0.0028
        blade(mb, [tuple(q + sp * 0.3), tuple(tip)], [0.0012, 0.0], reg, nrm=tuple(up))


def clump_template():
    """one barley clump (local, base at the origin): five stalks of different heights fanning left and right in the
    front view, each with a nodding bearded ear of kernels, and one leaf"""
    mb = MB()
    rng = random.Random(21)
    for k, a0 in enumerate((math.pi, 0.0, 0.78 * math.pi, 0.22 * math.pi, 0.5 * math.pi)):
        a = a0 + rng.uniform(-0.15, 0.15)
        d = Vector((math.cos(a), 0.0, math.sin(a)))
        Hs = (0.060, 0.074, 0.066, 0.081, 0.070)[k] + rng.uniform(-0.003, 0.003)
        lean = rng.uniform(0.004, 0.009)
        base = d * 0.0032
        pts = [base + d * lean * (u ** 1.6) + Vector((0, Hs * u, 0)) for u in (0.0, 0.6, 1.0)]
        tube(mb, [tuple(p) for p in pts], [0.0018, 0.0015, 0.0013], "barley", seg=3, smooth=True, caps=False)
        top = pts[-1]
        ed = (d * 0.60 + Vector((0, -0.58, 0))).normalized()
        side = ed.cross(Vector((0, 1, 0))).normalized()
        barley_ear(mb, top, ed, rng.uniform(0.019, 0.022), side, seed=k)
    a = 0.9
    d = Vector((math.cos(a), 0.0, math.sin(a)))
    pts = [tuple(d * (0.004 + 0.024 * u) + Vector((0, 0.010 + 0.036 * u - 0.032 * u * u, 0))) for u in
           (0.0, 0.5, 1.0)]
    blade(mb, pts, [0.0105, 0.0080, 0.0], "barleyLeaf", nrm=tuple(d))
    return mb


def build_field(root):
    """barley clumps on a jittered grid (the strips along the actors' marks and paths and the wall stay clear), skinned to a 6 x 2 grid of sway bones; armature `field` (action fieldSway) -> mesh `barley`"""
    tpl = clump_template()
    rng = random.Random(8)
    cx, cz = (FIELD[0] + FIELD[1]) / 2, (FIELD[2] + FIELD[3]) / 2
    NBX, NBZ = 6, 2
    bones = {}
    for i in range(NBX):
        for j in range(NBZ):
            bones[(i, j)] = (FIELD[0] + (i + 0.5) * (FIELD[1] - FIELD[0]) / NBX,
                             FIELD[2] + (j + 0.5) * (FIELD[3] - FIELD[2]) / NBZ)
    clumps, cut = [], []
    zs = np.arange(FIELD[2] + 0.010, FIELD[3] - 0.004, 0.0215)
    for r, z0 in enumerate(zs):
        for x0 in np.arange(FIELD[0] + 0.014 + (r % 2) * 0.0115, FIELD[1] - 0.004, 0.0215):
            x = x0 + rng.uniform(-0.0045, 0.0045); z = z0 + rng.uniform(-0.0045, 0.0045)
            reach = 0.040
            if (x < WALL_X + 0.020 or clear_dist(x, z) < 0.05 + reach or clear_dist(x, z, True) < 0.05 + reach
                    or any(math.hypot(x - a, z - b) < 0.05 for a, b in SHEAF_SPOTS)):
                cut.append((x, z))
                continue
            clumps.append((x, z))
    mb = MB()
    for n, (x, z) in enumerate(clumps):
        bi = min(bones, key=lambda k: (bones[k][0] - x) ** 2 + (bones[k][1] - z) ** 2)
        bn = "sway_%d_%d" % bi
        s = rng.uniform(0.86, 1.04)
        f = yaw_fn(x, z, rng.uniform(0, TAU), s, lean=(rng.uniform(-0.07, 0.07), rng.uniform(-0.07, 0.07)),
                   sy=rng.uniform(0.84, 1.06) * (1.04 if nz(x * 7, z * 7) > 0.6 else 1.0))

        def wt(lv, wv, bn=bn):
            w = min(1.0, max(0.0, lv[1] / 0.075)) ** 1.5
            return {"field_root": 1.0 - w, bn: w}
        mb.add(tpl, f, weight=wt)
    arm = bpy.data.armatures.new("field_arm")
    rig = link(bpy.data.objects.new("field", arm))
    rig.location = B(cx, 0.0, cz)
    parent_keep(rig, root)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    O = B(cx, 0, cz)
    r0 = arm.edit_bones.new("field_root"); r0.head = B(cx, 0, cz) - O; r0.tail = B(cx, 0.03, cz) - O
    for (i, j), (bx, bz) in bones.items():
        b = arm.edit_bones.new("sway_%d_%d" % (i, j)); b.head = B(bx, 0, bz) - O; b.tail = B(bx, 0.06, bz) - O
        b.parent = r0
    for b in arm.edit_bones:
        b.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')
    ob = make_obj("barley", mb, None, origin=(cx, 0.0, cz), smooth_angle=70)
    parent_keep(ob, rig)
    mod = ob.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
    # fieldSway: 4 s loop at 24 fps (frame 1 == frame 97); a gust runs across the field left to right, with a small
    # in-and-out nod; every term is a whole number of cycles per loop, so the loop is seamless
    bpy.context.scene.render.fps = 24
    rig.animation_data_create()
    zax, xax = Vector((0, 1, 0)), Vector((1, 0, 0))          # Blender Y = design -z (sideways sway), X (nod)
    for (i, j) in bones:
        pb = rig.pose.bones["sway_%d_%d" % (i, j)]; pb.rotation_mode = 'QUATERNION'
        inv = rig.data.bones[pb.name].matrix_local.to_3x3().inverted()
        ph = 0.9 * i + 0.5 * j
        for f in range(1, 98, 4):
            u = TAU * (f - 1) / 96
            side = 4.2 * math.sin(u - ph) + 1.6 * math.sin(2 * u - 1.7 * ph + 0.5)
            nod = 1.8 * math.sin(u - ph + 1.2) + 0.7 * math.sin(3 * u - ph)
            q = Quaternion((inv @ zax).normalized(), math.radians(side)) @ \
                Quaternion((inv @ xax).normalized(), math.radians(nod))
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
    act = rig.animation_data.action
    act.name = "fieldSway"
    return rig, ob, tpl, clumps, cut


# ============================================================================================ stubble, sheaves, dropped
def sheaf_template():
    """a standing sheaf: a bundle of stalks (ridged, waisted at the tie), a twisted straw band, a crown of
    drooping ears with beards"""
    mb = MB()
    prof = [(0.0, 0.0), (0.0150, 0.0), (0.0140, 0.012), (0.0112, 0.026), (0.0098, 0.034), (0.0110, 0.044),
            (0.0145, 0.056), (0.0165, 0.062), (0.0, 0.063)]
    lathe(mb, prof, "sheaf", seg=18, smooth=False, rfun=lambda th, i, k: 1.0 + (0.08 if k % 2 else 0.0))
    lathe(mb, [(0.0118, 0.030), (0.0122, 0.0333), (0.0118, 0.0365)], "sheafTie", seg=18, smooth=True)
    tube(mb, [(0.0105 * math.cos(TAU * k / 14), 0.0333 + 0.0018 * math.sin(3 * TAU * k / 14),
               0.0105 * math.sin(TAU * k / 14)) for k in range(14)], 0.0024, "sheafTie", seg=5, closed=True)
    rng = random.Random(4)
    for k in range(9):
        a = TAU * k / 9 + rng.uniform(-0.15, 0.15)
        d = Vector((math.cos(a), 0, math.sin(a)))
        top = d * 0.011 + Vector((0, 0.063 + rng.uniform(0.0, 0.006), 0))
        ed = (d * 0.72 + Vector((0, 0.10, 0))).normalized()
        pts = [top + ed * 0.016 * s + Vector((0, -0.006 * s * s, 0)) for s in np.linspace(0, 1, 5)]
        tube(mb, [tuple(p) for p in pts], [0.0022, 0.0040, 0.0042, 0.0032, 0.0012], "sheaf", seg=4)
        side = ed.cross(Vector((0, 1, 0))).normalized()
        for j, s in enumerate((0.5, 0.9)):
            p = top + ed * 0.016 * s
            tip = p + ed * 0.010 + side * (0.003 if j else -0.003) + Vector((0, 0.004, 0))
            blade(mb, [tuple(p), tuple(tip)], [0.0016, 0.0], "sheaf", nrm=tuple(side.cross(ed)))
    return mb


def build_stubble(root, cut):
    """cut stalk stubs over the stubble band and the cleared strips of the field (each samples the ground drawing's
    stubble), a few loose straws; child `sheaves` (three standing sheaves, one shared drawing)"""
    rng = random.Random(9)
    mb = MB()
    mb.nr = True
    pts = []
    for z in np.arange(FIELD[2] + 0.005, STUBBLE[3] - 0.004, 0.0105):
        for x in np.arange(STUBBLE[0] + 0.004, STUBBLE[1] - 0.003, 0.0105):
            px, pz = x + rng.uniform(-0.0035, 0.0035), z + rng.uniform(-0.0035, 0.0035)
            if pz > FIELD[3]:
                ok = True
            else:
                ok = px > WALL_X + 0.016 and any(math.hypot(px - a, pz - b) < 0.020 for a, b in cut)
            if ok and all(math.hypot(px - a, pz - b) > 0.019 for a, b in SHEAF_SPOTS):
                pts.append((px, pz))
    for i, (x, z) in enumerate(pts):
        hh = rng.uniform(0.0055, 0.0105); r = 0.0017
        a0 = rng.uniform(0, TAU); lx, lz = rng.uniform(-0.002, 0.002), rng.uniform(-0.002, 0.002)
        ring0 = [mb.v(x + r * math.cos(a0 + TAU * k / 3), 0.0, z + r * math.sin(a0 + TAU * k / 3)) for k in range(3)]
        ring1 = [mb.v(x + lx + r * 0.8 * math.cos(a0 + TAU * k / 3), hh, z + lz + r * 0.8 * math.sin(a0 + TAU * k / 3))
                 for k in range(3)]
        for k in range(3):
            k1 = (k + 1) % 3
            am = a0 + TAU * (k + 0.5) / 3
            mb.fo([ring0[k], ring0[k1], ring1[k1], ring1[k]], "stubble", (math.cos(am), 0, math.sin(am)))
    for i in range(26):                                        # loose straws lying about
        x, z = rng.uniform(STUBBLE[0] + 0.01, STUBBLE[1] - 0.01), rng.uniform(0.004, STUBBLE[3] - 0.004)
        a = rng.uniform(0, TAU); L = rng.uniform(0.012, 0.022)
        tube(mb, [(x, 0.0015, z), (x + L * math.cos(a), 0.0015, z + L * math.sin(a))], 0.0011, "stubble", seg=3,
             caps=False)
    mb.nr = False
    ob = make_obj("stubble", mb, root, origin=(0.32, 0.0, 0.04), smooth_angle=80, merge=False)
    tpl = sheaf_template()
    m = MB()
    for i, (x, z) in enumerate(SHEAF_SPOTS):
        m.add(tpl, yaw_fn(x, z, 0.7 * i + 0.3, (1.0, 0.92, 1.05)[i], lean=((0.05, -0.04, 0.03)[i], 0.0)))
    sh = make_obj("sheaves", m, ob, origin=(SHEAF_SPOTS[-1][0], 0.0, SHEAF_SPOTS[-1][1]), smooth_angle=60)
    return ob, sh, tpl, len(pts)


def build_dropped(root):
    """`dropped`: barley stalks lying on the stubble round (0.24, 0.10), where Boaz let them fall (hidden at start);
    they sample the barley drawing's colour"""
    rng = random.Random(17)
    mb = MB()
    mb.nr = True
    for i in range(9):
        x, z = 0.24 + rng.uniform(-0.035, 0.035), 0.10 + rng.uniform(-0.022, 0.022)
        if math.hypot(x - 0.24, z - 0.12) < 0.012:
            z -= 0.016
        a = rng.uniform(0, TAU); L = rng.uniform(0.040, 0.058)
        d = Vector((math.cos(a), 0, math.sin(a)))
        p0 = Vector((x, 0.0017, z)); p1 = p0 + d * L
        tube(mb, [tuple(p0), tuple((p0 + p1) / 2 + Vector((0, 0.0006, 0))), tuple(p1)], 0.0014, "barley", seg=3)
        ear = [p1 + d * 0.019 * s + Vector((0, 0.0015 + 0.0015 * math.sin(math.pi * s), 0)) for s in
               np.linspace(0, 1, 5)]
        tube(mb, [tuple(p) for p in ear], [0.0016, 0.0034, 0.0037, 0.0028, 0.001], "barley", seg=4)
        side = d.cross(Vector((0, 1, 0)))
        for j, s in enumerate((0.4, 0.75, 1.0)):
            p = p1 + d * 0.019 * s + Vector((0, 0.003, 0))
            blade(mb, [tuple(p), tuple(p + d * 0.014 + side * (0.004 if j % 2 else -0.004))], [0.0014, 0.0], "barley",
                  nrm=(0, 1, 0))
    mb.nr = False
    return make_obj("dropped", mb, root, origin=(0.24, 0.0, 0.10), smooth_angle=70)


# ============================================================================================ field wall
def build_field_wall(root):
    """low dry-stone wall along x 0.186 on the field's left side: two faces of irregular stones in three courses
    with capstones, ending in a tumble of fallen stones (keeps Boaz's night walk clear)"""
    rng = random.Random(2)
    mb = MB()
    z_front, z_end = -0.020, -0.220
    kept = []
    courses = [(0.0, 0.0115, 0.0105), (0.0105, 0.0215, 0.0095), (0.0205, 0.030, 0.0088)]
    for ci, (h0, h1, r) in enumerate(courses):
        z = z_front - (0.006 if ci % 2 else 0.0)
        while z > z_end + 0.008:
            L = rng.uniform(0.016, 0.024)
            zc = z - L / 2
            if zc - L / 2 < z_end:
                break
            for sx in ((-0.0065, 0.0065) if ci < 2 else (0.0,)):
                ext = max((h1 - h0) * 0.62 * (0.95 if ci < 2 else 1.55), L / 2) + 0.002
                if h1 > 0.012 and clear_dist(WALL_X + sx, zc) < 0.05 + ext:
                    continue                                # this stone fell: the wall is lower toward the path
                kept.append(zc)
                lumpy(mb, (WALL_X + sx + rng.uniform(-0.001, 0.001), (h0 + h1) / 2, zc), (h1 - h0) * 0.62,
                      "wallStone", seg=7, rings=4, sh=1.0, sx=(0.95 if ci < 2 else 1.55), sz=L / (h1 - h0) / 1.15,
                      amp=0.16, seed=ci * 31 + z * 900 + sx * 77, smooth=False)
            z -= L
    for i in range(5):                                  # fallen stones lying at the foot of the low end
        zc = z_end + 0.010 + i * 0.019 + rng.uniform(-0.005, 0.005)
        xc = WALL_X + rng.uniform(0.004, 0.018)
        r = rng.uniform(0.0055, 0.0075)
        lumpy(mb, (xc, r * 0.5, zc), r, "wallStone", seg=7, rings=4, sh=0.62, sx=1.3, amp=0.18, seed=i + 300,
              smooth=False)
    ob = make_obj("fieldWall", mb, root, origin=(WALL_X, 0.0, (z_front + z_end) / 2), smooth_angle=55)
    z_end = min(kept) if kept else z_end
    return ob, (z_end, z_front)


# ============================================================================================ olive tree, jars
def build_olive(root):
    """gnarled olive: three twisted strands with knots, flaring roots, four branches into a crown of lumpy
    silver-green blobs (crown bottom >= 0.17 so the actors pass under its edge)"""
    ox, oz = OLIVE
    mb = MB()
    def axis(u):                                       # the trunk's crooked spine: leans, kinks, leans back
        return (ox - 0.034 * u ** 1.2 + 0.010 * math.sin(math.pi * u), 0.180 * u - 0.002,
                oz - 0.004 * u + 0.011 * math.sin(2.3 * math.pi * u))
    for s in range(3):
        pts, rad = [], []
        for j in range(13):
            u = j / 12
            a = TAU * s / 3 + 3.4 * u + 0.5 * math.sin(5 * u + s)
            rr = 0.0118 * (1 - 0.5 * u) * (1.25 if u < 0.12 else 1.0) + 0.0025 * math.sin(7 * u + s)
            c = axis(u)
            pts.append((c[0] + rr * math.cos(a), c[1], c[2] + rr * math.sin(a)))
            rad.append(0.0098 * (1 - 0.38 * u) * (1 + 0.22 * math.sin(9 * u + 2 * s)) * (1.2 if u < 0.1 else 1.0))
        tube(mb, pts, rad, "oliveTrunk", seg=8, smooth=True)
    for k, (u, a, r) in enumerate(((0.22, 0.6, 0.0075), (0.47, 2.9, 0.0068), (0.66, 4.6, 0.0060), (0.35, 4.0, 0.0055))):
        c = axis(u)
        sphere(mb, (c[0] + 0.0125 * math.cos(a), c[1], c[2] + 0.0125 * math.sin(a)), r, "oliveTrunk", seg=8, rings=5)
    for k in range(5):                                 # roots
        a = TAU * k / 5 + 0.3
        d = (math.cos(a), math.sin(a))
        tube(mb, [(ox + d[0] * 0.006, 0.014, oz + d[1] * 0.006), (ox + d[0] * 0.020, 0.005, oz + d[1] * 0.020),
                  (ox + d[0] * 0.034, -0.002, oz + d[1] * 0.034)], [0.0068, 0.0050, 0.0026], "oliveTrunk", seg=6)
    top = Vector(axis(0.98))
    crown_c = Vector((ox - 0.036, 0.258, oz + 0.004))
    blobs = [((0.000, 0.022, 0.000), 0.058), ((-0.052, 0.000, 0.012), 0.045), ((0.040, -0.004, 0.000), 0.044),
             ((0.010, -0.006, 0.050), 0.044), ((-0.020, 0.004, -0.050), 0.046), ((0.036, 0.030, -0.030), 0.040),
             ((-0.040, 0.032, -0.010), 0.038), ((0.040, 0.010, 0.036), 0.036), ((-0.036, -0.004, 0.042), 0.036)]
    for i, (off, r) in enumerate(blobs):
        c = crown_c + Vector(off) * 0.86; r *= 0.93
        end = c - Vector((0, r * 0.55, 0))
        if i in (1, 2, 3, 4):
            mid = top + (end - top) * 0.5 + Vector((0, 0.012, 0))
            tube(mb, [tuple(top), tuple(mid), tuple(end)], [0.0062, 0.0046, 0.0030], "oliveTrunk", seg=6)
        sh = 0.74
        lo = c.y - r * sh
        assert lo >= 0.17 - 1e-6, (i, lo)
        lumpy(mb, tuple(c), r, "oliveCrown", seg=14, rings=8, sh=sh, amp=0.10, seed=i * 7 + 1)
    return make_obj("olive", mb, root, origin=(ox, 0.0, oz), smooth_angle=60)


def build_water_jars(root):
    """three water jars (with handles) and a small cup in the olive's shade; moved to the trunk's side of the
    olive so Naomi's walk from the road to the door stays clear"""
    mb = MB()
    for (x, z, H, a) in WATER:
        s = H / 0.060
        prof = [(0.0, 0.0), (0.0075, 0.0), (0.0135, 0.008), (0.0175, 0.022), (0.0170, 0.034), (0.0120, 0.045),
                (0.0062, 0.051), (0.0058, 0.055), (0.0088, 0.060), (0.0060, 0.0605), (0.0, 0.052)]
        lathe(mb, [(r * s, h * s) for r, h in prof], "waterJar", C=(x, 0, z), seg=14)
        for sg in (-1, 1):
            c, sn = math.cos(a), math.sin(a)
            dx, dz = sg * c, sg * sn
            tube(mb, [(x + dx * 0.0062 * s, 0.053 * s, z + dz * 0.0062 * s), (x + dx * 0.0150 * s, 0.052 * s,
                       z + dz * 0.0150 * s), (x + dx * 0.0160 * s, 0.038 * s, z + dz * 0.0160 * s)], 0.0018 * s,
                 "waterJar", seg=5)
    lathe(mb, [(0.0, 0.0), (0.004, 0.0), (0.0068, 0.008), (0.0058, 0.0085), (0.0, 0.003)], "waterJar",
          C=(-0.447, 0, 0.008), seg=12)
    cx = sum(w[0] for w in WATER) / 3; cz = sum(w[1] for w in WATER) / 3
    return make_obj("waterJars", mb, root, origin=(cx, 0.0, cz))


# ============================================================================================ canopy
def flower(mb, c, r, reg, facing=(0, 0, 1)):
    f = Vector(facing).normalized()
    u = f.cross(Vector((0, 1, 0)))
    if u.length < 1e-3:
        u = Vector((1, 0, 0))
    u.normalize(); v = f.cross(u)
    lathe(mb, [(0.0, -0.25 * r), (r * 0.85, -0.15 * r), (r, 0.05 * r), (r * 0.6, 0.30 * r), (0.0, 0.42 * r)], reg,
          C=c, A=tuple(f), U=tuple(u), V=tuple(v), seg=10, smooth=True,
          rfun=lambda th, i, k: 1.0 + (0.30 * math.cos(5 * th) if 0 < i < 4 else 0.0))


def build_canopy(root):
    """wedding arch centre front: two turned poles at x +-0.14 wound with garlands and flowers, a white cloth top
    sagging between them with scalloped valances, a flower swag along the front (hidden until S10)"""
    mb = MB()
    X, T = CANOPY_X, CANOPY_TOP
    for s in (-1, 1):
        lathe(mb, [(0.0, 0.0), (0.0125, 0.0), (0.0125, 0.010), (0.0092, 0.015), (0.0085, 0.20), (0.0080, T - 0.01),
                   (0.0100, T - 0.004), (0.0100, T + 0.003), (0.0, T + 0.004)], "canopyPole", C=(s * X, 0, 0.0),
              seg=10)
        sphere(mb, (s * X, T + 0.011, 0.0), 0.0078, "canopyPole", seg=10, rings=6)
        hel = [(s * X + 0.0105 * math.cos(TAU * 3.2 * u + s), 0.06 + (T - 0.08) * u,
                0.0105 * math.sin(TAU * 3.2 * u + s)) for u in np.linspace(0, 1, 40)]
        outer = [q for q in hel if (q[0] - s * X) * s > 0.004]       # flowers only on the outer side (walk side clear)
        for k, q in enumerate(outer[1::3]):                         # leafy puffs wound up the pole
            lumpy(mb, (q[0], q[1], q[2]), 0.0078, "garland", seg=7, rings=4, sh=0.8, amp=0.25, seed=k + 900 + s)
        for k, u in enumerate(np.linspace(0.06, 0.96, 6)):
            p = Vector(outer[int(u * (len(outer) - 1))])
            out = (p - Vector((s * X, p.y, 0.0))).normalized() + Vector((0, 0, 0.9))
            flower(mb, tuple(p + out.normalized() * 0.006), 0.0135, "flowerPink" if k % 2 == 0 else "flowerYellow",
                   facing=tuple(out))
    # cloth: two layers, catenary sag, scalloped valances front and back
    NXc, NZc = 22, 6
    W, Dp = X + 0.016, 0.040
    sag = lambda x: T + 0.006 - 0.014 * (1 - (x / W) ** 2)
    for lay, dh in ((0, 0.0), (1, -0.0018)):
        g = [[mb.v(-W + 2 * W * i / NXc, sag(-W + 2 * W * i / NXc) + dh + 0.002 * math.sin(math.pi * j / NZc),
                   -Dp + 2 * Dp * j / NZc) for j in range(NZc + 1)] for i in range(NXc + 1)]
        for i in range(NXc):
            for j in range(NZc):
                mb.fo([g[i][j], g[i + 1][j], g[i + 1][j + 1], g[i][j + 1]], "canopyCloth", (0, 1 if lay == 0 else -1, 0),
                      True)
    for zs, sgn in ((Dp, 1), (-Dp, -1)):
        for lay, dz in ((0, 0.0), (1, -0.0012 * sgn)):
            top = [mb.v(-W + 2 * W * i / NXc, sag(-W + 2 * W * i / NXc), zs + dz) for i in range(NXc + 1)]
            bot = [mb.v(-W + 2 * W * i / NXc, sag(-W + 2 * W * i / NXc) - 0.015 - 0.007 *
                        abs(math.sin(math.pi * i / 2.0 + 0.0)), zs + dz + sgn * 0.002) for i in range(NXc + 1)]
            for i in range(NXc):
                mb.fo([top[i], top[i + 1], bot[i + 1], bot[i]], "canopyCloth", (0, 0, sgn if lay == 0 else -sgn), True)
    # swag along the front with flowers and leaves
    sw = [(x, sag(x) - 0.006 - 0.014 * (1 - (x / X) ** 2), Dp + 0.006) for x in np.linspace(-X, X, 19)]
    for k, q in enumerate(sw):                                      # the swag: a rope of leafy puffs
        lumpy(mb, q, 0.0085, "garland", seg=7, rings=4, sh=0.85, amp=0.25, seed=k + 950)
    for k, i in enumerate(range(1, 19, 3)):
        p = Vector(sw[i]) + Vector((0, 0, 0.004))
        flower(mb, tuple(p + Vector((0, 0, 0.005))), 0.0140, "flowerYellow" if k % 2 == 0 else "flowerPink")
        for sg in (-1, 1):
            blade(mb, [tuple(p + Vector((sg * 0.006, -0.002, 0.002))), tuple(p + Vector((sg * 0.016, -0.007, 0.004))),
                       tuple(p + Vector((sg * 0.022, -0.004, 0.003)))], [0.005, 0.0045, 0.0], "garland",
                  nrm=(0, 0, 1))
    return make_obj("canopy", mb, root, origin=(0.0, 0.0, 0.0), smooth_angle=55)


# ============================================================================================ drawings / UV
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


def _chars():
    """the figures' sheet places and printed bboxes: pipeline/ru_characters.py output where it exists (authoritative),
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
    return {"naomi": {"sheetX": -0.33, "sheetY": 0.015, "height": 0.32, "box": [-0.455, 0.015, -0.205, 0.335]},
            "ruth": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.33, "box": [-0.115, 0.015, 0.115, 0.345]},
            "boaz": {"sheetX": 0.33, "sheetY": 0.015, "height": 0.38, "box": [0.19, 0.015, 0.47, 0.395]}}


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
# kind, scale, centre-x and bottom of the bbox on the sheet (sheet coords: x -0.5..0.5, ys 0 = art rect bottom)
DRAWINGS = {
    "hills":     dict(P_FRONT(), scale=1.75, cx=0.0, y0=1.050, members=["hills"]),
    "sheaf":     dict(P_FRONT(), scale=0.62, cx=-0.425, y0=1.062, members=[]),
    "barley":    dict(P_FRONT(), scale=0.60, cx=0.420, y0=1.040, members=[], creases=False),
    "house":     dict(P_OBL(0.30, 0.42), scale=1.22, cx=-0.279, y0=0.755, decorOnly=["houseStone"],
                      members=["house", "door", "window", "ladder", "houseJars", "basket", "oven"]),
    "threshing": dict(P_OBL(0.0, 0.55), scale=1.05, cx=0.093, y0=0.830,
                      members=["threshing", "grainHeap", "fork", "lamp"]),
    "olive":     dict(P_FRONT(), scale=1.30, cx=0.322, y0=0.760, members=["olive"]),
    "ground":    dict(P_PLAN(), scale=2.80, cx=-0.268, y0=0.430, members=["ground", "road"]),
    "canopy":    dict(P_OBL(0.0, 0.5), scale=1.35, cx=0.083, y0=0.430, members=["canopy"], creases=False),
    "waterJars": dict(P_FRONT(), scale=0.62, cx=0.330, y0=0.505, members=["waterJars"]),
    "fieldWall": dict(P_SIDE(0.6), scale=0.85, cx=0.350, y0=0.430, members=["fieldWall"]),
}
TEMPLATES = {"barley": ("barley",), "sheaf": ("sheaves",)}       # drawing -> instanced objects
CONSTS = {"ground": {"grass": ("ground", "grass"), "stone": ("fieldWall", "wallStone"), "bush": ("hills", "bush")},
          "stubble": {"stubble": ("ground", "stubble")},
          "dropped": {"barley": ("barley", "barley")}}


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
        m = (idb == rid) & ~crease
        ys, xs = np.nonzero(m)
        if not len(ys):
            continue
        y0, y1, x0, x1 = ys.min(), ys.max() + 1, xs.min(), xs.max() + 1
        cur = m[y0:y1, x0:x1].copy()
        while True:
            nxt = cur.copy()
            for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
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
    """faces nearly edge-on to their drawing's view (|n . d| < 0.22, n from P) take a clean texel deep inside their
    own region; no-raster faces take their named texel (CONSTS)"""
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
                       "written by pipeline/ru_bethlehem.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
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


def clearance_points(objs, skip=()):
    pts, names = [], []
    for name, ob in objs.items():
        if ob.type != 'MESH' or name in skip:
            continue
        if name == "barley":                                   # skinned: test the swayed extremes too
            continue
        for x, h, z in world_verts(ob):
            pts.append((x, h, z)); names.append(name)
    return np.array(pts), names


def barley_extremes(rig, ob):
    """barley vertex positions at the sway extremes (frames 1, 25, 49, 73)"""
    out = []
    dg = bpy.context.evaluated_depsgraph_get()
    for f in (1, 13, 25, 37, 49, 61, 73, 85):
        bpy.context.scene.frame_set(f); dg.update()
        me = ob.evaluated_get(dg).to_mesh()
        out.append(np.array([D(ob.matrix_world @ v.co) for v in me.vertices]))
        ob.evaluated_get(dg).to_mesh_clear()
    bpy.context.scene.frame_set(1)
    return np.concatenate(out)


def check_clearance(objs, rig):
    """CONTRACT §6: no geometry above 0.012 within 0.05 of a mark, nothing on the straight paths between consecutive
    marks of one actor. Overhead parts (olive crown >= 0.17, canopy cloth) only need head room: above 0.40 they are
    ignored, between 0.17 and 0.40 they must stay 0.035 from the walk line (a head's radius)."""
    P, names = clearance_points(objs)
    bx = barley_extremes(rig, objs["barley"])
    P = np.concatenate([P, bx]); names = names + ["barley"] * len(bx)
    names = np.array(names)
    low = (P[:, 1] > 0.012) & (P[:, 1] < 0.17)
    over = (P[:, 1] >= 0.17) & (P[:, 1] < 0.40)
    hard, soft = {}, {}

    def test(label, dist_fn, out, hidden_ok=()):
        d = dist_fn(P[:, 0], P[:, 2])
        sel = (low & (d < 0.05)) | (over & (d < 0.035))
        sel &= ~np.isin(names, list(hidden_ok))
        if sel.any():
            out[label] = (round(float(P[sel, 1].max()), 4), sorted(set(names[sel].tolist())))
    for label, (x, z) in CONTRACT_MARKS.items():
        hid = ("canopy",) if not label.startswith("wed") else ()
        test("mark " + label, lambda X, Z, x=x, z=z: np.hypot(X - x, Z - z), hard, hid + ("dropped",))
    for label, a, b, is_hard in PATHS:
        def fn(X, Z, a=a, b=b):
            ax, az = a; bx_, bz = b
            dx, dz = bx_ - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
            t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
            return np.hypot(X - ax - t * dx, Z - az - t * dz)
        hid = ("dropped",) + (() if "0.06,0.08" in label or "-0.06,0.08" in label or "-0.22,0.12" in label
                              else ("canopy",))
        test(label, fn, hard if is_hard else soft, hid)
    # first moves of the play: from the printed places (sheetX, 0) to the first mark (reported only)
    try:
        tl = json.load(open(TIMELINE))
        first = {}
        for a in tl["acting"]:
            if "to" in a and a["who"] not in first:
                first[a["who"]] = tuple(a["to"])
        for c, p in first.items():
            if c in CHAR_PROPOSAL:
                s = (CHAR_PROPOSAL[c]["sheetX"], 0.0)

                def fn(X, Z, a=s, b=p):
                    ax, az = a; bx_, bz = b
                    dx, dz = bx_ - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
                    t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
                    return np.hypot(X - ax - t * dx, Z - az - t * dz)
                test("start %s %.2f,0>%.2f,%.2f" % (c, s[0], p[0], p[1]), fn, soft, ("canopy", "dropped"))
    except Exception as e:
        soft["timeline"] = str(e)
    return hard, soft


# ============================================================================================ build
def page_mat():
    m = bpy.data.materials.new("ru_page")
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.85
    return m


STATE = {}
ORDER = ["ground", "road", "hills", "house", "door", "window", "ladder", "houseJars", "basket", "oven", "threshing",
         "grainHeap", "fork", "lamp", "barley", "stubble", "sheaves", "dropped", "fieldWall", "olive", "waterJars", "canopy"]


def mode_build():
    global SHEAF_SPOTS
    SOFT_SEGS[:] = [(a, b) for _, a, b, hard in PATHS if not hard]
    try:
        first = {}
        for a in json.load(open(TIMELINE))["acting"]:
            if "to" in a and a["who"] not in first:
                first[a["who"]] = (float(a["to"][0]), float(a["to"][1]))
        for c, p in first.items():
            if c in CHAR_PROPOSAL:
                SOFT_SEGS.append(((CHAR_PROPOSAL[c]["sheetX"], 0.0), p))
    except Exception as e:
        print("TIMELINE_WARN", e)
    SHEAF_SPOTS = pick_sheaf_spots()
    print("SHEAVES", SHEAF_SPOTS)
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = link(bpy.data.objects.new("bethlehem", None))
    objs = {}
    objs["ground"], objs["road"], scatter = build_ground(root)
    objs["hills"] = build_hills(root)
    objs["house"], kids = build_house(root)
    objs.update(kids)
    objs["threshing"], parts, flame = build_threshing(root)
    objs.update(parts)
    rig, objs["barley"], clump_tpl, clumps, cut = build_field(root)
    objs["stubble"], objs["sheaves"], sheaf_tpl, nstubs = build_stubble(root, cut)
    objs["dropped"] = build_dropped(root)
    objs["fieldWall"], wall_span = build_field_wall(root)
    objs["olive"] = build_olive(root)
    objs["waterJars"] = build_water_jars(root)
    objs["canopy"] = build_canopy(root)
    bpy.context.view_layer.update()
    tmp = {"tpl_barley": make_obj("tpl_barley", clump_tpl, None, smooth_angle=70),
           "tpl_sheaf": make_obj("tpl_sheaf", sheaf_tpl, None, smooth_angle=60)}
    src = raster_sources(objs, tmp)
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("BETHLEHEM_TRIS", total, json.dumps(tris))
    print("SCATTER", json.dumps(dict(scatter, clumps=len(clumps), stubs=nstubs, wall=[round(w, 3) for w in wall_span])))
    assert total <= MAX_TRIS, "over budget %d" % total
    lay = check_layout()
    hard, soft = check_clearance(objs, rig)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_SOFT", json.dumps(soft))
    if MODE == "check":                                # clearance / layout / budget only: nothing is written
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
    hmax = {n: round(max(v[1] for v in world_verts(ob)), 4) for n, ob in objs.items()}
    write_design(objs, tris, total, flame, hmax, const, hard, soft, wall_span, len(clumps))
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root, rig=rig, flame=flame)
    print("BUILD_OK", GLB, total)


def write_design(objs, tris, total, flame, hmax, const, hard, soft, wall_span, nclumps):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    d.setdefault("version", 1)
    d.setdefault("artHeightUnits", ART_H)
    d.setdefault("lines", {"outerPx": 4.5, "detailPx": 3.0,
                           "note": "same weights as David & Goliath and Esther; faces come from decals (no face ink)"})
    d.setdefault("sheet", {
        "page": [1240, 1754], "dpi": 150, "art": [120, 283, 1000, 1227],
        "markers": [[62, 225], [1178, 225], [1178, 1568], [62, 1568]], "markerSize": 64,
        "title": {"hanzi": "忠心的路得", "pinyin": "zhōng xīn de lù dé", "english": "Faithful Ruth", "box": 76, "gap": 12,
                  "cy": 100, "label": "DoodLive · 涂上颜色，再用手机扫一扫"},
        "footer": {"rect": [210, 1604, 820, 110], "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上", "路得记 · Ruth"],
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
    d["set"] = {
        "generatedBy": "pipeline/ru_bethlehem.py", "doc": "docs/ruth/SET.md", "contract": "docs/ruth/CONTRACT.md §6",
        "root": "bethlehem",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {"lampFlame": [round(c, 4) for c in flame], "grainHeap": [THR_C[0] + 0.006, 0.0, THR_C[1] - 0.010],
                  "fork": [0.245, 0.022, -0.385], "lamp": [0.203, 0.021, -0.340],
                  "house": [-0.30, 0.0, -0.43], "door": [DOOR_X, 0.0, HOUSE[3] - 0.013], "threshing": [THR_C[0], 0.0, THR_C[1]],
                  "field": [round((FIELD[0] + FIELD[1]) / 2, 4), 0.0, round((FIELD[2] + FIELD[3]) / 2, 4)],
                  "olive": list(OLIVE[:1]) + [0.0] + list(OLIVE[1:]), "canopy": [0.0, 0.0, 0.0], "dropped": [0.24, 0.0, 0.10],
                  "waterJars": [round(sum(w[0] for w in WATER) / 3, 4), 0.0, round(sum(w[1] for w in WATER) / 3, 4)]},
        "footprints": {"house": [HOUSE[0], HOUSE[2], HOUSE[1], HOUSE[3]], "houseFrontZ": HOUSE[3] + 0.004,
                       "threshing": {"centre": list(THR_C), "radius": THR_R + 0.022},
                       "field": list(FIELD), "stubble": list(STUBBLE), "fieldWall": {"x": WALL_X, "z": list(wall_span)},
                       "sheaves": [list(s) for s in SHEAF_SPOTS], "canopyPoles": [[-CANOPY_X, 0.0], [CANOPY_X, 0.0]],
                       "floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]], "hillsFrontZ": NEAR_ZB},
        "heights": {"house": HOUSE_H, "parapetTop": HOUSE_H + 0.026, "oliveCrownBottom": 0.17, "canopyTop": CANOPY_TOP,
                    "hillsTop": round(max(far_ridge(x) for x in np.linspace(-0.6, 0.6, 241)), 4), "barleyMax": 0.09},
        "animations": {"fieldSway": {"node": "field", "mesh": "barley", "length": 4.0, "fps": 24, "loop": True,
                                     "clumps": nclumps}},
        "hiddenAtStart": ["dropped", "canopy"],
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227; "
                             "P = world position, or the template position for instanced pieces",
                   "edgeOn": "faces with |n . D| < 0.22 (n in drawing space) take one clean texel of their region",
                   "namedTexels": "no-raster bits (stubble, tufts, pebbles, dropped stalks) take one texel of a named "
                                  "(drawing, region); constUV in model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard, "startMoves": soft},
        "sheetLayout": {"characters": CHAR_PROPOSAL, "charactersFrom": "model/regions_characters.json" if CHARS_FROM_FILE
                        else "proposal (regions_characters.json not there yet)"},
        "demoColours": COLOURS, "tris": total, "budget": MAX_TRIS,
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
    save_png(line, os.path.join(WORK, "bethlehem_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "bethlehem_drawings_demo.png"))
    tex = np.where(mask[..., None], grain, 0.0); got = mask.copy()
    for _ in range(10):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = shift(got, dy, dx); sv = shift(tex, dy, dx)
            take = sm & ~got
            tex[take] = sv[take]; got |= take
    tex[~got] = 1.0
    return tex, demo


# ============================================================================================ preview
def flat_mat(name, hexc, rough=0.7, emit=None):
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


def tex_mat(name, img, rough=0.85):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = rough
    try:
        b.inputs["Specular IOR Level"].default_value = 0.2
    except KeyError:
        pass
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.extension = 'EXTEND'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    W, H = PAGE
    mp.inputs["Location"].default_value = (ART[0] / W, (H - ART[1] - ART[3]) / H, 0)
    mp.inputs["Scale"].default_value = (ART[2] / W, ART[3] / H, 1)
    nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], t.inputs[0])
    nt.links.new(t.outputs[0], b.inputs["Base Color"])
    return m


def mannequins(layout):
    """preview stand-ins only (not shipped): simple figures in the demo colours at the actors' marks"""
    mats = {k: flat_mat("pvm_" + k, v, 0.6) for k, v in {
        "skin": "#E9B48F", "sage": "#9CC5A1", "cream": "#F3E9D2", "brown": "#8A5A3B", "hair": "#4A2E1F",
        "rose": "#B98A9E", "greyblue": "#8FA3B8", "ochre": "#D9A63A", "silver": "#C9C4BE", "olive": "#6E7F3A",
        "tunic": "#EFE3C8", "cord": "#4B3A26", "beard": "#3A2418", "rust": "#B5532E", "staff": "#9B6B43"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    for who, (x, z, yaw) in layout.items():
        mb = MB()
        if who == "ruth":
            lathe(mb, [(0.0, 0.0), (0.046, 0.0), (0.044, 0.02), (0.036, 0.10), (0.028, 0.19), (0.024, 0.235),
                       (0.0, 0.24)], "sage", C=(x, 0, z), seg=18)
            lathe(mb, [(0.030, 0.150), (0.030, 0.162)], "brown", C=(x, 0, z), seg=18)
            sphere(mb, (x, 0.268, z), 0.030, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, 0.205), (0.034, 0.21), (0.036, 0.26), (0.033, 0.29), (0.0, 0.302)], "cream",
                  C=(x, 0, z - 0.006), seg=16, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.35 else 0.0001)
        elif who == "naomi":
            lathe(mb, [(0.0, 0.0), (0.047, 0.0), (0.045, 0.02), (0.038, 0.10), (0.030, 0.18), (0.026, 0.225),
                       (0.0, 0.23)], "rose", C=(x, 0, z), seg=18)
            sphere(mb, (x, 0.255, z + 0.006), 0.029, "skin", seg=14, rings=9)
            lathe(mb, [(0.0, 0.17), (0.042, 0.175), (0.040, 0.245), (0.034, 0.28), (0.0, 0.292)], "greyblue",
                  C=(x, 0, z - 0.006), seg=16, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.35 else 0.0001)
            tube(mb, [(x + 0.045, 0.0, z + 0.02), (x + 0.045, 0.26, z + 0.02)], 0.004, "staff", seg=6)
        else:
            lathe(mb, [(0.0, 0.0), (0.052, 0.0), (0.050, 0.02), (0.044, 0.12), (0.040, 0.22), (0.036, 0.28),
                       (0.0, 0.285)], "tunic", C=(x, 0, z), seg=18)
            lathe(mb, [(0.054, 0.02), (0.050, 0.12), (0.046, 0.22), (0.044, 0.28)], "olive", C=(x, 0, z - 0.004),
                  seg=18, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.55 else 0.0001)
            sphere(mb, (x, 0.318, z), 0.033, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.300, z + 0.014), 0.020, "beard", seg=10, rings=7, sh=1.2, sz=0.8)
            lathe(mb, [(0.0, 0.29), (0.038, 0.30), (0.038, 0.335), (0.036, 0.35, "cord"), (0.037, 0.357, "tunic"),
                       (0.0, 0.365)], "tunic", C=(x, 0, z - 0.004), seg=16)
        ob = make_obj("pv_" + who, mb, None, origin=(x, 0.0, z), smooth_angle=60)
        ob["pv"] = 1
        ob.rotation_euler = (0, 0, math.radians(yaw))


def mode_preview():
    if not STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "bethlehem_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "bethlehem_preview_sheet.png")); sheet.pack()
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
    lamp_l = bpy.data.lights.new("pv_lamp", 'POINT'); lamp_l.color = (1.0, 0.62, 0.30); lamp_l.shadow_soft_size = 0.01
    lamp_o = link(bpy.data.objects.new("pv_lamp", lamp_l)); lamp_o.location = B(*STATE["flame"]) + Vector((0, 0, 0.012))
    flame_m = flat_mat("pv_flame", "#FFB040", 0.5, emit=("#FFA030", 6.0))
    mbf = MB()
    fx, fh, fz = STATE["flame"]
    lathe(mbf, [(0.0, fh - 0.001), (0.0032, fh + 0.003), (0.0024, fh + 0.008), (0.0, fh + 0.014)], "f", C=(fx, 0, fz),
          seg=10)
    fob = make_obj("pv_flame", mbf, None); fob.data.materials[0] = flame_m

    def light(mode):
        if mode == "day":
            sun.data.energy = 3.1; sun.data.color = (1.0, 0.95, 0.86)
            sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-30))
            fill.data.energy = 6.0; fill.data.color = (1.0, 0.88, 0.72)
            bg.inputs[0].default_value = (0.80, 0.84, 0.90, 1); bg.inputs[1].default_value = 0.75
            lamp_l.energy = 0.0; fob.hide_render = True
        else:
            sun.data.energy = 0.45; sun.data.color = (0.55, 0.66, 1.0)
            sun.rotation_euler = (math.radians(55), math.radians(20), math.radians(40))
            fill.data.energy = 1.0; fill.data.color = (0.45, 0.55, 1.0)
            bg.inputs[0].default_value = (0.10, 0.13, 0.28, 1); bg.inputs[1].default_value = 0.5
            lamp_l.energy = 0.35; fob.hide_render = False
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
    light("day")
    show(["canopy", "dropped"], False)
    cast({})
    phone = ((-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280))
    shoot("bethlehem_preview_phone_set", *phone)
    # a lower, closer phone (about 40 cm above an A4 page = 2.4 art widths): what a child holding the phone sees
    shoot("bethlehem_preview_phone_low", (0.02, 0.62, 0.95), (0.02, 0.06, -0.30), 52, (720, 1280))
    shoot("bethlehem_preview_front", (0.0, 0.26, 2.3), (0.0, 0.14, -0.25), 21, (1600, 1000))
    cast({"ruth": (0.14, 0.10, 0), "naomi": (-0.40, -0.22, 0), "boaz": (0.40, 0.16, -60)})
    shoot("bethlehem_preview_phone", *phone)
    cast({"naomi": (-0.40, 0.16, 20), "ruth": (-0.28, 0.14, -20)})
    shoot("bethlehem_preview_orbit", orbit((0.0, 0.10, -0.18), 1.6, 0.55, -30), (0.0, 0.08, -0.18), 38, (1280, 720))
    cast({"ruth": (0.14, 0.10, 60), "boaz": (0.30, 0.13, -60)})
    show(["dropped"], True)
    shoot("bethlehem_preview_field", (0.66, 0.20, 0.34), (0.33, 0.04, -0.08), 40, (1280, 720))
    show(["dropped"], False)
    light("night")
    cast({"boaz": (0.14, -0.30, 160), "ruth": (0.00, -0.22, 120)})
    shoot("bethlehem_preview_night", (0.62, 0.36, 0.12), (0.12, 0.08, -0.34), 40, (1280, 720))
    light("day")
    show(["canopy"], True)
    cast({"boaz": (0.06, 0.08, -30), "ruth": (-0.06, 0.08, 30), "naomi": (-0.22, 0.12, 30)})
    shoot("bethlehem_preview_wedding", orbit((0.0, 0.12, 0.0), 0.9, 0.30, 20), (0.0, 0.16, -0.04), 40, (1280, 720))
    show(["canopy"], False); cast({})
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "bethlehem_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    if os.environ.get("RU_CLOSEUPS", "1") == "1":
        shoot("close_house", (-0.17, 0.20, -0.10), (-0.30, 0.10, -0.40), 40, (1000, 1000), WORK)
        shoot("close_door", (-0.27, 0.10, -0.18), (-0.30, 0.07, -0.33), 34, (1000, 1000), WORK)
        shoot("close_threshing", (0.22, 0.22, -0.18), (0.30, 0.03, -0.44), 42, (1000, 1000), WORK)
        shoot("close_olive", (-0.30, 0.18, 0.15), (-0.44, 0.13, -0.08), 46, (1000, 1000), WORK)
        shoot("close_barley", (0.30, 0.09, 0.07), (0.36, 0.05, -0.06), 40, (1000, 800), WORK)
        shoot("close_hills", (0.0, 0.25, -0.15), (0.0, 0.14, -0.57), 50, (1200, 700), WORK)
        shoot("close_wall", (0.10, 0.08, 0.04), (0.186, 0.02, -0.08), 40, (1000, 800), WORK)
        show(["canopy"], True)
        shoot("close_canopy", (0.0, 0.25, 0.45), (0.0, 0.25, 0.0), 40, (1000, 900), WORK)
        show(["canopy"], False)
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["bethlehem", "ground", "road", "hills", "house", "door", "window", "ladder", "houseJars", "basket", "oven",
        "threshing", "grainHeap", "fork", "lamp", "lampFlame", "field", "barley", "stubble", "sheaves", "fieldWall",
        "olive", "waterJars", "dropped", "canopy"]


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
    acts = [a.name for a in bpy.data.actions]
    parents = {n: (bpy.data.objects[n].parent.name if bpy.data.objects[n].parent else None) for n in NEED[1:]
               if n in names}
    fl = [round(c, 4) for c in D(bpy.data.objects["lampFlame"].matrix_world.translation)] if "lampFlame" in names else None
    sway = 0.0
    ob = bpy.data.objects.get("barley")
    if ob is not None:
        dg = bpy.context.evaluated_depsgraph_get(); pos = []
        for f in (1, 25, 49, 97):
            bpy.context.scene.frame_set(f); dg.update()
            me = ob.evaluated_get(dg).to_mesh()
            pos.append(np.array([tuple(ob.matrix_world @ v.co) for v in me.vertices]))
            ob.evaluated_get(dg).to_mesh_clear()
        sway = float(max(np.abs(pos[1] - pos[0]).max(), np.abs(pos[2] - pos[0]).max()))
        loop = float(np.abs(pos[3] - pos[0]).max())
    else:
        loop = 1.0
    ok = (not missing and tris <= MAX_TRIS and 0.002 < sway < 0.02 and loop < 1e-4 and uv_bad == 0
          and any("fieldSway" in a for a in acts))
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "actions": acts, "parents": parents, "lampFlame": fl,
                                                         "fieldSwayMax": round(sway, 4), "loopError": loop}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
