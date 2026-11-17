"""The King Who Serves (story pack `lastsupper`): characters donkey, jesus, peter (+ john, james, andrew, seller1,
seller2, not on the sheet) — meshes, rigs, weights, UVs, face decals, previews, GLBs.

Contract: docs/lastsupper/CONTRACT.md §1-§4 (ids, sizes, sheet slots, bone names, props), look: docs/lastsupper/DESIGN.md
§1 and §3, notes for Animation: docs/lastsupper/RIG.md.

Jesus and Peter are the Real Miracles designs. This script does NOT copy them: it runs pipeline/mi_characters.py in its
own namespace (definitions only, the way story_kit.include works; `_run_miracles` below) and calls `build_jesus` /
`build_peter` unchanged, then adds this pack's props:
  * jesus: `towel` (hips), `basin` (root, on the floor 0.06 in front), `bread` (handL), `cup` (handR), all hidden;
  * peter: `palm` (handR, shown), `towel` (chest, over the left shoulder), `jug` (handR), the last two hidden; the
    Miracles `bucket` bone stays, its mesh is dropped (CONTRACT §3).
The Miracles face drawings are reused: the decals that already exist are copied from docs/miracles/design/faces/; the
new ones are drawn with the Miracles drawing code (`draw_faces`, patched at four marked places in memory so it can draw
new expressions; mi_characters.py itself is never edited).
New here:
  * the donkey: a young, small, round donkey on all fours (Daniel's lion skeleton with donkey ears and a short tail),
    big head, long upright ears with dark tips, cream muzzle and belly, a brush mane, a red saddle blanket with a gold
    stripe (seat y 0.155 at the root); printed in SIDE view (its left side, nose to -X): UV0 = mirrored side
    projection, faces not seen from the side take a clean texel of their own region (Daniel / Jonah method); face decal
    = front projection on the head (as Daniel's lion), eyelids on the frontmost head surface over their whole travel;
  * john, james, andrew, seller1, seller2: the Miracles fixed-paint friend body (`build_friend`, unchanged) with this
    pack's costume parts (beards, James's cloak, Andrew's head cloth, the dove seller's striped apron, the money
    changer's pouch and cap); their own front ID render on a virtual page becomes model/extras_paint.png (Esther's
    GUARDS method); one set of face drawings per group (disciples, sellers), re-coloured brows per person.

Run (repo root):
  python3 pipeline/ls_characters.py all                                           # everything below, in order
  python3 pipeline/ls_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python-exit-code 1 --python pipeline/ls_characters.py -- build    # cast + extras
  blender ... -- extras        # the five extras only (run by build)
  python3 pipeline/ls_characters.py proof                                         # $LS_WORK/uvproof.png
  blender ... -- preview       # lit demo-palette renders
  blender ... -- uvcheck       # models wearing uvproof.png
  blender ... -- posetest      # bend / blink / jaw / cloth, the ride fit (Jesus on the donkey), the kneel with the basin
  blender ... -- verify        # re-import GLBs, check bones / parents / budget / heights / seat
  python3 pipeline/ls_characters.py compose                                       # preview_*.png contact sheets
Blender: $BLENDER, else `blender` on PATH, else /Applications/Blender.app. Intermediate renders go to $LS_WORK
(default /tmp/lastsupper_chars/work). LS_ONLY=donkey (comma list) builds a subset of the cast (debug only).
"""
import sys, os, json, math, random, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
LS_WORK = os.environ.get("LS_WORK", "/tmp/lastsupper_chars/work")
os.environ["MI_WORK"] = LS_WORK          # the Miracles module creates its WORK folder at import: keep it in our scratch
MI_PATH = os.path.join(HERE, "mi_characters.py")
MI_FACES = os.path.join(ROOT, "docs/miracles/design/faces")
MI_SRC = open(MI_PATH, encoding="utf-8").read()


def _run_miracles():
    """Run pipeline/mi_characters.py in this module's namespace: every Miracles definition (builders, constants, the
    shared kit it includes) becomes ours, exactly as story_kit.include does for the kit. Its mode dispatch only runs
    under __main__, so nothing is built; outside Blender it stops with SystemExit after the Pillow part (caught)."""
    g = globals()
    keep = {k: g.get(k) for k in ("__name__", "__file__", "__doc__")}
    g["__name__"] = "mi_characters"; g["__file__"] = MI_PATH
    try:
        exec(compile(MI_SRC, MI_PATH, "exec"), g)
    except SystemExit:
        pass
    finally:
        g.update(keep)


_run_miracles()
_MI = {k: globals()[k] for k in ("build_jesus", "build_peter", "build_friend", "build_character", "eyelid_cage",
                                 "pose_test", "Ctx", "face_layout", "PALETTE", "SWATCHES", "ANCHORS", "PART_ANCHORS",
                                 "EXPRESSIONS", "SPEC", "EYE")
       if k in globals()}

# ---------------------------------------------------------------------------------------------- this pack
MODEL = os.path.join(ROOT, "assets/lastsupper/model")
FACES = os.path.join(ROOT, "docs/lastsupper/design/faces")
WORK = LS_WORK
ENV = "LS_"
PAGE_MATERIAL = "ls_page"
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/lastsupper/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

CHARS = ("donkey", "jesus", "peter")                 # printed cast, sheet order left -> right
DISCIPLES = ("john", "james", "andrew")
SELLERS = ("seller1", "seller2")
EXTRAS = DISCIPLES + SELLERS
FRIENDS = EXTRAS                    # the Miracles helpers call the fixed-paint people FRIENDS
QUADS = ("donkey",)
FISH = ()
HUMANS = CHARS + EXTRAS             # the Miracles preview helpers iterate HUMANS = every rig
DONKEY_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw", "eyelids", "earL", "earR", "tail1", "tail2",
                "upperArmL", "forearmL", "pawL", "upperArmR", "forearmR", "pawR",
                "thighL", "shinL", "footL", "thighR", "shinR", "footR"]
EXTRA_BONES = {"jesus": ["mantle1", "belt1", "towel", "basin", "bread", "cup"],
               "peter": ["cloth1", "bucket", "palm", "towel", "jug"], "donkey": [],
               "john": ["sash1"], "james": ["cloak1"], "andrew": ["cloth1"], "seller1": ["apron1"], "seller2": ["pouch"]}
EXTRA_PARENTS = {"mantle1": "chest", "belt1": "hips", "towel": None, "basin": "root", "bread": "handL", "cup": "handR",
                 "cloth1": "head", "bucket": "handR", "palm": "handR", "jug": "handR", "sash1": "hips",
                 "cloak1": "chest", "apron1": "hips", "pouch": "hips"}
TOWEL_PARENT = {"jesus": "hips", "peter": "chest"}


def bone_list(ch):
    return (DONKEY_BONES if ch in QUADS else CONTRACT_BONES) + EXTRA_BONES[ch]


PROPS = {"jesus": {"towel": False, "basin": False, "bread": False, "cup": False},
         "peter": {"palm": True, "towel": False, "jug": False}, "donkey": {}}
PROPS.update({e: {} for e in EXTRAS})                                    # prop bone -> shown by default
CONTRACT_HEIGHT = {"donkey": 0.27, "jesus": 0.36, "peter": 0.38,
                   "john": 0.33, "james": 0.36, "andrew": 0.37, "seller1": 0.33, "seller2": 0.35}
DONKEY_SIZE = dict(withers=0.15, earTips=0.27, noseToRump=0.28, tail=0.06, seat=0.155)
BUDGET = {"donkey": 20000, "jesus": 25000, "peter": 25000}
BUDGET.update({e: 18000 for e in EXTRAS})
DEFAULT_SHEET = {"donkey": (-0.32, 0.015), "jesus": (0.0, 0.015), "peter": (0.32, 0.015)}
# the extras: virtual page for their own ID render (two rows: three A-poses at +-0.34 never touch, C2) and rig places
EXTRA_PAGE = {"john": (-0.34, 0.015), "james": (0.0, 0.015), "andrew": (0.34, 0.015),
              "seller1": (-0.17, 0.58), "seller2": (0.17, 0.58)}
EXTRA_BLEND = {"john": (0.80, 0.0), "james": (1.00, 0.0), "andrew": (1.20, 0.0), "seller1": (1.40, 0.0),
               "seller2": (1.60, 0.0)}
FRIEND_PAGE = EXTRA_PAGE; FRIEND_BLEND = EXTRA_BLEND
EXTRAS_PAINT = os.path.join(MODEL, "extras_paint.png")
FRIEND_PAINT = EXTRAS_PAINT          # read by the Miracles preview material
RIDE_Y = 0.12                        # CONTRACT §4: Jesus's base y while riding
UPPER = 0.10

# ---------------------------------------------------------------------------------------------- palette (DESIGN §3)
_TAN = "#D2AE74"; _SANDAL = "#7A4E2E"; _CLAY = "#C46A3E"; _LINEN = "#F5F1E6"
PALETTE = dict(_MI.get("PALETTE", {}))
PALETTE = {"jesus": dict(PALETTE["jesus"], towel=_LINEN, basin=_CLAY, bread="#C98A4A", cup=_CLAY),
           "peter": dict(PALETTE["peter"], palm="#5E9A48", towel=_LINEN, jug=_CLAY),
           "donkey": {"coat": "#9C9A96", "muzzle": "#EFE6D2", "mane": "#3E3A38", "blanket": "#C2453A",
                      "gold": "#D9A93A", "hooves": "#3A3230"},
           "john": {"skin": "#D6A27A", "hair": "#9A6B42", "tunic": "#7FB6E0", "belt": "#F5F1E6", "sandals": _SANDAL},
           "james": {"skin": "#C08A62", "hair": "#1E1814", "tunic": "#6FA552", "belt": _TAN, "sandals": _SANDAL,
                     "cloak": "#7A5236"},
           "andrew": {"skin": "#BF8460", "hair": "#231A16", "tunic": "#D9A93A", "belt": _TAN, "sandals": _SANDAL,
                      "band": "#6E8AA6"},
           "seller1": {"skin": "#D69A78", "hair": "#1E1814", "tunic": "#E8843A", "belt": _TAN, "sandals": _SANDAL,
                       "apron": "#F1E3C4", "stripes": "#8A5A3B"},
           "seller2": {"skin": "#C8946C", "hair": "#2A2018", "tunic": "#7E4A86", "belt": _TAN, "sandals": _SANDAL,
                       "cap": "#9C3A3A", "pouch": "#8A5A3B"}}
REGION_NAMES.update({
    "towel": ("毛巾", "towel"), "basin": ("水盆", "basin"), "bread": ("饼", "bread"), "cup": ("杯", "cup"),
    "palm": ("棕树枝", "palm frond"), "jug": ("水罐", "jug"), "coat": ("毛", "coat"),
    "muzzle": ("嘴鼻和肚皮", "muzzle and belly"), "mane": ("鬃毛", "mane"), "blanket": ("鞍毯", "saddle blanket"),
    "gold": ("金边", "gold stripe"), "hooves": ("蹄", "hooves"), "cloak": ("短披风", "cloak"),
    "apron": ("围裙", "apron"), "stripes": ("条纹", "stripes"), "pouch": ("钱袋", "money pouch"),
    "band": ("头巾", "head cloth")})
# fixed-colour parts: UV1 points at a swatch in a corner of every decal of that character; UV0 anchored (detail lines)
SWATCHES = dict(_MI.get("SWATCHES", {}))
SWATCHES = {"jesus": SWATCHES["jesus"], "peter": SWATCHES["peter"],
            "donkey": {"hooves": (0.905, 0.925, 0.950, 0.995), "gold": (0.955, 0.925, 0.995, 0.995)}}
SWATCH_COL.update({"hooves": (58, 50, 48), "gold": (217, 169, 58)})
ANCHORS = {"jesus": dict(_MI["ANCHORS"]["jesus"]) if "ANCHORS" in _MI else {"sandals": "jesus.tunic"},
           "peter": dict(_MI["ANCHORS"]["peter"]) if "ANCHORS" in _MI else {},
           "donkey": {"hooves": "donkey.coat", "gold": "donkey.blanket"}}
# hidden props are not printed: they sample a printed region (CONTRACT §3; "set.<region>" = the set's drawings)
PROP_ANCHORS = {
    "jesus": {"towel": ["set.cloth", "set.lowTable", "jesus.tunic"], "basin": ["set.clay", "set.basinJug", "set.cupTable", "peter.tunic"],
              "bread": ["set.bread", "set.breadLoaf", "jesus.belt"], "cup": ["set.clay", "set.cupTable", "peter.tunic"]},
    "peter": {"towel": ["set.cloth", "set.lowTable", "jesus.tunic"], "jug": ["set.clay", "set.cupTable", "set.basinJug", "peter.tunic"],
              # the palm is printed with Peter but coloured from the set's palm green (CONTRACT §3)
              "palm": ["set.palmLeaf", "set.palmsRoad", "peter.vest"]},
}
PART_ANCHORS = {"jesus": dict(_MI["PART_ANCHORS"]["jesus"]), "peter": dict(_MI["PART_ANCHORS"]["peter"])} \
    if "PART_ANCHORS" in _MI else {}
PART_ANCHORS["donkey"] = {(p, "coat"): "donkey.coat" for p in ("legFL", "legFR", "legBL", "legBR", "earL", "earR",
                                                              "tail", "neck")}
PART_ANCHORS["donkey"].update({("earL", "mane"): "donkey.mane", ("earR", "mane"): "donkey.mane",
                               ("earL", "muzzle"): "donkey.muzzle", ("earR", "muzzle"): "donkey.muzzle"})

# ---------------------------------------------------------------------------------------------- the extras' bodies
# the Miracles friend body: one head size for all (one set of face drawings per group), k = body length, bodyX = width
FRIEND = {
    "john": dict(k=0.928, bodyX=0.90, belly=0.0, hair="short"),       # the youngest, 0.33, beardless
    "james": dict(k=1.000, bodyX=1.16, belly=0.0, hair="short"),      # broad, short black beard, 0.36
    "andrew": dict(k=1.022, bodyX=0.80, belly=0.0, hair="curly"),     # lanky, neat beard, Peter's head cloth, 0.37
    "seller1": dict(k=0.930, bodyX=1.30, belly=1.0, hair="fringe"),   # round, bald with a fringe, 0.33
    "seller2": dict(k=0.880, bodyX=0.80, belly=0.0, hair="cap"),      # thin, long nose, pointed beard, felt cap, 0.35
}
for _f, _v in FRIEND.items():
    _k = _v["k"]
    _sp = scaled(KING, _k, _k, height=CONTRACT_HEIGHT[_f], **_FHEAD)
    _sp["chin"] = _sp["top"] - _FH; _sp["hw"] = 0.0219
    _sp["shoulder"] = (_sp["shoulder"][0] * _v["bodyX"], _sp["shoulder"][1])
    _sp["hipX"] = _sp["hipX"] * min(1.25, _v["bodyX"])
    if _f == "seller1":
        _sp["handDims"] = {a: x * 1.10 for a, x in _sp["handDims"].items()}
    if _f in ("andrew", "seller2"):                   # lanky: longer arms
        _sp["upperArm"] *= 1.06; _sp["forearm"] *= 1.06
    if _f == "seller2":                               # the long nose (mesh only; the decal keeps the shared layout)
        _sp["nose_long"] = 0.55; _sp["noseH"] *= 1.35; _sp["nose_w"] = 1.05
    SPEC[_f] = _sp
EYE.update({e: (0.405, 0.320, 0.222) for e in EXTRAS})

# ---------------------------------------------------------------------------------------------- expressions
EXPRESSIONS = {"jesus": ["kind", "talk", "smile", "laugh", "firm", "gentle", "look_up", "sad"],
               "peter": ["jolly", "talk", "shock", "laugh", "amazed", "proud", "sheepish", "puzzled"],
               "donkey": ["calm", "happy", "heehaw", "chew", "sleepy"]}
DISCIPLE_EXPRESSIONS = ["happy", "talk", "proud", "amazed", "sheepish", "laugh"]
SELLER_EXPRESSIONS = ["hawk", "talk", "shock", "wail", "fluster"]
EXPRESSIONS.update({e: DISCIPLE_EXPRESSIONS for e in DISCIPLES})
EXPRESSIONS.update({e: SELLER_EXPRESSIONS for e in SELLERS})
NEW_EXPRESSIONS = {"jesus": ["sad"], "peter": ["proud", "sheepish", "puzzled"]}     # the rest is copied from Miracles
DEFAULT_EXPR = {"jesus": "kind", "peter": "jolly", "donkey": "calm"}
DEFAULT_EXPR.update({e: "happy" for e in DISCIPLES}); DEFAULT_EXPR.update({e: "hawk" for e in SELLERS})
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "jesus": {"idle": "kind", "talk": "talk", "walk": "kind", "stand_talk": "talk", "ride": "kind", "ride_wave": "smile",
              "ride_talk": "talk", "sad_look": "sad", "tip_table": "firm", "firm_talk": "firm", "open_cage": "firm",
              "rise_towel": "gentle", "kneel_wash": "gentle", "kneel_talk": "talk", "kneel_laugh": "laugh",
              "sit_supper": "kind", "bless_bread": "look_up", "lift_cup": "gentle", "smile": "smile", "laugh": "laugh",
              "wave": "smile"},
    "peter": {"idle": "jolly", "talk": "talk", "walk": "jolly", "laugh": "laugh", "amazed": "amazed", "cheer": "laugh",
              "listen_stone": "puzzled", "boast": "proud", "argue": "talk", "sit_bench": "jolly", "refuse": "shock",
              "offer_all": "laugh", "sit_wash": "jolly", "ashamed": "sheepish", "sit_supper": "jolly",
              "serve_rise": "jolly", "kneel_serve": "jolly", "wave": "jolly"},
    "donkey": {"idle": "calm", "walk": "calm", "hee_haw": "heehaw", "graze": "chew", "sleepy": "sleepy",
               "happy": "happy"},
}
_DCLIP = {"idle": "happy", "walk": "happy", "talk": "talk", "cheer": "laugh", "boast": "proud", "argue": "talk",
          "laugh": "laugh", "sit_bench": "happy", "sit_wash": "happy", "sit_supper": "happy", "amazed": "amazed",
          "ashamed": "sheepish", "nudge": "laugh", "wave": "happy"}
_SCLIP = {"idle": "hawk", "shout": "talk", "walk": "hawk", "shock": "shock", "chase_coins": "fluster", "flap": "wail"}
CLIP_EXPRESSION.update({e: _DCLIP for e in DISCIPLES}); CLIP_EXPRESSION.update({e: _SCLIP for e in SELLERS})


def face_file(ch, ex):
    return os.path.join(FACES, f"{ch}_{ex}.png")


# ---------------------------------------------------------------------------------------------- the donkey (layout)
# Facing +Z, hooves on y = 0, root on the ground under the belly centre (= under the seat). Body sections rump -> chest:
# (z, y centre, half width, half height), cage values (the subdivided surface sits ~4 % inside).
DK_BODY = [(-0.121, 0.114, 0.012, 0.014), (-0.116, 0.112, 0.026, 0.030), (-0.104, 0.110, 0.034, 0.039),
           (-0.082, 0.108, 0.038, 0.043), (-0.052, 0.106, 0.039, 0.044), (-0.020, 0.106, 0.0385, 0.0445),
           (0.012, 0.107, 0.0385, 0.0445), (0.040, 0.110, 0.037, 0.043), (0.062, 0.115, 0.032, 0.039),
           (0.078, 0.123, 0.024, 0.031), (0.087, 0.131, 0.014, 0.019)]
DK_E = 2.25
DK_HEAD = dict(c=(0.0, 0.200, 0.106), r=(0.031, 0.033, 0.034))
DK_BRIDGE = dict(c=(0.0, 0.188, 0.128), r=(0.022, 0.024, 0.022))
DK_MUZZLE = dict(c=(0.0, 0.171, 0.1385), r=(0.0275, 0.0235, 0.0285))
DK_JAW = dict(c=(0.0, 0.156, 0.129), r=(0.020, 0.011, 0.023))
DK_EYE = dict(x=0.0178, y=0.2045, w=0.0094, h=0.0084)
DK_DECAL = (-0.040, 0.148, 0.080)                       # front rect: x0, y0, size
DK_TAIL = [(0.0, 0.130, -0.114), (0.0, 0.122, -0.128), (0.0, 0.104, -0.140), (0.0, 0.086, -0.150),
           (0.0, 0.072, -0.156)]
DK_BLANKET = dict(z0=-0.052, z1=0.050, theta=100.0, off=0.0045, solid=0.0024)


def donkey_face_layout():
    X0, Y0, w = DK_DECAL
    e = DK_EYE

    def nx(x): return (x - X0) / w

    def ny(y): return (y - Y0) / w
    return dict(rect=[X0, Y0, X0 + w, Y0 + w], eyeL=(nx(e["x"]), ny(e["y"])), eyeR=(nx(-e["x"]), ny(e["y"])),
                eyeHalf=(e["w"] / w, e["h"] / w), brow=ny(e["y"] + 0.0125), mouth=ny(0.1575), nose=ny(0.1755),
                eyeLocal=(e["x"], e["y"], e["w"], e["h"]), hwN=0.031 / w)


def face_layout(ch):
    if ch in QUADS:
        return donkey_face_layout()
    return _MI["face_layout"](ch)


# ---------------------------------------------------------------------------------------------- face drawings
# The Miracles draw_faces, patched in memory at four marked places (asserted, so a change in mi_characters.py fails
# loudly instead of drifting): extra expressions via ls_face_params, the cast list, a hook that draws the donkey with
# the same eye / brow / mouth tools, and the overview labels.
LS_LOOK = {
    "john": dict(bcol=(120, 84, 52, 255), iris=(96, 70, 44), bw=0.050, nose=0.038, blush=0.31),
    "james": dict(bcol=(26, 20, 16, 255), iris=(80, 56, 38), bw=0.064, nose=0.042, blush=0.31),
    "andrew": dict(bcol=(30, 22, 18, 255), iris=(92, 62, 40), bw=0.054, nose=0.040, blush=0.31),
    "seller1": dict(bcol=(30, 22, 18, 255), iris=(92, 62, 40), bw=0.058, nose=0.044, blush=0.30),
    "seller2": dict(bcol=(40, 30, 24, 255), iris=(80, 60, 40), bw=0.046, nose=0.046, blush=0.31),
    "donkey": dict(bcol=(70, 64, 60, 255), iris=(78, 52, 38), bw=0.040, nose=0.040, blush=0.36),
}


def ls_face_params(base):
    """Wrap the Miracles face_params: Jesus `sad`, Peter `proud` / `sheepish` / `puzzled`, the disciples' and the sellers'
    sets (both start from the Miracles friend base look)."""
    def fp(key, ex):
        if key == "jesus" and ex == "sad":
            E, Bp, Bl, Br, M, o = base("jesus", "gentle")
            E.update(top=0.76, bot=0.86, look=(0.0, -0.30))
            Bp.update(inner=0.048, raise_=0.064, arch=0.04, outer=-0.024)
            M.update(kind="flat", wd=0.064); o.update(crow=0, bl=24)
            return E, Bp, Bl, Br, M, o
        if key == "peter" and ex in ("proud", "sheepish", "puzzled"):
            E, Bp, Bl, Br, M, o = base("peter", "talk")
            if ex == "proud":
                E.update(top=0.40, bot=0.70, look=(0.0, 0.30), tilt=0.10); Bp.update(raise_=0.082, arch=0.42)
                M.update(kind="smirk", wd=0.092, side=1.0, jaw=0.0); o.update(bl=130, crow=2)
            elif ex == "sheepish":
                E.update(top=0.80, look=(0.55, -0.70)); Bp.update(inner=0.052, raise_=0.078, arch=0.10, outer=-0.020)
                M.update(kind="wobbly", wd=0.076, jaw=0.02); o.update(bl=190, crow=1)
            else:
                E.update(top=0.98, look=(-0.40, 0.35))
                Bl = dict(inner=-0.030, raise_=0.050, arch=0.08); Br = dict(raise_=0.120, arch=0.62)
                M.update(kind="smirk", wd=0.072, side=-1.0, jaw=0.0); o.update(bl=90, crow=0)
            return E, Bp, Bl, Br, M, o
        if key in EXTRAS:
            E, Bp, Bl, Br, M, o = base("friend", "talk" if ex == "talk" else "happy")
            if key in DISCIPLES:
                if ex == "proud":
                    E.update(top=0.45, bot=0.72, look=(0.0, 0.25), tilt=0.10); Bp.update(raise_=0.080, arch=0.42)
                    M.update(kind="smirk", wd=0.080, side=1.0); o.update(bl=110, crow=1)
                elif ex == "amazed":
                    E.update(top=1.32, bot=1.10, pupil=0.36, lid=0.06, tilt=0.0); Bp.update(raise_=0.120, arch=0.64)
                    M.update(kind="o", wd=0.062, jaw=0.30); o.update(bl=100, crow=0)
                elif ex == "sheepish":
                    E.update(top=0.82, look=(0.50, -0.65)); Bp.update(inner=0.046, raise_=0.074, arch=0.10, outer=-0.020)
                    M.update(kind="wobbly", wd=0.066, jaw=0.02); o.update(bl=170)
                elif ex == "laugh":
                    E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.104, jaw=0.26)
                    o.update(bl=150, crow=2)
            else:
                if ex == "hawk":
                    E.update(top=0.80, bot=0.70, tilt=0.10); Bp.update(raise_=0.086, arch=0.56)
                    M.update(kind="grin", wd=0.112, jaw=0.12); o.update(bl=150, crow=2)
                elif ex == "talk":
                    M.update(wd=0.084)
                elif ex == "shock":
                    E.update(top=1.45, bot=1.25, pupil=0.28, lid=0.04, tilt=0.0)
                    Bp.update(raise_=0.140, arch=0.74, outer=0.020); M.update(kind="shout", wd=0.100, jaw=0.50)
                    o.update(bl=80, crow=0)
                elif ex == "wail":
                    E.update(mode="closed"); Bp.update(inner=0.070, raise_=0.090, arch=0.02, outer=-0.040)
                    M.update(kind="shout", wd=0.098, jaw=0.44); o.update(special=["tears"], bl=140, crs=False)
                elif ex == "fluster":
                    E.update(top=1.10, look=(0.40, 0.10), pupil=0.40, tilt=-0.05)
                    Bp.update(inner=0.055, raise_=0.085, arch=0.05, outer=-0.025)
                    M.update(kind="wobbly", wd=0.080, jaw=0.08); o.update(special=["sweat"], bl=160)
                if key == "seller1":                     # rosy cheeks
                    o["bl"] = min(230, o["bl"] + 70)
            return E, Bp, Bl, Br, M, o
        return base(key, ex)
    return fp


def ls_draw_exprs(ch):
    return NEW_EXPRESSIONS.get(ch, EXPRESSIONS[ch])


def ls_face_base(ch):
    return PALETTE[ch].get("skin") or PALETTE[ch].get("coat")


def ls_overview_cells():
    return [(ch, ex) for ch in ("jesus", "peter", "donkey") + EXTRAS for ex in EXPRESSIONS[ch]]


def ls_face_hook(ch, ex, img, T):
    """The donkey's drawings (front decal on the head): big kind eyes with long lashes, soft brows, two nostrils on the
    muzzle, a mouth line at the jaw. Uses the Miracles drawing tools T. Returns True when it handled (and saved) it."""
    if ch not in QUADS:
        return False
    from PIL import Image, ImageDraw
    F = face_layout(ch); eL, eR, half = F["eyeL"], F["eyeR"], F["eyeHalf"]
    stroke, bez, P = T["stroke"], T["bez"], T["P"]
    lk = LS_LOOK["donkey"]
    T["blush"](img, lk["blush"], F["nose"] + 0.06, 0.080, 0.045, 60 if ex != "happy" else 110)
    eyes = {"calm": dict(top=0.70, bot=0.92, look=(0.0, -0.10), lid=0.30),
            "happy": dict(mode="happy"),
            "heehaw": None,
            "chew": dict(top=0.55, bot=0.90, look=(0.20, -0.95), lid=0.36),
            "sleepy": dict(top=0.24, bot=0.90, look=(0.0, -0.70), lid=0.50)}[ex]
    dr = ImageDraw.Draw(img)
    for side, c in ((1, eL), (-1, eR)):
        if eyes is None:                                  # squeezed shut: > <
            cx, cy = c; ew, eh = half; o = side
            pts = [(cx + o * ew * 0.9, cy + eh * 0.9), (cx - o * ew * 0.7, cy + eh * 0.05), (cx + o * ew * 0.9, cy - eh * 0.8)]
            stroke(dr, bez(pts[0], (cx, cy + eh * 0.6), (cx - o * ew * 0.4, cy + eh * 0.2), pts[1], 20), 0.030, 0.026,
                   wmid=0.034)
            stroke(dr, bez(pts[1], (cx - o * ew * 0.4, cy - eh * 0.2), (cx, cy - eh * 0.5), pts[2], 20), 0.026, 0.020,
                   wmid=0.030)
            for k, a in enumerate((-30, 0, 30)):          # squeeze lines beyond the outer corner
                aa = math.radians(a); x0 = cx + o * ew * 1.35; y0 = cy
                stroke(dr, [(x0, y0 + 0.02 * math.sin(aa)), (x0 + o * 0.045 * math.cos(aa), y0 + 0.05 * math.sin(aa))],
                       0.012, 0.006)
        else:
            T["eye"](img, c, half, side=side, iris=lk["iris"], line=0.024, lash=3, tilt=-0.10, pupil=0.62, **eyes)
        dr = ImageDraw.Draw(img)
        b = dict(raise_=0.060, inner=0.0, arch=0.30, length=0.80, thick=1.0)
        if ex == "heehaw":
            b.update(raise_=0.040, inner=-0.030, arch=0.10)
        elif ex == "happy":
            b.update(raise_=0.080, arch=0.50)
        elif ex == "sleepy":
            b.update(raise_=0.050, inner=0.020, arch=0.12)
        T["brow"](dr, side, (c[0], F["brow"] - 0.015), half, w=lk["bw"], col=lk["bcol"], **b)
    # nostrils on the front of the muzzle
    ny_ = F["nose"]; big = 1.55 if ex == "heehaw" else 1.0
    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
    for sx in (-1, 1):
        x = 0.5 + sx * 0.088; rx, ry = 0.024 * big, 0.036 * big
        dl.ellipse((P(x - rx, ny_ + ry)[0], P(x - rx, ny_ + ry)[1], P(x + rx, ny_ - ry)[0], P(x + rx, ny_ - ry)[1]),
                   fill=(84, 66, 60, 235))
        stroke(dl, bez((x - sx * rx * 1.1, ny_ + ry * 1.25), (x + sx * rx * 0.2, ny_ + ry * 1.6),
                       (x + sx * rx * 1.3, ny_ + ry * 0.8), (x + sx * rx * 1.3, ny_ - ry * 0.4), 16), 0.010, 0.006,
               col=(110, 92, 84, 200))
    img.alpha_composite(lay)
    my = F["mouth"]
    if ex == "heehaw":
        T["mouth"](img, "shout", 0.5, my + 0.10, 0.140, lipcol=None, jaw=0.55)
    elif ex == "chew":
        T["mouth"](img, "smirk", 0.5, my, 0.110, lipcol=None, side=1.0)
    elif ex == "happy":
        T["mouth"](img, "smile", 0.5, my, 0.140, lipcol=None)
    elif ex == "sleepy":
        T["mouth"](img, "flat", 0.5, my, 0.100, lipcol=None)
    else:
        T["mouth"](img, "soft", 0.5, my, 0.130, lipcol=None)
    T["swatches"](img, ch)
    out = img.resize((T["PX"], T["PX"]), Image.LANCZOS)
    out.save(face_file(ch, ex)); T["made"][f"{ch}_{ex}"] = os.path.relpath(face_file(ch, ex), ROOT)
    return True


def _patched_draw_faces_src():
    a = MI_SRC.index("def draw_faces():"); b = MI_SRC.index("\ndef swatch_uv(")
    src = MI_SRC[a:b]
    reps = [
        ("    made = {}\n    LOOK = {", "    face_params = ls_face_params(face_params)\n    made = {}\n    LOOK = {"),
        ('    for ch in ("jesus", "peter", "man", "friend1"):\n        key = "friend" if ch in FRIENDS else ch\n',
         "    LOOK.update(LS_LOOK)\n    for ch in LS_FACE_CHARS:\n        key = ch\n"),
        ("        for ex in EXPRESSIONS[ch]:\n            img = Image.new(\"RGBA\", (N, N), (0, 0, 0, 0))\n",
         "        for ex in ls_draw_exprs(ch):\n            img = Image.new(\"RGBA\", (N, N), (0, 0, 0, 0))\n"
         "            if ls_face_hook(ch, ex, img, dict(eye=eye, brow=brow, mouth=mouth, stroke=stroke, bez=bez, P=P,"
         " poly=poly, soft=soft, blush=blush, swatches=swatches, N=N, PX=PX, made=made)):\n"
         "                continue\n"),
        ('    cells = [(ch, ex) for ch in ("jesus", "peter", "man", "friend1") for ex in EXPRESSIONS[ch]]\n',
         "    cells = ls_overview_cells()\n"),
        ('        base = PALETTE[ch]["skin"]\n', "        base = ls_face_base(ch)\n"),
        ("f\"{'friend' if ch in FRIENDS else ch}_{ex}\"", 'f"{ch}_{ex}"'),
    ]
    for old, new in reps:
        assert src.count(old) == 1, ("mi draw_faces changed; patch anchor not found once:", old[:60])
        src = src.replace(old, new)
    return src


LS_FACE_CHARS = ("jesus", "peter", "donkey") + EXTRAS
exec(compile(_patched_draw_faces_src(), MI_PATH + " (draw_faces, patched by ls_characters.py)", "exec"), globals())
_mi_draw_faces = draw_faces


def draw_faces():
    """Copy the Miracles decals this pack reuses, then draw the new ones (patched Miracles drawing code)."""
    copied = []
    for ch in ("jesus", "peter"):
        for ex in EXPRESSIONS[ch]:
            if ex in NEW_EXPRESSIONS[ch]:
                continue
            src = os.path.join(MI_FACES, f"{ch}_{ex}.png")
            shutil.copy(src, face_file(ch, ex)); copied.append(f"{ch}_{ex}")
    made = _mi_draw_faces()
    print("faces copied from Miracles:", len(copied), "| drawn:", len(made))
    return made


# ---------------------------------------------------------------------------------------------- compose (Pillow)
def compose():
    """Contact sheets model/preview_<char>.png, preview_extras.png, preview_all.png, preview_uvcheck.png,
    preview_pose.png, preview_ride.png from $LS_WORK."""
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
        cell = (480, 720) if ch != "donkey" else (560, 480)
        top = grid([W_(f"pv_{ch}_{v}.png") for v, _ in views], [lb for _, lb in views], 4, cell,
                   f"{ch}: rest pose, demo palette + default face decal")
        det = [("head", "face 3/4"), ("headfront", "face front"), ("props", "props shown")]
        if ch != "donkey":
            det[2:2] = [("handL", "left hand"), ("handR", "right hand")]
        bot = grid([W_(f"pv_{ch}_{v}.png") for v, _ in det], [lb for _, lb in det], 5, (384, 384), "close-ups")
        ex = grid([W_(f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]], EXPRESSIONS[ch], 6, (320, 320),
                  "face decals on the model (UV1)")
        stack([top, bot, ex]).save(os.path.join(MODEL, f"preview_{ch}.png"))
    fv = [W_(f"pv_{f}_{v}.png") for f in EXTRAS for v, _ in views]
    if any(os.path.exists(f) for f in fv):
        top = grid(fv, [f"{f} {lb}" for f in EXTRAS for _, lb in views], 4, (420, 630),
                   "extras (not on the sheet): fixed paint model/extras_paint.png on UV0 + face decals")
        grp = grid([W_(f"pv_extras_{v}.png") for v in ("line", "lineq")], ["line-up, front", "3/4"], 2, (960, 600),
                   "silhouettes side by side: john, james, andrew, seller1, seller2")
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
        r3 = Image.new("RGB", (2000, 400), bg)
        for i, f in enumerate(W_(f"uv_{n}.png") for n in ("dkL", "dkR", "dkTop", "dkFront")):
            if os.path.exists(f):
                r3.paste(Image.open(f).convert("RGB").resize((500, 400)), (500 * i, 0))
        hd = Image.new("RGB", (2000, 30), bg)
        ImageDraw.Draw(hd).text((10, 8), "UV0 proof: left = a perfectly coloured sheet (ID render in demo colours), right "
                                "= the models wearing it, front ortho (donkey turned to its side) = must equal the sheet; "
                                "then 3/4 + back; then the donkey: left side, right side (mirrored drawing), top, front",
                                fill=(40, 30, 20))
        stack([hd, r1, r2, r3]).save(os.path.join(MODEL, "preview_uvcheck.png"))
    pf = [(W_(f"pose_{ch}_{v}.png"), f"{ch} {v}") for ch in CHARS + EXTRAS for v in ("a", "b", "closed")]
    pf = [p for p in pf if os.path.exists(p[0])]
    if pf:
        grid([p[0] for p in pf], [p[1] for p in pf], 6, (320, 400),
             "pose test: a/b = elbows, fingers, thigh + knee, spine, head turn, jaw open, half / full blink, cloth bones; "
             "donkey a = head up, jaw open, foreleg lifted, ears + tail, b = head down, eyes shut; closed = eyes shut").save(
            os.path.join(MODEL, "preview_pose.png"))
    rf = [(W_(f"ride_{v}.png"), lb) for v, lb in (
        ("side", "ride: side (seat 0.155 on the blanket)"), ("front", "ride: front (legs either side of the barrel)"),
        ("q34", "ride: 3/4"), ("phone", "ride: phone angle"), ("low", "ride: walk low point (seat -0.006)"),
        ("high", "ride: walk high point (seat +0.006)"),
        ("kneel_side", "kneel_wash: side, basin 0.06 in front"), ("kneel_q34", "kneel: 3/4 with towel + basin"),
        ("kneel_phone", "kneel: phone angle at UPPER"), ("props_jesus", "jesus: towel, bread, cup shown"),
        ("props_peter", "peter: palm, towel, jug shown"), ("seated_wash", "kneel pair: Jesus 0.11 in front of john"))]
    rf = [r for r in rf if os.path.exists(r[0])]
    if rf:
        grid([r[0] for r in rf], [r[1] for r in rf], 3, (640, 480),
             "fit tests (not clips): the ride pair and the kneel with the basin").save(os.path.join(MODEL, "preview_ride.png"))
    print("composed previews ->", MODEL)


if not IN_BLENDER:
    if __name__ == "__main__":
        mode = sys.argv[1] if len(sys.argv) > 1 else "faces"

        def blender_bin():
            return os.environ.get("BLENDER") or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"

        def run_all():
            import subprocess
            me = os.path.abspath(__file__)
            draw_faces()
            subprocess.run([blender_bin(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", me, "--",
                            "build"], check=True, stdout=subprocess.DEVNULL)
            proof()
            for m in ("preview", "uvcheck", "posetest", "verify"):
                subprocess.run([blender_bin(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", me, "--",
                                m], check=True, stdout=subprocess.DEVNULL)
            compose()
            v = json.load(open(os.path.join(WORK, "verify.json")))
            for ch, i in v.items():
                print(ch, "bonesMatch", i["bonesMatch"], "parentsOK", i.get("parentsOK"), "actions", i["actions"],
                      "tris", i["tris"], "budget", i["budget"], "uvOrderOK", i.get("uvOrderOK"),
                      "maxInf", i.get("maxInfluences"), "height", i["heightTop"], "err%", i["heightErrPct"],
                      "minY", i["minY"], *(("seat", i["seatY"]) if "seatY" in i else ()))
        {"faces": draw_faces, "compose": compose, "proof": proof, "all": run_all}[mode]()
    raise SystemExit(0)

# =============================================================================================== Blender part
ONLY = [c for c in os.environ.get("LS_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()


def set_prop_anchors():
    """design.json set.propAnchors (Set + sheet role): "<char>/<prop>" -> {"region": [...], "uv": [u, v]} — the exact
    printed texel each prop samples; it wins over the PROP_ANCHORS search (kit: PROP_UV). Peter's palm is printed with
    him but coloured from the set's palm green, so it goes the same way."""
    try:
        pa = json.load(open(DESIGN_JSON)).get("set", {}).get("propAnchors", {})
    except Exception:                                           # noqa: BLE001
        return {}
    for key, v in pa.items():
        ch, _, prop = key.partition("/")
        uv = v.get("uv")
        if isinstance(uv[0], (list, tuple)):                  # a list of candidates: the first one
            uv = uv[0]
        PROP_UV.setdefault(ch, {})[prop] = [float(uv[0]), float(uv[1])]
    return pa


SET_PROP_ANCHORS = set_prop_anchors()
_MiCtx = _MI["Ctx"]


class Ctx(_MiCtx):
    def __init__(self, ch):
        if ch not in QUADS:
            _MiCtx.__init__(self, ch)
            self.lid_part = "face"; self.lid_reg = "skin"
            return
        self.ch = ch; self.F = face_layout(ch)          # quadruped: no human landmarks; S = 1, blend in art units
        self.s = {}; self.S = 1.0; self.blend = 0.008
        self.L = dict(chin=0.15, top=0.27, zc=DK_HEAD["c"][2], mouth=0.1575); self.H = 0.10
        self.parts = []; self.B = {}; self.hand = {}
        self.lid_part = "face"; self.lid_reg = "coat"


# =============================================================================================== props (Jesus, Peter)
def _clay_lathe(cg, centre, prof, N, reg, wfn=None):
    """A small turned pot (basin, cup, jug): prof = [(dy, r)], closed bottom and an open top closed by a fan (the water /
    the inside), low-poly on purpose (props count in their owner's 25k)."""
    rings = [cg.ring([centre + V(math.sin(2 * math.pi * j / N) * r, dy, math.cos(2 * math.pi * j / N) * r)
                      for j in range(N)], wfn) for dy, r in prof]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, 0)
    cg.fan(list(reversed(rings[0])), centre + V(0, prof[0][0], 0), wfn, reg, 0)
    cg.fan(rings[-1], centre + V(0, prof[-1][0] - 0.25 * abs(prof[-1][0] - prof[-2][0]), 0), wfn, reg, 0)
    return rings


def add_jesus_props(C):
    s = C.s; S = C.S
    hipY = s["hipY"]; wy = s["waistY"]
    rr = C.robe_rows
    # towel: a white linen band round the hips, over the mantle, tucked in; one end hanging at the right hip
    y0, y1 = hipY - 0.020 * S, wy - 0.012 * S
    C.B["towel"] = (V(0, y1, 0), V(0, y0 - 0.02 * S, 0), "hips")
    cg = Cage(); N = 12
    out_off, in_off = 0.0068 * S, 0.0050 * S

    def ringat(y, off, flare=0.0):
        return [shell_point(rr, y, 2 * math.pi * j / N, off + flare) for j in range(N)]
    r0 = cg.ring(ringat(y0, in_off, 0.0006 * S), None); r1 = cg.ring(ringat(y0, out_off, 0.0010 * S), None)
    r2 = cg.ring(ringat(y1, out_off), None); r3 = cg.ring(ringat(y1, in_off), None)
    for a, b in ((r0, r1), (r1, r2), (r2, r3), (r3, r0)):
        cg.bridge(a, b, "towel", 0)
    ae = -1.15                                                   # the hanging end at the right hip (character's right)
    pp, nn = [], []
    for t in (0.0, 0.33, 0.66, 1.0):
        y = lerp(y0 + 0.004 * S, y0 - 0.034 * S, t)
        p = shell_point(rr, y, ae - 0.10 * t, out_off + 0.0008 * S + 0.0010 * S * t)
        pp.append(p); nn.append(V(p.x, 0, p.z).normalized())
    strip(cg, pp, nn, [0.0060 * S * (1 + 0.25 * t) for t in (0.0, 0.33, 0.66, 1.0)], 0.0010 * S, None, "towel", 0)
    C.add("towel", cg, subdiv=0, rigid="towel")
    # basin: shallow terracotta bowl with water, 0.08 across, on the floor 0.06 in front (rest place of its bone)
    bc = V(0, 0.0004, 0.060)
    C.B["basin"] = (bc.copy(), bc + V(0, 0.020, 0), "root")
    cg = Cage()
    _clay_lathe(cg, bc, [(0.0, 0.024), (0.0035, 0.033), (0.0150, 0.0400), (0.0160, 0.0372), (0.0110, 0.0340)], 10, "basin")
    C.add("basin", cg, subdiv=0, rigid="basin")
    # bread: a round flat loaf in the left hand
    A = C.arm["L"]; gp = grip_point(C, "L")
    C.B["bread"] = (gp.copy(), gp + A["dh"] * 0.012 * S, "handL")
    cg = Cage()
    blob(cg, gp + A["Np"] * 0.0050 * S, 0.0145 * S, 0.0060 * S, 0.0145 * S, None, "bread", 0, NU=8, NV=4)
    C.add("bread", cg, subdiv=0, rigid="bread")
    # cup: a plain clay cup with a foot in the right hand
    A = C.arm["R"]; gp = grip_point(C, "R")
    C.B["cup"] = (gp.copy(), gp + V(0, 0.012 * S, 0), "handR")
    cg = Cage()
    cc = gp + A["Np"] * 0.0040 * S + V(0, -0.010 * S, 0)
    _clay_lathe(cg, cc, [(0.0, 0.0060 * S), (0.0030 * S, 0.0035 * S), (0.0060 * S, 0.0062 * S), (0.0170 * S, 0.0085 * S),
                         (0.0160 * S, 0.0074 * S)], 8, "cup")
    C.add("cup", cg, subdiv=0, rigid="cup")


def add_peter_props(C):
    s = C.s; S = C.S; nb = s["neckBase"]; chestY = s["chestY"]
    # the Miracles bucket: bone kept (one rig for both packs), mesh dropped (CONTRACT §3)
    C.parts = [p for p in C.parts if p["name"] != "bucket"]
    rr = C.robe_rows
    # palm frond in the right hand (shown by default): a spine with nine leaflet pairs, slightly V-folded
    A = C.arm["R"]; gp = grip_point(C, "R")
    C.B["palm"] = (gp.copy(), gp + V(0, 0.030 * S, 0), "handR")
    cg = Cage()
    base = gp + V(0, -0.012 * S, 0.001 * S); top = gp + V(0.004 * S, 0.120 * S, 0.0)
    NSP = 10; sp = [base.lerp(top, i / NSP) + V(0.003 * S * math.sin(i / NSP * math.pi), 0, 0) for i in range(NSP + 1)]
    tube(cg, sp[:3], [(0.0014 * S, 0.0014 * S)] * 3, 4, None, "palm", 0, ref=V(0, 0, 1))
    for i in range(1, NSP):
        a, b = sp[i], sp[i + 1]
        ln = 0.026 * S * math.sin(min(1.0, (i + 0.5) / NSP) * math.pi) ** 0.6 + 0.004 * S
        for sx in (-1, 1):
            tip = a + V(sx * ln, ln * 0.55, 0.004 * S)
            ia, ib, it = cg.add(a, None), cg.add(b, None), cg.add(tip, None)
            cg.face((ia, it, ib) if sx > 0 else (ia, ib, it), "palm", 0)
            ja, jb, jt = cg.add(a + V(0, 0, -0.0007 * S), None), cg.add(b + V(0, 0, -0.0007 * S), None), \
                cg.add(tip + V(0, 0, -0.0007 * S), None)
            cg.face((ja, jb, jt) if sx > 0 else (ja, jt, jb), "palm", 0)
    C.add("palm", cg, subdiv=0, rigid="palm")
    # towel over the left shoulder: a strip from the back over the shoulder to the front
    xw = 0.55 * s["shoulder"][0]

    def zf_zb(y):
        hw, zf, zb = table(rr, y)
        return zf, zb
    ys = [chestY - 0.034 * S, chestY - 0.010 * S, nb - 0.006 * S]
    path = []; nrm = []
    for y in ys:
        path.append(V(xw, y, zf_zb(y)[1] - 0.0030 * S)); nrm.append(V(0, 0, -1))
    yt = nb + 0.0040 * S; zf, zb = zf_zb(nb - 0.002 * S)
    path.append(V(xw, yt, (zf + zb) / 2)); nrm.append(V(0, 1, 0))
    for y in reversed(ys):
        path.append(V(xw, y, zf_zb(y)[0] + 0.0030 * S)); nrm.append(V(0, 0, 1))
    C.B["towel"] = (V(xw, yt, (zf + zb) / 2), V(xw, chestY - 0.034 * S, zf + 0.003 * S), "chest")
    cg = Cage()
    strip(cg, path, nrm, [0.0085 * S] * len(path), 0.0014 * S, None, "towel", 0)
    C.add("towel", cg, subdiv=0, rigid="towel")
    # jug: terracotta, one handle, hanging from the right hand by its handle (as the Miracles bucket)
    C.B["jug"] = (gp.copy(), gp + V(0, -0.030 * S, 0), "handR")
    cg = Cage()
    jc = gp + V(0, -0.044 * S, 0.0)
    prof = [(0.0, 0.0075 * S), (0.004 * S, 0.0110 * S), (0.014 * S, 0.0125 * S), (0.023 * S, 0.0085 * S),
            (0.028 * S, 0.0058 * S), (0.032 * S, 0.0068 * S), (0.0300 * S, 0.0055 * S)]
    _clay_lathe(cg, jc, prof, 10, "jug")
    hp = [jc + V(0, 0.027 * S, -0.0060 * S), gp + V(0, 0.000, -0.0025 * S), jc + V(0, 0.016 * S, -0.0130 * S)]
    hp = [cr_open(hp, t / 5) for t in range(6)]
    tube(cg, hp, [(0.0013 * S, 0.0010 * S)] * len(hp), 5, None, "jug", 0, ref=V(1, 0, 0))
    C.add("jug", cg, subdiv=0, rigid="jug")


def build_jesus_ls(C):
    _MI["build_jesus"](C)
    add_jesus_props(C)


def build_peter_ls(C):
    _MI["build_peter"](C)
    add_peter_props(C)


# =============================================================================================== the extras
def _rename_bone(C, old, new):
    """Rename a bone in the builder's skeleton and in every cage weight; new may be an existing bone (merge)."""
    if old not in C.B:
        return
    if new not in C.B:
        C.B[new] = C.B[old]
    del C.B[old]
    for pt in C.parts:
        cg = pt["cage"]
        for i, w in enumerate(cg.w):
            if old in w:
                v = w.pop(old); w[new] = w.get(new, 0.0) + v


def _extra_beard(C, kind):
    """Beards on the friend head (kit build_beard, hair region, one printed piece with the moustache)."""
    s = C.s; L = C.L; H = C.H; S = C.S
    if kind == "goatee":                                  # seller2: a little pointed beard
        top = [(0.00, L["mouth"] - 0.075 * H), (0.05, L["mouth"] - 0.065 * H), (0.10, L["mouth"] - 0.040 * H)]
        bot = [(0.00, L["chin"] - 0.22 * H), (0.04, L["chin"] - 0.12 * H), (0.10, L["mouth"] - 0.07 * H)]

        def bth(uu, y, v):
            return (0.0036 * S * smoothstep(0.0, 0.25, v) * (1 - 0.5 * smoothstep(0.0, 0.10, uu))) + 0.0005 * S
        build_beard(C, top, bot, bth, lambda u, y: 0.0, 0.10, L["chin"] - 0.22 * H, reg="hair", NU=9, NV=7)
        C.parts[-1]["piece_as"] = "beard"
        return
    f = 1.0 if kind == "short" else 0.72                 # james: short full; andrew: neat and thin
    top = [(0.00, L["mouth"] - 0.085 * H), (0.035, L["mouth"] - 0.07 * H), (0.07, L["mouth"] + 0.0 * H),
           (0.10, L["nose"] - 0.06 * H), (0.15, L["nose"] - 0.01 * H), (0.20, L["eye"] - 0.16 * H), (0.245, L["eye"] - 0.04 * H)]
    bot = [(0.00, L["chin"] - 0.10 * H * f), (0.06, L["chin"] - 0.095 * H * f), (0.12, L["chin"] - 0.06 * H * f),
           (0.17, L["chin"] + 0.02 * H), (0.21, L["mouth"] - 0.04 * H), (0.245, L["nose"] - 0.06 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0044, 0.0030, smoothstep(0.05, 0.24, uu)) * S * smoothstep(0.0, 0.20, v) * f
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        return 0.0006 * S * f * math.cos(2 * math.pi * u * 24) * math.cos(2 * math.pi * (y - L["chin"]) / (0.005 * S))
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.10 * H * f, reg="hair", NU=9, NV=5)
    C.parts[-1]["piece_as"] = "beard"
    if kind == "neat":                                   # Andrew: no moustache (budget; reads as a neat chin beard)
        return
    moustache(C, "moustache", L["mouth"] + 0.092 * H, 0.58 * s["hw"], 0.05 * H, 0.0, 0.0018 * S * f, reg="hair", off=0.0016)
    C.parts[-1]["piece_as"] = "beard"


def _shell_panel(C, name, reg_fn, a_cols, y_bot, y_top, off, wfn, NV=6, solid=0.0010, subdiv=1, piece_as=None):
    """A cloth panel lying on the tunic: columns at angles a_cols (0 = front, + toward +X), rows from y_bot(a) up to
    y_top(a); reg_fn(column index) gives the region of a column of faces."""
    rr = C.tunic_rows; S = C.S
    cg = Cage(); grid = []
    for a in a_cols:
        col = []
        for j in range(NV + 1):
            v = j / NV
            y = lerp(y_bot(a), y_top(a), v)
            col.append(cg.add(shell_point(rr, y, a, off(a, v)), wfn))
        grid.append(col)
    for i in range(len(a_cols) - 1):
        for j in range(NV):
            cg.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), reg_fn(i), 0)
    kw = dict(subdiv=subdiv, solidify=solid * S)
    if piece_as:
        kw["piece_as"] = piece_as
    C.add(name, cg, **kw)
    return grid


def build_extra(C):
    """The Miracles friend body (unchanged) + this pack's costume for one extra (CONTRACT §3, DESIGN §1)."""
    ch = C.ch
    _MI["build_friend"](C)
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]
    hipY, wy, chestY, nb = s["hipY"], s["waistY"], s["chestY"], s["neckBase"]
    if ch == "seller1":                                  # bald with a fringe, no beard (DESIGN §1)
        C.parts = [p for p in C.parts if p["name"] not in ("beard", "moustache")]
    if ch == "andrew":                                   # the friend head band = Peter's blue-grey head cloth (cloth1)
        _rename_bone(C, "band1", "cloth1")
    if ch == "james":
        _extra_beard(C, "short")
    elif ch == "andrew":
        _extra_beard(C, "neat")
    elif ch == "seller2":
        _extra_beard(C, "goatee")
    # the friend belt end: John's is the white sash (sash1); the others keep the belt end stiff on the hips
    _rename_bone(C, "belt1", "sash1" if ch == "john" else "hips")
    if ch != "john":                                     # no bone of its own any more: drop the hanging end (budget)
        C.parts = [p for p in C.parts if p["name"] != "beltEnd"]
    if ch == "james":                                    # short brown cloak over the left shoulder, down the back
        shY = s["shoulder"][1]
        cb = C.B["chest"]
        p_top = shell_point(C.tunic_rows, nb - 0.010 * S, 2.5, 0.004 * S)
        p_bot = shell_point(C.tunic_rows, hipY + 0.004 * S, 3.15, 0.004 * S)
        C.B["cloak1"] = (p_top, p_bot, "chest")
        wtop = C.w(["chest", "shoulderL", "spine"]); wcl = C.w(["cloak1"], blend=0.012 * S)

        def wfn(p):
            t = smoothstep(chestY + 0.006 * S, chestY - 0.020 * S, p.y)
            return mixw((wtop(p), 1 - t), (wcl(p), t)) if t > 0 else wtop(p)
        cols = [0.45 + (4.25 - 0.45) * i / 17 for i in range(18)]

        def ybot(a):
            t = smoothstep(1.75, 2.35, a)
            return lerp(shY - 0.010 * S, lerp(chestY - 0.016 * S, hipY - 0.006 * S, smoothstep(2.3, 3.9, a)), t)

        def ytop(a):
            return lerp(nb - 0.0015 * S, chestY + 0.002 * S, smoothstep(3.2, 4.25, a))

        def off(a, v):
            return (0.0030 + 0.0016 * (1 - v)) * S
        _shell_panel(C, "cloak", lambda i: "cloak", cols, ybot, ytop, off, wfn, NV=6, solid=0.0011, subdiv=0)
    if ch == "seller1":                                  # cream-and-brown striped apron (apron1)
        hemT = 0.100 * k
        p0 = shell_point(C.tunic_rows, wy - 0.006 * S, 0.0, 0.004 * S)
        p1 = shell_point(C.tunic_rows, hemT + 0.010 * S, 0.0, 0.005 * S)
        C.B["apron1"] = (p0, p1, "hips")
        wtop = C.w(["hips"]); wap = C.w(["apron1"], blend=0.012 * S)

        def wfn(p):
            t = smoothstep(wy - 0.010 * S, hipY - 0.016 * S, p.y)
            return mixw((wtop(p), 1 - t), (wap(p), t)) if t > 0 else wtop(p)
        cols = [-0.95 + 1.90 * i / 7 for i in range(8)]
        _shell_panel(C, "apron", lambda i: "stripes" if i % 2 else "apron", cols,
                     lambda a: hemT + 0.012 * S, lambda a: wy - 0.004 * S,
                     lambda a, v: (0.0032 + 0.0012 * (1 - v)) * S, wfn, NV=5, solid=0.0010)
    if ch == "seller2":                                  # fat money pouch on a string at the belt (pouch swings)
        bw = wy - 0.012 * S
        hw, zf, zb = table(C.tunic_rows, bw)
        a = -0.75
        top = shell_point(C.tunic_rows, bw - 0.006 * S, a, 0.0040 * S)
        C.B["pouch"] = (top.copy(), top + V(-0.002 * S, -0.020 * S, 0.003 * S), "hips")
        wp = lambda p: {"pouch": 1.0}
        cg = Cage()
        pc = top + V(-0.0020 * S, -0.0130 * S, 0.0040 * S)
        blob(cg, pc, 0.0088 * S, 0.0100 * S, 0.0072 * S, wp, "pouch", 0, NU=10, NV=6)
        blob(cg, top + V(-0.0008 * S, -0.0028 * S, 0.0016 * S), 0.0040 * S, 0.0022 * S, 0.0034 * S, wp, "pouch", 0, NU=8, NV=4)
        C.add("pouch", cg, subdiv=0)


# =============================================================================================== the donkey
def donkey_skeleton(C):
    B = {}
    B["root"] = (V(0, 0, 0), V(0, 0.020, 0), None)
    B["hips"] = (V(0, 0.112, -0.086), V(0, 0.112, -0.034), "root")
    B["spine"] = (V(0, 0.112, -0.034), V(0, 0.114, 0.016), "hips")
    B["chest"] = (V(0, 0.114, 0.016), V(0, 0.120, 0.056), "spine")
    B["neck"] = (V(0, 0.124, 0.058), V(0, 0.184, 0.094), "chest")
    B["head"] = (V(0, 0.184, 0.094), V(0, 0.204, 0.142), "neck")
    B["jaw"] = (V(0, 0.170, 0.106), V(0, 0.150, 0.150), "head")
    ex, ey, ew, eh = C.F["eyeLocal"]
    hc = V(*DK_HEAD["c"]); hr = DK_HEAD["r"]
    zf = hc.z + hr[2] * 0.92
    C.lid = dict(top=ey + 1.30 * eh, h0=0.18 * eh, closed=ey - 1.0 * eh)
    B["eyelids"] = (V(0, C.lid["top"], zf), V(0, C.lid["top"] - 0.010, zf), "head")
    for side, sd in (("L", 1), ("R", -1)):
        B["ear" + side] = (V(sd * 0.016, 0.222, 0.100), V(sd * 0.027, 0.268, 0.096), "head")
        B["upperArm" + side] = (V(sd * 0.023, 0.098, 0.050), V(sd * 0.023, 0.052, 0.054), "chest")
        B["forearm" + side] = (V(sd * 0.023, 0.052, 0.054), V(sd * 0.023, 0.016, 0.056), "upperArm" + side)
        B["paw" + side] = (V(sd * 0.023, 0.016, 0.056), V(sd * 0.023, 0.004, 0.068), "forearm" + side)
        B["thigh" + side] = (V(sd * 0.025, 0.100, -0.080), V(sd * 0.025, 0.054, -0.092), "hips")
        B["shin" + side] = (V(sd * 0.025, 0.054, -0.092), V(sd * 0.025, 0.016, -0.086), "thigh" + side)
        B["foot" + side] = (V(sd * 0.025, 0.016, -0.086), V(sd * 0.025, 0.004, -0.074), "shin" + side)
    tl = [V(*p) for p in DK_TAIL]
    B["tail1"] = (tl[0], tl[2], "hips")
    B["tail2"] = (tl[2], tl[4], "tail1")
    C.B = B


def build_donkey(C):
    """A young, small, round donkey (DESIGN §1): round barrel on short sturdy legs with dark hooves, a big head with a
    cream muzzle, very long upright ears with dark tips, a brush mane, a thin tail with a dark tuft, and a red saddle
    blanket with a gold stripe over the back (its top centre is the seat)."""
    donkey_skeleton(C)
    B = C.B
    secs = DK_BODY
    path = [V(0, yc, z) for z, yc, rx, ry in secs]
    path = [cr_open(path, i / 23) for i in range(24)]
    radii = [tuple(table(secs, p.z)[1:3]) for p in path]
    wbody = C.w(["hips", "spine", "chest", ("upperArmL", 0.016), ("upperArmR", 0.016), ("thighL", 0.018),
                 ("thighR", 0.018), ("tail1", 0.006)])
    cg = Cage()

    # no cream belly patch: in side view it printed under 3 mm (C3), so the belly keeps the coat colour
    tube(cg, path, radii, 18, wbody, "coat", 0, ref=V(0, 0, 1), e=DK_E, cap0=True, cap1=True, cap_len=0.5)
    C.add("body", cg, subdiv=1)
    for side, sd in (("L", 1), ("R", -1)):              # haunches and shoulders: soft masses over the leg tops
        cg = Cage()
        blob(cg, V(sd * 0.022, 0.104, -0.080), 0.017, 0.032, 0.030, C.w(["thigh" + side, "hips", "spine"], blend=0.010),
             "coat", 0, NU=12, NV=8)
        C.add("haunch" + side, cg, subdiv=1)
        cg = Cage()
        blob(cg, V(sd * 0.021, 0.100, 0.046), 0.0155, 0.028, 0.021, C.w(["upperArm" + side, "chest", "spine"], blend=0.010),
             "coat", 0, NU=10, NV=7)
        C.add("shoulder" + side, cg, subdiv=1)
    # ---- legs: short sturdy tubes, dark hooves (flat soles on y = 0)
    for side, sd in (("L", 1), ("R", -1)):
        for kind in ("F", "B"):
            cg = Cage()
            if kind == "F":
                bones = ["upperArm" + side, "forearm" + side, "paw" + side]
                pts = [V(sd * 0.023, 0.104, 0.048), V(sd * 0.023, 0.070, 0.052), B["upperArm" + side][1].copy(),
                       V(sd * 0.023, 0.020, 0.056)]
                rads = [0.0150, 0.0125, 0.0100, 0.0086]
                hc_ = V(sd * 0.023, 0.0072, 0.0585)
            else:
                bones = ["thigh" + side, "shin" + side, "foot" + side]
                pts = [V(sd * 0.025, 0.104, -0.078), V(sd * 0.025, 0.074, -0.088), B["thigh" + side][1].copy(),
                       V(sd * 0.025, 0.020, -0.084)]
                rads = [0.0165, 0.0135, 0.0102, 0.0088]
                hc_ = V(sd * 0.025, 0.0072, -0.0815)
            wl = C.w(bones, blend=0.007)
            dense = [cr_open(pts, i / 7) for i in range(8)]
            rr = [table([(i / (len(rads) - 1), r) for i, r in enumerate(rads)], i / 7)[0] for i in range(8)]
            tube(cg, dense, [(r, r * 1.04) for r in rr], 10, wl, "coat", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
            C.add("leg" + kind + side, cg, subdiv=1)
            cg = Cage()
            wh = C.w([bones[-1]], blend=0.01)
            _clay_lathe(cg, hc_ + V(0, -0.0072, 0), [(0.0, 0.0094), (0.0030, 0.0098), (0.0085, 0.0094), (0.0125, 0.0086),
                                                     (0.0135, 0.0060)], 10, "hooves", wh)

            def hpost(pts_, nrm):
                return [V(p.x, max(0.0004, p.y), p.z) for p in pts_]
            C.add("hoof" + kind + side, cg, subdiv=1, post=hpost, piece_as="leg" + kind + side)
    # ---- neck
    cg = Cage()
    npath = [V(0, 0.118, 0.046), V(0, 0.142, 0.066), V(0, 0.166, 0.083), V(0, 0.190, 0.098)]
    npath = [cr_open(npath, i / 6) for i in range(7)]
    nr = [(0.0250, 0.0290), (0.0235, 0.0270), (0.0215, 0.0250), (0.0200, 0.0230), (0.0190, 0.0215), (0.0185, 0.0205),
          (0.0180, 0.0200)]
    tube(cg, npath, nr, 14, C.w(["chest", "neck", "head"], blend=0.012), "coat", 0, ref=V(1, 0, 0), cap0=False, cap1=False)
    C.add("neck", cg, subdiv=1)
    # ---- head (named "face": the eyelids and the decal look for it), nose bridge, muzzle, jaw
    hc = V(*DK_HEAD["c"]); hr = DK_HEAD["r"]
    cg = Cage()
    blob(cg, hc, hr[0], hr[1], hr[2], C.w(["head", "neck"], blend=0.012), "coat", 0, NU=18, NV=11)
    ex, ey, ew, eh = C.F["eyeLocal"]; lid = C.lid

    def eye_plateau(pts_, nrm):
        """A small flat 'eye socket' plateau: over the lid travel the head front is held at its depth at the eye
        centre, so the rigid lids lie on the surface all the way down (C1) instead of floating at rest."""
        out = []
        for p in pts_:
            q = p.copy()
            if q.z > hc.z:
                dx = abs(abs(q.x) - ex)
                wx = smoothstep(1.70 * ew, 1.20 * ew, dx)
                wy = smoothstep(lid["top"] + 0.9 * eh, lid["top"] + 0.2 * eh, q.y) * \
                    smoothstep(lid["closed"] - 1.2 * eh, lid["closed"] - 0.3 * eh, q.y)
                w = wx * wy
                if w > 0:
                    t = (min(abs(q.x), 0.98 * hr[0]) / hr[0]) ** 2 + ((ey - hc.y) / hr[1]) ** 2
                    zc = hc.z + hr[2] * math.sqrt(max(0.0, 1 - t)) * 0.985
                    q.z = q.z + max(0.0, zc - q.z) * w
            out.append(q)
        return out
    C.add("face", cg, subdiv=1, decal=True, post=eye_plateau)
    cg = Cage()
    blob(cg, V(*DK_BRIDGE["c"]), *DK_BRIDGE["r"], C.w(["head"]), "coat", 0, NU=12, NV=7,
         ax=Matrix.Rotation(math.radians(-38), 3, V(1, 0, 0)))
    C.add("bridge", cg, subdiv=1, decal=True, piece_as="face")
    cg = Cage()

    def wmz(p):
        t = smoothstep(0.163, 0.154, p.y)
        return {"head": 1 - t, "jaw": t} if t > 0 else {"head": 1.0}
    blob(cg, V(*DK_MUZZLE["c"]), *DK_MUZZLE["r"], wmz, "muzzle", 0, NU=14, NV=8)
    C.add("muzzle", cg, subdiv=1, decal=True)
    cg = Cage()
    blob(cg, V(*DK_JAW["c"]), *DK_JAW["r"], lambda p: {"jaw": 1.0}, "muzzle", 0, NU=12, NV=6)
    C.add("jawMuzzle", cg, subdiv=1, decal=True, piece_as="muzzle")
    # ---- ears: long, upright, a little out; cream inside (front), dark tips (mane colour)
    for side, sd in (("L", 1), ("R", -1)):
        cg = Cage()
        h, t = B["ear" + side][0], B["ear" + side][1]
        d = (t - h).normalized()
        ep = [h + d * (0.052 * f) + V(0, 0, 0.0035 * math.sin(f * math.pi)) for f in (0.0, 0.15, 0.35, 0.58, 0.80, 0.94, 1.0)]
        er = [(0.0060, 0.0045), (0.0090, 0.0050), (0.0102, 0.0050), (0.0094, 0.0046), (0.0068, 0.0038), (0.0038, 0.0026),
              (0.0016, 0.0014)]
        we = lambda p, side=side, h=h: {"ear" + side: smoothstep(h.y - 0.002, h.y + 0.010, p.y),
                                         "head": 1 - smoothstep(h.y - 0.002, h.y + 0.010, p.y)} \
            if p.y < h.y + 0.010 else {"ear" + side: 1.0}

        def ereg(q, h=h, d=d):
            c = sum((cg.v[i] for i in q), V()) / len(q)
            f = (c - h).dot(d) / 0.052
            if f > 0.80:
                return "mane"
            axis = h + d * ((c - h).dot(d))
            if (c - axis).z > 0.0028 and abs((c - axis).x) < 0.0060 and 0.12 < f < 0.80:
                return "muzzle"
            return "coat"
        tube(cg, ep, er, 10, we, "coat", 0, ref=V(1, 0, 0), cap0=True, cap1=True, regfn=ereg, cap_len=0.4)
        C.add("ear" + side, cg, subdiv=1)
    # ---- mane: a short dark brush along the top of the neck from the poll to the withers, a forelock between the ears
    cg = Cage()
    mp = [V(0, 0.224, 0.094), V(0, 0.212, 0.084), V(0, 0.194, 0.074), V(0, 0.174, 0.064), V(0, 0.156, 0.054),
          V(0, 0.146, 0.044)]
    mp = [cr_open(mp, i / 9) for i in range(10)]
    mr = [(0.0042, 0.0080 + 0.0030 * math.sin(i / 9 * math.pi)) for i in range(10)]
    tube(cg, mp, mr, 8, C.w(["head", "neck", "chest"], blend=0.012), "mane", 0, ref=V(1, 0, 0), cap0=True, cap1=True)
    blob(cg, V(0, 0.228, 0.112), 0.0080, 0.0070, 0.0075, C.w(["head"]), "mane", 0, NU=8, NV=5)
    C.add("mane", cg, subdiv=1)
    # ---- tail: thin, down and back from the rump, a dark tuft at the tip
    cg = Cage()
    tp = [V(*p) for p in DK_TAIL]
    dense = [cr_open(tp, i / 8) for i in range(9)]
    tube(cg, dense, [0.0040 - 0.0014 * i / 8 for i in range(9)], 6, C.w(["hips", "tail1", "tail2"], blend=0.006), "coat", 0,
         ref=V(1, 0, 0), cap0=True, cap1=False)
    dd = (dense[-1] - dense[-3]).normalized()
    Xt = perp(V(1, 0, 0), dd); Zt = Xt.cross(dd)
    Mt = Matrix((Xt, dd, Zt)).transposed()
    blob(cg, dense[-1] + dd * 0.0080, 0.0068, 0.0150, 0.0068, lambda p: {"tail2": 1.0}, "mane", 0, NU=8, NV=6, ax=Mt)
    C.add("tail", cg, subdiv=1)
    # ---- saddle blanket: a rectangle folded over the back, to mid-belly on both sides, gold stripe, fringe edge
    bl = DK_BLANKET; NZ, NT = 9, 15; tm = math.radians(bl["theta"])
    cg = Cage(); grid = []
    for i in range(NZ):
        z = lerp(bl["z0"], bl["z1"], i / (NZ - 1))
        yc, rx, ry = table(secs, z)
        col = []
        for j in range(NT):
            th = lerp(-tm, tm, j / (NT - 1)); dr = (abs(th) / tm) ** 2
            off = bl["off"] + 0.0016 * dr
            p = V(se(math.sin(th), DK_E) * (rx + off), yc + se(math.cos(th), DK_E) * (ry + off), z)
            if abs(th) > 0.95 * tm:                       # the fringe: little zigzag on the hanging edge
                p.y -= 0.0018 * (0.5 + 0.5 * math.cos(i * math.pi))
            col.append(cg.add(p, wbody))
        grid.append(col)
    for i in range(NZ - 1):
        for j in range(NT - 1):
            thm = abs(lerp(-tm, tm, (j + 0.5) / (NT - 1))) / tm
            reg = "gold" if 0.84 < thm < 0.95 else "blanket"   # gold band just above the fringe
            cg.face((grid[i][j], grid[i][j + 1], grid[i + 1][j + 1], grid[i + 1][j]), reg, 0)
    C.add("blanket", cg, subdiv=1, solidify=bl["solid"])


BUILDERS = {"jesus": build_jesus_ls, "peter": build_peter_ls, "donkey": build_donkey}
BUILDERS.update({e: build_extra for e in EXTRAS})


# =============================================================================================== assembly overrides
REGIONS_KEY = "ls_regions"
_kit_eyelid_cage = _MI["eyelid_cage"]


def eyelid_cage(C, face_obj, sheet):
    """Humans: the kit's lids. The donkey: each lid row sits on the most forward head point over its whole travel
    (rest -> closed), never inside the round head (Daniel's lion fix, C1)."""
    if C.ch not in QUADS:
        return _kit_eyelid_cage(C, face_obj, sheet)
    me = face_obj.data
    vs = [to_design(face_obj.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    bvh = BVHTree.FromPolygons([tuple(v) for v in vs], [tuple(p.vertices) for p in me.polygons])
    ex, ey, ew, eh = C.F["eyeLocal"]
    top, h0 = C.lid["top"], C.lid["h0"]
    cg = Cage()
    for sx in (-1, 1):
        cols = []
        for i in range(8):
            x = sx * ex + (i / 7 - 0.5) * 2 * 1.12 * ew        # narrower than the human lids: inside the plateau
            col = []
            for j in range(4):
                y = top - h0 * j / 3
                d0 = h0 * j / 3; d1 = max(d0, h0 * j / 3 * 12.8, (top - C.lid["closed"]) * j / 3)
                zs = []
                for k in range(9):
                    hit = bvh.ray_cast(V(x, top - lerp(d0, d1, k / 8), 0.3), V(0, 0, -1), 1.0)
                    if hit[0]:
                        zs.append(hit[0].z)
                col.append(V(x, y, (max(zs) + 0.0003) if zs else 0.0))
            cols.append(col)
        good = [i for i, c in enumerate(cols) if all(abs(p.z) > 1e-9 for p in c)]
        for i, c in enumerate(cols):
            for j, p in enumerate(c):
                if abs(p.z) < 1e-9 and good:
                    p.z = cols[min(good, key=lambda g: abs(g - i))][j].z
        idx = [[cg.add(p, None) for p in col] for col in cols]
        for i in range(7):
            for j in range(3):
                cg.face((idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1]), C.lid_reg, 0)
    C.lid["closedScale"] = round((C.lid["top"] - C.lid["closed"]) / C.lid["h0"], 2)
    return cg


def side_uv(objs, sheet, to_uv, inset):
    """Side-view characters (Daniel's lion / Jonah's fish method, same code): UV0 = SIDE projection of the left side
    (+X) at its slot: page X = -z (nose to -X), page Y = y. Every vertex is mirrored to the left side first (|x|), so the
    right side samples the drawing of the left side. A face keeps the projection when all its (mirrored) corners face +X
    and a ray from each toward +X meets nothing of another region; otherwise it is flagged st_hidden = 1 and later takes
    one clean texel of its own region (side_texels)."""
    off = V(sheet[0], sheet[1], 0)
    allv, allf, freg = [], [], []
    per = []
    for o in objs:
        me = o.data; base = len(allv)
        vco = [to_design(o.matrix_world @ v.co) - off for v in me.vertices]
        vn = [to_design(o.matrix_world.to_3x3() @ v.normal).normalized() for v in me.vertices]
        rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
        allv += vco
        for poly, r in zip(me.polygons, rid):
            allf.append([base + i for i in poly.vertices]); freg.append(r)
        per.append((o, vco, vn, rid))
    bvh = BVHTree.FromPolygons([tuple(v) for v in allv], allf, all_triangles=False, epsilon=0.0)
    stats = {"corners": 0, "faces": 0, "hiddenFaces": 0}
    for o, vco, vn, rid in per:
        me = o.data
        uv0 = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")
        mir = []
        for p, n in zip(vco, vn):
            sg = 1.0 if p.x >= 0 else -1.0
            mir.append((V(abs(p.x), p.y, p.z), V(n.x * sg, n.y, n.z)))
        seen = []
        for m, nm in mir:
            if nm.x < 0.12:
                seen.append(None); continue
            hit = bvh.ray_cast(m + V(0.00035, 0, 0) + nm * 0.00015, V(1, 0, 0), 10.0)
            seen.append(hit[2])
        flags = []
        for fi, poly in enumerate(me.polygons):
            stats["faces"] += 1
            ok = True
            for vi in poly.vertices:
                m, nm = mir[vi]
                if nm.x < 0.12:
                    ok = False; break
                h = seen[vi]
                if h is not None and freg[h] != rid[fi]:
                    ok = False; break
            flags.append(0 if ok else 1)
            stats["hiddenFaces"] += 0 if ok else 1
            for li in poly.loop_indices:
                m, nm = mir[me.loops[li].vertex_index]
                stats["corners"] += 1
                nX, nY = -nm.z, nm.y
                uv0.data[li].uv = to_uv(-m.z - nX * inset, m.y - nY * inset)
        at = me.attributes.get("st_hidden") or me.attributes.new("st_hidden", 'INT', 'FACE')
        at.data.foreach_set("value", flags)
        me.uv_layers.active = uv0
    return stats


def side_texels(id_png, ids, chars):
    """Faces flagged st_hidden (side-view characters) and their eyelids take one texel: the deepest pixel of their own
    (character, region) in the printed ID render."""
    import numpy as np
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(img)
    rgb = np.round(px[..., :3] * 255).astype(np.int64)
    key = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    alpha = px[..., 3] > 0.5
    uvs = {}
    for ch in chars:
        for reg in sorted({e["region"] for e in ids if e["char"] == ch}):
            keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids if e["char"] == ch and e["region"] == reg]
            m = np.isin(key, keys) & alpha
            if not m.any():
                continue
            last = m
            while m.any():
                last = m; e = m.copy()
                e[1:, :] &= m[:-1, :]; e[:-1, :] &= m[1:, :]; e[:, 1:] &= m[:, :-1]; e[:, :-1] &= m[:, 1:]
                m = e
            ys, xs = np.nonzero(last)
            k = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
            uvs[(ch, reg)] = ((xs[k] + 0.5) / W, (ys[k] + 0.5) / H)
    n = 0; missing = set()
    for o in all_meshes():
        ch = o.name.split("_")[0]
        if ch not in chars or not o.data.attributes.get("st_hidden"):
            continue
        me = o.data
        rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
        hh = [0] * len(me.polygons); me.attributes["st_hidden"].data.foreach_get("value", hh)
        uv0 = me.uv_layers["UVMap"]
        for poly, r, h in zip(me.polygons, rr, hh):
            reg = REGIONS[r - 1].split(".")[1]
            if not h and not o.name.endswith("_eyelids"):
                continue
            uv = uvs.get((ch, reg))
            if uv is None:
                missing.add(f"{ch}.{reg}"); continue
            for li in poly.loop_indices:
                uv0.data[li].uv = uv
            n += 1
    return {"facesTexel": n, "texels": {f"{c}.{r}": [round(u, 5), round(v, 5)] for (c, r), (u, v) in uvs.items()},
            "regionsNotPrinted": sorted(missing)}


def side_rotate(rig, on):
    """Turn a side-view rig so its left side faces the front ortho camera (local +X -> world +Z design, nose to -X)."""
    rig.rotation_euler = (0, 0, math.radians(-90) if on else 0.0)
    bpy.context.view_layer.update()


def build_character(ch):
    if ch not in QUADS:
        return _MI["build_character"](ch)
    C = Ctx(ch)
    BUILDERS[ch](C)
    order = bone_list(ch)
    assert set(order) == set(C.B.keys()), (ch, set(order) ^ set(C.B.keys()))
    sheet = SHEET[ch]
    rig = make_armature(f"{ch}_rig", C.B, order)
    rig.location = (sheet[0], 0, sheet[1]); bpy.context.view_layer.update()
    objs = []
    face_obj = None
    for pt in C.parts:
        o = make_part_object(C, ch, pt, sheet, rig)
        objs.append((o, pt))
        if pt["name"] == C.lid_part:
            face_obj = o
    lid = dict(name="eyelids", cage=eyelid_cage(C, face_obj, sheet), rigid="eyelids", subdiv=0, piece_as=C.lid_part)
    objs.append((make_part_object(C, ch, lid, sheet, rig), lid))
    for o, pt in objs:
        finish_uv1_and_jaw(C, ch, o, pt, sheet)
    body = [o for o, pt in objs if not pt.get("rigid")]
    props = [o for o, pt in objs if pt.get("rigid")]
    bpy.ops.object.select_all(action='DESELECT')
    for o in body: o.select_set(True)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.object.join()
    bodyo = bpy.context.view_layer.objects.active; bodyo.name = f"{ch}_body"; bodyo.data.name = f"{ch}_body"
    bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
    bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
    am = bodyo.modifiers.new("Armature", 'ARMATURE'); am.object = rig
    for b in bone_list(ch):
        if not bodyo.vertex_groups.get(b) and b not in PROPS[ch] and b != "eyelids":
            bodyo.vertex_groups.new(name=b)
    to_uv = lambda X, Y: (X + sheet[0] + 0.5, (Y + sheet[1]) / ART_H)
    stats = side_uv([bodyo] + props, sheet, to_uv, INSET)
    rep = {"regions": {}, "parts": {}, "uvStats": stats}
    for o in [bodyo] + props:
        me = o.data; rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
        pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
        for poly, r, pp in zip(me.polygons, rid, pid):
            reg = REGIONS[r - 1].split(".")[1]
            d = rep["regions"].setdefault(reg, {"parts": set(), "bb": [9, 9, -9, -9]})
            d["parts"].add(PIECES[pp - 1][1])
            if o.name.endswith("_eyelids") or is_hidden_prop(o):
                continue
            for vi in poly.vertices:
                p = to_design(o.matrix_world @ me.vertices[vi].co)
                p = V(sheet[0] - (p.z), p.y, 0)
                bb = d["bb"]; bb[0] = min(bb[0], p.x); bb[1] = min(bb[1], p.y); bb[2] = max(bb[2], p.x); bb[3] = max(bb[3], p.y)
    return C, rig, bodyo, props, rep


def seat_height(body, rig):
    """Top of the blanket straight above the root (rest pose), rig-local y."""
    dg = bpy.context.evaluated_depsgraph_get()
    ev = body.evaluated_get(dg); me = ev.to_mesh()
    vs = [to_design(body.matrix_world @ v.co) for v in me.vertices]
    bvh = BVHTree.FromPolygons([tuple(v) for v in vs], [tuple(p.vertices) for p in me.polygons])
    ev.to_mesh_clear()
    o = to_design(rig.matrix_world.translation)
    hit = bvh.ray_cast(V(o.x, 0.5, o.z), V(0, -1, 0), 1.0)
    return round(hit[0].y - o.y, 4) if hit[0] else None


# =============================================================================================== modes
def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {"chars": {}, "sheet": {ch: SHEET[ch] for ch in ONLY}, "sheetSource": SHEET_SRC, "artHeight": ART_H}
    built = {}
    for ch in ONLY:
        C, rig, body, props, rep = build_character(ch)
        built[ch] = (C, rig, body, props, rep)
        tris = tri_count([body] + props)
        report["chars"][ch] = {"tris": tris, "bodyTris": tri_count([body]),
                               "props": {o.name: [o.parent_bone, tri_count([o])] for o in props},
                               "bones": [b.name for b in rig.data.bones], "uvStats": rep["uvStats"]}
        if ch in QUADS:
            report["chars"][ch]["seatY"] = seat_height(body, rig)
        print(f"[{ch}] tris={tris} body={tri_count([body])} props={[(o.name, tri_count([o])) for o in props]}"
              + (f" seat={report['chars'][ch]['seatY']}" if ch in QUADS else ""))
    for ch in QUADS:
        if ch in built:
            side_rotate(built[ch][1], True)
    ids = id_render("id_2x")
    jp = os.path.join(WORK, "id_2x.json"); jd = json.load(open(jp))
    jd["note"] = ("front-ortho ID render of the rest pose at sheet positions (2000 px = art width); background = alpha 0; "
                  "eyelids and hidden props hidden; the donkey is drawn in side view (its left side, nose to -X)")
    json.dump(jd, open(jp, "w"), indent=1)
    anchor_info = apply_pixel_anchors(os.path.join(WORK, "id_2x.png"), ids)
    report["donkeyTexels"] = side_texels(os.path.join(WORK, "id_2x.png"), ids, [c for c in QUADS if c in built])
    report["uvFixByIdRender"] = fix_uvs_by_id(os.path.join(WORK, "id_2x.png"), ids)
    for ch in QUADS:
        if ch in built:
            side_rotate(built[ch][1], False)
    # ---- regions_characters.json
    regions_out = {"version": 1, "generatedBy": "pipeline/ls_characters.py",
                   "note": "Per character: colourable regions (face attribute st_region), the mesh parts that carry "
                           "them, demo colour, bbox on the sheet (x, y in art units, y up from the art rect bottom; the "
                           "donkey's in side view, nose to -X), and anchors (regions too small to colour, or with a "
                           "fixed colour, take a constant UV inside a larger region and print as detail lines). ID "
                           "render for the line art: id_characters_2x.png/.json. Jesus and Peter are the Real Miracles "
                           "designs (pipeline/mi_characters.py builders, unchanged) plus this pack's props. The five "
                           "extras are not printed (offSheet).",
                   "sheet": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in ONLY},
                   "sheetSource": SHEET_SRC, "artHeightUnits": ART_H, "characters": {}}
    for ch in ONLY:
        C, rig, body, props, rep = built[ch]
        regs = {}; allbb = [9, 9, -9, -9]
        quad = ch in QUADS
        for reg, d in rep["regions"].items():
            bb = [round(v, 4) for v in d["bb"]]
            if bb[0] < 9 and reg not in SWATCHES.get(ch, {}):
                allbb = [min(allbb[0], bb[0]), min(allbb[1], bb[1]), max(allbb[2], bb[2]), max(allbb[3], bb[3])]
            zh, en = REGION_NAMES.get(reg, (reg, reg))
            regs[reg] = {"id": REGIONS.index(f"{ch}.{reg}") + 1, "hex": PALETTE[ch].get(reg), "zh": zh, "en": en,
                         "parts": sorted(d["parts"]), "bboxSheet": bb if bb[0] < 9 else None}
            if reg in SWATCHES.get(ch, {}):
                regs[reg]["fixedColour"] = True
            ai = anchor_info.get(ch, {})
            for kind in ("anchors", "propAnchors"):
                if reg in ai.get(kind, {}):
                    an = ai[kind][reg]
                    regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
                    sp = SET_PROP_ANCHORS.get(f"{ch}/{reg}")
                    if kind == "propAnchors" and sp and an["target"] == "design.json propUV":
                        regs[reg]["anchoredTo"] = "set." + sp["region"][-1]       # the set region it samples
                        regs[reg]["anchorSource"] = "design.json set.propAnchors"
                    if kind == "propAnchors" and PROPS[ch].get(reg):
                        regs[reg]["printNote"] = ("printed with the figure as line art; coloured from the set region at "
                                                  "anchorUV (design.json set.propAnchors)")
                    elif kind == "propAnchors":
                        regs[reg]["printNote"] = ("hidden-by-default prop, not printed with the figure; takes the "
                                                  "colour at anchorUV (override: design.json characters.%s.propUV.%s)"
                                                  % (ch, reg))
                    elif regs[reg].get("fixedColour"):
                        regs[reg]["printNote"] = "fixed colour from the face decal (UV1 swatch); print as detail lines"
                    else:
                        regs[reg]["printNote"] = "printed with the figure; takes the colour at anchorUV"
        entry = {
            ("size" if quad else "height"): (DONKEY_SIZE if quad else CONTRACT_HEIGHT[ch]),
            "bboxSheet": [round(v, 4) for v in allbb], "regions": regs,
            "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                          "projection": "front",
                          "swatches": {k: [round(x, 3) for x in v] for k, v in SWATCHES.get(ch, {}).items()},
                          "files": {e: os.path.relpath(face_file(ch, e), ROOT) for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": ({"pose": "standing on all fours", "facing": "+Z (nose toward the viewer)",
                          "root": "on the ground under the belly centre (= under the seat)",
                          "seatY": report["chars"][ch].get("seatY")} if quad else
                         {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z"}),
            "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                      for b, v in PROPS[ch].items()},
            "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
        if quad:
            entry["projection"] = {"kind": "side", "note": "UV0 = the donkey's left side seen from +X: u = -z + sheetX + "
                                   "0.5, v = (y + sheetY) / artH (x mirrored to |x|, so both sides share the drawing); "
                                   "faces not seen from the side take one clean texel of their own region"}
        regions_out["characters"][ch] = entry
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
    if set(CHARS) <= set(ONLY):
        shutil.copy(os.path.join(WORK, "id_2x.png"), os.path.join(MODEL, "id_characters_2x.png"))
        shutil.copy(os.path.join(WORK, "id_2x.json"), os.path.join(MODEL, "id_characters_2x.json"))
    # ---- final material, export (character-local), blend
    page = page_material()
    for o in all_meshes():
        me = o.data; me.materials.clear(); me.materials.append(page)
        me.polygons.foreach_set("material_index", [0] * len(me.polygons))
    for o in all_meshes():                       # TEXCOORD_0 = page (UVMap), TEXCOORD_1 = face decal
        assert [u.name for u in o.data.uv_layers][:2] == ["UVMap", "decal"], (o.name, [u.name for u in o.data.uv_layers])
        o.data.uv_layers.active_index = 0
        o.data.uv_layers["UVMap"].active_render = True
    for ch in ONLY:
        C, rig, body, props, rep = built[ch]
        rig.location = (0, 0, 0); bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        for o in rig.children: o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"), use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=False, export_def_bones=False,
                                  export_texcoords=True, export_materials='EXPORT', export_morph=False)
        rig.location = (SHEET[ch][0], 0, SHEET[ch][1])
    bpy.context.view_layer.update()
    report["partTris"] = PART_TRIS
    json.dump(report, open(os.path.join(WORK, "build_report.json"), "w"), indent=1, default=str)
    sc()[REGIONS_KEY] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({ch: {k: v for k, v in r.items() if k != "bones"} for ch, r in report["chars"].items()}))
    if os.environ.get("LS_NO_EXTRAS") != "1":
        import subprocess
        subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "--python-exit-code", "1", "--python",
                        os.path.abspath(__file__), "--", "extras"], check=True)


def friend_paint_material():
    """ls_extras_paint: Principled BSDF with model/extras_paint.png on UV0 (embedded in the extras' GLBs)."""
    m = bpy.data.materials.get("ls_extras_paint") or bpy.data.materials.new("ls_extras_paint")
    m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.8
    img = bpy.data.images.load(EXTRAS_PAINT, check_existing=True)
    t = nt.nodes.get("paint") or nt.nodes.new("ShaderNodeTexImage"); t.name = "paint"; t.image = img
    uvn = nt.nodes.get("uv0") or nt.nodes.new("ShaderNodeUVMap"); uvn.name = "uv0"; uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


EXTRA_LOOK = {"john": "the youngest: beardless, short wavy light-brown hair, sky-blue tunic, white sash (sash1)",
              "james": "John's big brother: broad, short black hair and beard, leaf-green tunic, brown cloak over the "
                       "left shoulder (cloak1)",
              "andrew": "Peter's little brother: lanky, curly black hair, neat beard, mustard tunic, Peter's blue-grey "
                        "head cloth (cloth1 = its tail)",
              "seller1": "the dove seller: round, bald with a black fringe, rosy cheeks, orange tunic, cream-and-brown "
                         "striped apron (apron1)",
              "seller2": "the money changer: thin, long nose, little pointed beard, tall dark-red felt cap, plum robe, "
                         "fat money pouch (pouch)"}


def mode_extras():
    """The five extras: built on a virtual page (EXTRA_PAGE), front ID render -> painted texture model/extras_paint.png,
    UV0 remapped into that texture, GLBs, then appended to characters.blend (rigs at EXTRA_BLEND, off the page)."""
    global ONLY
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ONLY = list(EXTRAS)
    SHEET.update({f: list(EXTRA_PAGE[f]) for f in EXTRAS})
    built = {}
    for ch in EXTRAS:
        C, rig, body, props, rep = build_character(ch)
        built[ch] = (C, rig, body, props)
        print(f"[{ch}] tris={tri_count([body] + props)} body={tri_count([body])}")
    ids = id_render("extras_id_2x")
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
        info[ch] = {"height": CONTRACT_HEIGHT[ch], "paint": "assets/lastsupper/model/extras_paint.png",
                    "uv0": "paint texture", "look": EXTRA_LOOK[ch], "blendRigLocation": list(EXTRA_BLEND[ch]),
                    "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                                  "files": {e: os.path.relpath(face_file(ch, e), ROOT) for e in EXPRESSIONS[ch]},
                                  "clipExpression": CLIP_EXPRESSION[ch],
                                  "note": "one drawing per expression for the group (disciples / sellers), brows "
                                          "re-coloured per person"},
                    "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                              "closed": C.lid["closedScale"]},
                    "extraBones": {b: EXTRA_PARENTS[b] for b in EXTRA_BONES[ch]},
                    "colours": PALETTE[ch], "tris": tri_count([body] + props)}
    bpy.context.view_layer.update()
    tmp = os.path.join(WORK, "extras.blend")
    sc()[REGIONS_KEY + "_extras"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True)
    rp = os.path.join(MODEL, "regions_characters.json")
    if os.path.exists(rp):
        rj = json.load(open(rp)); rj["offSheet"] = info
        rj["offSheetNote"] = ("the five extras: not printed; UV0 samples model/extras_paint.png (fixed demo-palette paint, "
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


# =============================================================================================== previews
class _RegionLookup(dict):
    def __missing__(self, r):
        tab = json.loads(sc().get(REGIONS_KEY, "[]"))
        for i, k in enumerate(tab):
            self[i + 1] = k.split(".")[1]
        return dict.__getitem__(self, r)


REGION_OF = _RegionLookup()


def char_frame(ch):
    if ch in QUADS:
        return 0.27, 0.200, 0.075
    L = landmarks(ch); Hh = CONTRACT_HEIGHT[ch]
    return Hh, (L["top"] + L["chin"]) / 2, L["top"] - L["chin"]


def preview_setup():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    setup_eevee((640, 960)); preview_lights()
    imgs = {}
    for ch in CHARS + EXTRAS:
        p = face_file(ch, DEFAULT_EXPR[ch])
        if os.path.exists(p):
            imgs[ch] = bpy.data.images.load(p, check_existing=True)
    present = [ch for ch in CHARS + EXTRAS if bpy.data.objects.get(f"{ch}_rig")]
    fmat = {f: friend_preview_material(f, imgs.get(f)) for f in EXTRAS if f in present}
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        if ch in EXTRAS:
            o.data.materials.clear(); o.data.materials.append(fmat[ch])
            o.data.polygons.foreach_set("material_index", [0] * len(o.data.polygons)); continue
        set_face_materials(o, lambda p, r: r, lambda r, ch=ch: preview_material(ch, REGION_OF[r], imgs.get(ch)))
    return imgs


def mode_preview():
    imgs = preview_setup()
    present = [ch for ch in CHARS + EXTRAS if bpy.data.objects.get(f"{ch}_rig")]
    cam = camera()
    for ch in present:
        show([ch])
        rig = bpy.data.objects[f"{ch}_rig"]; x = rig.location.x; zb = rig.location.z
        Hh, hy0, Hd = char_frame(ch)
        hy = zb + hy0
        quad = ch in QUADS
        if quad:
            sc().render.resolution_x, sc().render.resolution_y = 840, 720
            for nm, yaw in (("front", 0), ("q34", 35), ("side", 90), ("back", 180)):
                turntable(cam, Vector((x, 0, zb + 0.13)), yaw, 0.95, 0.10, 60)
                render(os.path.join(WORK, f"pv_{ch}_{nm}.png"))
        else:
            sc().render.resolution_x, sc().render.resolution_y = 640, 960
            for nm, yaw in (("front", 0), ("q34", 35), ("side", 90), ("back", 180)):
                turntable(cam, Vector((x, 0, zb + Hh * 0.50)), yaw, Hh * 3.1, Hh * 0.18, 60)
                render(os.path.join(WORK, f"pv_{ch}_{nm}.png"))
        sc().render.resolution_x, sc().render.resolution_y = 640, 640
        if ch in CHARS:
            turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 30, Hd * 4.6, Hd * 0.25, 60); render(os.path.join(WORK, f"pv_{ch}_head.png"))
            turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 0, Hd * 4.6, Hd * 0.10, 60); render(os.path.join(WORK, f"pv_{ch}_headfront.png"))
            if not quad:
                for s_ in "LR":
                    pb = rig.pose.bones["fingers" + s_]; tgt = rig.matrix_world @ pb.head
                    turntable(cam, tgt, 25 if s_ == "L" else -25, SPEC[ch]["hand"] * 4.6, SPEC[ch]["hand"] * 0.6, 60)
                    render(os.path.join(WORK, f"pv_{ch}_hand{s_}.png"))
            show([ch], props=True)
            if quad:
                turntable(cam, Vector((x, 0, zb + 0.13)), 55, 0.80, 0.45, 60)
            else:
                turntable(cam, Vector((x, 0, zb + Hh * 0.45)), 28, Hh * 2.6, Hh * 0.45, 60)
            render(os.path.join(WORK, f"pv_{ch}_props.png"))
            show([ch])
        sc().render.resolution_x, sc().render.resolution_y = 420, 420
        for e in EXPRESSIONS[ch]:
            set_decal(ch, bpy.data.images.load(face_file(ch, e), check_existing=True))
            if quad:
                turntable(cam, Vector((x, 0, hy - 0.01)), 18, 0.30, 0.03, 60)
            else:
                turntable(cam, Vector((x, 0, hy - 0.08 * Hd)), 12, Hd * 3.6, Hd * 0.12, 60)
            render(os.path.join(WORK, f"pv_{ch}_expr_{e}.png"))
        if ch in imgs:
            set_decal(ch, imgs[ch])
    cast = [c for c in CHARS if c in present]
    if len(cast) > 1:
        show(cast)
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1000
        turntable(cam, Vector((-0.04, 0.03, 0.20)), 10, 1.6, 0.20, 50); render(os.path.join(WORK, "pv_all.png"))
        turntable(cam, Vector((-0.04, 0.03, 0.16)), 18, 1.45, 1.10, 50); render(os.path.join(WORK, "pv_all_phone.png"))
    fr = [f for f in EXTRAS if f in present]
    if fr:
        show(fr)
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1000
        cx = sum(EXTRA_BLEND[f][0] for f in fr) / len(fr)
        turntable(cam, Vector((cx, 0.0, 0.19)), 0, 1.7, 0.16, 50); render(os.path.join(WORK, "pv_extras_line.png"))
        turntable(cam, Vector((cx, 0.0, 0.19)), 35, 1.7, 0.30, 50); render(os.path.join(WORK, "pv_extras_lineq.png"))
    print("PREVIEW done")


# =============================================================================================== pose tests
def pose_test(rig, ch, variant="a"):
    if ch in ("jesus", "peter"):
        return _MI["pose_test"](rig, ch, variant)
    pose_reset(rig)
    if variant == "none":
        return
    if ch in QUADS:
        if variant == "a":                               # head up, jaw open, near foreleg lifted, ears back, tail swish
            bend(rig, "neck", V(1, 0, 0), -14); bend(rig, "head", V(1, 0, 0), -16); bend(rig, "jaw", V(1, 0, 0), 20)
            bend(rig, "upperArmL", V(1, 0, 0), -35); bend(rig, "forearmL", V(1, 0, 0), 70)
            bend(rig, "earL", V(1, 0, 0), 30); bend(rig, "earR", V(0, 0, 1), -25)
            bend(rig, "tail1", V(0, 1, 0), 30); bend(rig, "tail2", V(0, 1, 0), 30)
            bend(rig, "thighR", V(1, 0, 0), 15); bend(rig, "shinR", V(1, 0, 0), -20)
            rig.pose.bones["eyelids"].scale = (1, 6.0, 1)
        else:                                            # sleepy: head low, ears droop, eyes shut
            bend(rig, "neck", V(1, 0, 0), 28); bend(rig, "head", V(1, 0, 0), 12)
            bend(rig, "earL", V(0, 0, 1), -40); bend(rig, "earR", V(0, 0, 1), 40)
            rig.pose.bones["eyelids"].scale = (1, C_LID_CLOSED.get(ch, 12.0), 1)
        bpy.context.view_layer.update()
        return
    B = {b.name: (to_design(b.head_local), to_design(b.tail_local)) for b in rig.data.bones}
    for side, sg in (("L", 1), ("R", -1)):
        h, t = B["forearm" + side]; d = (t - h).normalized()
        bend(rig, "forearm" + side, d.cross(V(0, 0, 1)) * sg * -1, 65 if side == "L" else 35)
        h, t = B["hand" + side]; dh = (t - h).normalized()
        hz = dh.cross(V(0, 0, 1)).normalized()
        bend(rig, "fingers" + side, hz * (1 if side == "L" else -1), 75)
    bend(rig, "upperArmL", V(1, 0, 0), -45)
    bend(rig, "thighL", V(1, 0, 0), -30); bend(rig, "shinL", V(1, 0, 0), 50)
    bend(rig, "spine", V(1, 0, 0), 10); bend(rig, "head", V(0, 1, 0), 25); bend(rig, "jaw", V(1, 0, 0), 14)
    rig.pose.bones["eyelids"].scale = (1, 6.0 if variant == "a" else C_LID_CLOSED.get(ch, 12.0), 1)
    eb = EXTRA_BONES[ch][0]
    bend(rig, eb, V(1, 0, 0), {"cloth1": -30, "cloak1": 25}.get(eb, -30))
    bpy.context.view_layer.update()


def _min_y(objs, base_z):
    dg = bpy.context.evaluated_depsgraph_get(); m = 9.0
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        m = min(m, min((o.matrix_world @ v.co).z for v in me.vertices))
        ev.to_mesh_clear()
    return round(m - base_z, 4)


def pose_ride(rig, seat_dy=0.0):
    """Jesus astride the donkey (a `ride` fit test, not the clip): hips head at rig-local y 0.035 (+ seat_dy) on base
    RIDE_Y, thighs forward and spread so the knees sit outside the barrel (±0.05), shins down, hands on the knees."""
    pose_reset(rig)
    pb = rig.pose.bones["hips"]; rest = pb.bone.matrix_local
    head = to_design(rest.translation)
    tgt = V(0, 0.035 + seat_dy, -0.008)
    pb.matrix_basis = Matrix.Translation(rest.to_3x3().inverted() @ to_bl(tgt - head))
    bpy.context.view_layer.update()
    for side, sg in (("L", 1), ("R", -1)):
        pose_rot(rig, "thigh" + side, [(V(1, 0, 0), -52), (V(0, 0, 1), 34 * sg)])
        bend(rig, "shin" + side, V(1, 0, 0), 58)
        bend(rig, "foot" + side, V(1, 0, 0), -20)
        pose_rot(rig, "upperArm" + side, [(V(0, 0, 1), -18 * sg), (V(1, 0, 0), -30)])
        bend(rig, "forearm" + side, V(1, 0, 0), -55)
    bend(rig, "mantle1", V(1, 0, 0), 30)
    bpy.context.view_layer.update()


def pose_kneel(rig):
    """Jesus kneeling (kneel_wash fit test, not the clip): the Miracles kneel_kind stance, left knee on the floor, right
    foot forward, torso leaning a little forward, hands toward the basin 0.06 in front."""
    pose_reset(rig)
    s = SPEC["jesus"]
    pb = rig.pose.bones["hips"]; rest = pb.bone.matrix_local
    drop = s["kneeY"] - 0.006
    pb.matrix_basis = Matrix.Translation(rest.to_3x3().inverted() @ to_bl(V(0, -drop, -0.010)))
    bpy.context.view_layer.update()
    bend(rig, "thighL", V(1, 0, 0), 4); bend(rig, "shinL", V(1, 0, 0), 92); bend(rig, "footL", V(1, 0, 0), -40)
    bend(rig, "thighR", V(1, 0, 0), -88); bend(rig, "shinR", V(1, 0, 0), 86); bend(rig, "footR", V(1, 0, 0), 2)
    for side, sg in (("L", 1), ("R", -1)):
        pose_rot(rig, "upperArm" + side, [(V(1, 0, 0), -40), (V(0, 0, 1), -10 * sg)])
        bend(rig, "forearm" + side, V(1, 0, 0), -35)
    bend(rig, "spine", V(1, 0, 0), 14); bend(rig, "head", V(1, 0, 0), 12)
    bpy.context.view_layer.update()


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
        quad = ch in QUADS
        for var in ("a", "b"):
            pose_test(rig, ch, var)
            if quad:
                sc().render.resolution_x, sc().render.resolution_y = 840, 720
                turntable(cam, Vector((rig.location.x, 0, rig.location.z + 0.13)), 40 if var == "a" else 70, 0.95, 0.12, 60)
            else:
                sc().render.resolution_x, sc().render.resolution_y = 640, 960
                Hh = char_frame(ch)[0]
                turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), 20 if var == "a" else 70,
                          Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pose_{ch}_{var}.png"))
        sc().render.resolution_x, sc().render.resolution_y = 540, 540
        Hh, hy0, Hd = char_frame(ch)
        pose_test(rig, ch, "b")
        if quad:
            pose_reset(rig); rig.pose.bones["eyelids"].scale = (1, C_LID_CLOSED.get(ch, 12.0), 1)
            bpy.context.view_layer.update()
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + hy0)), 20, 0.32, 0.03, 60)
        else:
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + hy0)), 25, Hd * 4.2, Hd * 0.1, 60)
        render(os.path.join(WORK, f"pose_{ch}_closed.png"))
        pose_test(rig, ch, "none")
    # ---- the ride pair: Jesus at base RIDE_Y on the donkey's mark (same heading)
    if "donkey" in present and "jesus" in present:
        dk = bpy.data.objects["donkey_rig"]; js = bpy.data.objects["jesus_rig"]
        keep = js.location.copy()
        js.location = (dk.location.x, dk.location.y, dk.location.z + RIDE_Y)
        show(["donkey", "jesus"])
        info = {}
        for nm, dy in (("", 0.0), ("low", -0.006), ("high", 0.006)):
            pose_ride(js, dy)
            body = bpy.data.objects["jesus_body"]
            info["minY" + nm] = _min_y([body], dk.location.z)
            sc().render.resolution_x, sc().render.resolution_y = 960, 720
            if nm:
                turntable(cam, Vector((dk.location.x, 0, dk.location.z + 0.20)), 90, 1.15, 0.10, 60)
                render(os.path.join(WORK, f"ride_{nm}.png")); continue
            for vw, yaw, dist, h in (("side", 90, 1.15, 0.10), ("front", 0, 1.10, 0.12), ("q34", 35, 1.10, 0.25),
                                     ("phone", 15, 1.25, 0.95)):
                turntable(cam, Vector((dk.location.x, 0, dk.location.z + 0.20)), yaw, dist, h, 60)
                render(os.path.join(WORK, f"ride_{vw}.png"))
        out["ride"] = info
        pose_reset(js); js.location = keep
        bpy.context.view_layer.update()
    # ---- the kneel with the basin (at base UPPER), and the props shown
    if "jesus" in present:
        js = bpy.data.objects["jesus_rig"]; keep = js.location.copy()
        js.location = (keep.x, keep.y, keep.z + UPPER)
        show(["jesus"])
        for nm in ("basin", "towel"):
            o = bpy.data.objects.get(f"jesus_{nm}")
            if o:
                o.hide_render = False
        pose_kneel(js)
        out["kneel"] = {"minY": _min_y([bpy.data.objects["jesus_body"]], keep.z + UPPER),
                        "basinMinY": _min_y([bpy.data.objects["jesus_basin"]], keep.z + UPPER)}
        sc().render.resolution_x, sc().render.resolution_y = 960, 720
        for vw, yaw, dist, h in (("kneel_side", 90, 0.85, 0.10), ("kneel_q34", 35, 0.85, 0.25), ("kneel_phone", 15, 1.0, 0.85)):
            turntable(cam, Vector((js.location.x, 0, js.location.z + 0.10)), yaw, dist, h, 60)
            render(os.path.join(WORK, f"ride_{vw}.png"))
        if "john" in present:                            # the kneel pair: Jesus 0.11 in front of a seated disciple
            jn = bpy.data.objects["john_rig"]; kj = jn.location.copy()
            jn.location = (js.location.x, js.location.y - 0.11, js.location.z)   # facing Jesus, on the floor
            jn.rotation_euler = (0, 0, math.radians(180))
            pose_reset(jn)
            pbh = jn.pose.bones["hips"]; rest = pbh.bone.matrix_local
            sp = SPEC["john"]
            pbh.matrix_basis = Matrix.Translation(rest.to_3x3().inverted() @ to_bl(V(0, -(sp["hipY"] - 0.052), 0.0)))
            bpy.context.view_layer.update()
            for side in "LR":
                bend(jn, "thigh" + side, V(1, 0, 0), -88); bend(jn, "shin" + side, V(1, 0, 0), 60)
            show(["jesus", "john"])
            for nm in ("basin", "towel"):
                bpy.data.objects[f"jesus_{nm}"].hide_render = False
            turntable(cam, Vector((js.location.x, 0, js.location.z + 0.08)), 70, 1.0, 0.30, 60)
            render(os.path.join(WORK, "ride_seated_wash.png"))
            pose_reset(jn); jn.location = kj; jn.rotation_euler = (0, 0, 0)
        pose_reset(js); js.location = keep
        bpy.context.view_layer.update()
        for ch in ("jesus", "peter"):
            rig = bpy.data.objects.get(f"{ch}_rig")
            if not rig:
                continue
            show([ch], props=True)
            Hh = CONTRACT_HEIGHT[ch]
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.45)), 30, Hh * 2.4, Hh * 0.35, 60)
            render(os.path.join(WORK, f"ride_props_{ch}.png"))
    json.dump(out, open(os.path.join(WORK, "posetest.json"), "w"), indent=1)
    print("POSETEST done", json.dumps(out))


# =============================================================================================== uv check, verify
def mode_uvcheck():
    """Models wearing $LS_WORK/uvproof.png (or $LS_UV_TEXTURE) through UV0: front ortho with the donkey turned to its side
    (must equal the sheet), 3/4 + back perspective, the donkey left / right / top / front."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get(ENV + "UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        if o.name.split("_")[0] in EXTRAS:
            o.hide_render = True; continue
        o.data.materials.clear(); o.data.materials.append(m)
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    sc().view_settings.view_transform = 'Standard'
    cam = front_ortho_camera()
    dk = bpy.data.objects.get("donkey_rig")
    if dk:
        side_rotate(dk, True)
    for nm_ in ("backdrop", "floor"):
        if bpy.data.objects.get(nm_):
            bpy.data.objects[nm_].hide_render = True
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    if dk:
        side_rotate(dk, False)
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = False
    for nm_ in ("backdrop", "floor"):
        if bpy.data.objects.get(nm_):
            bpy.data.objects[nm_].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc().render.resolution_x, sc().render.resolution_y = 1600, 900
    for nm, yaw in (("q34", 30), ("back", 180)):
        turntable(cam, Vector((-0.04, 0, 0.19)), yaw, 1.45, 0.16, 50)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    if dk:
        for o in all_meshes():
            if o.name not in ("floor", "backdrop"):
                o.hide_render = not o.name.startswith("donkey_") or o.name.endswith("_eyelids")
        sc().render.resolution_x, sc().render.resolution_y = 1000, 800
        for nm, yaw, h in (("dkL", 90, 0.08), ("dkR", -90, 0.08), ("dkTop", 30, 0.60), ("dkFront", 0, 0.08)):
            turntable(cam, Vector((dk.location.x, 0, dk.location.z + 0.13)), yaw, 0.95, h, 50)
            render(os.path.join(WORK, f"uv_{nm}.png"))
    print("UVCHECK done")


def mode_verify():
    out = {}
    for ch in CHARS + EXTRAS:
        p = os.path.join(MODEL, f"{ch}.glb")
        if not os.path.exists(p):
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=p)
        arms = [o for o in sc().objects if o.type == 'ARMATURE']
        meshes = [o for o in sc().objects if o.type == 'MESH' and o.name.startswith(ch)]
        bones = sorted(b.name for b in arms[0].data.bones) if arms else []
        want = sorted(bone_list(ch))
        parents = {b.name: (b.parent.name if b.parent else None) for b in arms[0].data.bones} if arms else {}
        exp = dict(EXTRA_PARENTS); exp["towel"] = TOWEL_PARENT.get(ch)
        bad_par = {b: parents.get(b) for b in EXTRA_BONES[ch] if parents.get(b) != exp[b]}
        info = {"armatures": len(arms), "bonesMatch": bones == want, "missing": sorted(set(want) - set(bones)),
                "extra": sorted(set(bones) - set(want)), "parents": parents, "parentsOK": not bad_par,
                "badParents": bad_par, "actions": len(bpy.data.actions), "meshes": {}}
        tris = 0; maxinf_all = 0
        for o in meshes:
            t = sum(len(p.vertices) - 2 for p in o.data.polygons); tris += t
            maxinf = max((sum(1 for g in v.groups if g.weight > 0) for v in o.data.vertices), default=0)
            maxinf_all = max(maxinf_all, maxinf)
            uvl = o.data.uv_layers
            n0 = len(uvl[0].data)
            u0 = [uvl[0].data[i].uv for i in range(0, n0, max(1, n0 // 2000))]
            u1 = [uvl[1].data[i].uv for i in range(0, n0, max(1, n0 // 2000))] if len(uvl) > 1 else []
            layer0_page = all(-0.01 <= a.x <= 1.01 and -0.01 <= a.y <= 1.01 for a in u0)
            layer1_decal = (len(u1) > 0 and (any(a.x < -0.5 for a in u1) or
                                             all(0.0 <= a.x <= 1.0 and 0.0 <= a.y <= 1.0 for a in u1)))
            info.setdefault("uvOrderOK", True)
            info["uvOrderOK"] &= layer0_page and layer1_decal
            info["meshes"][o.name] = {"skinned": any(m.type == 'ARMATURE' for m in o.modifiers),
                                      "parentBone": o.parent_bone or None, "tris": t,
                                      "uvLayers": [u.name for u in o.data.uv_layers], "maxInfluences": maxinf,
                                      "materials": [m.name for m in o.data.materials if m]}
        info["tris"] = tris; info["maxInfluences"] = maxinf_all
        info["budget"] = BUDGET[ch]; info["trisUnderBudget"] = tris <= BUDGET[ch]
        pts = [(o.matrix_world @ v.co) for o in meshes if not o.name.endswith("_eyelids") and not
               (o.parent_bone and PROPS.get(ch, {}).get(o.parent_bone) is False) for v in o.data.vertices]
        info["heightTop"] = round(max(p.z for p in pts), 4)
        info["minY"] = round(min(p.z for p in pts), 4)
        info["heightErrPct"] = round(100 * (info["heightTop"] - CONTRACT_HEIGHT[ch]) / CONTRACT_HEIGHT[ch], 2)
        if ch in QUADS:
            body = [o for o in meshes if o.name == f"{ch}_body"][0]
            vs = [to_design(body.matrix_world @ v.co) for v in body.data.vertices]
            bvh = BVHTree.FromPolygons([tuple(v) for v in vs], [tuple(pl.vertices) for pl in body.data.polygons])
            hit = bvh.ray_cast(V(0, 0.5, 0), V(0, -1, 0), 1.0)
            info["seatY"] = round(hit[0].y, 4) if hit[0] else None
            info["noseZ"] = round(max(v.z for v in vs), 4); info["rumpZ"] = round(min(v.z for v in vs if v.y > 0.09), 4)
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps({c: {k: v for k, v in i.items() if k not in ("meshes", "parents")} for c, i in out.items()}))


if __name__ == "__main__":
    {"build": mode_build, "extras": mode_extras, "preview": mode_preview, "posetest": mode_posetest,
     "verify": mode_verify, "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), os.path.abspath(__file__), "all"],
                                                 check=True)}[argv[0] if argv else "build"]()
