"""Blender (headless): the David & Goliath paper desert, desert boost (CONTRACT §12) -> assets/david-goliath/model/desert.glb

Every piece is built from assets/david-goliath/design.json desert.pieces (Design role, version 3); the Sheet role prints
desert.print from the same file, so print and 3D cannot drift. Details and formats: docs/david-goliath/DESERT.md.

Coordinates. A piece stands on the page at design/glTF (x, h, z) with z = -d, where d is the sheet height ys above the
art rectangle's bottom edge. In Blender (Z up) we build directly in (X, Y, Z) = (x, d, h); export_yup turns that into
glTF (x, h, -d).

Two kinds of piece (§12.1):
  front  hills, dunes, rocks, shrub, tents, banner cloths: upright volumes whose front orthographic silhouette equals
         design.json silhouette3D. Height field h(x, d) = top(x) * p(d) (§12.1 depth profile). UV0 = front projection
         u = x / scale + sheetX + 0.5, v = (h / scale + sheetY) / artHeightUnits, pulled INSET inside the printed
         drawing so the erased ink line is never sampled.
  ground brook (water film, no UV) and fiveStones (constant UV), top-down as §11.9.

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/dg_desert.py -- build     meshes + desert.glb + desert_lines.json + ID render
  blender -b --factory-startup --python pipeline/dg_desert.py -- verify    re-import desert.glb and check it
  blender -b --factory-startup --python pipeline/dg_desert.py -- preview   phone-view renders with the animated characters
  blender -b --factory-startup --python pipeline/dg_desert.py -- all       build, verify, preview
Intermediate renders go to $DG_WORK (default /tmp/dg_work); shipped previews are model/desert_preview_*.png.
"""
import bpy, bmesh, math, os, sys, json, random, zlib
import numpy as np
from mathutils import Vector, Matrix, Quaternion, noise
from mathutils.geometry import delaunay_2d_cdt
from mathutils.bvhtree import BVHTree

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = json.load(open(os.path.join(ROOT, "assets/david-goliath/design.json")))
DES = DESIGN["desert"]
PIECES = {p["id"]: p for p in DES["pieces"]}
MODEL = os.path.join(ROOT, "assets/david-goliath/model")
ANIM = os.path.join(ROOT, "assets/david-goliath/anim")
GLB = os.path.join(MODEL, "desert.glb")
LINES = os.path.join(MODEL, "desert_lines.json")
WORK = os.environ.get("DG_WORK", "/tmp/dg_work")
os.makedirs(WORK, exist_ok=True)

ART_H = DESIGN["artHeightUnits"]                       # 1.227
INSET = 0.004                                          # UV inset inside the printed outline (4 px of the 1000 px art rect)
PAPER = (-0.596, 0.596, -0.22, 1.486)                  # x min/max, d min/max (D8: page edge minus 0.024)
PAGE_YS_MIN = (DESIGN["sheet"]["art"][1] + DESIGN["sheet"]["art"][3] - DESIGN["sheet"]["page"][1]) / DESIGN["sheet"]["art"][2]
STAGE_CAP = 0.010
SINK = 0.002                                           # zero-height edges sink under the page (no light leak)
MAX_TRIS = DES["budget"]["maxTris"]
CAP = DES["heightCap"]
FRONT_ZONE = DES["frontZone"]
SPEAR_SHAFT_UV = (-0.160 + 0.5, 0.50 / ART_H)          # Goliath's printed spear shaft (§11.8: sheet x -0.160) = wood
EXPECTED = [p["id"] for p in DES["pieces"]]
FRONT_KINDS = ("hill", "dune", "rock", "shrub", "tent", "banner")
def rng(name):
    return random.Random(zlib.crc32(name.encode()))


# ============================================================================================ 2D geometry (numpy)
def poly_np(geom):
    a = np.array(geom, float)
    if np.allclose(a[0], a[-1]):
        a = a[:-1]
    x, y = a[:, 0], a[:, 1]
    if 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y) < 0:   # make counter-clockwise
        a = a[::-1].copy()
    return a


def seg_dist(P, A, B):
    """distance from points P (N,2) to segments A->B (M,2): (dist, segment index, closest point)."""
    P = np.atleast_2d(P)
    AB = B - A; L2 = (AB ** 2).sum(1); L2[L2 == 0] = 1e-12
    out_d = np.empty(len(P)); out_i = np.empty(len(P), int); out_c = np.empty((len(P), 2))
    for s in range(0, len(P), 2048):                  # chunked to keep memory small
        Q = P[s:s + 2048]
        t = np.clip(((Q[:, None, :] - A[None]) * AB[None]).sum(2) / L2[None], 0, 1)
        C = A[None] + t[..., None] * AB[None]
        d = np.linalg.norm(Q[:, None, :] - C, axis=2)
        i = d.argmin(1); r = np.arange(len(Q))
        out_d[s:s + 2048] = d[r, i]; out_i[s:s + 2048] = i; out_c[s:s + 2048] = C[r, i]
    return out_d, out_i, out_c


def poly_dist(P, poly):
    return seg_dist(P, poly, np.roll(poly, -1, axis=0))


def line_dist(P, line):
    return seg_dist(P, line[:-1], line[1:])


def inside(P, poly):
    P = np.atleast_2d(P); x, y = P[:, 0:1], P[:, 1:2]
    ax, ay = poly[:, 0][None], poly[:, 1][None]
    bx, by = np.roll(poly[:, 0], -1)[None], np.roll(poly[:, 1], -1)[None]
    cond = (ay > y) != (by > y)
    xint = ax + (y - ay) * (bx - ax) / np.where(by - ay == 0, 1e-12, by - ay)
    return (np.sum(cond & (x < xint), axis=1) % 2) == 1


def signed_inside_dist(P, poly):
    d, i, c = poly_dist(P, poly)
    return np.where(inside(P, poly), d, -d), i, c


def resample(line, step, closed):
    pts = np.vstack([line, line[:1]]) if closed else line
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts[:-1], pts[1:]):
        L = np.linalg.norm(b - a)
        if L < 1e-9:
            continue
        t = step - acc
        while t < L:
            out.append(a + (b - a) * t / L); t += step
        acc = L - (t - step)
    if not closed:
        out.append(pts[-1])
    elif np.linalg.norm(out[-1] - out[0]) < step * 0.4:
        out.pop()
    return np.array(out)


def grid_inside(poly, sx, sy, margin):
    lo, hi = poly.min(0), poly.max(0)
    pts = []
    for j, y in enumerate(np.arange(lo[1] + sy * 0.5, hi[1], sy)):
        off = (j % 2) * sx * 0.5
        for x in np.arange(lo[0] + off + sx * 0.25, hi[0], sx):
            pts.append((x, y))
    P = np.array(pts)
    d, _, _ = signed_inside_dist(P, poly)
    return P[d > margin]


def pole_of_inaccessibility(poly, exclude=None, step=0.002):
    P = grid_inside(poly, step, step, 0.0)
    d, _, _ = poly_dist(P, poly)
    if exclude is not None:
        for line, closed in exclude:
            d2 = (poly_dist(P, line) if closed else line_dist(P, line))[0]
            d = np.minimum(d, d2)
    k = int(d.argmax())
    return P[k], float(d[k])


def smoothstep(t):
    t = np.clip(t, 0, 1)
    return t * t * (3 - 2 * t)


def cdt(boundary, interior, extra_lines=()):
    """constrained Delaunay of a closed boundary + interior points + open constraint polylines -> (verts2d, tris)."""
    verts = [Vector((float(x), float(y))) for x, y in boundary]
    K = len(verts)
    edges = [(i, (i + 1) % K) for i in range(K)]
    for line in extra_lines:
        s = len(verts)
        verts += [Vector((float(x), float(y))) for x, y in line]
        edges += [(s + i, s + i + 1) for i in range(len(line) - 1)]
    verts += [Vector((float(x), float(y))) for x, y in interior]
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [list(range(K))], 1, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])
    T = [tuple(f) for f in fs if len(f) == 3]
    # drop triangles outside the footprint (CDT keeps the convex hull of constraint lines otherwise)
    cen = np.array([V[list(t)].mean(0) for t in T])
    keep = inside(cen, boundary)
    return V, [t for t, k in zip(T, keep) if k]


def adjacency(n, tris):
    nb = [set() for _ in range(n)]
    for a, b, c in tris:
        nb[a] |= {b, c}; nb[b] |= {a, c}; nb[c] |= {a, b}
    return [np.array(sorted(s), int) for s in nb]


def laplace(h, nb, movable, iters, f=0.5):
    h = h.copy()
    idx = np.nonzero(movable)[0]
    for _ in range(iters):
        avg = np.array([h[nb[i]].mean() if len(nb[i]) else h[i] for i in idx])
        h[idx] = h[idx] * (1 - f) + avg * f
    return h


# ============================================================================================ Blender helpers
def reset():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def new_obj(name, verts, faces, smooth=True, parent=None):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(map(float, v)) for v in verts], [], [tuple(f) for f in faces])
    me.validate(); me.update()
    for p in me.polygons:
        p.use_smooth = smooth
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    if parent is not None:
        ob.parent = parent
    return ob


def set_uv(ob, fn):
    """fn(N x 3 vertex coords) -> N x 2 uv; written per loop."""
    me = ob.data
    co = np.array([v.co[:] for v in me.vertices]) if len(me.vertices) else np.zeros((0, 3))
    uv = fn(co)
    lay = me.uv_layers.new(name="UVMap")
    lv = np.array([l.vertex_index for l in me.loops], int)
    lay.data.foreach_set("uv", uv[lv].astype(np.float32).ravel())


def uv_topdown(poly):
    def fn(co):
        P = co[:, :2]
        d, i, _ = signed_inside_dist(P, poly)
        A = poly[i]; B = np.roll(poly, -1, axis=0)[i]
        t = B - A; t /= np.linalg.norm(t, axis=1)[:, None] + 1e-12
        n_in = np.stack([-t[:, 1], t[:, 0]], 1)                 # CCW polygon: left normal points inside
        push = np.maximum(0.0, INSET - d)[:, None]
        Q = P + n_in * push
        return np.stack([Q[:, 0] + 0.5, Q[:, 1] / ART_H], 1)
    return fn


def uv_const(u, v):
    return lambda co: np.tile(np.array([[u, v]]), (len(co), 1))


def tri_count(ob):
    return sum(len(p.vertices) - 2 for p in ob.data.polygons)


# ============================================================================================ pieces


# ============================================================================================ front pieces: profiles
def envelope(sil, xs):
    """upper envelope of a closed silhouette polygon (x, y) at xs: max y of the polygon on each vertical line."""
    a = np.array(sil, float)
    if not np.allclose(a[0], a[-1]):
        a = np.vstack([a, a[:1]])
    A, B = a[:-1], a[1:]
    xs = np.asarray(xs, float)
    lo, hi = np.minimum(A[:, 0], B[:, 0]), np.maximum(A[:, 0], B[:, 0])
    dx = np.where(np.abs(B[:, 0] - A[:, 0]) < 1e-12, 1e-12, B[:, 0] - A[:, 0])
    t = (xs[:, None] - A[None, :, 0]) / dx[None]
    y = A[None, :, 1] + t * (B[None, :, 1] - A[None, :, 1])
    vert = np.abs(B[:, 0] - A[:, 0]) < 1e-9                    # vertical edges: their top end
    y = np.where(vert[None], np.maximum(A[:, 1], B[:, 1])[None], y)
    ok = (xs[:, None] >= lo[None] - 1e-9) & (xs[:, None] <= hi[None] + 1e-9)
    return np.where(ok, y, -1.0).max(1).clip(0, None)


def profile_samples(sil, step, extra=()):
    """x samples along the silhouette top, spaced by arc length of (x, top(x)); keeps peaks and the silhouette's
    own top vertices so the front silhouette of the mesh equals silhouette3D."""
    a = np.array(sil, float)
    x0, x1 = a[:, 0].min(), a[:, 0].max()
    xd = np.linspace(x0, x1, max(200, int((x1 - x0) / 0.0004)))
    yd = envelope(sil, xd)
    s = np.concatenate([[0], np.cumsum(np.hypot(np.diff(xd), np.diff(yd)))])
    n = max(3, int(round(s[-1] / step)) + 1)
    xs = list(np.interp(np.linspace(0, s[-1], n), s, xd))
    ev = envelope(sil, a[:, 0])
    xs += [x for (x, y), e in zip(a, ev) if abs(y - e) < 1e-6]        # silhouette vertices on the top
    xs += [float(xd[int(yd.argmax())])] + list(extra)
    xs = np.unique(np.round(np.array(xs), 6))
    keep = [xs[0]]
    for x in xs[1:]:
        if x - keep[-1] > 0.0012 or x == xs[-1]:
            keep.append(x)
    return np.array(keep)


def depth_p(d, D, front_eff=None):
    """§12.1 depth profile p(d) in [0, 1] (d = -z); front_eff may move the front foot per sample."""
    f = D["front"] if front_eff is None else front_eff
    t1 = np.clip((d - f) / np.maximum(1e-6, D["crestFrom"] - f), 0, 1)
    rise = t1 * t1 * (3 - 2 * t1)
    t2 = np.clip((d - D["crestTo"]) / max(1e-6, D["back"] - D["crestTo"]), 0, 1)
    fall = 1 - t2 * t2
    p = np.where(d < D["crestFrom"], rise, np.where(d > D["crestTo"], fall, 1.0))
    return np.where((d < f - 1e-9) | (d > D["back"] + 1e-9), 0.0, p)


def dz(p):
    """design depthZ (z, negative) -> d values (positive, front < back)"""
    z = p["depthZ"]
    return {"front": -z["front"], "crestFrom": -z["crestFrom"], "crestTo": -z["crestTo"], "back": -z["back"]}


def sheet_of(p, x, h):
    """front projection: 3D (x, h) -> sheet (x, ys) of the drawing"""
    m = p["frontUV"]
    return np.stack([np.asarray(x) / m["scale"] + m["sheetX"], np.asarray(h) / m["scale"] + m["sheetY"]], -1)


def push_inside(P, poly, inset):
    """move points that are outside poly or closer than inset to its outline to inset inside (nearest edge)."""
    d, i, c = signed_inside_dist(P, poly)
    A = poly[i]; B = np.roll(poly, -1, axis=0)[i]
    t = B - A; t /= np.linalg.norm(t, axis=1)[:, None] + 1e-12
    n_in = np.stack([-t[:, 1], t[:, 0]], 1)
    bad = d < inset
    Q = P.copy()
    Q[bad] = c[bad] + n_in[bad] * inset
    still = bad & ~inside(Q, poly)                  # concave corners: step toward the pole of the drawing
    if still.any():
        pole, _ = pole_of_inaccessibility(poly, step=0.003)
        for k in np.nonzero(still)[0]:
            for f in np.linspace(0.1, 1.0, 10):
                q = Q[k] + (pole - Q[k]) * f
                if inside(q[None], poly)[0] and poly_dist(q[None], poly)[0][0] >= inset * 0.7:
                    Q[k] = q; break
    return Q


def push_outside(P, poly, gap):
    d, i, c = signed_inside_dist(P, poly)
    A = poly[i]; B = np.roll(poly, -1, axis=0)[i]
    t = B - A; t /= np.linalg.norm(t, axis=1)[:, None] + 1e-12
    n_out = -np.stack([-t[:, 1], t[:, 0]], 1)
    bad = d > -gap
    Q = P.copy(); Q[bad] = c[bad] + n_out[bad] * gap
    return Q


def uv_front(p, owner=None, exclude=None):
    """UV0 = front projection of (x, h) into the piece's drawing, pulled INSET inside it (and out of exclude)."""
    poly = poly_np(owner if owner is not None else p["geomSheet"][0])
    exc = poly_np(exclude) if exclude is not None else None

    def fn(co):
        P = sheet_of(p, co[:, 0], co[:, 2])
        Q = push_inside(P, poly, INSET)
        if exc is not None:
            Q = push_outside(Q, exc, INSET)
            Q = push_inside(Q, poly, INSET * 0.75)
        return np.stack([Q[:, 0] + 0.5, Q[:, 1] / ART_H], 1)
    return fn


def mark_sharp_columns(ob, xs_sharp, tol=1e-6):
    """mark mesh edges whose two ends share one of the given x values as sharp (crisp brink / ridge)."""
    me = ob.data
    co = np.array([v.co[:] for v in me.vertices])
    for e in me.edges:
        a, b = co[e.vertices[0]], co[e.vertices[1]]
        if any(abs(a[0] - x) < tol and abs(b[0] - x) < tol for x in xs_sharp):
            e.use_edge_sharp = True


# ============================================================================================ front height fields
def ripple(x, d, wl, phase):
    """sand ripple pattern, crests roughly along x (like the ground shader of §12.4), asymmetric (steep lee side)."""
    th = 2 * math.pi * (d / wl + 0.45 * np.sin(2 * math.pi * x / 0.23 + phase) + 0.25 * np.sin(2 * math.pi * x / 0.071 + 2 * phase))
    return 0.5 + 0.5 * (np.sin(th) + 0.28 * np.sin(2 * th)) / 1.12


def build_field(p, parent, *, step, n_rise, n_plateau=2, n_fall=3, round_front=0.0, crest_wobble=0.0, foot_wave=0.0,
                ripple_wl=0.0, ripple_amp=0.0, smooth=True, sharp_peak=False, rock=False):
    """height field h(x, d) = top(x) * p(d) on a curvilinear grid: columns at profile samples, rows following the
    (optionally rounded) front foot, the crest band and the hidden back slope."""
    r = rng(p["id"])
    sil = p["silhouette3D"]; D = dz(p)
    xs = profile_samples(sil, step)
    top = envelope(sil, xs)
    x0, x1 = xs[0], xs[-1]
    walls = []
    if top[0] > 1e-4:
        xs = np.concatenate([[x0 - 1e-5], xs]); top = np.concatenate([[0.0], top]); walls.append(0)
    if top[-1] > 1e-4:
        xs = np.concatenate([xs, [x1 + 1e-5]]); top = np.concatenate([top, [0.0]]); walls.append(len(xs) - 1)
    xm, hw = (x0 + x1) / 2, (x1 - x0) / 2
    e = np.clip(1 - ((xs - xm) / hw) ** 2, 0, 1)
    phase = r.uniform(0, 6.28)
    if rock:
        rise = D["crestFrom"] - D["front"]
        jit = np.array([r.uniform(0, 0.35) for _ in xs]) * rise
        f_eff = D["front"] + jit
        rows_t = [("r", 0.0), ("r", 0.35), ("r", 1.0), ("c", 0.5), ("b", 0.0), ("b", 0.65), ("b", 1.0)]
    else:
        f_eff = D["front"] + round_front * (1 - np.sqrt(e))
        if foot_wave > 0:                                         # spurs and hollows: the front foot meanders
            f_eff = f_eff + foot_wave * (0.5 + 0.5 * np.array([noise.noise(Vector((x * 11.0, 4.7, phase))) for x in xs]))
        f_eff = np.minimum(f_eff, D["crestFrom"] - 0.02)
        rows_t = [("r", t) for t in np.linspace(0, 1, n_rise + 1)]
        rows_t += [("c", t) for t in np.linspace(0, 1, n_plateau + 1)[1:-1]]
        rows_t += [("b", t) for t in np.linspace(0, 1, n_fall + 1)]
    cw = np.array([noise.noise(Vector((x * 7.0, 1.3, phase))) for x in xs]) * crest_wobble
    cf = np.clip(D["crestFrom"] + cw, f_eff + 0.01, D["crestTo"] - 1e-4)
    verts = []
    grid = np.zeros((len(rows_t), len(xs)), int)
    for i, (kind, t) in enumerate(rows_t):
        for j, x in enumerate(xs):
            if kind == "r":
                d = f_eff[j] + t * (cf[j] - f_eff[j])
                t1 = t; pv = t1 * t1 * (3 - 2 * t1)
                if rock:
                    pv = math.sqrt(min(1.0, (d - D["front"]) / 0.012)) if d > D["front"] else 0.0
                    pv = max(pv, 0.0) if t > 0 else 0.0
            elif kind == "c":
                d = cf[j] + t * (D["crestTo"] - cf[j]); pv = 1.0
            else:
                d = D["crestTo"] + t * (D["back"] - D["crestTo"])
                pv = 1 - t * t
                if rock:
                    pv = math.sqrt(min(1.0, (D["back"] - d) / 0.012))
            h = top[j] * pv
            if rock and kind != "b":                                  # flat tilted top: highest at the front brink
                h *= 1.0 - 0.10 * max(0.0, (d - cf[j]) / max(1e-6, D["back"] - cf[j]))
            if ripple_amp > 0 and kind == "r" and 0 < t < 1:
                w = 4 * pv * (1 - pv)
                a = min(ripple_amp, 0.08 * top[j])
                h -= a * w * float(ripple(x, d, ripple_wl, phase))
            if h <= 1e-5 or j in walls:
                h = -SINK
            grid[i, j] = len(verts); verts.append((x, d, h))
    faces = []
    V = np.array(verts)
    for i in range(len(rows_t) - 1):
        for j in range(len(xs) - 1):
            q = (grid[i, j], grid[i, j + 1], grid[i + 1, j + 1], grid[i + 1, j])
            if max(V[k, 2] for k in q) <= 0:
                continue
            a, b, c, dd = q                                           # split along the shorter diagonal
            if np.linalg.norm(V[a] - V[c]) <= np.linalg.norm(V[b] - V[dd]):
                faces += [(a, b, c), (a, c, dd)]
            else:
                faces += [(a, b, dd), (b, c, dd)]
    used = sorted({k for f in faces for k in f})
    remap = {k: n for n, k in enumerate(used)}
    ob = new_obj(p["id"], V[used], [tuple(remap[k] for k in f) for f in faces], smooth=smooth, parent=parent)
    bm = bmesh.new(); bm.from_mesh(ob.data)
    for f in bm.faces:
        f.normal_update()
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if sum(f.normal.z * f.calc_area() for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(ob.data); bm.free()
    if sharp_peak:
        mark_sharp_columns(ob, [float(xs[int(top.argmax())])])
    return ob, xs, top


def uv_hill(p):
    """front UV for a hill, kept out of the drawings of the tents standing on it: a hill vertex whose projection lands
    in a tent drawing (the strip just in front of the gable) samples the hill just below that tent instead."""
    base = uv_front(p)
    poly = poly_np(p["geomSheet"][0])
    tents = [poly_np(t["geomSheet"][0]) for t in DES["pieces"] if t.get("onHill") == p["id"] and t["kind"] == "tent"]

    def fn(co):
        uv = base(co)
        Q = np.stack([uv[:, 0] - 0.5, uv[:, 1] * ART_H], 1)
        for t in tents:
            lo, hi = t.min(0), t.max(0)
            hit = (Q[:, 0] > lo[0] - INSET) & (Q[:, 0] < hi[0] + INSET) & (Q[:, 1] > lo[1] - INSET)
            Q[hit, 1] = lo[1] - 1.5 * INSET
        Q = push_inside(Q, poly, INSET * 0.75)
        return np.stack([Q[:, 0] + 0.5, Q[:, 1] / ART_H], 1)
    return fn


def build_hill(p, parent):
    ob, xs, top = build_field(p, parent, step=0.018, n_rise=24, n_plateau=2, n_fall=2, round_front=0.09,
                              crest_wobble=0.025, foot_wave=0.10, ripple_wl=0.062, ripple_amp=0.007)
    set_uv(ob, uv_hill(p))
    return ob, {"kind": "hill"}


def build_dune(p, parent):
    big = p["id"] == "duneFar"
    rise = dz(p)["crestFrom"] - dz(p)["front"]
    ob, xs, top = build_field(p, parent, step=0.014 if big else 0.011, n_rise=6 if big else max(8, int(rise / 0.011)),
                              n_plateau=1, n_fall=2, round_front=min(0.06, 0.35 * rise), crest_wobble=0.012, foot_wave=0.25 * rise,
                              ripple_wl=0.0 if big else 0.044, ripple_amp=0.0 if big else 0.006, sharp_peak=True)
    set_uv(ob, uv_front(p))
    k = int(top.argmax())
    return ob, {"kind": "dune", "brinkX": round(float(xs[k]), 4), "brinkH": round(float(top[k]), 4),
                "slipFace": "-x (wind from +X)"}


def build_rock(p, parent):
    ob, xs, top = build_field(p, parent, step=0.02, n_rise=2, smooth=False, rock=True)
    set_uv(ob, uv_front(p))
    return ob, {"kind": "rock"}


def build_shrub(p, parent):
    ob, xs, top = build_field(p, parent, step=0.004, n_rise=3, n_plateau=1, n_fall=2, smooth=False)
    me = ob.data; r = rng(p["id"])                      # crumple the inside a little (dry twiggy clump)
    for v in me.vertices:
        if v.co.z > 0.004:
            v.co.z *= 1.0 - 0.18 * r.random() * (1 if v.co.z < 0.92 * envelope(p["silhouette3D"], [v.co.x])[0] else 0)
    set_uv(ob, uv_front(p))
    return ob, {"kind": "shrub"}


# ============================================================================================ tents and banners
def hill_top(hill, x):
    return float(envelope(hill["silhouette3D"], [x])[0])


def build_tent(p, parent):
    """A-frame cloth tent: the gable (= silhouette3D, the drawing's triangle) faces +Z toward the viewer, the ridge runs
    back along -Z and sags 0.006 between the poles, a triangular doorway is recessed into the gable. Flat-shaded."""
    T = p["tent"]; hill = PIECES[p["onHill"]]
    a = np.array(p["silhouette3D"][:-1], float)        # x0,low  x0,eave  bend  apex  bend  x1,eave  x1,low
    pts = [tuple(v) for v in a]
    low = min(hill_top(hill, x) for x in np.linspace(a[:, 0].min(), a[:, 0].max(), 12)) - 0.006
    lowY = min(a[:, 1].min(), low)
    ring = [(x, lowY if y <= T["baseY"] - T["skirt"] + 1e-6 else y) for x, y in pts]
    if 0.5 * sum(ring[i][0] * ring[(i + 1) % len(ring)][1] - ring[(i + 1) % len(ring)][0] * ring[i][1] for i in range(len(ring))) < 0:
        ring = ring[::-1]
    door = poly_np(p["parts3D"]["tentDoor"])
    zG, zB = -T["zGable"], -T["zBack"]                 # d of gable and back
    sag = 0.006; base = T["baseY"]; apex = max(y for _, y in ring)
    rings = []
    verts, faces = [], []
    for d, s in ((zG, 0.0), ((zG + zB) / 2, sag), (zB, 0.0)):
        idx = []
        for x, y in ring:
            roof = max(0.0, (y - base) / (apex - base))
            idx.append(len(verts)); verts.append((x, d, y - s * roof))
        rings.append(idx)
    n = len(ring)
    bottom = [k for k in range(n) if ring[k][1] <= lowY + 1e-9 and ring[(k + 1) % n][1] <= lowY + 1e-9]
    for r0, r1 in zip(rings[:-1], rings[1:]):
        for k in range(n):
            if k in bottom:
                continue
            k2 = (k + 1) % n
            faces.append((r0[k], r0[k2], r1[k2], r1[k]))
    back = rings[-1]
    faces.append(tuple(reversed(back)))
    # gable with the door hole (CDT), then the recess
    V2, tris = cdt(np.array(ring), np.zeros((0, 2)), [np.vstack([door, door[:1]])])
    cen = np.array([V2[list(t)].mean(0) for t in tris])
    tris = [t for t, c in zip(tris, ~inside(cen, door)) if c]
    s0 = len(verts)
    verts += [(x, zG, y) for x, y in V2]
    faces += [tuple(s0 + k for k in t) for t in tris]
    rec = T["door"]["recess"]
    dfront = [len(verts) + k for k in range(len(door))]; verts += [(x, zG, y) for x, y in door]
    dback = [len(verts) + k for k in range(len(door))]; verts += [(x, zG + rec, y) for x, y in door]
    for k in range(len(door)):
        k2 = (k + 1) % len(door)
        faces.append((dfront[k], dback[k], dback[k2], dfront[k2]))
    faces.append(tuple(dback))
    ob = new_obj(p["id"], verts, faces, smooth=False, parent=parent)
    me = ob.data; me.validate(); me.update()
    bm = bmesh.new(); bm.from_mesh(me)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bm.faces.ensure_lookup_table()
    gable = [f for f in bm.faces if abs(f.calc_center_median().y - zG) < 1e-6 and abs(f.normal.y) > 0.9]
    if gable and sum(f.normal.y for f in gable) > 0:          # the gable must face the viewer (-Y in Blender = +Z glTF)
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(me); bm.free()
    # UV: door recess samples the door drawing; everything else the tent drawing outside the door
    tent_fn = uv_front(p, exclude=[(x / p["frontUV"]["scale"], y / p["frontUV"]["scale"] + p["frontUV"]["sheetY"]) for x, y in door])
    door_sheet = [(x / p["frontUV"]["scale"], y / p["frontUV"]["scale"] + p["frontUV"]["sheetY"]) for x, y in door]
    door_fn = uv_front(p, owner=door_sheet)
    co = np.array([v.co[:] for v in me.vertices])
    uv_t, uv_d = tent_fn(co), door_fn(co)
    lay = me.uv_layers.new(name="UVMap")
    out = []
    for poly_ in me.polygons:
        c = poly_.center
        is_door = (zG + 1e-5 < c.y <= zG + rec + 1e-5)
        for li in poly_.loop_indices:
            vi = me.loops[li].vertex_index
            out.append(uv_d[vi] if is_door else uv_t[vi])
    lay.data.foreach_set("uv", np.array(out, np.float32).ravel())
    return ob, {"kind": "tent", "gableSheet": sheet_of(p, a[:, 0], a[:, 1]).round(4).tolist(),
                "doorSheet": np.array(door_sheet).round(4).tolist(), "skirtBottom3D": round(lowY, 4)}


def build_banner(p, parent):
    B = p["banner"]; pid = p["id"]
    px, by, pz = B["poleBase3D"]; d = -pz
    ph = B["poleHeight"]; rp = B["poleDiameter"] / 2
    z0 = by - 0.010; ztop = by + ph
    cl = poly_np(p["silhouette3D"])
    side = 1.0 if cl[:, 0].mean() > px else -1.0
    L = float(np.abs(cl[:, 0] - px).max())
    yc = float(cl[:, 1].mean())
    arm = bpy.data.armatures.new(pid + "_arm")
    rig = bpy.data.objects.new(pid, arm); bpy.context.scene.collection.objects.link(rig); rig.parent = parent
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    b0 = arm.edit_bones.new(pid + "_bPole"); b0.head = (px, d, z0); b0.tail = (px, d, ztop)
    b1 = arm.edit_bones.new(pid + "_bCloth1"); b1.head = (px, d, yc); b1.tail = (px + side * L / 2, d, yc)
    b2 = arm.edit_bones.new(pid + "_bCloth2"); b2.head = b1.tail; b2.tail = (px + side * L, d, yc)
    b1.parent = b0; b2.parent = b1; b2.use_connect = True
    for b in (b0, b1, b2):
        b.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')
    # pole: hexagonal shaft + knob (knob top = heightMax)
    verts, faces = [], []
    nseg = 6
    for z in (z0, ztop):
        for k in range(nseg):
            a = 2 * math.pi * k / nseg
            verts.append((px + rp * math.cos(a), d + rp * math.sin(a), z))
    for k in range(nseg):
        faces.append((k, (k + 1) % nseg, nseg + (k + 1) % nseg, nseg + k))
    tip = len(verts); verts.append((px, d, ztop + 0.006))
    for k in range(nseg):
        faces.append((nseg + k, nseg + (k + 1) % nseg, tip))
    pole = new_obj(pid + "_pole", verts, faces, smooth=True, parent=rig)
    set_uv(pole, uv_const(*SPEAR_SHAFT_UV))
    # cloth: the drawn swallow-tail outline in the XY plane (front UV), with interior points so the wave bends it
    I = grid_inside(cl, 0.010, 0.009, 0.003)
    V2, tris = cdt(resample(cl, 0.006, True), I)
    cv = [(x, d - 0.0005, y) for x, y in V2]
    m = len(cv)
    cv += [(x, d + 0.0005, y) for x, y in V2]
    cf = [tuple(t) for t in tris] + [tuple(reversed([k + m for k in t])) for t in tris]
    cloth = new_obj(pid + "_cloth", cv, cf, smooth=True, parent=rig)
    bm = bmesh.new(); bm.from_mesh(cloth.data); bm.faces.ensure_lookup_table()
    front = bm.faces[:len(tris)]
    if sum(f.normal.y for f in front) > 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(cloth.data); bm.free()
    set_uv(cloth, uv_front(p))
    w = [min(1.0, abs(x - px) / L) for x, _, _ in cv]
    for ob in (pole, cloth):
        for name in (pid + "_bPole", pid + "_bCloth1", pid + "_bCloth2"):
            ob.vertex_groups.new(name=name)
    for vi in range(len(pole.data.vertices)):
        pole.vertex_groups[pid + "_bPole"].add([vi], 1.0, 'REPLACE')
    for vi, s in enumerate(w):
        wp = max(0.0, 1 - s / 0.10)
        w1 = max(0.0, 1 - abs(s - 0.35) / 0.45) * (1 - wp)
        w2 = max(0.0, (s - 0.25) / 0.75) * (1 - wp)
        tot = wp + w1 + w2
        for name, val in ((pid + "_bPole", wp), (pid + "_bCloth1", w1), (pid + "_bCloth2", w2)):
            if val > 0:
                cloth.vertex_groups[name].add([vi], val / tot, 'REPLACE')
    for ob in (pole, cloth):
        mod = ob.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
    # wave (loops: frame 1 == frame 49 at 24 fps = 2 s); the cloth swings about the vertical, in and out of the page
    act = bpy.data.actions.new(pid + "Wave")
    rig.animation_data_create(); rig.animation_data.action = act
    up = Vector((0, 0, 1))
    for bn, amp, lag in ((pid + "_bCloth1", 12.0, 0.0), (pid + "_bCloth2", 20.0, 1.1)):
        pb = rig.pose.bones[bn]; pb.rotation_mode = 'QUATERNION'
        axis = (rig.data.bones[bn].matrix_local.to_3x3().inverted() @ up).normalized()
        for f in range(1, 50, 4):
            ang = math.radians(amp) * math.sin(2 * math.pi * (f - 1) / 48 - lag)
            pb.rotation_quaternion = Quaternion(axis, ang)
            pb.keyframe_insert("rotation_quaternion", frame=f)
    return rig, {"kind": "banner", "poleBase3D": [px, by, pz], "poleTop": round(ztop + 0.006, 4),
                 "clothSide": "+x" if side > 0 else "-x"}


# ============================================================================================ ground pieces
def bank_strips(poly):
    """the brook's two long banks: outline runs that are not the straight end cuts (top and bottom of the strip)."""
    nxt = np.roll(poly, -1, axis=0)
    ylo, yhi = poly[:, 1].min(), poly[:, 1].max()
    flat = (np.abs(poly[:, 1] - nxt[:, 1]) < 1e-4) & ((np.abs(poly[:, 1] - ylo) < 0.002) | (np.abs(poly[:, 1] - yhi) < 0.002))
    runs, cur = [], []
    n = len(poly)
    start = int(np.nonzero(flat)[0][0]) + 1
    for k in range(n):
        i = (start + k) % n
        cur.append(poly[i])
        if flat[i]:
            if len(cur) > 1:
                runs.append(np.array(cur))
            cur = []
    if len(cur) > 1:
        runs.append(np.array(cur))
    return runs


def build_brook(p, parent, sand_uv):
    poly = poly_np(p["geomSheet"][0])
    B = resample(poly, 0.006, True)
    I = grid_inside(poly, 0.008, 0.008, 0.004)
    V, T = cdt(B, I)
    # Blender Y = d = ys here (ground pieces use sheet ys directly, negative below the art rect)
    water = new_obj("brook", np.column_stack([V, np.full(len(V), p["heightMax"])]), T, smooth=True, parent=parent)
    verts, faces = [], []
    prof = [(-0.0040, 0.0), (-0.0018, 0.0042), (0.0004, 0.0052), (0.0030, 0.0030)]   # (inward offset, height)
    for run in bank_strips(poly):
        pts = resample(run, 0.0045, False)
        s = len(verts)
        for k, q in enumerate(pts):
            t = pts[min(k + 1, len(pts) - 1)] - pts[max(k - 1, 0)]; t /= np.linalg.norm(t)
            n_in = np.array([-t[1], t[0]])
            taper = min(1.0, k / 2.0, (len(pts) - 1 - k) / 2.0) if len(pts) > 4 else 1.0
            for off, hgt in prof:
                q2 = q + n_in * off
                verts.append((q2[0], q2[1], hgt * (0.35 + 0.65 * taper)))
        m = len(prof)
        for k in range(len(pts) - 1):
            for j in range(m - 1):
                a = s + k * m + j
                faces.append((a, a + m, a + m + 1, a + 1))
    bank = new_obj("brookBank", verts, faces, smooth=True, parent=water)
    bm = bmesh.new(); bm.from_mesh(bank.data)
    for f in bm.faces:
        f.normal_update()
    if sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    bm.to_mesh(bank.data); bm.free()
    set_uv(bank, uv_const(*sand_uv))
    return water, {"kind": "water", "footprintSheet": poly.round(4).tolist(),
                   "banks": [r.round(4).tolist() for r in bank_strips(poly)]}


def build_stones(p, parent):
    r = rng(p["id"])
    root = bpy.data.objects.new("fiveStones", None); bpy.context.scene.collection.objects.link(root); root.parent = parent
    su, sv = DES["stoneUV"]
    for k, (x, y) in enumerate(p["stonesSheet"]):
        bm = bmesh.new()
        bmesh.ops.create_uvsphere(bm, u_segments=10, v_segments=6, radius=1.0)
        rx, ry = 0.0068 * r.uniform(0.92, 1.08), 0.0056 * r.uniform(0.92, 1.08)
        rot = r.uniform(0, math.pi)
        hz = p["heightMax"] - 0.0035
        for v in bm.verts:
            j = 1 + 0.07 * noise.noise(v.co * 1.7 + Vector((k * 3.0, 0, 0)))
            lx, ly, lz = v.co.x * rx * j, v.co.y * ry * j, v.co.z * hz * j
            if lz < 0:
                lz *= 0.6
            v.co = Vector((x + lx * math.cos(rot) - ly * math.sin(rot), y + lx * math.sin(rot) + ly * math.cos(rot), 0.0035 + lz))
        me = bpy.data.meshes.new(f"stone{k + 1}"); bm.to_mesh(me); bm.free()
        for f in me.polygons:
            f.use_smooth = True
        ob = bpy.data.objects.new(f"stone{k + 1}", me); bpy.context.scene.collection.objects.link(ob); ob.parent = root
        set_uv(ob, uv_const(su, sv))
    return root, {"kind": "stones", "stonesSheet": p["stonesSheet"]}


def page_mat():
    m = bpy.data.materials.new("dg_page"); m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.85
    return m


def water_mat():
    m = bpy.data.materials.new("dg_water"); m.use_nodes = True
    b = m.node_tree.nodes.get("Principled BSDF")
    b.inputs["Base Color"].default_value = (0.42, 0.74, 0.90, 1)
    b.inputs["Alpha"].default_value = 0.42
    b.inputs["Roughness"].default_value = 0.08
    try:
        m.surface_render_method = 'BLENDED'
    except Exception:
        m.blend_method = 'BLEND'
    return m


def sand_texel():
    """one clean texel of dune1's printed windward sand (side view): far from the outline and the slip-face part,
    and as far as possible from any printed line of the Design line-art mock."""
    p = PIECES["dune1"]; poly = poly_np(p["geomSheet"][0])
    sy = p["frontUV"]["sheetY"]
    slip = poly_np([(x, y + sy) for x, y in p["parts3D"]["duneShade"]])
    P = grid_inside(poly, 0.003, 0.003, 0.015)
    P = P[~inside(P, slip)]
    clear = np.minimum(poly_dist(P, poly)[0], poly_dist(P, slip)[0])
    score = clear.copy()
    mock = os.path.join(ROOT, "docs/david-goliath/design/sheet-mock-lineart.png")
    if os.path.exists(mock):
        img = bpy.data.images.load(mock); w, h = img.size
        a = np.array(img.pixels[:], np.float32).reshape(h, w, 4)
        ink = np.argwhere(a[..., :3].max(2) < 0.5)              # (row from bottom, col)
        art = DESIGN["sheet"]["art"]
        col = art[0] + (P[:, 0] + 0.5) * art[2]
        row = h - 1 - (art[1] + art[3] - P[:, 1] * art[2])
        near = ink[(np.abs(ink[:, 1] - col.mean()) < 220) & (np.abs(ink[:, 0] - row.mean()) < 220)]
        if len(near):
            dpx = np.sqrt(((near[None, :, 0] - row[:, None]) ** 2 + (near[None, :, 1] - col[:, None]) ** 2)).min(1)
            score = np.minimum(clear, dpx / art[2])
        bpy.data.images.remove(img)
    k = int(score.argmax()); q = P[k]
    return (float(q[0]) + 0.5, float(q[1]) / ART_H), [round(float(q[0]), 4), round(float(q[1]), 4)], float(score[k])


# ============================================================================================ build
def mode_build():
    reset()
    sc = bpy.context.scene
    root = bpy.data.objects.new("desert", None); sc.collection.objects.link(root)
    lines, built = {}, {}
    for pid, p in PIECES.items():
        k = p["kind"]
        if k == "hill":
            built[pid], lines[pid] = build_hill(p, root)
        elif k == "dune":
            built[pid], lines[pid] = build_dune(p, root)
        elif k == "rock":
            built[pid], lines[pid] = build_rock(p, root)
        elif k == "shrub":
            built[pid], lines[pid] = build_shrub(p, root)
        elif k == "tent":
            built[pid], lines[pid] = build_tent(p, root)
        elif k == "banner":
            built[pid], lines[pid] = build_banner(p, root)
    sand_uv, sand_xy, sand_clear = sand_texel()
    built["brook"], lines["brook"] = build_brook(PIECES["brook"], root, sand_uv)
    built["fiveStones"], lines["fiveStones"] = build_stones(PIECES["fiveStones"], root)
    missing = [k for k in EXPECTED if k not in built]
    assert not missing, missing
    for pid, p in PIECES.items():
        if p.get("mapping") == "front":
            lines[pid].update({"mapping": "front", "frontUV": p["frontUV"], "region": p["region"]})
    pm, wm = page_mat(), water_mat()
    for ob in bpy.data.objects:
        if ob.type == 'MESH':
            ob.data.materials.clear(); ob.data.materials.append(wm if ob.name == "brook" else pm)
    tris = {ob.name: tri_count(ob) for ob in bpy.data.objects if ob.type == 'MESH'}
    total = sum(tris.values())
    print("DESERT_TRIS", total, json.dumps(tris))
    assert total <= MAX_TRIS, f"over budget: {total} > {MAX_TRIS}"
    bpy.ops.object.select_all(action='DESELECT')
    for ob in [root] + list(root.children_recursive):
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    sc.render.fps = 24
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_yup=True, export_apply=False,
                              export_skins=True, export_animations=True, export_def_bones=False,
                              export_texcoords=True, export_normals=True, export_materials='EXPORT',
                              export_morph=False, export_anim_single_armature=False)
    meta = {"generatedBy": "pipeline/dg_desert.py", "contract": "CONTRACT §12",
            "units": "art-width units. Front pieces: 3D (x, h, z); sheet = (x / scale + sheetX, h / scale + sheetY). "
                     "Ground pieces: sheet (x, ys), 3D (x, h, -ys).",
            "uv": {"rule": DES["uvRule"], "inset": INSET, "sandBankUV": list(sand_uv), "sandBankSheet": sand_xy,
                   "sandBankClearance": round(sand_clear, 4), "poleUV": list(SPEAR_SHAFT_UV), "stoneUV": DES["stoneUV"]},
            "tris": tris, "trisTotal": total, "pieces": lines}
    json.dump(meta, open(LINES, "w"), indent=1)
    render_id(built)
    print("BUILD_OK", GLB)


def render_id(built):
    """UV-space ID render in the page frame (1240 x 1754 px, design.json sheet.page): each piece drawn where its UV0
    samples the scanned page (front pieces: their side-view drawing; stones: the constant texel) and the brook at its
    top-down footprint. Later print layers on top, as in desert.print. Lets the Sheet role check print = 3D."""
    sc = bpy.context.scene
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
    sc.render.dither_intensity = 0.0; sc.display.render_aa = 'OFF'; sc.render.film_transparent = True
    sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'MATERIAL'
    sh.show_cavity = False; sh.show_shadows = False; sh.show_object_outline = False; sh.show_specular_highlight = False
    for ob in list(bpy.data.objects):
        ob.hide_render = True
    W, Hp = DESIGN["sheet"]["page"]
    art = DESIGN["sheet"]["art"]; px = art[2]
    order = [s["piece"] for s in DES["print"]["shapes"]]
    layer = {pid: order.index(pid) if pid in order else len(order) for pid in EXPECTED}
    ids = {}
    for k, pid in enumerate(EXPECTED, start=1):
        col = (16 + (k % 15) * 16, 16 + ((k // 15) % 15) * 16, 64 + (k // 225) * 64)
        ids[pid] = {"id": k, "rgb": col}
        m = bpy.data.materials.new("id_" + pid); m.diffuse_color = (*[(c / 255.0) ** 2.2 for c in col], 1)
        z = 0.001 * layer[pid]
        for ob in [built[pid]] + list(built[pid].children_recursive):
            if ob.type != 'MESH' or ob.name.endswith("_pole") or ob.name == "brookBank":
                continue
            me = ob.data
            if pid == "brook":
                verts = [(v.co.x, v.co.y, z) for v in me.vertices]
                faces = [tuple(p.vertices) for p in me.polygons]
            else:
                uv = np.zeros(len(me.loops) * 2); me.uv_layers[0].data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
                verts = [(u - 0.5, v * ART_H, z) for u, v in uv]
                faces = [tuple(p.loop_indices) for p in me.polygons]
            flat = new_obj("id_" + ob.name, verts, faces, smooth=False)
            flat.data.materials.append(m)
    cam = bpy.data.objects.new("IDcam", bpy.data.cameras.new("IDcam")); sc.collection.objects.link(cam); sc.camera = cam
    x_c = (W / 2 - art[0]) / px - 0.5
    y_c = (art[1] + art[3] - Hp / 2) / px
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = Hp / px; cam.location = (x_c, y_c, 2.0); cam.rotation_euler = (0, 0, 0)
    cam.data.clip_start = 0.01; cam.data.clip_end = 10
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, Hp, 100
    sc.render.filepath = os.path.join(WORK, "desert_id.png"); bpy.ops.render.render(write_still=True)
    json.dump({"image": "desert_id.png", "size": [W, Hp], "pagePx": True, "art": art, "ids": ids,
               "space": "UV0 (page print frame); brook = top-down footprint; banner poles and the brook bank omitted",
               "decode": "sRGB bytes ~ rgb (Standard view, no AA); 0 alpha = not sampled by the 3D"},
              open(os.path.join(WORK, "desert_id.json"), "w"), indent=1)


# ============================================================================================ verify
def stage_polys():
    return [np.array(pp) for pp in DES["stageBand"]["polygonsSheet"]]


def mode_verify():
    reset()
    bpy.ops.import_scene.gltf(filepath=GLB)
    obs = {o.name: o for o in bpy.data.objects}
    rep = {"missing": [k for k in EXPECTED + ["desert"] if k not in obs], "fail": [], "warn": []}
    root = obs.get("desert")
    if root is not None and (root.parent is not None or any(abs(s - 1) > 1e-6 for s in root.scale)):
        rep["fail"].append("root transform")
    stages = stage_polys()
    tris = 0; heights = {}; uv_err = {}; sil_err = {}
    for pid in EXPECTED:
        o = obs.get(pid)
        if o is None:
            continue
        if o.parent is None or o.parent.name != "desert":
            rep["fail"].append(f"{pid} not a child of desert")
        p = PIECES[pid]
        meshes = [m for m in [o] + list(o.children_recursive) if m.type == 'MESH']
        zmax = 0.0; allco = []
        for m in meshes:
            co = np.array([(m.matrix_world @ v.co)[:] for v in m.data.vertices])   # Blender (x, d, h)
            allco.append(co)
            tris += sum(len(q.vertices) - 2 for q in m.data.polygons)
            zmax = max(zmax, co[:, 2].max())
            ylo = PAGE_YS_MIN if pid in ("brook", "fiveStones") else PAPER[2]
            if (co[:, 0].min() < PAPER[0] or co[:, 0].max() > PAPER[1] or co[:, 1].min() < ylo or co[:, 1].max() > PAPER[3]):
                rep["fail"].append(f"{m.name} leaves the paper")
            hi = co[co[:, 2] > STAGE_CAP]
            if len(hi) and any(inside(hi[:, :2], s).any() for s in stages):
                rep["fail"].append(f"{m.name} rises above {STAGE_CAP} inside the stage band")
            near = co[(co[:, 1] < -FRONT_ZONE["zBeyond"]) & (co[:, 2] > STAGE_CAP)]
            if len(near) and near[:, 2].max() > FRONT_ZONE["cap"] + 1e-4:
                rep["fail"].append(f"{m.name} rises {near[:, 2].max():.3f} at z > {FRONT_ZONE['zBeyond']}")
            if p.get("mapping") == "front" and m.data.uv_layers and not m.name.endswith("_pole"):
                uv = np.zeros(len(m.data.loops) * 2); m.data.uv_layers[0].data.foreach_get("uv", uv); uv = uv.reshape(-1, 2)
                lv = np.array([l.vertex_index for l in m.data.loops])
                if m.name.endswith("_cloth"):                         # skinned: compare at rest (bind) pose
                    co_r = np.array([v.co[:] for v in m.data.vertices])
                    co_r = np.array([(m.matrix_world @ Vector(c))[:] for c in co_r])
                else:
                    co_r = co
                S = sheet_of(p, co_r[lv, 0], co_r[lv, 2])
                exp = np.stack([S[:, 0] + 0.5, S[:, 1] / ART_H], 1)
                err = np.abs(uv - exp).max(1)
                q = np.stack([uv[:, 0] - 0.5, uv[:, 1] * ART_H], 1)
                owner = poly_np(p["geomSheet"][0])
                outside = float((~inside(q, owner)).mean())
                uv_err[pid] = {"err99": round(float(np.percentile(err, 99)), 4), "outsideDrawing": round(outside, 4)}
                if np.percentile(err, 99) > 0.025 or outside > 0.002:
                    rep["fail"].append(f"{m.name} UV: 99% err {np.percentile(err, 99):.4f}, outside its drawing {outside:.4f}")
            if p.get("mapping") == "front" and not m.name.endswith("_pole"):
                for poly_ in m.data.polygons:                      # dense samples on every edge (silhouette check)
                    vs = list(poly_.vertices)
                    for a_, b_ in zip(vs, vs[1:] + vs[:1]):
                        A_, B_ = co[a_], co[b_]
                        allco.append(A_[None] + np.linspace(0, 1, 9)[:, None] * (B_ - A_)[None])
        heights[pid] = round(float(zmax), 4)
        cap = CAP.get(pid, CAP.get(p["kind"], CAP.get({"water": "water", "stones": "stones"}.get(p["kind"], ""), 1.0)))
        if pid == "brook":
            cap = 0.010                                                 # bank lip; the film itself sits at 0.004
        lim = min(cap, p["heightMax"] + 0.0025) if p["kind"] in FRONT_KINDS else cap
        if zmax > lim + 1e-4:
            rep["fail"].append(f"{pid} height {zmax:.4f} > {lim:.4f}")
        if p.get("mapping") == "front" and p["kind"] in ("hill", "dune", "rock", "shrub", "tent"):
            co = np.vstack(allco)
            xs = np.linspace(min(q[0] for q in p["silhouette3D"]) + 0.002, max(q[0] for q in p["silhouette3D"]) - 0.002, 60)
            b = 0.0015
            got = np.array([co[np.abs(co[:, 0] - x) < b, 2].max(initial=0) for x in xs])
            env = np.array([envelope(p["silhouette3D"], np.linspace(x - b, x + b, 9)) for x in xs])
            e = float(np.max(np.maximum(got - env.max(1), env.min(1) - got).clip(0)))
            sil_err[pid] = round(e, 4)
            if e > 0.012:
                rep["warn" if p["kind"] in ("shrub",) else "fail"].append(f"{pid} front silhouette off by {e:.4f}")
    anims = [a.name for a in bpy.data.actions]
    for b in ("bannerIsraelWave", "bannerPhilWave"):
        if not any(a.startswith(b) for a in anims):
            rep["fail"].append(f"missing animation {b}")
    rep.update({"tris": tris, "budget": MAX_TRIS, "heights": heights, "uvErr99": uv_err, "silhouetteErr": sil_err,
                "actions": anims,
                "materials": sorted({s.material.name for o in bpy.data.objects if o.type == 'MESH' for s in o.material_slots if s.material})})
    if tris > MAX_TRIS:
        rep["fail"].append("over triangle budget")
    rep["pass"] = not rep["fail"] and not rep["missing"]
    json.dump(rep, open(os.path.join(WORK, "desert_verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps(rep))


# ============================================================================================ preview
def load_rgba(path):
    img = bpy.data.images.load(path); w, h = img.size
    a = np.array(img.pixels[:], np.float32).reshape(h, w, 4)
    bpy.data.images.remove(img)
    return a


def image_from(a, name):
    h, w = a.shape[:2]
    out = bpy.data.images.new(name, w, h, alpha=True)
    out.pixels.foreach_set(a.astype(np.float32).ravel())
    out.filepath_raw = os.path.join(WORK, name + ".png"); out.file_format = 'PNG'; out.save()
    return out


def erase_lines(a, ink=None):
    """the app's line-erase, roughly: printed ink (from the line-art mock when given) filled from its neighbours."""
    h, w = a.shape[:2]
    if ink is None:
        ink = a[..., :3].max(2) < 0.62
    ink = ink | np.roll(ink, 1, 0) | np.roll(ink, -1, 0) | np.roll(ink, 1, 1) | np.roll(ink, -1, 1)
    rgb = a[..., :3].copy(); known = ~ink
    for _ in range(8):
        acc = np.zeros_like(rgb); cnt = np.zeros((h, w, 1), np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            acc += np.roll(np.roll(rgb * known[..., None], dy, 0), dx, 1)
            cnt += np.roll(np.roll(known, dy, 0), dx, 1)[..., None]
        fill = (~known) & (cnt[..., 0] > 0)
        rgb[fill] = acc[fill] / cnt[fill]
        known = known | fill
    out = a.copy(); out[..., :3] = rgb
    return out


def srgb_to_lin(c):
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def mat_tex(name, img, mapping=None, rough=0.85):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = rough
    try:
        b.inputs["Specular IOR Level"].default_value = 0.2
    except KeyError:
        pass
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = img; tex.extension = 'EXTEND'; tex.interpolation = 'Linear'
    if mapping:
        uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (mapping[0], mapping[1], 0)
        mp.inputs["Scale"].default_value = (mapping[2], mapping[3], 1)
        nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], tex.inputs[0])
    nt.links.new(tex.outputs[0], b.inputs["Base Color"])
    return m


def place_actor(path, x, d, yaw, clip, frame):
    before = set(bpy.data.objects); acts_before = set(bpy.data.actions)
    bpy.ops.import_scene.gltf(filepath=path)
    new = [o for o in bpy.data.objects if o not in before]
    acts = [a for a in bpy.data.actions if a not in acts_before and clip in a.name.lower()]
    print("ACTOR", os.path.basename(path), [a.name for a in acts])
    for o in new:
        if o.type == 'ARMATURE' and acts:
            o.animation_data_create()
            o.animation_data.action = acts[0]
            try:
                o.animation_data.action_slot = acts[0].slots[0]
            except Exception:
                pass
    for o in [o for o in new if o.parent is None]:
        o.rotation_mode = 'XYZ'; o.rotation_euler.z += math.radians(yaw)
        o.location.x += x; o.location.y += d
    return new


def mode_preview():
    reset()
    sc = bpy.context.scene
    bpy.ops.import_scene.gltf(filepath=GLB)
    desert = [o for o in bpy.data.objects if o.type == 'MESH']
    W, Hp = DESIGN["sheet"]["page"]
    art = DESIGN["sheet"]["art"]
    demo = load_rgba(os.path.join(ROOT, "docs/david-goliath/design/sheet-mock-demo-colour.png"))
    la = os.path.join(ROOT, "docs/david-goliath/design/sheet-mock-lineart.png")
    ink = load_rgba(la)[..., :3].max(2) < 0.6 if os.path.exists(la) else None
    er = erase_lines(demo, ink)
    # desert front pieces: DGPaperLit-like albedo = lerp(scan, sand #F3D58E, paper) (§12.4)
    sandF = np.array([0xF3, 0xD5, 0x8E]) / 255.0
    mn = er[..., :3].min(2)
    t = np.clip((mn - 0.60) / 0.26, 0, 1); paper = (t * t * (3 - 2 * t))[..., None]
    front = er.copy(); front[..., :3] = er[..., :3] * (1 - paper) + sandF * paper
    img_front = image_from(front, "prev_front")
    img_chars = image_from(er, "prev_chars")
    # page ground: Design's baked sand ground with the brook hole (half res, page frame)
    ground_png = os.path.join(ROOT, "docs/david-goliath/design/ground-sand-demo.png")
    img_ground = bpy.data.images.load(ground_png)
    mapping = (art[0] / W, (Hp - art[1] - art[3]) / Hp, art[2] / W, art[3] / Hp)
    m_des = mat_tex("prev_desert", img_front, mapping)
    for o in desert:
        if o.name == "brook":
            continue
        o.data.materials.clear(); o.data.materials.append(m_des)
    px = art[2]
    x0, x1 = -art[0] / px - 0.5, (W - art[0]) / px - 0.5
    y1, y0 = (art[1] + art[3]) / px, (art[1] + art[3] - Hp) / px
    paper_ob = new_obj("paper", [(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], [(0, 1, 2, 3)], smooth=False)
    lay = paper_ob.data.uv_layers.new(name="UVMap")
    for li, uv in zip(range(4), [(0, 0), (1, 0), (1, 1), (0, 1)]):
        lay.data[li].uv = uv
    paper_ob.data.materials.append(mat_tex("prev_ground", img_ground, None, rough=0.95))
    tb = new_obj("table", [(-4, -4, -0.002), (4, -4, -0.002), (4, 5, -0.002), (-4, 5, -0.002)], [(0, 1, 2, 3)], smooth=False)
    tm = bpy.data.materials.new("table"); tm.use_nodes = True
    tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.20, 0.13, 0.08, 1); tb.data.materials.append(tm)
    m_chr = mat_tex("prev_chars", img_chars, mapping, rough=0.7)
    # light + world (as the Design AR mock)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 3.2; sun.data.angle = math.radians(3)
    sun.rotation_euler = (math.radians(42), math.radians(-22), math.radians(-30))
    sc.world = bpy.data.worlds.new("w"); sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.82, 0.86, 0.93, 1); bg.inputs[1].default_value = 0.85
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng; break
        except TypeError:
            pass
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 24
    except AttributeError:
        pass
    cam = bpy.data.objects.new("cam", bpy.data.cameras.new("cam")); sc.collection.objects.link(cam); sc.camera = cam
    cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.01; cam.data.clip_end = 30

    def shoot(name, eye, tgt, vfov, res, out):
        ex, ey, ez = eye; tx, ty, tz = tgt                       # design coords (x, y up, z toward the viewer)
        e = Vector((ex, -ez, ey)); g = Vector((tx, -tz, ty))
        cam.location = e; cam.rotation_euler = (g - e).to_track_quat('-Z', 'Y').to_euler()
        cam.data.angle_y = math.radians(vfov)
        sc.render.resolution_x, sc.render.resolution_y = res
        sc.render.filepath = os.path.join(out, name + ".png"); bpy.ops.render.render(write_still=True)

    def cast(layout):
        for o in [o for o in bpy.data.objects if o.get("dg_actor")]:
            bpy.data.objects.remove(o, do_unlink=True)
        for ch, (x, z, yaw, clip, fr) in layout.items():
            new = place_actor(os.path.join(ANIM, f"{ch}.glb"), x, -z, yaw, clip, fr)
            for o in new:
                o["dg_actor"] = 1
                if o.type == 'MESH':
                    for s in o.material_slots:
                        s.material = m_chr
        sc.frame_set(1)

    phone = ((-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280))
    cast({"david": (-0.30, 0.10, 35, "idle", 1), "goliath": (0.22, -0.25, -35, "idle", 1)})
    shoot("desert_preview_phone", *phone, MODEL)
    shoot("desert_preview_right", (0.30, 0.90, 1.10), (0.10, 0.08, -0.55), 55, (720, 1280), MODEL)
    shoot("desert_preview_low", (0.15, 0.30, 0.95), (-0.05, 0.18, -0.30), 45, (1280, 720), MODEL)
    shoot("desert_preview_brook", (-0.20, 0.16, 0.40), (-0.40, 0.0, 0.12), 32, (1200, 900), MODEL)
    if os.environ.get("DG_DESERT_CLOSEUPS"):
        shoot("close_campI", (-0.30, 0.45, -0.55), (-0.32, 0.30, -1.32), 40, (1200, 900), WORK)
        shoot("close_campP", (0.25, 0.50, -0.55), (0.27, 0.38, -1.32), 40, (1200, 900), WORK)
        shoot("close_dunes", (-0.05, 0.35, 0.10), (-0.35, 0.12, -0.70), 45, (1200, 900), WORK)
        shoot("close_rocks", (0.10, 0.22, -0.40), (-0.05, 0.03, -0.80), 45, (1200, 900), WORK)
        shoot("close_fr", (0.30, 0.15, 0.20), (0.43, 0.02, -0.12), 45, (1200, 900), WORK)
    # the play's opening: both actors on their sheet marks (DGPreview phone_00.5)
    cast({"david": (DESIGN["characters"]["david"]["sheetX"], 0.0, 0, "idle", 1),
          "goliath": (DESIGN["characters"]["goliath"]["sheetX"], 0.0, 0, "idle", 1)})
    shoot("desert_preview_start", *phone, MODEL)
    # top-down: everything except the actors
    for o in bpy.data.objects:
        if o.get("dg_actor"):
            o.hide_render = True
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = (0.0, 0.64, 3.0); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754
    sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "desert_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    print("PREVIEW_OK")


if __name__ == "__main__":
    {"build": mode_build, "verify": mode_verify, "preview": mode_preview}.get(MODE, lambda: None)()
    if MODE == "all":
        mode_build(); mode_verify(); mode_preview()
