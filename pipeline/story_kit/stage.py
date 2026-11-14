"""story_kit/stage.py: shared set functions, included into a pack script with
`story_kit.include(globals(), "stage")` (pipeline/story_kit/__init__.py; docs/STORY-KIT.md).

The functions run in the pack's own namespace, exactly as if they were written in the pack file, so they read the pack's
constants and helpers. A pack overrides one by defining a function of the same name after the include.
Extracted verbatim from pipeline/ru_characters.py / ru_animate.py / ru_bethlehem.py (identical in esther, daniel,
exodus or prodigal); story-specific literals became pack constants: ENV (env-var prefix, e.g. "RU_"),
PAGE_MATERIAL (the page material name, e.g. "ru_page").

Names a pack must define (or import) before calling these functions:
  ART, ART_H, CHAR_PROPOSAL, COLOURS, DECOR, DRAWINGS, FLOOR, HARD_PTS, HARD_SEGS, MODEL, NR_OF, PAGE,
  PAGE_MATERIAL, P_OF, REGION_MATS, REG_OF, RS, SOFT_SEGS, TAU, TEMPLATES, UP, Vector, _chars_proposal, bmesh, bpy,
  delaunay_2d_cdt, json, math, np, os, tessellate_polygon
"""


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


def seg_dist(p, a, b):
    ax, az = a; bx, bz = b; px, pz = p
    dx, dz = bx - ax, bz - az
    L2 = dx * dx + dz * dz
    t = 0.0 if L2 < 1e-12 else max(0.0, min(1.0, ((px - ax) * dx + (pz - az) * dz) / L2))
    return math.hypot(px - ax - t * dx, pz - az - t * dz)


def clear_dist(x, z, soft=False):
    """distance from (x, z) to the nearest stage mark or hard path (soft: also the reported-only moves)"""
    d = min(math.hypot(x - a, z - b) for a, b in HARD_PTS)
    for a, b in HARD_SEGS + (SOFT_SEGS if soft else []):
        d = min(d, seg_dist((x, z), a, b))
    return d


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
    """the figures' sheet places and printed bboxes: pipeline/<xx>_characters.py output where it exists (authoritative),
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


def page_mat():
    m = bpy.data.materials.new(PAGE_MATERIAL)
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.85
    return m


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
