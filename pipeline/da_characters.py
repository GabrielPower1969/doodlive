"""Daniel (story pack #4): characters daniel, king, officer, lion, lion2 — meshes, rigs, weights, UVs, face decals,
previews, GLBs.

Contract: docs/daniel/CONTRACT.md §2-§3 (ids, sizes, sheet slots, bone names, props), look: docs/daniel/DESIGN.md,
notes: docs/daniel/RIG.md. Started as a copy of pipeline/ru_characters.py (Ruth, pack #3) and keeps its method for the
three humans: procedural quad cages (pipeline/story_mesh.py helpers), heads mapped from the D&G base head by
landmarks, box-modelled hands, face decals on UV1 + an `eyelids` blink, UV0 = front page projection with occlusion +
ID-render fixes. New for Daniel:
  * two quadruped lions (`lion` on the sheet, `lion2` the lioness with her own painted texture): chunky round body,
    plump legs and paws, a big scalloped mane in soft tufts (skinned to head / neck / `mane`), round ears, a cream
    muzzle (cheek puffs + chin on `jaw`), a rounded nose, an S-curved tail with a dark tuft; face decals on the front
    of the head (eyes, brows, mouth) + a blink by `eyelids`, like the humans;
  * the lion is printed in SIDE view (its left side, nose to -X on the page): UV0 = mirrored side projection (the
    right side samples the drawing of the left side, which a symmetric lion matches); faces that cannot be seen from
    the side take one clean texel of their own region (CONTRACT §2);
  * lion2 is built on a virtual page; her side ID render becomes model/lion2_paint.png (flat demo colours with a
    little crayon grain and soft shading) and her UV0 points into it (Esther guard precedent);
  * Daniel: tied-back hair with a ponytail (`hair1`), short beard, gold yoke collar, teal sash with a hanging end
    (`sash1 sash2`), over-sleeves; King Darius: round belly (`belly`), cape (`cape1 cape2`), tall crown-hat, curly
    beard, medallion, signet ring (`ring` prop, shown); the official: long face, pointy nose, goatee, twirled
    moustache, headband, striped hem, front hem bone `robe1`, curly-toed slippers, the law scroll (`scroll` prop,
    hidden by default).

Run (repo root):
  python3 pipeline/da_characters.py all                                           # everything below, in order
  python3 pipeline/da_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/da_characters.py -- build        # models, rig, GLBs, blend, ID render
  python3 pipeline/da_characters.py proof                                         # $DA_WORK/uvproof.png
  blender -b --factory-startup --python pipeline/da_characters.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/da_characters.py -- uvcheck      # models wearing uvproof.png
  blender -b --factory-startup --python pipeline/da_characters.py -- posetest     # bend / blink / jaw / cloth bones
  blender -b --factory-startup --python pipeline/da_characters.py -- verify       # re-import GLBs, check bones/budget
  python3 pipeline/da_characters.py compose                                       # preview_*.png contact sheets
Blender: $BLENDER, else `blender` on PATH, else /Applications/Blender.app. Intermediate renders go to $DA_WORK
(default /tmp/daniel_chars/work). DA_ONLY=lion (comma list) builds a subset (debug only; finish with a full build).
"""
import sys, os, json, math, random, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/daniel/model")
FACES = os.path.join(ROOT, "docs/daniel/design/faces")
WORK = os.environ.get("DA_WORK", "/tmp/daniel_chars/work")
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/daniel/design.json")
LION2_PAINT = os.path.join(MODEL, "lion2_paint.png")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("daniel", "king", "officer", "lion", "lion2")
HUMANS = ("daniel", "king", "officer")
LIONS = ("lion", "lion2")
ON_SHEET = ("daniel", "king", "officer", "lion")
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
LION_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw", "eyelids", "tail1", "tail2", "tail3", "tail4",
              "earL", "earR", "upperArmL", "forearmL", "pawL", "upperArmR", "forearmR", "pawR",
              "thighL", "shinL", "footL", "thighR", "shinR", "footR", "mane"]
EXTRA_BONES = {"daniel": ["hair1", "sash1", "sash2"],
               "king": ["cape1", "cape2", "belly", "ring"],
               "officer": ["robe1", "scroll"],
               "lion": [], "lion2": []}


def bone_list(ch):
    return (LION_BONES if ch in LIONS else CONTRACT_BONES) + EXTRA_BONES[ch]


PROPS = {"daniel": {}, "king": {"ring": True}, "officer": {"scroll": False}, "lion": {}, "lion2": {}}
CONTRACT_HEIGHT = {"daniel": 0.34, "king": 0.40, "officer": 0.35, "lion": 0.13, "lion2": 0.12}   # lions: shoulder
DEFAULT_SHEET = {"daniel": (-0.38, 0.015), "king": (-0.15, 0.015), "officer": (0.07, 0.015), "lion": (0.32, 0.015),
                 "lion2": (3.0, 0.015)}        # lion2: virtual page, never printed
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (as Esther / Ruth)

# ---------------------------------------------------------------------------------------------- palette (DESIGN.md)
PALETTE = {
    "daniel": {"skin": "#DDA67E", "hair": "#4A2E1F", "robe": "#F4EEDD", "collar": "#E2B33C", "sash": "#2F8F9D",
               "sandals": "#8A5A3B"},
    "king": {"skin": "#D9A27A", "beard": "#2A1E1A", "crown": "#6E4FA8", "crownBand": "#E8B84A", "robe": "#9E86C8",
             "cape": "#3B4F9A", "medallion": "#E8B84A", "belt": "#E8B84A", "shoes": "#7A4E2E", "ring": "#E8B84A"},
    "officer": {"skin": "#E2B48C", "beard": "#231A16", "headband": "#E8B84A", "robe": "#D9773A", "stripes": "#B83A2E",
                "sash": "#5E8F3E", "slippers": "#8E3B2A", "scroll": "#F3E9D2", "seal": "#B83A2E"},
    "lion": {"body": "#E2A94A", "mane": "#A8562A", "muzzle": "#F3E2B8", "tuft": "#5A3420", "nose": "#6B3A2A"},
    "lion2": {"body": "#D9B47A", "muzzle": "#F1E3C4", "tuft": "#8A5A3B", "nose": "#7A4A38"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发和胡子", "hair and beard"), "robe": ("长袍", "robe"),
    "collar": ("金领", "gold collar"), "sash": ("腰带", "sash"), "sandals": ("凉鞋", "sandals"),
    "beard": ("胡子", "beard"), "crown": ("王冠", "crown"), "crownBand": ("王冠金边", "crown band"),
    "cape": ("披风", "cape"), "medallion": ("胸前金章", "medallion"), "belt": ("金腰带", "belt"), "shoes": ("鞋", "shoes"),
    "ring": ("戒指", "signet ring"), "headband": ("头带", "headband"), "stripes": ("条纹", "stripes"),
    "slippers": ("尖头鞋", "curly slippers"), "scroll": ("卷轴", "scroll"), "seal": ("封印", "seal"),
    "body": ("身体", "body"), "mane": ("鬃毛", "mane"), "muzzle": ("嘴巴和肚皮", "muzzle and belly"),
    "tuft": ("尾巴尖", "tail tuft"), "nose": ("鼻子", "nose"),
}
# regions too small to colour on A4: constant UV deep inside a printed region ("char.region", or "char.FACE" = that
# character's face skin away from eyes / brows / nose / mouth); a region anchored to itself = its own widest spot
ANCHORS = {
    # Set + sheet role, 2026-11-14 (owner: regions under 6 mm on the A4 print are too hard for children to colour).
    # Each region below had no printed cell of 6 mm anywhere (best cell in brackets); it now prints as detail lines
    # inside its neighbour and wears a printed set region of the same or the nearest demo colour:
    "daniel": {"sandals": "set.wood",            # (no cell) house wood #8A5A3B = sandals #8A5A3B
               "sash": "set.rugBlue"},           # (2.0 mm) his prayer rug's blue
    "king": {"ring": "set.throne",               # gold of the throne (the king's gold, one colour)
             "medallion": "set.throne",          # (4.1 mm)
             "belt": "set.throne",               # (2.0 mm)
             "crownBand": "set.throne",          # (1.7 mm)
             "cape": "set.gateTile",             # (2.0 mm) the glazed gate's blue
             "shoes": "set.wood"},               # (1.7 mm)
    "officer": {"beard": "king.beard",           # (1.0 mm) near-black, as the king's beard
                "headband": "set.relief",        # (0.7 mm) the gate's gold
                "sash": "set.frond",             # (1.7 mm) palm green
                "stripes": "set.canopy",         # (1.7 mm) the palace canopy's red
                "slippers": "set.wood"},         # (2.4 mm)
    "lion": {"muzzle": "set.rugCream",           # (2.4 mm) cream
             "tuft": "set.wood",                 # (1.8 mm)
             "nose": "set.wood"},                # (0.8 mm)
    "lion2": {},
}
# hidden-by-default props are not printed: their regions sample a printed region of similar colour (first target
# that exists wins; "set.<region>" = a region of the set's printed drawings); design.json characters.<id>.propUV wins
PROP_ANCHORS = {
    "officer": {"scroll": ["set.scroll", "daniel.robe"], "seal": ["set.wax", "officer.stripes"]},
}
# parts whose printed area is a sliver: every face of (part, region) takes one UV inside a larger region
PART_ANCHORS = {ch: {("handL", "skin"): f"{ch}.FACE", ("handR", "skin"): f"{ch}.FACE",
                     ("legL", "skin"): f"{ch}.FACE", ("legR", "skin"): f"{ch}.FACE"} for ch in HUMANS}
# Set + sheet role, 2026-11-14: printed pieces with no colourable cell take their own region's widest spot
PART_ANCHORS.setdefault("lion", {}).update({("earL", "muzzle"): "set.rugCream", ("earR", "muzzle"): "set.rugCream",
                                            ("forelock", "mane"): "lion.mane"})

# ---------------------------------------------------------------------------------------------- proportions
FR = dict(mouth=0.163, nose=0.273, eye=0.490, brow=0.583)
_LEN = ("top", "chin", "hw", "zc", "noseH", "neckBase", "chestY", "waistY", "hipY", "hipX", "kneeY", "ankleY",
        "footLen", "upperArm", "forearm", "hand")


def scaled(base, k, kx=None, **over):
    """A SPEC entry scaled by k (lengths; kx for widths), then overridden."""
    kx = kx or k
    s = dict(base)
    for key in _LEN:
        s[key] = base[key] * (kx if key in ("hw", "hipX") else k)
    s["neck"] = tuple(v * kx for v in base["neck"])
    s["shoulder"] = (base["shoulder"][0] * kx, base["shoulder"][1] * k)
    s["handDims"] = {a: v * kx for a, v in base["handDims"].items()}
    s["k"] = k; s["kx"] = kx
    s.update(over)
    return s


KING = dict(height=0.40, top=0.354, chin=0.294, hw=0.0222, zc=-0.002, depth=1.06, jaw=0.10, cheek=0.04,
            chin_narrow=0.0, crown=0.0, noseH=0.0028, nose_w=1.12, nose_long=0.0, brow=1.15, lips=0.9,
            chinAmt=0.6, sockets=1.0, cheekbones=1.0,
            neckBase=0.273, neck=(0.0108, 0.0098, -0.0108), shoulder=(0.046, 0.266), chestY=0.246,
            waistY=0.218, hipY=0.190, hipX=0.0200, kneeY=0.100, ankleY=0.019, footLen=0.044, footScale=1.15,
            upperArm=0.066, forearm=0.056, hand=0.037, palmFrac=0.52,
            handDims=dict(palmW=0.0154, palmH=0.0064, wristW=0.0112, wristH=0.0078, fingerW=0.0039,
                          fingerT=0.0036, thumbW=0.0040, thumbT=0.0036, armR=0.0072))
HAMAN = dict(height=0.37, top=0.354, chin=0.297, hw=0.0188, zc=-0.001, depth=1.06, jaw=-0.02, cheek=-0.06,
             chin_narrow=0.22, crown=0.0, noseH=0.0016, nose_w=0.80, nose_long=0.05, brow=1.3, lips=0.7,
             chinAmt=1.2, sockets=1.1, cheekbones=1.25,
             neckBase=0.276, neck=(0.0086, 0.0080, -0.0088), shoulder=(0.039, 0.270), chestY=0.250,
             waistY=0.224, hipY=0.197, hipX=0.0175, kneeY=0.105, ankleY=0.019, footLen=0.042, footScale=1.1,
             upperArm=0.065, forearm=0.055, hand=0.035, palmFrac=0.52,
             handDims=dict(palmW=0.0140, palmH=0.0056, wristW=0.0100, wristH=0.0068, fingerW=0.0034,
                           fingerT=0.0032, thumbW=0.0035, thumbT=0.0032, armR=0.0062))
SPEC = {
    # a grown man about forty, Esther's height: the king's male build scaled down, a kind, even face
    "daniel": scaled(KING, 0.93, 0.90, height=0.34, depth=1.05, jaw=0.02, cheek=0.06, noseH=0.0024, nose_w=1.0,
                     brow=0.95, lips=0.95, chinAmt=0.7, fr=dict(eye=0.486, brow=0.580, nose=0.270, mouth=0.163)),
    # King Darius = Esther's king proportions (height 0.40, 0.44 with the crown-hat)
    "king": scaled(KING, 1.0, 1.0, height=0.40, fr=dict(eye=0.486, brow=0.580, nose=0.268, mouth=0.163)),
    # the official: Haman's long narrow face, thinner and a little shorter
    "officer": scaled(HAMAN, 0.946, 0.88, height=0.35, fr=dict(eye=0.500, brow=0.590, nose=0.285, mouth=0.170)),
}
FIST = set()                       # no fists at rest in this pack
FIST_BEND = {}


def landmarks(ch):
    s = SPEC[ch]; H = s["top"] - s["chin"]
    L = dict(top=s["top"], chin=s["chin"], zc=s["zc"], hw=s["hw"])
    for k, f in FR.items():
        L[k] = s["chin"] + s.get("fr", {}).get(k, f) * H
    return L


EYE = {"daniel": (0.405, 0.265, 0.180), "king": (0.400, 0.250, 0.165), "officer": (0.420, 0.270, 0.150)}

# ---------------------------------------------------------------------------------------------- lions
# Base lion (CONTRACT §2: shoulder 0.13, nose to rump 0.22, tail +0.10), facing +Z, paws on y = 0, root under the belly
# centre. lion2 (lioness: shoulder 0.12, nose to rump 0.21) = the same layout scaled (kx, ky, kz) with no mane.
LION_K = {"lion": (1.0, 1.0, 0.945), "lion2": (0.90, 0.923, 0.905)}
LION_HEAD = dict(c=(0.0, 0.150, 0.088), r=(0.031, 0.028, 0.027))
LION_EYE = dict(x=0.0128, y=0.1585, w=0.0078, h=0.0068)      # eye centre (x, y) and half width / height (base units)


def lion_face_layout(ch):
    kx, ky, kz = LION_K[ch]
    cx, cy, cz = LION_HEAD["c"]
    w = 0.074 * ky; x0 = -w / 2; y0 = cy * ky - 0.040 * ky
    rect = [x0, y0, x0 + w, y0 + w]

    def nx(x): return (x - x0) / w

    def ny(y): return (y - y0) / w
    ex, ey = LION_EYE["x"] * kx, LION_EYE["y"] * ky
    ew, eh = LION_EYE["w"] * ky, LION_EYE["h"] * ky
    return dict(rect=rect, eyeL=(nx(ex), ny(ey)), eyeR=(nx(-ex), ny(ey)), eyeHalf=(ew / w, eh / w),
                brow=ny(ey + 0.0105 * ky), mouth=ny(0.1325 * ky), nose=ny(0.1445 * ky),
                eyeLocal=(ex, ey, ew, eh), hwN=0.031 * kx / w)


def face_layout(ch):
    """Decal rectangle (character-local x0 y0 x1 y1) and eye / brow / mouth placement in normalised decal space
    (0..1, y up). Humans: square rect from just under the mouth, side max(1.76 hw, 0.72 H) (as Esther / Ruth)."""
    if ch in LIONS:
        return lion_face_layout(ch)
    s = SPEC[ch]; L = landmarks(ch); H = L["top"] - L["chin"]; hw = s["hw"]
    w = max(1.76 * hw, 0.72 * H); x0 = -w / 2; y0 = L["mouth"] - 0.14 * H
    rect = [x0, y0, x0 + w, y0 + w]

    def nx(x): return (x - x0) / w

    def ny(y): return (y - y0) / w
    ex, ew, eh = EYE[ch]
    eyeX = ex * hw
    return dict(rect=rect, eyeL=(nx(eyeX), ny(L["eye"])), eyeR=(nx(-eyeX), ny(L["eye"])),
                eyeHalf=(ew * hw / w, eh * hw / w), brow=ny(L["brow"]), mouth=ny(L["mouth"]), nose=ny(L["nose"]),
                eyeLocal=(eyeX, L["eye"], ew * hw, eh * hw), hwN=hw / w)


EXPRESSIONS = {"daniel": ["calm", "talk", "smile", "pray", "sure", "joy"],
               "king": ["smile", "talk", "proud", "worried", "sorry", "tired", "joy"],
               "officer": ["sulky", "talk", "sly", "flatter", "gleeful", "scared", "nervous"],
               "lion": ["curious", "sleepy", "fierce", "blissful", "yawn"],
               "lion2": ["curious", "sleepy", "fierce", "blissful", "yawn"]}
DEFAULT_EXPR = {"daniel": "calm", "king": "smile", "officer": "sulky", "lion": "curious", "lion2": "curious"}
_LION_CLIPS = {"idle": "curious", "sleep": "sleepy", "wake_up": "sleepy", "roar": "fierce", "growl": "fierce",
               "prowl": "fierce", "yawn": "yawn", "lie_down": "blissful", "roll_over": "blissful", "walk": "curious"}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "daniel": {"idle": "calm", "walk": "calm", "talk": "talk", "bow": "calm", "kneel_pray": "pray", "stand_up": "calm",
               "calm_nod": "sure", "pet_lion": "smile", "wave_up": "joy", "hug": "joy", "wave": "smile"},
    "king": {"idle": "smile", "walk_sad": "sorry", "talk": "talk", "talk_happy": "joy", "proud": "proud",
             "stamp": "proud", "worried": "worried", "pace": "worried", "head_in_hands": "sorry",
             "reach_out": "sorry", "toss_sigh": "tired", "run": "worried", "call_out": "worried", "joy_jump": "joy",
             "hug": "joy", "proclaim": "joy"},
    "officer": {"idle": "sulky", "walk": "sulky", "talk": "talk", "fold_arms": "sulky", "stomp_walk": "sulky",
                "grumble": "sulky", "sly_idea": "sly", "rub_hands": "gleeful", "bow_flatter": "flatter",
                "tiptoe": "sly", "peek": "sly", "point": "gleeful", "scared_jump": "scared", "run_away": "scared"},
    "lion": dict(_LION_CLIPS), "lion2": dict(_LION_CLIPS),
}


def sheet_positions():
    """sheetX / sheetY per character: assets/daniel/design.json characters.<id> when present (Set + sheet role),
    else the CONTRACT §2 slots (also written to model/characters_layout.json)."""
    out = {ch: list(DEFAULT_SHEET[ch]) for ch in CHARS}
    art_h = ART_H_DEFAULT; src = "defaults"; prop_uv = {}
    if os.path.exists(DESIGN_JSON):
        try:
            d = json.load(open(DESIGN_JSON))
            art_h = d.get("artHeightUnits", art_h)
            for ch in ON_SHEET:
                c = d.get("characters", {}).get(ch, {})
                if "sheetX" in c:
                    out[ch] = [c["sheetX"], c.get("sheetY", out[ch][1])]; src = "design.json"
                if c.get("propUV"):
                    prop_uv[ch] = c["propUV"]
        except Exception as e:                                   # noqa: BLE001
            print("design.json unreadable, using defaults:", e)
    return out, art_h, src, prop_uv
# =============================================================================================== face decals (PIL)
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
        h1 = ir * 0.36; hx, hy = ix + ir * 0.38, iy + ir * 0.42
        dl.ellipse((P(hx - h1, hy + h1)[0], P(hx - h1, hy + h1)[1], P(hx + h1, hy - h1)[0], P(hx + h1, hy - h1)[1]),
                   fill=(255, 255, 255, 255))
        h2 = ir * 0.15; hx, hy = ix - ir * 0.40, iy - ir * 0.42
        dl.ellipse((P(hx - h2, hy + h2)[0], P(hx - h2, hy + h2)[1], P(hx + h2, hy - h2)[0], P(hx + h2, hy - h2)[1]),
                   fill=(255, 255, 255, 230))
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

    def sweat(img, x, y, s):
        dr = ImageDraw.Draw(img)
        pts = [(x, y + s * 1.3), (x + s * 0.55, y), (x + s * 0.4, y - s * 0.45), (x, y - s * 0.6),
               (x - s * 0.4, y - s * 0.45), (x - s * 0.55, y)]
        poly(dr, pts, (170, 215, 250, 235))
        stroke(dr, pts + [pts[0]], 0.006, 0.006, col=(60, 110, 160, 255))

    def lion_mouth(img, kind, my, ny_, wd, col=(70, 38, 26, 255)):
        """Lion mouths under the (geometry) nose: a short philtrum line and a soft 'w'. kind: w | wide | small | o |
        roar. The roar is a big rounded open mouth with soft white bumps for teeth (no fangs) and a pink tongue."""
        dr = ImageDraw.Draw(img)
        top = ny_ - 0.040
        if kind == "roar":
            L, R = (0.5 - wd * 1.05, my + 0.010), (0.5 + wd * 1.05, my + 0.010)
            up = bez(L, (0.5 - wd * 0.6, my + 0.050), (0.5 + wd * 0.6, my + 0.050), R)
            lo = bez(R, (0.5 + wd * 1.05, my - 0.260), (0.5 - wd * 1.05, my - 0.260), L)
            shape = [P(*p) for p in up + lo]
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            dl.polygon(shape, fill=(118, 36, 42, 255))
            m = Image.new("L", img.size, 0); ImageDraw.Draw(m).polygon(shape, fill=255)
            inner = Image.new("RGBA", img.size, (0, 0, 0, 0)); di = ImageDraw.Draw(inner)
            ys = [p[1] for p in up + lo]; ytop, ybot = max(ys), min(ys)
            for k in range(5):                                   # top row: 5 soft round bumps
                cx = 0.5 + (k - 2) * wd * 0.40; r = wd * 0.21
                di.ellipse((P(cx - r, ytop + 0.01)[0], P(cx - r, ytop + 0.01)[1], P(cx + r, ytop - 0.022)[0],
                            P(cx + r, ytop - 0.022)[1]), fill=(255, 252, 244, 255))
            for k in range(4):                                   # bottom row: 4 bumps
                cx = 0.5 + (k - 1.5) * wd * 0.40; r = wd * 0.18
                di.ellipse((P(cx - r, ybot + 0.020)[0], P(cx - r, ybot + 0.020)[1], P(cx + r, ybot - 0.01)[0],
                            P(cx + r, ybot - 0.01)[1]), fill=(255, 252, 244, 255))
            tr = wd * 0.55
            di.ellipse((P(0.5 - tr, ybot + 0.085)[0], P(0.5 - tr, ybot + 0.085)[1], P(0.5 + tr, ybot + 0.015)[0],
                        P(0.5 + tr, ybot + 0.015)[1]), fill=(226, 112, 120, 255))
            lay.paste(inner, (0, 0), Image.composite(inner.split()[3], Image.new("L", img.size, 0), m))
            img.alpha_composite(lay)
            dr = ImageDraw.Draw(img)
            stroke(dr, up + lo + [up[0]], 0.016, 0.016, col=col)
            stroke(dr, [(0.5, top), (0.5, my + 0.048)], 0.016, 0.014, col=col)
            return
        if kind == "yawn":
            cy = my - 0.085; rx = wd * 0.78; ry = 0.115
            box = (P(0.5 - rx, cy + ry)[0], P(0.5 - rx, cy + ry)[1], P(0.5 + rx, cy - ry)[0], P(0.5 + rx, cy - ry)[1])
            lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
            dl.ellipse(box, fill=(118, 36, 42, 255))
            m = Image.new("L", img.size, 0); ImageDraw.Draw(m).ellipse(box, fill=255)
            inner = Image.new("RGBA", img.size, (0, 0, 0, 0)); di = ImageDraw.Draw(inner)
            tr = rx * 0.62
            di.ellipse((P(0.5 - tr, cy - ry * 0.35)[0], P(0.5 - tr, cy - ry * 0.35)[1], P(0.5 + tr, cy - ry * 1.1)[0],
                        P(0.5 + tr, cy - ry * 1.1)[1]), fill=(226, 112, 120, 255))
            for k in (-1, 1):                                    # two tiny soft top teeth
                cx = 0.5 + k * rx * 0.45; r = rx * 0.16
                di.ellipse((P(cx - r, cy + ry * 1.05)[0], P(cx - r, cy + ry * 1.05)[1], P(cx + r, cy + ry * 0.78)[0],
                            P(cx + r, cy + ry * 0.78)[1]), fill=(255, 252, 244, 255))
            lay.paste(inner, (0, 0), Image.composite(inner.split()[3], Image.new("L", img.size, 0), m))
            img.alpha_composite(lay)
            dr = ImageDraw.Draw(img)
            dr.ellipse(box, outline=col, width=int(0.014 * N))
            stroke(dr, [(0.5, top), (0.5, cy + ry)], 0.015, 0.014, col=col)
            return
        if kind == "o":
            r = wd * 0.32; cy = my - 0.040
            dr.ellipse((P(0.5 - r, cy + r * 1.1)[0], P(0.5 - r, cy + r * 1.1)[1], P(0.5 + r, cy - r * 1.1)[0],
                        P(0.5 + r, cy - r * 1.1)[1]), fill=(118, 36, 42, 255))
            stroke(dr, bez((0.5 - r, cy), (0.5 - r, cy + r * 1.5), (0.5 + r, cy + r * 1.5), (0.5 + r, cy)), 0.012, 0.012, col=col)
            stroke(dr, bez((0.5 + r, cy), (0.5 + r, cy - r * 1.5), (0.5 - r, cy - r * 1.5), (0.5 - r, cy)), 0.012, 0.012, col=col)
        lift, dip, w = {"w": (0.012, 0.030, 1.0), "wide": (0.040, 0.044, 1.25), "small": (0.004, 0.022, 0.75),
                        "o": (0.010, 0.026, 0.95)}[kind]
        stroke(dr, [(0.5, top), (0.5, my + 0.004)], 0.015, 0.014, col=col)
        for sx in (-1, 1):
            pts = bez((0.5, my + 0.004), (0.5 + sx * wd * 0.20 * w, my - dip), (0.5 + sx * wd * 0.75 * w, my - dip),
                      (0.5 + sx * wd * w, my + lift))
            stroke(dr, pts, 0.016, 0.011, wmid=0.017, col=col)

    def whiskers(img, my, col):
        dr = ImageDraw.Draw(img)
        for sx in (-1, 1):
            for dx, dy in ((0.070, 0.030), (0.092, 0.020), (0.080, 0.002)):
                x, y = 0.5 + sx * dx, my + dy; r = 0.0075
                dr.ellipse((P(x - r, y + r)[0], P(x - r, y + r)[1], P(x + r, y - r)[0], P(x + r, y - r)[1]), fill=col)

    made = {}
    for ch in CHARS:
        F = face_layout(ch)
        eL, eR, half, by, my, ny_ = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"], F["nose"]
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            if ch in LIONS:
                she = ch == "lion2"
                E = dict(look=(0, 0.05), top=1.0, bot=1.0, tilt=0.05, lash=2 if she else 0, mode="open", lid=0.12,
                         inner_up=0.0, pupil=0.52, wet=False)
                Bp = dict(raise_=0.070, inner=0.0, arch=0.40, thick=1.0, outer=0.0)
                Bl, Br = {}, {}
                M = dict(kind="w", wd=0.130); bl = 0
                if ex == "curious":
                    E.update(top=1.12, bot=1.05, pupil=0.56, look=(0.25, 0.25)); M.update(kind="o")
                    Bl = dict(raise_=0.100, arch=0.62); Br = dict(raise_=0.070, arch=0.40)
                elif ex == "sleepy":
                    E.update(top=0.42, bot=0.95, lid=0.36, look=(0, -0.35), tilt=-0.10)
                    Bp.update(raise_=0.050, inner=0.012, arch=0.20, outer=-0.030); M.update(kind="small", wd=0.110)
                elif ex == "fierce":
                    E.update(top=0.86, bot=0.92, tilt=0.40, pupil=0.40, lid=0.20)
                    Bp.update(raise_=0.044, inner=-0.040, arch=0.06, thick=1.25, outer=0.012)
                    M.update(kind="roar", wd=0.165)
                elif ex == "blissful":
                    E.update(mode="happy"); Bp.update(raise_=0.084, arch=0.52); M.update(kind="wide", wd=0.140)
                    bl = 150
                elif ex == "yawn":                       # eyes squeezed shut, big round sleepy open mouth
                    E.update(mode="closed", lid=0.30); Bp.update(raise_=0.098, inner=0.020, arch=0.58)
                    M.update(kind="yawn", wd=0.120); bl = 60
                iris = (226, 156, 46) if not she else (196, 150, 70)
                bcol = (92, 52, 28, 255) if not she else (132, 92, 58, 255)
                if bl:
                    blush(img, 0.27, my + 0.055, 0.075, 0.042, bl)
                for side, c in ((1, eL), (-1, eR)):
                    eye(img, c, half, side=side, iris=iris, line=0.024, **E)
                dr = ImageDraw.Draw(img)
                for side, c in ((1, eL), (-1, eR)):
                    b = dict(Bp); b.update(Bl if side == 1 else Br)
                    brow(dr, side, (c[0], by), half, w=0.050 if not she else 0.040, col=bcol, length=0.95, **b)
                whiskers(img, my, (110, 70, 44, 210))
                lion_mouth(img, M["kind"], my, ny_, M["wd"])
            else:
                hwN = F["hwN"]
                bcol = {"daniel": (60, 38, 26, 255), "king": (36, 25, 21, 255), "officer": (35, 26, 22, 255)}[ch]
                iris = {"daniel": (100, 64, 36), "king": (82, 52, 30), "officer": (74, 52, 32)}[ch]
                bw = {"daniel": 0.034, "king": 0.054, "officer": 0.028}[ch]
                E = dict(look=(0, 0), top=1.0, bot=1.0, tilt=0.15, lash=0, mode="open", lid=0.10, inner_up=0.0,
                         pupil=0.55, wet=False)
                El, Er = {}, {}
                Bp = dict(raise_=0.0, inner=0.0, arch=0.35, thick=1.0, outer=0.0)
                Bl, Br = {}, {}
                M = dict(kind="flat", wd=0.095, jaw=0.0, side=0.0)
                lipcol = None; rim = None; bl = 0; crow = 0; folds = 0.0; bags = False; crs = True; drop_ = False
                if ch == "daniel":
                    E.update(lid=0.14, top=0.90, bot=0.88, tilt=0.08, pupil=0.55); M["wd"] = 0.086
                    lipcol = (176, 104, 88, 220); rim = (222, 164, 136, 235)
                    Bp.update(raise_=0.064, arch=0.18, thick=1.0); bl = 35; crow = 1
                    if ex == "calm":
                        E.update(top=0.86, look=(0.05, 0.0)); M.update(kind="soft", wd=0.084)
                    elif ex == "talk":
                        M.update(kind="open", wd=0.080, jaw=0.07); Bp.update(raise_=0.068, arch=0.22)
                    elif ex == "smile":
                        E.update(top=0.78, bot=0.72); Bp.update(raise_=0.076, arch=0.28); M.update(kind="smile", wd=0.090)
                        crow = 3
                    elif ex == "pray":
                        E.update(mode="closed"); Bp.update(inner=0.010, raise_=0.064, arch=0.14)
                        M.update(kind="soft", wd=0.072); crs = False; crow = 0
                    elif ex == "sure":
                        E.update(top=0.90, tilt=0.05, look=(0, 0.05)); Bp.update(inner=-0.012, raise_=0.060, arch=0.12, thick=1.08)
                        M.update(kind="small", wd=0.086)
                    elif ex == "joy":
                        E.update(mode="happy"); Bp.update(raise_=0.088, arch=0.36); M.update(kind="grin", wd=0.098, jaw=0.10)
                        bl = 70; crow = 3
                elif ch == "king":
                    E.update(lid=0.22, top=0.86, bot=0.86, tilt=0.06, pupil=0.54); M["wd"] = 0.092
                    lipcol = (176, 98, 84, 220); rim = (214, 150, 132, 235)
                    Bp.update(raise_=0.066, arch=0.30, thick=1.0); bl = 45; crow = 2
                    if ex == "smile":
                        E.update(top=0.80, bot=0.70); Bp.update(raise_=0.070, arch=0.38); M.update(kind="smile", wd=0.092)
                        crow = 3
                    elif ex == "talk":
                        M.update(kind="open", wd=0.086, jaw=0.08); Bp.update(raise_=0.072, arch=0.34)
                    elif ex == "proud":
                        E.update(top=0.48, bot=0.80, look=(0, -0.15), lid=0.32); Bp.update(raise_=0.086, arch=0.46, outer=0.010)
                        M.update(kind="soft", wd=0.084); crow = 2
                    elif ex == "worried":
                        E.update(top=1.06, bot=1.0, pupil=0.44, look=(0, -0.2), tilt=-0.06)
                        Bp.update(inner=0.050, raise_=0.088, arch=0.06, outer=-0.030); M.update(kind="wobbly", wd=0.074, jaw=0.02)
                    elif ex == "sorry":
                        E.update(top=0.84, look=(0, -0.45), tilt=-0.14, wet=True)
                        Bp.update(inner=0.054, raise_=0.090, arch=0.04, outer=-0.036); M.update(kind="frown", wd=0.074)
                        bl = 70
                    elif ex == "tired":
                        E.update(top=0.50, bot=0.90, lid=0.34, look=(0, -0.25), tilt=-0.12)
                        Bp.update(inner=0.022, raise_=0.060, arch=0.08, outer=-0.032); M.update(kind="flat", wd=0.070)
                        bags = True; crow = 0
                    elif ex == "joy":
                        E.update(mode="happy"); Bp.update(raise_=0.094, arch=0.56); M.update(kind="grin", wd=0.106, jaw=0.14)
                        bl = 80; crow = 3
                else:   # officer
                    E.update(lid=0.20, top=0.74, bot=0.80, tilt=0.22, pupil=0.58); M["wd"] = 0.080
                    lipcol = (170, 96, 90, 190); rim = (226, 170, 140, 200)
                    Bp.update(raise_=0.062, arch=0.48, thick=0.9, outer=0.006); bl = 30
                    if ex == "sulky":
                        E.update(top=0.62, bot=0.80, look=(-0.35, -0.25)); Bp.update(inner=0.026, raise_=0.060, arch=0.08, outer=-0.014)
                        M.update(kind="frown", wd=0.072)
                    elif ex == "talk":
                        E.update(top=0.72); M.update(kind="open", wd=0.074, jaw=0.06)
                    elif ex == "sly":
                        E.update(top=0.56, bot=0.72, look=(0.75, 0.0)); Er = dict(top=0.30, bot=0.62)
                        Bl = dict(raise_=0.096, arch=0.70); Br = dict(raise_=0.048, inner=-0.022, arch=0.10)
                        M.update(kind="smirk", wd=0.092, side=1)
                    elif ex == "flatter":
                        E.update(mode="happy"); Bp.update(raise_=0.094, arch=0.62, inner=0.010)
                        M.update(kind="grin", wd=0.108, jaw=0.03); bl = 70
                    elif ex == "gleeful":
                        E.update(top=0.62, bot=0.58, look=(0.45, 0.0)); Bp.update(inner=-0.028, raise_=0.072, arch=0.30)
                        M.update(kind="grin", wd=0.102, jaw=0.10)
                    elif ex == "scared":
                        E.update(top=1.40, bot=1.25, pupil=0.30, lid=0.06, tilt=0.0); Bp.update(raise_=0.126, arch=0.50, inner=0.024, outer=0.0)
                        M.update(kind="shout", wd=0.088, jaw=0.32); drop_ = True
                    elif ex == "nervous":
                        E.update(top=1.0, pupil=0.42, look=(-0.65, 0.1), tilt=0.05)
                        Bp.update(inner=0.042, raise_=0.090, arch=0.10, outer=-0.020); M.update(kind="wobbly", wd=0.074, jaw=0.03)
                        drop_ = True
                # ---- draw
                if bl:
                    blush(img, 0.32, ny_ - 0.035, 0.088, 0.046, bl)
                nose_hint(img, ny_ + 0.006, 0.034 if ch != "officer" else 0.028,
                          strength={"daniel": 1.0, "king": 1.1, "officer": 0.9}[ch])
                for side, c in ((1, eL), (-1, eR)):
                    e_ = dict(E); e_.update(El if side == 1 else Er)
                    eye(img, c, half, side=side, iris=iris, line=0.020, **e_)
                    if crs and e_["mode"] == "open":
                        crease(img, c, half, side, lift=1.50, col=(140, 90, 72, 120))
                    if bags and e_["mode"] == "open":
                        under_eye(img, c, half, side, col=(120, 80, 90, 170), drop=1.25)
                        under_eye(img, c, half, side, col=(120, 80, 90, 120), drop=1.55)
                    if crow:
                        crows(img, c, half, side, n=crow, ln=1.0 if e_["mode"] == "open" else 1.2, col=(130, 80, 62, 130))
                dr = ImageDraw.Draw(img)
                for side, c in ((1, eL), (-1, eR)):
                    b = dict(Bp); b.update(Bl if side == 1 else Br)
                    brow(dr, side, (c[0], by - 0.015), half, w=bw, col=bcol, **b)
                if rim and M["kind"] in ("open", "grin", "o", "shout", "wobbly"):
                    rim_mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, M["jaw"], rim)
                elif rim:                           # closed mouth on a beard: a light lip patch under the line
                    rx, ry = M["wd"] * 1.45, M["wd"] * 0.50
                    soft(img, lambda d: d.ellipse((P(0.5 - rx, my + ry * 0.7)[0], P(0.5 - rx, my + ry * 0.7)[1],
                                                   P(0.5 + rx, my - ry * 1.3)[0], P(0.5 + rx, my - ry * 1.3)[1]),
                                                  fill=rim), 0.004)
                mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, lipcol=lipcol, jaw=M["jaw"], side=M["side"])
                if drop_:
                    sweat(img, eL[0] + half[0] * 1.9, eL[1] + half[1] * 2.6, 0.030)
            out = img.resize((PX, PX), Image.LANCZOS)
            path = os.path.join(FACES, f"{ch}_{ex}.png")
            out.save(path); made[f"{ch}_{ex}"] = os.path.relpath(path, ROOT)
    # overview sheet: every expression over a skin swatch, plus a 64 px "phone distance" row (LESSONS L42)
    cells = [(ch, ex) for ch in CHARS for ex in EXPRESSIONS[ch]]
    cols = 8; cw = 256
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (cw + 24) + rows * 88), (250, 246, 238))
    dr = ImageDraw.Draw(sheet)
    for i, (ch, ex) in enumerate(cells):
        x, y = (i % cols) * cw, (i // cols) * (cw + 24 + 88)
        base = PALETTE[ch].get("skin") or PALETTE[ch]["body"]
        bg = Image.new("RGBA", (cw, cw), tuple(int(base[k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        fc = Image.open(os.path.join(FACES, f"{ch}_{ex}.png")).resize((cw, cw), Image.LANCZOS)
        bg.alpha_composite(fc); sheet.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 8, y + cw + 4), f"{ch}_{ex}", fill=(40, 30, 20))
        small = bg.resize((64, 64), Image.LANCZOS)
        sheet.paste(small.convert("RGB"), (x + 8, y + cw + 22))
    sheet.save(os.path.join(FACES, "overview.png"))
    print("faces:", len(made), "->", FACES)
    return made
def compose():
    """Contact sheets model/preview_<char>.png, preview_all.png, preview_uvcheck.png, preview_pose.png from the
    $DA_WORK renders."""
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

    def stack(parts, name):
        W = max(p.width for p in parts)
        im = Image.new("RGB", (W, sum(p.height for p in parts)), bg)
        y = 0
        for p in parts:
            im.paste(p, (0, y)); y += p.height
        im.save(os.path.join(MODEL, name))
    for ch in CHARS:
        exprs = [os.path.join(WORK, f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]]
        ex = grid(exprs, EXPRESSIONS[ch], 7, (300, 300), "face decals on the model (UV1)")
        if ch in LIONS:
            views = [("front", "front"), ("q34", "3/4"), ("side", "side (left)"), ("back", "back"),
                     ("phone", "phone angle"), ("phoneSide", "phone angle, side")]
            top = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in views], [lb for _, lb in views], 3, (640, 480),
                       f"{ch}: rest pose, demo colours{' (own paint)' if ch == 'lion2' else ''} + default face decal")
            det = [("headfront", "face front"), ("head", "face 3/4"), ("legs", "paws")]
            bot = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det], [lb for _, lb in det], 3, (420, 420), "close-ups")
        else:
            views = [("front", "front"), ("q34", "3/4"), ("side", "side"), ("back", "back")]
            top = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in views], [lb for _, lb in views], 4, (480, 720),
                       f"{ch}: rest pose, demo palette + default face decal")
            det = [("head", "face 3/4"), ("headfront", "face front"), ("handL", "left hand"), ("handR", "right hand"),
                   ("props", "props shown (rest pose)")]
            bot = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det], [lb for _, lb in det], 5, (384, 384), "close-ups")
        stack([top, bot, ex], f"preview_{ch}.png")
    if os.path.exists(os.path.join(WORK, "pv_all.png")):
        stack([grid([os.path.join(WORK, "pv_all.png"), os.path.join(WORK, "pv_all_phone.png")],
                    ["the cast at their sheet slots (lion2 placed beside the lion)", "phone-like high angle"], 1,
                    (1600, 1000), "Daniel cast")], "preview_all.png")
    uv = [os.path.join(WORK, f) for f in ("uvproof.png", "uv_front.png", "uv_q34.png", "uv_back.png")]
    if all(os.path.exists(f) for f in uv):
        top_a = Image.open(uv[0]).convert("RGB"); top_b = Image.open(uv[1]).convert("RGBA")
        bgw = Image.new("RGBA", top_b.size, (255, 255, 255, 255)); bgw.alpha_composite(top_b); top_b = bgw.convert("RGB")
        crop = (0, 760, 1000, top_a.height)
        r1 = [top_a.crop(crop), top_b.crop(crop)]
        r2 = [Image.open(uv[2]).convert("RGB").resize((1000, 562)), Image.open(uv[3]).convert("RGB").resize((1000, 562))]
        lions = [os.path.join(WORK, f"uv_{n}.png") for n in ("lionL", "lionR", "lionTop", "lionFront")]
        r3 = [Image.open(f).convert("RGB").resize((500, 350)) for f in lions if os.path.exists(f)]
        h1 = r1[0].height
        im = Image.new("RGB", (2000, 34 + h1 + 26 + 562 + 26 + 376), bg); d = ImageDraw.Draw(im)
        d.text((10, 10), "UV0 proof: a perfectly coloured sheet (ID render in demo colours, left) worn by the models "
                         "(front ortho with the lion turned to its side = the sheet; 3/4, back and the lion's right side "
                         "/ top keep each region's colour)", fill=(40, 30, 20))
        im.paste(r1[0], (0, 34)); im.paste(r1[1], (1000, 34))
        d.text((8, 34 + h1 + 6), "sheet (texture)", fill=(60, 50, 40)); d.text((1008, 34 + h1 + 6), "models, front ortho", fill=(60, 50, 40))
        im.paste(r2[0], (0, 34 + h1 + 26)); im.paste(r2[1], (1000, 34 + h1 + 26))
        y3 = 34 + h1 + 26 + 562 + 26
        for i, t in enumerate(r3):
            im.paste(t, (i * 500, y3))
        d.text((8, y3 - 18), "3/4 and back   |   lion: left side, right side (mirrored drawing), top, front",
               fill=(60, 50, 40))
        im.save(os.path.join(MODEL, "preview_uvcheck.png"))
    pf, lb = [], []
    for ch in CHARS:
        for var in (("a", "b") if ch in LIONS else ("a",)):
            for v in ("front", "side", "close", "closed"):
                f = os.path.join(WORK, f"pose_{ch}_{var}_{v}.png")
                if v == "close":
                    f = os.path.join(WORK, f"pose_{ch}_roar_close.png") if var == "a" else ""
                if v == "closed":
                    f = os.path.join(WORK, f"pose_{ch}_closed_close.png") if var == "b" else ""
                if os.path.exists(f):
                    pf.append(f); lb.append(f"{ch} {var} {v}")
    if pf:
        grid(pf, lb, 6, (360, 400), "pose test: humans = elbows, finger curl, thigh + knee, spine, head turn, jaw, half "
             "blink, cloth bones; lions a = head up + jaw open + paw lifted + tail + ears + mane, b = sitting").save(
            os.path.join(MODEL, "preview_pose.png"))
    print("composed previews ->", MODEL)


def proof():
    """$RU_WORK/uvproof.png: the ID render with every (piece, region) in its demo colour and a thin dark outline,
    i.e. a perfectly coloured sheet; uvcheck renders the models wearing it through UV0."""
    from PIL import Image, ImageFilter
    import numpy as np
    meta = json.load(open(os.path.join(MODEL, "id_characters_2x.json")))
    im = np.array(Image.open(os.path.join(MODEL, "id_characters_2x.png")).convert("RGBA"))
    out = np.zeros(im.shape[:2] + (3,), np.uint8); out[:] = (250, 248, 242)
    key = im[..., 0].astype(int) * 65536 + im[..., 1].astype(int) * 256 + im[..., 2]
    for e in meta["ids"]:
        r, g, b = e["rgb"]; h = e["hex"].lstrip("#")
        m = (key == r * 65536 + g * 256 + b) & (im[..., 3] > 0)
        out[m] = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
    edge = Image.fromarray(key.astype(np.int32).astype(np.uint8)).filter(ImageFilter.FIND_EDGES)
    e = np.array(edge) > 0
    e = np.array(Image.fromarray((e * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    out[e] = (60, 45, 35)
    Image.fromarray(out).resize((1000, round(1000 * ART_H_DEFAULT)), Image.LANCZOS).save(os.path.join(WORK, "uvproof.png"))
    Image.fromarray(out).save(os.path.join(WORK, "uvproof_2x.png"))
    print("proof ->", os.path.join(WORK, "uvproof.png"))


if not IN_BLENDER:
    if __name__ == "__main__":
        mode = sys.argv[1] if len(sys.argv) > 1 else "faces"
        def run_all():
            import subprocess
            bl = os.environ.get("BLENDER") or shutil.which("blender") or "/Applications/Blender.app/Contents/MacOS/Blender"
            me = os.path.abspath(__file__)
            draw_faces()
            for m in ("build",):
                subprocess.run([bl, "-b", "--factory-startup", "--python", me, "--", m], check=True, stdout=subprocess.DEVNULL)
            proof()
            for m in ("preview", "uvcheck", "posetest", "verify"):
                subprocess.run([bl, "-b", "--factory-startup", "--python", me, "--", m], check=True, stdout=subprocess.DEVNULL)
            compose()
            v = json.load(open(os.path.join(WORK, "verify.json")))
            for ch, i in v.items():
                print(ch, "bonesMatch", i["bonesMatch"], "actions", i["actions"], "tris", i["tris"],
                      "uvOrderOK", i.get("uvOrderOK"), "top", i["heightTop"],
                      {k: i[k] for k in ("noseToRump", "withers", "tailBackZ") if k in i})
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
ONLY = [c for c in os.environ.get("DA_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()


# =============================================================================================== context + skeleton
class Ctx:
    def __init__(self, ch):
        self.ch = ch; self.F = face_layout(ch)
        if ch in LIONS:                       # lions: no human landmarks; S = 1, blend in art units
            self.s = {}; self.L = None; self.H = None; self.S = 1.0; self.blend = 0.008
        else:
            self.s = SPEC[ch]; self.L = landmarks(ch)
            self.H = self.L["top"] - self.L["chin"]; self.S = self.s.get("S", self.s["height"] / 0.30)
            self.blend = 0.006 * self.S
        self.parts = []; self.B = {}; self.hand = {}
        self.decal_zmin = 0.0; self.lid_part = "face"; self.lid_reg = "skin"

    def w(self, spec, blend=None):
        spec = [(s, None) if isinstance(s, str) else s for s in spec]
        B, bl = self.B, blend or self.blend
        return lambda p: weigh(p, spec, B, bl)

    def add(self, name, cg, **kw):
        self.parts.append(dict(name=name, cage=cg, **kw))


def arm_frames(C, side):
    """Shoulder, elbow, wrist, knuckles and the hand frame for one side (rest pose)."""
    s = C.s; sd = 1 if side == "L" else -1
    a = math.radians(ARM_DEG)
    S0 = V(sd * s["shoulder"][0], s["shoulder"][1], 0)
    d = V(sd * math.cos(a), -math.sin(a), 0)
    E = S0 + d * s["upperArm"]; W = E + d * s["forearm"]
    fist = (C.ch, side) in FIST
    if fist:                                    # wrist cocked: hand points out nearly level, holds the sceptre upright
        b = math.radians(FIST_BEND.get((C.ch, side), 26.0))
        dh = V(sd * math.cos(b), -math.sin(b), 0)
        Np = V(0, 0, 1)                         # palm toward the viewer, thumb on top, knuckles back
    else:
        dh = d.copy()
        pin = -V(-dh.y, dh.x, 0) * sd           # palm toward the body / down
        Np = rot_about(pin, dh, math.radians(28))
        if Np.z > 0:
            Np = rot_about(pin, dh, math.radians(-28))
    Lh = s["hand"]; K = W + dh * (Lh * s["palmFrac"])
    Xh = -Np; Yh = dh.cross(Xh).normalized()
    thumb = (dh.cross(Np) if side == "R" else Np.cross(dh)).normalized()
    return dict(S0=S0, d=d, E=E, W=W, K=K, dh=dh, Np=Np, Xh=Xh, Yh=Yh, thumb=thumb, fist=fist, sd=sd)


def skeleton(C):
    s = C.s; L = C.L; H = C.H; S = C.S; B = {}
    nb = s["neckBase"]; headBase = L["chin"] + 0.247 * H
    B["root"] = (V(0, 0, 0), V(0, 0.03 * S, 0), None)
    B["hips"] = (V(0, s["hipY"], 0), V(0, s["waistY"], 0), "root")
    B["spine"] = (V(0, s["waistY"], 0), V(0, s["chestY"], 0), "hips")
    B["chest"] = (V(0, s["chestY"], 0), V(0, nb, 0), "spine")
    B["neck"] = (V(0, nb, 0), V(0, headBase, 0), "chest")
    B["head"] = (V(0, headBase, 0), V(0, L["top"], 0), "neck")
    chinZ = L["zc"] + 0.0195 * s["hw"] / 0.0199
    B["jaw"] = (V(0, L["chin"] + 0.287 * H, L["zc"] - 0.0013 * S), V(0, L["chin"] + 0.03 * H, chinZ), "head")
    for side in "LR":
        A = arm_frames(C, side); sd = A["sd"]
        B["shoulder" + side] = (V(sd * 0.22 * s["shoulder"][0], nb - 0.0027 * S, 0), A["S0"].copy(), "chest")
        B["upperArm" + side] = (A["S0"].copy(), A["E"].copy(), "shoulder" + side)
        B["forearm" + side] = (A["E"].copy(), A["W"].copy(), "upperArm" + side)
        B["hand" + side] = (A["W"].copy(), A["K"].copy(), "forearm" + side)
        B["fingers" + side] = (A["K"].copy(), A["K"] + A["dh"] * (s["hand"] * (1 - s["palmFrac"])), "hand" + side)
        x = sd * s["hipX"]; xk = x * 1.08
        B["thigh" + side] = (V(x, s["hipY"], 0), V(xk, s["kneeY"], 0), "hips")
        B["shin" + side] = (V(xk, s["kneeY"], 0), V(xk, s["ankleY"], -0.001), "thigh" + side)
        B["foot" + side] = (V(xk, s["ankleY"], -0.001), V(xk, 0.004 * S, 0.62 * s["footLen"]), "shin" + side)
        B["toe" + side] = (V(xk, 0.004 * S, 0.62 * s["footLen"]), V(xk, 0.0032 * S, 0.95 * s["footLen"]), "foot" + side)
    ex, ey, ew, eh = C.F["eyeLocal"]
    zf = L["zc"] + 0.020 * s["hw"] / 0.0199
    C.lid = dict(top=ey + 1.30 * eh, h0=0.18 * eh, closed=ey - 1.0 * eh)
    B["eyelids"] = (V(0, C.lid["top"], zf), V(0, C.lid["top"] - 0.010 * S, zf), "head")
    C.B = B
    C.arm = {sd: arm_frames(C, sd) for sd in "LR"}


# =============================================================================================== head
def neck_rows(C):
    s = C.s; L = C.L; hx, zf, zb = s["neck"]; nb = s["neckBase"]; S = C.S
    return [ellipse_row(L["chin"] - 0.0045 * S, hx, zf, zb), ellipse_row(L["chin"] - 0.0095 * S, hx * 1.02, zf * 1.02, zb * 1.02),
            ellipse_row(nb + 0.0030 * S, hx * 1.12, zf * 1.06, zb * 1.10), ellipse_row(nb - 0.0020 * S, hx * 1.40, zf * 1.12, zb * 1.22),
            ellipse_row(nb - 0.0070 * S, hx * 1.75, zf * 1.18, zb * 1.30)]


def build_head(C, cull, ears=None):
    s = C.s; L = C.L; H = C.H
    rows = mapped_head_rows(L, s["hw"], s["depth"], s["jaw"], s["cheek"], s["chin_narrow"], s["crown"])
    C.head = HeadEval(rows, L)
    rows = rows + neck_rows(C)
    us = front_dense(26, 0.45)
    cg = Cage()
    ytf, ytb = L["chin"] - 0.002, L["chin"] + 0.33 * H

    def wfn(p):
        zf_ = 0.4 * s["hw"]; zb_ = -0.4 * s["hw"]
        ys = lerp(ytb, ytf, smoothstep(zb_, zf_, p.z))
        wh = smoothstep(ys - 0.06 * H, ys + 0.06 * H, p.y)
        wn = weigh(p, [("chest", None), ("neck", None)], C.B, C.blend)
        return mixw(({"head": 1.0}, wh), (wn, 1 - wh))
    rings = [cg.ring(row_ring(r, us), wfn) for r in rows]
    cg.fan(rings[0], V(0, L["top"], L["zc"] - 0.0005 * C.S), wfn, "skin")
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin")
    last = rows[-1]
    cg.fan(rings[-1], V(0, last[0] - 0.004 * C.S, (last[1] + last[5]) / 2), wfn, "skin")
    post = face_post_fn(L, s["hw"], L["zc"], s["noseH"], 1.0, s["brow"], s["lips"], s["chinAmt"], s["nose_w"],
                        s["nose_long"], s["sockets"], s["cheekbones"])
    C.add("face", cg, decal=True, jaw=True, post=post, cull=cull)
    if ears:
        ey0, ey1, ew, et = ears
        for sx in (-1, 1):
            C.add("ear" + ("L" if sx > 0 else "R"),
                  ear_cage(C.head, L, sx, ey0, ey1, ew, et, C.w(["head"]), NA=10))


def head_u(C, p):
    return (math.atan2(p.x, p.z - C.L["zc"]) / (2 * math.pi)) % 1.0


def mirror_u(u):
    uu = u % 1.0
    return uu if uu <= 0.5 else 1.0 - uu


# =============================================================================================== hair shells
def hair_shell(C, rim, thick, name, reg, plumb=None, tuck_front=0.12, NU=40, NV=9, grooves=56, groove_amp=0.00026,
               parting=False, waves=0.0, curls=None, top_extra=0.0015, pc=0):
    """Hair shell over the skull. rim(u) = lower edge height; thick(u, y) = thickness; plumb(uu) in 0..1 = how much
    the hair below the widest level hangs straight down instead of hugging jaw / neck. The rim of the front part is
    tucked into the skin; elsewhere the edge gets a rolled inner lip (the hair has thickness)."""
    Hd = C.head; L = C.L; H = C.H
    yw = L["eye"]; Hc = V(0, L["eye"], L["zc"])
    cg = Cage(); wfn = C.w(["head"])

    def outer(u, y):
        yy = min(y, L["top"] - 0.0002)
        p = Hd.at(u, yy); n = Hd.normal(u, yy)
        q = p + n * thick(u, y)
        wp = plumb(mirror_u(u)) if plumb else 0.0
        if wp > 0 and y < yw:
            pw = Hd.at(u, yw) + Hd.normal(u, yw) * thick(u, yw)
            hq = V(q.x, 0, q.z - L["zc"]); rq = hq.length
            rw = V(pw.x, 0, pw.z - L["zc"]).length * (1 + 0.06 * (yw - y) / H)
            r = max(rq, lerp(rq, rw, wp))
            if rq > 1e-9:
                q = V(0, y, L["zc"]) + hq / rq * r
                q.y = y
        return q
    C.hair_outer = outer
    us = [k / NU for k in range(NU)]
    rows = []
    for j in range(-1, NV + 1):
        row = []
        for u in us:
            ry = rim(u); uu = mirror_u(u)
            if j == -1:                      # inner lip / tuck
                if uu < tuck_front:
                    p = Hd.at(u, ry + 0.0015) - Hd.normal(u, ry + 0.0015) * 0.0006
                else:
                    o = outer(u, ry); hn = V(o.x, 0, o.z - L["zc"]).normalized()
                    p = o - hn * thick(u, ry) * 0.85 + V(0, 0.0025 * C.S, 0)
                row.append(p); continue
            t = j / NV
            y = lerp(ry, L["top"] + top_extra, t ** 0.85)
            if j == 0 and uu < tuck_front:
                p = Hd.at(u, ry) + Hd.normal(u, ry) * 0.0002
            else:
                p = outer(u, y)
            row.append(p)
        rows.append(cg.ring(row, wfn))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(rows[-1], V(0, L["top"] + top_extra + 0.0004, L["zc"] - 0.001), wfn, reg, pc)

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            u = head_u(C, p); uu = mirror_u(u); ry = rim(u)
            fade = smoothstep(ry - 0.001, ry + 0.003, p.y)
            dirn = (p - Hc).normalized()
            g = groove_amp * math.cos(grooves * 2 * math.pi * u) * fade
            q = p + n * g
            if parting and p.z > L["zc"] and p.y > L["brow"]:
                q -= n * 0.0007 * math.exp(-(p.x / (0.0016 * C.S)) ** 2) * smoothstep(L["brow"] + 0.2 * H, L["brow"] + 0.35 * H, p.y)
            if waves and uu > 0.14:
                q += V(dirn.x, 0, dirn.z).normalized() * waves * math.sin((L["top"] - p.y) / H * 2 * math.pi * 2.3 + uu * 6) \
                    * smoothstep(L["eye"] + 0.1 * H, L["eye"] - 0.2 * H, p.y)
            if curls:
                q += n * curls(u, p.y) * fade
            out.append(q)
        return out
    C.add(name, cg, post=post, subdiv=1)


# =============================================================================================== hands
ARM12 = [math.radians(75 - 30 * k) for k in range(12)]


def build_forearm_hand(C, side, s_from):
    """Visible forearm (from inside the sleeve) + palm + 4 fingers (3 joints, from knuckle ports) + thumb (side port).
    Weights: forearm -> hand at the wrist; fingers by distance from their knuckle (hand -> fingers); thumb = hand."""
    A = C.arm[side]; s = C.s; hd = s["handDims"]
    d, dh, Xh, Yh, Np, W, K, E = A["d"], A["dh"], A["Xh"], A["Yh"], A["Np"], A["W"], A["K"], A["E"]
    Lh = s["hand"]; LHp = Lh * s["palmFrac"]; LF = s["forearm"]; fist = A["fist"]
    thumb_side0 = Yh.dot(A["thumb"]) > 0
    cg = Cage(); k12 = kcomp(12)
    X0 = perp(Xh, d); Y0 = d.cross(X0)
    warm = C.w(["forearm" + side, "hand" + side], blend=0.18 * Lh)
    rings = []
    stations = [s_from + (LF - s_from) * t for t in (0.0, 0.22, 0.45, 0.68, 0.88, 1.0)]
    for sv in stations:
        t = smoothstep(s_from, LF, sv)
        rx = lerp(hd["armR"], hd["wristH"] / 2, t ** 1.4); ry = lerp(hd["armR"] * 1.05, hd["wristW"] / 2, t ** 1.4)
        c = E + d * sv
        rings.append(cg.ring([section(c, X0, Y0, (rx * k12, rx * k12, ry * k12, ry * k12), a, 2.2) for a in ARM12], warm))
    cg.fan(rings[0], E + d * (s_from - 0.3 * hd["armR"]), warm, "skin")
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin")
    Wp, Hp = hd["palmW"], hd["palmH"]
    cols = [0.10, 0.225, 0.225, 0.225, 0.225] if thumb_side0 else [0.225, 0.225, 0.225, 0.225, 0.10]
    ys = [Wp / 2]
    for cw in cols:
        ys.append(ys[-1] - cw * Wp)

    def palm_ring(c, wsc, hsc, dome=0.18):
        pts = []
        for k in range(12):
            i = k if k < 6 else 11 - k
            top = k < 6
            y = ys[i] * wsc
            edge = i in (0, 5)
            xs = Hp / 2 * hsc * (0.62 if edge else 1.0)
            xs *= (1.0 + dome * (1 - (y / (Wp / 2)) ** 2) * 0.5) if top else (1.0 - 0.10 * (1 - (y / (Wp / 2)) ** 2))
            pts.append(c + Xh * (xs if top else -xs) + Yh * y * (0.92 if edge else 1.0))
        return pts
    wpalm = C.w(["forearm" + side, "hand" + side], blend=0.20 * Lh)
    pr = [cg.ring(palm_ring(W + dh * (0.04 * LHp), 0.78, 1.15, 0.05), wpalm)]
    pr.append(cg.ring(palm_ring(W + dh * (0.32 * LHp), 0.96, 1.08), wpalm))
    pr.append(cg.ring(palm_ring(W + dh * (0.68 * LHp), 1.0, 1.0), wpalm))
    pr.append(cg.ring(palm_ring(W + dh * (0.98 * LHp), 0.98, 0.92, 0.30), wpalm))
    cg.bridge(rings[-1], pr[0], "skin", 0)
    cg.bridge(pr[0], pr[1], "skin", 0)
    tj = 11 if thumb_side0 else 5
    cg.bridge(pr[1], pr[2], "skin", 0, skip=(tj,))
    cg.bridge(pr[2], pr[3], "skin", 0)
    tport = [pr[1][tj], pr[1][(tj + 1) % 12], pr[2][(tj + 1) % 12], pr[2][tj]]
    ring = pr[3]
    finger_cols = [1, 2, 3, 4] if thumb_side0 else [3, 2, 1, 0]
    lens = [0.94, 1.0, 0.94, 0.76]
    flen = Lh * (1 - s["palmFrac"])
    fw, ft = hd["fingerW"], hd["fingerT"]
    curl = [math.radians(a) for a in ((84, 96, 64) if fist else (14, 22, 12))]
    spreads = [-0.05, -0.015, 0.02, 0.07]
    C.fingers = getattr(C, "fingers", {}); C.fingers[side] = []
    thumb_off = Yh if thumb_side0 else -Yh
    for c in range(5):
        q = [ring[c], ring[c + 1], ring[11 - (c + 1)], ring[11 - c]]
        if c not in finger_cols:
            cg.face(q, "skin", 0); continue
        fi = finger_cols.index(c); lf = lens[fi] * flen
        base = sum((cg.v[i] for i in q), V()) / 4
        dirn = (dh - thumb_off * (spreads[fi] * (0.0 if fist else 1.0))).normalized()
        pal = perp(Np, dirn)
        pts = [base, base + dirn * (0.10 * lf)]
        p = pts[-1]; segs = (0.44, 0.31, 0.25)
        joints = []
        for k, (sl, ang) in enumerate(zip(segs, curl)):
            dirn, pal = (dirn * math.cos(ang) + pal * math.sin(ang)).normalized(), (pal * math.cos(ang) - dirn * math.sin(ang)).normalized()
            n0 = p; p = p + dirn * (sl * lf * (0.90 if k == 0 else 1.0))
            joints.append((n0, p, dirn.copy()))
            pts.append(p)
        C.fingers[side].append(dict(path=[x.copy() for x in pts], joints=joints))
        st = []
        # stations: knuckle, proximal mid, PIP, middle mid, DIP, distal mid, near tip
        prof = [(0.06, 1.04), (0.30, 1.00), (0.47, 1.03), (0.62, 0.95), (0.76, 0.97), (0.88, 0.88), (0.97, 0.78)]
        for t, sc in prof:
            pt = cr_open(pts, t)
            st.append((pt, (ft / 2 * sc * 1.25, ft / 2 * sc * 1.25, fw / 2 * sc * 1.18, fw / 2 * sc * 1.18)))
        b0 = base.copy()

        def wf(pp, b0=b0, lf=lf):
            t = smoothstep(0.10 * lf, 0.34 * lf, (pp - b0).length)
            return {"hand" + side: 1 - t, "fingers" + side: t} if t < 0.999 else {"fingers" + side: 1.0}
        extrude_port(cg, q, st, Xh, wf, "skin", 0, cap=True, mode="square", cap_len=0.9)
    # thumb
    whand = C.w(["hand" + side])
    tc = sum((cg.v[i] for i in tport), V()) / 4
    tl = flen * 0.95
    if fist:
        p1 = tc + thumb_off * (0.25 * hd["thumbW"]) + dh * (0.05 * LHp)
        d1 = (dh * 0.55 + thumb_off * 0.35 + Np * 0.55).normalized()
        p2 = p1 + d1 * (0.40 * tl)
        d2 = (dh * 0.55 - thumb_off * 0.55 + Np * 0.35).normalized()
        p3 = p2 + d2 * (0.36 * tl); p4 = p3 + (d2 - thumb_off * 0.3).normalized() * (0.26 * tl)
    else:
        tl = flen * 0.86
        p1 = tc + thumb_off * (0.25 * hd["thumbW"]) + dh * (0.10 * LHp) + Np * (0.15 * hd["thumbW"])
        d1 = (dh * 0.60 + thumb_off * 0.38 + Np * 0.55).normalized()
        p2 = p1 + d1 * (0.42 * tl)
        d2 = (dh * 0.75 + thumb_off * 0.02 + Np * 0.45).normalized()
        p3 = p2 + d2 * (0.33 * tl); p4 = p3 + (d2 + Np * 0.15).normalized() * (0.25 * tl)
    path = [tc, p1, p2, p3, p4]
    st = []
    for t, sc in ((0.14, 1.10), (0.32, 1.02), (0.50, 0.98), (0.66, 0.92), (0.82, 0.88), (0.95, 0.76)):
        st.append((cr_open(path, t), (hd["thumbT"] / 2 * sc * 1.25, hd["thumbT"] / 2 * sc * 1.25,
                                      hd["thumbW"] / 2 * sc * 1.2, hd["thumbW"] / 2 * sc * 1.2)))
    extrude_port(cg, tport, st, Xh, whand, "skin", 0, cap=True, mode="square", cap_len=0.9)
    C.add("hand" + side, cg, subdiv=1)


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


def build_leg(C, side, shoe_top, reg_shoe, pointy=0.0, top_y=0.050, regfn2=None, curl=0.0):
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
                if curl and t > 0:              # curled toe: the tip rolls up and back (Esther's Haman slippers)
                    tt = smoothstep(0.80 * fl, 1.0 * fl, zl)
                    ang = curl * tt * tt
                    piv = V(q.x, 0.012 * C.S, ank.z + 0.80 * fl + 0.004 * C.S)
                    d = q - piv
                    q = piv + V(d.x, d.y * math.cos(ang) + d.z * math.sin(ang), -d.y * math.sin(ang) + d.z * math.cos(ang))
            out.append(q)
        return out
    C.add("leg" + side, cg, post=post, subdiv=0)


# =============================================================================================== robes
def skirt_weights(C):
    s = C.s; hipY, kneeY = s["hipY"], s["kneeY"]; hipX = s["hipX"]; hem = C.robe_rows[-1][0]
    wt0 = C.w(["hips", "spine", "chest", ("neck", 0.008 * C.S), ("shoulderL", 0.012 * C.S), ("shoulderR", 0.012 * C.S)])

    wlow = C.w(["hips", "spine"])

    def wfn(p):
        # below the waist only hips / spine (Esther's version let the far-away shoulder bones win the normalisation
        # there, ~0.2 shoulder weight at knee height; harmless at rest, but a shrug or a baked pose dents the skirt)
        w = wt0(p) if p.y >= s["waistY"] else wlow(p)
        if p.y >= hipY:
            return w
        tt = min(1.0, (hipY - p.y) / (hipY - hem))
        kk = 0.82 * smoothstep(0.0, 0.45, tt)
        sL = min(1.0, max(0.0, 0.5 + p.x / (3.2 * hipX)))
        sh = 0.65 * smoothstep(kneeY + 0.012 * C.S, kneeY - 0.035 * C.S, p.y)
        w = {b: v * (1 - kk) for b, v in w.items()}
        for side, f in (("L", sL), ("R", 1 - sL)):
            w["thigh" + side] = w.get("thigh" + side, 0) + kk * f * (1 - sh)
            w["shin" + side] = w.get("shin" + side, 0) + kk * f * sh
        return w
    return wfn


def robe_point(C, y, a, off=0.0):
    return shell_point(C.robe_rows, y, a, off, e=2.5)


def build_robe(C, rows, sleeve_rad, sleeve_end, nf=14, fold_amp=0.0016, sleeve_fold=0.0009, bell_sag=0.0,
               regfn=None, sleeve_lip=(0.86, 0.0004, 0.0040), step=0.0052, N=44, reg="robe", name="robe",
               solidify=0.0, keep=False):
    s = C.s; S = C.S; shY = s["shoulder"][1]
    port = (shY - 0.020 * S, shY + 0.0015 * S)
    hem = rows[-1][0]
    ys = sorted({r[0] for r in rows if r[0] > port[0] + 1e-6} | {port[0], port[1]}, reverse=True)
    n = max(4, int(round((port[0] - hem) / (step * S))))
    ys += [port[0] - (port[0] - hem) * i / n for i in range(1, n + 1)]
    ys = sorted(set(round(y, 6) for y in ys if hem - 1e-9 <= y <= rows[0][0] + 1e-9), reverse=True)
    TT = resample_rows(rows, ys)
    C.robe_rows = TT
    C.sleeve_profile = [(sv * S, r * S) for sv, r in sleeve_rad]
    wtorso = skirt_weights(C)
    sleeves = {}
    for side in "LR":
        A = C.arm[side]; S0, d = A["S0"], A["d"]
        wsl = C.w(["chest", "shoulder" + side, "upperArm" + side, "forearm" + side])
        st = [(S0 + d * (sv * S), (r * S, r * S, r * S * 0.97, r * S * 0.97)) for sv, r in sleeve_rad]
        sleeves[side] = (st, wsl, sleeve_lip)
    cg = torso_shell(C, TT, N, port, math.radians(30), sleeves, wtorso, reg, e=2.5,
                     lip_top=(0.90, -0.0004 * S, 0.0030 * S), lip_bot=(0.95, 0.0002 * S, 0.0045 * S), direct=True,
                     regfn=regfn)
    if regfn:     # torso_shell applies regfn to the body only; sleeves keep "robe" unless the caller re-tags them
        pass
    LU, LF = s["upperArm"], s["forearm"]

    def fold(a):
        return math.cos(nf * a + 0.7) + 0.35 * math.cos((nf // 2 + 1) * a + 2.1) + 0.2 * math.cos((nf + 3) * a + 0.3)

    def post(pts, nrm):
        out = []
        for p in pts:
            q = p.copy()
            sl = None
            for side in "LR":
                A = C.arm[side]; sv = (p - A["S0"]).dot(A["d"])
                if sv > 0.004 * S:
                    rv = p - (A["S0"] + A["d"] * sv)
                    if rv.length < 0.030 * S:
                        sl = (A, sv, rv)
            if sl:
                A, sv, rv = sl
                A0 = perp(V(0, 0, 1), A["d"]); B0 = A["d"].cross(A0)
                ang = math.atan2(rv.dot(B0), rv.dot(A0))
                t = smoothstep(0.55 * LU * S, (LU + LF) * S, sv)
                q += rv.normalized() * sleeve_fold * t * math.cos(6 * ang + 0.4)
                if bell_sag:
                    q.y -= bell_sag * t * t * max(0.0, -rv.normalized().y + 0.3)
            elif p.y < s["waistY"]:
                a = math.atan2(p.x, p.z + 0.001)
                hn = V(p.x, 0, p.z + 0.001)
                hn = hn.normalized() if hn.length > 1e-9 else V(0, 0, 1)
                amp = fold_amp * S * smoothstep(s["waistY"] - 0.004 * S, hem + 0.02 * S, p.y) ** 0.8
                q += hn * amp * fold(a)
                if p.y < hem + 0.0070 * S:
                    q.y += 0.0011 * S * fold(a) * smoothstep(hem + 0.0070 * S, hem + 0.001 * S, p.y)
            out.append(q)
        return out
    def zone(p):
        for side in "LR":
            A = C.arm[side]
            if (p - A["S0"]).length < 0.020 * S and p.y > A["S0"].y - 0.010 * S:
                return True
        return False
    C.add(name, cg, post=post, subdiv=0, smooth=(zone, 8), solidify=solidify * S if solidify else 0.0)
    return cg


def waist_band(C, name, reg, y0, y1, off, pc=0, N=48, bulge=0.0010):
    cg = Cage(); wb = C.w(["hips", "spine"])
    angs = [2 * math.pi * j / N for j in range(N)]
    rings = []
    for y, o in ((y0, off), (y0 + 0.0005, off + bulge * 0.8), (lerp(y0, y1, 0.5), off + bulge), (y1 - 0.0005, off + bulge * 0.8), (y1, off)):
        rings.append(cg.ring([robe_point(C, y, a, o) for a in angs], wb))
    for a, b in zip(rings, rings[1:] + rings[:1]):
        cg.bridge(a, b, reg, pc)
    C.add(name, cg, subdiv=0)


def mantle_point(C, u, y, off, r_sleeve=None, plumb_y=None, plumb_extra=0.0):
    """Point on a garment draped over the robe: robe surface + off, hanging plumb below plumb_y at the back, pushed
    out of the sleeve tubes (push_out_of_sleeves). r_sleeve is unused (kept for call-site readability)."""
    a = 2 * math.pi * u
    hw, zf, zb = table(C.robe_rows, y)
    if plumb_y is not None and y < plumb_y:
        zb_bl = table(C.robe_rows, plumb_y)[2]
        zb = min(zb, zb_bl - plumb_extra * (plumb_y - y) / (0.03 * C.S))
    zc = (zf + zb) / 2; rd = (zf - zb) / 2
    p = V(se(math.sin(a), 2.5) * (hw + off), y, zc + se(math.cos(a), 2.5) * (rd + off))
    return push_out_of_sleeves(C, p, off)


def push_out_of_sleeves(C, p, off):
    """Move a point that lies inside a sleeve tube out to the sleeve surface + off (radially from the arm axis)."""
    for side in "LR":
        A = C.arm[side]
        sv = (p - A["S0"]).dot(A["d"])
        if sv < -0.004 * C.S:
            continue
        svc = max(0.0, sv)
        R = table(C.sleeve_profile, svc)[0] if svc <= C.sleeve_profile[-1][0] else 0.0
        if R <= 0:
            continue
        ax = A["S0"] + A["d"] * sv
        rv = p - ax
        need = R + off
        if sv < 0:                                  # behind the shoulder joint: fade the push out
            need *= smoothstep(-0.004 * C.S, 0.0, sv)
        if rv.length < need and rv.length > 1e-9:
            p = ax + rv.normalized() * need
    return p
# =============================================================================================== Ruth pack: shared
def smax(a, b, k):
    return (a + b + math.sqrt((a - b) ** 2 + k * k)) / 2


def hor(v):
    return V(v.x, 0, v.z)


def scale_rows(rows, k, kx, dx=0.0, dz=0.0):
    """Garment rows (y, hw, zf, zb) scaled (y by k, widths by kx), optionally grown by dx / dz (front and back)."""
    return [(y * k, hw * kx + dx, zf * kx + dz, zb * kx - dz) for y, hw, zf, zb in rows]


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


def hood(C, name, reg, rim, thick, wfn, NU=52, NV=22, flare=0.10, body_off=0.0020, back_settle=0.75,
         front_pull=0.0, folds=(11, 0.0020), hem_wave=0.0010, solid=0.0009, pc=0, pw=0.80, loose_top=0.0,
         settle=0.85):
    """A draped head-cloth (scarf, shawl, keffiyeh): closed rings from the free edge rim(u) up to the crown.
    Above eye level it lies on the hair / skull (+ thick); below it hangs plumb from the widest part of the head
    (flaring a little), settles on the robe's shoulders (+ body_off), lies down onto the back below the shoulder line
    (back_settle) and is pushed out of the sleeves; front columns can be pulled toward the chest centre (front_pull).
    Folds deepen below the chin; the hem waves."""
    Hd = C.head; L = C.L; H = C.H; S = C.S; s = C.s
    yw = L["eye"]; shY = s["shoulder"][1]; nb = s["neckBase"]
    top_robe = C.robe_rows[0][0]; hem_robe = C.robe_rows[-1][0]
    outer = getattr(C, "hair_outer", None)

    def headp(u, y):
        yy = min(y, L["top"] - 0.0002)
        q = outer(u, yy) if outer else Hd.at(u, yy)
        n = Hd.normal(u, max(min(yy, L["top"] - 0.001), L["chin"]))
        return q + n * thick(u, y)

    def fold(a):
        n_, _ = folds
        return math.cos(n_ * a + 0.7) + 0.40 * math.cos((n_ // 2 + 1) * a + 2.1) + 0.25 * math.cos((n_ + 4) * a + 0.3)

    def pt(u, y, edge=False):
        a = 2 * math.pi * u; uu = mirror_u(u)
        c = V(0, y, L["zc"])
        if y >= yw:
            return_head = headp(u, y)
            p = return_head
        else:
            pw_ = headp(u, yw); rw = hor(pw_ - V(0, yw, L["zc"])).length * (1 + flare * (yw - y) / H)
            ph = headp(u, max(y, L["chin"] - 0.05 * H)); hq = hor(ph - V(0, ph.y, L["zc"]))
            r = smax(hq.length, rw, 0.0015 * S)
            ang = math.atan2(hq.x, hq.z) if hq.length > 1e-9 else a
            fp = front_pull * smoothstep(shY + 0.004 * S, s["chestY"] - 0.004 * S, y) * smoothstep(0.30, 0.16, uu)
            ang *= (1 - fp)
            dirn = V(math.sin(ang), 0, math.cos(ang))
            if hem_robe <= y <= top_robe + 0.004 * S:
                q = shell_point(C.robe_rows, min(y, top_robe), ang, body_off * S)
                rb = hor(q - c).length
                st = settle * smoothstep(nb + 0.002 * S, shY - 0.002 * S, y) * smoothstep(0.40, 0.30, uu)
                st = max(st, back_settle * smoothstep(shY, shY - 0.030 * S, y) * smoothstep(0.30, 0.40, uu))
                r = smax(lerp(r, rb, st), rb, 0.0012 * S)
            p = c + dirn * r
        p = push_out_of_sleeves(C, p, body_off * S)
        # folds below the chin, a wave along the hem
        fa = folds[1] * S * smoothstep(L["chin"] + 0.02 * H, L["chin"] - 0.06 * S, y)
        if fa:
            p += hor(p - c).normalized() * fa * fold(a) * (0.5 + 0.5 * smoothstep(0.12, 0.30, uu))
        if edge:
            p.y += hem_wave * S * fold(a + 0.4)
        return p
    us = [k / NU for k in range(NU)]
    cg = Cage()
    ytop = L["top"]
    rows = []
    for j in range(NV):
        t = j / NV
        row = []
        for u in us:
            y = lerp(rim(u), ytop, t ** pw)
            row.append(pt(u, y, edge=(j == 0)))
        rows.append(cg.ring(row, wfn))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, reg, pc)
    topp = headp(0.5, ytop) + V(0, loose_top * S, 0)
    cg.fan(rows[-1], topp, wfn, reg, pc)
    C.hood_pt = pt
    C.add(name, cg, subdiv=0, solidify=solid * S)
    return cg


def hood_weights(C, chain, arm_reach=0.010):
    """Head above the chin, neck / chest / shoulders below, the back drape on the chain bones."""
    s = C.s; S = C.S; L = C.L; H = C.H; nb = s["neckBase"]; shY = s["shoulder"][1]
    wl = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S),
              ("upperArmL", arm_reach * S), ("upperArmR", arm_reach * S)])
    wc = C.w(chain, blend=0.012 * S)

    def f(p):
        wh = smoothstep(nb - 0.002 * S, L["chin"] - 0.02 * H, p.y)
        a = math.atan2(p.x, p.z + 0.001)
        tb = smoothstep(shY + 0.006 * S, shY - 0.012 * S, p.y) * smoothstep(-0.25, -0.65, math.cos(a))
        lo = mixw((wl(p), 1 - tb), (wc(p), tb)) if tb > 0 else wl(p)
        return mixw(({"head": 1.0}, wh), (lo, 1 - wh)) if wh < 1 else {"head": 1.0}
    return f


def drop_faces(cg, pred):
    keep = [i for i, q in enumerate(cg.f) if not pred(sum((cg.v[k] for k in q), V()) / len(q))]
    cg.f = [cg.f[i] for i in keep]; cg.reg = [cg.reg[i] for i in keep]; cg.pc = [cg.pc[i] for i in keep]


def sandal_regfn(S):
    """Sole + toe strap + instep strap + ankle strap; skin between (y, z relative to the ankle)."""
    def f(yy, dz):
        if yy < 0.0030 * S:
            return "sandals"
        if yy < 0.0105 * S and abs(dz - 0.0195 * S) < 0.0018 * S:
            return "sandals"
        if yy < 0.0150 * S and abs(dz - 0.0085 * S) < 0.0024 * S:
            return "sandals"
        if abs(yy - 0.0168 * S) < 0.0016 * S:
            return "sandals"
        return "skin"
    return f


def belt_tie(C, name, reg, kx, y0, tails, wd, pc=1, rows=None):
    """Knot on the belt at x = kx and hanging tails [(dx, y_end)] ending in small tassels."""
    S = C.S; wb = C.w(["hips", "spine", ("thighL", 0.02 * S), ("thighR", 0.02 * S)], blend=0.02 * S)
    cg = Cage()
    rr = rows or C.robe_rows
    ka = math.asin(min(1.0, kx / table(rr, y0)[0]))
    kc = shell_point(rr, y0, ka, 0.0034 * S)
    lathe_y(cg, kc, [(-0.0024 * S, 0.0016 * S), (0.0, 0.0030 * S), (0.0024 * S, 0.0016 * S)], 8, wb, reg, pc, e=2.6, zscale=0.6)
    for dx, y_end in tails:
        pp, nn = [], []
        for t in [i / 7 for i in range(8)]:
            y = lerp(y0 - 0.0018 * S, y_end, t)
            x = kx + dx * S + 0.0024 * S * t * (1 if dx > 0 else -0.5)
            a = math.asin(max(-1, min(1, x / (table(rr, y)[0] + 0.002))))
            p = shell_point(rr, y, a, (0.0028 + 0.0012 * math.sin(t * math.pi)) * S)
            pp.append(p); nn.append(V(p.x, 0, p.z).normalized())
        strip(cg, pp, nn, [wd * S * (1.0 - 0.15 * t) for t in [i / 7 for i in range(8)]], 0.0006 * S, wb, reg, pc)
        blob(cg, pp[-1] + V(0, -0.0016 * S, 0.0004 * S), 0.0016 * S, 0.0024 * S, 0.0012 * S, wb, reg, pc, NU=6, NV=4)
    C.add(name, cg, subdiv=0)


def grip_point(C, side, inset=0.0034):
    A = C.arm[side]; s = C.s; hd = s["handDims"]
    return A["K"] - A["dh"] * (0.18 * s["hand"] * s["palmFrac"]) + A["Np"] * (hd["palmH"] * 0.5 + inset * C.S)


def barley_ear(cg, base, d, ln, r, wfn, reg, pc=0, awns=True):
    """One bearded barley ear: a slim spindle along d (lumpy kernels) and two thin awn tufts."""
    d = d.normalized(); A_ = perp(V(0, 0, 1), d)
    if A_.length < 1e-6:
        A_ = perp(V(1, 0, 0), d)
    Bv = d.cross(A_)
    M = Matrix((A_, d, Bv)).transposed()
    blob(cg, base + d * (ln / 2), r, ln / 2, r * 0.85, wfn, reg, pc, NU=6, NV=5, ax=M)
    if awns:
        tip = base + d * ln
        for sg in (-1, 1):
            q = tip + (d * 0.9 + A_ * 0.35 * sg).normalized() * (ln * 0.55)
            tube(cg, [tip - d * (ln * 0.15), tip, q], [r * 0.25, r * 0.18, r * 0.05], 3, wfn, reg, pc, cap0=False, cap1=False)


def stalk_bunch(cg, centre, axis, n, length, spread, r_stalk, ear_len, ear_r, wfn, reg, pc=0, seed=1, below=0.35,
                droop=0.25):
    """A handful of barley stalks crossing at `centre` (the grip), ears up along axis, cut ends below."""
    rnd = random.Random(seed)
    axis = axis.normalized(); A_ = perp(V(0, 0, 1), axis); Bv = axis.cross(A_)
    for i in range(n):
        ang = 2 * math.pi * i / n + rnd.uniform(-0.3, 0.3)
        sp = spread * (0.5 + 0.5 * rnd.random())
        dirn = (axis + (A_ * math.cos(ang) + Bv * math.sin(ang)) * sp).normalized()
        ln = length * rnd.uniform(0.85, 1.1)
        p0 = centre - dirn * (ln * below) + (A_ * math.cos(ang) + Bv * math.sin(ang)) * (r_stalk * 1.5)
        p1 = centre + (A_ * math.cos(ang) + Bv * math.sin(ang)) * (r_stalk * 1.2)
        tip_d = (dirn + (A_ * math.cos(ang) + Bv * math.sin(ang)) * droop - axis * droop * 0.4).normalized()
        p2 = p1 + dirn * (ln * (1 - below) * 0.55)
        p3 = p2 + tip_d * (ln * (1 - below) * 0.45)
        tube(cg, [p0, p1, p2, p3], [r_stalk] * 4, 4, wfn, reg, pc, cap0=True, cap1=False)
        barley_ear(cg, p3, (p3 - p2), ear_len * rnd.uniform(0.9, 1.1), ear_r, wfn, reg, pc)


# =============================================================================================== Daniel pack: shared
def king_like_rim(C, cb):
    """Hair rim + skin cull of a man whose hair is cut / hidden above cb at the front (Esther's king method): the ears
    stay visible, the hair runs behind them down to the nape."""
    L = C.L; H = C.H; S = C.S; nb = C.s["neckBase"]
    ey0, ey1, ew, et = ears_spec(C)

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb + 0.003 * S), (0.13, cb + 0.003 * S), (0.17, cb - 0.004 * S), (0.19, L["eye"] + 0.02 * H),
                      (0.215, L["nose"]), (0.232, ey1 + 0.003 * S), (0.268, ey1 + 0.003 * S), (0.30, L["mouth"]),
                      (0.36, L["chin"] - 0.06 * H), (0.50, L["chin"] - 0.14 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return True
        return uu > 0.17 and p.y > rim(u) + 0.0045 * S and not (0.225 < uu < 0.275 and p.y < ey1)
    return rim, cull


def gold_collar(C, name, reg, yout, lobes=16, scallop=0.0030, pc=0):
    """Broad collar / yoke lying on the robe's shoulders and chest (Esther's king collar): rings from the neck line
    to a scalloped outer edge yout(uu); the offsets dip twice so the collar reads as three woven bands."""
    s = C.s; S = C.S; nb = s["neckBase"]
    wcol = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S)])
    vs = [(0.0, 0.0014), (0.06, 0.0022), (0.30, 0.0022), (0.34, 0.0015), (0.38, 0.0022), (0.64, 0.0022),
          (0.68, 0.0015), (0.72, 0.0022), (0.93, 0.0022), (1.0, 0.0016)]
    NU = 64; cg = Cage(); rings = []
    for v, off in vs:
        ring = []
        for i in range(NU):
            u = i / NU; uu = mirror_u(u)
            yo = table(yout, uu)[0] - scallop * S * (0.5 + 0.5 * math.cos(2 * math.pi * lobes * u)) ** 0.7
            y = lerp(nb + 0.0030 * S, yo, v)
            ring.append(mantle_point(C, u, y, off * S))
        rings.append(cg.ring(ring, wcol))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    C.add(name, cg, subdiv=0, solidify=0.0010 * S, smooth=(lambda p: True, 2))


def hanging_tie(C, name, reg, kx, y0, tails, wd, chain, pc=1):
    """Knot on a sash at x = kx and hanging ends [(dx, y_end)] skinned to a bone chain (top: hips, then chain[0],
    chain[1] down the length) so the ends swing."""
    S = C.S; rr = C.robe_rows
    wtop = C.w(["hips", "spine"])
    wch = C.w(chain, blend=0.010 * S)
    yend = min(t[1] for t in tails)
    ka0 = math.asin(min(1.0, kx / table(rr, y0)[0]))
    ka2 = math.asin(max(-1, min(1, kx / (table(rr, yend)[0] + 0.002))))
    p1 = shell_point(rr, y0 - 0.006 * S, ka0, 0.0040 * S)
    p2 = shell_point(rr, lerp(y0, yend, 0.5), ka2, 0.0042 * S)
    p3 = shell_point(rr, yend, ka2, 0.0042 * S)
    C.B[chain[0]] = (p1, p2, "hips")
    C.B[chain[1]] = (p2, p3, chain[0])

    def wfn(p):
        t = smoothstep(y0 - 0.004 * S, y0 - 0.014 * S, p.y)
        return mixw((wtop(p), 1 - t), (wch(p), t)) if t > 0 else wtop(p)
    cg = Cage()
    ka = math.asin(min(1.0, kx / table(rr, y0)[0]))
    kc = shell_point(rr, y0, ka, 0.0034 * S)
    lathe_y(cg, kc, [(-0.0026 * S, 0.0018 * S), (0.0, 0.0033 * S), (0.0026 * S, 0.0018 * S)], 8, wfn, reg, pc, e=2.6,
            zscale=0.6)
    for dx, y_end in tails:
        pp, nn = [], []
        for t in [i / 9 for i in range(10)]:
            y = lerp(y0 - 0.0018 * S, y_end, t)
            x = kx + dx * S + 0.0026 * S * t * (1 if dx > 0 else -0.5)
            a = math.asin(max(-1, min(1, x / (table(rr, y)[0] + 0.002))))
            p = shell_point(rr, y, a, (0.0030 + 0.0014 * math.sin(t * math.pi)) * S)
            pp.append(p); nn.append(V(p.x, 0, p.z).normalized())
        strip(cg, pp, nn, [wd * S * (1.0 + 0.25 * t) for t in [i / 9 for i in range(10)]], 0.0007 * S, wfn, reg, pc)
        # fringe at the end: a soft rounded hem
        blob(cg, pp[-1] + V(0, -0.0010 * S, 0.0004 * S), wd * S * 1.15, 0.0018 * S, 0.0010 * S, wfn, reg, pc, NU=8, NV=4)
    C.add(name, cg, subdiv=0)


def front_weights(C, cg, bone, centre_y, sigma, zmin, amount, ang_in=25.0, ang_out=75.0):
    """Blend a front zone of a skinned cage toward one bone (belly jiggle, robe front hem)."""
    for i, p in enumerate(cg.v):
        if p.z < zmin:
            continue
        a = abs(math.atan2(p.x, p.z + 0.001))
        if callable(centre_y):
            tw = centre_y(p.y)
        else:
            tw = math.exp(-((p.y - centre_y) / sigma) ** 2)
        tw *= smoothstep(math.radians(ang_out), math.radians(ang_in), a) * amount
        if tw > 0.01:
            cg.w[i] = mixw((cg.w[i], 1 - tw), ({bone: 1.0}, tw))


def haman_moustache(C, y0, reach, r0, name="moustache", reg="beard"):
    """Thin moustache: from under the nose out along the lip, then rolled up into a curl on each side (Esther)."""
    L = C.L; S = C.S
    cg = Cage(); wfn = C.w(["head"])
    for sx in (-1, 1):
        path, rad = [], []
        for i in range(10):
            f = i / 9
            x = sx * (0.03 + 0.97 * f) * reach
            p, n = head_surface(C, x, y0 - 0.0012 * S * math.sin(math.pi * f), 0.0012 * S)
            path.append(p); rad.append(r0 * (1.0 - 0.25 * f))
        end = path[-1]; n_end = head_surface(C, sx * reach, y0, 0.0)[1]
        X = V(sx, 0, 0); X = (X - n_end * X.dot(n_end)).normalized(); Y = V(0, 1, 0)
        rc = 0.0030 * S; cen = end + Y * rc
        for k in range(1, 23):
            t = k / 22
            ang = -math.pi / 2 + t * 2.2 * math.pi
            r = rc * (1.0 - 0.55 * t)
            p = cen + X * (math.cos(ang) * r) + Y * (math.sin(ang) * r) + n_end * (0.0006 * S * t)
            path.append(p); rad.append(r0 * 0.75 * (1.0 - 0.6 * t))
        tube(cg, path, [(r * 0.85, r) for r in rad], 8, wfn, reg, 1, cap0=True, cap1=True)
    C.add(name, cg, subdiv=0)


# =============================================================================================== Daniel
def build_daniel(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]
    cb = L["brow"] + 0.15 * H
    rim, cull = king_like_rim(C, cb)
    ey0, ey1, ew, et = ears_spec(C)
    skeleton(C)
    build_head(C, cull, ears=(ey0, ey1, ew, et))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0026, 0.0034, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        return t * S
    # long dark-brown hair combed back over the crown, hugging the head to the nape, tied there
    hair_shell(C, rim, thick, "hair", "hair", plumb=None, tuck_front=0.17, grooves=40, groove_amp=0.00030, NU=40, NV=9)
    # short neat beard + moustache (Boaz's method, shorter and trimmed)
    top = [(0.00, L["mouth"] - 0.075 * H), (0.035, L["mouth"] - 0.062 * H), (0.07, L["mouth"] + 0.010 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.00 * H), (0.20, L["eye"] - 0.16 * H), (0.245, L["eye"] - 0.05 * H)]
    bot = [(0.00, L["chin"] - 0.07 * H), (0.06, L["chin"] - 0.06 * H), (0.12, L["chin"] - 0.03 * H),
           (0.17, L["chin"] + 0.04 * H), (0.21, L["mouth"] - 0.03 * H), (0.245, L["nose"] - 0.03 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0034, 0.0022, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.22, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0004 * S

    def bcurls(u, y):
        return 0.00035 * S * math.cos(2 * math.pi * u * 40)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.07 * H, reg="hair")
    moustache(C, "moustache", L["mouth"] + 0.085 * H, 0.56 * s["hw"], 0.07 * H, 0.02 * H, 0.0018 * S, reg="hair", off=0.0014)
    # ---- cream linen robe to the ankles; short over-sleeves (to above the elbow) over long under-sleeves
    R = scale_rows(KING_ROBE, k, kx)
    R = [(y, hw * (1.0 - 0.05 * math.exp(-((y - 0.205 * k) / 0.03) ** 2)), zf - 0.0012 * math.exp(-((y - 0.20 * k) / 0.03) ** 2), zb)
         for y, hw, zf, zb in R]
    sleeve = [(0.004, 0.0128), (0.014, 0.0126), (0.028, 0.0121), (0.040, 0.0119), (0.047, 0.0121), (0.0495, 0.0118),
              (0.0515, 0.0098), (0.056, 0.0090), (0.068, 0.0085), (0.080, 0.0086), (0.088, 0.0089), (0.093, 0.0091)]
    build_robe(C, R, sleeve, None, nf=14, fold_amp=0.0018, sleeve_fold=0.0008, reg="robe", name="robe")
    s_from = max(0.012, 0.093 * S - s["upperArm"] - 0.008)
    for side in "LR":
        build_forearm_hand(C, side, s_from)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S))
    # ---- broad gold collar (yoke) in three woven bands
    gold_collar(C, "collar", "collar", [(0.00, s["chestY"] - 0.006 * S), (0.15, s["chestY"] - 0.001 * S),
                                        (0.25, shY - 0.010 * S), (0.35, s["chestY"] + 0.002 * S), (0.50, s["chestY"] + 0.000 * S)],
                lobes=18, scallop=0.0026)
    # ---- teal sash with a hanging end on his left front (sash1 / sash2)
    waist_band(C, "sash", "sash", wy - 0.0066 * S, wy + 0.0062 * S, 0.0010 * S, bulge=0.0012 * S)
    hanging_tie(C, "sashTie", "sash", 0.0110 * S, wy - 0.001 * S, [(-0.0006, wy - 0.064 * S), (0.0030, wy - 0.052 * S)],
                0.0030, ["sash1", "sash2"])
    # ---- ponytail: hair gathered at the nape, tied, hanging down the back (hair1)
    yg = L["chin"] + 0.22 * H
    zbh = C.hair_outer(0.5, yg).z
    yb = [nb - 0.004 * S, shY - 0.026 * S, s["chestY"] - 0.024 * S]
    zr = [table(C.robe_rows, y)[2] for y in yb]
    ctrl = [V(0, yg, zbh + 0.0012 * S), V(0, L["chin"] + 0.02 * H, zbh - 0.0040 * S), V(0, yb[0], zr[0] - 0.0058 * S),
            V(0, yb[1], zr[1] - 0.0044 * S), V(0, yb[2], zr[2] - 0.0030 * S)]
    NP = 14
    path = [cr_open(ctrl, i / NP) for i in range(NP + 1)]
    rads = [(0.0040 * S * (1 + 0.25 * math.sin(math.pi * min(1, t / 0.6))) * (1 - 0.75 * smoothstep(0.65, 1.0, t)))
            for t in [i / NP for i in range(NP + 1)]]
    C.B["hair1"] = (path[3].copy(), path[-1].copy(), "head")

    def wpony(p):
        t = smoothstep(L["chin"] + 0.12 * H, L["chin"] - 0.02 * H, p.y)
        return {"head": 1 - t, "hair1": t} if t > 0 else {"head": 1.0}
    cg = Cage()
    tube(cg, path, [(r * 1.15, r) for r in rads], 10, wpony, "hair", 0, ref=V(1, 0, 0), cap0=True, cap1=True, cap_len=0.8)
    tc = path[2]; td = (path[3] - path[1]).normalized()         # the tie: a wrapped band just below the gather point
    tube(cg, [tc - td * 0.0016 * S, tc + td * 0.0016 * S], [rads[2] * 1.25, rads[2] * 1.25], 10, wpony, "hair", 1,
         cap0=False, cap1=False)
    C.add("ponytail", cg, subdiv=1)


# =============================================================================================== King Darius
def build_king(C):
    s = C.s; L = C.L; H = C.H; S = C.S
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]
    cb = L["brow"] + 0.24 * H
    rim, cull = king_like_rim(C, cb)
    ey0, ey1, ew, et = ears_spec(C)
    skeleton(C)
    build_head(C, cull, ears=(ey0, ey1, ew, et))

    def thick(u, y):
        return (0.0034 + 0.0010 * smoothstep(L["eye"], L["chin"], y)) * S

    def curls(u, y):
        rh = 0.0058 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0012 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh)) \
            * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 30 + ph)))
    hair_shell(C, rim, thick, "hair", "beard", plumb=lambda uu: smoothstep(0.26, 0.34, uu), tuck_front=0.17, grooves=0,
               curls=curls, NU=40, NV=8)
    # big black curly beard in rows of curls + a curly moustache
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.065 * H), (0.07, L["mouth"] + 0.01 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.00 * H), (0.20, L["eye"] - 0.17 * H), (0.245, L["eye"] - 0.06 * H)]
    bot = [(0.00, L["chin"] - 0.36 * H), (0.06, L["chin"] - 0.34 * H), (0.12, L["chin"] - 0.24 * H),
           (0.17, L["chin"] - 0.04 * H), (0.21, L["mouth"] - 0.05 * H), (0.245, L["nose"] - 0.04 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0066, 0.0034, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0060 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0015 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 28 + ph))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.36 * H, NV=14)
    moustache(C, "moustache", L["mouth"] + 0.085 * H, 0.66 * s["hw"], 0.07 * H, 0.12 * H, 0.0024 * S, off=0.0016)
    # ---- lavender robe with a round belly; wide sleeves
    g = lambda y: math.exp(-((y - 0.196) / 0.036) ** 2)
    R = [(y, hw + 0.0050 * g(y), zf + 0.0150 * g(y), zb - 0.0010 * g(y)) for y, hw, zf, zb in KING_ROBE]
    sleeve = [(0.004, 0.0132), (0.014, 0.0129), (0.030, 0.0119), (0.046, 0.0113), (0.060, 0.0115), (0.070, 0.0121),
              (0.078, 0.0130), (0.084, 0.0137), (0.087, 0.0140)]
    cg = build_robe(C, R, sleeve, None, nf=12, fold_amp=0.0022, sleeve_fold=0.0010, bell_sag=0.0010 * S)
    front_weights(C, cg, "belly", 0.196, 0.030, 0.006, 0.80)
    for side in "LR":
        build_forearm_hand(C, side, max(0.012, 0.087 * S - s["upperArm"] - 0.010))
        build_leg(C, side, 0.0125 * S, "shoes")
    zfb = table(C.robe_rows, 0.198)[1]
    C.B["belly"] = (V(0, 0.198, zfb - 0.022), V(0, 0.198, zfb + 0.004), "spine")
    # ---- gold belt on the belly + a big round gold medallion with a star on the chest
    waist_band(C, "belt", "belt", wy - 0.0060 * S, wy + 0.0050 * S, 0.0012 * S, bulge=0.0008 * S)
    bpart = C.parts[-1]["cage"]
    front_weights(C, bpart, "belly", 0.196, 0.030, 0.006, 0.80)
    cg = Cage(); wm = C.w(["chest", "spine"])
    mc = robe_point(C, chestY - 0.004 * S, 0.0, 0.0018 * S)
    R0 = 0.0108 * S
    lathe_z(cg, mc, [(0.0, R0 * 0.94), (0.0008 * S, R0), (0.0016 * S, R0 * 0.97), (0.0020 * S, R0 * 0.86),
                     (0.0018 * S, R0 * 0.80), (0.0022 * S, R0 * 0.70), (0.0026 * S, R0 * 0.20), (0.0027 * S, 0.0)],
            24, wm, lambda a, b: "medallion", 0)
    star = []
    for j in range(10):
        r = R0 * (0.62 if j % 2 == 0 else 0.27)
        a = math.pi / 2 + 2 * math.pi * j / 10
        star.append((math.cos(a) * r, math.sin(a) * r))
    extrude_outline(cg, star, 0.0012 * S, wm, "medallion", 1, z0=0.0018 * S, bevel=0.12, origin=mc)
    C.add("medallion", cg, subdiv=0)
    # ---- deep-blue cape over the shoulders, open at the front, falling down the back (cape1 / cape2)
    zb_s = table(C.robe_rows, shY)[2]
    C.B["cape1"] = (V(0, shY - 0.004 * S, zb_s - 0.008 * S), V(0, 0.160, table(C.robe_rows, 0.160)[2] - 0.012 * S), "chest")
    C.B["cape2"] = (V(0, 0.160, table(C.robe_rows, 0.160)[2] - 0.012 * S), V(0, 0.040, table(C.robe_rows, 0.040)[2] - 0.016 * S), "cape1")
    wl = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S),
              ("upperArmL", 0.008 * S), ("upperArmR", 0.008 * S)])
    wc = C.w(["cape1", "cape2"], blend=0.014 * S)

    def wcape(p):
        tb = smoothstep(shY + 0.004 * S, shY - 0.022 * S, p.y) * smoothstep(-0.10, -0.55, math.cos(math.atan2(p.x, p.z + 0.001)))
        return mixw((wl(p), 1 - tb), (wc(p), tb)) if tb > 0 else wl(p)
    ytop, ybot = nb + 0.0020 * S, 0.032
    NV, NU = 20, 32
    cg = Cage(); rows = []
    for j in range(NV + 1):
        v = j / NV
        y = lerp(ytop, ybot, v ** 1.15)
        u0 = table([(ytop, 0.110), (shY, 0.200), (shY - 0.020 * S, 0.285), (chestY - 0.03 * S, 0.30), (0.0, 0.305)], y)[0]
        off = lerp(0.0028, 0.0110, smoothstep(shY, 0.03, y)) * S
        row = []
        for i in range(NU + 1):
            u = lerp(u0, 1 - u0, i / NU)
            p = mantle_point(C, u, y, off, plumb_y=chestY, plumb_extra=0.0010)
            uu = mirror_u(u)
            fold = 0.0012 * S * math.cos(2 * math.pi * 7 * u) * smoothstep(shY - 0.01 * S, 0.06, y)
            p += V(p.x, 0, p.z - (C.robe_rows[0][2] + C.robe_rows[0][3]) / 2).normalized() * fold
            if j == NV:
                p.y += 0.0012 * S * math.cos(2 * math.pi * 7 * u + 0.4)
            row.append(p)
        rows.append(cg.ring(row, wcape))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, "cape", 0, closed=False)
    C.add("cape", cg, subdiv=0, solidify=0.0012 * S)
    for sx in (-1, 1):                             # two gold clasps where the cape meets the collarbone
        cg = Cage()
        u = 0.115 if sx > 0 else 1 - 0.115
        c = mantle_point(C, u, lerp(ytop, shY, 0.55), 0.0048 * S)
        lathe_z(cg, c, [(0.0, 0.0034 * S), (0.0010 * S, 0.0036 * S), (0.0018 * S, 0.0026 * S), (0.0021 * S, 0.0)], 14,
                C.w(["chest"]), lambda a, b: "medallion", 0)
        C.add("clasp" + ("L" if sx > 0 else "R"), cg, subdiv=0)
    # ---- tall purple crown-hat with a gold band and a row of gold studs (skinned to the head)
    cg = Cage(); wh = C.w(["head"])
    Hc = 0.44 - cb
    prof = [(-0.0020 * S, 0.965), (0.0, 1.0), (0.004 * S, 1.010), (0.25 * Hc, 1.040), (0.55 * Hc, 1.080),
            (0.85 * Hc, 1.115), (Hc - 0.0016 * S, 1.130), (Hc - 0.0004 * S, 1.110), (Hc, 1.04), (Hc + 0.0006 * S, 0.80),
            (Hc + 0.0008 * S, 0.40), (Hc + 0.0009 * S, 0)]
    cr = head_lathe(C, cb, prof, 32, wh, "crown", 0, cg, extra_x=0.0040 * S, extra_f=0.0016 * S, extra_b=0.0050 * S)
    kk = lambda dy: table([(p[0], p[1]) for p in prof if p[1] > 0], dy)[0]
    y0b, y1b = 0.0020 * S, 0.0120 * S
    rings = []
    for yy, ka in ((y0b, 0.004), (y0b + 0.0007 * S, 0.034), (y1b - 0.0007 * S, 0.034), (y1b, 0.004)):
        rings.append(cg.ring([V(se(math.sin(2 * math.pi * j / 40), 2.3) * cr["rx"] * (kk(yy) + ka), cb + yy,
                                cr["zc"] + se(math.cos(2 * math.pi * j / 40), 2.3) * cr["rz"] * (kk(yy) + ka)) for j in range(40)], wh))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "crownBand", 1)
    ys = 0.0172 * S
    for j in range(16):                         # studs: a row of small gold domes above the band
        a = 2 * math.pi * j / 16
        kq = kk(ys) + 0.02
        c = V(se(math.sin(a), 2.3) * cr["rx"] * kq, cb + ys, cr["zc"] + se(math.cos(a), 2.3) * cr["rz"] * kq)
        nrm = V(math.sin(a), 0, math.cos(a)).normalized()
        X = V(0, 1, 0).cross(nrm).normalized()
        blob(cg, c, 0.0020 * S, 0.0020 * S, 0.0013 * S, wh, "crownBand", 2, NU=8, NV=5, ax=Matrix((X, V(0, 1, 0), nrm)).transposed())
    C.add("crown", cg, subdiv=0)
    finger_ring(C, "R", "ring")


# =============================================================================================== the official
def build_officer(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]
    cb = L["brow"] + 0.36 * H
    rim, cull = king_like_rim(C, cb)
    ey0, ey1, ew, et = ears_spec(C)
    skeleton(C)
    build_head(C, cull, ears=(ey0, ey1, ew * 1.08, et))

    def thick(u, y):
        return (0.0022 + 0.0008 * smoothstep(L["brow"], L["top"], y)) * S
    hair_shell(C, rim, thick, "hair", "beard", plumb=None, tuck_front=0.17, grooves=48, groove_amp=0.00022, NU=36, NV=8)
    # gold headband round the hair, a little lower at the back, with a round boss at the front
    cg = Cage(); wfn = C.w(["head"])
    NB = 48; pts, nrm = [], []
    for j in range(NB):
        u = j / NB
        y = lerp(L["brow"] + 0.22 * H, L["brow"] + 0.02 * H, (1 - math.cos(2 * math.pi * u)) / 2)
        p = C.hair_outer(u, y); n = C.head.normal(u, min(y, L["top"] - 0.001))
        pts.append(p); nrm.append(n)
    band_loop(cg, pts, nrm, [V(0, 1, 0)] * NB, 0.0028 * S, 0.0009 * S, wfn, "headband", 0)
    fc = pts[0] + nrm[0] * 0.0012 * S
    blob(cg, fc, 0.0028 * S, 0.0028 * S, 0.0012 * S, wfn, "headband", 0, NU=12, NV=6)
    C.add("headband", cg, subdiv=0)
    # pointy nose: out from the bridge to a sharp-ish tip, tipped a little down
    q0, _ = head_surface(C, 0.0, L["eye"] - 0.04 * H, -0.0006 * S)
    q1, _ = head_surface(C, 0.0, L["nose"] + 0.16 * H, 0.0020 * S)
    q2, _ = head_surface(C, 0.0, L["nose"] + 0.05 * H, 0.0058 * S)
    q3, _ = head_surface(C, 0.0, L["nose"] - 0.01 * H, 0.0074 * S)
    q4, _ = head_surface(C, 0.0, L["nose"] - 0.04 * H, 0.0030 * S)
    NN = 20
    path = [cr_open([q0, q1, q2, q3, q4], t / NN) for t in range(NN + 1)]
    nr0 = [(0.0014, 0.0012), (0.0015, 0.0013), (0.0017, 0.0015), (0.0019, 0.0017), (0.0021, 0.0019), (0.0023, 0.0021),
           (0.0025, 0.0023), (0.0026, 0.0024), (0.0026, 0.0024), (0.0024, 0.0022), (0.0020, 0.0018), (0.0015, 0.0014),
           (0.0011, 0.0010), (0.0012, 0.0012), (0.0016, 0.0015)]
    nr = [table([(kk / 14,) + nr0[kk] for kk in range(15)], t / NN) for t in range(NN + 1)]
    cg = Cage()
    tube(cg, path, [(a * S * 1.05, b * S) for a, b in nr], 12, C.w(["head"]), "skin", 2, ref=V(1, 0, 0),
         cap0=True, cap1=True, cap_len=0.7)
    for sx in (-1, 1):                                          # nostril wings
        c = q3 + V(sx * 0.0020 * S, -0.0022 * S, -0.0024 * S)
        blob(cg, c, 0.0013 * S, 0.0011 * S, 0.0013 * S, C.w(["head"]), "skin", 2, NU=10, NV=6)
    C.add("nose", cg, subdiv=0)
    # thin pointed goatee + twirled moustache
    p0, _ = head_surface(C, 0.0, L["mouth"] - 0.075 * H, 0.0008 * S)
    p1, _ = head_surface(C, 0.0, L["chin"] + 0.10 * H, 0.0016 * S)
    p2, _ = head_surface(C, 0.0, L["chin"] + 0.01 * H, 0.0020 * S)
    p3 = p2 + V(0, -0.0090 * S, 0.0030 * S); p4 = p2 + V(0, -0.0185 * S, 0.0068 * S)
    path = [cr_open([p0, p1, p2, p3, p4], t / 10) for t in range(11)]
    rad = [(lerp(0.0011, 0.0018, min(1, t / 3)) * S * (1 - 0.85 * smoothstep(0.55, 1.0, t / 10)),
            lerp(0.0036, 0.0042, min(1, t / 3)) * S * (1 - 0.90 * smoothstep(0.45, 1.0, t / 10))) for t in range(11)]
    cg = Cage()
    tube(cg, path, rad, 10, C.w(["head"]), "beard", 0, cap0=True, cap1=True, cap_len=0.8)
    C.add("goatee", cg, subdiv=0, decal=True, jaw=True, jawBelow=0.9, jawZ=-0.05)
    haman_moustache(C, L["mouth"] + 0.115 * H, 0.66 * s["hw"], 0.0010 * S)
    # ---- burnt-orange robe (thin), red stripes at the hem and the cuffs
    kr = nb / KING["neckBase"]
    R = scale_rows(KING_ROBE, kr, 0.80)
    R = [(y, hw, zf - 0.0010 * math.exp(-((y - 0.20) / 0.03) ** 2), zb) for y, hw, zf, zb in R]
    sleeve = [(0.004, 0.0108), (0.014, 0.0106), (0.030, 0.0098), (0.046, 0.0093), (0.060, 0.0095), (0.072, 0.0101),
              (0.082, 0.0108), (0.088, 0.0112)]
    send = sleeve[-1][0] * S
    cg = build_robe(C, R, sleeve, None, nf=12, fold_amp=0.0016, sleeve_fold=0.0008, reg="robe", name="robe")
    hem = C.robe_rows[-1][0]
    for fi, q in enumerate(cg.f):
        cen = sum((cg.v[i] for i in q), V()) / len(q)
        sl = None
        for side in "LR":
            A = C.arm[side]; sv = (cen - A["S0"]).dot(A["d"])
            if sv > 0.004 * S and (cen - (A["S0"] + A["d"] * sv)).length < 0.03 * S:
                sl = sv
        if sl is not None:
            if sl > send - 0.0085 * S:
                cg.reg[fi] = "stripes"; cg.pc[fi] = 3
        elif cen.y < hem + 0.0105 * S:
            cg.reg[fi] = "stripes"; cg.pc[fi] = 1
        elif hem + 0.0165 * S < cen.y < hem + 0.0235 * S:
            cg.reg[fi] = "stripes"; cg.pc[fi] = 2
    kneeY = s["kneeY"]
    front_weights(C, cg, "robe1", lambda y: 0.85 * smoothstep(kneeY + 0.020 * S, hem + 0.010 * S, y), 1.0, 0.004, 1.0,
                  ang_in=30.0, ang_out=80.0)
    zk = table(C.robe_rows, kneeY + 0.01)[1]; zh = table(C.robe_rows, hem)[1]
    C.B["robe1"] = (V(0, kneeY + 0.010, zk + 0.002), V(0, hem + 0.004, zh + 0.004), "hips")
    for side in "LR":
        build_forearm_hand(C, side, max(0.012, send - s["upperArm"] - 0.008))
        build_leg(C, side, 0.0125 * S, "slippers", pointy=1.2, curl=1.5)
    # ---- green sash, knotted on his right front, two ends
    waist_band(C, "sash", "sash", wy - 0.0060 * S, wy + 0.0058 * S, 0.0010 * S, bulge=0.0010 * S)
    belt_tie(C, "sashTie", "sash", -0.0095 * S, wy - 0.001 * S, [(-0.0016, wy - 0.044 * S), (0.0018, wy - 0.054 * S)], 0.0024)
    # ---- the law: a cream scroll with a red seal in the right hand (rigid, scroll bone; hidden by default)
    g = grip_point(C, "R", 0.0026)
    A = C.arm["R"]; up = A["Yh"] if A["Yh"].y > 0 else -A["Yh"]
    up = (up + V(0, 0.25, 0)).normalized()
    cg = Cage()
    ln = 0.036 * S; r0 = 0.0040 * S
    pts = [g + up * (t * ln) for t in (-0.50, -0.47, -0.42, 0.42, 0.47, 0.50)]
    rads = [r0 * 0.6, r0 * 1.12, r0 * 1.0, r0 * 1.0, r0 * 1.12, r0 * 0.6]
    tube(cg, pts, rads, 14, None, "scroll", 0, ref=V(0, 0, 1), cap0=True, cap1=True, cap_len=0.25)
    for sg in (-1, 1):                                            # wooden knobs at the ends
        blob(cg, g + up * (sg * 0.56 * ln), r0 * 0.55, r0 * 0.45, r0 * 0.55, None, "scroll", 0, NU=8, NV=5,
             ax=Matrix((perp(V(1, 0, 0), up), up, up.cross(perp(V(1, 0, 0), up)))).transposed())
    fz = V(0, 0, 1)
    cord0 = g + fz * (r0 * 0.9)
    seal_c = cord0 + fz * 0.0018 * S - up * 0.0105 * S
    tube(cg, [cord0, cord0 - up * 0.004 * S + fz * 0.0010 * S, seal_c + up * 0.0030 * S], [0.0005 * S] * 3, 6, None, "seal", 1,
         cap0=True, cap1=False)
    Xs = perp(V(1, 0, 0), fz); Ys = fz.cross(Xs)
    blob(cg, seal_c, 0.0042 * S, 0.0042 * S, 0.0013 * S, None, "seal", 1, NU=14, NV=6, ax=Matrix((Xs, Ys, fz)).transposed())
    C.add("scroll", cg, subdiv=0, rigid="scroll")
    C.B["scroll"] = (g.copy(), g + up * 0.02 * S, "handR")


# =============================================================================================== lions
LION_BODY = [   # (z, y centre, half width, half height) of the torso sections, rump -> neck (base units)
    (-0.104, 0.093, 0.013, 0.015), (-0.099, 0.092, 0.024, 0.027), (-0.088, 0.090, 0.033, 0.037),
    (-0.068, 0.088, 0.037, 0.042), (-0.040, 0.085, 0.036, 0.041), (-0.010, 0.085, 0.036, 0.041),
    (0.020, 0.088, 0.038, 0.043), (0.042, 0.093, 0.037, 0.044), (0.060, 0.104, 0.031, 0.038),
    (0.074, 0.122, 0.024, 0.030), (0.084, 0.138, 0.020, 0.024)]
LION_TAIL = [(0.0, 0.100, -0.102), (0.0, 0.099, -0.124), (0.0, 0.114, -0.141), (0.0, 0.139, -0.146),
             (0.0, 0.160, -0.136), (0.0, 0.168, -0.120)]


def lion_skeleton(C):
    kx, ky, kz = LION_K[C.ch]

    def P(x, y, z): return V(x * kx, y * ky, z * kz)
    B = {}
    B["root"] = (V(0, 0, 0), V(0, 0.020 * ky, 0), None)
    B["hips"] = (P(0, 0.098, -0.078), P(0, 0.100, -0.035), "root")
    B["spine"] = (P(0, 0.100, -0.035), P(0, 0.103, 0.012), "hips")
    B["chest"] = (P(0, 0.103, 0.012), P(0, 0.108, 0.052), "spine")
    B["neck"] = (P(0, 0.108, 0.052), P(0, 0.138, 0.078), "chest")
    B["head"] = (P(0, 0.138, 0.078), P(0, 0.150, 0.114), "neck")
    B["jaw"] = (P(0, 0.140, 0.090), P(0, 0.122, 0.110), "head")
    ex, ey, ew, eh = C.F["eyeLocal"]
    hc = V(*LION_HEAD["c"]); hr = LION_HEAD["r"]
    zf = hc.z * kz + hr[2] * kz * 0.92
    C.lid = dict(top=ey + 1.30 * eh, h0=0.18 * eh, closed=ey - 1.0 * eh)
    B["eyelids"] = (V(0, C.lid["top"], zf), V(0, C.lid["top"] - 0.010, zf), "head")
    for side, sd in (("L", 1), ("R", -1)):
        B["ear" + side] = (P(sd * 0.021, 0.168, 0.084), P(sd * 0.029, 0.187, 0.082), "head")
        B["upperArm" + side] = (P(sd * 0.026, 0.092, 0.040), P(sd * 0.028, 0.052, 0.034), "chest")
        B["forearm" + side] = (P(sd * 0.028, 0.052, 0.034), P(sd * 0.028, 0.016, 0.044), "upperArm" + side)
        B["paw" + side] = (P(sd * 0.028, 0.016, 0.044), P(sd * 0.028, 0.005, 0.066), "forearm" + side)
        B["thigh" + side] = (P(sd * 0.027, 0.088, -0.068), P(sd * 0.031, 0.052, -0.050), "hips")
        B["shin" + side] = (P(sd * 0.031, 0.052, -0.050), P(sd * 0.031, 0.024, -0.080), "thigh" + side)
        B["foot" + side] = (P(sd * 0.031, 0.024, -0.080), P(sd * 0.031, 0.005, -0.050), "shin" + side)
    B["mane"] = (P(0, 0.126, 0.064), P(0, 0.144, 0.036), "neck")
    tail = [P(*p) for p in LION_TAIL]
    acc = [0.0]
    for a, b in zip(tail, tail[1:]):
        acc.append(acc[-1] + (b - a).length)

    def at(f):
        d = f * acc[-1]
        for i in range(len(acc) - 1):
            if d <= acc[i + 1] + 1e-12:
                t = (d - acc[i]) / max(1e-12, acc[i + 1] - acc[i])
                return tail[i].lerp(tail[i + 1], t)
        return tail[-1].copy()
    pts = [at(f) for f in (0.0, 0.25, 0.5, 0.75, 1.0)]
    for i in range(4):
        B[f"tail{i + 1}"] = (pts[i], pts[i + 1], "hips" if i == 0 else f"tail{i}")
    C.B = B
    C.tail_path = tail; C.tail_len = acc[-1]


def build_lion(C):
    """A chunky, lovable cartoon lion (CONTRACT §2-§3): bean body, plump legs with round paws and toe bumps, big head
    with cheek puffs and a rounded nose, round ears, a big scalloped mane (lion only), S-tail with a dark tuft."""
    ch = C.ch; kx, ky, kz = LION_K[ch]; maned = ch == "lion"
    ks = (kx + ky + kz) / 3

    def P(x, y, z): return V(x * kx, y * ky, z * kz)
    lion_skeleton(C)
    B = C.B
    # ---- body: one tube from the rump to the neck; cream belly / chest underneath
    secs = [(z * kz, yc * ky, rx * kx, ry * ky) for z, yc, rx, ry in LION_BODY]
    if not maned:                                     # lioness: slimmer neck
        secs = [(z, yc, rx * (0.90 if z > 0.055 * kz else 1.0), ry * (0.92 if z > 0.055 * kz else 1.0)) for z, yc, rx, ry in secs]
    path = [V(0, yc, z) for z, yc, rx, ry in secs]
    path = [cr_open(path, i / 21) for i in range(22)]
    zt = [(p.z,) + tuple(table(secs, p.z)[i] for i in range(3)) for p in path]
    radii = [(rx, ry) for _, yc, rx, ry in zt]
    wbody = C.w(["hips", "spine", "chest", "neck", ("upperArmL", 0.016 * ks), ("upperArmR", 0.016 * ks),
                 ("thighL", 0.018 * ks), ("thighR", 0.018 * ks)])
    cg = Cage()

    def belly(q):
        c = sum((cg.v[i] for i in q), V()) / len(q)
        yc, rx, ry = table(secs, c.z)
        if c.y < yc - 0.55 * ry and -0.090 * kz < c.z < 0.064 * kz:
            return "muzzle"
        if c.z > 0.040 * kz and c.y < yc - 0.30 * ry and abs(c.x) < 0.50 * rx:
            return "muzzle"
        return "body"
    rings = tube(cg, path, radii, 18, wbody, "body", 0, ref=V(0, 0, 1), e=2.25, cap0=True, cap1=True, regfn=belly,
                 cap_len=0.5)
    C.add("body", cg, subdiv=1)
    # ---- haunches and shoulders: soft round masses over the leg tops (outlined on the sheet)
    for side, sd in (("L", 1), ("R", -1)):
        cg = Cage()
        wh = C.w(["thigh" + side, "hips", "spine"], blend=0.010 * ks)
        blob(cg, P(sd * 0.023, 0.088, -0.066), 0.017 * kx, 0.031 * ky, 0.031 * kz, wh, "body", 0, NU=12, NV=8)
        C.add("haunch" + side, cg, subdiv=1)
        cg = Cage()
        ws = C.w(["upperArm" + side, "chest", "spine"], blend=0.010 * ks)
        blob(cg, P(sd * 0.022, 0.086, 0.036), 0.015 * kx, 0.027 * ky, 0.022 * kz, ws, "body", 0, NU=10, NV=7)
        C.add("shoulder" + side, cg, subdiv=1)
    # ---- legs: plump tubes, round paws with three toe bumps (paws flat on the page)
    for side, sd in (("L", 1), ("R", -1)):
        for kind in ("F", "B"):
            cg = Cage()
            if kind == "F":
                bones = ["upperArm" + side, "forearm" + side, "paw" + side]
                pts = [P(sd * 0.025, 0.094, 0.038), B["upperArm" + side][1].copy(), B["forearm" + side][1] + V(0, 0.002, 0)]
                rads = [0.0176, 0.0150, 0.0126]
                pc_ = P(sd * 0.028, 0.0098, 0.053)
            else:
                bones = ["thigh" + side, "shin" + side, "foot" + side]
                pts = [P(sd * 0.026, 0.084, -0.064), B["thigh" + side][1].copy(), B["shin" + side][1].copy(),
                       P(sd * 0.031, 0.018, -0.072)]
                rads = [0.0190, 0.0152, 0.0120, 0.0116]
                pc_ = P(sd * 0.031, 0.0098, -0.062)
            wl = C.w(bones, blend=0.007 * ks)
            dense = [cr_open(pts, i / 7) for i in range(8)]
            rr = [table([(i / (len(rads) - 1), r) for i, r in enumerate(rads)], i / 7)[0] * ks for i in range(8)]
            tube(cg, dense, [(r, r * 1.04) for r in rr], 10, wl, "body", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
            wp = C.w([bones[-1]], blend=0.01)
            blob(cg, pc_, 0.0150 * kx, 0.0100 * ky, 0.0178 * kz, wp, "body", 0, NU=10, NV=6)
            for dx in (-0.0072, 0.0, 0.0072):                       # toe bumps along the front of the paw
                blob(cg, pc_ + P(dx, -0.0020, 0.0128 - 0.0030 * abs(dx) / 0.0072), 0.0050 * kx, 0.0055 * ky,
                     0.0056 * kz, wp, "body", 0, NU=6, NV=4)

            def post(pts_, nrm, pc_=pc_):
                out = []
                for p in pts_:
                    q = p.copy()
                    if q.y < 0.0040 and (q - pc_).length < 0.03:
                        q.y = max(0.0004, q.y * 0.55 + 0.0004)
                    out.append(q)
                return out
            C.add("leg" + kind + side, cg, subdiv=1, post=post)
    # ---- head: a soft round head, front a little flatter, cheeks a little wider at the bottom
    hc = P(*LION_HEAD["c"]); hr = LION_HEAD["r"]
    cg = Cage()
    whead = C.w(["head", "neck"], blend=0.010 * ks)
    blob(cg, hc, hr[0] * kx, hr[1] * ky, hr[2] * kz, whead, "body", 0, NU=18, NV=11)

    def hpost(pts_, nrm):
        out = []
        for p in pts_:
            q = p.copy()
            d = q - hc
            if d.z > 0:
                q.z = hc.z + d.z * (1 - 0.10 * smoothstep(0.0, hr[2] * kz, d.z))
            if d.y < 0:
                q.x = hc.x + d.x * (1 + 0.10 * smoothstep(0.0, -hr[1] * ky, d.y))
            out.append(q)
        return out
    C.add("head", cg, subdiv=1, decal=True, post=hpost)
    # nose bridge (body colour, under the decal) between the eyes and the nose
    cg = Cage()
    blob(cg, P(0, 0.1505, 0.1085), 0.0090 * kx, 0.0125 * ky, 0.0085 * kz, C.w(["head"]), "body", 0, NU=10, NV=6,
         ax=Matrix.Rotation(math.radians(-24), 3, V(1, 0, 0)))
    C.add("bridge", cg, subdiv=1, decal=True)
    # muzzle: two cheek puffs (upper half on head, lower half on jaw) and a chin on the jaw
    cg = Cage()

    def wcheek(p):
        t = smoothstep(0.1360 * ky, 0.1270 * ky, p.y)
        return {"head": 1 - t, "jaw": t} if t > 0 else {"head": 1.0}
    for sx in (-1, 1):
        blob(cg, P(sx * 0.0112, 0.1345, 0.1070), 0.0138 * kx, 0.0108 * ky, 0.0108 * kz, wcheek, "muzzle", 0, NU=12, NV=8)
    blob(cg, P(0, 0.1250, 0.1035), 0.0105 * kx, 0.0070 * ky, 0.0088 * kz, lambda p: {"jaw": 1.0}, "muzzle", 0, NU=10, NV=6)
    C.add("muzzle", cg, subdiv=1, decal=True)
    # nose: a rounded inverted triangle
    nc = P(0, 0.1448, 0.1185)
    cg = Cage()
    blob(cg, nc, 0.0088 * kx, 0.0060 * ky, 0.0056 * kz, C.w(["head"]), "nose", 0, NU=10, NV=6,
         ax=Matrix.Rotation(math.radians(-18), 3, V(1, 0, 0)))

    def npost(pts_, nrm):
        out = []
        for p in pts_:
            q = p.copy(); t = smoothstep(0.0, -0.006 * ky, q.y - nc.y)
            q.x = nc.x + (q.x - nc.x) * (1 - 0.48 * t)
            out.append(q)
        return out
    C.add("nose", cg, subdiv=1, post=npost)
    # ears: round, a cream inner ear, set at the top front edge of the mane
    for side, sd in (("L", 1), ("R", -1)):
        cg = Cage()
        we = lambda p, side=side: {"ear" + side: 1.0}
        c = P(sd * 0.0225, 0.1735, 0.0855)
        Mx = Matrix.Rotation(math.radians(-sd * 24), 3, V(0, 0, 1)) @ Matrix.Rotation(math.radians(-10), 3, V(1, 0, 0))
        blob(cg, c, 0.0102 * ks, 0.0098 * ks, 0.0040 * ks, we, "body", 0, NU=10, NV=6, ax=Mx)
        blob(cg, c + Mx @ V(0, -0.0006, 0.0030) * ks, 0.0060 * ks, 0.0056 * ks, 0.0014 * ks, we, "muzzle", 1, NU=8, NV=5, ax=Mx)
        C.add("ear" + side, cg, subdiv=1)
    # ---- mane (lion): a big round ruff of soft scalloped tufts around the face, back over the neck and down the chest
    if maned:
        Cf = P(0, 0.150, 0.088); Cb = P(0, 0.110, 0.016)
        D = (Cb - Cf); LN = D.length; D.normalize()
        Ax = V(1, 0, 0); Bx = perp(V(0, 1, 0), D)
        prof = [(0.12, 0.020), (0.03, 0.028), (0.0, 0.0322), (0.03, 0.041), (0.10, 0.052), (0.22, 0.060),
                (0.38, 0.064), (0.55, 0.063), (0.72, 0.058), (0.86, 0.048), (0.96, 0.034), (1.02, 0.018)]
        NT = 11; NU = NT * 4
        cg = Cage()
        hc_ = hc.copy()

        def wmane(p):
            t = (p - Cf).dot(D) / LN
            rho = (p - (Cf + D * (t * LN))).length
            wh = smoothstep(0.62, 0.10, t)
            wm = 0.50 * smoothstep(0.15, 0.75, t) + 0.30 * smoothstep(0.045, 0.066, rho)
            wn = max(0.0, 1.0 - wh - wm)
            w = {"head": wh, "mane": wm, "neck": wn}
            sm = sum(w.values())
            return {b: v / sm for b, v in w.items() if v / sm > 0.02}
        rings = []
        for j, (t, r0) in enumerate(prof):
            c = Cf + D * (t * LN)
            amp = 0.26 * smoothstep(0.0, 0.12, t) * smoothstep(1.02, 0.80, t)
            ph = 0.5 * math.pi * (j % 2) + 0.9 * t
            ring = []
            for i in range(NU):
                th = 2 * math.pi * i / NU
                tuft = (0.5 + 0.5 * math.cos(NT * th + ph)) ** 1.6
                r = r0 * (1 + amp * (tuft - 0.35))
                down = max(0.0, -math.sin(th))
                r *= 1 + 0.16 * down * smoothstep(0.05, 0.3, t) - 0.06 * max(0.0, math.sin(th)) * smoothstep(0.6, 1.0, t)
                dz = 0.0035 * tuft * smoothstep(0.0, 0.2, t) * smoothstep(1.0, 0.6, t)
                p = c + (Ax * math.cos(th) + Bx * math.sin(th)) * (r * ks) + D * (dz * ks)
                ring.append(p)
            rings.append(cg.ring(ring, wmane))
        cg.fan(rings[0], Cf + D * (0.16 * LN), wmane, "mane", 0)
        for a, b in zip(rings, rings[1:]):
            cg.bridge(a, b, "mane", 0)
        cg.fan(rings[-1], Cf + D * (1.06 * LN), wmane, "mane", 0)
        C.add("mane", cg, subdiv=1)
        # a soft forehead tuft between the ears (three little round curls)
        cg = Cage()
        for dx, dy, r in ((-0.0060, 0.0, 0.0050), (0.0, 0.0024, 0.0058), (0.0060, 0.0, 0.0050)):
            c = hc + P(dx, hr[1] * 0.86 + dy, 0.0060)
            blob(cg, c, r * ks, r * 1.15 * ks, r * 0.9 * ks, C.w(["head"]), "mane", 0, NU=8, NV=5,
                 ax=Matrix.Rotation(math.radians(-dx / 0.006 * 20), 3, V(0, 0, 1)))
        C.add("forelock", cg, subdiv=1)
    # ---- tail: S-curve up behind the rump, dark tuft at the tip
    tp = C.tail_path
    dense = [cr_open(tp, i / 14) for i in range(15)]
    rr = [(0.0060 - 0.0022 * (i / 14)) * ks for i in range(15)]
    cg = Cage()
    wt = C.w(["hips", "tail1", "tail2", "tail3", "tail4"], blend=0.005 * ks)
    tube(cg, dense, rr, 8, wt, "body", 0, ref=V(1, 0, 0), cap0=True, cap1=True)
    d = (dense[-1] - dense[-3]).normalized()
    Xt = perp(V(1, 0, 0), d); Zt = Xt.cross(d)
    Mt = Matrix((Xt, d, Zt)).transposed()
    tip = dense[-1]
    wtt = lambda p: {"tail4": 1.0}
    blob(cg, tip + d * 0.0060 * ks, 0.0088 * ks, 0.0150 * ks, 0.0088 * ks, wtt, "tuft", 1, NU=8, NV=6, ax=Mt)
    for k in range(3):                                           # fluffy flame-like tips
        a = 2 * math.pi * k / 3
        off = (Xt * math.cos(a) + Zt * math.sin(a)) * 0.0040 * ks
        blob(cg, tip + d * 0.0150 * ks + off, 0.0038 * ks, 0.0068 * ks, 0.0038 * ks, wtt, "tuft", 1, NU=8, NV=5,
             ax=Matrix.Rotation(0.35 * math.cos(a), 3, Zt) @ Mt)
    C.add("tail", cg, subdiv=1)
    C.decal_zmin = hc.z - 0.002
    C.lid_part = "head"; C.lid_reg = "body"
# =============================================================================================== Blender assembly
BUILDERS = {"daniel": build_daniel, "king": build_king, "officer": build_officer, "lion": build_lion, "lion2": build_lion}
PIECES = []           # global piece id -> (char, part, piece); index 0 = background
REGIONS = []          # global region id -> "char.region"
PART_TRIS = {}


def region_id(ch, reg):
    key = f"{ch}.{reg}"
    if key not in REGIONS: REGIONS.append(key)
    return REGIONS.index(key) + 1


def piece_id(key):
    if key not in PIECES: PIECES.append(key)
    return PIECES.index(key) + 1


def eyelid_cage(C, face_obj, sheet):
    """Two thin skin lids parked above the eyes (rest = open); scaling the `eyelids` bone along its length (local Y,
    pointing down) by ~closedScale closes them over the eyes."""
    me = face_obj.data
    vs = [to_design(face_obj.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    bvh = BVHTree.FromPolygons([tuple(v) for v in vs], [tuple(p.vertices) for p in me.polygons])
    ex, ey, ew, eh = C.F["eyeLocal"]
    top, h0 = C.lid["top"], C.lid["h0"]
    cg = Cage()
    for sx in (-1, 1):
        cols = []
        for i in range(8):
            x = sx * ex + (i / 7 - 0.5) * 2 * 1.32 * ew
            col = []
            for j in range(4):
                y = top - h0 * j / 3
                if C.ch in LIONS:
                    # a lion's head is round: the eye surface lies in front of the brow, so each lid row sits on the
                    # most forward head point over its whole travel (rest -> closed), never inside the head
                    d0 = h0 * j / 3; d1 = max(d0, h0 * j / 3 * 12.8, (top - C.lid["closed"]) * j / 3)
                    zs = []
                    for k in range(9):
                        hit = bvh.ray_cast(V(x, top - lerp(d0, d1, k / 8), 0.2), V(0, 0, -1), 1.0)
                        if hit[0]:
                            zs.append(hit[0].z)
                    z = (max(zs) + 0.0006) if zs else None
                    col.append(V(x, y, z if z is not None else 0.0)); continue
                hit = bvh.ray_cast(V(x, y, 0.2), V(0, 0, -1), 1.0)
                z = (hit[0].z if hit[0] else (col[-1].z - 0.00055 * C.S if col else 0.0)) + 0.00055 * C.S
                col.append(V(x, y, z))
            cols.append(col)
        if C.ch in LIONS:                        # columns that missed the head take the nearest column's depth
            good = [i for i, c in enumerate(cols) if all(abs(p.z) > 1e-9 for p in c)]
            for i, c in enumerate(cols):
                for j, p in enumerate(c):
                    if abs(p.z) < 1e-9 and good:
                        k = min(good, key=lambda g: abs(g - i))
                        p.z = cols[k][j].z
        idx = [[cg.add(p, None) for p in col] for col in cols]
        for i in range(7):
            for j in range(3):
                cg.face((idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1]), C.lid_reg, 0)
    C.lid["closedScale"] = round((C.lid["top"] - C.lid["closed"]) / C.lid["h0"], 2)
    return cg


def make_part_object(C, ch, pt, sheet, rig):
    cg = pt["cage"]
    o = new_mesh_obj(f"{ch}_{pt['name']}", [to_bl(v) for v in cg.v], cg.f)
    pkey = pt.get("piece_as")
    pids = [piece_id((ch, pkey or pt["name"], k if not pkey else 0)) for k in cg.pc]
    rids = [region_id(ch, r) for r in cg.reg]
    a1 = o.data.attributes.new("st_piece", 'INT', 'FACE'); a1.data.foreach_set("value", pids)
    a2 = o.data.attributes.new("st_region", 'INT', 'FACE'); a2.data.foreach_set("value", rids)
    rigid = pt.get("rigid")
    if not rigid:
        groups = {}
        for i, w in enumerate(cg.w):
            for b, v in w.items():
                if v > 1e-4: groups.setdefault(b, []).append((i, v))
        for b, lst in groups.items():
            g = o.vertex_groups.get(b) or o.vertex_groups.new(name=b)
            for i, v in lst: g.add([i], v, 'REPLACE')
    fix_normals(o)
    if pt.get("subdiv", 1):
        apply_subsurf(o, pt.get("subdiv", 1))
    fix_normals(o)
    if pt.get("post"):
        me = o.data
        pts = [to_design(v.co) for v in me.vertices]; nrm = [to_design(v.normal) for v in me.vertices]
        for v, p in zip(me.vertices, pt["post"](pts, nrm)):
            v.co = to_bl(p)
        me.update()
    if pt.get("smooth"):
        zone, iters = pt["smooth"]
        bm = bmesh.new(); bm.from_mesh(o.data)
        vs = [v for v in bm.verts if zone(to_design(v.co))]
        for _ in range(iters):
            bmesh.ops.smooth_vert(bm, verts=vs, factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
        bm.to_mesh(o.data); bm.free(); o.data.update()
    if pt.get("cull"):
        bm = bmesh.new(); bm.from_mesh(o.data)
        hid = {v.index: pt["cull"](to_design(v.co)) for v in bm.verts}
        dead = [f for f in bm.faces if all(hid[v.index] for v in f.verts)]
        bmesh.ops.delete(bm, geom=dead, context='FACES_ONLY')
        loose = [v for v in bm.verts if not v.link_faces]
        bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bm.to_mesh(o.data); bm.free(); o.data.update()
    if pt.get("solidify"):
        apply_solidify(o, pt["solidify"])
    if pt.get("sharp"):
        o.data.set_sharp_from_angle(angle=math.radians(pt["sharp"]))
    o.parent = rig
    if rigid:
        o.parent_type = 'BONE'; o.parent_bone = rigid
    o.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    o.matrix_world = Matrix.Translation((sheet[0], 0, sheet[1]))
    bpy.context.view_layer.update()
    PART_TRIS[o.name] = tri_count([o])
    return o


def finish_uv1_and_jaw(C, ch, o, pt, sheet):
    me = o.data
    L = C.L; H = C.H; S = C.S
    dec = C.F["rect"]
    vco = [to_design(o.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    vn = [to_design(o.matrix_world.to_3x3() @ v.normal).normalized() for v in me.vertices]
    if not me.uv_layers.get("UVMap"):                 # page UV must be layer 0 (TEXCOORD_0), decal layer 1
        me.uv_layers.new(name="UVMap")
    uv1 = me.uv_layers.get("decal") or me.uv_layers.new(name="decal")
    dus = []
    for p, n in zip(vco, vn):
        if pt.get("decal"):
            du = (p.x - dec[0]) / (dec[2] - dec[0]); dv = (p.y - dec[1]) / (dec[3] - dec[1])
            if p.z < C.decal_zmin or n.z < 0.3:
                if abs(dv - 0.5) > 0.45:
                    dv = 4.0 if dv > 0.5 else -3.0
                else:
                    du = 4.0 if du > 0.5 else -3.0
            dus.append((du, dv))
        else:
            dus.append((-1.0, -1.0))
    for poly in me.polygons:
        for li in poly.loop_indices:
            uv1.data[li].uv = dus[me.loops[li].vertex_index]
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


def bake_rest_pose(C, rig, body, poses):
    """Pose bones (design axis, degrees), apply that pose to the skinned body and make it the new rest pose of the rig
    (rigid props parented to bones keep their posed place). Used for Naomi's stoop."""
    props = [o for o in rig.children if o.parent_type == 'BONE']
    for bone, axis, deg in poses:
        bend(rig, bone, axis, deg)
    bpy.context.view_layer.update()
    keep = {o.name: o.matrix_world.copy() for o in props}
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = body; body.select_set(True)
    bpy.ops.object.modifier_apply(modifier="Armature")
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = rig; rig.select_set(True)
    bpy.ops.object.mode_set(mode='POSE')
    bpy.ops.pose.select_all(action='SELECT')
    bpy.ops.pose.armature_apply(selected=False)
    bpy.ops.object.mode_set(mode='OBJECT')
    bpy.context.view_layer.update()
    moved = 0.0
    for o in props:
        moved = max(moved, (o.matrix_world.translation - keep[o.name].translation).length)
        o.matrix_world = keep[o.name]
    bpy.context.view_layer.update()
    am = body.modifiers.new("Armature", 'ARMATURE'); am.object = rig
    return moved


REST_BAKE = {}      # no baked rest poses in this pack (kept for the shared bake_rest_pose helper)
LION2_PAGE = (0.02, 0.105, 0.34)   # lion2 virtual page: side-view centre (X, Y) and width of lion2_paint.png


def is_hidden_prop(o):
    ch, _, part = o.name.partition("_")
    return PROPS.get(ch, {}).get(part) is False


def side_uv(objs, sheet, to_uv, inset):
    """Lions (CONTRACT §2): UV0 = SIDE projection of the lion's left side (+X) at its slot: page X = -z (nose to -X),
    page Y = y. Every vertex is mirrored to the left side first (|x|), so the right side samples the drawing of the
    left side (a symmetric lion matches). A face keeps the projection when all its (mirrored) corners face +X and a
    ray from each toward +X meets nothing of another region; otherwise it is flagged st_hidden = 1 and later takes
    one clean texel of its own region (side_texels). to_uv(X, Y) maps page side coords (character-local) to UV."""
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


def side_texels(id_png, ids, chars, to_uv_px=None):
    """Faces flagged st_hidden (lions) take one texel: the deepest pixel of their own (character, region) in the
    given ID render (the printed sheet for the lion, the virtual page for lion2)."""
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
    """Turn a lion rig so its left side faces the front ortho camera (local +X -> world +Z design, nose to -X)."""
    rig.rotation_euler = (0, 0, math.radians(-90) if on else 0.0)
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
    for b in bone_list(ch):                      # every contract bone has a vertex group (lion2's `mane` stays empty)
        if not bodyo.vertex_groups.get(b) and b not in PROPS[ch] and b != "eyelids":
            bodyo.vertex_groups.new(name=b)
    if ch in LIONS:
        if ch == "lion":
            to_uv = lambda X, Y: (X + sheet[0] + 0.5, (Y + sheet[1]) / ART_H)
            stats = side_uv([bodyo] + props, sheet, to_uv, INSET)
        else:
            cx, cy, Wd = LION2_PAGE
            to_uv = lambda X, Y: ((X - cx) / Wd + 0.5, (Y - cy) / Wd + 0.5)
            stats = side_uv([bodyo] + props, sheet, to_uv, INSET * 0.5)
    else:
        vis = [bodyo] + [o for o in props if not is_hidden_prop(o)]
        stats = front_uv_with_occlusion([(o, o is not bodyo) for o in vis], sheet, ART_H, INSET,
                                        anchors=None, region_name=lambda r: REGIONS[r - 1].split(".")[1])
    # regions / bbox report (page coordinates: front view for humans, side view for the lion); hidden props and
    # eyelids do not count for the bbox
    rep = {"regions": {}, "parts": {}, "uvStats": stats}
    for o in [bodyo] + props:
        me = o.data; rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
        pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
        for poly, r, pp in zip(me.polygons, rid, pid):
            reg = REGIONS[r - 1].split(".")[1]
            d = rep["regions"].setdefault(reg, {"parts": set(), "bb": [9, 9, -9, -9]})
            pname = PIECES[pp - 1][1]
            d["parts"].add(pname)
            if o.name.endswith("_eyelids") or is_hidden_prop(o):
                continue
            for vi in poly.vertices:
                p = to_design(o.matrix_world @ me.vertices[vi].co)
                if ch in LIONS:
                    p = V(sheet[0] - (p.z), p.y, 0)
                bb = d["bb"]; bb[0] = min(bb[0], p.x); bb[1] = min(bb[1], p.y); bb[2] = max(bb[2], p.x); bb[3] = max(bb[3], p.y)
    return C, rig, bodyo, props, rep

# =============================================================================================== shared costume bits
def ears_spec(C):
    L = C.L; H = C.H; k = H / 0.0535
    return (L["chin"] + 0.31 * H, L["chin"] + 0.55 * H, 0.0078 * k, 0.0027 * k)


def head_surface(C, x, y, off=0.0):
    """Point on the target head surface in front at (x, y) (search over u), pushed out along the normal."""
    best = None
    for k in range(-60, 61):
        u = (k / 240.0) % 1.0
        p = C.head.at(u, y)
        dd = abs(p.x - x)
        if best is None or dd < best[0]:
            best = (dd, u, p)
    _, u, p = best
    return p + C.head.normal(u, y) * off, C.head.normal(u, y)


def build_beard(C, top_tab, bot_tab, thick_fn, curls_fn, umax, bottom_y, name="beard", reg="beard", NU=21, NV=11,
                solid=0.0045):
    Hd = C.head; L = C.L; zc = L["zc"]; chin = L["chin"]
    cg = Cage(); wfn = C.w(["head"])

    def base(u, y):
        if y >= chin + 0.004 * C.S:
            return Hd.at(u, y), Hd.normal(u, y)
        y0 = chin + 0.004 * C.S
        pc = Hd.at(u, y0); n = Hd.normal(u, y0)
        t = (y0 - y) / max(1e-6, (y0 - bottom_y))
        p = V(pc.x * (1 - 0.50 * t), y, zc + (pc.z - zc) * (1 - 0.20 * t * t) - 0.002 * C.S * t)
        return p, (n + V(0, -0.7 * t, 0.2 * t)).normalized()
    us = [-umax + 2 * umax * i / (NU - 1) for i in range(NU)]
    rows = []
    for j in range(NV + 1):
        v = j / NV; row = []
        for u in us:
            uu = abs(u)
            yt = table(top_tab, uu)[0]; yb = table(bot_tab, uu)[0]
            y = lerp(yt, yb, v)
            p, n = base(u % 1.0, y)
            row.append(p + n * thick_fn(uu, y, v) - n * 0.0008 * C.S * (1 - smoothstep(0.0, 0.12, v)))
        rows.append(cg.ring(row, wfn))
    for a, b in zip(rows, rows[1:]):
        cg.bridge(a, b, reg, 0, closed=False)

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            u = math.atan2(p.x, p.z - zc) / (2 * math.pi)
            out.append(p + n * curls_fn(u, p.y))
        return out
    C.add(name, cg, post=post, solidify=solid * C.S, decal=True, jaw=True, subdiv=0, jawBelow=0.6, jawZ=-0.03)


def moustache(C, name, y0, half_w, droop, curl, r0, reg="beard", off=0.0016):
    L = C.L; S = C.S
    cg = Cage(); wfn = C.w(["head"])
    for sx in (-1, 1):
        path, rad = [], []
        for i in range(9):
            f = i / 8
            x = sx * (0.02 + 0.98 * f) * half_w
            y = y0 - droop * f ** 1.6 + curl * smoothstep(0.65, 1.0, f) ** 2
            p, n = head_surface(C, x, y, off * S + r0 * (1 - 0.6 * f))
            if f > 0.7:
                p += V(sx * 0.0008 * S * (f - 0.7) / 0.3, 0, 0.0006 * S * (f - 0.7) / 0.3)
            path.append(p); rad.append((r0 * (1 - 0.55 * f ** 1.3) * 0.75, r0 * (1 - 0.55 * f ** 1.3)))
        rad[-1] = (rad[-1][0] * 0.5, rad[-1][1] * 0.5)
        tube(cg, path, rad, 8, wfn, reg, 1, cap0=True, cap1=True)
    C.add(name, cg, subdiv=0, decal=True)


def finger_ring(C, side, reg, pc=0):
    """Signet ring on the ring finger's first segment (rigid, `ring` bone)."""
    fg = C.fingers[side][2]; n0, p1, dirn = fg["joints"][0]
    c = n0.lerp(p1, 0.55)
    A = C.arm[side]; hd = C.s["handDims"]
    rr = hd["fingerW"] * 0.60
    cg = Cage()
    a0 = perp(A["Xh"], dirn); b0 = dirn.cross(a0)
    pts = [c + a0 * math.cos(2 * math.pi * k / 12) * rr + b0 * math.sin(2 * math.pi * k / 12) * rr for k in range(12)]
    nrm = [(p - c).normalized() for p in pts]
    band_loop(cg, pts, nrm, [dirn] * 12, 0.0009 * C.S, 0.0006 * C.S, None, reg, pc)
    M = Matrix((b0, dirn, a0)).transposed()
    blob(cg, c + a0 * (rr + 0.0010 * C.S), 0.0017 * C.S, 0.0021 * C.S, 0.0008 * C.S, None, reg, pc, NU=10, NV=5, ax=M)
    C.add("ring", cg, subdiv=0, rigid="ring")
    C.B["ring"] = (c, c + dirn * 0.004 * C.S, "hand" + side)


def head_lathe(C, base_y, prof, N, wfn, reg, pc, cg, extra_x=0.0, extra_f=0.0, extra_b=0.0, e=2.3, tilt=0.0):
    """Surface of revolution around the head (crown, cap): rings at base_y + dy with scale k of the head section at
    base_y (+ clearances). prof = [(dy, k)], k = 0 closes with a pole. tilt (rad) tips it back about the base."""
    Hd = C.head; zc = C.L["zc"]
    rx = abs(Hd.at(0.25, base_y).x) + extra_x
    zf = Hd.at(0.0, base_y).z + extra_f; zb = Hd.at(0.5, base_y).z - extra_b
    zcc = (zf + zb) / 2; rz = (zf - zb) / 2
    pivot = V(0, base_y, zcc)
    R = Matrix.Rotation(-tilt, 3, V(1, 0, 0))
    rings = []
    for dy, k in prof:
        if k <= 0:
            rings.append(None); continue
        pts = [V(se(math.sin(2 * math.pi * j / N), e) * rx * k, base_y + dy, zcc + se(math.cos(2 * math.pi * j / N), e) * rz * k)
               for j in range(N)]
        rings.append(cg.ring([pivot + R @ (p - pivot) for p in pts], wfn))
    for i in range(len(prof) - 1):
        a, b = rings[i], rings[i + 1]
        if a and b:
            cg.bridge(a, b, reg, pc)
        elif a and b is None:
            cg.fan(a, pivot + R @ V(0, prof[i + 1][0], 0), wfn, reg, pc)
    return dict(rx=rx, rz=rz, zc=zcc, pivot=pivot, R=R)
# =============================================================================================== render helpers
def setup_workbench(res):
    s = sc(); s.render.engine = 'BLENDER_WORKBENCH'
    s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
    s.render.dither_intensity = 0.0
    s.render.resolution_x, s.render.resolution_y = res; s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGBA'
    sh = s.display.shading
    sh.show_cavity = False; sh.show_shadows = False; sh.show_object_outline = False; sh.show_specular_highlight = False


def front_ortho_camera():
    cam = camera(); cam.data.type = 'ORTHO'; cam.data.ortho_scale = ART_H; cam.data.sensor_fit = 'AUTO'
    cam.location = (0.0, -20.0, ART_H / 2); cam.rotation_euler = (math.radians(90), 0, 0)
    return cam


def set_face_materials(o, key_fn, mat_fn):
    me = o.data
    pid = [0] * len(me.polygons); rid = [0] * len(me.polygons)
    me.attributes["st_piece"].data.foreach_get("value", pid); me.attributes["st_region"].data.foreach_get("value", rid)
    me.materials.clear(); slots = {}; idx = []
    for p, r in zip(pid, rid):
        k = key_fn(p, r)
        if k not in slots:
            slots[k] = len(slots); me.materials.append(mat_fn(k))
        idx.append(slots[k])
    me.polygons.foreach_set("material_index", idx)


def page_material():
    m = bpy.data.materials.get("da_page") or bpy.data.materials.new("da_page")
    m.diffuse_color = (1, 1, 1, 1)
    return m


def all_meshes():
    return [o for o in sc().objects if o.type == 'MESH']


def apply_pixel_anchors(id_png, ids):
    """Constant UV0 for (a) regions too small to colour (ANCHORS), (b) hidden-by-default props that are not printed
    (PROP_ANCHORS, or design.json characters.<id>.propUV), (c) sliver parts (PART_ANCHORS: hands, feet).
    A target "char.region" = the deepest pixel (farthest from any other region / the paper) of that region in the
    front ID render; "char.FACE" = the same for the face skin with the eyes / brows / nose / mouth masked out."""
    import numpy as np
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)          # rows bottom -> top
    rgb = np.round(px[..., :3] * 255).astype(np.int32)
    key = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    alpha = px[..., 3] > 0.5
    cache = {}

    def set_mask(treg):
        """Mask of a set region in the set's page-space ID render, returned in art-rect UV pixels (2x)."""
        sj = os.path.join(MODEL, "set_id_2x.json"); sp = os.path.join(MODEL, "set_id_2x.png")
        if not (os.path.exists(sj) and os.path.exists(sp) and os.path.exists(DESIGN_JSON)):
            return None
        meta = json.load(open(sj)); art = json.load(open(DESIGN_JSON)).get("sheet", {}).get("art")
        if not art:
            return None
        sc_ = meta.get("scale", 2)
        im2 = bpy.data.images.load(sp, check_existing=False)
        W2, H2 = im2.size
        R = np.round(np.array(im2.pixels[:], dtype=np.float32).reshape(H2, W2, 4)[..., 0] * 255).astype(int)
        bpy.data.images.remove(im2)                                         # rows bottom -> top
        idl = [e["id"] for e in meta["ids"] if e["region"] == treg]
        if not idl:
            return None
        AX, AY, AW, AH = art
        crop = R[H2 - int((AY + AH) * sc_):H2 - int(AY * sc_), int(AX * sc_):int((AX + AW) * sc_)]
        m = np.isin(crop, idl)
        return m, m.shape[1], m.shape[0]

    def target_uv(tgt):
        if isinstance(tgt, (list, tuple)):
            for t in tgt:
                uv = target_uv(t)
                if uv:
                    cache[tuple(tgt)] = (uv, t)
                    return uv
            return None
        if tgt in cache:
            return cache[tgt]
        tch, treg = tgt.split(".")
        if tch == "set":
            r = set_mask(treg)
            if r is None or not r[0].any():
                cache[tgt] = None; return None
            m, Wm, Hm = r
            last = m.copy(); mm = m.copy()
            while mm.any():
                last = mm
                e = mm.copy()
                e[1:, :] &= mm[:-1, :]; e[:-1, :] &= mm[1:, :]; e[:, 1:] &= mm[:, :-1]; e[:, :-1] &= mm[:, 1:]
                mm = e
            ys, xs = np.nonzero(last)
            k = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
            cache[tgt] = ((xs[k] + 0.5) / Wm, (ys[k] + 0.5) / Hm)
            return cache[tgt]
        if treg == "FACE":
            keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids
                    if e["char"] == tch and e["part"] == "face" and e["region"] == "skin"]
            mask = np.isin(key, keys) & alpha
            F = face_layout(tch); L = landmarks(tch); Hh = L["top"] - L["chin"]; hw = SPEC[tch]["hw"]
            sX, sY = SHEET[tch]
            yy, xx = np.mgrid[0:H, 0:W]
            lx = (xx + 0.5) / W - 0.5 - sX; ly = (yy + 0.5) / H * ART_H - sY
            ex, ey, ew, eh = F["eyeLocal"]
            feat = (np.abs(np.abs(lx) - ex) < ew * 1.7) & (ly > ey - eh * 2.2) & (ly < L["brow"] + 0.16 * Hh)
            feat |= (np.abs(lx) < 0.42 * hw) & (np.abs(ly - L["mouth"]) < 0.13 * Hh)
            feat |= (np.abs(lx) < 0.26 * hw) & (ly > L["nose"] - 0.07 * Hh) & (ly < ey)
            mask &= ~feat
        else:
            keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids
                    if e["char"] == tch and e["region"] == treg]
            mask = np.isin(key, keys) & alpha
        if not mask.any():
            print("ANCHOR: empty target", tgt); cache[tgt] = None; return None
        last = mask; m = mask.copy()
        while m.any():
            last = m
            e = m.copy()
            e[1:, :] &= m[:-1, :]; e[:-1, :] &= m[1:, :]; e[:, 1:] &= m[:, :-1]; e[:, :-1] &= m[:, 1:]
            m = e
        ys, xs = np.nonzero(last)
        k = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
        cache[tgt] = ((xs[k] + 0.5) / W, (ys[k] + 0.5) / H)
        return cache[tgt]

    def assign(ch, reg, uv, part=None):
        rid = REGIONS.index(f"{ch}.{reg}") + 1 if f"{ch}.{reg}" in REGIONS else None
        if rid is None:
            return 0
        n = 0
        for o in all_meshes():
            if not o.name.startswith(ch + "_"):
                continue
            me = o.data; rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
            pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
            uv0 = me.uv_layers["UVMap"]
            for poly, r, pp in zip(me.polygons, rr, pid):
                if r == rid and (part is None or PIECES[pp - 1][1] == part):
                    n += 1
                    for li in poly.loop_indices:
                        uv0.data[li].uv = uv
        return n
    out = {}
    for ch in ONLY:
        o_ = out.setdefault(ch, {"anchors": {}, "propAnchors": {}, "partAnchors": {}})
        for reg, tgt in ANCHORS.get(ch, {}).items():
            uv = target_uv(tgt)
            if uv:
                assign(ch, reg, uv)
                o_["anchors"][reg] = {"target": tgt.split(".")[1] if tgt.startswith(ch + ".") else tgt,
                                      "uv": [round(uv[0], 5), round(uv[1], 5)]}
        for reg, tgt in PROP_ANCHORS.get(ch, {}).items():
            uv = tuple(PROP_UV[ch][reg]) if reg in PROP_UV.get(ch, {}) else target_uv(tgt)
            src = "design.json propUV" if reg in PROP_UV.get(ch, {}) else cache.get(tuple(tgt), (None, tgt))[1]
            if uv:
                if src.endswith(".FACE"):          # FACE = a texel of that face's printed skin, clear of the features
                    src = src[:-len("FACE")] + "skin"
                assign(ch, reg, uv); o_["propAnchors"][reg] = {"target": src, "uv": [round(uv[0], 5), round(uv[1], 5)]}
        for (part, reg), tgt in PART_ANCHORS.get(ch, {}).items():
            uv = target_uv(tgt)
            if uv:
                sX, sY = SHEET[ch]
                assign(ch, reg, uv, part)
                o_["partAnchors"][f"{part}.{reg}"] = {"target": tgt, "uv": [round(uv[0], 5), round(uv[1], 5)],
                                                      "local": [round(uv[0] - 0.5 - sX, 4), round(uv[1] * ART_H - sY, 4)]}
    bpy.data.images.remove(img)
    return out


def fix_uvs_by_id(id_png, ids, erode=5):
    """Final UV0 check against the front ID render (= the printed drawing): every face corner must sample a pixel of
    its own character + region at least `erode` px (2x render) inside the outline. Corners that land elsewhere (back
    of the head projected onto the face, a hidden cape behind the robe, an inset that crossed a thin band) move to
    the nearest such pixel. Anchored regions and eyelids are left alone."""
    import numpy as np
    from mathutils.kdtree import KDTree
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)
    rgb = np.round(px[..., :3] * 255).astype(np.int64)
    key = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    alpha = px[..., 3] > 0.5
    labels = {}
    lab = np.full((H, W), -1, np.int32)
    for e in ids:
        L = labels.setdefault((e["char"], e["region"]), len(labels))
        lab[(key == e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2]) & alpha] = L
    er = np.full((H, W), -1, np.int32)
    kds = {}
    for (ch, reg), L in labels.items():
        m = lab == L
        for it in range(erode, -1, -1):
            e = m.copy()
            for _ in range(it):
                f = e.copy()
                f[1:, :] &= e[:-1, :]; f[:-1, :] &= e[1:, :]; f[:, 1:] &= e[:, :-1]; f[:, :-1] &= e[:, 1:]
                e = f
            if e.sum() >= 4:
                break
        er[e] = L
        ys, xs = np.nonzero(e)
        step = 2 if len(xs) > 40000 else 1
        kd = KDTree(len(xs[::step]))
        for i, (x, y) in enumerate(zip(xs[::step], ys[::step])):
            kd.insert((float(x), float(y), 0.0), i)
        kd.balance()
        kds[L] = (kd, xs[::step], ys[::step])
    moved = {}; total = 0
    for o in all_meshes():
        ch = o.name.split("_")[0]
        if ch not in ONLY or o.name.endswith("_eyelids"):
            continue
        me = o.data; rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
        uv0 = me.uv_layers["UVMap"]
        skip = set(ANCHORS.get(ch, {}).keys()) | set(PROP_ANCHORS.get(ch, {}).keys())
        pskip = set(PART_ANCHORS.get(ch, {}).keys())
        if is_hidden_prop(o):
            continue
        pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
        for poly, r, pp in zip(me.polygons, rr, pid):
            reg = REGIONS[r - 1].split(".")[1]
            if reg in skip or (PIECES[pp - 1][1], reg) in pskip or (ch, reg) not in labels:
                continue
            L = labels[(ch, reg)]
            pts = []
            bad = False
            for li in poly.loop_indices:
                total += 1
                u, v = uv0.data[li].uv
                x = min(W - 1, max(0, int(u * W))); y = min(H - 1, max(0, int(v * H)))
                pts.append((x, y))
                if er[y, x] != L:
                    bad = True
            if not bad:
                continue
            # the whole face moves to one interior pixel near its projected centre (no streaks across regions)
            cx = sum(p[0] for p in pts) / len(pts); cy = sum(p[1] for p in pts) / len(pts)
            kd, xs, ys = kds[L]
            _, i, _ = kd.find((cx, cy, 0.0))
            for li in poly.loop_indices:
                uv0.data[li].uv = ((xs[i] + 0.5) / W, (ys[i] + 0.5) / H)
            moved[f"{ch}.{reg}"] = moved.get(f"{ch}.{reg}", 0) + 1
    bpy.data.images.remove(img)
    return {"corners": total, "facesMoved": moved}


# =============================================================================================== modes
def id_materials(objs, idmap):
    def mat_fn(k):
        if k not in idmap:
            idmap[k] = len(idmap) + 1
        n = idmap[k]
        return flat_mat(f"id_{n}", [c / 255 for c in id_colour(n)])
    for o in objs:
        set_face_materials(o, lambda p, r: (p, r), mat_fn)


def id_list(idmap):
    ids = []
    for (p, r), n in sorted(idmap.items(), key=lambda kv: kv[1]):
        ch, pname, k = PIECES[p - 1]; rch, reg = REGIONS[r - 1].split(".")
        ids.append({"id": n, "rgb": id_colour(n), "char": ch, "part": pname, "piece": k, "region": reg,
                    "hex": PALETTE[ch].get(reg, "#cccccc")})
    return ids


def make_lion2_paint(id_png, ids, margin=14):
    """model/lion2_paint.png from lion2's side ID render on her virtual page: every region flat in its demo colour,
    a little crayon grain, a soft darker back and lighter belly (from the height inside the silhouette), colours
    grown 14 px into the paper so nothing bleeds at the silhouette."""
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
    yy = np.mgrid[0:H, 0:W][0] / H                                   # rows bottom -> top
    shade = 1.0 + 0.06 * (0.5 - yy) * 2.0                              # a touch darker on the back, lighter below
    col *= shade[..., None]
    rng = np.random.default_rng(11)
    g = rng.normal(0, 1, (H // 8 + 2, W // 8 + 2)).astype(np.float32)
    g = (g[:-1, :-1] + g[1:, :-1] + g[:-1, 1:] + g[1:, 1:]) / 4          # soft grain, no blocky pixels
    g = np.repeat(np.repeat(g, 8, 0), 8, 1)[:H, :W]
    col *= (1.0 + 0.012 * g)[..., None]
    for _ in range(margin):
        grow = ~have
        for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            src = np.roll(np.roll(have, dy, 0), dx, 1) & grow
            c2 = np.roll(np.roll(col, dy, 0), dx, 1)
            col[src] = c2[src]; have |= src; grow &= ~src
    bgc = np.array([int(PALETTE["lion2"]["body"].lstrip("#")[i:i + 2], 16) / 255 for i in (0, 2, 4)], np.float32)
    col[~have] = bgc
    out = np.ones((H, W, 4), np.float32); out[..., :3] = np.clip(col, 0, 1)
    im = bpy.data.images.new("lion2_paint", W, H, alpha=True)
    im.pixels.foreach_set(out.ravel())
    im.filepath_raw = LION2_PAINT; im.file_format = 'PNG'; im.save()
    bpy.data.images.remove(im)


def lion2_paint_material():
    m = bpy.data.materials.get("da_lion2_paint") or bpy.data.materials.new("da_lion2_paint")
    m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF")
    b.inputs["Roughness"].default_value = 0.8
    img = bpy.data.images.load(LION2_PAINT, check_existing=True)
    t = nt.nodes.get("paint") or nt.nodes.new("ShaderNodeTexImage"); t.name = "paint"; t.image = img
    uvn = nt.nodes.get("uv0") or nt.nodes.new("ShaderNodeUVMap"); uvn.name = "uv0"; uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    return m


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
        print(f"[{ch}] tris={tris} body={tri_count([body])} props={[(o.name, tri_count([o])) for o in props]}")
    sheet_chars = [c for c in ONLY if c in ON_SHEET]
    # ---- sheet ID render (front ortho, 2x art rect, no AA): one colour per (piece, region); eyelids and hidden props
    # hidden; the lion turned to show its left side (nose to -X); lion2 is not on the sheet
    setup_workbench((2000, round(2000 * ART_H)))
    s = sc(); s.render.film_transparent = True; s.display.render_aa = 'OFF'
    s.display.shading.light = 'FLAT'; s.display.shading.color_type = 'MATERIAL'
    cam = front_ortho_camera()
    if "lion" in built:
        side_rotate(built["lion"][1], True)
    idmap = {}
    on = [o for o in all_meshes() if o.name.split("_")[0] in sheet_chars]
    for o in all_meshes():
        o.hide_render = o not in on or o.name.endswith("_eyelids") or is_hidden_prop(o)
    id_materials(on, idmap)
    render(os.path.join(WORK, "id_2x.png"))
    ids = id_list(idmap)
    json.dump({"note": "front-ortho ID render of the rest pose at sheet positions (2000 px = art width); background = "
                       "alpha 0; eyelids hidden; the lion is drawn in side view (its left side, nose to -X)",
               "size": [s.render.resolution_x, s.render.resolution_y], "ids": ids},
              open(os.path.join(WORK, "id_2x.json"), "w"), indent=1)
    for o in all_meshes():
        o.hide_render = False
    anchor_info = apply_pixel_anchors(os.path.join(WORK, "id_2x.png"), ids)
    report["lionTexels"] = side_texels(os.path.join(WORK, "id_2x.png"), ids, [c for c in ("lion",) if c in built])
    fix_info = fix_uvs_by_id(os.path.join(WORK, "id_2x.png"), ids)
    report["uvFixByIdRender"] = fix_info
    if "lion" in built:
        side_rotate(built["lion"][1], False)
    # ---- lion2: side ID render on her virtual page -> lion2_paint.png, texels, UV fix
    if "lion2" in built:
        rig2 = built["lion2"][1]; side_rotate(rig2, True)
        cx, cy, Wd = LION2_PAGE; sx2, sy2 = SHEET["lion2"]
        s.render.resolution_x = s.render.resolution_y = 1024
        cam.data.ortho_scale = Wd
        cam.location = (sx2 + cx, -20.0, sy2 + cy)
        mine = [o for o in all_meshes() if o.name.startswith("lion2_")]
        for o in all_meshes():
            o.hide_render = o not in mine or o.name.endswith("_eyelids")
        idmap2 = {}
        id_materials(mine, idmap2)
        p2 = os.path.join(WORK, "lion2_id.png")
        render(p2)
        ids2 = id_list(idmap2)
        json.dump({"ids": ids2}, open(os.path.join(WORK, "lion2_id.json"), "w"), indent=1)
        for o in all_meshes():
            o.hide_render = False
        report["lion2Texels"] = side_texels(p2, ids2, ["lion2"])
        report["lion2UvFix"] = fix_uvs_by_id(p2, ids2)
        make_lion2_paint(p2, ids2)
        side_rotate(rig2, False)
    # ---- regions_characters.json
    regions_out = {"version": 1, "generatedBy": "pipeline/da_characters.py",
                   "note": "Per character: colourable regions (face attribute st_region), the mesh parts that carry "
                           "them, demo colour, bbox on the sheet (x, y in art units, y up from the art rect bottom; "
                           "the lion's in side view), and anchors (regions too small to colour take a constant UV "
                           "inside a larger region). ID render for the line art: id_characters_2x.png/.json (same "
                           "scheme as Ruth). lion2 is not on the sheet: her UV0 points into model/lion2_paint.png.",
                   "sheet": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in sheet_chars},
                   "sheetSource": SHEET_SRC, "artHeightUnits": ART_H, "characters": {}}
    for ch in ONLY:
        C, rig, body, props, rep = built[ch]
        regs = {}
        allbb = [9, 9, -9, -9]
        for reg, d in rep["regions"].items():
            bb = [round(v, 4) for v in d["bb"]]
            if bb[0] < 9:
                allbb = [min(allbb[0], bb[0]), min(allbb[1], bb[1]), max(allbb[2], bb[2]), max(allbb[3], bb[3])]
            zh, en = REGION_NAMES.get(reg, (reg, reg))
            regs[reg] = {"id": REGIONS.index(f"{ch}.{reg}") + 1, "hex": PALETTE[ch].get(reg), "zh": zh, "en": en,
                         "parts": sorted(d["parts"]), "bboxSheet": (bb if bb[0] < 9 else None) if ch in ON_SHEET else None}
            ai = anchor_info.get(ch, {})
            if reg in ai.get("anchors", {}):
                an = ai["anchors"][reg]
                regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
                regs[reg]["printNote"] = ("too small to colour; print as detail line art, takes the colour at anchorUV"
                                          if an["target"] != reg else "small region: takes the colour of its own widest printed spot")
            if reg in ai.get("propAnchors", {}):
                an = ai["propAnchors"][reg]
                regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
                regs[reg]["printNote"] = ("hidden-by-default prop, not printed with the figure; takes the colour at "
                                          "anchorUV (override: design.json characters.%s.propUV.%s = [u, v])" % (ch, reg))
        lion = ch in LIONS
        entry = {
            ("shoulderHeight" if lion else "height"): CONTRACT_HEIGHT[ch],
            "bboxSheet": [round(v, 4) for v in allbb] if ch in ON_SHEET else None, "regions": regs,
            "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                          "files": {e: f"docs/daniel/design/faces/{ch}_{e}.png" for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": ({"pose": "standing on all fours, paws on the page", "facing": "+Z (nose toward the viewer)",
                          "root": "on the ground under the belly centre"} if lion else
                         {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z"}),
            "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                      for b, v in PROPS[ch].items()},
            "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
        if ch == "lion":
            entry["projection"] = {"kind": "side", "note": "UV0 = the lion's left side seen from +X: u = -z + sheetX + "
                                   "0.5, v = (y + sheetY) / artH (character-local x mirrored to |x|, so both sides "
                                   "share the drawing); faces not seen from the side take one clean texel of their "
                                   "own region"}
        if ch == "lion2":
            entry["paint"] = "lion2_paint.png"
            entry["projection"] = {"kind": "side", "page": "virtual", "note": "UV0 points into model/lion2_paint.png "
                                   "(u = (-z - %.3f) / %.3f + 0.5, v = (y - %.3f) / %.3f + 0.5)" % (LION2_PAGE[0], LION2_PAGE[2], LION2_PAGE[1], LION2_PAGE[2])}
        regions_out["characters"][ch] = entry
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
    if SHEET_SRC == "defaults":
        json.dump({"note": "default sheet positions used by da_characters.py (assets/daniel/design.json had none); "
                           "the Set + sheet role owns the real values in design.json characters.<id>.sheetX/sheetY",
                   "artHeightUnits": ART_H,
                   "characters": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in ON_SHEET}},
                  open(os.path.join(WORK, "characters_layout.json"), "w"), indent=1)
    if set(ON_SHEET) <= set(ONLY):
        shutil.copy(os.path.join(WORK, "id_2x.png"), os.path.join(MODEL, "id_characters_2x.png"))
        shutil.copy(os.path.join(WORK, "id_2x.json"), os.path.join(MODEL, "id_characters_2x.json"))
    # ---- final material, export (character-local), blend
    page = page_material()
    paint2 = lion2_paint_material() if "lion2" in built else None
    for o in all_meshes():
        m = paint2 if o.name.startswith("lion2_") else page
        me = o.data; me.materials.clear(); me.materials.append(m)
        me.polygons.foreach_set("material_index", [0] * len(me.polygons))
    for o in all_meshes():                       # TEXCOORD_0 = page (UVMap), TEXCOORD_1 = face decal
        assert [u.name for u in o.data.uv_layers][:2] == ["UVMap", "decal"], (o.name, [u.name for u in o.data.uv_layers])
        o.data.uv_layers.active_index = 0
        o.data.uv_layers["UVMap"].active_render = True
        if o.data.attributes.get("st_hidden"):
            pass
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
    sc()["da_regions"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({ch: {k: v for k, v in r.items() if k != "bones"} for ch, r in report["chars"].items()}))


GOLD = {"collar", "crownBand", "medallion", "ring", "headband", "belt"}


def preview_material(ch, reg, decal_img):
    name = f"pv_{ch}_{reg}"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    col = [srgb_to_lin(c) for c in hex_rgb(PALETTE[ch].get(reg, "#cccccc"))] + [1.0]
    rgb = nt.nodes.new("ShaderNodeRGB"); rgb.outputs[0].default_value = col
    if ch == "lion2" and os.path.exists(LION2_PAINT):      # the lioness wears her own painted texture (UV0)
        pimg = bpy.data.images.load(LION2_PAINT, check_existing=True)
        uvp = nt.nodes.new("ShaderNodeUVMap"); uvp.uv_map = "UVMap"
        ptx = nt.nodes.new("ShaderNodeTexImage"); ptx.image = pimg
        nt.links.new(uvp.outputs["UV"], ptx.inputs["Vector"])
        rgb = ptx
    # crayon grain: a little value noise on the colour
    tc = nt.nodes.new("ShaderNodeTexCoord"); nz = nt.nodes.new("ShaderNodeTexNoise")
    nz.inputs["Scale"].default_value = 900.0; nz.inputs["Detail"].default_value = 3.0
    nt.links.new(tc.outputs["Object"], nz.inputs["Vector"])
    mr = nt.nodes.new("ShaderNodeMapRange"); mr.inputs["To Min"].default_value = 0.93; mr.inputs["To Max"].default_value = 1.05
    nt.links.new(nz.outputs["Fac"], mr.inputs["Value"])
    mul = nt.nodes.new("ShaderNodeMix"); mul.data_type = 'RGBA'; mul.blend_type = 'MULTIPLY'
    mul.inputs["Factor"].default_value = 1.0
    nt.links.new(rgb.outputs[0], mul.inputs[6]); nt.links.new(mr.outputs[0], mul.inputs[7])
    base = mul.outputs[2]
    if decal_img is not None:
        uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "decal"
        tex = nt.nodes.new("ShaderNodeTexImage"); tex.name = "decal"; tex.image = decal_img; tex.extension = 'CLIP'
        tex.interpolation = 'Cubic'
        nt.links.new(uv.outputs["UV"], tex.inputs["Vector"])
        mix = nt.nodes.new("ShaderNodeMix"); mix.data_type = 'RGBA'
        nt.links.new(tex.outputs["Alpha"], mix.inputs["Factor"])
        nt.links.new(base, mix.inputs[6]); nt.links.new(tex.outputs["Color"], mix.inputs[7])
        base = mix.outputs[2]
    nt.links.new(base, bsdf.inputs["Base Color"])
    if reg in GOLD:
        bsdf.inputs["Metallic"].default_value = 0.30; bsdf.inputs["Roughness"].default_value = 0.45
    else:
        bsdf.inputs["Roughness"].default_value = 0.72 if reg not in ("skin", "nose") else 0.55
        if reg in ("skin", "nose"):
            try:
                bsdf.inputs["Subsurface Weight"].default_value = 0.08
                bsdf.inputs["Subsurface Radius"].default_value = (0.004, 0.002, 0.0015)
            except Exception:
                pass
        else:
            try:
                bsdf.inputs["Sheen Weight"].default_value = 0.25
            except Exception:
                pass
    return m


def setup_eevee(res):
    s = sc()
    s.render.engine = 'BLENDER_EEVEE'
    s.render.resolution_x, s.render.resolution_y = res; s.render.resolution_percentage = 100
    s.render.image_settings.file_format = 'PNG'; s.render.image_settings.color_mode = 'RGB'
    s.render.film_transparent = False
    s.view_settings.view_transform = 'Standard'; s.view_settings.look = 'None'
    s.view_settings.exposure = -0.15
    try:
        s.eevee.taa_render_samples = 48
    except Exception:
        pass
    for k, v in (("use_shadows", True), ("use_raytracing", True)):
        try:
            setattr(s.eevee, k, v)
        except Exception:
            pass


def preview_lights():
    """Studio turntable: a curved paper backdrop and three suns parented to one empty (`turn`), which is rotated with
    the camera so every view is lit the same way."""
    s = sc()
    w = bpy.data.worlds.get("pvW") or bpy.data.worlds.new("pvW"); s.world = w; w.use_nodes = True
    bg = w.node_tree.nodes.get("Background")
    bg.inputs[0].default_value = (0.86, 0.80, 0.72, 1); bg.inputs[1].default_value = 0.55
    turn = bpy.data.objects.get("turn") or bpy.data.objects.new("turn", None)
    if turn.name not in s.collection.objects:
        s.collection.objects.link(turn)
    for nm, rot, en, ang, col in (("key", (math.radians(50), 0, math.radians(-35)), 3.6, 10, (1.0, 0.94, 0.84)),
                                  ("rim", (math.radians(62), 0, math.radians(150)), 2.6, 5, (0.88, 0.92, 1.0)),
                                  ("fill", (math.radians(70), 0, math.radians(55)), 0.9, 25, (1.0, 0.97, 0.93))):
        L = bpy.data.lights.get(nm) or bpy.data.lights.new(nm, 'SUN')
        L.energy = en; L.angle = math.radians(ang); L.color = col
        o = bpy.data.objects.get(nm) or bpy.data.objects.new(nm, L)
        if o.name not in s.collection.objects:
            s.collection.objects.link(o)
        o.rotation_euler = rot; o.parent = turn
    if not bpy.data.objects.get("backdrop"):
        verts, faces = [], []
        prof = []
        for i in range(25):                     # floor toward the camera, then a quarter circle up behind
            t = i / 24
            if t < 0.5:
                prof.append((-3.0 + 3.6 * (t / 0.5), 0.0))
            else:
                a = (t - 0.5) / 0.5 * math.pi / 2
                prof.append((0.6 + math.sin(a) * 1.2, 1.2 - math.cos(a) * 1.2))
        prof.append((1.8, 5.0))
        for y, z in prof:
            verts += [(-8, y, z), (8, y, z)]
        for i in range(len(prof) - 1):
            faces.append((2 * i, 2 * i + 1, 2 * i + 3, 2 * i + 2))
        me = bpy.data.meshes.new("backdrop"); me.from_pydata(verts, [], faces)
        for pl in me.polygons: pl.use_smooth = True
        bd = bpy.data.objects.new("backdrop", me); s.collection.objects.link(bd)
        m = bpy.data.materials.new("backdropM"); m.use_nodes = True
        b = m.node_tree.nodes.get("Principled BSDF"); b.inputs["Base Color"].default_value = (0.82, 0.76, 0.66, 1)
        b.inputs["Roughness"].default_value = 0.95
        me.materials.append(m)
        bd.parent = turn


def turntable(cam, target, yaw, dist, height, lens=60):
    turn = bpy.data.objects["turn"]
    turn.location = (target.x, 0.0, 0.0)
    turn.rotation_euler = (0, 0, math.radians(yaw))
    bpy.data.objects["backdrop"].location = (0, 0.55 * dist * 0 + 0.0, 0)
    look_from(cam, target, yaw, dist, height, lens)


def char_frame(ch):
    """(height for framing, head centre y, head size) per character (character-local)."""
    if ch in LIONS:
        kx, ky, kz = LION_K[ch]
        return 0.215 * ky, LION_HEAD["c"][1] * ky, 0.060 * ky
    L = landmarks(ch); Hh = SPEC[ch]["height"] + (0.04 if ch == "king" else 0.0)
    return Hh, (L["top"] + L["chin"]) / 2, L["top"] - L["chin"]


def preview_setup():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    setup_eevee((640, 960)); preview_lights()
    imgs = {}
    for ch in CHARS:
        p = os.path.join(FACES, f"{ch}_{DEFAULT_EXPR[ch]}.png")
        if os.path.exists(p):
            imgs[ch] = bpy.data.images.load(p, check_existing=True)
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        set_face_materials(o, lambda p, r: r, lambda r, ch=ch: preview_material(ch, REGION_OF[r], imgs.get(ch)))
    return imgs


def show(chs, props=False):
    for o in all_meshes():
        if o.name not in ("floor", "backdrop"):
            o.hide_render = o.name.split("_")[0] not in chs or (is_hidden_prop(o) and not props)


def mode_preview():
    imgs = preview_setup()
    present = [ch for ch in CHARS if bpy.data.objects.get(f"{ch}_rig")]
    cam = camera()
    for ch in [c for c in ONLY if c in present]:
        show([ch])
        rig = bpy.data.objects[f"{ch}_rig"]; x = rig.location.x; zb = rig.location.z; yb = rig.location.y
        Hh, hy0, Hd = char_frame(ch)
        hy = zb + hy0
        lion = ch in LIONS
        if lion:
            sc().render.resolution_x, sc().render.resolution_y = 960, 720
            tgt = Vector((x, yb, zb + 0.105 * LION_K[ch][1]))
            for nm, yaw, h in (("front", 0, 0.03), ("q34", 35, 0.05), ("side", 90, 0.02), ("back", 180, 0.05),
                               ("phone", 28, 0.62), ("phoneSide", 70, 0.55)):
                turntable(cam, tgt, yaw, 0.82, h, 60)
                render(os.path.join(WORK, f"pv_{ch}_{nm}.png"))
            sc().render.resolution_x, sc().render.resolution_y = 640, 640
            ht = Vector((x, yb - 0.10 * LION_K[ch][2], hy - 0.004))
            turntable(cam, ht, 0, 0.30, 0.02, 60); render(os.path.join(WORK, f"pv_{ch}_headfront.png"))
            turntable(cam, ht, 32, 0.30, 0.04, 60); render(os.path.join(WORK, f"pv_{ch}_head.png"))
            turntable(cam, Vector((x, yb + 0.06, zb + 0.03)), 60, 0.35, 0.05, 60); render(os.path.join(WORK, f"pv_{ch}_legs.png"))
        else:
            sc().render.resolution_x, sc().render.resolution_y = 640, 960
            for nm, yaw in (("front", 0), ("q34", 35), ("side", 90), ("back", 180)):
                turntable(cam, Vector((x, 0, zb + Hh * 0.50)), yaw, Hh * 3.1, Hh * 0.18, 60)
                render(os.path.join(WORK, f"pv_{ch}_{nm}.png"))
            sc().render.resolution_x, sc().render.resolution_y = 640, 640
            turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 30, Hd * 4.6, Hd * 0.25, 60); render(os.path.join(WORK, f"pv_{ch}_head.png"))
            turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 0, Hd * 4.6, Hd * 0.10, 60); render(os.path.join(WORK, f"pv_{ch}_headfront.png"))
            for s_ in "LR":
                pb = rig.pose.bones["fingers" + s_]; tgt = rig.matrix_world @ pb.head
                turntable(cam, tgt, 25 if s_ == "L" else -25, SPEC[ch]["hand"] * 4.6, SPEC[ch]["hand"] * 0.6, 60)
                render(os.path.join(WORK, f"pv_{ch}_hand{s_}.png"))
            show([ch], props=True)
            turntable(cam, Vector((x, 0, zb + Hh * 0.62)), 28, Hh * 1.9, Hh * 0.10, 60)
            render(os.path.join(WORK, f"pv_{ch}_props.png"))
            show([ch])
        sc().render.resolution_x, sc().render.resolution_y = 420, 420
        for e in EXPRESSIONS[ch]:
            img = bpy.data.images.load(os.path.join(FACES, f"{ch}_{e}.png"), check_existing=True)
            for m in bpy.data.materials:
                if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
                    m.node_tree.nodes["decal"].image = img
            if lion:
                turntable(cam, Vector((x, yb - 0.10 * LION_K[ch][2], hy - 0.006)), 14, 0.26, 0.02, 60)
            else:
                turntable(cam, Vector((x, 0, hy - 0.08 * Hd)), 12, Hd * 3.6, Hd * 0.12, 60)
            render(os.path.join(WORK, f"pv_{ch}_expr_{e}.png"))
        for m in bpy.data.materials:
            if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
                m.node_tree.nodes["decal"].image = imgs[ch]
    if len(present) > 1:
        r2 = bpy.data.objects.get("lion2_rig")
        if r2:
            r2.location = (0.62, 0.26, 0.0)
        show(present)
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1000
        turntable(cam, Vector((0.0, 0.03, 0.17)), 10, 1.45, 0.20, 50); render(os.path.join(WORK, "pv_all.png"))
        turntable(cam, Vector((0.0, 0.03, 0.10)), 18, 1.10, 0.85, 50); render(os.path.join(WORK, "pv_all_phone.png"))
    print("PREVIEW done")


def _region_of():
    return {i + 1: k.split(".")[1] for i, k in enumerate(REGIONS)}


class _RegionLookup(dict):
    def __missing__(self, r):
        # regions are recorded in the blend as a custom property by mode_build
        tab = json.loads(sc().get("da_regions", "[]"))
        for i, k in enumerate(tab):
            self[i + 1] = k.split(".")[1]
        return dict.__getitem__(self, r)


REGION_OF = _RegionLookup()


def bend(rig, bone, axis_design, deg):
    """Rotate a pose bone about a design-space axis through its head, on top of its rest frame (as dg_build)."""
    pb = rig.pose.bones[bone]
    R = Matrix.Rotation(math.radians(deg), 4, to_bl(axis_design).normalized())
    rest = pb.bone.matrix_local
    pb.rotation_mode = 'QUATERNION'
    h = rest.translation.copy()
    pb.matrix_basis = rest.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ rest
    bpy.context.view_layer.update()


def pose_test(rig, ch, variant="a"):
    B = {b.name: (to_design(b.head_local), to_design(b.tail_local)) for b in rig.data.bones}
    if ch in LIONS:
        if variant == "a":            # roar-ish: head up, jaw open, mane, ears, tail, one front paw lifted, half blink
            bend(rig, "neck", V(1, 0, 0), -14); bend(rig, "head", V(1, 0, 0), -12); bend(rig, "jaw", V(1, 0, 0), 30)
            bend(rig, "mane", V(1, 0, 0), 10); bend(rig, "earL", V(0, 0, 1), -25); bend(rig, "earR", V(1, 0, 0), 25)
            bend(rig, "tail1", V(1, 0, 0), 25); bend(rig, "tail3", V(0, 1, 0), 40)
            bend(rig, "upperArmL", V(1, 0, 0), -40); bend(rig, "forearmL", V(1, 0, 0), 70); bend(rig, "pawL", V(1, 0, 0), 30)
            bend(rig, "thighR", V(1, 0, 0), 20); bend(rig, "shinR", V(1, 0, 0), -30)
            rig.pose.bones["eyelids"].scale = (1, 6.0, 1)
        else:                         # sitting: hind legs folded under, spine raised, head level
            bend(rig, "hips", V(1, 0, 0), -38)
            for sd in "LR":
                bend(rig, "thigh" + sd, V(1, 0, 0), -55); bend(rig, "shin" + sd, V(1, 0, 0), 120)
                bend(rig, "foot" + sd, V(1, 0, 0), -60)
                bend(rig, "upperArm" + sd, V(1, 0, 0), 30)
            bend(rig, "neck", V(1, 0, 0), 22); bend(rig, "head", V(1, 0, 0), 10)
            bend(rig, "tail1", V(1, 0, 0), 40)
            rig.pose.bones["eyelids"].scale = (1, C_LID_CLOSED.get(ch, 12.0), 1)
        bpy.context.view_layer.update()
        return
    for side, sg in (("L", 1), ("R", -1)):
        h, t = B["forearm" + side]; d = (t - h).normalized()
        bend(rig, "forearm" + side, d.cross(V(0, 0, 1)) * sg * -1, 65 if side == "L" else 35)
        h, t = B["hand" + side]; dh = (t - h).normalized()
        hz = dh.cross(V(0, 0, 1)).normalized()
        bend(rig, "fingers" + side, hz * (1 if side == "L" else -1), 75)
    bend(rig, "upperArmL", V(1, 0, 0), -45)
    bend(rig, "thighL", V(1, 0, 0), -30); bend(rig, "shinL", V(1, 0, 0), 50)
    bend(rig, "spine", V(1, 0, 0), 10); bend(rig, "head", V(0, 1, 0), 25); bend(rig, "jaw", V(1, 0, 0), 14)
    pb = rig.pose.bones["eyelids"]; pb.scale = (1, 6.0, 1)
    if ch == "daniel":
        bend(rig, "hair1", V(1, 0, 0), -25); bend(rig, "sash1", V(1, 0, 0), 25); bend(rig, "sash2", V(1, 0, 0), 25)
    if ch == "king":
        bend(rig, "cape1", V(1, 0, 0), -20); bend(rig, "cape2", V(1, 0, 0), -20)
        rig.pose.bones["belly"].scale = (1.12, 1.12, 1.12)
    if ch == "officer":
        bend(rig, "robe1", V(1, 0, 0), 25)
    bpy.context.view_layer.update()


C_LID_CLOSED = {}


def mode_posetest():
    imgs = preview_setup()
    cam = camera()
    present = [ch for ch in CHARS if bpy.data.objects.get(f"{ch}_rig")]
    for ch in present:
        C_LID_CLOSED[ch] = 12.78
    for ch in present:
        rig = bpy.data.objects[f"{ch}_rig"]
        variants = ("a", "b") if ch in LIONS else ("a",)
        for var in variants:
            for pb in rig.pose.bones:
                pb.matrix_basis = Matrix.Identity(4); pb.scale = (1, 1, 1)
            pose_test(rig, ch, var)
            show([ch])
            if ch in LIONS:
                fimg = bpy.data.images.load(os.path.join(FACES, f"{ch}_{'fierce' if var == 'a' else 'curious'}.png"),
                                            check_existing=True)
                for m in bpy.data.materials:
                    if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
                        m.node_tree.nodes["decal"].image = fimg
                if var == "b":                     # eyelids forced closed: the lids must cover the eyes
                    sc().render.resolution_x, sc().render.resolution_y = 540, 540
                    hd = rig.matrix_world @ rig.pose.bones["head"].tail
                    for nm, yaw in (("closed_close", 0), ("closed_side", 60)):
                        turntable(cam, hd + Vector((0, 0, 0.0)), yaw, 0.26, 0.02, 60)
                        render(os.path.join(WORK, f"pose_{ch}_{nm}.png"))
                if var == "a":                     # roar close-up: jaw open + the fierce decal
                    sc().render.resolution_x, sc().render.resolution_y = 540, 540
                    hd = rig.matrix_world @ rig.pose.bones["head"].tail
                    turntable(cam, hd + Vector((0, 0, -0.01)), 15, 0.28, 0.0, 60)
                    render(os.path.join(WORK, f"pose_{ch}_roar_close.png"))
                sc().render.resolution_x, sc().render.resolution_y = 720, 540
                tgt = Vector((rig.location.x, rig.location.y, rig.location.z + 0.10))
                for nm, yaw in (("front", 25), ("side", 80)):
                    turntable(cam, tgt, yaw, 0.70, 0.08, 60)
                    render(os.path.join(WORK, f"pose_{ch}_{var}_{nm}.png"))
            else:
                sc().render.resolution_x, sc().render.resolution_y = 640, 960
                Hh = char_frame(ch)[0]
                for nm, yaw in (("front", 20), ("side", 70)):
                    turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), yaw, Hh * 3.1, Hh * 0.18, 60)
                    render(os.path.join(WORK, f"pose_{ch}_{var}_{nm}.png"))
    print("POSETEST done")


def mode_uvcheck():
    """Models wearing $DA_WORK/uvproof.png (or $DA_UV_TEXTURE) through UV0: front ortho with the lion turned to its
    side (must equal the sheet) and 3/4 + back perspective (each region keeps its colour all round). lion2 wears her
    own paint."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get("DA_UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        if o.name.startswith("lion2_"):
            continue
        o.data.materials.clear(); o.data.materials.append(m)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    sc().view_settings.view_transform = 'Standard'
    cam = front_ortho_camera()
    lr = bpy.data.objects.get("lion_rig")
    if lr:
        side_rotate(lr, True)
    for o in all_meshes():
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o) or o.name.startswith("lion2_")
    bpy.data.objects["backdrop"].hide_render = True
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    if lr:
        side_rotate(lr, False)
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = False
    bpy.data.objects["backdrop"].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    r2 = bpy.data.objects.get("lion2_rig")
    if r2:
        r2.location = (0.62, 0.26, 0.0)
    for o in all_meshes():
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    sc().render.resolution_x, sc().render.resolution_y = 1600, 900
    for nm, yaw in (("q34", 30), ("back", 180)):
        turntable(cam, Vector((0.0, 0.03, 0.17)), yaw, 1.45, 0.16, 50)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    sc().render.resolution_x, sc().render.resolution_y = 1000, 700     # the lions close: left side, right side, top
    for o in all_meshes():
        o.hide_render = o.hide_render or not o.name.startswith("lion_") and o.name not in ("backdrop",)
    for nm, yaw, h in (("lionL", 90, 0.05), ("lionR", -90, 0.05), ("lionTop", 30, 0.60), ("lionFront", 0, 0.05)):
        x = lr.location.x if lr else 0.32
        turntable(cam, Vector((x + 0.0, 0.0, 0.10)), yaw, 0.80, h, 60)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    print("UVCHECK done")


def mode_verify():
    out = {}
    for ch in CHARS:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        bpy.ops.import_scene.gltf(filepath=os.path.join(MODEL, f"{ch}.glb"))
        arms = [o for o in sc().objects if o.type == 'ARMATURE']
        meshes = [o for o in sc().objects if o.type == 'MESH' and o.name.startswith(ch)]
        bones = sorted(b.name for b in arms[0].data.bones) if arms else []
        want = sorted(bone_list(ch))
        info = {"armatures": len(arms), "bonesMatch": bones == want, "missing": sorted(set(want) - set(bones)),
                "extra": sorted(set(bones) - set(want)), "actions": len(bpy.data.actions), "meshes": {}}
        tris = 0
        for o in meshes:
            t = sum(len(p.vertices) - 2 for p in o.data.polygons); tris += t
            maxinf = max((sum(1 for g in v.groups if g.weight > 0) for v in o.data.vertices), default=0)
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
        info["tris"] = tris; info["trisUnder25k"] = tris < 25000
        pts = [(o.matrix_world @ v.co) for o in meshes for v in o.data.vertices]
        info["heightTop"] = round(max(p.z for p in pts), 4)
        info["minY"] = round(min(p.z for p in pts), 4)
        if ch in LIONS:
            body = [o for o in meshes if o.name.endswith("_body")][0]
            gi = {g.index: g.name for g in body.vertex_groups}
            bodyz, withers = [], []
            for v in body.data.vertices:
                p = body.matrix_world @ v.co
                gs = sorted(((g.weight, gi[g.group]) for g in v.groups), reverse=True)
                top = gs[0][1] if gs else ""
                if not top.startswith("tail"):
                    bodyz.append(-p.y)                    # design z = -Blender y
                if top in ("chest", "spine") and abs(p.x) < 0.006:
                    withers.append(p.z)
            info["noseZ"] = round(max(bodyz), 4); info["rumpZ"] = round(min(bodyz), 4)
            info["noseToRump"] = round(max(bodyz) - min(bodyz), 4)
            info["withers"] = round(max(withers), 4) if withers else None
            info["tailBackZ"] = round(min(-p.y for p in pts), 4)
            info["emptyGroups"] = sorted(g.name for g in body.vertex_groups
                                         if not any(gg.group == g.index and gg.weight > 0 for v in body.data.vertices for gg in v.groups))
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps({c: {k: v for k, v in i.items() if k != "meshes"} for c, i in out.items()}))


if __name__ == "__main__":
    {"build": mode_build, "preview": mode_preview, "posetest": mode_posetest, "verify": mode_verify,
     "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), os.path.abspath(__file__), "all"],
                                                 check=True)}[MODE]()
