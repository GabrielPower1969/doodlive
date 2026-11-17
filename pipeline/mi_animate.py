"""Real Miracles skeletal animation (Animation role, story pack `miracles`).

Built on the shared kit (pipeline/story_kit/animation.py) the way pipeline/jn_animate.py is. Two halves in one file:

* Under Blender (headless) it opens `assets/miracles/model/characters.blend` (Characters role's rigs), builds every
  clip of docs/miracles/CONTRACT.md §4 as an action `<char>_<clip>` and exports
  `assets/miracles/anim/{jesus,peter,man,friend1,friend2,friend3,friend4}.glb` (character + skin + one glTF animation
  per action) and `clips.json`. The four friends share one set of clip functions (actions friend1_<clip> ...
  friend4_<clip>), each baked on its own rig with a small per-friend variation (timing offset, amplitudes).
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/mi_animate.py all        # build + verify + contact sheet + freshness check
    python3 pipeline/mi_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/mi_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/mi_animate.py contact    # anim/contact_sheet.png (key poses per clip, on the galilee set)
    MI_PROBE="man_stand_wobbly:0,40,80:front" python3 pipeline/mi_animate.py probe     # work renders ($MI_ANIM_WORK/probe.png)
    MI_PROBE="carry:0,12:side,q3" python3 pipeline/mi_animate.py probe                 # the carry group (man + friend1 +
        friend2 at CARRY_D ahead / behind, man at base CARRY_Y), frames of the shared 48-frame cycle
    MI_PROBE="pair:peter_shake_awake:jesus_lie_sleep:0.10:12:front" python3 pipeline/mi_animate.py probe
        pair modes: front (default for the story pairs: B faces +Z, A stands `dist` in front of B facing it), face
        (A and B face each other along X), tandem (B `dist` in front of A, same facing), lie (B faces A's right)
    MI_ONLY=man_carried,friend1_carry  (with build: bake + check a subset, no export)

How the motion is made (the script is the source, no hand-placed keys): see jn_animate.py / ru_animate.py. Each clip
is a function frame -> channels (rotations in DESIGN axes in the bone's rest frame: rx ry rz bend raise swing twist
curl; offsets tx ty tz; scale s / sx sy sz). Legs and arms use two-bone IK where a hand or foot must be somewhere.
Lying / kneeling / seated clips use `settle` (a skinned proxy of the body: the lowest vertex of the named bones is put
on a given height). Secondary motion (mantle drape, belt / sash ends, head-cloth tail, head-band tail) is a damped
spring chain. Props are bones: `mat` / `ropes` / `matRoll` (man), `bucket` (peter); their show / hide is a timeline
prop event, except the ropes, which every man clip keeps scaled to 0.001 and `lowered` scales in (RIG.md §3).
Intermediates: $MI_ANIM_WORK (default /tmp/miracles_anim).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MI = os.path.join(ROOT, "assets/miracles")
MODEL = os.path.join(MI, "model")
ANIM = os.path.join(MI, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
SET_GLB = os.path.join(MODEL, "galilee.glb")
TIMELINE = os.path.join(MI, "timeline.json")
REGIONS_JSON = os.path.join(MODEL, "regions_characters.json")
FRIEND_PAINT = os.path.join(MODEL, "friend_paint.png")
FACE_DIR = os.path.join(ROOT, "docs/miracles/design/faces")
WORK = os.environ.get("MI_ANIM_WORK") or "/tmp/miracles_anim"
ENV = "MI_"                      # env-var / log prefix the story_kit functions use (MI_PROBE_*, MI_NOSET)
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FPS = 30
FRIENDS = ("friend1", "friend2", "friend3", "friend4")
CHARS = ("jesus", "peter", "man") + FRIENDS

# stage numbers the clips are fitted to (art-width units; docs/miracles/ANIMATION.md "staging")
CARRY_Y = 0.10       # the man's base height while carried (story.py)
CARRY_HAND = 0.15    # the friends' grip height (world y) = the centre of the mat poles in `carried`
CARRY_D = 0.24       # friend1 (carry_front) this far ahead of the man's root, friend2 (carry_back) this far behind:
                     # the poles end at +-0.2036 and the front carrier's hands are 0.04 behind his hips (CONTRACT §4)
CARRY_N = 48         # one carry cycle (two steps, 1.6 s); the man's bob is one per step (0.8 s)
WAKE_D = 0.10        # peter_shake_awake: the sleeper's root (under his shoulder) 0.10 in front of Peter
KNEEL_D = 0.12       # jesus_kneel_kind: the lying man 0.12 in front of Jesus (CONTRACT §4)
ROOF = 0.40
ROPE_TOP = 0.47      # lowered: the rope tops stay at this local height (the friends' hands at the roof hole)

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
    """The Characters role may re-run mi_characters.py: the anim GLBs must be newer than the model files."""
    src = [BLEND] + [os.path.join(MODEL, f"{c}.glb") for c in CHARS]
    newest = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    outs = [os.path.join(ANIM, f"{c}.glb") for c in CHARS]
    stale = [o for o in outs if (not os.path.exists(o)) or os.path.getmtime(o) < newest]
    print("MI_FRESH", "STALE " + ", ".join(os.path.basename(o) for o in stale) if stale else
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
    d.text((pad, 14), "Real Miracles - key poses per clip (30 fps; frame / seconds; marker names in red; pair rows = two "
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
    print("MI_CONTACT", out, sheet.size)


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
CLOSED = {ch: 12.78 for ch in CHARS}                     # RIG.md §2: eyelids.sy closed (all seven)

# =============================================================================================== rig model (pure python FK)
class Rig:
    """ru_animate.Rig + da_animate's skinned body proxy (for `settle`: seated / lying clips touch the page)."""
    H_OF = {"man": 0.34, "jesus": 0.36, "peter": 0.38, "friend1": 0.35, "friend2": 0.37, "friend3": 0.33,
            "friend4": 0.36}

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
        self.fish = False
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
            if tot <= 0:
                continue
            co = mw @ v.co
            if co.z > 0.09:
                continue
            for side in "LR":
                if any(b in ("foot" + side, "toe" + side, "shin" + side) for b, _ in ws):
                    self.footproxy[side].append((co, [(b, w / tot) for b, w in ws]))

    def skin(self, M, bones=None, prop=False):
        """Deformed proxy points (design coords, root space) - only vertices whose dominant bone is in `bones`."""
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
            if g("yaw"): R = rot_d((0, 1, 0), g("yaw")) @ R          # yaw about the vertical, applied last
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
        self.props = props or []     # props shown in this clip (renders / checks): mat, ropes, matRoll, bucket
        self.backwards = backwards
        self.seated = seated         # seated / lying / kneeling: meshMinY >= -0.008 is a hard check
        self.root_motion = root_motion   # text: the root bone travels / is offset (carried, lowered, squeeze_bounce)

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
KNEEL = {ch: dict(KY=0.020, kz=0.016, thigh_back=10.0, shin_slope=22.0) for ch in CHARS}


# =============================================================================================== acting helpers
ARM_REST = {"man": -20.0, "jesus": -18.0, "peter": -12.0, "friend1": -20.0, "friend2": -8.0, "friend3": -20.0,
            "friend4": -20.0}
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
    """Arms crossed over the chest (chest space). loose 0..1 = lower and looser."""
    k = 1.12 if rig.ch in ("peter", "friend2") else 1.0
    fz = 0.018 if rig.ch in ("peter", "friend2") else 0.0   # big chests / bellies stand out further
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
SEAT_HIPS_Y = -0.140        # hips joint drops ~0.14 when sitting on the page (settle fine-tunes it)


def seat_legs(rig, c, legs="up", w=1.0, spread=0.0, kneeL=0.0, kneeR=0.0, toe=0.0):
    """Sitting: legs 'up' (knees up, soles flat) or 'out' (legs out in front, heels down). Hips down, settle on.
    kneeL / kneeR pull a foot in (0..1) for 'out' (one knee up)."""
    for side in "LR":
        sx = 1 if side == "L" else -1
        b = rig.head["foot" + side]
        if legs == "up":
            pt = 0.0 + toe
            tgt = V(b.x + sx * (0.010 + spread), planted_ankle_y(rig, side, pt), 0.092 * rig.H / 0.36)
            pole = V(0.25 * sx, 1.0, 0.4)
        else:
            pull = kneeL if side == "L" else kneeR
            pt = lerp(-62.0, -10.0, pull) + toe
            tgt = V(b.x + sx * (0.016 + spread), planted_ankle_y(rig, side, pt), lerp(0.150, 0.090, pull) * rig.H / 0.36)
            pole = V(0.2 * sx, 1.0, 0.25)
        cur = c.get(f"ik.leg{side}")
        c[f"ik.leg{side}"] = tgt if (cur is None or w >= 0.999) else vlerp(cur, tgt, w)
        c[f"foot{side}.pitch"] = lerp(c.get(f"foot{side}.pitch", 0.0), pt, w)
        c[f"pole.leg{side}"] = pole
    c["hips.ty"] = c.get("hips.ty", 0.0) + SEAT_HIPS_Y * w * rig.H / 0.34
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


# =============================================================================================== shared acting helpers
def rot_y(v, deg):
    """Design-space vector turned about the vertical (+deg: +Z -> +X)."""
    a = math.radians(deg)
    return V(v.x * math.cos(a) + v.z * math.sin(a), v.y, -v.x * math.sin(a) + v.z * math.cos(a))


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


_kit_stand_feet = stand_feet


def stand_feet(rig, chs, spread=0.0, fwdL=0.0, fwdR=0.0, pitchL=0.0, pitchR=0.0, liftL=0.0, liftR=0.0, fwd=0.0, xL=0.0,
               xR=0.0):
    """Kit stand_feet + the contact-point pivot (heel when the toes are up, ball when the heel is up), so a foot that
    only pitches does not slide."""
    _kit_stand_feet(rig, chs, spread, fwdL, fwdR, pitchL, pitchR, liftL, liftR, fwd, xL, xR)
    for side, pt in (("L", pitchL), ("R", pitchR)):
        if abs(pt) > 1e-6:
            chs[f"ik.leg{side}"] = Vector(chs[f"ik.leg{side}"]) - V(0, 0, pivot_dz(rig, side, pt))


def kH(rig):
    """Scale for hand / body targets written for a 0.36-tall character."""
    return rig.H / 0.36


def stand_pose(rig, f, N, cycles=1, amp=0.5, spread=0.003):
    c = h_base(rig, f, N, cycles=cycles, amp=amp)
    stand_feet(rig, c, spread=spread)
    return c


def hand_on_hip(c, rig, side, w=1.0):
    sx = 1 if side == "L" else -1
    k = kH(rig) * (1.12 if rig.ch in ("peter", "friend2") else 1.0)
    arm_ik(c, side, V(0.072 * sx * k, 0.192 * kH(rig), 0.004), V(0.9 * sx, 0.2, -0.6), "root", w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -24, w); fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 80, w))


def palm_up(c, side, lift, w=1.0):
    """Forearm raised, palm up and open (an offering / explaining hand). lift 0..1."""
    sx = 1 if side == "L" else -1
    c[f"upperArm{side}.raise"] = lerp(c.get(f"upperArm{side}.raise", -20), -20 + 10 * lift, w)
    c[f"upperArm{side}.bend"] = lerp(c.get(f"upperArm{side}.bend", 8), 8 + 34 * lift, w)
    c[f"forearm{side}.bend"] = lerp(c.get(f"forearm{side}.bend", 26), 26 + 50 * lift, w)
    c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", -10 * sx), -10 * sx - 74 * sx * lift, w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 6 - 20 * lift, w)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 22 - 16 * lift, w))


def hand_wave(c, rig, side, f, N, cycles, high=1.0, w=1.0):
    """Open hand raised beside the head, waving from the elbow / wrist (IK target in root space)."""
    sx = 1 if side == "L" else -1
    k = kH(rig)
    wg = wave(f, N, cycles, 0.0)
    arm_ik(c, side, V((0.076 + 0.008 * wg) * sx * k, (0.236 + 0.030 * high) * k, 0.046 * k), V(0.6 * sx, -1.0, 0.1),
           "root", w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 40, w)
    c[f"hand{side}.twist"] = lerp(c.get(f"hand{side}.twist", 0), -sx * (40 + 30 * wave(f, N, cycles, -0.15)), w)
    c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", 0), -60 * sx, w)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 6 + 10 * max(0.0, wg), w))


def jump(c, rig, f, a, b, h, crouch=0.016):
    """A hop between frames a (take-off) and b (landing): crouch before, air time, a soft landing; feet leave the
    page (IK targets rise with the hips). Returns the height of this hop at f."""
    pre = bump(f, a - 8, a + 1)
    land = bump(f, b - 1, b + 8)
    air = math.sin(math.pi * min(1.0, max(0.0, (f - a) / (b - a)))) if a < f < b else 0.0
    up = h * air
    c["hips.ty"] = c.get("hips.ty", 0.0) - crouch * (pre + land) + up
    for side in "LR":
        k = "ik.leg" + side
        if k in c:
            c[k] = Vector(c[k]) + V(0, up * 0.92, 0)
            c[f"foot{side}.pitch"] = c.get(f"foot{side}.pitch", 0.0) + 26 * air
    return up


def on_mat(c, w=1.0, top=0.026):
    """The man standing on his flat mat (pad top 0.025): feet and hips up by the pad thickness."""
    c["hips.ty"] = c.get("hips.ty", 0.0) + top * w
    for side in "LR":
        k = "ik.leg" + side
        if k in c:
            c[k] = Vector(c[k]) + V(0, top * w, 0)


# =============================================================================================== JESUS
@clip("jesus", "idle", 150, True,
      notes="standing relaxed, slow breathing, weight settles from one foot to the other (hips lead), hands loosely "
            "together in front, looks round the room with a soft smile (neck leads, head follows), irregular blinks; "
            "mantle drape and belt end settle")
def jesus_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.9)
    hands_clasped(c, rig, V(0.0, 0.150, 0.046) * kH(rig), w=0.85)
    sh = K([(0, -0.6), (30, -0.6), (60, 0.8), (100, 0.8), (130, -0.6), (150, -0.6)], f, N, True)
    shl = KL([(0, -0.6), (30, -0.6), (60, 0.8), (100, 0.8), (130, -0.6), (150, -0.6)], f, N, True, lag=8)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2.0 * sh; c["spine.rz"] = 1.2 * shl; c["chest.rz"] = 0.8 * shl
    c["head.rz"] = -1.2 * shl
    look_keys(c, [(0, 0), (20, 0), (36, 18), (70, 18), (86, -14), (120, -14), (136, 0), (150, 0)], f, N)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [14, 64, 71, 118])
    return c


@clip("jesus", "talk", 96, True,
      notes="warm, open-handed: the right hand opens palm-up toward the listener on the first phrase, both hands open "
            "on the second, the left hand to the heart at the end; nods on stressed syllables; jaw in an irregular "
            "syllable rhythm (lip sync overrides it)")
def jesus_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    beats = talk_jaw(c, f, N, 13)
    bt = beat_curve(beats, f, N, width=9); btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -2 + 3.0 * bt; c["head.ry"] = 5 * wave(f, N, 1, 0.1); c["head.rz"] = 3 * wave(f, N, 1, 0.35)
    pr = K([(0, 0.3), (10, 1.0), (40, 1.0), (52, 0.8), (70, 0.6), (86, 0.2), (96, 0.3)], f, N, True)
    pl = K([(0, 0.0), (28, 0.0), (40, 0.9), (52, 0.9), (62, 0.0), (96, 0.0)], f, N, True)
    hr = K([(0, 0.0), (60, 0.0), (70, 1.0), (80, 1.0), (92, 0.0), (96, 0.0)], f, N, True)
    palm_up(c, "R", pr * (0.8 + 0.2 * btl))
    palm_up(c, "L", pl * (0.8 + 0.2 * btl))
    arm_ik(c, "L", V(0.016, 0.006, 0.044) * kH(rig), V(0.8, -0.6, -0.2), "chest", hr)
    c["chest.ry"] = -4 * pr + 4 * pl; c["chest.rx"] += 1.2 * bt
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.4 * sh; c["spine.rz"] = 0.8 * sh
    stand_feet(rig, c, spread=0.003)
    blink_ch(c, rig, f, N, [7, 61])
    return c


J_WALK = (0.070, 0.60)


@clip("jesus", "walk", 36, True, markers={"contactL": 0, "contactR": 18}, speed=J_WALK,
      notes="calm, unhurried walk (100 steps/min): small hip bob, chest counter-turn, relaxed arm swing with lagging "
            "forearms, head level; mantle and belt end swing late")
def jesus_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=J_WALK[0], lift=0.011, duty=J_WALK[1], heel=12, toeoff=22)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.004 + 0.0026 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.35); c["head.ry"] = 2.5 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.0 * math.cos(ph); c["chest.rz"] = -1.2 * math.cos(ph - 0.5)
    c["head.rx"] = -1 + 1.0 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 8 - 13 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 13 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 28 - 8 * math.sin(ph - 1.0); c["forearmR.bend"] = 28 + 8 * math.sin(ph - 1.0)
    blink_ch(c, rig, f, N, [27])
    return c


@clip("jesus", "teach", 180, True,
      notes="standing teaching: turns from the left side of the room to the right and back (feet stay, hips -> chest "
            "-> head), the right hand open and explaining, the left hand comes to his heart twice; jaw in a talking "
            "rhythm; a smile nod to each side")
def jesus_teach(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.8)
    beats = talk_jaw(c, f, N, 29, amp=(4, 11))
    bt = beat_curve(beats, f, N, width=9)
    turn = [(0, -22), (20, -24), (44, 0), (70, 24), (104, 26), (128, 0), (156, -20), (180, -22)]
    c["hips.ry"] = 0.15 * K(turn, f, N, True); c["spine.ry"] = 0.15 * KL(turn, f, N, True, lag=3)
    c["chest.ry"] = 0.25 * KL(turn, f, N, True, lag=5); c["neck.ry"] = 0.2 * KL(turn, f, N, True, lag=7)
    c["head.ry"] = 0.25 * KL(turn, f, N, True, lag=9)
    c["head.rx"] = -2 + 2.5 * bt + 4 * (bump(f, 22, 40) + bump(f, 104, 122))
    lift = K([(0, 0.6), (30, 1.0), (60, 0.5), (90, 1.0), (130, 0.7), (160, 1.0), (180, 0.6)], f, N, True)
    palm_up(c, "R", lift * (0.85 + 0.15 * beat_curve(beats, f - 3, N, width=10)))
    c["upperArmR.raise"] += 12 * lift
    heart = K([(0, 0), (40, 0), (52, 1), (78, 1), (90, 0), (120, 0), (132, 1), (156, 1), (168, 0), (180, 0)], f, N, True)
    arm_ik(c, "L", V(0.018, 0.006, 0.044) * kH(rig), V(0.8, -0.6, -0.2), "chest", heart)
    c["handL.bend"] = lerp(6, 4, heart); fingers(c, "L", lerp(22, 10, heart))
    stand_feet(rig, c, spread=0.005, fwdR=0.006)
    blink_ch(c, rig, f, N, [12, 70, 77, 140])
    return c


@clip("jesus", "look_up_smile", 60, False, markers={"look": 14, "laugh": 30},
      notes="dust falls: a little start, he looks up at the ceiling (neck first, head after, chin high), a short "
            "laugh (shoulders bob twice), then a warm smile held looking up; hands open a little at his sides")
def jesus_look_up_smile(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    st = bump(f, 0, 9)
    up = ease_io((f - 4) / 14); upl = ease_io((f - 7) / 14)
    c["shoulderL.raise"] += 3 * st; c["shoulderR.raise"] += 3 * st
    c["spine.rx"] = -3 * up; c["chest.rx"] += -5 * up
    c["neck.rx"] = -16 * up; c["head.rx"] = -2 - 18 * upl
    c["head.rz"] = 5 * upl
    lg = pulses(f, N, [(30, 1.0), (36, 0.8), (42, 0.5)], decay=2.2, loop=False)
    c["shoulderL.raise"] += 3 * lg; c["shoulderR.raise"] += 3 * lg; c["chest.rx"] += 2 * lg; c["head.rx"] += 2 * lg
    c["jaw.rx"] = 7 * lg
    o = ease_io((f - 10) / 16)
    for side in "LR":
        c[f"upperArm{side}.raise"] += 10 * o; c[f"forearm{side}.bend"] = 26 + 14 * o; fingers(c, side, 22 - 12 * o)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [2, 48], loop=False)
    return c


def kneel_kind_pose(rig, f, N, w=1.0):
    """On the left knee, right foot forward, leaning toward the man lying KNEEL_D in front, right hand reaching
    toward his chest (hovering just above it)."""
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    kneel_legs(rig, c, wL=w, wR=0.0, hips_w=w)
    b = rig.head["footR"]
    c["ik.legR"] = V(b.x - 0.006, planted_ankle_y(rig, "R", 0), b.z + 0.075 * w)
    c["footR.pitch"] = 0.0; c["pole.legR"] = V(-0.2, 0.3, 1)
    c["spine.rx"] = 12 * w; c["chest.rx"] += 10 * w; c["neck.rx"] = 4 * w; c["head.rx"] = 10 * w
    arm_ik(c, "R", V(-0.012, 0.092, KNEEL_D - 0.012), V(-0.8, -0.3, -0.4), "root", w)
    c["handR.bend"] = lerp(6, -6, w); fingers(c, "R", lerp(22, 12, w))
    c["forearmR.twist"] = lerp(c.get("forearmR.twist", 10), -40, w)
    arm_ik(c, "L", V(0.050, 0.104, 0.060), V(0.9, -0.4, -0.2), "root", w)           # resting on the raised knee
    c["handL.bend"] = 10 * w
    c["coatfollow"] = 0.6 * w
    return c


@clip("jesus", "kneel_kind", 60, False, seated=True, markers={"down": 30},
      notes="in place (no walk): he kneels down on his left knee, right foot forward, leans toward the man lying 0.12 "
            "in front (KNEEL_D), the right hand reaching toward him, palm down, hovering over his chest; the left "
            "hand rests on the raised knee; gentle head tilt; holds, breathing. Knee on the floor (meshMinY >= -0.008)")
def jesus_kneel_kind(rig, f, N):
    a = stand_pose(rig, f, N, amp=0.4)
    w = ease_io((f - 2) / 28)
    b = kneel_kind_pose(rig, f, N, 1.0)
    c = mix(a, b, w)
    bR = rig.head["footR"]                      # the right foot steps forward (lifted, not slid)
    st = ease_io((f - 2) / 16)
    c["ik.legR"] = V(bR.x - 0.006, planted_ankle_y(rig, "R", 0) + 0.022 * bump(f, 2, 18), bR.z + 0.075 * st)
    c["footR.pitch"] = -12 * bump(f, 2, 18)
    c["head.rz"] = c.get("head.rz", 0.0) + 8 * ease_io((f - 30) / 16)
    c["chest.rx"] = c.get("chest.rx", 0.0) + 1.0 * wave(f, 60, 1)
    blink_ch(c, rig, f, N, [10, 44], loop=False)
    c["floorclamp"] = True
    return c


@clip("jesus", "stand_talk", 54, False, markers={"up": 26},
      notes="from kneel_kind's end pose he rises (push on the raised knee), turns his chest and head to the room and "
            "raises the right hand, open, as he speaks; holds standing, the hand up")
def jesus_stand_talk(rig, f, N):
    a = jesus_kneel_kind(rig, 60, 60)
    b = h_base(rig, f, N, cycles=1, amp=0.5)
    stand_feet(rig, b, spread=0.004, fwdR=0.010)
    up = ease_io((f - 26) / 18)
    b["upperArmR.raise"] = lerp(-18, 46, up); b["upperArmR.bend"] = lerp(8, 30, up)
    b["forearmR.bend"] = lerp(26, 70, up); b["forearmR.twist"] = lerp(10, -60, up)
    b["handR.bend"] = lerp(6, -12, up); fingers(b, "R", lerp(22, 6, up))
    b["chest.ry"] = 10 * up; b["neck.ry"] = 6 * up; b["head.ry"] = 8 * up; b["head.rx"] = -3 * up
    w = ease_io((f - 2) / 26)
    c = mix(a, b, w)
    bR = rig.head["footR"]                      # the right foot steps back beside the left (lifted)
    st = ease_io((f - 16) / 14)
    c["ik.legR"] = V(bR.x - lerp(0.006, 0.004, st), planted_ankle_y(rig, "R", 0) + 0.020 * bump(f, 16, 30),
                     bR.z + lerp(0.075, 0.010, st))
    c["footR.pitch"] = 0.0
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.012 * bump(f, 4, 28)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 10 * bump(f, 4, 26)
    if f > 26:
        c["jaw.rx"] = 7 * bump(f, 34, 42) + 5 * bump(f, 44, 52)
    blink_ch(c, rig, f, N, [30], loop=False)
    c["floorclamp"] = True
    return c


@clip("jesus", "command_rise", 50, False, markers={"rise": 24},
      notes="'Get up!': a breath, turns square to the man, both palms sweep up from low in front to chest height, "
            "open and lifting (palms up), with a small rise onto the toes and a firm nod; holds, palms up")
def jesus_command_rise(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    br = bump(f, 0, 14)
    sw = ease_io((f - 12) / 14)
    c["chest.rx"] += -3 * br - 2 * sw; c["shoulderL.raise"] += 3 * br; c["shoulderR.raise"] += 3 * br
    for side, sx in (("L", 1), ("R", -1)):
        lo = V(0.050 * sx, 0.120, 0.080) * kH(rig)
        hi = V(0.092 * sx, 0.268, 0.090) * kH(rig)
        arm_ik(c, side, vlerp(lo, hi, sw), V(0.9 * sx, -0.6, -0.2), "root", ease_io((f - 4) / 10))
        c[f"forearm{side}.twist"] = -80 * sx * ease_io((f - 6) / 10)
        c[f"hand{side}.bend"] = lerp(0, -26, sw); fingers(c, side, lerp(22, 4, sw))
    c["head.rx"] = -3 * sw + 6 * bump(f, 26, 38)
    c["jaw.rx"] = 9 * bump(f, 20, 32)
    toes = bump(f, 20, 40)
    c["hips.ty"] = 0.004 * toes
    stand_feet(rig, c, spread=0.005, pitchL=10 * toes, pitchR=10 * toes)
    blink_ch(c, rig, f, N, [4], loop=False)
    return c


# --- lying asleep on his left side facing +Z, head toward +X (on the stern cushion), knees drawn up; the root is
#     under his shoulder; the cushion top is 0.045 above his base (CONTRACT §4: ~0.05; SET.md: 0.10 - deck 0.06)
SLEEP_HIPS = V(-0.115, -0.150, 0.000)
PILLOW_Y = 0.045


def sleep_pose(rig, c, w=1.0, breathe=0.0):
    c["hips.rz"] = c.get("hips.rz", 0.0) - 90 * w
    c["hips.tx"] = c.get("hips.tx", 0.0) + SLEEP_HIPS.x * w
    c["hips.ty"] = c.get("hips.ty", 0.0) + SLEEP_HIPS.y * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + SLEEP_HIPS.z * w
    c["spine.rx"] = c.get("spine.rx", 0.0) + (10 - 1.5 * breathe) * w
    c["chest.rx"] = c.get("chest.rx", 0.0) + (8 - 2.0 * breathe) * w
    c["spine.rz"] = c.get("spine.rz", 0.0) + 4 * w; c["chest.rz"] = c.get("chest.rz", 0.0) + 6 * w
    c["neck.rz"] = c.get("neck.rz", 0.0) + 10 * w; c["head.rz"] = c.get("head.rz", 0.0) + 14 * w   # head up onto the cushion
    c["neck.rx"] = c.get("neck.rx", 0.0) + 6 * w; c["head.rx"] = c.get("head.rx", 0.0) + 6 * w
    for side in "LR":
        for k in ("ik.leg", "ikw.leg"):
            c.pop(k + side, None)
        c[f"thigh{side}.rx"] = c.get(f"thigh{side}.rx", 0.0) - (62 + 8 * (side == "R")) * w
        c[f"shin{side}.rx"] = c.get(f"shin{side}.rx", 0.0) + (88 - 6 * (side == "R")) * w
        c[f"foot{side}.rx"] = c.get(f"foot{side}.rx", 0.0) + 22 * w
    # the lower (left) hand under the cheek, the upper (right) arm resting over the side
    arm_ik(c, "L", V(0.044, 0.006, 0.036), V(0.0, -0.1, 1.0), "head", w)
    arm_ik(c, "R", V(-0.020, 0.060, 0.050), V(-0.3, 0.6, 0.6), "hips", w)
    c["handL.bend"] = 30 * w; c["handR.bend"] = 10 * w
    fingers(c, "L", lerp(22, 30, w)); fingers(c, "R", lerp(22, 30, w))
    c["coatfollow"] = max(c.get("coatfollow", 0.0), w)
    c["settle"] = ("hips", None, 0.0010, w)        # whole body incl. the mantle hem (it would dip 2 cm otherwise)


SLEEP_N = 150


@clip("jesus", "lie_sleep", SLEEP_N, True, seated=True,
      notes="asleep on his left side facing the viewer, head toward his +X resting on the stern cushion (head 0.045 "
            "up), knees drawn up, the lower hand under his cheek; slow deep breathing (two breaths per 5 s loop), a "
            "little smile, one foot twitch; eyes shut. Root under his shoulder; hips 0.115 toward -X, feet ~0.22")
def jesus_lie_sleep(rig, f, N):
    c = {}
    br = K([(0, 0), (40, 1.0), (52, 1.0), (75, 0.0), (115, 1.0), (127, 1.0), (150, 0.0)], f, N, True)
    sleep_pose(rig, c, 1.0, breathe=br)
    c["shoulderR.raise"] = 2.5 * br; c["head.rz"] += -1.5 * br
    tw = pulses(f, N, [(96, 1.0)], decay=2.0)
    c["footR.rx"] += -14 * tw
    eyes(c, rig, 1.0)
    return c


def kneel_heels(rig, f, N):
    """Kneeling sitting back on his heels (legs by FK: thighs forward, shins folded under), hands on the thighs; the
    long robe reads better kneeling than sitting with the knees up."""
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"thigh{side}.rx"] = -84; c[f"thigh{side}.rz"] = 4 * sx
        c[f"shin{side}.rx"] = 150; c[f"foot{side}.rx"] = 58
        arm_ik(c, side, V(0.040 * sx, 0.075, 0.075), V(0.8 * sx, -0.4, -0.4), "root")
        c[f"hand{side}.bend"] = 10; fingers(c, side, 30)
    c["hips.ty"] = -0.110; c["hips.tz"] = -0.030
    c["spine.rx"] = 4; c["chest.rx"] += 2
    c["coatfollow"] = 0.6
    c["settle"] = ("hips", ("shinL", "shinR", "footL", "footR", "thighL", "thighR"), 0.0010, 1.0)
    return c


@clip("jesus", "wake_up", 96, False, seated=True, markers={"eyes": 10, "kneel": 40, "stand": 82},
      notes="from lie_sleep: opens his eyes calmly, pushes up on the lower arm and comes up onto his knees (sitting "
            "back on his heels), looks at Peter (toward his -X), then rises to standing at the root, no hurry, no "
            "fright; ends standing, calm, hands low")
def jesus_wake_up(rig, f, N):
    lie = jesus_lie_sleep(rig, 0, SLEEP_N)
    kn = kneel_heels(rig, f, N)
    kn["neck.ry"] = 14 * ease_io((f - 34) / 10); kn["head.ry"] = 18 * ease_io((f - 36) / 10)
    st = stand_pose(rig, f, N, amp=0.5, spread=0.005)
    w1 = ease_io((f - 12) / 28)
    w2 = ease_io((f - 50) / 32)
    c = mix(mix(lie, kn, w1), st, w2)
    sw = (1 - w1) * (1 - w2)
    c["settle"] = ("hips", None, 0.0010, sw + w1 * (1 - w2))
    if f < 12:
        eyes(c, rig, 1.0 - ease_io((f - 4) / 6))
    else:
        c["eyelids.sy"] = 1.0
        blink_ch(c, rig, f, N, [34, 70], loop=False)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 12 * bump(f, 50, 80)
    c["chest.rx"] = c.get("chest.rx", 0.0) + 6 * bump(f, 50, 80)
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.012 * bump(f, 50, 80)
    c["floorclamp"] = True
    return c


@clip("jesus", "calm_storm", 72, False, markers={"calm": 30},
      notes="stands firm (feet apart), lifts both arms out over the water, palms down, held strong at `calm` (1.0 s), "
            "then lowers them slowly, palms still down, as if smoothing the sea; ends standing, arms low, calm")
def jesus_calm_storm(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    up = ease_io((f - 4) / 18)
    down = ease_io((f - 36) / 30)
    for side, sx in (("L", 1), ("R", -1)):
        hi = V(0.082 * sx, 0.262, 0.120) * kH(rig)
        lo = V(0.070 * sx, 0.150, 0.070) * kH(rig)
        arm_ik(c, side, vlerp(hi, lo, down), V(0.9 * sx, -0.5, -0.2), "root", up * (1 - 0.6 * ease_io((f - 60) / 12)))
        c[f"forearm{side}.twist"] = lerp(-10 * sx, 30 * sx, up)
        c[f"hand{side}.bend"] = lerp(6, 12, up) + 10 * down; fingers(c, side, lerp(22, 4, up))
    c["chest.rx"] += -3 * up * (1 - down); c["head.rx"] = -3 * up * (1 - down) + 2 * down
    c["jaw.rx"] = 8 * bump(f, 24, 36)
    stand_feet(rig, c, spread=0.010, fwdR=0.010)
    blink_ch(c, rig, f, N, [50], loop=False)
    return c


@clip("jesus", "laugh", 54, False, markers={"laugh": 12},
      notes="a warm laugh: head tips back a little, shoulders shake in four shrinking bursts, the left hand to his "
            "chest; ends in the plain standing pose")
def jesus_laugh(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    lg = pulses(f, N, [(10, 1.0), (16, 0.9), (22, 0.7), (29, 0.5)], decay=2.2, loop=False)
    env = bump(f, 4, 46)
    c["head.rx"] = -2 - 8 * env + 3 * lg; c["neck.rx"] = -4 * env
    c["shoulderL.raise"] += 4 * lg; c["shoulderR.raise"] += 4 * lg; c["chest.rx"] += -3 * env + 2 * lg
    c["jaw.rx"] = 9 * env * (0.5 + 0.5 * lg)
    arm_ik(c, "L", V(0.016, -0.010, 0.046) * kH(rig), V(0.8, -0.6, -0.2), "chest", env)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [40], loop=False, base=1.0 + 2.0 * env)
    return c


@clip("jesus", "wave", 60, True,
      notes="friendly wave with the right hand beside his head, a little side sway, head tilted, the left hand low")
def jesus_wave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    hand_wave(c, rig, "R", f, N, 3, high=0.8)
    sh = wave(f, N, 1, 0.0)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh; c["chest.rz"] = 1.0 * sh
    c["head.rz"] = -6 + 2 * sh
    stand_feet(rig, c, spread=0.003)
    blink_ch(c, rig, f, N, [22])
    return c


# =============================================================================================== PETER
OAR_R = V(-0.090, 0.180, -0.010)     # the imagined steering-oar handle at his right side (root space, 0.38-tall)


@clip("peter", "idle", 180, True,
      notes="a big man at ease: weight shifts from foot to foot (hips lead, chest late), fists on his hips for the "
            "middle of the loop, then arms hang; looks round, a hum (small jaw); blinks")
def peter_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=1.0)
    hips = K([(0, 0), (30, 0), (46, 1), (120, 1), (136, 0), (180, 0)], f, N, True)
    hand_on_hip(c, rig, "L", hips); hand_on_hip(c, rig, "R", hips)
    sh = K([(0, -0.6), (40, -0.6), (70, 0.9), (120, 0.9), (150, -0.6), (180, -0.6)], f, N, True)
    shl = KL([(0, -0.6), (40, -0.6), (70, 0.9), (120, 0.9), (150, -0.6), (180, -0.6)], f, N, True, lag=8)
    c["hips.tx"] = 0.005 * sh; c["hips.rz"] = -2.6 * sh; c["spine.rz"] = 1.5 * shl; c["chest.rz"] = 1.0 * shl
    c["head.rz"] = -1.2 * shl
    look_keys(c, [(0, 0), (24, 0), (40, 20), (80, 20), (96, -16), (140, -16), (156, 0), (180, 0)], f, N)
    c["jaw.rx"] = 3 * bump(f, 100, 112) + 3 * bump(f, 116, 128)
    stand_feet(rig, c, spread=0.010)
    blink_ch(c, rig, f, N, [16, 70, 77, 150])
    return c


@clip("peter", "talk", 96, True,
      notes="big open gestures: both arms swing wide palms-up on the stressed words (left phrase, right phrase, both), "
            "chest out, a belly chuckle (shoulders bounce), nods; jaw in a syllable rhythm")
def peter_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    beats = talk_jaw(c, f, N, 77, amp=(6, 15))
    bt = beat_curve(beats, f, N, width=10); btl = beat_curve(beats, f - 3, N, width=12)
    c["head.rx"] = -3 + 4 * bt; c["head.ry"] = 6 * wave(f, N, 1, 0.15); c["head.rz"] = 3 * wave(f, N, 1, 0.4)
    pl = K([(0, 0.3), (10, 1.0), (34, 1.0), (46, 0.2), (62, 0.8), (84, 1.0), (96, 0.3)], f, N, True)
    pr = K([(0, 0.2), (24, 0.2), (36, 1.0), (60, 0.9), (70, 0.6), (84, 1.0), (96, 0.2)], f, N, True)
    for side, w_ in (("L", pl), ("R", pr)):
        sx = 1 if side == "L" else -1
        o = w_ * (0.75 + 0.25 * btl)
        c[f"upperArm{side}.raise"] = -12 + 46 * o; c[f"upperArm{side}.bend"] = 8 + 24 * o
        c[f"forearm{side}.bend"] = 26 + 34 * o; c[f"forearm{side}.twist"] = -10 * sx + (-70 * sx) * o
        c[f"hand{side}.bend"] = 6 - 26 * o; fingers(c, side, 24 - 18 * o)
    ch = pulses(f, N, [(50, 1.0), (55, 0.7), (60, 0.5)], decay=2.0)
    c["shoulderL.raise"] += 3 * ch; c["shoulderR.raise"] += 3 * ch; c["chest.rx"] += -3 + 1.5 * ch
    sh = wave(f, N, 1, 0.1)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2 * sh; c["chest.ry"] = 4 * (pl - pr)
    stand_feet(rig, c, spread=0.010)
    blink_ch(c, rig, f, N, [20, 74])
    return c


P_WALK = (0.080, 0.60)


@clip("peter", "walk", 36, True, markers={"contactL": 0, "contactR": 18}, speed=P_WALK,
      notes="rolling fisherman's walk: feet apart, the body rolls over each planted foot (hips and chest roll, head "
            "level), arms out from the body swinging wide, a bounce per step")
def peter_walk(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=P_WALK[0], lift=0.014, duty=P_WALK[1], heel=10, toeoff=20, spread=0.010)
    legs_ik_channels(c, g)
    for side in "LR":
        c[f"pole.leg{side}"] = V(0.35 if side == "L" else -0.35, 0, 1)
    ph = 2 * math.pi * f / N
    c["hips.tx"] = 0.009 * math.cos(ph); c["hips.ty"] = -0.006 + 0.004 * math.cos(2 * ph - 0.5)
    c["hips.rz"] = 6 * math.cos(ph); c["spine.rz"] = -2.5 * math.cos(ph - 0.3); c["chest.rz"] = -2.5 * math.cos(ph - 0.5)
    c["head.rz"] = -1.0 * math.cos(ph - 0.8)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.35)
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -2 + 4 * math.cos(ph + (0 if side == "L" else math.pi))
        c[f"upperArm{side}.bend"] = 10 + sg * 20 * math.sin(ph - 0.25)
        c[f"forearm{side}.bend"] = 34 + sg * 10 * math.sin(ph - 1.0)
        fingers(c, side, 40)
    blink_ch(c, rig, f, N, [24])
    return c


@clip("peter", "roof_shock", 50, False, markers={"hit": 4, "hands": 22},
      notes="dust hits him: a big flinch (ducks, shoulders up, eyes squeezed), then he looks straight up, both hands "
            "slap onto the top of his head (elbows wide, face clear), mouth wide open; holds")
def peter_roof_shock(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    fl = pulses(f, N, [(4, 1.0)], decay=1.4, loop=False) * (1 - ease_io((f - 14) / 8))
    c["shoulderL.raise"] += 10 * fl; c["shoulderR.raise"] += 10 * fl
    c["spine.rx"] = 8 * fl; c["chest.rx"] += 8 * fl; c["neck.rx"] = 10 * fl; c["hips.ty"] = -0.012 * fl
    up = ease_io((f - 12) / 10)
    c["neck.rx"] += -16 * up; c["head.rx"] = -4 - 16 * up; c["chest.rx"] += -4 * up
    hands = ease_io((f - 14) / 8)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.116 * sx, 0.150, 0.040), V(1.0 * sx, -0.4, -0.3), "root", ease_io(f / 8))
        arm_ik2(c, side, V(0.034 * sx, 0.050, 0.004), V(1.0 * sx, 0.3, -0.3), "head", hands)
        c[f"hand{side}.bend"] = 24 * hands; fingers(c, side, lerp(22, 30, hands))
    slap = pulses(f, N, [(22, 1.0)], decay=2.0, loop=False)
    c["head.rx"] += 3 * slap
    c["jaw.rx"] = 16 * ease_io((f - 16) / 6)
    stand_feet(rig, c, spread=0.010, fwdL=-0.008 * ease_io(f / 6))
    c["eyelids.sy"] = 1.0 + 9.0 * fl
    return c


@clip("peter", "dust_off", 78, False, markers={"shake": 46},
      notes="brushes the dust out of his hair (both hands scrubbing the top of his head), then out of his beard (one "
            "hand under the chin), then shakes his head like a wet dog (fast head shakes with the shoulders "
            "following); squints; ends standing, blinking, hands low")
def peter_dust_off(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    hair = ease_io(f / 10) * (1 - ease_io((f - 22) / 8))
    beard = ease_io((f - 22) / 8) * (1 - ease_io((f - 40) / 10))
    scrub = math.sin(2 * math.pi * f / 5)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V((0.030 + 0.008 * scrub * sx) * sx, 0.054, -0.004 + 0.008 * scrub), V(1.0 * sx, 0.3, -0.3),
               "head", max(hair, beard) if side == "R" else hair)
        fingers(c, side, 30 + 20 * scrub)
    arm_ik2(c, "R", V(-0.006 + 0.008 * scrub, -0.032, 0.046), V(-0.9, -0.5, 0.2), "head",
            beard / max(1e-4, hair + beard))
    c["head.rx"] = 8 * hair - 10 * beard
    sh = math.sin(2 * math.pi * (f - 44) / 6) * bump(f, 44, 66)
    shl = math.sin(2 * math.pi * (f - 45.5) / 6) * bump(f, 44, 66)
    c["head.ry"] = 30 * sh; c["neck.ry"] = 10 * shl; c["chest.ry"] = 5 * shl; c["head.rz"] = 6 * sh
    c["shoulderL.raise"] += 4 * bump(f, 44, 66); c["shoulderR.raise"] += 4 * bump(f, 44, 66)
    c["jaw.rx"] = 4 * bump(f, 48, 62)
    stand_feet(rig, c, spread=0.010)
    c["eyelids.sy"] = 1.0 + 5.0 * bump(f, 0, 70)
    if f > 66:
        blink_ch(c, rig, f, N, [70], loop=False)
    return c


@clip("peter", "laugh", 48, True, markers={"slap1": 12, "slap2": 36},
      notes="a big belly laugh: head back, shoulders and belly bouncing, the right hand slaps his thigh twice per loop "
            "(knee comes up a little to meet it), the left hand on his belly; mouth wide")
def peter_laugh(rig, f, N):
    c = h_base(rig, f, N, cycles=4, amp=1.4)
    lg = pulses(f, N, [(0, 0.8), (6, 1.0), (12, 0.8), (18, 0.9), (24, 0.8), (30, 1.0), (36, 0.8), (42, 0.9)], decay=2.6)
    c["head.rx"] = -10 + 3 * lg; c["neck.rx"] = -6; c["chest.rx"] += -6 + 2 * lg; c["spine.rx"] = -3
    c["shoulderL.raise"] += 4 * lg; c["shoulderR.raise"] += 4 * lg
    c["jaw.rx"] = 11 + 5 * lg
    slap = K([(0, 0.2), (8, 1.0), (12, 0.0), (20, 0.2), (32, 1.0), (36, 0.0), (44, 0.2), (48, 0.2)], f, N, True)
    arm_ik(c, "R", V(-0.036, 0.120 + 0.050 * slap, 0.040 + 0.020 * slap), V(-0.9, -0.3, -0.4))
    c["handR.bend"] = -10; fingers(c, "R", 10)
    arm_ik(c, "L", V(0.020, -0.050, 0.064), V(0.9, -0.5, 0.0), "chest")
    c["handL.bend"] = 10
    hit = pulses(f, N, [(12, 1.0), (36, 1.0)], decay=2.0)
    c["chest.rx"] += 6 * hit; c["head.rx"] += 6 * hit
    stand_feet(rig, c, spread=0.010, liftR=0.010 * hit, fwdR=0.006 * hit)
    c["eyelids.sy"] = 5.0
    return c


@clip("peter", "steer", 120, True,
      notes="calm: the right hand on the steering-oar handle at his right side (imagined handle; ANIMATION.md), the "
            "left fist on his hip, legs apart; sways with the boat, looks out over the water and back, hums")
def peter_steer(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    rock = wave(f, N, 1, 0.0); rockl = wave(f, N, 1, -0.06)
    c["hips.tx"] = 0.004 * rock; c["hips.rz"] = -2.2 * rock; c["spine.rz"] = 1.4 * rockl; c["chest.rz"] = 1.0 * rockl
    arm_ik(c, "R", OAR_R + V(0.0, 0.003 * rock, 0.004 * wave(f, N, 2)), V(-0.8, -0.4, -0.5))
    c["handR.bend"] = 10; fingers(c, "R", 72)
    hand_on_hip(c, rig, "L")
    look_keys(c, [(0, 0), (20, 0), (34, 22), (60, 22), (74, -10), (100, -10), (110, 0), (120, 0)], f, N)
    c["jaw.rx"] = 3 * bump(f, 80, 90) + 3 * bump(f, 94, 104)
    stand_feet(rig, c, spread=0.012, fwdL=0.006, fwdR=-0.004)
    blink_ch(c, rig, f, N, [14, 66, 73])
    return c


@clip("peter", "steer_hard", 72, True, markers={"heaveL": 14, "heaveR": 50},
      notes="in the storm: both hands on the oar handle at his right, heaving it hard left and right (the whole body "
            "throws its weight into it, chest turning, hips pushing), legs braced wide and bent, head ducked into the "
            "wind, teeth gritted, squinting")
def peter_steer_hard(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.4)
    keys = [(0, -1), (14, 1), (22, 0.8), (36, 1), (50, -1), (58, -0.8), (72, -1)]
    hv = K(keys, f, N, True); hvl = KL(keys, f, N, True, lag=3)
    jerk = pulses(f, N, [(12, 1.0), (48, 1.0)], decay=2.5)
    arm_ik(c, "R", OAR_R + V(0.004, -0.010, 0.024 * hv), V(-0.8, -0.5, -0.5))
    arm_ik(c, "L", OAR_R + V(0.036, 0.004, 0.030 + 0.024 * hv), V(0.7, -0.6, -0.4))
    c["handR.bend"] = 10; c["handL.bend"] = 14; fingers(c, "R", 82); fingers(c, "L", 82)
    c["chest.ry"] = -14 - 9 * hvl; c["spine.ry"] = -6 - 4 * hvl; c["hips.ry"] = -4 * hv
    c["spine.rx"] = 10 + 3 * jerk; c["chest.rx"] += 6 + 2 * jerk
    c["hips.ty"] = -0.018 - 0.004 * jerk; c["hips.tx"] = -0.007 * hv; c["hips.tz"] = -0.006
    c["hips.rz"] = 3 * hv
    c["neck.rx"] = -6; c["head.rx"] = 4; c["head.ry"] = 10 * hvl
    c["jaw.rx"] = 2 + 3 * jerk
    c["eyelids.sy"] = 3.6 + 2 * jerk
    stand_feet(rig, c, spread=0.018, fwdL=0.022, fwdR=-0.014, pitchR=6)
    return c


@clip("peter", "bail", 36, True, props=["bucket"], markers={"scoop": 9, "throw": 24},
      notes="frantic bailing with the bucket in his right hand: bends deep (knees and hips), scoops low in front-right "
            "(`scoop`), heaves it up across his body and flings the water out over the side to his LEFT (`throw`, "
            "left hand under the bucket), straight back down; eyes wide, mouth open")
def peter_bail(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    down = K([(0, 0.7), (9, 1.0), (14, 0.7), (22, 0.0), (26, 0.0), (32, 0.6), (36, 0.7)], f, N, True)
    thr = K([(0, 0.0), (12, 0.0), (20, 0.7), (24, 1.0), (28, 0.8), (34, 0.1), (36, 0.0)], f, N, True)
    c["hips.ty"] = -0.050 * down - 0.006 * thr; c["hips.tz"] = -0.030 * down; c["hips.rx"] = 26 * down
    c["spine.rx"] = 22 * down - 4 * thr; c["chest.rx"] += 12 * down; c["neck.rx"] = -14 * down; c["head.rx"] = -10 * down
    c["chest.ry"] = 6 * down - 28 * thr; c["spine.ry"] = -10 * thr; c["hips.ry"] = -6 * thr
    c["chest.rz"] = -6 * thr
    low = V(-0.040, 0.050, 0.110)
    high = V(0.120, 0.250, 0.060)
    tgt = vlerp(vlerp(V(-0.030, 0.110, 0.080), low, down), high, thr)
    arm_ik(c, "R", tgt, V(-0.8, -0.3, -0.4))
    c["handR.bend"] = -20 * thr + 10 * down; c["handR.twist"] = -60 * bump(f, 20, 30); fingers(c, "R", 80)
    arm_ik(c, "L", V(-0.010, -0.040, 0.010), V(0.8, -0.6, 0.0), "handR", thr)
    arm_ik2(c, "L", V(0.050, 0.090, 0.110), V(0.8, -0.4, -0.3), "root", 1 - thr)
    fingers(c, "L", 40)
    c["jaw.rx"] = 8 + 6 * thr
    stand_feet(rig, c, spread=0.018, fwdL=0.010, fwdR=-0.006)
    c["eyelids.sy"] = 1.0
    return c


_PARTNER = {}


def partner_pose(action, f):
    """Bone heads / tails of another clip's primary pose at frame f (root space of that actor)."""
    key = (action, int(f))
    if key not in _PARTNER:
        cl = next(c for c in CLIPS if c.action == action)
        rig = RIGS[cl.ch]
        _, _, M = evaluate_primary(rig, cl, max(0, min(cl.N, int(f))))
        _PARTNER[key] = {n: (rig.pos(M, n), rig.pos(M, n, "tail")) for n in rig.names}
    return _PARTNER[key]


def wake_target():
    """The sleeper's upper (right) shoulder in jesus_lie_sleep, in Peter's root space: the sleeper's root WAKE_D in
    front of Peter, facing Peter (yaw 180 to Peter), lying across Peter's view (head to Peter's right)."""
    p = partner_pose("jesus_lie_sleep", 0)
    q = p["upperArmR"][0] * 0.7 + p["chest"][0] * 0.3
    return V(-q.x, q.y, WAKE_D - q.z)


@clip("peter", "shake_awake", 48, True, markers={"shake1": 8, "shake2": 32},
      notes="bends right over the sleeper lying in front of him (lie_sleep root WAKE_D = 0.10 in front, facing him, "
            "head to Peter's right): knees bent, both hands on the sleeper's upper shoulder, shaking him in two "
            "panicky bursts per loop, wailing (jaw wide on the bursts), eyes wide, head-cloth tail flicking")
def peter_shake_awake(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    t = wake_target()
    burst = K([(0, 0.4), (6, 1.0), (16, 1.0), (22, 0.3), (30, 1.0), (40, 1.0), (46, 0.4), (48, 0.4)], f, N, True)
    sh = math.sin(2 * math.pi * 6 * f / N) * burst
    c["hips.tz"] = -0.034; c["hips.ty"] = -0.050
    c["hips.rx"] = 26; c["spine.rx"] = 24 + 2 * burst; c["chest.rx"] += 18; c["neck.rx"] = -18; c["head.rx"] = -12
    arm_ik(c, "R", t + V(-0.018 + 0.008 * sh, 0.010, -0.012 + 0.004 * sh), V(-0.8, 0.2, -0.6))
    arm_ik(c, "L", t + V(0.020 + 0.008 * sh, 0.010, -0.006 + 0.004 * sh), V(0.8, 0.2, -0.6))
    c["handR.bend"] = 30; c["handL.bend"] = 30; fingers(c, "R", 55); fingers(c, "L", 55)
    c["chest.rz"] = 2.5 * sh; c["head.rz"] = -2 * sh
    c["jaw.rx"] = 8 + 10 * beat_curve([7, 13, 31, 37], f, N, width=6)
    c["eyelids.sy"] = 1.0
    stand_feet(rig, c, spread=0.016, fwdL=0.010, fwdR=-0.024)
    return c


@clip("peter", "amazed", 66, False, markers={"look": 30},
      notes="slowly straightens up (from a crouch), mouth falls open, hands half raised and open, looks slowly round "
            "at the flat water (left ... right), a little shake of the head in disbelief; holds")
def peter_amazed(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    rise = ease_io(f / 24)
    c["hips.ty"] = -0.030 * (1 - rise); c["spine.rx"] = 14 * (1 - rise); c["chest.rx"] += 8 * (1 - rise)
    o = ease_io((f - 10) / 16)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.084 * sx, 0.186, 0.074), V(0.9 * sx, -0.6, -0.2), "root", o)
        c[f"forearm{side}.twist"] = -60 * sx * o; c[f"hand{side}.bend"] = -10 * o; fingers(c, side, lerp(22, 8, o))
    look = K([(0, 0), (24, 0), (38, 24), (50, -22), (62, -10), (66, -10)], f)
    c["head.ry"] = 0.7 * look; c["neck.ry"] = 0.3 * look; c["chest.ry"] = 0.12 * look
    c["head.ry"] += 8 * math.sin(2 * math.pi * (f - 54) / 8) * bump(f, 54, 66)
    c["jaw.rx"] = 13 * ease_io((f - 6) / 12)
    c["head.rx"] = -3 * o
    stand_feet(rig, c, spread=0.010)
    c["eyelids.sy"] = 1.0
    blink_ch(c, rig, f, N, [44], loop=False)
    return c


@clip("peter", "cower", 60, True, markers={"thunder": 20},
      notes="crouched low, hugging his knees (head ducked between his shoulders), rocking a little; a thunder flinch "
            "per loop (`thunder`: shoulders jump, eyes squeezed shut); scared face")
def peter_cower(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    kneel_legs(rig, c, 0.0, 0.0)                        # feet stay planted; a deep squat below
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        c[f"ik.leg{side}"] = V(b.x + sx * 0.012, planted_ankle_y(rig, side, 0), b.z + 0.020)
        c[f"foot{side}.pitch"] = 0.0; c[f"pole.leg{side}"] = V(0.4 * sx, 0.3, 1)
    rock = wave(f, N, 1)
    fl = pulses(f, N, [(20, 1.0)], decay=2.0)
    c["hips.ty"] = -0.118 + 0.002 * rock - 0.004 * fl; c["hips.tz"] = -0.050
    c["hips.rx"] = 34; c["spine.rx"] = 22 + 3 * rock + 4 * fl; c["chest.rx"] += 16
    c["neck.rx"] = 6; c["head.rx"] = 10 + 6 * fl
    c["shoulderL.raise"] += 8 + 6 * fl; c["shoulderR.raise"] += 8 + 6 * fl
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(-0.010 * sx, 0.110, 0.104), V(0.9 * sx, -0.2, 0.2), "root")
        c[f"hand{side}.bend"] = 20; fingers(c, side, 60)
    c["head.ry"] = 4 * wave(f, N, 1, 0.3)
    c["eyelids.sy"] = 1.0 + 11.0 * bump(f, 18, 30)
    c["floorclamp"] = True
    return c


@clip("peter", "wave", 48, True,
      notes="a big two-arm wave over his head, rocking side to side, beaming")
def peter_wave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.6)
    for side, sx in (("L", 1), ("R", -1)):
        wg = wave(f, N, 2, 0.0 if side == "L" else 0.5)
        arm_ik(c, side, V((0.090 + 0.030 * wg) * sx, 0.390, 0.020), V(0.8 * sx, -0.6, 0.2))
        c[f"hand{side}.bend"] = 20; c[f"forearm{side}.twist"] = -60 * sx; fingers(c, side, 6)
    sh = wave(f, N, 2, 0.0)
    c["hips.tx"] = 0.005 * sh; c["hips.rz"] = -2.4 * sh; c["chest.rz"] = 2.0 * sh; c["head.rz"] = -3 * sh
    c["jaw.rx"] = 6
    stand_feet(rig, c, spread=0.010, pitchL=6 * max(0.0, sh), pitchR=6 * max(0.0, -sh))
    blink_ch(c, rig, f, N, [30])
    return c


# =============================================================================================== MAN
ROPES_OFF = 0.001
LIE_TOP = 0.026          # lowest body point lying on the mat (pad top 0.025, RIG.md §3)


def mclip(name, N, loop, **kw):
    """Man clips: the ropes stay scaled to ROPES_OFF unless the clip sets them (only `lowered` does)."""
    def deco(fn):
        def wrapped(rig, f, N_):
            c = fn(rig, f, N_)
            if "ropes.sy" not in c:
                c["ropes.sx"] = c["ropes.sy"] = c["ropes.sz"] = ROPES_OFF
            return c
        CLIPS.append(Clip("man", name, N, loop, wrapped, **kw))
        return fn
    return deco


def lie_pose(rig, c, yaw=90.0, centre=(0.0, -0.020), breathe=0.0, look=0.0, nervous=0.0, w=1.0):
    """On his back on the mat, face up. yaw 90: head toward -X (lie_mat, the mat at rest); yaw 0: head toward -Z
    (carried). The hips sit 0.012 toward the feet from the pad centre; settle puts the lowest body point at LIE_TOP."""
    c["hips.yaw"] = c.get("hips.yaw", 0.0) + yaw * w
    c["hips.rx"] = c.get("hips.rx", 0.0) - 90 * w
    hp = rot_y(V(0.0, 0.0, 0.012), yaw) + V(centre[0], 0, centre[1])
    c["hips.tx"] = c.get("hips.tx", 0.0) + hp.x * w
    c["hips.ty"] = c.get("hips.ty", 0.0) + (0.046 - rig.head["hips"].y) * w
    c["hips.tz"] = c.get("hips.tz", 0.0) + hp.z * w
    c["spine.rx"] = c.get("spine.rx", 0.0) + (2 - 1.5 * breathe) * w
    c["chest.rx"] = c.get("chest.rx", 0.0) + (2 - 2.5 * breathe) * w
    c["neck.rx"] = c.get("neck.rx", 0.0) + (14 + 6 * nervous) * w
    c["head.rx"] = c.get("head.rx", 0.0) + 6 * w
    c["neck.ry"] = c.get("neck.ry", 0.0) + 0.4 * look * w; c["head.ry"] = c.get("head.ry", 0.0) + 0.6 * look * w
    for side, sx in (("L", 1), ("R", -1)):
        for k in ("ik.leg", "ikw.leg"):
            c.pop(k + side, None)
        c[f"thigh{side}.rx"] = c.get(f"thigh{side}.rx", 0.0) - 6 * w
        c[f"shin{side}.rx"] = c.get(f"shin{side}.rx", 0.0) + 10 * w
        c[f"foot{side}.rx"] = c.get(f"foot{side}.rx", 0.0) + 24 * w
        c[f"thigh{side}.rz"] = c.get(f"thigh{side}.rz", 0.0) + 2 * sx * w
        pole = rot_y(V(1.0 * sx, -0.6, -0.2), yaw)
        arm_ik(c, side, V((0.014 + 0.010 * nervous) * sx, -0.046 + 0.006 * sx, 0.050), pole, "chest", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 10, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 30 + 30 * nervous, w))
    c["sash1.rx"] = c.get("sash1.rx", 0.0) + 12 * w
    c["coatfollow"] = max(c.get("coatfollow", 0.0), w)
    c["settle"] = ("hips", None, LIE_TOP, w)


@mclip("lie_mat", 120, True, seated=True, props=["mat"],
       notes="on his back on the flat mat (mat bone at rest), head toward -X and a little raised, hands folded on his "
             "chest; slow breathing, irregular blinks, the toes wiggle once, he glances to his right and back")
def man_lie_mat(rig, f, N):
    c = {}
    br = K([(0, 0), (30, 1), (60, 0), (90, 1), (120, 0)], f, N, True)
    look = K([(0, 0), (64, 0), (72, 20), (92, 20), (100, 0), (120, 0)], f, N, True)
    lie_pose(rig, c, 90.0, breathe=br, look=look)
    tw = bump(f, 36, 48)
    c["footL.rx"] += -10 * tw * math.sin(2 * math.pi * (f - 36) / 6); c["footR.rx"] += -8 * tw
    blink_ch(c, rig, f, N, [10, 52, 59, 104])
    return c


def carry_bob(f):
    """The carry group's shared up-down (one dip per step, 0.8 s; lowest 4 frames after each contact)."""
    return -0.004 * (0.5 + 0.5 * math.cos(2 * math.pi * 2 * (f - 4) / CARRY_N))


POLE_C = 0.009           # pole centre height above the man's root in the rest mat (measured from man_mat: y 0.0018..0.0162)


@mclip("carried", CARRY_N, True, seated=True, props=["mat"], markers={"stepL": 0, "stepR": 24},
       root_motion="static lift: root raised CARRY_HAND - CARRY_Y - POLE_C (pole centres at world 0.15 on base "
                   "CARRY_Y 0.10) plus a 0.004 bob per step; mat turned 90 deg so its poles run along the travel",
       notes="lying on the mat as in lie_mat, but body and mat lifted as one and turned so the poles run along his "
             "facing (head toward -Z, feet first); one small dip per carrier step (0.8 s), he clutches the mat "
             "nervously and turns his head to look round (left, ahead, right). Carriers: friend1 carry_front "
             "CARRY_D ahead, friend2 carry_back CARRY_D behind, started on the same frame")
def man_carried(rig, f, N):
    c = {}
    look = K([(0, -26), (10, -26), (20, 0), (30, 26), (40, 26), (48, -26)], f, N, True)
    lie_pose(rig, c, 0.0, centre=(0.0, 0.0), breathe=0.5 + 0.5 * wave(f, N, 2), look=look, nervous=1.0)
    c["root.ty"] = CARRY_HAND - CARRY_Y - POLE_C + carry_bob(f)
    c["mat.ry"] = 90.0
    c["mat.tz"] = 0.020                     # the pad centre (rest z -0.02) to the group's centre line
    c["root.rz"] = 0.8 * wave(f, N, 2, 0.1)  # a little roll with the steps
    c["head.rx"] += 2 * wave(f, N, 2, 0.3)
    blink_ch(c, rig, f, N, [8, 33])
    return c


LOWER_N = 150
LOWER_LAND = 138
LOWER_HIDE = 144


def lower_y(f):
    """Root height: 0.40 at the start, down in jerky stages (pay-out, catch, pay-out), 0 at LOWER_LAND."""
    keys = [(0, 0.40), (10, 0.40), (30, 0.335), (40, 0.330), (62, 0.240), (72, 0.236), (94, 0.140), (104, 0.135),
            (124, 0.040), (130, 0.034), (LOWER_LAND, 0.0)]
    if f >= LOWER_LAND:
        return -0.003 * bump(f, LOWER_LAND, LOWER_LAND + 6)
    for (f0, y0), (f1, y1) in zip(keys, keys[1:]):
        if f0 <= f <= f1:
            return lerp(y0, y1, ease_io((f - f0) / (f1 - f0)))
    return 0.0


@mclip("lowered", LOWER_N, False, seated=True, props=["mat", "ropes"], markers={"land": LOWER_HIDE},
       root_motion="root starts at local y +0.40 (the roof) and comes down in four eased stages to 0 at frame 138 "
                   "(4.6 s), a 3 mm bump on landing; play at base y 0 on LAND",
       notes="5 s. Lying on the mat (lie_mat pose) as he is let down through the roof: four ropes from the mat corners "
             "rise to the friends' hands (their tops held at local y ROPE_TOP = 0.47; the ropes shorten as he goes "
             "down), the mat swings +-4 deg and jolts at each catch; he clutches the mat edges, looks up at the "
             "friends, then down at the floor; lands with a little bump at 4.6 s, ropes slack and shrink away by "
             "`land` (4.8 s); ends in lie_mat's pose, blinking")
def man_lowered(rig, f, N):
    c = {}
    y = lower_y(f)
    look_up = 1.0 - ease_io((f - 70) / 30)
    lie_pose(rig, c, 90.0, nervous=1.0 - ease_io((f - 130) / 16))
    c["neck.rx"] += -10 * look_up + 6 * (1 - look_up)
    c["neck.ry"] += 18 * K([(0, 0), (40, 0), (60, 1), (90, -1), (120, 0), (150, 0)], f)
    catch = pulses(f, N, [(30, 1.0), (62, 0.9), (94, 0.9), (124, 0.7), (LOWER_LAND, 1.2)], decay=3.0, loop=False)
    sway = 4.0 * math.sin(2 * math.pi * f / 50) * (1 - ease_io((f - 110) / 28))
    c["root.ty"] = y
    c["root.rz"] = sway + 1.5 * catch * (1 - ease_io((f - 130) / 8))
    c["root.rx"] = 1.5 * math.sin(2 * math.pi * f / 37 + 0.6) * (1 - ease_io((f - 110) / 28))
    c["chest.rx"] = c.get("chest.rx", 0.0) + 2 * catch
    for side in "LR":
        fingers(c, side, 70)
    L = max(0.02, ROPE_TOP - y - 0.025)
    show = ease_io(f / 3) * (1 - ease_io((f - (LOWER_HIDE - 5)) / 5))
    slack = ease_io((f - LOWER_LAND) / 6)
    sc = max(ROPES_OFF, show)
    c["ropes.sx"] = c["ropes.sz"] = sc
    c["ropes.sy"] = max(ROPES_OFF, (L / 0.45) * (1 + 0.04 * slack) * (1.0 if show > 0.5 else show * 2))
    if f > LOWER_LAND:
        c["ropes.rx"] = 6 * slack                      # slack ropes lean
    blink_ch(c, rig, f, N, [20, 80, LOWER_LAND + 4], loop=False)
    return c


def sit_pose_mat(rig, f, N, w=1.0):
    """Sitting up on the mat facing his feet (+X): hips upright (yaw 90), legs out along +X, hands on the mat beside
    the hips (root space turned by the yaw)."""
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    c["hips.yaw"] = 90.0
    hp = rot_y(V(0, 0, 0.012), 90.0) + V(0, 0, -0.020)
    c["hips.tx"] = hp.x; c["hips.tz"] = hp.z
    c["hips.ty"] = -(rig.head["hips"].y - 0.046)
    for side in "LR":
        for k in ("ik.leg", "ikw.leg"):
            c.pop(k + side, None)
        c[f"thigh{side}.rx"] = -84; c[f"shin{side}.rx"] = 12; c[f"foot{side}.rx"] = 18
    for side, sx in (("L", 1), ("R", -1)):
        p = rot_y(V(0.060 * sx, LIE_TOP + 0.010, -0.010), 90.0) + V(0, 0, -0.020)
        arm_ik(c, side, p, rot_y(V(0.6 * sx, 0.2, -1.0), 90.0), "root", 1.0)
        c[f"hand{side}.bend"] = -50; fingers(c, side, 10)
    c["spine.rx"] = 8; c["chest.rx"] += 6; c["neck.rx"] = 10; c["head.rx"] = 14
    c["coatfollow"] = 1.0
    c["settle"] = ("hips", ("hips", "thighL", "thighR", "shinL", "shinR", "spine"), LIE_TOP, w)
    return c


@mclip("sit_up", 84, False, seated=True, props=["mat"], markers={"up": 40, "toes": 56},
       notes="from lie_mat: a breath, he pushes up slowly on his hands and sits up facing his feet (+X), stares at his "
             "legs in wonder, wiggles his toes (twice), then turns his head toward his +Z (Jesus) with a hopeful look; "
             "holds sitting")
def man_sit_up(rig, f, N):
    a = man_lie_mat(rig, 0, 120)
    b = sit_pose_mat(rig, f, N)
    w = ease_io((f - 8) / 32)
    c = mix(a, b, w)
    c["settle"] = ("hips", ("hips", "thighL", "thighR", "shinL", "shinR", "spine"), LIE_TOP, 1.0)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 8 * bump(f, 10, 44)
    wig = math.sin(2 * math.pi * (f - 50) / 7) * bump(f, 48, 72)
    c["footL.rx"] = c.get("footL.rx", 0.0) - 18 * wig; c["footR.rx"] = c.get("footR.rx", 0.0) + 18 * wig
    turn = ease_io((f - 66) / 12)
    c["neck.ry"] = c.get("neck.ry", 0.0) - 28 * turn; c["head.ry"] = c.get("head.ry", 0.0) - 30 * turn   # toward +Z
    c["neck.rx"] = c.get("neck.rx", 0.0) - 10 * turn; c["head.rx"] = c.get("head.rx", 0.0) - 10 * turn
    blink_ch(c, rig, f, N, [30, 62], loop=False)
    c["floorclamp"] = True
    return c


@mclip("stand_wobbly", 126, False, props=["mat"], markers={"up": 52, "step1": 72, "step2": 88, "straight": 108},
       notes="like a newborn calf, standing on his mat (feet 0.026 up on the pad): from sit_up's pose he turns to face "
             "+Z, draws his knees in, pushes up bottom-first, rises onto knock-kneed wobbly legs, arms flung out for "
             "balance, lurching left and right; two tiny unsure steps in place (each with a wobble), then he "
             "straightens up tall, arms down, and blinks at his own legs; holds standing")
def man_stand_wobbly(rig, f, N):
    a = man_sit_up(rig, 84, 84)
    crouch = h_base(rig, f, N, cycles=2, amp=0.6)
    for side, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + side]
        crouch[f"ik.leg{side}"] = V(b.x + 0.006 * sx, planted_ankle_y(rig, side, 0), b.z + 0.024)
        crouch[f"foot{side}.pitch"] = 0.0; crouch[f"pole.leg{side}"] = V(0.3 * sx, 0.4, 1)
        arm_ik(crouch, side, V(0.050 * sx, 0.012 + LIE_TOP, 0.090), V(0.6 * sx, 0.2, -0.6))
        crouch[f"hand{side}.bend"] = -40
    crouch["hips.ty"] = -0.080; crouch["hips.tz"] = -0.040; crouch["hips.rx"] = 40; crouch["spine.rx"] = 20
    crouch["chest.rx"] += 10; crouch["neck.rx"] = -16; crouch["head.rx"] = -10
    crouch["hips.yaw"] = 30.0
    on_mat(crouch)
    st = h_base(rig, f, N, cycles=2, amp=0.6)
    stand_feet(rig, st, spread=0.010)
    # wobble while up: knock knees, arms out, lurches
    wob = bump(f, 46, 112) if f < 112 else 0.0
    lurch = K([(0, 0), (52, 0), (58, 1), (64, -1), (70, 0.7), (76, -0.9), (82, 0.8), (88, -0.7), (94, 0.6), (100, -0.4),
               (106, 0.2), (112, 0), (126, 0)], f)
    lurchl = KL([(0, 0), (52, 0), (58, 1), (64, -1), (70, 0.7), (76, -0.9), (82, 0.8), (88, -0.7), (94, 0.6),
                 (100, -0.4), (106, 0.2), (112, 0), (126, 0)], f, lag=3)
    st["hips.tx"] = 0.010 * lurch * wob; st["hips.rz"] = -6 * lurch * wob; st["spine.rz"] = 5 * lurchl * wob
    st["chest.rz"] = 5 * lurchl * wob; st["head.rz"] = -6 * lurchl * wob
    st["hips.ty"] = -0.020 * wob
    st["spine.rx"] = 6 * wob; st["chest.rx"] += 4 * wob
    for side, sx in (("L", 1), ("R", -1)):
        st[f"pole.leg{side}"] = V(-1.2 * sx * wob, 0.0, 1)                    # knees knock inward
        st[f"ik.leg{side}"] = Vector(st[f"ik.leg{side}"]) + V(0.014 * sx * wob, 0, 0)       # feet apart, knees in
        st[f"upperArm{side}.raise"] = lerp(-20, 62, wob) + 14 * lurch * sx * wob
        st[f"upperArm{side}.bend"] = 8 + 10 * wob; st[f"forearm{side}.bend"] = 26 - 10 * wob
        st[f"forearm{side}.twist"] = -40 * sx * wob; fingers(st, side, lerp(22, 2, wob))
        st[f"hand{side}.bend"] = 6 + 18 * wob * math.sin(2 * math.pi * f / 9 + (0 if side == "L" else 1.5))
    # two tiny steps in place: lift a foot, put it down, lurch
    for side, a0 in (("L", 66), ("R", 82)):
        lift = bump(f, a0, a0 + 10)
        k = "ik.leg" + side
        st[k] = Vector(st[k]) + V(0, 0.016 * lift, 0.004 * lift)
        st[f"foot{side}.pitch"] = -10 * lift
    st["head.rx"] = -2 + 10 * bump(f, 106, 124)                              # looks down at his legs at the end
    on_mat(st)
    w1 = ease_io((f - 2) / 24)
    w2 = ease_io((f - 32) / 22)
    c = mix(mix(a, crouch, w1), st, w2)
    c["hips.ty"] = c.get("hips.ty", 0.0) - 0.010 * bump(f, 26, 40)      # a wobbly sag on the way up
    blink_ch(c, rig, f, N, [10, 60, 114, 120], loop=False)
    c["floorclamp"] = True
    return c


@mclip("jump_joy", 66, False, props=["mat"], markers={"hop1": 16, "hop2": 38},
       notes="on his mat: leaps up twice (crouch, high hop with knees tucked, land), arms flung high, then lands "
             "laughing, shoulders bouncing; ends in the plain standing pose on the mat. The root does not move (the "
             "mat stays down)")
def man_jump_joy(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.6)
    stand_feet(rig, c, spread=0.008)
    up = jump(c, rig, f, 16, 30, 0.060, crouch=0.020) + jump(c, rig, f, 38, 52, 0.070, crouch=0.020)
    tuck = up / 0.07
    for side, sx in (("L", 1), ("R", -1)):
        k = "ik.leg" + side
        c[k] = Vector(c[k]) + V(0, 0.020 * tuck, 0.010 * tuck)
        arms = ease_io((f - 6) / 11) * (1 - ease_io((f - 54) / 10))
        c[f"upperArm{side}.raise"] = lerp(-20, 120, arms); c[f"upperArm{side}.bend"] = lerp(8, 20, arms)
        c[f"forearm{side}.bend"] = lerp(26, 12, arms); fingers(c, side, lerp(22, 2, arms))
        c[f"forearm{side}.twist"] = -40 * sx * arms
    lg = pulses(f, N, [(52, 1.0), (57, 0.8), (62, 0.6)], decay=2.2, loop=False)
    c["shoulderL.raise"] += 4 * lg; c["shoulderR.raise"] += 4 * lg; c["head.rx"] = -8 * up / 0.07 - 4 * lg
    c["jaw.rx"] = 10 * bump(f, 14, 60)
    on_mat(c)
    blink_ch(c, rig, f, N, [6, 60], loop=False)
    return c


ROLL_SWITCH = 36       # the timeline switches mat -> matRoll here (1.2 s, CONTRACT §4)


ROLL_POSE = {"matRoll.rx": 35.0, "matRoll.ry": 20.0, "matRoll.tx": 0.008}   # the roll slants down-forward and out,
                                                                             # so its end disc clears the face


def roll_hold(c, rig, w=1.0, side="L"):
    """The rolled mat on his left shoulder (posed by ROLL_POSE): the left hand holds its lowered front end (chest
    space)."""
    c.update(ROLL_POSE)
    arm_ik(c, side, V(0.062, 0.010, 0.052), V(1.0, -0.8, 0.2), "chest", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 20, w); fingers(c, "L", lerp(c.get("fingersL.curl", 22), 70, w))


@mclip("roll_mat", 90, False, props=["mat", "matRoll"], markers={"switch": ROLL_SWITCH, "shoulder": 56},
       notes="steps back off the mat, squats and rolls it up with both hands (rolling forward away from him); at 1.2 s "
             "(`switch`, the timeline swaps the props mat -> matRoll) he grabs the roll and heaves it up onto his left "
             "shoulder (`shoulder`), then steps forward back onto his mark, proud; holds, holding the roll (= idle)")
def man_roll_mat(rig, f, N):
    back = ease_io((f - 2) / 13) * (1 - ease_io((f - 58) / 16))
    sq = bump(f, 8, 44)
    b = h_base(rig, f, N, cycles=1, amp=0.4)
    stepL = ease_io((f - 2) / 8) * (1 - ease_io((f - 58) / 10))      # left foot steps first (back, later forward)
    stepR = ease_io((f - 7) / 8) * (1 - ease_io((f - 64) / 10))
    stand_feet(rig, b, spread=0.010, fwdL=-0.080 * stepL, fwdR=-0.080 * stepR)
    b["hips.tz"] = -0.080 * back
    for side, a0, a1 in (("L", 2, 58), ("R", 7, 64)):
        k = "ik.leg" + side
        b[k] = Vector(b[k]) + V(0, 0.020 * (bump(f, a0, a0 + 8) + bump(f, a1, a1 + 10)), 0)
    on_mat(b, 1 - ease_io((f - 2) / 8))            # off the mat; after the switch the flat mat is gone
    b["hips.ty"] -= 0.090 * sq; b["hips.tz"] -= 0.020 * sq; b["hips.rx"] = 38 * sq
    b["spine.rx"] = 22 * sq; b["chest.rx"] += 12 * sq; b["neck.rx"] = -14 * sq; b["head.rx"] = -4 * sq
    for side, sx in (("L", 1), ("R", -1)):
        b[f"pole.leg{side}"] = V(0.4 * sx, 0.3, 1)
        roll = 0.012 * math.sin(2 * math.pi * (f - 14) / 8)
        reach = V(0.040 * sx, 0.040 + roll, -0.080 * back + 0.060 + 0.030 * ease_io((f - 14) / 20) + roll)
        arm_ik(b, side, reach, V(0.6 * sx, 0.2, -0.6), "root", bump(f, 10, 40))
        b[f"hand{side}.bend"] = 20; fingers(b, side, 50)
    heave = ease_io((f - ROLL_SWITCH) / 18)
    roll_hold(b, rig, heave)
    arm_ik2(b, "R", V(-0.010, 0.060, 0.060), V(-0.8, -0.6, -0.2), "chest", heave * (1 - ease_io((f - 58) / 12)))
    c = b
    pr = ease_io((f - 66) / 12)
    c["chest.rx"] = c.get("chest.rx", 0.0) - 4 * pr; c["head.rx"] = c.get("head.rx", 0.0) - 4 * pr
    c["jaw.rx"] = 4 * pulses(f, N, [(52, 1.0)], decay=3.0, loop=False)
    c["chest.rz"] = c.get("chest.rz", 0.0) - 6 * bump(f, 40, 62)
    blink_ch(c, rig, f, N, [30, 76], loop=False)
    c["floorclamp"] = True
    return c


def man_roll_base(rig, f, N, cycles=1, amp=0.6):
    """Standing, the rolled mat on his left shoulder held by the left hand."""
    c = h_base(rig, f, N, cycles=cycles, amp=amp)
    roll_hold(c, rig)
    c["chest.rz"] = -2.0
    return c


M_DANCE = (0.060, 0.42)
DANCE_N = 48


def dance_feet(rig, f, N):
    """Step-hops (skips) for the first 32 frames (two skips), then an airborne spin (frames 32-46), landing on the
    left foot at 48 = 0. Returns the leg channels and the body yaw / hop height."""
    out = {}
    spin = 360.0 * ease_io((f - 32) / 14) if f >= 32 else 0.0
    hop = 0.0
    for side, off in (("L", 0.0), ("R", 0.5)):
        base = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        if f < 32:
            p = ((f / 32.0) + off) % 1.0
            L = M_DANCE[0]
            if p < M_DANCE[1]:
                s_ = p / M_DANCE[1]
                z = L / 2 - L * s_
                y = planted_ankle_y(rig, side, 0) + 0.010 * math.sin(math.pi * s_)      # the hop: heel lifts
                pitch = 16 * math.sin(math.pi * s_)
            else:
                s_ = (p - M_DANCE[1]) / (1 - M_DANCE[1])
                z = -L / 2 + L * smooth(s_)
                y = planted_ankle_y(rig, side, 0) + 0.030 * math.sin(math.pi * s_)
                pitch = lerp(16, -8, s_)
            pos = V(base.x, y, base.z + z)
        else:
            s_ = (f - 32) / 16.0
            hop = 0.045 * math.sin(math.pi * min(1.0, s_))
            pos = rot_y(V(base.x * 0.6, 0, base.z), spin) + V(0, planted_ankle_y(rig, side, 0) + hop * 0.9 + 0.012 * (side == "R"), 0)
            pitch = 20 * math.sin(math.pi * min(1.0, s_))
        out["leg" + side] = (pos, pitch)
    return out, spin, hop


@mclip("dance_mat", DANCE_N, True, props=["matRoll"], speed=(M_DANCE[0], M_DANCE[1] * 32 / DANCE_N),
       markers={"spin": 32},
       notes="skipping, spinning dance with the rolled mat on his left shoulder: two step-hops (knees high, the free "
             "right arm swinging up, head bobbing, laughing), then a hop-and-spin (a full turn in the air, `spin`); "
             "travels: naturalSpeed in clips.json (the director moves him at that speed)")
def man_dance_mat(rig, f, N):
    c = man_roll_base(rig, f, N, cycles=2, amp=0.6)
    legs, spin, hop = dance_feet(rig, f, N)
    for side in "LR":
        t, pitch = legs["leg" + side]
        c[f"ik.leg{side}"] = t; c[f"foot{side}.pitch"] = pitch
        c[f"pole.leg{side}"] = rot_y(V(0.2 if side == "L" else -0.2, 0.2, 1), spin)
        c[f"foot{side}.ry"] = spin
    c["hips.yaw"] = spin
    ph = 2 * math.pi * f / 16.0
    wsp = ease_io((f - 28) / 6) * (1 - ease_io((f - 42) / 6))      # skip -> spin -> skip, smooth both ways
    sk = 1.0 - wsp
    c["hips.ty"] = (0.006 + 0.008 * abs(math.sin(ph))) * sk + hop
    c["hips.rz"] = 4 * math.sin(ph / 2) * sk; c["chest.rz"] += -4 * math.sin(ph / 2) * sk
    c["head.rz"] = 6 * math.sin(ph / 2 - 0.4) * sk
    c["head.rx"] = -4 + 3 * math.cos(ph)
    arm = lerp(0.5 + 0.5 * math.sin(ph / 2), 1.0, wsp)
    c["upperArmR.raise"] = lerp(10, 110, arm); c["upperArmR.bend"] = 20; c["forearmR.bend"] = lerp(50, 20, arm)
    c["forearmR.twist"] = 40; fingers(c, "R", 10)
    c["jaw.rx"] = 8 + 4 * abs(math.sin(ph))
    c["eyelids.sy"] = 3.0
    return c


M_WALK = (0.074, 0.60)


@mclip("walk_mat", 32, True, props=["matRoll"], markers={"contactL": 0, "contactR": 16}, speed=M_WALK,
       notes="happy bouncy walk with the rolled mat on his left shoulder (left hand on it), the right arm swinging "
             "freely, a spring in every step, head up, smiling")
def man_walk_mat(rig, f, N):
    c = man_roll_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=M_WALK[0], lift=0.016, duty=M_WALK[1], heel=12, toeoff=26)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.002 + 0.005 * math.cos(2 * ph - 0.5)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.35); c["head.rz"] = 2.5 * math.cos(ph - 0.8)
    c["hips.rz"] = 2.5 * math.cos(ph)
    c["upperArmR.bend"] = 8 + 26 * math.sin(ph - 0.25); c["forearmR.bend"] = 30 + 14 * math.sin(ph - 1.0)
    c["head.rx"] = -4 + 2 * math.cos(2 * ph)
    blink_ch(c, rig, f, N, [20])
    return c


@mclip("talk", 96, True,
       notes="standing talk, both hands free: shy, eager gestures (hands open at chest height, a hand to his chest on "
             "'me'), small nods, weight shifting; jaw in a syllable rhythm")
def man_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    beats = talk_jaw(c, f, N, 55)
    bt = beat_curve(beats, f, N, width=9)
    c["head.rx"] = -2 + 3 * bt; c["head.ry"] = 5 * wave(f, N, 1, 0.2); c["head.rz"] = 4 * wave(f, N, 1, 0.4)
    o = K([(0, 0.4), (12, 1.0), (40, 0.9), (52, 0.2), (80, 0.6), (96, 0.4)], f, N, True)
    palm_up(c, "R", o); palm_up(c, "L", 0.6 * o)
    me = K([(0, 0), (52, 0), (60, 1), (76, 1), (84, 0), (96, 0)], f, N, True)
    arm_ik(c, "R", V(-0.010, 0.000, 0.044), V(-0.8, -0.6, -0.2), "chest", me)
    sh = wave(f, N, 1, 0.1)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.8 * sh
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [8, 58])
    return c


@mclip("idle", 120, True, props=["matRoll"],
       notes="standing happily, the rolled mat on his left shoulder (left hand on it), the right hand loose; bounces "
             "lightly on his toes now and then, looks round smiling, blinks")
def man_idle(rig, f, N):
    c = man_roll_base(rig, f, N, cycles=2, amp=0.8)
    bnc = bump(f, 70, 80) + bump(f, 82, 92)
    c["hips.ty"] = 0.006 * bnc
    look_keys(c, [(0, 0), (20, 0), (34, 20), (60, 20), (76, -16), (100, -16), (112, 0), (120, 0)], f, N)
    sh = wave(f, N, 1, 0.2)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.8 * sh; c["spine.rz"] = 1.0 * sh
    stand_feet(rig, c, spread=0.004, pitchL=20 * bnc, pitchR=20 * bnc)
    blink_ch(c, rig, f, N, [14, 58, 65, 104])
    return c


@mclip("wave", 48, True, props=["matRoll"],
       notes="waving with the free right hand high, the rolled mat on his left shoulder, bouncing on his toes, beaming")
def man_wave(rig, f, N):
    c = man_roll_base(rig, f, N, cycles=1, amp=0.6)
    hand_wave(c, rig, "R", f, N, 3, high=1.0)
    bnc = 0.5 + 0.5 * math.cos(2 * math.pi * 2 * f / N)
    c["hips.ty"] = 0.003 * bnc
    c["head.rz"] = -5; c["jaw.rx"] = 5
    stand_feet(rig, c, spread=0.004, pitchL=10 * bnc, pitchR=10 * bnc)
    blink_ch(c, rig, f, N, [30])
    return c


# =============================================================================================== FRIENDS (friend1-4)
# One function per clip, baked on each friend's own rig (actions friend1_<clip> ... friend4_<clip>). Variation per
# friend: a phase offset for the free loops (never for walk / carry: those stay in step with the man), an amplitude.
FV = {"friend1": dict(ph=0.00, amp=1.00), "friend2": dict(ph=0.17, amp=0.85), "friend3": dict(ph=0.41, amp=1.20),
      "friend4": dict(ph=0.63, amp=1.00)}


def fclip(name, N, loop, phase=True, **kw):
    """Register one clip for all four friends. phase: loops get the friend's phase offset (frames shifted)."""
    def deco(fn):
        for ch in FRIENDS:
            def wrapped(rig, f, N_, fn=fn, ch=ch):
                sh = int(round(FV[ch]["ph"] * N_)) if (loop and phase) else 0
                return fn(rig, (f + sh) % N_ if sh else f, N_)
            CLIPS.append(Clip(ch, name, N, loop, wrapped, **kw))
        return fn
    return deco


def famp(rig):
    return FV[rig.ch]["amp"]


@fclip("idle", 120, True,
       notes="standing, weight shifting, looking round, a scratch of the head or hands on hips (per friend phase)")
def friend_idle(rig, f, N):
    a = famp(rig)
    c = h_base(rig, f, N, cycles=3, amp=0.9)
    sh = K([(0, -0.6), (30, -0.6), (56, 0.8), (90, 0.8), (110, -0.6), (120, -0.6)], f, N, True)
    c["hips.tx"] = 0.004 * sh * a; c["hips.rz"] = -2.2 * sh * a; c["spine.rz"] = 1.2 * sh; c["head.rz"] = -1.5 * sh
    look_keys(c, [(0, 0), (16, 0), (30, 22 * a), (54, 22 * a), (68, -14), (96, -14), (110, 0), (120, 0)], f, N)
    hp = K([(0, 0), (60, 0), (70, 1), (100, 1), (110, 0), (120, 0)], f, N, True)
    hand_on_hip(c, rig, "L", hp)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [12, 64, 71])
    return c


F_WALK = (0.072, 0.60)
F_WALK_N = 40
F_SPEED = F_WALK[0] / (F_WALK[1] * F_WALK_N / FPS)          # 0.09 units/s, shared by walk and both carry clips
F_CARRY = (F_SPEED * F_WALK[1] * CARRY_N / FPS, F_WALK[1])   # stride for the 48-frame carry cycle at the same speed


@fclip("walk", F_WALK_N, True, phase=False, markers={"contactL": 0, "contactR": 20}, speed=F_WALK,
       notes="plain cheerful walk (90 steps/min), arms swinging, head bobbing; the same speed as the carry clips")
def friend_walk(rig, f, N):
    a = famp(rig)
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=F_WALK[0], lift=0.013, duty=F_WALK[1], heel=12, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.004 + 0.003 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -5 * math.sin(ph - 0.35); c["head.ry"] = 2 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.5 * math.cos(ph) * a; c["head.rz"] = 1.2 * math.cos(ph - 0.9) * a
    c["upperArmL.bend"] = 8 - 18 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 18 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 30 - 10 * math.sin(ph - 1.0); c["forearmR.bend"] = 30 + 10 * math.sin(ph - 1.0)
    blink_ch(c, rig, f, N, [27])
    return c


def carry_hands(c, rig, f, front):
    """Both hands on the pole ends: world y CARRY_HAND (+ the shared bob), x +-0.0675 (the poles), z behind the hips
    (front carrier) or in front (back carrier), from CARRY_D and the pole ends at +-0.2036."""
    z = (0.2036 - 0.008 - CARRY_D) if front else (CARRY_D - 0.2036 + 0.008)
    y = CARRY_HAND + carry_bob(f)
    for side, sx in (("L", 1), ("R", -1)):
        pole = V(0.6 * sx, 0.4, 1.0) if front else V(0.7 * sx, -0.5, -0.4)
        arm_ik(c, side, V(0.0675 * sx, y, z), pole, "root")
        c[f"hand{side}.bend"] = 10 if front else -10; fingers(c, side, 82)
        c[f"hand{side}.twist"] = 30 * sx if front else -10 * sx


@fclip("carry_front", CARRY_N, True, phase=False, markers={"contactL": 0, "contactR": 24}, speed=F_CARRY,
       notes="front carrier: walks (same speed as walk) holding the mat's two front pole ends behind him at y 0.15 "
             "(hands 0.04 behind his hips at the poles' ends; group spacing CARRY_D), arms back, leaning forward with "
             "effort, head up, puffing (strained face); steps in time with the man's bob")
def friend_carry_front(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.2)
    g = gait(rig, f, N, L=F_CARRY[0], lift=0.011, duty=F_CARRY[1], heel=10, toeoff=22)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.008 + 0.003 * math.cos(2 * ph - 0.4)
    c["hips.rx"] = 6; c["spine.rx"] = 8; c["chest.rx"] += 6; c["neck.rx"] = -8; c["head.rx"] = -8
    c["hips.rz"] = 2.5 * math.cos(ph); c["chest.rz"] = -1.5 * math.cos(ph - 0.5); c["hips.ry"] = 2 * math.sin(ph)
    carry_hands(c, rig, f, True)
    c["jaw.rx"] = 3 + 3 * (0.5 + 0.5 * math.cos(2 * ph))
    blink_ch(c, rig, f, N, [30])
    return c


@fclip("carry_back", CARRY_N, True, phase=False, markers={"contactL": 0, "contactR": 24}, speed=F_CARRY,
       notes="back carrier: walks (same speed as walk) holding the two back pole ends in front of him at y 0.15, arms "
             "forward, leaning back a little against the weight, knees soft, cheeks puffed (strained face); steps in "
             "time with the man's bob")
def friend_carry_back(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.2)
    g = gait(rig, f, N, L=F_CARRY[0], lift=0.010, duty=F_CARRY[1], heel=10, toeoff=20)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.010 + 0.003 * math.cos(2 * ph - 0.4)
    c["hips.rx"] = -2; c["spine.rx"] = -4; c["chest.rx"] += -2; c["neck.rx"] = 4; c["head.rx"] = 0
    c["hips.rz"] = 2.5 * math.cos(ph); c["chest.rz"] = -1.5 * math.cos(ph - 0.5)
    carry_hands(c, rig, f, False)
    c["jaw.rx"] = 2 + 2 * (0.5 + 0.5 * math.cos(2 * ph + 1.0))
    blink_ch(c, rig, f, N, [14])
    return c


SQ_N = 120
SQ_BOING = 48


def squeeze_root(f):
    """Root z: two steps forward 0.06, a squeeze, `boing` (frame 48) flings him back 0.08 (lands at frame 58)."""
    if f <= 26:
        return 0.060 * ease_io(f / 26)
    if f <= SQ_BOING:
        return 0.060 + 0.006 * math.sin(2 * math.pi * (f - 26) / 7) * bump(f, 26, SQ_BOING)
    s = min(1.0, (f - SQ_BOING) / 10)
    return 0.060 - 0.080 * (1 - (1 - s) ** 2)


@fclip("squeeze_bounce", SQ_N, False, markers={"boing": SQ_BOING, "sit": 58, "up": 100},
       root_motion="root travels +Z 0.06 (two steps), then is flung back to -0.02 (net 0.08 back from the crowd) and "
                   "stays there; play in place on the mark (no `to`), the root motion moves him",
       notes="walks 0.06 forward into the crowd (two steps), wiggles his shoulders and pushes as if squeezing through, "
             "`boing` (1.6 s): bounced straight back 0.08, legs flying up, he lands sitting down hard (bottom bounce, "
             "head wobble, stars), then scrambles up, rubs his bottom; ends standing, a sheepish grin")
def friend_squeeze_bounce(rig, f, N):
    z = squeeze_root(f)
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    stand_feet(rig, c, spread=0.004)
    if f < SQ_BOING + 2:                             # feet planted in the world while the root moves: two steps
        for side, a0 in (("L", 0), ("R", 13)):
            s_ = min(1.0, max(0.0, (f - a0) / 13))
            zw = 0.060 * ease_io(s_)
            k = "ik.leg" + side
            c[k] = Vector(c[k]) + V(0, 0.014 * math.sin(math.pi * s_), zw - z)
            c[f"foot{side}.pitch"] = -8 * math.sin(math.pi * s_)
    c["root.tz"] = z
    sq = bump(f, 24, SQ_BOING + 2)
    wig = math.sin(2 * math.pi * (f - 24) / 6) * sq
    c["spine.rx"] = 10 * sq; c["chest.rx"] += 6 * sq; c["chest.rz"] = 8 * wig; c["spine.rz"] = 4 * wig
    c["shoulderL.raise"] += 6 * sq * max(0, wig); c["shoulderR.raise"] += 6 * sq * max(0, -wig)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.050 * sx, 0.200 * kH(rig), 0.090), V(0.9 * sx, -0.5, -0.3), "root", sq)
        c[f"hand{side}.bend"] = -40 * sq
    # the boing: flung back, sits hard, bounces, gets up
    if f >= SQ_BOING:
        seat = ease_io((f - SQ_BOING) / 10) * (1 - ease_io((f - 82) / 20))
        sit = sit_upright(rig, f, N, legs="out", hands="back")
        c2 = mix(c, sit, seat)
        air = math.sin(math.pi * min(1.0, (f - SQ_BOING) / 10))
        for side in "LR":
            c2[f"thigh{side}.rx"] = c2.get(f"thigh{side}.rx", 0.0) - 30 * air
        c2["hips.ty"] = c2.get("hips.ty", 0.0) + 0.030 * air + 0.010 * bump(f, 58, 66)
        c2["head.rz"] = c2.get("head.rz", 0.0) + 10 * math.sin(2 * math.pi * (f - 58) / 10) * bump(f, 58, 84)
        c2["head.rx"] = c2.get("head.rx", 0.0) - 8 * air
        for side, sx in (("L", 1), ("R", -1)):
            c2[f"upperArm{side}.raise"] = c2.get(f"upperArm{side}.raise", 0.0) + 60 * air
        rub = bump(f, 96, 118)
        arm_ik2(c2, "R", V(-0.040, 0.170 * kH(rig), -0.040), V(-0.8, -0.4, -0.5), "root", rub)
        c2["handR.bend"] = c2.get("handR.bend", 0.0) + 20 * rub * math.sin(2 * math.pi * f / 6)
        c2["spine.rx"] = c2.get("spine.rx", 0.0) + 16 * bump(f, 80, 100)
        c2["hips.tz"] = c2.get("hips.tz", 0.0) + 0.016 * bump(f, 80, 100)
        c2["jaw.rx"] = 8 * bump(f, SQ_BOING, 66) + 4 * bump(f, 104, 120)
        c2["eyelids.sy"] = 1.0 + 8.0 * bump(f, 56, 70)
        c2["floorclamp"] = True
        return c2
    c["jaw.rx"] = 4 * sq
    blink_ch(c, rig, f, N, [8], loop=False)
    return c


@fclip("think", 90, True,
       notes="right hand on his chin, left arm across his belly holding the right elbow, head tilted, eyes up, the "
             "right foot tapping (three taps), a little hum")
def friend_think(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    arm_ik(c, "R", V(-0.006, -0.030, 0.040) * kH(rig), V(-0.6, -0.8, 0.1), "head")
    c["handR.bend"] = 30; fingers(c, "R", 50)
    arm_ik(c, "L", V(-0.020, -0.050, 0.050) * kH(rig), V(0.9, -0.5, 0.2), "chest")
    fingers(c, "L", 40)
    c["head.rz"] = 8 + 3 * wave(f, N, 1); c["head.rx"] = -6; c["head.ry"] = 6 * wave(f, N, 1, 0.3)
    tap = sum(bump(f, a0, a0 + 7) for a0 in (40, 50, 60))
    stand_feet(rig, c, spread=0.004, fwdR=0.008, pitchR=-18 * tap)
    c["jaw.rx"] = 2 * bump(f, 10, 30)
    blink_ch(c, rig, f, N, [20, 74], base=1.4)
    return c


@fclip("idea", 45, False, markers={"idea": 10},
       notes="an idea! the right arm shoots straight up (index up: hand open, fingers together), a little jump, big "
             "grin, eyes wide; holds the arm up")
def friend_idea(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    stand_feet(rig, c, spread=0.004)
    up = ease_io((f - 5) / 7)
    c["upperArmR.raise"] = lerp(-20, 150, up); c["upperArmR.bend"] = lerp(8, 18, up); c["forearmR.bend"] = lerp(26, 4, up)
    c["forearmR.twist"] = 40 * up; c["handR.bend"] = -10 * up; fingers(c, "R", lerp(22, 4, up))
    jump(c, rig, f, 10, 20, 0.030, crouch=0.012)
    c["head.rx"] = -6 * up; c["chest.rx"] += -4 * up
    c["jaw.rx"] = 6 * up
    c["eyelids.sy"] = 1.0
    return c


def friend_kneel(rig, f, N, lean=0.0):
    """Kneeling on both knees at the hole's edge, leaning forward by `lean` (0..1)."""
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    kneel_legs(rig, c, 1.0, 1.0)
    c["hips.rx"] = 6 + 30 * lean; c["spine.rx"] = 6 + 22 * lean; c["chest.rx"] += 4 + 12 * lean
    c["neck.rx"] = -6 - 8 * lean; c["head.rx"] = 4 + 10 * lean
    c["coatfollow"] = 0.6
    return c


@fclip("dig", 36, True, seated=True, markers={"tossR": 12, "tossL": 30},
       notes="kneeling at the roof hole, fast: both hands dig into the roof in front and pull up a clod, tossing it "
             "aside over his right shoulder, then over his left; strained face, quick head turns")
def friend_dig(rig, f, N):
    a = famp(rig)
    c = friend_kneel(rig, f, N, lean=0.8)
    k = kH(rig)
    dig = K([(0, 1.0), (4, 1.0), (12, 0.0), (18, 1.0), (22, 1.0), (30, 0.0), (36, 1.0)], f, N, True)
    side_ = K([(0, -1), (14, -1), (18, 1), (32, 1), (36, -1)], f, N, True)
    for side, sx in (("L", 1), ("R", -1)):
        low = V(0.020 * sx, 0.016, 0.120 * k)
        high = V((0.040 * sx - 0.100 * side_) , 0.230 * k, 0.020)
        arm_ik(c, side, vlerp(high, low, dig), V(0.9 * sx, -0.3, -0.3), "root")
        c[f"hand{side}.bend"] = 30 * dig; fingers(c, side, lerp(10, 70, dig))
    c["chest.ry"] = 20 * side_ * (1 - dig) * a; c["head.ry"] = 18 * side_ * (1 - dig)
    c["spine.rx"] += 10 * dig
    c["jaw.rx"] = 3 + 3 * (1 - dig)
    c["settle"] = ("hips", ("thighL", "thighR", "shinL", "shinR"), 0.001, 1.0)
    return c


@fclip("lower_rope", 40, True, seated=True, markers={"handL": 0, "handR": 20},
       notes="kneeling at the edge, leaning over the hole, paying out a rope hand over hand: one hand grips and lowers "
             "while the other reaches up for the next hold; careful, strained face")
def friend_lower_rope(rig, f, N):
    c = friend_kneel(rig, f, N, lean=0.6)
    k = kH(rig)
    for side, sx, off in (("L", 1, 0.0), ("R", -1, 0.5)):
        p = (f / N + off) % 1.0
        if p < 0.5:
            s_ = p / 0.5
            y = lerp(0.110, 0.035, s_) * k
            zz = 0.115 * k
        else:
            s_ = (p - 0.5) / 0.5
            y = lerp(0.035, 0.110, smooth(s_)) * k
            zz = (0.115 - 0.025 * math.sin(math.pi * s_)) * k
        arm_ik(c, side, V(0.012 * sx, y, zz), V(0.9 * sx, -0.4, -0.2), "root")
        c[f"hand{side}.bend"] = 10; fingers(c, side, 80 if p < 0.5 else 20)
    c["head.rx"] += 6; c["chest.rx"] += 2 * wave(f, N, 2)
    c["jaw.rx"] = 2
    c["settle"] = ("hips", ("thighL", "thighR", "shinL", "shinR"), 0.001, 1.0)
    return c


@fclip("peek", 60, True, seated=True,
       notes="kneeling, hands on the roof edge, leaning far over the hole and looking down, little nods (as if "
             "watching the man arrive), a smile")
def friend_peek(rig, f, N):
    c = friend_kneel(rig, f, N, lean=1.0)
    k = kH(rig)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.050 * sx, 0.034, 0.100 * k), V(0.8 * sx, 0.0, -0.4), "root")
        c[f"hand{side}.bend"] = -50; fingers(c, side, 10)
    c["neck.rx"] += 14; c["head.rx"] += 16 + 6 * beat_curve([10, 22, 40], f, N, width=8)
    c["head.ry"] = 6 * wave(f, N, 1, 0.2)
    c["settle"] = ("hips", ("thighL", "thighR", "shinL", "shinR"), 0.001, 1.0)
    blink_ch(c, rig, f, N, [30])
    return c


@fclip("cheer", 30, True, markers={"hop": 8},
       notes="jumps with both arms up, high-fives the air at the top of the hop, lands, again; cheering mouth")
def friend_cheer(rig, f, N):
    a = famp(rig)
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    stand_feet(rig, c, spread=0.006)
    jump(c, rig, f, 6, 18, 0.034 * a, crouch=0.014)
    clap = bump(f, 9, 16)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = 120 + 20 * clap; c[f"upperArm{side}.bend"] = 14 - 10 * clap
        c[f"forearm{side}.bend"] = 20 - 14 * clap; c[f"forearm{side}.twist"] = -50 * sx; fingers(c, side, 4)
        c[f"hand{side}.bend"] = -20 * clap
    c["head.rx"] = -8; c["jaw.rx"] = 9
    c["eyelids.sy"] = 1.0
    return c


@fclip("wave", 48, True,
       notes="friendly wave with the right hand, a little bounce, smiling")
def friend_wave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    hand_wave(c, rig, "R", f, N, 3, high=0.9)
    sh = wave(f, N, 1, 0.0)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh; c["head.rz"] = -5 + 2 * sh
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [20])
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


COAT = {"belt1": "thighL", "sash1": "thighL"}
FOOT_EPS = 0.0008
FLOOR_CHAIN = 0.008      # min height of a chain bone's tail (the panel / prop mesh has thickness)


def coat_follow(rig, basis, M, w):
    """Seated / lying / kneeling: the belt / sash end lies along the thigh (half way to hanging) instead of hanging
    through the page."""
    Mroot3 = (M["root"] @ rig.rest["root"].inverted()).to_3x3().normalized()
    down = Mroot3 @ Vector((0, 0, -1))
    for n, th in COAT.items():
        if n not in rig.names:
            continue
        td = (M[th].to_3x3().normalized() @ Vector((0, 1, 0))).normalized()
        up = Mroot3 @ Vector((0, 0, 1))
        td = td - up * td.dot(up)                       # along the thigh, but level: drapes, never sticks up
        td = td.normalized() if td.length > 1e-4 else (Mroot3 @ (C @ V(0, 0, 1)))
        sx = 1
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
            inv = (M["root"] @ rig.rest["root"].inverted()).inverted()     # settle in the root bone's own space
            pts = [to_d(inv @ to_bl(p)) for p in rig.skin(M, set(vbones) if vbones else None)]
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
        low = min([p.y for p in rig.skin(M)] + [foot_low(rig, M, sd) for sd in "LR"])
        if low < -0.002:
            chs["root.ty"] = chs.get("root.ty", 0.0) + (-0.002 - low)
            out = solve_pose(rig, chs)
    return out


CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "jesus": [(("mantle1",), 70.0, 7.0, 0.30, 12.0), (("belt1",), 90.0, 7.5, 0.30, 24.0)],
    "peter": [(("cloth1",), 90.0, 8.0, 0.30, 22.0)],
    "man": [(("sash1",), 90.0, 7.5, 0.30, 24.0)],
    "friend1": [(("belt1",), 90.0, 7.5, 0.30, 24.0)],
    "friend2": [(("belt1",), 85.0, 7.5, 0.30, 24.0)],
    "friend3": [(("belt1",), 95.0, 7.5, 0.30, 24.0), (("band1",), 100.0, 7.0, 0.25, 26.0)],
    "friend4": [(("belt1",), 90.0, 7.5, 0.30, 24.0)],
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
    sim_chains(rig, prim, clip_.loop, gscale=0.0 if clip_.seated else 1.0, floor=CHAIN_FLOOR.get(clip_.action, FLOOR_CHAIN))
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
    fr = ["idle", "walk", "carry_front", "carry_back", "squeeze_bounce", "think", "idea", "dig", "lower_rope", "peek",
          "cheer", "wave"]
    out = {"jesus": ["idle", "talk", "walk", "teach", "look_up_smile", "kneel_kind", "stand_talk", "command_rise",
                     "lie_sleep", "wake_up", "calm_storm", "laugh", "wave"],
           "peter": ["idle", "talk", "walk", "roof_shock", "dust_off", "laugh", "steer", "steer_hard", "bail",
                     "shake_awake", "amazed", "cower", "wave"],
           "man": ["lie_mat", "carried", "lowered", "sit_up", "stand_wobbly", "jump_joy", "roll_mat", "dance_mat",
                   "walk_mat", "talk", "idle", "wave"]}
    out.update({f: list(fr) for f in FRIENDS})
    return out


PROPS = ("mat", "ropes", "matRoll", "bucket")
CHAIN_FLOOR = {"jesus_lie_sleep": 0.034, "jesus_wake_up": 0.034, "man_lie_mat": 0.030, "man_carried": 0.030, "man_lowered": 0.030, "man_sit_up": 0.030}


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


SAMPLE_BONES = ("root", "head", "jaw", "handR", "handL", "footL", "toeR", "hips", "belt1", "sash1", "mantle1", "cloth1",
                "band1", "mat", "ropes", "matRoll", "bucket")


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
            "stage": {"carryY": CARRY_Y, "carryHandY": CARRY_HAND, "carryDistance": CARRY_D, "carryCycleFrames": CARRY_N,
                      "carryMode": "man `carried` at base y CARRY_Y; friend1 `carry_front` CARRY_D ahead of the man's root "
                      "and friend2 `carry_back` CARRY_D behind, all three facing the travel, started together (same "
                      "48-frame cycle, same speed)", "wakeDistance": WAKE_D, "wakeMode": "jesus `lie_sleep` root (under "
                      "his shoulder, head toward his +X) WAKE_D in front of Peter; Peter faces him",
                      "kneelDistance": KNEEL_D, "kneel": KNEEL["jesus"], "ropeTopLocalY": ROPE_TOP}}
    only = os.environ.get("MI_ONLY")
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
        print("MI_CHECK", cl.action, json.dumps(info["checks"]), flush=True)
        meta["clips"].append(info)
    meta["travel"] = travel_needs()
    for r in meta["travel"]:
        print("MI_TRAVEL", json.dumps(r))
    if only:
        print("MI_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "mi_anim.blend")
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
        print("MI_EXPORT", ch)
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("MI_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


# ----------------------------------------------------------------------------------------------- render helpers
REGIONS = json.load(open(REGIONS_JSON))
FACES = {ch: {"default": v["faceDecal"]["default"], "clips": v["faceDecal"].get("clipExpression", {})}
         for ch, v in list(REGIONS["characters"].items()) + list(REGIONS.get("offSheet", {}).items())}
DECAL_NODES = {}


def face_png(ch, expr):
    stem = "friend" if ch in FRIENDS else ch            # the four friends share one set of drawings
    p = os.path.join(FACE_DIR, f"{stem}_{expr}.png")
    return p if os.path.exists(p) else os.path.join(FACE_DIR, f"{stem}_{FACES[ch]['default']}.png")


def set_expression(ch, clip_name):
    if ch in DECAL_NODES:
        DECAL_NODES[ch].image = bpy.data.images.load(face_png(ch, FACES[ch]["clips"].get(clip_name, FACES[ch]["default"])),
                                                     check_existing=True)


_kit_char_material = char_material


def char_material(ch):
    """Kit demo colours for the sheet cast; the friends: their fixed paint (friend_paint.png on the page UV) + decal."""
    if ch not in FRIENDS:
        return _kit_char_material(ch)
    m = bpy.data.materials.new(f"anim_{ch}"); m.use_nodes = True; nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = 0.75
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(FRIEND_PAINT, check_existing=True)
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], tex.inputs["Vector"])
    dt = nt.nodes.new("ShaderNodeTexImage"); dt.image = bpy.data.images.load(face_png(ch, FACES[ch]["default"]), check_existing=True)
    dt.extension = 'CLIP'
    du = nt.nodes.new("ShaderNodeUVMap"); du.uv_map = "decal"
    nt.links.new(du.outputs["UV"], dt.inputs["Vector"])
    mx = nt.nodes.new("ShaderNodeMix"); mx.data_type = 'RGBA'
    nt.links.new(dt.outputs["Alpha"], mx.inputs["Factor"])
    nt.links.new(tex.outputs["Color"], mx.inputs[6]); nt.links.new(dt.outputs["Color"], mx.inputs[7])
    nt.links.new(mx.outputs[2], bsdf.inputs["Base Color"])
    DECAL_NODES[ch] = dt
    return m


def stage_of(cl):
    """Where a clip is shown in renders: (x, z, yaw, y). In the yard / road, the roof clips on the roof."""
    if cl.name in ("dig", "lower_rope", "peek"):
        return (-0.36, -0.38, 90.0, ROOF)
    if cl.name == "lowered":
        return (-0.24, -0.38, -90.0, 0.0)
    if cl.name == "carried":
        return (0.10, 0.10, 0.0, CARRY_Y)
    return (0.10, 0.10, 0.0, 0.0)


DIST_K = {ch: 1.25 for ch in CHARS}
PAIRS = [  # contact-sheet pair rows: (A action, B action, distance, mode, label)
    ("peter_shake_awake", "jesus_lie_sleep", WAKE_D, "front", "pair: shake_awake + lie_sleep (0.10, facing)"),
    ("jesus_kneel_kind", "man_lie_mat", KNEEL_D, "front", "pair: kneel_kind + lie_mat (0.12, facing)"),
]
PAIR_AT = {"tandem": (0.10, 0.10, 0.0), "lie": (0.12, 0.10, 0.0), "face": (0.10, 0.10, 0.0), "front": (0.10, 0.02, 0.0)}


def place_pair_mode(ra, rb, dist, mode, at=None):
    """B (the partner) at `at` = (x, z, y); A placed `dist` from B. face: they face each other (A -> +X, B -> -X);
    tandem: A behind B, both facing +Z; lie: A at -X facing +X, B facing +Z (lying along X, A at its -X side);
    front: B faces +Z, A stands `dist` in front of B facing it (-Z) - the geometry shake_awake / kneel_kind assume."""
    bx, bz, y = at or PAIR_AT[mode]
    if mode == "face":
        place_rig(ra, bx - dist, bz, 90.0, y); place_rig(rb, bx, bz, -90.0, y)
    elif mode == "tandem":
        place_rig(ra, bx, bz - dist, 0.0, y); place_rig(rb, bx, bz, 0.0, y)
    elif mode == "front":
        place_rig(rb, bx, bz, 0.0, y); place_rig(ra, bx, bz + dist, 180.0, y)
        return V(bx, y, bz + dist / 2)
    else:
        place_rig(ra, bx - dist, bz, 90.0, y); place_rig(rb, bx, bz, 0.0, y)
    return V(bx - dist / 2 if mode != "tandem" else bx, y, bz - (dist / 2 if mode == "tandem" else 0.0))


def pair_cams(T, mode):
    return {"front": T + V(0.0, 0.10, 0.55), "q3": T + V(0.30, 0.16, 0.34), "top": T + V(0.0, 0.50, 0.16),
            "back": T + V(0.0, 0.14, -0.50), "side": T + V(0.50, 0.10, 0.0), "lside": T + V(-0.50, 0.10, 0.0),
            "phone": T + V(0.10, 0.42, 0.62)}


CARRY_AT = (0.10, 0.10)        # carry group render spot: the man's root; the group walks toward -X (yaw -90)


def place_carry(rigs, fr):
    """man (carried, base CARRY_Y), friend1 (carry_front) CARRY_D ahead, friend2 (carry_back) CARRY_D behind, all
    facing -X, all at frame fr of their (same-length) loops. Returns the group centre."""
    x, z = CARRY_AT
    place_rig(rigs["man"], x, z, -90.0, CARRY_Y)
    place_rig(rigs["friend1"], x - CARRY_D, z, -90.0, 0.0)
    place_rig(rigs["friend2"], x + CARRY_D, z, -90.0, 0.0)
    return V(x, 0.0, z)


HIDE_SET = ("roofHole", "rubble")


def setup_look_mi(sc, res, samples=8):
    """Kit setup_look + hide the set's hidden-at-start props (roof hole, rubble)."""
    setup_look(sc, res, samples=samples)
    for o in bpy.data.objects:
        q = o
        while q is not None:
            if q.name.split(".")[0] in HIDE_SET:
                o.hide_render = True; break
            q = q.parent


def set_props_for_frame(rig, cl, fr):
    """roll_mat: the timeline switches mat -> matRoll at 1.2 s; show that in renders."""
    if cl.action == "man_roll_mat":
        bpy.data.objects["man_mat"].hide_render = fr >= 36
        bpy.data.objects["man_matRoll"].hide_render = fr < 36


def render_carry(sc, cam, rigs, frames_sel, views, d, prefix):
    clips = {c.action: c for c in CLIPS}
    trio = [("man", "man_carried"), ("friend1", "friend1_carry_front"), ("friend2", "friend2_carry_back")]
    show_only(rigs, [t[0] for t in trio], {ch: clips[a] for ch, a in trio})
    for ch, a in trio:
        set_expression(ch, clips[a].name)
    bk = {ch: bake_clip(rigs[ch], clips[a]) for ch, a in trio}
    out = []
    for fr in frames_sel:
        for ch, a in trio:
            apply_basis(rigs[ch], bk[ch][fr % clips[a].N][0])
        T = place_carry(rigs, fr) + V(0, 0.15, 0)
        bpy.context.view_layer.update()
        cams = {"side": T + V(0.0, 0.08, 0.75), "q3": T + V(0.45, 0.24, 0.55), "top": T + V(0.0, 0.80, 0.10),
                "front": T + V(-0.80, 0.10, 0.0), "back": T + V(0.80, 0.12, 0.0), "phone": T + V(0.15, 0.55, 0.85)}
        for vn in views:
            look(cam, T, cams[vn], lens=40)
            fn = f"{prefix}_{fr:03d}_{vn}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True); out.append((fr, vn, fn))
    for ch, _ in trio:
        reset_pose(rigs[ch])
    return out


def mode_contact():
    sc, rigs = open_scene()
    setup_look_mi(sc, (300, 300), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    clips = {c.action: c for c in CLIPS}
    for cl in CLIPS:
        if cl.ch in FRIENDS[1:] and cl.name not in ("carry_back",):
            continue           # friends share the functions: friend1 stands for all four (friend2 for carry_back)
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
            place_rig(rig, mark[0], mark[1], mark[2], mark[3])
            set_props_for_frame(rig, cl, fr)
            bpy.context.view_layer.update()
            H = rig.H * (2.4 if cl.name == "lowered" else 1.0)
            tgt_y = mark[3] + (0.20 if cl.name == "lowered" else 0.0)
            view_cam(cam, rig, (mark[0], mark[1], mark[2]), "q3", dist_k=DIST_K[cl.ch], H=H)
            if mark[3] or cl.name == "lowered":
                a_ = math.radians(32 + mark[2]); tg = V(mark[0], tgt_y + rig.H * 0.45, mark[1]); dist = H * 1.25
                look(cam, tg, V(tg.x + math.sin(a_) * dist, tg.y + rig.H * 0.15, tg.z + math.cos(a_) * dist))
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("MI_CONTACT_ROW", cl.action, picks, flush=True)
    row = {"action": "carry group (side / q3)", "loop": True, "frames_total": CARRY_N, "frames": []}
    for fr, vn, fn in render_carry(sc, cam, rigs, [0, 12, 24, 36], ("side",), d, "carry") + \
            render_carry(sc, cam, rigs, [6, 30], ("q3",), d, "carry"):
        row["frames"].append({"f": fr, "file": fn, "marker": vn})
    rows.append(row)
    for a, b, dist, mode, label in PAIRS:
        ca, cb = clips[a], clips[b]
        ra, rb = rigs[ca.ch], rigs[cb.ch]
        show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
        set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
        fa_, fb_ = bake_clip(ra, ca), bake_clip(rb, cb)
        row = {"action": label, "loop": ca.loop, "frames_total": ca.N, "frames": []}
        sel = [ca.N // 4, ca.N] if not ca.loop else [0, ca.N // 4]
        for fr in sel:
            fb = fr % cb.N if cb.loop else min(cb.N, fr)
            apply_basis(ra, fa_[fr][0]); apply_basis(rb, fb_[fb][0])
            T = place_pair_mode(ra, rb, dist, mode)
            bpy.context.view_layer.update()
            for vn in (("side", "q3") if mode == "front" else ("front", "q3")):
                look(cam, T + V(0, 0.10, 0), pair_cams(T + V(0, 0.10, 0), mode)[vn], lens=40)
                fn = f"pair_{a}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                row["frames"].append({"f": fr, "file": fn, "marker": vn})
        reset_pose(ra); reset_pose(rb)
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """MI_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'pair:<A>:<B>:<dist>:<frameA>[:mode[:views]]'; 'carry:<f1,f2>[:views]' (the carry group)."""
    sc, rigs = open_scene()
    res = int(os.environ.get("MI_PROBE_RES", "440"))
    setup_look_mi(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    clips = {cl.action: cl for cl in CLIPS}
    out = []
    for item in os.environ.get("MI_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "carry":
            frs = [int(v) for v in parts[1].split(",")]
            views = parts[2].split(",") if len(parts) > 2 else ["side", "q3"]
            out += [fn for _, _, fn in render_carry(sc, cam, rigs, frs, views, d, "carry")]
            continue
        if parts[0] == "pair":
            a, b, dist, fr = parts[1], parts[2], float(parts[3]), int(parts[4])
            mode = parts[5] if len(parts) > 5 else "face"
            views = parts[6].split(",") if len(parts) > 6 else ["front", "q3", "top", "side"]
            ca, cb = clips[a], clips[b]
            ra, rb = rigs[ca.ch], rigs[cb.ch]
            show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
            set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
            fb = (fr % cb.N) if cb.loop else max(0, min(cb.N, fr))
            apply_basis(ra, bake_clip(ra, ca)[min(fr, ca.N)][0]); apply_basis(rb, bake_clip(rb, cb)[fb][0])
            T = place_pair_mode(ra, rb, dist, mode) + V(0, 0.12, 0)
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
            apply_basis(rig, fr_[fr][0]); place_rig(rig, mark[0], mark[1], mark[2], mark[3])
            set_props_for_frame(rig, cl, fr)
            bpy.context.view_layer.update()
            dk = float(os.environ.get("MI_PROBE_DIST", str(DIST_K[cl.ch])))
            view_cam(cam, rig, (mark[0], mark[1], mark[2]), view, bone, dist_k=dk)
            if (mark[3] or cl.name == "lowered") and not bone:
                yaw = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "top": 25, "low": 25}[view] + mark[2]
                a_ = math.radians(yaw); up = 0.20 if cl.name == "lowered" else 0.0
                tg = V(mark[0], mark[3] + up + rig.H * 0.45, mark[1]); dist = rig.H * dk * (2.0 if up else 1.0)
                look(cam, tg, V(tg.x + math.sin(a_) * dist, tg.y + rig.H * 0.15, tg.z + math.cos(a_) * dist))
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("MI_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("MI_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
