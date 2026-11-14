"""Blender (headless): The prodigal son, story pack #6, home and the far country -> assets/prodigal/model/homeland.glb

A tabletop stage on the colouring sheet, back to front: a low backdrop (green Galilean hills with cypresses and olive
trees on the left, dry tawny hills, a glint of sea and a far headland on the right, the road winding away between);
the farmhouse (limestone, two storeys tall, flat roof with a parapet and a reed booth, an outside stair, an arched
wooden `door` in a stone frame, small windows, a grapevine on a pergola over the door); the courtyard (paving, a round
`well` with a windlass, a `figTree`, dry-stone walls on the west and the back, storage jars, a bench, a clay oven);
the field (planted furrows with young wheat, the bare hoeing strip); the pale `road` with its branch to the tavern;
the far-country `tavern` (a stoa with two fluted columns, a striped awning with a scalloped valance, bunting, tables,
stools, amphorae) and a market stall; the `pigpen` (fence with two gaps, mud, a lean-to, a trough with carob `pods`);
four round `pigs` (skinned, looping action `pigsWiggle`); hidden `feast` (long low table with food, cushions) and
`lamps` (oil lamps, door and string lanterns, with `lampsFlame*` empties).
Contract: docs/prodigal/CONTRACT.md §6. Details, nodes, marks and UV rules: docs/prodigal/SET.md.

Coordinates. Design / glTF (x, h, z): art-width units, page = XZ plane at h = 0, +z toward the viewer, +x right,
z = 0 at the art rectangle's bottom edge. In Blender (Z up) a design point (x, h, z) is (X, Y, Z) = (x, -z, h);
export_yup turns that back into glTF (x, h, z).

UV0 (every mesh, one material `pr_page` = the scanned art rectangle): as Exodus (pipeline/ex_egypt.py). Each piece
belongs to one *drawing* on the colouring sheet, a linear view a = A.P, b = B.P (depth D.P), and
  u = a / scale + sheetX + 0.5,   v = (b / scale + sheetY) / 1.227
P = the world position, or a drawing position (instanced pigs wear one pig drawing; small pieces are packed side by
side in their drawing so nothing hides behind anything else). Faces edge-on to their drawing or facing away from it
take one clean texel of their own region (LESSONS L51); scattered bits take the texel of a named (drawing, region).

Modes (run from the repo root):
  blender -b --factory-startup --python pipeline/pr_homeland.py -- build     homeland.glb + .blend + set_id_2x
  blender -b --factory-startup --python pipeline/pr_homeland.py -- verify    re-import homeland.glb and check it
  blender -b --factory-startup --python pipeline/pr_homeland.py -- all       build, preview, verify
  blender -b --factory-startup --python pipeline/pr_homeland.py -- check     build in memory, print the checks only
Work files go to $PR_WORK (default /tmp/pr_set_work).
"""
import bpy, bmesh, math, os, sys, json, random
import numpy as np
from mathutils import Vector, Quaternion
from mathutils.geometry import tessellate_polygon, delaunay_2d_cdt

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "all"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/prodigal/model")
GLB = os.path.join(MODEL, "homeland.glb")
BLEND = os.path.join(MODEL, "homeland.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/prodigal/design.json")
TIMELINE = os.path.join(ROOT, "assets/prodigal/timeline.json")
WORK = os.environ.get("PR_WORK", "/tmp/pr_set_work")
for d in (MODEL, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = 1.227
PAGE = (1240, 1754)
ART = (120, 283, 1000, 1227)
TARGET_TRIS = 70000                    # CONTRACT §6 (Exodus 69k)
MAX_TRIS = 75000                       # hard ceiling
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
    "fa door": (-0.30, -0.24), "fa look": (-0.16, -0.06), "fa meet": (0.00, 0.06), "fa feast": (-0.22, -0.10),
    "fa out": (-0.12, 0.08), "son home": (-0.16, -0.20), "son ask": (-0.22, -0.20), "son roadA": (-0.02, -0.04),
    "son roadB": (0.16, 0.06), "son tavern": (0.32, -0.26), "son pen": (0.34, 0.04), "son sit": (0.30, 0.10),
    "son roadC": (0.14, 0.12), "son hug": (0.10, 0.08), "son feast": (-0.32, -0.12), "son end": (0.06, 0.12),
    "bro field": (0.02, -0.34), "bro out": (-0.02, 0.10)}
FEAST_MARKS = [(-0.32, -0.12), (-0.22, -0.10)]   # the feast table keeps >= 0.06 from both (CONTRACT §6)
FEAST_CLEAR = 0.06
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
HIDDEN_AT_START = ["feast", "lamps"]


def visible_windows(node):
    """[(t0, t1)] when set node `node` is shown, from the timeline's prop events (homeland/<node>)"""
    vis = node not in HIDDEN_AT_START
    t_on = 0.0 if vis else None
    out = []
    for e in sorted((p for p in TL.get("props", []) if p["node"] == "homeland/" + node), key=lambda p: p["t"]):
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


SOFT_SEGS = []                # filled by mode_build: the first moves from the printed places


def clear_dist(x, z, soft=False):
    """distance from (x, z) to the nearest stage mark or hard path (soft: also the reported-only moves)"""
    d = min(math.hypot(x - a, z - b) for a, b in HARD_PTS)
    for a, b in HARD_SEGS + (SOFT_SEGS if soft else []):
        d = min(d, seg_dist((x, z), a, b))
    return d


# demo colouring (DESIGN.md table; the rest chosen to sit with it)
COLOURS = {
    # ground
    "grass": "#A9C46C", "earth": "#D8B98A", "road": "#E9D9B6", "paving": "#D9C29A", "soil": "#9A6A43",
    "wheat": "#B7C25A", "mud": "#7A5638",
    # backdrop
    "hillHome": "#A7C26A", "hillHomeFar": "#8DB06A", "hillFar": "#D9B77A", "hillFarBack": "#C29A6A", "sea": "#4E9CC9",
    "cypress": "#3F6E43", "olive": "#8FA876", "backRoad": "#E9D9B6", "town": "#F1EADB",
    # house
    "wall": "#E3D3B0", "roof": "#C9A77A", "door": "#8A5A3B", "frame": "#CDBB94", "windowDark": "#4A3324",
    "beam": "#8A5A3B", "vine": "#5E9A4A", "grapes": "#6B3F7A", "reed": "#D9C27A",
    # courtyard
    "wallStone": "#BFB49E", "well": "#A9A49A", "water": "#3E7FB0", "wood": "#9B6B43", "rope": "#C9A66B",
    "jar": "#C27A4A", "oven": "#C9875A", "figLeaf": "#5E9A4A", "figTrunk": "#8C7A68",
    # tavern
    "marble": "#F1EADB", "roofTile": "#C96F4A", "column": "#F6F0E2", "awning": "#D2483A", "awningB": "#F6F0E2", "paint": "#3E6FB0",
    "table": "#B07A47", "amphora": "#C46A3C", "stallCloth": "#F2C230", "fruit": "#F08A2E", "melon": "#7DB04A",
    "crate": "#B08A5A",
    # pig pen and pigs
    "fence": "#9B6B43", "trough": "#7E5536", "pods": "#6B4426", "shed": "#B08A5A", "straw": "#E9D08A",
    "pig": "#F2A7A0", "snout": "#E07F86",
    # feast and lamps
    "tableWood": "#8A5A3B", "cloth": "#FBF8EF", "bread": "#D9A45A", "dish": "#C9875A", "food": "#B5532E",
    "cup": "#E8B83A", "cushion": "#D2483A", "cushionB": "#3E6FB0", "lamp": "#C9875A", "lantern": "#4A4038",
    "lampGlass": "#F6D47A",
}
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
    if name in FORCE_NR:                                  # parts too small to colour: named texels (CONSTS)
        mb.N = [n or (r in FORCE_NR[name]) for n, r in zip(mb.N, mb.R)]
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

def flower(mb, c, r, reg, facing=(0, 0, 1)):
    f = Vector(facing).normalized()
    u = f.cross(Vector((0, 1, 0)))
    if u.length < 1e-3:
        u = Vector((1, 0, 0))
    u.normalize(); v = f.cross(u)
    lathe(mb, [(0.0, -0.25 * r), (r * 0.55, -0.15 * r), (r * 0.8, 0.35 * r), (r, 0.75 * r), (r * 0.25, 0.35 * r),
               (0.0, 0.3 * r)], reg, C=c, A=tuple(f), U=tuple(u), V=tuple(v), seg=10, smooth=True,
          rfun=lambda th, i, k: 1.0 + (0.32 * math.cos(6 * th) if 1 < i < 4 else 0.0))



# ============================================================================================ layout (design x, z)
HOUSE = (-0.52, -0.24, -0.55, -0.39)          # x0 x1 zBack zFront (footprint 0.28 x 0.16, centre (-0.38, -0.47))
HOUSE_H = 0.200
DOOR_X, DOOR_W, DOOR_SPRING = -0.330, 0.050, 0.068   # door centre x, width, arch springing height (top = +W/2)
FRAME_Z = -0.367                              # front of the stone door frame
DOOR_Z = -0.378                               # front face of the door panel (CONTRACT: z ~ -0.37)
STAIR_X = (-0.240, -0.205)
YARD = (-0.545, -0.080, -0.390, 0.020)        # paving x0 x1 z0 z1
WELL, WELL_R = (-0.46, -0.04), 0.040
FIG = (-0.50, -0.28)
BENCH = (-0.46, -0.32)
OVEN = (-0.505, -0.125)
FIELD = (-0.06, 0.24, -0.52, -0.28)
PLANT_Z = -0.402                              # planted rows behind, the bare hoeing strip in front
TAVERN = (0.255, 0.545, -0.535, -0.395)
TAV_C = (0.40, -0.47)
COLS_X, COL_Z, COL_H = (0.310, 0.490), -0.418, 0.150
AWN = (0.262, 0.538, -0.532, -0.365)          # awning x0 x1 zBack zFront
AWN_H = (0.214, 0.168)                        # awning height at the back wall and at the front edge
STALL = (0.54, -0.32)
PEN = (0.26, 0.56, -0.06, 0.18)
TROUGH = (0.48, 0.10)
TABLE_C = (-0.42, -0.215)
TABLE_W, TABLE_D, TABLE_H = 0.180, 0.065, 0.034
TROT_C, TROT_R = (0.522, 0.020), 0.017
PIG_SPOTS = [("eat", 0.462, 0.048, 90.0), ("eat", 0.445, 0.140, -40.0), ("wallow", 0.452, -0.022, 200.0),
             ("trot", TROT_C[0] - TROT_R, TROT_C[1], -90.0)]
HOME_FAR = [(0.245, -0.5875), (0.240, -0.40), (0.212, -0.24), (0.196, -0.08), (0.205, 0.06), (0.222, 0.21)]


def far_poly():
    return np.array(HOME_FAR + [(0.60, 0.21), (0.60, -0.5875)])


def yard_poly():
    x0, x1, z0, z1 = YARD
    east = [(x1 + 0.006 * math.sin(z * 41 + 0.5) + 0.004 * math.sin(z * 97), z) for z in np.linspace(z0, z1 - 0.02, 14)]
    south = [(x, z1 + 0.005 * math.sin(x * 37 + 1.1) + 0.003 * math.sin(x * 89)) for x in np.linspace(x1 - 0.02, x0, 16)]
    return np.array([(x0, z0)] + east + south)


def road_lines():
    main = catmull([(-0.115, -0.058), (-0.02, -0.012), (0.06, 0.030), (0.155, 0.090), (0.205, 0.21)], 0.008)
    branch = catmull([(0.125, 0.072), (0.195, -0.010), (0.255, -0.115), (0.300, -0.215), (0.340, -0.330)], 0.008)
    return main, branch


def road_polys():
    main, branch = road_lines()
    return strip_poly(main, 0.060, 0.078), strip_poly(branch, 0.052, 0.046)


def skirt(mb, poly, h, reg, h0=-0.0015):
    """vertical band from the outline of a flat piece down to the page (h may be a function (x, z))"""
    poly = [tuple(p) for p in poly]
    n = len(poly)
    area = sum(poly[i][0] * poly[(i + 1) % n][1] - poly[(i + 1) % n][0] * poly[i][1] for i in range(n))
    hf = h if callable(h) else (lambda x, z: h)
    for i in range(n):
        (ax, az), (bx, bz) = poly[i], poly[(i + 1) % n]
        o = (bz - az, 0, -(bx - ax)) if area < 0 else (-(bz - az), 0, bx - ax)
        mb.fo([mb.v(ax, hf(ax, az), az), mb.v(bx, hf(bx, bz), bz), mb.v(bx, h0, bz), mb.v(ax, h0, az)], reg, o)


def flat(mb, poly, h, reg, sk=True):
    ngon_top(mb, [tuple(p) for p in poly], h, reg)
    if sk:
        skirt(mb, poly, h, reg)


def pack(rows, sp, gap=0.014):
    """drawing places: shift each part's P so the parts of one drawing sit side by side (rows bottom to top, parts
    left to right) and nothing hides behind anything else on the sheet"""
    M = np.array([sp["A"], sp["B"]], float)
    E = np.linalg.pinv(M)
    b = 0.0
    skip = set().union(*FORCE_NR.values())
    for row in rows:
        a, top = 0.0, 0.0
        for mb in row:
            P = np.array(mb.P, float)
            used = sorted({i for f, r, n in zip(mb.F, mb.R, mb.N) if not n and r not in skip for i in f})
            A_, B_ = P[used] @ M[0], P[used] @ M[1]
            s = E @ np.array([a - A_.min(), b - B_.min()])
            mb.P = [tuple(p) for p in (P + s)]
            a += A_.max() - A_.min() + gap
            top = max(top, B_.max() - B_.min())
        b += top + gap


def merge(parts):
    out = MB()
    for p in parts:
        out.add(p, lambda q: q)
    return out


# ============================================================================================ ground
def build_ground(root):
    """the page floor: grass at home (left), dry earth in the far country (right), gently uneven, with a skirt; tufts,
    small flowers at home, dry scrub, pebbles and stones (named texels)"""
    far = far_poly()
    rect = np.array([(FLOOR[0], FLOOR[3]), (FLOOR[1], FLOOR[3]), (FLOOR[1], FLOOR[2]), (FLOOR[0], FLOOR[2])])
    bnd = _resample(np.array(HOME_FAR), 0.012)
    outlines = [_resample(rect, 0.03)]
    verts, edges = [], []
    for ol in outlines:
        b = len(verts)
        verts += [Vector((float(x), float(z))) for x, z in ol]
        edges += [(b + i, b + (i + 1) % len(ol)) for i in range(len(ol))]
    b = len(verts)
    verts += [Vector((float(x), float(z))) for x, z in bnd]
    edges += [(b + i, b + i + 1) for i in range(len(bnd) - 1)]
    allo = np.concatenate(outlines + [bnd])
    for j, z in enumerate(np.arange(FLOOR[2] + 0.02, FLOOR[3] - 0.01, 0.03)):
        for x in np.arange(FLOOR[0] + 0.02 + (j % 2) * 0.015, FLOOR[1] - 0.01, 0.03):
            p = np.array([x + (nz(x, z) - 0.5) * 0.012, z + (nz(z, x) - 0.5) * 0.012])
            if np.min(np.hypot(*(allo - p).T)) > 0.009:
                verts.append(Vector((float(p[0]), float(p[1]))))
    vs, es, fs, ov, oe, of = delaunay_2d_cdt(verts, edges, [], 0, 1e-7, True)
    V = np.array([(v.x, v.y) for v in vs])

    def height(x, z):
        return 0.0009 + 0.0009 * (math.sin(19 * x + 3 * z) * math.sin(13 * z - 5 * x) * 0.5 + 0.5) + 0.0003 * nz(x, z)
    mg = MB()
    ids = [mg.v(x, height(x, z), z) for x, z in V]
    for f in fs:
        if len(f) == 3:
            c = tuple(V[list(f)].mean(0))
            mg.fo([ids[i] for i in f], "earth" if in_poly(c, far) else "grass", UP)
    for (ax, az), (bx, bz) in zip(rect, np.roll(rect, -1, axis=0)):          # skirt round the page edge
        n = int(math.hypot(bx - ax, bz - az) / 0.05) + 1
        for i in range(n):
            x0, z0 = ax + (bx - ax) * i / n, az + (bz - az) * i / n
            x1, z1 = ax + (bx - ax) * (i + 1) / n, az + (bz - az) * (i + 1) / n
            reg = "earth" if in_poly(((x0 + x1) / 2 - 0.003 * np.sign((x0 + x1) / 2), (z0 + z1) / 2 + 0.003 * np.sign(-(z0 + z1) / 2 - 0.2)), far) else "grass"
            o = (0, 0, 1) if abs(az - bz) < 1e-6 and az > 0 else (0, 0, -1) if abs(az - bz) < 1e-6 else (np.sign(ax), 0, 0)
            mg.fo([mg.v(x0, height(x0, z0), z0), mg.v(x1, height(x1, z1), z1), mg.v(x1, -0.002, z1),
                   mg.v(x0, -0.002, z0)], reg, o)
    rng = random.Random(13)
    mg.nr = True
    roads = road_polys()
    blocked = [(-0.535, -0.195, -0.60, -0.355), (YARD[0] - 0.02, YARD[1] + 0.015, YARD[2] - 0.01, YARD[3] + 0.015),
               (FIELD[0] - 0.01, FIELD[1] + 0.01, FIELD[2] - 0.01, FIELD[3] + 0.005), (0.245, 0.555, -0.60, -0.355),
               (0.49, 0.59, -0.36, -0.28), (PEN[0] - 0.015, PEN[1] + 0.015, PEN[2] - 0.015, PEN[3] + 0.015),
               (-0.62, 0.62, -0.60, -0.548)]

    def free(x, z, pad=0.0):
        if not (FLOOR[0] + 0.012 < x < FLOOR[1] - 0.012 and FLOOR[2] + 0.04 < z < FLOOR[3] - 0.012):
            return False
        if any(in_poly((x, z), r) for r in roads):
            return False
        return not any(x0 - pad < x < x1 + pad and z0 - pad < z < z1 + pad for x0, x1, z0, z1 in blocked)
    tufts, tries = [], 0
    while len(tufts) < 80 and tries < 9000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z) or any(math.hypot(x - a, z - b) < 0.03 for a, b in tufts):
            continue
        tufts.append((x, z))
    for x, z in tufts:
        home = not in_poly((x, z), far)
        tall = (0.017 if home else 0.013) if clear_dist(x, z, True) > 0.07 else 0.0105
        for k in range(6 if home else 4):
            a = TAU * k / (6 if home else 4) + rng.uniform(-0.4, 0.4)
            hh = tall * rng.uniform(0.7, 1.05); lean = rng.uniform(0.3, 0.6) * hh
            d = (math.cos(a), math.sin(a))
            blade(mg, [(x + d[0] * 0.0015, 0.0005, z + d[1] * 0.0015), (x + d[0] * lean, hh, z + d[1] * lean)],
                  [0.0034, 0.0], "tuft" if home else "dryTuft", nrm=(d[0], 0.0, d[1]))
    flowers, tries = [], 0
    while len(flowers) < 34 and tries < 9000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.20), rng.uniform(-0.54, 0.20)
        if in_poly((x, z), far) or not free(x, z) or any(math.hypot(x - a, z - b) < 0.02 for a, b in flowers + tufts):
            continue
        flowers.append((x, z))
    for i, (x, z) in enumerate(flowers):
        hh = 0.0072 if clear_dist(x, z, True) < 0.07 else 0.011
        tube(mg, [(x, 0.0, z), (x + 0.001, hh, z)], 0.0007, "tuft", seg=3, caps=False)
        flower(mg, (x + 0.001, hh, z), 0.0034, "flowerY" if i % 3 else "flowerR", facing=(0, 1, 0.3))
    pebbles, tries = [], 0
    while len(pebbles) < 60 and tries < 9000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z) or any(math.hypot(x - a, z - b) < 0.016 for a, b in pebbles + tufts + flowers):
            continue
        pebbles.append((x, z))
    for i, (x, z) in enumerate(pebbles):
        r = rng.uniform(0.003, 0.0055)
        lumpy(mg, (x, r * 0.35, z), r, "pebble", seg=5, rings=3, sh=0.55, sx=rng.uniform(0.9, 1.4), amp=0.18, seed=i)
    rocks, tries = [], 0
    while len(rocks) < 14 and tries < 9000:
        tries += 1
        x, z = rng.uniform(-0.59, 0.59), rng.uniform(-0.55, 0.20)
        if not free(x, z, 0.01) or clear_dist(x, z, True) < 0.075:
            continue
        if any(math.hypot(x - a, z - b) < 0.06 for a, b in rocks) or \
                any(math.hypot(x - a, z - b) < 0.02 for a, b in pebbles + tufts + flowers):
            continue
        rocks.append((x, z))
    for i, (x, z) in enumerate(rocks):
        r = rng.uniform(0.008, 0.012)
        lumpy(mg, (x, r * 0.30, z), r, "stone", seg=7, rings=4, sh=0.62, sx=rng.uniform(1.0, 1.5), amp=0.2,
              seed=i + 700, smooth=False)
    mg.nr = False
    ob = make_obj("ground", mg, root, smooth_angle=35)
    return ob, {"tufts": len(tufts), "flowers": len(flowers), "pebbles": len(pebbles), "rocks": len(rocks)}


# ============================================================================================ road, courtyard paving, field
def build_road(root):
    """the pale dirt road (flat): from the courtyard gate past the far-country turn to the front edge, and the branch
    up to the tavern; wheel ruts printed as single lines"""
    mb = MB()
    main, branch = road_polys()
    flat(mb, branch, 0.0029, "road")
    flat(mb, main, 0.0031, "road")
    dec = DECOR.setdefault("ground", [])
    ml, bl = road_lines()
    for cl, w in ((ml, 0.016), (bl, 0.013)):
        for i in range(2, len(cl) - 3, 2):
            t = cl[i + 1] - cl[i]; t = t / (np.linalg.norm(t) + 1e-9); nn = np.array([-t[1], t[0]])
            for s in (-1, 1):
                a, b = cl[i] + nn * w * s, cl[i + 1] + nn * w * s
                dec.append(((a[0], 0.0033, a[1]), (b[0], 0.0033, b[1])))
    return make_obj("road", mb, root, origin=(0.06, 0.0, 0.03), smooth_angle=30)


def build_courtyard(root):
    """`courtyard`: the paved yard in front of the house (flagstones printed as single lines)"""
    mb = MB()
    poly = yard_poly()
    flat(mb, poly, 0.0036, "paving")
    dec = DECOR.setdefault("ground", [])
    x0, x1, z0, z1 = YARD
    rng = random.Random(5)
    zs = list(np.arange(z0 + 0.034, z1 + 0.01, 0.034))
    for z in zs:
        xs = np.linspace(x0, x1 + 0.01, 60)
        pts = [(x, z + 0.0025 * math.sin(x * 50 + z * 9)) for x in xs]
        pts = [p for p in pts if in_poly(p, poly)]
        for a, b in zip(pts[:-1], pts[1:]):
            dec.append(((a[0], 0.0037, a[1]), (b[0], 0.0037, b[1])))
    for r, (za, zb_) in enumerate(zip([z0] + zs, zs + [z1 + 0.01])):
        x = x0 + rng.uniform(0.01, 0.04)
        while x < x1 + 0.01:
            p0, p1 = (x, za + 0.002), (x + 0.004 * math.sin(x * 30), zb_ - 0.002)
            if in_poly(p0, poly) and in_poly(p1, poly):
                dec.append(((p0[0], 0.0037, p0[1]), (p1[0], 0.0037, p1[1])))
            x += rng.uniform(0.038, 0.056)
    return make_obj("courtyard", mb, root, origin=(-0.31, 0.0, -0.18), smooth_angle=30)


def build_field(root):
    """`field`: planted furrows (ridges with young wheat, h <= 0.05) behind the bare hoeing strip (flat soil)"""
    mb = MB()
    x0, x1, z0, z1 = FIELD
    edge = lambda x: 0.003 * math.sin(x * 47 + 0.3)
    plant = [(x, z0 + edge(x) * 0.5) for x in np.linspace(x0, x1, 16)] + \
        [(x, PLANT_Z + edge(x) * 0.4) for x in np.linspace(x1, x0, 16)]
    strip = [(x, PLANT_Z + edge(x) * 0.4) for x in np.linspace(x0, x1, 16)] + \
        [(x1 + 0.004 * math.sin(z * 60), z) for z in np.linspace(PLANT_Z + 0.01, z1 - 0.01, 6)] + \
        [(x, z1 + 0.004 * math.sin(x * 37)) for x in np.linspace(x1, x0, 16)] + \
        [(x0 + 0.004 * math.sin(z * 53), z) for z in np.linspace(z1 - 0.01, PLANT_Z + 0.01, 6)]
    flat(mb, plant, 0.0030, "wheat")
    flat(mb, strip, 0.0030, "soil")
    dec = DECOR.setdefault("ground", [])
    rows = list(np.arange(z0 + 0.012, PLANT_Z - 0.006, 0.0215))
    for zr in rows:                                               # ridges: low prisms along x
        cl = [(x, zr + 0.0015 * math.sin(x * 31 + zr * 7)) for x in np.linspace(x0 + 0.004, x1 - 0.004, 26)]
        L, C, R = [], [], []
        for x, z in cl:
            L.append(mb.v(x, 0.0031, z - 0.0085)); C.append(mb.v(x, 0.0085, z)); R.append(mb.v(x, 0.0031, z + 0.0085))
        for i in range(len(cl) - 1):
            mb.fo([L[i], L[i + 1], C[i + 1], C[i]], "wheat", (0, 1, -1), True)
            mb.fo([C[i], C[i + 1], R[i + 1], R[i]], "wheat", (0, 1, 1), True)
        if rows.index(zr) % 3 == 1:
            for a, b in zip(cl[:-1], cl[1:]):
                dec.append(((a[0], 0.0087, a[1]), (b[0], 0.0087, b[1])))
    rng = random.Random(21)
    for k in range(5):                                            # hoed clods in the strip (print only)
        x = x0 + 0.04 + k * 0.055 + rng.uniform(-0.008, 0.008); z = PLANT_Z + 0.02 + rng.uniform(0, 0.08)
        dec.append(((x, 0.0032, z), (x + 0.012, 0.0032, z + 0.002)))
    mb.nr = True
    for zr in rows:
        x = x0 + 0.008
        while x < x1 - 0.006:
            xx = x + rng.uniform(-0.002, 0.002); zz = zr + rng.uniform(-0.0015, 0.0015)
            for j in range(3):
                a = TAU * j / 3 + rng.uniform(-0.5, 0.5)
                hh = rng.uniform(0.022, 0.040); lean = rng.uniform(0.2, 0.45) * hh
                d = (math.cos(a), math.sin(a) * 0.6)
                blade(mb, [(xx, 0.0075, zz), (xx + d[0] * lean * 0.5, 0.0075 + hh * 0.55, zz + d[1] * lean * 0.5),
                           (xx + d[0] * lean, 0.0075 + hh, zz + d[1] * lean)], [0.0030, 0.0024, 0.0], "wheatBlade",
                      nrm=(d[0], 0.0, d[1]))
            x += rng.uniform(0.010, 0.014)
    mb.nr = False
    return make_obj("field", mb, root, origin=((x0 + x1) / 2, 0.0, (z0 + z1) / 2), smooth_angle=50)


# ============================================================================================ backdrop
def smooth(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def far_home(x):
    return smooth((0.265 - x) / 0.07) * (0.270 + 0.018 * math.sin(6.0 * x + 1.0) + 0.010 * math.sin(15 * x + 0.4))


def far_far(x):
    return smooth((x - 0.05) / 0.10) * (0.285 + 0.020 * math.sin(4.6 * x + 1.0) + 0.010 * math.sin(13 * x))


def near_home(x):
    return smooth((0.205 - x) / 0.05) * (0.100 + 0.026 * math.sin(8.0 * x + 0.3) + 0.010 * math.sin(19 * x + 1.0)
            - 0.040 * math.exp(-((x - 0.15) / 0.035) ** 2))


def near_far(x):
    return smooth((x - 0.105) / 0.06) * (0.092 + 0.022 * math.sin(9.0 * x + 1.5) + 0.009 * math.sin(21 * x)
            - 0.034 * math.exp(-((x - 0.13) / 0.03) ** 2))


SEA_TOP = 0.172


def build_backdrop(root):
    """low relief across the back: far green hills (left) and a far tawny headland (right) 0.19-0.29 high so the page
    beyond the stage is hidden from the phone; the sea strip in front of the headland; near green hills with cypresses
    and olive trees; near dry hills with a little white town; the road winding up the valley between; a sailing boat"""
    mb = MB()
    zb = FLOOR[2]
    xs = np.linspace(-0.60, 0.265, 60)
    extrude(mb, [(-0.60, 0.0), (0.265, 0.0)] + [(x, far_home(x)) for x in xs[::-1]], zb, zb + 0.005, "hillHomeFar")
    xs = np.linspace(0.05, 0.60, 44)
    extrude(mb, [(0.05, 0.0), (0.60, 0.0)] + [(x, far_far(x)) for x in xs[::-1]], zb + 0.0055, zb + 0.0105,
            "hillFarBack")
    xs = np.linspace(0.16, 0.60, 30)
    extrude(mb, [(0.16, 0.0), (0.60, 0.0)] + [(x, min(SEA_TOP + 0.0015 * math.sin(x * 40), 0.06 + (x - 0.16) * 3.0))
                                              for x in xs[::-1]], zb + 0.011, zb + 0.0145, "sea")
    dec = DECOR.setdefault("backdrop", [])
    rng = random.Random(3)
    for k in range(16):                                           # glints on the sea (print only)
        x = rng.uniform(0.22, 0.58); h = rng.uniform(0.150, 0.168)
        dec.append(((x, h, zb + 0.0147), (x + rng.uniform(0.008, 0.016), h, zb + 0.0147)))
    zc = zb + 0.0215
    xs = np.linspace(-0.60, 0.205, 62)
    puff(mb, [(-0.60, 0.0), (0.205, 0.0)] + [(x, near_home(x)) for x in xs[::-1]], zc, 0.0060, "hillHome",
         rad=0.012, edge=0.35, step=0.014)
    xs = np.linspace(0.105, 0.60, 40)
    puff(mb, [(0.105, 0.0), (0.60, 0.0)] + [(x, near_far(x)) for x in xs[::-1]], zc + 0.0015, 0.0060, "hillFar",
         rad=0.012, edge=0.35, step=0.014)
    # trees on the green hills: cypresses (tall flames) and olives (round grey-green crowns)
    tz = zc + 0.002
    for i, x in enumerate((-0.555, -0.43, -0.315, -0.205, -0.055, 0.035)):
        h0 = near_home(x) - 0.012; H = 0.062 + 0.022 * nz(i, 1); r = 0.0085 + 0.002 * nz(i, 2)
        lathe(mb, [(0.0, h0), (r * 0.6, h0), (r, h0 + H * 0.25), (r * 0.9, h0 + H * 0.55), (r * 0.45, h0 + H * 0.85),
                   (0.0, h0 + H)], "cypress", C=(x, 0, tz), seg=8, sv=0.6,
              rfun=lambda th, j, k: 1.0 + 0.10 * math.cos(3 * th + j))
    for i, x in enumerate((-0.49, -0.37, -0.26, -0.13, 0.075)):
        h0 = near_home(x) - 0.008; r = 0.014 + 0.003 * nz(i, 5)
        tube(mb, [(x, h0, tz), (x + 0.002, h0 + 0.014, tz)], 0.0025, "olive", seg=5)
        lumpy(mb, (x + 0.002, h0 + 0.014 + r * 0.7, tz), r, "olive", seg=10, rings=6, sh=0.75, sz=0.55, amp=0.16,
              seed=i + 20)
    # a little white town on the dry hills, a sailing boat on the sea
    for i, (x, w, hgt) in enumerate(((0.405, 0.016, 0.014), (0.424, 0.014, 0.020), (0.441, 0.018, 0.012),
                                     (0.462, 0.013, 0.017), (0.480, 0.016, 0.011))):
        h0 = near_far(x) - 0.006
        box(mb, x - w / 2, x + w / 2, h0, h0 + hgt, zc - 0.002, zc + 0.006, "town", skip=("bottom",))
        dec.append(((x - 0.002, h0 + hgt * 0.6, zc + 0.0062), (x + 0.002, h0 + hgt * 0.6, zc + 0.0062)))
    lathe(mb, [(0.0, 0.0), (0.006, 0.0), (0.0, 0.0045)], "town", C=(0.424, near_far(0.424) - 0.006 + 0.020, zc + 0.002),
          seg=10)
    bx, bh = 0.52, SEA_TOP - 0.012
    extrude(mb, [(bx - 0.010, bh + 0.004), (bx + 0.008, bh + 0.004), (bx + 0.0, bh + 0.026)], zb + 0.0146,
            zb + 0.0152, "town")
    mb.nr = True
    extrude(mb, [(bx - 0.016, bh + 0.004), (bx + 0.014, bh + 0.004), (bx + 0.010, bh - 0.002), (bx - 0.012, bh - 0.002)],
            zb + 0.0146, zb + 0.0154, "boat")
    mb.nr = False
    return make_obj("backdrop", mb, root, origin=(0.0, 0.0, -0.575), smooth_angle=50)


# ============================================================================================ house
def arch_poly(cx, w, spring, n=10, h0=0.0):
    r = w / 2
    return [(cx - r, h0), (cx + r, h0), (cx + r, spring)] + \
        [(cx + r * math.cos(math.pi * k / n), spring + r * math.sin(math.pi * k / n)) for k in range(1, n)] + \
        [(cx - r, spring)]


def build_house(root):
    """the farmhouse: limestone walls (quoins and stone courses printed as lines), flat roof with a parapet, beam
    ends, an upper string course, small windows with wooden lattices, an arched stone door frame and step, a grapevine
    on a pergola over the door, an outside stair up the east side, a reed booth and jars on the roof. Child `door`
    (origin at its hinge)."""
    mb = MB()
    dec = DECOR.setdefault("house", [])
    x0, x1, zb, zf = HOUSE
    H = HOUSE_H
    wins = [(-0.468, 0.048, 0.078, 0.026), (-0.468, 0.128, 0.160, 0.024), (-0.398, 0.128, 0.160, 0.024),
            (-0.270, 0.128, 0.160, 0.024)]                                       # (x, h0, h1, w)
    holes = [[(x - w / 2, h0), (x + w / 2, h0), (x + w / 2, h1), (x - w / 2, h1)] for x, h0, h1, w in wins]
    outer = [(x0, 0.0), (x1, 0.0), (x1, H), (x0, H)]
    tris = tessellate_polygon([[Vector((a, b, 0)) for a, b in outer]] + [[Vector((a, b, 0)) for a, b in h] for h in holes])
    allp = outer + sum(holes, [])
    vi = [mb.v(a, b, zf) for a, b in allp]
    for t in tris:
        mb.fo([vi[i] for i in t], "wall", (0, 0, 1))
    for hole in holes:
        for i in range(4):
            a, b = hole[i], hole[(i + 1) % 4]
            ddx, ddh = b[0] - a[0], b[1] - a[1]
            mb.fo([mb.v(a[0], a[1], zf), mb.v(b[0], b[1], zf), mb.v(b[0], b[1], zf - 0.010),
                   mb.v(a[0], a[1], zf - 0.010)], "wall", (-ddh, ddx, 0))
        box(mb, hole[0][0], hole[1][0], hole[0][1], hole[2][1], zf - 0.011, zf - 0.010, "windowDark", skip=("back",))
        xa, xb_, ha, hb = hole[0][0], hole[1][0], hole[0][1], hole[2][1]
        box(mb, xa - 0.005, xb_ + 0.005, ha - 0.004, ha, zf - 0.002, zf + 0.004, "beam", skip=("back",))   # sill
        box(mb, xa - 0.004, xb_ + 0.004, hb, hb + 0.005, zf - 0.002, zf + 0.003, "beam", skip=("back",))   # lintel
        for k in (1, 2):                                                  # lattice bars
            xx = xa + (xb_ - xa) * k / 3
            box(mb, xx - 0.0012, xx + 0.0012, ha, hb, zf - 0.006, zf - 0.004, "beam", skip=("back",))
        hm = (ha + hb) / 2
        box(mb, xa, xb_, hm - 0.0012, hm + 0.0012, zf - 0.0065, zf - 0.0045, "beam", skip=("back",))
    box(mb, x0, x1, 0.0, H, zb, zf, "wall", skip=("front", "bottom", "top"))
    # roof, parapet, beam ends, string course
    box(mb, x0 + 0.004, x1 - 0.004, H - 0.003, H, zb + 0.004, zf - 0.004, "roof", skip=("bottom",))
    for (a0, a1, c0, c1) in ((x0 - 0.002, x1 + 0.002, zf - 0.006, zf + 0.002), (x0 - 0.002, x1 + 0.002, zb - 0.002, zb + 0.006),
                             (x0 - 0.002, x0 + 0.006, zb, zf), (x1 - 0.006, x1 + 0.002, zb, zf)):
        box(mb, a0, a1, H, H + 0.013, c0, c1, "wall", skip=("bottom",))
    for x in np.linspace(x0 + 0.016, x1 - 0.016, 9):
        if any(abs(x - w[0]) < 0.016 for w in wins):
            continue
        lathe(mb, [(0.0, 0.0), (0.0034, 0.0), (0.0034, 0.011), (0.0, 0.0115)], "beam", C=(x, H - 0.012, zf - 0.002),
              A=(0, 0, 1), U=(1, 0, 0), V=(0, 1, 0), seg=6)
    for (a, b) in ((x0 - 0.002, DOOR_X - DOOR_W / 2 - 0.016), (DOOR_X + DOOR_W / 2 + 0.016, x1 + 0.002)):
        box(mb, a, b, 0.104, 0.111, zf - 0.002, zf + 0.0045, "frame", skip=("back",))
    # stone courses: quoins at both front corners and patches of coursed stone (single lines)
    zq = zf + 0.0003
    for k, hh in enumerate(np.arange(0.0, H - 0.01, 0.022)):
        for xc, sgn in ((x0, 1), (x1, -1)):
            w = 0.030 if k % 2 == 0 else 0.019
            dec.append(((xc + sgn * w, hh, zq), (xc + sgn * w, hh + 0.022, zq)))
            dec.append(((xc, hh + 0.022, zq), (xc + sgn * w, hh + 0.022, zq)))
    rng = random.Random(9)
    for (px0, px1, ph0, ph1) in ((-0.448, -0.408, 0.018, 0.090), (-0.300, -0.268, 0.030, 0.098),
                                 (-0.440, -0.300, 0.168, 0.196), (-0.505, -0.485, 0.112, 0.150)):
        for r, hb in enumerate(np.arange(ph0, ph1, 0.0145)):
            dec.append(((px0, hb, zq), (px1, hb, zq)))
            for xx in np.arange(px0 + (r % 2) * 0.012 + rng.uniform(0, 0.006), px1, 0.024):
                dec.append(((xx, hb, zq), (xx, min(hb + 0.0145, ph1), zq)))
    for k, hh in enumerate(np.arange(0.02, H - 0.01, 0.03)):              # east side courses (seen in the drawing)
        dec.append(((x1 + 0.0003, hh, zb), (x1 + 0.0003, hh, zf)))
    # door frame: two pilasters, an arch with a keystone, a step
    fw = 0.011
    for s in (-1, 1):
        xa = DOOR_X + s * (DOOR_W / 2 + fw / 2)
        box(mb, xa - fw / 2, xa + fw / 2, 0.0, DOOR_SPRING, zf, FRAME_Z, "frame", skip=("bottom",))
        box(mb, xa - fw / 2 - 0.002, xa + fw / 2 + 0.002, DOOR_SPRING - 0.004, DOOR_SPRING, zf, FRAME_Z + 0.002,
            "frame", skip=("bottom",))
    r0, r1 = DOOR_W / 2, DOOR_W / 2 + fw
    ring = [(DOOR_X + r1 * math.cos(math.pi * k / 12), DOOR_SPRING + r1 * math.sin(math.pi * k / 12)) for k in range(13)] + \
        [(DOOR_X + r0 * math.cos(math.pi * k / 12), DOOR_SPRING + r0 * math.sin(math.pi * k / 12)) for k in range(12, -1, -1)]
    extrude(mb, ring, zf, FRAME_Z, "frame", back=False)
    extrude(mb, [(DOOR_X - 0.006, DOOR_SPRING + r0 - 0.001), (DOOR_X + 0.006, DOOR_SPRING + r0 - 0.001),
                 (DOOR_X + 0.008, DOOR_SPRING + r1 + 0.003), (DOOR_X - 0.008, DOOR_SPRING + r1 + 0.003)],
            zf, FRAME_Z + 0.002, "frame", back=False)
    box(mb, DOOR_X - 0.040, DOOR_X + 0.040, 0.0, 0.0065, zf, -0.357, "frame", skip=("bottom",))
    box(mb, DOOR_X - r0, DOOR_X + r0, 0.0, DOOR_SPRING + r0, zf - 0.001, zf + 0.0004, "windowDark", skip=("back",))
    # pergola with a grapevine over the door
    pz = -0.353
    for px in (-0.379, -0.281):
        box(mb, px - 0.0035, px + 0.0035, 0.114, 0.121, zf, pz - 0.002, "beam")
        tube(mb, [(px, 0.0, pz + 0.001), (px, 0.116, pz + 0.001)], 0.0030, "beam", seg=6)
    box(mb, -0.392, -0.268, 0.121, 0.127, pz - 0.006, pz + 0.002, "beam")
    vine = [(-0.386, 0.0, pz + 0.004), (-0.383, 0.030, pz + 0.006), (-0.388, 0.062, pz + 0.004), (-0.382, 0.096, pz + 0.006),
            (-0.375, 0.124, pz + 0.002), (-0.350, 0.131, pz - 0.006), (-0.320, 0.129, pz - 0.004), (-0.290, 0.132, pz - 0.006)]
    tube(mb, vine, [0.0034, 0.0030, 0.0027, 0.0025, 0.0022, 0.0018, 0.0015, 0.0012], "beam", seg=6)
    rng = random.Random(17)
    for k in range(13):                                                   # leaf clumps along the beam and rafters
        t = k / 12
        c = (-0.392 + 0.126 * t + rng.uniform(-0.004, 0.004), 0.130 + 0.006 * nz(k, 3), pz - 0.010 + rng.uniform(-0.010, 0.008))
        lumpy(mb, c, 0.0105 + 0.003 * nz(k, 1), "vine", seg=8, rings=5, sh=0.6, amp=0.22, seed=k + 3)
    for k in range(4):
        c = (-0.384 + 0.004 * nz(k, 9), 0.040 + 0.024 * k, pz + 0.008)
        lumpy(mb, c, 0.0072, "vine", seg=7, rings=4, sh=0.8, sz=0.6, amp=0.2, seed=k + 30)
    for k in range(18):                                                   # single leaves facing the viewer
        x = -0.392 + 0.124 * rng.random(); h = 0.118 + 0.026 * rng.random() if k < 14 else 0.03 + 0.08 * rng.random()
        if k >= 14:
            x = -0.384 + rng.uniform(-0.006, 0.006)
        c = Vector((x, h, pz + 0.004 + 0.004 * rng.random()))
        leaf(mb, c, Vector((rng.uniform(-0.6, 0.6), -0.5, 0.3)).normalized(), Vector((0, 0.2, 1)).normalized(), 0.013,
             "vine")
    for gx in (-0.352, -0.304):                                           # grape bunches
        for j, (dx, dh) in enumerate(((0, 0), (-0.003, -0.004), (0.003, -0.004), (0, -0.008), (-0.0045, -0.0085),
                                      (0.0045, -0.0085), (0, -0.0125), (-0.003, -0.016), (0.003, -0.016), (0, -0.020))):
            sphere(mb, (gx + dx * 1.25, 0.118 + dh * 1.25, pz - 0.002 + 0.0015 * (j % 2)), 0.0042, "grapes", seg=6, rings=4)
    # outside stair up the east side, rising toward the back
    n = 9
    run = (zf - zb - 0.016) / n
    for k in range(n):
        za = zf - 0.004 - k * run
        box(mb, STAIR_X[0], STAIR_X[1], 0.0, H * (k + 1) / n, za - run, za, "wall", skip=("bottom",))
        dec.append(((STAIR_X[0], H * (k + 1) / n, za + 0.0002), (STAIR_X[1], H * (k + 1) / n, za + 0.0002)))
    box(mb, STAIR_X[0], STAIR_X[1], H - 0.001, H + 0.004, zb, zf - 0.004 - (n - 1) * run - run, "wall", skip=("bottom",))
    # jars on the roof
    for j, (rx, rz) in enumerate(((-0.290, -0.520), (-0.272, -0.505), (-0.410, -0.530))):
        lathe(mb, [(0.0, H), (0.0042, H), (0.0068, H + 0.007), (0.0064, H + 0.013), (0.0034, H + 0.019),
                   (0.0043, H + 0.0215), (0.0, H + 0.020)], "jar", C=(rx, 0, rz), seg=10)
    house = make_obj("house", mb, root, origin=(-0.38, 0.0, -0.47), smooth_angle=45, bevel=0.0006, bevel_angle=60)
    # the reed booth on the roof (its own place in the drawing so the roof under it keeps the roof colour)
    bm = MB()
    bx0, bx1, bz0, bz1 = -0.508, -0.446, -0.542, -0.494
    for px, pz_ in ((bx0, bz0), (bx1, bz0), (bx0, bz1), (bx1, bz1)):
        tube(bm, [(px, H, pz_), (px, H + 0.050, pz_)], 0.0024, "beam", seg=5)
    box(bm, bx0 - 0.006, bx1 + 0.006, H + 0.049, H + 0.054, bz0 - 0.006, bz1 + 0.008, "reed", skip=())
    for k in range(1, 12):
        xx = bx0 - 0.006 + (bx1 - bx0 + 0.012) * k / 12
        DECOR["house"].append(((xx, H + 0.0542, bz0 - 0.006), (xx, H + 0.0542, bz1 + 0.008)))
    sp = DRAWINGS["house"]
    off = np.array([0.0, 0.0, 0.0])
    bm.P = [(p[0] + 0.335, p[1] - H, p[2]) for p in bm.V]                 # drawn beside the house (P shifted)
    booth = make_obj("roofBooth", bm, house, origin=(-0.477, H, -0.518), smooth_angle=45)
    # the door (hinge at its left edge)
    dm = MB()
    extrude(dm, arch_poly(DOOR_X, DOOR_W, DOOR_SPRING, 12), DOOR_Z - 0.007, DOOR_Z, "door")
    for k in range(1, 5):
        xx = DOOR_X - DOOR_W / 2 + DOOR_W * k / 5
        top = DOOR_SPRING + math.sqrt(max(0.0, (DOOR_W / 2) ** 2 - (xx - DOOR_X) ** 2))
        DECOR["house"].append(((xx, 0.002, DOOR_Z + 0.0003), (xx, top - 0.001, DOOR_Z + 0.0003)))
    for hh in (0.016, 0.054):
        box(dm, DOOR_X - DOOR_W / 2 + 0.003, DOOR_X + DOOR_W / 2 - 0.003, hh, hh + 0.005, DOOR_Z, DOOR_Z + 0.0018, "door")
    dm.nr = True
    tube(dm, [(DOOR_X + 0.014 + 0.0045 * math.cos(TAU * k / 10), 0.042 + 0.0045 * math.sin(TAU * k / 10), DOOR_Z + 0.002)
              for k in range(10)], 0.0010, "ring", seg=4, closed=True)
    dm.nr = False
    door = make_obj("door", dm, house, origin=(DOOR_X - DOOR_W / 2, 0.0, DOOR_Z - 0.0035), smooth_angle=40)
    return house, door, booth


def leaf(mb, c, d, nrm, L, reg):
    """a lobed leaf (fig / vine) at c pointing along d, facing nrm: a mid lobe and two side lobes, double sided"""
    d = Vector(d).normalized(); nrm = Vector(nrm).normalized()
    side = d.cross(nrm).normalized()
    for ang, s in ((0.0, 1.0), (0.85, 0.72), (-0.85, 0.72)):
        dd = (d * math.cos(ang) + side * math.sin(ang)).normalized()
        p0 = Vector(c); p1 = p0 + dd * L * s * 0.5; p2 = p0 + dd * L * s
        blade(mb, [tuple(p0), tuple(p1 + nrm * 0.0008), tuple(p2)], [0.0025, 0.55 * L * s, 0.0], reg, nrm=tuple(nrm))


# ============================================================================================ courtyard pieces
def jar_tpl(H=0.040, seed=0):
    """a big storage jar (local, base at the origin)"""
    mb = MB()
    lathe(mb, [(0.0, 0.0), (0.0050, 0.0), (0.0110, H * 0.22), (0.0130, H * 0.48), (0.0110, H * 0.74), (0.0058, H * 0.88),
               (0.0062, H * 0.95), (0.0070, H), (0.0045, H * 0.99), (0.0, H * 0.94)], "jar", seg=12)
    for s in (-1, 1):
        tube(mb, [(s * 0.0060, H * 0.86, 0.0), (s * 0.0118, H * 0.84, 0.0), (s * 0.0115, H * 0.70, 0.0)], 0.0016,
             "jar", seg=5)
    return mb


def build_yard_pieces(court):
    """children of `courtyard`: `well` (round stone well with a windlass, rope and bucket) and `yard` (dry-stone walls
    on the west and the back with capstones, storage jars, a bench, a clay oven); packed side by side on the sheet"""
    rng = random.Random(23)
    dec = DECOR.setdefault("yard", [])
    # well
    wm = MB()
    x, z = WELL
    R, r, hw = WELL_R, WELL_R - 0.009, 0.042
    lathe(wm, [(r, hw - 0.004), (r, 0.020), (0.0, 0.020)], "water", C=(x, 0, z), seg=24, smooth=True)
    lathe(wm, [(R, 0.0), (R + 0.0012, hw * 0.5), (R, hw - 0.004), (R + 0.0025, hw - 0.0035), (R + 0.0025, hw),
               (r - 0.002, hw), (r - 0.002, hw - 0.004), (r, hw - 0.005)], "well", C=(x, 0, z), seg=24, smooth=False)
    for k in range(16):                                                   # stone joints (print only)
        a = TAU * (k + 0.5 * (k % 2)) / 16
        for (h0, h1, aa) in ((0.0, hw * 0.5, a), (hw * 0.5, hw - 0.004, a + TAU / 32)):
            p = (x + (R + 0.0015) * math.cos(aa), z + (R + 0.0015) * math.sin(aa))
            dec.append(((p[0], h0, p[1]), (p[0], h1, p[1])))
    for k in range(24):
        a0, a1 = TAU * k / 24, TAU * (k + 1) / 24
        dec.append(((x + (R + 0.0016) * math.cos(a0), hw * 0.5, z + (R + 0.0016) * math.sin(a0)),
                    (x + (R + 0.0016) * math.cos(a1), hw * 0.5, z + (R + 0.0016) * math.sin(a1))))
    for s in (-1, 1):                                                     # windlass posts, crossbar, rope, bucket
        px = x + s * (R - 0.002)
        box(wm, px - 0.0035, px + 0.0035, hw, 0.106, z - 0.0035, z + 0.0035, "wood", skip=("bottom",))
        box(wm, px - 0.0050, px + 0.0050, 0.106, 0.110, z - 0.0050, z + 0.0050, "wood", skip=("bottom",))
    tube(wm, [(x - R - 0.004, 0.098, z), (x + R + 0.004, 0.098, z)], 0.0036, "wood", seg=8)
    tube(wm, [(x + R + 0.004, 0.098, z), (x + R + 0.010, 0.098, z), (x + R + 0.010, 0.086, z)], 0.0016, "wood", seg=5)
    lathe(wm, [(0.0, 0.098 - 0.0058), (0.0058, 0.098 - 0.0058), (0.0058, 0.098 + 0.0058), (0.0, 0.098 + 0.0058)],
          "rope", C=(x - 0.010, 0, z), A=(1, 0, 0), U=(0, 1, 0), V=(0, 0, 1), seg=10)
    lathe(wm, [(0.0, -0.007), (0.0059, -0.007), (0.0059, 0.007), (0.0, 0.007)], "rope", C=(x - 0.003, 0.098, z),
          A=(1, 0, 0), U=(0, 1, 0), V=(0, 0, 1), seg=10)
    tube(wm, [(x - 0.003, 0.092, z + 0.003), (x - 0.006, 0.070, z + 0.012), (x - 0.006, 0.054, z + 0.022)], 0.0011,
         "rope", seg=4)
    bx_, bz_ = x + 0.006, z + R + 0.012                                     # bucket on the ground by the well
    lathe(wm, [(0.0, 0.0), (0.0075, 0.0), (0.0092, 0.016), (0.0080, 0.016), (0.0066, 0.002), (0.0, 0.002)], "wood",
          C=(bx_, 0, bz_), seg=12)
    tube(wm, [(bx_ - 0.009, 0.016, bz_), (bx_, 0.026, bz_), (bx_ + 0.009, 0.016, bz_)], 0.0010, "rope", seg=4)
    # west wall and back wall: a core with a capstone row
    walls = []
    for (wx0, wx1, wz0, wz1, H) in ((-0.556, -0.530, -0.388, 0.020, 0.028), (-0.203, -0.072, -0.390, -0.364, 0.030)):
        m = MB()
        box(m, wx0, wx1, 0.0, H, wz0, wz1, "wallStone", skip=("bottom",))
        along_z = (wz1 - wz0) > (wx1 - wx0)
        L = (wz1 - wz0) if along_z else (wx1 - wx0)
        n = int(L / 0.016)
        for k in range(n + 1):
            t = (k + 0.5) / (n + 1)
            cx = (wx0 + wx1) / 2 if along_z else wx0 + (wx1 - wx0) * t
            cz = wz0 + (wz1 - wz0) * t if along_z else (wz0 + wz1) / 2
            lumpy(m, (cx, H + 0.001, cz), 0.0095, "wallStone", seg=7, rings=4, sh=0.55,
                  sx=(1.25 if along_z else 0.95), sz=(0.95 if along_z else 1.25), amp=0.22, seed=k * 3.7 + wx0 * 10,
                  smooth=False)
        for row, hh in enumerate((0.010, 0.020)):                         # stone courses on the open faces
            if along_z:
                dec.append(((wx1 + 0.0003, hh, wz0), (wx1 + 0.0003, hh, wz1)))
                for zz in np.arange(wz0 + 0.008 * (row + 1), wz1, 0.018):
                    dec.append(((wx1 + 0.0003, hh - 0.010, zz), (wx1 + 0.0003, hh, zz + 0.002)))
            else:
                dec.append(((wx0, hh, wz1 + 0.0003), (wx1, hh, wz1 + 0.0003)))
                for xx in np.arange(wx0 + 0.008 * (row + 1), wx1, 0.018):
                    dec.append(((xx, hh - 0.010, wz1 + 0.0003), (xx + 0.002, hh, wz1 + 0.0003)))
        walls.append(m)
    # jars (one jar drawing, instanced)
    jt = jar_tpl()
    jm = MB()
    for (jx, jz, s, yaw) in ((-0.507, -0.372, 1.15, 0.2), (-0.486, -0.366, 0.95, 1.4), (-0.272, -0.368, 1.0, 2.2),
                             (-0.415, -0.008, 0.90, 0.6), (-0.510, -0.060, 1.05, 2.9)):
        jm.add(jt, yaw_fn(jx, jz, yaw, s))
    # bench and oven
    bm = MB()
    bx, bz = BENCH
    box(bm, bx - 0.036, bx + 0.036, 0.016, 0.021, bz - 0.011, bz + 0.011, "wood", skip=())
    for s in (-1, 1):
        box(bm, bx + s * 0.027 - 0.004, bx + s * 0.027 + 0.004, 0.0, 0.016, bz - 0.009, bz + 0.009, "wood",
            skip=("bottom",))
    om = MB()
    ox, oz = OVEN
    lathe(om, [(0.0, 0.0), (0.024, 0.0), (0.0235, 0.010), (0.019, 0.022), (0.011, 0.029), (0.004, 0.031),
               (0.004, 0.034), (0.0, 0.034)], "oven", C=(ox, 0, oz), seg=16)
    extrude(om, arch_poly(ox, 0.016, 0.006, 8), oz + 0.0236, oz + 0.0248, "windowDark", back=False,
            X=lambda a, b: (a, b))
    sp = DRAWINGS["yard"]
    pack([[walls[0], wm], [walls[1], jt, bm, om]], sp)
    # jars wear the jar drawing (the template's P)
    jm2 = MB()
    for (jx, jz, s, yaw) in ((-0.507, -0.372, 1.15, 0.2), (-0.486, -0.366, 0.95, 1.4), (-0.272, -0.368, 1.0, 2.2),
                             (-0.415, -0.008, 0.90, 0.6), (-0.510, -0.060, 1.05, 2.9)):
        jm2.add(jt, yaw_fn(jx, jz, yaw, s))
    well = make_obj("well", wm, court, origin=(x, 0.0, z), smooth_angle=45)
    yard = make_obj("yard", merge([walls[0], walls[1], jm2, bm, om]), court, origin=(-0.38, 0.0, -0.20),
                    smooth_angle=45)
    return well, yard


# ============================================================================================ fig tree
def build_fig(court):
    """`figTree`: a gnarled trunk splitting into three limbs, a broad crown of leaf masses with big lobed leaves (crown
    0.12-0.29 high), a few figs (named texel)"""
    mb = MB()
    x, z = FIG
    rng = random.Random(29)
    lathe(mb, [(0.0, 0.0), (0.020, 0.0), (0.013, 0.010), (0.0105, 0.030), (0.0095, 0.070), (0.0105, 0.088),
               (0.0, 0.090)], "figTrunk", C=(x, 0, z), seg=10, rfun=lambda th, i, k: 1.0 + 0.12 * math.cos(3 * th + i))
    limbs = [((x, 0.084, z), (x - 0.030, 0.130, z + 0.006), (x - 0.050, 0.165, z + 0.012)),
             ((x, 0.084, z), (x + 0.028, 0.128, z - 0.008), (x + 0.048, 0.168, z - 0.016)),
             ((x, 0.084, z), (x + 0.004, 0.140, z + 0.020), (x + 0.006, 0.190, z + 0.028))]
    for L in limbs:
        tube(mb, list(L), [0.0085, 0.0060, 0.0035], "figTrunk", seg=7)
    blobs = [(-0.048, 0.185, 0.010, 0.046), (0.046, 0.188, -0.014, 0.046), (0.004, 0.218, 0.024, 0.050),
             (-0.012, 0.240, -0.022, 0.046), (0.030, 0.232, 0.010, 0.040), (-0.040, 0.225, -0.008, 0.040),
             (0.010, 0.176, 0.032, 0.036), (0.000, 0.258, 0.000, 0.034)]
    for i, (dx, h, dz, r) in enumerate(blobs):
        lumpy(mb, (x + dx, h, z + dz), r, "figLeaf", seg=12, rings=7, sh=0.80, amp=0.16, seed=i * 2.3 + 1)
    cen = Vector((x, 0.215, z))
    for k in range(70):                                                   # big lobed leaves on the crown surface
        u = rng.uniform(-0.55, 0.95); a = rng.uniform(0, TAU)
        if k < 40:
            a = rng.uniform(math.pi * 0.15, math.pi * 0.85)              # more leaves on the front half
        dvec = Vector((math.cos(a) * math.sqrt(1 - u * u), u, math.sin(a) * math.sqrt(1 - u * u)))
        best = None
        for (dx, h, dz, r) in blobs:                                    # surface point of the outermost blob
            c = Vector((x + dx, h, z + dz))
            oc = cen - c
            bq = oc.dot(dvec); cq = oc.dot(oc) - (r * 0.98) ** 2
            disc = bq * bq - cq
            if disc >= 0:
                t = -bq + math.sqrt(disc)
                if best is None or t > best:
                    best = t
        if best is None:
            continue
        p = cen + dvec * best
        tang = dvec.cross(Vector((0, 1, 0)))
        if tang.length < 1e-3:
            tang = Vector((1, 0, 0))
        tang.normalize()
        d = (tang * math.cos(rng.uniform(0, TAU)) + Vector((0, -0.6, 0))).normalized()
        leaf(mb, tuple(p - dvec * 0.003), d, dvec, rng.uniform(0.020, 0.026), "figLeaf")
    mb.nr = True
    for k in range(10):
        u = rng.uniform(-0.6, 0.2); a = rng.uniform(0.1, math.pi - 0.1)
        dvec = Vector((math.cos(a) * math.sqrt(1 - u * u), u, math.sin(a) * math.sqrt(1 - u * u)))
        p = cen + dvec * 0.062
        lathe(mb, [(0.0, -0.0045), (0.0040, -0.0030), (0.0042, 0.0005), (0.0022, 0.0040), (0.0, 0.0048)], "fig",
              C=tuple(p), seg=8)
    mb.nr = False
    return make_obj("figTree", mb, court, origin=(x, 0.0, z), smooth_angle=55)


# ============================================================================================ tavern
def amphora_tpl():
    mb = MB()
    lathe(mb, [(0.0, 0.0), (0.0020, 0.002), (0.0050, 0.008), (0.0098, 0.020), (0.0105, 0.030), (0.0080, 0.040),
               (0.0040, 0.046), (0.0036, 0.054), (0.0048, 0.057), (0.0, 0.056)], "amphora", seg=12)
    for s in (-1, 1):
        tube(mb, [(s * 0.0038, 0.053, 0.0), (s * 0.0095, 0.054, 0.0), (s * 0.0085, 0.043, 0.0)], 0.0013,
             "amphora", seg=5)
    return mb


def column(mb, x, z, h0, H):
    """a fluted Doric column with base, echinus and abacus"""
    lathe(mb, [(0.0, h0), (0.0145, h0), (0.0145, h0 + 0.004), (0.0120, h0 + 0.007), (0.0, h0 + 0.007)], "column",
          C=(x, 0, z), seg=16)
    lathe(mb, [(0.0, h0 + 0.007), (0.0100, h0 + 0.007), (0.0098, h0 + 0.050), (0.0090, H - 0.012), (0.0, H - 0.011)],
          "column", C=(x, 0, z), seg=20, smooth=True, rfun=lambda th, i, k: 1.0 - (0.06 if k % 2 else 0.0))
    lathe(mb, [(0.0, H - 0.012), (0.0100, H - 0.012), (0.0135, H - 0.007), (0.0145, H - 0.005), (0.0, H - 0.005)],
          "column", C=(x, 0, z), seg=16)
    box(mb, x - 0.0155, x + 0.0155, H - 0.005, H, z - 0.0155, z + 0.0155, "column", skip=("bottom",))


def build_tavern(root):
    """the far-country tavern: a stoa on a marble platform (back wall with a painted band and a dark doorway, side
    walls, two fluted columns, an architrave), a striped awning with a scalloped valance on two front poles, bunting,
    two tables with cups and stools, amphorae, and a market stall with fruit under a yellow canopy. Parts are packed
    side by side in the tavern drawing (the awning would hide the tables)."""
    rng = random.Random(41)
    dec = DECOR.setdefault("tavern", [])
    x0, x1, zb, zf = TAVERN
    body = MB()
    box(body, x0, x1, 0.0, 0.010, zb, zf, "marble", skip=("bottom",))
    box(body, x0 + 0.010, x1 - 0.010, 0.0, 0.005, zf, zf + 0.010, "marble", skip=("bottom",))
    for xx in np.arange(x0 + 0.04, x1, 0.045):                              # platform slabs (print only)
        dec.append(((xx, 0.0102, zb + 0.016), (xx, 0.0102, zf)))
    hb = 0.200
    box(body, x0 + 0.004, x1 - 0.004, 0.010, hb, zb, zb + 0.014, "marble", skip=("bottom",))
    box(body, x0 + 0.004, x1 - 0.004, hb - 0.032, hb - 0.018, zb + 0.014, zb + 0.0155, "paint", skip=("back", "bottom"))
    for k, xx in enumerate(np.arange(x0 + 0.012, x1 - 0.012, 0.016)):     # meander on the band (print only)
        zz = zb + 0.0157
        dec.append(((xx, hb - 0.029, zz), (xx, hb - 0.021, zz))); dec.append(((xx, hb - 0.021, zz), (xx + 0.008, hb - 0.021, zz)))
    box(body, 0.372, 0.428, 0.010, 0.110, zb + 0.014, zb + 0.0152, "windowDark", skip=("back", "bottom"))
    box(body, 0.366, 0.434, 0.110, 0.118, zb + 0.014, zb + 0.018, "column", skip=("back", "bottom"))
    extrude(body, [(x0 + 0.004, hb), (x1 - 0.004, hb), (TAV_C[0], hb + 0.042)], zb, zb + 0.014, "marble")
    extrude(body, [(x0 + 0.030, hb + 0.004), (x1 - 0.030, hb + 0.004), (TAV_C[0], hb + 0.033)], zb + 0.014,
            zb + 0.0152, "paint", back=False)
    for sgn in (-1, 1):
        tube(body, [(TAV_C[0] + sgn * (x1 - x0) / 2 + sgn * 0.002, hb - 0.001, zb + 0.007),
                    (TAV_C[0], hb + 0.045, zb + 0.007)], 0.0042, "roofTile", seg=6)
        sphere(body, (TAV_C[0] + sgn * ((x1 - x0) / 2 - 0.002), hb + 0.006, zb + 0.007), 0.0060, "roofTile", seg=8,
               rings=5)
    sphere(body, (TAV_C[0], hb + 0.049, zb + 0.007), 0.0065, "roofTile", seg=8, rings=5)
    for xs in ((x0 + 0.004, x0 + 0.016), (x1 - 0.016, x1 - 0.004)):
        box(body, xs[0], xs[1], 0.010, COL_H + 0.020, zb + 0.014, COL_Z - 0.016, "marble", skip=("bottom",))
    for cx in COLS_X:
        column(body, cx, COL_Z, 0.010, COL_H)
    box(body, x0 + 0.002, x1 - 0.002, COL_H, COL_H + 0.020, COL_Z - 0.017, COL_Z + 0.017, "column", skip=())
    for xx in np.arange(x0 + 0.02, x1 - 0.01, 0.022):                     # triglyphs (print only)
        dec.append(((xx, COL_H + 0.004, COL_Z + 0.0172), (xx, COL_H + 0.016, COL_Z + 0.0172)))
    dec.append(((x0 + 0.002, COL_H + 0.010, COL_Z + 0.0172), (x1 - 0.002, COL_H + 0.010, COL_Z + 0.0172)))
    # awning: a striped slab from the back wall top down to the front edge, a scalloped valance, two poles
    aw = MB()
    ax0, ax1, azb, azf = AWN
    hbk, hfr = AWN_H
    NS = 8
    for i in range(NS):
        xa, xb_ = ax0 + (ax1 - ax0) * i / NS, ax0 + (ax1 - ax0) * (i + 1) / NS
        reg = "awning" if i % 2 == 0 else "awningB"
        sag = lambda x: 0.003 * math.sin(math.pi * ((x - ax0) / (ax1 - ax0) * NS % 1.0))
        q = [(xa, hbk, azb), (xb_, hbk, azb), (xb_, hfr - sag(xb_), azf), (xa, hfr - sag(xa), azf)]
        mid = ((xa + xb_) / 2, (hbk + hfr) / 2 - 0.004, (azb + azf) / 2)
        top = [aw.v(*p) for p in q]; c = aw.v(*mid)
        for k in range(4):
            aw.fo([top[k], top[(k + 1) % 4], c], reg, (0, 1, 0.3))
        bot = [aw.v(p[0], p[1] - 0.0025, p[2]) for p in q]; c2 = aw.v(mid[0], mid[1] - 0.0025, mid[2])
        for k in range(4):
            aw.fo([bot[k], bot[(k + 1) % 4], c2], reg, (0, -1, -0.3))
        aw.fo([top[2], top[3], bot[3], bot[2]], reg, (0, 0, 1))
        # valance tongue hanging from the front edge
        tongue = [(xa, hfr), (xb_, hfr)] + [((xa + xb_) / 2 + (xb_ - xa) / 2 * math.cos(math.pi * k / 6),
                                             hfr - 0.012 - 0.008 * math.sin(math.pi * k / 6)) for k in range(7)]
        tongue = [tongue[0], tongue[1]] + tongue[2:]
        extrude(aw, [(p[0], p[1]) for p in tongue], azf - 0.0012, azf + 0.0004, reg)
    for px in (ax0 + 0.004, ax1 - 0.004):
        tube(aw, [(px, 0.0, azf - 0.001), (px, hfr + 0.006, azf - 0.001)], 0.0026, "pole", seg=6)
        sphere(aw, (px, hfr + 0.008, azf - 0.001), 0.0042, "pole", seg=8, rings=5)
    # tables, cups, stools
    tm = MB()
    for (tx, tz) in ((0.338, -0.468), (0.462, -0.474)):
        lathe(tm, [(0.0, 0.010), (0.0060, 0.010), (0.0030, 0.012), (0.0028, 0.034), (0.0230, 0.034), (0.0235, 0.038),
                   (0.0, 0.038)], "table", C=(tx, 0, tz), seg=18)
        for k in range(3):
            a = TAU * k / 3 + 0.4
            cx_, cz_ = tx + 0.012 * math.cos(a), tz + 0.012 * math.sin(a)
            lathe(tm, [(0.0, 0.038), (0.0030, 0.038), (0.0022, 0.041), (0.0040, 0.048), (0.0, 0.047)], "cup",
                  C=(cx_, 0, cz_), seg=8)
        for k in range(3):
            a = TAU * k / 3 + 1.2
            sx, sz = tx + 0.036 * math.cos(a), tz + 0.030 * math.sin(a)
            lathe(tm, [(0.0, 0.010), (0.0080, 0.010), (0.0075, 0.022), (0.0090, 0.022), (0.0090, 0.026), (0.0, 0.026)],
                  "stool", C=(sx, 0, sz), seg=10)
    amp = amphora_tpl()
    am = MB()
    for (ax, az, yaw, lean) in ((0.285, -0.505, 0.3, 0.0), (0.302, -0.512, 1.9, 0.0), (0.518, -0.506, 0.9, 0.0),
                                (0.500, -0.512, 2.6, -0.12)):
        am.add(amp, yaw_fn(ax, az, yaw, 1.0, lean=(lean, 0.0), h0=0.010))
    # market stall: a crate counter with fruit under a canopy on four poles
    st = MB()
    sx, sz = STALL
    box(st, sx - 0.034, sx + 0.034, 0.0, 0.028, sz - 0.018, sz + 0.016, "crate", skip=("bottom",))
    for xx in np.arange(sx - 0.034 + 0.011, sx + 0.034, 0.011):
        DECOR["tavern"].append(((xx, 0.002, sz + 0.0163), (xx, 0.026, sz + 0.0163)))
    for k in range(9):
        fx_ = sx - 0.026 + 0.0065 * k + rng.uniform(-0.001, 0.001)
        for j in range(2):
            sphere(st, (fx_, 0.0325 + 0.002 * j, sz - 0.006 + 0.010 * j), 0.0042, "fruit", seg=7, rings=4)
    for k in range(3):
        lumpy(st, (sx + 0.014 * (k - 1), 0.036, sz - 0.012), 0.0068, "melon", seg=9, rings=5, sh=0.85, amp=0.05, seed=k)
    for (px, pz) in ((sx - 0.036, sz - 0.020), (sx + 0.036, sz - 0.020), (sx - 0.036, sz + 0.018), (sx + 0.036, sz + 0.018)):
        tube(st, [(px, 0.0, pz), (px, 0.094 if pz < sz else 0.082, pz)], 0.0020, "pole", seg=5)
    for i in range(4):                                                    # striped canopy, sloping to the front
        xa, xb_ = sx - 0.040 + 0.020 * i, sx - 0.020 + 0.020 * i
        reg = "stallCloth" if i % 2 == 0 else "awningB"
        q = [(xa, 0.094, sz - 0.024), (xb_, 0.094, sz - 0.024), (xb_, 0.080, sz + 0.024), (xa, 0.080, sz + 0.024)]
        top = [st.v(*p) for p in q]; bot = [st.v(p[0], p[1] - 0.002, p[2]) for p in q]
        st.fo(top, reg, (0, 1, 0.3)); st.fo(bot, reg, (0, -1, -0.3))
        st.fo([top[2], top[3], bot[3], bot[2]], reg, (0, 0, 1))
        extrude(st, [(xa, 0.080), (xb_, 0.080), ((xa + xb_) / 2, 0.071)], sz + 0.0235, sz + 0.0245, reg)
    tube(aw, [(0.232, 0.0, -0.300), (0.232, 0.152, -0.300)], 0.0022, "pole", seg=6)        # bunting mast
    sphere(aw, (0.232, 0.154, -0.300), 0.0036, "pole", seg=8, rings=5)
    sp = DRAWINGS["tavern"]
    pack([[st, tm, amp], [body, aw]], sp)
    amp2 = MB()
    for (ax, az, yaw, lean) in ((0.285, -0.505, 0.3, 0.0), (0.302, -0.512, 1.9, 0.0), (0.518, -0.506, 0.9, 0.0),
                                (0.500, -0.512, 2.6, -0.12)):
        amp2.add(amp, yaw_fn(ax, az, yaw, 1.0, lean=(lean, 0.0), h0=0.010))
    # bunting (named texels): from the left awning pole to the mast, from the right pole to the stall canopy (the
    # awning's front edge stays clear for the party lights)
    bun = MB()
    bun.nr = True
    regs = ["flagA", "flagB", "flagC", "flagD"]
    lines = [((ax0 + 0.004, hfr + 0.006, azf + 0.002), (0.232, 0.150, -0.300), 0.012, 4),
             ((ax1 - 0.004, hfr + 0.002, azf + 0.002), (sx - 0.036, 0.092, sz - 0.020), 0.018, 4)]
    fl = 0
    for (pa, pb, sagd, nflag) in lines:
        pa, pb = Vector(pa), Vector(pb)
        pts = [pa + (pb - pa) * t + Vector((0, -sagd * 4 * t * (1 - t), 0)) for t in np.linspace(0, 1, 13)]
        tube(bun, [tuple(p) for p in pts], 0.0007, "cord", seg=3, caps=False)
        for k in range(nflag):
            t = (k + 0.5) / nflag
            p = pa + (pb - pa) * t + Vector((0, -sagd * 4 * t * (1 - t), 0))
            dirv = (pb - pa).normalized()
            w = 0.0075
            a_, b_ = p - dirv * w, p + dirv * w
            tip = p + Vector((0, -0.016, 0)) + Vector((0, 0, 0.002))
            for sgn in (1, -1):
                bun.fo([bun.v(*a_), bun.v(*b_), bun.v(*tip)], regs[fl % 4], (0, 0, sgn))
            fl += 1
    bun.nr = False
    tav = make_obj("tavern", merge([body, aw, tm, amp2, st, bun]), root, origin=(TAV_C[0], 0.0, TAV_C[1]),
                   smooth_angle=45, bevel=0.0005, bevel_angle=60)
    return tav


# ============================================================================================ pig pen
def build_pen(root):
    """`pigpen`: a rough wooden fence (posts and two rails) round x 0.26-0.56, z -0.06-0.18 with the north and west
    gaps (and the north-west corner left open where the son's walks pass), mud puddles, a trough, a straw heap; child
    `pods` (carob pods piled on the trough)"""
    rng = random.Random(47)
    x0, x1, z0, z1 = PEN
    fm = MB()
    corners = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    gaps = [lambda x, z: abs(z - z0) < 1e-6 and 0.29 < x < 0.40, lambda x, z: abs(x - x0) < 1e-6 and 0.05 < z < 0.16]
    posts = []
    for i in range(4):
        (ax, az), (bx, bz) = corners[i], corners[(i + 1) % 4]
        L = math.hypot(bx - ax, bz - az); n = max(1, int(round(L / 0.036)))
        for k in range(n):
            t = k / n
            posts.append((ax + (bx - ax) * t, az + (bz - az) * t))
    keep = []
    for (px, pz) in posts:
        ok = clear_dist(px, pz) > 0.058 and not any(g(px, pz) for g in gaps)
        keep.append(ok)
    for gx, gz in ((0.40, z0), (x0, 0.045), (x0, 0.165)):                 # gate posts
        if clear_dist(gx, gz) > 0.058:
            posts.append((gx, gz)); keep.append(True)
    P = len(posts)
    perim = posts[:P - 3] if P > 3 else posts
    for i, (px, pz) in enumerate(posts):
        if not keep[i]:
            continue
        H = 0.054 + rng.uniform(-0.004, 0.004)
        lathe(fm, [(0.0, 0.0), (0.0048, 0.0), (0.0046, H - 0.006), (0.0030, H - 0.002), (0.0, H)], "fence",
              C=(px + rng.uniform(-0.001, 0.001), 0, pz + rng.uniform(-0.001, 0.001)), seg=6, smooth=False,
              rfun=lambda th, j, k: 1.0 + 0.08 * nz(j, k))
    n0 = len(perim)
    for i in range(n0):
        j = (i + 1) % n0
        if not (keep[i] and keep[j]):
            continue
        (ax, az), (bx, bz) = perim[i], perim[j]
        if any(g((ax + bx) / 2, (az + bz) / 2) for g in gaps):
            continue
        for hh in (0.020, 0.040):
            d = Vector((bx - ax, 0, bz - az)).normalized(); s = Vector((-d.z, 0, d.x))
            pa = Vector((ax, hh + rng.uniform(-0.002, 0.002), az)); pb = Vector((bx, hh + rng.uniform(-0.002, 0.002), bz))
            q = [pa - s * 0.0022, pb - s * 0.0022, pb + s * 0.0022, pa + s * 0.0022]
            top = [fm.v(*(p + Vector((0, 0.0040, 0)))) for p in q]; bot = [fm.v(*(p - Vector((0, 0.0040, 0)))) for p in q]
            fm.fo(top, "fence", UP); fm.fo(bot, "fence", (0, -1, 0))
            for k in range(4):
                k1 = (k + 1) % 4
                o = (q[k] + q[k1]) / 2 - (pa + pb) / 2
                fm.fo([top[k], top[k1], bot[k1], bot[k]], "fence", tuple(o))
    # gate rails on the west gap's posts: none (open). Mud puddles, a straw heap, the trough
    mm = MB()
    for i, (cx, cz, r) in enumerate(((0.320, 0.106, 0.036), (0.452, -0.020, 0.032), (0.402, 0.150, 0.020),
                                     (0.505, 0.150, 0.022), (0.380, 0.040, 0.016))):
        poly = blob_poly(cx, cz, r, 11 + i, n=18, amp=0.18)
        flat(mm, poly, 0.0034, "mud")
        for k in range(3):                                             # ripples (print only)
            a = rng.uniform(0, TAU); rr = r * rng.uniform(0.25, 0.55)
            DECOR.setdefault("pen", []).append(((cx + rr * math.cos(a), 0.0035, cz + rr * math.sin(a) * 0.8),
                                                (cx + rr * math.cos(a) + 0.008, 0.0035, cz + rr * math.sin(a) * 0.8)))
    sm = MB()
    lathe(sm, [(0.0, 0.0), (0.024, 0.0), (0.020, 0.006), (0.010, 0.012), (0.0, 0.014)], "straw", C=(0.535, 0, 0.158),
          seg=12, rfun=lambda th, i, k: 1.0 + (0.18 * (nz(i, k, 3) - 0.5) if 0 < i < 4 else 0.0))
    for k in range(12):
        a = rng.uniform(0, TAU); rr = rng.uniform(0.008, 0.024)
        p0 = (0.535 + rr * math.cos(a), 0.012 * (1 - rr / 0.026) + 0.002, 0.158 + rr * math.sin(a))
        b = rng.uniform(0, TAU)
        tube(sm, [p0, (p0[0] + 0.010 * math.cos(b), p0[1] + 0.001, p0[2] + 0.010 * math.sin(b))], 0.0007, "straw", seg=3,
             caps=False)
    tr = MB()
    tx, tz = TROUGH
    w, d, h = 0.0375, 0.014, 0.019
    box(tr, tx - w, tx + w, 0.0, h, tz - d, tz + d, "trough", skip=("top",))
    for (a0, a1, c0, c1) in ((tx - w, tx + w, tz - d, tz - d + 0.003), (tx - w, tx + w, tz + d - 0.003, tz + d),
                             (tx - w, tx - w + 0.003, tz - d, tz + d), (tx + w - 0.003, tx + w, tz - d, tz + d)):
        ngon_top(tr, [(a0, c0), (a1, c0), (a1, c1), (a0, c1)], h, "trough")
    for (a0, a1, c0, c1, hh, o) in ((tx - w + 0.003, tx + w - 0.003, tz - d + 0.003, tz - d + 0.003, 1, (0, 0, 1)),
                                     (tx - w + 0.003, tx + w - 0.003, tz + d - 0.003, tz + d - 0.003, 1, (0, 0, -1))):
        tr.fo([tr.v(a0, h, c0), tr.v(a1, h, c0), tr.v(a1, 0.006, c0), tr.v(a0, 0.006, c0)], "trough", o)
    for (a0, c0, c1, o) in ((tx - w + 0.003, tz - d + 0.003, tz + d - 0.003, (1, 0, 0)),
                            (tx + w - 0.003, tz - d + 0.003, tz + d - 0.003, (-1, 0, 0))):
        tr.fo([tr.v(a0, h, c0), tr.v(a0, h, c1), tr.v(a0, 0.006, c1), tr.v(a0, 0.006, c0)], "trough", o)
    ngon_top(tr, [(tx - w + 0.003, tz - d + 0.003), (tx + w - 0.003, tz - d + 0.003), (tx + w - 0.003, tz + d - 0.003),
                  (tx - w + 0.003, tz + d - 0.003)], 0.006, "trough")
    for s in (-1, 1):
        box(tr, tx + s * (w - 0.004) - 0.004, tx + s * (w - 0.004) + 0.004, 0.0, 0.004, tz - d - 0.004, tz + d + 0.004,
            "trough", skip=("bottom",))
    # pods: curved flat carob pods heaped in the trough and spilling over its front
    pm = MB()
    for k in range(13):
        if k < 9:
            cx, ch, cz = tx + rng.uniform(-0.026, 0.026), 0.009 + 0.004 * (k % 3), tz + rng.uniform(-0.006, 0.006)
        else:
            cx, ch, cz = tx + rng.uniform(-0.03, 0.03), 0.004 + 0.012 * (k == 9), tz + d + rng.uniform(0.003, 0.012)
        yaw = rng.uniform(0, TAU); L = rng.uniform(0.020, 0.026)
        pts = []
        for u in np.linspace(-1, 1, 7):
            px_ = u * L / 2; pz_ = 0.004 * (1 - u * u) * (1 if k % 2 else -1)
            pts.append((cx + px_ * math.cos(yaw) - pz_ * math.sin(yaw), ch + 0.0012 * (1 - u * u),
                        cz + px_ * math.sin(yaw) + pz_ * math.cos(yaw)))
        tube(pm, pts, [0.0012, 0.0024, 0.0028, 0.0029, 0.0028, 0.0024, 0.0012], "pod", seg=5, ref=(0, 1, 0))
    lumpy(pm, (tx, 0.0075, tz), 0.030, "pods", seg=14, rings=6, sh=0.30, sz=0.42, amp=0.18, seed=5)
    sp = DRAWINGS["pen"]
    pack([[fm, tr, sm], [mm, pm]], sp)
    pen = make_obj("pigpen", merge([fm, mm, sm, tr]), root, origin=(0.41, 0.0, 0.06), smooth_angle=40)
    pods = make_obj("pods", pm, pen, origin=(tx, 0.0, tz), smooth_angle=60)
    return pen, pods, sum(keep)


# ============================================================================================ pigs (skinned, looping)
def pig_tpl():
    """one round pig (local, base at the origin, facing +x): a barrel body, a round head, a snout disc with nostrils,
    floppy ears, four short legs with trotters, a curly tail; eyes and nostrils are named texels"""
    mb = MB()
    lathe(mb, [(0.0, -0.0300), (0.0085, -0.0285), (0.0140, -0.0235), (0.0172, -0.0140), (0.0182, -0.0030),
               (0.0178, 0.0070), (0.0160, 0.0150), (0.0125, 0.0215), (0.0, 0.0250)], "pig", C=(0, 0.0255, 0),
          A=(1, 0, 0), U=(0, 1, 0), V=(0, 0, 1), seg=14, sv=0.92)
    sphere(mb, (0.0260, 0.0300, 0.0), 0.0138, "pig", seg=12, rings=8)
    lathe(mb, [(0.0, 0.0), (0.0078, 0.0), (0.0081, 0.0090), (0.0070, 0.0115), (0.0, 0.0120)], "snout",
          C=(0.0345, 0.0272, 0.0), A=(1, 0, 0), U=(0, 1, 0), V=(0, 0, 1), seg=12)
    for s in (-1, 1):
        blade(mb, [(0.0235, 0.0405, s * 0.0062), (0.0290, 0.0455, s * 0.0102), (0.0345, 0.0400, s * 0.0130)],
              [0.0100, 0.0085, 0.0], "pig", nrm=(0.3, 0.6, s * 0.75))
        for (lx, lz) in ((0.0145, s * 0.0090), (-0.0150, s * 0.0090)):
            tube(mb, [(lx, 0.0150, lz), (lx, 0.0040, lz)], [0.0050, 0.0044], "pig", seg=8, caps=False)
            lathe(mb, [(0.0, 0.0), (0.0046, 0.0), (0.0046, 0.0042), (0.0, 0.0044)], "pig", C=(lx, 0, lz), seg=8)
    tail = []
    for k in range(10):
        t = k / 9
        tail.append((-0.0290 - 0.0040 * t + 0.0026 * math.cos(TAU * 1.3 * t) * t, 0.0320 + 0.0060 * t +
                     0.0026 * math.sin(TAU * 1.3 * t) * t, 0.0))
    tube(mb, tail, [0.0015] * 9 + [0.0009], "pig", seg=5)
    mb.nr = True
    for s in (-1, 1):
        sphere(mb, (0.0335, 0.0345, s * 0.0068), 0.0018, "eye", seg=6, rings=4)
        sphere(mb, (0.0463, 0.0280, s * 0.0026), 0.0014, "eye", seg=5, rings=3)
    mb.nr = False
    return mb


def pig_weights(kind, i):
    """vertex -> bone weights from the template position"""
    def w(lv, wv):
        x, h, z = lv
        out = {}
        head = min(1.0, max(0.0, (x - 0.011) / 0.008))
        tail = 1.0 if x < -0.0285 and h > 0.024 else 0.0
        leg = min(1.0, max(0.0, (0.0150 - h) / 0.0070)) if abs(x) < 0.022 and abs(abs(x) - 0.0148) < 0.008 else 0.0
        if leg > 0 and kind == "trot":
            nm = "pig%d_leg%s%s" % (i, "F" if x > 0 else "B", "L" if z < 0 else "R")
            out[nm] = leg
            out["pig%d" % i] = 1.0 - leg
            return out
        if tail:
            return {"pig%d_tail" % i: 1.0}
        if head > 0:
            out["pig%d_head" % i] = head
        out["pig%d" % i] = 1.0 - head
        return out
    return w


def build_pigs(root):
    """armature `pigs` (bone per pig + head, tail, trotter legs) -> mesh `pigBodies`; action `pigsWiggle` (4 s loop at
    24 fps, frame 1 == frame 97): snouts rooting, tails twitching, one pig trotting a little circle"""
    tpl = pig_tpl()
    mb = MB()
    frames = []
    for i, (kind, x, z, yaw) in enumerate(PIG_SPOTS, 1):
        s = 1.0 if kind != "trot" else 0.92
        f = yaw_fn(x, z, math.radians(yaw), s)
        mb.add(tpl, f, weight=pig_weights(kind, i))
        frames.append((kind, x, z, math.radians(yaw), s))
    mb.P = list(mb.P)
    arm = bpy.data.armatures.new("pigs_arm")
    rig = link(bpy.data.objects.new("pigs", arm))
    cx, cz = 0.49, 0.06
    rig.location = B(cx, 0.0, cz)
    parent_keep(rig, root)
    bpy.context.view_layer.objects.active = rig
    bpy.ops.object.mode_set(mode='EDIT')
    O = B(cx, 0, cz)
    r0 = arm.edit_bones.new("pigs_root"); r0.head = B(cx, 0, cz) - O; r0.tail = B(cx, 0.02, cz) - O
    for i, (kind, x, z, yaw, s) in enumerate(frames, 1):
        f = yaw_fn(x, z, yaw, s)
        b = arm.edit_bones.new("pig%d" % i); b.head = B(x, 0, z) - O; b.tail = B(x, 0.02, z) - O; b.parent = r0
        for nm, lp in (("head", (0.0150, 0.0280, 0.0)), ("tail", (-0.0285, 0.0320, 0.0))):
            p = f(lp)
            bb = arm.edit_bones.new("pig%d_%s" % (i, nm)); bb.head = B(*p) - O; bb.tail = B(p[0], p[1] + 0.012, p[2]) - O
            bb.parent = b
        if kind == "trot":
            for nm, lp in (("FL", (0.0145, 0.0150, -0.0090)), ("FR", (0.0145, 0.0150, 0.0090)),
                           ("BL", (-0.0150, 0.0150, -0.0090)), ("BR", (-0.0150, 0.0150, 0.0090))):
                p = f(lp)
                bb = arm.edit_bones.new("pig%d_leg%s" % (i, nm)); bb.head = B(*p) - O
                bb.tail = B(p[0], p[1] + 0.010, p[2]) - O; bb.parent = b
    for b in arm.edit_bones:
        b.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')
    ob = make_obj("pigBodies", mb, None, origin=(cx, 0.0, cz), smooth_angle=70)
    parent_keep(ob, rig)
    mod = ob.modifiers.new("Armature", 'ARMATURE'); mod.object = rig
    bpy.context.scene.render.fps = 24
    rig.animation_data_create()
    Zb = Vector((0, 0, 1))
    for i, (kind, x, z, yaw, s) in enumerate(frames, 1):
        fwd = Vector((math.cos(yaw), -math.sin(yaw), 0.0))           # Blender: design (cos, sin) in (x, z) -> (x, -z)
        lat = Vector((-math.sin(yaw), -math.cos(yaw), 0.0))
        ph = 1.3 * i
        bones = {nm: rig.pose.bones[nm] for nm in [b.name for b in arm.bones if b.name.startswith("pig%d" % i)]}
        inv = {nm: arm.bones[nm].matrix_local.to_3x3().inverted() for nm in bones}
        for pb in bones.values():
            pb.rotation_mode = 'QUATERNION'
        for fr in range(1, 98, 2):
            u = TAU * (fr - 1) / 96
            body = bones["pig%d" % i]; head = bones["pig%d_head" % i]; tail = bones["pig%d_tail" % i]
            ib, ih, it = inv[body.name], inv[head.name], inv[tail.name]
            if kind == "trot":
                a0 = math.pi
                d0 = Vector((TROT_C[0] + TROT_R * math.cos(a0), 0, TROT_C[1] + TROT_R * math.sin(a0)))
                a = a0 - u                                                  # clockwise seen from above
                d1 = Vector((TROT_C[0] + TROT_R * math.cos(a), 0, TROT_C[1] + TROT_R * math.sin(a)))
                dd = B(*(d1 - d0))
                bob = 0.0012 * (1 - math.cos(8 * u)) / 2
                body.location = ib @ (dd + Vector((0, 0, bob)))
                body.rotation_quaternion = Quaternion((ib @ Zb).normalized(), u) @ \
                    Quaternion((ib @ fwd).normalized(), math.radians(2.0 * math.sin(8 * u)))
                head.rotation_quaternion = Quaternion((ih @ lat).normalized(), math.radians(-5.0 * math.sin(8 * u + 0.6)))
                tail.rotation_quaternion = Quaternion((it @ fwd).normalized(), math.radians(40 * math.sin(10 * u)))
                for nm, phs in (("FL", 0.0), ("BR", 0.0), ("FR", math.pi), ("BL", math.pi)):
                    lb = bones["pig%d_leg%s" % (i, nm)]
                    lb.rotation_quaternion = Quaternion((inv[lb.name] @ lat).normalized(),
                                                        math.radians(30 * math.sin(8 * u + phs)))
            else:
                deep = 1.6 if kind == "wallow" else 1.0
                nod = -(10.0 + 9.0 * math.sin(2 * u + ph)) * deep - 2.5 * math.sin(8 * u + ph)
                turn = 7.0 * math.sin(u + ph)
                head.rotation_quaternion = Quaternion((ih @ Zb).normalized(), math.radians(turn)) @ \
                    Quaternion((ih @ lat).normalized(), math.radians(nod))
                tail.rotation_quaternion = Quaternion((it @ fwd).normalized(),
                                                      math.radians(35 * math.sin(6 * u + ph) + 10 * math.sin(14 * u)))
                body.rotation_quaternion = Quaternion((ib @ fwd).normalized(), math.radians(2.5 * math.sin(4 * u + ph))) @ \
                    Quaternion((ib @ Zb).normalized(), math.radians((6.0 if kind == "wallow" else 3.0) * math.sin(2 * u + ph)))
                body.location = ib @ Vector((0, 0, 0.0006 * (1 - math.cos(4 * u + ph)) / 2 - 0.0006 * (1 - math.cos(ph)) / 2))
            for pb in bones.values():
                pb.keyframe_insert("rotation_quaternion", frame=fr)
                if pb.name == "pig%d" % i:
                    pb.keyframe_insert("location", frame=fr)
    act = rig.animation_data.action
    act.name = "pigsWiggle"
    bpy.context.scene.frame_set(1)
    return rig, ob, tpl


# ============================================================================================ feast and lamps (hidden)
def lantern_tpl():
    """a hanging lantern (local: the hook at the origin, hanging down): a cap, a glass body in a frame, a base"""
    mb = MB()
    lathe(mb, [(0.0, -0.0020), (0.0020, -0.0020), (0.0060, -0.0060), (0.0062, -0.0068), (0.0, -0.0068)], "lantern",
          seg=8)
    lathe(mb, [(0.0, -0.0068), (0.0050, -0.0068), (0.0058, -0.0120), (0.0050, -0.0180), (0.0, -0.0180)], "lampGlass",
          seg=8, smooth=True)
    for k in range(4):
        a = TAU * k / 4 + TAU / 8
        tube(mb, [(0.0060 * math.cos(a), -0.0068, 0.0060 * math.sin(a)), (0.0064 * math.cos(a), -0.0122, 0.0064 * math.sin(a)),
                  (0.0055 * math.cos(a), -0.0182, 0.0055 * math.sin(a))], 0.0007, "lantern", seg=3)
    lathe(mb, [(0.0, -0.0180), (0.0058, -0.0180), (0.0050, -0.0210), (0.0, -0.0215)], "lantern", seg=8)
    tube(mb, [(0.0, 0.0, 0.0), (0.0, -0.0022, 0.0)], 0.0008, "lantern", seg=3)
    return mb


def oil_lamp(mb, x, h, z, yaw):
    """a clay slipper lamp with a nozzle and a handle; returns the flame point"""
    c, s = math.cos(yaw), math.sin(yaw)
    lathe(mb, [(0.0, h), (0.0040, h), (0.0058, h + 0.0030), (0.0050, h + 0.0048), (0.0016, h + 0.0056), (0.0, h + 0.0056)],
          "lamp", C=(x, 0, z), seg=10, sx=1.0, sv=0.85)
    tube(mb, [(x, h + 0.0030, z), (x + 0.0085 * c, h + 0.0040, z + 0.0085 * s)], [0.0028, 0.0019], "lamp", seg=6)
    tube(mb, [(x - 0.0052 * c, h + 0.0035, z - 0.0052 * s), (x - 0.0085 * c, h + 0.0050, z - 0.0085 * s)], 0.0012, "lamp",
         seg=4)
    return (x + 0.0092 * c, h + 0.0062, z + 0.0092 * s)


def build_feast(root):
    """`feast`: a long low table under the fig tree (centre (-0.42, -0.215), 0.18 x 0.065, top 0.034) with a white
    runner, bread, a big dish of stew, a bowl of grapes, figs, cups and a jug; cushions round it. `lamps`: three oil
    lamps on the table, two lanterns hanging from the pergola by the door and three on a cord to the fig tree; empties
    `lampsFlame`, `lampsFlame2`..`lampsFlame8` at the flames. Both hidden at the start (S11 shows them)."""
    rng = random.Random(53)
    tx, tz = TABLE_C
    W, Dp, Ht = TABLE_W, TABLE_D, TABLE_H
    tb = MB()
    box(tb, tx - W / 2, tx + W / 2, Ht - 0.010, Ht, tz - Dp / 2, tz + Dp / 2, "tableWood", skip=())
    for sx in (-1, 1):
        for sz in (-1, 1):
            box(tb, tx + sx * (W / 2 - 0.012) - 0.0045, tx + sx * (W / 2 - 0.012) + 0.0045, 0.0, Ht - 0.006,
                tz + sz * (Dp / 2 - 0.009) - 0.0045, tz + sz * (Dp / 2 - 0.009) + 0.0045, "tableLeg", skip=("bottom",))
    box(tb, tx - W / 2 + 0.010, tx + W / 2 - 0.010, Ht, Ht + 0.0012, tz - 0.019, tz + 0.019, "cloth", skip=("bottom",))
    h = Ht + 0.0012
    for (bx, bz) in ((tx - 0.072, tz - 0.010), (tx + 0.050, tz - 0.013)):
        lumpy(tb, (bx, h + 0.004, bz), 0.0110, "bread", seg=10, rings=5, sh=0.45, sx=1.25, amp=0.06, seed=bx * 100)
    lathe(tb, [(0.0, h), (0.0120, h), (0.0185, h + 0.0040), (0.0175, h + 0.0048), (0.0, h + 0.0030)], "dish",
          C=(tx, 0, tz - 0.004), seg=18)
    lumpy(tb, (tx, h + 0.0045, tz - 0.004), 0.0125, "food", seg=12, rings=5, sh=0.42, amp=0.14, seed=7)
    gx, gz = tx - 0.036, tz - 0.012
    lathe(tb, [(0.0, h), (0.0050, h), (0.0105, h + 0.0060), (0.0100, h + 0.0066), (0.0, h + 0.0040)], "dish",
          C=(gx, 0, gz), seg=14)
    for k in range(11):
        a = TAU * k / 7; rr = 0.0045 if k < 7 else 0.0018
        sphere(tb, (gx + rr * math.cos(a), h + 0.0078 + (0.0030 if k >= 7 else 0.0), gz + rr * math.sin(a)), 0.0030,
               "grapes", seg=6, rings=4)
    for k in range(4):
        sphere(tb, (tx + 0.026 + 0.007 * k, h + 0.0035, tz + 0.012 - 0.003 * (k % 2)), 0.0038, "grapes", seg=7, rings=4,
               sh=1.15)
    for k, cxp in enumerate((-0.080, -0.044, 0.018, 0.072)):              # cups along the back half
        lathe(tb, [(0.0, h), (0.0038, h), (0.0014, h + 0.0030), (0.0012, h + 0.0060), (0.0045, h + 0.0085),
                   (0.0048, h + 0.0130), (0.0, h + 0.0120)], "cup", C=(tx + cxp, 0, tz - 0.022), seg=10)
    lathe(tb, [(0.0, h), (0.0055, h), (0.0080, h + 0.0080), (0.0060, h + 0.0150), (0.0034, h + 0.0190),
               (0.0045, h + 0.0220), (0.0, h + 0.0210)], "dish", C=(tx + 0.080, 0, tz - 0.020), seg=12)
    cm = MB()
    for k, (cxp, czp) in enumerate(((-0.066, 0.052), (-0.010, 0.054), (0.046, 0.052), (-0.040, -0.054), (0.026, -0.054))):
        lumpy(cm, (tx + cxp, 0.0045, tz + czp), 0.0175, "cushion" if k % 2 == 0 else "cushionB", seg=12, rings=5, sh=0.28,
              sx=1.25, amp=0.05, seed=k + 70)
    # lamps
    lm = MB()
    flames = []
    for k, (lx, lz, yw) in enumerate(((tx - 0.052, tz + 0.020, 0.3), (tx + 0.014, tz + 0.022, -0.2),
                                      (tx + 0.062, tz + 0.018, 0.5))):
        flames.append(oil_lamp(lm, lx, h, lz, yw))
    lt = lantern_tpl()
    hangs = []
    for px in (-0.379, -0.281):                                            # from the pergola rafters by the door
        hangs.append((px, 0.110, -0.364))
    cord_a, cord_b = Vector((-0.270, 0.124, -0.354)), Vector((-0.452, 0.150, -0.252))
    cpts = [cord_a + (cord_b - cord_a) * t + Vector((0, -0.020 * 4 * t * (1 - t), 0)) for t in np.linspace(0, 1, 13)]
    for t in (0.25, 0.5, 0.75):
        p = cord_a + (cord_b - cord_a) * t + Vector((0, -0.020 * 4 * t * (1 - t), 0))
        hangs.append((p.x, p.y, p.z))
    lan = MB()
    for (hx, hh, hz) in hangs:
        lan.add(lt, lambda q, hx=hx, hh=hh, hz=hz: (q[0] + hx, q[1] + hh, q[2] + hz))
        flames.append((hx, hh - 0.0125, hz))
    lan.nr = True
    tube(lan, [tuple(p) for p in cpts], 0.0007, "cord", seg=3, caps=False)
    for (hx, hh, hz) in hangs[:2]:
        tube(lan, [(hx, hh + 0.010, hz), (hx, hh, hz)], 0.0006, "cord", seg=3, caps=False)
    lan.nr = False
    sp = DRAWINGS["feast"]
    pack([[tb], [cm]], sp)
    # the table lamps keep the lamp drawing; the lanterns wear the one lantern drawing (template P)
    lan2 = MB()
    for (hx, hh, hz) in hangs:
        lan2.add(lt, lambda q, hx=hx, hh=hh, hz=hz: (q[0] + hx, q[1] + hh, q[2] + hz))
    lan2.nr = True
    tube(lan2, [tuple(p) for p in cpts], 0.0007, "cord", seg=3, caps=False)
    for (hx, hh, hz) in hangs[:2]:
        tube(lan2, [(hx, hh + 0.010, hz), (hx, hh, hz)], 0.0006, "cord", seg=3, caps=False)
    lan2.nr = False
    feast = make_obj("feast", merge([tb, cm]), root, origin=(tx, 0.0, tz), smooth_angle=50)
    lamps = make_obj("lamps", merge([lm, lan2]), root, origin=(tx, 0.0, tz), smooth_angle=50)
    for k, p in enumerate(flames):
        empty("lampsFlame" if k == 0 else "lampsFlame%d" % (k + 1), p, lamps)
    return feast, lamps, flames
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


def P_PLAN_R():
    """plan turned a quarter (not mirrored): right = toward the viewer (+z), up = +x"""
    return {"A": (0, 0, 1), "B": (1, 0, 0), "D": (0, 1, 0)}




def _chars():
    """the figures' sheet places and printed bboxes: pipeline/pr_characters.py output where it exists (authoritative),
    the proposal below for figures not drawn yet"""
    prop = _chars_proposal()
    p = os.path.join(MODEL, "regions_characters.json")
    if not os.path.exists(p):
        return prop, False
    try:
        rc = json.load(open(p))
        got = {c: {"sheetX": rc["sheet"][c]["sheetX"], "sheetY": rc["sheet"][c]["sheetY"], "height": v["height"],
                   "box": v["bboxSheet"]} for c, v in rc["characters"].items() if c in rc.get("sheet", {})}
    except Exception as e:
        print("regions_characters.json unreadable, using the proposal:", e)
        return prop, False
    for c, v in prop.items():
        got.setdefault(c, v)
    return got, len(got) == len(rc.get("sheet", {})) == 3


def _chars_proposal():
    return {"father": {"sheetX": -0.33, "sheetY": 0.015, "height": 0.36, "box": [-0.45, 0.015, -0.21, 0.385]},
            "son": {"sheetX": 0.0, "sheetY": 0.015, "height": 0.34, "box": [-0.12, 0.015, 0.12, 0.365]},
            "brother": {"sheetX": 0.33, "sheetY": 0.015, "height": 0.37, "box": [0.20, 0.015, 0.46, 0.395]}}


SHEET_PLACE = {}                                       # sheet places this role overrides (none so far)


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
CHARS_PENDING = _apply_places(CHAR_PROPOSAL)
# kind, scale, centre-x and bottom of the bbox on the sheet (sheet coords: x -0.5..0.5, ys 0 = art rect bottom)
DRAWINGS = {
    "backdrop": dict(P_FRONT(), scale=1.78, cx=-0.140, y0=1.030, decorOnly=["sea"], members=["backdrop"]),
    "fig":      dict(P_FRONT(), scale=1.55, cx=0.300, y0=1.020, members=["figTree"]),
    "pig":      dict(P_FRONT(), scale=0.76, cx=0.430, y0=1.110, members=["pigBodies"]),
    "house":    dict(P_OBL(0.30, 0.42), scale=1.25, cx=-0.297, y0=0.700, decorOnly=["wall", "reed"],
                     members=["house", "door", "roofBooth"]),
    "tavern":   dict(P_OBL(0.30, 0.42), scale=1.97, cx=0.074, y0=0.725, decorOnly=["marble", "column", "crate"],
                     members=["tavern"]),
    "yard":     dict(P_OBL(0.30, 0.42), scale=1.50, cx=0.370, y0=0.700, decorOnly=["wallStone", "well"],
                     members=["well", "yard"]),
    "ground":   dict(P_PLAN(), scale=3.50, cx=-0.310, y0=0.410, decorOnly=["paving", "wheat", "soil", "road"],
                     members=["ground", "courtyard", "road", "field"]),
    "pen":      dict(P_OBL(0.10, 0.55), scale=1.60, cx=0.030, y0=0.410, decorOnly=["mud"], members=["pigpen", "pods"]),
    "feast":    dict(P_OBL(0.10, 0.55), scale=0.85, cx=0.355, y0=0.420, members=["feast", "lamps"]),
}
TEMPLATES = {}
CONSTS = {"ground": {"tuft": ("fig", "figLeaf"), "dryTuft": ("backdrop", "olive"), "pebble": ("yard", "well"),
                     "stone": ("yard", "wallStone"), "flowerY": ("tavern", "stallCloth"), "flowerR": ("feast", "cushion")},
          "field": {"wheatBlade": ("ground", "wheat")},
          "backdrop": {"boat": ("house", "door"), "town": ("tavern", "marble")},
          "door": {"ring": ("tavern", "windowDark")},
          "well": {"rope": ("pen", "straw")},
          "figTree": {"fig": ("feast", "food")},
          "tavern": {"flagA": ("feast", "cushion"), "flagB": ("tavern", "stallCloth"), "flagC": ("backdrop", "sea"),
                     "flagD": ("fig", "figLeaf"), "cord": ("pen", "straw"), "pole": ("pen", "trough"),
                     "stool": ("pen", "trough"), "cup": ("tavern", "stallCloth"), "fruit": ("tavern", "amphora"),
                     "melon": ("fig", "figLeaf"), "roofTile": ("tavern", "amphora")},
          "pods": {"pod": ("pen", "pods")},
          "pigBodies": {"eye": ("tavern", "windowDark")},
          "feast": {"tableLeg": ("pen", "trough"), "cup": ("tavern", "stallCloth")},
          "lamps": {"cord": ("pen", "straw"), "lamp": ("feast", "dish"), "lantern": ("tavern", "windowDark"),
                    "lampGlass": ("tavern", "stallCloth")}}
FORCE_NR = {"backdrop": {"town"}, "well": {"rope"}, "tavern": {"pole", "stool", "cup", "fruit", "melon", "roofTile"},
            "feast": {"tableLeg", "cup"}, "lamps": {"lamp", "lantern", "lampGlass"}, "pods": {"pod"}}


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
                if key is None and g is not None:         # bevel faces inherit a stray flag: their own region
                    key = (g, reg)
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
                       "written by pipeline/pr_homeland.py", "size": [W, H], "scale": 2, "ids": ids, "constUV": const},
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



# ============================================================================================ clearance
TIMED = ["feast", "lamps"]          # shown only part of the play: tested against those moments
EXEMPT = {}


def seg_dist_np(X, Z, a, b):
    ax, az = a; bx_, bz = b
    dx, dz = bx_ - ax, bz - az; L2 = max(dx * dx + dz * dz, 1e-12)
    t = np.clip(((X - ax) * dx + (Z - az) * dz) / L2, 0, 1)
    return np.hypot(X - ax - t * dx, Z - az - t * dz)


def pig_frames(rig, pigs, frames=(1, 13, 25, 37, 49, 61, 73, 85)):
    """world vertices of the skinned pigs at several frames of pigsWiggle (the trotter moves)"""
    sc = bpy.context.scene
    out = []
    for f in frames:
        sc.frame_set(f)
        dg = bpy.context.evaluated_depsgraph_get()
        ev = pigs.evaluated_get(dg)
        me = ev.to_mesh()
        mw = pigs.matrix_world
        out += [D(mw @ v.co) for v in me.vertices]
        ev.to_mesh_clear()
    sc.frame_set(1)
    return out


def check_clearance(objs, pig_pts=None):
    """CONTRACT §6: no geometry above 0.012 within 0.05 of a mark, nothing on the straight paths between consecutive
    marks of one actor. Overhead parts (>= 0.17: the fig crown, the awning) only need head room: between 0.17 and
    0.40 they must stay 0.035 from a walk line. The feast and lamps are tested against the stands and moves made while
    they are shown; the pigs at eight frames of their loop."""
    pts, names = [], []
    for name, ob in objs.items():
        if ob.type != 'MESH' or name in EXEMPT:
            continue
        vv = pig_pts if (name == "pigBodies" and pig_pts) else world_verts(ob)
        for x, h, z in vv:
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
    for node in TIMED:
        win = visible_windows(node)
        ov = lambda t0, t1: any(t0 < b and t1 > a for a, b in win)
        for label, p, t0, t1 in STANDS:
            if ov(t0, t1):
                test("%s / %s" % (node, label), np.hypot(X - p[0], Z - p[1]), hard, [node])
        for label, a, b, is_hard, t0, t1 in PATHS:
            if ov(t0, t1):
                test("%s / %s" % (node, label), seg_dist_np(X, Z, a, b), hard if is_hard else soft, [node])
    fsel = (names == "feast") & (P[:, 1] > 0.012)
    feast_d = min(float(np.hypot(X[fsel] - x, Z[fsel] - z).min()) for x, z in FEAST_MARKS) if fsel.any() else 9.0
    if feast_d < FEAST_CLEAR:
        hard["feast table < 0.06 from the S11 marks"] = round(feast_d, 4)
    first = {}
    for a in TL["acting"]:
        if "to" in a and a["who"] not in first:
            first[a["who"]] = (float(a["to"][0]), float(a["to"][1]))
    for c, p in first.items():
        if c in CHAR_PROPOSAL:
            s = (CHAR_PROPOSAL[c]["sheetX"], 0.0)
            test("start %s %.2f,0>%.2f,%.2f" % (c, s[0], p[0], p[1]), seg_dist_np(X, Z, s, p), soft)
    return hard, soft, round(feast_d, 4)


# ============================================================================================ build
def page_mat():
    m = bpy.data.materials.new("pr_page")
    try:
        m.use_nodes = True
    except Exception:
        pass
    b = m.node_tree.nodes.get("Principled BSDF")
    if b:
        b.inputs["Roughness"].default_value = 0.85
    return m


STATE = {}
ORDER = ["ground", "backdrop", "house", "roofBooth", "door", "courtyard", "well", "figTree", "yard", "field", "road",
         "tavern", "pigpen", "pods", "pigBodies", "feast", "lamps"]


def mode_build():
    SOFT_SEGS[:] = [(a, b) for _, a, b, hard, _, _ in PATHS if not hard]
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    root = link(bpy.data.objects.new("homeland", None))
    objs = {}
    objs["ground"], scatter = build_ground(root)
    objs["backdrop"] = build_backdrop(root)
    objs["house"], objs["door"], objs["roofBooth"] = build_house(root)
    objs["courtyard"] = build_courtyard(root)
    objs["well"], objs["yard"] = build_yard_pieces(objs["courtyard"])
    objs["figTree"] = build_fig(objs["courtyard"])
    objs["field"] = build_field(root)
    objs["road"] = build_road(root)
    objs["tavern"] = build_tavern(root)
    objs["pigpen"], objs["pods"], nposts = build_pen(root)
    rig, objs["pigBodies"], pig_t = build_pigs(root)
    objs["feast"], objs["lamps"], flames = build_feast(root)
    bpy.context.view_layer.update()
    src = raster_sources(objs, {})
    setup_maps(src)
    apply_uvs(objs)
    tris = {}
    for n, ob in objs.items():
        ob.data.calc_loop_triangles(); tris[n] = len(ob.data.loop_triangles)
    total = sum(tris.values())
    print("HOMELAND_TRIS", total, json.dumps(tris))
    print("SCATTER", json.dumps(scatter), "fencePosts", nposts)
    assert total <= MAX_TRIS, "over budget %d" % total
    lay = check_layout()
    ppts = pig_frames(rig, objs["pigBodies"])
    hard, soft, feast_d = check_clearance(objs, ppts)
    print("LAYOUT", "OK" if not lay else lay)
    print("BBOXES", json.dumps({g: [round(float(v), 3) for v in d["bboxSheet"]] for g, d in DRAWINGS.items()}))
    print("CLEARANCE", "OK" if not hard else json.dumps(hard))
    print("CLEARANCE_SOFT", json.dumps(soft))
    print("FEAST_TABLE min distance to the S11 marks", feast_d)
    print("CHAR_PLACES", json.dumps({c: [v["sheetX"], v["sheetY"]] for c, v in CHAR_PROPOSAL.items()}),
          "from regions_characters.json" if CHARS_FROM_FILE else "proposal (no regions_characters.json yet)")
    print("BUDGET", "%d / %d (target), %d hard ceiling" % (total, TARGET_TRIS, MAX_TRIS))
    if MODE == "check":
        STATE.update(objs=objs, rig=rig)
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
    write_design(objs, tris, total, flames, hmax, const, hard, soft, feast_d, nposts)
    STATE.update(objs=objs, tex=tex_img, demo=demo, root=root, rig=rig, flames=flames)
    print("BUILD_OK", GLB, total)


def write_design(objs, tris, total, flames, hmax, const, hard, soft, feast_d, nposts):
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
        sp = DRAWINGS[g] if g else None
        fu = ({k: (round(sp[k], 5) if isinstance(sp[k], float) else sp[k]) for k in ("A", "B", "D", "scale", "sheetX",
                                                                                   "sheetY")} if sp else None)
        pieces.append({"id": name, "drawing": g, "frontUV": fu, "packed": "drawing positions (P) shifted so parts "
                       "sit side by side" if g in ("yard", "tavern", "pen", "feast") or name == "roofBooth" else None,
                       "namedTexels": {r: list(k) for r, k in CONSTS.get(name, {}).items()} or None,
                       "regions": sorted(set(REG_OF[name])), "heightMax": hmax[name], "tris": tris[name]})
    drawings = {g: {k: (round(v, 5) if isinstance(v, float) else v) for k, v in dsp.items()} for g, dsp in DRAWINGS.items()}
    names = ["lampsFlame"] + ["lampsFlame%d" % (k + 1) for k in range(1, len(flames))]
    d["set"] = {
        "generatedBy": "pipeline/pr_homeland.py", "doc": "docs/prodigal/SET.md", "contract": "docs/prodigal/CONTRACT.md §6",
        "root": "homeland",
        "units": "art-width units; glTF (x, h, z): page = XZ plane at h 0, +z toward the viewer, z 0 = art rect bottom",
        "nodes": {"house": [-0.38, 0.0, -0.47], "door": {"hinge": [DOOR_X - DOOR_W / 2, 0.0, DOOR_Z - 0.0035],
                                                          "frontZ": DOOR_Z, "width": DOOR_W,
                                                          "height": round(DOOR_SPRING + DOOR_W / 2, 4)},
                  "courtyard": [-0.31, 0.0, -0.18], "well": [WELL[0], 0.0, WELL[1]], "figTree": [FIG[0], 0.0, FIG[1]],
                  "field": [(FIELD[0] + FIELD[1]) / 2, 0.0, (FIELD[2] + FIELD[3]) / 2], "tavern": [TAV_C[0], 0.0, TAV_C[1]],
                  "pigpen": [0.41, 0.0, 0.06], "pods": [TROUGH[0], 0.0, TROUGH[1]], "pigs": [0.49, 0.0, 0.06],
                  "feast": [TABLE_C[0], 0.0, TABLE_C[1]], "lamps": [TABLE_C[0], 0.0, TABLE_C[1]],
                  "lampsFlame": {n: [round(c, 4) for c in p] for n, p in zip(names, flames)},
                  "houseChimneyForMusic": [-0.38, 0.22, -0.47]},
        "footprints": {"floor": [FLOOR[0], FLOOR[2], FLOOR[1], FLOOR[3]], "house": [HOUSE[0], HOUSE[2], HOUSE[1], HOUSE[3]],
                       "stair": [STAIR_X[0], HOUSE[2], STAIR_X[1], HOUSE[3]], "courtyardPaving": [YARD[0], YARD[2], YARD[1], YARD[3]],
                       "wellRadius": WELL_R, "bench": list(BENCH), "oven": list(OVEN), "field": list(FIELD),
                       "plantedRowsFrontZ": PLANT_Z, "tavern": [TAVERN[0], TAVERN[2], TAVERN[1], TAVERN[3]],
                       "awning": [AWN[0], AWN[2], AWN[1], AWN[3]], "awningFrontEdge": {"z": AWN[3], "h": AWN_H[1],
                                                                                   "x": [AWN[0], AWN[1]]},
                       "stall": list(STALL), "pen": [PEN[0], PEN[2], PEN[1], PEN[3]], "trough": list(TROUGH),
                       "feastTable": [TABLE_C[0] - TABLE_W / 2, TABLE_C[1] - TABLE_D / 2, TABLE_C[0] + TABLE_W / 2,
                                      TABLE_C[1] + TABLE_D / 2],
                       "pigs": [[s[1], s[2]] for s in PIG_SPOTS], "trotCircle": {"centre": list(TROT_C), "r": TROT_R}},
        "heights": {"houseWall": HOUSE_H, "parapetTop": HOUSE_H + 0.013, "boothTop": HOUSE_H + 0.054,
                    "doorFrameFrontZ": FRAME_Z, "awningBack": AWN_H[0], "awningFront": AWN_H[1], "columns": COL_H,
                    "figTop": hmax["figTree"], "backdropTop": hmax["backdrop"], "tableTop": TABLE_H, "fence": 0.058,
                    "wheatMax": hmax["field"]},
        "animations": {"pigsWiggle": {"node": "pigs", "mesh": "pigBodies", "length": 4.0, "fps": 24, "loop": True,
                                      "note": "snouts rooting, tails twitching, pig 4 trots a circle r %.3f round %s" % (TROT_R, list(TROT_C))}},
        "hiddenAtStart": HIDDEN_AT_START,
        "uvRule": {"linear": "a = A.P, b = B.P: u = a / scale + sheetX + 0.5, v = (b / scale + sheetY) / 1.227; "
                             "P = world position, or the drawing position for packed parts / instanced pieces",
                   "edgeOn": "faces with n . D < 0.22 (edge-on or facing away) take one clean texel of their region (L51)",
                   "namedTexels": "scattered bits take one texel of a named (drawing, region); constUV in model/set_id_2x.json"},
        "drawings": drawings, "pieces": pieces, "constUV": const,
        "clearance": {"hard": "OK" if not hard else hard, "soft": soft, "feastTableMinDist": feast_d, "exempt": EXEMPT},
        "sheetLayout": {"characters": CHAR_PROPOSAL, "charactersFrom": "model/regions_characters.json" if CHARS_FROM_FILE
                        else "proposal (regions_characters.json not there yet)", "placesSetHere": SHEET_PLACE},
        "demoColours": COLOURS, "tris": total, "budget": TARGET_TRIS,
    }
    d["set"]["nodes"].pop("houseChimneyForMusic")
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
    save_png(line, os.path.join(WORK, "homeland_drawings_lineart.png"))
    save_png(demo, os.path.join(WORK, "homeland_drawings_demo.png"))
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
        "skin": "#E2A878", "sky": "#6FB3E0", "yellow": "#F2C230", "red": "#D2483A", "hair": "#4A2E1F",
        "cream": "#F1E6CC", "green": "#3F7A55", "grey": "#B9B4AE", "white": "#FBF8EF", "rust": "#A8582E",
        "beige": "#E9D9B6", "wood": "#9B6B43", "iron": "#7A7F86"}.items()}
    for k, m in mats.items():
        REGION_MATS[k] = m
    for who, (x, z, yaw) in layout.items():
        mb = MB()
        if who == "son":
            lathe(mb, [(0.0, 0.0), (0.030, 0.0), (0.033, 0.03), (0.032, 0.12), (0.028, 0.22), (0.024, 0.255), (0.0, 0.26)],
                  "sky", C=(x, 0, z), seg=18)
            lathe(mb, [(0.034, 0.125), (0.034, 0.140)], "yellow", C=(x, 0, z), seg=18)
            lathe(mb, [(0.033, 0.15), (0.031, 0.24)], "red", C=(x, 0, z), seg=18,
                  rfun=lambda th, i, k: 1.03 if math.sin(th) < 0.7 else 0.0001)
            sphere(mb, (x, 0.290, z), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.300, z - 0.004), 0.032, "hair", seg=12, rings=7, sh=0.85)
        elif who == "father":
            lathe(mb, [(0.0, 0.0), (0.040, 0.0), (0.040, 0.02), (0.034, 0.14), (0.029, 0.25), (0.024, 0.27), (0.0, 0.275)],
                  "cream", C=(x, 0, z), seg=18)
            lathe(mb, [(0.044, 0.02), (0.038, 0.14), (0.033, 0.25), (0.028, 0.27)], "green", C=(x, 0, z - 0.003),
                  seg=18, rfun=lambda th, i, k: 1.0 if math.sin(th) < 0.5 else 0.0001)
            sphere(mb, (x, 0.300, z), 0.030, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.282, z + 0.017), 0.021, "grey", seg=10, rings=7, sh=1.4, sz=0.7)
            sphere(mb, (x, 0.315, z - 0.006), 0.034, "white", seg=12, rings=7, sh=0.85)
        else:
            lathe(mb, [(0.0, 0.0), (0.024, 0.0), (0.026, 0.08), (0.038, 0.11), (0.040, 0.18), (0.036, 0.25), (0.030, 0.27),
                       (0.0, 0.275)], "rust", C=(x, 0, z), seg=18)
            sphere(mb, (x, 0.305, z), 0.031, "skin", seg=14, rings=9)
            sphere(mb, (x, 0.315, z - 0.006), 0.033, "beige", seg=12, rings=7, sh=0.8)
            tube(mb, [(x + 0.045, 0.02, z + 0.02), (x + 0.050, 0.33, z + 0.01)], 0.004, "wood", seg=6)
            box(mb, x + 0.040, x + 0.068, 0.0, 0.01, z + 0.01, z + 0.03, "iron")
        ob = make_obj("pv_" + who, mb, None, origin=(x, 0.0, z), smooth_angle=60)
        ob["pv"] = 1
        ob.rotation_euler = (0, 0, math.radians(yaw))


def mode_preview():
    if not STATE:
        raise SystemExit("preview needs a build in the same run: use `-- all`")
    sc = bpy.context.scene
    objs = STATE["objs"]
    img = save_png(STATE["tex"], os.path.join(WORK, "homeland_preview_texture.png")); img.pack()
    pmat = tex_mat("pv_set", img)
    for n, ob in objs.items():
        ob.data.materials.clear(); ob.data.materials.append(pmat)
    sheet = save_png(STATE["demo"], os.path.join(WORK, "homeland_preview_sheet.png")); sheet.pack()
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
    flame_m = flat_mat("pv_flame", "#FFE6A0", 0.5, emit=("#FFC860", 12.0))
    lamp_lights = []
    fm = MB()
    for (fx, fh, fz) in STATE["flames"]:
        lathe(fm, [(0.0, fh - 0.0015), (0.0022, fh + 0.0005), (0.0014, fh + 0.0040), (0.0, fh + 0.0068)], "f",
              C=(fx, 0, fz), seg=8)
        l = bpy.data.lights.new("pv_lamp", 'POINT'); l.color = (1.0, 0.70, 0.38); l.shadow_soft_size = 0.004
        o = link(bpy.data.objects.new("pv_lamp", l)); o.location = B(fx, fh + 0.004, fz)
        lamp_lights.append(l)
    fob = make_obj("pv_flames", fm, None); fob.data.materials[0] = flame_m
    win_l = []
    for (wx, wh) in ((-0.468, 0.062), (-0.468, 0.144), (-0.398, 0.144), (-0.270, 0.144)):
        l = bpy.data.lights.new("pv_win", 'POINT'); l.color = (1.0, 0.62, 0.30); l.shadow_soft_size = 0.01
        o = link(bpy.data.objects.new("pv_win", l)); o.location = B(wx, wh, HOUSE[3] + 0.012)
        win_l.append(l)

    def light(mode):
        fob.hide_render = mode != "night"
        for l in lamp_lights + win_l:
            l.energy = 0.0
        if mode == "day":
            sun.data.energy = 3.1; sun.data.color = (1.0, 0.95, 0.86)
            sun.rotation_euler = (math.radians(42), math.radians(-18), math.radians(-30))
            fill.data.energy = 6.0; fill.data.color = (1.0, 0.90, 0.76)
            bg.inputs[0].default_value = (0.80, 0.86, 0.94, 1); bg.inputs[1].default_value = 0.75
        elif mode == "dusk":
            sun.data.energy = 2.2; sun.data.color = (1.0, 0.66, 0.36)
            sun.rotation_euler = (math.radians(70), math.radians(8), math.radians(-60))
            fill.data.energy = 3.0; fill.data.color = (0.95, 0.65, 0.55)
            bg.inputs[0].default_value = (0.75, 0.55, 0.50, 1); bg.inputs[1].default_value = 0.6
        else:
            sun.data.energy = 0.40; sun.data.color = (0.55, 0.66, 1.0)
            sun.rotation_euler = (math.radians(55), math.radians(20), math.radians(40))
            fill.data.energy = 0.8; fill.data.color = (0.45, 0.55, 1.0)
            bg.inputs[0].default_value = (0.08, 0.10, 0.24, 1); bg.inputs[1].default_value = 0.5
            for l in lamp_lights:
                l.energy = 0.5
            for l in win_l:
                l.energy = 0.4
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
    light("day")
    show(HIDDEN_AT_START, False)
    cast({})
    phone = ((-0.08, 0.95, 1.15), (-0.08, 0.05, -0.50), 55, (720, 1280))
    shoot("homeland_preview_phone_set", *phone)
    shoot("homeland_preview_phone_low", (0.02, 0.62, 0.95), (0.02, 0.06, -0.30), 52, (720, 1280))
    shoot("homeland_preview_front", (0.0, 0.26, 2.3), (0.0, 0.14, -0.25), 21, (1600, 1000))
    s01 = {"father": (-0.30, -0.24, 0), "son": (-0.16, -0.20, 0), "brother": (0.02, -0.34, 0)}
    cast(s01)
    shoot("homeland_preview_phone", *phone)
    shoot("homeland_preview_orbit", orbit((0.0, 0.10, -0.18), 1.6, 0.55, -35), (0.0, 0.08, -0.18), 38, (1280, 720))
    shoot("homeland_preview_home", (-0.10, 0.24, 0.12), (-0.38, 0.10, -0.36), 46, (1280, 720))
    cast({"son": (0.32, -0.26, 0)})
    light("dusk")
    shoot("homeland_preview_tavern", (0.30, 0.20, 0.04), (0.42, 0.10, -0.42), 46, (1280, 720))
    light("day")
    cast({"son": (0.34, 0.04, 0)})
    shoot("homeland_preview_pigpen", (0.26, 0.26, 0.38), (0.44, 0.02, 0.06), 40, (1280, 720))
    sc.frame_set(1)
    cast({})
    for f in (1, 25, 49, 73):
        sc.frame_set(f)
        shoot("pigs_f%02d" % f, (0.46, 0.14, 0.30), (0.48, 0.02, 0.06), 34, (900, 600), WORK)
    sc.frame_set(1)
    cast({"father": (0.00, 0.06, -90), "son": (0.10, 0.08, 90), "brother": (0.02, -0.34, 0)})
    light("dusk")
    shoot("homeland_preview_run", (-0.25, 0.30, 0.55), (0.04, 0.10, -0.08), 40, (1280, 720))
    light("night")
    show(["feast", "lamps"], True)
    cast({"father": (-0.22, -0.10, -110), "son": (-0.32, -0.12, 100)})
    shoot("homeland_preview_night", (-0.64, 0.20, 0.06), (-0.36, 0.07, -0.24), 46, (1280, 720))
    shoot("homeland_preview_night_front", (-0.18, 0.30, 0.42), (-0.36, 0.08, -0.26), 44, (1280, 720))
    shoot("homeland_preview_night_phone", *phone)
    cast({})
    shoot("close_feast", (-0.36, 0.14, -0.06), (-0.42, 0.03, -0.215), 44, (1200, 800), WORK)
    show(["feast", "lamps"], False)
    light("day")
    shoot("homeland_preview_back", orbit((0.0, 0.10, -0.18), 1.5, 0.45, 160), (0.0, 0.08, -0.18), 38, (1280, 720))
    cam.data.type = 'ORTHO'; cam.data.ortho_scale = 1.80
    cam.location = B(0.0, 3.0, -0.64); cam.rotation_euler = (0, 0, 0)
    sc.render.resolution_x, sc.render.resolution_y = 1240, 1754; sc.render.resolution_percentage = 50
    sc.render.filepath = os.path.join(MODEL, "homeland_preview_topdown.png"); bpy.ops.render.render(write_still=True)
    cam.data.type = 'PERSP'
    if os.environ.get("PR_CLOSEUPS", "1") == "1":
        shoot("close_house", (-0.30, 0.16, -0.20), (-0.36, 0.10, -0.42), 46, (1200, 800), WORK)
        shoot("close_door", (-0.31, 0.09, -0.27), (-0.33, 0.07, -0.38), 40, (1000, 800), WORK)
        shoot("close_fig_well", (-0.30, 0.14, 0.12), (-0.47, 0.10, -0.15), 46, (1200, 800), WORK)
        shoot("close_field", (0.10, 0.14, -0.22), (0.08, 0.02, -0.44), 46, (1200, 700), WORK)
        shoot("close_backdrop", (0.10, 0.24, -0.10), (0.10, 0.14, -0.57), 52, (1400, 700), WORK)
        shoot("close_tavern_side", (0.16, 0.16, -0.30), (0.40, 0.10, -0.46), 44, (1200, 800), WORK)
        shoot("close_house_back", (-0.20, 0.30, -0.80), (-0.38, 0.10, -0.47), 44, (1200, 800), WORK)
    print("PREVIEW_OK")


# ============================================================================================ verify
NEED = ["homeland", "ground", "backdrop", "house", "door", "courtyard", "well", "figTree", "yard", "field", "road",
        "tavern", "pigpen", "pods", "pigs", "pigBodies", "feast", "lamps", "lampsFlame"]


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
    flames = sorted(n for n in names if n.startswith("lampsFlame"))
    acts = [a.name for a in bpy.data.actions]
    loop = None
    rig = bpy.data.objects.get("pigs")
    if rig and rig.animation_data and rig.animation_data.action:
        sc = bpy.context.scene
        pig = bpy.data.objects.get("pigBodies")

        def snap(f):
            sc.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get(); ev = pig.evaluated_get(dg); me = ev.to_mesh()
            a = np.array([tuple(v.co) for v in me.vertices]); ev.to_mesh_clear()
            return a
        fr = rig.animation_data.action.frame_range
        a1, a2, a3 = snap(int(fr[0])), snap(int(fr[1])), snap(int(fr[0]) + 24)
        loop = round(float(np.abs(a1 - a2).max()), 6)
        moved = round(float(np.abs(a1 - a3).max()), 4)
        print("PIGS frames", list(fr), "loopError", loop, "movedAt1s", moved)
    ok = not missing and tris <= MAX_TRIS and uv_bad == 0 and any("pigsWiggle" in a for a in acts) and \
        loop is not None and loop < 1e-4
    print("VERIFY", "PASS" if ok else "FAIL", json.dumps({"missing": missing, "tris": tris, "uvOutside": uv_bad,
                                                         "parents": parents, "flames": flames, "actions": acts}))


if __name__ == "__main__":
    if MODE in ("build", "all", "preview", "check"):
        mode_build()
    if MODE in ("preview", "all"):
        mode_preview()
    if MODE in ("verify", "all"):
        mode_verify()
