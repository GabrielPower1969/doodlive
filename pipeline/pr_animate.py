"""The prodigal son skeletal animation (Animation role, story pack #6).

Copied from pipeline/ex_animate.py (Exodus) and adapted. Two halves in one file:

* Under Blender (headless) it opens `assets/prodigal/model/characters.blend` (Characters role's rigs), builds every clip
  of docs/prodigal/CONTRACT.md §4 as an action `<char>_<clip>` and exports
  `assets/prodigal/anim/{son,father,brother}.glb` (character + skin + one glTF animation per action) and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/pr_animate.py all        # build + verify + contact sheet
    python3 pipeline/pr_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/pr_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/pr_animate.py contact    # anim/contact_sheet.png (key poses per clip + pair rows)
    PR_PROBE="father_run:0,6:side" python3 pipeline/pr_animate.py probe     # work renders ($PR_ANIM_WORK/probe.png)
    PR_ONLY=son_idle,father_run  (with build: bake + check a subset, no export)

Method as Exodus / Ruth (docs/prodigal/ANIMATION.md §7): clip functions frame -> channels in design axes, Catmull-Rom
keys, leg / arm IK, the planted-prop solver (here the brother's hoe: blade edge `hoeTip` on the page), damped spring
chains (father's beard, robe panels and head-cloth, the son's robe panels and spring-hung purse, the brother's
head-cloth tails), irregular blinks, syllable jaw rhythms. Prop visibility per clip (and per frame window) follows the
timeline's prop events.
Intermediates: $PR_ANIM_WORK (default /tmp/pr_anim_work).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
PRD = os.path.join(ROOT, "assets/prodigal")
MODEL = os.path.join(PRD, "model")
ANIM = os.path.join(PRD, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
SET_GLB = os.path.join(MODEL, "homeland.glb")
TIMELINE = os.path.join(PRD, "timeline.json")
FACES_JSON = os.path.join(PRD, "faces.json")
FACE_DIR = os.path.join(ROOT, "docs/prodigal/design/faces")
WORK = os.environ.get("PR_ANIM_WORK") or "/tmp/pr_anim_work"
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FPS = 30
CHARS = ("son", "father", "brother")

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
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith(("PR_", "Traceback", "Error", "  File")) or "Error" in ln]
    print("\n".join(tail[-260:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def compose_contact():
    from PIL import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(WORK, "contact", "contact.json")))
    cell, pad, lab = 170, 6, 34
    rows = meta["rows"]
    ncol = max(len(r["frames"]) for r in rows)
    W = 230 + ncol * (cell + pad) + pad
    H = 60 + len(rows) * (cell + lab + pad)
    sheet = Image.new("RGB", (W, H), (250, 246, 236))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 17)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((pad, 14), "The prodigal son - key poses per clip (30 fps; frame / seconds; marker names in red; * = extra clip; "
                      "pair rows = two actors at their story distance)", fill=(40, 30, 20), font=font)
    y = 60
    for r in rows:
        d.text((pad, y + 6), r["action"] + (" *" if r.get("extra") else ""), fill=(40, 30, 20), font=font)
        d.text((pad, y + 30), f"{r['frames_total']} f  {r.get('seconds', r['frames_total'] / FPS):.4g} s", fill=(90, 80, 70), font=small)
        d.text((pad, y + 48), "loop" if r["loop"] else "one-shot (holds last)", fill=(90, 80, 70), font=small)
        x = 230
        for fr in r["frames"]:
            im = Image.open(os.path.join(WORK, "contact", fr["file"])).convert("RGB").resize((cell, cell))
            sheet.paste(im, (x, y))
            d.text((x + 4, y + cell + 2), f"f{fr['f']}  {fr['f'] / FPS:.2f}s", fill=(60, 50, 40), font=small)
            if fr.get("marker"):
                d.text((x + 4, y + cell + 17), fr["marker"], fill=(200, 30, 30), font=small)
            x += cell + pad
        y += cell + lab + pad
    out = os.path.join(ANIM, "contact_sheet.png")
    sheet = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT) if os.environ.get("PR_QUANT", "0") == "1" else sheet
    sheet.save(out, optimize=True)
    print("PR_CONTACT", out, sheet.size)


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get("PR_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("PR_PROBE_OUT", "probe.png"))
    sheet.save(out); print("PR_PROBE_SHEET", out)


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
    """K with every key delayed by `lag` frames (overlapping action: a child follows its parent late)."""
    return K(keys, f - lag, N, loop)


def wave(f, N, cycles=1.0, phase=0.0):
    return math.sin(2 * math.pi * (cycles * f / N + phase))


def ease_io(t):
    t = min(1.0, max(0.0, t)); return 0.5 - 0.5 * math.cos(math.pi * t)


def bump(f, a, b):
    """0 -> 1 -> 0 between frames a and b (sine hump, eased)."""
    if f <= a or f >= b:
        return 0.0
    return math.sin(math.pi * smooth((f - a) / (b - a)))


def pulses(f, N, hits, decay=5.0, loop=True):
    """Irregular hits [(frame, strength)]: sharp attack, exponential decay (laughs, sobs, shakes)."""
    v = 0.0
    for h, s in hits:
        d = f - h
        if loop:
            d = d % N
        if 0 <= d < 6 * decay:
            v += s * (1 - math.exp(-d * 1.5)) * math.exp(-d / decay)
    return v


def vlerp(a, b, t):
    return Vector(a).lerp(Vector(b), t)


# ----------------------------------------------------------------------------------------------- acting helpers
BLINK_SHAPE = [1.0, 6.5, 12.8, 12.8, 8.0, 3.5, 1.0]      # frames 0..6: fast close, short hold, slower open


def blink(c, f, N, at, loop=True, base=1.0, slow=1.0):
    """Eyelids: blinks starting at the frames in `at` (irregular on purpose). base > 1 = heavy / half-shut lids."""
    s = base
    for b in at:
        d = (f - b) % N if loop else f - b
        u = d / slow
        if 0 <= u < len(BLINK_SHAPE) - 1:
            i = int(u); w = u - i
            s = max(s, lerp(BLINK_SHAPE[i], BLINK_SHAPE[i + 1], w))
    c["eyelids.sy"] = s


def syllables(N, seed, amp=(6.0, 15.0), dur=(3.0, 6.5), gap=0.2, lead=3, tail=5):
    """Irregular jaw keys for talking: syllables of varying length and opening, word gaps and breaths.
    Returns (keys, beats) - beats are the frames of the strongest syllables (for nods and hand beats)."""
    r = random.Random(seed)
    keys = [(0, 0.0)]
    t = float(lead)
    beats = []
    while t < N - tail - dur[0]:
        d = r.uniform(*dur)
        a = r.uniform(*amp)
        if r.random() < 0.22:
            a *= 0.45                       # unstressed / closed vowel
        peak = t + d * r.uniform(0.35, 0.55)
        keys.append((peak, a)); keys.append((t + d, r.uniform(0.0, 2.5)))
        if a > amp[0] + 0.70 * (amp[1] - amp[0]):
            beats.append(peak)
        t += d
        if r.random() < gap:
            t += r.uniform(5, 13)          # word gap / little breath
            keys.append((t - 1, 0.0))
    keys.append((N, 0.0))
    return sorted(keys), beats


def jaw_from(keys, f, N):
    return max(0.0, K(keys, f % N, N, False))


def beat_curve(beats, f, N, width=7.0, loop=True):
    """0..1 bumps at the beat frames (rise 40 %, fall 60 % of width)."""
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
    H_OF = {"son": 0.34, "father": 0.36, "brother": 0.37}

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
        self.staff_foot = None
        self.pole = None
        if "hoeTip" in self.names:
            # the brother's hoe: the blade edge (hoeTip head) in the hoe bone's local frame (Moses's staff solver)
            self.pole = "hoe"
            self.staff_foot = self.rest["hoe"].inverted() @ self.rest["hoeTip"].translation
            self.staff_len = (self.head["hoeTip"] - self.head["hoe"]).length
        # prop axis (bone-local): from the bone head to the mesh centroid (the stalk ears point this way)
        self.prop_axis = {}
        self.prop_cen = {}
        for b in ():
            o = bpy.data.objects.get(f"{ch}_{b}")
            if o is not None and b in self.names:
                mw = obj.matrix_world.inverted() @ o.matrix_world
                cen = sum((mw @ v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
                self.prop_axis[b] = (self.rest[b].inverted().to_3x3() @ (cen - self.rest[b].translation)).normalized()
                self.prop_cen[b] = to_d(cen) - self.head[b]          # drum centre: offset from the bone head (rest axes)

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
                R = R @ rot_d(hz if n[-1] == "L" else -hz, g("curl"))      # + = close the hand (RIG.md posetest)
            if g("bend"):
                ax = d.cross(V(0, 0, 1))
                if ax.length < 1e-6:
                    ax = V(1, 0, 0)
                R = R @ rot_d(ax, g("bend"))
            if g("twist"): R = R @ rot_d(d, g("twist"))
            Rr = self.rest3[n]
            q = (Rr.inverted() @ R @ Rr).to_quaternion()
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

    def ydir(self, M, n):
        return to_d(M[n].to_3x3() @ Vector((0, 1, 0))).normalized()

    def foot_of_staff(self, M):
        return to_d(M[self.pole] @ self.staff_foot)


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
    def __init__(self, ch, name, N, loop, fn, markers=None, notes="", extra=False, speed=None, props=None, backwards=False,
                 natural=None, timescale=1.0, prop_win=None):
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = markers or {}
        self.notes = notes
        self.extra = extra
        self.speed = speed           # (stride L, duty) for in-place locomotion -> natural speed
        self.props = props or []     # props this clip is posed for (shown in renders; Integration shows them by `prop`)
        self.backwards = backwards
        self.natural = natural       # explicit natural speed (u/s) for in-place locomotion without a gait (ride)
        self.timescale = timescale   # GLB times x this (unused here, kept from Exodus)
        self.prop_win = prop_win or {}   # prop -> (first, last) frame it is shown (timeline prop events)
        if ch == "brother" and "hoe" not in self.props:
            self.props = self.props + ["hoe"]

    @property
    def action(self):
        return f"{self.ch}_{self.name}"

    @property
    def natural_speed(self):
        if self.natural is not None:
            return self.natural
        if not self.speed:
            return None
        L, duty = self.speed
        return L / (duty * self.N / FPS)


CLIPS = []


def clip(ch, name, N, loop, **kw):
    def deco(fn):
        CLIPS.append(Clip(ch, name, N, loop, fn, **kw)); return fn
    return deco


# ----------------------------------------------------------------------------------------------- legs
def foot_points(rig, side):
    a = rig.head["foot" + side]
    ball = rig.head["toe" + side] - a
    tip = rig.tail["toe" + side] - a
    ball.y = tip.y = -a.y + 0.0005          # the sole under the ball / toe tip (the toe bones sit above it)
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


def gait(rig, f, N, L, lift, duty, offsetR=0.5, offsetL=0.0, heel=10.0, toeoff=24.0, out=None, lift_shape=1.0,
         spread=0.0, fwd=0.0):
    """In-place gait: per side the ankle target (root space) and foot pitch. Stance: the foot slides from +L/2 to
    -L/2 at constant speed (speed = L / (duty * N / FPS)); swing: eased return with lift."""
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
            contact = True
        else:
            s = (p - duty) / (1 - duty)
            z = -L / 2 + L * smooth(s)
            pitch = lerp(toeoff, -heel, smooth(s * 1.1))
            y = planted_ankle_y(rig, side, pitch) + lift * math.sin(math.pi * min(1.0, s)) ** lift_shape
            contact = False
        out["leg" + side] = (V(base.x + sx * spread, y, base.z + z + fwd), pitch, contact, p)
    return out


def legs_ik_channels(chs, g):
    for side in "LR":
        t, pitch, _, _ = g["leg" + side]
        chs[f"ik.leg{side}"] = t
        chs[f"foot{side}.pitch"] = pitch


def stand_feet(rig, chs, spread=0.0, fwdL=0.0, fwdR=0.0, pitchL=0.0, pitchR=0.0, liftL=0.0, liftR=0.0, fwd=0.0, xL=0.0, xR=0.0):
    for side, fw, pt, lf, xo in (("L", fwdL, pitchL, liftL, xL), ("R", fwdR, pitchR, liftR, xR)):
        b = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        chs[f"ik.leg{side}"] = V(b.x + sx * spread + xo, planted_ankle_y(rig, side, pt) + lf, b.z + fw + fwd)
        chs[f"foot{side}.pitch"] = pt


def arm_ik(c, side, target, pole=None, space="root", w=1.0):
    """Arm IK layer: later layers blend over earlier ones by their weight (targets mixed in world space, see ik_limb);
    the first layer's weight blends against FK."""
    c.setdefault(f"iklayers.arm{side}", []).append((Vector(target), space, float(w), None if pole is None else Vector(pole)))
    c[f"ik.arm{side}"] = Vector(target)
    c[f"ikspace.arm{side}"] = space
    c[f"ikw.arm{side}"] = w
    if pole is not None:
        c[f"pole.arm{side}"] = Vector(pole)


def fingers(c, side, curl):
    c[f"fingers{side}.curl"] = curl


def rel(rig, bone, p):
    """Offset of a root-space (rest) point from a bone's rest head: IK targets in that bone's space."""
    return Vector(p) - rig.head[bone]


# --- kneeling: knees on the page
def kneel_geom(rig, side, KY=0.012, kz=0.014, thigh_back=6.0, shin_slope=16.0, spread=0.003):
    """Knee joint KY above the page at z = kz, thigh leaning back by thigh_back, shin sloping up behind by shin_slope.
    Returns (hip joint, knee, ankle) in root space."""
    sx = 1 if side == "L" else -1
    b = rig.head["thigh" + side]
    th, sh = rig.length["thigh" + side], rig.length["shin" + side]
    knee = V(rig.head["shin" + side].x + sx * spread, KY, kz)
    tb, ss = math.radians(thigh_back), math.radians(shin_slope)
    hip = knee + V(0, th * math.cos(tb), -th * math.sin(tb))
    ankle = knee + V(0, sh * math.sin(ss), -sh * math.cos(ss))
    return hip, knee, ankle


def tuck_pitch(rig, side, ankle_y):
    """Foot pitch (toes tucked under) whose lowest point just touches the page for this ankle height."""
    best, bp = 1e9, 0.0
    for p in range(0, 100, 2):
        e = abs(planted_ankle_y(rig, side, p) - ankle_y)
        if e < best:
            best, bp = e, p
    return float(bp)


KNEEL = {}


def kneel_legs(rig, c, wL=1.0, wR=1.0, hips_w=None, **kw):
    """Blend both legs (w 0 = standing, 1 = kneeling, knees on the page) and the hips down."""
    prm = dict(KNEEL.get(rig.ch, {})); prm.update(kw)
    hw = 0.5 * (wL + wR) if hips_w is None else hips_w
    hipy = []
    for side, w in (("L", wL), ("R", wR)):
        hip, knee, ankle = kneel_geom(rig, side, **prm)
        hipy.append((hip.y - rig.head["thigh" + side].y, hip.z))
        b = rig.head["foot" + side]
        y_st = planted_ankle_y(rig, side, 0)
        pk = tuck_pitch(rig, side, ankle.y)
        tgt = V(lerp(b.x, ankle.x, w), lerp(y_st, ankle.y, w), lerp(b.z, ankle.z, w))
        pitch = pk * w
        tgt.y = max(tgt.y, planted_ankle_y(rig, side, pitch))
        c[f"ik.leg{side}"] = tgt
        c[f"foot{side}.pitch"] = pitch
        sx = 1 if side == "L" else -1
        c[f"pole.leg{side}"] = V(0.08 * sx, 0, 1)
    dy = sum(h[0] for h in hipy) / 2
    dz = sum(h[1] for h in hipy) / 2
    c["hips.ty"] = c.get("hips.ty", 0.0) + dy * hw
    c["hips.tz"] = c.get("hips.tz", 0.0) + dz * hw




# =============================================================================================== shared acting helpers
def chest_hand(c, side, off, w=1.0, pole=None):
    """Hand to a point in chest space (offset from the chest bone's rest head)."""
    sx = 1 if side == "L" else -1
    arm_ik(c, side, off, pole or V(0.8 * sx, -0.6, -0.2), "chest", w)


def shiver(f, N, amp=1.0, loop=True):
    """Fast irregular trembling (sobs): returns a -1..1-ish value, seamless for loops."""
    if loop:
        return amp * (0.6 * wave(f, N, int(N / 3.1), 0.0) + 0.4 * wave(f, N, int(N / 2.3), 0.37))
    return amp * (0.6 * math.sin(f * 2.03) + 0.4 * math.sin(f * 2.71 + 0.37))


HIP_AT = {"son": V(0.058, 0.186, 0.004), "father": V(0.066, 0.198, 0.012), "brother": V(0.070, 0.204, 0.004)}


def hand_on_hip(c, rig, side, w=1.0):
    """Fist on the hip, elbow out."""
    sx = 1 if side == "L" else -1
    h = HIP_AT[rig.ch]
    arm_ik(c, side, V(sx * h.x, h.y, h.z), V(sx * 1.0, 0.25, -0.55), "root", w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 0.0), 30, w)
    c[f"hand{side}.twist"] = lerp(c.get(f"hand{side}.twist", 0.0), sx * 20, w)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 20), 68, w))


def palm_up(c, side, amt, curl=12):
    """Forearm supinated, palm up (L: + twist, R: - twist)."""
    sx = 1 if side == "L" else -1
    c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", 0.0), sx * 80, amt)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 0.0), -14, amt)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 20), curl, amt))


def sway_side(c, s, amp=1.0, lag=0):
    """Lateral weight sway: s in -1..1 (+ = toward the character's left)."""
    c["hips.tx"] = c.get("hips.tx", 0.0) + 0.004 * amp * s
    c["hips.rz"] = c.get("hips.rz", 0.0) - 2.6 * amp * s


def lean_hug(c, amt):
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.008 * amt
    c["spine.rx"] = c.get("spine.rx", 0.0) + 5 * amt
    c["chest.rx"] = c.get("chest.rx", 0.0) + 5 * amt


# =============================================================================================== SON
# Rest: A-pose, slim young man. Props: purse (left hand; spring-hung), robe + robeL/R panels (hidden until S10; rigid on
# the chest: keep the upper arms below ~60 deg from hanging while it shows), ring (right hand).
S_WALK = (0.064, 0.60)        # stride, duty  (N 32 -> 0.100 u/s)
S_STRUT = (0.074, 0.58)       # N 30 -> 0.128 u/s
S_SAD = (0.050, 0.62)         # N 40 -> 0.060 u/s
S_TIRED = (0.046, 0.64)       # N 44 -> 0.049 u/s
S_PRAC = (0.026, 0.66)        # gait cycle 60 of the 120-frame loop -> 0.0197 u/s
S_SIT_HIP = V(0.0, 0.034, -0.016)   # hip joint (root-local) sitting on the page, knees up
TOSS_F = 18                   # toss_coins: coins leave the right hand (0.6 s, CONTRACT)
DROP_F = 78                   # empty_pockets: purse dropped / hidden (2.6 s, CONTRACT)
ROBE_ARM_MAX = 60.0


def s_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.5 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.1 * b * amp; c["shoulderR.raise"] = 1.1 * b * amp
    c["neck.rx"] = 0.5 * b * amp
    c["upperArmL.raise"] = -24; c["upperArmR.raise"] = -24
    c["upperArmL.bend"] = 6; c["upperArmR.bend"] = 6
    c["forearmL.bend"] = 20; c["forearmR.bend"] = 20
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 4; c["handR.bend"] = 4
    fingers(c, "L", 20); fingers(c, "R", 20)
    c["head.rx"] = -1
    return c


def purse_grip(c, w=1.0):
    """Son's left fingers curled round the purse neck."""
    fingers(c, "L", lerp(c.get("fingersL.curl", 20), 62, w))


def robe_swing(c, amt_l, amt_r):
    c["robeL.rx"] = c.get("robeL.rx", 0.0) + amt_l
    c["robeR.rx"] = c.get("robeR.rx", 0.0) + amt_r


def s_sit(rig, c, w=1.0, feet_z=0.092, spread=0.012, hip=S_SIT_HIP):
    """Blend from standing (0) to sitting on the page with the knees up (1)."""
    hy = hip.y - rig.head["thighL"].y
    c["hips.ty"] = c.get("hips.ty", 0.0) + hy * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + hip.z * w
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * spread * w, planted_ankle_y(rig, side, 0), lerp(b.z, feet_z, w))
        c[f"foot{side}.pitch"] = 0
        c[f"pole.leg{side}"] = V(sx * 0.25, 0.6, 1)


@clip("son", "idle", 150, True,
      notes="cheeky lad at rest: thumbs hooked in his sash, weight dropping onto one hip then the other, a little "
            "bounce up on his toes, glances round with a tilt of the head, quick blinks; arms stay low (fine with the "
            "robe on)")
def son_idle(rig, f, N):
    c = s_base(rig, f, N, cycles=3, amp=1.0)
    sh = [(0, -0.6), (30, -0.6), (44, 0.8), (90, 0.8), (104, -0.6), (150, -0.6)]
    s = K(sh, f, N, True); sl = KL(sh, f, N, True, lag=7)
    sway_side(c, s, 1.1); c["spine.rz"] = 1.6 * sl; c["chest.rz"] = 1.0 * sl; c["head.rz"] = -2.5 * sl
    look = [(0, 0), (12, 0), (20, -1), (36, -1), (48, 0.7), (66, 0.7), (76, 0), (150, 0)]
    c["neck.ry"] = 8 * K(look, f, N, True); c["head.ry"] = 12 * KL(look, f, N, True, lag=3)
    c["head.rz"] += 4 * K([(0, 0), (20, 1), (36, 1), (48, -0.6), (66, -0.6), (78, 0), (150, 0)], f, N, True)
    toes = bump(f, 112, 134)
    c["hips.ty"] = 0.005 * toes - 0.0015
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.034, 0.192 + 0.001 * wave(f, N, 3), 0.034), V(sx * 1.0, 0.0, -0.4))
        c[f"hand{side}.bend"] = 16; c[f"hand{side}.twist"] = -sx * 10
    fingers(c, "L", 50); fingers(c, "R", 50)
    blink(c, f, N, [16, 70, 75, 126])
    stand_feet(rig, c, spread=0.004, pitchL=-12 * toes, pitchR=-12 * toes,
               fwdR=0.006 * K([(0, 1), (44, 0), (104, 1), (150, 1)], f, N, True))
    return c


@clip("son", "walk", 32, True, markers={"contactL": 0, "contactR": 16}, speed=S_WALK,
      notes="young and easy: 112 steps/min, springy bounce, free arm swings with loose hands, hips and chest "
            "counter-turn, head steady; arms stay low (the robe shows in S11 / S14), robe panels swing with the legs")
def son_walk(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=S_WALK[0], lift=0.014, duty=S_WALK[1], heel=12, toeoff=26)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0055 - 0.0030 * math.cos(2 * ph - 0.6)
    c["hips.ry"] = -5 * math.cos(ph); c["chest.ry"] = 8 * math.cos(ph - 0.2); c["head.ry"] = -3 * math.cos(ph - 0.4)
    c["hips.rz"] = 2.4 * math.cos(ph - 1.6); c["chest.rz"] = -1.5 * math.cos(ph - 2.0)
    c["spine.rx"] = 1.5; c["head.rx"] = -2 + 1.4 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 6 - 22 * math.cos(ph - 0.25); c["upperArmR.bend"] = 6 + 22 * math.cos(ph - 0.25)
    c["forearmL.bend"] = 26 - 10 * math.cos(ph - 0.9); c["forearmR.bend"] = 26 + 10 * math.cos(ph - 0.9)
    c["handL.bend"] = 4 - 10 * math.cos(ph - 1.5); c["handR.bend"] = 4 + 10 * math.cos(ph - 1.5)
    robe_swing(c, -7 * math.cos(ph - 0.3), 7 * math.cos(ph - 0.3))
    blink(c, f, N, [20])
    return c


@clip("son", "talk", 96, True,
      notes="chatty and cheeky: right palm-up offers on the stressed syllables, left thumb jabs at his own chest, "
            "head bobs and tilts, a shoulder shrug; jaw in an irregular syllable rhythm (lip sync overrides it)")
def son_talk(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 91, amp=(5, 13), dur=(2.8, 5.5))
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=8)
    btl = beat_curve(beats, f - 3, N, width=9)
    c["head.rx"] = -2 + 4 * bt; c["head.ry"] = 7 * wave(f, N, 1, 0.1); c["head.rz"] = 5 * wave(f, N, 1, 0.35)
    pa = K([(0, 0.2), (10, 0.9), (40, 1.0), (52, 0.2), (88, 0.1), (96, 0.2)], f, N, True)
    me = K([(0, 0.0), (46, 0.0), (56, 1.0), (78, 0.9), (88, 0.0), (96, 0.0)], f, N, True)
    lift = pa * (0.75 + 0.25 * btl)
    c["upperArmR.bend"] = 6 + 40 * lift; c["forearmR.bend"] = 20 + 56 * lift; c["forearmR.twist"] = 10 - 85 * lift
    c["handR.bend"] = 4 - 22 * btl * pa; fingers(c, "R", 26 - 22 * btl * pa)
    chest_hand(c, "L", V(0.014, -0.006 + 0.004 * btl, 0.040), me)
    c["handL.bend"] = 10 * me; fingers(c, "L", 20 + 40 * me)
    shrug = bump(f, 60, 76)
    c["shoulderL.raise"] += 5 * shrug; c["shoulderR.raise"] += 5 * shrug
    c["chest.ry"] = 5 * lift - 4 * me
    sway_side(c, wave(f, N, 1, 0.2), 0.5)
    blink(c, f, N, [14, 50, 82])
    stand_feet(rig, c, spread=0.004)
    return c


@clip("son", "laze", 150, True,
      notes="S01 'just liked to play': leaning way back on nothing, hips pushed forward, both hands behind his "
            "head with the elbows out, right foot crossed in front tapping the toe; a big lazy yawn (head back, "
            "mouth wide, eyes shut, arms stretch) once per loop, then a smug look at the viewer; slow blinks")
def son_laze(rig, f, N):
    c = s_base(rig, f, N, cycles=3, amp=1.2)
    yawn = K([(0, 0), (70, 0), (80, 0.5), (92, 1.0), (108, 1.0), (118, 0.2), (126, 0), (150, 0)], f, N, True)
    sway = wave(f, N, 2, 0.1)
    c["hips.tz"] = 0.014; c["hips.rx"] = -6; c["spine.rx"] = -6 - 2 * yawn; c["chest.rx"] += -6 - 3 * yawn
    c["neck.rx"] = 2; c["head.rx"] = 6 - 16 * yawn
    c["hips.rz"] = 1.5 * sway; c["chest.rz"] = -1.2 * sway
    c["head.rz"] = -6 + 3 * sway; c["head.ry"] = 8 * K([(0, 0), (40, 0), (50, 1), (66, 1), (74, 0), (150, 0)], f, N, True)
    c["jaw.rx"] = 18 * yawn
    # hands behind the head (head space), elbows out; they push up on the yawn's stretch
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.030, 0.026 + 0.010 * yawn, -0.026), V(sx * 1.0, 0.6, -0.2), "head")
        c[f"hand{side}.bend"] = 30; c[f"hand{side}.twist"] = -sx * 30
        fingers(c, side, 30 + 20 * yawn)
    c["shoulderL.raise"] += 5 * yawn; c["shoulderR.raise"] += 5 * yawn
    # right foot crossed over in front of the left, toe tapping (heel down)
    tap = sum(bump(f, a, a + 8) for a in (6, 18, 30, 42, 128, 138))
    blink(c, f, N, [24, 56, 140], base=1.8, slow=1.5)
    c["eyelids.sy"] = max(c["eyelids.sy"], 1.0 + 11.7 * smooth((yawn - 0.4) / 0.4))
    stand_feet(rig, c, spread=0.0, fwdR=0.022, xR=0.024, pitchR=-16 * tap, fwdL=-0.010)
    c["pole.legR"] = V(0.4, 0, 1)
    return c


@clip("son", "ask_money", 96, False, markers={"palm": 40}, props=["purse"], prop_win={"purse": (96, 96)},
      notes="'Dad, give me my share - now!': a cocky stroll of half a step toward his father, right fist on his hip, "
            "the left hand comes out palm up (the purse lands in it at 22.18 s, timeline prop) with a little "
            "'come on' finger wiggle, chin up, head tilted, cheeky grin, weight on one leg; holds the palm out")
def son_ask_money(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.4)
    step = ease_io((f - 4) / 22)
    out = ease_io((f - 26) / 16)
    wig = sum(bump(f, a, a + 7) for a in (48, 56, 64)) * 1.0
    settle = bump(f, 40, 60)
    c["hips.tz"] = 0.010 * step; c["chest.rx"] += -3 * out + 2 * settle; c["head.rx"] = -1 - 6 * out
    c["head.rz"] = -9 * out; c["head.ry"] = 4 * out
    sway_side(c, -0.8 * out, 1.2); c["spine.rz"] = -2 * out; c["chest.rz"] = -2 * out
    hand_on_hip(c, rig, "R", ease_io((f - 6) / 18))
    arm_ik(c, "L", V(0.060, 0.214 + 0.004 * settle, 0.084), V(1.0, -0.5, -0.3), "root", out)
    palm_up(c, "L", out, curl=10 + 26 * wig)
    c["handL.bend"] += -10 * wig
    c["chest.ry"] = 8 * out
    stand_feet(rig, c, spread=0.004, fwdL=0.024 * step, fwdR=0.004 * step, pitchR=6 * out)
    blink(c, f, N, [30, 74], loop=False)
    return c


@clip("son", "wave_bye", 72, False, markers={"wave1": 22, "wave2": 34, "wave3": 46}, props=["purse"],
      notes="'Bye, Dad!': half turns away toward the road as if already leaving, and flings a big wave back over "
            "his right shoulder (three wrist-led waves, arm high), purse swinging in the left hand, grinning; turns "
            "back to face front and drops the arm, ready to strut")
def son_wave_bye(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.3)
    turn = ease_io((f - 2) / 14) * (1 - ease_io((f - 54) / 14))
    up = ease_io((f - 10) / 10) * (1 - ease_io((f - 52) / 14))
    wv = math.sin(2 * math.pi * (f - 18) / 12) * up if f >= 18 else 0.0
    c["hips.ry"] = -18 * turn; c["chest.ry"] = -12 * turn; c["neck.ry"] = 12 * turn; c["head.ry"] = 16 * turn
    c["head.rz"] = 6 * up; c["chest.rz"] = 4 * up
    arm_ik(c, "R", V(-0.090 + 0.010 * wv, 0.335, 0.010), V(-1.0, -0.5, -0.4), "root", up)
    c["handR.twist"] = -60 * up; c["handR.bend"] = 26 * wv; fingers(c, "R", 20 - 18 * up)
    purse_grip(c)
    c["upperArmL.bend"] = 6 - 12 * turn
    c["hips.ty"] = 0.003 * bump(f, 16, 30) - 0.002 * bump(f, 50, 66)
    stand_feet(rig, c, spread=0.004, fwdR=-0.012 * turn, pitchR=14 * turn)
    c["jaw.rx"] = 6 * up
    blink(c, f, N, [60], loop=False)
    return c


@clip("son", "strut", 30, True, markers={"contactL": 0, "contactR": 15}, speed=S_STRUT, props=["purse"],
      notes="swagger: chest out, chin up, big rolling shoulders and hips, a springy bounce on every step, the right "
            "arm swinging wide with a floppy wrist, the purse swinging high in the left hand (spring-hung), head "
            "bobbing to an inner tune; 120 steps/min")
def son_strut(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=S_STRUT[0], lift=0.018, duty=S_STRUT[1], heel=6, toeoff=28, lift_shape=0.8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0060 - 0.0042 * math.cos(2 * ph - 0.5)
    c["hips.ry"] = -9 * math.cos(ph); c["chest.ry"] = 15 * math.cos(ph - 0.25); c["head.ry"] = -5 * math.cos(ph - 0.5)
    c["hips.rz"] = 4.5 * math.cos(ph - 1.6); c["chest.rz"] = -3.5 * math.cos(ph - 2.0); c["head.rz"] = 3 * math.cos(ph - 2.4)
    c["spine.rx"] = -2; c["chest.rx"] += -4; c["head.rx"] = -5 + 2.5 * math.cos(2 * ph - 1.1)
    c["shoulderL.raise"] += 4 * math.cos(ph - 0.3); c["shoulderR.raise"] -= 4 * math.cos(ph - 0.3)
    c["upperArmL.raise"] = -18; c["upperArmR.raise"] = -14
    c["upperArmL.bend"] = 6 - 30 * math.cos(ph - 0.3); c["upperArmR.bend"] = 6 + 34 * math.cos(ph - 0.3)
    c["forearmL.bend"] = 30 - 14 * math.cos(ph - 1.0); c["forearmR.bend"] = 22 + 18 * math.cos(ph - 1.0)
    c["handR.bend"] = 6 + 22 * math.cos(ph - 1.8); c["handL.bend"] = 6 - 10 * math.cos(ph - 1.6)
    purse_grip(c)
    robe_swing(c, -9 * math.cos(ph - 0.3), 9 * math.cos(ph - 0.3))
    blink(c, f, N, [22], base=1.3)
    return c


@clip("son", "toss_coins", 66, False, markers={"toss": TOSS_F}, props=["purse"],
      notes="'It's on me!': holds the purse up in his left hand, the right hand dips in for a fistful, winds down and "
            "flings the coins high (open hand up and out at 0.6 s = marker toss: the coins_spray FX starts there), "
            "watches them fly with a laugh, then ends showing off: purse held up, right fist on his hip, chest out "
            "(a steady pose to hold through the party lines)")
def son_toss_coins(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.3)
    up = ease_io(f / 8)
    dip = bump(f, 2, 12)
    wind = ease_io((f - 8) / 5) * (1 - ease_io((f - 14) / 4))
    fling = ease_io((f - 13) / 5) * (1 - ease_io((f - 30) / 14))
    hip = ease_io((f - 40) / 12)
    # purse up in front of the chest (left), then lifted proudly
    purse = V(0.030, 0.226, 0.060).lerp(V(0.094, 0.236, 0.046), hip)
    arm_ik(c, "L", purse, V(1.0, -0.6, -0.3), "root", up)
    c["handL.bend"] = -10; purse_grip(c)
    # right hand: dips into the bag, winds down and back, flings high
    rp = V(0.010, 0.232, 0.064).lerp(V(-0.040, 0.170, 0.050), wind)
    rp = rp.lerp(V(-0.070, 0.350, 0.050), fling)
    arm_ik(c, "R", rp, V(-1.0, -0.4, -0.3), "root", up)
    hand_on_hip(c, rig, "R", hip)
    c["handR.bend"] += -26 * fling; fingers(c, "R", lerp(c["fingersR.curl"], 70, dip + wind) - 60 * fling)
    c["chest.rx"] += 3 * wind - 6 * fling - 3 * hip; c["head.rx"] = -1 + 4 * dip - 18 * fling - 4 * hip
    c["head.ry"] = -10 * fling; c["chest.ry"] = -8 * fling + 6 * hip
    c["hips.ty"] = -0.006 * wind + 0.004 * fling
    c["jaw.rx"] = 4 * dip + 10 * fling + 6 * pulses(f, N, [(24, 1), (30, 0.8), (36, 0.6)], decay=2.5, loop=False)
    stand_feet(rig, c, spread=0.006, pitchL=-10 * fling, pitchR=-10 * fling, fwdL=0.010 * hip)
    blink(c, f, N, [50], loop=False)
    return c


@clip("son", "party_dance", 54, True, markers={"beat1": 0, "beat2": 13.5, "beat3": 27, "beat4": 40.5}, props=["purse"],
      notes="silly party dance at the 'party' tempo (~134 bpm, a beat every 13.5 frames): knees bounce on every "
            "beat, hips wiggle, arms wave overhead in turn (right hand open, left hand waving the purse), head "
            "bobbing, a goofy step to each side, laughing")
def son_party_dance(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=0.4)
    bph = (f % 13.5) / 13.5
    bounce = math.cos(2 * math.pi * bph)
    side = wave(f, N, 1, 0.0)
    c["hips.ty"] = -0.006 + 0.004 * bounce
    c["hips.tx"] = 0.010 * side; c["hips.rz"] = 6 * wave(f, N, 2, 0.1); c["chest.rz"] = -5 * wave(f, N, 2, 0.15)
    c["hips.ry"] = 10 * wave(f, N, 1, 0.25); c["chest.ry"] = -6 * wave(f, N, 1, 0.3)
    c["head.rz"] = 8 * wave(f, N, 2, 0.35); c["head.rx"] = -4 + 3 * bounce
    a = 0.5 + 0.5 * wave(f, N, 1, 0.0)             # which arm is up
    for s_, sx, w in (("L", 1, 1 - a), ("R", -1, a)):
        hi = V(sx * 0.070 + 0.012 * wave(f, N, 4, 0.1), 0.348, 0.020)
        lo = V(sx * 0.064, 0.236, 0.050)
        arm_ik(c, s_, lo.lerp(hi, smooth(w)), V(sx * 1.0, -0.4, -0.4))
        c[f"hand{s_}.bend"] = 20 * wave(f, N, 4, 0.2 if s_ == "L" else 0.7)
    fingers(c, "R", 6); purse_grip(c)
    c["handR.twist"] = -40
    for side_, sx in (("L", 1), ("R", -1)):
        lift = bump((f + (0 if side_ == "L" else 27)) % N, 0, 13.5)
        b = rig.head["foot" + side_]
        c[f"ik.leg{side_}"] = V(b.x + sx * (0.006 + 0.010 * lift) + 0.010 * side, planted_ankle_y(rig, side_, 0) + 0.016 * lift, b.z + 0.008 * lift)
        c[f"foot{side_}.pitch"] = 14 * lift
    c["jaw.rx"] = 6 + 3 * bounce
    blink(c, f, N, [30])
    return c


@clip("son", "empty_pockets", 150, False,
      markers={"shake": 16, "upside": 48, "drop": DROP_F, "pockets": 96, "shrug": 124}, props=["purse"],
      prop_win={"purse": (0, DROP_F - 1)},
      notes="'Huh? Where's my money?': lifts the purse to his eye and peers in, shakes it by his ear (nothing), "
            "turns it upside down over his cupped right palm and shakes hard (nothing falls), lets it drop at 2.6 s "
            "(marker drop = the timeline's prop hide), then pulls his empty tunic 'pockets' out at both hips, looks "
            "down at his empty hands and freezes in a slumped, palms-up shrug (holds)")
def son_empty_pockets(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.3)
    peer = ease_io((f - 2) / 10) * (1 - ease_io((f - 30) / 10))
    shake_n = pulses(f, N, [(16, 1), (20, 0.9), (24, 0.8), (28, 0.6)], decay=1.6, loop=False)
    inv = ease_io((f - 36) / 10) * (1 - ease_io((f - DROP_F + 2) / 4))
    shake2 = math.sin(f * 2.4) * bump(f, 48, DROP_F - 4)
    drop = ease_io((f - DROP_F + 2) / 4)
    pock_in = ease_io((f - 84) / 14)
    pock = pock_in * (1 - ease_io((f - 112) / 12))
    shrug = ease_io((f - 112) / 16)
    # left hand with the purse: by the eye, by the ear (shake), held up fingers-up (upside down), then dropped
    p_eye = V(0.034, 0.300, 0.060)
    p_ear = V(0.060, 0.310, 0.020)
    p_inv = V(0.020, 0.270, 0.066)
    pl = V(0.040, 0.220, 0.050).lerp(p_eye, peer).lerp(p_ear, smooth((f - 12) / 6) * (1 - inv)).lerp(p_inv, inv)
    pl = pl + V(0.0, 0.006 * shake2, 0.0)
    w_l = ease_io(f / 6) * (1 - drop) + 0.0
    arm_ik(c, "L", pl, V(1.0, -0.5, -0.3), "root", w_l)
    c["handL.bend"] = -20 * peer - 60 * inv + 30 * shake_n * 0.3
    c["handL.twist"] = -30 * inv
    purse_grip(c, 1 - drop)
    c["hang.purse"] = 1.0 - 0.9 * inv                 # upside down: the bag follows the hand, not gravity
    # right palm cupped under the upturned purse
    arm_ik(c, "R", V(0.006, 0.226, 0.070), V(-1.0, -0.5, -0.3), "root", inv)
    palm_up(c, "R", inv, curl=30)
    # pockets: both hands pull at the hips, then the shrug
    for side, sx in (("L", 1), ("R", -1)):
        pk = V(sx * 0.064, 0.176, 0.016)
        out_ = V(sx * 0.088, 0.190, 0.044)
        if pock_in > 0:
            arm_ik(c, side, pk.lerp(out_, smooth((f - 96) / 10)), V(sx * 1.0, 0.0, -0.5), "root", pock_in)
            fingers(c, side, lerp(c[f"fingers{side}.curl"], 70, pock))
        if shrug > 0:
            arm_ik(c, side, V(sx * 0.074, 0.188, 0.058), V(sx * 1.0, -0.3, -0.4), "root", shrug)
            palm_up(c, side, shrug, curl=14)
    c["head.rx"] = -1 + 6 * peer - 4 * shrug + 14 * pock + 12 * shrug
    c["head.rz"] = -10 * peer + 6 * shrug; c["head.ry"] = -14 * peer
    c["neck.rx"] = 6 * pock + 4 * shrug
    c["chest.rx"] += 2 * peer + 4 * pock + 3 * shrug
    c["shoulderL.raise"] += 7 * bump(f, 112, 140) + 2 * shrug; c["shoulderR.raise"] += 7 * bump(f, 112, 140) + 2 * shrug
    c["hips.ty"] = -0.004 * shrug
    c["jaw.rx"] = 6 * shrug + 4 * peer
    stand_feet(rig, c, spread=0.005, fwdL=0.006 * shrug)
    blink(c, f, N, [34, 90, 98], loop=False)
    c["eyelids.sy"] = min(c["eyelids.sy"], 1.0) if 112 < f < 128 else c["eyelids.sy"]
    return c


@clip("son", "sad_idle", 150, True,
      notes="broke and alone: shoulders slumped, head hanging, arms dangling; slow heavy breaths with one long sigh "
            "(shoulders rise and drop), scuffs a toe in the dirt, one hopeless look up and round; slow heavy blinks")
def son_sad_idle(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=1.4)
    sigh = K([(0, 0), (40, 0), (54, 1), (62, 1), (80, -0.4), (96, 0), (150, 0)], f, N, True)
    look = K([(0, 0), (100, 0), (110, 1), (126, 1), (138, 0), (150, 0)], f, N, True)
    scuff = bump(f, 10, 34)
    c["spine.rx"] = 8; c["chest.rx"] += 11 - 4 * sigh; c["neck.rx"] = 12 - 8 * look; c["head.rx"] = 16 - 18 * look - 4 * sigh
    c["hips.tz"] = -0.006; c["hips.ty"] = -0.004
    c["shoulderL.raise"] += -8 + 8 * sigh; c["shoulderR.raise"] += -8 + 8 * sigh
    c["upperArmL.raise"] = -28; c["upperArmR.raise"] = -28; c["forearmL.bend"] = 10; c["forearmR.bend"] = 10
    fingers(c, "L", 30); fingers(c, "R", 30)
    c["head.ry"] = 14 * look * wave(f, N, 2, 0.1) + 4 * scuff
    sway_side(c, wave(f, N, 1, 0.3), 0.4)
    blink(c, f, N, [20, 88, 130], base=2.2, slow=2.0)
    stand_feet(rig, c, spread=0.003, fwdR=0.010 * scuff, liftR=0.004 * bump(f, 14, 22) + 0.004 * bump(f, 24, 32),
               pitchR=10 * scuff)
    return c


@clip("son", "sad_walk", 40, True, markers={"contactL": 0, "contactR": 20}, speed=S_SAD,
      notes="trudging to the pigs: slow (90 steps/min), head down, shoulders rounded, arms hanging and barely "
            "swinging, feet dragging (low lift), a heavy dip on every step")
def son_sad_walk(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.6)
    g = gait(rig, f, N, L=S_SAD[0], lift=0.011, duty=S_SAD[1], heel=6, toeoff=16)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0065 - 0.0030 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = -3 * math.cos(ph); c["chest.ry"] = 4 * math.cos(ph - 0.3)
    c["hips.rz"] = 2.0 * math.cos(ph - 1.6); c["chest.rz"] = -1.0 * math.cos(ph - 2.0)
    c["spine.rx"] = 4; c["chest.rx"] += 7; c["neck.rx"] = 8; c["head.rx"] = 12 + 2.5 * math.cos(2 * ph - 1.4)
    c["shoulderL.raise"] += -4; c["shoulderR.raise"] += -4
    c["upperArmL.raise"] = -28; c["upperArmR.raise"] = -28
    c["upperArmL.bend"] = 2 - 8 * math.cos(ph - 0.4); c["upperArmR.bend"] = 2 + 8 * math.cos(ph - 0.4)
    c["forearmL.bend"] = 12; c["forearmR.bend"] = 12
    fingers(c, "L", 30); fingers(c, "R", 30)
    blink(c, f, N, [26], base=2.0, slow=1.6)
    return c


@clip("son", "feed_pigs", 90, True, markers={"scatter1": 30, "scatter2": 75},
      notes="pig-boy: a mimed sack at his left hip (left forearm round it, fingers cupped), the right hand dips in "
            "and flings pods out to his left-front where the pigs are, twice per loop; bent a little, glum, head down "
            "toward the pigs, one weary wipe of the brow")
def son_feed_pigs(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=0.9)
    arm_ik(c, "L", V(0.052, 0.196, 0.040), V(1.0, -0.2, -0.6))
    c["handL.bend"] = -10; c["handL.twist"] = 40; fingers(c, "L", 55)
    sc = 0.0; dip = 0.0
    for t0 in (0, 45):
        dip = max(dip, bump(f, t0 + 6, t0 + 22))
        sc = max(sc, bump(f, t0 + 22, t0 + 40))
    sack = V(0.040, 0.214, 0.052)
    fling = V(0.060, 0.212, 0.120)
    rest = V(-0.050, 0.180, 0.040)
    rp = rest.lerp(sack, dip).lerp(fling, sc)
    arm_ik(c, "R", rp, V(-1.0, -0.5, -0.3), "root", max(dip, sc, 0.4))
    c["handR.bend"] = 10 * dip - 20 * sc; fingers(c, "R", 20 + 50 * dip - 40 * sc)
    c["chest.ry"] = 10 * dip + 18 * sc; c["head.ry"] = 18 + 6 * sc
    c["spine.rx"] = 3; c["chest.rx"] += 5 + 2 * sc; c["head.rx"] = 10
    c["shoulderL.raise"] += -3; c["shoulderR.raise"] += -3
    c["hips.ty"] = -0.002 - 0.002 * sc
    blink(c, f, N, [14, 60], base=1.8, slow=1.6)
    stand_feet(rig, c, spread=0.004, fwdL=0.006)
    return c


@clip("son", "hungry_look", 120, True, markers={"lick": 40, "rumble": 84},
      notes="'Even the pigs' pods look yummy...': leans toward the trough staring, hand rubbing his tummy in "
            "circles, licks his lips (jaw chews, head bobs), a greedy swallow, wipes his mouth with the back of the "
            "right hand; his tummy rumbles (a hunching jolt), sad droopy blinks; leans in and pulls back")
def son_hungry_look(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=1.0)
    lean = K([(0, 0.5), (20, 1.0), (60, 1.0), (76, 0.3), (100, 0.4), (120, 0.5)], f, N, True)
    lick = bump(f, 36, 58)
    wipe = bump(f, 60, 80)
    rumble = pulses(f, N, [(84, 1.0), (89, 0.6)], decay=2.0)
    c["hips.tz"] = -0.004 + 0.012 * lean - 0.006 * rumble; c["hips.ty"] = -0.006 * lean
    c["spine.rx"] = 10 + 10 * lean; c["chest.rx"] += 10 + 10 * lean + 10 * rumble
    c["neck.rx"] = -10 * lean; c["head.rx"] = 4 - 4 * lean + 4 * math.sin(f * 0.9) * lick + 8 * rumble
    c["head.rz"] = 8 * K([(0, 0.4), (40, 1), (70, -0.3), (120, 0.4)], f, N, True)
    c["jaw.rx"] = 5 * lick * (0.5 + 0.5 * math.sin(f * 1.2)) + 3 * bump(f, 64, 70)
    # tummy rub (left hand, circles)
    ang = 2 * math.pi * 3 * f / N
    arm_ik(c, "L", V(0.022 + 0.008 * math.cos(ang), 0.200 + 0.008 * math.sin(ang), 0.044), V(1.0, -0.3, -0.4))
    c["handL.bend"] = 24; c["handL.twist"] = 30; fingers(c, "L", 20)
    # right hand: hangs, then wipes the mouth with its back
    chest_hand(c, "R", V(-0.004, 0.058, 0.050), wipe, V(-1.0, -0.6, -0.1))
    c["shoulderL.raise"] += -3; c["shoulderR.raise"] += -3
    c["handR.bend"] = -16 * wipe; c["handR.twist"] = 40 * wipe
    c["head.ry"] = -8 * wipe
    c["shoulderL.raise"] += 4 * rumble; c["shoulderR.raise"] += 4 * rumble
    blink(c, f, N, [24, 100], base=1.9, slow=1.6)
    c["eyelids.sy"] = max(c["eyelids.sy"], 1.0 + 5.0 * lick)
    stand_feet(rig, c, spread=0.006, fwdL=0.012)
    return c


@clip("son", "sit_sad", 150, True,
      notes="homesick: sitting on the ground in the mud (hip joint 0.034 up), knees up, elbows on his knees and his "
            "face in his hands; slow sobbing breaths with little shudders, lifts his face once to stare at nothing "
            "and sinks back, a small head shake")
def son_sit_sad(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=1.3)
    s_sit(rig, c)
    lift = K([(0, 0), (70, 0), (84, 1), (108, 1), (124, 0), (150, 0)], f, N, True)
    sob = pulses(f, N, [(20, 0.8), (25, 0.6), (30, 0.4), (130, 0.6), (135, 0.4)], decay=2.0)
    c["hips.rx"] = 18; c["spine.rx"] = 14 - 4 * lift; c["chest.rx"] += 14 - 6 * lift + 2.5 * sob
    c["neck.rx"] = 12 - 10 * lift; c["head.rx"] = 18 - 22 * lift
    c["shoulderL.raise"] += 2 * sob; c["shoulderR.raise"] += 2 * sob
    sh = [(0, 0), (40, 0), (48, 5), (56, -5), (64, 3), (70, 0), (150, 0)]
    c["head.ry"] = K(sh, f, N, True) * (1 - lift)
    for side, sx in (("L", 1), ("R", -1)):
        face = V(sx * 0.016, 0.060 - 0.024 * lift, 0.062 - 0.006 * lift)
        chest_hand(c, side, face, 1.0, V(sx * 0.6, -1.0, 0.3))
        c[f"hand{side}.bend"] = -20 + 30 * lift; c[f"hand{side}.twist"] = sx * 10
        fingers(c, side, 22 + 20 * lift)
    blink(c, f, N, [16, 92, 100], base=2.4, slow=2.0)
    return c


@clip("son", "idea_stand", 66, False, markers={"idea": 14, "up": 34},
      notes="'That's it! I'll go home!': from sitting (frame 0 = the sit_sad pose) his head pops up, eyes wide, the "
            "right hand shoots up with a straight 'finger' by his face, then he springs to his feet with a little "
            "hop and ends standing tall, both fists clenched at his chest, chin up, determined (holds)")
def son_idea_stand(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.2)
    s0 = son_sit_sad(rig, 0, 150)
    look = ease_io((f - 2) / 8)
    finger = ease_io((f - 10) / 6) * (1 - ease_io((f - 26) / 8))
    crouch = ease_io((f - 22) / 12)                 # body forward over the feet
    hop = ease_io((f - 34) / 10)                    # springs up, the feet come under him in the air
    air = bump(f, 34, 46)
    fists = ease_io((f - 38) / 12)
    # hips: seated -> crouched over the feet -> standing (+ a little hop)
    hip_crouch = V(0.0, 0.106, 0.046)
    hip_stand = V(0.0, rig.head["thighL"].y, 0.0)
    hip = S_SIT_HIP.lerp(hip_crouch, crouch).lerp(hip_stand, hop)
    c["hips.ty"] = hip.y - rig.head["thighL"].y + 0.012 * air
    c["hips.tz"] = hip.z
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        fz = lerp(0.092, b.z, smooth((f - 35) / 8))
        c[f"ik.leg{side}"] = V(b.x + sx * lerp(0.012, 0.004, hop), planted_ankle_y(rig, side, 0) + 0.016 * air, fz)
        c[f"foot{side}.pitch"] = 8 * air
        c[f"pole.leg{side}"] = V(sx * 0.25, lerp(0.6, 0.0, hop), 1)
    for k in ("hips.rx", "spine.rx", "chest.rx", "neck.rx", "head.rx"):
        c[k] = lerp(s0.get(k, 0.0), 0.0, max(look * 0.6, hop))
    c["spine.rx"] += 14 * crouch * (1 - hop); c["chest.rx"] += 10 * crouch * (1 - hop)
    c["head.rx"] += -10 * look * (1 - fists) - 6 * fists; c["chest.rx"] += -4 * fists
    # hands (chest space): on the face -> right 'finger' up by the face / left on the knee -> both fists at the chest
    for side, sx in (("L", 1), ("R", -1)):
        face = V(sx * 0.016, 0.060, 0.062)
        mid = V(sx * 0.050, -0.040, 0.070) if side == "L" else V(-0.040, 0.080, 0.060)
        fist = V(sx * 0.026, -0.004, 0.050)
        w_mid = look if side == "L" else max(finger, look * (1 - ease_io((f - 26) / 8)))
        t = face.lerp(mid, w_mid).lerp(fist, fists)
        chest_hand(c, side, t, 1.0, V(sx * 0.8, -0.8, 0.0))
        fingers(c, side, lerp(22, 85, fists))
        c[f"hand{side}.bend"] = lerp(-20, 0, look)
    c["handR.bend"] += -20 * finger; fingers(c, "R", lerp(c["fingersR.curl"], 4, finger))
    c["jaw.rx"] = 8 * bump(f, 8, 26)
    blink(c, f, N, [52], loop=False)
    return c


@clip("son", "practise", 120, True, markers={"heart": 14, "bow": 44, "no": 76, "again": 100}, speed=S_PRAC,
      natural=S_PRAC[0] / (S_PRAC[1] * 60 / FPS),
      notes="trudging home rehearsing his speech, two slow pensive steps per 2 s (60 steps/min, short strides) while "
            "trying gestures: hand on heart, a deep humble bow, a cringing head-shake with a hand wave ('no, not like "
            "that'), then trying again with both palms open; lips moving; locomotion at a very slow walk")
def son_practise(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=0.6)
    P = 60
    g = gait(rig, f % P, P, L=S_PRAC[0], lift=0.011, duty=S_PRAC[1], heel=6, toeoff=16)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / P
    c["hips.ty"] = -0.0040 - 0.0020 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = -3 * math.cos(ph); c["hips.rz"] = 1.6 * math.cos(ph - 1.6)
    heart = K([(0, 0), (6, 0), (16, 1), (34, 1), (40, 0), (120, 0)], f, N, True)
    bow = K([(0, 0), (36, 0), (46, 1), (60, 1), (68, 0), (120, 0)], f, N, True)
    no = K([(0, 0), (66, 0), (72, 1), (88, 1), (94, 0), (120, 0)], f, N, True)
    again = K([(0, 0), (90, 0), (98, 1), (108, 1), (119, 0)], f, N, True)
    chest_hand(c, "R", V(-0.012, 0.004, 0.044), heart + 0.8 * bow)
    c["handR.bend"] = -10 * heart
    c["hips.tz"] = -0.010 * bow
    c["spine.rx"] = 4 + 16 * bow; c["chest.rx"] += 4 + 20 * bow; c["neck.rx"] = 8 * bow; c["head.rx"] = 4 + 14 * bow - 8 * again
    c["head.ry"] = 18 * math.sin(f * 0.75) * no; c["head.rz"] = 0.0
    arm_ik(c, "L", V(0.064, 0.290, 0.070), V(1.0, -0.5, -0.3), "root", no)
    c["handL.bend"] = 20 * math.sin(f * 0.75 + 0.8) * no; c["handL.twist"] = -60 * no
    c["head.rz"] = -6 * no + 5 * heart
    for side, sx in (("L", 1), ("R", -1)):
        if again > 0:
            arm_ik(c, side, V(sx * 0.074, 0.222, 0.076), V(sx * 1.0, -0.4, -0.4), "root", again)
            palm_up(c, side, again, curl=10)
    jk, _ = syllables(N, 33, amp=(3, 8), dur=(3.0, 6.0))
    c["jaw.rx"] = jaw_from(jk, f, N) * (0.6 + 0.4 * again) * (1 - 0.6 * bow)
    blink(c, f, N, [26, 80])
    return c


@clip("son", "walk_tired", 44, True, markers={"contactL": 0, "contactR": 22}, speed=S_TIRED,
      notes="the last stretch home, worn out: slow (82 steps/min) heavy steps that barely clear the ground, a "
            "slight limp (the left step lands harder), body bent forward, arms limp, head low but lifting toward home")
def son_walk_tired(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.8)
    g = gait(rig, f, N, L=S_TIRED[0], lift=0.011, duty=S_TIRED[1], heel=5, toeoff=14)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0070 - 0.0030 * math.cos(2 * ph - 0.4) - 0.0015 * math.cos(ph - 0.2)
    c["hips.ry"] = -3 * math.cos(ph); c["chest.ry"] = 3 * math.cos(ph - 0.3)
    c["hips.rz"] = 2.6 * math.cos(ph - 1.6); c["chest.rz"] = -1.8 * math.cos(ph - 2.0); c["head.rz"] = 1.5 * math.cos(ph - 2.3)
    c["spine.rx"] = 10; c["chest.rx"] += 12; c["neck.rx"] = 2; c["head.rx"] = -2 + 4 * math.cos(2 * ph - 1.4)
    c["hips.tz"] = -0.006
    c["shoulderL.raise"] += -8; c["shoulderR.raise"] += -8
    c["upperArmL.raise"] = -28; c["upperArmR.raise"] = -28
    c["upperArmL.bend"] = 12 - 8 * math.cos(ph - 0.7); c["upperArmR.bend"] = 12 + 8 * math.cos(ph - 0.7)
    c["forearmL.bend"] = 8; c["forearmR.bend"] = 8
    fingers(c, "L", 30); fingers(c, "R", 30)
    blink(c, f, N, [30], base=2.0, slow=1.8)
    return c


SON_HUG_HANDS = (V(0.034, 0.204, 0.112), V(-0.028, 0.210, 0.116))     # round the father's back (father 0.10 in front)


@clip("son", "hug", 90, True,
      notes="in his father's arms (father 0.10 in front): leans in, arms round the father's waist / back under the "
            "father's arms, cheek against the father's chest (head turned to his right), shoulders shaking with "
            "small sobs, rocking gently with the father (same 3 s rock: both sway to the same side of the stage)")
def son_hug(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=0.8)
    rock = wave(f, N, 1, 0.0)
    sob = pulses(f, N, [(10, 0.7), (16, 0.5), (55, 0.6), (61, 0.4)], decay=2.0)
    lean_hug(c, 1.0)
    c["hips.tz"] += 0.004
    sway_side(c, rock, 0.9)
    c["spine.rz"] = 1.4 * KL([(0, 0), (N, 0)], f, N, True) + 1.6 * wave(f, N, 1, -0.06)
    c["chest.rx"] += 1.5 * sob; c["shoulderL.raise"] += 3 * sob; c["shoulderR.raise"] += 3 * sob
    c["neck.rx"] = 8; c["head.rx"] = 8 + 1.0 * sob; c["head.ry"] = -34; c["head.rz"] = 10 + 2 * wave(f, N, 1, 0.1)
    sq = 0.5 + 0.5 * wave(f, N, 2, 0.2)
    for (side, sx), tgt in zip((("L", 1), ("R", -1)), SON_HUG_HANDS):
        arm_ik(c, side, tgt + V(-sx * 0.004 * sq, 0, 0.004 * sq), V(sx * 1.0, -0.2, 0.0))
        c[f"hand{side}.bend"] = 30; c[f"hand{side}.twist"] = -sx * 60; fingers(c, side, 40)
    blink(c, f, N, [], base=12.78)               # eyes shut in the hug (cry face)
    stand_feet(rig, c, spread=0.004, fwdL=0.006)
    return c


@clip("son", "sorry_head", 60, False, markers={"bow": 30},
      notes="'Dad, I was wrong...': still close to his father, he lets go and steps back into himself: hands clasped "
            "low in front, shoulders rounded, head bowed, a small sniff; holds (the father is still hugging him)")
def son_sorry_head(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.3)
    w = ease_io(f / 26)
    bow = ease_io((f - 10) / 22)
    sniff = bump(f, 40, 50)
    lean_hug(c, 1.0 - w)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.006, 0.186, 0.044), V(sx * 1.0, -0.4, -0.3), "root", w)
        c[f"hand{side}.bend"] = 18 * w; c[f"hand{side}.twist"] = -sx * 40 * w
        fingers(c, side, lerp(34, 50, w))
    c["spine.rx"] = c.get("spine.rx", 0.0) + 3 * bow; c["chest.rx"] += 5 * bow; c["neck.rx"] = 10 * bow
    c["head.rx"] = 4 * (1 - w) + 16 * bow - 3 * sniff; c["head.ry"] = -32 * (1 - w)
    c["shoulderL.raise"] += -4 * bow + 3 * sniff; c["shoulderR.raise"] += -4 * bow + 3 * sniff
    stand_feet(rig, c, spread=0.004, fwdL=0.006 * (1 - w))
    blink(c, f, N, [52], loop=False, base=1.0 + 3.0 * bow)
    return c


@clip("son", "amazed", 96, False, markers={"robe": 10, "ring": 42, "spread": 72}, props=["robe", "robeL", "robeR", "ring"],
      notes="the best robe and the ring: looks down at himself and lifts the robe's front edges a little (wondering), "
            "brings the right hand up in front of his face to stare at the ring (eyebrows up, jaw drops), then spreads "
            "both hands, palms up, toward his father, amazed and grateful (holds); upper arms stay below 60 deg "
            "from hanging (the rigid robe)")
def son_amazed(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.3)
    base = ease_io((f - 2) / 10)
    down = base * (1 - ease_io((f - 34) / 10))
    ring = ease_io((f - 34) / 12) * (1 - ease_io((f - 62) / 10))
    ring_in = ease_io((f - 34) / 12)
    spread = ease_io((f - 62) / 14)
    c["neck.rx"] = 10 * down + 4 * ring; c["head.rx"] = 10 * down + 6 * ring - 6 * spread
    c["head.ry"] = -10 * ring; c["head.rz"] = 6 * spread
    c["chest.rx"] += 3 * down - 3 * spread
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.052, 0.150, 0.042), V(sx * 1.0, 0.0, -0.4), "root", base)
        fingers(c, side, lerp(20, 55, down))
    arm_ik(c, "R", V(-0.006, 0.286, 0.084), V(-1.0, -0.6, -0.2), "root", ring_in)
    c["handR.bend"] = -30 * ring; c["handR.twist"] = 40 * ring; fingers(c, "R", lerp(c["fingersR.curl"], 30, ring))
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.074, 0.192, 0.062), V(sx * 1.0, -0.3, -0.4), "root", spread)
        palm_up(c, side, spread, curl=8)
    c["jaw.rx"] = 8 * ring + 4 * spread
    c["hips.tz"] = -0.004 * ring
    stand_feet(rig, c, spread=0.004)
    blink(c, f, N, [26], loop=False)
    c["eyelids.sy"] = min(c["eyelids.sy"], 1.0) if f > 36 else c["eyelids.sy"]
    return c


@clip("son", "dance", 66, True, markers={"beat1": 0, "beat2": 16.5, "beat3": 33, "beat4": 49.5},
      props=["robe", "robeL", "robeR", "ring"],
      notes="joy at the feast (~108 bpm, a beat every 16.5 frames): bouncing side-steps, a quarter turn to each side "
            "so the robe swirls (robe panels swing out late), hands clapping and flicking out at chest height (upper "
            "arms below 60 deg: the rigid robe), head bobbing, laughing")
def son_dance(rig, f, N):
    c = s_base(rig, f, N, cycles=2, amp=0.3)
    bph = (f % 16.5) / 16.5
    bounce = math.cos(2 * math.pi * bph)
    side = wave(f, N, 1, 0.0)
    clap = pulses(f, N, [(16.5, 1.0), (49.5, 1.0)], decay=2.0)
    c["hips.ry"] = 20 * wave(f, N, 1, 0.05); c["chest.ry"] = c.get("chest.ry", 0.0) + 8 * wave(f, N, 1, 0.0)
    c["hips.ty"] = -0.006 + 0.005 * bounce
    c["hips.tx"] = 0.010 * side; c["hips.rz"] = 4 * wave(f, N, 2, 0.1); c["chest.rz"] = -3 * wave(f, N, 2, 0.15)
    c["head.rz"] = 6 * wave(f, N, 2, 0.35); c["head.rx"] = -5 + 3 * bounce
    open_ = 1 - min(1.0, min(abs(((f - h + N / 2) % N) - N / 2) for h in (16.5, 49.5)) / 8.0)
    for s_, sx in (("L", 1), ("R", -1)):
        meet = V(sx * 0.006, 0.232, 0.052)
        out = V(sx * 0.080, 0.232 + 0.010 * wave(f, N, 2, 0.25 if s_ == "L" else 0.75), 0.030)
        arm_ik(c, s_, out.lerp(meet, open_), V(sx * 1.0, -0.6, -0.3))
        c[f"hand{s_}.twist"] = -sx * 70 * open_; c[f"hand{s_}.bend"] = -10 + 20 * (1 - open_) * wave(f, N, 4, 0.2)
        fingers(c, s_, 8)
    for side_, sx in (("L", 1), ("R", -1)):
        lift = bump((f + (0 if side_ == "L" else 33)) % N, 2, 18)
        b = rig.head["foot" + side_]
        c[f"ik.leg{side_}"] = V(b.x + sx * (0.006 + 0.008 * lift) + 0.010 * side, planted_ankle_y(rig, side_, 0) + 0.014 * lift, b.z + 0.012 * lift)
        c[f"foot{side_}.pitch"] = 12 * lift
        robe_swing(c, -14 * lift if side_ == "L" else 0.0, -14 * lift if side_ == "R" else 0.0)
    c["jaw.rx"] = 6 + 4 * clap
    blink(c, f, N, [44])
    return c


@clip("son", "wave", 48, True, props=["robe", "robeL", "robeR", "ring"],
      notes="S14 goodbye to the viewer: a big happy wave with the right hand up by his head (forearm up, elbow out "
            "forward-side so the upper arm stays under 60 deg in the rigid robe), wrist-led, three waves per loop, "
            "left hand on his chest, little bounce, head tilt, smile")
def son_wave(rig, f, N):
    c = s_base(rig, f, N, cycles=1, amp=0.5)
    arm_ik(c, "R", V(-0.074 - 0.008 * wave(f, N, 3, 0.0), 0.298, 0.052), V(-1.0, -0.8, 0.2))
    c["handR.twist"] = -70; c["handR.bend"] = 26 * wave(f, N, 3, 0.15); fingers(c, "R", 4)
    chest_hand(c, "L", V(0.012, -0.010, 0.040))
    c["head.rz"] = -6; c["hips.ty"] = -0.001 + 0.002 * wave(f, N, 3, 0.2)
    c["chest.rz"] = 2; c["jaw.rx"] = 4
    blink(c, f, N, [20])
    stand_feet(rig, c, spread=0.003)
    return c


# =============================================================================================== FATHER
# Rest: the stoop is baked in (chest +6, neck +5, head -7, arms -6): do not straighten it in idle. Long open abaya:
# cloakL / cloakR front panels (spring chains, hitched up by the left hand in `run`), headcloth back drape, beard1-2.
F_WALK = (0.060, 0.60)        # N 40 -> 0.075 u/s
F_RUN = (0.060, 0.48)         # N 24 -> 0.156 u/s
FA_GIVE = 66                  # sad_give: purse released (2.2 s, CONTRACT)
ARM_OUT = V(-0.026, 0.212, 0.068)        # arm_out wrist (root space): hand 0.10-0.12 in front at chest height
F_HUG_HANDS = (V(0.030, 0.236, 0.112), V(-0.024, 0.246, 0.116))      # round the son's upper back (son 0.10 in front)


def f_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.6 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.1 * b * amp; c["shoulderR.raise"] = 1.1 * b * amp
    c["neck.rx"] = 0.5 * b * amp; c["head.rx"] = -0.4 * b * amp
    c["upperArmL.raise"] = -22; c["upperArmR.raise"] = -22
    c["upperArmL.bend"] = 8; c["upperArmR.bend"] = 8
    c["forearmL.bend"] = 24; c["forearmR.bend"] = 24
    c["forearmL.twist"] = -12; c["forearmR.twist"] = 12
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 26); fingers(c, "R", 26)
    c["beard1.rz"] = 1.0 * wave(f, N, max(1, cycles), phase + 0.3)
    return c


def f_clasp(c, w=1.0, at=None):
    """Hands folded in front of the belly, left over right."""
    at = at or V(0.0, 0.196, 0.058)
    arm_ik(c, "L", at + V(0.012, 0.002, 0.004), V(0.8, -0.4, -0.4), "root", w)
    arm_ik(c, "R", at + V(-0.012, -0.002, 0.000), V(-0.8, -0.4, -0.4), "root", w)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 16, w)
        c[f"hand{side}.twist"] = lerp(c.get(f"hand{side}.twist", 0.0), -sx * 50, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 26), 44, w))


def f_cloak(c, f, N, amp=1.0, phase=0.0):
    c["cloakL.rx"] = c.get("cloakL.rx", 0.0) + 1.4 * amp * wave(f, N, 1, phase)
    c["cloakR.rx"] = c.get("cloakR.rx", 0.0) + 1.4 * amp * wave(f, N, 1, phase + 0.4)


@clip("father", "idle", 150, True,
      notes="a warm old man at rest: hands folded over his belly, slow deep breaths (the stoop lifts a little on the "
            "inhale), weight shifts, a slow look round and a kind nod, once strokes his beard with the right hand; "
            "slow blinks; beard, head-cloth and robe panels sway late")
def father_idle(rig, f, N):
    c = f_base(rig, f, N, cycles=3, amp=1.0)
    sh = [(0, 0.4), (40, 0.4), (60, -0.6), (110, -0.6), (130, 0.4), (150, 0.4)]
    s = K(sh, f, N, True); sl = KL(sh, f, N, True, lag=9)
    sway_side(c, s, 0.8); c["spine.rz"] = 1.2 * sl; c["chest.rz"] = 0.8 * sl
    look = [(0, 0), (14, 0), (28, 1), (46, 1), (58, -0.4), (76, -0.4), (88, 0), (150, 0)]
    c["neck.ry"] = 6 * K(look, f, N, True); c["head.ry"] = 9 * KL(look, f, N, True, lag=4)
    c["head.rx"] += 4 * bump(f, 92, 104) + 2 * bump(f, 104, 114)
    c["head.rz"] = 2 * K([(0, 0.5), (60, -0.5), (120, 0.8), (150, 0.5)], f, N, True)
    stroke = ease_io((f - 112) / 8) * (1 - ease_io((f - 138) / 10))
    f_clasp(c, 1.0)
    if stroke > 0:
        dn = 0.5 + 0.5 * math.cos(math.pi * (f - 118) / 8) if 118 <= f <= 134 else 1.0
        arm_ik(c, "R", V(-0.006, 0.012 - 0.026 * (1 - dn), 0.072), V(-0.9, -0.6, -0.3), "chest", stroke)
        c["handR.bend"] = lerp(c["handR.bend"], -10, stroke); fingers(c, "R", lerp(c["fingersR.curl"], 40, stroke))
        c["head.rx"] += -3 * stroke
        c["beard1.rx"] = 3 * stroke * (1 - dn)
    blink(c, f, N, [20, 72, 78, 132], base=1.3, slow=1.5)
    stand_feet(rig, c, spread=0.004, pitchL=K([(0, 0), (60, 0), (70, 4), (110, 4), (120, 0), (150, 0)], f, N, True))
    f_cloak(c, f, N, 0.6)
    return c


@clip("father", "walk", 40, True, markers={"contactL": 0, "contactR": 20}, speed=F_WALK,
      notes="dignified: unhurried 90 steps/min, a little stooped, hands clasped behind his back, firm heel strikes, "
            "gentle hip sway; the open robe's panels swing with the legs, beard and head-cloth follow late")
def father_walk(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=F_WALK[0], lift=0.011, duty=F_WALK[1], heel=10, toeoff=20)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0055 - 0.0026 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = -4 * math.cos(ph); c["chest.ry"] = 6 * math.cos(ph - 0.3); c["head.ry"] = -2 * math.cos(ph - 0.6)
    c["hips.rz"] = 2.2 * math.cos(ph - 1.6); c["chest.rz"] = -1.2 * math.cos(ph - 2.0); c["head.rz"] = 0.7 * math.cos(ph - 2.3)
    c["spine.rx"] = 1.5; c["head.rx"] = -1 + 1.5 * math.cos(2 * ph - 1.2)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.010, 0.204, -0.050), V(sx * 1.0, -0.2, 0.6))
        c[f"hand{side}.bend"] = 10; c[f"hand{side}.twist"] = sx * 40; fingers(c, side, 40)
    c["cloakL.rx"] = -7 * math.cos(ph - 0.5); c["cloakR.rx"] = 7 * math.cos(ph - 0.5)
    c["headcloth.rx"] = 2 * math.cos(2 * ph - 1.0)
    blink(c, f, N, [28], base=1.25)
    return c


@clip("father", "talk", 96, True,
      notes="warm and plain: the right hand opens palm-up toward the listener on the stressed syllables, the left "
            "comes to his heart once, slow nods on the beats, small head tilts; jaw in an irregular syllable rhythm "
            "(lip sync overrides it); beard follows the jaw")
def father_talk(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=0.9)
    jk, beats = syllables(N, 17, amp=(5, 12), dur=(3.5, 7.0), gap=0.28)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=10)
    btl = beat_curve(beats, f - 3, N, width=11)
    c["head.rx"] += 3.0 * bt; c["head.ry"] = 5 * wave(f, N, 1, 0.15); c["head.rz"] = 2.5 * wave(f, N, 1, 0.4)
    pa = K([(0, 0.3), (10, 0.9), (40, 1.0), (50, 0.2), (60, 0.0), (82, 0.0), (90, 0.4), (96, 0.3)], f, N, True)
    heart = K([(0, 0), (50, 0), (58, 1), (80, 1), (88, 0), (96, 0)], f, N, True)
    lift = pa * (0.7 + 0.3 * btl)
    c["upperArmR.bend"] = 8 + 36 * lift; c["forearmR.bend"] = 24 + 50 * lift; c["forearmR.twist"] = 12 - 82 * lift
    c["handR.bend"] = 6 - 20 * btl * pa; fingers(c, "R", 30 - 22 * btl * pa)
    chest_hand(c, "L", V(0.020, -0.004, 0.056), heart)
    c["chest.ry"] = -4 * lift; c["chest.rx"] += 1.2 * bt
    blink(c, f, N, [12, 50, 79], base=1.2, slow=1.3)
    stand_feet(rig, c, spread=0.004)
    f_cloak(c, f, N)
    return c


@clip("father", "sad_give", 120, False, markers={"out": 30, "give": FA_GIVE, "heart": 96}, props=["purse"],
      prop_win={"purse": (0, FA_GIVE - 1)},
      notes="giving away half of everything: the right hand is inside his robe at the chest (purse shown from 0, "
            "half hidden), slowly draws the purse out and looks at it, holds it out to his son at chest height with "
            "a small hesitation (pulls back, then offers), lets go at 2.2 s (marker give: the timeline swaps the purse "
            "to the son), then lays the empty hand on his heart and bows his head (holds)")
def father_sad_give(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.6)
    draw = ease_io((f - 4) / 22)
    offer = ease_io((f - 28) / 12)
    hes = bump(f, 36, 50)
    rel = ease_io((f - FA_GIVE + 2) / 4)
    heart = ease_io((f - 72) / 18)
    inside = V(-0.012, 0.236, 0.040)        # root space: hand under the robe front at the chest
    look = V(-0.030, 0.222, 0.072)          # in front, looked at
    give = V(-0.032, 0.226, 0.086)          # held out to the son (0.09 away)
    tgt = inside.lerp(look, draw).lerp(give, offer) + V(0, 0, -0.012 * hes)
    arm_ik(c, "R", tgt, V(-1.0, -0.6, -0.2), "root", 1.0)
    chest_hand(c, "R", V(-0.016, 0.000, 0.052), heart, V(-0.9, -0.6, -0.2))
    palm_up(c, "R", offer * (1 - heart) * 0.6, curl=50)
    fingers(c, "R", lerp(lerp(60, 55, offer), 20, rel) + 10 * heart)
    c["handR.bend"] = lerp(c["handR.bend"], -14, heart)
    c["head.rx"] += 10 * draw * (1 - offer) + 4 * offer + 10 * heart
    c["neck.rx"] = 4 * heart
    c["head.ry"] = -6 * draw * (1 - offer)
    c["chest.rx"] += 2 * offer + 2 * heart
    c["hips.tz"] = 0.004 * offer * (1 - heart)
    # left hand: hangs, then covers the right on the heart
    chest_hand(c, "L", V(-0.004, -0.008, 0.060), heart * 0.9, V(0.9, -0.6, -0.2))
    sigh = bump(f, 88, 112)
    c["shoulderL.raise"] += 2 * sigh - 2 * heart; c["shoulderR.raise"] += 2 * sigh - 2 * heart
    blink(c, f, N, [20, 98], loop=False, base=1.0 + 1.4 * heart, slow=1.6)
    stand_feet(rig, c, spread=0.004, fwdR=0.008 * offer)
    return c


@clip("father", "wave_sad", 120, True,
      notes="watching his son go: a slow wave with the right hand at shoulder height (two slow side-to-side sweeps), "
            "the hand sinks and hangs, a sad sigh with the head dropping, then he lifts it to wave again; the left "
            "hand rests on his heart")
def father_wave_sad(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=1.2)
    up = K([(0, 1.0), (40, 1.0), (52, 0.0), (90, 0.0), (106, 1.0), (120, 1.0)], f, N, True)
    sw = math.sin(2 * math.pi * 2 * f / N)
    arm_ik(c, "R", V(-0.090 + 0.010 * sw * up, 0.278 * up + 0.170 * (1 - up), 0.040 * up + 0.010), V(-1.0, -0.6, -0.2),
           "root", 0.3 + 0.7 * up)
    c["handR.twist"] = -60 * up; c["handR.bend"] = 14 * sw * up; fingers(c, "R", lerp(30, 8, up))
    chest_hand(c, "L", V(0.018, -0.004, 0.056))
    c["handL.bend"] = -10
    sigh = K([(0, 0), (52, 0), (62, 1), (72, 1), (88, 0), (120, 0)], f, N, True)
    c["head.rx"] += 6 * (1 - up) + 4 * sigh; c["neck.rx"] = 4 * (1 - up)
    c["chest.rx"] += 3 * (1 - up) - 2 * sigh; c["shoulderL.raise"] += 3 * sigh - 2 * (1 - up); c["shoulderR.raise"] += 3 * sigh - 2 * (1 - up)
    c["head.rz"] = 4 * up
    blink(c, f, N, [30, 66, 100], base=1.6, slow=1.8)
    stand_feet(rig, c, spread=0.004)
    f_cloak(c, f, N, 0.8)
    return c


@clip("father", "look_far", 120, True,
      notes="every day at the gate: right hand shading his eyes (palm down over the brows), leaning forward from the "
            "hips, rising onto his toes to see further, head slowly scanning the road left-right-centre, the left "
            "hand on the small of his back (old back); a hopeful little lean, then a sigh back down")
def father_look_far(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=0.8)
    scan = K([(0, 0), (20, -1), (44, -1), (64, 0.6), (84, 0.6), (104, 0), (120, 0)], f, N, True)
    toes = bump(f, 50, 96)
    c["hips.tz"] = 0.006 + 0.004 * toes; c["spine.rx"] = 4 + 3 * toes; c["chest.rx"] += 4 + 2 * toes
    c["neck.rx"] = -4; c["head.rx"] = -8 - 2 * toes
    c["head.ry"] = 12 * scan; c["neck.ry"] = 5 * scan; c["chest.ry"] = 3 * scan
    c["hips.ty"] = 0.006 * toes
    arm_ik(c, "R", V(-0.012, 0.094, 0.082), V(-1.0, -0.2, -0.3), "chest")
    c["handR.bend"] = -30; c["handR.twist"] = -70; fingers(c, "R", 8)
    arm_ik(c, "L", V(0.036, 0.206, -0.048), V(1.0, -0.2, 0.6))
    c["handL.bend"] = 20; c["handL.twist"] = 60; fingers(c, "L", 30)
    blink(c, f, N, [30, 76, 110], base=1.15, slow=1.4)
    stand_feet(rig, c, spread=0.004, pitchL=-16 * toes, pitchR=-16 * toes, fwdL=0.010)
    f_cloak(c, f, N, 0.7)
    return c


@clip("father", "see_son", 75, False, markers={"gasp": 6, "open": 52},
      notes="'Is that... my boy?!': freezes mid-breath, both hands fly to his mouth (gasp), leans in staring, a "
            "trembling half second, then the arms swing wide open, palms forward, chest lifting, laughing through "
            "tears (holds, ready to run)")
def father_see_son(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.2)
    gasp_in = ease_io((f - 2) / 6)
    gasp = gasp_in * (1 - ease_io((f - 40) / 12))
    trem = math.sin(f * 2.6) * bump(f, 14, 40)
    opn = ease_io((f - 42) / 14)
    over = bump(f, 50, 66)
    c["chest.rx"] += -4 * gasp + 2 * opn - 2 * over; c["head.rx"] += -4 * gasp - 6 * opn
    c["hips.tz"] = 0.006 * gasp + 0.004 * opn
    c["spine.rx"] = 2 * gasp
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.012, -0.034, 0.040 + 0.002 * trem), V(sx * 1.0, -0.6, -0.1), "head", gasp_in)
        c[f"hand{side}.bend"] = -10 * gasp; fingers(c, side, lerp(26, 18, gasp))
        arm_ik(c, side, V(sx * 0.122, 0.262 + 0.010 * over, 0.062), V(sx * 0.6, -1.0, -0.2), "root", opn)
        c[f"hand{side}.twist"] = sx * 30 * opn
        if opn > 0:
            fingers(c, side, lerp(c[f"fingers{side}.curl"], 6, opn))
            c[f"hand{side}.bend"] = lerp(c[f"hand{side}.bend"], -18, opn)
    c["jaw.rx"] = 8 * gasp + 6 * opn
    c["shoulderL.raise"] += 4 * gasp; c["shoulderR.raise"] += 4 * gasp
    stand_feet(rig, c, spread=0.005, fwdL=0.012 * opn, pitchR=8 * opn)
    blink(c, f, N, [30], loop=False)
    c["eyelids.sy"] = min(c["eyelids.sy"], 1.0) if f < 28 else c["eyelids.sy"]
    return c


@clip("father", "run", 24, True, markers={"contactL": 0, "contactR": 12}, speed=F_RUN,
      notes="THE moment: an old man's joyful, slightly clumsy run (150 steps/min, short strides, a little float): "
            "the left fist hitches the robe's left front panel up at his hip, the right arm reaches forward toward "
            "his son, wobbling; body pitched forward, a lopsided bob (the right step lands heavier), shoulders "
            "rolling, head-cloth and beard flying back, the free right panel flapping")
def father_run(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=F_RUN[0], lift=0.022, duty=F_RUN[1], heel=8, toeoff=34, lift_shape=0.8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0060 - 0.0065 * math.cos(2 * ph - 0.9) - 0.0025 * math.cos(ph - 0.9)
    c["hips.tz"] = 0.006
    c["hips.ry"] = -6 * math.cos(ph); c["chest.ry"] = 9 * math.cos(ph - 0.3); c["head.ry"] = -4 * math.cos(ph - 0.6)
    c["hips.rz"] = 3.2 * math.cos(ph - 1.6) + 1.2; c["chest.rz"] = -2.4 * math.cos(ph - 2.0) - 1.0
    c["head.rz"] = 3 * math.cos(ph - 2.4)
    c["hips.tx"] = 0.003 * math.cos(ph - 1.6)
    c["spine.rx"] = 8; c["chest.rx"] += 8 + 3 * math.cos(2 * ph - 1.2) + 2 * math.cos(ph - 1.4); c["neck.rx"] = -8
    c["head.rx"] = -10 + 3 * math.cos(2 * ph - 1.6)
    # left fist hitching the robe panel up at the front of his left hip
    hitch = V(0.046, 0.168 + 0.005 * math.cos(2 * ph - 1.0), 0.078)
    arm_ik(c, "L", hitch, V(1.0, -0.2, -0.6))
    c["handL.bend"] = 20; c["handL.twist"] = 40; fingers(c, "L", 82)
    c["cloakL.rx"] = -34 + 3 * math.cos(2 * ph - 1.0); c["cloakL.rz"] = 4; c["hang.cloakL"] = 0.0
    # right arm reaching forward toward the son, a wobbly reach
    reach = V(-0.052 + 0.006 * math.cos(ph - 0.4), 0.262 + 0.010 * math.cos(2 * ph - 1.4), 0.112)
    arm_ik(c, "R", reach, V(-1.0, -0.6, -0.2))
    c["handR.bend"] = -14 + 8 * math.cos(2 * ph - 2.0); c["handR.twist"] = -30; fingers(c, "R", 10)
    c["cloakR.rx"] = -4 + 12 * math.cos(ph - 0.8)
    c["headcloth.rx"] = 8 + 4 * math.cos(2 * ph - 1.4)
    c["beard1.rx"] = 6 + 3 * math.cos(2 * ph - 1.2)
    c["jaw.rx"] = 6
    blink(c, f, N, [], base=1.0)
    return c


@clip("father", "hug", 90, True,
      notes="the son found (son 0.10 in front): leaning over him, both arms wrapped round his shoulders and upper "
            "back, his cheek on the top of his son's head (head turned to his right), eyes shut, rocking gently from "
            "side to side, the right hand patting the son's back now and then; a happy shaky sob in the breath; robe "
            "panels and beard sway with the rock")
def father_hug(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=1.0)
    rock = wave(f, N, 1, 0.0)
    pat = pulses(f, N, [(20, 1.0), (28, 0.8), (64, 0.9)], decay=2.0)
    sob = pulses(f, N, [(40, 0.7), (45, 0.5)], decay=2.0)
    lean_hug(c, 1.4)
    sway_side(c, -rock, 0.9)
    c["chest.rz"] = c.get("chest.rz", 0.0) - 1.4 * wave(f, N, 1, -0.06)
    c["chest.rx"] += 1.5 * sob; c["shoulderL.raise"] += 2 * sob; c["shoulderR.raise"] += 2 * sob
    c["neck.rx"] = 10; c["head.rx"] += 14; c["head.ry"] = -24; c["head.rz"] = 12 - 3 * rock
    for (side, sx), tgt in zip((("L", 1), ("R", -1)), F_HUG_HANDS):
        p = tgt + (V(0, 0.004 * pat, -0.006 * pat) if side == "R" else V(0, 0, 0))
        arm_ik(c, side, p, V(sx * 1.0, 0.3, 0.2))
        c[f"hand{side}.bend"] = 34; c[f"hand{side}.twist"] = -sx * 60; fingers(c, side, 40)
    blink(c, f, N, [], base=12.78)
    stand_feet(rig, c, spread=0.005, fwdR=0.008)
    f_cloak(c, f, N, 1.2)
    return c


@clip("father", "call_servants", 90, False, markers={"clap1": 14, "clap2": 24, "point": 42},
      notes="'Quick! Bring the best robe!': straightens up as far as his old back allows, claps twice above his head, "
            "flings the right arm out pointing to his right (toward the house), then brings both hands together at "
            "his chest, beaming (a happy pose to hold while the servants answer)")
def father_call_servants(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.3)
    up = ease_io((f - 2) / 9) * (1 - ease_io((f - 28) / 8))
    gap = min(1.0, min(abs(f - 14), abs(f - 24)) / 4.0)
    up_in = ease_io((f - 2) / 9)
    point_in = ease_io((f - 30) / 8)
    point = point_in * (1 - ease_io((f - 62) / 12))
    end = ease_io((f - 62) / 16)
    c["chest.rx"] += -6 * up - 2 * point; c["spine.rx"] = -3 * up; c["head.rx"] += -8 * up
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * (0.006 + 0.030 * gap), 0.372, 0.034), V(sx * 1.0, -0.6, -0.1), "root", up if side == "L" else up_in)
        c[f"hand{side}.twist"] = -sx * 70 * up; fingers(c, side, lerp(26, 6, up))
    arm_ik(c, "R", V(-0.140, 0.270, 0.060), V(-0.6, -1.0, -0.2), "root", point_in)
    c["handR.bend"] = lerp(c["handR.bend"], -4, point); fingers(c, "R", lerp(c["fingersR.curl"], 30, point))
    c["chest.ry"] = -14 * point; c["head.ry"] = -24 * point
    for side, sx in (("L", 1), ("R", -1)):
        chest_hand(c, side, V(sx * 0.014, -0.010, 0.060), end, V(sx * 1.0, -0.6, -0.2))
        if end > 0:
            c[f"hand{side}.twist"] = lerp(c.get(f"hand{side}.twist", 0.0), -sx * 60, end)
            fingers(c, side, lerp(c[f"fingers{side}.curl"], 30, end))
    c["jaw.rx"] = 8 * up + 10 * point + 4 * end
    c["head.rz"] = 5 * end
    stand_feet(rig, c, spread=0.005, fwdR=-0.006 * point)
    blink(c, f, N, [70], loop=False)
    return c


@clip("father", "feast_cheer", 60, False, markers={"up": 16},
      notes="'Let's celebrate!': a little bounce and both arms fly up in a wide V, head thrown back laughing (jaw "
            "pulses), chest lifted; holds arms up, beaming")
def father_feast_cheer(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.3)
    dip = bump(f, 0, 10)
    up = ease_io((f - 6) / 10)
    over = bump(f, 14, 30)
    laugh = pulses(f, N, [(16, 1.0), (22, 0.8), (28, 0.7), (35, 0.5)], decay=2.5, loop=False)
    c["hips.ty"] = -0.006 * dip + 0.004 * over
    c["chest.rx"] += 2 * dip - 6 * up; c["spine.rx"] = -3 * up; c["head.rx"] += 3 * dip - 14 * up + 2 * laugh
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * (0.110 + 0.006 * over), 0.372 + 0.008 * over, 0.040), V(sx * 1.0, -0.2, -0.3), "root", up)
        c[f"hand{side}.bend"] = -20 * up; c[f"hand{side}.twist"] = sx * 20 * up; fingers(c, side, lerp(26, 6, up))
    c["shoulderL.raise"] += 2 * laugh; c["shoulderR.raise"] += 2 * laugh
    c["jaw.rx"] = 6 * up + 8 * laugh
    stand_feet(rig, c, spread=0.005, pitchL=-8 * over, pitchR=-8 * over)
    blink(c, f, N, [], loop=False)
    c["eyelids.sy"] = 1.0 + 4.0 * up            # laughing, crinkled eyes
    f_cloak(c, f, N, 0.5)
    return c


@clip("father", "dance", 66, True, markers={"clap1": 16.5, "clap2": 49.5},
      notes="an old man's happy folk dance at the feast (~108 bpm, beat every 16.5 frames): claps on 2 and 4 with "
            "the hands at chin height, a step-together side-step that bounces on every beat, shoulders shimmying, a "
            "little turn to each side, head bobbing, beard and robe swinging, laughing")
def father_dance(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=0.3)
    bph = (f % 16.5) / 16.5
    bounce = math.cos(2 * math.pi * bph)
    side = wave(f, N, 1, 0.0)
    claps = (16.5, 49.5)
    clap = pulses(f, N, [(h, 1.0) for h in claps], decay=2.0)
    c["hips.ry"] = 16 * wave(f, N, 1, 0.1); c["chest.ry"] = 6 * wave(f, N, 1, 0.05)
    c["hips.ty"] = -0.006 + 0.004 * bounce
    c["hips.tx"] = 0.008 * side; c["hips.rz"] = 3 * wave(f, N, 2, 0.1)
    c["chest.rz"] = -3 * wave(f, N, 2, 0.15) + 2 * math.sin(f * 0.8)
    c["head.rz"] = 5 * wave(f, N, 2, 0.35); c["head.rx"] += -4 + 2 * bounce
    open_ = min(1.0, min(abs(((f - h + N / 2) % N) - N / 2) for h in claps) / 7.0)
    for s_, sx in (("L", 1), ("R", -1)):
        arm_ik(c, s_, V(sx * (0.008 + 0.040 * open_), 0.284 + 0.008 * open_, 0.056), V(sx * 1.0, -0.6, -0.2))
        c[f"hand{s_}.twist"] = -sx * 70; c[f"hand{s_}.bend"] = -10; fingers(c, s_, 8)
    for side_, sx in (("L", 1), ("R", -1)):
        lift = bump((f + (0 if side_ == "L" else 33)) % N, 2, 18)
        b = rig.head["foot" + side_]
        c[f"ik.leg{side_}"] = V(b.x + sx * (0.006 + 0.008 * lift) + 0.010 * side, planted_ankle_y(rig, side_, 0) + 0.012 * lift, b.z + 0.008 * lift)
        c[f"foot{side_}.pitch"] = 10 * lift
    c["jaw.rx"] = 5 + 4 * clap
    c["cloakL.rx"] = -5 * side; c["cloakR.rx"] = 5 * side
    blink(c, f, N, [30])
    c["eyelids.sy"] = max(c["eyelids.sy"], 3.0)           # laughing eyes
    return c


@clip("father", "plead", 96, True,
      notes="begging his angry son to come in: leaning in, both palms open and up toward him, gently pumping on the "
            "stressed words, head tilted, a slow nod; the left hand once comes to his heart; jaw talks softly "
            "(lip sync overrides it)")
def father_plead(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=0.9)
    jk, beats = syllables(N, 29, amp=(4, 10), dur=(3.5, 7.0), gap=0.3)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=10)
    heart = K([(0, 0), (54, 0), (62, 1), (80, 1), (88, 0), (96, 0)], f, N, True)
    c["hips.tz"] = 0.008; c["spine.rx"] = 3; c["chest.rx"] += 4 + 1.5 * bt
    c["head.rx"] += 2 + 3 * bt; c["head.rz"] = -8 + 2 * wave(f, N, 1, 0.3); c["head.ry"] = 3 * wave(f, N, 1, 0.1)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.056, 0.226 + 0.008 * bt, 0.080 + 0.006 * bt), V(sx * 1.0, -0.4, -0.3), "root", 1.0)
        palm_up(c, side, 1.0 if side == "R" else 1 - heart, curl=12)
    chest_hand(c, "L", V(0.020, -0.004, 0.056), heart)
    blink(c, f, N, [22, 70], base=1.3, slow=1.4)
    stand_feet(rig, c, spread=0.004, fwdL=0.010)
    f_cloak(c, f, N)
    return c


@clip("father", "arm_out", 45, False, markers={"out": 26},
      notes="'Come, my son': slowly holds out his right hand at chest height toward the elder son 0.10-0.12 in front "
            "(wrist 0.062 in front, palm half up, fingers open), the left hand on his heart, head tilted, a warm "
            "smile; holds still so the brother can take the hand (take_hand meets it)")
def father_arm_out(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.3)
    out = ease_io((f - 4) / 22)
    arm_ik(c, "R", vlerp(V(-0.060, 0.170, 0.030), ARM_OUT, out), V(-1.0, -0.6, -0.2), "root", out)
    c["forearmR.twist"] = lerp(12, -50, out); c["handR.bend"] = lerp(6, -10, out); fingers(c, "R", lerp(26, 16, out))
    chest_hand(c, "L", V(0.018, -0.004, 0.056), ease_io((f - 10) / 16))
    c["head.rz"] = -6 * out; c["head.rx"] += 3 * out; c["chest.rx"] += 2 * out
    c["hips.tz"] = 0.004 * out
    stand_feet(rig, c, spread=0.004, fwdR=0.008 * out)
    blink(c, f, N, [36], loop=False, base=1.2)
    return c


# =============================================================================================== BROTHER
# Rest: broad farmer, right fist round the hoe (handle vertical, blade edge on the page). The hoe is always shown. The
# hoe can be planted with its blade edge (`hoeTip`) at a point on the page (`staff.foot`, `staff.dir` = from the blade
# edge up the handle, root space): the right wrist is solved so the tip lands there; otherwise it follows the hand.
B_WALK = (0.072, 0.60)        # N 36 -> 0.100 u/s
HOE_SIDE = (V(-0.118, 0.0, 0.050), V(0.02, 1.0, -0.06))      # planted at his right side, leaning a little in
HOE_LEAN = (V(-0.070, 0.0, 0.086), V(0.10, 1.0, -0.30))      # planted in front-right, leaning on it
HOE_HANG = V(-0.098, 0.180, 0.030)                            # right wrist when the hoe hangs loose (blade off the page)


def b_base(rig, f, N, cycles=1, amp=1.0, phase=0.0, hoe=HOE_SIDE):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.8 * b * amp; c["spine.rx"] = -0.7 * b * amp
    c["shoulderL.raise"] = 1.2 * b * amp; c["shoulderR.raise"] = 1.2 * b * amp
    c["neck.rx"] = 0.5 * b * amp
    c["upperArmL.raise"] = -18; c["upperArmL.bend"] = 6; c["forearmL.bend"] = 22; c["forearmL.twist"] = -10
    c["handL.bend"] = 6; fingers(c, "L", 30)
    c["head.rx"] = -1
    if hoe is not None:
        staff_at(c, *hoe)
        c["pole.armR"] = V(-0.8, -0.4, -0.4)
    return c


def staff_at(c, foot, d, w=1.0):
    c["staff.foot"] = Vector(foot); c["staff.dir"] = Vector(d).normalized(); c["staff.w"] = w


def b_cloth(c, f, N, amp=1.0, phase=0.0):
    c["headcloth.rx"] = c.get("headcloth.rx", 0.0) + 1.5 * amp * wave(f, N, 1, phase)


@clip("brother", "idle", 150, True, props=["hoe"],
      notes="the hard-working elder son at rest: the hoe planted at his right side with his fist on top, the left "
            "fist on his hip, broad stance, weight shifts, a slow look over the field, wipes his brow with the back "
            "of the left wrist once, a stretch of the back; steady blinks")
def brother_idle(rig, f, N):
    c = b_base(rig, f, N, cycles=3, amp=1.0)
    sh = [(0, -0.4), (40, -0.4), (56, 0.6), (104, 0.6), (120, -0.4), (150, -0.4)]
    s = K(sh, f, N, True); sl = KL(sh, f, N, True, lag=8)
    sway_side(c, s, 0.8); c["spine.rz"] = 1.2 * sl; c["chest.rz"] = 0.8 * sl
    look = [(0, 0), (20, 0), (34, -1), (56, -1), (68, 0.5), (84, 0.5), (94, 0), (150, 0)]
    c["neck.ry"] = 6 * K(look, f, N, True); c["head.ry"] = 10 * KL(look, f, N, True, lag=4)
    wipe = ease_io((f - 100) / 8) * (1 - ease_io((f - 122) / 10))
    hand_on_hip(c, rig, "L", 1.0)
    c["handL.bend"] = lerp(c["handL.bend"], 6, wipe); fingers(c, "L", lerp(c["fingersL.curl"], 30, wipe))
    if wipe > 0:
        across = smooth((f - 106) / 14)
        arm_ik(c, "L", V(0.024 - 0.034 * across, 0.022, 0.060), V(1.0, -0.6, -0.2), "head", wipe)
        c["handL.bend"] = lerp(c["handL.bend"], -30, wipe); c["handL.twist"] = lerp(c["handL.twist"], 70, wipe)
        c["head.rx"] += -6 * wipe
    stretch = bump(f, 126, 146)
    c["chest.rx"] += -4 * stretch; c["head.rx"] += -4 * stretch
    blink(c, f, N, [26, 84, 140])
    stand_feet(rig, c, spread=0.008, pitchR=K([(0, 0), (56, 0), (64, 5), (104, 5), (112, 0), (150, 0)], f, N, True))
    b_cloth(c, f, N, 0.6)
    return c


@clip("brother", "walk_hoe", 36, True, markers={"contactL": 0, "contactR": 18}, speed=B_WALK, props=["hoe"],
      notes="coming home from the field: the hoe on his right shoulder (fist in front at the chest, blade behind his "
            "back), heavy purposeful 100 steps/min, the left arm swinging, shoulders rolling, head-cloth tails "
            "bouncing late")
def brother_walk_hoe(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.5, hoe=None)
    g = gait(rig, f, N, L=B_WALK[0], lift=0.013, duty=B_WALK[1], heel=10, toeoff=22)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0060 - 0.0032 * math.cos(2 * ph - 0.5)
    c["hips.ry"] = -5 * math.cos(ph); c["chest.ry"] = 7 * math.cos(ph - 0.3); c["head.ry"] = -2 * math.cos(ph - 0.6)
    c["hips.rz"] = 2.6 * math.cos(ph - 1.6); c["chest.rz"] = -1.8 * math.cos(ph - 2.0)
    c["spine.rx"] = 2; c["head.rx"] = -1 + 1.5 * math.cos(2 * ph - 1.2)
    c["upperArmL.bend"] = 6 - 24 * math.cos(ph - 0.25); c["forearmL.bend"] = 24 - 10 * math.cos(ph - 0.9)
    c["handL.bend"] = 6 - 10 * math.cos(ph - 1.5); fingers(c, "L", 40)
    arm_ik(c, "R", V(-0.030, 0.246 + 0.002 * math.cos(2 * ph - 0.8), 0.046), V(-1.0, -0.8, -0.2), "root")
    c["aim.hoe"] = V(0.05, 0.62, -0.78)
    c["handR.twist"] = 0
    b_cloth(c, f, N, 0)
    c["headcloth.rx"] = 3 * math.cos(2 * ph - 1.2)
    blink(c, f, N, [22])
    return c


@clip("brother", "talk", 96, True, props=["hoe"],
      notes="blunt and firm: leaning a little on the planted hoe, the left hand chops the air on the stressed "
            "syllables and once taps his chest, head nods hard on the beats; jaw in an irregular rhythm (lip sync "
            "overrides it)")
def brother_talk(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 53, amp=(6, 14), dur=(3.0, 6.0), gap=0.22)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=7)
    btl = beat_curve(beats, f - 3, N, width=8)
    c["head.rx"] = -1 + 5 * bt; c["head.ry"] = 5 * wave(f, N, 1, 0.1); c["head.rz"] = 3 * wave(f, N, 1, 0.3)
    pa = K([(0, 0.3), (10, 1.0), (44, 1.0), (54, 0.2), (88, 0.2), (96, 0.3)], f, N, True)
    me = K([(0, 0), (50, 0), (58, 1), (78, 1), (86, 0), (96, 0)], f, N, True)
    arm_ik(c, "L", V(0.062, 0.218 + 0.014 * btl, 0.074 - 0.006 * btl), V(1.0, -0.5, -0.3), "root", pa)
    c["handL.twist"] = -60 * pa; c["handL.bend"] = -10 * btl; fingers(c, "L", 14)
    chest_hand(c, "L", V(0.016, -0.004, 0.052), me)
    c["chest.rx"] += 2 * bt
    blink(c, f, N, [16, 60])
    stand_feet(rig, c, spread=0.008)
    b_cloth(c, f, N)
    return c


def hoe_work(f):
    """work_field: hoe blade edge (tip) and handle direction (tip -> grip) over the 60-frame stroke."""
    tipk = {"y": [(0, 0.009), (14, 0.009), (24, 0.012), (36, 0.090), (46, 0.130), (54, 0.050), (60, 0.009)],
            "z": [(0, 0.140), (14, 0.112), (24, 0.104), (36, 0.140), (46, 0.150), (54, 0.150), (60, 0.140)]}
    ang = [(0, 34.0), (14, 30.0), (24, 30.0), (36, 40.0), (46, 46.0), (54, 40.0), (60, 34.0)]   # handle from vertical
    y = K(tipk["y"], f, 60, True); z = K(tipk["z"], f, 60, True); a = math.radians(K(ang, f, 60, True))
    return V(-0.018, max(0.0, y), z), V(0.06, math.cos(a), -math.sin(a))


@clip("brother", "work_field", 60, True, markers={"strike": 0, "lift": 40}, props=["hoe"],
      notes="hoeing: bent over the bare strip, the right fist at the top of the handle and the left hand lower down "
            "it; the blade chops into the soil in front (blade edge on the page at the strike, marker strike) and "
            "drags back toward him, then he straightens a little and swings the hoe up and forward for the next "
            "chop; knees soft, the body rocks with the stroke, a grunt in the jaw at the strike")
def brother_work_field(rig, f, N):
    tip, d = hoe_work(f)
    c = b_base(rig, f, N, cycles=1, amp=0.4, hoe=(tip, d))
    lift = K([(0, 0.0), (14, 0.1), (24, 0.2), (36, 0.8), (46, 1.0), (54, 0.5), (60, 0.0)], f, N, True)
    hit = pulses(f, N, [(0, 1.0)], decay=2.0)
    c["hips.tz"] = -0.012 + 0.004 * lift; c["hips.ty"] = -0.012 + 0.004 * lift
    c["hips.rx"] = 10 - 4 * lift; c["spine.rx"] = 14 - 6 * lift + 3 * hit; c["chest.rx"] += 14 - 8 * lift + 4 * hit
    c["neck.rx"] = -6; c["head.rx"] = 4 - 2 * lift
    c["hips.ry"] = 6 - 3 * lift; c["chest.ry"] = 6 + 2 * lift
    c["pole.armR"] = V(-1.0, -0.2, -0.3)
    c["handR.twist"] = -10
    # left hand lower down the handle (hoe space: the rest hoe points down from the grip)
    arm_ik(c, "L", V(0.000, -0.050, 0.000), V(1.0, -0.4, -0.2), "hoe")
    c["handL.bend"] = 10; c["handL.twist"] = 0; fingers(c, "L", 80)
    c["jaw.rx"] = 6 * hit
    blink(c, f, N, [30])
    stand_feet(rig, c, spread=0.012, fwdL=0.024, pitchR=4)
    c["headcloth.rx"] = 3 * lift
    return c


@clip("brother", "shake_head", 60, False, markers={"shake": 24},
      props=["hoe"],
      notes="watching his little brother swagger off: leans both hands on the planted hoe in front, a long "
            "disapproving look, three slow head shakes with a tut (jaw), lips pressed; holds leaning on the hoe")
def brother_shake_head(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.4, hoe=HOE_LEAN)
    lean = ease_io((f - 2) / 14)
    sh = K([(0, 0), (16, 0), (22, 1), (30, -1), (38, 1), (46, -0.6), (52, 0), (60, 0)], f, N)
    if lean < 1:
        staff_at(c, vlerp(HOE_SIDE[0], HOE_LEAN[0], lean), vlerp(HOE_SIDE[1], HOE_LEAN[1], lean))
    arm_ik(c, "L", V(-0.004, 0.034, 0.010), V(1.0, -0.5, -0.4), "hoe", lean)
    c["handL.bend"] = lerp(6, 24, lean); c["handL.twist"] = -40 * lean; fingers(c, "L", lerp(30, 60, lean))
    c["hips.tz"] = 0.006 * lean; c["spine.rx"] = 4 * lean; c["chest.rx"] += 5 * lean
    c["head.ry"] = 12 * sh; c["neck.ry"] = 4 * sh; c["head.rx"] = 4 * lean
    c["jaw.rx"] = 3 * bump(f, 22, 28) + 3 * bump(f, 36, 42)
    stand_feet(rig, c, spread=0.008, fwdR=0.006 * lean)
    blink(c, f, N, [10, 40], loop=False, base=1.6)
    return c


@clip("brother", "listen_music", 60, False, markers={"ear": 26}, props=["hoe"],
      notes="stops dead at the courtyard wall: swings the hoe down off his shoulder and plants it, cups his left "
            "hand behind his left ear, head tilted and turned toward the house (music and dancing?!), frowning; "
            "holds listening")
def brother_listen_music(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.4, hoe=None)
    down = ease_io((f - 2) / 14)
    ear = ease_io((f - 16) / 12)
    shoulder = V(-0.030, 0.246, 0.046)
    side_ = V(-0.110, 0.172, 0.036)
    if down < 0.999:
        arm_ik(c, "R", shoulder.lerp(side_, down), V(-1.0, -0.8, -0.2), "root")
        c["aim.hoe"] = vlerp(V(0.05, 0.62, -0.78), V(-0.02, -1.0, 0.06), smooth(down))
    else:
        staff_at(c, *HOE_SIDE)
    arm_ik(c, "L", V(0.036, 0.008, -0.006), V(1.0, -0.4, 0.2), "head", ear)
    c["handL.bend"] = -20 * ear; c["handL.twist"] = 40 * ear; fingers(c, "L", lerp(30, 40, ear))
    c["head.rz"] = -12 * ear; c["head.ry"] = 10 * ear; c["neck.rx"] = -3 * ear; c["chest.rx"] += 2 * ear
    c["hips.ty"] = -0.003 * bump(f, 0, 12)
    stand_feet(rig, c, spread=0.008)
    blink(c, f, N, [44], loop=False)
    return c


@clip("brother", "stomp_cross", 66, False, markers={"stamp1": 14, "stamp2": 28, "cross": 46}, props=["hoe"],
      notes="'Hmph!': two big angry stamps (left, right: knee up high, a jolt through the body), then the arms cross "
            "high on his chest with the hoe held upright in the crook of the arms, chin up, head turned away (holds "
            "the stubborn pose)")
def brother_stomp_cross(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.3, hoe=None)
    sL = bump(f, 4, 16); sR = bump(f, 18, 30)
    hitL = pulses(f, N, [(14, 1.0)], decay=1.6, loop=False); hitR = pulses(f, N, [(28, 1.0)], decay=1.6, loop=False)
    cross = ease_io((f - 30) / 14)
    turn = ease_io((f - 40) / 12)
    fist_up = 1 - cross
    # fists balled by the hips while stamping
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.078, 0.190 + 0.010 * (sL + sR), 0.026), V(sx * 1.0, -0.4, -0.4), "root", ease_io(f / 6))
        fingers(c, side, lerp(30, 85, fist_up))
    if f < 30:
        c["aim.hoe"] = V(-0.06, -1.0, 0.16)
    # crossed arms: left forearm over, right fist (with the hoe) tucked at the left upper arm
    arm_ik(c, "L", V(-0.036, 0.236, 0.050), V(1.0, -0.6, 0.4), "root", cross)
    arm_ik(c, "R", V(0.040, 0.242, 0.058), V(-1.0, -0.6, 0.4), "root", cross)
    c["handL.bend"] = lerp(6, 20, cross); fingers(c, "L", lerp(c["fingersL.curl"], 50, cross))
    c["handR.twist"] = 30 * cross
    if cross > 0:
        c["aim.hoe"] = vlerp(V(-0.06, -1.0, 0.16), V(0.10, -1.0, 0.10), cross)
    c["hips.ty"] = -0.008 * (hitL + hitR) + 0.004 * (sL + sR)
    c["chest.rx"] += 4 * (hitL + hitR) - 4 * turn; c["head.rx"] = 4 * (hitL + hitR) - 10 * turn
    c["head.ry"] = 30 * turn; c["neck.ry"] = 8 * turn; c["chest.ry"] = 6 * turn
    c["shoulderL.raise"] += 3 * cross; c["shoulderR.raise"] += 3 * cross
    stand_feet(rig, c, spread=0.010, liftL=0.030 * sL, liftR=0.030 * sR, fwdL=0.012 * sL, fwdR=0.012 * sR,
               pitchL=-10 * sL, pitchR=-10 * sR)
    c["jaw.rx"] = 4 * bump(f, 40, 50)
    blink(c, f, N, [56], loop=False, base=1.4)
    return c


@clip("brother", "complain", 120, True, markers={"point": 14, "me": 52, "up": 90}, props=["hoe"],
      notes="'All these years I worked for you...': jabs his left finger at his father, then thumps his own chest "
            "('I!'), then throws both hands up in disgust (the hoe goes up too), head shaking; jaw talks angrily "
            "(lip sync overrides it)")
def brother_complain(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=1.0, hoe=None)
    jk, beats = syllables(N, 71, amp=(7, 15), dur=(3.0, 5.5), gap=0.2)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=7)
    pt = K([(0, 0.4), (8, 1.0), (32, 1.0), (40, 0.0), (120, 0.4)], f, N, True)
    me = K([(0, 0), (38, 0), (46, 1), (66, 1), (72, 0), (120, 0)], f, N, True)
    up = K([(0, 0), (74, 0), (84, 1), (100, 1), (112, 0), (120, 0)], f, N, True)
    jab = sum(bump(f, a, a + 6) for a in (12, 20, 28))
    arm_ik(c, "L", V(0.050, 0.262, 0.130 + 0.010 * jab), V(1.0, -0.6, -0.2), "root", pt)
    c["handL.bend"] = -6 * pt; fingers(c, "L", lerp(30, 40, pt))
    chest_hand(c, "L", V(0.014, -0.004 + 0.004 * bump(f, 50, 56), 0.046), me)
    arm_ik(c, "R", V(-0.090, 0.186, 0.030), V(-1.0, -0.4, -0.4), "root", 1.0)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.100, 0.330, 0.050), V(sx * 1.0, -0.6, -0.3), "root", up)
        if side == "L":
            palm_up(c, "L", up * 0.5, curl=8)
    c["aim.hoe"] = vlerp(V(-0.06, -1.0, 0.16), V(-0.30, 0.5, -0.4), up)
    fingers(c, "R", 85)
    c["chest.rx"] += 3 * pt - 4 * up + 2 * bt; c["head.rx"] = -2 + 4 * bt - 8 * up
    c["head.ry"] = 10 * math.sin(f * 0.6) * up; c["chest.ry"] = -10 * pt + 6 * me
    c["hips.tz"] = 0.006 * pt
    blink(c, f, N, [36, 104], base=1.3)
    stand_feet(rig, c, spread=0.010, fwdL=0.010 * pt)
    b_cloth(c, f, N, 1.0)
    return c


@clip("brother", "soften", 75, False, markers={"drop": 24}, props=["hoe"],
      notes="his father's words land: a long breath out, the arms uncross and drop, shoulders sink, the hoe hangs "
            "loose in his right hand (blade near the ground), the head lowers to look at his feet, a small swallow, "
            "hurt and thinking (holds)")
def brother_soften(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.6, hoe=None)
    drop = ease_io((f - 8) / 22)
    look = ease_io((f - 24) / 18)
    swallow = bump(f, 52, 62)
    cross = 1 - drop
    arm_ik(c, "L", V(-0.036, 0.236, 0.050), V(1.0, -0.6, 0.4), "root", cross)
    arm_ik(c, "R", V(0.040, 0.242, 0.058), V(-1.0, -0.6, 0.4), "root", cross)
    arm_ik(c, "R", HOE_HANG, V(-1.0, -0.4, -0.4), "root", drop)
    c["aim.hoe"] = vlerp(V(0.10, -1.0, 0.10), V(-0.02, -1.0, 0.10), drop)
    c["upperArmL.raise"] = -24; c["forearmL.bend"] = lerp(22, 14, drop)
    fingers(c, "L", lerp(50, 30, drop)); fingers(c, "R", 80)
    c["chest.rx"] += 4 * look + 3 * drop; c["neck.rx"] = 10 * look; c["head.rx"] = 4 + 14 * look - 3 * swallow
    c["shoulderL.raise"] += -5 * drop + 3 * bump(f, 4, 20); c["shoulderR.raise"] += -5 * drop + 3 * bump(f, 4, 20)
    c["head.ry"] = 10 * (1 - drop)
    stand_feet(rig, c, spread=lerp(0.010, 0.006, drop))
    blink(c, f, N, [36, 56], loop=False, base=1.6, slow=1.8)
    return c


@clip("brother", "take_hand", 66, False, markers={"reach": 30, "take": 52}, props=["hoe"],
      notes="the open ending: a still pause looking down, a breath, he lifts his eyes to his father, then slowly "
            "reaches his left hand out and takes the father's offered right hand at chest height (wrist 0.046 in "
            "front: meets arm_out at 0.10-0.12 apart), a small squeeze; holds hand in hand, hoe hanging in the right")
def brother_take_hand(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.6, hoe=None)
    look = ease_io((f - 14) / 14)
    reach = ease_io((f - 26) / 22)
    sq = bump(f, 52, 62)
    arm_ik(c, "R", HOE_HANG, V(-1.0, -0.4, -0.4), "root")
    c["aim.hoe"] = V(-0.02, -1.0, 0.10); fingers(c, "R", 80)
    c["upperArmL.raise"] = -24; c["forearmL.bend"] = 14; fingers(c, "L", 30)
    arm_ik(c, "L", vlerp(V(0.070, 0.170, 0.020), V(0.024, 0.220, 0.050), reach), V(1.0, -0.6, -0.2), "root", reach)
    c["forearmL.twist"] = lerp(-10, 40, reach); c["handL.bend"] = lerp(6, 24, reach)
    fingers(c, "L", lerp(30, 50, reach) + 10 * sq)
    c["neck.rx"] = 10 * (1 - look); c["head.rx"] = 18 * (1 - look) - 2 * look; c["chest.rx"] += 4 * (1 - look) + 2 * reach
    c["hips.tz"] = 0.004 * reach
    c["shoulderL.raise"] += -5 * (1 - look); c["shoulderR.raise"] += -5
    stand_feet(rig, c, spread=0.006, fwdL=0.008 * reach)
    blink(c, f, N, [8, 40], loop=False, base=1.3)
    return c


# =============================================================================================== evaluation
HAND_SPACES = ("hoe", "handL", "handR", "purse")


def ik_limb(rig, basis, M, chs, limb):
    up, lo, end = {"legL": ("thighL", "shinL", "footL"), "legR": ("thighR", "shinR", "footR"),
                   "armL": ("upperArmL", "forearmL", "handL"), "armR": ("upperArmR", "forearmR", "handR")}[limb]
    key = "ik." + limb
    if key not in chs:
        return
    legs = limb.startswith("leg")
    side = limb[-1]
    sx = 1 if side == "L" else -1
    Mroot = M["root"] @ rig.rest["root"].inverted()

    def world(t, space):
        if space in M and space != "root":
            return to_d(M[space] @ (rig.rest[space].inverted() @ to_bl(rig.head[space] + Vector(t))))
        return to_d(Mroot @ to_bl(Vector(t)))
    pole = V(0.15 * sx, 0, 1) if legs else V(0.6 * sx, -0.6, -0.5)
    if "pole." + limb in chs:
        pole = Vector(chs["pole." + limb])
    layers = chs.get("iklayers." + limb)
    if layers:
        t_world, w, pl = None, 0.0, None
        for t, space, wi, pi in layers:
            if wi <= 1e-4:
                continue
            tw = world(t, space)
            if t_world is None:
                t_world, w, pl = tw, wi, (pi if pi is not None else pole)
            else:
                t_world = t_world.lerp(tw, wi); w = 1 - (1 - w) * (1 - wi)
                if pi is not None:
                    pl = pl.lerp(pi, wi)
        if t_world is None:
            return
        pole = pl
    else:
        w = chs.get("ikw." + limb, 1.0)
        if w <= 1e-4:
            return
        t_world = world(chs[key], chs.get("ikspace." + limb, "root"))
    pole = to_d(Mroot.to_3x3() @ to_bl(pole))
    old = {n: [basis[n][0].copy(), basis[n][1].copy(), basis[n][2]] for n in (up, lo, end)}
    ik2(rig, basis, M, up, lo, t_world, pole, legs)
    if legs:
        pitch = chs.get(f"foot{side}.pitch", 0.0)
        Rf = Mroot.to_3x3().normalized() @ rot_d((0, 1, 0), chs.get(f"foot{side}.ry", 0.0)) @ rot_d((1, 0, 0), pitch) @ rig.rest3[end]
        rig.set_world_rot(basis, M, end, Rf)
    if w < 0.9999:
        for n in (up, lo, end):
            basis[n][0] = old[n][0].slerp(basis[n][0], w)
        rig.fk(basis, M)


def aim_prop(rig, basis, M, bone, want_root_d, hand="handR"):
    """Turn the hand (minimal rotation) so the prop bone points along want (design, root space)."""
    Mroot = M["root"] @ rig.rest["root"].inverted()
    want = (Mroot.to_3x3() @ (C @ Vector(want_root_d))).normalized()
    ax = rig.prop_axis.get(bone, Vector((0, 1, 0)))
    cur = (M[bone].to_3x3().normalized() @ ax).normalized()
    Rd = cur.rotation_difference(want).to_matrix()
    Rh = M[hand].to_3x3().normalized()
    rig.set_world_rot(basis, M, hand, Rd @ Rh)


def staff_solve(rig, basis, M, chs):
    """Moses's staff solver, used for the brother's hoe: blade edge (hoeTip) at chs['staff.foot'] (root space),
    handle along chs['staff.dir'] (from the blade up toward the grip): iterate the right wrist target until the blade
    edge is there. Without staff.foot the hoe follows the hand (aim.hoe turns the hand so the handle points along it)."""
    if rig.staff_foot is None:
        return
    if "staff.foot" not in chs:
        if "ik.armR" in chs:
            ik_limb(rig, basis, M, chs, "armR")
        if "staff.aim" in chs:
            aim_prop(rig, basis, M, rig.pole, chs["staff.aim"])
        return
    Mroot = M["root"] @ rig.rest["root"].inverted()
    foot = Vector(chs["staff.foot"]); d = Vector(chs["staff.dir"]).normalized()
    want = to_d(Mroot @ to_bl(foot))
    target = Vector(chs["ik.armR"]) if "ik.armR" in chs else foot + d * (rig.staff_len + 0.004) + V(0.008, 0.004, -0.006)
    ch2 = {"ikspace.armR": "root", "ikw.armR": 1.0, "pole.armR": chs.get("pole.armR", V(-0.7, -0.5, -0.6))}
    for _ in range(10):
        ch2["ik.armR"] = target
        ik_limb(rig, basis, M, ch2, "armR")
        aim_prop(rig, basis, M, rig.pole, -d)
        err = rig.foot_of_staff(M) - want
        if err.length < 2e-5:
            break
        target = target - (CI @ (Mroot.to_3x3().inverted() @ (C @ err)))
    chs["ik.armR"] = target


def evaluate_primary(rig, clip_, f):
    chs = clip_.fn(rig, f, clip_.N)
    basis = rig.basis_from(chs)
    M = rig.fk(basis)
    for limb in ("legL", "legR"):
        ik_limb(rig, basis, M, chs, limb)
    late = []
    for limb in ("armL", "armR"):
        if limb == "armR" and rig.staff_foot is not None:
            continue                                    # the brother's right arm: solved with the hoe below
        if chs.get("ikspace." + limb, "root") in HAND_SPACES or \
                any(L[1] in HAND_SPACES and L[2] > 1e-4 for L in chs.get("iklayers." + limb, [])):
            late.append(limb); continue
        ik_limb(rig, basis, M, chs, limb)
    staff_solve(rig, basis, M, chs)
    for limb in late:
        ik_limb(rig, basis, M, chs, limb)
    for k in [k for k in chs if k.startswith("aim.")]:
        bone = k[4:]
        if bone in rig.names:
            aim_prop(rig, basis, M, bone, chs[k], hand=rig.parent[bone])
    # keep hand channel rotations relative to the IK'd forearm: re-apply the keyed hand twist/bend after IK
    return chs, basis, M


CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    # (a clip can scale the gravity weight per frame with the channel `hang.<bone>`, e.g. the hitched robe in `run`)
    "son": [(("purse",), 55.0, 3.6, 0.75, 75.0),
            (("robeL",), 80.0, 7.0, 0.25, 22.0), (("robeR",), 80.0, 7.0, 0.25, 22.0)],
    "father": [(("beard1", "beard2"), 85.0, 8.0, 0.25, 22.0),
               (("cloakL",), 70.0, 6.5, 0.22, 18.0), (("cloakR",), 70.0, 6.5, 0.22, 18.0),
               (("headcloth",), 80.0, 7.0, 0.25, 20.0), (("purse",), 55.0, 3.6, 0.75, 75.0)],
    "brother": [(("headcloth",), 85.0, 7.5, 0.25, 22.0)],
}


def sim_chains(rig, prim, loop):
    """Damped spring chains. Mutates prim[f] basis/M. Loops: 3 cycles, keep the last, spread the residual over the
    cycle so frame N == frame 0."""
    N = len(prim) - 1
    for names, k, cdamp, gw, lim in CHAINS[rig.ch]:
        if any(n not in rig.names for n in names):
            continue
        seq = (list(range(N)) * 3 + [N]) if loop else list(range(N + 1))
        state = {}
        out = {n: [None] * (N + 1) for n in names}
        sub = 4
        dt = 1.0 / FPS / sub
        for idx, fr in enumerate(seq):
            chs, basis, M = prim[fr]
            Mroot3 = (M["root"] @ rig.rest["root"].inverted()).to_3x3().normalized()
            for n in names:
                Cm = rig.carried(M, n).to_3x3().normalized()
                cur_c = (Cm @ basis[n][0].to_matrix()).col[1].normalized()
                rest_w = (Mroot3 @ rig.rest3[n].col[1]).normalized()
                gwf = gw * chs.get("hang." + n, 1.0)
                tgt = cur_c.slerp(rest_w, gwf) if gwf > 0 else cur_c
                wv = chs.get("wind." + n)
                if wv is not None and Vector(wv).length > 1e-5:
                    ww = (Mroot3 @ (C @ Vector(wv).normalized())).normalized()
                    tgt = tgt.slerp(ww, min(0.9, Vector(wv).length))
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
        if loop:
            for n in names:
                d0, dN = out[n][0], out[n][N]
                Rfull = dN.rotation_difference(d0)
                for fr in range(N + 1):
                    qi = Quaternion().slerp(Rfull, fr / N)
                    out[n][fr] = (qi.to_matrix() @ out[n][fr]).normalized()
            for fr in range(N + 1):
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
    sim_chains(rig, prim, clip_.loop)
    if clip_.loop:
        # exact seam: frame N's basis = frame 0's after the chains are closed
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
        pm = act.pose_markers.new(mname); pm.frame = int(round(mf))
    return act


# =============================================================================================== scene helpers
def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    for ch in CHARS:
        bpy.data.objects[f"{ch}_rig"].location = (0, 0, 0)
    bpy.context.view_layer.update()
    rigs = {ch: Rig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    return sc, rigs


def contract_clips():
    return {"son": ["idle", "walk", "talk", "laze", "ask_money", "wave_bye", "strut", "toss_coins", "party_dance",
                    "empty_pockets", "sad_idle", "sad_walk", "feed_pigs", "hungry_look", "sit_sad", "idea_stand",
                    "practise", "walk_tired", "hug", "sorry_head", "amazed", "dance", "wave"],
            "father": ["idle", "walk", "talk", "sad_give", "wave_sad", "look_far", "see_son", "run", "hug",
                       "call_servants", "feast_cheer", "dance", "plead", "arm_out"],
            "brother": ["idle", "walk_hoe", "talk", "work_field", "shake_head", "listen_music", "stomp_cross",
                        "complain", "soften", "take_hand"]}


def timeline_clips():
    return sorted({(a["who"], a["clip"]) for a in TL["acting"]})


def mesh_points(rig, step_n=3000, skip_props=()):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in rig.obj.children:
        if o.type != 'MESH' or o.name.endswith("_eyelids") or o.name in skip_props:
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = rig.obj.matrix_world.inverted() @ o.matrix_world
        n = len(me.vertices)
        step = max(1, n // step_n)
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


PROPS = ("purse", "robe", "robeL", "robeR", "ring", "hoe")


def prop_shown(cl, p, f=None):
    """Is prop p shown in clip cl (at frame f)? clip.props + per-frame windows (the timeline's prop events)."""
    if p not in cl.props:
        return False
    if f is None or p not in cl.prop_win:
        return True
    a, b = cl.prop_win[p]
    return a <= f <= b


def hidden_props(rig, cl, f=None):
    """Prop meshes not shown in this clip (at frame f): left out of the checks and the renders."""
    out = []
    for p in PROPS:
        nm = f"{rig.ch}_{p}"
        if nm in bpy.data.objects and not prop_shown(cl, p, f):
            out.append(nm)
    return out


def clip_checks(rig, cl, frames):
    out = {}
    ad = rig.obj.animation_data
    keep = ad.action if ad else None
    if ad:
        ad.action = None
    loc0, rot0 = rig.obj.location.copy(), rig.obj.rotation_euler.copy()
    rig.obj.location = (0, 0, 0); rig.obj.rotation_euler = (0, 0, 0)
    step = 3 if cl.N <= 60 else 5
    lows, blows = [], []
    low_at = None
    props_all = [f"{rig.ch}_{p}" for p in PROPS]
    for fr in sorted(set(list(range(0, cl.N + 1, step)) + [cl.N])):
        apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
        pts = mesh_points(rig, skip_props=hidden_props(rig, cl, fr))
        lp = min(pts, key=lambda q: q[0].y)
        lows.append(lp[0].y)
        if lp[0].y <= min(lows):
            low_at = [fr, lp[1], [round(v, 3) for v in lp[0]]]
        body = [q for q in pts if q[1] not in props_all]
        blows.append(min(q[0].y for q in body))
    out["meshMinY"] = round(min(lows), 4)
    if min(lows) < -0.004:
        out["meshMinAt"] = low_at
    nat = cl.natural_speed
    if nat is None:
        drift = 0.0
        for side in "LR":
            ref = None
            for basis, M in frames:
                p = rig.pos(M, "toe" + side)
                if p.y < 0.012 and rig.pos(M, "foot" + side).y < 0.03:
                    if ref is None:
                        ref = p
                    drift = max(drift, math.hypot(p.x - ref.x, p.z - ref.z))
                else:
                    ref = None
        out["plantedToeDriftMax"] = round(drift, 4)
    else:
        out["naturalSpeed"] = round(nat, 4)
        if cl.speed:
            # foot slide vs. stride speed: while a toe is planted its WORLD position (root-space z + v t, the actor
            # carried forward at the natural speed) should stay put
            v = nat / FPS
            slip = 0.0
            for side in "LR":
                ref = None
                for fr, (basis, M) in enumerate(frames):
                    p = rig.pos(M, "toe" + side)
                    w = V(p.x, 0, p.z + v * fr)
                    if p.y < 0.010 and rig.pos(M, "foot" + side).y < 0.03:
                        if ref is None:
                            ref = w
                        slip = max(slip, (w - ref).length)
                    else:
                        ref = None
            out["stanceSlipMax"] = round(slip, 4)
    if rig.staff_foot is not None:
        ys = [rig.foot_of_staff(M).y for _, M in frames]
        out["hoeTipY"] = [round(min(ys), 4), round(max(ys), 4)]          # blade edge height (0 = on the page)
    tails = lambda M: [rig.pos(M, n, "tail") for n in rig.names]
    if cl.loop:
        P0, P1, PN1, PN = tails(frames[0][1]), tails(frames[1][1]), tails(frames[-2][1]), tails(frames[-1][1])
        out["loopSeamVelErr"] = round(max(((P1[i] - P0[i]) - (PN[i] - PN1[i])).length for i in range(len(P0))), 5)
    else:
        PA, PB = tails(frames[-2][1]), tails(frames[-1][1])
        out["endVelMax"] = round(max((PB[i] - PA[i]).length for i in range(len(PA))), 5)
    reset_pose(rig)
    rig.obj.location, rig.obj.rotation_euler = loc0, rot0
    if ad:
        ad.action = keep
    return out


SAMPLE_BONES = ("head", "jaw", "handR", "handL", "footL", "toeR", "hips", "beard2", "cloakL", "headcloth", "purse",
                "robeL", "hoe", "hoeTip")


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    req = TL.get("requestedClips") or []
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl, "requestedClips": req,
            "stage": {"sitSadHip": [round(v, 4) for v in S_SIT_HIP],
                      "sitSadNote": "son sit_sad / idea_stand frame 0: sitting on the page, knees up (no seat needed)",
                      "hugDistance": 0.10, "hugNote": "father hug + son hug: actors 0.10 apart facing each other; the "
                      "rock is the same 3 s sine, both sway to the same side of the stage",
                      "armOutWrist": [round(v, 4) for v in ARM_OUT],
                      "takeHandNote": "brother take_hand meets father arm_out when they stand 0.10-0.12 apart",
                      "partyBeatFrames": 13.5, "feastBeatFrames": 16.5},
            "propWindows": {"son_ask_money": "purse shown only in the held end pose (it lands there at 22.18 s)",
                            "son_empty_pockets": f"purse until frame {DROP_F} (2.6 s, drop)",
                            "father_sad_give": f"purse until frame {FA_GIVE} (2.2 s, give)",
                            "son_amazed/dance/wave": "robe + robeL + robeR + ring"}}
    only = os.environ.get("PR_ONLY")
    only_ch = [c for c in os.environ.get("PR_CHARS", "").split(",") if c]
    for cl in CLIPS:
        if only and not any(cl.action.startswith(o) for o in only.split(",")):
            continue
        rig = rigs[cl.ch]
        frames = bake_clip(rig, cl)
        write_action(rig, cl, frames)
        seam = None
        if cl.loop:
            M0, MN = frames[0][1], frames[-1][1]
            seam = max((rig.pos(M0, n, "tail") - rig.pos(MN, n, "tail")).length for n in rig.names)
        rootmax = max(rig.pos(M, "root").length for _, M in frames)
        info = {"action": cl.action, "char": cl.ch, "clip": cl.name, "frames": cl.N, "seconds": round(cl.N * cl.timescale / FPS, 4),
                "loop": cl.loop, "rootMotion": False,
                "markers": {k: {"frame": v, "sec": round(v * cl.timescale / FPS, 4)} for k, v in cl.markers.items()},
                "loopSeamMaxErr": None if seam is None else round(seam, 6), "rootMaxOffset": round(rootmax, 5),
                "props": cl.props, "notes": cl.notes}
        if cl.extra:
            info["extra"] = True
        if cl.natural_speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            if cl.speed:
                info["stride"] = cl.speed[0]
        if cl.timescale != 1.0:
            info["timeScale"] = round(cl.timescale, 6)
            info["designFrames"] = cl.N
        if cl.prop_win:
            info["propWindows"] = {k: list(v) for k, v in cl.prop_win.items()}
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        print("PR_CHECK", cl.action, json.dumps(info["checks"]))
        meta["clips"].append(info)
        print(f"PR_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} root={info['rootMaxOffset']}")
    if only:
        print("PR_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "pr_anim.blend")
    bpy.ops.wm.save_as_mainfile(filepath=tmp_blend, compress=True)
    for ch in CHARS:
        if only_ch and ch not in only_ch:
            continue
        bpy.ops.wm.open_mainfile(filepath=tmp_blend)
        rig = bpy.data.objects[f"{ch}_rig"]
        for o in list(bpy.data.objects):
            if (o.type == 'CAMERA') or (not o.name.startswith(ch + "_")):
                bpy.data.objects.remove(o, do_unlink=True)
        for a in list(bpy.data.actions):
            if not a.name.startswith(ch + "_"):
                bpy.data.actions.remove(a)
        rig.location = (0, 0, 0); rig.rotation_euler = (0, 0, 0)
        rig.animation_data_create()
        rig.animation_data.action = None
        for a in sorted(bpy.data.actions, key=lambda a: a.name):
            tr = rig.animation_data.nla_tracks.new(); tr.name = a.name
            st = tr.strips.new(a.name, 0, a); st.name = a.name
            tr.mute = True
        for o in rig.children:
            if o.type == 'MESH':
                fix_uv_order(o)
        bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        for o in rig.children:
            o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.gltf(filepath=os.path.join(ANIM, f"{ch}.glb"), use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=True,
                                  export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_frame_step=1,
                                  export_def_bones=False, export_texcoords=True, export_materials='EXPORT', export_morph=False,
                                  export_optimize_animation_size=False, export_anim_slide_to_zero=False,
                                  export_rest_position_armature=True, export_negative_frame='CROP')
        patch_timescale(os.path.join(ANIM, f"{ch}.glb"), {c.action: c.timescale for c in CLIPS if c.ch == ch and c.timescale != 1.0})
        print("PR_EXPORT", ch)
    os.remove(tmp_blend)
    if only_ch:
        old = json.load(open(os.path.join(ANIM, "clips.json")))
        meta["clips"] = [c for c in old["clips"] if c["char"] not in only_ch] + meta["clips"]
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("PR_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


def patch_timescale(path, scales):
    """Stretch the keyframe times of the named animations in a GLB by their factor (new time accessors appended to
    the binary chunk, so an accessor shared with another animation is never touched)."""
    import struct
    if not scales:
        return
    b = open(path, "rb").read()
    l0 = struct.unpack_from("<I", b, 12)[0]
    j = json.loads(b[20:20 + l0])
    l1 = struct.unpack_from("<I", b, 20 + l0)[0]
    bin_ = bytearray(b[20 + l0 + 8:20 + l0 + 8 + l1])
    done = []
    for a in j["animations"]:
        k = scales.get(a["name"])
        if not k:
            continue
        remap = {}
        for s in a["samplers"]:
            ai = s["input"]
            if ai not in remap:
                acc = j["accessors"][ai]; bv = j["bufferViews"][acc["bufferView"]]
                off = bv.get("byteOffset", 0) + acc.get("byteOffset", 0)
                vals = [struct.unpack_from("<f", bin_, off + 4 * i)[0] * k for i in range(acc["count"])]
                while len(bin_) % 4:
                    bin_.append(0)
                nb = len(bin_)
                bin_ += struct.pack("<%df" % len(vals), *vals)
                j["bufferViews"].append({"buffer": 0, "byteOffset": nb, "byteLength": 4 * len(vals)})
                na = dict(acc); na["bufferView"] = len(j["bufferViews"]) - 1; na.pop("byteOffset", None)
                na["min"] = [min(vals)]; na["max"] = [max(vals)]
                j["accessors"].append(na); remap[ai] = len(j["accessors"]) - 1
            s["input"] = remap[ai]
        done.append((a["name"], round(k, 6)))
    while len(bin_) % 4:
        bin_.append(0)
    j["buffers"][0]["byteLength"] = len(bin_)
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + 8 + len(bin_)) + struct.pack("<II", len(js), 0x4E4F534A) + js \
        + struct.pack("<II", len(bin_), 0x004E4942) + bytes(bin_)
    open(path, "wb").write(out)
    print("PR_TIMESCALE", os.path.basename(path), done)


def fix_uv_order(o):
    """Page UVs must be the FIRST UV map (glTF TEXCOORD_0, 0..1) and the face decal the SECOND (TEXCOORD_1), as in
    David & Goliath / Esther's fix. Rebuild the layers in that order if they are not (page found by name, else range)."""
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
                          "uv0InUnitSquare": uv0_ok}
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
            ts = info.get("timeScale", 1.0)
            for fr, bones in info["samples"].items():
                x = int(fr) * ts
                bpy.context.scene.frame_set(int(x), subframe=x - int(x))
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
            print(f"PR_VERIFY {ch} {nm} {a['frames']}f {a['seconds']}s ch={a['channels']} sampleErr={out['sampleErr'][ch].get(nm)}")
        g = out["glb"][ch]
        print(f"PR_VERIFY_GLB {ch} bytes={g['bytes']} skins={g['skins']} meshes={g['meshes']} "
              f"uv0InUnitSquare={g['uv0InUnitSquare']} uv={json.dumps(g['uv'])}")
        print(f"PR_VERIFY_NODES {ch} {[n for n in g['nodes'] if n and n.split('_')[-1] in PROPS + ('eyelids',) or n in PROPS]}")
    print("PR_VERIFY_MISSING", json.dumps(out["contractMissing"]))


# ----------------------------------------------------------------------------------------------- render helpers
REGIONS = json.load(open(os.path.join(MODEL, "regions_characters.json")))
FACES = {ch: {"default": REGIONS["characters"][ch]["faceDecal"]["default"],
              "clips": REGIONS["characters"][ch]["faceDecal"].get("clipExpression", {})} for ch in CHARS}
if os.path.exists(FACES_JSON):                 # Integration's faces.json wins when it exists
    try:
        _fj = json.load(open(FACES_JSON))
        for ch in CHARS:
            if ch in _fj and "clips" in _fj[ch]:
                FACES[ch] = _fj[ch]
    except Exception:
        pass
DECAL_NODES = {}
SET_OBJS = []
SET_CLIPS = set()          # all clips render on a plain floor (PR_SET=1 shows the homeland set in probes)


def show_set(on):
    for o in SET_OBJS:
        if o.get("_hid") is None:
            o["_hid"] = int(o.hide_render)
        o.hide_render = bool(o["_hid"]) or not on


def srgb_lin(c):
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def hex_rgb(h):
    h = h.lstrip("#"); return [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]


def char_material(ch):
    """Demo colours by face region (attribute st_region -> constant colour ramp) + face decal on UV 'decal'."""
    regs = REGIONS["characters"][ch]["regions"]
    m = bpy.data.materials.new(f"anim_{ch}"); m.use_nodes = True; nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = 0.75
    at = nt.nodes.new("ShaderNodeAttribute"); at.attribute_name = "st_region"; at.attribute_type = 'GEOMETRY'
    dv = nt.nodes.new("ShaderNodeMath"); dv.operation = 'DIVIDE'; dv.inputs[1].default_value = 64.0
    nt.links.new(at.outputs["Fac"], dv.inputs[0])
    ramp = nt.nodes.new("ShaderNodeValToRGB"); ramp.color_ramp.interpolation = 'CONSTANT'
    els = ramp.color_ramp.elements
    items = sorted((r["id"], r.get("hex", "#cccccc")) for r in regs.values() if "id" in r)
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
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    nt.links.new(dt.outputs["Alpha"], mix.inputs["Factor"])
    nt.links.new(col, mix.inputs[6]); nt.links.new(dt.outputs["Color"], mix.inputs[7])
    nt.links.new(mix.outputs[2], bsdf.inputs["Base Color"])
    DECAL_NODES[ch] = dt
    return m


def set_expression(ch, clip_name):
    expr = FACES[ch]["clips"].get(clip_name, FACES[ch]["default"])
    p = os.path.join(FACE_DIR, f"{ch}_{expr}.png")
    if not os.path.exists(p):
        p = os.path.join(FACE_DIR, f"{ch}_{FACES[ch]['default']}.png")
    DECAL_NODES[ch].image = bpy.data.images.load(p, check_existing=True)


def setup_look(sc, res, samples=12, stage=True):
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = samples
    except Exception:
        pass
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = -0.1
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    sc.world = bpy.data.worlds.new("W"); sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.86, 0.84, 0.80, 1); bg.inputs[1].default_value = 0.9
    sc.world.color = (0.86, 0.84, 0.80)
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 2.8; sun.data.angle = math.radians(5)
    sun.rotation_euler = (math.radians(40), math.radians(-12), math.radians(-28))
    for o in list(bpy.data.objects):
        if o.type == 'CAMERA':
            bpy.data.objects.remove(o, do_unlink=True)
    for ch in CHARS:
        m = char_material(ch)
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name.startswith(ch + "_"):
                o.data.materials.clear(); o.data.materials.append(m)
    me = bpy.data.meshes.new("floor")
    R_ = 4.0
    vs = [(-R_, -R_, -0.0005), (R_, -R_, -0.0005), (R_, R_, -0.0005), (-R_, R_, -0.0005), (-R_, -R_, R_), (R_, -R_, R_), (R_, R_, R_), (-R_, R_, R_)]
    me.from_pydata(vs, [], [(0, 1, 2, 3), (3, 2, 6, 7), (0, 4, 5, 1), (1, 5, 6, 2), (0, 3, 7, 4)])
    fo = bpy.data.objects.new("floor", me); sc.collection.objects.link(fo)
    fm = bpy.data.materials.new("floor"); fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.82, 0.74, 0.58, 1); me.materials.append(fm)
    if stage and os.path.exists(SET_GLB) and os.environ.get("PR_SET") == "1":
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=SET_GLB)
        new = [o for o in bpy.data.objects if o not in before]
        SET_OBJS[:] = [o for o in new if o.type == 'MESH']
        pm = bpy.data.materials.new("anim_set"); pm.use_nodes = True
        b2 = pm.node_tree.nodes.get("Principled BSDF"); b2.inputs["Roughness"].default_value = 0.9
        b2.inputs["Base Color"].default_value = (0.80, 0.70, 0.52, 1)
        hide = {"feast", "lamps"}
        for o in new:
            if o.type == 'MESH':
                for i in range(len(o.material_slots)):
                    o.material_slots[i].material = pm
            q = o
            while q is not None:
                if q.name.split(".")[0] in hide:
                    o.hide_render = True; break
                q = q.parent
            o.select_set(False)


def camera(sc):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.clip_start = 0.005; cam.data.clip_end = 50
    return cam


def look(cam, target_d, cam_d, lens=40):
    cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.location = to_bl(cam_d)
    cam.rotation_euler = (to_bl(target_d) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def place_rig(rig, x, z, yaw_deg, y=0.0):
    rig.obj.location = to_bl(V(x, y, z))
    rig.obj.rotation_euler = (0, 0, math.radians(yaw_deg))


def show_only(rigs, chs, cl_of=None, fr_of=None):
    for ch, r_ in rigs.items():
        vis = ch in chs
        r_.obj.hide_render = not vis
        hid = hidden_props(r_, cl_of[ch], (fr_of or {}).get(ch)) if (cl_of and ch in cl_of) else []
        for o in r_.obj.children:
            o.hide_render = (not vis) or (o.name in hid)


MARKS = {"son": (0.0, 0.0, 0.0), "father": (0.0, 0.0, 0.0), "brother": (0.0, 0.0, 0.0)}   # plain floor
CLIP_MARKS = {}


def stage_of(cl):
    show_set(cl.action in SET_CLIPS or os.environ.get("PR_SET") == "1")
    return CLIP_MARKS.get(cl.action, MARKS[cl.ch])


def view_cam(cam, rig, mark, view, bone=None, dist_k=2.3, H=None):
    x, z, yaw0 = mark
    H = H or rig.H
    yaw = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "top": 25, "low": 25}[view] + yaw0
    tgt = V(x, H * float(os.environ.get("PR_TGT_K", "0.55")), z); dist = H * dist_k; hgt = H * 0.62
    if bone:
        tgt = to_d(rig.obj.matrix_world @ rig.obj.pose.bones[bone].head); dist = H * 0.9; hgt = tgt.y + 0.02
    if view == "top":
        hgt = dist * 1.3
    if view == "low":
        hgt = 0.02
    a_ = math.radians(yaw)
    look(cam, tgt, V(tgt.x + math.sin(a_) * dist, hgt, tgt.z + math.cos(a_) * dist))


PAIRS = [  # contact-sheet pair rows: (A action, B action, distance, label, [(frame A, frame B), ...])
    ("father_hug", "son_hug", 0.102, "pair: father hug + son hug (S09, 0.10)", [(0, 0), (22, 22), (45, 45)]),
    ("father_hug", "son_sorry_head", 0.102, "pair: father hug + son sorry_head (S10)", [(30, 20), (60, 60)]),
    ("father_sad_give", "son_ask_money", 0.089, "pair: sad_give + ask_money (S02, 0.089)", [(30, 95), (64, 95), (119, 96)]),
    ("father_arm_out", "brother_take_hand", 0.12, "pair: arm_out + take_hand (0.12; S13 timeline has 0.10)", [(44, 20), (44, 52), (44, 65)]),
    ("father_dance", "son_dance", 0.102, "pair: father dance + son dance (S11, 0.10)", [(0, 0), (16, 16), (33, 33)]),
]


def place_pair(rigs, ra, rb, dist, cx=-0.10, cz=0.08):
    show_set(False)
    """A at (cx - d/2, cz) facing +x (yaw +90), B at (cx + d/2, cz) facing -x: they face each other."""
    place_rig(ra, cx - dist / 2, cz, 90.0); place_rig(rb, cx + dist / 2, cz, -90.0)


def mode_contact():
    sc, rigs = open_scene()
    setup_look(sc, (380, 380), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    clips = {c.action: c for c in CLIPS}
    baked = {}
    for cl in CLIPS:
        rig = rigs[cl.ch]
        set_expression(cl.ch, cl.name)
        frames = bake_clip(rig, cl); baked[cl.action] = frames
        mk = sorted(set(int(round(v)) for v in cl.markers.values()))
        if len(mk) > 4:
            mk = []                     # many beat markers (dance hits): show the motion between them instead
        picks = sorted(set([0, cl.N] + [int(round(cl.N * k / 5)) for k in range(1, 5)] + mk))
        while len(picks) > 7:
            cand = [p for p in picks if p not in mk and p not in (0, cl.N)] or [p for p in picks if p not in (0, cl.N)]
            picks.remove(cand[len(cand) // 2])
        mark = stage_of(cl)
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": [], "extra": cl.extra,
               "seconds": cl.N * cl.timescale / FPS}
        for fr in picks:
            show_only(rigs, [cl.ch], {cl.ch: cl}, {cl.ch: fr})
            apply_basis(rig, frames[fr][0])
            place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, "q3", dist_k=1.4)
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if int(round(v)) == fr)})
        reset_pose(rig)
        rows.append(row)
        print("PR_CONTACT_ROW", cl.action, picks, flush=True)
    for a, b, dist, label, fpairs in PAIRS:
        ca, cb = clips[a], clips[b]
        ra, rb = rigs[ca.ch], rigs[cb.ch]
        set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
        row = {"action": label, "loop": ca.loop, "frames_total": ca.N, "frames": []}
        for i, (fa, fb) in enumerate(fpairs):
            show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb}, {ca.ch: fa, cb.ch: fb})
            apply_basis(ra, baked[a][fa][0]); apply_basis(rb, baked[b][fb][0])
            place_pair(rigs, ra, rb, dist)
            bpy.context.view_layer.update()
            for vn, cpos in (("front", V(-0.10, 0.20, 0.08 + 0.55)), ("q3", V(-0.10 + 0.40, 0.30, 0.08 + 0.40)),
                             ("back", V(-0.10 - 0.05, 0.26, 0.08 - 0.50))):
                if i > 0 and vn == "back":
                    continue
                look(cam, V(-0.10, 0.17, 0.08), cpos, lens=45)
                fn = f"pair_{a}_{b}_{fa:03d}_{fb:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                row["frames"].append({"f": fa, "file": fn, "marker": vn})
        reset_pose(ra); reset_pose(rb)
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """PR_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'pair:<actionA>:<actionB>:<dist>:<frame>[:view]' renders two actors facing each other at that distance."""
    sc, rigs = open_scene()
    res = int(os.environ.get("PR_PROBE_RES", "440"))
    setup_look(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    clips = {cl.action: cl for cl in CLIPS}
    baked = {}
    out = []

    def bk(a):
        if a not in baked:
            baked[a] = bake_clip(rigs[clips[a].ch], clips[a])
        return baked[a]
    for item in os.environ.get("PR_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "pair":
            a, b, dist, fr = parts[1], parts[2], float(parts[3]), int(parts[4])
            views = parts[5].split(",") if len(parts) > 5 else ["front", "q3", "top", "back"]
            ca, cb = clips[a], clips[b]
            ra, rb = rigs[ca.ch], rigs[cb.ch]
            show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
            set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
            apply_basis(ra, bk(a)[min(fr, ca.N)][0]); apply_basis(rb, bk(b)[min(fr, cb.N)][0])
            place_pair(rigs, ra, rb, dist)
            bpy.context.view_layer.update()
            T = V(-0.10, 0.18, 0.08)
            cams = {"front": V(-0.10, 0.20, 0.08 + 0.50), "q3": V(-0.10 + 0.36, 0.28, 0.08 + 0.36),
                    "top": V(-0.10, 0.62, 0.08 + 0.22), "back": V(-0.10, 0.22, 0.08 - 0.50),
                    "sideA": V(-0.10 - 0.45, 0.22, 0.10), "close": V(-0.10, 0.24, 0.08 + 0.26)}
            for vn in views:
                look(cam, T, cams[vn], lens=45)
                fn = f"pair_{a}_{b}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True); out.append(fn)
            reset_pose(ra); reset_pose(rb)
            continue
        action, frames, view = parts[0], parts[1], parts[2] if len(parts) > 2 else "q3"
        bone = None
        if "#" in view:
            view, bone = view.split("#")
        cl = clips[action]; rig = rigs[cl.ch]
        show_only(rigs, [cl.ch], {cl.ch: cl})
        set_expression(cl.ch, cl.name)
        fr_ = bk(action)
        mark = stage_of(cl)
        for fr in [int(v) for v in frames.split(",")]:
            fr = min(fr, cl.N)
            show_only(rigs, [cl.ch], {cl.ch: cl}, {cl.ch: fr})
            apply_basis(rig, fr_[fr][0]); place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, view, bone, dist_k=float(os.environ.get("PR_PROBE_DIST", "1.25")))
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("PR_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("PR_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()

