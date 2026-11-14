"""Gabriel skeletal animation (Animation role, story pack "gabriel": the archangel).

Adapted from pipeline/da_animate.py (Daniel): same clip-function method, IK with rolling foot contact, spring chains,
settle, loop closing, export, verify, contact sheet and freshness check, plus a wing layer for the hero:

* Wing poses per bone (`wing?1` shoulder, `wing?2` forearm, `wing?3` hand, `wing?_prim` primary fan) are rotations
  about the character's Z (in the wing plane: up / down) and Y (fore / aft), applied Z first then Y (docs/gabriel/RIG.md
  §4: the fold only looks right in that order), plus a twist about the bone (feathering). Right wing = mirrored.
* `flap(p)`: one wing beat as a function of the phase p (0 = top of the stroke). Down-stroke 55 % of the cycle with
  the wing fully extended and the primaries spread, up-stroke with the wing partly folded and the fan closed; every
  segment lags its parent (wing1 -> 2 -> 3 -> prim) so the tips whip through the turns, and the feathers twist with
  the air flow. The body rises on the down-stroke (root / chest react).
* Damped spring chains on wing?2 / wing?3 / wing?_prim give follow-through and the feather settle after a stop;
  hair1-2 and sash1-2 as in Daniel.
* The trumpet: the mouthpiece is held at the lips in head space (the RIG.md §4 solve), the arm follows by IK.

    python3 pipeline/ga_animate.py all        # build + verify + contact sheet + freshness check
    python3 pipeline/ga_animate.py build      # actions + anim/gabriel.glb + anim/clips.json (with checks)
    python3 pipeline/ga_animate.py verify     # re-import the GLB: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/ga_animate.py contact    # anim/contact_sheet.png
    python3 pipeline/ga_animate.py fresh      # are the model files newer than the anim export?
    GA_PROBE="hover:0,9,18,27:front;fly_down:126:side" python3 pipeline/ga_animate.py probe   # $GA_ANIM_WORK/probe.png
    GA_ONLY=hover,fly_down  (with build: bake + check a subset, no export)

Intermediates: $GA_ANIM_WORK (default /tmp/gabriel_anim).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GA = os.path.join(ROOT, "assets/gabriel")
MODEL = os.path.join(GA, "model")
ANIM = os.path.join(GA, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
MODEL_GLB = os.path.join(MODEL, "gabriel.glb")
SET_GLB = os.path.join(MODEL, "heaven.glb")
TIMELINE = os.path.join(GA, "timeline.json")
REGIONS_JSON = os.path.join(MODEL, "regions_characters.json")
FACE_DIR = os.path.join(ROOT, "docs/gabriel/design/faces")
WORK = os.environ.get("GA_ANIM_WORK") or "/tmp/gabriel_anim"
BLENDER = os.environ.get("BLENDER") or ("/Applications/Blender.app/Contents/MacOS/Blender"
                                        if os.path.exists("/Applications/Blender.app/Contents/MacOS/Blender") else "blender")
FPS = 30
CHARS = ("gabriel",)
LIONS = ()

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


# =============================================================================================== orchestration (python3)
def run_blender(mode, *extra):
    cmd = [BLENDER, "-b", "--factory-startup", "--python", os.path.abspath(__file__), "--", mode, *extra]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith(("GA_", "Traceback", "Error", "  File")) or "Error" in ln]
    print("\n".join(tail[-300:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def compose_contact():
    from PIL import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(WORK, "contact", "contact.json")))
    cell, pad, lab = 170, 6, 34
    rows = meta["rows"]
    ncol = max(len(r["frames"]) for r in rows)
    W = 250 + ncol * (cell + pad) + pad
    H = 60 + len(rows) * (cell + lab + pad)
    sheet = Image.new("RGB", (W, H), (250, 246, 236))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 17)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((pad, 14), "Gabriel - key poses per clip (30 fps; frame / seconds / root height; markers in red; "
                      "* = extra clip; camera follows the root)", fill=(40, 30, 20), font=font)
    y = 60
    for r in rows:
        d.text((pad, y + 6), r["action"] + (" *" if r.get("extra") else ""), fill=(40, 30, 20), font=font)
        d.text((pad, y + 30), f"{r['frames_total']} f  {r['frames_total'] / FPS:.2f} s", fill=(90, 80, 70), font=small)
        d.text((pad, y + 48), ("loop" if r["loop"] else "one-shot (holds last)") + f"   view {r.get('view', 'q3')}",
               fill=(90, 80, 70), font=small)
        x = 250
        for fr in r["frames"]:
            im = Image.open(os.path.join(WORK, "contact", fr["file"])).convert("RGB").resize((cell, cell))
            sheet.paste(im, (x, y))
            d.text((x + 4, y + cell + 2), f"f{fr['f']}  {fr['f'] / FPS:.2f}s  y{fr.get('ry', 0):.2f}", fill=(60, 50, 40), font=small)
            if fr.get("marker"):
                d.text((x + 4, y + cell + 17), fr["marker"], fill=(200, 30, 30), font=small)
            x += cell + pad
        y += cell + lab + pad
    out = os.path.join(ANIM, "contact_sheet.png")
    sheet = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    sheet.save(out, optimize=True)
    print("GA_CONTACT", out, sheet.size)


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get("GA_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("GA_PROBE_OUT", "probe.png"))
    sheet.save(out); print("GA_PROBE_SHEET", out)


def main_cli():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(WORK, exist_ok=True); os.makedirs(ANIM, exist_ok=True)
    if mode in ("build", "all"):
        run_blender("build")
    if mode in ("verify", "all"):
        run_blender("verify")
    if mode in ("contact", "all"):
        run_blender("contact"); compose_contact()
    if mode == "probe":
        run_blender("probe"); compose_probe()
    if mode == "compose":
        compose_contact()
    if mode == "debug":
        run_blender("debug")
    if mode in ("fresh", "all"):
        fresh_check()


def fresh_check():
    """The Character role may re-run ga_character.py (same bones, new mesh / UVs): the anim GLB must be newer."""
    src = [BLEND, MODEL_GLB, REGIONS_JSON]
    newest = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    outs = [os.path.join(ANIM, "gabriel.glb"), os.path.join(ANIM, "clips.json")]
    stale = [o for o in outs if (not os.path.exists(o)) or os.path.getmtime(o) < newest]
    print("GA_FRESH", "STALE " + ", ".join(os.path.basename(o) for o in stale) if stale else "OK (anim exports newer than the model files)")
    return not stale


if not IN_BLENDER:
    if __name__ == "__main__":
        main_cli()
    sys.exit(0) if __name__ == "__main__" else None


# =============================================================================================== Blender half
import bpy  # noqa: E402
from mathutils import Vector, Matrix, Quaternion  # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
TL = json.load(open(TIMELINE))
REGIONS = json.load(open(REGIONS_JSON))
C = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))          # design -> Blender: (x, y, z) -> (x, -z, y)
CI = C.transposed()


def V(x=0.0, y=0.0, z=0.0):
    return Vector((float(x), float(y), float(z)))


def to_bl(p):
    return C @ Vector(p)


def to_d(p):
    return CI @ Vector(p)


def rot_d(axis_d, deg):
    """Rotation (3x3, Blender coords) about a design-space axis."""
    return Matrix.Rotation(math.radians(deg), 3, (C @ Vector(axis_d)).normalized())


# ----------------------------------------------------------------------------------------------- curves
def smooth(t):
    t = min(1.0, max(0.0, t)); return t * t * (3 - 2 * t)


def lerp(a, b, t):
    return a + (b - a) * t


def K(keys, f, N=None, loop=False):
    """Catmull-Rom through [(frame, value)], clamped (or wrapped when loop: the key at N should equal the key at 0)."""
    ks = sorted(keys)
    if len(ks) == 1:
        return ks[0][1]
    if loop:
        f = f % N
        core = [k for k in ks if k[0] < N]
        ext = [(k[0] - N, k[1]) for k in core[-2:]] + core + [(k[0] + N, k[1]) for k in core[:3]]
        ks = ext
    else:
        if f <= ks[0][0]:
            return ks[0][1]
        if f >= ks[-1][0]:
            return ks[-1][1]
        ks = [(2 * ks[0][0] - ks[1][0], ks[0][1])] + ks + [(2 * ks[-1][0] - ks[-2][0], ks[-1][1])]
    for i in range(1, len(ks) - 2):
        (f1, p1), (f2, p2) = ks[i], ks[i + 1]
        if f1 <= f <= f2:
            (f0, p0), (f3, p3) = ks[i - 1], ks[i + 2]
            dt = f2 - f1
            t = (f - f1) / dt if dt else 0.0
            m1 = (p2 - p0) / (f2 - f0) * dt if f2 != f0 else 0.0
            m2 = (p3 - p1) / (f3 - f1) * dt if f3 != f1 else 0.0
            t2, t3 = t * t, t * t * t
            return (2 * t3 - 3 * t2 + 1) * p1 + (t3 - 2 * t2 + t) * m1 + (-2 * t3 + 3 * t2) * p2 + (t3 - t2) * m2
    return ks[-1][1]


def KL(keys, f, N=None, loop=False, lag=0.0):
    return K(keys, f - lag, N, loop)


def wave(f, N, cycles=1.0, phase=0.0):
    return math.sin(2 * math.pi * (cycles * f / N + phase))


def ease_io(t):
    t = min(1.0, max(0.0, t)); return 0.5 - 0.5 * math.cos(math.pi * t)


def ease_out(t):
    t = min(1.0, max(0.0, t)); return 1 - (1 - t) ** 3


def bump(f, a, b):
    if f <= a or f >= b:
        return 0.0
    return math.sin(math.pi * smooth((f - a) / (b - a)))


def ring(f, at, period=5.0, decay=6.0):
    """Decaying oscillation starting at frame `at` (feather shake / settle): 0 before, sin * exp after."""
    d = f - at
    if d <= 0:
        return 0.0
    return math.sin(2 * math.pi * d / period) * math.exp(-d / decay) * min(1.0, d / 1.5)


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


# ----------------------------------------------------------------------------------------------- acting helpers
LID = 20.0                                                   # eyelids local-Y scale: closed (RIG.md §3)
BLINK_SHAPE = [1.0, 10.5, 20.0, 20.0, 12.6, 5.6, 1.0]        # fast close, short hold, slower open


def blink(c, f, N, at, loop=True, base=1.0, slow=1.0):
    s = base
    for b in at:
        d = (f - b) % N if loop else f - b
        u = d / slow
        if 0 <= u < len(BLINK_SHAPE) - 1:
            i = int(u); w = u - i
            s = max(s, lerp(BLINK_SHAPE[i], BLINK_SHAPE[i + 1], w))
    c["eyelids.sy"] = s


def syllables(N, seed, amp=(6.0, 15.0), dur=(3.0, 6.5), gap=0.2, lead=3, tail=5):
    r = random.Random(seed)
    keys = [(0, 0.0)]
    t = float(lead)
    beats = []
    while t < N - tail - dur[0]:
        d = r.uniform(*dur)
        a = r.uniform(*amp)
        if r.random() < 0.22:
            a *= 0.45
        peak = t + d * r.uniform(0.35, 0.55)
        keys.append((peak, a)); keys.append((t + d, r.uniform(0.0, 2.5)))
        if a > amp[0] + 0.70 * (amp[1] - amp[0]):
            beats.append(peak)
        t += d
        if r.random() < gap:
            t += r.uniform(5, 13)
            keys.append((t - 1, 0.0))
    keys.append((N, 0.0))
    return sorted(keys), beats


def jaw_from(keys, f, N):
    return max(0.0, K(keys, f % N, N, False))


def beat_curve(beats, f, N, width=7.0, loop=True):
    v = 0.0
    for b in beats:
        d = f - b
        if loop:
            d = (d + N / 2) % N - N / 2
        if -0.4 * width <= d <= 0.6 * width:
            u = (d + 0.4 * width) / width
            v = max(v, math.sin(math.pi * u))
    return v


def addc(c, k, v):
    c[k] = c.get(k, 0.0) + v


# =============================================================================================== rig model (pure python FK)
class Rig:
    H_OF = {"gabriel": 0.62}

    def __init__(self, ch, obj):
        self.ch, self.obj = ch, obj
        bones = obj.data.bones

        def depth(b):
            n = 0
            while b.parent:
                b = b.parent; n += 1
            return n
        self.names = [b.name for b in sorted(bones, key=depth)]
        self.parent = {b.name: (b.parent.name if b.parent else None) for b in bones}
        self.rest = {b.name: b.matrix_local.copy() for b in bones}
        self.rest3 = {n: m.to_3x3() for n, m in self.rest.items()}
        self.rel = {n: (self.rest[self.parent[n]].inverted() @ self.rest[n]) if self.parent[n] else self.rest[n].copy() for n in self.names}
        self.head = {n: to_d(self.rest[n].translation) for n in self.names}
        self.tail = {b.name: to_d(b.tail_local) for b in bones}
        self.dir = {n: (self.tail[n] - self.head[n]).normalized() for n in self.names}
        self.length = {b.name: b.length for b in bones}
        self.children = {n: [c for c in self.names if self.parent[c] == n] for n in self.names}
        self.H = self.H_OF[ch]
        self.quad = False
        body = bpy.data.objects[f"{ch}_body"]
        mw = obj.matrix_world.inverted() @ body.matrix_world
        gname = {g.index: g.name for g in body.vertex_groups}
        vs = body.data.vertices
        self.proxy = []
        for i in range(len(vs)):
            v = vs[i]
            ws = [(gname[g.group], g.weight) for g in v.groups if g.weight > 1e-3 and gname.get(g.group) in self.rest]
            tot = sum(w for _, w in ws)
            if tot <= 0:
                continue
            ws = [(b, w / tot) for b, w in ws]
            dom = max(ws, key=lambda q: q[1])[0]
            # keep every leg / foot vertex (ground contact) and a thin sample of the rest
            if dom in LEG_BONES or i % 25 == 0:
                self.proxy.append((mw @ v.co, ws, dom))
        self.rest_inv = {n: m.inverted() for n, m in self.rest.items()}

    def skin(self, M, bones=None):
        out = []
        for co, ws, dom in self.proxy:
            if bones is not None and dom not in bones:
                continue
            p = Vector((0, 0, 0))
            for b, w in ws:
                p += w * ((M[b] @ self.rest_inv[b]) @ co)
            out.append(to_d(p))
        return out

    def basis_from(self, chs):
        out = {}
        for n in self.names:
            g = lambda k: chs.get(f"{n}.{k}", 0.0)
            d = self.dir[n]
            R = Matrix.Identity(3)
            sx = 1.0 if d.x >= 0 else -1.0
            if g("rx"): R = R @ rot_d((1, 0, 0), g("rx"))
            if g("ry"): R = R @ rot_d((0, 1, 0), g("ry"))
            if g("rz"): R = R @ rot_d((0, 0, 1), g("rz"))
            if g("swing"): R = R @ rot_d((0, -sx, 0), g("swing"))
            if g("raise"): R = R @ rot_d((0, 0, sx), g("raise"))
            if g("curl") and n[:-1] == "fingers":
                dh = self.dir["hand" + n[-1]]
                hz = dh.cross(V(0, 0, 1)).normalized()
                R = R @ rot_d(hz if n[-1] == "L" else -hz, g("curl"))
            if g("bend"):
                ax = d.cross(V(0, 0, 1))
                if ax.length < 1e-6:
                    ax = V(1, 0, 0)
                R = R @ rot_d(ax, g("bend"))
            if g("twist"): R = R @ rot_d(d, g("twist"))
            Rr = self.rest3[n]
            q = (Rr.inverted() @ R @ Rr).to_quaternion()
            if f"{n}.q" in chs:                          # raw pose quaternion override (RIG.md solved poses)
                q = Quaternion(chs[f"{n}.q"])
            off = V(g("tx"), g("ty"), g("tz"))
            loc = Rr.inverted() @ (C @ off) if off.length else Vector((0, 0, 0))
            s = chs.get(f"{n}.s", 1.0)
            sc = Vector((s, chs.get(f"{n}.sy", s), s))
            out[n] = [q, loc, sc]
        return out

    def fk(self, basis, M=None, only=None):
        M = {} if M is None else M
        names = self.names if only is None else [n for n in self.names if n in only]
        for n in names:
            q, loc, s = basis[n]
            B = Matrix.Translation(loc) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((s[0], s[1], s[2], 1.0))
            p = self.parent[n]
            M[n] = (M[p] @ self.rel[n] @ B) if p else (self.rel[n] @ B)
        return M

    def subtree(self, n):
        out, st = set(), [n]
        while st:
            x = st.pop(); out.add(x); st += self.children[x]
        return out

    def carried(self, M, n):
        p = self.parent[n]
        return (M[p] @ self.rel[n]) if p else self.rel[n].copy()

    def set_world_rot(self, basis, M, n, R_world3):
        Cm = self.carried(M, n).to_3x3().normalized()
        basis[n][0] = (Cm.inverted() @ R_world3).to_quaternion()
        self.fk(basis, M, only=self.subtree(n))

    def pos(self, M, n, at="head"):
        m = M[n]
        if at == "head":
            return to_d(m.translation)
        return to_d(m @ Vector((0, self.length[n], 0)))

    def point(self, M, n, p_rest_d):
        """A rest-pose point (design coords) carried by bone n."""
        return to_d((M[n] @ self.rest_inv[n]) @ to_bl(p_rest_d))


LEG_BONES = {"thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR"}


def frame_from(Y_d, Z_d):
    Y = (C @ Y_d).normalized()
    Z = (C @ Z_d)
    Z = (Z - Y * Z.dot(Y)).normalized()
    X = Y.cross(Z)
    return Matrix((X, Y, Z)).transposed()


def ik2(rig, basis, M, upper, lower, target_d, pole_d, legs):
    H = rig.pos(M, upper)
    L1, L2 = rig.length[upper], rig.length[lower]
    T = Vector(target_d)
    dvec = T - H
    d = max(1e-6, min(dvec.length, (L1 + L2) * 0.9995))
    u = dvec.normalized()
    a = (L1 * L1 - L2 * L2 + d * d) / (2 * d)
    h = math.sqrt(max(0.0, L1 * L1 - a * a))
    p = Vector(pole_d) - u * Vector(pole_d).dot(u)
    p = p.normalized() if p.length > 1e-6 else V(0, 0, 1)
    Kn = H + u * a + p * h
    zu = p if legs else -p
    Ru = frame_from(Kn - H, zu)
    rig.set_world_rot(basis, M, upper, Ru)
    X = Ru.col[0]
    Yl = (C @ (T - Kn)).normalized()
    Zl = X.cross(Yl)
    Rl = Matrix((X, Yl, Zl)).transposed()
    rig.set_world_rot(basis, M, lower, Rl)
    return Kn


# =============================================================================================== clip library
class Clip:
    def __init__(self, ch, name, N, loop, fn, markers=None, notes="", extra=False, speed=None, props=None, info=None,
                 auto_markers=None):
        self.info = info or {}
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = dict(markers or {})
        self.auto_markers = auto_markers or {}    # name -> "land" | "takeoff": measured from the baked feet
        self.notes = notes
        self.extra = extra
        self.speed = speed
        self.props = props or []

    @property
    def action(self):
        return f"{self.ch}_{self.name}"

    @property
    def natural_speed(self):
        if not self.speed:
            return None
        L, duty = self.speed
        return L / (duty * self.N / FPS)


CLIPS = []


def clip(ch, name, N, loop, **kw):
    def deco(fn):
        CLIPS.append(Clip(ch, name, N, loop, fn, **kw))
        return fn
    return deco


# ----------------------------------------------------------------------------------------------- legs
def foot_points(rig, side):
    a = rig.head["foot" + side]
    ball = rig.head["toe" + side] - a
    tip = rig.tail["toe" + side] - a
    heel = V(0, -a.y + 0.001, -0.18 * ball.z)
    return heel, ball, tip


_PAY = {}


def planted_ankle_y(rig, side, pitch_deg):
    key = (rig.ch, side, round(pitch_deg, 3))
    if key not in _PAY:
        R = rot_d((1, 0, 0), pitch_deg)
        low = min((CI @ (R @ (C @ p))).y for p in foot_points(rig, side))
        _PAY[key] = -low
    return _PAY[key]


def pivot_dz(rig, side, pitch):
    heel, ball, _ = foot_points(rig, side)
    q = heel if pitch < 0 else ball
    R = rot_d((1, 0, 0), pitch)
    return (CI @ (R @ (C @ q))).z - q.z


def gait(rig, f, N, L, lift, duty, offsetR=0.5, offsetL=0.0, heel=10.0, toeoff=24.0, out=None, spread=0.0, fwd=0.0):
    out = out if out is not None else {}
    for side, off in (("L", offsetL), ("R", offsetR)):
        p = (f / N + off) % 1.0
        base = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        if p < duty:
            s = p / duty
            z = L / 2 - L * s
            pitch = -heel * (1 - smooth(s / 0.15)) + toeoff * smooth((s - 0.7) / 0.3)
            y = planted_ankle_y(rig, side, pitch)
        else:
            s = (p - duty) / (1 - duty)
            z = -L / 2 + L * smooth(s)
            pitch = lerp(toeoff, -heel, smooth(s * 1.1))
            y = planted_ankle_y(rig, side, pitch) + lift * math.sin(math.pi * min(1.0, s))
        z -= pivot_dz(rig, side, pitch)
        out["leg" + side] = (V(base.x + sx * spread, y, base.z + z + fwd), pitch)
    return out


def legs_ik_channels(chs, g):
    for side in "LR":
        t, pitch = g["leg" + side]
        chs[f"ik.leg{side}"] = t
        chs[f"foot{side}.pitch"] = pitch


def stand_feet(rig, chs, spread=0.004, fwdL=0.0, fwdR=0.0, pitchL=0.0, pitchR=0.0, liftL=0.0, liftR=0.0, xL=0.0, xR=0.0):
    for side, fw, pt, lf, xo in (("L", fwdL, pitchL, liftL, xL), ("R", fwdR, pitchR, liftR, xR)):
        b = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        chs[f"ik.leg{side}"] = V(b.x + sx * spread + xo, planted_ankle_y(rig, side, pt) + lf, b.z + fw)
        chs[f"foot{side}.pitch"] = pt


def arm_ik(c, side, target, pole=None, space="root", w=1.0):
    c[f"ik.arm{side}"] = Vector(target)
    c[f"ikspace.arm{side}"] = space
    c[f"ikw.arm{side}"] = w
    if pole is not None:
        c[f"pole.arm{side}"] = Vector(pole)


def fingers(c, side, curl):
    c[f"fingers{side}.curl"] = curl


def kneel_geom(rig, side, KY=0.03, kz=0.0, thigh_back=0.0, shin_slope=10.0, spread=0.004):
    sx = 1 if side == "L" else -1
    th, sh = rig.length["thigh" + side], rig.length["shin" + side]
    knee = V(rig.head["shin" + side].x + sx * spread, KY, kz)
    tb, ss = math.radians(thigh_back), math.radians(shin_slope)
    hip = knee + V(0, th * math.cos(tb), -th * math.sin(tb))
    ankle = knee + V(0, sh * math.sin(ss), -sh * math.cos(ss))
    return hip, knee, ankle


def tuck_pitch(rig, side, ankle_y):
    best, bp = 1e9, 0.0
    for p in range(0, 100, 2):
        e = abs(planted_ankle_y(rig, side, p) - ankle_y)
        if e < best:
            best, bp = e, p
    return float(bp)


# =============================================================================================== WINGS
# Left-wing poses: "<seg>.<channel>" with seg 1 / 2 / 3 / p (prim) and channel rz (up + / down -, in the wing plane),
# ry (+ = back, - = tips forward), twist (+ = feathers swing back). Right wing = mirrored (rz, ry, twist negated).
WSPREAD = {}
WOPEN = {"1.rz": -4, "1.ry": 10, "2.ry": 18, "3.rz": -12, "3.ry": -18, "p.rz": -24}
WHALF = {"1.rz": -6, "1.ry": 16, "2.ry": 38, "3.rz": -30, "3.ry": -42, "p.rz": -60}
WFOLD = {"1.ry": 35, "2.ry": 115, "3.rz": -40, "3.ry": -130, "p.rz": -96}
# kneeling: the folded wings lifted a little and swept further back so the back foot stays clear of the primaries
WKNEEL = {"1.rz": float(os.environ.get("GA_KW1Z", "22")), "1.ry": float(os.environ.get("GA_KW1Y", "46")), "2.ry": 112,
          "3.rz": float(os.environ.get("GA_KW3Z", "-52")), "3.ry": -128, "p.rz": -96}
WWIDE = {"1.rz": 3, "1.ry": 3, "2.ry": 6, "3.rz": -5, "3.ry": -7, "p.rz": -10}
WGRAND = {"1.rz": 10, "1.ry": -3, "2.rz": 3, "2.ry": 2, "3.rz": 5, "p.rz": 3}
SEG_BONE = {"1": "wing{}1", "2": "wing{}2", "3": "wing{}3", "p": "wing{}_prim"}


def pm(a, b, w):
    """Pose mix a -> b (missing channels = 0 = the spread rest pose)."""
    return {k: lerp(a.get(k, 0.0), b.get(k, 0.0), w) for k in set(a) | set(b)}


def pmseg(a, b, ws):
    """Pose mix with a weight per segment: ws = {"1": w1, "2": w2, "3": w3, "p": wp}."""
    return {k: lerp(a.get(k, 0.0), b.get(k, 0.0), ws[k.split(".")[0]]) for k in set(a) | set(b)}


def padd(a, *bs):
    out = dict(a)
    for b in bs:
        for k, v in b.items():
            out[k] = out.get(k, 0.0) + v
    return out


def put_wings(c, PL, PR=None):
    PR = PL if PR is None else PR
    for side, P, sg in (("L", PL, 1.0), ("R", PR, -1.0)):
        for k, v in P.items():
            seg, ch = k.split(".")
            c[f"{SEG_BONE[seg].format(side)}.{ch}"] = v * (sg if ch in ("rz", "ry", "twist") else 1.0)


D_STROKE = 0.55          # down-stroke share of the cycle
FLAP_LAG = {"1": 0.0, "2": 0.07, "3": 0.13, "p": 0.18}
# per segment: (rz mid, rz half range, ry mid, ry half range) -> s = +1 top / -1 bottom (RIG.md §4 up / down-stroke)
FLAP_RANGE = {"1": (-5.0, 29.0, -3.0, 13.0), "2": (-1.0, 13.0, -4.0, 6.0), "3": (0.0, 10.0, 0.0, 0.0), "p": (-1.0, 7.0, 0.0, 0.0)}
# partial fold on the up-stroke (wing smaller, fan closed, feathers trailing)
UPFOLD = {"1.ry": 6, "2.ry": 30, "3.rz": -14, "3.ry": -30, "p.rz": -50}


def stroke(p):
    """+1 at the top (p = 0), -1 at the bottom (p = D_STROKE); eased turns."""
    p %= 1.0
    if p < D_STROKE:
        return math.cos(math.pi * p / D_STROKE)
    return -math.cos(math.pi * (p - D_STROKE) / (1 - D_STROKE))


def stroke_v(p):
    """Down-stroke speed: + while the wing goes down, - on the way up (peak 1)."""
    p %= 1.0
    if p < D_STROKE:
        return math.sin(math.pi * p / D_STROKE)
    return -math.sin(math.pi * (p - D_STROKE) / (1 - D_STROKE))


def upfold(p):
    """0 on the down-stroke, rising to 1 in the middle of the up-stroke, back to 0 just after the top."""
    u = ((p - D_STROKE + 0.03) % 1.0) / (1 - D_STROKE + 0.05)
    return math.sin(math.pi * u) ** 1.3 if 0 <= u <= 1 else 0.0


def flap(p, amp=1.0, fold=1.0, feather=1.0, lag=1.0):
    """One wing beat at phase p (0 = top). Every segment lags its parent: the tips whip through the turns."""
    P = {}
    for seg, (zm, za, ym, ya) in FLAP_RANGE.items():
        q = p - FLAP_LAG[seg] * lag
        s = stroke(q)
        P[f"{seg}.rz"] = amp * (zm + za * s)
        if ya:
            P[f"{seg}.ry"] = amp * (ym + ya * s)
    for k, v in UPFOLD.items():
        seg = k.split(".")[0]
        P[k] = P.get(k, 0.0) + fold * v * upfold(p - 0.45 * FLAP_LAG[seg] * lag)
    # feathering: the air bends the feathers back on the down-stroke (tips forward), forward on the up-stroke
    P["2.twist"] = feather * 9 * stroke_v(p - 0.10 * lag)
    P["3.twist"] = feather * 13 * stroke_v(p - 0.16 * lag)
    return P


def flight_body(c, p, amp=1.0):
    """Body reaction to a wing beat: the chest crunches and the body rises on the down-stroke."""
    v = stroke_v(p - 0.04)
    c["chest.rx"] = c.get("chest.rx", 0.0) + 3.0 * amp * v
    c["spine.rx"] = c.get("spine.rx", 0.0) + 1.6 * amp * v
    c["neck.rx"] = c.get("neck.rx", 0.0) - 1.6 * amp * stroke_v(p - 0.10)
    c["head.rx"] = c.get("head.rx", 0.0) - 1.4 * amp * stroke_v(p - 0.14)
    for side in "LR":
        c[f"shoulder{side}.raise"] = c.get(f"shoulder{side}.raise", 0.0) - 2.5 * amp * v
    return -stroke(p - 0.18)                      # +1 = highest (end of the down-stroke), for root bobbing


def flight_arms(c, p, amp=1.0, out=0.0):
    """Arms floating in flight: they lag the body bob (drop as it rises)."""
    s = stroke(p - 0.28)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = -16 + 12 * out + 5 * amp * s
        c[f"upperArm{side}.bend"] = 10 + 4 * out
        c[f"forearm{side}.bend"] = 30 + 4 * amp * stroke(p - 0.36)
        c[f"forearm{side}.twist"] = -14 * sx
        c[f"hand{side}.bend"] = 10 + 6 * amp * stroke(p - 0.44)
        fingers(c, side, 16 + 4 * amp * stroke(p - 0.5))


def dangle_legs(c, p, amp=1.0):
    """Legs hanging relaxed in flight (FK): the left a little forward, the right trailing, toes pointed; they swing
    late against the body bob."""
    s = stroke(p - 0.32)
    c["thighL.rx"] = -4 + 3 * amp * s; c["shinL.rx"] = 14 + 5 * amp * stroke(p - 0.40); c["footL.rx"] = 34
    c["thighR.rx"] = 7 + 3 * amp * s; c["shinR.rx"] = 30 + 5 * amp * stroke(p - 0.42); c["footR.rx"] = 40
    c["thighL.rz"] = 1.5; c["thighR.rz"] = -1.0


# =============================================================================================== BODY BASE
ARM_REST = -22.0


def h_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.6 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.2 * b * amp; c["shoulderR.raise"] = 1.2 * b * amp
    c["neck.rx"] = 0.8 * b * amp
    c["upperArmL.raise"] = ARM_REST; c["upperArmR.raise"] = ARM_REST
    c["upperArmL.bend"] = 8; c["upperArmR.bend"] = 8
    c["forearmL.bend"] = 24; c["forearmR.bend"] = 24
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 22); fingers(c, "R", 22)
    c["head.rx"] = -2
    return c


def look_keys(c, keys, f, N, loop=True, neck=0.4, head=0.6, lag=4):
    c["neck.ry"] = c.get("neck.ry", 0.0) + neck * K(keys, f, N, loop)
    c["head.ry"] = c.get("head.ry", 0.0) + head * KL(keys, f, N, loop, lag=lag)


def talk_jaw(c, f, N, seed, amp=(5, 13)):
    jk, beats = syllables(N, seed, amp=amp)
    c["jaw.rx"] = jaw_from(jk, f, N)
    return beats


def default_pole(limb):
    sx = 1 if limb.endswith("L") else -1
    return {"leg": V(0.15 * sx, 0, 1), "arm": V(0.6 * sx, -0.6, -0.5)}[limb[:3]]


def mix(a, b, w):
    """Channel dicts a -> b by w (floats / vectors lerp; strings switch at 0.5; one-sided keys fade from / to rest)."""
    out = {}
    for k in set(a) | set(b):
        if k == "settle" or k.endswith(".q"):
            continue
        va, vb = a.get(k), b.get(k)
        if isinstance(va, tuple) or isinstance(vb, tuple):          # ("trumpet.aim": (direction, weight))
            aim = (va or vb)[0] if w < 0.5 or vb is None else vb[0]
            out[k] = (aim, lerp(va[1] if va else 0.0, vb[1] if vb else 0.0, w))
            continue
        if isinstance(va, str) or isinstance(vb, str):
            out[k] = (vb if w >= 0.5 else va) or va or vb
        elif k.startswith("pole.") and (va is None or vb is None):
            d = default_pole(k[5:])
            out[k] = vlerp(d if va is None else va, d if vb is None else vb, w)
        elif isinstance(va, Vector) or isinstance(vb, Vector):
            if va is None:
                out[k] = vb
            elif vb is None:
                out[k] = va
            else:
                out[k] = vlerp(va, vb, w)
        else:
            dflt = 1.0 if (k.endswith(".s") or k.endswith(".sy") or k.startswith("ikw.") or k == "trumpet.lips") else 0.0
            if k == "trumpet.lips":
                dflt = 0.0
            out[k] = lerp(dflt if va is None else va, dflt if vb is None else vb, w)
    for side in "LR":
        k = "ik.arm" + side
        if (k in a) != (k in b):
            wa = a.get("ikw.arm" + side, 1.0) if k in a else 0.0
            wb = b.get("ikw.arm" + side, 1.0) if k in b else 0.0
            out["ikw.arm" + side] = lerp(wa, wb, w)
    return out


def grip(c):
    """Right hand closed round the trumpet (RIG.md §4: fingersR curled 72)."""
    fingers(c, "R", 72)


# =============================================================================================== CLIPS
@clip("gabriel", "idle", 150, True,
      notes="standing tall and kind: slow breathing with one deeper breath (the chest and the half-open wings rise "
            "with it), weight shift with the hips leading, looks a little away and back (neck leads), a small content "
            "nod; the wings breathe (shoulders of the wings lift, the primaries open and close a little, the right "
            "wing a few frames behind the left) and once rouse their feathers; hair and sash drift; irregular blinks")
def gabriel_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=1.0)
    deep = bump(f, 40, 86)
    c["chest.rx"] += -2.2 * deep; c["shoulderL.raise"] += 1.6 * deep; c["shoulderR.raise"] += 1.6 * deep
    sh = K([(0, -0.4), (20, -0.4), (46, 0.9), (88, 0.9), (110, -0.7), (136, -0.7), (150, -0.4)], f, N, True)
    shl = KL([(0, -0.4), (20, -0.4), (46, 0.9), (88, 0.9), (110, -0.7), (136, -0.7), (150, -0.4)], f, N, True, lag=7)
    c["hips.tx"] = 0.005 * sh; c["hips.ty"] = -0.0015 - 0.0012 * abs(sh)
    c["hips.rz"] = -2.0 * sh; c["spine.rz"] = 1.3 * shl; c["chest.rz"] = 0.9 * shl; c["head.rz"] = -1.2 * shl
    look_keys(c, [(0, 0), (30, 0), (40, -12), (62, -12), (72, 7), (98, 7), (110, 0), (150, 0)], f, N)
    c["head.rx"] += 4 * bump(f, 116, 134) + K([(0, 0), (40, 2), (62, 1), (72, -2), (98, -1), (110, 0), (150, 0)], f, N, True)
    c["upperArmL.bend"] += 3 * shl; c["upperArmR.bend"] -= 3 * shl
    fingers(c, "L", 24 + 5 * wave(f, N, 2, 0.6)); fingers(c, "R", 26 + 5 * wave(f, N, 3, 0.1))
    PL, PR = {}, {}
    for P, lag in ((PL, 0.0), (PR, 4.0)):
        b = wave(f - lag, N, 3, -0.06) + 1.4 * bump((f - lag) % N, 40, 90)
        bl = wave(f - lag - 5, N, 3, -0.06) + 1.4 * bump((f - lag - 5) % N, 40, 90)
        rouse = ring((f - lag) % N, 118, period=4.5, decay=5.0)
        P.update(padd(WHALF, {"1.rz": 1.6 * b, "1.ry": -1.6 * b, "2.ry": -2.5 * bl, "3.ry": 2.0 * bl,
                              "3.rz": 2.5 * rouse, "p.rz": 5.0 * bl + 4.0 * rouse, "2.twist": 3.0 * rouse}))
    put_wings(c, PL, PR)
    blink(c, f, N, [24, 66, 73, 131])
    stand_feet(rig, c, pitchR=K([(0, 0), (46, 0), (60, 5), (88, 5), (100, 0), (150, 0)], f, N, True))
    return c


HOVER_Y = 0.55
FLAP_T = 36                 # frames per wing beat in hover / fly_down (1.2 s)


@clip("gabriel", "hover", 72, True,
      notes=f"high in the air (root {HOVER_Y} up, in the clip): two slow powerful wing beats of 1.2 s; down-stroke with "
            "the wing fully extended and the primaries spread, up-stroke with the wing partly folded and the fan "
            "closed; wing1 -> 2 -> 3 -> prim each lag their parent, the feathers twist with the air; the body rises "
            "on every down-stroke (root bob 0.016) and the chest crunches; arms float, legs hang relaxed (toes "
            "pointed, the right leg trailing) and swing late; looks down at the page")
def gabriel_hover(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    p = (f % FLAP_T) / FLAP_T
    bob = flight_body(c, p)
    c["root.ty"] = HOVER_Y + 0.016 * bob + 0.004 * wave(f, N, 1, 0.1)
    c["root.rz"] = 1.2 * wave(f, N, 1, 0.3)
    c["hips.rx"] = 3
    flight_arms(c, p)
    dangle_legs(c, p)
    PL = flap(p)
    PR = flap(p - 0.012)
    put_wings(c, PL, PR)
    c["head.rx"] += 6; c["neck.rx"] += 3
    blink(c, f, N, [20, 55])
    return c


FD_N, FD_LAND = 144, 126    # fly_down: frames, planned touchdown (the marker is measured)


def flight_legs_ik(rig, c, root_y, w_reach, pitch_air, ground_pitch, w_land, f_soft=1.0):
    """Leg targets for flight -> landing: hanging (bent knees, toes pointed) -> reaching down -> planted. World y is
    clamped to the page; targets go to root space."""
    for side, sx, dz0, dy0, pa in (("L", 1, 0.006, 0.020, pitch_air), ("R", -1, -0.026, 0.034, pitch_air + 6)):
        b = rig.head["foot" + side]
        pitch = lerp(pa, ground_pitch, w_land)
        dy = lerp(dy0, 0.0, w_reach)
        dz = lerp(dz0, 0.012 if side == "L" else 0.0, w_reach)
        wy = root_y + planted_ankle_y(rig, side, pitch) + dy
        wy = max(wy, planted_ankle_y(rig, side, pitch))
        tgt = V(b.x + sx * 0.004, wy - root_y, b.z + lerp(dz, 0.0, w_land))
        c[f"ik.leg{side}"] = tgt
        c[f"foot{side}.pitch"] = pitch
        c[f"pole.leg{side}"] = V(0.12 * sx, 0, 1)


@clip("gabriel", "fly_down", FD_N, False, auto_markers={"land": "land"},
      notes=f"from hover height ({HOVER_Y}, same pose as hover frame 0) comes down in 4.2 s with three big slow wing "
            "beats (down-strokes centred at 0.33 / 1.53 / 2.73 s: the story's wing_flap sfx at 0.4 / 1.6 / 2.8), each "
            "down-stroke slows the fall; then the wings flare up and forward to brake (primaries spread, body leans "
            "back, legs reach down, toes first), touches down at the `land` marker, the knees absorb, a last soft push "
            "of the wings, the feathers settle; ends standing, wings open (= fold_wings frame 0)")
def gabriel_fly_down(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    L = FD_LAND
    u = min(1.0, f / L)
    H = HOVER_Y * (1 - (0.78 * (3 * u * u - 2 * u * u * u) + 0.22 * u))
    flapping = f < 104
    p = (min(f, 107.6) % FLAP_T) / FLAP_T          # the third beat's up-stroke freezes into the flare
    amp = K([(0, 1.0), (36, 0.95), (72, 0.9), (104, 0.8)], f)
    bob = flight_body(c, p, amp * (1 - smooth((f - 92) / 16)))
    fade = 1 - smooth((f - 64) / 40)
    root_y = max(0.0, H + 0.016 * bob * fade) if f < L else 0.0
    c["root.ty"] = root_y
    # wings: three beats -> flare -> touchdown push -> open, feathers settle
    P = flap(p, amp)
    FLARE = {"1.rz": 20, "1.ry": -20, "2.rz": 9, "2.ry": -6, "3.rz": 10, "p.rz": 8, "2.twist": -10, "3.twist": -16}
    PUSH = {"1.rz": -15, "1.ry": -8, "2.rz": -7, "2.ry": 4, "3.rz": -4, "3.ry": -6, "p.rz": -8, "2.twist": 6, "3.twist": 9}
    wf = ease_io((f - 94) / 16)
    P = pmseg(P, FLARE, {"1": wf, "2": ease_io((f - 96) / 16), "3": ease_io((f - 98) / 16), "p": ease_io((f - 99) / 16)})
    wp = ease_io((f - (L - 5)) / 9)
    P = pmseg(P, PUSH, {"1": wp, "2": ease_io((f - (L - 3)) / 9), "3": ease_io((f - (L - 2)) / 9), "p": ease_io((f - (L - 1)) / 9)})
    wo = ease_io((f - (L + 4)) / 13)
    P = pmseg(P, WOPEN, {"1": wo, "2": ease_io((f - (L + 6)) / 12), "3": ease_io((f - (L + 7)) / 12), "p": ease_io((f - (L + 8)) / 11)})
    st = ring(f, L + 12, period=6.0, decay=5.5)
    P = padd(P, {"3.rz": 3.0 * st, "p.rz": 5.0 * st, "2.twist": 3.0 * st, "3.twist": -3.0 * st})
    put_wings(c, P, padd(P, {"1.rz": 0.6 * wave(f, 72, 1)}) if f < 90 else P)
    # body
    lean = ease_io((f - 92) / 16) * (1 - ease_io((f - L) / 8))
    dip = K([(L - 1, 0.0), (L + 7, -0.030), (L + 14, -0.010), (L + 18, -0.003), (FD_N, 0.0)], f) if f >= L - 1 else 0.0
    c["hips.ty"] = dip
    c["hips.tz"] = -0.006 * bump(f, L, L + 16)
    c["spine.rx"] += -5 * lean + 9 * bump(f, L, L + 16)
    c["chest.rx"] += -4 * lean + 3 * bump(f, L + 2, L + 18)
    look = K([(0, 8), (60, 8), (100, 4), (L, 6), (L + 10, 2), (FD_N, -1)], f)
    c["head.rx"] += look; c["neck.rx"] += 0.4 * look
    # arms: floating -> out to the sides in the flare -> dropping late on touchdown -> rest
    if f < L + 14:
        flight_arms(c, p, amp=0.8, out=lean)
    wa = ease_io((f - (L + 2)) / 14)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = lerp(c[f"upperArm{side}.raise"], ARM_REST, wa) - 6 * bump(f, L + 2, L + 14)
        c[f"upperArm{side}.bend"] = lerp(c[f"upperArm{side}.bend"], 8, wa) + 8 * bump(f, L, L + 12)
        c[f"forearm{side}.bend"] = lerp(c[f"forearm{side}.bend"], 24, wa) + 10 * bump(f, L + 3, L + 15)
        c[f"forearm{side}.twist"] = lerp(c[f"forearm{side}.twist"], -10 * sx, wa)
        c[f"hand{side}.bend"] = lerp(c[f"hand{side}.bend"], 6, wa)
    # legs: hang -> reach -> plant (toes first, heel down) -> knees absorb (IK keeps the feet still)
    w_reach = ease_io((f - 98) / 22)
    w_land = ease_io((f - (L - 2)) / 7)
    flight_legs_ik(rig, c, root_y, w_reach, lerp(32, 22, w_reach), 0.0, w_land)
    blink(c, f, N, [30, 84, L + 16], loop=False)
    return c


@clip("gabriel", "fold_wings", 66, False,
      notes="from the open wings of the landing: a breath and a little lift and spread (anticipation), then folds the "
            "wings behind the back with overlapping action (wing1 leads, forearm, hand and the closing fan follow a "
            "few frames later), shakes the feathers into place (a quick decaying ruffle with a shrug), settles; holds "
            "folded (RIG.md §4 fold: tips at the knees)")
def gabriel_fold_wings(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.6)
    ant = bump(f, 0, 14)
    P0 = padd(WOPEN, {"1.rz": 5 * ant, "1.ry": -4 * ant, "p.rz": 10 * ant})
    ws = {"1": ease_io((f - 7) / 20), "2": ease_io((f - 10) / 22), "3": ease_io((f - 13) / 22), "p": ease_io((f - 9) / 20)}
    P = pmseg(P0, WFOLD, ws)
    sh = ring(f, 40, period=4.2, decay=5.0)
    shl = ring(f, 42, period=4.2, decay=5.0)
    P = padd(P, {"1.rz": 2.5 * sh, "2.ry": -3 * shl, "3.rz": 4 * shl, "p.rz": 6 * shl, "2.twist": 5 * sh, "3.twist": 4 * shl})
    put_wings(c, P)
    shrug = bump(f, 34, 50)
    c["shoulderL.raise"] += 4 * shrug + 1.5 * sh; c["shoulderR.raise"] += 4 * shrug - 1.5 * sh
    c["chest.rx"] += -2.5 * ant + 1.0 * sh; c["chest.rz"] = 1.2 * sh
    c["head.rx"] += -2 * ant + 5 * bump(f, 52, 66); c["head.rz"] = 2 * bump(f, 50, 66)
    blink(c, f, N, [16, 47], loop=False)
    stand_feet(rig, c)
    return c


G_WALK = (0.074, 0.62)


@clip("gabriel", "walk", 44, True, markers={"contactL": 0, "contactR": 22}, speed=G_WALK,
      notes="calm noble walk (~82 steps/min), wings folded: tall chest, soft hip bob, chest counter-turn, restrained "
            "arm swing with lagging forearms, head steady; the folded wings bounce a little late with each step, hair "
            "and sash swing late")
def gabriel_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=G_WALK[0], lift=0.013, duty=G_WALK[1], heel=11, toeoff=22, spread=0.002)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0045 + 0.0032 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 4.5 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.35); c["head.ry"] = 2.5 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.0 * math.cos(ph); c["chest.rz"] = -1.3 * math.cos(ph - 0.5); c["head.rz"] = 0.6 * math.cos(ph - 0.9)
    c["chest.rx"] += -3; c["spine.rx"] = 1; c["head.rx"] = -2 + 1.0 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 8 - 13 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 13 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 24 - 8 * math.sin(ph - 1.0); c["forearmR.bend"] = 24 + 8 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 8 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 8 * math.sin(ph - 1.6)
    bo = math.cos(2 * ph - 1.2); bol = math.cos(2 * ph - 1.9)
    put_wings(c, padd(WFOLD, {"1.rz": 1.2 * bo, "2.ry": -1.5 * bol, "3.rz": 1.5 * bol, "p.rz": 2.0 * bol}),
              padd(WFOLD, {"1.rz": 1.2 * bo, "2.ry": -1.5 * bol, "3.rz": 1.5 * bol, "p.rz": 2.0 * bol}))
    blink(c, f, N, [27])
    return c


# --- one knee on the page (right knee down, left foot forward)
KN = dict(KY=float(os.environ.get("GA_KY", "0.030")), kz=float(os.environ.get("GA_KZ", "-0.012")),
          thigh_back=float(os.environ.get("GA_TB", "-4")), shin_slope=float(os.environ.get("GA_SS", "10")), spread=0.010)
KNEEL_FRONT = V(0.046, 0.0, float(os.environ.get("GA_FZ", "0.150")))      # left ankle (y = planted)
_KNEEL_HIPS = {}


def kneel_legs(rig, c, w=1.0):
    hip, knee, ankle = kneel_geom(rig, "R", **KN)
    b = rig.head["footR"]
    pk = tuck_pitch(rig, "R", ankle.y)
    tgt = V(lerp(b.x, ankle.x, w), lerp(planted_ankle_y(rig, "R", 0), ankle.y, w), lerp(b.z, ankle.z, w))
    tgt.y = max(tgt.y, planted_ankle_y(rig, "R", pk * w))
    c["ik.legR"] = tgt; c["footR.pitch"] = pk * w; c["pole.legR"] = V(-0.10, 0, 1)
    bL = rig.head["footL"]
    c["ik.legL"] = vlerp(V(bL.x + 0.004, planted_ankle_y(rig, "L", 0), bL.z), V(KNEEL_FRONT.x, planted_ankle_y(rig, "L", 0), KNEEL_FRONT.z), w)
    c["footL.pitch"] = 0.0; c["pole.legL"] = V(0.25, 0.1, 1)
    c["footL.ry"] = -6 * w
    c["sword.rx"] = c.get("sword.rx", 0.0) + 24 * w          # the scabbard tip swings back off the page
    hy, hz = kneel_hips(rig)
    c["hips.ty"] = c.get("hips.ty", 0.0) + hy * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + hz * w


def kneel_hips(rig):
    """Hip drop of the kneel: the geometric hip height, then settled so the kneeling leg's lowest vertex is on the
    page (computed once on the skinned proxy)."""
    if "v" not in _KNEEL_HIPS:
        hip, knee, ankle = kneel_geom(rig, "R", **KN)
        hy = hip.y - rig.head["thighR"].y
        hz = hip.z - rig.head["thighR"].z
        _KNEEL_HIPS["v"] = (hy, hz)
        c = {}
        kneel_legs(rig, c, 1.0)
        put_wings(c, WKNEEL)
        _, basis, M = solve_pose(rig, c)
        low = min(p.y for p in rig.skin(M, {"thighR", "shinR", "footR", "toeR"}))
        _KNEEL_HIPS["v"] = (hy - low + 0.0004, hz)
        print("GA_KNEEL hips", [round(v, 4) for v in _KNEEL_HIPS["v"]], "lowest before settle", round(low, 4))
    return _KNEEL_HIPS["v"]


def kneel_upper(rig, c, f, N, talk=True, w=1.0):
    """Kneeling and talking warmly to the child: leaning in, left forearm on the left knee, right hand opening palm
    up toward the child on the stressed syllables, nods, head tilt."""
    beats = talk_jaw(c, f, N, 73, amp=(5, 12)) if talk else []
    if not talk:
        c["jaw.rx"] = 0.0
    bt = beat_curve(beats, f, N, width=9); btl = beat_curve(beats, f - 3, N, width=10)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 7 * w; c["chest.rx"] = c.get("chest.rx", 0.0) + 1.5 * bt
    c["neck.rx"] = c.get("neck.rx", 0.0) + 2 * w
    c["head.rx"] = c.get("head.rx", 0.0) + 2.5 * bt - 1.2 * wave(f, N, 1, 0.2)
    c["head.rz"] = (6 + 2.5 * wave(f, N, 1, 0.3)) * w
    c["head.ry"] = (2 * wave(f, N, 1, 0.1) + 1.5 * wave(f, N, 3, 0.4)) * w
    arm_ik(c, "L", V(0.060, 0.226, 0.128), V(1.0, -0.2, -0.5), "root", w)
    c["handL.bend"] = lerp(6, 18, w); fingers(c, "L", lerp(22, 30, w))
    pa = K([(0, 0.25), (14, 0.9), (60, 1.0), (78, 0.2), (100, 0.3), (118, 0.95), (140, 0.8), (150, 0.25)], f, N, True)
    lift = pa * (0.7 + 0.3 * btl) * w
    c["upperArmR.raise"] = lerp(ARM_REST, -14, w) + 6 * lift; c["upperArmR.bend"] = 8 + 34 * lift
    c["forearmR.bend"] = 24 + 46 * lift; c["forearmR.twist"] = 10 - 80 * lift
    c["handR.bend"] = 6 - 18 * btl * pa * w; fingers(c, "R", 26 - 20 * btl * pa * w - 6 * lift)
    c["chest.ry"] = (-4 * lift + 2) * w


@clip("gabriel", "kneel_down", 40, False, extra=True, markers={"knee_down": 28},
      notes="EXTRA (not in CONTRACT §4): from standing with folded wings, steps the left foot forward and goes down on "
            "the right knee (knee on the page), lifting the folded wings a little; ends = kneel_talk frame 0. Play it "
            "before kneel_talk (kneel_talk is a loop and cannot itself go down)")
def gabriel_kneel_down(rig, f, N):
    stand = h_base(rig, f, N, cycles=1, amp=0.3)
    stand_feet(rig, stand)
    put_wings(stand, WFOLD)
    kn = gabriel_kneel_talk(rig, 0, 150)
    w = ease_io((f - 6) / 22)
    c = mix(stand, kn, w)
    # the left foot steps (lifted) instead of sliding
    st = ease_io((f - 2) / 12)
    bL = rig.head["footL"]
    c["ik.legL"] = vlerp(V(bL.x + 0.004, planted_ankle_y(rig, "L", 0), bL.z), V(KNEEL_FRONT.x, planted_ankle_y(rig, "L", 0), KNEEL_FRONT.z), st) \
        + V(0, 0.022 * math.sin(math.pi * st), 0)
    c["footL.pitch"] = -8 * math.sin(math.pi * st)
    c["hips.ty"] = c.get("hips.ty", 0.0) + 0.006 * bump(f, 26, 36) * -1
    c["spine.rx"] = c.get("spine.rx", 0.0) + 6 * bump(f, 8, 32)
    kw = ease_io((f - 4) / 26)
    P = pmseg(WFOLD, WKNEEL, {"1": kw, "2": kw, "3": ease_io((f - 7) / 26), "p": kw})
    put_wings(c, P)
    blink(c, f, N, [10], loop=False)
    return c


@clip("gabriel", "kneel_talk", 150, True,
      notes="on the right knee (knee and tucked toes on the page, left foot planted forward), folded wings lifted "
            "and swept back so the back foot stays clear of the feathers; leans in and talks warmly: left forearm on "
            "the left knee, right hand opening palm up toward the child on the stressed syllables, nods, head tilt; "
            "jaw in an irregular syllable rhythm (lip sync overrides it); slow blinks")
def gabriel_kneel_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.7)
    kneel_legs(rig, c, 1.0)
    kneel_upper(rig, c, f, N)
    b = wave(f, N, 2, -0.05)
    put_wings(c, padd(WKNEEL, {"1.rz": 0.8 * b, "p.rz": 2 * wave(f - 5, N, 2)}))
    blink(c, f, N, [22, 88, 96], slow=1.2)
    return c


@clip("gabriel", "stand_up", 54, False, markers={"stand": 40},
      notes="from the kneel (kneel_talk frame 0): leans forward, pushes up on the left knee with the left hand, rises "
            "into a lunge (back foot on its toes), brings the right foot up beside the left, straightens; wings "
            "go from the lifted kneel fold back to the standing fold; holds standing (= talk frame 0 stance)")
def gabriel_stand_up(rig, f, N):
    kn = gabriel_kneel_talk(rig, 0, 150)
    stand = h_base(rig, f, N, cycles=1, amp=0.3)
    stand_feet(rig, stand)
    up = ease_io((f - 8) / 26)
    c = mix(kn, stand, up)
    hy, hz = kneel_hips(rig)
    hip, knee, ankle = kneel_geom(rig, "R", **KN)
    bR, bL = rig.head["footR"], rig.head["footL"]
    # hips: kneel -> lunge (the feet are still apart) -> standing
    c["hips.ty"] = K([(0, hy), (6, hy - 0.004), (32, -0.060), (40, -0.026), (48, -0.004), (54, 0.0)], f)
    c["hips.tz"] = K([(0, hz), (8, hz + 0.004), (32, 0.042), (40, 0.022), (50, 0.0), (54, 0.0)], f)
    # right (back) foot: tucked kneel ankle -> on its toes behind -> steps up to stand
    pk = tuck_pitch(rig, "R", ankle.y)
    back = V(bR.x - 0.004, planted_ankle_y(rig, "R", 34), -0.040)
    if f < 30:
        t = ease_io((f - 6) / 24)
        tgt = vlerp(ankle, back, t); pitch = lerp(pk, 34, t)
        tgt.y = max(tgt.y, planted_ankle_y(rig, "R", pitch))
    else:
        t = ease_io((f - 30) / 12)
        tgt = vlerp(back, V(bR.x - 0.004, planted_ankle_y(rig, "R", 0), bR.z), t) + V(0, 0.022 * math.sin(math.pi * t), 0)
        pitch = lerp(34, 0, t)
    c["ik.legR"] = tgt; c["footR.pitch"] = pitch; c["pole.legR"] = V(-0.10, 0, 1)
    # left (front) foot stays planted, then steps back beside the right
    t = ease_io((f - 38) / 12)
    c["ik.legL"] = vlerp(V(KNEEL_FRONT.x, planted_ankle_y(rig, "L", 0), KNEEL_FRONT.z),
                         V(bL.x + 0.004, planted_ankle_y(rig, "L", 0), bL.z), t) + V(0, 0.018 * math.sin(math.pi * t), 0)
    c["footL.pitch"] = -6 * math.sin(math.pi * t); c["footL.ry"] = -6 * (1 - t)
    lean = bump(f, 4, 40)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 16 * lean; c["chest.rx"] = c.get("chest.rx", 0.0) + 4 * lean
    c["head.rx"] = c.get("head.rx", 0.0) - 6 * lean
    # the left hand pushes on the knee (stays on it while the knee rises), then lets go
    hw = 1 - ease_io((f - 26) / 10)
    arm_ik(c, "L", V(0.058, lerp(0.226, 0.30, ease_io((f - 6) / 26)), lerp(0.128, 0.10, up)), V(1.0, -0.2, -0.5), "root", hw)
    P = pmseg(WKNEEL, WFOLD, {"1": ease_io((f - 20) / 24), "2": ease_io((f - 22) / 24), "3": ease_io((f - 24) / 24), "p": ease_io((f - 22) / 24)})
    put_wings(c, P)
    c["jaw.rx"] = 0.0
    blink(c, f, N, [44], loop=False)
    return c


@clip("gabriel", "talk", 120, True,
      notes="standing talk with open, generous gestures, wings folded: both hands open outward palms up (a giving "
            "gesture), then the right hand alone sweeps out, the left comes to the chest; nods on the stressed "
            "syllables, weight shift; jaw in an irregular syllable rhythm (lip sync overrides it); the folded wings "
            "lift a little with the big gesture")
def gabriel_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    beats = talk_jaw(c, f, N, 41)
    bt = beat_curve(beats, f, N, width=9); btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -2 + 3.0 * bt - 1.0 * wave(f, N, 1, 0.2)
    c["head.ry"] = 4 * wave(f, N, 1, 0.1) + 2 * wave(f, N, 3, 0.4); c["head.rz"] = 2.5 * wave(f, N, 1, 0.35)
    both = K([(0, 0.15), (12, 0.9), (40, 1.0), (54, 0.1), (110, 0.1), (120, 0.15)], f, N, True)
    rgt = K([(0, 0.2), (40, 0.3), (56, 0.95), (92, 1.0), (106, 0.3), (120, 0.2)], f, N, True)
    chest = K([(0, 0.0), (54, 0.0), (66, 1.0), (96, 0.9), (108, 0.0), (120, 0.0)], f, N, True)
    for side, sx, amt in (("L", 1, both), ("R", -1, max(both, rgt))):
        lift = amt * (0.75 + 0.25 * btl)
        c[f"upperArm{side}.raise"] = ARM_REST + 16 * lift
        c[f"upperArm{side}.bend"] = 8 + 30 * lift
        c[f"forearm{side}.bend"] = 24 + 36 * lift
        c[f"forearm{side}.twist"] = sx * (-10 + 80 * lift)
        c[f"hand{side}.bend"] = 6 - 16 * btl * amt
        fingers(c, side, 24 - 18 * btl * amt - 6 * lift)
    arm_ik(c, "L", V(0.016, 0.010 + 0.004 * btl, 0.066), V(0.8, -0.6, -0.2), "chest", chest)
    c["handL.bend"] = 6 - 10 * chest
    c["chest.ry"] = -4 * rgt + 3 * chest; c["chest.rx"] += 1.5 * bt - 2 * both
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.4 * sh; c["spine.rz"] = 0.8 * sh
    g = both
    put_wings(c, padd(WFOLD, {"1.rz": 3 * g, "1.ry": -3 * g, "p.rz": 4 * KL([(0, 0.15), (12, 0.9), (40, 1.0), (54, 0.1), (110, 0.1), (120, 0.15)], f, N, True, lag=6)}))
    blink(c, f, N, [9, 63, 98])
    stand_feet(rig, c)
    return c


@clip("gabriel", "point_up", 72, False, markers={"point": 20, "look_back": 54},
      notes="from the standing talk stance: a small dip, the right arm sweeps up and points to heaven (overshoot and "
            "settle), the chest lifts and he looks up after his hand, holds the look, then looks back at the child "
            "with a kind smile while the arm stays up; the folded wings lift a little with the gesture; holds")
def gabriel_point_up(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    up = K([(0, 0.0), (4, -0.05), (18, 1.06), (24, 0.98), (30, 1.0), (72, 1.0)], f)
    c["upperArmR.raise"] = lerp(ARM_REST, 128, up); c["upperArmR.bend"] = lerp(8, 16, up)
    c["forearmR.bend"] = lerp(24, 6, up) + 10 * bump(f, 12, 26); c["forearmR.twist"] = lerp(10, 40, up)
    c["handR.bend"] = lerp(6, -14, up); fingers(c, "R", lerp(22, 8, up))
    c["upperArmL.raise"] = ARM_REST + 6 * up; c["forearmL.bend"] = 24 + 10 * up; c["upperArmL.bend"] = 8 + 6 * up
    look = K([(0, 0.0), (10, 0.0), (24, 1.0), (44, 1.0), (58, 0.0), (72, 0.0)], f)
    c["neck.rx"] += -12 * look; c["head.rx"] += -22 * look + 2 * bump(f, 56, 70)
    c["head.ry"] = -10 * look; c["head.rz"] = -4 * look + 4 * bump(f, 54, 72) * 0.8 + 3 * smooth((f - 58) / 10)
    c["chest.rx"] += -4 * up - 1.5 * bump(f, 12, 26); c["chest.rz"] = 3 * up; c["spine.rz"] = 1.5 * up
    c["chest.ry"] = -3 * up
    g = KL([(0, 0.0), (4, -0.05), (18, 1.06), (24, 0.98), (30, 1.0), (72, 1.0)], f, lag=4)
    put_wings(c, padd(WFOLD, {"1.rz": 5 * g, "1.ry": -4 * g, "p.rz": 8 * g}))
    blink(c, f, N, [30, 60], loop=False)
    stand_feet(rig, c)
    return c


# --- the trumpet (rigid on handR: RIG.md §4, regions_characters.json trumpet.mouthpieceLocal / bellLocal)
TRUMPET_RIG_Q = {"upperArmR": (0.1032, -0.2906, -0.7448, -0.5917), "forearmR": (0.1136, 0.1187, 0.7011, -0.6939),
                 "handR": (0.9381, 0.0934, 0.3098, -0.1234)}
MOUTH_L = V(*REGIONS["characters"]["gabriel"]["trumpet"]["mouthpieceLocal"])
BELL_L = V(*REGIONS["characters"]["gabriel"]["trumpet"]["bellLocal"])
_TR = {}


def trumpet_hold(rig):
    """The hand transform that puts the mouthpiece on the lips, in HEAD space (RIG.md §4 solve, rest torso)."""
    if "rel" not in _TR:
        c = {f"{n}.q": q for n, q in TRUMPET_RIG_Q.items()}
        basis = rig.basis_from(c)
        M = rig.fk(basis)
        lips = rig.point(M, "trumpet", MOUTH_L)
        cur = (rig.point(M, "trumpet", BELL_L) - lips).normalized()
        # the RIG.md solve points the bell well out to his right; turn it about the mouthpiece toward up-forward
        want = V(*[float(v) for v in os.environ.get("GA_BELL", "-0.20,0.30,0.93").split(",")]).normalized()
        Rd = (C @ cur).rotation_difference(C @ want).to_matrix().to_4x4()
        Lb = to_bl(lips)
        Mh = Matrix.Translation(Lb) @ Rd @ Matrix.Translation(-Lb) @ M["handR"]
        _TR["rel"] = M["head"].inverted() @ Mh
        _TR["lips"] = lips
        _TR["elbow"] = rig.pos(M, "forearmR")
        print("GA_TRUMPET lips(rest)", [round(v, 4) for v in _TR["lips"]], "bell", [round(v, 4) for v in rig.point(M, "trumpet", BELL_L)])
    return _TR["rel"]


def arm_to(rig, basis, M, side, M_hand_world, pole_d, w=1.0):
    """Arm IK to a full hand transform (wrist position + hand rotation); the forearm takes the twist so the wrist
    does not wring."""
    up, lo, end = f"upperArm{side}", f"forearm{side}", f"hand{side}"
    old = {n: [basis[n][0].copy(), basis[n][1].copy(), basis[n][2]] for n in (up, lo, end)}
    T = to_d(M_hand_world.translation)
    ik2(rig, basis, M, up, lo, T, pole_d, False)
    Rh = M_hand_world.to_3x3().normalized()
    Rf = M[lo].to_3x3().normalized()
    yf = Rf.col[1]
    xh = Rh.col[0] - yf * Rh.col[0].dot(yf)
    if xh.length > 1e-6:
        xh.normalize()
        xf = Rf.col[0]
        ang = math.atan2(xf.cross(xh).dot(yf), xf.dot(xh))
        Rt = Matrix.Rotation(ang * 0.8, 3, yf)
        rig.set_world_rot(basis, M, lo, Rt @ Rf)
    rig.set_world_rot(basis, M, end, Rh)
    if w < 0.9999:
        for n in (up, lo, end):
            basis[n][0] = old[n][0].slerp(basis[n][0], w)
        rig.fk(basis, M)


def trumpet_post(rig, chs, basis, M):
    w = chs.get("trumpet.lips", 0.0)
    if w > 1e-4:
        rel = trumpet_hold(rig)
        Mh = M["head"] @ rel
        arm_to(rig, basis, M, "R", Mh, to_d((M["root"] @ rig.rest_inv["root"]).to_3x3() @ to_bl(V(-1.0, -0.35, -0.25))), w)
    tgt = chs.get("trumpet.aim")
    if tgt is not None:
        aim, w = tgt
        if w > 1e-4:
            a = rig.point(M, "trumpet", MOUTH_L); b = rig.point(M, "trumpet", BELL_L)
            cur = (b - a).normalized()
            Rd = (C @ cur).rotation_difference(C @ Vector(aim).normalized()).to_matrix()
            Rd = Quaternion().slerp(Rd.to_quaternion(), w).to_matrix()
            Rh = M["handR"].to_3x3().normalized()
            rig.set_world_rot(basis, M, "handR", Rd @ Rh)


@clip("gabriel", "raise_trumpet", 60, False, markers={"high": 24}, props=["trumpet"],
      notes="the golden trumpet in his right hand at his side: a little dip, then lifts it high above his head, bell to "
            "the sky, chest up, chin up, a proud smile; the folded wings open to half with overlapping action as the "
            "arm goes up; overshoot and settle; holds (blow_trumpet then brings it to the lips)")
def gabriel_raise_trumpet(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    up = K([(0, 0.0), (6, -0.08), (22, 1.05), (28, 0.97), (34, 1.0), (60, 1.0)], f)
    c["upperArmR.raise"] = lerp(ARM_REST, 112, up); c["upperArmR.bend"] = lerp(8, 22, up)
    c["forearmR.bend"] = lerp(24, 26, up) + 12 * bump(f, 10, 26); c["forearmR.twist"] = lerp(10, -20, up)
    c["handR.bend"] = lerp(6, -8, up)
    grip(c)
    c["trumpet.aim"] = (V(-0.25, 1.0, 0.25), ease_io((f - 8) / 16))
    c["upperArmL.raise"] = ARM_REST + 12 * up; c["upperArmL.bend"] = 8 + 6 * up; c["forearmL.bend"] = 24 + 8 * up
    c["chest.rx"] += -5 * up + 2 * bump(f, 0, 10); c["spine.rx"] += -1.5 * up
    c["neck.rx"] += -4 * up; c["head.rx"] += -8 * up; c["head.ry"] = -6 * up; c["head.rz"] = -3 * up
    c["chest.rz"] = 2 * up; c["chest.ry"] = -4 * up
    ws = {"1": ease_io((f - 10) / 20), "2": ease_io((f - 13) / 20), "3": ease_io((f - 16) / 20), "p": ease_io((f - 18) / 18)}
    P = pmseg(WFOLD, WHALF, ws)
    st = ring(f, 38, period=6.0, decay=5.0)
    put_wings(c, padd(P, {"3.rz": 3 * st, "p.rz": 5 * st}))
    blink(c, f, N, [4, 44], loop=False)
    stand_feet(rig, c)
    return c


BLOW_AT = (15, 75)           # phrase starts (frames): the blow marker is the first


@clip("gabriel", "blow_trumpet", 120, True, markers={"blow": BLOW_AT[0], "blow2": BLOW_AT[1]}, props=["trumpet"],
      notes="the trumpet at his lips (mouthpiece on the lips, RIG.md §4 hold, kept in head space), bell up and forward: "
            "two phrases per 4 s loop: a big breath (chest and shoulders rise, head back, wings gather), then he blows "
            "(`blow` = sound starts), leaning back so the bell lifts, the chest slowly empties; the wings flare open "
            "with each phrase (from half to almost spread, with overlapping action and a feather shiver) and relax; "
            "left arm out for balance")
def gabriel_blow_trumpet(rig, f, N):
    c = h_base(rig, f, N, cycles=0, amp=0.0)
    breath = 0.0; blow = 0.0; flare = 0.0; full = 0.0
    for b0 in BLOW_AT:
        d = (f - b0 + N / 2) % N - N / 2
        breath = max(breath, bump(d, -14, 3))                       # in-breath before the phrase
        blow = max(blow, bump(d, -1, 52) if d > -1 else 0.0)        # the phrase
        flare = max(flare, K([(-2, 0.0), (8, 1.0), (30, 0.85), (50, 0.0)], d) if -2 <= d <= 50 else 0.0)
        # lungs: fill before the phrase, empty slowly while blowing
        full = max(full, K([(-16, 0.0), (-2, 1.0), (10, 0.9), (48, 0.1), (56, 0.0)], d) if -16 <= d <= 56 else 0.0)
    c["trumpet.lips"] = 1.0
    grip(c)
    c["chest.rx"] = -5 * full - 1.5 * blow
    c["spine.rx"] = -2.5 * blow - 1 * breath
    c["shoulderL.raise"] = 3 * breath; c["shoulderR.raise"] = 3 * breath
    c["neck.rx"] = -3 * blow - 1.5 * breath; c["head.rx"] = -9 * blow - 4 * breath
    c["hips.tz"] = -0.004 * blow
    c["head.ry"] = -3 + 2 * wave(f, N, 1, 0.2); c["head.rz"] = -2 * blow
    c["chest.ry"] = -3
    c["upperArmL.raise"] = ARM_REST + 26 + 4 * flare; c["upperArmL.bend"] = 14; c["forearmL.bend"] = 34 - 6 * flare
    c["forearmL.twist"] = -40; c["handL.bend"] = -10 + 4 * flare; fingers(c, "L", 12)
    PL, PR = {}, {}
    for P, lg in ((PL, 0.0), (PR, 2.0)):
        fl = 0.0; fll = 0.0; br = 0.0; sh = 0.0
        for b0 in BLOW_AT:
            d = (f - lg - b0 + N / 2) % N - N / 2
            dl = (f - lg - 4 - b0 + N / 2) % N - N / 2
            fl = max(fl, K([(-2, 0.0), (8, 1.0), (30, 0.85), (50, 0.0)], d) if -2 <= d <= 50 else 0.0)
            fll = max(fll, K([(-2, 0.0), (8, 1.0), (30, 0.85), (50, 0.0)], dl) if -2 <= dl <= 50 else 0.0)
            br = max(br, bump(d, -14, 3))
            sh += ring(d, 10, period=4.0, decay=6.0)
        base = pmseg(WHALF, WWIDE, {"1": fl, "2": fll, "3": fll, "p": fll})
        P.update(padd(base, {"1.rz": 4 * br - 3 * fl * bump(fl, 0, 1), "1.ry": 3 * br, "3.rz": 2 * sh, "p.rz": 4 * sh,
                             "2.twist": 4 * sh}))
    put_wings(c, PL, PR)
    c["eyelids.sy"] = 1.0
    c["jaw.rx"] = 0.0
    stand_feet(rig, c)
    return c


@clip("gabriel", "spread_wings", 60, False, markers={"spread": 22}, props=["trumpet"],
      notes="starts as blow_trumpet frame 0 (trumpet at the lips); lowers the trumpet to his side, the wings dip "
            "and gather (anticipation) then sweep open to a majestic full spread raised a little above the rest pose "
            "(overlapping wing1 -> prim, overshoot, the feathers settle), chest up, chin up, both arms slightly out "
            "from the body, palms forward; holds")
def gabriel_spread_wings(rig, f, N):
    c0 = gabriel_blow_trumpet(rig, 0, 120)
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    grip(c)
    out = ease_io((f - 10) / 20)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = ARM_REST + 14 * out; c[f"upperArm{side}.bend"] = 8 + 6 * out
        c[f"forearm{side}.bend"] = 24 - 6 * out; c[f"forearm{side}.twist"] = sx * (-10 - 30 * out)
        c[f"hand{side}.bend"] = 6 - 10 * out
    fingers(c, "L", 22 - 12 * out)
    c["trumpet.aim"] = (V(-0.35, -0.55, 0.75), 1.0)
    c["chest.rx"] += -6 * out + 2 * bump(f, 2, 14); c["neck.rx"] += -2 * out; c["head.rx"] += -6 * out
    c["shoulderL.raise"] += 2 * out; c["shoulderR.raise"] += 2 * out
    stand_feet(rig, c)
    w0 = 1 - ease_io(f / 10)
    c = mix(c, c0, w0)
    c["trumpet.lips"] = w0
    ant = bump(f, 0, 14)
    P0 = {}                                      # blow_trumpet frame 0 wings as a left-wing pose
    for seg, bn in SEG_BONE.items():
        for ch in ("rz", "ry", "twist"):
            v = c0.get(f"{bn.format('L')}.{ch}")
            if v is not None:
                P0[f"{seg}.{ch}"] = v
    P0 = padd(P0, {"1.rz": -6 * ant, "1.ry": 6 * ant, "2.ry": 10 * ant, "p.rz": -14 * ant})
    ov = 1.0 + 0.10 * bump(f, 24, 40)
    G = {k: v * ov for k, v in WGRAND.items()}
    ws = {"1": ease_io((f - 8) / 16), "2": ease_io((f - 11) / 16), "3": ease_io((f - 13) / 16), "p": ease_io((f - 14) / 15)}
    P = pmseg(P0, G, ws)
    st = ring(f, 30, period=5.0, decay=6.0)
    P = padd(P, {"3.rz": 3 * st, "p.rz": 5 * st, "2.twist": 3 * st, "3.twist": -3 * st})
    put_wings(c, P)
    blink(c, f, N, [26], loop=False)
    return c


@clip("gabriel", "bless", 150, True, markers={"heart": 24, "open": 66},
      notes="wings wide and breathing slowly, the trumpet put away: the right hand comes to his heart, rests there, "
            "then opens palm toward the viewer (forward and a little out), holds, and returns to the heart; a slow "
            "warm nod and head tilt; jaw in a syllable rhythm for the line (lip sync overrides it); slow blinks")
def gabriel_bless(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.9)
    jk, beats = syllables(N, 91, amp=(4, 11))
    c["jaw.rx"] = jaw_from(jk, f, N)
    heart = K([(0, 0.8), (12, 1.0), (40, 1.0), (54, 0.0), (120, 0.0), (138, 0.9), (150, 0.8)], f, N, True)
    opn = K([(0, 0.0), (40, 0.0), (58, 1.0), (112, 1.0), (130, 0.0), (150, 0.0)], f, N, True)
    arm_ik(c, "R", V(0.004, 0.024, 0.072), V(-0.8, -0.7, -0.3), "chest", heart)
    c["handR.bend"] = 6 - 6 * heart; fingers(c, "R", 14)
    c["handR.twist"] = 0.0
    if opn > 0:
        c["upperArmR.raise"] = ARM_REST + 12 * opn; c["upperArmR.bend"] = 8 + 50 * opn
        c["forearmR.bend"] = 24 + 40 * opn; c["forearmR.twist"] = 10 - 85 * opn
        c["handR.bend"] = 6 - 40 * opn; fingers(c, "R", 14 - 10 * opn)
    c["upperArmL.raise"] = ARM_REST + 4; c["forearmL.bend"] = 28
    nod = bump(f, 60, 90)
    c["head.rx"] += 6 * nod + 3 * heart; c["neck.rx"] += 2 * nod
    c["head.rz"] = 5 * wave(f, N, 1, 0.1) + 3; c["head.ry"] = -3 * opn
    c["chest.ry"] = 4 * heart - 3 * opn; c["chest.rx"] += -2 * opn
    b = wave(f, N, 2, -0.05); bl = wave(f - 6, N, 2, -0.05)
    put_wings(c, padd(WWIDE, {"1.rz": 2.5 * b, "1.ry": -2 * b, "2.ry": -2.5 * bl, "p.rz": 5 * bl}),
              padd(WWIDE, {"1.rz": 2.5 * bl, "1.ry": -2 * bl, "2.ry": -2.5 * wave(f - 10, N, 2, -0.05), "p.rz": 5 * wave(f - 10, N, 2, -0.05)}))
    blink(c, f, N, [30, 100], base=1.6, slow=1.6)
    stand_feet(rig, c)
    return c


@clip("gabriel", "wave", 60, True,
      notes="friendly goodbye to the viewer: the right hand up beside the head waving from the elbow, a smile with a "
            "head tilt and a weight shift; the half-open wings wave along a little (tips flutter late); jaw syllables "
            "for the line (lip sync overrides it)")
def gabriel_wave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.7)
    ph = wave(f, N, 2)
    c["upperArmR.raise"] = 104; c["upperArmR.bend"] = 26
    c["forearmR.bend"] = 52 + 24 * ph; c["forearmR.twist"] = 64
    c["handR.bend"] = -8 + 14 * wave(f, N, 2, -0.12); fingers(c, "R", 6)
    c["head.rz"] = 5 + 2 * wave(f, N, 1, 0.2); c["head.rx"] = -3
    sh = wave(f, N, 1, 0.1)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.5 * sh; c["chest.rz"] = 1.0 * sh
    jk, beats = syllables(N, 17, amp=(4, 11))
    c["jaw.rx"] = jaw_from(jk, f, N)
    w1 = wave(f - 3, N, 2); w2 = wave(f - 7, N, 2)
    put_wings(c, padd(WHALF, {"1.rz": 2.0 * w1, "3.rz": 3.0 * w2, "p.rz": 5 * w2}),
              padd(WHALF, {"1.rz": 1.0 * w1, "3.rz": 1.5 * w2, "p.rz": 3 * w2}))
    stand_feet(rig, c)
    blink(c, f, N, [20])
    return c


FU_N = 105
FU_TOP = 1.2


def fu_phase(f):
    """fly_up wing phase: wings up (top) at 14, first huge down-stroke to 28, top at 38, then 27-frame beats
    (down-strokes centred at 21, 45, 72 = the story's wing_flap sfx at 0.6 / 1.5 s)."""
    if f <= 14:
        return 0.0
    if f <= 28:
        return D_STROKE * (f - 14) / 14
    if f <= 38:
        return D_STROKE + (1 - D_STROKE) * (f - 28) / 10
    return 1.0 + (f - 38) / 27.0


@clip("gabriel", "fly_up", FU_N, False, auto_markers={"takeoff": "takeoff"},
      notes=f"from the half-open standing pose (wave): crouches (knees bend, arms swing back, wings rise high), "
            f"springs with a huge down-stroke (feet leave the page at `takeoff`), then two more beats, faster (0.9 s), "
            f"rising and drifting back toward the gate; looks up, joyful; legs trail with pointed toes; root rises "
            f"to {FU_TOP} (and 0.18 back) in the clip; ends in the air (off the top of the page)")
def gabriel_fly_up(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    TK = 18
    ph = fu_phase(f)
    p = ph % 1.0
    crouch = ease_io((f - 1) / 11) * (1 - ease_io((f - 12) / 6))
    spring = ease_io((f - 12) / 6)
    # root: on the page until the takeoff, then accelerating up (+ a little lift on every down-stroke)
    if f <= TK - 1:
        ry = 0.0
    else:
        u = (f - (TK - 1)) / (N - (TK - 1))
        ry = FU_TOP * (0.25 * u + 0.75 * u ** 1.7) + 0.012 * max(0.0, -stroke(ph - 0.18)) * smooth((f - TK) / 10)
    c["root.ty"] = ry
    c["root.tz"] = -0.18 * smooth((f - 22) / 83)
    c["hips.ty"] = -0.050 * crouch + 0.006 * spring * (1 - smooth((f - 22) / 10))
    # legs: planted (crouch, push-off onto the toes) -> trailing behind, toes pointed
    pitch_push = 34 * ease_io((f - 13) / 5)
    w_air = ease_io((f - TK) / 12)
    for side, sx, dy, dz, pa in (("L", 1, 0.024, -0.006, 36), ("R", -1, 0.040, -0.034, 42)):
        b = rig.head["foot" + side]
        pitch = lerp(pitch_push, pa, w_air)
        y_pl = planted_ankle_y(rig, side, pitch)
        wy = max(y_pl, ry + y_pl + dy * w_air)
        c[f"ik.leg{side}"] = V(b.x + sx * 0.004, wy - ry, b.z + dz * w_air)
        c[f"foot{side}.pitch"] = pitch
        c[f"pole.leg{side}"] = V(0.12 * sx, 0, 1)
    # body: crouch forward, arch up on the spring, then a gentle forward lean in flight, looking up
    c["spine.rx"] = 14 * crouch - 4 * bump(f, 14, 30) + 3 * smooth((f - 30) / 20)
    c["chest.rx"] += 6 * crouch - 7 * bump(f, 14, 32)
    c["neck.rx"] += -4 * smooth((f - 16) / 14); c["head.rx"] += 4 * crouch - 14 * smooth((f - 16) / 18)
    if f >= 28:
        flight_body(c, p, 0.8 * smooth((f - 28) / 8))
    # arms: swing back in the crouch, sweep forward / up on the spring, then float trailing
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.bend"] = 8 - 30 * crouch + 18 * bump(f, 12, 32)
        c[f"upperArm{side}.raise"] = ARM_REST + 34 * bump(f, 12, 36)
        c[f"forearm{side}.bend"] = 24 + 26 * bump(f, 12, 34)
    if f > 26:
        fa = {}
        flight_arms(fa, p)
        w = smooth((f - 26) / 14)
        for k, v in fa.items():
            c[k] = lerp(c.get(k, 0.0), v, w)
    # wings: half -> high (gathered) -> huge first down-stroke -> two more beats
    TOPP = padd(flap(0.0, 1.0), {"1.rz": 8, "2.rz": 3})
    if f <= 14:
        ws = {"1": ease_io(f / 12), "2": ease_io((f - 2) / 12), "3": ease_io((f - 3) / 12), "p": ease_io((f - 4) / 11)}
        P = pmseg(WHALF, TOPP, ws)
    else:
        amp = K([(14, 1.18), (38, 1.08), (65, 1.0), (105, 0.95)], f)
        P = flap(ph, amp)
        P = pm(TOPP, P, smooth((f - 14) / 3))
    put_wings(c, P, padd(P, {"1.rz": 0.5 * wave(f, 54, 1)}))
    blink(c, f, N, [6, 70], loop=False)
    return c


# =============================================================================================== solve
HAND_SPACES = ("handL", "handR")


def ik_limb(rig, basis, M, chs, limb):
    up, lo, end = {"legL": ("thighL", "shinL", "footL"), "legR": ("thighR", "shinR", "footR"),
                   "armL": ("upperArmL", "forearmL", "handL"), "armR": ("upperArmR", "forearmR", "handR")}[limb]
    key = "ik." + limb
    if key not in chs:
        return
    w = chs.get("ikw." + limb, 1.0)
    if w <= 1e-4:
        return
    legs = limb.startswith("leg")
    side = limb[-1]
    sx = 1 if side == "L" else -1
    t = Vector(chs[key])
    space = chs.get("ikspace." + limb, "root")
    Mroot = M["root"] @ rig.rest["root"].inverted()
    if space in M and space != "root":
        t_world = to_d(M[space] @ (rig.rest[space].inverted() @ to_bl(rig.head[space] + t)))
    else:
        t_world = to_d(Mroot @ to_bl(t))
    pole = V(0.15 * sx, 0, 1) if legs else V(0.6 * sx, -0.6, -0.5)
    if "pole." + limb in chs:
        pole = Vector(chs["pole." + limb])
    pole = to_d(Mroot.to_3x3() @ to_bl(pole))
    old = {n: [basis[n][0].copy(), basis[n][1].copy(), basis[n][2]] for n in (up, lo, end)}
    ik2(rig, basis, M, up, lo, t_world, pole, legs)
    if legs:
        pitch = chs.get(f"foot{side}.pitch", 0.0)
        Rf = Mroot.to_3x3().normalized() @ rot_d((0, 1, 0), chs.get(f"foot{side}.ry", 0.0)) @ rot_d((1, 0, 0), pitch) @ rig.rest3[end]
        rig.set_world_rot(basis, M, end, Rf)
    else:
        # keep the hand's own channels (bend / twist) on top of the IK'd forearm
        pass
    if w < 0.9999:
        for n in (up, lo, end):
            basis[n][0] = old[n][0].slerp(basis[n][0], w)
        rig.fk(basis, M)


def evaluate_primary(rig, clip_, f):
    chs = clip_.fn(rig, f, clip_.N)
    out = solve_pose(rig, chs)
    st = chs.get("settle")
    if st:
        for bone, vbones, target, w in (st if isinstance(st, list) else [st]):
            if w <= 1e-4:
                continue
            _, _, M = out
            pts = rig.skin(M, set(vbones) if vbones else None)
            low = min(p.y for p in pts)
            chs[bone + ".ty"] = chs.get(bone + ".ty", 0.0) + w * (target - low)
            out = solve_pose(rig, chs)
    return out


def solve_pose(rig, chs):
    basis = rig.basis_from(chs)
    M = rig.fk(basis)
    for limb in ("legL", "legR"):
        ik_limb(rig, basis, M, chs, limb)
    late = []
    for limb in ("armL", "armR"):
        if chs.get("ikspace." + limb, "root") in HAND_SPACES:
            late.append(limb); continue
        ik_limb(rig, basis, M, chs, limb)
    for limb in late:
        ik_limb(rig, basis, M, chs, limb)
    trumpet_post(rig, chs, basis, M)
    return chs, basis, M


WING_SPRING = os.environ.get("GA_WINGSPRING", "1") == "1"
CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "gabriel": [(("hair1", "hair2"), 95.0, 8.0, 0.25, 22.0), (("sash1", "sash2"), 80.0, 7.0, 0.30, 26.0)]
    + ([(("wingL2", "wingL3", "wingL_prim"), 420.0, 17.0, 0.0, 7.0), (("wingR2", "wingR3", "wingR_prim"), 420.0, 17.0, 0.0, 7.0)]
       if WING_SPRING else []),
}


def sim_chains(rig, prim, loop, rng=None):
    N = len(prim) - 1
    for names, k, cdamp, gw, lim in CHAINS[rig.ch]:
        if any(n not in rig.names for n in names):
            continue
        seq = (list(range(N)) * 3 + [N]) if loop else list(range(N + 1))
        state = {}
        out = {n: [None] * (N + 1) for n in names}
        sub = 4
        dt = 1.0 / FPS / sub
        # the keyed rotations: every pass of a loop springs toward these (not toward the previous pass' result)
        keyed = [{n: prim[fr][1][n][0].copy() for n in names} for fr in range(N + 1)]
        top = names[0]
        for idx, fr in enumerate(seq):
            chs, basis, M = prim[fr]
            for n in names:
                basis[n][0] = keyed[fr][n].copy()
            rig.fk(basis, M, only=rig.subtree(top))
            Mroot3 = (M["root"] @ rig.rest["root"].inverted()).to_3x3().normalized()
            for n in names:
                Cm = rig.carried(M, n).to_3x3().normalized()
                cur_c = (Cm @ basis[n][0].to_matrix()).col[1].normalized()
                rest_w = (Mroot3 @ rig.rest3[n].col[1]).normalized()
                tgt = cur_c.slerp(rest_w, gw) if gw > 0 else cur_c
                if n not in state:
                    state[n] = [tgt.copy(), Vector((0, 0, 0))]
                s, v = state[n]
                for _ in range(sub):
                    acc = (tgt - s) * k - v * cdamp
                    v = v + acc * dt
                    s = (s + v * dt).normalized()
                ang = s.angle(tgt) if s.dot(tgt) < 0.99999999 else 0.0
                if ang > math.radians(lim):
                    s = tgt.slerp(s, math.radians(lim) / ang)
                state[n] = [s, v]
                Rd = cur_c.rotation_difference(s).to_matrix()
                rig.set_world_rot(basis, M, n, Rd @ (Cm @ basis[n][0].to_matrix()))
                if (not loop) or idx >= len(seq) - (N + 1):
                    out[n][fr] = s.copy()
        if loop or rng:
            a_, b_ = (0, N) if loop else rng
            for n in names:
                d0, dN = out[n][a_], out[n][b_]
                Rfull = dN.rotation_difference(d0)
                for fr in range(a_, b_ + 1):
                    qi = Quaternion().slerp(Rfull, (fr - a_) / (b_ - a_))
                    out[n][fr] = (qi.to_matrix() @ out[n][fr]).normalized()
            for fr in range(a_, b_ + 1):
                chs, basis, M = prim[fr]
                for n in names:
                    Cm = rig.carried(M, n).to_3x3().normalized()
                    cur = (Cm @ basis[n][0].to_matrix()).col[1].normalized()
                    Rd = cur.rotation_difference(out[n][fr]).to_matrix()
                    rig.set_world_rot(basis, M, n, Rd @ (Cm @ basis[n][0].to_matrix()))


def bake_clip(rig, clip_):
    N = clip_.N
    prim = [evaluate_primary(rig, clip_, f) for f in range(N + 1)]
    if clip_.loop:
        chs0, b0, M0 = prim[0]
        bN = {n: [b0[n][0].copy(), b0[n][1].copy(), b0[n][2].copy()] for n in b0}
        prim[N] = (prim[N][0], bN, rig.fk(bN))
    sim_chains(rig, prim, clip_.loop, clip_.info.get("loopRange"))
    if clip_.loop:
        b0 = prim[0][1]
        bN = {n: [b0[n][0].copy(), b0[n][1].copy(), b0[n][2].copy()] for n in b0}
        prim[N] = (prim[N][0], bN, rig.fk(bN))
    return [(p[1], p[2]) for p in prim]


def write_action(rig, clip_, frames):
    obj = rig.obj
    act = bpy.data.actions.get(clip_.action) or bpy.data.actions.new(clip_.action)
    act.use_fake_user = True
    obj.animation_data_create()
    obj.animation_data.action = act
    n = len(frames)
    for pb in obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
    lin = bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value
    for name in rig.names:
        qs, ls, ss = [], [], []
        prevq = None
        for basis, _ in frames:
            q, l, s = basis[name]
            q = q.copy()
            if prevq is not None and prevq.dot(q) < 0:
                q.negate()
            prevq = q
            qs.append(q); ls.append(l); ss.append(s)
        for path, comps in ((f'pose.bones["{name}"].rotation_quaternion', [[q[i] for q in qs] for i in range(4)]),
                            (f'pose.bones["{name}"].location', [[l[i] for l in ls] for i in range(3)]),
                            (f'pose.bones["{name}"].scale', [[s[i] for s in ss] for i in range(3)])):
            for i, vals in enumerate(comps):
                fc = act.fcurve_ensure_for_datablock(obj, path, index=i, group_name=name)
                fc.keyframe_points.clear()
                fc.keyframe_points.add(n)
                co = []
                for fr, v in enumerate(vals):
                    co += [float(fr), float(v)]
                fc.keyframe_points.foreach_set("co", co)
                fc.keyframe_points.foreach_set("interpolation", [lin] * n)
                fc.update()
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, clip_.N
    act.use_cyclic = clip_.loop
    for m in list(act.pose_markers):
        act.pose_markers.remove(m)
    for mname, mf in clip_.markers.items():
        pm_ = act.pose_markers.new(mname); pm_.frame = int(mf)
    return act


# =============================================================================================== scene helpers
def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rig_obj = bpy.data.objects["gabriel_rig"]
    rig_obj.location = (0, 0, 0)            # character-local (the blend keeps the rig at the sheet slot)
    rigs = {"gabriel": Rig("gabriel", rig_obj)}
    return sc, rigs


def contract_clips():
    return {"gabriel": ["idle", "hover", "fly_down", "fold_wings", "walk", "kneel_talk", "stand_up", "talk", "point_up",
                        "raise_trumpet", "blow_trumpet", "spread_wings", "bless", "wave", "fly_up"]}


def timeline_clips():
    return sorted({(a["who"], a["clip"]) for a in TL["acting"]})


def travel_needs():
    loco = {c.action: c for c in CLIPS if c.speed}
    pos, out = {}, []
    acts = sorted(TL["acting"], key=lambda a: a["t"])
    for i, a in enumerate(acts):
        who, to = a["who"], a.get("to")
        if to is None:
            continue
        p0 = pos.get(who)
        pos[who] = to
        act = f"{who}_{a['clip']}"
        if p0 is None:
            continue
        nxt = next((b["t"] for b in acts[i + 1:] if b["who"] == who), None)
        dist = math.hypot(to[0] - p0[0], to[1] - p0[1])
        if dist < 1e-4:
            continue
        row = {"t": round(a["t"], 2), "action": act, "from": p0, "to": to, "dist": round(dist, 3),
               "time": None if nxt is None else round(nxt - a["t"], 2)}
        if nxt:
            row["needSpeed"] = round(dist / (nxt - a["t"]), 3)
        if act in loco:
            row["naturalSpeed"] = round(loco[act].natural_speed, 3)
            if nxt:
                row["rate"] = round(row["needSpeed"] / loco[act].natural_speed, 2)
        else:
            row["glide"] = True
        out.append(row)
    return out


def mesh_points(rig, step_n=6000, skip_props=(), full=False):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in rig.obj.children:
        if o.type != 'MESH' or o.name.endswith("_eyelids") or o.name in skip_props:
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = rig.obj.matrix_world.inverted() @ o.matrix_world
        n = len(me.vertices)
        step = 1 if full else max(1, n // step_n)
        for i in range(0, n, step):
            pts.append((to_d(mw @ me.vertices[i].co), o.name))
        ev.to_mesh_clear()
    return pts


def apply_basis(rig, basis):
    for n in rig.names:
        pb = rig.obj.pose.bones[n]
        pb.rotation_mode = 'QUATERNION'
        q, l, s = basis[n]
        pb.rotation_quaternion = q; pb.location = l; pb.scale = s


def reset_pose(rig):
    for pb in rig.obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)


PROPS = ("trumpet", "sword")


def hidden_props(rig, cl):
    out = []
    if "gabriel_trumpet" in bpy.data.objects and "trumpet" not in cl.props:
        out.append("gabriel_trumpet")
    return out


_BODY_GROUPS = {}


def body_vertex_sets():
    """Indices of body vertices by dominant bone family (feathers / back foot) for the feather-poke check."""
    if not _BODY_GROUPS:
        body = bpy.data.objects["gabriel_body"]
        gi = {g.index: g.name for g in body.vertex_groups}
        wing, foot = [], []
        for v in body.data.vertices:
            gs = sorted(((g.weight, gi[g.group]) for g in v.groups), reverse=True)
            if not gs:
                continue
            d = gs[0][1]
            if d.startswith("wing"):
                wing.append(v.index)
            elif d in ("footR", "toeR"):
                foot.append(v.index)
        _BODY_GROUPS["wing"], _BODY_GROUPS["footR"] = wing, foot
    return _BODY_GROUPS


def feather_poke(rig, basis):
    """Smallest distance from a back-foot (footR / toeR) vertex to a feather vertex in this pose, and how many foot
    vertices are within 4 mm of a feather (0 = clear)."""
    apply_basis(rig, basis); bpy.context.view_layer.update()
    body = bpy.data.objects["gabriel_body"]
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me = ev.to_mesh()
    mw = rig.obj.matrix_world.inverted() @ body.matrix_world
    sets = body_vertex_sets()
    from mathutils.kdtree import KDTree
    wing = [mw @ me.vertices[i].co for i in sets["wing"]]
    kd = KDTree(len(wing))
    for i, p in enumerate(wing):
        kd.insert(p, i)
    kd.balance()
    dmin, near = 9.0, 0
    for i in sets["footR"]:
        co, idx, d = kd.find(mw @ me.vertices[i].co)
        dmin = min(dmin, d)
        if d < 0.004:
            near += 1
    ev.to_mesh_clear()
    return round(dmin, 4), near


def foot_low(rig, M):
    """Lowest point of either foot (heel / ball / toe tip) in root space."""
    lo = 9.0
    for side in "LR":
        fm = M["foot" + side] @ rig.rest_inv["foot" + side]
        a = rig.head["foot" + side]
        for q in foot_points(rig, side):
            lo = min(lo, to_d(fm @ to_bl(a + q)).y)
    return lo


def clip_checks(rig, cl, frames):
    out = {}
    ad = rig.obj.animation_data
    keep = ad.action if ad else None
    if ad:
        ad.action = None
    step = 3 if cl.N <= 60 else 5
    lows = []
    low_at = None
    skip = hidden_props(rig, cl)
    for fr in range(0, cl.N + 1, step):
        apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
        pts = mesh_points(rig, skip_props=skip)
        lp = min(pts, key=lambda q: q[0].y)
        lows.append(lp[0].y)
        if lp[0].y <= min(lows):
            low_at = [fr, lp[1], [round(v, 3) for v in lp[0]]]
    out["meshMinY"] = round(min(lows), 4)
    if min(lows) < -0.004:
        out["meshMinAt"] = low_at
    if cl.name in ("kneel_talk", "kneel_down", "stand_up"):
        pk = []
        for fr in sorted(set([0, cl.N // 2, cl.N] + list(range(0, cl.N + 1, 10)))):
            pk.append((fr,) + feather_poke(rig, frames[fr][0]))
        out["backFootToFeatherMin"] = min(p[1] for p in pk)
        out["backFootVertsWithin4mm"] = max(p[2] for p in pk)
    tips = [("toeL", "head"), ("toeR", "head")]
    if cl.speed is None:
        drift = 0.0
        for bn, at in tips:
            ref = None
            for basis, M in frames:
                p = rig.pos(M, bn, at)
                if p.y < 0.012 and rig.pos(M, "foot" + bn[-1]).y < 0.03:
                    if ref is None:
                        ref = p
                    drift = max(drift, math.hypot(p.x - ref.x, p.z - ref.z))
                else:
                    ref = None
        out["plantedDriftMax"] = round(drift, 4)
    else:
        out["naturalSpeed"] = round(cl.natural_speed, 4)
        v = cl.natural_speed / FPS
        err = 0.0

        def cpts(M, bn):
            side = bn[-1]
            fm = M["foot" + side] @ rig.rest_inv["foot" + side]
            a = rig.head["foot" + side]
            return [to_d(fm @ to_bl(a + q)) for q in foot_points(rig, side)]
        for bn, at in tips:
            for fr in range(cl.N):
                q0, q1 = cpts(frames[fr][1], bn), cpts(frames[fr + 1][1], bn)
                i = min(range(len(q0)), key=lambda j: q0[j].y)
                p0, p1 = q0[i], q1[i]
                if p0.y < 0.0015 and p1.y < 0.0015:
                    err = max(err, math.hypot(p1.x - p0.x, (p1.z - p0.z) + v) * FPS)
        out["stanceSlipMax"] = round(err, 4)
    reset_pose(rig)
    if ad:
        ad.action = keep
    return out


SAMPLE_BONES = ("root", "head", "jaw", "handR", "handL", "footL", "toeR", "hips", "hair2", "sash2", "wingL1", "wingL3",
                "wingR_prim", "wingR2", "trumpet")


def measured_markers(rig, cl, frames):
    out = {}
    lows = [foot_low(rig, M) for _, M in frames]       # M carries the root motion: page height of the feet
    for name, kind in cl.auto_markers.items():
        if kind == "land":
            fr = next((i for i, y in enumerate(lows) if y <= 0.0015), None)
        else:
            on = [i for i, y in enumerate(lows) if y <= 0.0015]
            fr = (max(on) + 1) if on else None
        if fr is not None:
            out[name] = fr
    return out


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    req = TL.get("requestedClips") or []
    rig = rigs["gabriel"]
    trumpet_hold(rig)
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl, "requestedClips": req,
            "stage": {"kneel": dict(KN, frontAnkle=[round(v, 3) for v in KNEEL_FRONT], hipsDrop=[round(v, 4) for v in kneel_hips(rig)]),
                      "hoverRootY": HOVER_Y, "flyUpRoot": [0.0, FU_TOP, -0.18],
                      "trumpetLipsRest": [round(v, 4) for v in _TR["lips"]]},
            "travel": travel_needs(),
            "rootTravelNote": "hover / fly_down / fly_up carry their height on the `root` bone inside the clip (fly_up also "
                              "0.18 back toward the gate); the director adds no height. All other clips keep root at 0.",
            "propsNote": "gabriel/trumpet is posed for in the clips whose `props` list it (raise_trumpet, blow_trumpet, "
                         "spread_wings); hidden otherwise. gabriel/sword is always shown."}
    only = os.environ.get("GA_ONLY")
    for cl in CLIPS:
        if only and not any(cl.name.startswith(o) or cl.action.startswith(o) for o in only.split(",")):
            continue
        frames = bake_clip(rig, cl)
        mm = measured_markers(rig, cl, frames)
        cl.markers.update(mm)
        write_action(rig, cl, frames)
        seam = None
        if cl.loop:
            M0, MN = frames[0][1], frames[-1][1]
            seam = max((rig.pos(M0, n, "tail") - rig.pos(MN, n, "tail")).length for n in rig.names)
        rootmax = max(rig.pos(M, "root").length for _, M in frames)
        info = {"action": cl.action, "char": cl.ch, "clip": cl.name, "frames": cl.N, "seconds": round(cl.N / FPS, 3),
                "loop": cl.loop, "rootMotion": False,
                "markers": {k: {"frame": v, "sec": round(v / FPS, 3)} for k, v in sorted(cl.markers.items(), key=lambda q: q[1])},
                "loopSeamMaxErr": None if seam is None else round(seam, 6), "rootMaxOffset": round(rootmax, 5),
                "rootY": [round(rig.pos(frames[0][1], "root").y, 4), round(rig.pos(frames[-1][1], "root").y, 4)],
                "props": cl.props, "notes": cl.notes}
        if cl.extra:
            info["extra"] = True
        if cl.speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            info["stride"] = cl.speed[0]
        info.update(cl.info)
        if cl.loop:
            def step(a_, b_):
                return max((rig.pos(frames[a_][1], n, "tail") - rig.pos(frames[b_][1], n, "tail")).length
                           for n in rig.names if n != "eyelids")
            inner = max(step(f_, f_ + 1) for f_ in range(cl.N - 1))
            info["seamStep"] = round(step(cl.N - 1, cl.N), 5); info["maxStep"] = round(inner, 5)
        if "trumpet" in cl.props:
            tp = {}
            for nm, fr in sorted(cl.markers.items(), key=lambda q: q[1]):
                M = frames[fr][1]
                tp[nm] = {"mouthpiece": [round(v, 4) for v in rig.point(M, "trumpet", MOUTH_L)],
                          "bell": [round(v, 4) for v in rig.point(M, "trumpet", BELL_L)],
                          "bellDir": [round(v, 3) for v in (rig.point(M, "trumpet", BELL_L) - rig.point(M, "trumpet", MOUTH_L)).normalized()]}
            if cl.name == "blow_trumpet":
                errs = []
                for fr in range(cl.N + 1):
                    M = frames[fr][1]
                    lips = to_d((M["head"] @ rig.rest_inv["head"]) @ to_bl(_TR["lips"]))
                    errs.append((rig.point(M, "trumpet", MOUTH_L) - lips).length)
                tp["mouthpieceToLipsMax"] = round(max(errs), 5)
                meta["stage"]["trumpetBellAtBlow"] = tp["blow"]["bell"]
                meta["stage"]["trumpetBellDirAtBlow"] = tp["blow"]["bellDir"]
            info["trumpet"] = tp
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        if cl.name in ("fly_down", "fly_up"):
            info["checks"]["footLowAtMarker"] = {k: round(foot_low(rig, frames[v][1]), 4) for k, v in cl.markers.items()}
        print("GA_CHECK", cl.action, json.dumps(info["checks"]), "seam", info.get("seamStep"), "/", info.get("maxStep"),
              "markers", json.dumps(cl.markers), json.dumps(info.get("trumpet", {}))[:400])
        meta["clips"].append(info)
        print(f"GA_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} rootY={info['rootY']}")
    if only:
        print("GA_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "ga_anim.blend")
    bpy.ops.wm.save_as_mainfile(filepath=tmp_blend, compress=True)
    bpy.ops.wm.open_mainfile(filepath=tmp_blend)
    rig_o = bpy.data.objects["gabriel_rig"]
    for o in list(bpy.data.objects):
        if (o.type == 'CAMERA') or (not o.name.startswith("gabriel_")):
            bpy.data.objects.remove(o, do_unlink=True)
    rig_o.location = (0, 0, 0); rig_o.rotation_euler = (0, 0, 0)
    rig_o.animation_data_create()
    rig_o.animation_data.action = None
    for a in sorted(bpy.data.actions, key=lambda a: a.name):
        tr = rig_o.animation_data.nla_tracks.new(); tr.name = a.name
        st = tr.strips.new(a.name, 0, a); st.name = a.name
        tr.mute = True
    for o in rig_o.children:
        if o.type == 'MESH':
            fix_uv_order(o)
            o.hide_render = False; o.hide_viewport = False; o.hide_set(False)
    bpy.context.view_layer.update()
    bpy.ops.object.select_all(action='DESELECT')
    rig_o.select_set(True)
    for o in rig_o.children:
        o.select_set(True)
    bpy.context.view_layer.objects.active = rig_o
    bpy.ops.export_scene.gltf(filepath=os.path.join(ANIM, "gabriel.glb"), use_selection=True, export_yup=True,
                              export_apply=False, export_skins=True, export_animations=True,
                              export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_frame_step=1,
                              export_def_bones=False, export_texcoords=True, export_materials='EXPORT', export_morph=False,
                              export_optimize_animation_size=False, export_anim_slide_to_zero=False,
                              export_rest_position_armature=True, export_negative_frame='CROP')
    print("GA_EXPORT gabriel")
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("GA_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


def fix_uv_order(o):
    me = o.data
    lays = list(me.uv_layers)
    if len(lays) < 2:
        return
    data = {}
    for l in lays:
        buf = [0.0] * (2 * len(l.data)); l.data.foreach_get("uv", buf); data[l.name] = buf
    page = "UVMap" if "UVMap" in data else min(data, key=lambda n: sum(1 for v in data[n] if v < -1e-4 or v > 1 + 1e-4))
    order = [page] + [n for n in data if n != page]
    if [l.name for l in lays] == order:
        return
    for l in list(me.uv_layers):
        me.uv_layers.remove(l)
    for n in order:
        nl = me.uv_layers.new(name=n)
        nl.data.foreach_set("uv", data[n])
    me.uv_layers.active = me.uv_layers[page]
    try:
        me.uv_layers[page].active_render = True
    except Exception:
        pass


def glb_json(path):
    import struct
    b = open(path, "rb").read()
    assert b[:4] == b"glTF"
    l0 = struct.unpack_from("<I", b, 12)[0]
    return json.loads(b[20:20 + l0])


def accessor_range(path, j, idx):
    import struct
    acc = j["accessors"][idx]
    if "min" in acc:
        return acc["min"], acc["max"]
    b = open(path, "rb").read()
    l0 = struct.unpack_from("<I", b, 12)[0]
    bin0 = 20 + l0 + 8
    bv = j["bufferViews"][acc["bufferView"]]
    off = bin0 + bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
    stride = bv.get("byteStride", 8)
    mn, mx = [1e9, 1e9], [-1e9, -1e9]
    for i in range(acc["count"]):
        u, v = struct.unpack_from("<ff", b, off + i * stride)
        mn = [min(mn[0], u), min(mn[1], v)]; mx = [max(mx[0], u), max(mx[1], v)]
    return mn, mx


def mode_verify():
    meta = json.load(open(os.path.join(ANIM, "clips.json")))
    want = {c["action"]: c for c in meta["clips"]}
    out = {"glb": {}, "sampleErr": {}}
    for ch in CHARS:
        path = os.path.join(ANIM, f"{ch}.glb")
        j = glb_json(path)
        anims = {}
        for a in j.get("animations", []):
            tmax = max(j["accessors"][s["input"]]["max"][0] for s in a["samplers"])
            anims[a["name"]] = {"channels": len(a["channels"]), "seconds": round(tmax, 4), "frames": round(tmax * FPS)}
        uv = {}
        for mesh in j.get("meshes", []):
            for pr in mesh["primitives"]:
                for k in ("TEXCOORD_0", "TEXCOORD_1"):
                    if k in pr["attributes"]:
                        mn, mx = accessor_range(path, j, pr["attributes"][k])
                        uv.setdefault(k, []).append((mesh["name"], [round(v, 3) for v in mn], [round(v, 3) for v in mx]))
        uv0_ok = all(mn[0] >= -1e-3 and mn[1] >= -1e-3 and mx[0] <= 1.001 and mx[1] <= 1.001 for _, mn, mx in uv.get("TEXCOORD_0", []))
        out["glb"][ch] = {"bytes": os.path.getsize(path), "animations": anims, "skins": len(j.get("skins", [])),
                          "nodes": [n.get("name") for n in j["nodes"]], "meshes": len(j.get("meshes", [])), "uv": uv,
                          "uv0InUnitSquare": uv0_ok, "joints": len(j["skins"][0]["joints"]) if j.get("skins") else 0}
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.render.fps = FPS
        bpy.ops.import_scene.gltf(filepath=path)
        arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][0]
        errs = {}
        for name, info in want.items():
            if info["char"] != ch:
                continue
            act = next((a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_")), None)
            if act is None:
                errs[name] = "missing"; continue
            arm.animation_data_create(); arm.animation_data.action = act
            if act.slots:
                try:
                    arm.animation_data.action_slot = act.slots[0]
                except Exception:
                    pass
            worst = 0.0
            for fr, bones in info["samples"].items():
                bpy.context.scene.frame_set(int(fr))
                bpy.context.view_layer.update()
                for bn, exp in bones.items():
                    p = arm.matrix_world @ arm.pose.bones[bn].head
                    got = Vector((p.x, p.z, -p.y))
                    worst = max(worst, (got - Vector(exp)).length)
            errs[name] = round(worst, 6)
        out["sampleErr"][ch] = errs
    want_c = contract_clips()
    out["contractMissing"] = {ch: [c for c in want_c[ch] if f"{ch}_{c}" not in out["glb"][ch]["animations"]] for ch in CHARS}
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    for ch in CHARS:
        for nm, a in sorted(out["glb"][ch]["animations"].items()):
            print(f"GA_VERIFY {ch} {nm} {a['frames']}f {a['seconds']}s ch={a['channels']} sampleErr={out['sampleErr'][ch].get(nm)}")
        g = out["glb"][ch]
        print(f"GA_VERIFY_GLB {ch} bytes={g['bytes']} skins={g['skins']} joints={g['joints']} meshes={g['meshes']} "
              f"uv0InUnitSquare={g['uv0InUnitSquare']} uv={json.dumps(g['uv'])}")
        print(f"GA_VERIFY_NODES {ch} {[n for n in g['nodes'] if n and (n in PROPS or n.startswith('gabriel_'))]}")
    print("GA_VERIFY_MISSING", json.dumps(out["contractMissing"]))


# ----------------------------------------------------------------------------------------------- render helpers
FACES = {ch: {"default": v["faceDecal"]["default"], "clips": v["faceDecal"].get("clipExpression", {})}
         for ch, v in REGIONS["characters"].items()}
DECAL_NODES = {}


def srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


DEMO = {"wingFeathers": "#FFFFFF", "wingCoverts": "#F4EEDC", "trumpet": "#E0B040"}


def char_material(ch):
    regs = REGIONS["characters"][ch]["regions"]
    m = bpy.data.materials.new(f"anim_{ch}"); m.use_nodes = True; nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = 0.7
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "st_region"; at.attribute_type = 'GEOMETRY'
    dv = nt.nodes.new("ShaderNodeMath"); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = 64.0
    nt.links.new(at.outputs["Fac"], dv.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    items = sorted((r["id"], DEMO.get(k, r.get("hex", "#cccccc"))) for k, r in regs.items() if "id" in r)
    els[0].position = 0.0; els[0].color = (0.8, 0.8, 0.8, 1)
    els[1].position = 0.999; els[1].color = (0.8, 0.8, 0.8, 1)
    for rid, hx in items:
        e = els.new((rid - 0.5) / 64.0)
        e.color = [srgb_lin(v) for v in hex_rgb(hx)] + [1.0]
    nt.links.new(dv.outputs[0], ramp.inputs["Fac"])
    col = ramp.outputs["Color"]
    fd = FACES[ch]
    dt = nt.nodes.new("ShaderNodeTexImage")
    dt.image = bpy.data.images.load(os.path.join(FACE_DIR, f"{ch}_{fd['default']}.png"), check_existing=True)
    dt.extension = 'CLIP'
    du = nt.nodes.new("ShaderNodeUVMap"); du.uv_map = "decal"
    nt.links.new(du.outputs["UV"], dt.inputs["Vector"])
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'
    nt.links.new(dt.outputs["Alpha"], mx.inputs["Factor"])
    nt.links.new(col, mx.inputs[6]); nt.links.new(dt.outputs["Color"], mx.inputs[7])
    nt.links.new(mx.outputs[2], bsdf.inputs["Base Color"])
    DECAL_NODES[ch] = dt
    return m


def set_expression(ch, clip_name):
    expr = FACES[ch]["clips"].get(clip_name, FACES[ch]["default"])
    p = os.path.join(FACE_DIR, f"{ch}_{expr}.png")
    if not os.path.exists(p):
        p = os.path.join(FACE_DIR, f"{ch}_{FACES[ch]['default']}.png")
    DECAL_NODES[ch].image = bpy.data.images.load(p, check_existing=True)


def setup_look(sc, res, samples=10):
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = -0.15
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    sc.render.film_transparent = False
    sc.world = bpy.data.worlds.new("W")
    sc.world.color = (0.62, 0.72, 0.86)
    try:
        sc.world.use_nodes = True
        bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.62, 0.72, 0.86, 1); bg.inputs[1].default_value = 1.0
    except Exception as e:
        print("GA_WORLD", e)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 2.6; sun.data.angle = math.radians(5)
    sun.rotation_euler = (math.radians(40), math.radians(-12), math.radians(-28))
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    m = char_material("gabriel")
    for o in bpy.data.objects:
        if o.type == 'MESH' and o.name.startswith("gabriel_"):
            o.data.materials.clear(); o.data.materials.append(m)
            o.hide_render = False
    # floor (page) with a 0.1 grid so travel and height read; a ruler post at the back left (ticks every 0.2)
    me = bpy.data.meshes.new("floor")
    R_ = 3.0
    me.from_pydata([(-R_, -R_, -0.0005), (R_, -R_, -0.0005), (R_, R_, -0.0005), (-R_, R_, -0.0005)], [], [(0, 1, 2, 3)])
    fo = bpy.data.objects.new("floor", me); sc.collection.objects.link(fo)
    fm = bpy.data.materials.new("floor"); fm.use_nodes = True; nt = fm.node_tree
    bs = nt.nodes["Principled BSDF"]; bs.inputs["Roughness"].default_value = 0.95
    tc = nt.nodes.new("ShaderNodeTexCoord")
    ch = nt.nodes.new("ShaderNodeTexChecker"); ch.inputs["Scale"].default_value = 30.0
    ch.inputs["Color1"].default_value = (0.86, 0.82, 0.72, 1); ch.inputs["Color2"].default_value = (0.80, 0.75, 0.64, 1)
    nt.links.new(tc.outputs["Object"], ch.inputs["Vector"]); nt.links.new(ch.outputs["Color"], bs.inputs["Base Color"])
    me.materials.append(fm)
    pm_ = bpy.data.materials.new("post"); pm_.use_nodes = True
    pm_.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.35, 0.30, 0.45, 1)
    for i in range(0, 11):
        h = i * 0.2
        bpy.ops.mesh.primitive_cube_add(size=1, location=to_bl(V(-0.62, h, -0.45)))
        o = bpy.context.active_object; o.scale = (0.05 if i % 5 else 0.09, 0.004, 0.006); o.data.materials.append(pm_)
    bpy.ops.mesh.primitive_cube_add(size=1, location=to_bl(V(-0.62, 1.0, -0.45)))
    o = bpy.context.active_object; o.scale = (0.006, 0.006, 2.0); o.data.materials.append(pm_)
    if os.environ.get("GA_SET") == "1" and os.path.exists(SET_GLB):
        bpy.ops.import_scene.gltf(filepath=SET_GLB)


def camera(sc):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.clip_start = 0.005; cam.data.clip_end = 50
    return cam


def look(cam, target_d, cam_d, lens=40):
    cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.location = to_bl(cam_d)
    cam.rotation_euler = (to_bl(target_d) - cam.location).to_track_quat('-Z', 'Y').to_euler()


VIEWS = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "q3b": 145, "top": 20, "low": 20}


def view_cam(cam, rig, view, root_y, bone=None, dist=1.45, lens=40):
    yaw = VIEWS[view]
    tgt = V(0, root_y + 0.36, -0.03); hgt = tgt.y + 0.10
    if bone:
        tgt = to_d(rig.obj.matrix_world @ rig.obj.pose.bones[bone].head)
        hgt = tgt.y + 0.03
    if view == "top":
        hgt = tgt.y + dist * 1.1
    if view == "low":
        hgt = 0.03
    a_ = math.radians(yaw)
    look(cam, tgt, V(tgt.x + math.sin(a_) * dist, hgt, tgt.z + math.cos(a_) * dist), lens=lens)


def show_props(rig, cl):
    hid = hidden_props(rig, cl)
    for o in rig.obj.children:
        o.hide_render = o.name in hid


EXTRA_ROWS = [  # (action, view, frames | None = auto, dist)
    ("hover", "front", [0, 5, 10, 15, 20, 25, 30], 1.6),
    ("hover", "side", [0, 5, 10, 15, 20, 25, 30], 1.6),
    ("fly_down", "front", [0, 20, 56, 100, 112, 126, 144], 1.6),
    ("fly_down", "side", [90, 104, 116, 122, 126, 133, 144], 1.5),
    ("fold_wings", "back", [0, 10, 18, 26, 34, 44, 66], 1.4),
    ("fold_wings", "side", [0, 14, 22, 30, 42, 66], 1.3),
    ("kneel_talk", "side", [0, 75], 1.2),
    ("kneel_talk", "q3b", [0, 75], 1.2),
    ("blow_trumpet", "front", None, 1.5),
    ("fly_up", "side", [0, 12, 18, 24, 32, 45, 72, 105], 1.7),
    ("spread_wings", "front", None, 1.5),
]


def mode_contact():
    sc, rigs = open_scene()
    setup_look(sc, (380, 380), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    rig = rigs["gabriel"]
    baked = {}
    clips = {c.name: c for c in CLIPS}
    meta = json.load(open(os.path.join(ANIM, "clips.json")))
    mk_of = {c["clip"]: {k: v["frame"] for k, v in c["markers"].items()} for c in meta["clips"]}
    only = os.environ.get("GA_ONLY")

    def render_row(cl, view, picks, dist, label=None):
        set_expression("gabriel", cl.name); show_props(rig, cl)
        if cl.name not in baked:
            baked[cl.name] = bake_clip(rig, cl)
        frames = baked[cl.name]
        mk = mk_of.get(cl.name, cl.markers)
        row = {"action": label or cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": [], "extra": cl.extra, "view": view}
        for fr in picks:
            apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
            ry = rig.pos(frames[fr][1], "root").y
            view_cam(cam, rig, view, ry, dist=dist)
            fn = f"{cl.name}_{view}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "ry": ry, "marker": ",".join(k for k, v in mk.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("GA_CONTACT_ROW", cl.action, view, picks, flush=True)

    for cl in CLIPS:
        if only and cl.name not in only.split(","):
            continue
        mk = sorted(set(mk_of.get(cl.name, cl.markers).values()))
        picks = sorted(set([0, cl.N] + [int(round(cl.N * k / 5)) for k in range(1, 5)] + mk))
        while len(picks) > 7:
            cand = [p for p in picks if p not in mk and p not in (0, cl.N)] or [p for p in picks if p not in (0, cl.N)]
            picks.remove(cand[len(cand) // 2])
        render_row(cl, "q3", picks, 1.45)
    for name, view, picks, dist in EXTRA_ROWS:
        if only and name not in only.split(","):
            continue
        cl = clips[name]
        if picks is None:
            mk = sorted(set(mk_of.get(cl.name, cl.markers).values()))
            picks = sorted(set([0, cl.N // 4, cl.N // 2] + mk))[:7]
        render_row(cl, view, [min(p, cl.N) for p in picks], dist)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """GA_PROBE="clip:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|q3b|top|low."""
    sc, rigs = open_scene()
    res = int(os.environ.get("GA_PROBE_RES", "440"))
    setup_look(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    clips = {cl.name: cl for cl in CLIPS}
    rig = rigs["gabriel"]
    baked = {}
    out = []
    for item in os.environ.get("GA_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        name, frames, view = parts[0], parts[1], parts[2] if len(parts) > 2 else "q3"
        bone = None
        if "#" in view:
            view, bone = view.split("#")
        cl = clips[name]
        set_expression("gabriel", cl.name); show_props(rig, cl)
        if name not in baked:
            baked[name] = bake_clip(rig, cl)
        for fr in [int(v) for v in frames.split(",")]:
            fr = min(fr, cl.N)
            apply_basis(rig, baked[name][fr][0]); bpy.context.view_layer.update()
            ry = rig.pos(baked[name][fr][1], "root").y
            view_cam(cam, rig, view, ry, bone, dist=float(os.environ.get("GA_PROBE_DIST", "1.4")) if not bone else 0.32)
            fn = f"{name}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("GA_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("GA_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
