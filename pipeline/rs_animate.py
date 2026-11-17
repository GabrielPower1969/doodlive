"""He Is Risen! skeletal animation (Animation role, story pack `risen`).

Two halves in one file, the shape of pipeline/ls_animate.py:

* Under Blender (headless) it opens `assets/risen/model/characters.blend` (Characters role's rigs), builds every clip
  of docs/risen/CONTRACT.md §4 as an action `<char>_<clip>` and exports
  `assets/risen/anim/{jesus,mary,angel,peter,john,thomas,joanna}.glb` (character + skin + one glTF animation per
  action) and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/rs_animate.py all        # build + verify + contact sheet + freshness check
    python3 pipeline/rs_animate.py build      # actions + GLBs + anim/clips.json (checks, set checks, pair checks)
    python3 pipeline/rs_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/rs_animate.py contact    # anim/contact_sheet.png (key poses per clip; staged clips on the set)
    RS_PROBE="angel_sit_stone:0,60:front,side" python3 pipeline/rs_animate.py probe   # work renders ($RS_ANIM_WORK)
    RS_PROBE="pair:jesus_hold_hands:mary_hold_hands:0.11:0,30:meet:side,q3" python3 pipeline/rs_animate.py probe
        pair modes: meet (A at JESUS_G facing B, B `dist` away on the line to MARY_MEET, y 0), touch (A at ROOM_J
        facing -X, B `dist` to its -X facing +X, y UPPER)
    RS_ONLY=angel_,peter_stoop  (with build: bake + check a subset, no export)

Reuse, not copies (CONTRACT §2, R5): this script runs pipeline/ls_animate.py in its own namespace (definitions only;
its final mode dispatch is cut off at an asserted anchor), and ls_animate.py itself runs pipeline/mi_animate.py the
same way. So the Real Miracles clips (Jesus idle / talk / walk / wave; Peter idle / talk / walk / laugh / amazed; the
friends' idle) and The King Who Serves' disciple motion (talk, cheer, the bench sit) are the same functions, baked on
this pack's rigs. Nothing in `mi_*` or `ls_*` is edited; their clip lists are dropped and this pack registers its own.

Stage numbers the clips are fitted to are the constants in `_rs_constants()` (docs/risen/ANIMATION.md §2).
Intermediates: $RS_ANIM_WORK (default /tmp/risen_anim).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LS_PATH = os.path.join(HERE, "ls_animate.py")


def _rs_constants():
    """This pack's paths and stage numbers. Re-applied after The King Who Serves module ran in this namespace."""
    RS = os.path.join(ROOT, "assets/risen")
    model = os.path.join(RS, "model")
    return dict(
        RSDIR=RS, MODEL=model, ANIM=os.path.join(RS, "anim"), BLEND=os.path.join(model, "characters.blend"),
        SET_GLB=os.path.join(model, "garden.glb"), TIMELINE=os.path.join(RS, "timeline.json"),
        REGIONS_JSON=os.path.join(model, "regions_characters.json"),
        EXTRAS_PAINT=os.path.join(model, "extras_paint.png"),
        FACE_DIR=os.path.join(ROOT, "docs/risen/design/faces"),
        WORK=os.environ.get("RS_ANIM_WORK") or "/tmp/risen_anim",
        ENV="RS_", BLENDER=os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender"), FPS=30,
        CHARS=("jesus", "mary", "angel", "peter", "john", "thomas", "joanna"),
        EXTRAS=("peter", "john", "thomas", "joanna"),        # fixed paint (extras_paint.png), not on the sheet
        WOMEN=("mary", "joanna"), DISCIPLES=(), SELLERS=(), FRIENDS=(),
        # stage numbers (art-width units; docs/risen/ANIMATION.md §2)
        UPPER=0.10,                 # upstairs room floor; every clip is built in the actor's own space
        BENCH_SEAT=0.040,           # bench cushion top above the room floor (SET.md: 0.14 = UPPER + 0.04)
        STONE_TOP=0.38,             # flat top of the rolled-away stone (SET.md, lead-approved 2026-11-18)
        ANGEL_Y=0.311,              # the angel's base y in story.py (2026-11-18); the seat is fitted to it
        STONE_C=(-0.1126, -0.4103), # STONE_ASIDE: the stone centre = the angel's mark
        STONE_YAW=40.0,             # the rolled stone's disc plane runs front-left -> back-right, 40 deg off X
        STONE_HALF_T=0.025,         # half thickness of the disc (0.05)
        PAIR_D=0.11,                # hold_hands, show_hands / reach (A1)
        DOOR_Z=-0.312,              # the rock's front face at the tomb door (SET.md)
        DOOR_TOP=0.34,              # top of the door opening (round top, r 0.065)
        FISH_ON=18,                 # eat_fish: the fish prop is in the hand from frame 18 (0.6 s)
    )


globals().update(_rs_constants())
os.environ.setdefault("LS_ANIM_WORK", WORK)       # the sister modules' scratch dirs go under ours (R11)
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
    print("\n".join(tail[-500:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def fresh_check():
    """The Characters role may re-run rs_characters.py: the anim GLBs must be newer than the model files (A7)."""
    src = [BLEND] + [os.path.join(MODEL, f"{c}.glb") for c in CHARS]
    newest = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    outs = [os.path.join(ANIM, f"{c}.glb") for c in CHARS]
    stale = [o for o in outs if (not os.path.exists(o)) or os.path.getmtime(o) < newest]
    print("RS_FRESH", "STALE " + ", ".join(os.path.basename(o) for o in stale) if stale else
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
    cols = min(len(ims), int(os.environ.get("RS_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("RS_PROBE_OUT", "probe.png"))
    sheet.save(out); print("RS_PROBE_SHEET", out)


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
    d.text((pad, 14), "He Is Risen! - key poses per clip (30 fps; frame / seconds; marker or view in red; staged clips "
                      "on the garden set; pair rows = two actors at their story distance)", fill=(40, 30, 20), font=font)
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
    print("RS_CONTACT", out, sheet.size)


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


def _load_lastsupper():
    """Run pipeline/ls_animate.py (which runs mi_animate.py) in this namespace, without its final mode dispatch
    (asserted, so a change to that line fails loudly instead of running The King Who Serves build)."""
    src = open(LS_PATH, encoding="utf-8").read()
    cut = '\n{"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, ' \
          '"debug": mode_debug}[MODE]()'
    assert src.count(cut) == 1, "ls_animate.py: the final dispatch line changed; update rs_animate._load_lastsupper"
    g = globals()
    keep_file, keep_doc = g.get("__file__"), g.get("__doc__")
    g["__file__"] = LS_PATH
    try:
        exec(compile(src[:src.index(cut)], LS_PATH + " (definitions, run by rs_animate.py)", "exec"), g)
    finally:
        g["__file__"] = keep_file; g["__doc__"] = keep_doc


_load_lastsupper()
LS_CLIP = {c.action: c for c in CLIPS}        # The King Who Serves clips (functions kept, list dropped)
globals().update(_rs_constants())
os.makedirs(WORK, exist_ok=True)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
TL = json.load(open(TIMELINE))
CLIPS.clear()
_PAY.clear(); _BAKED.clear(); _PARTNER.clear(); _SEAT.clear()

SEAT_LOCAL = STONE_TOP - ANGEL_Y              # the angel's seat (lowest robe point on the stone) in rig space
CLOSED = {ch: 12.78 for ch in CHARS}          # RIG.md §4: eyelids.sy closed (all seven)
KNEEL = {ch: dict(KY=0.020, kz=0.016, thigh_back=10.0, shin_slope=22.0) for ch in CHARS}
ARM_REST = {"jesus": -18.0, "peter": -12.0, "john": -20.0, "thomas": -16.0, "mary": -14.0, "joanna": -14.0,
            "angel": -16.0}
FV = {"john": dict(ph=0.00, amp=1.15), "thomas": dict(ph=0.31, amp=0.95), "mary": dict(ph=0.00, amp=1.00),
      "joanna": dict(ph=0.57, amp=0.85)}
COAT = {"belt1": "thighL", "sash1": "thighL"}
CHAIN_FLOOR = {}
NO_GRAVITY = set()
CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "jesus": [(("mantle1",), 70.0, 7.0, 0.30, 12.0), (("belt1",), 90.0, 7.5, 0.30, 24.0)],
    "peter": [(("cloth1",), 90.0, 8.0, 0.30, 22.0)],
    "john": [(("sash1",), 90.0, 7.5, 0.30, 24.0)],
    "thomas": [(("cloak1",), 70.0, 7.0, 0.30, 16.0)],
    "mary": [(("veil1",), 75.0, 6.5, 0.30, 20.0), (("sash1",), 90.0, 7.5, 0.30, 24.0)],
    "joanna": [(("veil1",), 80.0, 7.0, 0.30, 18.0), (("sash1",), 90.0, 7.5, 0.30, 24.0)],
    "angel": [(("sash1",), 85.0, 7.5, 0.30, 22.0)],
}
PROPS = ("fish", "jar", "bucket")
HIDE_SET = ("tombStone",)                    # renders: the stone is rolled away (tombStoneAside shown)

# marks (story.py) for renders and staging checks: (x, z)
TOMB_DOOR = (-0.33, -0.24)
DOOR_C = (-0.33, -0.30)                      # tombDoor node origin (what `face="tombDoor"` turns to)
MARY_DOOR = (-0.30, -0.22)
JOANNA_DOOR = (-0.40, -0.21)
PETER_PUFF = (-0.22, -0.14)
JESUS_G = (-0.10, -0.12)
MARY_MEET = (-0.205, -0.075)
MARY_CRY = (-0.24, -0.05)
MARY_T = (-0.30, -0.13)
BENCH = {"thomas": (0.20, -0.49), "john": (0.30, -0.49), "peter": (0.40, -0.49)}
ROOM_J = (0.30, -0.30)
TABLE_J = (0.41, -0.30)
LOWTABLE_C = (0.511, -0.31)
THOMAS_TOUCH = (0.19, -0.30)
OPEN = (0.0, 0.10)


# =============================================================================================== rig
class RsRig(Rig):
    """mi_animate.Rig + this cast's heights (ls helpers read .quad / .seat)."""
    H_OF = {"angel": 0.40, "jesus": 0.36, "mary": 0.34, "peter": 0.38, "john": 0.33, "thomas": 0.36, "joanna": 0.33}

    def __init__(self, ch, obj):
        super().__init__(ch, obj)
        self.quad = False
        self.seat = None


def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rigs = {ch: RsRig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    RIGS.clear(); RIGS.update(rigs)
    return sc, rigs


def stone_frame(p):
    """(along the disc plane, along its normal) of a point in the seated angel's root space (angel at STONE_ASIDE,
    yaw 0). The disc plane runs toward +X / -Z (its right end turned back), the normal toward +X / +Z."""
    a = math.radians(STONE_YAW)
    return p.x * math.cos(a) - p.z * math.sin(a), p.x * math.sin(a) + p.z * math.cos(a)


def on_stone(p, along=0.05):
    u, n = stone_frame(p)
    return abs(n) < STONE_HALF_T and abs(u) < along


# --- solve / evaluate extensions: the jar hangs from its cord; the angel's seat rests on the stone
_ls_solve_pose = solve_pose


def solve_pose(rig, chs):
    out = _ls_solve_pose(rig, chs)
    if "jar" in rig.names:                       # the spice jar hangs from the left fist by its cord: always down
        _, basis, M = out
        Mroot3 = (M["root"] @ rig.rest["root"].inverted()).to_3x3().normalized()
        down = (Mroot3 @ Vector((0, 0, -1))).normalized()
        cur = M["jar"].to_3x3().normalized()
        Rd = cur.col[1].normalized().rotation_difference(down).to_matrix()
        rig.set_world_rot(basis, M, "jar", Rd @ cur)
    return out


_mi_evaluate_primary = evaluate_primary


def evaluate_primary(rig, clip_, f):
    """mi evaluate_primary + `seatsettle` (the angel): the lowest hips / thigh point over the stone's top footprint
    goes to SEAT_LOCAL (points in front of the stone's face hang free)."""
    out = _mi_evaluate_primary(rig, clip_, f)
    chs = out[0]
    ss = chs.get("seatsettle")
    if ss:
        target, w = ss
        pts = [p for p in rig.skin(out[2], {"hips", "thighL", "thighR"}) if on_stone(p)]
        if pts:
            low = min(p.y for p in pts)
            chs["hips.ty"] = chs.get("hips.ty", 0.0) + w * (target - low)
            out = solve_pose(rig, chs)
    return out


# =============================================================================================== registration
def add_clip(ch, name, N, loop, fn, **kw):
    info = kw.pop("info", None)
    cl = Clip(ch, name, N, loop, fn, **kw)
    cl.info = info or {}
    CLIPS.append(cl)
    return cl


def reuse_fn(ch, name, fn, N, loop, src, phase=0.0, **kw):
    """Register a sister pack's clip function under this cast (same function; the source is named in the notes)."""
    kw["notes"] = kw.get("notes", "") + f" [{src}, reused unchanged]"
    if phase and loop:
        def wrapped(rig, f, N_, fn=fn, sh=int(round(phase * N))):
            return fn(rig, (f + sh) % N_, N_)
        return add_clip(ch, name, N, loop, wrapped, **kw)
    return add_clip(ch, name, N, loop, fn, **kw)


def mi_reuse(ch, src, name=None, phase=0.0, **over):
    s = MI_CLIP[src]
    fn = globals()["friend_" + s.name] if src.startswith("friend1_") else s.fn
    kw = dict(markers=dict(s.markers), notes=s.notes, speed=s.speed, props=[], seated=s.seated)
    kw.update(over)
    return reuse_fn(ch, name or s.name, fn, s.N, s.loop, "Real Miracles clip " + src, phase=phase, **kw)


def rclip(chs, name, N, loop, phase=True, **kw):
    """One function for one or several characters; free loops are phase-shifted per person (FV) so a group never
    moves in unison (travel clips never)."""
    chs = (chs,) if isinstance(chs, str) else tuple(chs)

    def deco(fn):
        for ch in chs:
            sh = FV[ch]["ph"] if (ch in FV and loop and phase and not kw.get("speed")) else 0.0
            if sh:
                def wrapped(rig, f, N_, fn=fn, s=int(round(sh * N))):
                    return fn(rig, (f + s) % N_, N_)
                add_clip(ch, name, N, loop, wrapped, **dict(kw))
            else:
                add_clip(ch, name, N, loop, fn, **dict(kw))
        return fn
    return deco


def amp_of(rig):
    return FV[rig.ch]["amp"] if rig.ch in FV else 1.0


# =============================================================================================== shared helpers
def hold_jar(c, rig, w=1.0, bob=0.0):
    """The left fist at the hip, holding the jar's cord (the jar hangs below it, beside the skirt)."""
    k = kH(rig)
    arm_ik(c, "L", V(0.074 * k, (0.162 + bob) * k, 0.016 * k), V(0.9, -0.2, -0.6), "root", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 8, w); fingers(c, "L", lerp(c.get("fingersL.curl", 22), 72, w))
    c["forearmL.twist"] = lerp(c.get("forearmL.twist", -10), 20, w)


def hands_cheeks(c, rig, w=1.0, lift=0.0, wipe=(0.0, 0.0), out=0.0):
    """Both hands at the cheeks, BELOW the eyes (A5): wrists at the jaw line, fingers up along the cheeks.
    lift 0..1 raises them a little (still under the eyes); wipe = per-hand small up / down rub."""
    for side, sx, wp in (("L", 1, wipe[0]), ("R", -1, wipe[1])):
        arm_ik(c, side, V((0.026 + 0.012 * out) * sx, -0.022 + 0.004 * lift + 0.004 * wp, 0.024), V(0.9 * sx, -0.7, -0.2),
               "head", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 22, w)
        c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", -10 * sx), -50 * sx, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 14, w))


WING_SEAT_FWD = {"L": 16.0, "R": 26.0}   # seated: inner halves swung forward (RIG.md measured 8 on a stand-in; the real
WING_SEAT_LIFT = 5.0     # stone and the alcove's rock behind the right wing need more) and lifted a little


def wings(c, f, N, mode="half", w=1.0, breathe=1.0, cycles=1, seated=True):
    """The angel's wings (RIG.md §2: rest = half-open). half / folded / open; seated swings the inner halves forward
    (WING_SEAT_FWD) and up so the backs clear the stone and the rock; a slow breathing lift with the outer half lagging (secondary motion)."""
    b = math.sin(2 * math.pi * cycles * f / N)
    bl = math.sin(2 * math.pi * cycles * f / N - 0.9)
    tgt = {"half": (0.0, 0.0, 0.0), "folded": (0.0, -18.0, -95.0), "open": (30.0, 12.0, 18.0)}[mode]
    for side, sx in (("L", 1), ("R", -1)):
        rz1 = tgt[0] + 2.5 * breathe * b + (WING_SEAT_LIFT if seated else 0.0)
        ry1 = tgt[1] - (WING_SEAT_FWD[side] if seated else 0.0)
        c[f"wing{side}1.rz"] = lerp(c.get(f"wing{side}1.rz", 0.0), sx * rz1, w)
        c[f"wing{side}1.ry"] = lerp(c.get(f"wing{side}1.ry", 0.0), sx * ry1, w)
        if mode == "folded":
            c[f"wing{side}2.ry"] = lerp(c.get(f"wing{side}2.ry", 0.0), sx * tgt[2], w)
            c[f"wing{side}2.rz"] = lerp(c.get(f"wing{side}2.rz", 0.0), sx * 2.0 * breathe * bl, w)
        else:
            c[f"wing{side}2.rz"] = lerp(c.get(f"wing{side}2.rz", 0.0), sx * (tgt[2] + 3.5 * breathe * bl), w)


def angel_seat(rig, c, f, N, swing=1.0, cycles=1):
    """Seated on the rolled stone (the `ride` method: hips on the stone top at base ANGEL_Y): thighs level over the
    stone's front face, shins hanging and swinging a little (alternate legs), the seat settled on the stone top."""
    for side, sx, ph in (("L", 1, 0.0), ("R", -1, math.pi)):
        for k_ in ("ik.leg", "ikw.leg"):
            c.pop(k_ + side, None)
        s = math.sin(2 * math.pi * cycles * f / N + ph)
        c[f"thigh{side}.rx"] = -88.0
        c[f"thigh{side}.rz"] = 4.0 * sx
        c[f"shin{side}.rx"] = 80.0 + 10.0 * swing * s
        c[f"foot{side}.rx"] = 10.0 + 8.0 * swing * s
    c["hips.ty"] = c.get("hips.ty", 0.0) + (SEAT_LOCAL + 0.034 - rig.head["hips"].y)
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.006
    c["seatsettle"] = (SEAT_LOCAL, 1.0)
    c["coatfollow"] = 1.0
    c["nofootfix"] = True


def stone_hands(c, rig, w=1.0, sides="LR"):
    """Hands on the stone's top edge beside the hips (the top runs diagonally: the left hand back, the right in
    front); the wrists are just above the top, the fingers curl over the edge."""
    a = math.radians(STONE_YAW)
    for side, sx in (("L", 1), ("R", -1)):
        if side not in sides:
            continue
        u = 0.052 * sx
        tgt = V(u * math.cos(a), SEAT_LOCAL + 0.016, -u * math.sin(a))
        arm_ik(c, side, tgt, V(0.8 * sx, 0.1, -0.6), "root", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 40, w)
        fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 40, w))


def wings_follow(c, k=0.9):
    """The chest turning right swings the right wing back into the rock: turn the wings' roots against it."""
    t = c.get("chest.ry", 0.0) + c.get("spine.ry", 0.0)
    c["wingR1.ry"] = c.get("wingR1.ry", 0.0) - k * t
    c["wingL1.ry"] = c.get("wingL1.ry", 0.0) - 0.4 * k * t


def angel_base(rig, f, N, cycles=1, swing=1.0, breathe=1.0):
    c = h_base(rig, f, N, cycles=cycles, amp=0.7)
    angel_seat(rig, c, f, N, swing=swing, cycles=cycles)
    wings(c, f, N, "half", breathe=breathe, cycles=cycles)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 6; c["chest.rx"] += 3
    return c


# =============================================================================================== JESUS
for _nm in ("idle", "talk", "walk", "wave"):
    mi_reuse("jesus", "jesus_" + _nm)


@rclip("jesus", "appear", 45, False, markers={"open": 30},
       notes="as He appears (the timeline pops Him in, grow 0.6): arms open slowly from His sides to a welcoming "
             "half-open pose (hands out at waist height, palms up and forward), the chest opens, a small nod at "
             "`open`; face joy; holds")
def jesus_appear(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.5)
    k = kH(rig)
    o = ease_io((f - 3) / 27)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.112 * sx, 0.180, 0.060) * k, V(0.9 * sx, -0.6, -0.3), "root", o)
        c[f"forearm{side}.twist"] = lerp(-10 * sx, -70 * sx, o)
        c[f"hand{side}.bend"] = lerp(6, -14, o); fingers(c, side, lerp(22, 6, o))
    c["chest.rx"] += -3 * o; c["spine.rx"] = -1 * o
    c["head.rx"] = -2 + 7 * bump(f, 26, 42)
    c["head.rz"] = 3 * o
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [36], loop=False)
    return c


@rclip("jesus", "call_name", 40, False, markers={"name": 18},
       notes="'Mary.': a soft step toward her (right foot, lifted), the right hand a little out, palm up, head tilted, "
             "face gentle; holds")
def jesus_call_name(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    st = ease_io((f - 2) / 16)
    stand_feet(rig, c, spread=0.004, fwdR=0.024 * st, liftR=0.016 * bump(f, 2, 18))
    c["hips.tz"] = 0.010 * st; c["spine.rx"] = 3 * st
    o = ease_io((f - 6) / 16)
    arm_ik(c, "R", V(-0.070, 0.165, 0.080) * k, V(-0.9, -0.6, -0.3), "root", o)
    c["forearmR.twist"] = lerp(10, 70, o); c["handR.bend"] = lerp(6, -10, o); fingers(c, "R", lerp(22, 8, o))
    c["head.rz"] = -9 * o; c["head.rx"] = -2 + 5 * o; c["neck.rx"] = 3 * o
    c["jaw.rx"] = 5 * bump(f, 16, 24)
    blink_ch(c, rig, f, N, [30], loop=False)
    return c


HH_Y = 0.185             # hold_hands: the joined hands' height (world, both actors at y 0)
HH_Z = {"jesus": 0.043, "mary": 0.047}     # wrist distance in front of each root (they stand PAIR_D apart, facing)


def hold_hands_fn(rig, f, N):
    """Both hands joined with the partner's at chest height, PAIR_D apart, facing; a small happy sway in phase."""
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    z = HH_Z[rig.ch]
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.026 * sx, HH_Y, z), V(0.9 * sx, -0.7, -0.1), "root", 1.0)
        c[f"forearm{side}.twist"] = -35 * sx
        c[f"hand{side}.bend"] = 4; fingers(c, side, 40)
    s = wave(f, N, 1)
    m = 1 if rig.ch == "jesus" else -1          # mirrored, so both lean the same way in the world
    c["hips.tx"] = 0.003 * s * m; c["hips.rz"] = -1.6 * s * m; c["chest.rz"] = 1.2 * s * m
    c["head.rz"] = (-6 if rig.ch == "jesus" else 8) + 2.5 * s * m
    c["head.rx"] = (3 if rig.ch == "jesus" else -4) + 1.5 * wave(f, N, 2)
    stand_feet(rig, c, spread=0.004)
    if rig.ch == "mary":
        bo = 0.5 + 0.5 * wave(f, N, 2)
        c["hips.ty"] = 0.003 * bo
        stand_feet(rig, c, spread=0.004, pitchL=6 * bo, pitchR=6 * bo)
    blink_ch(c, rig, f, N, [20] if rig.ch == "jesus" else [44])
    return c


rclip("jesus", "hold_hands", 60, True,
      notes="holds both of Mary's hands at chest height (wrists 0.043 in front of His root, joined hands at y 0.185), "
            "Mary 0.11 in front facing Him (A1); a small happy sway, head tilted; face joy")(hold_hands_fn)


@rclip("jesus", "peace", 120, True,
       notes="'Peace be with you!': both hands raised to shoulder height, palms out, a warm greeting; a slow look round "
             "the room (left ... right), small nods")
def jesus_peace(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    k = kH(rig)
    lift = 0.92 + 0.08 * wave(f, N, 2)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.092 * sx, 0.262 * lift, 0.062) * k, V(0.9 * sx, -0.8, -0.2), "root", 1.0)
        c[f"forearm{side}.twist"] = -72 * sx; c[f"hand{side}.bend"] = -22; fingers(c, side, 4)
    turn = [(0, -16), (20, -16), (50, 18), (80, 18), (110, -16), (120, -16)]
    c["chest.ry"] = 0.25 * K(turn, f, N, True); c["neck.ry"] = 0.3 * KL(turn, f, N, True, lag=4)
    c["head.ry"] = 0.4 * KL(turn, f, N, True, lag=7)
    c["head.rx"] = -2 + 4 * (bump(f, 22, 36) + bump(f, 82, 96))
    c["jaw.rx"] = 4 * bump(f, 4, 16)
    stand_feet(rig, c, spread=0.005)
    blink_ch(c, rig, f, N, [40, 100])
    return c


SH_Y = 0.200             # show_hands: wrists at chest height, palms up
SH_Z = 0.050


@rclip("jesus", "show_hands", 96, True,
       notes="both hands held out in front at chest height (wrists 0.05 in front of the root, 0.056 to the sides, beside the bellies at the pair distance; y 0.20), palms up, "
             "turning slowly (the hands are drawn as always: no marks); looks down at them and up at the friend, a "
             "smile. Thomas's `reach` touches them at 0.11")
def jesus_show_hands(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    k = kH(rig)
    tw = wave(f, N, 1)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.056 * sx, SH_Y, SH_Z) * k, V(0.9 * sx, -0.7, -0.3), "root", 1.0)
        c[f"forearm{side}.twist"] = -84 * sx + 14 * sx * tw
        c[f"hand{side}.bend"] = -14; fingers(c, side, 6)
    lk = K([(0, 0), (16, 0), (28, 1), (56, 1), (68, 0), (96, 0)], f, N, True)
    c["neck.rx"] = 6 * lk; c["head.rx"] = -2 + 10 * lk
    c["chest.rx"] += 2 * lk
    c["jaw.rx"] = 3 * bump(f, 74, 86)
    stand_feet(rig, c, spread=0.005)
    blink_ch(c, rig, f, N, [10, 70])
    return c


EAT_PLATE = V(0.0, 0.056, 0.090)        # the fish on the plate in Jesus's root space at TABLE_J facing lowTable (y UPPER)


@rclip("jesus", "eat_fish", 120, False, props=["fish"],
       markers={"take": FISH_ON, "show": 36, "bite": 48, "laugh": 92},
       notes="beside the table, facing it (TABLE_J, face=lowTable; the plate 0.09 in front, top UPPER + 0.056): bends "
             "and takes a fish from the plate with the right hand (prop shown at `take` 0.6 s, the timeline hides the "
             "set's fishOnPlate then), straightens and turns half to the viewer (His right) showing it palm up, a bite "
             "at `bite` 1.6 s (hand at the mouth), chews happily (face chew), a laugh, the left hand to His chest; "
             "holds standing, turned to the viewer, the fish in His hand")
def jesus_eat_fish(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    k = kH(rig)
    dn = ease_io((f - 1) / 13) * (1 - ease_io((f - 20) / 14))
    c["hips.ty"] = -0.034 * dn; c["hips.tz"] = -0.018 * dn
    c["hips.rx"] = 18 * dn; c["spine.rx"] = 18 * dn; c["chest.rx"] += 10 * dn
    c["neck.rx"] = -6 * dn; c["head.rx"] = 6 * dn
    turn = ease_io((f - 22) / 18)
    c["hips.ry"] = -14 * turn; c["spine.ry"] = -8 * turn; c["chest.ry"] = -10 * turn; c["head.ry"] = -10 * turn
    # right hand: plate -> show (palm up in front of the chest) -> mouth -> chest
    reach = ease_io((f - 1) / 13)
    arm_ik(c, "R", EAT_PLATE + V(-0.006, 0.016, -0.016), V(-0.8, -0.3, -0.5), "root", reach)
    show = ease_io((f - 20) / 14)
    arm_ik2(c, "R", V(-0.052, 0.200, 0.070) * k, V(-0.9, -0.7, -0.3), "root", show)
    if f >= 34:
        mouth = ease_io((f - 36) / 12) * (1 - ease_io((f - 60) / 14))
        c["ik.armR"] = V(-0.052, 0.200, 0.070) * k; c["ikspace.armR"] = "root"; c["ikw.armR"] = 1.0
        c["pole.armR"] = V(-0.9, -0.7, -0.3)
        arm_ik2(c, "R", V(-0.006, -0.030, 0.040), V(-0.9, -0.8, 0.0), "head", mouth)
    c["forearmR.twist"] = lerp(10, 70, show) - 30 * bump(f, 38, 60)
    c["handR.bend"] = lerp(lerp(6, 30, reach), -8, show)
    grab = ease_io((f - 12) / 6)
    fingers(c, "R", lerp(lerp(22, 4, reach), 46, grab))
    chew = bump(f, 50, 92)
    c["jaw.rx"] = 6 * chew * (0.5 + 0.5 * math.sin(2 * math.pi * (f - 50) / 7)) + 9 * bump(f, 40, 50)
    c["head.rx"] = c.get("head.rx", -2.0) + 3 * chew * math.sin(2 * math.pi * (f - 50) / 14)
    lg = pulses(f, N, [(94, 1.0), (100, 0.8), (106, 0.6)], decay=2.2, loop=False)
    env = bump(f, 88, 120) if f < 104 else 1.0 - 0.4 * ease_io((f - 104) / 16)
    c["head.rx"] += -6 * env + 2 * lg
    c["shoulderL.raise"] += 3 * lg; c["shoulderR.raise"] += 3 * lg; c["chest.rx"] += 2 * lg
    c["jaw.rx"] += 8 * env * (0.5 + 0.5 * lg) * (1 if f >= 88 else 0)
    arm_ik(c, "L", V(0.016, -0.010, 0.046) * k, V(0.8, -0.6, -0.2), "chest", ease_io((f - 86) / 10))
    stand_feet(rig, c, spread=0.004)
    c["floorclamp"] = True
    blink_ch(c, rig, f, N, [30, 70], loop=False)
    return c


# =============================================================================================== WOMEN (Mary + Joanna)
W_WALK = (0.072, 0.60)
W_WALK_N = 40
W_RUN = (0.050, 0.38)
W_RUN_N = 20


def w_idle(rig, f, N, jar=False):
    a = amp_of(rig)
    c = h_base(rig, f, N, cycles=3, amp=0.8)
    k = kH(rig)
    sh = K([(0, -0.6), (30, -0.6), (56, 0.8), (90, 0.8), (110, -0.6), (120, -0.6)], f, N, True)
    c["hips.tx"] = 0.004 * sh * a; c["hips.rz"] = -2.0 * sh * a; c["spine.rz"] = 1.0 * sh; c["head.rz"] = -2 * sh
    look_keys(c, [(0, 0), (18, 0), (32, 18 * a), (56, 18 * a), (70, -12), (96, -12), (110, 0), (120, 0)], f, N)
    if jar:
        hold_jar(c, rig)
        arm_ik(c, "R", V(-0.020, 0.146, 0.044) * k, V(-0.8, -0.5, -0.4), "root", 0.8)
    else:
        hands_clasped(c, rig, V(0.0, 0.142, 0.044) * k, w=0.85)
    stand_feet(rig, c, spread=0.003)
    blink_ch(c, rig, f, N, [12, 64, 71])
    return c


def w_walk(rig, f, N, jar=False):
    a = amp_of(rig)
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    g = gait(rig, f, N, L=W_WALK[0], lift=0.012, duty=W_WALK[1], heel=10, toeoff=20)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.004 + 0.0024 * math.cos(2 * ph - 0.4)
    c["hips.ry"] = 4 * math.sin(ph); c["chest.ry"] = -4 * math.sin(ph - 0.35); c["head.ry"] = 2 * math.sin(ph - 0.7)
    c["hips.rz"] = 3.0 * math.cos(ph) * a; c["chest.rz"] = -1.2 * math.cos(ph - 0.5); c["head.rz"] = 1.2 * math.cos(ph - 0.9)
    c["upperArmL.bend"] = 8 - 12 * math.sin(ph - 0.25); c["upperArmR.bend"] = 8 + 12 * math.sin(ph - 0.25)
    c["forearmL.bend"] = 30 - 8 * math.sin(ph - 1.0); c["forearmR.bend"] = 30 + 8 * math.sin(ph - 1.0)
    if jar:
        hold_jar(c, rig, bob=0.003 * math.cos(2 * ph - 0.4))
    blink_ch(c, rig, f, N, [27])
    return c


rclip(WOMEN, "idle", 120, True,
      notes="standing, hands loosely together in front, weight shifting, looking round, blinks")(lambda r, f, N: w_idle(r, f, N))
rclip(WOMEN, "idle_jar", 120, True, props=["jar"],
      notes="as idle, the left fist at the hip holding the spice jar by its cord (the jar hangs beside the skirt), the "
            "right hand resting at the waist")(lambda r, f, N: w_idle(r, f, N, True))
rclip(WOMEN, "walk", W_WALK_N, True, phase=False, markers={"contactL": 0, "contactR": 20}, speed=W_WALK,
      notes="small, light steps under the long dress, a little hip sway, arms swinging close")(lambda r, f, N: w_walk(r, f, N))
rclip(WOMEN, "walk_jar", W_WALK_N, True, phase=False, markers={"contactL": 0, "contactR": 20}, speed=W_WALK,
      props=["jar"], notes="the walk with the left fist at the hip holding the jar (it hangs and bobs)")(
    lambda r, f, N: w_walk(r, f, N, True))


@rclip(WOMEN, "run", W_RUN_N, True, phase=False, markers={"contactL": 0, "contactR": 10}, speed=W_RUN,
       notes="a light, joyful run: quick steps with a little flight, leaning forward, elbows bent and swinging, the "
             "veil bouncing (chain), a skip in the hips")
def w_run(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=W_RUN[0], lift=0.022, duty=W_RUN[1], heel=6, toeoff=26)
    legs_ik_channels(c, g)
    p = f / N
    ph = 2 * math.pi * p
    c["hips.ty"] = -0.008 - 0.006 * math.cos(4 * math.pi * (p - 0.19))
    c["hips.rx"] = 6; c["spine.rx"] = 6; c["chest.rx"] += 2; c["head.rx"] = -6
    c["hips.ry"] = 6 * math.sin(ph); c["chest.ry"] = -8 * math.sin(ph - 0.3); c["head.ry"] = 2 * math.sin(ph - 0.6)
    c["hips.rz"] = 2 * math.cos(ph)
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -14
        c[f"upperArm{side}.bend"] = 10 + sg * 30 * math.sin(ph - 0.25)
        c[f"forearm{side}.bend"] = 70 + sg * 12 * math.sin(ph - 0.9)
        fingers(c, side, 30)
    c["jaw.rx"] = 4
    blink_ch(c, rig, f, N, [14])
    return c


@rclip(WOMEN, "sad", 120, True,
       notes="head bowed, hands folded low in front, a slow deep breath, a small sway (S01)")
def w_sad(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.2)
    k = kH(rig)
    hands_clasped(c, rig, V(0.0, 0.132, 0.040) * k, w=1.0)
    br = K([(0, 0), (40, 1), (60, 1), (100, 0), (120, 0)], f, N, True)
    c["neck.rx"] = 12 + 2 * br; c["head.rx"] = 14 - 2 * br; c["spine.rx"] = 3; c["chest.rx"] += 3 - 2 * br
    c["shoulderL.raise"] += 2 * br - 2; c["shoulderR.raise"] += 2 * br - 2
    s = wave(f, N, 1)
    c["hips.tx"] = 0.002 * s; c["hips.rz"] = -1.2 * s; c["head.rz"] = 3 + 1.5 * s
    stand_feet(rig, c, spread=0.003)
    blink_ch(c, rig, f, N, [30, 90], slow=1.6)
    return c


@rclip(WOMEN, "gasp", 36, False, props=["jar"], markers={"gasp": 6, "look": 24},
       notes="a step back (right foot), both hands fly to the mouth (the jar stays hanging from the left fist), eyes "
             "round (face gasp), then looks up at the angel; holds looking up, hands at the mouth (eyes clear, A5)")
def w_gasp(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    k = kH(rig)
    fl = pulses(f, N, [(5, 1.0)], decay=1.6, loop=False)
    c["shoulderL.raise"] += 6 * fl; c["shoulderR.raise"] += 6 * fl
    back = ease_io((f - 2) / 10)
    stand_feet(rig, c, spread=0.004, fwdR=-0.022 * back, liftR=0.014 * bump(f, 2, 12))
    c["hips.tz"] = -0.008 * back; c["chest.rx"] += -4 * back
    hold_jar(c, rig, 1.0)
    hm = ease_io((f - 2) / 8)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik2(c, side, V(0.012 * sx, -0.044, 0.034), V(0.9 * sx, -0.6, -0.3), "head", hm) if side == "L" else \
            arm_ik(c, side, V(0.012 * sx, -0.044, 0.034), V(0.9 * sx, -0.6, -0.3), "head", hm)
        c[f"hand{side}.bend"] = lerp(6, 20, hm)
    fingers(c, "R", lerp(22, 12, hm))
    up = ease_io((f - 16) / 12)
    c["neck.rx"] = -8 * up; c["head.rx"] = -2 - 9 * up; c["chest.rx"] += -3 * up
    c["eyelids.sy"] = 1.0
    return c


PEEK = {   # per actor: (mark, the hand on the edge, that wrist's world point (x, z)), base y 0. The right jamb has the
           # rolled stone's left end right beside it (SET.md), so a right hand rests on the stone's rim there.
    "mary": (MARY_DOOR, "R", (-0.273, -0.277)), "joanna": (JOANNA_DOOR, "L", (-0.418, -0.298)),
    "john": (TOMB_DOOR, "L", (-0.418, -0.298))}
EDGE_L = (-0.418, -0.298)        # the rock face left of the door (wrist just in front of it)
EDGE_R = (-0.273, -0.277)        # the rolled stone's rim right of the door (its left end, wrist 0.012 off it)


def local_of(mark, wpt, y, face=DOOR_C):
    yaw = yaw_to(mark, face)
    loc = rot_y(V(wpt[0] - mark[0], 0, wpt[1] - mark[1]), -yaw)
    return V(loc.x, y, loc.z)


def peek_target(ch, y):
    mark, side, w_ = PEEK[ch]
    return side, local_of(mark, w_, y)


def peek_fn(rig, f, N):
    """Leans in at the tomb door (0.07-0.09 in front, face=tombDoor), one hand on the rock beside the opening, looks
    in, a slow look round inside; holds."""
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    k = kH(rig)
    lean = ease_io((f - 2) / 18)
    c["hips.tz"] = -0.010 * lean; c["hips.rx"] = 8 * lean; c["spine.rx"] = 12 * lean; c["chest.rx"] += 8 * lean
    c["neck.rx"] = 4 * lean; c["head.rx"] = -2 + 2 * lean
    side, tgt = peek_target(rig.ch, 0.196 * k)
    sx = 1 if side == "L" else -1
    hw = ease_io((f - 4) / 14)
    arm_ik(c, side, tgt, V(0.9 * sx, -0.3, -0.4), "root", hw)
    c[f"hand{side}.bend"] = lerp(6, -30, hw); fingers(c, side, lerp(22, 14, hw))
    c[f"forearm{side}.twist"] = lerp(-10 * sx, -70 * sx, hw)
    other = "R" if side == "L" else "L"
    if rig.ch in WOMEN and other == "L":
        hold_jar(c, rig)
    else:
        ox = 1 if other == "L" else -1
        arm_ik(c, other, V(0.010 * ox, -0.030, 0.050) * k, V(0.9 * ox, -0.6, -0.2), "chest", hw)
        fingers(c, other, 40)
    look = [(0, 0), (20, 0), (30, -14), (40, -14), (48, 8), (54, 8)]
    c["head.ry"] = 0.8 * K(look, f); c["neck.ry"] = 0.3 * K(look, f)
    stand_feet(rig, c, spread=0.004, fwdR=0.008 * lean if side == "R" else 0.0,
               fwdL=0.008 * lean if side == "L" else 0.0)
    c["eyelids.sy"] = 1.0
    blink_ch(c, rig, f, N, [44], loop=False)
    return c


rclip(WOMEN, "peek", 54, False, props=["jar"], markers={"in": 20},
      notes="at the door mark (MARY_DOOR / JOANNA_DOOR, face=tombDoor): leans forward, one hand on the rock edge "
            "beside the opening (Mary her right hand on the right jamb, Joanna her left on the left jamb, the jar "
            "dangling), looks in and slowly round; holds")(peek_fn)


@rclip("mary", "talk", 96, True,
       notes="spare: gentle talk, the right hand opening palm up, small nods (jaw)")
def mary_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.7)
    k = kH(rig)
    beats = talk_jaw(c, f, N, 41, amp=(4, 11))
    bt = beat_curve(beats, f, N, width=9)
    pr = K([(0, 0.3), (12, 0.9), (40, 0.9), (54, 0.3), (78, 0.7), (96, 0.3)], f, N, True)
    palm_up(c, "R", pr)
    arm_ik(c, "L", V(0.014, -0.006, 0.040) * k, V(0.8, -0.6, -0.2), "chest", 0.7)
    c["head.rx"] = -2 + 3 * bt; c["head.rz"] = 4 * wave(f, N, 1, 0.3)
    stand_feet(rig, c, spread=0.003)
    blink_ch(c, rig, f, N, [10, 64])
    return c


@rclip("mary", "tell", 72, True,
       notes="excited, tumbling news: both hands moving (alternating, palms open, up to the face and out), little "
             "bounces on the toes, quick nods, jaw fast")
def mary_tell(rig, f, N):
    c = h_base(rig, f, N, cycles=3, amp=0.6)
    k = kH(rig)
    beats = talk_jaw(c, f, N, 53, amp=(6, 14))
    bt = beat_curve(beats, f, N, width=7)
    for side, sx, off in (("L", 1, 0.0), ("R", -1, 0.5)):
        ph = 2 * math.pi * (f / N * 2 + off)
        arm_ik(c, side, V((0.070 + 0.018 * math.sin(ph)) * sx, 0.215 + 0.040 * math.cos(ph), 0.074) * k,
               V(0.9 * sx, -0.6, -0.2), "root", 1.0)
        c[f"forearm{side}.twist"] = -60 * sx; c[f"hand{side}.bend"] = -16 + 18 * math.sin(ph - 0.7); fingers(c, side, 6)
    bo = 0.5 + 0.5 * math.cos(2 * math.pi * f / N * 6)
    c["hips.ty"] = 0.005 * bo
    c["head.rx"] = -3 + 4 * bt; c["head.rz"] = 5 * wave(f, N, 2)
    stand_feet(rig, c, spread=0.004, pitchL=10 * bo, pitchR=10 * bo)
    c["eyelids.sy"] = 1.0
    return c


@rclip("mary", "cry", 120, True, markers={"wipeL": 30, "wipeR": 90},
       notes="head down, both hands at the cheeks below the eyes (never over them, A5), wiping tears in turn, "
             "shoulders shaking softly in sobs, a small sway; face cry")
def mary_cry(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    wl = bump(f, 20, 42); wr = bump(f, 80, 102)
    hands_cheeks(c, rig, 1.0, lift=0.0, wipe=(wl * math.sin(2 * math.pi * (f - 20) / 11), wr * math.sin(2 * math.pi * (f - 80) / 11)))
    sob = pulses(f, N, [(8, 1.0), (14, 0.7), (56, 0.9), (62, 0.6), (110, 0.8)], decay=2.0)
    c["shoulderL.raise"] += 4 * sob; c["shoulderR.raise"] += 4 * sob; c["chest.rx"] += 2 * sob
    c["neck.rx"] = 8; c["head.rx"] = 10 + 2 * sob
    s = wave(f, N, 1)
    c["hips.tx"] = 0.002 * s; c["hips.rz"] = -1.2 * s; c["head.rz"] = 4 * s
    stand_feet(rig, c, spread=0.003)
    blink_ch(c, rig, f, N, [50], slow=1.5)
    return c


@rclip("mary", "talk_down", 96, True,
       notes="speaks without looking up: head down and a little aside, the right hand wiping her cheek (below the "
             "eye), the left hand low at her waist; jaw talking")
def mary_talk_down(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.7)
    k = kH(rig)
    talk_jaw(c, f, N, 61, amp=(4, 10))
    wp = math.sin(2 * math.pi * f / N * 3)
    arm_ik(c, "R", V(-0.026, -0.022 + 0.004 * wp, 0.024), V(-0.9, -0.7, -0.2), "head", 1.0)
    c["handR.bend"] = 22; c["forearmR.twist"] = 50; fingers(c, "R", 14)
    arm_ik(c, "L", V(0.020, 0.150, 0.046) * k, V(0.8, -0.4, -0.4), "root", 0.8)
    c["neck.rx"] = 6; c["head.rx"] = 9; c["head.ry"] = -10; c["head.rz"] = 5 + 2 * wave(f, N, 1)
    stand_feet(rig, c, spread=0.003)
    blink_ch(c, rig, f, N, [30, 76], slow=1.4)
    return c


@rclip("mary", "turn_joy", 36, False, markers={"know": 6, "smile": 22},
       notes="she looks up and knows Him: the head comes up fast (`know`), both hands fly to her cheeks (below the "
             "eyes, A5), a gasp up onto her toes leaning back a little, then a big smile with a happy head tilt "
             "(`smile`, face joy); holds, hands at the cheeks")
def mary_turn_joy(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    up = ease_io(f / 6)
    c["neck.rx"] = lerp(6, -6, up); c["head.rx"] = lerp(9, -6, up)
    hm = ease_io((f - 3) / 7)
    hands_cheeks(c, rig, hm, lift=0.0, out=0.6)
    toes = bump(f, 6, 24)
    c["hips.ty"] = 0.006 * toes
    c["chest.rx"] += -5 * toes - 2 * up; c["spine.rx"] = -2 * toes
    c["shoulderL.raise"] += 6 * toes; c["shoulderR.raise"] += 6 * toes
    sm = ease_io((f - 20) / 10)
    c["head.rz"] = 9 * sm; c["head.rx"] += -2 * sm
    c["jaw.rx"] = 9 * bump(f, 6, 20)
    stand_feet(rig, c, spread=0.004, pitchL=12 * toes, pitchR=12 * toes)
    c["eyelids.sy"] = 1.0
    return c


rclip("mary", "hold_hands", 60, True,
      notes="the partner of Jesus's hold_hands: both hands joined with His at chest height (wrists 0.047 in front of her "
            "root), 0.11 apart facing (A1); a happy bounce on her toes and a tilt; face joy")(hold_hands_fn)
mi_reuse("mary", "friend1_cheer", props=[],
         notes="jumps a little with both arms up, high-fives the air, laughing")


# =============================================================================================== ANGEL
@rclip("angel", "idle", 120, True,
       notes="standing, wings folded behind (inner halves back, outer halves folded behind them), hands together, "
             "breathing, a look round (parked pose / cover only; not in the play)")
def angel_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    k = kH(rig)
    hands_clasped(c, rig, V(0.0, 0.150, 0.046) * k, w=0.85)
    look_keys(c, [(0, 0), (20, 0), (36, 16), (66, 16), (82, -12), (108, -12), (120, 0)], f, N)
    wings(c, f, N, "folded", breathe=0.8, cycles=2, seated=False)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [14, 70])
    return c


@rclip("angel", "sit_stone", 120, True, seated=True,
       notes="sits on the rolled stone (base ANGEL_Y, yaw 0 at STONE_ASIDE: the seat rests on the 0.38 top), legs "
             "dangling in front of the stone's face and swinging a little, hands on the top edge beside the hips, "
             "wings half-open breathing slowly; a look round; face smile")
def angel_sit_stone(rig, f, N):
    c = angel_base(rig, f, N, cycles=1)
    stone_hands(c, rig)
    look_keys(c, [(0, 0), (24, 0), (40, -18), (70, -18), (86, 12), (108, 12), (120, 0)], f, N)
    blink_ch(c, rig, f, N, [16, 76])
    return c


@rclip("angel", "wings_open", 48, False, seated=True, markers={"open": 15},
       notes="from sit_stone: the wings spread wide (peak at `open` 0.5 s), hold, and settle back to half-open; the arms "
             "open wide with them and come back to the stone; chest lifts; face joy; ends on sit_stone's first pose")
def angel_wings_open(rig, f, N):
    c = angel_base(rig, 0, 120, cycles=1)
    stone_hands(c, rig)
    o = ease_io(f / 15) * (1 - ease_io((f - 26) / 20))
    wings(c, 0, 120, "open", w=o, breathe=0.0)
    k = kH(rig)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik2(c, side, V(0.130 * sx, SEAT_LOCAL + 0.200, 0.050) * 1.0, V(0.9 * sx, -0.6, -0.3), "root", o)
        c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", 0), -60 * sx, o)
        fingers(c, side, lerp(40, 4, o)); c[f"hand{side}.bend"] = lerp(40, -10, o)
    c["chest.rx"] += -6 * o; c["head.rx"] = -2 - 6 * o
    c["eyelids.sy"] = 1.0
    return c


@rclip("angel", "sit_talk", 96, True, seated=True,
       notes="seated: leans a little toward the women (the chest and head turn to its right, where they stand), the "
             "right hand open palm up, the left on the stone; warm talk (jaw); legs swing slowly")
def angel_sit_talk(rig, f, N):
    c = angel_base(rig, f, N, cycles=1, swing=0.5)
    stone_hands(c, rig, sides="L")
    beats = talk_jaw(c, f, N, 71, amp=(5, 12))
    bt = beat_curve(beats, f, N, width=9)
    pr = K([(0, 0.6), (16, 1.0), (44, 1.0), (60, 0.6), (80, 0.9), (96, 0.6)], f, N, True)
    arm_ik(c, "R", V(-0.075, SEAT_LOCAL + 0.130 + 0.020 * pr, 0.080), V(-0.9, -0.6, -0.3), "root", 1.0)
    c["forearmR.twist"] = 60 + 10 * pr; c["handR.bend"] = -14; fingers(c, "R", 6)
    c["spine.rx"] += 4; c["chest.rx"] += 3 + 1.5 * bt
    c["chest.ry"] = -10; c["neck.ry"] = -6; c["head.ry"] = -8 + 4 * wave(f, N, 1, 0.2)
    c["head.rx"] = -2 + 3 * bt; c["head.rz"] = 4
    wings_follow(c)
    blink_ch(c, rig, f, N, [20, 70])
    return c


POINT_YAW = -63.0        # the tomb door seen from the angel's seat (face viewer): to its right and a little forward


@rclip("angel", "sit_point", 54, False, seated=True, markers={"point": 20, "back": 36},
       notes="seated (keep the actor's yaw = the seat's: face viewer): turns the chest to its right and points to the "
             "tomb door with the whole open right arm ('come and see'), looks along the arm, then looks back at the "
             "women (`back`); the left hand stays on the stone; holds pointing")
def angel_sit_point(rig, f, N):
    c = angel_base(rig, f, N, cycles=1, swing=0.4)
    stone_hands(c, rig, sides="L")
    t = ease_io((f - 2) / 18)
    a = math.radians(POINT_YAW)
    d = V(math.sin(a), 0.10, math.cos(a)).normalized()
    sh = V(-0.050, SEAT_LOCAL + 0.170, 0.0)
    arm_ik(c, "R", sh + d * 0.125 + V(0, 0.030, 0), V(-0.3, -1.0, -0.2), "root", t)
    c["forearmR.twist"] = lerp(10, 60, t); c["handR.bend"] = lerp(6, -12, t); fingers(c, "R", lerp(22, 4, t))
    c["chest.ry"] = -18 * t; c["spine.ry"] = -6 * t; c["chest.rx"] += -2 * t
    look = [(0, 0), (8, 0), (22, -40), (32, -40), (44, -26), (54, -26)]
    c["neck.ry"] = 0.35 * K(look, f); c["head.ry"] = 0.45 * KL(look, f, lag=3) + 0.0
    c["head.rz"] = 5 * ease_io((f - 36) / 10)
    c["jaw.rx"] = 6 * bump(f, 24, 34) + 5 * bump(f, 38, 48)
    wings_follow(c)
    blink_ch(c, rig, f, N, [30], loop=False)
    return c


@rclip("angel", "sit_wave", 48, True, seated=True,
       notes="seated: a big cheerful wave goodbye with the right arm high, a sway, legs swinging happily, the left hand "
             "on the stone; face joy")
def angel_sit_wave(rig, f, N):
    c = angel_base(rig, f, N, cycles=2, swing=1.4)
    stone_hands(c, rig, sides="L")
    arm_wave_up(c, "R", f, N, 2, high=0.9)
    s = wave(f, N, 1)
    c["chest.rz"] = 3 * s; c["head.rz"] = -4 * s; c["chest.ry"] = -8; c["head.ry"] = -10
    wings_follow(c)
    c["jaw.rx"] = 5
    c["eyelids.sy"] = 1.0
    return c


# =============================================================================================== PETER + JOHN
for _nm in ("idle", "talk", "walk", "laugh", "amazed"):
    mi_reuse("peter", "peter_" + _nm)
mi_reuse("john", "friend1_idle", name="idle", phase=FV["john"]["ph"])
reuse_fn("john", "talk", d_talk, 96, True, "The King Who Serves disciples' talk (ls d_talk)",
         notes="talking: the right hand opens palm-up on the phrases, small nods")
mi_reuse("john", "peter_laugh", name="laugh", phase=FV["john"]["ph"],
         notes="a big laugh, the right hand slapping his thigh twice per loop (The King Who Serves disciples' laugh)")
def john_amazed_fn(rig, f, N):
    """Miracles peter_amazed with its opening crouch mostly taken out: John comes from `peek` (standing), Peter from
    `stoop_look` (crouched, so Peter keeps the original)."""
    c = MI_CLIP["peter_amazed"].fn(rig, f, N)
    rise = 1 - ease_io(f / 24)
    c["hips.ty"] = c.get("hips.ty", 0.0) + 0.024 * rise
    c["spine.rx"] = c.get("spine.rx", 0.0) - 10 * rise; c["chest.rx"] = c.get("chest.rx", 0.0) - 5 * rise
    return c


reuse_fn("john", "amazed", john_amazed_fn, 66, False, "Real Miracles clip peter_amazed, the opening crouch reduced",
         markers={"look": 30},
         notes="standing: straightens, mouth falls open, both hands half raised and open, looks slowly round, a little "
               "disbelieving head shake; holds (The King Who Serves disciples' amazed, standing)")


def cheer_open(rig, f, N):
    """The King Who Serves cheer (ls cheer_fn), with an open waving right hand (no palm frond here)."""
    c = cheer_fn(rig, f, N)
    c.pop("palm.aim", None)
    fingers(c, "R", 8)
    return c


for _ch in ("peter", "john", "thomas"):
    reuse_fn(_ch, "cheer", cheer_open, 40, True, "The King Who Serves cheer (ls cheer_fn), open hand",
             phase=FV[_ch]["ph"] if _ch in FV else 0.0, markers={"bounce": 10},
             notes="both arms up: the right hand high waving, the left fist pumping, bouncing, laughing")


def sad_bench(rig, f, N):
    """On the back bench (seat UPPER + 0.04): elbows on the knees, hands loosely together between them, head down,
    slow breathing."""
    c = seated_base(rig, f, N, "bench", cycles=2, amp=1.0)
    k = kH(rig)
    c["spine.rx"] += 14; c["chest.rx"] += 10
    br = K([(0, 0), (40, 1), (60, 1), (100, 0), (120, 0)], f, N, True)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.010 * sx, 0.092 * k, 0.092 * k), V(0.8 * sx, 0.0, -0.4), "root")
        c[f"hand{side}.bend"] = 18; fingers(c, side, 40)
    c["neck.rx"] = 14 + 2 * br; c["head.rx"] = 14 - 2 * br
    c["shoulderL.raise"] += 2 * br; c["shoulderR.raise"] += 2 * br
    c["head.rz"] = 3 * wave(f, N, 1)
    blink_ch(c, rig, f, N, [30, 90], slow=1.6)
    return c


rclip(("peter", "john"), "sit_sad", 120, True, seated=True,
      notes="on the back bench (cushion top UPPER + 0.04; BENCH marks, face viewer): elbows on the knees, hands "
            "together between them, head down, slow breathing; feet on the floor ~0.066 ahead")(sad_bench)


@rclip(("peter", "john"), "jump_up", 27, False, markers={"up": 12},
       notes="from sit_sad: jumps to his feet (a hop, the feet land under him), hands fly up open; ends standing "
             "(A4: this is how they get off the bench)")
def jump_up_fn(rig, f, N):
    a = sad_bench(rig, 0, 120)
    b = h_base(rig, f, N, cycles=1, amp=0.4)
    stand_feet(rig, b, spread=0.006)
    o = ease_io((f - 6) / 14)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(b, side, V(0.080 * sx, 0.200, 0.060) * kH(rig), V(0.9 * sx, -0.6, -0.2), "root", 0.7 * o)
        b[f"forearm{side}.twist"] = -50 * sx; fingers(b, side, 8)
    w = ease_io((f - 2) / 13)
    c = mix(a, b, w)
    hop = bump(f, 6, 20)
    c["hips.ty"] = c.get("hips.ty", 0.0) + 0.014 * hop
    for side in "LR":
        c[f"ik.leg{side}"] = Vector(c[f"ik.leg{side}"]) + V(0, 0.014 * hop, 0)
    c["head.rx"] = c.get("head.rx", 0.0) - 6 * w
    c["eyelids.sy"] = 1.0
    c["floorclamp"] = True
    return c


P_RUN = (0.061, 0.46)
P_RUN_N = 24


@rclip("peter", "run_puff", P_RUN_N, True, phase=False, markers={"contactL": 0, "contactR": 12}, speed=P_RUN,
       notes="a heavy, flat-footed run: low lift, wide feet, the body rolling over each step, arms pumping with bent "
             "elbows, leaning forward, cheeks puffed (face puff); slower than John's run")
def peter_run_puff(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=P_RUN[0], lift=0.012, duty=P_RUN[1], heel=3, toeoff=10, spread=0.010)
    legs_ik_channels(c, g)
    for side in "LR":
        c[f"pole.leg{side}"] = V(0.35 if side == "L" else -0.35, 0, 1)
    p = f / N
    ph = 2 * math.pi * p
    c["hips.ty"] = -0.012 - 0.006 * math.cos(4 * math.pi * (p - 0.23))
    c["hips.tx"] = 0.008 * math.cos(ph); c["hips.rz"] = 6 * math.cos(ph); c["chest.rz"] = -3 * math.cos(ph - 0.4)
    c["hips.rx"] = 8; c["spine.rx"] = 8; c["chest.rx"] += 4; c["head.rx"] = -8 + 3 * math.cos(4 * math.pi * p)
    c["hips.ry"] = 5 * math.sin(ph); c["chest.ry"] = -7 * math.sin(ph - 0.3)
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -6
        c[f"upperArm{side}.bend"] = 14 + sg * 34 * math.sin(ph - 0.25)
        c[f"forearm{side}.bend"] = 82 + sg * 10 * math.sin(ph - 0.9)
        fingers(c, side, 70)
    c["jaw.rx"] = 2
    c["eyelids.sy"] = 1.0
    return c


@rclip("peter", "puff", 60, True, markers={"breath1": 10, "breath2": 40},
       notes="bent over, hands on his knees, catching his breath: two big heaving breaths per loop (chest and "
             "shoulders), head up looking ahead, cheeks puffing (face puff)")
def peter_puff(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=1.6)
    k = kH(rig)
    c["hips.ty"] = -0.026; c["hips.tz"] = -0.018
    c["hips.rx"] = 28; c["spine.rx"] = 18; c["chest.rx"] += 10
    br = pulses(f, N, [(10, 1.0), (40, 1.0)], decay=1.6)
    c["chest.rx"] += -4 * br; c["shoulderL.raise"] += 6 * br; c["shoulderR.raise"] += 6 * br
    c["neck.rx"] = -16; c["head.rx"] = -10 - 3 * br
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.040 * sx, 0.112 * k, 0.050 * k), V(0.9 * sx, -0.2, -0.3), "root", 1.0)
        c[f"hand{side}.bend"] = 20; fingers(c, side, 40)
    c["jaw.rx"] = 5 + 6 * br
    stand_feet(rig, c, spread=0.014)
    blink_ch(c, rig, f, N, [24])
    return c


STOOP_N = 84


@rclip("peter", "stoop_look", STOOP_N, False, markers={"in": 20, "look": 44, "out": 66},
       notes="at TOMB_DOOR (the door 0.07 in front, top 0.34; face tombDoor): bends his knees and back and ducks his "
             "head under the low lintel into the doorway, bracing his hands on the door's edges (the left on the rock "
             "face, the right on the rolled stone's rim), looks round inside (left, right), then turns his head back "
             "out to John on his left (`out`); his top stays under the door top; holds")
def peter_stoop_look(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    dn = ease_io((f - 2) / 18)
    c["hips.ty"] = -0.040 * dn; c["hips.tz"] = -0.018 * dn
    c["hips.rx"] = 6 * dn; c["spine.rx"] = 20 * dn; c["chest.rx"] += 12 * dn
    c["neck.rx"] = 12 * dn; c["head.rx"] = -16 * dn
    hw = ease_io((f - 4) / 14)
    for side, sx, w_, yy in (("L", 1, EDGE_L, 0.215), ("R", -1, EDGE_R, 0.200)):
        arm_ik(c, side, local_of(TOMB_DOOR, w_, yy), V(0.9 * sx, -0.3, -0.3), "root", hw)
        c[f"hand{side}.bend"] = lerp(6, -36, hw); fingers(c, side, lerp(22, 12, hw))
        c[f"forearm{side}.twist"] = lerp(-10 * sx, -70 * sx, hw)
    look = [(0, 0), (22, 0), (30, -24), (42, -24), (50, 20), (58, 20), (66, 34), (84, 34)]
    c["head.ry"] = 0.65 * K(look, f); c["neck.ry"] = 0.35 * K(look, f)
    c["head.rz"] = -4 * ease_io((f - 66) / 10)
    c["jaw.rx"] = 4 * bump(f, 66, 80)
    stand_feet(rig, c, spread=0.012, fwdR=0.006 * dn)
    c["eyelids.sy"] = 1.0
    blink_ch(c, rig, f, N, [56], loop=False)
    return c


def shock_fn(rig, f, N):
    """Jumps back (a little hop, both feet land 0.025 back), hands up palms out at the shoulders, eyes wide, knees
    knocking (comic), teeth chattering."""
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    k = kH(rig)
    a = amp_of(rig) if rig.ch in FV else 1.1
    bk = ease_io((f - 3) / 10)
    hop = bump(f, 3, 15)
    c["hips.ty"] = 0.010 * hop * a - 0.012 * ease_io((f - 14) / 6)
    c["hips.tz"] = -0.026 * bk
    c["chest.rx"] += -8 * bk + 3 * ease_io((f - 16) / 8); c["head.rx"] = -4 * bk
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.084 * sx, 0.262, 0.050) * k, V(0.9 * sx, -0.8, -0.2), "root", ease_io((f - 2) / 7))
        c[f"forearm{side}.twist"] = -72 * sx; c[f"hand{side}.bend"] = -24; fingers(c, side, 2)
    knock = math.sin(2 * math.pi * (f - 16) / 6) * ease_io((f - 16) / 6)
    stand_feet(rig, c, spread=0.010, fwd=-0.026 * bk, liftL=0.012 * hop, liftR=0.012 * hop)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"pole.leg{side}"] = V(-0.45 * sx * (0.6 + 0.4 * knock), 0, 1)
    c["jaw.rx"] = 4 + 3 * abs(math.sin(2 * math.pi * f / 4)) * ease_io((f - 14) / 6)
    c["shoulderL.raise"] += 6 * bk; c["shoulderR.raise"] += 6 * bk
    c["eyelids.sy"] = 1.0
    return c


rclip(("peter", "john"), "shock", 54, False, markers={"jump": 3, "land": 15},
      notes="'A g-g-ghost?': jumps back (a hop, both feet land 0.026 back), hands up palms out, eyes wide, knees "
            "knocking (bent in, alternating) and teeth chattering, comic; holds hands up (Miracles has no standing "
            "Peter shock, so Peter shares John's)")(shock_fn)

J_RUN = (0.052, 0.36)
J_RUN_N = 18


@rclip("john", "run", J_RUN_N, True, phase=False, markers={"contactL": 0, "contactR": 9}, speed=J_RUN,
       notes="a light, fast run: long flight, high knees, leaning forward, arms swinging wide, the sash flying")
def john_run(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=J_RUN[0], lift=0.026, duty=J_RUN[1], heel=4, toeoff=30)
    legs_ik_channels(c, g)
    p = f / N
    ph = 2 * math.pi * p
    c["hips.ty"] = -0.008 - 0.007 * math.cos(4 * math.pi * (p - 0.18))
    c["hips.rx"] = 8; c["spine.rx"] = 6; c["chest.rx"] += 2; c["head.rx"] = -8
    c["hips.ry"] = 7 * math.sin(ph); c["chest.ry"] = -10 * math.sin(ph - 0.3); c["hips.rz"] = 2 * math.cos(ph)
    for side, sg in (("L", -1), ("R", 1)):
        c[f"upperArm{side}.raise"] = -12
        c[f"upperArm{side}.bend"] = 12 + sg * 40 * math.sin(ph - 0.25)
        c[f"forearm{side}.bend"] = 66 + sg * 16 * math.sin(ph - 0.9)
        fingers(c, side, 30)
    c["jaw.rx"] = 3
    blink_ch(c, rig, f, N, [10])
    return c


@rclip("john", "wave_hurry", 32, True, markers={"beckon1": 6, "beckon2": 22},
       notes="'Come on!': jogging on the spot (heels up in turn, a bounce), beckoning with both arms twice per loop "
             "(reach forward, pull back with curled fingers), nodding; jaw")
def john_wave_hurry(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.4)
    k = kH(rig)
    ph = 2 * math.pi * f / N
    lL = max(0.0, math.sin(ph)); lR = max(0.0, -math.sin(ph))
    c["hips.ty"] = -0.004 + 0.004 * abs(math.cos(ph))
    stand_feet(rig, c, spread=0.006, pitchL=22 * lL, pitchR=22 * lR, liftL=0.004 * lL, liftR=0.004 * lR)
    bk = 0.5 + 0.5 * math.cos(2 * ph)          # 1 = arms reaching out, 0 = pulled back up by the shoulders
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V((0.070 + 0.010 * bk) * sx, 0.300 - 0.090 * bk, 0.025 + 0.090 * bk) * k,
               V(0.9 * sx, -0.7, -0.2), "root", 1.0)
        c[f"forearm{side}.twist"] = 50 * sx; c[f"hand{side}.bend"] = 40 - 50 * bk; fingers(c, side, 75 - 65 * bk)
    c["head.rx"] = -2 + 4 * math.cos(2 * ph); c["chest.rx"] += -2
    c["jaw.rx"] = 6 + 4 * bk
    c["eyelids.sy"] = 1.0
    return c


rclip("john", "peek", 54, False, markers={"in": 20},
      notes="as Mary's peek (shared function): at TOMB_DOOR facing the door, the right hand on the rock beside the "
            "opening, leans in and looks round; holds")(peek_fn)


# =============================================================================================== THOMAS
mi_reuse("thomas", "friend1_idle", name="idle", phase=FV["thomas"]["ph"])


def doubt_pose(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    folded_arms(c, rig)
    c["neck.ry"] = 12; c["head.ry"] = 14
    c["chest.rx"] += -3; c["head.rx"] = -4
    c["hips.tx"] = 0.006; c["hips.rz"] = -3
    stand_feet(rig, c, spread=0.008, fwdR=0.010)
    return c


@rclip("thomas", "doubt", 120, True, markers={"shake": 50},
       notes="arms crossed, weight on one leg, looks away, a slow shake of the head (twice, at `shake`), a small "
             "frown (face doubt)")
def thomas_doubt(rig, f, N):
    c = doubt_pose(rig, f, N)
    shk = bump(f, 40, 84)
    c["head.ry"] += 16 * math.sin(2 * math.pi * (f - 40) / 22) * shk
    c["jaw.rx"] = 3 * bump(f, 92, 104)
    blink_ch(c, rig, f, N, [20, 100])
    return c


@rclip("thomas", "shock", 36, False, markers={"jump": 4},
       notes="from doubt: a step back (right foot), the arms uncross and come up open at the chest, eyes wide, head "
             "back a little; holds")
def thomas_shock(rig, f, N):
    a = doubt_pose(rig, 0, 120)
    b = h_base(rig, f, N, cycles=1, amp=0.3)
    k = kH(rig)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(b, side, V(0.070 * sx, 0.228, 0.062) * k, V(0.9 * sx, -0.7, -0.2), "root", 1.0)
        b[f"forearm{side}.twist"] = -66 * sx; b[f"hand{side}.bend"] = -20; fingers(b, side, 4)
    b["chest.rx"] += -6; b["head.rx"] = -6
    stand_feet(rig, b, spread=0.008, fwdR=-0.020)
    b["hips.tz"] = -0.008
    w = ease_io((f - 2) / 10)
    c = mix(a, b, w)
    c["ik.legR"] = Vector(c["ik.legR"]) + V(0, 0.014 * bump(f, 2, 12), 0)
    c["shoulderL.raise"] = c.get("shoulderL.raise", 0.0) + 6 * bump(f, 2, 16)
    c["shoulderR.raise"] = c.get("shoulderR.raise", 0.0) + 6 * bump(f, 2, 16)
    c["eyelids.sy"] = 1.0
    return c


REACH_STEP = 0.004
_REACH = {}


def reach_palm():
    """Jesus's left palm in show_hands (frame 0) in Thomas's root space (Jesus PAIR_D in front, facing Thomas)."""
    p = partner_pose("jesus_show_hands", 0)
    h, t = p["handL"]
    q = h + (t - h) * 0.9 + V(0, 0.006, 0)
    return V(-q.x, q.y, PAIR_D - q.z)


def reach_pose(rig, f, N, wrist):
    b = h_base(rig, f, N, cycles=1, amp=0.3)
    st = ease_io((f - 4) / 18)
    stand_feet(rig, b, spread=0.008, fwdR=REACH_STEP * st, fwdL=REACH_STEP * ease_io((f - 10) / 16))
    b["ik.legR"] = Vector(b["ik.legR"]) + V(0, 0.010 * bump(f, 4, 22), 0)
    b["hips.tz"] = REACH_STEP * st - 0.006
    b["hips.rx"] = -3; b["spine.rx"] = 2; b["neck.rx"] = 14; b["head.rx"] = 12
    b["chest.ry"] = 8; b["head.ry"] = 6                      # turned a little toward the hand he touches
    arm_ik(b, "R", wrist, V(-0.9, -0.5, -0.4), "root", 1.0)
    b["handR.bend"] = -24; fingers(b, "R", 6)
    arm_ik(b, "L", V(0.012, -0.030, 0.050), V(0.9, -0.6, 0.0), "chest", 1.0)   # the other hand to his chest
    b["handL.bend"] = 10; fingers(b, "L", 30)
    return b


def reach_wrist(rig):
    """The right wrist target that puts Thomas's fingertips on the palm (solved: three corrections on the end pose)."""
    if rig.ch not in _REACH:
        palm = reach_palm()
        wrist = palm + V(0.0, 0.010, -0.020)
        for _ in range(4):
            _, _, M = solve_pose(rig, reach_pose(rig, 60, 60, wrist))
            tip = rig.pos(M, "fingersR", "tail")
            wrist = wrist + (palm + V(0, 0.004, 0) - tip)
        _REACH[rig.ch] = (wrist, round((palm + V(0, 0.004, 0) - tip).length, 4))
    return _REACH[rig.ch][0]


@rclip("thomas", "reach", 60, False, markers={"touch": 34},
       notes="pair with Jesus's show_hands (Jesus 0.11 in front, facing): a small step closer (both feet 0.004; at 0.11 "
             "there is no room for more), reaches out and gently touches His left palm with the fingertips of his right "
             "hand (`touch`; the wrist target is solved so the fingertips land on the palm), the left hand to his "
             "chest, head bowed to look; holds")
def thomas_reach(rig, f, N):
    a = thomas_shock(rig, 36, 36)
    b = reach_pose(rig, f, N, reach_wrist(rig))
    w = ease_io((f - 2) / 30)
    c = mix(a, b, w)
    c["eyelids.sy"] = 1.0
    blink_ch(c, rig, f, N, [48], loop=False)
    return c


@rclip("thomas", "kneel_worship", 60, False, seated=True, markers={"down": 28, "look": 40},
       notes="sinks to both knees, both hands to his chest, then looks up at Jesus (face awe); holds kneeling "
             "(meshMinY >= -0.008)")
def thomas_kneel_worship(rig, f, N):
    a = thomas_reach(rig, 60, 60)
    b = h_base(rig, f, N, cycles=1, amp=0.4)
    kneel_both(rig, b, 1.0, lean=0.0)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(b, side, V(0.010 * sx, -0.030 + 0.006 * (side == "R"), 0.050), V(0.9 * sx, -0.6, 0.0), "chest", 1.0)
        b[f"hand{side}.bend"] = 10; fingers(b, side, 30)
    up = ease_io((f - 30) / 14)
    b["neck.rx"] = -8 * up; b["head.rx"] = -2 - 16 * up; b["chest.rx"] += -4 * up
    w = ease_io((f - 2) / 26)
    c = mix(a, b, w)
    c["floorclamp"] = True
    blink_ch(c, rig, f, N, [50], loop=False, slow=1.6)
    return c


# =============================================================================================== JOANNA (shared above)
# idle, walk, idle_jar, walk_jar, sad, gasp, peek, run are registered for both women by rclip(WOMEN, ...).


# =============================================================================================== checks
def contract_clips():
    return {"jesus": ["idle", "talk", "walk", "wave", "appear", "call_name", "hold_hands", "peace", "show_hands",
                      "eat_fish"],
            "mary": ["idle", "walk", "talk", "idle_jar", "walk_jar", "sad", "gasp", "peek", "run", "tell", "cry",
                     "talk_down", "turn_joy", "hold_hands", "cheer"],
            "angel": ["idle", "sit_stone", "wings_open", "sit_talk", "sit_point", "sit_wave"],
            "peter": ["idle", "talk", "walk", "laugh", "amazed", "shock", "sit_sad", "jump_up", "run_puff", "puff",
                      "stoop_look", "cheer"],
            "john": ["idle", "talk", "laugh", "amazed", "sit_sad", "jump_up", "run", "wave_hurry", "peek", "shock",
                     "cheer"],
            "thomas": ["idle", "doubt", "shock", "reach", "kneel_worship", "cheer"],
            "joanna": ["idle", "walk", "idle_jar", "walk_jar", "sad", "gasp", "peek", "run"]}


def stage_of(cl):
    """Where a clip is shown in renders and set checks: (x, z, yaw, y, on_set)."""
    n, ch = cl.name, cl.ch
    if ch == "angel":
        return (STONE_C[0], STONE_C[1], 0.0, ANGEL_Y, True) if n != "idle" else (OPEN[0], OPEN[1], 0.0, 0.0, False)
    if n == "peek":
        m = PEEK[ch][0]
        return (m[0], m[1], yaw_to(m, DOOR_C), 0.0, True)
    if n == "stoop_look":
        return (TOMB_DOOR[0], TOMB_DOOR[1], yaw_to(TOMB_DOOR, DOOR_C), 0.0, True)
    if n == "puff":
        return (PETER_PUFF[0], PETER_PUFF[1], yaw_to(PETER_PUFF, DOOR_C), 0.0, True)
    if n in ("sit_sad", "jump_up"):
        x, z = BENCH[ch]
        return (x, z, 0.0, UPPER, True)
    if n == "eat_fish":
        return (TABLE_J[0], TABLE_J[1], yaw_to(TABLE_J, LOWTABLE_C), UPPER, True)
    if ch == "thomas" and n in ("reach", "kneel_worship", "shock", "doubt"):
        return (THOMAS_TOUCH[0], THOMAS_TOUCH[1], 90.0, UPPER, True)
    if ch == "jesus" and n == "show_hands":
        return (ROOM_J[0], ROOM_J[1], -90.0, UPPER, True)
    if ch == "jesus" and n == "hold_hands":
        return (JESUS_G[0], JESUS_G[1], yaw_to(JESUS_G, MARY_MEET), 0.0, True)
    if ch == "mary" and n == "hold_hands":
        return (MARY_MEET[0], MARY_MEET[1], yaw_to(MARY_MEET, JESUS_G), 0.0, True)
    if ch in WOMEN and n == "gasp":
        return (MARY_T[0], MARY_T[1], yaw_to(MARY_T, STONE_C), 0.0, True)
    if ch == "mary" and n in ("cry", "talk_down", "turn_joy"):
        return (MARY_CRY[0], MARY_CRY[1], 0.0, 0.0, True)
    return (OPEN[0], OPEN[1], 0.0, 0.0, False)


SET_BVH = {}


def load_set_bvh():
    """Import garden.glb and build world-space BVH trees (Blender coords) of the nodes the clips touch. `rock` =
    tombHill + tombDoor (the door reveal faces, so a point in the opening is not counted as inside the hill)."""
    if SET_BVH:
        return SET_BVH
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=SET_GLB)
    new = [o for o in bpy.data.objects if o not in before]
    groups = {"rock": ("tombHill", "tombDoor"), "stoneAside": ("tombStoneAside",), "bench": ("bench",),
              "table": ("lowTable", "fishPlate"), "house": ("house", "houseIn"), "jar": ("waterJar",)}
    for key, names in groups.items():
        vs, ps = [], []
        for o in new:
            if o.type == 'MESH' and o.name.split(".")[0] in names:
                mw = o.matrix_world
                off = len(vs)
                vs += [mw @ v.co for v in o.data.vertices]
                ps += [[off + i for i in p.vertices] for p in o.data.polygons]
        SET_BVH[key] = BVHTree.FromPolygons(vs, ps)
    for o in new:
        bpy.data.objects.remove(o, do_unlink=True)
    return SET_BVH


def inside(bvh, p_d, maxd=0.06):
    hit = bvh.find_nearest(to_bl(p_d), maxd)
    if hit[0] is None:
        return False, None
    loc, nor = hit[0], hit[1]
    if nor.z < -0.7:                 # a mesh's closed underside on the ground: points just above it are outside
        return False, hit[3]
    dv = to_bl(p_d) - loc
    if dv.length < 0.0008:
        return False, hit[3]
    # behind the nearest face AND mostly along its normal (a point beside a jamb edge is off to the side, not inside)
    return dv.normalized().dot(nor) < -0.5, hit[3]


SET_CHECK_NODES = {
    "angel": ("rock", "stoneAside"), "peek": ("rock", "stoneAside"), "stoop_look": ("rock", "stoneAside"), "puff": ("rock",),
    "sit_sad": ("bench", "jar", "house"), "jump_up": ("bench", "jar", "house"), "eat_fish": ("table", "house"),
    "thomas": ("house",), "show_hands": ("house",), "gasp": ("rock", "stoneAside"),
}


def set_checks():
    """Per staged clip, on its story mark with the real set: proxy points inside set meshes (by node and bone), and the
    special numbers: the angel's seat gap on the stone top and legs vs the stone's front face; Peter's top beyond the
    door plane; the eat_fish hand to the plate at FISH_ON."""
    bv = load_set_bvh()
    sanity = {"doorCentreInsideRock": inside(bv["rock"], V(-0.33, 0.15, -0.33))[0],
              "hillInsideRock": inside(bv["rock"], V(-0.50, 0.10, -0.45), 0.2)[0]}
    out = {"sanity": sanity}
    for cl in CLIPS:
        x, z, yaw, y, on = stage_of(cl)
        if not on:
            continue
        key = "angel" if cl.ch == "angel" else ("thomas" if cl.ch == "thomas" else cl.name)
        nodes = SET_CHECK_NODES.get(key)
        if not nodes:
            continue
        rig = RIGS[cl.ch]
        frames = bake_clip(rig, cl)
        res = {"mark": [round(x, 4), round(z, 4), round(yaw, 1), y], "inside": {}, "insideBones": {}, "depthMax": {}}
        step = 3
        seat_gaps, legs_bad, beyond_top, top = [], 0, -1.0, -1.0
        for fr in range(0, cl.N + 1, step):
            M = frames[fr][1]
            pts = world_pts(rig, M, (x, z, yaw, y))
            for p, dom in pts:
                top = max(top, p.y)
                if p.y - y < 0.012:          # feet on the floor: meshMinY's job (the set's ground skirts confuse it)
                    continue
                for nd in nodes:
                    ins, dd = inside(bv[nd], p)
                    if ins:
                        res["inside"][nd] = res["inside"].get(nd, 0) + 1
                        kk = f"{nd}:{dom}"
                        res["insideBones"][kk] = res["insideBones"].get(kk, 0) + 1
                        res["depthMax"][kk] = round(max(res["depthMax"].get(kk, 0.0), dd), 4)
                if cl.name in ("stoop_look", "peek") and p.z < DOOR_Z:
                    beyond_top = max(beyond_top, p.y)
            if cl.ch == "angel":
                loc = [(q, d) for q, (co, ws, d) in zip(rig.skin(M), rig.proxy)]
                seat = [q.y + y for q, d in loc if d in ("hips", "thighL", "thighR") and on_stone(q)]
                if seat:
                    seat_gaps.append(min(seat) - STONE_TOP)
                for q, d in loc:
                    if d.startswith(("shin", "foot", "toe")):
                        u, n = stone_frame(q)
                        if abs(u) < 0.19 and n < STONE_HALF_T + 0.002:
                            legs_bad += 1
        res["top"] = round(top, 4)
        if seat_gaps:
            res["seatGapMin"] = round(min(seat_gaps), 4); res["seatGapMax"] = round(max(seat_gaps), 4)
            res["legPointsBehindStoneFace"] = legs_bad
        if beyond_top > 0:
            res["topBeyondDoorPlane"] = round(beyond_top, 4)
        if cl.name == "eat_fish":
            M = frames[FISH_ON][1]
            h = rig.pos(M, "fish") if "fish" in rig.names else rig.pos(M, "handR")
            wp = rot_y(h, yaw) + V(x, y, z)
            res["fishBoneAtTake"] = [round(v, 4) for v in wp]
            res["fishBoneToPlate"] = round((wp - V(0.50, 0.157, -0.31)).length, 4)
        out[cl.action] = res
        print("RS_SET", cl.action, json.dumps(res), flush=True)
    return out


PAIR_CHECKS = [  # (A, B, distance, mode)
    ("jesus_hold_hands", "mary_hold_hands", PAIR_D, "meet"),
    ("jesus_show_hands", "thomas_reach", PAIR_D, "touch"),
    ("jesus_show_hands", "thomas_kneel_worship", PAIR_D, "touch"),
]
ARM_BONES = {"upperArmL", "upperArmR", "forearmL", "forearmR", "handL", "handR", "fingersL", "fingersR", "fish", "jar"}


def pair_marks(mode, dist):
    """(markA, markB) as (x, z, yaw, y): meet = A at JESUS_G facing MARY_MEET, B `dist` along that line facing A;
    touch = A at ROOM_J facing -X, B `dist` to its -X facing +X (y UPPER)."""
    if mode == "meet":
        yaw = yaw_to(JESUS_G, MARY_MEET)
        a = math.radians(yaw)
        bx, bz = JESUS_G[0] + dist * math.sin(a), JESUS_G[1] + dist * math.cos(a)
        return (JESUS_G[0], JESUS_G[1], yaw, 0.0), (bx, bz, yaw + 180.0, 0.0)
    if mode == "touch":
        return (ROOM_J[0], ROOM_J[1], -90.0, UPPER), (ROOM_J[0] - dist, ROOM_J[1], 90.0, UPPER)
    raise ValueError(mode)


def pair_check():
    clips = {c.action: c for c in CLIPS}
    out = {}
    for a, b, dist, mode in PAIR_CHECKS:
        ca, cb = clips[a], clips[b]
        ra, rb = RIGS[ca.ch], RIGS[cb.ch]
        fa, fb = bake_clip(ra, ca), bake_clip(rb, cb)
        ma, mb = pair_marks(mode, dist)
        body, hands = (1.0, 0, 0), 1.0
        for fr in range(0, max(ca.N, cb.N) + 1, 3):
            Ma = fa[fr % ca.N if ca.loop else min(fr, ca.N)][1]
            Mb = fb[fr % cb.N if cb.loop else min(fr, cb.N)][1]
            pa = world_pts(ra, Ma, ma); pb = world_pts(rb, Mb, mb)
            d = pair_min_dist([p for p, dm in pa if dm not in ARM_BONES], [p for p, dm in pb if dm not in ARM_BONES],
                              eps=0.03)
            if d[0] < body[0]:
                body = (d[0], d[1], fr)
            ha = [p for p, dm in pa if dm in ("handL", "handR", "fingersL", "fingersR")]
            hb = [p for p, dm in pb if dm in ("handL", "handR", "fingersL", "fingersR")]
            hd = pair_min_dist(ha, hb, eps=0.03)[0]
            if fr >= min(ca.N, cb.N) * 0.6 or ca.loop and cb.loop:
                hands = min(hands, hd)
        out[f"{a}+{b}@{dist}"] = {"bodyMinDist(no arms)": body[0], "bodyPointsCloser4mm": body[1], "atFrame": body[2],
                                  "handsMinDist": round(hands, 4)}
    return out


def a8_check():
    """A8: one actor given two clips at the same instant (only the second is seen)."""
    seen, out = {}, []
    for a in TL["acting"]:
        k = (a["who"], round(a["t"], 3))
        if k in seen and seen[k] != a["clip"]:
            out.append({"who": a["who"], "t": a["t"], "clips": [seen[k], a["clip"]]})
        seen[k] = a["clip"]
    return out


SAMPLE_BONES = ("root", "head", "jaw", "handR", "handL", "footL", "footR", "hips", "belt1", "sash1", "mantle1",
                "cloth1", "cloak1", "veil1", "wingL1", "wingL2", "wingR2", "fish", "jar")


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
            "stage": {"upper": UPPER, "benchSeat": BENCH_SEAT, "stoneTop": STONE_TOP, "angelY": ANGEL_Y,
                      "angelSeatLocal": round(SEAT_LOCAL, 4), "stoneAside": STONE_C, "stoneYaw": STONE_YAW,
                      "angelMode": "angel at STONE_ASIDE, base y ANGEL_Y, yaw 0 (face viewer) in EVERY seated clip; the "
                      "seat is fitted to that yaw (the stone's top runs diagonally); do not turn the angel with face=",
                      "pairDistance": PAIR_D, "holdHandsY": HH_Y, "showHands": {"y": SH_Y, "z": SH_Z},
                      "fishOnFrame": FISH_ON, "doorPlaneZ": DOOR_Z, "doorTop": DOOR_TOP}}
    only = os.environ.get("RS_ONLY")
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
            info["stride"] = cl.speed[0]
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        if cl.loop:
            info["loopSeamMaxErr"] = info["checks"]["seamStep"]
        print("RS_CHECK", cl.action, json.dumps(info["checks"]), flush=True)
        meta["clips"].append(info)
    meta["travel"] = travel_needs()
    for r in meta["travel"]:
        print("RS_TRAVEL", json.dumps(r))
    meta["a8"] = a8_check()
    print("RS_A8", json.dumps(meta["a8"]))
    if not only or os.environ.get("RS_PAIRCHECK") == "1":
        meta["pairCheck"] = pair_check()
        print("RS_PAIR", json.dumps(meta["pairCheck"]))
    meta["setCheck"] = set_checks() if (not only or os.environ.get("RS_SETCHECK") == "1") else {}
    if only:
        print("RS_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "rs_anim.blend")
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
        print("RS_EXPORT", ch)
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("RS_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


# =============================================================================================== render helpers
REGIONS = json.load(open(REGIONS_JSON))
FACES = {ch: {"default": v["faceDecal"]["default"], "clips": v["faceDecal"].get("clipExpression", {})}
         for ch, v in list(REGIONS["characters"].items()) + list(REGIONS.get("offSheet", {}).items())}
DECAL_NODES = {}
DIST_K = {ch: 1.35 for ch in CHARS}
PROP_ON = {("jesus", "eat_fish"): {"fish": FISH_ON}}


def set_props_for_frame(rig, cl, fr):
    for p, at in PROP_ON.get((cl.ch, cl.name), {}).items():
        o = bpy.data.objects.get(f"{cl.ch}_{p}")
        if o:
            o.hide_render = fr < at
    fo = bpy.data.objects.get("fishOnPlate")
    if fo is not None:
        fo.hide_render = (cl.ch, cl.name) == ("jesus", "eat_fish") and fr >= FISH_ON


def render_pair(sc, cam, rigs, a, b, dist, mode, frames_sel, views, d, prefix):
    clips = {c.action: c for c in CLIPS}
    ca, cb = clips[a], clips[b]
    ra, rb = rigs[ca.ch], rigs[cb.ch]
    show_only(rigs, [ca.ch, cb.ch], {ca.ch: ca, cb.ch: cb})
    set_expression(ca.ch, ca.name); set_expression(cb.ch, cb.name)
    fa, fb = bake_clip(ra, ca), bake_clip(rb, cb)
    ma, mb = pair_marks(mode, dist)
    out = []
    for fr in frames_sel:
        apply_basis(ra, fa[fr % ca.N if ca.loop else min(fr, ca.N)][0])
        apply_basis(rb, fb[fr % cb.N if cb.loop else min(fr, cb.N)][0])
        place_mark(ra, ma); place_mark(rb, mb)
        bpy.context.view_layer.update()
        T = V((ma[0] + mb[0]) / 2, mb[3] + 0.17, (ma[1] + mb[1]) / 2)
        ax = V(mb[0] - ma[0], 0, mb[1] - ma[1]).normalized()
        side = V(-ax.z, 0, ax.x)
        if side.z < 0:
            side = -side
        cams = {"side": T + side * 0.48 + V(0, 0.04, 0), "q3": T + side * 0.36 + ax * 0.20 + V(0, 0.12, 0),
                "q3b": T + side * 0.36 - ax * 0.20 + V(0, 0.12, 0), "top": T + V(0.0, 0.50, 0.12),
                "phone": T + V(0.10, 0.42, 0.80), "front": T + V(0, 0.05, 0.55)}
        for vn in views:
            look(cam, T, cams[vn], lens=40)
            fn = f"{prefix}_{fr:03d}_{vn}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True); out.append((fr, vn, fn))
    reset_pose(ra); reset_pose(rb)
    return out


def cam_for(cam, rig, mark, view, dk):
    if view == "phone":           # the play's camera distance on a phone (dist ~0.5-0.6 at height ~0.2, SET.md §4)
        x, z, yaw0, y = mark[:4]
        tg = V(x, y + rig.H * 0.5, z)
        look(cam, tg, V(x + 0.10, y + 0.30, z + 0.60), lens=40)
        return
    if view in WORLD_VIEWS:       # world-fixed views (the set's walls would block actor-relative ones)
        x, z, yaw0, y = mark[:4]
        tg = V(x, y + rig.H * float(os.environ.get("RS_PROBE_AIM", "0.5")), z)
        look(cam, tg, tg + WORLD_VIEWS[view] * (dk / 1.35), lens=40)
        return
    mark_cam(cam, rig, mark[:4], view, dk)


WORLD_VIEWS = {"wfront": V(0, 0.10, 0.55), "wfl": V(-0.36, 0.14, 0.42), "wfr": V(0.36, 0.14, 0.42),
               "wtop": V(0, 0.60, 0.16), "wleft": V(-0.50, 0.08, 0.12), "wright": V(0.50, 0.08, 0.12)}


def contact_view(cl, mark):
    """Staged clips: world-fixed views from the open side of the set (actor-relative cameras end up inside walls)."""
    if not mark[4]:
        return "q3"
    if cl.ch == "angel":
        return "wfront"
    if cl.name in ("gasp", "puff") or (cl.name == "peek" and cl.ch == "mary"):
        return "wfr"
    if cl.name == "peek" and cl.ch == "joanna":
        return "wfront"
    if cl.name in ("peek", "stoop_look"):
        return "wfl"
    return "wfront"


def mode_contact():
    sc, rigs = open_scene()
    setup_look_ls(sc, (300, 300), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    for cl in CLIPS:
        if cl.ch == "joanna" and cl.name not in ("peek", "gasp"):
            continue        # Joanna shares Mary's functions; her two staged clips are shown
        rig = rigs[cl.ch]
        show_only(rigs, [cl.ch], {cl.ch: cl})
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
            cam_for(cam, rig, mark, view, DIST_K[cl.ch] * (1.5 if cl.ch == "angel" else 1.0))
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("RS_CONTACT_ROW", cl.action, picks, flush=True)
    use_set(True)
    for a, b, dist, mode in PAIR_CHECKS:
        row = {"action": f"pair: {a.split('_', 1)[1]} + {b} ({dist})", "loop": True, "frames_total": 0, "frames": []}
        for fr, views in [(0, ("side",)), (20, ("side",)), (40, ("q3",)), (60, ("phone",))]:
            for f_, vn, fn in render_pair(sc, cam, rigs, a, b, dist, mode, [fr], views, d, f"pair_{a}_{b}"):
                row["frames"].append({"f": f_, "file": fn, "marker": vn})
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """RS_PROBE="action:f1,f2:view,view;..."  view = front|q3|side|back|q3l|lside|top|low|phone.
    'pair:<A>:<B>:<dist>:<f1,f2>[:mode[:views]]' (modes meet | touch). RS_PROBE_SET=0 hides the set."""
    sc, rigs = open_scene()
    res = int(os.environ.get("RS_PROBE_RES", "440"))
    setup_look_ls(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    for f_ in os.listdir(d):
        os.remove(os.path.join(d, f_))
    clips = {cl.action: cl for cl in CLIPS}
    out = []
    for item in os.environ.get("RS_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "pair":
            use_set(True)
            a, b, dist = parts[1], parts[2], float(parts[3])
            frs = [int(v) for v in parts[4].split(",")]
            mode = parts[5] if len(parts) > 5 else "meet"
            views = parts[6].split(",") if len(parts) > 6 else ["side", "q3"]
            out += [fn for _, _, fn in render_pair(sc, cam, rigs, a, b, dist, mode, frs, views, d, f"pair_{a}_{b}")]
            continue
        action, frames, view = parts[0], parts[1], parts[2] if len(parts) > 2 else "q3"
        cl = clips[action]; rig = rigs[cl.ch]
        show_only(rigs, [cl.ch], {cl.ch: cl})
        set_expression(cl.ch, cl.name)
        fr_ = bake_clip(rig, cl)
        mark = stage_of(cl)
        withset = mark[4] and os.environ.get("RS_PROBE_SET", "1") == "1"
        use_set(withset)
        if not withset:
            mark = (mark[0], mark[1], mark[2], 0.0, False)
        dk = float(os.environ.get("RS_PROBE_DIST", str(DIST_K[cl.ch])))
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
    print("RS_PROBE", len(out))


def mode_debug():
    sc, rigs = open_scene()
    exec(os.environ.get("RS_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))


{"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
