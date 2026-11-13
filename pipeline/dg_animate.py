"""David & Goliath skeletal animation (Animation role).

Two halves in one file:

* Under Blender (headless) it opens `assets/david-goliath/model/dg_characters.blend` (Blender role's rigs), builds every
  clip of CONTRACT §5 (+ timeline.json requestedClips) as an action named `<char>_<clip>`, and exports
  `assets/david-goliath/anim/{david,goliath}.glb` (character + skin + one glTF animation per action).
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet / preview MP4 (Pillow + ffmpeg).

    python3 pipeline/dg_animate.py all        # build + verify + contact sheet + preview.mp4 (~several minutes)
    python3 pipeline/dg_animate.py build      # actions + GLBs + anim/clips.json
    python3 pipeline/dg_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build
    python3 pipeline/dg_animate.py contact    # anim/contact_sheet.png (key poses per clip)
    python3 pipeline/dg_animate.py preview    # anim/preview.mp4 (timeline.json performance, low res, + audio)
    DG_PROBE="david_kneel_pick:34,46:q3@-0.32,0.2#handR" python3 pipeline/dg_animate.py probe   # work renders

How the motion is made (no hand-placed Blender keys; the script is the source):
  * Each clip is a function frame -> channels. Channels are rotations in DESIGN axes (x right, y up, z toward the viewer)
    applied in the bone's rest frame and carried by its parent: `rx ry rz` (generic), `bend` (hinge about rest_dir x Z,
    + = tip forward), `raise` (+ = tip up, for side bones), `swing` (+ = tip forward about vertical), `twist`, and
    `tx ty tz` (design offsets), `s` (uniform scale). Keyed values are Catmull-Rom splines (`K`), wrapped for loops.
  * Legs (and some arms) use an analytic two-bone IK whose targets are channels; feet keep a ground contact by pivoting
    on heel / ball / toe, so a dropped hip bends the knees (weight) and steps plant.
  * Secondary motion is simulated, not keyed: the sling is a 3-segment Verlet chain hanging from the hand (except while
    it is being whirled), Goliath's spear lags the hand with a damped spring. Loops simulate 3 cycles and keep the last,
    so they close seamlessly.
  * Everything is sampled at 30 fps and written as one key per frame (quaternion + location + scale) per bone.
Character scale for physics: David is 0.30 units ~ 1.5 m, so g = 9.8 / 5 ~ 2.0 units/s^2.
Intermediates go to $DG_ANIM_WORK (default $DG_WORK/anim, DG_WORK default /tmp/dg_work).
Rig: CONTRACT §11 (45 deg rest, fists modelled closed, six finger bones); finger channel `curl` (+ = toward the palm).
Renders (contact sheet, preview, probe) use EEVEE with the desert set, the face decals on UV1 and the textures of
prepare_textures() (v3 demo colouring, lines erased, sand page; see ANIMATION.md).
"""
import json, math, os, subprocess, sys, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
DG = os.path.join(ROOT, "assets/david-goliath")
MODEL = os.path.join(DG, "model")
ANIM = os.path.join(DG, "anim")
BLEND = os.path.join(MODEL, "dg_characters.blend")
TIMELINE = os.path.join(DG, "timeline.json")
DESERT_GLB = os.path.join(MODEL, "desert.glb")
WORK = os.environ.get("DG_ANIM_WORK") or os.path.join(os.environ.get("DG_WORK", "/tmp/dg_work"), "anim")
FPS = 30
CHARS = ("david", "goliath")
G = 2.0                                   # gravity in art-width units / s^2 (see docstring)

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


# =============================================================================================== orchestration (python3)
def run_blender(mode, *extra):
    cmd = ["blender", "-b", "--factory-startup", "--python", os.path.abspath(__file__), "--", mode, *extra]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith(("DG_", "Traceback", "Error", "  File")) or "Error" in ln]
    print("\n".join(tail[-150:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def compose_contact():
    from PIL import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(WORK, "contact", "contact.json")))
    cell, pad, lab = 220, 6, 34
    rows = meta["rows"]
    ncol = max(len(r["frames"]) for r in rows)
    W = 210 + ncol * (cell + pad) + pad
    H = 60 + len(rows) * (cell + lab + pad)
    sheet = Image.new("RGB", (W, H), (250, 246, 236))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((pad, 14), "David & Goliath - key poses per clip (30 fps; frame / seconds; marker names in red)", fill=(40, 30, 20), font=font)
    y = 60
    for r in rows:
        d.text((pad, y + 6), r["action"], fill=(40, 30, 20), font=font)
        d.text((pad, y + 30), f"{r['frames_total']} f  {r['frames_total'] / FPS:.2f} s", fill=(90, 80, 70), font=small)
        d.text((pad, y + 50), "loop" if r["loop"] else "one-shot", fill=(90, 80, 70), font=small)
        x = 210
        for fr in r["frames"]:
            im = Image.open(os.path.join(WORK, "contact", fr["file"])).convert("RGB").resize((cell, cell))
            sheet.paste(im, (x, y))
            txt = f"f{fr['f']}  {fr['f'] / FPS:.2f}s"
            d.text((x + 4, y + cell + 2), txt, fill=(60, 50, 40), font=small)
            if fr.get("marker"):
                d.text((x + 4, y + cell + 17), fr["marker"], fill=(200, 30, 30), font=small)
            x += cell + pad
        y += cell + lab + pad
    out = os.path.join(ANIM, "contact_sheet.png")
    sheet.save(out, optimize=True)
    print("DG_CONTACT", out, sheet.size)


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get("DG_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("DG_PROBE_OUT", "probe.png"))
    sheet.save(out); print("DG_PROBE_SHEET", out)


def compose_preview():
    frames = os.path.join(WORK, "preview", "f_%04d.png")
    tmp = os.path.join(WORK, "preview_video.mp4")
    tl = json.load(open(TIMELINE))
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-framerate", str(FPS), "-i", frames, "-c:v", "libx264", "-pix_fmt",
                    "yuv420p", "-crf", "26", "-preset", "medium", tmp], check=True)
    out = os.path.join(ANIM, "preview.mp4")
    mix = os.path.join(DG, "audio", "preview_mix.mp3")
    if os.path.exists(mix):
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", tmp, "-i", mix, "-map", "0:v", "-map", "1:a", "-c:v", "copy",
                        "-c:a", "aac", "-b:a", "96k", "-t", str(tl["duration"]), out], check=True)
    else:
        shutil.copy(tmp, out)
    print("DG_PREVIEW", out, "audio" if os.path.exists(mix) else "no audio")


DESIGN_DIR = os.path.join(ROOT, "docs/david-goliath/design")


def prepare_textures():
    """Render textures (CONTRACT §12.4 look, approximated): $WORK/tex_chars.png and $WORK/tex_desert.png, both in the
    A4 page frame (1240 x 1754). Source: the Sheet role's demo sheet when it is newer than design.json (v3), else
    Design's v3 demo-colour mock. Printed lines are erased (filled from their neighbours, like the app); for the desert
    the unpainted paper is lerped to sand #F3D58E (DGPaperLit _BaseColor). The page itself wears Design's baked sand
    ground (design/ground-sand-demo.png). Characters keep $DG_WORK/uvproof.png when DG_CHAR_TEXTURE=uvproof."""
    import numpy as np
    from PIL import Image
    D = json.load(open(os.path.join(DG, "design.json")))
    Wp, Hp = D["sheet"]["page"]; art = D["sheet"]["art"]
    sheet_demo = os.path.join(DG, "sheet", "demo-colored.png")
    lineart = os.path.join(DESIGN_DIR, "sheet-mock-lineart.png")
    if os.path.exists(sheet_demo) and os.path.getmtime(sheet_demo) > os.path.getmtime(os.path.join(DG, "design.json")):
        # Sheet role's demo is the art rectangle only: paste it into a sand page so both textures share one frame
        src = Image.open(sheet_demo).convert("RGB").resize((art[2], art[3]), Image.LANCZOS)
        page = Image.new("RGB", (Wp, Hp), (0xF3, 0xD5, 0x8E)); page.paste(src, (art[0], art[1]))
        la = os.path.join(DG, "sheet", "lineart.png")
        ink = None
        if os.path.exists(la):
            li = Image.open(la).convert("L").resize((art[2], art[3]), Image.NEAREST)
            ink = np.zeros((Hp, Wp), bool); ink[art[1]:art[1] + art[3], art[0]:art[0] + art[2]] = np.asarray(li) < 153
        used = "sheet/demo-colored.png"
    else:
        page = Image.open(os.path.join(DESIGN_DIR, "sheet-mock-demo-colour.png")).convert("RGB")
        ink = np.asarray(Image.open(lineart).convert("RGB")).max(2) < 153 if os.path.exists(lineart) else None
        used = "design/sheet-mock-demo-colour.png"
    a = np.asarray(page).astype(np.float32) / 255.0
    if ink is None:
        ink = a.max(2) < 0.62
    ink = ink | np.roll(ink, 1, 0) | np.roll(ink, -1, 0) | np.roll(ink, 1, 1) | np.roll(ink, -1, 1)
    rgb = a.copy(); known = ~ink
    for _ in range(8):
        acc = np.zeros_like(rgb); cnt = np.zeros(rgb.shape[:2] + (1,), np.float32)
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (-1, -1), (1, -1), (-1, 1)):
            acc += np.roll(np.roll(rgb * known[..., None], dy, 0), dx, 1)
            cnt += np.roll(np.roll(known, dy, 0), dx, 1)[..., None]
        fill = (~known) & (cnt[..., 0] > 0)
        rgb[fill] = acc[fill] / cnt[fill]
        known = known | fill
    Image.fromarray((rgb * 255).astype(np.uint8)).save(os.path.join(WORK, "tex_chars.png"))
    sand = np.array([0xF3, 0xD5, 0x8E], np.float32) / 255.0
    t = np.clip((rgb.min(2) - 0.60) / 0.26, 0, 1); paper = (t * t * (3 - 2 * t))[..., None]
    Image.fromarray(((rgb * (1 - paper) + sand * paper) * 255).astype(np.uint8)).save(os.path.join(WORK, "tex_desert.png"))
    json.dump({"source": used}, open(os.path.join(WORK, "tex_source.json"), "w"))
    print("DG_TEXTURES from", used)


def main_cli():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(WORK, exist_ok=True); os.makedirs(ANIM, exist_ok=True)
    if mode in ("contact", "preview", "probe", "all"):
        prepare_textures()
    if mode in ("build", "all"):
        run_blender("build")
    if mode in ("verify", "all"):
        run_blender("verify")
    if mode in ("contact", "all"):
        run_blender("contact"); compose_contact()
    if mode in ("preview", "all"):
        run_blender("preview"); compose_preview()
    if mode == "probe":
        run_blender("probe"); compose_probe()
    if mode == "compose":
        compose_contact(); compose_preview()


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
            m1 = (p2 - p0) / (f2 - f0) * dt if f2 != f0 else 0.0     # non-uniform Catmull-Rom tangents
            m2 = (p3 - p1) / (f3 - f1) * dt if f3 != f1 else 0.0
            t2, t3 = t * t, t * t * t
            return (2 * t3 - 3 * t2 + 1) * p1 + (t3 - 2 * t2 + t) * m1 + (-2 * t3 + 3 * t2) * p2 + (t3 - t2) * m2
    return ks[-1][1]


def KK(spec, f, N=None, loop=False):
    """spec: {channel: [(frame, value)...]} -> {channel: value}"""
    return {ch: K(keys, f, N, loop) for ch, keys in spec.items()}


def wave(f, N, cycles=1.0, phase=0.0):
    return math.sin(2 * math.pi * (cycles * f / N + phase))


def add(d, ch, v):
    d[ch] = d.get(ch, 0.0) + v


# =============================================================================================== rig model (pure python FK)
class Rig:
    def __init__(self, ch, obj):
        self.ch, self.obj = ch, obj
        self.names = []
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
        self.H = {"david": 0.30, "goliath": 0.80}[ch]

    # channels -> basis (quat, loc, scale)
    def basis_from(self, chs):
        out = {}
        for n in self.names:
            g = lambda k: chs.get(f"{n}.{k}", 0.0)
            d = self.dir[n]
            R = Matrix.Identity(3)
            sx = 1.0 if d.x >= 0 else -1.0
            # generic (outermost) . swing . raise . bend . twist (innermost)
            if g("rx"): R = R @ rot_d((1, 0, 0), g("rx"))
            if g("ry"): R = R @ rot_d((0, 1, 0), g("ry"))
            if g("rz"): R = R @ rot_d((0, 0, 1), g("rz"))
            if g("swing"): R = R @ rot_d((0, -sx, 0), g("swing"))
            if g("raise"): R = R @ rot_d((0, 0, sx), g("raise"))
            if g("curl") and n[:-1] in ("fingers", "fingerTips", "thumb"):
                dh = self.dir["hand" + n[-1]]
                hz = dh.cross(V(0, 0, 1)).normalized()
                R = R @ rot_d(hz if n[-1] == "L" else -hz, g("curl"))      # + = curl toward the palm (§11.6 fists)
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
            out[n] = [q, loc, s]
        return out

    def fk(self, basis, M=None, only=None):
        M = {} if M is None else M
        names = self.names if only is None else [n for n in self.names if n in only]
        for n in names:
            q, loc, s = basis[n]
            B = Matrix.Translation(loc) @ q.to_matrix().to_4x4() @ Matrix.Diagonal((s, s, s, 1.0))
            p = self.parent[n]
            M[n] = (M[p] @ self.rel[n] @ B) if p else (self.rel[n] @ B)
        return M

    def subtree(self, n):
        out, st = set(), [n]
        while st:
            x = st.pop(); out.add(x); st += self.children[x]
        return out

    def carried(self, M, n):
        """Armature-space matrix bone n would have with identity basis (parent posed)."""
        p = self.parent[n]
        return (M[p] @ self.rel[n]) if p else self.rel[n].copy()

    def set_world_rot(self, basis, M, n, R_world3):
        """Set basis rotation of n so its armature-space rotation equals R_world3 (Blender coords)."""
        Cm = self.carried(M, n).to_3x3().normalized()
        basis[n][0] = (Cm.inverted() @ R_world3).to_quaternion()
        self.fk(basis, M, only=self.subtree(n))

    def pos(self, M, n, at="head"):
        m = M[n]
        if at == "head":
            return to_d(m.translation)
        return to_d(m @ Vector((0, self.length[n], 0)))


def frame_from(Y_d, Z_d):
    """Blender 3x3 with local Y along Y_d and local Z toward Z_d (both design vectors)."""
    Y = (C @ Y_d).normalized()
    Z = (C @ Z_d)
    Z = (Z - Y * Z.dot(Y)).normalized()
    X = Y.cross(Z)
    return Matrix((X, Y, Z)).transposed()


def ik2(rig, basis, M, upper, lower, target_d, pole_d, legs):
    """Two-bone IK. legs: the joint (knee) points along the pole and the lower bone folds back (-Z);
    arms: the elbow points along the pole and the forearm folds forward (+Z)."""
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
    s = -1.0 if legs else 1.0
    # upper frame: Y along H->K, Z forward-ish (legs: along the pole; arms: opposite the pole)
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
    def __init__(self, ch, name, N, loop, fn, markers=None, root_motion=False, ik=None, notes=""):
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = markers or {}
        self.root_motion = root_motion
        self.ik = ik or {}
        self.notes = notes

    @property
    def action(self):
        return f"{self.ch}_{self.name}"


CLIPS = []


def clip(ch, name, N, loop, **kw):
    def deco(fn):
        CLIPS.append(Clip(ch, name, N, loop, fn, **kw)); return fn
    return deco


# ----------------------------------------------------------------------------------------------- shared helpers
def foot_points(rig, side):
    """Ankle-relative contact points (heel, ball, toe tip) in design space, rest pose."""
    a = rig.head["foot" + side]
    ball = rig.head["toe" + side] - a
    tip = rig.tail["toe" + side] - a
    heel = V(0, -a.y + 0.0, -0.18 * (ball.z))
    heel.y = -a.y + 0.001 * rig.H / 0.3
    return heel, ball, tip


def planted_ankle_y(rig, side, pitch_deg):
    """Ankle height that keeps the lowest of heel/ball/toe on the ground for a foot pitch (+ = toe down)."""
    R = rot_d((1, 0, 0), pitch_deg)
    low = min((CI @ (R @ (C @ p))).y for p in foot_points(rig, side))
    return -low


def gait(rig, f, N, L, lift, duty, offsetR=0.5, offsetL=0.0, heel=12.0, toeoff=30.0, out=None, lift_shape=1.0):
    """In-place gait. Returns per side ankle targets (design, root space) and foot pitch.
    Stance: the foot slides from +L/2 to -L/2 at constant speed (speed = L / (duty * N / FPS)); swing: eased return with lift."""
    out = out if out is not None else {}
    for side, off in (("L", offsetL), ("R", offsetR)):
        p = (f / N + off) % 1.0
        base = rig.head["foot" + side]
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
        out["leg" + side] = (V(base.x, y, base.z + z), pitch, contact, p)
    return out


def legs_ik_channels(chs, g):
    for side in "LR":
        t, pitch, _, _ = g["leg" + side]
        chs[f"ik.leg{side}"] = t
        chs[f"foot{side}.pitch"] = pitch


def stand_feet(rig, chs, spread=0.0, fwdL=0.0, fwdR=0.0, pitchL=0.0, pitchR=0.0, liftL=0.0, liftR=0.0):
    for side, fw, pt, lf in (("L", fwdL, pitchL, liftL), ("R", fwdR, pitchR, liftR)):
        b = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        chs[f"ik.leg{side}"] = V(b.x + sx * spread, planted_ankle_y(rig, side, pt) + lf, b.z + fw)
        chs[f"foot{side}.pitch"] = pt


def fist(c, side, open_=0.0, thumb=0.0):
    """Hands modelled as fists (David R, Goliath L/R): open_ 0 = closed grip (rest), 1 = fingers straight."""
    c[f"fingers{side}.curl"] = -18 * open_
    c[f"fingerTips{side}.curl"] = -95 * open_
    c[f"thumb{side}.curl"] = -25 * max(open_, thumb)


def open_hand(c, side, curl=0.0, tips=None, thumb=0.0):
    """Hand modelled open (David L): curl 0 = straight (rest), 60-90 = loose to closed fist."""
    c[f"fingers{side}.curl"] = curl
    c[f"fingerTips{side}.curl"] = curl * 1.1 if tips is None else tips
    c[f"thumb{side}.curl"] = thumb


# =============================================================================================== DAVID
# Rest (§11.4): arms 45 deg below horizontal, right fist round the sling cords, left hand open (fingers together).
# raise -46 = arms relaxed by the side. Fingers: `fist()` for the right hand (closed at rest), `open_hand()` for the left.
def kneel_mark():
    """Where David kneels: the last `to` of David before his kneel_pick entry in timeline.json (CONTRACT §11.11)."""
    acts = sorted(TL["acting"], key=lambda a: a["t"])
    t_k = next(a["t"] for a in acts if a["who"] == "david" and a["clip"] == "kneel_pick")
    tos = [a["to"] for a in acts if a["who"] == "david" and "to" in a and a["t"] < t_k]
    return tos[-1] if tos else (-0.32, 0.20)


_STONES = None


def brook_stones_local():
    """Centres (design x, y, z) of desert.glb stone1..5 in David-local coordinates at the kneel mark (facing +Z)."""
    global _STONES
    if _STONES is None:
        import struct
        b = open(DESERT_GLB, "rb").read(); l0 = struct.unpack_from("<I", b, 12)[0]; j = json.loads(b[20:20 + l0])
        mx, mz = kneel_mark()
        out = []
        for k in range(1, 6):
            nd = next(n for n in j["nodes"] if n["name"] == f"stone{k}")
            acc = j["accessors"][j["meshes"][nd["mesh"]]["primitives"][0]["attributes"]["POSITION"]]
            c = [(a + b_) / 2 for a, b_ in zip(acc["min"], acc["max"])]
            t = nd.get("translation", [0, 0, 0])
            out.append(V(c[0] + t[0] - mx, acc["max"][1] + t[1], c[2] + t[2] - mz))
        _STONES = out
    return _STONES


def david_base(rig, f, N, loop=True, breath_cycles=1):
    c = {}
    b = wave(f, N, breath_cycles)
    c["chest.rx"] = -1.5 * b
    c["shoulderL.raise"] = 1.2 * b; c["shoulderR.raise"] = 1.2 * b
    c["upperArmL.raise"] = -44; c["upperArmR.raise"] = -36
    c["upperArmL.bend"] = 4; c["upperArmR.bend"] = 6
    c["forearmL.bend"] = 16; c["forearmR.bend"] = 18
    c["handL.bend"] = 6; c["handR.bend"] = 4
    open_hand(c, "L", curl=18, tips=24, thumb=4)          # relaxed open hand, fingers slightly curled
    return c


@clip("david", "idle", 60, True, notes="breathing, weight shift L<->R, looks around; sling hangs and sways; left hand relaxed")
def david_idle(rig, f, N):
    c = david_base(rig, f, N)
    sh = wave(f, N, 1, 0.25)
    c["hips.tx"] = 0.004 * sh; c["hips.ty"] = -0.0015 - 0.001 * abs(sh)
    c["hips.rz"] = -2.0 * sh; c["spine.rz"] = 1.2 * sh; c["chest.rz"] = 1.0 * sh
    c["head.ry"] = 6 * wave(f, N, 1, 0.1); c["head.rx"] = 2 * wave(f, N, 2, 0.3)
    c["neck.rz"] = -1.0 * sh
    c["upperArmR.bend"] += 3 * wave(f, N, 1, 0.35)
    c["fingersL.curl"] += 6 * wave(f, N, 1, 0.6)
    stand_feet(rig, c, spread=0.002)
    return c


@clip("david", "walk", 24, True, markers={"contactL": 0, "contactR": 12},
      notes="light quick in-place walk; stride 0.06 per cycle")
def david_walk(rig, f, N):
    c = david_base(rig, f, N, breath_cycles=1)
    g = gait(rig, f, N, L=0.060, lift=0.016, duty=0.58, heel=14, toeoff=28)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.004 + 0.004 * math.cos(2 * ph)            # high at passing, low at contact
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -9 * math.sin(ph - 0.3); c["head.ry"] = 4 * math.sin(ph - 0.5)
    c["hips.rz"] = 3 * math.cos(ph); c["chest.rz"] = -2 * math.cos(ph - 0.4)
    c["spine.rx"] = 4; c["head.rx"] = -3 + 1.5 * math.cos(2 * ph - 0.6)
    # arms swing opposite the legs, forearm lags (overlap)
    c["upperArmL.bend"] = 4 - 24 * math.sin(ph - 0.25); c["upperArmR.bend"] = 6 + 24 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 22 - 10 * math.sin(ph - 0.9); c["forearmR.bend"] = 24 + 10 * math.sin(ph - 0.9)
    open_hand(c, "L", curl=26 + 6 * math.sin(ph - 1.2), tips=30, thumb=6)
    return c


@clip("david", "talk", 36, True, notes="jaw flap ~4 syllables/s, open left hand gesture (fingers spread on the beats), head nods")
def david_talk(rig, f, N):
    c = david_base(rig, f, N, breath_cycles=1)
    jaw = [(0, 0), (3, 16), (6, 3), (9, 13), (12, 2), (15, 18), (18, 4), (21, 11), (24, 1), (27, 15), (30, 3), (33, 9), (36, 0)]
    c["jaw.rx"] = max(0.0, K(jaw, f, N, True))
    c["head.rx"] = 3 * wave(f, N, 2, 0.1); c["head.ry"] = 5 * wave(f, N, 1); c["head.rz"] = 2 * wave(f, N, 1, 0.3)
    # left hand: open palm gesture, beats on the stressed syllables
    beat = K([(0, 0), (6, 1), (14, 0.4), (20, 1), (30, 0.3), (36, 0)], f, N, True)
    c["upperArmL.raise"] = -36 + 6 * beat; c["upperArmL.bend"] = 26 + 8 * beat
    c["forearmL.bend"] = 62 + 12 * beat; c["forearmL.twist"] = -40; c["handL.bend"] = -10 * beat
    open_hand(c, "L", curl=22 - 18 * beat, tips=26 - 22 * beat, thumb=-10 * beat)
    c["chest.ry"] = 4 * wave(f, N, 1, 0.05); c["chest.rx"] += 2 * beat
    stand_feet(rig, c, spread=0.002)
    return c


PICKS = [34, 46, 58, 70, 82]          # frames: the right hand closes on stone k (desert.glb stone1..5)
BAGS = [40, 52, 64, 76]               # frames: stones 1-4 drop into the bag at the left hip; stone 5 goes to the sling


def rot_y(p, deg):
    """Design vector p rotated about +Y (the same sense as a `ry` channel: +Z turns toward +X)."""
    a = math.radians(deg)
    return V(p.x * math.cos(a) + p.z * math.sin(a), p.y, -p.x * math.sin(a) + p.z * math.cos(a))


# CONTRACT §12.5 moved the five stones to x -0.43...-0.40, z 0.10...0.16 (0.08-0.13 from the kneel mark, to his right
# and BEHIND him). Facing the viewer he cannot reach them, so while kneeling he turns his right side to the brook and
# shuffles toward it (root motion inside the clip, back to zero by the last frame, so the Director keeps the actor at
# the timeline mark facing the viewer). Feet are planned in actor space and step, they do not slide.
KNEEL_YAW = -45.0                     # deg: the stones end up on his right side (3/4 view, turned toward the brook)
KNEEL_STEP = V(-0.015, 0.0, -0.025)   # root offset while kneeling: back from the page edge, a little toward the brook
                                      # (a bigger step toward the stones puts the planted right foot on stone4)


def kneel_root(f):
    """(progress u, yaw, offset) of the kneel turn at frame f (0 standing, 1 kneeling at the brook)."""
    u = smooth(f / 14.0) * (1 - smooth((f - 84) / 11.0))
    return u, KNEEL_YAW * u, KNEEL_STEP * u


@clip("david", "kneel_pick", 96, False, root_motion=True,
      markers={"kneel": 16, "pick1": 34, "pick2": 46, "pick3": 58, "pick4": 70, "pick5": 82, "stone_in_pouch": 88},
      notes="turns his right side to the brook and shuffles 0.03 back from the page edge (root motion, back to zero by frame 96), "
            "kneels on the left knee, the right hand reaches down and out to each of the five desert.glb stones (open -> pinch -> close), stones 1-4 go into the bag, stone 5 "
            "(bone `stone`, visible from frame 82) into the sling pouch at 88; stands up by 96")
def david_kneel(rig, f, N):
    c = david_base(rig, f, N, loop=False)
    down = K([(0, 0), (4, -0.06), (16, 1), (84, 1), (94, 0.04), (96, 0)], f)
    down = min(1.0, max(-0.08, down))
    dn = max(0.0, down)
    u, yaw, T = kneel_root(f)
    c["root.ry"] = yaw; c["root.tx"] = T.x; c["root.tz"] = T.z
    # kneel on the left knee (shin on the ground, toes tucked), right foot planted forward, knee up. Each foot moves
    # from its standing spot to its kneeling spot (in the turned frame) in a step of its own: right 2-11 / 87-95,
    # left 5-16 / 84-93. Targets are root space, so the actor-space plan is rotated back by the current root turn.
    c["hips.ty"] = -0.060 * dn + 0.003 * min(0.0, down)
    c["hips.tz"] = -0.006 * dn
    bL, bR = rig.head["footL"], rig.head["footR"]
    pL = 72 * dn
    kL = KNEEL_STEP + rot_y(V(bL.x + 0.002, 0, bL.z - 0.066), KNEEL_YAW)
    kR = KNEEL_STEP + rot_y(V(bR.x - 0.004, 0, bR.z + 0.012), KNEEL_YAW)
    sL = smooth((f - 5) / 11.0) * (1 - smooth((f - 84) / 9.0))
    sR = smooth((f - 2) / 9.0) * (1 - smooth((f - 87) / 8.0))
    wL = V(bL.x, 0, bL.z).lerp(kL, sL); wR = V(bR.x, 0, bR.z).lerp(kR, sR)
    lR = 0.016 * math.sin(math.pi * sR) if 0.0 < sR < 1.0 else 0.0
    yL = max(planted_ankle_y(rig, "L", pL) + 0.003 * dn, lerp(planted_ankle_y(rig, "L", 0), 0.027, dn))
    tL = rot_y(wL - T, -yaw); tR = rot_y(wR - T, -yaw)
    c["ik.legL"] = V(tL.x, yL, tL.z)
    c["footL.pitch"] = pL
    c["ik.legR"] = V(tR.x, planted_ankle_y(rig, "R", 0) + lR, tR.z)
    c["footR.pitch"] = 0
    c["pole.legR"] = V(-0.2, 0, 1)
    # right hand: rest -> stone1 -> bag -> stone2 ... -> stone5 -> up in front of the chest (stone shown) -> rest
    st = [rot_y(p - KNEEL_STEP, -KNEEL_YAW) for p in brook_stones_local()]     # stones in the kneeling root frame
    hand_up = 0.016                                   # wrist above the stone top when the fingertips touch it
    bag = V(0.020, 0.074, 0.040)                      # front of the bag at the left hip, kneeling
    keys = [(22, V(-0.070, 0.090, 0.010))]
    for k, fr in enumerate(PICKS):
        s_ = st[k]
        keys.append((fr - 4, s_ + V(0.006, hand_up + 0.020, 0.004)))
        keys.append((fr, s_ + V(0.004, hand_up, 0.002)))
        if k < 4:
            keys.append((BAGS[k], bag))
    keys += [(87, V(-0.030, 0.120, 0.050)), (90, V(-0.040, 0.110, 0.040))]
    w = smooth((f - 16) / 7) * (1 - smooth((f - 88) / 7))
    tgt = V(*(K([(fr, p[i]) for fr, p in keys], f) for i in range(3)))
    c["ik.armR"] = tgt; c["ikw.armR"] = w
    c["pole.armR"] = V(-1.0, 0.1, -0.5)
    c["handR.bend"] = 20 * w
    # how far out the hand is -> lean the torso to the right (+rz) and forward
    reach = min(1.0, max(0.0, (-tgt.x + 0.01) / 0.05)) * w
    c["spine.rx"] = 10 * dn + 14 * reach; c["chest.rx"] = 6 * dn + 8 * reach
    c["spine.rz"] = 26 * reach; c["chest.rz"] = 20 * reach
    c["hips.rz"] = 10 * reach; c["hips.tx"] = -0.014 * reach
    c["shoulderR.raise"] = -14 * reach
    behind = min(1.0, max(0.0, (-tgt.z - 0.02) / 0.06)) * w     # stone1 lies behind his hip: turn toward it
    c["chest.ry"] = -14 * reach - 18 * behind; c["hips.ry"] = -10 * behind; c["hips.tz"] -= 0.012 * behind
    c["sling.damp"] = 16.0
    c["neck.rx"] = 6 * dn; c["head.rx"] = 10 * dn + 6 * reach; c["head.ry"] = -18 * reach
    # fingers: open on the way down, pinch at the stone, open again over the bag
    op = 0.0
    for fr in PICKS:
        op = max(op, max(0.0, 1 - abs(f - (fr - 3)) / 4.0))
    for fr in BAGS:
        op = max(op, 0.8 * max(0.0, 1 - abs(f - fr) / 3.0))
    fist(c, "R", open_=0.85 * op * w)
    # left forearm rests on the left thigh
    c["upperArmL.raise"] = lerp(-44, -52, dn); c["upperArmL.bend"] = lerp(4, 30, dn); c["forearmL.bend"] = lerp(16, 34, dn)
    open_hand(c, "L", curl=lerp(18, 40, dn), tips=lerp(24, 40, dn), thumb=4)
    # stone: in the hand from pick5 (82) until it drops into the pouch at 88
    c["stone.mode"] = "hand" if 82 <= f < 88 else "pouch"
    c["stone.s"] = 0.0 if f < 82 else 1.0
    return c


def windup_pose(rig, f, N, spins=3):
    c = david_base(rig, f, N, breath_cycles=1)
    ph = 2 * math.pi * spins * f / N
    # throwing stance: left foot forward, knees soft, torso coiled to the right, left arm aims at Goliath
    stand_feet(rig, c, spread=0.004, fwdL=0.026, fwdR=-0.018, pitchR=10)
    c["hips.ty"] = -0.008 + 0.0015 * math.cos(ph); c["hips.ry"] = -10; c["chest.ry"] = -8 + 3 * math.sin(ph)
    c["spine.rx"] = -3; c["head.ry"] = 16; c["head.rx"] = -2
    c["upperArmL.raise"] = 8; c["upperArmL.swing"] = 62; c["forearmL.bend"] = 10; c["handL.bend"] = -10
    open_hand(c, "L", curl=6, tips=6, thumb=0)                       # pointing hand, fingers straight
    # right arm overhead, the hand draws a small circle that drives the sling; the fist stays closed on the cords
    c["upperArmR.raise"] = 112 + 6 * math.sin(ph); c["upperArmR.swing"] = 10 + 6 * math.cos(ph)
    c["forearmR.bend"] = 28 + 8 * math.sin(ph + 0.5); c["handR.bend"] = 10
    c["sling.mode"] = "spin"; c["sling.phase"] = ph
    return c


@clip("david", "sling_windup", 36, True, notes="3 sling spins per loop (2.5 rev/s) overhead, left arm aims, right fist closed")
def david_windup(rig, f, N):
    return windup_pose(rig, f, N, 3)


RELEASE_F = 2           # stone leaves the pouch (marker 'release')
HIT_T = 0.45            # seconds after clip start the stone reaches Goliath's forehead (timeline 72.60 -> 73.05)
STONE_TARGET = V(0.0, 0.69, 0.33)   # David-local design coords of Goliath's forehead at the timeline marks (see ANIMATION.md)


@clip("david", "sling_release", 45, False, markers={"release": RELEASE_F, "hit": 14},
      notes="whip forward, the right hand opens at release (frame 2) and closes on the cord again, arm follows through "
            "across the body, stone flies to STONE_TARGET (arrives at 0.45 s), drops and rolls on the page")
def david_release(rig, f, N):
    c = windup_pose(rig, 0, 36, 3)        # starts from the windup's frame-0 pose
    t = smooth(f / 10.0)                  # whip + follow-through
    r = smooth((f - 22) / 20.0)           # recover
    c["upperArmR.raise"] = lerp(112, -10, t) + lerp(0, -30, r)
    c["upperArmR.swing"] = lerp(10, 70, t) + lerp(0, -60, r)
    c["forearmR.bend"] = lerp(28, 10, t) + lerp(0, 8, r)
    c["chest.ry"] = lerp(-8, 22, t) - 22 * r; c["hips.ry"] = lerp(-10, 8, t) - 8 * r
    c["spine.rx"] = lerp(-3, 10, t) - 10 * r + 0
    c["head.ry"] = lerp(16, 0, t); c["head.rx"] = lerp(-2, -8, t) + 8 * r
    c["upperArmL.raise"] = lerp(8, -30, t) + lerp(0, -14, r); c["upperArmL.swing"] = lerp(62, 10, t) - 10 * r
    open_hand(c, "L", curl=lerp(6, 30, t), tips=lerp(6, 34, t), thumb=4)
    fist(c, "R", open_=0.75 * smooth((f - 1) / 2.0) * (1 - smooth((f - 12) / 10.0)))
    stand_feet(rig, c, spread=0.004, fwdL=lerp(0.026, 0.034, t) - 0.020 * r, fwdR=-0.018 + 0.018 * r,
               pitchR=lerp(10, 34, t) * (1 - r), liftR=0.004 * math.sin(math.pi * r))
    c["hips.ty"] = lerp(-0.008, -0.012, t) + 0.010 * r; c["hips.tz"] = 0.004 * t * (1 - r)
    if f < RELEASE_F + 6:
        c["sling.mode"] = "spin"
        c["sling.phase"] = 2 * math.pi * (0.0 + 2.5 * f / FPS)
        c["sling.flatten"] = smooth(f / 4.0)
    else:
        c["sling.mode"] = "sim"
    c["stone.mode"] = "pouch" if f < RELEASE_F else "free"
    return c


@clip("david", "run", 16, True, markers={"contactL": 0, "contactR": 8}, notes="eager run, flight phase, arms pump")
def david_run(rig, f, N):
    c = david_base(rig, f, N)
    g = gait(rig, f, N, L=0.070, lift=0.030, duty=0.40, heel=6, toeoff=36, lift_shape=0.8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.006 + 0.006 * math.cos(2 * ph - 0.8)
    c["hips.ry"] = 8 * math.sin(ph); c["chest.ry"] = -12 * math.sin(ph - 0.3)
    c["spine.rx"] = 12; c["chest.rx"] = 4; c["head.rx"] = -10
    c["upperArmL.raise"] = -40; c["upperArmR.raise"] = -38
    c["upperArmL.bend"] = 10 - 40 * math.sin(ph - 0.2); c["upperArmR.bend"] = 10 + 40 * math.sin(ph - 0.2)
    c["forearmL.bend"] = 80 - 12 * math.sin(ph - 0.8); c["forearmR.bend"] = 80 + 12 * math.sin(ph - 0.8)
    open_hand(c, "L", curl=55, tips=65, thumb=10)                     # loose running fist
    return c


@clip("david", "victory", 45, False, markers={"takeoff": 10, "land": 22},
      notes="crouch, jump with both arms up (two raised fists, the right one still holding the sling), land; holds")
def david_victory(rig, f, N):
    c = david_base(rig, f, N, loop=False)
    crouch = K([(0, 0), (8, 1), (10, 0.3), (12, -0.2), (22, -0.2), (24, 1.0), (30, 0.2), (36, 0), (45, 0)], f)
    air = 0.0
    if 10 <= f <= 22:
        s = (f - 10) / 12.0
        air = 4 * s * (1 - s)            # parabola 0..1..0
    c["hips.ty"] = -0.016 * max(0, crouch) + 0.045 * air
    c["spine.rx"] = 10 * max(0, crouch) - 6 * air; c["head.rx"] = -10 * smooth((f - 8) / 6)
    arms = smooth((f - 7) / 6)
    for s_ in "LR":
        c[f"upperArm{s_}.raise"] = lerp(-44, 128, arms) - 8 * max(0, crouch) * (1 if f > 22 else 0)
        c[f"upperArm{s_}.bend"] = lerp(4, 20, arms)
        c[f"forearm{s_}.bend"] = lerp(16, 24, arms) + 25 * max(0, crouch) * (1 if f > 22 else 0)
    open_hand(c, "L", curl=lerp(18, 88, arms), tips=lerp(24, 100, arms), thumb=lerp(4, 35, arms))
    for side in "LR":
        b = rig.head["foot" + side]
        pt = 30 * air
        c[f"ik.leg{side}"] = V(b.x, planted_ankle_y(rig, side, pt) + 0.045 * air, b.z - 0.006 * air)
        c[f"foot{side}.pitch"] = pt
    c["jaw.rx"] = 10 * smooth((f - 10) / 5)
    return c


@clip("david", "pray", 90, False, markers={"knees_down": 34, "hands_together": 50},
      notes="kneels (right knee, then left), both hands open, palms together in front of the chest, head bowed; holds")
def david_pray(rig, f, N):
    c = david_base(rig, f, N, loop=False)
    one = smooth((f - 4) / 16)         # first the right knee, then the left
    two = smooth((f - 18) / 16)
    down = 0.5 * (one + two)
    c["hips.ty"] = -0.060 * down
    c["hips.tz"] = -0.010 * down
    c["spine.rx"] = 4 * down; c["neck.rx"] = 10 * smooth((f - 40) / 20); c["head.rx"] = 18 * smooth((f - 40) / 20)
    for side, w in (("L", two), ("R", one)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x, max(planted_ankle_y(rig, side, 72 * w) + 0.003 * w, lerp(planted_ankle_y(rig, side, 0), 0.027, w)), b.z - 0.066 * w)
        c[f"foot{side}.pitch"] = 72 * w
    h = smooth((f - 30) / 20)
    c["ik.armL"] = V(0.0075, -0.012, 0.050); c["ik.armR"] = V(-0.0075, -0.012, 0.050)
    c["ikspace.armL"] = c["ikspace.armR"] = "chest"
    c["pole.armL"] = V(0.5, -1.0, -0.3); c["pole.armR"] = V(-0.5, -1.0, -0.3)
    c["ikw.armL"] = h; c["ikw.armR"] = h
    open_hand(c, "L", curl=lerp(18, 4, h), tips=lerp(24, 4, h), thumb=0)
    fist(c, "R", open_=h)
    c["handL.bend"] = lerp(6, -20, h); c["handR.bend"] = lerp(4, -20, h)
    return c


# =============================================================================================== GOLIATH
def goliath_base(rig, f, N, breath_cycles=1):
    c = {}
    b = wave(f, N, breath_cycles)
    c["chest.rx"] = -2.0 * b; c["spine.rx"] = 2
    c["shoulderL.raise"] = 2 * b; c["shoulderR.raise"] = 2 * b
    # spear arm: forearm forward, spear upright; shield arm forward
    c["upperArmR.raise"] = -38; c["upperArmR.bend"] = 16; c["forearmR.bend"] = 58; c["forearmR.twist"] = 0
    c["upperArmL.raise"] = -30; c["upperArmL.bend"] = 20; c["forearmL.bend"] = 42
    c["handR.bend"] = -8
    c["neck.rx"] = -2; c["head.rx"] = 2
    c["spear.up"] = 1.0          # 1 = spear kept upright like a staff (the hand turns around it), 0 = follows the hand
    return c


@clip("goliath", "idle", 90, True, notes="slow heavy breathing, weight shift, grumpy head turns; spear sways (spring)")
def goliath_idle(rig, f, N):
    c = goliath_base(rig, f, N)
    sh = wave(f, N, 1, 0.25)
    c["hips.tx"] = 0.006 * sh; c["hips.ty"] = -0.004 - 0.002 * wave(f, N, 2)
    c["hips.rz"] = -1.5 * sh; c["chest.rz"] = 1.2 * sh
    c["head.ry"] = 8 * K([(0, 0), (20, 0), (34, 10), (56, 10), (70, -4), (90, 0)], f, N, True) / 10
    c["head.rz"] = 2 * wave(f, N, 1, 0.4)
    stand_feet(rig, c, spread=0.004)
    return c


def goliath_steps(rig, f, N, L, lift, duty, offL, offR, lean, drop):
    c = goliath_base(rig, f, N)
    g = gait(rig, f, N, L=L, lift=lift, duty=duty, offsetL=offL, offsetR=offR, heel=10, toeoff=18)
    legs_ik_channels(c, g)
    # contact impact: hips drop sharply after each contact and recover slowly (weight)
    imp = 0.0
    for side in "LR":
        p = g["leg" + side][3]
        k = p / duty if p < duty else 9
        imp = max(imp, math.exp(-((k - 0.12) / 0.10) ** 2))
    ph = 2 * math.pi * (f / N + offL)
    c["hips.ty"] = -0.010 - drop * imp + 0.006 * math.cos(2 * ph)
    c["hips.rz"] = 4 * math.cos(ph); c["hips.ry"] = 5 * math.sin(ph)
    c["chest.ry"] = -6 * math.sin(ph - 0.4); c["chest.rz"] = -3 * math.cos(ph - 0.5)
    c["spine.rx"] = lean; c["chest.rx"] = 3 * imp
    c["head.rx"] = -lean * 0.6 + 4 * imp                      # head nods after the impact (overlap)
    c["upperArmL.bend"] = 20 - 10 * math.sin(ph - 0.4)
    c["upperArmR.bend"] = 16 + 8 * math.sin(ph - 0.4)
    c["_impact"] = imp
    return c


@clip("goliath", "walk", 66, True, markers={"contactL": 9, "contactR": 42},
      notes="slow ground-shaking walk; contacts at 0.3 s and 1.4 s = timeline dust/giant_step 1.3, 2.4, 3.5")
def goliath_walk(rig, f, N):
    return goliath_steps(rig, f, N, L=0.10, lift=0.050, duty=0.64, offL=-9 / 66, offR=-42 / 66, lean=4, drop=0.016)


@clip("goliath", "charge", 60, True, markers={"contactL": 0, "contactR": 30},
      notes="lumbering charge, spear levelled at David, shield forward; contacts 1.0 s apart (giant_step 69, 70, 71)")
def goliath_charge(rig, f, N):
    c = goliath_steps(rig, f, N, L=0.15, lift=0.06, duty=0.60, offL=0.0, offR=-0.5, lean=14, drop=0.020)
    c["upperArmR.raise"] = -24; c["upperArmR.bend"] = 30; c["forearmR.bend"] = 55; c["handR.bend"] = 10
    c["spear.up"] = 0.0
    c["spear.aim"] = V(0.12, 0.06, 1.0)               # levelled at David, tip forward and slightly inward
    c["upperArmL.raise"] = -20; c["upperArmL.bend"] = 55 - 6 * wave(f, N, 1); c["forearmL.bend"] = 55
    c["head.rx"] = -8
    c["jaw.rx"] = 10
    return c


@clip("goliath", "talk", 48, True, notes="boastful talk: jaw flap, chin up, spear arm gestures")
def goliath_talk(rig, f, N):
    c = goliath_base(rig, f, N)
    jaw = [(0, 0), (4, 14), (8, 4), (12, 18), (16, 2), (20, 12), (24, 3), (28, 16), (32, 1), (36, 13), (40, 4), (44, 10), (48, 0)]
    c["jaw.rx"] = max(0.0, K(jaw, f, N, True))
    c["head.rx"] = -6 + 3 * wave(f, N, 2, 0.1); c["head.ry"] = 6 * wave(f, N, 1); c["neck.rx"] = -3
    c["chest.rx"] = -4 + 1.5 * wave(f, N, 2, 0.2)
    beat = K([(0, 0), (8, 1), (20, 0.3), (30, 1), (40, 0.2), (48, 0)], f, N, True)
    c["upperArmR.bend"] = 16 + 10 * beat; c["forearmR.bend"] = 58 + 10 * beat
    c["upperArmL.raise"] = -30 + 4 * beat
    stand_feet(rig, c, spread=0.004)
    return c


@clip("goliath", "taunt", 48, False, markers={"clang": 9},
      notes="lifts the spear and bangs it on the shield (clang at 0.3 s), chin up, sneer")
def goliath_taunt(rig, f, N):
    c = goliath_base(rig, f, N)
    up = K([(0, 0), (6, 1), (9, -0.15), (12, 0.1), (16, 0), (24, 0.8), (27, -0.1), (30, 0.05), (36, 0), (48, 0)], f)
    c["upperArmR.raise"] = -38 + 80 * up; c["upperArmR.swing"] = 40 * max(0, up) + 20; c["forearmR.bend"] = 58 + 20 * up
    c["upperArmL.raise"] = -30; c["upperArmL.bend"] = 50; c["upperArmL.swing"] = 30; c["forearmL.bend"] = 50
    c["hips.ty"] = -0.008 * max(0, up)
    c["spear.up"] = 0.0
    c["chest.ry"] = 10 * up; c["head.rx"] = -10 * smooth(f / 8); c["head.rz"] = -4 * smooth(f / 8)
    c["jaw.rx"] = 6 * smooth((f - 30) / 6)
    stand_feet(rig, c, spread=0.006)
    return c


@clip("goliath", "laugh", 60, False, notes="head back, belly bounces 5 times (ha-ha-ha), jaw open")
def goliath_laugh(rig, f, N):
    c = goliath_base(rig, f, N)
    env = smooth(f / 6) * (1 - smooth((f - 50) / 10))
    ha = 0.5 + 0.5 * math.cos(2 * math.pi * f / 9.0)          # ~3.3 ha/s
    c["head.rx"] = -26 * env + 6 * ha * env; c["neck.rx"] = -8 * env
    c["chest.rx"] = -10 * env + 5 * ha * env; c["spine.rx"] = 2 - 8 * env
    c["hips.ty"] = -0.012 * env * ha; c["hips.tz"] = 0.008 * env
    c["chest.ry"] = 6 * env * math.sin(2 * math.pi * f / 30.0)
    c["shoulderL.raise"] = 6 * ha * env; c["shoulderR.raise"] = 6 * ha * env
    c["jaw.rx"] = env * (12 + 8 * ha)
    c["upperArmL.raise"] = -30 - 14 * env; c["upperArmL.bend"] = 20 + 14 * env; c["forearmL.bend"] = 42 + 40 * env
    c["upperArmR.raise"] = -38 + 10 * env * ha
    stand_feet(rig, c, spread=0.004)
    return c


@clip("goliath", "roar", 54, False, markers={"roar": 16},
      notes="anticipation crouch + inhale, then roar with arms out and spear high, settle")
def goliath_roar(rig, f, N):
    c = goliath_base(rig, f, N)
    a = K([(0, 0), (12, 1), (16, 0), (54, 0)], f)                 # inhale / crouch
    r = K([(0, 0), (12, 0), (17, 1), (40, 1), (54, 0.1)], f)     # roar
    shake = math.sin(2 * math.pi * f / 3.0) * r
    c["hips.ty"] = -0.022 * a - 0.008 * r
    c["spine.rx"] = 10 * a - 6 * r; c["chest.rx"] = 6 * a - 10 * r + 0.8 * shake
    c["head.rx"] = 12 * a + 6 * r; c["neck.rx"] = -8 * r
    c["jaw.rx"] = 4 * a + 26 * r
    c["upperArmL.raise"] = -30 + 50 * r; c["upperArmL.bend"] = 20 + 10 * r
    c["upperArmR.raise"] = -38 + 90 * r; c["forearmR.bend"] = 58 - 30 * r
    c["shoulderL.raise"] = 8 * r; c["shoulderR.raise"] = 8 * r
    c["spear.up"] = 1.0 - min(1.0, max(0.0, r))
    stand_feet(rig, c, spread=0.010 * r)
    return c


@clip("goliath", "hit_react", 28, False, markers={"impact": 0},
      notes="impact at frame 0: head snaps back, stagger one step back, wobble (dizzy)")
def goliath_hit(rig, f, N):
    c = goliath_base(rig, f, N)
    snap = K([(0, 0), (3, 1), (8, 0.6), (14, 0.2), (28, 0.1)], f)
    wob = math.sin(2 * math.pi * f / 14.0) * smooth(f / 6)
    c["head.rx"] = -38 * snap; c["neck.rx"] = -14 * snap; c["chest.rx"] = -14 * snap; c["spine.rx"] = 2 - 8 * snap
    c["spine.rz"] = 4 * wob; c["head.rz"] = 8 * wob; c["chest.rz"] = 3 * wob
    c["jaw.rx"] = 14 * snap
    c["spear.up"] = 0.6
    c["upperArmL.raise"] = -30 + 30 * snap; c["upperArmR.raise"] = -38 + 26 * snap
    stagger = smooth((f - 2) / 10)
    stand_feet(rig, c, spread=0.008, fwdR=-0.05 * stagger,
               liftR=0.03 * math.sin(math.pi * min(1, max(0, (f - 2) / 10))))
    c["hips.tz"] = -0.02 * stagger; c["hips.ty"] = -0.01 * stagger
    return c


FALL_GROUND = 36
FALL_BACK = 0.20        # he staggers this far back (-Z) before toppling forward, so he lands on the paper (§11, D8)
SPEAR_REL, SHIELD_REL = 20, 22
SPEAR_BUTT = 0.402     # spear bone head (grip) to the butt spike tip, along the shaft      # frames the hands open and let go of spear and shield
# Where spear and shield come to rest (character-local design coords; Goliath faces +Z when he falls): the spear lies
# along his right side, the shield face up beside his left hip. Checked against paper and desert in `build` (clips.json).
SPEAR_REST = (V(-0.135, 0.0095, -0.13), V(0, 0, 1), V(0, 1, 0))      # bone head (grip), tip direction, blade side
SHIELD_REST = (V(0.245, 0.013, -0.30), V(0, 1, 0), V(0, 0, -1))       # bone head (grip), face normal, bone Z


@clip("goliath", "fall", 54, False, root_motion=True, markers={"knees": 16, "ground": FALL_GROUND},
      notes="dizzy sway and two stagger steps back (0.20), knees buckle, he pivots about the knees and falls onto his face "
            "(+Z, toward the viewer) with the head turned onto the cheek; hands open, spear and shield fall free and lie "
            "beside him. Root motion. With the timeline mark (0.16, -0.22) and facing the viewer the whole body, spear "
            "and shield stay on the paper (checked in clips.json fallFootprint)")
def goliath_fall(rig, f, N):
    c = goliath_base(rig, f, N)
    sway = math.sin(2 * math.pi * f / 16.0) * (1 - smooth((f - 10) / 8))
    c["head.rz"] = 8 * sway; c["spine.rz"] = 4 * sway; c["head.rx"] = -14 + 14 * smooth((f - 8) / 10)
    # stagger back: right foot, then left foot, hips follow (world = character space; the root carries the motion)
    back = FALL_BACK
    sR = smooth(f / 8.0); sL = smooth((f - 5) / 8.0)
    c["root.tz"] = -back * smooth(f / 13.0)
    buck = K([(0, 0), (8, -0.04), (16, 1), (54, 1)], f); buck = min(1.0, max(0.0, buck))
    c["hips.ty"] = -0.172 * buck
    c["spine.rx"] = 6 * buck + 4 * sway; c["chest.rx"] = 6 * buck - 8 * (1 - buck) * smooth(f / 6)
    for side, s_, ph0 in (("L", sL, 5), ("R", sR, 0)):
        b = rig.head["foot" + side]
        lift = 0.045 * math.sin(math.pi * min(1.0, max(0.0, (f - ph0) / 8.0)))
        pt = 50 * buck
        c[f"ik.leg{side}"] = V(b.x, planted_ankle_y(rig, side, pt) + lift * (1 - buck), b.z - back * s_ - 0.16 * buck)
        c[f"foot{side}.pitch"] = pt
        c[f"ikspace.leg{side}"] = "world"
    # topple about the knees: ease-in (gravity), small bounce at the ground mark
    tt = max(0.0, (f - 16) / (FALL_GROUND - 16))
    topple = tt * tt if f <= FALL_GROUND else 1.0 - 0.035 * math.exp(-(f - FALL_GROUND) / 3.0) * math.sin(math.pi * (f - FALL_GROUND) / 4.0)
    c["root.rx"] = 86 * topple
    c["_fall_pivot"] = topple
    # arms: flung up in surprise while buckling, then limp along the sides, a little out, palms down on the page
    up = K([(0, 0), (6, 0.5), (14, 0.7), (24, 0.3), (34, 0), (54, 0)], f)
    arms = smooth((f - 20) / 14)
    c["upperArmL.raise"] = lerp(-30 + 50 * up, -62, arms); c["upperArmL.bend"] = lerp(20, 34, arms)
    c["forearmL.bend"] = lerp(42, 10, arms); c["upperArmL.swing"] = 0
    c["upperArmR.raise"] = lerp(-38 + 50 * up, -62, arms); c["upperArmR.bend"] = lerp(16, 34, arms)
    c["forearmR.bend"] = lerp(58, 10, arms)
    c["handL.bend"] = lerp(0, -10, arms); c["handR.bend"] = lerp(-8, -10, arms)
    # lying: the arms rest on the page beside the chest (targets in the chest frame; its front faces the page)
    lie = smooth((f - 24) / 12)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"ik.arm{side}"] = V(0.165 * sx, -0.170, 0.072)
        c[f"ikspace.arm{side}"] = "chest"; c[f"ikw.arm{side}"] = lie
        c[f"pole.arm{side}"] = V(1.0 * sx, 0.0, -0.8)
    fist(c, "L", open_=smooth((f - SHIELD_REL) / 6)); fist(c, "R", open_=smooth((f - SPEAR_REL) / 6))
    c["head.ry"] = -70 * smooth((f - 32) / 10)       # turns onto the right cheek so the dizzy face shows
    c["neck.rx"] = -14 * smooth((f - 26) / 10)
    c["jaw.rx"] = 8
    c["spear.up"] = 1.0 - smooth((f - 4) / 14)
    c["spear.free"] = (SPEAR_REL, 34)                # (release frame, landing frame)
    c["shield.free"] = (SHIELD_REL, 37)
    return c


@clip("goliath", "down", 60, True, root_motion=True,
      notes="lying on his face (same root offset as the last frame of fall), slow breathing, head on the cheek")
def goliath_down(rig, f, N):
    c = goliath_fall(rig, 54, 54)
    c["chest.rx"] += 1.5 * wave(f, N, 1)
    c["jaw.rx"] = 8 + 2 * wave(f, N, 1, 0.2)
    c["_down"] = True
    return c


# debug only: DG_TEST="david:fingersL.curl=60,fingerTipsL.curl=60" adds a 1-frame clip <char>_test (idle frame 0 + overrides)
if os.environ.get("DG_TEST"):
    for _spec in os.environ["DG_TEST"].split(";"):
        _ch, _kv = _spec.split(":", 1)

        def _mk(ch=_ch, kv=_kv):
            base = david_idle if ch == "david" else goliath_idle

            def fn(rig, f, N):
                c = base(rig, 0, 60 if ch == "david" else 90)
                for item in kv.split(","):
                    k, v = item.split("=")
                    c[k] = float(v)
                return c
            return fn
        CLIPS.append(Clip(_ch, "test", 1, False, _mk()))


# =============================================================================================== evaluation
def fall_root_fix(rig, M, basis, chs):
    """Fall: the root rotation (root.rx) pivots about the knees, not the feet, on top of the root's own translation T
    (stagger). Root world = t + R p with t = P + R (T - P), P = knee midpoint of the same pose without the rotation;
    then lift so the armour rests on the page."""
    if "_fall_pivot" not in chs:
        return
    topple = chs["_fall_pivot"]
    ch0 = dict(chs); ch0["root.rx"] = 0
    b0 = rig.basis_from(ch0); M0 = rig.fk(b0)
    apply_ik(rig, b0, M0, ch0)
    P = (rig.pos(M0, "shinL") + rig.pos(M0, "shinR")) / 2
    T = V(chs.get("root.tx", 0.0), chs.get("root.ty", 0.0), chs.get("root.tz", 0.0))
    R = rot_d((1, 0, 0), chs.get("root.rx", 0.0))
    off = P + CI @ (R @ (C @ (T - P)))
    for _ in range(3):
        basis["root"][1] = rig.rest3["root"].inverted() @ (C @ off)
        rig.fk(basis, M)
        apply_ik(rig, basis, M, chs)
        pts = [rig.pos(M, n, "tail") for n in ("chest", "spine", "neck")] + [rig.pos(M, n) for n in ("hips", "chest")]
        lowest = min(p.y for p in pts)
        clear = 0.080 * smooth(topple * 1.4)        # armour depth: the chest line sits this far above the page when lying
        if lowest < clear:
            off.y += (clear - lowest)


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
        # targets are in root space (design) unless ikspace says "world" (armature space) or "chest"
        # (offset from the chest's rest head, carried by the posed chest)
        space = chs.get("ikspace." + limb, "root")
        Mroot = M["root"] @ rig.rest["root"].inverted()      # posed root delta (the rest frame is not identity)
        if space == "world":
            t_world = t; Mroot = Matrix.Identity(4)
        elif space in M:                 # offset from that bone's rest head, carried by the posed bone
            Mc = M[space]
            t_world = to_d(Mc @ (rig.rest[space].inverted() @ to_bl(rig.head[space] + t)))
        else:
            t_world = to_d(Mroot @ to_bl(t))
        pole = V(0.15 * sx, 0, 1) if legs else V(0.6 * sx, -0.6, -0.5)
        if "pole." + limb in chs:
            pole = Vector(chs["pole." + limb])
        if space in M and space != "root":
            Pm = (M[space] @ rig.rest[space].inverted()).to_3x3()   # pole turns with the target's bone
        else:
            Pm = Mroot.to_3x3()
        pole = to_d(Pm @ to_bl(pole))
        old = {n: [basis[n][0].copy(), basis[n][1].copy(), basis[n][2]] for n in (up, lo, end)}
        ik2(rig, basis, M, up, lo, t_world, pole, legs)
        if legs:
            # foot: rest orientation carried by the root (stays flat on the page) + pitch about the side axis
            pitch = chs.get(f"foot{side}.pitch", 0.0)
            Rf = Mroot.to_3x3().normalized() @ rot_d((1, 0, 0), pitch) @ rig.rest3[end]
            rig.set_world_rot(basis, M, end, Rf)
        if w < 0.9999:
            for n in (up, lo, end):
                basis[n][0] = old[n][0].slerp(basis[n][0], w)
            rig.fk(basis, M)


def evaluate_primary(rig, clip_, f):
    chs = clip_.fn(rig, f, clip_.N)
    basis = rig.basis_from(chs)
    M = rig.fk(basis)
    apply_ik(rig, basis, M, chs)
    fall_root_fix(rig, M, basis, chs)
    return chs, basis, M


def sling_guides(rig, M, chs):
    """Guide points (design) for the 3 sling bones while the sling is whirled (or being released)."""
    n0 = rig.pos(M, "slingCord1")
    hand = rig.pos(M, "handR", "tail")
    ph = chs["sling.phase"]
    up = (hand - rig.pos(M, "forearmR")).normalized()
    # whirl plane: nearly horizontal over the head, tilted 20 deg toward the target (+Z)
    e1 = V(1, 0, 0); e2 = V(0, 0.34, 0.94).normalized()
    flat = chs.get("sling.flatten", 0.0)
    pts = [n0]
    R = [0.0, 0.030, 0.056, 0.084]
    lag = [0.0, 0.25, 0.45, 0.55]
    for k in (1, 2, 3):
        a = ph - lag[k]
        p = n0 + (e1 * math.cos(a) + e2 * math.sin(a)) * R[k] + up * (0.004 * k)
        pts.append(p)
    return pts


def sim_sling(rig, frames_M, N, loop, init=None, pre_frames=0, damping=5.0):
    """Verlet chain (4 nodes, node 0 pinned to the cord1 head). frames_M: list of M per frame.
    Returns node lists per frame. For loops, run 3 cycles and keep the last."""
    L = [rig.length["slingCord1"], rig.length["slingCord2"], rig.length["slingPouch"]]
    sub = 8
    dt = 1.0 / FPS / sub
    cycles = 8 if loop else 1
    seq = (list(range(N)) * cycles + [N]) if loop else list(range(len(frames_M)))
    if init is None:
        n0 = rig.pos(frames_M[seq[0]], "slingCord1")
        nodes = [n0, n0 + V(0, -L[0], 0), n0 + V(0, -L[0] - L[1], 0), n0 + V(0, -sum(L), 0)]
        prev = [p.copy() for p in nodes]
    else:
        nodes, prev = [p.copy() for p in init[0]], [p.copy() for p in init[1]]
    out = {}
    last_pin = nodes[0].copy()
    for idx, fr in enumerate(seq):
        pin = rig.pos(frames_M[fr], "slingCord1")
        for s in range(sub):
            a = (s + 1) / sub
            p0 = last_pin.lerp(pin, a)
            for i in (1, 2, 3):
                v = (nodes[i] - prev[i]) * (1 - damping * dt)
                prev[i] = nodes[i].copy()
                nodes[i] = nodes[i] + v + V(0, -G, 0) * dt * dt
                # stay above the page
                if nodes[i].y < 0.004:
                    nodes[i].y = 0.004
            nodes[0] = p0
            for _ in range(4):
                for i in range(3):
                    a_, b_ = nodes[i], nodes[i + 1]
                    d = b_ - a_
                    l = max(d.length, 1e-9)
                    diff = (l - L[i]) / l
                    if i == 0:
                        nodes[1] = b_ - d * diff
                    else:
                        nodes[i] = a_ + d * diff * 0.5
                        nodes[i + 1] = b_ - d * diff * 0.5
        last_pin = pin.copy()
        if (not loop) or idx >= len(seq) - (N + 1):
            out[fr] = [p.copy() for p in nodes]
    if loop:
        # remove the tiny residual mismatch so the loop closes exactly (spread linearly over the cycle)
        d = [a - b for a, b in zip(out[N], out[0])]
        for fr in range(N + 1):
            out[fr] = [p - e * (fr / N) for p, e in zip(out[fr], d)]
    return out, (nodes, prev)


def aim_chain(rig, basis, M, names, pts):
    for i, n in enumerate(names):
        Cm = rig.carried(M, n).to_3x3().normalized()
        cur = Cm.col[1].normalized()
        want = (C @ (pts[i + 1] - pts[i])).normalized()
        Rd = cur.rotation_difference(want).to_matrix()
        rig.set_world_rot(basis, M, n, Rd @ Cm)


def bake_clip(rig, clip_):
    """-> list of basis dicts (one per frame 0..N) + per-frame M, with secondary motion and the stone."""
    N = clip_.N
    prim = [evaluate_primary(rig, clip_, f) for f in range(N + 1)]
    frames_M = [p[2] for p in prim]
    res = []
    if rig.ch == "david":
        sim_frames = [f for f in range(N + 1) if prim[f][0].get("sling.mode", "sim") == "sim"]
        damp = prim[0][0].get("sling.damp", 5.0)
        sim = {}
        if sim_frames:
            if clip_.loop:
                sim, _ = sim_sling(rig, frames_M, N, True)
            else:
                # one-shot: start from a settled chain (2 s of the first frame), then run straight through
                f0 = sim_frames[0]
                init = None
                if f0 > 0:                       # released after spinning: seed with the spin guides (velocity!)
                    g1 = sling_guides(rig, frames_M[f0 - 1], dict(prim[f0 - 1][0], **{"sling.phase": prim[f0 - 1][0].get("sling.phase", 0)}))
                    g2 = sling_guides(rig, frames_M[f0 - 2], dict(prim[f0 - 2][0], **{"sling.phase": prim[f0 - 2][0].get("sling.phase", 0)}))
                    # prev positions one substep earlier ~ linear extrapolation of last frame
                    prevp = [b + (a - b) * (1 - 1 / 8) for a, b in zip(g1, g2)]
                    init = ([p.copy() for p in g1], prevp)
                    sim, _ = sim_sling(rig, frames_M[f0:], len(frames_M) - f0, False, init=init, damping=damp)
                    sim = {k + f0: v for k, v in sim.items()}
                else:
                    settle = [frames_M[0]] * 60
                    _, st = sim_sling(rig, settle, 60, False)
                    sim, _ = sim_sling(rig, frames_M, N + 1, False, init=st, damping=damp)
        # stone flight (sling_release): release point = pouch at RELEASE_F
        rel_pos = None
        for f in range(N + 1):
            chs, basis, M = prim[f]
            if chs.get("sling.mode", "sim") == "spin":
                pts = sling_guides(rig, M, chs)
            else:
                pts = sim[f]
            aim_chain(rig, basis, M, ["slingCord1", "slingCord2", "slingPouch"], pts)
            mode = chs.get("stone.mode", "pouch")
            if f == RELEASE_F and clip_.name == "sling_release":
                rel_pos = stone_world_in(rig, M, "slingPouch")
            if mode == "pouch":
                place_stone(rig, basis, M, stone_world_in(rig, M, "slingPouch"))
            elif mode == "hand":
                place_stone(rig, basis, M, rig.pos(M, "handR", "tail") + V(0, -0.004, 0.004))
            elif mode == "free":
                place_stone(rig, basis, M, stone_flight(rel_pos, f / FPS), spin=f * 40.0)
            basis["stone"][2] = chs.get("stone.s", 1.0)
            res.append((basis, M))
    else:
        # spear spring (lags the hand, overlap); shield/spear drop in fall
        dirs, want = [], []
        up_bl = Vector((0, 0, 1))
        for f in range(N + 1):
            chs, basis, M = prim[f]
            d0 = rig.carried(M, "spear").to_3x3().normalized().col[1].copy()
            dirs.append(d0)
            w = chs.get("spear.up", 0.0)
            wd = d0.slerp(up_bl, w) if w > 0 else d0
            if "spear.aim" in chs:              # levelled spear: the shaft points this design direction from the grip
                wd = wd.slerp((C @ Vector(chs["spear.aim"])).normalized(), chs.get("spear.aimw", 1.0))
            want.append(wd)
        lagged = spring_dirs(want, clip_.loop, k=90.0, c=7.0)
        for f in range(N + 1):
            chs, basis, M = prim[f]
            Cm = rig.carried(M, "spear").to_3x3().normalized()
            Rd = dirs[f].rotation_difference(lagged[f]).to_matrix()
            Rw = Rd @ Cm
            rig.set_world_rot(basis, M, "spear", Rw)
            # the grip slides along the shaft rather than letting the butt spike sink into the page
            butt = to_d(M["spear"] @ Vector((0, -SPEAR_BUTT, 0)))
            ydir = to_d(M["spear"].to_3x3() @ Vector((0, 1, 0))).normalized()
            if butt.y < 0.003 and ydir.y > 0.3 and not (chs.get("spear.free") and f > chs["spear.free"][0]):
                basis["spear"][1] = basis["spear"][1] + basis["spear"][0] @ Vector((0, (0.003 - butt.y) / ydir.y, 0))
                rig.fk(basis, M, only={"spear"})
            res.append((basis, M))
        # props let go (fall): from the hand-held world matrix at the release frame, a ballistic drop (ease-in) to the
        # resting matrix on the page, with a small tumble; `down` holds the resting matrix
        for prop, rest in (("spear", SPEAR_REST), ("shield", SHIELD_REST)):
            spec = prim[0][0].get(prop + ".free")
            if not spec:
                continue
            f_rel, f_land = spec
            down = prim[0][0].get("_down", False)
            W_rel = None if down else res[min(f_rel, N)][1][prop].copy()
            head, ydir, zdir = rest
            Rg = frame_from(ydir, zdir)
            W_land = Matrix.Translation(to_bl(head)) @ Rg.to_4x4()
            for f in range(N + 1):
                basis, M = res[f]
                if down:
                    W = W_land
                elif f <= f_rel:
                    continue
                else:
                    t = min(1.0, (f - f_rel) / (f_land - f_rel))
                    tt = t * t                                           # gravity: ease-in
                    p0, p1 = W_rel.translation, W_land.translation
                    pos = p0.lerp(p1, tt)
                    if f > f_land:                                   # tiny settle bounce
                        u = f - f_land
                        pos = p1 + Vector((0, 0, 0.006 * math.exp(-u / 2.5) * abs(math.sin(math.pi * u / 3.0))))
                    q = W_rel.to_quaternion().slerp(W_land.to_quaternion(), smooth(t))
                    W = Matrix.Translation(pos) @ q.to_matrix().to_4x4()
                Cm = rig.carried(M, prop)
                B = Cm.inverted() @ W
                basis[prop][0] = B.to_quaternion(); basis[prop][1] = B.translation.copy()
                rig.fk(basis, M, only={prop})
    return res


def rot_lerp(A, B, t):
    return A.to_quaternion().slerp(B.to_quaternion(), t).to_matrix()


def flat_on_page(rig, M, n, along_d):
    """World rotation laying bone n flat on the page pointing along along_d (design)."""
    return frame_from(along_d, V(0, 1, 0))


def spring_dirs(dirs, loop, k, c):
    """Damped spring on a unit direction (critically-ish damped), max deviation 8 deg."""
    n = len(dirs)
    cycles = 3 if loop else 1
    seq = list(range(n - 1)) * cycles + [n - 1] if loop else list(range(n))
    cur = dirs[seq[0]].copy(); vel = Vector((0, 0, 0))
    out = [None] * n
    dt = 1.0 / FPS / 4
    for idx, f in enumerate(seq):
        tgt = dirs[f]
        for _ in range(4):
            acc = (tgt - cur) * k - vel * c
            vel += acc * dt
            cur = (cur + vel * dt).normalized()
        ang = cur.angle(tgt)
        lim = math.radians(8)
        if ang > lim:
            cur = tgt.slerp(cur, lim / ang) if hasattr(tgt, "slerp") else cur
        if (not loop) or idx >= len(seq) - n:
            out[f] = cur.copy()
    if loop:
        out[n - 1] = out[0]
    return out


def stone_world_in(rig, M, pouch):
    """Where the stone sits in the pouch: rest offset stone<-pouch carried by the posed pouch."""
    off = rig.rest[pouch].inverted() @ rig.rest["stone"]
    return to_d((M[pouch] @ off).translation)


def place_stone(rig, basis, M, pos_d, spin=0.0):
    Cm = rig.carried(M, "stone")
    want = to_bl(pos_d)
    R = Cm.to_3x3().normalized()
    if spin:
        R = rot_d((1, 0, 0), spin) @ R
    Mw = Matrix.Translation(want) @ R.to_4x4()
    B = Cm.inverted() @ Mw
    basis["stone"][0] = B.to_quaternion()
    basis["stone"][1] = B.translation.copy()
    rig.fk(basis, M, only={"stone"})


def stone_flight(p0, t):
    """Ballistic from p0 at release time to STONE_TARGET at HIT_T; after the hit it pops back, falls, bounces, rolls."""
    t0 = RELEASE_F / FPS
    tau = HIT_T - t0
    if t <= HIT_T:
        s = t - t0
        v0 = (STONE_TARGET - p0) / tau + V(0, 0.5 * G * tau, 0)
        return p0 + v0 * s + V(0, -0.5 * G * s * s, 0)
    s = t - HIT_T
    r = 0.006
    v = V(0, 0.25, -0.22)
    p = STONE_TARGET + v * s + V(0, -0.5 * G * s * s, 0)
    if p.y < r:
        # time of first landing
        a, b, cc = -0.5 * G, v.y, STONE_TARGET.y - r
        tl = (-b - math.sqrt(b * b - 4 * a * cc)) / (2 * a)
        land = STONE_TARGET + v * tl + V(0, -0.5 * G * tl * tl, 0)
        u = s - tl
        vb = 0.35 * G * tl * 0.5
        y = r + max(0.0, vb * u - 0.5 * G * u * u)
        roll = 0.05 * (1 - math.exp(-u * 4))
        return V(land.x, y, land.z - roll)
    return p


# =============================================================================================== writing actions
def write_action(rig, clip_, frames):
    obj = rig.obj
    act = bpy.data.actions.get(clip_.action) or bpy.data.actions.new(clip_.action)
    act.use_fake_user = True
    obj.animation_data_create()
    obj.animation_data.action = act
    n = len(frames)
    for pb in obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
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
        grp = name
        for path, comps in ((f'pose.bones["{name}"].rotation_quaternion', [[q[i] for q in qs] for i in range(4)]),
                            (f'pose.bones["{name}"].location', [[l[i] for l in ls] for i in range(3)]),
                            (f'pose.bones["{name}"].scale', [[s for s in ss] for _ in range(3)])):
            for i, vals in enumerate(comps):
                fc = act.fcurve_ensure_for_datablock(obj, path, index=i, group_name=grp)
                fc.keyframe_points.clear()
                fc.keyframe_points.add(n)
                co = []
                for fr, v in enumerate(vals):
                    co += [float(fr), float(v)]
                fc.keyframe_points.foreach_set("co", co)
                fc.keyframe_points.foreach_set("interpolation", [bpy.types.Keyframe.bl_rna.properties["interpolation"].enum_items["LINEAR"].value] * n)
                fc.update()
    act.use_frame_range = True
    act.frame_start, act.frame_end = 0, clip_.N
    act.use_cyclic = clip_.loop
    act.pose_markers.clear() if hasattr(act.pose_markers, "clear") else None
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


def requested_clips():
    req = TL.get("requestedClips") or []
    have = {(c.ch, c.name) for c in CLIPS}
    missing = []
    for r in req:
        ch, name = (r.get("who"), r.get("clip")) if isinstance(r, dict) else (r.split("_", 1) + [""])[:2]
        if (ch, name) not in have:
            missing.append(r)
    return req, missing


def contract_clips():
    want = {"david": ["idle", "walk", "talk", "kneel_pick", "sling_windup", "sling_release", "run", "victory", "pray"],
            "goliath": ["idle", "walk", "talk", "taunt", "laugh", "roar", "charge", "hit_react", "fall", "down"]}
    return want


# =============================================================================================== modes
PAPER = (-0.596, 0.596, -1.486, 0.22)          # D8: x min/max, z min/max on the page (edge minus 0.024)
PAGE_FRONT_Z = 0.244                            # the sheet's front edge (CONTRACT §12.4 ground z range)
LOCOMOTION = {"walk", "run", "charge"}


def mesh_points(rig):
    """Evaluated vertices (design coords, character-local) of every mesh of this character in the current pose."""
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in rig.obj.children:
        if o.type != 'MESH' or o.hide_render:
            continue
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        mw = o.matrix_world
        n = len(me.vertices)
        step = max(1, n // 1500)
        for i in range(0, n, step):
            pts.append(to_d(mw @ me.vertices[i].co))
        ev.to_mesh_clear()
    return pts


def clip_checks(rig, cl, frames):
    """Contact / penetration / sliding numbers for clips.json (see ANIMATION.md §2)."""
    out = {}
    ad = rig.obj.animation_data
    keep = ad.action if ad else None
    if ad:
        ad.action = None                 # evaluate the baked basis, not the action written last
    rig.obj.location = (0, 0, 0); rig.obj.rotation_euler = (0, 0, 0)
    step = 2 if cl.N <= 60 else 3
    lows = []
    for fr in range(0, cl.N + 1, step):
        apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
        pts = mesh_points(rig)
        lows.append(min(p.y for p in pts))
        if os.environ.get("DG_DEBUG_LOW") and lows[-1] == min(lows):
            lp = min(pts, key=lambda p: p.y); print("DG_LOW", cl.action, fr, [round(v, 4) for v in lp])
        if fr == cl.N:
            last = pts
    out["meshMinY"] = round(min(lows), 4)                 # < 0 = something sinks into the page
    # foot sliding: horizontal drift of planted toes (y < 1.5 % of height) over the clip; in-place locomotion slides
    # by design (the Director moves the actor), so it reports the stance speed instead
    if cl.name not in LOCOMOTION:
        drift = 0.0
        for side in "LR":
            ref = None
            for basis, M in frames:
                p = rig.pos(M, "toe" + side)
                if p.y < 0.015 * rig.H + 0.004 and rig.pos(M, "foot" + side).y < 0.12 * rig.H:
                    if ref is None:
                        ref = p
                    drift = max(drift, math.hypot(p.x - ref.x, p.z - ref.z))
                else:
                    ref = None
        out["plantedToeDriftMax"] = round(drift, 4)
    if cl.ch == "goliath" and cl.name in ("fall", "down"):
        mx, mz = goliath_fall_mark()
        xs = [p.x + mx for p in last]; zs = [p.z + mz for p in last]
        bb = [round(min(xs), 3), round(max(xs), 3), round(min(zs), 3), round(max(zs), 3)]
        onp = bb[0] >= PAPER[0] and bb[1] <= PAPER[1] and bb[2] >= PAPER[2] and bb[3] <= PAPER[3]
        hits = desert_overlaps([(p.x + mx, p.y, p.z + mz) for p in last])
        out["fallFootprint"] = {"mark": [mx, mz], "yaw": 0.0, "bboxXXZZ": bb, "onPaper": onp, "paper": list(PAPER),
                                "desertOverlap": hits,
                                "desertPenetration": desert_penetration([(p.x + mx, p.y, p.z + mz) for p in last])}
    if cl.ch == "david" and cl.name == "kneel_pick":
        st = brook_stones_local()
        dmin, err = [], []
        for k, fr in enumerate(PICKS):
            M = frames[fr][1]
            d_ = min((rig.pos(M, b, "tail") - st[k]).length for b in ("handR", "fingersR", "fingerTipsR", "thumbR"))
            dmin.append(round(d_, 4))
            chs = cl.fn(rig, fr, cl.N)
            _, yaw_, T_ = kneel_root(fr)                     # the target is in root space; the root turns in this clip
            err.append(round((rig.pos(M, "forearmR", "tail") - (rot_y(Vector(chs["ik.armR"]), yaw_) + T_)).length, 4))
        out["pickHandToStone"] = dmin
        # whole clip at the kneel mark (actor yaw 0): page front edge, brook bank, desert
        mx, mz = kneel_mark()
        zmax, xmin, pen = -9.0, 9.0, {}
        for fr in range(0, cl.N + 1, 4):
            apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
            pts = [(p.x + mx, p.y, p.z + mz) for p in mesh_points(rig)]
            zmax = max(zmax, max(p[2] for p in pts if p[1] < 0.02))
            xmin = min(xmin, min(p[0] for p in pts if p[1] < 0.02))
            for k_, v_ in desert_penetration(pts).items():
                e = pen.setdefault(k_, [0, 0.0]); e[0] += v_[0]; e[1] = max(e[1], v_[1])
        out["kneelOnPage"] = {"lowPointsZmax": round(zmax, 4), "pageFrontZ": PAGE_FRONT_Z, "lowPointsXmin": round(xmin, 4),
                              "desertPenetration": pen}
        out["kneelMark"] = list(kneel_mark())
        out["pickWristIkError"] = err
    reset_pose(rig)
    if ad:
        ad.action = keep
    return out


def goliath_fall_mark():
    acts = sorted(TL["acting"], key=lambda a: a["t"])
    t_f = next(a["t"] for a in acts if a["who"] == "goliath" and a["clip"] == "fall")
    tos = [a["to"] for a in acts if a["who"] == "goliath" and "to" in a and a["t"] < t_f]
    return tuple(tos[-1]) if tos else (0.13, 0.0)


def desert_overlaps(pts_world):
    """Desert pieces (design.json footprints, sheet coords; z = -ys) that a lying body point covers within 0.01."""
    hits = {}
    for pc in DESIGN["desert"]["pieces"]:
        if pc["kind"] in ("water",):
            continue
        # v3 front pieces: bboxSheet is where the piece is DRAWN; footprintSheet is its 3D footprint (x, -z)
        x0, y0, x1, y1 = pc.get("footprintSheet") or pc["bboxSheet"]
        n = sum(1 for (x, y, z) in pts_world if x0 - 0.01 <= x <= x1 + 0.01 and y0 - 0.01 <= -z <= y1 + 0.01)
        if n:
            hits[pc["id"]] = n
    return hits


_DESERT_BVH = None


def desert_bvh():
    """[(object name, BVHTree in Blender world coords)] of every desert.glb mesh. Imported once and removed again, so
    the scene (and the exported character GLBs) stay as they were."""
    global _DESERT_BVH
    if _DESERT_BVH is None:
        from mathutils.bvhtree import BVHTree
        _DESERT_BVH = []
        if os.path.exists(DESERT_GLB):
            before = set(bpy.data.objects)
            bpy.ops.import_scene.gltf(filepath=DESERT_GLB)
            new = [o for o in bpy.data.objects if o not in before]
            bpy.context.view_layer.update()
            dg = bpy.context.evaluated_depsgraph_get()
            for o in new:
                # skip the water film and the importer's bone-shape helper ("Icosphere", banner rigs)
                if o.type == 'MESH' and o.name != "brook" and not o.name.startswith("Icosphere"):
                    ev = o.evaluated_get(dg); me = ev.to_mesh()
                    vs = [o.matrix_world @ v.co for v in me.vertices]
                    _DESERT_BVH.append((o.name, BVHTree.FromPolygons(vs, [tuple(p.vertices) for p in me.polygons])))
                    ev.to_mesh_clear()
            for o in new:
                bpy.data.objects.remove(o, do_unlink=True)
    return _DESERT_BVH


def desert_height(x, z):
    """(height, piece) of the desert surface at page point (x, z) (design coords); (0, None) on the bare page."""
    best = (0.0, None)
    for name, t in desert_bvh():
        hit = t.ray_cast(Vector((x, -z, 2.0)), Vector((0, 0, -1)))
        if hit[0] is not None and hit[0].z > best[0]:
            best = (hit[0].z, name)
    return best


def desert_penetration(pts_world, raised=0.006, tol=0.003):
    """Body points (design, world) that are inside a raised desert piece: {piece: [count, max depth]}."""
    out = {}
    for (x, y, z) in pts_world:
        h, name = desert_height(x, z)
        if name and h > raised and y < h - tol:
            e = out.setdefault(name, [0, 0.0]); e[0] += 1; e[1] = round(max(e[1], h - y), 4)
    return out


def mode_build():
    sc, rigs = open_scene()
    req, missing = requested_clips()
    assert not missing, f"requestedClips not implemented: {missing}"
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    meta = {"fps": FPS, "units": "art-width", "clips": [], "stoneTarget": list(STONE_TARGET), "hitTime": HIT_T, "gravity": G}
    baked = {}
    for cl in CLIPS:
        rig = rigs[cl.ch]
        frames = bake_clip(rig, cl)
        baked[cl.action] = frames
        write_action(rig, cl, frames)
        # loop seam check: pose at frame N vs frame 0 (max bone-tail distance)
        seam = None
        if cl.loop:
            M0, MN = frames[0][1], frames[-1][1]
            seam = max((rig.pos(M0, n, "tail") - rig.pos(MN, n, "tail")).length for n in rig.names)
        # root drift (in-place check) and foot sliding during contact
        rootmax = max(rig.pos(M, "root").length for _, M in frames)
        info = {"action": cl.action, "char": cl.ch, "clip": cl.name, "frames": cl.N, "seconds": round(cl.N / FPS, 3),
                "loop": cl.loop, "rootMotion": cl.root_motion,
                "markers": {k: {"frame": v, "sec": round(v / FPS, 3)} for k, v in cl.markers.items()},
                "loopSeamMaxErr": None if seam is None else round(seam, 6), "rootMaxOffset": round(rootmax, 5),
                "notes": cl.notes}
        # sample a few world positions for verify
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in ("head", "jaw", "handR", "handL", "footL", "toeR", "stone", "slingPouch", "spear", "hips") if n in rig.names}
        info["samples"] = samp
        if cl.action == "david_kneel_pick":
            info["desertEvents"] = [{"frame": fr, "sec": round(fr / FPS, 3), "hide": f"desert/fiveStones/stone{k + 1}"}
                                    for k, fr in enumerate(PICKS)]
        info["checks"] = clip_checks(rig, cl, frames)
        print("DG_CHECK", cl.action, json.dumps(info["checks"]))
        meta["clips"].append(info)
        print(f"DG_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} root={info['rootMaxOffset']}")
    # foot ground check (lowest toe/heel y) per clip
    # --- export each character from a clean copy at the origin
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "dg_anim.blend")
    bpy.ops.wm.save_as_mainfile(filepath=tmp_blend, compress=True)
    for ch in CHARS:
        bpy.ops.wm.open_mainfile(filepath=tmp_blend)
        other = "goliath" if ch == "david" else "david"
        rig = bpy.data.objects[f"{ch}_rig"]
        for o in list(bpy.data.objects):
            if o.name.startswith(other + "_") or o.type == 'CAMERA':
                bpy.data.objects.remove(o, do_unlink=True)
        for a in list(bpy.data.actions):
            if not a.name.startswith(ch + "_"):
                bpy.data.actions.remove(a)
        rig.location = (0, 0, 0); rig.rotation_euler = (0, 0, 0)
        # NLA: one muted track per action so every action is exported with the armature
        rig.animation_data_create()
        rig.animation_data.action = None
        for a in sorted(bpy.data.actions, key=lambda a: a.name):
            tr = rig.animation_data.nla_tracks.new(); tr.name = a.name
            st = tr.strips.new(a.name, 0, a); st.name = a.name
            tr.mute = True
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
        print("DG_EXPORT", ch)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("DG_BUILD_OK", len(meta["clips"]))


def glb_json(path):
    import struct
    b = open(path, "rb").read()
    assert b[:4] == b"glTF"
    l0 = struct.unpack_from("<I", b, 12)[0]
    return json.loads(b[20:20 + l0])


def mode_verify():
    meta = json.load(open(os.path.join(ANIM, "clips.json")))
    want = {c["action"]: c for c in meta["clips"]}
    out = {"glb": {}, "reimport": {}, "sampleErr": {}}
    for ch in CHARS:
        path = os.path.join(ANIM, f"{ch}.glb")
        j = glb_json(path)
        anims = {}
        for a in j.get("animations", []):
            tmax = 0.0
            for s in a["samplers"]:
                acc = j["accessors"][s["input"]]
                tmax = max(tmax, acc["max"][0])
            anims[a["name"]] = {"channels": len(a["channels"]), "seconds": round(tmax, 4), "frames": round(tmax * FPS)}
        out["glb"][ch] = {"bytes": os.path.getsize(path), "animations": anims, "skins": len(j.get("skins", [])),
                          "nodes": len(j["nodes"]), "meshes": len(j.get("meshes", []))}
        # Blender re-import
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.context.scene.render.fps = FPS
        bpy.ops.import_scene.gltf(filepath=path)
        arm = [o for o in bpy.context.scene.objects if o.type == 'ARMATURE'][0]
        acts = {}
        for a in bpy.data.actions:
            acts[a.name] = [round(v, 3) for v in a.frame_range]
        out["reimport"][ch] = acts
        # sample check: imported action vs build samples (bone tail world positions, design coords)
        errs = {}
        for name, info in want.items():
            if info["char"] != ch:
                continue
            act = next((a for a in bpy.data.actions if a.name == name or a.name.startswith(name + "_") or a.name.startswith(name)), None)
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
                    pb = arm.pose.bones[bn]
                    p = arm.matrix_world @ pb.head      # glTF has no bone tails: compare joint positions
                    got = Vector((p.x, p.z, -p.y))
                    worst = max(worst, (got - Vector(exp)).length)
            errs[name] = round(worst, 6)
        out["sampleErr"][ch] = errs
    # contract check
    want_c = contract_clips()
    out["contractMissing"] = {ch: [c for c in want_c[ch] if f"{ch}_{c}" not in out["glb"][ch]["animations"]] for ch in CHARS}
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    for ch in CHARS:
        for nm, a in sorted(out["glb"][ch]["animations"].items()):
            print(f"DG_VERIFY {ch} {nm} {a['frames']}f {a['seconds']}s ch={a['channels']} sampleErr={out['sampleErr'][ch].get(nm)}")
    print("DG_VERIFY_MISSING", json.dumps(out["contractMissing"]))
    print("DG_VERIFY_REIMPORT", json.dumps(out["reimport"]))


# ----------------------------------------------------------------------------------------------- render helpers
DGW = os.environ.get("DG_WORK", "/tmp/dg_work")


def first_existing(*paths):
    for p in paths:
        if p and os.path.exists(p):
            return p
    return None


def char_texture():
    """(path, page_frame) for the characters' UV0. Default: $WORK/tex_chars.png (prepare_textures: the v3 demo colouring
    with the lines erased, A4 page frame). DG_CHAR_TEXTURE overrides with an art-rectangle image (e.g. $DG_WORK/uvproof.png)."""
    if os.environ.get("DG_CHAR_TEXTURE"):
        return os.environ["DG_CHAR_TEXTURE"], False
    p = os.path.join(WORK, "tex_chars.png")
    if os.path.exists(p):
        return p, True
    return first_existing(os.path.join(DGW, "uvproof.png"), os.path.join(DG, "sheet", "demo-colored.png")), False


def desert_texture():
    """Desert pieces (front UV0 = art UV): $WORK/tex_desert.png (erased demo colouring, paper -> sand), page frame."""
    return first_existing(os.environ.get("DG_PAGE_TEXTURE"), os.path.join(WORK, "tex_desert.png"),
                          os.path.join(ROOT, "docs/david-goliath/design/sheet-mock-demo-colour.png"))


def page_texture():
    """The A4 page under everything: Design's baked sand ground (CONTRACT §12.4; brook hole shows the painted page)."""
    return first_existing(os.environ.get("DG_GROUND_TEXTURE"), os.path.join(ROOT, "docs/david-goliath/design/ground-sand-demo.png"),
                          os.path.join(WORK, "tex_desert.png"))


DESIGN = json.load(open(os.path.join(DG, "design.json")))
DECAL_NODES = {}          # char -> image node of the face decal (swapped per clip in the preview)


def tex_material(name, img_path, uv="UVMap", mapping=None, rough=0.8, decal=None):
    m = bpy.data.materials.new(name); m.use_nodes = True; nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = rough
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(img_path, check_existing=True)
    tex.extension = 'EXTEND'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = uv
    src = uvn.outputs["UV"]
    if mapping:
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Location"].default_value = (mapping[0], mapping[1], 0)
        mp.inputs["Scale"].default_value = (mapping[2], mapping[3], 1)
        nt.links.new(src, mp.inputs[0]); src = mp.outputs[0]
    nt.links.new(src, tex.inputs["Vector"])
    col = tex.outputs["Color"]
    if decal:
        dt = nt.nodes.new("ShaderNodeTexImage"); dt.image = bpy.data.images.load(decal, check_existing=True)
        dt.extension = 'CLIP'
        du = nt.nodes.new("ShaderNodeUVMap"); du.uv_map = "decal"
        nt.links.new(du.outputs["UV"], dt.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
        nt.links.new(dt.outputs["Alpha"], mix.inputs["Factor"])
        nt.links.new(col, mix.inputs[6]); nt.links.new(dt.outputs["Color"], mix.inputs[7])
        col = mix.outputs[2]
        m["decal_node"] = dt.name
    nt.links.new(col, bsdf.inputs["Base Color"])
    return m


def set_expression(ch, expr):
    fd = DESIGN["faceDecals"][ch]
    path = os.path.join(ROOT, fd["files"].get(expr, fd["files"][fd["default"]]))
    node = DECAL_NODES.get(ch)
    if node is not None:
        node.image = bpy.data.images.load(path, check_existing=True)


def clip_expression(ch, clip_name):
    fd = DESIGN["faceDecals"][ch]
    return fd["clipExpression"].get(clip_name, fd["default"])


def setup_look(sc, res, desert=True, samples=16):
    """EEVEE look for contact sheet and preview: characters wear the page texture on UV0 and the face decal on UV1,
    the A4 page lies on y = 0 (art rectangle bottom edge on z = 0) and the desert set stands on it."""
    sc.render.engine = 'BLENDER_EEVEE'
    try:
        sc.eevee.taa_render_samples = samples; sc.eevee.use_shadows = True
    except Exception:
        pass
    sc.view_settings.view_transform = 'Standard'; sc.view_settings.exposure = -0.15
    sc.render.resolution_x, sc.render.resolution_y = res; sc.render.resolution_percentage = 100
    sc.render.image_settings.file_format = 'PNG'; sc.render.image_settings.color_mode = 'RGB'
    sc.render.film_transparent = False
    sc.world = bpy.data.worlds.new("W"); sc.world.use_nodes = True
    bg = sc.world.node_tree.nodes["Background"]; bg.inputs[0].default_value = (0.80, 0.86, 0.95, 1); bg.inputs[1].default_value = 0.9
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", 'SUN')); sc.collection.objects.link(sun)
    sun.data.energy = 2.6; sun.data.angle = math.radians(4)
    sun.rotation_euler = (math.radians(42), math.radians(-14), math.radians(-30))
    # characters: one material each (own face decal)
    ctex, cpage = char_texture()
    art = DESIGN["sheet"]["art"]; Wp, Hp = DESIGN["sheet"]["page"]
    amap = (art[0] / Wp, (Hp - art[1] - art[3]) / Hp, art[2] / Wp, art[3] / Hp)    # art UV -> page image UV
    for ch in CHARS:
        fd = DESIGN["faceDecals"][ch]
        m = tex_material(f"anim_{ch}", ctex, mapping=amap if cpage else None,
                         decal=os.path.join(ROOT, fd["files"][fd["default"]]))
        DECAL_NODES[ch] = m.node_tree.nodes[m["decal_node"]]
        for o in bpy.data.objects:
            if o.type == 'MESH' and o.name.startswith(ch + "_"):
                o.data.materials.clear(); o.data.materials.append(m)
    # page
    art = DESIGN["sheet"]["art"]; Wp, Hp = DESIGN["sheet"]["page"]
    px = art[2]
    x0, x1 = -art[0] / px - 0.5, (Wp - art[0]) / px - 0.5
    y1, y0 = (art[1] + art[3]) / px, (art[1] + art[3] - Hp) / px
    me = bpy.data.meshes.new("page")
    me.from_pydata([(x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0)], [], [(0, 1, 2, 3)])
    lay = me.uv_layers.new(name="UVMap")
    for i, uv in enumerate([(0, 0), (1, 0), (1, 1), (0, 1)]):
        lay.data[i].uv = uv
    po = bpy.data.objects.new("page", me); sc.collection.objects.link(po)
    ptex = page_texture()
    me.materials.append(tex_material("anim_page", ptex, rough=0.95))
    tb = bpy.data.meshes.new("table")
    tb.from_pydata([(-4, -4, -0.002), (4, -4, -0.002), (4, 5, -0.002), (-4, 5, -0.002)], [], [(0, 1, 2, 3)])
    to = bpy.data.objects.new("table", tb); sc.collection.objects.link(to)
    tm = bpy.data.materials.new("table"); tm.use_nodes = True
    tm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.36, 0.25, 0.17, 1); tb.materials.append(tm)
    if desert and os.path.exists(DESERT_GLB):
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=DESERT_GLB)
        new = [o for o in bpy.data.objects if o not in before]
        mapping = (art[0] / Wp, (Hp - art[1] - art[3]) / Hp, art[2] / Wp, art[3] / Hp)   # art UV -> page image UV
        md = tex_material("anim_desert", desert_texture(), mapping=mapping, rough=0.9)
        water = bpy.data.materials.new("anim_water"); water.use_nodes = True
        wb = water.node_tree.nodes["Principled BSDF"]
        wb.inputs["Base Color"].default_value = (0.55, 0.75, 0.9, 1); wb.inputs["Roughness"].default_value = 0.08
        wb.inputs["Alpha"].default_value = 0.35
        for o in new:
            if o.type != 'MESH':
                continue
            is_water = any(s.material and "water" in s.material.name for s in o.material_slots)
            o.data.materials.clear(); o.data.materials.append(water if is_water else md)
        for o in new:
            o.select_set(False)
    return po


def camera(sc):
    cam = bpy.data.objects.get("Cam") or bpy.data.objects.new("Cam", bpy.data.cameras.new("Cam"))
    if cam.name not in sc.collection.objects:
        sc.collection.objects.link(cam)
    sc.camera = cam; cam.data.clip_start = 0.01; cam.data.clip_end = 50
    return cam


def look(cam, target_d, cam_d, lens=35):
    cam.data.type = 'PERSP'; cam.data.lens = lens
    cam.location = to_bl(cam_d)
    cam.rotation_euler = (to_bl(target_d) - cam.location).to_track_quat('-Z', 'Y').to_euler()


def apply_basis(rig, basis):
    for n in rig.names:
        pb = rig.obj.pose.bones[n]
        pb.rotation_mode = 'QUATERNION'
        q, l, s = basis[n]
        pb.rotation_quaternion = q; pb.location = l; pb.scale = (s, s, s)


def reset_pose(rig):
    for pb in rig.obj.pose.bones:
        pb.rotation_mode = 'QUATERNION'
        pb.rotation_quaternion = (1, 0, 0, 0); pb.location = (0, 0, 0); pb.scale = (1, 1, 1)


def place_rig(rig, x, z, yaw_deg):
    rig.obj.location = to_bl(V(x, 0, z))
    rig.obj.rotation_euler = (0, 0, math.radians(yaw_deg))


def mode_contact():
    sc, rigs = open_scene()
    setup_look(sc, (440, 440), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    for cl in CLIPS:
        rig = rigs[cl.ch]
        other = rigs["goliath" if cl.ch == "david" else "david"]
        other.obj.hide_render = True
        for o in other.obj.children:
            o.hide_render = True
        for o in rig.obj.children:
            o.hide_render = False
        rig.obj.hide_render = False
        place_rig(rig, 0, 0, 0)
        set_expression(cl.ch, clip_expression(cl.ch, cl.name))
        frames = bake_clip(rig, cl)
        picks = sorted(set([0, cl.N] + [int(round(cl.N * k / 5)) for k in range(1, 5)] + list(cl.markers.values())))
        while len(picks) > 8:
            # drop evenly spaced non-marker frames first
            cand = [p for p in picks if p not in cl.markers.values() and p not in (0, cl.N)]
            if not cand:
                break
            picks.remove(cand[len(cand) // 2])
        H = rig.H
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": []}
        for fr in picks:
            apply_basis(rig, frames[fr][0])
            bpy.context.view_layer.update()
            tgt = V(0, H * 0.5, 0.0)
            yaw = math.radians(35)
            dist = H * 1.8
            if cl.action in ("goliath_fall", "goliath_down"):
                tgt = V(0, 0.16, 0.02); dist = 1.25; yaw = math.radians(62)
            if cl.action == "david_kneel_pick":
                yaw = math.radians(-35)          # from his right: the reaching hand
            if cl.action == "david_sling_release":
                tgt = V(0, 0.22, 0.10); dist = 0.72; yaw = math.radians(80)
            look(cam, tgt, tgt + V(math.sin(yaw) * dist, H * 0.15, math.cos(yaw) * dist), lens=40)
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            mk = ",".join(k for k, v in cl.markers.items() if v == fr)
            row["frames"].append({"f": fr, "file": fn, "marker": mk})
        reset_pose(rig)
        rows.append(row)
        print("DG_CONTACT_ROW", cl.action, picks)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """Work renders for judging poses (not shipped). DG_PROBE="action:f1,f2:view[@x,z][#bone];..."
    view = front | q3 (35 deg) | side | back | top | low; '#bone' = close-up on that bone; '@x,z' = world mark (yaw 0)."""
    sc, rigs = open_scene()
    setup_look(sc, (520, 520), desert=os.environ.get("DG_PROBE_DESERT", "1") == "1", samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    clips = {cl.action: cl for cl in CLIPS}
    baked = {}
    out = []
    for item in os.environ.get("DG_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        action, frames, view = parts[0], parts[1], parts[2] if len(parts) > 2 else "q3"
        bone = None; mark = (0.0, 0.0)
        if "#" in view:
            view, bone = view.split("#")
        if "@" in view:
            view, m = view.split("@"); mark = tuple(float(v) for v in m.split(","))
        cl = clips[action]; rig = rigs[cl.ch]
        for ch, r in rigs.items():
            vis = ch == cl.ch
            r.obj.hide_render = not vis
            for o in r.obj.children:
                o.hide_render = not vis
        if action not in baked:
            baked[action] = bake_clip(rig, cl)
        set_expression(cl.ch, clip_expression(cl.ch, cl.name))
        place_rig(rig, mark[0], mark[1], 0)
        for fr in [int(v) for v in frames.split(",")]:
            fr = min(fr, cl.N)
            apply_basis(rig, baked[action][fr][0]); bpy.context.view_layer.update()
            H = rig.H
            yaw = {"front": 0, "q3": 35, "side": 90, "back": 180, "top": 20, "low": 20, "lside": -90, "q3l": -35}[view]
            tgt = V(mark[0], H * 0.5, mark[1]); dist = H * 2.4; hgt = H * 0.15
            if bone:
                tgt = to_d(rig.obj.matrix_world @ rig.obj.pose.bones[bone].head); dist = H * 0.6; hgt = 0.0
            if cl.root_motion and cl.ch == "goliath":
                tgt = V(mark[0], 0.12, mark[1] + 0.30); dist = 1.5
            if view == "top":
                hgt = dist * 1.4
            if view == "low":
                hgt = -tgt.y + 0.01
            a_ = math.radians(yaw)
            look(cam, tgt, tgt + V(math.sin(a_) * dist, hgt, math.cos(a_) * dist), lens=40)
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("DG_PROBE", len(out))


# ----------------------------------------------------------------------------------------------- performance (preview)
NATURAL_SPEED = {}      # filled from the clips: locomotion speed in units/s (stride / stance time)


def clip_speed(cl):
    sp = {"david_walk": (0.060, 0.58, 24), "david_run": (0.070, 0.40, 16), "goliath_walk": (0.10, 0.64, 66),
          "goliath_charge": (0.15, 0.60, 60)}
    if cl.action in sp:
        L, duty, N = sp[cl.action]
        return L / (duty * N / FPS)
    return None


def yaw_to(dx, dz):
    return math.degrees(math.atan2(dx, dz))


def angle_lerp(a, b, t):
    d = (b - a + 180) % 360 - 180
    return a + d * t


class Actor:
    def __init__(self, who, x, z):
        self.who = who; self.x, self.z = x, z
        self.yaw = 0.0
        self.cur = None; self.cur_t0 = 0.0; self.cur_rate = 1.0
        self.prev = None; self.prev_t0 = 0.0; self.prev_rate = 1.0; self.blend_t0 = 0.0; self.blend = 0.0
        self.move = None        # (t0, t1, x0, z0, x1, z1)
        self.face = "viewer"


def mode_preview():
    sc, rigs = open_scene()
    res = (640, 360)
    setup_look(sc, res, samples=int(os.environ.get("DG_PREVIEW_SAMPLES", "8")))
    cam = camera(sc)
    clips = {cl.action: cl for cl in CLIPS}
    print("DG_PREVIEW baking clips", flush=True)
    baked = {a: bake_clip(rigs[cl.ch], cl) for a, cl in clips.items()}
    D = json.load(open(os.path.join(DG, "design.json")))
    actors = {ch: Actor(ch, D["characters"][ch]["sheetX"], 0.0) for ch in CHARS}
    acting = sorted(TL["acting"], key=lambda a: a["t"])
    shots = TL["shots"]
    dur = TL["duration"]
    nfr = int(round(dur * FPS))
    out = os.path.join(WORK, "preview"); os.makedirs(out, exist_ok=True)
    for fn in os.listdir(out):
        os.remove(os.path.join(out, fn))
    nxt = {}
    for i, a in enumerate(acting):
        later = [b["t"] for b in acting[i + 1:] if b["who"] == a["who"]]
        nxt[i] = later[0] if later else dur
    ai = 0
    stone_obj = bpy.data.objects["david_stone"]
    brook_stones = [bpy.data.objects.get(f"stone{k}") for k in range(1, 6)]
    picks_t0 = None
    stone_visible = False
    log = []
    stage = []

    def sample(action, t_local, loop):
        fr = baked[action]
        N = len(fr) - 1
        f = t_local * FPS
        if loop:
            f = f % N
        else:
            f = min(max(f, 0.0), N)
        i0 = int(math.floor(f)); i1 = min(i0 + 1, N); w = f - i0
        b0, b1 = fr[i0][0], fr[i1][0]
        return {n: [b0[n][0].slerp(b1[n][0], w), b0[n][1].lerp(b1[n][1], w), lerp(b0[n][2], b1[n][2], w)] for n in b0}

    for k in range(nfr):
        t = k / FPS
        while ai < len(acting) and acting[ai]["t"] <= t + 1e-6:
            a = acting[ai]; A = actors[a["who"]]
            name = f"{a['who']}_{a['clip']}"
            if A.cur is not None:
                A.prev, A.prev_t0, A.prev_rate = A.cur, A.cur_t0, A.cur_rate
                A.blend_t0, A.blend = a["t"], a.get("blend", 0.25)
            A.cur, A.cur_t0, A.cur_rate = name, a["t"], 1.0
            A.face = a.get("face", A.face)
            if "to" in a:
                x1, z1 = a["to"]
                A.move = (a["t"], nxt[ai], A.x, A.z, x1, z1)
                dist = math.hypot(x1 - A.x, z1 - A.z)
                v_nat = clip_speed(clips[name])
                if v_nat and nxt[ai] > a["t"]:
                    v = dist / (nxt[ai] - a["t"])
                    A.cur_rate = min(1.5, max(0.5, v / v_nat))
                    log.append({"t": a["t"], "who": a["who"], "clip": a["clip"], "speedNeeded": round(v, 4),
                                "speedNatural": round(v_nat, 4), "rateUsed": round(A.cur_rate, 3)})
            else:
                A.move = None
            if name == "david_kneel_pick":
                picks_t0 = a["t"]
            ai += 1
        # update positions / facing
        for ch, A in actors.items():
            moving = False
            if A.move:
                t0, t1, x0, z0, x1, z1 = A.move
                s = min(1.0, (t - t0) / max(1e-6, t1 - t0))
                nx, nz = lerp(x0, x1, s), lerp(z0, z1, s)
                if s < 1.0 and math.hypot(x1 - x0, z1 - z0) > 1e-4:
                    moving = True
                    want = yaw_to(x1 - x0, z1 - z0)
                A.x, A.z = nx, nz
            if not moving:
                if A.face == "viewer":
                    want = 0.0
                else:
                    o = actors[A.face] if A.face in actors else None
                    want = yaw_to(o.x - A.x, o.z - A.z) if o else 0.0
            A.yaw = angle_lerp(A.yaw, want, 1 - math.exp(-(1 / FPS) / 0.12))
        # poses
        for ch, A in actors.items():
            rig = rigs[ch]
            cl = clips[A.cur]
            basis = sample(A.cur, (t - A.cur_t0) * A.cur_rate, cl.loop)
            if A.prev and A.blend > 0 and t - A.blend_t0 < A.blend:
                pc = clips[A.prev]
                pb_ = sample(A.prev, (t - A.prev_t0) * A.prev_rate, pc.loop)
                w = smooth((t - A.blend_t0) / A.blend)
                basis = {n: [pb_[n][0].slerp(basis[n][0], w), pb_[n][1].lerp(basis[n][1], w), lerp(pb_[n][2], basis[n][2], w)] for n in basis}
            apply_basis(rig, basis)
            place_rig(rig, A.x, A.z, A.yaw)
        # stones: desert stone k disappears when David's hand closes on it (pick k); his own stone shows from pick5
        # until the sling_release clip is left (CONTRACT / ANIMATION.md §4)
        if picks_t0 is not None:
            for si, ob in enumerate(brook_stones):
                if ob is not None:
                    ob.hide_render = t >= picks_t0 + PICKS[si] / FPS
            if t >= picks_t0 + PICKS[4] / FPS and actors["david"].cur in ("david_kneel_pick", "david_walk", "david_idle",
                                                                            "david_talk", "david_run", "david_sling_windup",
                                                                            "david_sling_release"):
                stone_visible = True
        if stone_visible and t > picks_t0 + 4 and actors["david"].cur != "david_sling_release" and t > 72.6:
            stone_visible = False
        stone_obj.hide_render = not stone_visible
        for ch, A in actors.items():
            set_expression(ch, clip_expression(ch, A.cur.split("_", 1)[1]))
        bpy.context.view_layer.update()
        if k % 6 == 0:          # stage check: nobody walks through the desert pieces or off the page front
            for ch in CHARS:
                pts = [(p.x, p.y, p.z) for p in mesh_points(rigs[ch])]
                pen = {n: v for n, v in desert_penetration(pts).items() if not n.startswith("stone")}
                zmax = max(p[2] for p in pts if p[1] < 0.02) if any(p[1] < 0.02 for p in pts) else None
                if pen or (zmax is not None and zmax > PAGE_FRONT_Z):
                    stage.append({"t": round(t, 2), "who": ch, "clip": actors[ch].cur, "desert": pen,
                                  "lowZmax": None if zmax is None else round(zmax, 4)})
        # camera
        shot = next((s for s in shots if s["t0"] <= t < s["t1"]), shots[-1])
        cmr = shot["camera"]
        tg = cmr["target"]

        def actor_pt(ch):
            A = actors[ch]; return V(A.x, rigs[ch].H * 0.55, A.z)
        if tg == "both":
            target = (actor_pt("david") + actor_pt("goliath")) / 2; target.y = 0.28
        elif tg == "stone":
            sb = rigs["david"].obj.pose.bones["stone"]
            target = to_d(rigs["david"].obj.matrix_world @ sb.head)
        else:
            target = actor_pt(tg)
        yaw = cmr.get("yawDeg", 0.0)
        if cmr["type"] == "orbit":
            yaw += 8.0 * (t - shot["t0"])
        if cmr["type"] == "fixed":
            if not hasattr(mode_preview, "_fixed") or mode_preview._fixed[0] != shot["id"]:
                mode_preview._fixed = (shot["id"], target.copy())
            target = mode_preview._fixed[1]
        a_ = math.radians(yaw)
        dist = cmr.get("dist", 1.2)
        cpos = V(target.x + math.sin(a_) * dist, cmr.get("height", 0.3), target.z + math.cos(a_) * dist)
        look(cam, target, cpos, lens=30)
        rng = os.environ.get("DG_PREVIEW_RANGE")          # "t0,t1[,step]" seconds: work renders of a part only
        if rng:
            r = [float(v) for v in rng.split(",")]
            if not (r[0] <= t < r[1]) or (len(r) > 2 and k % int(r[2])):
                continue
        sc.render.filepath = os.path.join(out, f"f_{k + 1:04d}.png")
        bpy.ops.render.render(write_still=True)
        if rng:
            print("DG_PREVIEW_RENDERED", k, flush=True)
        if k % 150 == 0:
            print(f"DG_PREVIEW frame {k}/{nfr}", flush=True)
    json.dump({"frames": nfr, "res": res, "locomotion": log, "stageViolations": stage},
              open(os.path.join(WORK, "preview.json"), "w"), indent=1)
    print("DG_PREVIEW_STAGE", len(stage), json.dumps(stage[:12]))
    print("DG_PREVIEW_DONE", nfr)


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "preview": mode_preview, "probe": mode_probe}[MODE]()
