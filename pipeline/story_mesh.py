"""Shared procedural-mesh helpers for DoodLive story characters (Blender, headless).

Generic pieces of pipeline/dg_build.py (David & Goliath), copied here so any story can use them without importing
dg_build.py (which runs a build mode on import). dg_build.py itself is unchanged and keeps its own copies.

Conventions (same as dg_build.py):
  * design space: x right, y up, z toward the viewer (== glTF); Blender is Z-up, a design point (x, y, z) is Blender
    (x, -z, y); export_yup turns it back;
  * a Cage is a quad cage in design coordinates; every vertex carries skin weights (dict bone -> w), every face a
    region name and a piece index (pieces = separately outlined areas of the printed sheet);
  * units are art-width units (1.0 = width of the sheet's art rectangle).
"""
import bpy, bmesh, math, os, json, random
from mathutils import Vector, Matrix


def sc():
    return bpy.context.scene


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


# Base head (David's, from the D&G turnaround): rows (y, front z, front-side (x, z), side (x, z), back-side (x, z),
# back z) top to bottom; other heads are mapped from it by landmarks (see mapped_head_rows).
BASE_HEAD = [
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
BASE_LAND = dict(top=0.2945, brow=0.2722, eye=0.2672, nose=0.2556, mouth=0.2497, chin=0.241, hw=0.0199, zc=-0.001)


def ellipse_row(y, hx, zf, zb):
    zm = (zf + zb) / 2
    return (y, zf, (0.72 * hx, zm + (zf - zm) * 0.72), (hx, zm), (0.72 * hx, zm + (zb - zm) * 0.72), zb)




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



ARM_ANG = [math.radians(75 - 30 * k) for k in range(12)]     # 12 verts: t0..t5 (back of hand side), b5..b0


def section(c, X, Y, ext, ang, e=2.2):
    ca, sa = math.cos(ang), math.sin(ang)
    x = se(ca, e) * (ext[0] if ca >= 0 else ext[1])
    y = se(sa, e) * (ext[2] if sa >= 0 else ext[3])
    return c + X * x + Y * y



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




# =============================================================================================== heads (generic)
def mapped_head_rows(L, hw, depth=1.05, jaw=0.0, cheek=0.0, chin_narrow=0.0, crown=0.0):
    """Map BASE_HEAD onto new landmarks L (top brow eye nose mouth chin zc), half width hw.
    jaw > 0 squarer/heavier jaw, < 0 softer; cheek > 0 fuller cheeks; chin_narrow > 0 pointier chin;
    crown > 0 taller skull top. Returns rows (top -> bottom, head only)."""
    D = BASE_LAND
    srcY = [D["chin"] - 0.01, D["chin"], D["mouth"], D["nose"], D["eye"], D["brow"], D["top"]]
    sH = (L["top"] - L["chin"]) / (D["top"] - D["chin"])
    dstY = [L["chin"] - 0.01 * sH, L["chin"], L["mouth"], L["nose"], L["eye"], L["brow"], L["top"]]

    def my(y):
        for i in range(len(srcY) - 1):
            if y <= srcY[i + 1] or i == len(srcY) - 2:
                t = (y - srcY[i]) / (srcY[i + 1] - srcY[i]); return lerp(dstY[i], dstY[i + 1], t)
    sx = hw / D["hw"]; sz = sx * depth

    def mz(z): return L["zc"] + (z - D["zc"]) * sz
    rows = []
    for y, zf, fs, s, bs, zb in BASE_HEAD:
        yn = my(y)
        t_jaw = smoothstep(0.2575, 0.2465, y)                        # 0 above the nose, 1 at the chin
        t_chk = math.exp(-((y - 0.2560) / 0.0060) ** 2)              # cheek band
        t_chin = smoothstep(0.2470, 0.2400, y)
        jw = 1.0 + jaw * t_jaw + cheek * t_chk
        fsx = fs[0] * sx * (1.0 + 1.3 * jaw * t_jaw + 0.6 * cheek * t_chk) * (1.0 - chin_narrow * t_chin)
        ssx = s[0] * sx * jw * (1.0 - 0.5 * chin_narrow * t_chin)
        rows.append((yn, mz(zf), (fsx, mz(fs[1])), (ssx, mz(s[1])), (bs[0] * sx * (1 + 0.3 * jaw * t_jaw), mz(bs[1])),
                     mz(zb)))
    if crown:
        rows = [(r[0] + crown * smoothstep(L["brow"], L["top"], r[0]),) + tuple(r[1:]) for r in rows]
    return rows


def face_post_fn(L, hw, zc, nose_h, g=1.0, brow=1.0, lips=1.0, chin=1.0, nose_w=1.0, nose_long=0.0, sockets=1.0,
                 cheekbones=1.0, head=None):
    """Displacement of the subdivided face: nose (bridge, tip, alae, nostrils), brow ridge, shallow eye sockets,
    cheekbones, lips, chin. Same model as dg_build.build_head with per-character factors."""
    H = L["top"] - L["chin"]
    nose_y0 = L["eye"]; nose_tip_y = L["nose"] + 0.10 * H - nose_long * H; nose_bot = L["nose"] - 0.012 * H - nose_long * 0.5 * H
    gw = g * nose_w

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            q = p.copy()
            if p.z > zc and n.z > -0.2:
                x, y = p.x, p.y
                ax = abs(x) / hw
                hmax = nose_h
                if nose_bot - 0.02 * H < y < nose_y0 + 0.03 * H:
                    if y >= nose_tip_y:
                        t = (nose_y0 + 0.03 * H - y) / (nose_y0 + 0.03 * H - nose_tip_y)
                        h = hmax * (0.18 + 0.82 * t ** 1.7); wdt = (0.10 + 0.07 * t) * hw * gw
                    else:
                        t = (nose_tip_y - y) / (nose_tip_y - nose_bot + 0.02 * H)
                        h = hmax * max(0.0, 1 - t ** 1.3); wdt = 0.17 * hw * gw
                    q.z += h * math.exp(-(abs(x) / wdt) ** 2.4)
                    for sx in (-1, 1):
                        q.z += 0.38 * hmax * math.exp(-((x - sx * 0.17 * hw * gw) / (0.085 * hw * gw)) ** 2
                                                      - ((y - (L["nose"] + 0.01 * H - nose_long * 0.6 * H)) / (0.045 * H)) ** 2)
                    q.z -= 0.18 * hmax * math.exp(-((abs(x) - 0.09 * hw * gw) / (0.05 * hw)) ** 2
                                                  - ((y - (L["nose"] - 0.006 * H - nose_long * 0.6 * H)) / (0.02 * H)) ** 2)
                q.z += brow * 0.06 * hw * g * math.exp(-((y - L["brow"]) / (0.045 * H)) ** 2) * smoothstep(0.95, 0.55, ax) \
                    * (1 - 0.45 * math.exp(-(ax / 0.12) ** 2))
                for sx in (-1, 1):
                    q.z -= sockets * 0.045 * hw * math.exp(-((x - sx * 0.40 * hw) / (0.22 * hw)) ** 2 - ((y - L["eye"]) / (0.06 * H)) ** 2)
                for sx in (-1, 1):
                    k = cheekbones * 0.035 * hw * math.exp(-((x - sx * 0.66 * hw) / (0.22 * hw)) ** 2
                                                           - ((y - (L["eye"] - 0.11 * H)) / (0.07 * H)) ** 2)
                    q += n * k
                ym = L["mouth"]
                lw = math.exp(-(abs(x) / (0.30 * hw)) ** 2.6)
                q.z += lips * 0.050 * hw * lw * math.exp(-((y - (ym + 0.030 * H)) / (0.022 * H)) ** 2)
                q.z += lips * 0.060 * hw * lw * math.exp(-((y - (ym - 0.032 * H)) / (0.024 * H)) ** 2)
                q.z -= 0.030 * hw * math.exp(-(abs(x) / (0.28 * hw)) ** 2.6) * math.exp(-((y - ym) / (0.010 * H)) ** 2)
                q.z += chin * 0.05 * hw * math.exp(-(abs(x) / (0.25 * hw)) ** 2 - ((y - (L["chin"] + 0.06 * H)) / (0.045 * H)) ** 2)
            out.append(q)
        return out
    return post


def ear_cage(head, L, sx, ey0, ey1, ew, et, wfn, NA=10, reg="skin", pc=1):
    """Ear (rim + hollow), tilted back, half sunk into the head surface (head = HeadEval). From dg_build.build_ear."""
    eh = (ey1 - ey0) * 1.05
    yc = (ey0 + ey1) / 2
    us = 0.25 if sx > 0 else 0.75
    root = head.at(us, yc)
    nrm = V(sx, 0, -0.25).normalized()
    up = V(0, 1, 0); up = rot_about(up, nrm, math.radians(-sx * 10))
    side = nrm.cross(up).normalized() * sx
    if side.z < 0:
        side = -side
    cg = Cage()
    centre = root + nrm * (et * 0.10) + V(0, 0, -0.10 * ew)
    prof = [(1.00, 0.0), (0.88, 0.60), (0.62, 0.45), (0.30, -0.05)]
    rings = []
    for rfrac, hfrac in prof:
        pts = []
        for j in range(NA):
            a = 2 * math.pi * j / NA
            ry = eh / 2 * (1.0 if math.sin(a) > 0 else 0.92)
            rx = ew / 2 * (1.0 + 0.15 * math.sin(a)) * (0.85 if math.cos(a) > 0 else 1.0)
            pts.append(centre + up * (math.sin(a) * ry * rfrac) + side * (math.cos(a) * rx * rfrac) + nrm * (hfrac * et))
        rings.append(cg.ring(pts, wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(rings[-1], centre + nrm * (-0.15 * et), wfn, reg, pc)
    pts = [centre + (cg.v[i] - centre) * 0.70 + nrm * (-0.65 * et) - nrm * ((cg.v[i] - centre).dot(nrm)) * 0.70
           for i in rings[0]]
    r = cg.ring(pts, wfn); cg.bridge(r, rings[0], reg, pc)
    cg.fan(r, centre - nrm * (et * 1.1), wfn, reg, pc)
    return cg


# =============================================================================================== tubes / blobs
def frame_along(path, ref=None):
    """Parallel-transport frames (T, A, B) along a polyline; A starts perpendicular to ref (default +Z)."""
    ref = ref or V(0, 0, 1)
    out = []
    A = None
    for i, p in enumerate(path):
        T = (path[min(i + 1, len(path) - 1)] - path[max(i - 1, 0)]).normalized()
        if A is None:
            A = perp(ref, T)
            if A.length < 1e-6:
                A = perp(V(1, 0, 0), T)
        else:
            A = perp(A, T)
        out.append((T, A, T.cross(A)))
    return out


def tube(cg, path, radii, N, wfn, reg, pc=0, ref=None, cap0=True, cap1=True, e=2.0, squash=1.0, twist=0.0,
         regfn=None, cap_len=0.6):
    """Tube along a path; radii per path point (float or (ra, rb)); squash scales the B axis. Returns ring list."""
    fr = frame_along(path, ref)
    rings = []
    for i, (p, (T, A, B)) in enumerate(zip(path, fr)):
        r = radii[i]
        ra, rb = (r, r * squash) if not isinstance(r, (tuple, list)) else r
        tw = twist * i
        rings.append(cg.ring([p + A * (se(math.cos(2 * math.pi * j / N + tw), e) * ra)
                              + B * (se(math.sin(2 * math.pi * j / N + tw), e) * rb) for j in range(N)], wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc, regfn=regfn)
    if cap0:
        r0 = radii[0] if not isinstance(radii[0], (tuple, list)) else radii[0][0]
        cg.fan(rings[0], path[0] - fr[0][0] * r0 * cap_len, wfn, reg, pc)
    if cap1:
        r1 = radii[-1] if not isinstance(radii[-1], (tuple, list)) else radii[-1][0]
        cg.fan(rings[-1], path[-1] + fr[-1][0] * r1 * cap_len, wfn, reg, pc)
    return rings


def blob(cg, c, rx, ry, rz, wfn, reg, pc=0, NU=8, NV=5, ax=None):
    """Closed ellipsoid-ish blob (UV sphere cage) centred at c; ax = optional 3x3 matrix (columns x, y, z axes)."""
    M = ax or Matrix.Identity(3)
    rings = []
    for j in range(1, NV):
        th = math.pi * j / NV
        rings.append(cg.ring([c + M @ V(math.sin(th) * math.cos(2 * math.pi * k / NU) * rx, math.cos(th) * ry,
                                        math.sin(th) * math.sin(2 * math.pi * k / NU) * rz) for k in range(NU)], wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(rings[0], c + M @ V(0, ry, 0), wfn, reg, pc)
    cg.fan(list(reversed(rings[-1])), c + M @ V(0, -ry, 0), wfn, reg, pc)
    return rings


def extrude_outline(cg, outline, depth, wfn, reg, pc=0, z0=0.0, bevel=0.0, origin=None, X=None, Y=None, Z=None):
    """Flat prism from a closed 2D outline [(x, y)] in the plane (origin, X, Y), from z0 to z0 + depth along Z, with
    an optional bevel (inset of the front/back rims). Front and back are triangle fans to the centroid."""
    O = origin or V(); X = X or V(1, 0, 0); Y = Y or V(0, 1, 0); Z = Z or V(0, 0, 1)
    cx = sum(p[0] for p in outline) / len(outline); cy = sum(p[1] for p in outline) / len(outline)

    def P(x, y, z): return O + X * x + Y * y + Z * z
    layers = []
    if bevel:
        ins = [(cx + (x - cx) * (1 - bevel), cy + (y - cy) * (1 - bevel)) for x, y in outline]
        layers = [(ins, z0), (outline, z0 + depth * 0.25), (outline, z0 + depth * 0.75), (ins, z0 + depth)]
    else:
        layers = [(outline, z0), (outline, z0 + depth)]
    rings = [cg.ring([P(x, y, z) for x, y in pts], wfn) for pts, z in layers]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(list(reversed(rings[0])), P(cx, cy, z0), wfn, reg, pc)
    cg.fan(rings[-1], P(cx, cy, z0 + depth), wfn, reg, pc)
    return rings


# =============================================================================================== Blender scene
def new_mesh_obj(name, verts_bl, faces):
    me = bpy.data.meshes.new(name); me.from_pydata([tuple(v) for v in verts_bl], [], faces); me.update()
    o = bpy.data.objects.new(name, me); sc().collection.objects.link(o)
    return o


def fix_normals(o, outward=True):
    bm = bmesh.new(); bm.from_mesh(o.data)
    loose = [v for v in bm.verts if not v.link_faces]
    if loose: bmesh.ops.delete(bm, geom=loose, context='VERTS')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if outward:
        cen = sum((v.co for v in bm.verts), Vector()) / max(1, len(bm.verts))
        score = sum(f.normal.dot(f.calc_center_median() - cen) * f.calc_area() for f in bm.faces)
        if score < 0:
            for f in bm.faces: f.normal_flip()
    bm.to_mesh(o.data); bm.free()
    for poly in o.data.polygons: poly.use_smooth = True


def make_armature(name, bones, order):
    """bones: name -> (head V, tail V, parent) in design coords. Local Z of every bone points to the viewer (+Z)
    where the bone is not along Z (limb flexion = rotation about local X), as in dg_build."""
    arm = bpy.data.armatures.new(name)
    o = bpy.data.objects.new(name, arm); sc().collection.objects.link(o)
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.mode_set(mode='EDIT')
    for nm in order:
        h, t, parent = bones[nm]
        eb = arm.edit_bones.new(nm); eb.head = to_bl(h); eb.tail = to_bl(t)
        dirn = (eb.tail - eb.head).normalized()
        eb.align_roll(Vector((0, -1, 0)) if abs(dirn.y) < 0.9 else Vector((0, 0, 1)))
        if parent:
            eb.parent = arm.edit_bones[parent]
            eb.use_connect = (eb.parent.tail - eb.head).length < 1e-6
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def apply_modifier(o, m):
    bpy.context.view_layer.objects.active = o
    bpy.ops.object.select_all(action='DESELECT'); o.select_set(True)
    bpy.ops.object.modifier_apply(modifier=m.name)


def apply_solidify(o, th, offset=-1.0):
    m = o.modifiers.new("solid", 'SOLIDIFY'); m.thickness = th; m.offset = offset; m.use_even_offset = False
    m.use_rim = True
    apply_modifier(o, m)


def apply_subsurf(o, levels=1):
    m = o.modifiers.new("subd", 'SUBSURF'); m.levels = levels; m.render_levels = levels; m.quality = 3
    m.uv_smooth = 'NONE'; m.boundary_smooth = 'ALL'
    apply_modifier(o, m)


def tri_count(objs):
    return sum(sum(len(p.vertices) - 2 for p in o.data.polygons) for o in objs)


def srgb_to_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#"); return tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4))


def flat_mat(name, srgb):
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.diffuse_color = (*[srgb_to_lin(c) for c in srgb], 1.0)
    return m


def id_colour(k):
    """ID k -> sRGB bytes, decodable after Standard view transform (same scheme as tools/make_dg_sheet.py)."""
    return (16 + (k % 15) * 16, 16 + ((k // 15) % 15) * 16, 64 + (k // 225) * 64)


def camera(name="Cam"):
    cam = bpy.data.objects.get(name)
    if not cam:
        cam = bpy.data.objects.new(name, bpy.data.cameras.new(name)); sc().collection.objects.link(cam)
    sc().camera = cam; cam.data.clip_start = 0.005; cam.data.clip_end = 100
    return cam


def look_from(cam, target, yaw_deg, dist, height, lens=60):
    """Perspective camera at yaw (0 = in front, +Z design), distance, height above target; target in Blender coords."""
    cam.data.type = 'PERSP'; cam.data.lens = lens
    a = math.radians(yaw_deg)
    cam.location = target + Vector((math.sin(a) * dist, -math.cos(a) * dist, height))
    cam.rotation_euler = (target - cam.location).to_track_quat('-Z', 'Y').to_euler()


def render(path):
    sc().render.filepath = path; bpy.ops.render.render(write_still=True)


# =============================================================================================== UVs
def front_uv_with_occlusion(objs, sheet_xy, art_h, inset, anchors=None, region_name=None):
    """UV0 = front orthographic page projection u = x + sheetX + 0.5, v = (y + sheetY) / artH (character-local x, y),
    with an inward inset at silhouettes (as dg_build). Improvement over dg_build: a face corner whose vertex is hidden
    in the front view behind a DIFFERENT part or region (ray toward the viewer hits it) samples the nearest visible
    vertex of its own part + region instead, so e.g. the back of a cape is not painted with the robe colour in front of
    it. anchors: {region: target region} = constant UV (deep inside the target's visible area) for whole regions too
    small to colour (rings, beads, ...).
    objs: list of (object, rigid bool); objects are in rest pose at their sheet position; face attributes
    'st_piece' (part piece key index) and 'st_region' (region id) must exist.
    Returns stats."""
    from mathutils.bvhtree import BVHTree
    from mathutils.kdtree import KDTree
    sX, sY = sheet_xy
    off = V(sX, sY, 0)
    allv, allf, freg, fpart = [], [], [], []
    for o, _ in objs:
        me = o.data; base = len(allv)
        allv += [to_design(o.matrix_world @ v.co) - off for v in me.vertices]
        rid = [0] * len(me.polygons); pid = [0] * len(me.polygons)
        me.attributes["st_region"].data.foreach_get("value", rid); me.attributes["st_piece"].data.foreach_get("value", pid)
        for poly, r, p in zip(me.polygons, rid, pid):
            allf.append([base + i for i in poly.vertices]); freg.append(r); fpart.append((o.name, p))
    bvh = BVHTree.FromPolygons([tuple(v) for v in allv], allf, all_triangles=False, epsilon=0.0)
    stats = {"hiddenCorners": 0, "corners": 0}

    def first_hit(p, n):
        o = p + V(0, 0, 1) * 0.00035 + n * 0.00012
        hit = bvh.ray_cast(o, V(0, 0, 1), 10.0)
        return hit[2]
    # pass 1: visible vertices per (part, region) -> KD trees
    per_obj = []
    for o, rigid in objs:
        me = o.data
        vco = [to_design(o.matrix_world @ v.co) - off for v in me.vertices]
        vn = [(to_design((o.matrix_world.to_3x3() @ v.normal)).normalized()) for v in me.vertices]
        rid = [0] * len(me.polygons); pid = [0] * len(me.polygons)
        me.attributes["st_region"].data.foreach_get("value", rid); me.attributes["st_piece"].data.foreach_get("value", pid)
        hits = [first_hit(p, n) for p, n in zip(vco, vn)]
        per_obj.append((o, rigid, vco, vn, rid, pid, hits))
    visible = {}
    for o, rigid, vco, vn, rid, pid, hits in per_obj:
        me = o.data
        for fi, poly in enumerate(me.polygons):
            key = (o.name, pid[fi], rid[fi])
            for vi in poly.vertices:
                h = hits[vi]
                ok = h is None or (freg[h] == rid[fi] and fpart[h] == (o.name, pid[fi]))
                if ok and vn[vi].z > 0.05:
                    visible.setdefault(key, {})[vi] = vco[vi]
    anchor_uv = {}
    if anchors:
        # the anchor of a region = the visible vertex of the target region farthest (in x, y) from other regions
        byreg = {}
        for (oname, p, r), d in visible.items():
            for vi, q in d.items():
                byreg.setdefault(r, []).append(q)
        for reg, target in anchors.items():
            tid = [r for r in byreg if region_name(r) == target]
            if not tid:
                continue
            others = [q for r, lst in byreg.items() if r not in tid for q in lst]
            kd = KDTree(len(others))
            for i, q in enumerate(others): kd.insert(V(q.x, q.y, 0), i)
            kd.balance()
            best, bd = None, -1
            for r in tid:
                for q in byreg[r]:
                    dd = kd.find(V(q.x, q.y, 0))[2]
                    if dd > bd: bd, best = dd, q
            anchor_uv[reg] = (best.x + sX + 0.5, (best.y + sY) / art_h)
            stats.setdefault("anchors", {})[reg] = {"target": target, "uv": [round(anchor_uv[reg][0], 5), round(anchor_uv[reg][1], 5)],
                                                    "clearance": round(bd, 5)}
    kds = {}
    for key, d in visible.items():
        kd = KDTree(len(d))
        for i, (vi, p) in enumerate(d.items()):
            kd.insert(p, vi)
        kd.balance(); kds[key] = kd
    for o, rigid, vco, vn, rid, pid, hits in per_obj:
        me = o.data
        uv0 = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")

        def proj(p, n):
            return (p.x + sX + 0.5 - n.x * inset, (p.y + sY - n.y * inset) / art_h)
        for fi, poly in enumerate(me.polygons):
            key = (o.name, pid[fi], rid[fi])
            rname = region_name(rid[fi]) if region_name else None
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                stats["corners"] += 1
                if rname in anchor_uv:
                    uv0.data[li].uv = anchor_uv[rname]; continue
                h = hits[vi]
                ok = h is None or (freg[h] == rid[fi] and fpart[h] == (o.name, pid[fi]))
                if ok or key not in kds:
                    uv0.data[li].uv = proj(vco[vi], vn[vi])
                else:
                    stats["hiddenCorners"] += 1
                    _, vj, _ = kds[key].find(vco[vi])
                    q = vco[vj]; nq = vn[vj]
                    uv0.data[li].uv = proj(q, V(nq.x, nq.y, 0) * 2.0)     # a little deeper inside the region
        me.uv_layers.active = uv0
    return stats
