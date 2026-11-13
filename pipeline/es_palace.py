"""Blender (headless): Esther story pack, the palace throne room set -> assets/esther/model/palace.glb

A tabletop stage that stands on the colouring sheet: a three-step dais with a lion-footed throne, two fluted columns
with twin-bull capitals, crimson curtains tied back with gold cords (looping action `curtainSway`), two bronze
braziers (empties `flameL` / `flameR` for the fire FX), a carpet with a border pattern, pale stone floor tiles, a low
back wall with winged guardian reliefs and glazed bricks, and a banquet table (goblets, fruit bowl, bread).
Contract: docs/esther/CONTRACT.md §6. Details, nodes, marks and UV rules: docs/esther/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge (as David & Goliath). In Blender (Z up) a design point (x, h, z) is
(X, Y, Z) = (x, -z, h); export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `es_page` = the scanned art rectangle). Each piece belongs to one *drawing* on the
colouring sheet; the drawing is the piece seen in its projection, so a child's colour lands on the surface behind it:
  front   u = m*x / scale + sheetX + 0.5,  v = ((h + k*(zRef - z)) / scale + sheetY) / 1.227
          (m = -1 for a mirrored copy; k = 0 is the plain front orthographic view of David & Goliath, k > 0 an
          oblique view from slightly above, used for the dais so its treads get their own band of the drawing)
  plan    u = x / scale + sheetX + 0.5,     v = ((zRef - z) / scale + sheetY) / 1.227   (carpet, seen from above)
  tile    every floor tile samples one cell of a 2 x 2 tile swatch drawing (checker A / B)
  const   one texel (the curtain rod samples the gold valance of the curtain drawing)
Shared drawings: columnR = columnL's drawing (shifted), curtainR = curtainL's (mirrored), brazierR = brazierL's.

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/es_palace.py -- build     palace.glb + palace.blend + sheet drawings
  blender -b --factory-startup --python pipeline/es_palace.py -- verify    re-import palace.glb and check it
  blender -b --factory-startup --python pipeline/es_palace.py -- preview   lit renders (needs a build in this run)
  blender -b --factory-startup --python pipeline/es_palace.py -- all       build, preview, verify
Work files go to $ES_WORK (default /tmp/es_work).
"""
import bpy, bmesh, math, os, sys, json
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.geometry import tessellate_polygon

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/esther/model")
SHEET = os.path.join(ROOT, "assets/esther/sheet")
GLB = os.path.join(MODEL, "palace.glb")
BLEND = os.path.join(MODEL, "palace.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/esther/design.json")
WORK = os.environ.get("ES_WORK", "/tmp/es_work")
for d in (MODEL, SHEET, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)                      # print frame, px (150 dpi), as David & Goliath design.json sheet.page
ART = (120, 283, 1000, 1227)             # art rectangle x, y, w, h in page px
DAIS_TOP = 0.07
MAX_TRIS = 40000
TAU = 2 * math.pi
UP = (0.0, 1.0, 0.0)

# stage marks (CONTRACT §6 + timeline.json): the set keeps these clear
MARKS = {"throneSeat": (0.0, -0.30), "stepsFoot": (0.0, -0.12), "table": (0.22, 0.08)}
COL_X, COL_Z = 0.28, -0.43               # columns
BRZ_X, BRZ_Z = 0.29, -0.13               # braziers
CURT_Z = -0.43                           # curtain plane (= columns)
ROD_H, TIE_H, CURT_TOP = 0.415, 0.215, 0.41

# demo colouring (DESIGN.md table; the rest picked to sit with it)
COLOURS = {
    "floorA": "#EFE6D4", "floorB": "#E7DBC3",
    "carpetField": "#3B4A8C", "carpetBorder": "#C8643C", "carpetInlay": "#F2C14E",
    "daisStep": "#E8D3A8", "daisTrim": "#E8B53C", "daisRug": "#2F5FD0",
    "throneGold": "#E8B53C", "throneCushion": "#C8323F", "throneBack": "#2F5FD0", "throneDisc": "#E8743C",
    "colShaft": "#E8D3A8", "colGold": "#E8B53C", "colBull": "#E2C48E",
    "curtain": "#B5283A", "curtainBand": "#E8B53C", "cord": "#F2C14E",
    "brazier": "#A8682E", "brazierRim": "#E8B53C", "coal": "#6B2A1C",
    "wallStone": "#EADFC8", "wallBrick": "#7CC0CC", "frieze": "#2F5FD0", "rosette": "#F2C14E",
    "guardBody": "#E8B53C", "guardWing": "#8CC8F0", "guardCoverts": "#2F5FD0", "guardMane": "#C8643C",
    "tableGold": "#E8B53C", "tableCloth": "#F6EEDC",
    "goblet": "#F2C14E", "bowl": "#A8682E", "fruitRed": "#C8323F", "grapes": "#6A3FB5", "fruitGreen": "#9BC25A",
    "bread": "#D9A35A",
}


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


# ============================================================================================ mesh builder
class MB:
    """Collects vertices (design coords) and faces with a region name, a smooth flag and optional skin weights."""

    def __init__(self):
        self.V, self.F, self.R, self.S = [], [], [], []
        self.W = {}                                   # vertex index -> {bone: weight}

    def v(self, x, h, z):
        self.V.append((float(x), float(h), float(z)))
        return len(self.V) - 1

    def fo(self, idx, reg, out, smooth=False):
        """add a face, wound so its normal points along `out` (design coords)"""
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
        self.F.append(idx); self.R.append(reg); self.S.append(smooth)


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


# ============================================================================================ objects
REGION_MATS = {}
FACE_REGIONS = {}                         # object name -> list of region names per polygon (kept for the drawings)


def region_mat(r):
    if r not in REGION_MATS:
        m = bpy.data.materials.new("rg_" + r)
        m.diffuse_color = (*lin(hex_rgb(COLOURS.get(r, "#FFFFFF"))), 1)
        REGION_MATS[r] = m
    return REGION_MATS[r]


def link(ob):
    bpy.context.scene.collection.objects.link(ob)
    return ob


def make_obj(name, mb, parent=None, origin=(0, 0, 0), smooth_angle=40.0, bevel=None, bevel_angle=50.0):
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
    if not mb.W:
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
            e.smooth = False                              # flat facets (flutes): keep the crease as a drawn line
    bm.to_mesh(me); bm.free()
    if parent is not None:
        parent_keep(ob, parent)
    return ob


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


# ============================================================================================ pieces
def build_floor(root):
    """pale stone tiles, 16 x 11, each a slightly domed slab with a soft groove; checker of two colourable tiles"""
    mb = MB()
    X0, ZF, TW, TD, NX, NZ = -0.60, 0.21, 0.075, 0.0725, 16, 11
    ins, hT, hE = 0.0045, 0.0022, 0.0009
    tiles = []
    for j in range(NZ):
        z1 = ZF - j * TD; z0 = z1 - TD
        for i in range(NX):
            x0 = X0 + i * TW; x1 = x0 + TW
            if x0 >= -0.136 and x1 <= 0.136 and z1 <= -0.12 and z0 >= -0.50:
                continue                                          # under the dais
            reg = "floorA" if (i + j) % 2 == 0 else "floorB"
            o = [mb.v(x0, hE, z1), mb.v(x1, hE, z1), mb.v(x1, hE, z0), mb.v(x0, hE, z0)]
            n = [mb.v(x0 + ins, hT, z1 - ins), mb.v(x1 - ins, hT, z1 - ins), mb.v(x1 - ins, hT, z0 + ins),
                 mb.v(x0 + ins, hT, z0 + ins)]
            mb.fo(n, reg, UP)
            for k in range(4):
                mb.fo([o[k], o[(k + 1) % 4], n[(k + 1) % 4], n[k]], reg, UP)
            tiles.append((i, j))
    X1, ZB = X0 + NX * TW, ZF - NZ * TD
    segs = []                                          # skirt, one segment per tile so each maps into one cell
    for i in range(NX):
        segs.append(((X0 + i * TW, ZF), (X0 + (i + 1) * TW, ZF), (0, 0, 1)))
        segs.append(((X0 + i * TW, ZB), (X0 + (i + 1) * TW, ZB), (0, 0, -1)))
    for j in range(NZ):
        segs.append(((X0, ZF - j * TD), (X0, ZF - (j + 1) * TD), (-1, 0, 0)))
        segs.append(((X1, ZF - j * TD), (X1, ZF - (j + 1) * TD), (1, 0, 0)))
    for a, b, out in segs:
        q = [mb.v(a[0], hE, a[1]), mb.v(b[0], hE, b[1]), mb.v(b[0], -0.002, b[1]), mb.v(a[0], -0.002, a[1])]
        mb.fo(q, "floorA", out)
    ob = make_obj("floor", mb, root, smooth_angle=30)
    ob["tile"] = json.dumps({"x0": X0, "zFront": ZF, "w": TW, "d": TD, "nx": NX, "nz": NZ})
    return ob


def build_carpet(root):
    """runner from the front of the page to the foot of the steps: indigo field, terracotta border with gold
    diamonds, a gold lozenge medallion and a gold fringe at the front end"""
    mb = MB()
    X, ZF, ZB, BW = 0.12, 0.205, -0.118, 0.034
    hb, ht = 0.0012, 0.0042
    outer = [(-X, ZF), (X, ZF), (X, ZB), (-X, ZB)]
    inner = [(-X + BW, ZF - BW), (X - BW, ZF - BW), (X - BW, ZB + BW), (-X + BW, ZB + BW)]
    o = [mb.v(x, ht, z) for x, z in outer]; n = [mb.v(x, ht, z) for x, z in inner]
    for k in range(4):
        mb.fo([o[k], o[(k + 1) % 4], n[(k + 1) % 4], n[k]], "carpetBorder", UP)
    mb.fo(n, "carpetField", UP)
    ob_ = [mb.v(x, hb, z) for x, z in outer]
    for k in range(4):
        a, b = outer[k], outer[(k + 1) % 4]
        mb.fo([o[k], o[(k + 1) % 4], ob_[(k + 1) % 4], ob_[k]], "carpetBorder",
              ((a[0] + b[0]) / 2, 0, (a[1] + b[1]) / 2 - (ZF + ZB) / 2))
    hi = ht + 0.0006
    # diamonds along the long borders and across the ends
    d = 0.0125
    for sx in (-1, 1):
        xc = sx * (X - BW / 2)
        zc = ZF - 0.045
        while zc > ZB + 0.03:
            ngon_top(mb, [(xc, zc + d), (xc + d * 0.8, zc), (xc, zc - d), (xc - d * 0.8, zc)], hi, "carpetInlay", ht)
            zc -= 0.052
    for zc in (ZF - BW / 2, ZB + BW / 2):
        for xc in (-0.043, 0.0, 0.043):
            ngon_top(mb, [(xc, zc + d * 0.8), (xc + d, zc), (xc, zc - d * 0.8), (xc - d, zc)], hi, "carpetInlay", ht)
    # medallion: lozenge with a field-coloured centre ring
    zc = (ZF + ZB) / 2
    ngon_top(mb, [(0, zc + 0.085), (0.042, zc + 0.02), (0.042, zc - 0.02), (0, zc - 0.085), (-0.042, zc - 0.02),
                  (-0.042, zc + 0.02)], hi, "carpetInlay", ht)
    ngon_top(mb, [(0, zc + 0.04), (0.02, zc), (0, zc - 0.04), (-0.02, zc)], hi + 0.0005, "carpetBorder", hi)
    # fringe
    nf = 14
    for i in range(nf):
        x0 = -X + 2 * X * i / nf; x1 = -X + 2 * X * (i + 1) / nf
        ngon_top(mb, [(x0 + 0.002, ZF), (x1 - 0.002, ZF), ((x0 + x1) / 2, ZF + 0.009)], 0.0024, "carpetInlay")
    return make_obj("carpet", mb, root, smooth_angle=30)


def build_dais(root):
    """three wide steps up to a platform (top = DAIS_TOP) with a gold edge, small rosette studs on the risers and a
    lapis rug under the throne. Steps stay inside |x| <= 0.135 so Haman's whisper mark (0.16, -0.24) is floor."""
    mb = MB()
    ZB = -0.50
    steps = [(0.135, -0.150, 0.000, 0.0233), (0.125, -0.170, 0.0233, 0.0467), (0.115, -0.190, 0.0467, DAIS_TOP)]
    for hw, zf, h0, h1 in steps:
        box(mb, -hw, hw, h0 - (0.002 if h0 == 0 else 0.0), h1, ZB, zf, "daisStep", skip=("bottom",))
        # rosette studs on the riser
        hc = (h0 + h1) / 2 if h0 > 0 else h1 / 2
        nst = int((2 * hw - 0.03) / 0.042) + 1
        for i in range(nst):
            xc = -(nst - 1) * 0.021 + i * 0.042
            lathe(mb, [(0.0058, 0.0), (0.0058, 0.0008), (0.0035, 0.0016), (0.0, 0.0019)], "daisStep",
                  C=(xc, hc, zf), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=10, smooth=True,
                  rfun=lambda th, i_, k: 1.0 + (0.18 if k % 2 == 0 and i_ < 2 else 0.0))
    # gold edge moulding round the platform (front + sides)
    box(mb, -0.118, 0.118, DAIS_TOP - 0.0115, DAIS_TOP + 0.0005, -0.193, -0.188, "daisTrim", skip=("bottom",))
    for s in (-1, 1):
        box(mb, s * 0.113 if s > 0 else -0.118, 0.118 if s > 0 else -0.113, DAIS_TOP - 0.0115, DAIS_TOP + 0.0005,
            ZB, -0.188, "daisTrim", skip=("bottom",))
    # rug
    box(mb, -0.096, 0.096, DAIS_TOP, DAIS_TOP + 0.0014, -0.482, -0.205, "daisRug", skip=("bottom",))
    return make_obj("dais", mb, root, bevel=0.0012)


def build_throne(root):
    """tall-backed throne on the platform, seat centre (0, -0.30); lion-paw feet, turned legs, armrests with ball
    finials, a lapis back panel with a gold rosette, and a winged sun-disc crest"""
    mb = MB()
    H = DAIS_TOP
    G = "throneGold"
    zf, zb = -0.222, -0.378                       # seat frame front / back
    legs = [(-0.072, -0.236), (0.072, -0.236), (-0.072, -0.364), (0.072, -0.364)]
    for x, z in legs:
        lathe(mb, [(0.0, H + 0.012), (0.0085, H + 0.012), (0.0062, H + 0.024), (0.0078, H + 0.038), (0.0056, H + 0.052),
                   (0.0070, H + 0.068), (0.0078, H + 0.088), (0.0, H + 0.088)], G, C=(x, 0, z), seg=12)
        # lion paw: a squashed ball with three toes toward the viewer
        sphere(mb, (x, H + 0.0075, z + 0.002), 0.0118, G, seg=12, rings=6, sh=0.62, sz=1.15)
        for dx in (-0.0062, 0.0, 0.0062):
            sphere(mb, (x + dx, H + 0.0042, z + 0.0125), 0.0045, G, seg=8, rings=5, sh=0.85, sz=1.1)
    # stretchers between the legs
    for z in (-0.236, -0.364):
        tube(mb, [(-0.072, H + 0.032, z), (0.072, H + 0.032, z)], 0.0032, G, seg=8, caps=False)
    for x in (-0.072, 0.072):
        tube(mb, [(x, H + 0.032, -0.236), (x, H + 0.032, -0.364)], 0.0032, G, seg=8, caps=False)
    # seat frame and cushion
    box(mb, -0.086, 0.086, H + 0.086, H + 0.100, zb, zf, G)
    box(mb, -0.079, 0.079, H + 0.100, H + 0.116, -0.371, -0.226, "throneCushion")
    # armrests: front post + bar + ball finial
    for s in (-1, 1):
        x = s * 0.085
        lathe(mb, [(0.0, H + 0.100), (0.0062, H + 0.100), (0.0048, H + 0.118), (0.0062, H + 0.134), (0.0052, H + 0.156),
                   (0.0, H + 0.156)], G, C=(x, 0, -0.240), seg=10)
        box(mb, x - 0.0085, x + 0.0085, H + 0.153, H + 0.166, -0.385, -0.238, G)
        sphere(mb, (x, H + 0.168, -0.236), 0.0105, G, seg=12, rings=7)
    # back posts with finials
    for s in (-1, 1):
        x = s * 0.080
        lathe(mb, [(0.0, H + 0.090), (0.0085, H + 0.090), (0.0075, H + 0.20), (0.0072, H + 0.33), (0.0092, H + 0.338),
                   (0.0085, H + 0.346), (0.0, H + 0.36)], G, C=(x, 0, -0.386), seg=12)
    # back frame (4 bars) and recessed lapis panel with a gold rosette
    zbf, zbb = -0.379, -0.393
    box(mb, -0.074, 0.074, H + 0.116, H + 0.132, zbb, zbf, G)
    box(mb, -0.074, 0.074, H + 0.330, H + 0.348, zbb, zbf, G)
    for s in (-1, 1):
        box(mb, s * 0.074 - (0.016 if s > 0 else 0), s * 0.074 + (0.016 if s < 0 else 0), H + 0.132, H + 0.330,
            zbb, zbf, G)
    box(mb, -0.058, 0.058, H + 0.132, H + 0.330, zbb + 0.002, zbf - 0.0025, "throneBack", skip=("back",))
    lathe(mb, [(0.026, 0.0), (0.026, 0.002), (0.021, 0.0042), (0.011, 0.0058), (0.0075, 0.0072), (0.0, 0.008)], G,
          C=(0.0, H + 0.232, zbf - 0.0025), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=24,
          rfun=lambda th, i, k: 1.0 + (0.13 * math.cos(8 * th) if i < 3 else 0.0))
    # winged sun-disc crest
    hc = H + 0.374
    WING = [(18, -9), (40, -7), (62, -3), (84, 5), (102, 16), (92, 18), (82, 14), (88, 21), (74, 19), (78, 26),
            (62, 21), (42, 15), (20, 11)]
    for s in (-1, 1):
        extrude(mb, WING, -0.389, -0.381, G, X=lambda a, b, s=s: (s * a * 0.001, hc + b * 0.001))
    lathe(mb, [(0.0, 0.0), (0.0225, 0.0), (0.0225, 0.004), (0.019, 0.0068), (0.0, 0.0082)], "throneDisc",
          C=(0.0, hc + 0.002, -0.3895), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=24)
    return make_obj("throne", mb, root, origin=(0.0, DAIS_TOP, MARKS["throneSeat"][1]), bevel=0.0011)


BULL = [(0, 4), (22, 4), (30, 1), (38, 0), (55, 0), (61, 3), (61, 8), (53, 11), (45, 12), (47, 19), (51, 26),
        (57, 30), (63, 30), (69, 29), (75, 31), (79, 36), (80, 42), (77, 46), (71, 50), (66, 56), (60, 60), (53, 60),
        (45, 58), (35, 53), (23, 47), (11, 43), (0, 41)]
HORN = [(58, 55), (66, 55), (73, 61), (78, 69), (80, 79), (75, 77), (71, 69), (65, 64), (58, 61)]
EAR = [(55, 57), (45, 65), (42, 62), (49, 55)]
COLLAR = [(41, 18), (49, 21), (54, 54), (46, 57)]


def build_column(name, cx, cz, root):
    """Persian column: stepped plinth, lotus bell base, 24-flute shaft, gold neck ring, palm capital, abacus and a
    twin-bull capital (bulls face +-x, so the front view shows them in profile)"""
    mb = MB()
    box(mb, cx - 0.047, cx + 0.047, -0.002, 0.012, cz - 0.047, cz + 0.047, "colShaft", skip=("bottom",))
    box(mb, cx - 0.040, cx + 0.040, 0.012, 0.020, cz - 0.040, cz + 0.040, "colShaft", skip=("bottom",))
    lathe(mb, [(0.0, 0.020), (0.0365, 0.020), (0.0395, 0.025), (0.0380, 0.034), (0.0325, 0.045), (0.0265, 0.055),
               (0.0235, 0.061), (0.0, 0.061)], "colGold", C=(cx, 0, cz), seg=32,
          rfun=lambda th, i, k: 1.0 + (0.07 * max(0.0, math.cos(8 * th)) if 1 <= i <= 4 else 0.0))
    lathe(mb, [(0.0215, 0.060), (0.0262, 0.062), (0.0262, 0.069), (0.0215, 0.071)], "colGold", C=(cx, 0, cz), seg=32)
    lathe(mb, [(0.0218, 0.069), (0.0213, 0.18), (0.0204, 0.30), (0.0195, 0.42)], "colShaft", C=(cx, 0, cz), seg=48,
          smooth=False, rfun=lambda th, i, k: 1.0 if k % 2 == 0 else 0.88)
    lathe(mb, [(0.0195, 0.418), (0.0245, 0.421), (0.0245, 0.433), (0.0200, 0.437)], "colGold", C=(cx, 0, cz), seg=32)
    lathe(mb, [(0.0200, 0.436), (0.0238, 0.446), (0.0300, 0.457), (0.0350, 0.466), (0.0360, 0.470), (0.0, 0.470)],
          "colShaft", C=(cx, 0, cz), seg=32,
          rfun=lambda th, i, k: 1.0 + (0.09 * max(0.0, math.cos(8 * th + 0.4)) if 1 <= i <= 3 else 0.0))
    box(mb, cx - 0.041, cx + 0.041, 0.469, 0.480, cz - 0.027, cz + 0.027, "colGold")
    h0 = 0.480
    for s in (1, -1):
        X = (lambda a, b, s=s: (cx + s * a * 0.001, h0 + b * 0.001))
        puff(mb, BULL, cz, 0.0185, "colBull", X=X, rad=0.011, edge=0.35, step=0.0055)
        puff(mb, EAR, cz, 0.0215, "colBull", X=X, rad=0.004, edge=0.5, step=0.003)
        hc = [(61, 57), (67, 59.5), (73, 64.5), (77, 71), (78.5, 78)]
        for sz in (1, -1):                         # curved horns either side of the head
            pts = []
            for j, (a, b) in enumerate(hc):
                u = j / (len(hc) - 1)
                x, hh = X(a, b)
                pts.append((x, hh, cz + sz * (0.0095 + 0.007 * u)))
            tube(mb, pts, [0.0040 - 0.0026 * j / (len(hc) - 1) for j in range(len(hc))], "colGold", seg=8)
        puff(mb, COLLAR, cz, 0.0205, "colGold", X=X, rad=0.004, edge=0.6, step=0.003)
        for sz in (1, -1):                         # eyes
            sphere(mb, (cx + s * 0.071, h0 + 0.049, cz + sz * 0.0118), 0.0032, "colBull", seg=8, rings=5)
    return make_obj(name, mb, root, origin=(cx, 0.0, cz), bevel=0.0015, bevel_angle=70, smooth_angle=55)


def curtain_geom(mb, sg):
    """one curtain on side sg (+1 right, -1 left): pleated two-layer cloth from the rod down to the floor, gathered
    at the tie, with a gold valance band; plus the gold cord round cloth and column and a tassel. Skin weights in
    mb.W (bones curtain_root, curtain<S>_upper, curtain<S>_lower)."""
    S = "R" if sg > 0 else "L"
    bu, bl, br = "curtain%s_upper" % S, "curtain%s_lower" % S, "curtain_root"
    ts = [0.0, 0.035, 0.07] + [0.07 + (0.93 * i / 24) for i in range(1, 25)]
    NS = 24
    xo = 0.251

    def xi(t):
        if t <= 0.5:
            return 0.115 + (0.222 - 0.115) * (t / 0.5) ** 1.7
        return 0.222 - (0.222 - 0.163) * ((t - 0.5) / 0.5) ** 0.75

    def hh(t):
        if t <= 0.5:
            return CURT_TOP - (CURT_TOP - TIE_H) * (t / 0.5)
        return TIE_H - (TIE_H - 0.003) * ((t - 0.5) / 0.5)

    w0 = xo - xi(0)
    grid_f, grid_b = [], []
    for t in ts:
        rf, rb = [], []
        x_in = xi(t); w = xo - x_in
        A = 0.0018 if t < 0.071 else 0.0045 + 0.0080 * (1 - w / w0)
        belly = 0.011 * math.sin(math.pi * t / 0.5) if t < 0.5 else 0.010 * ((t - 0.5) / 0.5) ** 2
        for k in range(NS + 1):
            s = k / NS
            x = sg * (x_in + w * s)
            dz = A * math.sin(TAU * 5 * s + 0.4) + belly * (1.0 - 0.55 * s)
            z = CURT_Z + dz
            h = hh(t)
            wu = (math.sin(math.pi * t / 0.5) ** 1.2) * (0.55 + 0.45 * (1 - s)) if 0 < t < 0.5 else 0.0
            wl = ((t - 0.5) / 0.5) ** 1.3 if t > 0.5 else 0.0
            for lst, zz in ((rf, z), (rb, z - 0.0025)):
                vi = mb.v(x, h, zz)
                mb.W[vi] = {br: max(0.0, 1 - wu - wl), bu: wu, bl: wl}
                lst.append(vi)
        grid_f.append(rf); grid_b.append(rb)
    for i in range(len(ts) - 1):
        reg = "curtainBand" if ts[i] < 0.069 else "curtain"
        for k in range(NS):
            q = [grid_f[i][k], grid_f[i][k + 1], grid_f[i + 1][k + 1], grid_f[i + 1][k]]
            mb.fo(q, reg, (0, 0, 1), True)
            q = [grid_b[i][k], grid_b[i][k + 1], grid_b[i + 1][k + 1], grid_b[i + 1][k]]
            mb.fo(q, reg, (0, 0, -1), True)
    # edges joining the layers
    last = len(ts) - 1
    for k in range(NS):
        mb.fo([grid_f[0][k], grid_f[0][k + 1], grid_b[0][k + 1], grid_b[0][k]], "curtainBand", UP)
        mb.fo([grid_f[last][k], grid_f[last][k + 1], grid_b[last][k + 1], grid_b[last][k]], "curtain", (0, -1, 0))
    for i in range(len(ts) - 1):
        reg = "curtainBand" if ts[i] < 0.069 else "curtain"
        mb.fo([grid_f[i][0], grid_f[i + 1][0], grid_b[i + 1][0], grid_b[i][0]], reg, (-sg, 0, 0))
        mb.fo([grid_f[i][NS], grid_f[i + 1][NS], grid_b[i + 1][NS], grid_b[i][NS]], reg, (sg, 0, 0))
    n0 = len(mb.V)
    # cord: round the column shaft and round the gathered cloth, a knot and a tassel
    tube(mb, [(sg * COL_X + 0.0255 * math.cos(TAU * k / 20), TIE_H, CURT_Z + 0.0255 * math.sin(TAU * k / 20))
              for k in range(20)], 0.0030, "cord", seg=7, closed=True, ref=(0, 1, 0))
    xc = sg * 0.2355
    tube(mb, [(xc + 0.0195 * math.cos(TAU * k / 20), TIE_H - 0.002, CURT_Z + 0.004 + 0.0175 * math.sin(TAU * k / 20))
              for k in range(20)], 0.0034, "cord", seg=7, closed=True, ref=(0, 1, 0))
    sphere(mb, (sg * 0.232, TIE_H - 0.002, CURT_Z + 0.0225), 0.0058, "cord", seg=10, rings=6)
    lathe(mb, [(0.0, TIE_H - 0.008), (0.0035, TIE_H - 0.010), (0.0042, TIE_H - 0.018), (0.0040, TIE_H - 0.024),
               (0.0075, TIE_H - 0.046), (0.0068, TIE_H - 0.050), (0.0, TIE_H - 0.051)][::-1], "cord",
          C=(sg * 0.232, 0, CURT_Z + 0.0235), seg=10)
    for vi in range(n0, len(mb.V)):
        mb.W[vi] = {br: 1.0}


def build_curtains(root):
    """armature `curtains` (action curtainSway) with skinned meshes curtainL, curtainR and the static curtainRod"""
    arm = bpy.data.armatures.new("curtains_arm")
    rig = link(bpy.data.objects.new("curtains", arm))
    rig.parent = root
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    r0 = arm.edit_bones.new("curtain_root"); r0.head = B(0, ROD_H, CURT_Z); r0.tail = B(0, ROD_H + 0.04, CURT_Z)
    for sg, S in ((-1, "L"), (1, "R")):
        u = arm.edit_bones.new("curtain%s_upper" % S)
        u.head = B(sg * 0.17, ROD_H, CURT_Z); u.tail = B(sg * 0.17, TIE_H, CURT_Z); u.parent = r0
        lo = arm.edit_bones.new("curtain%s_lower" % S)
        lo.head = B(sg * 0.2355, TIE_H, CURT_Z); lo.tail = B(sg * 0.20, 0.0, CURT_Z); lo.parent = r0
    for b in arm.edit_bones:
        b.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')
    obs = {}
    for sg, S in ((-1, "L"), (1, "R")):
        mb = MB(); curtain_geom(mb, sg)
        ob = make_obj("curtain" + S, mb, None, smooth_angle=60)
        ob.parent = rig
        mod = ob.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
        obs[S] = ob
    mb = MB()
    tube(mb, [(-0.259, ROD_H, CURT_Z), (0.259, ROD_H, CURT_Z)], 0.0052, "curtainBand", seg=10, caps=False)
    for x in np.linspace(-0.235, 0.235, 2):
        pass
    rod = make_obj("curtainRod", mb, None)
    rod.parent = rig
    rod.vertex_groups.new(name="curtain_root").add(list(range(len(rod.data.vertices))), 1.0, 'REPLACE')
    mod = rod.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
    # sway: 4 s loop at 24 fps, frame 1 == frame 97; gentle swing in and out of the page plus a little sideways
    bpy.context.scene.render.fps = 24
    rig.animation_data_create()
    xax, zax = Vector((1, 0, 0)), Vector((0, 1, 0))           # Blender X (in/out swing pivot), Blender Y (= design z)
    keys = {}
    for S, ph in (("L", 0.0), ("R", 1.3)):
        keys["curtain%s_upper" % S] = [(xax, 2.6, ph)]
        keys["curtain%s_lower" % S] = [(xax, 2.2, ph + 0.9), (zax, 1.4 * (1 if S == "L" else -1), ph + 2.0)]
    for bn, comps in keys.items():
        pb = rig.pose.bones[bn]; pb.rotation_mode = 'QUATERNION'
        inv = rig.data.bones[bn].matrix_local.to_3x3().inverted()
        for f in range(1, 98, 4):
            q = Quaternion()
            for ax, amp, ph in comps:
                a = (inv @ ax).normalized()
                q = q @ Quaternion(a, math.radians(amp) * math.sin(TAU * (f - 1) / 96 - ph))
            pb.rotation_quaternion = q
            pb.keyframe_insert("rotation_quaternion", frame=f)
    act = rig.animation_data.action
    act.name = "curtainSway"
    return rig, obs["L"], obs["R"], rod


def build_brazier(name, cx, cz, root):
    """bronze bowl on a tripod with S-curved legs and hoof feet, a gold rim band and glowing coals"""
    mb = MB()
    R = "brazier"
    for i in range(3):
        a = TAU * i / 3 + math.pi / 2                       # one leg toward the viewer
        ca, sa = math.cos(a), math.sin(a)
        pts = []
        for j in range(8):
            u = j / 7
            r = 0.036 - 0.021 * u + 0.007 * math.sin(math.pi * u)
            pts.append((cx + r * ca, 0.006 + 0.088 * u, cz + r * sa))
        tube(mb, pts, [0.0036 - 0.0008 * j / 7 for j in range(8)], R, seg=7, caps=False)
        sphere(mb, (cx + 0.036 * ca, 0.0055, cz + 0.036 * sa), 0.0062, R, seg=8, rings=5, sh=0.9)
    rr = 0.036 - 0.021 * 0.45 + 0.007 * math.sin(math.pi * 0.45)
    tube(mb, [(cx + rr * math.cos(TAU * k / 24), 0.006 + 0.088 * 0.45, cz + rr * math.sin(TAU * k / 24))
              for k in range(24)], 0.0026, R, seg=6, closed=True, ref=(0, 1, 0))
    lathe(mb, [(0.0, 0.089), (0.010, 0.0905), (0.022, 0.097), (0.031, 0.1055), (0.0355, 0.113, "brazierRim"),
               (0.0385, 0.121), (0.0392, 0.1265), (0.0360, 0.1285), (0.0320, 0.1255), (0.0, 0.120)], R,
          C=(cx, 0, cz), seg=24)
    lathe(mb, [(0.0325, 0.1245), (0.028, 0.133), (0.016, 0.1405), (0.0, 0.1425)], "coal", C=(cx, 0, cz), seg=16,
          rfun=lambda th, i, k: 1.0 + 0.08 * math.sin(5 * th + i))
    for i, (dx, dz) in enumerate(((0.012, 0.004), (-0.010, 0.008), (-0.004, -0.013), (0.009, -0.010), (0.0, 0.0))):
        sphere(mb, (cx + dx, 0.1365 + (0.003 if i == 4 else 0.0), cz + dz), 0.0072, "coal", seg=7, rings=4, sh=0.7)
    return make_obj(name, mb, root, origin=(cx, 0.0, cz))


GUARD_BODY = [(-44, 0), (-35, 0), (-33, 16), (-27, 20), (-25, 0), (-16, 0), (-15, 20), (-6, 25), (12, 25), (16, 19),
              (16, 0), (25, 0), (26, 17), (31, 15), (32, 0), (41, 0), (40, 22), (43, 38), (36, 48), (10, 48),
              (-20, 47), (-34, 46), (-38, 50), (-46, 54), (-52, 62), (-50, 70), (-56, 68), (-58, 60), (-52, 50),
              (-44, 44), (-46, 30), (-46, 10)]
GUARD_WING = [(34, 40), (18, 36), (0, 40), (-16, 50), (-28, 62), (-34, 74), (-30, 82), (-18, 86), (-4, 86), (10, 82),
              (18, 76), (12, 74), (0, 76), (-10, 74), (-14, 70), (-2, 64), (12, 58), (24, 50)]
GUARD_COVERTS = [(34, 40), (18, 36), (2, 40), (-8, 49), (0, 57), (14, 56), (27, 49)]
GUARD_FACE = [(40, 42), (50, 42), (58, 44), (62, 48), (61, 53), (55, 57), (47, 60), (40, 56)]


def brick(mb, x0, x1, h0, h1, zb, zf, c=0.0016):
    """raised glazed brick with chamfered sides (no bevel pass needed)"""
    o = [mb.v(x0, h0, zb), mb.v(x1, h0, zb), mb.v(x1, h1, zb), mb.v(x0, h1, zb)]
    n = [mb.v(x0 + c, h0 + c, zf), mb.v(x1 - c, h0 + c, zf), mb.v(x1 - c, h1 - c, zf), mb.v(x0 + c, h1 - c, zf)]
    mb.fo(n, "wallBrick", (0, 0, 1))
    outs = [(0, -1, 1), (1, 0, 1), (0, 1, 1), (-1, 0, 1)]
    for k in range(4):
        mb.fo([o[k], o[(k + 1) % 4], n[(k + 1) % 4], n[k]], "wallBrick", outs[k])


def build_wall(root):
    """low back wall: stone plinth, glazed-brick field, lapis frieze with gold rosettes, cornice and stepped
    crenellations, and two winged guardians (lions with upswept wings) facing the throne"""
    mb = MB()
    ZF, ZBK, X = -0.58, -0.64, 0.60
    box(mb, -X, X, -0.002, 0.205, ZBK, ZF, "wallBrick", skip=("bottom",))
    box(mb, -X - 0.004, X + 0.004, -0.002, 0.034, ZBK - 0.004, ZF + 0.006, "wallStone", skip=("bottom",))
    box(mb, -X - 0.002, X + 0.002, 0.205, 0.270, ZBK, ZF + 0.004, "frieze")
    box(mb, -X - 0.005, X + 0.005, 0.270, 0.281, ZBK - 0.003, ZF + 0.007, "wallStone")
    for i in range(16):
        xm = -0.5625 + 0.075 * i
        for w, h0, h1 in ((0.052, 0.281, 0.294), (0.036, 0.294, 0.307), (0.020, 0.307, 0.319)):
            box(mb, xm - w / 2, xm + w / 2, h0, h1, ZBK + 0.004, ZF - 0.004, "wallStone", skip=("bottom",))
    # rosettes on the frieze
    for i in range(12):
        xc = -0.55 + 0.10 * i
        lathe(mb, [(0.0235, 0.0), (0.0235, 0.0022), (0.019, 0.0045), (0.0085, 0.0058), (0.0068, 0.0078), (0.0, 0.0084)],
              "rosette", C=(xc, 0.2375, ZF + 0.004), A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=14,
              rfun=lambda th, i_, k: 1.0 + (0.12 * math.cos(7 * th) if i_ < 3 else 0.0))
    # guardians (left one faces +x, right one mirrored)
    GX, GH, S_ = 0.47, 0.034, 0.002
    for sg in (-1, 1):
        X_ = (lambda a, b, sg=sg: (sg * GX - sg * a * S_, GH + b * S_))
        extrude(mb, GUARD_BODY, ZF - 0.001, ZF + 0.0075, "guardBody", X=X_, back=False)
        extrude(mb, GUARD_WING, ZF + 0.002, ZF + 0.0105, "guardWing", X=X_, back=False)
        extrude(mb, GUARD_COVERTS, ZF + 0.004, ZF + 0.0128, "guardCoverts", X=X_, back=False)
        mane = [(39 + (17 if k % 2 == 0 else 14) * math.cos(TAU * k / 18), 51 + (17 if k % 2 == 0 else 14) *
                 math.sin(TAU * k / 18)) for k in range(18)]
        tuft = [(-50 + 6 * math.cos(TAU * k / 8), 72 + 5 * math.sin(TAU * k / 8)) for k in range(8)]
        extrude(mb, tuft, ZF + 0.001, ZF + 0.0095, "guardMane", X=X_, back=False)
        extrude(mb, mane, ZF + 0.003, ZF + 0.0115, "guardMane", X=X_, back=False)
        extrude(mb, GUARD_FACE, ZF + 0.005, ZF + 0.0138, "guardBody", X=X_, back=False)
        extrude(mb, [(40, 61), (43, 69), (47, 62)], ZF + 0.005, ZF + 0.0125, "guardBody", X=X_, back=False)
    # glazed bricks (raised, staggered) where no guardian stands
    rows = 6; hb0, hb1 = 0.036, 0.203
    rh = (hb1 - hb0) / rows
    for r in range(rows):
        h0 = hb0 + r * rh + 0.0016; h1 = hb0 + (r + 1) * rh - 0.0016
        off = 0.0 if r % 2 == 0 else 0.03
        x = -0.345 + off
        while x < 0.345 - 0.001:
            x0, x1 = max(x, -0.345) + 0.0016, min(x + 0.06, 0.345) - 0.0016
            if x1 - x0 > 0.01:
                brick(mb, x0 - 0.0016, x1 + 0.0016, h0 - 0.0016, h1 + 0.0016, ZF, ZF + 0.0024, c=0.0)
            x += 0.06
        if off:
            brick(mb, -0.345, -0.345 + off, h0 - 0.0016, h1 + 0.0016, ZF, ZF + 0.0024, c=0.0)
    return make_obj("wallRelief", mb, root, origin=(0.0, 0.0, ZF), bevel=0.0012, bevel_angle=60)


def build_table(root):
    """low banquet table at (0.22, 0.08): gold frame on lion legs, linen cloth with a zigzag hem; children
    goblet1, goblet2, bowl (with fruit) and bread"""
    tx, tz = MARKS["table"]
    x0, x1, z0, z1 = tx - 0.075, tx + 0.075, tz - 0.035, tz + 0.035
    HT = 0.048
    mb = MB()
    for x, z in ((x0 + 0.012, z0 + 0.010), (x1 - 0.012, z0 + 0.010), (x0 + 0.012, z1 - 0.010), (x1 - 0.012, z1 - 0.010)):
        lathe(mb, [(0.0, 0.008), (0.0060, 0.008), (0.0044, 0.016), (0.0058, 0.028), (0.0042, 0.038), (0.0060, HT - 0.004),
                   (0.0, HT - 0.004)], "tableGold", C=(x, 0, z), seg=10)
        sphere(mb, (x, 0.0055, z + 0.002), 0.0075, "tableGold", seg=10, rings=5, sh=0.75, sz=1.15)
    box(mb, x0, x1, HT - 0.006, HT, z0, z1, "tableGold")
    # cloth: top + skirt with zigzag hem on all four sides
    ct = HT + 0.0012; e = 0.003
    cx0, cx1, cz0, cz1 = x0 - e, x1 + e, z0 - e, z1 + e
    mb.fo([mb.v(cx0, ct, cz1), mb.v(cx1, ct, cz1), mb.v(cx1, ct, cz0), mb.v(cx0, ct, cz0)], "tableCloth", UP)
    for (ax, az), (bx, bz), out in (((cx0, cz1), (cx1, cz1), (0, 0, 1)), ((cx1, cz1), (cx1, cz0), (1, 0, 0)),
                                    ((cx1, cz0), (cx0, cz0), (0, 0, -1)), ((cx0, cz0), (cx0, cz1), (-1, 0, 0))):
        L = math.hypot(bx - ax, bz - az); n = max(2, int(round(L / 0.0125)))
        top = [mb.v(ax + (bx - ax) * i / n, ct, az + (bz - az) * i / n) for i in range(n + 1)]
        bot = [mb.v(ax + (bx - ax) * i / n, ct - (0.030 if i % 2 else 0.022), az + (bz - az) * i / n)
               for i in range(n + 1)]
        for i in range(n):
            mb.fo([top[i], top[i + 1], bot[i + 1], bot[i]], "tableCloth", out)
    table = make_obj("table", mb, root, origin=(tx, 0.0, tz))
    top_h = ct
    items = {}
    # goblets
    for name, gx, gz in (("goblet1", 0.165, 0.086), ("goblet2", 0.280, 0.074)):
        m = MB()
        lathe(m, [(0.0, top_h), (0.0090, top_h), (0.0085, top_h + 0.003), (0.0025, top_h + 0.006), (0.0022, top_h + 0.015),
                  (0.0042, top_h + 0.017), (0.0024, top_h + 0.020), (0.0058, top_h + 0.023), (0.0092, top_h + 0.030),
                  (0.0104, top_h + 0.038), (0.0094, top_h + 0.0386), (0.0084, top_h + 0.031), (0.0, top_h + 0.026)],
              "goblet", C=(gx, 0, gz), seg=16)
        items[name] = make_obj(name, m, None, origin=(gx, top_h, gz))
    # bowl with fruit
    bx, bz = 0.205, 0.082
    m = MB()
    lathe(m, [(0.0, top_h), (0.0085, top_h), (0.0075, top_h + 0.004), (0.0055, top_h + 0.0055), (0.014, top_h + 0.008),
              (0.021, top_h + 0.013), (0.0235, top_h + 0.0175), (0.0215, top_h + 0.0182), (0.0, top_h + 0.010)],
          "bowl", C=(bx, 0, bz), seg=20)
    hb = top_h + 0.016
    for dx, dz in ((-0.008, 0.004), (0.009, 0.006)):
        sphere(m, (bx + dx, hb + 0.003, bz + dz), 0.0088, "fruitRed", seg=10, rings=6)
        lathe(m, [(0.0, 0.0), (0.0028, 0.0), (0.0034, 0.004), (0.0, 0.0041)], "fruitRed",
              C=(bx + dx, hb + 0.0115, bz + dz), seg=6)
    sphere(m, (bx + 0.001, hb + 0.0085, bz - 0.006), 0.0082, "fruitRed", seg=10, rings=6, sh=1.1)
    for i, (dx, dh, dz) in enumerate(((-0.004, 0.012, 0.012), (0.002, 0.012, 0.013), (-0.001, 0.0065, 0.016),
                                      (0.005, 0.0065, 0.015), (-0.007, 0.0065, 0.015), (0.002, 0.001, 0.018),
                                      (-0.003, 0.001, 0.018), (0.0, 0.017, 0.010))):
        sphere(m, (bx + dx, hb + dh, bz + dz), 0.0042, "grapes", seg=8, rings=5)
    items["bowl"] = make_obj("bowl", m, None, origin=(bx, top_h, bz))
    # bread: two round loaves, one leaning
    rx, rz = 0.248, 0.098
    m = MB()
    lathe(m, [(0.0, top_h), (0.0135, top_h), (0.0142, top_h + 0.003), (0.0120, top_h + 0.0075), (0.0070, top_h + 0.0105),
              (0.0, top_h + 0.0115)], "bread", C=(rx, 0, rz), seg=16)
    lathe(m, [(0.0, 0.0), (0.0110, 0.0), (0.0116, 0.0025), (0.0096, 0.0062), (0.0052, 0.0085), (0.0, 0.0092)], "bread",
          C=(rx + 0.010, top_h + 0.002, rz - 0.013), A=(0.0, 0.97, 0.24), U=(1, 0, 0), V=(0, -0.24, 0.97), seg=16,
          sx=1.25)
    items["bread"] = make_obj("bread", m, None, origin=(rx, top_h, rz))
    for ob in items.values():
        parent_keep(ob, table)
    return table, items


# ============================================================================================ drawings / UV
def proj(spec, x, h, z):
    m = -1.0 if spec.get("mirror") else 1.0
    if spec["kind"] == "plan":
        return m * x, spec["zRef"] - z
    return m * x, h + spec.get("k", 0.0) * (spec.get("zRef", 0.0) - z)


def depth_of(spec, x, h, z):
    if spec["kind"] in ("plan", "tile"):
        return h
    return z + spec.get("k", 0.0) * h


def world_verts(ob):
    mw = ob.matrix_world
    return [D(mw @ v.co) for v in ob.data.vertices]


# Sheet placement proposal (sheet coords: x from -0.5 to 0.5, ys from 0 at the art rect's bottom to 1.227 at its
# top). The three figures (front view, rest pose, scale 1) take the bottom band ys 0.015..0.43; the set drawings
# fill the space above. Each drawing: projection kind, scale, and where its bbox centre-x / bottom go.
def _chars():
    """the figures' sheet places and printed bboxes (pipeline/es_characters.py output; authoritative)"""
    p = os.path.join(MODEL, "regions_characters.json")
    if os.path.exists(p):
        rc = json.load(open(p))
        return {c: {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"], "height": v["height"],
                    "box": v["bboxSheet"]} for c, v in rc["characters"].items()}
    return {"esther": {"sheetX": -0.33, "sheetY": 0.015, "height": 0.34, "box": [-0.449, 0.015, -0.211, 0.355]},
            "king": {"sheetX": 0.02, "sheetY": 0.015, "height": 0.40, "box": [-0.193, 0.015, 0.156, 0.415]},
            "haman": {"sheetX": 0.34, "sheetY": 0.015, "height": 0.37, "box": [0.213, 0.015, 0.467, 0.386]}}


CHAR_PROPOSAL = _chars()
DRAWINGS = {
    "wall":    {"members": ["wallRelief"], "kind": "front", "scale": 1.50, "cx": 0.0, "y0": 0.997},
    "column":  {"members": ["columnL"], "kind": "front", "scale": 1.05, "cx": -0.405, "y0": 0.445},
    "curtain": {"members": ["curtainL"], "kind": "front", "scale": 1.00, "cx": -0.215, "y0": 0.452},
    "throne":  {"members": ["throne"], "kind": "front", "scale": 1.05, "cx": 0.0, "y0": 0.598},
    "dais":    {"members": ["dais"], "kind": "front", "k": 0.30, "zRef": -0.15, "scale": 1.30, "cx": 0.0, "y0": 0.445},
    "brazier": {"members": ["brazierL"], "kind": "front", "scale": 0.80, "cx": 0.21, "y0": 0.765},
    "banquet": {"members": ["table", "goblet1", "goblet2", "bowl", "bread"], "kind": "front", "scale": 0.72,
                "cx": 0.355, "y0": 0.445},
    "carpet":  {"members": ["carpet"], "kind": "plan", "zRef": 0.214, "scale": 1.25, "cx": 0.385, "y0": 0.60},
    "floor":   {"members": ["floor"], "kind": "tile", "scale": 1.30, "cx": 0.215, "y0": 0.605},
}
SHARED = {"columnR": ("column", "shift"), "curtainR": ("curtain", "mirror"), "brazierR": ("brazier", "shift")}


def setup_maps(objs):
    """fill DRAWINGS[*] sheetX / sheetY / bboxSheet from the built geometry; return per-object UV specs"""
    specs = {}
    for g, dsp in DRAWINGS.items():
        if dsp["kind"] == "tile":
            t = json.loads(objs["floor"]["tile"])
            w, d = 2 * t["w"] / dsp["scale"], 2 * t["d"] / dsp["scale"]
            dsp["sheetX"] = dsp["cx"] - w / 2; dsp["sheetY"] = dsp["y0"]
            dsp["bboxSheet"] = [round(dsp["sheetX"], 4), round(dsp["y0"], 4), round(dsp["sheetX"] + w, 4),
                                round(dsp["y0"] + d, 4)]
            specs["floor"] = dict(dsp, tile=t)
            continue
        A, Bv = [], []
        for name in dsp["members"]:
            for x, h, z in world_verts(objs[name]):
                a, b = proj(dsp, x, h, z); A.append(a); Bv.append(b)
        a0, a1, b0, b1 = min(A), max(A), min(Bv), max(Bv)
        s = dsp["scale"]
        dsp["sheetX"] = dsp["cx"] - (a0 + a1) / 2 / s
        dsp["sheetY"] = dsp["y0"] - b0 / s
        dsp["bboxSheet"] = [round(a0 / s + dsp["sheetX"], 4), round(b0 / s + dsp["sheetY"], 4),
                            round(a1 / s + dsp["sheetX"], 4), round(b1 / s + dsp["sheetY"], 4)]
        dsp["bbox3D"] = [round(a0, 4), round(b0, 4), round(a1, 4), round(b1, 4)]
        for name in dsp["members"]:
            specs[name] = dict(dsp)
    for name, (g, how) in SHARED.items():
        sp = dict(DRAWINGS[g])
        src = DRAWINGS[g]["members"][0]
        if how == "mirror":
            sp["mirror"] = True
        else:
            cs = np.mean([v[0] for v in world_verts(objs[src])])
            ct = np.mean([v[0] for v in world_verts(objs[name])])
            sp["sheetX"] = sp["sheetX"] + (cs - ct) / sp["scale"]
        specs[name] = sp
    # curtain rod: one texel in the middle of the curtain's gold valance
    sp = specs["curtainL"]
    a, b = proj(sp, -0.20, CURT_TOP - 0.016, CURT_Z)
    rod_uv = (a / sp["scale"] + sp["sheetX"] + 0.5, (b / sp["scale"] + sp["sheetY"]) / ART_H)
    specs["curtainRod"] = {"kind": "const", "uv": [round(rod_uv[0], 5), round(rod_uv[1], 5)]}
    return specs


def uv_of(spec, x, h, z, centroid=None):
    if spec["kind"] == "const":
        return tuple(spec["uv"])
    if spec["kind"] == "tile":
        t = spec["tile"]; cx, ch, cz = centroid
        cx = min(max(cx, t["x0"] + 1e-4), t["x0"] + t["nx"] * t["w"] - 1e-4)
        cz = min(max(cz, t["zFront"] - t["nz"] * t["d"] + 1e-4), t["zFront"] - 1e-4)
        i = min(max(int(math.floor((cx - t["x0"]) / t["w"])), 0), t["nx"] - 1)
        j = min(max(int(math.floor((t["zFront"] - cz) / t["d"])), 0), t["nz"] - 1)
        lx = x - (t["x0"] + i * t["w"]); lz = (t["zFront"] - j * t["d"]) - z
        xs = spec["sheetX"] + ((i % 2) * t["w"] + lx) / spec["scale"]
        ys = spec["sheetY"] + ((j % 2) * t["d"] + lz) / spec["scale"]
        return xs + 0.5, ys / ART_H
    a, b = proj(spec, x, h, z)
    return a / spec["scale"] + spec["sheetX"] + 0.5, (b / spec["scale"] + spec["sheetY"]) / ART_H


def apply_uvs(objs, specs):
    for name, ob in objs.items():
        if ob.type != 'MESH':
            continue
        sp = specs[name]
        me = ob.data
        lay = me.uv_layers.new(name="UVMap")
        W = world_verts(ob)
        for p in me.polygons:
            cen = tuple(np.mean([W[v] for v in p.vertices], axis=0))
            for li in p.loop_indices:
                x, h, z = W[me.loops[li].vertex_index]
                lay.data[li].uv = uv_of(sp, x, h, z, cen)
        FACE_REGIONS[name] = [me.materials[p.material_index].name[3:] for p in me.polygons]


RS = [1]                                  # raster scale (2 while rendering the set ID map for the sheet)


def to_px(u, v):
    return (ART[0] + u * ART[2]) * RS[0], (ART[1] + (1.0 - v) * ART[3]) * RS[0]


def raster_drawings(objs, specs):
    """UV-space render of every drawing (source pieces only): region ids + depth, then sharp-edge decor lines"""
    W, H = PAGE[0] * RS[0], PAGE[1] * RS[0]
    idb = np.zeros((H, W), np.int32); zb = np.full((H, W), -1e9)
    regid, regname = {}, {0: None}
    crease = np.zeros((H, W), bool)
    for g, dsp in DRAWINGS.items():
        for name in dsp["members"]:
            ob = objs[name]; sp = specs[name]; me = ob.data
            me.calc_loop_triangles()
            Wv = world_verts(ob)
            uvl = me.uv_layers["UVMap"].data
            regs = FACE_REGIONS[name]
            for tri in me.loop_triangles:
                key = (g, regs[tri.polygon_index])
                if key not in regid:
                    regid[key] = len(regid) + 1; regname[regid[key]] = key
                rid = regid[key]
                P = np.array([to_px(*uvl[li].uv) for li in tri.loops])
                Z = np.array([depth_of(sp, *Wv[vi]) for vi in tri.vertices])
                x0, y0 = np.floor(P.min(0)).astype(int); x1, y1 = np.ceil(P.max(0)).astype(int)
                x0, y0 = max(x0, 0), max(y0, 0); x1, y1 = min(x1, W - 1), min(y1, H - 1)
                if x1 < x0 or y1 < y0:
                    continue
                gx, gy = np.meshgrid(np.arange(x0, x1 + 1) + 0.5, np.arange(y0, y1 + 1) + 0.5)
                (ax, ay), (bx, by), (cx, cy) = P
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
    # decor lines: visible sharp edges (folds, flutes, bricks, feathers), same projection
    for g, dsp in DRAWINGS.items():
        if dsp["kind"] == "tile":
            continue
        for name in dsp["members"]:
            ob = objs[name]; sp = specs[name]; me = ob.data
            Wv = world_verts(ob)
            sharp = me.attributes.get("sharp_edge")
            sv = np.zeros(len(me.edges), bool)
            if sharp is not None:
                sharp.data.foreach_get("value", sv)
            for e in me.edges:
                if not sv[e.index]:
                    continue
                a, b = Wv[e.vertices[0]], Wv[e.vertices[1]]
                pa = np.array(to_px(*uv_of(sp, *a))); pb = np.array(to_px(*uv_of(sp, *b)))
                n = int(np.linalg.norm(pb - pa) / 0.6) + 2
                for t in np.linspace(0, 1, n):
                    p = pa + (pb - pa) * t
                    xi, yi = int(p[0]), int(p[1])
                    if 0 <= xi < W and 0 <= yi < H and idb[yi, xi] > 0:
                        d = depth_of(sp, *[a[k] + (b[k] - a[k]) * t for k in range(3)])
                        if d >= zb[yi, xi] - 0.0025:
                            crease[yi, xi] = True
    # depth steps inside one region (an ear over a neck, an eye on a head, a leg in front of a body)
    for dy, dx in ((0, 1), (1, 0)):
        sz = shift(zb, dy, dx); si = shift(idb, dy, dx)
        crease |= (idb > 0) & (si == idb) & (np.abs(zb - sz) > 0.004)
    return idb, regname, crease


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


def compose_sheets(idb, regname, crease):
    """line art (proposal), demo colouring and the preview texture (colours, no lines, padded)"""
    H, W = idb.shape
    mask = idb > 0
    edge = np.zeros_like(mask)
    for dy, dx in ((0, 1), (1, 0)):
        s = shift(idb, dy, dx)
        edge |= (idb != s) & mask & (s > 0)
    inner = dilate(edge, 1)
    outer = dilate(mask, 4) & ~mask
    col = np.ones((H, W, 3), np.float32)
    lut = np.ones((max(regname) + 1, 3), np.float32)
    for rid, key in regname.items():
        if key:
            lut[rid] = hex_rgb(COLOURS.get(key[1], "#FFFFFF"))
    fill = lut[idb]
    # crayon grain: diagonal strokes plus paper tooth showing through
    rng = np.random.default_rng(7)
    n = rng.random((H, W)).astype(np.float32)
    st = sum(shift(n, k, k) for k in range(-5, 6)) / 11.0
    tooth = rng.random((H, W)) > 0.965
    grain = fill * (1.0 - 0.14 * (st - 0.5)[..., None])
    grain = np.where(tooth[..., None], grain * 0.8 + 0.2, grain)
    demo = np.where(mask[..., None], grain, col)
    line = np.ones((H, W, 3), np.float32)
    for arr in (line, demo):
        arr[crease & mask & ~inner] = (0.55, 0.55, 0.55)
        arr[inner | outer] = (0.08, 0.08, 0.08)
    # character placeholders (proposal only): dashed boxes
    for ch, c in CHAR_PROPOSAL.items():
        x0, y0, x1, y1 = c["box"]
        X0, Y1 = to_px(x0 + 0.5, y0 / ART_H); X1, Y0 = to_px(x1 + 0.5, y1 / ART_H)
        X0, X1, Y0, Y1 = int(X0), int(X1), int(Y0), int(Y1)
        for arr in (line, demo):
            for xx in range(X0, X1, 12):
                arr[Y0:Y0 + 3, xx:xx + 6] = 0.6; arr[Y1 - 3:Y1, xx:xx + 6] = 0.6
            for yy in range(Y0, Y1, 12):
                arr[yy:yy + 6, X0:X0 + 3] = 0.6; arr[yy:yy + 6, X1 - 3:X1] = 0.6
    # art rectangle frame (thin, light) for orientation
    ax0, ay0 = ART[0], ART[1]; ax1, ay1 = ART[0] + ART[2], ART[1] + ART[3]
    for arr in (line, demo):
        arr[ay0:ay0 + 2, ax0:ax1] = 0.75; arr[ay1 - 2:ay1, ax0:ax1] = 0.75
        arr[ay0:ay1, ax0:ax0 + 2] = 0.75; arr[ay0:ay1, ax1 - 2:ax1] = 0.75
    save_png(line, os.path.join(WORK, "palace_drawings_lineart.png"))      # quick look; the sheet is make_sheet.py
    save_png(demo, os.path.join(WORK, "palace_drawings_demo.png"))
    # preview texture: colours without lines, grown outward so edge texels never hit white
    tex = np.where(mask[..., None], grain, 0.0); got = mask.copy()
    for _ in range(10):
        for dy, dx in ((0, 1), (0, -1), (1, 0), (-1, 0)):
            sm = shift(got, dy, dx); sv = shift(tex, dy, dx)
            take = sm & ~got
            tex[take] = sv[take]; got |= take
    tex[~got] = 1.0
    return tex, demo


def safe_texels(idb, regname, crease):
    """(drawing, region) -> uv of the pixel deepest inside that region's printed area (furthest from every line)"""
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
        while True:                                  # erode until one more step would empty it
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


def fix_up_faces(objs, specs, idb, regname, crease):
    """Upward-facing faces of front-projected pieces collapse onto one printed row (often the ink line or the
    drawing above it); seen from above they would be dark slabs. They take one texel from deep inside their own
    region's printed area instead (table top -> cloth front, seat -> cushion front, rims, wall tops ...)."""
    tex = safe_texels(idb, regname, crease)
    count = {}
    for name, ob in objs.items():
        sp = specs[name]
        if ob.type == 'MESH' and sp["kind"] == "tile":        # floor: each tile one clean texel of its swatch cell
            me = ob.data; lay = me.uv_layers["UVMap"].data; regs = FACE_REGIONS[name]
            for p in me.polygons:
                uv = tex.get(("floor", regs[p.index]))
                if uv is not None:
                    for li in p.loop_indices:
                        lay[li].uv = uv
            count[name] = len(me.polygons)
            continue
        if ob.type != 'MESH' or sp["kind"] != "front":
            continue
        oblique = sp.get("k", 0.0) != 0.0                # dais: thin tread bands only; the rug band is wide
        g = SHARED[name][0] if name in SHARED else next(k for k, v in DRAWINGS.items() if name in v["members"])
        me = ob.data; lay = me.uv_layers["UVMap"].data
        nm = ob.matrix_world.to_3x3()
        regs = FACE_REGIONS[name]
        n = 0
        for p in me.polygons:
            wn = (nm @ p.normal).normalized()
            if wn.z < 0.6:                               # Blender Z = design h (up)
                continue
            if oblique and regs[p.index] == "daisRug":
                continue
            uv = tex.get((g, regs[p.index]))
            if uv is None:
                continue
            for li in p.loop_indices:
                lay[li].uv = uv
            n += 1
        if n:
            count[name] = n
    return count


def write_set_id(idb2, regname, crease2, specs):
    """Set drawings for the sheet tool (tools/story/make_sheet.py): page frame at 2x (2480 x 3508). R = region id
    (1..N, 0 = none), G = 255 on detail lines (folds, flutes, bricks, feathers, depth steps), alpha = 255."""
    H, W = idb2.shape
    a = np.zeros((H, W, 4), np.float32)
    a[..., 0] = idb2 / 255.0; a[..., 1] = crease2.astype(np.float32); a[..., 3] = 1.0
    save_png(a, os.path.join(MODEL, "set_id_2x.png"))
    users = {}
    for n, (g, how) in SHARED.items():
        users.setdefault(g, []).append(n)
    ids = []
    for rid, key in regname.items():
        if not key:
            continue
        g, reg = key
        ids.append({"id": rid, "char": "set", "part": g, "region": reg, "hex": COLOURS.get(reg, "#FFFFFF"),
                    "nodes": DRAWINGS[g]["members"] + users.get(g, [])})
    const = [{"node": n, "uv": sp["uv"], "region": "curtainBand"} for n, sp in specs.items() if sp["kind"] == "const"]
    json.dump({"note": "set drawings at 2x of the page (1240 x 1754 @150 dpi): R = id, G = detail line mask; "
                       "written by pipeline/es_palace.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
              open(os.path.join(MODEL, "set_id_2x.json"), "w"), indent=1)


# ============================================================================================ checks
def check_layout():
    """drawings inside the art rect, apart from each other and above the figures' band"""
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
    """max set height around the actors' marks (radius 0.045): must be floor/carpet only"""
    pts = []
    for name, ob in objs.items():
        if ob.type != 'MESH' or name in ("floor", "carpet"):
            continue
        for x, h, z in world_verts(ob):
            pts.append((x, h, z, name))
    P = np.array([p[:3] for p in pts]); names = [p[3] for p in pts]
    table_items = {"table", "goblet1", "goblet2", "bowl", "bread"}
    marks = [("esther start", -0.32, 0.18, False), ("esther walk", -0.12, 0.12, False), ("steps foot", 0.0, -0.12, False, 0.028),
             ("esther wave", -0.04, 0.14, False), ("esther banquet", 0.06, 0.10, False),
             ("haman start", 0.36, 0.02, True), ("haman strut", 0.24, 0.06, True), ("haman whisper", 0.16, -0.24, False),
             ("haman banquet", 0.36, 0.10, False)]
    for t in np.linspace(0, 1, 9):                     # Esther's walks
        marks.append(("esther path a", -0.32 + 0.20 * t, 0.18 - 0.06 * t, False))
        if t < 0.86:
            marks.append(("esther path b", -0.12 + 0.12 * t, 0.12 - 0.24 * t, False))
        marks.append(("haman path", 0.24 - 0.08 * t, 0.06 - 0.30 * t, True))
    out = {}
    for m in marks:
        label, x, z, no_table = m[:4]; rad = m[4] if len(m) > 4 else 0.045
        d = np.hypot(P[:, 0] - x, P[:, 2] - z)
        sel = [i for i in np.where(d < rad)[0] if not (no_table and names[i] in table_items)]
        hmax = max([P[i, 1] for i in sel], default=0.0)
        if hmax > 0.006:
            out[label] = (round(float(hmax), 4), sorted({names[i] for i in sel}))
    return out


# ============================================================================================ build
def es_page_mat():
    m = bpy.data.materials.new("es_page")
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.85
    return m


STATE = {}


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = link(bpy.data.objects.new("palace", None))
    objs = {}
    objs["floor"] = build_floor(root)
    objs["carpet"] = build_carpet(root)
    objs["dais"] = build_dais(root)
    objs["throne"] = build_throne(root)
    objs["columnL"] = build_column("columnL", -COL_X, COL_Z, root)
    objs["columnR"] = build_column("columnR", COL_X, COL_Z, root)
    rig, objs["curtainL"], objs["curtainR"], objs["curtainRod"] = build_curtains(root)
    objs["brazierL"] = build_brazier("brazierL", -BRZ_X, BRZ_Z, root)
    objs["brazierR"] = build_brazier("brazierR", BRZ_X, BRZ_Z, root)
    flames = {"flameL": (-BRZ_X, 0.148, BRZ_Z), "flameR": (BRZ_X, 0.148, BRZ_Z)}
    for n, p in flames.items():
        empty(n, p, root)
    objs["wallRelief"] = build_wall(root)
    objs["table"], items = build_table(root)
    objs.update(items)
    bpy.context.view_layer.update()
    specs = setup_maps(objs)
    apply_uvs(objs, specs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("PALACE_TRIS", total, json.dumps(tris))
    assert total <= MAX_TRIS, "over budget %d" % total
    lay = check_layout()
    clr = check_clearance(objs)
    print("LAYOUT", "OK" if not lay else lay)
    print("CLEARANCE", "OK" if not clr else json.dumps(clr))
    RS[0] = 2
    idb2, regname, crease2 = raster_drawings(objs, specs)
    RS[0] = 1
    write_set_id(idb2, regname, crease2, specs)
    idb = idb2[1::2, 1::2]
    crease = crease2.reshape(PAGE[1], 2, PAGE[0], 2).any(axis=(1, 3))
    STATE["upFaces"] = fix_up_faces(objs, specs, idb, regname, crease)
    print("UP_FACES", json.dumps(STATE["upFaces"]))
    tex, demo = compose_sheets(idb, regname, crease)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    # export with the one page material
    pm = es_page_mat()
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pm)
        ob.data.polygons.foreach_set("material_index", [0] * len(ob.data.polygons))
    bpy.ops.object.select_all(action='DESELECT')
    for ob in [root] + list(root.children_recursive):
        ob.select_set(True)
    bpy.context.view_layer.objects.active = root
    sc.frame_set(1)
    bpy.ops.export_scene.gltf(filepath=GLB, use_selection=True, export_yup=True, export_apply=False,
                              export_skins=True, export_animations=True, export_def_bones=False,
                              export_texcoords=True, export_normals=True, export_materials='EXPORT',
                              export_morph=False, export_anim_single_armature=False)
    # heights for the record
    hmax = {n: round(max(v[1] for v in world_verts(ob)), 4) for n, ob in objs.items()}
    seat_h = round(DAIS_TOP + 0.116, 4)
    write_design(objs, specs, tris, total, flames, hmax, seat_h)
    STATE.update(objs=objs, specs=specs, tex=tex, demo=demo, root=root, rig=rig, flames=flames, regname=regname)
    print("BUILD_OK", GLB, total)


def write_design(objs, specs, tris, total, flames, hmax, seat_h):
    d = json.load(open(DESIGN_JSON)) if os.path.exists(DESIGN_JSON) else {}
    if "version" not in d:
        d["version"] = 1
    pieces = []
    for name in ["floor", "carpet", "dais", "throne", "columnL", "columnR", "curtainL", "curtainR", "curtainRod",
                 "brazierL", "brazierR", "wallRelief", "table", "goblet1", "goblet2", "bowl", "bread"]:
        sp = specs[name]
        g = next((k for k, v in DRAWINGS.items() if name in v["members"]), None)
        if name in SHARED:
            g = SHARED[name][0]
        fu = {k: (round(v, 5) if isinstance(v, float) else v) for k, v in sp.items()
              if k in ("kind", "scale", "sheetX", "sheetY", "k", "zRef", "mirror", "uv")}
        if sp["kind"] == "tile":
            fu["tile"] = sp["tile"]
        regs = sorted(set(FACE_REGIONS.get(name, [])))
        pieces.append({"id": name, "drawing": g, "frontUV": fu, "regions": regs, "heightMax": hmax[name],
                       "tris": tris[name],
                       "sharesDrawing": (SHARED[name][1] + " of " + DRAWINGS[SHARED[name][0]]["members"][0])
                       if name in SHARED else None})
    drawings = {g: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dsp.items() if k != "tile"}
                for g, dsp in DRAWINGS.items()}
    d["set"] = {
        "generatedBy": "pipeline/es_palace.py",
        "doc": "docs/esther/SET.md",
        "contract": "docs/esther/CONTRACT.md §6",
        "root": "palace",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "daisTop": DAIS_TOP,
        "throneSeat": {"x": 0.0, "z": MARKS["throneSeat"][1], "h": seat_h,
                       "note": "top of the cushion; seat front edge z -0.226, back panel front z -0.379"},
        "marks": {"throneSeat": list(MARKS["throneSeat"]), "stepsFoot": list(MARKS["stepsFoot"]),
                  "table": list(MARKS["table"])},
        "flames": {k: [round(c, 4) for c in v] for k, v in flames.items()},
        "footprints": {"dais": {"steps": [[0.135, -0.150], [0.125, -0.170], [0.115, -0.190]], "back": -0.50,
                                "note": "half-width, front z per step"},
                       "columns": [[-COL_X, COL_Z], [COL_X, COL_Z]], "braziers": [[-BRZ_X, BRZ_Z], [BRZ_X, BRZ_Z]],
                       "table": [0.145, 0.045, 0.295, 0.115], "carpet": [-0.12, -0.118, 0.12, 0.205],
                       "floor": [-0.60, -0.5875, 0.60, 0.21], "wall": [-0.60, -0.64, 0.60, -0.58]},
        "animations": {"curtainSway": {"node": "curtains", "length": 4.0, "fps": 24, "loop": True}},
        "hiddenAtStart": ["table"],
        "uvRule": {
            "front": "u = m*x / scale + sheetX + 0.5, v = ((h + k*(zRef - z)) / scale + sheetY) / 1.227 "
                     "(m = -1 when mirror; k = 0 unless given)",
            "plan": "u = x / scale + sheetX + 0.5, v = ((zRef - z) / scale + sheetY) / 1.227",
            "tile": "tile (i, j) local (lx, lz): u = sheetX + ((i%2)*w + lx) / scale + 0.5, "
                    "v = (sheetY + ((j%2)*d + lz) / scale) / 1.227",
            "const": "one uv for the whole mesh",
        },
        "drawings": drawings,
        "pieces": pieces,
        "sheetLayout": {
            "status": "final (2026-11-14): composed by tools/story/make_sheet.py esther from model/set_id_2x.png",
            "characters": CHAR_PROPOSAL,
            "note": "figures at the bottom (front view, scale 1, characters.<id>.sheetX/sheetY); set drawings above "
                    "them (set.drawings); outlines lie outside each drawing, so UVs need no inset",
        },
        "demoColours": COLOURS,
        "tris": total,
        "budget": MAX_TRIS,
    }
    json.dump(d, open(DESIGN_JSON, "w"), indent=1, ensure_ascii=False)


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


def tex_mat(name, img, rough=0.8):
    m = bpy.data.materials.new(name)
    try:
        m.use_nodes = True
    except Exception:
        pass
    nt = m.node_tree
    b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = rough
    try:
        b.inputs["Specular IOR Level"].default_value = 0.25
    except KeyError:
        pass
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.extension = 'EXTEND'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    mp = nt.nodes.new("ShaderNodeMapping")
    W, H = PAGE
    # UV is in art-rect space; the texture is the whole page
    mp.inputs["Location"].default_value = (ART[0] / W, (H - ART[1] - ART[3]) / H, 0)
    mp.inputs["Scale"].default_value = (ART[2] / W, ART[3] / H, 1)
    nt.links.new(uvn.outputs[0], mp.inputs[0]); nt.links.new(mp.outputs[0], t.inputs[0])
    nt.links.new(t.outputs[0], b.inputs["Base Color"])
    return m


def mannequins(layout, table_shown):
    """preview stand-ins only (not shipped): simple figures in the demo colours, at the actors' marks"""
    made = []

    def obj(name, mb, mats):
        ob = make_obj("pv_" + name, mb, None, smooth_angle=60)
        for i, m in enumerate(ob.data.materials):
            ob.data.materials[i] = mats[m.name.split("_", 1)[1].split(".")[0]] if m.name.startswith("pvm_") else m
        ob["pv"] = 1
        made.append(ob)

    mats = {k: flat_mat("pvm_" + k, v, 0.6) for k, v in {
        "skin": "#E9B48F", "ivory": "#F6EEDC", "crimson": "#C8323F", "gold": "#F2C14E", "hair": "#4A2E1F",
        "purple": "#6A3FB5", "beard": "#3A2418", "wine": "#8E2B3A", "mustard": "#D9A63A", "teal": "#1F5C66"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    for who, (x, z, yaw) in layout.items():
        mb = MB()
        if who == "esther":
            lathe(mb, [(0.0, 0.0), (0.052, 0.0), (0.050, 0.02), (0.040, 0.10), (0.030, 0.19), (0.026, 0.235),
                       (0.034, 0.255), (0.020, 0.268), (0.0, 0.27)], "ivory", C=(x, 0, z), seg=20)
            lathe(mb, [(0.0, 0.17), (0.031, 0.17), (0.031, 0.185), (0.0, 0.185)], "gold", C=(x, 0, z), seg=20)
            sphere(mb, (x, 0.300, z), 0.033, "skin", seg=16, rings=10)
            sphere(mb, (x, 0.306, z - 0.006), 0.035, "hair", seg=16, rings=10, sh=0.95)
            tube(mb, [(x + 0.03, 0.29, z + 0.005), (x + 0.04, 0.24, z + 0.012), (x + 0.042, 0.17, z + 0.012)],
                 [0.010, 0.009, 0.006], "hair", seg=8)
            lathe(mb, [(0.034, 0.326), (0.036, 0.330), (0.034, 0.336)], "gold", C=(x, 0, z - 0.003), seg=16)
            lathe(mb, [(0.050, 0.04), (0.042, 0.12), (0.036, 0.20), (0.037, 0.255)], "crimson",
                  C=(x, 0, z - 0.012), seg=14, sv=0.7, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.2 else 0.0001)
        elif who == "king":
            hs = DAIS_TOP + 0.116
            lathe(mb, [(0.0, hs), (0.050, hs), (0.044, hs + 0.04), (0.038, hs + 0.11), (0.046, hs + 0.13),
                       (0.022, hs + 0.145), (0.0, hs + 0.148)], "purple", C=(x, 0, z - 0.02), seg=20)
            lathe(mb, [(0.048, hs + 0.115), (0.050, hs + 0.13), (0.03, hs + 0.145)], "gold", C=(x, 0, z - 0.02), seg=20)
            for s in (-1, 1):
                tube(mb, [(x + s * 0.024, hs + 0.02, z - 0.02), (x + s * 0.026, hs + 0.018, z + 0.07)], 0.020, "purple",
                     seg=10)
                tube(mb, [(x + s * 0.026, hs + 0.018, z + 0.072), (x + s * 0.026, DAIS_TOP + 0.01, z + 0.085)], 0.016,
                     "purple", seg=10)
                tube(mb, [(x + s * 0.045, hs + 0.12, z - 0.02), (x + s * 0.06, hs + 0.06, z + 0.02),
                          (x + s * 0.07, hs + 0.055, z + 0.05)], 0.011, "purple", seg=8)
            sphere(mb, (x, hs + 0.178, z - 0.018), 0.034, "skin", seg=16, rings=10)
            sphere(mb, (x, hs + 0.160, z - 0.004), 0.024, "beard", seg=12, rings=8, sh=1.1, sz=0.8)
            lathe(mb, [(0.0, hs + 0.195), (0.030, hs + 0.195), (0.031, hs + 0.245, "gold"), (0.031, hs + 0.250),
                       (0.0, hs + 0.250)], "purple", C=(x, 0, z - 0.02), seg=16)
        else:
            lathe(mb, [(0.0, 0.0), (0.050, 0.0), (0.047, 0.03), (0.040, 0.12), (0.032, 0.21), (0.040, 0.26),
                       (0.022, 0.282), (0.0, 0.285)], "wine", C=(x, 0, z), seg=20)
            lathe(mb, [(0.041, 0.11), (0.037, 0.14)], "mustard", C=(x, 0, z), seg=20)
            sphere(mb, (x, 0.318, z), 0.032, "skin", seg=16, rings=10)
            lathe(mb, [(0.0, 0.335), (0.033, 0.335, "gold"), (0.034, 0.343, "teal"), (0.030, 0.365), (0.0, 0.372)],
                  "teal", C=(x, 0, z), seg=16)
            sphere(mb, (x, 0.297, z + 0.012), 0.012, "beard", seg=8, rings=6, sh=1.4)
        obj(who, mb, mats)
    return made


def mode_preview():
    if not STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "palace_preview_texture.png"))
    img.pack()
    pmat = tex_mat("pv_palace", img)
    for ob in objs.values():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    # paper (the coloured proposal sheet) on a wooden tabletop
    sheet = save_png(STATE["demo"], os.path.join(WORK, "palace_preview_sheet.png")); sheet.pack()
    W, H = PAGE; px = ART[2]
    x0, x1 = -ART[0] / px - 0.5, (W - ART[0]) / px - 0.5
    ztop = -(ART[1] + ART[3]) / px; zbot = (H - ART[1] - ART[3]) / px
    me = bpy.data.meshes.new("paper")
    me.from_pydata([B(x0, -0.001, zbot), B(x1, -0.001, zbot), B(x1, -0.001, ztop), B(x0, -0.001, ztop)], [],
                   [(0, 1, 2, 3)])
    uvl = me.uv_layers.new(name="UVMap")
    for li, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        uvl.data[li].uv = uv
    paper = link(bpy.data.objects.new("pv_paper", me))
    pm = bpy.data.materials.new("pv_paper_m")
    try:
        pm.use_nodes = True
    except Exception:
        pass
    t = pm.node_tree.nodes.new("ShaderNodeTexImage"); t.image = sheet
    pm.node_tree.links.new(t.outputs[0], pm.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    pm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 0.95
    me.materials.append(pm)
    tb = bpy.data.meshes.new("tabletop")
    tb.from_pydata([B(-4, -0.004, 4), B(4, -0.004, 4), B(4, -0.004, -4), B(-4, -0.004, -4)], [], [(0, 1, 2, 3)])
    tb.materials.append(flat_mat("pv_wood", "#6E4A33", 0.6))
    link(bpy.data.objects.new("pv_table", tb))
    # flames (preview only; the app plays brazier_fire) + warm point lights
    fl = flat_mat("pv_flame", "#FF7A2A", 0.5, emit=("#FF6A1E", 2.2))
    fl2 = flat_mat("pv_flame2", "#FFC040", 0.5, emit=("#FFB43A", 3.0))
    for n, (x, h, z) in STATE["flames"].items():
        mb = MB()
        lathe(mb, [(0.0, h - 0.006), (0.022, h), (0.018, h + 0.022), (0.010, h + 0.045), (0.0, h + 0.068)], "f1",
              C=(x, 0, z), seg=14, rfun=lambda th, i, k: 1.0 + 0.12 * math.sin(3 * th + i))
        ob = make_obj("pv_" + n, mb, None); ob.data.materials[0] = fl
        mb = MB()
        lathe(mb, [(0.0, h - 0.002), (0.012, h + 0.004), (0.009, h + 0.02), (0.0, h + 0.040)], "f2",
              C=(x, 0, z + 0.006), seg=12)
        ob = make_obj("pv_" + n + "_in", mb, None); ob.data.materials[0] = fl2
        L = bpy.data.lights.new("pv_" + n + "_l", 'POINT'); L.energy = 2.2; L.color = (1.0, 0.62, 0.32)
        L.shadow_soft_size = 0.02
        lo = link(bpy.data.objects.new("pv_" + n + "_l", L)); lo.location = B(x, h + 0.05, z + 0.01)
    sun = link(bpy.data.objects.new("pv_sun", bpy.data.lights.new("pv_sun", 'SUN')))
    sun.data.energy = 3.0; sun.data.angle = math.radians(4); sun.data.color = (1.0, 0.95, 0.86)
    sun.rotation_euler = (math.radians(40), math.radians(-18), math.radians(-28))
    fill = link(bpy.data.objects.new("pv_fill", bpy.data.lights.new("pv_fill", 'AREA')))
    fill.data.energy = 6.0; fill.data.size = 1.5; fill.data.color = (1.0, 0.86, 0.70)
    fill.location = B(0.0, 0.8, 1.2); fill.rotation_euler = (B(0, 0.1, -0.2) - fill.location).to_track_quat('-Z', 'Y').to_euler()
    sc.world = bpy.data.worlds.new("w")
    try:
        sc.world.use_nodes = True
    except Exception:
        pass
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.80, 0.82, 0.88, 1)
    bg.inputs[1].default_value = 0.75
    sc.render.engine = 'BLENDER_EEVEE'
    sc.view_settings.view_transform = 'Standard'
    try:
        sc.eevee.taa_render_samples = 32
    except AttributeError:
        pass
    cam = link(bpy.data.objects.new("pv_cam", bpy.data.cameras.new("pv_cam"))); sc.camera = cam
    cam.data.sensor_fit = 'VERTICAL'; cam.data.clip_start = 0.01; cam.data.clip_end = 30
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

    table_nodes = [objs[n] for n in ("table", "goblet1", "goblet2", "bowl", "bread")]

    def show_table(on):
        for o in table_nodes:
            o.hide_render = not on

    def cast(layout):
        for o in [o for o in bpy.data.objects if o.get("pv")]:
            bpy.data.objects.remove(o, do_unlink=True)
        if layout:
            mannequins(layout, False)

    opening = {"esther": (-0.32, 0.18, 0), "king": (0.0, -0.30, 0), "haman": (0.36, 0.02, -60)}
    show_table(False)
    cast({})
    phone = ((-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280))
    shoot("palace_preview_phone_set", *phone)
    shoot("palace_preview_front", (0.0, 0.26, 2.3), (0.0, 0.20, -0.30), 21, (1600, 1000))
    cast(opening)
    shoot("palace_preview_phone", *phone)
    shoot("palace_preview_orbit", orbit((0.0, 0.10, -0.15), 1.7, 0.55, -25), (0.0, 0.10, -0.15), 38, (1280, 720))
    show_table(True)
    cast({"esther": (0.06, 0.10, 30), "king": (0.0, -0.30, 0), "haman": (0.36, 0.10, -60)})
    shoot("palace_preview_banquet", orbit((0.22, 0.05, 0.08), 1.0, 0.35, -15), (0.20, 0.08, -0.05), 40, (1280, 720))
    show_table(False); cast({})
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "palace_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    if os.environ.get("ES_CLOSEUPS", "1") == "1":
        show_table(False); cast({})
        shoot("close_throne", (0.10, 0.30, 0.25), (0.0, 0.22, -0.32), 34, (1000, 1000), WORK)
        shoot("close_capital", (-0.16, 0.50, 0.05), (-0.28, 0.50, -0.43), 30, (1000, 1000), WORK)
        shoot("close_guardian", (-0.40, 0.18, -0.15), (-0.47, 0.13, -0.58), 40, (1000, 800), WORK)
        shoot("close_brazier", (-0.20, 0.18, 0.08), (-0.29, 0.08, -0.13), 36, (1000, 1000), WORK)
        show_table(True)
        shoot("close_table", (0.22, 0.20, 0.38), (0.22, 0.04, 0.08), 30, (1000, 800), WORK)
        shoot("close_carpet", (0.0, 0.40, 0.55), (0.0, 0.0, 0.0), 36, (1000, 800), WORK)
    print("PREVIEW_OK")


# ============================================================================================ verify
def mode_verify():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    bpy.ops.import_scene.gltf(filepath=GLB)
    names = {o.name for o in bpy.data.objects}
    need = ["palace", "floor", "carpet", "dais", "throne", "columnL", "columnR", "curtainL", "curtainR", "brazierL",
            "brazierR", "flameL", "flameR", "wallRelief", "table", "goblet1", "goblet2", "bowl", "bread"]
    missing = [n for n in need if n not in names]
    root = bpy.data.objects.get("palace")
    rootT = root is not None and root.matrix_world.is_identity if hasattr(root.matrix_world, "is_identity") else True
    tris = 0; uv_bad = 0
    for o in bpy.data.objects:
        if o.type == 'MESH':
            o.data.calc_loop_triangles(); tris += len(o.data.loop_triangles)
            if o.data.uv_layers:
                uv = np.zeros(len(o.data.loops) * 2); o.data.uv_layers[0].data.foreach_get("uv", uv)
                nb = int(((uv < 0) | (uv > 1)).sum()); uv_bad += nb
                if nb:
                    print("UV_OUTSIDE", o.name, nb, uv.reshape(-1, 2)[((uv < 0) | (uv > 1)).reshape(-1, 2).any(1)][:3])
            else:
                uv_bad += 1
    acts = [a.name for a in bpy.data.actions]
    parents = {n: (bpy.data.objects[n].parent.name if bpy.data.objects[n].parent else None)
               for n in ("goblet1", "goblet2", "bowl", "bread", "flameL", "flameR") if n in names}
    fl = {n: [round(c, 4) for c in D(bpy.data.objects[n].matrix_world.translation)] for n in ("flameL", "flameR")
          if n in names}
    sway = 0.0
    cl = bpy.data.objects.get("curtainL")
    if cl is not None:
        dg = bpy.context.evaluated_depsgraph_get()
        pos = []
        for f in (1, 25, 49):
            bpy.context.scene.frame_set(f); dg.update()
            me = cl.evaluated_get(dg).to_mesh()
            pos.append(np.array([tuple(cl.matrix_world @ v.co) for v in me.vertices]))
            cl.evaluated_get(dg).to_mesh_clear()
        sway = float(max(np.abs(pos[1] - pos[0]).max(), np.abs(pos[2] - pos[0]).max()))
    ok = not missing and tris <= MAX_TRIS and 0.002 < sway < 0.03 and uv_bad == 0 and any("curtainSway" in a for a in acts)
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "actions": acts, "parents": parents, "flames": fl,
                                                         "rootIdentity": rootT, "curtainSwayMax": round(sway, 4)}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
