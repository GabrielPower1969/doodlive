"""Blender (headless): Daniel story pack, Babylon -> assets/daniel/model/babylon.glb

A tabletop stage on the colouring sheet, back to front: the mud-brick city wall (reed-mat courses, brick patches,
stepped merlons, buttress towers, flat roofs, a ziggurat and palms beyond) with the blue-glazed `gate` (towers,
arched wooden doors, gold rosettes and walking lions); the palace front (a façade with a blue rosette
frieze, a three-step dais, two columns with palm-leaf capitals, a red canopy with a scalloped valance, the carved
`throne` with lion-head arms, incense stands, jars and two pole torches, `torch` = the flame point of the left one);
Daniel's two-storey mud-brick house (outside stair, terrace with a wooden balcony rail, shutters, beam ends, plant
pots, a hanging cloth); the short `windowWall` with an arched lattice window and open shutters, the woven `rug`; three
date palms (`palm`); the lions' den (a ring of chamfered stone blocks with coping, sandy floor, a straw bed, two flat
rocks, a water trough) with the big round stone (`stoneOpen`, and `stoneShut` + `seal` hidden until S08); the
`market` stall (striped awning, pomegranates, melons, dates, jars) and the courtyard (`ground`: paving slabs with
cracks, sand at the edges, tufts and pebbles).
Contract: docs/daniel/CONTRACT.md §6. Details, nodes, marks and UV rules: docs/daniel/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge (as Esther and Ruth). In Blender (Z up) a design point (x, h, z) is
(X, Y, Z) = (x, -z, h); export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `da_page` = the scanned art rectangle): as Ruth (pipeline/ru_bethlehem.py). Each piece
belongs to one drawing on the sheet, a linear view a = A.P, b = B.P, u = a / scale + sheetX + 0.5,
v = (b / scale + sheetY) / 1.227. Instanced pieces (the three palms, the two stones and the seal) use their
template position P, so they wear one drawing. New here: a face takes one clean texel deep inside its own region not
only when it is edge-on to its drawing (|n.D| < 0.22) but also when it faces away from the drawing (n.D < 0) or is
hidden behind another part of the same drawing (its centre lands on another region): no mirrored or borrowed print
on backs and undersides (LESSONS L51). Thin or tiny bits (torch poles, lattice bars, cords, fringe, straw, pebbles)
are not drawn and take a texel of a named region (CONSTS).

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/da_babylon.py -- build     babylon.glb + .blend + sheet drawings
  blender -b --factory-startup --python pipeline/da_babylon.py -- verify    re-import babylon.glb and check it
  blender -b --factory-startup --python pipeline/da_babylon.py -- all       build, preview, verify
  blender -b --factory-startup --python pipeline/da_babylon.py -- check     build in memory, print the checks only
Work files go to $DA_WORK (default /tmp/daniel_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/daniel/model")
GLB = os.path.join(MODEL, "babylon.glb")
BLEND = os.path.join(MODEL, "babylon.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/daniel/design.json")
TIMELINE = os.environ.get("DA_TIMELINE", os.path.join(ROOT, "assets/daniel/timeline.json"))
WORK = os.environ.get("DA_WORK", "/tmp/daniel_set")
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
MAX_TRIS = 80000                     # contract: 60k asked, <= 80k allowed
TARGET_TRIS = 60000
TAU = 2 * math.pi
UP = (0.0, 1.0, 0.0)
FLOOR = (-0.60, 0.60, -0.5875, 0.21)


def hex_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4))


def lin(c):
    return tuple(x / 12.92 if x <= 0.04045 else ((x + 0.055) / 1.055) ** 2.4 for x in c)


def B(x, h, z):
    return Vector((x, -z, h))


def D(v):
    return (v.x, v.z, -v.y)


def nz(a, b=0.0, c=0.0):
    s = math.sin(a * 12.9898 + b * 78.233 + c * 37.719) * 43758.5453
    return s - math.floor(s)


# ============================================================================================ mesh builder (as Ruth)
class MB:
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

    def add(self, src, fn, world_p=False):
        """instance of `src`: world = fn(local); P = the template's own P (its drawing model), or the new world
        position when world_p (plain geometry built in a helper frame)"""
        base = len(self.V)
        for i, (x, h, z) in enumerate(src.V):
            self.V.append(tuple(float(c) for c in fn((x, h, z))))
            self.P.append(self.V[-1] if world_p else src.P[i])
        for f, r, s, nr in zip(src.F, src.R, src.S, src.N):
            self.F.append([base + i for i in f]); self.R.append(r); self.S.append(s); self.N.append(nr or self.nr)


def yaw_fn(x0, z0, yaw=0.0, s=1.0, h0=0.0, lean=(0.0, 0.0), sxz=1.0):
    """template -> world: scale s (sxz extra on x and z only), yaw, then move to (x0, z0)"""
    c, sn = math.cos(yaw), math.sin(yaw)

    def f(p):
        x, h, z = p
        x, z = x * sxz, z * sxz
        x, z = x * c - z * sn, x * sn + z * c
        return (x0 + s * (x + lean[0] * h), h0 + s * h, z0 + s * (z + lean[1] * h))
    return f


PALM_SXZ = 0.68          # the palm template is drawn wide on the sheet (6 mm trunk); the 3D palms are 0.68 as wide


def box(mb, x0, x1, h0, h1, z0, z1, reg, skip=(), smooth=False):
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


def cbox(mb, x0, x1, h0, h1, z0, z1, reg, c=0.0015, skip_bottom=True):
    """box with a chamfered top rim (stone slabs, steps, coping)"""
    c = min(c, (x1 - x0) / 3, (z1 - z0) / 3, (h1 - h0) / 2)
    hc = h1 - c
    lo = [mb.v(x0, h0, z0), mb.v(x1, h0, z0), mb.v(x1, h0, z1), mb.v(x0, h0, z1)]
    mid = [mb.v(x0, hc, z0), mb.v(x1, hc, z0), mb.v(x1, hc, z1), mb.v(x0, hc, z1)]
    top = [mb.v(x0 + c, h1, z0 + c), mb.v(x1 - c, h1, z0 + c), mb.v(x1 - c, h1, z1 - c), mb.v(x0 + c, h1, z1 - c)]
    mb.fo(top, reg, UP)
    outs = [(0, 0, -1), (1, 0, 0), (0, 0, 1), (-1, 0, 0)]
    for k in range(4):
        k1 = (k + 1) % 4
        o = outs[k]
        mb.fo([lo[k], lo[k1], mid[k1], mid[k]], reg, o)
        mb.fo([mid[k], mid[k1], top[k1], top[k]], reg, (o[0], 0.8, o[2]))
    if not skip_bottom:
        mb.fo(lo, reg, (0, -1, 0))


def lathe(mb, prof, reg, C=(0, 0, 0), A=(0, 1, 0), U=(1, 0, 0), V=(0, 0, 1), seg=16, smooth=True, rfun=None,
          sx=1.0, sv=1.0, phase=0.0):
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


def lumpy(mb, c, r, reg, seg=10, rings=6, sh=1.0, sx=1.0, sz=1.0, amp=0.12, seed=0.0, smooth=True, flat_bottom=None):
    prof = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        prof.append((r * math.sin(th), -r * math.cos(th) * sh))
    prof[0] = (0.0, prof[0][1]); prof[-1] = (0.0, prof[-1][1])
    if flat_bottom is not None:
        prof = [(rr, max(a, flat_bottom - c[1])) for rr, a in prof]
    lathe(mb, prof, reg, C=c, seg=seg, smooth=smooth, sx=sx, sv=sz,
          rfun=lambda t, i, k: 1.0 + amp * (nz(i + seed, k, seed * 3.1) - 0.5) * 2)


def tube(mb, pts, r, reg, seg=8, closed=False, smooth=True, caps=True, ref=None):
    pts = [Vector(p) for p in pts]; n = len(pts)
    rs = list(r) if isinstance(r, (list, tuple)) else [r] * n
    rings, prev = [], None
    for i in range(n):
        t = (pts[(i + 1) % n] - pts[i - 1]) if closed else (pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)])
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


def extrude(mb, poly, zb, zf, reg, X=lambda a, b: (a, b), back=True, side_reg=None, smooth=False, holes=()):
    """front-facing relief: polygon (a, b) -> (x, h) by X, from z = zb (back) to z = zf (front); optional holes
    (each a polygon) cut through the front face with reveals"""
    def clean(poly):
        pts = []
        for a, b in poly:
            p = X(a, b)
            if not pts or (abs(p[0] - pts[-1][0]) + abs(p[1] - pts[-1][1])) > 1e-7:
                pts.append(p)
        if abs(pts[0][0] - pts[-1][0]) + abs(pts[0][1] - pts[-1][1]) < 1e-7:
            pts.pop()
        return pts
    pts = clean(poly)
    hl = [clean(h) for h in holes]
    allp = pts + sum(hl, [])
    fr = [mb.v(x, h, zf) for x, h in allp]
    tris = tessellate_polygon([[Vector((x, h, 0)) for x, h in pts]] + [[Vector((x, h, 0)) for x, h in q] for q in hl])
    for t in tris:
        mb.fo([fr[i] for i in t], reg, (0, 0, 1), smooth)
    if back:
        bk_all = [mb.v(x, h, zb) for x, h in allp]
        for t in tris:
            mb.fo([bk_all[i] for i in t], reg, (0, 0, -1), smooth)
    for loop in [pts] + hl:
        n = len(loop)
        area = sum(loop[i][0] * loop[(i + 1) % n][1] - loop[(i + 1) % n][0] * loop[i][1] for i in range(n)) / 2
        hole = loop is not pts
        for i in range(n):
            j = (i + 1) % n
            dx, dh = loop[j][0] - loop[i][0], loop[j][1] - loop[i][1]
            o = (dh, -dx) if area > 0 else (-dh, dx)
            if hole:
                o = (-o[0], -o[1])
            mb.fo([mb.v(loop[i][0], loop[i][1], zf), mb.v(loop[j][0], loop[j][1], zf), mb.v(loop[j][0], loop[j][1], zb),
                   mb.v(loop[i][0], loop[i][1], zb)], side_reg or reg, (o[0], o[1], 0), smooth)


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
        a, b = np.array(poly[i], float), np.array(poly[(i + 1) % n], float)
        L = np.linalg.norm(b - a); k = max(1, int(math.ceil(L / step)))
        for j in range(k):
            out.append(a + (b - a) * j / k)
    return np.array(out)


def puff(mb, poly, zc, half, reg, X=lambda a, b: (a, b), rad=0.006, edge=0.3, step=0.004, smooth=True, back=False):
    """pillow-shaped relief from a front polygon (rounded at the outline, exact front silhouette)"""
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
        if len(G):
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
        if back:
            mb.fo([bk[i] for i in t], reg, (0, 0, -1), smooth)
    order = [int(np.argmin(((V - p) ** 2).sum(1))) for p in bnd]
    area = sum(bnd[i][0] * bnd[(i + 1) % K][1] - bnd[(i + 1) % K][0] * bnd[i][1] for i in range(K))
    for i in range(K):
        a, b = order[i], order[(i + 1) % K]
        dx, dy = V[b] - V[a]
        o = (dy, -dx) if area > 0 else (-dy, dx)
        mb.fo([fr[a], fr[b], bk[b], bk[a]], reg, (o[0], o[1], 0), smooth)


def blade(mb, pts, widths, reg, nrm=None):
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


def ngon_top(mb, poly_xz, h, reg, hb=None, out=UP, hfun=None):
    top = [mb.v(x, h + (hfun(x, z) if hfun else 0.0), z) for x, z in poly_xz]
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


def in_poly(p, poly):
    return bool(_inside(np.array([p], float), np.asarray(poly, float))[0])


def blob_poly(cx, cz, r, seed, n=16, amp=0.28, sz=0.8):
    return np.array([(cx + r * (1 + amp * (nz(seed, k) - 0.5) * 2) * math.cos(TAU * k / n),
                      cz + r * sz * (1 + amp * (nz(seed + 1, k) - 0.5) * 2) * math.sin(TAU * k / n)) for k in range(n)])


def patchy(x, h, seed=0.0, thr=0.40):
    """low-frequency 'brick patch' mask: the cartoon way of drawing a few bricks here and there"""
    v = (math.sin(41 * x + 7 * h + seed) * math.sin(23 * h - 13 * x + 2 * seed) +
         0.5 * math.sin(67 * x - 31 * h + 3 * seed))
    return v > thr


def blocks(mb, L, rows, W, rng, reg, holes=lambda h0, h1: [], wmin=0.026, wmax=0.046, proud=(0.0022, 0.0042),
           g=0.0012, ch=0.0014, decor=None, patch=None, only_patch=False):
    """courses of chamfered blocks on any surface W(s, h, d) -> (x, h, z), d = out of the surface (the normal is
    taken per block, so W may curve). patch(s, h): blocks whose outline is printed (decor); only_patch: build only
    those (brick patches on a plastered wall)."""
    h = 0.0
    n = 0
    for ri, rh in enumerate(rows):
        h0, h1 = h, h + rh
        h = h1
        blocked = sorted(holes(h0, h1))
        s = -rng.uniform(0.0, wmin) if ri % 2 else 0.0
        while s < L - 1e-4:
            w = rng.uniform(wmin, wmax)
            a, b = max(s, 0.0), min(s + w, L)
            s += w
            for bs0, bs1 in blocked:
                if a < bs1 and b > bs0:
                    if a >= bs0 and b <= bs1:
                        a = b
                    elif a < bs0:
                        b = bs0
                    else:
                        a = bs1
            if b - a < 0.006:
                continue
            sm, hm = (a + b) / 2, (h0 + h1) / 2
            inp = patch(sm, hm) if patch else True
            if only_patch and not inp:
                continue
            if decor is not None and inp:
                for p0, p1 in (((a, h0), (b, h0)), ((b, h0), (b, h1)), ((b, h1), (a, h1)), ((a, h1), (a, h0))):
                    decor.append((W(p0[0], p0[1], 0.0), W(p1[0], p1[1], 0.0)))
            dp = rng.uniform(*proud)
            sa, sb, ha, hb = a + g, b - g, h0 + g, h1 - g
            c = min(ch, (sb - sa) / 3, (hb - ha) / 3)
            j = lambda: rng.uniform(-0.0004, 0.0004)
            o = [mb.v(*W(sa, ha, 0)), mb.v(*W(sb, ha, 0)), mb.v(*W(sb, hb, 0)), mb.v(*W(sa, hb, 0))]
            q = [mb.v(*W(sa + c + j(), ha + c, dp)), mb.v(*W(sb - c + j(), ha + c, dp + j())),
                 mb.v(*W(sb - c + j(), hb - c, dp)), mb.v(*W(sa + c + j(), hb - c, dp + j()))]
            P0 = Vector(W(sm, hm, 0))
            out = Vector(W(sm, hm, 0.01)) - P0
            sides = [Vector(W(sm, hm - 0.01, 0)) - P0, Vector(W(sm + 0.01, hm, 0)) - P0,
                     Vector(W(sm, hm + 0.01, 0)) - P0, Vector(W(sm - 0.01, hm, 0)) - P0]
            mb.fo(q, reg, tuple(out))
            for k in range(4):
                mb.fo([o[k], o[(k + 1) % 4], q[(k + 1) % 4], q[k]], reg, tuple(sides[k] + out * 0.3))
            n += 1
    return n


# ============================================================================================ layout of the page
WALL_ZF, WALL_ZB, WALL_TOP = -0.560, -0.5875, 0.215
GATE_X0, GATE_X1 = 0.20, 0.60                       # the glazed section (node `gate`)
GATE_C, ARCH_HW, ARCH_SPRING = 0.40, 0.036, 0.104
PAL_FACADE_Z = (-0.559, -0.541)
PLAT = (-0.165, 0.165, -0.541, -0.384, 0.040)      # x0 x1 zb zf top
STEPS_HW = 0.12
STEP_FRONT = -0.352
COLS = [(-0.135, -0.402), (0.135, -0.402)]
COL_TOP = 0.268
TORCH = (-0.15, -0.36)
TORCH2 = (0.15, -0.36)
TORCH_H = 0.192
THRONE = (0.0, -0.497)
HOUSE = (-0.565, -0.325, -0.545, -0.345)            # lower storey x0 x1 zb zf
HOUSE_H1, HOUSE_H2 = 0.125, 0.245
UPPER = (-0.565, -0.415, -0.545, -0.395)
STAIR_X = (-0.325, -0.297)
WWALL_X = (-0.5545, -0.5305)
WWALL_Z = (-0.24, -0.04)
WWALL_H = 0.160
WIN_Z, WIN_HW, WIN_SILL, WIN_SPRING = -0.14, 0.026, 0.056, 0.114
RUG = (-0.515, -0.365, -0.195, -0.085)
PALM_MAIN = (-0.29, -0.07)
PALMS_SIDE = [(-0.222, -0.505, 0.80), (0.222, -0.505, 0.82)]
DEN_C = (0.38, -0.17)
DEN_T, DEN_TOP = 0.030, 0.076
DEN_OPEN_TH = math.radians(133.5)                   # opening direction (clearance for Daniel's walk in and out)
DEN_OPEN_HALF = 0.356                               # half angle (inner chord ~0.108, mid chord ~0.122)
DEN_BULGE_TH = math.atan2(-0.26 - DEN_C[1], 0.30 - DEN_C[0])
STONE_R, STONE_T = 0.062, 0.028
MARKET = (0.52, 0.15)
LION_ROCKS = [(0.45, -0.22, 0.054, 0.044, 0.3), (0.30, -0.255, 0.044, 0.033, -0.5)]
TROUGH = (0.517, -0.165, 0.026, 0.080)              # cx cz size-x size-z (against the right wall)


def den_rin(th):
    d = math.atan2(math.sin(th - DEN_BULGE_TH), math.cos(th - DEN_BULGE_TH))
    return 0.160 + 0.022 * math.exp(-(d / 0.42) ** 2)


def den_pt(th, r):
    return (DEN_C[0] + r * math.cos(th), DEN_C[1] + r * math.sin(th))


DEN_OPEN_PT = den_pt(DEN_OPEN_TH, 0.175)


# ============================================================================================ marks and paths
HEIGHT = {"daniel": 0.34, "king": 0.44, "officer": 0.35, "lion": 0.22, "lion2": 0.21}
CONTRACT_MARKS = [("king", (0.00, -0.30)), ("king", (-0.05, -0.30)), ("king", (0.05, 0.08)), ("king", (0.02, -0.02)),
                  ("daniel", (-0.14, -0.20)), ("daniel", (-0.30, -0.24)), ("daniel", (-0.42, -0.14)),
                  ("daniel", (-0.20, -0.16)), ("daniel", (0.16, 0.03)), ("daniel", (0.36, -0.13)),
                  ("daniel", (0.13, 0.06)), ("daniel", (-0.12, 0.02)),
                  ("officer", (0.12, -0.22)), ("officer", (0.04, 0.10)), ("officer", (0.30, 0.10)),
                  ("officer", (-0.22, -0.02)), ("officer", (-0.12, 0.12)), ("officer", (-0.30, 0.16)),
                  ("officer", (-0.40, 0.18)),
                  ("lion", (0.45, -0.22)), ("lion2", (0.30, -0.26)), ("lion", (0.44, -0.09)), ("lion2", (0.28, -0.18))]
FLAT_OK = {"rug"}                                   # contract: the rug is flat, allowed under a mark


def _timeline():
    try:
        return json.load(open(TIMELINE))
    except Exception:
        return {"acting": [], "props": []}


TL = _timeline()


def _paths():
    """(actor, a, b, t0, t1): consecutive targets of one actor in timeline.json (off-page ends are clipped to the
    floor edge, the part on the page counts)"""
    out, last = [], {}
    for a in TL["acting"]:
        if "to" not in a:
            continue
        w, p = a["who"], (float(a["to"][0]), float(a["to"][1]))
        if w in last and math.hypot(p[0] - last[w][0], p[1] - last[w][1]) > 1e-4:
            L = math.hypot(p[0] - last[w][0], p[1] - last[w][1])
            out.append((w, last[w], p, float(a["t"]), float(a["t"]) + L / 0.08 + 1.0))
        last[w] = p
    return out


PATHS = _paths()


def _prop_events():
    ev = {}
    for p in TL.get("props", []):
        node = p["node"].split("/", 1)
        if node[0] == "babylon":
            ev.setdefault(node[1], []).append((float(p["t"]), bool(p["show"])))
    for k in ev:
        ev[k].sort()
    return ev


PROP_EV = _prop_events()


def visible_during(node, t0, t1):
    ev = PROP_EV.get(node)
    if not ev:
        return True
    state = True
    for t, s in ev:
        if t <= t0:
            state = s
    if state:
        return True
    return any(s and t0 < t <= t1 for t, s in ev)


def seg_dist(p, a, b):
    ax, az = a; bx, bz = b; px, pz = p
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    return math.hypot(px - ax - t * dx, pz - az - t * dz)


def clear_dist(x, z):
    d = min(math.hypot(x - a, z - b) for _, (a, b) in CONTRACT_MARKS)
    for _, a, b, _, _ in PATHS:
        d = min(d, seg_dist((x, z), a, b))
    return d


# demo colouring (DESIGN.md table; the rest chosen to sit with it)
COLOURS = {
    "sand": "#E2C389", "paving": "#E6D6B4",
    "mudBrick": "#D8B07A", "roofBeyond": "#D9A06A", "ziggurat": "#C99A62", "palmFar": "#5E9446",
    "gateTile": "#2E5FA8", "relief": "#E8C15A", "gateDoor": "#8A5A3B",
    "palaceWall": "#EAD7AE", "sandstone": "#E3CFA3", "canopy": "#B8423A", "frieze": "#2E5FA8", "throne": "#D9A63A",
    "cushion": "#B8423A",
    "houseWall": "#D9A06A", "roof": "#C98F5C", "wood": "#8A5A3B",
    "shutter": "#8A5A3B",
    "rugRed": "#B8423A", "rugBlue": "#2E5FA8", "rugCream": "#F4EEDD",
    "frond": "#4F8A3C", "trunk": "#8A6A44",
    "denStone": "#9C8A72", "denFloor": "#D9B77A", "straw": "#E9D08A", "flatRock": "#B5A68C",
    "bigStone": "#A79A86", "wax": "#C0392B",
    "awningRed": "#B8423A", "awningCream": "#F4EEDD", "stallWood": "#A47548", "pomegranate": "#C0392B",
    "melon": "#7DAA4E", "marketJar": "#C8643C", "dates": "#B8682E",
}


# ============================================================================================ objects
REGION_MATS = {}
P_OF, NR_OF, REG_OF = {}, {}, {}
DECOR = {}


def region_mat(r):
    if r not in REGION_MATS:
        m = bpy.data.materials.new("rg_" + r)
        m.diffuse_color = (*lin(hex_rgb(COLOURS.get(r, "#FFFFFF"))), 1)
        REGION_MATS[r] = m
    return REGION_MATS[r]


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def make_obj(name, mb, parent=None, origin=(0, 0, 0), smooth_angle=40.0, merge=True):
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
    bm = bmesh.new(); bm.from_mesh(me)
    if merge:
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
    bm.normal_update()
    pcl = bm.edges.layers.int.new("pc")            # printed crease: sharp edges between exactly two faces
    for e in bm.edges:
        two = len(e.link_faces) == 2
        if not two or e.calc_face_angle(0) > math.radians(smooth_angle):
            e.smooth = False
        elif not (e.link_faces[0].smooth or e.link_faces[1].smooth) and e.calc_face_angle(0) > math.radians(12):
            e.smooth = False
        if two and not e.smooth:
            n0, n1 = e.link_faces[0].normal, e.link_faces[1].normal
            e[pcl] = 1 if n0.dot(n1) > -0.9 else 0  # not the rim of a double-sided sheet
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


# ============================================================================================ ground
def pave_poly():
    pts = []
    x0, x1, z0, z1, r = -0.475, 0.445, -0.312, 0.172, 0.05
    for (cx, cz, a0) in ((x1 - r, z1 - r, 0.0), (x0 + r, z1 - r, 0.5 * math.pi), (x0 + r, z0 + r, math.pi),
                         (x1 - r, z0 + r, 1.5 * math.pi)):
        for k in range(5):
            a = a0 + 0.5 * math.pi * k / 4
            pts.append((cx + r * math.cos(a), cz + r * math.sin(a)))
    return _resample(np.array(pts), 0.03) + np.array([[(nz(i, 1) - 0.5) * 0.008, (nz(i, 2) - 0.5) * 0.008]
                                                       for i in range(len(_resample(np.array(pts), 0.03)))])


def in_den(x, z, pad=0.0):
    return math.hypot(x - DEN_C[0], z - DEN_C[1]) < den_rin(math.atan2(z - DEN_C[1], x - DEN_C[0])) + DEN_T + pad


BLOCKED = [  # footprints (x0, x1, z0, z1) where the paving and scatter stop
    (HOUSE[0] - 0.01, STAIR_X[1] + 0.005, HOUSE[2], HOUSE[3] + 0.008),
    (PLAT[0] - 0.012, PLAT[1] + 0.012, -0.56, STEP_FRONT + 0.002),
    (WWALL_X[0] - 0.006, WWALL_X[1] + 0.006, WWALL_Z[0] - 0.006, WWALL_Z[1] + 0.006),
    (MARKET[0] - 0.075, MARKET[0] + 0.08, MARKET[1] - 0.055, MARKET[1] + 0.05),
]


def build_ground(root):
    """the courtyard: a constrained triangulation of the plan regions (pale paving bed in the middle, warm sand at
    the edges), the paving itself as chamfered slabs in running bond (a few with cracks, a few tilted), with a
    skirt; tufts (palm-frond texel), pebbles and rocks (den-stone texel), and a bush at the main palm's foot"""
    pave = pave_poly()
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    outlines = [_resample(rect, 0.03), pave]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    allo = np.concatenate(outlines)
    for j, z in enumerate(np.arange(FLOOR[2] + 0.02, FLOOR[3] - 0.01, 0.034)):
        for x in np.arange(FLOOR[0] + 0.02 + (j % 2) * 0.017, FLOOR[1] - 0.01, 0.034):
            p = np.array([x + (nz(x, z) - 0.5) * 0.012, z + (nz(z, x) - 0.5) * 0.012])
            if np.min(np.hypot(*(allo - p).T)) > 0.01:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def height(x, z):
        if in_poly((x, z), pave):
            return 0.0006
        return 0.0010 + 0.0013 * (math.sin(19 * x + 4 * z) * math.sin(13 * z - 6 * x) * 0.5 + 0.5) + 0.0004 * nz(x, z)
    H = [height(x, z) for x, z in V]
    mg = MB()
    idx = {}
    for f in fs:
        if len(f) != 3:
            continue
        c = tuple(V[list(f)].mean(0))
        reg = "paving" if in_poly(c, pave) else "sand"
        q = []
        for i in f:
            if i not in idx:
                idx[i] = mg.v(V[i][0], H[i], V[i][1])
            q.append(idx[i])
        mg.fo(q, reg, UP)
    for (ax, az), (bx, bz) in zip(rect, np.roll(rect, -1, axis=0)):
        n = int(math.hypot(bx - ax, bz - az) / 0.05) + 1
        cx, cz = (ax + bx) / 2, (az + bz) / 2
        o = (cx, 0, cz - (FLOOR[2] + FLOOR[3]) / 2) if abs(az - bz) < 1e-6 else (cx, 0, 0)
        for i in range(n):
            x0, z0 = ax + (bx - ax) * i / n, az + (bz - az) * i / n
            x1, z1 = ax + (bx - ax) * (i + 1) / n, az + (bz - az) * (i + 1) / n
            mg.fo([mg.v(x0, height(x0, z0), z0), mg.v(x1, height(x1, z1), z1), mg.v(x1, -0.002, z1),
                   mg.v(x0, -0.002, z0)], "sand", o)
    # paving slabs in running bond
    rng = random.Random(21)
    dec = DECOR.setdefault("ground", [])
    nslab = 0
    zrow = -0.333
    row = 0
    while zrow < 0.170:
        dz = rng.uniform(0.042, 0.052)
        x = -0.475 - rng.uniform(0.0, 0.03)
        while x < 0.445:
            w = rng.uniform(0.050, 0.078)
            a, b = x, x + w
            x += w
            za, zb = zrow, zrow + dz
            cx, cz = (a + b) / 2, (za + zb) / 2
            corners = [(a, za), (b, za), (b, zb), (a, zb)]
            if not all(in_poly(p, pave) for p in corners):
                continue
            if any(in_den(px, pz, 0.006) for px, pz in corners + [(cx, cz)]):
                continue
            if any(x0 < px < x1 and z0 < pz < z1 for px, pz in corners + [(cx, cz)] for x0, x1, z0, z1 in BLOCKED):
                continue
            g = 0.0014
            ht = 0.0022 + 0.0009 * rng.random()
            tilt = (rng.uniform(-0.012, 0.012), rng.uniform(-0.012, 0.012)) if rng.random() < 0.18 else (0, 0)
            hf = lambda px, pz, cx=cx, cz=cz, ht=ht, tilt=tilt: ht + tilt[0] * (px - cx) + tilt[1] * (pz - cz)
            cbox_top = [(a + g, za + g), (b - g, za + g), (b - g, zb - g), (a + g, zb - g)]
            c = 0.0018
            inner = [(a + g + c, za + g + c), (b - g - c, za + g + c), (b - g - c, zb - g - c), (a + g + c, zb - g - c)]
            ti = [mg.v(px, hf(px, pz), pz) for px, pz in inner]
            to = [mg.v(px, 0.0006, pz) for px, pz in cbox_top]
            mg.fo(ti, "paving", UP)
            for k in range(4):
                k1 = (k + 1) % 4
                ox_, oz_ = (cbox_top[k][0] + cbox_top[k1][0]) / 2 - cx, (cbox_top[k][1] + cbox_top[k1][1]) / 2 - cz
                mg.fo([to[k], to[k1], ti[k1], ti[k]], "paving", (ox_, 0.4, oz_))
            nslab += 1
            if patchy(cx * 0.7, cz * 0.9, 5.0, 0.95):            # a few slabs drawn on the sheet
                for k in range(4):
                    p0, p1 = cbox_top[k], cbox_top[(k + 1) % 4]
                    dec.append(((p0[0], 0.003, p0[1]), (p1[0], 0.003, p1[1])))
            if rng.random() < 0.10:                               # a crack
                t0 = rng.uniform(0.2, 0.8)
                pts = [(a + g + (b - a - 2 * g) * t0, za + g)]
                for k in range(1, 4):
                    pts.append((pts[-1][0] + rng.uniform(-0.01, 0.01), za + g + (zb - za - 2 * g) * k / 3))
                for p0, p1 in zip(pts, pts[1:]):
                    dec.append(((p0[0], 0.003, p0[1]), (p1[0], 0.003, p1[1])))
                    tube(mg, [(p0[0], hf(*p0) + 0.0001, p0[1]), (p1[0], hf(*p1) + 0.0001, p1[1])], 0.0005, "paving",
                         seg=3, caps=False)
        zrow += dz
        row += 1
    # scattered bits
    mg.nr = True

    def free(x, z, pad=0.0):
        if not (FLOOR[0] + 0.012 < x < FLOOR[1] - 0.012 and FLOOR[2] + 0.03 < z < FLOOR[3] - 0.012):
            return False
        if in_den(x, z, 0.012 + pad):
            return False
        for x0, x1, z0, z1 in BLOCKED + [(-0.6, 0.6, -0.6, -0.556)]:
            if x0 - pad < x < x1 + pad and z0 - pad < z < z1 + pad:
                return False
        if math.hypot(x - PALM_MAIN[0], z - PALM_MAIN[1]) < 0.04:
            return False
        if RUG[0] - 0.01 < x < RUG[1] + 0.01 and RUG[2] - 0.01 < z < RUG[3] + 0.01:
            return False
        return True
    tufts = []
    tries = 0
    while len(tufts) < 70 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        sandy = not in_poly((x, z), pave)
        if not sandy and rng.random() < 0.7:
            continue
        if not free(x, z) or any(math.hypot(x - a, z - b) < 0.028 for a, b in tufts):
            continue
        tufts.append((x, z))
    for x, z in tufts:
        tall = 0.016 if clear_dist(x, z) > 0.065 else 0.0105
        for k in range(5):
            a = TAU * k / 5 + rng.uniform(-0.4, 0.4)
            hh = tall * rng.uniform(0.7, 1.05); lean = rng.uniform(0.25, 0.5) * hh
            d = (math.cos(a), math.sin(a))
            blade(mg, [(x + d[0] * 0.0015, 0.0005, z + d[1] * 0.0015), (x + d[0] * lean, hh, z + d[1] * lean)],
                  [0.0034, 0.0], "tuft", nrm=(d[0], 0.0, d[1]))
    pebbles = []
    tries = 0
    while len(pebbles) < 55 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if in_poly((x, z), pave) and rng.random() < 0.75:
            continue
        if not free(x, z) or any(math.hypot(x - a, z - b) < 0.016 for a, b in pebbles + tufts):
            continue
        pebbles.append((x, z))
    for i, (x, z) in enumerate(pebbles):
        r = rng.uniform(0.0035, 0.0062)
        lumpy(mg, (x, r * 0.35, z), r, "pebble", seg=5, rings=3, sh=0.55, sx=rng.uniform(0.9, 1.4), amp=0.18, seed=i)
    rocks = []
    tries = 0
    while len(rocks) < 10 and tries < 8000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if in_poly((x, z), pave) or not free(x, z, 0.01) or clear_dist(x, z) < 0.08:
            continue
        if any(math.hypot(x - a, z - b) < 0.06 for a, b in rocks):
            continue
        rocks.append((x, z))
    for i, (x, z) in enumerate(rocks):
        r = rng.uniform(0.008, 0.013)
        lumpy(mg, (x, r * 0.3, z), r, "pebble", seg=7, rings=4, sh=0.62, sx=rng.uniform(1.0, 1.5), amp=0.2,
              seed=i + 700, smooth=False)
    # a low bush at the main palm's foot (the official's hiding place)
    for i, (dx, dz, r) in enumerate(((-0.020, -0.006, 0.021), (0.004, 0.012, 0.018), (-0.030, 0.016, 0.015))):
        lumpy(mg, (PALM_MAIN[0] + dx, r * 0.55, PALM_MAIN[1] + dz), r, "tuft", seg=9, rings=5, sh=0.75, amp=0.22,
              seed=i + 40)
    mg.nr = False
    ob = make_obj("ground", mg, root, smooth_angle=35)
    return ob, {"slabs": nslab, "tufts": len(tufts), "pebbles": len(pebbles), "rocks": len(rocks)}


# ============================================================================================ city wall + gate
LION_SIDE = [(0.10, 0.42), (0.06, 0.48), (0.035, 0.56), (0.0, 0.60), (-0.01, 0.53), (0.03, 0.46), (0.07, 0.40),
             (0.12, 0.35), (0.12, 0.20), (0.10, 0.04), (0.13, 0.0), (0.21, 0.0), (0.195, 0.06), (0.21, 0.22),
             (0.25, 0.20), (0.27, 0.05), (0.26, 0.0), (0.345, 0.0), (0.34, 0.06), (0.33, 0.21),
             (0.40, 0.23), (0.56, 0.23),
             (0.60, 0.19), (0.60, 0.05), (0.58, 0.0), (0.665, 0.0), (0.67, 0.06), (0.68, 0.20),
             (0.71, 0.21), (0.72, 0.05), (0.70, 0.0), (0.795, 0.0), (0.79, 0.07), (0.79, 0.25),
             (0.85, 0.32), (0.89, 0.37), (0.96, 0.39), (1.0, 0.45), (0.985, 0.53), (0.93, 0.58), (0.87, 0.65),
             (0.78, 0.68), (0.69, 0.66), (0.62, 0.59), (0.57, 0.50),
             (0.40, 0.49), (0.21, 0.47), (0.13, 0.45)]


def rosette_poly(cx, ch, r, petals=8):
    pts = []
    n = petals * 6
    for k in range(n):
        a = TAU * k / n
        rr = r * (0.62 + 0.38 * abs(math.cos(petals * a / 2)) ** 0.7)
        pts.append((cx + rr * math.cos(a), ch + rr * math.sin(a)))
    return pts


def rosette(mb, cx, ch, z, r, reg="relief", fat=False):
    poly = rosette_poly(cx, ch, r) if not fat else \
        [(cx + r * (0.80 + 0.20 * abs(math.cos(4 * TAU * k / 48))) * math.cos(TAU * k / 48),
          ch + r * (0.80 + 0.20 * abs(math.cos(4 * TAU * k / 48))) * math.sin(TAU * k / 48)) for k in range(48)]
    puff(mb, poly, z + 0.0018, 0.0018, reg, rad=r * 0.35, step=max(0.0025, r / 6))
    sphere(mb, (cx, ch, z + 0.0034), r * 0.30, reg, seg=10, rings=5, sz=0.45)


def merlon_outline(x0, x1, h0, step=0.0095, n=3):
    """outline of a run of stepped (Babylonian) merlons on the wall top: list of (x, h) from x0 to x1 at h0"""
    pts = [(x0, h0)]
    w = 0.036
    x = x0 + 0.010
    while x + w <= x1 - 0.008:
        ws = [w, w * 0.66, w * 0.33]
        for i in range(n):
            pts.append((x + (w - ws[i]) / 2, h0 + step * i)); pts.append((x + (w - ws[i]) / 2, h0 + step * (i + 1)))
        for i in reversed(range(n)):
            pts.append((x + (w + ws[i]) / 2, h0 + step * (i + 1))); pts.append((x + (w + ws[i]) / 2, h0 + step * i))
        x += w + 0.012
    pts.append((x1, h0))
    return pts


def build_city_wall(root):
    """mud-brick wall relief across the back (the glazed section x 0.20..0.60 is the `gate` node): stepped merlons,
    reed-mat courses, brick patches, two buttress towers, flat roofs, a ziggurat and two palms beyond"""
    mb = MB()
    rng = random.Random(31)
    dec = DECOR.setdefault("wall", [])
    x0, x1 = FLOOR[0], GATE_X0
    xm = -0.310
    poly = [(x0, 0.0), (x1, 0.0)] + merlon_outline(xm, x1, WALL_TOP)[::-1] + [(x0, WALL_TOP)]
    extrude(mb, poly, WALL_ZB, WALL_ZF, "mudBrick", back=False)
    # buttress towers (proud, taller, own merlons)
    for tx0, tx1 in ((-0.300, -0.236), (0.128, 0.192)):
        top = 0.248
        tp = [(tx0, 0.0), (tx1, 0.0)] + merlon_outline(tx0, tx1, top, step=0.0085)[::-1]
        extrude(mb, tp, WALL_ZF - 0.002, WALL_ZF + 0.012, "mudBrick", back=False)
        for h in (0.07, 0.14, 0.205):
            box(mb, tx0 + 0.006, tx1 - 0.006, h, h + 0.0035, WALL_ZF + 0.012, WALL_ZF + 0.0145, "mudBrick",
                skip=("back", "bottom"))
    # reed-mat courses: thin proud ledges along the wall
    for h in (0.052, 0.104, 0.156):
        segs = [(x0, -0.300), (-0.236, 0.128), (0.192, x1)]
        for a, b in segs:
            box(mb, a + 0.002, b - 0.002, h, h + 0.0026, WALL_ZF, WALL_ZF + 0.0022, "mudBrick", skip=("back", "bottom"))
    # brick patches (raised bricks, printed on the sheet)
    nb = blocks(mb, x1 - x0, [0.0118] * 18, lambda s, h, d: (x0 + s, h, WALL_ZF + d), rng, "mudBrick",
                holes=lambda h0, h1: [(-0.302 - x0, -0.234 - x0), (0.126 - x0, 0.194 - x0)],
                wmin=0.026, wmax=0.034, proud=(0.0010, 0.0018), g=0.0010, ch=0.0008, decor=dec,
                patch=lambda s, h: patchy((x0 + s) * 0.8, h * 0.9, 1.0, 0.62) and h < 0.200, only_patch=True)
    # beyond the wall: flat roofs, a ziggurat, two palms (flat reliefs standing on the wall's back half)
    zb = WALL_ZB + 0.0005
    for i, (bx, w, top) in enumerate(((-0.318, 0.078, 0.296), (-0.252, 0.075, 0.296), (0.100, 0.085, 0.296))):
        box(mb, bx, bx + w, WALL_TOP - 0.01, top, zb, zb + 0.012, "mudBrick", skip=("back", "bottom"))
        box(mb, bx - 0.002, bx + w + 0.002, top, top + 0.004, zb, zb + 0.0135, "mudBrick", skip=("back", "bottom"))
        if i % 2 == 0:
            box(mb, bx + w * 0.3, bx + w * 0.55, top - 0.026, top - 0.010, zb + 0.012, zb + 0.0128, "mudBrick",
                skip=("back", "bottom"))
    zc = -0.445
    for k, (hw, h0, h1) in enumerate(((0.120, 0.20, 0.236), (0.090, 0.236, 0.262), (0.060, 0.262, 0.284),
                                      (0.032, 0.284, 0.300))):
        box(mb, zc - hw, zc + hw, h0, h1, zb + 0.001 * k, zb + 0.010 + 0.001 * k, "ziggurat", skip=("back", "bottom"))
        box(mb, zc - hw - 0.001, zc + hw + 0.001, h1 - 0.003, h1, zb + 0.001 * k, zb + 0.0115 + 0.001 * k, "ziggurat",
            skip=("back", "bottom"))
        for x in np.linspace(zc - hw + 0.012, zc + hw - 0.012, max(2, int(hw / 0.02))):   # niches on each stage
            box(mb, x - 0.003, x + 0.003, h0 + 0.006, h1 - 0.007, zb + 0.010 + 0.001 * k, zb + 0.0112 + 0.001 * k,
                "ziggurat", skip=("back", "bottom"))
    box(mb, zc - 0.007, zc + 0.007, 0.20, 0.284, zb + 0.0135, zb + 0.018, "ziggurat", skip=("back", "bottom"))
    for (px, top) in ((-0.385, 0.300), (0.255, 0.296)):
        mb.nr = True
        tube(mb, [(px, WALL_TOP - 0.01, zb + 0.004), (px + 0.004, top - 0.02, zb + 0.004)], 0.004, "farTrunk", seg=5)
        mb.nr = False
        fr = []
        for k in range(7):
            a = math.radians(-15 + 210 * k / 6)
            fr += [(px + 0.004 + 0.012 * math.cos(a + 0.2), top - 0.022 + 0.008 * math.sin(a + 0.2)),
                   (px + 0.004 + 0.038 * math.cos(a), top - 0.026 + 0.026 * math.sin(a) - 0.010 * abs(math.cos(a)))]
        fr = [(x, max(h, top - 0.06)) for x, h in fr]
        fr = [(x, min(h, top)) for x, h in fr]
        mb.nr = True
        extrude(mb, fr, zb + 0.002, zb + 0.008, "palmFar", back=False)
        mb.nr = False
    wall = make_obj("cityWall", mb, root, origin=(0.0, 0.0, -0.574), smooth_angle=30)
    return wall, nb


def build_gate(parent):
    """the blue-glazed gate: two glazed wings, two towers, the gate face with an arched opening and studded wooden
    doors; gold trims, rosettes (a big one over the arch), a walking lion on each wing facing the gate"""
    mb = MB()
    rng = random.Random(41)
    dec = DECOR.setdefault("gate", [])
    zw, zt, zg = -0.5555, -0.5465, -0.551
    wings = ((GATE_X0, 0.287), (0.513, GATE_X1))
    for a, b in wings:
        poly = [(a, 0.0), (b, 0.0)] + merlon_outline(a, b, WALL_TOP)[::-1]
        extrude(mb, poly, WALL_ZB, zw, "gateTile", back=False)
    for a, b in ((0.283, 0.343), (0.457, 0.517)):
        poly = [(a, 0.0), (b, 0.0)] + merlon_outline(a, b, 0.266, step=0.009)[::-1]
        extrude(mb, poly, WALL_ZB, zt, "gateTile", back=False)
    gx0, gx1 = 0.343, 0.457
    GT = 0.238
    arc = lambda a0, a1, n: [(GATE_C + ARCH_HW * math.cos(a0 + (a1 - a0) * k / n),
                              ARCH_SPRING + ARCH_HW * math.sin(a0 + (a1 - a0) * k / n)) for k in range(n + 1)]
    left = [(gx0, 0.0), (GATE_C - ARCH_HW, 0.0)] + arc(math.pi, math.pi / 2, 6) + [(GATE_C, GT), (gx0, GT)]
    right = arc(math.pi / 2, 0.0, 6) + [(GATE_C + ARCH_HW, 0.0), (gx1, 0.0), (gx1, GT), (GATE_C, GT)]
    for half in (left, right):
        extrude(mb, half, WALL_ZB, zg, "gateTile", back=False)
    mtop = merlon_outline(gx0, gx1, GT, step=0.008)
    extrude(mb, [(gx0, GT - 0.003), (gx1, GT - 0.003)] + mtop[::-1], WALL_ZB, zg, "gateTile", back=False)
    # arch reveal and the doors (recessed)
    zd = zg - 0.012
    for k in range(12):
        a0, a1 = math.pi * k / 12, math.pi * (k + 1) / 12
        p0 = (GATE_C + ARCH_HW * math.cos(a0), ARCH_SPRING + ARCH_HW * math.sin(a0))
        p1 = (GATE_C + ARCH_HW * math.cos(a1), ARCH_SPRING + ARCH_HW * math.sin(a1))
        mb.fo([mb.v(p0[0], p0[1], zg), mb.v(p1[0], p1[1], zg), mb.v(p1[0], p1[1], zd), mb.v(p0[0], p0[1], zd)],
              "gateTile", (GATE_C - (p0[0] + p1[0]) / 2, ARCH_SPRING - (p0[1] + p1[1]) / 2, 0))
    for s in (-1, 1):
        x = GATE_C + s * ARCH_HW
        mb.fo([mb.v(x, 0, zg), mb.v(x, ARCH_SPRING, zg), mb.v(x, ARCH_SPRING, zd), mb.v(x, 0, zd)], "gateTile",
              (-s, 0, 0))
    extrude(mb, [(GATE_C - ARCH_HW, 0.0), (GATE_C + ARCH_HW, 0.0)] + arc(0.0, math.pi, 12)[1:-1],
            zd - 0.0005, zd, "gateDoor", back=False)
    for s in (-1, 1):                                   # two door leaves: planks
        for i in range(3):
            xa = GATE_C + s * ARCH_HW * i / 3; xb = GATE_C + s * ARCH_HW * (i + 1) / 3
            xa, xb = min(xa, xb) + 0.0005, max(xa, xb) - 0.0005
            top = lambda x: ARCH_SPRING + math.sqrt(max(0.0, ARCH_HW ** 2 - (x - GATE_C) ** 2))
            poly = [(xa, 0.0), (xb, 0.0)] + [(x, top(x) - 0.0004) for x in np.linspace(xb, xa, 4)]
            extrude(mb, poly, zd, zd + 0.003 + 0.0005 * i, "gateDoor", back=False)
        for hb in (0.03, 0.075, 0.115):
            xa, xb = sorted((GATE_C + s * 0.003, GATE_C + s * (ARCH_HW - 0.003)))
            if hb > ARCH_SPRING:
                xb2 = math.sqrt(max(0.0, ARCH_HW ** 2 - (hb - ARCH_SPRING + 0.004) ** 2)) - 0.003
                xa, xb = sorted((GATE_C + s * 0.003, GATE_C + s * xb2))
            box(mb, xa, xb, hb - 0.003, hb + 0.003, zd + 0.003, zd + 0.0052, "gateDoor", skip=("back",))
            mb.nr = True
            for x in np.linspace(xa + 0.004, xb - 0.004, 3):
                sphere(mb, (x, hb, zd + 0.0058), 0.0016, "stud", seg=6, rings=3)
            mb.nr = False
    # gold arch frame of glazed bricks
    for k in range(13):
        a0 = math.pi * k / 13 + 0.01; a1 = math.pi * (k + 1) / 13 - 0.01
        r0, r1 = ARCH_HW + 0.0015, ARCH_HW + 0.0105
        poly = [(GATE_C + r0 * math.cos(a0), ARCH_SPRING + r0 * math.sin(a0)),
                (GATE_C + r1 * math.cos(a0), ARCH_SPRING + r1 * math.sin(a0)),
                (GATE_C + r1 * math.cos(a1), ARCH_SPRING + r1 * math.sin(a1)),
                (GATE_C + r0 * math.cos(a1), ARCH_SPRING + r0 * math.sin(a1))][::-1]
        extrude(mb, poly, zg, zg + 0.003, "relief", back=False)
    for s in (-1, 1):
        x = GATE_C + s * ARCH_HW
        box(mb, min(x, x + s * 0.0105), max(x, x + s * 0.0105), 0.0, ARCH_SPRING, zg, zg + 0.003, "relief",
            skip=("back", "bottom"))
    # gold trims (bands) on wings, towers and face
    for a, b, z in ((GATE_X0, 0.283, zw), (0.517, GATE_X1, zw), (0.283, 0.343, zt), (0.457, 0.517, zt)):
        for h in (0.092, 0.172):
            box(mb, a + 0.001, b - 0.001, h, h + 0.0055, z, z + 0.0028, "relief", skip=("back", "bottom"))
    box(mb, gx0 + 0.002, gx1 - 0.002, 0.226, 0.232, zg, zg + 0.0028, "relief", skip=("back", "bottom"))
    # walking lions on the wings, facing the gate
    for a, b, face in ((GATE_X0, 0.283, 1), (0.517, GATE_X1, -1)):
        Lw = 0.068
        cx = (a + b) / 2
        X = lambda u, v, cx=cx, face=face: (cx + face * (u - 0.5) * Lw, 0.104 + v * Lw)
        puff(mb, LION_SIDE, zw + 0.0022, 0.0022, "relief", X=X, rad=0.004, step=0.0028)
        # mane ruff: a second puff a little prouder
        mane = [(0.60, 0.48), (0.64, 0.30), (0.74, 0.24), (0.83, 0.30), (0.88, 0.42), (0.86, 0.56), (0.80, 0.66),
                (0.70, 0.66), (0.63, 0.58)]
        puff(mb, mane[::face], zw + 0.0046, 0.0012, "relief", X=X, rad=0.003, step=0.0028)
    # rosettes
    for x, z in ((0.313, zt), (0.487, zt)):
        rosette(mb, x, 0.132, z, 0.018)
        rosette(mb, x, 0.214, z, 0.016)
    for a, b in ((GATE_X0, 0.283), (0.517, GATE_X1)):
        for x in np.linspace(a + 0.018, b - 0.018, 3):
            rosette(mb, x, 0.194, zw, 0.0105)
    rosette(mb, GATE_C, 0.1885, zg, 0.033, fat=True)
    for x in (gx0 + 0.015, gx1 - 0.015):
        rosette(mb, x, 0.190, zg, 0.0105)
    # glazed brick patches
    nb = 0
    for a, b, z in ((GATE_X0, 0.283, zw), (0.517, GATE_X1, zw), (0.283, 0.343, zt), (0.457, 0.517, zt)):
        nb += blocks(mb, b - a, [0.0115] * 8, lambda s, h, d, a=a, z=z: (a + s, h, z + d), rng, "gateTile",
                     wmin=0.022, wmax=0.030, proud=(0.0008, 0.0014), g=0.0009, ch=0.0006, decor=dec,
                     patch=lambda s, h, a=a: patchy((a + s) * 1.1, h * 1.3, 4.0, 0.55), only_patch=True)
    g = make_obj("gate", mb, parent, origin=(GATE_C, 0.0, zg), smooth_angle=35)
    return g, nb


# ============================================================================================ palace
def build_palace(root):
    """the palace front: façade with pilasters, stepped merlons and a blue rosette frieze, the royal backdrop panel,
    the dais (platform + three steps), two columns with palm-leaf capitals, a sagging red canopy with a scalloped
    valance and gold tassels, incense stands, two jars and two pole torches. Children: throne, torch (empty)."""
    mb = MB()
    rng = random.Random(51)
    fz0, fz1 = PAL_FACADE_Z
    fx0, fx1 = -0.175, 0.175
    poly = [(fx0, 0.0), (fx1, 0.0)] + merlon_outline(fx0, fx1, 0.322, step=0.0080)[::-1]
    extrude(mb, poly, fz0, fz1, "palaceWall", back=False)
    for s in (-1, 1):                                   # corner pilasters
        a, b = sorted((s * 0.175, s * 0.152))
        box(mb, a, b, 0.0, 0.324, fz1, fz1 + 0.006, "palaceWall", skip=("back", "bottom"))
    for x in (-0.105, 0.105):                           # recessed panels between pilasters (proud frames)
        for s in (-1, 1):
            box(mb, x + s * 0.034 - 0.003, x + s * 0.034 + 0.003, 0.05, 0.18, fz1, fz1 + 0.0035, "palaceWall",
                skip=("back", "bottom"))
        box(mb, x - 0.037, x + 0.037, 0.177, 0.183, fz1, fz1 + 0.0035, "palaceWall", skip=("back", "bottom"))
    # blue frieze with gold rosettes: glazed tiles like the gate's, so they wear the gate's colours (not printed)
    mb.nr = True
    box(mb, fx0 + 0.023, fx1 - 0.023, 0.192, 0.240, fz1, fz1 + 0.004, "friezeTile", skip=("back", "bottom"))
    for x in np.linspace(fx0 + 0.045, fx1 - 0.045, 6):
        rosette(mb, float(x), 0.216, fz1 + 0.004, 0.0135, reg="friezeGold")
    mb.nr = False
    # royal backdrop panel (arched, gilded) with a sun rosette
    pw, ps = 0.056, 0.140
    pan = [(-pw, 0.04), (pw, 0.04)] + [(pw * math.cos(math.pi * k / 12), ps + pw * math.sin(math.pi * k / 12))
                                       for k in range(13)]
    extrude(mb, pan, fz1, fz1 + 0.004, "throne", back=False)            # gilded, one gold with the throne
    rosette(mb, 0.0, 0.150, fz1 + 0.004, 0.028, reg="throne")
    # platform + steps
    x0, x1, zb, zf, top = PLAT
    cbox(mb, x0, x1, 0.0, top, zb, zf, "sandstone", c=0.002)
    dec = DECOR.setdefault("palace", [])
    for i, (h, z0) in enumerate(((top * 2 / 3, zf), (top / 3, zf + 0.016))):
        cbox(mb, -STEPS_HW, STEPS_HW, 0.0, h, zf - 0.002, z0 + 0.016 if i == 0 else STEP_FRONT, "sandstone", c=0.0015)
    for x in np.linspace(x0 + 0.04, x1 - 0.04, 6):     # carved panels on the platform front (beside the steps)
        if abs(x) > STEPS_HW + 0.01:
            dec.append(((x, 0.008, zf), (x, 0.032, zf)))
    # columns: base, shaft with entasis and rings, palm-leaf capital, abacus
    for cx, cz in COLS:
        lathe(mb, [(0.0, top), (0.019, top), (0.019, top + 0.004), (0.016, top + 0.009), (0.0125, top + 0.013)],
              "sandstone", C=(cx, 0, cz), seg=14)
        prof = [(0.0125, top + 0.013), (0.0118, 0.12), (0.0108, 0.226), (0.0122, 0.228), (0.0122, 0.233),
                (0.0105, 0.235)]
        lathe(mb, prof, "sandstone", C=(cx, 0, cz), seg=12)
        for k in range(10):                            # palm leaves flaring out
            a = TAU * k / 10 + 0.15
            d = Vector((math.cos(a), 0, math.sin(a)))
            p0 = Vector((cx, 0.234, cz)) + d * 0.008
            pts = [tuple(p0), tuple(p0 + d * 0.007 + Vector((0, 0.013, 0))),
                   tuple(p0 + d * 0.016 + Vector((0, 0.027, 0))), tuple(p0 + d * 0.021 + Vector((0, 0.031, 0)))]
            blade(mb, pts, [0.009, 0.011, 0.009, 0.004], "sandstone", nrm=(d.x, 0, d.z))
        lathe(mb, [(0.0, 0.234), (0.009, 0.234), (0.011, 0.25), (0.0, 0.252)], "sandstone", C=(cx, 0, cz), seg=10)
        cbox(mb, cx - 0.022, cx + 0.022, 0.262, COL_TOP, cz - 0.022, cz + 0.022, "sandstone", c=0.0015)
    # entablature over the columns: a blue-tiled frieze with gold trims and rosettes
    ez = COLS[0][1]
    mb.nr = True                                       # glazed like the gate: wears the gate's tile and gold texels
    cbox(mb, -0.162, 0.162, COL_TOP, COL_TOP + 0.036, ez - 0.009, ez + 0.009, "friezeTile", c=0.0015)
    for hh in (COL_TOP + 0.002, COL_TOP + 0.031):
        box(mb, -0.160, 0.160, hh, hh + 0.0035, ez + 0.009, ez + 0.0115, "friezeGold", skip=("back", "bottom"))
    for x in np.linspace(-0.130, 0.130, 6):
        if abs(x) > 0.03:
            rosette(mb, float(x), COL_TOP + 0.0185, ez + 0.009, 0.0105, reg="friezeGold")
    mb.nr = False
    # crest: a winged sun disc standing on the entablature (gilded: printed as one gold region with the throne)
    sc_h = COL_TOP + 0.040
    wing = [(0.0, -0.004), (0.020, -0.006), (0.050, 0.000), (0.074, 0.010), (0.064, 0.014), (0.068, 0.018),
            (0.056, 0.020), (0.058, 0.025), (0.044, 0.024), (0.030, 0.018), (0.0, 0.016)]
    for sgn in (-1, 1):
        puff(mb, [(sgn * x, sc_h + 0.004 + y) for x, y in wing], ez + 0.004, 0.003, "throne", rad=0.004, step=0.004)
    disc = [(0.034 * math.cos(TAU * k / 28), sc_h + 0.030 + 0.034 * math.sin(TAU * k / 28)) for k in range(28)]
    puff(mb, disc, ez + 0.006, 0.004, "throne", rad=0.006, step=0.004)     # one gold with the throne
    # canopy: cloth sagging between the front beam and the façade, scalloped valance on the front and sides
    cx0, cx1, cz0, cz1 = -0.157, 0.157, fz1 + 0.001, COLS[0][1] - 0.009
    NX, NZ = 14, 7
    hf = lambda x, z: (COL_TOP + 0.037 + 0.022 * (z - cz1) / (cz0 - cz1)
                       - 0.008 * math.sin(math.pi * (x - cx0) / (cx1 - cx0)) * (0.35 + 0.65 * math.sin(
                           math.pi * (z - cz0) / (cz1 - cz0))))
    grid = [[mb.v(cx0 + (cx1 - cx0) * i / NX, hf(cx0 + (cx1 - cx0) * i / NX, cz0 + (cz1 - cz0) * j / NZ),
                  cz0 + (cz1 - cz0) * j / NZ) for j in range(NZ + 1)] for i in range(NX + 1)]
    for i in range(NX):
        for j in range(NZ):
            mb.fo([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], "canopy", UP, True)
            mb.fo([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]], "canopy", (0, -1, 0), True)
    tassels = []

    def valance(p0, p1, n, out):
        for k in range(n):
            a = Vector(p0) + (Vector(p1) - Vector(p0)) * (k / n)
            b = Vector(p0) + (Vector(p1) - Vector(p0)) * ((k + 1) / n)
            m = (a + b) / 2
            pts = [a, b, b - Vector((0, 0.010, 0)), m - Vector((0, 0.020, 0)), a - Vector((0, 0.010, 0))]
            ids = [mb.v(*p) for p in pts]
            mb.fo(ids, "canopy", out, True)
            mb.fo(ids, "canopy", tuple(-c for c in out), True)
            tassels.append(m - Vector((0, 0.021, 0)))
    for s, xx in ((-1, cx0), (1, cx1)):
        valance((xx - s * 0.0005, hf(xx, cz1), cz1), (xx - s * 0.0005, hf(xx, cz0), cz0 + 0.004), 5, (s, 0, 0))
    mb.nr = True
    for t in tassels:
        sphere(mb, tuple(t), 0.0028, "tassel", seg=6, rings=4, sh=1.4)
    # incense stands and jars on the platform
    for sx in (-1, 1):
        x, z = sx * 0.098, -0.462
        lathe(mb, [(0.0, top), (0.010, top), (0.004, top + 0.006), (0.0028, top + 0.050), (0.009, top + 0.056),
                   (0.0105, top + 0.064), (0.0, top + 0.061)], "incense", C=(x, 0, z), seg=10)
        x, z = sx * 0.148, -0.522
        prof = [(0.0, top), (0.007, top), (0.013, top + 0.010), (0.0155, top + 0.022), (0.012, top + 0.036),
                (0.0065, top + 0.042), (0.0075, top + 0.046), (0.0, top + 0.044)]
        lathe(mb, prof, "jar", C=(x, 0, z), seg=12)
    # pole torches beside the steps (the left one's flame point is the `torch` empty)
    for (tx, tz) in (TORCH, TORCH2):
        lathe(mb, [(0.0, 0.0), (0.009, 0.0), (0.009, 0.005), (0.004, 0.009), (0.0, 0.0095)], "torchBowl",
              C=(tx, 0, tz), seg=8)
        tube(mb, [(tx, 0.008, tz), (tx, TORCH_H - 0.004, tz)], 0.0032, "torchPole", seg=6)
        lathe(mb, [(0.0, TORCH_H - 0.006), (0.006, TORCH_H - 0.005), (0.013, TORCH_H + 0.006), (0.0145, TORCH_H + 0.012),
                   (0.012, TORCH_H + 0.013), (0.0, TORCH_H + 0.009)], "torchBowl", C=(tx, 0, tz), seg=10)
    mb.nr = False
    pal = make_obj("palace", mb, root, origin=(0.0, 0.0, -0.46), smooth_angle=40)
    torch = empty("torch", (TORCH[0], TORCH_H + 0.018, TORCH[1]), pal)
    return pal, torch


def build_throne(parent):
    """carved throne: lion-paw legs, seat with a red cushion, a tall back with a rounded crest and a red panel,
    arms ending in lion heads (round muzzle, mane ruff), a footstool"""
    mb = MB()
    tx, tz = THRONE
    top = PLAT[4]
    w, d = 0.040, 0.026
    for sx in (-1, 1):
        for sz in (-1, 1):
            x, z = tx + sx * (w - 0.006), tz + sz * (d - 0.006)
            lathe(mb, [(0.0, top), (0.0072, top), (0.0078, top + 0.004), (0.0055, top + 0.010), (0.0045, top + 0.040),
                       (0.0, top + 0.041)], "throne", C=(x, 0, z), seg=8)
            sphere(mb, (x, top + 0.004, z + 0.004), 0.0058, "throne", seg=8, rings=4, sh=0.7, sz=1.2)
    cbox(mb, tx - w, tx + w, top + 0.036, top + 0.048, tz - d, tz + d, "throne", c=0.0015)
    cbox(mb, tx - w + 0.006, tx + w - 0.006, top + 0.048, top + 0.056, tz - d + 0.004, tz + d - 0.004, "cushion",
         c=0.003)
    # back: panel with a rounded crest
    bz0, bz1 = tz - d, tz - d + 0.010
    back = [(-w, top + 0.04), (w, top + 0.04), (w, top + 0.132)] + \
        [(w * 1.12 * math.cos(math.pi * k / 12), top + 0.132 + 0.046 * math.sin(math.pi * k / 12)) for k in range(13)] + \
        [(-w, top + 0.132)]
    extrude(mb, back, bz0, bz1, "throne", X=lambda a, b: (tx + a, b), back=True)
    cp = [(-0.029, top + 0.058), (0.029, top + 0.058), (0.029, top + 0.100)] + \
        [(0.029 * math.cos(math.pi * k / 8), top + 0.100 + 0.008 * math.sin(math.pi * k / 8)) for k in range(9)]
    puff(mb, cp, bz1 + 0.0035, 0.0035, "cushion", X=lambda a, b: (tx + a, b), rad=0.005, step=0.004)
    sphere(mb, (tx, top + 0.182, bz0 + 0.005), 0.007, "throne", seg=8, rings=5)
    # arms with lion-head ends
    for sx in (-1, 1):
        x = tx + sx * (w - 0.004)
        box(mb, x - 0.005, x + 0.005, top + 0.048, top + 0.082, tz - d + 0.008, tz + d - 0.004, "throne")
        cbox(mb, x - 0.0065, x + 0.0065, top + 0.082, top + 0.089, tz - d + 0.006, tz + d - 0.002, "throne", c=0.002)
        hz = tz + d + 0.004
        lumpy(mb, (x, top + 0.092, hz), 0.010, "throne", seg=10, rings=6, sz=0.7, amp=0.18, seed=sx)
        sphere(mb, (x, top + 0.089, hz + 0.007), 0.0055, "throne", seg=8, rings=5, sz=0.9)
    # footstool
    cbox(mb, tx - 0.026, tx + 0.026, top, top + 0.013, tz + d + 0.010, tz + d + 0.034, "throne", c=0.002)
    S = 1.28
    for L in (mb.V, mb.P):
        for i, (x, h, z) in enumerate(L):
            L[i] = (tx + (x - tx) * S, top + (h - top) * S, tz + (z - tz) * S)
    return make_obj("throne", mb, parent, origin=(tx, top, tz), smooth_angle=40)


# ============================================================================================ house
def arch_outline(cx, half, h0, spring, n=8):
    return [(cx - half, h0), (cx + half, h0)] + [(cx + half * math.cos(math.pi * k / n),
                                                 spring + half * math.sin(math.pi * k / n)) for k in range(n + 1)]


def build_house(root):
    """Daniel's two-storey mud-brick house: lower storey with an arched plank door and a shuttered window, upper
    storey with a terrace door and windows, parapet, beam ends, the outside stair up the right side, a wooden balcony
    rail round the terrace, a striped cloth over the rail, plant pots and jars"""
    mb = MB()
    rng = random.Random(61)
    dec = DECOR.setdefault("house", [])
    x0, x1, zb, zf = HOUSE
    ux0, ux1, uzb, uzf = UPPER
    H1, H2 = HOUSE_H1, HOUSE_H2
    door = arch_outline(-0.475, 0.029, 0.0, 0.066)
    win1 = [(-0.400, 0.052), (-0.366, 0.052), (-0.366, 0.090), (-0.400, 0.090)]
    extrude(mb, [(x0, 0.0), (x1, 0.0), (x1, H1), (x0, H1)], zf - 0.0005, zf, "houseWall", back=False,
            holes=[door, win1])
    # lower storey: right side and left side
    for x, o in ((x1, 1), (x0, -1)):
        mb.fo([mb.v(x, 0, zb), mb.v(x, 0, zf), mb.v(x, H1, zf), mb.v(x, H1, zb)], "houseWall", (o, 0, 0))
    # terrace floor (L shape) and upper storey
    ngon_top(mb, [(x0, uzf), (ux1, uzf), (ux1, zb), (x1, zb), (x1, zf), (x0, zf)], H1, "roof")
    udoor = arch_outline(-0.455, 0.018, H1, H1 + 0.062)
    uwin = [(-0.535, H1 + 0.040), (-0.505, H1 + 0.040), (-0.505, H1 + 0.082), (-0.535, H1 + 0.082)]
    extrude(mb, [(ux0, H1), (ux1, H1), (ux1, H2), (ux0, H2)], uzf - 0.0005, uzf, "houseWall", back=False,
            holes=[udoor, uwin])
    mb.fo([mb.v(ux1, H1, uzf), mb.v(ux1, H1, uzb), mb.v(ux1, H2, uzb), mb.v(ux1, H2, uzf)], "houseWall", (1, 0, 0))
    mb.fo([mb.v(ux0, H1, uzf), mb.v(ux0, H1, uzb), mb.v(ux0, H2, uzb), mb.v(ux0, H2, uzf)], "houseWall", (-1, 0, 0))
    # upper roof inside a parapet
    PT, PH = 0.008, 0.016
    ngon_top(mb, [(ux0 + PT, uzf - PT), (ux1 - PT, uzf - PT), (ux1 - PT, uzb), (ux0 + PT, uzb)], H2 - 0.002, "roof")
    for (ax0, ax1, az0, az1) in ((ux0 - 0.002, ux1 + 0.002, uzf - PT, uzf + 0.002), (ux0 - 0.002, ux0 + PT, uzb, uzf),
                                 (ux1 - PT, ux1 + 0.002, uzb, uzf)):
        cbox(mb, ax0, ax1, H2 - 0.004, H2 + PH, az0, az1, "houseWall", c=0.0015)
    for x in (ux0 + 0.006, ux1 - 0.006):                 # corner horns on the parapet
        cbox(mb, x - 0.006, x + 0.006, H2 + PH, H2 + PH + 0.008, uzf - 0.006, uzf + 0.002, "houseWall", c=0.002)
    # door / windows: reveals, lintels, sills, the doors and shutters (wood)
    for hole, zz in ((door, zf), (win1, zf), (udoor, uzf), (uwin, uzf)):
        n = len(hole)
        area = sum(hole[i][0] * hole[(i + 1) % n][1] - hole[(i + 1) % n][0] * hole[i][1] for i in range(n))
        for i in range(n):
            a, b = hole[i], hole[(i + 1) % n]
            if a[1] == b[1] and a[1] in (0.0, H1):
                continue
            dx, dh = b[0] - a[0], b[1] - a[1]
            o = (-dh, dx) if area > 0 else (dh, -dx)
            mb.fo([mb.v(a[0], a[1], zz), mb.v(b[0], b[1], zz), mb.v(b[0], b[1], zz - 0.010),
                   mb.v(a[0], a[1], zz - 0.010)], "houseWall", (o[0], o[1], 0))
    for (dx_, half, h0, spring, zz) in ((-0.475, 0.029, 0.0, 0.066, zf), (-0.455, 0.018, H1, H1 + 0.062, uzf)):
        top = lambda x: spring + math.sqrt(max(0.0, half ** 2 - (x - dx_) ** 2))
        extrude(mb, arch_outline(dx_, half, h0, spring), zz - 0.0105, zz - 0.0100, "wood", back=False)
        xs = np.linspace(dx_ - half, dx_ + half, 5)
        for i in range(4):
            poly = [(xs[i] + 0.0004, h0), (xs[i + 1] - 0.0004, h0)] + \
                [(x, top(x) - 0.0004) for x in np.linspace(xs[i + 1] - 0.0004, xs[i] + 0.0004, 4)]
            extrude(mb, poly, zz - 0.010, zz - 0.007 + 0.0006 * (i % 2), "wood", back=False)
        for hb in (h0 + 0.018, h0 + 0.052):
            box(mb, dx_ - half + 0.004, dx_ + half - 0.004, hb - 0.003, hb + 0.003, zz - 0.007, zz - 0.0045, "wood",
                skip=("back",))
        mb.nr = True
        tube(mb, [(dx_ + half * 0.55 + 0.004 * math.cos(TAU * k / 10), h0 + 0.036 + 0.004 * math.sin(TAU * k / 10),
                   zz - 0.0042) for k in range(10)], 0.0009, "iron", seg=4, closed=True, ref=(0, 0, 1))
        mb.nr = False
        box(mb, dx_ - half - 0.004, dx_ + half + 0.004, 0.0 if h0 == 0 else h0, (0.0 if h0 == 0 else h0) + 0.004,
            zz - 0.010, zz + 0.006, "houseWall", skip=("bottom",))
    for (wx0, wx1, h0, h1, zz) in ((-0.400, -0.366, 0.052, 0.090, zf), (-0.535, -0.505, H1 + 0.040, H1 + 0.082, uzf)):
        for i, (a, b) in enumerate(((wx0, (wx0 + wx1) / 2), ((wx0 + wx1) / 2, wx1))):
            box(mb, a + 0.0005, b - 0.0005, h0 + 0.001, h1 - 0.001, zz - 0.008, zz - 0.005, "wood", skip=("back",))
            for hh in (h0 + (h1 - h0) * 0.3, h0 + (h1 - h0) * 0.7):
                box(mb, a + 0.002, b - 0.002, hh - 0.0015, hh + 0.0015, zz - 0.005, zz - 0.0038, "wood", skip=("back",))
        box(mb, wx0 - 0.005, wx1 + 0.005, h1, h1 + 0.006, zz, zz + 0.005, "wood", skip=("back",))
        box(mb, wx0 - 0.004, wx1 + 0.004, h0 - 0.004, h0, zz - 0.002, zz + 0.007, "houseWall", skip=("back",))
    # shuttered window on the upper storey's right face
    for i, (a, b) in enumerate(((-0.488, -0.470), (-0.470, -0.452))):
        box(mb, ux1, ux1 + 0.003, H1 + 0.042, H1 + 0.080, a, b, "wood", skip=("left",))
    box(mb, ux1, ux1 + 0.005, H1 + 0.080, H1 + 0.086, -0.492, -0.448, "wood", skip=("left",))
    # beam ends under both roof lines
    mb.nr = False
    for x in np.linspace(x0 + 0.015, x1 - 0.015, 8):
        if abs(x + 0.475) < 0.038 or -0.41 < x < -0.355:
            continue
        lathe(mb, [(0.0, 0.0), (0.0042, 0.0), (0.0042, 0.011), (0.0, 0.0115)], "wood",
              C=(x, H1 - 0.010, zf - 0.002), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=6)
    for x in np.linspace(ux0 + 0.013, ux1 - 0.013, 5):
        if abs(x + 0.455) < 0.026 or abs(x + 0.520) < 0.022:
            continue
        lathe(mb, [(0.0, 0.0), (0.0042, 0.0), (0.0042, 0.011), (0.0, 0.0115)], "wood",
              C=(x, H2 - 0.010, uzf - 0.002), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=6)
    for z in np.linspace(zb + 0.02, zf - 0.02, 5):
        lathe(mb, [(0.0, 0.0), (0.0042, 0.0), (0.0042, 0.011), (0.0, 0.0115)], "wood",
              C=(x1 - 0.002, H1 - 0.010, z), A=(1, 0, 0), U=(0, 0, 1), V=(0, 1, 0), seg=6)
    # outside stair up the right side, rising toward the back
    sx0, sx1 = STAIR_X
    n = 8
    zfoot, ztop = zf - 0.008, zb + 0.012
    for i in range(n):
        za = zfoot - (zfoot - ztop) * i / n
        zb_ = zfoot - (zfoot - ztop) * (i + 1) / n
        h = H1 * (i + 1) / n
        cbox(mb, sx0, sx1, 0.0, h, zb_, za, "houseWall", c=0.0012)
    box(mb, sx0, sx1, 0.0, H1, zb, ztop, "houseWall", skip=("left",))
    # balcony rail round the terrace: posts, top and middle rails
    rail = [((x0 + 0.004, zf - 0.003), (x1 - 0.002, zf - 0.003)), ((x1 - 0.003, zf - 0.003), (x1 - 0.003, -0.47))]
    for (ax, az), (bx, bz) in rail:
        xa_, xb_ = sorted((ax, bx)); za_, zb_ = sorted((az, bz))
        box(mb, xa_ - 0.002, xb_ + 0.002, H1, H1 + 0.030, za_ - 0.002, zb_ + 0.002, "wood", skip=("bottom",))
        cbox(mb, xa_ - 0.0035, xb_ + 0.0035, H1 + 0.030, H1 + 0.036, za_ - 0.0035, zb_ + 0.0035, "wood", c=0.0015)
        L = math.hypot(bx - ax, bz - az)
        k = max(2, int(L / 0.045))
        for i in range(k + 1):                         # posts standing proud of the panel
            px, pz = ax + (bx - ax) * i / k, az + (bz - az) * i / k
            box(mb, px - 0.003, px + 0.003, H1, H1 + 0.031, pz - 0.003, pz + 0.003, "wood", skip=("bottom",))
    # terrace things: water jar, two plant pots, a rolled mat; a striped cloth over the rail
    mb.nr = True
    for (px, pz, s) in ((-0.344, -0.372, 1.0), (-0.386, -0.362, 0.75)):
        prof = [(0.0, H1), (0.006 * s, H1), (0.010 * s, H1 + 0.016 * s), (0.008 * s, H1 + 0.022 * s), (0.0, H1 + 0.02 * s)]
        lathe(mb, prof, "pot", C=(px, 0, pz), seg=8)
        for k in range(6):
            a = TAU * k / 6
            d = (math.cos(a), math.sin(a))
            blade(mb, [(px, H1 + 0.019 * s, pz), (px + d[0] * 0.012 * s, H1 + 0.036 * s, pz + d[1] * 0.012 * s),
                       (px + d[0] * 0.019 * s, H1 + 0.032 * s, pz + d[1] * 0.019 * s)], [0.006 * s, 0.006 * s, 0.0],
                  "leaf", nrm=(d[0], 0, d[1]))
    prof = [(0.0, H1), (0.007, H1), (0.012, H1 + 0.012), (0.0125, H1 + 0.024), (0.008, H1 + 0.034), (0.0045, H1 + 0.036),
            (0.0055, H1 + 0.04), (0.0, H1 + 0.038)]
    lathe(mb, prof, "pot", C=(-0.343, 0, -0.420), seg=10)
    tube(mb, [(-0.40, H1 + 0.006, -0.380), (-0.40, H1 + 0.006, -0.355)], 0.0055, "clothBlue", seg=8)
    for k in range(5):                                   # cloth over the rail: stripes
        xa = -0.540 + 0.008 * k
        reg = "clothRed" if k % 2 == 0 else "clothBlue"
        pts = [(xa, H1 + 0.004, zf - 0.007), (xa, H1 + 0.036, zf - 0.004), (xa, H1 + 0.037, zf + 0.0015),
               (xa, H1 + 0.010, zf + 0.004)]
        for i in range(3):
            a, b = pts[i], pts[i + 1]
            mb.fo([mb.v(*a), mb.v(a[0] + 0.008, a[1], a[2]), mb.v(b[0] + 0.008, b[1], b[2]), mb.v(*b)], reg,
                  (0, 0.3, 1 if i > 0 else -1))
    # a water jar and a bench by the door
    prof = [(0.0, 0.0), (0.006, 0.0), (0.012, 0.012), (0.0135, 0.026), (0.009, 0.038), (0.0055, 0.041),
            (0.0065, 0.046), (0.0, 0.044)]
    lathe(mb, prof, "pot", C=(-0.432, 0, zf + 0.012), seg=10)
    mb.nr = False
    cbox(mb, -0.545, -0.505, 0.0, 0.016, zf + 0.002, zf + 0.016, "wood", c=0.0015)
    # brick patches on the front and right faces (printed)
    nb = blocks(mb, x1 - x0, [0.0115] * 10, lambda s, h, d: (x0 + s, h, zf + d), rng, "houseWall",
                holes=lambda h0, h1: [(-0.508 - x0, -0.442 - x0)] + ([(-0.405 - x0, -0.361 - x0)] if h1 > 0.047 and h0 < 0.095 else []),
                wmin=0.022, wmax=0.030, proud=(0.0008, 0.0013), g=0.0009, ch=0.0006, decor=dec,
                patch=lambda s, h: patchy((x0 + s) * 1.3, h * 1.1, 7.0, 0.62), only_patch=True)
    nb += blocks(mb, ux1 - ux0, [0.0115] * 10, lambda s, h, d: (ux0 + s, H1 + h, uzf + d), rng, "houseWall",
                 holes=lambda h0, h1: [(-0.476 - ux0, -0.434 - ux0)] + ([(-0.540 - ux0, -0.500 - ux0)] if h1 > 0.036 and h0 < 0.088 else []),
                 wmin=0.022, wmax=0.030, proud=(0.0008, 0.0013), g=0.0009, ch=0.0006, decor=dec,
                 patch=lambda s, h: patchy((ux0 + s) * 1.3, h * 1.1, 11.0, 0.62), only_patch=True)
    return make_obj("house", mb, root, origin=(-0.44, 0.0, -0.44), smooth_angle=40), nb


# ============================================================================================ window wall + rug
def build_window_wall(root):
    """a short mud-brick wall with pilasters, a coping, an arched window (frame, lattice of diagonal bars, open
    shutters on the inside, an inner sill with a little pot of flowers). `window` = empty at the window centre."""
    mb = MB()
    rng = random.Random(71)
    dec = DECOR.setdefault("windowWall", [])
    xa, xb = WWALL_X
    za, zb = WWALL_Z
    win = arch_outline(WIN_Z, WIN_HW, WIN_SILL, WIN_SPRING, n=10)
    # the wall as a side extrusion: polygon in (z, h), extruded along x (X maps (a, b) -> (x, h) with a = z)
    outline = [(za, 0.0), (zb, 0.0), (zb, WWALL_H), (za, WWALL_H)]
    wall = MB()
    extrude(wall, outline, xa, xb, "houseWall", back=True, holes=[win])
    swap = lambda p: (p[2], p[1], p[0])
    mb.add(wall, swap, world_p=True)
    for z0_, z1_ in ((za - 0.004, za + 0.016), (zb - 0.016, zb + 0.004)):          # pilasters
        cbox(mb, xa - 0.004, xb + 0.004, 0.0, WWALL_H + 0.010, z0_, z1_, "houseWall", c=0.0015)
    cbox(mb, xa - 0.003, xb + 0.003, WWALL_H, WWALL_H + 0.007, za, zb, "houseWall", c=0.0015)   # coping
    # inner sill, frame (wood) round the arch on the inner face
    cbox(mb, xb - 0.004, xb + 0.012, WIN_SILL - 0.006, WIN_SILL, WIN_Z - WIN_HW - 0.006, WIN_Z + WIN_HW + 0.006,
         "houseWall", c=0.0012)
    fr = MB()
    for k in range(10):
        a0, a1 = math.pi * k / 10, math.pi * (k + 1) / 10
        r0, r1 = WIN_HW, WIN_HW + 0.006
        poly = [(WIN_Z + r0 * math.cos(a0), WIN_SPRING + r0 * math.sin(a0)),
                (WIN_Z + r1 * math.cos(a0), WIN_SPRING + r1 * math.sin(a0)),
                (WIN_Z + r1 * math.cos(a1), WIN_SPRING + r1 * math.sin(a1)),
                (WIN_Z + r0 * math.cos(a1), WIN_SPRING + r0 * math.sin(a1))]
        extrude(fr, poly, -(xb + 0.003), -xb, "shutter", back=False)
    for s in (-1, 1):
        extrude(fr, [(WIN_Z + s * WIN_HW, WIN_SILL), (WIN_Z + s * (WIN_HW + 0.006), WIN_SILL),
                     (WIN_Z + s * (WIN_HW + 0.006), WIN_SPRING), (WIN_Z + s * WIN_HW, WIN_SPRING)], -(xb + 0.003),
                -xb, "shutter", back=False)
    mb.add(fr, lambda p: (-p[2], p[1], p[0]), world_p=True)
    # open shutters against the inner face, each with two panels
    for s in (-1, 1):
        z0_ = WIN_Z + s * (WIN_HW + 0.007)
        z1_ = z0_ + s * 0.043
        a, b = sorted((z0_, z1_))
        box(mb, xb + 0.0015, xb + 0.0045, WIN_SILL + 0.001, WIN_SPRING + 0.010, a, b, "shutter", skip=("left",))
        for hh in (WIN_SILL + 0.020, WIN_SILL + 0.048):
            box(mb, xb + 0.0045, xb + 0.0058, hh - 0.010, hh + 0.010, a + 0.004, b - 0.004, "shutter", skip=("left",))
    # lattice: diagonal bars inside the opening (not printed: they take the shutter texel)
    mb.nr = True
    xm = (xa + xb) / 2
    for k in range(-6, 7):
        for sgn in (-1, 1):
            pts = []
            for t in np.linspace(-0.08, 0.08, 20):
                z = WIN_Z + k * 0.0085 + t * sgn
                h = WIN_SILL + 0.035 + t
                if WIN_SILL < h < WIN_SPRING + math.sqrt(max(0.0, WIN_HW ** 2 - (z - WIN_Z) ** 2)) - 0.001 and \
                        abs(z - WIN_Z) < WIN_HW - 0.0005:
                    pts.append((xm, h, z))
            if len(pts) >= 2:
                a, b = pts[0], pts[-1]
                tube(mb, [a, b], 0.0009, "lattice", seg=4, caps=False)
    # flowers on the sill
    px, pz = xb + 0.006, WIN_Z + 0.017
    lathe(mb, [(0.0, WIN_SILL), (0.0045, WIN_SILL), (0.006, WIN_SILL + 0.010), (0.0, WIN_SILL + 0.009)], "pot",
          C=(px, 0, pz), seg=8)
    for k in range(5):
        a = TAU * k / 5
        d = (math.cos(a) * 0.006, math.sin(a) * 0.006)
        tube(mb, [(px, WIN_SILL + 0.009, pz), (px + d[0], WIN_SILL + 0.022, pz + d[1])], 0.0007, "leaf", seg=3)
        sphere(mb, (px + d[0], WIN_SILL + 0.023, pz + d[1]), 0.0028, "flower", seg=6, rings=3)
    mb.nr = False
    nb = blocks(mb, zb - za - 0.03, [0.0115] * 13, lambda s, h, d: (xb + d, h, zb - 0.015 - s), rng, "houseWall",
                holes=lambda h0, h1: [(zb - 0.015 - (WIN_Z + WIN_HW + 0.042), zb - 0.015 - (WIN_Z - WIN_HW - 0.042))]
                if h1 > WIN_SILL - 0.008 and h0 < WIN_SPRING + WIN_HW + 0.008 else [],
                wmin=0.022, wmax=0.030, proud=(0.0008, 0.0013), g=0.0009, ch=0.0006, decor=dec,
                patch=lambda s, h: patchy(s * 1.3, h * 1.2, 13.0, 0.5), only_patch=True)
    ob = make_obj("windowWall", mb, root, origin=(-0.54, 0.0, -0.14), smooth_angle=40)
    w = empty("window", (-0.54, 0.10, -0.14), ob)
    return ob, w, nb


def build_rug(root):
    """the woven prayer rug: blue border, red field, cream diamond medallion with blue heart, corner diamonds,
    a slight cloth wave and fringe tassels at both ends"""
    x0, x1, z0, z1 = RUG
    bw = 0.025
    cx, cz = (x0 + x1) / 2, (z0 + z1) / 2
    field = [(x0 + bw, z0 + bw), (x1 - bw, z0 + bw), (x1 - bw, z1 - bw), (x0 + bw, z1 - bw)]
    med = [(cx - 0.030, cz), (cx, cz - 0.018), (cx + 0.030, cz), (cx, cz + 0.018)]
    heart = [(cx - 0.004, cz), (cx, cz - 0.0025), (cx + 0.004, cz), (cx, cz + 0.0025)]
    outer = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    outl = [_resample(outer, 0.01), _resample(field, 0.01), _resample(med, 0.008)]
    verts, edges = [], []
    for ol in outl:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    for x in np.arange(x0 + 0.006, x1, 0.012):
        for z in np.arange(z0 + 0.006, z1, 0.012):
            if min(np.min(np.hypot(*(o - np.array([x, z])).T)) for o in outl) > 0.004:
                verts.append(Vector((float(x), float(z))))
    vs, es, fs, *_ = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])
    mb = MB()
    hf = lambda x, z: 0.0042 + 0.0009 * math.sin(40 * x + 3) * math.sin(31 * z + 1)
    ids = [mb.v(x, hf(x, z), z) for x, z in V]
    for f in fs:
        if len(f) != 3:
            continue
        c = tuple(V[list(f)].mean(0))
        if in_poly(c, med):
            reg = "rugCream"
        elif in_poly(c, field):
            reg = "rugRed"
        else:
            reg = "rugBlue"
        mb.fo([ids[i] for i in f], reg, UP, True)
    for (ax, az), (bx, bz) in zip(outer, outer[1:] + outer[:1]):        # rug edge
        n = int(math.hypot(bx - ax, bz - az) / 0.01) + 1
        for i in range(n):
            pa = (ax + (bx - ax) * i / n, az + (bz - az) * i / n); pb = (ax + (bx - ax) * (i + 1) / n, az + (bz - az) * (i + 1) / n)
            mb.fo([mb.v(pa[0], hf(*pa), pa[1]), mb.v(pb[0], hf(*pb), pb[1]), mb.v(pb[0], 0.0028, pb[1]),
                   mb.v(pa[0], 0.0028, pa[1])], "rugBlue", ((pa[0] + pb[0]) / 2 - cx, 0, (pa[1] + pb[1]) / 2 - cz))
    mb.nr = True
    for xe, s in ((x0, -1), (x1, 1)):
        for z in np.linspace(z0 + 0.005, z1 - 0.005, 10):
            blade(mb, [(xe, 0.0036, z), (xe + s * 0.008, 0.0033, z + 0.001 * math.sin(z * 300))], [0.0028, 0.0012],
                  "fringe", nrm=(0, 1, 0))
    mb.nr = False
    return make_obj("rug", mb, root, origin=(-0.44, 0.0, -0.14), smooth_angle=50)


# ============================================================================================ palms
def palm_template(seed=3):
    """one date palm in template coords (foot at the origin): a gently curved trunk of stacked leaf-base rings, a
    crown boss, 13 pinnate fronds (rising, level and drooping), three date clusters"""
    mb = MB()
    H = 0.405
    axis = lambda u: (0.030 * u * u - 0.004 * math.sin(math.pi * u), H * u, 0.004 * math.sin(2.2 * u))
    n = 30
    for i in range(n):
        u0, u1 = i / n, (i + 1) / n
        c0, c1 = Vector(axis(u0)), Vector(axis(u1))
        r0 = 0.038 * (1 - 0.22 * u0)
        r1 = 0.038 * (1 - 0.22 * u1)
        lathe(mb, [(r0 * 0.92, 0.0), (r0 * 1.04, (c1.y - c0.y) * 0.6), (r1 * 0.92, c1.y - c0.y)],
              "trunk", C=tuple(c0), seg=9, smooth=False, phase=(i % 2) * math.pi / 9,
              rfun=lambda th, ii, k: 1.0 + 0.08 * ((k % 2) - 0.5) * (1 if ii == 1 else 0))
    top = Vector(axis(1.0))
    lumpy(mb, tuple(top + Vector((0, 0.004, 0))), 0.047, "frond", seg=10, rings=6, sh=0.8, amp=0.18, seed=seed)
    rng = random.Random(seed)
    fronds = []
    for k in range(13):
        a = TAU * k / 13 + rng.uniform(-0.15, 0.15)
        kind = k % 3                                  # 0 rising, 1 level, 2 drooping
        L = rng.uniform(0.128, 0.150)
        rise = (0.050, 0.030, 0.022)[kind]
        droop = (0.028, 0.058, 0.088)[kind]
        fronds.append((a, L, rise, droop))
    for a, L, rise, droop in fronds:
        d = Vector((math.cos(a), 0, math.sin(a)))
        side = Vector((-math.sin(a), 0, math.cos(a)))
        pts = []
        for j in range(11):
            s = j / 10
            pts.append(top + d * (0.012 + L * s) + Vector((0, rise * math.sin(math.pi * s * 0.75) - droop * s * s, 0)))
        tube(mb, [tuple(p) for p in pts[:6]], [0.0022, 0.002, 0.0018, 0.0015, 0.0012, 0.001], "frond", seg=4)
        for sg in (-1, 1):                                    # leaflets: one serrated ribbon each side
            edge = []
            for j in range(1, 11):
                s = j / 10
                w = 0.036 * math.sin(math.pi * min(1.0, s * 1.08)) ** 0.6 * (1.0 if j % 2 else 0.72)
                edge.append(pts[j] + side * sg * w + Vector((0, -0.009 - 0.007 * s, 0)) + d * 0.006)
            for j in range(1, 10):
                ids = [mb.v(*pts[j]), mb.v(*pts[j + 1]), mb.v(*edge[j]), mb.v(*edge[j - 1])]
                nrm = side.cross(pts[j + 1] - pts[j]) * sg
                mb.fo(ids, "frond", tuple(nrm))
                mb.fo(ids, "frond", tuple(-nrm))
    mb.nr = True
    for k in range(3):
        a = TAU * k / 3 + 0.5
        d = Vector((math.cos(a), 0, math.sin(a)))
        c = top + d * 0.020 + Vector((0, -0.022, 0))
        tube(mb, [tuple(top + d * 0.008), tuple(c + Vector((0, 0.008, 0)))], 0.0018, "dateStalk", seg=4)
        lumpy(mb, tuple(c), 0.011, "date", seg=8, rings=5, sh=1.3, amp=0.3, seed=k + 9)
    mb.nr = False
    return mb, top


def build_palms(root):
    """the main date palm (the official hides behind it) and two palms flanking the palace, all instances of one
    template (one drawing on the sheet). The main palm's yaw is chosen so that no frond hangs into a walk."""
    tpl, top = palm_template()
    TV = np.array(tpl.V)

    def violations(fn):
        P = np.array([fn(tuple(v)) for v in TV])
        bad = 0
        for who, a, b, _, _ in PATHS:
            Hh = HEIGHT.get(who, 0.35) + 0.04
            sel = (P[:, 1] > 0.012) & (P[:, 1] < Hh)
            if not sel.any():
                continue
            Q = P[sel]
            ax, az = a; bx, bz = b
            dx, dz = bx - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
            t = np.clip(((Q[:, 0] - ax) * dx + (Q[:, 2] - az) * dz) / L2, 0, 1)
            dd = np.hypot(Q[:, 0] - ax - t * dx, Q[:, 2] - az - t * dz)
            lim = np.where(Q[:, 1] < 0.17, 0.05, 0.035)
            bad += int((dd < lim).sum())
        for who, (x, z) in CONTRACT_MARKS:
            Hh = HEIGHT.get(who, 0.35) + 0.04
            sel = (P[:, 1] > 0.012) & (P[:, 1] < Hh)
            dd = np.hypot(P[sel, 0] - x, P[sel, 2] - z)
            lim = np.where(P[sel, 1] < 0.17, 0.05, 0.035)
            bad += int((dd < lim).sum())
        return bad
    best = None
    for sc in (1.0, 1.04, 1.08, 1.12, 1.16, 1.20, 1.24, 1.28):
        for yd in range(0, 360, 6):
            fn = yaw_fn(PALM_MAIN[0], PALM_MAIN[1], math.radians(yd), s=sc, sxz=PALM_SXZ)
            v = violations(fn)
            if best is None or v < best[0]:
                best = (v, yd, sc)
        if best[0] == 0:
            break
    mb = MB()
    mb.add(tpl, yaw_fn(PALM_MAIN[0], PALM_MAIN[1], math.radians(best[1]), s=best[2], sxz=PALM_SXZ))
    for i, (x, z, s) in enumerate(PALMS_SIDE):
        mb.add(tpl, yaw_fn(x, z, math.radians(70 + 110 * i), s=s, sxz=PALM_SXZ))
    ob = make_obj("palm", mb, root, origin=(PALM_MAIN[0], 0.0, PALM_MAIN[1]), smooth_angle=60)
    return ob, tpl, {"mainYawDeg": best[1], "mainScale": best[2], "mainViolations": best[0],
                     "crownBottomMain": round(best[2] * min(v[1] for v in tpl.V if v[1] > 0.30), 4)}


# ============================================================================================ den + stones
def sector_slab(mb, ta, tb, r0f, r1f, h0, h1, reg, ch=0.0018, n=4):
    """an annular-sector slab (coping stone) with a chamfered top"""
    ths = np.linspace(ta, tb, n + 1)
    outer = [den_pt(t, r1f(t)) for t in ths]
    inner = [den_pt(t, r0f(t)) for t in ths[::-1]]
    poly = outer + inner
    cxz = np.mean(poly, axis=0)
    ins = [tuple(np.array(p) + (cxz - np.array(p)) / max(np.linalg.norm(cxz - np.array(p)), 1e-9) * ch) for p in poly]
    lo = [mb.v(p[0], h0, p[1]) for p in poly]
    mid = [mb.v(p[0], h1 - ch, p[1]) for p in poly]
    tp = [mb.v(p[0], h1, p[1]) for p in ins]
    tris = tessellate_polygon([[Vector((p[0], p[1], 0)) for p in ins]])
    for t in tris:
        mb.fo([tp[i] for i in t], reg, UP)
    m = len(poly)
    for i in range(m):
        j = (i + 1) % m
        o = ((poly[i][0] + poly[j][0]) / 2 - cxz[0], 0, (poly[i][1] + poly[j][1]) / 2 - cxz[1])
        mb.fo([lo[i], lo[j], mid[j], mid[i]], reg, o)
        mb.fo([mid[i], mid[j], tp[j], tp[i]], reg, (o[0], 0.6 * math.hypot(o[0], o[2]), o[2]))


def build_den(root):
    """the lions' den: a ring of stone (three courses of chamfered blocks on both faces, irregular coping stones on
    top), the opening toward the front-left, a sandy floor with a straw bed, two flat rocks at the lion marks, a
    stone water trough against the back wall, straw strands and pebbles"""
    mb = MB()
    rng = random.Random(81)
    dec = DECOR.setdefault("den", [])
    ta = DEN_OPEN_TH + DEN_OPEN_HALF
    tb = DEN_OPEN_TH + TAU - DEN_OPEN_HALF
    Rm = 0.175
    L = (tb - ta) * Rm
    th_of = lambda s: ta + s / Rm
    rin, rout = den_rin, (lambda t: den_rin(t) + DEN_T)
    CH = DEN_TOP - 0.008
    # core faces (seen in the joints)
    NS = 64
    ths = np.linspace(ta, tb, NS + 1)
    for i in range(NS):
        t0, t1 = ths[i], ths[i + 1]
        for rf, sg in ((rout, 1), (rin, -1)):
            p0, p1 = den_pt(t0, rf(t0)), den_pt(t1, rf(t1))
            tm = (t0 + t1) / 2
            mb.fo([mb.v(p0[0], 0, p0[1]), mb.v(p1[0], 0, p1[1]), mb.v(p1[0], CH, p1[1]), mb.v(p0[0], CH, p0[1])],
                  "denStone", (sg * math.cos(tm), 0, sg * math.sin(tm)))
    for t, sg in ((ta, -1), (tb, 1)):                   # end faces
        p0, p1 = den_pt(t, rin(t)), den_pt(t, rout(t))
        o = (-math.sin(t) * sg, 0, math.cos(t) * sg)
        mb.fo([mb.v(p0[0], 0, p0[1]), mb.v(p1[0], 0, p1[1]), mb.v(p1[0], CH, p1[1]), mb.v(p0[0], CH, p0[1])],
              "denStone", o)
    rows = [0.0235, 0.0225, CH - 0.046]
    Wout = lambda s, h, d: (*den_pt(th_of(s), rout(th_of(s)) + d)[:1], h, den_pt(th_of(s), rout(th_of(s)) + d)[1])
    Win = lambda s, h, d: (*den_pt(th_of(s), rin(th_of(s)) - d)[:1], h, den_pt(th_of(s), rin(th_of(s)) - d)[1])
    nb = blocks(mb, L, rows, Wout, rng, "denStone", wmin=0.034, wmax=0.052, proud=(0.0025, 0.0045), g=0.0012,
                ch=0.0018, decor=dec, patch=lambda s, h: patchy(s * 0.9, h * 2.0, 2.0, -0.1))
    nb += blocks(mb, L * 0.92, rows, Win, rng, "denStone", wmin=0.030, wmax=0.046, proud=(0.0022, 0.0038),
                 g=0.0012, ch=0.0016, decor=dec, patch=lambda s, h: patchy(s * 0.9 + 3, h * 2.0, 3.0, -0.1))
    # coping stones
    s = 0.0
    while s < L - 0.004:
        w = rng.uniform(0.036, 0.054)
        a_, b_ = s + 0.0012, min(s + w, L) - 0.0012
        s += w
        if b_ - a_ < 0.01:
            continue
        hh = DEN_TOP - 0.002 + rng.uniform(-0.002, 0.002)
        sector_slab(mb, th_of(a_), th_of(b_), lambda t: rin(t) - 0.004, lambda t: rout(t) + 0.004, CH - 0.001, hh,
                    "denStone")
        if patchy(s, 1.0, 6.0, -0.4):
            p0, p1 = den_pt(th_of(a_), rout(th_of(a_)) + 0.004), den_pt(th_of(a_), rin(th_of(a_)) - 0.004)
            dec.append(((p0[0], hh, p0[1]), (p1[0], hh, p1[1])))
    # floor: sand disc with the straw bed region
    straw_c = (0.395, -0.268)
    straw = blob_poly(straw_c[0], straw_c[1], 0.062, 5.0, n=18, amp=0.10, sz=0.70)
    ring = [den_pt(t, den_rin(t) - 0.002) for t in np.linspace(0, TAU, 72, endpoint=False)]
    outl = [np.array(ring), _resample(straw, 0.008)]
    verts, edges = [], []
    for ol in outl:
        b0 = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b0 + i, b0 + (i + 1) % len(ol)) for i in range(len(ol))]
    for x in np.arange(DEN_C[0] - 0.18, DEN_C[0] + 0.18, 0.022):
        for z in np.arange(DEN_C[1] - 0.18, DEN_C[1] + 0.18, 0.022):
            p = np.array([x + (nz(x, z) - 0.5) * 0.008, z + (nz(z, x) - 0.5) * 0.008])
            if in_poly(tuple(p), ring) and min(np.min(np.hypot(*(o - p).T)) for o in outl) > 0.006:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, *_ = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])
    fh = lambda x, z: (0.0058 if in_poly((x, z), straw) else 0.0030) + 0.0006 * nz(x, z)
    ids = {}
    for f in fs:
        if len(f) != 3:
            continue
        c = tuple(V[list(f)].mean(0))
        if not in_poly(c, ring):
            continue
        reg = "straw" if in_poly(c, straw) else "denFloor"
        q = []
        for i in f:
            if i not in ids:
                x, z = V[i]
                ids[i] = mb.v(x, 0.0058 if (reg == "straw" and not any(np.hypot(*(np.array(ring) - V[i]).T) < 1e-6))
                              else fh(x, z), z)
            q.append(ids[i])
        mb.fo(q, reg, UP)
    # flat rocks at the lion marks, the trough
    for i, (x, z, rx, rz, a) in enumerate(LION_ROCKS):
        lumpy(mb, (x, 0.0035, z), 1.0, "flatRock", seg=12, rings=4, sh=0.0070, sx=rx, sz=rz, amp=0.10, seed=i + 3,
              smooth=False, flat_bottom=0.002)
    tx, tz, tl, tw = TROUGH
    cbox(mb, tx - tl / 2, tx + tl / 2, 0.0, 0.024, tz - tw / 2, tz + tw / 2, "flatRock", c=0.002)
    mb.nr = True
    box(mb, tx - tl / 2 + 0.005, tx + tl / 2 - 0.005, 0.0242, 0.0246, tz - tw / 2 + 0.005, tz + tw / 2 - 0.005,
        "water", skip=("bottom", "left", "right", "front", "back"))
    # straw: strands on the bed and scattered
    for k in range(70):
        if k < 40:
            r = 0.046 * math.sqrt(rng.random()); a = rng.uniform(0, TAU)
            x, z, h = straw_c[0] + r * math.cos(a), straw_c[1] + r * math.sin(a) * 0.62, 0.0066
        else:
            a = rng.uniform(0, TAU); r = rng.uniform(0.03, 0.15)
            x, z, h = DEN_C[0] + r * math.cos(a), DEN_C[1] + r * math.sin(a), 0.0036
            if r > den_rin(a) - 0.012:
                continue
        b = rng.uniform(0, TAU); Ls = rng.uniform(0.012, 0.022)
        d = (math.cos(b) * Ls / 2, math.sin(b) * Ls / 2)
        blade(mb, [(x - d[0], h, z - d[1]), (x + d[0], h + 0.0015, z + d[1])], [0.0018, 0.0012], "strawBit",
              nrm=(0, 1, 0))
    for k in range(14):
        a = rng.uniform(0, TAU); r = rng.uniform(0.02, 0.14)
        x, z = DEN_C[0] + r * math.cos(a), DEN_C[1] + r * math.sin(a)
        rr = rng.uniform(0.003, 0.0055)
        lumpy(mb, (x, 0.003 + rr * 0.3, z), rr, "pebble", seg=5, rings=3, sh=0.55, amp=0.2, seed=k + 60)
    mb.nr = False
    return make_obj("den", mb, root, origin=(DEN_C[0], 0.0, DEN_C[1]), smooth_angle=40), nb


def stone_template():
    """the big round stone: a hewn wheel (irregular many-sided rim, chamfered faces, a carved ring), standing on
    its edge in the template XY plane (face toward +z), foot at the origin; and the seal: a cord across the face to
    the wall ends with a red wax seal stamped with a ring"""
    mb = MB()
    R, T = STONE_R, STONE_T
    n = 18
    rim = [(R * (1 + 0.035 * (nz(k, 2) - 0.5) * 2) * math.cos(TAU * k / n),
            R + R * (1 + 0.035 * (nz(k, 2) - 0.5) * 2) * math.sin(TAU * k / n)) for k in range(n)]
    rim[n * 3 // 4] = (rim[n * 3 // 4][0], 0.0)                 # flat foot
    c = 0.006
    for zs in (1, -1):
        inner = [(x * (1 - c / R), R + (h - R) * (1 - c / R)) for x, h in rim]
        fo = [mb.v(x, h, zs * T / 2) for x, h in inner]
        mid = [mb.v(x, h, zs * (T / 2 - c * 0.7)) for x, h in rim]
        cen = mb.v(0.0, R, zs * (T / 2 + 0.002))
        for k in range(n):
            mb.fo([cen, fo[k], fo[(k + 1) % n]], "bigStone", (0, 0, zs), True)
            mb.fo([fo[k], fo[(k + 1) % n], mid[(k + 1) % n], mid[k]], "bigStone",
                  (rim[k][0], rim[k][1] - R, zs * 0.8))
        if zs == 1:
            top_mid = mid
        else:
            bot_mid = mid
    for k in range(n):
        k1 = (k + 1) % n
        mb.fo([top_mid[k], top_mid[k1], bot_mid[k1], bot_mid[k]], "bigStone", (rim[k][0], rim[k][1] - R, 0))
    rr = R * 0.66
    pts = [(rr * math.cos(TAU * k / 24), R + rr * math.sin(TAU * k / 24)) for k in range(25)]
    tube(mb, [(p[0], p[1], T / 2 - 0.0002) for p in pts[:-1]], 0.0016, "bigStone", seg=4, closed=True)
    seal = MB()
    zf = T / 2 + 0.002
    hc = R * 1.05
    cord_pts = [(-0.078, hc + 0.004, -0.004), (-0.050, hc + 0.0015, zf + 0.0005), (0.0, hc - 0.002, zf + 0.0035),
                (0.050, hc + 0.0015, zf + 0.0005), (0.078, hc + 0.004, -0.004)]
    seal.nr = True
    tube(seal, cord_pts, 0.0016, "cord", seg=5)
    seal.nr = False
    wc = (0.0, hc - 0.004, zf + 0.004)
    lathe(seal, [(0.0, -0.0035), (0.0205, -0.0035), (0.0215, 0.0), (0.019, 0.0035), (0.011, 0.0042), (0.0, 0.0045)],
          "wax", C=wc, A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=16,
          rfun=lambda th, i, k: 1.0 + 0.07 * math.sin(5 * th + 1) * (1 if i in (1, 2) else 0))
    tube(seal, [(0.0095 * math.cos(TAU * k / 16), hc - 0.004 + 0.0095 * math.sin(TAU * k / 16), zf + 0.0083)
                for k in range(16)], 0.0012, "wax", seg=4, closed=True)
    return mb, seal


def stone_fn(th, r):
    """template -> world for a stone standing at ring angle th, radius r (face = outward normal)"""
    x0, z0 = den_pt(th, r)
    nx, nzz = math.cos(th), math.sin(th)
    # template +z -> outward normal (nx, nz); yaw_fn maps z-axis to (-sin y, cos y)
    yaw = math.atan2(-nx, nzz)
    return yaw_fn(x0, z0, yaw)


def stone_clear(th, r):
    """hard clearance of a stoneOpen placed at (th, r): min margin over marks and paths while it is visible"""
    tpl, _ = STONE_TPL
    P = np.array([stone_fn(th, r)(v) for v in tpl.V])
    P = P[P[:, 1] > 0.012]
    m = 1.0
    for who, (x, z) in CONTRACT_MARKS:
        m = min(m, float(np.hypot(P[:, 0] - x, P[:, 2] - z).min()) - 0.05)
    for who, a, b, t0, t1 in PATHS:
        if not visible_during("stoneOpen", t0, t1):
            continue
        ax, az = a; bx, bz = b
        dx, dz = bx - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
        t = np.clip(((P[:, 0] - ax) * dx + (P[:, 2] - az) * dz) / L2, 0, 1)
        m = min(m, float(np.hypot(P[:, 0] - ax - t * dx, P[:, 2] - az - t * dz).min()) - 0.05)
    return m


STONE_TPL = None


def build_stones(root):
    global STONE_TPL
    STONE_TPL = stone_template()
    tpl, seal_tpl = STONE_TPL
    # stoneShut: in the gap, at mid radius
    shut_th, shut_r = DEN_OPEN_TH, 0.175
    # stoneOpen: the first place round the outside of the ring, back-left of the opening, that clears every walk
    r_open = 0.19 + DEN_T * 0 + STONE_T / 2 + 0.006
    found = None
    for k in range(0, 160):
        th = DEN_OPEN_TH + DEN_OPEN_HALF + 0.10 + 0.01 * k
        if stone_clear(th, r_open) >= 0.002:
            found = th
            break
    if found is None:
        found = DEN_OPEN_TH + 1.2
    m_open = MB(); m_open.add(tpl, stone_fn(found, r_open))
    m_shut = MB(); m_shut.add(tpl, stone_fn(shut_th, shut_r))
    m_seal = MB(); m_seal.add(seal_tpl, stone_fn(shut_th, shut_r))
    po = den_pt(found, r_open); ps = den_pt(shut_th, shut_r)
    so = make_obj("stoneOpen", m_open, root, origin=(po[0], 0.0, po[1]), smooth_angle=50)
    ss = make_obj("stoneShut", m_shut, root, origin=(ps[0], 0.0, ps[1]), smooth_angle=50)
    wax = stone_fn(shut_th, shut_r)((0.0, STONE_R * 1.05 - 0.004, STONE_T / 2 + 0.006))
    se = make_obj("seal", m_seal, ss, origin=wax, smooth_angle=50)
    combo = MB()
    combo.add(tpl, lambda p: p); combo.add(seal_tpl, lambda p: p)
    info = {"stoneOpenTh": round(math.degrees(found), 1), "stoneOpen": [round(c, 4) for c in po],
            "stoneShut": [round(c, 4) for c in ps], "openMargin": round(stone_clear(found, r_open), 4),
            "seal": [round(c, 4) for c in wax]}
    return so, ss, se, combo, info


# ============================================================================================ market
def build_market(root):
    """a little stall at the front-right corner: four posts, a sloping awning in red and cream stripes with a
    scalloped edge, a plank counter with pomegranates and a basket of dates, melons on the ground, two tall jars, a
    sack of grain"""
    mb = MB()
    mx, mz = MARKET
    px0, px1, pzb, pzf = mx - 0.062, mx + 0.062, mz - 0.042, mz + 0.040
    hb, hf = 0.154, 0.132
    for (x, z, h) in ((px0, pzb, hb), (px1, pzb, hb), (px0, pzf, hf), (px1, pzf, hf)):
        tube(mb, [(x, 0.0, z), (x, h + 0.004, z)], 0.0036, "stallWood", seg=6)
    # awning
    ax0, ax1 = px0 - 0.006, px1 + 0.006
    az0, az1 = pzb - 0.006, pzf + 0.010
    NS = 3
    sag = lambda x, z: -0.004 * math.sin(math.pi * (z - az0) / (az1 - az0))
    hfn = lambda x, z: hb + 0.002 + (hf - hb) * (z - az0) / (pzf - pzb) + sag(x, z)
    for i in range(NS):
        xa, xb = ax0 + (ax1 - ax0) * i / NS, ax0 + (ax1 - ax0) * (i + 1) / NS
        reg = "awningRed" if i % 2 == 0 else "awningCream"
        for j in range(4):
            za, zb = az0 + (az1 - az0) * j / 4, az0 + (az1 - az0) * (j + 1) / 4
            q = [mb.v(xa, hfn(xa, za), za), mb.v(xb, hfn(xb, za), za), mb.v(xb, hfn(xb, zb), zb), mb.v(xa, hfn(xa, zb), zb)]
            mb.fo(q, reg, UP, True)
            mb.fo(q, reg, (0, -1, 0), True)
        m = (xa + xb) / 2
        hz = hfn(m, az1)
        pts = [mb.v(xa, hfn(xa, az1), az1), mb.v(xb, hfn(xb, az1), az1), mb.v(xb, hfn(xb, az1) - 0.007, az1 + 0.001),
               mb.v(m, hz - 0.014, az1 + 0.002), mb.v(xa, hfn(xa, az1) - 0.007, az1 + 0.001)]
        mb.fo(pts, reg, (0, 0, 1), True)
        mb.fo(pts, reg, (0, 0, -1), True)
    # counter: plank front, top, legs
    cx0, cx1, cz0, cz1, ch = mx - 0.054, mx + 0.054, mz - 0.010, mz + 0.026, 0.050
    cbox(mb, cx0, cx1, ch - 0.005, ch, cz0, cz1, "stallWood", c=0.0015)
    for i in range(4):
        h0, h1 = 0.004 + i * 0.0112, 0.004 + (i + 1) * 0.0112 - 0.0008
        box(mb, cx0 + 0.002, cx1 - 0.002, h0, h1, cz1 - 0.004, cz1 - 0.0005 + 0.0005 * (i % 2), "stallWood",
            skip=("back",))
    for x in (cx0 + 0.004, cx1 - 0.004):
        box(mb, x - 0.003, x + 0.003, 0.0, ch - 0.005, cz0 + 0.002, cz1 - 0.002, "stallWood")
    # pomegranates on the counter (crown nubs on top)
    for i, (dx, dz, r) in enumerate(((-0.030, 0.010, 0.0195), (-0.006, 0.012, 0.0140), (-0.020, -0.006, 0.0125),
                                     (-0.018, 0.009, 0.012))):
        hh = ch + r * 0.9 + (0.017 if i == 3 else 0.0)
        lumpy(mb, (mx + dx, hh, mz + dz), r, "pomegranate", seg=12, rings=7, sh=0.92, amp=0.06, seed=i + 2)
        mb.nr = True
        lathe(mb, [(0.0, 0.0), (0.0035, 0.0), (0.0042, 0.004), (0.0, 0.0035)], "crown", C=(mx + dx, hh + r * 0.88, mz + dz),
              seg=6, smooth=False, rfun=lambda th, ii, k: 1.0 + 0.3 * (k % 2))
        mb.nr = False
    # basket of dates
    bx, bz = mx + 0.024, mz + 0.004
    mb.nr = True
    lathe(mb, [(0.0, ch), (0.021, ch), (0.030, ch + 0.012), (0.033, ch + 0.016), (0.0, ch + 0.012)], "basket",
          C=(bx, 0, bz), seg=14, smooth=False, rfun=lambda th, i, k: 1.0 + (0.04 if (i + k) % 2 else -0.02))
    mb.nr = False
    lumpy(mb, (bx, ch + 0.020, bz), 0.038, "dates", seg=14, rings=6, sh=0.52, amp=0.12, seed=7)
    # melons in front of the stall's left post, on the ground
    for i, (x, z, r, a) in enumerate(((mx - 0.110, mz + 0.026, 0.027, 0.4), (mx - 0.082, mz + 0.042, 0.019, -0.3))):
        lumpy(mb, (x, r * 0.78, z), r, "melon", seg=14, rings=7, sh=0.8, sx=1.22, amp=0.03, seed=i + 30)
    # two tall jars at the back, a sack of grain
    for (x, z, s) in ((px0 - 0.028, pzb + 0.004, 1.48), (px0 - 0.064, pzb + 0.012, 0.95)):
        prof = [(0.0, 0.0), (0.008, 0.0), (0.016, 0.014), (0.019, 0.030), (0.015, 0.048), (0.0075, 0.056),
                (0.0085, 0.062), (0.0, 0.060)]
        lathe(mb, [(r * s, h * s) for r, h in prof], "marketJar", C=(x, 0, z), seg=14)
    mb.nr = True
    lumpy(mb, (px1 - 0.004, 0.016, pzb - 0.016), 0.017, "sack", seg=10, rings=6, sh=1.1, amp=0.10, seed=12,
          flat_bottom=0.0)
    mb.nr = False
    return make_obj("market", mb, root, origin=(mx, 0.0, mz), smooth_angle=45)


# ============================================================================================ drawings / UV
def P_FRONT():
    return {"A": (1, 0, 0), "B": (0, 1, 0), "D": (0, 0, 1)}


def P_OBL(kx, k):
    return {"A": (1, 0, -kx), "B": (0, 1, -k), "D": (kx, k, 1)}


def P_PLAN():
    return {"A": (1, 0, 0), "B": (0, 0, -1), "D": (0, 1, 0)}


def P_FROM_EAST():
    """seen from +x (the window wall's inner face): right on the sheet = -z"""
    return {"A": (0, 0, -1), "B": (0, 1, 0), "D": (1, 0, 0)}


def _chars_proposal():
    """sheet slots (Set + sheet role, 2026-11-14 re-plan): the people at Ruth-like spacing on the bottom line, the
    side-view lion on a second row above Daniel; boxes = the Characters role's printed bboxes at those slots"""
    return {"daniel": {"sheetX": -0.34, "sheetY": 0.015, "height": 0.34, "box": [-0.463, 0.016, -0.217, 0.349]},
            "king": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.40, "box": [-0.134, 0.016, 0.134, 0.457]},
            "officer": {"sheetX": 0.34, "sheetY": 0.015, "height": 0.35, "box": [0.225, 0.016, 0.455, 0.354]},
            "lion": {"sheetX": -0.361, "sheetY": 0.368, "height": 0.13, "box": [-0.485, 0.368, -0.211, 0.562]}}


def _chars():
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    rc = json.load(open(p))
    got = {c: {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"], "height": v.get("height", prop.get(c, {}).get("height", 0.3)),
               "box": v["bboxSheet"]} for c, v in rc["characters"].items() if c in rc.get("sheet", {}) and v.get("bboxSheet")}
    for c, v in prop.items():
        got.setdefault(c, v)
    return got, all(c in rc.get("characters", {}) for c in prop)


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
DRAWINGS = {   # three columns round the figures: left above the lion, middle above the king, right above the official
    "den":        dict(P_OBL(0.0, 0.72), scale=1.50, cx=-0.355, y0=0.583, members=["den"],
                       decorOnly=["denStone", "flatRock"]),
    "house":      dict(P_OBL(0.30, 0.55), scale=1.38, cx=-0.364, y0=0.832, members=["house"],
                       decorOnly=["houseWall", "roof", "wood"]),
    "stone":      dict(P_FRONT(), scale=0.98, cx=0.372, y0=1.084, members=[], decorOnly=["bigStone", "wax"]),
    "palace":     dict(P_OBL(0.0, 0.34), scale=1.65, cx=-0.0925, y0=0.477, members=["palace", "throne"],
                       decorOnly=["palaceWall", "throne"]),
    "palm":       dict(P_FRONT(), scale=1.60, cx=0.1235, y0=0.477, members=[], creases=False),
    "gate":       dict(P_FRONT(), scale=1.35, cx=-0.040, y0=0.808, members=["gate"],
                       decorOnly=["gateTile", "gateDoor", "relief"]),
    "wall":       dict(P_FRONT(), scale=1.75, cx=0.022, y0=1.040, members=["cityWall"],
                       decorOnly=["mudBrick", "ziggurat"]),
    "market":     dict(P_OBL(0.25, 0.35), scale=0.92, cx=0.3595, y0=0.374, members=["market"],
                       decorOnly=["stallWood"]),
    "windowWall": dict(P_FROM_EAST(), scale=1.08, cx=0.372, y0=0.612, members=["windowWall"],
                       decorOnly=["houseWall", "shutter"]),
    "rug":        dict(P_PLAN(), scale=0.68, cx=0.372, y0=0.782, members=["rug"], creases=False),
    "ground":     dict(P_PLAN(), scale=7.0, cx=0.372, y0=0.957, members=["ground"], decorOnly=["paving", "sand"],
                       creases=False),
}
TEMPLATES = {"palm": ("palm",), "stone": ("stoneOpen", "stoneShut", "seal")}
CONSTS = {
    "ground": {"tuft": ("palm", "frond"), "pebble": ("den", "denStone")},
    "cityWall": {"farTrunk": ("palm", "trunk"), "palmFar": ("palm", "frond")},
    "gate": {"stud": ("gate", "relief")},
    "palace": {"friezeTile": ("gate", "gateTile"), "friezeGold": ("gate", "relief"), "tassel": ("palace", "throne"), "incense": ("palace", "throne"), "jar": ("market", "marketJar"),
               "torchBowl": ("palace", "throne"), "torchPole": ("house", "wood")},
    "house": {"iron": ("house", "wood"), "pot": ("market", "marketJar"), "leaf": ("palm", "frond"),
              "clothBlue": ("rug", "rugBlue"), "clothRed": ("rug", "rugRed")},
    "windowWall": {"lattice": ("windowWall", "shutter"), "pot": ("market", "marketJar"), "leaf": ("palm", "frond"),
                   "flower": ("rug", "rugRed")},
    "rug": {"fringe": ("rug", "rugCream")},
    "palm": {"date": ("market", "dates"), "dateStalk": ("palm", "trunk")},
    "den": {"water": ("gate", "gateTile"), "strawBit": ("den", "straw"), "pebble": ("den", "denStone")},
    "seal": {"cord": ("den", "straw")},
    "market": {"crown": ("market", "pomegranate"), "basket": ("market", "stallWood"), "sack": ("market", "awningCream")},
}


def dproj(sp, P):
    P = np.asarray(P, float)
    return P @ np.array(sp["A"], float), P @ np.array(sp["B"], float), P @ np.array(sp["D"], float)


def raster_sources(objs, tmp):
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
            if not used:
                continue
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
        if not dsp.get("creases", True):
            continue
        for name, P, tris in src[g]:
            ob = bpy.data.objects[name]; me = ob.data
            sharp = me.attributes.get("pc")
            if sharp is None:
                continue
            sv = np.zeros(len(me.edges), np.int32); sharp.data.foreach_get("value", sv)
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
    for g, dsp in DRAWINGS.items():
        regs = dsp.get("decorOnly")
        ids = [r for r, k in regname.items() if k and k[0] == g and (regs and k[1] in regs)]
        m = np.isin(idb, ids)
        crease[m] = False
        allg = np.isin(idb, [r for r, k in regname.items() if k and k[0] == g])
        for p0, p1 in DECOR.get(g, []):
            P2 = np.array([p0, p1], float)
            uv = uv_of(dsp, P2); dep = dproj(dsp, P2)[2]
            pa = np.array(to_px(*uv[0])); pb = np.array(to_px(*uv[1]))
            n = int(np.linalg.norm(pb - pa) / 0.6) + 2
            for t in np.linspace(0, 1, n):
                q = pa + (pb - pa) * t
                xi, yi = int(q[0]), int(q[1])
                if 0 <= xi < W and 0 <= yi < H and allg[yi, xi]:
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
        uvv = np.zeros((len(P), 2)) if g is None else uv_of(DRAWINGS[g], P)
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
    """faces edge-on to or facing away from their drawing's view (n . D < 0.22, n from P), or hidden behind another
    part of the drawing (the face centre lands on another region), take a clean texel deep inside their own region;
    no-raster faces take their named texel (CONSTS)"""
    tex = safe_texels(idb, regname, crease)
    rid_of = {k: r for r, k in regname.items() if k}
    count, missing = {}, set()
    stats = {"edgeOrBack": 0, "hidden": 0, "named": 0}
    H, W = idb.shape
    for name, ob in objs.items():
        if ob.type != 'MESH':
            continue
        g = drawing_of(name)
        me = ob.data; lay = me.uv_layers["UVMap"].data
        P = P_OF[name]; nr = NR_OF[name]; regs = REG_OF[name]
        dv = np.array(DRAWINGS[g]["D"], float) / np.linalg.norm(DRAWINGS[g]["D"]) if g else None
        uvv = uv_of(DRAWINGS[g], P) if g else None
        n = 0
        for p in me.polygons:
            reg = regs[p.index]
            if nr[p.index] or g is None:
                key = CONSTS.get(name, {}).get(reg)
                if key is None:
                    missing.add((name, reg)); continue
                stats["named"] += 1
            else:
                vids = list(p.vertices)
                Q = P[vids]
                nn = np.zeros(3)
                for i in range(len(Q)):
                    nn += np.cross(Q[i], Q[(i + 1) % len(Q)])
                L = np.linalg.norm(nn)
                key = (g, reg)
                if L < 1e-12 or (nn @ dv) / L < 0.22:
                    stats["edgeOrBack"] += 1
                else:
                    cu = uvv[vids].mean(0)
                    px, py = to_px(cu[0], cu[1])
                    xi, yi = int(px), int(py)
                    if 0 <= xi < W and 0 <= yi < H and idb[yi, xi] == rid_of.get(key, -1):
                        continue
                    stats["hidden"] += 1
            uv = tex.get(key)
            if uv is None:
                missing.add((name, reg)); continue
            for li in p.loop_indices:
                lay[li].uv = uv
            n += 1
        if n:
            count[name] = n
    return count, sorted(missing), tex, stats


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
                       "written by pipeline/da_babylon.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
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


def check_clearance(objs):
    """CONTRACT §6: no geometry above 0.012 within 0.05 of a mark, nothing on the straight paths between consecutive
    marks of one actor. Overhead parts only need head room: above the actor's height + 0.04 they are ignored, between
    0.17 and that height they must stay 0.035 from the line (a head's radius). Hidden props (stoneShut, seal,
    stoneOpen while shut) count for a walk only while the timeline shows them. Returns (hard failures, per-mark
    minimum clearance)."""
    pts, names = [], []
    for name, ob in objs.items():
        if ob.type != 'MESH' or name in FLAT_OK:
            continue
        for x, h, z in world_verts(ob):
            if h > 0.012:
                pts.append((x, h, z)); names.append(name)
    P = np.array(pts); names = np.array(names)
    hard, marks = {}, []

    def test(label, who, d, nodes_ok):
        Hh = HEIGHT.get(who, 0.35) + 0.04
        low = P[:, 1] < 0.17
        over = (P[:, 1] >= 0.17) & (P[:, 1] < Hh)
        sel = (low & (d < 0.05)) | (over & (d < 0.035))
        sel &= nodes_ok
        margin = float(np.min(np.where(low, d - 0.05, np.where(over, d - 0.035, 9.0))[nodes_ok])) if nodes_ok.any() else 9
        if sel.any():
            hard[label] = (round(float(P[sel, 1].max()), 4), sorted(set(names[sel].tolist())), round(margin, 4))
        return margin
    allok = np.ones(len(P), bool)
    for who, (x, z) in CONTRACT_MARKS:
        m = test("mark %s %.2f,%.2f" % (who, x, z), who, np.hypot(P[:, 0] - x, P[:, 2] - z), allok)
        marks.append((who, x, z, round(m, 4)))
    for who, a, b, t0, t1 in PATHS:
        vis = np.array([visible_during(n, t0, t1) for n in names])
        ax, az = a; bx, bz = b
        bx_c = max(min(bx, 0.60), -0.60); ax_c = max(min(ax, 0.60), -0.60)
        dx, dz = bx_c - ax_c, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
        t = np.clip(((P[:, 0] - ax_c) * dx + (P[:, 2] - az) * dz) / L2, 0, 1)
        d = np.hypot(P[:, 0] - ax_c - t * dx, P[:, 2] - az - t * dz)
        test("path %s %.2f,%.2f>%.2f,%.2f @%.0fs" % (who, ax, az, bx, bz, t0), who, d, vis)
    return hard, marks


# ============================================================================================ build
def page_mat():
    m = bpy.data.materials.new("da_page")
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.85
    return m


STATE = {}
ORDER = ["ground", "cityWall", "gate", "palace", "throne", "house", "windowWall", "rug", "palm", "den", "stoneOpen",
         "stoneShut", "seal", "market"]


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = link(bpy.data.objects.new("babylon", None))
    objs = {}
    objs["ground"], scatter = build_ground(root)
    objs["cityWall"], nb_wall = build_city_wall(root)
    objs["gate"], nb_gate = build_gate(objs["cityWall"])
    objs["palace"], torch = build_palace(root)
    objs["throne"] = build_throne(objs["palace"])
    objs["house"], nb_house = build_house(root)
    objs["windowWall"], window, nb_ww = build_window_wall(root)
    objs["rug"] = build_rug(root)
    objs["palm"], palm_tpl, palm_info = build_palms(root)
    objs["den"], nb_den = build_den(root)
    objs["stoneOpen"], objs["stoneShut"], objs["seal"], stone_tpl, stone_info = build_stones(root)
    objs["market"] = build_market(root)
    bpy.context.view_layer.update()
    tmp = {"tpl_palm": make_obj("tpl_palm", palm_tpl, None, smooth_angle=60),
           "tpl_stone": make_obj("tpl_stone", stone_tpl, None, smooth_angle=50)}
    src = raster_sources(objs, tmp)
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("BABYLON_TRIS", total, json.dumps(tris))
    print("SCATTER", json.dumps(dict(scatter, bricks={"wall": nb_wall, "gate": nb_gate, "house": nb_house,
                                                      "windowWall": nb_ww, "denBlocks": nb_den})))
    print("PALM", json.dumps(palm_info))
    print("STONES", json.dumps(stone_info))
    assert total <= MAX_TRIS, "over budget %d" % total
    if total > TARGET_TRIS:
        print("TRIS_NOTE above the 60k target (allowed up to %d)" % MAX_TRIS)
    lay = check_layout()
    hard, marks = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    for who, x, z, m in marks:
        print("CLEARANCE_MARK %-8s (%.2f, %.2f) margin %+.3f %s" % (who, x, z, m, "ok" if m >= 0 else "FAIL"))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    STATE.update(hard=hard, marks=marks)
    if MODE == "check":
        return
    RS[0] = 2
    idb2, regname, crease2 = raster_drawings(src)
    RS[0] = 1
    idb = idb2[1::2, 1::2]
    crease = crease2.reshape(PAGE[1], 2, PAGE[0], 2).any(axis=(1, 3))
    fixed, missing, tex, fstats = fix_faces(objs, idb, regname, crease)
    const = write_set_id(idb2, regname, crease2, tex)
    print("FIXED_FACES", json.dumps(fstats), "MISSING", missing)
    tex_img, demo = compose_sheets(idb, regname, crease)
    for o in tmp.values():
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.preferences.filepaths.save_version = 0
    objs["stoneShut"].hide_render = False
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    pm = page_mat()
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pm)
        ob.data.polygons.foreach_set("material_index", [0] * len(ob.data.polygons))
        for an in ("px", "ph", "pz", "nr", "pc"):
            if an in ob.data.attributes:
                ob.data.attributes.remove(ob.data.attributes[an])
    bpy.ops.object.select_all(action='DESELECT')
    for ob in [root] + list(root.children_recursive):
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_yup=True, export_apply=False,
                              export_texcoords=True, export_normals=True, export_materials='EXPORT',
                              export_animations=False, export_morph=False)
    hmax = {n: round(max(v[1] for v in world_verts(ob)), 4) for n, ob in objs.items()}
    write_design(objs, tris, total, hmax, const, hard, marks, palm_info, stone_info)
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root)
    print("BUILD_OK", GLB, total)


def write_design(objs, tris, total, hmax, const, hard, marks, palm_info, stone_info):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"sheetX": v["sheetX"], "sheetY": v["sheetY"]})
        e.setdefault("height", v["height"])
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
        "generatedBy": "pipeline/da_babylon.py", "doc": "docs/daniel/SET.md", "contract": "docs/daniel/CONTRACT.md §6",
        "root": "babylon",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {"torch": [TORCH[0], round(TORCH_H + 0.018, 4), TORCH[1]], "window": [-0.54, 0.10, -0.14],
                  "throne": [THRONE[0], PLAT[4], THRONE[1]], "palace": [0.0, 0.0, -0.46], "house": [-0.44, 0.0, -0.44],
                  "windowWall": [-0.54, 0.0, -0.14], "rug": [-0.44, 0.0, -0.14], "palm": [PALM_MAIN[0], 0.0, PALM_MAIN[1]],
                  "den": [DEN_C[0], 0.0, DEN_C[1]], "denOpening": [round(DEN_OPEN_PT[0], 4), 0.0, round(DEN_OPEN_PT[1], 4)],
                  "stoneOpen": [stone_info["stoneOpen"][0], 0.0, stone_info["stoneOpen"][1]],
                  "stoneShut": [stone_info["stoneShut"][0], 0.0, stone_info["stoneShut"][1]],
                  "seal": stone_info["seal"], "market": [MARKET[0], 0.0, MARKET[1]], "gate": [GATE_C, 0.0, -0.551],
                  "cityWall": [0.0, 0.0, -0.574]},
        "footprints": {"palacePlatform": [PLAT[0], PLAT[2], PLAT[1], PLAT[3]], "stepFrontZ": STEP_FRONT,
                       "house": [HOUSE[0], HOUSE[2], STAIR_X[1], HOUSE[3]], "windowWall": [WWALL_X[0], WWALL_Z[0], WWALL_X[1], WWALL_Z[1]],
                       "rug": [RUG[0], RUG[2], RUG[1], RUG[3]],
                       "den": {"centre": list(DEN_C), "innerRadius": 0.16, "innerBulgeToward": [0.30, -0.26],
                               "wall": DEN_T, "openingDirDeg": round(math.degrees(DEN_OPEN_TH), 1),
                               "openingInnerChord": round(2 * 0.160 * math.sin(DEN_OPEN_HALF), 4),
                               "openingCentre": [round(c, 4) for c in DEN_OPEN_PT]},
                       "lionRocks": [[r[0], r[1]] for r in LION_ROCKS], "trough": list(TROUGH[:2]),
                       "market": [MARKET[0] - 0.09, MARKET[1] - 0.07, MARKET[0] + 0.07, MARKET[1] + 0.055],
                       "floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]], "wallFrontZ": WALL_ZF},
        "heights": {"wallTop": WALL_TOP, "wallMax": hmax["cityWall"], "gateMax": hmax["gate"], "denTop": DEN_TOP,
                    "palmMax": hmax["palm"], "palmCrownBottomMain": palm_info["crownBottomMain"],
                    "platformTop": PLAT[4], "houseMax": hmax["house"], "windowWall": WWALL_H},
        "hiddenAtStart": ["stoneShut", "seal"],
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227; "
                             "P = world position, or the template position for instanced pieces (palms, stones, seal)",
                   "cleanTexel": "faces with n . D < 0.22 (edge-on or facing away, n in drawing space) or hidden behind "
                                 "another part of their drawing take one clean texel of their own region",
                   "namedTexels": "thin bits (torch poles, lattice, cords, fringe, straw, tufts, pebbles, fruit crowns) "
                                  "take one texel of a named (drawing, region); constUV in model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard,
                      "marks": [{"who": w, "at": [x, z], "margin": m} for w, x, z, m in marks]},
        "sheetLayout": {"characters": CHAR_PROPOSAL, "charactersFrom": "model/regions_characters.json" if CHARS_FROM_FILE
                        else "proposal (regions_characters.json not there yet)"},
        "demoColours": COLOURS, "tris": total, "budget": MAX_TRIS, "target": TARGET_TRIS,
    }
    json.dump(d, open(DESIGN_JSON, "w"), indent=1, ensure_ascii=False)


def compose_sheets(idb, regname, crease):
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
    save_png(line, os.path.join(WORK, "babylon_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "babylon_drawings_demo.png"))
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
    """preview stand-ins only (not shipped): simple figures in the demo colours"""
    mats = {k: flat_mat("pvm_" + k, v, 0.6) for k, v in {
        "skin": "#E9B48F", "cream": "#F4EEDD", "gold": "#E2B33C", "teal": "#2F8F9D", "hair": "#4A2E1F",
        "lav": "#9E86C8", "blue": "#3B4F9A", "purple": "#6E4FA8", "beard": "#2A1E1A", "orange": "#D9773A",
        "green": "#5E8F3E", "lion": "#E2A94A", "mane": "#A8562A", "muzzle": "#F3E2B8", "sandy": "#D9B47A"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    for who, (x, z, yaw) in layout.items():
        mb = MB()
        if who == "daniel":
            lathe(mb, [(0.0, 0.0), (0.045, 0.0), (0.043, 0.02), (0.036, 0.12), (0.032, 0.22), (0.028, 0.26), (0.0, 0.265)],
                  "cream", C=(x, 0, z), seg=18)
            lathe(mb, [(0.034, 0.15), (0.034, 0.165)], "teal", C=(x, 0, z), seg=18)
            lathe(mb, [(0.0, 0.245), (0.036, 0.25), (0.024, 0.268), (0.0, 0.27)], "gold", C=(x, 0, z), seg=16)
            sphere(mb, (x, 0.295, z), 0.031, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.302, z - 0.008), 0.031, "hair", seg=12, rings=8, sz=0.9)
            sphere(mb, (x, 0.278, z + 0.016), 0.016, "hair", seg=10, rings=6, sh=1.2, sz=0.7)
        elif who == "king":
            lathe(mb, [(0.0, 0.0), (0.056, 0.0), (0.055, 0.03), (0.060, 0.14), (0.046, 0.26), (0.032, 0.30), (0.0, 0.305)],
                  "lav", C=(x, 0, z), seg=18)
            lathe(mb, [(0.062, 0.05), (0.058, 0.17), (0.048, 0.27), (0.034, 0.30)], "blue", C=(x, 0, z - 0.005), seg=18,
                  rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.3 else 0.0001)
            sphere(mb, (x, 0.335, z), 0.034, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.312, z + 0.016), 0.024, "beard", seg=10, rings=7, sh=1.3, sz=0.8)
            lathe(mb, [(0.0, 0.355), (0.030, 0.355), (0.033, 0.40, "gold"), (0.033, 0.41, "purple"), (0.031, 0.44),
                       (0.0, 0.44)], "purple", C=(x, 0, z), seg=16)
        elif who == "officer":
            lathe(mb, [(0.0, 0.0), (0.044, 0.0), (0.040, 0.02), (0.032, 0.14), (0.029, 0.24), (0.024, 0.275), (0.0, 0.28)],
                  "orange", C=(x, 0, z), seg=18)
            lathe(mb, [(0.031, 0.15), (0.031, 0.164)], "green", C=(x, 0, z), seg=18)
            sphere(mb, (x, 0.308, z), 0.028, "skin", seg=14, rings=9, sh=1.2)
            lathe(mb, [(0.029, 0.322), (0.029, 0.332)], "gold", C=(x, 0, z), seg=16)
        else:
            body = "lion" if who == "lion" else "sandy"
            c = Vector((x, 0.09, z))
            sphere(mb, (x, 0.085, z), 0.06, body, seg=14, rings=8, sx=0.75, sz=1.35)
            for dx in (-0.03, 0.03):
                for dz in (-0.05, 0.05):
                    tube(mb, [(x + dx, 0.0, z + dz), (x + dx, 0.07, z + dz)], 0.012, body, seg=6)
            if who == "lion":
                sphere(mb, (x, 0.135, z + 0.075), 0.05, "mane", seg=14, rings=8, sz=0.8)
            sphere(mb, (x, 0.135, z + 0.09), 0.034, body, seg=12, rings=8)
            sphere(mb, (x, 0.125, z + 0.118), 0.016, "muzzle", seg=10, rings=6)
        ob = make_obj("pv_" + who, mb, None, origin=(x, 0.0, z), smooth_angle=60)
        ob["pv"] = 1
        ob.rotation_euler = (0, 0, math.radians(yaw))


def mode_preview():
    if not STATE.get("objs"):
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "babylon_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "babylon_preview_sheet.png")); sheet.pack()
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
    tl = bpy.data.lights.new("pv_torch", 'POINT'); tl.color = (1.0, 0.62, 0.30); tl.shadow_soft_size = 0.01
    tlo = link(bpy.data.objects.new("pv_torch", tl)); tlo.location = B(TORCH[0], TORCH_H + 0.03, TORCH[1])
    flame_m = flat_mat("pv_flame", "#FFB040", 0.5, emit=("#FFA030", 8.0))
    mbf = MB()
    fh = TORCH_H + 0.010
    lathe(mbf, [(0.0, fh), (0.008, fh + 0.006), (0.006, fh + 0.018), (0.0, fh + 0.032)], "f", C=(TORCH[0], 0, TORCH[1]),
          seg=10)
    fob = make_obj("pv_flame", mbf, None); fob.data.materials[0] = flame_m

    def light(mode):
        if mode == "day":
            sun.data.energy = 3.1; sun.data.color = (1.0, 0.95, 0.86)
            sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-30))
            fill.data.energy = 6.0; fill.data.color = (1.0, 0.88, 0.72)
            bg.inputs[0].default_value = (0.80, 0.84, 0.90, 1); bg.inputs[1].default_value = 0.75
            tl.energy = 0.0; fob.hide_render = True
        else:
            sun.data.energy = 0.45; sun.data.color = (0.55, 0.66, 1.0)
            sun.rotation_euler = (math.radians(55), math.radians(20), math.radians(40))
            fill.data.energy = 1.0; fill.data.color = (0.45, 0.55, 1.0)
            bg.inputs[0].default_value = (0.10, 0.13, 0.28, 1); bg.inputs[1].default_value = 0.5
            tl.energy = 0.6; fob.hide_render = False
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
            for o in [objs[n]] + list(objs[n].children_recursive):
                o.hide_render = not on

    def cast(layout):
        for o in [o for o in bpy.data.objects if o.get("pv")]:
            bpy.data.objects.remove(o, do_unlink=True)
        if layout:
            mannequins(layout)
    light("day")
    show(["stoneShut"], False)
    show(["stoneOpen"], True)
    cast({})
    phone = ((-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280))
    shoot("babylon_preview_phone_set", *phone)
    shoot("babylon_preview_phone_low", (0.02, 0.62, 0.95), (0.02, 0.06, -0.30), 52, (720, 1280))
    shoot("babylon_preview_front", (0.0, 0.26, 2.3), (0.0, 0.14, -0.25), 21, (1600, 1000))
    s01 = {"king": (0.0, -0.30, 0), "daniel": (-0.14, -0.20, 150), "officer": (0.12, -0.22, -150),
           "lion": (0.45, -0.22, -20), "lion2": (0.30, -0.26, 40)}
    cast(s01)
    shoot("babylon_preview_phone", *phone)
    shoot("babylon_preview_orbit", orbit((0.0, 0.10, -0.18), 1.5, 0.55, -25), (0.0, 0.10, -0.18), 38, (1280, 720))
    cast({"daniel": (-0.42, -0.14, -90), "officer": (-0.22, -0.02, -60)})
    shoot("babylon_preview_window", (-0.22, 0.30, 0.12), (-0.48, 0.08, -0.15), 42, (1280, 720))
    cast({"daniel": (0.36, -0.13, 0), "lion": (0.44, -0.09, -120), "lion2": (0.28, -0.18, 120)})
    shoot("babylon_preview_den", (0.10, 0.36, 0.22), (0.38, 0.03, -0.17), 42, (1280, 720))
    show(["stoneShut"], True); show(["stoneOpen"], False)
    light("night")
    cast({"daniel": (0.36, -0.13, 0), "lion": (0.45, -0.22, -60), "king": (-0.05, -0.30, 0)})
    shoot("babylon_preview_night", (0.05, 0.42, 0.45), (0.15, 0.06, -0.25), 46, (1280, 720))
    shoot("babylon_preview_sealed", (0.08, 0.17, 0.12), (0.26, 0.05, -0.05), 40, (1000, 800))
    light("day")
    show(["stoneShut"], False); show(["stoneOpen"], True); cast({})
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "babylon_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    if os.environ.get("DA_CLOSEUPS", "1") == "1":
        shoot("close_gate", (0.40, 0.18, -0.20), (0.40, 0.15, -0.56), 46, (1000, 800), WORK)
        shoot("close_palace", (0.0, 0.20, -0.12), (0.0, 0.14, -0.47), 50, (1000, 900), WORK)
        shoot("close_house", (-0.22, 0.26, -0.14), (-0.44, 0.12, -0.44), 46, (1000, 900), WORK)
        shoot("close_market", (0.40, 0.16, 0.36), (0.52, 0.06, 0.14), 42, (1000, 800), WORK)
        shoot("close_palm", (-0.14, 0.34, 0.20), (-0.29, 0.30, -0.07), 50, (1000, 900), WORK)
        shoot("close_wall", (-0.20, 0.22, -0.30), (-0.20, 0.15, -0.56), 50, (1000, 700), WORK)
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["babylon", "ground", "cityWall", "gate", "palace", "throne", "torch", "house", "windowWall", "window", "rug",
        "palm", "den", "stoneOpen", "stoneShut", "seal", "market"]


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
    pos = {n: [round(c, 4) for c in D(bpy.data.objects[n].matrix_world.translation)] for n in ("torch", "window")
           if n in names}
    ok = not missing and tris <= MAX_TRIS and uv_bad == 0
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "parents": parents, "empties": pos}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
