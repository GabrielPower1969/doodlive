"""Saul Sees the Light! skeletal animation (Animation role, story pack `saul`).

Two halves in one file, the shape of pipeline/rs_animate.py:

* Under Blender (headless) it opens `assets/saul/model/characters.blend` (Characters role's rigs), builds every clip
  of docs/saul/CONTRACT.md §4 as an action `<char>_<clip>` and exports
  `assets/saul/anim/{saul,ananias,barnabas,judas,priest,tallguard,shortguard,peter}.glb` (character + skin + one glTF
  animation per action) and `clips.json`. Saul's skinned ropes node is moved under the `basket` joint after export, as
  the model GLB does (sa_characters._ropes_under_basket, run from that file, not copied).
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/sa_animate.py all        # build + verify + contact sheet + freshness check
    python3 pipeline/sa_animate.py build      # actions + GLBs + anim/clips.json (clip, pair, basket and set checks)
    python3 pipeline/sa_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/sa_animate.py contact    # anim/contact_sheet.png (key poses per clip; staged clips on the set)
    SA_PROBE="saul_basket_down:0,90,170:wbasket" python3 pipeline/sa_animate.py probe     # work renders
    SA_PROBE="pair:hug:0,30:side,q3" python3 pipeline/sa_animate.py probe                  # a PAIRS row by key
    SA_ONLY=saul_basket,ananias_pour  (with build: bake + check a subset, no export)

Reuse, not copies (CONTRACT §2, R5): this script runs pipeline/rs_animate.py in its own namespace (definitions only;
its final mode dispatch is cut off at an asserted anchor); rs_animate.py runs ls_animate.py, which runs mi_animate.py,
the same way. Every man in this pack is the Miracles friend body (and the Miracles Peter), so the Miracles friend
clips (idle, walk, wave, cheer), Peter's idle / wave / laugh, The King Who Serves' talk / boast / cheer / cross-legged
sit / kneel and He Is Risen!'s puff are the same functions baked on this pack's rigs. Nothing in mi_* / ls_* / rs_* is
edited; their clip lists are dropped and this pack registers its own.

Stage numbers the clips are fitted to: `_sa_constants()` and the marks block (docs/saul/ANIMATION.md §2).
Intermediates: $SA_ANIM_WORK (default /tmp/saul_animation).
"""
import ast, json, math, os, random, struct, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RS_PATH = os.path.join(HERE, "rs_animate.py")
SA_CHAR_PATH = os.path.join(HERE, "sa_characters.py")


def _sa_constants():
    """This pack's paths and stage numbers. Re-applied after the He Is Risen! module ran in this namespace."""
    SA = os.path.join(ROOT, "assets/saul")
    model = os.path.join(SA, "model")
    return dict(
        SADIR=SA, MODEL=model, ANIM=os.path.join(SA, "anim"), BLEND=os.path.join(model, "characters.blend"),
        SET_GLB=os.path.join(model, "damascus.glb"), TIMELINE=os.path.join(SA, "timeline.json"),
        REGIONS_JSON=os.path.join(model, "regions_characters.json"),
        EXTRAS_PAINT=os.path.join(model, "extras_paint.png"),
        FACE_DIR=os.path.join(ROOT, "docs/saul/design/faces"),
        WORK=os.environ.get("SA_ANIM_WORK") or "/tmp/saul_animation",
        ENV="SA_", BLENDER=os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender"), FPS=30,
        CHARS=("saul", "ananias", "barnabas", "judas", "priest", "tallguard", "shortguard", "peter"),
        EXTRAS=("judas", "priest", "tallguard", "shortguard", "peter"),   # fixed paint, not on the sheet
        WOMEN=(), DISCIPLES=(), SELLERS=(), FRIENDS=(),
        # stage numbers (art-width units; docs/saul/ANIMATION.md §2)
        PORCH_Y=0.04, STEP_Y=0.04,
        MAT_TOP=0.0065,             # prayer mat top (SET.md)
        BASKET_Z=-0.080,            # basket centre in Saul's root space in basket_wait / _down / _out (he climbs out
                                    # forward and ends standing on his root): his S11 mark is BASKET_DOWN + 0.08 in z
        BASKET_WAIT_Y=0.17,         # basket floor (bone head) above the base while hanging at the window
        BASKET_IN=0.011,            # the basket's inner floor above its bone head (mesh)
        ROPE_TOP=(-0.065, 0.235),   # rig-local window end of the ropes (x, y); z = BASKET_Z in the basket clips
        LEAD_D=0.14,                # walk_blind / lead_hand: the tall guard this far ahead on the same line
        HUG_D=0.10,                 # Saul / Peter hug (CONTRACT); see pairCheck
        BESIDE_D=0.10,              # Barnabas arm_round: Saul this far to his right, both facing the same way
    )


globals().update(_sa_constants())
os.environ.setdefault("RS_ANIM_WORK", WORK)       # the sister modules' scratch dirs go under ours (R11)
os.environ.setdefault("LS_ANIM_WORK", WORK)
os.environ.setdefault("MI_ANIM_WORK", WORK)

try:
    import bpy  # noqa: F401
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False


# =============================================================================================== orchestration (python3)
def run_blender(mode, *extra):
    """One Blender at a time, low priority; --python-exit-code 1 so a script crash fails the run."""
    cmd = ["nice", "-n", "10", BLENDER, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
           os.path.abspath(__file__), "--", mode, *extra]
    print("+", " ".join(cmd), flush=True)
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    tail = [ln for ln in p.stdout.splitlines() if ln.startswith((ENV, "Traceback", "Error", "  File")) or "Error" in ln]
    print("\n".join(tail[-600:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def fresh_check():
    """The Characters role may re-run sa_characters.py: the anim GLBs must be newer than the model files (A7)."""
    src = [BLEND] + [os.path.join(MODEL, f"{c}.glb") for c in CHARS]
    newest = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    outs = [os.path.join(ANIM, f"{c}.glb") for c in CHARS]
    stale = [o for o in outs if (not os.path.exists(o)) or os.path.getmtime(o) < newest]
    print("SA_FRESH", "STALE " + ", ".join(os.path.basename(o) for o in stale) if stale else
          "OK (anim exports newer than the model files)")
    return not stale


def compose_probe():
    from PIL import Image
    d = os.path.join(WORK, "probe")
    names = json.load(open(os.path.join(d, "probe.json")))
    ims = [Image.open(os.path.join(d, n)).convert("RGB") for n in names]
    if not ims:
        return
    w, h = ims[0].size
    cols = min(len(ims), int(os.environ.get("SA_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("SA_PROBE_OUT", "probe.png"))
    sheet.save(out); print("SA_PROBE_SHEET", out)


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
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 17)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 13)
    except OSError:
        font = small = ImageFont.load_default()
    d.text((pad, 14), "Saul Sees the Light! - key poses per clip (30 fps; frame / seconds; marker or view in red; "
                      "staged clips on the damascus set; pair rows = two actors at their story distance)",
           fill=(40, 30, 20), font=font)
    y = 60
    for r in rows:
        d.text((pad, y + 6), r["action"], fill=(40, 30, 20), font=font)
        d.text((pad, y + 30), f"{r['frames_total']} f  {r['frames_total'] / FPS:.2f} s", fill=(90, 80, 70), font=small)
        d.text((pad, y + 48), "loop" if r["loop"] else "one-shot (holds last)", fill=(90, 80, 70), font=small)
        x = 250
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
    print("SA_CONTACT", out, sheet.size)


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


if not IN_BLENDER:
    if __name__ == "__main__":
        main_cli()
    sys.exit(0) if __name__ == "__main__" else None


# =============================================================================================== Blender half
import bpy  # noqa: E402
from mathutils import Vector, Matrix, Quaternion  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402


def _load_risen():
    """Run pipeline/rs_animate.py (-> ls_animate.py -> mi_animate.py) in this namespace, without its final mode
    dispatch (asserted, so a change to that line fails loudly instead of running the He Is Risen! build)."""
    src = open(RS_PATH, encoding="utf-8").read()
    cut = '\n{"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, ' \
          '"debug": mode_debug}[MODE]()'
    assert src.count(cut) == 1, "rs_animate.py: the final dispatch line changed; update sa_animate._load_risen"
    g = globals()
    keep_file, keep_doc = g.get("__file__"), g.get("__doc__")
    g["__file__"] = RS_PATH
    try:
        exec(compile(src[:src.index(cut)], RS_PATH + " (definitions, run by sa_animate.py)", "exec"), g)
    finally:
        g["__file__"] = keep_file; g["__doc__"] = keep_doc


def _sa_char_fn(name):
    """One function from pipeline/sa_characters.py (the Characters role's file), compiled from its source by name."""
    tree = ast.parse(open(SA_CHAR_PATH, encoding="utf-8").read())
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    ns = {"json": json, "struct": struct}
    exec(compile(ast.Module(body=[node], type_ignores=[]), SA_CHAR_PATH, "exec"), ns)
    return ns[name]


_load_risen()
RS_FN = {c.action: c for c in CLIPS}          # He Is Risen! clips (functions kept, list dropped)
globals().update(_sa_constants())
os.makedirs(WORK, exist_ok=True)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
TL = json.load(open(TIMELINE))
CLIPS.clear()
_PAY.clear(); _BAKED.clear(); _PARTNER.clear(); _SEAT.clear()

CLOSED = {ch: 12.78 for ch in CHARS}          # RIG.md §2: eyelids.sy closed (all eight)
KNEEL = {ch: dict(KY=0.020, kz=0.016, thigh_back=10.0, shin_slope=22.0) for ch in CHARS}
ARM_REST = {"saul": -18.0, "ananias": -12.0, "barnabas": -16.0, "judas": -18.0, "priest": -16.0, "tallguard": -22.0,
            "shortguard": -8.0, "peter": -12.0}
FV = {"saul": dict(ph=0.00, amp=1.05), "ananias": dict(ph=0.23, amp=0.90), "barnabas": dict(ph=0.41, amp=1.10),
      "judas": dict(ph=0.57, amp=1.00), "priest": dict(ph=0.11, amp=0.60), "tallguard": dict(ph=0.07, amp=1.20),
      "shortguard": dict(ph=0.33, amp=0.95), "peter": dict(ph=0.0, amp=1.0)}
COAT = {}
CHAIN_FLOOR = {}
NO_GRAVITY = set()
CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "saul": [(("cloak1",), 70.0, 7.0, 0.30, 16.0)],
    "barnabas": [(("mantle1",), 70.0, 7.0, 0.30, 14.0)],
    "peter": [(("cloth1",), 90.0, 8.0, 0.30, 22.0)],
    "ananias": [], "judas": [], "priest": [], "tallguard": [], "shortguard": [],
}
PROPS = ("letters", "bread", "basket", "ropes", "jug", "lantern", "bucket")
HIDE_SET = ()

# marks (story.py 2026-11-18, SET.md) for renders and checks: (x, z)
PRIEST = (0.47, -0.42)
SAUL_PORCH = (0.42, -0.24)
LIGHT = (0.18, 0.08)
ROAD_D = (0.13, -0.01)
ROAD_E = (0.10, -0.10)
GATE_OUT = (0.09, -0.16)
ANANIAS_HOME = (-0.465, 0.08)                # staging: the house moved to the front left (SET.md)
SYN_STEP = (-0.37, -0.36)
SAUL_MAT = (-0.15, -0.46)
JUDAS_IN = (-0.21, -0.37)
JUDAS_DOOR = (-0.13, -0.27)
JUDAS_HOUSE_C = (-0.155, -0.44)               # judasHouse node origin (what face="judasHouse" turns to)
DOOR_POST = (-0.20, -0.305)                   # judasDoor: the one post (SET.md)
ANANIAS_TOUCH = (-0.08, -0.42)
ANANIAS_POUR = (-0.22, -0.42)
BASKET_DOWN = (0.095, -0.46)                  # where the basket hangs / lands (story.py)
SAUL_BASKET = (BASKET_DOWN[0], BASKET_DOWN[1] - BASKET_Z)   # Saul's mark for the basket clips (lead: story.py)
WALL_FACE_X = 0.027                           # the city wall's outside face (SET.md)
WINDOW = dict(z=(-0.495, -0.425), y=(0.20, 0.27), top=0.30)
JHOUSE_DOOR = (0.24, -0.33)                   # staging (peek_afraid arm in the house front at -0.37)
SAUL_S12 = (0.40, -0.24)
TALL_GATE = (0.12, -0.04)
SHORT_GATE = (0.19, -0.11)                    # staging (boast / doze arm in the back tower at (0.11, -0.27))
OPEN = (0.0, 0.10)


# =============================================================================================== rig
class SaRig(RsRig):
    H_OF = {"saul": 0.37, "ananias": 0.33, "barnabas": 0.39, "judas": 0.35, "priest": 0.36, "tallguard": 0.41,
            "shortguard": 0.30, "peter": 0.38}
    LIFT_BONES = ("shoulderL", "shoulderR", "cloak1")

    def __init__(self, ch, obj):
        super().__init__(ch, obj)
        # every body vertex below the waist that the cloak's shoulder / cloak1 weights carry (for `liftmin`)
        self.liftproxy = []
        if ch == "saul":
            body = bpy.data.objects[f"{ch}_body"]
            mw = obj.matrix_world.inverted() @ body.matrix_world
            gname = {g.index: g.name for g in body.vertex_groups}
            for v in body.data.vertices:
                co = mw @ v.co
                if to_d(co).y > 0.20:
                    continue
                ws = [(gname[g.group], g.weight) for g in v.groups if g.weight > 1e-3 and gname.get(g.group) in self.rest]
                tot = sum(w for _, w in ws)
                if tot > 0 and any(b in self.LIFT_BONES and w / tot > 0.1 for b, w in ws):
                    self.liftproxy.append((co, [(b, w / tot) for b, w in ws]))

    def lift_low(self, M):
        lo = 1e9
        for co, ws in self.liftproxy:
            p = Vector((0, 0, 0))
            for b, w in ws:
                p += w * ((M[b] @ self.rest_inv[b]) @ co)
            lo = min(lo, p.z)
        return lo


def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rigs = {ch: SaRig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    RIGS.clear(); RIGS.update(rigs)
    return sc, rigs


def set_world_mat(rig, basis, M, n, Mw):
    """Give bone n the armature-space matrix Mw (rotation + location) and update its subtree."""
    B = rig.carried(M, n).inverted() @ Mw
    loc, q, _ = B.decompose()
    basis[n][0] = q; basis[n][1] = loc
    rig.fk(basis, M, only=rig.subtree(n))


_rs_solve_pose = solve_pose


def solve_pose(rig, chs):
    """rs solve_pose + this pack's props:
    - `jug` / `lantern` hang from the fist: they keep their rest (hanging) orientation in the root's frame, tilted by
      `<bone>.tilt` (deg) about `<bone>.axis` (root space) - Ananias pours by tilting the jug;
    - `basket.at` (root space, the basket bone head = its floor) and `basket.rz` / `basket.rx`: the basket is placed
      there whatever the hips do (it is the hips' child in the skeleton);
    - `ropeTop.at`: the ropes' window end (root space)."""
    out = _rs_solve_pose(rig, chs)
    _, basis, M = out
    Mroot = M["root"] @ rig.rest["root"].inverted()
    Mroot3 = Mroot.to_3x3().normalized()
    for b in ("jug", "lantern"):
        if b in rig.names:
            R = Mroot3 @ rig.rest3[b]
            if chs.get(b + ".tilt"):
                R = Mroot3 @ rot_d(chs.get(b + ".axis", V(1, 0, 0)), chs[b + ".tilt"]) @ rig.rest3[b]
            rig.set_world_rot(basis, M, b, R)
    if "basket.at" in chs and "basket" in rig.names:
        R = rot_d((0, 0, 1), chs.get("basket.rz", 0.0)) @ rot_d((1, 0, 0), chs.get("basket.rx", 0.0)) @ rig.rest3["basket"]
        Mw = Mroot @ Matrix.Translation(to_bl(chs["basket.at"])) @ R.to_4x4()
        set_world_mat(rig, basis, M, "basket", Mw)
    if "ropeTop.at" in chs and "ropeTop" in rig.names:
        Mw = Mroot @ Matrix.Translation(to_bl(chs["ropeTop.at"])) @ rig.rest3["ropeTop"].to_4x4()
        set_world_mat(rig, basis, M, "ropeTop", Mw)
    return out


_mi_mix = mix


def mix(a, b, w):
    """mi mix + this pack's tuple channel `liftmin` (kept from whichever pose has it)."""
    lm = b.get("liftmin") or a.get("liftmin")
    out = _mi_mix({k: v for k, v in a.items() if k != "liftmin"}, {k: v for k, v in b.items() if k != "liftmin"}, w)
    if lm:
        out["liftmin"] = lm
    return out


_rs_evaluate_primary = evaluate_primary
CLOAK_FLOOR = -0.003


def evaluate_primary(rig, clip_, f):
    """rs evaluate_primary + `liftmin` (bones, floor): if the lowest proxy point whose dominant bone is in `bones` is
    under `floor`, the hips go up by the difference (Saul's cloak sides are skinned to the shoulders down to the hip
    line: seated on the ground they would go through it; RIG.md, reported to the lead)."""
    out = _rs_evaluate_primary(rig, clip_, f)
    chs = out[0]
    lm = chs.get("liftmin")
    if lm:
        bones, floor = lm
        if rig.liftproxy:
            low = rig.lift_low(out[2])
            if low < floor:
                chs["hips.ty"] = chs.get("hips.ty", 0.0) + (floor - low)
                out = solve_pose(rig, chs)
    return out


# =============================================================================================== registration
def reg(chs, name, N, loop, phase=True, **kw):
    """rs rclip (one function for one or several characters, free loops phase-shifted per person)."""
    return rclip(chs, name, N, loop, phase=phase, **kw)


def reuse_mi(ch, src, name=None, **over):
    ph = FV[ch]["ph"] if MI_CLIP[src].loop and not MI_CLIP[src].speed else 0.0
    return mi_reuse(ch, src, name=name, phase=ph, **over)


def local_of_mark(mark, yaw, wpt, y):
    """A world point (x, z) at height y in the root space of an actor on `mark` facing `yaw`."""
    loc = rot_y(V(wpt[0] - mark[0], 0, wpt[1] - mark[1]), -yaw)
    return V(loc.x, y, loc.z)


def to_world(mark, yaw, p, y0=0.0):
    q = rot_y(Vector(p), yaw)
    return V(q.x + mark[0], q.y + y0, q.z + mark[1])


def fv_amp(rig):
    return FV[rig.ch]["amp"]


# =============================================================================================== shared acting helpers
def shade_eyes(c, rig, w=1.0, side="L"):
    """A hand flat above the brow against the light (above the eyes, never over them: A5)."""
    sx = 1 if side == "L" else -1
    arm_ik(c, side, V(0.034 * sx, 0.024, 0.052), V(1.0 * sx, 0.4, -0.1), "head", w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 10, w)
    c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", -10 * sx), -60 * sx, w)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 4, w))


def cloak_seated(c, rig, w=1.0, deg=70.0):
    """Saul seated / kneeling / crouched: the cloak's back panel swung back and out over the ground behind him
    instead of hanging through it (RIG.md: +X rotation of cloak1 swings it back)."""
    if "cloak1" in rig.names:
        c["cloak1.rx"] = lerp(c.get("cloak1.rx", 0.0), deg, w)
        if deg >= 60.0:
            c["liftmin"] = (("shoulderL", "shoulderR", "cloak1"), CLOAK_FLOOR)


def hand_back_ground(c, side, w=1.0, z=-0.066):
    """Seated: one hand planted on the ground behind the hips (leaning back on it)."""
    sx = 1 if side == "L" else -1
    arm_ik(c, side, V(0.068 * sx, 0.012, z), V(0.6 * sx, 0.2, -1.0), "root", w)
    c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -60, w)
    fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 8, w))


def prayer_hands(c, rig, w=1.0):
    """Hands folded in front of the chest (chest space)."""
    hands_clasped(c, rig, V(0.0, -0.016, 0.050), w=w, space="chest")
    c["pole.armL"] = V(0.4, -0.9, 0.2); c["pole.armR"] = V(-0.4, -0.9, 0.2)      # elbows in (Ananias's narrow room)
    for side in "LR":
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -10, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 30, w))


def palms_up_open(c, rig, w=1.0, out=1.0, y=-0.040, z=0.062):
    """Both hands open, palms up, in front of the chest (chest space): joy, welcome, rapt."""
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V((0.050 + 0.040 * out) * sx, y, z), V(0.9 * sx, -0.6, -0.3), "chest", w)
        c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", -10 * sx), -75 * sx, w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), -14, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 6, w))


def knees_knock(c, f, amt=1.0, period=6.0):
    """Comic knocking knees: the knee poles swing inward in turn."""
    s = math.sin(2 * math.pi * f / period)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"pole.leg{side}"] = V(sx * (0.15 - 0.55 * amt * (0.5 + 0.5 * s * sx)), 0, 1)


# =============================================================================================== SAUL
reuse_mi("saul", "friend1_idle", name="idle")
reuse_mi("saul", "friend1_walk", name="walk")
reuse_mi("saul", "friend1_wave", name="wave")
reuse_mi("saul", "friend1_cheer", name="cheer")
reg("saul", "talk", 96, True, notes="friendly talk, the right hand opening palm up on the phrases, small nods "
    "[The King Who Serves d_talk, reused unchanged]")(d_talk)

MARCH = (0.066, 0.60)
MARCH_N = 30


@reg("saul", "march", MARCH_N, True, phase=False, markers={"contactL": 0, "contactR": 15}, speed=MARCH,
     notes="a stiff, stomping march (120 steps/min): flat-footed stamps with a jolt on each contact, knees lifted, "
           "chin up, chest out, fists swinging hard and straight, the cloak flapping behind")
def saul_march(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=MARCH[0], lift=0.022, duty=MARCH[1], heel=4, toeoff=12)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    stomp = pulses(f, N, [(0, 1.0), (15, 1.0)], decay=1.4)
    c["hips.ty"] = -0.003 + 0.003 * math.cos(2 * ph - 0.5) - 0.003 * stomp
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -7 * math.sin(ph - 0.3); c["head.ry"] = 2 * math.sin(ph - 0.6)
    c["hips.rz"] = 2.0 * math.cos(ph)
    c["spine.rx"] = -2; c["chest.rx"] += -5; c["neck.rx"] = -3; c["head.rx"] = -8 + 2 * stomp
    c["shoulderL.raise"] += 2 * stomp; c["shoulderR.raise"] += 2 * stomp
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -14
        c[f"upperArm{side}.bend"] = 10 + sg * 32 * math.sin(ph - 0.2)
        c[f"forearm{side}.bend"] = 18 + sg * 8 * math.sin(ph - 0.7)
        fingers(c, side, 85)
    c["cloak1.rx"] = 14 + 8 * math.sin(2 * ph - 0.8)
    c["jaw.rx"] = 1
    blink_ch(c, rig, f, N, [22])
    return c


@reg("saul", "angry_talk", 72, True, markers={"stamp": 42},
     notes="talks hot-headed: the right hand points at the listener (an open hand: one finger bone per hand) jabbing "
           "on the stressed syllables, the left fist shaking at the chest, head jutting; one stamp of the right foot "
           "per loop (`stamp`); jaw in a syllable rhythm")
def saul_angry_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.9)
    k = kH(rig)
    beats = talk_jaw(c, f, N, 31, amp=(7, 16))
    bt = beat_curve(beats, f, N, width=8)
    arm_ik(c, "R", V(-0.040, 0.262 + 0.010 * bt, 0.110 + 0.018 * bt) * k, V(-0.8, -0.5, -0.3), "root", 1.0)
    c["handR.bend"] = -6; fingers(c, "R", 8); c["forearmR.twist"] = 20
    arm_ik(c, "L", V(0.066, 0.212 + 0.012 * bt, 0.052) * k, V(0.9, -0.4, -0.3), "root", 1.0)
    fingers(c, "L", 88); c["handL.bend"] = 10
    st = pulses(f, N, [(42, 1.0)], decay=1.8)
    c["chest.rx"] += -3 - 3 * bt + 3 * st; c["head.rx"] = -4 + 5 * bt + 3 * st; c["neck.rx"] = -2
    c["hips.tz"] = 0.004 * bt
    c["shoulderL.raise"] += 3 * st; c["shoulderR.raise"] += 3 * st
    stand_feet(rig, c, spread=0.010, liftR=0.016 * bump(f, 30, 42))
    c["cloak1.rx"] = 4 * st
    blink_ch(c, rig, f, N, [12, 60])
    return c


def handoff_points():
    """The scroll hand-off (world): on the line PRIEST -> SAUL_PORCH, 0.095 from the priest, y 0.235 (priest's wrist)
    and 0.110 from the priest (Saul's wrist, a fist further on)."""
    dx, dz = SAUL_PORCH[0] - PRIEST[0], SAUL_PORCH[1] - PRIEST[1]
    L = math.hypot(dx, dz)
    u = (dx / L, dz / L)
    return (PRIEST[0] + 0.095 * u[0], PRIEST[1] + 0.095 * u[1]), (PRIEST[0] + 0.110 * u[0], PRIEST[1] + 0.110 * u[1])


TAKE_GRAB = 10


@reg("saul", "take_letters", 72, False, props=["letters"], markers={"grab": TAKE_GRAB, "up": 32, "tuck": 58},
     notes="at SAUL_PORCH facing the priest (on the porch, 0.187 away): leans in and takes the scroll from the "
           "priest's hand at `grab` (0.33 s; the timeline shows saul/letters then), holds it high and proud (chin up, "
           "chest out) at `up`, then brings it down and tucks it at his belt (right fist at the belt, the left on his "
           "hip); holds")
def saul_take_letters(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    _, sw = handoff_points()
    yaw = yaw_to(SAUL_PORCH, PRIEST)
    hw = local_of_mark(SAUL_PORCH, yaw, sw, 0.232)
    t0 = V(-0.040, 0.262, 0.110) * k                      # angry_talk's pointing hand
    up_t = V(-0.052, 0.392, 0.040) * k
    belt = V(-0.050, 0.188, 0.052) * k
    reach = ease_io(f / TAKE_GRAB)
    up = ease_io((f - 14) / 16)
    tuck = ease_io((f - 42) / 16)
    t = vlerp(vlerp(vlerp(t0, hw, reach), up_t, up), belt, tuck)
    arm_ik(c, "R", t, V(-0.8, -0.5, -0.3), "root", 1.0)
    fingers(c, "R", lerp(10, 80, ease_io((f - TAKE_GRAB + 2) / 4)))
    c["forearmR.twist"] = lerp(20, 50, up) - 40 * tuck
    c["handR.bend"] = lerp(-4, 10, tuck)
    lean = reach * (1 - up)
    c["spine.rx"] = 8 * lean; c["chest.rx"] += 4 * lean - 6 * up * (1 - tuck) - 3 * tuck; c["hips.tz"] = 0.006 * lean
    c["head.rx"] = 2 * lean - 10 * up * (1 - 0.6 * tuck); c["neck.rx"] = -3 * up
    c["head.ry"] = -6 * up * (1 - tuck)
    hand_on_hip(c, rig, "L", ease_io((f - 26) / 12))
    c["jaw.rx"] = 4 * bump(f, 28, 40)
    stand_feet(rig, c, spread=0.010)
    blink_ch(c, rig, f, N, [48], loop=False)
    return c


FALL_N = 42
SIT_N = 90


def saul_sit_base(rig, f, N, shade=1.0, cycles=3):
    """Seated in the road (legs out, the left knee up), leaning back on the right hand, looking up into the light, the
    left hand shading the eyes."""
    c = h_base(rig, f, N, cycles=cycles, amp=0.7)
    seat_legs(rig, c, "out", kneeL=0.6, kneeR=0.1)
    hand_back_ground(c, "R")
    shade_eyes(c, rig, shade, "L")
    c["spine.rx"] = c.get("spine.rx", 0.0) - 8; c["chest.rx"] += -4
    c["neck.rx"] = -8; c["head.rx"] = -14
    c["coatfollow"] = 0.0
    cloak_seated(c, rig, 1.0, 75.0)
    return c


@reg("saul", "sit_look_up", SIT_N, True, seated=True,
     notes="seated in the road, legs out (left knee up), leaning back on the right hand, the left hand shading his "
           "eyes, looking up into the light; small trembling breaths; face look_up")
def saul_sit_look_up(rig, f, N):
    c = saul_sit_base(rig, f, N)
    tr = wave(f, N, 9) * 0.8
    c["shoulderL.raise"] += 0.8 * tr; c["shoulderR.raise"] += 0.8 * tr; c["chest.rx"] += 0.6 * tr
    c["head.ry"] = 4 * wave(f, N, 1, 0.3)
    blink_ch(c, rig, f, N, [30, 72])
    return c


@reg("saul", "fall_down", FALL_N, False, seated=True, markers={"shield": 6, "bump": 21},
     notes="the light hits: the left arm flies up to shield his eyes (above them, A5), his knees give and he sits "
           "down hard on the ground (`bump` 0.7 s, a small rebound), the right hand slaps down behind him; ends as "
           "sit_look_up frame 0 (meshMinY >= -0.008)")
def saul_fall_down(rig, f, N):
    a = h_base(rig, f, N, cycles=1, amp=0.3)
    stand_feet(rig, a, spread=0.010)
    shade_eyes(a, rig, ease_io((f - 1) / 6), "L")
    fl = pulses(f, N, [(2, 1.0)], decay=1.6, loop=False)
    a["shoulderL.raise"] += 6 * fl; a["shoulderR.raise"] += 6 * fl; a["head.rx"] = 4 * fl
    a["hips.ty"] = -0.020 * ease_io((f - 6) / 8)
    b = saul_sit_base(rig, 0, SIT_N)
    t = min(1.0, max(0.0, (f - 7) / 14))
    w = t * t
    c = mix(a, b, w)
    c["hips.ty"] = c.get("hips.ty", 0.0) + 0.006 * bump(f, 21, 29)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 6 * bump(f, 19, 30)
    c["head.rx"] = c.get("head.rx", 0.0) + 5 * bump(f, 20, 28)
    c["eyelids.sy"] = 1.0 + 8.0 * bump(f, 1, 14)
    for side in "LR":                              # the legs fly out as he lands (feet off the ground while moving)
        c[f"ik.leg{side}"] = Vector(c[f"ik.leg{side}"]) + V(0, 0.018 * bump(f, 6, 30), 0)
    c["floorclamp"] = True
    return c


BLIND_N = 48
BLIND = (0.056, 0.70)                     # 0.05 u/s (V_BLIND)
HOLD_PT = V(0.004, 0.190, 0.085)          # the joined hands in Saul's root space (the guard LEAD_D ahead)


def blind_arms(c, rig, f, N, w=1.0):
    """Blind: the right hand forward holding the guard's hand (HOLD_PT), the left reaching out a little."""
    arm_ik(c, "R", HOLD_PT + V(-0.002, 0, -0.012), V(-0.8, -0.6, -0.2), "root", w)
    c["handR.bend"] = lerp(c.get("handR.bend", 6), 0, w); c["forearmR.twist"] = lerp(c.get("forearmR.twist", 10), -30, w)
    fingers(c, "R", lerp(c.get("fingersR.curl", 22), 45, w))
    k = kH(rig)
    arm_ik(c, "L", V(0.070 + 0.006 * wave(f, N, 1), 0.205 + 0.006 * wave(f, N, 1, 0.3), 0.070) * k,
           V(0.9, -0.5, -0.3), "root", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), -16, w); fingers(c, "L", lerp(c.get("fingersL.curl", 22), 10, w))
    c["forearmL.twist"] = lerp(c.get("forearmL.twist", -10), -40, w)


@reg("saul", "get_up_blind", 48, False, seated=True, markers={"push": 10, "up": 34},
     notes="from sit_look_up: lowers the shading hand, leans forward, pushes up on the right hand and slowly gets to "
           "his feet, both hands reaching out in front, turning his head, searching; face blind (the line says his "
           "eyes are open, so the lids stay open and the decal carries it); ends as walk_blind's upper body")
def saul_get_up_blind(rig, f, N):
    a = saul_sit_base(rig, 0, SIT_N, shade=1.0 - ease_io(f / 8))
    a["spine.rx"] = a.get("spine.rx", 0.0) + 22 * ease_io((f - 2) / 10)
    a["neck.rx"] = -8 + 10 * ease_io(f / 10); a["head.rx"] = -14 + 14 * ease_io(f / 10)
    b = h_base(rig, f, N, cycles=1, amp=0.4)
    stand_feet(rig, b, spread=0.010)
    blind_arms(b, rig, f, N)
    b["head.rx"] = -4
    w = ease_io((f - 8) / 26)
    c = mix(a, b, w)
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.020 * bump(f, 8, 36)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 12 * bump(f, 10, 40)
    c["head.ry"] = 16 * math.sin(2 * math.pi * (f - 30) / 24) * ease_io((f - 30) / 8)
    for side, a0 in (("L", 6), ("R", 10)):         # each foot drawn in under him off the ground
        c[f"ik.leg{side}"] = Vector(c[f"ik.leg{side}"]) + V(0, 0.016 * bump(f, a0, a0 + 28), 0)
    c["floorclamp"] = True
    return c


@reg("saul", "walk_blind", BLIND_N, True, phase=False, markers={"contactL": 0, "contactR": 24}, speed=BLIND,
     notes=f"slow careful steps (flat feet, small lift), led by the hand: the right hand forward at {HOLD_PT.z:.3f} "
           f"in front holding the tall guard's left hand (the guard LEAD_D {LEAD_D} ahead on the same line, same "
           "speed), the left hand out a little, head turning slowly, searching; face blind")
def saul_walk_blind(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=BLIND[0], lift=0.009, duty=BLIND[1], heel=4, toeoff=8)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.004 + 0.002 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 3 * math.sin(ph); c["hips.rz"] = 2 * math.cos(ph); c["chest.rz"] = -1 * math.cos(ph - 0.4)
    blind_arms(c, rig, f, N)
    c["head.ry"] = 10 * wave(f, N, 1, 0.1); c["head.rx"] = -5; c["neck.rx"] = -2
    c["chest.rx"] += 2
    blink_ch(c, rig, f, N, [36])
    return c


def sit_pray_base(rig, f, N, cycles=2, amp=0.8):
    c = seated_base(rig, f, N, "cross", cycles=cycles, amp=amp, seat=MAT_TOP)
    for side in "LR":                              # crossed feet on the mat, toes not through the page
        c[f"ik.leg{side}"] = Vector(c[f"ik.leg{side}"]) + V(0, 0.005, 0)
    prayer_hands(c, rig)
    c["neck.rx"] = 8; c["head.rx"] = 10
    cloak_seated(c, rig, 1.0, 70.0)
    return c


@reg("saul", "sit_pray", 120, True, seated=True, markers={"shake": 96},
     notes="seated cross-legged on the mat (top 0.0065), hands folded at the chest, head bowed, eyes closed, slow "
           "breathing; at `shake` (3.2 s, when Judas offers bread 3 s into S06) a small gentle head shake; face pray")
def saul_sit_pray(rig, f, N):
    c = sit_pray_base(rig, f, N)
    shk = bump(f, 94, 118)
    c["head.ry"] = 9 * math.sin(2 * math.pi * (f - 94) / 10) * shk
    c["head.rx"] += -3 * shk
    eyes(c, rig, 1.0)
    return c


@reg("saul", "see_again", 48, False, seated=True, markers={"rub": 6, "open": 20, "joy": 32},
     notes="seated cross-legged (from sit_pray, Ananias's hands on his head): blinks, rubs his eyes with both hands "
           "(0.4 s on the eyes, A5), the eyes open wide, both hands open out with joy; the head lifts only a little "
           "(Ananias's hands stay on it); face see")
def saul_see_again(rig, f, N):
    c = sit_pray_base(rig, f, N, cycles=1, amp=0.5)
    rub = ease_io((f - 2) / 5) * (1 - ease_io((f - 15) / 5))
    joy = ease_io((f - 20) / 12)
    for side, sx in (("L", 1), ("R", -1)):
        if f < 20:
            r = math.sin(2 * math.pi * (f - 4) / 6) * rub
            arm_ik2(c, side, V(0.022 * sx, 0.010 + 0.004 * r, 0.050), V(0.9 * sx, -0.7, -0.2), "head", rub)
            c[f"hand{side}.bend"] = lerp(-10, 24, rub)
        else:
            arm_ik2(c, side, V(0.100 * sx, -0.020, 0.070), V(0.9 * sx, -0.6, -0.3), "chest", joy)
            c[f"forearm{side}.twist"] = -75 * sx * joy; c[f"hand{side}.bend"] = lerp(-10, -16, joy)
            fingers(c, side, lerp(30, 4, joy))
    c["neck.rx"] = 8 - 4 * joy; c["head.rx"] = 10 - 8 * ease_io((f - 16) / 10)
    c["chest.rx"] += -4 * joy
    c["eyelids.sy"] = lerp(CLOSED[rig.ch], 1.0, ease_io((f - 1) / 3)) if f < 18 else 1.0
    c["eyelids.sy"] = max(c["eyelids.sy"], 1.0 + 11.0 * bump(f, 18, 24))
    c["jaw.rx"] = 8 * ease_io((f - 20) / 8)
    return c


def kneel_pray_fn(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    kneel_both(rig, c, 1.0, lean=0.1)
    cloak_seated(c, rig, 1.0, 35.0)
    prayer_hands(c, rig)
    c["neck.rx"] = 8; c["head.rx"] = 12
    eyes(c, rig, 1.0)
    c["floorclamp"] = True
    return c


reg("saul", "kneel", 120, True, seated=True,
    notes="on both knees, upright, head bowed, hands folded at the chest, eyes closed (S09, the jug above him)")(kneel_pray_fn)

EAT_N = 90
EAT_BITE = 36


def clear_arm(c, side):
    for k_ in ("ik.arm", "ikw.arm", "ikspace.arm", "pole.arm", "ikb.arm", "ikbw.arm", "ikbspace.arm", "ikbpole.arm"):
        c.pop(k_ + side, None)


def heels_pose(rig, f, N):
    """Kneeling, sitting back on the heels (Miracles kneel_heels legs)."""
    c = kneel_heels(rig, f, N)
    c["hips.tz"] = -0.030
    cloak_seated(c, rig, 1.0, 55.0)
    return c


@reg("saul", "eat_bread", EAT_N, False, seated=True, props=["bread"], markers={"take": 6, "bite": EAT_BITE,
                                                                               "laugh": 66},
     notes="from kneel to sitting back on the heels: takes the loaf from Judas (front-left; prop shown by the "
           "timeline just before), brings it to his mouth, a big happy bite at `bite` (1.2 s), chews (face chew), "
           "then laughs, the left hand on his belly; holds sitting on the heels with the bread")
def saul_eat_bread(rig, f, N):
    a = kneel_pray_fn(rig, 0, 120)
    a["eyelids.sy"] = 1.0
    b = heels_pose(rig, f, N)
    w = ease_io((f - 4) / 22)
    c = mix(a, b, w)
    clear_arm(c, "L"); clear_arm(c, "R")
    take = V(0.030, 0.150, 0.090)
    mouth = V(-0.004, -0.032, 0.044)
    hold = V(-0.040, 0.130, 0.070)
    t = vlerp(V(-0.011, 0.150, 0.060), take, ease_io(f / 6))
    t = vlerp(t, hold, ease_io((f - 10) / 10))
    arm_ik(c, "R", t, V(-0.8, -0.5, -0.3), "root", 1.0)
    mo = ease_io((f - 14) / 14) * (1 - ease_io((f - 48) / 12))
    arm_ik2(c, "R", mouth, V(-0.9, -0.8, 0.0), "head", mo)
    c["forearmR.twist"] = 30; c["handR.bend"] = -10; fingers(c, "R", 40)
    arm_ik(c, "L", vlerp(V(0.011, 0.150, 0.060), V(0.040, 0.075, 0.075), w), V(0.8, -0.4, -0.4), "root", 1.0)
    belly = ease_io((f - 60) / 10)
    arm_ik2(c, "L", V(0.016, -0.060, 0.062), V(0.9, -0.5, 0.0), "chest", belly)
    fingers(c, "L", 30)
    chew = bump(f, EAT_BITE, 66)
    c["jaw.rx"] = 9 * bump(f, EAT_BITE - 6, EAT_BITE + 2) + 6 * chew * (0.5 + 0.5 * math.sin(2 * math.pi * (f - 36) / 7))
    lg = pulses(f, N, [(68, 1.0), (74, 0.8), (80, 0.7)], decay=2.2, loop=False)
    env = ease_io((f - 64) / 6)
    c["jaw.rx"] += env * (8 + 4 * lg)
    c["head.rx"] = c.get("head.rx", 0.0) - 8 * env + 2 * lg + 3 * chew * math.sin(2 * math.pi * (f - 36) / 14)
    c["neck.rx"] = c.get("neck.rx", 0.0) * (1 - w)
    c["shoulderL.raise"] = c.get("shoulderL.raise", 0.0) + 3 * lg; c["shoulderR.raise"] = c.get("shoulderR.raise", 0.0) + 3 * lg
    c["eyelids.sy"] = 1.0 + 3.0 * env
    c["floorclamp"] = True
    return c


@reg("saul", "preach", 120, True,
     notes="on the top step (base y 0.04): arms opening wide to everyone (palms up), turning to the left and right "
           "listeners, then the left hand to his heart, warm and strong; jaw in a syllable rhythm")
def saul_preach(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.0)
    beats = talk_jaw(c, f, N, 57, amp=(6, 14))
    bt = beat_curve(beats, f, N, width=9)
    op = K([(0, 0.4), (16, 1.0), (50, 1.0), (62, 0.5), (90, 0.6), (108, 1.0), (120, 0.4)], f, N, True)
    heart = K([(0, 0), (60, 0), (70, 1), (92, 1), (102, 0), (120, 0)], f, N, True)
    for side, sx in (("L", 1), ("R", -1)):
        o = op * (0.85 + 0.15 * bt)
        arm_ik(c, side, V((0.070 + 0.060 * o) * sx, -0.010 + 0.030 * o, 0.060 + 0.010 * o), V(0.9 * sx, -0.6, -0.3),
               "chest", 1.0)
        c[f"forearm{side}.twist"] = -72 * sx; c[f"hand{side}.bend"] = -14; fingers(c, side, 6)
    arm_ik2(c, "L", V(0.016, -0.026, 0.050), V(0.9, -0.5, 0.0), "chest", heart)
    if heart > 0:
        c["forearmL.twist"] = lerp(-72, -10, heart); c["handL.bend"] = lerp(-14, 10, heart); fingers(c, "L", 20 * heart)
    turn = K([(0, -14), (30, -14), (54, 16), (84, 16), (108, -14), (120, -14)], f, N, True)
    c["chest.ry"] = 0.35 * turn; c["neck.ry"] = 0.3 * KL([(0, -14), (30, -14), (54, 16), (84, 16), (108, -14),
                                                           (120, -14)], f, N, True, lag=3)
    c["head.ry"] = 0.35 * KL([(0, -14), (30, -14), (54, 16), (84, 16), (108, -14), (120, -14)], f, N, True, lag=6)
    c["head.rx"] = -4 + 4 * bt; c["chest.rx"] += -3
    sh = wave(f, N, 1, 0.2)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.6 * sh
    stand_feet(rig, c, spread=0.010)
    blink_ch(c, rig, f, N, [24, 90])
    return c


# ---- the basket (S11) --------------------------------------------------------------------------------------------
BASKET_TURN = 90.0     # in the basket Saul sits turned to his left (facing +X, his back to the wall): his shoulders
                       # (0.16 wide with the cloak) do not fit between the wall face (0.027) and the believers' house
                       # (0.16) facing the viewer; turned, his depth (~0.09) does


def basket_frame(p, sway=0.0, turn=BASKET_TURN):
    """A point given in the turned sitter's frame (basket centre origin, +Z where he faces) -> root space."""
    return V(sway, 0, BASKET_Z) + rot_y(Vector(p), turn)


BASKET_KNEEL = dict(KY=0.016, kz=0.016, thigh_back=8.0, shin_slope=24.0, spread=0.0)
BK_OFFZ = 0.026        # the kneeling footprint (knee caps ... tucked toes) centred in the basket


def basket_kneel(rig, inner, sway=0.0, turn=BASKET_TURN):
    """Kneeling upright in the basket (the only pose a 0.37-tall Saul fits into a 0.10 basket: RIG.md §2), turned
    `turn`: per leg the ankle target (root space), toe pitch, knee pole; and the hips offset (tx, ty, tz)."""
    legs = {}
    hips = []
    for side, sx in (("L", 1), ("R", -1)):
        hip, knee, ankle = kneel_geom(rig, side, **BASKET_KNEEL)
        q = basket_frame(V(ankle.x, 0, ankle.z + BK_OFFZ), sway, turn)
        legs[side] = (V(q.x, inner + ankle.y, q.z), tuck_pitch(rig, side, ankle.y), rot_y(V(0.08 * sx, 0, 1), turn))
        hips.append(hip)
    hy = sum(h.y for h in hips) / 2 + inner - rig.head["thighL"].y
    hz = sum(h.z for h in hips) / 2
    h = basket_frame(V(0, 0, hz + BK_OFFZ), sway, turn)
    return legs, (h.x, hy, h.z)


def basket_seat(rig, c, floor, sway=0.0, rz=0.0, rx=0.0, settle_w=1.0):
    """Kneeling in the basket whose floor (bone head) is at `floor` (root-space y) at BASKET_Z, turned BASKET_TURN
    (his back to the wall): upright on his knees, toes tucked, hands on the rim in front of him, elbows in. The basket
    is placed by `basket.at` (solve_pose), the rope tops by `ropeTop.at` (the window)."""
    c["basket.at"] = V(sway, floor, BASKET_Z); c["basket.rz"] = rz; c["basket.rx"] = rx
    c["ropeTop.at"] = V(ROPE_TOP[0], ROPE_TOP[1], BASKET_Z)
    inner = floor + BASKET_IN
    legs, (hx, hy, hz) = basket_kneel(rig, inner, sway)
    for side, (t, pt, pole) in legs.items():
        c[f"ik.leg{side}"] = t; c[f"foot{side}.pitch"] = pt; c[f"foot{side}.ry"] = BASKET_TURN
        c[f"pole.leg{side}"] = pole
    c["hips.tx"] = c.get("hips.tx", 0.0) + hx
    c["hips.ty"] = c.get("hips.ty", 0.0) + hy
    c["hips.tz"] = c.get("hips.tz", 0.0) + hz
    c["hips.ry"] = c.get("hips.ry", 0.0) + BASKET_TURN
    c["hips.rx"] = c.get("hips.rx", 0.0) + 4
    c["nofootfix"] = True
    c["spine.rx"] = c.get("spine.rx", 0.0) + 6; c["chest.rx"] = c.get("chest.rx", 0.0) + 4
    cloak_seated(c, rig, 1.0, BASKET_CLOAK)
    c["cloak1.sy"] = BASKET_CLOAK_SY        # the cloak's back panel folded up in the basket (shorter along the bone)
    c["coatfollow"] = 0.6
    for side, sx in (("L", 1), ("R", -1)):
        t = basket_frame(V(0.026 * sx, 0, 0.040), sway)
        arm_ik(c, side, V(t.x, floor + 0.086, t.z), rot_y(V(0.3 * sx, -0.5, 1.0), BASKET_TURN), "root", 1.0)
        c[f"hand{side}.bend"] = 30; fingers(c, side, 70)


BW_N = 90
BASKET_CLOAK = -6.0
BASKET_CLOAK_SY = 0.45


@reg("saul", "basket_wait", BW_N, True, seated=True, props=["basket", "ropes"],
     notes=f"crouched in the basket hanging at the window: basket floor {BASKET_WAIT_Y} above the base, the basket "
           f"centre {-BASKET_Z} BEHIND his root (BASKET_Z: his S11 mark is BASKET_DOWN + {-BASKET_Z} in z, so that "
           "basket_out ends standing on the root); sitting on its floor, knees up, holding the front rim, peeking "
           "down left and right; the basket sways a little on its ropes; face whisper")
def saul_basket_wait(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    s = wave(f, N, 1)
    basket_seat(rig, c, BASKET_WAIT_Y, sway=0.0015 * s, rz=1.4 * s)
    c["hips.rz"] = 1.0 * s
    look = [(0, -18), (20, -18), (36, 22), (60, 22), (76, -18), (90, -18)]
    c["head.ry"] = 0.6 * K(look, f, N, True); c["neck.ry"] = 0.3 * KL(look, f, N, True, lag=4)
    c["neck.rx"] = 10; c["head.rx"] = 12
    blink_ch(c, rig, f, N, [12, 50])
    return c


BD_N = 180
BD_LAND = 168
BD_DROPS = 6


def basket_floor(f):
    """basket_down: from BASKET_WAIT_Y to 0 in six jerky drops (hand over hand above), a short rope bounce after each,
    the last drop touching down at BD_LAND."""
    step = BASKET_WAIT_Y / BD_DROPS
    y = BASKET_WAIT_Y
    for i in range(BD_DROPS):
        s0 = 8 + 30 * i
        e0 = BD_LAND if i == BD_DROPS - 1 else s0 + 10
        if f >= e0:
            y -= step
            if i < BD_DROPS - 1:
                y -= 0.0025 * math.sin(math.pi * min(1.0, (f - e0) / 8)) if f < e0 + 8 else 0.0
        elif f > s0:
            y -= step * ease_io((f - s0) / (e0 - s0)) if i < BD_DROPS - 1 else step * smooth((f - s0) / (e0 - s0))
    return max(0.0, y)


@reg("saul", "basket_down", BD_N, False, seated=True, props=["basket", "ropes"],
     markers={"drop1": 8, "drop2": 38, "drop3": 68, "drop4": 98, "drop5": 128, "drop6": 158, "land": BD_LAND},
     notes="the descent from basket_wait: the basket floor goes from 0.17 to the ground in six jerky drops (one every "
           "1.0 s, hand over hand above), a little rope bounce and a swing after each, touching down softly at `land` "
           "(5.6 s), a bump; Saul holds the rim, looks down, up at the window, down again; the ropes stretch "
           "(ropeTop stays at the window)")
def saul_basket_down(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.6)
    y = basket_floor(f)
    jolt = sum(pulses(f, N, [(8 + 30 * i + 10, 1.0)], decay=3.0, loop=False) for i in range(BD_DROPS - 1))
    s = 0.6 * math.sin(2 * math.pi * f / 40) * min(1.0, jolt)
    land = pulses(f, N, [(BD_LAND, 1.0)], decay=2.5, loop=False)
    basket_seat(rig, c, y, sway=0.0012 * s, rz=1.6 * s + 0.4 * wave(f, 90, 1), rx=1.5 * land)
    c["spine.rx"] += 5 * land + 2 * jolt; c["head.rx"] = c.get("head.rx", 0.0) + 4 * land
    lk = K([(0, 0), (40, 0), (60, 1), (100, 1), (120, 0), (180, 0)], f)
    c["neck.rx"] = 8 - 18 * lk; c["head.rx"] = c["head.rx"] + 14 - 26 * lk
    c["head.ry"] = 10 * math.sin(2 * math.pi * f / 70) * (1 - lk)
    c["shoulderL.raise"] = c.get("shoulderL.raise", 0.0) + 4 * min(1.0, jolt)
    c["shoulderR.raise"] = c.get("shoulderR.raise", 0.0) + 4 * min(1.0, jolt)
    blink_ch(c, rig, f, N, [30, 112, 150], loop=False)
    return c


BO_N = 42


@reg("saul", "basket_out", BO_N, False, props=["basket", "ropes"], markers={"stand": 10, "stepL": 21, "stepR": 30,
                                                                            "wave": 32},
     notes="from basket_down's landing: stands up in the basket and climbs out over the FRONT rim (toward the viewer: "
           "the believers' house leaves no room at +X), the left foot then the right, ending standing on his root; "
           "turns and waves up at the window behind him with the right hand, a finger of the left to his lips; holds "
           "(the timeline shrinks the basket away at 1.4 s)")
def saul_basket_out(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    c["basket.at"] = V(0, 0, BASKET_Z); c["ropeTop.at"] = V(ROPE_TOP[0], ROPE_TOP[1], BASKET_Z)
    inner = BASKET_IN
    up = ease_io(f / 10)
    turn = BASKET_TURN * (1 - ease_io((f - 1) / 12))      # turns from facing +X to the viewer as he stands
    # the feet: in the basket -> over the front rim (0.08 + toe room) -> on the ground at the root
    klegs, (khx, khy, khz) = basket_kneel(rig, inner, 0.0, turn)
    for side, sx, a0, a1 in (("L", 1, 12, 22), ("R", -1, 21, 31)):
        b = rig.head["foot" + side]
        s_ = ease_io((f - a0) / (a1 - a0))
        z0, z1 = BASKET_Z + 0.004, b.z
        y0, y1 = inner + planted_ankle_y(rig, side, 0.0), planted_ankle_y(rig, side, 0.0)
        lift = 0.092 * math.sin(math.pi * min(1.0, max(0.0, (f - a0) / (a1 - a0)))) if a0 < f < a1 else 0.0
        if f <= a0:
            sit_t, spt, _ = klegs[side]
            st_t = V(b.x + 0.004 * sx, y0, z0)
            c[f"ik.leg{side}"] = vlerp(st_t, sit_t, 1.0 - up) + V(0, 0.010 * bump(f, 2, 12), 0)
            c[f"foot{side}.pitch"] = spt * (1.0 - up)
            c[f"foot{side}.ry"] = turn
        else:
            c[f"ik.leg{side}"] = V(b.x + 0.004 * sx, lerp(y0, y1, s_) + lift, lerp(z0, z1, s_))
            c[f"foot{side}.pitch"] = -14 * bump(f, a0, a1)
        c[f"pole.leg{side}"] = rot_y(V(0.25 * sx, 0.5 * bump(f, a0, a1), 1.0), turn)
    # hips: crouched in the basket -> standing in it -> over the rim -> on the root
    _, (h0x, h0y, h0z) = basket_kneel(rig, inner, 0.0, BASKET_TURN)
    hx = lerp(h0x, 0.0, up)
    hz = lerp(h0z, BASKET_Z, up)
    hz = lerp(hz, BASKET_Z * 0.45, ease_io((f - 12) / 10))
    hz = lerp(hz, 0.0, ease_io((f - 22) / 10))
    hy_sit = h0y
    hy_st = inner * (1 - ease_io((f - 18) / 12))
    c["hips.ty"] = lerp(hy_sit, hy_st, up) - 0.010 * bump(f, 12, 32)
    c["hips.tz"] = hz
    c["hips.tx"] = hx + 0.010 * bump(f, 12, 22) - 0.010 * bump(f, 21, 31)
    c["hips.ry"] = turn
    c["hips.rx"] = lerp(4, 0, up) + 8 * bump(f, 10, 32)
    c["spine.rx"] = lerp(6, 0, up) + 10 * bump(f, 10, 32); c["chest.rx"] += lerp(4, 0, up)
    c["coatfollow"] = 0.6 * (1 - up)
    cloak_seated(c, rig, 1.0, BASKET_CLOAK * (1 - up))
    c["cloak1.sy"] = lerp(BASKET_CLOAK_SY, 1.0, up)
    # hands: on the rim while climbing, then the wave and the finger to the lips
    k = kH(rig)
    rim = 1.0 - ease_io((f - 24) / 8)
    for side, sx in (("L", 1), ("R", -1)):
        t0 = basket_frame(V(0.026 * sx, 0, 0.040), 0.0, turn)
        t1 = V(0.030 * sx, 0, BASKET_Z + 0.044)
        t = vlerp(t0, t1, ease_io((f - 4) / 10))
        arm_ik(c, side, V(t.x, 0.086, t.z), rot_y(V(0.3 * sx, -0.4, 1.0), turn), "root", rim)
        c[f"hand{side}.bend"] = 30 * rim; fingers(c, side, lerp(22, 70, rim))
    wv = ease_io((f - 26) / 8)
    if wv > 0:
        hand_wave(c, rig, "R", f, 24, 2, high=1.0, w=wv)
        arm_ik2(c, "L", V(0.004, -0.044, 0.052), V(0.9, -0.8, 0.0), "head", wv)
        fingers(c, "L", lerp(c.get("fingersL.curl", 22), 50, wv)); c["handL.bend"] = 30 * wv
    c["chest.ry"] = -22 * wv; c["neck.ry"] = -14 * wv; c["head.ry"] = -18 * wv
    c["neck.rx"] = lerp(8, -6, wv) * up + 8 * (1 - up); c["head.rx"] = lerp(10, -14, wv)
    c["nofootfix"] = True
    c["floorclamp"] = False
    blink_ch(c, rig, f, N, [36], loop=False)
    return c


def tiptoe_fn(rig, f, N, L, duty, lift, style):
    """Careful tiptoe: on the balls of the feet the whole stance, knees lifted high, a slow swing. style saul: arms
    out for balance, a finger of the left hand to the lips; style ananias: shoulders up, both hands up at the chest,
    peering ahead."""
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=L, lift=lift, duty=duty, heel=-14, toeoff=30, lift_shape=0.7)
    for side in "LR":
        t, pitch, contact, p = g["leg" + side]
        np_ = max(pitch, 16.0)
        t = Vector(t) + V(0, planted_ankle_y(rig, side, np_) - planted_ankle_y(rig, side, pitch),
                          pivot_dz(rig, side, pitch) - pivot_dz(rig, side, np_))
        c[f"ik.leg{side}"] = t; c[f"foot{side}.pitch"] = np_
        c[f"pole.leg{side}"] = V(0.15 if side == "L" else -0.15, 0.3, 1)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = 0.002 + 0.003 * math.cos(2 * ph - 0.6)
    c["hips.rz"] = 3 * math.cos(ph); c["chest.rz"] = -2 * math.cos(ph - 0.4); c["hips.ry"] = 3 * math.sin(ph)
    k = kH(rig)
    if style == "saul":
        c["spine.rx"] = 6; c["chest.rx"] += 4; c["head.rx"] = 2
        arm_ik(c, "L", V(0.004, -0.044, 0.052), V(0.9, -0.8, 0.0), "head", 1.0)
        c["handL.bend"] = 30; fingers(c, "L", 50)
        arm_ik(c, "R", V(-0.120 - 0.010 * math.cos(ph), 0.215 + 0.012 * math.sin(ph), 0.030) * k,
               V(-0.6, -0.8, 0.0), "root", 1.0)
        c["handR.bend"] = -10; fingers(c, "R", 8); c["forearmR.twist"] = 30
        c["head.ry"] = 14 * math.sin(ph * 0.5 * 2) * 0.6
    else:
        c["shoulderL.raise"] += 8; c["shoulderR.raise"] += 8
        c["spine.rx"] = 8; c["neck.rx"] = -6; c["head.rx"] = -6
        hands_clasped(c, rig, V(0.0, 0.205, 0.060) * k, wring=math.sin(2 * ph), w=1.0)
        fingers(c, "L", 50); fingers(c, "R", 50)
        c["head.ry"] = 12 * math.sin(ph)
    c["jaw.rx"] = 1
    blink_ch(c, rig, f, N, [20])
    return c


TIP_S = (0.0528, 0.55)       # 0.06 u/s with N 48
TIP_A = (0.0432, 0.60)       # 0.06 u/s with N 36
reg("saul", "tiptoe", 48, True, phase=False, markers={"contactL": 0, "contactR": 24}, speed=TIP_S,
    notes="big careful tiptoe steps on the balls of the feet, knees high, the right arm out for balance, a finger of "
          "the left hand to the lips, glancing about; face whisper")(
    lambda r, f, N: tiptoe_fn(r, f, N, TIP_S[0], TIP_S[1], 0.030, "saul"))


def hug_fn(rig, f, N):
    """Two-armed hug with the partner HUG_D in front, facing: hips back, chest leaning in, arms round the partner
    (Saul over the shoulders, Peter under the arms round the back), heads past each other (each turned to his own
    right), a small happy sway in phase (mirrored)."""
    c = h_base(rig, f, N, cycles=2, amp=0.7)
    s = hug_sway(f, N)
    m = 1 if rig.ch == "saul" else -1
    over = rig.ch == "saul"
    c["hips.tz"] = -0.014; c["hips.rx"] = 6; c["spine.rx"] = 8; c["chest.rx"] += 6
    for side, sx in (("L", 1), ("R", -1)):
        pat = 0.004 * bump((f + (0 if side == "R" else 15)) % N, 4, 14)
        if over:
            arm_ik(c, side, V(0.046 * sx, 0.262, HUG_D + 0.006 + pat), V(0.9 * sx, 0.2, -0.3), "root", 1.0)
        else:
            arm_ik(c, side, V(0.060 * sx, 0.208, HUG_D + 0.002 + pat), V(0.9 * sx, -0.4, -0.3), "root", 1.0)
        c[f"hand{side}.bend"] = 20; fingers(c, side, 40); c[f"forearm{side}.twist"] = 20 * sx
    c["hips.tx"] = 0.003 * s * m; c["hips.rz"] = -1.6 * s * m; c["chest.rz"] = 1.4 * s * m
    c["neck.ry"] = -14; c["head.ry"] = -22; c["head.rz"] = 6 + 2 * s * m; c["head.rx"] = 4
    c["jaw.rx"] = 6 + 3 * bump(f, 20, 34)
    stand_feet(rig, c, spread=0.008, fwd=-0.006)
    c["eyelids.sy"] = 4.0
    return c


reg(("saul", "peter"), "hug", 60, True, phase=False,
    notes=f"a warm two-armed hug with the partner {HUG_D} in front, facing (Saul's arms over Peter's shoulders, "
          "Peter's round Saul's back), hips back and chests leaning in, heads past each other, a small sway in phase; "
          "both start together")(hug_fn)


# =============================================================================================== ANANIAS
reuse_mi("ananias", "friend1_idle", name="idle")
reuse_mi("ananias", "friend1_walk", name="walk")
reuse_mi("ananias", "friend1_wave", name="wave")
reg("ananias", "talk", 96, True, notes="talk: the right hand opening palm up, small nods [d_talk, reused]")(d_talk)
reg("ananias", "cheer", 40, True, markers={"bounce": 10},
    notes="bouncing on the spot, the right hand waving high, the left fist pumping, cheering (feet planted: he stands "
          "beside the kneeling Saul) [The King Who Serves cheer_fn, reused]")(cheer_fn)
reg("ananias", "kneel_pray", 120, True, seated=True,
    notes="kneels, hands folded at the chest, eyes closed, head bowed, slow breathing")(kneel_pray_fn)


@reg("ananias", "kneel_look_up", 96, True, seated=True,
     notes="kneeling, looks up into the light, both hands open palms up in front, rapt, a slow sway; face look_up")
def ananias_kneel_look_up(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    kneel_both(rig, c, 1.0, lean=0.0)
    palms_up_open(c, rig, 1.0, out=0.05 + 0.05 * wave(f, N, 1), y=-0.050, z=0.066)
    c["neck.rx"] = -10; c["head.rx"] = -14 + 2 * wave(f, N, 2); c["chest.rx"] += -3
    s = wave(f, N, 1, 0.2)
    c["head.rz"] = 3 * s; c["spine.rz"] = 1.5 * s
    blink_ch(c, rig, f, N, [30, 80], slow=1.5)
    c["floorclamp"] = True
    return c


def ananias_alarm(rig, f, N):
    """Standing in alarm: hands up beside his face (palms out, eyes clear), shoulders up, knees knocking."""
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    stand_feet(rig, c, spread=0.010)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.060 * sx, -0.012, 0.030), V(0.9 * sx, -0.7, -0.2), "head", 1.0)
        c[f"forearm{side}.twist"] = -70 * sx; c[f"hand{side}.bend"] = -24; fingers(c, side, 4)
    c["shoulderL.raise"] += 8; c["shoulderR.raise"] += 8; c["chest.rx"] += -4; c["head.rx"] = -4
    c["jaw.rx"] = 9
    knees_knock(c, f, 1.0, 6.0)
    return c


@reg("ananias", "startle", 30, False, seated=True, markers={"jump": 6, "land": 16},
     notes="from kneel_look_up: jumps up to his feet in alarm (a little hop), hands up by his face (palms out, eyes "
           "clear), knees knocking, mouth open; face fright; holds")
def ananias_startle(rig, f, N):
    a = ananias_kneel_look_up(rig, 0, 96)
    b = ananias_alarm(rig, f, N)
    jump(b, rig, f, 8, 16, 0.016, crouch=0.010)
    w = ease_io((f - 1) / 9)
    c = mix(a, b, w)
    c["eyelids.sy"] = 1.0
    c["floorclamp"] = True
    return c


@reg("ananias", "nervous", 60, True, markers={"gulp": 40},
     notes="wringing his hands at his belly, knees knocking, quick glances left and right, a big gulp (`gulp`); "
           "face gulp")
def ananias_nervous(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.9)
    k = kH(rig)
    wr = math.sin(2 * math.pi * f / 15)
    hands_clasped(c, rig, V(0.0, 0.168, 0.066) * k, wring=wr, w=1.0)
    c["forearmL.twist"] = -10 + 18 * wr; c["forearmR.twist"] = 10 + 18 * wr
    fingers(c, "L", 50); fingers(c, "R", 50)
    stand_feet(rig, c, spread=0.010)
    knees_knock(c, f, 0.8, 10.0)
    look = [(0, 0), (6, -26), (18, -26), (24, 22), (34, 22), (40, 0), (60, 0)]
    c["head.ry"] = 0.7 * K(look, f, N, True); c["neck.ry"] = 0.3 * KL(look, f, N, True, lag=2)
    g = bump(f, 38, 48)
    c["head.rx"] = -2 + 6 * g; c["jaw.rx"] = 4 * g; c["shoulderL.raise"] += 6 + 3 * g; c["shoulderR.raise"] += 6 + 3 * g
    blink_ch(c, rig, f, N, [10, 52])
    return c


reg("ananias", "tiptoe", 36, True, phase=False, markers={"contactL": 0, "contactR": 18}, speed=TIP_A,
    notes="nervous little tiptoe steps on the balls of the feet, shoulders up, both hands up at the chest wringing, "
          "peering ahead and about; face gulp")(lambda r, f, N: tiptoe_fn(r, f, N, TIP_A[0], TIP_A[1], 0.018, "ananias"))


def knock_target(rig):
    """The left knuckles on the judasDoor post (SET.md: one post at (-0.20, -0.305)) from JUDAS_DOOR facing the house."""
    yaw = yaw_to(JUDAS_DOOR, JUDAS_HOUSE_C)
    p = local_of_mark(JUDAS_DOOR, yaw, DOOR_POST, 0.170)
    d = V(p.x, 0, p.z)
    return p - d.normalized() * 0.022


@reg("ananias", "knock", 30, False, markers={"knock": 6},
     notes="at JUDAS_DOOR facing judasHouse: a timid knock with the left hand on the door post (SET.md: the one post "
           "at (-0.20, -0.305), front-left of him; the knuckles aimed at it) - three small taps from `knock` (0.2 s), "
           "then steps back a little and wrings his hands; face gulp; holds")
def ananias_knock(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    tgt = knock_target(rig)
    reach = ease_io(f / 5) * (1 - ease_io((f - 18) / 7))
    tap = sum(bump(f, a0, a0 + 4) for a0 in (5, 9, 13))
    tdir = V(tgt.x, 0, tgt.z).normalized()
    arm_ik(c, "L", tgt - tdir * (0.010 * tap), V(0.9, -0.4, -0.3), "root", reach)
    c["handL.bend"] = 10; fingers(c, "L", 75); c["forearmL.twist"] = -40 * reach
    back = ease_io((f - 16) / 10)
    hands_clasped(c, rig, V(0.0, 0.168, 0.066) * k, wring=math.sin(2 * math.pi * f / 15), w=back)
    c["spine.rx"] = 6 * reach - 2 * back; c["head.rx"] = 4 * reach; c["chest.ry"] = 10 * reach
    c["shoulderL.raise"] += 4; c["shoulderR.raise"] += 4 + 3 * back
    stand_feet(rig, c, spread=0.010, fwdL=-0.012 * ease_io((f - 17) / 7), fwdR=-0.012 * ease_io((f - 21) / 6),
               liftL=0.014 * bump(f, 16, 25), liftR=0.014 * bump(f, 20, 28))
    c["hips.tz"] = -0.012 * ease_io((f - 16) / 12)
    blink_ch(c, rig, f, N, [24], loop=False)
    return c


def partner_crown(action, mark_p, mark_me, f=0, yaw_p=0.0):
    """The top of the partner's skull (highest head-skinned proxy point of that clip's primary pose at f) in my root
    space: the partner on mark_p facing yaw_p, me on mark_me facing the partner."""
    cl = next(c for c in CLIPS if c.action == action)
    rg = RIGS[cl.ch]
    _, _, M = evaluate_primary(rg, cl, f)
    top = max(rg.skin(M, {"head"}), key=lambda p: p.y)
    w = to_world(mark_p, yaw_p, top)
    return local_of_mark(mark_me, yaw_to(mark_me, mark_p), (w.x, w.z), w.y), None


HANDS_ON_W = {}


def hands_on_targets(rig):
    if rig.ch not in HANDS_ON_W:
        cr, _ = partner_crown("saul_sit_pray", SAUL_MAT, ANANIAS_TOUCH, 0)
        HANDS_ON_W[rig.ch] = cr
    return HANDS_ON_W[rig.ch]


@reg("ananias", "hands_on", 90, True,
     notes="stands beside the seated Saul (sit_pray / see_again on SAUL_MAT, Ananias on ANANIAS_TOUCH 0.08 away, "
           "facing him) and rests both hands gently on Saul's head (palms on the top of the skull of sit_pray), "
           "leaning a little, slow breathing; face brave")
def ananias_hands_on(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.7)
    cr = hands_on_targets(rig)
    side_ax = V(cr.z, 0, -cr.x).normalized()          # horizontal, across the line to Saul
    fwd = V(cr.x, 0, cr.z).normalized()
    for side, sx in (("L", 1), ("R", -1)):
        t = cr + side_ax * (0.016 * sx) + V(0, 0.011 + 0.001 * wave(f, N, 2), 0) + fwd * 0.004
        arm_ik(c, side, t, V(0.9 * sx, 0.3, -0.4), "root", 1.0)
        c[f"hand{side}.bend"] = 30; fingers(c, side, 16); c[f"forearm{side}.twist"] = -20 * sx
    c["spine.rx"] = 8; c["chest.rx"] += 4; c["neck.rx"] = 6; c["head.rx"] = 10
    stand_feet(rig, c, spread=0.010)
    blink_ch(c, rig, f, N, [30, 70], slow=1.4)
    return c


POUR_N = 72
POUR_A, POUR_B = 18, 60
POUR_W = {}


def pour_crown(rig):
    if rig.ch not in POUR_W:
        cr, _ = partner_crown("saul_kneel", SAUL_MAT, ANANIAS_POUR, 0)
        POUR_W[rig.ch] = cr
    return POUR_W[rig.ch]


@reg("ananias", "pour", POUR_N, False, props=["jug"], markers={"lift": 6, "pour": POUR_A, "stop": POUR_B},
     notes="beside the kneeling Saul (ANANIAS_POUR, 0.08 away, facing him): lifts the jug (it hangs from his right "
           "fist by the handle) over Saul's head, rising on tiptoe (he is short, Saul kneels tall), and tips it to pour (`pour` 0.6 s ... `stop` 2.0 s: the timeline "
           "plays water_pour at the jug), the left hand open, raised in blessing; then rights the jug; holds")
def ananias_pour(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    k = kH(rig)
    cr = pour_crown(rig)
    fwd = V(cr.x, 0, cr.z).normalized()
    up = ease_io((f - 2) / 14)
    rest = V(-0.090, 0.150, 0.030) * k
    over = cr + V(0, 0.072, 0) - fwd * 0.040
    arm_ik(c, "R", vlerp(rest, over, up), V(-0.8, -0.5, -0.4), "root", 1.0)
    fingers(c, "R", 80); c["handR.bend"] = 6
    tilt = ease_io((f - POUR_A + 4) / 8) * (1 - ease_io((f - POUR_B) / 8))
    c["jug.tilt"] = 70 * tilt + 5 * tilt * math.sin(2 * math.pi * f / 14)
    c["jug.axis"] = V(fwd.z, 0, -fwd.x)
    bl = ease_io((f - 10) / 12)
    arm_ik(c, "L", V(0.070, 0.250, 0.050) * k, V(0.9, -0.6, -0.3), "root", bl)
    c["forearmL.twist"] = -70 * bl; c["handL.bend"] = -20 * bl; fingers(c, "L", lerp(22, 4, bl))
    c["spine.rx"] = 8 * up; c["neck.rx"] = 6 * up; c["head.rx"] = 6 * up; c["hips.tz"] = 0.006 * up
    c["jaw.rx"] = 4 * bump(f, 22, 56)
    toe = ease_io((f - 4) / 10) * (1 - ease_io((f - POUR_B - 2) / 8))     # on tiptoe: short Ananias, kneeling Saul
    c["hips.ty"] = 0.014 * toe
    stand_feet(rig, c, spread=0.010, pitchL=26 * toe, pitchR=26 * toe)
    blink_ch(c, rig, f, N, [44], loop=False)
    return c


def listen_fn(rig, f, N):
    """Standing listening: hands loosely together low, nodding now and then, weight shifting, a happy smile."""
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    a = fv_amp(rig)
    hands_clasped(c, rig, V(0.0, 0.138, 0.050) * kH(rig), w=0.9)
    nod = sum(bump(f, a0, a0 + 10) for a0 in (18, 42, 72))
    c["head.rx"] = -2 + 7 * nod; c["neck.rx"] = 2 * nod
    sh = K([(0, -0.6), (30, -0.6), (52, 0.8), (76, 0.8), (90, -0.6), (96, -0.6)], f, N, True)
    c["hips.tx"] = 0.003 * sh * a; c["hips.rz"] = -1.8 * sh * a; c["head.rz"] = 4 + 2 * sh
    stand_feet(rig, c, spread=0.006)
    blink_ch(c, rig, f, N, [8, 60])
    return c


reg(("ananias", "judas", "tallguard", "shortguard"), "listen", 96, True,
    notes="standing listening: hands loosely together low, nodding now and then, weight shifting, smiling")(listen_fn)


# =============================================================================================== BARNABAS
reuse_mi("barnabas", "friend1_idle", name="idle")
reuse_mi("barnabas", "friend1_walk", name="walk")
reuse_mi("barnabas", "friend1_wave", name="wave")
reuse_mi("barnabas", "peter_laugh", name="laugh", props=[])
reg("barnabas", "talk", 96, True, notes="talk: the right hand opening palm up, small nods [d_talk, reused]")(d_talk)


@reg("barnabas", "arm_round", 90, True,
     notes=f"an arm round the shoulders of the person beside him: Saul {BESIDE_D} to his RIGHT (his -X), both facing "
           "the same way (toward Peter): the right forearm across behind Saul's neck, the hand on Saul's far "
           "shoulder; the left hand open toward Peter in front; a warm sway, small nods; face kind")
def barnabas_arm_round(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    k = kH(rig)
    arm_ik(c, "R", V(-BESIDE_D - 0.040, 0.276, -0.006), V(-0.3, 0.6, -1.0), "root", 1.0)
    c["handR.bend"] = 30; fingers(c, "R", 40); c["forearmR.twist"] = 30
    o = 0.85 + 0.15 * wave(f, N, 1)
    arm_ik(c, "L", V(0.070 * o, 0.215, 0.090) * k, V(0.9, -0.6, -0.3), "root", 1.0)
    c["forearmL.twist"] = -72; c["handL.bend"] = -14; fingers(c, "L", 6)
    c["chest.ry"] = -6; c["chest.rz"] = 4; c["spine.rz"] = 3
    s = wave(f, N, 1, 0.2)
    c["hips.tx"] = -0.004 + 0.002 * s; c["hips.rz"] = 1.5 * s
    nod = sum(bump(f, a0, a0 + 12) for a0 in (20, 60))
    c["head.rx"] = -2 + 6 * nod; c["head.rz"] = -5; c["head.ry"] = 6
    c["jaw.rx"] = 3 * bump(f, 30, 44)
    stand_feet(rig, c, spread=0.010, xR=-0.006)
    blink_ch(c, rig, f, N, [14, 70])
    return c


# =============================================================================================== JUDAS
reuse_mi("judas", "friend1_idle", name="idle")
reuse_mi("judas", "friend1_wave", name="wave")
reuse_mi("judas", "peter_laugh", name="laugh", props=[])


@reg("judas", "offer_bread", 60, True, props=["bread"], markers={"bow": 20},
     notes="holds the loaf out on his right palm, the left hand under it, a hopeful little bow per loop (`bow`); "
           "travel-free: a `to` on it glides (0.04 in S06): the lead swaps that for a short walk")
def judas_offer_bread(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.7)
    k = kH(rig)
    bow = bump(f, 14, 40)
    arm_ik(c, "R", V(-0.014, 0.196 - 0.010 * bow, 0.092 + 0.008 * bow) * k, V(-0.9, -0.6, -0.3), "root", 1.0)
    c["forearmR.twist"] = 70; c["handR.bend"] = -14; fingers(c, "R", 14)
    arm_ik(c, "L", V(0.016, 0.186 - 0.010 * bow, 0.086 + 0.008 * bow) * k, V(0.9, -0.6, -0.3), "root", 1.0)
    c["forearmL.twist"] = -70; c["handL.bend"] = -14; fingers(c, "L", 14)
    c["spine.rx"] = 4 + 10 * bow; c["hips.rx"] = 4 * bow; c["hips.tz"] = -0.006 * bow; c["neck.rx"] = -4 * bow
    c["head.rx"] = -2 + 4 * bow; c["head.rz"] = 6
    stand_feet(rig, c, spread=0.006)
    blink_ch(c, rig, f, N, [44])
    return c


# =============================================================================================== PRIEST
@reg("priest", "idle", 150, True,
     notes="stands calmly on the porch, hands folded in his sleeves at the chest, slow breathing, a slow look round, "
           "slow blinks; grave")
def priest_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.7)
    hands_clasped(c, rig, V(0.0, -0.040, 0.050), w=1.0, space="chest")
    fingers(c, "L", 40); fingers(c, "R", 40)
    look_keys(c, [(0, 0), (30, 0), (50, 12), (90, 12), (110, -8), (140, -8), (150, 0)], f, N)
    c["head.rx"] = 1; c["chest.rx"] += -1
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [20, 100], slow=1.6, base=1.6)
    return c


@reg("priest", "give_letters", 36, False, markers={"out": 18, "give": 30},
     notes="holds out the rolled scroll toward Saul at the foot of the steps (the priest has no scroll prop: his "
           "right fist reads as holding it until Saul's saul/letters appears), the arm out by `out` (0.6 s), lets go at "
           "`give` (1.0 s) and opens the hand: 'Go.'; holds")
def priest_give_letters(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    k = kH(rig)
    pw, _ = handoff_points()
    yaw = yaw_to(PRIEST, SAUL_PORCH)
    hw = local_of_mark(PRIEST, yaw, pw, 0.235 - PORCH_Y)
    o = ease_io((f - 1) / 17)
    st = V(-0.010, 0.215, 0.050) * k
    arm_ik(c, "R", vlerp(st, hw, o), V(-0.8, -0.6, -0.3), "root", 1.0)
    g = ease_io((f - 28) / 6)
    fingers(c, "R", lerp(lerp(40, 70, o), 6, g)); c["forearmR.twist"] = lerp(10, 40, o) + 30 * g
    c["handR.bend"] = -10 * g
    hands_clasped(c, rig, V(0.0, -0.040, 0.050), w=1.0 - o, space="chest")
    c["spine.rx"] = 4 * o; c["head.rx"] = 3 * o + 5 * bump(f, 28, 36)
    c["jaw.rx"] = 4 * bump(f, 26, 34)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [12], loop=False, slow=1.4)
    return c


# =============================================================================================== GUARDS
for _g in ("tallguard", "shortguard"):
    reuse_mi(_g, "friend1_idle", name="idle")
    reuse_mi(_g, "friend1_walk", name="walk")
reuse_mi("shortguard", "friend1_wave", name="wave")
reg("shortguard", "talk", 96, True, notes="talk: the right hand opening palm up, small nods [d_talk, reused]")(d_talk)
reg("shortguard", "boast", 72, True,
    notes="chest out, thumbs at the chest by his sash, chin up, rocking on his heels, a puffed little nod [The King "
          "Who Serves boast_fn, reused]")(boast_fn)
reg(("tallguard", "shortguard"), "puff", 60, True, markers={"breath1": 10, "breath2": 40},
    notes="bent over, hands on his knees, panting: two heaving breaths per loop, head up [He Is Risen! peter_puff, "
          "reused]")(peter_puff)

PUFF_N = {"tallguard": 24, "shortguard": 20}
PUFF_V = 0.085


def puff_stride(ch):
    return (PUFF_V * 0.5 * PUFF_N[ch] / FPS, 0.5)


def walk_puff_fn(rig, f, N):
    """A tired trot carrying the bags: short quick steps, leaning forward, fists at the chest on the bag straps
    (no bag props), the neck bobbing (late, long on the tall guard), mouth open puffing."""
    L, duty = puff_stride(rig.ch)
    c = h_base(rig, f, N, cycles=1, amp=0.6)
    g = gait(rig, f, N, L=L, lift=0.011, duty=duty, heel=6, toeoff=14)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.008 + 0.004 * math.cos(2 * ph - 0.5)
    c["hips.rx"] = 6; c["spine.rx"] = 8; c["chest.rx"] += 4
    nk = 1.6 if rig.ch == "tallguard" else 0.8
    c["neck.rx"] = -6 + 5 * nk * math.cos(2 * ph - 1.4); c["head.rx"] = -6 - 3 * nk * math.cos(2 * ph - 2.0)
    c["hips.rz"] = 3 * math.cos(ph); c["chest.rz"] = -2 * math.cos(ph - 0.5); c["hips.ry"] = 3 * math.sin(ph)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.034 * sx, -0.040 + 0.006 * math.cos(2 * ph - 0.8), 0.048), V(0.9 * sx, -0.5, -0.4),
               "chest", 1.0)
        c[f"hand{side}.bend"] = 10; fingers(c, side, 85)
    c["jaw.rx"] = 6 + 3 * (0.5 + 0.5 * math.cos(2 * ph))
    blink_ch(c, rig, f, N, [10])
    return c


for _g in ("tallguard", "shortguard"):
    reg(_g, "walk_puff", PUFF_N[_g], True, phase=False, markers={"contactL": 0, "contactR": PUFF_N[_g] // 2},
        speed=puff_stride(_g),
        notes="a tired trot carrying the bags (fists at the chest on the straps), short quick steps, leaning forward, "
              "the neck bobbing, puffing; same speed for both guards")(walk_puff_fn)


@reg(("tallguard",), "shrug", 36, False, markers={"shrug": 14},
     notes="a big shrug at the short guard: shoulders up, palms up and out, head tilted, mouth pulled; holds")
def guard_shrug(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    s = ease_io((f - 2) / 12)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.095 * sx, 0.200, 0.062) * k, V(0.9 * sx, -0.6, -0.3), "root", s)
        c[f"forearm{side}.twist"] = -78 * sx * s; c[f"hand{side}.bend"] = -18 * s; fingers(c, side, lerp(22, 4, s))
    sh = s + 0.3 * bump(f, 10, 22)
    c["shoulderL.raise"] += 10 * sh; c["shoulderR.raise"] += 10 * sh
    c["head.rz"] = 10 * s; c["neck.rx"] = -2 * s; c["head.rx"] = -4 * s
    c["jaw.rx"] = 3 * s
    stand_feet(rig, c, spread=0.008)
    blink_ch(c, rig, f, N, [20], loop=False)
    return c


@reg(("tallguard", "shortguard"), "duck", 45, False, markers={"duck": 8, "peep": 30},
     notes="crouches, both arms over his head (comic, a child hiding from thunder), then peeps out between his arms "
           "(`peep`); holds peeping")
def guard_duck(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    d = ease_io((f - 1) / 7)
    c["hips.ty"] = -0.050 * kH(rig) * d; c["hips.tz"] = -0.020 * d; c["hips.rx"] = 14 * d
    c["spine.rx"] = 20 * d; c["chest.rx"] += 10 * d; c["neck.rx"] = 12 * d; c["head.rx"] = 8 * d
    pe = ease_io((f - 28) / 8)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V((0.022 + 0.012 * pe) * sx, 0.056 - 0.006 * pe, 0.010 + 0.018 * pe), V(0.9 * sx, 0.3, 0.2),
               "head", d)
        c[f"hand{side}.bend"] = 20 * d; fingers(c, side, lerp(22, 40, d))
    c["neck.rx"] -= 10 * pe; c["head.rx"] -= 16 * pe
    c["shoulderL.raise"] += 8 * d; c["shoulderR.raise"] += 8 * d
    c["eyelids.sy"] = 1.0 + 11.0 * d * (1 - pe)
    stand_feet(rig, c, spread=0.014)
    c["floorclamp"] = True
    return c


def amazed_loop(rig, f, N):
    """Looks round for the voice, mouth open, hands half raised and open."""
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    k = kH(rig)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.082 * sx, 0.196, 0.070) * k, V(0.9 * sx, -0.6, -0.2), "root", 1.0)
        c[f"forearm{side}.twist"] = -60 * sx; c[f"hand{side}.bend"] = -10; fingers(c, side, 8)
    look = [(0, -28), (20, -28), (40, 26), (62, 26), (80, -28), (90, -28)]
    c["head.ry"] = 0.6 * K(look, f, N, True); c["neck.ry"] = 0.25 * KL(look, f, N, True, lag=4)
    c["chest.ry"] = 0.12 * KL(look, f, N, True, lag=8)
    c["head.rx"] = -6 + 3 * wave(f, N, 2); c["jaw.rx"] = 11
    c["shoulderL.raise"] += 3; c["shoulderR.raise"] += 3
    stand_feet(rig, c, spread=0.010)
    c["eyelids.sy"] = 1.0
    blink_ch(c, rig, f, N, [50])
    return c


reg(("tallguard", "shortguard"), "amazed", 90, True,
    notes="looks round for the voice (left ... right), mouth open, hands half raised and open; face amazed")(amazed_loop)


@reg("tallguard", "lead_hand", BLIND_N, True, phase=False, markers={"contactL": 0, "contactR": 24}, speed=BLIND,
     notes=f"walks slowly forward (the same gait speed as saul_walk_blind), the left arm reaching back to hold "
           f"Saul's right hand: Saul LEAD_D {LEAD_D} behind on the same line (the joined hands {HOLD_PT.z:.3f} in "
           "front of Saul); the chest turned a little to his left, glancing back over his left shoulder; the right arm "
           "swings gently")
def tallguard_lead_hand(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    g = gait(rig, f, N, L=BLIND[0], lift=0.010, duty=BLIND[1], heel=8, toeoff=14)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.004 + 0.002 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 3 * math.sin(ph); c["hips.rz"] = 2 * math.cos(ph)
    c["chest.ry"] = 10; c["spine.ry"] = 4
    hp = V(HOLD_PT.x, HOLD_PT.y, HOLD_PT.z - LEAD_D)
    arm_ik(c, "L", hp + V(0.002, 0, -0.012), V(0.9, -0.4, 0.6), "root", 1.0)
    c["handL.bend"] = 0; fingers(c, "L", 45); c["forearmL.twist"] = 40
    c["upperArmR.bend"] = 8 + 14 * math.sin(ph - 0.25); c["forearmR.bend"] = 28 + 6 * math.sin(ph - 1.0)
    look = [(0, 0), (12, 0), (18, 34), (30, 34), (36, 0), (48, 0)]
    c["head.ry"] = 0.7 * K(look, f, N, True); c["neck.ry"] = 0.3 * KL(look, f, N, True, lag=3)
    blink_ch(c, rig, f, N, [40])
    return c


@reg("tallguard", "scratch_head", 72, True,
     notes="scratching his cap with the right hand (quick little scratches), head tilted, the left hand on his hip, "
           "weight on one leg; face puzzled")
def tallguard_scratch_head(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    sc_ = math.sin(2 * math.pi * f / 6)
    arm_ik(c, "R", V(-0.030 + 0.004 * sc_, 0.070, 0.004 + 0.003 * sc_), V(-0.8, 0.5, 0.2), "head", 1.0)
    c["handR.bend"] = 30; fingers(c, "R", 50 + 10 * sc_)
    hand_on_hip(c, rig, "L", 1.0)
    c["head.rz"] = -9 + 1.5 * wave(f, N, 2); c["head.rx"] = 2; c["neck.ry"] = 6
    c["hips.tx"] = 0.005; c["hips.rz"] = -2.5
    c["jaw.rx"] = 2 + 2 * bump(f, 30, 44)
    stand_feet(rig, c, spread=0.010, fwdL=0.008)
    blink_ch(c, rig, f, N, [20, 56])
    return c


@reg("tallguard", "lantern_peer", 120, True, props=["lantern"],
     notes="holds the lantern up high in his right hand (it hangs from the fist), peers down the road, turning his "
           "head slowly left and right, leaning forward a little, the left hand on his hip")
def tallguard_lantern_peer(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.7)
    k = kH(rig)
    lk = K([(0, -24), (24, -24), (50, 22), (80, 22), (104, -24), (120, -24)], f, N, True)
    arm_ik(c, "R", V(-0.070 + 0.0006 * lk, 0.372, 0.080) * k, V(-0.8, -0.6, -0.2), "root", 1.0)
    fingers(c, "R", 80); c["handR.bend"] = 10
    hand_on_hip(c, rig, "L", 1.0)
    c["head.ry"] = 0.6 * lk; c["neck.ry"] = 0.3 * KL([(0, -24), (24, -24), (50, 22), (80, 22), (104, -24),
                                                        (120, -24)], f, N, True, lag=4)
    c["chest.ry"] = 0.15 * lk
    c["spine.rx"] = 5; c["neck.rx"] = -4; c["head.rx"] = 2
    stand_feet(rig, c, spread=0.010)
    blink_ch(c, rig, f, N, [36, 96])
    return c


@reg("tallguard", "wave", 48, True,
     notes="a shy wave: the right hand at shoulder height waving from the wrist, head tilted, the left hand behind "
           "his back, a little sway")
def tallguard_wave(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    hand_wave(c, rig, "R", f, N, 3, high=0.0)
    arm_ik(c, "L", V(0.030, 0.180, -0.050) * kH(rig), V(0.9, -0.4, 0.4), "root", 1.0)
    fingers(c, "L", 40)
    sh = wave(f, N, 1)
    c["hips.tx"] = 0.003 * sh; c["hips.rz"] = -1.4 * sh; c["head.rz"] = 9 + 2 * sh; c["head.rx"] = 4
    stand_feet(rig, c, spread=0.006)
    blink_ch(c, rig, f, N, [16])
    return c


@reg("shortguard", "doze", 120, True, markers={"jerk1": 52, "jerk2": 118},
     notes="falls asleep standing: the head sinks slowly forward and jerks up (twice per loop), a small sway, eyes "
           "closed, arms hanging, mouth a little open breathing; face asleep (the timeline adds zzz)")
def shortguard_doze(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.2)
    nod = [(0, 4), (8, 4), (46, 24), (52, 27), (56, 3), (66, 4), (110, 22), (116, 25), (118, 6), (120, 4)]
    c["neck.rx"] = 0.45 * K(nod, f, N, True); c["head.rx"] = 0.6 * KL(nod, f, N, True, lag=1.5)
    c["spine.rx"] = 3 + 0.1 * K(nod, f, N, True)
    s = wave(f, N, 1, 0.1)
    c["hips.tx"] = 0.003 * s; c["hips.rz"] = -2.0 * s; c["chest.rz"] = 1.2 * s; c["head.rz"] = 3 * s
    for side in "LR":
        c[f"upperArm{side}.raise"] = ARM_REST[rig.ch] - 4; c[f"forearm{side}.bend"] = 14; fingers(c, side, 30)
    c["jaw.rx"] = 3 + 2 * (0.5 + 0.5 * wave(f, N, 2))
    stand_feet(rig, c, spread=0.010)
    eyes(c, rig, 1.0)
    return c


# =============================================================================================== PETER
reuse_mi("peter", "peter_idle", name="idle")
reuse_mi("peter", "peter_wave", name="wave")


@reg("peter", "peek_afraid", 45, False, markers={"peek": 10, "back": 26},
     notes="at JHOUSE_DOOR facing Saul: leans out to look (`peek`), then shrinks back (`back`: weight back, a "
           "nervous little foot lift, shoulders up, leaning away, hands up palms out at the chest); his face stays turned to Saul and visible; "
           "face afraid; holds")
def peter_peek_afraid(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    lean = ease_io(f / 10) * (1 - ease_io((f - 16) / 10))
    back = ease_io((f - 16) / 12)
    c["spine.rx"] = 12 * lean - 6 * back; c["neck.rx"] = -6 * lean + 6 * back; c["head.rx"] = -4 * lean
    c["hips.tz"] = 0.010 * lean - 0.006 * back; c["hips.rx"] = 4 * lean
    c["chest.ry"] = 8 * lean
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.050 * sx, 0.252, 0.072) * k, V(0.9 * sx, -0.7, -0.2), "root", back)
        c[f"forearm{side}.twist"] = -70 * sx * back; c[f"hand{side}.bend"] = -24 * back; fingers(c, side, lerp(22, 4, back))
    c["shoulderL.raise"] += 9 * back; c["shoulderR.raise"] += 9 * back
    stand_feet(rig, c, spread=0.010, liftR=0.008 * bump(f, 16, 24))
    c["jaw.rx"] = 6 * back
    c["eyelids.sy"] = 1.0
    blink_ch(c, rig, f, N, [36], loop=False)
    return c


# =============================================================================================== checks
def contract_clips():
    return {
        "saul": ["idle", "walk", "march", "angry_talk", "take_letters", "fall_down", "sit_look_up", "get_up_blind",
                 "walk_blind", "sit_pray", "see_again", "kneel", "eat_bread", "preach", "talk", "basket_wait",
                 "basket_down", "basket_out", "tiptoe", "hug", "wave", "cheer"],
        "ananias": ["idle", "walk", "talk", "kneel_pray", "kneel_look_up", "startle", "nervous", "tiptoe", "knock",
                    "hands_on", "pour", "listen", "cheer", "wave"],
        "barnabas": ["idle", "walk", "talk", "laugh", "wave", "arm_round"],
        "judas": ["idle", "listen", "laugh", "wave", "offer_bread"],
        "priest": ["idle", "give_letters"],
        "tallguard": ["idle", "walk", "walk_puff", "puff", "shrug", "duck", "amazed", "lead_hand", "listen",
                      "scratch_head", "lantern_peer", "wave"],
        "shortguard": ["idle", "walk", "talk", "listen", "amazed", "walk_puff", "puff", "duck", "boast", "doze",
                       "wave"],
        "peter": ["idle", "peek_afraid", "hug", "wave"]}


def barnabas_mark():
    """S12 as the clip assumes it: Barnabas at (0.30, -0.22) facing Peter at JHOUSE_DOOR."""
    m = (0.30, -0.22)
    return m, yaw_to(m, JHOUSE_DOOR)


def stage_of(cl):
    """Where a clip is shown in renders and set checks: (x, z, yaw, y, on_set)."""
    n, ch = cl.name, cl.ch
    if ch == "priest":
        return (PRIEST[0], PRIEST[1], yaw_to(PRIEST, SAUL_PORCH), PORCH_Y, True)
    if n in ("take_letters", "angry_talk") and ch == "saul":
        return (SAUL_PORCH[0], SAUL_PORCH[1], yaw_to(SAUL_PORCH, PRIEST), 0.0, True)
    if n in ("fall_down", "sit_look_up", "get_up_blind"):
        return (LIGHT[0], LIGHT[1], 0.0, 0.0, True)
    if n in ("sit_pray", "see_again", "kneel", "eat_bread"):
        return (SAUL_MAT[0], SAUL_MAT[1], 0.0, 0.0, True)
    if n == "preach":
        return (SYN_STEP[0], SYN_STEP[1], 0.0, STEP_Y, True)
    if n.startswith("basket_"):
        return (SAUL_BASKET[0], SAUL_BASKET[1], 0.0, 0.0, True)
    if ch == "ananias" and n in ("kneel_pray", "kneel_look_up", "startle", "nervous"):
        return (ANANIAS_HOME[0], ANANIAS_HOME[1], 0.0, 0.0, True)
    if n == "knock":
        return (JUDAS_DOOR[0], JUDAS_DOOR[1], yaw_to(JUDAS_DOOR, JUDAS_HOUSE_C), 0.0, True)
    if n == "hands_on":
        return (ANANIAS_TOUCH[0], ANANIAS_TOUCH[1], yaw_to(ANANIAS_TOUCH, SAUL_MAT), 0.0, True)
    if n == "pour":
        return (ANANIAS_POUR[0], ANANIAS_POUR[1], yaw_to(ANANIAS_POUR, SAUL_MAT), 0.0, True)
    if n == "lantern_peer":
        return (TALL_GATE[0], TALL_GATE[1], 0.0, 0.0, True)
    if n in ("doze", "boast"):
        return (SHORT_GATE[0], SHORT_GATE[1], 0.0, 0.0, True)
    if n == "peek_afraid":
        return (JHOUSE_DOOR[0], JHOUSE_DOOR[1], yaw_to(JHOUSE_DOOR, SAUL_S12), 0.0, True)
    if n == "offer_bread":
        return (JUDAS_IN[0], JUDAS_IN[1], yaw_to(JUDAS_IN, SAUL_MAT), 0.0, True)     # staging: offered in place
    return (OPEN[0], OPEN[1], 0.0, 0.0, False)


SET_BVH = {}


def load_set_bvh():
    """Import damascus.glb: world-space BVH trees (Blender coords) per mesh node, except the floor-like nodes."""
    if SET_BVH:
        return SET_BVH
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SET_GLB)
    new = [o for o in bpy.data.objects if o not in before]
    skip = {"ground", "road", "straightStreet", "prayerMat"}
    for o in new:
        if o.type == 'MESH' and o.name.split(".")[0] not in skip:
            mw = o.matrix_world
            SET_BVH[o.name.split(".")[0]] = BVHTree.FromPolygons([mw @ v.co for v in o.data.vertices],
                                                                 [list(p.vertices) for p in o.data.polygons])
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    return SET_BVH


def set_checks():
    """Per staged clip on its story mark with the real set: proxy points (above the floor zone) inside set meshes,
    counted by set node and body bone."""
    bv = load_set_bvh()
    out = {}
    for cl in CLIPS:
        x, z, yaw, y, on = stage_of(cl)
        if not on:
            continue
        rig = RIGS[cl.ch]
        frames = bake_clip(rig, cl)
        res = {"mark": [round(x, 4), round(z, 4), round(yaw, 1), y], "inside": 0, "insideBy": {}}
        for fr in range(0, cl.N + 1, 4):
            M = frames[fr][1]
            for p, dom in world_pts(rig, M, (x, z, yaw, y)):
                if p.y - y < 0.012:
                    continue
                for nd, t in bv.items():
                    if inside(t, p)[0]:
                        res["inside"] += 1
                        k_ = f"{nd}:{dom}"
                        res["insideBy"][k_] = res["insideBy"].get(k_, 0) + 1
        out[cl.action] = res
        print("SA_SET", cl.action, json.dumps(res), flush=True)
    return out


def basket_check():
    """The basket clips at SAUL_BASKET facing the viewer: the basket's wall-side edge and Saul's body vs the wall face
    (x WALL_FACE_X), the rope tops vs the window opening, the basket floor height, Saul's lowest point."""
    rig = RIGS["saul"]
    mark = (SAUL_BASKET[0], SAUL_BASKET[1], 0.0, 0.0)
    out = {}
    R = 0.0534                                             # basket rim radius (mesh)
    for name in ("saul_basket_wait", "saul_basket_down", "saul_basket_out"):
        cl = next(c for c in CLIPS if c.action == name)
        frames = bake_clip(rig, cl)
        bmin, body_min, tops, floors, bodylow = 9.0, 9.0, [], [], 9.0
        for fr in range(0, cl.N + 1, 2):
            M = frames[fr][1]
            b = to_world(mark[:2], 0.0, rig.pos(M, "basket"))
            bmin = min(bmin, b.x - R)
            floors.append(b.y)
            t = to_world(mark[:2], 0.0, rig.pos(M, "ropeTop"))
            tops.append((round(t.x, 4), round(t.y, 4), round(t.z, 4)))
            pts = [p for p, d in world_pts(rig, M, mark)]
            body_min = min(body_min, min(p.x for p in pts))
            bodylow = min(bodylow, min(p.y for p in pts))
        tz = [t[2] for t in tops]; ty = [t[1] for t in tops]
        out[name] = {"basketEdgeToWall": round(bmin - WALL_FACE_X, 4), "bodyToWall": round(body_min - WALL_FACE_X, 4),
                     "basketFloorRange": [round(min(floors), 4), round(max(floors), 4)],
                     "ropeTopY": [min(ty), max(ty)], "ropeTopZ": [min(tz), max(tz)],
                     "ropeTopInWindow": all(WINDOW["z"][0] + 0.007 < t[2] < WINDOW["z"][1] - 0.007 and
                                            WINDOW["y"][0] < t[1] < WINDOW["y"][1] for t in tops),
                     "bodyProxyMinY": round(bodylow, 4)}
    print("SA_BASKET", json.dumps(out))
    return out


def pairs():
    """(key, A action, markA, B action, markB, B frame lag): marks (x, z, yaw, y) as the story stages them."""
    hold_d = LEAD_D
    bm, byaw = barnabas_mark()
    beside = to_world(bm, byaw, V(-BESIDE_D, 0, 0))
    a_y = yaw_to(ANANIAS_TOUCH, SAUL_MAT); p_y = yaw_to(ANANIAS_POUR, SAUL_MAT)
    return [
        ("lead", "saul_walk_blind", (0.0, 0.10, 0.0, 0.0), "tallguard_lead_hand", (0.0, 0.10 + hold_d, 0.0, 0.0)),
        ("hug", "saul_hug", (0.0, 0.10, 0.0, 0.0), "peter_hug", (0.0, 0.10 + HUG_D, 180.0, 0.0)),
        ("hands_on", "ananias_hands_on", (ANANIAS_TOUCH[0], ANANIAS_TOUCH[1], a_y, 0.0), "saul_sit_pray",
         (SAUL_MAT[0], SAUL_MAT[1], 0.0, 0.0)),
        ("hands_on_see", "ananias_hands_on", (ANANIAS_TOUCH[0], ANANIAS_TOUCH[1], a_y, 0.0), "saul_see_again",
         (SAUL_MAT[0], SAUL_MAT[1], 0.0, 0.0)),
        ("pour", "ananias_pour", (ANANIAS_POUR[0], ANANIAS_POUR[1], p_y, 0.0), "saul_kneel",
         (SAUL_MAT[0], SAUL_MAT[1], 0.0, 0.0)),
        ("arm_round", "barnabas_arm_round", (bm[0], bm[1], byaw, 0.0), "saul_idle", (beside.x, beside.z, byaw, 0.0)),
        ("letters", "priest_give_letters", (PRIEST[0], PRIEST[1], yaw_to(PRIEST, SAUL_PORCH), PORCH_Y),
         "saul_take_letters", (SAUL_PORCH[0], SAUL_PORCH[1], yaw_to(SAUL_PORCH, PRIEST), 0.0)),
    ]


ARM_BONES = {"upperArmL", "upperArmR", "forearmL", "forearmR", "handL", "handR", "fingersL", "fingersR"}
HAND_BONES = ("handL", "handR", "fingersL", "fingersR")


def pair_check():
    clips = {c.action: c for c in CLIPS}
    out = {}
    for key, a, ma, b, mb in pairs():
        ca, cb = clips[a], clips[b]
        ra, rb = RIGS[ca.ch], RIGS[cb.ch]
        fa, fb = bake_clip(ra, ca), bake_clip(rb, cb)
        body, hands, allmin = (1.0, 0, 0), (1.0, 0), (1.0, 0, 0)
        for fr in range(0, max(ca.N, cb.N) + 1, 3):
            Ma = fa[fr % ca.N if ca.loop else min(fr, ca.N)][1]
            Mb = fb[fr % cb.N if cb.loop else min(fr, cb.N)][1]
            pa = world_pts(ra, Ma, ma); pb = world_pts(rb, Mb, mb)
            d = pair_min_dist([p for p, dm in pa if dm not in ARM_BONES], [p for p, dm in pb if dm not in ARM_BONES],
                              eps=0.03)
            if d[0] < body[0]:
                body = (d[0], d[1], fr)
            d2 = pair_min_dist([p for p, dm in pa], [p for p, dm in pb], eps=0.03)
            if d2[0] < allmin[0]:
                allmin = (d2[0], d2[1], fr)
            ha = [p for p, dm in pa if dm in HAND_BONES]
            hb = [p for p, dm in pb if dm in HAND_BONES]
            hd = pair_min_dist(ha, hb, eps=0.04)[0]
            if hd < hands[0]:
                hands = (hd, fr)
        out[key] = {"pair": f"{a} + {b}", "bodyMinDist(no arms)": body[0], "bodyPointsCloser4mm": body[1],
                    "atFrame": body[2], "anyMinDist": allmin[0], "anyPointsCloser4mm": allmin[1],
                    "handsMinDist": round(hands[0], 4), "handsAtFrame": hands[1]}
    # the hand-in-hand walk at other spacings (the hands' gap only)
    for dd in (0.12, 0.14):
        ca, cb = clips["saul_walk_blind"], clips["tallguard_lead_hand"]
        fa, fb = bake_clip(RIGS["saul"], ca), bake_clip(RIGS["tallguard"], cb)
        best = 1.0
        for fr in range(0, ca.N + 1, 3):
            Ma, Mb = fa[fr][1], fb[fr][1]
            ha = [p for p, dm in world_pts(RIGS["saul"], Ma, (0, 0, 0, 0)) if dm in HAND_BONES]
            hb = [p for p, dm in world_pts(RIGS["tallguard"], Mb, (0, dd, 0, 0)) if dm in HAND_BONES]
            best = min(best, pair_min_dist(ha, hb, eps=0.05)[0])
        out[f"lead@{dd}"] = {"handsMinDist": round(best, 4)}
    return out


SAMPLE_BONES = ("root", "head", "jaw", "handR", "handL", "footL", "footR", "hips", "cloak1", "mantle1", "cloth1",
                "letters", "bread", "basket", "ropeTop", "jug", "lantern")


def mode_build():
    sc, rigs = open_scene()
    want = contract_clips()
    have = {ch: [c.name for c in CLIPS if c.ch == ch] for ch in CHARS}
    for ch in CHARS:
        assert set(want[ch]) == set(have[ch]), (ch, set(want[ch]) - set(have[ch]), set(have[ch]) - set(want[ch]))
        assert len(have[ch]) == len(set(have[ch])), (ch, "duplicate clip")
    missing_tl = [f"{w}_{c}" for w, c in timeline_clips() if c not in have.get(w, [])]
    meta = {"fps": FPS, "units": "art-width", "clips": [], "timelineMissing": missing_tl,
            "requestedClips": TL.get("requestedClips") or [],
            "count": {ch: len(have[ch]) for ch in CHARS},
            "stage": {"basketZ": BASKET_Z, "basketWaitFloor": BASKET_WAIT_Y, "saulBasketMark": list(SAUL_BASKET),
                      "basketMode": "basket_wait / basket_down / basket_out: Saul at SAUL_BASKET = BASKET_DOWN + "
                      f"{-BASKET_Z} in z, facing the viewer (yaw 0); the basket (and the ropes' window end, ropeTop "
                      f"keyed to rig-local z {BASKET_Z}) {-BASKET_Z} behind his root at BASKET_DOWN",
                      "leadDistance": LEAD_D, "holdPoint": [round(v, 4) for v in HOLD_PT], "hugDistance": HUG_D,
                      "besideDistance": BESIDE_D, "matTop": MAT_TOP, "handsOn": "Ananias on ANANIAS_TOUCH facing "
                      "Saul on SAUL_MAT (sit_pray, face viewer)", "pour": "Ananias on ANANIAS_POUR facing Saul on "
                      "SAUL_MAT (kneel, face viewer)", "takeLettersGrabFrame": TAKE_GRAB}}
    only = os.environ.get("SA_ONLY")
    for cl in CLIPS:
        if only and not any(cl.action.startswith(o) for o in only.split(",")):
            continue
        rig = rigs[cl.ch]
        frames = bake_clip(rig, cl)
        write_action(rig, cl, frames)
        rootmax = max(rig.pos(M, "root").length for _, M in frames)
        info = {"action": cl.action, "char": cl.ch, "clip": cl.name, "frames": cl.N, "seconds": round(cl.N / FPS, 3),
                "loop": cl.loop, "seated": cl.seated, "rootMotion": False,
                "markers": {k: {"frame": v, "sec": round(v / FPS, 3)} for k, v in cl.markers.items()},
                "rootMaxOffset": round(rootmax, 5), "props": cl.props, "notes": cl.notes}
        info.update(getattr(cl, "info", {}) or {})
        if cl.speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            info["stride"] = round(cl.speed[0], 4)
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        if cl.loop:
            info["loopSeamMaxErr"] = info["checks"]["seamStep"]
        print("SA_CHECK", cl.action, json.dumps(info["checks"]), flush=True)
        meta["clips"].append(info)
    meta["travel"] = travel_needs()
    for r in meta["travel"]:
        print("SA_TRAVEL", json.dumps(r))
    meta["a8"] = a8_check()
    print("SA_A8", json.dumps(meta["a8"]))
    if not only or os.environ.get("SA_PAIRCHECK") == "1":
        meta["pairCheck"] = pair_check()
        print("SA_PAIR", json.dumps(meta["pairCheck"]))
        meta["basketCheck"] = basket_check()
    meta["setCheck"] = set_checks() if (not only or os.environ.get("SA_SETCHECK") == "1") else {}
    if only:
        print("SA_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "sa_anim.blend")
    bpy.ops.wm.save_as_mainfile(filepath=tmp_blend, compress=True)
    ropes_under_basket = _sa_char_fn("_ropes_under_basket")
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
                                  export_def_bones=False, export_texcoords=True, export_materials='EXPORT', export_morph=False,
                                  export_optimize_animation_size=False, export_anim_slide_to_zero=False,
                                  export_rest_position_armature=True, export_negative_frame='CROP')
        if ch == "saul":
            print("SA_ROPES_UNDER_BASKET", ropes_under_basket(path))
        print("SA_EXPORT", ch)
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("SA_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


# =============================================================================================== render helpers
REGIONS = json.load(open(REGIONS_JSON))
FACES = {ch: {"default": v["faceDecal"]["default"], "clips": v["faceDecal"].get("clipExpression", {})}
         for ch, v in list(REGIONS["characters"].items()) + list(REGIONS.get("offSheet", {}).items())}
DECAL_NODES = {}
DIST_K = {ch: 1.35 for ch in CHARS}
PROP_ON = {("saul", "take_letters"): {"letters": TAKE_GRAB}}
PROP_ALWAYS = {("saul", n): ("basket", "ropes") for n in ("basket_wait", "basket_down", "basket_out")}


def set_props_for_frame(rig, cl, fr):
    for p, at in PROP_ON.get((cl.ch, cl.name), {}).items():
        o = bpy.data.objects.get(f"{cl.ch}_{p}")
        if o:
            o.hide_render = fr < at


def cam_for(cam, rig, mark, view, dk):
    x, z, yaw0, y = mark[:4]
    if view == "phone":
        tg = V(x, y + rig.H * 0.5, z)
        look(cam, tg, V(x + 0.10, y + 0.30, z + 0.60), lens=40)
        return
    if view in WORLD_VIEWS:
        tg = V(x, y + rig.H * float(os.environ.get("SA_PROBE_AIM", "0.5")), z)
        look(cam, tg, tg + WORLD_VIEWS[view] * (dk / 1.35), lens=40)
        return
    mark_cam(cam, rig, mark[:4], view, dk)


WORLD_VIEWS = {"wfront": V(0, 0.10, 0.55), "wfl": V(-0.36, 0.14, 0.42), "wfr": V(0.36, 0.14, 0.42),
               "wtop": V(0, 0.60, 0.16), "wleft": V(-0.50, 0.08, 0.12), "wright": V(0.50, 0.08, 0.12),
               "wbasket": V(0.50, 0.10, 0.26), "wback": V(0.0, 0.14, -0.50)}


def contact_view(cl, mark):
    if not mark[4]:
        return "q3"
    if cl.name.startswith("basket_"):
        return "wbasket"
    if cl.ch == "priest":
        return "wfl"
    if cl.name in ("take_letters", "angry_talk", "knock", "hands_on", "pour", "peek_afraid"):
        return "q3"
    return "wfront"


def render_pair_row(sc, cam, rigs, key, frames_sel, views, d):
    pa = {p[0]: p for p in pairs()}[key]
    _, a, ma, b, mb = pa
    clips = {c.action: c for c in CLIPS}
    ca, cb = clips[a], clips[b]
    ra, rb = rigs[ca.ch], rigs[cb.ch]
    show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
    set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
    fa, fb = bake_clip(ra, ca), bake_clip(rb, cb)
    out = []
    on_set = key == "letters" and os.environ.get("SA_PROBE_SET", "1") == "1"
    use_set(on_set)
    for fr in frames_sel:
        apply_basis(ra, fa[fr % ca.N if ca.loop else min(fr, ca.N)][0])
        apply_basis(rb, fb[fr % cb.N if cb.loop else min(fr, cb.N)][0])
        place_mark(ra, ma); place_mark(rb, mb)
        set_props_for_frame(ra, ca, fr); set_props_for_frame(rb, cb, fr)
        bpy.context.view_layer.update()
        T = V((ma[0] + mb[0]) / 2, max(ma[3], mb[3]) + 0.17, (ma[1] + mb[1]) / 2)
        ax = V(mb[0] - ma[0], 0, mb[1] - ma[1]).normalized()
        side = V(-ax.z, 0, ax.x)
        if side.z < 0:
            side = -side
        cams = {"side": T + side * 0.48 + V(0, 0.04, 0), "q3": T + side * 0.36 + ax * 0.20 + V(0, 0.12, 0),
                "q3b": T + side * 0.36 - ax * 0.20 + V(0, 0.12, 0), "top": T + V(0.0, 0.50, 0.12),
                "phone": T + V(0.10, 0.42, 0.80), "front": T + V(0, 0.05, 0.55), "close": T + V(0.10, 0.10, 0.32)}
        for vn in views:
            look(cam, T, cams[vn], lens=40)
            fn = f"pair_{key}_{fr:03d}_{vn}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True); out.append((fr, vn, fn))
    reset_pose(ra); reset_pose(rb)
    return out


def show_clip(rigs, cl):
    show_only(rigs, [cl.ch], {cl.ch: cl})
    for p in PROP_ALWAYS.get((cl.ch, cl.name), ()):
        o = bpy.data.objects.get(f"{cl.ch}_{p}")
        if o:
            o.hide_render = False


def mode_contact():
    sc, rigs = open_scene()
    setup_look_ls(sc, (300, 300), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    for cl in CLIPS:
        rig = rigs[cl.ch]
        show_clip(rigs, cl)
        set_expression(cl.ch, cl.name)
        frames = bake_clip(rig, cl)
        mk = sorted(set(cl.markers.values()))
        picks = sorted(set([0, cl.N] + [int(round(cl.N * k / 5)) for k in range(1, 5)] + [m for m in mk if m <= cl.N]))
        while len(picks) > 7:
            cand = [p for p in picks if p not in mk and p not in (0, cl.N)] or [p for p in picks if p not in (0, cl.N)]
            picks.remove(cand[len(cand) // 2])
        mark = stage_of(cl)
        use_set(mark[4])
        if not mark[4]:
            mark = (mark[0], mark[1], mark[2], 0.0, False)
        view = contact_view(cl, mark)
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": []}
        for fr in picks:
            apply_basis(rig, frames[fr][0])
            place_mark(rig, mark[:4])
            set_props_for_frame(rig, cl, fr)
            bpy.context.view_layer.update()
            cam_for(cam, rig, mark, view, DIST_K[cl.ch] * (1.6 if cl.name.startswith("basket_") else 1.0))
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("SA_CONTACT_ROW", cl.action, picks, flush=True)
    for key, a, ma, b, mb in pairs():
        row = {"action": f"pair {key}: {a} + {b}", "loop": True, "frames_total": 0, "frames": []}
        for fr, views in [(0, ("side",)), (20, ("q3",)), (40, ("side",)), (60, ("phone",))]:
            for f_, vn, fn in render_pair_row(sc, cam, rigs, key, [fr], views, d):
                row["frames"].append({"f": f_, "file": fn, "marker": vn})
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """SA_PROBE="action:f1,f2:view,view;..."  view = front|q3|side|back|q3l|lside|top|low|phone|w*.
    'pair:<key>:<f1,f2>[:views]' (keys of pairs()). SA_PROBE_SET=0 hides the set."""
    sc, rigs = open_scene()
    res = int(os.environ.get("SA_PROBE_RES", "440"))
    setup_look_ls(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    for f_ in os.listdir(d):
        os.remove(os.path.join(d, f_))
    clips = {cl.action: cl for cl in CLIPS}
    out = []
    for item in os.environ.get("SA_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "pair":
            frs = [int(v) for v in parts[2].split(",")]
            views = parts[3].split(",") if len(parts) > 3 else ["side", "q3"]
            out += [fn for _, _, fn in render_pair_row(sc, cam, rigs, parts[1], frs, views, d)]
            continue
        action, frames, view = parts[0], parts[1], parts[2] if len(parts) > 2 else "q3"
        cl = clips[action]; rig = rigs[cl.ch]
        show_clip(rigs, cl)
        set_expression(cl.ch, cl.name)
        fr_ = bake_clip(rig, cl)
        mark = stage_of(cl)
        withset = mark[4] and os.environ.get("SA_PROBE_SET", "1") == "1"
        use_set(withset)
        if not withset:
            mark = (mark[0], mark[1], mark[2], 0.0, False)
        dk = float(os.environ.get("SA_PROBE_DIST", str(DIST_K[cl.ch])))
        for fr in [int(v) for v in frames.split(",")]:
            fr = min(fr, cl.N)
            apply_basis(rig, fr_[fr][0]); place_mark(rig, mark[:4])
            set_props_for_frame(rig, cl, fr)
            bpy.context.view_layer.update()
            for vn in view.split(","):
                cam_for(cam, rig, mark, vn, dk)
                fn = f"{action}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("SA_PROBE", len(out))


def mode_debug():
    sc, rigs = open_scene()
    exec(os.environ.get("SA_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))


{"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
