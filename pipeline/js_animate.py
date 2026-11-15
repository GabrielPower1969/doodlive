"""Joseph skeletal animation (Animation role, story pack `joseph`).

Built on the shared kit (pipeline/story_kit/animation.py) the same way as pipeline/ru_animate.py. Two halves in one file:

* Under Blender (headless) it opens `assets/joseph/model/characters.blend` (Characters role's rigs, read fresh every
  run), builds every clip of docs/joseph/CONTRACT.md §4 as an action `<char>_<clip>` and exports
  `assets/joseph/anim/{joseph,jacob,brother,pharaoh}.glb` (character + skin + one glTF animation per action) and
  `clips.json`. The skinned coat mesh is nested under its `coat` joint after export, as the model GLB does.
* Under plain python3 it orchestrates the Blender runs, composes the contact sheet and prints the staging check.

    python3 pipeline/js_animate.py all        # build + verify + contact sheet + staging
    python3 pipeline/js_animate.py build      # actions + GLBs + anim/clips.json (with checks)
    python3 pipeline/js_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build
    python3 pipeline/js_animate.py contact    # anim/contact_sheet.png (key poses per clip, on the twolands set)
    python3 pipeline/js_animate.py staging    # timeline moves vs. clip speeds (python only, no Blender)
    JS_PROBE="joseph_twirl:0,20:front" python3 pipeline/js_animate.py probe        # $JS_ANIM_WORK/probe.png
    JS_PROBE="pair:joseph_hug:brother_hug:0.115:30" python3 pipeline/js_animate.py probe
    JS_PROBE="pair:joseph_lift_up:brother_stand_up:0.11:60:front,q3:24" ...   # last field: B starts 24 f later
    JS_SHOW=joseph_coat  (probe/contact: force a prop mesh visible, e.g. the coat in clips where the story hides it)
    JS_ONLY=joseph_hug,jacob_  (with build: bake + check a subset, no export)
    python3 pipeline/js_animate.py paircheck  # body-into-body depth of every two-person clip at its distance

How the motion is made: as Ruth (see pipeline/ru_animate.py). Each clip is a function frame -> channels in DESIGN axes
(x = the character's left, y up, z = where he faces); legs and arms by two-bone IK; Jacob's stick is solved like
Naomi's staff (its foot planted on the page); secondary motion (coat panels, shawl, bag, apron, belly) is damped
spring chains on top. Joseph's coat panels also follow the thighs (sitting, bowing) so the tunic stays inside.
Two-person clips are fitted to a partner standing D in front (constants below), facing back.
Intermediates: $JS_ANIM_WORK (default /tmp/joseph_anim/work).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
JS = os.path.join(ROOT, "assets/joseph")
MODEL = os.path.join(JS, "model")
ANIM = os.path.join(JS, "anim")
BLEND = os.path.join(MODEL, "characters.blend")
SET_GLB = os.path.join(MODEL, "twolands.glb")
TIMELINE = os.path.join(JS, "timeline.json")
FACE_DIR = os.path.join(ROOT, "docs/joseph/design/faces")
WORK = os.environ.get("JS_ANIM_WORK") or "/tmp/joseph_anim/work"
ENV = "JS_"
BLENDER = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
FPS = 30
CHARS = ("joseph", "jacob", "brother", "pharaoh")

# distances the two-person clips are fitted to (CONTRACT §4: 0.11, give_coat / crown_him 0.12)
HUG_D = 0.115        # joseph_hug, brother_hug, jacob_hug (works 0.11-0.12)
GRAB_D = 0.11        # brother_grab_coat
LIFT_D = 0.115       # joseph_lift_up + brother_stand_up (stand_up starts 24 f = 0.8 s after lift_up, story S10)
LIFT_LAG = 24
GIVE_D = 0.12        # jacob_give_coat
CROWN_D = 0.12       # pharaoh_crown_him

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


# =============================================================================================== orchestration (python3)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                      # noqa: E402
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "animation")   # shared animation functions (docs/STORY-KIT.md)

# 3D eyes pilot (pipeline/js_characters.py E3, JS_EYES3D=0 = off): Joseph's blinks come from the runtime
# (DGFace3D.cs: random intervals, a blink on big gaze shifts). His clips keep only the held lid level of `blink`
# (heavy / half-shut lids) and explicit eyes-closed holds (`eyelids.sy` = 12, e.g. the hug); the runtime reads the
# `eyelids` bone as a lid closure. Every other character keeps its baked blinks.
RUNTIME_BLINK = {"joseph"} if os.environ.get("JS_EYES3D", "1") != "0" else set()
_KIT_BLINK = blink
_BLINK_OWNER = [None]


def blink(c, f, N, at, loop=True, base=1.0, slow=1.0):
    if _BLINK_OWNER[0] in RUNTIME_BLINK:
        c["eyelids.sy"] = base
        return
    _KIT_BLINK(c, f, N, at, loop=loop, base=base, slow=slow)


def compose_contact():
    from PIL import Image, ImageDraw, ImageFont
    meta = json.load(open(os.path.join(WORK, "contact", "contact.json")))
    cell, pad, lab = 150, 5, 34
    rows = meta["rows"]
    ncol = max(len(r["frames"]) for r in rows)
    W = 250 + ncol * (cell + pad) + pad
    H = 60 + len(rows) * (cell + lab + pad)
    sheet = Image.new("RGB", (W, H), (250, 246, 236))
    d = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 16)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 12)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((pad, 14), "Joseph - key poses per clip (30 fps; frame / seconds; markers in red; pair rows = two actors at "
                      "their fitted distance, B offset in frames)", fill=(40, 30, 20), font=font)
    y = 60
    for r in rows:
        d.text((pad, y + 6), r["action"], fill=(40, 30, 20), font=font)
        d.text((pad, y + 30), f"{r['frames_total']} f  {r['frames_total'] / FPS:.2f} s", fill=(90, 80, 70), font=small)
        d.text((pad, y + 46), "loop" if r["loop"] else "one-shot (holds last)", fill=(90, 80, 70), font=small)
        if r.get("look"):
            d.text((pad, y + 62), "look: " + r["look"], fill=(90, 80, 70), font=small)
        x = 250
        for fr in r["frames"]:
            im = Image.open(os.path.join(WORK, "contact", fr["file"])).convert("RGB").resize((cell, cell))
            sheet.paste(im, (x, y))
            d.text((x + 4, y + cell + 2), f"f{fr['f']}  {fr['f'] / FPS:.2f}s", fill=(60, 50, 40), font=small)
            if fr.get("marker"):
                d.text((x + 4, y + cell + 16), fr["marker"], fill=(200, 30, 30), font=small)
            x += cell + pad
        y += cell + lab + pad
    out = os.path.join(ANIM, "contact_sheet.png")
    sheet = sheet.quantize(colors=255, method=Image.Quantize.MEDIANCUT)
    sheet.save(out, optimize=True)
    print("JS_CONTACT", out, sheet.size)


def staging():
    """Every move in the timeline: distance, clip, time to the actor's next beat, the clip's natural speed and the
    factor the director would need. Flags glides (a `to` on a non-travel clip) and > 1.6x."""
    tl = json.load(open(TIMELINE))
    meta = json.load(open(os.path.join(ANIM, "clips.json")))
    sp = {c["action"]: c.get("naturalSpeed") for c in meta["clips"]}
    pos, rows, out = {}, tl["acting"], []
    for i, a in enumerate(rows):
        if "to" not in a:
            continue
        p0 = pos.get(a["who"], tuple(a["to"])); p1 = tuple(a["to"]); pos[a["who"]] = p1
        d = math.dist(p0, p1)
        if a["t"] <= 0.01 or d < 1e-4 or a.get("snap"):      # snap = placed at once (a cut), not a move
            continue
        nxt = next((b["t"] for b in rows[i + 1:] if b["who"] == a["who"]), tl["duration"])
        avail = nxt - a["t"]
        v = sp.get(f"{a['who']}_{a['clip']}")
        row = {"t": round(a["t"], 2), "who": a["who"], "clip": a["clip"], "from": list(p0), "to": list(p1),
               "dist": round(d, 3), "avail": round(avail, 2)}
        if not v:
            row["flag"] = "GLIDE (no travel clip)"
        else:
            row["natural"] = v
            row["needSec"] = round(d / v, 2)
            row["factor"] = round(d / v / max(avail, 1e-3), 2)
            if row["factor"] > 1.6:
                row["flag"] = "TOO FAST (> 1.6x)"
        out.append(row)
        print("JS_STAGING", json.dumps(row))
    json.dump(out, open(os.path.join(WORK, "staging.json"), "w"), indent=1)
    return out


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    os.makedirs(WORK, exist_ok=True); os.makedirs(ANIM, exist_ok=True)
    if mode in ("build", "all"):
        run_blender("build")
    if mode in ("verify", "all"):
        run_blender("verify")
    if mode in ("contact", "all"):
        run_blender("contact"); compose_contact()
    if mode in ("staging", "all"):
        staging()
    if mode == "probe":
        run_blender("probe"); compose_probe()
    if mode == "paircheck":
        run_blender("paircheck")
    if mode == "compose":
        compose_contact()


if not IN_BLENDER:
    if __name__ == "__main__":
        main()
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
STICK = "stick"                                          # Jacob's walking stick (solved like Naomi's staff)


# =============================================================================================== rig model (pure python FK)
class Rig:
    H_OF = {"joseph": 0.34, "jacob": 0.33, "brother": 0.38, "pharaoh": 0.40}

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
        self.prop_axis = {}
        if STICK in self.names:
            # the stick's foot (lowest vertex of jacob_stick in the rest pose) in the stick bone's local frame
            o = bpy.data.objects.get(f"{ch}_{STICK}")
            mw = obj.matrix_world.inverted() @ o.matrix_world
            low = min((mw @ v.co for v in o.data.vertices), key=lambda p: p.z)
            self.staff_foot = self.rest[STICK].inverted() @ low
            self.staff_len = (to_d(low) - self.head[STICK]).length
            self.prop_axis[STICK] = (self.rest[STICK].inverted().to_3x3() @ (low - self.rest[STICK].translation)).normalized() * -1

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
        return to_d(M[STICK] @ self.staff_foot)


class Clip:
    def __init__(self, ch, name, N, loop, fn, markers=None, notes="", extra=False, speed=None, props=None, look=None):
        self.ch, self.name, self.N, self.loop, self.fn = ch, name, N, loop, fn
        self.markers = markers or {}
        self.notes = notes
        self.extra = extra
        self.speed = speed           # (stride L, duty) for in-place locomotion -> natural speed
        self.props = props or []
        self.look = look             # joseph: which props the clip is shown with in renders ("coat" / "plain" / "governor")

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


def staff_solve(rig, basis, M, chs):
    """Kit's staff_solve with the bone named STICK (Jacob's stick): plant its foot at chs['staff.foot'] (root space)
    along chs['staff.dir'] by iterating the right wrist target."""
    if rig.staff_foot is None:
        return
    if "staff.foot" not in chs:
        if "ik.armR" in chs:
            ik_limb(rig, basis, M, chs, "armR")
        if "staff.aim" in chs:
            aim_prop(rig, basis, M, STICK, chs["staff.aim"])
        return
    Mroot = M["root"] @ rig.rest["root"].inverted()
    foot = Vector(chs["staff.foot"]); d = Vector(chs["staff.dir"]).normalized()
    want = to_d(Mroot @ to_bl(foot))
    target = Vector(chs["ik.armR"]) if "ik.armR" in chs else foot + d * (rig.staff_len + 0.004) + V(0.008, 0.004, -0.006)
    ch2 = {"ikspace.armR": "root", "ikw.armR": 1.0, "pole.armR": chs.get("pole.armR", V(-0.7, -0.5, -0.6))}
    for _ in range(8):
        ch2["ik.armR"] = target
        ik_limb(rig, basis, M, ch2, "armR")
        aim_prop(rig, basis, M, STICK, d)
        err = rig.foot_of_staff(M) - want
        if err.length < 2e-5:
            break
        target = target - (CI @ (Mroot.to_3x3().inverted() @ (C @ err)))
    chs["ik.armR"] = target


def pivot_dz(rig, side, pitch):
    """Ankle z shift that keeps the touching point (heel when the toes are up, ball / tip when the heel is up) where
    it stood."""
    if abs(pitch) < 1e-6:
        return 0.0
    R = rot_d((1, 0, 0), pitch)
    P = min(foot_points(rig, side), key=lambda q: (CI @ (R @ (C @ q))).y)     # the point that touches the page
    return P.z - (CI @ (R @ (C @ P))).z


def stand_feet(rig, chs, spread=0.0, fwdL=0.0, fwdR=0.0, pitchL=0.0, pitchR=0.0, liftL=0.0, liftR=0.0, fwd=0.0, xL=0.0, xR=0.0):
    """Kit stand_feet, plus: a foot that rises on its toes pivots about the ball (no slide of the planted ball)."""
    for side, fw, pt, lf, xo in (("L", fwdL, pitchL, liftL, xL), ("R", fwdR, pitchR, liftR, xR)):
        b = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        dz = pivot_dz(rig, side, pt) if lf <= 0 else 0.0
        chs[f"ik.leg{side}"] = V(b.x + sx * spread + xo, planted_ankle_y(rig, side, pt) + lf, b.z + fw + fwd + dz)
        chs[f"foot{side}.pitch"] = pt


def gait(rig, f, N, L, lift, duty, offsetR=0.5, offsetL=0.0, heel=10.0, toeoff=24.0, out=None, lift_shape=1.0,
         spread=0.0, fwd=0.0):
    """Kit gait, plus: in stance the foot rolls about its heel (heel strike) and its ball (toe-off), so the point that
    touches the page moves at exactly the stance speed (no skating while the foot rolls)."""
    out = out if out is not None else {}
    for side, off in (("L", offsetL), ("R", offsetR)):
        p = (f / N + off) % 1.0
        base = rig.head["foot" + side]
        sx = 1 if side == "L" else -1
        if p < duty:
            s = p / duty
            pitch = -heel * (1 - smooth(s / 0.15)) + toeoff * smooth((s - 0.7) / 0.3)
            z = L / 2 - L * s + pivot_dz(rig, side, pitch)
            y = planted_ankle_y(rig, side, pitch)
            contact = True
        else:
            s = (p - duty) / (1 - duty)
            z0 = -L / 2 + pivot_dz(rig, side, toeoff); z1 = L / 2 + pivot_dz(rig, side, -heel)
            z = lerp(z0, z1, smooth(s))
            pitch = lerp(toeoff, -heel, smooth(s * 1.1))
            y = planted_ankle_y(rig, side, pitch) + lift * math.sin(math.pi * min(1.0, s)) ** lift_shape
            contact = False
        out["leg" + side] = (V(base.x + sx * spread, y, base.z + z + fwd), pitch, contact, p)
    return out


def stepping(f, a, b, dist, h=0.016):
    """A foot step between frames a and b: (forward offset, lift)."""
    t = ease_io((f - a) / max(1e-6, b - a))
    return dist * t, h * math.sin(math.pi * min(1.0, max(0.0, (f - a) / max(1e-6, b - a))))


def arm_mix(c, side, tA, spaceA, tB, spaceB, mix, pole, w=1.0):
    """Arm IK toward a blend of two targets in different spaces (resolved to root space after the body FK)."""
    c[f"ik.arm{side}"] = Vector(tA); c[f"ikspace.arm{side}"] = "root"; c[f"ikw.arm{side}"] = w
    c[f"ikmix.arm{side}"] = (Vector(tA), spaceA, Vector(tB), spaceB, min(1.0, max(0.0, mix)))
    c[f"pole.arm{side}"] = Vector(pole)


def root_point(rig, M, t, space):
    Mroot = M["root"] @ rig.rest["root"].inverted()
    if space in M and space != "root":
        w = M[space] @ (rig.rest[space].inverted() @ to_bl(rig.head[space] + Vector(t)))
    else:
        w = Mroot @ to_bl(Vector(t))
    return to_d(Mroot.inverted() @ w)


def partner(p, D):
    """A point given in the partner's root space (partner D in front, facing back) -> own root space."""
    return V(-p[0], p[1], D - p[2])


def hips_to(rig, c, y, z, x=0.0):
    """Hip joint to an absolute root-space height / depth (offsets from the rest hips)."""
    h = rig.head["hips"]
    c["hips.tx"] = c.get("hips.tx", 0.0) + x
    c["hips.ty"] = y - h.y
    c["hips.tz"] = z - h.z


def seat_legs(rig, c, ankleL, ankleR, pitch=0.0, w=1.0, pole_up=0.6):
    """Blend both ankles from standing (w 0) to the given root-space ankle points (seated / crouched), knees forward."""
    for side, a in (("L", ankleL), ("R", ankleR)):
        b = rig.head["foot" + side]
        st = V(b.x, planted_ankle_y(rig, side, 0), b.z)
        tgt = st.lerp(Vector(a), w)
        c[f"ik.leg{side}"] = tgt
        c[f"foot{side}.pitch"] = pitch * w
        sx = 1 if side == "L" else -1
        c[f"pole.leg{side}"] = V(0.12 * sx, pole_up, 1)


# kneels: knees on the page (kit kneel_geom). Brother bows low with his knees a little behind his mark so his head
# stays clear of the person he bows to (0.11-0.13 in front).
KNEEL = {"brother": dict(KY=0.029, kz=-0.032, thigh_back=48.0, shin_slope=8.0, spread=0.004)}
SEAT_Y = {"joseph": 0.030, "brother": 0.034}          # hip joint height when sitting on the page


def hands_clasped(c, rig, at, wring=0.0, w=1.0, space="root"):
    """Both hands loosely together at `at` (root space unless space given)."""
    arm_ik(c, "L", at + V(0.011 + 0.002 * wring, 0.000, -0.004), V(0.7, -0.6, -0.4), space, w)
    arm_ik(c, "R", at + V(-0.011 + 0.002 * wring, -0.004, 0.000), V(-0.7, -0.6, -0.4), space, w)


def mouth(c, f, N, seed, amp=(5, 12), gap=0.25, loop=True):
    jk, beats = syllables(N, seed, amp=amp, gap=gap)
    c["jaw.rx"] = jaw_from(jk, f, N)
    return beats


# =============================================================================================== JOSEPH
# Rest: A-pose (arms 55 deg below horizontal), coat on (sleeves skinned to the arms). Young, light, quick.
def jo_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.4 * b * amp; c["spine.rx"] = -0.5 * b * amp
    c["shoulderL.raise"] = 1.0 * b * amp; c["shoulderR.raise"] = 1.0 * b * amp
    c["neck.rx"] = 0.6 * b * amp
    c["upperArmL.raise"] = -18; c["upperArmR.raise"] = -18
    c["upperArmL.bend"] = 6; c["upperArmR.bend"] = 6
    c["forearmL.bend"] = 22; c["forearmR.bend"] = 22
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 20); fingers(c, "R", 20)
    c["head.rx"] = -3
    return c


@clip("joseph", "idle", 150, True, look="coat",
      notes="light on his feet: rises onto his toes twice (a happy little bounce), weight L -> R, looks round (left, up "
            "at the sky, right) with the head leading and the chest late, the left hand once smooths the coat on his "
            "chest; bright blinks; coat panels swing")
def joseph_idle(rig, f, N):
    c = jo_base(rig, f, N, cycles=3, amp=0.9)
    sh = K([(0, 0.6), (30, 0.6), (50, -0.8), (96, -0.8), (118, 0.6), (150, 0.6)], f, N, True)
    shl = KL([(0, 0.6), (30, 0.6), (50, -0.8), (96, -0.8), (118, 0.6), (150, 0.6)], f, N, True, lag=6)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2.2 * sh; c["spine.rz"] = 1.3 * shl; c["chest.rz"] = 0.8 * shl
    c["head.rz"] = -1.2 * shl
    toes = bump(f, 8, 22) + 0.8 * bump(f, 22, 34) + 0.7 * bump(f, 100, 114)
    c["hips.ty"] = -0.0015 + 0.006 * toes - 0.0012 * abs(sh)
    look = [(0, 0), (36, 0), (46, 16), (66, 16), (72, 2), (90, 2), (102, -14), (124, -14), (134, 0), (150, 0)]
    up = K([(0, 0), (66, 0), (74, 1), (90, 1), (98, 0), (150, 0)], f, N, True)
    c["neck.ry"] = 0.4 * K(look, f, N, True); c["head.ry"] = 0.6 * KL(look, f, N, True, lag=3)
    c["chest.ry"] = 0.15 * KL(look, f, N, True, lag=6)
    c["head.rx"] += -12 * up + 2 * toes; c["neck.rx"] += -4 * up
    smooth_coat = ease_io((f - 108) / 14) * (1 - ease_io((f - 132) / 14))
    arm_ik(c, "L", V(0.016, -0.012 - 0.012 * bump(f, 118, 132), 0.040), V(0.8, -0.6, -0.2), "chest", smooth_coat)
    c["handL.bend"] = 6 - 18 * smooth_coat
    for s_ in "LR":
        c[f"upperArm{s_}.raise"] += 4 * toes
        c[f"forearm{s_}.bend"] += 6 * toes
    fingers(c, "L", 20 - 8 * smooth_coat); fingers(c, "R", 22 + 4 * wave(f, N, 2, 0.3))
    pt = 16 * toes
    stand_feet(rig, c, spread=0.002, pitchL=pt, pitchR=pt)
    c["jaw.rx"] = 1.5
    blink(c, f, N, [20, 61, 67, 128])
    return c


@clip("joseph", "talk", 96, True, look="coat",
      notes="jaw in an irregular syllable rhythm (lip sync overrides it); nods on the stressed syllables; the right "
            "hand opens palm-up toward the listener in the first phrase, both hands spread a little in the second; "
            "weight shift; two blinks")
def joseph_talk(rig, f, N):
    c = jo_base(rig, f, N, cycles=2, amp=0.8)
    beats = mouth(c, f, N, 41, amp=(5, 13))
    bt = beat_curve(beats, f, N, width=9); btl = beat_curve(beats, f - 3, N, width=10)
    c["head.rx"] = -3 + 3.5 * bt - 1.0 * wave(f, N, 1, 0.2)
    c["head.ry"] = 6 * wave(f, N, 1, 0.1) + 2 * wave(f, N, 3, 0.4); c["head.rz"] = 3 * wave(f, N, 1, 0.35)
    pa = K([(0, 0.2), (10, 0.9), (40, 1.0), (52, 0.1), (88, 0.1), (96, 0.2)], f, N, True)
    pb = K([(0, 0.0), (46, 0.0), (58, 1.0), (84, 0.9), (94, 0.0), (96, 0.0)], f, N, True)
    lift = pa * (0.75 + 0.25 * btl)
    c["upperArmR.bend"] = 6 + 38 * lift; c["forearmR.bend"] = 22 + 52 * lift; c["forearmR.twist"] = 10 - 80 * lift
    c["handR.bend"] = 6 - 22 * btl * pa; fingers(c, "R", 26 - 20 * btl * pa)
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{s_}.raise"] += 14 * pb
        c[f"forearm{s_}.bend"] += 30 * pb
        c[f"forearm{s_}.twist"] += -60 * pb * sx
    c["chest.ry"] = -4 * lift; c["chest.rx"] += 1.5 * bt
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh; c["spine.rz"] = 0.9 * sh
    blink(c, f, N, [7, 61])
    stand_feet(rig, c, spread=0.002)
    return c


J_WALK = (0.072, 0.60)


@clip("joseph", "walk", 32, True, markers={"contactL": 0, "contactR": 16}, speed=J_WALK, look="coat",
      notes="light young walk, ~112 steps/min: springy hip bob, chest counter-turn, arms swing with lagging forearms, "
            "head steady with a small nod per step; coat panels swing late")
def joseph_walk(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=J_WALK[0], lift=0.012, duty=J_WALK[1], heel=12, toeoff=24)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0040 + 0.0032 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -6 * math.sin(ph - 0.35); c["head.ry"] = 3 * math.sin(ph - 0.7)
    c["hips.rz"] = 2.4 * math.cos(ph); c["chest.rz"] = -1.4 * math.cos(ph - 0.5); c["head.rz"] = 0.8 * math.cos(ph - 0.9)
    c["spine.rx"] = 2; c["head.rx"] = -4 + 1.4 * math.cos(2 * ph - 1.0)
    c["upperArmL.bend"] = 6 - 18 * math.sin(ph - 0.25); c["upperArmR.bend"] = 6 + 18 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 26 - 10 * math.sin(ph - 1.0); c["forearmR.bend"] = 26 + 10 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 9 * math.sin(ph - 1.6); c["handR.bend"] = 6 + 9 * math.sin(ph - 1.6)
    blink(c, f, N, [25])
    return c


J_RUN = (0.130, 0.38)


@clip("joseph", "run", 22, True, markers={"contactL": 0, "contactR": 11}, speed=J_RUN, look="governor",
      notes="eager run to his father: leaning forward, both arms out wide and forward (ready to hug), a flight phase "
            "with a bounce on every step, head up and beaming; coat / collar bounce")
def joseph_run(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=J_RUN[0], lift=0.022, duty=J_RUN[1], heel=8, toeoff=34, lift_shape=0.8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.006 + 0.007 * math.cos(2 * ph - 0.9)
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -7 * math.sin(ph - 0.35)
    c["hips.rz"] = 2.0 * math.cos(ph); c["spine.rx"] = 9; c["chest.rx"] += 4
    c["neck.rx"] = -6; c["head.rx"] = -8 + 2.5 * math.cos(2 * ph - 1.2)
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{s_}.raise"] = 34 + 5 * math.cos(2 * ph - 0.8)
        c[f"upperArm{s_}.bend"] = 34 - 10 * sx * math.sin(ph - 0.3)
        c[f"forearm{s_}.bend"] = 26 + 6 * math.cos(2 * ph - 1.4)
        c[f"forearm{s_}.twist"] = -40 * sx
        c[f"hand{s_}.bend"] = -6
        fingers(c, s_, 8)
    c["jaw.rx"] = 6
    blink(c, f, N, [14])
    return c


J_SAD = (0.046, 0.64)


@clip("joseph", "walk_sad", 44, True, markers={"contactL": 0, "contactR": 22}, speed=J_SAD, look="plain",
      notes="led away: slow heavy steps, head down, shoulders forward, wrists together low in front (as if tied); a "
            "look back over the shoulder once per two steps... (small), slow blinks")
def joseph_walk_sad(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.6)
    g = gait(rig, f, N, L=J_SAD[0], lift=0.008, duty=J_SAD[1], heel=6, toeoff=14)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.005 + 0.0026 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 3 * math.sin(ph); c["chest.ry"] = -2.5 * math.sin(ph - 0.4)
    c["hips.rz"] = 2.4 * math.cos(ph); c["chest.rz"] = -1.0 * math.cos(ph - 0.6)
    c["spine.rx"] = 4; c["chest.rx"] += 6
    c["shoulderL.swing"] = 5; c["shoulderR.swing"] = 5
    c["neck.rx"] = 8; c["head.rx"] = 16 + 2.0 * math.cos(2 * ph - 1.3); c["head.rz"] = 1.0 * math.cos(ph - 1.0)
    hands_clasped(c, rig, V(0.0, 0.128 + 0.003 * math.cos(2 * ph - 1.2), 0.036))
    c["handL.twist"] = -20; c["handR.twist"] = 20
    fingers(c, "L", 34); fingers(c, "R", 38)
    blink(c, f, N, [30], base=1.6, slow=1.6)
    return c


@clip("joseph", "twirl", 60, False, markers={"spin": 10, "front": 40}, look="coat",
      notes="dips, then spins once on his toes to show the coat, arms out (palms up), the coat panels flaring out and "
            "catching up late; lands softly facing front with the arms open and a proud little chin-up; holds. The "
            "root bone turns 360 deg about Y (no translation), like ruth_joy")
def joseph_twirl(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.4)
    tw = ease_io((f - 9) / 31)
    c["root.ry"] = 360.0 * tw
    spin = math.sin(math.pi * tw)                     # spin speed, 0 at the ends
    dip = bump(f, 0, 11) + 0.8 * bump(f, 38, 50)
    settle = ease_io((f - 42) / 14)
    c["hips.ty"] = -0.009 * dip + 0.006 * spin
    toe = 22 * spin
    stand_feet(rig, c, spread=0.0, pitchL=toe, pitchR=toe)
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{s_}.raise"] = -18 + 62 * spin + 46 * settle * (1 - spin)
        c[f"upperArm{s_}.bend"] = 6 + 8 * spin + 18 * settle
        c[f"forearm{s_}.bend"] = 22 - 12 * spin + 8 * settle + 8 * dip
        c[f"forearm{s_}.twist"] = -sx * (10 + 70 * max(spin, settle))
        c[f"hand{s_}.bend"] = 6 - 16 * max(spin, settle)
        fingers(c, s_, 20 - 14 * max(spin, settle))
    c["coat.follow"] = 0.85 - 0.75 * spin
    flare = 26 * spin + 6 * bump(f, 40, 54)
    c["coatL.rz"] = flare; c["coatR.rz"] = -flare
    c["coatL.rx"] = -10 * spin; c["coatR.rx"] = -10 * spin
    c["head.rx"] = -4 - 6 * spin - 6 * settle + 4 * dip; c["head.rz"] = 6 * spin - 3 * settle
    c["chest.rx"] += -4 * settle + 2 * dip; c["spine.rz"] = -3 * spin
    c["jaw.rx"] = 4 * spin + 3 * settle
    blink(c, f, N, [4, 52], loop=False)
    return c


@clip("joseph", "tell_dream", 150, True, look="coat",
      notes="acts the dream out, eager: ties a bundle (the hands circle round each other in front of his belly, then "
            "pull the knot tight with a jerk), then both hands go up flat like standing sheaves and bow forward twice "
            "(wrists fold, the head bows with them), a bounce on the toes; jaw talks throughout (lip sync overrides it)")
def joseph_tell_dream(rig, f, N):
    c = jo_base(rig, f, N, cycles=2, amp=0.8)
    beats = mouth(c, f, N, 77, amp=(5, 13), gap=0.18)
    bt = beat_curve(beats, f, N, width=9)
    tie = K([(0, 1), (50, 1), (60, 0), (136, 0), (148, 1), (150, 1)], f, N, True)
    sheaf = K([(0, 0), (54, 0), (66, 1), (130, 1), (144, 0), (150, 0)], f, N, True)
    # tying: two circles of the hands round each other, then the knot pulled tight
    a = 2 * math.pi * f / 20.0
    roll = V(0.010 * math.cos(a), 0.010 * math.sin(a), 0)
    pull = bump(f, 42, 52)
    centre = V(0.0, 0.150, 0.050)
    tL = centre + V(0.012 + 0.030 * pull, 0, 0) + roll
    tR = centre + V(-0.012 - 0.030 * pull, 0, 0) - roll
    # sheaves: forearms up, hands flat, two bows (wrists fold forward), the second deeper
    bow = bump(f, 78, 94) + 1.2 * bump(f, 104, 124)
    sL = V(0.052, 0.238 + 0.008 * bump(f, 66, 76) - 0.018 * bow, 0.070 + 0.016 * bow)
    sR = V(-0.052, 0.238 + 0.008 * bump(f, 66, 76) - 0.018 * bow, 0.070 + 0.016 * bow)
    w_s = sheaf
    m = sheaf / max(1e-6, tie + sheaf)
    w = min(1.0, 1.5 * (tie + sheaf))
    arm_mix(c, "L", tL, "root", sL, "root", m, V(0.85, -0.55, -0.25), w)
    arm_mix(c, "R", tR, "root", sR, "root", m, V(-0.85, -0.55, -0.25), w)
    c["handL.twist"] = -20 * w_s; c["handR.twist"] = 20 * w_s
    c["handL.bend"] = 10 * (1 - m) + (-30 + 70 * bow) * w_s; c["handR.bend"] = 10 * (1 - m) + (-30 + 70 * bow) * w_s
    fingers(c, "L", (40 + 20 * pull) * (1 - m) + 4 * m); fingers(c, "R", (40 + 20 * pull) * (1 - m) + 4 * m)
    c["head.rx"] = -3 + 3 * bt + 10 * bow * sheaf + 6 * tie * (1 - pull) - 4 * pull
    c["chest.rx"] += 4 * bow * sheaf + 3 * tie; c["spine.rx"] = 2 * tie
    c["head.ry"] = 5 * wave(f, N, 1, 0.2); c["head.rz"] = 4 * wave(f, N, 1, 0.5)
    toes = 0.8 * bump(f, 64, 74) + 0.6 * bump(f, 126, 138)
    c["hips.ty"] = 0.004 * toes - 0.002 * tie
    stand_feet(rig, c, spread=0.002, pitchL=12 * toes, pitchR=12 * toes)
    blink(c, f, N, [30, 98, 140])
    return c


@clip("joseph", "in_pit", 96, False, markers={"sit": 40}, look="plain",
      notes="pushed: the body recoils, a stumbling step back with the arms flung up, he drops down to sit on the floor "
            "of the well (knees up, it is narrow), looks round scared, then reaches one arm (right) up high toward the "
            "rim, the other hand on the ground; holds reaching. Fits inside the well's 0.07 radius at the PIT mark")
def joseph_in_pit(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.4)
    rec = bump(f, 0, 16)
    step = ease_io((f - 4) / 8)
    down = ease_io((f - 16) / 22)
    land = bump(f, 36, 46)
    reach = ease_io((f - 58) / 18)
    # legs: right foot steps back, then both feet come forward and the hips drop onto the page
    seat = SEAT_Y["joseph"]
    hy = rig.head["hips"].y
    hips_y = lerp(hy - 0.002 * rec, seat, down) - 0.003 * land
    hips_z = lerp(-0.010 * step, -0.030, down)
    hips_to(rig, c, hips_y, hips_z)
    zR, hR = stepping(f, 3, 12, -0.024)
    stand_feet(rig, c, spread=0.002, fwdR=zR * (1 - down), liftR=hR)
    aL = V(0.026, planted_ankle_y(rig, "L", 0) + 0.002, 0.040)
    aR = V(-0.024, planted_ankle_y(rig, "R", 0) + 0.002, 0.034)
    if down > 0:
        lift = 0.022 * math.sin(math.pi * min(1.0, down * 1.3))
        for s_, a in (("L", aL), ("R", aR)):
            st = Vector(c[f"ik.leg{s_}"])
            t_ = st.lerp(a, down); t_.y += lift
            c[f"ik.leg{s_}"] = t_
            c[f"pole.leg{s_}"] = V(0.15 if s_ == "L" else -0.15, 0.7, 1)
            c[f"foot{s_}.pitch"] = 0
    c["hips.rx"] = -10 * down
    c["spine.rx"] = -6 * rec + 10 * down - 2 * land; c["chest.rx"] += -6 * rec + 6 * down - 4 * reach
    # arms: flung up in the stumble, then hands to the ground beside him, then the right arm reaches up
    fl = rec + 0.6 * bump(f, 10, 30)
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{s_}.raise"] = -18 + 60 * fl
        c[f"forearm{s_}.bend"] = 22 + 40 * fl
    gL = V(0.042, 0.038, -0.026 + 0.008 * land)       # inside the well (inner radius 0.07 round the PIT mark)
    arm_ik(c, "L", gL, V(0.9, 0.2, -0.4), "root", down)
    c["handL.bend"] = -50 * down; fingers(c, "L", 10)
    gR0 = V(-0.046, 0.032, -0.018)
    gR1 = V(-0.040, 0.300, 0.040)
    look = bump(f, 44, 66)
    tR = gR0.lerp(gR1, reach) + V(0.004 * math.sin(f * 0.6) * reach, 0.006 * bump(f, 76, 90), 0)
    arm_ik(c, "R", tR, V(-0.9, -0.2, -0.3), "root", down)
    c["handR.bend"] = -20 * reach; fingers(c, "R", 14 + 30 * bump(f, 78, 92))
    c["head.rx"] = -4 - 8 * rec + 6 * down - 26 * reach
    c["head.ry"] = 24 * look - 14 * bump(f, 58, 70) - 6 * reach; c["neck.rx"] = -10 * reach
    c["head.rz"] = 8 * reach
    c["jaw.rx"] = 6 * rec + 4 * reach
    blink(c, f, N, [24, 48], loop=False)
    return c


J_CARRY = (0.060, 0.62)


@clip("joseph", "carry_work", 38, True, markers={"contactL": 0, "contactR": 19}, speed=J_CARRY, look="plain",
      notes="a servant at work: walks carrying a (mimed) water jar on his right shoulder, the right hand up by his ear "
            "steadying it, elbow out, head tilted away from it; the left arm swings; steady honest steps with a dip under "
            "the weight; no prop (the jar is the pose)")
def joseph_carry_work(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=J_CARRY[0], lift=0.010, duty=J_CARRY[1], heel=10, toeoff=20)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0050 + 0.0030 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -3 * math.sin(ph - 0.35)
    c["hips.rz"] = 2.4 * math.cos(ph); c["spine.rz"] = 3; c["chest.rz"] = 3 - 1.0 * math.cos(ph - 0.5)
    c["head.rz"] = -9 + 1.0 * math.cos(ph - 0.9); c["head.rx"] = -2 + 1.2 * math.cos(2 * ph - 1.0)
    jar = 0.002 * math.cos(2 * ph - 1.2)
    arm_ik(c, "R", V(-0.052, 0.292 + jar, 0.006), V(-0.9, 0.3, -0.3), "root")
    c["handR.bend"] = -30; c["handR.twist"] = 60; fingers(c, "R", 50)
    c["shoulderR.raise"] = 8
    c["upperArmL.bend"] = 6 - 16 * math.sin(ph - 0.25); c["forearmL.bend"] = 26 - 10 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 9 * math.sin(ph - 1.6)
    blink(c, f, N, [27])
    return c


@clip("joseph", "sit_cell", 90, False, markers={"seated": 26, "up": 64}, look="plain",
      notes="sits down on the cell's bench behind him (top h 0.062, front edge 0.025 behind his mark), leans forward with "
            "the elbows on his knees and the hands loosely together, head hanging; a sigh; then he lifts his head and "
            "looks up (trusting); holds")
def joseph_sit_cell(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.5)
    down = ease_io((f - 4) / 20)
    land = bump(f, 22, 32)
    lean = ease_io((f - 24) / 18)
    sigh = bump(f, 40, 58)
    up = ease_io((f - 56) / 16)
    hy = rig.head["hips"].y
    hips_to(rig, c, lerp(hy, 0.083, down) - 0.002 * land, lerp(0.0, -0.046, down))
    zL, hL = stepping(f, 6, 16, 0.028); zR, hR = stepping(f, 12, 22, 0.022)
    stand_feet(rig, c, spread=0.004, fwdL=zL, fwdR=zR, liftL=hL, liftR=hR)
    c["pole.legL"] = V(0.12, 0.3, 1); c["pole.legR"] = V(-0.12, 0.3, 1)
    c["hips.rx"] = 6 * down + 10 * lean
    c["spine.rx"] = 14 * lean + 4 * sigh - 6 * up; c["chest.rx"] += 14 * lean - 4 * sigh - 4 * up
    c["shoulderL.raise"] += 3 * sigh; c["shoulderR.raise"] += 3 * sigh
    hw = ease_io((f - 26) / 16)
    hands_clasped(c, rig, V(0.0, 0.100 + 0.004 * sigh, 0.072), w=hw)
    fingers(c, "L", 30); fingers(c, "R", 34)
    c["neck.rx"] = 10 * lean - 16 * up; c["head.rx"] = -3 + 14 * lean - 26 * up
    c["head.rz"] = 4 * up
    blink(c, f, N, [14, 50, 80], loop=False, base=1.3, slow=1.4)
    return c


@clip("joseph", "bow_point_up", 80, False, markers={"bow": 22, "point": 54}, look="plain",
      notes="humble before the king: right hand to his chest, a respectful bow from the waist; then he straightens and "
            "lifts the right hand high to point up to heaven, the head following it up; the left hand open at his side; "
            "holds pointing")
def joseph_bow_point_up(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.4)
    br = bump(f, 0, 10)
    bow = ease_io((f - 6) / 14) * (1 - ease_io((f - 34) / 14))
    up = ease_io((f - 38) / 16)
    over = bump(f, 50, 62)
    c["hips.tz"] = -0.008 * bow
    c["hips.rx"] = 10 * bow; c["spine.rx"] = 14 * bow; c["chest.rx"] += 10 * bow - 2 * br - 3 * up
    c["neck.rx"] = 6 * bow; c["head.rx"] = -3 + 12 * bow - 20 * up - 4 * over
    hand = ease_io((f - 4) / 12)
    pt = V(-0.050, 0.420 + 0.010 * over, 0.040)
    arm_mix(c, "R", V(-0.012, -0.004, 0.044), "chest", pt, "root", up, V(-0.8, -0.5, -0.25), hand)
    c["handR.bend"] = -10 - 10 * up
    fingers(c, "R", 20 + 34 * up)
    c["upperArmL.raise"] = -18 + 14 * up; c["forearmL.bend"] = 22 + 20 * up; c["forearmL.twist"] = -10 + 60 * up
    fingers(c, "L", 20 - 10 * up)
    c["head.ry"] = -6 * up; c["head.rz"] = 3 * up
    stand_feet(rig, c, spread=0.002)
    blink(c, f, N, [3, 36, 70], loop=False)
    return c


@clip("joseph", "explain", 120, True, look="plain",
      notes="a kind teacher: counts on his fingers (the right hand taps three fingers of the open left hand, a nod on "
            "each), then opens both palms out to the listener, then brings them back; jaw talks (lip sync overrides it)")
def joseph_explain(rig, f, N):
    c = jo_base(rig, f, N, cycles=2, amp=0.8)
    beats = mouth(c, f, N, 19, amp=(5, 12))
    bt = beat_curve(beats, f, N, width=9)
    count = K([(0, 0.9), (6, 1), (52, 1), (62, 0), (102, 0), (114, 0.9), (120, 0.9)], f, N, True)
    open_ = K([(0, 0), (56, 0), (68, 1), (96, 1), (108, 0), (120, 0)], f, N, True)
    taps = [14, 28, 42]
    tap = max(bump(f, t - 4, t + 5) for t in taps)
    k = sum(1 for t in taps if f >= t - 5) - 1
    k = max(0, min(2, k))
    left_hand = V(0.030, 0.178, 0.064)
    arm_ik(c, "L", left_hand, V(0.9, -0.5, -0.3), "root", count)
    c["handL.twist"] = -70 * count; c["handL.bend"] = -24 * count
    tip = left_hand + V(-0.010 + 0.007 * k, 0.026 + 0.004 * tap, 0.012)
    arm_ik(c, "R", tip + V(-0.018, 0.004, 0.0) + V(0, 0.010 * (1 - tap), 0.004 * (1 - tap)), V(-0.9, -0.6, -0.2), "root", count)
    c["handR.bend"] = 26 * count; fingers(c, "R", 40 * count)
    fingers(c, "L", 8 * count)
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{s_}.raise"] += 22 * open_
        c[f"upperArm{s_}.bend"] += 36 * open_
        c[f"forearm{s_}.bend"] += 40 * open_
        c[f"forearm{s_}.twist"] += -sx * 80 * open_
        c[f"hand{s_}.bend"] = c.get(f"hand{s_}.bend", 0) - 14 * open_
    c["head.rx"] = -3 + 4 * tap * count + 3 * bt * (1 - count); c["head.ry"] = -6 * count + 4 * wave(f, N, 1, 0.6)
    c["head.rz"] = 4 * open_
    c["chest.rx"] += 2 * count - 2 * open_
    blink(c, f, N, [8, 50, 90])
    stand_feet(rig, c, spread=0.002)
    return c


@clip("joseph", "stand_proud", 60, False, markers={"collar": 22}, look="governor",
      notes="straightens up tall (a breath that lifts the chest), the right hand touches the new collar, chin up and a "
            "look out over the land (head turns to his left); the hand settles back down, the left hand at his belt; "
            "holds, standing tall")
def joseph_stand_proud(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.3)
    up = ease_io((f - 2) / 14)
    touch = ease_io((f - 10) / 10) * (1 - ease_io((f - 34) / 14))
    look = ease_io((f - 24) / 16)
    c["chest.rx"] += -6 * up; c["spine.rx"] = -2 * up; c["hips.ty"] = 0.002 * up
    c["shoulderL.swing"] = -4 * up; c["shoulderR.swing"] = -4 * up
    arm_ik(c, "R", V(-0.014, -0.006, 0.046), V(-0.8, -0.6, -0.2), "chest", touch)
    c["handR.bend"] = -16 * touch; fingers(c, "R", 20 + 8 * touch)
    arm_ik(c, "L", V(0.060, 0.172, 0.022), V(0.9, 0.0, -0.4), "root", ease_io((f - 20) / 16))
    c["handL.bend"] = 20; fingers(c, "L", 50)
    c["head.rx"] = -3 - 8 * up + 2 * touch; c["head.ry"] = 18 * look; c["neck.ry"] = 6 * look
    c["head.rz"] = -2 * look
    stand_feet(rig, c, spread=0.004)
    blink(c, f, N, [8, 44], loop=False)
    return c


@clip("joseph", "recognise", 60, False, markers={"start": 4, "turn": 30}, look="governor",
      notes="a small start (shoulders up, head back), the right hand to his chest; then he turns half away (hips, chest, "
            "head, in that order) and lowers his head so his brother cannot see his face; holds turned away, breathing "
            "hard")
def joseph_recognise(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.4)
    st = bump(f, 0, 12)
    hand = ease_io((f - 4) / 10)
    turn = ease_io((f - 18) / 18); turnl = ease_io((f - 21) / 18)
    br = 0.6 * wave(f, 18, 1) * ease_io((f - 36) / 10)
    c["shoulderL.raise"] += 5 * st; c["shoulderR.raise"] += 5 * st
    c["head.rx"] = -3 - 8 * st + 9 * turnl; c["neck.rx"] = 4 * turnl
    c["hips.ry"] = -18 * turn; c["spine.ry"] = -12 * turn; c["chest.ry"] = -14 * turnl; c["head.ry"] = -28 * turnl
    c["chest.rx"] += -4 * st + 6 * turnl - 1.5 * br
    arm_ik(c, "R", V(-0.010, 0.000, 0.046), V(-0.8, -0.6, -0.2), "chest", hand)
    c["handR.bend"] = -14; fingers(c, "R", 30)
    c["upperArmL.bend"] = 6 - 10 * turn; c["upperArmL.raise"] = -18 - 4 * turn; c["forearmL.bend"] = 22 + 10 * turn
    zL, hL = stepping(f, 18, 30, -0.010)
    stand_feet(rig, c, spread=0.002, fwdL=zL, liftL=hL)
    blink(c, f, N, [6, 40], loop=False, base=1.0 + 0.6 * turn)
    return c


@clip("joseph", "ask_gently", 90, True, look="governor",
      notes="hands clasped at his chest, leaning in a little toward the listener, head tilted, small soft nods; "
            "the hands squeeze once; jaw moves a little (lip sync overrides it)")
def joseph_ask_gently(rig, f, N):
    c = jo_base(rig, f, N, cycles=2, amp=0.8)
    beats = mouth(c, f, N, 5, amp=(3, 8), gap=0.4)
    bt = beat_curve(beats, f, N, width=12)
    sq = bump(f, 40, 58)
    c["hips.tz"] = 0.004; c["spine.rx"] = 5; c["chest.rx"] += 3 + 1.5 * bt
    hands_clasped(c, rig, V(0.0, -0.012, 0.050), wring=sq, space="chest")
    c["handL.bend"] = -14; c["handR.bend"] = -14
    fingers(c, "L", 44 + 10 * sq); fingers(c, "R", 44 + 10 * sq)
    c["head.rx"] = 2 + 4 * bt; c["head.rz"] = 9 + 2 * wave(f, N, 1, 0.3); c["head.ry"] = 2 * wave(f, N, 1, 0.6)
    blink(c, f, N, [16, 60], base=1.2)
    stand_feet(rig, c, spread=0.002, fwdL=0.010)
    return c


@clip("joseph", "reveal", 80, False, markers={"off": 27}, look="governor",
      notes="the dam breaks: a breath in, both hands go up to the striped head-cloth, lift it up and off (the `nemes` "
            "bone rises with the hands; marker `off` = the frame the cloth leaves the head: hide joseph/nemes there), "
            "then the arms open wide, palms out ('it's me!'), chest open, head up; holds with arms open, breathing")
def joseph_reveal(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.3)
    br = bump(f, 0, 10)
    up = ease_io((f - 6) / 12)
    lift = ease_io((f - 17) / 10)
    opn = ease_io((f - 30) / 16)
    over = bump(f, 40, 56)
    w_head = up * (1 - opn)
    # hands at the sides of the head-cloth (head space), then lifting with it
    for s_, sx in (("L", 1), ("R", -1)):
        arm_ik(c, s_, V(0.040 * sx, 0.026 + 0.040 * lift, 0.004), V(0.9 * sx, -0.2, -0.4), "head", w_head)
    c["nemes.ty"] = 0.042 * lift; c["nemes.tz"] = -0.006 * lift
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{s_}.raise"] = -18 + 62 * opn + 6 * over
        c[f"upperArm{s_}.bend"] = 6 + 30 * opn
        c[f"forearm{s_}.bend"] = 22 + 6 * opn
        c[f"forearm{s_}.twist"] = -sx * 70 * opn
        c[f"hand{s_}.bend"] = 6 - 20 * opn
    fingers(c, "L", 30 * w_head + 8); fingers(c, "R", 30 * w_head + 8)
    c["chest.rx"] += -2 * br - 6 * opn; c["head.rx"] = -3 + 4 * up - 8 * opn - 3 * over
    c["hips.ty"] = -0.003 * br + 0.002 * opn
    c["jaw.rx"] = 4 * opn
    stand_feet(rig, c, spread=0.003)
    blink(c, f, N, [5, 60], loop=False)
    return c


LIFT_G0 = V(0.0, 0.118, 0.070)          # where the two pairs of hands meet (Joseph's root space, LIFT_D apart)
LIFT_G1 = V(0.0, 0.198, 0.054)
LIFT_DX = 0.024


def lift_grip(fj):
    """(grip centre in Joseph's root space, rise 0..1) at Joseph's lift_up frame fj."""
    rise = ease_io((fj - 40) / 38)
    return LIFT_G0.lerp(LIFT_G1, rise) + V(0, 0.003 * bump(fj, 36, 44), 0), rise


@clip("joseph", "lift_up", 90, False, markers={"grip": 36, "up": 78}, look="governor",
      notes="bends down over his brother sitting on the ground 0.115 in front, takes both his hands (grip at f 36) and "
            "raises him to his feet, leaning back a little as he pulls; ends holding his hands at chest height. Pair: "
            "brother_stand_up must start 24 f (0.8 s) after this clip, as story S10 has it")
def joseph_lift_up(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.4)
    g, rise = lift_grip(f)
    bend = ease_io((f - 6) / 26) * (1 - ease_io((f - 38) / 18))
    reach = ease_io((f - 10) / 26)
    hip_down = 0.020 * bend
    c["hips.ty"] = -hip_down; c["hips.tz"] = -0.012 * bend - 0.004 * rise
    c["hips.rx"] = 12 * bend; c["spine.rx"] = 14 * bend - 3 * rise; c["chest.rx"] += 12 * bend - 4 * rise
    c["neck.rx"] = 4 * bend; c["head.rx"] = -3 + 14 * bend + 4 * rise
    for s_, sx in (("L", 1), ("R", -1)):
        side = V(0.060 * sx, 0.165, 0.020)
        arm_ik(c, s_, side.lerp(g + V(LIFT_DX * sx, 0.004, -0.008), reach), V(0.8 * sx, -0.6, -0.3), "root", reach)
        c[f"hand{s_}.twist"] = -sx * 40 * reach
        fingers(c, s_, 20 + 40 * ease_io((f - 34) / 4))
    stand_feet(rig, c, spread=0.004)
    c["pole.legL"] = V(0.15, 0, 1); c["pole.legR"] = V(-0.15, 0, 1)
    blink(c, f, N, [18, 60], loop=False)
    return c


def hug_body(rig, c, f, N, s, sq, lean=0.003):
    """Shared hug: sway s (same phase for both partners), squeeze sq; every hugger puts his head to his own right so
    two heads pass each other. Hips stay back (bellies and Jacob's robe already touch at 0.11), the chest leans in.
    Arms (tall over short): Joseph's both arms go under, round the partner's back; the brother's both go over
    Joseph's shoulders; Jacob's free left arm goes round Joseph's waist, under Joseph's arms."""
    c["hips.tz"] = lean; c["spine.rx"] = 4; c["chest.rx"] += 5 + 2 * sq
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -2.0 * s; c["spine.rz"] = 3 + 1.4 * s; c["chest.rz"] = 3 + 1.0 * s


def hug_arms(c, D, s, sq, pat=0.0, yR=0.220, yL=0.206, xR=-0.026, xL=0.030, zR=0.008, zL=0.004, pole_y=-0.3,
             right=True, left=True):
    """Wrists on the partner's back (own root space, partner D in front); hands bent round him."""
    if right:
        arm_ik(c, "R", V(xR + 0.002 * s, yR - 0.004 * sq, D + zR + 0.003 * pat), V(-1.0, pole_y, -0.2))
        c["handR.bend"] = 36 - 6 * pat; c["handR.twist"] = 50
    if left:
        arm_ik(c, "L", V(xL + 0.002 * s, yL - 0.004 * sq, D + zL), V(1.0, pole_y, -0.2))
        c["handL.bend"] = 40; c["handL.twist"] = -60


@clip("joseph", "hug", 90, True, look="governor",
      notes="a long hug of someone 0.11-0.12 in front (fitted at 0.115; probed with brother_hug and jacob_hug): leans "
            "in, both arms round the partner's back under his arms, head to his own right against the partner's "
            "shoulder; rocking side to side (same phase as the partner's hug), one squeeze and a pat; eyes closed, "
            "happy tears")
def joseph_hug(rig, f, N):
    c = jo_base(rig, f, N, cycles=2, amp=1.2)
    s = hug_sway(f, N)
    sq = bump(f, 40, 62)
    pat = pulses(f, N, [(66, 1.0), (75, 0.7)], decay=2.5)
    hug_body(rig, c, f, N, s, sq)
    c["neck.rx"] = 4; c["head.rx"] = 6; c["neck.ry"] = -10; c["head.ry"] = -26; c["head.rz"] = 8 + 2 * s
    hug_arms(c, HUG_D, s, sq, pat, yR=0.222, yL=0.208, xR=-0.036, xL=0.038, zR=0.024, zL=0.020)
    c["handR.bend"] = 22 - 6 * pat; c["handL.bend"] = 24; c["chest.rx"] -= 2
    fingers(c, "R", 18 + 10 * sq); fingers(c, "L", 22 + 12 * sq)
    c["eyelids.sy"] = 12.0
    stand_feet(rig, c, spread=0.003, fwdL=0.010, fwdR=-0.004)
    return c


@clip("joseph", "wave", 48, True, look="governor",
      notes="a big happy wave to the viewer: the right arm high above the head sweeping wide side to side, the wrist "
            "flapping late; bouncing on his toes, the left hand on his hip, the head tilting with the wave, beaming")
def joseph_wave(rig, f, N):
    c = jo_base(rig, f, N, cycles=1, amp=0.6)
    ph = 2 * math.pi * f / N
    s = math.sin(2 * ph)
    arm_ik(c, "R", V(-0.070 + 0.034 * s, 0.392 - 0.012 * abs(s), 0.030), V(-0.9, -0.3, -0.2))
    c["handR.bend"] = -10; c["handR.raise"] = -26 * math.sin(2 * ph - 0.9)
    fingers(c, "R", 4 + 8 * max(0.0, math.sin(2 * ph - 1.6)))
    bounce = 0.5 - 0.5 * math.cos(2 * ph)
    c["hips.ty"] = -0.002 + 0.004 * bounce
    stand_feet(rig, c, spread=0.003, pitchL=10 * bounce, pitchR=10 * bounce)
    c["hips.tx"] = 0.003 * math.sin(ph); c["hips.rz"] = -1.5 * math.sin(ph)
    c["chest.rz"] = 2.5 * math.sin(2 * ph - 0.4) - 2; c["head.rz"] = 6 * math.sin(2 * ph - 0.8) - 3
    arm_ik(c, "L", V(0.060, 0.172, 0.020), V(0.9, 0.0, -0.4))
    c["handL.bend"] = 20; fingers(c, "L", 50)
    c["jaw.rx"] = 5
    blink(c, f, N, [20])
    return c


# =============================================================================================== JACOB
# Rest: stooped (baked in the skeleton: do not add it again), right fist round the stick. Unless a clip says otherwise
# the stick stands on the page at his right side and the right wrist is solved to it (`staff.foot` + `staff.dir`).
STICK_SIDE = (V(-0.098, 0.0, 0.036), V(-0.04, 1.0, -0.12))
STICK_FRONT = (V(-0.020, 0.0, 0.078), V(0.06, 1.0, -0.24))


def ja_base(rig, f, N, cycles=1, amp=1.0, phase=0.0, stick=STICK_SIDE):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.8 * b * amp; c["spine.rx"] = -0.8 * b * amp
    c["shoulderL.raise"] = 1.3 * b * amp; c["shoulderR.raise"] = 1.3 * b * amp
    c["neck.rx"] = 0.8 * b * amp; c["head.rx"] = -0.6 * b * amp
    c["upperArmL.raise"] = -18; c["upperArmL.bend"] = 6; c["forearmL.bend"] = 30; c["forearmL.twist"] = -10
    c["handL.bend"] = 6; fingers(c, "L", 26)
    fingers(c, "R", 70)
    if stick is not None:
        staff_at(c, *stick)
        c["pole.armR"] = V(-0.7, -0.5, -0.6)
    return c


def left_on_stick(c, rig, w=1.0, lift=0.0):
    """Left hand cupped over the right fist on top of the stick (target in stick space)."""
    arm_ik(c, "L", V(0.010, 0.022 + lift, 0.006), V(0.9, -0.5, -0.3), STICK, w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 30, w); c["handL.twist"] = -40 * w
    fingers(c, "L", lerp(c.get("fingersL.curl", 26), 55, w))


@clip("jacob", "idle", 150, True,
      notes="an old father at ease: both hands stacked on the stick planted in front of him, leaning on it; slow deep "
            "breathing, a gentle side-to-side sway, looks fondly round (left, then right) and smiles, one contented "
            "nod; slow blinks; the shawl settles")
def jacob_idle(rig, f, N):
    c = ja_base(rig, f, N, cycles=3, amp=1.0, stick=STICK_FRONT)
    sw = wave(f, N, 2, 0.1)
    c["hips.tx"] = 0.003 * sw; c["hips.rz"] = -1.8 * sw; c["spine.rz"] = 1.0 * wave(f, N, 2, 0.05)
    lean = K([(0, 0), (30, 0), (50, 1), (90, 1), (110, 0.3), (150, 0)], f, N, True)
    c["hips.tz"] = -0.003 + 0.003 * lean; c["spine.rx"] += 2 * lean
    look = [(0, 0), (20, 0), (34, 14), (60, 14), (70, -2), (92, -12), (114, -12), (126, 0), (150, 0)]
    c["head.ry"] = 0.7 * K(look, f, N, True); c["neck.ry"] = 0.3 * KL(look, f, N, True, lag=4)
    nod = K([(0, 0), (128, 0), (134, 6), (140, 0), (150, 0)], f, N, True)
    c["head.rx"] += nod - 2 * bump(f, 30, 60)
    left_on_stick(c, rig)
    blink(c, f, N, [24, 71, 112, 140], base=1.3, slow=1.6)
    stand_feet(rig, c, spread=0.003, pitchL=K([(0, 0), (40, 0), (52, 4), (90, 4), (100, 0), (150, 0)], f, N, True))
    return c


@clip("jacob", "talk", 96, True,
      notes="talks warmly: right hand on the stick at his side, the left hand gestures palm-up on the stressed "
            "syllables and once comes to his chest; head nods and tilts; jaw in an irregular rhythm with pauses (lip "
            "sync overrides it); a chuckle in the shoulders")
def jacob_talk(rig, f, N):
    c = ja_base(rig, f, N, cycles=2, amp=0.9)
    jk, beats = syllables(N, 63, amp=(4, 11), dur=(3.5, 7.0), gap=0.3)
    c["jaw.rx"] = jaw_from(jk, f, N)
    bt = beat_curve(beats, f, N, width=10); btl = beat_curve(beats, f - 3, N, width=11)
    c["head.rx"] += 2.5 * bt - 1.5 * wave(f, N, 1, 0.2)
    c["head.ry"] = 4 * wave(f, N, 1, 0.15) + 1.5 * wave(f, N, 3, 0.4); c["head.rz"] = 3 * wave(f, N, 1, 0.4)
    ph = K([(0, 0.3), (10, 0.9), (40, 1.0), (50, 0.2), (60, 0.0), (82, 0.0), (90, 0.4), (96, 0.3)], f, N, True)
    chest = K([(0, 0), (46, 0), (58, 1), (78, 1), (90, 0), (96, 0)], f, N, True)
    lift = ph * (0.7 + 0.3 * btl)
    c["upperArmL.raise"] = -18 + 3 * lift; c["upperArmL.bend"] = 6 + 34 * lift
    c["forearmL.bend"] = 30 + 46 * lift; c["forearmL.twist"] = -10 + 75 * lift
    c["handL.bend"] = 6 - 18 * btl * ph; fingers(c, "L", 30 - 20 * btl * ph)
    arm_ik(c, "L", V(0.012, -0.010, 0.044), V(0.8, -0.6, -0.2), "chest", chest)
    chk = pulses(f, N, [(70, 0.8), (76, 0.5)], decay=2.5)
    c["shoulderL.raise"] += 2 * chk; c["shoulderR.raise"] += 2 * chk
    c["chest.ry"] = 4 * lift; c["chest.rx"] += 1.2 * bt
    blink(c, f, N, [12, 50, 79], base=1.2, slow=1.4)
    stand_feet(rig, c, spread=0.003)
    return c


def give_stick(rig, w_offer):
    """Stick foot / direction while offering (held upright in the fist, foot off the page) vs planted at the side."""
    grip = V(-0.034, 0.168, 0.080)
    d_off = V(0.0, 1.0, 0.12).normalized()
    foot_off = grip - d_off * rig.staff_len
    foot = STICK_SIDE[0].lerp(foot_off, w_offer)
    d = STICK_SIDE[1].normalized().lerp(d_off, w_offer)
    return foot, d


@clip("jacob", "give_coat", 96, False, markers={"offer": 24, "pat": 60}, look=None,
      notes="holds both arms out in front, the forearms up as if a folded coat lies across them (the right fist still "
            "holds the stick, lifted upright), a proud chuckle; then the left hand pats the shoulder of the son 0.12 "
            "in front (twice) and the stick goes back down beside him; holds smiling")
def jacob_give_coat(rig, f, N):
    c = ja_base(rig, f, N, cycles=1, amp=0.5, stick=None)
    offer = ease_io((f - 4) / 18) * (1 - ease_io((f - 40) / 14))
    pat_w = ease_io((f - 44) / 12)
    pats = bump(f, 58, 66) + bump(f, 68, 76)
    chk = pulses(f, N, [(26, 0.9), (31, 0.6)], decay=2.5, loop=False)
    foot, d = give_stick(rig, offer)
    staff_at(c, foot, d)
    c["pole.armR"] = V(-0.8, -0.6, -0.3)
    # left: palm up under the "coat", then to the partner's right shoulder
    offerL = V(0.036, 0.176, 0.072)
    shoulder = partner(V(-0.058, 0.262, 0.016), GIVE_D)                 # the son's right shoulder (0.12 in front)
    pat_pt = shoulder + V(0, 0.006 - 0.008 * pats, 0.0)
    tL = offerL.lerp(pat_pt, pat_w)
    arm_ik(c, "L", tL, V(0.9, -0.5, -0.3), "root", max(offer, pat_w))
    c["handL.twist"] = -70 * offer; c["handL.bend"] = -10 * offer + 40 * pat_w
    fingers(c, "L", 20 - 10 * offer + 10 * pat_w)
    c["hips.tz"] = 0.006 * offer + 0.012 * pat_w; c["spine.rx"] = 3 * pat_w
    c["shoulderL.raise"] += 2 * chk; c["shoulderR.raise"] += 2 * chk; c["chest.rx"] += -1.5 * chk
    c["head.rx"] = -3 * offer + 2 * pat_w; c["head.rz"] = 6 * pat_w
    c["jaw.rx"] = 4 * offer + 3 * chk
    zL, hL = stepping(f, 44, 56, 0.012)
    stand_feet(rig, c, spread=0.003, fwdL=zL, liftL=hL)
    blink(c, f, N, [10, 50, 84], loop=False, base=1.2, slow=1.4)
    return c


@clip("jacob", "weep", 120, True,
      notes="quiet grief: the head bowed into his left hand (palm over the eyes, the mouth and beard still seen from the "
            "front), shoulders shaking in uneven sobs, the knees give a little on each; the right hand leans on the "
            "stick at his side; a slow shake of the head")
def jacob_weep(rig, f, N):
    c = ja_base(rig, f, N, cycles=2, amp=0.6)
    sob = pulses(f, N, [(6, 1.0), (12, 0.7), (18, 0.5), (48, 0.9), (53, 0.6), (82, 1.0), (88, 0.7), (95, 0.5)], decay=3.0)
    c["shoulderL.raise"] += 4 * sob; c["shoulderR.raise"] += 4.5 * sob
    c["chest.rx"] += 6 - 2.5 * sob; c["spine.rx"] += 3
    c["hips.ty"] = -0.003 - 0.002 * sob
    c["neck.rx"] = 12; c["head.rx"] = 24 + 3 * sob
    shake = K([(0, 0), (60, 0), (66, -5), (74, 5), (82, -2), (90, 0), (120, 0)], f, N, True)
    c["head.ry"] = 6 + shake; c["head.rz"] = 6
    arm_ik(c, "L", V(0.016, -0.014 - 0.002 * sob, 0.042), V(0.9, -0.7, 0.1), "head")
    c["handL.bend"] = -44; c["handL.twist"] = -60; fingers(c, "L", 24 + 6 * sob)
    blink(c, f, N, [0], base=12.0)
    stand_feet(rig, c, spread=0.003)
    return c


A_WALK = (0.050, 0.64)


@clip("jacob", "walk_old", 48, True, markers={"contactL": 0, "contactR": 24, "stickPlant": 2}, speed=A_WALK,
      notes="slow old walk, stooped: short steps with a dip on each, the head nods late; the stick is lifted and set "
            "down every other step (planted with the left foot, so it stays still on the page while it carries "
            "weight); the free left arm hangs and swings a little; the shawl bounces")
def jacob_walk_old(rig, f, N):
    c = ja_base(rig, f, N, cycles=1, amp=0.6, stick=None)
    g = gait(rig, f, N, L=A_WALK[0], lift=0.007, duty=A_WALK[1], heel=6, toeoff=14)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.005 + 0.0026 * math.cos(2 * ph - 0.3)
    c["hips.ry"] = 3 * math.sin(ph); c["chest.ry"] = -2.5 * math.sin(ph - 0.4)
    c["hips.rz"] = 2.6 * math.cos(ph); c["chest.rz"] = -1.4 * math.cos(ph - 0.6); c["head.rz"] = 1.0 * math.cos(ph - 1.0)
    c["spine.rx"] = 2; c["chest.rx"] += 1
    c["head.rx"] = 1 + 2.2 * math.cos(2 * ph - 1.3); c["neck.rx"] = 1 + 1.0 * math.cos(2 * ph - 0.9)
    c["upperArmL.bend"] = 6 - 8 * math.sin(ph - 0.3); c["forearmL.bend"] = 32 - 5 * math.sin(ph - 1.0)
    c["handL.bend"] = 6 - 5 * math.sin(ph - 1.6)
    footL = g["legL"]
    p = footL[3]
    base = V(-0.098, 0.0, 0.0)
    if p < A_WALK[1]:
        z = footL[0].z - rig.head["footL"].z + 0.034
        foot = base + V(0, 0.0, z)
    else:
        s = (p - A_WALK[1]) / (1 - A_WALK[1])
        z = -A_WALK[0] / 2 + A_WALK[0] * smooth(s) + 0.034
        foot = base + V(0, 0.020 * math.sin(math.pi * s), z)
    grip = V(-0.098, 0.150, 0.022 + 0.006 * math.sin(ph))
    staff_at(c, foot, grip - foot)
    c["pole.armR"] = V(-0.7, -0.5, -0.6)
    blink(c, f, N, [31], base=1.3, slow=1.5)
    return c


@clip("jacob", "hug", 90, True,
      notes="holds his son 0.11-0.12 in front (fitted at 0.115, probed with joseph_hug): the left arm round his waist, "
            "the stick still planted at his right side, his head beside his son's (to his own right), cheek on the "
            "shoulder; rocks with him (same phase), a squeeze, laughing-crying sobs in the shoulders; eyes shut")
def jacob_hug(rig, f, N):
    c = ja_base(rig, f, N, cycles=2, amp=1.0, stick=None)
    s = -hug_sway(f, N)
    sq = bump(f, 40, 62)
    sob = pulses(f, N, [(14, 0.8), (20, 0.5), (70, 0.9), (76, 0.5)], decay=3.0)
    c["hips.tz"] = -0.006; c["spine.rx"] = 3; c["chest.rx"] += 2 + 2 * sq - 1.5 * sob
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -2.0 * s; c["spine.rz"] = 3 + 1.2 * s; c["chest.rz"] = 3
    c["shoulderL.raise"] += 2 * sob; c["shoulderR.raise"] += 2 * sob
    c["neck.rx"] = -4; c["head.rx"] = -6; c["neck.ry"] = -8; c["head.ry"] = -22; c["head.rz"] = 6 + 2 * s
    hug_arms(c, HUG_D, s, sq, yL=0.180, xL=0.044, zL=0.006, right=False)
    c["handL.bend"] = 26
    fingers(c, "L", 24 + 14 * sq)
    staff_at(c, V(-0.090 + 0.002 * s, 0.0, 0.004), V(-0.02, 1.0, -0.06))
    c["pole.armR"] = V(-1.0, -0.4, -0.3)
    stand_feet(rig, c, spread=0.003, fwdL=0.008)
    c["eyelids.sy"] = 12.0
    return c


# =============================================================================================== BROTHER
# Rest: A-pose. Big, heavy, sure of himself: chest out, arms held a little away from the body.
def b_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.6 * b * amp - 2; c["spine.rx"] = -0.6 * b * amp
    c["shoulderL.raise"] = 1.2 * b * amp; c["shoulderR.raise"] = 1.2 * b * amp
    c["neck.rx"] = 0.8 * b * amp
    c["upperArmL.raise"] = -14; c["upperArmR.raise"] = -14
    c["upperArmL.bend"] = 6; c["upperArmR.bend"] = 6
    c["forearmL.bend"] = 24; c["forearmR.bend"] = 24
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 34); fingers(c, "R", 34)
    c["head.rx"] = -3
    return c


def fold_arms_pose(c, rig, w=1.0, hug=0.0):
    """Arms folded high on the chest (right forearm over the left), targets in chest space."""
    arm_ik(c, "L", V(-0.030, -0.020 + 0.002 * hug, 0.058), V(0.9, -0.7, 0.1), "chest", w)
    arm_ik(c, "R", V(0.032, -0.004, 0.066), V(-0.9, -0.7, 0.1), "chest", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), -6, w); c["handR.bend"] = lerp(c.get("handR.bend", 6), 8, w)
    c["handL.twist"] = 30 * w; c["handR.twist"] = -40 * w
    fingers(c, "L", lerp(34, 50, w)); fingers(c, "R", lerp(34, 40, w))


@clip("brother", "idle", 150, True,
      notes="heavy and sure of himself: thumbs hooked in his belt, weight sinking onto one hip and then the other, "
            "chest out, a slow look round with the chin up, a sniff (head jerks up a little), a scratch of the beard "
            "with the right hand; slow blinks; the bag swings")
def brother_idle(rig, f, N):
    c = b_base(rig, f, N, cycles=3, amp=1.0)
    sh = K([(0, -0.8), (40, -0.8), (64, 0.9), (110, 0.9), (134, -0.8), (150, -0.8)], f, N, True)
    shl = KL([(0, -0.8), (40, -0.8), (64, 0.9), (110, 0.9), (134, -0.8), (150, -0.8)], f, N, True, lag=8)
    c["hips.tx"] = 0.005 * sh; c["hips.rz"] = -3.0 * sh; c["hips.ty"] = -0.002 * abs(sh)
    c["spine.rz"] = 1.8 * shl; c["chest.rz"] = 1.0 * shl; c["head.rz"] = -1.5 * shl
    look = [(0, 0), (20, 0), (34, 18), (56, 18), (66, -4), (100, -4), (114, -16), (136, -16), (150, 0)]
    c["neck.ry"] = 0.4 * K(look, f, N, True); c["head.ry"] = 0.6 * KL(look, f, N, True, lag=4)
    sniff = pulses(f, N, [(72, 1.0)], decay=4.0)
    c["head.rx"] = -5 - 4 * sniff
    scratch = ease_io((f - 80) / 14) * (1 - ease_io((f - 102) / 14))
    arm_ik(c, "L", V(0.050, 0.192, 0.030), V(0.9, 0.0, -0.4), "root", 1.0)
    arm_mix(c, "R", V(-0.050, 0.192, 0.030), "root", V(-0.010 + 0.004 * math.sin(f * 1.4), -0.030, 0.034), "head",
            scratch, V(-0.9, -0.3, -0.3))
    for s_ in "LR":
        c[f"hand{s_}.bend"] = 18; fingers(c, s_, 50)
    c["handR.bend"] = 18 - 18 * scratch; fingers(c, "R", 50 - 20 * scratch)
    blink(c, f, N, [26, 80, 121], base=1.25)
    stand_feet(rig, c, spread=0.004, pitchL=K([(0, 0), (50, 0), (64, 6), (110, 6), (124, 0), (150, 0)], f, N, True))
    return c


@clip("brother", "talk", 96, True,
      notes="talks bluntly: jaw in an irregular rhythm (lip sync overrides it), head jutting on the stressed syllables, "
            "the right hand chops the air, the left thumb in the belt; weight shift")
def brother_talk(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.8)
    beats = mouth(c, f, N, 13, amp=(6, 14))
    bt = beat_curve(beats, f, N, width=8); btl = beat_curve(beats, f - 2, N, width=8)
    c["head.rx"] = -4 + 4 * bt; c["neck.rx"] = 2 * bt
    c["head.ry"] = 6 * wave(f, N, 1, 0.1); c["head.rz"] = 3 * wave(f, N, 1, 0.35)
    arm_ik(c, "L", V(0.050, 0.192, 0.030), V(0.9, 0.0, -0.4))
    c["handL.bend"] = 18; fingers(c, "L", 50)
    up = K([(0, 0.6), (12, 1), (60, 1), (80, 0.3), (96, 0.6)], f, N, True)
    c["upperArmR.bend"] = 6 + 38 * up; c["forearmR.bend"] = 24 + 50 * up + 14 * btl
    c["forearmR.twist"] = 10 - 40 * up; c["handR.bend"] = 6 + 16 * btl; fingers(c, "R", 20)
    c["chest.ry"] = -5 * up; c["chest.rx"] += 2 * bt
    sh = wave(f, N, 1, 0.15)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.8 * sh
    blink(c, f, N, [9, 58], base=1.2)
    stand_feet(rig, c, spread=0.004)
    return c


B_WALK = (0.084, 0.60)


@clip("brother", "walk", 36, True, markers={"contactL": 0, "contactR": 18}, speed=B_WALK,
      notes="heavy, swaggering walk: big hip roll, shoulders swinging against it, arms swinging wide from the body, "
            "chin up; feet land flat and heavy; the bag swings")
def brother_walk(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=B_WALK[0], lift=0.011, duty=B_WALK[1], heel=8, toeoff=20)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0050 + 0.0034 * math.cos(2 * ph - 0.3)
    c["hips.ry"] = 7 * math.sin(ph); c["chest.ry"] = -9 * math.sin(ph - 0.35); c["head.ry"] = 4 * math.sin(ph - 0.7)
    c["hips.rz"] = 4.0 * math.cos(ph); c["chest.rz"] = -2.2 * math.cos(ph - 0.5); c["head.rz"] = 1.0 * math.cos(ph - 0.9)
    c["head.rx"] = -5 + 1.4 * math.cos(2 * ph - 1.0)
    c["upperArmL.raise"] = -8; c["upperArmR.raise"] = -8
    c["upperArmL.bend"] = 6 - 18 * math.sin(ph - 0.25); c["upperArmR.bend"] = 6 + 18 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 26 - 8 * math.sin(ph - 1.0); c["forearmR.bend"] = 26 + 8 * math.sin(ph - 1.0)
    blink(c, f, N, [29], base=1.2)
    return c


@clip("brother", "fold_arms", 50, False, markers={"folded": 20},
      notes="a 'hmph': chest out, folds his arms high on his chest (right over left), shifts his weight onto one hip and "
            "turns his head away with the chin up; holds (sulking, slow breath)")
def brother_fold_arms(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.5)
    fold = ease_io((f - 2) / 16)
    away = ease_io((f - 14) / 14)
    over = bump(f, 16, 28)
    fold_arms_pose(c, rig, fold)
    c["chest.rx"] += -3 * fold - 1 * over
    c["hips.tx"] = 0.005 * away; c["hips.rz"] = -3 * away; c["spine.rz"] = 2 * away
    c["head.ry"] = 26 * away + 3 * over; c["neck.ry"] = 6 * away; c["head.rx"] = -3 - 6 * away; c["head.rz"] = -4 * away
    stand_feet(rig, c, spread=0.005, pitchR=5 * away)
    blink(c, f, N, [10, 40], loop=False, base=1.3)
    return c


@clip("brother", "grumble", 120, True,
      notes="muttering to himself, arms folded: the jaw grumbles (lip sync overrides it), head shakes, a shrug, then he "
            "kicks a pebble with the right foot (wind-up, kick, the foot comes back down to its mark) and sulks")
def brother_grumble(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=0.8)
    beats = mouth(c, f, N, 91, amp=(3, 9), gap=0.4)
    bt = beat_curve(beats, f, N, width=10)
    fold_arms_pose(c, rig, 1.0, hug=bump(f, 20, 40))
    shake = K([(0, 0), (10, 0), (16, -8), (22, 7), (28, -4), (34, 0), (120, 0)], f, N, True)
    shrug = bump(f, 40, 56)
    c["head.ry"] = 18 + shake + 4 * wave(f, N, 1, 0.3); c["head.rx"] = -2 + 3 * bt; c["head.rz"] = -3
    c["shoulderL.raise"] += 7 * shrug; c["shoulderR.raise"] += 7 * shrug; c["neck.rx"] = -2 * shrug
    # the kick: right foot back (wind-up), swing forward, back down to the mark
    kick = K([(0, 0), (68, 0), (73, -0.6), (77, 1.0), (84, 0.2), (89, 0), (120, 0)], f, N, True)
    lift = bump(f, 62, 92)
    stand_feet(rig, c, spread=0.004)
    b = rig.head["footR"]
    pk = -20 * max(0.0, kick) + 4 * max(0.0, -kick)
    c["ik.legR"] = V(b.x, planted_ankle_y(rig, "R", pk) + 0.030 * lift + 0.010 * max(0, kick),
                     b.z + 0.040 * kick * min(1.0, 4 * lift))
    c["footR.pitch"] = pk
    c["hips.rx"] = -3 * max(0.0, kick); c["chest.rx"] += 2 * max(0.0, kick)
    c["hips.tx"] = 0.004 * lift; c["hips.rz"] = -2 * lift
    c["head.rx"] += 8 * bump(f, 76, 98)                   # looks where the pebble went
    blink(c, f, N, [6, 52, 104], base=1.3)
    return c


@clip("brother", "angry_point", 45, False, markers={"jab": 12},
      notes="outraged: a sharp breath back, then steps in and jabs his right arm straight at the listener (fist with "
            "the arm out: pointing), leaning in, chin forward, the left fist clenched at his side; two smaller jabs; "
            "holds pointing")
def brother_angry_point(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.4)
    back = bump(f, 0, 10)
    jab = ease_io((f - 7) / 6)
    j2 = bump(f, 20, 27) + 0.7 * bump(f, 29, 36)
    c["hips.tz"] = -0.004 * back + 0.010 * jab; c["spine.rx"] = -4 * back + 8 * jab + 2 * j2
    c["chest.rx"] += -4 * back + 6 * jab + 2 * j2; c["chest.ry"] = 10 * jab
    c["neck.rx"] = -6 * jab; c["head.rx"] = -3 + 2 * back - 2 * jab + 3 * j2
    pt = V(-0.034, 0.262 + 0.004 * j2, 0.140 + 0.010 * j2)
    arm_ik(c, "R", V(-0.070, 0.230, -0.020).lerp(pt, jab), V(-0.8, -0.6, -0.4), "root", max(back, jab))
    c["handR.bend"] = -6; fingers(c, "R", 60)
    c["upperArmL.raise"] = -16; c["forearmL.bend"] = 40 * jab; fingers(c, "L", 34 + 40 * jab)
    zR, hR = stepping(f, 6, 13, 0.024)
    stand_feet(rig, c, spread=0.004, fwdR=zR, liftR=hR)
    c["jaw.rx"] = 6 * jab + 4 * j2
    blink(c, f, N, [3], loop=False)
    return c


@clip("brother", "grab_coat", 54, False, markers={"grab": 16, "off": 24},
      notes="lunges, grabs the coat at the shoulders of the brother 0.11 in front with both hands (f 16) and yanks it "
            "back toward his own chest (marker `off` at f 24 = hide joseph/coat), staggering back a step with it; ends "
            "clutching the (now hidden) coat at his chest, triumphant and sour")
def brother_grab_coat(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.3)
    ant = bump(f, 0, 8)
    reach = ease_io((f - 5) / 10) * (1 - ease_io((f - 21) / 8))
    yank = ease_io((f - 21) / 8)
    stag = bump(f, 24, 40)
    grab = [partner(V(0.044, 0.250, 0.030), GRAB_D), partner(V(-0.044, 0.250, 0.030), GRAB_D)]   # his L / R shoulder
    chest = [V(0.030, 0.230, 0.070), V(-0.030, 0.236, 0.072)]
    for i, (s_, sx) in enumerate((("L", 1), ("R", -1))):
        g = grab[1 - i]                                   # his left hand takes the shoulder on his left
        g = g + V(0.010 * sx, 0, -0.006)
        home = V(0.090 * sx, 0.170, 0.010)
        t_ = home.lerp(g, reach) if yank <= 0 else g.lerp(chest[i], yank)
        arm_ik(c, s_, t_, V(0.9 * sx, -0.5, -0.3), "root", max(reach, yank, 0.0) if f < 21 else 1.0)
        c[f"hand{s_}.bend"] = -10 * reach + 10 * yank; c[f"hand{s_}.twist"] = -sx * 40 * reach
        fingers(c, s_, 20 + 60 * ease_io((f - 14) / 3))
    c["hips.tz"] = -0.004 * ant + 0.018 * reach - 0.010 * yank
    c["spine.rx"] = -3 * ant + 12 * reach - 6 * yank; c["chest.rx"] += -2 * ant + 6 * reach - 6 * yank
    c["head.rx"] = -3 + 4 * reach - 6 * yank
    z1, h1 = stepping(f, 5, 14, 0.030); z2, h2 = stepping(f, 22, 32, -0.016)
    z3, h3 = stepping(f, 27, 38, -0.012)
    stand_feet(rig, c, spread=0.004, fwdR=z1 + z2, liftR=h1 + h2, fwdL=z3, liftL=h3)
    c["jaw.rx"] = 5 * reach + 3 * yank
    blink(c, f, N, [2, 30], loop=False)
    return c


@clip("brother", "take_coins", 75, False, markers={"coins": 22, "fist": 30},
      notes="holds out the right palm (fx coins_spray there), the coins land (a little dip of the hand, f 22), the "
            "fist closes (f 30) and goes to his chest, the left hand rubs the beard, a greedy sideways glance and a "
            "smirk; holds")
def brother_take_coins(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.5)
    out = ease_io((f - 2) / 14)
    land = bump(f, 20, 28)
    fist = ease_io((f - 28) / 4)
    home = ease_io((f - 36) / 14)
    glance = ease_io((f - 40) / 10)
    palm = V(-0.040, 0.200 - 0.008 * land, 0.090)
    chest = V(-0.020, 0.236, 0.074)
    arm_ik(c, "R", palm.lerp(chest, home), V(-0.8, -0.6, -0.3), "root", out)
    c["handR.twist"] = -80 * out * (1 - home); c["handR.bend"] = -10
    fingers(c, "R", 6 + 70 * fist)
    rub = ease_io((f - 44) / 8)
    arm_ik(c, "L", V(0.012 + 0.003 * math.sin(f * 1.2) * rub, -0.040, 0.036), V(0.9, -0.6, -0.2), "head", rub)
    fingers(c, "L", 40)
    c["head.rx"] = -3 + 8 * (out - home) * (1 - glance); c["head.ry"] = -24 * glance; c["neck.ry"] = -6 * glance
    c["chest.rx"] += 3 * out * (1 - home); c["chest.ry"] = -4 * glance
    stand_feet(rig, c, spread=0.004)
    c["jaw.rx"] = 2 * glance
    blink(c, f, N, [12, 58], loop=False, base=1.0 + 0.4 * glance)
    return c


def bow_low_pose(rig, c, f, N, w=1.0, bow=1.0, breath=0.0):
    """Kneeling, sitting back toward the heels, chest folded forward, hands on the page in front, head low."""
    kneel_legs(rig, c, w, w)
    c["hips.rx"] = c.get("hips.rx", 0.0) + 20 * bow
    c["spine.rx"] = 18 * bow - 2 * breath; c["chest.rx"] = c.get("chest.rx", 0.0) + 16 * bow - 1.5 * breath
    c["neck.rx"] = 16 * bow; c["head.rx"] = 22 * bow
    for s_, sx in (("L", 1), ("R", -1)):
        arm_ik(c, s_, V(0.046 * sx, 0.016, 0.044), V(0.9 * sx, -0.3, -0.5), "root", bow)
        c[f"hand{s_}.bend"] = -40 * bow; c[f"hand{s_}.twist"] = -sx * 20 * bow
        fingers(c, s_, lerp(34, 6, bow))


@clip("brother", "bow_low", 75, False, markers={"knees": 24, "bow": 44},
      notes="humbled: a tired breath, kneels (both knees on the page, a little behind his mark), sits back toward his "
            "heels and bows the chest and head low, hands flat on the page in front; holds bowed, breathing. Keep the "
            "person he bows to >= 0.11 in front (head clearance)")
def brother_bow_low(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.3)
    one = ease_io((f - 4) / 18); two = ease_io((f - 10) / 16)
    w = 0.5 * (one + two)
    kneel_legs(rig, c, two, one, hips_w=w)
    for s_ in "LR":
        c[f"ik.leg{s_}"] = c[f"ik.leg{s_}"] + V(0, 0.002 * bump(f, 6, 30), 0)     # the tucking feet clear the page
    c["hips.ty"] -= 0.005 * bump(f, 0, 10)
    bow = ease_io((f - 22) / 22)
    br = wave(f, 40, 1) * ease_io((f - 50) / 10)
    c2 = {}
    bow_low_pose(rig, c2, f, N, w=1.0, bow=bow, breath=br)
    for k in ("hips.rx", "spine.rx", "neck.rx", "head.rx"):
        c[k] = c2[k]
    c["chest.rx"] += c2["chest.rx"]
    hw = ease_io((f - 20) / 22)
    for s_, sx in (("L", 1), ("R", -1)):
        arm_ik(c, s_, V(0.046 * sx, 0.016, 0.044), V(0.9 * sx, -0.3, -0.5), "root", hw)
        c[f"hand{s_}.bend"] = -40 * hw; c[f"hand{s_}.twist"] = -sx * 20 * hw
        fingers(c, s_, lerp(34, 6, hw))
    blink(c, f, N, [6, 40], loop=False, base=1.3)
    return c


def seated_back(rig, c, w=1.0):
    """Sitting on the page behind his mark, knees up, leaning back on both hands (end of fall_back_scared)."""
    seat = SEAT_Y["brother"]
    hips_to(rig, c, seat, -0.086)
    for s_, sx in (("L", 1), ("R", -1)):
        b = rig.head["foot" + s_]
        c[f"ik.leg{s_}"] = V(b.x + 0.006 * sx, planted_ankle_y(rig, s_, 0), b.z)
        c[f"foot{s_}.pitch"] = 0.0
        c[f"pole.leg{s_}"] = V(0.25 * sx, 0.8, 1)
        arm_ik(c, s_, V(0.064 * sx, 0.028, -0.150), V(0.6 * sx, 0.2, -0.8), "root", w)
        c[f"hand{s_}.bend"] = -50; fingers(c, s_, 8)
    c["hips.rx"] = -14; c["spine.rx"] = -6; c["chest.rx"] = c.get("chest.rx", 0.0) + 4


@clip("brother", "fall_back_scared", 45, False, markers={"jerk": 4, "sit": 20},
      notes="from bow_low: jerks up in shock (eyes wide), then falls back onto his bottom behind his mark, catching "
            "himself on both hands, knees up; trembles; holds sitting (stand_up starts from this pose)")
def brother_fall_back_scared(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.2)
    jerk = ease_io(f / 4)
    fall = ease_io((f - 6) / 14)
    land = bump(f, 18, 28)
    tremble = 0.5 * math.sin(f * 2.1) * ease_io((f - 24) / 6)
    # start: the bow_low end pose, upper body flung up
    k = {}
    kneel_legs(rig, k, 1.0, 1.0)
    s = {}
    seated_back(rig, s)
    h0 = V(k["hips.tx"] if "hips.tx" in k else 0.0, k["hips.ty"], k["hips.tz"])
    h1 = V(s["hips.tx"], s["hips.ty"], s["hips.tz"])
    h = h0.lerp(h1, fall) + V(0, 0.010 * jerk * (1 - fall) - 0.003 * land, 0)
    c["hips.tx"], c["hips.ty"], c["hips.tz"] = h.x, h.y, h.z
    for s_, sx in (("L", 1), ("R", -1)):
        a0, a1 = Vector(k[f"ik.leg{s_}"]), Vector(s[f"ik.leg{s_}"])
        t_ = a0.lerp(a1, fall); t_.y += 0.020 * math.sin(math.pi * fall)
        c[f"ik.leg{s_}"] = t_
        c[f"foot{s_}.pitch"] = lerp(k[f"foot{s_}.pitch"], 0.0, fall)
        c[f"pole.leg{s_}"] = V(0.12 * sx, lerp(0.0, 0.8, fall), 1)
        arm_ik(c, s_, V(0.090 * sx, 0.200, 0.030).lerp(V(0.064 * sx, 0.028 + 0.003 * land, -0.150), ease_io((f - 8) / 12)),
               V(0.6 * sx, 0.2, -0.8), "root", min(1.0, 0.3 + jerk))
        c[f"hand{s_}.bend"] = -50 * fall; fingers(c, s_, lerp(10, 8, fall))
        c[f"upperArm{s_}.raise"] = 30 * jerk * (1 - fall)
    c["hips.rx"] = lerp(26 * (1 - jerk), -14, fall); c["spine.rx"] = lerp(22 * (1 - jerk) - 6 * jerk, -6, fall)
    c["chest.rx"] += lerp(20 * (1 - jerk) - 6 * jerk, 4, fall) + tremble
    c["head.rx"] = lerp(18 * (1 - jerk) - 8 * jerk, -2, fall) + tremble; c["neck.rx"] = -4 * jerk
    c["shoulderL.raise"] += 6 * jerk * (1 - fall) + 3 * land; c["shoulderR.raise"] += 6 * jerk * (1 - fall) + 3 * land
    c["jaw.rx"] = 8 * jerk
    c["eyelids.sy"] = 1.0
    return c


@clip("brother", "stand_up", 66, False, markers={"grip": 12, "up": 54},
      notes="from sitting (fall_back_scared): reaches both hands up to his brother 0.115 in front, is gripped (f 12) and "
            "pulled up onto his feet, the body coming forward over the feet; ends standing, holding hands, head a "
            "little bowed. Pair: joseph_lift_up starts 24 f earlier")
def brother_stand_up(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.2)
    fj = f + LIFT_LAG
    g, rise = lift_grip(fj)
    reach = ease_io(f / 12)
    up = ease_io((f - 14) / 40)
    s = {}
    seated_back(rig, s)
    h1 = V(0.0, -0.002, 0.004)
    h0 = V(s["hips.tx"], s["hips.ty"], s["hips.tz"])
    h = h0.lerp(h1, up) + V(0, 0, 0.010 * math.sin(math.pi * up))
    c["hips.tx"], c["hips.ty"], c["hips.tz"] = h.x, h.y, h.z
    stand_feet(rig, c, spread=0.006)
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"pole.leg{s_}"] = V(0.25 * sx, 0.8 * (1 - up), 1)
        hand = partner(g + V(-LIFT_DX * sx, 0.000, 0.010), LIFT_D)      # his L hand holds Joseph's R hand
        start = V(0.064 * sx, 0.028, -0.150)
        arm_ik(c, s_, start.lerp(hand, reach), V(0.7 * sx, -0.4, -0.5), "root")
        c[f"hand{s_}.twist"] = -sx * 40 * reach; c[f"hand{s_}.bend"] = -50 * (1 - reach)
        fingers(c, s_, 8 + 50 * ease_io((f - 10) / 4))
    lean = math.sin(math.pi * up)
    c["hips.rx"] = lerp(-14, 0, reach) + 16 * lean
    c["spine.rx"] = lerp(-6, 6, reach) + 4 * lean - 6 * up
    c["chest.rx"] += 4 + 6 * lean - 4 * up
    c["head.rx"] = -4 + 10 * up; c["neck.rx"] = 4 * up
    blink(c, f, N, [30, 58], loop=False, base=1.2)
    return c


@clip("brother", "hug", 90, True,
      notes="hugs his brother 0.11-0.12 in front (fitted at 0.115, probed with joseph_hug): stoops to him, both arms "
            "over his shoulders, hands on his upper back, the head down on the brother's left shoulder (to his own "
            "right), shoulders heaving with relief; rocks with him (same phase)")
def brother_hug(rig, f, N):
    c = b_base(rig, f, N, cycles=2, amp=1.3)
    s = -hug_sway(f, N)
    sq = bump(f, 40, 62)
    sob = pulses(f, N, [(10, 0.7), (16, 0.5), (60, 0.8), (66, 0.5)], decay=3.0)
    hug_body(rig, c, f, N, s, sq, lean=-0.002)
    c["hips.ty"] = -0.008; c["spine.rx"] = 6; c["chest.rx"] += 4 - 1.5 * sob
    c["shoulderL.raise"] += 2 * sob; c["shoulderR.raise"] += 2 * sob
    c["neck.rx"] = 14; c["head.rx"] = 14; c["neck.ry"] = -10; c["head.ry"] = -30; c["head.rz"] = 10 + 2 * s
    hug_arms(c, HUG_D, s, sq, yR=0.252, yL=0.258, xR=-0.018, xL=0.020, zR=0.030, zL=0.032, pole_y=0.3)
    fingers(c, "R", 24 + 12 * sq); fingers(c, "L", 24 + 12 * sq)
    c["pole.legL"] = V(0.15, 0, 1); c["pole.legR"] = V(-0.15, 0, 1)
    stand_feet(rig, c, spread=0.004, fwdL=0.006, fwdR=-0.010)
    c["eyelids.sy"] = 12.0
    return c


@clip("brother", "wave", 48, True,
      notes="an awkward, shy wave: the right hand only shoulder-high, small quick waggles, the left hand rubbing the "
            "back of his neck, a sheepish head tilt and shuffle of the feet")
def brother_wave(rig, f, N):
    c = b_base(rig, f, N, cycles=1, amp=0.5)
    ph = 2 * math.pi * f / N
    s = math.sin(4 * ph)
    arm_ik(c, "R", V(-0.070 + 0.010 * s, 0.290, 0.050), V(-0.9, -0.6, -0.3))
    c["handR.bend"] = -6; c["handR.raise"] = -18 * math.sin(4 * ph - 0.9); fingers(c, "R", 10)
    arm_ik(c, "L", V(0.016 + 0.004 * math.sin(2 * ph), -0.004, -0.030), V(0.9, 0.2, -0.3), "head")
    c["handL.bend"] = 20; fingers(c, "L", 30)
    c["head.rz"] = -10 + 2 * math.sin(ph); c["head.rx"] = 4; c["head.ry"] = -6
    c["shoulderL.raise"] = 4; c["shoulderR.raise"] = 4
    c["hips.tx"] = 0.003 * math.sin(ph); c["hips.rz"] = -1.6 * math.sin(ph)
    stand_feet(rig, c, spread=0.002, pitchR=8 * (0.5 + 0.5 * math.sin(ph)))
    c["jaw.rx"] = 2
    blink(c, f, N, [12, 36], base=1.1)
    return c


# =============================================================================================== PHARAOH
# Rest: A-pose, round belly (bone `belly`, from spine), front apron (`apron1`). Comic and generous, grand gestures.
def p_base(rig, f, N, cycles=1, amp=1.0, phase=0.0):
    c = {}
    b = wave(f, N, cycles, phase)
    c["chest.rx"] = -1.8 * b * amp - 3; c["spine.rx"] = -0.8 * b * amp - 2
    c["shoulderL.raise"] = 1.2 * b * amp; c["shoulderR.raise"] = 1.2 * b * amp
    c["belly.s"] = 1.0 + 0.02 * b * amp; c["belly.ty"] = 0.001 * b * amp
    c["upperArmL.raise"] = -10; c["upperArmR.raise"] = -10
    c["upperArmL.bend"] = 10; c["upperArmR.bend"] = 10
    c["forearmL.bend"] = 24; c["forearmR.bend"] = 24
    c["forearmL.twist"] = -10; c["forearmR.twist"] = 10
    c["handL.bend"] = 6; c["handR.bend"] = 6
    fingers(c, "L", 24); fingers(c, "R", 24)
    c["head.rx"] = -5
    return c


def hands_on_hips(c, rig, w=1.0):
    for s_, sx in (("L", 1), ("R", -1)):
        arm_ik(c, s_, V(0.074 * sx, 0.214, 0.004), V(0.9 * sx, 0.1, -0.5), "root", w)
        c[f"hand{s_}.bend"] = lerp(c.get(f"hand{s_}.bend", 6), 30, w); c[f"hand{s_}.twist"] = -sx * 30 * w
        fingers(c, s_, lerp(24, 40, w))


def belly_bounce(c, f, t0, amp=1.0, decay=7.0, freq=0.42):
    """Damped belly wobble starting at frame t0 (vertical + squash)."""
    if f < t0:
        return
    d = f - t0
    v = amp * math.exp(-d / decay) * math.sin(freq * d * 2.0)
    c["belly.ty"] = c.get("belly.ty", 0.0) + 0.006 * v
    c["belly.s"] = c.get("belly.s", 1.0) + 0.05 * v
    c["belly.rx"] = c.get("belly.rx", 0.0) + 8 * v


@clip("pharaoh", "idle", 150, True,
      notes="the grand king: hands on his hips, chin up, chest out; slow breathing that lifts the belly, weight shifts "
            "with a little belly wobble, looks down his nose to one side and the other, a self-satisfied nod")
def pharaoh_idle(rig, f, N):
    c = p_base(rig, f, N, cycles=3, amp=1.1)
    hands_on_hips(c, rig)
    sh = K([(0, 0.6), (40, 0.6), (64, -0.8), (110, -0.8), (130, 0.6), (150, 0.6)], f, N, True)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2.4 * sh; c["spine.rz"] = 1.2 * KL([(0, 0.6), (40, 0.6), (64, -0.8), (110, -0.8), (130, 0.6), (150, 0.6)], f, N, True, lag=8)
    belly_bounce(c, f, 64, 0.5); belly_bounce(c, f, 130, 0.5)
    look = [(0, 0), (20, 0), (32, 20), (58, 20), (68, 0), (90, 0), (100, -18), (124, -18), (136, 0), (150, 0)]
    c["head.ry"] = 0.7 * K(look, f, N, True); c["neck.ry"] = 0.3 * KL(look, f, N, True, lag=4)
    nod = K([(0, 0), (70, 0), (76, 6), (84, -1), (90, 0), (150, 0)], f, N, True)
    c["head.rx"] += -6 + nod
    blink(c, f, N, [18, 76, 120], base=1.4)
    stand_feet(rig, c, spread=0.006)
    return c


@clip("pharaoh", "talk", 96, True,
      notes="grand gestures: jaw in a booming rhythm (lip sync overrides it), the right arm sweeps out wide palm-up, "
            "then both arms open; head tilts back on the big words; belly bounces with the emphasis")
def pharaoh_talk(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=0.9)
    beats = mouth(c, f, N, 29, amp=(6, 15))
    bt = beat_curve(beats, f, N, width=9)
    sweep = K([(0, 0.2), (12, 1), (44, 1), (52, 0.3), (96, 0.2)], f, N, True)
    both = K([(0, 0), (50, 0), (62, 1), (86, 1), (94, 0), (96, 0)], f, N, True)
    c["upperArmR.raise"] = -10 + 50 * sweep + 30 * both; c["upperArmR.bend"] = 10 + 30 * sweep
    c["forearmR.bend"] = 24 + 20 * sweep; c["forearmR.twist"] = 10 - 80 * max(sweep, both)
    c["handR.bend"] = 6 - 20 * bt
    c["upperArmL.raise"] = -10 + 70 * both; c["upperArmL.bend"] = 10 + 26 * both
    c["forearmL.bend"] = 24 + 14 * both; c["forearmL.twist"] = -10 + 80 * both
    fingers(c, "R", 24 - 16 * sweep); fingers(c, "L", 24 - 16 * both)
    c["head.rx"] = -6 - 5 * bt; c["head.ry"] = -8 * sweep + 4 * wave(f, N, 1, 0.3); c["chest.ry"] = -6 * sweep
    c["belly.ty"] += 0.002 * bt
    blink(c, f, N, [8, 62], base=1.3)
    stand_feet(rig, c, spread=0.006)
    return c


@clip("pharaoh", "doze", 150, True,
      notes="asleep on his feet: eyes shut, mouth a little open, the head nods lower and lower in three sinking nods "
            "(each deeper, the body tipping forward and the knees going soft), then a jerk upright with the eyes "
            "popping open for a moment, and he drifts off again; snoring breaths lift the belly; arms hang heavy")
def pharaoh_doze(rig, f, N):
    c = p_base(rig, f, N, cycles=3, amp=1.4)
    sink = K([(0, 0.05), (14, 0.10), (30, 0.32), (36, 0.24), (52, 0.28), (72, 0.60), (78, 0.52), (92, 0.56),
              (116, 1.0), (124, 1.04), (127, 1.0), (131, 0.0), (136, -0.08), (142, 0.04), (150, 0.05)], f, N, True)
    jerk = bump(f, 127, 140)
    c["neck.rx"] = 14 * sink; c["head.rx"] = -6 + 30 * sink - 8 * jerk
    c["head.rz"] = 8 * sink * wave(f, N, 1, 0.1)
    c["chest.rx"] += 8 * sink; c["spine.rx"] += 3 * sink
    c["hips.tz"] = 0.008 * sink; c["hips.ty"] = -0.008 * sink + 0.003 * jerk
    c["shoulderL.raise"] += -4 * sink + 8 * jerk; c["shoulderR.raise"] += -4 * sink + 8 * jerk
    c["upperArmL.raise"] = -14 + 30 * jerk; c["upperArmR.raise"] = -14 + 30 * jerk
    c["forearmL.bend"] = 14 + 30 * jerk; c["forearmR.bend"] = 14 + 30 * jerk
    fingers(c, "L", 14 - 10 * jerk); fingers(c, "R", 14 - 10 * jerk)
    belly_bounce(c, f, 129, 1.0)
    snore = wave(f, 50, 1, 0.1)
    c["belly.s"] += 0.02 * snore
    c["jaw.rx"] = 5 + 3 * sink + 2 * snore
    c["eyelids.sy"] = 1.0 if 129 <= f < 139 else 12.0
    stand_feet(rig, c, spread=0.006, pitchL=-4 * sink, pitchR=-4 * sink)
    return c


@clip("pharaoh", "wake_jump", 54, False, markers={"jump": 6, "land": 20},
      notes="wakes with a start: jumps straight up with both arms flung high, lands with a squash and the belly "
            "bouncing (damped wobble), then holds frozen in panic, hands up by his head, knees bent, eyes wide")
def pharaoh_wake_jump(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.3)
    crouch = bump(f, 0, 7)
    air = math.sin(math.pi * (f - 6) / 14) if 6 <= f <= 20 else 0.0
    land = bump(f, 19, 30)
    hold = ease_io((f - 26) / 12)
    c["hips.ty"] = -0.010 * crouch + 0.040 * air - 0.012 * land - 0.006 * hold
    toe = 30 * air
    stand_feet(rig, c, spread=0.008, pitchL=toe, pitchR=toe, liftL=0.032 * air, liftR=0.032 * air)
    up = ease_io((f - 4) / 6)
    for s_, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{s_}.raise"] = -10 + 140 * up * (1 - 0.4 * hold) + 10 * land
        c[f"upperArm{s_}.bend"] = 10 + 10 * up + 20 * hold
        c[f"forearm{s_}.bend"] = 24 - 10 * up + 70 * hold
        c[f"forearm{s_}.twist"] = -sx * 60 * hold
        c[f"hand{s_}.bend"] = -20 * up
        fingers(c, s_, 24 - 22 * up)
    c["belly.ty"] += -0.008 * air
    belly_bounce(c, f, 20, 2.2, decay=9.0)
    c["chest.rx"] += 4 * crouch - 6 * air + 3 * land; c["head.rx"] = -5 - 10 * air + 4 * land - 3 * hold
    c["head.ry"] = 10 * bump(f, 30, 40) - 10 * bump(f, 38, 50)
    c["jaw.rx"] = 8 * up
    c["eyelids.sy"] = 12.0 if f < 3 else 1.0
    return c


@clip("pharaoh", "lean_ask", 50, False, markers={"ask": 20},
      notes="hopeful: leans forward from the hips toward the person in front, the right hand held out palm-up, the "
            "left hand on his belly, eyebrows up (curious face), a small nod of the chin; holds leaning")
def pharaoh_lean_ask(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.4)
    lean = ease_io((f - 4) / 16)
    over = bump(f, 16, 30)
    c["hips.tz"] = -0.006 * lean; c["hips.rx"] = 6 * lean; c["spine.rx"] += 8 * lean; c["chest.rx"] += 8 * lean + 2 * over
    c["neck.rx"] = -4 * lean; c["head.rx"] = -5 - 2 * lean + 3 * over; c["head.rz"] = 6 * lean
    arm_ik(c, "R", V(-0.048, 0.250, 0.110), V(-0.8, -0.6, -0.3), "root", lean)
    c["handR.twist"] = -80 * lean; c["handR.bend"] = -10; fingers(c, "R", 24 - 14 * lean)
    arm_ik(c, "L", V(0.040, 0.250, 0.060), V(0.9, -0.3, -0.3), "root", lean)
    c["handL.bend"] = 20; fingers(c, "L", 30)
    belly_bounce(c, f, 18, 0.4)
    stand_feet(rig, c, spread=0.006)
    blink(c, f, N, [26], loop=False)
    return c


@clip("pharaoh", "delighted", 60, True, markers={"clap1": 8, "clap2": 20, "clap3": 32},
      notes="overjoyed: three claps in front of his chest (above the belly), bouncing on his toes with the belly "
            "jiggling late, head tipped back laughing; then the arms swing open")
def pharaoh_delighted(rig, f, N):
    c = p_base(rig, f, N, cycles=2, amp=0.8)
    claps = [8, 20, 32]
    hit = max(bump(f, t - 6, t + 1) for t in claps)
    opn = K([(0, 0.4), (4, 0), (36, 0), (46, 1), (54, 1), (60, 0.4)], f, N, True)
    cl = 1 - opn
    sep = 0.004 + 0.030 * (1 - hit)
    for s_, sx in (("L", 1), ("R", -1)):
        arm_ik(c, s_, V(sx * sep, 0.296, 0.088), V(0.9 * sx, -0.5, -0.3), "root", cl)
        c[f"hand{s_}.twist"] = -sx * 60 * cl
        c[f"upperArm{s_}.raise"] += 60 * opn; c[f"upperArm{s_}.bend"] += 20 * opn
        c[f"forearm{s_}.twist"] += -sx * 70 * opn
        fingers(c, s_, 6)
    bounce = 0.5 - 0.5 * math.cos(2 * math.pi * f / 12)
    c["hips.ty"] = 0.004 * bounce
    stand_feet(rig, c, spread=0.006, pitchL=10 * bounce, pitchR=10 * bounce)
    c["belly.ty"] += 0.004 * math.cos(2 * math.pi * f / 12 - 1.4)
    c["belly.s"] += 0.03 * math.cos(2 * math.pi * f / 12 - 1.6)
    c["head.rx"] = -10 - 6 * hit; c["head.rz"] = 4 * wave(f, N, 1, 0.2)
    c["jaw.rx"] = 6 + 4 * hit
    blink(c, f, N, [26])
    return c


@clip("pharaoh", "crown_him", 96, False, markers={"lift": 18, "on": 36},
      notes="takes the honour from his own neck (both hands to his collar, a lift), steps forward and places it on the "
            "head of the man 0.12 in front (hands at his head height, marker `on` = show joseph/nemes and collar), "
            "presses it down gently, steps back with the hands opening proudly, ends with hands clasped on his belly, "
            "beaming")
def pharaoh_crown_him(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.3)
    toneck = ease_io((f - 2) / 12)
    lift = ease_io((f - 14) / 8)
    place = ease_io((f - 20) / 16)
    press = bump(f, 36, 46)
    back = ease_io((f - 50) / 18)
    rest = ease_io((f - 66) / 16)
    head = partner(V(0.0, 0.352, 0.000), CROWN_D)
    for s_, sx in (("L", 1), ("R", -1)):
        neck = V(0.034 * sx, 0.296, 0.036)
        over = V(0.040 * sx, 0.330 + 0.010 * lift, 0.060)
        on = head + V(0.034 * sx, 0.006 - 0.008 * press, -0.024)
        opn = V(0.120 * sx, 0.290, 0.050)
        belly = V(0.022 * sx, 0.262, 0.058)
        p = neck.lerp(over, lift).lerp(on, place).lerp(opn, back).lerp(belly, rest)
        arm_ik(c, s_, p, V(0.9 * sx, -0.4, -0.3), "root", toneck)
        c[f"hand{s_}.bend"] = 20 * place * (1 - back) + 10 * rest; c[f"hand{s_}.twist"] = -sx * 30 * place
        fingers(c, s_, 24 + 30 * toneck * (1 - back))
    step = place * (1 - back)
    c["hips.tz"] = 0.012 * step - 0.010 * rest; c["spine.rx"] += 6 * step - 3 * rest; c["chest.rx"] += 4 * step - 5 * rest
    c["head.rx"] = -5 + 4 * step - 4 * rest; c["head.rz"] = 5 * rest
    z1, h1 = stepping(f, 18, 30, 0.016); z2, h2 = stepping(f, 50, 62, -0.016)
    stand_feet(rig, c, spread=0.006, fwdL=z1 + z2, liftL=h1 + h2)
    belly_bounce(c, f, 70, 0.6)
    c["jaw.rx"] = 4 * rest
    blink(c, f, N, [6, 58, 84], loop=False)
    return c


@clip("pharaoh", "wave", 60, True,
      notes="a regal wave from his throne: the right hand raised at the shoulder, palm out, turning slowly at the "
            "wrist (a royal waggle), the left hand resting on the belly, chin up, a gracious small bow of the head")
def pharaoh_wave(rig, f, N):
    c = p_base(rig, f, N, cycles=1, amp=0.6)
    ph = 2 * math.pi * f / N
    arm_ik(c, "R", V(-0.088, 0.330, 0.050), V(-0.9, -0.6, -0.2))
    c["handR.twist"] = -60 + 34 * math.sin(2 * ph); c["handR.bend"] = -10; fingers(c, "R", 6)
    arm_ik(c, "L", V(0.040, 0.250, 0.064), V(0.9, -0.3, -0.3))
    c["handL.bend"] = 20; fingers(c, "L", 30)
    c["head.rx"] = -8 + 3 * math.sin(ph - 0.5); c["head.rz"] = 3 * math.sin(ph); c["head.ry"] = 4 * math.sin(ph - 0.3)
    c["hips.tx"] = 0.002 * math.sin(ph); c["hips.rz"] = -1.2 * math.sin(ph)
    c["belly.ty"] += 0.0015 * math.sin(2 * ph - 1.2)
    stand_feet(rig, c, spread=0.006)
    c["jaw.rx"] = 2
    blink(c, f, N, [22, 50], base=1.2)
    return c


# =============================================================================================== evaluation
HAND_SPACES = (STICK, "handL", "handR")
COAT_FOLLOW = 0.7          # Joseph's coat panels follow this much of the thigh's swing (the rest stays with the chest)


def coat_follow(rig, basis, M, w=0.85):
    Mroot3 = (M["root"] @ rig.rest["root"].inverted()).to_3x3().normalized()
    for side in "LR":
        th, pn = "thigh" + side, "coat" + side
        rest_dir = (Mroot3 @ rig.rest3[th].col[1]).normalized()
        cur_dir = M[th].to_3x3().normalized().col[1].normalized()
        R = Quaternion().slerp(rest_dir.rotation_difference(cur_dir), COAT_FOLLOW).to_matrix()
        Cm = rig.carried(M, pn).to_3x3().normalized()
        Rc = Cm @ basis[pn][0].to_matrix()
        # what the panel would be with only the root moving (hanging from the pelvis), turned by the thigh swing
        hang = Mroot3 @ rig.rest3[pn]
        want = (R @ hang).col[1].normalized()
        cur = Rc.col[1].normalized()
        Rd = cur.rotation_difference(cur.slerp(want, w)).to_matrix()
        rig.set_world_rot(basis, M, pn, Rd @ Rc)


def evaluate_primary(rig, clip_, f):
    _BLINK_OWNER[0] = rig.ch
    chs = clip_.fn(rig, f, clip_.N)
    basis = rig.basis_from(chs)
    M = rig.fk(basis)
    for limb in ("legL", "legR"):
        ik_limb(rig, basis, M, chs, limb)
    if "coatL" in rig.names:
        coat_follow(rig, basis, M, chs.get("coat.follow", 0.85))
    for limb in ("armL", "armR"):
        mx = chs.get("ikmix." + limb)
        if mx:
            tA, sA, tB, sB, m = mx
            chs["ik." + limb] = root_point(rig, M, tA, sA).lerp(root_point(rig, M, tB, sB), m)
            chs["ikspace." + limb] = "root"
    late = []
    for limb in ("armL", "armR"):
        if limb == "armR" and rig.staff_foot is not None and ("staff.foot" in chs or "staff.aim" in chs):
            continue
        if chs.get("ikspace." + limb, "root") in HAND_SPACES:
            late.append(limb); continue
        ik_limb(rig, basis, M, chs, limb)
    staff_solve(rig, basis, M, chs)
    for limb in late:
        ik_limb(rig, basis, M, chs, limb)
    return chs, basis, M


CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "joseph": [(("coatL",), 85.0, 7.5, 0.10, 18.0), (("coatR",), 85.0, 7.5, 0.10, 18.0)],
    "jacob": [(("shawl1", "shawl2"), 70.0, 8.0, 0.30, 24.0)],
    "brother": [(("bag",), 90.0, 6.5, 0.25, 22.0)],
    "pharaoh": [(("apron1",), 90.0, 7.5, 0.25, 16.0), (("belly",), 170.0, 5.0, 0.0, 10.0)],
}


def sim_chains(rig, prim, loop):
    """Damped spring chains (as Ruth). Mutates prim[f] basis/M. Loops: 3 cycles, keep the last, spread the residual
    over the cycle so frame N == frame 0."""
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
    for o in bpy.data.objects:
        if o.type == 'ARMATURE':
            o.animation_data_clear()
            reset_pose(type("R", (), {"obj": o})())
    bpy.context.view_layer.update()
    rigs = {ch: Rig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    return sc, rigs


def contract_clips():
    return {"joseph": ["idle", "talk", "walk", "run", "walk_sad", "twirl", "tell_dream", "in_pit", "carry_work",
                       "sit_cell", "bow_point_up", "explain", "stand_proud", "recognise", "ask_gently", "reveal",
                       "lift_up", "hug", "wave"],
            "jacob": ["idle", "talk", "give_coat", "weep", "walk_old", "hug"],
            "brother": ["idle", "talk", "walk", "fold_arms", "grumble", "angry_point", "grab_coat", "take_coins",
                        "bow_low", "fall_back_scared", "stand_up", "hug", "wave"],
            "pharaoh": ["idle", "talk", "doze", "wake_jump", "lean_ask", "delighted", "crown_him", "wave"]}


PROPS = ("coat", "nemes", "collar", "stick")
LOOKS = {"coat": {"coat"}, "plain": set(), "governor": {"nemes", "collar"}, None: {"coat"}}
SKINNED_PROPS = {"joseph": {"coat"}}


def hidden_props(rig, cl):
    """Prop meshes not shown with this clip in renders (Joseph's look; JS_SHOW forces some visible)."""
    if rig.ch != "joseph":
        return []
    show = set(LOOKS.get(cl.look, LOOKS[None]))
    force = {n.split("_", 1)[-1] for n in os.environ.get(ENV + "SHOW", "").split(",") if n.startswith("joseph_")}
    show |= force
    return [f"joseph_{p}" for p in ("coat", "nemes", "collar") if p not in show]


SEATED = {"joseph_in_pit", "joseph_sit_cell", "brother_bow_low", "brother_fall_back_scared", "brother_stand_up",
          "joseph_lift_up"}


def clip_checks(rig, cl, frames):
    out = {}
    ad = rig.obj.animation_data
    keep = ad.action if ad else None
    if ad:
        ad.action = None
    loc0, rot0 = rig.obj.location.copy(), rig.obj.rotation_euler.copy()
    rig.obj.location = (0, 0, 0); rig.obj.rotation_euler = (0, 0, 0)
    step = 2 if cl.action in SEATED else (3 if cl.N <= 60 else 5)
    lows, lows_all = [], []
    low_at = None
    skip = hidden_props(rig, cl)
    for fr in list(range(0, cl.N + 1, step)) + [cl.N]:
        apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
        pts = mesh_points(rig, step_n=6000)
        vis = [p for p in pts if p[1] not in skip]
        lp = min(vis, key=lambda q: q[0].y)
        lows.append(lp[0].y); lows_all.append(min(p[0].y for p in pts))
        if lp[0].y <= min(lows):
            low_at = [fr, lp[1], [round(v, 3) for v in lp[0]]]
    out["meshMinY"] = round(min(lows), 4)
    out["meshMinYAllProps"] = round(min(lows_all), 4)
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
        # slip: a stance foot's speed against the natural speed (should be equal: no skating)
        v_nat = cl.natural_speed
        worst = 0.0
        for side in "LR":
            fp = foot_points(rig, side)
            hb = rig.head["foot" + side]

            def pts(M):
                Mf = M["foot" + side] @ rig.rest["foot" + side].inverted()
                return [to_d(Mf @ to_bl(hb + q)) for q in fp]
            for fr in range(cl.N):
                A, B = pts(frames[fr][1]), pts(frames[fr + 1][1])
                ia = min(range(3), key=lambda i: A[i].y); ib = min(range(3), key=lambda i: B[i].y)
                if ia == ib and A[ia].y < 0.0006 and B[ib].y < 0.0006:
                    sl = abs((B[ib].z - A[ia].z) * FPS + v_nat)
                    if sl > worst:
                        worst = sl; out["slipAt"] = [side, fr, ia]
        out["stanceSlipMax"] = round(worst, 4)
    if rig.staff_foot is not None:
        ys = [rig.foot_of_staff(M).y for _, M in frames]
        out["stickFootY"] = [round(min(ys), 4), round(max(ys), 4)]
    reset_pose(rig)
    rig.obj.location, rig.obj.rotation_euler = loc0, rot0
    if ad:
        ad.action = keep
    return out


SAMPLE_BONES = ("head", "jaw", "handR", "handL", "footL", "toeR", "hips", "coatL", "nemes", "shawl2", "stick", "bag",
                "belly", "apron1")


def nest_skinned_props(glb, ch):
    """As pipeline/js_characters.py (Characters role): move each skinned prop's mesh node (joseph_coat) under its prop
    joint (coat) in the GLB so the engine's prop switch reaches it. glTF ignores a skinned mesh node's transform."""
    import struct
    names = SKINNED_PROPS.get(ch, set())
    if not names:
        return {}
    data = open(glb, "rb").read()
    magic, ver, total = struct.unpack_from("<III", data, 0)
    clen, ctype = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + clen].decode("utf-8"))
    rest = data[20 + clen:]
    nodes = js["nodes"]
    idx = {n.get("name"): i for i, n in enumerate(nodes)}
    moved = {}
    for b in names:
        mi, bi = idx.get(f"{ch}_{b}"), idx.get(b)
        if mi is None or bi is None or mi in nodes[bi].get("children", []):
            continue
        for n in nodes:
            if mi in n.get("children", []):
                n["children"].remove(mi)
                if not n["children"]:
                    del n["children"]
        for sc_ in js.get("scenes", []):
            if mi in sc_.get("nodes", []):
                sc_["nodes"].remove(mi)
        nodes[bi].setdefault("children", []).append(mi)
        for key in ("translation", "rotation", "scale", "matrix"):
            nodes[mi].pop(key, None)
        moved[f"{ch}_{b}"] = b
    raw = json.dumps(js, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    out = struct.pack("<III", magic, ver, 12 + 8 + len(raw) + len(rest)) + struct.pack("<II", len(raw), ctype) + raw + rest
    open(glb, "wb").write(out)
    return moved


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) <= set(have[ch]), (ch, set(want[ch]) - set(have[ch]))
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    req = TL.get("requestedClips") or []
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl, "requestedClips": req,
            "stage": {"hugDistance": HUG_D, "grabDistance": GRAB_D, "liftDistance": LIFT_D, "liftLagFrames": LIFT_LAG,
                      "giveCoatDistance": GIVE_D, "crownDistance": CROWN_D, "kneel": KNEEL["brother"], "seatY": SEAT_Y},
            "models": {ch: os.path.getmtime(os.path.join(MODEL, f"{ch}.glb")) for ch in CHARS}}
    only = os.environ.get(ENV + "ONLY")
    for cl in CLIPS:
        if only and not any(cl.action.startswith(o) for o in only.split(",")):
            continue
        rig = rigs[cl.ch]
        frames = bake_clip(rig, cl)
        write_action(rig, cl, frames)
        seam = None
        inner = None
        if cl.loop:
            M0, MN = frames[0][1], frames[-1][1]
            bn = [n for n in rig.names if n != "eyelids"]          # blinks scale the lid bone: not a pose step
            seam = max((rig.pos(M0, n, "tail") - rig.pos(MN, n, "tail")).length for n in bn)
            inner, inner_at = 0.0, None
            for i in range(cl.N):
                for n in bn:
                    dd = (rig.pos(frames[i][1], n, "tail") - rig.pos(frames[i + 1][1], n, "tail")).length
                    if dd > inner:
                        inner, inner_at = dd, (i, n)
        rootmax = max(rig.pos(M, "root").length for _, M in frames)
        info = {"action": cl.action, "char": cl.ch, "clip": cl.name, "frames": cl.N, "seconds": round(cl.N / FPS, 3),
                "loop": cl.loop, "rootMotion": False,
                "markers": {k: {"frame": v, "sec": round(v / FPS, 3)} for k, v in cl.markers.items()},
                "loopSeamMaxErr": None if seam is None else round(seam, 6),
                "loopMaxStepInside": None if inner is None else round(inner, 6),
                "rootMaxOffset": round(rootmax, 5), "look": cl.look, "notes": cl.notes}
        if cl.speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            info["stride"] = cl.speed[0]
            info["duty"] = cl.speed[1]
        if cl.action == "joseph_twirl":
            info["rootSpin"] = "root bone turns 360 deg about Y between f 9 and f 40 (no translation)"
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        print("JS_CHECK", cl.action, json.dumps(info["checks"]), flush=True)
        meta["clips"].append(info)
        print(f"JS_CLIP {cl.action} N={cl.N} loop={cl.loop} seam={info['loopSeamMaxErr']} "
              f"inner={info['loopMaxStepInside']} at={inner_at if cl.loop else None} root={info['rootMaxOffset']}", flush=True)
    if only:
        print("JS_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "js_anim.blend")
    bpy.ops.wm.save_as_mainfile(filepath=tmp_blend, compress=True)
    nested = {}
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
        path = os.path.join(ANIM, f"{ch}.glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=True,
                                  export_animation_mode='NLA_TRACKS', export_force_sampling=True, export_frame_step=1,
                                  export_def_bones=False, export_texcoords=True, export_materials='EXPORT',
                                  export_morph=any(o.type == 'MESH' and o.data.shape_keys for o in rig.children),
                                  export_optimize_animation_size=False, export_anim_slide_to_zero=False,
                                  export_rest_position_armature=True, export_negative_frame='CROP')
        nested.update(nest_skinned_props(path, ch))
        print("JS_EXPORT", ch, flush=True)
    os.remove(tmp_blend)
    meta["nestedSkinnedProps"] = nested
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("JS_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


# ----------------------------------------------------------------------------------------------- render helpers
REGIONS = json.load(open(os.path.join(MODEL, "regions_characters.json")))
FACES = {ch: {"default": REGIONS["characters"][ch]["faceDecal"]["default"],
              "clips": REGIONS["characters"][ch]["faceDecal"].get("clipExpression", {})} for ch in CHARS}
DECAL_NODES = {}
SET_HIDE = {"caravan", "grainPiles", "sacks", "dreamSheaves", "dreamStars", "dreamSheaves2", "dreamCows", "dreamGrain"}


def set_expression(ch, clip_name):
    expr = FACES[ch]["clips"].get(clip_name, FACES[ch]["default"])
    p = os.path.join(FACE_DIR, f"{ch}_{expr}.png")
    if not os.path.exists(p):
        p = os.path.join(FACE_DIR, f"{ch}_{FACES[ch]['default']}.png")
    DECAL_NODES[ch].image = bpy.data.images.load(p, check_existing=True)


def setup_scene(sc, res, samples=8):
    setup_look(sc, res, samples=samples)
    for o in bpy.data.objects:
        q = o
        while q is not None:
            if q.name.split(".")[0] in SET_HIDE:
                o.hide_render = True; break
            q = q.parent


def stage_of(cl):
    """Where a clip is shown in renders: (x, z, yaw)."""
    if cl.action == "joseph_in_pit":
        return (-0.34, 0.08, 0.0)
    if cl.action == "joseph_sit_cell":
        return (0.10, -0.06, 0.0)
    if cl.ch == "joseph":
        egypt = cl.look == "governor" or cl.name in ("carry_work", "bow_point_up", "explain")
        return (0.26, 0.06, 0.0) if egypt else (-0.16, -0.02, 0.0)
    if cl.ch == "jacob":
        return (-0.30, -0.10, 0.0)
    if cl.ch == "brother":
        return (0.22, 0.10, 0.0) if cl.name in ("bow_low", "fall_back_scared", "stand_up", "hug", "wave") else (-0.12, -0.02, 0.0)
    return (0.20, -0.20, 0.0)          # pharaoh: open sand (his THRONE mark is hidden behind the granary from q3)


PAIRS = [  # (A action, B action, distance, B frame offset, A frames, label)
    ("joseph_hug", "brother_hug", HUG_D, 0, [0, 30, 50], "pair: joseph_hug + brother_hug (0.115)"),
    ("joseph_hug", "jacob_hug", HUG_D, 0, [0, 30, 50], "pair: joseph_hug + jacob_hug (0.115)"),
    ("joseph_lift_up", "brother_stand_up", LIFT_D, LIFT_LAG, [24, 36, 56, 90], "pair: lift_up + stand_up (0.115, B +24 f)"),
    ("brother_grab_coat", "joseph_idle", GRAB_D, 0, [16, 24, 54], "pair: grab_coat + joseph_idle (0.11)"),
    ("jacob_give_coat", "joseph_idle", GIVE_D, 0, [24, 62, 96], "pair: give_coat + joseph_idle (0.12)"),
    ("pharaoh_crown_him", "joseph_explain", CROWN_D, 0, [20, 36], "pair: crown_him + joseph_explain (0.12)"),
    ("pharaoh_crown_him", "joseph_stand_proud", CROWN_D, 48, [56, 96], "pair: crown_him + stand_proud (0.12, B +48 f)"),
    ("brother_bow_low", "joseph_recognise", 0.12, 0, [44, 75], "pair: bow_low + joseph_recognise (0.12)"),
    ("brother_fall_back_scared", "joseph_reveal", 0.12, -35, [0, 45], "pair: fall_back + reveal end (0.12)"),
]


def pair_frames(ra, rb, fa, fb, D):
    apply_basis(ra, fa[0]); apply_basis(rb, fb[0])
    place_pair(None, ra, rb, D)
    bpy.context.view_layer.update()


def mode_contact():
    sc, rigs = open_scene()
    setup_scene(sc, (340, 340), samples=8)
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
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": [], "look": cl.look}
        for fr in picks:
            apply_basis(rig, frames[fr][0])
            place_rig(rig, mark[0], mark[1], mark[2])
            bpy.context.view_layer.update()
            view_cam(cam, rig, mark, "q3", dist_k=1.25)
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("JS_CONTACT_ROW", cl.action, picks, flush=True)
    for a, b, dist, off, frs, label in PAIRS:
        ca, cb = clips[a], clips[b]
        ra, rb = rigs[ca.ch], rigs[cb.ch]
        show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
        set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
        row = {"action": label, "loop": ca.loop, "frames_total": ca.N, "frames": []}
        for i, fr in enumerate(frs):
            fb = max(0, min(fr - off, cb.N))
            pair_frames(ra, rb, baked[a][fr], baked[b][fb], dist)
            for vn, cpos in (("q3", V(-0.10 + 0.34, 0.30, 0.08 + 0.38)), ("side", V(-0.10, 0.24, 0.08 + 0.52))):
                look(cam, V(-0.10, 0.16, 0.08), cpos, lens=45)
                fn = f"pair_{a}_{b}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                row["frames"].append({"f": fr, "file": fn, "marker": vn})
        reset_pose(ra); reset_pose(rb)
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """JS_PROBE="action:f1,f2:view[#bone];..."  view = front|q3|side|back|q3l|lside|top|low.
    'pair:<A>:<B>:<dist>:<frame>[:views[:B offset]]' renders two actors facing each other at that distance."""
    sc, rigs = open_scene()
    res = int(os.environ.get(ENV + "PROBE_RES", "440"))
    setup_scene(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    for fn_ in os.listdir(d):
        os.remove(os.path.join(d, fn_))
    clips = {cl.action: cl for cl in CLIPS}
    baked = {}
    out = []

    def bk(a):
        if a not in baked:
            baked[a] = bake_clip(rigs[clips[a].ch], clips[a])
        return baked[a]
    for item in os.environ.get(ENV + "PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "pair":
            a, b, dist, fr = parts[1], parts[2], float(parts[3]), int(parts[4])
            views = parts[5].split(",") if len(parts) > 5 and parts[5] else ["front", "q3", "top", "back"]
            off = int(parts[6]) if len(parts) > 6 else 0
            ca, cb = clips[a], clips[b]
            ra, rb = rigs[ca.ch], rigs[cb.ch]
            show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
            set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
            pair_frames(ra, rb, bk(a)[min(fr, ca.N)], bk(b)[max(0, min(fr - off, cb.N))], dist)
            T = V(-0.10, 0.17, 0.08)
            cams = {"front": V(-0.10, 0.20, 0.08 + 0.50), "q3": V(-0.10 + 0.36, 0.28, 0.08 + 0.36),
                    "top": V(-0.10, 0.62, 0.08 + 0.22), "back": V(-0.10, 0.22, 0.08 - 0.50),
                    "sideA": V(-0.10 - 0.45, 0.22, 0.10), "close": V(-0.10, 0.26, 0.08 + 0.26),
                    "low": V(-0.10, 0.06, 0.08 + 0.45), "phone": V(-0.10, 0.45, 0.08 + 0.60)}
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
            view_cam(cam, rig, mark, view, bone, dist_k=float(os.environ.get(ENV + "PROBE_DIST", "1.25")))
            fn = f"{action}_{fr:03d}_{view}{'_' + bone if bone else ''}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("JS_PROBE", len(out))


def dominant_groups(o):
    names = {g.index: g.name for g in o.vertex_groups}
    dom = []
    for v in o.data.vertices:
        best = max(v.groups, key=lambda g: g.weight, default=None)
        dom.append(names.get(best.group, "") if best else "")
    return dom


def world_points(rig, skip, step_n=5000):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in rig.obj.children:
        if o.type != 'MESH' or o.name.endswith("_eyelids") or o.name in skip or o.hide_render:
            continue
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        dom = DOM.setdefault(o.name, dominant_groups(o)) if o.vertex_groups else [o.name] * len(me.vertices)
        n = len(me.vertices); stp = max(1, n // step_n)
        for i in range(0, n, stp):
            pts.append((o.matrix_world @ me.vertices[i].co, dom[i] if i < len(dom) else ""))
        ev.to_mesh_clear()
    return pts


def body_bvh(rig):
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    o = bpy.data.objects[f"{rig.ch}_body"]
    ev = o.evaluated_get(dg); me = ev.to_mesh()
    vs = [o.matrix_world @ v.co for v in me.vertices]
    ps = [tuple(p.vertices) for p in me.polygons]
    ev.to_mesh_clear()
    return BVHTree.FromPolygons(vs, ps)


DOM = {}
RAYS = [Vector((0.31, 0.12, 0.94)).normalized(), Vector((-0.42, -0.27, 0.87)).normalized()]   # Blender z = up


def inside(bvh, p):
    """Ray parity in two upward directions (both odd = inside the partner's closed body)."""
    for d in RAYS:
        n, o = 0, p.copy()
        for _ in range(40):
            hit = bvh.ray_cast(o, d)
            if hit[0] is None:
                break
            n += 1; o = hit[0] + d * 1e-5
        if n % 2 == 0:
            return False
    return True
HANDS = ("handL", "handR", "fingersL", "fingersR", "forearmL", "forearmR")


def mode_paircheck():
    """For each pair: every 3rd frame, how deep A's vertices go inside B's body mesh (and B's in A's). Hands and
    forearms are reported apart (they are meant to touch)."""
    sc, rigs = open_scene()
    clips = {c.action: c for c in CLIPS}
    res = {}
    specs = PAIRS + [("joseph_hug", "brother_hug", 0.11, 0, None, "hug 0.11"), ("joseph_hug", "brother_hug", 0.12, 0, None, "hug 0.12"),
                     ("joseph_hug", "jacob_hug", 0.11, 0, None, "hug jacob 0.11"), ("joseph_hug", "jacob_hug", 0.12, 0, None, "hug jacob 0.12"),
                     ("brother_grab_coat", "joseph_idle", 0.12, 0, None, "grab 0.12"),
                     ("brother_bow_low", "joseph_recognise", 0.11, 0, None, "bow 0.11"),
                     ("joseph_lift_up", "brother_stand_up", 0.11, LIFT_LAG, None, "lift 0.11"),
                     ("joseph_lift_up", "brother_stand_up", 0.12, LIFT_LAG, None, "lift 0.12")]
    for a, b, dist, off, _, label in specs:
        ca, cb = clips[a], clips[b]
        ra, rb = rigs[ca.ch], rigs[cb.ch]
        fa_all, fb_all = bake_clip(ra, ca), bake_clip(rb, cb)
        worst = {"body": [0.0, None, None], "hands": [0.0, None, None]}
        for fr in range(0, ca.N + 1, 3):
            fb = max(0, min(fr - off, cb.N))
            pair_frames(ra, rb, fa_all[fr], fb_all[fb], dist)
            for X, Y, cx in ((ra, rb, ca), (rb, ra, cb)):
                bvh = body_bvh(Y)
                for p, g in world_points(X, hidden_props(X, cx)):
                    hit = bvh.find_nearest(p)
                    if hit[0] is None or hit[3] > 0.03 or not inside(bvh, p):
                        continue
                    depth = hit[3]
                    k = "hands" if g in HANDS else "body"
                    if depth > worst[k][0]:
                        worst[k] = [round(depth, 4), fr, f"{X.ch}.{g} in {Y.ch}"]
        res[label] = worst
        print("JS_PAIR", label, json.dumps(worst), flush=True)
        reset_pose(ra); reset_pose(rb)
    json.dump(res, open(os.path.join(WORK, "paircheck.json"), "w"), indent=1)


if IN_BLENDER:
    os.makedirs(WORK, exist_ok=True)

    def mode_debug():
        sc, rigs = open_scene()
        exec(os.environ.get(ENV + "DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))
    {"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe,
     "paircheck": mode_paircheck, "debug": mode_debug}[MODE]()
