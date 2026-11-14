"""Daniel skeletal animation (Animation role, story pack #4: Daniel and the lions).

Adapted from pipeline/ru_animate.py (Ruth), itself from es_animate.py / dg_animate.py: same clip-function method,
IK, spring chains, export, verify and contact sheet, plus a quadruped layer for the two lions (paw IK with planted
tips, four-beat gait, sit / lie / roll-over poses).

* Under Blender (headless) it opens `assets/daniel/model/characters.blend` (Characters role's rigs, read fresh on every
  run, so new sheet UVs are picked up), builds every clip of docs/daniel/CONTRACT.md §4 as an action `<char>_<clip>` and
  exports `assets/daniel/anim/{daniel,king,officer,lion,lion2}.glb` (character + skin + one glTF animation per action)
  and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/da_animate.py all        # build + verify + contact sheet + freshness check
    python3 pipeline/da_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/da_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/da_animate.py contact    # anim/contact_sheet.png (key poses per clip + pair rows)
    python3 pipeline/da_animate.py fresh      # are the model files newer than the anim exports?
    DA_PROBE="lion_roll_over:0,60,120:q3" python3 pipeline/da_animate.py probe     # $DA_ANIM_WORK/probe.png
    DA_PROBE="pair:king_hug:daniel_hug:0.11:30" python3 pipeline/da_animate.py probe   # two actors facing
    DA_ONLY=lion_,daniel_kneel  (with build: bake + check a subset, no export)

How the motion is made (no hand-placed keys; the script is the source):
  * Each clip is a function frame -> channels. Rotations are in DESIGN axes (x right, y up, z toward the viewer),
    applied in the bone's rest frame: `rx ry rz`, `bend`, `raise`, `swing`, `twist`, `curl` (fingers, + = close),
    offsets `tx ty tz` and `sy` (local-Y scale: eyelids blink). Keys are Catmull-Rom splines (`K`), wrapped for loops.
  * Human legs: two-bone IK to ankle targets (heel / ball / toe contact; kneels place the knee on the page). Arms: the
    same IK where a hand must be somewhere (belly, partner's back, a lion's mane), in root space or any bone's space.
  * Lion legs: two-bone IK to the wrist / hock so that the paw TIP lands exactly on its target with a given paw pitch
    (planted paws do not slide); the gait is a lateral-sequence four-beat walk (LH, LF, RH, RF).
  * Secondary motion is simulated: hair, sash, cape, belly, robe hem, tails, ears and mane are damped spring chains on
    top of the keyed pose (loops simulate 3 cycles and close exactly).
  * Blinks at irregular frames; talk is an irregular syllable rhythm with word gaps; every one-shot has anticipation,
    overshoot and settle.
Intermediates: $DA_ANIM_WORK (default /tmp/daniel_anim).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DA = os.path.join(ROOT, "assets/daniel")
MODEL = os.path.join(DA, "model")
ANIM = os.path.join(DA, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
SET_GLB = os.path.join(MODEL, "babylon.glb")
TIMELINE = os.path.join(DA, "timeline.json")
REGIONS_JSON = os.path.join(MODEL, "regions_characters.json")
FACE_DIR = os.path.join(ROOT, "docs/daniel/design/faces")
WORK = os.environ.get("DA_ANIM_WORK") or "/tmp/daniel_anim"
BLENDER = os.environ.get("BLENDER") or ("/Applications/Blender.app/Contents/MacOS/Blender"
                                        if os.path.exists("/Applications/Blender.app/Contents/MacOS/Blender") else "blender")
FPS = 30
CHARS = ("daniel", "king", "officer", "lion", "lion2")
LIONS = ("lion", "lion2")

# stage distances the two-actor clips are fitted to (CONTRACT §4 + task brief; story marks in docs/daniel/storyboard)
HUG_D = 0.11         # king_hug <-> daniel_hug (reach 0.10 in front; the story's KING_DEN..(0.13, 0.06) is 0.082)
PET_D = 0.12         # pet_lion: the hand reaches the lion's mane 0.12 in front of Daniel, at the lying lion's mane height
PET_Y = 0.070        # mane height of the lion lying / rolled over (root-space y of the hand target)
STAMP_AT = (-0.010, 0.240, 0.092)   # king_stamp: where the ring presses (king root space, chest height, in front)
SEAT = (0.0, 0.027, -0.078)         # king_toss_sigh: the dais' second step (h 0.027, z -0.365) seen from KING (0, -0.30)

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
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith(("DA_", "Traceback", "Error", "  File")) or "Error" in ln]
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
    d.text((pad, 14), "Daniel - key poses per clip (30 fps; frame / seconds; marker names in red; * = extra clip; "
                      "pair rows = two actors at their story distance)", fill=(40, 30, 20), font=font)
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
    sheet = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT) if os.environ.get("DA_QUANT", "1") == "1" else sheet
    sheet.save(out, optimize=True)
    print("DA_CONTACT", out, sheet.size)


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get("DA_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("DA_PROBE_OUT", "probe.png"))
    sheet.save(out); print("DA_PROBE_SHEET", out)


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
    if mode in ("fresh", "all"):
        fresh_check()


def fresh_check():
    """The Set + sheet role may re-run da_characters.py (new sheet UVs): the anim GLBs must be newer than the model."""
    src = [BLEND] + [os.path.join(MODEL, f"{c}.glb") for c in CHARS]
    newest = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    outs = [os.path.join(ANIM, f"{c}.glb") for c in CHARS]
    stale = [o for o in outs if (not os.path.exists(o)) or os.path.getmtime(o) < newest]
    print("DA_FRESH", "STALE " + ", ".join(os.path.basename(o) for o in stale) if stale else "OK (anim exports newer than the model files)")
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
    H_OF = {"daniel": 0.36, "king": 0.47, "officer": 0.37, "lion": 0.24, "lion2": 0.22}

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
        self.quad = ch in LIONS
        self.prop_axis = {}
        # skin proxy: ~1500 body vertices with their bone weights (linear-blend skinned in python from M) for
        # ground contact (`settle`) and quick reach checks
        body = bpy.data.objects[f"{ch}_body"]
        mw = obj.matrix_world.inverted() @ body.matrix_world
        gname = {g.index: g.name for g in body.vertex_groups}
        vs = body.data.vertices
        step = max(1, len(vs) // 1500)
        self.proxy = []
        for i in range(0, len(vs), step):
            v = vs[i]
            ws = [(gname[g.group], g.weight) for g in v.groups if g.weight > 1e-3 and gname.get(g.group) in self.rest]
            tot = sum(w for _, w in ws)
            if tot <= 0:
                continue
            ws = [(b, w / tot) for b, w in ws]
            dom = max(ws, key=lambda q: q[1])[0]
            self.proxy.append((mw @ v.co, ws, dom))
        self.rest_inv = {n: m.inverted() for n, m in self.rest.items()}

    def skin(self, M, bones=None):
        """Deformed proxy points (design coords) - only vertices whose dominant bone is in `bones` when given."""
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
    def __init__(self, ch, name, N, loop, fn, markers=None, notes="", extra=False, speed=None, props=None, backwards=False, info=None):
        self.info = info or {}
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = markers or {}
        self.notes = notes
        self.extra = extra
        self.speed = speed           # (stride L, duty) for in-place locomotion -> natural speed
        self.props = props or []     # props this clip is posed for (shown in renders; Integration shows them by `prop`)
        self.backwards = backwards

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
        for c in (LIONS if ch == "lions" else (ch,)):
            CLIPS.append(Clip(c, name, N, loop, fn, **kw))
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
        # roll about the contact point: the heel while the toes are up (pitch < 0), the ball while the heel is up,
        # so a planted foot does not skate as it rolls (continuous: no correction at pitch 0)
        z -= pivot_dz(rig, side, pitch)
        out["leg" + side] = (V(base.x + sx * spread, y, base.z + z + fwd), pitch, contact, p)
    return out


def pivot_dz(rig, side, pitch):
    heel, ball, _ = foot_points(rig, side)
    q = heel if pitch < 0 else ball
    R = rot_d((1, 0, 0), pitch)
    return (CI @ (R @ (C @ q))).z - q.z


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


KNEEL = {"daniel": dict(KY=float(os.environ.get("DA_KY", "0.023")), kz=0.016, thigh_back=float(os.environ.get("DA_TB", "14")),
                       shin_slope=float(os.environ.get("DA_SS", "30")))}


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



# =============================================================================================== HUMANS (shared)
# Rest: A-pose, arms 55 deg below horizontal, open relaxed hands, facing +Z (as Ruth). raise -22 = arms by the robe.
ARM_REST = {"daniel": -22.0, "king": -15.0, "officer": -23.0}


def h_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.5 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.1 * b * amp; c["shoulderR.raise"] = 1.1 * b * amp
    c["neck.rx"] = 0.8 * b * amp
    ar = ARM_REST[rig.ch]
    c["upperArmL.raise"] = ar; c["upperArmR.raise"] = ar
    c["upperArmL.bend"] = 8; c["upperArmR.bend"] = 8
    c["forearmL.bend"] = 26; c["forearmR.bend"] = 26
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 22); fingers(c, "R", 22)
    c["head.rx"] = -2
    if rig.ch == "king":
        c["belly.s"] = 1.0 + 0.025 * b * amp            # the belly breathes too
    return c


def hands_clasped(c, rig, at, wring=0.0, w=1.0, space="root"):
    """Both wrists loosely together at `at` (root space unless space given)."""
    arm_ik(c, "L", at + V(0.011 + 0.002 * wring, 0.000, -0.004), V(0.7, -0.6, -0.4), space, w)
    arm_ik(c, "R", at + V(-0.011 + 0.002 * wring, -0.004, 0.000), V(-0.7, -0.6, -0.4), space, w)


def arm_up_wave(c, side, f, N, cycles, high=1.0, w=1.0, amp=1.0):
    """Raised arm waving from the elbow (open hand, palm forward)."""
    sx = 1 if side == "L" else -1
    ph = wave(f, N, cycles)
    c[f"upperArm{side}.raise"] = lerp(c.get(f"upperArm{side}.raise", -22), 70 + 50 * high, w)
    c[f"upperArm{side}.bend"] = lerp(c.get(f"upperArm{side}.bend", 8), 20 + 6 * high, w)
    c[f"forearm{side}.bend"] = lerp(c.get(f"forearm{side}.bend", 26), 66 - 30 * high + 22 * amp * ph, w)
    c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", -10 * sx), -70 * sx, w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -10 + 14 * amp * wave(f, N, cycles, -0.12), w)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 6, w))


def look_keys(c, keys, f, N, loop=True, neck=0.4, head=0.6, lag=4):
    c["neck.ry"] = c.get("neck.ry", 0.0) + neck * K(keys, f, N, loop)
    c["head.ry"] = c.get("head.ry", 0.0) + head * KL(keys, f, N, loop, lag=lag)


def talk_jaw(c, f, N, seed, amp=(5, 13)):
    jk, beats = syllables(N, seed, amp=amp)
    c["jaw.rx"] = jaw_from(jk, f, N)
    return beats


def default_pole(limb):
    sx = 1 if limb.endswith("L") else -1
    return {"leg": V(0.15 * sx, 0, 1), "arm": V(0.6 * sx, -0.6, -0.5), "fro": V(0, 0.2, -1),
            "hin": V(0.12 * sx, 0, 1)}[limb[:3]]


def mix(a, b, w):
    """Channel dicts a -> b by w (floats / vectors lerp; strings switch at 0.5; one-sided keys fade from / to rest)."""
    out = {}
    for k in set(a) | set(b):
        va, vb = a.get(k), b.get(k)
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
            dflt = 1.0 if (k.endswith(".s") or k.endswith(".sy") or k.startswith("ikw.")) else 0.0
            out[k] = lerp(dflt if va is None else va, dflt if vb is None else vb, w)
    for side in "LR":                      # fade an IK arm in / out when only one side has it
        k = "ik.arm" + side
        if (k in a) != (k in b):
            wa = a.get("ikw.arm" + side, 1.0) if k in a else 0.0
            wb = b.get("ikw.arm" + side, 1.0) if k in b else 0.0
            out["ikw.arm" + side] = lerp(wa, wb, w)
    return out


# =============================================================================================== DANIEL
@clip("daniel", "idle", 150, True,
      notes="calm and steady: slow breathing with one deeper breath, small weight shift with the hips leading, hands "
            "loosely together in front, looks at his partner, glances away and back (neck leads), a small content nod; "
            "ponytail and sash settle after each move; blinks single / double / slow")
def daniel_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.9)
    deep = bump(f, 40, 84)
    c["chest.rx"] += -2.0 * deep; c["shoulderL.raise"] += 1.5 * deep; c["shoulderR.raise"] += 1.5 * deep
    sh = K([(0, -0.4), (20, -0.4), (46, 0.9), (88, 0.9), (110, -0.7), (136, -0.7), (150, -0.4)], f, N, True)
    shl = KL([(0, -0.4), (20, -0.4), (46, 0.9), (88, 0.9), (110, -0.7), (136, -0.7), (150, -0.4)], f, N, True, lag=7)
    c["hips.tx"] = 0.004 * sh; c["hips.ty"] = -0.0012 - 0.001 * abs(sh)
    c["hips.rz"] = -2.0 * sh; c["spine.rz"] = 1.3 * shl; c["chest.rz"] = 0.9 * shl; c["head.rz"] = -1.2 * shl
    look_keys(c, [(0, 0), (30, 0), (40, -12), (62, -12), (72, 6), (98, 6), (110, 0), (150, 0)], f, N)
    c["head.rx"] += 4 * bump(f, 116, 134) + K([(0, 0), (40, 2), (62, 1), (72, -2), (98, -1), (110, 0), (150, 0)], f, N, True)
    hands_clasped(c, rig, V(0.0, 0.160 + 0.002 * wave(f, N, 3), 0.042))
    fingers(c, "L", 30 + 5 * wave(f, N, 2, 0.6)); fingers(c, "R", 34 + 5 * wave(f, N, 3, 0.1))
    blink(c, f, N, [24, 66, 73, 131])
    stand_feet(rig, c, spread=0.003, pitchR=K([(0, 0), (46, 0), (60, 6), (88, 6), (100, 0), (150, 0)], f, N, True))
    return c


D_WALK = (0.078, 0.60)


@clip("daniel", "walk", 34, True, markers={"contactL": 0, "contactR": 17}, speed=D_WALK,
      notes="calm, even walk (~106 steps/min): soft hip bob, chest counter-turn, relaxed arm swing with lagging "
            "forearms, head steady; ponytail and the sash ends swing late")
def daniel_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=D_WALK[0], lift=0.012, duty=D_WALK[1], heel=12, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0042 + 0.0030 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -6 * math.sin(ph - 0.35); c["head.ry"] = 3 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.2 * math.cos(ph); c["chest.rz"] = -1.4 * math.cos(ph - 0.5); c["head.rz"] = 0.7 * math.cos(ph - 0.9)
    c["spine.rx"] = 2; c["head.rx"] = -2 + 1.2 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 8 - 16 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 16 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 26 - 9 * math.sin(ph - 1.0); c["forearmR.bend"] = 26 + 9 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 9 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 9 * math.sin(ph - 1.6)
    blink(c, f, N, [27])
    return c


@clip("daniel", "talk", 96, True,
      notes="warm, unhurried talking: jaw in an irregular syllable rhythm with word gaps (lip sync overrides it), nods "
            "on the stressed syllables; phrase 1 the right hand opens palm-up toward the listener, phrase 2 the left "
            "hand comes to his chest; small weight shift; two blinks")
def daniel_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    beats = talk_jaw(c, f, N, 41)
    bt = beat_curve(beats, f, N, width=9); btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -2 + 3.0 * bt - 1.0 * wave(f, N, 1, 0.2)
    c["head.ry"] = 4 * wave(f, N, 1, 0.1) + 2 * wave(f, N, 3, 0.4); c["head.rz"] = 2.5 * wave(f, N, 1, 0.35)
    pa = K([(0, 0.2), (10, 0.9), (38, 1.0), (52, 0.15), (88, 0.1), (96, 0.2)], f, N, True)
    pb = K([(0, 0.0), (44, 0.0), (56, 1.0), (84, 0.9), (94, 0.0), (96, 0.0)], f, N, True)
    lift = pa * (0.75 + 0.25 * btl)
    c["upperArmR.raise"] = -22 + 4 * lift; c["upperArmR.bend"] = 8 + 38 * lift
    c["forearmR.bend"] = 26 + 50 * lift; c["forearmR.twist"] = 10 - 80 * lift
    c["handR.bend"] = 6 - 20 * btl * pa; fingers(c, "R", 28 - 22 * btl * pa - 6 * lift)
    arm_ik(c, "L", V(0.012, -0.004 + 0.004 * btl, 0.040), V(0.8, -0.6, -0.2), "chest", pb)
    c["handL.bend"] = 6 - 14 * pb
    c["chest.ry"] = -4 * lift + 3 * pb; c["chest.rx"] += 1.5 * bt
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.4 * sh; c["spine.rz"] = 0.8 * sh
    blink(c, f, N, [9, 63])
    stand_feet(rig, c, spread=0.003)
    return c


@clip("daniel", "bow", 56, False, markers={"bow": 24},
      notes="a breath, the right hand comes to his chest, bows from the hips (chest and head follow late, ponytail "
            "swings forward), holds a beat, comes half way up and stays: a respectful half-bow with the hand on his "
            "heart")
def daniel_bow(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    ant = bump(f, 0, 9)
    hand = ease_io((f - 2) / 12)
    down = ease_io((f - 10) / 14) * (1 - 0.55 * ease_io((f - 34) / 16))
    downl = ease_io((f - 13) / 14) * (1 - 0.55 * ease_io((f - 37) / 16))
    c["chest.rx"] += -2.5 * ant + 9 * downl; c["spine.rx"] = 9 * down; c["hips.rx"] = 8 * down
    c["hips.tz"] = -0.006 * down
    c["neck.rx"] = 6 * downl; c["head.rx"] = -2 - 3 * ant + 12 * downl
    arm_ik(c, "R", V(-0.010, -0.006, 0.040), V(-0.8, -0.6, -0.2), "chest", hand)
    c["handR.bend"] = 6 - 12 * hand; fingers(c, "R", 22 - 8 * hand)
    c["upperArmL.bend"] = 8 + 6 * down; c["forearmL.bend"] = 26 + 6 * down
    blink(c, f, N, [22], loop=False, base=1.0 + 2.0 * downl)
    stand_feet(rig, c, spread=0.003)
    return c


def daniel_kneel_pose(rig, c, w=1.0):
    kneel_legs(rig, c, w, w)
    c["hips.rx"] = c.get("hips.rx", 0.0) - 2 * w


def pray_upper(rig, c, f, N, w=1.0, loop=True):
    """Kneeling prayer: hands raised a little in front, palms up, elbows soft; head bowed; slow breathing."""
    br = wave(f, N, 2) if loop else 0.0
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.036 * sx, 0.172 + 0.002 * br, 0.068), V(0.8 * sx, -0.7, -0.2), "root", w)
        c[f"hand{side}.twist"] = lerp(c.get(f"hand{side}.twist", 0.0), -78 * sx, w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -20, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 10, w))
    c["spine.rx"] = c.get("spine.rx", 0.0) + 5 * w; c["chest.rx"] = c.get("chest.rx", 0.0) + 2 * w - 1.2 * br * w
    c["neck.rx"] = c.get("neck.rx", 0.0) + 10 * w; c["head.rx"] = c.get("head.rx", 0.0) + 16 * w


@clip("daniel", "kneel_pray", 80, False, markers={"knees_down": 30},
      notes="faces the window (or the viewer in the den): a breath, kneels right knee then left (knees on the page), "
            "settles back, raises both hands a little in front of his chest, palms up, bows his head and closes his "
            "eyes; holds (eyes closed, still). pet_lion and stand_up start from the same kneel")
def daniel_kneel_pray(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.2)
    one = ease_io((f - 4) / 16); two = ease_io((f - 13) / 17)
    w = 0.5 * (one + two)
    kneel_legs(rig, c, two, one, hips_w=w)
    c["hips.rx"] = -2 * w
    c["hips.ty"] -= 0.006 * bump(f, 0, 12)
    c["spine.rx"] = 12 * bump(f, 6, 34)
    c["chest.rx"] += 4 * bump(f, 6, 34) - 2.5 * bump(f, 0, 8)
    hw = ease_io((f - 34) / 18)
    pray_upper(rig, c, 0, N, hw, loop=False)
    eyes = ease_io((f - 46) / 10)
    c["eyelids.sy"] = 1.0 + 11.78 * eyes
    if f < 46:
        blink(c, f, N, [8], loop=False)
    return c


@clip("daniel", "stand_up", 54, False, markers={"stand": 34},
      notes="from the kneel (kneel_pray / pet_lion): opens his eyes and looks up, sets the left foot forward, pushes "
            "up with a hand on the knee, rises, brings the feet together, settles calm; holds standing")
def daniel_stand_up(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    up = ease_io((f - 12) / 22)
    stepL = ease_io((f - 4) / 9)
    backL = ease_io((f - 32) / 9)
    look = ease_io(f / 10)
    kneel_legs(rig, c, 0.0, 1 - up, hips_w=1 - up)
    c["hips.rx"] = -2 * (1 - up)
    hip, knee, ankle = kneel_geom(rig, "L", **KNEEL["daniel"])
    bL = rig.head["footL"]
    lunge = V(bL.x + 0.004, planted_ankle_y(rig, "L", 0), 0.062)
    a0 = V(ankle.x, ankle.y, ankle.z)
    pk = tuck_pitch(rig, "L", ankle.y)
    if f < 32:
        t = stepL
        tgt = a0.lerp(lunge, t); tgt.y = max(tgt.y, planted_ankle_y(rig, "L", pk * (1 - t))) + 0.018 * math.sin(math.pi * t)
        c["ik.legL"] = tgt; c["footL.pitch"] = pk * (1 - t)
    else:
        t = backL
        tgt = lunge.lerp(V(bL.x, planted_ankle_y(rig, "L", 0), bL.z), t); tgt.y += 0.010 * math.sin(math.pi * t)
        c["ik.legL"] = tgt; c["footL.pitch"] = 0
    c["pole.legL"] = V(0.1, 0, 1)
    c["hips.tz"] += 0.016 * math.sin(math.pi * up)
    c["hips.ty"] += 0.004 * bump(f, 4, 26)
    lean = bump(f, 8, 38)
    c["spine.rx"] = 5 * (1 - up) + 14 * lean; c["chest.rx"] += 4 * lean
    c["neck.rx"] = 10 * (1 - look); c["head.rx"] = lerp(16, -3, look) - 5 * lean
    knee_pt = V(0.026, lerp(0.050, 0.10, up), 0.050 + 0.010 * up)
    hw = 1 - ease_io((f - 26) / 10)
    if f < 36:
        arm_ik(c, "L", vlerp(V(0.036, 0.172, 0.068), knee_pt, ease_io(f / 8)), V(0.8, -0.3, -0.5), "root", hw)
    rw = 1 - ease_io((f - 6) / 22)
    arm_ik(c, "R", V(-0.036, 0.172, 0.068), V(-0.8, -0.7, -0.2), "root", rw)
    c["handR.twist"] = 78 * rw; c["handR.bend"] = lerp(6, -20, rw)
    c["eyelids.sy"] = 1.0 + 11.78 * (1 - ease_io(f / 5))
    if f >= 41:
        stand_feet(rig, c, spread=0.003)
        c["ik.legL"] = vlerp(tgt, c["ik.legL"], ease_io((f - 41) / 3))
    if f >= 5:
        blink(c, f, N, [44], loop=False)
    return c


@clip("daniel", "calm_nod", 48, False, markers={"nod": 16},
      notes="sure and gentle (\"don't worry\"): a small breath, one slow deep nod with a slight head tilt, the right "
            "hand opens a little toward the listener, eyes close softly on the nod; settles back to the idle stance")
def daniel_calm_nod(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    nod = K([(0, 0), (6, -3), (16, 14), (24, 9), (34, 2), (48, 0)], f)
    c["head.rx"] += nod; c["neck.rx"] += 0.35 * KL([(0, 0), (6, -3), (16, 14), (24, 9), (34, 2), (48, 0)], f, lag=2)
    c["head.rz"] = 5 * bump(f, 8, 40)
    c["chest.rx"] += -2 * bump(f, 0, 10)
    op = bump(f, 10, 44)
    c["upperArmR.bend"] = 8 + 20 * op; c["forearmR.bend"] = 26 + 34 * op; c["forearmR.twist"] = 10 - 60 * op
    fingers(c, "R", 22 - 12 * op)
    hands_clasped(c, rig, V(0.0, 0.160, 0.042), w=1 - op)
    c["eyelids.sy"] = max(1.0, 1.0 + 9.0 * bump(f, 12, 26))
    stand_feet(rig, c, spread=0.003)
    return c


@clip("daniel", "pet_lion", 96, True,
      notes=f"kneeling (same kneel as kneel_pray), leaning forward; the right hand strokes the lion's mane {PET_D} in "
            f"front at the lying lion's mane height ({PET_Y}): two long strokes per loop (hand on, slide, lift, back), "
            "the left hand rests on his thigh, head tilted down toward the lion, smiling, slow blinks")
def daniel_pet_lion(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    daniel_kneel_pose(rig, c)
    c["spine.rx"] = 16; c["chest.rx"] += 10; c["hips.rx"] += 4
    c["neck.rx"] = 6; c["head.rx"] = 12; c["head.rz"] = 8 + 2 * wave(f, N, 1, 0.3)
    c["chest.ry"] = 6
    # stroke path (wrist, root space): on at the front of the mane, slide back over it, lift, return
    D, Y = PET_D, PET_Y
    pts = [(0, V(-0.022, Y + 0.040, D - 0.040)), (12, V(-0.020, Y + 0.020, D - 0.040)), (34, V(-0.014, Y + 0.022, D - 0.004)),
           (42, V(-0.016, Y + 0.040, D - 0.012)), (48, V(-0.022, Y + 0.040, D - 0.040))]
    pts = pts + [(48 + k, p + V(0.004, 0, 0)) for k, p in pts[1:]]
    tgt = V(*(K([(k, v[i]) for k, v in pts], f, N, True) for i in range(3)))
    on = sum(bump(f, a, a + 32) for a in (10, 58))
    arm_ik(c, "R", tgt, V(-0.8, -0.4, -0.3))
    c["handR.bend"] = -18 - 14 * on; c["handR.twist"] = 30
    fingers(c, "R", 8 + 10 * on)
    arm_ik(c, "L", V(0.040, 0.085, 0.060), V(0.8, -0.3, -0.4))
    c["handL.bend"] = -10; fingers(c, "L", 30)
    c["chest.rx"] += 2.0 * on; c["spine.rz"] = -2.5 * on
    blink(c, f, N, [20, 70], base=2.2, slow=1.8)
    return c


@clip("daniel", "wave_up", 48, True,
      notes="happy, looking up at someone above (the king at the den's opening): chin up, the right arm high waving "
            "from the elbow, the left hand up at shoulder height too, little bounces on his toes")
def daniel_wave_up(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    arm_up_wave(c, "R", f, N, 2, high=1.0)
    c["upperArmL.raise"] = 8; c["upperArmL.bend"] = 14; c["forearmL.bend"] = 40; c["forearmL.twist"] = -40
    c["handL.bend"] = -6 + 6 * wave(f, N, 2, 0.3); fingers(c, "L", 12)
    c["neck.rx"] = -10; c["head.rx"] = -18 + 2 * wave(f, N, 2, 0.2); c["head.rz"] = -4 + 3 * wave(f, N, 1)
    c["chest.rx"] += -5; c["spine.rx"] = -2
    hop = max(0.0, wave(f, N, 2, 0.05))
    c["hips.ty"] = 0.004 * hop - 0.001
    stand_feet(rig, c, spread=0.003, pitchL=10 * hop, pitchR=10 * hop)
    blink(c, f, N, [30])
    return c


def hug_sway(f, N):
    return wave(f, N, 1, 0.0)


@clip("daniel", "hug", 90, True,
      notes=f"hugs the king standing {HUG_D} in front: steps in, both arms round the king's waist (under the cape), "
            "cheek against the king's chest, head turned to his right, eyes closed; rocking side to side in phase "
            "with king_hug (start them on the same frame); one squeeze")
def daniel_hug(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    s = hug_sway(f, N)
    sq = bump(f, 40, 62)
    c["hips.tz"] = 0.012; c["spine.rx"] = 5; c["chest.rx"] += 4 + 2 * sq
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -2.0 * s; c["spine.rz"] = 1.4 * s; c["chest.rz"] = 1.0 * s
    c["spine.rz"] += -3; c["chest.rz"] += -3
    c["neck.rx"] = 4; c["head.rx"] = 4; c["neck.ry"] = 8; c["head.ry"] = 22; c["neck.rz"] = -8; c["head.rz"] = -14 + 2 * s
    D = HUG_D
    arm_ik(c, "R", V(-0.030 + 0.002 * s, 0.200 - 0.004 * sq, D + 0.024), V(-1.0, -0.2, 0.1))
    arm_ik(c, "L", V(0.030 + 0.002 * s, 0.206 - 0.004 * sq, D + 0.026), V(1.0, -0.2, 0.1))
    c["handR.twist"] = 60; c["handL.twist"] = -60; c["handR.bend"] = 20; c["handL.bend"] = 20
    fingers(c, "R", 20 + 14 * sq); fingers(c, "L", 20 + 14 * sq)
    c["eyelids.sy"] = 12.78
    stand_feet(rig, c, spread=0.003, fwdL=0.012, fwdR=-0.004)
    return c


@clip("daniel", "wave", 48, True,
      notes="friendly goodbye to the viewer: the right hand up beside the head waving from the elbow, the left hand "
            "relaxed, a smile with a small head tilt and a weight shift")
def daniel_wave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.7)
    arm_up_wave(c, "R", f, N, 2, high=0.75, amp=0.9)
    c["head.rz"] = 5 + 2 * wave(f, N, 1, 0.2); c["head.rx"] = -3
    sh = wave(f, N, 1, 0.1)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.5 * sh; c["chest.rz"] = 1.0 * sh
    stand_feet(rig, c, spread=0.003)
    blink(c, f, N, [20])
    return c


# =============================================================================================== KING
def belly_hands(c, rig, w=1.0, pat=0.0, lift=0.0):
    """Both hands resting on the round belly (wrists at its sides, palms on the front)."""
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.058 * sx, 0.204 + lift + 0.006 * pat, 0.026), V(0.9 * sx, -0.4, -0.6), "root", w)
        c[f"hand{side}.twist"] = lerp(c.get(f"hand{side}.twist", 0.0), -10 * sx, w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 34 - 14 * pat, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 18, w))


@clip("king", "idle", 150, True,
      notes="content and regal: both hands on his round belly (two little pats with a belly jiggle), slow breathing "
            "that lifts the belly, weight shifts L -> R, looks round his court and back, a pleased chin-up, blinks")
def king_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=1.0)
    pat = pulses(f, N, [(70, 1.0), (80, 0.8)], decay=2.5)
    belly_hands(c, rig, pat=pat)
    c["belly.ty"] = -0.002 * pat
    sh = K([(0, -0.5), (24, -0.5), (52, 1.0), (92, 1.0), (116, -0.7), (138, -0.7), (150, -0.5)], f, N, True)
    shl = KL([(0, -0.5), (24, -0.5), (52, 1.0), (92, 1.0), (116, -0.7), (138, -0.7), (150, -0.5)], f, N, True, lag=8)
    c["hips.tx"] = 0.005 * sh; c["hips.rz"] = -2.2 * sh; c["spine.rz"] = 1.4 * shl; c["chest.rz"] = 1.0 * shl
    c["head.rz"] = -1.0 * shl
    look_keys(c, [(0, 0), (30, 0), (42, 14), (66, 14), (80, -10), (104, -10), (118, 0), (150, 0)], f, N)
    c["head.rx"] = -2 - 5 * bump(f, 118, 146)
    blink(c, f, N, [17, 58, 64, 125])
    stand_feet(rig, c, spread=0.004)
    return c


K_WALK_SAD = (0.050, 0.66)


@clip("king", "walk_sad", 48, True, markers={"contactL": 0, "contactR": 24}, speed=K_WALK_SAD,
      notes="slow, heavy, sad walk: head low, shoulders slumped, arms hanging, short dragging steps with a heavy "
            "drop on each, cape swaying late, a sigh in the chest")
def king_walk_sad(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=1.2)
    g = gait(rig, f, N, L=K_WALK_SAD[0], lift=0.007, duty=K_WALK_SAD[1], heel=8, toeoff=16)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.003 + 0.0022 * math.cos(2 * ph - 0.3)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -3 * math.sin(ph - 0.4)
    c["hips.rz"] = 3.0 * math.cos(ph); c["chest.rz"] = -1.5 * math.cos(ph - 0.6); c["head.rz"] = 1.5 * math.cos(ph - 1.0)
    c["spine.rx"] = 4; c["chest.rx"] += 6; c["neck.rx"] = 10; c["head.rx"] = 14 + 1.5 * math.cos(2 * ph - 1.2)
    c["shoulderL.raise"] = -4; c["shoulderR.raise"] = -4; c["shoulderL.swing"] = 4; c["shoulderR.swing"] = 4
    c["upperArmL.raise"] = -12; c["upperArmR.raise"] = -12
    c["upperArmL.bend"] = 4 - 7 * math.sin(ph - 0.3); c["upperArmR.bend"] = 4 + 7 * math.sin(ph - 0.3)
    c["forearmL.bend"] = 12; c["forearmR.bend"] = 12
    fingers(c, "L", 30); fingers(c, "R", 30)
    blink(c, f, N, [14], base=2.0, slow=1.6)
    return c


@clip("king", "talk", 96, True,
      notes="the king speaks: jaw in a syllable rhythm with word gaps, the left hand stays on his belly, the right "
            "hand makes broad regal gestures on the stressed words, chin up, weight shift")
def king_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.9)
    beats = talk_jaw(c, f, N, 52, amp=(6, 15))
    bt = beat_curve(beats, f, N, width=10); btl = beat_curve(beats, f - 3, N, width=11)
    arm_ik(c, "L", V(0.050, 0.196, 0.040), V(0.9, -0.4, -0.5))
    c["handL.twist"] = 30; c["handL.bend"] = 26; fingers(c, "L", 10)
    sweep = K([(0, 0.3), (20, 1.0), (44, 0.6), (64, 1.0), (84, 0.4), (96, 0.3)], f, N, True)
    c["upperArmR.raise"] = -15 + 18 * sweep; c["upperArmR.bend"] = 8 + 30 * btl + 10 * sweep
    c["forearmR.bend"] = 40 + 30 * btl; c["forearmR.twist"] = 10 - 70 * sweep
    c["handR.bend"] = -10 * btl; fingers(c, "R", 14)
    c["head.rx"] = -4 + 3 * bt; c["head.ry"] = -5 * sweep + 3 * wave(f, N, 1, 0.3); c["head.rz"] = 2 * wave(f, N, 1, 0.6)
    c["chest.ry"] = -4 * sweep; c["chest.rx"] += -2 + 1.5 * bt
    sh = wave(f, N, 1, 0.2)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -1.8 * sh
    c["belly.ty"] = 0.0012 * bt
    blink(c, f, N, [12, 70])
    stand_feet(rig, c, spread=0.004)
    return c


@clip("king", "talk_happy", 96, True,
      notes="delighted: arms open wide with palms up, chuckling between words (shoulder and belly bounces in uneven "
            "pulses), head tipping back on the laughs, jaw talking; the belly jiggles late")
def king_talk_happy(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    beats = talk_jaw(c, f, N, 61, amp=(7, 16))
    bt = beat_curve(beats, f, N, width=10)
    laugh = pulses(f, N, [(30, 1.0), (36, 0.8), (41, 0.6), (74, 1.0), (80, 0.7)], decay=2.6)
    open_ = 0.85 + 0.15 * wave(f, N, 2, 0.1)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = 10 + 14 * open_ + 4 * laugh
        c[f"upperArm{side}.bend"] = 26 + 6 * bt
        c[f"forearm{side}.bend"] = 44 + 6 * laugh
        c[f"forearm{side}.twist"] = -70 * sx
        c[f"hand{side}.bend"] = -14; fingers(c, side, 10)
    c["shoulderL.raise"] += 4 * laugh; c["shoulderR.raise"] += 4 * laugh
    c["chest.rx"] += -4 - 3 * laugh; c["spine.rx"] = -2
    c["head.rx"] = -8 - 6 * laugh + 2 * bt; c["head.rz"] = 3 * wave(f, N, 1, 0.3); c["head.ry"] = 3 * wave(f, N, 1, 0.1)
    c["jaw.rx"] = max(c["jaw.rx"], 10 * laugh)
    c["belly.ty"] = 0.004 * laugh; c["belly.s"] = 1.0 + 0.05 * laugh
    c["hips.ty"] = -0.002 * laugh
    blink(c, f, N, [14, 58])
    stand_feet(rig, c, spread=0.004)
    return c


@clip("king", "proud", 120, True,
      notes="pleased with himself: chin up, chest out, hands on his hips (elbows out), sways slowly side to side "
            "rocking heel to toe, eyes half closed")
def king_proud(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    sw = wave(f, N, 1, 0.0); swl = wave(f, N, 1, -0.06)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.072 * sx, 0.196, 0.006), V(1.0 * sx, 0.1, -0.7))
        c[f"hand{side}.twist"] = 70 * sx; c[f"hand{side}.bend"] = 30; fingers(c, side, 40)
    c["chest.rx"] += -6; c["spine.rx"] = -3; c["neck.rx"] = -4; c["head.rx"] = -10 + 1.5 * wave(f, N, 2, 0.2)
    c["hips.tx"] = 0.005 * sw; c["hips.rz"] = -2.4 * sw; c["spine.rz"] = 1.6 * swl; c["chest.rz"] = 1.2 * swl
    c["head.rz"] = -2 * swl + 2
    rock = wave(f, N, 2, 0.25)
    stand_feet(rig, c, spread=0.006, pitchL=5 * max(0, rock), pitchR=5 * max(0, rock))
    c["hips.ty"] = 0.002 * max(0, rock)
    c["belly.s"] = 1.04
    blink(c, f, N, [40, 100], base=4.0)
    return c


@clip("king", "stamp", 60, False, markers={"stamp": 30},
      notes="seals the law: the right fist (signet ring) rises with a little flourish, then presses firmly down onto "
            "something at his chest height in front of him (marker `stamp` = contact), holds a beat, lifts and settles "
            "with a satisfied nod; ends with both hands on his belly (idle)")
def king_stamp(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    belly_hands(c, rig, w=1.0)
    up = ease_io((f - 2) / 14)
    down = ease_io((f - 20) / 10)
    back = ease_io((f - 38) / 16)
    at = V(*STAMP_AT)
    high = at + V(0.006, 0.050, -0.014)
    tgt = vlerp(vlerp(V(-0.050, 0.196, 0.040), high, up), at + V(0, 0.012, -0.014), down)
    tgt = vlerp(tgt, V(-0.050, 0.196, 0.040), back)
    w_ik = 1.0
    arm_ik(c, "R", tgt, V(-0.9, -0.3, -0.5), "root", w_ik)
    press = bump(f, 27, 38)
    c["handR.bend"] = lerp(lerp(26, -20, up), 40, down * (1 - back)); c["handR.twist"] = lerp(-30, 30, back)
    fingers(c, "R", lerp(10, 85, ease_io((f - 6) / 10)) * (1 - back) + 10 * back)
    c["spine.rx"] = 6 * down * (1 - back) + 3 * press; c["chest.rx"] += -3 * up * (1 - down) + 6 * down * (1 - back)
    c["hips.ty"] = -0.004 * press
    c["head.rx"] = -6 * up * (1 - down) + 10 * down * (1 - back) + 6 * bump(f, 44, 56)
    c["chest.ry"] = -6 * down * (1 - back)
    c["belly.ty"] = -0.003 * press
    blink(c, f, N, [33], loop=False)
    stand_feet(rig, c, spread=0.004)
    return c


@clip("king", "worried", 90, True,
      notes="fretting: both hands pressed to his cheeks, rocking side to side, small fast head shakes, quick nervous "
            "blinks, belly wobbles")
def king_worried(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=1.0)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.030 * sx, -0.010, 0.026), V(0.9 * sx, -0.6, -0.3), "head")
        c[f"hand{side}.bend"] = 10; c[f"hand{side}.twist"] = 60 * sx; fingers(c, side, 16)
    r = wave(f, N, 2); rl = wave(f, N, 2, -0.06)
    c["hips.tx"] = 0.005 * r; c["hips.rz"] = -3 * r; c["spine.rz"] = 2.0 * rl; c["chest.rz"] = 1.5 * rl
    c["head.ry"] = 6 * wave(f, N, 6, 0.1) * (0.5 + 0.5 * abs(r)); c["head.rz"] = -3 * rl
    c["head.rx"] = 4; c["chest.rx"] += 3
    c["belly.ty"] = 0.0015 * wave(f, N, 4)
    blink(c, f, N, [10, 26, 31, 58, 76], slow=0.8)
    stand_feet(rig, c, spread=0.004)
    return c


K_PACE_N = 128


@clip("king", "pace", K_PACE_N, True, markers={"turn1": 32, "turn2": 96},
      notes="IN PLACE (the director does not move him): hands clasped behind his back, he walks three slow steps to "
            "his left, turns round, three back and turns again - a real small path of about 0.07 about the root, the "
            "planted feet stay still; head down in thought, a sigh at each turn. Cape lifted a little off the hands")
def king_pace(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    # path: x(t) along +-x, heading (yaw) +90 (walking to his left = +x) / -90
    T = N
    xk = [(0, -0.035), (8, -0.035), (40, 0.035), (64, 0.035), (72, 0.035), (104, -0.035), (128, -0.035)]
    hk = [(0, -90), (8, 90), (40, 90), (64, 270), (72, 270), (104, 270), (128, 450)]
    # piecewise: 0-8 turn (end of the previous leg), 8-40 walk +x, 40-64 hold+turn, 64-72, 72-104 walk -x, 104-128 turn
    def seg(ff):
        ff = ff % T
        if ff < 8:
            return -0.035, lerp(-90, 90, smooth((ff + 24) / 32)), 0
        if ff < 40:
            return lerp(-0.035, 0.035, (ff - 8) / 32), 90, 1
        if ff < 72:
            return 0.035, lerp(90, 270, smooth((ff - 40) / 32)), 0
        if ff < 104:
            return lerp(0.035, -0.035, (ff - 72) / 32), 270, 1
        return -0.035, lerp(-90, 90, smooth((ff - 104) / 32)), 0
    x, hd, walking = seg(f)
    R = Matrix.Rotation(math.radians(hd), 3, (0, 1, 0))       # design yaw about +y
    # feet: during the walk legs, an in-place gait in the body frame (stride 0.07/3 steps); during the turns, small
    # stepping turns (stride ~0) so the feet pivot under him
    g = gait(rig, f % 32, 32, L=0.035 if walking else 0.006, lift=0.008, duty=0.6, heel=8, toeoff=14)
    for side in "LR":
        t, pitch, _, _ = g["leg" + side]
        loc = R @ Vector(t)
        c["ik.leg" + side] = V(x, 0, 0) + loc
        c[f"foot{side}.pitch"] = pitch
        c[f"foot{side}.ry"] = hd
    c["hips.tx"] = x; c["hips.ry"] = hd
    ph = 2 * math.pi * f / 32
    c["hips.ty"] = -0.004 + 0.0025 * math.cos(2 * ph - 0.3)
    c["hips.rz"] = 2.0 * math.cos(ph)
    c["chest.rx"] += 5; c["neck.rx"] = 8; c["head.rx"] = 10 - 6 * (bump(f, 44, 64) + bump(f, 108, 128))
    sigh = bump(f, 44, 66) + bump(f, 108, 128)
    c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh; c["chest.rx"] += -2 * sigh
    # hands clasped behind the back (chest space), elbows out-back
    arm_ik(c, "L", V(0.012, -0.070, -0.050), V(0.7, -0.2, -1.0), "chest")
    arm_ik(c, "R", V(-0.012, -0.074, -0.052), V(-0.7, -0.2, -1.0), "chest")
    c["handL.bend"] = 10; c["handR.bend"] = 10; fingers(c, "L", 50); fingers(c, "R", 50)
    c["cape1.bend"] = -14
    blink(c, f, N, [20, 85], base=1.6)
    return c


@clip("king", "head_in_hands", 60, False, markers={"sob": 34},
      notes="despair: a breath, his hands come up to his face and the head sinks into them, shoulders slump forward, "
            "one big sobbing sigh, holds slumped (still)")
def king_head_in_hands(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.2)
    up = ease_io((f - 4) / 16)
    sink = ease_io((f - 12) / 16)
    sob = pulses(f, N, [(34, 1.0), (40, 0.6)], decay=3.0, loop=False)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.018 * sx, -0.012, 0.036), V(0.8 * sx, -0.7, -0.1), "head", up)
        c[f"hand{side}.bend"] = 20 * up; c[f"hand{side}.twist"] = 70 * sx * up; fingers(c, side, 22 - 10 * up)
    c["spine.rx"] = 6 * sink; c["chest.rx"] += 8 * sink - 2 * sob; c["neck.rx"] = 12 * sink; c["head.rx"] = 14 * sink
    c["shoulderL.raise"] += 3 * sob - 3 * sink; c["shoulderR.raise"] += 3 * sob - 3 * sink
    c["shoulderL.swing"] = 5 * sink; c["shoulderR.swing"] = 5 * sink
    c["hips.ty"] = -0.004 * sink
    c["belly.ty"] = -0.002 * sob
    c["eyelids.sy"] = 1 + 11.78 * sink
    stand_feet(rig, c, spread=0.004)
    return c


@clip("king", "reach_out", 48, False, markers={"reach": 22},
      notes="pleading toward Daniel: a little step forward on the left foot, leans in, both hands reach out in front "
            "at chest height, palms up and open; holds reaching")
def king_reach_out(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    st = ease_io((f - 4) / 14)
    r = ease_io((f - 8) / 14) + 0.05 * bump(f, 18, 30)
    for side, sx in (("L", 1), ("R", -1)):
        a = V(0.050 * sx, 0.200, 0.045); b = V(0.034 * sx, 0.238, 0.130)
        arm_ik(c, side, vlerp(a, b, r), V(0.8 * sx, -0.7, -0.2), "root", min(1.0, 0.3 + r))
        c[f"hand{side}.twist"] = -60 * sx * r; c[f"hand{side}.bend"] = -14 * r; fingers(c, side, 22 - 12 * r)
    c["hips.tz"] = 0.014 * st; c["spine.rx"] = 6 * r; c["chest.rx"] += 4 * r
    c["head.rx"] = -2 + 4 * r; c["head.rz"] = 6 * r
    stand_feet(rig, c, spread=0.004, fwdL=0.030 * st)
    c["ik.legL"].y += 0.010 * math.sin(math.pi * st)
    blink(c, f, N, [3, 36], loop=False)
    return c


def king_seated(rig, c, w=1.0):
    """Sitting on the dais step behind him (SEAT): feet stay on the page in front, hips back and down."""
    sy, sz = SEAT[1], SEAT[2]
    hip_y = sy + 0.040                         # hip joint above the seat surface
    dy = hip_y - rig.head["hips"].y
    c["hips.ty"] = c.get("hips.ty", 0.0) + dy * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + (sz + 0.012) * w
    c["hips.rx"] = c.get("hips.rx", 0.0) - 6 * w
    c["spine.rx"] = c.get("spine.rx", 0.0) + 10 * w
    for side in "LR":
        c["pole.leg" + side] = V(0.25 if side == "L" else -0.25, 0.3, 1)


@clip("king", "toss_sigh", 180, True, markers={"up": 74, "sit": 132},
      notes=f"sleepless: sits on the dais step behind him (seat {SEAT[1]} high, {abs(SEAT[2])} behind the root), "
            "elbows on knees, chin in hands, a long sigh (shoulders lift and drop), flops back, gets up restless, "
            "turns his head about, sits down again with a bump (belly jiggle). Loops on the seated pose")
def king_toss_sigh(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.2)
    stand = ease_io((f - 66) / 18) * (1 - ease_io((f - 120) / 16))
    sit = 1 - stand
    king_seated(rig, c, sit)
    stand_feet(rig, c, spread=0.010 * sit + 0.004, fwd=0.030 * sit)
    # seated: elbows on knees, chin in hands (chin hold 0-40), then the sigh + flop back (40-62)
    chin = K([(0, 1), (34, 1), (44, 0), (150, 0), (164, 1), (180, 1)], f, N, True) * sit
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.014 * sx, -0.034, 0.034), V(0.6 * sx, -1.0, 0.2), "head", chin)
        c[f"hand{side}.twist"] = 40 * sx * chin; c[f"hand{side}.bend"] = 20 * chin
    c["spine.rx"] += 14 * chin; c["chest.rx"] += 8 * chin; c["neck.rx"] = 4 * chin
    sigh = bump(f, 38, 64) * sit
    c["shoulderL.raise"] += 6 * sigh; c["shoulderR.raise"] += 6 * sigh
    c["chest.rx"] += -6 * sigh; c["head.rx"] = -10 * sigh + 6 * chin
    flop = bump(f, 52, 70) * sit
    c["spine.rx"] += -8 * flop; c["head.rx"] += -6 * flop
    c["upperArmL.raise"] += 10 * flop; c["upperArmR.raise"] += 10 * flop
    # standing: restless look about, hands wringing
    look_keys(c, [(0, 0), (80, 0), (90, 20), (100, 20), (108, -18), (118, -18), (126, 0), (180, 0)], f, N, neck=0.5, head=0.5)
    hands_clasped(c, rig, V(0.0, 0.205, 0.060), wring=wave(f, N, 8), w=stand)
    c["cape1.bend"] = -55 * sit; c["cape2.bend"] = -30 * sit
    bumpsit = pulses(f, N, [(134, 1.0)], decay=3.0)
    c["belly.ty"] = -0.004 * bumpsit; c["hips.ty"] -= 0.003 * bumpsit
    blink(c, f, N, [20, 90, 140], base=3.5 * sit + 1.0, slow=1.6)
    return c


K_RUN = (0.060, 0.45)


@clip("king", "run", 22, True, markers={"contactL": 0, "contactR": 11}, speed=K_RUN,
      notes="hurried royal waddle-run: short quick steps with a side-to-side waddle, leaning forward, arms pumping "
            "with flapping hands, belly bouncing on every step, the cape flying out behind")
def king_run(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=K_RUN[0], lift=0.022, duty=K_RUN[1], heel=6, toeoff=16)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = 0.002 + 0.007 * math.cos(2 * ph - 0.8)
    c["hips.rz"] = 7 * math.cos(ph); c["chest.rz"] = -4 * math.cos(ph - 0.5); c["head.rz"] = -2 * math.cos(ph - 0.9)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -7 * math.sin(ph - 0.3)
    c["spine.rx"] = 8; c["chest.rx"] += 6; c["neck.rx"] = -4; c["head.rx"] = -8
    c["upperArmL.raise"] = 6; c["upperArmR.raise"] = 6
    c["upperArmL.bend"] = 20 - 34 * math.sin(ph - 0.3); c["upperArmR.bend"] = 20 + 34 * math.sin(ph - 0.3)
    c["forearmL.bend"] = 70; c["forearmR.bend"] = 70
    c["handL.bend"] = 20 * math.sin(ph - 1.4); c["handR.bend"] = -20 * math.sin(ph - 1.4)
    fingers(c, "L", 10); fingers(c, "R", 10)
    c["belly.ty"] = 0.003 * math.cos(2 * ph - 1.6); c["belly.s"] = 1.0 + 0.03 * math.cos(2 * ph - 1.8)
    c["cape1.bend"] = -30; c["cape2.bend"] = -14
    blink(c, f, N, [5])
    return c


@clip("king", "call_out", 72, True, markers={"call1": 14, "call2": 48},
      notes="calling into the den: hands cupped round his mouth, leaning toward the den on tiptoe, two calls per loop "
            "(jaw wide, body pumps forward on each call), listening tilt between them")
def king_call_out(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    call = pulses(f, N, [(12, 1.0), (46, 1.0)], decay=6.0)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.026 * sx, -0.030, 0.034), V(0.9 * sx, -0.5, -0.1), "head")
        c[f"hand{side}.twist"] = 80 * sx; c[f"hand{side}.bend"] = 10; fingers(c, side, 40)
    c["jaw.rx"] = 4 + 18 * min(1.0, call)
    c["spine.rx"] = 10 + 6 * call; c["chest.rx"] += 6 + 4 * call; c["hips.tz"] = 0.006 + 0.004 * call
    listen = bump(f, 26, 42) + bump(f, 60, 72) + bump(f, 0, 6)
    c["head.rz"] = 10 * listen; c["head.rx"] = -10 + 4 * listen
    tip = 0.6 + 0.4 * min(1.0, call)
    stand_feet(rig, c, spread=0.005, pitchL=14 * tip, pitchR=14 * tip)
    c["hips.ty"] = 0.004 * tip
    c["belly.ty"] = 0.002 * call
    c["eyelids.sy"] = 1.0
    blink(c, f, N, [30, 64])
    return c


@clip("king", "joy_jump", 54, False, markers={"takeoff": 16, "land": 30},
      notes="pure joy: crouches, hops straight up with both arms flung high, belly bouncing, lands with a squash and "
            "a belly jiggle, settles with arms open")
def king_joy_jump(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.2)
    crouch = bump(f, 2, 18) + 0.8 * bump(f, 28, 42)
    air = bump(f, 15, 31)
    arms = ease_io((f - 8) / 10) * (1 - 0.5 * ease_io((f - 36) / 14))
    c["hips.ty"] = -0.011 * crouch + 0.048 * air
    c["spine.rx"] = 8 * crouch - 4 * air; c["chest.rx"] += 4 * crouch - 8 * air
    for side in "LR":
        c[f"upperArm{side}.raise"] = -15 + 105 * arms
        c[f"upperArm{side}.bend"] = 8 + 10 * arms; c[f"forearm{side}.bend"] = 26 - 6 * arms
        c[f"hand{side}.bend"] = -10 * arms; fingers(c, side, 22 - 16 * arms)
    stand_feet(rig, c, spread=0.004 + 0.004 * air, pitchL=-18 * air, pitchR=-18 * air)
    for side in "LR":
        c["ik.leg" + side] = c["ik.leg" + side] + V(0, 0.040 * air, 0)
    land = pulses(f, N, [(30, 1.0)], decay=3.0, loop=False)
    c["belly.ty"] = 0.006 * air - 0.006 * land; c["belly.s"] = 1.0 + 0.06 * land
    c["head.rx"] = -10 * arms + 6 * land
    c["jaw.rx"] = 12 * arms
    blink(c, f, N, [44], loop=False)
    return c


@clip("king", "hug", 90, True,
      notes=f"hugs Daniel standing {HUG_D} in front (shorter than him): leans over him, both arms wrapped round "
            "Daniel's back at the shoulder blades, cheek on top of Daniel's head, eyes closed and smiling; rocking in "
            "phase with daniel_hug (start them on the same frame), one big squeeze with a belly jiggle")
def king_hug(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.2)
    s = hug_sway(f, N)
    sq = bump(f, 40, 62)
    D = HUG_D
    c["hips.tz"] = 0.004; c["spine.rx"] = 6; c["chest.rx"] += 6 + 2 * sq
    c["hips.tx"] = -0.003 * s; c["hips.rz"] = 2.0 * s; c["spine.rz"] = -1.4 * s; c["chest.rz"] = -1.0 * s
    c["chest.rz"] += -3
    c["neck.rx"] = 8; c["head.rx"] = 10; c["neck.rz"] = -6; c["head.rz"] = -14 - 2 * s; c["head.ry"] = 14
    arm_ik(c, "L", V(0.022 + 0.002 * s, 0.240 - 0.004 * sq, D + 0.030), V(1.0, 0.1, 0.1))
    arm_ik(c, "R", V(-0.018 + 0.002 * s, 0.228 - 0.004 * sq, D + 0.032), V(-1.0, 0.1, 0.1))
    c["handR.twist"] = 50; c["handL.twist"] = -50; c["handR.bend"] = 20; c["handL.bend"] = 20
    fingers(c, "R", 22 + 12 * sq); fingers(c, "L", 22 + 12 * sq)
    c["belly.ty"] = -0.002 * sq; c["belly.s"] = 1.0 - 0.03 * sq
    c["eyelids.sy"] = 12.78
    stand_feet(rig, c, spread=0.005, fwdR=0.010, fwdL=-0.004)
    return c


@clip("king", "proclaim", 96, True,
      notes="the decree, booming: left arm raised high (open hand), the right hand on Daniel's near shoulder (Daniel "
            "standing to his right, about 0.14 away and a little in front, as in S12), chin up, chest out, jaw in a "
            "big slow syllable rhythm, emphatic downward beats of the raised hand")
def king_proclaim(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    beats = talk_jaw(c, f, N, 77, amp=(8, 18))
    bt = beat_curve(beats, f, N, width=12); btl = beat_curve(beats, f - 3, N, width=12)
    c["upperArmL.raise"] = 92 - 8 * btl; c["upperArmL.bend"] = 26; c["forearmL.bend"] = 16 + 10 * btl
    c["forearmL.twist"] = 60; c["handL.bend"] = -16 + 18 * btl; fingers(c, "L", 6)
    arm_ik(c, "R", V(-0.088, 0.256 + 0.002 * wave(f, N, 2), 0.036), V(-0.9, -0.6, -0.2))
    c["handR.bend"] = 26; c["handR.twist"] = -10; fingers(c, "R", 26)
    c["chest.rx"] += -6 + 2 * bt; c["spine.rx"] = -2; c["head.rx"] = -10 + 4 * bt; c["chest.ry"] = 4
    c["head.ry"] = 6 * wave(f, N, 1, 0.2)
    c["belly.ty"] = 0.0015 * bt
    blink(c, f, N, [20, 66])
    stand_feet(rig, c, spread=0.006)
    return c


# =============================================================================================== OFFICER
@clip("officer", "idle", 150, True,
      notes="shifty: shoulders up, fingertips together in front, eyes and head dart left - right - left with quick "
            "turns and frozen holds, little fidgeting finger taps, weight shifting, a sniff; blinks")
def officer_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.8)
    c["shoulderL.raise"] += 3; c["shoulderR.raise"] += 3; c["chest.rx"] += 3; c["neck.rx"] = 4
    hands_clasped(c, rig, V(0.0, 0.190 + 0.003 * wave(f, N, 5), 0.050))
    tap = 0.5 + 0.5 * wave(f, N, 10)
    fingers(c, "L", 10 + 20 * tap); fingers(c, "R", 10 + 20 * (1 - tap))
    dart = [(0, 0), (18, 0), (21, -24), (40, -24), (43, 20), (60, 20), (63, 0), (90, 0), (93, 26), (104, 26),
            (107, -16), (126, -16), (129, 0), (150, 0)]
    c["head.ry"] = K(dart, f, N, True); c["neck.ry"] = 0.3 * KL(dart, f, N, True, lag=2)
    c["head.rx"] = -3 + 4 * bump(f, 64, 76)
    sh = K([(0, -0.6), (40, -0.6), (52, 0.8), (110, 0.8), (124, -0.6), (150, -0.6)], f, N, True)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2.4 * sh; c["spine.rz"] = 1.6 * sh
    blink(c, f, N, [10, 46, 92, 98, 132])
    stand_feet(rig, c, spread=0.002)
    return c


O_WALK = (0.072, 0.60)


@clip("officer", "walk", 32, True, markers={"contactL": 0, "contactR": 16}, speed=O_WALK,
      notes="prim, busy walk: quick steps, nose up, shoulders stiff, elbows in with the forearms swinging, the robe "
            "hem swinging late")
def officer_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=O_WALK[0], lift=0.012, duty=O_WALK[1], heel=12, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.004 + 0.003 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.35)
    c["hips.rz"] = 3.0 * math.cos(ph); c["chest.rz"] = -1.5 * math.cos(ph - 0.5)
    c["head.rx"] = -6; c["spine.rx"] = -1
    c["upperArmL.raise"] = -26; c["upperArmR.raise"] = -26
    c["forearmL.bend"] = 40 - 18 * math.sin(ph - 0.6); c["forearmR.bend"] = 40 + 18 * math.sin(ph - 0.6)
    c["upperArmL.bend"] = 6 - 8 * math.sin(ph - 0.25); c["upperArmR.bend"] = 6 + 8 * math.sin(ph - 0.25)
    c["handL.bend"] = 10 - 14 * math.sin(ph - 1.4); c["handR.bend"] = 10 + 14 * math.sin(ph - 1.4)
    blink(c, f, N, [20])
    return c


@clip("officer", "talk", 96, True,
      notes="whiny, wheedling talk: jaw in a quick syllable rhythm, a wagging index hand on the stressed words, the "
            "other hand on his chest, head bobbing and tilting, shoulders up")
def officer_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    beats = talk_jaw(c, f, N, 83, amp=(5, 12))
    bt = beat_curve(beats, f, N, width=7); btl = beat_curve(beats, f - 2, N, width=8)
    c["upperArmR.raise"] = -10; c["upperArmR.bend"] = 36 + 6 * btl; c["forearmR.bend"] = 92 + 10 * btl
    c["forearmR.twist"] = -10; c["handR.bend"] = -16 + 30 * btl * wave(f, N, 12); fingers(c, "R", 8)
    arm_ik(c, "L", V(0.012, -0.004, 0.036), V(0.8, -0.6, -0.2), "chest")
    c["handL.bend"] = -8
    c["head.rx"] = -4 + 4 * bt; c["head.rz"] = 5 * wave(f, N, 2, 0.2); c["head.ry"] = 6 * wave(f, N, 1, 0.4)
    c["shoulderL.raise"] += 2; c["shoulderR.raise"] += 2
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -2 * sh
    blink(c, f, N, [16, 60])
    stand_feet(rig, c, spread=0.002)
    return c


def folded_arms(c, w=1.0):
    arm_ik(c, "L", V(-0.026, -0.018, 0.034), V(0.9, -0.5, 0.2), "chest", w)
    arm_ik(c, "R", V(0.028, -0.026, 0.030), V(-0.9, -0.5, 0.2), "chest", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 4, w); c["handR.bend"] = lerp(c.get("handR.bend", 6), 4, w)
    fingers(c, "L", lerp(22, 30, w)); fingers(c, "R", lerp(22, 30, w))


@clip("officer", "fold_arms", 40, False, markers={"huff": 14},
      notes="sulky: a huff (shoulders up and down), folds his arms tight across his chest, chin up, turns his head "
            "away with eyes half closed, weight onto one leg with the other knee bent; holds")
def officer_fold_arms(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    huff = bump(f, 4, 18)
    w = ease_io((f - 6) / 14)
    folded_arms(c, w)
    c["shoulderL.raise"] += 5 * huff; c["shoulderR.raise"] += 5 * huff
    turn = ease_io((f - 14) / 12)
    c["head.ry"] = -22 * turn; c["neck.ry"] = -8 * turn; c["head.rx"] = -10 * turn; c["head.rz"] = -4 * turn
    c["hips.tx"] = 0.006 * turn; c["hips.rz"] = -3 * turn; c["chest.rz"] = 2 * turn
    stand_feet(rig, c, spread=0.002, fwdR=0.006 * turn, pitchR=14 * turn)
    c["eyelids.sy"] = 1.0 + 4.0 * turn
    return c


O_STOMP = (0.064, 0.56)


@clip("officer", "stomp_walk", 30, True, markers={"stompL": 0, "stompR": 15}, speed=O_STOMP,
      notes="angry stamping walk: high knee lifts, each foot slammed down flat (the body jolts on impact), fists "
            "clenched and pumping stiffly, head jutting forward, robe hem flapping")
def officer_stomp_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=O_STOMP[0], lift=0.040, duty=O_STOMP[1], heel=0, toeoff=6, lift_shape=0.6)
    legs_ik_channels(c, g)
    for side in "LR":
        c[f"pole.leg{side}"] = V(0.15 if side == "L" else -0.15, 0.3, 1)
    ph = 2 * math.pi * f / N
    jolt = pulses(f, N, [(0, 1.0), (15, 1.0)], decay=1.6)
    c["hips.ty"] = -0.003 - 0.004 * jolt + 0.002 * math.cos(2 * ph)
    c["chest.rx"] += 6 + 3 * jolt; c["neck.rx"] = -8; c["head.rx"] = 2 + 4 * jolt
    c["hips.rz"] = 3 * math.cos(ph); c["chest.ry"] = -6 * math.sin(ph)
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -20; c[f"upperArm{side}.bend"] = 10 + sg * 22 * math.sin(ph)
        c[f"forearm{side}.bend"] = 70; fingers(c, side, 85)
    blink(c, f, N, [8])
    return c


@clip("officer", "grumble", 72, True, markers={"stamp": 44},
      notes="grumbling to the viewer: both fists up in front of his chest shaking with fury, muttering jaw, then one "
            "foot stamp (body jolts), fists shake again; scowl")
def officer_grumble(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    beats = talk_jaw(c, f, N, 91, amp=(3, 9))
    shake = wave(f, N, 12) * (1 - bump(f, 36, 54))
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.030 * sx, 0.216 + 0.006 * shake, 0.072 + 0.004 * shake), V(0.9 * sx, -0.6, -0.3))
        fingers(c, side, 88); c[f"hand{side}.bend"] = 10
    lift = bump(f, 34, 46)
    jolt = pulses(f, N, [(46, 1.0)], decay=1.8)
    stand_feet(rig, c, spread=0.003, liftR=0.030 * lift)
    c["pole.legR"] = V(-0.15, 0.3, 1)
    c["hips.ty"] = -0.004 * jolt; c["chest.rx"] += 6 + 4 * jolt; c["head.rx"] = 4 + 6 * jolt
    c["head.ry"] = 4 * shake; c["chest.ry"] = 3 * shake
    c["hips.tx"] = -0.004 * lift; c["hips.rz"] = 3 * lift
    blink(c, f, N, [20, 60])
    return c


@clip("officer", "sly_idea", 50, False, markers={"idea": 24},
      notes="sly idea: rubs his chin thinking (eyes up), then \"aha!\" - the right hand pops up beside his face, "
            "fingers up (single-bone fingers: open hand, palm forward), head tilts with a sly grin, the other hand on "
            "his hip; holds")
def officer_sly_idea(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    think = ease_io(f / 8) * (1 - ease_io((f - 18) / 6))
    pop = ease_io((f - 20) / 7) + 0.08 * bump(f, 24, 34)
    arm_ik(c, "R", V(-0.012, -0.032, 0.028), V(-0.8, -0.8, -0.1), "head", think)
    c["handR.bend"] = 20 * think; fingers(c, "R", 40 * think)
    c["upperArmR.raise"] = lerp(c["upperArmR.raise"], 26, pop); c["upperArmR.bend"] = lerp(8, 26, pop)
    c["forearmR.bend"] = lerp(26, 118, pop); c["forearmR.twist"] = lerp(10, -40, pop)
    c["handR.bend"] += -14 * pop; fingers(c, "R", c["fingersR.curl"] * (1 - pop) + 4 * pop)
    arm_ik(c, "L", V(0.060, 0.180, 0.004), V(1.0, 0.1, -0.7), "root", ease_io((f - 10) / 12))
    c["handL.bend"] = 30; c["handL.twist"] = 60; fingers(c, "L", 40)
    c["head.rx"] = -10 * think + 4 * pop - 4; c["head.ry"] = 8 * think - 6 * pop; c["head.rz"] = 10 * pop
    c["chest.rx"] += -3 * pop; c["hips.tx"] = 0.004 * pop
    stand_feet(rig, c, spread=0.002, pitchR=8 * pop)
    blink(c, f, N, [4], loop=False)
    c["eyelids.sy"] = max(c["eyelids.sy"], 1.0 + 3.0 * pop)
    return c


@clip("officer", "rub_hands", 40, True,
      notes="scheming glee: hunched, hands rubbing together quickly in front of his chest, shoulders up, giggling "
            "head bobs")
def officer_rub_hands(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    r = wave(f, N, 4)
    at = V(0.0, 0.205, 0.056)
    arm_ik(c, "L", at + V(0.010, 0.006 * r, -0.004 + 0.004 * r), V(0.8, -0.6, -0.4))
    arm_ik(c, "R", at + V(-0.010, -0.006 * r, -0.004 - 0.004 * r), V(-0.8, -0.6, -0.4))
    c["handL.twist"] = -40; c["handR.twist"] = 40; c["handL.bend"] = 4; c["handR.bend"] = 4
    fingers(c, "L", 20); fingers(c, "R", 20)
    gig = pulses(f, N, [(6, 1.0), (14, 0.7), (26, 0.9)], decay=2.0)
    c["shoulderL.raise"] += 4 + 3 * gig; c["shoulderR.raise"] += 4 + 3 * gig
    c["chest.rx"] += 8; c["spine.rx"] = 4; c["neck.rx"] = -4; c["head.rx"] = -2 - 3 * gig; c["head.rz"] = 4 * wave(f, N, 1)
    c["jaw.rx"] = 4 * gig
    blink(c, f, N, [30])
    stand_feet(rig, c, spread=0.002)
    return c


@clip("officer", "bow_flatter", 96, True, props=["scroll"], markers={"bow1": 22, "bow2": 70},
      notes="oily flattery to the king: two deep bows per loop from the hips with a sweeping left-hand flourish (a "
            "circle out and down to the side), the right hand holding the law scroll against his chest; comes up with "
            "a big fake grin and a head tilt between the bows (officer/scroll shown)")
def officer_bow_flatter(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    bow = K([(0, 0), (8, -0.1), (22, 1.0), (32, 0.9), (44, 0.0), (56, -0.1), (70, 1.0), (80, 0.9), (92, 0.0), (96, 0)],
            f, N, True)
    bowl = KL([(0, 0), (8, -0.1), (22, 1.0), (32, 0.9), (44, 0.0), (56, -0.1), (70, 1.0), (80, 0.9), (92, 0.0), (96, 0)],
              f, N, True, lag=3)
    c["hips.rx"] = 18 * bow; c["spine.rx"] = 16 * bow; c["chest.rx"] += 14 * bowl; c["neck.rx"] = 4 * bowl
    c["head.rx"] = -6 + 6 * bowl
    c["hips.tz"] = -0.012 * bow
    arm_ik(c, "R", V(-0.012, -0.014, 0.040), V(-0.8, -0.6, -0.2), "chest")
    c["handR.bend"] = 0; c["handR.twist"] = -20; fingers(c, "R", 68)
    # left flourish: out and round in a circle, ending low to the side at the bottom of the bow
    fl = K([(0, 0), (10, 0.3), (22, 1.0), (34, 0.6), (44, 0), (58, 0.3), (70, 1.0), (82, 0.6), (92, 0), (96, 0)], f, N, True)
    c["upperArmL.raise"] = -22 + 60 * fl; c["upperArmL.bend"] = 8 + 30 * math.sin(math.pi * fl)
    c["forearmL.bend"] = 26 + 40 * math.sin(math.pi * fl) ** 2; c["forearmL.twist"] = -10 + 60 * fl
    c["handL.bend"] = -20 * fl + 14 * wave(f, N, 4); fingers(c, "L", 4)
    c["head.rz"] = 10 * (1 - bow) * bump(f, 36, 58) + 10 * bump(f, 84, 96) + 10 * bump(f, 0, 10)
    stand_feet(rig, c, spread=0.002, fwdL=0.012)
    blink(c, f, N, [40, 88])
    return c


O_TIP = (0.056, 0.52)


@clip("officer", "tiptoe", 40, True, markers={"contactL": 0, "contactR": 20}, speed=O_TIP,
      notes="exaggerated cartoon tiptoe: on the tips of his curly slippers, knees lifted high and placed carefully, "
            "hunched forward, both hands held up at his chest like little paws, head low and turning to peek about")
def officer_tiptoe(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=O_TIP[0], lift=0.034, duty=O_TIP[1], heel=-34, toeoff=40, lift_shape=0.7)
    for side in "LR":
        t, pitch, contact, p = g["leg" + side]
        pt = 36.0
        t = V(t.x, planted_ankle_y(rig, side, pt) + (t.y - planted_ankle_y(rig, side, pitch)), t.z + pivot_dz(rig, side, pitch))
        c["ik.leg" + side] = t; c[f"foot{side}.pitch"] = pt
        c[f"pole.leg{side}"] = V(0.2 if side == "L" else -0.2, 0.2, 1)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = 0.002 + 0.004 * math.cos(2 * ph - 0.8)
    c["spine.rx"] = 10; c["chest.rx"] += 14; c["neck.rx"] = -10; c["head.rx"] = -4
    c["hips.rz"] = 2 * math.cos(ph); c["chest.ry"] = -4 * math.sin(ph)
    c["head.ry"] = 22 * K([(0, 0), (8, 1), (16, 1), (22, -1), (34, -1), (40, 0)], f, N, True)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.034 * sx, 0.208 + 0.004 * math.sin(ph + (0 if side == "L" else math.pi)), 0.060),
               V(0.9 * sx, -0.7, -0.2))
        c[f"hand{side}.bend"] = 50; fingers(c, side, 30)
    blink(c, f, N, [26])
    return c


@clip("officer", "peek", 90, True, markers={"out": 20, "back": 60},
      notes="spying from behind the palm: leans far out sideways to his left (hips and spine), the head pokes out "
            "and turns toward the target, rubs his hands in glee while out, then ducks back to cover and peeks again")
def officer_peek(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    out = K([(0, 0.15), (12, 0.15), (20, 1.0), (52, 1.0), (60, 0.15), (72, 0.15), (78, 0.6), (84, 0.6), (90, 0.15)], f, N, True)
    outl = KL([(0, 0.15), (12, 0.15), (20, 1.0), (52, 1.0), (60, 0.15), (72, 0.15), (78, 0.6), (84, 0.6), (90, 0.15)], f, N, True, lag=3)
    c["hips.tx"] = 0.018 * out; c["hips.rz"] = 8 * out; c["spine.rz"] = 14 * outl; c["chest.rz"] = 12 * outl
    c["neck.rz"] = 8 * outl; c["head.rz"] = -18 * outl
    c["chest.rx"] += 8; c["spine.rx"] = 4; c["head.rx"] = -4
    r = wave(f, N, 8)
    at = V(0.004, 0.205, 0.052)
    arm_ik(c, "L", at + V(0.010, 0.005 * r, -0.004), V(0.8, -0.6, -0.4), "root", out)
    arm_ik(c, "R", at + V(-0.010, -0.005 * r, -0.004), V(-0.8, -0.6, -0.4), "root", out)
    fingers(c, "L", 20); fingers(c, "R", 20)
    stand_feet(rig, c, spread=0.004 + 0.006 * out, pitchR=12 * out)
    blink(c, f, N, [34, 80])
    return c


@clip("officer", "point", 36, False, markers={"point": 14},
      notes="accusing: \"aha!\" - leans in and thrusts the right arm straight out at Daniel (open hand, fingers "
            "straight - single-bone fingers), the left hand on his hip, chin jutting; holds pointing")
def officer_point(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    ant = bump(f, 0, 10)
    th = ease_io((f - 6) / 7) + 0.08 * bump(f, 12, 24)
    arm_ik(c, "R", vlerp(V(-0.060, 0.205, 0.030), V(-0.030, 0.252, 0.150), th) + V(0, 0, -0.02 * ant),
           V(-0.9, -0.4, -0.2), "root", min(1.0, 0.2 + 1.2 * th))
    c["forearmR.twist"] = lerp(10, -20, th)
    c["handR.bend"] = -10 * th; fingers(c, "R", lerp(22, 2, th))
    arm_ik(c, "L", V(0.058, 0.180, 0.004), V(1.0, 0.1, -0.7), "root", ease_io((f - 4) / 10))
    c["handL.bend"] = 30; c["handL.twist"] = 60; fingers(c, "L", 40)
    c["spine.rx"] = 6 * th - 3 * ant; c["chest.rx"] += 4 * th; c["hips.tz"] = 0.008 * th
    c["chest.ry"] = -10 * th; c["neck.rx"] = -6 * th; c["head.rx"] = -6 * th
    stand_feet(rig, c, spread=0.003, fwdR=0.022 * ease_io((f - 4) / 8))
    blink(c, f, N, [26], loop=False)
    return c


@clip("officer", "scared_jump", 40, False, markers={"jump": 6, "land": 26},
      notes="cartoon fright: jumps straight up off both feet, legs cycling in the air (two quick running circles), "
            "arms flung up and wiggling, hair-raising stretch; lands in a low crouch already leaning to run")
def officer_scared_jump(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.1)
    air = bump(f, 4, 28)
    up = ease_io((f - 2) / 6)
    c["hips.ty"] = 0.085 * air - 0.010 * bump(f, 24, 40) - 0.006 * bump(f, 0, 5)
    c["chest.rx"] += -8 * air; c["neck.rx"] = -6 * air; c["head.rx"] = -6 * air
    stand_feet(rig, c, spread=0.004)
    cyc = 2 * math.pi * (f - 6) / 10
    for side, off in (("L", 0.0), ("R", math.pi)):
        a = cyc + off
        base = c["ik.leg" + side]
        lift = V(0, 0.085 * air + 0.020 * air * (1 + math.sin(a)), 0.024 * air * math.cos(a))
        c["ik.leg" + side] = base + lift
        c[f"foot{side}.pitch"] = 20 * air
    for side, sx, ph in (("L", 1, 0.0), ("R", -1, 0.5)):
        c[f"upperArm{side}.raise"] = lerp(-22, 110, up) * (1 - 0.6 * ease_io((f - 26) / 10))
        c[f"upperArm{side}.bend"] = 10 + 10 * wave(f, 10, 1, ph); c[f"forearm{side}.bend"] = 20 + 20 * wave(f, 6, 1, ph)
        c[f"hand{side}.bend"] = 20 * wave(f, 4, 1, ph); fingers(c, side, 0)
    crouch = ease_io((f - 26) / 6)
    c["hips.ty"] -= 0.012 * crouch; c["spine.rx"] = 12 * crouch; c["chest.rx"] += 6 * crouch
    c["eyelids.sy"] = 1.0
    return c


O_RUN = (0.100, 0.40)


@clip("officer", "run_away", 18, True, markers={"contactL": 0, "contactR": 9}, speed=O_RUN,
      notes="panicked cartoon run: fast high-kneed strides, body leaning forward, both arms flailing wildly over his "
            "head, head thrown back yelling (jaw open), robe hem flapping")
def officer_run_away(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.2)
    g = gait(rig, f, N, L=O_RUN[0], lift=0.040, duty=O_RUN[1], heel=6, toeoff=30, lift_shape=0.8)
    legs_ik_channels(c, g)
    for side in "LR":
        c[f"pole.leg{side}"] = V(0.15 if side == "L" else -0.15, 0.2, 1)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = 0.004 + 0.006 * math.cos(2 * ph - 0.9)
    c["spine.rx"] = 12; c["chest.rx"] += 6; c["neck.rx"] = -14; c["head.rx"] = -10
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -10 * math.sin(ph - 0.3)
    for side, sg in (("L", 1), ("R", -1)):
        a = ph + (0 if side == "L" else math.pi * 0.7)
        c[f"upperArm{side}.raise"] = 95 + 20 * math.sin(a)
        c[f"upperArm{side}.bend"] = 10 + 25 * math.cos(a)
        c[f"forearm{side}.bend"] = 30 + 25 * math.sin(2 * a)
        c[f"hand{side}.bend"] = 25 * math.sin(2 * a + 1); fingers(c, side, 0)
    c["jaw.rx"] = 14 + 4 * math.sin(2 * ph)
    c["eyelids.sy"] = 1.0
    return c


# =============================================================================================== LIONS (lion + lion2)
# Rest: standing on all fours, paws flat, facing +Z, tail in an S-curve up behind the rump. Same clip functions for
# both; every distance is scaled by the rig (k = 1 for the lion, ~0.92 for the lioness).
LEGS = ("frontL", "frontR", "hindL", "hindR")
END = {"frontL": "pawL", "frontR": "pawR", "hindL": "footL", "hindR": "footR"}
BODY_BONES = ("hips", "spine", "chest")
TAIL = ("tail1", "tail2", "tail3", "tail4")


def lk(rig):
    return rig.head["upperArmL"].y / 0.092


def tip(rig, leg):
    return rig.tail[END[leg]].copy()


def paws_stand(rig, c, offs=None, pitch=None):
    """All four paw tips at their rest spots (+ offsets, root space): planted."""
    offs = offs or {}; pitch = pitch or {}
    for leg in LEGS:
        c["ik." + leg] = tip(rig, leg) + offs.get(leg, V())
        c[leg + ".pitch"] = pitch.get(leg, 0.0)


def tail_sway(c, f, N, amp=8.0, cycles=1.0, phase=0.0, lift=0.0, loop=True):
    """Sideways tail swing travelling down the tail (each segment late)."""
    for i, b in enumerate(TAIL):
        a = amp * (0.6 + 0.25 * i) * wave(f - 3 * i, N, cycles, phase)
        if i < 2:
            c[b + ".ry"] = c.get(b + ".ry", 0.0) + a
        else:
            c[b + ".rz"] = c.get(b + ".rz", 0.0) + a
        c[b + ".rx"] = c.get(b + ".rx", 0.0) - lift * (1.0 if i < 2 else 0.5)


def l_base(rig, f, N, cycles=2, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.0 * b * amp; c["spine.rx"] = 0.6 * b * amp
    c["hips.ty"] = 0.0006 * b * amp * lk(rig)
    c["neck.rx"] = 0.6 * b * amp
    c["earL.rx"] = 0.0; c["earR.rx"] = 0.0
    return c


def ear_twitch(c, f, N, side, hits, loop=True, amp=22.0):
    v = pulses(f, N, hits, decay=1.6, loop=loop)
    c[f"ear{side}.rz"] = c.get(f"ear{side}.rz", 0.0) + amp * v * (1 if side == "L" else -1)
    c[f"ear{side}.rx"] = c.get(f"ear{side}.rx", 0.0) - 0.5 * amp * v


# --- sitting: rump down on the page, front legs straight, hind feet flat, tail round the side
def sit_pose(rig, c, w=1.0):
    k = lk(rig)
    c["hips.rx"] = c.get("hips.rx", 0.0) - 38 * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.034 * k * w
    c["hips.ty"] = c.get("hips.ty", 0.0) - 0.050 * k * w
    c["spine.rx"] = c.get("spine.rx", 0.0) + 4 * w
    c["chest.rx"] = c.get("chest.rx", 0.0) + 8 * w
    c["neck.rx"] = c.get("neck.rx", 0.0) + 16 * w
    c["head.rx"] = c.get("head.rx", 0.0) + 14 * w
    for leg in ("frontL", "frontR"):
        c["ik." + leg] = c.get("ik." + leg, tip(rig, leg)) + V(0, 0, -0.008 * k * w)
    for leg, sx in (("hindL", 1), ("hindR", -1)):
        t = tip(rig, leg)
        c["ik." + leg] = vlerp(c.get("ik." + leg, t), V(t.x + 0.010 * k * sx, t.y, t.z + 0.030 * k), w)
        c[leg + ".pitch"] = lerp(c.get(leg + ".pitch", 0.0), -26, w)
        c["pole." + leg] = V(0.35 * sx, 0.3, 1)
    # tail: from the rump along the page and round his left side toward the front paws
    for b, rx, ry, rz in (("tail1", 46, -18, 0), ("tail2", 24, -30, 0), ("tail3", 40, 0, 50), ("tail4", 30, 0, 40)):
        c[b + ".rx"] = c.get(b + ".rx", 0.0) + rx * w
        c[b + ".ry"] = c.get(b + ".ry", 0.0) + ry * w
        c[b + ".rz"] = c.get(b + ".rz", 0.0) + rz * w
    c["settle"] = ("hips", ("hips", "thighL", "thighR", "tail1"), 0.0015, w)


# --- lying on the belly (sphinx), front legs forward on the page, hind legs folded beside the body
def lie_pose(rig, c, w=1.0, head_down=1.0):
    k = lk(rig)
    c["hips.ty"] = c.get("hips.ty", 0.0) - 0.046 * k * w
    c["hips.rx"] = c.get("hips.rx", 0.0) + 1 * w
    for leg, sx in (("frontL", 1), ("frontR", -1)):
        t = tip(rig, leg)
        c["ik." + leg] = vlerp(c.get("ik." + leg, t), V(t.x - 0.002 * k * sx, t.y, t.z + 0.050 * k), w)
        c[leg + ".pitch"] = lerp(c.get(leg + ".pitch", 0.0), -20, w)
        c["pole." + leg] = V(0.3 * sx, 0.2, -1)
    for leg, sx in (("hindL", 1), ("hindR", -1)):
        t = tip(rig, leg)
        c["ik." + leg] = vlerp(c.get("ik." + leg, t), V(t.x + 0.020 * k * sx, t.y + 0.002 * k, t.z + 0.028 * k), w)
        c[leg + ".pitch"] = lerp(c.get(leg + ".pitch", 0.0), -26, w)
        c["pole." + leg] = V(0.6 * sx, 0.2, 1)
    c["neck.rx"] = c.get("neck.rx", 0.0) + (8 + 26 * head_down) * w
    c["head.rx"] = c.get("head.rx", 0.0) + (4 + 6 * head_down) * w
    for b, rx in (("tail1", 30), ("tail2", 30), ("tail3", 26), ("tail4", 10)):
        c[b + ".rx"] = c.get(b + ".rx", 0.0) + rx * w
    c["settle"] = ("hips", BODY_BONES, 0.003, w)


def curl_pose(rig, c, w=1.0):
    """On top of lie_pose: body curved into a C toward its left, head on the left paw, tail round the front."""
    c["spine.ry"] = c.get("spine.ry", 0.0) + 10 * w
    c["chest.ry"] = c.get("chest.ry", 0.0) + 12 * w
    c["neck.ry"] = c.get("neck.ry", 0.0) + 24 * w
    c["head.ry"] = c.get("head.ry", 0.0) + 12 * w
    c["head.rz"] = c.get("head.rz", 0.0) + 16 * w
    for b, ry, rz in (("tail1", -26, 0), ("tail2", -40, 0), ("tail3", 0, -30), ("tail4", 0, -30)):
        c[b + ".ry"] = c.get(b + ".ry", 0.0) + ry * w
        c[b + ".rz"] = c.get(b + ".rz", 0.0) + rz * w
    k = lk(rig)
    c["ik.frontR"] = c["ik.frontR"] + V(0.010 * k * w, 0, 0)
    c["ik.frontL"] = c["ik.frontL"] + V(0.006 * k * w, 0, -0.004 * k * w)


def lion_stand(rig, f, N, cycles=2, amp=1.0):
    c = l_base(rig, f, N, cycles, amp)
    paws_stand(rig, c)
    return c


def mixs(a, b, w):
    """mix() for lion channel dicts, settle tuples included."""
    sa, sb = a.get("settle"), b.get("settle")
    a2 = {k: v for k, v in a.items() if k != "settle"}; b2 = {k: v for k, v in b.items() if k != "settle"}
    out = mix(a2, b2, w)
    if sa and sb:
        out["settle"] = (sb[0], sb[1], sb[2], lerp(sa[3], sb[3], w))
    elif sa:
        out["settle"] = (sa[0], sa[1], sa[2], sa[3] * (1 - w))
    elif sb:
        out["settle"] = (sb[0], sb[1], sb[2], sb[3] * w)
    return out


def mix_groups(a, b, wts, default):
    """Blend per channel group: wts = {prefix tuple: weight}; others use `default`."""
    out = mixs(a, b, default)
    for prefixes, w in wts.items():
        part = mixs({k: v for k, v in a.items() if k.startswith(prefixes) and k != "settle"},
                    {k: v for k, v in b.items() if k.startswith(prefixes) and k != "settle"}, w)
        out.update(part)
    return out


def step_lifts(rig, c, wts):
    """Paws that move to a new spot during a transition are lifted (a step), not slid along the page."""
    k = lk(rig)
    for leg, w in wts.items():
        c["ik." + leg] = c["ik." + leg] + V(0, 0.014 * k * math.sin(math.pi * min(1.0, max(0.0, w))), 0)


FRONT = ("ik.frontL", "ik.frontR", "frontL.", "frontR.", "pole.frontL", "pole.frontR")
HIND = ("ik.hindL", "ik.hindR", "hindL.", "hindR.", "pole.hindL", "pole.hindR")
HEAD = ("neck.", "head.", "jaw.", "earL.", "earR.", "mane.")
TAILP = ("tail1.", "tail2.", "tail3.", "tail4.")


@clip("lions", "idle", 150, True,
      notes="sitting like a big cat: rump on the page, front legs straight, hind feet flat, tail round his left side; "
            "slow breathing, looks about with curious head tilts, the tail tip flicks twice, ears twitch, blinks "
            "(single, double, slow)")
def lion_idle(rig, f, N):
    c = l_base(rig, f, N, cycles=3, amp=1.2)
    paws_stand(rig, c)
    sit_pose(rig, c, 1.0)
    look = [(0, 0), (24, 0), (34, 18), (60, 18), (70, -12), (100, -12), (112, 0), (150, 0)]
    c["neck.ry"] = 0.4 * K(look, f, N, True); c["head.ry"] = 0.6 * KL(look, f, N, True, lag=4)
    c["head.rz"] = 12 * bump(f, 36, 62) - 10 * bump(f, 74, 98)
    flick = pulses(f, N, [(46, 1.0), (52, 0.6), (118, 0.9)], decay=2.2)
    c["tail3.rz"] += 26 * flick; c["tail4.rz"] += 34 * flick; c["tail4.rx"] = c.get("tail4.rx", 0) - 20 * flick
    tail_sway(c, f, N, amp=3.0, cycles=1)
    ear_twitch(c, f, N, "L", [(80, 1.0)]); ear_twitch(c, f, N, "R", [(20, 1.0), (26, 0.6)])
    blink(c, f, N, [12, 64, 70, 128])
    return c


@clip("lions", "sleep", 180, True,
      notes="asleep, lying curled on the belly: body in a C toward its left, chin on the left paw, tail curled round "
            "the front; slow deep breathing (3 s), a little snore in the jaw, one ear twitch, a tail-tip twitch, "
            "eyes closed")
def lion_sleep(rig, f, N):
    c = l_base(rig, f, N, cycles=2, amp=2.2)
    paws_stand(rig, c)
    lie_pose(rig, c, 1.0)
    curl_pose(rig, c, 1.0)
    br = wave(f, N, 2)
    c["jaw.rx"] = 2.0 + 2.0 * max(0.0, br)
    ear_twitch(c, f, N, "R", [(70, 1.0), (75, 0.7)], amp=26)
    tw = pulses(f, N, [(132, 1.0)], decay=2.5)
    c["tail4.rz"] += 30 * tw; c["tail3.rz"] += 12 * tw
    c["eyelids.sy"] = 12.78
    return c


@clip("lions", "wake_up", 96, False, markers={"head_up": 22, "up": 76},
      notes="from sleep: an ear twitches, the head lifts, sleepy half-open eyes and a slow blink, a little head shake, "
            "front legs push up, then the rump, straightens the tail; ends standing on all fours (blends into roar / "
            "growl / prowl)")
def lion_wake_up(rig, f, N):
    a = lion_sleep(rig, 0, 180)
    b = lion_stand(rig, f, N, cycles=1, amp=1.0)
    head = ease_io((f - 6) / 18)
    body = ease_io((f - 40) / 28)
    front = ease_io((f - 38) / 22)
    hind = ease_io((f - 52) / 22)
    tail = ease_io((f - 30) / 40)
    c = mix_groups(a, b, {HEAD: head, FRONT: front, HIND: hind, TAILP: tail}, body)
    step_lifts(rig, c, {"frontL": ease_io((f - 38) / 14), "frontR": ease_io((f - 44) / 14),
                        "hindL": ease_io((f - 52) / 14), "hindR": ease_io((f - 58) / 14)})
    # head: lifts a little higher while still lying, looks round sleepily
    c["neck.rx"] -= 10 * bump(f, 10, 50); c["head.ry"] += 8 * bump(f, 24, 46)
    c["head.rz"] += 6 * wave(f, 12, 1) * bump(f, 30, 44)
    c["chest.rx"] -= 6 * bump(f, 40, 62)
    ear_twitch(c, f, N, "L", [(2, 1.0)], loop=False)
    lids = 12.78 - 6.0 * head - 5.8 * ease_io((f - 66) / 12)
    lids = max(lids, 12.78 * bump(f, 28, 36))
    c["eyelids.sy"] = max(1.0, lids)
    return c


@clip("lions", "roar", 80, False, markers={"roar": 22},
      notes="the big roar (warm, not scary): draws the head back and down, then rears it up and forward with the jaw "
            "wide (28 deg), the mane shaking, chest up, tail up stiff, paws planted; closes the mouth with a little "
            "head shake and a proud huff; ends standing")
def lion_roar(rig, f, N):
    c = lion_stand(rig, f, N, cycles=1, amp=0.6)
    k = lk(rig)
    ant = bump(f, 0, 18)
    roar = ease_io((f - 14) / 8) * (1 - ease_io((f - 48) / 14))
    c["hips.tz"] = -0.006 * k * ant + 0.004 * k * roar
    c["chest.rx"] += 6 * ant - 10 * roar; c["spine.rx"] += 2 * ant - 4 * roar
    c["neck.rx"] += 14 * ant - 14 * roar; c["head.rx"] = 6 * ant + 4 * roar
    shake = wave(f, 7, 1) * bump(f, 18, 52)
    c["head.ry"] = 7 * shake; c["neck.ry"] = 3 * shake
    c["mane.rx"] = 4 * shake; c["mane.rz"] = 8 * shake
    c["jaw.rx"] = 28 * roar + 3 * ant
    huff = bump(f, 58, 70)
    c["head.ry"] += 6 * wave(f, 8, 1) * bump(f, 56, 72); c["head.rx"] += -4 * huff; c["jaw.rx"] += 4 * huff
    for b, v in (("tail1", -18), ("tail2", -14), ("tail3", -8), ("tail4", 10)):
        c[b + ".rx"] = v * roar
    c["earL.rx"] = 18 * roar; c["earR.rx"] = 18 * roar
    c["eyelids.sy"] = 1.0 + 2.5 * roar
    if f > 66:
        blink(c, f, N, [70], loop=False)
    return c


@clip("lions", "growl", 90, True,
      notes="a low warning growl: head lowered and forward, shoulders hunched, the lip curls (jaw trembles a little "
            "open), weight rocks slowly side to side and each front paw lifts and is set down again on the same spot, "
            "tail low and swishing")
def lion_growl(rig, f, N):
    c = lion_stand(rig, f, N, cycles=2, amp=0.8)
    k = lk(rig)
    sw = wave(f, N, 1)
    c["hips.ty"] -= 0.006 * k; c["hips.tx"] = 0.005 * k * sw
    c["chest.rz"] = -3 * sw; c["hips.rz"] = 2 * sw; c["spine.ry"] = 3 * sw
    c["chest.rx"] += 6; c["neck.rx"] += 18; c["head.rx"] = -10 + 2 * wave(f, N, 2, 0.3)
    c["head.ry"] = -4 * sw
    c["jaw.rx"] = 6 + 2.0 * wave(f, N, 15) + 2 * bump(f, 30, 60)
    for leg, at in (("frontL", 18), ("frontR", 63)):
        lift = bump(f, at, at + 14)
        c["ik." + leg] = c["ik." + leg] + V(0, 0.016 * k * lift, 0.004 * k * lift)
        c[leg + ".pitch"] = 40 * lift
    tail_sway(c, f, N, amp=12, cycles=1, phase=0.25, lift=-14)
    c["earL.rx"] = 22; c["earR.rx"] = 22
    blink(c, f, N, [44])
    c["eyelids.sy"] = max(c["eyelids.sy"], 2.0)
    return c


def quad_gait(rig, c, f, N, L, lift, duty, phases, flexF=55.0, flexH=40.0, lo_y=0.0):
    """In-place four-beat gait: per leg the paw tip slides back from +L/2 to -L/2 during stance (planted in world when
    the director moves the actor at L / (duty * N / FPS)), then swings forward with lift and wrist / hock flexion."""
    for leg in LEGS:
        p = (f / N + phases[leg]) % 1.0
        t0 = tip(rig, leg)
        front = leg.startswith("front")
        if p < duty:
            s = p / duty
            z = L / 2 - L * s
            y = t0.y + lo_y
            pitch = 22 * smooth((s - 0.8) / 0.2)            # heel peels up at the end of the stance (tip stays)
        else:
            s = (p - duty) / (1 - duty)
            z = -L / 2 + L * smooth(s)
            y = t0.y + lo_y + lift * math.sin(math.pi * s) ** 0.8
            pitch = lerp(22, 0, smooth(s * 1.15)) + (flexF if front else flexH) * math.sin(math.pi * min(1.0, s * 1.1)) ** 1.2
        c["ik." + leg] = V(t0.x, y, t0.z + z)
        c[leg + ".pitch"] = pitch


L_WALK = (0.060, 0.62)
L_PHASE = {"hindL": 0.0, "frontL": 0.25, "hindR": 0.5, "frontR": 0.75}


@clip("lions", "walk", 40, True, markers={"hindL": 0, "frontL": 10, "hindR": 20, "frontR": 30}, speed=L_WALK,
      notes="relaxed cat walk, lateral four-beat sequence (left hind, left fore, right hind, right fore): soft "
            "shoulder and hip roll, head steady with a small nod, tail swaying late; paws planted in stance")
def lion_walk(rig, f, N):
    c = l_base(rig, f, N, cycles=1, amp=0.4)
    k = lk(rig)
    quad_gait(rig, c, f, N, L_WALK[0] * k, 0.018 * k, L_WALK[1], L_PHASE)
    ph = 2 * math.pi * f / N
    c["hips.ty"] += -0.002 * k + 0.0015 * k * math.cos(2 * ph)
    c["hips.rz"] = 3 * math.sin(ph); c["chest.rz"] = -4 * math.sin(ph - 1.6)
    c["spine.ry"] = 3 * math.sin(ph); c["chest.ry"] = -3 * math.sin(ph - 0.6)
    c["neck.ry"] = 2 * math.sin(ph - 1.2); c["head.ry"] = -2 * math.sin(ph - 1.2)
    c["neck.rx"] += 2 * math.cos(2 * ph - 0.6); c["head.rx"] = -2 * math.cos(2 * ph - 0.6)
    tail_sway(c, f, N, amp=10, cycles=1, phase=0.1, lift=4)
    blink(c, f, N, [16])
    return c


L_PROWL = (0.050, 0.70)


@clip("lions", "prowl", 60, True, markers={"hindL": 0, "frontL": 15, "hindR": 30, "frontR": 45}, speed=L_PROWL,
      notes="slow stalking prowl: body low, head low and forward, shoulder blades rolling, each paw lifted high and "
            "placed carefully, a slow swish of the low tail, eyes fixed ahead")
def lion_prowl(rig, f, N):
    c = l_base(rig, f, N, cycles=1, amp=0.3)
    k = lk(rig)
    quad_gait(rig, c, f, N, L_PROWL[0] * k, 0.022 * k, L_PROWL[1], L_PHASE, flexF=65, flexH=45)
    ph = 2 * math.pi * f / N
    c["hips.ty"] += -0.011 * k + 0.0012 * k * math.cos(2 * ph)
    c["chest.rx"] += 5; c["neck.rx"] += 16; c["head.rx"] = -12
    c["chest.rz"] = -5 * math.sin(ph - 1.6); c["hips.rz"] = 3 * math.sin(ph)
    c["spine.ry"] = 2 * math.sin(ph); c["neck.ry"] = -2 * math.sin(ph - 1.2); c["head.ry"] = 2 * math.sin(ph - 1.2)
    tail_sway(c, f, N, amp=14, cycles=1, phase=0.3, lift=-10)
    c["earL.rx"] = 10; c["earR.rx"] = 10
    blink(c, f, N, [40])
    return c


@clip("lions", "yawn", 120, False, markers={"stretch": 26, "yawn": 84},
      notes="lazy and funny: a long cat stretch (front paws walk forward, chest down, rump up, eyes shut), back up, "
            "sits down, then a HUGE yawn (head up, jaw wide 36 deg, ears back, eyes squeezed), a lip smack and a "
            "content blink; ends sitting (= idle frame 0)")
def lion_yawn(rig, f, N):
    k = lk(rig)
    st = lion_stand(rig, f, N, cycles=1, amp=0.5)
    sit = lion_idle(rig, 0, 150)
    bow = ease_io((f - 4) / 18) * (1 - ease_io((f - 36) / 14))
    # stretch: front paws step forward, chest down (hips pitch nose-down about the rump), neck long
    for leg, at in (("frontL", 4), ("frontR", 10)):
        out = ease_io((f - at) / 9) * (1 - ease_io((f - 34 - (at - 4)) / 10))
        st["ik." + leg] = st["ik." + leg] + V(0, 0.010 * k * bump(f, at, at + 9) + 0.010 * k * bump(f, 34 + at - 4, 44 + at - 4),
                                              0.032 * k * out)
        st[leg + ".pitch"] = -20 * out
    st["hips.rx"] = 14 * bow; st["hips.ty"] += 0.002 * k * bow; st["spine.rx"] = 8 * bow; st["chest.rx"] += 6 * bow
    st["neck.rx"] = -16 * bow; st["head.rx"] = 6 * bow
    for b, v in (("tail1", -20), ("tail2", -16), ("tail3", -10)):
        st[b + ".rx"] = v * bow
    st["eyelids.sy"] = 1.0 + 11.78 * bump(f, 8, 40)
    s = ease_io((f - 46) / 18)
    c = mixs(st, sit, s)
    # the yawn (sitting): head tips up, jaw opens wide, eyes squeezed, ears back
    y = ease_io((f - 66) / 12) * (1 - ease_io((f - 92) / 10))
    c["neck.rx"] -= 8 * y; c["head.rx"] -= 4 * y
    c["jaw.rx"] = 36 * y + 5 * pulses(f, N, [(104, 1.0), (110, 0.7)], decay=1.5, loop=False)
    c["earL.rx"] = c.get("earL.rx", 0) + 30 * y; c["earR.rx"] = c.get("earR.rx", 0) + 30 * y
    c["chest.rx"] -= 4 * y
    c["eyelids.sy"] = max(c.get("eyelids.sy", 1.0), 1.0 + 11.78 * ease_io((f - 64) / 6) * (1 - ease_io((f - 96) / 8)))
    if f >= 100:
        blink(c, f, N, [112], loop=False, slow=1.6)
        c["eyelids.sy"] = max(c["eyelids.sy"], 1.0)
    return c


@clip("lions", "lie_down", 72, False, markers={"down": 44},
      notes="settles down for a rest: the front legs fold first (chest sinks), then the rump, front paws forward, "
            "head lowered onto the paws with a happy sigh, tail curled along the side; holds lying (blissful)")
def lion_lie_down(rig, f, N):
    a = lion_stand(rig, f, N, cycles=1, amp=0.5)
    b = lion_stand(rig, 0, N, cycles=1, amp=0.0)
    lie_pose(rig, b, 1.0)
    front = ease_io((f - 6) / 22)
    body = ease_io((f - 14) / 26)
    hind = ease_io((f - 20) / 22)
    head = ease_io((f - 30) / 22)
    tail = ease_io((f - 26) / 30)
    c = mix_groups(a, b, {FRONT: front, HIND: hind, HEAD: head, TAILP: tail}, body)
    step_lifts(rig, c, {"frontL": ease_io((f - 4) / 12), "frontR": ease_io((f - 10) / 12),
                        "hindL": ease_io((f - 20) / 12), "hindR": ease_io((f - 26) / 12)})
    c["chest.rx"] += 8 * bump(f, 6, 36)
    sigh = bump(f, 50, 66)
    c["chest.rx"] -= 3 * sigh; c["hips.ty"] += 0.0015 * sigh
    c["eyelids.sy"] = 1.0 + 5.0 * ease_io((f - 46) / 10)
    for b_, v in (("tail2", -20), ("tail3", -26), ("tail4", -20)):
        c[b_ + ".ry" if b_ == "tail2" else b_ + ".rz"] = c.get(b_ + ".ry" if b_ == "tail2" else b_ + ".rz", 0.0) + v * tail
    return c


ROLL_N, ROLL_LOOP = 150, 70


def back_pose(rig, c, w=1.0):
    """Lying on the back (body space): paws folded up 'in the air' (body-space down), head tipped back toward the
    viewer; the root roll and the settle are added by the clip."""
    k = lk(rig)
    for leg, sx in (("frontL", 1), ("frontR", -1)):
        t = tip(rig, leg)
        c["ik." + leg] = vlerp(c["ik." + leg], V(t.x + 0.004 * k * sx, -0.034 * k, t.z - 0.004 * k), w)
        c[leg + ".pitch"] = lerp(c.get(leg + ".pitch", 0.0), 70, w)
        c["pole." + leg] = V(0.0, 0.6, -1)
    for leg, sx in (("hindL", 1), ("hindR", -1)):
        t = tip(rig, leg)
        c["ik." + leg] = vlerp(c["ik." + leg], V(t.x + 0.022 * k * sx, -0.030 * k, t.z + 0.012 * k), w)
        c[leg + ".pitch"] = lerp(c.get(leg + ".pitch", 0.0), 40, w)
        c["pole." + leg] = V(0.7 * sx, 0.0, 1)


@clip("lions", "roll_over", ROLL_N, False, markers={"onBack": 52, "loopStart": ROLL_LOOP, "loopEnd": ROLL_N},
      info={"loopRange": [ROLL_LOOP, ROLL_N], "loopRangeNote": "frames 70..150 are a seamless loop (frame 150 == frame "
            "70); the clip holds frame 150, or Integration may loop 70..150 for a longer wiggle"},
      notes="the comic high point: from sitting, flops down onto its side and rolls onto its back - belly up, paws "
            "folded in the air, head tipped back toward Daniel with a blissful smile; then wriggles happily on its "
            "back (scratching it on the floor), paws kneading the air, tail wagging; frames 70..150 loop seamlessly")
def lion_roll_over(rig, f, N):
    k = lk(rig)
    sit = lion_idle(rig, 0, 150)
    lie = lion_stand(rig, 0, 60, cycles=1, amp=0.0)
    lie_pose(rig, lie, 1.0, head_down=0.0)
    lie["settle"] = ("root", None, 0.0015, 1.0)
    a = ease_io(f / 22)
    c = mixs(sit, lie, a)
    step_lifts(rig, c, {"frontL": ease_io(f / 12), "frontR": ease_io((f - 5) / 12)})
    roll = ease_io((f - 20) / 28)
    back_w = ease_io((f - 26) / 24)
    if f >= ROLL_LOOP:
        g = (f - ROLL_LOOP)
        M_ = ROLL_N - ROLL_LOOP
        wig = wave(g, M_, 2); wig2 = wave(g, M_, 4, 0.2); kick = wave(g, M_, 2, 0.25)
        on = 1.0
    else:
        wig = wig2 = kick = 0.0; g = 0; M_ = 80
        on = ease_io((f - 52) / 18)
    back_pose(rig, c, back_w)
    c["root.rz"] = 168 * roll + 8 * bump(f, 40, 62) + 8 * wig * on
    c["root.rx"] = -12 * back_w
    # tuck during the roll, then paws knead the air
    tuck = bump(f, 18, 50)
    for leg, sx, ph in (("frontL", 1, 0.0), ("frontR", -1, 0.5), ("hindL", 1, 0.25), ("hindR", -1, 0.75)):
        kn = wave(g, M_, 4, ph) * on
        if leg.startswith("front"):
            c["ik." + leg] = c["ik." + leg] + V(0, 0.010 * k * kn + 0.010 * k * tuck, 0.008 * k * kn - 0.010 * k * tuck)
            c[leg + ".pitch"] += 14 * kn
        else:
            c["ik." + leg] = c["ik." + leg] + V(0.004 * k * kick * sx, 0.012 * k * tuck + 0.008 * k * kn * 0.5, 0.012 * k * tuck)
    # spine wriggle on the back, head tipped back and turned toward the viewer, blissful
    c["spine.rz"] = c.get("spine.rz", 0.0) + 6 * wig2 * on; c["chest.rz"] = c.get("chest.rz", 0.0) - 6 * wig2 * on
    c["spine.ry"] = c.get("spine.ry", 0.0) + 4 * wig * on
    c["neck.rz"] = c.get("neck.rz", 0.0) - 28 * back_w; c["head.rz"] = c.get("head.rz", 0.0) - 34 * back_w + 4 * wig * on
    c["neck.rx"] = c.get("neck.rx", 0.0) - 14 * back_w; c["head.rx"] = c.get("head.rx", 0.0) - 10 * back_w
    c["jaw.rx"] = 6 * back_w + 2 * wig2 * on
    # tail: wags along the floor
    for i, b in enumerate(TAIL):
        c[b + ".ry" if i < 2 else b + ".rz"] = c.get(b + ".ry" if i < 2 else b + ".rz", 0.0) + \
            (14 + 6 * i) * wave(g - 2 * i, M_, 5) * on
    c["eyelids.sy"] = max(1.0, 12.78 * ease_io((f - 44) / 10))
    if f >= ROLL_LOOP:
        peek = bump(g, 46, 60)
        c["eyelids.sy"] = 12.78 - 11.0 * peek
    c["settle"] = [("hips", ("hips", "thighL", "thighR", "tail1"), 0.0015, 1 - a), ("root", None, 0.0015, ease_io((f - 6) / 16))]
    return c


HAND_SPACES = ("handL", "handR", "scroll")
QUAD = {"frontL": ("upperArmL", "forearmL", "pawL"), "frontR": ("upperArmR", "forearmR", "pawR"),
        "hindL": ("thighL", "shinL", "footL"), "hindR": ("thighR", "shinR", "footR")}


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


def ik_quad(rig, basis, M, chs, limb):
    """Lion leg: the paw TIP (tail of pawX / footX) goes exactly to chs['ik.<limb>'] (root space) with the paw bone
    turned by <limb>.pitch (about X, + = tip down / paw curls under) and <limb>.ry; upper + lower bone solve the rest
    by two-bone IK (front elbow bends back, hind knee forward)."""
    up, lo, end = QUAD[limb]
    key = "ik." + limb
    if key not in chs:
        return
    w = chs.get("ikw." + limb, 1.0)
    if w <= 1e-4:
        return
    hind = limb.startswith("hind")
    Mroot = M["root"] @ rig.rest["root"].inverted()
    R3 = Mroot.to_3x3().normalized()
    tip = to_d(Mroot @ to_bl(Vector(chs[key])))
    Rend = R3 @ rot_d((0, 1, 0), chs.get(limb + ".ry", 0.0)) @ rot_d((1, 0, 0), chs.get(limb + ".pitch", 0.0)) @ rig.rest3[end]
    wrist = tip - to_d(Rend @ Vector((0, rig.length[end], 0)))
    pole = Vector(chs.get("pole." + limb, V(0.12 if limb[-1] == "L" else -0.12, 0, 1) if hind else V(0, 0.2, -1)))
    pole = to_d(R3 @ to_bl(pole))
    old = {n: [basis[n][0].copy(), basis[n][1].copy(), basis[n][2]] for n in (up, lo, end)}
    ik2(rig, basis, M, up, lo, wrist, pole, hind)
    rig.set_world_rot(basis, M, end, Rend)
    if w < 0.9999:
        for n in (up, lo, end):
            basis[n][0] = old[n][0].slerp(basis[n][0], w)
        rig.fk(basis, M)


def evaluate_primary(rig, clip_, f):
    chs = clip_.fn(rig, f, clip_.N)
    out = solve_pose(rig, chs)
    st = chs.get("settle")
    if st:
        # settle: move one bone (root / hips) up or down so the lowest proxy vertex of the given bones touches the
        # page (a list = applied in order)
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
    if rig.quad:
        for limb in QUAD:
            ik_quad(rig, basis, M, chs, limb)
        return chs, basis, M
    for limb in ("legL", "legR"):
        ik_limb(rig, basis, M, chs, limb)
    late = []
    for limb in ("armL", "armR"):
        if chs.get("ikspace." + limb, "root") in HAND_SPACES:
            late.append(limb); continue
        ik_limb(rig, basis, M, chs, limb)
    for limb in late:
        ik_limb(rig, basis, M, chs, limb)
    return chs, basis, M


CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "daniel": [(("hair1",), 90.0, 8.0, 0.25, 25.0), (("sash1", "sash2"), 80.0, 7.0, 0.30, 28.0)],
    "king": [(("cape1", "cape2"), 60.0, 6.5, 0.30, 32.0), (("belly",), 170.0, 5.0, 0.0, 10.0)],
    "officer": [(("robe1",), 85.0, 7.0, 0.30, 22.0)],
    "lion": [(("tail1", "tail2", "tail3", "tail4"), 75.0, 6.5, 0.0, 35.0), (("earL",), 230.0, 9.0, 0.0, 12.0),
             (("earR",), 230.0, 9.0, 0.0, 12.0), (("mane",), 130.0, 6.0, 0.0, 14.0)],
    "lion2": [(("tail1", "tail2", "tail3", "tail4"), 75.0, 6.5, 0.0, 35.0), (("earL",), 230.0, 9.0, 0.0, 12.0),
              (("earR",), 230.0, 9.0, 0.0, 12.0)],
}


def sim_chains(rig, prim, loop, rng=None):
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
        pm = act.pose_markers.new(mname); pm.frame = int(mf)
    return act


# =============================================================================================== scene helpers
def fix_stray_eyelid_verts():
    """Workaround (reported to Characters): lion2_eyelids has two vertices left at the back of the head (~0.08 behind
    the eyes), drawing two thin lines through the head whenever it turns. Snap any eyelid vertex that is far from the
    rest of its strip onto its nearest neighbour. No-op once the model is fixed."""
    fixed = []
    for o in bpy.data.objects:
        if o.type != 'MESH' or not o.name.endswith("_eyelids"):
            continue
        vs = o.data.vertices
        cos = [v.co.copy() for v in vs]
        med = Vector([sorted(c[i] for c in cos)[len(cos) // 2] for i in range(3)])
        spread = sorted((c - med).length for c in cos)[int(len(cos) * 0.9)]
        for i, c in enumerate(cos):
            if (c - med).length > max(2.5 * spread, 0.03):
                j = min((k for k in range(len(cos)) if k != i and (cos[k] - med).length <= max(2.5 * spread, 0.03)),
                        key=lambda k: (cos[k] - c).length)
                vs[i].co = cos[j]
                fixed.append((o.name, i))
    if fixed:
        print("DA_FIX stray eyelid vertices snapped:", fixed)
    return fixed


def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    fix_stray_eyelid_verts()
    sc = bpy.context.scene
    sc.render.fps = FPS
    rigs = {ch: Rig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    return sc, rigs


def contract_clips():
    lion = ["idle", "sleep", "wake_up", "roar", "growl", "prowl", "yawn", "lie_down", "roll_over", "walk"]
    return {"daniel": ["idle", "walk", "talk", "bow", "kneel_pray", "stand_up", "calm_nod", "pet_lion", "wave_up", "hug",
                       "wave"],
            "king": ["idle", "walk_sad", "talk", "talk_happy", "proud", "stamp", "worried", "pace", "head_in_hands",
                     "reach_out", "toss_sigh", "run", "call_out", "joy_jump", "hug", "proclaim"],
            "officer": ["idle", "walk", "talk", "fold_arms", "stomp_walk", "grumble", "sly_idea", "rub_hands",
                        "bow_flatter", "tiptoe", "peek", "point", "scared_jump", "run_away"],
            "lion": lion, "lion2": list(lion)}


def timeline_clips():
    return sorted({(a["who"], a["clip"]) for a in TL["acting"]})


def travel_needs():
    """Per locomotion move in the timeline: distance, time until the actor's next clip, needed speed."""
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


PROPS = ("scroll", "ring")


def hidden_props(rig, cl):
    """Prop meshes not posed for in this clip (left out of the checks and the renders). The ring is always shown."""
    out = []
    nm = f"{rig.ch}_scroll"
    if nm in bpy.data.objects and "scroll" not in cl.props:
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
    if cl.ch == "king" and cl.name == "toss_sigh":
        # the dais behind him (KING mark): steps at z_rel < -0.055 (0.013), < -0.065 (0.027), < -0.088 (0.040)
        front, seat = [], []
        for fr in range(0, cl.N + 1, 10):
            apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
            for q, _ in mesh_points(rig, skip_props=skip):
                if q.z > -0.055:
                    front.append(q.y)
                elif -0.088 < q.z < -0.065:
                    seat.append((fr, q.y))
        out["meshMinYInFrontOfDais"] = round(min(front), 4)
        s0 = [y for fr, y in seat if fr in (0, 30, 170, 180)]
        out["seatLowestY (step top 0.027)"] = round(min(s0), 4) if s0 else None
        out["note"] = "robe / cape below the step tops are inside the dais (hidden); only the front of the dais counts"
    if min(lows) < -0.004:
        out["meshMinAt"] = low_at
    tips = ([("pawL", "tail"), ("pawR", "tail"), ("footL", "tail"), ("footR", "tail")] if rig.quad
            else [("toeL", "head"), ("toeR", "head")])
    if cl.speed is None:
        drift = 0.0
        for bn, at in tips:
            ref = None
            for basis, M in frames:
                p = rig.pos(M, bn, at)
                if p.y < 0.012 and (rig.quad or rig.pos(M, "foot" + bn[-1]).y < 0.03):
                    if ref is None:
                        ref = p
                    drift = max(drift, math.hypot(p.x - ref.x, p.z - ref.z))
                else:
                    ref = None
        out["plantedDriftMax"] = round(drift, 4)
    else:
        out["naturalSpeed"] = round(cl.natural_speed, 4)
        # stance check: a planted foot / paw must slide back at exactly the natural speed (then it is still on the page
        # while the director moves the actor forward at that speed)
        v = cl.natural_speed / FPS
        err = 0.0

        def cpts(M, bn, at):
            if rig.quad:
                return [rig.pos(M, bn, at)]
            side = bn[-1]
            fm = M["foot" + side] @ rig.rest_inv["foot" + side]
            a = rig.head["foot" + side]
            return [to_d(fm @ to_bl(a + q)) for q in foot_points(rig, side)]
        for bn, at in tips:
            for fr in range(cl.N):
                q0, q1 = cpts(frames[fr][1], bn, at), cpts(frames[fr + 1][1], bn, at)
                i = min(range(len(q0)), key=lambda j: q0[j].y)
                p0, p1 = q0[i], q1[i]
                thr = (rig.tail[bn].y + 0.0012) if rig.quad else 0.0015
                if p0.y < thr and p1.y < thr:
                    err = max(err, math.hypot(p1.x - p0.x, (p1.z - p0.z) + v) * FPS)
        out["stanceSlipMax"] = round(err, 4)        # u/s; 0 = feet glued to the page in world space
    reset_pose(rig)
    rig.obj.location, rig.obj.rotation_euler = loc0, rot0
    if ad:
        ad.action = keep
    return out


SAMPLE_BONES = ("head", "jaw", "handR", "handL", "footL", "toeR", "hips", "hair1", "sash2", "cape2", "belly",
                "robe1", "scroll", "pawL", "pawR", "tail4", "mane", "earL")


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    req = TL.get("requestedClips") or []
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl, "requestedClips": req,
            "stage": {"hugDistance": HUG_D, "petLion": {"maneAhead": PET_D, "maneHeight": PET_Y},
                      "stampAt": list(STAMP_AT), "kingSeat": list(SEAT), "kneel": KNEEL["daniel"]},
            "travel": travel_needs(),
            "propsNote": "officer/scroll is posed for in the clips whose `props` list it; king/ring is always shown"}
    only = os.environ.get("DA_ONLY")
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
                "props": cl.props, "notes": cl.notes}
        if cl.extra:
            info["extra"] = True
        if cl.speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            info["stride"] = cl.speed[0]
        info.update(cl.info)
        if cl.loop:
            # continuity across the seam: the step N-1 -> N (= 0) against the largest step inside the clip
            def step(a_, b_):
                return max((rig.pos(frames[a_][1], n, "tail") - rig.pos(frames[b_][1], n, "tail")).length
                           for n in rig.names if n != "eyelids")
            inner = max(step(f_, f_ + 1) for f_ in range(cl.N - 1))
            info["seamStep"] = round(step(cl.N - 1, cl.N), 5); info["maxStep"] = round(inner, 5)
        if "loopRange" in cl.info:
            a_, b_ = cl.info["loopRange"]
            info["loopRangeSeamErr"] = round(max((rig.pos(frames[a_][1], n, "tail") - rig.pos(frames[b_][1], n, "tail")).length
                                                 for n in rig.names), 6)
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        print("DA_CHECK", cl.action, json.dumps(info["checks"]), "seam", info.get("seamStep"), "/", info.get("maxStep"),
              info.get("loopRangeSeamErr", ""))
        meta["clips"].append(info)
        print(f"DA_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} root={info['rootMaxOffset']}")
    if only:
        print("DA_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "da_anim.blend")
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
        print("DA_EXPORT", ch)
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("DA_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


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
            print(f"DA_VERIFY {ch} {nm} {a['frames']}f {a['seconds']}s ch={a['channels']} sampleErr={out['sampleErr'][ch].get(nm)}")
        g = out["glb"][ch]
        print(f"DA_VERIFY_GLB {ch} bytes={g['bytes']} skins={g['skins']} meshes={g['meshes']} "
              f"uv0InUnitSquare={g['uv0InUnitSquare']} uv={json.dumps(g['uv'])}")
        print(f"DA_VERIFY_NODES {ch} {[n for n in g['nodes'] if n and n.split('_')[-1] in PROPS + ('eyelids',) or n in PROPS]}")
    print("DA_VERIFY_MISSING", json.dumps(out["contractMissing"]))


# ----------------------------------------------------------------------------------------------- render helpers
REGIONS = json.load(open(REGIONS_JSON))
FACES = {ch: {"default": v["faceDecal"]["default"], "clips": v["faceDecal"].get("clipExpression", {})}
         for ch, v in REGIONS["characters"].items()}
FACE_OVERRIDE = {("lion", "sleep"): "sleepy", ("lion", "idle"): "curious"}
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
    if stage and os.path.exists(SET_GLB) and os.environ.get("DA_NOSET") != "1":
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=SET_GLB)
        new = [o for o in bpy.data.objects if o not in before]
        pm = bpy.data.materials.new("anim_set"); pm.use_nodes = True
        b2 = pm.node_tree.nodes.get("Principled BSDF"); b2.inputs["Roughness"].default_value = 0.9
        b2.inputs["Base Color"].default_value = (0.80, 0.70, 0.52, 1)
        hide = {"canopy", "dropped"}
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


def show_only(rigs, chs, cl_of=None):
    for ch, r in rigs.items():
        vis = ch in chs
        r.obj.hide_render = not vis
        hid = hidden_props(r, cl_of[ch]) if (cl_of and ch in cl_of) else []
        for o in r.obj.children:
            o.hide_render = (not vis) or (o.name in hid)


def stage_of(cl):
    """Where a clip is shown in renders: (x, z, yaw). Open courtyard in front of the palace; toss_sigh at KING."""
    if cl.ch == "king" and cl.name == "toss_sigh":
        return (0.0, -0.30, 0.0)
    return {"daniel": (-0.14, 0.06, 0.0), "king": (0.02, 0.04, 0.0), "officer": (0.04, 0.10, 0.0),
            "lion": (0.10, 0.10, 0.0), "lion2": (0.10, 0.10, 0.0)}[cl.ch]


def view_cam(cam, rig, mark, view, bone=None, dist_k=2.3, H=None):
    x, z, yaw0 = mark
    H = H or rig.H
    yaw = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "top": 25, "low": 25}[view] + yaw0
    tgt = V(x, H * 0.45, z); dist = H * dist_k; hgt = H * 0.60
    if bone:
        tgt = to_d(rig.obj.matrix_world @ rig.obj.pose.bones[bone].head); dist = H * 0.9; hgt = tgt.y + 0.02
    if view == "top":
        hgt = dist * 1.3
    if view == "low":
        hgt = 0.02
    a_ = math.radians(yaw)
    look(cam, tgt, V(tgt.x + math.sin(a_) * dist, hgt, tgt.z + math.cos(a_) * dist))


PAIRS = [  # contact-sheet pair rows: (A action, B action, distance (None = pet: mane 0.12 ahead), label)
    ("king_hug", "daniel_hug", HUG_D, f"pair: king_hug + daniel_hug ({HUG_D})"),
    ("daniel_pet_lion", "lion_roll_over", None, "pair: daniel_pet_lion + lion_roll_over (mane 0.12 ahead)"),
]


def pet_distance(rig_lion, frames):
    """Root distance so the rolled-over lion's mane (head joint) is PET_D in front of Daniel (lion facing him)."""
    M = frames[-1][1]
    return PET_D + rig_lion.pos(M, "head").z


def place_pair(rigs, ra, rb, dist, cx=-0.10, cz=0.08):
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
        show_only(rigs, [cl.ch], {cl.ch: cl})
        set_expression(cl.ch, cl.name)
        frames = bake_clip(rig, cl); baked[cl.action] = frames
        mk = sorted(set(cl.markers.values()))
        picks = sorted(set([0, cl.N] + [int(round(cl.N * k / 5)) for k in range(1, 5)] + mk))
        while len(picks) > 7:
            cand = [p for p in picks if p not in mk and p not in (0, cl.N)] or [p for p in picks if p not in (0, cl.N)]
            picks.remove(cand[len(cand) // 2])
        mark = stage_of(cl)
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": [], "extra": cl.extra}
        for fr in picks:
            apply_basis(rig, frames[fr][0])
            place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, "q3", dist_k=1.5 if rig.quad else 1.2)
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("DA_CONTACT_ROW", cl.action, picks, flush=True)
    for a, b, dist, label in PAIRS:
        ca, cb = clips[a], clips[b]
        ra, rb = rigs[ca.ch], rigs[cb.ch]
        show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
        set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
        row = {"action": label, "loop": ca.loop, "frames_total": ca.N, "frames": []}
        if dist is None:
            dist = pet_distance(rb, baked[b])
            row["action"] += f" d={dist:.3f}"
        n = ca.N
        for i, fr in enumerate([0, n // 3, n - 6 if not ca.loop else n // 2]):
            fb = cb.N if (ca.loop and not cb.loop) else min(fr, cb.N)
            apply_basis(ra, baked[a][fr][0]); apply_basis(rb, baked[b][fb][0])
            place_pair(rigs, ra, rb, dist)
            bpy.context.view_layer.update()
            for vn, cpos in (("front", V(-0.10, 0.20, 0.08 + 0.55)), ("q3", V(-0.10 + 0.40, 0.30, 0.08 + 0.40)),
                             ("top", V(-0.10, 0.62, 0.08 + 0.22))):
                if i > 0 and vn == "top":
                    continue
                look(cam, V(-0.10, 0.17, 0.08), cpos, lens=45)
                fn = f"pair_{a}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                row["frames"].append({"f": fr, "file": fn, "marker": vn})
        reset_pose(ra); reset_pose(rb)
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """DA_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'pair:<actionA>:<actionB>:<dist>:<frame>[:view]' renders two actors facing each other at that distance."""
    sc, rigs = open_scene()
    res = int(os.environ.get("DA_PROBE_RES", "440"))
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
    for item in os.environ.get("DA_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "pair":
            a, b, fr = parts[1], parts[2], int(parts[4])
            dist = pet_distance(rigs[clips[b].ch], bk(b)) if parts[3] == "pet" else float(parts[3])
            views = parts[5].split(",") if len(parts) > 5 else ["front", "q3", "top", "back"]
            ca, cb = clips[a], clips[b]
            ra, rb = rigs[ca.ch], rigs[cb.ch]
            show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
            set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
            fb = cb.N if (ca.loop and not cb.loop) else min(fr, cb.N)
            apply_basis(ra, bk(a)[min(fr, ca.N)][0]); apply_basis(rb, bk(b)[fb][0])
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
            apply_basis(rig, fr_[fr][0]); place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, view, bone, dist_k=float(os.environ.get("DA_PROBE_DIST", "1.25")))
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("DA_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("DA_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
