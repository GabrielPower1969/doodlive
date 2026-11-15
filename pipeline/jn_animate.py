"""Jonah skeletal animation (Animation role, story pack `jonah`).

Built on the shared kit (pipeline/story_kit/animation.py) the way pipeline/ru_animate.py is. Two halves in one file:

* Under Blender (headless) it opens `assets/jonah/model/characters.blend` (Characters role's rigs), builds every clip
  of docs/jonah/CONTRACT.md §4 as an action `<char>_<clip>` and exports `assets/jonah/anim/{jonah,captain,fish}.glb`
  (character + skin + one glTF animation per action) and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/jn_animate.py all        # build + verify + contact sheet + freshness check
    python3 pipeline/jn_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/jn_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/jn_animate.py contact    # anim/contact_sheet.png (key poses per clip, on the coast set)
    JN_PROBE="jonah_refuse:0,30,60:q3" python3 pipeline/jn_animate.py probe        # work renders ($JN_ANIM_WORK/probe.png)
    JN_PROBE="pair:captain_heave:jonah_fall_in:0.10:30:tandem" python3 pipeline/jn_animate.py probe
        pair modes: face (default; A and B face each other), tandem (B stands `dist` in front of A, both face the
        same way), lie (B lies curled `dist` in front of A, A faces B, B faces the viewer). A pair frame refers to A;
        B is sampled at frame - JN_PAIR_LAG (heave -> fall_in: 21).
    JN_ONLY=jonah_sleep,captain_shake  (with build: bake + check a subset, no export)

How the motion is made (the script is the source, no hand-placed keys): see ru_animate.py. Each clip is a function
frame -> channels (rotations in DESIGN axes in the bone's rest frame: rx ry rz bend raise swing twist curl; offsets
tx ty tz; scale s / sy). Legs and arms use two-bone IK where a hand or foot must be somewhere. Seated and lying clips
use `settle` (a skinned proxy of the body: the lowest vertex of the named bones is put on the page). Secondary motion
(coat panels, belt end, seaweed, head-wrap tail, sash end, the fish's dorsal fin) is a damped spring chain.
The fish is a new rig type: no legs, a body chain root -> body1 -> body2 -> body3 -> tail, a jaw (+rx = open), side
fins and a dorsal fin. Its swim is a travelling body wave (yaw per segment, phase lag head -> tail).
Intermediates: $JN_ANIM_WORK (default /tmp/jonah_anim).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JN = os.path.join(ROOT, "assets/jonah")
MODEL = os.path.join(JN, "model")
ANIM = os.path.join(JN, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
SET_GLB = os.path.join(MODEL, "coast.glb")
TIMELINE = os.path.join(JN, "timeline.json")
REGIONS_JSON = os.path.join(MODEL, "regions_characters.json")
FACE_DIR = os.path.join(ROOT, "docs/jonah/design/faces")
WORK = os.environ.get("JN_ANIM_WORK") or "/tmp/jonah_anim"
ENV = "JN_"                      # env-var / log prefix the story_kit functions use (JN_PROBE_*, JN_NOSET)
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FPS = 30
CHARS = ("jonah", "captain", "fish")

# stage distances the two-actor clips are fitted to (root to root, art-width units)
HEAVE_D = 0.10       # captain_heave -> jonah_fall_in: Jonah stands 0.10 in front of the captain, both face the same way
SHAKE_D = 0.19       # captain_shake_awake -> jonah_sleep_curl: Jonah's root 0.10 in front of the captain, lying along
                     # the captain's facing (head toward him), Jonah facing the viewer (side-on to the captain)
HEAVE_LAG = 21       # jonah_fall_in starts 0.7 s (21 f) after captain_heave (story.py S04: dt=0.7)

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


# =============================================================================================== orchestration (python3)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                      # noqa: E402
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "animation")   # shared animation functions (docs/STORY-KIT.md)
_kit_ik_limb = ik_limb                      # the kit's two-bone limb IK, wrapped below (two-target arms)


def run_blender(mode, *extra):
    """Kit run_blender + `nice -n 10` (one Blender at a time, low priority)."""
    cmd = ["nice", "-n", "10", BLENDER, "-b", "--factory-startup", "--python", os.path.abspath(__file__), "--", mode, *extra]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith((ENV, "Traceback", "Error", "  File")) or "Error" in ln]
    print("\n".join(tail[-300:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def fresh_check():
    """The Characters role may re-run jn_characters.py: the anim GLBs must be newer than the model files."""
    src = [BLEND] + [os.path.join(MODEL, f"{c}.glb") for c in CHARS]
    newest = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    outs = [os.path.join(ANIM, f"{c}.glb") for c in CHARS]
    stale = [o for o in outs if (not os.path.exists(o)) or os.path.getmtime(o) < newest]
    print("JN_FRESH", "STALE " + ", ".join(os.path.basename(o) for o in stale) if stale else
          "OK (anim exports newer than the model files)")
    return not stale


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
    if mode in ("all", "fresh"):
        fresh_check()


def compose_contact():
    from PIL import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(WORK, "contact", "contact.json")))
    cell, pad, lab = 150, 5, 34
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
    d.text((pad, 14), "Jonah - key poses per clip (30 fps; frame / seconds; marker names in red; pair rows = two "
                      "actors at their story distance)", fill=(40, 30, 20), font=font)
    y = 60
    for r in rows:
        d.text((pad, y + 6), r["action"], fill=(40, 30, 20), font=font)
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
    sheet = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    sheet.save(out, optimize=True)
    print("JN_CONTACT", out, sheet.size)


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

BLINK_SHAPE = [1.0, 6.5, 12.8, 12.8, 8.0, 3.5, 1.0]      # frames 0..6: fast close, short hold, slower open
CLOSED = {"jonah": 12.78, "captain": 12.78, "fish": 13.06}  # RIG.md: eyelids.sy closed


# =============================================================================================== rig model (pure python FK)
class Rig:
    """ru_animate.Rig + da_animate's skinned body proxy (for `settle`: seated / lying clips touch the page)."""
    H_OF = {"jonah": 0.36, "captain": 0.38, "fish": 0.21}

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
        self.rest_inv = {n: m.inverted() for n, m in self.rest.items()}
        self.rel = {n: (self.rest[self.parent[n]].inverted() @ self.rest[n]) if self.parent[n] else self.rest[n].copy() for n in self.names}
        self.head = {n: to_d(self.rest[n].translation) for n in self.names}
        self.tail = {b.name: to_d(b.tail_local) for b in bones}
        self.dir = {n: (self.tail[n] - self.head[n]).normalized() for n in self.names}
        self.length = {b.name: b.length for b in bones}
        self.children = {n: [c for c in self.names if self.parent[c] == n] for n in self.names}
        self.H = self.H_OF[ch]
        self.fish = ch == "fish"
        self.staff_foot = None
        self.prop_axis = {}
        body = bpy.data.objects[f"{ch}_body"]
        mw = obj.matrix_world.inverted() @ body.matrix_world
        gname = {g.index: g.name for g in body.vertex_groups}
        vs = body.data.vertices
        step = max(1, len(vs) // 1600)
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

        self.footproxy = {"L": [], "R": []}
        for v in vs:
            ws = [(gname[g.group], g.weight) for g in v.groups if g.weight > 1e-3 and gname.get(g.group) in self.rest]
            tot = sum(w for _, w in ws)
            if tot <= 0 or ch == "fish":
                continue
            co = mw @ v.co
            if co.z > 0.09:
                continue
            for side in "LR":
                if any(b in ("foot" + side, "toe" + side, "shin" + side) for b, _ in ws):
                    self.footproxy[side].append((co, [(b, w / tot) for b, w in ws]))

        sw = bpy.data.objects.get(f"{ch}_seaweed")
        if sw is not None:
            mw2 = obj.matrix_world.inverted() @ sw.matrix_world
            gn2 = {g.index: g.name for g in sw.vertex_groups}
            for v in list(sw.data.vertices)[::4]:
                ws = [(gn2[g.group], g.weight) for g in v.groups if g.weight > 1e-3 and gn2.get(g.group) in self.rest]
                if not ws and sw.parent_type == 'BONE':
                    ws = [(sw.parent_bone, 1.0)]
                if ws:
                    tot = sum(w for _, w in ws)
                    self.proxy.append((mw2 @ v.co, [(b, w / tot) for b, w in ws], "prop:seaweed"))

    def skin(self, M, bones=None, prop=False):
        """Deformed proxy points (design coords, root space) - only vertices whose dominant bone is in `bones`;
        the seaweed prop's points only when `prop` (it is hidden in most clips)."""
        out = []
        for co, ws, dom in self.proxy:
            if (bones is not None and dom not in bones) or (dom == "prop:seaweed" and not prop):
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
                R = R @ rot_d(hz if n[-1] == "L" else -hz, g("curl"))      # + = close the hand
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
            sc = Vector((chs.get(f"{n}.sx", s), chs.get(f"{n}.sy", s), chs.get(f"{n}.sz", s)))
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


# =============================================================================================== clip library
class Clip:
    def __init__(self, ch, name, N, loop, fn, markers=None, notes="", speed=None, props=None, backwards=False,
                 seated=False, root_motion=None):
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = markers or {}
        self.notes = notes
        self.extra = notes.startswith("EXTRA")
        self.speed = speed           # (stride L, duty) for in-place locomotion -> natural speed
        self.props = props or []     # props this clip is posed for (seaweed)
        self.backwards = backwards
        self.seated = seated         # seated / lying / kneeling: meshMinY >= -0.008 is a hard check
        self.root_motion = root_motion   # text: the root bone travels (fall_in, tumble_out, fish one-shots)

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
_PAY = {}
KNEEL = {"jonah": dict(KY=0.021, kz=0.016, thigh_back=12.0, shin_slope=24.0)}


# =============================================================================================== acting helpers
ARM_REST = {"jonah": -22.0, "captain": -14.0}
RIGS = {}                    # filled by open_scene(): partner-aware clips read the other actor's pose (heave)


def h_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    """Standing human base (da_animate.h_base): breathing, arms relaxed by the sides."""
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
    return c


def hands_clasped(c, rig, at, wring=0.0, w=1.0, space="root"):
    arm_ik(c, "L", at + V(0.011 + 0.002 * wring, 0.000, -0.004), V(0.7, -0.6, -0.4), space, w)
    arm_ik(c, "R", at + V(-0.011 + 0.002 * wring, -0.004, 0.000), V(-0.7, -0.6, -0.4), space, w)


def folded_arms(c, rig, w=1.0, loose=0.0):
    """Arms crossed over the chest (chest space). loose 0..1 = lower and looser (Jonah's grumpy idle)."""
    k = 1.0 if rig.ch == "jonah" else 1.12
    fz = 0.0 if rig.ch == "jonah" else 0.022          # the captain's chest and belly stand out further
    arm_ik(c, "L", V(-0.024 * k, -0.020 * k - 0.012 * loose, 0.036 * k + fz + 0.004 * loose), V(0.9, -0.5, 0.2), "chest", w)
    arm_ik(c, "R", V(0.026 * k, -0.028 * k - 0.012 * loose, 0.032 * k + fz + 0.004 * loose), V(-0.9, -0.5, 0.2), "chest", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 4, w); c["handR.bend"] = lerp(c.get("handR.bend", 6), 4, w)
    fingers(c, "L", lerp(c.get("fingersL.curl", 22), 34, w)); fingers(c, "R", lerp(c.get("fingersR.curl", 22), 34, w))


def look_keys(c, keys, f, N, loop=True, neck=0.4, head=0.6, lag=4):
    c["neck.ry"] = c.get("neck.ry", 0.0) + neck * K(keys, f, N, loop)
    c["head.ry"] = c.get("head.ry", 0.0) + head * KL(keys, f, N, loop, lag=lag)


def talk_jaw(c, f, N, seed, amp=(5, 13)):
    jk, beats = syllables(N, seed, amp=amp)
    c["jaw.rx"] = jaw_from(jk, f, N)
    return beats


def eyes(c, rig, shut):
    """Eyelids: 0 = open, 1 = closed (RIG.md closed value per character)."""
    c["eyelids.sy"] = lerp(1.0, CLOSED[rig.ch], max(0.0, min(1.0, shut)))


def blink_ch(c, rig, f, N, at, loop=True, base=1.0, slow=1.0):
    blink(c, f, N, at, loop, base, slow)
    if rig.ch == "fish":
        c["eyelids.sy"] = 1.0 + (c["eyelids.sy"] - 1.0) * (CLOSED["fish"] - 1.0) / 11.8


def gait(rig, f, N, L, lift, duty, offsetR=0.5, offsetL=0.0, heel=10.0, toeoff=24.0, out=None, lift_shape=1.0,
         spread=0.0, fwd=0.0):
    """da_animate.gait: kit gait + roll about the contact point (heel while the toes are up, ball while the heel is
    up), so a planted foot does not skate as it rolls."""
    out = out if out is not None else {}
    for side, off in (("L", offsetL), ("R", offsetR)):
        p = (f / N + off) % 1.0
        base = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        if p < duty:
            s_ = p / duty
            z = L / 2 - L * s_
            pitch = -heel * (1 - smooth(s_ / 0.15)) + toeoff * smooth((s_ - 0.7) / 0.3)
            y = planted_ankle_y(rig, side, pitch)
            contact = True
        else:
            s_ = (p - duty) / (1 - duty)
            z = -L / 2 + L * smooth(s_)
            pitch = lerp(toeoff, -heel, smooth(s_ * 1.1))
            y = planted_ankle_y(rig, side, pitch) + lift * math.sin(math.pi * min(1.0, s_)) ** lift_shape
            contact = False
        z -= pivot_dz(rig, side, pitch)
        out["leg" + side] = (V(base.x + sx * spread, y, base.z + z + fwd), pitch, contact, p)
    return out


def pivot_dz(rig, side, pitch):
    """da_animate.pivot_dz: forward shift of the planted contact point when the foot pitches (heel / ball pivot)."""
    heel, ball, _ = foot_points(rig, side)
    q = heel if pitch < 0 else ball
    R = rot_d((1, 0, 0), pitch)
    return (CI @ (R @ (C @ q))).z - q.z


def default_pole(limb):
    sx = 1 if limb.endswith("L") else -1
    return {"leg": V(0.15 * sx, 0, 1), "arm": V(0.6 * sx, -0.6, -0.5)}[limb[:3]]


def collapse_ikb(c):
    """A two-target arm whose blend is complete becomes a plain one (so it can be mixed again)."""
    c = dict(c)
    for side in "LR":
        if c.get("ikbw.arm" + side, 0.0) >= 0.999:
            c["ik.arm" + side] = c.pop("ikb.arm" + side); c["ikspace.arm" + side] = c.pop("ikbspace.arm" + side)
            if "ikbpole.arm" + side in c:
                c["pole.arm" + side] = c.pop("ikbpole.arm" + side)
            c.pop("ikbw.arm" + side, None)
        elif c.get("ikbw.arm" + side) is not None and c["ikbw.arm" + side] <= 1e-3:
            for k in ("ikb.arm", "ikbspace.arm", "ikbpole.arm", "ikbw.arm"):
                c.pop(k + side, None)
    return c


def mix(a, b, w):
    """Channel dicts a -> b by w (da_animate.mix; IK legs fade in / out too; an arm whose IK space differs between
    a and b becomes a two-target arm, blended in world space by ik_limb). Strings switch at 0.5."""
    if w <= 1e-6:
        return dict(a)
    if w >= 1 - 1e-6:
        return dict(b)
    a, b = collapse_ikb(a), collapse_ikb(b)
    out = {}
    for k in set(a) | set(b):
        va, vb = a.get(k), b.get(k)
        if k == "settle":
            continue
        if isinstance(va, str) or isinstance(vb, str):
            out[k] = (vb if w >= 0.5 else va) or va or vb
        elif k.startswith("pole.") and (va is None or vb is None):
            d = default_pole(k[5:])
            out[k] = vlerp(d if va is None else va, d if vb is None else vb, w)
        elif isinstance(va, Vector) or isinstance(vb, Vector):
            out[k] = vb if va is None else (va if vb is None else vlerp(va, vb, w))
        else:
            dflt = 1.0 if (k.endswith(".s") or k.endswith(".sy") or k.startswith("ikw.")) else 0.0
            out[k] = lerp(dflt if va is None else va, dflt if vb is None else vb, w)
    for limb in ("armL", "armR", "legL", "legR"):
        k = "ik." + limb
        if (k in a) != (k in b):
            wa = a.get("ikw." + limb, 1.0) if k in a else 0.0
            wb = b.get("ikw." + limb, 1.0) if k in b else 0.0
            out["ikw." + limb] = lerp(wa, wb, w)
    for side in "LR":
        k = "ik.arm" + side
        sa_, sb_ = a.get("ikspace.arm" + side, "root"), b.get("ikspace.arm" + side, "root")
        if k in a and k in b and sa_ != sb_:
            out[k] = a[k]; out["ikspace.arm" + side] = sa_
            out["ikb.arm" + side] = b[k]; out["ikbspace.arm" + side] = sb_; out["ikbw.arm" + side] = w
            out["pole.arm" + side] = a.get("pole.arm" + side, default_pole("arm" + side))
            out["ikbpole.arm" + side] = b.get("pole.arm" + side, default_pole("arm" + side))
            out["ikw.arm" + side] = lerp(a.get("ikw.arm" + side, 1.0), b.get("ikw.arm" + side, 1.0), w)
    sa, sb = a.get("settle"), b.get("settle")
    if sa or sb:
        bone, vb_, tgt, wa_ = sa or sb
        out["settle"] = (bone, vb_, tgt, lerp(sa[3] if sa else 0.0, sb[3] if sb else 0.0, w))
    return out


def arm_ik2(c, side, target, pole, space, wB):
    """Second IK target for an arm, blended with the first in world space (wB = share of this one)."""
    c[f"ikb.arm{side}"] = Vector(target); c[f"ikbspace.arm{side}"] = space; c[f"ikbw.arm{side}"] = wB
    c[f"ikbpole.arm{side}"] = Vector(pole)


def arm_wave_up(c, side, f, N, cycles, high=1.0, w=1.0, amp=1.0):
    """Raised arm waving from the elbow (open hand, palm forward). high 0 = shoulder height (shy), 1 = overhead."""
    sx = 1 if side == "L" else -1
    ph = wave(f, N, cycles)
    c[f"upperArm{side}.raise"] = lerp(c.get(f"upperArm{side}.raise", -22), 40 + 70 * high, w)
    c[f"upperArm{side}.bend"] = lerp(c.get(f"upperArm{side}.bend", 8), 24 + 4 * high, w)
    c[f"forearm{side}.bend"] = lerp(c.get(f"forearm{side}.bend", 26), 84 - 44 * high + 20 * amp * ph, w)
    c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", -10 * sx), -70 * sx, w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -10 + 16 * amp * wave(f, N, cycles, -0.12), w)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 6, w))


# --------------------------------------------------------------------------------------------- seated / lying family
SEAT_HIPS_Y = -0.150        # hips joint drops from 0.187 to ~0.037 when Jonah sits on the page (settle fine-tunes it)


def seat_legs(rig, c, legs="up", w=1.0, spread=0.0, kneeL=0.0, kneeR=0.0, toe=0.0):
    """Jonah sitting: legs 'up' (knees up, soles flat) or 'out' (legs out in front, heels down). Hips down, settle on.
    kneeL / kneeR pull a foot in (0..1) for 'out' (one knee up)."""
    for side in "LR":
        sx = 1 if side == "L" else -1
        b = rig.head["foot" + side]
        if legs == "up":
            pt = 0.0 + toe
            tgt = V(b.x + sx * (0.010 + spread), planted_ankle_y(rig, side, pt), 0.092)
            pole = V(0.25 * sx, 1.0, 0.4)
        else:
            pull = kneeL if side == "L" else kneeR
            pt = lerp(-62.0, -10.0, pull) + toe
            tgt = V(b.x + sx * (0.016 + spread), planted_ankle_y(rig, side, pt), lerp(0.150, 0.090, pull))
            pole = V(0.2 * sx, 1.0, 0.25)
        cur = c.get(f"ik.leg{side}")
        c[f"ik.leg{side}"] = tgt if (cur is None or w >= 0.999) else vlerp(cur, tgt, w)
        c[f"foot{side}.pitch"] = lerp(c.get(f"foot{side}.pitch", 0.0), pt, w)
        c[f"pole.leg{side}"] = pole
    c["hips.ty"] = c.get("hips.ty", 0.0) + SEAT_HIPS_Y * w
    c["hips.tz"] = c.get("hips.tz", 0.0) - 0.012 * w
    c["settle"] = ("hips", ("hips", "thighL", "thighR", "spine"), 0.0010, w)
    c["coatfollow"] = max(c.get("coatfollow", 0.0), w)       # coat panels and belt end lie along the thighs


def hands_back(c, rig, w=1.0, lean=1.0, dz=0.0):
    """Both hands planted on the page behind the hips (leaning back on them)."""
    for side in "LR":
        sx = 1 if side == "L" else -1
        arm_ik(c, side, V(0.070 * sx, 0.012, -0.050 - 0.020 * lean + dz), V(0.6 * sx, 0.2, -1.0), "root", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -60, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 8, w))


# =============================================================================================== JONAH
@clip("jonah", "idle", 150, True,
      notes="grumpy: arms loosely crossed, weight shifts L -> R with the hips leading, two huffy breaths (shoulders "
            "up, sharp sigh out), turns his chin away (neck leads, head follows) and back, the right toe taps three "
            "times, irregular blinks; coat panels and belt end settle after each shift")
def jonah_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.9)
    folded_arms(c, rig, 1.0, loose=0.6)
    huff = pulses(f, N, [(28, 1.0), (98, 0.8)], decay=4.0)
    pre = bump(f, 18, 30) + bump(f, 88, 100)
    c["chest.rx"] += -2.0 * pre + 3.0 * huff; c["shoulderL.raise"] += 2.5 * pre - 2.0 * huff
    c["shoulderR.raise"] += 2.5 * pre - 2.0 * huff; c["head.rx"] += -2 * pre + 3 * huff
    sh = K([(0, -0.4), (20, -0.4), (44, 1.0), (86, 1.0), (108, -0.8), (136, -0.8), (150, -0.4)], f, N, True)
    shl = KL([(0, -0.4), (20, -0.4), (44, 1.0), (86, 1.0), (108, -0.8), (136, -0.8), (150, -0.4)], f, N, True, lag=7)
    c["hips.tx"] = 0.0050 * sh; c["hips.ty"] = -0.0015 - 0.0012 * abs(sh)
    c["hips.rz"] = -2.6 * sh; c["spine.rz"] = 1.6 * shl; c["chest.rz"] = 1.0 * shl; c["head.rz"] = -1.8 * shl
    look = [(0, 0), (40, 0), (48, -24), (78, -24), (86, 3), (112, 3), (120, 0), (150, 0)]
    look_keys(c, look, f, N)
    c["head.rx"] += K([(0, 0), (48, -5), (78, -4), (86, 1), (150, 0)], f, N, True)
    tap = sum(bump(f, a, a + 7) for a in (118, 126, 134))
    stand_feet(rig, c, spread=0.004, fwdR=0.008, pitchR=-16 * tap)
    blink(c, f, N, [12, 60, 67, 104], slow=1.2)
    return c


J_WALK = (0.072, 0.60)


@clip("jonah", "walk", 34, True, markers={"contactL": 0, "contactR": 17}, speed=J_WALK,
      notes="plain walk, ~106 steps/min: hip bob and drop, chest counter-turn, arms swing with lagging forearms; coat "
            "panels swing late")
def jonah_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=J_WALK[0], lift=0.012, duty=J_WALK[1], heel=12, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0045 + 0.0030 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -6 * math.sin(ph - 0.35); c["head.ry"] = 3 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.5 * math.cos(ph); c["chest.rz"] = -1.5 * math.cos(ph - 0.5); c["head.rz"] = 0.8 * math.cos(ph - 0.9)
    c["spine.rx"] = 2; c["head.rx"] = -2 + 1.4 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 8 - 16 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 16 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 28 - 10 * math.sin(ph - 1.0); c["forearmR.bend"] = 28 + 10 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 9 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 9 * math.sin(ph - 1.6)
    blink(c, f, N, [27])
    return c


@clip("jonah", "talk", 96, True,
      notes="jaw in an irregular syllable rhythm (lip sync overrides it); nods on the stressed syllables; first phrase "
            "the right hand opens palm-up toward the listener, second phrase the left hand taps his chest ('me'); "
            "weight shift; two blinks")
def jonah_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    beats = talk_jaw(c, f, N, 41)
    bt = beat_curve(beats, f, N, width=9)
    btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -2 + 3.5 * bt - 1.0 * wave(f, N, 1, 0.2)
    c["head.ry"] = 5 * wave(f, N, 1, 0.1) + 2 * wave(f, N, 3, 0.4); c["head.rz"] = 3 * wave(f, N, 1, 0.35)
    pa = K([(0, 0.2), (10, 0.9), (38, 1.0), (52, 0.15), (88, 0.1), (96, 0.2)], f, N, True)
    pb = K([(0, 0.0), (44, 0.0), (56, 1.0), (84, 0.9), (94, 0.0), (96, 0.0)], f, N, True)
    lift = pa * (0.75 + 0.25 * btl)
    c["upperArmR.raise"] = -22 + 4 * lift; c["upperArmR.bend"] = 8 + 40 * lift
    c["forearmR.bend"] = 26 + 52 * lift; c["forearmR.twist"] = 10 - 80 * lift
    c["handR.bend"] = 6 - 22 * btl * pa
    fingers(c, "R", 30 - 26 * btl * pa - 6 * lift)
    arm_ik(c, "L", V(0.014, -0.004 + 0.005 * btl, 0.044), V(0.8, -0.6, -0.2), "chest", pb)
    c["handL.bend"] = 6 - 14 * pb
    c["chest.ry"] = -4 * lift + 3 * pb; c["chest.rx"] += 1.5 * bt
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh; c["spine.rz"] = 0.9 * sh
    blink(c, f, N, [7, 61])
    stand_feet(rig, c, spread=0.003)
    return c


J_TIP = (0.054, 0.52)


@clip("jonah", "tiptoe", 40, True, markers={"contactL": 0, "contactR": 20}, speed=J_TIP,
      notes="exaggerated cartoon tiptoe: high on his toes, knees lifted high and placed with care, hunched, both "
            "hands up at his chest like little paws; every step he looks back over a shoulder (left, then right), "
            "the chest turning with the head; coat panels bob")
def jonah_tiptoe(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=J_TIP[0], lift=0.036, duty=J_TIP[1], heel=-34, toeoff=40, lift_shape=0.7)
    for side in "LR":
        t, pitch, contact, p = g["leg" + side]
        pt = 38.0
        t = V(t.x, planted_ankle_y(rig, side, pt) + (t.y - planted_ankle_y(rig, side, pitch)), t.z + pivot_dz(rig, side, pitch))
        c["ik.leg" + side] = t; c[f"foot{side}.pitch"] = pt
        c[f"pole.leg{side}"] = V(0.2 if side == "L" else -0.2, 0.2, 1)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = 0.002 + 0.0045 * math.cos(2 * ph - 0.8)
    c["spine.rx"] = 10; c["chest.rx"] += 12; c["neck.rx"] = -8; c["head.rx"] = -4
    c["hips.rz"] = 2 * math.cos(ph)
    back = K([(0, 0), (5, 1), (14, 1), (19, 0), (25, -1), (34, -1), (39, 0), (40, 0)], f, N, True)
    c["chest.ry"] = 16 * back - 3 * math.sin(ph); c["neck.ry"] = 22 * KL([(0, 0), (5, 1), (14, 1), (19, 0), (25, -1), (34, -1), (39, 0), (40, 0)], f, N, True, lag=1)
    c["head.ry"] = 30 * KL([(0, 0), (5, 1), (14, 1), (19, 0), (25, -1), (34, -1), (39, 0), (40, 0)], f, N, True, lag=2)
    c["head.rz"] = 5 * back
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.030 * sx, 0.200 + 0.004 * math.sin(ph + (0 if side == "L" else math.pi)), 0.058),
               V(0.9 * sx, -0.7, -0.2))
        c[f"hand{side}.bend"] = 52; fingers(c, side, 34)
    blink(c, f, N, [17, 37])
    return c


J_STOMP = (0.064, 0.56)


@clip("jonah", "stomp_walk", 30, True, markers={"stompL": 0, "stompR": 15}, speed=J_STOMP,
      notes="cross, heavy stamping walk: knees high, each foot slammed down flat (the body jolts on impact), fists "
            "clenched and pumping stiffly, head jutting forward, coat flapping")
def jonah_stomp_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=J_STOMP[0], lift=0.040, duty=J_STOMP[1], heel=0, toeoff=6, lift_shape=0.6)
    legs_ik_channels(c, g)
    for side in "LR":
        c[f"pole.leg{side}"] = V(0.15 if side == "L" else -0.15, 0.3, 1)
    ph = 2 * math.pi * f / N
    jolt = pulses(f, N, [(0, 1.0), (15, 1.0)], decay=1.6)
    c["hips.ty"] = -0.003 - 0.004 * jolt + 0.002 * math.cos(2 * ph)
    c["chest.rx"] += 6 + 3 * jolt; c["neck.rx"] = -8; c["head.rx"] = 2 + 4 * jolt
    c["hips.rz"] = 3 * math.cos(ph); c["chest.ry"] = -6 * math.sin(ph)
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -18; c[f"upperArm{side}.bend"] = 10 + sg * 24 * math.sin(ph)
        c[f"forearm{side}.bend"] = 72; fingers(c, side, 88)
    c["eyelids.sy"] = 2.6
    return c


@clip("jonah", "listen_up", 54, False, markers={"look": 20},
      notes="a little start (shoulders up, blink), then he looks up at the sky - neck first, head after - leaning back "
            "a touch; the right hand comes half up, palm up and open ('who, me?'); holds, breathing")
def jonah_listen_up(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    start = bump(f, 0, 10)
    up = ease_io((f - 6) / 16); upl = ease_io((f - 9) / 16)
    c["shoulderL.raise"] += 4 * start; c["shoulderR.raise"] += 4 * start
    c["spine.rx"] = -4 * up; c["chest.rx"] += -4 * up
    c["neck.rx"] = -14 * up; c["head.rx"] = -2 - 20 * upl + 2 * bump(f, 24, 36)
    c["head.rz"] = 6 * upl; c["head.ry"] = -4 * upl
    h = ease_io((f - 12) / 16)
    c["upperArmR.raise"] = lerp(-22, -2, h); c["upperArmR.bend"] = lerp(8, 38, h)
    c["forearmR.bend"] = lerp(26, 82, h); c["forearmR.twist"] = lerp(10, -78, h)
    c["handR.bend"] = lerp(6, -16, h); fingers(c, "R", lerp(22, 8, h))
    c["upperArmL.bend"] = 8 + 6 * h; c["forearmL.bend"] = 26 + 10 * h
    blink(c, f, N, [3, 40], loop=False)
    stand_feet(rig, c, spread=0.003)
    return c


@clip("jonah", "refuse", 66, False, markers={"no": 10, "snort": 36},
      notes="head back, then three shrinking head shakes ('No way!'), arms snap across his chest, he turns a shoulder "
            "away from the voice with his chin up and a snort (shoulders hop); eyes half shut; holds")
def jonah_refuse(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    ant = bump(f, 0, 9)
    c["head.rx"] = -2 - 6 * ant; c["chest.rx"] += -2 * ant
    sh = [(0, 0), (6, 3), (10, -22), (15, 20), (20, -15), (25, 9), (30, -3), (34, 0), (66, 0)]
    c["head.ry"] = K(sh, f); c["neck.ry"] = 0.35 * KL(sh, f, lag=2); c["chest.ry"] = 0.12 * KL(sh, f, lag=3)
    c["head.rz"] = -0.15 * KL(sh, f, lag=1)
    fa = ease_io((f - 18) / 10)
    folded_arms(c, rig, fa)
    c["upperArmL.bend"] = c.get("upperArmL.bend", 8); c["upperArmR.bend"] = c.get("upperArmR.bend", 8)
    turn = ease_io((f - 28) / 14)
    snort = pulses(f, N, [(36, 1.0)], decay=2.5, loop=False)
    c["hips.ry"] = -10 * turn; c["spine.ry"] = -8 * turn; c["chest.ry"] += -14 * turn
    c["neck.ry"] += -10 * turn; c["head.ry"] += -18 * turn
    c["head.rx"] += -10 * turn + 3 * snort; c["head.rz"] += -5 * turn
    c["shoulderL.raise"] += 5 * snort; c["shoulderR.raise"] += 5 * snort; c["chest.rx"] += -2 * snort
    c["hips.tx"] = 0.004 * turn; c["hips.rz"] = -2 * turn
    stand_feet(rig, c, spread=0.003, pitchR=10 * turn)
    c["eyelids.sy"] = 1.0 + 4.5 * ease_io((f - 34) / 8)
    if f < 30:
        blink(c, f, N, [1], loop=False)
    return c


# --- sleeping (lying curled on his right side, head toward -X, facing the viewer); root under his shoulder
CURL_HIPS = V(0.000, -0.150, 0.004)      # hips offset in the curl (the root stays under the hips)


def curl_pose(rig, c, w=1.0, breathe=0.0, snore=0.0):
    c["hips.rz"] = c.get("hips.rz", 0.0) + 90 * w
    c["hips.tx"] = c.get("hips.tx", 0.0) + CURL_HIPS.x * w
    c["hips.ty"] = c.get("hips.ty", 0.0) + CURL_HIPS.y * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + CURL_HIPS.z * w
    c["spine.rx"] = c.get("spine.rx", 0.0) + (14 - 1.5 * breathe) * w
    c["chest.rx"] = c.get("chest.rx", 0.0) + (12 - 2.5 * breathe) * w
    c["neck.rx"] = c.get("neck.rx", 0.0) + 6 * w; c["head.rx"] = c.get("head.rx", 0.0) + 8 * w
    c["head.rz"] = c.get("head.rz", 0.0) - 10 * w
    for side, sx in (("L", 1), ("R", -1)):
        for k in ("ik.leg", "ikw.leg"):
            c.pop(k + side, None)
        c[f"thigh{side}.rx"] = c.get(f"thigh{side}.rx", 0.0) - (78 + 6 * (side == "L")) * w
        c[f"shin{side}.rx"] = c.get(f"shin{side}.rx", 0.0) + (104 - 6 * (side == "L")) * w
        c[f"foot{side}.rx"] = c.get(f"foot{side}.rx", 0.0) + 20 * w
    # hands together under the right cheek (a pillow), elbows forward
    arm_ik(c, "R", V(-0.040, 0.004, 0.034), V(0.0, -0.1, 1.0), "head", w)
    arm_ik(c, "L", V(-0.034, 0.016, 0.040), V(0.0, 0.4, 0.9), "head", w)
    c["handR.bend"] = 30 * w; c["handL.bend"] = 30 * w
    fingers(c, "L", lerp(22, 30, w)); fingers(c, "R", lerp(22, 30, w))
    c["coatfollow"] = max(c.get("coatfollow", 0.0), w)
    c["jaw.rx"] = c.get("jaw.rx", 0.0) + snore * w
    c["settle"] = ("hips", None, -0.0055, w)        # the proxy reads ~7 mm low on the twisted under-arm (measured)


SLEEP_N = 120


@clip("jonah", "sleep_curl", SLEEP_N, True, seated=True,
      notes="curled on his right side facing the viewer, knees drawn up, hands together under his cheek; two snores "
            "per loop: a long slow inhale (chest and shoulders rise, mouth falls open, head tips back a little) and a "
            "puffed exhale (mouth shuts); a foot twitch and a lip smack in the second one; eyes shut")
def jonah_sleep_curl(rig, f, N):
    c = {}
    br = K([(0, 0), (34, 1.0), (44, 1.0), (58, -0.2), (60, 0), (96, 1.1), (104, 1.1), (118, -0.2), (120, 0)], f, N, True)
    sn = K([(0, 0), (20, 2), (34, 11), (42, 12), (48, 2), (54, 0), (78, 2), (96, 13), (102, 14), (108, 0), (112, 3),
            (116, 0), (120, 0)], f, N, True)
    curl_pose(rig, c, 1.0, breathe=br, snore=sn)
    c["shoulderL.raise"] = 3 * br; c["head.rx"] += -3 * br
    tw = pulses(f, N, [(72, 1.0)], decay=2.0)
    c["footL.rx"] += -16 * tw; c["shinL.rx"] += -6 * tw
    eyes(c, rig, 1.0)
    return c


@clip("jonah", "lie_down", 40, False, seated=True, markers={"down": 30},
      notes="EXTRA (not in CONTRACT §4, a lead-in for A4): from standing he yawns and stretches, kneels / sits and "
            "curls up on his right side; ends in sleep_curl frame 0. Play it before sleep_curl (S02, after the walk "
            "to CARGO)")
def jonah_lie_down(rig, f, N):
    st = h_base(rig, f, N, cycles=1, amp=0.3)
    stand_feet(rig, st, spread=0.003)
    yawn = bump(f, 0, 16)
    st["chest.rx"] += -6 * yawn; st["head.rx"] = -2 - 14 * yawn; st["jaw.rx"] = 14 * yawn
    st["upperArmL.raise"] += 30 * yawn; st["upperArmR.raise"] += 30 * yawn
    curl = jonah_sleep_curl(rig, 0, SLEEP_N)
    w = ease_io((f - 10) / 22)
    c = mix(st, curl, w)
    c["settle"] = ("hips", None, -0.0055, w)
    c["floorclamp"] = True
    eyes(c, rig, ease_io((f - 4) / 6) * bump(f, 2, 16) + ease_io((f - 24) / 8))
    return c


def sit_upright(rig, f, N, legs="up", hands="back"):
    """Seated base pose (the hips on the page), arms planted behind or resting on the knees."""
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    seat_legs(rig, c, legs)
    if hands == "back":
        hands_back(c, rig)
    elif hands == "knees":
        for side, sx in (("L", 1), ("R", -1)):
            arm_ik(c, side, V(0.034 * sx, 0.092, 0.070), V(0.8 * sx, -0.3, -0.4))
            c[f"hand{side}.bend"] = 20; fingers(c, side, 40)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 6; c["chest.rx"] += 4
    return c


def stand_pose(rig, f, N, cycles=1, amp=0.5):
    c = h_base(rig, f, N, cycles=cycles, amp=amp)
    stand_feet(rig, c, spread=0.003)
    return c


@clip("jonah", "wake_startled", 72, False, seated=False, markers={"jolt": 9, "standing": 52},
      notes="starts in the sleep_curl pose; a last snore, then a jolt: eyes snap open, arms fling up, he springs up to "
            "sitting (overshoot back on his hands), looks left - right in a panic, scrambles to his feet (hand on the "
            "deck, knee up, push), and ends standing, wide-eyed, hands up in front ('Wha-?'), panting")
def jonah_wake_startled(rig, f, N):
    curl = jonah_sleep_curl(rig, min(f, 8), SLEEP_N)
    sit = sit_upright(rig, f, N, legs="up", hands="back")
    pan = K([(0, 0), (16, 0), (20, 1), (26, 1), (30, -1), (36, -1), (40, 0), (72, 0)], f)
    sit["neck.ry"] = 14 * pan; sit["head.ry"] = 26 * KL([(0, 0), (16, 0), (20, 1), (26, 1), (30, -1), (36, -1), (40, 0), (72, 0)], f, lag=1)
    sit["spine.rx"] += -8 * bump(f, 10, 22)
    st = stand_pose(rig, f, N, cycles=4, amp=1.4)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(st, side, V(0.044 * sx, 0.222, 0.062), V(0.8 * sx, -0.6, -0.3))
        st[f"hand{side}.bend"] = 40; fingers(st, side, 6)
        st[f"hand{side}.twist"] = 30 * sx
    st["head.rx"] = -6; st["shoulderL.raise"] = 5; st["shoulderR.raise"] = 5
    w1 = ease_io((f - 8) / 7)
    w2 = ease_io((f - 36) / 16)
    c = mix(mix(curl, sit, w1), st, w2)
    # the jolt: hands fly from under his cheek up beside his head (open), then back onto the deck behind him
    for side, sx in (("L", 1), ("R", -1)):
        for k in ("ikb.arm", "ikbspace.arm", "ikbw.arm", "ikbpole.arm"):
            c.pop(k + side, None)
        flung = V(0.085 * sx, 0.150, 0.050)
        back = sit["ik.arm" + side]
        if f < 14:
            arm_ik(c, side, curl["ik.arm" + side], curl["pole.arm" + side], "head", 1.0)
            arm_ik2(c, side, flung, V(0.8 * sx, -0.6, -0.4), "root", ease_io((f - 8) / 6))
        elif f < 36:
            arm_ik(c, side, vlerp(flung, back, ease_io((f - 15) / 7)), V(0.6 * sx, 0.0, -0.8), "root", 1.0)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 0.0), -30, bump(f, 8, 20))
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 2, bump(f, 8, 20)))
    # scramble: right knee comes up first, a push on the left hand
    c["hips.ty"] = c.get("hips.ty", 0.0) + 0.010 * bump(f, 40, 50)
    c["chest.rx"] = c.get("chest.rx", 0.0) + 16 * bump(f, 34, 52)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 10 * bump(f, 34, 52)
    if f < 9:
        eyes(c, rig, 1.0)
        c["jaw.rx"] = 4 * bump(f, 0, 8)
    else:
        c["eyelids.sy"] = 1.0
        c["jaw.rx"] = 10 * ease_io((f - 9) / 3) * (1 - 0.5 * ease_io((f - 30) / 20))
        blink(c, f, N, [44], loop=False)
    c["floorclamp"] = True
    return c


@clip("jonah", "ashamed", 120, True,
      notes="head hung low, shoulders slumped forward; his right hand rubs the back of his neck (elbow out, so the face "
            "stays clear), the left hand hangs and fiddles with the coat; one long sigh; the left toe scuffs the deck; "
            "he peeks up at the captain once and drops his eyes again; heavy slow blinks")
def jonah_ashamed(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    sigh = K([(0, 0), (40, 0), (54, 1), (62, 1), (82, -0.6), (100, 0), (120, 0)], f, N, True)
    up = K([(0, 0), (86, 0), (92, 1), (102, 1), (110, 0), (120, 0)], f, N, True)
    c["chest.rx"] += 8 - 3 * sigh; c["spine.rx"] += 3; c["neck.rx"] = 12 - 7 * up
    c["shoulderL.raise"] += -3 + 3 * sigh; c["shoulderR.raise"] += -2 + 3 * sigh
    c["shoulderL.swing"] = 5; c["shoulderR.swing"] = 3
    c["head.rx"] = 20 - 16 * up + 2 * wave(f, N, 1, 0.3)
    c["head.ry"] = -6 + 4 * up; c["head.rz"] = 5 - 3 * up
    rub = 0.004 * math.sin(2 * math.pi * 4 * f / N)
    arm_ik(c, "R", V(-0.020 + rub, 0.026, -0.030), V(-0.9, 0.4, 0.5), "neck")
    c["handR.bend"] = 26; fingers(c, "R", 30 + 8 * math.sin(2 * math.pi * 4 * f / N))
    fid = wave(f, N, 3, 0.2)
    c["upperArmL.bend"] = 10 + 3 * fid; c["forearmL.bend"] = 34 + 6 * fid; fingers(c, "L", 34 + 10 * fid)
    scuff = K([(0, 0), (20, 0), (28, 1), (36, 0.2), (44, 1), (52, 0), (120, 0)], f, N, True)
    sh = K([(0, 0), (30, 0.6), (70, 0.6), (90, -0.4), (120, 0)], f, N, True)
    c["hips.tx"] = 0.0025 * sh; c["hips.rz"] = -1.6 * sh; c["hips.ty"] = -0.002
    stand_feet(rig, c, spread=0.0, fwdL=0.010, pitchL=22 * scuff)
    c["footL.ry"] = 14 * scuff
    blink(c, f, N, [9, 47, 96], base=1.8, slow=1.6)
    return c


# --- fall_in: the captain (0.10 behind him) lifts him by the armpits and tips him over the rail (root motion)
NOSE = V(-0.008, -0.010, 0.056)     # right wrist under the nose (head space): the fingers pinch it
FALL_N = 48
FALL_SPLASH = 42
FALL_FLOOR = -0.086         # fall_in: the coat ends stop at the sea surface (0.012 world = -0.088 below the deck)


def fall_root(f):
    lift = ease_io(f / 12)
    over = ease_io((f - 10) / 13)
    y = 0.05 * lift + 0.015 * over
    z = 0.040 * over
    if f > 23:
        s = min(1.0, (f - 23) / (FALL_SPLASH - 23))
        y = 0.065 + 0.03 * s - 0.235 * s * s
        z = 0.040 + 0.060 * (1 - (1 - s) ** 1.6)
    return y, z


@clip("jonah", "fall_in", FALL_N, False, markers={"release": 23, "splash": FALL_SPLASH},
      root_motion="root travels +Z 0.10 and down to y -0.14 (frame 42 = splash, lowest point); held to the end",
      notes="the captain grabs him under the arms from behind: he is lifted (legs dangle and pedal), pinches his nose, "
            "pulls his knees up into a cannonball with the left arm round them, is tipped over the rail backwards "
            "(bottom first), falls (eyes shut, cheeks puffed) and hits the water at frame 42 (`splash`)")
def jonah_fall_in(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.2)
    y, z = fall_root(f)
    c["root.ty"] = y; c["root.tz"] = z
    ball = ease_io((f - 12) / 12)
    tip = ease_io((f - 14) / 10) * 0.25 + 0.75 * ease_io((f - 23) / 19)
    c["hips.rx"] = -62 * tip
    c["hips.ty"] = -0.118 * ease_io((f - 20) / 22)
    c["hips.tz"] = -0.020 * ball
    ped = math.sin(2 * math.pi * f / 10) * (1 - ball) * ease_io(f / 6)
    for side, sg in (("L", 1), ("R", -1)):
        c[f"thigh{side}.rx"] = lerp(-6 + 14 * sg * ped, -112, ball)
        c[f"shin{side}.rx"] = lerp(14 + 18 * max(0.0, sg * ped), 128, ball)
        c[f"foot{side}.rx"] = lerp(18, 30, ball)
        c[f"thigh{side}.rz"] = 4 * sg * ball
    c["spine.rx"] = 12 * ball; c["chest.rx"] += 8 * ball; c["neck.rx"] = 6 * ball; c["head.rx"] = 6 * ball
    # lifted by the armpits: shoulders hunch up, upper arms pushed up and out
    lifted = ease_io(f / 5) * (1 - ease_io((f - 21) / 4))
    c["shoulderL.raise"] += 12 * lifted; c["shoulderR.raise"] += 12 * lifted
    c["upperArmL.raise"] = lerp(-22, -2, lifted); c["upperArmR.raise"] = lerp(-22, -2, lifted)
    nose = ease_io((f - 8) / 8)
    arm_ik(c, "R", NOSE, V(-0.9, -0.4, 0.2), "head", nose)
    c["handR.bend"] = 20 * nose; fingers(c, "R", lerp(22, 62, nose))
    hug = ease_io((f - 16) / 8)
    arm_ik(c, "L", V(-0.004, 0.040, 0.110), V(0.9, -0.2, 0.3), "hips", hug)
    c["handL.bend"] = 30 * hug; fingers(c, "L", lerp(22, 60, hug))
    c["eyelids.sy"] = lerp(1.0, CLOSED["jonah"], ease_io((f - 6) / 4))
    c["jaw.rx"] = 0.0
    return c


# --- sitting family
@clip("jonah", "sit_hold_nose", 96, True, seated=True,
      notes="inside the fish: sits with his knees up, the left arm hugging his shins, the right hand pinching his "
            "nose; looks round the dark (left, up, right), two disgusted shudders (shoulders up, head shake); blinks")
def jonah_sit_hold_nose(rig, f, N):
    c = sit_upright(rig, f, N, legs="up", hands=None)
    c["spine.rx"] += 4
    arm_ik(c, "L", V(-0.010, 0.088, 0.096), V(0.9, -0.2, 0.2))
    c["handL.bend"] = 26; fingers(c, "L", 58)
    arm_ik(c, "R", NOSE, V(-0.9, -0.4, 0.2), "head")
    c["handR.bend"] = 20; fingers(c, "R", 62)
    look = [(0, 0), (10, 0), (20, 30), (34, 30), (44, -6), (54, -6), (66, -32), (80, -32), (90, 0), (96, 0)]
    look_keys(c, look, f, N, neck=0.35, head=0.65)
    c["head.rx"] += K([(0, 0), (40, 0), (46, -16), (56, -16), (62, 0), (96, 0)], f, N, True)
    shud = pulses(f, N, [(14, 1.0), (84, 0.8)], decay=3.0)
    c["shoulderL.raise"] += 6 * shud; c["shoulderR.raise"] += 6 * shud
    c["head.rz"] = 6 * shud * math.sin(f * 1.9)
    c["chest.rx"] += -2 * shud
    blink(c, f, N, [6, 52, 59])
    return c


# Fix 2026-11-15 (docs/jonah/FIXLOG-20261115.md): kneeling upright his head top reached 0.279, through the top of the
# `belly` dome (inner height ~0.25). He now prays sitting back on his heels: thighs leaning back, shins flat, hips
# low, which puts the head top under the dome with room to spare.
KNEEL_PRAY = dict(thigh_back=72.0, shin_slope=4.0)


def kneel_pose(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    kneel_legs(rig, c, 1.0, 1.0, **KNEEL_PRAY)
    c["hips.rx"] = -3
    arm_ik(c, "L", V(0.013, -0.034, 0.050), V(0.8, -0.7, -0.2), "chest")
    arm_ik(c, "R", V(-0.013, -0.034, 0.050), V(-0.8, -0.7, -0.2), "chest")
    c["handL.bend"] = 64; c["handR.bend"] = 64
    c["handL.twist"] = 64; c["handR.twist"] = -64
    fingers(c, "L", 6); fingers(c, "R", 6)
    c["coatfollow"] = 0.6
    return c


@clip("jonah", "kneel_pray", 84, False, seated=True, markers={"knees_down": 30, "bow": 52},
      notes="starts from sit_hold_nose's pose (the nose hand drops): he rolls forward onto his knees and sits back on "
            "his heels (small, so his head stays under the belly dome), puts his hands together in front of his "
            "chest, takes a breath, bows his head and shuts his eyes; holds, breathing. Knees on the floor "
            "(meshMinY >= -0.008)")
def jonah_kneel_pray(rig, f, N):
    a = jonah_sit_hold_nose(rig, 0, 96)
    b = kneel_pose(rig, f, N)
    w = ease_io((f - 4) / 26)
    c = mix(a, b, w)
    c["settle"] = ("hips", ("hips", "thighL", "thighR", "shinL", "shinR", "spine"), 0.0010, 1 - ease_io((f - 18) / 12))
    c["spine.rx"] = c.get("spine.rx", 0.0) + 18 * bump(f, 6, 34)
    c["chest.rx"] = c.get("chest.rx", 0.0) + 8 * bump(f, 6, 34)
    hw = ease_io((f - 6) / 34)              # hands travel from nose / shins to the chest (two-target IK, world space)
    for side in "LR":
        if "ikbw.arm" + side in c:
            c["ikbw.arm" + side] = hw
    br = bump(f, 40, 52)
    bow = ease_io((f - 46) / 16)
    c["chest.rx"] += -3 * br + 12 * bow; c["spine.rx"] += 8 * bow          # a deep bow (head stays under the dome)
    c["neck.rx"] = c.get("neck.rx", 0.0) + 12 * bow; c["head.rx"] = c.get("head.rx", 0.0) + 20 * bow
    c["head.ry"] = c.get("head.ry", 0.0) * (1 - bow)
    c["shoulderL.raise"] = c.get("shoulderL.raise", 0.0) + 3 * br; c["shoulderR.raise"] = c.get("shoulderR.raise", 0.0) + 3 * br
    eyes(c, rig, ease_io((f - 50) / 8))
    if f < 44:
        blink(c, f, N, [12], loop=False)
    c["floorclamp"] = True
    return c


def ball_pose(rig, c, w=1.0):
    """Tucked into a ball: knees to the chest, arms round the shins, head down."""
    for side, sg in (("L", 1), ("R", -1)):
        for k in ("ik.leg", "ikw.leg"):
            c.pop(k + side, None)
        c[f"thigh{side}.rx"] = lerp(c.get(f"thigh{side}.rx", 0.0), -118, w)
        c[f"shin{side}.rx"] = lerp(c.get(f"shin{side}.rx", 0.0), 132, w)
        c[f"foot{side}.rx"] = lerp(c.get(f"foot{side}.rx", 0.0), 30, w)
    c["hips.ty"] = c.get("hips.ty", 0.0) - 0.100 * w
    c["spine.rx"] = c.get("spine.rx", 0.0) + 16 * w; c["chest.rx"] = c.get("chest.rx", 0.0) + 14 * w
    c["neck.rx"] = c.get("neck.rx", 0.0) + 10 * w; c["head.rx"] = c.get("head.rx", 0.0) + 10 * w
    arm_ik(c, "L", V(-0.002, 0.040, 0.100), V(0.9, -0.2, 0.3), "hips", w)
    arm_ik(c, "R", V(0.002, 0.034, 0.104), V(-0.9, -0.2, 0.3), "hips", w)
    fingers(c, "L", 60 * w); fingers(c, "R", 60 * w)
    c["coatfollow"] = max(c.get("coatfollow", 0.0), w)


TUMBLE_N = 60
TUMBLE_LAND = 40
TUMBLE_X0 = -0.16


@clip("jonah", "tumble_out", TUMBLE_N, False, seated=True, props=["seaweed"], markers={"touch": 9, "land": TUMBLE_LAND},
      root_motion="root starts 0.16 to the left (-X) and 0.05 up (out of the fish's mouth) and rolls in along +X to the "
                  "mark, where he ends sitting",
      notes="shot out of the fish's mouth tucked in a ball: arcs down onto the sand (`touch`, frame 9), bounces, rolls "
            "over once along +X, unrolls and plonks down sitting with his legs out (`land`, frame 40), arms flung "
            "back on the sand; sways, dazed, seaweed on his head")
def jonah_tumble_out(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    unroll = ease_io((f - 30) / 14)
    sit = sit_upright(rig, f, N, legs="out", hands="back")
    sit["spine.rx"] += -6; sit["head.rz"] = 8 * math.sin(2 * math.pi * f / 26) * ease_io((f - 44) / 6)
    sit["head.rx"] = 6 - 4 * math.cos(2 * math.pi * f / 26) * ease_io((f - 44) / 6)
    ball = dict(c); ball_pose(rig, ball, 1.0)
    c = mix(ball, sit, unroll)
    # path of the ball centre: arc out of the mouth, touch at 9, bounce, roll to the mark
    xs = K([(0, TUMBLE_X0), (9, TUMBLE_X0 + 0.050), (16, TUMBLE_X0 + 0.080), (36, -0.012), (42, 0.0), (60, 0.0)], f)
    roll = -360.0 * ease_io((f - 12) / 26)
    cy = 0.070
    th = math.radians(roll)
    c["root.rz"] = roll
    c["root.tx"] = xs + cy * math.sin(th) * (1 - unroll)
    air = K([(0, 0.050), (4, 0.052), (9, 0.0), (12, 0.018), (16, 0.0), (60, 0.0)], f)
    c["root.ty"] = 0.0
    settles = []
    wb = 1 - unroll
    if wb > 0:
        settles.append(("root", None, 0.0012 + air + 0.017 * bump(f, 12, 34), wb))   # seaweed fronds clear the sand
    if unroll > 0:
        settles.append(("hips", ("hips", "thighL", "thighR", "spine"), 0.0010, unroll))
    c["settle"] = settles
    c["seaweed_on"] = True
    c["root.ty"] = air * unroll        # in the air at the start only (unroll = 0 then: the root settle carries `air`)
    land = pulses(f, N, [(TUMBLE_LAND, 1.0)], decay=2.5, loop=False)
    c["chest.rx"] = c.get("chest.rx", 0.0) + 6 * land; c["head.rx"] = c.get("head.rx", 0.0) + 8 * land
    c["eyelids.sy"] = CLOSED["jonah"] if f < 40 else 1.0 + 3.0 * (1 - ease_io((f - 40) / 6)) + 1.6
    c["floorclamp"] = True
    return c


@clip("jonah", "sit_dazed", 90, True, seated=True, props=["seaweed"],
      notes="sits on the sand with his legs out, leaning back on his hands, swaying in a slow dizzy circle (head "
            "circles the other way); tilts his head right and thumps the left side of it three times with his left "
            "hand to shake the water out of his ear, then a quick head shake; heavy dazed blinks; seaweed flops")
def jonah_sit_dazed(rig, f, N):
    c = sit_upright(rig, f, N, legs="out", hands="back")
    ph = 2 * math.pi * f / N
    c["spine.rz"] = 3 * math.sin(ph); c["spine.rx"] += -6 + 2 * math.cos(ph)
    c["chest.rz"] = 2 * math.sin(ph - 0.5); c["head.rz"] = -5 * math.sin(ph - 1.2); c["head.rx"] = 4 * math.cos(ph - 1.2)
    ear = ease_io((f - 32) / 14) * (1 - ease_io((f - 66) / 12))
    c["head.rz"] += 22 * ear; c["neck.rz"] = 8 * ear
    thump = pulses(f, N, [(47, 1.0), (53, 1.0), (59, 1.0)], decay=1.5)
    arm_ik2(c, "L", V(0.050 - 0.010 * thump, 0.040, 0.004), V(0.9, -0.3, -0.2), "head", ear)
    c["handL.bend"] = lerp(c.get("handL.bend", -60), 0, ear); fingers(c, "L", lerp(8, 30, ear))
    c["head.rz"] += -4 * thump
    shake = math.sin(2 * math.pi * (f - 68) / 5) * bump(f, 68, 82)
    c["head.ry"] = 18 * shake
    blink(c, f, N, [20, 64, 84], base=2.6, slow=1.8)
    return c


@clip("jonah", "stand_up", 60, False, props=["seaweed"], markers={"up": 40},
      notes="from sit_dazed's pose: pulls his feet in, rocks forward with his hands pushing off the sand, rises, "
            "brushes the sand off his coat with both hands, a little shake of the head; ends standing")
def jonah_stand_up(rig, f, N):
    a = jonah_sit_dazed(rig, 0, 90)
    crouch = sit_upright(rig, f, N, legs="up", hands=None)
    crouch["spine.rx"] += 18; crouch["chest.rx"] += 12; crouch["head.rx"] = -6
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(crouch, side, V(0.066 * sx, 0.042, 0.030), V(0.6 * sx, 0.2, -0.6))
        crouch[f"hand{side}.bend"] = 0
    st = stand_pose(rig, f, N, amp=1.0)
    w1 = ease_io((f - 2) / 16)
    w2 = ease_io((f - 18) / 22)
    c = mix(mix(a, crouch, w1), st, w2)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 14 * bump(f, 16, 42); c["chest.rx"] = c.get("chest.rx", 0.0) + 6 * bump(f, 16, 42)
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.020 * bump(f, 14, 44)
    br = bump(f, 42, 58)
    sw = math.sin(2 * math.pi * (f - 42) / 6) * br
    for side, sx in (("L", 1), ("R", -1)):
        if f > 40:
            arm_ik(c, side, V(0.034 * sx, 0.120 + 0.010 * sw * sx, 0.052), V(0.8 * sx, -0.6, -0.3), "root", br)
            c[f"hand{side}.bend"] = -10 + 26 * sw * sx
    c["head.ry"] = 10 * math.sin(2 * math.pi * (f - 48) / 5) * bump(f, 48, 58)
    blink(c, f, N, [8, 46], loop=False, base=1.0 + 1.6 * (1 - ease_io((f - 20) / 20)))
    c["floorclamp"] = True
    return c


@clip("jonah", "nod_ok", 50, False, markers={"nod": 30},
      notes="a deep breath in (chest and shoulders rise, chin up), out, then one firm nod; his fists close at his "
            "sides; ends standing tall and steady")
def jonah_nod_ok(rig, f, N):
    c = stand_pose(rig, f, N, amp=0.3)
    br = bump(f, 2, 24); out = bump(f, 20, 32)
    c["chest.rx"] += -5 * br + 2 * out; c["shoulderL.raise"] += 5 * br; c["shoulderR.raise"] += 5 * br
    c["head.rx"] = -2 - 6 * br
    nod = K([(0, 0), (26, 0), (31, 18), (36, 14), (42, -2), (50, -1)], f)
    c["head.rx"] += nod; c["neck.rx"] = 0.3 * KL([(0, 0), (26, 0), (31, 18), (36, 14), (42, -2), (50, -1)], f, lag=2)
    fist = ease_io((f - 26) / 6)
    fingers(c, "L", lerp(22, 80, fist)); fingers(c, "R", lerp(22, 80, fist))
    c["forearmL.bend"] = 26 + 10 * fist; c["forearmR.bend"] = 26 + 10 * fist
    eyes(c, rig, 0.35 * br)
    return c


@clip("jonah", "proclaim", 96, True, markers={"call1": 10, "call2": 58},
      notes="calling out to the whole city: hands cupped round his mouth (kept to the sides so the mouth shows), "
            "leaning forward from the hips, two big calls per loop, first to his left, then to his right (chest and "
            "head turn), each call pumps the body forward; jaw wide on the calls; wide stance")
def jonah_proclaim(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    turn = K([(0, 1), (36, 1), (48, -1), (84, -1), (96, 1)], f, N, True)
    call = beat_curve([10, 18, 26, 58, 66, 74], f, N, width=8)
    pump = beat_curve([10, 58], f, N, width=18)
    c["spine.rx"] = 6 + 6 * pump; c["chest.rx"] += 4 + 4 * pump
    c["hips.ry"] = 4 * turn; c["chest.ry"] = 12 * turn; c["neck.ry"] = 6 * turn; c["head.ry"] = 8 * turn
    c["head.rx"] = -6 - 4 * pump
    c["jaw.rx"] = 4 + 14 * call
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.030 * sx, -0.020, 0.046), V(0.9 * sx, -0.6, -0.1), "head")
        c[f"hand{side}.bend"] = 40; c[f"hand{side}.twist"] = -40 * sx; fingers(c, side, 30)
    stand_feet(rig, c, spread=0.008, fwdL=0.012, fwdR=-0.004)
    blink(c, f, N, [40, 88])
    return c


@clip("jonah", "surprised", 48, False, markers={"take": 16},
      notes="double-take: a glance at the gate, he looks away (it can't be...), then snaps back with a jolt - head "
            "jerks back, shoulders up, hands fly up open at his chest, jaw drops; holds wide-eyed")
def jonah_surprised(rig, f, N):
    c = stand_pose(rig, f, N, amp=0.3)
    hd = K([(0, 0), (6, 0), (11, -24), (14, -22), (17, 6), (21, -2), (26, 0), (48, 0)], f)
    c["head.ry"] = hd; c["neck.ry"] = 0.3 * KL([(0, 0), (6, 0), (11, -24), (14, -22), (17, 6), (21, -2), (26, 0), (48, 0)], f, lag=2)
    jolt = ease_io((f - 15) / 4)
    pop = pulses(f, N, [(16, 1.0)], decay=3.0, loop=False)
    c["head.rx"] = -2 - 8 * jolt - 4 * pop; c["chest.rx"] += -4 * jolt
    c["shoulderL.raise"] += 7 * jolt - 2 * ease_io((f - 30) / 10); c["shoulderR.raise"] += 7 * jolt - 2 * ease_io((f - 30) / 10)
    c["hips.ty"] = 0.004 * pop
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.052 * sx, 0.236, 0.066), V(0.8 * sx, -0.6, -0.3), "root", jolt)
        c[f"hand{side}.bend"] = lerp(6, 48, jolt); c[f"hand{side}.twist"] = 20 * sx * jolt
        fingers(c, side, lerp(22, 2, jolt))
    c["jaw.rx"] = 16 * jolt
    stand_feet(rig, c, spread=0.003)
    c["eyelids.sy"] = 1.0
    if f < 14:
        blink(c, f, N, [3], loop=False)
    return c


@clip("jonah", "sit_sulk", 72, False, seated=True, markers={"plonk": 16},
      notes="plonks down on the hill (a little bounce), folds his arms, chin on his chest, a huff, and taps one foot "
            "four times; eyes half shut; holds the sulk")
def jonah_sit_sulk(rig, f, N):
    a = stand_pose(rig, f, N, amp=0.3)
    b = sit_upright(rig, f, N, legs="up", hands=None)
    w = ease_io(f / 14)
    c = mix(a, b, w)
    bounce = pulses(f, N, [(16, 1.0)], decay=2.0, loop=False)
    st = c.get("settle")
    if st:
        c["settle"] = (st[0], st[1], st[2] + 0.006 * bounce, st[3])
    fa = ease_io((f - 3) / 14)
    folded_arms(c, rig, fa)
    chin = ease_io((f - 22) / 12)
    huff = pulses(f, N, [(34, 1.0)], decay=3.0, loop=False)
    c["neck.rx"] = c.get("neck.rx", 0.0) + 12 * chin; c["head.rx"] = c.get("head.rx", 0.0) + 18 * chin - 4 * huff
    c["head.ry"] = -10 * chin
    c["shoulderL.raise"] = c.get("shoulderL.raise", 0.0) + 5 * huff; c["shoulderR.raise"] = c.get("shoulderR.raise", 0.0) + 5 * huff
    tap = sum(bump(f, a_, a_ + 6) for a_ in (40, 47, 54, 61))
    c["footR.pitch"] = c.get("footR.pitch", 0.0) - 22 * tap
    c["eyelids.sy"] = 1.0 + 4.0 * ease_io((f - 26) / 8)
    c["floorclamp"] = True
    return c


@clip("jonah", "relax_happy", 120, True, seated=True,
      notes="bliss in the shade: sits with his legs out, ankles crossed, leaning back on his hands, face up, eyes "
            "closed; one long contented sigh, head sways gently, toes wiggle")
def jonah_relax_happy(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.9)
    seat_legs(rig, c, "out")
    c["ik.legR"] = c["ik.legR"] + V(0.020, 0.010, -0.010)
    c["ik.legL"] = c["ik.legL"] + V(-0.004, 0.0, 0.004)
    hands_back(c, rig, lean=1.5)
    sigh = K([(0, 0), (20, 0), (44, 1), (52, 1), (76, -0.3), (90, 0), (120, 0)], f, N, True)
    c["spine.rx"] = -8; c["chest.rx"] += -6 - 3 * sigh
    c["neck.rx"] = -10; c["head.rx"] = -14 - 4 * sigh
    c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh
    c["head.rz"] = 5 * wave(f, N, 1, 0.1); c["head.ry"] = 4 * wave(f, N, 1, 0.35)
    c["footL.pitch"] += 8 * wave(f, N, 4, 0.0); c["footR.pitch"] += 8 * wave(f, N, 4, 0.5)
    eyes(c, rig, 0.92)
    return c


@clip("jonah", "wail", 72, True, seated=True,
      notes="over-the-top wailing at the dead plant: sitting, legs out, both arms thrown up toward it, rocking "
            "forward and back (two rocks per loop), head back, mouth wide with sobs, shoulders jerking")
def jonah_wail(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    seat_legs(rig, c, "out", kneeL=0.3)
    rock = wave(f, N, 2, 0.0)
    sob = pulses(f, N, [(4, 1.0), (14, 0.7), (40, 1.0), (50, 0.8)], decay=2.2)
    c["spine.rx"] = 2 + 10 * rock; c["chest.rx"] += 4 * rock - 3 * sob
    c["neck.rx"] = -8 - 4 * rock; c["head.rx"] = -14 - 4 * rock + 3 * sob
    c["head.rz"] = 6 * wave(f, N, 1, 0.2)
    for side, sx in (("L", 1), ("R", -1)):
        lag = 0.0 if side == "L" else 0.08
        c[f"shoulder{side}.raise"] = 6 + 5 * sob
        c[f"upperArm{side}.raise"] = 118 + 8 * wave(f, N, 2, lag); c[f"upperArm{side}.bend"] = 26
        c[f"forearm{side}.bend"] = 18 + 10 * wave(f, N, 2, 0.2 + lag)
        c[f"forearm{side}.twist"] = -60 * sx; c[f"hand{side}.bend"] = -18
        fingers(c, side, 4)
    c["jaw.rx"] = 12 + 6 * sob
    c["eyelids.sy"] = CLOSED["jonah"] * 0.85
    return c


@clip("jonah", "look_city", 120, False, markers={"stand": 70},
      notes="starts seated (legs out, as in wail / relax_happy): he lowers his arms and looks up, listening (the "
            "question sinks in), slowly gets up, sets a hand on his hip, turns his gaze to the city, and the hand "
            "slowly drops from the hip as he understands; holds standing, soft")
def jonah_look_city(rig, f, N):
    a = sit_upright(rig, f, N, legs="out", hands="back")
    up = ease_io((f - 2) / 18)
    a["neck.rx"] = -10 * up; a["head.rx"] = -14 * up
    crouch = sit_upright(rig, f, N, legs="up", hands=None)
    crouch["spine.rx"] += 18; crouch["chest.rx"] += 12
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(crouch, side, V(0.066 * sx, 0.042, 0.030), V(0.6 * sx, 0.2, -0.6))
        crouch[f"hand{side}.bend"] = 0
    st = stand_pose(rig, f, N, cycles=2, amp=0.8)
    hip = ease_io((f - 72) / 10) * (1 - ease_io((f - 88) / 26))
    arm_ik(st, "R", V(-0.058, 0.180, 0.004), V(-0.9, 0.0, -0.4), "root", hip)
    st["handR.bend"] = -30 * hip
    st["head.ry"] = 8 * ease_io((f - 74) / 14)
    st["head.rx"] = -2 + 4 * ease_io((f - 90) / 20)
    w1 = ease_io((f - 34) / 14)
    w2 = ease_io((f - 46) / 24)
    c = mix(mix(a, crouch, w1), st, w2)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 12 * bump(f, 44, 72)
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.016 * bump(f, 40, 72)
    blink(c, f, N, [26, 60, 104], loop=False, slow=1.4)
    c["floorclamp"] = True
    return c


@clip("jonah", "wave", 48, True,
      notes="a small, slightly shy wave: the right hand only at shoulder height, small fast waggles, shoulders up a "
            "little, head tilted, the left hand behind his back; weight rocks from foot to foot")
def jonah_wave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.6)
    wg = wave(f, N, 3, 0.0)
    arm_ik(c, "R", V(-0.074 + 0.006 * wg, 0.262, 0.050), V(-0.6, -1.0, 0.1))
    c["handR.bend"] = 40; c["handR.twist"] = 40 + 30 * wave(f, N, 3, -0.15); c["forearmR.twist"] = 60
    fingers(c, "R", 6 + 10 * max(0.0, wg))
    arm_ik(c, "L", V(0.040, 0.165, -0.050), V(0.8, -0.4, 0.4))
    c["handL.bend"] = 10
    sh = wave(f, N, 1, 0.0)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -2 * sh; c["chest.rz"] = 1.2 * sh
    c["head.rz"] = -8 + 2 * sh; c["head.rx"] = 2
    c["shoulderL.raise"] += 3; c["shoulderR.raise"] += 2
    stand_feet(rig, c, spread=0.002, pitchL=6 * max(0.0, sh), pitchR=6 * max(0.0, -sh))
    blink(c, f, N, [20])
    return c


# =============================================================================================== CAPTAIN
OAR = V(-0.074, 0.172, 0.006)        # the steering-oar handle in the captain's root space at CAPT_DECK (coast.glb)


@clip("captain", "idle", 180, True,
      notes="one 6 s loop = one shipRock period: right hand resting on the steering-oar handle (at his right side), "
            "left fist on his hip, legs apart; his body sways against the ship's roll (hips lead, chest late), he "
            "looks out to sea and back, a hum (small jaw), belly breathing; blinks")
def captain_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=1.0)
    rock = wave(f, N, 1, 0.0)
    rockl = wave(f, N, 1, -0.06)
    c["hips.tx"] = 0.004 * rock; c["hips.rz"] = -2.5 * rock; c["spine.rz"] = 1.6 * rockl; c["chest.rz"] = 1.2 * rockl
    c["head.rz"] = -1.2 * wave(f, N, 1, -0.12)
    arm_ik(c, "R", OAR + V(0.0, 0.002 * rock, 0.0), V(-0.8, -0.4, -0.5))
    c["handR.bend"] = 10; fingers(c, "R", 70)
    arm_ik(c, "L", V(0.074, 0.190, 0.006), V(0.9, 0.2, -0.6))
    c["handL.bend"] = -20; fingers(c, "L", 80)
    look = [(0, 0), (30, 0), (44, 24), (80, 24), (96, -10), (130, -10), (146, 0), (180, 0)]
    look_keys(c, look, f, N)
    c["head.rx"] += K([(0, 0), (44, -4), (80, -4), (96, 1), (180, 0)], f, N, True)
    c["jaw.rx"] = 3 * bump(f, 100, 112) + 3 * bump(f, 116, 128)
    stand_feet(rig, c, spread=0.010, fwdL=0.006, fwdR=-0.004)
    blink(c, f, N, [16, 70, 77, 150])
    return c


@clip("captain", "talk", 96, True,
      notes="big open gestures: both arms swing open wide palms-up on the stressed words (left phrase, right phrase, "
            "both), chest out, a belly chuckle (shoulders bounce), nods; jaw in a syllable rhythm")
def captain_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    beats = talk_jaw(c, f, N, 77, amp=(6, 15))
    bt = beat_curve(beats, f, N, width=10)
    btl = beat_curve(beats, f - 3, N, width=12)
    c["head.rx"] = -3 + 4 * bt; c["head.ry"] = 6 * wave(f, N, 1, 0.15); c["head.rz"] = 3 * wave(f, N, 1, 0.4)
    pl = K([(0, 0.3), (10, 1.0), (34, 1.0), (46, 0.2), (62, 0.8), (84, 1.0), (96, 0.3)], f, N, True)
    pr = K([(0, 0.2), (24, 0.2), (36, 1.0), (60, 0.9), (70, 0.6), (84, 1.0), (96, 0.2)], f, N, True)
    for side, w_ in (("L", pl), ("R", pr)):
        sx = 1 if side == "L" else -1
        o = w_ * (0.75 + 0.25 * btl)
        c[f"upperArm{side}.raise"] = -14 + 46 * o; c[f"upperArm{side}.bend"] = 8 + 24 * o
        c[f"forearm{side}.bend"] = 26 + 34 * o; c[f"forearm{side}.twist"] = -10 * sx + (-70 * sx) * o
        c[f"hand{side}.bend"] = 6 - 26 * o; fingers(c, side, 24 - 18 * o)
    ch = pulses(f, N, [(50, 1.0), (55, 0.7), (60, 0.5)], decay=2.0)
    c["shoulderL.raise"] += 3 * ch; c["shoulderR.raise"] += 3 * ch; c["chest.rx"] += -3 + 1.5 * ch
    sh = wave(f, N, 1, 0.1)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2 * sh; c["chest.ry"] = 4 * (pl - pr)
    stand_feet(rig, c, spread=0.010)
    blink(c, f, N, [20, 74])
    return c


C_WALK = (0.080, 0.60)


@clip("captain", "walk", 36, True, markers={"contactL": 0, "contactR": 18}, speed=C_WALK,
      notes="rolling sailor's walk: feet wide apart, the body rolls far over each planted foot (hips and chest roll, "
            "head stays level), arms held out from the belly and swinging wide, a bounce per step")
def captain_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=C_WALK[0], lift=0.014, duty=C_WALK[1], heel=10, toeoff=20, spread=0.012)
    legs_ik_channels(c, g)
    for side in "LR":
        c[f"pole.leg{side}"] = V(0.35 if side == "L" else -0.35, 0, 1)
    ph = 2 * math.pi * f / N
    c["hips.tx"] = 0.010 * math.cos(ph); c["hips.ty"] = -0.006 + 0.004 * math.cos(2 * ph - 0.5)
    c["hips.rz"] = 6 * math.cos(ph); c["spine.rz"] = -2.5 * math.cos(ph - 0.3); c["chest.rz"] = -2.5 * math.cos(ph - 0.5)
    c["head.rz"] = -1.0 * math.cos(ph - 0.8)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.35)
    c["chest.rx"] += -3
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -4 + 4 * math.cos(ph + (0 if side == "L" else math.pi))
        c[f"upperArm{side}.bend"] = 10 + sg * 20 * math.sin(ph - 0.25)
        c[f"forearm{side}.bend"] = 34 + sg * 10 * math.sin(ph - 1.0)
        fingers(c, side, 40)
    blink(c, f, N, [24])
    return c


@clip("captain", "greet", 66, False, markers={"sweep": 22, "point": 40},
      notes="'Welcome aboard!': a breath and a lean back, then the right arm sweeps wide in a big welcome (palm up), "
            "left fist on his hip, a laugh; then the arm swings forward and points ahead out to sea ('we're off!'); "
            "holds pointing, chest out")
def captain_greet(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    ant = bump(f, 0, 12)
    sw = ease_io((f - 6) / 16)
    pt = ease_io((f - 30) / 10)
    c["chest.rx"] += -3 * ant - 4 * sw; c["spine.rx"] = -3 * ant
    raise_ = lerp(lerp(-14, 52, sw), 74, pt)
    c["upperArmR.raise"] = raise_; c["upperArmR.bend"] = lerp(lerp(8, -14, sw), 62, pt)
    c["forearmR.bend"] = lerp(lerp(26, 18, sw), 8, pt); c["forearmR.twist"] = lerp(lerp(10, -70, sw), -20, pt)
    c["handR.bend"] = lerp(lerp(6, -20, sw), 4, pt); fingers(c, "R", lerp(lerp(22, 4, sw), 2, pt))
    arm_ik(c, "L", V(0.074, 0.190, 0.006), V(0.9, 0.2, -0.6), "root", ease_io((f - 4) / 10))
    c["handL.bend"] = -20; fingers(c, "L", 80)
    laugh = pulses(f, N, [(22, 1.0), (27, 0.7), (32, 0.5)], decay=2.0, loop=False)
    c["jaw.rx"] = 10 * sw * (1 - pt) + 8 * laugh + 6 * bump(f, 38, 50)
    c["shoulderL.raise"] += 3 * laugh; c["shoulderR.raise"] += 3 * laugh
    c["head.rx"] = -2 - 6 * sw + 4 * laugh; c["head.ry"] = -10 * sw * (1 - pt) - 8 * pt
    c["chest.ry"] = -6 * sw * (1 - pt) - 6 * pt
    stand_feet(rig, c, spread=0.010, fwdR=0.010 * pt, liftR=0.008 * bump(f, 30, 40))
    blink(c, f, N, [3, 54], loop=False)
    return c


@clip("captain", "steer_hard", 72, True, markers={"heaveL": 14, "heaveR": 50},
      notes="in the storm: both hands on the steering-oar handle at his right, heaving it hard to one side and the "
            "other (the whole body throws its weight into it, chest turning, hips pushing), legs braced wide and "
            "bent, head ducked against the wind, teeth gritted; the hands slide only +-0.02 along the static oar")
def captain_steer_hard(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.4)
    hv = K([(0, -1), (14, 1), (22, 0.8), (36, 1), (50, -1), (58, -0.8), (72, -1)], f, N, True)
    hvl = KL([(0, -1), (14, 1), (22, 0.8), (36, 1), (50, -1), (58, -0.8), (72, -1)], f, N, True, lag=3)
    jerk = pulses(f, N, [(12, 1.0), (48, 1.0)], decay=2.5)
    arm_ik(c, "R", OAR + V(0.004, -0.004, 0.020 * hv), V(-0.8, -0.5, -0.5))
    arm_ik(c, "L", OAR + V(0.030, 0.012, 0.024 + 0.020 * hv), V(0.7, -0.6, -0.4))
    c["handR.bend"] = 10; c["handL.bend"] = 14; fingers(c, "R", 80); fingers(c, "L", 80)
    c["chest.ry"] = -14 - 8 * hvl; c["spine.ry"] = -6 - 4 * hvl; c["hips.ry"] = -4 * hv
    c["spine.rx"] = 8 + 3 * jerk; c["chest.rx"] += 6 + 2 * jerk
    c["hips.ty"] = -0.016 - 0.003 * jerk; c["hips.tx"] = -0.006 * hv; c["hips.tz"] = -0.006
    c["hips.rz"] = 3 * hv
    c["neck.rx"] = -6; c["head.rx"] = 4; c["head.ry"] = 10 * hvl
    c["jaw.rx"] = 2 + 3 * jerk
    c["eyelids.sy"] = 3.4 + 2 * jerk
    stand_feet(rig, c, spread=0.016, fwdL=0.020, fwdR=-0.012, pitchR=6)
    return c


# --- partner-aware clips: hand targets come from the partner's own clip, evaluated at the matching frame
_PARTNER = {}


def partner_pose(action, f):
    key = (action, int(f))
    if key not in _PARTNER:
        cl = next(c for c in CLIPS if c.action == action)
        rig = RIGS[cl.ch]
        _, _, M = evaluate_primary(rig, cl, max(0, min(cl.N, int(f))))
        _PARTNER[key] = {n: (rig.pos(M, n), rig.pos(M, n, "tail")) for n in rig.names}
    return _PARTNER[key]


def shake_target(f):
    """Jonah's upper (left) shoulder in the sleep_curl pose, in the captain's root space (lie mode: Jonah's root
    SHAKE_D in front of the captain, his head toward the captain, facing the captain's right)."""
    p = partner_pose("jonah_sleep_curl", 0)
    q = (p["upperArmL"][0] * 0.65 + p["chest"][0] * 0.35)
    return V(-q.z, q.y, SHAKE_D + q.x)


@clip("captain", "shake_awake", 48, True, markers={"shake1": 8, "shake2": 32},
      notes="bends right over Jonah lying curled at his feet (Jonah's root SHAKE_D = 0.19 in front, head toward the "
            "captain), knees bent, both hands on his upper shoulder and arm, shaking him hard in two bursts per "
            "loop, shouting (jaw wide on the bursts), eyes wide")
def captain_shake_awake(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    t = shake_target(f)
    burst = K([(0, 0.4), (6, 1.0), (16, 1.0), (22, 0.3), (30, 1.0), (40, 1.0), (46, 0.4), (48, 0.4)], f, N, True)
    sh = math.sin(2 * math.pi * 6 * f / N) * burst
    c["hips.tz"] = -0.026; c["hips.ty"] = -0.034
    c["hips.rx"] = 22; c["spine.rx"] = 22 + 2 * burst; c["chest.rx"] += 18; c["neck.rx"] = -14; c["head.rx"] = -10
    arm_ik(c, "R", t + V(-0.016 + 0.010 * sh, 0.010, -0.018 + 0.004 * sh), V(-0.8, 0.2, -0.6))
    arm_ik(c, "L", t + V(0.018 + 0.010 * sh, 0.004, 0.012 + 0.004 * sh), V(0.8, 0.2, -0.6))
    c["handR.bend"] = 30; c["handL.bend"] = 30; fingers(c, "R", 55); fingers(c, "L", 55)
    c["chest.rz"] = 2.5 * sh; c["head.rz"] = -2 * sh
    c["jaw.rx"] = 6 + 10 * beat_curve([7, 13, 31, 37], f, N, width=6)
    c["eyelids.sy"] = 1.0
    stand_feet(rig, c, spread=0.014, fwdL=0.024, fwdR=-0.010)
    return c


@clip("captain", "refuse_hands", 54, False, markers={"no": 14},
      notes="'Throw you in? No, no!': a startled step back, both palms pushed out in front of his chest, head "
            "shaking hard twice, then the hands sink a little and the head drops, torn; holds")
def captain_refuse_hands(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    up = ease_io((f - 2) / 8)
    sink = ease_io((f - 34) / 14)
    step = ease_io((f - 2) / 8)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.050 * sx, 0.244 - 0.024 * sink, 0.096 - 0.012 * sink), V(0.8 * sx, -0.5, -0.5), "root", up)
        c[f"hand{side}.bend"] = lerp(6, 62 - 14 * sink, up); c[f"hand{side}.twist"] = 10 * sx * up
        fingers(c, side, lerp(22, 2, up))
    shk = [(0, 0), (8, 0), (12, -20), (17, 18), (22, -16), (27, 12), (32, -4), (36, 0), (54, 0)]
    c["head.ry"] = K(shk, f); c["neck.ry"] = 0.3 * KL(shk, f, lag=2)
    c["spine.rx"] = -5 * up + 4 * sink; c["chest.rx"] += -3 * up + 4 * sink
    c["head.rx"] = -4 * up + 12 * sink; c["neck.rx"] = 4 * sink
    c["hips.tz"] = -0.012 * step
    stand_feet(rig, c, spread=0.010, fwdL=-0.030 * step, fwdR=0.004, liftL=0.012 * bump(f, 1, 11))
    c["jaw.rx"] = 8 * bump(f, 10, 34)
    blink(c, f, N, [40], loop=False, base=1.0 + 1.4 * sink)
    return c


HEAVE_N = 72
HEAVE_REL = HEAVE_LAG + 23            # = jonah_fall_in `release`


def heave_targets(f):
    """Jonah's armpits (just under and behind his shoulders) from jonah_fall_in at the matching frame, in the
    captain's root space (tandem: Jonah HEAVE_D in front, both facing +Z)."""
    fj = max(0, min(FALL_N, f - HEAVE_LAG))
    p = partner_pose("jonah_fall_in", fj)
    out = {}
    for side in "LR":
        sh = p["upperArm" + side][0]
        ch = p["chest"][0]
        q = sh.lerp(ch, 0.28) + (p["chest"][0] - p["spine"][0]).normalized() * -0.020 + V(0, 0, -0.012)
        out[side] = V(q.x, q.y, q.z + HEAVE_D)
    return out


@clip("captain", "heave", HEAVE_N, False, markers={"grab": HEAVE_LAG, "release": HEAVE_REL},
      notes="eyes shut, 'forgive us!': a deep breath, he bends and takes Jonah (0.10 in front, back to him) under "
            "both arms (`grab`, frame 21 = jonah_fall_in frame 0), lifts him with a grunt, rises on his toes and "
            "tips him forward over the rail (`release`, frame 44 = jonah_fall_in frame 23), follows through, then "
            "pulls both hands to his mouth and peeks with one eye")
def captain_heave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    T = heave_targets(f)
    reach = ease_io((f - 6) / 15)
    hold = 1.0 if HEAVE_LAG <= f <= HEAVE_REL else 0.0
    after = ease_io((f - HEAVE_REL) / 8)
    back = ease_io((f - HEAVE_REL - 10) / 12)
    br = bump(f, 0, 12)
    c["chest.rx"] += -4 * br; c["shoulderL.raise"] += 4 * br; c["shoulderR.raise"] += 4 * br
    lift = ease_io((f - HEAVE_LAG) / 12)
    tipw = ease_io((f - HEAVE_LAG - 10) / 14)
    c["hips.ty"] = -0.018 * reach * (1 - lift) - 0.006 * (1 - reach) * 0 + 0.004 * tipw * (1 - after)
    c["hips.tz"] = -0.012 * reach + 0.012 * tipw * (1 - back)
    c["spine.rx"] = 10 * reach * (1 - lift) + 6 * tipw * (1 - back) - 4 * lift * (1 - tipw)
    c["chest.rx"] += 8 * reach * (1 - lift) + 6 * tipw * (1 - back)
    for side, sx in (("L", 1), ("R", -1)):
        if f <= HEAVE_REL:
            tgt = T[side]
            if f < HEAVE_LAG:
                tgt = tgt + V(0.012 * sx, -0.008, -0.020) * (1 - ease_io((f - 12) / 9))
            arm_ik(c, side, tgt, V(0.9 * sx, -0.4, -0.3), "root", reach)
        else:
            follow = T[side] + V(0.0, 0.012, 0.030) * after
            arm_ik(c, side, follow, V(0.8 * sx, -0.6, -0.3), "root", 1.0)
            arm_ik2(c, side, V(0.014 * sx, -0.040, 0.050), V(0.9 * sx, -0.6, -0.2), "head", back)
        c[f"hand{side}.bend"] = lerp(20 * reach, -10, back); fingers(c, side, lerp(lerp(22, 60, reach * (1 - after)), 40, back))
    grunt = pulses(f, N, [(HEAVE_LAG + 4, 1.0), (HEAVE_REL - 2, 1.0)], decay=3.0, loop=False)
    c["jaw.rx"] = 6 * grunt + 4 * bump(f, HEAVE_REL + 12, HEAVE_REL + 26)
    c["head.rx"] = -4 * grunt + 8 * back; c["neck.rx"] = 4 * back
    toes = bump(f, HEAVE_REL - 8, HEAVE_REL + 8)
    stand_feet(rig, c, spread=0.012, fwdL=0.016, fwdR=-0.012, pitchL=0.0, pitchR=22 * toes)
    peek = bump(f, 60, 72) if f < 72 else 0.0
    c["eyelids.sy"] = CLOSED["captain"] * (1 - ease_io(f / 6) * 0 - 0) if f >= 6 else lerp(1.0, CLOSED["captain"], f / 6)
    if f >= 6:
        c["eyelids.sy"] = CLOSED["captain"] - (CLOSED["captain"] - 4.5) * ease_io((f - 62) / 6)
    return c


@clip("captain", "amazed", 60, False, markers={"hands_up": 20},
      notes="the sea goes still: his hands drop, then come up onto his head (elbows wide, face clear), jaw drops, he "
            "turns slowly to look across the calm water, a little bounce of disbelief; holds")
def captain_amazed(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.6)
    up = ease_io((f - 8) / 14)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.120 * sx, 0.150, 0.040), V(1.0 * sx, -0.4, -0.3), "root", ease_io(f / 8))
        arm_ik2(c, side, V(0.048 * sx, 0.044, -0.006), V(1.0 * sx, 0.2, -0.3), "head", up)
        c[f"hand{side}.bend"] = 20 * up; fingers(c, side, lerp(22, 20, up))
    look = K([(0, 0), (20, 0), (34, -18), (50, 14), (60, 10)], f)
    c["head.ry"] = 0.7 * look; c["neck.ry"] = 0.3 * look; c["chest.ry"] = 0.15 * look
    c["jaw.rx"] = 14 * ease_io((f - 10) / 8)
    bnc = pulses(f, N, [(18, 1.0)], decay=3.0, loop=False)
    c["hips.ty"] = 0.004 * bnc; c["head.rx"] = -4 * up - 3 * bnc
    stand_feet(rig, c, spread=0.010)
    c["eyelids.sy"] = 1.0
    blink(c, f, N, [4, 46], loop=False)
    return c


# =============================================================================================== FISH
# Nose to +Z, belly on the page. root.rx < 0 = nose up; jaw.rx > 0 = open (55 = the gulp); finR / finL .rz: the
# side fins flap (finL up = +, finR up = -). Body wave: yaw (ry) per chain segment with a phase lag head -> tail.
FISH_SEG = (("body1", 0.00), ("body2", 0.13), ("body3", 0.26), ("tail", 0.40))


def body_wave(c, f, N, cycles, amps, phase=0.0, steady=1.0):
    """Travelling body wave: relative yaw per segment, each later in phase, so the bend runs head -> tail.
    `steady` counter-turns the root so the head points along the travel."""
    for (b, lag), a in zip(FISH_SEG, amps):
        c[f"{b}.ry"] = c.get(f"{b}.ry", 0.0) + a * wave(f, N, cycles, phase - lag)
    c["root.ry"] = c.get("root.ry", 0.0) - steady * 0.6 * amps[0] * wave(f, N, cycles, phase + 0.1)


def fins(c, f, N, cycles, amp=1.0, tuck=0.0, phase=0.0):
    """Side fins scull (flap + feather), dorsal follows; tuck 1 = folded back along the body (fast swim)."""
    for side, sg, ph in (("L", 1, 0.0), ("R", -1, 0.5)):
        w = wave(f, N, cycles, phase + ph * 0.15)
        c[f"fin{side}.rz"] = c.get(f"fin{side}.rz", 0.0) + sg * (12 * amp * w - 6 * tuck)
        c[f"fin{side}.twist"] = c.get(f"fin{side}.twist", 0.0) + sg * 20 * amp * wave(f, N, cycles, phase + ph * 0.15 - 0.25)
        c[f"fin{side}.ry"] = c.get(f"fin{side}.ry", 0.0) - sg * 18 * tuck
    c["dorsal.rz"] = c.get("dorsal.rz", 0.0) + 3 * wave(f, N, cycles, phase + 0.3)


def f_base(rig, f, N, cycles=2, amp=1.0):
    c = {}
    b = wave(f, N, cycles)
    c["root.ty"] = 0.004 + 0.004 * b * amp
    c["root.rx"] = 1.5 * wave(f, N, cycles, 0.2) * amp
    c["body1.sx"] = 1.0 + 0.015 * wave(f, N, cycles, 0.1) * amp       # breathing: the head swells a little
    c["body2.sx"] = 1.0 / c["body1.sx"]
    return c


def puff(c, s):
    """Cheeks puff: the head segment widens and deepens (children compensated)."""
    c["body1.sx"] = c.get("body1.sx", 1.0) * s; c["body1.sz"] = c.get("body1.sz", 1.0) * s
    c["body2.sx"] = c.get("body2.sx", 1.0) / s; c["body2.sz"] = c.get("body2.sz", 1.0) / s


@clip("fish", "idle", 120, True,
      notes="hovering in place: gentle bob and pitch, side fins sculling (feathering on the return), a slow lazy "
            "tail sweep (body wave at low amplitude), the mouth works softly (breathing water), blinks")
def fish_idle(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=1.0)
    body_wave(c, f, N, 1, (1.5, 3.0, 5.0, 10.0))
    fins(c, f, N, 4, amp=1.0)
    c["jaw.rx"] = 2.0 + 2.0 * wave(f, N, 2, 0.4)
    blink_ch(c, rig, f, N, [18, 76, 83])
    return c


F_SWIM = (0.192, 1.0)          # "stride" per loop: natural speed 0.192 / 1.6 s = 0.12 units/s


@clip("fish", "swim", 48, True, speed=F_SWIM,
      notes="a body wave travelling from head to tail (relative yaw per segment, phase lag head -> tail, amplitude "
            "growing toward the tail fin), the head held steady along the travel, side fins tucked back with small "
            "strokes, dorsal fin trailing, a small bob; natural speed 0.12 units/s")
def fish_swim(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=0.8)
    body_wave(c, f, N, 1, (4.0, 7.0, 11.0, 20.0))
    fins(c, f, N, 1, amp=0.6, tuck=1.0, phase=0.1)
    c["root.rz"] = 2.0 * wave(f, N, 1, 0.3)
    c["jaw.rx"] = 1.0
    blink_ch(c, rig, f, N, [30])
    return c


GULP_N = 96
GULP_AT = 38


@clip("fish", "gulp", GULP_N, False, markers={"open": 30, "gulp": GULP_AT},
      root_motion="root rises 0.10, lunges 0.08 forward (+Z), sinks back to (0, 0, 0) by the end",
      notes="spots its dinner (eyes wide, tail curls back to wind up), rises 0.10 with the nose up, the jaw opens to "
            "55 deg, lunges 0.08 forward, SNAPS shut (`gulp`, frame 38), cheeks bulge and a swallow lump runs down "
            "the body, sinks back down and drifts back to its mark with a satisfied tail wag; holds")
def fish_gulp(rig, f, N):
    c = f_base(rig, f, N, cycles=2, amp=0.3)
    rise = ease_io((f - 10) / 18)
    sink = ease_io((f - 50) / 30)
    lunge = ease_io((f - 30) / 7) ** 1.5
    c["root.ty"] = 0.004 + 0.100 * rise * (1 - sink) - 0.004 * bump(f, 2, 12) * (1 - rise)
    c["root.tz"] = 0.080 * lunge * (1 - ease_io((f - 54) / 30))
    c["root.rx"] = -14 * rise * (1 - ease_io((f - 32) / 6)) + 6 * bump(f, 36, 48) - 4 * bump(f, 2, 12)
    wind = bump(f, 0, 20)
    c["body2.ry"] = 6 * wind; c["body3.ry"] = 12 * wind; c["tail.ry"] = 22 * wind
    c["body3.rx"] = 6 * rise * (1 - sink); c["tail.rx"] = 10 * rise * (1 - sink)
    opened = ease_io((f - 14) / 16)
    shut = ease_io((f - (GULP_AT - 2)) / 2.5)
    c["jaw.rx"] = 55.0 * opened * (1 - shut) + 4 * bump(f, GULP_AT, GULP_AT + 8)
    bul = bump(f, GULP_AT, GULP_AT + 18)
    puff(c, 1.0 + 0.14 * bul)
    lump2 = bump(f, GULP_AT + 10, GULP_AT + 26); lump3 = bump(f, GULP_AT + 20, GULP_AT + 36)
    s2 = 1.0 + 0.10 * lump2
    c["body2.sx"] *= s2; c["body2.sz"] *= s2; c["body3.sx"] = 1.0 / s2 * (1.0 + 0.08 * lump3)
    c["body3.sz"] = 1.0 / s2 * (1.0 + 0.08 * lump3); c["tail.sx"] = 1.0 / (1.0 + 0.08 * lump3)
    c["tail.sz"] = 1.0 / (1.0 + 0.08 * lump3)
    wag = ease_io((f - 58) / 6) * (1 - ease_io((f - 86) / 8))
    body_wave(c, f, 24, 1, (2.0 * wag, 4.0 * wag, 7.0 * wag, 14.0 * wag))
    fins(c, f, N, 6, amp=1.0 + 1.5 * lunge * (1 - sink), tuck=0.6 * rise * (1 - sink))
    c["eyelids.sy"] = 1.0
    if GULP_AT - 1 <= f <= GULP_AT + 16:
        c["eyelids.sy"] = CLOSED["fish"]
    elif f > GULP_AT + 16:
        blink_ch(c, rig, f, N, [74], loop=False)
    return c


@clip("fish", "burp", 54, False, markers={"burp": 22},
      notes="oops: the cheeks puff up, a small hop (tail flick), the jaw pops open 10 deg with the burp (`burp`), the "
            "puff goes down, an embarrassed little wiggle; ends in the idle pose")
def fish_burp(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.4)
    pf = ease_io(f / 12) * (1 - ease_io((f - 22) / 8))
    puff(c, 1.0 + 0.15 * pf)
    hop = bump(f, 12, 32)
    c["root.ty"] += 0.006 + 0.030 * hop; c["root.rx"] += -6 * bump(f, 10, 22) + 4 * bump(f, 22, 34)
    c["tail.rx"] = 14 * bump(f, 8, 18) - 5 * bump(f, 18, 30)
    c["jaw.rx"] = 10.0 * bump(f, 19, 34) + 1.0
    wig = bump(f, 32, 52)
    c["root.rz"] = 5 * wig * math.sin(2 * math.pi * (f - 32) / 10)
    c["root.ry"] = 4 * wig * math.sin(2 * math.pi * (f - 34) / 10)
    fins(c, f, N, 3, amp=1.0 + hop)
    blink_ch(c, rig, f, N, [6, 40], loop=False)
    return c


SPIT_AT = 24


@clip("fish", "spit", 60, False, markers={"spit": SPIT_AT},
      root_motion="root rears up 0.05, recoils 0.05 backward (-Z) at the spit, returns to (0, 0, 0)",
      notes="breathes in (cheeks puff), rears up with the nose high and the tail tucked under, throws its head "
            "forward and spits - jaw wide (50 deg) - with the body recoiling 0.05 backward (`spit`, frame 24), then "
            "shakes its head, shuts the mouth and settles back on its mark")
def fish_spit(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.3)
    rear = ease_io(f / 14) * (1 - ease_io((f - 18) / 6))
    fwd = bump(f, 16, 30)
    rec = ease_io((f - SPIT_AT) / 4) * (1 - ease_io((f - 32) / 22))
    hi = ease_io(f / 10) * (1 - ease_io((f - 36) / 20))
    c["root.ty"] = 0.004 + 0.040 * hi + 0.020 * rear
    c["root.rx"] = -14 * rear + 3 * fwd - 10 * rec
    c["root.ty"] += 0.016 * bump(f, 18, 32)
    c["root.tz"] = -0.050 * rec + 0.010 * fwd
    c["root.ty"] += 0.022 * rec
    c["body3.rx"] = 12 * rear - 6 * rec; c["tail.rx"] = 18 * rear - 10 * rec
    puff(c, 1.0 + 0.16 * ease_io(f / 12) * (1 - ease_io((f - SPIT_AT) / 3)))
    c["jaw.rx"] = 50.0 * ease_io((f - (SPIT_AT - 3)) / 3) * (1 - ease_io((f - 32) / 10)) + 1.0
    shake = math.sin(2 * math.pi * (f - 34) / 7) * bump(f, 34, 50)
    c["root.ry"] = 6 * shake
    fins(c, f, N, 3, amp=1.0 + rec)
    c["eyelids.sy"] = CLOSED["fish"] * 0.8 if SPIT_AT - 4 <= f <= SPIT_AT + 4 else 1.0
    if f > SPIT_AT + 10:
        blink_ch(c, rig, f, N, [48], loop=False)
    return c


@clip("fish", "wave_fin", 60, True,
      notes="rolls a little onto its left side (the right fin side comes up) and flaps the right fin up and down in a "
            "big friendly wave, the left fin paddles, the tail wags slowly, happy blinks")
def fish_wave_fin(rig, f, N):
    c = f_base(rig, f, N, cycles=1, amp=0.6)
    c["root.rz"] = -14 + 2 * wave(f, N, 1, 0.2)
    c["root.ty"] += 0.012
    fl = wave(f, N, 3, 0.0)
    c["finR.rz"] = -40 - 32 * fl; c["finR.ry"] = 20; c["finR.twist"] = -20 * wave(f, N, 3, -0.2)
    fins(c, f, N, 2, amp=0.6)
    c["finR.rz"] = -40 - 32 * fl
    body_wave(c, f, N, 1, (1.0, 2.0, 4.0, 9.0))
    blink_ch(c, rig, f, N, [12, 44])
    return c


# =============================================================================================== evaluation
HAND_SPACES = ("handL", "handR")


def ik_world(rig, M, t, space):
    Mroot = M["root"] @ rig.rest["root"].inverted()
    if space in M and space != "root":
        return to_d(M[space] @ (rig.rest[space].inverted() @ to_bl(rig.head[space] + Vector(t))))
    return to_d(Mroot @ to_bl(Vector(t)))


def ik_limb(rig, basis, M, chs, limb):
    """Kit ik_limb + an optional second target `ikb.<limb>` (own space and pole) blended in world space by
    `ikbw.<limb>`: lets a hand travel between targets held in different bones' spaces without a pop."""
    if "ikb." + limb not in chs or chs.get("ikbw." + limb, 0.0) <= 1e-4:
        return _kit_ik_limb(rig, basis, M, chs, limb)
    wb = chs["ikbw." + limb]
    Mroot = M["root"] @ rig.rest["root"].inverted()
    ta = ik_world(rig, M, chs["ik." + limb], chs.get("ikspace." + limb, "root"))
    tb = ik_world(rig, M, chs["ikb." + limb], chs.get("ikbspace." + limb, "root"))
    tw = ta.lerp(tb, wb)
    t_root = CI @ (Mroot.inverted() @ to_bl(tw))
    pa = chs.get("pole." + limb, default_pole(limb)); pb = chs.get("ikbpole." + limb, pa)
    ch2 = dict(chs)
    ch2["ik." + limb] = t_root; ch2["ikspace." + limb] = "root"; ch2["pole." + limb] = vlerp(pa, pb, wb)
    return _kit_ik_limb(rig, basis, M, ch2, limb)


COAT = {"coatL": "thighL", "coatR": "thighR", "belt1": "thighL"}
FOOT_EPS = 0.0008
FLOOR_CHAIN = 0.008      # min height of a chain bone's tail (the panel / prop mesh has thickness)


def coat_follow(rig, basis, M, w):
    """Seated / lying / kneeling: the coat panels and the belt end lie along the thighs (half way to hanging) instead
    of hanging through the page."""
    Mroot3 = (M["root"] @ rig.rest["root"].inverted()).to_3x3().normalized()
    down = Mroot3 @ Vector((0, 0, -1))
    for n, th in COAT.items():
        if n not in rig.names:
            continue
        td = (M[th].to_3x3().normalized() @ Vector((0, 1, 0))).normalized()
        up = Mroot3 @ Vector((0, 0, 1))
        td = td - up * td.dot(up)                       # along the thigh, but level: drapes, never sticks up
        td = td.normalized() if td.length > 1e-4 else (Mroot3 @ (C @ V(0, 0, 1)))
        sx = 1 if n.endswith("L") or n == "belt1" else -1
        out = Mroot3 @ (C @ V(sx, 0, 0))
        want = (td * 0.62 + down * 0.38).normalized()
        Cm = rig.carried(M, n).to_3x3().normalized()
        cur = (Cm @ basis[n][0].to_matrix())
        cy = cur.col[1].normalized()
        R = cy.rotation_difference(cy.slerp(want, w) if cy.dot(want) > -0.999 else want).to_matrix()
        rig.set_world_rot(basis, M, n, R @ cur)


def solve_pose(rig, chs):
    basis = rig.basis_from(chs)
    M = rig.fk(basis)
    if rig.fish:
        return chs, basis, M
    for limb in ("legL", "legR"):
        ik_limb(rig, basis, M, chs, limb)
    late = []
    for limb in ("armL", "armR"):
        if chs.get("ikspace." + limb, "root") in HAND_SPACES or chs.get("ikbspace." + limb, "root") in HAND_SPACES:
            late.append(limb); continue
        ik_limb(rig, basis, M, chs, limb)
    for limb in late:
        ik_limb(rig, basis, M, chs, limb)
    if chs.get("coatfollow", 0.0) > 1e-4:
        coat_follow(rig, basis, M, chs["coatfollow"])
    return chs, basis, M


def foot_low(rig, M, side):
    """Lowest skinned point of a foot (all foot / toe / lower-shin vertices), root space."""
    lo = 1e9
    for co, ws in rig.footproxy[side]:
        p = Vector((0, 0, 0))
        for b, w in ws:
            p += w * ((M[b] @ rig.rest_inv[b]) @ co)
        lo = min(lo, p.z)
    return lo


def evaluate_primary(rig, clip_, f):
    """Clip channels -> pose; `settle` (da_animate): move a bone up / down so the lowest proxy vertex of the given
    bones touches the page (a list = applied in order)."""
    chs = clip_.fn(rig, f, clip_.N)
    out = solve_pose(rig, chs)
    st = chs.get("settle")
    if st:
        for bone, vbones, target, w in (st if isinstance(st, list) else [st]):
            if w <= 1e-4:
                continue
            _, _, M = out
            pts = rig.skin(M, set(vbones) if vbones else None, prop=bool(chs.get("seaweed_on")))
            low = min(p.y for p in pts)
            chs[bone + ".ty"] = chs.get(bone + ".ty", 0.0) + w * (target - low)
            out = solve_pose(rig, chs)
    # foot settle: an IK foot whose skinned sole / toe / calf dips under the page is lifted (the model's toes dip
    # when the knee bends; a calf on the page when the legs are out)
    if not rig.fish and not chs.get("nofootfix"):
        lift = False
        for side in "LR":
            k = "ik.leg" + side
            if k in chs and chs.get("ikw.leg" + side, 1.0) > 0.5 and chs[k].y < 0.08:
                lo = foot_low(rig, out[2], side)
                if lo < FOOT_EPS:
                    chs[k] = Vector(chs[k]) + V(0, FOOT_EPS - lo, 0); lift = True
        if lift:
            out = solve_pose(rig, chs)
    # floor clamp (transitions between seated / lying / standing): never let the body dip under the page
    if chs.get("floorclamp"):
        _, _, M = out
        low = min([p.y for p in rig.skin(M, prop=bool(chs.get("seaweed_on")))] + [foot_low(rig, M, sd) for sd in "LR"])
        if low < -0.002:
            chs["root.ty"] = chs.get("root.ty", 0.0) + (-0.002 - low)
            out = solve_pose(rig, chs)
    return out


CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "jonah": [(("coatL",), 80.0, 7.0, 0.22, 16.0), (("coatR",), 80.0, 7.0, 0.22, 16.0),
              (("belt1",), 90.0, 7.5, 0.30, 24.0), (("seaweed",), 110.0, 6.5, 0.0, 22.0)],
    "captain": [(("wrap1",), 90.0, 8.0, 0.30, 24.0), (("sash1",), 85.0, 7.5, 0.30, 22.0)],
    "fish": [(("dorsal",), 160.0, 9.0, 0.0, 10.0)],
}


def sim_chains(rig, prim, loop, gscale=1.0, floor=FLOOR_CHAIN):
    """ru_animate.sim_chains (+ gscale: seated / lying clips do not pull the coat toward the rest hang)."""
    N = len(prim) - 1
    for names, k, cdamp, gw, lim in CHAINS[rig.ch]:
        if any(n not in rig.names for n in names):
            continue
        gw = gw * gscale
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
                hz = M[n].translation.z          # keep the dangling end above the page (seated, rolling, lying)
                need = (floor - hz) / rig.length[n]
                if s.z < need and need < 0.99:
                    hor = Vector((s.x, s.y, 0.0))
                    hor = hor.normalized() if hor.length > 1e-6 else Vector((1, 0, 0))
                    s = hor * math.sqrt(max(0.0, 1 - need * need)) + Vector((0, 0, need))
                    v = v * 0.3
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


_BAKED = {}


def bake_clip(rig, clip_):
    """Kit bake_clip, with the clip's chain gravity scale; cached per run (probe / contact bake each clip once)."""
    if clip_.action in _BAKED:
        return _BAKED[clip_.action]
    N = clip_.N
    prim = [evaluate_primary(rig, clip_, f) for f in range(N + 1)]
    if clip_.loop:
        chs0, b0, M0 = prim[0]
        bN = {n: [b0[n][0].copy(), b0[n][1].copy(), b0[n][2].copy()] for n in b0}
        prim[N] = (prim[N][0], bN, rig.fk(bN))
    sim_chains(rig, prim, clip_.loop, gscale=0.0 if clip_.seated else 1.0, floor=FLOOR_CHAIN if clip_.action != "jonah_fall_in" else FALL_FLOOR)
    if clip_.loop:
        b0 = prim[0][1]
        bN = {n: [b0[n][0].copy(), b0[n][1].copy(), b0[n][2].copy()] for n in b0}
        prim[N] = (prim[N][0], bN, rig.fk(bN))
    out = [(p[1], p[2]) for p in prim]
    _BAKED[clip_.action] = out
    return out


# =============================================================================================== scene helpers
def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rigs = {ch: Rig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    RIGS.clear(); RIGS.update(rigs)
    return sc, rigs


def contract_clips():
    return {"jonah": ["idle", "talk", "walk", "tiptoe", "stomp_walk", "listen_up", "refuse", "sleep_curl",
                      "wake_startled", "ashamed", "fall_in", "sit_hold_nose", "kneel_pray", "tumble_out", "sit_dazed",
                      "stand_up", "nod_ok", "proclaim", "surprised", "sit_sulk", "relax_happy", "wail", "look_city",
                      "wave"],
            "captain": ["idle", "talk", "walk", "greet", "steer_hard", "shake_awake", "refuse_hands", "heave", "amazed"],
            "fish": ["idle", "swim", "gulp", "burp", "spit", "wave_fin"]}


PROPS = ("seaweed",)


def hidden_props(rig, cl):
    out = []
    for p in PROPS:
        nm = f"{rig.ch}_{p}"
        if nm in bpy.data.objects and p not in cl.props:
            out.append(nm)
    return out


def clip_checks(rig, cl, frames):
    """da_animate.clip_checks: lowest mesh point (real evaluated meshes), planted-foot drift for in-place clips, the
    stance slip of locomotion clips (feet glued to the page when the actor moves at the natural speed), the loop seam,
    and the max rotation step between frames (pops)."""
    out = {}
    ad = rig.obj.animation_data
    keep = ad.action if ad else None
    if ad:
        ad.action = None
    loc0, rot0 = rig.obj.location.copy(), rig.obj.rotation_euler.copy()
    rig.obj.location = (0, 0, 0); rig.obj.rotation_euler = (0, 0, 0)
    step = 3 if cl.N <= 60 else 4
    lows = []
    low_at = None
    skip = hidden_props(rig, cl)
    for fr in range(0, cl.N + 1, step):
        apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
        pts = mesh_points(rig, skip_props=skip)
        lp = min(pts, key=lambda q: q[0].y)
        lows.append(lp[0].y)
        if lp[0].y <= min(lows):
            prox = min(((p, d) for p, (co, ws, d) in zip(rig.skin(frames[fr][1], prop=True), rig.proxy)), key=lambda q: q[0].y)
            low_at = [fr, lp[1], [round(v, 3) for v in lp[0]], "proxy bone " + prox[1]]
    out["meshMinY"] = round(min(lows), 4)
    if min(lows) < -0.004 or cl.seated:
        out["meshMinAt"] = low_at
    if not rig.fish:
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

            def cpts(M, side):
                fm = M["foot" + side] @ rig.rest_inv["foot" + side]
                a = rig.head["foot" + side]
                return [to_d(fm @ to_bl(a + q)) for q in foot_points(rig, side)]
            for side in "LR":
                for fr in range(cl.N):
                    q0, q1 = cpts(frames[fr][1], side), cpts(frames[fr + 1][1], side)
                    i = min(range(len(q0)), key=lambda j: q0[j].y)
                    p0, p1 = q0[i], q1[i]
                    if p0.y < 0.0015 and p1.y < 0.0015:
                        err = max(err, math.hypot(p1.x - p0.x, (p1.z - p0.z) + v) * FPS)
            out["stanceSlipMax"] = round(err, 4)
    elif cl.speed is not None:
        out["naturalSpeed"] = round(cl.natural_speed, 4)
    # pops: largest per-frame step of any bone tail (inside the clip) and, for loops, at the seam
    steps, sbone = [], []
    for fr in range(cl.N):
        M0, M1 = frames[fr][1], frames[fr + 1][1]
        st_ = [((rig.pos(M0, n, "tail") - rig.pos(M1, n, "tail")).length, n) for n in rig.names if n != "eyelids"]
        m_ = max(st_)
        steps.append(m_[0]); sbone.append(m_[1])
    out["maxStep"] = round(max(steps), 4)
    out["maxStepAt"] = [steps.index(max(steps)), sbone[steps.index(max(steps))]]
    if cl.loop:
        M0, MN, M1 = frames[0][1], frames[-1][1], frames[1][1]
        out["seamStep"] = round(max((rig.pos(MN, n, "tail") - rig.pos(M1, n, "tail")).length for n in rig.names
                                    if n != "eyelids"), 4)
        out["seamOK"] = out["seamStep"] <= max(steps) + 2e-4
    reset_pose(rig)
    rig.obj.location, rig.obj.rotation_euler = loc0, rot0
    if ad:
        ad.action = keep
    return out


def travel_needs():
    """Per move with a `to` in the timeline: distance, time until the actor's next beat, needed speed and the rate
    against the clip's natural speed (StoryDirector plays locomotion at most 1.6x; other clips glide)."""
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
        if p0 is None or a["t"] <= 0.01:
            continue
        nxt = next((b["t"] for b in acts[i + 1:] if b["who"] == who), TL["duration"])
        dist = math.hypot(to[0] - p0[0], to[1] - p0[1])
        if dist < 1e-4:
            continue
        row = {"t": round(a["t"], 2), "action": act, "from": p0, "to": to, "dist": round(dist, 3),
               "time": round(nxt - a["t"], 2), "needSpeed": round(dist / max(0.01, nxt - a["t"]), 3)}
        if act in loco:
            row["naturalSpeed"] = round(loco[act].natural_speed, 3)
            row["rate"] = round(row["needSpeed"] / loco[act].natural_speed, 2)
        else:
            row["glide"] = True
            row["glideSeconds"] = round(max(0.6, dist / 0.12), 2)
        out.append(row)
    return out


SAMPLE_BONES = ("root", "head", "jaw", "handR", "handL", "footL", "toeR", "hips", "coatL", "belt1", "wrap1", "sash1",
                "body1", "body3", "tail", "finR", "dorsal")


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    extra = {ch: sorted(set(have[ch]) - set(want[ch])) for ch in CHARS}
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl,
            "requestedClips": TL.get("requestedClips") or [], "extraClips": extra,
            "stage": {"heaveDistance": HEAVE_D, "heaveMode": "tandem: Jonah HEAVE_D in front of the captain, both "
                      "facing the same way (captain behind him)", "heaveToFallInLag": HEAVE_LAG / FPS,
                      "shakeDistance": SHAKE_D, "shakeMode": "Jonah (sleep_curl, facing the viewer) lies with his head "
                      "toward the captain; the captain stands SHAKE_D from Jonah's root along the line of Jonah's "
                      "body and faces him", "kneel": KNEEL["jonah"]}}
    only = os.environ.get("JN_ONLY")
    for cl in CLIPS:
        if only and not any(cl.action.startswith(o) for o in only.split(",")):
            continue
        rig = rigs[cl.ch]
        frames = bake_clip(rig, cl)
        write_action(rig, cl, frames)
        rootmax = max(rig.pos(M, "root").length for _, M in frames)
        info = {"action": cl.action, "char": cl.ch, "clip": cl.name, "frames": cl.N, "seconds": round(cl.N / FPS, 3),
                "loop": cl.loop, "seated": cl.seated, "rootMotion": bool(cl.root_motion),
                "markers": {k: {"frame": v, "sec": round(v / FPS, 3)} for k, v in cl.markers.items()},
                "rootMaxOffset": round(rootmax, 5), "props": cl.props, "notes": cl.notes}
        if cl.extra:
            info["extra"] = True
        if cl.root_motion:
            info["rootMotionNote"] = cl.root_motion
            M_end = frames[-1][1]
            info["rootEnd"] = [round(v, 4) for v in rig.pos(M_end, "root")]
        if cl.speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            info["stride"] = cl.speed[0]
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        if cl.loop:
            info["loopSeamMaxErr"] = info["checks"]["seamStep"]
        print("JN_CHECK", cl.action, json.dumps(info["checks"]), flush=True)
        meta["clips"].append(info)
    meta["travel"] = travel_needs()
    for r in meta["travel"]:
        print("JN_TRAVEL", json.dumps(r))
    if only:
        print("JN_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "jn_anim.blend")
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
        print("JN_EXPORT", ch)
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("JN_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


# ----------------------------------------------------------------------------------------------- render helpers
REGIONS = json.load(open(REGIONS_JSON))
FACES = {ch: {"default": v["faceDecal"]["default"], "clips": v["faceDecal"].get("clipExpression", {})}
         for ch, v in REGIONS["characters"].items()}
DECAL_NODES = {}


def set_expression(ch, clip_name):
    expr = FACES[ch]["clips"].get(clip_name, FACES[ch]["default"])
    p = os.path.join(FACE_DIR, f"{ch}_{expr}.png")
    if not os.path.exists(p):
        p = os.path.join(FACE_DIR, f"{ch}_{FACES[ch]['default']}.png")
    DECAL_NODES[ch].image = bpy.data.images.load(p, check_existing=True)


def stage_of(cl):
    """Where a clip is shown in renders: (x, z, yaw). Humans on the road, the fish side-on in the open sea lane."""
    if cl.ch == "fish":
        return (-0.26, 0.06, -90.0)
    if cl.ch == "captain":
        return (0.40, 0.12, 0.0)
    return (0.26, 0.13, 0.0)


DIST_K = {"jonah": 1.25, "captain": 1.25, "fish": 3.4}


PAIRS = [  # contact-sheet pair rows: (A action, B action, distance, mode, B lag, label)
    ("captain_heave", "jonah_fall_in", HEAVE_D, "tandem", HEAVE_LAG,
     "pair: heave + fall_in (tandem 0.10, on the deck at RAIL)"),
    ("captain_shake_awake", "jonah_sleep_curl", SHAKE_D, "lie", 0,
     "pair: shake_awake + sleep_curl (0.19, on the deck)"),
]
PAIR_AT = {"tandem": (-0.22, -0.16, 0.10), "lie": (-0.28, -0.24, 0.10), "face": (0.30, 0.12, 0.0)}


def place_pair_mode(ra, rb, dist, mode, at=None):
    """B (the partner) at `at` = (x, z, y); A placed `dist` from B. face: they face each other (A -> +X, B -> -X);
    tandem: A behind B, both facing +Z; lie: A at -X facing +X, B facing +Z (the viewer)."""
    bx, bz, y = at or PAIR_AT[mode]
    if mode == "face":
        place_rig(ra, bx - dist, bz, 90.0, y); place_rig(rb, bx, bz, -90.0, y)
    elif mode == "tandem":
        place_rig(ra, bx, bz - dist, 0.0, y); place_rig(rb, bx, bz, 0.0, y)
    else:
        place_rig(ra, bx - dist, bz, 90.0, y); place_rig(rb, bx, bz, 0.0, y)
    return V(bx - dist / 2 if mode != "tandem" else bx, y, bz - (dist / 2 if mode == "tandem" else 0.0))


def pair_cams(T, mode):
    k = 0.36
    return {"front": T + V(0.0, 0.10, 0.55 * k / 0.36), "q3": T + V(0.30, 0.16, 0.34), "top": T + V(0.0, 0.50, 0.16),
            "back": T + V(0.0, 0.14, -0.50), "side": T + V(0.50, 0.10, 0.0), "lside": T + V(-0.50, 0.10, 0.0),
            "phone": T + V(0.10, 0.42, 0.62)}


HIDE_SET = ("belly", "plantSmall", "plantBig", "plantDry", "worm", "shelter")


def setup_look_jn(sc, res, samples=8):
    """Kit setup_look + hide the coast's hidden-at-start props (belly dome, plants, worm, shelter)."""
    setup_look(sc, res, samples=samples)
    for o in bpy.data.objects:
        q = o
        while q is not None:
            if q.name.split(".")[0] in HIDE_SET:
                o.hide_render = True; break
            q = q.parent


def mode_contact():
    sc, rigs = open_scene()
    setup_look_jn(sc, (340, 340), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    clips = {c.action: c for c in CLIPS}
    for cl in CLIPS:
        rig = rigs[cl.ch]
        show_only(rigs, [cl.ch], {cl.ch: cl})
        set_expression(cl.ch, cl.name)
        frames = bake_clip(rig, cl)
        mk = sorted(set(cl.markers.values()))
        picks = sorted(set([0, cl.N] + [int(round(cl.N * k / 5)) for k in range(1, 5)] + mk))
        while len(picks) > 7:
            cand = [p for p in picks if p not in mk and p not in (0, cl.N)] or [p for p in picks if p not in (0, cl.N)]
            picks.remove(cand[len(cand) // 2])
        mark = stage_of(cl)
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": []}
        for fr in picks:
            apply_basis(rig, frames[fr][0])
            place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            view = "side" if cl.ch == "fish" else "q3"
            view_cam(cam, rig, mark, view, dist_k=DIST_K[cl.ch])
            if cl.root_motion and cl.ch == "jonah":
                view_cam(cam, rig, (mark[0] - 0.06, mark[1] + 0.03, mark[2]), view, dist_k=1.7)
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("JN_CONTACT_ROW", cl.action, picks, flush=True)
    for a, b, dist, mode, lag, label in PAIRS:
        ca, cb = clips[a], clips[b]
        ra, rb = rigs[ca.ch], rigs[cb.ch]
        show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
        set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
        fa_, fb_ = bake_clip(ra, ca), bake_clip(rb, cb)
        row = {"action": label, "loop": ca.loop, "frames_total": ca.N, "frames": []}
        sel = [lag, lag + 12, lag + 23, min(ca.N, lag + 32)] if mode == "tandem" else [0, ca.N // 4]
        for fr in sel:
            fb = max(0, min(cb.N, fr - lag)) if not cb.loop else fr % cb.N
            apply_basis(ra, fa_[fr][0]); apply_basis(rb, fb_[fb][0])
            T = place_pair_mode(ra, rb, dist, mode)
            bpy.context.view_layer.update()
            views = ("q3", "side") if mode == "tandem" else ("front", "q3")
            for vn in views:
                look(cam, T + V(0, 0.14, 0), pair_cams(T + V(0, 0.14, 0), mode)[vn], lens=40)
                fn = f"pair_{a}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                row["frames"].append({"f": fr, "file": fn, "marker": vn})
        reset_pose(ra); reset_pose(rb)
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """JN_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'pair:<A>:<B>:<dist>:<frameA>[:mode[:views]]' (mode face|tandem|lie; B at frameA - JN_PAIR_LAG, or B's loop frame)."""
    sc, rigs = open_scene()
    res = int(os.environ.get("JN_PROBE_RES", "440"))
    setup_look_jn(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    clips = {cl.action: cl for cl in CLIPS}
    out = []
    lag = int(os.environ.get("JN_PAIR_LAG", "0"))
    for item in os.environ.get("JN_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "pair":
            a, b, dist, fr = parts[1], parts[2], float(parts[3]), int(parts[4])
            mode = parts[5] if len(parts) > 5 else "face"
            views = parts[6].split(",") if len(parts) > 6 else ["front", "q3", "top", "side"]
            ca, cb = clips[a], clips[b]
            ra, rb = rigs[ca.ch], rigs[cb.ch]
            show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
            set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
            fb = (fr % cb.N) if cb.loop else max(0, min(cb.N, fr - lag))
            apply_basis(ra, bake_clip(ra, ca)[min(fr, ca.N)][0]); apply_basis(rb, bake_clip(rb, cb)[fb][0])
            T = place_pair_mode(ra, rb, dist, mode) + V(0, 0.14, 0)
            bpy.context.view_layer.update()
            cams = pair_cams(T, mode)
            for vn in views:
                look(cam, T, cams[vn], lens=40)
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
        fr_ = bake_clip(rig, cl)
        mark = stage_of(cl)
        for fr in [int(v) for v in frames.split(",")]:
            fr = min(fr, cl.N)
            apply_basis(rig, fr_[fr][0]); place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            dk = float(os.environ.get("JN_PROBE_DIST", str(DIST_K[cl.ch])))
            view_cam(cam, rig, mark, view, bone, dist_k=dk)
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("JN_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("JN_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
