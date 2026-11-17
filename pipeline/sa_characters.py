"""Saul Sees the Light! (story pack `saul`): characters ananias, saul, barnabas (printed) + judas, priest, tallguard,
shortguard, peter (fixed paint, not on the sheet) — meshes, rigs, weights, UVs, face decals, previews, GLBs.

Contract: docs/saul/CONTRACT.md §1-§4 (ids, sizes, sheet slots, bone names, props), look: docs/saul/DESIGN.md §1 and
§3, notes for Animation: docs/saul/RIG.md.

Reuse, never fork (CONTRACT §2, R5): this script runs pipeline/rs_characters.py (He Is Risen!) in its own namespace
(definitions only, the way story_kit.include works; `_run_risen` below). rs_characters.py runs ls_characters.py, which
runs mi_characters.py, the same way, so every Real Miracles / The King Who Serves / He Is Risen! definition is ours:
  * peter: He Is Risen!'s `build_peter_rs` = the Miracles `build_peter`, unchanged, `bucket` mesh dropped (bone kept);
    fixed paint (his front ID render on a virtual page becomes part of model/extras_paint.png, Miracles demo colours);
  * every other man is the Miracles friend body (`build_friend`, unchanged) with this pack's costume parts on top:
    - saul: short dark hair, short neat beard, deep-red robe to the shins, wide brown belt with a pouch, dark-blue
      travel cloak over both shoulders and down the back (cloak1); props letters / bread (handR) and the basket rig
      (bone basket from hips, bone ropeTop from root, mesh saul_ropes skinned to both);
    - ananias: small and round, bald with a grey fringe and round beard, small brown cap, moss-green robe to the
      ankles, mustard shawl over both shoulders; prop jug (handR);
    - barnabas: big, black curly hair, full black beard, terracotta robe to the shins, wide dark-green sash, cream mantle
      over the left shoulder (mantle1);
    - judas: short brown beard, striped blue-and-white head cloth, sand tunic, brown apron-sash; prop bread (handR);
    - priest: long white beard, white turban, white robe to the ankles, blue over-robe with a gold hem band;
    - tallguard / shortguard: a comic pair in grey-blue tunics with rust sashes and travel bags on the back; the tall
      one long and thin with a tall pointed cap and a thin moustache (prop lantern, handR), the short one round with a
      flat cap and a bushy black beard.
  The robe-length change re-runs the kit `build_robe` with the friend's own numbers and a lower hem (`_long_robe`).
None of mi_*.py / ls_*.py / rs_*.py / story_kit is edited. Face decals: Peter's existing drawings are copied
(Miracles: jolly talk shock laugh; He Is Risen!: sad); everything else is drawn with the same patched Miracles drawing
code (the friend base look; Judas's and the guards' group expressions use the same parameters as the earlier packs'
group drawings, re-coloured brows).

Run (repo root):
  python3 pipeline/sa_characters.py all                                           # everything below, in order
  python3 pipeline/sa_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python-exit-code 1 --python pipeline/sa_characters.py -- build    # cast + extras
  blender ... -- extras        # the five extras only (run by build)
  python3 pipeline/sa_characters.py proof                                         # $SA_WORK/uvproof.png
  blender ... -- preview       # lit demo-palette renders
  blender ... -- uvcheck       # models wearing uvproof.png
  blender ... -- posetest      # bend / blink / jaw / cloth, props shown, the basket at the window and lowered
  blender ... -- verify        # re-import GLBs, check bones / parents / budget / heights / rope skin
  python3 pipeline/sa_characters.py compose                                       # preview_*.png contact sheets
Blender: $BLENDER, else `blender` on PATH, else /Applications/Blender.app. Intermediate renders go to $SA_WORK
(default /tmp/saul_characters/work). SA_ONLY=saul (comma list) builds a subset of the printed cast (debug only).
"""
import sys, os, json, math, random, shutil, struct

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SA_WORK = os.environ.get("SA_WORK", "/tmp/saul_characters/work")
os.environ["RS_WORK"] = SA_WORK          # rs (and through it ls, mi) create their WORK folder at import: keep it in ours
os.environ["LS_WORK"] = SA_WORK
RS_PATH = os.path.join(HERE, "rs_characters.py")
RS_FACES = os.path.join(ROOT, "docs/risen/design/faces")
RS_SRC = open(RS_PATH, encoding="utf-8").read()
SA_FILE = os.path.abspath(__file__)


def _run_risen():
    """Run pipeline/rs_characters.py in this module's namespace (it runs ls, which runs mi, the same way): every
    definition becomes ours. Its mode dispatch only runs under __main__, so nothing is built; outside Blender it stops
    with SystemExit after its Pillow part (caught)."""
    g = globals()
    keep = {k: g.get(k) for k in ("__name__", "__file__", "__doc__")}
    g["__name__"] = "rs_characters"; g["__file__"] = RS_PATH
    try:
        exec(compile(RS_SRC, RS_PATH, "exec"), g)
    except SystemExit:
        pass
    finally:
        g.update(keep)


_run_risen()
_RS = {k: globals()[k] for k in ("build_peter_rs", "rs_face_params", "draw_faces", "compose", "pose_test")
       if k in globals()}
_ls_build_character = build_character                                   # noqa: F821 (ls / mi, run above)
__file__ = SA_FILE

# ---------------------------------------------------------------------------------------------- this pack
MODEL = os.path.join(ROOT, "assets/saul/model")
FACES = os.path.join(ROOT, "docs/saul/design/faces")
WORK = SA_WORK
ENV = "SA_"
PAGE_MATERIAL = "sa_page"
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/saul/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

CHARS = ("ananias", "saul", "barnabas")             # printed cast, sheet order left -> right
EXTRAS = ("judas", "priest", "tallguard", "shortguard", "peter")
MEN = CHARS + EXTRAS[:4]                             # the friend-body men (everyone but Peter)
DISCIPLES = (); WOMEN = (); FRIENDS = (); SELLERS = (); QUADS = (); FISH = ()
HUMANS = CHARS + EXTRAS
EXTRA_BONES = {"saul": ["cloak1", "letters", "bread", "basket", "ropeTop"], "ananias": ["jug"],
               "barnabas": ["mantle1"], "judas": ["bread"], "priest": [], "tallguard": ["lantern"],
               "shortguard": [], "peter": ["cloth1", "bucket"]}
EXTRA_PARENTS = {"cloak1": "chest", "letters": "handR", "bread": "handR", "basket": "hips", "ropeTop": "root",
                 "jug": "handR", "mantle1": "chest", "lantern": "handR", "cloth1": "head", "bucket": "handR"}
TOWEL_PARENT = {}
CLOTH_BEND = {"cloak1": 25, "mantle1": 20, "cloth1": -30}     # pose test: swing of the cloth bone (deg about X)


def bone_list(ch):
    return CONTRACT_BONES + EXTRA_BONES[ch]                             # noqa: F821


PROPS = {"saul": {"letters": False, "bread": False, "basket": False}, "ananias": {"jug": False}, "barnabas": {},
         "judas": {"bread": False}, "priest": {}, "tallguard": {"lantern": False}, "shortguard": {}, "peter": {}}
CONTRACT_HEIGHT = {"ananias": 0.33, "saul": 0.37, "barnabas": 0.39, "judas": 0.35, "priest": 0.36, "tallguard": 0.41,
                   "shortguard": 0.30, "peter": 0.38}
BUDGET = {"saul": 27000, "ananias": 25000, "barnabas": 25000, "judas": 18000, "priest": 18000, "tallguard": 18000,
          "shortguard": 18000, "peter": 18000}
DEFAULT_SHEET = {"ananias": (-0.32, 0.015), "saul": (0.0, 0.015), "barnabas": (0.32, 0.015)}
# the extras: virtual page for their own ID render (three A-poses at +-0.34 never touch, C2; the rest on a 2nd row)
EXTRA_PAGE = {"judas": (-0.34, 0.015), "priest": (0.0, 0.015), "tallguard": (0.34, 0.015),
              "shortguard": (-0.20, 0.58), "peter": (0.20, 0.58)}
EXTRA_BLEND = {"judas": (0.80, 0.0), "priest": (1.00, 0.0), "tallguard": (1.20, 0.0), "shortguard": (1.40, 0.0),
               "peter": (1.60, 0.0)}
FRIEND_PAGE = EXTRA_PAGE; FRIEND_BLEND = EXTRA_BLEND
EXTRAS_PAINT = os.path.join(MODEL, "extras_paint.png")
FRIEND_PAINT = EXTRAS_PAINT
WING_TOP = 0.0
# the basket rig (CONTRACT §3): rig-local design units
BASKET_D, BASKET_H = 0.10, 0.08                      # across, high
BASKET_DROP = 0.050                                  # basket floor = hips head - this (Saul crouched inside)
ROPE_TOP = (-0.065, 0.235, 0.0)                      # ropeTop head: the window when Saul stands at BASKET_DOWN
WALL_FACE_X = -0.065                                 # the wall's outside face, rig-local at BASKET_DOWN facing +Z

# ---------------------------------------------------------------------------------------------- palette (DESIGN §3)
_SANDAL = "#7A4E2E"
PALETTE = {
    "saul": {"skin": "#D2A07A", "hair": "#3E2A1E", "tunic": "#B23A3A", "cloak": "#2F4A7A", "belt": "#8A5A32",
             "sandals": _SANDAL, "letters": "#F1E3C4", "bread": "#C98A4A", "basket": "#D8B26E"},
    "ananias": {"skin": "#E0AE8A", "hair": "#A8A8A0", "cap": "#7A5532", "tunic": "#6E8F4E", "shawl": "#D9A93A",
                "sandals": _SANDAL, "jug": "#C46A3E"},
    "barnabas": {"skin": "#B87C56", "hair": "#2A2420", "tunic": "#D9773A", "mantle": "#F1E3C4", "belt": "#3E6B4A",
                 "sandals": _SANDAL},
    "judas": {"skin": "#C8946C", "hair": "#5A3A26", "tunic": "#E2C89A", "cloth": "#4A78B0", "stripes": "#FFFFFF",
              "belt": "#8A6A4A", "apron": "#8A6A4A", "sandals": _SANDAL, "bread": "#C98A4A"},
    "priest": {"skin": "#D6A27A", "hair": "#ECEAE2", "tunic": "#F4F2EA", "overrobe": "#3D5FA0", "hem": "#E2B44A",
               "turban": "#F4F2EA", "sandals": _SANDAL},
    "tallguard": {"skin": "#C99268", "hair": "#2A2018", "tunic": "#7F93A8", "belt": "#B4502F", "cap": "#D9A93A",
                  "bags": "#8A6A4A", "sandals": _SANDAL, "lantern": "#C46A3E"},
    "shortguard": {"skin": "#C08A62", "hair": "#1E1814", "tunic": "#7F93A8", "belt": "#B4502F", "cap": "#7A5532",
                   "bags": "#8A6A4A", "sandals": _SANDAL},
    "peter": dict(_MI["PALETTE"]["peter"]),                              # noqa: F821
}
REGION_NAMES.update({                                                    # noqa: F821
    "tunic": ("长袍", "robe"), "cloak": ("披风", "travel cloak"), "belt": ("腰带", "belt / sash"),
    "shawl": ("披肩", "shawl"), "cap": ("帽子", "cap"), "mantle": ("外披", "mantle"), "letters": ("书信", "letters"),
    "bread": ("饼", "bread"), "basket": ("筐子和绳子", "basket and ropes"), "jug": ("水罐", "jug"),
    "lantern": ("灯笼", "lantern"), "overrobe": ("外袍", "over-robe"), "hem": ("金边", "gold hem"),
    "turban": ("头巾", "turban"), "cloth": ("头巾", "head cloth"), "stripes": ("条纹", "stripes"),
    "apron": ("围裙", "apron"), "bags": ("行李", "travel bags")})
REGION_NAMES["hair"] = ("头发和胡子", "hair and beard")                  # noqa: F821
# fixed-colour parts: UV1 points at a swatch in a corner of every decal of that character; UV0 anchored (detail lines)
_SW = {"sandals": (0.955, 0.925, 0.995, 0.995)}
SWATCHES = {"saul": dict(_SW), "ananias": dict(_SW), "barnabas": dict(_SW),
            "peter": dict(_MI["SWATCHES"]["peter"])}                     # noqa: F821
ANCHORS = {"saul": {"sandals": "saul.tunic"}, "ananias": {"sandals": "ananias.tunic"},
           "barnabas": {"sandals": "barnabas.tunic"}, "peter": dict(_MI["ANCHORS"]["peter"])}   # noqa: F821
# hidden props are not printed: they sample a printed region (CONTRACT §3; "set.<region>" = the set's drawings, read
# from assets/saul/model/set_id_2x.* + design.json; design.json set.propAnchors wins). The character fallbacks are the
# nearest printed colour while the set is not built yet.
PROP_ANCHORS = {
    "saul": {"letters": ["set.synagogue", "set.synagogueColumns", "set.columns", "barnabas.mantle"],
             "bread": ["set.breadBasket", "ananias.shawl"],
             "basket": ["set.breadBasket", "ananias.shawl"]},
    "ananias": {"jug": ["set.waterJar", "set.pots", "barnabas.tunic"]},
}
PART_ANCHORS = {ch: {(p, "skin"): f"{ch}.FACE" for p in ("handL", "handR", "legL", "legR", "kneeL", "kneeR",
                                                          "armL", "armR")} for ch in CHARS}

# ---------------------------------------------------------------------------------------------- bodies
# the Miracles friend body: one head size for all (one face layout), k = body length (skull top 0.354 k), bodyX = width
FRIEND = {
    "saul": dict(k=1.035, bodyX=0.96, belly=0.0, hair="short", robe=0.064),      # young, lean, 0.37
    "ananias": dict(k=0.890, bodyX=1.26, belly=1.0, hair="fringe", robe=0.030),  # small, round, old, 0.33 with the cap
    "barnabas": dict(k=1.086, bodyX=1.05, belly=0.0, hair="curly", robe=0.066),  # big, broad, 0.39
    "judas": dict(k=0.930, bodyX=1.04, belly=0.0, hair="short", robe=None),      # homely, 0.35 with the head cloth
    "priest": dict(k=0.950, bodyX=0.98, belly=0.0, hair="fringe", robe=0.030),   # old, 0.36 with the turban
    "tallguard": dict(k=1.055, bodyX=0.78, belly=0.0, hair="cap", robe=None),    # long and thin, 0.41 with the cap
    "shortguard": dict(k=0.837, bodyX=1.32, belly=1.0, hair="short", robe=None),  # short and round, 0.30 with the cap
}
for _f, _v in FRIEND.items():
    _k = _v["k"]
    _sp = scaled(KING, _k, _k, height=CONTRACT_HEIGHT[_f], **_FHEAD)   # noqa: F821
    _sp["chin"] = _sp["top"] - _FH; _sp["hw"] = 0.0219                  # noqa: F821
    _sp["shoulder"] = (_sp["shoulder"][0] * _v["bodyX"], _sp["shoulder"][1])
    _sp["hipX"] = _sp["hipX"] * min(1.25, _v["bodyX"])
    if _f in ("ananias", "shortguard"):
        _sp["handDims"] = {a: x * 1.08 for a, x in _sp["handDims"].items()}
    if _f == "barnabas":                              # big hands; arms a little shorter so the A-pose fits the slot
        _sp["handDims"] = {a: x * 1.14 for a, x in _sp["handDims"].items()}
        _sp["hand"] *= 1.04; _sp["upperArm"] *= 0.90; _sp["forearm"] *= 0.90
    if _f == "tallguard":                             # lanky: longer arms, long nose (mesh only)
        _sp["upperArm"] *= 1.06; _sp["forearm"] *= 1.06
        _sp["nose_long"] = 0.60; _sp["noseH"] *= 1.40; _sp["nose_w"] = 1.0
    if _f == "ananias":                               # a round button nose
        _sp["nose_w"] = 1.30; _sp["noseH"] *= 1.15
    SPEC[_f] = _sp                                                      # noqa: F821
EYE.update({c: (0.405, 0.320, 0.222) for c in MEN})                    # noqa: F821

# ---------------------------------------------------------------------------------------------- expressions (DESIGN §1)
EXPRESSIONS = {
    "saul": ["angry", "shout", "shock", "look_up", "blind", "pray", "see", "kind", "talk", "laugh", "chew", "whisper"],
    "ananias": ["gentle", "talk", "look_up", "fright", "gulp", "brave", "joy", "whisper"],
    "barnabas": ["happy", "talk", "laugh", "kind"],
    "judas": ["happy", "talk", "amazed", "laugh"],
    "priest": ["grave", "talk"],
    "tallguard": ["happy", "talk", "amazed", "shock", "puff", "sleepy", "asleep", "puzzled"],
    "shortguard": ["happy", "talk", "amazed", "shock", "puff", "sleepy", "asleep", "puzzled"],
    "peter": ["jolly", "talk", "shock", "laugh", "sad", "afraid"],
}
COPIED = {"peter": [("mi", ["jolly", "talk", "shock", "laugh"]), ("rs", ["sad"])]}
NEW_EXPRESSIONS = {ch: list(EXPRESSIONS[ch]) for ch in MEN}
NEW_EXPRESSIONS["peter"] = ["afraid"]
DEFAULT_EXPR = {"saul": "angry", "ananias": "gentle", "barnabas": "happy", "judas": "happy", "priest": "grave",
                "tallguard": "happy", "shortguard": "happy", "peter": "jolly"}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "saul": {"idle": "angry", "walk": "kind", "march": "angry", "angry_talk": "shout", "take_letters": "angry",
             "fall_down": "shock", "sit_look_up": "look_up", "get_up_blind": "blind", "walk_blind": "blind",
             "sit_pray": "pray", "see_again": "see", "kneel": "pray", "eat_bread": "chew", "preach": "talk",
             "talk": "talk", "basket_wait": "whisper", "basket_down": "whisper", "basket_out": "whisper",
             "tiptoe": "whisper", "hug": "laugh", "wave": "kind", "cheer": "laugh"},
    "ananias": {"idle": "gentle", "walk": "gentle", "talk": "talk", "kneel_pray": "gentle", "kneel_look_up": "look_up",
                "startle": "fright", "nervous": "gulp", "tiptoe": "gulp", "knock": "gulp", "hands_on": "brave",
                "pour": "joy", "listen": "joy", "cheer": "joy", "wave": "joy"},
    "barnabas": {"idle": "happy", "walk": "happy", "talk": "talk", "laugh": "laugh", "wave": "happy",
                 "arm_round": "kind"},
    "judas": {"idle": "happy", "listen": "happy", "laugh": "laugh", "wave": "happy", "offer_bread": "happy"},
    "priest": {"idle": "grave", "give_letters": "talk"},
    "tallguard": {"idle": "happy", "walk": "happy", "walk_puff": "puff", "puff": "puff", "shrug": "puzzled",
                  "duck": "shock", "amazed": "amazed", "lead_hand": "happy", "listen": "happy",
                  "scratch_head": "puzzled", "lantern_peer": "puzzled", "wave": "happy"},
    "shortguard": {"idle": "happy", "walk": "happy", "talk": "talk", "listen": "happy", "amazed": "amazed",
                   "walk_puff": "puff", "puff": "puff", "duck": "shock", "boast": "happy", "doze": "asleep",
                   "wave": "happy"},
    "peter": {"idle": "jolly", "peek_afraid": "afraid", "hug": "laugh", "wave": "jolly"},
}


def face_file(ch, ex):
    return os.path.join(FACES, f"{ch}_{ex}.png")


# ---------------------------------------------------------------------------------------------- face drawings
# The patched Miracles draw_faces (exec'd by ls_characters.py) looks up ls_face_params, LS_LOOK, LS_FACE_CHARS,
# ls_draw_exprs, ls_face_hook, ls_overview_cells and ls_face_base at call time: this pack rebinds them.
LS_LOOK = {
    "saul": dict(bcol=(40, 26, 18, 255), iris=(84, 56, 36), bw=0.076, nose=0.040, blush=0.31),
    "ananias": dict(bcol=(150, 148, 140, 255), iris=(96, 72, 48), bw=0.072, nose=0.046, blush=0.33),
    "barnabas": dict(bcol=(26, 20, 16, 255), iris=(70, 50, 34), bw=0.066, nose=0.044, blush=0.31),
    "judas": dict(bcol=(78, 54, 34, 255), iris=(92, 62, 40), bw=0.056, nose=0.040, blush=0.31),
    "priest": dict(bcol=(206, 204, 196, 255), iris=(88, 76, 60), bw=0.064, nose=0.042, blush=0.30),
    "tallguard": dict(bcol=(52, 38, 26, 255), iris=(92, 62, 40), bw=0.046, nose=0.046, blush=0.31),
    "shortguard": dict(bcol=(22, 16, 12, 255), iris=(80, 56, 38), bw=0.070, nose=0.044, blush=0.32),
}
LS_FACE_CHARS = ("saul", "ananias", "barnabas", "judas", "priest", "tallguard", "shortguard", "peter")


def sa_face_params(base):
    """This pack's drawings: Saul, Ananias, Barnabas, the priest (new), Judas and the guards (the friend group drawings
    + the guards' new ones), Peter `afraid`. All start from the Miracles friend base look (base("friend", <no ex>))."""
    def look(key):
        E, Bp, Bl, Br, M, o = base("friend", "_base")
        if key == "saul":            # thick dark brows carry the change of heart
            Bp.update(thick=1.45); o.update(bl=60, crow=0)
        elif key == "ananias":       # old, rosy cheeks, bushy grey brows
            Bp.update(thick=1.40, raise_=0.070); o.update(bl=175, crow=2)
        elif key == "barnabas":
            Bp.update(thick=1.20); o.update(bl=120, crow=2)
        elif key == "priest":        # old, calm, heavier lids; never sinister
            E.update(lid=0.18, tilt=0.0); Bp.update(thick=1.15, arch=0.20); o.update(bl=40, crow=2)
        elif key == "tallguard":
            Bp.update(thick=0.85); o.update(bl=70)
        elif key == "shortguard":
            Bp.update(thick=1.35); o.update(bl=130)
        return E, Bp, Bl, Br, M, o

    def group(key, ex, E, Bp, Bl, Br, M, o):
        """The friend group drawings (Miracles / The King Who Serves / He Is Risen! parameters) + the guards' new ones."""
        if ex == "happy":
            E.update(top=0.84); Bp.update(arch=0.40); M.update(kind="smile", wd=0.086)
        elif ex == "talk":
            M.update(kind="open", wd=0.076, jaw=0.08)
        elif ex == "amazed":
            E.update(top=1.32, bot=1.10, pupil=0.36, lid=0.06, tilt=0.0); Bp.update(raise_=0.120, arch=0.64)
            M.update(kind="o", wd=0.062, jaw=0.30); o.update(bl=max(o["bl"], 100), crow=0)
        elif ex == "laugh":
            E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.104, jaw=0.26)
            o.update(bl=max(o["bl"], 150), crow=2)
        elif ex == "shock":
            E.update(top=1.45, bot=1.25, pupil=0.28, lid=0.04, tilt=0.0)
            Bp.update(raise_=0.140, arch=0.74, outer=0.020); M.update(kind="wobbly", wd=0.090, jaw=0.30)
            o.update(crow=0, special=["sweat"])
        elif ex == "puff":           # red cheeks, mouth open panting, eyes squeezed
            E.update(mode="closed"); Bp.update(inner=0.050, raise_=0.085, arch=0.04, outer=-0.020)
            M.update(kind="shout", wd=0.094, jaw=0.42); o.update(bl=235, crow=0, crs=False, special=["sweat"])
        elif ex == "sleepy":         # eyes half closed, a smile
            E.update(top=0.30, bot=0.80, look=(0.0, -0.35), lid=0.30); Bp.update(raise_=0.052, arch=0.22)
            M.update(kind="smile", wd=0.074)
        elif ex == "asleep":         # eyes shut, mouth open
            E.update(mode="closed"); Bp.update(raise_=0.050, arch=0.16); M.update(kind="o", wd=0.056, jaw=0.24)
            o.update(crs=False)
        elif ex == "puzzled":        # one brow up, mouth to one side
            E.update(top=0.98, look=(-0.40, 0.35)); Bl = dict(inner=-0.030, raise_=0.050, arch=0.08)
            Br = dict(raise_=0.120, arch=0.62); M.update(kind="smirk", wd=0.072, side=-1.0); o.update(crow=0)
        return E, Bp, Bl, Br, M, o

    def fp(key, ex):
        if key == "peter":
            if ex != "afraid":
                return base(key, ex)
            E, Bp, Bl, Br, M, o = base("peter", "talk")     # eyes round, brows up, mouth small and wobbly
            E.update(top=1.30, bot=1.16, pupil=0.32, lid=0.05, tilt=0.0, look=(0.35, 0.0))
            Bp.update(inner=0.060, raise_=0.115, arch=0.22, outer=-0.010)
            M.update(kind="wobbly", wd=0.066, jaw=0.05); o.update(bl=60, crow=0, special=["sweat"])
            return E, Bp, Bl, Br, M, o
        if key not in MEN:
            return base(key, ex)
        E, Bp, Bl, Br, M, o = look(key)
        if key == "saul":
            if ex == "angry":        # brows down hard, mouth a tight line
                E.update(top=0.80, bot=0.86, tilt=0.0); Bp.update(inner=-0.058, raise_=0.040, arch=0.04, outer=0.012)
                M.update(kind="flat", wd=0.060); o.update(bl=40)
            elif ex == "shout":      # brows down, mouth open square ("March!")
                E.update(top=0.96, tilt=0.0); Bp.update(inner=-0.062, raise_=0.040, arch=0.04, outer=0.012)
                M.update(kind="shout", wd=0.092, jaw=0.46); o.update(bl=90)
            elif ex == "shock":
                E.update(top=1.45, bot=1.25, pupil=0.28, lid=0.04, tilt=0.0)
                Bp.update(raise_=0.140, arch=0.72, outer=0.020); M.update(kind="o", wd=0.060, jaw=0.32)
            elif ex == "look_up":    # eyes up, a small O, brows soft
                E.update(top=1.10, look=(0.0, 0.95), pupil=0.48); Bp.update(inner=0.020, raise_=0.095, arch=0.40)
                M.update(kind="o", wd=0.044, jaw=0.12); o.update(bl=70)
            elif ex == "blind":      # eyes gently closed, brows a little raised, a calm mouth
                E.update(mode="closed"); Bp.update(inner=0.020, raise_=0.086, arch=0.30)
                M.update(kind="soft", wd=0.060); o.update(crs=False, bl=50)
            elif ex == "pray":       # eyes closed, a small peaceful mouth
                E.update(mode="closed"); Bp.update(inner=0.012, raise_=0.066, arch=0.26)
                M.update(kind="small", wd=0.052); o.update(crs=False, bl=70)
            elif ex == "see":        # eyes wide open and shining, a big open smile
                E.update(top=1.30, bot=1.10, pupil=0.42, lid=0.06, wet=True); Bp.update(raise_=0.120, arch=0.60)
                M.update(kind="grin", wd=0.104, jaw=0.22); o.update(bl=120, crow=1)
            elif ex == "kind":       # default from S08: brows relaxed and lifted, a warm closed smile
                E.update(top=0.80, bot=0.80, look=(0.05, -0.08)); Bp.update(inner=0.020, raise_=0.074, arch=0.34)
                M.update(kind="soft", wd=0.076); o.update(crow=2, bl=90)
            elif ex == "talk":
                Bp.update(raise_=0.068, arch=0.34); M.update(kind="open", wd=0.074, jaw=0.08)
            elif ex == "laugh":
                E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.104, jaw=0.26)
                o.update(bl=140, crow=2)
            elif ex == "chew":       # cheeks round, eyes smiling
                E.update(mode="happy"); Bp.update(raise_=0.074, arch=0.46); M.update(kind="small", wd=0.060)
                o.update(bl=200, crow=2)
            elif ex == "whisper":    # lips rounded, eyes sparkling
                E.update(top=1.04, pupil=0.46, wet=True, look=(0.30, 0.10)); Bp.update(raise_=0.082, arch=0.46)
                M.update(kind="o", wd=0.040, jaw=0.05); o.update(bl=80)
            return E, Bp, Bl, Br, M, o
        if key == "ananias":
            if ex == "gentle":
                E.update(top=0.78, bot=0.80, look=(0.0, -0.05)); Bp.update(inner=0.020, arch=0.30)
                M.update(kind="soft", wd=0.072)
            elif ex == "talk":
                M.update(kind="open", wd=0.072, jaw=0.08)
            elif ex == "look_up":    # rapt, in the light
                E.update(top=1.12, look=(0.0, 0.95), pupil=0.48, wet=True); Bp.update(inner=0.020, raise_=0.095, arch=0.42)
                M.update(kind="o", wd=0.046, jaw=0.14)
            elif ex == "fright":     # eyes huge, mouth a wobbly zigzag, brows right up ("THAT Saul?!")
                E.update(top=1.50, bot=1.30, pupil=0.26, lid=0.04, tilt=0.0)
                Bp.update(raise_=0.150, arch=0.76, outer=0.030); M.update(kind="wobbly", wd=0.086, jaw=0.32)
                o.update(special=["sweat"], crow=0)
            elif ex == "gulp":       # eyes squeezed, cheeks puffed
                E.update(mode="closed"); Bp.update(inner=0.060, raise_=0.090, arch=0.04, outer=-0.030)
                M.update(kind="small", wd=0.046); o.update(bl=235, crs=False)
            elif ex == "brave":      # chin up, a small determined smile
                E.update(top=0.92, look=(0.0, 0.25), tilt=0.0); Bp.update(inner=-0.016, raise_=0.064, arch=0.20)
                M.update(kind="smile", wd=0.062)
            elif ex == "joy":
                E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.100, jaw=0.20)
            elif ex == "whisper":
                E.update(top=1.04, pupil=0.46, look=(0.30, 0.10)); Bp.update(raise_=0.082, arch=0.44)
                M.update(kind="o", wd=0.040, jaw=0.05)
            return E, Bp, Bl, Br, M, o
        if key == "barnabas":
            if ex == "happy":        # a wide smile (default)
                E.update(top=0.82, bot=0.78); M.update(kind="grin", wd=0.100, jaw=0.10); o.update(bl=140)
            elif ex == "talk":
                Bp.update(raise_=0.070, arch=0.40); M.update(kind="open", wd=0.082, jaw=0.10)
            elif ex == "laugh":
                E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.110, jaw=0.28)
                o.update(bl=160, crow=3)
            elif ex == "kind":
                E.update(top=0.76, bot=0.80, look=(0.05, -0.10)); Bp.update(inner=0.020, raise_=0.068, arch=0.30)
                M.update(kind="soft", wd=0.078); o.update(bl=110)
            return E, Bp, Bl, Br, M, o
        if key == "priest":
            if ex == "grave":        # eyes calm, mouth straight (not a villain)
                E.update(top=0.82, bot=0.86); Bp.update(raise_=0.052, arch=0.16)
                M.update(kind="flat", wd=0.062)
            elif ex == "talk":
                E.update(top=0.86); Bp.update(raise_=0.056, arch=0.18); M.update(kind="open", wd=0.066, jaw=0.07)
            return E, Bp, Bl, Br, M, o
        return group(key, ex, E, Bp, Bl, Br, M, o)      # judas, tallguard, shortguard
    return fp


ls_face_params = sa_face_params


def ls_draw_exprs(ch):
    return NEW_EXPRESSIONS.get(ch, [])


def ls_face_base(ch):
    return PALETTE[ch].get("skin")


def ls_overview_cells():
    return [(ch, ex) for ch in CHARS + EXTRAS for ex in EXPRESSIONS[ch]]


def ls_face_hook(ch, ex, img, T):
    return False


def draw_faces():
    """Copy Peter's existing decals (Miracles, He Is Risen!), then draw the new ones (patched Miracles drawing code)."""
    copied = []
    for ch, srcs in COPIED.items():
        for src_pack, exprs in srcs:
            src_dir = MI_FACES if src_pack == "mi" else RS_FACES             # noqa: F821
            for ex in exprs:
                shutil.copy(os.path.join(src_dir, f"{ch}_{ex}.png"), face_file(ch, ex)); copied.append(f"{ch}_{ex}")
    made = _mi_draw_faces()                                                  # noqa: F821
    print("faces copied:", len(copied), "| drawn:", len(made))
    _overview()                                                              # noqa: F821
    return made


FIT_VIEWS = (("basket_wait", "basket at the window (basket_wait height), front; stand-in wall face + window"),
             ("basket_wait_side", "basket at the window, from the right (S11 camera side)"),
             ("basket_down", "basket lowered to the ground: ropes stretched to ropeTop, front"),
             ("basket_down_side", "basket lowered, from the right"),
             ("saul_letters", "Saul: letters shown in the right hand"), ("saul_bread", "Saul: bread shown"),
             ("ananias_jug", "Ananias: jug shown in the right hand"),
             ("tallguard_lantern", "tall guard: lantern shown"), ("judas_bread", "Judas: bread shown"),
             ("guards_pair", "the guards side by side (0.41 / 0.30)"),
             ("saul_seated", "Saul seated on the ground (test pose): lowest point"),
             ("pair_hug", "Saul / Peter at 0.10 (rest poses facing each other)"))


if not IN_BLENDER:                                                           # noqa: F821
    if __name__ == "__main__":
        mode = sys.argv[1] if len(sys.argv) > 1 else "faces"

        def blender_bin():
            return os.environ.get("BLENDER") or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"

        def run_all():
            import subprocess
            draw_faces()
            subprocess.run([blender_bin(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", SA_FILE,
                            "--", "build"], check=True, stdout=subprocess.DEVNULL)
            proof()                                                          # noqa: F821
            for m in ("preview", "uvcheck", "posetest", "verify"):
                subprocess.run([blender_bin(), "-b", "--factory-startup", "--python-exit-code", "1", "--python", SA_FILE,
                                "--", m], check=True, stdout=subprocess.DEVNULL)
            compose()                                                        # noqa: F821
            v = json.load(open(os.path.join(WORK, "verify.json")))
            for ch, i in v.items():
                print(ch, "bonesMatch", i["bonesMatch"], "parentsOK", i.get("parentsOK"), "actions", i["actions"],
                      "tris", i["tris"], "budget", i["budget"], "uvOrderOK", i.get("uvOrderOK"),
                      "maxInf", i.get("maxInfluences"), "height", i["heightTop"], "err%", i["heightErrPct"],
                      "minY", i["minY"], *(("ropes", i["ropes"]) if "ropes" in i else ()))
        {"faces": draw_faces, "compose": compose, "proof": proof, "all": run_all}[mode]()   # noqa: F821
    raise SystemExit(0)

# =============================================================================================== Blender part
ONLY = [c for c in os.environ.get("SA_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()                       # noqa: F821
SET_PROP_ANCHORS = set_prop_anchors()                                       # noqa: F821
REGIONS_KEY = "sa_regions"


def is_hidden_prop(o):
    """Kit rule (PROPS[ch][part] is False) + Saul's ropes, which show and hide with the basket."""
    ch, _, part = o.name.partition("_")
    if ch == "saul" and part == "ropes":
        return True
    return PROPS.get(ch, {}).get(part) is False


# =============================================================================================== costume helpers
def _drop(C, *names):
    C.parts = [p for p in C.parts if p["name"] not in names]


def _friend(C, belt=True):
    """The Miracles friend body, unchanged; then: the hanging belt end has no bone of its own in this pack (belt1 ->
    hips, mesh dropped; as The King Who Serves), the curly hair's red head band is not part of any costume here."""
    _MI["build_friend"](C)                                                  # noqa: F821
    _rename_bone(C, "belt1", "hips")                                        # noqa: F821
    _drop(C, "beltEnd")
    if not belt:
        _drop(C, "beltA")
    if "band1" in C.B:
        _rename_bone(C, "band1", "head")                                    # noqa: F821
        _drop(C, "band")


def _long_robe(C, hem_k):
    """Rebuild the friend robe with a lower hem (hem_k * k): the friend's own rows, sleeves and fold numbers (as
    build_friend calls build_robe), only the cut moves down. The friend's knee tubes stay inside."""
    ch = C.ch; fs = FRIEND[ch]; bx = fs["bodyX"]
    s = C.s; S = C.S; k = s["k"]; wy = s["waistY"]; chestY = s["chestY"]
    _drop(C, "tunic")
    RT = cut_rows(scale_rows(KING_ROBE, k, k * bx), hem_k * k)              # noqa: F821
    if fs["belly"]:
        yb = wy - 0.016 * S
        RT = [(y, hw * (1 + 0.04 * math.exp(-((y - chestY) / 0.025) ** 2)) + 0.0060 * S * math.exp(-((y - yb) / 0.034) ** 2),
               zf + 0.0200 * S * math.exp(-((y - yb) / 0.040) ** 2),
               zb - 0.0030 * S * math.exp(-((y - yb) / 0.034) ** 2)) for y, hw, zf, zb in RT]
    sleeve_t = [(0.004, 0.0126 * min(1.15, bx)), (0.014, 0.0124 * min(1.15, bx)), (0.026, 0.0120 * min(1.15, bx)),
                (0.036, 0.0118 * min(1.15, bx))]
    build_robe(C, RT, sleeve_t, None, nf=10, fold_amp=0.0012, sleeve_fold=0.0005, reg="tunic", name="tunic", N=30,
               step=0.0072)                                                 # noqa: F821
    C.tunic_rows = C.robe_rows


def _drape(C, name, reg, a_cols, y_bot, y_top, off, wfn, NV=6, solid=0.0011, plumb_y=None, regfn=None):
    """A cloth panel draped on the robe (kit mantle_point: pushed out of the sleeves, hanging plumb below plumb_y):
    columns at angles a_cols (0 = front, + toward +X = the character's left), rows from y_bot(a) up to y_top(a)."""
    S = C.S; cg = Cage(); grid = []                                         # noqa: F821
    for a in a_cols:
        col = []
        for j in range(NV + 1):
            v = j / NV
            y = lerp(y_bot(a), y_top(a), v)                                 # noqa: F821
            col.append(cg.add(mantle_point(C, (a / (2 * math.pi)) % 1.0, y, off(a, v), plumb_y=plumb_y), wfn))  # noqa: F821
        grid.append(col)
    for i in range(len(a_cols) - 1):
        for j in range(NV):
            cg.face((grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]), regfn(i, j) if regfn else reg, 0)
    C.add(name, cg, subdiv=0, solidify=solid * S)
    return grid


def _cloth_weights(C, top_bones, bone, skirt=0.0):
    """Top on the torso bones, lower back on the cloth bone, below the hips partly on the legs (skirt weights)."""
    S = C.S; s = C.s; chestY, hipY = s["chestY"], s["hipY"]
    wtop = C.w(top_bones)
    wcl = C.w([bone], blend=0.012 * S) if bone else None
    wsk = skirt_weights(C) if skirt else None                               # noqa: F821

    def wfn(p):
        w = wtop(p)
        if wcl:
            t = smoothstep(chestY + 0.004 * S, chestY - 0.024 * S, p.y) * smoothstep(-0.2, -0.6, math.cos(math.atan2(p.x, p.z)))  # noqa: F821
            if t > 0:
                w = mixw((w, 1 - t), (wcl(p), t))                           # noqa: F821
        if wsk and p.y < hipY:
            u = skirt * smoothstep(hipY, hipY - 0.05 * S, p.y)              # noqa: F821
            w = mixw((w, 1 - u), (wsk(p), u))                               # noqa: F821
        return w
    return wfn


def _wide_belt(C, reg, half, pouch=False):
    """A wide band at the waist (>= 6 mm on the print), kit waist_band; Saul's has a small pouch on the right hip."""
    s = C.s; S = C.S; bw = s["waistY"] - 0.012 * S
    waist_band(C, "belt", reg, bw - half * S, bw + half * S, 0.0012 * S, bulge=0.0010 * S)   # noqa: F821
    if pouch:
        hw, zf, zb = table(C.robe_rows, bw)                                 # noqa: F821
        top = shell_point(C.robe_rows, bw - half * S, -1.15, 0.0030 * S)    # noqa: F821 (the right hip: -X)
        wp = C.w(["hips"])
        cg = Cage()                                                         # noqa: F821
        blob(cg, top + V(-0.0015 * S, -0.0075 * S, 0.0010 * S), 0.0060 * S, 0.0070 * S, 0.0042 * S, wp, reg, 0, NU=8, NV=5)  # noqa: F821
        C.add("pouch", cg, subdiv=0, piece_as="belt")


def _cap_lathe(C, name, reg, base_y, prof, N=18, tilt=0.0, ex=0.0030, ef=0.0026, eb=0.0034, subdiv=1, regfix=None):
    """Head gear (kit head_lathe; prof dy in design units at S = 1). subdiv=0 (the extras, 18k budget): the profile is
    doubled by linear interpolation and N raised by a third instead."""
    cg = Cage(); wfn = C.w(["head"]); S = C.S                               # noqa: F821
    if not subdiv:
        dense = [prof[0]]
        for a, b in zip(prof, prof[1:]):
            if b[1] > 0:
                dense.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
            dense.append(b)
        prof = dense; N = int(N * 4 / 3) // 2 * 2
    n0 = len(cg.f)
    head_lathe(C, base_y, [(dy * S, k) for dy, k in prof], N, wfn, reg, 0, cg, extra_x=ex * S, extra_f=ef * S,
               extra_b=eb * S, tilt=tilt)                                   # noqa: F821
    if regfix:
        for i in range(n0, len(cg.f)):
            cg.reg[i] = regfix(i - n0, N)
    C.add(name, cg, subdiv=subdiv)


def _hide_hair_under(C, y):
    """Drop the hair faces that a cap / cloth / turban covers completely (budget; never seen)."""
    for p in C.parts:
        if p["name"] == "hair":
            drop_faces(p["cage"], lambda c: c.y > y)                        # noqa: F821


def _bags(C):
    """Saul's travel bags on a guard's back: a big sack and a small one at the hip (fixed paint)."""
    s = C.s; S = C.S; rr = C.robe_rows
    cg = Cage(); wc = C.w(["chest", "spine"]); wh = C.w(["hips"])           # noqa: F821
    c1 = shell_point(rr, s["chestY"] - 0.010 * S, math.pi + 0.15, 0.0100 * S)   # noqa: F821
    blob(cg, c1, 0.0180 * S, 0.0200 * S, 0.0110 * S, wc, "bags", 0, NU=10, NV=6)   # noqa: F821
    c2 = shell_point(rr, s["hipY"] + 0.004 * S, math.pi - 0.9, 0.0080 * S)      # noqa: F821
    blob(cg, c2, 0.0110 * S, 0.0130 * S, 0.0080 * S, wh, "bags", 0, NU=8, NV=5)    # noqa: F821
    C.add("bags", cg, subdiv=0)


# =============================================================================================== props
def _hand_frame(C, side="R"):
    A = C.arm[side]; gp = grip_point(C, side)                               # noqa: F821
    ax = A["dh"].copy(); up = A["Np"].copy()
    across = V(0, 0, 1).cross(ax).normalized()                              # noqa: F821
    return A, gp, ax, up, across


def add_letters(C):
    """A rolled scroll tied with a cord, 0.06 long, across the right fist (hidden)."""
    S = C.S; A, gp, ax, up, across = _hand_frame(C)
    C.B["letters"] = (gp.copy(), gp + ax * 0.012 * S, "handR")
    cg = Cage(); c = gp + up * 0.0020 * S                                   # noqa: F821
    L_ = 0.060; n = 7
    path = [c + across * (L_ * (i / (n - 1) - 0.5)) for i in range(n)]
    rad = [0.0072, 0.0068, 0.0064, 0.0064, 0.0064, 0.0068, 0.0072]
    tube(cg, path, rad, 10, None, "letters", 0, ref=ax)                     # noqa: F821
    ring = [c + across * 0.004 + (ax * math.cos(2 * math.pi * j / 10) + up * math.sin(2 * math.pi * j / 10)) * 0.0070
            for j in range(11)]
    tube(cg, ring, [0.0011] * len(ring), 5, None, "letters", 0, ref=across, cap0=False, cap1=False)   # noqa: F821
    C.add("letters", cg, subdiv=0, rigid="letters")


def add_bread(C, owner):
    """A round flat loaf, 0.05 across, lying on the right palm (hidden)."""
    S = C.S; A, gp, ax, up, across = _hand_frame(C)
    C.B["bread"] = (gp.copy(), gp + ax * 0.012 * S, "handR")
    cg = Cage()                                                             # noqa: F821
    zax = ax.cross(up).normalized()
    M = Matrix((ax, up, zax)).transposed()                                  # noqa: F821
    c = gp + up * 0.0080 + ax * 0.004
    blob(cg, c, 0.0250, 0.0085, 0.0250, None, "bread", 0, NU=14, NV=6, ax=M)   # noqa: F821
    C.add("bread", cg, subdiv=0, rigid="bread")


def add_jug(C):
    """Ananias's terracotta water jug with one handle, 0.06 high, hanging from the right hand by its handle (hidden)."""
    S = C.S; gp = grip_point(C, "R")                                        # noqa: F821
    C.B["jug"] = (gp.copy(), gp + V(0, -0.030, 0), "handR")                 # noqa: F821
    cg = Cage()                                                             # noqa: F821
    jc = gp + V(0, -0.064, 0.0)                                             # noqa: F821
    prof = [(0.0, 0.0100), (0.005, 0.0150), (0.018, 0.0180), (0.032, 0.0150), (0.044, 0.0090), (0.052, 0.0075),
            (0.059, 0.0092), (0.0560, 0.0072)]
    _clay_lathe(cg, jc, prof, 12, "jug")                                    # noqa: F821
    hp = [jc + V(0, 0.050, -0.0085), gp + V(0, 0.000, -0.0025), jc + V(0, 0.030, -0.0190)]   # noqa: F821
    hp = [cr_open(hp, t / 6) for t in range(7)]                             # noqa: F821
    tube(cg, hp, [(0.0020, 0.0015)] * len(hp), 6, None, "jug", 0, ref=V(1, 0, 0))   # noqa: F821
    C.add("jug", cg, subdiv=0, rigid="jug")


def add_lantern(C):
    """The tall guard's small clay lantern on a cord, hanging below the right fist (hidden)."""
    S = C.S; gp = grip_point(C, "R")                                        # noqa: F821
    C.B["lantern"] = (gp.copy(), gp + V(0, -0.025, 0), "handR")             # noqa: F821
    cg = Cage()                                                             # noqa: F821
    lc = gp + V(0, -0.058, 0.0)                                             # noqa: F821
    prof = [(0.0, 0.0060), (0.004, 0.0120), (0.014, 0.0140), (0.024, 0.0125), (0.030, 0.0080), (0.034, 0.0050),
            (0.036, 0.0030)]
    rings = lathe_y(cg, lc, prof, 12, None, "lantern", 0)                   # noqa: F821
    pth = [lc + V(0.0030, 0.036, 0.0), gp + V(0.0006, -0.004, 0.0), lc + V(-0.0030, 0.036, 0.0)]   # noqa: F821
    pth = [cr_open(pth, t / 6) for t in range(7)]                           # noqa: F821
    tube(cg, pth, [(0.0010, 0.0010)] * len(pth), 5, None, "lantern", 0, ref=V(0, 0, 1))   # noqa: F821
    C.add("lantern", cg, subdiv=0, rigid="lantern")


def add_basket_rig(C):
    """CONTRACT §3: bone `basket` (hips; mesh saul_basket, a round woven basket 0.10 across, 0.08 high; Saul crouches
    inside with the basket floor BASKET_DROP below the hips head), bone `ropeTop` (root, fixed at ROPE_TOP) and two ropes
    from the rim to the window (saul_ropes: rigid on `basket` while building; skinned to basket + ropeTop after the
    build, `_skin_ropes`)."""
    s = C.s; hipY = s["hipY"]
    y0 = hipY - BASKET_DROP; R = BASKET_D / 2
    c0 = V(0, y0, 0)                                                        # noqa: F821
    C.B["basket"] = (c0.copy(), c0 + V(0, BASKET_H, 0), "hips")             # noqa: F821
    top = V(*ROPE_TOP)                                                      # noqa: F821
    C.B["ropeTop"] = (top.copy(), top + V(0, 0.020, 0), "root")             # noqa: F821
    cg = Cage(); N = 24                                                     # noqa: F821
    # outer wall with woven ridges, a rolled rim, the inner wall and the floor
    prof = [(0.000, R * 0.80)]
    for i in range(9):
        t = i / 8; y = 0.006 + t * (BASKET_H - 0.010)
        prof.append((y, R * (0.90 + 0.10 * math.sin(min(1.0, t * 1.6) * math.pi / 2)) + (0.0008 if i % 2 else -0.0004)))
    outer = lathe_y(cg, c0, prof, N, None, "basket", 0, top_pole=False, bot_pole=False)   # noqa: F821
    cg.fan(list(reversed(outer[0])), c0.copy(), None, "basket", 0)       # flat bottom at the basket floor
    rim = [cg.ring([c0 + V(math.sin(2 * math.pi * j / N) * (R + dr), BASKET_H + dy, math.cos(2 * math.pi * j / N) * (R + dr))
                    for j in range(N)], None) for dr, dy in ((0.0030, -0.003), (0.0034, 0.0005), (0.0, 0.0030),
                                                             (-0.0034, 0.0005), (-0.0030, -0.003))]   # noqa: F821
    cg.bridge(outer[-1], rim[0], "basket", 0)
    for a, b in zip(rim, rim[1:]):
        cg.bridge(a, b, "basket", 0)
    inner = [cg.ring([c0 + V(math.sin(2 * math.pi * j / N) * r, y, math.cos(2 * math.pi * j / N) * r) for j in range(N)], None)
             for y, r in ((BASKET_H - 0.003, R - 0.0030), (0.010, R * 0.80 - 0.0020))]   # noqa: F821
    cg.bridge(rim[-1], inner[0], "basket", 0)
    cg.bridge(inner[0], inner[1], "basket", 0)
    cg.fan(inner[1], c0 + V(0, 0.010, 0), None, "basket", 0)                # noqa: F821
    C.add("basket", cg, subdiv=0, rigid="basket")
    # two ropes: from the rim on the wall side (toward -X) up to the window; rings kept horizontal so the rope stays round
    # when the clip lowers the basket (linear skinning of a translation keeps the ring offsets)
    cg = Cage(); C.rope_t = []                                              # noqa: F821
    NS, NR, r = 10, 6, 0.0018
    for sz in (1, -1):
        a = math.radians(-90 + sz * 42)
        p0 = c0 + V(math.sin(a) * (R + 0.0010), BASKET_H + 0.001, math.cos(a) * (R + 0.0010))   # noqa: F821
        p1 = top + V(0.003, -0.002, sz * 0.007)                             # noqa: F821
        rings = []
        for i in range(NS + 1):
            t = i / NS; p = p0.lerp(p1, t)
            rings.append(cg.ring([p + V(math.cos(2 * math.pi * j / NR) * r, 0, math.sin(2 * math.pi * j / NR) * r)
                                  for j in range(NR)], None))               # noqa: F821
            C.rope_t += [t] * NR
        for a_, b_ in zip(rings, rings[1:]):
            cg.bridge(a_, b_, "basket", 0)
        for rr_, pp, tt in ((rings[0], p0, 0.0), (rings[-1], p1, 1.0)):
            cg.fan(rr_, pp, None, "basket", 0); C.rope_t.append(tt)
    C.add("ropes", cg, subdiv=0, rigid="basket")


def _skin_ropes(rig):
    """saul_ropes: from a rigid child of bone `basket` to a skinned mesh (basket at the rim ends, ropeTop at the window
    ends, linear in between) parented to the rig object (the glTF exporter skins only object-parented meshes; the GLB
    node is moved back under the `basket` joint by `_ropes_under_basket`)."""
    o = bpy.data.objects.get("saul_ropes")                                  # noqa: F821
    C = _ROPE_CTX.get("saul")
    if not o or C is None:
        return
    mw = o.matrix_world.copy()
    o.parent_type = 'OBJECT'; o.parent_bone = ""
    o.matrix_parent_inverse = Matrix.Identity(4)                            # noqa: F821
    bpy.context.view_layer.update()                                         # noqa: F821
    o.matrix_world = mw
    ga = o.vertex_groups.new(name="basket"); gt = o.vertex_groups.new(name="ropeTop")
    assert len(o.data.vertices) == len(C.rope_t), (len(o.data.vertices), len(C.rope_t))
    for v, t in zip(o.data.vertices, C.rope_t):
        if t < 1.0:
            ga.add([v.index], 1.0 - t, 'REPLACE')
        if t > 0.0:
            gt.add([v.index], t, 'REPLACE')
    m = o.modifiers.new("Armature", 'ARMATURE'); m.object = rig
    bpy.context.view_layer.update()                                         # noqa: F821


def _ropes_under_basket(path):
    """Move the skinned node saul_ropes under the `basket` joint node in the GLB (glTF: a skinned mesh node's own
    transform is ignored, so the picture does not change), so StoryDirector's prop `saul/basket` (every renderer under
    the bone `basket`) shows and hides the ropes with the basket."""
    d = open(path, "rb").read()
    n0 = struct.unpack("<I", d[12:16])[0]
    j = json.loads(d[20:20 + n0])
    rest = d[20 + n0:]
    names = {nd.get("name"): i for i, nd in enumerate(j["nodes"])}
    ri, bi = names.get("saul_ropes"), names.get("basket")
    if ri is None or bi is None:
        return False
    for nd in j["nodes"]:
        if "children" in nd and ri in nd["children"]:
            nd["children"].remove(ri)
            if not nd["children"]:
                del nd["children"]
    for sc_ in j.get("scenes", []):
        if ri in sc_.get("nodes", []):
            sc_["nodes"].remove(ri)
    j["nodes"][bi].setdefault("children", []).append(ri)
    js = json.dumps(j, separators=(",", ":")).encode()
    js += b" " * ((4 - len(js) % 4) % 4)
    out = struct.pack("<III", 0x46546C67, 2, 12 + 8 + len(js) + len(rest)) + struct.pack("<I", len(js)) + b"JSON" + js + rest
    open(path, "wb").write(out)
    return True


# =============================================================================================== the men
def build_saul(C):
    """Young man of about thirty: short dark hair, short neat beard, deep-red robe to the shins, wide brown leather belt
    with a pouch on the right hip, dark-blue travel cloak over both shoulders and down the back (cloak1)."""
    _friend(C, belt=False)
    s = C.s; S = C.S; k = s["k"]
    nb, wy, chestY, hipY = s["neckBase"], s["waistY"], s["chestY"], s["hipY"]
    _extra_beard(C, "neat")                                                 # noqa: F821
    L = C.L; H = C.H
    moustache(C, "moustache", L["mouth"] + 0.092 * H, 0.52 * s["hw"], 0.03 * H, 0.0, 0.0014 * S, reg="hair", off=0.0014)  # noqa: F821
    C.parts[-1]["piece_as"] = "beard"
    _long_robe(C, FRIEND["saul"]["robe"])
    _wide_belt(C, "belt", 0.0150, pouch=True)
    # travel cloak: round the back over both shoulders, front edges at the chest, the back down to the calves
    p_top = shell_point(C.robe_rows, nb - 0.008 * S, math.pi, 0.004 * S)    # noqa: F821
    p_bot = shell_point(C.robe_rows, hipY - 0.010 * S, math.pi, 0.008 * S)  # noqa: F821
    C.B["cloak1"] = (p_top, p_bot, "chest")
    wfn = _cloth_weights(C, ["chest", "shoulderL", "shoulderR", "spine"], "cloak1", skirt=0.25)
    cols = [0.66 + (2 * math.pi - 1.32) * i / 17 for i in range(18)]
    calf = 0.080 * k

    def ybot(a):
        f = smoothstep(0.30, -0.80, math.cos(a))                            # noqa: F821
        return lerp(chestY - 0.010 * S, calf, f ** 0.8)                      # noqa: F821

    def ytop(a):
        return nb - 0.0015 * S

    def off(a, v):
        return (0.0034 + 0.0020 * (1 - v)) * S
    _drape(C, "cloak", "cloak", cols, ybot, ytop, off, wfn, NV=10, solid=0.0011, plumb_y=hipY)
    add_letters(C); add_bread(C, "saul"); add_basket_rig(C)
    _ROPE_CTX["saul"] = C


_ROPE_CTX = {}


def build_ananias(C):
    """Small, round older man: bald with a grey fringe and round beard (friend `fringe`), a small brown round cap, a
    moss-green robe to the ankles, a mustard shawl over both shoulders; no belt (the shawl covers the waist)."""
    _friend(C, belt=False)
    s = C.s; S = C.S; L = C.L; H = C.H
    nb, wy, chestY = s["neckBase"], s["waistY"], s["chestY"]
    _cap_lathe(C, "cap", "cap", L["eye"] + 0.40 * H,
               [(-0.0035, 1.04), (0.0, 1.07), (0.0060, 1.02), (0.0120, 0.86), (0.0165, 0.60), (0.0190, 0.30), (0.0198, 0.0)],
               N=18, tilt=math.radians(12), ex=0.0022, ef=0.0018, eb=0.0024)
    _long_robe(C, FRIEND["ananias"]["robe"])
    wfn = _cloth_weights(C, ["chest", "shoulderL", "shoulderR", "spine"], None)
    cols = [0.26 + (2 * math.pi - 0.52) * i / 19 for i in range(20)]

    def ybot(a):
        f = smoothstep(0.30, -0.80, math.cos(a))                            # noqa: F821
        return lerp(wy - 0.022 * S, chestY - 0.034 * S, f)                  # noqa: F821

    def off(a, v):
        return (0.0030 + 0.0016 * (1 - v)) * S
    _drape(C, "shawl", "shawl", cols, ybot, lambda a: nb - 0.0015 * S, off, wfn, NV=7, solid=0.0011)
    add_jug(C)


def build_barnabas(C):
    """Big, broad, warm: black curly hair, full black beard, terracotta robe to the shins, a wide dark-green sash, a cream
    mantle over the left shoulder, round the back to the right hip (mantle1)."""
    _friend(C, belt=False)
    s = C.s; S = C.S; k = s["k"]
    nb, wy, chestY, hipY, shY = s["neckBase"], s["waistY"], s["chestY"], s["hipY"], s["shoulder"][1]
    _extra_beard(C, "short")                                                # noqa: F821
    _long_robe(C, FRIEND["barnabas"]["robe"])
    _wide_belt(C, "belt", 0.0140)
    p_top = shell_point(C.robe_rows, nb - 0.010 * S, 2.6, 0.004 * S)        # noqa: F821
    p_bot = shell_point(C.robe_rows, hipY - 0.020 * S, 3.4, 0.006 * S)      # noqa: F821
    C.B["mantle1"] = (p_top, p_bot, "chest")
    wfn = _cloth_weights(C, ["chest", "shoulderL", "spine"], "mantle1", skirt=0.35)
    cols = [0.30 + (4.05 - 0.30) * i / 19 for i in range(20)]

    def ybot(a):
        return lerp(hipY - 0.012 * S, 0.135 * k, smoothstep(1.4, 3.0, a))    # noqa: F821

    def ytop(a):
        return lerp(nb - 0.0015 * S, wy - 0.004 * S, smoothstep(3.25, 4.05, a))   # noqa: F821

    def off(a, v):
        return (0.0036 + 0.0018 * (1 - v)) * S
    _drape(C, "mantle", "mantle", cols, ybot, ytop, off, wfn, NV=9, solid=0.0011, plumb_y=hipY)


def build_judas(C):
    """Homely householder: short brown beard, striped blue-and-white head cloth, sand tunic, brown apron-sash."""
    _friend(C)
    s = C.s; S = C.S; L = C.L; H = C.H; k = s["k"]; wy, hipY = s["waistY"], s["hipY"]
    _extra_beard(C, "short")                                                # noqa: F821
    _cap_lathe(C, "headcloth", "cloth", L["brow"] + 0.16 * H,
               [(-0.0070, 1.10), (-0.0010, 1.15), (0.0080, 1.12), (0.0170, 1.00), (0.0240, 0.78), (0.0290, 0.48),
                (0.0310, 0.20), (0.0314, 0.0)], N=24, tilt=math.radians(-8), ex=0.0032, ef=0.0020, eb=0.0050,
               regfix=lambda i, N: "stripes" if ((i % N) // 2) % 2 else "cloth", subdiv=0)
    _hide_hair_under(C, L["brow"] + 0.16 * H + 0.008 * S)
    hemT = 0.100 * k
    wfn = skirt_weights(C)                                                  # noqa: F821
    cols = [-0.95 + 1.90 * i / 7 for i in range(8)]
    _drape(C, "apron", "apron", cols, lambda a: hemT + 0.014 * S, lambda a: wy - 0.004 * S,
           lambda a, v: (0.0034 + 0.0012 * (1 - v)) * S, wfn, NV=5, solid=0.0010)
    add_bread(C, "judas")


def build_priest(C):
    """Old, calm, grave: long white beard, white cloth turban, white robe to the ankles, blue over-robe (open at the
    front) with a gold hem band. No breastplate."""
    _friend(C, belt=False)
    s = C.s; S = C.S; L = C.L; H = C.H; k = s["k"]; nb = s["neckBase"]
    _drop(C, "beard", "moustache")                                          # the fringe's round beard -> a long one
    top = [(0.00, L["mouth"] - 0.085 * H), (0.035, L["mouth"] - 0.07 * H), (0.07, L["mouth"] + 0.0 * H),
           (0.10, L["nose"] - 0.06 * H), (0.15, L["nose"] - 0.01 * H), (0.20, L["eye"] - 0.16 * H), (0.245, L["eye"] - 0.04 * H)]
    bot = [(0.00, L["chin"] - 0.62 * H), (0.06, L["chin"] - 0.58 * H), (0.12, L["chin"] - 0.42 * H),
           (0.17, L["chin"] - 0.10 * H), (0.21, L["mouth"] - 0.04 * H), (0.245, L["nose"] - 0.06 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0048, 0.0030, smoothstep(0.05, 0.24, uu)) * S * smoothstep(0.0, 0.20, v)   # noqa: F821
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bwave(u, y):
        return 0.0005 * S * math.cos(2 * math.pi * u * 18)
    build_beard(C, top, bot, bthick, bwave, 0.245, L["chin"] - 0.62 * H, reg="hair", NU=11, NV=9)   # noqa: F821
    C.parts[-1]["piece_as"] = "beard"
    moustache(C, "moustache", L["mouth"] + 0.092 * H, 0.60 * s["hw"], 0.07 * H, 0.0, 0.0018 * S, reg="hair", off=0.0016)  # noqa: F821
    C.parts[-1]["piece_as"] = "beard"
    _cap_lathe(C, "turban", "turban", L["brow"] + 0.22 * H,
               [(-0.0050, 1.08), (0.0010, 1.16), (0.0085, 1.18), (0.0160, 1.12), (0.0220, 0.96), (0.0265, 0.66),
                (0.0288, 0.30), (0.0292, 0.0)], N=20, tilt=math.radians(-4), ex=0.0040, ef=0.0026, eb=0.0050,
               subdiv=0)
    _hide_hair_under(C, L["brow"] + 0.22 * H + 0.006 * S)
    _long_robe(C, FRIEND["priest"]["robe"])
    _drop(C, "kneeL", "kneeR")                                              # inside the ankle-length robe (budget)
    wfn = skirt_weights(C)                                                  # noqa: F821
    cols = [0.34 + (2 * math.pi - 0.68) * i / 21 for i in range(22)]
    yb = 0.098 * k

    def off(a, v):
        return (0.0032 + 0.0010 * (1 - v)) * S
    _drape(C, "overrobe", "overrobe", cols, lambda a: yb + 0.010 * S, lambda a: nb - 0.0015 * S, off, wfn, NV=8,
           solid=0.0010)
    _drape(C, "hemband", "hem", cols, lambda a: yb, lambda a: yb + 0.0105 * S,
           lambda a, v: (0.0040 + 0.0004 * (1 - v)) * S, wfn, NV=2, solid=0.0010)


def build_tallguard(C):
    """Long and thin: long neck and nose, thin moustache, tall pointed cloth cap, grey-blue tunic, rust sash, travel
    bags on the back; the lantern (handR, hidden). No weapons."""
    _friend(C)
    s = C.s; S = C.S; L = C.L; H = C.H
    _drop(C, "cap")                                                         # the friend cap -> a taller one
    cb = L["brow"] + 0.26 * H
    _cap_lathe(C, "cap", "cap", cb - 0.06 * H,
               [(-0.0060, 1.06), (0.0, 1.10), (0.0043, 1.06), (0.0107, 0.92), (0.0178, 0.74), (0.0249, 0.54),
                (0.0313, 0.36), (0.0362, 0.20), (0.0391, 0.08), (0.0401, 0.0)], N=18, tilt=math.radians(14),
               ex=0.0036, ef=0.0030, eb=0.0040, subdiv=0)
    moustache(C, "moustache", L["mouth"] + 0.092 * H, 0.62 * s["hw"], 0.06 * H, 0.0, 0.0011 * S, reg="hair", off=0.0014)  # noqa: F821
    C.parts[-1]["piece_as"] = "beard"
    _bags(C)
    add_lantern(C)


def build_shortguard(C):
    """Short and round: big round face, bushy black beard, flat round cap, grey-blue tunic, rust sash, big belly, a bag."""
    _friend(C)
    s = C.s; L = C.L; H = C.H
    _extra_beard(C, "short")                                                # noqa: F821
    _cap_lathe(C, "cap", "cap", L["brow"] + 0.26 * H,
               [(-0.0040, 1.06), (0.0, 1.10), (0.0050, 1.10), (0.0080, 1.00), (0.0100, 0.70), (0.0108, 0.0)], N=20,
               tilt=math.radians(-6), ex=0.0030, ef=0.0024, eb=0.0030, subdiv=0)
    _hide_hair_under(C, L["brow"] + 0.26 * H + 0.008 * C.S)
    _bags(C)


BUILDERS = {"saul": build_saul, "ananias": build_ananias, "barnabas": build_barnabas, "judas": build_judas,
            "priest": build_priest, "tallguard": build_tallguard, "shortguard": build_shortguard,
            "peter": _RS["build_peter_rs"]}


def build_character(ch):
    """The Miracles assembly (via The King Who Serves), then Saul's ropes become a skinned mesh."""
    r = _ls_build_character(ch)
    if ch == "saul":
        _skin_ropes(r[1])
    return r


# =============================================================================================== modes
def _regions_note(rj):
    rj["generatedBy"] = "pipeline/sa_characters.py"
    rj["note"] = ("Per character: colourable regions (face attribute st_region), the mesh parts that carry them, demo "
                  "colour, bbox on the sheet (x, y in art units, y up from the art rect bottom), and anchors (regions "
                  "too small to colour, or with a fixed colour, take a constant UV inside a larger region and print as "
                  "detail lines). ID render for the line art: id_characters_2x.png/.json. All three printed men are the "
                  "Real Miracles friend body (pipeline/mi_characters.py build_friend, unchanged) with this pack's "
                  "costume. The five extras are not printed (offSheet).")
    if "saul" in rj.get("characters", {}):
        rj["characters"]["saul"]["basketRig"] = {
            "bones": {"basket": "hips", "ropeTop": "root"}, "meshes": {"saul_basket": "rigid on basket",
                                                                       "saul_ropes": "skinned: basket + ropeTop"},
            "basketFloorBelowHips": BASKET_DROP, "basketDiameter": BASKET_D, "basketHeight": BASKET_H,
            "ropeTop": list(ROPE_TOP),
            "note": "prop saul/basket shows and hides both (the GLB node saul_ropes sits under the basket joint); the "
                    "ropes take the basket colour (anchor of region basket)"}


def mode_build():
    """The printed cast (the King Who Serves mode_build, generic for humans), then the extras in a fresh Blender."""
    os.environ["LS_NO_EXTRAS"] = "1"
    _LS["mode_build"]()                                                     # noqa: F821
    rp = os.path.join(MODEL, "regions_characters.json")
    rj = json.load(open(rp)); _regions_note(rj)
    json.dump(rj, open(rp, "w"), indent=1, ensure_ascii=False)
    gp = os.path.join(MODEL, "saul.glb")
    if os.path.exists(gp):
        print("ropes under basket:", _ropes_under_basket(gp))
    import subprocess
    subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "--python-exit-code", "1", "--python", SA_FILE,
                    "--", "extras"], check=True)                            # noqa: F821


def friend_paint_material():
    """sa_extras_paint: Principled BSDF with model/extras_paint.png on UV0 (embedded in the extras' GLBs)."""
    m = bpy.data.materials.get("sa_extras_paint") or bpy.data.materials.new("sa_extras_paint")   # noqa: F821
    m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.8
    img = bpy.data.images.load(EXTRAS_PAINT, check_existing=True)          # noqa: F821
    t = nt.nodes.get("paint") or nt.nodes.new("ShaderNodeTexImage"); t.name = "paint"; t.image = img
    uvn = nt.nodes.get("uv0") or nt.nodes.new("ShaderNodeUVMap"); uvn.name = "uv0"; uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


EXTRA_LOOK = {"judas": "short brown beard, striped blue-and-white head cloth, sand tunic, brown apron-sash; bread (handR, "
                       "hidden)",
              "priest": "long white beard, white turban, white robe to the ankles, blue over-robe with a gold hem band",
              "tallguard": "long and thin, tall mustard pointed cap, thin moustache, grey-blue tunic, rust sash, travel "
                           "bags on the back; lantern (handR, hidden)",
              "shortguard": "short and round, flat brown cap, bushy black beard, grey-blue tunic, rust sash, a bag",
              "peter": "the Real Miracles Peter, unchanged (rust-red tunic, sand vest, dark-brown waist cloth, blue-grey "
                       "head cloth, curly black hair and beard); bucket bone kept, no mesh"}


def mode_extras():
    """The five extras: built on a virtual page (EXTRA_PAGE), front ID render (props shown, so they get a colour) ->
    painted texture model/extras_paint.png, UV0 remapped into that texture, GLBs, then appended to characters.blend
    (rigs at EXTRA_BLEND, off the page). (He Is Risen!'s mode_extras with this pack's paths.)"""
    global ONLY
    bpy.ops.wm.read_factory_settings(use_empty=True)                        # noqa: F821
    ONLY = list(EXTRAS)
    SHEET.update({f: list(EXTRA_PAGE[f]) for f in EXTRAS})
    built = {}
    for ch in EXTRAS:
        C, rig, body, props, rep = build_character(ch)
        built[ch] = (C, rig, body, props)
        print(f"[{ch}] tris={tri_count([body] + props)} body={tri_count([body])}")   # noqa: F821
    ids = id_render("extras_id_2x", hide_props=False)                       # noqa: F821
    idp = os.path.join(WORK, "extras_id_2x.png")
    tex = region_texels(idp, ids)                                           # noqa: F821
    x0, y0, cw, chh, W, H = make_friend_paint(idp, ids)                     # noqa: F821
    for o in all_meshes():                                                  # noqa: F821
        uv0 = o.data.uv_layers["UVMap"]
        a = [0.0] * (2 * len(uv0.data)); uv0.data.foreach_get("uv", a)
        for i in range(0, len(a), 2):
            a[i] = (a[i] * W - x0) / cw; a[i + 1] = (a[i + 1] * H - y0) / chh
        uv0.data.foreach_set("uv", a)
    mat = friend_paint_material()
    for o in all_meshes():                                                  # noqa: F821
        me = o.data; me.materials.clear(); me.materials.append(mat)
        me.polygons.foreach_set("material_index", [0] * len(me.polygons))
        assert [u.name for u in me.uv_layers][:2] == ["UVMap", "decal"], o.name
        me.uv_layers.active_index = 0; me.uv_layers["UVMap"].active_render = True
    info = {}
    for ch in EXTRAS:
        C, rig, body, props = built[ch]
        rig.location = (0, 0, 0); bpy.context.view_layer.update()           # noqa: F821
        bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)  # noqa: F821
        for o in rig.children: o.select_set(True)
        bpy.context.view_layer.objects.active = rig                         # noqa: F821
        bpy.ops.export_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"), use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=False, export_def_bones=False,
                                  export_texcoords=True, export_materials='EXPORT', export_morph=False,
                                  export_image_format='AUTO')               # noqa: F821
        rig.location = (EXTRA_BLEND[ch][0], 0, EXTRA_BLEND[ch][1])
        info[ch] = {"height": CONTRACT_HEIGHT[ch], "paint": "assets/saul/model/extras_paint.png",
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
                    "colours": PALETTE[ch], "tris": tri_count([body] + props)}   # noqa: F821
    bpy.context.view_layer.update()                                         # noqa: F821
    tmp = os.path.join(WORK, "extras.blend")
    sc()[REGIONS_KEY + "_extras"] = json.dumps(REGIONS)                     # noqa: F821
    bpy.context.preferences.filepaths.save_version = 0                      # noqa: F821
    bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True)                # noqa: F821
    rp = os.path.join(MODEL, "regions_characters.json")
    if os.path.exists(rp):
        rj = json.load(open(rp)); rj["offSheet"] = info
        rj["offSheetNote"] = ("the five extras: not printed; UV0 samples model/extras_paint.png (fixed demo-palette paint, "
                              "one flat colour per region), face decal on UV1 like the cast")
        json.dump(rj, open(rp, "w"), indent=1, ensure_ascii=False)
    if os.path.exists(BLEND):
        bpy.ops.wm.open_mainfile(filepath=BLEND)                            # noqa: F821
        for o in [o for o in bpy.data.objects if o.name.startswith(tuple(f + "_" for f in EXTRAS))]:   # noqa: F821
            bpy.data.objects.remove(o, do_unlink=True)                      # noqa: F821
        with bpy.data.libraries.load(tmp, link=False) as (src, dst):        # noqa: F821
            dst.objects = [n for n in src.objects if n.startswith(tuple(f + "_" for f in EXTRAS))]
        for o in dst.objects:
            sc().collection.objects.link(o)                                 # noqa: F821
        sc()[REGIONS_KEY + "_extras"] = json.dumps(REGIONS)                 # noqa: F821
        for im in bpy.data.images:                                          # noqa: F821
            if os.path.basename(im.filepath) == "extras_paint.png":
                im.filepath = "//extras_paint.png"
                try:
                    im.pack()
                except Exception:                                           # noqa: BLE001
                    pass
        bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True, relative_remap=True)   # noqa: F821
    try:
        os.remove(tmp)
    except OSError:
        pass
    print("EXTRAS_REPORT", json.dumps({ch: {"tris": v["tris"]} for ch, v in info.items()}), json.dumps(tex["regionsNotSeen"]))
    json.dump(PART_TRIS, open(os.path.join(WORK, "extras_parts.json"), "w"), indent=1)   # noqa: F821


def mode_preview():
    _LS["mode_preview"]()                                                   # noqa: F821


def mode_uvcheck():
    _LS["mode_uvcheck"]()                                                   # noqa: F821


# =============================================================================================== pose tests
def pose_test(rig, ch, variant="a"):
    """Miracles Peter: his own test. The friend men: The King Who Serves generic test (elbows, fingers, thigh + knee,
    spine, head turn, jaw, blink) + every cloth bone swung."""
    if ch == "peter":
        return _MI["pose_test"](rig, ch, variant)                           # noqa: F821
    pose_reset(rig)                                                         # noqa: F821
    if variant == "none":
        return
    B = {b.name: (to_design(b.head_local), to_design(b.tail_local)) for b in rig.data.bones}   # noqa: F821
    for side in "LR":
        h, t = B["forearm" + side]; d = (t - h).normalized()
        bend(rig, "forearm" + side, d.cross(V(0, 0, 1)) * -(1 if side == "L" else -1), 65 if side == "L" else 35)   # noqa: F821
        h, t = B["hand" + side]; dh = (t - h).normalized()
        hz = dh.cross(V(0, 0, 1)).normalized()                              # noqa: F821
        bend(rig, "fingers" + side, hz * (1 if side == "L" else -1), 75)    # noqa: F821
    bend(rig, "upperArmL", V(1, 0, 0), -45)                                 # noqa: F821
    bend(rig, "thighL", V(1, 0, 0), -30); bend(rig, "shinL", V(1, 0, 0), 50)   # noqa: F821
    bend(rig, "spine", V(1, 0, 0), 10); bend(rig, "head", V(0, 1, 0), 25); bend(rig, "jaw", V(1, 0, 0), 14)   # noqa: F821
    rig.pose.bones["eyelids"].scale = (1, 6.0 if variant == "a" else C_LID_CLOSED.get(ch, 12.0), 1)   # noqa: F821
    for eb in EXTRA_BONES[ch]:
        if eb in CLOTH_BEND:
            bend(rig, eb, V(1, 0, 0), CLOTH_BEND[eb])                       # noqa: F821
    bpy.context.view_layer.update()                                         # noqa: F821


def _crouch(rig, hips_dy):
    """Test pose for the basket: hips up / down by hips_dy, thighs forward, shins folded back, arms on the rim."""
    pose_reset(rig)                                                         # noqa: F821
    rig.pose.bones["hips"].location = (0, hips_dy, 0)
    for side, sg in (("L", 1), ("R", -1)):
        bend(rig, "thigh" + side, V(1, 0, 0), -105)                         # noqa: F821
        bend(rig, "shin" + side, V(1, 0, 0), 125)                           # noqa: F821
        bend(rig, "foot" + side, V(1, 0, 0), -20)                           # noqa: F821
        pose_rot(rig, "upperArm" + side, [(V(0, 0, 1), 10 * sg), (V(1, 0, 0), -20)])   # noqa: F821
        bend(rig, "forearm" + side, V(1, 0, 0), -45)                        # noqa: F821
    bend(rig, "spine", V(1, 0, 0), 12); bend(rig, "head", V(1, 0, 0), 14)   # noqa: F821
    bpy.context.view_layer.update()                                         # noqa: F821


def _pts(objs):
    dg = bpy.context.evaluated_depsgraph_get(); out = []                    # noqa: F821
    for o in objs:
        ev = o.evaluated_get(dg); me = ev.to_mesh()
        out += [to_design(o.matrix_world @ v.co) for v in me.vertices]     # noqa: F821
        ev.to_mesh_clear()
    return out


def _stand_box(name, c, size, rgb=(0.72, 0.66, 0.60)):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=to_bl(V(*c)))       # noqa: F821
    o = bpy.context.active_object; o.name = name; o.scale = (size[0], size[2], size[1])
    m = bpy.data.materials.new(name + "_m"); m.use_nodes = True             # noqa: F821
    m.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = rgb + (1,)
    o.data.materials.append(m)
    return o


def mode_posetest():
    imgs = preview_setup()                                                  # noqa: F821
    cam = camera()                                                          # noqa: F821
    present = [ch for ch in CHARS + EXTRAS if bpy.data.objects.get(f"{ch}_rig")]   # noqa: F821
    try:
        rj = json.load(open(os.path.join(MODEL, "regions_characters.json")))
        for ch in present:
            src = rj["characters"].get(ch) or rj.get("offSheet", {}).get(ch)
            C_LID_CLOSED[ch] = src["blink"]["closed"]                       # noqa: F821
    except Exception:                                                       # noqa: BLE001
        pass
    out = {}
    for ch in present:
        rig = bpy.data.objects[f"{ch}_rig"]                                 # noqa: F821
        show([ch])                                                          # noqa: F821
        Hh, hy0, Hd = char_frame(ch)                                        # noqa: F821
        for var in ("a", "b"):
            pose_test(rig, ch, var)
            sc().render.resolution_x, sc().render.resolution_y = 640, 960  # noqa: F821
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), 20 if var == "a" else 70,
                      Hh * 3.1, Hh * 0.18, 60)                              # noqa: F821
            render(os.path.join(WORK, f"pose_{ch}_{var}.png"))              # noqa: F821
        sc().render.resolution_x, sc().render.resolution_y = 540, 540      # noqa: F821
        pose_test(rig, ch, "b")
        turntable(cam, Vector((rig.location.x, 0, rig.location.z + hy0)), 25, Hd * 4.2, Hd * 0.1, 60)   # noqa: F821
        render(os.path.join(WORK, f"pose_{ch}_closed.png"))                 # noqa: F821
        pose_test(rig, ch, "none")
    sc().render.resolution_x, sc().render.resolution_y = 960, 720          # noqa: F821
    # ---- props shown in the hand
    for ch, nm in (("saul", "letters"), ("saul", "bread"), ("ananias", "jug"), ("tallguard", "lantern"),
                   ("judas", "bread")):
        if ch not in present:
            continue
        rig = bpy.data.objects[f"{ch}_rig"]                                 # noqa: F821
        show([ch])                                                          # noqa: F821
        for o in rig.children:
            if o.name == f"{ch}_{nm}":
                o.hide_render = False
        turntable(cam, Vector((rig.location.x, 0, rig.location.z + 0.16)), 30, 0.95, 0.20, 60)   # noqa: F821
        render(os.path.join(WORK, f"fit_{ch}_{nm}.png"))                    # noqa: F821
    # ---- the basket rig: Saul moved off the page, a stand-in wall face + window (rig-local x WALL_FACE_X)
    if "saul" in present:
        rig = bpy.data.objects["saul_rig"]; keep = rig.location.copy()       # noqa: F821
        X0 = 3.0
        rig.location = to_bl(V(X0, 0, 0))                                   # noqa: F821
        wall = _stand_box("sa_wall", (X0 + WALL_FACE_X - 0.03, 0.15, 0.0), (0.06, 0.30, 0.30))
        win = _stand_box("sa_window", (X0 + WALL_FACE_X - 0.001, 0.235, 0.0), (0.004, 0.07, 0.07), (0.15, 0.12, 0.10))
        body = bpy.data.objects["saul_body"]; bk = bpy.data.objects["saul_basket"]; rp = bpy.data.objects["saul_ropes"]   # noqa: F821
        show(["saul"])                                                      # noqa: F821
        bk.hide_render = False; rp.hide_render = False
        hips0 = to_design(rig.matrix_world @ rig.data.bones["hips"].head_local)   # noqa: F821
        info = {}
        for nm, floor in (("basket_wait", 0.17), ("basket_down", 0.0)):
            dy = floor - (hips0.y - BASKET_DROP)
            _crouch(rig, dy)
            P = _pts([rp]); Bk = _pts([bk]); Bd = _pts([body])
            topy = max(p.y for p in P)
            info[nm] = {"hipsDy": round(dy, 4), "basketBottom": round(min(p.y for p in Bk), 4),
                        "basketMinXLocal": round(min(p.x for p in Bk) - X0, 4),
                        "ropeTopY": round(topy, 4), "ropeMaxLen": round(max(p.y for p in P) - min(p.y for p in P), 4),
                        "ropeTopXLocal": round(min(p.x for p in P) - X0, 4),
                        "bodyMinY": round(min(p.y for p in Bd), 4),
                        "bodyBelowBasketFloor": round(min(p.y for p in Bd) - (min(p.y for p in Bk) + 0.004), 4)}
            for vw, yaw in (("", 0), ("_side", 90)):
                turntable(cam, Vector((X0 - 0.02, 0, 0.16)), yaw, 0.95, 0.12, 60)   # noqa: F821
                render(os.path.join(WORK, f"fit_{nm}{vw}.png"))             # noqa: F821
        out["basket"] = info
        # seated on the ground (fall_down end, test pose): hips down, thighs forward, lean back on one hand
        pose_reset(rig)                                                     # noqa: F821
        rig.pose.bones["hips"].location = (0, -(hips0.y - 0.040), 0)
        for side in "LR":
            bend(rig, "thigh" + side, V(1, 0, 0), -88); bend(rig, "shin" + side, V(1, 0, 0), 30)   # noqa: F821
        bend(rig, "spine", V(1, 0, 0), -12)                                 # noqa: F821
        bpy.context.view_layer.update()                                     # noqa: F821
        bk.hide_render = True; rp.hide_render = True
        out["seated"] = {"minY": round(min(p.y for p in _pts([body])), 4), "hipsHeadY": 0.040}
        turntable(cam, Vector((X0, 0, 0.12)), 60, 0.95, 0.15, 60); render(os.path.join(WORK, "fit_saul_seated.png"))   # noqa: F821
        pose_reset(rig); rig.location = keep                                # noqa: F821
        for o in (wall, win):
            bpy.data.objects.remove(o, do_unlink=True)                      # noqa: F821
    # ---- the guards side by side, Saul / Peter at 0.10 facing each other
    if "tallguard" in present and "shortguard" in present:
        show(["tallguard", "shortguard"])                                   # noqa: F821
        tg, sg_ = bpy.data.objects["tallguard_rig"], bpy.data.objects["shortguard_rig"]   # noqa: F821
        cx = (tg.location.x + sg_.location.x) / 2
        turntable(cam, Vector((cx, 0, 0.20)), 15, 1.1, 0.15, 60); render(os.path.join(WORK, "fit_guards_pair.png"))   # noqa: F821
    if "saul" in present and "peter" in present:
        sr, pr = bpy.data.objects["saul_rig"], bpy.data.objects["peter_rig"]   # noqa: F821
        ks, kp = sr.location.copy(), pr.location.copy()
        sr.location = to_bl(V(3.0, 0, 0.05)); sr.rotation_euler = (0, 0, math.radians(180))   # noqa: F821
        pr.location = to_bl(V(3.0, 0, -0.05))                               # noqa: F821
        show(["saul", "peter"])                                             # noqa: F821
        turntable(cam, Vector((3.0, 0, 0.20)), 90, 1.0, 0.15, 60); render(os.path.join(WORK, "fit_pair_hug.png"))   # noqa: F821
        sr.location = ks; pr.location = kp; sr.rotation_euler = (0, 0, 0)
    json.dump(out, open(os.path.join(WORK, "posetest.json"), "w"), indent=1)
    print("POSETEST done", json.dumps(out))


def mode_verify():
    """The King Who Serves verify (bones, parents, budget, heights), then Saul's ropes: skinned to basket + ropeTop and
    sitting under the basket joint in the GLB."""
    _LS["mode_verify"]()                                                    # noqa: F821
    vp = os.path.join(WORK, "verify.json"); v = json.load(open(vp))
    p = os.path.join(MODEL, "saul.glb")
    if os.path.exists(p) and "saul" in v:
        d = open(p, "rb").read(); n0 = struct.unpack("<I", d[12:16])[0]; j = json.loads(d[20:20 + n0])
        nm = [nd.get("name") for nd in j["nodes"]]
        ri = nm.index("saul_ropes") if "saul_ropes" in nm else None
        par = [nm[i] for i, nd in enumerate(j["nodes"]) if ri is not None and ri in nd.get("children", [])]
        skin = j["nodes"][ri].get("skin") if ri is not None else None
        joints = [nm[k] for k in j["skins"][skin]["joints"]] if skin is not None else []
        v["saul"]["ropes"] = {"node": ri is not None, "parent": par[0] if par else None, "skinned": skin is not None,
                              "skinHasBasketAndRopeTop": {"basket", "ropeTop"} <= set(joints)}
        json.dump(v, open(vp, "w"), indent=1)
    print("VERIFY", json.dumps({c: {k_: x for k_, x in i.items() if k_ not in ("meshes", "parents")} for c, i in v.items()}))


if __name__ == "__main__":
    {"build": mode_build, "extras": mode_extras, "preview": mode_preview, "posetest": mode_posetest,
     "verify": mode_verify, "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), SA_FILE, "all"],
                                                 check=True)}[argv[0] if argv else "build"]()   # noqa: F821
