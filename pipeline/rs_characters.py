"""He Is Risen! (story pack `risen`): characters angel, jesus, mary (printed) + peter, john, thomas, joanna (fixed
paint, not on the sheet) — meshes, rigs, weights, UVs, face decals, previews, GLBs.

Contract: docs/risen/CONTRACT.md §1-§4 (ids, sizes, sheet slots, bone names, props), look: docs/risen/DESIGN.md §1 and
§3, notes for Animation: docs/risen/RIG.md.

Reuse, never fork (CONTRACT §2, R5): this script runs pipeline/ls_characters.py (The King Who Serves) in its own
namespace (definitions only, the way story_kit.include works; `_run_lastsupper` below). ls_characters.py itself runs
pipeline/mi_characters.py (Real Miracles) the same way, so every Miracles and King-Who-Serves definition becomes ours:
  * jesus: the Miracles `build_jesus`, unchanged, plus this pack's `fish` prop (handR, hidden);
  * peter: the Miracles `build_peter`, unchanged; the `bucket` bone stays, its mesh is dropped (as The King Who Serves);
    fixed paint (his front ID render on a virtual page becomes part of model/extras_paint.png, Miracles demo colours);
  * john: The King Who Serves `build_extra` ("john": the Miracles friend body + the white sash on sash1), unchanged;
  * thomas: the Miracles friend body (`build_friend`, unchanged) with a new costume (square beard, rust head band,
    short grey-brown cloak over both shoulders on cloak1).
New here:
  * `build_woman(C)` for mary (printed) and joanna (fixed paint): Ruth's female body (kit), wavy hair in front of a
    head veil (kit `hood`, back on veil1), a long dress with wide sleeves, a sash with one hanging end (sash1), a
    small spice jar in the left hand (`jar`, hidden); Joanna is the same builder with another costume (rounder, an
    apron-sash panel);
  * `build_angel(C)`: the kit human body in a long white robe with a high round neck, a broad gold sash (sash1),
    short golden curls, bare feet, and two soft wings of three layered feather rows each (coverts, secondaries,
    primaries), `wingL1/wingR1` (inner half, from chest) and `wingL2/wingR2` (outer half), folded half-open.
None of mi_*.py / ls_*.py is edited. Face decals that exist are copied (Miracles: Jesus, Peter; The King Who Serves:
Peter `puzzled`, John's group drawings); the new ones are drawn with the same patched Miracles drawing code.

Run (repo root):
  python3 pipeline/rs_characters.py all                                           # everything below, in order
  python3 pipeline/rs_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python-exit-code 1 --python pipeline/rs_characters.py -- build    # cast + extras
  blender ... -- extras        # the four extras only (run by build)
  python3 pipeline/rs_characters.py proof                                         # $RS_WORK/uvproof.png
  blender ... -- preview       # lit demo-palette renders
  blender ... -- uvcheck       # models wearing uvproof.png
  blender ... -- posetest      # bend / blink / jaw / cloth, wing fold, the angel on the stone, Mary crying / joyful,
                               # Peter stooping into the door, props shown
  blender ... -- verify        # re-import GLBs, check bones / parents / budget / heights
  python3 pipeline/rs_characters.py compose                                       # preview_*.png contact sheets
Blender: $BLENDER, else `blender` on PATH, else /Applications/Blender.app. Intermediate renders go to $RS_WORK
(default /tmp/risen_chars/work). RS_ONLY=angel (comma list) builds a subset of the printed cast (debug only).
"""
import sys, os, json, math, random, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RS_WORK = os.environ.get("RS_WORK", "/tmp/risen_chars/work")
os.environ["LS_WORK"] = RS_WORK          # ls (and through it mi) create their WORK folder at import: keep it in ours
LS_PATH = os.path.join(HERE, "ls_characters.py")
LS_FACES = os.path.join(ROOT, "docs/lastsupper/design/faces")
LS_SRC = open(LS_PATH, encoding="utf-8").read()
RS_FILE = os.path.abspath(__file__)


def _run_lastsupper():
    """Run pipeline/ls_characters.py in this module's namespace (it runs mi_characters.py the same way): every
    definition becomes ours. Its mode dispatch only runs under __main__, so nothing is built; outside Blender it stops
    with SystemExit after its Pillow part (caught)."""
    g = globals()
    keep = {k: g.get(k) for k in ("__name__", "__file__", "__doc__")}
    g["__name__"] = "ls_characters"; g["__file__"] = LS_PATH
    try:
        exec(compile(LS_SRC, LS_PATH, "exec"), g)
    except SystemExit:
        pass
    finally:
        g.update(keep)


_run_lastsupper()
_LS = {k: globals()[k] for k in ("ls_face_params", "PALETTE", "SWATCHES", "ANCHORS", "PART_ANCHORS", "FRIEND",
                                 "EXPRESSIONS", "CLIP_EXPRESSION", "LS_LOOK") if k in globals()}
for _k in ("build_extra", "pose_test", "mode_build", "mode_preview", "mode_uvcheck", "mode_verify", "Ctx"):
    if _k in globals():
        _LS[_k] = globals()[_k]
__file__ = RS_FILE

# ---------------------------------------------------------------------------------------------- this pack
MODEL = os.path.join(ROOT, "assets/risen/model")
FACES = os.path.join(ROOT, "docs/risen/design/faces")
WORK = RS_WORK
ENV = "RS_"
PAGE_MATERIAL = "rs_page"
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/risen/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

CHARS = ("angel", "jesus", "mary")                 # printed cast, sheet order left -> right
DISCIPLES = ("john", "thomas")
WOMEN = ("mary", "joanna")
EXTRAS = ("peter", "john", "thomas", "joanna")
FRIENDS = ()                         # only the Miracles pose_test reads it (belt1 bend); none here
SELLERS = ()
QUADS = ()
FISH = ()
HUMANS = CHARS + EXTRAS
WING_BONES = ["wingL1", "wingL2", "wingR1", "wingR2"]
EXTRA_BONES = {"jesus": ["mantle1", "belt1", "fish"], "peter": ["cloth1", "bucket"], "john": ["sash1"],
               "thomas": ["cloak1"], "mary": ["veil1", "sash1", "jar"], "joanna": ["veil1", "sash1", "jar"],
               "angel": ["sash1"] + WING_BONES}
EXTRA_PARENTS = {"mantle1": "chest", "belt1": "hips", "fish": "handR", "cloth1": "head", "bucket": "handR",
                 "sash1": "hips", "cloak1": "chest", "veil1": "head", "jar": "handL", "wingL1": "chest",
                 "wingL2": "wingL1", "wingR1": "chest", "wingR2": "wingR1"}
TOWEL_PARENT = {}


def bone_list(ch):
    return CONTRACT_BONES + EXTRA_BONES[ch]


PROPS = {"jesus": {"fish": False}, "mary": {"jar": False}, "joanna": {"jar": False}, "angel": {},
         "peter": {}, "john": {}, "thomas": {}}                         # prop bone -> shown by default
CONTRACT_HEIGHT = {"angel": 0.40, "jesus": 0.36, "mary": 0.34, "peter": 0.38, "john": 0.33, "thomas": 0.36,
                   "joanna": 0.33}
WING_TOP = 0.46
BUDGET = {"angel": 30000, "jesus": 25000, "mary": 25000, "peter": 25000, "john": 18000, "thomas": 18000,
          "joanna": 18000}
DEFAULT_SHEET = {"angel": (-0.32, 0.015), "jesus": (0.0, 0.015), "mary": (0.32, 0.015)}
# the extras: virtual page for their own ID render (three A-poses at +-0.34 never touch, C2; the fourth on a 2nd row)
EXTRA_PAGE = {"peter": (-0.34, 0.015), "john": (0.0, 0.015), "thomas": (0.34, 0.015), "joanna": (0.0, 0.58)}
EXTRA_BLEND = {"peter": (0.80, 0.0), "john": (1.00, 0.0), "thomas": (1.20, 0.0), "joanna": (1.40, 0.0)}
FRIEND_PAGE = EXTRA_PAGE; FRIEND_BLEND = EXTRA_BLEND
EXTRAS_PAINT = os.path.join(MODEL, "extras_paint.png")
FRIEND_PAINT = EXTRAS_PAINT
UPPER = 0.10                         # CONTRACT §5: the upstairs room floor
ANGEL_Y = 0.185                      # CONTRACT §4: the angel's base y on the stone (hips on the stone top 0.22)
STONE_ASIDE = (-0.17, -0.285)        # CONTRACT §6: tombStoneAside centre (x, z), disc 0.22 across, 0.05 thick

# ---------------------------------------------------------------------------------------------- palette (DESIGN §3)
_TAN = "#D2AE74"; _SANDAL = "#7A4E2E"; _CLAY = "#C46A3E"
_MIP = _MI["PALETTE"]
PALETTE = {
    "jesus": dict(_MIP["jesus"], fish="#C98A4A"),
    "peter": dict(_MIP["peter"]),
    "john": dict(_LS["PALETTE"]["john"]),
    "mary": {"skin": "#E6B48E", "hair": "#4A3020", "veil": "#8DB5D8", "dress": "#D9775F", "sash": "#F1E3C4",
             "sandals": _SANDAL, "jar": _CLAY},
    "joanna": {"skin": "#D9A27A", "hair": "#7D6E62", "veil": "#A84A3A", "dress": "#D9A93A", "sash": "#F1E3C4",
               "sandals": _SANDAL, "jar": _CLAY},
    "angel": {"skin": "#EBC29E", "hair": "#E2B85A", "robe": "#F4F7FB", "sash": "#E6B23E", "wings": "#FFF6DE"},
    "thomas": {"skin": "#C48C64", "hair": "#2A2018", "tunic": "#3E8E86", "belt": _TAN, "sandals": _SANDAL,
               "cloak": "#8A7A68", "band": "#B4502F"},
}
REGION_NAMES.update({
    "fish": ("烤鱼", "grilled fish"), "veil": ("头纱", "veil"), "dress": ("长裙", "dress"), "sash": ("腰带", "sash"),
    "jar": ("香料罐", "spice jar"), "robe": ("白袍", "robe"), "wings": ("翅膀", "wings"),
    "cloak": ("短披风", "cloak"), "band": ("头带", "head band"), "hair": ("头发", "hair")})
REGION_NAMES["hair"] = ("头发和胡子", "hair and beard")
# fixed-colour parts: UV1 points at a swatch in a corner of every decal of that character; UV0 anchored (detail lines)
_SW = {"sandals": (0.955, 0.925, 0.995, 0.995)}
SWATCHES = {"jesus": dict(_MI["SWATCHES"]["jesus"]), "peter": dict(_MI["SWATCHES"]["peter"]), "mary": dict(_SW),
            "joanna": dict(_SW)}
ANCHORS = {"jesus": dict(_MI["ANCHORS"]["jesus"]), "peter": dict(_MI["ANCHORS"]["peter"]),
           # Mary's sash prints well under 6 mm (DESIGN §1: "else a detail line taking the dress colour")
           "mary": {"sandals": "mary.dress", "sash": "mary.dress"}, "angel": {}}
# hidden props are not printed: they sample a printed region (CONTRACT §3; "set.<region>" = the set's drawings)
PROP_ANCHORS = {
    "jesus": {"fish": ["set.fishPlate", "set.fishOnPlate", "set.fish", "jesus.belt"]},
    "mary": {"jar": ["set.waterJar", "set.jar", "set.clay", "mary.dress"]},
}
PART_ANCHORS = {"jesus": dict(_MI["PART_ANCHORS"]["jesus"])}
for _c in ("mary", "angel"):
    PART_ANCHORS[_c] = {(p, "skin"): f"{_c}.FACE" for p in ("handL", "handR", "legL", "legR")}

# ---------------------------------------------------------------------------------------------- bodies
# women: Ruth's female body (the Esther proportions, a pack constant in pipeline/ru_characters.py; same numbers here)
WOMAN_BASE = dict(height=0.34, top=0.330, chin=0.272, hw=0.0204, zc=-0.001, depth=1.02, jaw=-0.12, cheek=0.08,
                  fr=dict(eye=0.472, brow=0.565, nose=0.262, mouth=0.158),
                  chin_narrow=0.10, crown=0.0, noseH=0.0016, nose_w=0.82, nose_long=0.0, brow=0.45, lips=1.25,
                  chinAmt=0.8, sockets=0.85, cheekbones=0.9,
                  neckBase=0.257, neck=(0.0079, 0.0074, -0.0080), shoulder=(0.034, 0.250), chestY=0.230,
                  waistY=0.205, hipY=0.180, hipX=0.0165, kneeY=0.094, ankleY=0.018, footLen=0.038, footScale=1.0,
                  upperArm=0.058, forearm=0.049, hand=0.031, palmFrac=0.52,
                  handDims=dict(palmW=0.0132, palmH=0.0054, wristW=0.0094, wristH=0.0064, fingerW=0.0034,
                                fingerT=0.0031, thumbW=0.0033, thumbT=0.0030, armR=0.0058))
WOMAN = {   # costume per woman (build_woman)
    "mary": dict(veil_front=0.17, round=0.0, apron=False, lod=1.0),       # young, soft round face, big dark eyes
    "joanna": dict(veil_front=0.12, round=1.0, apron=True, lod=0.72),      # older, practical, a little rounder
}
SPEC["mary"] = scaled(WOMAN_BASE, 1.0, 1.0, height=0.34, jaw=-0.10, cheek=0.16, chin_narrow=0.10, noseH=0.0017,
                      nose_w=0.86, lips=1.2, fr=dict(eye=0.468, brow=0.560, nose=0.262, mouth=0.160))
SPEC["joanna"] = scaled(WOMAN_BASE, 0.968, 1.06, height=0.33, jaw=0.02, cheek=0.26, chin_narrow=0.04, noseH=0.0019,
                        nose_w=0.95, lips=1.0, brow=0.55, chinAmt=0.6, cheekbones=0.7,
                        fr=dict(eye=0.474, brow=0.566, nose=0.262, mouth=0.160))
# the angel: the King body (as Jesus), a little taller; a young open face
SPEC["angel"] = scaled(KING, 1.105, 1.03, height=0.40, jaw=0.04, cheek=0.12, chin_narrow=0.04, noseH=0.0028,
                       nose_w=1.05, nose_long=0.0, brow=0.95, lips=0.95, chinAmt=0.6, sockets=0.95, cheekbones=0.95,
                       fr=dict(eye=0.494, brow=0.584, nose=0.274, mouth=0.164))
# thomas: the Miracles friend body (one head size, as every disciple), k = body length, bodyX = width
FRIEND = dict(_LS["FRIEND"])
FRIEND["thomas"] = dict(k=1.000, bodyX=1.06, belly=0.0, hair="short")   # sensible, solid, 0.36
_v = FRIEND["thomas"]; _k = _v["k"]
_sp = scaled(KING, _k, _k, height=CONTRACT_HEIGHT["thomas"], **_FHEAD)
_sp["chin"] = _sp["top"] - _FH; _sp["hw"] = 0.0219
_sp["shoulder"] = (_sp["shoulder"][0] * _v["bodyX"], _sp["shoulder"][1])
_sp["hipX"] = _sp["hipX"] * min(1.25, _v["bodyX"])
SPEC["thomas"] = _sp
EYE.update({"mary": (0.420, 0.330, 0.245), "joanna": (0.410, 0.290, 0.215), "angel": (0.405, 0.335, 0.232),
            "thomas": (0.405, 0.320, 0.222)})

# ---------------------------------------------------------------------------------------------- expressions
EXPRESSIONS = {"jesus": ["kind", "talk", "smile", "laugh", "gentle", "look_up", "joy", "chew"],
               "peter": ["jolly", "talk", "shock", "laugh", "amazed", "puzzled", "sad", "puff"],
               "john": ["happy", "talk", "amazed", "laugh", "sad", "shock"],
               "thomas": ["happy", "talk", "amazed", "shock", "doubt", "awe"],
               "mary": ["gentle", "talk", "sad", "cry", "gasp", "joy", "amazed"],
               "joanna": ["gentle", "talk", "sad", "gasp", "joy"],
               "angel": ["smile", "talk", "joy", "kind"]}
COPIED = {"jesus": ("mi", ["kind", "talk", "smile", "laugh", "gentle", "look_up"]),
          "peter": ("mi", ["jolly", "talk", "shock", "laugh", "amazed"]),
          "peter_ls": ("ls", ["puzzled"]),
          "john": ("ls", ["happy", "talk", "amazed", "laugh"])}
NEW_EXPRESSIONS = {"jesus": ["joy", "chew"], "peter": ["sad", "puff"], "john": ["sad", "shock"],
                   "thomas": EXPRESSIONS["thomas"], "mary": EXPRESSIONS["mary"], "joanna": EXPRESSIONS["joanna"],
                   "angel": EXPRESSIONS["angel"]}
DEFAULT_EXPR = {"jesus": "kind", "peter": "jolly", "john": "happy", "thomas": "happy", "mary": "gentle",
                "joanna": "gentle", "angel": "smile"}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "jesus": {"idle": "kind", "talk": "talk", "walk": "kind", "wave": "smile", "appear": "joy", "call_name": "gentle",
              "hold_hands": "joy", "peace": "joy", "show_hands": "smile", "eat_fish": "chew"},
    "mary": {"idle": "gentle", "walk": "gentle", "talk": "talk", "idle_jar": "gentle", "walk_jar": "gentle",
             "sad": "sad", "gasp": "gasp", "peek": "amazed", "run": "joy", "tell": "talk", "cry": "cry",
             "talk_down": "sad", "turn_joy": "joy", "hold_hands": "joy", "cheer": "joy"},
    "angel": {"idle": "smile", "sit_stone": "smile", "wings_open": "joy", "sit_talk": "talk", "sit_point": "kind",
              "sit_wave": "joy"},
    "peter": {"idle": "jolly", "talk": "talk", "walk": "jolly", "laugh": "laugh", "amazed": "amazed", "shock": "shock",
              "sit_sad": "sad", "jump_up": "puzzled", "run_puff": "puff", "puff": "puff", "stoop_look": "puzzled",
              "cheer": "laugh"},
    "john": {"idle": "happy", "talk": "talk", "laugh": "laugh", "amazed": "amazed", "sit_sad": "sad",
             "jump_up": "amazed", "run": "happy", "wave_hurry": "talk", "peek": "amazed", "shock": "shock",
             "cheer": "laugh"},
    "thomas": {"idle": "happy", "doubt": "doubt", "shock": "shock", "reach": "amazed", "kneel_worship": "awe",
               "cheer": "happy"},
    "joanna": {"idle": "gentle", "walk": "gentle", "idle_jar": "gentle", "walk_jar": "gentle", "sad": "sad",
               "gasp": "gasp", "peek": "gentle", "run": "joy"},
}


def face_file(ch, ex):
    return os.path.join(FACES, f"{ch}_{ex}.png")


def face_layout(ch):
    return _MI["face_layout"](ch)


# ---------------------------------------------------------------------------------------------- face drawings
# The patched Miracles draw_faces (exec'd by ls_characters.py) looks up ls_face_params, LS_LOOK, LS_FACE_CHARS,
# ls_draw_exprs, ls_face_hook, ls_overview_cells and ls_face_base at call time: this pack rebinds them.
LS_LOOK = dict(_LS["LS_LOOK"])
LS_LOOK.update({
    "thomas": dict(bcol=(30, 22, 18, 255), iris=(84, 60, 40), bw=0.066, nose=0.042, blush=0.31),
    "mary": dict(bcol=(70, 44, 30, 255), iris=(78, 50, 34), bw=0.040, nose=0.032, blush=0.30),
    "joanna": dict(bcol=(96, 80, 70, 255), iris=(92, 64, 42), bw=0.044, nose=0.036, blush=0.31),
    "angel": dict(bcol=(176, 128, 62, 255), iris=(74, 118, 168), bw=0.046, nose=0.036, blush=0.30),
})
_ls_face_params = _LS["ls_face_params"]


def rs_face_params(base):
    """Wrap the King-Who-Serves face_params (itself a wrap of the Miracles one): the new drawings of this pack."""
    lsfp = _ls_face_params(base)

    def woman(key):
        E, Bp, Bl, Br, M, o = base("friend", "happy")
        E.update(lid=0.12, top=1.0, bot=0.95, tilt=0.10, pupil=0.60, lash=3 if key == "mary" else 2, look=(0, 0))
        Bp.update(raise_=0.066, arch=0.36, thick=0.82, inner=0.0, outer=0.0)
        M.update(kind="soft", wd=0.072, jaw=0.0, side=0.0)
        o.update(lipcol=(200, 96, 100, 230), rim=(234, 176, 162, 235), bl=95, crow=0 if key == "mary" else 1,
                 crs=True, special=[])
        return E, Bp, Bl, Br, M, o

    def fp(key, ex):
        if key == "jesus" and ex in ("joy", "chew"):
            E, Bp, Bl, Br, M, o = base("jesus", "smile")
            if ex == "joy":       # a wide open smile, eyes curved, brows up ("Mary." / "Peace be with you!")
                E.update(top=0.66, bot=0.60, look=(0.0, 0.05)); Bp.update(raise_=0.090, arch=0.52)
                M.update(kind="grin", wd=0.098, jaw=0.22); o.update(bl=120, crow=3)
            else:                 # chewing: cheeks round, lips closed, eyes smiling
                E.update(mode="happy"); Bp.update(raise_=0.074, arch=0.46)
                M.update(kind="small", wd=0.060, jaw=0.0); o.update(bl=190, crow=3)
            return E, Bp, Bl, Br, M, o
        if key == "peter" and ex in ("sad", "puff"):
            E, Bp, Bl, Br, M, o = base("peter", "talk")
            if ex == "sad":       # head down, brows up in the middle
                E.update(top=0.70, bot=0.80, look=(0.0, -0.60)); Bp.update(inner=0.060, raise_=0.070, arch=0.04,
                                                                          outer=-0.030)
                M.update(kind="frown", wd=0.082, jaw=0.0); o.update(bl=60, crow=0)
            else:                 # red cheeks, mouth wide panting, eyes squeezed
                E.update(mode="closed"); Bp.update(inner=0.050, raise_=0.085, arch=0.04, outer=-0.020)
                M.update(kind="shout", wd=0.094, jaw=0.42); o.update(bl=235, crow=0, crs=False, special=["sweat"])
            return E, Bp, Bl, Br, M, o
        if key in DISCIPLES and ex in ("sad", "shock", "doubt", "awe"):
            E, Bp, Bl, Br, M, o = base("friend", "happy")
            if ex == "sad":
                E.update(top=0.72, bot=0.82, look=(0.10, -0.50)); Bp.update(inner=0.050, raise_=0.070, arch=0.04,
                                                                           outer=-0.025)
                M.update(kind="frown", wd=0.072); o.update(bl=60, crow=0)
            elif ex == "shock":   # eyes huge, mouth a wobbly zigzag ("a g-g-ghost?")
                E.update(top=1.45, bot=1.25, pupil=0.28, lid=0.04, tilt=0.0)
                Bp.update(raise_=0.140, arch=0.74, outer=0.020); M.update(kind="wobbly", wd=0.090, jaw=0.30)
                o.update(bl=70, crow=0, special=["sweat"])
            elif ex == "doubt":   # one brow down, mouth flat to one side
                E.update(top=0.70, bot=0.80, look=(-0.55, 0.10)); Bl = dict(inner=-0.030, raise_=0.045, arch=0.06)
                Br = dict(raise_=0.100, arch=0.50); M.update(kind="smirk", wd=0.070, side=-1.0); o.update(bl=60, crow=0)
            else:                 # awe: eyes wet and shining, mouth open in a soft smile ("My Lord and my God!")
                E.update(top=1.15, bot=1.0, pupil=0.48, wet=True, look=(0.0, 0.55), lid=0.08)
                Bp.update(inner=0.030, raise_=0.100, arch=0.45); M.update(kind="grin", wd=0.080, jaw=0.10)
                o.update(bl=120, crow=1)
            return E, Bp, Bl, Br, M, o
        if key in WOMEN:
            E, Bp, Bl, Br, M, o = woman(key)
            if ex == "gentle":
                E.update(top=0.88, look=(0.0, -0.05)); M.update(kind="soft", wd=0.068); o["bl"] = 105
            elif ex == "talk":
                E.update(top=0.96); M.update(kind="open", wd=0.064, jaw=0.07)
            elif ex == "sad":     # brows up in the middle, mouth small
                E.update(top=0.80, bot=0.86, look=(0.0, -0.35)); Bp.update(inner=0.050, raise_=0.075, arch=0.04,
                                                                          outer=-0.025)
                M.update(kind="small", wd=0.056); o.update(bl=60)
            elif ex == "cry":     # eyes squeezed, two drawn tear drops, mouth wobbly (not ugly-crying)
                E.update(mode="closed"); Bp.update(inner=0.060, raise_=0.085, arch=0.02, outer=-0.035)
                M.update(kind="wobbly", wd=0.064, jaw=0.05); o.update(special=["tears"], bl=150, crs=False)
            elif ex == "gasp":    # eyes round, mouth O
                E.update(top=1.40, bot=1.20, pupil=0.34, lid=0.05, tilt=0.0); Bp.update(raise_=0.130, arch=0.70)
                M.update(kind="o", wd=0.058, jaw=0.30); o.update(bl=80)
            elif ex == "joy":     # laughing, eyes curved (a tear is added on one cheek after drawing)
                E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.090, jaw=0.20)
                o.update(bl=155)
            elif ex == "amazed":
                E.update(top=1.30, bot=1.10, pupil=0.36, lid=0.06); Bp.update(raise_=0.120, arch=0.64)
                M.update(kind="o", wd=0.054, jaw=0.18); o.update(bl=110)
            return E, Bp, Bl, Br, M, o
        if key == "angel":
            E, Bp, Bl, Br, M, o = base("friend", "happy")
            E.update(lid=0.10, top=1.0, bot=0.95, tilt=0.05, pupil=0.55, lash=1, look=(0, 0))
            Bp.update(raise_=0.068, arch=0.40, thick=0.95, inner=0.0, outer=0.0)
            M.update(kind="grin", wd=0.092, jaw=0.08, side=0.0)
            o.update(lipcol=(190, 110, 100, 220), rim=(236, 186, 160, 235), bl=85, crow=1, crs=True, special=[])
            if ex == "smile":     # a big friendly smile (default)
                E.update(top=0.82, bot=0.76); M.update(kind="grin", wd=0.096, jaw=0.08); o.update(bl=110, crow=2)
            elif ex == "talk":
                E.update(top=0.94); M.update(kind="open", wd=0.080, jaw=0.09)
            elif ex == "joy":
                E.update(mode="happy"); Bp.update(raise_=0.092, arch=0.56); M.update(kind="grin", wd=0.104, jaw=0.24)
                o.update(bl=140, crow=3)
            elif ex == "kind":    # closed-mouth smile, soft eyes
                E.update(top=0.74, bot=0.78, look=(0.05, -0.10)); Bp.update(inner=0.020, raise_=0.066, arch=0.28)
                M.update(kind="soft", wd=0.074); o.update(crow=2, bl=95)
            return E, Bp, Bl, Br, M, o
        return lsfp(key, ex)
    return fp


ls_face_params = rs_face_params
LS_FACE_CHARS = ("jesus", "peter", "john", "thomas", "mary", "joanna", "angel")


def ls_draw_exprs(ch):
    return NEW_EXPRESSIONS.get(ch, [])


def ls_face_base(ch):
    return PALETTE[ch].get("skin")


def ls_overview_cells():
    return [(ch, ex) for ch in ("angel", "jesus", "mary", "peter", "john", "thomas", "joanna") for ex in EXPRESSIONS[ch]]


def ls_face_hook(ch, ex, img, T):
    return False


def _tear_on_cheek(ch, ex, side=-1):
    """Mary's `joy`: "a tear still on one cheek" (one drop under the viewer's left eye), drawn on the finished decal."""
    from PIL import Image, ImageDraw
    p = face_file(ch, ex); im = Image.open(p).convert("RGBA"); N = im.width
    F = face_layout(ch); c = F["eyeR"] if side < 0 else F["eyeL"]; ew, eh = F["eyeHalf"]
    x, y, s = c[0] - side * ew * 0.1, c[1] - eh * 3.0, 0.034
    P = lambda a, b: (a * N, (1 - b) * N)
    pts = [(x, y + s * 1.3), (x + s * 0.55, y), (x + s * 0.4, y - s * 0.45), (x, y - s * 0.6), (x - s * 0.4, y - s * 0.45),
           (x - s * 0.55, y)]
    lay = Image.new("RGBA", im.size, (0, 0, 0, 0)); d = ImageDraw.Draw(lay)
    d.polygon([P(*q) for q in pts], fill=(150, 205, 245, 235))
    d.line([P(*q) for q in pts + pts[:1]], fill=(60, 110, 160, 255), width=max(2, N // 170))
    hx, hy = x - s * 0.18, y - s * 0.05
    d.ellipse((P(hx - s * 0.12, hy + s * 0.18)[0], P(hx, hy + s * 0.18)[1], P(hx + s * 0.08, hy)[0],
               P(hx + s * 0.08, hy)[1]), fill=(255, 255, 255, 220))
    im.alpha_composite(lay); im.save(p)


def draw_faces():
    """Copy the decals this pack reuses (Miracles, The King Who Serves), then draw the new ones (patched Miracles
    drawing code)."""
    copied = []
    for key, (src_pack, exprs) in COPIED.items():
        ch = key.split("_")[0]
        src_dir = MI_FACES if src_pack == "mi" else LS_FACES
        for ex in exprs:
            shutil.copy(os.path.join(src_dir, f"{ch}_{ex}.png"), face_file(ch, ex)); copied.append(f"{ch}_{ex}")
    made = _mi_draw_faces()
    _tear_on_cheek("mary", "joy")
    # the overview was drawn before the tear: draw it again from the files
    made2 = dict(made)
    print("faces copied:", len(copied), "| drawn:", len(made2))
    _overview()
    return made2


def _overview():
    from PIL import Image, ImageDraw
    cells = ls_overview_cells(); cols = 8; cw = 256
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (cw + 24 + 88)), (250, 246, 238))
    dr = ImageDraw.Draw(sheet)
    for i, (ch, ex) in enumerate(cells):
        x, y = (i % cols) * cw, (i // cols) * (cw + 24 + 88)
        base = ls_face_base(ch)
        bg = Image.new("RGBA", (cw, cw), tuple(int(base[k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        bg.alpha_composite(Image.open(face_file(ch, ex)).convert("RGBA").resize((cw, cw), Image.LANCZOS))
        sheet.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 8, y + cw + 4), f"{ch}_{ex}", fill=(40, 30, 20))
        sheet.paste(bg.resize((64, 64), Image.LANCZOS).convert("RGB"), (x + 8, y + cw + 22))
    sheet.save(os.path.join(FACES, "overview.png"))


# ---------------------------------------------------------------------------------------------- compose (Pillow)
def compose():
    """Contact sheets model/preview_<char>.png, preview_extras.png, preview_all.png, preview_uvcheck.png,
    preview_pose.png, preview_fit.png from $RS_WORK."""
    from PIL import Image, ImageDraw
    bg = (250, 246, 238)

    def grid(files, labels, cols, cell, title):
        rows = (len(files) + cols - 1) // cols
        im = Image.new("RGB", (cols * cell[0], rows * (cell[1] + 26) + 34), bg)
        d = ImageDraw.Draw(im)
        d.text((10, 10), title, fill=(40, 30, 20))
        for i, (f, lb) in enumerate(zip(files, labels)):
            if not os.path.exists(f):
                continue
            t = Image.open(f).convert("RGB").resize(cell, Image.LANCZOS)
            x, y = (i % cols) * cell[0], 34 + (i // cols) * (cell[1] + 26)
            im.paste(t, (x, y)); d.text((x + 8, y + cell[1] + 6), lb, fill=(60, 50, 40))
        return im

    def stack(parts):
        W = max(p.width for p in parts)
        im = Image.new("RGB", (W, sum(p.height for p in parts)), bg)
        y = 0
        for p in parts:
            im.paste(p, (0, y)); y += p.height
        return im
    W_ = lambda n: os.path.join(WORK, n)
    views = [("front", "front"), ("q34", "3/4"), ("side", "side"), ("back", "back")]
    for ch in CHARS:
        top = grid([W_(f"pv_{ch}_{v}.png") for v, _ in views], [lb for _, lb in views], 4, (480, 720),
                   f"{ch}: rest pose, demo palette + default face decal")
        det = [("head", "face 3/4"), ("headfront", "face front"), ("handL", "left hand"), ("handR", "right hand"),
               ("props", "props shown")]
        bot = grid([W_(f"pv_{ch}_{v}.png") for v, _ in det], [lb for _, lb in det], 5, (384, 384), "close-ups")
        ex = grid([W_(f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]], EXPRESSIONS[ch], 6, (320, 320),
                  "face decals on the model (UV1)")
        stack([top, bot, ex]).save(os.path.join(MODEL, f"preview_{ch}.png"))
    fv = [W_(f"pv_{f}_{v}.png") for f in EXTRAS for v, _ in views]
    if any(os.path.exists(f) for f in fv):
        top = grid(fv, [f"{f} {lb}" for f in EXTRAS for _, lb in views], 4, (420, 630),
                   "extras (not on the sheet): fixed paint model/extras_paint.png on UV0 + face decals")
        grp = grid([W_(f"pv_extras_{v}.png") for v in ("line", "lineq")], ["line-up, front", "3/4"], 2, (960, 600),
                   "silhouettes side by side: " + ", ".join(EXTRAS))
        cells = [(e, x) for e in EXTRAS for x in EXPRESSIONS[e]]
        ex = grid([W_(f"pv_{e}_expr_{x}.png") for e, x in cells], [f"{e} {x}" for e, x in cells], 6, (300, 300),
                  "face decals on the model")
        stack([top, grp, ex]).save(os.path.join(MODEL, "preview_extras.png"))
    al = [W_(f) for f in ("pv_all.png", "pv_all_phone.png")]
    if all(os.path.exists(f) for f in al):
        stack([grid([al[0]], ["the cast at their sheet slots"], 1, (1600, 1000), "cast"),
               grid([al[1]], ["phone-like high angle"], 1, (1600, 1000), "")]).save(os.path.join(MODEL, "preview_all.png"))
    uv = [W_(f) for f in ("uvproof.png", "uv_front.png", "uv_q34.png", "uv_back.png")]
    if all(os.path.exists(f) for f in uv):
        a = Image.open(uv[0]).convert("RGB")
        b = Image.open(uv[1]).convert("RGBA")
        w = Image.new("RGBA", b.size, (255, 255, 255, 255)); w.alpha_composite(b); b = w.convert("RGB")
        r1 = Image.new("RGB", (2000, a.height), bg); r1.paste(a, (0, 0)); r1.paste(b.resize((1000, a.height)), (1000, 0))
        r2 = Image.new("RGB", (2000, 562), bg)
        r2.paste(Image.open(uv[2]).convert("RGB").resize((1000, 562)), (0, 0))
        r2.paste(Image.open(uv[3]).convert("RGB").resize((1000, 562)), (1000, 0))
        hd = Image.new("RGB", (2000, 30), bg)
        ImageDraw.Draw(hd).text((10, 8), "UV0 proof: left = a perfectly coloured sheet (ID render in demo colours), right "
                                "= the models wearing it, front ortho (must equal the sheet); then 3/4 + back",
                                fill=(40, 30, 20))
        stack([hd, r1, r2]).save(os.path.join(MODEL, "preview_uvcheck.png"))
    pf = [(W_(f"pose_{ch}_{v}.png"), f"{ch} {v}") for ch in CHARS + EXTRAS for v in ("a", "b", "closed")]
    pf = [p for p in pf if os.path.exists(p[0])]
    if pf:
        grid([p[0] for p in pf], [p[1] for p in pf], 6, (320, 400),
             "pose test: a/b = elbows, fingers, thigh + knee, spine, head turn, jaw open, half / full blink, cloth bones "
             "(angel b: wings folded); closed = eyes shut").save(os.path.join(MODEL, "preview_pose.png"))
    rf = [(W_(f"fit_{v}.png"), lb) for v, lb in FIT_VIEWS]
    rf = [r for r in rf if os.path.exists(r[0])]
    if rf:
        grid([r[0] for r in rf], [r[1] for r in rf], 3, (640, 480),
             "fit tests (test poses, not clips)").save(os.path.join(MODEL, "preview_fit.png"))
    print("composed previews ->", MODEL)


FIT_VIEWS = (("angel_side", "angel on the stone: side (stand-in stone + rock face)"),
             ("angel_front", "angel on the stone: front"), ("angel_phone", "angel on the stone: phone angle"),
             ("angel_open", "wings spread wide (wings_open peak), front"),
             ("angel_fold", "wings folded (outer half behind the inner), back"),
             ("mary_cry", "Mary crying: hands near the cheeks, eyes visible"),
             ("mary_joy", "Mary turn_joy end: hands to the cheeks, face joy"),
             ("mary_jar", "Mary: jar shown in the left hand"),
             ("peter_stoop", "Peter stooping into the door (top 0.34), side"),
             ("peter_stoop_front", "Peter stooping: front (door frame stand-in)"),
             ("jesus_fish", "Jesus: fish shown in the right hand"),
             ("pair_hands", "hold_hands spacing: Jesus / Mary 0.11 apart"))


if not IN_BLENDER:
    if __name__ == "__main__":
        mode = sys.argv[1] if len(sys.argv) > 1 else "faces"

        def blender_bin():
            return os.environ.get("BLENDER") or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"

        def run_all():
            import subprocess
            draw_faces()
            subprocess.run([blender_bin(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", RS_FILE,
                            "--", "build"], check=True, stdout=subprocess.DEVNULL)
            proof()
            for m in ("preview", "uvcheck", "posetest", "verify"):
                subprocess.run([blender_bin(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", RS_FILE,
                                "--", m], check=True, stdout=subprocess.DEVNULL)
            compose()
            v = json.load(open(os.path.join(WORK, "verify.json")))
            for ch, i in v.items():
                print(ch, "bonesMatch", i["bonesMatch"], "parentsOK", i.get("parentsOK"), "actions", i["actions"],
                      "tris", i["tris"], "budget", i["budget"], "uvOrderOK", i.get("uvOrderOK"),
                      "maxInf", i.get("maxInfluences"), "height", i["heightTop"], "err%", i["heightErrPct"],
                      "minY", i["minY"], *(("wingTop", i["wingTop"]) if "wingTop" in i else ()))
        {"faces": draw_faces, "compose": compose, "proof": proof, "all": run_all}[mode]()
    raise SystemExit(0)

# =============================================================================================== Blender part
ONLY = [c for c in os.environ.get("RS_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()
SET_PROP_ANCHORS = set_prop_anchors()
REGIONS_KEY = "rs_regions"


# =============================================================================================== props
def add_fish(C):
    """Jesus's grilled fish in the right hand (hidden): a small fish 0.05 long, body along the hand, tail fin."""
    S = C.S; A = C.arm["R"]; gp = grip_point(C, "R")
    ax = A["dh"].copy(); up = A["Np"]
    c = gp + up * 0.0042 * S + V(0, 0, 0.004)
    C.B["fish"] = (gp.copy(), gp + ax * 0.012 * S, "handR")
    cg = Cage()
    L_ = 0.050; n = 9
    side = V(0, 0, 1).cross(ax).normalized()                   # across the hand, in the picture plane
    c = c + ax * 0.004 * S                                     # across the palm, held like a real fish
    path = [c + side * (L_ * (i / (n - 1) - 0.45)) for i in range(n)]
    rad = [(0.0016 + 0.0072 * math.sin(math.pi * min(1.0, (i / (n - 1)) * 1.15)) ** 0.8) for i in range(n)]
    rad = [(max(0.0014, r), max(0.0012, r * 0.50)) for r in rad]
    tube(cg, path, rad, 8, None, "fish", 0, ref=ax)
    tail = path[0] - side * 0.002
    for sg in (1, -1):                                         # a V tail fin (both faces)
        a = cg.add(tail, None); b = cg.add(tail - side * 0.012 + ax * sg * 0.0085, None)
        cc = cg.add(tail - side * 0.007, None)
        cg.face((a, b, cc) if sg > 0 else (a, cc, b), "fish", 0)
        cg.face((a, cc, b) if sg > 0 else (a, b, cc), "fish", 0)
    C.add("fish", cg, subdiv=0, rigid="fish")


def add_jar(C):
    """The small round spice jar with a lid and a cord (0.05 high), held in the left hand (hidden by default)."""
    S = C.S; gp = grip_point(C, "L")
    C.B["jar"] = (gp.copy(), gp + V(0, -0.020, 0), "handL")
    cg = Cage()
    jc = gp + V(0, -0.046, 0.002)
    prof = [(0.0, 0.0080), (0.006, 0.0140), (0.018, 0.0168), (0.030, 0.0140), (0.036, 0.0080), (0.040, 0.0072),
            (0.0405, 0.0094), (0.0445, 0.0092), (0.0470, 0.0040), (0.0485, 0.0)]
    rings = [cg.ring([jc + V(math.sin(2 * math.pi * j / 12) * r, dy, math.cos(2 * math.pi * j / 12) * r)
                      for j in range(12)], None) for dy, r in prof[:-1]]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "jar", 0)
    cg.fan(list(reversed(rings[0])), jc, None, "jar", 0)
    cg.fan(rings[-1], jc + V(0, prof[-1][0], 0), None, "jar", 0)
    # the cord: from the neck up to the fist (the jar hangs from it)
    pth = [jc + V(0.0060, 0.038, 0.0), gp + V(0.0012, -0.004, 0.0), jc + V(-0.0060, 0.038, 0.0)]
    pth = [cr_open(pth, t / 6) for t in range(7)]
    tube(cg, pth, [(0.0010, 0.0010)] * len(pth), 5, None, "jar", 0, ref=V(0, 0, 1))
    C.add("jar", cg, subdiv=0, rigid="jar")


def build_jesus_rs(C):
    _MI["build_jesus"](C)
    add_fish(C)


def build_peter_rs(C):
    _MI["build_peter"](C)
    C.parts = [p for p in C.parts if p["name"] != "bucket"]     # bone kept (CONTRACT §3), mesh dropped


# =============================================================================================== women
def build_woman(C):
    """Mary / Joanna: Ruth's female body, wavy hair, head veil (veil1), long dress with wide sleeves, sash with one
    hanging end (sash1), the jar (handL, hidden)."""
    ch = C.ch; cs = WOMAN[ch]
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; hipY = s["hipY"]
    rim = esther_like_rim(C, 0.37)
    C.hair_rim = rim
    skeleton(C)
    build_head(C, hair_cull(C, rim))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0032, 0.0044, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        t = lerp(t, 0.0040, smoothstep(0.10, 0.20, uu) * smoothstep(L["eye"], L["mouth"], y))
        if uu < 0.12:
            t = lerp(t, 0.0024, smoothstep(L["brow"] + 0.43 * H, L["brow"] + 0.34 * H, y))
        return t * S

    def plumb(uu):
        return smoothstep(0.12, 0.18, uu) * smoothstep(0.44, 0.30, uu)
    hair_shell(C, rim, thick, "hair", "hair", plumb=plumb, parting=False, waves=0.0012 * S, NU=32 if cs["lod"] >= 1 else 24,
               NV=7 if cs["lod"] >= 1 else 6, grooves=40,
               groove_amp=0.00034)
    # ---- long dress to the ankles, wide sleeves (a soft bell at the wrist)
    R = scale_rows(ESTHER_ROBE, k, kx)
    rnd = cs["round"]
    R = [(y, hw * (1.0 + 0.05 * smoothstep(0.20 * k, 0.08 * k, y)) + rnd * 0.0040 * math.exp(-((y - 0.205 * k) / 0.03) ** 2),
          zf + rnd * 0.0026 * math.exp(-((y - 0.20 * k) / 0.03) ** 2), zb - rnd * 0.0006) for y, hw, zf, zb in R]
    sleeve = [(0.004, 0.0104), (0.014, 0.0102), (0.028, 0.0098), (0.042, 0.0100), (0.056, 0.0110), (0.068, 0.0126),
              (0.078, 0.0142), (0.085, 0.0152), (0.088, 0.0155)]
    build_robe(C, R, sleeve, None, nf=16, fold_amp=0.0020, sleeve_fold=0.0011, bell_sag=0.0014 * S, reg="dress",
               name="dress", **({} if cs["lod"] >= 1 else dict(N=36, step=0.0070)))
    C.tunic_rows = C.robe_rows
    for side in "LR":
        build_forearm_hand(C, side, 0.040 * S)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S))
    # ---- sash at the waist, a knot and one hanging end at her left hip (sash1)
    waist_band(C, "sash", "sash", wy - 0.0066 * S, wy + 0.0062 * S, 0.0011 * S, bulge=0.0011 * S)
    hanging_end(C, "sashEnd", "sash", 0.0130 * S, wy - 0.001 * S, wy - 0.062 * S, 0.0040, "sash1", off=0.0036)
    C.parts[-1]["piece_as"] = "sash"
    if cs["apron"]:                                  # Joanna: a cream apron panel tied with the sash
        wtop = C.w(["hips"]); wsk = skirt_weights(C)

        def wfn(p):
            t = smoothstep(wy - 0.010 * S, hipY - 0.012 * S, p.y)
            return mixw((wtop(p), 1 - t), (wsk(p), t)) if t > 0 else wtop(p)
        cols = [-0.85 + 1.70 * i / 8 for i in range(9)]
        _shell_panel(C, "apron", lambda i: "sash", cols, lambda a: 0.082 * k + 0.004 * S * abs(a),
                     lambda a: wy - 0.006 * S, lambda a, v: (0.0030 + 0.0014 * (1 - v)) * S, wfn, NV=6, solid=0.0010,
                     piece_as="apron")
    # ---- head veil: over the head (hair showing in front), framing the face, to the shoulders and the upper back
    zbh = C.head.at(0.5, L["chin"] + 0.15 * H).z
    zb_bl = table(C.robe_rows, chestY)[2]
    C.B["veil1"] = (V(0, L["chin"] + 0.10 * H, zbh - 0.003 * S), V(0, chestY - 0.010 * S, zb_bl - 0.007 * S), "head")
    vf = cs["veil_front"]

    def vrim(u):
        uu = mirror_u(u)
        return table([(0.000, L["top"] - vf * H), (0.050, L["top"] - (vf + 0.03) * H), (0.095, L["brow"] + 0.24 * H),
                      (0.130, L["eye"] + 0.04 * H), (0.160, L["nose"] - 0.05 * H), (0.182, L["mouth"] - 0.12 * H),
                      (0.195, L["chin"] - 0.22 * H), (0.206, shY - 0.006 * S), (0.225, chestY - 0.006 * S),
                      (0.26, shY - 0.016 * S), (0.30, shY - 0.030 * S), (0.36, chestY - 0.020 * S),
                      (0.43, wy + 0.012 * S), (0.50, wy + 0.004 * S)], uu)[0]

    def vthick(u, y):
        uu = mirror_u(u)
        return (0.0022 + 0.0012 * smoothstep(L["brow"], L["top"], y) + 0.0010 * smoothstep(0.15, 0.30, uu)) * S
    hood(C, "veil", "veil", vrim, vthick, hood_weights(C, ["veil1", ("chest", None)]), NU=int(50 * cs["lod"]) // 2 * 2,
         NV=int(20 * cs["lod"]),
         flare=0.06, body_off=0.0024, front_pull=0.30, folds=(13, 0.0016), hem_wave=0.0012, solid=0.0010)
    add_jar(C)


# =============================================================================================== the angel
# Left wing (x > 0) in the rest pose, design units: the edge over the top (root -> tip) and the edge underneath
# (root -> tip); the wing surface is the ruled surface between them (t = 0 top edge .. 1 bottom edge), rows of feathers
# hang downward. Depth z swept back from the shoulder blade. Mirrored for the right wing.
WING_TOP_EDGE = [(0.020, 0.290), (0.030, 0.360), (0.048, 0.418), (0.072, 0.451), (0.096, 0.460), (0.117, 0.449),
                 (0.131, 0.420), (0.138, 0.383)]
WING_BOT_EDGE = [(0.020, 0.290), (0.022, 0.235), (0.032, 0.180), (0.052, 0.140), (0.078, 0.128), (0.102, 0.150),
                 (0.122, 0.212), (0.134, 0.300), (0.138, 0.383)]
WING_ROWS = [("coverts", 0.00, 0.40, 0.0030, 9), ("secondaries", 0.32, 0.72, 0.0015, 8), ("primaries", 0.62, 1.00, 0.0, 7)]
WING_Z0, WING_SLOPE = -0.031, 0.105


def _resample(pts, n):
    seg = [math.dist(a, b) for a, b in zip(pts, pts[1:])]; tot = sum(seg)
    out = []
    for i in range(n):
        d = tot * i / (n - 1); j = 0
        while j < len(seg) - 1 and d > seg[j]:
            d -= seg[j]; j += 1
        f = d / seg[j] if seg[j] else 0
        a, b = pts[j], pts[j + 1]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out


def wing_weights(C, side):
    """Inner half on wing*1, outer half on wing*2 (blend across the middle), the root blended into the chest."""
    b1, b2 = f"wing{side}1", f"wing{side}2"

    def f(p):
        x = abs(p.x)
        t2 = smoothstep(0.066, 0.092, x)
        tc = smoothstep(0.034, 0.020, x) * 0.6
        w = {b1: (1 - t2) * (1 - tc), b2: t2 * (1 - tc)}
        if tc > 0:
            w["chest"] = tc
        return {k_: v for k_, v in w.items() if v > 1e-4}
    return f


def build_wing(C, side):
    sd = 1 if side == "L" else -1
    NS = 56
    top = _resample(WING_TOP_EDGE, NS + 1); bot = _resample(WING_BOT_EDGE, NS + 1)
    wfn = wing_weights(C, side)

    def P(si, t, layer, bulge=0.0):
        x = top[si][0] + (bot[si][0] - top[si][0]) * t; y = top[si][1] + (bot[si][1] - top[si][1]) * t
        z = WING_Z0 - WING_SLOPE * (x - 0.020) + layer + bulge * math.sin(math.pi * min(1.0, max(0.0, t)))
        return V(sd * x, y, z)
    cg = Cage()
    for pc, (nm, t0, t1, layer, nf) in enumerate(WING_ROWS):
        NT = 4
        grid = []
        for i in range(NS + 1):
            s_ = i / NS
            # feather tips: rounded scallops along the lower edge of the row
            sc = abs(math.sin(math.pi * nf * s_)) ** 0.55
            tb = min(1.0, t1 - (0.07 if t1 < 1.0 else 0.06) * (1 - sc)) if 0 < i < NS else t1 - 0.06
            if t1 >= 1.0:
                tb = 1.0 - 0.07 * (1 - sc) if 0 < i < NS else 1.0
            col = []
            for j in range(NT + 1):
                t = lerp(t0, tb, j / NT)
                col.append(cg.add(P(i, t, layer, 0.0030), wfn))
            grid.append(col)
        for i in range(NS):
            for j in range(NT):
                q = (grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1])
                cg.face(q if sd > 0 else tuple(reversed(q)), "wings", pc)
    C.add("wing" + side, cg, subdiv=0, solidify=0.0011)


def build_angel(C):
    """The angel: kit King body, long white robe (high round neck, long sleeves), broad gold sash (sash1), short golden
    curls, bare feet, two wings (wing*1 / wing*2)."""
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]
    cb = L["brow"] + 0.30 * H
    back = L["chin"] + 0.04 * H; sides = L["eye"] - 0.04 * H

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb), (0.08, cb - 0.01 * H), (0.13, L["brow"] + 0.15 * H), (0.17, L["eye"] + 0.10 * H),
                      (0.22, sides), (0.30, lerp(sides, back, 0.5)), (0.40, back), (0.50, back)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return True
        return uu > 0.15 and p.y > rim(u) + 0.0045 * S
    skeleton(C)
    build_head(C, cull)

    def thick(u, y):
        uu = mirror_u(u)
        return (0.0036 + 0.0012 * smoothstep(L["eye"], L["top"], y) + 0.0006 * smoothstep(0.15, 0.40, uu)) * S

    def curls(u, y):                                  # short golden curls: rows of round bumps
        rh = 0.0046 * S; row = math.floor((y - L["chin"]) / rh)
        return 0.0024 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 28 + 0.5 * (row % 2)))) - 0.15)
    hair_shell(C, rim, thick, "hair", "hair", plumb=lambda uu: smoothstep(0.30, 0.42, uu) * 0.5, tuck_front=0.15,
               grooves=0, groove_amp=0.0, curls=curls, NU=30, NV=7, top_extra=0.0005)
    # ---- long white robe to the feet, high round neck, long sleeves
    hemT = 0.016 * k
    RT = cut_rows(scale_rows(KING_ROBE, k, kx), hemT)
    sleeve = [(0.004, 0.0124), (0.014, 0.0120), (0.030, 0.0112), (0.046, 0.0108), (0.060, 0.0108), (0.072, 0.0114),
              (0.082, 0.0122), (0.090, 0.0130), (0.095, 0.0134)]
    build_robe(C, RT, sleeve, None, nf=14, fold_amp=0.0014, sleeve_fold=0.0008, bell_sag=0.0008 * S, reg="robe",
               name="robe", N=36, step=0.0078)
    C.tunic_rows = C.robe_rows
    top_y = C.robe_rows[0][0]
    cgc = Cage(); wc = C.w(["chest", "neck"])
    ring = [shell_point(C.robe_rows, top_y - 0.0012 * S, 2 * math.pi * j / 24, 0.0006 * S) for j in range(24)]
    ring.append(ring[0])
    tube(cgc, ring, [(0.0013 * S, 0.0011 * S)] * len(ring), 6, wc, "robe", 0, ref=V(0, 1, 0), cap0=False, cap1=False)
    C.add("collar", cgc, subdiv=0, piece_as="robe")
    for side in "LR":
        build_forearm_hand(C, side, 0.046 * S)
        build_leg(C, side, 0.0, "skin")                 # bare feet
    # ---- broad gold sash, one end hanging at his right hip (sash1)
    bw = wy - 0.004 * S
    wrap_band(C, "sashA", "sash", bw - 0.0158 * S, bw + 0.0132 * S, 0.0016, 0.0014, 0.0005, 1.5, phase=0.6, NA=48)
    hanging_end(C, "sashEnd", "sash", -0.0150 * S, bw - 0.006 * S, bw - 0.080 * S, 0.0060, "sash1", off=0.0040)
    C.parts[-1]["piece_as"] = "sashA"
    C.parts[-2]["piece_as"] = "sashA"
    # ---- wings: wing*1 (inner half, from the chest at the shoulder blade) -> wing*2 (outer half)
    for side in "LR":
        sd = 1 if side == "L" else -1
        r0 = V(sd * 0.020, 0.292, WING_Z0 + 0.004)
        m = V(sd * 0.080, 0.330, WING_Z0 - WING_SLOPE * 0.060)
        t = V(sd * 0.137, 0.390, WING_Z0 - WING_SLOPE * 0.117)
        C.B[f"wing{side}1"] = (r0, m, "chest")
        C.B[f"wing{side}2"] = (m.copy(), t, f"wing{side}1")
        build_wing(C, side)


# =============================================================================================== thomas
def build_thomas(C):
    """The Miracles friend body (unchanged) + Thomas's costume: square beard, rust head band, short grey-brown cloak over
    both shoulders (cloak1). The friend belt end is dropped (no bone of its own)."""
    _MI["build_friend"](C)
    s = C.s; L = C.L; H = C.H; S = C.S
    hipY, wy, chestY, nb = s["hipY"], s["waistY"], s["chestY"], s["neckBase"]
    # square beard: flat bottom straight across, full sides (kit build_beard, hair region)
    top = [(0.00, L["mouth"] - 0.085 * H), (0.035, L["mouth"] - 0.07 * H), (0.07, L["mouth"] + 0.0 * H),
           (0.10, L["nose"] - 0.06 * H), (0.15, L["nose"] - 0.01 * H), (0.20, L["eye"] - 0.16 * H), (0.245, L["eye"] - 0.04 * H)]
    bot = [(0.00, L["chin"] - 0.13 * H), (0.08, L["chin"] - 0.13 * H), (0.13, L["chin"] - 0.11 * H),
           (0.17, L["chin"] - 0.02 * H), (0.21, L["mouth"] - 0.05 * H), (0.245, L["nose"] - 0.06 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0046, 0.0034, smoothstep(0.05, 0.24, uu)) * S * smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S
    build_beard(C, top, bot, bthick, lambda u, y: 0.0004 * S * math.cos(2 * math.pi * u * 20), 0.245,
                L["chin"] - 0.13 * H, reg="hair", NU=9, NV=5)
    C.parts[-1]["piece_as"] = "beard"
    moustache(C, "moustache", L["mouth"] + 0.092 * H, 0.58 * s["hw"], 0.04 * H, 0.0, 0.0018 * S, reg="hair", off=0.0016)
    C.parts[-1]["piece_as"] = "beard"
    _rename_bone(C, "belt1", "hips")
    C.parts = [p for p in C.parts if p["name"] != "beltEnd"]
    # head band round the hair (no tail)
    cg = Cage(); wfn = C.w(["head"])
    cbh = L["brow"] + 0.30 * H
    path = []
    for i in range(24):
        u = i / 24; uu = mirror_u(u)
        y = lerp(cbh - 0.050 * H, L["eye"] + 0.20 * H, smoothstep(0.0, 0.5, uu) ** 0.9)
        ph, n = hair_pt(C, u, y, 0.0014 * S)
        path.append(ph)
    twisted_ring(cg, path, 0.0032 * S, 0.0014 * S, wfn, "band", 0, N=5, twist=0.0, ref=V(0, 1, 0))
    C.add("band", cg, subdiv=0)
    # short cloak over both shoulders: round the back, the front edges falling to the chest; lower back on cloak1
    shY = s["shoulder"][1]
    p_top = shell_point(C.tunic_rows, nb - 0.008 * S, math.pi, 0.004 * S)
    p_bot = shell_point(C.tunic_rows, wy + 0.004 * S, math.pi, 0.005 * S)
    C.B["cloak1"] = (p_top, p_bot, "chest")
    wtop = C.w(["chest", "shoulderL", "shoulderR", "spine"]); wcl = C.w(["cloak1"], blend=0.012 * S)

    def wfn2(p):
        t = smoothstep(chestY + 0.004 * S, chestY - 0.024 * S, p.y) * smoothstep(-0.2, -0.6, math.cos(math.atan2(p.x, p.z)))
        return mixw((wtop(p), 1 - t), (wcl(p), t)) if t > 0 else wtop(p)
    cols = [0.62 + (2 * math.pi - 1.24) * i / 11 for i in range(12)]

    def ybot(a):
        f = smoothstep(0.30, -0.80, math.cos(a))        # 0 at the front edges, 1 at the back
        return lerp(chestY - 0.012 * S, wy - 0.002 * S, f)

    def ytop(a):
        return nb - 0.0015 * S

    def off(a, v):
        return (0.0034 + 0.0018 * (1 - v)) * S
    _shell_panel(C, "cloak", lambda i: "cloak", cols, ybot, ytop, off, wfn2, NV=4, solid=0.0011, subdiv=0)


BUILDERS = {"jesus": build_jesus_rs, "peter": build_peter_rs, "john": _LS["build_extra"], "thomas": build_thomas,
            "mary": build_woman, "joanna": build_woman, "angel": build_angel}


# =============================================================================================== modes
def mode_build():
    """The printed cast (the King Who Serves mode_build, generic for humans), then the extras in a fresh Blender."""
    os.environ["LS_NO_EXTRAS"] = "1"
    _LS["mode_build"]()
    rp = os.path.join(MODEL, "regions_characters.json")
    rj = json.load(open(rp))
    rj["generatedBy"] = "pipeline/rs_characters.py"
    rj["note"] = ("Per character: colourable regions (face attribute st_region), the mesh parts that carry them, demo "
                  "colour, bbox on the sheet (x, y in art units, y up from the art rect bottom), and anchors (regions "
                  "too small to colour, or with a fixed colour, take a constant UV inside a larger region and print as "
                  "detail lines). ID render for the line art: id_characters_2x.png/.json. Jesus is the Real Miracles "
                  "design (pipeline/mi_characters.py build_jesus, unchanged) plus the fish. The angel's height is the "
                  "top of the head (wing tops: wingTop). The four extras are not printed (offSheet).")
    if "angel" in rj["characters"]:
        rj["characters"]["angel"]["wingTop"] = WING_TOP
        rj["characters"]["angel"]["wings"] = {"bones": {b: EXTRA_PARENTS[b] for b in WING_BONES},
                                              "note": "wing*1 = inner half (from chest), wing*2 = outer half; rest = "
                                                      "folded half-open (sheet pose); rotate wing*2 about its head to "
                                                      "fold the outer half behind the inner one"}
    json.dump(rj, open(rp, "w"), indent=1, ensure_ascii=False)
    import subprocess
    subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "--python-exit-code", "1", "--python", RS_FILE,
                    "--", "extras"], check=True)


def friend_paint_material():
    """rs_extras_paint: Principled BSDF with model/extras_paint.png on UV0 (embedded in the extras' GLBs)."""
    m = bpy.data.materials.get("rs_extras_paint") or bpy.data.materials.new("rs_extras_paint")
    m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.8
    img = bpy.data.images.load(EXTRAS_PAINT, check_existing=True)
    t = nt.nodes.get("paint") or nt.nodes.new("ShaderNodeTexImage"); t.name = "paint"; t.image = img
    uvn = nt.nodes.get("uv0") or nt.nodes.new("ShaderNodeUVMap"); uvn.name = "uv0"; uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


EXTRA_LOOK = {"peter": "the Real Miracles Peter, unchanged (rust-red tunic, sand vest, dark-brown waist cloth, blue-grey "
                       "head cloth, curly black hair and beard); bucket bone kept, no mesh",
              "john": "The King Who Serves John, unchanged: beardless, short wavy light-brown hair, sky-blue tunic, white "
                      "sash (sash1)",
              "thomas": "square beard, straight dark hair, rust head band, teal tunic, tan belt, short grey-brown cloak "
                        "over both shoulders (cloak1)",
              "joanna": "Mary's body (build_woman), rounder: mustard dress, brick-red veil (veil1), cream apron-sash "
                        "(sash1), grey-streaked hair; jar (handL, hidden)"}


def mode_extras():
    """The four extras: built on a virtual page (EXTRA_PAGE), front ID render (props shown, so Joanna's jar gets a
    colour) -> painted texture model/extras_paint.png, UV0 remapped into that texture, GLBs, then appended to
    characters.blend (rigs at EXTRA_BLEND, off the page)."""
    global ONLY
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ONLY = list(EXTRAS)
    SHEET.update({f: list(EXTRA_PAGE[f]) for f in EXTRAS})
    built = {}
    for ch in EXTRAS:
        C, rig, body, props, rep = build_character(ch)
        built[ch] = (C, rig, body, props)
        print(f"[{ch}] tris={tri_count([body] + props)} body={tri_count([body])}")
    ids = id_render("extras_id_2x", hide_props=False)
    idp = os.path.join(WORK, "extras_id_2x.png")
    tex = region_texels(idp, ids)
    x0, y0, cw, chh, W, H = make_friend_paint(idp, ids)
    for o in all_meshes():
        uv0 = o.data.uv_layers["UVMap"]
        a = [0.0] * (2 * len(uv0.data)); uv0.data.foreach_get("uv", a)
        for i in range(0, len(a), 2):
            a[i] = (a[i] * W - x0) / cw; a[i + 1] = (a[i + 1] * H - y0) / chh
        uv0.data.foreach_set("uv", a)
    mat = friend_paint_material()
    for o in all_meshes():
        me = o.data; me.materials.clear(); me.materials.append(mat)
        me.polygons.foreach_set("material_index", [0] * len(me.polygons))
        assert [u.name for u in me.uv_layers][:2] == ["UVMap", "decal"], o.name
        me.uv_layers.active_index = 0; me.uv_layers["UVMap"].active_render = True
    info = {}
    for ch in EXTRAS:
        C, rig, body, props = built[ch]
        rig.location = (0, 0, 0); bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
        for o in rig.children: o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"), use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=False, export_def_bones=False,
                                  export_texcoords=True, export_materials='EXPORT', export_morph=False,
                                  export_image_format='AUTO')
        rig.location = (EXTRA_BLEND[ch][0], 0, EXTRA_BLEND[ch][1])
        info[ch] = {"height": CONTRACT_HEIGHT[ch], "paint": "assets/risen/model/extras_paint.png",
                    "uv0": "paint texture", "look": EXTRA_LOOK[ch], "blendRigLocation": list(EXTRA_BLEND[ch]),
                    "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                                  "swatches": {k_: [round(x, 3) for x in v] for k_, v in SWATCHES.get(ch, {}).items()},
                                  "files": {e: os.path.relpath(face_file(ch, e), ROOT) for e in EXPRESSIONS[ch]},
                                  "clipExpression": CLIP_EXPRESSION[ch]},
                    "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                              "closed": C.lid["closedScale"]},
                    "extraBones": {b: EXTRA_PARENTS[b] for b in EXTRA_BONES[ch]},
                    "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                              for b, v in PROPS[ch].items()},
                    "colours": PALETTE[ch], "tris": tri_count([body] + props)}
    bpy.context.view_layer.update()
    tmp = os.path.join(WORK, "extras.blend")
    sc()[REGIONS_KEY + "_extras"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True)
    rp = os.path.join(MODEL, "regions_characters.json")
    if os.path.exists(rp):
        rj = json.load(open(rp)); rj["offSheet"] = info
        rj["offSheetNote"] = ("the four extras: not printed; UV0 samples model/extras_paint.png (fixed demo-palette paint, "
                              "one flat colour per region), face decal on UV1 like the cast")
        json.dump(rj, open(rp, "w"), indent=1, ensure_ascii=False)
    if os.path.exists(BLEND):
        bpy.ops.wm.open_mainfile(filepath=BLEND)
        for o in [o for o in bpy.data.objects if o.name.startswith(tuple(f + "_" for f in EXTRAS))]:
            bpy.data.objects.remove(o, do_unlink=True)
        with bpy.data.libraries.load(tmp, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith(tuple(f + "_" for f in EXTRAS))]
        for o in dst.objects:
            sc().collection.objects.link(o)
        sc()[REGIONS_KEY + "_extras"] = json.dumps(REGIONS)
        for im in bpy.data.images:                               # no absolute paths in the shared blend
            if os.path.basename(im.filepath) == "extras_paint.png":
                im.filepath = "//extras_paint.png"
                try:
                    im.pack()
                except Exception:                              # noqa: BLE001
                    pass
        bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True, relative_remap=True)
    try:
        os.remove(tmp)
    except OSError:
        pass
    print("EXTRAS_REPORT", json.dumps({ch: {"tris": v["tris"]} for ch, v in info.items()}), json.dumps(tex["regionsNotSeen"]))
    json.dump(PART_TRIS, open(os.path.join(WORK, "extras_parts.json"), "w"), indent=1)


def char_frame(ch):
    L = landmarks(ch); Hh = CONTRACT_HEIGHT[ch] if ch != "angel" else WING_TOP
    return Hh, (L["top"] + L["chin"]) / 2, L["top"] - L["chin"]


def mode_preview():
    _LS["mode_preview"]()


# =============================================================================================== pose tests
def pose_test(rig, ch, variant="a"):
    _LS["pose_test"](rig, ch, variant)
    if ch == "angel" and variant == "b":                 # outer halves folded behind the inner ones, wings drawn in
        for side, sg in (("L", 1), ("R", -1)):
            bend(rig, f"wing{side}1", V(0, 1, 0), -18 * sg)
            bend(rig, f"wing{side}2", V(0, 1, 0), -95 * sg)
    if ch in WOMEN and variant != "none":
        bend(rig, "sash1", V(1, 0, 0), -25)


def _min_y(objs, base_z):
    dg = bpy.context.evaluated_depsgraph_get(); m = 9.0
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        m = min(m, min((o.matrix_world @ v.co).z for v in me.vertices))
        ev.to_mesh_clear()
    return round(m - base_z, 4)


def _eval_pts(o):
    dg = bpy.context.evaluated_depsgraph_get(); ev = o.evaluated_get(dg); me = ev.to_mesh()
    pts = [to_design(o.matrix_world @ v.co) for v in me.vertices]
    ev.to_mesh_clear()
    return pts


def _hips_to(rig, tgt):
    pb = rig.pose.bones["hips"]; rest = pb.bone.matrix_local
    head = to_design(rest.translation)
    pb.matrix_basis = Matrix.Translation(rest.to_3x3().inverted() @ to_bl(tgt - head))
    bpy.context.view_layer.update()


def pose_sit_stone(rig, seat=0.035):
    """The angel sitting on the round stone (a sit_stone fit test, not the clip): hips head at rig-local y = seat over
    base ANGEL_Y, thighs forward level, shins hanging, hands on the stone's top edge beside the hips."""
    pose_reset(rig)
    _hips_to(rig, V(0, seat, 0.0))
    for side, sg in (("L", 1), ("R", -1)):
        pose_rot(rig, "thigh" + side, [(V(1, 0, 0), -86), (V(0, 0, 1), 5 * sg)])
        bend(rig, "shin" + side, V(1, 0, 0), 80)
        pose_rot(rig, "upperArm" + side, [(V(0, 0, 1), -22 * sg), (V(1, 0, 0), 8)])
        bend(rig, "forearm" + side, V(1, 0, 0), -12)
    bpy.context.view_layer.update()


def _reach(rig, side, target):
    """Coarse search of upper-arm (down / forward) and elbow angles that put the fingers' root nearest to target
    (design, rig-local); the elbow folds about the axis normal to the upper arm and the target."""
    sg = 1 if side == "L" else -1
    best = None
    for za in range(-80, 1, 8):
        for xa in range(-80, 1, 8):
            pose_rot(rig, "upperArm" + side, [(V(0, 0, 1), za * sg), (V(1, 0, 0), xa)])
            pb = rig.pose.bones["forearm" + side]
            E = to_design(pb.head); W = to_design(pb.tail)
            u = (W - E).normalized(); tv = (target - E)
            ax = u.cross(tv).normalized()
            ang = math.degrees(u.angle(tv)) if tv.length > 1e-6 else 0.0
            # forearm length to fingers ~ forearm + hand: rotate and measure
            bend(rig, "forearm" + side, ax, ang)
            K = to_design(rig.pose.bones["fingers" + side].head)
            d = (K - target).length
            if best is None or d < best[0]:
                best = (d, za, xa, ax.copy(), ang)
            rig.pose.bones["forearm" + side].matrix_basis = Matrix.Identity(4)
    d, za, xa, ax, ang = best
    pose_rot(rig, "upperArm" + side, [(V(0, 0, 1), za * sg), (V(1, 0, 0), xa)])
    pb = rig.pose.bones["forearm" + side]; E = to_design(pb.head); W = to_design(pb.tail)
    u = (W - E).normalized(); tv = target - E
    bend(rig, "forearm" + side, u.cross(tv).normalized(), math.degrees(u.angle(tv)))
    bpy.context.view_layer.update()
    return round(d, 4)


def _cheek(ch, side, dy=0.0, dz=0.022):
    L = landmarks(ch); hw = SPEC[ch]["hw"]
    return V((1 if side == "L" else -1) * 0.95 * hw, L["nose"] - 0.006 + dy, L["zc"] + dz)


def pose_cry(rig):
    """Mary crying (cry fit test): head down a little, elbows in, the finger roots at the cheeks below the eyes
    (the eyes stay visible, A5)."""
    pose_reset(rig)
    bend(rig, "neck", V(1, 0, 0), 8)
    miss = [_reach(rig, sd, _cheek("mary", sd, -0.012, 0.020)) for sd in "LR"]
    bend(rig, "head", V(1, 0, 0), 10)
    return miss


def pose_joy(rig):
    """Mary at the end of turn_joy: looks up, both hands at the cheeks (the face open), a big smile (decal joy)."""
    pose_reset(rig)
    miss = [_reach(rig, sd, _cheek("mary", sd, -0.010, 0.016)) for sd in "LR"]
    bend(rig, "head", V(1, 0, 0), -10)
    return miss


def pose_stoop(rig):
    """Peter ducking into the tomb door (stoop_look fit test): knees bent, spine and chest forward, head forward and
    turned a little; the top of him must pass under the door top 0.34 at 0.08 in front."""
    pose_reset(rig)
    s = SPEC["peter"]
    _hips_to(rig, V(0, s["hipY"] - 0.030, -0.012))
    for side in "LR":
        bend(rig, "thigh" + side, V(1, 0, 0), -38); bend(rig, "shin" + side, V(1, 0, 0), 52)
        bend(rig, "foot" + side, V(1, 0, 0), -14)
    bend(rig, "spine", V(1, 0, 0), 30); bend(rig, "chest", V(1, 0, 0), 18); bend(rig, "neck", V(1, 0, 0), 6)
    bend(rig, "head", V(0, 1, 0), 15)
    for side, sg in (("L", 1), ("R", -1)):
        pose_rot(rig, "upperArm" + side, [(V(1, 0, 0), -35), (V(0, 0, 1), 6 * sg)])
        bend(rig, "forearm" + side, V(1, 0, 0), -30)
    bpy.context.view_layer.update()


def _stand_in(name, verts_fn):
    o = verts_fn()
    o.name = name
    return o


def _cyl_x(name, centre, r, depth):
    """A disc standing on its edge facing +Z (design), for the stone stand-in."""
    bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=r, depth=depth, location=to_bl(centre),
                                        rotation=(0.0, 0.0, 0.0))
    o = bpy.context.active_object; o.name = name
    o.rotation_euler = (math.radians(90), 0, 0)              # Blender Z axis -> design Z (toward the viewer)
    return o


def _box(name, c, size):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=to_bl(c))
    o = bpy.context.active_object; o.name = name
    o.scale = (size[0], size[2], size[1])
    return o


def _grey(o, rgb=(0.72, 0.66, 0.60)):
    m = bpy.data.materials.new(o.name + "_m"); m.use_nodes = True
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (*rgb, 1)
    o.data.materials.clear(); o.data.materials.append(m)


C_LID_CLOSED = {}


def mode_posetest():
    imgs = preview_setup()
    cam = camera()
    present = [ch for ch in CHARS + EXTRAS if bpy.data.objects.get(f"{ch}_rig")]
    try:
        rj = json.load(open(os.path.join(MODEL, "regions_characters.json")))
        for ch in present:
            src = rj["characters"].get(ch) or rj.get("offSheet", {}).get(ch)
            C_LID_CLOSED[ch] = src["blink"]["closed"]
    except Exception:                                           # noqa: BLE001
        pass
    out = {}
    for ch in present:
        rig = bpy.data.objects[f"{ch}_rig"]
        show([ch])
        Hh = char_frame(ch)[0]
        for var in ("a", "b"):
            pose_test(rig, ch, var)
            sc().render.resolution_x, sc().render.resolution_y = 640, 960
            yaw = (20 if var == "a" else 70) if ch != "angel" else (20 if var == "a" else 160)
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), yaw, Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pose_{ch}_{var}.png"))
        sc().render.resolution_x, sc().render.resolution_y = 540, 540
        Hh, hy0, Hd = char_frame(ch)
        pose_test(rig, ch, "b")
        turntable(cam, Vector((rig.location.x, 0, rig.location.z + hy0)), 25, Hd * 4.2, Hd * 0.1, 60)
        render(os.path.join(WORK, f"pose_{ch}_closed.png"))
        pose_test(rig, ch, "none")
    sc().render.resolution_x, sc().render.resolution_y = 960, 720
    # ---- the angel on the stone (stand-in stone + rock face, or garden.glb when the Set role has written it)
    if "angel" in present:
        ag = bpy.data.objects["angel_rig"]; keep = ag.location.copy()
        sx, sz = STONE_ASIDE
        stone = _cyl_x("standin_stone", V(sx, 0.11, sz), 0.11, 0.05); _grey(stone)
        rock = _box("standin_rock", V(sx, 0.22, -0.35), (0.40, 0.44, 0.10)); _grey(rock, (0.79, 0.58, 0.42))
        seat_z = sz + 0.022                                      # on the front half of the flat top (0.06 wide)
        ag.location = to_bl(V(sx, ANGEL_Y, seat_z))
        show(["angel"])
        stone.hide_render = False; rock.hide_render = False
        body = bpy.data.objects["angel_body"]

        def low_over_stone():
            pts_ = _eval_pts(body)
            near_ = [p for p in pts_ if abs(p.x - sx) < 0.04 and -0.31 < p.z < -0.255 and p.y > 0.15]
            return (min(p.y for p in near_) if near_ else None), pts_
        seat = 0.035
        for _ in range(3):                                       # settle the seat on the stone top (0.22)
            pose_sit_stone(ag, seat)
            lo, pts = low_over_stone()
            if lo is None:
                break
            seat += 0.2205 - lo
        vg = {g.index: g.name for g in body.vertex_groups}
        wingv = [i for i, v in enumerate(body.data.vertices) if any(vg[g.group].startswith("wing") and g.weight > 0.5
                                                                    for g in v.groups)]
        swing = 0
        while swing < 60 and min(pts[i].z for i in wingv) < -0.296:   # swing the wings forward until clear of the rock
            swing += 4
            pose_sit_stone(ag, seat)
            for side, sg in (("L", 1), ("R", -1)):
                bend(ag, f"wing{side}1", V(0, 1, 0), -swing * sg)
            pts = _eval_pts(body)
        lo, _ = low_over_stone()
        info = {"seatZ": round(seat_z, 4), "hipsHeadRigLocalY": round(seat, 4), "hipsHeadWorldY": round(ANGEL_Y + seat, 4),
                "lowestOverStone": round(lo, 4) if lo else None, "minY": round(min(p.y for p in pts), 4),
                "wingSwingForwardDeg": swing, "wingBackZ": round(min(pts[i].z for i in wingv), 4),
                "rockFaceZ": -0.30, "legsFrontZ": round(max(p.z for p in pts if p.y < 0.15), 4)}
        out["angelSeat"] = info
        tgt = Vector((sx, -sz, 0.20))
        for vw, yaw, dist, h in (("angel_side", 90, 1.15, 0.10), ("angel_front", 0, 1.15, 0.14),
                                 ("angel_phone", 12, 1.30, 0.95)):
            turntable(cam, tgt, yaw, dist, h, 60); render(os.path.join(WORK, f"fit_{vw}.png"))
        stone.hide_render = True; rock.hide_render = True
        pose_reset(ag); ag.location = keep
        for side, sg in (("L", 1), ("R", -1)):              # wings_open peak: spread wide
            bend(ag, f"wing{side}1", V(0, 0, 1), 30 * sg); bend(ag, f"wing{side}1", V(0, 1, 0), 25 * sg)
            bend(ag, f"wing{side}2", V(0, 0, 1), 18 * sg)
        turntable(cam, Vector((ag.location.x, 0, 0.24)), 0, 1.4, 0.15, 60); render(os.path.join(WORK, "fit_angel_open.png"))
        pose_reset(ag)
        pose_test(ag, "angel", "b"); ag.pose.bones["eyelids"].scale = (1, 1, 1); bpy.context.view_layer.update()
        turntable(cam, Vector((ag.location.x, 0, 0.24)), 160, 1.2, 0.20, 60); render(os.path.join(WORK, "fit_angel_fold.png"))
        pose_reset(ag)
    # ---- Mary crying and joyful
    if "mary" in present:
        mr = bpy.data.objects["mary_rig"]
        show(["mary"])
        mr.location = to_bl(V(0.32, 0, 0.015)); bpy.context.view_layer.update()
        miss = {}
        for nm, fn, ex in (("mary_cry", pose_cry, "cry"), ("mary_joy", pose_joy, "joy")):
            miss[nm] = fn(mr)
            set_decal("mary", bpy.data.images.load(face_file("mary", ex), check_existing=True))
            turntable(cam, Vector((mr.location.x, 0, mr.location.z + 0.25)), 15, 0.55, 0.05, 60)
            render(os.path.join(WORK, f"fit_{nm}.png"))
        out["maryHands"] = {"fingerRootToCheekMiss": miss, "note": "the eyes stay visible; judged from the render"}
        pose_reset(mr); set_decal("mary", imgs["mary"])
        show(["mary"], props=True)
        turntable(cam, Vector((mr.location.x, 0, mr.location.z + 0.16)), 30, 0.95, 0.20, 60)
        render(os.path.join(WORK, "fit_mary_jar.png"))
    # ---- Peter stooping into the door
    if "peter" in present:
        pt_ = bpy.data.objects["peter_rig"]; keep = pt_.location.copy()
        pt_.location = to_bl(V(2.0, 0, 0)); bpy.context.view_layer.update()
        show(["peter"])
        door_z = -0.08
        lin = _box("standin_lintel", V(2.0, 0.37, door_z - 0.03), (0.30, 0.06, 0.04)); _grey(lin, (0.79, 0.58, 0.42))
        jl = _box("standin_jambL", V(2.0 - 0.10, 0.17, door_z - 0.03), (0.07, 0.34, 0.04)); _grey(jl, (0.79, 0.58, 0.42))
        jr = _box("standin_jambR", V(2.0 + 0.10, 0.17, door_z - 0.03), (0.07, 0.34, 0.04)); _grey(jr, (0.79, 0.58, 0.42))
        pt_.rotation_euler = (0, 0, math.radians(180))         # facing -Z (into the door), as in the scene
        pose_stoop(pt_)
        pts = _eval_pts(bpy.data.objects["peter_body"])
        top_all = max(p.y for p in pts)
        at_door = [p.y for p in pts if p.z < door_z + 0.01]
        out["peterStoop"] = {"top": round(top_all, 4), "topBeyondDoorPlane": round(max(at_door), 4) if at_door else None,
                             "doorTop": 0.34, "frontmostZ": round(min(p.z for p in pts), 4)}
        turntable(cam, Vector((2.0, 0.04, 0.20)), 90, 1.2, 0.08, 60); render(os.path.join(WORK, "fit_peter_stoop.png"))
        turntable(cam, Vector((2.0, 0.04, 0.20)), 0, 1.2, 0.10, 60); render(os.path.join(WORK, "fit_peter_stoop_front.png"))
        for o in (lin, jl, jr):
            bpy.data.objects.remove(o, do_unlink=True)
        pose_reset(pt_); pt_.location = keep; pt_.rotation_euler = (0, 0, 0)
    # ---- props shown, the hold_hands spacing
    if "jesus" in present:
        js = bpy.data.objects["jesus_rig"]
        show(["jesus"], props=True)
        turntable(cam, Vector((js.location.x, 0, js.location.z + 0.16)), 30, 0.95, 0.20, 60)
        render(os.path.join(WORK, "fit_jesus_fish.png"))
        if "mary" in present:
            mr = bpy.data.objects["mary_rig"]; kj, km = js.location.copy(), mr.location.copy()
            js.location = to_bl(V(3.0, 0, 0.055)); js.rotation_euler = (0, 0, math.radians(180))
            mr.location = to_bl(V(3.0, 0, -0.055))
            for rig_, sg_ in ((js, 1), (mr, 1)):
                pose_reset(rig_)
                for side, sg in (("L", 1), ("R", -1)):
                    pose_rot(rig_, "upperArm" + side, [(V(0, 0, 1), -25 * sg), (V(1, 0, 0), -45)])
                    bend(rig_, "forearm" + side, V(1, 0, 0), -40)
            show(["jesus", "mary"])
            turntable(cam, Vector((3.0, 0, 0.20)), 90, 1.0, 0.15, 60); render(os.path.join(WORK, "fit_pair_hands.png"))
            pose_reset(js); pose_reset(mr); js.location = kj; mr.location = km; js.rotation_euler = (0, 0, 0)
    json.dump(out, open(os.path.join(WORK, "posetest.json"), "w"), indent=1)
    print("POSETEST done", json.dumps(out))


def mode_uvcheck():
    _LS["mode_uvcheck"]()


def mode_verify():
    """The King Who Serves verify (bones, parents, budget, heights), then the angel: height = the body without the
    wings (wing tops reported as wingTop)."""
    _LS["mode_verify"]()
    vp = os.path.join(WORK, "verify.json"); v = json.load(open(vp))
    p = os.path.join(MODEL, "angel.glb")
    if os.path.exists(p) and "angel" in v:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=p)
        body = [o for o in sc().objects if o.type == 'MESH' and o.name.startswith("angel_body")][0]
        vg = {g.index: g.name for g in body.vertex_groups}
        top = 0.0; wtop = 0.0
        for vt in body.data.vertices:
            z = (body.matrix_world @ vt.co).z
            if any(vg[g.group].startswith("wing") and g.weight > 0.01 for g in vt.groups):
                wtop = max(wtop, z)
            else:
                top = max(top, z)
        v["angel"]["heightTop"] = round(top, 4); v["angel"]["wingTop"] = round(wtop, 4)
        v["angel"]["heightErrPct"] = round(100 * (top - CONTRACT_HEIGHT["angel"]) / CONTRACT_HEIGHT["angel"], 2)
        v["angel"]["wingTopErrPct"] = round(100 * (wtop - WING_TOP) / WING_TOP, 2)
        json.dump(v, open(vp, "w"), indent=1)
    print("VERIFY", json.dumps({c: {k_: x for k_, x in i.items() if k_ not in ("meshes", "parents")} for c, i in v.items()}))


if __name__ == "__main__":
    {"build": mode_build, "extras": mode_extras, "preview": mode_preview, "posetest": mode_posetest,
     "verify": mode_verify, "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), RS_FILE, "all"],
                                                 check=True)}[argv[0] if argv else "build"]()
