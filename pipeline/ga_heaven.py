"""Blender (headless): Gabriel story pack, the city of light -> assets/gabriel/model/heaven.glb

A tabletop stage on the colouring sheet: a sea of soft cumulus puffs (`clouds`: a low peach base sheet and sculpted
clumps, flat in the centre stage, banked up at the back and the sides), the `gate` of heaven at the back centre (a
gatehouse with an arched portal of light, two columns, a gold cornice and gable, the sun-disc rosette `gateGlow`
with rays over the arch, five wide steps down to the clouds, wall wings with lit arched windows and two domed
towers), two floating islets (`islandL`, `islandR`: an upside-down rock, a grass cap, a pond, a tree, a waterfall
wisp that ends in mist, pebbles hanging under it) and big cloud puffs at the front corners (`frontClouds`).
Contract: docs/gabriel/CONTRACT.md §6. Details, nodes and UV rules: docs/gabriel/SET.md.
Template: pipeline/da_babylon.py (mesh builder, drawings, UV rules and checks are the same code).

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `ga_page` = the scanned art rectangle): each piece belongs to one drawing on the
sheet, a linear view a = A.P, b = B.P, u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227. The cloud
clumps are instances of one sculpted template per node (`clouds`, `frontClouds`) and use the template position P, so
every clump wears the one cloud drawing of its node. A face edge-on to its drawing, facing away from it or hidden
behind another part takes one clean texel of its own region (LESSONS L51). Bits that are not drawn (the cloud base
sheet, the rosette rays, the pebbles) take a texel of a named region (CONSTS). The round lobes of the clouds, the
tree crowns and the mist are drawn on the sheet exactly (ray against ellipsoid), and the set drawings above the
figure are placed against the cast's real printed pixels (autofit).

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/ga_heaven.py -- build     heaven.glb + .blend + sheet drawings
  blender -b --factory-startup --python pipeline/ga_heaven.py -- verify    re-import heaven.glb and check it
  blender -b --factory-startup --python pipeline/ga_heaven.py -- all       build, preview, verify
  blender -b --factory-startup --python pipeline/ga_heaven.py -- check     build in memory, print the checks only
Work files go to $GA_WORK (default /tmp/gabriel_set).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/gabriel/model")
GLB = os.path.join(MODEL, "heaven.glb")
BLEND = os.path.join(MODEL, "heaven.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/gabriel/design.json")
WORK = os.environ.get("GA_WORK", "/tmp/gabriel_set")
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
MAX_TRIS = 45000                     # contract: set budget
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


# ============================================================================================ objects
REGION_MATS = {}
P_OF, NR_OF, REG_OF = {}, {}, {}
DECOR = {}


def region_mat(r):
    if r not in REGION_MATS:
        m = bpy.data.materials.new("rg_" + r)
        m.diffuse_color = (*lin(hex_rgb(COLOURS.get(r.split("#")[0], "#FFFFFF"))), 1)
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



# ============================================================================================ layout of the page
ZB, ZW, ZG = -0.5855, -0.500, -0.488          # back of the gate; wall-wing front face (contract z = -0.50); gatehouse front
GH_HW = 0.11                                  # gatehouse half width
TOWER_X = (0.29, 0.37)
GH_TOP = 0.345
DOOR_SPRING = 0.158
PLAT_H = 0.06                                 # top step = the threshold
STEPS = [(0.060 - 0.012 * k, -0.444 + 0.021 * k, 0.118 + 0.012 * k) for k in range(5)]   # (top h, front z, half width)
ROSETTE = (0.0, 0.296, 0.031)                 # centre x, centre h, disc radius
ISLANDS = {"islandL": (-0.45, -0.30, 1), "islandR": (0.45, -0.28, -1)}       # centre x, z, side of the waterfall
ISL_TOP = 0.262                               # rock 0.18 ... 0.262, grass cap to 0.28 (contract: floating 0.18-0.28)
ISL_R = 0.085
SKY, STAND, FRONT = (0.0, 0.02), (0.0, 0.02), (0.0, 0.10)                    # marks (storyboard/story.py)

# demo colouring (DESIGN.md table; the rest chosen to sit with it)
COLOURS = {
    "cloud": "#FFF6E2", "cloudShade": "#F7DDB0",
    "gateWall": "#F6EEDC", "gateGold": "#EED48E", "gateGlow": "#F2A43A", "gateLight": "#F8C56B",
    "rock": "#C9A47A", "grass": "#A9CF72", "tree": "#7DAA55", "water": "#BFE6F5", "mist": "#FFF6E2",
}


def smooth01(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _rect_dist(x, z, x0, x1, z0, z1):
    dx = max(x0 - x, 0.0, x - x1); dz = max(z0 - z, 0.0, z - z1)
    return math.hypot(dx, dz)


def allowed_h(x, z):
    """the height the clouds may reach at (x, z): continuous, always under the contract ceilings (0.04 in the centre
    stage x +-0.35, z -0.30...0.21 and in the wing sweep x +-0.55, z -0.15...0.20; 0.10 elsewhere), and lower
    still (0.016) where Gabriel stands, walks and kneels so his feet and knee stay in sight"""
    core = _rect_dist(x, z, -0.24, 0.24, -0.14, 0.30)
    a = 0.018 + (0.037 - 0.018) * smooth01(core / 0.07)
    u = min(_rect_dist(x, z, -0.36, 0.36, -0.31, 0.30), _rect_dist(x, z, -0.56, 0.56, -0.16, 0.30))
    if u > 0:
        a = 0.037 + (0.096 - 0.037) * smooth01(u / 0.10)
    st = _rect_dist(x, z, -0.18, 0.18, -0.60, -0.345)        # the stair: clouds only lap its foot
    a = min(a, 0.020 + 0.076 * smooth01(st / 0.09))
    return a


# ============================================================================================ sculpted puffs
LOBES_OF = {}


def lobes(mb, L, seg=10, rings=4, floor=0.0, tag=True, draw=None):
    """cumulus built the cartoon way: overlapping round lobes. L = (x, h, z, r, squash, region); each lobe is an
    ellipsoid from its top down to `floor` (None: the whole ball). Faces wholly inside another lobe are left out. With
    `tag` a lobe's faces are named '<region>#<i>': the sheet prints the line between two lobes of one region as a
    detail arc (merge_lobes), which is what makes the drawing read as a cloud."""
    base = len(LOBES_OF.get(draw, [])) if draw else 0
    for i, (x, h, z, r, sq, reg) in enumerate(L):
        if draw:
            LOBES_OF.setdefault(draw, []).append((x, h, z, r, sq, "%s#%d" % (reg, base + i), floor))
    for i, (x, h, z, r, sq, reg) in enumerate(L):
        rh = r * sq
        ce = -1.0 if floor is None else max(-1.0, min(1.0, (floor - h) / rh))
        t_end = math.acos(ce)
        n = max(2, int(round(rings * t_end / (math.pi / 2))))
        ring = []
        for k in range(n + 1):
            t = t_end * k / n
            if k == 0:
                ring.append(mb.v(x, h + rh, z)); continue
            if t > math.pi - 1e-6:
                ring.append(mb.v(x, h - rh, z)); continue
            ring.append([mb.v(x + r * math.sin(t) * math.cos(TAU * j / seg), h + rh * math.cos(t),
                              z + r * math.sin(t) * math.sin(TAU * j / seg)) for j in range(seg)])
        name = "%s#%d" % (reg, base + i) if tag else reg
        for k in range(n):
            a, b = ring[k], ring[k + 1]
            for j in range(seg):
                j1 = (j + 1) % seg
                if isinstance(a, int):
                    q = [a, b[j], b[j1]]
                elif isinstance(b, int):
                    q = [a[j], a[j1], b]
                else:
                    q = [a[j], a[j1], b[j1], b[j]]
                Q = np.array([mb.V[v] for v in q])
                c = Q.mean(axis=0)
                inside = False
                for m, (x2, h2, z2, r2, sq2, _) in enumerate(L):         # every corner inside another lobe
                    if m != i and (((Q[:, 0] - x2) / r2) ** 2 + ((Q[:, 1] - h2) / (r2 * sq2)) ** 2 +
                                   ((Q[:, 2] - z2) / r2) ** 2 < 0.97).all():
                        inside = True; break
                if not inside:
                    mb.fo(q, name, (c[0] - x, (c[1] - h) / (sq * sq), c[2] - z), True)


CLOUD_LOBES = [   # the floor clump: a wide low heap, light tops behind, a peach skirt of smaller puffs in front
    (0.000, 0.0, -0.010, 0.088, 0.92, "cloud"), (0.100, 0.0, -0.002, 0.070, 0.90, "cloud"),
    (-0.102, 0.0, -0.006, 0.073, 0.90, "cloud"), (0.172, 0.0, 0.016, 0.046, 0.88, "cloud"),
    (-0.176, 0.0, 0.014, 0.048, 0.88, "cloud"),
    (0.050, 0.0, 0.068, 0.058, 0.82, "cloudShade"), (-0.058, 0.0, 0.072, 0.055, 0.82, "cloudShade"),
    (0.128, 0.0, 0.062, 0.040, 0.80, "cloudShade"), (-0.136, 0.0, 0.064, 0.040, 0.80, "cloudShade"),
]
FRONT_LOBES = [   # the corner cloud: a towering cumulus
    (0.000, 0.0, 0.000, 0.088, 1.00, "cloud"), (0.022, 0.078, -0.012, 0.062, 1.00, "cloud"),
    (-0.064, 0.036, -0.004, 0.056, 1.00, "cloud"), (0.090, 0.0, 0.008, 0.064, 0.95, "cloud"),
    (-0.112, 0.0, 0.014, 0.052, 0.90, "cloud"),
    (0.030, 0.0, 0.072, 0.056, 0.82, "cloudShade"), (-0.050, 0.0, 0.076, 0.047, 0.82, "cloudShade"),
    (0.118, 0.0, 0.062, 0.042, 0.80, "cloudShade"),
]


def cloud_template(L, draw=None):
    """draw: the template that is printed (its lobes are rastered exactly); else the low-poly one for the instances"""
    mb = MB()
    lobes(mb, L, seg=28 if draw else 13, rings=9 if draw else 4, draw=draw)
    return mb


def place(mb, tpl, x0, z0, yaw, s, sh=1.0, sx=1.0, kk=1.0):
    """instance of a cloud template: scale s (sh extra on the height, sx extra on the width), yaw, move; then each
    vertex sinks under the allowed height at its place (smoothly: the puff sags toward the stage, no flat cut).
    Returns False (nothing added) when the clump would leave the floor."""
    V = np.array(tpl.V)
    top = float(V[:, 1].max()) * s * sh
    c, sn = math.cos(yaw), math.sin(yaw)
    X = x0 + s * (V[:, 0] * sx * c - V[:, 2] * sn); Z = z0 + s * (V[:, 0] * sx * sn + V[:, 2] * c)
    if X.min() < FLOOR[0] + 0.004 or X.max() > FLOOR[1] - 0.004 or Z.min() < FLOOR[2] + 0.004 or Z.max() > FLOOR[3] - 0.004:
        return False

    def f(p):
        x, h, z = p
        x *= sx
        x, z = x * c - z * sn, x * sn + z * c
        Xp, Zp = x0 + s * x, z0 + s * z
        Hh = s * sh * h
        a = allowed_h(Xp, Zp) * kk
        if top > a:
            Hh *= a / top
        return (Xp, Hh, Zp)
    mb.add(tpl, f)
    return True


TPL = {}


def build_clouds(root):
    """the cloud floor: a low rolling base sheet with a scalloped rim and sculpted clumps over it"""
    TPL["clouds"] = cloud_template(CLOUD_LOBES, "clouds")
    tpl = cloud_template(CLOUD_LOBES)
    mb = MB()
    x0, x1, z0, z1 = FLOOR
    # ---- base sheet (not drawn: takes the shade texel of the cloud drawing)
    mb.nr = True
    nx_, nz_ = 30, 20
    rim = lambda t, k: 0.012 * (1.0 + math.sin(t * 46 + k)) / 2
    grid = {}
    for j in range(nz_ + 1):
        for i in range(nx_ + 1):
            u, v = i / nx_, j / nz_
            x = x0 + (x1 - x0) * u; z = z0 + (z1 - z0) * v
            e = min(u, 1 - u) * (x1 - x0), min(v, 1 - v) * (z1 - z0)
            if i in (0, nx_):
                x += (rim(z, 1.0) if i == 0 else -rim(z, 2.0))
            if j in (0, nz_):
                z += (rim(x, 3.0) if j == 0 else -rim(x, 4.0))
            d = min(e)
            h = 0.0 if d < 1e-9 else min(allowed_h(x, z) * 0.45, 0.004 + 0.004 * smooth01(d / 0.05) +
                                         0.0035 * math.sin(31 * x + 2) * math.sin(27 * z + 1))
            grid[i, j] = mb.v(x, max(h, 0.0), z)
    for j in range(nz_):
        for i in range(nx_):
            mb.fo([grid[i, j], grid[i + 1, j], grid[i + 1, j + 1], grid[i, j + 1]], "base", UP, True)
    mb.nr = False
    # ---- clumps: rows from the back to the front, so the front ones overlap the ones behind
    rng = random.Random(5)
    n = 0
    spots = []
    gx, gz = 0.235, 0.118
    j = 0
    z = z0 + 0.13
    while z < z1 - 0.10:
        off = (j % 2) * gx / 2
        x = x0 + 0.13 + off
        while x < x1 - 0.12:
            spots.append((x + rng.uniform(-0.025, 0.025), z + rng.uniform(-0.014, 0.014)))
            x += gx
        z += gz; j += 1
    spots += [(-0.36, 0.085), (0.0, 0.092), (0.36, 0.085), (-0.18, 0.10), (0.18, 0.10)]      # the front row
    for x, z in spots:
        if abs(x) < 0.43 and z < -0.40:                       # the gate, its wall and the stair
            continue
        a = allowed_h(x, z)
        s = rng.uniform(0.78, 0.92) if a < 0.03 else rng.uniform(0.86, 1.05)
        yaw = rng.uniform(-0.45, 0.45)
        kk = rng.uniform(0.66, 1.0)
        for _ in range(10):
            if place(mb, tpl, x, z, yaw, s, kk=kk):
                n += 1; break
            s *= 0.93; x *= 0.97; z = -0.19 + (z + 0.19) * 0.95
    # banks at the back corners and the sides (under the islands, round the wall ends), and at the foot of the wall
    for x, z, s, yw in ((-0.44, -0.47, 0.60, 0.15), (0.44, -0.47, 0.60, -0.15), (-0.47, -0.35, 0.56, 0.5),
                        (0.47, -0.35, 0.56, -0.5), (-0.325, -0.435, 0.46, 0.1), (0.325, -0.435, 0.46, -0.1),
                        (-0.50, -0.20, 0.42, 1.0), (0.50, -0.20, 0.42, -1.0)):
        if place(mb, tpl, x, z, yw, s, sh=1.5):
            n += 1
    ob = make_obj("clouds", mb, root, origin=(0.0, 0.0, -0.19), smooth_angle=80, merge=False)
    return ob, n


def build_front_clouds(root):
    """the corner puffs: tall only outside the wing sweep (x beyond +-0.55), a low skirt reaching in to +-0.40"""
    TPL["frontClouds"] = cloud_template(FRONT_LOBES, "frontClouds")
    tpl = cloud_template(FRONT_LOBES)
    mb = MB()
    n = 0
    for sg in (-1, 1):
        for x, z, s, yw in ((0.475, 0.105, 0.62, 0.30), (0.495, -0.035, 0.52, 0.55), (0.385, 0.150, 0.40, 0.10)):
            if place(mb, tpl, sg * x, z, -sg * yw, s, kk=0.85 + 0.15 * (n % 2)):
                n += 1
    ob = make_obj("frontClouds", mb, root, origin=(0.0, 0.0, 0.10), smooth_angle=80, merge=False)
    return ob, n


# ============================================================================================ gate
def arch_poly(cx, half, h0, spring, n=14):
    pts = [(cx - half, h0), (cx + half, h0)]
    for i in range(n + 1):
        a = math.pi * i / n
        pts.append((cx + half * math.cos(a), spring + half * math.sin(a)))
    return pts


def arc_pts(cx, ch, r, a0, a1, n=16):
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), ch + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def dline(g, pts, z):
    """detail line on the sheet: a polyline (x, h) at depth z in a front drawing"""
    lst = DECOR.setdefault(g, [])
    for a, b in zip(pts, pts[1:]):
        lst.append(((a[0], a[1], z), (b[0], b[1], z)))


def quad_front(mb, x0, x1, h0, h1, z, reg):
    mb.fo([mb.v(x0, h0, z), mb.v(x1, h0, z), mb.v(x1, h1, z), mb.v(x0, h1, z)], reg, (0, 0, 1))


def build_gate(root):
    """the gate of heaven: gatehouse with the portal of light, columns, cornice and gable, five steps, wall wings
    with lit windows, two domed towers. Returns (gate, gateGlow)."""
    mb = MB()
    zc = (ZB + ZG) / 2
    # ---- wall wings with two arched windows each
    for sg in (-1, 1):
        xa, xb = sorted((sg * GH_HW, sg * TOWER_X[0]))
        box(mb, xa, xb, 0.0, 0.185, ZB + 0.012, ZW - 0.010, "gateWall", skip=("bottom", "front"))
        wins = [arch_poly(sg * c, 0.027, 0.058, 0.122, 10) for c in (0.157, 0.243)]
        extrude(mb, [(xa, 0.0), (xb, 0.0), (xb, 0.185), (xa, 0.185)], ZW - 0.010, ZW, "gateWall", back=False,
                holes=wins)
        for c in (0.157, 0.243):
            quad_front(mb, sg * c - 0.03, sg * c + 0.03, 0.05, 0.155, ZW - 0.0085, "gateLight")
            dline("gate", [(sg * c - 0.036, 0.046), (sg * c + 0.036, 0.046)], ZW + 0.001)      # sill
        cbox(mb, xa, xb, 0.185, 0.200, ZB + 0.008, ZW + 0.006, "gateWall", c=0.002)
        nsc = 6
        for i in range(nsc):                                # a scalloped crest
            c0 = xa + (xb - xa) * (i + 0.5) / nsc
            extrude(mb, [(c0 + 0.0115 * math.cos(math.pi * q / 8), 0.1995 + 0.0115 * math.sin(math.pi * q / 8))
                         for q in range(9)], ZW - 0.016, ZW + 0.003, "gateWall")
        dline("gate", [(xa, 0.185), (xb, 0.185)], ZW + 0.0065)
    # ---- towers
    for sg in (-1, 1):
        x0, x1 = sorted((sg * TOWER_X[0], sg * TOWER_X[1]))
        cx = sg * (TOWER_X[0] + TOWER_X[1]) / 2
        box(mb, x0, x1, 0.0, 0.25, ZB, ZG - 0.008, "gateWall", skip=("bottom", "front"))
        win = arch_poly(cx, 0.018, 0.115, 0.165, 10)
        extrude(mb, [(x0, 0.0), (x1, 0.0), (x1, 0.25), (x0, 0.25)], ZG - 0.008, ZG, "gateWall", back=False, holes=[win])
        quad_front(mb, cx - 0.021, cx + 0.021, 0.11, 0.19, ZG - 0.0065, "gateLight")
        dline("gate", [(x0, 0.075), (x1, 0.075)], ZG + 0.001)
        cbox(mb, x0 - 0.007, x1 + 0.007, 0.25, 0.276, ZB, ZG + 0.007, "gateGold", c=0.003)
        dline("gate", [(x0 - 0.007, 0.276), (x1 + 0.007, 0.276)], ZG + 0.0075)
        lathe(mb, [(0.040, 0.276), (0.0435, 0.288), (0.0415, 0.302), (0.033, 0.322), (0.020, 0.340), (0.009, 0.352),
                   (0.0045, 0.360), (0.0, 0.361)], "gateGold", C=(cx, 0, zc), seg=22)
        sphere(mb, (cx, 0.367, zc), 0.0085, "gateGold", seg=12, rings=8)
    # ---- gatehouse
    door = arch_poly(0.0, 0.05, PLAT_H, DOOR_SPRING, 18)
    box(mb, -GH_HW, GH_HW, 0.0, GH_TOP, ZB, ZG - 0.016, "gateWall", skip=("bottom", "front"))
    extrude(mb, [(-GH_HW, 0.0), (GH_HW, 0.0), (GH_HW, GH_TOP), (-GH_HW, GH_TOP)], ZG - 0.016, ZG, "gateWall",
            back=False, holes=[door])
    quad_front(mb, -0.055, 0.055, PLAT_H - 0.004, DOOR_SPRING + 0.055, ZG - 0.0145, "gateLight")
    # archivolt: a proud band round the arch
    ring = arc_pts(0, DOOR_SPRING, 0.066, 0, math.pi, 18) + [(-0.066, PLAT_H), (-0.05, PLAT_H)] + \
        arc_pts(0, DOOR_SPRING, 0.05, math.pi, 0, 18) + [(0.05, PLAT_H), (0.066, PLAT_H)]
    extrude(mb, ring, ZG, ZG + 0.005, "gateWall", back=False)
    dline("gate", [(0.066, PLAT_H)] + arc_pts(0, DOOR_SPRING, 0.066, 0, math.pi, 22) + [(-0.066, PLAT_H)], ZG + 0.0055)
    star = [(0.011 * (1.0 if i % 2 == 0 else 0.38) * math.cos(math.pi / 2 + i * math.pi / 4),
             DOOR_SPRING + 0.012 + 0.011 * (1.0 if i % 2 == 0 else 0.38) * math.sin(math.pi / 2 + i * math.pi / 4)) for i in range(9)]
    dline("gate", star, ZG - 0.014)
    cbox(mb, -GH_HW - 0.010, GH_HW + 0.010, GH_TOP, GH_TOP + 0.024, ZB, ZG + 0.048, "gateGold", c=0.003)
    extrude(mb, [(-GH_HW - 0.010, GH_TOP + 0.024), (GH_HW + 0.010, GH_TOP + 0.024), (0.0, 0.410)], ZB + 0.02,
            ZG + 0.044, "gateGold")
    dline("gate", [(-GH_HW - 0.010, GH_TOP + 0.024), (GH_HW + 0.010, GH_TOP + 0.024)], ZG + 0.0485)
    sphere(mb, (0.0, 0.4135, ZG + 0.020), 0.006, "gateGold", seg=12, rings=8)
    # rosette rays (the disc itself is the node gateGlow)
    rx, rh, rr = ROSETTE
    mb.nr = True
    for i in range(16):
        a = TAU * i / 16
        long_ = i % 2 == 0
        r0, r1 = rr + 0.0035, rr + (0.0135 if long_ else 0.009)
        w = 0.0035
        ca, sa = math.cos(a), math.sin(a)
        tri = [(rx + r0 * ca - w * sa, rh + r0 * sa + w * ca), (rx + r0 * ca + w * sa, rh + r0 * sa - w * ca),
               (rx + r1 * ca, rh + r1 * sa)]
        extrude(mb, tri, ZG, ZG + 0.0035, "ray", back=False)
    mb.nr = False
    for i in range(16):
        a = TAU * i / 16
        r0, r1 = rr + 0.0055, rr + (0.0135 if i % 2 == 0 else 0.0095)
        dline("gate", [(rx + r0 * math.cos(a), rh + r0 * math.sin(a)), (rx + r1 * math.cos(a), rh + r1 * math.sin(a))],
              ZG + 0.004)
    # ---- portico columns (fluted; they carry the cornice and the gable)
    for sg in (-1, 1):
        cx, cz = sg * 0.089, ZG + 0.024
        cbox(mb, cx - 0.019, cx + 0.019, PLAT_H, PLAT_H + 0.012, cz - 0.019, cz + 0.019, "gateGold", c=0.003)
        lathe(mb, [(0.0155, PLAT_H + 0.012), (0.0165, PLAT_H + 0.016), (0.0135, PLAT_H + 0.022)], "gateGold",
              C=(cx, 0, cz), seg=20)
        ct = GH_TOP
        lathe(mb, [(0.0128, PLAT_H + 0.022), (0.0124, 0.190), (0.0108, ct - 0.024)], "gateGold", C=(cx, 0, cz), seg=20,
              smooth=False, rfun=lambda th, i, k: 1.0 if k % 2 == 0 else 0.86)
        lathe(mb, [(0.0115, ct - 0.024), (0.0135, ct - 0.021), (0.0115, ct - 0.018), (0.0185, ct - 0.007),
                   (0.0185, ct - 0.0045)], "gateGold", C=(cx, 0, cz), seg=20)
        box(mb, cx - 0.020, cx + 0.020, ct - 0.0065, ct, cz - 0.020, cz + 0.020, "gateGold", skip=("top",))
        dline("gate", [(cx - 0.019, PLAT_H + 0.012), (cx + 0.019, PLAT_H + 0.012)], cz + 0.0195)
        dline("gate", [(cx - 0.0125, GH_TOP - 0.021), (cx + 0.0125, GH_TOP - 0.021)], cz + 0.014)
    # ---- newel posts at the foot of the stair
    for sg in (-1, 1):
        cx, cz = sg * (STEPS[4][2] + 0.006), STEPS[4][1] - 0.012
        cbox(mb, cx - 0.013, cx + 0.013, 0.0, 0.034, cz - 0.013, cz + 0.013, "gateGold", c=0.003)
        sphere(mb, (cx, 0.045, cz), 0.0125, "gateGold", seg=14, rings=9)
        dline("gate", [(cx - 0.013, 0.034), (cx + 0.013, 0.034)], cz + 0.0135)
    # ---- five steps (the top one is the threshold)
    for k, (hk, zf, hw) in enumerate(STEPS):
        zb_ = ZG - 0.016 if k == 0 else STEPS[k - 1][1] - 0.004
        cbox(mb, -hw, hw, 0.0, hk, zb_, zf, "gateGold", c=0.002)
        dline("gate", [(-hw, hk), (hw, hk)], zf + 0.0005)
    gate = make_obj("gate", mb, root, origin=(0.0, 0.0, ZW), smooth_angle=40)
    # ---- gateGlow: the sun-disc over the arch (a shallow lens), its own node for the glow
    mg = MB()
    lathe(mg, [(rr, 0.0), (rr, 0.0035), (rr * 0.93, 0.0062), (rr * 0.70, 0.0088), (rr * 0.36, 0.0102), (0.0, 0.0107)],
          "gateGlow", C=(rx, rh, ZG), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=30)
    glow = make_obj("gateGlow", mg, gate, origin=(rx, rh, ZG), smooth_angle=50)
    return gate, glow


# ============================================================================================ islets
def build_island(root, name):
    """a floating islet: faceted upside-down rock, scalloped grass cap, pond, tree, waterfall wisp into mist, pebbles"""
    cx, cz, f = ISLANDS[name]
    seed = 3.0 if f > 0 else 7.0
    T, R, SV = ISL_TOP, ISL_R, 0.80
    mb = MB()
    lathe(mb, [(R * 0.97, T + 0.002), (R * 0.95, T - 0.018), (R * 0.82, T - 0.042), (R * 0.58, T - 0.062),
               (R * 0.28, T - 0.076), (0.0, T - 0.082)], "rock", C=(cx, 0, cz), seg=10, smooth=False, sv=SV,
          rfun=lambda th, i, k: 1.0 + (0.16 * (nz(i + seed, k, seed) - 0.5) if i else 0.0))
    lathe(mb, [(R * 0.96, T - 0.004), (R * 1.06, T + 0.003), (R * 0.97, T + 0.011), (R * 0.62, T + 0.016),
               (R * 0.30, T + 0.018), (0.0, T + 0.018)], "grass", C=(cx, 0, cz), seg=20, sv=SV,
          rfun=lambda th, i, k: 1.0 + (0.045 * math.sin(5 * th + seed) if i < 3 else 0.0))
    # pond and waterfall on the front edge, on the side that faces the stage
    xw = cx + f * 0.032
    zl = cz + R * SV * 0.99                                 # the lip
    pond = [(xw + f * 0.004 + 0.034 * math.cos(TAU * i / 16), cz + 0.020 + 0.021 * math.sin(TAU * i / 16)) for i in range(16)]
    ngon_top(mb, pond, T + 0.0185, "water")
    hw = 0.021
    over = [mb.v(xw - hw, T + 0.0185, cz + 0.034), mb.v(xw + hw, T + 0.0185, cz + 0.034),
            mb.v(xw + hw, T + 0.014, zl + 0.006), mb.v(xw - hw, T + 0.014, zl + 0.006)]
    mb.fo(over, "water", (0, 1, 0.4))
    # the fall: a ribbon that widens and ripples on its way down, then fans out into the mist
    top, bot, nseg = T + 0.014, 0.100, 14
    half = lambda t: hw + 0.005 * t + 0.030 * t ** 3 + 0.0028 * math.sin(t * 4.2 * math.pi) * (0.3 + 0.7 * t)
    left = [(xw - half(i / nseg), top + (bot - top) * i / nseg) for i in range(nseg + 1)]
    right = [(xw + half(i / nseg) * 0.96 + 0.0012 * math.sin(i * 1.3), top + (bot - top) * i / nseg) for i in range(nseg + 1)]
    w1 = half(1.0)
    foot = [(xw - w1 * 0.66, 0.089), (xw - w1 * 0.36, 0.096), (xw - w1 * 0.05, 0.087), (xw + w1 * 0.30, 0.095),
            (xw + w1 * 0.62, 0.089)]
    fall = left + foot + right[::-1]
    puff(mb, fall, zl + 0.004, 0.006, "water", rad=0.012, edge=0.25, step=0.0075)
    dline(name, [(xw - 0.007, T + 0.004), (xw - 0.006, 0.235), (xw - 0.008, 0.205)], zl + 0.0105)
    dline(name, [(xw + 0.007, T - 0.014), (xw + 0.006, 0.222), (xw + 0.009, 0.192)], zl + 0.0105)
    lobes(mb, [(xw - 0.034, 0.083, zl + 0.020, 0.026, 1.0, "mist"), (xw - 0.001, 0.078, zl + 0.024, 0.032, 1.0, "mist"),
               (xw + 0.034, 0.083, zl + 0.020, 0.026, 1.0, "mist")], seg=14, rings=5, floor=None, draw=name)
    mb.nr = True
    for dx, hh, dz, r in ((0.050 * f, 0.163, 0.0, 0.012), (-0.035 * f, 0.150, 0.02, 0.009), (0.012 * f, 0.138, -0.01, 0.007)):
        lumpy(mb, (cx + dx, hh, cz + dz), r, "pebble", seg=7, rings=5, amp=0.22, seed=seed + r, smooth=False)
    mb.nr = False
    # tree
    tx, tz = cx - f * 0.030, cz - 0.008
    tube(mb, [(tx, T + 0.012, tz), (tx + 0.002, T + 0.040, tz), (tx, T + 0.068, tz)], [0.0125, 0.0105, 0.0095], "rock",
         seg=8)
    hb = T + 0.050
    if f > 0:                                               # a round crown
        el = [(tx, hb + 0.046, tz, 0.046, 1.0, "tree"), (tx - 0.040, hb + 0.030, tz + 0.006, 0.032, 1.0, "tree"),
              (tx + 0.042, hb + 0.032, tz + 0.004, 0.033, 1.0, "tree"), (tx + 0.008, hb + 0.074, tz, 0.032, 1.0, "tree"),
              (tx - 0.004, hb + 0.026, tz + 0.030, 0.028, 1.0, "tree")]
    else:                                                   # a taller one, in three tiers
        el = [(tx, hb + 0.030, tz, 0.046, 0.95, "tree"), (tx + 0.002, hb + 0.058, tz, 0.036, 1.0, "tree"),
              (tx + 0.004, hb + 0.081, tz, 0.025, 1.0, "tree"), (tx - 0.034, hb + 0.022, tz + 0.010, 0.027, 1.0, "tree"),
              (tx + 0.036, hb + 0.024, tz + 0.008, 0.027, 1.0, "tree")]
    lobes(mb, el, seg=16, rings=6, floor=None, draw=name)
    # a little bush on the other side
    lobes(mb, [(cx + f * 0.048, T + 0.016, cz - 0.012, 0.024, 1.0, "tree"),
               (cx + f * 0.066, T + 0.012, cz + 0.002, 0.018, 1.0, "tree")], seg=12, rings=4, floor=None, tag=False)
    return make_obj(name, mb, root, origin=(cx, 0.23, cz), smooth_angle=50)


def _chars_proposal():
    """CONTRACT §2: Gabriel fills the page (height 0.62, wings spread about 1.0 wide, tips up to about 0.80)"""
    return {"gabriel": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.62, "box": [-0.50, 0.015, 0.50, 0.80]}}


def _chars():
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    rc = json.load(open(p))
    got = {}
    for c, v in rc.get("characters", {}).items():
        sh = rc.get("sheet", {}).get(c)
        if sh and v.get("bboxSheet"):
            got[c] = {"sheetX": sh["sheetX"], "sheetY": sh["sheetY"],
                      "height": v.get("height", prop.get(c, {}).get("height", 0.62)), "box": v["bboxSheet"]}
    for c, v in prop.items():
        got.setdefault(c, v)
    return got, all(c in rc.get("characters", {}) for c in prop)


CHAR_PROPOSAL, CHARS_FROM_FILE = _chars()
# Gabriel fills the page; the set drawings sit in the band above his wings (gate in the middle, an islet on each
# side) and in the two bottom corners beside his legs, under the wings (the two cloud drawings)
DRAWINGS = {
    "gate":        dict(P_FRONT(), scale=1.34, cx=0.0, y0=0.868, fit="above", members=["gate", "gateGlow"],
                        decorOnly=["gateWall", "gateGold", "gateGlow", "gateLight"]),
    "islandL":     dict(P_OBL(0.0, 0.40), scale=1.12, cx=-0.390, y0=0.868, fit="above", members=["islandL"],
                        decorOnly=["rock", "water"]),
    "islandR":     dict(P_OBL(0.0, 0.40), scale=1.12, cx=0.390, y0=0.868, fit="above", members=["islandR"],
                        decorOnly=["rock", "water"]),
    "clouds":      dict(P_OBL(0.0, 0.50), scale=1.45, cx=-0.325, y0=0.030, members=[]),
    "frontClouds": dict(P_OBL(0.0, 0.35), scale=1.20, cx=0.345, y0=0.030, members=[]),
}
TEMPLATES = {"clouds": ("clouds",), "frontClouds": ("frontClouds",)}
CONSTS = {
    "clouds": {"base": ("clouds", "cloudShade")},
    "gate": {"ray": ("gate", "gateGold")},
    "islandL": {"pebble": ("islandL", "rock")},
    "islandR": {"pebble": ("islandR", "rock")},
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


def raster_lobes(g, dsp, idb, zb, regid, regname):
    """the round lobes of clouds and tree crowns, drawn exactly (ray against ellipsoid per pixel) instead of from
    their triangles: clean arcs on the sheet. Views with A = (1, 0, 0), B = (0, 1, -k), D = (0, k, 1) only."""
    assert tuple(dsp["A"]) == (1, 0, 0) and dsp["B"][0] == 0 and dsp["B"][1] == 1
    k = -dsp["B"][2]
    H, W = idb.shape
    s = dsp["scale"]
    for x, h, z, r, sq, reg, floor in LOBES_OF[g]:
        rh = r * sq
        ua = (x - r) / s + dsp["sheetX"] + 0.5; ub = (x + r) / s + dsp["sheetX"] + 0.5
        ext = rh + k * r + 0.002
        va = ((h - k * z) - ext) / s + dsp["sheetY"]; vb = ((h - k * z) + ext) / s + dsp["sheetY"]
        (X0, Y1), (X1, Y0) = to_px(ua, va / ART_H), to_px(ub, vb / ART_H)
        X0, X1, Y0, Y1 = max(int(X0) - 1, 0), min(int(X1) + 2, W), max(int(Y0) - 1, 0), min(int(Y1) + 2, H)
        if X1 <= X0 or Y1 <= Y0:
            continue
        gx, gy = np.meshgrid(np.arange(X0, X1) + 0.5, np.arange(Y0, Y1) + 0.5)
        a = ((gx / RS[0] - ART[0]) / ART[2] - 0.5 - dsp["sheetX"]) * s
        b = ((1.0 - (gy / RS[0] - ART[1]) / ART[3]) * ART_H - dsp["sheetY"]) * s
        xx = 1.0 - ((a - x) / r) ** 2
        A2 = k * k / (rh * rh) + 1.0 / (r * r)
        B2 = 2 * (k * (b - h) / (rh * rh) - z / (r * r))
        C2 = (b - h) ** 2 / (rh * rh) + z * z / (r * r) - xx
        disc = B2 * B2 - 4 * A2 * C2
        ok = (xx > 0) & (disc > 0)
        t = (-B2 + np.sqrt(np.where(ok, disc, 0.0))) / (2 * A2)
        if floor is not None:
            ok &= (b + k * t) >= floor
        dep = k * b + (k * k + 1) * t
        key = (g, reg)
        if key not in regid:
            regid[key] = len(regid) + 1; regname[regid[key]] = key
        sz = zb[Y0:Y1, X0:X1]; si = idb[Y0:Y1, X0:X1]
        upd = ok & (dep > sz)
        sz[upd] = dep[upd]; si[upd] = regid[key]


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
                if "#" in reg and g in LOBES_OF:
                    continue                              # lobes: drawn exactly by raster_lobes
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
    for g in LOBES_OF:
        raster_lobes(g, DRAWINGS[g], idb, zb, regid, regname)
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
    """faces edge-on to or facing away from their drawing's view (n . D < 0.22, n from P), or hidden or half hidden
    behind another part of the drawing (the face centre is off its region, or a point 0.8 of the way to a corner is on
    another region), take a clean texel deep inside their own region;
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
                    own = rid_of.get(key, -1)
                    ok = True
                    for q in [cu] + [cu + (uvv[v] - cu) * 0.8 for v in vids]:   # the centre must be on its own
                        px, py = to_px(q[0], q[1])                              # region, and no part of the face
                        xi, yi = int(px), int(py)                               # on another one (half hidden)
                        r_ = idb[yi, xi] if 0 <= xi < W and 0 <= yi < H else 0
                        if r_ != own and (q is cu or r_ > 0):
                            ok = False; break
                    if ok:
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
                       "written by pipeline/ga_heaven.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)
    return const



# ============================================================================================ checks
def load_mask(path):
    img = bpy.data.images.load(path)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32); img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[::-1, :, 3] > 0.5


def char_mask_page():
    """the cast's printed pixels on the page at 1x (None until the Characters role has written the ID render)"""
    p = os.path.join(MODEL, "id_characters_2x.png")
    if not os.path.exists(p):
        return None
    m2 = load_mask(p)
    if m2.shape != (ART[3] * 2, ART[2] * 2):
        print("CHAR_MASK unexpected size", m2.shape)
        return None
    m = m2.reshape(ART[3], 2, ART[2], 2).any(axis=(1, 3))
    page = np.zeros((PAGE[1], PAGE[0]), bool)
    page[ART[1]:ART[1] + ART[3], ART[0]:ART[0] + ART[2]] = m
    return page


FIT_GAP_PX = 20        # paper between a set drawing and the figure (1x px: 3.4 mm)
FIT_TOP = ART_H - 0.016
FIT_LIFT = 0.45        # of the free height that is left: the drawings sit a little above the wings, not on them


def autofit(src):
    """Gabriel fills the page and his outline changes with every character build: the drawings marked fit="above"
    (gate, islets) slide down until FIT_GAP_PX above the figure's printed pixels (the real ID render), then up by
    FIT_LIFT of what is left under the top of the art rectangle. No ID render yet: the layout numbers stay."""
    cm = char_mask_page()
    if cm is None:
        return {}
    near = dilate(cm, FIT_GAP_PX)
    H, W = near.shape
    first = np.where(near.any(axis=0), near.argmax(axis=0), H)          # top row of the figure (+ gap) per column
    idb, regname, _ = raster_drawings(src)
    out = {}
    for g, dsp in DRAWINGS.items():
        if dsp.get("fit") != "above":
            continue
        m = np.isin(idb, [r for r, k_ in regname.items() if k_ and k_[0] == g])
        cols = m.any(axis=0)
        if not cols.any():
            continue
        last = H - 1 - m[::-1].argmax(axis=0)                           # bottom row of the drawing per column
        drop = int((first[cols] - last[cols]).min()) - 1                # px it can come down (negative: go up)
        top = int(np.nonzero(m.any(axis=1))[0][0])
        low_y0 = dsp["y0"] - drop / ART[2]
        height = dsp["bboxSheet"][3] - dsp["bboxSheet"][1]
        slack = max(0.0, FIT_TOP - (low_y0 + height))
        dsp["y0"] = round(low_y0 + FIT_LIFT * slack, 4)
        out[g] = {"y0": dsp["y0"], "lowest": round(low_y0, 4), "slack": round(slack, 4)}
    return out


def refine_half_hidden(objs, src, names=("gate", "islandL", "islandR"), min_edge=0.011, passes=6):
    """UV0 is decided per face (fix_faces: a face whose centre is hidden behind another part of its drawing takes a
    clean texel), so a big wall face half hidden behind the stair or a column would wear their print on its free
    half, and a rock face behind the waterfall the water's. Faces that look toward the drawing and are only partly
    on their own region are split until their edges are under min_edge: the print of the part in front stays within
    a few millimetres of its silhouette (LESSONS L51). Returns the triangles added per piece."""
    idb, regname, _ = raster_drawings(src)
    base = np.zeros(max(regname) + 1, np.int32)
    ids = {}
    for r, k_ in regname.items():
        if k_:
            base[r] = ids.setdefault((k_[0], k_[1].split("#")[0]), len(ids) + 1)
    H, W = idb.shape
    added = {}
    for name in names:
        ob = objs[name]; g = drawing_of(name); dsp = DRAWINGS[g]
        dv = np.array(dsp["D"], float); dv /= np.linalg.norm(dv)
        me = ob.data
        me.calc_loop_triangles(); n0 = len(me.loop_triangles)
        for _ in range(passes):
            P = P_OF[name]; nr = NR_OF[name]; regs = REG_OF[name]
            uv = uv_of(dsp, P)
            px, py = to_px(uv[:, 0], uv[:, 1])
            pts = np.stack([px, py], -1)
            split = []
            for p in me.polygons:
                if nr[p.index]:
                    continue
                vids = list(p.vertices)
                Q = P[vids]
                nn = np.zeros(3)
                for i in range(len(Q)):
                    nn += np.cross(Q[i], Q[(i + 1) % len(Q)])
                L = np.linalg.norm(nn)
                if L < 1e-14 or (nn @ dv) / L < 0.22:
                    continue
                own = ids.get((g, regs[p.index].split("#")[0]), -1)
                c = pts[vids].mean(0)
                seen_own = seen_other = False
                for q in [c] + [c + (pts[v] - c) * 0.8 for v in vids]:
                    xi, yi = int(q[0]), int(q[1])
                    b_ = base[idb[yi, xi]] if 0 <= xi < W and 0 <= yi < H else 0
                    if b_ == own:
                        seen_own = True
                    elif b_ > 0:
                        seen_other = True
                if seen_own and seen_other:
                    split.append(p.index)
            if not split:
                break
            bm = bmesh.new(); bm.from_mesh(me); bm.faces.ensure_lookup_table()
            edges = {e for i in split for e in bm.faces[i].edges if e.calc_length() > min_edge}
            if not edges:
                bm.free(); break
            bmesh.ops.subdivide_edges(bm, edges=list(edges), cuts=1, use_grid_fill=False)
            bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
            bm.to_mesh(me); bm.free()
            mw = ob.matrix_world
            Pn = np.array([D(mw @ v.co) for v in me.vertices], np.float32)   # world position = the drawing model
            for k_, ax in enumerate(("px", "ph", "pz")):
                me.attributes[ax].data.foreach_set("value", Pn[:, k_])
            read_attrs(ob)
        me.calc_loop_triangles(); added[name] = len(me.loop_triangles) - n0
    return added


def check_layout(idb=None):
    msgs = []
    boxes = {g: d["bboxSheet"] for g, d in DRAWINGS.items()}
    for g, b in boxes.items():
        if b[0] < -0.485 or b[2] > 0.485 or b[1] < 0.012 or b[3] > ART_H - 0.012:
            msgs.append("drawing %s outside the art rect: %s" % (g, b))
    gs = list(boxes)
    for i in range(len(gs)):
        for j in range(i + 1, len(gs)):
            a, b = boxes[gs[i]], boxes[gs[j]]
            gx = max(b[0] - a[2], a[0] - b[2]); gy = max(b[1] - a[3], a[1] - b[3])
            if max(gx, gy) < 0.012:
                msgs.append("bbox overlap %s / %s (gap %.3f)" % (gs[i], gs[j], max(gx, gy)))
    cm = char_mask_page()
    info = {"castMask": cm is not None}
    if cm is None:                                          # no ID render yet: boxes against the proposal
        for g, b in boxes.items():
            for c, cv in CHAR_PROPOSAL.items():
                cb = cv["box"]
                gx = max(cb[0] - b[2], b[0] - cb[2]); gy = max(cb[1] - b[3], b[1] - cb[3])
                if max(gx, gy) < 0.02:
                    msgs.append("drawing %s too close to the proposed box of %s (%.3f)" % (g, c, max(gx, gy)))
    elif idb is not None:                                   # the real thing: >= 2.5 mm of paper between the inks
        near = dilate(cm, 15)
        hit = near & (idb > 0)
        info["setWithin15pxOfCastPx"] = int(hit.sum())
        if hit.any():
            ys, xs = np.nonzero(hit)
            msgs.append("set drawing within 15 px of the figure: %d px round page (%d, %d)" %
                        (hit.sum(), int(xs.mean()), int(ys.mean())))
    return msgs, info


def check_clearance(objs):
    """CONTRACT §6 ceilings, measured on the vertices: centre stage (x +-0.35, z -0.30...0.21) clouds <= 0.04,
    wing sweep (x +-0.55, z -0.15...0.20) nothing above 0.04, the keep-clear stage (x +-0.30, z -0.20...0.21),
    cloud tops <= 0.10 anywhere, gate <= 0.42, floor bounds"""
    out, fails = {}, []
    allv = {n: np.array(world_verts(ob)) for n, ob in objs.items() if ob.type == 'MESH'}
    P = np.concatenate(list(allv.values()))
    centre = (np.abs(P[:, 0]) <= 0.35) & (P[:, 2] >= -0.30) & (P[:, 2] <= 0.21)
    sweep = (np.abs(P[:, 0]) <= 0.55) & (P[:, 2] >= -0.15) & (P[:, 2] <= 0.20)
    stage = (np.abs(P[:, 0]) <= 0.30) & (P[:, 2] >= -0.20) & (P[:, 2] <= 0.21)
    marks = [np.hypot(P[:, 0] - x, P[:, 2] - z) < 0.12 for x, z in (STAND, FRONT)]
    out["centreStageMaxH"] = round(float(P[centre, 1].max()), 4)
    out["wingSweepMaxH"] = round(float(P[sweep, 1].max()), 4)
    out["keepClearStageMaxH"] = round(float(P[stage, 1].max()), 4)
    out["roundTheMarksMaxH"] = round(float(max(P[m, 1].max() for m in marks)), 4)
    out["cloudsMaxH"] = round(float(max(allv["clouds"][:, 1].max(), allv["frontClouds"][:, 1].max())), 4)
    out["gateMaxH"] = round(float(max(allv["gate"][:, 1].max(), allv["gateGlow"][:, 1].max())), 4)
    out["islandMinMaxH(mist to tree top)"] = {n: [round(float(allv[n][:, 1].min()), 4), round(float(allv[n][:, 1].max()), 4)]
                                              for n in ("islandL", "islandR")}
    out["bounds"] = [round(float(v), 4) for v in (P[:, 0].min(), P[:, 0].max(), P[:, 2].min(), P[:, 2].max())]
    out["minH"] = round(float(P[:, 1].min()), 4)
    if out["centreStageMaxH"] > 0.04: fails.append("centre stage above 0.04")
    if out["wingSweepMaxH"] > 0.04: fails.append("wing sweep above 0.04")
    if out["cloudsMaxH"] > 0.10: fails.append("clouds above 0.10")
    if out["gateMaxH"] > 0.42: fails.append("gate above 0.42")
    b = out["bounds"]
    if b[0] < FLOOR[0] - 1e-4 or b[1] > FLOOR[1] + 1e-4 or b[2] < FLOOR[2] - 1e-4 or b[3] > FLOOR[3] + 1e-4:
        fails.append("outside the floor %s" % b)
    if out["minH"] < -1e-5: fails.append("below the page")
    return fails, out


# ============================================================================================ build
def page_mat():
    m = bpy.data.materials.new("ga_page")
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.85
    return m


def merge_lobes(idb, regname, crease):
    """'<region>#<i>' ids (the lobes of a cloud or a tree crown) become one region; the border between two lobes of
    one region is printed as a detail line"""
    remap = np.zeros(max(regname) + 1, np.int32)
    new, ids = {0: None}, {}
    for rid, key in regname.items():
        if not key:
            continue
        b = (key[0], key[1].split("#")[0])
        if b not in ids:
            ids[b] = len(ids) + 1; new[ids[b]] = b
        remap[rid] = ids[b]
    out = remap[idb]
    for dy, dx in ((0, 1), (1, 0)):
        s = shift(idb, dy, dx)
        crease |= (idb != s) & (idb > 0) & (s > 0) & (out == remap[s])
    for name in list(REG_OF):
        REG_OF[name] = [r.split("#")[0] for r in REG_OF[name]]
    return out, new, crease


STATE = {}
ORDER = ["clouds", "gate", "gateGlow", "islandL", "islandR", "frontClouds"]
SHEET = {
    "page": [1240, 1754], "dpi": 150, "art": [120, 283, 1000, 1227],
    "markers": [[62, 225], [1178, 225], [1178, 1568], [62, 1568]], "markerSize": 64,
    "title": {"hanzi": "大天使加百列", "pinyin": "dà tiān shǐ jiā bǎi liè", "english": "Gabriel the Archangel",
              "box": 80, "gap": 50, "cy": 102, "label": "DoodLive · 涂上颜色，再用手机扫一扫",
              "note": "six boxes, like David & Goliath (76 / 12 / 100) and Daniel (84 / 22 / 104): box 80 / gap 50 / "
                      "cy 102 was the most distinct of a grid of candidates that keep the pinyin 6 mm from the "
                      "top edge (most similar other title NCC 0.35; tools/story/sheet_gabriel.py signature)"},
    "footer": {"rect": [210, 1604, 820, 110],
               "lines": ["四个黑方块要完整拍进画面 · 不要涂到黑方块上", "路加福音 1 章 · Luke 1"],
               "note": "centred on the page (x 620); line 1 at rect y + 40, line 2 at y + 76"},
    "edgeRule": "all ink except the four markers (fixed by the template) >= 6 mm (35.4 px) from every page edge",
}


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    root = link(bpy.data.objects.new("heaven", None))
    objs = {}
    objs["clouds"], n_clumps = build_clouds(root)
    objs["gate"], objs["gateGlow"] = build_gate(root)
    objs["islandL"] = build_island(root, "islandL")
    objs["islandR"] = build_island(root, "islandR")
    objs["frontClouds"], n_front = build_front_clouds(root)
    bpy.context.view_layer.update()
    tmp = {"tpl_" + g: make_obj("tpl_" + g, m, None, smooth_angle=80, merge=False) for g, m in TPL.items()}
    src = raster_sources(objs, tmp)
    setup_maps(src)
    fit = autofit(src)
    if fit:
        setup_maps(src)
        print("AUTOFIT", json.dumps(fit))
    if MODE != "check":
        print("REFINED", json.dumps(refine_half_hidden(objs, src)))
        src = raster_sources(objs, tmp)
        setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    tpl_tris = {}
    for n, ob in tmp.items():
        ob.data.calc_loop_triangles(); tpl_tris[n] = len(ob.data.loop_triangles)
    print("HEAVEN_TRIS", total, json.dumps(tris), "templates", json.dumps(tpl_tris),
          "clumps", n_clumps, "frontPuffs", n_front)
    assert total <= MAX_TRIS, "over budget %d" % total
    hard, clr = check_clearance(objs)
    print("CLEARANCE", "OK" if not hard else hard, json.dumps(clr))
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    STATE.update(hard=hard, clr=clr)
    if MODE == "check":
        lay, info = check_layout()
        print("LAYOUT", "OK" if not lay else lay, info)
        return
    RS[0] = 2
    idb2, regname, crease2 = raster_drawings(src)
    RS[0] = 1
    idb2, regname, crease2 = merge_lobes(idb2, regname, crease2)
    idb = idb2[1::2, 1::2]
    crease = crease2.reshape(PAGE[1], 2, PAGE[0], 2).any(axis=(1, 3))
    lay, info = check_layout(idb)
    print("LAYOUT", "OK" if not lay else lay, info)
    fixed, missing, tex, fstats = fix_faces(objs, idb, regname, crease)
    const = write_set_id(idb2, regname, crease2, tex)
    print("FIXED_FACES", json.dumps(fstats), "MISSING", missing)
    tex_img, demo = compose_sheets(idb, regname, crease)
    for o in tmp.values():
        bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
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
    write_design(objs, tris, total, hmax, const, hard, clr, lay, info, n_clumps, n_front)
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root)
    print("BUILD_OK", GLB, total)


def write_design(objs, tris, total, hmax, const, hard, clr, lay, info, n_clumps, n_front):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    d["version"] = 1
    d["artHeightUnits"] = ART_H
    d["lines"] = {"outerPx": 4.5, "detailPx": 3.0,
                  "note": "same weights as David & Goliath, Esther, Ruth and Daniel"}
    d["sheet"] = SHEET
    ch = d.get("characters", {})
    for c, v in CHAR_PROPOSAL.items():
        e = ch.get(c, {})
        e.update({"sheetX": v["sheetX"], "sheetY": v["sheetY"], "projection": "front"})
        e.setdefault("height", v["height"])
        ch[c] = e
    d["characters"] = ch
    d["_note"] = "sheet, lines, characters.* and set/* are written by pipeline/ga_heaven.py (Set + sheet role)"
    pieces = []
    for name in ORDER:
        g = drawing_of(name)
        sp = DRAWINGS[g]
        fu = {k: (round(sp[k], 5) if isinstance(sp[k], float) else sp[k]) for k in ("A", "B", "D", "scale", "sheetX",
                                                                                  "sheetY")}
        pieces.append({"id": name, "drawing": g, "frontUV": fu, "instanced": name in sum(TEMPLATES.values(), ()),
                       "namedTexels": {r: list(k) for r, k in CONSTS.get(name, {}).items()} or None,
                       "regions": sorted(set(REG_OF[name])), "heightMax": hmax[name], "tris": tris[name]})
    drawings = {g: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dsp.items()} for g, dsp in DRAWINGS.items()}
    il, ir = ISLANDS["islandL"], ISLANDS["islandR"]
    d["set"] = {
        "generatedBy": "pipeline/ga_heaven.py", "doc": "docs/gabriel/SET.md", "contract": "docs/gabriel/CONTRACT.md §6",
        "root": "heaven",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {"clouds": [0.0, 0.0, -0.19], "gate": [0.0, 0.0, ZW], "gateGlow": [ROSETTE[0], ROSETTE[1], ZG],
                  "islandL": [il[0], 0.23, il[1]], "islandR": [ir[0], 0.23, ir[1]], "frontClouds": [0.0, 0.0, 0.10]},
        "footprints": {"floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]],
                       "gate": [-TOWER_X[1] - 0.007, ZB, TOWER_X[1] + 0.007, ZG + 0.009], "wallFrontZ": ZW,
                       "gatehouseFrontZ": ZG, "door": {"halfWidth": 0.05, "sill": PLAT_H, "top": round(DOOR_SPRING + 0.05, 4)},
                       "steps": [{"top": round(h, 4), "frontZ": round(z, 4), "halfWidth": round(w, 4)} for h, z, w in STEPS],
                       "islandL": {"centre": [il[0], il[1]], "radius": ISL_R}, "islandR": {"centre": [ir[0], ir[1]], "radius": ISL_R},
                       "marks": {"sky/stand": list(STAND), "front": list(FRONT)}},
        "heights": {"gateMax": clr["gateMaxH"], "wallTop": 0.20, "towerTop": 0.3755, "gatehouseCornice": round(GH_TOP + 0.024, 4),
                    "rosetteCentre": ROSETTE[1], "threshold": PLAT_H, "islandRock": [round(ISL_TOP - 0.082, 4), ISL_TOP],
                    "islandGrassTop": round(ISL_TOP + 0.018, 4), "islandMax": max(hmax["islandL"], hmax["islandR"]),
                    "cloudsMax": clr["cloudsMaxH"], "centreStageMax": clr["centreStageMaxH"],
                    "wingSweepMax": clr["wingSweepMaxH"], "roundTheMarksMax": clr["roundTheMarksMaxH"]},
        "hiddenAtStart": [],
        "clouds": {"clumps": n_clumps, "frontPuffs": n_front,
                   "rule": "clumps are instances of one sculpted template per node; every vertex stays under "
                           "allowed_h(x, z) (0.016 round the marks, 0.034 in the centre stage and the wing sweep, "
                           "0.096 at the back and the sides)"},
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227; "
                             "P = world position, or the template position for the cloud clumps",
                   "cleanTexel": "faces with n . D < 0.22 (edge-on or facing away, n in drawing space) or hidden behind "
                                 "another part of their drawing take one clean texel of their own region",
                   "namedTexels": "the cloud base sheet, the rosette rays and the "
                                  "pebbles under the islets take one texel of a named (drawing, region); constUV in "
                                  "model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard, "measured": clr},
        "sheetLayout": {"characters": CHAR_PROPOSAL, "charactersFrom": "model/regions_characters.json" if CHARS_FROM_FILE
                        else "proposal (regions_characters.json not there yet)",
                        "check": "OK" if not lay else lay, "info": info},
        "demoColours": COLOURS, "tris": total, "budget": MAX_TRIS,
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
    save_png(line, os.path.join(WORK, "heaven_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "heaven_drawings_demo.png"))
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


def mannequin(x, z, h0=0.0, wings=True):
    """preview stand-in only (not shipped): Gabriel's size, in the demo colours"""
    mats = {k: flat_mat("pvm_" + k, v, 0.6) for k, v in {
        "skin": "#F2C9A0", "ivory": "#F1E7D2", "gold": "#E6B23E", "sash": "#D9732C", "hair": "#9A6533",
        "wing": "#FFFDF6"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    mb = MB()
    C = (x, h0, z)
    for sg in (-1, 1):
        tube(mb, [(x + sg * 0.035, h0, z), (x + sg * 0.04, h0 + 0.16, z)], 0.026, "gold", seg=10)
        tube(mb, [(x + sg * 0.04, h0 + 0.16, z), (x + sg * 0.035, h0 + 0.32, z)], 0.03, "ivory", seg=10)
        tube(mb, [(x + sg * 0.085, h0 + 0.49, z), (x + sg * 0.15, h0 + 0.33, z + 0.01)], [0.03, 0.02], "ivory", seg=10)
        sphere(mb, (x + sg * 0.09, h0 + 0.50, z), 0.042, "gold", seg=12, rings=8)
    lathe(mb, [(0.0, 0.30), (0.062, 0.30), (0.056, 0.36), (0.064, 0.44), (0.075, 0.50), (0.04, 0.535), (0.0, 0.54)],
          "ivory", C=C, seg=18, sv=0.7)
    lathe(mb, [(0.062, 0.34), (0.062, 0.375)], "sash", C=C, seg=18, sv=0.75)
    sphere(mb, (x, h0 + 0.575, z), 0.042, "skin", seg=14, rings=9, sh=1.1)
    sphere(mb, (x, h0 + 0.585, z - 0.012), 0.045, "hair", seg=14, rings=9, sh=1.05)
    if wings:
        for sg in (-1, 1):
            poly = [(0.03, 0.50), (0.14, 0.60), (0.30, 0.72), (0.50, 0.80), (0.47, 0.60), (0.40, 0.44), (0.30, 0.33),
                    (0.20, 0.27), (0.10, 0.30), (0.04, 0.40)]
            extrude(mb, [(x + sg * a, h0 + b) for a, b in poly], z - 0.05, z - 0.04, "wing")
    ob = make_obj("pv_gabriel", mb, None, origin=(x, 0.0, z), smooth_angle=60)
    ob["pv"] = 1
    return ob


def mode_preview():
    if not STATE.get("objs"):
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "heaven_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "heaven_preview_sheet.png")); sheet.pack()
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
    try:
        pm.use_nodes = True
    except Exception:
        pass
    t = pm.node_tree.nodes.new("ShaderNodeTexImage"); t.image = sheet
    pm.node_tree.links.new(t.outputs[0], pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    me.materials.append(pm)
    tb = bpy.data.meshes.new("tabletop")
    tb.from_pydata([B(-4, -0.004, 4), B(4, -0.004, 4), B(4, -0.004, -4), B(-4, -0.004, -4)], [], [(0, 1, 2, 3)])
    tb.materials.append(flat_mat("pv_wood", "#6E4A33", 0.6))
    link(bpy.data.objects.new("pv_table", tb))
    # golden hour: a warm key from behind the gate, a soft fill from the viewer, a glow at the rosette
    sun = link(bpy.data.objects.new("pv_sun", bpy.data.lights.new("pv_sun", 'SUN')))
    sun.data.angle = math.radians(6); sun.data.energy = 2.6; sun.data.color = (1.0, 0.86, 0.62)
    sun.rotation_euler = (math.radians(50), math.radians(8), math.radians(205))
    fill = link(bpy.data.objects.new("pv_fill", bpy.data.lights.new("pv_fill", 'AREA')))
    fill.data.size = 1.6; fill.data.energy = 14.0; fill.data.color = (1.0, 0.93, 0.82)
    fill.location = B(-0.2, 0.9, 1.3); fill.rotation_euler = (B(0, 0.1, -0.2) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    gl = bpy.data.lights.new("pv_glow", 'POINT'); gl.color = (1.0, 0.70, 0.30); gl.energy = 0.35; gl.shadow_soft_size = 0.03
    glo = link(bpy.data.objects.new("pv_glow", gl)); glo.location = B(ROSETTE[0], ROSETTE[1], ZG + 0.06)
    sc.world = bpy.data.worlds.new("w")
    try:
        sc.world.use_nodes = True
    except Exception:
        pass
    bg = sc.world.node_tree.nodes["Background"]
    bg.inputs[0].default_value = (1.0, 0.80, 0.55, 1); bg.inputs[1].default_value = 0.6
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

    def cast(spec):
        for o in [o for o in bpy.data.objects if o.get("pv")]:
            bpy.data.objects.remove(o, do_unlink=True)
        if spec:
            mannequin(*spec)
    phone = ((-0.05, 1.05, 1.55), (-0.02, 0.18, -0.30), 55, (720, 1280))
    cast(None)
    shoot("heaven_preview_phone_set", *phone)
    shoot("heaven_preview_front", (0.0, 0.26, 2.3), (0.0, 0.16, -0.25), 21, (1600, 1000))
    shoot("heaven_preview_orbit", orbit((0.0, 0.10, -0.19), 0.95, 0.46, -20), (0.0, 0.10, -0.19), 50, (1280, 720))
    shoot("heaven_preview_gate", (0.06, 0.20, -0.02), (0.0, 0.17, -0.50), 50, (1200, 900))
    shoot("heaven_preview_island", (-0.20, 0.27, 0.10), (-0.44, 0.22, -0.30), 40, (1000, 800))
    shoot("heaven_preview_low", (0.34, 0.10, 0.62), (0.0, 0.13, -0.30), 40, (1280, 720))
    cast((STAND[0], STAND[1]))
    shoot("heaven_preview_phone", *phone)
    shoot("heaven_preview_stage", (0.18, 0.42, 1.25), (0.0, 0.30, -0.10), 40, (1280, 900))
    cast(None)
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "heaven_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["heaven", "clouds", "gate", "gateGlow", "islandL", "islandR", "frontClouds"]


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
    pos = {n: [round(c, 4) for c in D(bpy.data.objects[n].matrix_world.translation)] for n in NEED[1:] if n in names}
    ok = not missing and tris <= MAX_TRIS and uv_bad == 0
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "parents": parents, "origins": pos}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
