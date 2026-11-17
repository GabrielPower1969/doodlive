"""The King Who Serves skeletal animation (Animation role, story pack `lastsupper`).

Two halves in one file, the shape of pipeline/mi_animate.py:

* Under Blender (headless) it opens `assets/lastsupper/model/characters.blend` (Characters role's rigs), builds every
  clip of docs/lastsupper/CONTRACT.md §4 as an action `<char>_<clip>` and exports
  `assets/lastsupper/anim/{jesus,peter,donkey,john,james,andrew,seller1,seller2}.glb` (character + skin + one glTF
  animation per action) and `clips.json`.
* Under plain python3 it orchestrates the Blender runs and composes the contact sheet (Pillow).

    python3 pipeline/ls_animate.py all        # build + verify + contact sheet + freshness check
    python3 pipeline/ls_animate.py build      # actions + GLBs + anim/clips.json (with checks, ride + kneel pair checks)
    python3 pipeline/ls_animate.py verify     # re-import GLBs: actions, frame ranges, sampled pose == build, UV order
    python3 pipeline/ls_animate.py contact    # anim/contact_sheet.png (key poses per clip, on the jerusalem set)
    LS_PROBE="peter_refuse:0,20,44:q3" python3 pipeline/ls_animate.py probe       # work renders ($LS_ANIM_WORK/probe.png)
    LS_PROBE="pair:jesus_ride:donkey_walk:0:6:ride:side,q3" python3 pipeline/ls_animate.py probe
        pair modes: ride (A rides B: same mark and heading, A at base RIDE_Y), bench (B seated on the bench facing +X,
        A `dist` in front facing B, both at UPPER), front (B faces +Z, A `dist` in front facing it, both at UPPER)
    LS_ONLY=donkey_,jesus_ride  (with build: bake + check a subset, no export)

Jesus and Peter are the Real Miracles characters, and so are their shared clips. This script does NOT copy the
Miracles clips: it runs pipeline/mi_animate.py in this module's namespace (definitions only, the way
ls_characters.py runs mi_characters.py), keeps the Miracles clip functions and helpers, drops the Miracles clip
list, and registers the reused clips (jesus idle / talk / walk / laugh / wave, peter idle / talk / walk / laugh /
wave, the Miracles friends' idle / walk / wave for the five extras, who share the friend body) under this pack's
characters. A change to those clips in mi_animate.py reaches this pack on the next build. Nothing in `mi_*` is edited.
The donkey's quadruped layer (hoof IK, four-beat gait) follows pipeline/da_animate.py (the lions); the two small
functions it needs (`quad_gait`, `ik_quad`) are adapted here because da_animate.py is not on the kit.

How the motion is made: see mi_animate.py. Each clip is a function frame -> channels (rotations in design axes,
offsets, scales); IK for hands / feet / hooves; `settle` puts a seated body on its seat; spring chains for mantle,
belt, sash, cloak, apron, pouch, head cloths, donkey ears and tail. Props are bones (towel, basin, bread, cup, palm,
jug); the timeline shows / hides them. Intermediates: $LS_ANIM_WORK (default /tmp/lastsupper_anim).
"""
import json, math, os, random, subprocess, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MI_PATH = os.path.join(HERE, "mi_animate.py")


def _ls_constants():
    """This pack's paths and stage numbers. Re-applied after the Miracles module has run in this namespace."""
    LS = os.path.join(ROOT, "assets/lastsupper")
    model = os.path.join(LS, "model")
    return dict(
        LSDIR=LS, MODEL=model, ANIM=os.path.join(LS, "anim"), BLEND=os.path.join(model, "characters.blend"),
        SET_GLB=os.path.join(model, "jerusalem.glb"), TIMELINE=os.path.join(LS, "timeline.json"),
        REGIONS_JSON=os.path.join(model, "regions_characters.json"),
        EXTRAS_PAINT=os.path.join(model, "extras_paint.png"),
        FACE_DIR=os.path.join(ROOT, "docs/lastsupper/design/faces"),
        WORK=os.environ.get("LS_ANIM_WORK") or "/tmp/lastsupper_anim",
        ENV="LS_", BLENDER=os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender"), FPS=30,
        DISCIPLES=("john", "james", "andrew"), SELLERS=("seller1", "seller2"),
        EXTRAS=("john", "james", "andrew", "seller1", "seller2"),
        CHARS=("jesus", "peter", "donkey", "john", "james", "andrew", "seller1", "seller2"),
        FRIENDS=(),                 # Miracles name; nobody here uses the Miracles friend face / paint paths
        # stage numbers the clips are fitted to (art-width units; docs/lastsupper/ANIMATION.md "staging")
        UPPER=0.10,                 # room floor (clips are built in the actor's own space: they work at any base y)
        RIDE_Y=0.12,                # Jesus's base y while riding
        SEAT_Y=0.1552,              # donkey seat (blanket top over the root) at rest, RIG.md §1
        RIDE_N=27,                  # one donkey walk cycle = one ride rock (0.9 s, CONTRACT §4)
        KNEEL_D=0.11,               # kneel_wash / kneel_talk / kneel_laugh / kneel_serve: the seated person 0.11 ahead
        BASIN_D=0.06,               # the basin bone rests 0.06 in front of Jesus's root (RIG.md §2), kept there kneeling
        BENCH_SEAT=0.040,           # bench cushion top above the floor (CONTRACT §6)
        CUSHION=0.0115,             # supper cushions (SET.md: h 0.0115)
        TABLE_TOP=0.05,             # low table top above the floor
        STONES_D=0.08,              # listen_stone: stones 0.08 in front, tops at 0.03
        TABLE_D=0.06,               # tip_table / open_cage: the table's near edge 0.05-0.06 in front
        STAND_D=0.083,              # rise_towel: basin stand centre in front of STAND when facing it (SET.md)
    )


globals().update(_ls_constants())

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
    print("\n".join(tail[-400:]))
    if p.returncode != 0 or "Traceback" in p.stdout or "Traceback" in p.stderr:
        print(p.stderr[-4000:])
        sys.exit(f"blender {mode} failed")


def fresh_check():
    """The Characters role may re-run ls_characters.py: the anim GLBs must be newer than the model files (A7)."""
    src = [BLEND] + [os.path.join(MODEL, f"{c}.glb") for c in CHARS]
    newest = max(os.path.getmtime(p) for p in src if os.path.exists(p))
    outs = [os.path.join(ANIM, f"{c}.glb") for c in CHARS]
    stale = [o for o in outs if (not os.path.exists(o)) or os.path.getmtime(o) < newest]
    print("LS_FRESH", "STALE " + ", ".join(os.path.basename(o) for o in stale) if stale else
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
    cols = min(len(ims), int(os.environ.get("LS_PROBE_COLS", "4")))
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * w, rows * h), (255, 255, 255))
    for i, im in enumerate(ims):
        sheet.paste(im, ((i % cols) * w, (i // cols) * h))
    out = os.path.join(WORK, os.environ.get("LS_PROBE_OUT", "probe.png"))
    sheet.save(out); print("LS_PROBE_SHEET", out)


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
    d.text((pad, 14), "The King Who Serves - key poses per clip (30 fps; frame / seconds; marker names in red; pair rows "
                      "= two actors at their story distance)", fill=(40, 30, 20), font=font)
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
    print("LS_CONTACT", out, sheet.size)


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


def _load_miracles():
    """Run pipeline/mi_animate.py in this namespace, without its final mode dispatch (asserted, so a change to that
    block fails loudly instead of running the Miracles build)."""
    src = open(MI_PATH, encoding="utf-8").read()
    cut = "\nif IN_BLENDER:\n    os.makedirs(WORK, exist_ok=True)\n"
    assert src.count(cut) == 1, "mi_animate.py: the final dispatch block changed; update ls_animate._load_miracles"
    g = globals()
    keep_file, keep_doc = g.get("__file__"), g.get("__doc__")
    g["__file__"] = MI_PATH
    try:
        exec(compile(src[:src.index(cut)], MI_PATH + " (definitions, run by ls_animate.py)", "exec"), g)
    finally:
        g["__file__"] = keep_file; g["__doc__"] = keep_doc


_load_miracles()
globals().update(_ls_constants())
os.makedirs(WORK, exist_ok=True)
argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
TL = json.load(open(TIMELINE))

MI_CLIP = {c.action: c for c in CLIPS}      # the Miracles clips (functions kept, list dropped)
CLIPS.clear()
_PAY.clear(); _BAKED.clear(); _PARTNER.clear()

CLOSED = {ch: 12.78 for ch in CHARS}                     # RIG.md §2: eyelids.sy closed (all eight)
KNEEL = {ch: dict(KY=0.020, kz=0.016, thigh_back=10.0, shin_slope=22.0) for ch in CHARS}
ARM_REST = {"jesus": -18.0, "peter": -12.0, "john": -20.0, "james": -16.0, "andrew": -20.0, "seller1": -6.0,
            "seller2": -18.0, "donkey": 0.0}
FV = {"john": dict(ph=0.00, amp=1.15), "james": dict(ph=0.31, amp=0.95), "andrew": dict(ph=0.57, amp=0.80),
      "seller1": dict(ph=0.13, amp=1.10), "seller2": dict(ph=0.44, amp=1.00)}
COAT = {"belt1": "thighL", "sash1": "thighL"}
CHAIN_FLOOR = {}
CHAINS = {
    # bones, stiffness k (1/s^2), damping c (1/s), weight toward the rest hang (gravity), max lag (deg)
    "jesus": [(("mantle1",), 70.0, 7.0, 0.30, 12.0), (("belt1",), 90.0, 7.5, 0.30, 24.0)],
    "peter": [(("cloth1",), 90.0, 8.0, 0.30, 22.0)],
    "john": [(("sash1",), 90.0, 7.5, 0.30, 24.0)],
    "james": [(("cloak1",), 70.0, 7.0, 0.30, 16.0)],
    "andrew": [(("cloth1",), 95.0, 8.0, 0.30, 22.0)],
    "seller1": [(("apron1",), 80.0, 7.0, 0.30, 18.0)],
    "seller2": [(("pouch",), 120.0, 6.0, 0.30, 30.0)],
    "donkey": [(("tail1", "tail2"), 75.0, 6.5, 0.0, 35.0), (("earL",), 230.0, 9.0, 0.0, 12.0),
               (("earR",), 230.0, 9.0, 0.0, 12.0)],
}
PROPS = ("towel", "basin", "bread", "cup", "palm", "jug")
HIDE_SET = ("palmsRoad", "table2Tipped", "coinsFloor", "cagesOpen")

# marks (story.py) used for renders and for the staging checks
BENCH_MARK = (-0.54, -0.42)
WASH_MARK = (-0.43, -0.42)
STAND_MARK = (-0.15, -0.46)
SUP = {"james": (-0.34, -0.54), "jesus": (-0.27, -0.54), "john": (-0.20, -0.54), "andrew": (-0.41, -0.46),
       "peter": (-0.41, -0.35)}
ROAD_MARK = (0.26, 0.11)


# =============================================================================================== rig
class LsRig(Rig):
    """mi_animate.Rig + this cast's heights + the donkey's quadruped flag and seat point."""
    H_OF = {"jesus": 0.36, "peter": 0.38, "donkey": 0.27, "john": 0.33, "james": 0.36, "andrew": 0.37,
            "seller1": 0.33, "seller2": 0.35}

    def __init__(self, ch, obj):
        super().__init__(ch, obj)
        self.quad = ch == "donkey"
        self.seat = None
        if self.quad:
            body = bpy.data.objects[f"{ch}_body"]
            mw = obj.matrix_world.inverted() @ body.matrix_world
            gname = {g.index: g.name for g in body.vertex_groups}
            want = to_bl(V(0.0, SEAT_Y, 0.005))
            best = None
            for v in body.data.vertices:
                co = mw @ v.co
                dd = (co - want).length
                if best is None or dd < best[0]:
                    best = (dd, co.copy(), v)
            ws = [(gname[g.group], g.weight) for g in best[2].groups if g.weight > 1e-3 and gname.get(g.group) in self.rest]
            tot = sum(w for _, w in ws)
            self.seat = (best[1], [(b, w / tot) for b, w in ws])

    def seat_point(self, M):
        co, ws = self.seat
        p = Vector((0, 0, 0))
        for b, w in ws:
            p += w * ((M[b] @ self.rest_inv[b]) @ co)
        return to_d(p)


def open_scene():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    sc.render.fps = FPS
    rigs = {ch: LsRig(ch, bpy.data.objects[f"{ch}_rig"]) for ch in CHARS}
    RIGS.clear(); RIGS.update(rigs)
    return sc, rigs


# =============================================================================================== registration
def add_clip(ch, name, N, loop, fn, **kw):
    info = kw.pop("info", None)
    cl = Clip(ch, name, N, loop, fn, **kw)
    cl.info = info or {}
    CLIPS.append(cl)
    return cl


def reuse(ch, src, name=None, phase=0.0, **over):
    """Register a Miracles clip under this pack's character (same function, length, markers and speed)."""
    s = MI_CLIP[src]
    fn = s.fn
    if src.startswith("friend1_"):
        fn = globals()["friend_" + s.name]              # the raw shared friend function, not friend1's phase wrapper
    kw = dict(markers=dict(s.markers), notes=s.notes + " [Real Miracles clip " + src + ", reused unchanged]",
              speed=s.speed, props=list(s.props), seated=s.seated)
    kw.update(over)
    if phase and s.loop:
        def wrapped(rig, f, N_, fn=fn, sh=int(round(phase * s.N))):
            return fn(rig, (f + sh) % N_, N_)
        return add_clip(ch, name or s.name, s.N, s.loop, wrapped, **kw)
    return add_clip(ch, name or s.name, s.N, s.loop, fn, **kw)


def lclip(chs, name, N, loop, phase=True, **kw):
    """Register one function for one or several characters; free loops of the extras are phase-shifted per person
    so a group never moves in unison (travel clips are never shifted)."""
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


# =============================================================================================== shared helpers
def shift_arms(c, dy, dz=0.0, sides="LR"):
    """Root-space arm IK targets follow the body when the hips drop (a standing upper body reused seated)."""
    for side in sides:
        for k in ("ik.arm", "ikb.arm"):
            if k + side in c and c.get(("ikspace.arm" if k == "ik.arm" else "ikbspace.arm") + side, "root") == "root":
                c[k + side] = Vector(c[k + side]) + V(0, dy, dz)


def seat_drop(rig):
    """Approximate hips drop when seated on the bench (settle refines it) - for root-space hand targets."""
    return -(rig.head["hips"].y - 0.064 * kH(rig))


def bench_legs(rig, c, w=1.0, feet_z=0.066, spread=0.010, pitch=0.0, lift=0.0, back=None):
    """Seated on the bench (cushion top BENCH_SEAT): the hips settle on the seat, the feet planted on the floor in
    front (feet_z ahead of the root; the bench front edge is ~0.008 ahead of a BENCH mark, SET.md). back = (wL, wR)
    pulls a foot back under the bench front (refuse)."""
    k = kH(rig)
    for side in "LR":
        sx = 1 if side == "L" else -1
        b = rig.head["foot" + side]
        z = feet_z * k
        if back:
            z = lerp(z, -0.004, back[0 if side == "L" else 1])
        tgt = V(b.x + sx * spread, planted_ankle_y(rig, side, pitch) + lift, z)
        cur = c.get(f"ik.leg{side}")
        c[f"ik.leg{side}"] = tgt if (cur is None or w >= 0.999) else vlerp(cur, tgt, w)
        c[f"foot{side}.pitch"] = lerp(c.get(f"foot{side}.pitch", 0.0), pitch, w)
        c[f"pole.leg{side}"] = V(0.20 * sx, 0.6, 1.0)
    c["hips.ty"] = c.get("hips.ty", 0.0) + seat_drop(rig) * w
    c["hips.tz"] = c.get("hips.tz", 0.0) - 0.014 * w
    c["settle"] = ("hips", ("hips", "thighL", "thighR"), BENCH_SEAT, w)
    c["coatfollow"] = max(c.get("coatfollow", 0.0), w)


def cross_legs(rig, c, w=1.0, seat=CUSHION):
    """Sitting cross-legged on a supper cushion: hips on the cushion, knees out, ankles crossed in front (right over
    left)."""
    k = kH(rig)
    for side in "LR":
        sx = 1 if side == "L" else -1
        tgt = V(-0.020 * sx * k, 0.018 + (0.006 if side == "R" else 0.0), (0.050 if side == "L" else 0.058) * k)
        cur = c.get(f"ik.leg{side}")
        c[f"ik.leg{side}"] = tgt if (cur is None or w >= 0.999) else vlerp(cur, tgt, w)
        c[f"foot{side}.pitch"] = lerp(c.get(f"foot{side}.pitch", 0.0), 20.0, w)
        c[f"foot{side}.ry"] = lerp(c.get(f"foot{side}.ry", 0.0), -62.0 * sx, w)
        c[f"pole.leg{side}"] = V(1.0 * sx, 0.7, 0.5)
    c["hips.ty"] = c.get("hips.ty", 0.0) - (rig.head["hips"].y - 0.030 * k) * w
    c["hips.tz"] = c.get("hips.tz", 0.0) - 0.010 * w
    c["settle"] = ("hips", ("hips", "thighL", "thighR"), seat, w)
    c["coatfollow"] = max(c.get("coatfollow", 0.0), w)
    c["nofootfix"] = False


def cross_drop(rig):
    return -(rig.head["hips"].y - 0.034 * kH(rig))


def kneel_both(rig, c, w=1.0, lean=0.0):
    """On both knees (kit kneel_legs, Miracles' KNEEL numbers), upright, leaning forward by `lean` (0..1)."""
    kneel_legs(rig, c, w, w)
    c["hips.rx"] = c.get("hips.rx", 0.0) + (4 + 18 * lean) * w
    c["spine.rx"] = c.get("spine.rx", 0.0) + (4 + 14 * lean) * w
    c["chest.rx"] = c.get("chest.rx", 0.0) + (2 + 8 * lean) * w
    c["coatfollow"] = max(c.get("coatfollow", 0.0), 0.6 * w)


def kneel_drop(rig):
    hip, _, _ = kneel_geom(rig, "L", **KNEEL[rig.ch])
    return hip.y - rig.head["thighL"].y


def seated_base(rig, f, N, legs="bench", cycles=2, amp=0.6, **kw):
    c = h_base(rig, f, N, cycles=cycles, amp=amp)
    (bench_legs if legs == "bench" else cross_legs)(rig, c, **kw)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 3; c["chest.rx"] += 2
    return c


def hands_on_knees(c, rig, w=1.0, dz=0.0, legs="bench"):
    k = kH(rig)
    for side, sx in (("L", 1), ("R", -1)):
        if legs == "bench":
            tgt = V(0.034 * sx * k, 0.084 * k, (0.062 + dz) * k)
        else:
            tgt = V(0.052 * sx * k, 0.030 * k, (0.040 + dz) * k)
        arm_ik(c, side, tgt, V(0.8 * sx, -0.2, -0.5), "root", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 26, w); fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 36, w))


def look_down_at(c, w, amt=1.0):
    c["neck.rx"] = c.get("neck.rx", 0.0) + 12 * amt * w
    c["head.rx"] = c.get("head.rx", 0.0) + 16 * amt * w


# =============================================================================================== JESUS (reused)
for _nm in ("idle", "talk", "walk", "laugh", "wave"):
    reuse("jesus", "jesus_" + _nm)
PALM_UP = V(0.10, 1.0, 0.10)        # Peter holds the frond upright (aimed after the arm is solved; RIG.md: palm on handR)


def with_palm(fn):
    def wrapped(rig, f, N):
        c = fn(rig, f, N)
        c["palm.aim"] = PALM_UP
        return c
    return wrapped


for _nm in ("idle", "talk", "walk", "laugh", "wave"):
    _cl = reuse("peter", "peter_" + _nm, props=["palm"] if _nm in ("idle", "walk", "talk", "laugh") else [])
    if _nm in ("idle", "walk", "talk", "laugh"):
        _cl.fn = with_palm(_cl.fn)
for _ch in EXTRAS:
    for _nm in ("idle", "walk", "wave") if _ch in DISCIPLES else ("walk",):
        reuse(_ch, "friend1_" + _nm, phase=FV[_ch]["ph"] if _nm != "walk" else 0.0)


# =============================================================================================== JESUS: ride
_SEAT = {}


def donkey_seat(action, f):
    """Seat point (root space of the donkey) and the spine's roll / pitch (deg) in a donkey clip at frame f."""
    key = (action, int(f))
    if key not in _SEAT:
        cl = next(c for c in CLIPS if c.action == action)
        rig = RIGS["donkey"]
        _, _, M = evaluate_primary(rig, cl, int(f) % cl.N if cl.loop else min(cl.N, int(f)))
        p = rig.seat_point(M)
        R = M["spine"].to_3x3().normalized() @ rig.rest3["spine"].inverted()      # spine turn from its rest frame
        side = to_d(R @ (C @ V(1, 0, 0)))
        fwd = to_d(R @ (C @ V(0, 0, 1)))
        roll = math.degrees(math.atan2(side.y, side.x))
        pitch = math.degrees(math.atan2(-fwd.y, fwd.z))
        _SEAT[key] = (p, roll, pitch)
    return _SEAT[key]


RIDE_HIPS = V(0.0, 0.0450, -0.012)   # hips joint over the seat (rig-local, base RIDE_Y): the robe seat touches the blanket


def ride_base(rig, f, N, rock=1.0):
    """Astride the donkey (RIG.md pose_ride): hips over the seat, thighs forward and spread round the barrel, shins
    hanging, hands on the knees; the hips follow the donkey `walk` seat frame by frame (same 27-frame cycle)."""
    c = h_base(rig, f, N, cycles=N // RIDE_N, amp=0.5)
    p, roll, pitch = donkey_seat("donkey_walk", f % RIDE_N)
    base = RIDE_HIPS + V(0, (p.y - SEAT_Y) * rock + (SEAT_Y - 0.1552), (p.z - 0.005) * rock)
    c["hips.tx"] = p.x * rock
    c["hips.ty"] = base.y - rig.head["hips"].y
    c["hips.tz"] = base.z
    c["hips.rz"] = -1.0 * roll * rock
    c["hips.rx"] = pitch * 0.6 * rock
    c["spine.rz"] = 0.5 * roll * rock; c["chest.rz"] = 0.4 * roll * rock     # the upper body stays upright (lags)
    for side, sx in (("L", 1), ("R", -1)):
        for k_ in ("ik.leg", "ikw.leg"):
            c.pop(k_ + side, None)
        c[f"thigh{side}.rz"] = 40.0 * sx
        c[f"thigh{side}.rx"] = -52.0
        c[f"shin{side}.rx"] = 96.0 + 3.0 * math.sin(2 * math.pi * f / RIDE_N + (0 if side == "L" else math.pi)) * rock
        c[f"foot{side}.rx"] = 10.0
    hands_ride(c, rig)
    c["mantle1.rx"] = -40.0               # the back drape lies out over the donkey's back, not through it
    c["coatfollow"] = 0.7
    return c


def hands_ride(c, rig, w=1.0, sides="LR"):
    for side, sx in (("L", 1), ("R", -1)):
        if side not in sides:
            continue
        arm_ik(c, side, V(0.058 * sx, 0.044, 0.050), V(0.8 * sx, -0.3, -0.4), "root", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 18, w); fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 34, w))


for _a in ("jesus_ride", "jesus_ride_wave", "jesus_ride_talk"):
    CHAIN_FLOOR[_a] = 0.050
for _a in ("jesus_sit_supper", "jesus_bless_bread", "jesus_lift_cup", "jesus_smile"):
    CHAIN_FLOOR[_a] = 0.034
NO_GRAVITY = {"jesus_ride", "jesus_ride_wave", "jesus_ride_talk"}
_mi_bake_clip = bake_clip


def bake_clip(rig, clip_):
    """mi bake_clip; the ride clips bake their chains without the pull toward the standing hang (as seated clips)."""
    if clip_.action in NO_GRAVITY and clip_.action not in _BAKED:
        keep = clip_.seated
        clip_.seated = True
        try:
            return _mi_bake_clip(rig, clip_)
        finally:
            clip_.seated = keep
    return _mi_bake_clip(rig, clip_)


RIDE_INFO = {"rideWith": "donkey_walk (same mark, same heading, base y RIDE_Y = 0.12), cycle 27 frames",
             "rideCycleFrames": 27}


@lclip("jesus", "ride", RIDE_N, True, info=RIDE_INFO,
       notes="seated astride the donkey at base y RIDE_Y (0.12): the hips over the blanket, thighs spread round the "
             "barrel, shins hanging down both sides, hands on the knees; the hips follow the donkey `walk` seat frame "
             "by frame (27-frame cycle = one rock, 0.9 s), the upper body lags a little, calm look round")
def jesus_ride(rig, f, N):
    c = ride_base(rig, f, N)
    c["head.ry"] = 6 * wave(f, N, 1, 0.2); c["neck.ry"] = 3 * wave(f, N, 1, 0.1)
    c["head.rx"] = -2 + 1.0 * math.cos(4 * math.pi * f / N - 1.0)
    blink_ch(c, rig, f, N, [11])
    return c


@lclip("jesus", "ride_wave", 3 * RIDE_N, True, info=RIDE_INFO,
       notes="as `ride` (same seat follow), the right hand waving to the crowd beside His head, the head turning "
             "slowly left and right with a smile, the left hand on the knee; 81 frames = 3 donkey steps cycles")
def jesus_ride_wave(rig, f, N):
    c = ride_base(rig, f, N)
    hand_wave(c, rig, "R", f, N, 6, high=0.6)
    shift_arms(c, RIDE_HIPS.y - rig.head["hips"].y + 0.020, 0.0, sides="R")
    turn = [(0, -18), (14, -20), (36, 20), (54, 22), (72, -14), (81, -18)]
    c["head.ry"] = 0.6 * KL(turn, f, N, True, lag=3); c["neck.ry"] = 0.3 * K(turn, f, N, True)
    c["chest.ry"] = 0.15 * K(turn, f, N, True)
    c["head.rz"] = -4
    blink_ch(c, rig, f, N, [30, 66])
    return c


@lclip("jesus", "ride_talk", 3 * RIDE_N, True, info=RIDE_INFO,
       notes="as `ride`, turned a little to His left (chest and head), the right hand open palm up toward the people, "
             "speaking (jaw in a syllable rhythm), small nods")
def jesus_ride_talk(rig, f, N):
    c = ride_base(rig, f, N)
    beats = talk_jaw(c, f, N, 41)
    bt = beat_curve(beats, f, N, width=9)
    c["chest.ry"] = 12; c["spine.ry"] = 6; c["neck.ry"] = 6; c["head.ry"] = 10
    c["head.rx"] = -2 + 3 * bt
    lift = 0.8 + 0.2 * beat_curve(beats, f - 3, N, width=10)
    arm_ik(c, "R", V(-0.040, 0.120, 0.090), V(-0.8, -0.4, -0.4), "root", 1.0)
    c["forearmR.twist"] = -60 * lift; c["handR.bend"] = -14 * lift; fingers(c, "R", 8)
    blink_ch(c, rig, f, N, [20, 60])
    return c


# =============================================================================================== JESUS: temple
@lclip("jesus", "sad_look", 66, False, markers={"look": 30},
       notes="stops, looks slowly over the court (head right ... left), the shoulders drop a little and the head "
             "lowers; hands loosely together; holds, sad face")
def jesus_sad_look(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    look = K([(0, 0), (8, 0), (26, -24), (40, -24), (56, 16), (66, 10)], f)
    c["head.ry"] = 0.6 * look; c["neck.ry"] = 0.3 * look; c["chest.ry"] = 0.12 * look
    sag = ease_io((f - 24) / 30)
    c["shoulderL.raise"] -= 4 * sag; c["shoulderR.raise"] -= 4 * sag
    c["chest.rx"] += 4 * sag; c["neck.rx"] = 4 * sag; c["head.rx"] = -2 + 8 * sag
    hands_clasped(c, rig, V(0.0, 0.150, 0.044) * kH(rig), w=ease_io((f - 4) / 20) * 0.9)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [16, 50], loop=False, slow=1.6)
    return c


@lclip("jesus", "tip_table", 48, False, markers={"tip": 27},
       notes="steps in (right foot), bends and takes the table's near edge (hands y ~0.07, 0.05 in front), lifts it "
             "up and away so it tips away from Him (`tip` at 0.9 s: the timeline swaps table2 -> table2Tipped), "
             "straightens up firm, hands lowering; ends upright")
def jesus_tip_table(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    k = kH(rig)
    dn = ease_io((f - 2) / 12) * (1 - ease_io((f - 20) / 10))
    up = ease_io((f - 18) / 9) * (1 - ease_io((f - 32) / 14))
    st = ease_io((f - 30) / 16)
    c["hips.ty"] = -0.034 * dn - 0.010 * up
    c["hips.tz"] = -0.012 * dn
    c["hips.rx"] = 22 * dn + 8 * up; c["spine.rx"] = 16 * dn + 6 * up; c["chest.rx"] += 10 * dn - 4 * up
    c["neck.rx"] = -10 * dn; c["head.rx"] = -6 * dn + 2 * st
    grip = ease_io((f - 4) / 10) * (1 - st)
    for side, sx in (("L", 1), ("R", -1)):
        lo = V(0.040 * sx, 0.072, 0.064)
        hi = V(0.046 * sx, 0.170 * k, 0.100)
        arm_ik(c, side, vlerp(lo, hi, up), V(0.9 * sx, -0.4, -0.3), "root", grip)
        c[f"hand{side}.bend"] = lerp(6, -30, grip); fingers(c, side, lerp(22, 60, grip))
        c[f"forearm{side}.twist"] = -30 * sx * grip
    c["jaw.rx"] = 5 * bump(f, 20, 32)
    stand_feet(rig, c, spread=0.008, fwdR=0.022 * ease_io((f - 1) / 8), liftR=0.014 * bump(f, 1, 9),
               fwdL=-0.006 * dn)
    c["floorclamp"] = True
    blink_ch(c, rig, f, N, [40], loop=False)
    return c


@lclip("jesus", "firm_talk", 96, True,
       notes="standing tall, the right arm pointing up and out ('My Father's house'), the left hand open at His side; "
             "firm, clear nods on the stressed words, not angry; jaw in a syllable rhythm")
def jesus_firm_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    k = kH(rig)
    beats = talk_jaw(c, f, N, 57, amp=(6, 14))
    bt = beat_curve(beats, f, N, width=8)
    pt = K([(0, 0.9), (30, 1.0), (50, 0.6), (70, 1.0), (96, 0.9)], f, N, True)
    arm_ik(c, "R", V(-0.110 * k, 0.330 * k + 0.012 * bt, 0.080 * k), V(-0.6, -0.8, -0.2), "root", pt)
    c["handR.bend"] = -8; fingers(c, "R", 10); c["forearmR.twist"] = -40
    palm_up(c, "L", 0.55 + 0.2 * beat_curve(beats, f - 3, N, width=10))
    c["chest.rx"] += -3; c["head.rx"] = -4 + 4 * bt; c["chest.ry"] = -6 * pt
    c["head.ry"] = 6 * wave(f, N, 1, 0.2)
    stand_feet(rig, c, spread=0.008, fwdR=0.006)
    blink_ch(c, rig, f, N, [14, 70])
    return c


@lclip("jesus", "open_cage", 66, False, markers={"open": 48},
       notes="reaches to the cages on the table (0.05-0.06 in front, hands at y ~0.10), works the little doors open "
             "with both hands, then at `open` (1.6 s) sweeps both hands up high, palms up, as the doves go, looking up "
             "after them; holds")
def jesus_open_cage(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    k = kH(rig)
    reach = ease_io((f - 2) / 12)
    work = math.sin(2 * math.pi * f / 8) * bump(f, 14, 44)
    lift = ease_io((f - 44) / 10)
    c["hips.rx"] = 10 * reach * (1 - lift)
    c["spine.rx"] = 14 * reach * (1 - lift); c["chest.rx"] += 8 * reach * (1 - lift) - 6 * lift
    c["hips.tz"] = -0.010 * reach * (1 - lift)
    c["neck.rx"] = 8 * reach * (1 - lift) - 14 * lift; c["head.rx"] = 6 * reach * (1 - lift) - 14 * lift
    for side, sx in (("L", 1), ("R", -1)):
        lo = V(0.030 * sx + 0.004 * work * sx, 0.112 + 0.008 * work * (1 if side == "L" else -1), 0.112)
        hi = V(0.090 * sx, 0.330 * k, 0.060)
        arm_ik(c, side, vlerp(lo, hi, lift), V(0.9 * sx, -0.5, -0.2), "root", reach)
        c[f"forearm{side}.twist"] = lerp(-20 * sx, -80 * sx, lift)
        c[f"hand{side}.bend"] = lerp(-10, -24, lift); fingers(c, side, lerp(40 + 20 * work, 4, lift))
    c["jaw.rx"] = 4 * lift
    stand_feet(rig, c, spread=0.006, fwdR=0.008)
    blink_ch(c, rig, f, N, [30], loop=False)
    return c


# =============================================================================================== JESUS: the towel and the basin
TOWEL_ON = 24
BASIN_ON = 48


@lclip("jesus", "rise_towel", 90, False, props=["towel", "basin"],
       markers={"towel": TOWEL_ON, "basin": BASIN_ON, "pourStart": 54, "pourEnd": 90},
       info={"propsShown": {"towel": TOWEL_ON, "basin": BASIN_ON}},
       notes="standing at the basin stand, facing it (stand 0.083 in front): ties the towel round His waist (hands at "
             "the belt, a tug; prop `towel` shown at 0.8 s), reaches to the stand and takes the basin in both hands "
             "(prop `basin` shown at 1.6 s, the set's basinJug hidden), lifts it to His waist and holds it level "
             "while the water is poured into it (1.8-3.0 s, the water_pour fx), looking into it; ends holding it")
def jesus_rise_towel(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    tie = ease_io((f - 2) / 8) * (1 - ease_io((f - 26) / 8))
    tug = math.sin(2 * math.pi * (f - 10) / 7) * bump(f, 10, 26)
    reach = ease_io((f - 32) / 14)
    lift = ease_io((f - 50) / 12)
    stand = V(0.0, 0.092, STAND_D - 0.004)                 # basin on the stand top (UPPER + 0.08), its rim reached
    held = V(0.0, 0.150 * k, 0.058)
    bpos = vlerp(stand, held, lift)
    for side, sx in (("L", 1), ("R", -1)):
        belt = V(0.030 * sx + 0.004 * tug * sx, 0.188 * k, 0.040)
        rim = bpos + V(0.040 * sx, 0.010, 0.0)
        arm_ik(c, side, belt, V(0.8 * sx, -0.5, -0.3), "root", tie)
        arm_ik2(c, side, rim, V(0.9 * sx, -0.4, -0.3), "root", reach)
        c[f"hand{side}.bend"] = lerp(6, 10, tie) - 20 * reach
        c[f"forearm{side}.twist"] = 30 * sx * reach
        fingers(c, side, 40 * tie + lerp(22, 30, reach) * (1 - tie))
    bend_ = reach * (1 - lift)
    c["spine.rx"] = 6 * tie + 18 * bend_ + 6 * lift; c["chest.rx"] += 4 * tie + 10 * bend_
    c["hips.tz"] = -0.010 * bend_; c["hips.ty"] = -0.006 * bend_
    c["neck.rx"] = 8 * tie + 6 * bend_ + 10 * lift; c["head.rx"] = 6 * tie + 6 * bend_ + 10 * lift
    # the basin bone (child of root, rest on the floor 0.06 in front) rides on the stand, then in the hands
    rest = rig.head["basin"]
    off = bpos - V(0.0, 0.010, 0.0) - rest
    c["basin.tx"], c["basin.ty"], c["basin.tz"] = off.x, off.y, off.z
    stand_feet(rig, c, spread=0.005)
    blink_ch(c, rig, f, N, [20, 70], loop=False)
    return c


def jesus_kneel_pose(rig, f, N, lean=0.35, w=1.0):
    """On both knees KNEEL_D behind the seated person's root, the basin on the floor BASIN_D in front (its rest place),
    leaning toward the feet. The forward foot of Miracles' kneel_kind would land in the basin (RIG.md §3): both knees."""
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    kneel_both(rig, c, w, lean)
    return c


def kneel_wash_hands(c, rig, f, N, w=1.0):
    """Right hand scoops in the basin and pours over the feet, left hand wipes with the towel end; one loop = two
    scoops and one wipe."""
    sc_ = K([(0, 0.0), (10, 1.0), (16, 1.0), (26, 0.0), (36, 0.0), (46, 1.0), (52, 1.0), (62, 0.0), (72, 0.0)], f, N, True)
    pour = K([(0, 0.6), (8, 0.0), (18, 0.0), (26, 1.0), (32, 1.0), (40, 0.4), (44, 0.0), (54, 0.0), (62, 1.0),
              (68, 1.0), (72, 0.6)], f, N, True)
    wipe = math.sin(2 * math.pi * f / 12)
    bas = V(0.0, 0.0, BASIN_D)
    dip = bas + V(-0.016, 0.022, -0.004)
    over = bas + V(-0.006, 0.064, 0.002)
    arm_ik(c, "R", vlerp(vlerp(over, dip, sc_), over + V(0, 0.010, 0), pour * (1 - sc_)), V(-0.8, -0.2, -0.5), "root", w)
    c["handR.bend"] = lerp(c.get("handR.bend", 6), 10 + 30 * pour, w); fingers(c, "R", lerp(22, 30 + 30 * sc_, w))
    c["forearmR.twist"] = lerp(c.get("forearmR.twist", 10), -20 + 50 * pour, w)
    arm_ik(c, "L", bas + V(0.020 + 0.006 * wipe, 0.034, -0.008 + 0.004 * wipe), V(0.8, -0.2, -0.5), "root", w)
    c["handL.bend"] = lerp(c.get("handL.bend", 6), 30, w); fingers(c, "L", lerp(22, 60, w))
    return sc_, pour


@lclip("jesus", "kneel_wash", 72, True, seated=True, props=["towel", "basin"], markers={"scoop1": 13, "scoop2": 49},
       notes=f"kneeling on both knees {KNEEL_D} in front of a seated person (bench or cushion), the basin on the floor "
             f"{BASIN_D} in front: the right hand scoops water and pours it over the feet (twice per loop), the left "
             "hand wipes with the towel end, head bowed over the feet, gentle; knees on the floor")
def jesus_kneel_wash(rig, f, N):
    c = jesus_kneel_pose(rig, f, N, lean=0.35)
    sc_, pour = kneel_wash_hands(c, rig, f, N)
    c["neck.rx"] = 14 + 4 * sc_; c["head.rx"] = 14 + 4 * sc_
    c["head.ry"] = -4 * pour
    blink_ch(c, rig, f, N, [30], slow=1.4)
    c["floorclamp"] = True
    return c


@lclip("jesus", "kneel_talk", 96, True, seated=True, props=["towel", "basin"],
       notes="the same kneel, upright, looking up at the seated person's face, speaking gently (jaw), the right hand "
             "open toward him, palm up, the left hand resting on the basin rim")
def jesus_kneel_talk(rig, f, N):
    c = jesus_kneel_pose(rig, f, N, lean=0.05)
    beats = talk_jaw(c, f, N, 63, amp=(4, 11))
    bt = beat_curve(beats, f, N, width=9)
    c["neck.rx"] = -10; c["head.rx"] = -10 + 3 * bt; c["head.rz"] = 5 + 2 * wave(f, N, 1)
    o = 0.85 + 0.15 * beat_curve(beats, f - 3, N, width=10)
    arm_ik(c, "R", V(-0.030, 0.150, 0.080), V(-0.8, -0.4, -0.4), "root", 1.0)
    c["forearmR.twist"] = -70 * o; c["handR.bend"] = -16 * o; fingers(c, "R", 8)
    arm_ik(c, "L", V(0.030, 0.040, BASIN_D - 0.022), V(0.8, -0.2, -0.5), "root", 1.0)
    c["handL.bend"] = 26; fingers(c, "L", 30)
    blink_ch(c, rig, f, N, [22, 74])
    c["floorclamp"] = True
    return c


@lclip("jesus", "kneel_laugh", 54, False, seated=True, props=["towel", "basin"], markers={"laugh": 10},
       notes="the same kneel, a warm real laugh (head back, shoulders shaking in four shrinking bursts, the left hand "
             "to His chest), ending in the kneel_talk pose (holds; stand_talk rises from here)")
def jesus_kneel_laugh(rig, f, N):
    a = jesus_kneel_talk(rig, 0, 96)
    c = dict(a)
    lg = pulses(f, N, [(10, 1.0), (16, 0.9), (22, 0.7), (29, 0.5)], decay=2.2, loop=False)
    env = bump(f, 4, 46)
    c["head.rx"] = a["head.rx"] - 8 * env + 3 * lg; c["neck.rx"] = a["neck.rx"] - 3 * env
    c["shoulderL.raise"] += 4 * lg; c["shoulderR.raise"] += 4 * lg; c["chest.rx"] += -3 * env + 2 * lg
    c["jaw.rx"] = 9 * env * (0.5 + 0.5 * lg)
    arm_ik2(c, "L", V(0.016, -0.010, 0.046) * kH(rig), V(0.8, -0.6, -0.2), "chest", env)
    blink_ch(c, rig, f, N, [44], loop=False, base=1.0 + 2.0 * env)
    c["floorclamp"] = True
    return c


@lclip("jesus", "stand_talk", 54, False, props=["towel"], markers={"up": 26},
       notes="from the kneel (kneel_laugh's end pose) He rises (one foot forward, push), turns to the room and raises "
             "the right hand, open, as He speaks; holds standing, the hand up (Miracles' stand_talk, from this kneel)")
def jesus_stand_talk(rig, f, N):
    a = jesus_kneel_laugh(rig, 54, 54)
    k1 = dict(a)                                   # half-kneel: the right foot set forward flat (f2-14)
    bR = rig.head["footR"]
    k1["ik.legR"] = V(bR.x - 0.004, planted_ankle_y(rig, "R", 0), bR.z + 0.070)
    k1["footR.pitch"] = 0.0; k1["pole.legR"] = V(-0.2, 0.3, 1)
    k1["hips.tz"] = a.get("hips.tz", 0.0) + 0.006
    b = h_base(rig, f, N, cycles=1, amp=0.5)
    stand_feet(rig, b, spread=0.004, fwdR=0.010)
    up = ease_io((f - 26) / 18)
    b["upperArmR.raise"] = lerp(-18, 46, up); b["upperArmR.bend"] = lerp(8, 30, up)
    b["forearmR.bend"] = lerp(26, 70, up); b["forearmR.twist"] = lerp(10, -60, up)
    b["handR.bend"] = lerp(6, -12, up); fingers(b, "R", lerp(22, 6, up))
    b["chest.ry"] = 10 * up; b["neck.ry"] = 6 * up; b["head.ry"] = 8 * up; b["head.rx"] = -3 * up
    w1 = ease_io((f - 2) / 12)
    w2 = ease_io((f - 14) / 16)
    c = mix(mix(a, k1, w1), b, w2)
    c["ik.legR"] = Vector(c["ik.legR"]) + V(0, 0.016 * bump(f, 2, 14) + 0.010 * bump(f, 24, 34), 0)
    c["hips.tz"] = c.get("hips.tz", 0.0) + 0.014 * bump(f, 10, 30)
    c["spine.rx"] = c.get("spine.rx", 0.0) + 14 * bump(f, 10, 30)
    if f > 26:
        c["jaw.rx"] = 7 * bump(f, 34, 42) + 5 * bump(f, 44, 52)
    blink_ch(c, rig, f, N, [30], loop=False)
    c["floorclamp"] = True
    return c


# =============================================================================================== JESUS: supper
def table_hands(c, rig, w=1.0):
    """Seated cross-legged at the low table (its near edge ~0.04 ahead, top 0.05): forearms resting on the edge."""
    k = kH(rig)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.030 * sx * k, 0.058, 0.056), V(0.8 * sx, -0.3, -0.4), "root", w)
        c[f"hand{side}.bend"] = lerp(c.get(f"hand{side}.bend", 6), 4, w); fingers(c, side, lerp(c.get(f"fingers{side}.curl", 22), 30, w))
        c[f"forearm{side}.twist"] = lerp(c.get(f"forearm{side}.twist", 0), -10 * sx, w)


def supper_base(rig, f, N, cycles=2):
    c = seated_base(rig, f, N, legs="cross", cycles=cycles, amp=0.7)
    table_hands(c, rig)
    return c


@lclip(("jesus",), "sit_supper", 120, True, seated=True,
       notes="sitting cross-legged on a cushion at the low table (its top 0.05, near edge ~0.04 ahead), forearms on "
             "the table edge, slow breathing, looks round at His friends with a smile; hips on the cushion")
def jesus_sit_supper(rig, f, N):
    c = supper_base(rig, f, N)
    look_keys(c, [(0, 0), (20, 0), (36, -24), (60, -24), (76, 24), (100, 24), (112, 0), (120, 0)], f, N)
    c["head.rz"] = 3 * wave(f, N, 1, 0.3)
    blink_ch(c, rig, f, N, [14, 64, 71])
    return c


BREAD_ON = 6
BREAD_BREAK = 66


@lclip("jesus", "bless_bread", 96, False, seated=True, props=["bread"], markers={"bread": BREAD_ON, "break": BREAD_BREAK},
       info={"propsShown": {"bread": BREAD_ON}},
       notes="seated: the left hand takes the loaf from the table (prop `bread` shown at 0.2 s, set breadLoaf hidden), "
             "both hands lift it a little, He looks up and gives thanks, breaks it in two at `break` (2.2 s: the right "
             "hand pulls away from the left), then offers the halves out to both sides; holds")
def jesus_bless_bread(rig, f, N):
    c = supper_base(rig, f, N, cycles=1)
    k = kH(rig)
    loaf = V(0.000, 0.064, 0.080)                       # the loaf on the table (S10: (-0.27, -0.46) from (-0.27, -0.54))
    take = ease_io(f / 6)
    lift = ease_io((f - 12) / 14)
    brk = ease_io((f - 62) / 6)
    out = ease_io((f - 74) / 14)
    held = V(0.010, 0.140 * k, 0.070)
    pL = vlerp(vlerp(loaf, held, lift), V(0.070, 0.130 * k, 0.090), out)
    pR = vlerp(held + V(-0.020, 0.0, 0.0), held + V(-0.050, 0.004, 0.0), brk)
    pR = vlerp(pR, V(-0.070, 0.130 * k, 0.090), out)
    tabL, tabR = V(0.030 * k, 0.058, 0.056), V(-0.030 * k, 0.058, 0.056)
    arm_ik(c, "L", vlerp(tabL, pL, take), V(0.8, -0.4, -0.3), "root", 1.0)
    arm_ik(c, "R", vlerp(tabR, pR, lift), V(-0.8, -0.4, -0.3), "root", 1.0)
    c["forearmL.twist"] = lerp(-10, 60, lift); c["handL.bend"] = lerp(4, -20, lift); fingers(c, "L", lerp(30, 40, take))
    c["forearmR.twist"] = lerp(10, -60, lift); c["handR.bend"] = -20 * lift; fingers(c, "R", lerp(30, 40, lift))
    up = ease_io((f - 26) / 10) * (1 - ease_io((f - 56) / 10))
    c["neck.rx"] = -10 * up; c["head.rx"] = -14 * up
    c["head.ry"] = 0.6 * K([(0, 0), (74, 0), (82, -18), (90, 18), (96, 18)], f)
    c["spine.rx"] += 6 * take * (1 - lift)
    c["jaw.rx"] = 4 * bump(f, 32, 44) + 4 * bump(f, 46, 56)
    c["eyelids.sy"] = 1.0 + 4.0 * up
    return c


CUP_ON = 12


@lclip("jesus", "lift_cup", 66, False, seated=True, props=["cup"], markers={"cup": CUP_ON, "high": 40},
       info={"propsShown": {"cup": CUP_ON}},
       notes="seated: the right hand takes the cup from the table (prop `cup` shown at 0.4 s, set cupTable hidden), "
             "the left hand joins it, both lift it to chest height and hold it out a little; gentle; holds")
def jesus_lift_cup(rig, f, N):
    c = supper_base(rig, f, N, cycles=1)
    k = kH(rig)
    cup = V(0.026, 0.060, 0.086)                        # the cup on the table (S11: (-0.24, -0.45) from (-0.27, -0.54))
    take = ease_io((f - 2) / 10)
    lift = ease_io((f - 18) / 22)
    held = V(-0.004, 0.150 * k, 0.090)
    pR = vlerp(cup + V(-0.010, 0.0, -0.004), held, lift)
    tabL, tabR = V(0.030 * k, 0.058, 0.056), V(-0.030 * k, 0.058, 0.056)
    arm_ik(c, "R", vlerp(tabR, pR, take), V(-0.8, -0.4, -0.3), "root", 1.0)
    arm_ik(c, "L", vlerp(tabL, held + V(0.022, -0.006, -0.004), ease_io((f - 24) / 12)), V(0.8, -0.4, -0.3), "root", 1.0)
    c["handR.bend"] = lerp(4, 10, take); fingers(c, "R", lerp(30, 70, take)); c["forearmR.twist"] = lerp(-10, 20, lift)
    c["handL.bend"] = 10 * lift; fingers(c, "L", lerp(30, 20, lift))
    c["spine.rx"] += 4 * take * (1 - lift)
    c["head.rx"] = 4 * lift; c["neck.rx"] = 3 * lift
    blink_ch(c, rig, f, N, [54], loop=False, slow=1.5)
    return c


@lclip("jesus", "smile", 90, True, seated=True,
       notes="seated cross-legged at the table, a warm smile at Peter, a small slow nod and a head tilt")
def jesus_smile(rig, f, N):
    c = supper_base(rig, f, N)
    c["head.rx"] = -2 + 5 * bump(f, 24, 46) + 4 * bump(f, 60, 80)
    c["head.rz"] = 6 + 2 * wave(f, N, 1)
    blink_ch(c, rig, f, N, [12, 54], slow=1.3)
    return c


# =============================================================================================== PETER (and the disciples)
def cheer_fn(rig, f, N):
    """Arms up shouting: the right hand high waving (Peter's palm frond, or an empty hand), the left fist pumping, a
    bounce per beat."""
    a = famp(rig) if rig.ch in FV else 1.2
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    ph = 2 * math.pi * f / N
    arm_ik(c, "R", V((-0.060 - 0.040 * math.sin(ph)) * k, 0.400 * k, 0.020), V(-0.6, -0.8, 0.2), "root", 1.0)
    c["handR.bend"] = 10 * math.sin(ph - 0.6); c["forearmR.twist"] = 30; fingers(c, "R", 70 if rig.ch == "peter" else 8)
    pump = 0.5 + 0.5 * math.cos(2 * ph)
    arm_ik(c, "L", V(0.080 * k, (0.250 + 0.090 * pump) * k, 0.040), V(0.8, -0.6, 0.0), "root", 1.0)
    fingers(c, "L", 80)
    bounce = abs(math.sin(ph))
    c["hips.ty"] = -0.010 * (1 - bounce) * a
    c["chest.rx"] += -4; c["head.rx"] = -10 + 3 * bounce
    c["chest.rz"] = 3 * math.sin(ph); c["head.rz"] = -3 * math.sin(ph)
    c["jaw.rx"] = 9 + 5 * (1 - bounce)
    if rig.ch == "peter":
        c["palm.aim"] = V(-0.6 * math.sin(ph - 0.6), 1.0, 0.15)      # the frond swings over his head
    stand_feet(rig, c, spread=0.008)
    c["eyelids.sy"] = 1.0
    return c


lclip("peter", "cheer", 40, True, props=["palm"], markers={"bounce": 10},
      notes="stands bouncing, waving the palm frond high over his head with the right hand (frond swings across), "
            "the left fist pumping, shouting (jaw wide); the feet stay planted")(cheer_fn)
lclip(DISCIPLES, "cheer", 40, True, markers={"bounce": 10},
      notes="as Peter's cheer with an empty waving hand: right hand high waving, left fist pumping, bouncing, shouting"
      )(cheer_fn)


@lclip("peter", "listen_stone", 96, False, props=["palm"], markers={"ear": 30, "tap": 66},
       notes="bends at the waist toward the stone heap 0.08 in front (tops y 0.03), knees bent, the left hand cupped "
             "to his ear, head turned to listen; then the left hand taps a stone twice (`tap`), puzzled face; the "
             "right hand with the palm frond rests on his knee; holds bent")
def peter_listen_stone(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    dn = ease_io((f - 2) / 22)
    c["hips.ty"] = -0.050 * dn; c["hips.tz"] = -0.040 * dn
    c["hips.rx"] = 40 * dn; c["spine.rx"] = 22 * dn; c["chest.rx"] += 10 * dn
    c["neck.rx"] = -16 * dn; c["head.rx"] = -10 * dn
    ear = ease_io((f - 14) / 10) * (1 - ease_io((f - 54) / 8))
    tap = ease_io((f - 56) / 8)
    knock = bump(f, 62, 68) + bump(f, 70, 76)
    c["head.rz"] = -16 * ear + 6 * tap; c["head.ry"] = 18 * ear
    arm_ik(c, "L", V(0.040, 0.020, 0.008), V(0.9, -0.2, -0.4), "head", ease_io((f - 14) / 10))
    arm_ik2(c, "L", V(0.022, 0.030 + 0.012 * (1 - knock), STONES_D - 0.002), V(0.8, 0.0, -0.6), "root",
            tap / max(1e-4, ear + tap) if (ear + tap) > 1e-3 else 0.0)
    c["handL.bend"] = 20 * ear - 20 * tap; fingers(c, "L", 20 * ear + 60 * tap)
    arm_ik(c, "R", V(-0.040, 0.095, 0.070), V(-0.8, -0.2, -0.5), "root", dn)
    c["handR.bend"] = 10; fingers(c, "R", 70)
    c["palm.aim"] = V(0.25, 1.0, 0.35)
    c["jaw.rx"] = 3 * ear + 4 * bump(f, 78, 92)
    stand_feet(rig, c, spread=0.016, fwdL=0.010)
    c["floorclamp"] = True
    blink_ch(c, rig, f, N, [40, 84], loop=False)
    return c


def boast_fn(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.8)
    a = famp(rig) if rig.ch in FV else 1.2
    pr = 0.85 + 0.15 * wave(f, N, 2)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.026 * sx, -0.012 + 0.006 * pr, 0.052 * (1.15 if rig.ch == "peter" else 1.0)),
               V(0.9 * sx, -0.4, -0.2), "chest", 1.0)
        c[f"hand{side}.bend"] = 20; fingers(c, side, 85)
    c["chest.rx"] += -6 * pr; c["spine.rx"] = -3 * pr; c["neck.rx"] = -4; c["head.rx"] = -10 * pr
    rock = wave(f, N, 1)
    c["hips.tz"] = -0.004 * rock * a; c["chest.ry"] = 4 * wave(f, N, 1, 0.25) * a; c["head.ry"] = -6 * wave(f, N, 1, 0.3)
    c["jaw.rx"] = 3 + 3 * bump(f, 10, 22) + 3 * bump(f, 40, 52)
    stand_feet(rig, c, spread=0.012, pitchL=6 * max(0.0, rock), pitchR=6 * max(0.0, rock))
    blink_ch(c, rig, f, N, [30], base=1.4)
    return c


lclip("peter", "boast", 72, True,
      notes="chest out, both thumbs at his chest, chin up (proud), rocking on his heels, a puffed little nod")(boast_fn)
lclip(DISCIPLES, "boast", 72, True,
      notes="as Peter's boast: chest out, thumbs at the chest, chin up, rocking on the heels")(boast_fn)


def argue_fn(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    k = kH(rig)
    beats = talk_jaw(c, f, N, 91 + len(rig.ch), amp=(7, 15))
    turn = K([(0, 0), (12, 0), (20, -30), (32, -30), (40, 0), (60, 0)], f, N, True)
    c["hips.ry"] = 0.3 * turn; c["chest.ry"] = 0.5 * turn; c["head.ry"] = 0.4 * KL([(0, 0), (12, 0), (20, -30),
                                                                                       (32, -30), (40, 0), (60, 0)], f, N, True, lag=3)
    for side, sx, off in (("L", 1, 0.0), ("R", -1, 0.5)):
        ph = 2 * math.pi * (f / N * 3 + off)
        arm_ik(c, side, V((0.070 + 0.020 * math.sin(ph)) * sx * k, (0.240 + 0.040 * math.cos(ph)) * k, 0.070 * k),
               V(0.8 * sx, -0.6, -0.2), "root", 1.0)
        c[f"forearm{side}.twist"] = -60 * sx; c[f"hand{side}.bend"] = -20 + 20 * math.sin(ph - 0.7); fingers(c, side, 6)
    c["head.rx"] = -2 + 3 * beat_curve(beats, f, N, width=8); c["head.rz"] = 5 * wave(f, N, 2)
    stand_feet(rig, c, spread=0.012, liftR=0.008 * bump(f, 16, 24), fwdR=0.0)
    blink_ch(c, rig, f, N, [8, 44])
    return c


lclip("peter", "argue", 60, True,
      notes="flustered: both hands waving in front of him (alternating, palms out), turning away and back, talking "
            "fast (jaw)")(argue_fn)
lclip(DISCIPLES, "argue", 60, True, notes="as Peter's argue: hands waving, turning away and back, talking fast")(argue_fn)
for _ch in DISCIPLES:
    reuse(_ch, "peter_laugh", phase=FV[_ch]["ph"], props=[],
          notes="a big belly laugh, the right hand slapping his thigh twice per loop [Real Miracles clip peter_laugh, "
                "reused unchanged on the friend body]")


def d_talk(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.8)
    a = famp(rig)
    beats = talk_jaw(c, f, N, 17 + len(rig.ch) * 3, amp=(5, 12))
    bt = beat_curve(beats, f, N, width=9)
    pr = K([(0, 0.2), (14, 0.8 * a), (40, 0.8 * a), (56, 0.3), (80, 0.6 * a), (96, 0.2)], f, N, True)
    palm_up(c, "R", pr)
    nk = K([(0, 0), (50, 0), (58, 1), (84, 1), (92, 0), (96, 0)], f, N, True) * (1.0 if rig.ch == "andrew" else 0.0)
    arm_ik(c, "L", V(0.010, -0.010, -0.020), V(0.9, 0.3, -0.4), "neck", nk)  # Andrew rubs his neck, shy
    c["head.rx"] = -2 + 3 * bt; c["head.rz"] = 4 * wave(f, N, 1, 0.3) + 4 * nk; c["head.ry"] = 4 * wave(f, N, 1, 0.1)
    stand_feet(rig, c, spread=0.004)
    blink_ch(c, rig, f, N, [10, 64])
    return c


lclip(DISCIPLES, "talk", 96, True,
      notes="talking: the right hand opens palm-up on the phrases, small nods; Andrew (mild, shy) rubs the back of "
            "his neck in the middle of the loop")(d_talk)


# --- seated on the bench (Peter + disciples)
@lclip(("peter",) + DISCIPLES, "sit_bench", 120, True, seated=True,
       notes=f"sitting on the bench (cushion top {BENCH_SEAT} above the floor), hands on the knees, feet on the floor "
             "~0.066 ahead, breathing, looking round, blinks; hips on the seat")
def sit_bench_fn(rig, f, N):
    c = seated_base(rig, f, N, "bench", cycles=3, amp=0.8)
    hands_on_knees(c, rig)
    look_keys(c, [(0, 0), (24, 0), (40, 20), (70, 20), (86, -14), (104, -14), (114, 0), (120, 0)], f, N)
    blink_ch(c, rig, f, N, [16, 70, 77])
    return c


def amazed_fn(rig, f, N):
    """Miracles' peter_amazed upper body on the bench (A4: from the sit_bench pose, no standing up)."""
    c = MI_CLIP["peter_amazed"].fn(rig, f, N)
    for k_ in [k_ for k_ in c if k_.startswith(("ik.leg", "ikw.leg", "pole.leg", "footL.", "footR."))]:
        c.pop(k_)
    c["hips.ty"] = 0.0; c["spine.rx"] = 10 * (1 - ease_io(f / 24)); c["chest.rx"] = c.get("chest.rx", 0.0) * 0.5
    bench_legs(rig, c)
    shift_arms(c, seat_drop(rig) * 0.92, -0.010)
    tg = {sd: (Vector(c["ik.arm" + sd]), c.get("ikw.arm" + sd, 1.0), c.get("pole.arm" + sd)) for sd in "LR"}
    hands_on_knees(c, rig)
    for sd, (t, w_, pole) in tg.items():
        arm_ik2(c, sd, t + V(0, 0.050 * kH(rig), 0.020), pole, "root", w_)
    c["chest.rx"] += -3 * ease_io((f - 10) / 16)
    return c


@lclip(("peter",) + DISCIPLES, "amazed", 66, False, seated=True, markers={"look": 30},
       notes="seated on the bench (from sit_bench, A4): straightens up, mouth falls open, both hands half raised and "
             "open, looks slowly round (left ... right), a little disbelieving head shake; holds [Miracles "
             "peter_amazed upper body, legs seated]")
def amazed_seated(rig, f, N):
    return amazed_fn(rig, f, N)


@lclip("peter", "refuse", 44, False, seated=True, markers={"jerk": 6},
       notes="seated: jerks both feet back under the bench front, both hands up palms out, leaning back away from "
             "Jesus, shocked (`shock`); holds")
def peter_refuse(rig, f, N):
    j = ease_io(f / 6)
    c = seated_base(rig, f, N, "bench", cycles=1, amp=0.4, back=(j, j), lift=0.012 * bump(f, 0, 10))
    k = kH(rig)
    dy = seat_drop(rig)
    lean = ease_io(f / 7)
    c["spine.rx"] -= 12 * lean; c["chest.rx"] += -8 * lean; c["hips.tz"] -= 0.004 * lean
    c["neck.rx"] = 8 * lean; c["head.rx"] = 6 * lean
    for side, sx in (("L", 1), ("R", -1)):
        lo = V(0.034 * sx * k, 0.084 * k, 0.062 * k)
        hi = V(0.084 * sx * k, 0.300 * k + dy, 0.050 * k)
        arm_ik(c, side, vlerp(lo, hi, ease_io((f - 1) / 6)), V(0.8 * sx, -0.6, -0.2), "root", 1.0)
        c[f"forearm{side}.twist"] = -60 * sx * lean; c[f"hand{side}.bend"] = -34 * lean; fingers(c, side, 4)
    sh = math.sin(2 * math.pi * f / 5) * bump(f, 8, 30)
    c["head.ry"] = 10 * sh; c["handL.twist"] = 10 * sh; c["handR.twist"] = -10 * sh
    c["shoulderL.raise"] += 6 * lean; c["shoulderR.raise"] += 6 * lean
    c["jaw.rx"] = 12 * ease_io((f - 4) / 6)
    c["eyelids.sy"] = 1.0
    return c


@lclip("peter", "offer_all", 54, False, seated=True, markers={"thrust": 10, "duck": 30},
       notes="seated: thrusts both hands straight out to Jesus, palms up (`thrust`), then ducks his whole head forward "
             "and down as if under a tap (`duck`), eyes squeezed, grinning; comic; holds ducked")
def peter_offer_all(rig, f, N):
    c = seated_base(rig, f, N, "bench", cycles=1, amp=0.4, feet_z=0.072)
    k = kH(rig)
    dy = seat_drop(rig)
    th = ease_io((f - 2) / 8)
    dk = ease_io((f - 24) / 8)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, vlerp(V(0.034 * sx * k, 0.084 * k, 0.062 * k),
                              V(0.040 * sx * k, 0.200 * k + dy + 0.010 * dk, (0.150 - 0.020 * dk) * k), th),
               V(0.8 * sx, -0.6, -0.3), "root", 1.0)
        c[f"forearm{side}.twist"] = -80 * sx * th; c[f"hand{side}.bend"] = -20 * th; fingers(c, side, lerp(22, 4, th))
    c["spine.rx"] += 10 * th + 22 * dk; c["chest.rx"] += 8 * dk; c["hips.tz"] += 0.010 * dk
    c["neck.rx"] = 26 * dk; c["head.rx"] = -6 * th + 26 * dk
    c["shoulderL.raise"] += 8 * dk; c["shoulderR.raise"] += 8 * dk
    c["jaw.rx"] = 8 * th + 4 * dk
    c["eyelids.sy"] = 1.0 + 9.0 * dk
    return c


@lclip("peter", "sit_wash", 120, True, seated=True,
       notes="seated on the bench, feet forward (in the basin ~0.06 ahead), looking down at his feet being washed, a "
             "happy sigh now and then (shoulders lift and drop, eyes close), hands on the knees")
def peter_sit_wash(rig, f, N):
    c = seated_base(rig, f, N, "bench", cycles=2, amp=0.6, feet_z=0.060)
    hands_on_knees(c, rig, dz=-0.006)
    look_down_at(c, 1.0, 0.9)
    s = K([(0, 0), (40, 0), (54, 1), (66, 1), (84, 0), (120, 0)], f, N, True)
    c["shoulderL.raise"] += 5 * s; c["shoulderR.raise"] += 5 * s; c["chest.rx"] += -3 * s; c["head.rx"] += -6 * s
    c["eyelids.sy"] = 1.0 + 11.0 * s * bump(f, 50, 70)
    c["head.rz"] = 4 * wave(f, N, 1, 0.2)
    return c


def ashamed_fn(rig, f, N):
    c = seated_base(rig, f, N, "bench", cycles=1, amp=0.4)
    hands_on_knees(c, rig, w=1.0)
    d = ease_io((f - 2) / 18)
    rub = math.sin(2 * math.pi * f / 10) * bump(f, 16, 66)
    arm_ik2(c, "R", V(-0.034, -0.004 + 0.006 * rub, -0.016 + 0.004 * rub), V(-1.0, -0.2, 0.3), "head",
            ease_io((f - 6) / 14))
    c["handR.bend"] = 20; fingers(c, "R", 30)
    c["neck.rx"] = 14 * d; c["head.rx"] = 14 * d; c["head.rz"] = 8 * d; c["head.ry"] = -6 * d
    c["chest.rx"] += 4 * d; c["shoulderL.raise"] += 3 * d
    c["eyelids.sy"] = 1.0 + 3.0 * d
    return c


lclip(("peter",) + DISCIPLES, "ashamed", 66, False, seated=True, markers={"down": 20},
      notes="seated on the bench: eyes down, head lowered and tilted, the right hand rubs the back of his neck "
            "(sheepish), the left hand on his knee; holds")(ashamed_fn)


@lclip(("peter",) + DISCIPLES, "sit_supper", 120, True, seated=True,
       notes="cross-legged on a cushion at the low table, hands resting near the table edge, looking toward Jesus "
             "and round, breathing; hips on the cushion")
def sit_supper_fn(rig, f, N):
    c = seated_base(rig, f, N, "cross", cycles=3, amp=0.7)
    table_hands(c, rig)
    look_keys(c, [(0, 0), (30, 0), (46, 14), (74, 14), (90, -10), (110, -10), (120, 0)], f, N)
    blink_ch(c, rig, f, N, [18, 72, 79])
    return c


SERVE_ON = 24


@lclip("peter", "serve_rise", 48, False, seated=True, props=["towel", "jug"], markers={"pick": SERVE_ON, "down": 44},
       info={"propsShown": {"towel": SERVE_ON, "jug": SERVE_ON}},
       notes="from sit_supper: uncrosses his legs and comes up onto his knees, reaching down to his right side for the "
             "towel and the jug (both props shown at 0.8 s: the towel on his shoulder, the jug in the right hand), "
             "ends kneeling upright with the jug: the kneel_serve start pose")
def peter_serve_rise(rig, f, N):
    a = sit_supper_fn(rig, 0, 120)
    b = peter_kneel_serve(rig, 0, 72)
    w = ease_io((f - 2) / 30)
    c = mix(a, b, w)
    for side in "LR":                                   # the knees come up off the cushion (lifted, not dragged)
        c[f"ik.leg{side}"] = Vector(c[f"ik.leg{side}"]) + V(0, 0.014 * bump(f, 4, 30), 0)
    pick = bump(f, 12, 34)
    arm_ik2(c, "R", V(-0.080, 0.064, 0.010), V(-0.8, 0.0, -0.4), "root", pick)
    c["spine.rz"] = c.get("spine.rz", 0.0) - 10 * pick; c["chest.ry"] = c.get("chest.ry", 0.0) - 14 * pick
    c["head.ry"] = c.get("head.ry", 0.0) - 20 * pick
    c["floorclamp"] = True
    return c


@lclip("peter", "kneel_serve", 72, True, seated=True, props=["towel", "jug"], markers={"pour": 14, "rub": 46},
       notes=f"kneeling on both knees {KNEEL_D} in front of a seated person: tips the jug (right hand) over the feet "
             "(`pour`, with a clumsy slosh), then rubs them with the towel end in the left hand, careful and a bit "
             "awkward, tongue-out concentration (jaw), head bowed")
def peter_kneel_serve(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.5)
    kneel_both(rig, c, 1.0, 0.5)
    pour = K([(0, 0.0), (8, 1.0), (24, 1.0), (32, 0.0), (72, 0.0)], f, N, True)
    rub = K([(0, 0.0), (34, 0.0), (40, 1.0), (62, 1.0), (68, 0.0), (72, 0.0)], f, N, True)
    sl = math.sin(2 * math.pi * f / 9) * bump(f, 8, 26)
    feet = V(0.0, 0.040, 0.050)
    arm_ik(c, "R", feet + V(-0.030, 0.060 - 0.010 * pour, -0.010 + 0.012 * pour), V(-0.8, -0.3, -0.4), "root", 1.0)
    c["handR.bend"] = 10 + 40 * pour + 6 * sl; c["forearmR.twist"] = 10 - 50 * pour; fingers(c, "R", 80)
    sc_ = math.sin(2 * math.pi * f / 8)
    arm_ik(c, "L", feet + V(0.016 + 0.010 * sc_ * rub, -0.004, -0.004 + 0.006 * sc_ * rub), V(0.8, -0.2, -0.5),
           "root", 1.0)
    c["handL.bend"] = 30; fingers(c, "L", 60)
    c["neck.rx"] = 12; c["head.rx"] = 12 + 4 * rub; c["head.rz"] = 6 * wave(f, N, 1)
    c["chest.ry"] = -6 * pour + 4 * rub
    c["jaw.rx"] = 3 + 2 * rub
    blink_ch(c, rig, f, N, [30])
    c["floorclamp"] = True
    return c


# --- the disciples' own seated clips
@lclip(DISCIPLES, "sit_wash", 120, True, seated=True,
       notes="sitting on the floor / cushion with the legs out in front, knees a little up, feet forward ~0.07 "
             "(Andrew in S12, turned to the viewer while Peter washes them), leaning back on his hands, giggling "
             "(shoulders shake now and then), looking down at his feet")
def d_sit_wash(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.6)
    seat_legs(rig, c, "out", kneeL=0.75, kneeR=0.75)
    c["settle"] = ("hips", ("hips", "thighL", "thighR"), CUSHION, 1.0)
    hands_back(c, rig, lean=0.6)
    gig = pulses(f, N, [(30, 1.0), (36, 0.8), (42, 0.6), (90, 1.0), (96, 0.7)], decay=2.0)
    c["shoulderL.raise"] += 4 * gig; c["shoulderR.raise"] += 4 * gig; c["chest.rx"] += 2 * gig
    c["jaw.rx"] = 4 + 6 * gig
    look_down_at(c, 1.0, 0.7)
    c["head.rx"] += -6 * gig; c["head.rz"] = 5 * wave(f, N, 1, 0.2)
    c["eyelids.sy"] = 1.0 + 4.0 * gig
    c["floorclamp"] = True
    return c


NUDGE_SIDE = {"james": "L", "john": "R", "andrew": "R"}   # S12 side by side facing the viewer: James's left is John


def d_nudge(rig, f, N):
    c = seated_base(rig, f, N, "cross", cycles=1, amp=0.6)
    table_hands(c, rig, w=0.6)
    side = NUDGE_SIDE[rig.ch]
    sx = 1 if side == "L" else -1
    jab = pulses(f, N, [(12, 1.0), (40, 1.0)], decay=1.6)
    lean = 0.7 + 0.3 * jab
    arm_ik(c, side, V(0.010 * sx, -0.022 + 0.006 * jab, 0.040), V(1.0 * sx, -0.1, -0.7), "chest", 1.0)  # elbow out
    c[f"hand{side}.bend"] = 10; fingers(c, side, 80)
    c["spine.rz"] = (6 * lean + 6 * jab) * -sx; c["chest.rz"] = (4 * lean + 6 * jab) * -sx
    c["chest.ry"] = -14 * jab * sx; c["spine.rx"] += 4 * lean
    c["head.rz"] = 8 * lean * sx; c["head.ry"] = 10 * sx
    gig = pulses(f, N, [(16, 0.8), (22, 0.6), (44, 0.8), (50, 0.6)], decay=2.0)
    c["shoulderL.raise"] += 3 * gig; c["shoulderR.raise"] += 3 * gig; c["jaw.rx"] = 4 + 5 * gig
    c["eyelids.sy"] = 1.0 + 3.0 * gig
    return c


lclip(DISCIPLES, "nudge", 60, True, seated=True, markers={"jab1": 12, "jab2": 40},
      notes="seated cross-legged (supper), leaning toward the neighbour beside him and jabbing him with the elbow on "
            "that side twice per loop (James his left, John and Andrew their right: S12 sitting side by side facing "
            "the viewer), grinning, giggling shoulders")(d_nudge)


# =============================================================================================== SELLERS
@lclip(SELLERS, "idle", 90, True,
       notes="behind the table: rubbing the hands together (greedy little wrings), counting on the fingers, weight "
             "shifting, looking round for customers")
def s_idle(rig, f, N):
    c = h_base(rig, f, N, cycles=2, amp=0.9)
    k = kH(rig)
    fz = 0.020 if rig.ch == "seller1" else 0.0
    wr = math.sin(2 * math.pi * f / 15)
    cnt = K([(0, 0), (44, 0), (52, 1), (78, 1), (86, 0), (90, 0)], f, N, True)
    hands_clasped(c, rig, V(0.0, 0.160 * k, 0.046 + fz), wring=wr * (1 - cnt))
    arm_ik2(c, "R", V(-0.020, 0.170 * k, 0.060 + fz), V(-0.8, -0.5, -0.3), "root", cnt)
    fingers(c, "R", 30 + 30 * math.sin(2 * math.pi * f / 9) * cnt)
    look_keys(c, [(0, 0), (16, 0), (26, 18), (40, 18), (52, -10), (74, -10), (84, 0), (90, 0)], f, N)
    sh = wave(f, N, 1)
    c["hips.tx"] = 0.004 * sh; c["hips.rz"] = -2 * sh
    stand_feet(rig, c, spread=0.008)
    blink_ch(c, rig, f, N, [12, 60])
    return c


@lclip(SELLERS, "shout", 48, True, markers={"cry": 8},
       notes="hawking: the left hand cupped at his mouth, the right hand held up high (seller1 shows a dove, seller2 a "
             "coin: pinched fingers; no prop mesh), shouting (jaw wide on each cry), leaning forward on each cry")
def s_shout(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.8)
    k = kH(rig)
    cry = K([(0, 0.3), (6, 1.0), (18, 1.0), (24, 0.3), (30, 1.0), (40, 1.0), (48, 0.3)], f, N, True)
    arm_ik(c, "L", V(0.022, -0.030, 0.034), V(0.9, -0.3, 0.0), "head", 1.0)
    c["handL.bend"] = 30; fingers(c, "L", 40)
    arm_ik(c, "R", V(-0.070 * k, (0.300 + 0.020 * cry) * k, 0.050 * k), V(-0.8, -0.7, 0.0), "root", 1.0)
    c["handR.bend"] = -10; fingers(c, "R", 50); c["forearmR.twist"] = -40
    c["chest.rx"] += 4 * cry; c["spine.rx"] = 3 * cry; c["head.rx"] = -6 * cry
    c["jaw.rx"] = 4 + 11 * cry
    stand_feet(rig, c, spread=0.010)
    c["eyelids.sy"] = 1.0
    return c


@lclip(SELLERS, "shock", 40, False, markers={"jump": 4, "land": 16},
       notes="jumps back (a hop, landing a step behind), both hands up, eyes huge, mouth open; holds")
def s_shock(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    k = kH(rig)
    stand_feet(rig, c, spread=0.010)
    bk = ease_io((f - 4) / 12)
    for side in "LR":
        c[f"ik.leg{side}"] = Vector(c[f"ik.leg{side}"]) + V(0, 0, -0.030 * bk)
    c["hips.tz"] = -0.030 * bk
    jump(c, rig, f, 5, 15, 0.024, crouch=0.010)
    up = ease_io((f - 2) / 6)
    for side, sx in (("L", 1), ("R", -1)):
        arm_ik(c, side, V(0.090 * sx * k, 0.300 * k, 0.040 - 0.030 * bk), V(0.8 * sx, -0.6, -0.2), "root", up)
        c[f"forearm{side}.twist"] = -60 * sx * up; fingers(c, side, lerp(22, 2, up)); c[f"hand{side}.bend"] = -30 * up
    c["spine.rx"] = -8 * up; c["chest.rx"] += -6 * up; c["head.rx"] = -4 * up
    c["jaw.rx"] = 14 * up
    c["eyelids.sy"] = 1.0
    return c


S_CHASE = (0.032, 0.55)


@lclip(SELLERS, "chase_coins", 24, True, markers={"contactL": 0, "contactR": 12, "snatchR": 6, "snatchL": 18},
       speed=S_CHASE,
       notes="bent double, scuttling forward with quick short steps, both hands snatching at the floor in turn "
             "(fingers clawing), fluster face; travels: natural speed in clips.json")
def s_chase_coins(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.3)
    g = gait(rig, f, N, L=S_CHASE[0], lift=0.010, duty=S_CHASE[1], heel=8, toeoff=18, spread=0.010)
    legs_ik_channels(c, g)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.040 + 0.003 * math.cos(2 * ph); c["hips.tz"] = -0.030
    c["hips.rx"] = 40; c["spine.rx"] = 26; c["chest.rx"] += 12; c["neck.rx"] = -24; c["head.rx"] = -14
    c["hips.rz"] = 4 * math.cos(ph)
    for side, sx, off in (("L", 1, 0.5), ("R", -1, 0.0)):
        p = (f / N + off) % 1.0
        dn = math.sin(math.pi * min(1.0, p / 0.5)) if p < 0.5 else 0.0
        arm_ik(c, side, V(0.040 * sx, 0.030 + 0.050 * (1 - dn), 0.110 - 0.020 * dn), V(0.8 * sx, -0.2, -0.4), "root", 1.0)
        c[f"hand{side}.bend"] = 30 * dn; fingers(c, side, 20 + 60 * dn)
    c["jaw.rx"] = 6 + 4 * math.sin(2 * ph)
    c["eyelids.sy"] = 1.0
    return c


@lclip(SELLERS, "flap", 40, True, markers={"flap": 10},
       notes="flapping both arms like a bird at the sky, bouncing on his toes, looking up after the doves, wailing "
             "(jaw open)")
def s_flap(rig, f, N):
    c = h_base(rig, f, N, cycles=1, amp=0.4)
    ph = 2 * math.pi * f / N * 2
    fl = 0.5 + 0.5 * math.sin(ph)
    for side, sx in (("L", 1), ("R", -1)):
        c[f"upperArm{side}.raise"] = -10 + 95 * fl; c[f"upperArm{side}.bend"] = 6
        c[f"forearm{side}.bend"] = 10 + 20 * (1 - fl); c[f"hand{side}.bend"] = -30 * fl + 10; fingers(c, side, 6)
    c["neck.rx"] = -14; c["head.rx"] = -14 + 3 * fl
    bounce = fl
    c["hips.ty"] = 0.004 * bounce
    stand_feet(rig, c, spread=0.008, pitchL=14 * bounce, pitchR=14 * bounce)
    c["jaw.rx"] = 12 + 3 * math.sin(ph * 0.5)
    c["eyelids.sy"] = 1.0
    return c


# =============================================================================================== DONKEY (quadruped)
LEGS = ("frontL", "frontR", "hindL", "hindR")
END = {"frontL": "pawL", "frontR": "pawR", "hindL": "footL", "hindR": "footR"}
QUAD = {"frontL": ("upperArmL", "forearmL", "pawL"), "frontR": ("upperArmR", "forearmR", "pawR"),
        "hindL": ("thighL", "shinL", "footL"), "hindR": ("thighR", "shinR", "footR")}


def hoof(rig, leg):
    return rig.tail[END[leg]].copy()


def hooves_stand(rig, c, offs=None, pitch=None):
    offs = offs or {}; pitch = pitch or {}
    for leg in LEGS:
        c["ik." + leg] = hoof(rig, leg) + offs.get(leg, V())
        c[leg + ".pitch"] = pitch.get(leg, 0.0)


def ik_quad(rig, basis, M, chs, limb):
    """da_animate.ik_quad: the hoof TIP (tail of paw / foot) goes exactly to chs['ik.<limb>'] (root space), the hoof
    bone turned by <limb>.pitch (about X, + = toe down); upper + lower bone by two-bone IK. Donkey poles: the front
    knee (carpus) points forward, the hind hock backward."""
    up, lo, end = QUAD[limb]
    key = "ik." + limb
    if key not in chs:
        return
    hind = limb.startswith("hind")
    Mroot = M["root"] @ rig.rest["root"].inverted()
    R3 = Mroot.to_3x3().normalized()
    tip = to_d(Mroot @ to_bl(Vector(chs[key])))
    Rend = R3 @ rot_d((0, 1, 0), chs.get(limb + ".ry", 0.0)) @ rot_d((1, 0, 0), chs.get(limb + ".pitch", 0.0)) @ rig.rest3[end]
    wrist = tip - to_d(Rend @ Vector((0, rig.length[end], 0)))
    pole = Vector(chs.get("pole." + limb, V(0, 0.1, -1) if hind else V(0, 0.1, 1)))
    pole = to_d(R3 @ to_bl(pole))
    ik2(rig, basis, M, up, lo, wrist, pole, False)
    rig.set_world_rot(basis, M, end, Rend)


_mi_solve_pose = solve_pose


def solve_pose(rig, chs):
    if "palm.aim" in chs and not getattr(rig, "quad", False):
        out = _mi_solve_pose(rig, chs)
        aim_prop(rig, out[1], out[2], "palm", chs["palm.aim"], hand="handR")
        return out
    if getattr(rig, "quad", False):
        basis = rig.basis_from(chs)
        M = rig.fk(basis)
        for limb in QUAD:
            ik_quad(rig, basis, M, chs, limb)
        return chs, basis, M
    return _mi_solve_pose(rig, chs)


def tail_sway(c, f, N, amp=8.0, cycles=1.0, phase=0.0, lift=0.0):
    for i, b in enumerate(("tail1", "tail2")):
        a = amp * (0.7 + 0.4 * i) * wave(f - 3 * i, N, cycles, phase)
        c[b + ".rz"] = c.get(b + ".rz", 0.0) + a
        c[b + ".rx"] = c.get(b + ".rx", 0.0) - lift
    return c


def ear_flick(c, f, N, side, hits, loop=True, amp=24.0):
    v = pulses(f, N, hits, decay=1.6, loop=loop)
    c[f"ear{side}.rz"] = c.get(f"ear{side}.rz", 0.0) + amp * v * (1 if side == "L" else -1)
    c[f"ear{side}.rx"] = c.get(f"ear{side}.rx", 0.0) - 0.6 * amp * v


def d_base(rig, f, N, cycles=2, amp=1.0):
    c = {}
    b = wave(f, N, cycles)
    c["chest.rx"] = -0.6 * b * amp; c["neck.rx"] = 0.8 * b * amp
    hooves_stand(rig, c)
    return c


@lclip("donkey", "idle", 120, True,
       notes="standing on all fours, ear flicks (left, right, both), tail swish, a slow head bob and look round, "
             "blinks; the seat (blanket top) stays within +-0.002 of 0.155")
def donkey_idle(rig, f, N):
    c = d_base(rig, f, N, cycles=3, amp=1.0)
    look = [(0, 0), (20, 0), (34, 16), (60, 16), (72, -10), (100, -10), (110, 0), (120, 0)]
    c["neck.ry"] = 0.5 * K(look, f, N, True); c["head.ry"] = 0.5 * KL(look, f, N, True, lag=4)
    c["neck.rx"] += 6 * bump(f, 80, 100); c["head.rx"] = -4 * bump(f, 80, 100)
    ear_flick(c, f, N, "L", [(14, 1.0), (70, 0.8)]); ear_flick(c, f, N, "R", [(44, 1.0), (50, 0.6), (70, 0.8)])
    tail_sway(c, f, N, amp=14, cycles=2)
    blink_ch(c, rig, f, N, [24, 88, 95])
    return c


D_WALK = (0.050, 0.62)
D_PHASE = {"hindL": 0.0, "frontL": 0.25, "hindR": 0.5, "frontR": 0.75}


def quad_gait(rig, c, f, N, L, lift, duty, phases, flexF=55.0, flexH=40.0):
    """da_animate.quad_gait: per leg the hoof tip slides back +L/2 -> -L/2 in stance (planted when moved at
    L / (duty N / FPS)), then swings forward lifted, the hoof flexing under."""
    for leg in LEGS:
        p = (f / N + phases[leg]) % 1.0
        t0 = hoof(rig, leg)
        front = leg.startswith("front")
        if p < duty:
            s = p / duty
            z = L / 2 - L * s
            y = t0.y
            pitch = 22 * smooth((s - 0.8) / 0.2)
        else:
            s = (p - duty) / (1 - duty)
            z = -L / 2 + L * smooth(s)
            y = t0.y + lift * math.sin(math.pi * s) ** 0.8
            pitch = lerp(22, 0, smooth(s * 1.15)) + (flexF if front else flexH) * math.sin(math.pi * min(1.0, s * 1.1)) ** 1.2
        c["ik." + leg] = V(t0.x, y, t0.z + z)
        c[leg + ".pitch"] = pitch


@lclip("donkey", "walk", RIDE_N, True, markers={"hindL": 0, "frontL": 7, "hindR": 14, "frontR": 20}, speed=D_WALK,
       notes="short-stepping donkey walk (lateral four-beat: left hind, left fore, right hind, right fore; 0.9 s per "
             "cycle), the head nodding with each step, ears bobbing late, tail swaying; the seat rises and falls by "
             "<= 0.003 (Jesus's ride follows it frame by frame); hooves planted in stance")
def donkey_walk(rig, f, N):
    c = {}
    quad_gait(rig, c, f, N, D_WALK[0], 0.012, D_WALK[1], D_PHASE, flexF=60, flexH=46)
    ph = 2 * math.pi * f / N
    c["hips.ty"] = -0.0010 + 0.0022 * math.cos(2 * ph)
    c["hips.rz"] = 2.0 * math.sin(ph); c["chest.rz"] = -2.4 * math.sin(ph - 1.6)
    c["spine.ry"] = 2.0 * math.sin(ph); c["chest.ry"] = -2.0 * math.sin(ph - 0.6)
    c["neck.rx"] = 5 * math.cos(2 * ph - 0.8); c["head.rx"] = -3 * math.cos(2 * ph - 1.4)
    c["neck.ry"] = 2 * math.sin(ph - 1.2)
    c["earL.rx"] = -4 * math.cos(2 * ph - 2.0); c["earR.rx"] = -4 * math.cos(2 * ph - 2.0)
    tail_sway(c, f, N, amp=10, cycles=1, phase=0.1)
    blink_ch(c, rig, f, N, [16])
    return c


@lclip("donkey", "hee_haw", 60, False, markers={"bray": 9, "shake": 42},
       notes="2.0 s: throws the head up and stretches the neck, ears flat back, jaw wide open at `bray` (0.3 s, the "
             "heehaw face), ribs pumping twice (hee ... haw), then shakes its head and ears (`shake`); ends standing")
def donkey_hee_haw(rig, f, N):
    c = d_base(rig, f, N, cycles=1, amp=0.4)
    up = ease_io((f - 1) / 7) * (1 - ease_io((f - 36) / 10))
    c["neck.rx"] += -30 * up; c["head.rx"] = -26 * up; c["chest.rx"] += -4 * up
    pump = pulses(f, N, [(10, 1.0), (24, 1.0)], decay=2.4, loop=False)
    c["chest.sy"] = 1.0 + 0.05 * pump; c["chest.sx"] = 1.0 + 0.06 * pump; c["spine.sx"] = 1.0 + 0.04 * pump
    c["jaw.rx"] = (24 * ease_io((f - 4) / 5) * (1 - ease_io((f - 32) / 6))) * (0.85 + 0.15 * pump)
    for side in "LR":
        c[f"ear{side}.rx"] = -55 * up
    sh = math.sin(2 * math.pi * (f - 40) / 6) * bump(f, 40, 56)
    c["head.ry"] = 18 * sh; c["neck.ry"] = 6 * sh
    c["earL.rz"] = 20 * sh; c["earR.rz"] = 20 * sh
    tail_sway(c, f, N, amp=20, cycles=3, lift=-20 * up)
    c["eyelids.sy"] = 1.0 + 9.0 * up * bump(f, 6, 34)
    if f > 50:
        blink_ch(c, rig, f, N, [52], loop=False)
    return c


@lclip("donkey", "graze", 90, True, markers={"bite": 20},
       notes="head down to the ground, nibbling (jaw chewing, the chew face), front legs a little apart, an ear "
             "turning now and then, tail swishing slowly")
def donkey_graze(rig, f, N):
    c = d_base(rig, f, N, cycles=2, amp=0.6)
    c["ik.frontL"] = c["ik.frontL"] + V(0.004, 0, 0.004); c["ik.frontR"] = c["ik.frontR"] + V(-0.004, 0, 0.004)
    c["chest.rx"] += 6; c["spine.rx"] = 2
    c["neck.rx"] += 96 + 2 * wave(f, N, 2); c["head.rx"] = -46 + 4 * bump(f, 16, 26)
    c["jaw.rx"] = 3 + 3 * max(0.0, math.sin(2 * math.pi * f / 9))
    c["head.ry"] = 6 * wave(f, N, 1, 0.3)
    ear_flick(c, f, N, "L", [(30, 1.0)], amp=30); ear_flick(c, f, N, "R", [(66, 1.0)], amp=30)
    tail_sway(c, f, N, amp=10, cycles=1)
    blink_ch(c, rig, f, N, [50])
    return c


@lclip("donkey", "sleepy", 120, True,
       notes="dozing standing: head low, eyes half to fully closed (the sleepy face), ears drooping out to the sides "
             "slowly, a slow nod down and a little jerk back up, tail still")
def donkey_sleepy(rig, f, N):
    c = d_base(rig, f, N, cycles=1, amp=1.2)
    nod = K([(0, 0.0), (60, 0.0), (86, 1.0), (92, 1.0), (98, 0.1), (120, 0.0)], f, N, True)
    c["neck.rx"] += 26 + 14 * nod; c["head.rx"] = 10 + 6 * nod
    for side, sx in (("L", 1), ("R", -1)):
        c[f"ear{side}.rz"] = 40 * sx + 8 * sx * nod; c[f"ear{side}.rx"] = 10
    c["eyelids.sy"] = lerp(6.5, 12.78, max(0.0, min(1.0, 0.5 + 0.5 * nod + 0.2 * wave(f, N, 1))))
    tail_sway(c, f, N, amp=3, cycles=1)
    return c


@lclip("donkey", "happy", 36, False, markers={"hop": 12},
       notes="a little hop with the front feet (chest up, both front hooves off the ground), ears up and forward, "
             "head up; lands and ends standing (spare, for the cover)")
def donkey_happy(rig, f, N):
    c = d_base(rig, f, N, cycles=1, amp=0.4)
    hp = math.sin(math.pi * min(1.0, max(0.0, (f - 6) / 12))) if 6 < f < 18 else 0.0
    pre = bump(f, 0, 8)
    c["chest.ty"] = 0.020 * hp - 0.004 * pre; c["spine.rx"] = -8 * hp; c["chest.rx"] += -6 * hp
    for leg in ("frontL", "frontR"):
        c["ik." + leg] = c["ik." + leg] + V(0, 0.026 * hp, 0.004 * hp)
        c[leg + ".pitch"] = 50 * hp
    c["neck.rx"] += -12 * hp + 4 * bump(f, 18, 28); c["head.rx"] = -8 * hp
    for side in "LR":
        c[f"ear{side}.rx"] = 14 * ease_io((f - 2) / 6)
    tail_sway(c, f, N, amp=14, cycles=2, lift=-10 * hp)
    return c


# =============================================================================================== checks
_mi_clip_checks = clip_checks


def quad_checks(rig, cl, frames):
    """Lowest mesh point, planted-hoof drift (in-place) or stance slip (walk), loop seam, max step; plus the seat
    range (CONTRACT: idle within +-0.004, walk within +-0.006 of 0.155)."""
    out = {}
    lows = []
    for fr in range(0, cl.N + 1, 3):
        apply_basis(rig, frames[fr][0]); bpy.context.view_layer.update()
        lows.append(min(p.y for p, _ in mesh_points(rig)))
    out["meshMinY"] = round(min(lows), 4)
    tips = [END[l] for l in LEGS]
    if cl.speed is None:
        drift = 0.0
        for bn in tips:
            ref = None
            for basis, M in frames:
                p = rig.pos(M, bn, "tail")
                if p.y < rig.tail[bn].y + 0.0012:
                    ref = ref or p
                    drift = max(drift, math.hypot(p.x - ref.x, p.z - ref.z))
                else:
                    ref = None
        out["plantedDriftMax"] = round(drift, 4)
    else:
        out["naturalSpeed"] = round(cl.natural_speed, 4)
        v = cl.natural_speed / FPS
        err = 0.0
        for bn in tips:
            thr = rig.tail[bn].y + 0.0012
            for fr in range(cl.N):
                p0, p1 = rig.pos(frames[fr][1], bn, "tail"), rig.pos(frames[fr + 1][1], bn, "tail")
                if p0.y < thr and p1.y < thr:
                    err = max(err, math.hypot(p1.x - p0.x, (p1.z - p0.z) + v) * FPS)
        out["stanceSlipMax"] = round(err, 4)
    seats = [rig.seat_point(M).y for _, M in frames]
    out["seatMin"], out["seatMax"] = round(min(seats), 4), round(max(seats), 4)
    steps = []
    for fr in range(cl.N):
        M0, M1 = frames[fr][1], frames[fr + 1][1]
        steps.append(max((rig.pos(M0, n, "tail") - rig.pos(M1, n, "tail")).length for n in rig.names if n != "eyelids"))
    out["maxStep"] = round(max(steps), 4)
    if cl.loop:
        M0, MN, M1 = frames[0][1], frames[-1][1], frames[1][1]
        out["seamStep"] = round(max((rig.pos(MN, n, "tail") - rig.pos(M1, n, "tail")).length for n in rig.names
                                    if n != "eyelids"), 4)
        out["seamOK"] = out["seamStep"] <= max(steps) + 2e-4
    reset_pose(rig)
    return out


def clip_checks(rig, cl, frames):
    return quad_checks(rig, cl, frames) if rig.quad else _mi_clip_checks(rig, cl, frames)


def world_pts(rig, M, mark, bones=None):
    """Proxy points of a pose in world design space, the actor at mark = (x, z, yaw, y)."""
    x, z, yaw, y = mark
    return [(rot_y(p, yaw) + V(x, y, z), d) for p, (co, ws, d) in zip(rig.skin(M, bones), [q for q in rig.proxy
                                                                                          if bones is None or q[2] in bones])]


def ride_check():
    """The ride pair on one mark: per frame of the 27-frame cycle, the rider's lowest seat point minus the donkey's
    seat (gap > 0 floats, < 0 sinks into the blanket) and rider leg points inside the donkey's barrel. Against
    `walk` in phase, and against `idle` at any phase (ride starts mid-idle in S03)."""
    clips = {c.action: c for c in CLIPS}
    dk, js = RIGS["donkey"], RIGS["jesus"]
    out = {}
    for ra in ("jesus_ride", "jesus_ride_wave", "jesus_ride_talk"):
        fj = bake_clip(js, clips[ra])
        for da in ("donkey_walk", "donkey_idle"):
            fd = bake_clip(dk, clips[da])
            gaps, inside, where = [], 0, {}
            phases = [0] if da == "donkey_walk" else list(range(0, clips[da].N, 15))
            for ph in phases:
                for fr in range(0, clips[ra].N, 1 if da == "donkey_walk" else 3):
                    Mj = fj[fr][1]; Md = fd[(fr + ph) % clips[da].N][1]
                    seat = dk.seat_point(Md)
                    pts = [p + V(0, RIDE_Y, 0) for p in js.skin(Mj, {"hips"})]
                    near = [p for p in pts if abs(p.x - seat.x) < 0.012 and abs(p.z - seat.z) < 0.03
                            and p.y > seat.y - 0.03]
                    if near:
                        gaps.append(min(p.y for p in near) - seat.y)
                    if fr % 3 == 0:
                        body = dk.skin(Md, {"spine", "chest", "hips", "neck"})
                        bins = {}
                        for q in body:
                            key = (round(q.y / 0.01), round(q.z / 0.01))
                            lo_, hi_ = bins.get(key, (9.0, -9.0))
                            bins[key] = (min(lo_, q.x), max(hi_, q.x))
                        for p, (co, ws, dm) in zip(js.skin(Mj), js.proxy):
                            p = p + V(0, RIDE_Y, 0)
                            key = (round(p.y / 0.01), round(p.z / 0.01))
                            if key in bins and bins[key][0] + 0.003 < p.x < bins[key][1] - 0.003:
                                inside += 1
                                where[dm] = where.get(dm, 0) + 1
            out[f"{ra}+{da}"] = {"seatGapMin": round(min(gaps), 4) if gaps else None,
                                 "seatGapMax": round(max(gaps), 4) if gaps else None, "riderPointsInsideDonkey": inside,
                                 "insideByBone": where}
    return out


def pair_min_dist(pa, pb, eps=0.012):
    """Smallest distance between two point clouds (voxel hash, only pairs within eps)."""
    grid = {}
    for q in pb:
        grid.setdefault((int(q.x // eps), int(q.y // eps), int(q.z // eps)), []).append(q)
    best = eps
    close = 0
    for p in pa:
        gx, gy, gz = int(p.x // eps), int(p.y // eps), int(p.z // eps)
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    for q in grid.get((gx + dx, gy + dy, gz + dz), ()):
                        d = (p - q).length
                        if d < best:
                            best = d
                        if d < 0.004:
                            close += 1
    return round(best, 4), close


KNEEL_PAIRS = [  # (A kneeling, B seated, distance, mode, label)
    ("jesus_kneel_wash", "andrew_amazed", KNEEL_D, "bench", "kneel_wash + andrew amazed (bench)"),
    ("jesus_kneel_wash", "peter_sit_wash", KNEEL_D, "bench", "kneel_wash + peter sit_wash (bench)"),
    ("jesus_kneel_talk", "peter_refuse", KNEEL_D, "bench", "kneel_talk + peter refuse (bench)"),
    ("jesus_kneel_talk", "peter_offer_all", KNEEL_D, "bench", "kneel_talk + peter offer_all (bench)"),
    ("peter_kneel_serve", "andrew_sit_wash", KNEEL_D, "front", "kneel_serve + andrew sit_wash (floor)"),
]


def pair_marks(mode, dist):
    """(markA, markB) for the pair modes: bench = B on the james bench seat facing +X, A dist further +X facing -X;
    front = B at Andrew's supper seat facing +Z, A dist in front facing -Z; ride = both on the road mark."""
    if mode == "bench":
        bx, bz = BENCH_MARK
        return (bx + dist, bz, -90.0, UPPER), (bx, bz, 90.0, UPPER)
    if mode == "front":
        bx, bz = SUP["andrew"]
        return (bx, bz + dist, 180.0, UPPER), (bx, bz, 0.0, UPPER)
    if mode == "ride":
        x, z = ROAD_MARK
        return (x, z, -90.0, RIDE_Y), (x, z, -90.0, 0.0)
    raise ValueError(mode)


def kneel_check():
    clips = {c.action: c for c in CLIPS}
    out = {}
    for a, b, dist, mode, label in KNEEL_PAIRS:
        ca, cb = clips[a], clips[b]
        ra, rb = RIGS[ca.ch], RIGS[cb.ch]
        fa, fb = bake_clip(ra, ca), bake_clip(rb, cb)
        ma, mb = pair_marks(mode, dist)
        worst = (1.0, 0)
        for fr in range(0, max(ca.N, cb.N) + 1, 6):
            Ma = fa[fr % ca.N if ca.loop else min(fr, ca.N)][1]
            Mb = fb[fr % cb.N if cb.loop else min(fr, cb.N)][1]
            pa = [p for p, _ in world_pts(ra, Ma, ma)]
            pb = [p for p, _ in world_pts(rb, Mb, mb)]
            d = pair_min_dist(pa, pb)
            if d[0] < worst[0] or (d[0] == worst[0] and d[1] > worst[1]):
                worst = (d[0], d[1], fr)
        out[label] = {"minDist": worst[0], "pointsCloserThan4mm": worst[1], "atFrame": worst[2] if len(worst) > 2 else 0}
    return out


# =============================================================================================== build
def contract_clips():
    dis = ["idle", "walk", "talk", "cheer", "boast", "argue", "laugh", "sit_bench", "sit_wash", "sit_supper", "amazed",
           "ashamed", "nudge", "wave"]
    sel = ["idle", "shout", "walk", "shock", "chase_coins", "flap"]
    out = {"jesus": ["idle", "talk", "walk", "stand_talk", "ride", "ride_wave", "ride_talk", "sad_look", "tip_table",
                     "firm_talk", "open_cage", "rise_towel", "kneel_wash", "kneel_talk", "kneel_laugh", "sit_supper",
                     "bless_bread", "lift_cup", "smile", "laugh", "wave"],
           "peter": ["idle", "talk", "walk", "laugh", "amazed", "cheer", "listen_stone", "boast", "argue", "sit_bench",
                     "refuse", "offer_all", "sit_wash", "ashamed", "sit_supper", "serve_rise", "kneel_serve", "wave"],
           "donkey": ["idle", "walk", "hee_haw", "graze", "sleepy", "happy"]}
    out.update({d: list(dis) for d in DISCIPLES})
    out.update({s: list(sel) for s in SELLERS})
    return out


def ride_travel(travel):
    """Each donkey move with a `to` against Jesus's move on the same beat: the director moves the donkey at its walk
    speed (linear) and the rider as a glide (eased, dist / 0.12 s) unless the ride clips get a speed: offset between
    rider and seat over the move."""
    out = []
    dv = next(c for c in CLIPS if c.action == "donkey_walk").natural_speed
    rows = {(r["t"], r["action"].split("_")[0]): r for r in travel}
    for (t, who), r in rows.items():
        if who != "donkey":
            continue
        j = rows.get((t, "jesus"))
        d = r["dist"]
        nat = d / dv
        rate = min(1.6, max(1.0, nat / max(0.3, r["time"]))) if nat > r["time"] else 1.0
        Td = nat / rate
        Tj = max(0.6, d / 0.12)
        worst = 0.0
        for i in range(101):
            tt = Td * 1.2 * i / 100
            sd = min(1.0, tt / Td)
            s = min(1.0, tt / Tj); sj = s * s * (3 - 2 * s)
            worst = max(worst, abs(sj - sd) * d)
        out.append({"t": t, "dist": d, "donkeySeconds": round(Td, 2), "riderGlideSeconds": round(Tj, 2),
                    "riderHasMove": bool(j), "maxOffsetIfGlide": round(worst, 3),
                    "donkeyRate": round(rate, 2), "time": r["time"]})
    return out


SAMPLE_BONES = ("root", "head", "jaw", "handR", "handL", "footL", "footR", "pawL", "hips", "belt1", "sash1", "mantle1",
                "cloth1", "cloak1", "apron1", "pouch", "earL", "tail2", "towel", "basin", "bread", "cup", "palm", "jug")


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
            "stage": {"upper": UPPER, "rideY": RIDE_Y, "seatY": SEAT_Y, "rideCycleFrames": RIDE_N,
                      "rideMode": "jesus ride / ride_wave / ride_talk at base y RIDE_Y on the donkey's mark and heading; "
                      "the ride clips follow the donkey walk seat frame by frame, so start ride with donkey walk on the "
                      "same beat (same 27-frame cycle)", "kneelDistance": KNEEL_D, "basinInFront": BASIN_D,
                      "benchSeat": BENCH_SEAT, "cushion": CUSHION, "tableTop": TABLE_TOP, "stonesDistance": STONES_D,
                      "standDistance": STAND_D, "kneel": KNEEL["jesus"]}}
    only = os.environ.get("LS_ONLY")
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
        info.update(getattr(cl, "info", {}) or {})
        if cl.speed:
            info["naturalSpeed"] = round(cl.natural_speed, 4)
            info["stride"] = cl.speed[0]
        if cl.name in ("ride", "ride_wave", "ride_talk"):
            info["rideSpeed"] = round(next(c for c in CLIPS if c.action == "donkey_walk").natural_speed, 4)
        samp = {}
        for fr in sorted(set([0, cl.N // 2, cl.N])):
            M = frames[fr][1]
            samp[str(fr)] = {n: [round(v, 5) for v in rig.pos(M, n)] for n in SAMPLE_BONES if n in rig.names}
        info["samples"] = samp
        info["checks"] = clip_checks(rig, cl, frames)
        if cl.loop:
            info["loopSeamMaxErr"] = info["checks"]["seamStep"]
        print("LS_CHECK", cl.action, json.dumps(info["checks"]), flush=True)
        meta["clips"].append(info)
    meta["travel"] = travel_needs()
    for r in meta["travel"]:
        print("LS_TRAVEL", json.dumps(r))
    if not only or "jesus_ride" in only or "donkey" in only:
        meta["rideCheck"] = ride_check()
        meta["rideTravel"] = ride_travel(meta["travel"])
        print("LS_RIDE", json.dumps(meta["rideCheck"]))
        print("LS_RIDE_TRAVEL", json.dumps(meta["rideTravel"]))
    if not only or "kneel" in only:
        meta["kneelCheck"] = kneel_check()
        print("LS_KNEEL", json.dumps(meta["kneelCheck"]))
    if only:
        print("LS_BUILD_PARTIAL (no export)"); return
    os.makedirs(ANIM, exist_ok=True)
    bpy.context.preferences.filepaths.save_version = 0
    tmp_blend = os.path.join(WORK, "ls_anim.blend")
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
        print("LS_EXPORT", ch)
    os.remove(tmp_blend)
    json.dump(meta, open(os.path.join(ANIM, "clips.json"), "w"), indent=1)
    print("LS_BUILD_OK", len(meta["clips"]), "timelineMissing", missing_tl)


# =============================================================================================== render helpers
REGIONS = json.load(open(REGIONS_JSON))
FACES = {ch: {"default": v["faceDecal"]["default"], "clips": v["faceDecal"].get("clipExpression", {})}
         for ch, v in list(REGIONS["characters"].items()) + list(REGIONS.get("offSheet", {}).items())}
DECAL_NODES = {}


def face_png(ch, expr):
    p = os.path.join(FACE_DIR, f"{ch}_{expr}.png")
    return p if os.path.exists(p) else os.path.join(FACE_DIR, f"{ch}_{FACES[ch]['default']}.png")


def char_material(ch):
    """Kit demo colours for the sheet cast (jesus, peter, donkey); the extras: their fixed paint + decal."""
    if ch not in EXTRAS:
        return _kit_char_material(ch)
    m = bpy.data.materials.new(f"anim_{ch}"); m.use_nodes = True; nt = m.node_tree
    bsdf = nt.nodes.get("Principled BSDF"); bsdf.inputs["Roughness"].default_value = 0.75
    tex = nt.nodes.new("ShaderNodeTexImage"); tex.image = bpy.data.images.load(EXTRAS_PAINT, check_existing=True)
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


def yaw_to(frm, to):
    return math.degrees(math.atan2(to[0] - frm[0], to[1] - frm[1]))


def stage_of(cl):
    """Where a clip is shown in renders: (x, z, yaw, y) on the jerusalem set."""
    n, ch = cl.name, cl.ch
    if ch == "donkey":
        return (ROAD_MARK[0], ROAD_MARK[1], -90.0, 0.0)
    if n.startswith("ride"):
        return (ROAD_MARK[0], ROAD_MARK[1], -90.0, RIDE_Y)
    if n in ("sit_bench", "amazed", "ashamed", "refuse", "offer_all") or (ch == "peter" and n == "sit_wash"):
        return (BENCH_MARK[0], BENCH_MARK[1], 90.0, UPPER)
    if ch == "jesus" and n.startswith("kneel"):
        return (WASH_MARK[0], WASH_MARK[1], -90.0, UPPER)
    if n == "kneel_serve":
        return (SUP["peter"][0], SUP["peter"][1], 180.0, UPPER)
    if n in ("sit_supper", "bless_bread", "lift_cup", "smile", "nudge", "serve_rise") or n == "sit_wash":
        x, z = SUP.get(ch, SUP["andrew"])
        return (x, z, 0.0, UPPER)
    if n == "rise_towel":
        return (STAND_MARK[0], STAND_MARK[1], yaw_to(STAND_MARK, (-0.115, -0.535)), UPPER)
    if n == "stand_talk":
        return (WASH_MARK[0], WASH_MARK[1], -90.0, UPPER)
    if n == "tip_table":
        return (0.36, -0.26, yaw_to((0.36, -0.26), (0.46, -0.28)), 0.0)
    if n == "open_cage":
        return (0.28, -0.42, 90.0, 0.0)
    if n == "listen_stone":
        return (0.13, 0.18, yaw_to((0.13, 0.18), (0.05, 0.17)), 0.0)
    if ch in SELLERS:
        return (0.46, -0.37, 0.0, 0.0) if n != "chase_coins" else (0.53, -0.20, 0.0, 0.0)
    return (0.20, 0.10, 0.0, 0.0)


DIST_K = {ch: 1.35 for ch in CHARS}
DIST_K["donkey"] = 1.9


SET_OBJS = []


def setup_look_ls(sc, res, samples=8):
    before = set(bpy.data.objects)
    setup_look(sc, res, samples=samples)
    SET_OBJS[:] = [o for o in bpy.data.objects if o not in before and o.type == 'MESH' and o.name != "floor"]
    for o in SET_OBJS:
        o["ls_hide"] = False
    for o in bpy.data.objects:
        q = o
        while q is not None:
            if q.name.split(".")[0] in HIDE_SET + tuple(f"crowd{i}" for i in range(1, 9)):
                o.hide_render = True; o["ls_hide"] = True; break
            q = q.parent


def use_set(flag):
    """Single-clip renders: no set (walls block the room and court cameras), actor at y 0; pair rows: the set."""
    for o in SET_OBJS:
        o.hide_render = (not flag) or bool(o.get("ls_hide", False))


PROP_ON = {("jesus", "rise_towel"): {"towel": TOWEL_ON, "basin": BASIN_ON}, ("jesus", "bless_bread"): {"bread": BREAD_ON},
           ("jesus", "lift_cup"): {"cup": CUP_ON}, ("peter", "serve_rise"): {"towel": SERVE_ON, "jug": SERVE_ON}}


def set_props_for_frame(rig, cl, fr):
    for p, at in PROP_ON.get((cl.ch, cl.name), {}).items():
        o = bpy.data.objects.get(f"{cl.ch}_{p}")
        if o:
            o.hide_render = fr < at


def mark_cam(cam, rig, mark, view, dist_k, H=None):
    x, z, yaw0, y = mark
    H = H or rig.H
    yaw = {"front": 0, "q3": 32, "side": 90, "back": 180, "q3l": -32, "lside": -90, "top": 25, "low": 25,
           "phone": 15}[view] + yaw0
    tg = V(x, y + H * 0.45, z)
    dist = H * dist_k
    hgt = tg.y + H * (0.15 if view not in ("top", "phone") else (1.2 if view == "top" else 0.9))
    a_ = math.radians(yaw)
    look(cam, tg, V(tg.x + math.sin(a_) * dist, hgt, tg.z + math.cos(a_) * dist))


def place_mark(rig, mark):
    place_rig(rig, mark[0], mark[1], mark[2], mark[3])


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
        T = V((ma[0] + mb[0]) / 2, mb[3] + 0.12, (ma[1] + mb[1]) / 2)
        if mode == "ride":
            T = V(mb[0], 0.15, mb[1])
        cams = {"front": T + V(0.0, 0.08, 0.55), "q3": T + V(0.32, 0.18, 0.40), "top": T + V(0.0, 0.55, 0.15),
                "side": T + V(0.0, 0.06, 0.60) if mode == "ride" else T + V(0.50, 0.08, 0.10),
                "back": T + V(0.0, 0.10, -0.55), "lside": T + V(0.0, 0.06, -0.60),
                "phone": T + V(0.12, 0.45, 0.70)}
        if mode == "bench":
            cams["side"] = T + V(0.0, 0.08, 0.55); cams["q3"] = T + V(0.25, 0.20, 0.45)
        if mode == "front":
            cams["side"] = T + V(-0.14, 0.12, 0.45); cams["q3"] = T + V(0.20, 0.16, 0.45)
        for vn in views:
            look(cam, T, cams[vn], lens=40)
            fn = f"{prefix}_{fr:03d}_{vn}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True); out.append((fr, vn, fn))
    reset_pose(ra); reset_pose(rb)
    return out


def mode_contact():
    sc, rigs = open_scene()
    setup_look_ls(sc, (300, 300), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "contact"); os.makedirs(d, exist_ok=True)
    rows = []
    for cl in CLIPS:
        if cl.ch in ("james", "andrew") and cl.name not in ("sit_wash",):
            continue            # the disciples share the functions: john stands for all three (andrew's sit_wash shown)
        if cl.ch == "john" and cl.name == "sit_wash":
            continue
        if cl.ch == "seller2" and cl.name not in ("shout", "chase_coins"):
            continue
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
        on_road = mark[3] == 0.0 and mark[1] > 0.0 or cl.name.startswith("ride") or cl.ch == "donkey"
        use_set(on_road)
        if not on_road:
            mark = (mark[0], mark[1], mark[2], 0.0)
        row = {"action": cl.action, "loop": cl.loop, "frames_total": cl.N, "frames": []}
        for fr in picks:
            apply_basis(rig, frames[fr][0])
            place_mark(rig, mark)
            set_props_for_frame(rig, cl, fr)
            bpy.context.view_layer.update()
            mark_cam(cam, rig, mark, "q3", DIST_K[cl.ch])
            fn = f"{cl.action}_{fr:03d}.png"
            sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
            row["frames"].append({"f": fr, "file": fn, "marker": ",".join(k for k, v in cl.markers.items() if v == fr)})
        reset_pose(rig)
        rows.append(row)
        print("LS_CONTACT_ROW", cl.action, picks, flush=True)
    use_set(True)
    for a, b, dist, mode, label in [("jesus_ride", "donkey_walk", 0.0, "ride", "pair: ride + donkey walk (one mark)"),
                                    ("jesus_ride_wave", "donkey_walk", 0.0, "ride", "pair: ride_wave + donkey walk")] + \
            [(a, b, dd, m, "pair: " + lb) for a, b, dd, m, lb in KNEEL_PAIRS]:
        row = {"action": label, "loop": True, "frames_total": 0, "frames": []}
        if mode == "ride":
            sel = [(0, ("side",)), (7, ("side",)), (14, ("side",)), (20, ("q3",)), (40, ("front",)), (60, ("phone",))]
        else:
            sel = [(0, ("q3",)), (24, ("q3",)), (44, ("side",)), (12, ("phone",))]
        for fr, views in sel:
            for f_, vn, fn in render_pair(sc, cam, rigs, a, b, dist, mode, [fr], views, d, f"pair_{a}_{b}"):
                row["frames"].append({"f": f_, "file": fn, "marker": vn})
        rows.append(row)
    json.dump({"rows": rows}, open(os.path.join(d, "contact.json"), "w"), indent=1)


def mode_probe():
    """LS_PROBE="action:f1,f2:view;..."  view = front|q3|side|back|q3l|lside|top|low|phone.
    'pair:<A>:<B>:<dist>:<f1,f2>[:mode[:views]]' (modes ride | bench | front)."""
    sc, rigs = open_scene()
    res = int(os.environ.get("LS_PROBE_RES", "440"))
    setup_look_ls(sc, (res, res), samples=8)
    cam = camera(sc)
    d = os.path.join(WORK, "probe"); os.makedirs(d, exist_ok=True)
    for f_ in os.listdir(d):
        os.remove(os.path.join(d, f_))
    clips = {cl.action: cl for cl in CLIPS}
    out = []
    for item in os.environ.get("LS_PROBE", "").split(";"):
        if not item.strip():
            continue
        parts = item.strip().split(":")
        if parts[0] == "pair":
            use_set(True)
            a, b, dist = parts[1], parts[2], float(parts[3])
            frs = [int(v) for v in parts[4].split(",")]
            mode = parts[5] if len(parts) > 5 else "bench"
            views = parts[6].split(",") if len(parts) > 6 else ["q3", "side"]
            out += [fn for _, _, fn in render_pair(sc, cam, rigs, a, b, dist, mode, frs, views, d, f"pair_{a}_{b}")]
            continue
        action, frames, view = parts[0], parts[1], parts[2] if len(parts) > 2 else "q3"
        cl = clips[action]; rig = rigs[cl.ch]
        show_only(rigs, [cl.ch], {cl.ch: cl})
        set_expression(cl.ch, cl.name)
        fr_ = bake_clip(rig, cl)
        mark = stage_of(cl)
        withset = os.environ.get("LS_PROBE_SET", "0") == "1"
        use_set(withset)
        if not withset:
            mark = (mark[0], mark[1], mark[2], 0.0)
        dk = float(os.environ.get("LS_PROBE_DIST", str(DIST_K[cl.ch])))
        for fr in [int(v) for v in frames.split(",")]:
            fr = min(fr, cl.N)
            apply_basis(rig, fr_[fr][0]); place_mark(rig, mark)
            set_props_for_frame(rig, cl, fr)
            bpy.context.view_layer.update()
            for vn in view.split(","):
                mark_cam(cam, rig, mark, vn, dk)
                fn = f"{action}_{fr:03d}_{vn}.png"
                sc.render.filepath = os.path.join(d, fn); bpy.ops.render.render(write_still=True)
                out.append(fn)
        reset_pose(rig)
    json.dump(out, open(os.path.join(d, "probe.json"), "w"))
    print("LS_PROBE", len(out))


def mode_debug():
    sc, rigs = open_scene()
    exec(os.environ.get("LS_DEBUG", ""), dict(globals(), sc=sc, rigs=rigs))


{"build": mode_build, "verify": mode_verify, "contact": mode_contact, "probe": mode_probe, "debug": mode_debug}[MODE]()
