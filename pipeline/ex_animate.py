"""Exodus skeletal animation (Animation role, story pack #5).

Copied from pipeline/ru_animate.py (Ruth) and adapted. Two halves in one file:

* Under Blender (headless) it opens `assets/exodus/model/characters.blend` (Characters role's rigs), builds every clip of
  docs/exodus/CONTRACT.md §4 (+ extras) as an action `<char>_<clip>` and exports
  `assets/exodus/anim/{moses,pharaoh,miriam}.glb` (character + skin + one glTF animation per action) and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/ex_animate.py all        # build + verify + contact sheet
    python3 pipeline/ex_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/ex_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/ex_animate.py contact    # anim/contact_sheet.png (key poses per clip, in Egypt)
    EX_PROBE="moses_walk_staff:0,11:side" python3 pipeline/ex_animate.py probe     # work renders ($EX_ANIM_WORK/probe.png)
    EX_ONLY=moses_idle,pharaoh_ride  (with build: bake + check a subset, no export)

Method as Ruth (see docs/exodus/ANIMATION.md §6): clip functions frame -> channels in design axes, Catmull-Rom keys,
leg / arm IK, Moses's staff solver (staff foot planted on the page), damped spring chains for beard, mantle, nemes
lappets, scarf and braid (+ per-bone wind), irregular blinks, syllable jaw rhythms. New here: the chariot as a rigid
bone tipped about a pivot (`chariot_xf`), and time-scaled clips (`timescale`: the GLB times of tambourine_dance and
moses_clap are stretched so the loops are exactly whole bars of the `song` cue).
Intermediates: $EX_ANIM_WORK (default /tmp/ex_anim_work).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
EX = os.path.join(ROOT, "assets/exodus")
MODEL = os.path.join(EX, "model")
ANIM = os.path.join(EX, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
SET_GLB = os.path.join(MODEL, "egypt.glb")
TIMELINE = os.path.join(EX, "timeline.json")
FACES_JSON = os.path.join(EX, "faces.json")
FACE_DIR = os.path.join(ROOT, "docs/exodus/design/faces")
WORK = os.environ.get("EX_ANIM_WORK") or "/tmp/ex_anim_work"
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FPS = 30
CHARS = ("moses", "pharaoh", "miriam")

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
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith(("EX_", "Traceback", "Error", "  File")) or "Error" in ln]
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
    d.text((pad, 14), "Exodus - key poses per clip (30 fps; frame / seconds; marker names in red; * = extra clip; "
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
    sheet = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT) if os.environ.get("EX_QUANT", "0") == "1" else sheet
    sheet.save(out, optimize=True)
    print("EX_CONTACT", out, sheet.size)


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get("EX_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("EX_PROBE_OUT", "probe.png"))
    sheet.save(out); print("EX_PROBE_SHEET", out)


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
    H_OF = {"moses": 0.37, "pharaoh": 0.39, "miriam": 0.34}

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
        if "staff" in self.names:
            # the staff's foot (lowest vertex of naomi_staff in the rest pose) in the staff bone's local frame
            o = bpy.data.objects.get(f"{ch}_staff")
            mw = obj.matrix_world.inverted() @ o.matrix_world
            low = min((mw @ v.co for v in o.data.vertices), key=lambda p: p.z)
            self.staff_foot = self.rest["staff"].inverted() @ low
            self.staff_len = (to_d(low) - self.head["staff"]).length
        # prop axis (bone-local): from the bone head to the mesh centroid (the stalk ears point this way)
        self.prop_axis = {}
        self.prop_cen = {}
        for b in ("tambourine",):
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
        return to_d(M["staff"] @ self.staff_foot)


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
                 natural=None, timescale=1.0):
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = markers or {}
        self.notes = notes
        self.extra = extra
        self.speed = speed           # (stride L, duty) for in-place locomotion -> natural speed
        self.props = props or []     # props this clip is posed for (shown in renders; Integration shows them by `prop`)
        self.backwards = backwards
        self.natural = natural       # explicit natural speed (u/s) for in-place locomotion without a gait (ride)
        self.timescale = timescale   # GLB times x this (whole bars of the song cue)

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


def gusts(f, seed=0.0):
    """Irregular 0..1 wind gust signal (sum of incommensurate sines)."""
    s = 0.55 + 0.25 * math.sin(f * 0.21 + seed) + 0.15 * math.sin(f * 0.47 + 1.3 * seed) + 0.08 * math.sin(f * 1.13 + 2.1)
    return min(1.0, max(0.0, s))


def loop_gusts(f, N, seed=0.0):
    """Seamless gusts for loops (integer cycles per loop)."""
    return 0.55 + 0.22 * wave(f, N, 2, 0.1 + seed) + 0.14 * wave(f, N, 5, 0.3 + seed) + 0.07 * wave(f, N, 11, 0.7)


def shiver(f, N, amp=1.0, loop=True):
    """Fast irregular trembling (soggy, cold): returns a -1..1-ish value, seamless for loops."""
    if loop:
        return amp * (0.6 * wave(f, N, int(N / 3.1), 0.0) + 0.4 * wave(f, N, int(N / 2.3), 0.37))
    return amp * (0.6 * math.sin(f * 2.03) + 0.4 * math.sin(f * 2.71 + 0.37))


# =============================================================================================== MOSES
# Rest: stooped (baked chest +8, neck +8, head -10, arms -8), right fist round the staff, staff vertical at his right
# side. Unless a clip says otherwise the staff stands on the page and the right wrist is solved to it
# (`staff.foot` + `staff.dir`, root space). Without staff.foot the staff simply follows the hand (optional staff.aim).
STAFF_SIDE = (V(-0.106, 0.0, 0.044), V(-0.03, 1.0, -0.10))           # beside him, top leaning in a little
STAFF_FRONT = (V(-0.056, 0.0, 0.084), V(0.03, 1.0, -0.17))           # in front-right: both hands on it
STAFF_KNEEL = (V(-0.080, 0.0, 0.040), V(-0.02, 1.0, -0.06))
SONG_K = 900.0 / (7 * 128)            # 128 design frames -> 4 bars of 6/8 at dotted quarter 112 (30/7 s)


def staff_at(c, foot, d, w=1.0):
    c["staff.foot"] = Vector(foot); c["staff.dir"] = Vector(d).normalized(); c["staff.w"] = w


def m_base(rig, f, N, cycles=1, amp=1.0, phase=0.0, staff=STAFF_SIDE):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.7 * b * amp; c["spine.rx"] = -0.7 * b * amp       # inhale lifts the stoop a little
    c["shoulderL.raise"] = 1.2 * b * amp; c["shoulderR.raise"] = 1.2 * b * amp
    c["neck.rx"] = 0.6 * b * amp; c["head.rx"] = -0.5 * b * amp
    c["upperArmL.raise"] = -24; c["upperArmL.bend"] = 8; c["forearmL.bend"] = 28; c["forearmL.twist"] = -12
    c["handL.bend"] = 6; fingers(c, "L", 26)
    if staff is not None:
        staff_at(c, *staff)
        c["pole.armR"] = V(-0.7, -0.5, -0.6)
    # beard: a slow breath-driven sway on top of the spring chain
    c["beard1.rz"] = 1.2 * wave(f, N, max(1, cycles), phase + 0.3)
    return c


def left_on_staff(c, rig, w=1.0, lift=0.0):
    """Left hand cupped over the right fist on the staff (target in staff space: rest staff is vertical)."""
    arm_ik(c, "L", V(0.010, 0.030 + lift, 0.006), V(0.9, -0.5, -0.3), "staff", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 26, w); c["handL.twist"] = -40 * w
    fingers(c, "L", lerp(c.get("fingersL.curl", 26), 58, w))


def m_mantle(c, f, N, amp=1.0, phase=0.0, loop=True):
    """A little keyed life in the mantle panels (the spring chain adds the follow-through)."""
    c["mantleL.rx"] = c.get("mantleL.rx", 0.0) + 1.5 * amp * wave(f, N, 1, phase)
    c["mantleR.rx"] = c.get("mantleR.rx", 0.0) + 1.5 * amp * wave(f, N, 1, phase + 0.4)


@clip("moses", "idle", 150, True, props=["staff"],
      notes="old shepherd at rest: both hands stacked on the staff planted in front of his right side, leaning a "
            "little weight on it; slow deep breaths (the stoop lifts on the inhale, one deeper sigh), weight shifts, a "
            "slow look round and back, a thoughtful beard-stroke with the left hand; bushy-browed slow blinks; beard "
            "and mantle sway late")
def moses_idle(rig, f, N):
    c = m_base(rig, f, N, cycles=3, amp=1.0, staff=STAFF_FRONT)
    sigh = K([(0, 0), (90, 0), (102, 1), (110, 1), (126, -0.4), (140, 0), (150, 0)], f, N, True)
    c["chest.rx"] += -3 * sigh; c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh
    sh = [(0, 0.3), (40, -0.7), (84, -0.7), (118, 0.6), (150, 0.3)]
    c["hips.tx"] = 0.003 * K(sh, f, N, True); c["hips.rz"] = -1.8 * K(sh, f, N, True)
    c["spine.rz"] = 1.1 * KL(sh, f, N, True, lag=8); c["chest.rz"] = 0.6 * KL(sh, f, N, True, lag=12)
    look = [(0, 0), (16, 0), (30, 1), (52, 1), (62, -0.5), (80, -0.5), (92, 0), (150, 0)]
    c["neck.ry"] = 6 * K(look, f, N, True); c["head.ry"] = 10 * KL(look, f, N, True, lag=4)
    c["head.rx"] += K([(0, 0), (30, -3), (52, -3), (62, 0), (150, 0)], f, N, True) + 2 * sigh
    c["head.rz"] = 2.0 * K([(0, 0.5), (60, -0.5), (120, 0.8), (150, 0.5)], f, N, True)
    # left hand on the staff; once it leaves to stroke the beard (f 22-58)
    stroke = ease_io((f - 22) / 8) * (1 - ease_io((f - 50) / 10))
    left_on_staff(c, rig, w=1 - stroke)
    if stroke > 0:
        down = 0.5 + 0.5 * math.cos(math.pi * (f - 26) / 9) if 26 <= f <= 50 else 1.0
        arm_ik(c, "L", V(0.010, 0.010 - 0.030 * (1 - down), 0.060), V(0.9, -0.6, -0.3), "chest", stroke)
        c["handL.bend"] = lerp(c["handL.bend"], -10, stroke); fingers(c, "L", lerp(c["fingersL.curl"], 40, stroke))
        c["head.rx"] += -4 * stroke; c["beard1.rx"] = 3 * stroke * (1 - down)
    blink(c, f, N, [12, 66, 72, 128], base=1.25, slow=1.5)
    stand_feet(rig, c, spread=0.003, pitchL=K([(0, 0), (40, 0), (52, 4), (86, 4), (98, 0), (150, 0)], f, N, True))
    m_mantle(c, f, N, 0.6)
    return c


M_WALK = (0.060, 0.62)


@clip("moses", "walk_staff", 44, True, markers={"contactL": 0, "contactR": 22, "staffPlant": 0}, speed=M_WALK,
      props=["staff"],
      notes="old but steady: unhurried 82 steps/min, slightly stooped, firm heel strikes; the staff swings forward "
            "with the left foot and is PLANTED with it (every other step) - it stays still on the page while the "
            "left foot is down, the arm pushing on it; free left arm swings a little; hip bob, head nods late; "
            "mantle panels swing with the legs, beard follows")
def moses_walk_staff(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.5, staff=None)
    g = gait(rig, f, N, L=M_WALK[0], lift=0.010, duty=M_WALK[1], heel=10, toeoff=18)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0045 + 0.0026 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -3.5 * math.sin(ph - 0.4); c["head.ry"] = 1.5 * math.sin(ph - 0.8)
    c["hips.rz"] = 2.6 * math.cos(ph); c["chest.rz"] = -1.4 * math.cos(ph - 0.6); c["head.rz"] = 0.8 * math.cos(ph - 1.0)
    c["spine.rx"] = 2; c["chest.rx"] += 1.5
    c["head.rx"] = -1 + 1.8 * math.cos(2 * ph - 1.3); c["neck.rx"] = 0.8 * math.cos(2 * ph - 0.9)
    c["upperArmL.bend"] = 8 - 12 * math.sin(ph - 0.3); c["forearmL.bend"] = 30 - 8 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 7 * math.sin(ph - 1.6)
    # staff: planted while the left foot is in stance (slides back with it = still on the page), swung forward
    footL = g["legL"]
    p = footL[3]
    base = V(-0.104, 0.0, 0.0)
    lead = 0.036
    if p < M_WALK[1]:
        foot = base + V(0, 0.0, footL[0].z - rig.head["footL"].z + lead)
    else:
        s = (p - M_WALK[1]) / (1 - M_WALK[1])
        foot = base + V(0, 0.020 * math.sin(math.pi * s), -M_WALK[0] / 2 + M_WALK[0] * smooth(s) + lead)
    grip = V(-0.098, 0.166 - 0.003 * math.cos(2 * ph), 0.026 + 0.006 * math.sin(ph))
    staff_at(c, foot, grip - foot)
    c["pole.armR"] = V(-0.7, -0.5, -0.6)
    c["mantleL.rx"] = 7 * math.sin(ph - 0.6); c["mantleR.rx"] = -7 * math.sin(ph - 0.6)
    c["mantleBack.rx"] = -3 + 2 * math.cos(2 * ph - 0.8)
    blink(c, f, N, [30], base=1.15)
    return c


@clip("moses", "talk", 96, True, props=["staff"],
      notes="talks plainly: staff planted at his right side, the left hand opens palm-up on the stressed syllables "
            "and once comes to his chest; nods on the beats, small head tilts; jaw in an irregular syllable rhythm "
            "(lip sync overrides it); blinks")
def moses_talk(rig, f, N):
    c = m_base(rig, f, N, cycles=2, amp=0.9)
    jk, beats = syllables(N, 61, amp=(5, 12), dur=(3.5, 7.0), gap=0.28)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=10)
    btl = beat_curve(beats, f - 3, N, width=11)
    c["head.rx"] += 3.0 * bt - 1.2 * wave(f, N, 1, 0.2); c["head.ry"] = 5 * wave(f, N, 1, 0.15) + 1.5 * wave(f, N, 3, 0.4)
    c["head.rz"] = 2.5 * wave(f, N, 1, 0.4)
    ph = K([(0, 0.3), (10, 0.9), (40, 1.0), (50, 0.2), (60, 0.0), (82, 0.0), (90, 0.4), (96, 0.3)], f, N, True)
    chest = K([(0, 0), (50, 0), (58, 1), (80, 1), (88, 0), (96, 0)], f, N, True)
    lift = ph * (0.7 + 0.3 * btl)
    c["upperArmL.raise"] = -24 + 4 * lift; c["upperArmL.bend"] = 8 + 36 * lift
    c["forearmL.bend"] = 28 + 50 * lift; c["forearmL.twist"] = -12 + 80 * lift
    c["handL.bend"] = 6 - 20 * btl * ph; fingers(c, "L", 30 - 22 * btl * ph)
    chest_hand(c, "L", V(0.022, -0.004, 0.058), chest)
    c["chest.ry"] = 4 * lift; c["chest.rx"] += 1.2 * bt
    blink(c, f, N, [12, 50, 79], base=1.15, slow=1.3)
    stand_feet(rig, c, spread=0.003)
    m_mantle(c, f, N)
    return c


@clip("moses", "look_curious", 120, True, props=["staff"],
      notes="peering at the burning bush: leans forward from the hips with the left hand shading his eyes (palm "
            "down over the brows), head pushed forward and tilting one way then the other, a slow 'hmm' nod, a "
            "small rise onto the toes to see better; staff planted at his side; slow curious blinks")
def moses_look_curious(rig, f, N):
    c = m_base(rig, f, N, cycles=2, amp=0.8)
    tilt = K([(0, -1), (24, -1), (40, 1), (66, 1), (82, -0.3), (100, -0.3), (120, -1)], f, N, True)
    peer = K([(0, 0.6), (30, 1.0), (60, 0.8), (90, 1.0), (120, 0.6)], f, N, True)
    toes = bump(f, 46, 74)
    c["hips.tz"] = 0.006 * peer; c["spine.rx"] = 6 + 4 * peer; c["chest.rx"] += 4 * peer
    c["neck.rx"] = -4 - 3 * peer; c["head.rx"] = -6 - 4 * peer + 3 * bump(f, 84, 100)
    c["head.rz"] = 9 * tilt; c["neck.ry"] = 3 * tilt; c["head.ry"] = 6 * KL([(0, -1), (24, -1), (40, 1), (66, 1), (82, -0.3), (100, -0.3), (120, -1)], f, N, True, lag=5)
    c["hips.ty"] = 0.005 * toes
    # left hand shading the eyes (palm down over the brows)
    arm_ik(c, "L", V(0.012, 0.088 + 0.002 * wave(f, N, 2), 0.080), V(1.0, -0.2, -0.3), "chest")
    c["handL.bend"] = -28; c["handL.twist"] = 70; fingers(c, "L", 8)
    blink(c, f, N, [20, 58, 104], base=1.0, slow=1.5)
    stand_feet(rig, c, spread=0.003, pitchL=-14 * toes, pitchR=-14 * toes, fwdL=0.010)
    m_mantle(c, f, N, 0.7)
    return c


@clip("moses", "startle", 36, False, props=["staff"], markers={"jump": 8},
      notes="God calls his name: a sharp intake, a small jump on the spot with both hands flying up (left hand open "
            "by his face, the staff lifted off the page in his fist), lands with bent knees, eyes wide; settles "
            "standing with the staff planted at his side, hand on chest (next: kneel_bow)")
def moses_startle(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.3, staff=None)
    ant = bump(f, 0, 6)
    air = bump(f, 5, 15)
    up = ease_io((f - 4) / 4) * (1 - ease_io((f - 14) / 16))
    land = bump(f, 13, 24)
    settle = ease_io((f - 18) / 14)
    c["hips.ty"] = -0.006 * ant + 0.016 * air - 0.010 * land
    c["chest.rx"] += 2 * ant - 9 * up + 3 * land; c["spine.rx"] = -4 * up + 2 * land
    c["head.rx"] = 3 * ant - 12 * up + 4 * land; c["neck.rx"] = -4 * up
    c["head.ry"] = 6 * settle
    c["shoulderL.raise"] = 8 * up; c["shoulderR.raise"] = 8 * up
    # left hand flies up by the face, then comes to the chest
    arm_ik(c, "L", V(0.070, 0.300, 0.060), V(1.0, -0.4, -0.3), "root", up)
    c["handL.bend"] = 6 - 30 * up; fingers(c, "L", 26 - 30 * up)
    chest_hand(c, "L", V(0.022, -0.004, 0.058), settle * (1 - up))
    # staff hand: from planted at the side, up with the jump (staff follows the hand), planted again
    f0, d0 = STAFF_SIDE
    lift = up
    staff_at(c, f0 + V(0.0, 0.050 * lift + 0.012 * air, 0.010 * lift), d0, 1.0)
    stand_feet(rig, c, spread=0.003, liftL=0.010 * air, liftR=0.010 * air, pitchL=-6 * air, pitchR=-6 * air)
    blink(c, f, N, [26], loop=False)
    c["eyelids.sy"] = min(c["eyelids.sy"], 1.0)
    m_mantle(c, f, N, 0.3, loop=False)
    return c


def kneel_one(rig, c, w, **kw):
    """Moses's one-knee kneel: right knee on the page, left foot planted forward (knee up). w 0 = standing."""
    prm = dict(KY=0.036, kz=0.000, thigh_back=8.0, shin_slope=24.0); prm.update(kw)
    hip, knee, ankle = kneel_geom(rig, "R", **prm)
    bR = rig.head["footR"]
    pk = tuck_pitch(rig, "R", ankle.y)
    tgt = V(lerp(bR.x, ankle.x, w), lerp(planted_ankle_y(rig, "R", 0), ankle.y, w), lerp(bR.z, ankle.z, w))
    tgt.y = max(tgt.y, planted_ankle_y(rig, "R", pk * w))
    c["ik.legR"] = tgt; c["footR.pitch"] = pk * w; c["pole.legR"] = V(-0.08, 0, 1)
    dy = hip.y - rig.head["thighR"].y
    c["hips.ty"] = c.get("hips.ty", 0.0) + dy * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + hip.z * w
    bL = rig.head["footL"]
    step = ease_io(w * 1.6)
    c["ik.legL"] = V(bL.x + 0.006 * step, planted_ankle_y(rig, "L", 0) + 0.010 * math.sin(math.pi * min(1.0, w * 1.6)), bL.z + 0.078 * step)
    c["footL.pitch"] = 0; c["pole.legL"] = V(0.15, 0.2, 1)


@clip("moses", "kneel_bow", 66, False, props=["staff"], markers={"knee_down": 24, "bow": 44},
      notes="humble before the burning bush: a breath, steps the left foot forward and goes down on the right knee "
            "(knee on the page, robe folding over it), the staff kept upright at his right side, left hand to his "
            "heart, head and back bow low; holds, breathing")
def moses_kneel_bow(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.3, staff=STAFF_KNEEL)
    w = ease_io((f - 4) / 20)
    kneel_one(rig, c, w)
    c["hips.ty"] -= 0.004 * bump(f, 0, 8)
    bow = ease_io((f - 26) / 18)
    over = bump(f, 38, 54)
    c["hips.rx"] = 4 * bow; c["spine.rx"] = 4 * w + 10 * bow + 2 * over
    c["chest.rx"] += 2 * w + 10 * bow + 2 * over
    c["neck.rx"] = 10 * bow; c["head.rx"] = 16 * bow + 3 * over
    hw = ease_io((f - 14) / 16)
    chest_hand(c, "L", V(0.024, -0.010, 0.056), hw)
    c["handL.bend"] = -10 * hw; fingers(c, "L", 26 + 6 * hw)
    sf, sd = STAFF_SIDE
    kf, kd = STAFF_KNEEL
    staff_at(c, sf.lerp(kf, w) + V(0, 0.010 * bump(f, 6, 22), 0), sd.lerp(kd, w))
    blink(c, f, N, [8, 52], loop=False, base=lerp(1.0, 3.5, bow), slow=1.4)
    return c


@clip("moses", "who_me", 96, True, props=["staff"],
      notes="'Me? Who am I?': left hand pats his own chest twice, head shakes (no, no), then the shoulders come up "
            "in a big helpless shrug with the left palm opening out to the side and the head tilting; a nervous "
            "little step back; staff planted in the right hand; worried blinks")
def moses_who_me(rig, f, N):
    c = m_base(rig, f, N, cycles=2, amp=0.7)
    pat = pulses(f, N, [(8, 1.0), (16, 0.8), (70, 0.7)], decay=2.0)
    shake = K([(0, 0), (20, 0), (24, 12), (29, -12), (34, 9), (39, -5), (44, 0), (96, 0)], f, N, True)
    shrug = K([(0, 0), (46, 0), (54, 1), (66, 1), (74, 0), (96, 0)], f, N, True)
    onchest = 1 - shrug
    chest_hand(c, "L", V(0.020, -0.004 - 0.004 * pat, 0.060 - 0.006 * pat), onchest)
    c["handL.bend"] = lerp(-12, 6, shrug)
    c["upperArmL.raise"] = -24 + 30 * shrug; c["upperArmL.bend"] = 8 + 30 * shrug
    c["forearmL.bend"] = 28 + 50 * shrug; c["forearmL.twist"] = -12 + 85 * shrug
    fingers(c, "L", 22 - 18 * shrug)
    c["shoulderL.raise"] += 9 * shrug; c["shoulderR.raise"] += 9 * shrug
    c["head.ry"] = shake + 4 * wave(f, N, 1, 0.2); c["neck.ry"] = 0.35 * KL([(0, 0), (20, 0), (24, 12), (29, -12), (34, 9), (39, -5), (44, 0), (96, 0)], f, N, True, lag=2)
    c["head.rz"] = 10 * shrug - 2; c["head.rx"] += 4 - 3 * shrug
    c["chest.rx"] += -2 * shrug; c["hips.tz"] = -0.004 * shrug
    c["chest.ry"] = 4 * shrug
    blink(c, f, N, [3, 40, 80, 86], slow=1.0)
    stand_feet(rig, c, spread=0.003, fwdR=-0.010 * shrug)
    m_mantle(c, f, N)
    return c


THROW_REL = 16.5      # frame of the release (0.55 s)


@clip("moses", "throw_staff", 40, False, props=["staff"], markers={"release": THROW_REL},
      notes="'Throw it on the ground': a hesitant look at the staff, lifts it in the right fist (anticipation, weight "
            "back), then tosses it down onto the page in front of him - the fist sweeps forward and down and opens at "
            "`release` = 0.55 s (the director hides moses/staff and starts the `snake` FX there); follow-through, "
            "leans to look at it, hands half up; holds")
def moses_throw_staff(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.3, staff=None)
    lookat = ease_io(f / 6)
    wind = ease_io((f - 3) / 9) * (1 - ease_io((f - 12) / 4.5))
    throw = ease_io((f - 11) / 6)
    follow = ease_io((f - 17) / 12)
    # right wrist path (root space): side -> up/back (wind-up) -> forward-down (release) -> out, open
    side = V(-0.104, 0.166, 0.030)
    up = V(-0.090, 0.235, -0.006)
    rel_ = V(-0.050, 0.150, 0.110)
    after = V(-0.064, 0.150, 0.080)
    if f < 12:
        p = side.lerp(up, wind)
    elif f < 17:
        p = up.lerp(rel_, throw)
    else:
        p = rel_.lerp(after, follow)
    arm_ik(c, "R", p, V(-0.8, -0.5, -0.3))
    # staff orientation follows the throw: upright -> tilted back -> pointing forward-down (falls flat)
    if f < 12:
        c["staff.aim"] = V(-0.05, 1.0, -0.10).lerp(V(-0.05, 1.0, -0.45), wind)
    else:
        c["staff.aim"] = V(-0.05, 1.0, -0.45).lerp(V(0.0, -0.15, 1.0), min(1.0, throw * 1.1))
    opn = ease_io((f - 16) / 3)
    fingers(c, "R", -30 * opn); c["handR.bend"] = -20 * opn
    c["hips.tz"] = -0.006 * wind + 0.010 * throw; c["spine.rx"] = -3 * wind + 9 * throw + 2 * follow
    c["chest.rx"] += -3 * wind + 6 * throw; c["chest.ry"] = 8 * wind - 6 * throw
    c["head.rx"] = 6 * lookat - 4 * wind + 14 * throw; c["neck.rx"] = 4 * throw
    # left hand comes up half-defensive after the release
    c["upperArmL.raise"] = -24 + 18 * follow; c["upperArmL.bend"] = 8 + 26 * follow
    c["forearmL.bend"] = 28 + 40 * follow; c["forearmL.twist"] = -12 + 40 * follow
    fingers(c, "L", 26 - 24 * follow)
    stand_feet(rig, c, spread=0.003, fwdL=0.016 * throw, pitchR=6 * wind)
    blink(c, f, N, [2], loop=False)
    m_mantle(c, f, N, 0.3, loop=False)
    return c


JB_BACK = 0.060


@clip("moses", "jump_back", 54, False, props=[], markers={"hop": 8, "land": 20},
      notes="'Whoa, a snake!': comic hop BACKWARDS 0.06 (rootMotion false: the body ends 0.06 behind the root) with "
            "both arms flung up, mantle and beard flying; lands in a crouch, knees bent, leaning forward over the "
            "snake and pointing down at it with the left hand, right hand up by his shoulder; holds. Staff hidden "
            "(it is the snake)")
def moses_jump_back(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.2, staff=None)
    ant = bump(f, 0, 7)
    air = bump(f, 6, 20)
    back = ease_io((f - 5) / 14)
    land = bump(f, 18, 30)
    crouch = ease_io((f - 22) / 14)
    up = ease_io((f - 3) / 4) * (1 - ease_io((f - 20) / 14))
    c["hips.tz"] = -JB_BACK * back
    c["hips.ty"] = -0.008 * ant + 0.030 * air - 0.012 * land - 0.024 * crouch
    c["chest.rx"] += 3 * ant - 12 * up + 8 * crouch; c["spine.rx"] = -6 * up + 10 * crouch + 3 * land
    c["hips.rx"] = 10 * crouch
    c["head.rx"] = 4 * ant - 14 * up + 10 * crouch; c["neck.rx"] = -6 * up + 4 * crouch
    c["shoulderL.raise"] = 10 * up; c["shoulderR.raise"] = 10 * up
    # arms: flung up, then left points down at the snake, right hand up by the shoulder (scared)
    arm_ik(c, "L", V(0.090, 0.330, 0.020), V(1.0, -0.3, -0.4), "root", up)
    arm_ik(c, "R", V(-0.090, 0.330, 0.020), V(-1.0, -0.3, -0.4), "root", up)
    point = crouch * (1 - up)
    if point > 0:
        c["ik.armL"] = vlerp(c["ik.armL"], V(0.050, 0.120, 0.120 - JB_BACK), point) if up > 0 else V(0.050, 0.120, 0.120 - JB_BACK)
        c["ikw.armL"] = max(c.get("ikw.armL", 0.0), point); c["pole.armL"] = V(1.0, 0.0, -0.3)
        c["ik.armR"] = vlerp(c["ik.armR"], V(-0.060, 0.230, 0.020 - JB_BACK), point) if up > 0 else V(-0.060, 0.230, 0.020 - JB_BACK)
        c["ikw.armR"] = max(c.get("ikw.armR", 0.0), point); c["pole.armR"] = V(-1.0, -0.5, -0.2)
    c["handL.bend"] = -8 * point; fingers(c, "L", 26 - 30 * up + 34 * point)
    c["handR.bend"] = -30 * point; fingers(c, "R", -20 * up - 25 * point)
    c["head.ry"] = 0
    # legs: take off, travel back, land bent; feet a little apart
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        lift = 0.024 * air
        z = b.z - JB_BACK * ease_io((f - 6) / 12) + 0.008 * (side == "L") * crouch
        c[f"ik.leg{side}"] = V(b.x + sx * 0.006 * crouch, planted_ankle_y(rig, side, 0) + lift, z)
        c[f"foot{side}.pitch"] = 12 * air * (1 if f < 12 else -0.5)
    c["mantleL.rx"] = -10 * air; c["mantleR.rx"] = -10 * air; c["mantleBack.rx"] = 12 * air
    blink(c, f, N, [40], loop=False)
    c["eyelids.sy"] = min(c["eyelids.sy"], 1.0) if f < 38 else c["eyelids.sy"]
    return c


GRAB_SHOW = 27        # staff re-shown (0.9 s)


@clip("moses", "grab_tail", 48, False, props=["staff"], markers={"grab": 20, "staff": GRAB_SHOW},
      notes="'Take it by the tail': from the jump_back crouch (feet 0.06 back) a cautious step in, bends low (knees "
            "and back) and reaches down with the right hand to y = 0.02 in front, fingers close on the tail (f 20), "
            "lifts - the staff is re-shown at 0.9 s upright in his fist - and plants it at his side as he straightens; "
            "a relieved breath; ends standing")
def moses_grab_tail(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.3, staff=None)
    stepin = ease_io(f / 14)
    bend = ease_io((f - 4) / 14) * (1 - ease_io((f - 24) / 14))
    rise = ease_io((f - 24) / 16)
    back0 = -JB_BACK * (1 - stepin)
    c["hips.tz"] = back0 + 0.008 * bend
    c["hips.ty"] = -0.024 * (1 - stepin) * (1 - bend) - 0.042 * bend
    c["hips.rx"] = 10 * (1 - stepin) * (1 - bend) + 18 * bend
    c["spine.rx"] = 10 * (1 - stepin) + 16 * bend; c["chest.rx"] += 8 * (1 - stepin) + 14 * bend - 2 * rise
    c["head.rx"] = 10 * (1 - stepin) * (1 - bend) + 6 * bend - 4 * rise; c["neck.rx"] = 6 * bend
    # right hand: down to the tail, grab, lift to the side
    low = V(-0.040, 0.020, 0.090)
    side, sd = STAFF_SIDE
    grip_side = V(-0.104, 0.166, 0.030)
    if f < GRAB_SHOW:
        tgt = V(-0.060, 0.200, 0.020).lerp(low, ease_io((f - 4) / 14))
        arm_ik(c, "R", tgt, V(-0.8, -0.3, -0.5))
        c["staff.aim"] = V(0.0, 1.0, 0.0)
        fingers(c, "R", -25 + 25 * ease_io((f - 18) / 4))
    else:
        t = ease_io((f - GRAB_SHOW) / 14)
        # the staff appears upright in the rising fist, then is planted at his side
        lifted = low + V(-0.030, 0.185, -0.020)
        staff_at(c, (lifted - V(0, rig.staff_len - 0.0, 0)).lerp(side, t) if False else side, sd)
        if t < 1:
            c.pop("staff.foot", None); c.pop("staff.dir", None)
            arm_ik(c, "R", lifted.lerp(grip_side, t), V(-0.8, -0.5, -0.4))
            c["staff.aim"] = V(-0.03, 1.0, -0.10)
        fingers(c, "R", 0)
    c["upperArmL.raise"] = -24 + 10 * bend; c["upperArmL.bend"] = 8 + 20 * bend; c["forearmL.bend"] = 28 + 20 * bend
    sigh = bump(f, 36, 48)
    c["chest.rx"] += -3 * sigh; c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh
    for side_, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side_]
        z0 = b.z - JB_BACK + (0.008 if side_ == "L" else 0.0)
        st = ease_io((f - (0 if side_ == "L" else 6)) / 10)
        c[f"ik.leg{side_}"] = V(b.x + sx * 0.006 * (1 - st), planted_ankle_y(rig, side_, 0) + 0.010 * math.sin(math.pi * st), lerp(z0, b.z, st))
        c[f"foot{side_}.pitch"] = 0
    blink(c, f, N, [33], loop=False)
    return c


@clip("moses", "nod_brave", 50, False, props=["staff"], markers={"nod": 26},
      notes="'All right... I'll go!': a deep breath in (chest and shoulders rise, the stoop straightens), a firm "
            "nod, the fist tightens and pulls the staff in close and upright, chin up, a small determined smile; "
            "holds standing a little taller")
def moses_nod_brave(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.2)
    br = bump(f, 0, 22)
    tall = ease_io((f - 14) / 16)
    nod = K([(0, 0), (20, 0), (24, -4), (28, 14), (33, 3), (38, 5), (50, 5)], f)
    c["chest.rx"] += -5 * br - 3 * tall; c["spine.rx"] = -2 * br - 2 * tall
    c["shoulderL.raise"] += 5 * br; c["shoulderR.raise"] += 5 * br
    c["head.rx"] = -3 * br + nod - 7 * tall; c["neck.rx"] = 0.3 * KL([(0, 0), (20, 0), (24, -4), (28, 14), (33, 3), (38, 5), (50, 5)], f, lag=2) - 2 * tall
    sf, sd = STAFF_SIDE
    staff_at(c, sf.lerp(V(-0.094, 0.0, 0.052), tall), sd.lerp(V(-0.01, 1.0, -0.05), tall))
    chest_hand(c, "L", V(0.022, -0.004, 0.058), bump(f, 2, 30) * 0.9)
    fingers(c, "L", 26 + 20 * tall)
    c["upperArmL.raise"] = -24 - 3 * tall
    blink(c, f, N, [32], loop=False)
    stand_feet(rig, c, spread=0.004 + 0.004 * tall)
    return c


@clip("moses", "staff_raise", 40, False, props=["staff"], markers={"up": 16},
      notes="lifts the staff high in the right hand (fist above his head, the staff upright, its foot clear of the "
            "page), left arm out to the side with the hand open, chest up, chin up, weight forward on the left foot; "
            "a small overshoot and settle; holds (used for 'Let my people go!', the plagues and the finale)")
def moses_staff_raise(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.2, staff=None)
    ant = bump(f, 0, 8)
    up = ease_io((f - 4) / 12)
    over = bump(f, 14, 26)
    p = V(-0.104, 0.166, 0.030).lerp(V(-0.062, 0.392, 0.040), up) + V(0, 0.006 * over, 0)
    p.y -= 0.006 * ant
    arm_ik(c, "R", p, V(-1.0, -0.2, -0.3))
    c["staff.aim"] = V(-0.03, 1.0, -0.10).lerp(V(0.06, 1.0, 0.08), up)
    fingers(c, "R", 0)
    c["upperArmL.raise"] = -24 + 52 * up + 4 * over; c["upperArmL.bend"] = 8 + 22 * up
    c["forearmL.bend"] = 28 - 8 * up; c["forearmL.twist"] = -12 + 60 * up
    c["handL.bend"] = 6 - 18 * up; fingers(c, "L", 26 - 22 * up)
    c["chest.rx"] += 2 * ant - 8 * up; c["spine.rx"] = -3 * up; c["neck.rx"] = -3 * up
    c["head.rx"] = 3 * ant - 8 * up - 2 * over; c["head.rz"] = -3 * up
    c["hips.tz"] = 0.006 * up
    stand_feet(rig, c, spread=0.004, fwdL=0.018 * up)
    blink(c, f, N, [30], loop=False)
    m_mantle(c, f, N, 0.4, loop=False)
    c["mantleL.rx"] += -4 * over; c["mantleR.rx"] += -4 * over
    return c


@clip("moses", "sigh_head", 54, False, props=["staff"], markers={"sigh": 16},
      notes="Pharaoh changed his mind again: a long sigh (shoulders rise, then sink), eyes close for a moment, the "
            "head shakes slowly three times, left hand rubs his brow once; ends standing, staff planted at his side")
def moses_sigh_head(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.2)
    rise = bump(f, 0, 18)
    sink = bump(f, 14, 46)
    c["chest.rx"] += -4 * rise + 5 * sink; c["shoulderL.raise"] += 5 * rise - 4 * sink; c["shoulderR.raise"] += 5 * rise - 4 * sink
    sh = [(0, 0), (16, 0), (22, 9), (30, -9), (38, 7), (46, -3), (54, 0)]
    c["head.ry"] = K(sh, f); c["neck.ry"] = 0.3 * KL(sh, f, lag=3)
    c["head.rx"] = 6 * sink - 2 * rise; c["neck.rx"] = 3 * sink
    rub = bump(f, 24, 48)
    arm_ik(c, "L", V(0.016, 0.084 + 0.004 * math.sin(f * 0.8), 0.070), V(1.0, -0.4, -0.3), "chest", rub)
    c["handL.bend"] = -20 * rub; fingers(c, "L", 26 - 10 * rub)
    blink(c, f, N, [14], loop=False, slow=3.5)
    stand_feet(rig, c, spread=0.003)
    return c


@clip("moses", "brave_talk", 96, True, props=["staff"],
      notes="'Don't be afraid! Stand still': calm and strong, standing tall (stoop lifted), staff planted firmly "
            "at his side, the left palm out toward his listener at chest height with small steadying pushes on the "
            "stressed syllables, a slow reassuring nod; jaw talks (lip sync overrides it)")
def moses_brave_talk(rig, f, N):
    c = m_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 17, amp=(6, 13), dur=(4.0, 7.5), gap=0.3)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=12)
    btl = beat_curve(beats, f - 3, N, width=12)
    c["chest.rx"] += -4; c["spine.rx"] = -2; c["neck.rx"] = -2
    c["head.rx"] = -3 + 4 * bt - 1.0 * wave(f, N, 1, 0.3); c["head.ry"] = 3 * wave(f, N, 1, 0.1)
    palm = K([(0, 0.85), (20, 1.0), (50, 0.9), (70, 1.0), (96, 0.85)], f, N, True)
    arm_ik(c, "L", V(0.058, 0.258 + 0.004 * btl, 0.122 + 0.010 * btl), V(1.0, -0.6, -0.3), "root", palm)
    c["handL.bend"] = -62 + 10 * btl; c["handL.twist"] = -10; fingers(c, "L", 4)
    sf, sd = STAFF_SIDE
    staff_at(c, sf, V(-0.01, 1.0, -0.06))
    blink(c, f, N, [9, 57], base=1.0)
    stand_feet(rig, c, spread=0.005, fwdL=0.012)
    m_mantle(c, f, N)
    return c


@clip("moses", "staff_over_sea", 270, False, props=["staff"], markers={"reach": 30, "gust": 120},
      notes="the hero moment: a breath, steps forward onto the left foot, raises both arms forward-up and holds the "
            "staff out LEVEL across in front of him above his head (right fist on the grip, left hand further along "
            "the shaft), chest lifted, chin up, gazing at the sea; a strong wind from the sea blows the beard to his "
            "right, the mantle panels flare back and flap, gusts come and go (strongest ~4 s); the arms brace "
            "against each gust; 9 s long to cover the sea_wind FX, ends in a still heroic hold")
def moses_staff_over_sea(rig, f, N):
    c = m_base(rig, f, N, cycles=4, amp=0.6, staff=None)
    ant = bump(f, 0, 12)
    step = ease_io((f - 6) / 14)
    up = ease_io((f - 10) / 22)
    over = bump(f, 28, 44)
    wind_in = ease_io((f - 20) / 30) * (1 - 0.6 * ease_io((f - 230) / 36))
    g = gusts(f, 0.4) * wind_in
    brace = g * up
    # both hands on the staff, held level across, forward-up
    grip = V(-0.040, 0.352 + 0.004 * over - 0.004 * brace, 0.098 - 0.004 * brace)
    rest_grip = V(-0.104, 0.166, 0.030)
    arm_ik(c, "R", rest_grip.lerp(grip, up), V(-1.0, -0.5, -0.3))
    c["staff.aim"] = V(-0.03, 1.0, -0.10).lerp(V(1.0, 0.03, -0.06), up)
    fingers(c, "R", 0)
    # left hand on the shaft 0.085 along from the grip (staff space: rest staff points up +Y)
    arm_ik(c, "L", V(0.004, 0.085, 0.004), V(1.0, -0.6, -0.3), "staff", ease_io((f - 14) / 18))
    c["handL.bend"] = 10; c["handL.twist"] = -60; fingers(c, "L", 56)
    c["hips.tz"] = 0.014 * step - 0.004 * ant; c["hips.ty"] = -0.004 * ant - 0.004 * step
    c["chest.rx"] += 3 * ant - 9 * up + 1.5 * brace; c["spine.rx"] = -4 * up + 2 * step
    c["neck.rx"] = -4 * up; c["head.rx"] = 2 * ant - 10 * up + 1.0 * brace - 2 * over
    c["head.rz"] = -2 * brace
    stand_feet(rig, c, spread=0.006, fwdL=0.034 * step, fwdR=-0.008 * step, pitchR=8 * step)
    # wind: beard to his right, mantle flared back, flapping with the gusts
    flap = math.sin(f * 0.9) * 0.15 + math.sin(f * 1.7 + 0.5) * 0.08
    c["wind.beard1"] = V(-0.95, 0.0, 0.25) * (0.65 * g)
    c["wind.beard2"] = V(-0.95, 0.10, 0.20) * (1.0 * g)
    c["wind.mantleL"] = V(0.55, 0.05, -0.85) * ((0.45 + flap) * g)
    c["wind.mantleR"] = V(-0.55, 0.05, -0.85) * ((0.45 - flap) * g)
    c["wind.mantleBack"] = V(-0.25, 0.10, -1.0) * ((0.55 + flap) * g)
    blink(c, f, N, [60, 150, 158, 236], loop=False)
    return c


@clip("moses", "clap", 32, True, props=["staff"], markers={"clap1": 0, "clap2": 16}, timescale=SONG_K,
      notes="joining Miriam's song: staff planted in front (as idle), the left palm claps onto the right fist on the "
            "staff on every dotted beat, a happy knee-bounce and nod with the beat, head tilting side to side, "
            "smiling. Time-scaled in the GLB to exactly one bar of the song (1.0714 s = 32 frames x 1.00446), claps on "
            "frame 0 and 16 = the song's dotted beats")
def moses_clap(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.5, staff=STAFF_FRONT)
    hit = pulses(f, N, [(0, 1.0), (16, 1.0)], decay=2.5)
    open_ = 0.5 - 0.5 * math.cos(2 * math.pi * 2 * f / N)       # 0 at the claps, 1 between
    arm_ik(c, "L", V(0.040 + 0.010 * open_, 0.040 + 0.050 * open_, 0.020 + 0.030 * open_), V(0.9, -0.5, -0.3), "staff")
    c["handL.bend"] = 10 - 20 * open_; c["handL.twist"] = -60; fingers(c, "L", 12)
    c["hips.ty"] = -0.004 * hit - 0.002 * open_
    c["head.rx"] = 3 * hit - 2; c["head.rz"] = 5 * wave(f, N, 1, 0.25); c["neck.rz"] = 2 * wave(f, N, 1, 0.1)
    c["chest.rx"] += 1.5 * hit; c["chest.rz"] = 1.5 * wave(f, N, 1, 0.3)
    c["jaw.rx"] = 4 + 2 * open_
    blink(c, f, N, [22])
    stand_feet(rig, c, spread=0.003)
    return c


@clip("moses", "talk_warm", 120, True, props=["staff"],
      notes="grandfatherly: staff planted at his side, gentle slow open-palm gestures with the left hand toward the "
            "child (palm up, a soft sweep out), once the hand to his heart, warm head tilts and slow nods, a smile in "
            "the eyes; jaw in a slow irregular rhythm (lip sync overrides it); slow blinks")
def moses_talk_warm(rig, f, N):
    c = m_base(rig, f, N, cycles=2, amp=1.0)
    jk, beats = syllables(N, 92, amp=(4, 10), dur=(4.5, 8.5), gap=0.35)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=14)
    c["head.rx"] += 2.5 * bt - 1.5 * wave(f, N, 1, 0.2); c["head.rz"] = 5 * wave(f, N, 1, 0.1)
    c["head.ry"] = 3 * wave(f, N, 1, 0.45)
    sweep = K([(0, 0.2), (14, 0.8), (40, 1.0), (56, 0.3), (68, 0.0), (100, 0.0), (112, 0.2), (120, 0.2)], f, N, True)
    heart = K([(0, 0), (60, 0), (70, 1), (98, 1), (108, 0), (120, 0)], f, N, True)
    c["upperArmL.raise"] = -24 + 14 * sweep; c["upperArmL.bend"] = 8 + 30 * sweep
    c["forearmL.bend"] = 28 + 40 * sweep; c["forearmL.twist"] = -12 + 85 * sweep
    c["handL.bend"] = 6 - 16 * sweep; fingers(c, "L", 24 - 18 * sweep)
    chest_hand(c, "L", V(0.024, -0.006, 0.058), heart)
    c["chest.ry"] = 5 * sweep - 3 * heart; c["chest.rx"] += 1.0 * bt
    blink(c, f, N, [18, 84], base=1.2, slow=1.6)
    stand_feet(rig, c, spread=0.003)
    m_mantle(c, f, N)
    return c


@clip("moses", "wave", 48, True, props=["staff"],
      notes="a friendly old man's wave with the left hand raised by his head (wrist-led, three waves per loop), staff "
            "planted in the right hand; head tilt, smile")
def moses_wave(rig, f, N):
    c = m_base(rig, f, N, cycles=1, amp=0.5)
    arm_ik(c, "L", V(0.098 + 0.008 * wave(f, N, 3, 0.0), 0.318, 0.040), V(1.0, -0.6, -0.2))
    c["handL.twist"] = -70; c["handL.bend"] = 22 * wave(f, N, 3, 0.15); fingers(c, "L", 6)
    c["head.rz"] = -5; c["head.rx"] = -3; c["chest.rz"] = -2
    blink(c, f, N, [20])
    stand_feet(rig, c, spread=0.003)
    return c


# =============================================================================================== PHARAOH
# Rest: A-pose, straight, bare arms. Comic villain: big, theatrical, vain; `sad_sit` is the one real sad moment.
CHARIOT_FLOOR = 0.035
CH_PIVOT_R = V(-0.060, 0.0, -0.004)       # right wheel's contact (the chariot tips about it in wobble)


def p_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.6 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.0 * b * amp; c["shoulderR.raise"] = 1.0 * b * amp
    c["upperArmL.raise"] = -20; c["upperArmR.raise"] = -20
    c["upperArmL.bend"] = 6; c["upperArmR.bend"] = 6
    c["forearmL.bend"] = 22; c["forearmR.bend"] = 22
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    fingers(c, "L", 24); fingers(c, "R", 24)
    c["chest.rx"] += -3; c["head.rx"] = -5                          # chest out, chin up: always
    return c


def hands_on_hips(c, w=1.0, sway=0.0):
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.064, 0.212 + 0.002 * sway * sx, -0.004), V(sx * 1.0, 0.25, -0.55), "root", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 0.0), 30, w)
        c[f"hand{side}.twist"] = lerp(c.get(f"hand{side}.twist", 0.0), sx * 20, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 24), 70, w))


def point_arm(c, side, amt, tgt=None, w=1.0):
    """Arm out straight, pointing (fist with the hand straight; single-bone fingers)."""
    sx = 1 if side == "L" else -1
    tgt = tgt or V(sx * 0.080, 0.262, 0.150)
    arm_ik(c, side, tgt, V(sx * 1.0, -0.6, -0.2), "root", amt * w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 0.0), -6, amt)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 24), 35, amt))


def ph_lappets(c, f, N, amp=1.0, phase=0.0):
    c["nemes1L.rx"] = c.get("nemes1L.rx", 0.0) + 1.2 * amp * wave(f, N, 1, phase)
    c["nemes1R.rx"] = c.get("nemes1R.rx", 0.0) + 1.2 * amp * wave(f, N, 1, phase + 0.3)


@clip("pharaoh", "idle", 150, True,
      notes="vain king at ease: chest out, chin up, weight on one hip then the other, the left hand on his hip, the "
            "right hand admires its bracelets once (lifts, turns the wrist, a satisfied little nod), looks down his "
            "nose left and right; slow, heavy-lidded blinks; lappets sway")
def pharaoh_idle(rig, f, N):
    c = p_base(rig, f, N, cycles=3, amp=1.0)
    sh = [(0, 0.6), (50, 0.6), (70, -0.6), (120, -0.6), (140, 0.6), (150, 0.6)]
    s = K(sh, f, N, True); sl = KL(sh, f, N, True, lag=8)
    c["hips.tx"] = 0.005 * s; c["hips.rz"] = -3.0 * s; c["spine.rz"] = 1.6 * sl; c["chest.rz"] = 1.2 * sl
    c["head.rz"] = -1.5 * sl
    look = [(0, 0), (20, 0), (32, 1), (50, 1), (60, -1), (82, -1), (94, 0), (150, 0)]
    c["neck.ry"] = 6 * K(look, f, N, True); c["head.ry"] = 12 * KL(look, f, N, True, lag=4)
    # left fist on the hip
    arm_ik(c, "L", V(0.064, 0.212, -0.004), V(1.0, 0.25, -0.55))
    c["handL.bend"] = 30; c["handL.twist"] = 20; fingers(c, "L", 70)
    adm = ease_io((f - 96) / 10) * (1 - ease_io((f - 128) / 12))
    turn = math.sin(math.pi * (f - 104) / 12) if 104 <= f <= 128 else 0.0
    c["upperArmR.bend"] = 6 + 40 * adm; c["forearmR.bend"] = 22 + 80 * adm
    c["forearmR.twist"] = 10 - 50 * adm + 30 * turn * adm; c["handR.bend"] = -10 * adm
    c["head.rx"] += 8 * adm; c["head.ry"] += -10 * adm; fingers(c, "R", 24 - 10 * adm)
    blink(c, f, N, [40, 88, 140], base=2.0, slow=1.4)        # heavy, smug lids
    stand_feet(rig, c, spread=0.006, pitchR=K([(0, 0), (60, 0), (70, 6), (120, 6), (130, 0), (150, 0)], f, N, True))
    ph_lappets(c, f, N)
    return c


P_WALK = (0.078, 0.58)


@clip("pharaoh", "walk", 36, True, markers={"contactL": 0, "contactR": 18}, speed=P_WALK,
      notes="strut: chest out, chin up, high proud knees and pointed toes, big stiff arm swings, a pompous "
            "shoulder roll, little bounce; lappets bounce late")
def pharaoh_walk(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=P_WALK[0], lift=0.022, duty=P_WALK[1], heel=4, toeoff=30, lift_shape=0.8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.003 + 0.0042 * math.cos(2 * ph - 0.3)
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -9 * math.sin(ph - 0.3); c["head.ry"] = 4 * math.sin(ph - 0.6)
    c["hips.rz"] = 3 * math.cos(ph); c["chest.rz"] = -2.5 * math.cos(ph - 0.5)
    c["chest.rx"] += -3; c["head.rx"] += -2 + 2 * math.cos(2 * ph - 0.8)
    c["upperArmL.bend"] = 6 - 26 * math.sin(ph - 0.15); c["upperArmR.bend"] = 6 + 26 * math.sin(ph - 0.15)
    c["forearmL.bend"] = 18 - 6 * math.sin(ph - 0.6); c["forearmR.bend"] = 18 + 6 * math.sin(ph - 0.6)
    c["shoulderL.raise"] += 3 * math.sin(ph); c["shoulderR.raise"] -= 3 * math.sin(ph)
    fingers(c, "L", 40); fingers(c, "R", 40)
    blink(c, f, N, [25], base=1.6)
    return c


@clip("pharaoh", "talk", 96, True,
      notes="pompous speech: big theatrical gestures with both hands in turn (a grand sweep out, a hand to his own "
            "chest - 'I!' - a jabbing finger), chin up, head bobbing on the stressed words; jaw in an irregular "
            "rhythm (lip sync overrides it)")
def pharaoh_talk(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 44, amp=(7, 16), dur=(3.0, 6.0), gap=0.25)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=8)
    btl = beat_curve(beats, f - 3, N, width=9)
    c["head.rx"] += 4 * bt; c["head.ry"] = 8 * wave(f, N, 1, 0.1); c["head.rz"] = 4 * wave(f, N, 1, 0.3)
    sweep = K([(0, 0.0), (8, 1.0), (30, 1.0), (40, 0.0), (96, 0.0)], f, N, True)
    me = K([(0, 0), (36, 0), (44, 1), (60, 1), (66, 0), (96, 0)], f, N, True)
    jab = K([(0, 0), (62, 0), (70, 1), (88, 1), (94, 0), (96, 0)], f, N, True)
    c["upperArmR.raise"] = -20 + 70 * sweep; c["upperArmR.bend"] = 6 + 30 * sweep
    c["forearmR.bend"] = 22 + 10 * sweep; c["forearmR.twist"] = 10 - 70 * sweep
    c["handR.bend"] = -10 * sweep; fingers(c, "R", 24 - 20 * sweep)
    chest_hand(c, "L", V(0.010, -0.002, 0.050), me)
    c["handL.bend"] = -20 * me; fingers(c, "L", 20)
    point_arm(c, "R", jab, V(-0.050, 0.250 + 0.010 * btl, 0.150))
    c["chest.ry"] = -10 * sweep + 6 * me + 8 * jab; c["chest.rx"] += 2 * bt
    c["hips.tz"] = 0.004 * jab
    blink(c, f, N, [20, 75], base=1.4)
    stand_feet(rig, c, spread=0.006, fwdR=0.010 * jab)
    ph_lappets(c, f, N)
    return c


@clip("pharaoh", "smug", 120, True,
      notes="fists on his hips, elbows out, chest out, chin high, looking down his nose; a slow self-satisfied sway "
            "side to side, one smug little head-bob, heavy half-closed lids with slow blinks; lappets sway")
def pharaoh_smug(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=0.9)
    s = wave(f, N, 1, 0.0); sl = wave(f, N, 1, -0.06)
    c["hips.tx"] = 0.004 * s; c["hips.rz"] = -2.6 * s; c["spine.rz"] = 1.6 * sl; c["chest.rz"] = 1.4 * sl
    c["head.rz"] = -3 * sl + 2 * wave(f, N, 2, 0.2)
    c["chest.rx"] += -2; c["head.rx"] += -3 + 3 * bump(f, 60, 72) - 2 * bump(f, 72, 84)
    c["head.ry"] = 6 * wave(f, N, 1, 0.25)
    hands_on_hips(c, sway=s)
    blink(c, f, N, [30, 92], base=2.6, slow=1.6)
    stand_feet(rig, c, spread=0.010)
    ph_lappets(c, f, N)
    return c


@clip("pharaoh", "point_order", 36, False, markers={"point": 12},
      notes="the boss: a sharp breath in, the left fist goes to his hip, the right arm shoots out straight pointing "
            "(whole hand, finger-straight) at the workers, a jab with a lean forward, chin up; overshoot and settle; holds")
def pharaoh_point_order(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.2)
    ant = bump(f, 0, 9)
    out = ease_io((f - 6) / 6)
    jab = bump(f, 11, 22)
    hw = ease_io(f / 10)
    arm_ik(c, "L", V(0.064, 0.212, -0.004), V(1.0, 0.25, -0.55), "root", hw)
    c["handL.bend"] = 30 * hw; c["handL.twist"] = 20 * hw; fingers(c, "L", 24 + 46 * hw)
    point_arm(c, "R", out, V(-0.060, 0.268 + 0.010 * jab, 0.168 + 0.010 * jab))
    c["upperArmR.raise"] = -20 + 30 * ant
    c["chest.rx"] += 2 * ant + 3 * jab; c["chest.ry"] = 6 * ant - 10 * out
    c["hips.tz"] = 0.004 * out + 0.004 * jab; c["head.rx"] += 2 * ant + 3 * jab
    stand_feet(rig, c, spread=0.008, fwdR=0.016 * out)
    blink(c, f, N, [4], loop=False, base=1.4)
    ph_lappets(c, f, N, loop=False) if False else None
    return c


@clip("pharaoh", "laugh", 75, False, markers={"ha": 10},
      notes="a huge fake belly laugh: leans back, throws his head back, both hands on his belly, shoulders and belly "
            "shake in uneven fading pulses (HA HA HA), wipes an eye, settles into the smug pose (fists on hips, chin "
            "up) = frame 0 of `smug`; holds")
def pharaoh_laugh(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.2)
    back = ease_io((f - 2) / 8) * (1 - ease_io((f - 46) / 14))
    hits = pulses(f, N, [(10, 1.0), (16, 0.9), (22, 0.85), (28, 0.7), (35, 0.55), (42, 0.35)], decay=2.5, loop=False)
    c["spine.rx"] = -10 * back - 2 * hits; c["chest.rx"] += -10 * back + 3 * hits; c["neck.rx"] = -10 * back
    c["head.rx"] = -26 * back + 4 * hits
    c["shoulderL.raise"] = 4 * hits; c["shoulderR.raise"] = 4 * hits
    c["hips.tz"] = 0.006 * back; c["hips.ty"] = -0.002 * hits
    c["jaw.rx"] = 6 * back + 10 * hits
    belly = back
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.030, 0.226 + 0.003 * hits, 0.050), V(sx * 1.0, -0.4, -0.3), "root", belly)
        c[f"hand{side}.bend"] = -10 * belly; fingers(c, side, 24 + 10 * belly)
    # settle to smug
    sm = ease_io((f - 52) / 18)
    smug = pharaoh_smug(rig, 0, 120)
    for k in ("chest.rx", "head.rx", "spine.rx", "head.rz", "hips.tx", "hips.rz", "spine.rz", "chest.rz", "head.ry"):
        c[k] = lerp(c.get(k, 0.0), smug.get(k, 0.0), sm)
    if sm > 0:
        hands_on_hips(c, w=sm, sway=0.0)
    wipe = bump(f, 44, 58)
    if wipe > 0 and sm < 0.5:
        chest_hand(c, "R", V(-0.012, 0.072, 0.060), wipe, V(-1.0, -0.5, -0.2))
    stand_feet(rig, c, spread=lerp(0.006, 0.010, sm))
    blink(c, f, N, [], loop=False)
    c["eyelids.sy"] = 1.0 + 5.0 * back + 1.6 * sm
    return c


@clip("pharaoh", "arms_crossed", 120, True,
      notes="stubborn 'No!': arms folded high across the chest, chin up and head turned away (nose in the air), the "
            "right foot taps impatiently (irregular), one sideways peek back and a 'hmph' re-turn; heavy-lidded blinks")
def pharaoh_arms_crossed(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=0.9)
    peek = K([(0, 0), (60, 0), (66, 1), (80, 1), (84, -0.15), (94, 0), (120, 0)], f, N, True)
    hmph = bump(f, 80, 92)
    c["head.ry"] = 32 - 26 * peek; c["neck.ry"] = 10 - 8 * peek
    c["head.rx"] += -6 + 3 * peek - 3 * hmph; c["head.rz"] = -4
    c["chest.ry"] = -4; c["chest.rx"] += -2 - 2 * hmph
    chest_hand(c, "L", V(-0.034, -0.030, 0.044), 1.0, V(1.0, -0.2, -0.1))
    chest_hand(c, "R", V(0.036, -0.020, 0.054), 1.0, V(-1.0, -0.2, -0.1))
    c["handL.bend"] = 10; c["handR.bend"] = 10; fingers(c, "L", 60); fingers(c, "R", 50)
    taps = [8, 16, 24, 40, 48, 100, 108]
    tp = max(bump(f, t, t + 6) for t in taps)
    blink(c, f, N, [34, 96], base=1.8, slow=1.3)
    stand_feet(rig, c, spread=0.008, pitchR=-16 * tp, fwdR=0.010)
    ph_lappets(c, f, N)
    return c


@clip("pharaoh", "frog_panic", 150, False, markers={"freeze": 6, "swat": 36, "allright": 110},
      notes="a frog lands on his head: freezes stiff, eyes roll up (head tilts back slowly), a beat, then panics - "
            "swats wildly at his head with both hands, hopping on the spot (three hops, knees up, lappets flying); "
            "then gives in: both palms out in front pushing 'all right, all right!' twice, leaning back; holds")
def pharaoh_frog_panic(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.2)
    freeze = ease_io(f / 5)
    lookup = ease_io((f - 10) / 14) * (1 - ease_io((f - 36) / 6))
    panic = ease_io((f - 32) / 4) * (1 - ease_io((f - 96) / 10))
    give = ease_io((f - 98) / 10)
    hops = [(42, 58), (60, 74), (77, 92)]
    air = max(bump(f, a, b) for a, b in hops)
    c["shoulderL.raise"] = 8 * freeze * (1 - panic); c["shoulderR.raise"] = 8 * freeze * (1 - panic)
    c["head.rx"] += -18 * lookup + 4 * panic * math.sin(f * 0.9); c["neck.rx"] = -6 * lookup
    c["chest.rx"] += -2 * freeze
    c["hips.ty"] = 0.024 * air - 0.006 * panic * (1 - air)
    # swatting: hands alternate over the head
    swL = math.sin(f * 0.75); swR = math.sin(f * 0.75 + 2.2)
    for side, sx, sw in (("L", 1, swL), ("R", -1, swR)):
        arm_ik(c, side, V(sx * (0.040 + 0.020 * sw), 0.395 + 0.015 * sw, 0.010 + 0.025 * math.cos(f * 0.75 + (0 if sx > 0 else 2.2))),
               V(sx * 1.0, 0.2, -0.3), "root", panic)
        c[f"hand{side}.bend"] = -20 * panic * sw; fingers(c, side, 10)
    c["head.ry"] = 12 * panic * math.sin(f * 0.45)
    # 'all right, all right': palms out, pushing twice
    push = pulses(f, N, [(104, 1.0), (118, 0.8)], decay=3.0, loop=False)
    for side, sx in (("L", 1), ("R", -1)):
        if give > 0:
            arm_ik(c, side, V(sx * 0.062, 0.282, 0.130 + 0.018 * push), V(sx * 1.0, -0.5, -0.3), "root", give)
            c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 0), -70, give); c[f"hand{side}.twist"] = 0
            fingers(c, side, lerp(10, 2, give))
    c["chest.rx"] += -4 * give; c["spine.rx"] = -3 * give; c["head.rx"] += 4 * give; c["hips.tz"] = -0.006 * give
    c["head.rz"] = 6 * give
    # hops: feet leave the page, knees up
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * 0.008, planted_ankle_y(rig, side, 0) + 0.018 * air, b.z)
        c[f"foot{side}.pitch"] = 18 * air
    c["eyelids.sy"] = 1.0
    blink(c, f, N, [130], loop=False)
    return c


@clip("pharaoh", "sneaky_no", 80, False, markers={"rub": 8, "no": 44},
      notes="'Heh heh... changed my mind!': hunches in, rubs his hands together at his chest with a sly sideways "
            "look, then straightens, the right hand comes up by his face with the finger straight and wags 'no-no-no' "
            "(three wags), head tilted, left hand on the hip; holds the last wag")
def pharaoh_sneaky_no(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.2)
    hunch = ease_io(f / 8) * (1 - ease_io((f - 32) / 10))
    up = ease_io((f - 32) / 10)
    rub = math.sin(f * 1.1) * hunch
    c["chest.rx"] += 8 * hunch; c["spine.rx"] = 4 * hunch; c["shoulderL.raise"] = 4 * hunch; c["shoulderR.raise"] = 4 * hunch
    c["head.rx"] += 6 * hunch; c["head.ry"] = -14 * hunch + 8 * up; c["head.rz"] = 8 * hunch - 8 * up
    chest_hand(c, "L", V(0.008 + 0.006 * rub, -0.040, 0.050), hunch, V(1.0, -0.7, 0.0))
    chest_hand(c, "R", V(-0.008 + 0.006 * rub, -0.044, 0.052), hunch, V(-1.0, -0.7, 0.0))
    fingers(c, "L", 20); fingers(c, "R", 20)
    if up > 0:
        hw = up
        arm_ik(c, "L", V(0.064, 0.212, -0.004), V(1.0, 0.25, -0.55), "root", hw)
        c["handL.bend"] = 30 * hw; fingers(c, "L", lerp(20, 70, hw))
        wag = 18 * math.sin(2 * math.pi * (f - 42) / 10) * ease_io((f - 40) / 4) * (1 - ease_io((f - 66) / 8))
        arm_ik(c, "R", V(-0.044, 0.320, 0.060), V(-1.0, -0.6, -0.2), "root", hw)
        c["handR.bend"] = -10; c["handR.twist"] = -20 + wag * 0.4; fingers(c, "R", 30)
        c["forearmR.twist"] = wag
    c["jaw.rx"] = 3 * bump(f, 4, 30)
    blink(c, f, N, [26], loop=False, base=1.8)
    stand_feet(rig, c, spread=0.008, pitchL=6 * hunch)
    return c


# --- sitting on the dais edge (story mark PH_PALACE (-0.36, -0.30), dais upper step top 0.030 at z <= -0.378 world)
SIT_HIP = V(0.0, 0.062, -0.072)           # hip joint (root-local) while seated on the step edge


def sit_legs(rig, c, w=1.0, feet_z=0.040, spread=0.010, hip=SIT_HIP):
    """Blend from standing (0) to seated on a low step behind him (1): hips to `hip`, feet on the page in front."""
    hy = hip.y - rig.head["thighL"].y
    c["hips.ty"] = c.get("hips.ty", 0.0) + hy * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + hip.z * w
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * spread * w, planted_ankle_y(rig, side, 0), lerp(b.z, feet_z, w))
        c[f"foot{side}.pitch"] = 0
        c[f"pole.leg{side}"] = V(sx * 0.25, 0.3, 1)


@clip("pharaoh", "sad_sit", 180, True,
      notes="real sorrow, no comedy: sits on the edge of his dais (hip joint 0.062 up, 0.072 behind the root; the "
            "dais step top is 0.030), knees up, elbows on his knees and his face in his hands; very slow heavy "
            "breathing with one long shuddering exhale, the head lifts once from the hands to stare at nothing and "
            "sinks again, a slow small head shake; lappets hang still")
def pharaoh_sad_sit(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=1.3)
    c["chest.rx"] += 3; c["head.rx"] = 0
    sit_legs(rig, c)
    lift = K([(0, 0), (70, 0), (86, 1), (112, 1), (130, 0), (180, 0)], f, N, True)
    exhale = K([(0, 0), (30, 0), (40, 1), (52, 1), (70, -0.6), (90, 0), (180, 0)], f, N, True)
    shudder = pulses(f, N, [(52, 0.6), (57, 0.4), (61, 0.3)], decay=2.0)
    c["hips.rx"] = 14; c["spine.rx"] = 16 - 4 * lift; c["chest.rx"] += 14 - 6 * lift + 3 * exhale - 1.5 * shudder
    c["shoulderL.raise"] += -3 + 3 * exhale; c["shoulderR.raise"] += -3 + 3 * exhale
    c["neck.rx"] = 14 - 10 * lift; c["head.rx"] += 18 - 20 * lift
    sh = [(0, 0), (140, 0), (148, 5), (156, -5), (164, 3), (172, 0), (180, 0)]
    c["head.ry"] = K(sh, f, N, True) + 3 * lift
    # face in hands (hands in head space would follow; chest space keeps the elbows on the knees steady)
    for side, sx in (("L", 1), ("R", -1)):
        face = V(sx * 0.016, 0.060 - 0.020 * lift, 0.068 - 0.006 * lift)
        chest_hand(c, side, face, 1.0, V(sx * 0.6, -1.0, 0.3))
        c[f"hand{side}.bend"] = -20 + 30 * lift; c[f"hand{side}.twist"] = sx * 10
        fingers(c, side, 20 + 20 * lift)
    blink(c, f, N, [20, 96, 104], base=2.4, slow=2.2)
    c["nemes1L.rx"] = 2; c["nemes1R.rx"] = 2
    return c


@clip("pharaoh", "tantrum", 105, False, markers={"stamp1": 36, "stamp2": 50, "stamp3": 64, "point": 84},
      notes="'Wait! Who's going to make my bricks?!': from sitting on the dais (frame 0 = sad_sit pose, hands down) "
            "he jumps up, fists balled and shaking by his shoulders, stamps three times (L, R, L - each stamp a big "
            "knee lift and a jolt through the body, lappets bouncing), then flings the right arm forward pointing "
            "('After them!'), left fist on the hip; holds")
def pharaoh_tantrum(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.2)
    s0 = pharaoh_sad_sit(rig, 0, 180)
    up = ease_io((f - 6) / 12)
    sitw = 1 - up
    sit_legs(rig, c, w=sitw)
    pop = bump(f, 12, 24)
    c["hips.ty"] += 0.020 * pop
    for k in ("hips.rx", "spine.rx", "chest.rx", "neck.rx", "head.rx"):
        c[k] = lerp(c.get(k, 0.0), s0.get(k, 0.0), sitw * sitw)
    c["chest.rx"] += -6 * up; c["head.rx"] += -6 * up
    stamps = [(30, "L"), (44, "R"), (58, "L")]
    fists = ease_io((f - 10) / 8) * (1 - ease_io((f - 72) / 8))
    shake = math.sin(f * 1.7)
    face = 1 - ease_io((f - 2) / 10)
    for side, sx in (("L", 1), ("R", -1)):
        if face > 0 and fists < 0.01:
            chest_hand(c, side, V(sx * 0.016, 0.060 - 0.040 * (1 - face), 0.068), 1.0, V(sx * 0.6, -1.0, 0.3))
        else:
            arm_ik(c, side, V(sx * 0.072, 0.282 + 0.008 * shake * sx, 0.040), V(sx * 1.0, -0.6, -0.3), "root", 1.0)
        fingers(c, side, 24 + 60 * fists); c[f"hand{side}.bend"] = 20 * fists - 20 * face
    jolt = 0.0
    for t, side in stamps:
        sx = 1 if side == "L" else -1
        k = bump(f, t - 2, t + 6)
        jolt += pulses(f, N, [(t + 6, 1.0)], decay=2.0, loop=False)
        b = rig.head["foot" + side]
        key = f"ik.leg{side}"
        if key not in c or f >= 18:
            c[key] = V(b.x + sx * 0.008, planted_ankle_y(rig, side, 0), b.z + 0.004)
            c[f"foot{side}.pitch"] = 0
        if k > 0:
            c[key] = c[key] + V(0, 0.040 * k, 0.010 * k)
            c[f"foot{side}.pitch"] = -10 * k
        c[f"pole.leg{side}"] = V(sx * 0.15, 0, 1)
    if f >= 18:
        for side, sx in (("L", 1), ("R", -1)):
            if f"ik.leg{side}" not in c:
                b = rig.head["foot" + side]
                c[f"ik.leg{side}"] = V(b.x + sx * 0.008, planted_ankle_y(rig, side, 0), b.z + 0.004)
    c["hips.ty"] += -0.006 * jolt; c["chest.rx"] += 4 * jolt; c["head.rx"] += 5 * jolt
    c["head.ry"] = 8 * math.sin(f * 0.5) * fists
    c["jaw.rx"] = 6 * fists
    pt = ease_io((f - 74) / 8)
    jab = bump(f, 80, 92)
    if pt > 0:
        point_arm(c, "R", pt, V(-0.060, 0.268 + 0.008 * jab, 0.160 + 0.010 * jab))
        arm_ik(c, "L", V(0.064, 0.212, -0.004), V(1.0, 0.25, -0.55), "root", pt)
        c["handL.bend"] = 30 * pt; fingers(c, "L", lerp(84, 70, pt))
    c["chest.ry"] = -10 * pt; c["hips.tz"] = c.get("hips.tz", 0.0) + 0.006 * pt
    blink(c, f, N, [96], loop=False)
    c["eyelids.sy"] = min(c["eyelids.sy"], 1.0) if f < 90 else c["eyelids.sy"]
    return c


def chariot_xf(rz=0.0, rx=0.0, pivot=None, lift=0.0):
    """Rigid chariot transform (design root space): rotation rx (pitch) then rz (roll) about `pivot`, plus a lift.
    Returns (Rd 3x3, P, t_bone) - t_bone is the chariot bone's tx/ty/tz for that pivot."""
    P = Vector(pivot) if pivot is not None else V(0, 0, 0)
    Rd = Matrix.Rotation(math.radians(rx), 3, 'X') @ Matrix.Rotation(math.radians(rz), 3, 'Z')
    H = V(0, CHARIOT_FLOOR, 0)
    t = (P - Rd @ P) - (H - Rd @ H) + V(0, lift, 0)
    return Rd, P, t


def chariot_apply(c, rz=0.0, rx=0.0, pivot=None, lift=0.0):
    Rd, P, t = chariot_xf(rz, rx, pivot, lift)
    c["chariot.rx"] = rx; c["chariot.rz"] = rz
    c["chariot.tx"], c["chariot.ty"], c["chariot.tz"] = t.x, t.y, t.z
    return lambda p: P + Rd @ (Vector(p) - P) + V(0, lift, 0)


def ride_feet(rig, c, xf, crouch=0.0, spread=0.006, fwdL=0.010, fwdR=-0.006):
    for side, sx, fw in (("L", 1, fwdL), ("R", -1, fwdR)):
        b = rig.head["foot" + side]
        p = V(b.x + sx * spread, planted_ankle_y(rig, side, 0) + CHARIOT_FLOOR, b.z + fw)
        c[f"ik.leg{side}"] = xf(p); c[f"foot{side}.pitch"] = 0
        c[f"pole.leg{side}"] = V(sx * 0.2, 0, 1)


P_RIDE_N = 48
P_RIDE_SPEED = 2 * math.pi * 0.034 / (P_RIDE_N / FPS)      # one wheel turn per loop (r = 0.034)


@clip("pharaoh", "ride", P_RIDE_N, True, props=["chariot", "wheelL"], natural=P_RIDE_SPEED,
      notes="standing in the chariot (hips +0.035: soles on the chariot floor; the chariot stays on the page), fists "
            "forward over the front rail holding invisible reins, leaning forward, knees springy - bouncing twice per "
            "loop with the rattle, chin up and grinning; the chariot body jiggles a little (wheels stay on the page), "
            "the left wheel turns once per loop (= natural speed 0.134 u/s); lappets and back tail blown back")
def pharaoh_ride(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=0.5)
    ph = 2 * math.pi * f / N
    bounce = 0.5 - 0.5 * math.cos(2 * ph)
    rattle = 0.6 * math.sin(4 * ph + 0.3)
    xf = chariot_apply(c, rz=0.8 * math.sin(2 * ph + 0.5), rx=0.6 * math.sin(4 * ph), pivot=V(0, 0, -0.004),
                       lift=0.0006 * (1 + math.sin(4 * ph)))
    c["wheelL.rx"] = 360.0 * f / N
    ride_feet(rig, c, xf)
    c["hips.ty"] = CHARIOT_FLOOR - 0.008 - 0.006 * bounce
    c["hips.tz"] = 0.004
    c["hips.rx"] = 6; c["spine.rx"] = 6 + 1.5 * bounce; c["chest.rx"] += 2 + 1 * rattle
    c["head.rx"] = -8 + 2 * bounce - 1.0 * rattle; c["neck.rx"] = -2
    c["head.rz"] = 2 * math.sin(2 * ph + 1.0)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.030, 0.205 + CHARIOT_FLOOR - 0.006 * bounce + 0.003 * rattle, 0.090), V(sx * 0.8, -0.8, -0.2))
        c[f"hand{side}.bend"] = 10; c[f"hand{side}.twist"] = sx * 60; fingers(c, side, 75)
    c["jaw.rx"] = 3
    g = loop_gusts(f, N)
    c["wind.nemesBack"] = V(0, 0.15, -1.0) * (0.35 * g)
    c["wind.nemes1L"] = V(0.4, 0.2, -1.0) * (0.20 * g); c["wind.nemes1R"] = V(-0.4, 0.2, -1.0) * (0.20 * g)
    blink(c, f, N, [30], base=1.3)
    return c


@clip("pharaoh", "ride_idle", 90, True, extra=True, props=["chariot", "wheelL"],
      notes="EXTRA: standing in the stopped chariot (hips +0.035), reins in his fists, impatient: drums his fingers, "
            "leans to look ahead, bobs on his toes. The director hands a finished locomotion move over to `idle`, "
            "which would sink him into the chariot floor - Story should play this after each `ride` move instead")
def pharaoh_ride_idle(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=0.8)
    xf = chariot_apply(c, 0.0, 0.0, V(0, 0, 0))
    c["wheelL.rx"] = 0.0
    ride_feet(rig, c, xf)
    look = K([(0, 0), (20, 0), (32, 1), (56, 1), (66, 0), (90, 0)], f, N, True)
    bob = bump(f, 60, 72) + bump(f, 74, 86)
    c["hips.ty"] = CHARIOT_FLOOR - 0.004 + 0.004 * bob; c["hips.tz"] = 0.002
    c["spine.rx"] = 3 + 4 * look; c["neck.rx"] = -4 * look; c["head.rx"] = -6 - 2 * look
    c["head.ry"] = 6 * wave(f, N, 1, 0.2)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.032, 0.214 + CHARIOT_FLOOR, 0.082), V(sx * 0.8, -0.8, -0.2))
        c[f"hand{side}.bend"] = 10; c[f"hand{side}.twist"] = sx * 60
    fingers(c, "L", 75); fingers(c, "R", 60 + 15 * math.sin(2 * math.pi * 6 * f / N))
    blink(c, f, N, [44], base=1.5)
    ride_feet(rig, c, xf)
    for side in "LR":
        c[f"foot{side}.pitch"] = -10 * bob
    return c


@clip("pharaoh", "wobble", 84, False, props=["chariot"], markers={"tilt": 6, "crouch": 64},
      notes="the left wheel is gone (wheelL hidden by the timeline just before): the chariot drops onto its left "
            "side (tipping about the right wheel, up to 14 deg), rocks back and drops again; Pharaoh windmills both "
            "arms, knees wobbling, then crouches down clinging to the front rail with both hands, head ducked, "
            "peeking; holds crouched (soles stay on the tilted chariot floor)")
def pharaoh_wobble(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.2)
    tilt = K([(0, 0), (6, -9), (12, -6.5), (20, -11), (28, -7), (36, -12.5), (46, -10.5), (58, -14), (70, -13), (84, -13.5)], f)
    pitch = K([(0, 0), (8, 2.5), (18, -1.5), (30, 2), (44, -1), (58, 2.5), (84, 2.0)], f)
    xf = chariot_apply(c, rz=tilt, rx=pitch, pivot=CH_PIVOT_R)
    crouch = ease_io((f - 50) / 16)
    mill = ease_io((f - 4) / 6) * (1 - ease_io((f - 50) / 10))
    ride_feet(rig, c, xf, spread=0.008 + 0.006 * crouch)
    # body: balance against the tilt (leans right = counter), knees bend, then crouch
    c["hips.ty"] = CHARIOT_FLOOR - 0.010 * (1 - crouch) - 0.070 * crouch + 0.004 * math.sin(f * 0.9) * mill
    c["hips.tx"] = -0.006 * mill + xf(V(0, 0.2, 0)).x * 0.4
    c["hips.rz"] = 0.6 * tilt * (1 - 0.5 * crouch); c["spine.rz"] = -0.8 * tilt * (1 - crouch)
    c["chest.rz"] = -0.6 * tilt * (1 - crouch) + 6 * math.sin(f * 0.6) * mill
    c["hips.rx"] = 18 * crouch; c["spine.rx"] = 14 * crouch; c["chest.rx"] += 10 * crouch
    c["head.rx"] = -10 * mill + 6 * crouch; c["neck.rx"] = 6 * crouch
    c["head.ry"] = 10 * math.sin(f * 0.4) * mill
    for side, sx, ph0 in (("L", 1, 0.0), ("R", -1, math.pi)):
        a = f * 0.55 + ph0
        tgt = V(sx * (0.100 + 0.030 * math.cos(a)), 0.300 + 0.070 * math.sin(a), 0.020 + 0.030 * math.cos(a))
        arm_ik(c, side, tgt, V(sx * 1.0, -0.3, -0.4), "root", mill)
        rail = xf(V(sx * 0.030, 0.150, 0.052))
        if crouch > 0:
            arm_ik(c, side, rail, V(sx * 1.0, -0.2, 0.0), "root", crouch) if mill < 0.01 else None
            if mill >= 0.01:
                c[f"ik.arm{side}"] = vlerp(tgt, rail, crouch); c[f"ikw.arm{side}"] = max(mill, crouch)
        c[f"hand{side}.bend"] = 20 * crouch; fingers(c, side, lerp(8, 70, crouch))
    c["eyelids.sy"] = 1.0
    blink(c, f, N, [76], loop=False)
    c["jaw.rx"] = 8 * mill + 4 * crouch
    c["wind.nemesBack"] = V(-0.5, 0.2, -0.6) * (0.3 * mill)
    return c


SOGGY_HIP = V(0.0, 0.0305, -0.010)


def soggy_pose(rig, c, w=1.0):
    """Sitting on the wet sand, legs out straight in front (slightly apart, toes up), hands limp on the sand."""
    hy = SOGGY_HIP.y - rig.head["thighL"].y
    c["hips.ty"] = c.get("hips.ty", 0.0) + hy * w; c["hips.tz"] = c.get("hips.tz", 0.0) + SOGGY_HIP.z * w
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        legl = rig.length["thigh" + side] + rig.length["shin" + side]
        ank = V(b.x + sx * 0.020, 0.020, SOGGY_HIP.z + legl * 0.985)
        c[f"ik.leg{side}"] = vlerp(V(b.x, planted_ankle_y(rig, side, 0), b.z), ank, w)
        c[f"foot{side}.pitch"] = -35 * w
        c[f"pole.leg{side}"] = V(sx * 0.1, 1.0, 0.2)


@clip("pharaoh", "soggy_sit", 120, True,
      notes="washed up: sitting on the wet sand, legs straight out in front, toes up; slumped, arms hanging, hands "
            "limp on the sand by his hips; the nemes lappets droop flat (pulled down/inward), head low; shivers in "
            "little bursts (teeth chatter in the jaw), one big shaky sigh, a sulky look up; slow wet blinks")
def pharaoh_soggy_sit(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=1.0)
    c["chest.rx"] += 3; c["head.rx"] = 0
    soggy_pose(rig, c)
    burst = K([(0, 1.0), (14, 1.0), (20, 0.2), (56, 0.2), (62, 1.0), (78, 1.0), (84, 0.2), (120, 1.0)], f, N, True)
    sv = shiver(f, N, 1.0) * burst
    sigh = K([(0, 0), (86, 0), (96, 1), (102, 1), (114, -0.3), (120, 0)], f, N, True)
    look = K([(0, 0), (30, 0), (38, 1), (50, 1), (56, 0), (120, 0)], f, N, True)
    c["hips.rx"] = -6; c["spine.rx"] = 10; c["chest.rx"] += 10 - 3 * sigh + 0.8 * sv
    c["shoulderL.raise"] += 2.5 * sv + 3 * sigh - 2; c["shoulderR.raise"] += -2.5 * sv + 3 * sigh - 2
    c["neck.rx"] = 10 - 8 * look; c["head.rx"] += 14 - 14 * look + 1.2 * sv; c["head.ry"] = -6 * look
    c["head.rz"] = 5 + 1.0 * sv
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.070, 0.040 + 0.002 * sv * sx, 0.016), V(sx * 1.0, -0.2, -0.4))
        c[f"hand{side}.bend"] = 20; fingers(c, side, 20)
    c["jaw.rx"] = 2.5 + 1.5 * sv
    c["nemes1L.rx"] = 14; c["nemes1R.rx"] = 14; c["nemes1L.rz"] = -8; c["nemes1R.rz"] = 8
    c["nemesBack.rx"] = 8
    blink(c, f, N, [24, 70, 108], base=3.2, slow=1.8)
    return c


@clip("pharaoh", "sneeze", 72, False, markers={"ah1": 10, "ah2": 26, "achoo": 40},
      notes="'Ah... ah... ACHOO!': from soggy_sit, two growing inhales (head tips back, chest rises, eyes squeeze), "
            "a hold, then a big forward sneeze that jerks the whole upper body forward and down, lappets flapping, a "
            "shake of the head, and he slumps back into the soggy_sit pose (ends = soggy_sit frame 0)")
def pharaoh_sneeze(rig, f, N):
    c = pharaoh_soggy_sit(rig, 0, 120)
    a1 = bump(f, 2, 20)
    a2 = ease_io((f - 16) / 14) * (1 - ease_io((f - 38) / 3))
    sn = bump(f, 37, 54)
    snap = pulses(f, N, [(39, 1.0)], decay=3.0, loop=False)
    shake = math.sin(f * 1.4) * bump(f, 44, 62)
    c["chest.rx"] += -4 * a1 - 7 * a2 + 14 * snap + 3 * sn
    c["spine.rx"] += -2 * a2 + 6 * snap
    c["head.rx"] += -10 * a1 - 18 * a2 + 26 * snap + 4 * sn; c["neck.rx"] += -4 * a2 + 8 * snap
    c["head.ry"] += 10 * shake
    c["shoulderL.raise"] += 4 * a1 + 6 * a2 - 4 * snap; c["shoulderR.raise"] += 4 * a1 + 6 * a2 - 4 * snap
    c["jaw.rx"] += 6 * a1 + 10 * a2 + 4 * snap
    c["eyelids.sy"] = 3.2 + 9.0 * max(a2, snap)
    c["nemes1L.rx"] += -10 * snap; c["nemes1R.rx"] += -10 * snap
    return c


@clip("pharaoh", "angry", 90, True,
      notes="furious: fists clenched and shaking at his sides, leaning forward, cheeks puffed (face decal), little "
            "stamps of the right foot, head shaking, shoulders up")
def pharaoh_angry(rig, f, N):
    c = p_base(rig, f, N, cycles=3, amp=1.4)
    sh = math.sin(2 * math.pi * 9 * f / N)
    c["chest.rx"] += 6; c["spine.rx"] = 4; c["head.rx"] += 6; c["shoulderL.raise"] += 6; c["shoulderR.raise"] += 6
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.074, 0.190 + 0.004 * sh * sx, 0.020), V(sx * 1.0, -0.6, -0.4))
        fingers(c, side, 85); c[f"hand{side}.bend"] = 15
    c["head.ry"] = 6 * math.sin(2 * math.pi * 3 * f / N)
    st = max(bump(f, 10, 18), bump(f, 40, 48), bump(f, 64, 72))
    stand_feet(rig, c, spread=0.008, liftR=0.016 * st)
    c["jaw.rx"] = 0.0
    blink(c, f, N, [30])
    return c


# =============================================================================================== MIRIAM
def mi_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.4 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.0 * b * amp; c["shoulderR.raise"] = 1.0 * b * amp
    c["neck.rx"] = 0.6 * b * amp
    c["upperArmL.raise"] = -22; c["upperArmR.raise"] = -22
    c["upperArmL.bend"] = 8; c["upperArmR.bend"] = 8
    c["forearmL.bend"] = 26; c["forearmR.bend"] = 26
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 22); fingers(c, "R", 22)
    c["head.rx"] = -2
    return c


def mi_hands(c, at, wring=0.0, w=1.0, space="root"):
    arm_ik(c, "L", at + V(0.010 + 0.002 * wring, 0.000, -0.004), V(0.7, -0.6, -0.4), space, w)
    arm_ik(c, "R", at + V(-0.010 + 0.002 * wring, -0.004, 0.000), V(-0.7, -0.6, -0.4), space, w)


@clip("miriam", "idle", 150, True,
      notes="lively even at rest: light weight shifts with a little knee bounce, hands loosely together, quick "
            "glances round (head leads, a curious tilt), tucks the braid back once with her left hand; quick "
            "blinks incl. a double; scarf and braid swing late")
def miriam_idle(rig, f, N):
    c = mi_base(rig, f, N, cycles=3, amp=0.9)
    sh = [(0, -0.5), (20, -0.5), (36, 1.0), (76, 1.0), (96, -0.8), (130, -0.8), (150, -0.5)]
    s = K(sh, f, N, True); sl = KL(sh, f, N, True, lag=6)
    c["hips.tx"] = 0.004 * s; c["hips.rz"] = -2.6 * s; c["spine.rz"] = 1.5 * sl; c["chest.rz"] = 1.0 * sl
    c["hips.ty"] = -0.0015 * abs(s)
    look = [(0, 0), (24, 0), (30, -14), (48, -14), (54, 10), (70, 10), (78, 0), (150, 0)]
    c["neck.ry"] = 0.4 * K(look, f, N, True); c["head.ry"] = 0.6 * KL(look, f, N, True, lag=3)
    c["head.rz"] = 4 * K([(0, 0), (30, 1), (48, 1), (54, -1), (70, -1), (80, 0), (150, 0)], f, N, True)
    tuck = ease_io((f - 96) / 8) * (1 - ease_io((f - 116) / 10))
    mi_hands(c, V(0.0, 0.142 + 0.002 * wave(f, N, 3), 0.036))
    if tuck > 0:
        c["ik.armL"] = vlerp(c["ik.armL"], V(0.030, 0.228, 0.030), tuck)
        c["handL.bend"] = 6 - 20 * tuck
        c["head.rz"] += -6 * tuck
    fingers(c, "L", 30 - 10 * tuck); fingers(c, "R", 32)
    blink(c, f, N, [12, 58, 63, 118])
    stand_feet(rig, c, spread=0.002, pitchL=K([(0, 0), (36, 0), (46, 8), (76, 8), (86, 0), (150, 0)], f, N, True))
    return c


MI_WALK = (0.064, 0.58)


@clip("miriam", "walk", 28, True, markers={"contactL": 0, "contactR": 14}, speed=MI_WALK,
      notes="quick light steps (~129 steps/min): springy bounce, small skips of the heels, arms swinging freely "
            "with lagging hands, chest counter-turn, head bright and steady; braid and scarf bounce late")
def miriam_walk(rig, f, N):
    c = mi_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=MI_WALK[0], lift=0.012, duty=MI_WALK[1], heel=12, toeoff=26)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0035 + 0.0034 * math.cos(2 * ph - 0.5)
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -7 * math.sin(ph - 0.35); c["head.ry"] = 3 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.4 * math.cos(ph); c["chest.rz"] = -1.6 * math.cos(ph - 0.5)
    c["spine.rx"] = 1; c["head.rx"] = -3 + 1.5 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 8 - 20 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 20 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 30 - 12 * math.sin(ph - 1.0); c["forearmR.bend"] = 30 + 12 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 12 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 12 * math.sin(ph - 1.6)
    blink(c, f, N, [20])
    return c


@clip("miriam", "talk", 96, True,
      notes="bright and quick: both hands talk (right palm-up offers, left hand to her chest), head tilts and nods "
            "on the stressed syllables, a little bounce; jaw in an irregular rhythm (lip sync overrides it)")
def miriam_talk(rig, f, N):
    c = mi_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 73, amp=(5, 13), dur=(2.8, 5.5))
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=8)
    btl = beat_curve(beats, f - 3, N, width=9)
    c["head.rx"] = -2 + 4 * bt; c["head.ry"] = 6 * wave(f, N, 1, 0.1); c["head.rz"] = 5 * wave(f, N, 1, 0.35)
    pa = K([(0, 0.2), (10, 0.9), (38, 1.0), (52, 0.15), (88, 0.1), (96, 0.2)], f, N, True)
    pb = K([(0, 0.0), (44, 0.0), (56, 1.0), (84, 0.9), (94, 0.0), (96, 0.0)], f, N, True)
    lift = pa * (0.75 + 0.25 * btl)
    c["upperArmR.raise"] = -22 + 4 * lift; c["upperArmR.bend"] = 8 + 40 * lift
    c["forearmR.bend"] = 26 + 54 * lift; c["forearmR.twist"] = 10 - 82 * lift
    c["handR.bend"] = 6 - 22 * btl * pa; fingers(c, "R", 28 - 24 * btl * pa)
    chest_hand(c, "L", V(0.012, -0.004 + 0.004 * btl, 0.044), pb)
    c["hips.ty"] = -0.002 * bt
    blink(c, f, N, [7, 61])
    stand_feet(rig, c, spread=0.002)
    return c


@clip("miriam", "carry_brick", 90, True,
      notes="a slave's load: both hands hold a heavy brick against her chest (no brick prop exists in the rig - the "
            "hands mime a block 0.045 wide), bent forward under it, knees soft, shuffling in place with tiny heavy "
            "steps, hitching the brick up once, a tired head-shake and breath; slow tired blinks")
def miriam_carry_brick(rig, f, N):
    c = mi_base(rig, f, N, cycles=2, amp=1.2)
    ph = 2 * math.pi * f / N
    hitch = bump(f, 50, 62)
    sag = 0.5 - 0.5 * math.cos(2 * ph)
    c["hips.ty"] = -0.008 - 0.002 * sag; c["hips.rx"] = 6; c["spine.rx"] = 9 - 3 * hitch; c["chest.rx"] += 8 - 2 * hitch
    c["neck.rx"] = -4; c["head.rx"] = 4 + 2 * sag
    c["hips.rz"] = 2 * math.sin(ph); c["chest.rz"] = -1.2 * math.sin(ph - 0.4)
    c["head.ry"] = 6 * bump(f, 70, 86) - 6 * bump(f, 76, 90)
    brick = V(0.0, 0.176 + 0.006 * hitch - 0.002 * sag, 0.052)
    arm_ik(c, "L", brick + V(0.024, 0.0, 0.0), V(0.9, -0.6, -0.2))
    arm_ik(c, "R", brick + V(-0.024, 0.0, 0.0), V(-0.9, -0.6, -0.2))
    c["handL.twist"] = -60; c["handR.twist"] = 60; c["handL.bend"] = 10; c["handR.bend"] = 10
    fingers(c, "L", 45); fingers(c, "R", 45)
    # shuffle in place: tiny alternating steps (lift and set down on the same spot)
    for side, sx, off in (("L", 1, 0.0), ("R", -1, 0.5)):
        p = (f / N * 2 + off) % 1.0
        b = rig.head["foot" + side]
        lift = 0.006 * bump(p * 100, 0, 30)
        c[f"ik.leg{side}"] = V(b.x + sx * 0.004, planted_ankle_y(rig, side, 0) + lift, b.z + 0.004 * (side == "L"))
        c[f"foot{side}.pitch"] = 8 * bump(p * 100, 0, 30)
    blink(c, f, N, [20, 66], base=1.5, slow=1.5)
    return c


@clip("miriam", "pray_stand", 120, True,
      notes="'Oh God... can you hear us?': hands clasped tight at her chest, head bowed, eyes mostly closed, a slow "
            "sway, one tremble of the shoulders (holding back tears), lifts her face upward once and bows again")
def miriam_pray_stand(rig, f, N):
    c = mi_base(rig, f, N, cycles=2, amp=1.0)
    up = K([(0, 0), (50, 0), (62, 1), (82, 1), (94, 0), (120, 0)], f, N, True)
    sob = pulses(f, N, [(24, 0.8), (30, 0.5)], decay=2.5)
    s = wave(f, N, 1, 0.0)
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -1.6 * s; c["spine.rz"] = 1.0 * s
    c["chest.rx"] += 4 - 6 * up - 1.2 * sob; c["shoulderL.raise"] += 2 * sob + 2; c["shoulderR.raise"] += 2 * sob + 2
    c["neck.rx"] = 8 - 14 * up; c["head.rx"] = 14 - 26 * up
    chest_hand(c, "L", V(0.010, -0.010, 0.046)); chest_hand(c, "R", V(-0.008, -0.014, 0.048))
    c["handL.bend"] = -20; c["handR.bend"] = -20; fingers(c, "L", 60); fingers(c, "R", 60)
    c["eyelids.sy"] = lerp(9.5, 2.0, up)
    blink(c, f, N, [70], base=c["eyelids.sy"])
    stand_feet(rig, c, spread=0.001)
    return c


@clip("miriam", "hurry_wave", 72, True,
      notes="'Everyone, eat up! Shoes on!': bustling - both arms beckon 'come on, come on' in turn (big scooping "
            "waves from out-front to her shoulder), looking left then right over the people, bouncing on her toes, a "
            "quick step on the spot; scarf and braid swing")
def miriam_hurry_wave(rig, f, N):
    c = mi_base(rig, f, N, cycles=2, amp=0.6)
    ph = 2 * math.pi * f / N
    look = math.sin(ph)
    c["head.ry"] = 24 * look; c["neck.ry"] = 10 * math.sin(ph - 0.3); c["chest.ry"] = 10 * math.sin(ph - 0.6)
    c["head.rx"] = -4
    bounce = 0.5 - 0.5 * math.cos(4 * ph)
    c["hips.ty"] = -0.002 + 0.004 * bounce
    for side, sx, off in (("L", 1, 0.0), ("R", -1, 0.5)):
        p = (f / N * 2 + off) % 1.0
        scoop = math.sin(math.pi * p)          # 0 out-front -> 1 at the shoulder
        tgt = V(sx * (0.070 - 0.030 * scoop), 0.215 + 0.050 * scoop, 0.110 - 0.070 * scoop)
        arm_ik(c, side, tgt, V(sx * 1.0, -0.5, -0.3))
        c[f"hand{side}.bend"] = -30 * scoop + 10; c[f"hand{side}.twist"] = -sx * 50
        fingers(c, side, 10 + 40 * scoop)
    stand_feet(rig, c, spread=0.003, pitchL=-12 * bounce, pitchR=-12 * bounce, liftL=0.003 * bounce, liftR=0.003 * bounce)
    blink(c, f, N, [30])
    return c


@clip("miriam", "joy", 60, True, markers={"hop": 16},
      notes="'We're free!': a dip, a little hop with both arms flung up (hands open), lands and bounces, laughing "
            "(jaw), braid and scarf flying")
def miriam_joy(rig, f, N):
    c = mi_base(rig, f, N, cycles=1, amp=0.4)
    dip = bump(f, 4, 16) + bump(f, 30, 40)
    air = bump(f, 12, 30)
    arms = K([(0, 0.4), (10, 0.3), (18, 1.0), (32, 1.0), (44, 0.5), (60, 0.4)], f, N, True)
    c["hips.ty"] = -0.010 * dip + 0.026 * air
    c["chest.rx"] += 3 * dip - 6 * air; c["head.rx"] = 3 * dip - 10 * air
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.080, 0.300 + 0.020 * arms, 0.030), V(sx * 1.0, -0.2, -0.3), "root", arms)
        c[f"hand{side}.bend"] = -20 * arms; fingers(c, side, 22 - 22 * arms)
    stand_feet(rig, c, spread=0.003, liftL=0.020 * air, liftR=0.020 * air, pitchL=20 * air, pitchR=20 * air)
    c["jaw.rx"] = 5 + 6 * pulses(f, N, [(20, 1.0), (28, 0.8), (38, 0.6)], decay=2.5)
    blink(c, f, N, [48])
    return c


@clip("miriam", "scared", 90, True,
      notes="the sea in front, the chariots behind: hands at her mouth, shoulders up, shrunk back with knees soft, "
            "trembling; twice glances back over her shoulder (quick head whip) and back to Moses; quick nervous blinks")
def miriam_scared(rig, f, N):
    c = mi_base(rig, f, N, cycles=3, amp=1.6)
    tr = math.sin(2 * math.pi * 15 * f / N) * 0.6
    back = K([(0, 0), (16, 0), (20, 1), (32, 1), (36, 0), (56, 0), (60, 1), (70, 1), (74, 0), (90, 0)], f, N, True)
    c["hips.tz"] = -0.008; c["hips.ty"] = -0.006
    c["chest.rx"] += 6 + 0.6 * tr; c["spine.rx"] = -3; c["shoulderL.raise"] += 7; c["shoulderR.raise"] += 7
    c["head.rx"] = 6; c["head.ry"] = 60 * back + 1.5 * tr; c["neck.ry"] = 22 * back; c["chest.ry"] = 12 * back
    c["head.rz"] = -4 * (1 - back)
    chest_hand(c, "L", V(0.010, 0.040, 0.050)); chest_hand(c, "R", V(-0.010, 0.036, 0.052))
    c["handL.bend"] = -30; c["handR.bend"] = -30; fingers(c, "L", 40 + 4 * tr); fingers(c, "R", 40 - 4 * tr)
    blink(c, f, N, [10, 44, 49, 80], slow=0.8)
    stand_feet(rig, c, spread=0.0, fwdL=-0.006, pitchR=6)
    return c


@clip("miriam", "wow", 45, False, markers={"wow": 14},
      notes="the walls of water: a gasp, both hands fly to her cheeks, she leans back with her mouth open and rises "
            "onto her toes, delighted, a little overshoot; holds hands on cheeks, beaming")
def miriam_wow(rig, f, N):
    c = mi_base(rig, f, N, cycles=1, amp=0.2)
    ant = bump(f, 0, 8)
    up = ease_io((f - 4) / 10)
    over = bump(f, 12, 26)
    c["chest.rx"] += 3 * ant - 7 * up - 2 * over; c["spine.rx"] = -4 * up; c["head.rx"] = 4 * ant - 12 * up - 3 * over
    c["hips.tz"] = -0.006 * up; c["hips.ty"] = 0.004 * up
    c["head.rz"] = 6 * up
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * 0.032, -0.022, 0.034), V(sx * 1.0, -0.6, -0.1), "head", up)
        c[f"hand{side}.bend"] = -10 * up; fingers(c, side, 22 - 12 * up)
    c["jaw.rx"] = 9 * up
    stand_feet(rig, c, spread=0.003, pitchL=-14 * up, pitchR=-14 * up)
    blink(c, f, N, [36], loop=False)
    return c


TAMB_N = 128           # 4 bars of 6/8, beats (dotted quarters) every 16 design frames; GLB time-scaled to 30/7 s


@clip("miriam", "tambourine_dance", TAMB_N, True, props=["tambourine"], timescale=SONG_K,
      markers={f"hit{i + 1}": 16 * i for i in range(8)},
      notes="Miriam's song (6/8, dotted quarter 112): the tambourine held high in the left hand, struck by the "
            "right palm on every dotted beat (8 hits per loop, marker hitN; the GLB is time-scaled so the loop is "
            "exactly 4 bars = 4.2857 s and frame 0 = a downbeat), bouncing step-hops on the beats; bar 3 is a "
            "turning hop (the root turns once round on the spot, no translation), bar 4 a high shake with a kick; "
            "head bobbing, laughing, skirt swing (hips/thighs), scarf and braid swirl")
def miriam_tambourine_dance(rig, f, N):
    c = mi_base(rig, f, N, cycles=4, amp=0.4)
    beat = 16
    bph = (f % beat) / beat
    hit = pulses(f, N, [(16 * i, 1.0 if i % 2 == 0 else 0.75) for i in range(8)], decay=2.0)
    hop = math.sin(math.pi * min(1.0, bph / 0.8)) if bph < 0.8 else 0.0
    bar = int(f // 32)
    # root turn: bar 3 (frames 64-96) one full turn, eased
    turn = 360.0 * ease_io((f - 64) / 32) if 64 <= f < 96 else (360.0 if f >= 96 else 0.0)
    c["root.ry"] = turn if f < N else 0.0
    c["hips.ty"] = -0.006 + 0.012 * hop - 0.004 * hit
    sw = math.sin(2 * math.pi * f / 32)
    c["hips.rz"] = 4 * sw; c["hips.ry"] = 8 * sw; c["chest.ry"] = -6 * sw; c["chest.rz"] = -2 * sw
    c["head.rz"] = 6 * math.sin(2 * math.pi * f / 32 + 0.6); c["head.rx"] = -6 + 4 * hit
    c["chest.rx"] += -4 + 2 * hit
    # left arm high with the tambourine (shaken up and out between beats), brought in to meet the right palm on
    # each dotted beat (Miriam's arms are short: the hit happens up-front, just left of her head)
    away = 0.5 - 0.5 * math.cos(2 * math.pi * bph)                 # 0 at the hit, 1 mid-beat
    b4 = bump(f, 96, 128)                                        # bar 4: shaken higher (eased so the seam is smooth)
    shake = math.sin(f * 2.2) * b4
    hi = 0.012 * b4
    meetL, highL = V(0.064, 0.322, 0.040), V(0.074, 0.366 + hi, 0.030 + 0.006 * sw)
    arm_ik(c, "L", meetL.lerp(highL, away) + V(0, 0.004 * shake, 0), V(1.0, -0.2, -0.5))
    c["handL.bend"] = 10 + 10 * shake; c["handL.twist"] = -20
    fingers(c, "L", 55)
    meetR, outR = V(0.040, 0.318, 0.050), V(-0.092, 0.236, 0.060)
    c["spine.rz"] = c.get("spine.rz", 0.0) - 5 * (1 - away); c["chest.rz"] += -6 * (1 - away)
    arm_ik(c, "R", meetR.lerp(outR, away ** 0.8), V(-1.0, -0.4, -0.3))
    c["handR.bend"] = -30 + 20 * away; c["handR.twist"] = 0; fingers(c, "R", 6)
    c["head.rz"] += -6 * (1 - away); c["head.ry"] = 8 * (1 - away)
    # feet: step-hops on the beats (alternate feet lead), kick on bar 4's second beat
    for side, sx in (("L", 1), ("R", -1)):
        lead = (int(f // beat) % 2 == (0 if side == "L" else 1))
        kick = bump(f, 112, 126) if side == "R" else 0.0
        c[f"ik.leg{side}"] = V(rig.head["foot" + side].x + sx * 0.004, planted_ankle_y(rig, side, 0) + 0.014 * hop * (1.0 if lead else 0.4) + 0.020 * kick,
                               rig.head["foot" + side].z + 0.012 * hop * (1 if lead else 0) + 0.040 * kick)
        c[f"foot{side}.pitch"] = 16 * hop * (1 if lead else 0.3) - 20 * kick
    c["jaw.rx"] = 6 + 5 * hit
    blink(c, f, N, [40, 100])
    return c


@clip("miriam", "wave", 48, True,
      notes="a big happy wave with the right hand high (wrist-led, three waves per loop), left hand on her chest, "
            "bouncing a little, head tilt")
def miriam_wave(rig, f, N):
    c = mi_base(rig, f, N, cycles=1, amp=0.5)
    arm_ik(c, "R", V(-0.082 - 0.008 * wave(f, N, 3, 0.0), 0.300, 0.036), V(-1.0, -0.6, -0.2))
    c["handR.twist"] = 70; c["handR.bend"] = 24 * wave(f, N, 3, 0.15); fingers(c, "R", 4)
    chest_hand(c, "L", V(0.012, -0.010, 0.044))
    c["head.rz"] = 6; c["hips.ty"] = 0.002 * wave(f, N, 3, 0.2)
    c["jaw.rx"] = 4
    blink(c, f, N, [20])
    stand_feet(rig, c, spread=0.002)
    return c


@clip("miriam", "clap", 40, True, markers={"clap1": 7, "clap2": 19, "clap3": 31},
      notes="happy clapping in front of her chest, three claps per loop, bouncing on her knees, head bobbing")
def miriam_clap(rig, f, N):
    c = mi_base(rig, f, N, cycles=1, amp=0.4)
    hits = [7, 19, 31]
    hit = pulses(f, N, [(h, 1.0) for h in hits], decay=2.0)
    open_ = min(abs(((f - h + N / 2) % N) - N / 2) for h in hits) / 6.0
    open_ = min(1.0, open_)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * (0.008 + 0.026 * open_), 0.206 + 0.006 * open_, 0.060), V(sx * 1.0, -0.6, -0.2))
        c[f"hand{side}.twist"] = -sx * 70; c[f"hand{side}.bend"] = -10; fingers(c, side, 8)
    c["hips.ty"] = -0.004 * hit; c["head.rx"] = -3 + 3 * hit; c["head.rz"] = 4 * wave(f, N, 1, 0.2)
    c["jaw.rx"] = 5
    blink(c, f, N, [24])
    stand_feet(rig, c, spread=0.002)
    return c
# =============================================================================================== evaluation
HAND_SPACES = ("staff", "handL", "handR", "tambourine")


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
    """Naomi: staff foot at chs['staff.foot'] (root space, on the page), staff along chs['staff.dir']: iterate the
    right wrist target until the foot is there. Without staff.foot: optional staff.aim only (staff follows the hand)."""
    if rig.staff_foot is None:
        return
    if "staff.foot" not in chs:
        if "ik.armR" in chs:
            ik_limb(rig, basis, M, chs, "armR")
        if "staff.aim" in chs:
            aim_prop(rig, basis, M, "staff", chs["staff.aim"])
        return
    Mroot = M["root"] @ rig.rest["root"].inverted()
    foot = Vector(chs["staff.foot"]); d = Vector(chs["staff.dir"]).normalized()
    want = to_d(Mroot @ to_bl(foot))
    target = Vector(chs["ik.armR"]) if "ik.armR" in chs else foot + d * (rig.staff_len + 0.004) + V(0.008, 0.004, -0.006)
    ch2 = {"ikspace.armR": "root", "ikw.armR": 1.0, "pole.armR": chs.get("pole.armR", V(-0.7, -0.5, -0.6))}
    for _ in range(7):
        ch2["ik.armR"] = target
        ik_limb(rig, basis, M, ch2, "armR")
        aim_prop(rig, basis, M, "staff", d)
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
            continue                                    # Moses's right arm: solved with the staff below
        if chs.get("ikspace." + limb, "root") in HAND_SPACES:
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
    "moses": [(("beard1", "beard2"), 85.0, 8.0, 0.25, 22.0),
              (("mantleL",), 80.0, 7.0, 0.22, 16.0), (("mantleR",), 80.0, 7.0, 0.22, 16.0),
              (("mantleBack",), 70.0, 7.0, 0.25, 18.0)],
    "pharaoh": [(("nemes1L",), 110.0, 9.0, 0.20, 14.0), (("nemes1R",), 110.0, 9.0, 0.20, 14.0),
                (("nemesBack",), 90.0, 8.0, 0.25, 20.0)],
    "miriam": [(("scarf1", "scarf2"), 75.0, 7.5, 0.30, 30.0), (("braid1", "braid2"), 95.0, 8.0, 0.25, 24.0)],
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
                tgt = cur_c.slerp(rest_w, gw) if gw > 0 else cur_c
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
    return {"moses": ["idle", "walk_staff", "talk", "look_curious", "startle", "kneel_bow", "who_me", "throw_staff",
                      "jump_back", "grab_tail", "nod_brave", "staff_raise", "sigh_head", "brave_talk", "staff_over_sea",
                      "clap", "talk_warm", "wave"],
            "pharaoh": ["idle", "walk", "talk", "smug", "point_order", "laugh", "arms_crossed", "frog_panic", "sneaky_no",
                        "sad_sit", "tantrum", "ride", "wobble", "soggy_sit", "sneeze", "angry"],
            "miriam": ["idle", "walk", "talk", "carry_brick", "pray_stand", "hurry_wave", "joy", "scared", "wow",
                       "tambourine_dance", "wave", "clap"]}


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


PROPS = ("staff", "chariot", "wheelL", "tambourine")


def staff_hidden(cl, f):
    """Moses's staff is the snake between throw_staff `release` and grab_tail 0.9 s (the timeline's prop events)."""
    if cl.ch != "moses":
        return False
    if cl.name == "jump_back":
        return True
    if cl.name == "throw_staff":
        return f > THROW_REL
    if cl.name == "grab_tail":
        return f < GRAB_SHOW
    return False


def hidden_props(rig, cl, f=None):
    """Prop meshes not shown in this clip (at frame f): left out of the checks and the renders."""
    out = []
    for p in PROPS:
        nm = f"{rig.ch}_{p}"
        if nm in bpy.data.objects:
            want = p in cl.props
            if p == "staff" and f is not None and staff_hidden(cl, f):
                want = False
            if not want:
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
    if "chariot" in cl.props:
        out["bodyMinY"] = round(min(blows), 4)          # soles on the chariot floor (0.035)
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
    if rig.staff_foot is not None and "staff" in cl.props:
        ys, slip, ref = [], 0.0, None
        v = (nat or 0.0) / FPS
        for fr, (_, M) in enumerate(frames):
            if staff_hidden(cl, fr):
                continue
            p = rig.foot_of_staff(M)
            ys.append(p.y)
            if p.y < 0.004:
                w = V(p.x, 0, p.z + v * fr)
                ref = ref or w
                slip = max(slip, (w - ref).length)
            else:
                ref = None
        out["staffFootY"] = [round(min(ys), 4), round(max(ys), 4)]
        out["staffPlantSlipMax"] = round(slip, 4)
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


SAMPLE_BONES = ("head", "jaw", "handR", "handL", "footL", "toeR", "hips", "beard2", "mantleL", "nemes1L", "nemesBack",
                "scarf2", "braid2", "staff", "chariot", "wheelL", "tambourine")


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    req = TL.get("requestedClips") or []
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl, "requestedClips": req,
            "stage": {"chariotFloorY": CHARIOT_FLOOR, "sadSitHip": [round(v, 4) for v in SIT_HIP],
                      "sadSitNote": "sad_sit seat = the dais upper step edge behind PH_PALACE (-0.36, -0.30)",
                      "soggySitHip": [round(v, 4) for v in SOGGY_HIP], "jumpBackOffsetZ": -JB_BACK,
                      "songBarSec": round(15.0 / 14.0, 6)},
            "staffHidden": {"throw_staff": f"after frame {THROW_REL} (release)", "jump_back": "all",
                            "grab_tail": f"before frame {GRAB_SHOW} (0.9 s)"}}
    only = os.environ.get("EX_ONLY")
    only_ch = [c for c in os.environ.get("EX_CHARS", "").split(",") if c]
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
        if cl.action == "miriam_tambourine_dance":
            info["rootSpin"] = "root bone turns 360 deg about Y in bar 3 (no translation)"
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        print("EX_CHECK", cl.action, json.dumps(info["checks"]))
        meta["clips"].append(info)
        print(f"EX_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} root={info['rootMaxOffset']}")
    if only:
        print("EX_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "ru_anim.blend")
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
        print("EX_EXPORT", ch)
    os.remove(tmp_blend)
    if only_ch:
        old = json.load(open(os.path.join(ANIM, "clips.json")))
        meta["clips"] = [c for c in old["clips"] if c["char"] not in only_ch] + meta["clips"]
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("EX_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


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
    print("EX_TIMESCALE", os.path.basename(path), done)


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
            print(f"EX_VERIFY {ch} {nm} {a['frames']}f {a['seconds']}s ch={a['channels']} sampleErr={out['sampleErr'][ch].get(nm)}")
        g = out["glb"][ch]
        print(f"EX_VERIFY_GLB {ch} bytes={g['bytes']} skins={g['skins']} meshes={g['meshes']} "
              f"uv0InUnitSquare={g['uv0InUnitSquare']} uv={json.dumps(g['uv'])}")
        print(f"EX_VERIFY_NODES {ch} {[n for n in g['nodes'] if n and n.split('_')[-1] in PROPS + ('eyelids',) or n in PROPS]}")
    print("EX_VERIFY_MISSING", json.dumps(out["contractMissing"]))


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
SET_CLIPS = {"pharaoh_sad_sit", "pharaoh_tantrum"}     # shown with the set (the dais seat); the rest on a plain floor


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
    expr = {("pharaoh", "ride_idle"): "smug"}.get((ch, clip_name), expr)
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
    if stage and os.path.exists(SET_GLB) and os.environ.get("EX_NOSET") != "1":
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=SET_GLB)
        new = [o for o in bpy.data.objects if o not in before]
        SET_OBJS[:] = [o for o in new if o.type == 'MESH']
        pm = bpy.data.materials.new("anim_set"); pm.use_nodes = True
        b2 = pm.node_tree.nodes.get("Principled BSDF"); b2.inputs["Roughness"].default_value = 0.9
        b2.inputs["Base Color"].default_value = (0.80, 0.70, 0.52, 1)
        hide = {"doorMarks", "crowdShore", "crowdFar", "looseWheel", "seaWallBack", "seaWallFront"}
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


MARKS = {  # where a clip is shown in renders (story marks, docs/exodus/storyboard/story.py): (x, z, yaw)
    "moses": (0.12, 0.08, 0.0), "pharaoh": (-0.36, -0.30, 0.0), "miriam": (0.02, 0.13, 0.0)}
CLIP_MARKS = {
    "moses_look_curious": (0.04, -0.28, 30.0), "moses_startle": (0.07, -0.30, 30.0), "moses_kneel_bow": (0.07, -0.30, 30.0),
    "moses_who_me": (0.07, -0.30, 30.0), "moses_throw_staff": (0.07, -0.30, 30.0), "moses_jump_back": (0.07, -0.30, 30.0),
    "moses_grab_tail": (0.07, -0.30, 30.0), "moses_nod_brave": (0.07, -0.30, 30.0),
    "moses_staff_over_sea": (0.12, 0.08, 75.0), "moses_clap": (0.46, 0.04, 0.0), "moses_walk_staff": (0.34, -0.30, 0.0),
    "pharaoh_ride": (-0.10, 0.05, 0.0), "pharaoh_ride_idle": (-0.10, 0.05, 0.0), "pharaoh_wobble": (0.24, 0.07, 0.0),
    "pharaoh_soggy_sit": (0.12, 0.03, 0.0), "pharaoh_sneeze": (0.12, 0.03, 0.0), "pharaoh_walk": (-0.18, -0.24, 0.0),
    "miriam_carry_brick": (-0.20, -0.06, 0.0), "miriam_pray_stand": (-0.20, -0.06, 0.0),
    "miriam_hurry_wave": (-0.02, -0.32, 0.0), "miriam_tambourine_dance": (0.53, 0.12, 0.0), "miriam_wow": (0.02, 0.13, 60.0),
}


def stage_of(cl):
    show_set(cl.action in SET_CLIPS or os.environ.get("EX_SET") == "1")
    return CLIP_MARKS.get(cl.action, MARKS[cl.ch])


def view_cam(cam, rig, mark, view, bone=None, dist_k=2.3, H=None):
    x, z, yaw0 = mark
    H = H or rig.H
    yaw = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "top": 25, "low": 25}[view] + yaw0
    tgt = V(x, H * float(os.environ.get("EX_TGT_K", "0.55")), z); dist = H * dist_k; hgt = H * 0.62
    if bone:
        tgt = to_d(rig.obj.matrix_world @ rig.obj.pose.bones[bone].head); dist = H * 0.9; hgt = tgt.y + 0.02
    if view == "top":
        hgt = dist * 1.3
    if view == "low":
        hgt = 0.02
    a_ = math.radians(yaw)
    look(cam, tgt, V(tgt.x + math.sin(a_) * dist, hgt, tgt.z + math.cos(a_) * dist))


PAIRS = [  # contact-sheet pair rows: (A action, B action, distance, label)
    ("moses_brave_talk", "miriam_scared", 0.112, "pair: brave_talk + miriam scared (S10, 0.112)"),
    ("moses_staff_raise", "pharaoh_laugh", 0.197, "pair: staff_raise + pharaoh laugh (S05, 0.197)"),
    ("moses_clap", "miriam_tambourine_dance", 0.106, "pair: moses clap + tambourine_dance (S13, 0.106)"),
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
        print("EX_CONTACT_ROW", cl.action, picks, flush=True)
    for a, b, dist, label in PAIRS:
        ca, cb = clips[a], clips[b]
        ra, rb = rigs[ca.ch], rigs[cb.ch]
        show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
        set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
        row = {"action": label, "loop": ca.loop, "frames_total": ca.N, "frames": []}
        n = ca.N
        for i, fr in enumerate([0, n // 3, n - 6 if not ca.loop else n // 2]):
            fb = min(fr, cb.N)
            apply_basis(ra, baked[a][fr][0]); apply_basis(rb, baked[b][fb][0])
            place_pair(rigs, ra, rb, dist)
            bpy.context.view_layer.update()
            for vn, cpos in (("front", V(-0.10, 0.20, 0.08 + 0.55)), ("q3", V(-0.10 + 0.40, 0.30, 0.08 + 0.40)),
                             ("back", V(-0.10 - 0.05, 0.26, 0.08 - 0.50))):
                if i > 0 and vn == "back":
                    continue
                look(cam, V(-0.10, 0.17, 0.08), cpos, lens=45)
                fn = f"pair_{a}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                row["frames"].append({"f": fr, "file": fn, "marker": vn})
        reset_pose(ra); reset_pose(rb)
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """EX_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'pair:<actionA>:<actionB>:<dist>:<frame>[:view]' renders two actors facing each other at that distance."""
    sc, rigs = open_scene()
    res = int(os.environ.get("EX_PROBE_RES", "440"))
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
    for item in os.environ.get("EX_PROBE", "").split(";"):
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
            view_cam(cam, rig, mark, view, bone, dist_k=float(os.environ.get("EX_PROBE_DIST", "1.25")))
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("EX_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("EX_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
