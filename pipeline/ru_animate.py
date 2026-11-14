"""Ruth skeletal animation (Animation role, story pack #3).

Adapted from pipeline/es_animate.py (Esther, committed version), which is adapted from pipeline/dg_animate.py.
Two halves in one file:

* Under Blender (headless) it opens `assets/ruth/model/characters.blend` (Characters role's rigs), builds every clip of
  docs/ruth/CONTRACT.md §4 (+ one extra) as an action `<char>_<clip>` and exports `assets/ruth/anim/{ruth,naomi,boaz}.glb`
  (character + skin + one glTF animation per action) and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/ru_animate.py all        # build + verify + contact sheet
    python3 pipeline/ru_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/ru_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/ru_animate.py contact    # anim/contact_sheet.png (key poses per clip, in Bethlehem)
    RU_PROBE="ruth_glean:0,40:side" python3 pipeline/ru_animate.py probe       # work renders ($RU_ANIM_WORK/probe.png)
    RU_PROBE="pair:ruth_hug:naomi_hug:0.122:30" python3 pipeline/ru_animate.py probe   # two actors facing each other
    RU_ONLY=ruth_glean,naomi_hug  (with build: bake + check a subset, no export)

How the motion is made (no hand-placed keys; the script is the source):
  * Each clip is a function frame -> channels. Rotations are in DESIGN axes (x right, y up, z toward the viewer),
    applied in the bone's rest frame: `rx ry rz`, `bend`, `raise`, `swing`, `twist`, `curl` (fingers, + = close),
    offsets `tx ty tz` and `sy` (local-Y scale: eyelids blink). Keys are Catmull-Rom splines (`K`), wrapped for loops.
  * Legs: two-bone IK to ankle targets (gait with heel / ball / toe contact; kneels place the knee on the page).
    Arms: the same IK where a hand must be somewhere (staff, sheaf, baby, partner's back), the target in root space or
    in the space of any bone (chest, head, sheaf, baby, staff).
  * Naomi's staff is solved: given where its foot stands on the page and its direction, the right wrist target is
    iterated until the staff foot is there (planted every other step in walk_tired, at her side when she talks).
  * Secondary motion is simulated: scarf, shawl, head-cloth and Boaz's cloak panels are damped spring chains on top of
    the keyed pose (loops simulate 3 cycles and close exactly); the stalk handfuls wobble a little in the fist.
  * Blinks at irregular frames (single, double, slow); talk is an irregular syllable rhythm with word gaps; nods and
    hand beats land on the stressed syllables; every one-shot has anticipation, overshoot and settle.
Intermediates: $RU_ANIM_WORK (default /tmp/ru_anim_work).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RU = os.path.join(ROOT, "assets/ruth")
MODEL = os.path.join(RU, "model")
ANIM = os.path.join(RU, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
SET_GLB = os.path.join(MODEL, "bethlehem.glb")
TIMELINE = os.path.join(RU, "timeline.json")
FACES_JSON = os.path.join(RU, "faces.json")
FACE_DIR = os.path.join(ROOT, "docs/ruth/design/faces")
WORK = os.environ.get("RU_ANIM_WORK") or "/tmp/ru_anim_work"
ENV = "RU_"                      # env-var / log prefix the story_kit functions use (RU_PROBE_*, RU_VERIFY*, RU_NOSET)
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FPS = 30
CHARS = ("ruth", "naomi", "boaz")

# stage distances the two-actor clips are fitted to (docs/ruth/storyboard/story.py marks)
HUG_D = 0.122        # ROAD_A (-0.40, 0.16) .. ROAD_B (-0.28, 0.14): hold_hands / listen_moved / hug
CHEER_D = 0.126      # DOOR (-0.30, -0.20) .. DOOR_RUTH (-0.18, -0.16): cheer_up / show_bundle
ASK_D = 0.161        # THRESH (0.14, -0.30) .. THRESH_RUTH (0.00, -0.22): ask_humble
TALK_D = 0.163       # GLEAN (0.14, 0.10) .. BOAZ_TALK (0.30, 0.13): talk_kind / bow_kneel

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


# =============================================================================================== orchestration (python3)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                      # noqa: E402
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "animation")   # shared animation functions: 60 defs (docs/STORY-KIT.md)


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
    d.text((pad, 14), "Ruth - key poses per clip (30 fps; frame / seconds; marker names in red; * = extra clip; "
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
    sheet = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT) if os.environ.get("RU_QUANT", "0") == "1" else sheet
    sheet.save(out, optimize=True)
    print("RU_CONTACT", out, sheet.size)


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


# ----------------------------------------------------------------------------------------------- curves
# ----------------------------------------------------------------------------------------------- acting helpers
BLINK_SHAPE = [1.0, 6.5, 12.8, 12.8, 8.0, 3.5, 1.0]      # frames 0..6: fast close, short hold, slower open


# =============================================================================================== rig model (pure python FK)
class Rig:
    H_OF = {"ruth": 0.33, "naomi": 0.31, "boaz": 0.38}

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
        for b in ("stalks", "sheaf"):
            o = bpy.data.objects.get(f"{ch}_{b}")
            if o is not None and b in self.names:
                mw = obj.matrix_world.inverted() @ o.matrix_world
                cen = sum((mw @ v.co for v in o.data.vertices), Vector()) / len(o.data.vertices)
                self.prop_axis[b] = (self.rest[b].inverted().to_3x3() @ (cen - self.rest[b].translation)).normalized()

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


# =============================================================================================== clip library
class Clip:
    def __init__(self, ch, name, N, loop, fn, markers=None, notes="", extra=False, speed=None, props=None, backwards=False):
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


# ----------------------------------------------------------------------------------------------- legs
_PAY = {}


# --- kneeling: knees on the page
KNEEL = {"ruth": dict(KY=float(os.environ.get("RU_KY", "0.022")), kz=0.016, thigh_back=float(os.environ.get("RU_TB", "12")), shin_slope=float(os.environ.get("RU_SS", "26")))}


# =============================================================================================== RUTH
# Rest: A-pose, arms 55 deg below horizontal, hands open (palm to the body). raise -22 = arms relaxed by the dress.
def r_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.5 * b * amp; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.1 * b * amp; c["shoulderR.raise"] = 1.1 * b * amp
    c["neck.rx"] = 0.8 * b * amp
    c["upperArmL.raise"] = -22; c["upperArmR.raise"] = -22
    c["upperArmL.bend"] = 8; c["upperArmR.bend"] = 8
    c["forearmL.bend"] = 26; c["forearmR.bend"] = 26
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 22); fingers(c, "R", 22)
    c["head.rx"] = -2
    return c


def hands_clasped(c, rig, at, wring=0.0, w=1.0, space="root"):
    """Both hands loosely together at `at` (root space unless space given)."""
    arm_ik(c, "L", at + V(0.011 + 0.002 * wring, 0.000, -0.004), V(0.7, -0.6, -0.4), space, w)
    arm_ik(c, "R", at + V(-0.011 + 0.002 * wring, -0.004, 0.000), V(-0.7, -0.6, -0.4), space, w)


@clip("ruth", "idle", 150, True,
      notes="breathes (with a deeper breath at 1/3), weight L -> R -> L with the hips leading and the chest late, hands "
            "loosely together in front, the left hand once smooths the scarf end on her chest; looks at her partner, "
            "glances away and back (neck leads, head follows); blinks single, double and slow at irregular times; "
            "scarf tail settles after each turn")
def ruth_idle(rig, f, N):
    c = r_base(rig, f, N, cycles=3, amp=0.9)
    deep = bump(f, 36, 76)
    c["chest.rx"] += -2.2 * deep; c["shoulderL.raise"] += 1.6 * deep; c["shoulderR.raise"] += 1.6 * deep
    sh = K([(0, -0.3), (16, -0.3), (40, 1.0), (82, 1.0), (104, -0.8), (134, -0.8), (150, -0.3)], f, N, True)
    sh_l = KL([(0, -0.3), (16, -0.3), (40, 1.0), (82, 1.0), (104, -0.8), (134, -0.8), (150, -0.3)], f, N, True, lag=7)
    c["hips.tx"] = 0.0045 * sh; c["hips.ty"] = -0.0015 - 0.0012 * abs(sh)
    c["hips.rz"] = -2.4 * sh; c["spine.rz"] = 1.5 * sh_l; c["chest.rz"] = 1.0 * sh_l; c["head.rz"] = -1.6 * sh_l
    look = [(0, 0), (28, 0), (38, -11), (60, -11), (70, 4), (100, 4), (112, 0), (150, 0)]
    c["neck.ry"] = 0.4 * K(look, f, N, True); c["head.ry"] = 0.6 * KL(look, f, N, True, lag=4)
    c["head.rx"] += K([(0, 0), (38, 2), (60, 1), (70, -2), (100, -1), (112, 0), (150, 0)], f, N, True)
    c["head.rz"] += 3.0 * K([(0, 1), (40, 1), (60, -0.4), (100, -0.4), (120, 1), (150, 1)], f, N, True)
    # hands together in front; the left hand smooths the scarf end (f 84-120)
    tuck = ease_io((f - 84) / 10) * (1 - ease_io((f - 108) / 14))
    at = V(0.0, 0.158 + 0.002 * wave(f, N, 3), 0.040)
    hands_clasped(c, rig, at)
    if tuck > 0:
        c["ik.armL"] = vlerp(c["ik.armL"], V(0.018, 0.212 - 0.010 * bump(f, 90, 106), 0.050), tuck)
        c["handL.bend"] = 6 - 20 * tuck
    fingers(c, "L", 30 + 6 * wave(f, N, 2, 0.6) - 10 * tuck); fingers(c, "R", 34 + 5 * wave(f, N, 3, 0.1))
    blink(c, f, N, [21, 63, 70, 128], slow=1.0)
    stand_feet(rig, c, spread=0.002, pitchR=K([(0, 0), (40, 0), (56, 7), (82, 7), (96, 0), (150, 0)], f, N, True))
    return c


R_WALK = (0.074, 0.60)


@clip("ruth", "walk", 34, True, markers={"contactL": 0, "contactR": 17}, speed=R_WALK,
      notes="light young walk, ~106 steps/min: soft hip bob and drop, chest counter-turn, arms swing with lagging "
            "forearms and wrists, head steady with a small nod per step; scarf tail swings late")
def ruth_walk(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=R_WALK[0], lift=0.011, duty=R_WALK[1], heel=12, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0042 + 0.0030 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -6 * math.sin(ph - 0.35); c["head.ry"] = 3 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.5 * math.cos(ph); c["chest.rz"] = -1.5 * math.cos(ph - 0.5); c["head.rz"] = 0.8 * math.cos(ph - 0.9)
    c["spine.rx"] = 2; c["head.rx"] = -3 + 1.4 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 8 - 15 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 15 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 28 - 9 * math.sin(ph - 1.0); c["forearmR.bend"] = 28 + 9 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 9 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 9 * math.sin(ph - 1.6)
    fingers(c, "L", 24 + 6 * math.sin(ph - 1.8)); fingers(c, "R", 24 - 6 * math.sin(ph - 1.8))
    blink(c, f, N, [27])
    return c


@clip("ruth", "talk", 96, True,
      notes="jaw in an irregular syllable rhythm with word gaps (lip sync overrides it); nods on the stressed syllables; "
            "first phrase the right hand opens palm-up toward the listener, second phrase the left hand comes to her "
            "chest; weight shift; two blinks")
def ruth_talk(rig, f, N):
    c = r_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 31, amp=(5, 13))
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=9)
    btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -2 + 3.5 * bt - 1.0 * wave(f, N, 1, 0.2)
    c["head.ry"] = 5 * wave(f, N, 1, 0.1) + 2 * wave(f, N, 3, 0.4); c["head.rz"] = 3 * wave(f, N, 1, 0.35)
    c["neck.ry"] = 2 * wave(f, N, 1, 0.05)
    # phrase A (0-48): right palm-up; phrase B (48-96): left hand to the chest, right relaxes
    pa = K([(0, 0.2), (10, 0.9), (38, 1.0), (52, 0.15), (88, 0.1), (96, 0.2)], f, N, True)
    pb = K([(0, 0.0), (44, 0.0), (56, 1.0), (84, 0.9), (94, 0.0), (96, 0.0)], f, N, True)
    lift = pa * (0.75 + 0.25 * btl)
    c["upperArmR.raise"] = -22 + 2 * lift; c["upperArmR.bend"] = 8 + 40 * lift
    c["forearmR.bend"] = 26 + 52 * lift; c["forearmR.twist"] = 10 - 80 * lift
    c["handR.bend"] = 6 - 22 * btl * pa
    fingers(c, "R", 30 - 26 * btl * pa - 6 * lift)
    arm_ik(c, "L", V(0.012, -0.004 + 0.004 * btl, 0.046), V(0.8, -0.6, -0.2), "chest", pb)
    c["handL.bend"] = 6 - 14 * pb
    fingers(c, "L", 26 - 8 * pb)
    c["chest.ry"] = -4 * lift + 3 * pb; c["chest.rx"] += 1.5 * bt
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh; c["spine.rz"] = 0.9 * sh
    blink(c, f, N, [7, 61])
    stand_feet(rig, c, spread=0.002)
    return c


@clip("ruth", "sad", 120, True,
      notes="head low, shoulders slumped and forward, hands hanging together low in front; slow heavy breathing with "
            "one long sigh (rise, hold, sink); looks up at her partner once and down again; slow heavy blinks")
def ruth_sad(rig, f, N):
    c = r_base(rig, f, N, cycles=2, amp=0.8)
    sigh = K([(0, 0), (40, 0), (54, 1), (62, 1), (82, -0.6), (100, 0), (120, 0)], f, N, True)
    up = K([(0, 0), (14, 0), (22, 1), (34, 1), (44, 0), (120, 0)], f, N, True)
    c["chest.rx"] += 7 - 3 * sigh; c["spine.rx"] += 3; c["neck.rx"] = 9 - 5 * up
    c["shoulderL.raise"] += -3 + 3 * sigh; c["shoulderR.raise"] += -3 + 3 * sigh
    c["shoulderL.swing"] = 4; c["shoulderR.swing"] = 4
    up = K([(0, 0), (14, 0), (22, 1), (34, 1), (44, 0), (120, 0)], f, N, True)
    c["head.rx"] = 22 - 18 * up + 2 * wave(f, N, 1, 0.3)
    c["head.ry"] = -3 + 2 * up; c["head.rz"] = 4 - 2 * up
    hands_clasped(c, rig, V(0.0, 0.142 + 0.002 * sigh, 0.034))
    fingers(c, "L", 34); fingers(c, "R", 40)
    sh = K([(0, 0), (30, 0.6), (70, 0.6), (90, -0.4), (120, 0)], f, N, True)
    c["hips.tx"] = 0.0025 * sh; c["hips.rz"] = -1.6 * sh; c["hips.ty"] = -0.002
    blink(c, f, N, [9, 47, 96], base=1.8, slow=1.6)
    stand_feet(rig, c, spread=0.0, pitchL=K([(0, 0), (70, 0), (80, 5), (100, 5), (110, 0), (120, 0)], f, N, True))
    return c


@clip("ruth", "shake_head", 36, False, markers={"no": 8},
      notes="a quick breath in, then three firm head shakes that shrink (no!), the shoulders and chest answering a "
            "little late, scarf whipping behind; ends chin up and steady, hands coming up toward the chest (next: hold_hands)")
def ruth_shake(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.3)
    ant = bump(f, 0, 8)
    c["chest.rx"] += -2.5 * ant; c["head.rx"] = -2 - 3 * ant
    sh = [(0, 0), (5, 3), (9, -20), (14, 18), (19, -13), (24, 7), (29, -2), (34, 0), (36, 0)]
    c["head.ry"] = K(sh, f); c["neck.ry"] = 0.35 * KL(sh, f, lag=2)
    c["chest.ry"] = 0.12 * KL(sh, f, lag=3)
    c["head.rz"] = -0.15 * KL(sh, f, lag=1)
    res = ease_io((f - 22) / 12)
    c["head.rx"] += -4 * res; c["chest.rx"] += -2 * res
    up = ease_io((f - 20) / 16)
    hands_clasped(c, rig, V(0.0, 0.170 + 0.025 * up, 0.044 + 0.010 * up), w=up)
    fingers(c, "L", 22 + 16 * up); fingers(c, "R", 22 + 16 * up)
    blink(c, f, N, [26], loop=False)
    stand_feet(rig, c, spread=0.002)
    return c


@clip("ruth", "hold_hands", 90, True,
      notes="pleading: leans in with the left foot a little forward, both hands reach forward at chest height toward "
            "her partner 0.12 in front, palms up and open; small pleading pushes on the stressed words (irregular), "
            "head tilts and nods, chest heaves with a held-back sob; blinks")
def ruth_hold_hands(rig, f, N):
    c = r_base(rig, f, N, cycles=2, amp=1.2)
    _, beats = syllables(N, 7, amp=(6, 14), gap=0.35)
    push = beat_curve(beats, f, N, width=13)
    pushl = beat_curve(beats, f - 3, N, width=13)
    c["hips.tz"] = 0.004 + 0.002 * push; c["spine.rx"] = 3 + 2 * push; c["chest.rx"] += 2 + 2 * pushl
    for side, sx, lag in (("L", 1, 0), ("R", -1, 2)):
        pl = beat_curve(beats, f - lag, N, width=13)
        arm_ik(c, side, V(0.026 * sx, 0.180 + 0.004 * pl + 0.002 * wave(f, N, 2, 0.1 * sx), 0.050 + 0.008 * pl),
               V(0.8 * sx, -0.7, -0.1))
        c[f"hand{side}.twist"] = 60 * (-sx)
        c[f"hand{side}.bend"] = -18
        fingers(c, side, 12 + 10 * (1 - pl))
    c["head.rz"] = 6 + 3 * wave(f, N, 1, 0.2); c["head.rx"] = 2 + 4 * pushl - 2 * wave(f, N, 1, 0.4)
    c["head.ry"] = 2 * wave(f, N, 1, 0.6)
    sob = pulses(f, N, [(30, 1.0), (36, 0.6), (70, 0.8)], decay=3.0)
    c["chest.rx"] += -1.5 * sob; c["shoulderL.raise"] += 2 * sob; c["shoulderR.raise"] += 2 * sob
    blink(c, f, N, [18, 52, 58])
    stand_feet(rig, c, spread=0.002, fwdL=0.016)
    return c


@clip("ruth", "hug", 90, True,
      notes="arms around her partner standing 0.122 in front (fitted to Naomi's hug at the S02 marks): leans in, "
            "right arm over Naomi's left shoulder, left arm round her back lower down, cheek tilted onto Naomi's head; "
            "gentle side-to-side rocking (same phase as naomi_hug), one squeeze and a pat on the back, deep breaths")
def ruth_hug(rig, f, N):
    c = r_base(rig, f, N, cycles=2, amp=1.2)
    s = hug_sway(f, N)
    sq = bump(f, 40, 62)
    pat = pulses(f, N, [(66, 1.0), (75, 0.7)], decay=2.5)
    c["hips.tz"] = 0.016; c["spine.rx"] = 7; c["chest.rx"] += 6 + 2 * sq
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -2.0 * s; c["spine.rz"] = 1.4 * s; c["chest.rz"] = 1.0 * s
    c["neck.rx"] = 6; c["head.rx"] = 8; c["neck.ry"] = 8; c["head.ry"] = 22; c["head.rz"] = -12 + 2 * s
    c["chest.ry"] = 4
    D = HUG_D
    # Ruth's right hand on Naomi's upper back (over her left shoulder), left hand round her back at the waist
    arm_ik(c, "R", V(-0.006 + 0.002 * s, 0.208 - 0.006 * sq, D + 0.020 + 0.004 * pat), V(-1.0, 0.1, -0.15))
    arm_ik(c, "L", V(0.016 + 0.002 * s, 0.170 - 0.006 * sq, D + 0.018), V(1.0, -0.2, -0.1))
    c["handR.bend"] = 18 - 6 * pat; c["handL.bend"] = 14
    c["handR.twist"] = 40; c["handL.twist"] = -50
    fingers(c, "R", 18 + 10 * sq); fingers(c, "L", 22 + 12 * sq)
    c["eyelids.sy"] = 1.0
    stand_feet(rig, c, spread=0.003, fwdL=0.014, fwdR=-0.004)
    return c


@clip("ruth", "cheer_up", 66, False, markers={"touch": 30},
      notes="a breath, steps in on the left foot, reaches her right hand to Naomi's left upper arm (0.126 in front, "
            "S03 marks), squeezes it, leans in with a head tilt and a smile; then brightens: a little bounce on the "
            "toes, left hand opens palm-up beside her (eager); holds with the hand on Naomi's arm")
def ruth_cheer_up(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.5)
    ant = bump(f, 0, 10)
    step = ease_io((f - 6) / 14)
    reach = ease_io((f - 10) / 20)
    over = bump(f, 26, 40)
    bright = ease_io((f - 40) / 14)
    bounce = bump(f, 42, 52) + 0.5 * bump(f, 52, 60)
    c["hips.tz"] = 0.020 * step + 0.004 * over; c["hips.ty"] = -0.003 * ant + 0.004 * bounce
    c["spine.rx"] = 6 * reach; c["chest.rx"] += -2 * ant + 4 * reach - 3 * bright
    c["chest.ry"] = -8 * reach + 3 * bright
    D = CHEER_D
    start = V(-0.070, 0.150, 0.020)
    tgt = V(-0.056, 0.198 + 0.003 * over, D - 0.016)
    arm_ik(c, "R", start.lerp(tgt, reach), V(-0.9, -0.5, -0.1), "root", min(1.0, 0.2 + reach * 1.3))
    c["handR.twist"] = -30 * reach; c["handR.bend"] = -10 * reach
    fingers(c, "R", 22 + 26 * bump(f, 28, 44) + 12 * reach)
    # left hand: to her chest during the reach ("don't be sad"), then out palm-up, eager
    arm_ik(c, "L", V(0.014, -0.006, 0.046), V(0.8, -0.6, -0.2), "chest", reach * (1 - bright))
    c["upperArmL.raise"] = -22 + 10 * bright; c["upperArmL.bend"] = 8 + 28 * bright
    c["forearmL.bend"] = 26 + 50 * bright; c["forearmL.twist"] = -10 + 75 * bright
    c["handL.bend"] = 6 - 16 * bright; fingers(c, "L", 22 - 14 * bright)
    c["head.rz"] = 8 * reach - 2 * bright; c["head.rx"] = -2 + 4 * reach - 5 * bright; c["head.ry"] = -6 * reach
    stand_feet(rig, c, spread=0.002, fwdL=0.030 * step, pitchL=0, pitchR=10 * bounce, liftR=0.0)
    blink(c, f, N, [4, 46], loop=False)
    return c


# --- gleaning (kneeling)
def glean_kneel(rig, c, w=1.0):
    kneel_legs(rig, c, w, w)
    c["hips.rx"] = c.get("hips.rx", 0.0) - 3 * w


# reach-and-pick cycle: (frame, x, z) where the left hand picks a stalk off the stubble
GLEAN_PICKS = [(24, 0.046, 0.082), (82, 0.000, 0.094)]
GLEAN_BUNCH = V(-0.024, 0.104, 0.064)
GLEAN_N = 120


def glean_hand(f, N):
    """Left wrist target (root space) + grip / bend, for the kneel-reach-pick-gather loop."""
    bunch = GLEAN_BUNCH                           # right fist with the handful, in front of her belly
    rest = V(0.034, 0.096, 0.062)
    keys_t = []
    # per pick: look (p-14), reach (p-10..p), pick (p..p+6), lift and gather into the bunch (p+6..p+22), back to rest
    pts = [(0, rest)]
    for p, x, z in GLEAN_PICKS:
        pts += [(p - 12, rest), (p - 2, V(x, 0.054, z)), (p + 3, V(x, 0.044, z)), (p + 8, V(x * 0.8, 0.074, z - 0.004)),
                (p + 20, bunch + V(0.016, 0.006, 0.008)), (p + 25, bunch + V(0.012, 0.004, 0.006)), (p + 36, rest)]
    pts.append((N, rest))
    tgt = V(*(K([(k, v[i]) for k, v in pts], f, N, True) for i in range(3)))
    grip = 0.0
    for p, _, _ in GLEAN_PICKS:
        grip = max(grip, ease_io((f - p) / 4) * (1 - ease_io((f - p - 22) / 5)))
    reach = max(bump(f, p - 14, p + 12) for p, _, _ in GLEAN_PICKS)
    return tgt, grip, reach


@clip("ruth", "glean", GLEAN_N, True, props=["stalks"],
      notes="kneeling (both knees on the stubble), right fist holds the handful in front of her lap; two picks per "
            "loop at different spots: she looks first, leans and reaches down with the LEFT hand (anticipation lean "
            "back), fingers close on a stalk, lifts it, adds it to the handful in the right fist (fist opens a little "
            "and closes), straightens, wipes a glance up at the field; breathing, blinks. (The stalks prop is on handR, "
            "so the hands are swapped against the contract wording.)")
def ruth_glean(rig, f, N):
    c = r_base(rig, f, N, cycles=3, amp=0.7)
    glean_kneel(rig, c)
    tgt, grip, reach = glean_hand(f, N)
    # torso: lean forward into each reach (spine + chest), small lean back before it, sway
    pre = max(bump(f, p - 18, p - 8) for p, _, _ in GLEAN_PICKS)
    gather = max(bump(f, p + 10, p + 30) for p, _, _ in GLEAN_PICKS)
    c["hips.rx"] += 16 * reach + 4 * gather; c["spine.rx"] = 6 + 20 * reach - 4 * pre + 6 * gather
    c["chest.rx"] += 4 + 18 * reach + 3 * gather
    side = max(bump(f, p - 14, p + 12) * (1 if x > 0.02 else -0.4) for p, x, _ in GLEAN_PICKS)
    c["spine.rz"] = -5 * side; c["chest.ry"] = 6 * side + 4 * gather
    look_up = bump(f, 60, 74) + bump(f, 112, 120) + bump(f, 0, 6)
    c["neck.rx"] = 10 * reach + 4 * gather - 6 * look_up
    c["head.rx"] = 18 * reach + 8 * gather - 10 * look_up + 2
    c["head.ry"] = 10 * side - 6 * gather + 8 * bump(f, 60, 74)
    arm_ik(c, "L", tgt, V(0.8, -0.3, -0.4))
    c["handL.bend"] = -40 * reach + 8 * gather; c["handL.twist"] = -20 * reach
    fingers(c, "L", 12 + 55 * grip)
    arm_ik(c, "R", GLEAN_BUNCH + V(0, 0.004 * gather - 0.020 * reach, 0.006 * gather + 0.012 * reach), V(-0.8, -0.5, -0.3))
    c["handR.bend"] = -8; c["handR.twist"] = 20
    c["aim.stalks"] = V(-0.55, 0.80, 0.25 + 0.1 * gather)
    fingers(c, "R", 68 - 14 * max(bump(f, p + 16, p + 28) for p, _, _ in GLEAN_PICKS))
    blink(c, f, N, [15, 52, 97, 104])
    return c


@clip("ruth", "kneel", 30, False, extra=True, markers={"knees_down": 22},
      notes="EXTRA (not in CONTRACT §4): stand -> kneel for gleaning, right knee first then left, the right hand "
            "closes; ends in frame 0 of glean. Play it before glean when she arrives standing (S04, t 62.54)")
def ruth_kneel(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.2)
    one = ease_io((f - 2) / 14); two = ease_io((f - 9) / 14)
    p = ruth_glean(rig, 0, GLEAN_N)
    w = 0.5 * (one + two)
    kneel_legs(rig, c, two, one, hips_w=w)
    c["hips.ty"] -= 0.006 * bump(f, 0, 10)
    c["hips.rx"] = lerp(0, p.get("hips.rx", 0), w)
    c["spine.rx"] = lerp(0, p.get("spine.rx", 0), w) + 10 * bump(f, 4, 26)
    c["chest.rx"] += 4 * bump(f, 4, 26)
    hw = ease_io((f - 10) / 18)
    for k in ("ik.armL", "ik.armR", "ikspace.armL", "ikspace.armR", "pole.armL", "pole.armR"):
        c[k] = p[k]
    c["ikw.armL"] = c["ikw.armR"] = hw
    for k in ("handL.bend", "handR.bend", "handL.twist", "handR.twist", "head.rx", "neck.rx", "head.ry"):
        c[k] = lerp(c.get(k, 0.0), p.get(k, 0.0), hw)
    fingers(c, "L", lerp(22, p["fingersL.curl"], hw)); fingers(c, "R", lerp(22, p["fingersR.curl"], hw))
    blink(c, f, N, [3], loop=False)
    return c


@clip("ruth", "stand_up", 54, False, markers={"stand": 34}, props=["stalks"],
      notes="from the glean kneel: looks up (at Boaz), sets the left foot forward, pushes up with a hand on the knee, "
            "rises, brings the feet together, brushes her skirt once with the left hand; right fist keeps the handful; "
            "holds standing")
def ruth_stand_up(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.4)
    p = ruth_glean(rig, 0, GLEAN_N)
    up = ease_io((f - 12) / 22)
    stepL = ease_io((f - 4) / 9)
    backL = ease_io((f - 32) / 9)
    look = ease_io(f / 10)
    # legs: right knee from kneeling to standing; left foot steps forward (kneel -> lunge) then back
    kneel_legs(rig, c, 0.0, 1 - up, hips_w=1 - up)
    hip, knee, ankle = kneel_geom(rig, "L", **KNEEL["ruth"])
    bL = rig.head["footL"]
    lunge = V(bL.x + 0.004, planted_ankle_y(rig, "L", 0), 0.060)
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
    c["spine.rx"] = lerp(p.get("spine.rx", 0), 0, up) + 14 * lean; c["chest.rx"] += 4 * lean
    c["head.rx"] = lerp(p["head.rx"], -4, look) - 6 * lean; c["neck.rx"] = lerp(p.get("neck.rx", 0), 0, look)
    # left hand pushes on the left knee, then brushes the skirt
    knee_pt = V(0.024, lerp(0.045, 0.10, up), 0.050 + 0.010 * up)
    hw = 1 - ease_io((f - 26) / 10)
    if f < 36:
        arm_ik(c, "L", vlerp(p["ik.armL"], knee_pt, ease_io(f / 8)), V(0.8, -0.3, -0.5), "root", hw)
    brush = bump(f, 38, 50)
    c["upperArmL.bend"] = 8 + 14 * brush; c["forearmL.bend"] = 26 + 20 * brush
    c["handL.bend"] = 6 - 30 * brush * math.sin(math.pi * (f - 38) / 6) if 38 <= f <= 50 else 6
    fingers(c, "L", 22 - 10 * brush)
    rw = 1 - ease_io((f - 30) / 16)
    arm_ik(c, "R", p["ik.armR"], V(-0.8, -0.5, -0.3), "root", rw)
    c["handR.bend"] = -8 * rw; fingers(c, "R", 62)
    c["aim.stalks"] = V(-0.55, 0.80, 0.25).lerp(V(-0.45, 0.55, 0.70), up)
    c["head.ry"] = 0; c["head.rz"] = 4 * ease_io((f - 40) / 10)
    if f >= 41:
        stand_feet(rig, c, spread=0.002)
        c["ik.legL"] = vlerp(tgt, c["ik.legL"], ease_io((f - 41) / 3))
    blink(c, f, N, [2, 44], loop=False)
    return c


@clip("ruth", "bow_kneel", 72, False, markers={"knees_down": 22, "bow": 40}, props=["stalks"],
      notes="humble and amazed: a breath, kneels (right knee then left), puts her hands together in front of her chest "
            "(right fist with the handful inside the left hand), bows the head and chest low; holds, breathing. "
            "Ends kneeling (if `shy` follows, play `stand_up` first)")
def ruth_bow_kneel(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.4)
    one = ease_io((f - 4) / 14); two = ease_io((f - 10) / 14)
    w = 0.5 * (one + two)
    kneel_legs(rig, c, two, one, hips_w=w)
    c["hips.ty"] -= 0.005 * bump(f, 0, 10)
    bow = ease_io((f - 24) / 18)
    over = bump(f, 36, 52)
    br = 0.5 * wave(f, 36, 1) * ease_io((f - 50) / 10)
    c["hips.rx"] = -2 * w + 8 * bow; c["spine.rx"] = 6 * w + 16 * bow + 2 * over
    c["chest.rx"] += 12 * bow + 2 * over - 1.5 * br
    c["neck.rx"] = 10 * bow; c["head.rx"] = 16 * bow + 2 * over
    hw = ease_io((f - 10) / 16)
    arm_ik(c, "L", V(0.010, -0.020, 0.050), V(0.8, -0.6, -0.2), "chest", hw)
    arm_ik(c, "R", V(-0.006, -0.026, 0.052), V(-0.8, -0.6, -0.2), "chest", hw)
    c["handL.bend"] = -24 * hw; c["handR.bend"] = -18 * hw
    fingers(c, "L", 22 + 26 * hw); fingers(c, "R", 64)
    c["aim.stalks"] = V(-0.45, 0.55, 0.70).lerp(V(-0.15, 0.80, 0.55), hw)
    blink(c, f, N, [6, 56], loop=False)
    return c


@clip("ruth", "shy", 120, True, props=["stalks"],
      notes="shy: hands clasped low in front, shoulders up a little, head down and turned aside; small sway side to "
            "side, the right toe twists on its tip; peeks up at him once (head lifts, holds, drops quickly); quick "
            "blinks; scarf sways")
def ruth_shy(rig, f, N):
    c = r_base(rig, f, N, cycles=2, amp=0.8)
    s = wave(f, N, 2, 0.0)
    peek = K([(0, 0), (56, 0), (62, 1), (76, 1), (80, 0), (120, 0)], f, N, True)
    c["shoulderL.raise"] += 4; c["shoulderR.raise"] += 4
    c["chest.rx"] += 2; c["spine.rx"] = 2
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -2.2 * s; c["spine.rz"] = 1.2 * s; c["chest.rz"] = 1.4 * KL([(0, 0)], f)
    c["chest.ry"] = 4 * wave(f, N, 2, 0.1)
    c["neck.rx"] = 4 - 3 * peek; c["head.rx"] = 13 - 12 * peek; c["head.ry"] = 14 - 10 * peek + 2 * wave(f, N, 2, 0.3)
    c["head.rz"] = 8 - 3 * peek + 2 * s
    hands_clasped(c, rig, V(0.0, 0.150 + 0.002 * s, 0.036), wring=wave(f, N, 4, 0.2))
    fingers(c, "L", 38 + 6 * wave(f, N, 4, 0.2)); fingers(c, "R", 62)
    c["aim.stalks"] = V(-0.25, -0.85, 0.45)
    tw = wave(f, N, 2, 0.25)
    stand_feet(rig, c, spread=0.0, pitchR=22 + 4 * tw, fwdR=0.010)
    c["footR.ry"] = 14 * tw
    blink(c, f, N, [12, 40, 79, 84, 108])
    return c


def sheaf_arms(c, rig, w=1.0, bob=0.0):
    """Hands on the sheaf (child of chest; targets in sheaf space): left forearm under the cut ends, right hand round
    the front of the bundle."""
    arm_ik(c, "L", rel(rig, "sheaf", V(0.042, 0.156, 0.050)) + V(0, bob, 0), V(0.9, -0.5, -0.3), "sheaf", w)
    arm_ik(c, "R", rel(rig, "sheaf", V(-0.014, 0.192, 0.082)) + V(0, bob, 0), V(-0.5, -0.85, 0.1), "sheaf", w)
    c["handL.bend"] = -20; c["handL.twist"] = -70
    c["handR.bend"] = 26; c["handR.twist"] = 50
    fingers(c, "L", 40); fingers(c, "R", 52)


R_CARRY = (0.058, 0.62)


@clip("ruth", "carry_walk", 38, True, markers={"contactL": 0, "contactR": 19}, speed=R_CARRY, props=["sheaf"],
      notes="happy walk home with the big sheaf hugged in both arms: leans back a little against its weight, the "
            "bundle bobs with each step (late), chest counter-turns, head peeks to one side of it, a little bounce in "
            "the step; scarf swings")
def ruth_carry_walk(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=R_CARRY[0], lift=0.012, duty=R_CARRY[1], heel=12, toeoff=22)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0040 + 0.0034 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -3 * math.sin(ph - 0.35); c["head.ry"] = 5 + 3 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.5 * math.cos(ph); c["chest.rz"] = -1.0 * math.cos(ph - 0.5); c["head.rz"] = 5 + 1.2 * math.cos(ph - 0.9)
    c["spine.rx"] = -3; c["chest.rx"] += -2; c["head.rx"] = -2 + 1.4 * math.cos(2 * ph - 1.0)
    bob = 0.002 * math.cos(2 * ph - 1.6)
    c["sheaf.ty"] = bob; c["sheaf.rz"] = 1.5 * math.cos(ph - 1.0)
    sheaf_arms(c, rig)
    c["jaw.rx"] = 2
    blink(c, f, N, [24])
    return c


@clip("ruth", "show_bundle", 60, False, markers={"up": 26},
      props=["sheaf"],
      notes="proud: dips (anticipation), lifts the sheaf up and forward to show it, rising onto her toes, chin up and "
            "a beaming tilt; small overshoot, settles holding it high in front of her chest; holds")
def ruth_show_bundle(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.4)
    ant = bump(f, 0, 12)
    up = ease_io((f - 8) / 18)
    over = bump(f, 22, 38)
    settle = ease_io((f - 34) / 18)
    lift = up + 0.15 * over - 0.2 * settle
    c["hips.ty"] = -0.006 * ant + 0.004 * lift
    c["sheaf.ty"] = -0.004 * ant + 0.012 * lift; c["sheaf.tz"] = 0.040 * lift; c["sheaf.tx"] = -0.020 * lift
    c["sheaf.rx"] = 8 * lift; c["sheaf.rz"] = 14 * lift
    sheaf_arms(c, rig)
    c["chest.rx"] += 2 * ant - 5 * lift; c["spine.rx"] = -2 * lift
    c["head.rx"] = 2 * ant - 6 * lift; c["head.rz"] = -8 * lift + 2 * settle; c["head.ry"] = 10 * lift
    toe = 14 * (up - 0.6 * settle) + 6 * over
    stand_feet(rig, c, spread=0.002, pitchL=toe, pitchR=toe)
    c["jaw.rx"] = 3 * lift
    blink(c, f, N, [3, 44], loop=False)
    return c


@clip("ruth", "joy", 72, True, markers={"twirl": 8, "hop": 50},
      notes="dips, twirls once on her toes (arms out, the scarf tail flies out and catches up late), dips again, a "
            "little hop with both hands up, lands softly on bent knees; loops")
def ruth_joy(rig, f, N):
    c = r_base(rig, f, N, cycles=2, amp=0.6)
    tw = ease_io((f - 8) / 30)
    c["root.ry"] = 360.0 * tw if f < N else 0.0
    dip = bump(f, 0, 9) + bump(f, 38, 49)
    hop = max(0.0, math.sin(math.pi * (f - 49) / 13)) if 49 <= f <= 62 else 0.0
    land = bump(f, 61, 71)
    c["hips.ty"] = -0.010 * dip - 0.011 * land + 0.026 * hop + 0.004 * math.sin(math.pi * tw)
    toe = 18 * math.sin(math.pi * tw)
    stand_feet(rig, c, spread=0.0, pitchL=toe + 28 * hop, pitchR=toe + 28 * hop, liftL=0.026 * hop, liftR=0.026 * hop)
    arms_out = math.sin(math.pi * tw)
    arms_up = smooth((f - 44) / 8) * (1 - smooth((f - 64) / 8))
    for side in "LR":
        c[f"upperArm{side}.raise"] = -22 + 48 * arms_out + 115 * arms_up
        c[f"upperArm{side}.bend"] = 8 + 10 * arms_out + 14 * arms_up
        c[f"forearm{side}.bend"] = 26 - 10 * arms_out + 16 * arms_up + 10 * dip
        c[f"hand{side}.bend"] = 6 - 14 * arms_out
        fingers(c, side, 22 - 16 * max(arms_out, arms_up))
    c["head.rx"] = -4 * arms_out - 10 * arms_up + 3 * dip; c["head.rz"] = 6 * arms_out
    c["chest.rx"] += -4 * arms_up + 3 * dip; c["spine.rz"] = -3 * arms_out
    c["jaw.rx"] = 5 * arms_up + 3 * arms_out
    blink(c, f, N, [40])
    return c


@clip("ruth", "ask_humble", 60, False, markers={"ask": 30},
      notes="steps in on the left foot toward Boaz (0.16 away at the S09 marks), small nervous breath, hands clasped "
            "at her chest, a little bow of the chest, head tilted, looking up at him; holds with a slow breath")
def ruth_ask_humble(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.5)
    br = bump(f, 0, 12)
    step = ease_io((f - 6) / 16)
    clasp = ease_io((f - 8) / 18)
    bow = ease_io((f - 20) / 14)
    over = bump(f, 28, 42)
    c["hips.tz"] = 0.014 * step; c["hips.ty"] = 0.002 * br - 0.003 * bow
    c["chest.rx"] += -3 * br + 6 * bow + 1.5 * over; c["spine.rx"] = 3 * bow
    c["shoulderL.raise"] += 2 * br + 2 * clasp; c["shoulderR.raise"] += 2 * br + 2 * clasp
    hands_clasped(c, rig, V(0.0, -0.010, 0.050), w=clasp, space="chest")
    c["handL.bend"] = -16 * clasp; c["handR.bend"] = -16 * clasp
    fingers(c, "L", 22 + 26 * clasp); fingers(c, "R", 22 + 26 * clasp)
    c["head.rx"] = -2 + 4 * bow - 10 * bow; c["neck.rx"] = 6 * bow
    c["head.rz"] = 10 * bow + 2 * over; c["head.ry"] = -3 * bow
    stand_feet(rig, c, spread=0.002, fwdL=0.026 * step, pitchR=0)
    blink(c, f, N, [16, 50], loop=False)
    return c


@clip("ruth", "wave", 48, True,
      notes="waves to the viewer: right hand up by her head, the forearm sways side to side, the wrist and fingers follow "
            "late; body sways and bounces softly on the knees, head tilts; left hand rests at the belt")
def ruth_wave(rig, f, N):
    c = r_base(rig, f, N, cycles=1, amp=0.6)
    ph = 2 * math.pi * f / N
    s = math.sin(2 * ph)
    arm_ik(c, "R", V(-0.084 + 0.020 * s, 0.302 + 0.004 * math.cos(2 * ph), 0.040), V(-0.8, -0.6, -0.2))
    c["handR.bend"] = -10
    c["handR.raise"] = -20 * math.sin(2 * ph - 0.9)
    fingers(c, "R", 4 + 10 * max(0.0, math.sin(2 * ph - 1.6)))
    c["hips.ty"] = -0.004 - 0.003 * math.cos(2 * ph)
    c["hips.tx"] = 0.003 * math.sin(ph); c["hips.rz"] = -1.5 * math.sin(ph)
    c["chest.rz"] = 2.0 * math.sin(ph - 0.4) - 2; c["head.rz"] = 5 * math.sin(ph - 0.8) - 3
    c["head.ry"] = 3 * math.sin(ph - 0.3)
    arm_ik(c, "L", V(0.040, 0.178, 0.036), V(0.9, -0.4, -0.3))
    c["handL.bend"] = 10; fingers(c, "L", 30)
    c["jaw.rx"] = 3
    blink(c, f, N, [20])
    stand_feet(rig, c, spread=0.002)
    return c


# =============================================================================================== NAOMI
# Rest: stooped (baked), right hand a fist round the staff. Unless a clip says otherwise the staff stands on the page
# at her right side and the right wrist is solved to it (`staff.foot` + `staff.dir`, root space).
STAFF_SIDE = (V(-0.080, 0.0, 0.040), V(-0.05, 1.0, -0.14))          # beside her, leaning in a little
STAFF_FRONT = (V(-0.036, 0.0, 0.062), V(0.08, 1.0, -0.22))          # in front: both hands on top


def n_base(rig, f, N, cycles=1, amp=1.0, phase=0.0, staff=STAFF_SIDE):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.8 * b * amp; c["spine.rx"] = -0.8 * b * amp       # inhale lifts the stoop a little
    c["shoulderL.raise"] = 1.3 * b * amp; c["shoulderR.raise"] = 1.3 * b * amp
    c["neck.rx"] = 0.8 * b * amp; c["head.rx"] = -0.6 * b * amp
    c["upperArmL.raise"] = -20; c["upperArmL.bend"] = 8; c["forearmL.bend"] = 30; c["forearmL.twist"] = -10
    c["handL.bend"] = 6; fingers(c, "L", 26)
    if staff is not None:
        staff_at(c, *staff)
        c["pole.armR"] = V(-0.7, -0.5, -0.6)
    return c


def left_on_staff(c, rig, w=1.0, lift=0.0):
    """Left hand cupped over the right fist on top of the staff (target in staff space)."""
    arm_ik(c, "L", V(0.012, 0.024 + lift, 0.004), V(0.9, -0.5, -0.3), "staff", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 30, w); c["handL.twist"] = -40 * w
    fingers(c, "L", lerp(c.get("fingersL.curl", 26), 55, w))


@clip("naomi", "idle", 150, True,
      notes="tired: both hands stacked on the staff planted in front of her, leaning her weight on it; slow deep "
            "stooped breathing (the stoop deepens on each exhale), one long sigh (shoulders rise, hold, fall); "
            "weight shifts onto the staff and back; lifts her head to look round slowly, drops it; heavy slow "
            "blinks; shawl settles")
def naomi_idle(rig, f, N):
    c = n_base(rig, f, N, cycles=3, amp=1.1, staff=STAFF_FRONT)
    sigh = K([(0, 0), (86, 0), (98, 1), (108, 1), (124, -0.4), (140, 0), (150, 0)], f, N, True)
    c["chest.rx"] += -3 * sigh + 2; c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh
    lean = K([(0, 0), (30, 0), (50, 1), (80, 1), (100, 0.3), (150, 0)], f, N, True)
    c["hips.tz"] = -0.004 + 0.004 * lean; c["spine.rx"] += 2 * lean
    sh = K([(0, 0.3), (40, -0.6), (90, -0.6), (120, 0.6), (150, 0.3)], f, N, True)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.8 * sh; c["spine.rz"] = 1.0 * KL([(0, 0.3), (40, -0.6), (90, -0.6), (120, 0.6), (150, 0.3)], f, N, True, lag=8)
    look = [(0, 0), (14, 0), (30, 1), (56, 1), (66, 0.3), (86, 0.3), (96, 0), (150, 0)]
    lk = K(look, f, N, True)
    c["head.rx"] += 3 - 7 * lk + 3 * sigh; c["neck.rx"] += -2 * lk
    c["head.ry"] = 10 * K([(0, 0), (30, 0.8), (56, 0.8), (66, -0.6), (86, -0.6), (96, 0), (150, 0)], f, N, True)
    c["neck.ry"] = 0.4 * c["head.ry"]
    left_on_staff(c, rig)
    fingers(c, "L", 55 + 6 * wave(f, N, 2, 0.4))
    blink(c, f, N, [24, 71, 112, 140], base=1.6, slow=1.7)
    stand_feet(rig, c, spread=0.003, pitchL=K([(0, 0), (40, 0), (52, 5), (90, 5), (100, 0), (150, 0)], f, N, True))
    return c


N_WALK = (0.042, 0.66)


@clip("naomi", "walk_tired", 52, True, markers={"contactL": 0, "contactR": 26, "staffPlant": 2}, speed=N_WALK,
      notes="slow tired shuffle, stooped: short low steps with a heavy drop on each, the head bobs and nods late; the "
            "staff is lifted and set down every other step (planted with the left foot, so it stays still on the "
            "page while it carries weight); the free left arm hangs and swings little; shawl bounces")
def naomi_walk_tired(rig, f, N):
    c = n_base(rig, f, N, cycles=1, amp=0.6, staff=None)
    g = gait(rig, f, N, L=N_WALK[0], lift=0.006, duty=N_WALK[1], heel=6, toeoff=14)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.006 + 0.0028 * math.cos(2 * ph - 0.3)
    c["hips.ry"] = 3 * math.sin(ph); c["chest.ry"] = -2.5 * math.sin(ph - 0.4)
    c["hips.rz"] = 3.0 * math.cos(ph); c["chest.rz"] = -1.4 * math.cos(ph - 0.6); c["head.rz"] = 1.0 * math.cos(ph - 1.0)
    c["spine.rx"] = 3; c["chest.rx"] += 2
    c["head.rx"] = 1 + 2.2 * math.cos(2 * ph - 1.3); c["neck.rx"] = 1 + 1.0 * math.cos(2 * ph - 0.9)
    c["upperArmL.bend"] = 8 - 7 * math.sin(ph - 0.3); c["forearmL.bend"] = 32 - 5 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 5 * math.sin(ph - 1.6)
    # staff: planted while the left foot is in stance (slides back with it), swung forward while the left foot swings
    footL = g["legL"]
    p = footL[3]
    base = V(-0.100, 0.0, 0.0)
    if p < N_WALK[1]:
        z = footL[0].z - rig.head["footL"].z + 0.030
        foot = base + V(0, 0.0, z)
    else:
        s = (p - N_WALK[1]) / (1 - N_WALK[1])
        z = -N_WALK[0] / 2 + N_WALK[0] * smooth(s) + 0.030
        foot = base + V(0, 0.018 * math.sin(math.pi * s), z)
    grip = V(-0.094, 0.145, 0.018 + 0.006 * math.sin(ph))
    staff_at(c, foot, grip - foot)
    c["pole.armR"] = V(-0.7, -0.5, -0.6)
    blink(c, f, N, [31], base=1.5, slow=1.5)
    return c


@clip("naomi", "talk", 96, True,
      notes="talks tiredly and lovingly: right hand on the staff at her side, the left hand makes small palm-up "
            "gestures on the stressed syllables and once touches her chest; head tilts and small shakes; jaw in an "
            "irregular rhythm with pauses (lip sync overrides it); slow blinks")
def naomi_talk(rig, f, N):
    c = n_base(rig, f, N, cycles=2, amp=0.9)
    jk, beats = syllables(N, 53, amp=(4, 11), dur=(3.5, 7.0), gap=0.3)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=10)
    btl = beat_curve(beats, f - 3, N, width=11)
    c["head.rx"] += 2.5 * bt - 1.5 * wave(f, N, 1, 0.2); c["head.ry"] = 4 * wave(f, N, 1, 0.15) + 1.5 * wave(f, N, 3, 0.4)
    c["head.rz"] = 3 * wave(f, N, 1, 0.4)
    ph = K([(0, 0.3), (10, 0.9), (40, 1.0), (50, 0.2), (60, 0.0), (82, 0.0), (90, 0.4), (96, 0.3)], f, N, True)
    chest = K([(0, 0), (50, 0), (58, 1), (80, 1), (88, 0), (96, 0)], f, N, True)
    lift = ph * (0.7 + 0.3 * btl)
    c["upperArmL.raise"] = -20 + 3 * lift; c["upperArmL.bend"] = 8 + 34 * lift
    c["forearmL.bend"] = 30 + 46 * lift; c["forearmL.twist"] = -10 + 75 * lift
    c["handL.bend"] = 6 - 18 * btl * ph; fingers(c, "L", 30 - 20 * btl * ph)
    arm_ik(c, "L", V(0.012, -0.010, 0.046), V(0.8, -0.6, -0.2), "chest", chest)
    c["chest.ry"] = 4 * lift; c["chest.rx"] += 1.2 * bt
    blink(c, f, N, [12, 50, 79], base=1.3, slow=1.4)
    stand_feet(rig, c, spread=0.003)
    return c


@clip("naomi", "sad", 120, True,
      notes="grief: left hand pressed to her chest, head low, a slow 'oh...' sigh (rise, hold, sink deeper), a small "
            "slow head shake, right hand on the staff; heavy slow blinks")
def naomi_sad(rig, f, N):
    c = n_base(rig, f, N, cycles=2, amp=0.9)
    sigh = K([(0, 0), (30, 0), (44, 1), (54, 1), (74, -0.7), (96, -0.3), (120, 0)], f, N, True)
    c["chest.rx"] += 4 - 3 * sigh; c["spine.rx"] += 2 - 1 * sigh
    c["shoulderL.raise"] += 2 + 3 * sigh; c["shoulderR.raise"] += 2 + 3 * sigh
    c["neck.rx"] += 4; c["head.rx"] += 9 - 3 * sigh
    shake = K([(0, 0), (76, 0), (82, -5), (89, 5), (96, -3), (103, 0), (120, 0)], f, N, True)
    c["head.ry"] = shake; c["neck.ry"] = 0.3 * KL([(0, 0), (76, 0), (82, -5), (89, 5), (96, -3), (103, 0), (120, 0)], f, N, True, lag=2)
    c["head.rz"] = 3 + 1.5 * wave(f, N, 1, 0.2)
    arm_ik(c, "L", V(0.014, 0.012 + 0.002 * sigh, 0.046), V(0.8, -0.6, -0.2), "chest")
    c["handL.bend"] = -10; fingers(c, "L", 34)
    blink(c, f, N, [14, 58, 104], base=1.9, slow=1.8)
    stand_feet(rig, c, spread=0.002)
    return c


@clip("naomi", "send_away", 66, False, markers={"go": 26},
      notes="gentle 'go home': a sigh, the left hand rises palm-out toward Ruth (0.12 in front) and pushes softly twice, "
            "head tilted and shaking a little, then the hand sinks halfway and stays offered; right hand on the staff; "
            "holds")
def naomi_send_away(rig, f, N):
    c = n_base(rig, f, N, cycles=1, amp=0.7)
    sigh = bump(f, 0, 16)
    up = ease_io((f - 8) / 14)
    push = bump(f, 20, 30) + 0.7 * bump(f, 32, 44)
    sink = ease_io((f - 46) / 16)
    c["shoulderL.raise"] += 3 * sigh; c["chest.rx"] += -2 * sigh + 2 * up
    tgt = V(0.040, 0.186 - 0.020 * sink, 0.070 + 0.014 * push - 0.012 * sink)
    arm_ik(c, "L", V(0.06, 0.13, 0.02).lerp(tgt, up), V(0.9, -0.5, -0.2), "root", up)
    c["handL.bend"] = -40 * up + 12 * sink; c["handL.twist"] = 20 * up
    fingers(c, "L", 26 - 20 * up)
    c["head.rz"] = 7 * up; c["head.ry"] = K([(0, 0), (22, 0), (28, -4), (36, 4), (44, -2), (54, 0), (66, 0)], f)
    c["head.rx"] += 2 * push
    c["hips.tz"] = 0.003 * push
    blink(c, f, N, [4, 50], loop=False, base=1.3, slow=1.4)
    stand_feet(rig, c, spread=0.002)
    return c


@clip("naomi", "listen_moved", 120, True,
      notes="moved to tears: the left hand at her mouth, head tilting and slowly nodding as she listens, chest "
            "catching in small sobs (irregular), a deep shaky breath, right hand on the staff; slow wet blinks")
def naomi_listen_moved(rig, f, N):
    c = n_base(rig, f, N, cycles=2, amp=1.0)
    sob = pulses(f, N, [(18, 0.9), (24, 0.6), (64, 1.0), (69, 0.5), (100, 0.7)], decay=3.0)
    c["chest.rx"] += -1.6 * sob; c["shoulderL.raise"] += 2.4 * sob; c["shoulderR.raise"] += 2.0 * sob
    nod = K([(0, 0), (30, 0), (40, 1), (52, 0), (80, 0), (88, 0.8), (98, 0), (120, 0)], f, N, True)
    c["head.rx"] += 2 + 4 * nod; c["head.rz"] = 7 + 2 * wave(f, N, 1, 0.3); c["head.ry"] = -3 * wave(f, N, 1, 0.6)
    arm_ik(c, "L", V(0.012, -0.020 + 0.002 * sob, 0.034), V(0.9, -0.5, -0.2), "head")
    c["handL.bend"] = -30; c["handL.twist"] = -10; fingers(c, "L", 40 + 8 * sob)
    blink(c, f, N, [10, 46, 54, 92], base=1.4, slow=2.0)
    stand_feet(rig, c, spread=0.002)
    return c


@clip("naomi", "hug", 90, True,
      notes="arms around Ruth standing 0.122 in front (fitted to ruth_hug at the S02 marks): left arm round her back "
            "under Ruth's arms, the right fist keeps the staff planted at Ruth's side, head resting against Ruth's "
            "shoulder; rocks with Ruth (same phase), a squeeze, deep breaths")
def naomi_hug(rig, f, N):
    c = n_base(rig, f, N, cycles=2, amp=1.2, staff=None)
    s = -hug_sway(f, N)                       # Ruth's +x is Naomi's -x: the same rocking seen from the other side
    sq = bump(f, 40, 62)
    c["hips.tz"] = 0.012; c["spine.rx"] = 3; c["chest.rx"] += 2 + 2 * sq
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -2.0 * s; c["spine.rz"] = 1.2 * s
    c["neck.rx"] = -2; c["head.rx"] = -4; c["neck.ry"] = 8; c["head.ry"] = 22; c["head.rz"] = -9 + 2 * s
    D = HUG_D
    arm_ik(c, "L", V(0.012 + 0.002 * s, 0.176 - 0.004 * sq, D + 0.016), V(1.0, -0.2, -0.1))
    c["handL.bend"] = 16; c["handL.twist"] = -40; fingers(c, "L", 24 + 14 * sq)
    staff_at(c, V(-0.062 + 0.002 * s, 0.0, D - 0.020), V(0.10, 1.0, -0.12))
    c["pole.armR"] = V(-1.0, -0.4, -0.3)
    stand_feet(rig, c, spread=0.003, fwdR=0.010)
    blink(c, f, N, [20, 66], base=1.5, slow=2.0)
    return c


@clip("naomi", "nod", 40, False, markers={"nod": 10},
      notes="a tender 'yes': small breath, two nods (the second smaller), the stoop lifts a little and she smiles, "
            "left hand comes to the right fist on the staff; settles")
def naomi_nod(rig, f, N):
    c = n_base(rig, f, N, cycles=1, amp=0.4)
    nod = K([(0, 0), (4, -2), (10, 9), (16, -1), (22, 6), (28, 0), (40, 0)], f)
    c["head.rx"] += nod; c["neck.rx"] += 0.3 * KL([(0, 0), (4, -2), (10, 9), (16, -1), (22, 6), (28, 0), (40, 0)], f, lag=2)
    lift = ease_io((f - 16) / 18)
    c["chest.rx"] += -3 * lift; c["head.rz"] = 5 * lift
    staff_at(c, *STAFF_FRONT)
    left_on_staff(c, rig, w=ease_io((f - 6) / 20))
    blink(c, f, N, [26], loop=False, base=1.2)
    stand_feet(rig, c, spread=0.003)
    return c


@clip("naomi", "surprised", 45, False, markers={"oh": 9},
      notes="'Oh my!': a quick intake of breath, leans back with a little hop back on the heels, the left hand flies up "
            "open beside her face, the right lifts the staff off the page; eyebrows up (face); small overshoot; holds "
            "with the stoop straighter")
def naomi_surprised(rig, f, N):
    c = n_base(rig, f, N, cycles=1, amp=0.3, staff=None)
    ant = bump(f, 0, 6)
    up = ease_io((f - 3) / 7)
    over = bump(f, 8, 20)
    settle = ease_io((f - 16) / 16)
    v = up + 0.18 * over - 0.15 * settle
    c["hips.tz"] = -0.008 * v; c["hips.ty"] = -0.003 * ant + 0.003 * over
    c["spine.rx"] = -4 * v; c["chest.rx"] += 2 * ant - 9 * v; c["neck.rx"] = -3 * v; c["head.rx"] = -6 * v
    c["shoulderL.raise"] += 5 * v; c["shoulderR.raise"] += 4 * v
    arm_ik(c, "L", V(0.050, 0.150, 0.03).lerp(V(0.060, 0.262, 0.050), v), V(0.9, -0.6, -0.2), "root")
    c["handL.bend"] = -30 * v; c["handL.twist"] = 30 * v; fingers(c, "L", 26 - 24 * v)
    arm_ik(c, "R", V(-0.094, 0.146, 0.020).lerp(V(-0.080, 0.205, 0.058), v), V(-0.9, -0.6, -0.3), "root")
    c["staff.aim"] = V(-0.10, 1.0, 0.10).normalized()
    fingers(c, "R", 0)
    stand_feet(rig, c, spread=0.003, pitchL=-10 * over, pitchR=-10 * over)
    c["jaw.rx"] = 8 * v
    blink(c, f, N, [26], loop=False)
    return c


@clip("naomi", "bless_up", 80, False, markers={"up": 30},
      notes="joy lifts her: hands come to her chest (gathering), then both arms rise to heaven, the staff held high in "
            "the right hand, the stoop straightens, head back, face up; small overshoot and a happy tremble; holds")
def naomi_bless_up(rig, f, N):
    c = n_base(rig, f, N, cycles=1, amp=0.4, staff=None)
    gat = bump(f, 0, 22)
    up = ease_io((f - 14) / 18)
    over = bump(f, 28, 44)
    trem = 0.6 * math.sin(f * 1.9) * ease_io((f - 40) / 10)
    v = up + 0.10 * over
    c["spine.rx"] = -8 * v; c["chest.rx"] += 2 * gat - 14 * v; c["neck.rx"] = -10 * v; c["head.rx"] = -10 * v
    c["hips.ty"] = 0.004 * v
    for side, sx in (("L", 1), ("R", -1)):
        hi = V(0.078 * sx, 0.345 + 0.004 * trem, 0.030)
        chest = V(0.012 * sx, 0.205, 0.052)
        lo = V(0.065 * sx, 0.150, 0.020) if side == "L" else V(-0.094, 0.146, 0.020)
        t1 = lo.lerp(chest, ease_io(f / 12))
        arm_ik(c, side, t1.lerp(hi, v), V(0.9 * sx, -0.6, -0.4))
        c[f"hand{side}.bend"] = -20 * v
        c[f"hand{side}.twist"] = 40 * v * sx
    fingers(c, "L", 26 - 20 * v); fingers(c, "R", 0)
    c["staff.aim"] = V(-0.30, 1.0, 0.05).normalized()
    stand_feet(rig, c, spread=0.003, pitchL=6 * v, pitchR=6 * v)
    c["jaw.rx"] = 6 * v
    blink(c, f, N, [6, 60], loop=False)
    return c


@clip("naomi", "clap", 40, True, markers={"clap1": 7, "clap2": 19, "clap3": 31},
      notes="happy claps in front of her chest (three per loop, the third a touch stronger), bouncing on her knees, "
            "head bobbing and tilting with the beat, the stoop lifted; no staff (hidden in S10)")
def naomi_clap(rig, f, N):
    c = n_base(rig, f, N, cycles=1, amp=0.5, staff=None)
    claps = [7, 19, 31]
    open_ = 1.0
    for cf in claps:
        d = (f - cf) % N
        d = d - N if d > N / 2 else d
        open_ = min(open_, min(1.0, abs(d) / 6.0) ** 0.8)
    hit = sum(math.exp(-((f - cf) % N) / 2.5) for cf in claps if (f - cf) % N < 10)
    c["chest.rx"] += -6 + 1.5 * hit; c["spine.rx"] = -3; c["head.rx"] += -3 + 2 * hit
    c["hips.ty"] = -0.004 + 0.002 * math.cos(2 * math.pi * 3 * f / N)
    c["head.rz"] = 4 * wave(f, N, 1, 0.1); c["head.ry"] = 3 * wave(f, N, 1, 0.3)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(sx * (0.004 + 0.026 * open_), 0.194 + 0.004 * open_, 0.064), V(0.8 * sx, -0.6, -0.3))
        c[f"hand{side}.twist"] = -sx * 70
        c[f"hand{side}.bend"] = -8
        fingers(c, side, 8)
    c["jaw.rx"] = 5
    stand_feet(rig, c, spread=0.003)
    blink(c, f, N, [14])
    return c


@clip("naomi", "hold_baby", 120, True, props=["baby"],
      notes="cradles the baby in both arms (left hand under its head, right forearm under its body), rocking it slowly: "
            "hips and chest sway, the baby rolls a little late; looks down at it tenderly, once up at the viewer with a "
            "smile and back; slow happy blinks; no staff")
def naomi_hold_baby(rig, f, N):
    c = n_base(rig, f, N, cycles=2, amp=0.8, staff=None)
    s = wave(f, N, 2, 0.0)
    sl = wave(f, N, 2, -0.06)
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -1.8 * s; c["spine.rz"] = 1.6 * sl; c["chest.ry"] = 4 * sl
    c["baby.rx"] = 3 * wave(f, N, 2, -0.12); c["baby.ty"] = 0.002 * wave(f, N, 4, 0.1)
    up = K([(0, 0), (60, 0), (70, 1), (86, 1), (96, 0), (120, 0)], f, N, True)
    c["neck.rx"] += 6 - 5 * up; c["head.rx"] += 12 - 16 * up; c["head.rz"] = 6 * sl + 4; c["head.ry"] = 8 - 8 * up
    arm_ik(c, "L", rel(rig, "baby", V(0.052, 0.176, 0.030)), V(0.9, -0.5, -0.4), "baby")
    arm_ik(c, "R", rel(rig, "baby", V(0.002, 0.168, 0.052)), V(-0.9, -0.6, -0.2), "baby")
    c["handL.bend"] = 20; c["handL.twist"] = -60; fingers(c, "L", 30)
    c["handR.bend"] = 16; c["handR.twist"] = 60; fingers(c, "R", 30)
    blink(c, f, N, [22, 98], base=1.3, slow=1.8)
    stand_feet(rig, c, spread=0.003)
    return c


@clip("naomi", "joy", 60, True,
      notes="laughs with her arms open, the stoop lifted: little bounces on her knees, head back on each laugh burst "
            "(irregular), shoulders shake, arms open wider on the bursts; no staff in her hand (hidden at the end)")
def naomi_joy(rig, f, N):
    c = n_base(rig, f, N, cycles=2, amp=0.5, staff=None)
    lf = pulses(f, N, [(4, 1.0), (12, 0.7), (19, 0.5), (34, 1.0), (41, 0.6)], decay=3.0)
    c["chest.rx"] += -8 - 2 * lf; c["spine.rx"] = -4; c["head.rx"] += -6 - 4 * lf; c["neck.rx"] = -3
    c["shoulderL.raise"] += 3 * lf; c["shoulderR.raise"] += 3 * lf
    c["hips.ty"] = -0.003 - 0.002 * math.cos(2 * math.pi * 2 * f / N)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = 14 + 8 * lf; c[f"upperArm{side}.bend"] = 26
        c[f"forearm{side}.bend"] = 40; c[f"forearm{side}.twist"] = sx * -60
        c[f"hand{side}.bend"] = -14; fingers(c, side, 8)
    c["jaw.rx"] = 6 + 6 * lf
    c["head.rz"] = 4 * wave(f, N, 1, 0.2)
    stand_feet(rig, c, spread=0.003)
    blink(c, f, N, [26])
    return c


# =============================================================================================== BOAZ
def b_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -2.0 * b * amp - 1.5; c["spine.rx"] = -0.8 * b * amp
    c["shoulderL.raise"] = 1.4 * b * amp; c["shoulderR.raise"] = 1.4 * b * amp
    c["neck.rx"] = 0.9 * b * amp
    c["upperArmL.raise"] = -18; c["upperArmR.raise"] = -18
    c["upperArmL.bend"] = 8; c["upperArmR.bend"] = 8
    c["forearmL.bend"] = 22; c["forearmR.bend"] = 22
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 26); fingers(c, "R", 26)
    return c


def left_on_sash(c, w=1.0):
    arm_ik(c, "L", V(0.066, -0.054, 0.018), V(0.9, -0.2, -0.6), "chest", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), -6, w); c["handL.twist"] = -30 * w
    fingers(c, "L", lerp(c.get("fingersL.curl", 26), 40, w))


@clip("boaz", "idle", 150, True,
      notes="the content landowner: weight on one leg then the other (hips lead, chest late), left hand resting on his "
            "sash, broad slow breaths; looks over his field, nods to himself; strokes his beard once with the right "
            "hand; blinks; head-cloth and cloak panels settle")
def boaz_idle(rig, f, N):
    c = b_base(rig, f, N, cycles=3, amp=1.0)
    sh = K([(0, 0.7), (50, 0.7), (72, -0.7), (126, -0.7), (150, 0.7)], f, N, True)
    shl = KL([(0, 0.7), (50, 0.7), (72, -0.7), (126, -0.7), (150, 0.7)], f, N, True, lag=8)
    c["hips.tx"] = 0.005 * sh; c["hips.rz"] = -2.6 * sh; c["spine.rz"] = 1.5 * shl; c["chest.rz"] = 1.0 * shl
    c["head.rz"] = -1.2 * shl
    look = [(0, 0), (20, 0), (32, 14), (56, 14), (66, -6), (94, -6), (104, 0), (150, 0)]
    c["neck.ry"] = 0.4 * K(look, f, N, True); c["head.ry"] = 0.6 * KL(look, f, N, True, lag=4)
    nod = K([(0, 0), (40, 0), (44, 4), (48, 0), (52, 3), (56, 0), (150, 0)], f, N, True)
    c["head.rx"] = -1 + nod
    left_on_sash(c)
    stroke = ease_io((f - 96) / 10) * (1 - ease_io((f - 128) / 12))
    if stroke > 0:
        arm_ik(c, "R", V(-0.004, -0.050 - 0.008 * bump(f, 106, 126), 0.030), V(-0.9, -0.6, -0.3), "head", stroke)
        c["handR.bend"] = -20 * stroke; fingers(c, "R", 26 + 14 * stroke)
    c["head.rx"] += -4 * stroke
    blink(c, f, N, [17, 66, 73, 130])
    stand_feet(rig, c, spread=0.004, pitchR=K([(0, 0), (60, 0), (74, 5), (124, 5), (140, 0), (150, 0)], f, N, True))
    return c


B_WALK = (0.084, 0.58)


@clip("boaz", "walk", 34, True, markers={"contactL": 0, "contactR": 17}, speed=B_WALK,
      notes="confident easy stride: chest out, a strong heel strike and a solid hip bob, shoulders counter-turn, arms "
            "swing freely with late forearms; the open robe's front panels swing with the legs and lag the turns; "
            "head-cloth bounces")
def boaz_walk(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=B_WALK[0], lift=0.014, duty=B_WALK[1], heel=14, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.005 + 0.0036 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -7 * math.sin(ph - 0.3); c["head.ry"] = 4 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.2 * math.cos(ph); c["chest.rz"] = -1.4 * math.cos(ph - 0.5)
    c["chest.rx"] += -2; c["head.rx"] = -2 + 1.5 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 8 - 20 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 20 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 24 - 10 * math.sin(ph - 1.0); c["forearmR.bend"] = 24 + 10 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 8 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 8 * math.sin(ph - 1.6)
    c["cloakL.rx"] = 9 * math.sin(ph - 0.6); c["cloakR.rx"] = -9 * math.sin(ph - 0.6)
    blink(c, f, N, [22])
    return c


@clip("boaz", "talk", 96, True,
      notes="hearty talk: jaw in an irregular rhythm (lip sync overrides it); both hands gesture in turn (right "
            "palm-up out to the side, left open in front), nods and a head tilt on the stressed syllables, chest "
            "out; weight shift; blinks")
def boaz_talk(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.9)
    jk, beats = syllables(N, 77, amp=(6, 14))
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=9); btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -2 + 3.5 * bt; c["head.ry"] = 5 * wave(f, N, 1, 0.2) + 2 * wave(f, N, 3, 0.1)
    c["head.rz"] = 3 * wave(f, N, 1, 0.5)
    pa = K([(0, 0.2), (8, 1.0), (40, 0.9), (50, 0.2), (96, 0.2)], f, N, True)
    pb = K([(0, 0.1), (44, 0.1), (54, 1.0), (86, 0.9), (94, 0.1), (96, 0.1)], f, N, True)
    for side, p, sx in (("R", pa, -1), ("L", pb, 1)):
        lift = p * (0.75 + 0.25 * btl)
        c[f"upperArm{side}.raise"] = -18 + 8 * lift; c[f"upperArm{side}.bend"] = 8 + 36 * lift
        c[f"forearm{side}.bend"] = 22 + 50 * lift; c[f"forearm{side}.twist"] = (10 - 80 * lift) * (-sx)
        c[f"hand{side}.bend"] = 6 - 20 * btl * p
        fingers(c, side, 30 - 24 * btl * p)
    c["chest.ry"] = -4 * pa + 4 * pb
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh
    blink(c, f, N, [9, 63])
    stand_feet(rig, c, spread=0.004)
    return c


@clip("boaz", "greet", 48, False, markers={"hail": 16},
      notes="'Good morning, everyone!': a breath and a small dip, the right arm swings up high with an open hand "
            "(hail), chest out, a big smile; the hand gives one small wave at the top; holds the arm raised; left "
            "hand on the sash")
def boaz_greet(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.5)
    ant = bump(f, 0, 10)
    up = ease_io((f - 6) / 12)
    over = bump(f, 14, 26)
    wv = math.sin(math.pi * (f - 22) / 7) * bump(f, 22, 36) if f > 22 else 0.0
    c["hips.ty"] = -0.004 * ant; c["chest.rx"] += 3 * ant - 5 * up; c["chest.ry"] = -5 * up
    c["head.rx"] = -2 + 2 * ant - 6 * up; c["head.rz"] = -4 * up
    hi = V(-0.098, 0.405 + 0.006 * over, 0.040)
    arm_ik(c, "R", V(-0.11, 0.17, 0.0).lerp(hi, up), V(-0.9, -0.6, -0.2), "root", min(1.0, 0.2 + 1.2 * up))
    c["handR.bend"] = -8; c["handR.raise"] = 16 * wv; c["handR.twist"] = 10 * up
    fingers(c, "R", 26 - 22 * up)
    left_on_sash(c, w=ease_io(f / 14))
    c["jaw.rx"] = 6 * up - 3 * ease_io((f - 34) / 10)
    stand_feet(rig, c, spread=0.004, fwdL=0.010 * up)
    blink(c, f, N, [30], loop=False)
    return c


@clip("boaz", "look_curious", 90, True,
      notes="'Hm? Who's that?': right hand shading his eyes, leaning forward and a little to the right, head tilted, "
            "peering with small adjustments (lean in, hold, tilt the other way, hold), left hand on his hip; a slow "
            "curious blink")
def boaz_look_curious(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.7)
    pe = K([(0, 0), (20, 1), (42, 1), (52, 0.5), (74, 0.6), (90, 0)], f, N, True)
    tl = K([(0, 1), (40, 1), (52, -0.6), (78, -0.6), (90, 1)], f, N, True)
    c["hips.tz"] = 0.006 + 0.004 * pe; c["spine.rx"] = 4 + 4 * pe; c["chest.rx"] += 3 + 3 * pe
    c["spine.rz"] = -3; c["chest.rz"] = -2
    c["neck.rx"] = 2 + 3 * pe; c["head.rx"] = -2 + 2 * pe; c["head.rz"] = 8 * tl; c["head.ry"] = -4 + 3 * tl
    arm_ik(c, "R", V(-0.026, 0.024, 0.034), V(-0.9, -0.4, -0.3), "head")
    c["handR.bend"] = -10; c["handR.twist"] = -70; fingers(c, "R", 10)
    arm_ik(c, "L", V(0.070, 0.200, 0.010), V(0.9, -0.2, -0.6))
    c["handL.bend"] = -30; c["handL.twist"] = -60; fingers(c, "L", 50)
    blink(c, f, N, [33, 80], slow=1.4)
    stand_feet(rig, c, spread=0.004, fwdR=0.016, pitchL=4 * pe)
    return c


@clip("boaz", "talk_kind", 96, True,
      notes="fatherly: both forearms forward with open palms up, unhurried; on a phrase the right hand sweeps out to "
            "his right (toward the water jars), the head tilts, slow nods with the stressed syllables; a warm lean "
            "in; jaw rhythm slower (lip sync overrides it); blinks")
def boaz_talk_kind(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.8)
    jk, beats = syllables(N, 91, amp=(5, 12), dur=(4.0, 7.5), gap=0.3)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=11)
    sweep = K([(0, 0), (40, 0), (50, 1), (66, 1), (76, 0), (96, 0)], f, N, True)
    c["hips.tz"] = 0.004; c["spine.rx"] = 2; c["chest.rx"] += 2
    c["head.rx"] = 1 + 3 * bt; c["head.rz"] = 5 + 2 * wave(f, N, 1, 0.3) - 6 * sweep; c["head.ry"] = -8 * sweep
    for side, sx in (("L", 1), ("R", -1)):
        sw = sweep if side == "R" else 0.0
        tgt = V(0.050 * sx, 0.192 + 0.006 * bt, 0.074 - 0.004 * bt).lerp(V(-0.140, 0.205, 0.060), sw)
        arm_ik(c, side, tgt, V(0.9 * sx, -0.7, -0.2))
        c[f"hand{side}.twist"] = -sx * 70; c[f"hand{side}.bend"] = -14 - 6 * bt
        fingers(c, side, 14 + 6 * (1 - bt))
    c["chest.ry"] = -6 * sweep
    blink(c, f, N, [14, 58, 88], slow=1.2)
    stand_feet(rig, c, spread=0.004)
    return c


@clip("boaz", "hand_on_heart", 56, False, markers={"heart": 22},
      notes="moved and warm: a breath, the right hand comes to his heart (left side of the chest), a small bow of the "
            "head and chest with a gentle overshoot, then straightens a little with a smile; left hand on the sash; "
            "holds")
def boaz_hand_on_heart(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.6)
    br = bump(f, 0, 12)
    hand = ease_io((f - 4) / 16)
    bow = ease_io((f - 16) / 12) - 0.5 * ease_io((f - 34) / 16)
    c["chest.rx"] += -3 * br + 7 * bow; c["spine.rx"] = 3 * bow
    c["neck.rx"] = 4 * bow; c["head.rx"] = 9 * bow; c["head.rz"] = 5 * hand
    arm_ik(c, "R", V(0.018, -0.006, 0.054), V(-0.9, -0.6, -0.2), "chest", hand)
    c["handR.bend"] = -14 * hand; c["handR.twist"] = 20 * hand; fingers(c, "R", 26 - 8 * hand)
    left_on_sash(c)
    blink(c, f, N, [24, 46], loop=False, slow=1.3)
    stand_feet(rig, c, spread=0.004)
    return c


@clip("boaz", "sneaky_drop", 136, False, markers={"left": 14, "right": 40, "grin": 64, "drop": 104},
      props=["stalks"],
      notes="comic beat: the big handful in his right fist; shoulders up, a sly glance to his LEFT (leans, holds), a "
            "quick glance to his RIGHT (holds), back to the viewer with a cheeky grin, left finger to the lips (shh) "
            "and a bounce on his toes; the right hand slides behind his back and at `drop` (3.47 s) the fingers spring "
            "open with a wrist flick; then he looks up all innocent, rocking on his heels; holds with the open hand "
            "behind his back. Hide boaz/stalks + play stalks_fall at `drop`")
def boaz_sneaky_drop(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.6)
    sneak = ease_io(f / 10) * (1 - 0.6 * ease_io((f - 106) / 12))
    c["shoulderL.raise"] += 5 * sneak; c["shoulderR.raise"] += 5 * sneak
    c["spine.rx"] = 4 * sneak; c["chest.rx"] += 3 * sneak; c["neck.rx"] = 3 * sneak
    look = [(0, 0), (6, -3), (14, 26), (30, 26), (34, 24), (40, -28), (54, -28), (60, 0), (100, 0), (136, 0)]
    c["head.ry"] = K(look, f); c["neck.ry"] = 0.35 * KL(look, f, lag=2); c["chest.ry"] = 0.15 * KL(look, f, lag=4)
    c["spine.rz"] = -0.06 * KL(look, f, lag=3)
    c["hips.tx"] = 0.004 * K([(0, 0), (14, 1), (30, 1), (40, -1), (54, -1), (60, 0), (136, 0)], f)
    grin = ease_io((f - 58) / 8) * (1 - ease_io((f - 96) / 10))
    c["head.rz"] = 8 * grin + 4 * bump(f, 104, 120)
    bounce = bump(f, 64, 72) + bump(f, 74, 82)
    c["hips.ty"] = 0.004 * bounce - 0.002 * sneak
    shh = ease_io((f - 60) / 8) * (1 - ease_io((f - 92) / 10))
    left_on_sash(c, w=1 - shh)
    if shh > 0:
        arm_ik(c, "L", V(0.002, -0.042, 0.050), V(0.9, -0.7, -0.2), "head", shh)
        c["handL.bend"] = -30 * shh; c["handL.twist"] = -20 * shh; fingers(c, "L", 40)
    # right fist: at his side, slides behind his back (f 80-100), opens at the drop with a flick
    back = ease_io((f - 80) / 18)
    side_ = V(-0.122, 0.165, 0.010)
    behind = V(-0.040, 0.196, -0.068)
    arm_ik(c, "R", side_.lerp(behind, back) + V(0, 0.010 * bump(f, 102, 110), 0), V(-0.9, -0.2, 0.6), "root", 0.6 + 0.4 * back)
    c["handR.bend"] = 14 * back + 24 * bump(f, 102, 112); c["handR.twist"] = 0
    fingers(c, "R", 70 - 66 * ease_io((f - 103) / 3))
    inno = ease_io((f - 110) / 10)
    c["head.rx"] = -2 - 12 * inno + 2 * sneak; c["head.ry"] += 6 * inno
    rock = math.sin((f - 112) / 30 * 2 * math.pi) * inno
    stand_feet(rig, c, spread=0.004, pitchL=-8 * max(0, rock) + 8 * max(0, -rock) + 10 * bounce,
               pitchR=-8 * max(0, rock) + 8 * max(0, -rock) + 10 * bounce)
    c["jaw.rx"] = 2 * grin
    blink(c, f, N, [20, 47, 86, 122], loop=False)
    return c


@clip("boaz", "chuckle", 60, False, markers={"heh": 8},
      notes="'Heh heh': the left hand to his belly, the right hand comes round from behind his back, shoulders shake "
            "in uneven bursts (heh-heh-heh, fading), head tips back a little and bobs, eyes crinkle (lids lower); "
            "settles into a contented smile; holds")
def boaz_chuckle(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.4)
    lf = pulses(f, N, [(8, 1.0), (14, 0.85), (20, 0.7), (27, 0.5), (36, 0.3)], decay=2.4, loop=False)
    c["shoulderL.raise"] += 4 * lf; c["shoulderR.raise"] += 4 * lf; c["chest.rx"] += -2 * lf
    c["head.rx"] = -4 - 3 * lf; c["head.rz"] = 4 + 1.5 * lf
    arm_ik(c, "L", V(0.020, -0.060, 0.064), V(0.9, -0.6, -0.2), "chest", ease_io(f / 10))
    c["handL.bend"] = -8; fingers(c, "L", 30)
    back = 1 - ease_io((f - 2) / 18)
    arm_ik(c, "R", V(-0.040, 0.196, -0.068), V(-0.9, -0.2, 0.6), "root", back)
    fingers(c, "R", lerp(26, 4, back))
    c["jaw.rx"] = 3 + 6 * lf
    c["hips.ty"] = -0.002 * lf
    blink(c, f, N, [44], loop=False, base=1.0 + 2.5 * min(1.0, lf))
    stand_feet(rig, c, spread=0.004)
    return c


@clip("boaz", "listen", 120, True,
      notes="listens kindly: leans in a little with a head tilt, hands loosely together in front, small 'mm' nods at "
            "irregular times, one slow tilt to the other side, weight shift; slow blinks")
def boaz_listen(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.8)
    nod = K([(0, 0), (20, 0), (24, 4), (28, 0), (32, 2.5), (36, 0), (70, 0), (75, 5), (81, 0), (120, 0)], f, N, True)
    tl = K([(0, 1), (48, 1), (60, -0.4), (96, -0.4), (110, 1), (120, 1)], f, N, True)
    c["hips.tz"] = 0.003; c["spine.rx"] = 2; c["chest.rx"] += 2
    c["head.rx"] = 2 + nod; c["head.rz"] = 6 * tl; c["head.ry"] = 2 * tl
    arm_ik(c, "L", V(0.016, 0.180, 0.050), V(0.8, -0.6, -0.4))
    arm_ik(c, "R", V(-0.008, 0.176, 0.054), V(-0.8, -0.6, -0.4))
    fingers(c, "L", 40); fingers(c, "R", 44)
    sh = K([(0, 0.6), (60, 0.6), (80, -0.6), (110, -0.6), (120, 0.6)], f, N, True)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2.0 * sh
    blink(c, f, N, [10, 64, 100], slow=1.4)
    stand_feet(rig, c, spread=0.004)
    return c


@clip("boaz", "joy", 60, True,
      notes="laughs out loud with his arms flung open: bursts that throw his head back (irregular), arms opening wider "
            "on each, bouncing on his knees, cloak panels and head-cloth swinging")
def boaz_joy(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.5)
    lf = pulses(f, N, [(3, 1.0), (10, 0.7), (16, 0.5), (32, 1.0), (39, 0.7), (46, 0.4)], decay=3.0)
    c["chest.rx"] += -5 - 3 * lf; c["head.rx"] = -6 - 6 * lf; c["neck.rx"] = -2
    c["hips.ty"] = -0.004 - 0.003 * math.cos(2 * math.pi * 2 * f / N)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = 30 + 12 * lf; c[f"upperArm{side}.bend"] = 20
        c[f"forearm{side}.bend"] = 30; c[f"forearm{side}.twist"] = sx * -60
        c[f"hand{side}.bend"] = -16; fingers(c, side, 6)
    c["jaw.rx"] = 8 + 6 * lf
    c["head.rz"] = 3 * wave(f, N, 1, 0.3)
    stand_feet(rig, c, spread=0.005)
    blink(c, f, N, [24])
    return c


@clip("boaz", "wave", 48, True,
      notes="a big friendly wave: right hand up by his head, the forearm sways, the wrist follows late; body rocks, "
            "head tilts; left hand on the sash")
def boaz_wave(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.6)
    ph = 2 * math.pi * f / N
    s = math.sin(2 * ph)
    arm_ik(c, "R", V(-0.110 + 0.026 * s, 0.368 + 0.005 * math.cos(2 * ph), 0.042), V(-0.8, -0.6, -0.2))
    c["handR.bend"] = -10; c["handR.raise"] = -20 * math.sin(2 * ph - 0.9)
    fingers(c, "R", 4 + 10 * max(0.0, math.sin(2 * ph - 1.6)))
    c["hips.tx"] = 0.003 * math.sin(ph); c["hips.rz"] = -1.5 * math.sin(ph); c["hips.ty"] = -0.003 - 0.002 * math.cos(2 * ph)
    c["chest.rz"] = 2 * math.sin(ph - 0.4) - 2; c["head.rz"] = 4 * math.sin(ph - 0.8) - 3
    left_on_sash(c)
    c["jaw.rx"] = 4
    blink(c, f, N, [30])
    stand_feet(rig, c, spread=0.004)
    return c


# =============================================================================================== evaluation
HAND_SPACES = ("staff", "handL", "handR", "stalks")


def evaluate_primary(rig, clip_, f):
    chs = clip_.fn(rig, f, clip_.N)
    basis = rig.basis_from(chs)
    M = rig.fk(basis)
    for limb in ("legL", "legR"):
        ik_limb(rig, basis, M, chs, limb)
    late = []
    for limb in ("armL", "armR"):
        if limb == "armR" and rig.staff_foot is not None:
            continue                                    # Naomi's right arm: solved with the staff below
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
    "ruth": [(("scarf1", "scarf2"), 75.0, 7.5, 0.30, 30.0),
             (("stalks",), 200.0, 10.0, 0.0, 5.0)],
    "naomi": [(("shawl1", "shawl2"), 70.0, 8.0, 0.30, 24.0)],
    "boaz": [(("headcloth",), 90.0, 8.5, 0.30, 22.0),
             (("cloakL",), 80.0, 7.0, 0.22, 16.0), (("cloakR",), 80.0, 7.0, 0.22, 16.0),
             (("stalks",), 180.0, 9.0, 0.0, 6.0)],
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


# =============================================================================================== scene helpers
def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rigs = {ch: Rig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    return sc, rigs


def contract_clips():
    return {"ruth": ["idle", "walk", "talk", "sad", "shake_head", "hold_hands", "hug", "cheer_up", "glean", "stand_up",
                     "bow_kneel", "shy", "carry_walk", "show_bundle", "joy", "ask_humble", "wave"],
            "naomi": ["idle", "walk_tired", "talk", "sad", "send_away", "listen_moved", "hug", "nod", "surprised",
                      "bless_up", "clap", "hold_baby", "joy"],
            "boaz": ["idle", "walk", "talk", "greet", "look_curious", "talk_kind", "hand_on_heart", "sneaky_drop",
                     "chuckle", "listen", "joy", "wave"]}


PROPS = ("sheaf", "stalks", "baby", "staff")


def hidden_props(rig, cl):
    """Prop meshes not posed for in this clip (left out of the checks and the renders)."""
    out = []
    for p in PROPS:
        nm = f"{rig.ch}_{p}"
        if nm in bpy.data.objects:
            want = p in cl.props or (p == "staff" and cl.name not in NAOMI_NO_STAFF)
            if not want:
                out.append(nm)
    return out


NAOMI_NO_STAFF = {"clap", "hold_baby", "joy"}


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
    if min(lows) < -0.004:
        out["meshMinAt"] = low_at
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
    if rig.staff_foot is not None and cl.name not in NAOMI_NO_STAFF:
        ys = [rig.foot_of_staff(M).y for _, M in frames]
        out["staffFootY"] = [round(min(ys), 4), round(max(ys), 4)]
    reset_pose(rig)
    rig.obj.location, rig.obj.rotation_euler = loc0, rot0
    if ad:
        ad.action = keep
    return out


SAMPLE_BONES = ("head", "jaw", "handR", "handL", "footL", "toeR", "hips", "scarf2", "shawl2", "headcloth", "cloakL",
                "staff", "sheaf", "baby", "stalks")


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    req = TL.get("requestedClips") or []
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl, "requestedClips": req,
            "stage": {"hugDistance": HUG_D, "cheerDistance": CHEER_D, "askDistance": ASK_D, "talkKindDistance": TALK_D,
                      "kneel": KNEEL["ruth"]},
            "naomiNoStaffClips": sorted(NAOMI_NO_STAFF)}
    only = os.environ.get("RU_ONLY")
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
        if cl.name == "joy" and cl.ch == "ruth":
            info["rootSpin"] = "root bone turns 360 deg about Y during the twirl (no translation)"
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        print("RU_CHECK", cl.action, json.dumps(info["checks"]))
        meta["clips"].append(info)
        print(f"RU_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} root={info['rootMaxOffset']}")
    if only:
        print("RU_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "ru_anim.blend")
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
        print("RU_EXPORT", ch)
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("RU_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


# ----------------------------------------------------------------------------------------------- render helpers
REGIONS = json.load(open(os.path.join(MODEL, "regions_characters.json")))
FACES = json.load(open(FACES_JSON))
DECAL_NODES = {}


def set_expression(ch, clip_name):
    expr = FACES[ch]["clips"].get(clip_name, FACES[ch]["default"])
    if ch == "ruth" and clip_name == "kneel":
        expr = "calm"
    p = os.path.join(FACE_DIR, f"{ch}_{expr}.png")
    if not os.path.exists(p):
        p = os.path.join(FACE_DIR, f"{ch}_{FACES[ch]['default']}.png")
    DECAL_NODES[ch].image = bpy.data.images.load(p, check_existing=True)


def stage_of(cl):
    """Where a clip is shown in renders: (x, z, yaw). Open ground in front of the field / house."""
    if cl.ch == "ruth" and cl.name in ("glean", "kneel", "stand_up", "bow_kneel"):
        return (0.14, 0.10, 0.0)
    if cl.ch == "ruth":
        return (-0.06, 0.10, 0.0)
    if cl.ch == "naomi":
        return (-0.22, 0.12, 0.0)
    return (0.30, 0.13, 0.0)


PAIRS = [  # contact-sheet pair rows: (A action, B action, distance, label)
    ("ruth_hug", "naomi_hug", HUG_D, "pair: ruth_hug + naomi_hug (0.122)"),
    ("ruth_hold_hands", "naomi_listen_moved", HUG_D, "pair: hold_hands + listen_moved (0.122)"),
    ("ruth_cheer_up", "naomi_sad", CHEER_D, "pair: cheer_up + naomi_sad (0.126)"),
]


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
            view_cam(cam, rig, mark, "q3", dist_k=1.2)
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("RU_CONTACT_ROW", cl.action, picks, flush=True)
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
    """RU_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'pair:<actionA>:<actionB>:<dist>:<frame>[:view]' renders two actors facing each other at that distance."""
    sc, rigs = open_scene()
    res = int(os.environ.get("RU_PROBE_RES", "440"))
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
    for item in os.environ.get("RU_PROBE", "").split(";"):
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
            apply_basis(rig, fr_[fr][0]); place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, view, bone, dist_k=float(os.environ.get("RU_PROBE_DIST", "1.25")))
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("RU_PROBE", len(out))


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get("RU_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
