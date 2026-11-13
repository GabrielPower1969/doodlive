"""Blender (headless): David & Goliath characters — meshes, rig, weights, UVs, sheet ID render, previews, GLB export.

Redraw of 2026-10-27 (CONTRACT §11): realistic-proportion cartoon people instead of joined ellipsoids.

Everything is driven by assets/david-goliath/design.json (Design role, version 2) and docs/david-goliath/CONTRACT.md:
  * art-width units, rest pose built exactly at design.json bonesLocal (arms 45 deg below horizontal, facing the viewer);
  * one Armature per character with the CONTRACT §3 bone names + the §11.6 finger bones + the prop bones;
  * modelling = box-modelled quad cages (rings with edge loops at every joint, ports for sleeves, fingers and thumbs),
    weights painted on the cage, then Subdivision Surface level 1 APPLIED (weights are interpolated by the modifier),
    then small surface details (nose, lips, brow, pleats, armour scales) displaced on the subdivided mesh;
  * skin: head+neck, each arm with its hand (palm, 4 fingers, thumb) and each leg with its foot are continuous meshes;
    the torso under the clothes is not modelled (= "hidden body deleted", §11.5);
  * clothes are separate shells with rolled hems; props are rigid meshes parented to one bone;
  * all skinned parts are joined into ONE body mesh per character;
  * UV0 = front orthographic projection onto the art rectangle at the SHEET position (u = x + sheetX + 0.5,
    v = (y + sheetY) / artH, x/y character-local), computed in rest pose (LESSONS L7), with a small inward inset;
  * UV1 "decal" = face-decal projection (design.json faceDecals.rectLocal), back of the head pushed outside 0..1.

Coordinates: design space (x right, y up, z toward the viewer) == glTF space. Blender is Z-up, so a design point
(x, y, z) is Blender (x, -z, y); export_yup turns it back. The GLBs are in character-local coordinates (root bone at the
origin); the sheet position is design.json characters.<id>.sheetX / sheetY.

Modes (run from the repo root; pipeline/dg_make_all.sh runs them all in order):
  blender -b --factory-startup --python pipeline/dg_build.py -- build     model + GLB + ID render + previews + pose test
  blender -b --factory-startup --python pipeline/dg_build.py -- uvcheck   textured renders with sheet/demo-colored.png
  blender -b --factory-startup --python pipeline/dg_build.py -- verify    re-import the GLBs and check bones/skins/props
Intermediate renders go to $DG_WORK (default /tmp/dg_work); pipeline/dg_compose.py turns them into the PNGs we ship.
"""
import bpy, bmesh, math, sys, os, json, random
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DESIGN = json.load(open(os.path.join(ROOT, "assets/david-goliath/design.json")))
MODEL = os.path.join(ROOT, "assets/david-goliath/model")
SHEET = os.path.join(ROOT, "assets/david-goliath/sheet")
WORK = os.environ.get("DG_WORK", "/tmp/dg_work")
BLEND = os.path.join(MODEL, "dg_characters.blend")
for d in (MODEL, SHEET, WORK):
    os.makedirs(d, exist_ok=True)

ART_H = DESIGN["artHeightUnits"]            # 1.227
INSET = 0.004                               # UV inset at silhouettes (art units = 4 px of the 1000 px art rect)
CHARS = ("david", "goliath")
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR"]
FINGER_BONES = ["fingersL", "fingerTipsL", "thumbL", "fingersR", "fingerTipsR", "thumbR"]
EXTRA_BONES = {"david": FINGER_BONES + ["slingCord1", "slingCord2", "slingPouch", "stone"],
               "goliath": FINGER_BONES + ["spear", "shield", "helmet"]}


# =============================================================================================== small math
def V(x=0.0, y=0.0, z=0.0):
    return Vector((float(x), float(y), float(z)))


def to_bl(p):                                # design -> Blender
    return Vector((p.x, -p.z, p.y))


def to_design(c):                            # Blender -> design
    return Vector((c.x, c.z, -c.y))


def se(c, e):                                # signed power used by superellipses
    return math.copysign(abs(c) ** (2.0 / e), c)


def smoothstep(e0, e1, x):
    if e1 == e0:
        return 1.0 if x >= e1 else 0.0
    t = min(1.0, max(0.0, (x - e0) / (e1 - e0)))
    return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def table(rows, x):
    """Piecewise-linear interpolation in a table of rows (x, v1, v2, ...) sorted by x (either direction)."""
    rs = rows if rows[0][0] <= rows[-1][0] else list(reversed(rows))
    if x <= rs[0][0]:
        return tuple(rs[0][1:])
    for a, b in zip(rs, rs[1:]):
        if x <= b[0]:
            t = (x - a[0]) / (b[0] - a[0]) if b[0] != a[0] else 0.0
            t = t * t * (3 - 2 * t) * 0.35 + t * 0.65            # mostly linear, slightly eased (no kinks at nodes)
            return tuple(lerp(u, v, t) for u, v in zip(a[1:], b[1:]))
    return tuple(rs[-1][1:])


def cr(p0, p1, p2, p3, t):
    t2, t3 = t * t, t * t * t
    return 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)


def cr_closed(ctrl, u):
    n = len(ctrl); t = (u % 1.0) * n; i = int(math.floor(t)); f = t - i
    return cr(ctrl[(i - 1) % n], ctrl[i % n], ctrl[(i + 1) % n], ctrl[(i + 2) % n], f)


def densify(rows, k, ylo=None, yhi=None):
    """Insert k-1 Catmull-Rom interpolated rows between consecutive rows (tuples of floats); only between rows whose
    first value lies in [ylo, yhi] when given."""
    R = [list(r) for r in rows]; out = []
    for i in range(len(R) - 1):
        out.append(tuple(R[i]))
        y0, y1 = R[i][0], R[i + 1][0]
        if ylo is not None and not (ylo <= min(y0, y1) and max(y0, y1) <= yhi):
            continue
        p0, p3 = R[max(i - 1, 0)], R[min(i + 2, len(R) - 1)]
        for j in range(1, k):
            t = j / k
            out.append(tuple(cr(a, b, c, d, t) for a, b, c, d in zip(p0, R[i], R[i + 1], p3)))
    out.append(tuple(R[-1]))
    return out


def cr_open(pts, t):
    """Catmull-Rom through pts, t in [0,1] uniform per segment."""
    n = len(pts) - 1; x = min(max(t, 0.0), 1.0) * n; i = min(int(x), n - 1); f = x - i
    p0 = pts[max(i - 1, 0)]; p3 = pts[min(i + 2, n)]
    return cr(p0, pts[i], pts[i + 1], p3, f)


def kcomp(n):
    """Radial growth that makes a ring of n cage vertices land on the intended radius after one Catmull-Clark step."""
    return 4.0 / (3.0 + math.cos(2 * math.pi / n))


def front_dense(n, a=0.42):
    """n ring parameters in [0,1) (0 = front), denser at the front (face, toes) than at the back."""
    return [(k / n - a / (2 * math.pi) * math.sin(2 * math.pi * k / n)) % 1.0 for k in range(n)]


def perp(v, axis):
    w = v - axis * v.dot(axis)
    return w.normalized() if w.length > 1e-9 else w


def rot_about(v, axis, ang):
    return Matrix.Rotation(ang, 3, axis) @ v


# =============================================================================================== cage
class Cage:
    """Quad cage in design coordinates. Every vertex carries its skin weights (dict bone -> w), every face a region
    name and a piece index (pieces = separately outlined areas of the printed sheet)."""
    def __init__(self):
        self.v, self.w, self.f, self.reg, self.pc = [], [], [], [], []

    def add(self, p, wfn):
        self.v.append(V(*p)); self.w.append(wfn(self.v[-1]) if wfn else {})
        return len(self.v) - 1

    def ring(self, pts, wfn):
        return [self.add(p, wfn) for p in pts]

    def face(self, idx, reg, pc=0):
        self.f.append(tuple(idx)); self.reg.append(reg); self.pc.append(pc)

    def bridge(self, r1, r2, reg, pc=0, skip=(), closed=True, regfn=None):
        n = len(r1)
        for j in range(n if closed else n - 1):
            if j in skip:
                continue
            q = (r1[j], r1[(j + 1) % n], r2[(j + 1) % n], r2[j])
            rg = regfn(q) if regfn else reg
            self.face(q, rg, pc)

    def fan(self, ring, p, wfn, reg, pc=0):
        c = self.add(p, wfn); n = len(ring)
        for j in range(n):
            self.face((ring[j], ring[(j + 1) % n], c), reg, pc)
        return c

    def grid_cap(self, ring, wfn, reg, pc=0, centre=None, lift=None):
        """Close an even ring with quads: a strip of quads across the middle (no triangle fan)."""
        n = len(ring); h = n // 2
        if n % 2 or n < 6:
            return self.fan(ring, centre if centre is not None else sum((self.v[i] for i in ring), V()) / n, wfn, reg, pc)
        # pair ring[j] with ring[n-j] (mirror across the 0 - n/2 axis)
        mids = []
        for j in range(1, h):
            a, b = self.v[ring[j]], self.v[ring[n - j]]
            m = (a + b) / 2
            if lift is not None:
                m = lift(m)
            mids.append(self.add(m, wfn))
        prev = [ring[0]]
        # first triangle-free strip: ring[0], ring[1], mid1, ring[n-1]
        self.face((ring[0], ring[1], mids[0], ring[n - 1]), reg, pc)
        for k in range(1, h - 1):
            self.face((mids[k - 1], ring[k], ring[k + 1], mids[k]), reg, pc)
            self.face((ring[n - k], mids[k - 1], mids[k], ring[n - k - 1]), reg, pc)
        self.face((mids[h - 2], ring[h - 1], ring[h], ring[h + 1]), reg, pc)
        return mids


def extrude_port(cg, loop, stations, ref, wfn, reg, pc=0, cap=True, mode="square", cap_len=0.6, regfn=None):
    """Grow a tube out of an existing vertex loop (a 'port'), box-modelling style.
    stations: list of (centre, (a+, a-, b+, b-)) half-extents along the transported frame (A = ref axis, B = T x A).
    mode 'square': keep the loop's corner layout (fingers); 'round': redistribute to even angles (sleeves)."""
    pts = [cg.v[i] for i in loop]; c0 = sum(pts, V()) / len(pts)
    T = (stations[0][0] - c0).normalized()
    A = perp(ref, T); Bv = T.cross(A)
    offs = [((p - c0).dot(A), (p - c0).dot(Bv)) for p in pts]
    if mode == "square":
        ma = max(abs(o[0]) for o in offs) or 1.0; mb = max(abs(o[1]) for o in offs) or 1.0
        unit0 = [(o[0] / ma, o[1] / mb) for o in offs]
        units = [unit0] * len(stations)
    else:
        ang = [math.atan2(o[1], o[0]) for o in offs]
        un = [ang[0]]
        for a in ang[1:]:
            while a - un[-1] > math.pi: a -= 2 * math.pi
            while a - un[-1] < -math.pi: a += 2 * math.pi
            un.append(a)
        step = 2 * math.pi / len(un) * (1 if un[-1] > un[0] else -1)
        even = [un[0] + step * k for k in range(len(un))]
        units = []
        for k in range(len(stations)):
            t = min(1.0, (k + 1) / 2.0)
            units.append([(math.cos(lerp(a, e, t)), math.sin(lerp(a, e, t))) for a, e in zip(un, even)])
    prev = loop; prevc = c0
    for k, (c, ext) in enumerate(stations):
        nxt = stations[k + 1][0] if k + 1 < len(stations) else c + (c - prevc)
        T = (nxt - prevc).normalized()
        A = perp(A, T); Bv = T.cross(A)
        ring = []
        for ua, ub in units[k]:
            ring.append(c + A * (ua * (ext[0] if ua >= 0 else ext[1])) + Bv * (ub * (ext[2] if ub >= 0 else ext[3])))
        idx = cg.ring(ring, wfn)
        cg.bridge(prev, idx, reg, pc, regfn=regfn)
        prev, prevc = idx, c
    if cap:
        ext = stations[-1][1]; r = (ext[0] + ext[1] + ext[2] + ext[3]) / 4
        cg.fan(prev, stations[-1][0] + T * r * cap_len, wfn, reg, pc)
    return prev


# =============================================================================================== weights
def seg_metrics(p, a, b):
    ab = b - a; L = ab.length; u = ab / L
    t = (p - a).dot(u)
    return max(0.0, -t, t - L), (p - (a + u * t)).length


def weigh(p, spec, Bn, blend):
    """Smooth chain skinning: each candidate bone scores by how far the point lies OUTSIDE the bone's span along its
    axis (relative to the nearest bone), times an optional radial reach falloff. Normalised, pruned, max 4."""
    m = {b: seg_metrics(p, Bn[b][0], Bn[b][1]) for b, _ in spec}
    amin = min(ax for ax, _ in m.values())
    w = {}
    for b, reach in spec:
        ax, rad = m[b]
        v = math.exp(-((ax - amin) / blend) ** 2)
        if reach:
            v *= math.exp(-(rad / reach) ** 2)
        w[b] = v
    s = sum(w.values()) or 1.0
    w = {b: v / s for b, v in w.items() if v / s > 0.03}
    w = dict(sorted(w.items(), key=lambda kv: -kv[1])[:4])
    s = sum(w.values())
    return {b: v / s for b, v in w.items()}


def bones_of(ch):
    bl = DESIGN["characters"][ch]["bonesLocal"]
    return {k: (V(*v["head"]), V(*v["tail"]), v["parent"]) for k, v in bl.items()}


class Ctx:
    """Per-character build context: bones, proportions, scale, weight-function factory, parts list."""
    def __init__(self, ch):
        self.ch = ch; self.info = DESIGN["characters"][ch]; self.P = self.info["proportions"]
        self.B = bones_of(ch); self.S = self.info["height"] / 0.30; self.blend = 0.006 * self.S
        self.parts = []

    def w(self, spec, blend=None):
        spec = [(s, None) if isinstance(s, str) else s for s in spec]
        B, bl = self.B, blend or self.blend
        return lambda p: weigh(p, spec, B, bl)

    def add(self, name, cg, **kw):
        self.parts.append(dict(name=name, cage=cg, **kw))


def mixw(*pairs):
    """Blend weight dicts: mixw((w1, a), (w2, b)) with a + b = 1."""
    out = {}
    for w, a in pairs:
        for b, v in w.items():
            out[b] = out.get(b, 0.0) + v * a
    return out


# =============================================================================================== head
# David's head as rows (y, front z, front-side (x, z), side (x, z), back-side (x, z), back z), top to bottom, built from
# the turnaround's front and side outlines (make_design.py david_head_shapes / side_david). Goliath's head is the same
# topology mapped by landmarks (chin, mouth, nose, eye, brow, skull top) and widened/deepened.
DAVID_HEAD = [
    (0.2925, 0.0115, (0.0085, 0.0085), (0.0120, -0.0010), (0.0085, -0.0105), -0.0130),
    (0.2885, 0.0170, (0.0130, 0.0125), (0.0172, -0.0012), (0.0128, -0.0160), -0.0195),
    (0.2830, 0.0200, (0.0150, 0.0150), (0.0190, -0.0015), (0.0148, -0.0190), -0.0225),
    (0.2770, 0.0211, (0.0157, 0.0163), (0.0197, -0.0015), (0.0154, -0.0200), -0.0236),
    (0.2722, 0.0212, (0.0158, 0.0166), (0.0199, -0.0015), (0.0154, -0.0198), -0.0233),
    (0.2680, 0.0196, (0.0153, 0.0154), (0.0199, -0.0015), (0.0150, -0.0190), -0.0222),
    (0.2625, 0.0200, (0.0153, 0.0155), (0.0195, -0.0020), (0.0142, -0.0170), -0.0190),
    (0.2575, 0.0206, (0.0148, 0.0150), (0.0185, -0.0025), (0.0120, -0.0130), -0.0120),
    (0.2530, 0.0214, (0.0137, 0.0147), (0.0168, -0.0022), (0.0100, -0.0095), -0.0090),
    (0.2497, 0.0207, (0.0122, 0.0145), (0.0155, -0.0012), (0.0092, -0.0085), -0.0083),
    (0.2465, 0.0210, (0.0100, 0.0146), (0.0130, 0.0002), (0.0088, -0.0082), -0.0080),
    (0.2435, 0.0197, (0.0074, 0.0153), (0.0104, 0.0028), (0.0087, -0.0080), -0.0080),
    (0.2413, 0.0155, (0.0064, 0.0118), (0.0092, 0.0018), (0.0086, -0.0078), -0.0080),
    (0.2397, 0.0090, (0.0063, 0.0064), (0.0088, 0.0000), (0.0085, -0.0076), -0.0080),
]
DAVID_LAND = dict(top=0.2945, brow=0.2722, eye=0.2672, nose=0.2556, mouth=0.2497, chin=0.241, hw=0.0199, zc=-0.001)


def ellipse_row(y, hx, zf, zb):
    zm = (zf + zb) / 2
    return (y, zf, (0.72 * hx, zm + (zf - zm) * 0.72), (hx, zm), (0.72 * hx, zm + (zb - zm) * 0.72), zb)


def head_rows(ch):
    """Return (rows top->bottom incl. neck, landmarks dict) for one character."""
    if ch == "david":
        rows = list(DAVID_HEAD)
        rows += [ellipse_row(0.2365, 0.0088, 0.0078, -0.0080), ellipse_row(0.2315, 0.0091, 0.0080, -0.0082),
                 ellipse_row(0.2262, 0.0106, 0.0084, -0.0090), ellipse_row(0.2212, 0.0130, 0.0088, -0.0100)]
        L = dict(DAVID_LAND); L["neckTop"] = (0.2385, 0.2500)
        return rows, L
    P = DESIGN["characters"]["goliath"]["proportions"]
    L = dict(top=0.7465, brow=P["browY"], eye=P["eyeY"], nose=P["noseY"], mouth=P["mouthY"], chin=P["chin"],
             hw=0.0405, zc=-0.002)
    D = DAVID_LAND
    srcY = [D["chin"] - 0.01, D["chin"], D["mouth"], D["nose"], D["eye"], D["brow"], D["top"]]
    dstY = [L["chin"] - 0.01 * (L["top"] - L["chin"]) / (D["top"] - D["chin"]), L["chin"], L["mouth"], L["nose"],
            L["eye"], L["brow"], L["top"]]

    def my(y):
        for i in range(len(srcY) - 1):
            if y <= srcY[i + 1] or i == len(srcY) - 2:
                t = (y - srcY[i]) / (srcY[i + 1] - srcY[i]); return lerp(dstY[i], dstY[i + 1], t)
    sx = L["hw"] / D["hw"]; sz = sx * 1.05

    def mz(z): return L["zc"] + (z - D["zc"]) * sz
    rows = []
    for y, zf, fs, s, bs, zb in DAVID_HEAD:
        yn = my(y); t_jaw = smoothstep(0.2575, 0.2465, y)               # 0 above the nose, 1 at the chin
        jw = 1.0 + 0.16 * t_jaw                                       # heavier, squarer jaw
        fsx = fs[0] * sx * (1.0 + 0.22 * t_jaw); ssx = s[0] * sx * jw
        bsx, bz, zbb = bs[0] * sx, mz(bs[1]), mz(zb)
        if y < 0.2585:                                                # thick neck behind the jaw
            bsx = max(bsx, 0.0285); bz = min(bz, -0.0240); zbb = min(zbb, -0.0300)
        brow = 0.0018 * math.exp(-((y - 0.2722) / 0.002) ** 2)        # heavier brow ridge
        rows.append((yn, mz(zf) + brow * sx, (fsx, mz(fs[1]) + brow * sx * 0.7), (ssx, mz(s[1])), (bsx, bz), zbb))
    rows += [ellipse_row(0.638, 0.0290, 0.0255, -0.0310), ellipse_row(0.628, 0.0310, 0.0270, -0.0340),
             ellipse_row(0.618, 0.0380, 0.0290, -0.0380), ellipse_row(0.608, 0.0480, 0.0300, -0.0400)]
    L["neckTop"] = (0.6395, 0.6650)
    return rows, L


def row_ring(row, us):
    y, zf, fs, s, bs, zb = row
    ctrl = [V(0, y, zf), V(fs[0], y, fs[1]), V(s[0], y, s[1]), V(bs[0], y, bs[1]), V(0, y, zb),
            V(-bs[0], y, bs[1]), V(-s[0], y, s[1]), V(-fs[0], y, fs[1])]
    return [cr_closed(ctrl, u) for u in us]


class HeadEval:
    """Target head surface (no subdivision shrink) sampled densely, for hair / beard / ears placement."""
    def __init__(self, rows, L, M=128):
        self.us = [k / M for k in range(M)]; self.M = M
        self.rings = [(r[0], row_ring(r, self.us)) for r in rows]
        self.L = L
        self.top = V(0, L["top"], L["zc"])

    def at(self, u, y):
        R = self.rings
        if y >= R[0][0]:
            t = min(1.0, (y - R[0][0]) / max(1e-6, self.top.y - R[0][0]))
            return self._ring(R[0][1], u).lerp(self.top, t)
        for (y0, a), (y1, b) in zip(R, R[1:]):
            if y1 <= y <= y0:
                t = (y0 - y) / (y0 - y1)
                return self._ring(a, u).lerp(self._ring(b, u), t)
        return self._ring(R[-1][1], u)

    def _ring(self, ring, u):
        x = (u % 1.0) * self.M; i = int(x); f = x - i
        return ring[i % self.M].lerp(ring[(i + 1) % self.M], f)

    def normal(self, u, y):
        e = 1e-3
        p = self.at(u, y)
        du = self.at(u + e, y) - self.at(u - e, y)
        dy = self.at(u, y + 0.0005) - self.at(u, y - 0.0005)
        n = du.cross(dy)
        c = V(0, y, self.L["zc"])
        if n.dot(p - c) < 0:
            n = -n
        return n.normalized() if n.length > 1e-12 else (p - c).normalized()


def build_head(C):
    """Head + neck: one continuous quad cage (front-dense rings), face details displaced after subdivision."""
    rows, L = head_rows(C.ch)
    C.head = HeadEval(rows, L); C.headL = L
    N = 24
    us = front_dense(N, 0.45)
    cg = Cage()
    H = L["top"] - L["chin"]; ytf, ytb = L["neckTop"]

    def wfn(p):
        # head vs neck: a seam under the jaw, rising toward the nape (the head turns on the top of the neck)
        zf = 0.4 * L["hw"]; zb = -0.4 * L["hw"]
        ys = lerp(ytb, ytf, smoothstep(zb, zf, p.z))
        wh = smoothstep(ys - 0.06 * H, ys + 0.06 * H, p.y)
        wn = weigh(p, [("chest", None), ("neck", None)], C.B, C.blend)
        return mixw(({"head": 1.0}, wh), (wn, 1 - wh))
    rings = [cg.ring(row_ring(r, us), wfn) for r in rows]
    cg.fan(rings[0], V(0, L["top"], L["zc"] - 0.0005 * C.S), wfn, "skin")
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin")
    last = rows[-1]
    cg.fan(rings[-1], V(0, last[0] - 0.004 * C.S, (last[1] + last[5]) / 2), wfn, "skin")

    hw = L["hw"]; zc = L["zc"]
    nose_tip_z = C.info["depth"]["noseTipZ"]
    nose_y0 = L["eye"]; nose_tip_y = L["nose"] + 0.10 * H; nose_bot = L["nose"] - 0.012 * H
    g = 1.25 if C.ch == "goliath" else 1.0

    def face_post(pts, nrm):
        out = []
        base_tip = C.head.at(0.0, nose_tip_y).z
        hmax = max(0.0, nose_tip_z - base_tip)
        for p, n in zip(pts, nrm):
            q = p.copy()
            if p.z > zc and n.z > -0.2:
                x, y = p.x, p.y
                ax = abs(x) / hw
                # nose: bridge -> tip -> underside, alae at the base
                if nose_bot - 0.02 * H < y < nose_y0 + 0.03 * H:
                    if y >= nose_tip_y:
                        t = (nose_y0 + 0.03 * H - y) / (nose_y0 + 0.03 * H - nose_tip_y)
                        h = hmax * (0.18 + 0.82 * t ** 1.7); wdt = (0.10 + 0.07 * t) * hw * g
                    else:
                        t = (nose_tip_y - y) / (nose_tip_y - nose_bot + 0.02 * H)
                        h = hmax * max(0.0, 1 - t ** 1.3); wdt = 0.17 * hw * g
                    q.z += h * math.exp(-(abs(x) / wdt) ** 2.4)
                    for sx in (-1, 1):                       # alae (nostril wings)
                        q.z += 0.38 * hmax * math.exp(-((x - sx * 0.17 * hw * g) / (0.085 * hw * g)) ** 2
                                                      - ((y - (L["nose"] + 0.01 * H)) / (0.045 * H)) ** 2)
                    q.z -= 0.18 * hmax * math.exp(-((abs(x) - 0.09 * hw * g) / (0.05 * hw)) ** 2
                                                  - ((y - (L["nose"] - 0.006 * H)) / (0.02 * H)) ** 2)   # nostrils
                # brow ridge over each eye, glabella dip in the middle
                q.z += 0.06 * hw * g * math.exp(-((y - L["brow"]) / (0.045 * H)) ** 2) * smoothstep(0.95, 0.55, ax) \
                    * (1 - 0.45 * math.exp(-(ax / 0.12) ** 2))
                # shallow eye sockets
                for sx in (-1, 1):
                    q.z -= 0.045 * hw * math.exp(-((x - sx * 0.40 * hw) / (0.22 * hw)) ** 2 - ((y - L["eye"]) / (0.06 * H)) ** 2)
                # cheekbones (outward)
                for sx in (-1, 1):
                    k = 0.035 * hw * math.exp(-((x - sx * 0.66 * hw) / (0.22 * hw)) ** 2 - ((y - (L["eye"] - 0.11 * H)) / (0.07 * H)) ** 2)
                    q += n * k
                # lips: upper and lower volume, mouth line, philtrum hint
                ym = L["mouth"]
                lw = math.exp(-(abs(x) / (0.30 * hw)) ** 2.6)
                q.z += 0.050 * hw * lw * math.exp(-((y - (ym + 0.030 * H)) / (0.022 * H)) ** 2)
                q.z += 0.060 * hw * lw * math.exp(-((y - (ym - 0.032 * H)) / (0.024 * H)) ** 2)
                q.z -= 0.030 * hw * math.exp(-(abs(x) / (0.28 * hw)) ** 2.6) * math.exp(-((y - ym) / (0.010 * H)) ** 2)
                # chin ball
                q.z += 0.05 * hw * math.exp(-(abs(x) / (0.25 * hw)) ** 2 - ((y - (L["chin"] + 0.06 * H)) / (0.045 * H)) ** 2)
            out.append(q)
        return out
    if C.ch == "david":
        def cull(p):
            u = math.atan2(p.x, p.z - zc) / (2 * math.pi)
            return p.y > hair_rim(u) + 0.0055 and p.z < 0.75 * hw or p.y > hair_rim(u) + 0.0085 or p.y < 0.2290
    else:
        def cull(p):
            if p.y > 0.7175 or p.y < 0.6320:
                return True
            if 0.6860 < p.y and p.z < -0.012:          # back of the head inside the neck guard
                return True
            return p.y < 0.6545 and p.z > 0.006 and abs(p.x) < 0.030 and p.y > 0.6255
    C.add("face", cg, decal=True, jaw=True, post=face_post, cull=cull)

    # ears: a rim (helix) and a hollow (concha), tilted back, half sunk into the head
    for sx in (-1, 1):
        build_ear(C, sx)


def build_ear(C, sx):
    L = C.headL; H = L["top"] - L["chin"]
    if C.ch == "david":
        ey0, ey1 = DESIGN["characters"]["david"]["proportions"]["earY"]
        eh, ew, et = (ey1 - ey0) * 1.05, 0.0075, 0.0026
    else:
        ey0, ey1 = 0.680, 0.708
        eh, ew, et = (ey1 - ey0) * 0.95, 0.0150, 0.0050
    yc = (ey0 + ey1) / 2
    us = 0.25 if sx > 0 else 0.75
    root = C.head.at(us, yc)
    nrm = V(sx, 0, -0.25).normalized()            # faces outward and a little back
    up = V(0, 1, 0); up = rot_about(up, nrm, math.radians(-sx * 10))
    side = nrm.cross(up).normalized() * sx       # along the head toward the face (+Z-ish)
    if side.z < 0:
        side = -side
    cg = Cage(); wfn = C.w(["head"])
    NA = 10 if C.ch == "david" else 8
    centre = root + nrm * (et * 0.10) + V(0, 0, -0.10 * ew)
    rim = []
    prof = [(1.00, 0.0), (0.88, 0.60), (0.62, 0.45), (0.30, -0.05)]   # (radius frac, height frac) front
    back = [(0.70, -0.65)]
    rings = []
    for rfrac, hfrac in prof:
        pts = []
        for j in range(NA):
            a = 2 * math.pi * j / NA
            r = rfrac
            # C-shaped outline: wider at the top, lobe at the bottom, flatter at the front (tragus side)
            ry = eh / 2 * (1.0 if math.sin(a) > 0 else 0.92)
            rx = ew / 2 * (1.0 + 0.15 * math.sin(a)) * (0.85 if math.cos(a) > 0 else 1.0)
            pts.append(centre + up * (math.sin(a) * ry * r) + side * (math.cos(a) * rx * r) + nrm * (hfrac * et))
        rings.append(cg.ring(pts, wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin", 1)
    cg.fan(rings[-1], centre + nrm * (-0.15 * et), wfn, "skin", 1)
    prev = rings[0]
    for rfrac, hfrac in back:
        pts = [centre + (cg.v[i] - centre) * rfrac + nrm * (hfrac * et) - nrm * ((cg.v[i] - centre).dot(nrm)) * rfrac
               for i in rings[0]]
        r = cg.ring(pts, wfn); cg.bridge(r, prev, "skin", 1); prev = r
    cg.fan(prev, centre - nrm * (et * 1.1), wfn, "skin", 1)
    C.add("ear" + ("L" if sx > 0 else "R"), cg)


# =============================================================================================== limbs
ARM_ANG = [math.radians(75 - 30 * k) for k in range(12)]     # 12 verts: t0..t5 (back of hand side), b5..b0


def section(c, X, Y, ext, ang, e=2.2):
    ca, sa = math.cos(ang), math.sin(ang)
    x = se(ca, e) * (ext[0] if ca >= 0 else ext[1])
    y = se(sa, e) * (ext[2] if sa >= 0 else ext[3])
    return c + X * x + Y * y


def build_arm(C, side, A):
    """Arm (shoulder -> wrist), palm, four fingers (ports in the knuckle end cap) and thumb (port in the palm side)."""
    B = C.B; sd = 1 if side == "L" else -1
    S, E, W, K = B["upperArm" + side][0], B["forearm" + side][0], B["hand" + side][0], B["hand" + side][1]
    d = (E - S).normalized(); bout = V(-d.y, d.x, 0) * sd; Z = V(0, 0, 1)
    X0 = bout; Y0 = d.cross(X0)                       # L: +Z, R: -Z
    LU, LF, LH = (E - S).length, (W - E).length, (K - W).length
    fist = A["fist"]
    alpha_h = 0.0
    if fist:
        alpha_h = math.pi / 2 if Y0.dot(Z) > 0 else -math.pi / 2
    Xh = X0 * math.cos(alpha_h) + Y0 * math.sin(alpha_h); Yh = d.cross(Xh)
    thumb_dir = bout if fist else Z
    thumb_side0 = Yh.dot(thumb_dir) > 0               # thumb on the +Y (i = 0) side of the palm
    cg = Cage(); k12 = kcomp(12)
    warm = C.w([("shoulder" + side, A["shReach"]), "upperArm" + side, "forearm" + side, "hand" + side])
    wpalm = C.w(["forearm" + side, "hand" + side], blend=0.20 * LH)
    # ---- arm rings (base frame X0 = out, Y0 = d x out); forearm twists into the hand frame
    def ext_at(s):
        out, inn = table(A["front"], s); fr, bk = table(A["depth"], s)
        if Y0.dot(Z) < 0:
            fr, bk = bk, fr
        return (out * k12, inn * k12, fr * k12, bk * k12)
    rings = []
    for s in A["stations"]:
        c = S + d * s
        tw = alpha_h * smoothstep(LU + 0.15 * LF, LU + LF, s)
        ext = ext_at(s)
        pts = [section(c, X0, Y0, ext, a + tw, 2.2) for a in ARM_ANG]
        if A.get("elbowBump") and abs(s - LU) < 0.25 * LU:           # olecranon at the back of the elbow
            k = A["elbowBump"] * math.exp(-((s - LU) / (0.10 * LU)) ** 2)
            pts = [p + (-Z if Y0.dot(Z) > 0 else Z) * 0 + (p - c).normalized() * k * max(0.0, -(p - c).normalized().dot(Z))
                   for p in pts]
        rings.append(cg.ring(pts, warm))
    cap_c = S + d * (A["stations"][0] - 0.25 * A["front"][0][1])
    cg.fan(rings[0], cap_c, warm, "skin")
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin")
    # ---- palm: wrist ring (round, hand frame) then rectangular rings t0..t5 / b5..b0
    Wp, Hp = A["palmW"], A["palmH"]
    cols = [0.10, 0.225, 0.225, 0.225, 0.225] if thumb_side0 else [0.225, 0.225, 0.225, 0.225, 0.10]
    ys = [Wp / 2]
    for cw in cols:
        ys.append(ys[-1] - cw * Wp)

    def palm_ring(c, wsc, hsc, dome=0.18):
        pts = []
        for k in range(12):
            i = k if k < 6 else 11 - k
            top = k < 6
            y = ys[i] * wsc
            edge = i in (0, 5)
            xs = Hp / 2 * hsc * (0.62 if edge else 1.0)
            if top:
                xs *= 1.0 + dome * (1 - (y / (Wp / 2)) ** 2) * 0.5
            else:
                xs *= 1.0 - 0.10 * (1 - (y / (Wp / 2)) ** 2)
            pts.append(c + Xh * (xs if top else -xs) + Yh * y * (0.92 if edge else 1.0))
        return pts
    Ww, Hw = A["wristW"], A["wristH"]
    pr = [cg.ring([section(W + d * (0.04 * LH), Xh, Yh, (Hw / 2 * k12, Hw / 2 * k12, Ww / 2 * k12, Ww / 2 * k12), a, 2.4)
                   for a in ARM_ANG], wpalm)]
    pr.append(cg.ring(palm_ring(W + d * (0.30 * LH), 0.97, 1.05), wpalm))
    pr.append(cg.ring(palm_ring(W + d * (0.66 * LH), 1.0, 1.0), wpalm))
    pr.append(cg.ring(palm_ring(W + d * (0.97 * LH), 0.98, 0.95, 0.30), wpalm))
    cg.bridge(rings[-1], pr[0], "skin", 1)
    cg.bridge(pr[0], pr[1], "skin", 1)
    tj = 11 if thumb_side0 else 5                     # side quad between pr[1] and pr[2] becomes the thumb port
    cg.bridge(pr[1], pr[2], "skin", 1, skip=(tj,))
    cg.bridge(pr[2], pr[3], "skin", 1)
    tport = [pr[1][tj], pr[1][(tj + 1) % 12], pr[2][(tj + 1) % 12], pr[2][tj]]
    # ---- fingers out of the knuckle end cap
    ring = pr[3]
    finger_cols = [1, 2, 3, 4] if thumb_side0 else [3, 2, 1, 0]          # index, middle, ring, little
    lens = [0.94, 1.0, 0.94, 0.76]
    wfing = C.w(["hand" + side, "fingers" + side, "fingerTips" + side], blend=0.10 * LH)
    f1 = B["fingers" + side]; f2 = B["fingerTips" + side]
    v1 = f1[1] - f1[0]; v2 = f2[1] - f2[0]
    fw, ft = A["fingerW"], A["fingerT"]
    for c in range(5):
        q = [ring[c], ring[c + 1], ring[11 - (c + 1)], ring[11 - c]]
        if c not in finger_cols:
            cg.face(q, "skin", 1)
            continue
        fi = finger_cols.index(c); lf = lens[fi]
        base = sum((cg.v[i] for i in q), V()) / 4
        spread = Yh * ((base - K).dot(Yh)) * (0.08 if not fist else 0.0)
        pA = base + v1 * (0.12 * lf); pB = base + v1 * lf + spread * 0.5
        pC = pB + v2 * lf + spread
        path = [base, pA, pB, pC]
        st = []
        taper = A.get("fingerTaper", [(0.10, 1.00), (0.33, 0.98), (0.55, 0.96), (0.74, 0.90), (0.92, 0.80)])
        for t, sc in taper:
            pt = cr_open(path, t)
            st.append((pt, (ft / 2 * sc * 1.25, ft / 2 * sc * 1.25, fw / 2 * sc * 1.18, fw / 2 * sc * 1.18)))
        extrude_port(cg, q, st, Xh, wfing, "skin", 1, cap=True, mode="square", cap_len=0.9)
    # ---- thumb
    tb = B["thumb" + side]; tv = tb[1] - tb[0]
    wth = C.w(["hand" + side, "thumb" + side], blend=0.10 * LH)
    tc = sum((cg.v[i] for i in tport), V()) / 4
    out_dir = (Yh if thumb_side0 else -Yh)
    p1 = tc + out_dir * (0.25 * A["thumbW"]) + tv * 0.15
    p2 = tb[1] + out_dir * (0.20 * A["thumbW"])
    if fist:
        p2 = tb[1] + out_dir * (0.10 * A["thumbW"]) + d * (0.10 * LH)
        p3 = p2 + d * (0.10 * LH) - Xh * (0.55 * Hp) - out_dir * (0.85 * A["thumbW"])
    else:
        p3 = p2 + tv.normalized() * (0.30 * LH)
    path = [tc, p1, p2, p3]
    st = []
    for t, sc in ((0.18, 1.05), (0.40, 1.00), (0.62, 0.92), (0.80, 0.88), (0.94, 0.75)):
        st.append((cr_open(path, t), (A["thumbT"] / 2 * sc * 1.25, A["thumbT"] / 2 * sc * 1.25,
                                      A["thumbW"] / 2 * sc * 1.2, A["thumbW"] / 2 * sc * 1.2)))
    extrude_port(cg, tport, st, Xh, wth, "skin", 1, cap=True, mode="square", cap_len=0.9)
    hide = A.get("hideS")
    C.add("arm" + side, cg, cull=(lambda p: (p - S).dot(d) < hide) if hide else None)
    C.hand = getattr(C, "hand", {}); C.hand[side] = dict(Xh=Xh, Yh=Yh, d=d, K=K, W=W, Wp=Wp, Hp=Hp)


def build_leg(C, side, Lg):
    """Leg from inside the clothes down through knee, calf, ankle and the foot (horizontal slices growing forward),
    closed by a flat sole. N = 16, denser at the front (knee, toes)."""
    sd = 1 if side == "L" else -1
    N = Lg.get("N", 16); direct = Lg.get("subdiv", 1) == 0
    k = 1.0 if direct else kcomp(N); us = front_dense(N, 0.40)
    angs = [math.pi / 2 - 2 * math.pi * u for u in us]          # u = 0 -> +Z (front); then toward +X
    X, Y = V(1, 0, 0), V(0, 0, 1)
    cg = Cage()
    wleg = C.w(["thigh" + side, "shin" + side, "foot" + side, "toe" + side])
    toe_out = math.radians(Lg.get("toeOut", 6.0)) * sd
    ank = C.B["foot" + side][0]
    rings = []
    rows = Lg["rows"]                                   # (y, x centre, out, in, front, back, z centre)
    if direct:
        rows = densify(rows, 2)
    for y, xc, out, inn, fr, bk, zc in rows:
        c = V(xc * sd, y, zc)
        ext = (out * k, inn * k, fr * k, bk * k) if sd > 0 else (inn * k, out * k, fr * k, bk * k)
        e = 2.2 if y > Lg["footTop"] else 2.6
        pts = []
        for a in angs:
            p = section(c, X, Y, ext, a, e)
            if y < Lg["footTop"]:                       # toes out: rotate the foot slices about the ankle axis
                tt = smoothstep(Lg["footTop"], Lg["footTop"] - 0.5 * (Lg["footTop"] - 0.0), y)
                q = p - V(ank.x, 0, ank.z)
                q = rot_about(q, V(0, 1, 0), toe_out * tt)
                p = q + V(ank.x, 0, ank.z)
                # footprint: narrow heel, wide ball
                zl = (p.z - ank.z)
                wprof = table(Lg["footprint"], zl)[0]
                p.x = ank.x + (p.x - ank.x) * wprof
            pts.append(p)
        rings.append(cg.ring(pts, wleg))
    top = rows[0]
    cg.fan(rings[0], V(top[1] * sd, top[0] + 0.3 * top[4], top[6]), wleg, Lg["regTop"])

    def regfn(q):
        yy = sum(cg.v[i].y for i in q) / 4
        return Lg["regFoot"] if yy < Lg["regSplit"] else Lg["regTop"]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, None, 0, regfn=regfn)
    cg.grid_cap(rings[-1], wleg, Lg["regFoot"], 0)

    def foot_post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            q = p.copy()
            if q.y < Lg["sole"]:
                q.y = Lg["sole"] * 0.35 + q.y * 0.65 if q.y > 0 else Lg["sole"] * 0.2
            if Lg.get("toes") and q.y < 0.45 * Lg["footTop"]:
                zl = rot_about(q - V(ank.x, 0, ank.z), V(0, 1, 0), -toe_out).z
                if zl > Lg["toeZ"] and n.y > 0.1:
                    xl = rot_about(q - V(ank.x, 0, ank.z), V(0, 1, 0), -toe_out).x * sd
                    g = 0.0
                    for gx in Lg["toes"]:
                        g += math.exp(-((xl - gx) / (0.10 * Lg["toeW"])) ** 2)
                    q.y -= Lg["toeGroove"] * g * smoothstep(Lg["toeZ"], Lg["toeZ"] + 0.004 * C.S, zl)
            for kx, ky, kz, amp, r in Lg.get("bumps", []):          # kneecap, ankle bones (outward)
                dd = (q - V(kx * sd, ky, kz)).length
                if dd < 2.5 * r:
                    q += n * amp * math.exp(-(dd / r) ** 2)
            out.append(q)
        return out
    def cull(p):
        if p.y > Lg.get("hideAbove", 9.0):
            return True
        g = Lg.get("hideGreave")
        if g and g[0] < p.y < g[1]:
            xc, out, inn, fr, bk, zc = table([(r[0],) + tuple(r[1:]) for r in rows], p.y)
            q = V(p.x - xc * sd, 0, p.z - zc)
            if q.length > 1e-9 and q.normalized().z > g[2]:
                return True
        return False
    C.add("leg" + side, cg, post=foot_post, subdiv=Lg.get("subdiv", 1), cull=cull)
    C.leg = getattr(C, "leg", {}); C.leg[side] = dict(rows=rows, angs=angs, k=k, sd=sd)


def leg_point(C, side, y, a, off=0.0):
    """Point on the (target) leg surface at height y and angle a (0 = +X... see build_leg angs), pushed out by off."""
    lg = C.leg[side]; sd = lg["sd"]
    r = table([(row[0],) + tuple(row[1:]) for row in lg["rows"]], y)
    xc, out, inn, fr, bk, zc = r
    ext = (out + off, inn + off, fr + off, bk + off) if sd > 0 else (inn + off, out + off, fr + off, bk + off)
    return section(V(xc * sd, y, zc), V(1, 0, 0), V(0, 0, 1), ext, a, 2.2)


# =============================================================================================== clothing shells
def torso_shell(C, rows, N, port_y, port_ang, sleeves, wtorso, reg, e=2.5, lip_top=None, lip_bot=None, regfn=None,
                sleeve_pc=1, body_pc=0, direct=False):
    """Garment body: rings (y, half width, z front, z back) top -> bottom, uniform angles (j = 0 front, N/4 = +X),
    with a rectangular port of faces on each side (rows with y in port_y, columns within port_ang of the side) out of
    which the sleeves are extruded. sleeves[side] = (stations, weight fn, lip) for extrude_port."""
    cg = Cage(); k = 1.0 if direct else kcomp(N)
    angs = [2 * math.pi * j / N for j in range(N)]

    def ring_pts(y, hw, zf, zb, sc=1.0):
        zc = (zf + zb) / 2; rd = (zf - zb) / 2
        return [V(se(math.sin(a), e) * hw * k * sc, y, zc + se(math.cos(a), e) * rd * k * sc) for a in angs]
    rings = [cg.ring(ring_pts(*r), wtorso) for r in rows]
    pr = [i for i, r in enumerate(rows) if port_y[0] - 1e-6 <= r[0] <= port_y[1] + 1e-6]
    r_top, r_bot = min(pr), max(pr)
    cols = {}
    for side, centre in (("L", math.pi / 2), ("R", 3 * math.pi / 2)):
        cj = [j for j, a in enumerate(angs) if abs(a - centre) <= port_ang + 1e-6]
        cols[side] = (min(cj), max(cj))
    for i in range(len(rings) - 1):
        sk = set()
        if r_top <= i < r_bot:
            for c0, c1 in cols.values():
                sk |= set(range(c0, c1))
        cg.bridge(rings[i], rings[i + 1], reg, body_pc, skip=sk, regfn=regfn)
    for side in ("L", "R"):
        c0, c1 = cols[side]
        loop = [rings[r_top][j] for j in range(c0, c1 + 1)]
        loop += [rings[i][c1] for i in range(r_top + 1, r_bot)]
        loop += [rings[r_bot][j] for j in range(c1, c0 - 1, -1)]
        loop += [rings[i][c0] for i in range(r_bot - 1, r_top, -1)]
        if sleeves.get(side):
            st, wsl, lip = sleeves[side]
            last = extrude_port(cg, loop, st, V(0, 0, 1), wsl, reg, sleeve_pc, cap=False, mode="round")
            if lip:                                          # rolled hem: turn the edge inward
                c = st[-1][0]; Tn = (st[-1][0] - st[-2][0]).normalized()
                pts = [c + (cg.v[i] - c) * lip[0] - Tn * lip[1] for i in last]
                r1 = cg.ring(pts, wsl); cg.bridge(last, r1, reg, sleeve_pc)
                pts = [c + (cg.v[i] - c) * lip[0] - Tn * lip[2] for i in last]
                r2 = cg.ring(pts, wsl); cg.bridge(r1, r2, reg, sleeve_pc)
    if lip_top:
        y, hw, zf, zb = rows[0]
        a = cg.ring(ring_pts(y - lip_top[1], hw, zf, zb, lip_top[0]), wtorso); cg.bridge(rings[0], a, reg, body_pc)
        b = cg.ring(ring_pts(y - lip_top[2], hw, zf, zb, lip_top[0]), wtorso); cg.bridge(a, b, reg, body_pc)
    if lip_bot:
        y, hw, zf, zb = rows[-1]
        a = cg.ring(ring_pts(y + lip_bot[1], hw, zf, zb, lip_bot[0]), wtorso); cg.bridge(rings[-1], a, reg, body_pc, regfn=regfn)
        b = cg.ring(ring_pts(y + lip_bot[2], hw, zf, zb, lip_bot[0]), wtorso); cg.bridge(a, b, reg, body_pc, regfn=regfn)
    return cg


def resample_rows(rows, ys):
    """Rows (y, ...) sampled at the given heights with Catmull-Rom through the original rows (top -> bottom)."""
    R = list(rows); out = []
    for y in ys:
        for i in range(len(R) - 1):
            if R[i + 1][0] <= y <= R[i][0]:
                t = (R[i][0] - y) / (R[i][0] - R[i + 1][0])
                p0, p3 = R[max(i - 1, 0)], R[min(i + 2, len(R) - 1)]
                vals = [cr(a, b, c, d, t) for a, b, c, d in zip(p0, R[i], R[i + 1], p3)]
                vals[0] = y; out.append(tuple(vals)); break
    return out


def shell_point(rows, y, a, off=0.0, e=2.5):
    """Point on a garment's target surface (rows as in torso_shell) at height y, angle a (0 = front, + toward +X)."""
    hw, zf, zb = table(rows, y)
    zc = (zf + zb) / 2; rd = (zf - zb) / 2
    return V(se(math.sin(a), e) * (hw + off), y, zc + se(math.cos(a), e) * (rd + off))


def band_loop(cg, pts, nrms, wdir, half_w, th, wfn, reg, pc=0):
    """Closed strap/band along a closed loop of surface points: 4 rings (inner-low, outer-low, outer-high, inner-high)."""
    rs = []
    for s_w, s_t in ((-1, 0.0), (-1, 1.0), (1, 1.0), (1, 0.0)):
        rs.append(cg.ring([p + wd * (s_w * half_w) + n * (s_t * th) for p, n, wd in zip(pts, nrms, wdir)], wfn))
    for a, b in zip(rs, rs[1:] + rs[:1]):
        cg.bridge(a, b, reg, pc)
    return rs


def strip(cg, path, nrms, half_ws, th, wfn, reg, pc=0, cap=True):
    """Open flat strip (ribbon with thickness) along a path."""
    rings = []
    for i, p in enumerate(path):
        t = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        n = perp(nrms[i], t); w = t.cross(n).normalized() * half_ws[i]
        rings.append(cg.ring([p - w, p - w + n * th, p + w + n * th, p + w], wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    if cap:
        cg.face(tuple(reversed(rings[0])), reg, pc); cg.face(tuple(rings[-1]), reg, pc)
    return rings


def lathe_y(cg, centre, prof, N, wfn, reg, pc=0, e=2.0, zscale=1.0, top_pole=True, bot_pole=True, regs=None):
    """Surface of revolution about the y axis: prof = [(y offset, radius)], optional per-ring region list."""
    rings = []
    for i, (dy, r) in enumerate(prof):
        rings.append(cg.ring([centre + V(se(math.sin(2 * math.pi * j / N), e) * r, dy,
                                         se(math.cos(2 * math.pi * j / N), e) * r * zscale) for j in range(N)], wfn))
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        cg.bridge(a, b, regs[i] if regs else reg, pc)
    if bot_pole:
        cg.fan(rings[0], centre + V(0, prof[0][0] - 0.3 * prof[0][1], 0), wfn, regs[0] if regs else reg, pc)
    if top_pole:
        cg.fan(rings[-1], centre + V(0, prof[-1][0] + 0.3 * prof[-1][1], 0), wfn, regs[-1] if regs else reg, pc)
    return rings


def lathe_z(cg, centre, prof, N, wfn, reg_fn, pc=0):
    """Surface of revolution about +Z through centre: prof = [(z offset, radius)], radius 0 ends become poles."""
    rings, poles = [], []
    for dz, r in prof:
        if r <= 0:
            rings.append(None); poles.append(centre + V(0, 0, dz)); continue
        rings.append(cg.ring([centre + V(math.cos(2 * math.pi * j / N) * r, math.sin(2 * math.pi * j / N) * r, dz)
                              for j in range(N)], wfn)); poles.append(None)
    for i in range(len(prof) - 1):
        a, b = rings[i], rings[i + 1]
        if a and b:
            cg.bridge(a, b, reg_fn(prof[i], prof[i + 1]), pc)
        elif a is None and b:
            cg.fan(b, poles[i], wfn, reg_fn(prof[i], prof[i + 1]), pc)
        elif b is None and a:
            cg.fan(a, poles[i + 1], wfn, reg_fn(prof[i], prof[i + 1]), pc)
    return rings


# =============================================================================================== David
D_ARM = dict(
    fist=False, shReach=0.011,
    stations=[-0.004, 0.006, 0.020, 0.034, 0.047, 0.054, 0.061, 0.072, 0.084, 0.0955],
    front=[(-0.004, 0.0060, 0.0060), (0.004, 0.0080, 0.0072), (0.012, 0.0086, 0.0076), (0.026, 0.0077, 0.0084),
           (0.044, 0.0067, 0.0068), (0.053, 0.0062, 0.0063), (0.062, 0.0077, 0.0071), (0.079, 0.0061, 0.0057),
           (0.0955, 0.0046, 0.0045)],
    depth=[(-0.004, 0.0062, 0.0062), (0.008, 0.0068, 0.0068), (0.020, 0.0062, 0.0066), (0.053, 0.0049, 0.0055), (0.064, 0.0058, 0.0055),
           (0.0955, 0.0036, 0.0034)],
    elbowBump=0.0010,
    hideS=0.011, palmW=0.0122, palmH=0.0048, wristW=0.0092, wristH=0.0060, fingerW=0.0029, fingerT=0.0026,
    thumbW=0.0031, thumbT=0.0028)

D_LEG = dict(
    rows=[  # (y, x centre, out, in, front, back, z centre)
        (0.126, 0.0178, 0.0128, 0.0095, 0.0094, 0.0100, 0.0010),
        (0.106, 0.0184, 0.0110, 0.0088, 0.0080, 0.0085, 0.0022),
        (0.094, 0.0185, 0.0096, 0.0082, 0.0072, 0.0076, 0.0030),
        (0.086, 0.0185, 0.0086, 0.0077, 0.0070, 0.0068, 0.0033),
        (0.080, 0.0186, 0.0084, 0.0076, 0.0064, 0.0070, 0.0030),
        (0.072, 0.0188, 0.0090, 0.0083, 0.0058, 0.0084, 0.0016),
        (0.062, 0.0189, 0.0094, 0.0086, 0.0056, 0.0094, 0.0006),
        (0.050, 0.0188, 0.0086, 0.0074, 0.0053, 0.0082, 0.0000),
        (0.038, 0.0184, 0.0068, 0.0058, 0.0050, 0.0062, -0.0004),
        (0.028, 0.0182, 0.0055, 0.0050, 0.0046, 0.0052, -0.0006),
        (0.020, 0.0181, 0.0056, 0.0053, 0.0048, 0.0050, -0.0006),
        (0.0145, 0.0180, 0.0054, 0.0052, 0.0110, 0.0066, 0.0020),
        (0.0100, 0.0180, 0.0064, 0.0060, 0.0170, 0.0080, 0.0045),
        (0.0062, 0.0180, 0.0076, 0.0072, 0.0215, 0.0088, 0.0072),
        (0.0036, 0.0180, 0.0084, 0.0080, 0.0230, 0.0090, 0.0118),
        (0.0014, 0.0180, 0.0082, 0.0078, 0.0225, 0.0086, 0.0128)],
    footTop=0.0160, sole=0.0007, regTop="skin", regFoot="skin", regSplit=-1, N=18, subdiv=0, hideAbove=0.106,
    footprint=[(-0.012, 0.70), (-0.004, 0.78), (0.006, 0.90), (0.018, 1.05), (0.026, 1.10), (0.034, 0.95), (0.040, 0.70)],
    toes=[-0.0060, -0.0021, 0.0012, 0.0042], toeW=0.018, toeZ=0.0275, toeGroove=0.0007, toeOut=6.0,
    bumps=[(0.0186, 0.084, 0.0098, 0.0011, 0.0035),                       # kneecap
           (0.0240, 0.0185, -0.0004, 0.0008, 0.0022), (0.0128, 0.0195, -0.0004, 0.0008, 0.0022)])  # ankle bones


def build_david(C):
    P = C.P; B = C.B
    build_head(C)
    for s in "LR":
        A = dict(D_ARM)
        if s == "R":
            A["fist"] = True
        build_arm(C, s, A)
        build_leg(C, s, D_LEG)
    build_hair(C)
    # ---- tunic: torso with sleeve ports, skirt folds, rolled hems
    T = [(0.2305, 0.0098, 0.0088, -0.0102), (0.2287, 0.0172, 0.0108, -0.0122), (0.2262, 0.0278, 0.0126, -0.0132),
         (0.2152, 0.0328, 0.0139, -0.0137), (0.2040, 0.0312, 0.0141, -0.0136), (0.1920, 0.0309, 0.0133, -0.0121),
         (0.1790, 0.0285, 0.0121, -0.0102), (0.1680, 0.0300, 0.0140, -0.0121), (0.1530, 0.0323, 0.0166, -0.0151),
         (0.1390, 0.0346, 0.0190, -0.0180), (0.1170, 0.0392, 0.0218, -0.0204), (0.0975, 0.0424, 0.0234, -0.0220)]
    C.tunic_rows = T
    hipY, hemY, hipX = P["hipY"], P["tunicHemY"], P["hipX"]

    def skirt(w, p):
        if p.y >= hipY:
            return w
        tt = min(1.0, (hipY - p.y) / (hipY - hemY)); sL = min(1.0, max(0.0, 0.5 + p.x / (3.0 * hipX)))
        kk = 0.65 * tt
        w = {b: v * (1 - kk) for b, v in w.items()}
        w["thighL"] = w.get("thighL", 0) + kk * sL; w["thighR"] = w.get("thighR", 0) + kk * (1 - sL)
        return w
    wt0 = C.w(["hips", "spine", "chest", ("neck", 0.008), ("shoulderL", 0.012), ("shoulderR", 0.012)])

    def wtorso(p): return skirt(wt0(p), p)
    sleeves = {}
    for s in "LR":
        S, E = B["upperArm" + s][0], B["forearm" + s][0]; d = (E - S).normalized()
        wsl = C.w(["chest", "shoulder" + s, "upperArm" + s])
        st = [(S + d * 0.000, (0.0096, 0.0096, 0.0092, 0.0092)), (S + d * 0.006, (0.0097, 0.0097, 0.0094, 0.0094)),
              (S + d * 0.014, (0.0094, 0.0094, 0.0093, 0.0093)), (S + d * 0.0225, (0.0090, 0.0090, 0.0090, 0.0090))]
        sleeves[s] = (st, wsl, (0.88, 0.0004, 0.0035))
    ys = [0.2305, 0.2296, 0.2287, 0.2275, 0.2262] + [0.2262 - (0.2262 - 0.2040) * i / 4 for i in range(1, 5)] \
        + [0.2040 - (0.2040 - 0.0975) * i / 18 for i in range(1, 19)]
    TT = resample_rows(T, ys)
    cg = torso_shell(C, TT, 40, (0.2040, 0.2262), math.radians(30), sleeves, wtorso, "tunic", e=2.5,
                     lip_top=(0.90, -0.0004, 0.0030), lip_bot=(0.95, 0.0002, 0.0045), direct=True)

    def tunic_post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            q = p.copy()
            if p.y < 0.168:                              # skirt folds, deeper toward the hem
                a = math.atan2(p.x, p.z + 0.0005)
                amp = 0.0012 * smoothstep(0.168, 0.100, max(p.y, 0.100))
                hn = V(p.x, 0, p.z + 0.0005).normalized()
                q += hn * amp * (math.cos(12 * a + 0.4) + 0.35 * math.cos(7 * a))
            if 0.190 < p.y < 0.214 and p.z > 0:          # a soft pull fold under the strap
                q.z -= 0.0004 * math.exp(-(((p.x + 0.012) - (0.214 - p.y) * 0.6) / 0.004) ** 2)
            out.append(q)
        return out
    C.add("tunic", cg, post=tunic_post, subdiv=0)
    # ---- sash (wrapped band) with a knot and two hanging ends at his left hip
    cg = Cage(); wb = C.w(["hips", "spine"])
    y0, y1 = P["beltY"]
    N = 48; angs = [2 * math.pi * j / N for j in range(N)]
    rings = []
    for y, off in ((y0, 0.0002), (y0 + 0.0005, 0.0012), (y0 + 0.0040, 0.0015), (y1 - 0.0005, 0.0012), (y1, 0.0002)):
        rings.append(cg.ring([shell_point(T, y, a, off * 1.0 + 0.0006) for a in angs], wb))
    for a, b in zip(rings, rings[1:] + rings[:1]):
        cg.bridge(a, b, "belt", 0)
    C.add("sash", cg, subdiv=0)
    cg = Cage()
    kc = V(0.0215, 0.1765, 0); kc.z = shell_point(T, 0.1765, math.asin(min(1, 0.0215 / 0.0290)), 0.0)[2] + 0.0028
    lathe_y(cg, kc, [(-0.0030, 0.0026), (0.0, 0.0046), (0.0030, 0.0026)], 8, wb, "belt", 1, e=2.6, zscale=0.55)
    for path in (((0.0205, 0.1730), (0.0220, 0.1640), (0.0230, 0.1560), (0.0242, 0.1490)),
                 ((0.0248, 0.1730), (0.0280, 0.1650), (0.0300, 0.1580), (0.0312, 0.1535))):
        pp, nn = [], []
        for x, y in path:
            a = math.asin(max(-1, min(1, x / (table(T, y)[0] + 0.004))))
            p = shell_point(T, y, a, 0.0018); pp.append(p); nn.append((p - V(0, y, 0)).normalized())
        strip(cg, pp, nn, [0.0026, 0.0030, 0.0032, 0.0030], 0.0007, wb, "belt", 1)
    C.add("sashKnot", cg)
    # ---- shepherd's bag: strap from the right shoulder over the chest to the left hip, bag at the front of the hip
    cg = Cage(); wst = C.w(["chest", "spine", "hips"])
    path = []
    fr = [(-0.0210, 0.2272), (-0.0120, 0.2170), (-0.0010, 0.2040), (0.0110, 0.1900), (0.0210, 0.1760), (0.0275, 0.1640)]
    for x, y in fr:
        a = math.asin(max(-1, min(1, x / (table(T, y)[0] + 0.002))))
        path.append(shell_point(T, y, a, 0.0012))
    for x, y in reversed(fr):
        a = math.pi - math.asin(max(-1, min(1, x / (table(T, y)[0] + 0.002))))
        path.append(shell_point(T, y, a, 0.0012))
    top = V(-0.0225, 0.2300, -0.0005)
    path.append(top)
    nrms = []
    for p in path:
        ax = V(0, min(p.y, 0.212), 0)
        n = (p - ax); n.y *= 1.0 if p.y > 0.222 else 0.2; nrms.append(n.normalized())
    tang = [(path[(i + 1) % len(path)] - path[i - 1]).normalized() for i in range(len(path))]
    wdir = [t.cross(n).normalized() for t, n in zip(tang, nrms)]
    band_loop(cg, path, nrms, wdir, 0.0032, 0.0008, wst, "bag", 0)
    C.add("strap", cg, subdiv=1)
    cg = Cage(); wbag = C.w(["hips", "spine"])
    bc = V(0.0300, 0.1530, 0); bc.z = shell_point(T, 0.153, math.asin(0.0300 / 0.0335), 0.0)[2] + 0.0072
    prof = [(-0.0105, 0.0085), (-0.0080, 0.0124), (-0.0010, 0.0130), (0.0070, 0.0124), (0.0118, 0.0080)]
    rings = []
    for dy, r in prof:
        rings.append(cg.ring([bc + V(se(math.sin(2 * math.pi * j / 12), 3.2) * r, dy,
                                     se(math.cos(2 * math.pi * j / 12), 3.2) * r * 0.62 - 0.0005) for j in range(12)], wbag))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "bag", 0)
    cg.grid_cap(rings[0], wbag, "bag", 0); cg.grid_cap(rings[-1], wbag, "bag", 0)
    C.add("bag", cg)
    cg = Cage()
    # flap: curved plate over the top front, rounded lower edge, toggle
    fl = []
    NX = 7
    for i in range(NX):
        x = -0.0128 + 0.0256 * i / (NX - 1)
        xn = x / 0.0128
        edge = 0.0010 - 0.0042 * (1 - xn * xn) ** 0.6           # rounded lower edge, lowest in the middle
        col = []
        for yy, zz in ((0.0126, -0.0040), (0.0130, 0.0030), (0.0100, 0.0084), (0.0050, 0.0088), (edge, 0.0086)):
            col.append(bc + V(x * (1.04 if yy > 0.012 else 1.06), yy, zz))
        fl.append(col)
    idx = [[cg.add(p, wbag) for p in col] for col in fl]
    for i in range(NX - 1):
        for j in range(len(fl[0]) - 1):
            cg.face((idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1]), "bag", 1)
    C.add("bagFlap", cg, solidify=0.0006)
    cg = Cage()
    lathe_y(cg, bc + V(0, -0.0020, 0.0094), [(-0.0012, 0.0008), (0.0012, 0.0008)], 6, wbag, "bag", 1)
    C.add("bagToggle", cg, subdiv=0)
    # ---- sandals: soles + ankle strap + instep strap
    for s in "LR":
        sd = 1 if s == "L" else -1
        cg = Cage(); ws = C.w([("foot" + s, None), ("toe" + s, None), ("shin" + s, 0.006)])
        lg = C.leg[s]
        bot = [leg_point_full(C, s, 0.0014, a) for a in [math.pi / 2 - 2 * math.pi * u for u in front_dense(12, 0.35)]]
        cen = sum(bot, V()) / len(bot)
        rr = []
        for scl, y in ((0.78, 0.0000), (1.07, 0.0001), (1.09, 0.0010), (1.07, 0.0019), (0.80, 0.0021)):
            rr.append(cg.ring([V(cen.x + (p.x - cen.x) * scl, y, cen.z + (p.z - cen.z) * scl) for p in bot], ws))
        for a, b in zip(rr, rr[1:]):
            cg.bridge(a, b, "sandals", 0)
        cg.grid_cap(rr[0], ws, "sandals", 0); cg.grid_cap(rr[-1], ws, "sandals", 0)
        C.add("sandal" + s, cg)
        cg = Cage()
        # ankle strap
        ank = [leg_point_full(C, s, 0.0175, 2 * math.pi * j / 24, 0.0004) for j in range(24)]
        ac = sum(ank, V()) / len(ank)
        band_loop(cg, ank, [(p - ac).normalized() for p in ank], [V(0, 1, 0)] * len(ank), 0.0011, 0.0006, ws, "sandals", 1)
        # instep strap: a loop across the foot at mid-instep (from the sole up over the top and back)
        loop = instep_loop(C, s, 0.45, 0.0005)
        lc = sum(loop, V()) / len(loop)
        nr = [(p - lc).normalized() for p in loop]
        ax = rot_about(V(0, 0, 1), V(0, 1, 0), math.radians(6.0) * sd)
        band_loop(cg, loop, nr, [ax] * len(loop), 0.0012, 0.0006, ws, "sandals", 1)
        C.add("sandalStraps" + s, cg, subdiv=0)
    # ---- sling: two cords as one band from the bottom of the right fist down to the pouch; pouch; stone
    sl = DESIGN["characters"]["david"]["props"]["sling"]
    c1, c2, cp = B["slingCord1"], B["slingCord2"], B["slingPouch"]
    top = c1[0] + V(0, 0.0040, 0); bot = cp[0]
    cg = Cage(); wc = C.w(["handR", "slingCord1", "slingCord2"], blend=0.006)
    NS = 7; pts, nrm, hw = [], [], []
    for i in range(NS):
        t = i / (NS - 1)
        p = top.lerp(bot, t) + V(0, 0, 0.0012 * math.sin(t * math.pi))
        pts.append(p); nrm.append(V(0, 0, 1)); hw.append(lerp(sl["cordBandWidth"][0], sl["cordBandWidth"][1], t ** 1.2) / 2)
    rings = strip(cg, pts, nrm, hw, 0.0012, wc, "sling", 0, cap=False)
    cg.face(tuple(reversed(rings[0])), "sling", 0)
    C.add("slingCords", cg)
    cg = Cage(); wp = C.w(["slingCord2", "slingPouch"], blend=0.004)
    pc = V(bot.x, (cp[0].y + cp[1].y) / 2 - 0.0005, -0.0004)
    pw, ph, pd = sl["pouch"]
    grid = []
    NU, NV = 7, 5
    for i in range(NU):
        u = -1 + 2 * i / (NU - 1); row = []
        for j in range(NV):
            v = -1 + 2 * j / (NV - 1)
            r2 = min(1.0, u * u + v * v * 0.95)
            z = -pd * 0.55 * (1 - r2) + 0.0015 * (1 - abs(u))     # cradle bulging back, lip toward the viewer
            row.append(pc + V(u * pw / 2 * math.sqrt(max(0.0, 1 - 0.35 * v * v)), v * ph / 2, z))
        grid.append(row)
    idx = [[cg.add(p, wp) for p in row] for row in grid]
    for i in range(NU - 1):
        for j in range(NV - 1):
            cg.face((idx[i][j], idx[i][j + 1], idx[i + 1][j + 1], idx[i + 1][j]), "sling", 1)
    C.add("slingPouch", cg, solidify_faces=0.0009)
    st = B["stone"][0]
    cg = Cage()
    rnd = random.Random(7)
    lumps = [(V(rnd.uniform(-1, 1), rnd.uniform(-1, 1), rnd.uniform(-1, 1)).normalized(), rnd.uniform(-0.05, 0.06))
             for _ in range(6)]

    def pebble(p):
        q = p - st; n = q.normalized()
        return st + q * (1 + sum(a * max(0.0, n.dot(l)) ** 3 for l, a in lumps))
    prof = [(-0.0050, 0.0), (-0.0036, 0.0042), (0.0, 0.0060), (0.0036, 0.0042), (0.0050, 0.0)]
    rings = []
    for dz, r in prof[1:-1]:
        rings.append(cg.ring([pebble(st + V(math.cos(2 * math.pi * j / 10) * r, math.sin(2 * math.pi * j / 10) * r * 0.86,
                                             dz * 0.85)) for j in range(10)], None))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "stone", 0)
    cg.fan(rings[0], pebble(st + V(0, 0, prof[0][0] * 0.85)), None, "stone", 0)
    cg.fan(rings[-1], pebble(st + V(0, 0, prof[-1][0] * 0.85)), None, "stone", 0)
    C.add("stone", cg, rigid="stone")


def leg_ring_pts(C, side, y, off=0.0):
    lg = C.leg[side]
    return [leg_point_full(C, side, y, a, off) for a in lg["angs"]]


def leg_point_full(C, side, y, a, off=0.0):
    """Like leg_point but includes the foot transforms (toe-out, footprint) used in build_leg."""
    lg = C.leg[side]; sd = lg["sd"]
    Lg = D_LEG if C.ch == "david" else G_LEG
    rows = lg["rows"]
    r = table([(row[0],) + tuple(row[1:]) for row in rows], y)
    xc, out, inn, fr, bk, zc = r
    ext = (out + off, inn + off, fr + off, bk + off) if sd > 0 else (inn + off, out + off, fr + off, bk + off)
    e = 2.2 if y > Lg["footTop"] else 2.6
    p = section(V(xc * sd, y, zc), V(1, 0, 0), V(0, 0, 1), ext, a, e)
    ank = C.B["foot" + side][0]
    if y < Lg["footTop"]:
        tt = smoothstep(Lg["footTop"], Lg["footTop"] * 0.5, y)
        q = rot_about(p - V(ank.x, 0, ank.z), V(0, 1, 0), math.radians(Lg.get("toeOut", 6.0)) * sd * tt)
        p = q + V(ank.x, 0, ank.z)
        wprof = table(Lg["footprint"], p.z - ank.z)[0]
        p.x = ank.x + (p.x - ank.x) * wprof
    return p


def foot_slice(C, side, y, n=48):
    return [leg_point_full(C, side, y, 2 * math.pi * j / n) for j in range(n)]


def inside_xz(poly, x, z):
    c = False; n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a.z > z) != (b.z > z):
            xi = a.x + (z - a.z) / (b.z - a.z) * (b.x - a.x)
            if x < xi:
                c = not c
    return c


def instep_loop(C, side, frac, off):
    """Arc over the foot in the vertical plane z = const at `frac` of the foot length (heel -> toe), found by marching
    rays from the middle of the sole outward until they leave the foot; pushed out by `off`."""
    Lg = D_LEG if C.ch == "david" else G_LEG
    bot = foot_slice(C, side, 0.0014)
    zmin = min(p.z for p in bot); zmax = max(p.z for p in bot)
    zt = lerp(zmin, zmax, frac)
    near = [p for p in bot if abs(p.z - zt) < 0.25 * (zmax - zmin)]
    cx = (min(p.x for p in near) + max(p.x for p in near)) / 2
    o = V(cx, 0.0010, zt)
    cache = {}

    def inside(p):
        if p.y > Lg["footTop"] or p.y < 0.0:
            return False
        key = round(p.y / 0.0004)
        if key not in cache:
            cache[key] = foot_slice(C, side, key * 0.0004)
        return inside_xz(cache[key], p.x, p.z)
    pts = []
    for i in range(13):
        psi = math.pi * i / 12
        dirn = V(math.cos(psi), math.sin(psi) * 1.0, 0)
        r = 0.0
        while r < 0.05 and inside(o + dirn * (r + 0.0002)):
            r += 0.0002
        pts.append(o + dirn * (r + off))
    return pts


HAIR_RIM = [(0.00, 0.2805), (0.05, 0.2812), (0.09, 0.2795), (0.13, 0.2745), (0.17, 0.2690), (0.205, 0.2615),
            (0.225, 0.2690), (0.25, 0.2722), (0.275, 0.2700), (0.30, 0.2605), (0.36, 0.2565), (0.50, 0.2550)]


def hair_rim(u, lobes=False):
    uu = u % 1.0; uu = uu if uu <= 0.5 else 1.0 - uu
    y = table(HAIR_RIM, uu)[0]
    if lobes and uu < 0.20:                                 # curls hanging over the forehead
        y -= 0.0011 * (0.5 + 0.5 * math.cos(2 * math.pi * u * 18)) * smoothstep(0.20, 0.12, uu)
    return y


def build_hair(C):
    """David's curly hair: a shell over the skull whose rim follows the hairline (fringe, sideburns, nape) and whose
    outer surface carries curls; the rim is tucked into the skin so there is no visible edge."""
    Hd = C.head; L = C.headL
    rim = lambda u: hair_rim(u, True)
    NU, NV = 36, 8
    cg = Cage(); wfn = C.w(["head"])
    rnd = random.Random(3)
    curls = []
    for i in range(120):                               # curl centres (Fibonacci sphere, top-biased)
        yv = 1 - (i + 0.5) / 120 * 1.25
        r = math.sqrt(max(0.0, 1 - yv * yv)); th = i * 2.39996
        curls.append((V(r * math.cos(th), yv, r * math.sin(th)).normalized(), rnd.uniform(0.75, 1.15)))
    Hc = V(0, 0.270, L["zc"] - 0.001)

    def thick(u, y, rimy):
        uu = u % 1.0; uu = uu if uu <= 0.5 else 1.0 - uu
        base = lerp(0.0046, 0.0060, smoothstep(0.270, 0.286, y)) - 0.0012 * smoothstep(0.288, 0.294, y)  # volume, top = 0.300
        base = lerp(base, 0.0046, smoothstep(0.30, 0.5, uu) * 0.5)
        if uu < 0.15:
            base = lerp(base, 0.0036, smoothstep(0.285, 0.278, y))           # fringe sits close to the forehead
        return base * smoothstep(rimy - 0.0005, rimy + 0.0040, y) + 0.0008
    us = [k / NU for k in range(NU)]
    rows = []
    for j in range(NV + 1):
        row = []
        for u in us:
            ry = rim(u)
            t = j / NV
            y = lerp(ry, L["top"] + 0.001, t ** 0.85)
            if j == 0:
                p = Hd.at(u, ry) - Hd.normal(u, ry) * 0.0006       # tucked under the skin
            else:
                p = Hd.at(u, min(y, L["top"] - 0.0002))
                n = (p - Hc).normalized()
                p = p + n * thick(u, y, ry)
            row.append(p)
        rows.append(cg.ring(row, wfn))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, "hair", 0)
    cg.fan(rows[-1], V(0, 0.3002, L["zc"] - 0.002), wfn, "hair", 0)

    def hair_post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            q = p - Hc; dirn = q.normalized()
            bump = 0.0
            for cdir, s in curls:
                dd = (dirn - cdir).length
                if dd < 0.45:
                    bump += s * math.exp(-(dd / 0.125) ** 2)
            rimy = rim(math.atan2(p.x, p.z) / (2 * math.pi))
            fade = smoothstep(rimy + 0.0005, rimy + 0.004, p.y)
            out.append(p + dirn * (0.0024 * min(bump, 1.25) - 0.0008) * fade)
        return out
    C.add("hair", cg, post=hair_post)


# =============================================================================================== Goliath
G_ARM = dict(
    fist=True, shReach=0.028,
    stations=[0.000, 0.022, 0.060, 0.100, 0.127, 0.141, 0.160, 0.200, 0.250],
    fingerTaper=[(0.12, 1.00), (0.40, 1.00), (0.68, 0.94), (0.90, 0.82)],
    front=[(0.000, 0.0170, 0.0170), (0.012, 0.0250, 0.0222), (0.026, 0.0290, 0.0255), (0.065, 0.0250, 0.0275),
           (0.115, 0.0200, 0.0215), (0.138, 0.0190, 0.0195), (0.168, 0.0232, 0.0216), (0.208, 0.0180, 0.0165),
           (0.250, 0.0150, 0.0140)],
    depth=[(0.000, 0.0200, 0.0200), (0.020, 0.0262, 0.0262), (0.050, 0.0270, 0.0260), (0.138, 0.0195, 0.0210), (0.173, 0.0230, 0.0215),
           (0.250, 0.0150, 0.0140)],
    elbowBump=0.0030,
    hideS=0.038, palmW=0.0395, palmH=0.0175, wristW=0.0300, wristH=0.0200, fingerW=0.0096, fingerT=0.0092,
    thumbW=0.0104, thumbT=0.0094)

G_LEG = dict(
    rows=[  # (y, x centre, out, in, front, back, z centre)
        (0.300, 0.0522, 0.0372, 0.0282, 0.0310, 0.0322, 0.0030),
        (0.270, 0.0532, 0.0345, 0.0268, 0.0292, 0.0296, 0.0048),
        (0.245, 0.0540, 0.0305, 0.0244, 0.0265, 0.0250, 0.0065),
        (0.222, 0.0540, 0.0262, 0.0222, 0.0245, 0.0222, 0.0078),
        (0.207, 0.0542, 0.0248, 0.0216, 0.0232, 0.0220, 0.0078),
        (0.190, 0.0548, 0.0268, 0.0230, 0.0215, 0.0262, 0.0050),
        (0.165, 0.0550, 0.0275, 0.0235, 0.0205, 0.0295, 0.0025),
        (0.130, 0.0545, 0.0255, 0.0205, 0.0190, 0.0270, 0.0005),
        (0.100, 0.0535, 0.0215, 0.0180, 0.0170, 0.0205, -0.0010),
        (0.075, 0.0528, 0.0178, 0.0158, 0.0158, 0.0168, -0.0020),
        (0.062, 0.0525, 0.0186, 0.0170, 0.0168, 0.0190, -0.0020),
        (0.048, 0.0522, 0.0194, 0.0180, 0.0195, 0.0200, -0.0010),
        (0.036, 0.0520, 0.0204, 0.0188, 0.0290, 0.0220, 0.0040),
        (0.026, 0.0520, 0.0226, 0.0210, 0.0430, 0.0248, 0.0105),
        (0.016, 0.0520, 0.0250, 0.0234, 0.0560, 0.0258, 0.0190),
        (0.008, 0.0520, 0.0262, 0.0246, 0.0620, 0.0264, 0.0235),
        (0.0025, 0.0520, 0.0262, 0.0246, 0.0630, 0.0262, 0.0245)],
    footTop=0.040, sole=0.0015, regTop="skin", regFoot="feet", regSplit=0.0625, N=18, subdiv=0, hideAbove=0.282,
    hideGreave=(0.066, 0.190, -0.30),
    footprint=[(-0.030, 0.78), (-0.010, 0.86), (0.020, 0.96), (0.050, 1.06), (0.070, 1.04), (0.085, 0.86), (0.095, 0.62)],
    toes=None, toeOut=5.0,
    bumps=[(0.0545, 0.212, 0.0300, 0.0035, 0.0090)])


def build_goliath(C):
    P = C.P; B = C.B
    build_head(C)
    for s in "LR":
        build_arm(C, s, dict(G_ARM))
        build_leg(C, s, G_LEG)
    build_beard(C)
    # ---- scale armour coat (torso + short scale sleeves)
    A = [(0.6410, 0.0345, 0.0300, -0.0430), (0.6370, 0.0600, 0.0420, -0.0560), (0.6300, 0.0880, 0.0540, -0.0640),
         (0.6200, 0.1080, 0.0620, -0.0700), (0.5900, 0.1170, 0.0730, -0.0745), (0.5600, 0.1040, 0.0790, -0.0755),
         (0.5250, 0.0995, 0.0805, -0.0735), (0.4900, 0.0900, 0.0750, -0.0690), (0.4500, 0.0830, 0.0705, -0.0680),
         (0.4150, 0.0890, 0.0725, -0.0720), (0.3850, 0.0960, 0.0790, -0.0780), (0.3620, 0.1000, 0.0830, -0.0810)]
    C.armour_rows = A
    wt = C.w(["hips", "spine", "chest", ("neck", 0.02), ("shoulderL", 0.03), ("shoulderR", 0.03)])
    sleeves = {}
    for s in "LR":
        S, E = B["upperArm" + s][0], B["forearm" + s][0]; d = (E - S).normalized()
        wsl = C.w(["chest", "shoulder" + s, "upperArm" + s])
        st = [(S + d * 0.004, (0.0335, 0.0335, 0.0312, 0.0312)), (S + d * 0.018, (0.0338, 0.0338, 0.0320, 0.0320)),
              (S + d * 0.036, (0.0330, 0.0330, 0.0318, 0.0318)), (S + d * 0.054, (0.0318, 0.0318, 0.0310, 0.0310))]
        sleeves[s] = (st, wsl, (0.86, 0.0010, 0.0080))
    rowH = 0.0240; y0s = 0.3620
    ys = [0.6410, 0.6390, 0.6370, 0.6335, 0.6300, 0.6250, 0.6200]
    ys += [0.6200 - (0.6200 - 0.5600) * i / 6 for i in range(1, 7)]
    yy = 0.5600
    while yy - rowH / 3 > y0s + 1e-4:
        yy -= rowH / 3; ys.append(yy)
    ys.append(y0s)
    AA = resample_rows(A, ys)
    cg = torso_shell(C, AA, 36, (0.5600, 0.6200), math.radians(30), sleeves, wt, "armour", e=2.6,
                     lip_top=(0.90, -0.0010, 0.0060), lip_bot=(0.94, 0.0006, 0.0100), direct=True)

    def scales(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            hw = table(A, p.y)[0]
            if abs(p.x) > hw * 1.04 or p.y > 0.6195 or p.y < y0s + 0.0005:
                out.append(p); continue
            a = math.atan2(p.x, p.z) % (2 * math.pi)
            j = int(round(a / (2 * math.pi / 36)))
            rf = (p.y - y0s) / rowH
            r = int(math.floor(rf + 1e-6)); v = rf - r
            ledge = (1.0 - v) ** 0.7                        # bottom edge of each row stands proud
            ph = ((j + 1.5 * (r % 2)) % 3) / 3.0               # position across a scale (3 columns wide, staggered)
            bump = 0.40 + 0.60 * math.sin(math.pi * (ph + 1 / 6)) ** 2
            dsp = 0.0060 * ledge * bump
            if 0.432 < p.y < 0.470:
                dsp *= 0.2                                     # flat under the belt
            out.append(p + n * dsp)
        return out
    C.add("armour", cg, post=scales, subdiv=0, sharp=24,
          cull=lambda p: P["beltY"][0] + 0.0030 < p.y < P["beltY"][1] - 0.0030 and abs(p.x) < 0.075)
    # ---- wide belt over the armour, bronze plate in front
    cg = Cage(); wb = C.w(["hips", "spine"])
    y0, y1 = P["beltY"]
    N = 48; angs = [2 * math.pi * j / N for j in range(N)]
    rings = []
    for y, off in ((y0, 0.0012), (y0 + 0.0012, 0.0040), (y1 - 0.0012, 0.0040), (y1, 0.0012)):
        rings.append(cg.ring([shell_point(A, y, a, off, 2.6) for a in angs], wb))
    for a, b in zip(rings, rings[1:] + rings[:1]):
        cg.bridge(a, b, "belt", 0)
    pz = shell_point(A, (y0 + y1) / 2, 0.0, 0.0050, 2.6).z
    pl = []
    for x, y in ((-0.0120, y0 + 0.002), (0.0120, y0 + 0.002), (0.0120, y1 - 0.002), (-0.0120, y1 - 0.002)):
        pl.append(V(x, y, pz))
    r0 = cg.ring(pl, wb); r1 = cg.ring([p + V(0, 0, 0.0030) for p in pl], wb)
    r2 = cg.ring([p + V(-0.0016 * math.copysign(1, p.x), 0.0016 * (1 if p.y > (y0 + y1) / 2 else -1), 0.0035) for p in pl], wb)
    cg.bridge(r0, r1, "belt", 1); cg.bridge(r1, r2, "belt", 1); cg.face(tuple(r2), "belt", 1)
    C.add("belt", cg, subdiv=0)
    # ---- kilt with pleats under the armour
    K = [(0.4000, 0.0860, 0.0680, -0.0640), (0.3620, 0.0950, 0.0770, -0.0760), (0.3300, 0.1000, 0.0830, -0.0810),
         (0.2950, 0.1055, 0.0880, -0.0850), (0.2640, 0.1100, 0.0915, -0.0880)]
    hipY, hemY, hipX = P["hipY"], P["kiltHemY"], P["hipX"]
    wk0 = C.w(["hips", "spine"])

    def wkilt(p):
        w = wk0(p)
        if p.y >= hipY:
            return w
        tt = min(1.0, (hipY - p.y) / (hipY - hemY)); sL = min(1.0, max(0.0, 0.5 + p.x / (3.0 * hipX))); kk = 0.65 * tt
        w = {b: v * (1 - kk) for b, v in w.items()}
        w["thighL"] = w.get("thighL", 0) + kk * sL; w["thighR"] = w.get("thighR", 0) + kk * (1 - sL)
        return w
    cg = Cage(); NK = 54
    angs = [2 * math.pi * j / NK for j in range(NK)]
    rings = [cg.ring([shell_point(K, r[0], a, 0.0, 2.4) * 1.0 for a in angs], wkilt) for r in densify(K, 2, 0.26, 0.37)]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "kilt", 0)
    y, hw, zf, zb = K[-1]
    lip1 = cg.ring([shell_point(K, y, a, -0.0020, 2.4) + V(0, 0.0010, 0) for a in angs], wkilt)
    lip2 = cg.ring([shell_point(K, y, a, -0.0030, 2.4) + V(0, 0.0120, 0) for a in angs], wkilt)
    cg.bridge(rings[-1], lip1, "kilt", 0); cg.bridge(lip1, lip2, "kilt", 0)

    def pleats(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            a = math.atan2(p.x, p.z + 0.002)
            amp = 0.0032 * smoothstep(0.370, 0.300, max(p.y, 0.300))
            hn = V(p.x, 0, p.z + 0.002).normalized()
            tri = 2 * abs(((18 * a / math.pi) % 2) - 1) - 1           # knife-pleat triangle wave (18 pleats)
            out.append(p + hn * amp * tri)
        return out
    C.add("kilt", cg, post=pleats, subdiv=0, sharp=24)
    # ---- leather bracers on the forearms
    for s in "LR":
        h = C.hand[s]; E, W = B["forearm" + s][0], B["hand" + s][0]; d = (W - E).normalized()
        S0 = B["upperArm" + s][0]; LU = (E - S0).length; LF = (W - E).length
        cg = Cage(); wbr = C.w(["forearm" + s, "hand" + s])
        rings = []
        sd = 1 if s == "L" else -1
        bout = V(-d.y, d.x, 0) * sd; Y0 = d.cross(bout)
        for t, off in ((0.040, 0.0005), (0.043, 0.0030), (0.060, 0.0030), (0.065, 0.0022), (0.070, 0.0030),
                       (0.110, 0.0028), (0.112, 0.0005)):
            s_ = LU + t
            out, inn = table(G_ARM["front"], s_); fr, bk = table(G_ARM["depth"], s_)
            if Y0.dot(V(0, 0, 1)) < 0:
                fr, bk = bk, fr
            c = E + d * t
            alpha_h = (math.pi / 2 if Y0.z > 0 else -math.pi / 2) * smoothstep(LU + 0.15 * LF, LU + LF, s_)
            kk2 = 1.0
            pts = [section(c, bout, Y0, ((out + off) * kk2, (inn + off) * kk2, (fr + off) * kk2, (bk + off) * kk2),
                           2 * math.pi * j / 20 + alpha_h, 2.3) for j in range(20)]
            rings.append(cg.ring(pts, wbr))
        for a, b in zip(rings, rings[1:]):
            cg.bridge(a, b, "bracers", 0)
        cg.bridge(rings[-1], rings[0], "bracers", 0)

        def lace(pts, nrm, d=d, E=E):
            out = []
            for p, n in zip(pts, nrm):
                t = (p - E).dot(d)
                out.append(p)
            return out
        C.add("bracer" + s, cg, post=lace, subdiv=0)
    # ---- bronze greaves over the shins (front + sides), knee flare, centre ridge; straps at the back
    for s in "LR":
        cg = Cage(); wg = C.w(["thigh" + s, "shin" + s])
        lg = C.leg[s]; sd = lg["sd"]
        NA = 15
        ys = [0.201, 0.195, 0.184, 0.168, 0.145, 0.120, 0.095, 0.075, 0.062, 0.054]
        rows = []
        for y in ys:
            flare = 0.0035 * smoothstep(0.180, 0.200, y) + 0.0030 * smoothstep(0.075, 0.056, y)
            row = []
            for i in range(NA):
                f = -1 + 2 * i / (NA - 1)                     # -1 inner side .. +1 outer side (wraps ~ 250 deg)
                a = math.pi / 2 - f * math.radians(118) * sd
                p = leg_point(C, s, y, a, 0.0040 + flare)
                row.append(p)
            rows.append(row)
        outer = [cg.ring(r, wg) for r in rows]
        for a, b in zip(outer, outer[1:]):
            cg.bridge(a, b, "greaves", 0, closed=False)

        def ridge(pts, nrm, sd=sd):
            out = []
            for p, n in zip(pts, nrm):
                xc = table([(r[0], r[1]) for r in G_LEG["rows"]], p.y)[0] * sd
                fx = (p.x - xc) / 0.010
                out.append(p + n * 0.0016 * math.exp(-fx * fx) * smoothstep(-0.005, 0.01, p.z))
            return out
        C.add("greave" + s, cg, post=ridge, solidify=0.0025, subdiv=0)
    # ---- boots: the leg below 0.0625 is region "feet"; add a rolled cuff and laces
    for s in "LR":
        cg = Cage(); wbt = C.w(["shin" + s, "foot" + s])
        cuff = [leg_point_full(C, s, 0.0628, 2 * math.pi * j / 18, 0.0010) for j in range(18)]
        cc = sum(cuff, V()) / len(cuff)
        band_loop(cg, cuff, [(p - cc).normalized() for p in cuff], [V(0, 1, 0)] * len(cuff), 0.0030, 0.0022, wbt, "feet", 1)
        welt = [leg_point_full(C, s, 0.0045, math.pi / 2 - 2 * math.pi * u, 0.0010) for u in front_dense(22, 0.3)]
        wc = sum(welt, V()) / len(welt)
        band_loop(cg, welt, [V(p.x - wc.x, 0, p.z - wc.z).normalized() for p in welt], [V(0, 1, 0)] * len(welt),
                  0.0028, 0.0020, wbt, "feet", 1)
        C.add("bootTrim" + s, cg, subdiv=0)
    # ---- helmet (rigid): dome + rim band + neck guard + ridge; transverse crest
    build_helmet(C)
    build_spear(C)
    build_shield(C)


def build_beard(C):
    """Goliath's beard (a thick modelled volume over jaw and chin, hanging below the chin, with locks) + moustache."""
    Hd = C.head; L = C.headL
    cg = Cage(); wfn = C.w(["head"])
    NU, NV = 19, 10
    umax = 0.255
    top_tab = [(0.00, 0.6600), (0.035, 0.6605), (0.07, 0.6655), (0.11, 0.6740), (0.16, 0.6810), (0.21, 0.6840),
               (0.255, 0.6830)]
    bot_tab = [(0.00, 0.6215), (0.06, 0.6235), (0.12, 0.6300), (0.18, 0.6420), (0.22, 0.6530), (0.255, 0.6640)]
    chin = L["chin"]
    zc = L["zc"]

    def base(u, y):
        uu = abs(((u + 0.5) % 1.0) - 0.5)
        if y >= chin + 0.004:
            p = Hd.at(u, y); n = Hd.normal(u, y)
            return p, n
        pc = Hd.at(u, chin + 0.004); n = Hd.normal(u, chin + 0.004)
        t = (chin + 0.004 - y) / (chin + 0.004 - 0.618)
        p = V(pc.x * (1 - 0.55 * t), y, zc + (pc.z - zc) * (1 - 0.25 * t * t) - 0.004 * t)
        n = (n + V(0, -0.6 * t, 0)).normalized()
        return p, n

    def thick(u, y, v):
        uu = abs(((u + 0.5) % 1.0) - 0.5)
        t = lerp(0.0110, 0.0060, smoothstep(0.05, 0.25, uu))
        t *= smoothstep(0.0, 0.18, v)
        if uu < 0.06 and y > 0.656:                                   # thin under the lower lip (mouth reads)
            t *= 0.35
        return t + 0.0006
    us = [-umax + 2 * umax * i / (NU - 1) for i in range(NU)]
    outer = []
    for j in range(NV + 1):
        v = j / NV; row = []
        for u in us:
            uu = abs(u)
            yt = table(top_tab, uu)[0]; yb = table(bot_tab, uu)[0]
            y = lerp(yt, yb, v)
            p, n = base(u % 1.0, y)
            row.append(p + n * thick(u % 1.0, y, v) - n * 0.0010 * (1 - smoothstep(0.0, 0.12, v)))
        outer.append(cg.ring(row, wfn))
    for a, b in zip(outer, outer[1:]):
        cg.bridge(a, b, "beard", 0, closed=False)

    def locks(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            a = math.atan2(p.x, p.z - zc)
            g = 0.0016 * math.cos(a * 22) * smoothstep(0.660, 0.635, p.y)
            out.append(p + n * g)
        return out
    C.add("beard", cg, post=locks, solidify=0.0050, decal=True, jaw=True, subdiv=0)
    # moustache: a tapered lock from the middle under the nose drooping to each mouth corner
    cg = Cage()
    pts = []
    for i in range(11):
        f = -1 + 2 * i / 10
        x = f * 0.0270
        y = 0.6770 - 0.0035 * abs(f) - 0.0090 * abs(f) ** 2.2 + 0.0008 * math.exp(-(f / 0.15) ** 2)
        u = math.atan2(x, 0.04) / (2 * math.pi)
        p = Hd.at(u % 1.0, y); n = Hd.normal(u % 1.0, y)
        pts.append((p + n * 0.0026, n))
    rings = []
    for i, (p, n) in enumerate(pts):
        f = -1 + 2 * i / 10
        th = 0.0034 * (1 - 0.75 * abs(f) ** 1.6) + 0.0006
        hh = 0.0052 * (1 - 0.6 * abs(f) ** 1.5) + 0.0008
        t = (pts[min(i + 1, 10)][0] - pts[max(i - 1, 0)][0]).normalized()
        up = perp(V(0, 1, 0), t)
        nn = t.cross(up).normalized()
        if nn.dot(n) < 0:
            nn = -nn
        rings.append(cg.ring([p + up * (hh * math.cos(2 * math.pi * k / 8) * 0.5) + nn * (th * math.sin(2 * math.pi * k / 8) * 0.5)
                              for k in range(8)], wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "beard", 1)
    cg.fan(rings[0], pts[0][0] + (pts[0][0] - pts[1][0]) * 0.6, wfn, "beard", 1)
    cg.fan(rings[-1], pts[-1][0] + (pts[-1][0] - pts[-2][0]) * 0.6, wfn, "beard", 1)
    C.add("moustache", cg, decal=True, subdiv=0)


def build_helmet(C):
    L = C.headL
    cg = Cage()
    N = 32
    angs = [2 * math.pi * j / N for j in range(N)]
    # bronze dome (design front outline + side depths): superellipse rings, lower edge at y 0.713 just above the brow
    D = [(0.7130, 0.0462, 0.0456, -0.0528), (0.7200, 0.0482, 0.0474, -0.0537), (0.7300, 0.0476, 0.0466, -0.0528),
         (0.7400, 0.0452, 0.0440, -0.0502), (0.7500, 0.0398, 0.0386, -0.0442), (0.7580, 0.0322, 0.0312, -0.0362),
         (0.7640, 0.0222, 0.0214, -0.0250), (0.7672, 0.0115, 0.0110, -0.0130)]
    D = densify(D, 2)

    def ring(y, hw, zf, zb, sc=1.0, e=2.2):
        zc = (zf + zb) / 2; rd = (zf - zb) / 2
        return [V(se(math.sin(a), e) * hw * sc, y, zc + se(math.cos(a), e) * rd * sc) for a in angs]
    rings = [cg.ring(ring(*r), None) for r in D]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "helmet", 0)
    cg.fan(rings[-1], V(0, 0.7682, (D[-1][2] + D[-1][3]) / 2), None, "helmet", 0)
    # lower edge rolls inward under the dome so it has thickness
    y0, hw0, zf0, zb0 = D[0]
    band = []
    for dy, sc in ((-0.0006, 0.990), (-0.0006, 0.955), (0.0030, 0.950)):
        band.append(cg.ring(ring(y0 + dy, hw0, zf0, zb0, sc), None))
    cg.bridge(rings[0], band[0], "helmet", 0)
    for a, b in zip(band, band[1:]):
        cg.bridge(a, b, "helmet", 0)

    def ridge(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            k = 0.0022 * math.exp(-(p.x / 0.0035) ** 2) if p.y > 0.726 else 0.0
            band = 0.0024 * smoothstep(0.7128, 0.7142, p.y) * smoothstep(0.7240, 0.7224, p.y)   # raised rim band
            out.append(p + n * (k + band))
        return out
    C.add("helmetDome", cg, rigid="helmet", post=ridge, subdiv=0)
    # neck guard: a flared skirt round the sides and back, open at the face
    cg = Cage()
    yb = y0 + 0.0010
    NG = 25
    gas = [math.radians(62 + (298 - 62) * i / (NG - 1)) for i in range(NG)]
    grows = []
    for dy, fl in ((0.0000, 1.00), (-0.0080, 1.04), (-0.0160, 1.08), (-0.0240, 1.13), (-0.0310, 1.17), (-0.0335, 1.18)):
        zc = (zf0 + zb0) / 2; rd = (zf0 - zb0) / 2
        row = [V(se(math.sin(a), 2.2) * hw0 * fl, yb + dy, zc + se(math.cos(a), 2.2) * rd * fl) for a in gas]
        grows.append(cg.ring(row, None))
    for a, b in zip(grows, grows[1:]):
        cg.bridge(a, b, "helmet", 0, closed=False)
    C.add("helmetGuard", cg, rigid="helmet", solidify=0.0022, subdiv=0)
    # crest: transverse fan of horsehair on a holder; front/back surfaces with combed grooves
    cg = Cage()
    outline = [(0, 0.8000), (0.0180, 0.7990), (0.0360, 0.7930), (0.0500, 0.7810), (0.0520, 0.7700), (0.0300, 0.7640),
               (0, 0.7630)]
    half = outline + [(-x, y) for x, y in reversed(outline[1:-1])]
    ctrl = [V(x, y, 0) for x, y in half]
    NO = 30
    cen = V(0, 0.7735, 0)
    rim = []
    for k in range(NO):
        p = cr_closed(ctrl, k / NO)
        if p.y > 0.7700:                                   # tufted upper edge
            p = cen + (p - cen) * (1.0 + 0.06 * (0.5 + 0.5 * math.cos(k * 2 * math.pi / 3.0)))
        rim.append(p)
    zc = L["zc"] - 0.004
    layers = []
    for fz, sc in ((0.0, 1.0), (0.55, 0.78), (0.85, 0.50), (1.0, 0.22)):
        for sgn in ((1,) if fz == 0.0 else (1, -1)):
            pass
    front, back = [], []
    for fz, sc in ((0.65, 0.72), (1.0, 0.25)):
        front.append([cen + (p - cen) * sc + V(0, 0, zc + 0.0045 * fz) for p in rim])
        back.append([cen + (p - cen) * sc + V(0, 0, zc - 0.0045 * fz) for p in rim])
    r0 = cg.ring([p + V(0, 0, zc) for p in rim], None)
    prev = r0
    for row in front:
        r = cg.ring(row, None); cg.bridge(prev, r, "crest", 0); prev = r
    cg.fan(prev, cen + V(0, 0, zc + 0.0050), None, "crest", 0)
    prev = r0
    for row in back:
        r = cg.ring(row, None); cg.bridge(r, prev, "crest", 0); prev = r
    cg.fan(prev, cen + V(0, 0, zc - 0.0050), None, "crest", 0)

    def comb(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            a = math.atan2(p.x, p.y - 0.760)
            g = 0.0014 * math.cos(a * 36)
            sweep = -0.006 * ((p.y - 0.764) / 0.036) ** 2           # tips swept back a little
            out.append(p + V(n.x, n.y, n.z * 0.3) * g + V(0, 0, sweep))
        return out
    C.add("crest", cg, rigid="helmet", post=comb, subdiv=0)
    cg = Cage()
    lathe_y(cg, V(0, 0.7655, zc), [(-0.0040, 0.0060), (0.0, 0.0072), (0.0030, 0.0060)], 12, None, "helmet", 1, zscale=0.8)
    C.add("crestHolder", cg, rigid="helmet", subdiv=0)


def build_spear(C):
    B = C.B; sp = DESIGN["characters"]["goliath"]["props"]["spear"]
    x = B["spear"][0].x; sheetY = C.info["sheetY"]
    y0, y1 = sp["y"][0] - sheetY, sp["y"][1] - sheetY
    cg = Cage()
    r = sp["shaftDiameter"] / 2
    hl, hw = sp["head"]["length"], sp["head"]["width"]
    c = V(x, 0, 0)
    yb = y0 + 0.028; ycol = y1 - hl - 0.012
    prof = [(y0, 0.0012), (y0 + 0.010, 0.0042), (yb - 0.004, 0.0072), (yb, 0.0098), (yb + 0.003, r * 1.02),
            (0.30, r), (0.60, r * 0.97), (ycol - 0.009, r * 0.95), (ycol - 0.008, 0.0128), (ycol + 0.008, 0.0128),
            (ycol + 0.009, 0.0085)]
    regs = []
    for (ya, ra), (yb_, rb) in zip(prof, prof[1:]):
        regs.append("spearHead" if ya < yb + 0.001 else ("spearShaft"))
    N = 12
    rings = []
    for y, rr in prof:
        rings.append(cg.ring([c + V(math.sin(2 * math.pi * j / N) * rr, y, math.cos(2 * math.pi * j / N) * rr)
                              for j in range(N)], None))
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        cg.bridge(a, b, regs[i], 0 if regs[i] == "spearShaft" else 1)
    cg.fan(rings[0], c + V(0, y0 - 0.002, 0), None, "spearHead", 1)
    # leaf head: diamond section (mid-rib thick, edges thin) lofted along y
    hp = [(ycol + 0.009, 0.0060, 0.0060), (ycol + 0.016, 0.0105, 0.0050), (ycol + 0.026, 0.0160, 0.0047),
          (ycol + 0.040, 0.0198, 0.0045), (ycol + 0.055, 0.0196, 0.0043), (ycol + 0.070, 0.0172, 0.0040),
          (ycol + 0.083, 0.0130, 0.0035), (ycol + 0.095, 0.0080, 0.0028), (y1 - 0.004, 0.0025, 0.0016)]
    hr = []
    for y, wv, tv in hp:
        pts = []
        for j in range(N):
            a = 2 * math.pi * j / N
            sx, sz = math.sin(a), math.cos(a)
            pts.append(c + V(math.copysign(abs(sx) ** 0.8, sx) * wv, y, math.copysign(abs(sz) ** 1.6, sz) * tv))
        hr.append(cg.ring(pts, None))
    cg.bridge(rings[-1], hr[0], "spearHead", 2)
    for a, b in zip(hr, hr[1:]):
        cg.bridge(a, b, "spearHead", 2)
    cg.fan(hr[-1], c + V(0, y1, 0), None, "spearHead", 2)
    C.add("spear", cg, rigid="spear", subdiv=0)


def build_shield(C):
    sp = DESIGN["characters"]["goliath"]["props"]["shield"]
    sx, sy, sz = sp["centreSheet"]; sx -= C.info["sheetX"]; sy -= C.info["sheetY"]
    R = sp["diameter"] / 2; rim = sp["rim"]; boss = sp["bossDiameter"] / 2; dish = sp["dish"]; th = sp["thickness"]
    cg = Cage()
    cen = V(sx, sy, sz)
    prof = [(-th * 0.5, 0.0), (-th * 0.5, R - 0.010), (-th * 0.35, R - 0.002), (0.0, R + 0.0005), (th * 0.40, R - 0.0015),
            (th * 0.55, R - rim * 0.55), (th * 0.30, R - rim), (th * 0.30 + dish * 0.30, R - rim - 0.008),
            (th * 0.30 + dish * 0.45, R - 0.0235), (th * 0.30 + dish * 0.45 + 0.0018, R - 0.0255),
            (th * 0.30 + dish * 0.45, R - 0.0275), (th * 0.30 + dish * 0.75, R - 0.042),
            (th * 0.30 + dish, boss + 0.002), (th * 0.30 + dish + 0.004, boss - 0.0005), (th * 0.30 + dish + 0.011, boss * 0.70),
            (th * 0.30 + dish + 0.015, boss * 0.30), (th * 0.30 + dish + 0.016, 0.0)]

    def regf(a, b):
        r = (a[1] + b[1]) / 2
        if a[1] == 0 and a[0] < 0:
            return "shield"
        if r > R - rim - 0.001 or (a[0] < 0 and b[0] <= 0.0):
            return "shieldRim"
        return "shield" if r > boss + 0.001 else "shieldBoss"
    lathe_z(cg, cen, prof, 32, None, regf)
    C.add("shield", cg, rigid="shield", subdiv=0)


def build_character_parts(ch):
    C = Ctx(ch)
    (build_david if ch == "david" else build_goliath)(C)
    return C


# =============================================================================================== scene building
sc = bpy.context.scene


def new_mesh_obj(name, verts_bl, faces):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts_bl], [], faces); me.update()
    o = bpy.data.objects.new(name, me); sc.collection.objects.link(o)
    return o


def fix_normals(o):
    bm = bmesh.new(); bm.from_mesh(o.data)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose: bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    cen = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
    score = sum(f.normal.dot(f.calc_center_median() - cen) * f.calc_area() for f in bm.faces)
    if score < 0:
        for f in bm.faces: f.normal_flip()
    bm.to_mesh(o.data); bm.free()
    for poly in o.data.polygons: poly.use_smooth = True


def make_armature(ch):
    B = bones_of(ch)
    arm = bpy.data.armatures.new(ch + "_rig")
    o = bpy.data.objects.new(ch + "_rig", arm); sc.collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    order = CONTRACT_BONES + EXTRA_BONES[ch]
    assert set(order) == set(B.keys()), (ch, set(order) ^ set(B.keys()))
    for name in order:
        h, t, parent = B[name]
        eb = arm.edit_bones.new(name); eb.head = to_bl(h); eb.tail = to_bl(t)
        dirn = (eb.tail - eb.head).normalized()
        eb.align_roll(Vector((0, -1, 0)) if abs(dirn.y) < 0.9 else Vector((0, 0, 1)))   # local Z -> viewer
        if parent:
            eb.parent = arm.edit_bones[parent]
            eb.use_connect = (eb.parent.tail - eb.head).length < 1e-6
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def apply_modifier(o, m):
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    bpy.ops.object.modifier_apply(modifier=m.name)


def apply_solidify(o, th):
    m = o.modifiers.new("solid", 'SOLIDIFY'); m.thickness = th; m.offset = -1.0; m.use_even_offset = False
    m.use_rim = True
    apply_modifier(o, m)


def apply_subsurf(o, levels=1):
    m = o.modifiers.new("subd", 'SUBSURF'); m.levels = levels; m.render_levels = levels; m.quality = 3
    m.uv_smooth = 'NONE'; m.boundary_smooth = 'ALL'
    apply_modifier(o, m)


PART_TRIS = {}                   # part -> (cage faces, final triangles), for the budget report
PIECE_TABLE = []                 # global piece id -> (char, part, piece) ; index 0 = background
REGION_TABLE = []                # global region id -> "char.region"


def region_id(ch, reg):
    key = f"{ch}.{reg}"
    if key not in REGION_TABLE: REGION_TABLE.append(key)
    return REGION_TABLE.index(key) + 1


def build_character(ch):
    C = build_character_parts(ch)
    info = C.info; sheetX = info["sheetX"]; sheetY = info.get("sheetY", 0.0); S = C.S
    rig = make_armature(ch); rig.location = (sheetX, 0, sheetY)          # Blender Z = design y
    bpy.context.view_layer.update()
    mouthY = C.P["mouthY"]; chin = C.P["chin"]; H = C.P["skullTop"] - C.P["chin"]
    dec = DESIGN["faceDecals"][ch]["rectLocal"]
    body, props = [], []
    for pt in C.parts:
        cg = pt["cage"]
        o = new_mesh_obj(f"{ch}_{pt['name']}", [to_bl(v) for v in cg.v], cg.f)
        pids = []
        for k in cg.pc:
            key = (ch, pt["name"], k)
            if key not in PIECE_TABLE: PIECE_TABLE.append(key)
            pids.append(PIECE_TABLE.index(key) + 1)
        rids = [region_id(ch, r) for r in cg.reg]
        a1 = o.data.attributes.new("dg_piece", 'INT', 'FACE'); a1.data.foreach_set("value", pids)
        a2 = o.data.attributes.new("dg_region", 'INT', 'FACE'); a2.data.foreach_set("value", rids)
        rigid = pt.get("rigid")
        if not rigid:
            groups = {}
            for i, w in enumerate(cg.w):
                for b, v in w.items():
                    if v > 1e-4: groups.setdefault(b, []).append((i, v))
            for b, lst in groups.items():
                g = o.vertex_groups.get(b) or o.vertex_groups.new(name=b)
                for i, v in lst: g.add([i], v, 'REPLACE')
        fix_normals(o)
        if pt.get("subdiv", 1):
            apply_subsurf(o, pt.get("subdiv", 1))
        fix_normals(o)
        if pt.get("post"):
            me = o.data
            pts = [to_design(v.co) for v in me.vertices]; nrm = [to_design(v.normal) for v in me.vertices]
            new = pt["post"](pts, nrm)
            for v, p in zip(me.vertices, new):
                v.co = to_bl(p)
            me.update()
        if pt.get("sharp"):                       # crisp scale ledges / knife pleats: split normals above this angle
            o.data.set_sharp_from_angle(angle=math.radians(pt["sharp"]))
        if pt.get("cull"):
            bm = bmesh.new(); bm.from_mesh(o.data)
            hid = {v.index: pt["cull"](to_design(v.co)) for v in bm.verts}
            dead = [f for f in bm.faces if all(hid[v.index] for v in f.verts)]
            bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
            loose = [v for v in bm.verts if not v.link_faces]
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
            bm.to_mesh(o.data); bm.free(); o.data.update()
        th = pt.get("solidify") or pt.get("solidify_faces")
        if th:
            apply_solidify(o, th)
        PART_TRIS[f"{ch}_{pt['name']}"] = (len(cg.f), tri_count([o]))
        # parent to the rig (identity parent-inverse; LESSONS L26) — world = local + (sheetX, sheetY)
        o.parent = rig
        if rigid:
            o.parent_type = 'BONE'; o.parent_bone = rigid
        o.matrix_parent_inverse = Matrix.Identity(4)
        bpy.context.view_layer.update()
        o.matrix_world = Matrix.Translation((sheetX, 0, sheetY))
        bpy.context.view_layer.update()
        me = o.data
        uv0 = me.uv_layers.new(name="UVMap"); uv1 = me.uv_layers.new(name="decal")
        vco = [to_design(v.co) for v in me.vertices]
        if rigid:
            vco = [to_design(o.matrix_world @ v.co) - V(sheetX, sheetY, 0) for v in me.vertices]
        vn = [to_design(v.normal) for v in me.vertices]
        uvs, dus = [], []
        for p, n in zip(vco, vn):
            x = p.x + sheetX
            uvs.append((x + 0.5 - n.x * INSET, (p.y + sheetY - n.y * INSET) / ART_H))
            if pt.get("decal"):
                du = (p.x - dec[0]) / (dec[2] - dec[0]); dv = (p.y - dec[1]) / (dec[3] - dec[1])
                if p.z < 0.0 or n.z < 0.3:   # back / grazing: move straight up/down out of the decal (no smears)
                    if abs(dv - 0.5) > 0.45:
                        dv = 4.0 if dv > 0.5 else -3.0
                    else:
                        du = 4.0 if du > 0.5 else -3.0
                dus.append((du, dv))
            else:
                dus.append((-1.0, -1.0))
        for poly in me.polygons:
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                uv0.data[li].uv = uvs[vi]; uv1.data[li].uv = dus[vi]
        me.uv_layers.active = uv0
        if not rigid:
            if pt.get("jaw"):
                band = 0.0045 * S
                gj = o.vertex_groups.get("jaw") or o.vertex_groups.new(name="jaw")
                gidx = {g.index: g for g in o.vertex_groups}
                for i, p in enumerate(vco):
                    wj = smoothstep(mouthY + band * 0.5, mouthY - band, p.y) \
                        * smoothstep(-0.25 * 0.044 * S, 0.1 * 0.044 * S, p.z) \
                        * smoothstep(chin - 0.20 * H, chin + 0.02 * H, p.y)
                    if wj <= 0:
                        continue
                    v = me.vertices[i]
                    for ge in list(v.groups):
                        gidx[ge.group].add([i], ge.weight * (1 - wj), 'REPLACE')
                    gj.add([i], wj, 'ADD')
            body.append(o)
        else:
            props.append(o)
    bpy.ops.object.select_all(action='DESELECT')
    for o in body: o.select_set(True)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.object.join()
    bodyo = bpy.context.view_layer.objects.active; bodyo.name = f"{ch}_body"; bodyo.data.name = f"{ch}_body"
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    am = bodyo.modifiers.new("Armature", 'ARMATURE'); am.object = rig
    cage_quads = sum(len(pt["cage"].f) for pt in C.parts)
    return rig, bodyo, props, cage_quads


# =============================================================================================== materials / render
def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def flat_mat(name, srgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*[srgb_to_lin(c) for c in srgb], 1.0)
    return m


def hex_rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def set_face_materials(o, key_fn, mat_fn):
    """Assign one material per distinct key(piece, region) on the object's faces."""
    me = o.data
    pid = [0] * len(me.polygons); rid = [0] * len(me.polygons)
    me.attributes["dg_piece"].data.foreach_get("value", pid); me.attributes["dg_region"].data.foreach_get("value", rid)
    me.materials.clear(); slots = {}
    idx = []
    for p, r in zip(pid, rid):
        k = key_fn(p, r)
        if k not in slots:
            slots[k] = len(slots); me.materials.append(mat_fn(k))
        idx.append(slots[k])
    me.polygons.foreach_set("material_index", idx)


def id_colour(k):
    """ID k -> sRGB bytes, decodable after Standard view transform (see tools/make_dg_sheet.py)."""
    return (16 + (k % 15) * 16, 16 + ((k // 15) % 15) * 16, 64 + (k // 225) * 64)


def setup_render(engine_res, ortho=True):
    sc.render.engine = 'BLENDER_WORKBENCH'
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.look = 'None'
    sc.render.dither_intensity = 0.0
    sc.render.resolution_x, sc.render.resolution_y = engine_res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGBA'
    sh = sc.display.shading
    sh.show_cavity = False; sh.show_shadows = False; sh.show_object_outline = False; sh.show_specular_highlight = False


def camera(name="Cam"):
    cam = bpy.data.objects.get(name)
    if not cam:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.clip_start = 0.01; cam.data.clip_end = 100
    return cam


def front_ortho_camera():
    cam = camera(); cam.data.type = 'ORTHO'; cam.data.ortho_scale = ART_H; cam.data.sensor_fit = 'AUTO'
    cam.location = (0.0, -20.0, ART_H / 2); cam.rotation_euler = (math.radians(90), 0, 0)
    return cam


def look_from(cam, target, yaw_deg, dist, height, lens=60):
    cam.data.type = 'PERSP'; cam.data.lens = lens
    a = math.radians(yaw_deg)
    cam.location = target + Vector((math.sin(a) * dist, -math.cos(a) * dist, height))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()


def render(path):
    sc.render.filepath = path; bpy.ops.render.render(write_still=True)


def region_palette_mat(rid):
    ch, reg = REGION_TABLE[rid - 1].split(".")
    pal = DESIGN["palette"][ch]
    return flat_mat(f"pal_{ch}_{reg}", hex_rgb(pal.get(reg, "#cccccc")))


def page_material(image_path=None):
    m = bpy.data.materials.get("dg_page") or bpy.data.materials.new("dg_page")
    m.diffuse_color = (1, 1, 1, 1)
    nt = m.node_tree; bsdf = nt.nodes.get("Principled BSDF")
    if bsdf is None:
        bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled"); out = nt.nodes.get("Material Output") or nt.nodes.new("ShaderNodeOutputMaterial")
        nt.links.new(bsdf.outputs[0], out.inputs[0])
    bsdf.inputs["Roughness"].default_value = 0.8
    if image_path:
        tex = nt.nodes.get("page_tex") or nt.nodes.new("ShaderNodeTexImage"); tex.name = "page_tex"
        tex.image = bpy.data.images.load(image_path, check_existing=True); tex.interpolation = 'Linear'
        uvn = nt.nodes.get("page_uv") or nt.nodes.new("ShaderNodeUVMap"); uvn.name = "page_uv"; uvn.uv_map = "UVMap"
        nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"]); nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        nt.nodes.active = tex
    return m


def all_meshes():
    return [o for o in sc.objects if o.type == 'MESH']


def show_only(ch):
    for o in sc.objects:
        if o.type == 'MESH':
            o.hide_render = bool(ch) and not o.name.startswith(ch + "_")


def tri_count(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)


# =============================================================================================== pose test
def bend(rig, bone, axis_design, deg):
    """Rotate a pose bone about a design-space axis through its head, on top of its (unposed) rest frame."""
    pb = rig.pose.bones[bone]
    R = Matrix.Rotation(math.radians(deg), 4, to_bl(axis_design).normalized())
    rest = pb.bone.matrix_local
    pb.rotation_mode = 'QUATERNION'
    h = rest.translation.copy()
    pb.matrix_basis = rest.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ rest
    bpy.context.view_layer.update()


def pose_test(rig):
    # elbows fold forward (toward the viewer), knees fold back, spine leans in, fingers curl / open, thumbs move
    B = {b.name: (to_design(b.head_local), to_design(b.tail_local)) for b in rig.data.bones}
    for side in "LR":
        h, t = B["forearm" + side]; d = (t - h).normalized()
        ax = d.cross(V(0, 0, 1))
        bend(rig, "forearm" + side, ax, 60)
        bend(rig, "shin" + side, V(1, 0, 0), 60)
        h, t = B["hand" + side]; dh = (t - h).normalized()
        hz = dh.cross(V(0, 0, 1)).normalized()
        fh, ft = B["fingerTips" + side]
        curled = (ft - fh).dot(dh) < 0.0
        sgn = -1 if curled else 1          # open hands curl, fists open
        bend(rig, "fingers" + side, hz if side == "L" else -hz, sgn * 50)
        bend(rig, "fingerTips" + side, hz if side == "L" else -hz, sgn * 50)
        bend(rig, "thumb" + side, dh, 25)
    bend(rig, "spine", V(1, 0, 0), 30); bend(rig, "chest", V(1, 0, 0), 30)


def edge_stretch(o):
    dg = bpy.context.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg); me2 = ev.to_mesh()
    rest = o.data
    worst, bad, where = 0.0, 0, {}
    for e in rest.edges:
        a, b = e.vertices
        l0 = (rest.vertices[a].co - rest.vertices[b].co).length
        l1 = (me2.vertices[a].co - me2.vertices[b].co).length
        if l0 > 1e-7:
            r = max(l1 / l0, l0 / max(l1, 1e-9)); worst = max(worst, r)
            if r > 1.6:
                bad += 1
                gs = rest.vertices[a].groups
                g = max(gs, key=lambda x: x.weight) if len(gs) else None
                nm = o.vertex_groups[g.group].name if g else "-"
                where[nm] = where.get(nm, 0) + 1
    ev.to_mesh_clear()
    return worst, bad, len(rest.edges), where


# =============================================================================================== modes
def preview_shading(sh):
    sh.light = 'STUDIO'; sh.color_type = 'MATERIAL'; sh.show_cavity = True; sh.cavity_type = 'BOTH'
    sh.cavity_ridge_factor = 0.6; sh.cavity_valley_factor = 1.0
    sh.show_object_outline = True; sh.object_outline_color = (0.15, 0.12, 0.10)
    sh.show_shadows = True; sh.shadow_intensity = 0.35
    try:
        sh.studio_light = 'paint.sl'
    except Exception:
        pass


def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    global sc; sc = bpy.context.scene
    report = {"chars": {}}
    rigs, bodies, propsd = {}, {}, {}
    for ch in CHARS:
        rig, body, props, cageq = build_character(ch)
        rigs[ch], bodies[ch], propsd[ch] = rig, body, props
        tris = tri_count([body] + props)
        bones = [b.name for b in rig.data.bones]
        report["chars"][ch] = {"tris": tris, "bodyTris": tri_count([body]), "cageFaces": cageq, "bones": bones,
                               "props": {o.name: o.parent_bone for o in props},
                               "propTris": {o.name: tri_count([o]) for o in props},
                               "vertexGroups": sorted(g.name for g in body.vertex_groups)}
        print(f"[{ch}] tris={tris} cage={cageq} bones={len(bones)} props={[o.name for o in props]}")
    # ---- sheet ID render (front ortho, 2x the art rect, no AA): one colour per (piece, region)
    setup_render((2000, round(2000 * ART_H)))
    sc.render.film_transparent = True; sc.display.render_aa = 'OFF'
    sc.display.shading.light = 'FLAT'; sc.display.shading.color_type = 'MATERIAL'
    front_ortho_camera()
    idmap = {}
    for o in all_meshes():
        def key_fn(p, r): return (p, r)

        def mat_fn(k):
            n = len(idmap) + 1; idmap[k] = n
            return flat_mat(f"id_{n}", [c / 255 for c in id_colour(n)])
        set_face_materials(o, key_fn, mat_fn)
    render(os.path.join(WORK, "id_2x.png"))
    ids = []
    for (p, r), n in sorted(idmap.items(), key=lambda kv: kv[1]):
        ch, pname, k = PIECE_TABLE[p - 1]; rch, reg = REGION_TABLE[r - 1].split(".")
        ids.append({"id": n, "rgb": id_colour(n), "char": ch, "part": pname, "piece": k, "region": reg,
                    "hex": DESIGN["palette"][ch].get(reg, "#cccccc")})
    json.dump({"note": "front-ortho ID render of the rest pose at sheet positions; background = alpha 0",
               "size": [sc.render.resolution_x, sc.render.resolution_y], "ids": ids}, open(os.path.join(WORK, "id_2x.json"), "w"), indent=1)
    # ---- previews in demo palette colours
    for o in all_meshes():
        set_face_materials(o, lambda p, r: r, region_palette_mat)
    setup_render((900, 900)); sc.render.film_transparent = False; sc.display.render_aa = '8'
    preview_shading(sc.display.shading)
    w = bpy.data.worlds.new("W"); sc.world = w; w.color = (0.98, 0.96, 0.90)
    cam = camera()
    for ch in CHARS:
        show_only(ch)
        info = DESIGN["characters"][ch]; Hh = info["height"]; x = info["sheetX"]
        tgt = Vector((x, 0, Hh * 0.52))
        for yaw in (0, 35, 90, 180):
            look_from(cam, tgt, yaw, Hh * 3.4, Hh * 0.10, 60)
            render(os.path.join(WORK, f"prev_{ch}_{yaw}.png"))
        # close-ups: head 3/4 and hands
        P = info["proportions"]; hy = (P["skullTop"] + P["chin"]) / 2 + info["sheetY"]
        look_from(cam, Vector((x, 0, hy)), 30, (P["skullTop"] - P["chin"]) * 4.2, 0.0, 60)
        render(os.path.join(WORK, f"prev_{ch}_head.png"))
        look_from(cam, Vector((x, 0, hy)), 0, (P["skullTop"] - P["chin"]) * 4.2, 0.0, 60)
        render(os.path.join(WORK, f"prev_{ch}_headfront.png"))
        Bl = bones_of(ch)
        for s in "LR":
            hp = Bl["hand" + s][1] + V(x, info["sheetY"], 0)
            look_from(cam, Vector((hp.x, -hp.z, hp.y)), 20 if s == "L" else -20, P["hand"] * 4.0, P["hand"] * 0.5, 60)
            render(os.path.join(WORK, f"prev_{ch}_hand{s}.png"))
        fp = Bl["foot" + "L"][0] + V(x, info["sheetY"], 0)
        look_from(cam, Vector((fp.x, -0.01 * Hh, 0.02 * Hh)), 40, Hh * 0.55, Hh * 0.18, 60)
        render(os.path.join(WORK, f"prev_{ch}_feet.png"))
    show_only(None)
    sc.render.resolution_x, sc.render.resolution_y = 1400, 1000
    look_from(cam, Vector((-0.05, 0, 0.42)), 20, 2.3, 0.35, 50); render(os.path.join(WORK, "prev_both.png"))
    # ---- pose test
    stretch = {}
    for ch in CHARS:
        pose_test(rigs[ch]); stretch[ch] = edge_stretch(bodies[ch])
    sc.render.resolution_x, sc.render.resolution_y = 900, 900
    for ch in CHARS:
        show_only(ch)
        info = DESIGN["characters"][ch]; Hh = info["height"]; x = info["sheetX"]
        for yaw in (0, 60, 90):
            look_from(cam, Vector((x, 0, Hh * 0.5)), yaw, Hh * 3.4, Hh * 0.15, 60)
            render(os.path.join(WORK, f"pose_{ch}_{yaw}.png"))
        rig = rigs[ch]
        for bone, yaw, dist in (("forearmL", 75, 1.5), ("shinL", 90, 1.5), ("spine", 90, 1.5), ("fingersL", 30, 0.45),
                                ("fingersR", -30, 0.45)):
            pb = rig.pose.bones[bone]; tgt = rig.matrix_world @ pb.head
            look_from(cam, tgt, yaw, Hh * dist, 0.0, 60)
            render(os.path.join(WORK, f"pose_{ch}_{bone}.png"))
    show_only(None)
    report["poseStretch"] = {ch: {"worstEdgeRatio": round(s[0], 3), "edgesOver1.6": s[1], "edges": s[2], "over1.6ByBone": s[3]} for ch, s in stretch.items()}
    for ch in CHARS:
        for pb in rigs[ch].pose.bones: pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    # ---- final materials, export (character-local: rig at the origin), blend
    page = page_material()
    for o in all_meshes():
        me = o.data; me.materials.clear(); me.materials.append(page)
        me.polygons.foreach_set("material_index", [0] * len(me.polygons))
    expected = {}
    for ch in CHARS:
        rig = rigs[ch]; rig.location = (0, 0, 0); bpy.context.view_layer.update()
        expected[ch] = {o.name: [list(map(lambda v: round(v, 5), to_design(o.matrix_world @ Vector(c)))) for c in (o.bound_box[0], o.bound_box[6])]
                        for o in rig.children}
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        for o in rig.children: o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"), use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=False, export_def_bones=False,
                                  export_texcoords=True, export_materials='EXPORT', export_morph=False)
        rig.location = (DESIGN["characters"][ch]["sheetX"], 0, DESIGN["characters"][ch].get("sheetY", 0.0))
    bpy.context.view_layer.update()
    report["expectedLocalBounds"] = expected
    report["pieces"] = len(PIECE_TABLE); report["regions"] = REGION_TABLE; report["partTris"] = PART_TRIS
    json.dump(report, open(os.path.join(WORK, "build_report.json"), "w"), indent=1)
    bpy.context.preferences.filepaths.save_version = 0           # no .blend1 backup next to the deliverable
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({k: v for k, v in report.items() if k != "expectedLocalBounds"}))


def mode_uvcheck():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    global sc; sc = bpy.context.scene
    demo = os.environ.get("DG_UV_TEXTURE") or os.path.join(SHEET, "demo-colored.png")
    page_material(demo)
    setup_render((1000, round(1000 * ART_H)))
    sc.render.film_transparent = True; sc.display.render_aa = '8'
    sh = sc.display.shading; sh.light = 'FLAT'; sh.color_type = 'TEXTURE'
    front_ortho_camera(); render(os.path.join(WORK, "uv_front.png"))
    setup_render((800, 800)); sc.render.film_transparent = False; sc.display.render_aa = '8'
    sh.light = 'STUDIO'; sh.color_type = 'TEXTURE'; sh.show_cavity = True
    if not sc.world:
        sc.world = bpy.data.worlds.new("W")
    sc.world.color = (0.98, 0.96, 0.90)
    cam = camera()
    for ch in CHARS:
        show_only(ch)
        info = DESIGN["characters"][ch]; Hh = info["height"]
        for yaw in (0, 35, 90, 180):
            look_from(cam, Vector((info["sheetX"], 0, Hh * 0.52)), yaw, Hh * 3.4, Hh * 0.10, 60)
            render(os.path.join(WORK, f"uv_{ch}_{yaw}.png"))
    show_only(None)
    for ch in CHARS:
        fd = DESIGN["faceDecals"][ch]
        m = bpy.data.materials["dg_page"]; nt = m.node_tree
        tex = nt.nodes["page_tex"]; tex.image = bpy.data.images.load(os.path.join(ROOT, fd["files"][fd["default"]]), check_existing=True)
        tex.extension = 'CLIP'; nt.nodes["page_uv"].uv_map = "decal"
        for o in all_meshes(): o.data.uv_layers["decal"].active_render = True; o.data.uv_layers.active = o.data.uv_layers["decal"]
        info = DESIGN["characters"][ch]; r = fd["rectLocal"]
        cam.data.type = 'ORTHO'; cam.data.ortho_scale = (r[2] - r[0]) * 1.6
        cam.location = (info["sheetX"] + (r[0] + r[2]) / 2, -20, (r[1] + r[3]) / 2 + info["sheetY"]); cam.rotation_euler = (math.radians(90), 0, 0)
        sh.light = 'FLAT'; sc.render.film_transparent = True
        render(os.path.join(WORK, f"decal_{ch}.png"))
        sh.light = 'STUDIO'
        look_from(cam, Vector((info["sheetX"], 0, (r[1] + r[3]) / 2 + info["sheetY"])), 35, (r[3] - r[1]) * 5, 0.0, 60)
        render(os.path.join(WORK, f"decal_{ch}_35.png"))
        tex.image = bpy.data.images.load(demo, check_existing=True); tex.extension = 'REPEAT'; nt.nodes["page_uv"].uv_map = "UVMap"
        for o in all_meshes(): o.data.uv_layers["UVMap"].active_render = True; o.data.uv_layers.active = o.data.uv_layers["UVMap"]
    print("UVCHECK done")


def mode_verify():
    out = {}
    for ch in CHARS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"))
        arms = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE']
        meshes = [o for o in bpy.context.scene.objects if o.type == 'MESH' and o.data.users and
                  (o.parent is not None or o.name.startswith(ch))]          # skip the importer's bone-shape icosphere
        bones = sorted(b.name for b in arms[0].data.bones) if arms else []
        want = sorted(CONTRACT_BONES + EXTRA_BONES[ch])
        info = {"armatures": len(arms), "bonesMatch": bones == want, "missing": sorted(set(want) - set(bones)),
                "extra": sorted(set(bones) - set(want)), "actions": len(bpy.data.actions), "meshes": {}}
        rep = json.load(open(os.path.join(WORK, "build_report.json")))["expectedLocalBounds"][ch]
        tris = 0
        for o in meshes:
            skinned = any(m.type == 'ARMATURE' for m in o.modifiers)
            bb = [to_design(o.matrix_world @ Vector(c)) for c in (o.bound_box[0], o.bound_box[6])]
            lo = Vector([min(a, b) for a, b in zip(*bb)]); hi = Vector([max(a, b) for a, b in zip(*bb)])
            exp = rep.get(o.name)
            err = None
            if exp:
                e0 = Vector([min(a, b) for a, b in zip(*exp)]); e1 = Vector([max(a, b) for a, b in zip(*exp)])
                err = round(max((lo - e0).length, (hi - e1).length), 5)
            t = sum(len(p.vertices) - 2 for p in o.data.polygons); tris += t
            maxinf = max((sum(1 for g in v.groups if g.weight > 0) for v in o.data.vertices), default=0)
            info["meshes"][o.name] = {"skinned": skinned, "parentBone": o.parent_bone or None, "tris": t,
                                      "uvLayers": [u.name for u in o.data.uv_layers], "groups": len(o.vertex_groups),
                                      "maxInfluences": maxinf, "bboxErrVsBuild": err}
        info["tris"] = tris; info["trisWithinBudget"] = tris <= DESIGN["modelling"]["trisMax"][ch]
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps(out))


{"build": mode_build, "uvcheck": mode_uvcheck, "verify": mode_verify}[MODE]()
