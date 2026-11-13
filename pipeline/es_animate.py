"""Esther skeletal animation (Animation role, story pack #2).

Two halves in one file, like pipeline/dg_animate.py (the David & Goliath pipeline it is adapted from):

* Under Blender (headless) it opens `assets/esther/model/characters.blend` (Characters role's rigs), builds every clip of
  docs/esther/CONTRACT.md §4 (+ timeline.json requestedClips, + two extras) as an action `<char>_<clip>` and exports
  `assets/esther/anim/{esther,king,haman}.glb` (character + skin + one glTF animation per action) and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/es_animate.py all        # build + verify + contact sheet
    python3 pipeline/es_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/es_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build
    python3 pipeline/es_animate.py contact    # anim/contact_sheet.png (key poses per clip, in the palace)
    ES_PROBE="esther_pray:0,45:q3" python3 pipeline/es_animate.py probe      # work renders ($ES_ANIM_WORK/probe.png)
    ES_PROBE="scene:sceptre" python3 pipeline/es_animate.py probe            # S08 staging: king + Esther at their marks

How the motion is made (no hand-placed keys; the script is the source):
  * Each clip is a function frame -> channels. Rotations are in DESIGN axes (x right, y up, z toward the viewer),
    applied in the bone's rest frame: `rx ry rz`, `bend` (+ = tip forward), `raise` (+ = tip up, side bones), `swing`,
    `twist`, `curl` (fingers, + = close), `tx ty tz` (design offsets) and `sy` (local-Y scale: the eyelids blink).
    Keys are Catmull-Rom splines (`K`), wrapped for loops.
  * Legs use a two-bone IK to ankle targets with heel / ball / toe ground contact; arms use it when a hand must be at a
    place (hands at the chest, folded in prayer, at the mouth, the sceptre tip). The king's sceptre can be aimed (the
    hand turns so the staff points along a direction) and its tip placed exactly (`sceptre.tip`).
  * Secondary motion is simulated, not keyed: Esther's braid (braid1-3) and cape (cape1-2) are damped spring chains
    that lag the head / chest and settle; the sceptre lags the fist a little. Loops simulate 3 cycles, keep the last
    and spread the residual so they close exactly.
  * Faces: eyelids blink by scaling `eyelids` along its length (1 open ... 12.8 closed) at irregular times; jaw talk is
    an irregular syllable rhythm with word gaps (`syllables()`), head nods and hand beats land on the stressed ones.
  * Sampled at 30 fps, one key per frame per bone (quaternion + location + scale), linear.
Intermediates: $ES_ANIM_WORK (default $ES_WORK/anim, ES_WORK default /tmp/es_work).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
ES = os.path.join(ROOT, "assets/esther")
MODEL = os.path.join(ES, "model")
ANIM = os.path.join(ES, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
PALACE_GLB = os.path.join(MODEL, "palace.glb")
TIMELINE = os.path.join(ES, "timeline.json")
FACES_JSON = os.path.join(ES, "faces.json")
WORK = os.environ.get("ES_ANIM_WORK") or os.path.join(os.environ.get("ES_WORK", "/tmp/es_work"), "anim")
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FPS = 30
CHARS = ("esther", "king", "haman")
G = 2.0                     # gravity, art-width units / s^2 (Esther 0.34 ~ 1.6 m)

# stage (docs/esther/SET.md, CONTRACT §6)
DAIS_TOP = 0.07
THRONE = (0.0, -0.30)
STEP_FOOT = (0.0, -0.12)
SEAT_H = 0.186 - DAIS_TOP   # cushion top above the king's root
SEAT_Z = (-0.079, 0.074)    # seat back panel front .. seat front edge, king-local z

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
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith(("ES_", "Traceback", "Error", "  File")) or "Error" in ln]
    print("\n".join(tail[-200:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def compose_contact():
    from PIL import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(WORK, "contact", "contact.json")))
    cell, pad, lab = 200, 6, 34
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
    d.text((pad, 14), "Esther - key poses per clip (30 fps; frame / seconds; marker names in red; * = extra clip)",
           fill=(40, 30, 20), font=font)
    y = 60
    for r in rows:
        d.text((pad, y + 6), r["action"] + (" *" if r.get("extra") else ""), fill=(40, 30, 20), font=font)
        d.text((pad, y + 30), f"{r['frames_total']} f  {r['frames_total'] / FPS:.2f} s", fill=(90, 80, 70), font=small)
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
    sheet.save(out, optimize=True)
    print("ES_CONTACT", out, sheet.size)


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get("ES_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("ES_PROBE_OUT", "probe.png"))
    sheet.save(out); print("ES_PROBE_SHEET", out)


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
from mathutils import Vector, Matrix  # noqa: E402

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


def Kv(keys, f, N=None, loop=False):
    """K for vectors: keys [(frame, V)]."""
    return V(*(K([(k, v[i]) for k, v in keys], f, N, loop) for i in range(3)))


def KL(keys, f, N=None, loop=False, lag=0.0):
    """K with every key delayed by `lag` frames (overlapping action: a child follows its parent late)."""
    return K(keys, f - lag, N, loop)


def wave(f, N, cycles=1.0, phase=0.0):
    return math.sin(2 * math.pi * (cycles * f / N + phase))


def add(d, ch, v):
    d[ch] = d.get(ch, 0.0) + v


def ease_io(t):
    t = min(1.0, max(0.0, t)); return 0.5 - 0.5 * math.cos(math.pi * t)


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


def syllables(N, seed, amp=(6.0, 15.0), dur=(3.0, 6.5), gap=0.2, lead=3, tail=5, loop=True):
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
        if a > amp[0] + 0.72 * (amp[1] - amp[0]):
            beats.append(peak)
        t += d
        if r.random() < gap:
            t += r.uniform(5, 13)          # word gap / little breath
            keys.append((t - 1, 0.0))
    keys.append((N, 0.0))
    keys = sorted(keys)
    return keys, beats


def jaw_from(keys, f, N, loop=True):
    return max(0.0, K(keys, f, N, loop) if not loop else K(keys, f % N, N, False))


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


# =============================================================================================== rig model (pure python FK)
class Rig:
    H_OF = {"esther": 0.34, "king": 0.40, "haman": 0.37}

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
    def __init__(self, ch, name, N, loop, fn, markers=None, notes="", extra=False, speed=None):
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = markers or {}
        self.notes = notes
        self.extra = extra
        self.speed = speed           # (stride L, duty) for in-place locomotion -> natural speed

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
        CLIPS.append(Clip(ch, name, N, loop, fn, **kw)); return fn
    return deco


# ----------------------------------------------------------------------------------------------- legs
def foot_points(rig, side):
    a = rig.head["foot" + side]
    ball = rig.head["toe" + side] - a
    tip = rig.tail["toe" + side] - a
    heel = V(0, -a.y + 0.001, -0.18 * ball.z)
    return heel, ball, tip


def planted_ankle_y(rig, side, pitch_deg):
    R = rot_d((1, 0, 0), pitch_deg)
    low = min((CI @ (R @ (C @ p))).y for p in foot_points(rig, side))
    return -low


def gait(rig, f, N, L, lift, duty, offsetR=0.5, offsetL=0.0, heel=10.0, toeoff=24.0, out=None, lift_shape=1.0,
         spread=0.0, fwd=0.0, back=False):
    """In-place gait: per side the ankle target (root space) and foot pitch. Stance: the foot slides from +L/2 to
    -L/2 at constant speed (speed = L / (duty * N / FPS)); swing: eased return with lift. back=True: walking backward."""
    out = out if out is not None else {}
    sgn = -1.0 if back else 1.0
    for side, off in (("L", offsetL), ("R", offsetR)):
        p = (f / N + off) % 1.0
        base = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        if p < duty:
            s = p / duty
            z = sgn * (L / 2 - L * s)
            if back:
                pitch = toeoff * 0.5 * (1 - smooth(s / 0.2)) - heel * 0.6 * smooth((s - 0.75) / 0.25)
            else:
                pitch = -heel * (1 - smooth(s / 0.15)) + toeoff * smooth((s - 0.7) / 0.3)
            y = planted_ankle_y(rig, side, pitch)
            contact = True
        else:
            s = (p - duty) / (1 - duty)
            z = sgn * (-L / 2 + L * smooth(s))
            if back:
                pitch = lerp(-heel * 0.6, toeoff * 0.5, smooth(s))
            else:
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
    c[f"ik.arm{side}"] = target
    c[f"ikspace.arm{side}"] = space
    c[f"ikw.arm{side}"] = w
    if pole is not None:
        c[f"pole.arm{side}"] = pole


def fingers(c, side, curl):
    c[f"fingers{side}.curl"] = curl


# =============================================================================================== ESTHER
# Rest: A-pose, arms 55 deg below horizontal, hands open (palm to the body). raise -24 = arms relaxed by the robe.
def e_base(rig, f, N, cycles=1, amp=1.0):
    c = {}
    b = wave(f, N, cycles)
    c["chest.rx"] = -1.4 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.0 * b * amp; c["shoulderR.raise"] = 1.0 * b * amp
    c["neck.rx"] = 0.8 * b * amp
    c["upperArmL.raise"] = -22; c["upperArmR.raise"] = -22
    c["upperArmL.bend"] = 8; c["upperArmR.bend"] = 8
    c["forearmL.bend"] = 26; c["forearmR.bend"] = 26
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 22); fingers(c, "R", 22)
    c["head.rx"] = -2
    return c


@clip("esther", "idle", 150, True,
      notes="breathes, shifts her weight L->R->L, looks round (neck leads, head follows), blinks at irregular times "
            "(single and double); fingers stir; braid and cape settle after each head turn")
def esther_idle(rig, f, N):
    c = e_base(rig, f, N, cycles=2)
    sh = K([(0, -0.2), (18, -0.2), (40, 1.0), (78, 1.0), (100, -0.7), (132, -0.7), (150, -0.2)], f, N, True)
    sh_l = KL([(0, -0.2), (18, -0.2), (40, 1.0), (78, 1.0), (100, -0.7), (132, -0.7), (150, -0.2)], f, N, True, lag=6)
    c["hips.tx"] = 0.0045 * sh; c["hips.ty"] = -0.0015 - 0.0012 * abs(sh)
    c["hips.rz"] = -2.4 * sh; c["spine.rz"] = 1.4 * sh_l; c["chest.rz"] = 1.0 * sh_l
    c["head.rz"] = -1.2 * sh_l
    look = [(0, 0), (34, 0), (44, 9), (76, 9), (88, -6), (118, -6), (128, 2), (150, 0)]
    c["neck.ry"] = 0.4 * K(look, f, N, True)
    c["head.ry"] = 0.6 * KL(look, f, N, True, lag=3)
    c["head.rx"] += K([(0, 0), (44, -2), (76, 1), (90, 2), (118, 0), (150, 0)], f, N, True)
    c["upperArmL.bend"] += 2 * wave(f, N, 1, 0.3); c["upperArmR.bend"] += 2 * wave(f, N, 1, 0.8)
    fingers(c, "L", 22 + 8 * wave(f, N, 1, 0.6)); fingers(c, "R", 20 + 6 * wave(f, N, 2, 0.1))
    blink(c, f, N, [22, 61, 69, 120])
    stand_feet(rig, c, spread=0.002, pitchR=K([(0, 0), (40, 0), (55, 6), (78, 6), (92, 0), (150, 0)], f, N, True))
    return c


E_WALK = (0.075, 0.60)


@clip("esther", "walk", 36, True, markers={"contactL": 0, "contactR": 18}, speed=E_WALK,
      notes="graceful in-place walk, 100 steps/min; hips bob and drop, chest counter-turns, arms swing softly with "
            "lagging forearms and hands; braid and cape swing")
def esther_walk(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=E_WALK[0], lift=0.012, duty=E_WALK[1], heel=12, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0045 + 0.0030 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -6 * math.sin(ph - 0.35); c["head.ry"] = 3 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.5 * math.cos(ph); c["chest.rz"] = -1.5 * math.cos(ph - 0.5); c["head.rz"] = 0.8 * math.cos(ph - 0.9)
    c["spine.rx"] = 2; c["head.rx"] = -3 + 1.2 * math.cos(2 * ph - 0.9)
    c["upperArmL.bend"] = 8 - 14 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 14 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 28 - 8 * math.sin(ph - 1.0); c["forearmR.bend"] = 28 + 8 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 8 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 8 * math.sin(ph - 1.6)
    fingers(c, "L", 24 + 6 * math.sin(ph - 1.8)); fingers(c, "R", 24 - 6 * math.sin(ph - 1.8))
    blink(c, f, N, [27])
    return c


@clip("esther", "talk", 90, True,
      notes="jaw in an irregular syllable rhythm with word gaps; head nods on the stressed syllables; right hand rises "
            "palm-up and opens on the beats, closes softly between; weight shift; two blinks")
def esther_talk(rig, f, N):
    c = e_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 11, amp=(5, 13))
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=9)
    btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -2 + 3.5 * bt - 1.0 * wave(f, N, 1, 0.2)
    c["head.ry"] = 5 * wave(f, N, 1, 0.1) + 2 * wave(f, N, 3, 0.4); c["head.rz"] = 3 * wave(f, N, 1, 0.35)
    c["neck.ry"] = 2 * wave(f, N, 1, 0.05)
    # right hand: palm-up gesture, opens on the beats (the gesture lifts in phrases, not every syllable)
    phrase = K([(0, 0.25), (12, 0.9), (40, 1.0), (52, 0.4), (64, 0.9), (82, 0.7), (90, 0.25)], f, N, True)
    lift = phrase * (0.75 + 0.25 * btl)
    c["upperArmR.raise"] = -22 + 2 * lift; c["upperArmR.bend"] = 8 + 40 * lift
    c["forearmR.bend"] = 26 + 52 * lift; c["forearmR.twist"] = 10 - 80 * lift
    c["handR.bend"] = 6 - 22 * btl
    fingers(c, "R", 30 - 28 * btl - 6 * lift)
    c["upperArmL.bend"] = 10 + 6 * phrase; c["forearmL.bend"] = 34 + 10 * phrase
    fingers(c, "L", 26)
    c["chest.ry"] = -4 * lift; c["chest.rx"] += 1.5 * bt
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh; c["spine.rz"] = 0.9 * sh
    blink(c, f, N, [7, 58])
    stand_feet(rig, c, spread=0.002)
    return c


def hands_at_chest(c, wring, f, N, lift=0.0, w=1.0):
    """Both hands held together at the chest (worried): targets in chest space, slight wringing."""
    arm_ik(c, "L", V(0.010 + 0.002 * wring, -0.004 + lift, 0.040 + 0.003 * wring), V(0.7, -0.7, -0.1), "chest", w)
    arm_ik(c, "R", V(-0.006 + 0.002 * wring, -0.010 + lift, 0.044 - 0.002 * wring), V(-0.7, -0.7, -0.1), "chest", w)


@clip("esther", "worried", 120, True,
      notes="small and scared: shoulders up, chest sunk, head down, hands held together at the chest and wringing; "
            "quick glances left and right with holds; nervous weight shifts; frequent blinks")
def esther_worried(rig, f, N):
    c = e_base(rig, f, N, cycles=3, amp=0.7)          # faster, shallower breathing
    c["shoulderL.raise"] += 5; c["shoulderR.raise"] += 5
    c["spine.rx"] += 3; c["chest.rx"] += 4; c["neck.rx"] = 4
    gl = [(0, 0), (14, 0), (18, -13), (36, -13), (40, 3), (58, 3), (62, 15), (76, 15), (82, 0), (104, 0), (107, -5), (114, -5), (120, 0)]
    c["head.ry"] = K(gl, f, N, True); c["neck.ry"] = 0.3 * KL(gl, f, N, True, lag=-1)
    c["head.rx"] = 7 + 2 * K([(0, 0), (18, -2), (40, 1), (62, -2), (82, 1), (120, 0)], f, N, True)
    c["head.rz"] = 4 + 2 * wave(f, N, 1, 0.2)
    wr = math.sin(2 * math.pi * 3 * f / N) * 0.6 + math.sin(2 * math.pi * 5 * f / N + 1) * 0.4
    hands_at_chest(c, wr, f, N)
    fingers(c, "L", 50 + 10 * wr); fingers(c, "R", 55 - 10 * wr)
    c["handL.bend"] = -10; c["handR.bend"] = -10
    sh = K([(0, 0), (20, 0.6), (50, 0.6), (60, -0.5), (95, -0.5), (120, 0)], f, N, True)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.8 * sh; c["hips.ty"] = -0.003
    blink(c, f, N, [9, 44, 50, 97])
    stand_feet(rig, c, spread=-0.002, pitchL=K([(0, 0), (60, 0), (66, 5), (95, 5), (100, 0), (120, 0)], f, N, True))
    return c


# --- kneeling (pray)
KNEEL_HIPS_TY = -0.062
KNEEL_HIPS_TZ = -0.020
KNEEL_ANKLE_Y = 0.050      # ankles raised: toes tucked under, shins slant up so the robe does not sink into the page
KNEEL_PITCH = 45.0
KNEEL_BACK = -0.064


def kneel_legs(rig, c, wL=1.0, wR=1.0):
    for side, w in (("L", wL), ("R", wR)):
        b = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        y_st = planted_ankle_y(rig, side, 0)
        c[f"ik.leg{side}"] = V(b.x + sx * 0.004 * w, lerp(y_st, KNEEL_ANKLE_Y, w), b.z + KNEEL_BACK * w)
        c[f"foot{side}.pitch"] = KNEEL_PITCH * w
        c[f"pole.leg{side}"] = V(0.1 * sx, 0, 1)


def pray_pose(rig, c, f, N, w=1.0, loop=True):
    """The kneeling prayer pose (hands folded at the chest, head bowed). w blends the arms/head in."""
    c["hips.ty"] = KNEEL_HIPS_TY; c["hips.tz"] = KNEEL_HIPS_TZ
    c["hips.rx"] = -4; c["spine.rx"] = 4; c["chest.rx"] = c.get("chest.rx", 0) + 3
    kneel_legs(rig, c)
    c["neck.rx"] = 9 * w; c["head.rx"] = 17 * w
    arm_ik(c, "L", V(0.007, -0.002, 0.048), V(0.8, -0.6, -0.2), "chest", w)
    arm_ik(c, "R", V(-0.007, -0.002, 0.048), V(-0.8, -0.6, -0.2), "chest", w)
    c["handL.bend"] = lerp(6, -28, w); c["handR.bend"] = lerp(6, -28, w)
    fingers(c, "L", lerp(22, 46, w)); fingers(c, "R", lerp(22, 46, w))
    c["braid.bias"] = V(-0.3, 0.0, 0.15)


@clip("esther", "pray", 90, True,
      notes="kneeling (upright, on both knees), hands folded at the chest, head bowed; slow deep breathing, a small "
            "sway, the folded hands lift a little on each breath. Starts and ends in the kneeling pose: play the "
            "extra clip esther_kneel before it for the way down")
def esther_pray(rig, f, N):
    c = e_base(rig, f, N, cycles=2, amp=1.3)
    pray_pose(rig, c, f, N)
    c["chest.rz"] = 1.2 * wave(f, N, 1, 0.1); c["head.rz"] = -1.0 * wave(f, N, 1, 0.25)
    c["head.rx"] += 1.5 * wave(f, N, 2, 0.3)
    c["ik.armL"] = c["ik.armL"] + V(0, 0.003 * wave(f, N, 2, 0.15), 0)
    c["ik.armR"] = c["ik.armR"] + V(0, 0.003 * wave(f, N, 2, 0.15), 0)
    return c


@clip("esther", "kneel", 36, False, extra=True, markers={"knees_down": 24},
      notes="EXTRA (not in CONTRACT §4): stand -> kneel, right knee first, hands come together; ends in frame 0 of pray")
def esther_kneel(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.0)
    one = ease_io((f - 2) / 16); two = ease_io((f - 10) / 16)
    down = 0.5 * (one + two)
    hw = ease_io((f - 12) / 20)
    p = {}
    pray_pose(rig, p, f, N, w=hw)
    c["hips.ty"] = KNEEL_HIPS_TY * down - 0.006 * math.sin(math.pi * min(1, f / 12))
    c["hips.tz"] = KNEEL_HIPS_TZ * down
    c["hips.rx"] = -4 * down; c["spine.rx"] = 4 * down + 6 * math.sin(math.pi * smooth(f / 26))
    for side, w in (("L", two), ("R", one)):
        b = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        y_st = planted_ankle_y(rig, side, 0)
        c[f"ik.leg{side}"] = V(b.x + sx * 0.004 * w, max(planted_ankle_y(rig, side, KNEEL_PITCH * w), lerp(y_st, KNEEL_ANKLE_Y, w)), b.z + KNEEL_BACK * w)
        c[f"foot{side}.pitch"] = KNEEL_PITCH * w
        c[f"pole.leg{side}"] = V(0.1 * sx, 0, 1)
    for k in ("ik.armL", "ik.armR", "ikspace.armL", "ikspace.armR", "pole.armL", "pole.armR", "braid.bias"):
        c[k] = p[k]
    c["ikw.armL"] = c["ikw.armR"] = hw
    c["neck.rx"] = p["neck.rx"]; c["head.rx"] = p["head.rx"]
    c["handL.bend"] = p["handL.bend"]; c["handR.bend"] = p["handR.bend"]
    fingers(c, "L", p["fingersL.curl"]); fingers(c, "R", p["fingersR.curl"])
    blink(c, f, N, [4], loop=False)
    return c


@clip("esther", "rise_brave", 84, False, markers={"stand": 46, "chin_up": 62},
      notes="from the kneeling prayer: deep breath, hands part, left foot steps forward, pushes up to standing, feet "
            "together, then chin up and chest open, shoulders back, hands close into soft fists at her sides; holds")
def esther_rise(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.4)
    # 0-12 breath in (from the pray pose), 12-22 left foot forward, 22-46 push up, 46-56 feet together, 56-70 resolve
    br = math.sin(math.pi * smooth(f / 14))
    up = ease_io((f - 20) / 26)
    hw = 1 - ease_io((f - 10) / 14)
    p = {}
    pray_pose(rig, p, f, N, w=hw)
    c["hips.ty"] = lerp(KNEEL_HIPS_TY, 0.0, up) + 0.004 * br
    c["hips.tz"] = lerp(KNEEL_HIPS_TZ, 0.0, up) + 0.018 * math.sin(math.pi * up)
    c["hips.rx"] = lerp(-4, 0, up)
    lean = math.sin(math.pi * smooth((f - 16) / 34))
    c["spine.rx"] = lerp(4, 0, up) + 12 * lean; c["chest.rx"] += -3 * br + 4 * lean
    # left foot: step forward (kneel -> lunge), then back beside the right one
    stepL = ease_io((f - 10) / 10); backL = ease_io((f - 44) / 10)
    bL = rig.head["footL"]; bR = rig.head["footR"]
    kneelR = 1 - up
    yR = max(planted_ankle_y(rig, "R", KNEEL_PITCH * kneelR), lerp(planted_ankle_y(rig, "R", 0), KNEEL_ANKLE_Y, kneelR))
    c["ik.legR"] = V(bR.x - 0.004 * kneelR, yR, bR.z + KNEEL_BACK * kneelR); c["footR.pitch"] = KNEEL_PITCH * kneelR
    zL = lerp(KNEEL_BACK, 0.050, stepL) * (1 - backL)
    lift = 0.02 * math.sin(math.pi * stepL) + 0.012 * math.sin(math.pi * backL)
    pitchL = KNEEL_PITCH * (1 - stepL)
    c["ik.legL"] = V(bL.x + 0.004 * (1 - stepL), max(planted_ankle_y(rig, "L", pitchL), lerp(KNEEL_ANKLE_Y, planted_ankle_y(rig, "L", 0), stepL)) + lift, bL.z + zL)
    c["footL.pitch"] = pitchL
    c["pole.legL"] = V(0.1, 0, 1); c["pole.legR"] = V(-0.1, 0, 1)
    # resolve: chin up, chest open, shoulders back, soft fists
    res = ease_io((f - 54) / 14)
    over = math.sin(math.pi * smooth((f - 54) / 22))
    c["chest.rx"] += -6 * res - 2 * over; c["spine.rx"] += -1.5 * res
    c["shoulderL.swing"] = -6 * res; c["shoulderR.swing"] = -6 * res
    c["neck.rx"] = lerp(p["neck.rx"], -2 * res, ease_io((f - 6) / 30))
    c["head.rx"] = lerp(p["head.rx"], -9 * res - 2 * over, ease_io((f - 6) / 30))
    c["head.ry"] = 4 * math.sin(math.pi * smooth((f - 24) / 26)) - 2 * res
    c["upperArmL.raise"] = -22 - 3 * res; c["upperArmR.raise"] = -22 - 3 * res
    c["upperArmL.bend"] = 8 - 4 * res + 18 * lean; c["upperArmR.bend"] = 8 - 4 * res + 18 * lean
    c["forearmL.bend"] = 26 - 8 * res + 20 * lean; c["forearmR.bend"] = 26 - 8 * res + 20 * lean
    for k in ("ik.armL", "ik.armR", "ikspace.armL", "ikspace.armR", "pole.armL", "pole.armR"):
        c[k] = p[k]
    c["ikw.armL"] = c["ikw.armR"] = hw
    c["handL.bend"] = lerp(p["handL.bend"], 4, 1 - hw); c["handR.bend"] = lerp(p["handR.bend"], 4, 1 - hw)
    fist = lerp(p["fingersL.curl"], 22, 1 - hw) + 38 * res
    fingers(c, "L", fist); fingers(c, "R", fist)
    c["braid.bias"] = p["braid.bias"] * hw
    c["eyelids.sy"] = 1.0
    blink(c, f, N, [2, 50], loop=False)
    return c


E_CLIMB = (0.050, 0.66)


@clip("esther", "climb", 48, True, markers={"contactL": 0, "contactR": 24}, speed=E_CLIMB,
      notes="careful steps up toward the throne: slow, knees lifted high, both hands gather the skirt at the front; "
            "leans a little forward, looks down at the step then up at the king")
def esther_climb(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.8)
    g = gait(rig, f, N, L=E_CLIMB[0], lift=0.026, duty=E_CLIMB[1], heel=4, toeoff=14, lift_shape=0.8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.006 + 0.003 * math.cos(2 * ph - 0.6)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -3 * math.sin(ph - 0.4)
    c["hips.rz"] = 2.5 * math.cos(ph); c["chest.rz"] = -1.2 * math.cos(ph - 0.6)
    c["spine.rx"] = 6; c["chest.rx"] += 2
    # head: looks down at the step on each lift, up at the king between
    c["head.rx"] = 6 + 6 * math.cos(2 * ph + 0.3); c["neck.rx"] = 2
    # hands gather the skirt (lifted with the stepping knee)
    for side, sx, phs in (("L", 1, 0.0), ("R", -1, math.pi)):
        up = 0.006 * max(0.0, math.sin(ph + phs + 0.5))
        arm_ik(c, side, V(0.040 * sx, 0.122 + up, 0.048), V(0.7 * sx, -0.3, -0.6))
        fingers(c, side, 70)
        c[f"hand{side}.bend"] = 10
    blink(c, f, N, [33])
    return c


def curtsey_pose(rig, c, d, f):
    """d 0..1: depth of the curtsey (right foot behind, knees bend, torso and head bow, hands hold the skirt out)."""
    bR = rig.head["footR"]; bL = rig.head["footL"]
    c["hips.ty"] = -0.040 * d; c["hips.tz"] = -0.012 * d
    c["ik.legR"] = V(bR.x + 0.010 * d, planted_ankle_y(rig, "R", 30 * d), bR.z - 0.050 * d); c["footR.pitch"] = 30 * d
    c["ik.legL"] = V(bL.x, planted_ankle_y(rig, "L", 0), bL.z + 0.006 * d); c["footL.pitch"] = 0
    c["pole.legL"] = V(0.25, 0, 1); c["pole.legR"] = V(-0.1, -0.2, 1)
    c["spine.rx"] = 12 * d; c["chest.rx"] = c.get("chest.rx", 0) + 10 * d; c["neck.rx"] = 8 * d; c["head.rx"] = 18 * d
    c["head.rz"] = -4 * d
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArmL.raise" if side == "L" else "upperArmR.raise"] = -22 + 8 * d
        c[f"upperArm{side}.bend"] = 8 + 10 * d
        c[f"forearm{side}.bend"] = 26 + 6 * d
        c[f"hand{side}.bend"] = 6 - 10 * d
        fingers(c, side, 22 + 45 * d)


@clip("esther", "bow", 66, False, markers={"down": 34},
      notes="graceful curtsey to the king: small rise and breath (anticipation), right foot slides behind, knees bend, "
            "torso and head bow, hands hold the skirt out; holds the low pose (next: touch_sceptre)")
def esther_bow(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.4)
    d = ease_io((f - 10) / 24)
    over = 0.10 * math.sin(math.pi * smooth((f - 30) / 16))
    curtsey_pose(rig, c, d + over * d, f)
    rise = math.sin(math.pi * smooth(f / 12))
    c["hips.ty"] += 0.004 * rise; c["chest.rx"] += -3 * rise; c["head.rx"] += -4 * rise
    blink(c, f, N, [26], loop=False)
    c["braid.bias"] = V(0, 0, 0)
    return c


_TIP = {}


def sceptre_tip_esther_local():
    """Where the king's sceptre knob is at the end of king_extend_sceptre, in Esther's local coordinates when both
    stand at their S08 marks (king at the throne on the dais, facing Esther; Esther at the foot of the steps facing
    the king, yaw 180)."""
    if "tip" not in _TIP:
        tip_k = EXTEND_TIP                                   # king-local (design)
        world = V(THRONE[0] + tip_k.x, DAIS_TOP + tip_k.y, THRONE[1] + tip_k.z)
        loc = V(-(world.x - STEP_FOOT[0]), world.y, -(world.z - STEP_FOOT[1]))
        _TIP["tip"] = loc
    return _TIP["tip"]


@clip("esther", "touch_sceptre", 66, False, markers={"touch": 36},
      notes="rises from the curtsey, takes a small breath, reaches up with the left hand and touches the tip of the "
            "king's sceptre (target computed from king_extend_sceptre at the S08 marks), holds it a moment, draws the "
            "hand back to her chest, relieved; holds")
def esther_touch(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.5)
    d = 1 - ease_io((f - 2) / 18)
    curtsey_pose(rig, c, d, f)
    tip = sceptre_tip_esther_local()
    reach = ease_io((f - 14) / 22)
    back = ease_io((f - 46) / 16)
    w = reach * (1 - back)
    # wrist target: a hand-length below/behind the knob so the fingertips land on it
    wrist = tip + V(0.002, -0.022, -0.012)
    start = V(0.055, 0.15, 0.02)
    chest = V(0.010, 0.0, 0.044)
    if f < 46:
        arm_ik(c, "L", start.lerp(wrist, reach), V(0.8, -0.5, -0.3), "root", min(1.0, reach * 1.6))
    else:
        cw = rig_chest_world(rig, c, chest)
        arm_ik(c, "L", wrist.lerp(cw, back), V(0.8, -0.6, -0.2), "root", 1.0)
    c["handL.bend"] = -18 * w + 20 * back
    fingers(c, "L", 8 * w + 40 * back + 22 * (1 - reach))
    # body follows the reach: up on the toes a little, chest lifts, head looks up at the tip
    c["hips.ty"] += 0.004 * w
    c["chest.rx"] += -5 * w; c["chest.ry"] = 6 * w; c["spine.rz"] = -2 * w
    c["head.rx"] += -10 * w + 4 * back; c["head.ry"] = 4 * w
    # right hand comes to the chest too at the end
    arm_ik(c, "R", V(-0.008, -0.010, 0.046), V(-0.8, -0.6, -0.2), "chest", back)
    fingers(c, "R", 22 + 20 * back)
    stand_feet(rig, c, spread=0.0, fwdL=0.004 * w) if d < 0.01 else None
    sigh = math.sin(math.pi * smooth((f - 48) / 16))
    c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh
    blink(c, f, N, [8, 52], loop=False)
    return c


def rig_chest_world(rig, c, off):
    """Root-space point of a chest-space offset, for this frame's channels without arm IK (approximation)."""
    ch = {k: v for k, v in c.items() if not k.startswith(("ik.arm", "ikw.arm", "ikspace.arm", "pole.arm"))}
    b = rig.basis_from(ch); M = rig.fk(b)
    Mc = M["chest"]
    return to_d(Mc @ (rig.rest["chest"].inverted() @ to_bl(rig.head["chest"] + off)))


@clip("esther", "invite", 60, False, markers={"open": 24},
      notes="open-arm invitation: draws in and breathes (anticipation), both arms sweep open, palms up, fingers open, "
            "weight forward, head tilt with a smile; settles with the right hand still offering and the left at the "
            "chest; holds")
def esther_invite(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.5)
    ant = math.sin(math.pi * smooth(f / 12))
    op = ease_io((f - 8) / 16)
    over = math.sin(math.pi * smooth((f - 20) / 14))
    settle = ease_io((f - 32) / 20)
    o = op + 0.12 * over
    oL = o * (1 - 0.65 * settle)
    oR = o * (1 - 0.15 * settle)
    for side, ov in (("L", oL), ("R", oR)):
        sgn = 1 if side == "L" else -1
        c[f"upperArm{side}.raise"] = -22 - 5 * ant + 20 * ov
        c[f"upperArm{side}.bend"] = 8 + 32 * ov
        c[f"forearm{side}.bend"] = 26 + 10 * ant + 18 * ov
        c[f"forearm{side}.twist"] = -10 * sgn - 75 * sgn * ov * (1 if side == "R" else 1)
        c[f"hand{side}.bend"] = 6 - 20 * ov
        fingers(c, side, 28 + 8 * ant - 26 * ov)
    arm_ik(c, "L", V(0.010, -0.006, 0.046), V(0.8, -0.6, -0.2), "chest", settle * 0.9)
    c["chest.rx"] += 2 * ant - 4 * op; c["spine.rx"] = 3 * op - 1 * ant
    c["hips.tz"] = 0.006 * op - 0.003 * ant
    c["head.rz"] = 6 * op - 2 * settle; c["head.rx"] = -4 * op + 2 * ant
    c["head.ry"] = -3 * settle
    stand_feet(rig, c, spread=0.002, fwdL=0.006 * op)
    blink(c, f, N, [4, 40], loop=False)
    return c


@clip("esther", "point", 45, False, markers={"point": 14},
      notes="accuses: pulls the arm back and turns the chest (anticipation), snaps the right arm out straight at the "
            "target, leans in, chin up; small overshoot and settle; left hand a fist at her side; holds")
def esther_point(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.3)
    ant = math.sin(math.pi * smooth(f / 10))
    p = ease_io((f - 6) / 8)
    over = math.sin(math.pi * smooth((f - 13) / 10))
    tgt_far = V(-0.034, 0.262, 0.140) + V(0, 0.006, 0.004) * over
    tgt_ant = V(-0.048, 0.205, -0.010)
    start = V(-0.060, 0.150, 0.020)
    if f < 6:
        tgt = start.lerp(tgt_ant, ant)
    else:
        tgt = tgt_ant.lerp(tgt_far, p)
    arm_ik(c, "R", tgt, V(-0.7, -0.6, -0.3), "root", min(1.0, f / 4 + 0.0) if f < 4 else 1.0)
    c["handR.bend"] = -6 * p; fingers(c, "R", lerp(22, 2, p))
    c["chest.ry"] = 10 * ant - 8 * p; c["spine.ry"] = -4 * p
    c["spine.rx"] = 5 * p; c["chest.rx"] += -3 * p + 2 * over
    c["head.rx"] = -6 * p; c["head.ry"] = 4 * p; c["neck.rx"] = 2 * p
    c["hips.tz"] = 0.006 * p
    fingers(c, "L", 22 + 50 * p); c["upperArmL.raise"] = -24 - 2 * p; c["forearmL.bend"] = 26 + 14 * p
    stand_feet(rig, c, spread=0.002, fwdR=0.012 * p)
    blink(c, f, N, [24], loop=False)
    return c


@clip("esther", "joy", 72, True, markers={"twirl": 8, "hop": 50},
      notes="dips, twirls once on her toes (arms out, braid and cape fly out and catch up), dips again, hops with "
            "both arms up, lands softly; loops")
def esther_joy(rig, f, N):
    c = e_base(rig, f, N, cycles=2, amp=0.6)
    tw = ease_io((f - 8) / 30)                      # 0..1 over the twirl
    c["root.ry"] = 360.0 * tw if f < N else 0.0
    dip = math.sin(math.pi * smooth(f / 9)) + math.sin(math.pi * smooth((f - 38) / 11))
    hop = max(0.0, math.sin(math.pi * (f - 49) / 13)) if 49 <= f <= 62 else 0.0
    land = math.sin(math.pi * smooth((f - 61) / 10))
    c["hips.ty"] = -0.010 * dip - 0.012 * land + 0.030 * hop + 0.004 * math.sin(math.pi * tw)
    toe = 18 * math.sin(math.pi * tw)
    stand_feet(rig, c, spread=0.0, pitchL=toe + 30 * hop, pitchR=toe + 30 * hop,
               liftL=0.030 * hop, liftR=0.030 * hop)
    c["ik.legL"] = c["ik.legL"] + V(0, 0, 0); c["ik.legR"] = c["ik.legR"] + V(0, 0, 0)
    arms_out = math.sin(math.pi * tw)
    arms_up = smooth((f - 44) / 8) * (1 - smooth((f - 64) / 8))
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = -22 + 45 * arms_out + 122 * arms_up
        c[f"upperArm{side}.bend"] = 8 + 10 * arms_out + 10 * arms_up
        c[f"forearm{side}.bend"] = 26 - 10 * arms_out + 10 * arms_up + 10 * dip
        c[f"hand{side}.bend"] = 6 - 12 * arms_out
        fingers(c, side, 22 - 16 * max(arms_out, arms_up))
    c["head.rx"] = -4 * arms_out - 10 * arms_up + 3 * dip; c["head.rz"] = 5 * arms_out
    c["chest.rx"] += -4 * arms_up + 3 * dip
    c["spine.rz"] = -3 * arms_out
    c["jaw.rx"] = 4 * arms_up + 2 * arms_out
    blink(c, f, N, [40])
    return c


@clip("esther", "wave", 48, True,
      notes="waves to the viewer: right hand up by her head, forearm sways side to side, the wrist and fingers follow "
            "late; body sways and bounces softly on the knees, head tilts; left hand at the waist")
def esther_wave(rig, f, N):
    c = e_base(rig, f, N, cycles=1, amp=0.6)
    ph = 2 * math.pi * f / N
    s = math.sin(2 * ph)                             # two waves per loop
    arm_ik(c, "R", V(-0.086 + 0.020 * s, 0.312 + 0.004 * math.cos(2 * ph), 0.040), V(-0.8, -0.6, -0.2))
    c["handR.rz"] = 0.0
    c["handR.bend"] = -10
    c["handR.ry"] = 0.0
    c["handR.twist"] = 0.0
    c["handR.rx"] = 0.0
    c["handR.swing"] = 0.0
    c["handR.raise"] = -20 * math.sin(2 * ph - 0.9)
    fingers(c, "R", 4 + 10 * max(0.0, math.sin(2 * ph - 1.6)))
    c["hips.ty"] = -0.004 - 0.003 * math.cos(2 * ph)
    c["hips.tx"] = 0.003 * math.sin(ph); c["hips.rz"] = -1.5 * math.sin(ph)
    c["chest.rz"] = 2.0 * math.sin(ph - 0.4) - 2; c["head.rz"] = 5 * math.sin(ph - 0.8) - 3
    c["head.ry"] = 3 * math.sin(ph - 0.3)
    c["upperArmL.raise"] = -18; c["upperArmL.bend"] = 14; c["forearmL.bend"] = 60; c["handL.bend"] = 0
    fingers(c, "L", 30)
    blink(c, f, N, [20])
    stand_feet(rig, c, spread=0.002)
    return c


# =============================================================================================== KING
# Seated on the throne: his root is on the dais top under the seat; the hip joints sit SEAT_H + 0.014 above the root.
SIT_TY = -0.036          # hips bone offset (rest hips y 0.19 -> 0.154): robe underside within ~1 cm of the cushion top (seatGap)
SIT_TZ = -0.012
STAND_Z = 0.088          # standing in front of the throne: feet and hips this far forward of the root (seat edge 0.074)


def k_base(rig, f, N, cycles=1, amp=1.0):
    c = {}
    b = wave(f, N, cycles)
    c["chest.rx"] = -2.2 * b * amp; c["spine.rx"] = -0.8 * b * amp
    c["shoulderL.raise"] = 1.6 * b * amp; c["shoulderR.raise"] = 1.6 * b * amp
    c["neck.rx"] = 1.0 * b * amp
    return c


def sit(rig, c, lean=0.0):
    c["hips.ty"] = SIT_TY; c["hips.tz"] = SIT_TZ; c["hips.rx"] = -6 + 0.5 * lean
    c["spine.rx"] = c.get("spine.rx", 0) + 4 + lean * 0.6; c["chest.rx"] = c.get("chest.rx", 0) + lean * 0.4
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * 0.010, planted_ankle_y(rig, side, 0), 0.078)
        c[f"foot{side}.pitch"] = 0
        c[f"pole.leg{side}"] = V(0.15 * sx, 0.3, 1)


def sceptre_rest(c, f, N, sway=1.0):
    """Right hand on the right thigh holding the sceptre upright (staff leaning out a little)."""
    arm_ik(c, "R", V(-0.074, 0.150, 0.060), V(-0.6, -0.5, -0.6))
    c["sceptre.dir"] = V(-0.18, 1.0, 0.10 + 0.02 * sway * wave(f, N, 1, 0.3))
    fingers(c, "R", 0)


def left_on_knee(c, f, N, tap=0.0):
    arm_ik(c, "L", V(0.054, 0.150, 0.078), V(0.7, -0.4, -0.6))
    c["handL.bend"] = 30
    fingers(c, "L", 30 + tap)


@clip("king", "sit_idle", 150, True,
      notes="seated, heavy: slow deep breathing with one sigh, slow head turns (neck leads), heavy slow blinks; the "
            "left hand rests on the knee, fingers drum once; the sceptre stands in the right fist")
def king_sit_idle(rig, f, N):
    c = k_base(rig, f, N, cycles=2)
    sit(rig, c)
    sigh = math.sin(math.pi * smooth((f - 60) / 34))
    c["chest.rx"] += -3 * sigh; c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh
    look = [(0, 0), (20, 0), (40, -8), (74, -8), (96, 5), (130, 5), (150, 0)]
    c["neck.ry"] = 0.45 * K(look, f, N, True); c["head.ry"] = 0.55 * KL(look, f, N, True, lag=6)
    c["head.rx"] = 1 + 2 * sigh; c["head.rz"] = 1.5 * wave(f, N, 1, 0.4)
    c["hips.rz"] = 0.8 * wave(f, N, 1, 0.1)
    sceptre_rest(c, f, N)
    tap = 0.0
    for t0 in (104, 109, 114):
        tap += 14 * max(0.0, math.sin(math.pi * (f - t0) / 5)) if t0 <= f <= t0 + 5 else 0.0
    left_on_knee(c, f, N, tap=-tap)
    blink(c, f, N, [30, 98, 136], slow=1.4)
    return c


@clip("king", "sit_talk", 96, True,
      notes="seated, speaks slowly: deep jaw in an irregular rhythm, nods on the stressed syllables, the left hand "
            "lifts from the knee palm-up and opens on the beats; leans in a little")
def king_sit_talk(rig, f, N):
    c = k_base(rig, f, N, cycles=2)
    sit(rig, c, lean=4)
    jk, beats = syllables(N, 23, amp=(5, 12), dur=(4.0, 8.0), gap=0.25)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=10); btl = beat_curve(beats, f - 4, N, width=12)
    c["head.rx"] = 1 + 3.5 * bt; c["head.ry"] = 4 * wave(f, N, 1, 0.2); c["head.rz"] = 2 * wave(f, N, 1, 0.5)
    phrase = K([(0, 0.2), (14, 0.9), (46, 1.0), (60, 0.3), (72, 0.8), (90, 0.5), (96, 0.2)], f, N, True)
    lift = phrase * (0.7 + 0.3 * btl)
    arm_ik(c, "L", V(0.060, 0.150 + 0.050 * lift, 0.078 + 0.020 * lift), V(0.8, -0.5, -0.4))
    c["handL.bend"] = 30 - 40 * lift; c["handL.twist"] = -40 * lift
    fingers(c, "L", 30 - 26 * btl)
    sceptre_rest(c, f, N)
    blink(c, f, N, [17, 70], slow=1.3)
    return c


@clip("king", "sit_listen", 120, True,
      notes="leans in toward the speaker, head tilted, strokes his beard with the left hand, slow 'hmm' nods; "
            "slow blinks")
def king_sit_listen(rig, f, N):
    c = k_base(rig, f, N, cycles=2, amp=0.8)
    sit(rig, c, lean=12)
    c["chest.rx"] += 4; c["neck.rx"] = 4; c["head.rz"] = 7 + 1.5 * wave(f, N, 1, 0.1)
    nod = K([(0, 0), (30, 0), (36, 5), (42, 0), (48, 4), (54, 0), (90, 0), (96, 4), (102, 0), (120, 0)], f, N, True)
    c["head.rx"] = 2 + nod; c["head.ry"] = 3 * wave(f, N, 1, 0.3)
    strokes = 0.5 + 0.5 * math.sin(2 * math.pi * 2 * f / N)
    arm_ik(c, "L", V(0.006, -0.040 - 0.010 * strokes, 0.040), V(0.8, -0.6, -0.2), "head")
    c["handL.bend"] = -10; fingers(c, "L", 40 + 15 * strokes)
    sceptre_rest(c, f, N)
    blink(c, f, N, [14, 64, 72], slow=1.3)
    return c


@clip("king", "give_ring", 60, False, markers={"release": 30},
      notes="careless: leans back with a sigh, then holds out his right hand (ring finger first, the sceptre tilting "
            "away) toward Haman and keeps it there; marker release = hand fully out, Haman may take the ring")
def king_give_ring(rig, f, N):
    c = k_base(rig, f, N, cycles=1, amp=0.6)
    lean = 4 - 6 * math.sin(math.pi * smooth(f / 16))
    sit(rig, c, lean=lean)
    out = ease_io((f - 10) / 20)
    over = math.sin(math.pi * smooth((f - 26) / 12))
    rest = V(-0.074, 0.150, 0.060)
    hand = V(-0.060, 0.168, 0.150) + V(0, 0.004, 0.004) * over
    arm_ik(c, "R", rest.lerp(hand, out), V(-0.7, -0.6, -0.3))
    c["sceptre.dir"] = V(-0.18, 1.0, 0.10).lerp(V(-0.75, 0.75, 0.0), out)
    c["handR.twist"] = 0
    fingers(c, "R", 0)
    left_on_knee(c, f, N)
    c["head.ry"] = -4 * out; c["head.rx"] = 3 * out - 2 * math.sin(math.pi * smooth(f / 16)); c["head.rz"] = 3 * out
    c["chest.ry"] = -5 * out
    blink(c, f, N, [6, 44], loop=False, slow=1.5, base=1.0 + 2.5 * out)      # bored, half-lidded
    return c


# The sceptre knob at the end of extend_sceptre (king-local, design): over the top of Esther's reach at the S08 marks.
EXTEND_TIP = V(-0.040, 0.270, 0.128)
EXTEND_DIR = V(0.22, 0.86, 0.46)


@clip("king", "extend_sceptre", 60, False, markers={"out": 30},
      notes="surprised, leans back a little and breathes in, then leans forward and holds the golden sceptre out to "
            "Esther, the knob lowering to her (tip lands at EXTEND_TIP, king-local) with a small overshoot; keeps it")
def king_extend_sceptre(rig, f, N):
    c = k_base(rig, f, N, cycles=1, amp=0.5)
    ant = math.sin(math.pi * smooth(f / 12))
    out = ease_io((f - 9) / 21)
    over = math.sin(math.pi * smooth((f - 27) / 14))
    sit(rig, c, lean=-4 * ant + 12 * out)
    c["chest.rx"] += -3 * ant
    rest_tip = V(-0.074 - 0.025, 0.150 + 0.135, 0.060 + 0.012)
    tip = rest_tip.lerp(EXTEND_TIP, out) + V(0, -0.006, 0.004) * over
    c["sceptre.tip"] = tip
    c["sceptre.dir"] = V(-0.18, 1.0, 0.10).lerp(EXTEND_DIR, out)
    arm_ik(c, "R", V(-0.074, 0.150, 0.060), V(-0.7, -0.5, -0.4))
    fingers(c, "R", 0)
    left_on_knee(c, f, N)
    c["head.rx"] = -3 * ant + 4 * out; c["head.rz"] = 4 * out; c["head.ry"] = -3 * out
    c["jaw.rx"] = 5 * ant
    blink(c, f, N, [2, 40], loop=False, slow=1.3)
    return c


@clip("king", "sit_smile", 120, True,
      notes="kind and relaxed: leans back a little, warm head tilt, chuckles (shoulders bounce three times), slow "
            "nod; left hand open on the knee; slow blinks")
def king_sit_smile(rig, f, N):
    c = k_base(rig, f, N, cycles=2)
    sit(rig, c, lean=-2)
    ch_ = 0.0
    for t0 in (40, 47, 54):
        if t0 <= f <= t0 + 6:
            ch_ = max(ch_, math.sin(math.pi * (f - t0) / 6))
    c["shoulderL.raise"] += 3 * ch_; c["shoulderR.raise"] += 3 * ch_; c["chest.rx"] += -2 * ch_
    c["jaw.rx"] = 3 * ch_
    c["head.rz"] = 5 + 2 * wave(f, N, 1, 0.2); c["head.rx"] = -2 * ch_ + K([(0, 0), (80, 0), (88, 4), (100, 0), (120, 0)], f, N, True)
    c["head.ry"] = 3 * wave(f, N, 1, 0.6)
    sceptre_rest(c, f, N)
    left_on_knee(c, f, N)
    fingers(c, "L", 14)
    blink(c, f, N, [24, 90], slow=1.4)
    return c


def k_stand(rig, c, spread=0.006, fwdL=0.0, fwdR=0.0, w=1.0):
    """Standing in front of the throne (forward of the seat edge)."""
    c["hips.tz"] = c.get("hips.tz", 0) + STAND_Z * w
    for side, sx, fw in (("L", 1, fwdL), ("R", -1, fwdR)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * spread, planted_ankle_y(rig, side, 0), b.z + STAND_Z + fw)
        c[f"foot{side}.pitch"] = 0


@clip("king", "stand_angry", 54, False, markers={"up": 26},
      notes="rises from the throne in anger: leans forward and grips (anticipation), pushes up and forward onto his "
            "feet in front of the seat, chest swells (overshoot), settles into a wide angry stance, fists; holds")
def king_stand_angry(rig, f, N):
    c = k_base(rig, f, N, cycles=1, amp=0.8)
    lean = math.sin(math.pi * smooth(f / 26))
    up = ease_io((f - 6) / 20)
    over = math.sin(math.pi * smooth((f - 22) / 16))
    c["hips.ty"] = lerp(SIT_TY, 0.0, up) - 0.006 * (1 - up) * lean + 0.004 * over
    c["hips.tz"] = lerp(SIT_TZ, STAND_Z - 0.004, up)
    c["hips.rx"] = lerp(-6, 0, up)
    c["spine.rx"] = lerp(4, 0, up) + 16 * lean; c["chest.rx"] += 4 * lean - 6 * over
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * lerp(0.010, 0.012, up), planted_ankle_y(rig, side, 0), lerp(0.078, b.z + STAND_Z, up))
        c[f"foot{side}.pitch"] = 0
        c[f"pole.leg{side}"] = V(0.15 * sx, 0.3, 1)
    # hands: left grips the knee then becomes a fist; right keeps the sceptre
    arm_ik(c, "L", V(0.054, 0.150, 0.078), V(0.7, -0.4, -0.6), "root", 1 - up)
    fingers(c, "L", lerp(30, 85, ease_io((f - 4) / 12)))
    c["upperArmL.raise"] = -14; c["upperArmL.bend"] = 10; c["forearmL.bend"] = 30
    arm_ik(c, "R", V(-0.074, 0.150, 0.060), V(-0.6, -0.5, -0.6), "root", 1 - up)
    c["upperArmR.raise"] = -16; c["upperArmR.bend"] = 14; c["forearmR.bend"] = 38
    c["sceptre.dir"] = V(-0.18, 1.0, 0.10)
    c["shoulderL.raise"] += 3 * over; c["shoulderR.raise"] += 3 * over
    c["head.rx"] = 4 * lean - 4 * over + 3 * up; c["neck.rx"] = -2 * over
    c["jaw.rx"] = 6 * over
    blink(c, f, N, [3], loop=False)
    return c


def k_angry_base(rig, f, N, cycles=2, amp=1.6):
    c = k_base(rig, f, N, cycles=cycles, amp=amp)
    c["hips.ty"] = 0.0; c["hips.tz"] = STAND_Z - 0.004
    k_stand(rig, c, spread=0.012, w=0.0)
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * 0.012, planted_ankle_y(rig, side, 0), b.z + STAND_Z)
        c[f"foot{side}.pitch"] = 0
    c["chest.rx"] += -6; c["head.rx"] = 3; c["neck.rx"] = 0
    c["upperArmL.raise"] = -14; c["upperArmL.bend"] = 10; c["forearmL.bend"] = 30
    c["upperArmR.raise"] = -16; c["upperArmR.bend"] = 14; c["forearmR.bend"] = 38
    c["sceptre.dir"] = V(-0.18, 1.0, 0.10)
    fingers(c, "L", 85)
    return c


@clip("king", "angry_idle", 90, True,
      notes="standing, furious: big heaving breaths, fists clench and loosen, weight shifts, a snort (head jerk) and "
            "a glare that does not leave its target")
def king_angry_idle(rig, f, N):
    c = k_angry_base(rig, f, N)
    sn = math.sin(math.pi * smooth((f - 50) / 6)) if 50 <= f <= 62 else 0.0
    c["head.rx"] += -4 * sn; c["neck.rx"] += -2 * sn; c["jaw.rx"] = 2 * sn
    sh = wave(f, N, 1, 0.2)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -1.6 * sh; c["chest.rz"] = 1.0 * sh
    fingers(c, "L", 78 + 10 * wave(f, N, 3, 0.1))
    c["head.ry"] = 2 * wave(f, N, 1, 0.5)
    blink(c, f, N, [18, 74])
    return c


@clip("king", "point_away", 45, False, markers={"point": 16},
      notes="orders Haman away: pulls the left arm back across the chest (anticipation), flings it out to his left, "
            "arm straight, hand flat, head and chest follow; overshoot and hold; the sceptre hand drops to his side")
def king_point_away(rig, f, N):
    c = k_angry_base(rig, f, N, cycles=1, amp=1.0)
    ant = math.sin(math.pi * smooth(f / 12))
    p = ease_io((f - 8) / 10)
    over = math.sin(math.pi * smooth((f - 15) / 12))
    start = V(0.080, 0.170, STAND_Z + 0.020)
    a_ = V(0.010, 0.230, STAND_Z + 0.060)
    far = V(0.185, 0.272, STAND_Z + 0.060) + V(0.004, 0.006, 0) * over
    tgt = start.lerp(a_, ant) if f < 8 else a_.lerp(far, p)
    arm_ik(c, "L", tgt, V(0.6, -0.7, -0.3))
    fingers(c, "L", lerp(85, 0, p)); c["handL.bend"] = -10 * p
    c["chest.ry"] = -8 * ant + 14 * p; c["spine.ry"] = 4 * p
    c["head.ry"] = 18 * p - 6 * ant; c["head.rx"] += -4 * p; c["jaw.rx"] = 8 * over
    c["hips.tx"] = 0.004 * p
    blink(c, f, N, [30], loop=False)
    return c


@clip("king", "celebrate", 60, True,
      notes="standing, glad and kind: both arms up (sceptre raised high in the right), bounces on his knees, head "
            "back laughing, the left hand waves; heavy, not quick")
def king_celebrate(rig, f, N):
    c = k_base(rig, f, N, cycles=2, amp=1.2)
    ph = 2 * math.pi * f / N
    b = 0.5 - 0.5 * math.cos(2 * ph)
    c["hips.ty"] = -0.012 * b; c["hips.tz"] = STAND_Z - 0.004
    for side, sx in (("L", 1), ("R", -1)):
        bf = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(bf.x + sx * 0.012, planted_ankle_y(rig, side, 0), bf.z + STAND_Z)
        c[f"foot{side}.pitch"] = 0
        c[f"pole.leg{side}"] = V(0.2 * sx, 0, 1)
    lag = 0.5 - 0.5 * math.cos(2 * ph - 0.8)
    c["upperArmL.raise"] = 104 + 10 * lag; c["upperArmL.bend"] = 20; c["forearmL.bend"] = 30 + 20 * math.sin(2 * ph - 1.2)
    c["upperArmL.swing"] = 6 * math.sin(ph)
    fingers(c, "L", 6); c["handL.bend"] = -10 * math.sin(2 * ph - 1.8)
    c["upperArmR.raise"] = 98 + 8 * lag; c["upperArmR.bend"] = 24; c["forearmR.bend"] = 28 + 10 * lag
    c["sceptre.dir"] = V(-0.10, 1.0, 0.05 + 0.15 * math.sin(ph - 0.6))
    c["head.rx"] = -8 - 3 * b; c["chest.rx"] += -4 - 2 * b
    c["jaw.rx"] = 6 + 6 * lag
    c["head.rz"] = 4 * math.sin(ph - 0.4); c["chest.rz"] = 2 * math.sin(ph)
    blink(c, f, N, [41])
    return c


# =============================================================================================== HAMAN
def h_base(rig, f, N, cycles=1, amp=1.0):
    c = {}
    b = wave(f, N, cycles)
    c["chest.rx"] = -3.0 - 1.5 * b * amp; c["spine.rx"] = -2.0
    c["hips.tz"] = 0.004
    c["shoulderL.raise"] = 1.2 * b * amp; c["shoulderR.raise"] = 1.2 * b * amp
    c["head.rx"] = -5
    c["upperArmL.raise"] = -22; c["upperArmR.raise"] = -22
    c["upperArmL.bend"] = 10; c["upperArmR.bend"] = 10
    c["forearmL.bend"] = 30; c["forearmR.bend"] = 30
    fingers(c, "L", 24); fingers(c, "R", 24)
    return c


def rub_hands(c, f, N, cycles, amp=1.0, lift=0.0):
    r = math.sin(2 * math.pi * cycles * f / N)
    arm_ik(c, "L", V(0.010 + 0.004 * r * amp, -0.032 + lift, 0.050), V(0.8, -0.6, -0.2), "chest")
    arm_ik(c, "R", V(-0.010 + 0.004 * r * amp, -0.034 + lift, 0.050 + 0.002 * r), V(-0.8, -0.6, -0.2), "chest")
    c["handL.bend"] = -16; c["handR.bend"] = -16
    fingers(c, "L", 34 + 8 * r); fingers(c, "R", 34 - 8 * r)


@clip("haman", "idle", 120, True,
      notes="comic and smug: rubs his hands together, bounces up on his toes twice, sly head tilts and glances, "
            "blinks (one slow sly one)")
def haman_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=2)
    rub_hands(c, f, N, 8, amp=K([(0, 1), (40, 1), (50, 0.2), (80, 0.2), (90, 1), (120, 1)], f, N, True))
    up = 0.0
    for t0 in (52, 64):
        if t0 <= f <= t0 + 12:
            up = max(up, math.sin(math.pi * (f - t0) / 12))
    c["hips.ty"] = -0.004 + 0.010 * up
    stand_feet(rig, c, spread=0.004, pitchL=30 * up, pitchR=30 * up, liftL=0.010 * up, liftR=0.010 * up)
    c["chest.rx"] += -2 * up
    tilt = K([(0, 0), (20, 0), (26, 8), (44, 8), (50, -3), (90, -3), (96, 5), (112, 5), (120, 0)], f, N, True)
    c["head.rz"] = tilt; c["head.ry"] = K([(0, 0), (24, -10), (46, -10), (52, 6), (92, 6), (98, 0), (120, 0)], f, N, True)
    c["neck.rz"] = 0.3 * KL([(0, 0), (20, 0), (26, 8), (44, 8), (50, -3), (90, -3), (96, 5), (112, 5), (120, 0)], f, N, True, lag=-2)
    sh = wave(f, N, 1, 0.1)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2 * sh
    blink(c, f, N, [12, 75], slow=1.0)
    blink_extra = {}
    blink(blink_extra, f, N, [100], slow=2.2)
    c["eyelids.sy"] = max(c["eyelids.sy"], blink_extra["eyelids.sy"])
    return c


H_STRUT = (0.070, 0.56)


@clip("haman", "strut", 30, True, markers={"contactL": 0, "contactR": 15}, speed=H_STRUT,
      notes="proud bouncy walk: chest out, leans back, knees lifted, big hip bounce, arms swing wide and stiff with "
            "the hands flopping late, chin up, head bobs on each step")
def haman_strut(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=H_STRUT[0], lift=0.026, duty=H_STRUT[1], heel=18, toeoff=26, lift_shape=0.7)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.005 + 0.007 * math.cos(2 * ph - 0.5)
    c["hips.ry"] = 7 * math.sin(ph); c["chest.ry"] = -9 * math.sin(ph - 0.3); c["head.ry"] = 4 * math.sin(ph - 0.7)
    c["hips.rz"] = 4 * math.cos(ph); c["chest.rz"] = -3 * math.cos(ph - 0.5)
    c["spine.rx"] = -5; c["chest.rx"] += -3
    c["head.rx"] = -8 + 3 * math.cos(2 * ph - 1.1)
    c["upperArmL.raise"] = -16; c["upperArmR.raise"] = -16
    c["upperArmL.bend"] = 10 - 30 * math.sin(ph - 0.2); c["upperArmR.bend"] = 10 + 30 * math.sin(ph - 0.2)
    c["forearmL.bend"] = 22 - 14 * math.sin(ph - 1.0); c["forearmR.bend"] = 22 + 14 * math.sin(ph - 1.0)
    c["handL.bend"] = 10 - 22 * math.sin(ph - 1.8); c["handR.bend"] = 10 + 22 * math.sin(ph - 1.8)
    fingers(c, "L", 12); fingers(c, "R", 12)
    blink(c, f, N, [22])
    return c


H_SNEAK = (0.080, 0.55)


@clip("haman", "walk", 24, True, markers={"contactL": 0, "contactR": 12}, speed=H_SNEAK, extra=True,
      notes="EXTRA (timeline S04 asks for haman walk; not in CONTRACT §4): a quick sneaky scurry on tiptoe, hunched "
            "forward, knees bent, hands rubbing at the chest, head low and glancing")
def haman_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=H_SNEAK[0], lift=0.018, duty=H_SNEAK[1], heel=-14, toeoff=30, lift_shape=0.8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.012 + 0.004 * math.cos(2 * ph - 0.5)
    c["spine.rx"] = 10; c["chest.rx"] = 6; c["head.rx"] = -10; c["neck.rx"] = -4
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.3)
    c["hips.rz"] = 2 * math.cos(ph)
    c["head.ry"] = K([(0, -6), (6, -6), (9, 6), (18, 6), (21, -6), (24, -6)], f, N, True)
    rub_hands(c, f, N, 4, amp=1.0, lift=0.010)
    blink(c, f, N, [16])
    return c


@clip("haman", "talk", 90, True,
      notes="oily talk: jaw in an irregular rhythm, shrugs and palms-up gestures on the stressed syllables, head "
            "waggles, leans in and out")
def haman_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2)
    jk, beats = syllables(N, 37, amp=(6, 15), dur=(3.0, 6.0), gap=0.18)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=8); btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rz"] = 6 * wave(f, N, 2, 0.1); c["head.ry"] = 5 * wave(f, N, 1, 0.3); c["head.rx"] = -5 + 3 * bt
    phrase = K([(0, 0.3), (10, 1.0), (36, 0.8), (46, 0.2), (58, 1.0), (80, 0.9), (90, 0.3)], f, N, True)
    lift = phrase * (0.7 + 0.3 * btl)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = -22 + 14 * lift; c[f"upperArm{side}.bend"] = 10 + 26 * lift
        c[f"forearm{side}.bend"] = 30 + 46 * lift; c[f"forearm{side}.twist"] = -sx * 70 * lift
        c[f"hand{side}.bend"] = -20 * btl
        fingers(c, side, 26 - 24 * btl)
    c["shoulderL.raise"] += 5 * bt; c["shoulderR.raise"] += 5 * bt
    c["spine.rx"] += 4 * phrase; c["hips.tz"] -= 0.004 * phrase
    blink(c, f, N, [27, 80])
    stand_feet(rig, c, spread=0.004)
    return c


@clip("haman", "demand", 45, False, markers={"wide": 16},
      notes="'everyone must bow to me!': crouches and draws his arms in (anticipation), springs up onto his toes and "
            "throws his arms wide and up, chest out, chin up; bounces down and holds the pose")
def haman_demand(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    ant = math.sin(math.pi * smooth(f / 10))
    w = ease_io((f - 7) / 9)
    up = math.sin(math.pi * smooth((f - 8) / 16))
    c["hips.ty"] = -0.016 * ant + 0.010 * up
    stand_feet(rig, c, spread=0.010 * w, pitchL=26 * up, pitchR=26 * up, liftL=0.008 * up, liftR=0.008 * up)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = -26 - 8 * ant + 100 * w + 8 * up
        c[f"upperArm{side}.bend"] = 10 + 14 * ant + 8 * w
        c[f"forearm{side}.bend"] = 30 + 40 * ant - 18 * w
        c[f"forearm{side}.twist"] = -sx * 50 * w
        c[f"hand{side}.bend"] = -24 * w + 10 * up
        fingers(c, side, 50 * ant + 4)
    c["chest.rx"] += 6 * ant - 8 * w - 3 * up; c["spine.rx"] += 4 * ant - 3 * w
    c["head.rx"] = -5 + 6 * ant - 10 * w; c["jaw.rx"] = 10 * up
    blink(c, f, N, [30], loop=False)
    return c


@clip("haman", "whisper", 90, True,
      notes="sly whisper: leans to his right and forward toward the king, right hand cupped at the side of his mouth, "
            "left hand behind his back; jaw murmurs, eyebrows of the sly face; sneaky glances back")
def haman_whisper(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    c["hips.tx"] = -0.006; c["hips.rz"] = 3
    c["spine.rz"] = -6; c["chest.rz"] = -6; c["spine.rx"] = 8; c["chest.rx"] = 4
    c["neck.rz"] = -2; c["head.rz"] = -6 + 2 * wave(f, N, 2, 0.1)
    jk, beats = syllables(N, 41, amp=(3, 7), dur=(3.0, 6.0), gap=0.3)
    c["jaw.rx"] = jaw_from(jk, f, N)
    gl = [(0, 0), (40, 0), (44, 14), (56, 14), (60, 0), (90, 0)]
    c["head.ry"] = -4 + K(gl, f, N, True)
    arm_ik(c, "R", V(-0.026, -0.016, 0.026), V(-0.9, -0.4, -0.1), "head")
    c["handR.bend"] = -30; fingers(c, "R", 30)
    arm_ik(c, "L", V(0.030, 0.150, -0.040), V(0.8, -0.2, 0.6))
    fingers(c, "L", 40)
    stand_feet(rig, c, spread=0.006, xR=-0.004, pitchL=8)
    blink(c, f, N, [20, 70])
    return c


@clip("haman", "take_ring", 45, False, markers={"grab": 20},
      notes="greedy snatch: rubs his hands and leans back (anticipation), darts the left hand forward and up and "
            "grabs the ring, pulls it to his chest, admires it with a gleeful bounce; holds")
def haman_take_ring(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    ant = math.sin(math.pi * smooth(f / 12))
    reach = ease_io((f - 10) / 10)
    back = ease_io((f - 24) / 10)
    hop = math.sin(math.pi * smooth((f - 32) / 10))
    rub_hands(c, f, N, 3, amp=1 - reach)
    near = V(0.036, 0.205, 0.060)
    far = V(0.030, 0.262, 0.175)
    chest = V(0.016, 0.240, 0.072)
    if f < 24:
        arm_ik(c, "L", near.lerp(far, reach), V(0.8, -0.5, -0.3), "root", reach)
    else:
        arm_ik(c, "L", far.lerp(chest, back), V(0.8, -0.6, -0.2), "root", 1.0)
    fingers(c, "L", 34 * (1 - reach) + 5 * reach if f < 19 else 80)
    c["handL.bend"] = -10 * reach + 10 * back
    c["spine.rx"] += -6 * ant + 10 * reach * (1 - back); c["chest.rx"] += 4 * reach * (1 - back) - 3 * hop
    c["head.rx"] = -5 + 6 * back; c["head.ry"] = 8 * back; c["head.rz"] = 6 * back
    c["hips.ty"] = 0.008 * hop
    stand_feet(rig, c, spread=0.004, fwdL=0.016 * reach * (1 - back), pitchL=20 * hop, pitchR=20 * hop, liftL=0.006 * hop, liftR=0.006 * hop)
    c["jaw.rx"] = 6 * hop
    blink(c, f, N, [4, 38], loop=False)
    return c


def arms_crossed(c):
    arm_ik(c, "L", V(-0.032, -0.022, 0.050), V(0.9, -0.4, 0.3), "chest")
    arm_ik(c, "R", V(0.034, -0.016, 0.060), V(-0.9, -0.4, 0.3), "chest")
    c["handL.bend"] = 10; c["handR.bend"] = 10
    fingers(c, "L", 50); fingers(c, "R", 50)


@clip("haman", "smug", 120, True,
      notes="arms crossed, chin up, half-lidded eyes, taps his right foot, head bobs to it, nose in the air; one slow "
            "self-satisfied nod")
def haman_smug(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    arms_crossed(c)
    c["chest.rx"] += -3; c["head.rx"] = -9
    tap = 0.0
    for t0 in (10, 22, 34, 46, 70, 82, 94):
        if t0 <= f <= t0 + 8:
            tap = max(tap, math.sin(math.pi * (f - t0) / 8))
    stand_feet(rig, c, spread=0.006, fwdR=0.010, pitchR=-18 * tap)
    c["head.rx"] += 2 * tap; c["head.rz"] = 3 * wave(f, N, 1, 0.2)
    nod = K([(0, 0), (56, 0), (62, 6), (70, -2), (76, 0), (120, 0)], f, N, True)
    c["head.rx"] += nod
    c["head.ry"] = 6 * wave(f, N, 1, 0.6)
    sh = wave(f, N, 1, 0.4)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2 * sh
    blink(c, f, N, [40, 104], base=3.5, slow=1.6)
    return c


CAP_SLIP = {"cap.rx": -42.0, "cap.rz": 22.0, "cap.tz": -0.010, "cap.ty": -0.003, "cap.tx": 0.003}


def cap_slipped(c, w):
    for k, v in CAP_SLIP.items():
        c[k] = v * w


@clip("haman", "shock", 36, False, markers={"slip": 10},
      notes="caught! freezes for a beat, jumps straight up with arms flung out, the cap pops and slips back askew "
            "(marker slip), lands knock-kneed and crouched, hands up; cap stays askew (and in cower / led_away)")
def haman_shock(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.0)
    jump = math.sin(math.pi * (f - 3) / 12) if 3 <= f <= 15 else 0.0
    land = ease_io((f - 14) / 10)
    c["hips.ty"] = 0.040 * jump - 0.040 * land - 0.010 * math.sin(math.pi * smooth((f - 14) / 8))
    c["hips.tz"] = -0.010 * land
    stand_feet(rig, c, spread=0.006 * land, pitchL=20 * jump, pitchR=20 * jump, liftL=0.030 * jump, liftR=0.030 * jump, xL=-0.004 * land, xR=0.004 * land)
    c["pole.legL"] = V(-0.2, 0, 1); c["pole.legR"] = V(0.2, 0, 1)
    fling = math.sin(math.pi * smooth((f - 2) / 16))
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = -22 + 118 * fling
        c[f"forearm{side}.bend"] = 30 + 30 * fling
        fingers(c, side, 0)
    cw = cower_pose_weights(land)
    for k, v in cw.items():
        c[k] = v
    c["spine.rx"] = -6 * jump + 14 * land; c["head.rx"] = -8 * jump + 6 * land
    pop = math.sin(math.pi * smooth((f - 4) / 8)) if f < 12 else 0.0
    cap_slipped(c, ease_io((f - 4) / 6))
    c["cap.ty"] = c.get("cap.ty", 0) + 0.012 * pop
    c["jaw.rx"] = 14 * fling
    c["eyelids.sy"] = 1.0
    return c


def cower_pose_weights(w):
    c = {}
    if w <= 0:
        return c
    arm_ik(c, "L", V(0.016, 0.060, 0.050), V(0.8, -0.6, -0.1), "chest", w)
    arm_ik(c, "R", V(-0.016, 0.056, 0.054), V(-0.8, -0.6, -0.1), "chest", w)
    c["handL.bend"] = -30 * w; c["handR.bend"] = -30 * w
    return c


H_COWER_TY = -0.040


@clip("haman", "cower", 48, True,
      notes="crouched and trembling, knees together, hands up in front of his face, peeks out between them and ducks "
            "back; cap askew")
def haman_cower(rig, f, N):
    c = h_base(rig, f, N, cycles=4, amp=0.6)
    tr = math.sin(2 * math.pi * 6 * f / N) * 0.6 + math.sin(2 * math.pi * 10 * f / N) * 0.4
    c["hips.ty"] = H_COWER_TY + 0.002 * tr; c["hips.tz"] = -0.010
    c["hips.tx"] = 0.0015 * tr
    stand_feet(rig, c, spread=0.006, xL=-0.004, xR=0.004)
    c["pole.legL"] = V(-0.2, 0, 1); c["pole.legR"] = V(0.2, 0, 1)
    c["spine.rx"] = 14; c["chest.rx"] = 6; c["neck.rx"] = 4
    peek = K([(0, 0), (14, 0), (18, 1), (28, 1), (31, 0), (48, 0)], f, N, True)
    for k, v in cower_pose_weights(1.0).items():
        c[k] = v
    c["ik.armL"] = c["ik.armL"] + V(0.012 * peek, -0.008 * peek, 0) + V(0, 0.0015 * tr, 0)
    c["ik.armR"] = c["ik.armR"] + V(-0.012 * peek, -0.008 * peek, 0) + V(0, -0.0015 * tr, 0)
    c["head.rx"] = 6 - 6 * peek; c["head.ry"] = 6 * peek; c["head.rz"] = 2 * tr
    fingers(c, "L", 10 + 6 * tr); fingers(c, "R", 10 - 6 * tr)
    c["jaw.rx"] = 4 + 2 * tr
    cap_slipped(c, 1.0)
    blink(c, f, N, [8, 40])
    return c


H_BACK = (0.050, 0.62)


@clip("haman", "led_away", 36, True, markers={"contactL": 0, "contactR": 18}, speed=H_BACK,
      notes="backward shuffle: crouched, little quick steps backward, hands up, glances back over his shoulder and "
            "back to the king; cap askew")
def haman_led_away(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    g = gait(rig, f, N, L=H_BACK[0], lift=0.012, duty=H_BACK[1], heel=6, toeoff=16, back=True)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = H_COWER_TY * 0.6 + 0.003 * math.cos(2 * ph)
    c["hips.tz"] = -0.006
    c["spine.rx"] = 12; c["chest.rx"] = 4
    c["hips.ry"] = 4 * math.sin(ph); c["hips.rz"] = 2 * math.cos(ph)
    for k, v in cower_pose_weights(1.0).items():
        c[k] = v
    c["ik.armL"] = c["ik.armL"] + V(0, 0.002 * math.sin(2 * ph), 0)
    c["ik.armR"] = c["ik.armR"] + V(0, 0.002 * math.sin(2 * ph + 1), 0)
    fingers(c, "L", 10); fingers(c, "R", 10)
    gl = [(0, 0), (8, 0), (12, 28), (20, 28), (24, 0), (36, 0)]
    c["head.ry"] = K(gl, f, N, True); c["neck.ry"] = 0.4 * KL(gl, f, N, True, lag=-2)
    c["head.rx"] = 4
    c["jaw.rx"] = 3 + 2 * math.sin(4 * ph)
    cap_slipped(c, 1.0)
    blink(c, f, N, [26])
    return c


# =============================================================================================== evaluation
def apply_ik(rig, basis, M, chs):
    for limb, (up, lo, end) in (("legL", ("thighL", "shinL", "footL")), ("legR", ("thighR", "shinR", "footR")),
                                ("armL", ("upperArmL", "forearmL", "handL")), ("armR", ("upperArmR", "forearmR", "handR"))):
        key = "ik." + limb
        if key not in chs:
            continue
        w = chs.get("ikw." + limb, 1.0)
        if w <= 1e-4:
            continue
        legs = limb.startswith("leg")
        side = limb[-1]
        sx = 1 if side == "L" else -1
        t = Vector(chs[key])
        space = chs.get("ikspace." + limb, "root")
        Mroot = M["root"] @ rig.rest["root"].inverted()
        if space in M and space != "root":
            Mc = M[space]
            t_world = to_d(Mc @ (rig.rest[space].inverted() @ to_bl(rig.head[space] + t)))
        else:
            t_world = to_d(Mroot @ to_bl(t))
        pole = V(0.15 * sx, 0, 1) if legs else V(0.6 * sx, -0.6, -0.5)
        if "pole." + limb in chs:
            pole = Vector(chs["pole." + limb])
        Pm = (M[space] @ rig.rest[space].inverted()).to_3x3() if (space in M and space != "root") else Mroot.to_3x3()
        pole = to_d(Pm @ to_bl(pole))
        old = {n: [basis[n][0].copy(), basis[n][1].copy(), basis[n][2]] for n in (up, lo, end)}
        ik2(rig, basis, M, up, lo, t_world, pole, legs)
        if legs:
            pitch = chs.get(f"foot{side}.pitch", 0.0)
            Rf = Mroot.to_3x3().normalized() @ rot_d((1, 0, 0), pitch) @ rig.rest3[end]
            rig.set_world_rot(basis, M, end, Rf)
        else:
            # keep the hand's channel rotation (bend etc.) relative to the new forearm
            pass
        if w < 0.9999:
            for n in (up, lo, end):
                basis[n][0] = old[n][0].slerp(basis[n][0], w)
            rig.fk(basis, M)


def aim_sceptre(rig, basis, M, want_d):
    """Turn the right hand (minimal rotation) so the sceptre bone points along want_d (design, root space)."""
    Mroot = M["root"] @ rig.rest["root"].inverted()
    want = (Mroot.to_3x3() @ (C @ Vector(want_d))).normalized()
    cur = M["sceptre"].to_3x3().normalized().col[1].normalized()
    Rd = cur.rotation_difference(want).to_matrix()
    Rh = M["handR"].to_3x3().normalized()
    rig.set_world_rot(basis, M, "handR", Rd @ Rh)


def king_sceptre(rig, basis, M, chs):
    if "sceptre.dir" not in chs and "sceptre.tip" not in chs:
        return
    d = Vector(chs.get("sceptre.dir", V(0, 1, 0)))
    if "sceptre.tip" in chs:
        tip = Vector(chs["sceptre.tip"])
        target = Vector(chs["ik.armR"])
        for _ in range(4):
            ch2 = dict(chs); ch2["ik.armR"] = target
            apply_ik(rig, basis, M, {k: v for k, v in ch2.items() if k.endswith("armR")})
            aim_sceptre(rig, basis, M, d)
            err = rig.pos(M, "sceptreTip") - tip
            target = target - err
        chs["ik.armR"] = target
    else:
        aim_sceptre(rig, basis, M, d)


def evaluate_primary(rig, clip_, f):
    chs = clip_.fn(rig, f, clip_.N)
    basis = rig.basis_from(chs)
    M = rig.fk(basis)
    apply_ik(rig, basis, M, chs)
    if rig.ch == "king":
        king_sceptre(rig, basis, M, chs)
    return chs, basis, M


CHAINS = {
    # name list, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "esther": [(("braid1", "braid2", "braid3"), 70.0, 8.0, 0.35, 28.0, "braid.bias"),
               (("cape1", "cape2"), 90.0, 9.0, 0.25, 22.0, None)],
    "king": [(("sceptre",), 220.0, 18.0, 0.0, 3.0, None)],
    "haman": [],
}


def sim_chains(rig, prim, loop):
    """Damped spring chains (braid, cape, sceptre wobble). Mutates prim[f] basis/M. Loops: 3 cycles, keep the last,
    spread the residual over the cycle so frame N == frame 0."""
    N = len(prim) - 1
    for names, k, cdamp, gw, lim, bias_key in CHAINS[rig.ch]:
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
            bias = chs.get(bias_key) if bias_key else None
            for n in names:
                Cm = rig.carried(M, n).to_3x3().normalized()
                cur_c = (Cm @ basis[n][0].to_matrix()).col[1].normalized()      # keyed (carried) direction
                rest_w = (Mroot3 @ rig.rest3[n].col[1]).normalized()
                tgt = cur_c.slerp(rest_w, gw) if gw > 0 else cur_c
                if bias is not None and Vector(bias).length > 1e-6:
                    tgt = (tgt + Mroot3 @ (C @ Vector(bias)) * 0.6).normalized()
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
            # closing correction: rotate each bone's direction by a growing fraction of (N -> 0) mismatch
            for fr in range(N + 1):
                chs, basis, M = prim[fr]
                for n in names:
                    pass
            for n in names:
                d0, dN = out[n][0], out[n][N]
                Rfull = dN.rotation_difference(d0)
                for fr in range(N + 1):
                    q = Rfull.copy()
                    q = q.slerp(q, 1.0) if False else q
                    from mathutils import Quaternion
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
        # the last frame must equal the first exactly
        chs0, b0, M0 = prim[0]
        bN = {n: [b0[n][0].copy(), b0[n][1].copy(), b0[n][2].copy()] for n in b0}
        prim[N] = (prim[N][0], bN, rig.fk(bN))
    sim_chains(rig, prim, clip_.loop)
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
        pm = act.pose_markers.new(mname); pm.frame = int(mf)
    return act


# =============================================================================================== scene helpers
def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rigs = {ch: Rig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    return sc, rigs


def contract_clips():
    return {"esther": ["idle", "walk", "talk", "worried", "pray", "rise_brave", "climb", "bow", "touch_sceptre", "invite",
                       "point", "joy", "wave"],
            "king": ["sit_idle", "sit_talk", "sit_listen", "give_ring", "extend_sceptre", "sit_smile", "stand_angry",
                     "angry_idle", "point_away", "celebrate"],
            "haman": ["idle", "strut", "talk", "demand", "whisper", "take_ring", "smug", "shock", "cower", "led_away"]}


def timeline_clips():
    return sorted({(a["who"], a["clip"]) for a in TL["acting"]})


def mesh_points(rig, step_n=2500):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in rig.obj.children:
        if o.type != 'MESH' or o.hide_render or o.name.endswith("_eyelids"):
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


SEATED = {"sit_idle", "sit_talk", "sit_listen", "give_ring", "extend_sceptre", "sit_smile"}


def clip_checks(rig, cl, frames):
    out = {}
    ad = rig.obj.animation_data
    keep = ad.action if ad else None
    if ad:
        ad.action = None
    loc0, rot0 = rig.obj.location.copy(), rig.obj.rotation_euler.copy()
    rig.obj.location = (0, 0, 0); rig.obj.rotation_euler = (0, 0, 0)
    step = 3 if cl.N <= 60 else 5
    lows, seat = [], []
    for fr in range(0, cl.N + 1, step):
        apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
        pts = mesh_points(rig)
        lp = min(pts, key=lambda q: q[0].y)
        lows.append(lp[0].y)
        if lp[0].y <= min(lows):
            low_at = [fr, lp[1], [round(v, 3) for v in lp[0]]]
        if rig.ch == "king" and cl.name in SEATED:
            # robe underside over the cushion (cushion top SEAT_H above the root): positive = gap, negative = sinks in
            # under the buttocks only (|x| < 0.03, z -0.06..0): the skirt hanging from the knees is not seat contact
            sp = [p for p, _ in pts if abs(p.x) < 0.03 and -0.06 < p.z < 0.0 and p.y > SEAT_H - 0.06]
            if sp:
                seat.append(min(p.y for p in sp) - SEAT_H)
    out["meshMinY"] = round(min(lows), 4)
    if min(lows) < -0.004:
        out["meshMinAt"] = low_at
    if seat:
        out["seatGap"] = [round(min(seat), 4), round(max(seat), 4)]
    if cl.speed is None:
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
        out["naturalSpeed"] = round(cl.natural_speed, 4)
    reset_pose(rig)
    rig.obj.location, rig.obj.rotation_euler = loc0, rot0
    if ad:
        ad.action = keep
    return out


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have[w]]
    req = TL.get("requestedClips") or []
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl, "requestedClips": req,
            "stage": {"daisTop": DAIS_TOP, "throne": THRONE, "stepFoot": STEP_FOOT, "seatAboveRoot": SEAT_H,
                      "kingStandZ": STAND_Z, "sceptreTipKingLocal": [round(v, 4) for v in EXTEND_TIP]}}
    only = os.environ.get("ES_ONLY")
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
        info = {"action": cl.action, "char": cl.ch, "clip": cl.name, "frames": cl.N, "seconds": round(cl.N / FPS, 3),
                "loop": cl.loop, "rootMotion": False,
                "markers": {k: {"frame": v, "sec": round(v / FPS, 3)} for k, v in cl.markers.items()},
                "loopSeamMaxErr": None if seam is None else round(seam, 6), "rootMaxOffset": round(rootmax, 5),
                "notes": cl.notes}
        if cl.extra:
            info["extra"] = True
        if cl.speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            info["stride"] = cl.speed[0]
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in
                             ("head", "jaw", "handR", "handL", "footL", "toeR", "hips", "braid3", "sceptreTip", "cap") if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        if cl.action == "king_extend_sceptre":
            info["checks"]["sceptreTipEnd"] = [round(v, 4) for v in rig.pos(frames[-1][1], "sceptreTip")]
        print("ES_CHECK", cl.action, json.dumps(info["checks"]))
        meta["clips"].append(info)
        print(f"ES_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} root={info['rootMaxOffset']}")
    if only:
        print("ES_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "es_anim.blend")
    bpy.ops.wm.save_as_mainfile(filepath=tmp_blend, compress=True)
    for ch in CHARS:
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
        print("ES_EXPORT", ch)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("ES_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


def fix_uv_order(o):
    """Page UVs must be the FIRST UV map (glTF TEXCOORD_0, 0..1, what DGPaperLit samples the scan with) and the face
    decal the SECOND (TEXCOORD_1), as in David & Goliath. model/*.glb and characters.blend have them the other way
    round (['decal', 'UVMap']); rebuild the layers in the right order. The page layer is found by name, else by range."""
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
    """min / max of a float VEC2 accessor, read from the GLB binary chunk (the exporter writes no min/max for UVs)."""
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
                          "nodes": len(j["nodes"]), "meshes": len(j.get("meshes", [])), "uv": uv, "uv0InUnitSquare": uv0_ok}
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
            print(f"ES_VERIFY {ch} {nm} {a['frames']}f {a['seconds']}s ch={a['channels']} sampleErr={out['sampleErr'][ch].get(nm)}")
        print(f"ES_VERIFY_GLB {ch} bytes={out['glb'][ch]['bytes']} skins={out['glb'][ch]['skins']} meshes={out['glb'][ch]['meshes']} "
              f"uv0InUnitSquare={out['glb'][ch]['uv0InUnitSquare']} uv={json.dumps(out['glb'][ch]['uv'])}")
    print("ES_VERIFY_MISSING", json.dumps(out["contractMissing"]))


# ----------------------------------------------------------------------------------------------- render helpers
REGIONS = json.load(open(os.path.join(MODEL, "regions_characters.json")))
FACES = json.load(open(FACES_JSON))
DESIGN = json.load(open(os.path.join(ES, "design.json")))
DECAL_NODES = {}


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
    dt.image = bpy.data.images.load(os.path.join(ROOT, f"docs/esther/design/faces/{ch}_{fd['default']}.png"), check_existing=True)
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
    if clip_name == "kneel":
        expr = "pray" if ch == "esther" else expr
    if ch == "haman" and clip_name == "walk":
        expr = "sly"
    DECAL_NODES[ch].image = bpy.data.images.load(os.path.join(ROOT, f"docs/esther/design/faces/{ch}_{expr}.png"), check_existing=True)


def setup_look(sc, res, samples=12, palace=True):
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
    vs = [(-R_, -R_, 0), (R_, -R_, 0), (R_, R_, 0), (-R_, R_, 0), (-R_, -R_, R_), (R_, -R_, R_), (R_, R_, R_), (-R_, R_, R_)]
    me.from_pydata(vs, [], [(0, 1, 2, 3), (3, 2, 6, 7), (0, 4, 5, 1), (1, 5, 6, 2), (0, 3, 7, 4)])
    fo = bpy.data.objects.new("floor", me); sc.collection.objects.link(fo)
    fm = bpy.data.materials.new("floor"); fm.use_nodes = True
    fm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.82, 0.78, 0.70, 1); me.materials.append(fm)
    if palace and os.path.exists(PALACE_GLB):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=PALACE_GLB)
        new = [o for o in bpy.data.objects if o not in before]
        art = DESIGN["sheet"]["art"]; Wp, Hp = DESIGN["sheet"]["page"]
        pm = bpy.data.materials.new("anim_palace"); pm.use_nodes = True; nt = pm.node_tree
        bsdf = nt.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = 0.85
        bsdf.inputs["Base Color"].default_value = (0.78, 0.66, 0.50, 1)
        demo = os.path.join(ES, "sheet", "palace_proposal_demo.png")
        if os.environ.get("ES_PALACE_TEX") and os.path.exists(demo):
            tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(demo, check_existing=True)
            tex.extension = 'EXTEND'
            uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
            mp = nt.nodes.new("ShaderNodeMapping")
            mp.inputs["Location"].default_value = (art[0] / Wp, (Hp - art[1] - art[3]) / Hp, 0)
            mp.inputs["Scale"].default_value = (art[2] / Wp, art[3] / Hp, 1)
            nt.links.new(uvn.outputs["UV"], mp.inputs[0]); nt.links.new(mp.outputs[0], tex.inputs["Vector"])
            nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
        for o in new:
            if o.type == 'MESH':
                for i in range(len(o.material_slots)):
                    o.material_slots[i].material = pm
            if o.name.startswith(("table", "goblet", "bowl", "bread")):
                o.hide_render = True
        for o in new:
            o.select_set(False)


def camera(sc):
    cam = bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.clip_start = 0.01; cam.data.clip_end = 50
    return cam


def look(cam, target_d, cam_d, lens=40):
    cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.location = to_bl(cam_d)
    cam.rotation_euler = (to_bl(target_d) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def place_rig(rig, x, z, yaw_deg, y=0.0):
    rig.obj.location = to_bl(V(x, y, z))
    rig.obj.rotation_euler = (0, 0, math.radians(yaw_deg))


def show_only(rigs, chs):
    for ch, r in rigs.items():
        vis = ch in chs
        r.obj.hide_render = not vis
        for o in r.obj.children:
            o.hide_render = (not vis)


def stage_of(cl):
    """Where a clip is shown in renders: (x, z, yaw, y)."""
    if cl.ch == "king":
        return (THRONE[0], THRONE[1], 0.0, DAIS_TOP)
    if cl.ch == "esther" and cl.name in ("bow", "touch_sceptre"):
        # facing the throne (yaw 180); shown on the open floor so the braziers by the steps do not hide her
        return (-0.12, 0.12, 180.0, 0.0)
    if cl.ch == "esther":
        return (-0.12, 0.12, 0.0, 0.0)
    return (0.24, 0.06, 0.0, 0.0)


def view_cam(cam, rig, mark, view, bone=None, dist_k=2.3):
    x, z, yaw0, y0 = mark
    H = rig.H
    yaw = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "top": 25, "low": 25}[view] + yaw0
    tgt = V(x, y0 + H * 0.5, z); dist = H * dist_k; hgt = y0 + H * 0.62
    if bone:
        tgt = to_d(rig.obj.matrix_world @ rig.obj.pose.bones[bone].head); dist = H * 0.9; hgt = tgt.y + 0.02
    if view == "top":
        hgt = y0 + dist * 1.3
    if view == "low":
        hgt = y0 + 0.03
    a_ = math.radians(yaw)
    look(cam, tgt, V(tgt.x + math.sin(a_) * dist, hgt, tgt.z + math.cos(a_) * dist))


def mode_contact():
    sc, rigs = open_scene()
    setup_look(sc, (400, 400), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    for cl in CLIPS:
        rig = rigs[cl.ch]
        show_only(rigs, [cl.ch])
        set_expression(cl.ch, cl.name)
        frames = bake_clip(rig, cl)
        mk = sorted(set(cl.markers.values()))
        picks = sorted(set([0, cl.N] + [int(round(cl.N * k / 5)) for k in range(1, 5)] + mk))
        while len(picks) > 7:
            cand = [p for p in picks if p not in mk and p not in (0, cl.N)]
            if not cand:
                break
            picks.remove(cand[len(cand) // 2])
        mark = stage_of(cl)
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": [], "extra": cl.extra}
        for fr in picks:
            apply_basis(rig, frames[fr][0])
            place_rig(rig, mark[0], mark[1], mark[2], mark[3])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, "lside" if mark[2] == 180.0 else "q3", dist_k=1.75)
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("ES_CONTACT_ROW", cl.action, picks, flush=True)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """ES_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'scene:sceptre[:frame]' renders the S08 staging (king extend_sceptre end + Esther touch_sceptre at `touch`)."""
    sc, rigs = open_scene()
    res = int(os.environ.get("ES_PROBE_RES", "480"))
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
    for item in os.environ.get("ES_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "scene":
            k = rigs["king"]; e = rigs["esther"]
            show_only(rigs, ["king", "esther"])
            set_expression("king", "extend_sceptre"); set_expression("esther", "touch_sceptre")
            fe = int(parts[2]) if len(parts) > 2 else clips["esther_touch_sceptre"].markers["touch"]
            fk_ = int(parts[3]) if len(parts) > 3 else clips["king_extend_sceptre"].N
            apply_basis(k, bk("king_extend_sceptre")[fk_][0]); place_rig(k, THRONE[0], THRONE[1], 0, DAIS_TOP)
            apply_basis(e, bk("esther_touch_sceptre")[fe][0]); place_rig(e, STEP_FOOT[0], STEP_FOOT[1], 180, 0)
            bpy.context.view_layer.update()
            for nm, cpos, tgt in (("side", V(0.75, 0.30, -0.20), V(0, 0.22, -0.21)), ("q3", V(0.45, 0.42, 0.45), V(0, 0.20, -0.20)),
                                  ("close", V(0.28, 0.36, -0.05), V(-0.03, 0.31, -0.17))):
                look(cam, tgt, cpos, lens=40)
                fn = f"scene_sceptre_{fe}_{nm}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True); out.append(fn)
            reset_pose(k); reset_pose(e)
            continue
        action, frames, view = parts[0], parts[1], parts[2] if len(parts) > 2 else "q3"
        bone = None
        if "#" in view:
            view, bone = view.split("#")
        cl = clips[action]; rig = rigs[cl.ch]
        show_only(rigs, [cl.ch])
        set_expression(cl.ch, cl.name)
        fr_ = bk(action)
        mark = stage_of(cl)
        for fr in [int(v) for v in frames.split(",")]:
            fr = min(fr, cl.N)
            apply_basis(rig, fr_[fr][0]); place_rig(rig, mark[0], mark[1], mark[2], mark[3])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, view, bone)
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("ES_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)
    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("ES_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
