"""Real Miracles (story pack #10): characters jesus, peter, man (+ friend1..friend4, not on the sheet) — meshes, rigs,
weights, UVs, face decals, previews, GLBs.

Contract: docs/miracles/CONTRACT.md §2-§3 (ids, sizes, sheet slots, bone names, props), look: docs/miracles/DESIGN.md
§1 and §3, notes for Animation: docs/miracles/RIG.md. Built on the shared kit (pipeline/story_kit/characters.py:
procedural quad cages, heads mapped from the D&G base head by landmarks, box-modelled hands, face decals on UV1 + an
`eyelids` blink, UV0 = front page projection with occlusion + ID-render fixes), in the shape of
pipeline/jn_characters.py (Jonah: sculpted hair / beard locks, sandals, fixed-colour decal swatches). New here:
  * Jesus: shoulder-length wavy hair parted in the middle, short full beard, long cream tunic, a warm brown mantle over
    the left shoulder and wrapped round the waist (one panel; its back drape on `mantle1`), a tan cloth belt with a
    hanging end (`belt1`), sandals;
  * Peter: curly black hair and beard, a blue-grey head cloth (band round the head, knot and short tail on `cloth1`),
    rust-red knee tunic with sleeves rolled to the elbow, sand over-vest, dark-brown waist cloth under a thick rope belt
    (fixed colour), bare forearms, big hands, sandals; a hidden wooden `bucket` in the right hand;
  * the man on the mat: thin, short light-brown hair, scruffy beard, pale green knee tunic, mustard sash (`sash1`),
    barefoot; his striped sleeping `mat` with two carrying poles (child of root, SHOWN, lies flat on the page in the
    rest pose: CONTRACT §3), four `ropes` (child of mat, hidden) and the rolled mat `matRoll` (child of chest, hidden).
    The mat is printed as its own shape: for the sheet (ID render + UV0 projection only) it is stood up to face the
    viewer at MAT_SHEET (design.json characters.man.matSheet overrides), then put back flat for the GLB;
  * the four friends: not on the sheet; fixed paint model/friend_paint.png on UV0 from their own front ID render on a
    virtual page (Esther's GUARDS method), four silhouettes (leader, big and round, small with a head band, lanky with a
    pointed cap), one shared set of face drawings (identical head proportions) docs/miracles/design/faces/friend_*.png.

Run (repo root):
  python3 pipeline/mi_characters.py all                                           # everything below, in order
  python3 pipeline/mi_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/mi_characters.py -- build        # cast + friends, GLBs, blend, ID render
  blender -b --factory-startup --python pipeline/mi_characters.py -- friends      # friends only (run by build)
  python3 pipeline/mi_characters.py proof                                         # $MI_WORK/uvproof.png
  blender -b --factory-startup --python pipeline/mi_characters.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/mi_characters.py -- uvcheck      # models wearing uvproof.png
  blender -b --factory-startup --python pipeline/mi_characters.py -- posetest     # bend / blink / jaw / cloth / lying
  blender -b --factory-startup --python pipeline/mi_characters.py -- verify       # re-import GLBs, check bones/budget
  python3 pipeline/mi_characters.py compose                                       # preview_*.png contact sheets
Blender: $BLENDER, else `blender` on PATH, else /Applications/Blender.app. Intermediate renders go to $MI_WORK
(default /tmp/miracles_chars/work). MI_ONLY=man (comma list) builds a subset of the cast (debug only).
"""
import sys, os, json, math, random, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/miracles/model")
FACES = os.path.join(ROOT, "docs/miracles/design/faces")
WORK = os.environ.get("MI_WORK", "/tmp/miracles_chars/work")
ENV = "MI_"
PAGE_MATERIAL = "mi_page"
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/miracles/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("man", "jesus", "peter")                 # printed cast, sheet order left -> right
FRIENDS = ("friend1", "friend2", "friend3", "friend4")
HUMANS = CHARS + FRIENDS
FISH = ()
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
EXTRA_BONES = {"jesus": ["mantle1", "belt1"], "peter": ["cloth1", "bucket"],
               "man": ["mat", "ropes", "matRoll", "sash1"],
               "friend1": ["belt1"], "friend2": ["belt1"], "friend3": ["belt1", "band1"], "friend4": ["belt1"]}


def bone_list(ch):
    return CONTRACT_BONES + EXTRA_BONES[ch]


PROPS = {"jesus": {}, "peter": {"bucket": False}, "man": {"mat": True, "ropes": False, "matRoll": False},
         "friend1": {}, "friend2": {}, "friend3": {}, "friend4": {}}      # prop bone -> shown by default
CONTRACT_HEIGHT = {"man": 0.34, "jesus": 0.36, "peter": 0.38,
                   "friend1": 0.35, "friend2": 0.37, "friend3": 0.33, "friend4": 0.36}
BUDGET = {"man": 25000, "jesus": 25000, "peter": 25000,
          "friend1": 18000, "friend2": 18000, "friend3": 18000, "friend4": 18000}
DEFAULT_SHEET = {"man": (-0.32, 0.015), "jesus": (0.0, 0.015), "peter": (0.32, 0.015)}
# the mat on the sheet: stood up to face the viewer (plan view of its top), centre (x, y) on the page; poles to +-0.20
MAT_SHEET_DEFAULT = (-0.28, 0.47)
# the mat in the rest pose (CONTRACT §3): centre (0, 0, -0.02), long axis X, pad 0.30 x 0.12, poles to +-0.20, top 0.025
MAT = dict(cz=-0.02, hx=0.150, hz=0.060, top=0.025, bot=0.004, pole_x=0.200, pole_r=0.0072, pole_y=0.0090,
           pole_z=0.0675, rope_h=0.45)
# friends: virtual page for their own ID render (two rows, so the hands never overlap) and rig places in the blend
FRIEND_PAGE = {"friend1": (-0.20, 0.015), "friend2": (0.20, 0.015), "friend3": (-0.20, 0.58), "friend4": (0.20, 0.58)}
FRIEND_BLEND = {"friend1": (0.80, 0.0), "friend2": (1.00, 0.0), "friend3": (1.20, 0.0), "friend4": (1.40, 0.0)}
FRIEND_PAINT = os.path.join(MODEL, "friend_paint.png")
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (as Ruth / Daniel / Jonah)

# ---------------------------------------------------------------------------------------------- palette (DESIGN §3)
PALETTE = {
    "jesus": {"skin": "#C99268", "hair": "#4A3020", "tunic": "#F2E8D2", "mantle": "#9A5B34", "belt": "#D2AE74",
              "sandals": "#7A4E2E"},
    "peter": {"skin": "#BF8460", "hair": "#231A16", "tunic": "#B4502F", "vest": "#D9C29A", "waistcloth": "#5A3A26",
              "headcloth": "#6E8AA6", "rope": "#C8A472", "sandals": "#7A4E2E", "bucket": "#8A5A3B"},
    "man": {"skin": "#D2A07A", "hair": "#9A6B42", "tunic": "#A9CF8E", "sash": "#D9A93A", "mat": "#F1E3C4",
            "stripes": "#C2453A", "poles": "#7A5636", "ropes": "#C8A472", "roll": "#F1E3C4", "rollStripes": "#C2453A"},
    "friend1": {"skin": "#C68E64", "hair": "#1E1814", "tunic": "#E8843A", "belt": "#D2AE74", "sandals": "#7A4E2E"},
    "friend2": {"skin": "#B87C56", "hair": "#3A2A20", "tunic": "#2E9A92", "belt": "#D2AE74", "sandals": "#7A4E2E"},
    "friend3": {"skin": "#D6A27A", "hair": "#4A3020", "tunic": "#EFC53F", "belt": "#D2AE74", "sandals": "#7A4E2E",
                "band": "#C2453A"},
    "friend4": {"skin": "#C08A62", "hair": "#2A2018", "tunic": "#5A5FB8", "belt": "#D2AE74", "sandals": "#7A4E2E",
                "cap": "#A8433A"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发和胡子", "hair and beard"), "tunic": ("长衣", "tunic"),
    "mantle": ("外袍", "mantle"), "belt": ("腰带", "belt"), "sandals": ("凉鞋", "sandals"),
    "vest": ("背心", "vest"), "waistcloth": ("腰布", "waist cloth"), "headcloth": ("头巾", "head cloth"),
    "rope": ("绳腰带", "rope belt"), "bucket": ("水桶", "bucket"), "sash": ("腰带", "sash"),
    "mat": ("褥子", "mat"), "stripes": ("褥子条纹", "mat stripes"), "poles": ("抬杆", "carrying poles"),
    "ropes": ("绳子", "ropes"), "roll": ("卷起的褥子", "rolled mat"), "rollStripes": ("卷起的条纹", "rolled stripes"),
    "band": ("头带", "head band"), "cap": ("尖帽", "pointed cap"),
}
# fixed-colour parts (DESIGN §1: "fixed-colour detail lines, not regions"): their UV1 points at a swatch in the corner
# of every decal of that character (SWATCHES, decal space 0..1, y up); their UV0 is anchored (ANCHORS) so they print as
# detail lines inside a neighbour
SWATCHES = {
    "jesus": {"sandals": (0.955, 0.925, 0.995, 0.995)},
    "peter": {"rope": (0.905, 0.925, 0.950, 0.995), "sandals": (0.955, 0.925, 0.995, 0.995)},
    "man": {"poles": (0.905, 0.925, 0.950, 0.995), "ropes": (0.955, 0.925, 0.995, 0.995)},
}
SWATCH_COL = {"sandals": (122, 78, 46), "rope": (200, 164, 114), "poles": (122, 86, 54), "ropes": (200, 164, 114)}
# regions too small to colour on A4 (or fixed-colour detail): constant UV0 deep inside a printed region
ANCHORS = {
    "jesus": {"sandals": "jesus.tunic"},
    "peter": {"sandals": "peter.tunic", "rope": "peter.waistcloth"},
    "man": {"poles": "man.mat", "ropes": "man.mat"},
}
# hidden-by-default props are not printed: their regions sample a printed region of similar colour (first target that
# exists wins; "set.<region>" = a region of the set's printed drawings); design.json characters.<id>.propUV wins
PROP_ANCHORS = {
    "peter": {"bucket": ["set.hull", "set.boatHull", "set.boat", "set.beams", "peter.waistcloth"]},
    "man": {"roll": "man.mat", "rollStripes": "man.stripes"},
}
# parts whose printed area is a sliver: every face of (part, region) takes one UV inside a larger region
PART_ANCHORS = {ch: {("handL", "skin"): f"{ch}.FACE", ("handR", "skin"): f"{ch}.FACE",
                     ("legL", "skin"): f"{ch}.FACE", ("legR", "skin"): f"{ch}.FACE"} for ch in CHARS}
PART_ANCHORS["peter"].update({("kneeL", "skin"): "peter.FACE", ("kneeR", "skin"): "peter.FACE",
                              ("armL", "skin"): "peter.FACE", ("armR", "skin"): "peter.FACE"})
PART_ANCHORS["man"].update({("kneeL", "skin"): "man.FACE", ("kneeR", "skin"): "man.FACE"})
PART_ANCHORS["jesus"].update({("beltFringe", "belt"): "jesus.belt"})

# ---------------------------------------------------------------------------------------------- proportions
FR = dict(mouth=0.163, nose=0.273, eye=0.490, brow=0.583)
_LEN = ("top", "chin", "hw", "zc", "noseH", "neckBase", "chestY", "waistY", "hipY", "hipX", "kneeY", "ankleY",
        "footLen", "upperArm", "forearm", "hand")


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                      # noqa: E402
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "characters")   # shared characters functions (docs/STORY-KIT.md)


KING = dict(height=0.40, top=0.354, chin=0.294, hw=0.0222, zc=-0.002, depth=1.06, jaw=0.10, cheek=0.04,
            chin_narrow=0.0, crown=0.0, noseH=0.0028, nose_w=1.12, nose_long=0.0, brow=1.15, lips=0.9,
            chinAmt=0.6, sockets=1.0, cheekbones=1.0,
            neckBase=0.273, neck=(0.0108, 0.0098, -0.0108), shoulder=(0.046, 0.266), chestY=0.246,
            waistY=0.218, hipY=0.190, hipX=0.0200, kneeY=0.100, ankleY=0.019, footLen=0.044, footScale=1.15,
            upperArm=0.066, forearm=0.056, hand=0.037, palmFrac=0.52,
            handDims=dict(palmW=0.0154, palmH=0.0064, wristW=0.0112, wristH=0.0078, fingerW=0.0039,
                          fingerT=0.0036, thumbW=0.0040, thumbT=0.0036, armR=0.0072))
SPEC = {
    # Jesus: about thirty, kind open face, shoulder-length hair, short full beard (0.36 with the hair)
    "jesus": scaled(KING, 0.985, 1.0, height=0.36, top=0.352, chin=0.290, hw=0.0212, jaw=0.06, cheek=0.10,
                    chin_narrow=0.02, noseH=0.0032, nose_w=1.15, nose_long=0.12, brow=1.08, lips=0.92, chinAmt=0.55,
                    sockets=0.95, cheekbones=0.95, fr=dict(eye=0.500, brow=0.590, nose=0.280, mouth=0.168)),
    # Peter: about thirty-five, broad, weathered, big nose, bushy brows, big forearms and hands (0.38 with the cloth)
    "peter": scaled(KING, 1.05, 1.16, height=0.38, jaw=0.24, cheek=0.50, noseH=0.0040, nose_w=1.40, nose_long=0.10,
                    brow=1.18, lips=0.95, chinAmt=0.5, cheekbones=0.85, footScale=1.30,
                    fr=dict(eye=0.488, brow=0.580, nose=0.268, mouth=0.160)),
    # the man: about twenty-five, thin face, big hopeful eyes, short hair, scruffy short beard (0.34 with the hair)
    "man": scaled(KING, 0.935, 0.90, height=0.34, top=0.3335, chin=0.2765, hw=0.0196, jaw=0.0, cheek=-0.05,
                  chin_narrow=0.06, noseH=0.0030, nose_w=1.0, nose_long=0.05, brow=1.0, lips=0.85, chinAmt=0.65,
                  sockets=1.05, cheekbones=1.10, footScale=1.10, fr=dict(eye=0.500, brow=0.590, nose=0.280, mouth=0.168)),
}
SPEC["peter"]["handDims"] = {k: v * 1.22 for k, v in SPEC["peter"]["handDims"].items()}
SPEC["peter"]["handDims"]["armR"] *= 1.18
SPEC["peter"]["hand"] *= 1.12
SPEC["jesus"]["handDims"] = {k: v * 1.08 for k, v in SPEC["jesus"]["handDims"].items()}
SPEC["jesus"]["hand"] *= 1.05
SPEC["man"]["handDims"] = {k: v * 1.02 for k, v in SPEC["man"]["handDims"].items()}
# friends: one head (identical proportions, so they share one set of face drawings), different bodies. k = body
# length scale; bodyX widens or narrows the torso / hips / shoulders (applied in build_friend), the head keeps kx = k.
_FHEAD = dict(jaw=0.12, cheek=0.20, noseH=0.0034, nose_w=1.18, brow=1.10, lips=0.9, chinAmt=0.55, cheekbones=0.95,
              fr=dict(eye=0.496, brow=0.586, nose=0.275, mouth=0.165))
FRIEND = {   # body length k (skull top = 0.354 k), torso width, belly
    "friend1": dict(k=0.972, bodyX=0.92, belly=0.0, hair="short"),          # the leader: slim, 0.35
    "friend2": dict(k=1.042, bodyX=1.28, belly=1.0, hair="fringe"),         # big and round, bald with a fringe, 0.37
    "friend3": dict(k=0.910, bodyX=0.98, belly=0.0, hair="curly"),          # small and quick, head band, 0.33
    "friend4": dict(k=0.918, bodyX=0.82, belly=0.0, hair="cap"),            # lanky, pointed cap, 0.36
}
_FH = 0.0596           # one head size for all four (top - chin), hw 0.0219
for _f, _v in FRIEND.items():
    _k = _v["k"]
    _sp = scaled(KING, _k, _k, height=CONTRACT_HEIGHT[_f], **_FHEAD)
    _sp["chin"] = _sp["top"] - _FH; _sp["hw"] = 0.0219
    _sp["shoulder"] = (_sp["shoulder"][0] * _v["bodyX"], _sp["shoulder"][1])
    _sp["hipX"] = _sp["hipX"] * min(1.25, _v["bodyX"])
    if _f == "friend2":
        _sp["handDims"] = {a: x * 1.10 for a, x in _sp["handDims"].items()}
    if _f == "friend4":            # lanky: longer arms
        _sp["upperArm"] *= 1.07; _sp["forearm"] *= 1.07
    SPEC[_f] = _sp
FIST = set()
FIST_BEND = {}
EYE = {"jesus": (0.400, 0.330, 0.226), "peter": (0.415, 0.300, 0.214), "man": (0.405, 0.350, 0.250)}
EYE.update({f: (0.405, 0.320, 0.222) for f in FRIENDS})

EXPRESSIONS = {"jesus": ["kind", "talk", "smile", "laugh", "sleep", "firm", "gentle", "look_up"],
               "peter": ["jolly", "talk", "shock", "wail", "laugh", "scared", "amazed", "squint"],
               "man": ["shy", "talk", "nervous", "hope", "wonder", "joy", "laugh"]}
FRIEND_EXPRESSIONS = ["happy", "talk", "strain", "oof", "think", "idea", "cheer"]
EXPRESSIONS.update({f: FRIEND_EXPRESSIONS for f in FRIENDS})
DEFAULT_EXPR = {"jesus": "kind", "peter": "jolly", "man": "shy"}
DEFAULT_EXPR.update({f: "happy" for f in FRIENDS})
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "jesus": {"idle": "kind", "talk": "talk", "walk": "kind", "teach": "talk", "look_up_smile": "look_up",
              "kneel_kind": "gentle", "stand_talk": "talk", "command_rise": "firm", "lie_sleep": "sleep",
              "wake_up": "gentle", "calm_storm": "firm", "laugh": "laugh", "wave": "smile"},
    "peter": {"idle": "jolly", "talk": "talk", "walk": "jolly", "roof_shock": "shock", "dust_off": "squint",
              "laugh": "laugh", "steer": "jolly", "steer_hard": "squint", "bail": "scared", "shake_awake": "wail",
              "amazed": "amazed", "cower": "scared", "wave": "jolly"},
    "man": {"lie_mat": "shy", "carried": "nervous", "lowered": "nervous", "sit_up": "wonder", "stand_wobbly": "hope",
            "jump_joy": "joy", "roll_mat": "joy", "dance_mat": "laugh", "walk_mat": "joy", "talk": "talk",
            "idle": "joy", "wave": "joy"},
}
_FCLIP = {"idle": "happy", "walk": "happy", "carry_front": "strain", "carry_back": "strain", "squeeze_bounce": "oof",
          "think": "think", "idea": "idea", "dig": "strain", "lower_rope": "strain", "peek": "happy", "cheer": "cheer",
          "wave": "happy"}
CLIP_EXPRESSION.update({f: _FCLIP for f in FRIENDS})


def face_file(ch, ex):
    """Friends share one drawing per expression (identical head proportions): faces/friend_<expr>.png."""
    return os.path.join(FACES, f"{'friend' if ch in FRIENDS else ch}_{ex}.png")


def mat_sheet():
    """Centre of the mat's printed shape on the page: design.json characters.man.matSheet [x, y] (Set + sheet role),
    else MAT_SHEET_DEFAULT."""
    if os.path.exists(DESIGN_JSON):
        try:
            v = json.load(open(DESIGN_JSON)).get("characters", {}).get("man", {}).get("matSheet")
            if v:
                return (float(v[0]), float(v[1]))
        except Exception:                                        # noqa: BLE001
            pass
    return MAT_SHEET_DEFAULT


def draw_faces():
    from PIL import Image, ImageDraw, ImageFilter
    SS = 4; PX = 512; N = PX * SS
    INK = (43, 29, 23, 255)

    def P(x, y):
        return (x * N, (1 - y) * N)

    def bez(p0, p1, p2, p3, n=40):
        out = []
        for i in range(n + 1):
            t = i / n; a = (1 - t) ** 3; b = 3 * (1 - t) ** 2 * t; c = 3 * (1 - t) * t * t; d = t ** 3
            out.append((a * p0[0] + b * p1[0] + c * p2[0] + d * p3[0], a * p0[1] + b * p1[1] + c * p2[1] + d * p3[1]))
        return out

    def stroke(dr, pts, w0, w1=None, col=INK, wmid=None):
        """Round-capped stroke with a width profile (normalised units of the decal)."""
        w1 = w0 if w1 is None else w1
        n = len(pts)
        for i in range(n - 1):
            t = i / (n - 1)
            w = (w0 + (w1 - w0) * t) if wmid is None else (
                w0 + (wmid - w0) * (t / 0.5) if t < 0.5 else wmid + (w1 - wmid) * ((t - 0.5) / 0.5))
            a, b = P(*pts[i]), P(*pts[i + 1])
            r = w * N / 2
            steps = max(1, int(math.dist(a, b) / max(1.0, r * 0.35)))
            for k in range(steps + 1):
                f = k / steps
                x = a[0] + (b[0] - a[0]) * f; y = a[1] + (b[1] - a[1]) * f
                dr.ellipse((x - r, y - r, x + r, y + r), fill=col)

    def poly(dr, pts, col):
        dr.polygon([P(*p) for p in pts], fill=col)

    def eye(img, c, half, look=(0.0, 0.0), top=1.0, bot=1.0, tilt=0.0, lash=0, iris=(92, 58, 36), lid=0.10,
            side=1, mode="open", inner_up=0.0, pupil=0.55, line=0.020, lower=True, wet=False):
        """Almond eye. c centre, half (ew, eh) normalised; top/bot scale the upper/lower arcs (openness);
        tilt raises the outer corner; side +1 = character's left eye (viewer's right). mode: open | happy | closed."""
        dr = ImageDraw.Draw(img)
        cx, cy = c; ew, eh = half
        o = side            # outer corner direction in x
        inner = (cx - o * ew, cy - tilt * eh * 0.5 + inner_up * eh)
        outer = (cx + o * ew, cy + tilt * eh * 0.5)
        if mode == "happy":       # upside-down U, thick, with lashes
            pts = bez(inner, (cx - o * ew * 0.6, cy + eh * 1.25), (cx + o * ew * 0.6, cy + eh * 1.25), outer)
            pts = [(x, y - eh * 0.25) for x, y in pts]
            stroke(dr, pts, line * 1.3, line * 1.1, wmid=line * 1.6)
            if lash:
                ox, oy = pts[-1]
                stroke(dr, [(ox, oy), (ox + o * ew * 0.22, oy + eh * 0.25)], line * 0.9, line * 0.3)
            return
        if mode == "closed":      # calm closed: downward arc with lashes
            pts = bez(inner, (cx - o * ew * 0.5, cy - eh * 0.75), (cx + o * ew * 0.5, cy - eh * 0.75), outer)
            stroke(dr, pts, line * 1.2, line * 1.0, wmid=line * 1.5)
            if lash:
                for f, ln in ((0.55, 0.20), (0.75, 0.26), (0.92, 0.30)):
                    x, y = pts[int(f * (len(pts) - 1))]
                    stroke(dr, [(x, y), (x + o * ew * 0.10 * ln / 0.2, y - eh * ln * 1.3)], line * 0.6, line * 0.25)
            return
        up = bez(inner, (cx - o * ew * 0.55, cy + eh * 1.30 * top + inner_up * eh * 0.5),
                 (cx + o * ew * 0.45, cy + eh * 1.30 * top), outer)
        dn = bez(outer, (cx + o * ew * 0.45, cy - eh * 1.15 * bot), (cx - o * ew * 0.55, cy - eh * 1.15 * bot), inner)
        white = Image.new("L", (N, N), 0); dw = ImageDraw.Draw(white)
        dw.polygon([P(*p) for p in up + dn], fill=255)
        layer = Image.new("RGBA", (N, N), (0, 0, 0, 0)); dl = ImageDraw.Draw(layer)
        dl.rectangle((0, 0, N, N), fill=(255, 253, 248, 255))
        ix, iy = cx + look[0] * ew * 0.45, cy + look[1] * eh * 0.40 - 0.08 * eh
        ir = eh * 1.02
        dl.ellipse((P(ix - ir, iy + ir)[0], P(ix - ir, iy + ir)[1], P(ix + ir, iy - ir)[0], P(ix + ir, iy - ir)[1]),
                   fill=iris + (255,))
        ir2 = ir * 0.80          # darker rim / lighter lower half for depth
        dk = tuple(int(v * 0.55) for v in iris)
        dl.ellipse((P(ix - ir, iy + ir)[0], P(ix - ir, iy + ir)[1], P(ix + ir, iy - ir)[0], P(ix + ir, iy - ir)[1]),
                   outline=dk + (255,), width=int(ir * 0.16 * N))
        lt = tuple(min(255, int(v * 1.35 + 20)) for v in iris)
        dl.chord((P(ix - ir2, iy + ir2)[0], P(ix - ir2, iy + ir2)[1], P(ix + ir2, iy - ir2)[0], P(ix + ir2, iy - ir2)[1]),
                 20, 160, fill=lt + (255,))
        pr = ir * pupil
        dl.ellipse((P(ix - pr, iy + pr)[0], P(ix - pr, iy + pr)[1], P(ix + pr, iy - pr)[0], P(ix + pr, iy - pr)[1]),
                   fill=(24, 16, 12, 255))
        h1 = ir * 0.40; hx, hy = ix + ir * 0.36, iy + ir * 0.40
        dl.ellipse((P(hx - h1, hy + h1)[0], P(hx - h1, hy + h1)[1], P(hx + h1, hy - h1)[0], P(hx + h1, hy - h1)[1]),
                   fill=(255, 255, 255, 255))
        h2 = ir * 0.18; hx, hy = ix - ir * 0.40, iy - ir * 0.40
        dl.ellipse((P(hx - h2, hy + h2)[0], P(hx - h2, hy + h2)[1], P(hx + h2, hy - h2)[0], P(hx + h2, hy - h2)[1]),
                   fill=(255, 255, 255, 230))
        h3 = ir * 0.09; hx, hy = ix + ir * 0.62, iy + ir * 0.02          # a third tiny sparkle
        dl.ellipse((P(hx - h3, hy + h3)[0], P(hx - h3, hy + h3)[1], P(hx + h3, hy - h3)[0], P(hx + h3, hy - h3)[1]),
                   fill=(255, 255, 255, 210))
        if wet:
            dl.ellipse((P(ix - ir * 0.9, iy - ir * 0.55)[0], P(ix - ir * 0.9, iy - ir * 0.55)[1],
                        P(ix + ir * 0.9, iy - ir * 0.95)[0], P(ix + ir * 0.9, iy - ir * 0.95)[1]), fill=(200, 230, 255, 160))
        # upper-lid shadow inside the white
        sh = Image.new("RGBA", (N, N), (0, 0, 0, 0)); ds = ImageDraw.Draw(sh)
        stroke(ds, up, line * 2.2, line * 2.2, col=(120, 90, 80, 70))
        layer = Image.alpha_composite(layer, sh)
        img.paste(layer, (0, 0), white)
        dr = ImageDraw.Draw(img)
        stroke(dr, up, line * (1.0 + lid), line * (1.35 + lid * 2), wmid=line * (1.5 + lid * 2))
        if lower:
            stroke(dr, dn[3:-6], line * 0.35, line * 0.55, col=(90, 60, 50, 200))
        if lash:
            ox, oy = up[-1]
            for k, (dx, dy, w) in enumerate(((0.30, 0.22, 0.85), (0.16, 0.36, 0.7), (0.04, 0.40, 0.55))[:lash]):
                p0 = up[-1 - k * 4]
                pm = (p0[0] + o * ew * dx * 0.4, p0[1] + eh * dy * 0.7)
                stroke(dr, [p0, pm, (p0[0] + o * ew * dx, p0[1] + eh * dy)], line * w, line * 0.22)

    def brow(dr, side, c, half, raise_=0.0, inner=0.0, arch=0.35, w=0.028, col=(59, 36, 24, 255), length=1.05,
             thick=1.0, outer=0.0):
        cx, cy = c; ew, eh = half; o = side
        y0 = cy + raise_ - 0.045
        pi = (cx - o * ew * 0.95 * length, y0 + inner)
        po = (cx + o * ew * 1.10 * length, y0 - eh * 0.25 + outer)
        pts = bez(pi, (cx - o * ew * 0.35, y0 + inner * 0.6 + eh * arch), (cx + o * ew * 0.45, y0 + eh * arch * 0.9 + outer * 0.5), po)
        stroke(dr, pts, w * 1.25 * thick, w * 0.35 * thick, wmid=w * 1.15 * thick, col=col)

    def mouth(img, kind, cx, cy, wd, lipcol=None, jaw=0.0, side=0.0):
        """kind: smile | flat | frown | small | open | o | grin | smirk | shout | wobbly | soft"""
        dr = ImageDraw.Draw(img)
        L, R = (cx - wd, cy), (cx + wd, cy)
        if kind in ("smile", "soft", "flat", "frown", "small", "smirk"):
            k = {"smile": 0.55, "soft": 0.30, "flat": 0.06, "frown": -0.30, "small": 0.20, "smirk": 0.0}[kind]
            if kind == "small":
                L, R = (cx - wd * 0.6, cy), (cx + wd * 0.6, cy)
            if lipcol:
                up = bez(L, (cx - wd * 0.5, cy + wd * 0.18 - k * wd * 0.15), (cx + wd * 0.5, cy + wd * 0.18 - k * wd * 0.15), R)
                lo = bez(R, (cx + wd * 0.45, cy - wd * 0.42 - k * wd * 0.3), (cx - wd * 0.45, cy - wd * 0.42 - k * wd * 0.3), L)
                lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
                dl.polygon([P(*p) for p in up + lo], fill=lipcol)
                lay = lay.filter(ImageFilter.GaussianBlur(N * 0.004))
                img.alpha_composite(lay); dr = ImageDraw.Draw(img)
            if kind == "smirk":
                pts = bez((cx - wd * 0.75, cy + wd * 0.02), (cx - wd * 0.2, cy - wd * 0.16), (cx + wd * 0.45, cy - wd * 0.12),
                          (cx + wd * 0.95, cy + wd * 0.32))
                tick = bez((cx + wd * 0.90, cy + wd * 0.48), (cx + wd * 1.02, cy + wd * 0.38), (cx + wd * 1.05, cy + wd * 0.22),
                           (cx + wd * 0.98, cy + wd * 0.10), 12)
                if side < 0:
                    pts = [(2 * cx - x, y) for x, y in pts]; tick = [(2 * cx - x, y) for x, y in tick]
                stroke(dr, pts, 0.014, 0.020, wmid=0.021)
                stroke(dr, tick, 0.008, 0.005, col=(90, 55, 45, 220))
                return
            pts = bez(L, (cx - wd * 0.45, cy - wd * k), (cx + wd * 0.45, cy - wd * k), R)
            stroke(dr, pts, 0.014, 0.014, wmid=0.021)
            if kind in ("smile", "soft"):
                for e in (L, R):             # dimple-like corner ticks
                    d = 1 if e is R else -1
                    stroke(dr, [(e[0] - d * 0.006, e[1] - 0.002), (e[0] + d * 0.010, e[1] + 0.012)], 0.010, 0.006)
            return
        # open shapes: upper edge at cy (+ a little), lower edge dropped by jaw
        if kind == "open":
            up = bez(L, (cx - wd * 0.5, cy + wd * 0.10), (cx + wd * 0.5, cy + wd * 0.10), R)
            lo = bez(R, (cx + wd * 0.65, cy - wd * (0.75 + jaw)), (cx - wd * 0.65, cy - wd * (0.75 + jaw)), L)
        elif kind == "grin":
            up = bez(L, (cx - wd * 0.5, cy - wd * 0.12), (cx + wd * 0.5, cy - wd * 0.12), R)
            lo = bez(R, (cx + wd * 0.75, cy - wd * (1.05 + jaw)), (cx - wd * 0.75, cy - wd * (1.05 + jaw)), L)
            L = (L[0], L[1]); R = (R[0], R[1])
        elif kind == "o":
            r = wd * 0.55; h = wd * (0.85 + jaw)
            up = bez((cx - r, cy - h * 0.45), (cx - r, cy + h * 0.25), (cx + r, cy + h * 0.25), (cx + r, cy - h * 0.45))
            lo = bez((cx + r, cy - h * 0.45), (cx + r, cy - h * 1.1), (cx - r, cy - h * 1.1), (cx - r, cy - h * 0.45))
        elif kind == "shout":
            L, R = (cx - wd, cy - wd * 0.30), (cx + wd, cy - wd * 0.30)
            up = bez(L, (cx - wd * 0.55, cy + wd * 0.22), (cx + wd * 0.55, cy + wd * 0.22), R)
            lo = bez(R, (cx + wd * 0.75, cy - wd * (0.95 + jaw)), (cx - wd * 0.75, cy - wd * (0.95 + jaw)), L)
        elif kind == "wobbly":
            up = [(cx - wd + 2 * wd * i / 30, cy + 0.010 * math.sin(i / 30 * 3 * math.pi)) for i in range(31)]
            lo = [(cx + wd - 2 * wd * i / 30, cy - wd * (0.42 + jaw) * math.sin(math.pi * i / 30) ** 0.7
                   + 0.008 * math.sin(i / 30 * 4 * math.pi)) for i in range(31)]
        shape = [P(*p) for p in up + lo]
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.polygon(shape, fill=(110, 34, 44, 255))
        m = Image.new("L", img.size, 0); ImageDraw.Draw(m).polygon(shape, fill=255)
        inner = Image.new("RGBA", img.size, (0, 0, 0, 0)); di = ImageDraw.Draw(inner)
        ys = [p[1] for p in up + lo]; top, botm = max(ys), min(ys)
        if kind in ("open", "grin", "shout", "wobbly"):       # top teeth band
            tb = top - (top - botm) * (0.30 if kind != "wobbly" else 0.45)
            di.rectangle((P(cx - wd * 1.2, top + 0.02)[0], P(0, top + 0.02)[1], P(cx + wd * 1.2, tb)[0], P(0, tb)[1]),
                         fill=(255, 255, 252, 255))
            if kind in ("wobbly", "shout"):
                bb = botm + (top - botm) * 0.40
                di.rectangle((P(cx - wd * 1.2, bb)[0], P(0, bb)[1], P(cx + wd * 1.2, botm - 0.02)[0], P(0, botm - 0.02)[1]),
                             fill=(255, 255, 252, 255))
        if kind in ("open", "grin", "o", "shout"):           # tongue
            tr = wd * 0.55
            di.ellipse((P(cx - tr, botm + (top - botm) * 0.42)[0], P(0, botm + (top - botm) * 0.42)[1],
                        P(cx + tr, botm - (top - botm) * 0.2)[0], P(0, botm - (top - botm) * 0.2)[1]), fill=(222, 104, 112, 255))
        lay.paste(inner, (0, 0), Image.composite(inner.split()[3], Image.new("L", img.size, 0), m))
        img.alpha_composite(lay)
        dr = ImageDraw.Draw(img)
        pts = up + lo + [up[0]]
        stroke(dr, pts, 0.013, 0.013, col=(52, 26, 24, 255))
        if lipcol:   # soft lower lip tint
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            lo2 = [(x, y - 0.012) for x, y in lo]
            stroke(dl, lo2[4:-4], 0.020, 0.020, col=lipcol)
            lay = lay.filter(ImageFilter.GaussianBlur(N * 0.003)); img.alpha_composite(lay)

    def blush(img, cx, cy, rx, ry, a):
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        for sx in (-1, 1):
            x = 0.5 + sx * cx
            dl.ellipse((P(x - rx, cy + ry)[0], P(x - rx, cy + ry)[1], P(x + rx, cy - ry)[0], P(x + rx, cy - ry)[1]),
                       fill=(232, 120, 120, a))
        lay = lay.filter(ImageFilter.GaussianBlur(N * 0.022)); img.alpha_composite(lay)

    def lines(img, pts_list, w=0.010, col=(120, 70, 55, 200)):
        dr = ImageDraw.Draw(img)
        for pts in pts_list:
            stroke(dr, pts, w, w * 0.4, col=col)

    def drop(img, x, y, s):
        dr = ImageDraw.Draw(img)
        pts = [(x, y + s * 1.2)] + [(x + s * 0.6 * math.sin(a), y - s * 0.5 * math.cos(a) * 0 - s * 0.6 + s * 0.6 * -math.cos(a) * 0)
                                     for a in []]
        poly(dr, [(x, y + s * 1.3), (x + s * 0.55, y), (x + s * 0.4, y - s * 0.45), (x, y - s * 0.6),
                  (x - s * 0.4, y - s * 0.45), (x - s * 0.55, y)], (150, 205, 245, 235))
        stroke(dr, [(x, y + s * 1.3), (x + s * 0.55, y), (x + s * 0.4, y - s * 0.45), (x, y - s * 0.6),
                    (x - s * 0.4, y - s * 0.45), (x - s * 0.55, y), (x, y + s * 1.3)], 0.006, 0.006, col=(60, 110, 160, 255))

    def soft(img, fn, blur=0.003):
        """Draw with fn(ImageDraw) on a separate layer, blur it a little and composite (soft shading lines)."""
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); fn(ImageDraw.Draw(lay))
        if blur:
            lay = lay.filter(ImageFilter.GaussianBlur(N * blur))
        img.alpha_composite(lay)

    def nose_hint(img, cy, w, col=(150, 82, 62, 150), strength=1.0):
        """A small soft 'u' under the nose tip, two nostril ticks and a faint shadow on one side of the bridge."""
        c = (col[0], col[1], col[2], int(col[3] * strength))
        soft(img, lambda d: stroke(d, bez((0.5 - w, cy + w * 0.35), (0.5 - w * 0.55, cy - w * 0.45),
                                            (0.5 + w * 0.55, cy - w * 0.45), (0.5 + w, cy + w * 0.35), 24),
                                   0.007, 0.007, col=c, wmid=0.011), 0.0025)
        for sx in (-1, 1):
            soft(img, lambda d, sx=sx: stroke(d, [(0.5 + sx * w * 0.95, cy + w * 0.10), (0.5 + sx * w * 0.55, cy - w * 0.12)],
                                              0.008, 0.004, col=(c[0] - 30, c[1] - 20, c[2] - 15, c[3])), 0.002)
        soft(img, lambda d: stroke(d, [(0.5 + w * 0.55, cy + w * 3.2), (0.5 + w * 0.62, cy + w * 1.2)], 0.010, 0.006,
                                   col=(c[0], c[1], c[2], c[3] // 3)), 0.006)

    def crease(img, c, half, side, lift=1.55, col=(140, 90, 72, 120), lenf=0.85):
        cx, cy = c; ew, eh = half; o = side
        pts = bez((cx - o * ew * 0.55 * lenf, cy + eh * 1.05), (cx - o * ew * 0.2, cy + eh * lift),
                  (cx + o * ew * 0.45, cy + eh * lift * 0.98), (cx + o * ew * 0.95 * lenf, cy + eh * 0.95), 24)
        soft(img, lambda d: stroke(d, pts, 0.006, 0.004, col=col, wmid=0.008), 0.0015)

    def crows(img, c, half, side, n=3, col=(130, 80, 62, 150), ln=1.0):
        cx, cy = c; ew, eh = half; o = side
        def f(d):
            for k in range(n):
                a = math.radians((-25 + 25 * k) if n == 3 else (-15 + 30 * k))
                x0 = cx + o * ew * 1.22; y0 = cy + eh * 0.15
                stroke(d, [(x0, y0 + eh * 0.5 * math.sin(a)),
                           (x0 + o * ew * 0.38 * ln * math.cos(a), y0 + eh * 1.1 * ln * math.sin(a) + eh * 0.1)],
                       0.006, 0.003, col=col)
        soft(img, f, 0.0015)

    def under_eye(img, c, half, side, col=(150, 100, 90, 110), drop=1.35):
        cx, cy = c; ew, eh = half; o = side
        pts = bez((cx - o * ew * 0.55, cy - eh * drop * 0.95), (cx - o * ew * 0.1, cy - eh * drop * 1.2),
                  (cx + o * ew * 0.45, cy - eh * drop * 1.1), (cx + o * ew * 0.85, cy - eh * drop * 0.7), 20)
        soft(img, lambda d: stroke(d, pts, 0.004, 0.003, col=col, wmid=0.007), 0.002)

    def cheek_lines(img, y0, y1, x0, x1, col=(140, 82, 64, 110)):
        """Soft smile folds from beside the nostrils (y0, x0) curving out and down past the mouth corners (y1, x1)."""
        def f(d):
            for sx in (-1, 1):
                stroke(d, bez((0.5 + sx * x0, y0), (0.5 + sx * (x0 + (x1 - x0) * 0.9), y0 - (y0 - y1) * 0.25),
                              (0.5 + sx * x1 * 1.04, y0 - (y0 - y1) * 0.7), (0.5 + sx * x1, y1), 16),
                       0.005, 0.003, col=col, wmid=0.008)
        soft(img, f, 0.002)

    def rim_mouth(img, kind, cx, cy, wd, jaw, col):
        """Light lip rim behind an open mouth (reads on a dark beard, LESSONS L42)."""
        t = Image.new("RGBA", img.size, (0, 0, 0, 0))
        mouth(t, kind, cx, cy, wd, lipcol=None, jaw=jaw)
        a = t.split()[3].filter(ImageFilter.MaxFilter(int(N * 0.018) | 1)).filter(ImageFilter.GaussianBlur(N * 0.003))
        lay = Image.new("RGBA", img.size, col); lay.putalpha(a.point(lambda v: v * col[3] // 255))
        img.alpha_composite(lay)

    # ------------------------------------------------------------------ Jonah pack extras
    def swatches(img, ch):
        """Fixed colours for parts whose UV1 points here (SWATCHES); the mouth strip is a gradient throat -> lips."""
        dr = ImageDraw.Draw(img)
        for nm, (x0, y0, x1, y1) in SWATCHES.get(ch, {}).items():
            col = SWATCH_COL[nm]
            if isinstance(col[0], tuple):
                n = 32
                for k in range(n):
                    t = k / (n - 1); c = tuple(int(lerp_(a, b, t)) for a, b in zip(col[0], col[1]))
                    xa = x0 + (x1 - x0) * k / n; xb = x0 + (x1 - x0) * (k + 1) / n
                    dr.rectangle((P(xa, y1)[0], P(xa, y1)[1], P(xb, y0)[0] + 1, P(xb, y0)[1]), fill=c + (255,))
            else:
                dr.rectangle((P(x0, y1)[0], P(x0, y1)[1], P(x1, y0)[0], P(x1, y0)[1]), fill=col + (255,))

    def lerp_(a, b, t):
        return a + (b - a) * t

    def tears(img, c, half, side, n=2, s=0.016):
        cx, cy = c; ew, eh = half
        dr = ImageDraw.Draw(img)
        x = cx + side * ew * 0.55
        stroke(dr, [(x, cy - eh * 0.9), (x + side * 0.004, cy - eh * 2.2), (x + side * 0.002, cy - eh * 3.4)], 0.016, 0.010,
               col=(150, 205, 245, 210))
        for k in range(n):
            drop(img, x + side * (0.006 + 0.012 * k), cy - eh * (2.6 + 1.5 * k), s * (1 - 0.2 * k))

    def nose_wrinkles(img, cy, w):
        def f(d):
            for k, dy in enumerate((0.030, 0.050, 0.068)):
                ww = w * (0.85 - 0.12 * k)
                stroke(d, bez((0.5 - ww, cy + dy - 0.006), (0.5 - ww * 0.3, cy + dy + 0.006), (0.5 + ww * 0.3, cy + dy + 0.006),
                              (0.5 + ww, cy + dy - 0.006), 16), 0.007, 0.004, col=(120, 66, 50, 190), wmid=0.009)
        soft(img, f, 0.0015)

    def pout(img, cx, cy, wd, lipcol):
        dr = ImageDraw.Draw(img)
        pts = bez((cx - wd * 0.55, cy - wd * 0.02), (cx - wd * 0.2, cy + wd * 0.12), (cx + wd * 0.2, cy + wd * 0.12),
                  (cx + wd * 0.55, cy - wd * 0.02))
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        lo = bez((cx + wd * 0.5, cy - wd * 0.04), (cx + wd * 0.35, cy - wd * 0.42), (cx - wd * 0.35, cy - wd * 0.42),
                 (cx - wd * 0.5, cy - wd * 0.04))
        dl.polygon([P(*p) for p in pts + lo], fill=lipcol)
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(N * 0.002)))
        dr = ImageDraw.Draw(img)
        stroke(dr, pts, 0.014, 0.014, wmid=0.019)
        stroke(dr, lo[2:-2], 0.008, 0.008, col=(90, 50, 44, 230))

    def grimace(img, cx, cy, wd, lipcol):
        """Yuck: mouth pulled down and to one side, teeth clenched."""
        dr = ImageDraw.Draw(img)
        up = bez((cx - wd, cy - wd * 0.18), (cx - wd * 0.4, cy + wd * 0.10), (cx + wd * 0.4, cy + wd * 0.02), (cx + wd, cy - wd * 0.30))
        lo = bez((cx + wd, cy - wd * 0.30), (cx + wd * 0.4, cy - wd * 0.52), (cx - wd * 0.4, cy - wd * 0.46), (cx - wd, cy - wd * 0.18))
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        dl.polygon([P(*p) for p in up + lo], fill=(255, 253, 248, 255))
        img.alpha_composite(lay)
        dr = ImageDraw.Draw(img)
        mid = [((a[0] + b[0]) / 2, (a[1] + b[1]) / 2) for a, b in zip(up, reversed(lo))]
        stroke(dr, mid, 0.006, 0.006, col=(120, 90, 80, 220))
        for f in (0.25, 0.5, 0.75):
            i = int(f * (len(up) - 1)); a = up[i]; b = list(reversed(lo))[i]
            stroke(dr, [a, b], 0.005, 0.005, col=(120, 90, 80, 200))
        stroke(dr, up + lo + [up[0]], 0.012, 0.012, col=(52, 26, 24, 255))

    def sweat(img, x, y, s):
        drop(img, x, y, s)


    def face_params(ch, ex):
        """Per character base look + per expression changes (eye / brow / mouth parameters as Jonah's faces)."""
        E = dict(look=(0, 0), top=1.0, bot=1.0, tilt=0.15, lash=0, mode="open", lid=0.10, inner_up=0.0,
                 pupil=0.55, wet=False)
        Bp = dict(raise_=0.0, inner=0.0, arch=0.35, thick=1.0, outer=0.0, length=0.86)
        Bl, Br = {}, {}
        M = dict(kind="flat", wd=0.095, jaw=0.0, side=0.0)
        o = dict(lipcol=None, rim=None, bl=0, crow=0, crs=True, special=[])
        if ch == "jesus":
            E.update(lid=0.12, top=0.95, bot=0.90, tilt=0.0, pupil=0.52)
            M["wd"] = 0.084; o.update(lipcol=(178, 100, 86, 220), rim=(214, 160, 138, 235), bl=60, crow=1)
            Bp.update(raise_=0.060, arch=0.30)
            if ex == "kind":
                E.update(top=0.82, look=(0.0, -0.05)); Bp.update(inner=0.012, arch=0.30); M.update(kind="soft", wd=0.078)
                o["crow"] = 2
            elif ex == "talk":
                E.update(top=0.88); M.update(kind="open", wd=0.076, jaw=0.08)
            elif ex == "smile":
                E.update(top=0.76, bot=0.80); M.update(kind="grin", wd=0.088, jaw=0.06); o.update(crow=3, bl=90)
            elif ex == "laugh":
                E.update(mode="happy"); Bp.update(raise_=0.080, arch=0.50); M.update(kind="grin", wd=0.096, jaw=0.16)
                o.update(crow=3, bl=110)
            elif ex == "sleep":
                E.update(mode="closed"); Bp.update(inner=0.008, raise_=0.056, arch=0.22); M.update(kind="soft", wd=0.058)
                o.update(crs=False, bl=40, crow=0)
            elif ex == "firm":
                E.update(top=0.92, tilt=0.05); Bp.update(inner=-0.012, raise_=0.052, arch=0.08)
                M.update(kind="flat", wd=0.070); o.update(crow=0, bl=30)
            elif ex == "gentle":
                E.update(top=0.72, bot=0.80, look=(0.1, -0.15)); Bp.update(inner=0.024, raise_=0.066, arch=0.26)
                M.update(kind="soft", wd=0.070); o.update(crow=2, bl=60)
            elif ex == "look_up":
                E.update(top=1.08, look=(0.0, 0.95), pupil=0.50); Bp.update(raise_=0.080, arch=0.42)
                M.update(kind="smile", wd=0.070); o.update(bl=70)
        elif ch == "peter":
            E.update(lid=0.14, top=0.92, bot=0.84, tilt=0.08, pupil=0.54)
            M["wd"] = 0.096; o.update(lipcol=(176, 90, 78, 230), rim=(218, 150, 128, 235), bl=120, crow=2)
            Bp.update(raise_=0.064, arch=0.32, thick=1.18)
            if ex == "jolly":
                E.update(top=0.74, bot=0.62, look=(0.05, 0.0)); Bp.update(raise_=0.070, arch=0.42)
                M.update(kind="grin", wd=0.108, jaw=0.14); o["bl"] = 150
            elif ex == "talk":
                M.update(kind="open", wd=0.088, jaw=0.10); Bp.update(raise_=0.070, arch=0.40)
            elif ex == "shock":
                E.update(top=1.40, bot=1.20, pupil=0.30, lid=0.05, tilt=0.0); Bp.update(raise_=0.135, arch=0.72, outer=0.02)
                M.update(kind="shout", wd=0.100, jaw=0.55); o.update(crow=0, bl=90)
            elif ex == "wail":
                E.update(mode="closed"); Bp.update(inner=0.070, raise_=0.090, arch=0.02, outer=-0.040)
                M.update(kind="shout", wd=0.096, jaw=0.45); o.update(special=["tears"], bl=140, crs=False)
            elif ex == "laugh":
                E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.112, jaw=0.26)
                o.update(bl=170, crow=3)
            elif ex == "scared":
                E.update(top=1.18, pupil=0.40, look=(0.35, 0.0), tilt=-0.06)
                Bp.update(inner=0.060, raise_=0.090, arch=0.04, outer=-0.030); M.update(kind="wobbly", wd=0.084, jaw=0.10)
                o.update(special=["sweat"], bl=50, crow=1)
            elif ex == "amazed":
                E.update(top=1.30, bot=1.10, pupil=0.36, lid=0.06, tilt=0.0); Bp.update(raise_=0.120, arch=0.66)
                M.update(kind="o", wd=0.072, jaw=0.34); o.update(crow=0, bl=120)
            elif ex == "squint":
                E.update(top=0.26, bot=0.50, look=(0.0, -0.1), tilt=0.10); Bp.update(inner=-0.040, raise_=0.046, arch=0.06)
                o.update(special=["grimace", "wrinkles", "drops"], bl=110)
        elif ch == "man":
            E.update(lid=0.10, top=1.0, bot=0.95, tilt=0.0, pupil=0.56, lash=1)
            M["wd"] = 0.080; o.update(lipcol=(182, 108, 96, 220), rim=(222, 172, 150, 235), bl=70, crow=0)
            Bp.update(raise_=0.066, arch=0.30, thick=0.92)
            if ex == "shy":
                E.update(top=0.86, look=(0.45, -0.45)); Bp.update(inner=0.032, raise_=0.070, arch=0.20, outer=-0.010)
                M.update(kind="small", wd=0.062); o["bl"] = 120
            elif ex == "talk":
                E.update(top=0.96); M.update(kind="open", wd=0.072, jaw=0.07)
            elif ex == "nervous":
                E.update(top=1.06, look=(-0.40, -0.10)); Bp.update(inner=0.052, raise_=0.080, arch=0.06, outer=-0.020)
                M.update(kind="wobbly", wd=0.066, jaw=0.03); o.update(special=["sweat"], bl=50)
            elif ex == "hope":
                E.update(top=1.10, look=(0.0, 0.92), pupil=0.52); Bp.update(inner=0.040, raise_=0.090, arch=0.30)
                M.update(kind="soft", wd=0.064); o["bl"] = 80
            elif ex == "wonder":
                E.update(top=1.36, bot=1.12, pupil=0.36, lid=0.06); Bp.update(raise_=0.120, arch=0.62)
                M.update(kind="o", wd=0.060, jaw=0.28); o["bl"] = 90
            elif ex == "joy":
                E.update(top=0.90, look=(0.0, 0.10)); Bp.update(raise_=0.090, arch=0.52)
                M.update(kind="grin", wd=0.100, jaw=0.14); o.update(bl=140, crow=2)
            elif ex == "laugh":
                E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.100, jaw=0.24)
                o.update(bl=150, crow=2)
        else:                                                    # the friends (one shared drawing per expression)
            E.update(lid=0.12, top=0.95, bot=0.90, tilt=0.06, pupil=0.55)
            M["wd"] = 0.090; o.update(lipcol=(176, 96, 84, 220), rim=(216, 160, 136, 235), bl=90, crow=1)
            Bp.update(raise_=0.064, arch=0.34, thick=1.05)
            if ex == "happy":
                E.update(top=0.84); Bp.update(arch=0.40); M.update(kind="smile", wd=0.086)
            elif ex == "talk":
                M.update(kind="open", wd=0.076, jaw=0.08)
            elif ex == "strain":
                E.update(top=0.30, bot=0.55, tilt=0.10); Bp.update(inner=-0.042, raise_=0.048, arch=0.05)
                o.update(special=["grimace", "sweat"], bl=170)
            elif ex == "oof":
                E.update(mode="closed"); Bp.update(inner=0.050, raise_=0.090, arch=0.04, outer=-0.030)
                M.update(kind="o", wd=0.062, jaw=0.22); o.update(bl=130, crs=False)
            elif ex == "think":
                E.update(top=0.80, look=(0.60, 0.60)); Bl = dict(inner=-0.020, raise_=0.052, arch=0.10)
                Br = dict(raise_=0.090, arch=0.45); M.update(kind="smirk", wd=0.062, side=1.0)
            elif ex == "idea":
                E.update(top=1.30, bot=1.10, pupil=0.40, lid=0.06); Bp.update(raise_=0.120, arch=0.62)
                M.update(kind="grin", wd=0.096, jaw=0.12); o.update(bl=120, crow=2)
            elif ex == "cheer":
                E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.55); M.update(kind="grin", wd=0.104, jaw=0.28)
                o.update(bl=150, crow=2)
        return E, Bp, Bl, Br, M, o

    made = {}
    LOOK = {"jesus": dict(bcol=(56, 36, 24, 255), iris=(110, 70, 40), bw=0.054, nose=0.040, blush=0.30),
            "peter": dict(bcol=(30, 22, 18, 255), iris=(100, 66, 40), bw=0.064, nose=0.044, blush=0.31),
            "man": dict(bcol=(104, 72, 46, 255), iris=(118, 98, 58), bw=0.046, nose=0.036, blush=0.30),
            "friend": dict(bcol=(44, 30, 22, 255), iris=(92, 62, 40), bw=0.056, nose=0.040, blush=0.31)}
    for ch in ("jesus", "peter", "man", "friend1"):
        key = "friend" if ch in FRIENDS else ch
        F = face_layout(ch)
        eL, eR, half, by, my, ny_ = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"], F["nose"]
        lk = LOOK[key]
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            E, Bp, Bl, Br, M, o = face_params(key, ex)
            special = o["special"]
            if E["mode"] == "open":                       # big, warm eyes (Jonah polish 2026-11-15)
                E["top"] = min(1.45, E["top"] * 1.08)
            lift = 0.045                                  # brows clear of the parked eyelid strip
            Bp["raise_"] = Bp["raise_"] + lift
            for d_ in (Bl, Br):
                if "raise_" in d_:
                    d_["raise_"] += lift
            if o["bl"]:
                blush(img, lk["blush"], ny_ - 0.035, 0.090, 0.048, o["bl"])
            nose_hint(img, ny_ + 0.006, lk["nose"], strength=1.15)
            for side, c in ((1, eL), (-1, eR)):
                eye(img, c, half, side=side, iris=lk["iris"], line=0.021, **E)
                if o["crs"] and E["mode"] == "open":
                    crease(img, c, half, side, lift=1.55, col=(140, 90, 72, 120))
                if o["crow"]:
                    crows(img, c, half, side, n=o["crow"], ln=1.0 if E["mode"] == "open" else 1.2, col=(130, 80, 62, 130))
                if "tears" in special:
                    tears(img, c, half, side)
            if "wrinkles" in special:
                nose_wrinkles(img, ny_, 0.036)
            if "sweat" in special:
                sweat(img, eL[0] + half[0] * 2.4, eL[1] + half[1] * 1.6, 0.030)
            if "drops" in special:                        # rain on his face (squint)
                for x_, y_ in ((0.22, 0.86), (0.80, 0.80), (0.70, 0.20)):
                    drop(img, x_, y_, 0.020)
            dr = ImageDraw.Draw(img)
            for side, c in ((1, eL), (-1, eR)):
                b = dict(Bp); b.update(Bl if side == 1 else Br)
                brow(dr, side, (c[0], by - 0.015), half, w=lk["bw"], col=lk["bcol"], **b)
            wd = M["wd"] * (1.45 if M["kind"] in ("open", "grin", "o", "shout", "wobbly") else 1.30)
            lipcol, rim = o["lipcol"], o["rim"]
            if "grimace" in special:
                soft(img, lambda d: d.ellipse((P(0.5 - wd * 1.3, my + wd * 0.4)[0], P(0.5 - wd * 1.3, my + wd * 0.4)[1],
                                               P(0.5 + wd * 1.3, my - wd * 0.9)[0], P(0.5 + wd * 1.3, my - wd * 0.9)[1]),
                                              fill=rim), 0.004)
                grimace(img, 0.5, my, wd * 0.95, lipcol)
            else:
                if rim and M["kind"] in ("open", "grin", "o", "shout", "wobbly"):
                    rim_mouth(img, M["kind"], 0.5, my - 0.012, wd, M["jaw"] * 1.25, rim)
                elif rim:
                    rx, ry = M["wd"] * 1.45, M["wd"] * 0.50
                    soft(img, lambda d: d.ellipse((P(0.5 - rx, my + ry * 0.7)[0], P(0.5 - rx, my + ry * 0.7)[1],
                                                   P(0.5 + rx, my - ry * 1.3)[0], P(0.5 + rx, my - ry * 1.3)[1]),
                                                  fill=rim), 0.004)
                mouth(img, M["kind"], 0.5, my - (0.012 if M["kind"] in ("open", "grin", "o", "shout") else 0.0), wd,
                      lipcol=lipcol, jaw=M["jaw"] * 1.25, side=M["side"])
            if ch in SWATCHES:
                swatches(img, ch)
            out = img.resize((PX, PX), Image.LANCZOS)
            path = face_file(ch, ex)
            out.save(path); made[f"{key}_{ex}"] = os.path.relpath(path, ROOT)
    # overview sheet: every expression over its base colour, plus a 64 px "phone distance" row (LESSONS L42)
    cells = [(ch, ex) for ch in ("jesus", "peter", "man", "friend1") for ex in EXPRESSIONS[ch]]
    cols = 8; cw = 256
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (cw + 24 + 88)), (250, 246, 238))
    dr = ImageDraw.Draw(sheet)
    for i, (ch, ex) in enumerate(cells):
        x, y = (i % cols) * cw, (i // cols) * (cw + 24 + 88)
        base = PALETTE[ch]["skin"]
        bg = Image.new("RGBA", (cw, cw), tuple(int(base[k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        fc = Image.open(face_file(ch, ex)).resize((cw, cw), Image.LANCZOS)
        bg.alpha_composite(fc); sheet.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 8, y + cw + 4), f"{'friend' if ch in FRIENDS else ch}_{ex}", fill=(40, 30, 20))
        small = bg.resize((64, 64), Image.LANCZOS)
        sheet.paste(small.convert("RGB"), (x + 8, y + cw + 22))
    sheet.save(os.path.join(FACES, "overview.png"))
    print("faces:", len(made), "->", FACES)
    return made


def swatch_uv(ch, nm, f=0.5):
    x0, y0, x1, y1 = SWATCHES[ch][nm]
    return (lerp_(x0, x1, f), (y0 + y1) / 2)


def lerp_(a, b, t):
    return a + (b - a) * t


def in_swatch(ch, du, dv, margin=0.02):
    for x0, y0, x1, y1 in SWATCHES.get(ch, {}).values():
        if x0 - margin <= du <= x1 + margin and y0 - margin <= dv <= y1 + margin:
            return True
    return False


def compose():
    """Contact sheets model/preview_<char>.png, preview_friends.png, preview_all.png, preview_uvcheck.png,
    preview_pose.png from $MI_WORK."""
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
    views = [("front", "front"), ("q34", "3/4"), ("side", "side"), ("back", "back")]
    for ch in CHARS:
        top = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in views], [lb for _, lb in views], 4,
                   (480, 720), f"{ch}: rest pose, demo palette + default face decal")
        det = [("head", "face 3/4"), ("headfront", "face front"), ("handL", "left hand"), ("handR", "right hand"),
               ("props", "props shown")]
        if ch == "man":
            det += [("mat", "the mat in the rest pose (flat on the page)"), ("matsheet", "the mat as printed")]
        bot = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det], [lb for _, lb in det], 5, (384, 384),
                   "close-ups")
        ex = grid([os.path.join(WORK, f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]], EXPRESSIONS[ch], 6,
                  (320, 320), "face decals on the model (UV1)")
        stack([top, bot, ex]).save(os.path.join(MODEL, f"preview_{ch}.png"))
    fv = [os.path.join(WORK, f"pv_{f}_{v}.png") for f in FRIENDS for v, _ in views]
    if any(os.path.exists(f) for f in fv):
        top = grid(fv, [f"{f} {lb}" for f in FRIENDS for _, lb in views], 4, (420, 630),
                   "friends (not on the sheet): fixed paint model/friend_paint.png on UV0 + shared face decals friend_*")
        grp = grid([os.path.join(WORK, f"pv_friends_{v}.png") for v in ("line", "lineq")], ["line-up, front", "3/4"],
                   2, (960, 600), "silhouettes side by side")
        ex = grid([os.path.join(WORK, f"pv_friend1_expr_{e}.png") for e in FRIEND_EXPRESSIONS] +
                  [os.path.join(WORK, f"pv_friend{i}_expr_happy.png") for i in (2, 3, 4)],
                  FRIEND_EXPRESSIONS + ["friend2 happy", "friend3 happy", "friend4 happy"], 5, (320, 320),
                  "shared face decals (friend1), default on the others")
        stack([top, grp, ex]).save(os.path.join(MODEL, "preview_friends.png"))
    al = [os.path.join(WORK, f) for f in ("pv_all.png", "pv_all_phone.png")]
    if all(os.path.exists(f) for f in al):
        stack([grid([al[0]], ["the cast at their sheet slots (mat flat, as in the rest pose)"], 1, (1600, 1000), "cast"),
               grid([al[1]], ["phone-like high angle"], 1, (1600, 1000), "")]).save(os.path.join(MODEL, "preview_all.png"))
    uv = [os.path.join(WORK, f) for f in ("uvproof.png", "uv_front.png", "uv_q34.png", "uv_back.png")]
    if all(os.path.exists(f) for f in uv):
        a = Image.open(uv[0]).convert("RGB")
        b = Image.open(uv[1]).convert("RGBA")
        w = Image.new("RGBA", b.size, (255, 255, 255, 255)); w.alpha_composite(b); b = w.convert("RGB")
        crop = (0, 0, 1000, a.height)
        r1 = Image.new("RGB", (2000, a.height), bg); r1.paste(a.crop(crop), (0, 0)); r1.paste(b.crop(crop).resize((1000, a.height)), (1000, 0))
        r2 = Image.new("RGB", (2000, 562), bg)
        r2.paste(Image.open(uv[2]).convert("RGB").resize((1000, 562)), (0, 0))
        r2.paste(Image.open(uv[3]).convert("RGB").resize((1000, 562)), (1000, 0))
        r3 = Image.new("RGB", (2000, 562), bg)
        for i, f in enumerate(os.path.join(WORK, f"uv_{n}.png") for n in ("mat", "matq")):
            if os.path.exists(f):
                r3.paste(Image.open(f).convert("RGB").resize((1000, 562)), (1000 * i, 0))
        hd = Image.new("RGB", (2000, 30), bg)
        ImageDraw.Draw(hd).text((10, 8), "UV0 proof: left = a perfectly coloured sheet (ID render in demo colours), right = "
                                "the models wearing it, front ortho with the mat stood up as printed = must equal the "
                                "sheet; then 3/4 + back; then the mat lying flat (rest pose) from above and 3/4",
                                fill=(40, 30, 20))
        stack([hd, r1, r2, r3]).save(os.path.join(MODEL, "preview_uvcheck.png"))
    pf = [(os.path.join(WORK, f"pose_{ch}_{v}.png"), f"{ch} {v}") for ch in CHARS + FRIENDS for v in ("a", "b", "closed")]
    pf += [(os.path.join(WORK, f"pose_man_{v}.png"), f"man {v}") for v in ("lie", "lieq", "liephone", "carried")]
    pf = [p for p in pf if os.path.exists(p[0])]
    if pf:
        grid([p[0] for p in pf], [p[1] for p in pf], 6, (320, 400),
             "pose test: a/b = elbows, fingers, thigh + knee, spine, head turn, jaw open, half / full blink, cloth bones; "
             "closed = eyes shut close-up; man lie = lying on his back on the mat (lie_mat), carried = mat lifted").save(
            os.path.join(MODEL, "preview_pose.png"))
    print("composed previews ->", MODEL)


if not IN_BLENDER:
    if __name__ == "__main__":
        mode = sys.argv[1] if len(sys.argv) > 1 else "faces"

        def blender_bin():
            b = os.environ.get("BLENDER") or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
            return b

        def run_all():
            import subprocess
            me = os.path.abspath(__file__)
            draw_faces()
            subprocess.run([blender_bin(), "-b", "--factory-startup", "--python", me, "--", "build"], check=True,
                           stdout=subprocess.DEVNULL)
            proof()
            for m in ("preview", "uvcheck", "posetest", "verify"):
                subprocess.run([blender_bin(), "-b", "--factory-startup", "--python", me, "--", m], check=True,
                               stdout=subprocess.DEVNULL)
            compose()
            v = json.load(open(os.path.join(WORK, "verify.json")))
            for ch, i in v.items():
                print(ch, "bonesMatch", i["bonesMatch"], "parentsOK", i.get("parentsOK"), "actions", i["actions"],
                      "tris", i["tris"], "budget", i["budget"], "uvOrderOK", i.get("uvOrderOK"),
                      "maxInf", i.get("maxInfluences"), "height", i["heightTop"], "err%", i["heightErrPct"],
                      "minY", i["minY"])
        {"faces": draw_faces, "compose": compose, "proof": proof, "all": run_all}[mode]()
    raise SystemExit(0)

# =============================================================================================== Blender part
sys.path.insert(0, HERE)
from story_mesh import *                                  # noqa: E402,F401,F403
import bmesh                                               # noqa: E402
from mathutils import Vector, Matrix                       # noqa: E402
from mathutils.bvhtree import BVHTree                      # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
ONLY = [c for c in os.environ.get("MI_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()


# =============================================================================================== context
class Ctx:
    def __init__(self, ch):
        self.ch = ch; self.F = face_layout(ch)
        self.s = SPEC[ch]; self.L = landmarks(ch)
        self.H = self.L["top"] - self.L["chin"]; self.S = self.s.get("S", self.s["height"] / 0.30)
        self.blend = 0.006 * self.S
        self.parts = []; self.B = {}; self.hand = {}

    def w(self, spec, blend=None):
        spec = [(s, None) if isinstance(s, str) else s for s in spec]
        B, bl = self.B, blend or self.blend
        return lambda p: weigh(p, spec, B, bl)

    def add(self, name, cg, **kw):
        self.parts.append(dict(name=name, cage=cg, **kw))


ARM12 = [math.radians(75 - 30 * k) for k in range(12)]


# =============================================================================================== legs / shoes
# lower rows of the D&G leg (y, x centre, out, in, front, back, z centre), David scale; scaled by footScale * S.
LEG_ROWS = [
    (0.062, 0.0189, 0.0094, 0.0086, 0.0056, 0.0094, 0.0006),
    (0.050, 0.0188, 0.0086, 0.0074, 0.0053, 0.0082, 0.0000),
    (0.038, 0.0184, 0.0068, 0.0058, 0.0050, 0.0062, -0.0004),
    (0.028, 0.0182, 0.0055, 0.0050, 0.0046, 0.0052, -0.0006),
    (0.020, 0.0181, 0.0058, 0.0055, 0.0050, 0.0052, -0.0006),
    (0.0145, 0.0180, 0.0058, 0.0055, 0.0112, 0.0068, 0.0020),
    (0.0100, 0.0180, 0.0068, 0.0064, 0.0172, 0.0082, 0.0045),
    (0.0062, 0.0180, 0.0080, 0.0076, 0.0218, 0.0090, 0.0072),
    (0.0036, 0.0180, 0.0088, 0.0084, 0.0234, 0.0092, 0.0118),
    (0.0014, 0.0180, 0.0086, 0.0082, 0.0229, 0.0088, 0.0128)]
FOOTPRINT = [(-0.012, 0.74), (-0.004, 0.80), (0.006, 0.92), (0.018, 1.05), (0.026, 1.08), (0.034, 0.95), (0.040, 0.72)]


def build_leg(C, side, shoe_top, reg_shoe, pointy=0.0, top_y=0.050, regfn2=None):
    s = C.s; sd = 1 if side == "L" else -1
    k = s["footScale"]; Sy = C.S * 0.95
    xc = C.B["thigh" + side][1].x * sd
    rows = []
    for y, x0, out, inn, fr, bk, zc in LEG_ROWS:
        if y > top_y + 1e-6:
            continue
        rows.append((y * Sy, xc, out * k * C.S, inn * k * C.S, fr * k * C.S, bk * k * C.S, zc * k * C.S))
    rows = densify(rows, 2)
    N = 16; us = front_dense(N, 0.40)
    angs = [math.pi / 2 - 2 * math.pi * u for u in us]
    X, Y = V(1, 0, 0), V(0, 0, 1)
    cg = Cage(); wleg = C.w(["thigh" + side, "shin" + side, "foot" + side, "toe" + side])
    ank = C.B["foot" + side][0]; foot_top = 0.0160 * Sy * k
    toe_out = math.radians(6.0) * sd
    rings = []
    for y, xc_, out, inn, fr, bk, zc in rows:
        c = V(xc_ * sd, y, zc)
        ext = (out, inn, fr, bk) if sd > 0 else (inn, out, fr, bk)
        e = 2.2 if y > foot_top else 2.6
        pts = []
        for a in angs:
            p = section(c, X, Y, ext, a, e)
            if y < foot_top:
                tt = smoothstep(foot_top, foot_top * 0.5, y)
                q = rot_about(p - V(ank.x, 0, ank.z), V(0, 1, 0), toe_out * tt)
                p = q + V(ank.x, 0, ank.z)
                wprof = table(FOOTPRINT, (p.z - ank.z) / (k * C.S))[0]
                p.x = ank.x + (p.x - ank.x) * wprof
            pts.append(p)
        rings.append(cg.ring(pts, wleg))
    top = rows[0]
    cg.fan(rings[0], V(top[1] * sd, top[0] + 0.004, top[6]), wleg, "skin", 1)

    def regfn(q):
        yy = sum(cg.v[i].y for i in q) / 4
        if regfn2:
            return regfn2(yy, sum(cg.v[i].z for i in q) / 4 - ank.z)
        return reg_shoe if yy < shoe_top else "skin"
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, None, 0, regfn=regfn)
    cg.grid_cap(rings[-1], wleg, reg_shoe, 0)
    fl = s["footLen"]

    def post(pts, nrm):
        out = []
        for p in pts:
            q = p.copy()
            if q.y < 0.0010:
                q.y = 0.0004 if q.y < 0.0006 else q.y
            if pointy:
                zl = q.z - ank.z
                t = smoothstep(0.55 * fl, 1.0 * fl, zl)
                if t > 0:
                    q.y += pointy * t * t * 0.010 * C.S
                    q.z += pointy * t * t * 0.006 * C.S
                    q.x = ank.x + (q.x - ank.x) * (1 - 0.35 * t)
            out.append(q)
        return out
    C.add("leg" + side, cg, post=post, subdiv=0)


ESTHER_ROBE = [(0.2600, 0.0098, 0.0090, -0.0095), (0.2585, 0.0150, 0.0106, -0.0112), (0.2565, 0.0228, 0.0118, -0.0122),
               (0.2545, 0.0292, 0.0124, -0.0127), (0.2530, 0.0322, 0.0127, -0.0129), (0.2515, 0.0336, 0.0129, -0.0130),
               (0.2470, 0.0358, 0.0135, -0.0132), (0.2400, 0.0352, 0.0152, -0.0132), (0.2300, 0.0332, 0.0170, -0.0128),
               (0.2200, 0.0302, 0.0158, -0.0120), (0.2070, 0.0272, 0.0128, -0.0115), (0.1950, 0.0300, 0.0136, -0.0130),
               (0.1800, 0.0350, 0.0160, -0.0155), (0.1600, 0.0382, 0.0182, -0.0172), (0.1300, 0.0414, 0.0206, -0.0188),
               (0.0950, 0.0448, 0.0228, -0.0205), (0.0600, 0.0482, 0.0252, -0.0220), (0.0300, 0.0515, 0.0275, -0.0235),
               (0.0105, 0.0540, 0.0292, -0.0245)]
KING_ROBE = [(0.2760, 0.0128, 0.0118, -0.0125), (0.2745, 0.0195, 0.0134, -0.0142), (0.2725, 0.0285, 0.0148, -0.0155),
             (0.2705, 0.0368, 0.0158, -0.0161), (0.2690, 0.0418, 0.0163, -0.0164), (0.2675, 0.0446, 0.0166, -0.0166),
             (0.2620, 0.0482, 0.0182, -0.0170), (0.2540, 0.0476, 0.0202, -0.0170), (0.2440, 0.0460, 0.0218, -0.0168),
             (0.2320, 0.0442, 0.0230, -0.0162), (0.2180, 0.0432, 0.0240, -0.0160), (0.2040, 0.0442, 0.0236, -0.0170),
             (0.1900, 0.0456, 0.0230, -0.0180), (0.1600, 0.0482, 0.0232, -0.0195), (0.1200, 0.0512, 0.0246, -0.0210),
             (0.0800, 0.0546, 0.0264, -0.0228), (0.0400, 0.0580, 0.0284, -0.0245), (0.0110, 0.0606, 0.0300, -0.0258)]


# =============================================================================================== humans: shared bits
def hanging_end(C, name, reg, kx, y0, y_end, wd, bone, off=0.0040, pc=1, knot=True):
    """A knot on a band at x = kx and one hanging end skinned to `bone` (child of hips) so it swings (Daniel's
    hanging_tie with a single bone)."""
    S = C.S; rr = C.robe_rows
    wtop = C.w(["hips", "spine"])
    ka0 = math.asin(max(-1, min(1.0, kx / table(rr, y0)[0])))
    ka2 = math.asin(max(-1, min(1, (kx + 0.002 * S * (1 if kx > 0 else -1)) / (table(rr, y_end)[0] + 0.002))))
    p1 = shell_point(rr, y0 - 0.006 * S, ka0, (off + 0.0010) * S)
    p3 = shell_point(rr, y_end, ka2, (off + 0.0012) * S)
    C.B[bone] = (p1, p3, "hips")
    wb = C.w([bone], blend=0.010 * S)

    def wfn(p):
        t = smoothstep(y0 - 0.004 * S, y0 - 0.016 * S, p.y)
        return mixw((wtop(p), 1 - t), (wb(p), t)) if t > 0 else wtop(p)
    cg = Cage()
    kc = shell_point(rr, y0, ka0, off * S)
    if knot:
        lathe_y(cg, kc, [(-0.0030 * S, 0.0020 * S), (0.0, 0.0038 * S), (0.0030 * S, 0.0020 * S)], 10, wfn, reg, pc, e=2.6,
                zscale=0.6)
    pp, nn = [], []
    for t in [i / 9 for i in range(10)]:
        y = lerp(y0 - 0.0020 * S, y_end, t)
        x = kx + 0.0030 * S * t * (1 if kx > 0 else -1)
        a = math.asin(max(-1, min(1, x / (table(rr, y)[0] + 0.002))))
        p = shell_point(rr, y, a, (off + 0.0004 + 0.0014 * math.sin(t * math.pi)) * S)
        pp.append(p); nn.append(V(p.x, 0, p.z).normalized())
    strip(cg, pp, nn, [wd * S * (1.0 + 0.30 * t) for t in [i / 9 for i in range(10)]], 0.0008 * S, wfn, reg, pc)
    blob(cg, pp[-1] + V(0, -0.0010 * S, 0.0004 * S), wd * S * 1.25, 0.0020 * S, 0.0011 * S, wfn, reg, pc, NU=10, NV=4)
    C.add(name, cg, subdiv=0)


def ragged_hem(cg, hem, S, amp=0.0034, band=0.0060):
    """Fray the hem of a robe cage: an irregular zigzag on the lowest rows (Jonah's old tunic)."""
    for i, p in enumerate(cg.v):
        if p.y < hem + band * S:
            a = math.atan2(p.x, p.z)
            z = (abs(((a * 11.0 / math.pi) % 2.0) - 1.0) * 2 - 1) * 0.7 + 0.3 * math.sin(a * 5.0 + 1.3)
            f = smoothstep(hem + band * S, hem + 0.0005 * S, p.y)
            cg.v[i] = V(p.x, p.y + amp * S * z * f, p.z)


KING_ROBE = [(0.2760, 0.0128, 0.0118, -0.0125), (0.2745, 0.0195, 0.0134, -0.0142), (0.2725, 0.0285, 0.0148, -0.0155),
             (0.2705, 0.0368, 0.0158, -0.0161), (0.2690, 0.0418, 0.0163, -0.0164), (0.2675, 0.0446, 0.0166, -0.0166),
             (0.2620, 0.0482, 0.0182, -0.0170), (0.2540, 0.0476, 0.0202, -0.0170), (0.2440, 0.0460, 0.0218, -0.0168),
             (0.2320, 0.0442, 0.0230, -0.0162), (0.2180, 0.0432, 0.0240, -0.0160), (0.2040, 0.0442, 0.0236, -0.0170),
             (0.1900, 0.0456, 0.0230, -0.0180), (0.1600, 0.0482, 0.0232, -0.0195), (0.1200, 0.0512, 0.0246, -0.0210),
             (0.0800, 0.0546, 0.0264, -0.0228), (0.0400, 0.0580, 0.0284, -0.0245), (0.0110, 0.0606, 0.0300, -0.0258)]


def cut_rows(rows, hem):
    return [r for r in rows if r[0] > hem + 0.006] + [(hem,) + tuple(table(rows, hem))]


# =============================================================================================== polish 2026-11-15
# Sculpt pass ("精致、多面、声音合适、儿童喜爱，精修"): sculpted hair / beard locks, a twisted head cloth, layered trims,
# sandals with real soles and straps, the captain's vest and rope details. Every new part either merges into a printed
# region (piece_as) or prints as detail lines (PART_ANCHORS / fixed-colour swatches), so no new sheet slivers.
def lock(cg, ctrl, w0, th, wfn, NS=14, N=8, reg="hair", pc=0, tip=0.12, root=0.55, flat=0.38, h0=0.65, hend=0.72):
    """One sculpted lock of hair (Gabriel's lock, pipeline/ga_character.py): a flattened, tapering tube along
    ctrl = [(point, outward normal)], w0 = half width, th = height above its base line."""
    P_ = [c[0] for c in ctrl]; Nn = [c[1] for c in ctrl]
    rings = []
    for i in range(NS + 1):
        t = i / NS
        p = cr_open(P_, t); n = cr_open(Nn, t).normalized()
        T = (cr_open(P_, min(1.0, t + 0.02)) - cr_open(P_, max(0.0, t - 0.02))).normalized()
        A = perp(n, T); Bv = T.cross(A)
        w = w0 * (root + (1 - root) * math.sin(math.pi / 2 * min(1.0, t / 0.35))) * (1 - (1 - tip) * smoothstep(0.62, 1.0, t))
        h = th * (h0 + (1 - h0) * math.sin(math.pi / 2 * min(1.0, t / 0.4))) * (1 - hend * smoothstep(0.70, 1.0, t))
        ring = []
        for k in range(N):
            a = 2 * math.pi * k / N
            sa = math.sin(a)
            ring.append(p + Bv * (math.cos(a) * w) + A * (sa * h if sa >= 0 else sa * h * flat))
        rings.append(cg.ring(ring, wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(list(reversed(rings[0])), P_[0] - (P_[1] - P_[0]).normalized() * w0 * 0.3, wfn, reg, pc)
    cg.fan(rings[-1], P_[-1] + (P_[-1] - P_[-2]).normalized() * w0 * (0.25 + 0.6 * tip), wfn, reg, pc)


def rim_uu(rim, y):
    """Smallest mirrored azimuth where the hair shell (lower edge rim(u)) still reaches down to height y."""
    for k in range(0, 201):
        uu = 0.5 * k / 200
        if rim(uu) <= y:
            return uu
    return 0.5


def hair_pt(C, u, y, off):
    """Point `off` above the hair shell at (u, y) and the outward direction (radial; horizontal below eye level)."""
    L = C.L
    q = C.hair_outer(u % 1.0, y)
    n = (q - V(0, min(q.y, L["eye"]), L["zc"])).normalized()
    return q + n * off, n


def hair_locks(C, rim, specs, w0, th, name="locks", piece="hair", streak_ids=(), NP=8, NS=16, N=8, flick=0.0008):
    """Locks combed from the crown down over the hair shell: specs = [(uu top, uu bottom, width factor)], mirrored to
    both sides; each lock stays clear of the face (uu >= the hair edge at its height + margin) and ends just above the
    shell's lower edge with a small outward flick."""
    L = C.L; H = C.H; S = C.S
    cg = Cage(); wfn = C.w(["head"])
    yT = L["top"] - 0.060 * H                         # start below the crown: the crown height stays as before (kneel_pray under the belly dome)
    for sx in (1, -1):
        for k, (ut, ub, wf) in enumerate(specs):
            if sx < 0 and ut >= 0.4999 and ub >= 0.4999:
                continue                                      # the middle back lock only once
            yb = rim(ub) + 0.030 * H
            ys_ = [lerp(yT, yb, (i / (NP - 1)) ** 0.85) for i in range(NP)]
            us_ = [min(0.5, max(lerp(ut, ub, smoothstep(0.0, 1.0, i / (NP - 1)) ** 0.8), rim_uu(rim, y) + 0.022))
                   for i, y in enumerate(ys_)]
            for _ in range(2):                                # smooth out the kinks of the face-edge clamp
                us_ = [us_[0]] + [(us_[i - 1] + 2 * us_[i] + us_[i + 1]) / 4 for i in range(1, NP - 1)] + [us_[-1]]
                us_ = [min(0.5, max(uu, rim_uu(rim, y) + 0.022)) for uu, y in zip(us_, ys_)]
            ctrl = []
            for i in range(NP):
                y = ys_[i]; uu = us_[i]
                u = uu if sx > 0 else 1.0 - uu
                p, n = hair_pt(C, u, y, 0.0003 * S)
                ctrl.append((p, n))
            p, n = ctrl[-1]
            ctrl[-1] = (p + n * flick * S + V(0, 0.0010 * S, 0), (n + V(0, 0.6, 0)).normalized())
            reg = "streaks" if k in streak_ids else "hair"
            kk = 1.45 if k in streak_ids else 1.0          # the grey lock lies on top of its neighbours
            lock(cg, ctrl, w0 * wf * S, th * kk * S, wfn, NS=NS, N=N, reg=reg, tip=0.30, root=0.60, h0=0.45, hend=0.60)
    C.add(name, cg, subdiv=0, piece_as=piece)


def cage_bvh(cg):
    return BVHTree.FromPolygons([tuple(v) for v in cg.v], [tuple(f) for f in cg.f])


def beard_locks(C, beard_part, cols, w0, th, reg, piece, name="beardLocks", NS=12, N=8):
    """Locks lying on the beard: cols = [(x top, y top, x bottom, y bottom)]; each control point is the beard's front
    surface hit by a ray along -Z (jaw-weighted with the beard, decal-flagged so an open-mouth drawing stays visible)."""
    S = C.S
    bc = [p for p in C.parts if p["name"] == beard_part][-1]["cage"]
    bvh = cage_bvh(bc)
    cg = Cage(); wfn = C.w(["head"])
    for x0, y0, x1, y1 in cols:
        ctrl = []
        for i in range(7):
            t = i / 6
            x = lerp(x0, x1, t); y = lerp(y0, y1, t)
            hit = bvh.ray_cast(V(x, y, 0.3), V(0, 0, -1), 1.0)
            if not hit[0]:
                continue
            n = hit[1] if hit[1].z > 0 else -hit[1]
            ctrl.append((hit[0] + n * 0.0002 * S, (n + V(0, 0, 0.3)).normalized()))
        if len(ctrl) >= 4:
            lock(cg, ctrl, w0 * S, th * S, wfn, NS=NS, N=N, reg=reg, tip=0.30, root=0.60, h0=0.55, hend=0.50)
    C.add(name, cg, subdiv=0, piece_as=piece, decal=True, jaw=True, jawBelow=0.6, jawZ=-0.03)


def beard_curls(C, beard_part, pts, r, reg, piece, name="beardCurls", NU=8, NV=4):
    """Small round curls (flattened blobs) on the beard surface at the given (x, y) points (ray along -Z)."""
    S = C.S
    bc = [p for p in C.parts if p["name"] == beard_part][-1]["cage"]
    bvh = cage_bvh(bc)
    cg = Cage(); wfn = C.w(["head"])
    for i, (x, y) in enumerate(pts):
        hit = bvh.ray_cast(V(x, y, 0.3), V(0, 0, -1), 1.0)
        if not hit[0]:
            continue
        n = hit[1] if hit[1].z > 0 else -hit[1]
        n = (n + V(0, 0, 0.4)).normalized()
        xa = perp(V(0, 1, 0), n); ya = n.cross(xa)
        M = Matrix((xa, ya, n)).transposed()
        rr = r * S * (0.85 + 0.30 * ((i * 7) % 5) / 4)
        blob(cg, hit[0] - n * rr * 0.05, rr, rr * 0.92, rr * 0.42, wfn, reg, 0, NU=NU, NV=NV, ax=M)
    C.add(name, cg, subdiv=0, piece_as=piece, decal=True, jaw=True, jawBelow=0.6, jawZ=-0.03)


def twisted_ring(cg, path, ra, rb, wfn, reg, pc=0, N=6, twist=0.9, ref=None):
    """A twisted rope / cloth roll along a closed path (the first point is repeated at the end)."""
    return tube(cg, path + [path[0]], [(ra, rb)] * (len(path) + 1), N, wfn, reg, pc, ref=ref, cap0=False, cap1=False,
                twist=twist)


def wrap_band(C, name, reg, y0, y1, off, bulge, amp, turns, NA=80, rows=(0.0, 0.06, 0.20, 0.36, 0.50, 0.64, 0.80, 0.94, 1.0),
              phase=0.4, pc=0):
    """A cloth band wrapped round the waist: rounded profile, rolled edges and diagonal folds (the captain's sash
    method), on the current robe rows."""
    S = C.S; cg = Cage(); wb = C.w(["hips", "spine"])
    rings = []
    for t in rows:
        y = lerp(y0, y1, t)
        ring = []
        for i in range(NA):
            a = 2 * math.pi * i / NA
            edge = smoothstep(0.0, 0.12, t) * smoothstep(1.0, 0.88, t)
            fold = amp * S * math.cos(2 * math.pi * turns * t + 1.7 * math.sin(a) + phase) * edge
            o = off * S + bulge * S * math.sin(math.pi * t) ** 0.6 * edge + fold
            ring.append(shell_point(C.robe_rows, y, a, o))
        rings.append(cg.ring(ring, wb))
    for a_, b_ in zip(rings, rings[1:]):
        cg.bridge(a_, b_, reg, pc)
    C.add(name, cg, subdiv=0)


def foot_slice(cg0, pred):
    pts = [p for p in cg0.v if pred(p)]
    return pts


def sandal_gear(C, side, reg="sandals", name=None, straps=True):
    """Real sandals: a sole slab round the foot (bottom at y 0.0002) and raised straps over the painted ones (ankle
    ring, instep and toe straps, a T-strap between them). Fixed colour through the decal swatch; UV0 anchored."""
    S = C.S
    legp = [p for p in C.parts if p["name"] == "leg" + side][-1]
    vs = legp["cage"].v
    ank = C.B["foot" + side][0]
    wleg = C.w(["shin" + side, "foot" + side, "toe" + side])
    cg = Cage()
    low = [p for p in vs if p.y < 0.0045 * S]
    cx = sum(p.x for p in low) / len(low); cz = sum(p.z for p in low) / len(low)
    NB = 24; rad = [0.0] * NB
    for p in low:
        a = math.atan2(p.x - cx, p.z - cz); b = int((a + math.pi) / (2 * math.pi) * NB) % NB
        rad[b] = max(rad[b], math.hypot(p.x - cx, p.z - cz))
    for i in range(NB):                                     # fill empty bins from neighbours
        if rad[i] == 0.0:
            rad[i] = max(rad[(i - 1) % NB], rad[(i + 1) % NB])
    rad = [(rad[(i - 1) % NB] + 2 * rad[i] + rad[(i + 1) % NB]) / 4 for i in range(NB)]

    def at(i, k, y):
        a = -math.pi + 2 * math.pi * (i + 0.5) / NB
        return V(cx + math.sin(a) * rad[i] * k, y, cz + math.cos(a) * rad[i] * k)
    rings = [cg.ring([at(i, 1.10, 0.0002) for i in range(NB)], wleg),
             cg.ring([at(i, 1.13, 0.0014 * S) for i in range(NB)], wleg),
             cg.ring([at(i, 1.10, 0.0030 * S) for i in range(NB)], wleg),
             cg.ring([at(i, 0.86, 0.0030 * S) for i in range(NB)], wleg)]
    for a_, b_ in zip(rings, rings[1:]):
        cg.bridge(a_, b_, reg, 0)
    cg.fan(list(reversed(rings[0])), V(cx, 0.0002, cz), wleg, reg, 0)
    if straps:
        # ankle ring
        ys = 0.0168 * S
        ring = [p for p in vs if abs(p.y - ys) < 0.0030 * S]
        if ring:
            ax_ = sum(p.x for p in ring) / len(ring); az_ = sum(p.z for p in ring) / len(ring)
            NB2 = 24; rr = [0.0] * NB2
            for p in ring:
                a = math.atan2(p.x - ax_, p.z - az_); b = int((a + math.pi) / (2 * math.pi) * NB2) % NB2
                rr[b] = max(rr[b], math.hypot(p.x - ax_, p.z - az_))
            for i in range(NB2):
                if rr[i] == 0.0:
                    rr[i] = max(rr[(i - 1) % NB2], rr[(i + 1) % NB2])
            path = [V(ax_ + math.sin(-math.pi + 2 * math.pi * (i + 0.5) / NB2) * (rr[i] + 0.0006 * S), ys,
                      az_ + math.cos(-math.pi + 2 * math.pi * (i + 0.5) / NB2) * (rr[i] + 0.0006 * S)) for i in range(NB2)]
            twisted_ring(cg, path, 0.0013 * S, 0.0007 * S, wleg, reg, 0, N=6, twist=0.0, ref=V(0, 1, 0))
        # instep and toe straps: arcs over the foot at fixed z
        arcs = []
        for dz, r_ in ((0.0085, 0.0014), (0.0195, 0.0011)):
            zs = ank.z + dz * S
            sl = [p for p in vs if abs(p.z - zs) < 0.0022 * S and p.y < 0.016 * S]
            if len(sl) < 3:
                continue
            x0 = min(p.x for p in sl); x1 = max(p.x for p in sl); yt = max(p.y for p in sl)
            xc = (x0 + x1) / 2; hx = (x1 - x0) / 2 + 0.0006 * S
            path = [V(xc + hx * math.cos(math.pi * i / 12), 0.0022 * S + (yt + 0.0005 * S - 0.0022 * S) * math.sin(math.pi * i / 12) ** 0.8, zs)
                    for i in range(13)]
            tube(cg, path, [(r_ * S, 0.0006 * S)] * 13, 6, wleg, reg, 0, ref=V(0, 0, 1), cap0=True, cap1=True)
            arcs.append(path[6])
        if len(arcs) == 2 and ring:
            top = V(arcs[0].x, ys, arcs[0].z - 0.0040 * S)
            tpath = [arcs[1].lerp(arcs[0], t) for t in (0.0, 0.5, 1.0)] + [arcs[0].lerp(top, t) + V(0, 0, 0.0012 * S * math.sin(math.pi * t)) for t in (0.5, 1.0)]
            tube(cg, tpath, [(0.0010 * S, 0.0005 * S)] * len(tpath), 6, wleg, reg, 0, ref=V(1, 0, 0), cap0=True, cap1=True)
    C.add(name or ("sandal" + side), cg, subdiv=0)




# =============================================================================================== Miracles: shared bits
def bare_arm(C, side, sv0, sv1, rr):
    """Bare upper arm from inside a short sleeve (sv0, in S units along the arm) to past the elbow (the captain's)."""
    A = C.arm[side]; S = C.S; hd = C.s["handDims"]
    cg = Cage()
    wa = C.w(["chest", "shoulder" + side, "upperArm" + side, "forearm" + side])
    svs = [sv0 + (sv1 - sv0) * t for t in (0.0, 0.25, 0.5, 0.75, 1.0)]
    path = [A["S0"] + A["d"] * (sv * S) for sv in svs] + [A["E"] + A["d"] * 0.004 * S]
    rads = [rr * S * f for f in (1.0, 1.02, 0.98, 0.92, 0.88)] + [hd["armR"]]
    tube(cg, path, [(r, r * 0.95) for r in rads], 12, wa, "skin", 0, ref=V(0, 0, 1), cap0=True, cap1=False)
    C.add("arm" + side, cg, subdiv=1)


def bare_knees(C, hemT, reg_shoe="sandals", sandals=True):
    """Knee tube from inside a knee-length hem down to the kit's lower leg, the kit leg and sandals (the captain's)."""
    s = C.s; S = C.S
    for side in "LR":
        cg = Cage()
        wk = C.w(["thigh" + side, "shin" + side])
        x0 = C.B["thigh" + side][1].x
        kS = s["footScale"] * S
        xe, ze = (0.0086 + 0.0074) / 2 * kS * 0.97, (0.0053 + 0.0082) / 2 * kS * 0.97   # the kit leg at y 0.050
        ye = 0.050 * S * 0.95
        path = [V(x0 * 0.98, y, 0.0006 * S) for y in (hemT + 0.020 * S, hemT, lerp(hemT, ye, 0.5), ye)]
        rr = [(ze * 1.12, xe * 1.10), (ze * 1.10, xe * 1.08), (ze * 1.05, xe * 1.04), (ze * 1.02, xe * 1.02)]
        tube(cg, path, rr, 12, wk, "skin", 0, ref=V(0, 0, 1), cap0=True, cap1=False)
        C.add("knee" + side, cg, subdiv=1)
        if sandals:
            build_leg(C, side, -1.0, reg_shoe, regfn2=sandal_regfn(S), top_y=0.050)
            sandal_gear(C, side, reg=reg_shoe)
        else:
            build_leg(C, side, -1.0, "skin", top_y=0.050)


def cuff_ring(C, side, sv, R, name_cg, reg, th=(0.0024, 0.0018), n=28):
    """A rolled sleeve end (twisted ring) round the arm at sv (S units) with radius R (S units)."""
    A_ = C.arm[side]; S = C.S
    c0 = A_["S0"] + A_["d"] * (sv * S)
    X0 = perp(V(0, 0, 1), A_["d"]); Y0 = A_["d"].cross(X0)
    pts = [c0 + (X0 * math.cos(2 * math.pi * j / n) + Y0 * math.sin(2 * math.pi * j / n)) * (R * S) for j in range(n)]
    twisted_ring(name_cg, pts, th[0] * S, th[1] * S, C.w(["upperArm" + side, "forearm" + side]), reg, 0, N=6,
                 twist=0.0, ref=A_["d"])


def short_hair(C, cb, back, sides, thick0=0.0030, name="hair", reg="hair", messy=0.0008, grooves=40):
    """Short hair: front edge cb, side edge at `sides` (y), back edge at `back` (y). Returns rim()."""
    L = C.L; H = C.H; S = C.S

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb), (0.08, cb - 0.01 * H), (0.13, L["brow"] + 0.14 * H), (0.17, L["eye"] + 0.10 * H),
                      (0.22, sides), (0.30, lerp(sides, back, 0.5)), (0.40, back), (0.50, back)], uu)[0]

    def thick(u, y):
        uu = mirror_u(u)
        t = thick0 + 0.0012 * smoothstep(L["eye"], L["top"], y) + 0.0006 * smoothstep(0.15, 0.40, uu)
        return t * S

    def mess(u, y):
        return messy * S * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 15 + 0.30 * math.sin(y * 300)))) \
            * smoothstep(L["top"] - 0.04 * H, L["eye"], y)
    hair_shell(C, rim, thick, name, reg, plumb=lambda uu: smoothstep(0.30, 0.42, uu) * 0.5, tuck_front=0.15,
               grooves=grooves, groove_amp=0.00035, curls=mess, NU=40, NV=8, top_extra=0.0004)
    return rim


def hair_cull_rim(C, rim, cb):
    s = C.s; S = C.S; nb = s["neckBase"]; L = C.L

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return p.y < nb - 0.0060 * S or uu > 0.02 or p.y > cb + 0.006 * S
        return uu > 0.15 and p.y > rim(u) + 0.0045 * S
    return cull


# =============================================================================================== Jesus
def build_jesus(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; shY = s["shoulder"][1]
    cb = L["brow"] + 0.29 * H                      # hairline, parted in the middle

    def rim(u):                                    # shoulder-length: over the ears, to the top of the shoulders
        uu = mirror_u(u)
        return table([(0.00, cb), (0.08, cb - 0.01 * H), (0.13, L["brow"] + 0.16 * H), (0.17, L["eye"] + 0.02 * H),
                      (0.20, L["nose"] - 0.06 * H), (0.235, L["mouth"] - 0.10 * H), (0.30, L["chin"] - 0.20 * H),
                      (0.38, L["chin"] - 0.27 * H), (0.50, L["chin"] - 0.29 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return True
        return uu > 0.15 and p.y > rim(u) + 0.0045 * S
    skeleton(C)
    build_head(C, cull)

    def thick(u, y):
        uu = mirror_u(u)
        t = 0.0030 + 0.0014 * smoothstep(L["eye"], L["top"], y) + 0.0012 * smoothstep(0.15, 0.40, uu)
        t *= 1.0 - 0.30 * smoothstep(L["top"] - 0.18 * H, L["top"], y)
        return t * S

    def wavy(u, y):                                # soft waves that lift a little at the ends
        return 0.00075 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 11 + 0.45 * math.sin(y * 200)))) \
            * smoothstep(L["top"] - 0.08 * H, L["eye"], y)
    hair_shell(C, rim, thick, "hair", "hair", plumb=lambda uu: smoothstep(0.22, 0.32, uu), tuck_front=0.15, grooves=36,
               groove_amp=0.00040, parting=True, waves=0.0009 * S, curls=wavy, NU=36, NV=8, top_extra=0.0003)
    # short full beard + moustache (one region with the hair)
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.068 * H), (0.07, L["mouth"] + 0.005 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.01 * H), (0.20, L["eye"] - 0.15 * H), (0.245, L["eye"] - 0.02 * H)]
    bot = [(0.00, L["chin"] - 0.15 * H), (0.06, L["chin"] - 0.14 * H), (0.12, L["chin"] - 0.10 * H),
           (0.17, L["chin"] - 0.02 * H), (0.21, L["mouth"] - 0.06 * H), (0.245, L["nose"] - 0.05 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0058, 0.0036, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0056 * S; row = math.floor((y - L["chin"]) / rh)
        return 0.0006 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 24 + 0.5 * (row % 2)))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.15 * H, reg="hair")
    moustache(C, "moustache", L["mouth"] + 0.100 * H, 0.60 * s["hw"], 0.07 * H, 0.0, 0.0018 * S, reg="hair", off=0.0016)
    C.parts[-1]["piece_as"] = "beard"
    # ---- long cream tunic to the ankles, sleeves to the wrist, a V neck (rolled edge)
    hemT = 0.034 * k
    RT = cut_rows(scale_rows(KING_ROBE, k, kx), hemT)
    RT[0] = (RT[0][0] - 0.0040 * S, RT[0][1] * 1.16) + RT[0][2:]
    RT[1] = (RT[1][0] - 0.0028 * S, RT[1][1] * 1.06) + RT[1][2:]
    sleeve_t = [(0.004, 0.0124), (0.014, 0.0120), (0.030, 0.0112), (0.048, 0.0106), (0.062, 0.0104), (0.074, 0.0108),
                (0.084, 0.0114), (0.096, 0.0120), (0.103, 0.0124)]
    build_robe(C, RT, sleeve_t, None, nf=12, fold_amp=0.0012, sleeve_fold=0.0008, reg="tunic", name="tunic", N=36,
               step=0.0078)
    C.tunic_rows = C.robe_rows
    vtop = C.robe_rows[0][0]
    cgv = Cage(); wv = C.w(["chest", "neck"])
    vp = []
    for t in [j / 12 for j in range(13)]:                       # V: left neck edge -> point -> right neck edge
        a = math.radians(lerp(30.0, 0.0, min(1.0, t * 2)) if t <= 0.5 else lerp(0.0, -30.0, (t - 0.5) * 2))
        y = lerp(vtop - 0.0020 * S, chestY + 0.012 * S, 1 - abs(t - 0.5) * 2)
        vp.append(shell_point(C.robe_rows, y, a, 0.0010 * S))
    tube(cgv, vp, [(0.0011 * S, 0.0011 * S)] * len(vp), 6, wv, "tunic", 0, ref=V(0, 0, 1))
    C.add("vneck", cgv, subdiv=0, piece_as="tunic")
    for side in "LR":
        build_forearm_hand(C, side, 0.040)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.062)
    # ---- warm brown mantle: over the left shoulder, across the chest to the right hip, wrapped round the waist to
    # below the knee (one panel front and back); its back drape on mantle1
    hemO = 0.074 * k
    RO = [(y, hw + 0.0030 * S + 0.0100 * S * smoothstep(0.215, 0.07, y), zf + 0.0030 * S + 0.0020 * S * smoothstep(0.20, 0.07, y),
           zb - 0.0030 * S - 0.0012 * S * smoothstep(0.20, 0.07, y)) for y, hw, zf, zb in scale_rows(KING_ROBE, k, kx)]
    RO = cut_rows(RO, hemO)
    sleeve_o = [(0.004, 0.0150), (0.014, 0.0148), (0.024, 0.0144), (0.032, 0.0142)]
    cg = build_robe(C, RO, sleeve_o, None, nf=10, fold_amp=0.0020, sleeve_fold=0.0006, reg="mantle", name="mantle",
                    solidify=0.0010, keep=True, N=36, step=0.0072)
    hwC = table(C.robe_rows, chestY)[0]

    def ycut(x):                                   # top edge of the mantle: right hip -> left shoulder
        return lerp(wy - 0.006 * S, C.robe_rows[0][0] + 0.004 * S, smoothstep(-0.95 * hwC, 0.55 * hwC, x))

    def sleeve_of(c):
        for side in "LR":
            A_ = C.arm[side]; sv = (c - A_["S0"]).dot(A_["d"])
            if sv > 0.002 * S and (c - (A_["S0"] + A_["d"] * sv)).length < 0.03 * S:
                return side
        return None

    def gone(c):
        sd = sleeve_of(c)
        if sd == "R":
            return True
        if sd == "L":
            return False
        return c.y > ycut(c.x)
    drop_faces(cg, gone)
    zc_ = lambda y: (table(C.robe_rows, y)[1] + table(C.robe_rows, y)[2]) / 2
    zbC = table(C.robe_rows, chestY)[2]; zbH = table(C.robe_rows, hemO + 0.01)[2]
    C.B["mantle1"] = (V(0.30 * hwC, chestY - 0.010 * S, zbC - 0.003 * S), V(0.10 * hwC, hemO + 0.006, zbH - 0.004 * S), "chest")
    for i, p in enumerate(cg.v):                   # the back drape swings on mantle1 (blend in below the chest)
        if p.z > zc_(p.y) - 0.002 * S or sleeve_of(p):
            continue
        tw = 0.75 * smoothstep(chestY - 0.006 * S, wy - 0.030 * S, p.y) * smoothstep(zc_(p.y) - 0.002 * S, zc_(p.y) - 0.010 * S, p.z)
        if tw > 0:
            cg.w[i] = mixw((cg.w[i], 1 - tw), ({"mantle1": 1.0}, tw))
    # rolled edge along the diagonal top of the mantle, front and back (merges into the mantle on the sheet)
    cge = Cage(); we = skirt_weights(C)
    for a0, a1 in ((-math.pi * 0.62, math.pi * 0.62), (math.pi * 1.38, math.pi * 0.62)):
        path = []
        for j in range(33):
            a = lerp(a0, a1, j / 32)
            y = ycut(math.sin(a) * hwC)
            for _ in range(3):
                y = ycut(shell_point(C.robe_rows, min(y, C.robe_rows[0][0] - 0.002 * S), a, 0.0).x)
            y = min(y, C.robe_rows[0][0] - 0.0020 * S)
            p = shell_point(C.robe_rows, y, a, 0.0018 * S)
            if sleeve_of(p) == "L" and y > shY - 0.022 * S:
                continue
            path.append(p)
        if len(path) > 4:
            tube(cge, path, [(0.0019 * S, 0.0015 * S)] * len(path), 6, we, "mantle", 0, ref=V(0, 1, 0))
    C.add("mantleEdge", cge, subdiv=0, piece_as="mantle")
    # ---- narrow tan cloth belt over the mantle (two wraps), one fringed end hanging (belt1)
    bw = wy - 0.010 * S
    wrap_band(C, "beltA", "belt", bw - 0.0130 * S, bw + 0.0005 * S, 0.0012, 0.0012, 0.0006, 1.6, phase=0.3, NA=48)
    C.parts[-1]["piece_as"] = "belt"
    wrap_band(C, "beltB", "belt", bw - 0.0010 * S, bw + 0.0115 * S, 0.0022, 0.0012, 0.0006, 1.6, phase=2.1, NA=48)
    C.parts[-1]["piece_as"] = "belt"
    hanging_end(C, "beltEnd", "belt", -0.0120 * S, bw - 0.004 * S, bw - 0.060 * S, 0.0042, "belt1", off=0.0042)
    C.parts[-1]["piece_as"] = "belt"
    rr_ = C.robe_rows; kx_ = -0.0120 * S; y_end = bw - 0.060 * S
    xe = kx_ - 0.0030 * S
    ae = math.asin(max(-1, min(1, xe / (table(rr_, y_end)[0] + 0.002))))
    pe = shell_point(rr_, y_end, ae, (0.0042 + 0.0004) * S) + V(0, -0.0018 * S, 0.0004 * S)
    cg = Cage(); wfr = C.w(["belt1"], blend=0.010 * S)
    for j in range(6):
        dx = (j - 2.5) / 2.5 * 0.0042 * S * 1.1
        ln = (0.0080 + 0.0020 * ((j * 3) % 4) / 3) * S
        pth = [pe + V(dx * (1 + 0.15 * t), -ln * t, 0.0004 * S * math.sin(t * 3 + j)) for t in [q / 5 for q in range(6)]]
        tube(cg, pth, [(0.00070 * S * (1 - 0.4 * t), 0.00060 * S * (1 - 0.4 * t)) for t in [q / 5 for q in range(6)]], 6,
             wfr, "belt", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
    C.add("beltFringe", cg, subdiv=0)
    for side in "LR":
        sandal_gear(C, side)


# =============================================================================================== Peter
def build_peter(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]
    cb = L["brow"] + 0.27 * H                      # hairline (under the cloth)

    def hrim(u):                                   # curly hair: over the ears, thick at the nape
        uu = mirror_u(u)
        return table([(0.00, cb), (0.08, cb - 0.01 * H), (0.13, L["brow"] + 0.12 * H), (0.17, L["eye"] + 0.00 * H),
                      (0.21, L["nose"] - 0.06 * H), (0.26, L["mouth"] - 0.02 * H), (0.34, L["chin"] + 0.02 * H),
                      (0.50, L["chin"] - 0.06 * H)], uu)[0]
    crim_front = L["brow"] + 0.20 * H

    def crim(u):                                   # the head cloth: low on the forehead, above the ears, high at the back
        uu = mirror_u(u)
        return table([(0.00, crim_front), (0.10, crim_front - 0.01 * H), (0.17, L["brow"] + 0.16 * H),
                      (0.25, L["brow"] + 0.18 * H), (0.36, L["brow"] + 0.10 * H), (0.50, L["eye"] + 0.10 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S:
            return True
        if p.y > crim(u) + 0.0050 * S:
            return True
        return uu > 0.15 and p.y > hrim(u) + 0.0045 * S
    skeleton(C)
    build_head(C, cull)

    def hthick(u, y):
        uu = mirror_u(u)
        return (0.0034 + 0.0012 * smoothstep(0.15, 0.40, uu)) * S

    def curly(u, y):                               # tight round curls
        return 0.0011 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / (0.0050 * S)))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 34 + 0.5 * math.floor((y - L["chin"]) / (0.0050 * S)) % 2 * 0.5))) - 0.2)
    hair_shell(C, hrim, hthick, "hair", "hair", plumb=lambda uu: smoothstep(0.30, 0.42, uu) * 0.6, tuck_front=0.15,
               grooves=0, curls=curly, NU=24, NV=4, top_extra=0.0002)
    hair_outer = C.hair_outer
    # curls poking out below the cloth at the temples and the nape (flattened blobs on the hair shell)
    cgc = Cage(); wfh = C.w(["head"])
    rnd = random.Random(11)
    for sx in (1, -1):
        for uu, yy in ((0.20, crim(0.20) - 0.02 * H), (0.24, crim(0.24) - 0.05 * H), (0.30, crim(0.30) - 0.10 * H),
                       (0.36, crim(0.36) - 0.10 * H), (0.42, crim(0.42) - 0.12 * H), (0.48, crim(0.48) - 0.14 * H),
                       (0.27, crim(0.27) - 0.20 * H), (0.38, crim(0.38) - 0.24 * H), (0.46, crim(0.46) - 0.28 * H)):
            u = uu if sx > 0 else 1.0 - uu
            q = hair_outer(u, yy)
            n = (q - V(0, min(q.y, L["eye"]), L["zc"])).normalized()
            xa = perp(V(0, 1, 0), n); ya = n.cross(xa)
            rr = (0.0030 + 0.0006 * rnd.random()) * S
            blob(cgc, q - n * rr * 0.1, rr, rr * 0.95, rr * 0.55, wfh, "hair", 0, NU=6, NV=4,
                 ax=Matrix((xa, ya, n)).transposed())
    C.add("curls", cgc, subdiv=0, piece_as="hair")

    def cthick(u, y):
        uu = mirror_u(u)
        return (0.0062 + 0.0010 * smoothstep(L["eye"], L["top"], y) + 0.0006 * smoothstep(0.2, 0.5, uu)) * S

    def folds(u, y):
        return 0.0006 * S * math.cos(2 * math.pi * (u * 9 + 0.8 * (y - L["chin"]) / H)) * smoothstep(L["top"], L["eye"], y)
    hair_shell(C, crim, cthick, "headcloth", "headcloth", plumb=None, tuck_front=0.0, grooves=0, curls=folds, NU=26,
               NV=6, top_extra=0.0030)
    Hd = C.head
    ky = crim(0.5) + 0.010 * H
    kc = C.hair_outer(0.5, ky) + Hd.normal(0.5, ky) * (0.0030 * S)
    C.B["cloth1"] = (kc.copy(), kc + V(0, -0.046 * S, -0.012 * S), "head")
    ww = C.w(["cloth1"], blend=0.006 * S)

    def wtail(p):
        t = smoothstep(kc.y - 0.004 * S, kc.y - 0.014 * S, p.y)
        return mixw(({"head": 1.0}, 1 - t), (ww(p), t)) if t > 0 else {"head": 1.0}
    cg = Cage()
    blob(cg, kc, 0.0058 * S, 0.0048 * S, 0.0040 * S, wtail, "headcloth", 0, NU=10, NV=6)
    for sd in (1, -1):
        Mx = Matrix.Rotation(math.radians(sd * 50), 3, V(0, 0, 1))
        blob(cg, kc + V(sd * 0.0072 * S, 0.0028 * S, -0.0006 * S), 0.0060 * S, 0.0032 * S, 0.0028 * S, wtail, "headcloth", 0,
             NU=8, NV=5, ax=Mx)
    for sd, ln in ((1, 0.050), (-1, 0.040)):
        pp = [kc + V(sd * (0.003 + 0.008 * t) * S, -ln * S * t, -(0.004 + 0.012 * t * t) * S) for t in [i / 7 for i in range(8)]]
        rad = [(0.0016 * S, (0.0058 * (1 - 0.35 * t) + 0.0012) * S) for t in [i / 7 for i in range(8)]]
        tube(cg, pp, rad, 6, wtail, "headcloth", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
    C.add("knot", cg, subdiv=0, piece_as="headcloth")
    cg = Cage(); NPB = 30
    path = []
    for i in range(NPB):
        u = i / NPB; y = crim(u) + 0.0040 * S
        q = C.hair_outer(u, y); n = (q - V(0, min(q.y, L["eye"]), L["zc"])).normalized()
        path.append(q + n * 0.0004 * S)
    twisted_ring(cg, path, 0.0024 * S, 0.0018 * S, C.w(["head"]), "headcloth", 0, N=6, twist=0.0, ref=V(0, 1, 0))
    C.add("clothHem", cg, subdiv=0, piece_as="headcloth")
    # thick curly black beard + moustache
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.068 * H), (0.07, L["mouth"] + 0.005 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.01 * H), (0.20, L["eye"] - 0.12 * H), (0.245, L["eye"] + 0.00 * H)]
    bot = [(0.00, L["chin"] - 0.17 * H), (0.06, L["chin"] - 0.16 * H), (0.12, L["chin"] - 0.11 * H),
           (0.17, L["chin"] - 0.01 * H), (0.21, L["mouth"] - 0.04 * H), (0.245, L["nose"] - 0.03 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0062, 0.0036, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0046 * S; row = math.floor((y - L["chin"]) / rh)
        return 0.0011 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 36 + 0.5 * (row % 2)))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.17 * H, reg="hair")
    moustache(C, "moustache", L["mouth"] + 0.094 * H, 0.66 * s["hw"], 0.05 * H, 0.04 * H, 0.0022 * S, reg="hair", off=0.0016)
    C.parts[-1]["piece_as"] = "beard"
    hw_ = s["hw"]; cp = []
    for j, yy in enumerate((L["mouth"] - 0.12 * H, L["mouth"] - 0.20 * H, L["chin"] + 0.01 * H, L["chin"] - 0.07 * H)):
        n_ = 8 - j
        for i in range(n_):
            cp.append(((i - (n_ - 1) / 2) / max(1, n_ - 1) * hw_ * (1.70 - 0.32 * j) + (0.0 if j % 2 else 0.0010 * S), yy))
    for sx in (1, -1):
        for yy in (L["mouth"] - 0.04 * H,):
            cp.append((sx * hw_ * 0.92, yy))
    beard_curls(C, "beard", cp, 0.0023, "hair", "beard", NU=6)
    # ---- rust-red tunic to the knee, sleeves rolled to the elbow
    hemT = 0.100 * k
    RT = cut_rows(scale_rows(KING_ROBE, k, kx), hemT)
    yb = wy - 0.012 * S                            # broad chest, a little belly
    RT = [(y, hw * (1 + 0.05 * math.exp(-((y - chestY) / 0.025) ** 2)) + 0.0030 * S * math.exp(-((y - yb) / 0.028) ** 2),
           zf + 0.0030 * S * math.exp(-((y - chestY) / 0.02) ** 2) + 0.0110 * S * math.exp(-((y - yb) / 0.034) ** 2),
           zb - 0.0010 * S * math.exp(-((y - yb) / 0.03) ** 2)) for y, hw, zf, zb in RT]
    sleeve_t = [(0.004, 0.0138), (0.014, 0.0136), (0.026, 0.0132), (0.038, 0.0128), (0.048, 0.0126)]
    build_robe(C, RT, sleeve_t, None, nf=12, fold_amp=0.0013, sleeve_fold=0.0006, reg="tunic", name="tunic", N=32,
               step=0.0075)
    C.tunic_rows = C.robe_rows
    cg = Cage()
    for side in "LR":
        cuff_ring(C, side, 0.046, 0.0136, cg, "tunic", th=(0.0030, 0.0022), n=22)
    C.add("cuffs", cg, subdiv=0, piece_as="tunic")
    for side in "LR":
        bare_arm(C, side, 0.034, 0.052, 0.0112)
        build_forearm_hand(C, side, 0.002)
    bare_knees(C, hemT)
    # ---- sand over-vest: sleeveless, open front, rolled edges, tucked under the waist cloth (the captain's vest)
    sy0, sy1 = wy - 0.0190 * S, wy + 0.0110 * S
    vy0 = sy1 - 0.0080 * S; vy1 = C.robe_rows[0][0] - 0.0030 * S
    wv = skirt_weights(C)

    def vgap(y):
        return math.radians(lerp(10.0, 26.0, smoothstep(chestY + 0.008 * S, vy1, y)))
    tbvh = cage_bvh([p for p in C.parts if p["name"] == "tunic"][-1]["cage"])

    def vpt(y, f, off):
        g = vgap(y); a = lerp(g, 2 * math.pi - g, f)
        p = push_out_of_sleeves(C, shell_point(C.robe_rows, y, a, off), off)
        row = table(C.robe_rows, y)
        d = V(-p.x, 0, (row[1] + row[2]) / 2 - p.z)
        if d.length > 1e-9:
            d.normalize()
            hit = tbvh.ray_cast(p - d * 0.03 * S, d, 0.06 * S)
            if hit[0] and (hit[0] - (p + d * off)).dot(-d) > 0:
                p = hit[0] - d * off
        return p

    def vpa(y, a, off):
        g = vgap(y)
        return vpt(y, (a - g) / (2 * math.pi - 2 * g), off)
    armpit = shY - 0.024 * S

    def arm_w(y):
        return math.radians(36.0) * smoothstep(armpit, armpit + 0.016 * S, y) ** 0.8
    cg = Cage(); off_v = 0.0017 * S

    def grid(y0_, y1_, nr, spans):
        for lo, hi, nc in spans:
            rows_ = []
            for j in range(nr + 1):
                y = lerp(y0_, y1_, j / nr)
                a0, a1 = lo(y), hi(y)
                rows_.append(cg.ring([vpa(y, lerp(a0, a1, i / nc), off_v) for i in range(nc + 1)], wv))
            for r0, r1 in zip(rows_, rows_[1:]):
                cg.bridge(r0, r1, "vest", 0, closed=False)
    grid(vy0, armpit, 5, [(lambda y: vgap(y), lambda y: 2 * math.pi - vgap(y), 30)])
    grid(armpit, vy1, 5, [(lambda y: vgap(y), lambda y: math.pi / 2 - arm_w(y), 7),
                          (lambda y: math.pi / 2 + arm_w(y), lambda y: 1.5 * math.pi - arm_w(y), 14),
                          (lambda y: 1.5 * math.pi + arm_w(y), lambda y: 2 * math.pi - vgap(y), 7)])
    C.add("vest", cg, subdiv=0, solidify=0.0009)
    cg = Cage()
    ve0 = sy1 + 0.0004 * S
    for fe in (0.0, 1.0):
        ep = [vpt(lerp(ve0, vy1, t), fe, 0.0024 * S) for t in [q / 13 for q in range(14)]]
        tube(cg, ep, [(0.0016 * S, 0.0012 * S)] * len(ep), 6, wv, "vest", 0, ref=V(0, 0, 1))
    C.add("vestEdge", cg, subdiv=0, piece_as="vest")
    # ---- dark-brown waist cloth (wide band, diagonal folds) under a thick rope belt (fixed colour) with a knot
    cg = Cage(); wb = C.w(["hips", "spine"])
    NA = 44; rings = []
    rows = [0.0, 0.05, 0.16, 0.34, 0.50, 0.66, 0.84, 0.95, 1.0]
    for t in rows:
        y = lerp(sy0, sy1, t)
        ring = []
        for i in range(NA):
            a = 2 * math.pi * i / NA
            edge = smoothstep(0.0, 0.10, t) * smoothstep(1.0, 0.90, t)
            fold = 0.0010 * S * math.cos(2 * math.pi * 2.5 * t + 1.6 * math.sin(a) + 0.4) * edge
            off = 0.0012 * S + (0.0016 * S * math.sin(math.pi * t) ** 0.6) * edge + fold
            ring.append(shell_point(C.robe_rows, y, a, off))
        rings.append(cg.ring(ring, wb))
    for a_, b_ in zip(rings, rings[1:]):
        cg.bridge(a_, b_, "waistcloth", 0)
    C.add("waistcloth", cg, subdiv=0)
    cg = Cage()
    yr = (sy0 + sy1) / 2 - 0.0010 * S
    twisted_ring(cg, [shell_point(C.robe_rows, yr, 2 * math.pi * i / 40, 0.0046 * S) for i in range(40)],
                 0.0026 * S, 0.0022 * S, wb, "rope", 0, N=6, twist=1.1, ref=V(0, 1, 0))
    ka = math.radians(-24); kc2 = shell_point(C.robe_rows, yr, ka, 0.0070 * S)
    blob(cg, kc2, 0.0042 * S, 0.0036 * S, 0.0030 * S, wb, "rope", 0, NU=10, NV=6)
    wends = C.w(["hips", ("thighR", 0.02 * S)], blend=0.02 * S)
    for dx, ln in ((-0.0030, 0.030), (0.0020, 0.024)):
        pth = [kc2 + V(dx * S + 0.0010 * S * t, -ln * S * t, 0.0012 * S * math.sin(t * 2.5)) for t in [q / 6 for q in range(7)]]
        tube(cg, pth, [(0.0020 * S, 0.0018 * S)] * len(pth), 6, wends, "rope", 0, ref=V(0, 0, 1), twist=0.9, cap0=True,
             cap1=True)
    C.add("rope", cg, subdiv=0)
    # ---- the bucket (hidden prop, right hand): a small wooden bucket hanging from its rope handle
    gp = grip_point(C, "R")
    A_ = C.arm["R"]
    C.B["bucket"] = (gp.copy(), gp + V(0, -0.030 * S, 0), "handR")
    cg = Cage()
    br, bh = 0.0130 * S, 0.0210 * S
    top_c = gp + V(0, -0.0170 * S, 0)
    prof = [(-bh, 0.0), (-bh, br * 0.86), (-bh * 0.96, br * 0.88), (-bh * 0.5, br * 0.95), (-bh * 0.08, br),
            (0.0, br * 1.06), (0.0015 * S, br * 1.06), (0.0015 * S, br * 0.92), (-bh * 0.85, br * 0.80), (-bh * 0.85, 0.0)]
    rings = []
    for dy, r in prof:
        if r <= 0:
            rings.append(None); continue
        rings.append(cg.ring([top_c + V(math.sin(2 * math.pi * j / 12) * r, dy, math.cos(2 * math.pi * j / 12) * r)
                              for j in range(12)], None))
    for i in range(len(prof) - 1):
        a, b = rings[i], rings[i + 1]
        if a and b:
            cg.bridge(a, b, "bucket", 0)
        elif b and a is None:
            cg.fan(list(reversed(b)), top_c + V(0, prof[i][0], 0), None, "bucket", 0)
        elif a and b is None:
            cg.fan(a, top_c + V(0, prof[i + 1][0], 0), None, "bucket", 0)
    for f in (0.30, 0.72):                                      # two hoops
        y = -bh * f
        r = lerp(br * 0.95, br, f) + 0.0006 * S
        twisted_ring(cg, [top_c + V(math.sin(2 * math.pi * j / 16) * r, y, math.cos(2 * math.pi * j / 16) * r) for j in range(16)],
                     0.0008 * S, 0.0008 * S, None, "bucket", 0, N=5, twist=0.0, ref=V(0, 1, 0))
    hp = [top_c + V(math.cos(math.pi * t) * br * 1.02, 0.0016 * S + math.sin(math.pi * t) * (gp.y - top_c.y - 0.0018 * S), 0)
          for t in [q / 12 for q in range(13)]]
    tube(cg, hp, [(0.0009 * S, 0.0009 * S)] * len(hp), 6, None, "bucket", 0, ref=V(0, 0, 1))
    C.add("bucket", cg, subdiv=0, rigid="bucket")


# =============================================================================================== the man on the mat
def build_man(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; shY = s["shoulder"][1]
    cb = L["brow"] + 0.30 * H
    back = L["chin"] + 0.06 * H; sides = L["eye"] - 0.02 * H

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb), (0.08, cb - 0.01 * H), (0.13, L["brow"] + 0.14 * H), (0.17, L["eye"] + 0.08 * H),
                      (0.22, sides), (0.30, lerp(sides, back, 0.5)), (0.40, back), (0.50, back)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return True
        return uu > 0.15 and p.y > rim(u) + 0.0045 * S
    skeleton(C)
    build_head(C, cull, ears=None)

    def thick(u, y):
        uu = mirror_u(u)
        t = 0.0026 + 0.0012 * smoothstep(L["eye"], L["top"], y) + 0.0006 * smoothstep(0.15, 0.40, uu)
        return t * S

    def mess(u, y):                                 # short and untidy
        return 0.0009 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 17 + 0.35 * math.sin(y * 300)))) \
            * smoothstep(L["top"] - 0.04 * H, L["eye"], y)
    hair_shell(C, rim, thick, "hair", "hair", plumb=lambda uu: smoothstep(0.30, 0.42, uu) * 0.5, tuck_front=0.15,
               grooves=40, groove_amp=0.00035, curls=mess, NU=40, NV=8, top_extra=0.0004)
    # scruffy short beard (patchy edge, thin) + a thin moustache
    top = [(0.00, L["mouth"] - 0.085 * H), (0.035, L["mouth"] - 0.075 * H), (0.07, L["mouth"] - 0.01 * H),
           (0.10, L["nose"] - 0.07 * H), (0.15, L["nose"] - 0.02 * H), (0.20, L["eye"] - 0.20 * H), (0.245, L["eye"] - 0.08 * H)]
    bot = [(0.00, L["chin"] - 0.08 * H), (0.06, L["chin"] - 0.075 * H), (0.12, L["chin"] - 0.04 * H),
           (0.17, L["chin"] + 0.04 * H), (0.21, L["mouth"] - 0.02 * H), (0.245, L["nose"] - 0.07 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0030, 0.0020, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.25, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0004 * S

    def bscruff(u, y):
        return 0.0006 * S * (math.sin(u * 190 + y * 900) * 0.5 + math.sin(u * 77 - y * 1300) * 0.5)
    build_beard(C, top, bot, bthick, bscruff, 0.245, L["chin"] - 0.08 * H, reg="hair", solid=0.0035)
    moustache(C, "moustache", L["mouth"] + 0.090 * H, 0.52 * s["hw"], 0.05 * H, 0.0, 0.0013 * S, reg="hair", off=0.0014)
    C.parts[-1]["piece_as"] = "beard"
    # ---- plain pale green tunic to the knee, sleeves to the forearm; thin
    hemT = 0.104 * k
    RT = cut_rows(scale_rows(KING_ROBE, k, kx), hemT)
    RT[0] = (RT[0][0] - 0.0035 * S, RT[0][1] * 1.12) + RT[0][2:]
    sleeve_t = [(0.004, 0.0118), (0.014, 0.0114), (0.030, 0.0106), (0.048, 0.0100), (0.062, 0.0100), (0.074, 0.0104),
                (0.084, 0.0108)]
    build_robe(C, RT, sleeve_t, None, nf=12, fold_amp=0.0012, sleeve_fold=0.0008, reg="tunic", name="tunic", N=40,
               step=0.0062)
    C.tunic_rows = C.robe_rows
    cg = Cage()
    for side in "LR":
        cuff_ring(C, side, 0.083, 0.0110, cg, "tunic", th=(0.0016, 0.0013))
    C.add("cuffs", cg, subdiv=0, piece_as="tunic")
    for side in "LR":
        build_forearm_hand(C, side, 0.026)
    bare_knees(C, hemT, sandals=False)
    # ---- mustard sash: two wraps, a knot and a hanging end (sash1)
    bw = wy - 0.008 * S
    wrap_band(C, "sashA", "sash", bw - 0.0170 * S, bw + 0.0005 * S, 0.0012, 0.0015, 0.0008, 1.8, phase=0.6, NA=48)
    C.parts[-1]["piece_as"] = "sash"
    wrap_band(C, "sashB", "sash", bw - 0.0010 * S, bw + 0.0140 * S, 0.0024, 0.0015, 0.0008, 1.8, phase=2.4, NA=48)
    C.parts[-1]["piece_as"] = "sash"
    hanging_end(C, "sashEnd", "sash", 0.0140 * S, bw - 0.004 * S, bw - 0.062 * S, 0.0056, "sash1", off=0.0048)
    C.parts[-1]["piece_as"] = "sash"
    # ---- the mat (shown, child of root; flat on the page in the rest pose), the ropes (child of mat, hidden) and
    # the rolled mat on the left shoulder (child of chest, hidden)
    build_mat(C)
    build_mat_roll(C)


MAT_STRIPES = ((-0.118, -0.078), (-0.020, 0.020), (0.078, 0.118))     # red bands across the pad, 0.04 wide (>= 6 mm)


def build_mat(C):
    m = MAT; cz = m["cz"]
    yc = (m["top"] + m["bot"]) / 2; hy = (m["top"] - m["bot"]) / 2
    C.B["mat"] = (V(0, 0.014, cz), V(0, 0.044, cz), "root")
    C.B["ropes"] = (V(0, m["top"], cz), V(0, m["top"] + m["rope_h"], cz), "mat")
    cg = Cage()
    xs = set()
    for x0, x1 in MAT_STRIPES:
        xs |= {x0, x1}
    n = 30
    xs |= {-m["hx"] + 2 * m["hx"] * i / n for i in range(n + 1)}
    xs |= {-m["hx"] + 0.006, m["hx"] - 0.006, -m["hx"] + 0.002, m["hx"] - 0.002}
    xs = sorted(round(x, 5) for x in xs)
    xs = [x for i, x in enumerate(xs) if i == 0 or x - xs[i - 1] > 0.0015]
    NS = 20

    def section(x):
        """Pillow section at x: rounded (superellipse) in z, y; domed top; ends rounded in plan."""
        t = abs(x) / m["hx"]
        end = math.sqrt(max(0.0, 1 - max(0.0, (t - 0.94) / 0.06) ** 2))       # round the ends a little
        pts = []
        for j in range(NS):
            a = 2 * math.pi * j / NS
            ca, sa = math.cos(a), math.sin(a)
            zz = cz + se(ca, 3.6) * m["hz"] * (0.82 + 0.18 * end)
            dome = 1.0 + 0.25 * (1 - (abs(se(ca, 3.6))) ** 2) * (1 if sa > 0 else 0.2)
            yy = yc + se(sa, 3.6) * hy * dome * (0.55 + 0.45 * end)
            pts.append(V(x, yy, zz))
        return pts

    def reg_x(x):
        for x0, x1 in MAT_STRIPES:
            if x0 - 1e-6 <= x <= x1 + 1e-6:
                return "stripes"
        return "mat"
    rings = [cg.ring(section(x), None) for x in xs]
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        cg.bridge(a, b, reg_x((xs[i] + xs[i + 1]) / 2), 0)
    cg.fan(list(reversed(rings[0])), V(xs[0] - 0.0015, yc, cz), None, "mat", 0)
    cg.fan(rings[-1], V(xs[-1] + 0.0015, yc, cz), None, "mat", 0)
    # two carrying poles along the long sides, sticking out 0.05 at each end (fixed colour: detail lines)
    for sz in (1, -1):
        z = cz + sz * m["pole_z"]
        path = [V(-m["pole_x"] + 2 * m["pole_x"] * i / 16, m["pole_y"], z) for i in range(17)]
        tube(cg, path, [(m["pole_r"], m["pole_r"])] * len(path), 8, None, "poles", 0, ref=V(0, 1, 0), cap_len=0.5)
    C.add("mat", cg, subdiv=0, rigid="mat")
    # four ropes from the pad's corners rising 0.45 (hidden except in `lowered`; fixed colour)
    cg = Cage()
    for sx in (1, -1):
        for sz in (1, -1):
            p0 = V(sx * (m["hx"] - 0.006), m["top"] - 0.002, cz + sz * (m["hz"] - 0.006))
            p1 = V(sx * 0.055, m["top"] + m["rope_h"], cz + sz * 0.045)
            path = [p0.lerp(p1, t) for t in [q / 10 for q in range(11)]]
            tube(cg, path, [(0.0016, 0.0016)] * len(path), 6, None, "ropes", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
            blob(cg, p0, 0.0040, 0.0030, 0.0040, None, "ropes", 0, NU=8, NV=4)        # knot at the corner
    C.add("ropes", cg, subdiv=0, rigid="ropes")


def build_mat_roll(C):
    """The rolled mat on the left shoulder: a cream roll with three red bands and two cord ties (fixed colour), its
    axis front-to-back, a little down at the front. matRoll bone: head at the roll centre, tail along the axis."""
    s = C.s; S = C.S
    A = C.arm["L"]
    r = 0.0210; ln = 0.130
    c = V(A["S0"].x - 0.004 * S, s["shoulder"][1] + 0.0105 * S + r, -0.006 * S)
    ax = V(0, -0.22, 1.0).normalized()
    C.B["matRoll"] = (c.copy(), c + ax * 0.040, "chest")
    X0 = V(1, 0, 0); Y0 = ax.cross(X0).normalized()
    cg = Cage()
    NS = 18; ts = [i / 24 for i in range(25)]

    def band(t):
        for a0, a1 in ((0.10, 0.24), (0.43, 0.57), (0.76, 0.90)):
            if a0 <= t <= a1:
                return "rollStripes"
        return "roll"
    rings = []
    for t in ts:
        cc = c + ax * (ln * (t - 0.5))
        rr = r * (1.0 - 0.06 * math.sin(math.pi * t) * 0)
        rings.append(cg.ring([cc + (X0 * math.cos(2 * math.pi * j / NS) + Y0 * math.sin(2 * math.pi * j / NS)) * rr
                              for j in range(NS)], None))
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        cg.bridge(a, b, band((ts[i] + ts[i + 1]) / 2), 0)
    for end, ring in ((-0.5, list(reversed(rings[0]))), (0.5, rings[-1])):   # spiral ends (a cream cap with a dent)
        cg.fan(ring, c + ax * (ln * end * 0.98), None, "roll", 0)
    for t in (0.33, 0.67):
        cc = c + ax * (ln * (t - 0.5))
        twisted_ring(cg, [cc + (X0 * math.cos(2 * math.pi * j / 24) + Y0 * math.sin(2 * math.pi * j / 24)) * (r + 0.0009)
                          for j in range(24)], 0.0014, 0.0011, None, "ropes", 0, N=5, twist=0.8, ref=ax)
    C.add("matRoll", cg, subdiv=0, rigid="matRoll")


# =============================================================================================== the four friends
def build_friend(C):
    ch = C.ch; fs = FRIEND[ch]; bx = fs["bodyX"]
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]
    nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]
    hair = fs["hair"]
    cb = L["brow"] + 0.30 * H
    if hair == "fringe":                           # bald with a fringe round the back and sides
        back = L["chin"] + 0.02 * H; sides = L["eye"] - 0.06 * H
        fr_top = L["eye"] + 0.36 * H

        def rim(u):
            uu = mirror_u(u)
            return table([(0.00, fr_top), (0.16, fr_top), (0.20, L["eye"] + 0.10 * H), (0.23, sides),
                          (0.32, lerp(sides, back, 0.5)), (0.40, back), (0.50, back)], uu)[0]

        def top_of(u):
            uu = mirror_u(u)
            return table([(0.00, fr_top - 0.10 * H), (0.18, fr_top - 0.10 * H), (0.24, L["eye"] + 0.30 * H),
                          (0.36, L["eye"] + 0.36 * H), (0.50, L["eye"] + 0.38 * H)], uu)[0]

        def cull(p):
            u = head_u(C, p); uu = mirror_u(u)
            if p.y < nb - 0.0060 * S:
                return True
            return uu > 0.20 and rim(u) + 0.0045 * S < p.y < top_of(u) - 0.0050 * S
    else:
        if hair == "curly":
            back = L["chin"] + 0.00 * H; sides = L["eye"] - 0.10 * H; cb = L["brow"] + 0.26 * H
        elif hair == "cap":
            back = L["chin"] + 0.08 * H; sides = L["eye"] - 0.02 * H; cb = L["brow"] + 0.26 * H
        else:
            back = L["chin"] + 0.05 * H; sides = L["eye"] - 0.04 * H

        def rim(u):
            uu = mirror_u(u)
            return table([(0.00, cb), (0.08, cb - 0.01 * H), (0.13, L["brow"] + 0.14 * H), (0.17, L["eye"] + 0.08 * H),
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
        base = 0.0034 if hair == "curly" else 0.0026
        return (base + 0.0012 * smoothstep(L["eye"], L["top"], y) + 0.0006 * smoothstep(0.15, 0.40, uu)) * S

    def mess(u, y):
        if hair == "curly":
            rh = 0.0048 * S; row = math.floor((y - L["chin"]) / rh)
            return 0.0013 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                                 * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 30 + 0.5 * (row % 2)))) - 0.15)
        return 0.0007 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 15 + 0.3 * math.sin(y * 300)))) \
            * smoothstep(L["top"] - 0.04 * H, L["eye"], y)
    hair_shell(C, rim, thick, "hair", "hair", plumb=lambda uu: smoothstep(0.30, 0.42, uu) * 0.5, tuck_front=0.15,
               grooves=0 if hair == "curly" else 36, groove_amp=0.00035, curls=mess, NU=26 if hair != "cap" else 22, NV=6 if hair != "cap" else 5, top_extra=0.0004)
    if hair == "fringe":
        hc = C.parts[-1]["cage"]
        drop_faces(hc, lambda c: c.y > top_of(head_u(C, c)))
        # a short round beard (one region with the hair)
        top = [(0.00, L["mouth"] - 0.085 * H), (0.035, L["mouth"] - 0.07 * H), (0.07, L["mouth"] + 0.0 * H),
               (0.10, L["nose"] - 0.06 * H), (0.15, L["nose"] - 0.01 * H), (0.20, L["eye"] - 0.16 * H), (0.245, L["eye"] - 0.04 * H)]
        bot = [(0.00, L["chin"] - 0.10 * H), (0.06, L["chin"] - 0.095 * H), (0.12, L["chin"] - 0.06 * H),
               (0.17, L["chin"] + 0.02 * H), (0.21, L["mouth"] - 0.04 * H), (0.245, L["nose"] - 0.06 * H)]

        def bthick(uu, y, v):
            t = lerp(0.0044, 0.0030, smoothstep(0.05, 0.24, uu)) * S * smoothstep(0.0, 0.20, v)
            if uu < 0.06 and y > L["mouth"] - 0.10 * H:
                t *= 0.35
            return t + 0.0005 * S

        def bcurls(u, y):
            return 0.0006 * S * math.cos(2 * math.pi * u * 24) * math.cos(2 * math.pi * (y - L["chin"]) / (0.005 * S))
        build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.10 * H, reg="hair", NU=17, NV=8)
        moustache(C, "moustache", L["mouth"] + 0.092 * H, 0.58 * s["hw"], 0.05 * H, 0.0, 0.0018 * S, reg="hair", off=0.0016)
        C.parts[-1]["piece_as"] = "beard"
    if hair == "curly":                            # head band (red) with a short hanging tail on band1
        cg = Cage(); wfn = C.w(["head"])
        NPB = 40; path = []
        for i in range(NPB):
            u = i / NPB; uu = mirror_u(u)
            y = lerp(cb - 0.030 * H, L["eye"] + 0.16 * H, smoothstep(0.0, 0.5, uu) ** 0.9)
            ph, n = hair_pt(C, u, y, 0.0016 * S)
            ps = C.head.at(u, y) + C.head.normal(u, y) * 0.0032 * S
            path.append(ps.lerp(ph, smoothstep(0.06, 0.16, uu)))
        twisted_ring(cg, path, 0.0034 * S, 0.0016 * S, wfn, "band", 0, N=8, twist=0.0, ref=V(0, 1, 0))
        kp, kn = hair_pt(C, 0.5, L["eye"] + 0.16 * H, 0.0034 * S)
        blob(cg, kp, 0.0042 * S, 0.0036 * S, 0.0024 * S, wfn, "band", 0, NU=10, NV=5)
        C.B["band1"] = (kp.copy(), kp + V(0.004 * S, -0.032 * S, -0.008 * S), "head")
        wt = C.w(["band1"], blend=0.006 * S)

        def wtail(p):
            t = smoothstep(kp.y - 0.003 * S, kp.y - 0.010 * S, p.y)
            return mixw(({"head": 1.0}, 1 - t), (wt(p), t)) if t > 0 else {"head": 1.0}
        for sd, ln in ((1, 0.034), (-1, 0.026)):
            pp, nn = [], []
            for t in [j / 6 for j in range(7)]:
                p = kp + V(sd * (0.002 + 0.006 * t) * S, -ln * S * t, -(0.003 + 0.008 * t * t) * S)
                pp.append(p); nn.append(V(0, 0, -1))
            strip(cg, pp, nn, [(0.0030 - 0.0006 * t) * S for t in [j / 6 for j in range(7)]], 0.0008 * S, wtail, "band", 0)
        C.add("band", cg, subdiv=0)
    if hair == "cap":                              # pointed cap (a soft felt cone, tip bent back)
        cg = Cage(); wfn = C.w(["head"])
        by = cb - 0.06 * H
        prof = [(-0.0060 * S, 1.06), (0.0, 1.10), (0.006 * S, 1.06), (0.014 * S, 0.92), (0.022 * S, 0.74),
                (0.030 * S, 0.54), (0.037 * S, 0.34), (0.042 * S, 0.17), (0.0445 * S, 0.0)]
        info = head_lathe(C, by, prof, 18, wfn, "cap", 0, cg, extra_x=0.0036 * S, extra_f=0.0030 * S,
                          extra_b=0.0040 * S, tilt=math.radians(16))
        C.add("cap", cg, subdiv=1)
    # ---- knee-length tunic, sleeves to mid upper arm, bare forearms
    hemT = 0.100 * k
    RT = cut_rows(scale_rows(KING_ROBE, k, k * bx), hemT)
    if fs["belly"]:
        yb = wy - 0.016 * S
        RT = [(y, hw * (1 + 0.04 * math.exp(-((y - chestY) / 0.025) ** 2)) + 0.0060 * S * math.exp(-((y - yb) / 0.034) ** 2),
               zf + 0.0200 * S * math.exp(-((y - yb) / 0.040) ** 2),
               zb - 0.0030 * S * math.exp(-((y - yb) / 0.034) ** 2)) for y, hw, zf, zb in RT]
    sleeve_t = [(0.004, 0.0126 * min(1.15, bx)), (0.014, 0.0124 * min(1.15, bx)), (0.026, 0.0120 * min(1.15, bx)),
                (0.036, 0.0118 * min(1.15, bx))]
    build_robe(C, RT, sleeve_t, None, nf=10, fold_amp=0.0012, sleeve_fold=0.0005, reg="tunic", name="tunic", N=30,
               step=0.0072)
    C.tunic_rows = C.robe_rows
    cg = Cage()
    for side in "LR":
        cuff_ring(C, side, 0.034, 0.0120 * min(1.15, bx), cg, "tunic", th=(0.0018, 0.0014), n=20)
    C.add("cuffs", cg, subdiv=0, piece_as="tunic")
    for side in "LR":
        bare_arm(C, side, 0.024, 0.050, 0.0100 * min(1.2, bx))
        build_forearm_hand(C, side, 0.002)
    bare_knees(C, hemT)
    # ---- tan belt (one wrap) with a hanging end (belt1)
    bw = wy - 0.012 * S
    wrap_band(C, "beltA", "belt", bw - 0.0080 * S, bw + 0.0080 * S, 0.0014, 0.0012, 0.0006, 1.4, phase=0.8, NA=40)
    hanging_end(C, "beltEnd", "belt", (0.0120 if ch in ("friend1", "friend3") else -0.0120) * S, bw - 0.002 * S,
                bw - 0.050 * S, 0.0040, "belt1", off=0.0036)
    C.parts[-1]["piece_as"] = "belt"
    C.parts[-2]["piece_as"] = "belt"


BUILDERS = {"jesus": build_jesus, "peter": build_peter, "man": build_man}
BUILDERS.update({f: build_friend for f in FRIENDS})


# =============================================================================================== Blender assembly
PIECES = []           # global piece id -> (char, part, piece); index 0 = background
REGIONS = []          # global region id -> "char.region"
PART_TRIS = {}
REST_BAKE = {}


def finish_uv1_and_jaw(C, ch, o, pt, sheet):
    """UV1 (decal): front projection of the face rect (front-facing parts flagged decal); fixed-colour regions point at
    their swatch. The jaw weights of the face / beard, as Ruth / Jonah."""
    me = o.data
    dec = C.F["rect"]
    vco = [to_design(o.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    vn = [to_design(o.matrix_world.to_3x3() @ v.normal).normalized() for v in me.vertices]
    if not me.uv_layers.get("UVMap"):                 # page UV must be layer 0 (TEXCOORD_0), decal layer 1
        me.uv_layers.new(name="UVMap")
    uv1 = me.uv_layers.get("decal") or me.uv_layers.new(name="decal")
    rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
    sw = SWATCHES.get(ch, {})
    for poly, r in zip(me.polygons, rid):
        reg = REGIONS[r - 1].split(".")[1]
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index; p = vco[vi]; n = vn[vi]
            if reg in sw:                                     # fixed-colour region (sandals, rope, poles, ropes)
                uv = swatch_uv(ch, reg)
            elif pt.get("decal"):
                du = (p.x - dec[0]) / (dec[2] - dec[0]); dv = (p.y - dec[1]) / (dec[3] - dec[1])
                if p.z < 0.0 or n.z < 0.3:
                    if abs(dv - 0.5) > 0.45:
                        dv = 4.0 if dv > 0.5 else -3.0
                    else:
                        du = 4.0 if du > 0.5 else -3.0
                elif in_swatch(ch, du, dv):
                    du, dv = -3.0, -3.0
                uv = (du, dv)
            else:
                uv = (-1.0, -1.0)
            uv1.data[li].uv = uv
    L = C.L; H = C.H; S = C.S
    if pt.get("jaw") and not pt.get("rigid"):
        band = 0.0045 * S; mouthY = L["mouth"]; chin = L["chin"]
        gj = o.vertex_groups.get("jaw") or o.vertex_groups.new(name="jaw")
        gidx = {g.index: g for g in o.vertex_groups}
        zmin = pt.get("jawZ", -0.25 * 0.044 * S)
        for i, p in enumerate(vco):
            wj = smoothstep(mouthY + band * 0.5, mouthY - band, p.y) * smoothstep(zmin, 0.1 * 0.044 * S, p.z) \
                * smoothstep(chin - pt.get("jawBelow", 0.20) * H, chin + 0.02 * H, p.y)
            if wj <= 0:
                continue
            v = me.vertices[i]
            for ge in list(v.groups):
                gidx[ge.group].add([i], ge.weight * (1 - wj), 'REPLACE')
            gj.add([i], wj, 'ADD')


def mat_sheet_pose(on):
    """The man's mat: stood up to face the viewer at mat_sheet() (its top = the printed shape) for the ID render and
    the UV0 projection; back flat at the rest place (CONTRACT §3) for the GLB."""
    o = bpy.data.objects.get("man_mat")
    if o is None:
        return
    sX, sY = SHEET["man"]
    if on:
        mx, my = mat_sheet()
        yc = (MAT["top"] + MAT["bot"]) / 2
        R = Matrix.Rotation(math.radians(90), 4, 'X')
        o.matrix_world = Matrix.Translation(to_bl(V(mx, my, 0.12))) @ R @ Matrix.Translation(-to_bl(V(0, yc, MAT["cz"])))
    else:
        o.matrix_world = Matrix.Translation((sX, 0, sY))
    bpy.context.view_layer.update()


def build_character(ch):
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
        if pt["name"] == "face":
            face_obj = o
    lid = dict(name="eyelids", cage=eyelid_cage(C, face_obj, sheet), rigid="eyelids", subdiv=0, piece_as="face")
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
    for b in bone_list(ch):                      # every deforming contract bone has a vertex group
        if not bodyo.vertex_groups.get(b) and b not in PROPS[ch] and b != "eyelids":
            bodyo.vertex_groups.new(name=b)
    if ch == "man":
        mat_sheet_pose(True)
    vis = [bodyo] + [o for o in props if not is_hidden_prop(o)]
    stats = front_uv_with_occlusion([(o, o is not bodyo) for o in vis], sheet, ART_H, INSET,
                                    anchors=None, region_name=lambda r: REGIONS[r - 1].split(".")[1])
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
                bb = d["bb"]; bb[0] = min(bb[0], p.x); bb[1] = min(bb[1], p.y); bb[2] = max(bb[2], p.x); bb[3] = max(bb[3], p.y)
    return C, rig, bodyo, props, rep


def id_render(stem, hide_props=True):
    """Front ortho ID render of everything in the scene (2x art rect, no AA): one colour per (piece, region); eyelids
    and hidden props hidden. Writes $MI_WORK/<stem>.png/.json and returns the id table."""
    setup_workbench((2000, round(2000 * ART_H)))
    s = sc(); s.render.film_transparent = True; s.display.render_aa = 'OFF'
    s.display.shading.light = 'FLAT'; s.display.shading.color_type = 'MATERIAL'
    front_ortho_camera()
    idmap = {}

    def mat_fn(k):
        if k not in idmap:
            idmap[k] = len(idmap) + 1
        n = idmap[k]
        return flat_mat(f"id_{n}", [c / 255 for c in id_colour(n)])
    for o in all_meshes():
        o.hide_render = o.name.endswith("_eyelids") or (hide_props and is_hidden_prop(o))
        set_face_materials(o, lambda p, r: (p, r), mat_fn)
    render(os.path.join(WORK, stem + ".png"))
    ids = []
    for (p, r), n in sorted(idmap.items(), key=lambda kv: kv[1]):
        ch, pname, k = PIECES[p - 1]; rch, reg = REGIONS[r - 1].split(".")
        ids.append({"id": n, "rgb": id_colour(n), "char": ch, "part": pname, "piece": k, "region": reg,
                    "hex": PALETTE[ch].get(reg, "#cccccc")})
    json.dump({"note": "front-ortho ID render of the rest pose at sheet positions (2000 px = art width); background = "
                       "alpha 0; eyelids and hidden props hidden; the man's mat is stood up to face the viewer at its "
                       "own printed place (matSheet)", "size": [s.render.resolution_x, s.render.resolution_y], "ids": ids},
              open(os.path.join(WORK, stem + ".json"), "w"), indent=1)
    for o in all_meshes():
        o.hide_render = False
    return ids


# =============================================================================================== modes
def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    report = {"chars": {}, "sheet": {ch: SHEET[ch] for ch in ONLY}, "sheetSource": SHEET_SRC, "artHeight": ART_H,
              "matSheet": list(mat_sheet())}
    built = {}
    for ch in ONLY:
        C, rig, body, props, rep = build_character(ch)
        built[ch] = (C, rig, body, props, rep)
        tris = tri_count([body] + props)
        report["chars"][ch] = {"tris": tris, "bodyTris": tri_count([body]),
                               "props": {o.name: [o.parent_bone, tri_count([o])] for o in props},
                               "bones": [b.name for b in rig.data.bones], "uvStats": rep["uvStats"]}
        print(f"[{ch}] tris={tris} body={tri_count([body])} props={[(o.name, tri_count([o])) for o in props]}")
    ids = id_render("id_2x")
    anchor_info = apply_pixel_anchors(os.path.join(WORK, "id_2x.png"), ids)
    fix_info = fix_uvs_by_id(os.path.join(WORK, "id_2x.png"), ids)
    report["uvFixByIdRender"] = fix_info
    # ---- regions_characters.json
    ms = mat_sheet()
    regions_out = {"version": 1, "generatedBy": "pipeline/mi_characters.py",
                   "note": "Per character: colourable regions (face attribute st_region), the mesh parts that carry "
                           "them, demo colour, bbox on the sheet (x, y in art units, y up from the art rect bottom), "
                           "and anchors (regions too small to colour, or with a fixed colour, take a constant UV inside "
                           "a larger region and print as detail lines). The man's mat prints as its own shape (its top, "
                           "stood up to face the viewer) at matSheet. ID render for the line art: id_characters_2x.png"
                           "/.json (same scheme as Ruth / Jonah). The four friends are not printed (offSheet).",
                   "sheet": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in ONLY},
                   "sheetSource": SHEET_SRC, "artHeightUnits": ART_H, "characters": {}}
    for ch in ONLY:
        C, rig, body, props, rep = built[ch]
        regs = {}
        allbb = [9, 9, -9, -9]
        for reg, d in rep["regions"].items():
            bb = [round(v, 4) for v in d["bb"]]
            figure = not (ch == "man" and reg in ("mat", "stripes", "poles"))
            if bb[0] < 9 and reg not in SWATCHES.get(ch, {}) and figure:
                allbb = [min(allbb[0], bb[0]), min(allbb[1], bb[1]), max(allbb[2], bb[2]), max(allbb[3], bb[3])]
            zh, en = REGION_NAMES.get(reg, (reg, reg))
            regs[reg] = {"id": REGIONS.index(f"{ch}.{reg}") + 1, "hex": PALETTE[ch].get(reg), "zh": zh, "en": en,
                         "parts": sorted(d["parts"]), "bboxSheet": bb if bb[0] < 9 else None}
            if reg in SWATCHES.get(ch, {}):
                regs[reg]["fixedColour"] = True
            ai = anchor_info.get(ch, {})
            if reg in ai.get("anchors", {}):
                an = ai["anchors"][reg]
                regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
                regs[reg]["printNote"] = ("fixed colour from the face decal (UV1 swatch); print as detail lines, "
                                          "not a colouring region" if regs[reg].get("fixedColour") else
                                          "too small to colour; print as detail line art, takes the colour at anchorUV")
            if reg in ai.get("propAnchors", {}):
                an = ai["propAnchors"][reg]
                regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
                regs[reg]["printNote"] = ("hidden-by-default prop, not printed with the figure; takes the colour at "
                                          "anchorUV (override: design.json characters.%s.propUV.%s = [u, v])" % (ch, reg))
        entry = {
            "height": CONTRACT_HEIGHT[ch], "bboxSheet": [round(v, 4) for v in allbb], "regions": regs,
            "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                          "projection": "front",
                          "swatches": {k: [round(x, 3) for x in v] for k, v in SWATCHES.get(ch, {}).items()},
                          "files": {e: os.path.relpath(face_file(ch, e), ROOT) for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z"},
            "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                      for b, v in PROPS[ch].items()},
            "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
        if ch == "man":
            mb = [9, 9, -9, -9]
            for reg in ("mat", "stripes", "poles"):
                bb = regs.get(reg, {}).get("bboxSheet")
                if bb:
                    mb = [min(mb[0], bb[0]), min(mb[1], bb[1]), max(mb[2], bb[2]), max(mb[3], bb[3])]
            entry["matSheet"] = {"centre": [round(ms[0], 4), round(ms[1], 4)], "bboxSheet": [round(v, 4) for v in mb],
                                 "note": "the mat's printed shape: its top seen from above (long axis along page X, "
                                         "the side toward the viewer at the bottom), poles as detail lines; override "
                                         "the place with design.json characters.man.matSheet = [x, y]",
                                 "restPlacement": {"centre": [0.0, 0.0, MAT["cz"]], "padSize": [0.30, 0.12],
                                                   "polesToX": MAT["pole_x"], "top": MAT["top"]}}
        regions_out["characters"][ch] = entry
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
    if set(CHARS) <= set(ONLY):
        shutil.copy(os.path.join(WORK, "id_2x.png"), os.path.join(MODEL, "id_characters_2x.png"))
        shutil.copy(os.path.join(WORK, "id_2x.json"), os.path.join(MODEL, "id_characters_2x.json"))
    mat_sheet_pose(False)                          # the mat back flat at its rest place for the GLB
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
        if ch == "man":
            bpy.data.objects["man_mat"].matrix_world = Matrix.Identity(4); bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        for o in rig.children: o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"), use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=False, export_def_bones=False,
                                  export_texcoords=True, export_materials='EXPORT', export_morph=False)
        rig.location = (SHEET[ch][0], 0, SHEET[ch][1])
        if ch == "man":
            bpy.context.view_layer.update(); mat_sheet_pose(False)
    bpy.context.view_layer.update()
    report["partTris"] = PART_TRIS
    json.dump(report, open(os.path.join(WORK, "build_report.json"), "w"), indent=1, default=str)
    sc()["mi_regions"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({ch: {k: v for k, v in r.items() if k != "bones"} for ch, r in report["chars"].items()}))
    if os.environ.get("MI_NO_FRIENDS") != "1":
        import subprocess
        subprocess.run([bpy.app.binary_path, "-b", "--factory-startup", "--python", os.path.abspath(__file__), "--",
                        "friends"], check=True)


# =============================================================================================== the friends (fixed paint)
def friend_paint_material():
    """mi_friend_paint: Principled BSDF with model/friend_paint.png on UV0 (embedded in the friend GLBs)."""
    m = bpy.data.materials.get("mi_friend_paint") or bpy.data.materials.new("mi_friend_paint")
    m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.8
    img = bpy.data.images.load(FRIEND_PAINT, check_existing=True)
    t = nt.nodes.get("paint") or nt.nodes.new("ShaderNodeTexImage"); t.name = "paint"; t.image = img
    uvn = nt.nodes.get("uv0") or nt.nodes.new("ShaderNodeUVMap"); uvn.name = "uv0"; uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


def make_friend_paint(id_png, ids, margin=12):
    """model/friend_paint.png from the friends' front ID render: every (piece, region) flat in its demo colour with a
    little crayon grain, colours grown 12 px into the paper, cropped to the figures (Esther's make_guard_paint).
    Returns the crop (x0, y0, w, h, W, H) in ID-render pixels (rows from the bottom) for the UV remap."""
    import numpy as np
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(img)
    key = np.round(px[..., :3] * 255).astype(np.int64)
    key = key[..., 0] * 65536 + key[..., 1] * 256 + key[..., 2]
    alpha = px[..., 3] > 0.5
    col = np.zeros((H, W, 3), np.float32); have = np.zeros((H, W), bool)
    for e in ids:
        m = (key == e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2]) & alpha
        col[m] = [int(e["hex"].lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)]; have |= m
    rng = np.random.default_rng(7)
    g = rng.normal(0, 1, (H // 4 + 1, W // 4 + 1)).astype(np.float32)
    g = np.repeat(np.repeat(g, 4, 0), 4, 1)[:H, :W]
    col *= (1.0 + 0.025 * g)[..., None]
    for _ in range(margin):
        grow = ~have
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(np.roll(have, dy, 0), dx, 1) & grow
            c2 = np.roll(np.roll(col, dy, 0), dx, 1)
            col[src] = c2[src]; have |= src; grow &= ~src
    ys, xs = np.nonzero(alpha)
    x0, x1 = max(0, xs.min() - margin), min(W, xs.max() + margin + 1)
    y0, y1 = max(0, ys.min() - margin), min(H, ys.max() + margin + 1)
    crop = np.clip(col[y0:y1, x0:x1], 0, 1)
    out = np.ones((y1 - y0, x1 - x0, 4), np.float32); out[..., :3] = crop
    im = bpy.data.images.new("friend_paint", x1 - x0, y1 - y0, alpha=True)
    im.pixels.foreach_set(out.ravel())
    im.filepath_raw = FRIEND_PAINT; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)
    return (int(x0), int(y0), int(x1 - x0), int(y1 - y0), W, H)


def region_texels(id_png, ids):
    """Friends: every face of a (character, region) samples ONE texel, the deepest pixel of that region in the front ID
    render (the paint is flat per region, so this never bleeds across thin bands such as cuffs and belts)."""
    import numpy as np
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    bpy.data.images.remove(img)
    rgb = np.round(px[..., :3] * 255).astype(np.int64)
    key = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    alpha = px[..., 3] > 0.5
    uvs = {}
    for ch in ONLY:
        for reg in sorted({e["region"] for e in ids if e["char"] == ch}):
            keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids if e["char"] == ch and e["region"] == reg]
            m = np.isin(key, keys) & alpha
            last = m
            while m.any():
                last = m; e = m.copy()
                e[1:, :] &= m[:-1, :]; e[:-1, :] &= m[1:, :]; e[:, 1:] &= m[:, :-1]; e[:, :-1] &= m[:, 1:]
                m = e
            ys, xs = np.nonzero(last)
            if len(xs) == 0:
                continue
            k = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
            uvs[(ch, reg)] = ((xs[k] + 0.5) / W, (ys[k] + 0.5) / H)
    n = 0; missing = set()
    for o in all_meshes():
        ch = o.name.split("_")[0]
        me = o.data; rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
        uv0 = me.uv_layers["UVMap"]
        for poly, r in zip(me.polygons, rr):
            uv = uvs.get((ch, REGIONS[r - 1].split(".")[1]))
            if uv is None:
                missing.add(REGIONS[r - 1]); continue
            for li in poly.loop_indices:
                uv0.data[li].uv = uv
            n += 1
    return {"texels": {f"{c}.{r}": [round(u, 4), round(v, 4)] for (c, r), (u, v) in uvs.items()}, "faces": n,
            "regionsNotSeen": sorted(missing)}


def mode_friends():
    """friend1..friend4: built on a virtual page (FRIEND_PAGE), front ID render -> painted texture
    model/friend_paint.png, UV0 remapped into that texture, GLBs model/friend1..4.glb, then appended to characters.blend
    (rigs at FRIEND_BLEND, off the page) for the Animation role."""
    global ONLY
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ONLY = list(FRIENDS)
    SHEET.update({f: list(FRIEND_PAGE[f]) for f in FRIENDS})
    built = {}
    for ch in FRIENDS:
        C, rig, body, props, rep = build_character(ch)
        built[ch] = (C, rig, body, props)
        print(f"[{ch}] tris={tri_count([body] + props)} body={tri_count([body])}")
    ids = id_render("friend_id_2x")
    idp = os.path.join(WORK, "friend_id_2x.png")
    tex = region_texels(idp, ids)
    x0, y0, cw, chh, W, H = make_friend_paint(idp, ids)
    for o in all_meshes():                                     # UV0: ID-render space -> the cropped paint texture
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
    for ch in FRIENDS:
        C, rig, body, props = built[ch]
        rig.location = (0, 0, 0); bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT'); rig.select_set(True)
        for o in rig.children: o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        bpy.ops.export_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"), use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=False, export_def_bones=False,
                                  export_texcoords=True, export_materials='EXPORT', export_morph=False,
                                  export_image_format='AUTO')
        rig.location = (FRIEND_BLEND[ch][0], 0, FRIEND_BLEND[ch][1])
        info[ch] = {"height": CONTRACT_HEIGHT[ch], "paint": "assets/miracles/model/friend_paint.png", "uv0": "paint texture",
                    "look": {"friend1": "the leader: slim, orange tunic, short black hair",
                             "friend2": "big and round, teal tunic, bald with a fringe, short beard",
                             "friend3": "small and quick, yellow tunic, curly hair, red head band (band1)",
                             "friend4": "lanky, purple-blue tunic, red pointed cap"}[ch],
                    "blendRigLocation": list(FRIEND_BLEND[ch]),
                    "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                                  "files": {e: os.path.relpath(face_file(ch, e), ROOT) for e in EXPRESSIONS[ch]},
                                  "clipExpression": CLIP_EXPRESSION[ch],
                                  "note": "one shared drawing per expression for all four friends"},
                    "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                              "closed": C.lid["closedScale"]},
                    "colours": PALETTE[ch], "tris": tri_count([body] + props)}
    bpy.context.view_layer.update()
    tmp = os.path.join(WORK, "friends.blend")
    sc()["mi_regions_friends"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=tmp, compress=True)
    rp = os.path.join(MODEL, "regions_characters.json")
    if os.path.exists(rp):
        rj = json.load(open(rp)); rj["offSheet"] = info
        rj["offSheetNote"] = ("the four friends: not printed; UV0 samples model/friend_paint.png (fixed demo-palette "
                              "paint, one flat colour per region), face decal on UV1 like the cast")
        json.dump(rj, open(rp, "w"), indent=1, ensure_ascii=False)
    if os.path.exists(BLEND):
        bpy.ops.wm.open_mainfile(filepath=BLEND)
        for o in [o for o in bpy.data.objects if o.name.startswith(tuple(f + "_" for f in FRIENDS))]:
            bpy.data.objects.remove(o, do_unlink=True)
        with bpy.data.libraries.load(tmp, link=False) as (src, dst):
            dst.objects = [n for n in src.objects if n.startswith(tuple(f + "_" for f in FRIENDS))]
        for o in dst.objects:
            sc().collection.objects.link(o)
        sc()["mi_regions_friends"] = json.dumps(REGIONS)
        for im in bpy.data.images:                               # no absolute paths in the shared blend
            if os.path.basename(im.filepath) == "friend_paint.png":
                im.filepath = "//friend_paint.png"
                try:
                    im.pack()
                except Exception:                              # noqa: BLE001
                    pass
        bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True, relative_remap=True)
    try:
        os.remove(tmp)
    except OSError:
        pass
    print("FRIENDS_REPORT", json.dumps({ch: {"tris": v["tris"]} for ch, v in info.items()}), json.dumps(tex["regionsNotSeen"]))
    json.dump(PART_TRIS, open(os.path.join(WORK, "friend_parts.json"), "w"), indent=1)


# =============================================================================================== previews
GOLD = set()


class _RegionLookup(dict):
    def __missing__(self, r):
        tab = json.loads(sc().get("mi_regions", "[]"))
        for i, k in enumerate(tab):
            self[i + 1] = k.split(".")[1]
        return dict.__getitem__(self, r)


REGION_OF = _RegionLookup()


def friend_preview_material(ch, decal_img):
    """Preview: the friend paint texture on UV0 + the face decal on UV1 (node `decal`, swapped per expression)."""
    m = bpy.data.materials.new(f"pv_{ch}_paint"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.7
    try:
        b.inputs["Sheen Weight"].default_value = 0.2
    except Exception:                                          # noqa: BLE001
        pass
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = bpy.data.images.load(FRIEND_PAINT, check_existing=True)
    u0 = nt.nodes.new("ShaderNodeUVMap"); u0.uv_map = "UVMap"; nt.links.new(u0.outputs["UV"], t.inputs["Vector"])
    u1 = nt.nodes.new("ShaderNodeUVMap"); u1.uv_map = "decal"
    d = nt.nodes.new("ShaderNodeTexImage"); d.name = "decal"; d.image = decal_img; d.extension = 'CLIP'; d.interpolation = 'Cubic'
    nt.links.new(u1.outputs["UV"], d.inputs["Vector"])
    mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
    nt.links.new(d.outputs["Alpha"], mix.inputs["Factor"]); nt.links.new(t.outputs["Color"], mix.inputs[6])
    nt.links.new(d.outputs["Color"], mix.inputs[7]); nt.links.new(mix.outputs[2], b.inputs["Base Color"])
    return m


def char_frame(ch):
    L = landmarks(ch); Hh = CONTRACT_HEIGHT[ch]
    return Hh, (L["top"] + L["chin"]) / 2, L["top"] - L["chin"]


def preview_setup():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    setup_eevee((640, 960)); preview_lights()
    imgs = {}
    for ch in HUMANS:
        p = face_file(ch, DEFAULT_EXPR[ch])
        if os.path.exists(p):
            imgs[ch] = bpy.data.images.load(p, check_existing=True)
    present = [ch for ch in HUMANS if bpy.data.objects.get(f"{ch}_rig")]
    fmat = {f: friend_preview_material(f, imgs.get(f)) for f in FRIENDS if f in present}
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        if ch in FRIENDS:
            o.data.materials.clear(); o.data.materials.append(fmat[ch])
            o.data.polygons.foreach_set("material_index", [0] * len(o.data.polygons)); continue
        set_face_materials(o, lambda p, r: r, lambda r, ch=ch: preview_material(ch, REGION_OF[r], imgs.get(ch)))
    return imgs


def show(chs, props=False, mat=False):
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        hide = ch not in chs or (is_hidden_prop(o) and not props)
        if o.name == "man_mat" and not (mat or props):
            hide = True
        o.hide_render = hide


def set_decal(ch, img):
    for m in bpy.data.materials:
        if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
            m.node_tree.nodes["decal"].image = img


def mode_preview():
    imgs = preview_setup()
    present = [ch for ch in HUMANS if bpy.data.objects.get(f"{ch}_rig")]
    cam = camera()
    for ch in [c for c in list(ONLY) + list(FRIENDS) if c in present]:
        show([ch])
        rig = bpy.data.objects[f"{ch}_rig"]; x = rig.location.x; zb = rig.location.z
        Hh, hy0, Hd = char_frame(ch)
        hy = zb + hy0
        sc().render.resolution_x, sc().render.resolution_y = 640, 960
        for nm, yaw in (("front", 0), ("q34", 35), ("side", 90), ("back", 180)):
            turntable(cam, Vector((x, 0, zb + Hh * 0.50)), yaw, Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pv_{ch}_{nm}.png"))
        sc().render.resolution_x, sc().render.resolution_y = 640, 640
        if ch in CHARS:
            turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 30, Hd * 4.6, Hd * 0.25, 60); render(os.path.join(WORK, f"pv_{ch}_head.png"))
            turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 0, Hd * 4.6, Hd * 0.10, 60); render(os.path.join(WORK, f"pv_{ch}_headfront.png"))
            for s_ in "LR":
                pb = rig.pose.bones["fingers" + s_]; tgt = rig.matrix_world @ pb.head
                turntable(cam, tgt, 25 if s_ == "L" else -25, SPEC[ch]["hand"] * 4.6, SPEC[ch]["hand"] * 0.6, 60)
                render(os.path.join(WORK, f"pv_{ch}_hand{s_}.png"))
            show([ch], props=True)
            turntable(cam, Vector((x, 0, zb + Hh * 0.55)), 28, Hh * 2.4, Hh * 0.45, 60)
            render(os.path.join(WORK, f"pv_{ch}_props.png"))
            if ch == "man":                                  # the mat alone, flat at its rest place
                show([], mat=True)
                bpy.data.objects["man_mat"].hide_render = False
                turntable(cam, Vector((x, 0, zb + 0.01)), 20, 0.75, 0.42, 60)
                render(os.path.join(WORK, f"pv_{ch}_mat.png"))
            show([ch])
        sc().render.resolution_x, sc().render.resolution_y = 420, 420
        exprs = EXPRESSIONS[ch] if ch in CHARS or ch == "friend1" else [DEFAULT_EXPR[ch]]
        for e in exprs:
            set_decal(ch, bpy.data.images.load(face_file(ch, e), check_existing=True))
            turntable(cam, Vector((x, 0, hy - 0.08 * Hd)), 12, Hd * 3.6, Hd * 0.12, 60)
            render(os.path.join(WORK, f"pv_{ch}_expr_{e}.png"))
        set_decal(ch, imgs[ch])
    cast = [c for c in CHARS if c in present]
    if len(cast) > 1:
        show(cast, mat=True)
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1000
        turntable(cam, Vector((0.0, 0.03, 0.22)), 10, 1.6, 0.20, 50); render(os.path.join(WORK, "pv_all.png"))
        turntable(cam, Vector((0.0, 0.03, 0.16)), 18, 1.45, 1.10, 50); render(os.path.join(WORK, "pv_all_phone.png"))
    fr = [f for f in FRIENDS if f in present]
    if fr:
        show(fr)
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1000
        cx = sum(FRIEND_BLEND[f][0] for f in fr) / len(fr)
        turntable(cam, Vector((cx, 0.0, 0.19)), 0, 1.5, 0.16, 50); render(os.path.join(WORK, "pv_friends_line.png"))
        turntable(cam, Vector((cx, 0.0, 0.19)), 35, 1.5, 0.30, 50); render(os.path.join(WORK, "pv_friends_lineq.png"))
    print("PREVIEW done")


def pose_reset(rig):
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4); pb.scale = (1, 1, 1)
    bpy.context.view_layer.update()


def pose_test(rig, ch, variant="a"):
    pose_reset(rig)
    if variant == "none":
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
    if ch == "jesus":
        bend(rig, "mantle1", V(1, 0, 0), 22); bend(rig, "belt1", V(1, 0, 0), 30)
    if ch == "peter":
        bend(rig, "cloth1", V(1, 0, 0), -30)
    if ch == "man":
        bend(rig, "sash1", V(1, 0, 0), 30)
    if ch in FRIENDS:
        bend(rig, "belt1", V(1, 0, 0), 30)
    if ch == "friend3":
        bend(rig, "band1", V(1, 0, 0), -35)
    bpy.context.view_layer.update()


def design_rot_to_bl(cols):
    """A design-space rotation (images of design X, Y, Z) as a Blender 4x4 matrix."""
    P = Matrix(((1, 0, 0), (0, 0, -1), (0, 1, 0)))
    Md = Matrix((cols[0], cols[1], cols[2])).transposed()
    return (P @ Md @ P.inverted()).to_4x4()


def pose_lie(rig, lift=0.0):
    """The man lying on his back on the mat (a lie_mat test, not the clip): head toward -X, face up, head a little
    raised, hands on the chest; the mat bone stays at rest. The hips are settled so the lowest body point is 1 mm
    above the mat top. Returns the hips head place used (design, rig-local) and the lowest point."""
    pose_reset(rig)
    s = SPEC["man"]
    pb = rig.pose.bones["hips"]
    rest = pb.bone.matrix_local
    R = design_rot_to_bl((V(0, 0, -1), V(-1, 0, 0), V(0, 1, 0)))
    head = rest.translation.copy()
    B = {b.name: (to_design(b.head_local), to_design(b.tail_local)) for b in rig.data.bones}

    def apply(tgt):
        pb.matrix = Matrix.Translation(tgt) @ R @ Matrix.Translation(-head) @ rest
        bpy.context.view_layer.update()
        for side, sg in (("L", 1), ("R", -1)):          # arms down, forward, elbows bent: hands on the chest
            pbu = rig.pose.bones["upperArm" + side]
            restu = pbu.bone.matrix_local; hu = restu.translation.copy()
            Ra = Matrix.Rotation(math.radians(-40), 4, to_bl(V(1, 0, 0)).normalized()) @ \
                Matrix.Rotation(math.radians(-38 * sg), 4, to_bl(V(0, 0, 1)).normalized())
            pbu.matrix_basis = restu.inverted() @ Matrix.Translation(hu) @ Ra @ Matrix.Translation(-hu) @ restu
            h, t = B["forearm" + side]; d = (t - h).normalized()
            pbf = rig.pose.bones["forearm" + side]
            restf = pbf.bone.matrix_local; hf = restf.translation.copy()
            ax = to_bl(d.cross(V(0, 0, 1)) * sg * -1).normalized()
            pbf.matrix_basis = restf.inverted() @ Matrix.Translation(hf) @ Matrix.Rotation(math.radians(110), 4, ax) @ \
                Matrix.Translation(-hf) @ restf
        bend(rig, "neck", V(1, 0, 0), 14)
        bpy.context.view_layer.update()
        body = bpy.data.objects["man_body"]
        dg = bpy.context.evaluated_depsgraph_get()
        ev = body.evaluated_get(dg); me = ev.to_mesh()
        mw = body.matrix_world
        miny = min((mw @ v.co).z for v in me.vertices) - rig.matrix_world.translation.z
        ev.to_mesh_clear()
        return miny
    tgt = to_bl(V(0.17 - s["hipY"] + 0.020, MAT["top"] + 0.024 + lift, MAT["cz"]))
    for _ in range(2):
        miny = apply(tgt)
        tgt = tgt + Vector((0, 0, (MAT["top"] + 0.001 + lift) - miny))
    miny = apply(tgt)
    return {"hipsHead": [round(tgt.x, 4), round(tgt.z, 4), round(-tgt.y, 4)], "minY": round(miny, 4)}


C_LID_CLOSED = {}


def mode_posetest():
    imgs = preview_setup()
    cam = camera()
    present = [ch for ch in HUMANS if bpy.data.objects.get(f"{ch}_rig")]
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
        for var in ("a", "b"):
            pose_test(rig, ch, var)
            sc().render.resolution_x, sc().render.resolution_y = 640, 960
            Hh = char_frame(ch)[0]
            yaw = 20 if var == "a" else 70
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), yaw, Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pose_{ch}_{var}.png"))
        sc().render.resolution_x, sc().render.resolution_y = 540, 540
        L = landmarks(ch); Hd = L["top"] - L["chin"]
        turntable(cam, Vector((rig.location.x, 0, rig.location.z + (L["top"] + L["chin"]) / 2)), 25, Hd * 4.2, Hd * 0.1, 60)
        render(os.path.join(WORK, f"pose_{ch}_closed.png"))
        pose_test(rig, ch, "none")
    if "man" in present:
        rig = bpy.data.objects["man_rig"]
        show(["man"], mat=True)
        info = pose_lie(rig)
        out["lie"] = info
        x = rig.location.x; zb = rig.location.z
        sc().render.resolution_x, sc().render.resolution_y = 960, 720
        for nm, yaw, dist, h in (("lie", 0, 0.95, 0.30), ("lieq", 40, 0.85, 0.35), ("liephone", 15, 1.0, 0.80)):
            turntable(cam, Vector((x, MAT["cz"] * -1, zb + 0.04)), yaw, dist, h, 50)
            render(os.path.join(WORK, f"pose_man_{nm}.png"))
        pose_reset(rig)
    json.dump(out, open(os.path.join(WORK, "posetest.json"), "w"), indent=1)
    print("POSETEST done", json.dumps(out))


def mode_uvcheck():
    """Models wearing $MI_WORK/uvproof.png (or $MI_UV_TEXTURE) through UV0: front ortho with the mat stood up as
    printed (must equal the sheet), 3/4 + back perspective, the mat lying flat from above and 3/4."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get(ENV + "UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        if o.name.split("_")[0] in FRIENDS:
            o.hide_render = True; continue
        o.data.materials.clear(); o.data.materials.append(m)
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    sc().view_settings.view_transform = 'Standard'
    cam = front_ortho_camera()
    mat_sheet_pose(True)
    bpy.data.objects["backdrop"].hide_render = True; bpy.data.objects["floor"].hide_render = True
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    mat_sheet_pose(False)
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = False
    bpy.data.objects["backdrop"].hide_render = False; bpy.data.objects["floor"].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc().render.resolution_x, sc().render.resolution_y = 1600, 900
    mo = bpy.data.objects["man_mat"]
    mo.hide_render = True
    for nm, yaw in (("q34", 30), ("back", 180)):
        turntable(cam, Vector((0.0, 0, 0.19)), yaw, 1.45, 0.16, 50)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    for o in all_meshes():
        if o.name not in ("floor", "backdrop"):
            o.hide_render = o.name != "man_mat"
    x = bpy.data.objects["man_rig"].location.x; zb = bpy.data.objects["man_rig"].location.z
    for nm, yaw, h in (("mat", 0, 0.75), ("matq", 35, 0.35)):
        turntable(cam, Vector((x, -MAT["cz"], zb + 0.01)), yaw, 0.65, h, 50)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    print("UVCHECK done")


EXTRA_PARENTS = {"mantle1": "chest", "belt1": "hips", "cloth1": "head", "bucket": "handR", "mat": "root",
                 "ropes": "mat", "matRoll": "chest", "sash1": "hips", "band1": "head"}


def mode_verify():
    out = {}
    for ch in HUMANS:
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
        bad_par = {b: parents.get(b) for b in EXTRA_BONES[ch] if parents.get(b) != EXTRA_PARENTS[b]}
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
            layer1_decal = (len(u1) > 0 and any(a.x < -0.5 for a in u1))
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
        if ch == "man":
            mo = [o for o in meshes if o.parent_bone == "mat"]
            if mo:
                mp = [(mo[0].matrix_world @ v.co) for v in mo[0].data.vertices]
                info["matRest"] = {"x": [round(min(p.x for p in mp), 4), round(max(p.x for p in mp), 4)],
                                   "z_design": [round(min(-p.y for p in mp), 4), round(max(-p.y for p in mp), 4)],
                                   "y": [round(min(p.z for p in mp), 4), round(max(p.z for p in mp), 4)]}
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps({c: {k: v for k, v in i.items() if k not in ("meshes", "parents")} for c, i in out.items()}))


if __name__ == "__main__":
    {"build": mode_build, "friends": mode_friends, "preview": mode_preview, "posetest": mode_posetest,
     "verify": mode_verify, "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), os.path.abspath(__file__), "all"],
                                                 check=True)}[MODE]()
