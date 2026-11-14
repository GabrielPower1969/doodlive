"""Exodus (story pack #4): characters moses, pharaoh, miriam — meshes, rig, weights, UVs, face decals, previews, GLBs.

Contract: docs/exodus/CONTRACT.md §2-§3 (ids, heights, bone names, props), look: docs/exodus/DESIGN.md, notes:
docs/exodus/RIG.md. Started as a copy of pipeline/ru_characters.py (Ruth, pack #3) and keeps its method: procedural
quad cages (pipeline/story_mesh.py helpers, unchanged), heads mapped from the D&G base head by landmarks, box-modelled
hands, face decals on UV1 + an `eyelids` blink, UV0 = front page projection with occlusion + ID-render fixes, Ruth's
`hood()` drape for head-cloths. New for Exodus:
  * Moses: shoulder-length white hair, a long two-bone white beard (`beard1/2`, child of `jaw`) hanging in front of
    the chest, a drooping moustache, an open striped shepherd's mantle (two stripe regions; front panels on
    `mantleL/R`, back drape on `mantleBack`), a twisted two-strand rope belt, a gnarled staff with a crook knot
    (`staff` + leaf `staffTip`), a slight stoop baked into the rest pose (as Naomi);
  * Pharaoh: a bare torso and arms (skin "sleeves"), a striped nemes head-cloth built with `hood()` and cut into
    horizontal lapis / gold stripes by bisecting planes (`bands` post step: clean straight stripe edges), lappets on
    `nemes1L/R`, back tail on `nemesBack`, a broad collar laid along the torso surface by arc length (`shell_band`),
    a pleated kilt with a red-and-gold apron, gold arm-bands, cobra and false beard, taller legs (bare shins); a
    hidden golden chariot (`chariot`, child of `root`) with a separate left wheel (`wheelL`, child of `chariot`);
  * Miriam: a teal head-scarf over dark hair with a thick three-strand braid over her left shoulder (`braid1/2`),
    scarf tail (`scarf1/2`), saffron dress with an embroidered hem border and cuffs, rust belt, coral bead necklace,
    bare feet, a hidden tambourine (`tambourine`, child of `handL`);
  * faces: Moses's bushy white brows (light fill + soft grey edge so they read on any skin), Pharaoh's kohl-lined
    almond eyes with a winged liner and thin high brows, water drops for `soggy`, Miriam's `sing` mouth.

Run (repo root):
  python3 pipeline/ex_characters.py all                                           # everything below, in order
  python3 pipeline/ex_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/ex_characters.py -- build        # models, rig, GLBs, blend, ID render
  python3 pipeline/ex_characters.py proof                                         # $EX_WORK/uvproof.png
  blender -b --factory-startup --python pipeline/ex_characters.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/ex_characters.py -- uvcheck      # models wearing uvproof.png
  blender -b --factory-startup --python pipeline/ex_characters.py -- posetest     # bend / blink / jaw / cloth bones
  blender -b --factory-startup --python pipeline/ex_characters.py -- verify       # re-import GLBs, check bones/budget
  python3 pipeline/ex_characters.py compose                                       # preview_*.png contact sheets
Intermediate renders go to $EX_WORK (default /tmp/ex_char_work). EX_ONLY=moses (comma list) builds a subset.
"""
import sys, os, json, math, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/exodus/model")
FACES = os.path.join(ROOT, "docs/exodus/design/faces")
WORK = os.environ.get("EX_WORK", "/tmp/ex_char_work")
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/exodus/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("moses", "pharaoh", "miriam")
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
EXTRA_BONES = {"moses": ["beard1", "beard2", "mantleL", "mantleR", "mantleBack", "staff", "staffTip"],
               "pharaoh": ["nemes1L", "nemes1R", "nemesBack", "chariot", "wheelL"],
               "miriam": ["scarf1", "scarf2", "braid1", "braid2", "tambourine"]}
PROPS = {"moses": {"staff": True}, "pharaoh": {"chariot": False, "wheelL": False},
         "miriam": {"tambourine": False}}           # prop bone -> shown by default (hidden ones are not printed)
CONTRACT_HEIGHT = {"moses": 0.37, "pharaoh": 0.39, "miriam": 0.34}
DEFAULT_SHEET = {"pharaoh": (-0.33, 0.015), "moses": (0.0, 0.015), "miriam": (0.33, 0.015)}
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (as Esther / Ruth)

# ---------------------------------------------------------------------------------------------- palette (DESIGN.md)
PALETTE = {
    "moses": {"skin": "#D39A6F", "hair": "#F4F1EA", "tunic": "#F1E6CC", "mantleA": "#C98B3A", "mantleB": "#6B4426",
              "belt": "#B89466", "sandals": "#8A5A3B", "staff": "#8A5E3A"},
    "pharaoh": {"skin": "#C98E62", "nemesA": "#2F5DA8", "nemesB": "#E8B83A", "collar": "#3FB8AF", "kilt": "#FBF8EF",
                "sash": "#C2413A", "bands": "#E8B83A", "sandals": "#E8B83A", "chariot": "#E0B13A",
                "chariotTrim": "#C2413A"},
    "miriam": {"skin": "#E2AE84", "hair": "#4A2E1F", "scarf": "#2E9C9A", "dress": "#F2B33D", "belt": "#B5532E",
               "hem": "#3E6FB0", "necklace": "#E86A5A", "tambourine": "#B07A47", "ribbons": "#E86A5A"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发和胡子", "hair and beard"), "tunic": ("内袍", "tunic"),
    "mantleA": ("外袍条纹 A", "mantle stripe A"), "mantleB": ("外袍条纹 B", "mantle stripe B"),
    "belt": ("腰带", "belt"), "sandals": ("凉鞋", "sandals"), "staff": ("牧杖", "staff"),
    "nemesA": ("头巾条纹 A", "head-cloth stripe A"), "nemesB": ("头巾条纹 B", "head-cloth stripe B"),
    "collar": ("宽项圈", "collar"), "kilt": ("短裙", "kilt"), "sash": ("围裙腰带", "apron sash"),
    "bands": ("金饰", "gold bands"), "chariot": ("战车", "chariot"), "chariotTrim": ("战车花边", "chariot trim"),
    "scarf": ("头巾", "head-scarf"), "dress": ("长裙", "dress"), "hem": ("裙边", "hem border"),
    "necklace": ("项链", "necklace"), "tambourine": ("手鼓", "tambourine"), "ribbons": ("彩带", "ribbons"),
}
# regions too small to colour on A4 (< ~2 mm across): constant UV deep inside a printed region ("char.region", or
# "char.FACE" = that character's face skin away from eyes / brows / nose / mouth)
ANCHORS = {
    "moses": {},
    "pharaoh": {},
    "miriam": {"necklace": "miriam.necklace"},
}
# hidden-by-default props are not printed: their regions sample a printed region of similar colour (first target
# that exists wins; "set.<region>" = a region of the set's printed drawings). Override with design.json
# characters.<id>.propUV.<region> = [u, v] (page UV).
PROP_ANCHORS = {
    "moses": {},
    "pharaoh": {"chariot": ["set.chariot", "pharaoh.nemesB"], "chariotTrim": ["set.chariotTrim", "pharaoh.sash"]},
    "miriam": {"tambourine": ["set.tambourine", "moses.staff"], "ribbons": ["set.ribbons", "miriam.belt"]},
}
# parts whose printed area is a sliver: every face of (part, region) takes one UV inside a larger region
PART_ANCHORS = {
    "moses": {("handL", "skin"): "moses.FACE", ("handR", "skin"): "moses.FACE", ("legL", "skin"): "moses.FACE",
              ("legR", "skin"): "moses.FACE"},
    "pharaoh": {("handL", "skin"): "pharaoh.FACE", ("handR", "skin"): "pharaoh.FACE"},
    "miriam": {("handL", "skin"): "miriam.FACE", ("handR", "skin"): "miriam.FACE", ("legL", "skin"): "miriam.FACE",
               ("legR", "skin"): "miriam.FACE"},
}

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


ESTHER = dict(height=0.34, top=0.330, chin=0.272, hw=0.0204, zc=-0.001, depth=1.02, jaw=-0.12, cheek=0.08,
              fr=dict(eye=0.472, brow=0.565, nose=0.262, mouth=0.158),
              chin_narrow=0.10, crown=0.0, noseH=0.0016, nose_w=0.82, nose_long=0.0, brow=0.45, lips=1.25,
              chinAmt=0.8, sockets=0.85, cheekbones=0.9,
              neckBase=0.257, neck=(0.0079, 0.0074, -0.0080), shoulder=(0.034, 0.250), chestY=0.230,
              waistY=0.205, hipY=0.180, hipX=0.0165, kneeY=0.094, ankleY=0.018, footLen=0.038, footScale=1.0,
              upperArm=0.058, forearm=0.049, hand=0.031, palmFrac=0.52,
              handDims=dict(palmW=0.0132, palmH=0.0054, wristW=0.0094, wristH=0.0064, fingerW=0.0034,
                            fingerT=0.0031, thumbW=0.0033, thumbT=0.0030, armR=0.0058))
KING = dict(height=0.40, top=0.354, chin=0.294, hw=0.0222, zc=-0.002, depth=1.06, jaw=0.10, cheek=0.04,
            chin_narrow=0.0, crown=0.0, noseH=0.0028, nose_w=1.12, nose_long=0.0, brow=1.15, lips=0.9,
            chinAmt=0.6, sockets=1.0, cheekbones=1.0,
            neckBase=0.273, neck=(0.0108, 0.0098, -0.0108), shoulder=(0.046, 0.266), chestY=0.246,
            waistY=0.218, hipY=0.190, hipX=0.0200, kneeY=0.100, ankleY=0.019, footLen=0.044, footScale=1.15,
            upperArm=0.066, forearm=0.056, hand=0.037, palmFrac=0.52,
            handDims=dict(palmW=0.0154, palmH=0.0064, wristW=0.0112, wristH=0.0078, fingerW=0.0039,
                          fingerT=0.0036, thumbW=0.0040, thumbT=0.0036, armR=0.0072))
SPEC = {
    # Moses: about eighty but strong; built straight at ~0.38, the baked stoop brings the top to ~0.37
    "moses": scaled(KING, 1.04, 1.04, height=0.38, jaw=0.02, cheek=-0.02, chin_narrow=0.04, noseH=0.0034,
                    nose_w=1.18, nose_long=0.10, brow=1.30, lips=0.70, chinAmt=0.5, sockets=1.15, cheekbones=1.10,
                    fr=dict(eye=0.488, brow=0.580, nose=0.268, mouth=0.163)),
    # Pharaoh: younger, tall and thin, chin up; the nemes adds ~0.012 on top
    "pharaoh": scaled(KING, 1.07, 0.97, height=0.39, jaw=0.14, cheek=-0.04, chin_narrow=0.06, noseH=0.0031,
                      nose_w=0.98, nose_long=0.14, brow=0.95, lips=1.00, chinAmt=0.85, sockets=1.0, cheekbones=1.15,
                      footScale=1.0, fr=dict(eye=0.486, brow=0.580, nose=0.266, mouth=0.163)),
    # Miriam: a lively grown woman (about forty-five)
    "miriam": scaled(ESTHER, 1.015, 1.02, height=0.34, jaw=-0.06, cheek=0.12, chin_narrow=0.06, noseH=0.0018,
                     nose_w=0.90, lips=1.15, brow=0.55, cheekbones=0.95,
                     fr=dict(eye=0.474, brow=0.566, nose=0.262, mouth=0.160)),
}
FIST = {("moses", "R")}            # hands closed round a prop at rest (Moses's staff)
FIST_BEND = {("moses", "R"): 20.0}    # wrist cock of a fist (deg below horizontal); the staff then runs diagonally



def landmarks(ch):
    s = SPEC[ch]; H = s["top"] - s["chin"]
    L = dict(top=s["top"], chin=s["chin"], zc=s["zc"], hw=s["hw"])
    for k, f in FR.items():
        L[k] = s["chin"] + s.get("fr", {}).get(k, f) * H
    return L


EYE = {"moses": (0.405, 0.255, 0.150), "pharaoh": (0.405, 0.290, 0.150), "miriam": (0.415, 0.300, 0.225)}


def face_layout(ch):
    """Decal rectangle (character-local x0 y0 x1 y1) and eye / brow / mouth placement in normalised decal space
    (0..1, y up). Square rect from just under the mouth, side max(1.76 hw, 0.72 H) so brows fit (as Esther)."""
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


EXPRESSIONS = {"moses": ["calm", "talk", "curious", "amazed", "worried", "scared", "brave", "pray", "joy"],
               "pharaoh": ["smug", "talk", "laugh", "angry", "shock", "scared", "sad", "sneaky", "soggy"],
               "miriam": ["calm", "talk", "sad", "pray", "worried", "scared", "wow", "joy", "sing"]}
DEFAULT_EXPR = {"moses": "calm", "pharaoh": "smug", "miriam": "calm"}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "moses": {"idle": "calm", "walk_staff": "calm", "talk": "talk", "look_curious": "curious", "startle": "scared",
              "kneel_bow": "pray", "who_me": "worried", "throw_staff": "brave", "jump_back": "scared",
              "grab_tail": "worried", "nod_brave": "brave", "staff_raise": "brave", "sigh_head": "worried",
              "brave_talk": "talk", "staff_over_sea": "brave", "clap": "joy", "talk_warm": "talk", "wave": "joy"},
    "pharaoh": {"idle": "smug", "walk": "smug", "talk": "talk", "smug": "smug", "point_order": "angry",
                "laugh": "laugh", "arms_crossed": "smug", "frog_panic": "scared", "sneaky_no": "sneaky",
                "sad_sit": "sad", "tantrum": "angry", "ride": "smug", "wobble": "shock", "soggy_sit": "soggy",
                "sneeze": "soggy", "angry": "angry"},
    "miriam": {"idle": "calm", "walk": "calm", "talk": "talk", "carry_brick": "sad", "pray_stand": "pray",
               "hurry_wave": "worried", "joy": "joy", "scared": "scared", "wow": "wow", "tambourine_dance": "sing",
               "wave": "joy", "clap": "joy"},
}


def sheet_positions():
    """sheetX / sheetY per character: assets/exodus/design.json characters.<id> when present (Set + sheet role),
    else the defaults (also written to model/characters_layout.json)."""
    out = {ch: list(DEFAULT_SHEET[ch]) for ch in CHARS}
    art_h = ART_H_DEFAULT; src = "defaults"; prop_uv = {}
    if os.path.exists(DESIGN_JSON):
        try:
            d = json.load(open(DESIGN_JSON))
            art_h = d.get("artHeightUnits", art_h)
            for ch in CHARS:
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
            side=1, mode="open", inner_up=0.0, pupil=0.55, line=0.020, lower=True, wet=False, kohl=0.0):
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
            stroke(dr, pts, line * 1.3 * (1 + kohl * 0.4), line * 1.1, wmid=line * 1.6 * (1 + kohl * 0.4))
            if kohl:
                ox, oy = pts[-1]
                stroke(dr, [(ox, oy), (ox + o * ew * 0.45, oy + eh * 0.10)], line * 1.3, line * 0.3)
            if lash:
                ox, oy = pts[-1]
                stroke(dr, [(ox, oy), (ox + o * ew * 0.22, oy + eh * 0.25)], line * 0.9, line * 0.3)
            return
        if mode == "closed":      # calm closed: downward arc with lashes
            pts = bez(inner, (cx - o * ew * 0.5, cy - eh * 0.75), (cx + o * ew * 0.5, cy - eh * 0.75), outer)
            stroke(dr, pts, line * 1.2 * (1 + kohl * 0.5), line * 1.0 * (1 + kohl * 0.5), wmid=line * 1.5 * (1 + kohl * 0.5))
            if kohl:
                ox, oy = pts[-1]
                stroke(dr, [(ox, oy), (ox + o * ew * 0.50, oy + eh * 0.25)], line * 1.4, line * 0.3)
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
        if kohl:                    # Egyptian liner: heavy upper line, a wing past the outer corner, a dark lower line
            stroke(dr, up, line * (0.9 + kohl * 0.5), line * (1.3 + kohl * 0.8), wmid=line * (1.4 + kohl * 0.8), col=(20, 14, 12, 255))
            ox, oy = up[-1]
            stroke(dr, [(ox, oy), (ox + o * ew * 0.30, oy + eh * 0.14), (ox + o * ew * 0.60, oy + eh * 0.34)],
                   line * (1.2 + kohl * 0.6), line * 0.30, col=(20, 14, 12, 255))
            stroke(dr, dn[0:-2], line * (0.7 + kohl * 0.4), line * (0.5 + kohl * 0.3), col=(28, 20, 16, 235))
        elif lower:
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

    def bushy_brow(img, side, c, half, raise_=0.0, inner=0.0, arch=0.35, w=0.040, length=1.12, outer=0.0,
                   thick=1.0, fill=(246, 243, 236, 255), edge=(150, 138, 128, 235), tufts=5):
        """Moses: a thick white brow (soft grey edge so it reads on any skin colour) with hair tufts flicking out."""
        cx, cy = c; ew, eh = half; o = side
        y0 = cy + raise_ - 0.045
        pi = (cx - o * ew * 0.95 * length, y0 + inner)
        po = (cx + o * ew * 1.15 * length, y0 - eh * 0.35 + outer)
        pts = bez(pi, (cx - o * ew * 0.35, y0 + inner * 0.6 + eh * arch), (cx + o * ew * 0.45, y0 + eh * arch * 0.9 + outer * 0.5), po)
        W0, W1, WM = w * 1.15 * thick, w * 0.55 * thick, w * 1.20 * thick
        soft(img, lambda d: stroke(d, pts, W0 * 1.30, W1 * 1.35, wmid=WM * 1.28, col=edge), 0.0018)
        rnd = random.Random(17 + side)
        tl = []
        for k in range(tufts):
            f = 0.18 + 0.80 * k / max(1, tufts - 1)
            x, y = pts[int(f * (len(pts) - 1))]
            ln = w * (0.9 + 0.7 * f) * (0.8 + 0.4 * rnd.random())
            ang = math.radians(35 + 40 * f + rnd.uniform(-10, 10))
            tl.append([(x, y), (x + o * ln * math.cos(ang) * 0.9, y + ln * math.sin(ang) * (0.55 if f < 0.7 else -0.25))])

        def f_edge(d):
            for t in tl:
                stroke(d, t, w * 0.62, w * 0.22, col=edge)
        soft(img, f_edge, 0.0015)
        dr = ImageDraw.Draw(img)
        stroke(dr, pts, W0, W1, wmid=WM, col=fill)
        for t in tl:
            stroke(dr, t, w * 0.40, w * 0.12, col=fill)
        soft(img, lambda d: stroke(d, [(x, y - w * 0.18) for x, y in pts[4:-6]], w * 0.18, w * 0.10,
                                   col=(205, 198, 190, 160)), 0.001)

    def forehead(img, y, n=3, gap=0.030, wd=0.17, col=(140, 85, 62, 120), worry=0.0):
        """Soft horizontal forehead lines (Moses); worry bends them up in the middle."""
        def f(d):
            for k in range(n):
                yy = y + k * gap; ww = wd * (1 - 0.18 * k)
                stroke(d, bez((0.5 - ww, yy - 0.006), (0.5 - ww * 0.35, yy + 0.010 + worry), (0.5 + ww * 0.35, yy + 0.010 + worry),
                              (0.5 + ww, yy - 0.006), 24), 0.006, 0.004, col=col, wmid=0.009)
        soft(img, f, 0.002)

    made = {}
    for ch in CHARS:
        F = face_layout(ch)
        eL, eR, half, by, my, ny_ = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"], F["nose"]
        hwN = F["hwN"]
        bcol = {"moses": (246, 243, 236, 255), "pharaoh": (26, 18, 14, 255), "miriam": (62, 38, 26, 255)}[ch]
        iris = {"moses": (92, 70, 48), "pharaoh": (64, 40, 24), "miriam": (104, 66, 36)}[ch]
        bw = {"moses": 0.040, "pharaoh": 0.016, "miriam": 0.024}[ch]
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            E = dict(look=(0, 0), top=1.0, bot=1.0, tilt=0.15, lash=0, mode="open", lid=0.10, inner_up=0.0,
                     pupil=0.55, wet=False, kohl=0.0)
            Bp = dict(raise_=0.0, inner=0.0, arch=0.35, thick=1.0, outer=0.0)
            Bl, Br = {}, {}
            M = dict(kind="flat", wd=0.095, jaw=0.0, side=0.0)
            lipcol = None; rim = None; bl = 0; crow = 0; folds = 0.0; bags = False; crs = True
            fh = None; drops = []; puff = 0; sweat = False
            if ch == "moses":
                # old, kind, sun-browned: crinkled eyes, bushy white brows carry the acting, forehead lines; the mouth
                # sits on the white beard / moustache (a soft lip patch under closed mouths, LESSONS L42)
                E.update(lid=0.20, top=0.84, bot=0.84, tilt=0.04, pupil=0.56); M["wd"] = 0.084
                lipcol = (176, 98, 84, 200); rim = (196, 132, 116, 210)
                Bp.update(raise_=0.070, arch=0.30, thick=1.0); bl = 55; crow = 3; folds = 0.050; bags = True
                fh = dict(y=by + 0.085, n=3, worry=0.0)
                if ex == "calm":
                    E.update(top=0.74, bot=0.72, look=(0.05, -0.05)); Bp.update(inner=0.010, raise_=0.072)
                    M.update(kind="soft", wd=0.080)
                elif ex == "talk":
                    M.update(kind="open", wd=0.080, jaw=0.08); E.update(top=0.86); Bp.update(raise_=0.080, arch=0.36)
                elif ex == "curious":
                    E.update(top=0.98, look=(-0.55, 0.20)); Bl = dict(raise_=0.110, arch=0.62, outer=0.010)
                    Br = dict(raise_=0.060, inner=-0.014, arch=0.18); M.update(kind="small", wd=0.066)
                    fh.update(n=2)
                elif ex == "amazed":
                    E.update(top=1.30, bot=1.10, pupil=0.42, lid=0.10, tilt=0.0); Bp.update(raise_=0.125, arch=0.60)
                    M.update(kind="o", wd=0.070, jaw=0.20); crow = 1; fh.update(y=by + 0.10, worry=0.010)
                elif ex == "worried":
                    E.update(top=0.92, look=(0.25, -0.30), tilt=-0.10)
                    Bp.update(inner=0.050, raise_=0.090, arch=0.08, outer=-0.030); M.update(kind="wobbly", wd=0.070, jaw=0.02)
                    fh.update(worry=0.014); crow = 2
                elif ex == "scared":          # comic: eyes huge, mouth open
                    E.update(top=1.42, bot=1.25, pupil=0.32, lid=0.06, tilt=-0.05, look=(0, 0.1))
                    Bp.update(inner=0.040, raise_=0.130, arch=0.30, outer=-0.010); M.update(kind="shout", wd=0.086, jaw=0.18)
                    crow = 0; fh.update(y=by + 0.11, worry=0.016); sweat = True
                elif ex == "brave":           # brows down, firm smile
                    E.update(top=0.88, tilt=0.10, look=(0, 0.05)); Bp.update(inner=-0.026, raise_=0.056, arch=0.16, thick=1.08)
                    M.update(kind="smile", wd=0.082); crow = 2; fh.update(n=2)
                elif ex == "pray":
                    E.update(mode="closed"); Bp.update(inner=0.020, raise_=0.072, arch=0.22); M.update(kind="soft", wd=0.072)
                    crs = False
                elif ex == "joy":
                    E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.50); M.update(kind="grin", wd=0.096, jaw=0.10)
                    bl = 90; crow = 3
            elif ch == "pharaoh":
                # vain, theatrical, comic: kohl-lined almond eyes, thin high dark brows, big range
                E.update(kohl=0.6, lid=0.10, top=0.90, bot=0.90, tilt=0.20, pupil=0.56); M["wd"] = 0.090
                lipcol = (168, 92, 82, 170)
                Bp.update(raise_=0.096, arch=0.55, thick=1.0, outer=0.010); bl = 0; crow = 0
                if ex == "smug":
                    E.update(top=0.60, bot=0.86, look=(0.35, 0.30), lid=0.22)
                    Bl = dict(raise_=0.118, arch=0.72); Br = dict(raise_=0.096, arch=0.50)
                    M.update(kind="smirk", wd=0.094, side=1)
                elif ex == "talk":
                    M.update(kind="open", wd=0.088, jaw=0.10); Bp.update(raise_=0.104, arch=0.62)
                elif ex == "laugh":
                    E.update(mode="happy"); Bp.update(raise_=0.110, arch=0.70); M.update(kind="grin", wd=0.110, jaw=0.32)
                    bl = 70
                elif ex == "angry":           # comic: cheeks puffed, brows slammed down
                    E.update(top=0.62, bot=0.80, tilt=0.32, pupil=0.50, look=(0, -0.05))
                    Bp.update(inner=-0.050, raise_=0.070, arch=0.12, outer=0.030, thick=1.25)
                    M.update(kind="small", wd=0.048); puff = 1; bl = 150
                elif ex == "shock":
                    E.update(top=1.40, bot=1.25, pupil=0.30, lid=0.06, tilt=0.05)
                    Bp.update(raise_=0.150, arch=0.80, outer=0.020); M.update(kind="o", wd=0.080, jaw=0.32)
                elif ex == "scared":
                    E.update(top=1.25, bot=1.15, pupil=0.32, look=(-0.60, 0.25), tilt=-0.05)
                    Bp.update(inner=0.050, raise_=0.130, arch=0.25, outer=-0.020)
                    M.update(kind="wobbly", wd=0.090, jaw=0.14); sweat = True
                elif ex == "sad":             # S07: real sorrow, not comic
                    E.update(top=0.78, bot=0.88, look=(0, -0.55), tilt=-0.12, wet=True, kohl=0.35)
                    Bp.update(inner=0.048, raise_=0.100, arch=0.10, outer=-0.030); M.update(kind="frown", wd=0.070)
                elif ex == "sneaky":
                    E.update(top=0.58, bot=0.80, look=(0.85, -0.05)); Bl = dict(raise_=0.125, arch=0.80)
                    Br = dict(raise_=0.074, inner=-0.022, arch=0.25); M.update(kind="smirk", wd=0.100, side=-1)
                elif ex == "soggy":           # half-closed, drippy, mouth pulled down
                    E.update(top=0.46, bot=0.80, look=(0, -0.35), tilt=-0.18, lid=0.28, kohl=0.35)
                    Bp.update(inner=0.030, raise_=0.084, arch=0.12, outer=-0.040); M.update(kind="frown", wd=0.082)
                    drops = [(0.30, by + 0.05, 0.020), (0.71, by + 0.10, 0.016), (0.80, ny_ - 0.07, 0.018),
                             (0.505, ny_ - 0.040, 0.014)]
            else:   # miriam
                E.update(lash=2, tilt=0.14, lid=0.06, pupil=0.54); lipcol = (206, 96, 92, 175); M["wd"] = 0.086
                Bp.update(raise_=0.080, arch=0.34, thick=0.98); bl = 100; crow = 1
                if ex == "calm":
                    M.update(kind="soft"); E.update(look=(0.05, 0.05), top=0.92)
                elif ex == "talk":
                    M.update(kind="open", wd=0.078, jaw=0.07); Bp.update(raise_=0.088, arch=0.40)
                elif ex == "sad":
                    E.update(top=0.88, look=(0, -0.45), tilt=-0.06, wet=True)
                    Bp.update(inner=0.042, raise_=0.090, arch=0.10, outer=-0.020); M.update(kind="frown", wd=0.068); bl = 70
                elif ex == "pray":
                    E.update(mode="closed"); Bp.update(inner=0.018, raise_=0.084, arch=0.26); M.update(kind="soft", wd=0.072)
                    crs = False
                elif ex == "worried":
                    E.update(top=0.98, look=(-0.35, -0.10), tilt=-0.06)
                    Bp.update(inner=0.044, raise_=0.094, arch=0.12, outer=-0.020); M.update(kind="flat", wd=0.066)
                elif ex == "scared":
                    E.update(top=1.25, bot=1.12, pupil=0.36, look=(0.55, 0.10), tilt=0.0)
                    Bp.update(inner=0.046, raise_=0.120, arch=0.30, outer=-0.012); M.update(kind="wobbly", wd=0.076, jaw=0.10)
                    bl = 60
                elif ex == "wow":             # open delighted mouth
                    E.update(top=1.22, bot=1.05, pupil=0.44, look=(0, 0.25)); Bp.update(raise_=0.120, arch=0.58)
                    M.update(kind="grin", wd=0.084, jaw=0.30); bl = 150
                elif ex == "joy":
                    E.update(mode="happy"); Bp.update(raise_=0.098, arch=0.48); M.update(kind="grin", wd=0.096, jaw=0.10)
                    bl = 160; crow = 2
                elif ex == "sing":
                    E.update(mode="happy"); Bp.update(raise_=0.104, arch=0.52); M.update(kind="o", wd=0.074, jaw=0.20)
                    bl = 150; crow = 2
            # ---- draw
            if bl:
                blush(img, 0.31, ny_ - 0.035, 0.088 if not puff else 0.110, 0.046 if not puff else 0.070, bl)
            if puff:                       # puffed cheeks: round highlights + outline arcs
                for sx in (-1, 1):
                    cxp = 0.5 + sx * 0.30; cyp = ny_ - 0.055; r = 0.085
                    soft(img, lambda d, cxp=cxp, cyp=cyp, sx=sx: stroke(d, bez((cxp - sx * r * 0.2, cyp + r * 0.85),
                                                                            (cxp + sx * r * 1.05, cyp + r * 0.9),
                                                                            (cxp + sx * r * 1.15, cyp - r * 0.6),
                                                                            (cxp + sx * r * 0.1, cyp - r * 0.95), 24),
                                                                       0.010, 0.006, col=(130, 60, 48, 170), wmid=0.014), 0.002)
                    soft(img, lambda d, cxp=cxp, cyp=cyp: d.ellipse((P(cxp - 0.020, cyp + 0.040)[0], P(cxp - 0.020, cyp + 0.040)[1],
                                                                    P(cxp + 0.020, cyp + 0.010)[0], P(cxp + 0.020, cyp + 0.010)[1]),
                                                                   fill=(255, 235, 220, 150)), 0.004)
            nose_hint(img, ny_ + 0.006, {"moses": 0.040, "pharaoh": 0.034, "miriam": 0.030}[ch],
                      strength={"moses": 1.15, "pharaoh": 1.05, "miriam": 0.85}[ch])
            if folds:
                wide = M["kind"] in ("smile", "grin")
                cheek_lines(img, ny_ + 0.004, my + (0.000 if wide else 0.012), 0.100, M["wd"] * 1.25 + (0.040 if wide else 0.030),
                            col=(130, 74, 56, 105 if wide else 80))
            if fh:
                forehead(img, fh["y"], n=fh["n"], worry=fh["worry"])
            for side, c in ((1, eL), (-1, eR)):
                eye(img, c, half, side=side, iris=iris, line=0.020 if ch != "pharaoh" else 0.019, **E)
                if crs and E["mode"] == "open":
                    crease(img, c, half, side, lift=1.55 if ch != "moses" else 1.50,
                           col=(140, 90, 72, 110 if ch != "moses" else 150))
                if bags and E["mode"] == "open":
                    under_eye(img, c, half, side, drop=1.25 if E["bot"] < 0.9 else 1.35, col=(140, 90, 76, 130))
                if crow:
                    crows(img, c, half, side, n=crow, ln=1.0 if E["mode"] == "open" else 1.2,
                          col=(130, 80, 62, 150 if ch == "moses" else 90))
            dr = ImageDraw.Draw(img)
            for side, c in ((1, eL), (-1, eR)):
                b = dict(Bp); b.update(Bl if side == 1 else Br)
                if ch == "moses":
                    bushy_brow(img, side, (c[0], by - 0.010), half, w=bw, **b)
                else:
                    brow(dr, side, (c[0], by - 0.015), half, w=bw, col=bcol,
                         length=1.18 if ch == "pharaoh" else 1.05, **b)
            if rim and M["kind"] in ("open", "grin", "o", "shout", "wobbly"):
                rim_mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, M["jaw"], rim)
            elif rim:                           # closed mouth on a beard: a light lip patch under the line
                rx, ry = M["wd"] * 1.30, M["wd"] * 0.42
                soft(img, lambda d: d.ellipse((P(0.5 - rx, my + ry * 0.5)[0], P(0.5 - rx, my + ry * 0.5)[1],
                                               P(0.5 + rx, my - ry * 1.3)[0], P(0.5 + rx, my - ry * 1.3)[1]),
                                              fill=rim), 0.004)
            mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, lipcol=lipcol, jaw=M["jaw"], side=M["side"])
            if sweat:
                drop(img, 0.88 if ch != "miriam" else 0.12, by - 0.030, 0.020)
            for x, y, sz in drops:
                drop(img, x, y, sz)
            out = img.resize((PX, PX), Image.LANCZOS)
            path = os.path.join(FACES, f"{ch}_{ex}.png")
            out.save(path); made[f"{ch}_{ex}"] = os.path.relpath(path, ROOT)
    # overview sheet: every expression over a skin swatch, plus a 64 px "phone distance" row (LESSONS L42)
    cells = [(ch, ex) for ch in CHARS for ex in EXPRESSIONS[ch]]
    cols = 9; cw = 256
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (cw + 24) + rows * 88), (250, 246, 238))
    dr = ImageDraw.Draw(sheet)
    for i, (ch, ex) in enumerate(cells):
        x, y = (i % cols) * cw, (i // cols) * (cw + 24 + 88)
        bg = Image.new("RGBA", (cw, cw), tuple(int(PALETTE[ch]["skin"][k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        fc = Image.open(os.path.join(FACES, f"{ch}_{ex}.png")).resize((cw, cw), Image.LANCZOS)
        bg.alpha_composite(fc); sheet.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 8, y + cw + 4), f"{ch}_{ex}", fill=(40, 30, 20))
        small = bg.resize((64, 64), Image.LANCZOS)
        sheet.paste(small.convert("RGB"), (x + 8, y + cw + 22))
    sheet.save(os.path.join(FACES, "overview.png"))
    print("faces:", len(made), "->", FACES)
    return made
def compose():
    """Contact sheets model/preview_<char>.png and preview_all.png from the $EX_WORK renders."""
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
    for ch in CHARS:
        views = [("front", "front"), ("q34", "3/4"), ("side", "side"), ("back", "back")]
        files = [os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in views]
        top = grid(files, [lb for _, lb in views], 4, (480, 720), f"{ch}: rest pose, demo palette + default face decal")
        det = [("head", "face 3/4"), ("headfront", "face front"), ("handL", "left hand"), ("handR", "right hand"),
               ("props", "hidden props shown (rest pose)")]
        files2 = [os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det]
        bot = grid(files2, [lb for _, lb in det], 5, (384, 384), "close-ups")
        exprs = [os.path.join(WORK, f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]]
        ex = grid(exprs, EXPRESSIONS[ch], 5, (384, 384), "face decals on the model (UV1)")
        W = max(top.width, bot.width, ex.width)
        im = Image.new("RGB", (W, top.height + bot.height + ex.height), bg)
        im.paste(top, (0, 0)); im.paste(bot, (0, top.height)); im.paste(ex, (0, top.height + bot.height))
        im.save(os.path.join(MODEL, f"preview_{ch}.png"))
    a = os.path.join(WORK, "pv_all.png")
    if os.path.exists(a):
        Image.open(a).convert("RGB").save(os.path.join(MODEL, "preview_all.png"))
    uv = [os.path.join(WORK, f) for f in ("uvproof.png", "uv_front.png", "uv_q34.png", "uv_back.png")]
    if all(os.path.exists(f) for f in uv):
        top_a = Image.open(uv[0]).convert("RGB"); top_b = Image.open(uv[1]).convert("RGBA")
        bgw = Image.new("RGBA", top_b.size, (255, 255, 255, 255)); bgw.alpha_composite(top_b); top_b = bgw.convert("RGB")
        crop = (0, 760, 1000, top_a.height)
        r1 = [top_a.crop(crop), top_b.crop(crop)]
        r2 = [Image.open(uv[2]).convert("RGB").resize((1000, 562)), Image.open(uv[3]).convert("RGB").resize((1000, 562))]
        h1 = r1[0].height
        im = Image.new("RGB", (2000, 34 + h1 + 26 + 562 + 26), bg); d = ImageDraw.Draw(im)
        d.text((10, 10), "UV0 proof: a perfectly coloured sheet (ID render in demo colours, left) worn by the models "
                         "(front ortho = the sheet; 3/4 and back keep each region's colour)", fill=(40, 30, 20))
        im.paste(r1[0], (0, 34)); im.paste(r1[1], (1000, 34))
        d.text((8, 34 + h1 + 6), "sheet (texture)", fill=(60, 50, 40)); d.text((1008, 34 + h1 + 6), "models, front ortho", fill=(60, 50, 40))
        im.paste(r2[0], (0, 34 + h1 + 26)); im.paste(r2[1], (1000, 34 + h1 + 26))
        d.text((8, 34 + h1 + 26 + 568), "3/4", fill=(60, 50, 40)); d.text((1008, 34 + h1 + 26 + 568), "back", fill=(60, 50, 40))
        im.save(os.path.join(MODEL, "preview_uvcheck.png"))
    pf = [os.path.join(WORK, f"pose_{ch}_{v}.png") for ch in CHARS for v in "ab"]
    if all(os.path.exists(f) for f in pf):
        g = grid(pf, [f"{ch} {v}" for ch in CHARS for v in ("front-ish", "side-ish")], 6, (320, 480),
                 "pose test: elbows, finger curl, thigh + knee, spine, head turn, jaw open, half blink (eyelids Y x6), "
                 "mantleL + mantleBack + beard1/2 / nemes1L + nemesBack / scarf2 + braid1/2")
        g.save(os.path.join(MODEL, "preview_pose.png"))
    print("composed previews ->", MODEL)


def proof():
    """$EX_WORK/uvproof.png: the ID render with every (piece, region) in its demo colour and a thin dark outline,
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
    print("proof ->", os.path.join(WORK, "uvproof.png"))


if not IN_BLENDER:
    if __name__ == "__main__":
        mode = sys.argv[1] if len(sys.argv) > 1 else "faces"
        def run_all():
            import subprocess
            bl = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
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
                      "uvOrderOK", i.get("uvOrderOK"))
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
ONLY = [c for c in os.environ.get("EX_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()


# =============================================================================================== context + skeleton
class Ctx:
    def __init__(self, ch):
        self.ch = ch; self.s = SPEC[ch]; self.L = landmarks(ch); self.F = face_layout(ch)
        self.H = self.L["top"] - self.L["chin"]; self.S = self.s.get("S", self.s["height"] / 0.30)
        self.blend = 0.006 * self.S
        self.parts = []; self.B = {}; self.hand = {}

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


def build_leg(C, side, shoe_top, reg_shoe, pointy=0.0, top_y=0.050, regfn2=None, rows_in=None, rk=1.0):
    """Lower leg + foot from LEG_ROWS (or rows_in, e.g. LEG_ROWS_KNEE for bare shins); rk thins the leg above the
    ankle (Exodus addition, defaults keep Ruth's behaviour)."""
    s = C.s; sd = 1 if side == "L" else -1
    k = s["footScale"]; Sy = C.S * 0.95
    xc = C.B["thigh" + side][1].x * sd
    rows = []
    for y, x0, out, inn, fr, bk, zc in (rows_in or LEG_ROWS):
        if y > top_y + 1e-6:
            continue
        kk = k * (lerp(1.0, rk, smoothstep(0.022, 0.034, y)) if rk != 1.0 else 1.0)
        rows.append((y * Sy, xc, out * kk * C.S, inn * kk * C.S, fr * kk * C.S, bk * kk * C.S, zc * k * C.S))
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


# =============================================================================================== heads (from Ruth)
def esther_like_rim(C, front=0.38, scale=1.0):
    L = C.L; H = C.H

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, L["brow"] + front * H), (0.05, L["brow"] + (front - 0.03) * H), (0.09, L["brow"] + 0.24 * H),
                      (0.13, L["brow"] + 0.05 * H), (0.165, L["eye"] - 0.06 * H), (0.20, L["nose"] - 0.04 * H),
                      (0.24, L["mouth"] - 0.10 * H), (0.30, L["chin"] - 0.04 * H), (0.40, L["chin"] - 0.08 * H),
                      (0.50, L["chin"] - 0.10 * H)], uu)[0]
    return rim


def hair_cull(C, rim):
    s = C.s; S = C.S; nb = s["neckBase"]

    def cull(p):
        u = head_u(C, p); ry = rim(u)
        if p.y < nb - 0.0060 * S:
            return True
        return (p.y > ry + 0.0045 * S and p.z < 0.70 * s["hw"]) or p.y > ry + 0.0080 * S
    return cull



# =============================================================================================== Exodus: shared bits
def open_front(C, cg, rows, gap, N_=32, e_=2.5, fade_deg=70.0):
    """Open a garment shell cleanly down the front (Boaz's abaya method): in superellipse angle space push the centre
    column to +gap(y) and its left neighbour to -gap(y) (fading out by fade_deg so the sleeve ports stay put), then
    drop the faces between them. rows = the shell's rows (y, hw, zf, zb)."""
    S = C.S; dlt = 2 * math.pi / N_; fade = math.radians(fade_deg)

    def on_arm(c):
        for side in "LR":
            A_ = C.arm[side]; sv = (c - A_["S0"]).dot(A_["d"])
            if sv > 0.004 * S and (c - (A_["S0"] + A_["d"] * sv)).length < 0.03 * S:
                return True
        return False
    for i, p in enumerate(cg.v):
        if on_arm(p) or p.z < -0.002:
            continue
        hw_, zf_, zb_ = table(rows, p.y); zc_ = (zf_ + zb_) / 2; rd_ = (zf_ - zb_) / 2
        X = p.x / hw_; Z = (p.z - zc_) / rd_
        scl = (abs(X) ** e_ + abs(Z) ** e_) ** (1 / e_)
        if scl < 1e-6:
            continue
        a0 = math.atan2(math.copysign(abs(X / scl) ** (e_ / 2), X), math.copysign(abs(Z / scl) ** (e_ / 2), Z))
        g = gap(p.y)
        if a0 >= -1e-6:
            a1 = a0 + g * (1 - smoothstep(0.0, fade, a0))
        else:
            a1 = a0 - (g - dlt) * (1 - smoothstep(dlt, fade, -a0))
        cg.v[i] = V(se(math.sin(a1), e_) * hw_ * scl, p.y, zc_ + se(math.cos(a1), e_) * rd_ * scl)

    def opening(c):
        if on_arm(c):
            return False
        return c.z > 0 and abs(math.atan2(c.x, c.z)) < gap(c.y) * 0.85
    drop_faces(cg, opening)
    return on_arm


def sleeve_sv(C, p):
    """(side, distance along the arm, radial vector) when p lies in a sleeve tube, else None."""
    for side in "LR":
        A = C.arm[side]; sv = (p - A["S0"]).dot(A["d"])
        if sv > 0.004 * C.S:
            rv = p - (A["S0"] + A["d"] * sv)
            if rv.length < 0.030 * C.S:
                return side, sv, rv
    return None


def retag(cg, fn):
    """Re-tag cage faces: fn(centroid, old region) -> region."""
    for i, q in enumerate(cg.f):
        c = sum((cg.v[k] for k in q), V()) / len(q)
        cg.reg[i] = fn(c, cg.reg[i])


def ring_rows_shell(C, rows, N, reg, wfn, nf=0, amp=0.0, e=2.5, hem_lip=True, pc=0, top_lip=False):
    """A plain closed garment shell (skirt / kilt) from rows (y, hw, zf, zb) top -> bottom, no sleeve ports, with
    optional radial pleats (nf folds, amp growing toward the hem) and a rolled hem."""
    cg = Cage(); angs = [2 * math.pi * j / N for j in range(N)]
    y0, yh = rows[0][0], rows[-1][0]

    def pts(y, hw, zf, zb, sc=1.0, dy=0.0):
        zc = (zf + zb) / 2; rd = (zf - zb) / 2; out = []
        for a in angs:
            t = smoothstep(y0, yh, y)
            pl = amp * (0.35 + 0.65 * t) * (abs(math.sin(nf * a / 2)) * 2 - 1) if nf else 0.0
            out.append(V(se(math.sin(a), e) * (hw + pl) * sc, y + dy, zc + se(math.cos(a), e) * (rd + pl) * sc))
        return out
    rings = [cg.ring(pts(*r), wfn) for r in rows]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    if hem_lip:
        y, hw, zf, zb = rows[-1]
        a = cg.ring(pts(y, hw, zf, zb, 0.97, 0.0004 * C.S), wfn); cg.bridge(rings[-1], a, reg, pc)
        b = cg.ring(pts(y, hw, zf, zb, 0.95, 0.0045 * C.S), wfn); cg.bridge(a, b, reg, pc)
    if top_lip:
        y, hw, zf, zb = rows[0]
        a = cg.ring(pts(y, hw, zf, zb, 0.92, -0.0004 * C.S), wfn); cg.bridge(a, rings[0], reg, pc)
    return cg


def shell_profile(rows, a, off, y_from, y_to, n=80, e=2.5):
    """Points down a garment shell at angle a from y_from to y_to and their cumulative arc lengths."""
    pts = [shell_point(rows, lerp(y_from, y_to, i / n), a, off, e) for i in range(n + 1)]
    s = [0.0]
    for p, q in zip(pts, pts[1:]):
        s.append(s[-1] + (q - p).length)
    return pts, s


def at_arclen(pts, s, x):
    if x <= 0:
        return pts[0]
    for i in range(1, len(s)):
        if s[i] >= x:
            t = (x - s[i - 1]) / max(1e-12, s[i] - s[i - 1])
            return pts[i - 1].lerp(pts[i], t)
    return pts[-1]


def rope(cg, path, r, wfn, reg, pc=0, strands=2, twist=0.0042, closed=False, N=6):
    """Twisted rope: `strands` thin tubes winding round the path (pitch `twist` per turn)."""
    fr = frame_along(path + ([path[0], path[1]] if closed else []))[:len(path)]
    L_ = [0.0]
    for p, q in zip(path, path[1:]):
        L_.append(L_[-1] + (q - p).length)
    for k in range(strands):
        ph = 2 * math.pi * k / strands
        pts = []
        for p, (T, A, B), l in zip(path, fr, L_):
            an = ph + 2 * math.pi * l / twist
            pts.append(p + (A * math.cos(an) + B * math.sin(an)) * (r * 0.55))
        if closed:
            pts = pts + [pts[0]]
        tube(cg, pts, [r * 0.62] * len(pts), N, wfn, reg, pc, cap0=not closed, cap1=not closed)


# =============================================================================================== Moses
def build_moses(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]

    # ---- shoulder-length white hair, high receding forehead, covers the ears
    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, L["brow"] + 0.44 * H), (0.06, L["brow"] + 0.42 * H), (0.10, L["brow"] + 0.30 * H),
                      (0.13, L["brow"] + 0.10 * H), (0.155, L["eye"] - 0.04 * H), (0.19, L["nose"] - 0.06 * H),
                      (0.23, L["chin"] - 0.20 * H), (0.30, nb + 0.002 * S), (0.40, nb - 0.006 * S),
                      (0.50, nb - 0.010 * S)], uu)[0]
    C.hair_rim = rim
    skeleton(C)
    build_head(C, hair_cull(C, rim))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0030, 0.0038, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        t = lerp(t, 0.0048, smoothstep(0.12, 0.24, uu) * smoothstep(L["brow"], L["mouth"], y))
        if uu < 0.12:
            t = lerp(t, 0.0018, smoothstep(L["brow"] + 0.46 * H, L["brow"] + 0.38 * H, y))
        return t * S

    def plumb(uu):
        return smoothstep(0.12, 0.20, uu)
    hair_shell(C, rim, thick, "hair", "hair", plumb=plumb, parting=False, waves=0.0010 * S, NU=32, NV=8, grooves=60,
               groove_amp=0.00040)
    # ---- full white beard over cheeks and chin + a drooping moustache (decal = mouth)
    top = [(0.00, L["mouth"] - 0.075 * H), (0.035, L["mouth"] - 0.060 * H), (0.07, L["mouth"] + 0.030 * H),
           (0.10, L["nose"] - 0.030 * H), (0.15, L["nose"] + 0.040 * H), (0.20, L["eye"] - 0.12 * H),
           (0.225, L["eye"] - 0.06 * H)]
    bot = [(0.00, L["chin"] - 0.22 * H), (0.08, L["chin"] - 0.20 * H), (0.14, L["chin"] - 0.10 * H),
           (0.19, L["chin"] + 0.06 * H), (0.21, L["mouth"] - 0.02 * H), (0.225, L["nose"] - 0.06 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0062, 0.0022, smoothstep(0.05, 0.225, uu)) * S
        t *= smoothstep(0.0, 0.18, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        return 0.0007 * S * math.cos(2 * math.pi * (u * 40)) * smoothstep(L["mouth"], L["chin"], y)
    build_beard(C, top, bot, bthick, bcurls, 0.225, L["chin"] - 0.22 * H, reg="hair")
    moustache(C, "moustache", L["mouth"] + 0.090 * H, 0.66 * s["hw"], 0.16 * H, -0.02 * H, 0.0027 * S,
              reg="hair", off=0.0016)
    # ---- cream tunic, sleeves to the wrist, hem at the ankle
    RT = scale_rows(KING_ROBE, k, kx)
    RT = [(y, hw * (1 - 0.06 * smoothstep(0.17, 0.02, y)), zf, zb) for y, hw, zf, zb in RT]
    sleeve_t = [(0.004, 0.0126), (0.014, 0.0122), (0.030, 0.0110), (0.048, 0.0103), (0.062, 0.0101), (0.074, 0.0103),
                (0.082, 0.0106), (0.088, 0.0108)]
    build_robe(C, RT, sleeve_t, None, nf=12, fold_amp=0.0012, sleeve_fold=0.0007, reg="tunic", name="tunic",
               N=28, step=0.0095)
    C.tunic_rows = C.robe_rows
    for side in "LR":
        build_forearm_hand(C, side, 0.046)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.030)
    # ---- twisted rope belt on the tunic (shows between the mantle panels), knot and two tails on his left
    yb = wy - 0.002 * S
    wbelt = C.w(["hips", "spine"])
    loop = [shell_point(C.tunic_rows, yb, 2 * math.pi * j / 56, 0.0007 * S) for j in range(56)]
    cg = Cage()                      # under the mantle: shows in the front opening only
    rope(cg, loop, 0.0018 * S, wbelt, "belt", closed=True, twist=0.0045 * S, N=5)
    kn = shell_point(C.tunic_rows, yb, math.radians(5), 0.0028 * S)
    blob(cg, kn, 0.0030 * S, 0.0026 * S, 0.0022 * S, wbelt, "belt", 0, NU=8, NV=5)
    wtail = C.w(["hips", ("thighL", 0.02 * S)], blend=0.02 * S)
    for dx, ln in ((-0.0020, 0.050), (0.0024, 0.040)):
        path = []
        for i in range(9):
            t = i / 8; y = yb - 0.002 * S - ln * S * t
            a = math.radians(5) + (dx * S / 0.04) * t
            path.append(shell_point(C.tunic_rows, y, a, (0.0030 + 0.0008 * math.sin(t * math.pi)) * S))
        rope(cg, path, 0.0017 * S, wtail, "belt", twist=0.0045 * S, N=4)
        blob(cg, path[-1] + V(0, -0.0018 * S, 0), 0.0016 * S, 0.0026 * S, 0.0016 * S, wtail, "belt", 0, NU=6, NV=4)
    C.add("belt", cg, subdiv=0)
    # ---- the shepherd's mantle: open front, wide sleeves to mid-forearm, broad vertical stripes, mid-shin
    RO = [(y, hw + 0.0030 * S + 0.0024 * S * smoothstep(0.20, 0.05, y), zf + 0.0032 * S + 0.0012 * S * smoothstep(0.20, 0.05, y),
           zb - 0.0034 * S - 0.0020 * S * smoothstep(0.22, 0.05, y)) for y, hw, zf, zb in RT]
    hemO = 0.058 * k
    RO = [r for r in RO if r[0] > hemO + 0.006] + [(hemO,) + tuple(table(RO, hemO))]
    RO[0] = (RO[0][0] - 0.0012 * S,) + RO[0][1:]
    sleeve_o = [(0.004, 0.0150), (0.014, 0.0148), (0.030, 0.0140), (0.046, 0.0138), (0.058, 0.0146), (0.066, 0.0158),
                (0.071, 0.0166), (0.074, 0.0170)]
    cg = build_robe(C, RO, sleeve_o, None, nf=9, fold_amp=0.0020, sleeve_fold=0.0012, bell_sag=0.0016 * S, reg="mantleA",
                    name="mantle", solidify=0.0012, keep=True, N=32, step=0.0080)
    mantle_rows = C.robe_rows
    C.robe_rows = C.tunic_rows                  # the rope belt / beard below measure the tunic

    def gap(y):         # half-angle of the front opening (wider toward the hem: the mantle hangs open)
        return math.radians(lerp(7.0, 17.0, smoothstep(nb, 0.05, y) ** 0.8))
    open_front(C, cg, mantle_rows, gap)
    # stripes: A on the front edges, then B / A / B round to the back; sleeves A with a dark cuff; dark hem band
    end_o = sleeve_o[-1][0] * S
    zc0 = sum(table(mantle_rows, y)[1] + table(mantle_rows, y)[2] for y in (0.10, 0.15, 0.20)) / 6
    y_hb = hemO + 0.010 * S; SA = 66.0           # true angle (the mantle is ~2.2x wider than deep: ~47 deg in shape space)

    def stripe(c, n, reg, k=0):
        if k == 1:                                   # sleeves: plain A with a dark cuff
            sl = sleeve_sv(C, c)
            return "mantleB" if sl and sl[1] > end_o - 0.011 * S else "mantleA"
        if c.y < y_hb:
            return "mantleB"
        a = abs(math.degrees(math.atan2(c.x, c.z - zc0)))
        return "mantleA" if a < SA or 90 <= a < 180 - SA else "mantleB"
    mp = C.parts[-1]
    mp["cuts"] = [(V(0, 0, zc0), V(math.cos(math.radians(a)), 0, -math.sin(math.radians(a)))) for a in (SA, -SA, 90.0)] \
        + [(V(0, y_hb, 0), V(0, 1, 0))]
    mp["retag"] = stripe
    # front panels on mantleL / mantleR, the back drape on mantleBack
    zfc = table(mantle_rows, chestY)[1]; zbc = table(mantle_rows, chestY)[2]
    for side, sd in (("L", 1), ("R", -1)):
        x0 = sd * table(mantle_rows, chestY)[0] * 0.42
        C.B["mantle" + side] = (V(x0, chestY - 0.004 * S, zfc + 0.002 * S),
                                V(sd * table(mantle_rows, hemO + 0.01)[0] * 0.50, hemO + 0.004, table(mantle_rows, hemO + 0.01)[1] + 0.004 * S),
                                "chest")
    C.B["mantleBack"] = (V(0, chestY - 0.004 * S, zbc - 0.002 * S),
                         V(0, hemO + 0.004, table(mantle_rows, hemO + 0.01)[2] - 0.006 * S), "chest")
    for i, p in enumerate(cg.v):
        if sleeve_sv(C, p):
            continue
        a = math.atan2(p.x, p.z + 0.001)
        tw = smoothstep(chestY + 0.004 * S, chestY - 0.040 * S, p.y) * smoothstep(math.radians(80), math.radians(30), abs(a))
        if tw > 0 and p.z > 0:
            cg.w[i] = mixw((cg.w[i], 1 - 0.85 * tw), ({"mantle" + ("L" if p.x > 0 else "R"): 1.0}, 0.85 * tw))
            continue
        tb = smoothstep(chestY - 0.006 * S, chestY - 0.050 * S, p.y) * smoothstep(math.radians(105), math.radians(150), abs(a))
        if tb > 0:
            cg.w[i] = mixw((cg.w[i], 1 - 0.85 * tb), ({"mantleBack": 1.0}, 0.85 * tb))
    # ---- the long beard: hangs from the chin in front of the chest, strands, a soft two-lobed tip (beard1 / beard2)
    zf_chin = C.head.at(0.0, L["chin"] + 0.02 * H).z
    y_top = L["chin"] + 0.05 * H; y_tip = chestY - 0.010 * S
    neck_zf = s["neck"][1]

    def zback(y):
        z = neck_zf + 0.0012 * S
        if y < C.tunic_rows[0][0]:
            z = max(z, table(C.tunic_rows, y)[1] + 0.0042 * S)
        return z

    def bt(y):
        return min(1.0, max(0.0, (y_top - y) / (y_top - y_tip)))
    zmid = lambda y: (zback(y) + lerp(zf_chin + 0.0050 * S, zback(y) + 0.0040 * S, bt(y) ** 1.2)) / 2
    C.B["beard1"] = (V(0, L["chin"] - 0.04 * H, zmid(L["chin"] - 0.04 * H)), V(0, lerp(y_top, y_tip, 0.52), zmid(lerp(y_top, y_tip, 0.52))), "jaw")
    C.B["beard2"] = (C.B["beard1"][1].copy(), V(0, y_tip, zmid(y_tip)), "beard1")
    wb = C.w(["beard1", "beard2"], blend=0.010 * S)

    def wbeard(p):
        t = bt(p.y); wt = smoothstep(0.22, 0.0, t)
        return mixw(({"jaw": 0.65, "head": 0.35}, wt), (wb(p), 1 - wt)) if wt > 0 else wb(p)
    cg = Cage(); NB = 16; NR = 12
    W0 = 0.86 * s["hw"]
    for j in range(NR + 1):
        t = j / NR; y = lerp(y_top, y_tip, t ** 0.92)
        W = W0 * (1.0 + 0.12 * math.sin(math.pi * min(1.0, t * 1.3))) * max(0.0, 1 - t ** 2.4) ** 0.50
        W = max(W, 0.0010 * S)
        zb_ = zback(y); zf_ = lerp(zf_chin + 0.0050 * S, zb_ + 0.0040 * S, t ** 1.2) + 0.0018 * S * math.sin(math.pi * t)
        zc_ = (zf_ + zb_) / 2; rd = max(0.0008 * S, (zf_ - zb_) / 2)
        row = []
        for i in range(NB):
            a = 2 * math.pi * i / NB
            x = se(math.sin(a), 2.4) * W
            yy = y + (0.0030 * S * math.cos(2 * math.pi * x / (W0 * 1.1)) * smoothstep(0.75, 1.0, t))   # two-lobed tip
            row.append(V(x, yy, zc_ + se(math.cos(a), 2.4) * rd))
        rows_ = cg.ring(row, wbeard)
        if j:
            cg.bridge(prev, rows_, "hair", 0)
        else:
            first = rows_
        prev = rows_
    cg.fan(list(reversed(first)), V(0, y_top + 0.004 * S, zmid(y_top)), wbeard, "hair", 0)
    cg.fan(prev, V(0, y_tip - 0.003 * S, zmid(y_tip)), wbeard, "hair", 0)

    def bpost(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            t = bt(p.y)
            g = 0.00055 * S * math.cos(2 * math.pi * p.x / (0.0040 * S) + 3.0 * t) * smoothstep(0.02, 0.15, t)
            sway = 0.0010 * S * math.sin(t * 2.6 * math.pi) * t
            out.append(p + n * g + V(sway, 0, 0))
        return out
    C.add("beardLong", cg, post=bpost, subdiv=1)
    # ---- the gnarled staff in the right fist: as tall as he is, a crook knot on top (staff, staffTip)
    g = grip_point(C, "R", 0.0030)
    top_y = 0.352
    cg = Cage()
    bot = V(g.x - 0.002 * S, 0.0030, g.z + 0.0012 * S)
    T = V(g.x + 0.0006 * S, top_y, g.z - 0.0004 * S)
    path = []
    for i in range(17):
        t = i / 16
        p = bot.lerp(T, t)
        p += V(0.0014 * S * math.sin(t * 9.0 + 0.4) * (1 - t * 0.4), 0, 0.0010 * S * math.sin(t * 6.0 + 1.3))
        path.append(p)
    r_c = 0.0105 * S; Cc = T + V(-r_c, 0, 0)
    for i in range(1, 12):
        th = math.radians(220.0 * i / 11)
        path.append(Cc + V(r_c * math.cos(th), r_c * math.sin(th) * 1.05, 0.0006 * S * math.sin(th)))
    n_ = len(path)
    rads = [(0.0028 + 0.0007 * (i / 16)) * S if i <= 16 else (0.0034 - 0.0010 * (i - 16) / (n_ - 17)) * S for i in range(n_)]
    rads = [r * (1 + 0.10 * math.sin(i * 2.3)) for i, r in enumerate(rads)]
    tube(cg, path, rads, 8, None, "staff", 0, cap0=True, cap1=False, cap_len=0.4)
    blob(cg, path[-1] + (path[-1] - path[-2]).normalized() * 0.0012 * S, 0.0034 * S, 0.0034 * S, 0.0032 * S, None,
         "staff", 0, NU=10, NV=6)                                   # the knot at the end of the crook
    for t, sx in ((0.18, 1), (0.36, -1), (0.62, 1), (0.84, -1)):    # knots in the wood
        p = cr_open(path[:17], t)
        blob(cg, p + V(sx * 0.0026 * S, 0, 0.0008 * S), 0.0012 * S, 0.0018 * S, 0.0012 * S, None, "staff", 0, NU=6, NV=4)
    C.add("staff", cg, subdiv=0, rigid="staff")
    C.B["staff"] = (g.copy(), T.copy(), "handR")
    ctop = Cc + V(0, r_c * 1.05, 0)
    C.B["staffTip"] = (ctop.copy(), ctop + V(0, 0.010 * S, 0), "staff")


# =============================================================================================== Pharaoh
PHARAOH_TORSO = [(0.2760, 0.0110, 0.0100, -0.0108), (0.2745, 0.0175, 0.0112, -0.0122), (0.2725, 0.0262, 0.0124, -0.0134),
                 (0.2705, 0.0340, 0.0132, -0.0140), (0.2690, 0.0392, 0.0136, -0.0143), (0.2675, 0.0420, 0.0140, -0.0145),
                 (0.2620, 0.0436, 0.0152, -0.0148), (0.2540, 0.0414, 0.0166, -0.0150), (0.2440, 0.0372, 0.0168, -0.0146),
                 (0.2320, 0.0326, 0.0150, -0.0138), (0.2180, 0.0298, 0.0140, -0.0132), (0.2040, 0.0306, 0.0142, -0.0138),
                 (0.1900, 0.0326, 0.0148, -0.0146), (0.1780, 0.0330, 0.0150, -0.0148)]
# leg rows (David scale, as LEG_ROWS) extended above the knee for the bare shins under the kilt
LEG_ROWS_KNEE = [(0.100, 0.0186, 0.0098, 0.0094, 0.0080, 0.0082, 0.0004), (0.0865, 0.0187, 0.0090, 0.0085, 0.0084, 0.0072, 0.0010),
                 (0.078, 0.0188, 0.0084, 0.0078, 0.0070, 0.0078, 0.0006), (0.070, 0.0189, 0.0092, 0.0086, 0.0062, 0.0092, 0.0004)] + LEG_ROWS


def build_pharaoh(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; hipY = s["hipY"]
    y_band = L["brow"] + 0.20 * H                   # lower edge of the nemes forehead band

    def nrim(u):        # nemes edge: forehead band, down beside the face, lappets to the chest, wings on the shoulders
        uu = mirror_u(u)
        return table([(0.000, y_band), (0.090, y_band - 0.010 * H), (0.125, L["brow"] + 0.02 * H),
                      (0.150, L["eye"] - 0.10 * H), (0.170, L["mouth"] - 0.10 * H), (0.185, chestY - 0.020 * S),
                      (0.245, chestY - 0.024 * S), (0.262, shY - 0.006 * S), (0.30, shY - 0.004 * S),
                      (0.38, shY - 0.012 * S), (0.44, chestY - 0.018 * S), (0.50, chestY - 0.030 * S)], uu)[0]

    def cull(p):
        if p.y < nb - 0.0060 * S:
            return True
        u = head_u(C, p); uu = mirror_u(u)
        ry = max(nrim(u), L["chin"] + 0.10 * H) if uu > 0.14 else nrim(u)
        return p.y > ry + 0.0055 * S and (uu > 0.10 or p.y > y_band + 0.006 * S)
    skeleton(C)
    build_head(C, cull)
    # ---- bare torso and arms (a skin "robe" whose sleeves are the upper arms; forearms from build_forearm_hand)
    RB = scale_rows(PHARAOH_TORSO, k, kx)
    arm = [(0.004, 0.0104), (0.012, 0.0102), (0.022, 0.0091), (0.032, 0.0079), (0.042, 0.0069), (0.050, 0.0062),
           (0.056, 0.0058), (0.062, 0.0057)]
    build_robe(C, RB, arm, None, nf=12, fold_amp=0.0, sleeve_fold=0.0, reg="skin", name="torso", sleeve_lip=None,
               N=36, step=0.0070)
    C.torso_rows = C.robe_rows
    for side in "LR":
        build_forearm_hand(C, side, 0.004)
    # chest / collarbone / belly shaping: a soft muscle hint on the torso front
    tpart = C.parts[-3] if C.parts[-3]["name"] == "torso" else [p for p in C.parts if p["name"] == "torso"][0]
    old_post = tpart["post"]

    def tpost(pts, nrm):
        out = old_post(pts, nrm); res = []
        for p, q, n in zip(pts, out, nrm):
            if p.z > 0 and not sleeve_sv(C, p):
                for sx in (-1, 1):       # pectorals
                    q = q + n * 0.0010 * S * math.exp(-((p.x - sx * 0.016 * S) / (0.010 * S)) ** 2 - ((p.y - (chestY - 0.004 * S)) / (0.008 * S)) ** 2)
                q = q - n * 0.0005 * S * math.exp(-(p.x / (0.0025 * S)) ** 2) * smoothstep(chestY + 0.01 * S, chestY - 0.03 * S, p.y)
            res.append(q)
        return res
    tpart["post"] = tpost
    # ---- pleated white kilt with a red belt and a red-and-gold apron
    hem = 0.112 * k + 0.004
    KR = [(wy + 0.0050 * S, 0.0322 * kx, 0.0150, -0.0140), (wy - 0.004 * S, 0.0330 * kx, 0.0158, -0.0146),
          (hipY, 0.0352 * kx, 0.0172, -0.0156), (hipY - 0.025, 0.0390 * kx, 0.0196, -0.0170),
          (lerp(hipY - 0.025, hem, 0.5), 0.0428 * kx, 0.0222, -0.0186), (hem, 0.0466 * kx, 0.0248, -0.0200)]
    KR = resample_rows(KR, [KR[0][0] - (KR[0][0] - hem) * i / 14 for i in range(15)])
    wk0 = C.w(["hips", "spine"])
    hipX = s["hipX"]

    def wkilt(p):
        w = wk0(p)
        if p.y >= hipY:
            return w
        tt = min(1.0, (hipY - p.y) / (hipY - hem)); kk = 0.80 * smoothstep(0.0, 0.6, tt)
        sL = min(1.0, max(0.0, 0.5 + p.x / (3.0 * hipX)))
        w = {b: v * (1 - kk) for b, v in w.items()}
        w["thighL"] = w.get("thighL", 0) + kk * sL; w["thighR"] = w.get("thighR", 0) + kk * (1 - sL)
        return w
    cg = ring_rows_shell(C, KR, 48, "kilt", wkilt, nf=24, amp=0.00075 * S)
    C.add("kilt", cg, subdiv=0)
    C.robe_rows = KR
    waist_band(C, "belt", "sash", wy - 0.0050 * S, wy + 0.0050 * S, 0.0010 * S, bulge=0.0010 * S, N=48)
    # apron: a trapezoid hanging from the belt in front, red with two gold bars (cut cleanly by planes)
    y0a, y1a = wy - 0.0048 * S, hem + 0.006
    cg = Cage(); NC = 6; NRa = 12
    grid = []
    for j in range(NRa + 1):
        y = lerp(y0a, y1a, j / NRa)
        hwA = lerp(0.0095, 0.0150, j / NRa) * S * 0.98
        zf_ = table(KR, y)[1]
        row = []
        for i in range(NC + 1):
            x = lerp(-hwA, hwA, i / NC)
            row.append(V(x, y, zf_ + 0.0026 * S - 0.0016 * S * (x / (hwA + 1e-9)) ** 2 * 0.5 + 0.0010 * S * (j / NRa)))
        grid.append(cg.ring(row, wkilt))
    for a, b in zip(grid, grid[1:]):
        cg.bridge(a, b, "sash", 0, closed=False)
    bars = [(lerp(y0a, y1a, 0.42), lerp(y0a, y1a, 0.50)), (lerp(y0a, y1a, 0.82), lerp(y0a, y1a, 0.90))]

    def apron_reg(c, n, r, k=0):
        return "bands" if any(b1 <= c.y <= b0 for b0, b1 in bars) else "sash"
    C.add("apron", cg, subdiv=0, solidify=0.0010 * S, cuts=[(V(0, y, 0), V(0, 1, 0)) for b in bars for y in b],
          retag=apron_reg)
    # ---- legs: bare shins from just above the knee, gold sandals
    for side in "LR":
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.101, rows_in=LEG_ROWS_KNEE, rk=0.80)
    # ---- broad collar along the torso surface (arc length from the neck), three raised bands + a beaded edge
    N_ = 48; NR = 7
    wcol = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S)])
    cg = Cage(); rings = []
    prof = []
    for j in range(N_):
        a = 2 * math.pi * j / N_
        pts, sl = shell_profile(C.torso_rows, a, 0.0012 * S, C.torso_rows[0][0], chestY - 0.045 * S)
        s0 = sl[min(range(len(pts)), key=lambda i: abs(pts[i].y - (nb - 0.0030 * S)))]
        ca = math.cos(a)
        wd = (0.026 * S if ca > 0 else 0.019 * S) * (0.55 + 0.45 * abs(ca)) + 0.004 * S * (1 - abs(ca))
        prof.append((pts, sl, s0, wd))
    for i in range(NR + 1):
        t = i / NR; row = []
        for pts, sl, s0, wd in prof:
            row.append(at_arclen(pts, sl, s0 + wd * t))
        rings.append(cg.ring(row, wcol))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "collar", 0)
    tor_c = lambda p: V(0, p.y, (table(C.torso_rows, p.y)[1] + table(C.torso_rows, p.y)[2]) / 2) if C.torso_rows[-1][0] <= p.y <= C.torso_rows[0][0] else V(0, p.y, 0)
    C.add("collar", cg, subdiv=0, solidify=0.0010 * S)
    # ridges: three raised round cords between the bands (tubes along rings 2, 4, 6) + bead drops on the outer edge
    cg = Cage()
    for t in (0.36, 0.72):
        loop = []
        for pts, sl, s0, wd in prof:
            loop.append(at_arclen(pts, sl, s0 + wd * t))
        nrm = [(p - tor_c(p)).normalized() for p in loop]
        loop = [p + n * 0.0011 * S for p, n in zip(loop, nrm)]
        tube(cg, loop + [loop[0]], [0.0008 * S] * (len(loop) + 1), 4, wcol, "collar", 0, cap0=False, cap1=False)
    for j, (pts, sl, s0, wd) in enumerate(prof):
        if j % 3:
            continue
        p = at_arclen(pts, sl, s0 + wd + 0.0016 * S)
        n = (p - tor_c(p)).normalized()
        blob(cg, p + n * 0.0010 * S, 0.0016 * S, 0.0020 * S, 0.0011 * S, wcol, "collar", 0, NU=6, NV=3)
    C.add("collarBeads", cg, subdiv=0)
    # ---- gold arm-bands (upper arms) and bracelets (wrists)
    cg = Cage()
    for side in "LR":
        A = C.arm[side]; d = A["d"]; X0 = perp(V(0, 0, 1), d); Y0 = d.cross(X0)
        for sv, r, hw_, bones in ((0.036 * S, table([(a * S, b * S) for a, b in arm], 0.036 * S)[0] + 0.0004 * S, 0.0022 * S,
                                   ["upperArm" + side]),):
            c = A["S0"] + d * sv
            pts = [c + (X0 * math.cos(2 * math.pi * j / 20) + Y0 * math.sin(2 * math.pi * j / 20)) * r for j in range(20)]
            band_loop(cg, pts, [(p - c).normalized() for p in pts], [d] * 20, hw_, 0.0010 * S, C.w(bones), "bands", 0)
        W = A["W"]; c = W - d * 0.0060 * S; hd = s["handDims"]; r = hd["wristW"] * 0.62
        pts = [c + (X0 * math.cos(2 * math.pi * j / 20) * 1.05 + Y0 * math.sin(2 * math.pi * j / 20) * 0.95) * r for j in range(20)]
        band_loop(cg, pts, [(p - c).normalized() for p in pts], [d] * 20, 0.0026 * S, 0.0010 * S,
                  C.w(["forearm" + side, "hand" + side], blend=0.006 * S), "bands", 0)
    C.add("bands", cg, subdiv=0)
    # ---- the nemes: hood() drape, flared wings, lappets on nemes1L / R, back tail on nemesBack; cut into stripes
    zbh = C.head.at(0.5, L["chin"] + 0.15 * H).z
    zb_bl = table(C.torso_rows, chestY)[2]
    C.B["nemesBack"] = (V(0, L["chin"] + 0.06 * H, zbh - 0.006 * S), V(0, chestY - 0.028 * S, zb_bl - 0.008 * S), "head")
    base_w = hood_weights(C, ["nemesBack", ("chest", None)])

    def wnemes(p):
        w = base_w(p)
        a = math.atan2(p.x, p.z + 0.001)
        tl = smoothstep(shY + 0.004 * S, shY - 0.026 * S, p.y) * smoothstep(math.radians(84), math.radians(60), abs(a))
        if tl > 0:
            w = mixw((w, 1 - tl), ({"nemes1" + ("L" if p.x > 0 else "R"): 1.0}, tl))
        return w

    def nthick(u, y):
        uu = mirror_u(u)
        return (0.0020 + 0.0016 * smoothstep(L["brow"], L["top"], y) + 0.0010 * smoothstep(0.15, 0.30, uu)) * S
    stripe_w = 0.0088 * S
    C.robe_rows = C.torso_rows
    hood(C, "nemes", "nemesA", nrim, nthick, wnemes, NU=44, NV=16, flare=1.00, body_off=0.0024, back_settle=0.80,
         front_pull=0.40, folds=(14, 0.0004), hem_wave=0.0002, solid=0.0012, loose_top=0.0, settle=0.92)
    npart = C.parts[-1]
    lo = chestY - 0.040 * S; hi = L["top"] + 0.012 * S
    cuts = []
    yv = y_band
    while yv > lo:
        cuts.append(yv); yv -= stripe_w
    yv = y_band + stripe_w * 1.25
    while yv < hi:
        cuts.append(yv); yv += stripe_w

    def nemes_reg(c, n, r, k=0):
        if c.y >= y_band:          # the forehead band (gold), then alternating stripes up over the crown
            i = int(math.floor((c.y - y_band) / stripe_w - 0.25))
            return "nemesB" if i <= 0 or i % 2 == 0 else "nemesA"
        i = int(math.floor((y_band - c.y) / stripe_w))
        return "nemesA" if i % 2 == 0 else "nemesB"
    npart["cuts"] = [(V(0, y, 0), V(0, 1, 0)) for y in cuts]; npart["retag"] = nemes_reg
    # lappet bones: from the shoulder line down to the lappet ends
    for side, sd in (("L", 1), ("R", -1)):
        p0 = C.hood_pt(0.215 if sd > 0 else 0.785, shY - 0.004 * S)
        p1 = C.hood_pt(0.215 if sd > 0 else 0.785, chestY - 0.020 * S)
        C.B["nemes1" + side] = (p0 + V(0, 0, 0.001 * S), p1 + V(0, 0, 0.001 * S), "chest")
    # ---- cobra (uraeus) on the brow band, gold
    cg = Cage(); wh = C.w(["head"])
    fp, fn = C.hood_pt(0.0, y_band + 0.004 * S), V(0, 0, 1)
    base = fp + V(0, 0, 0.0014 * S)
    path = [base + V(0, -0.0010 * S, -0.0006 * S), base + V(0, 0.0022 * S, 0.0012 * S), base + V(0, 0.0046 * S, 0.0010 * S),
            base + V(0, 0.0066 * S, 0.0016 * S)]
    tube(cg, path, [0.0017 * S, 0.0016 * S, 0.0015 * S, 0.0013 * S], 6, wh, "bands", 0, cap0=True, cap1=False)
    hc = path[-1] + V(0, 0.0012 * S, 0.0004 * S)
    blob(cg, hc + V(0, 0.0004 * S, -0.0004 * S), 0.0048 * S, 0.0042 * S, 0.0012 * S, wh, "bands", 0, NU=10, NV=5)  # the flared hood
    blob(cg, hc + V(0, 0.0026 * S, 0.0016 * S), 0.0014 * S, 0.0011 * S, 0.0017 * S, wh, "bands", 0, NU=6, NV=4)  # head
    C.add("cobra", cg, subdiv=0)
    # ---- false beard: a short braided gold beard under the chin, slightly pointed (jaw)
    cg = Cage(); wj = C.w(["jaw"])
    cz = C.head.at(0.0, L["chin"] + 0.04 * H).z
    path = [V(0, L["chin"] + 0.06 * H, cz - 0.0045 * S), V(0, L["chin"] - 0.10 * H, cz - 0.0010 * S),
            V(0, L["chin"] - 0.26 * H, cz + 0.0002 * S), V(0, L["chin"] - 0.36 * H, cz + 0.0020 * S)]
    path = [cr_open(path, i / 10) for i in range(11)]
    rr = [(0.0030 - 0.0014 * (i / 10) ** 1.5) * S * (1 + 0.10 * math.cos(i * math.pi)) for i in range(11)]
    tube(cg, path, rr, 8, wj, "bands", 0, cap0=True, cap1=True, cap_len=0.9)
    C.add("fbeard", cg, subdiv=0)
    # ---- the chariot (child of root, hidden by default): floor at y 0.035, curved breastwork with a red sun disc,
    # two six-spoke wheels (left one separate: wheelL), a short pole. Built round his feet, facing +Z.
    fl_y = 0.035; fl_th = 0.006
    ax_y = 0.034; ax_z = -0.004; wx = 0.060; wr = 0.034
    cg = Cage()
    # floor: a rounded box
    out = [(math.sin(2 * math.pi * j / 24) * 0.044, math.cos(2 * math.pi * j / 24) * 0.050) for j in range(24)]
    out = [(x * (1.0 if z > 0 else 0.98), z * (1.0 if z > 0 else 0.72) + 0.010) for x, z in out]
    extrude_outline(cg, out, fl_th, None, "chariot", 0, z0=0.0, bevel=0.10, origin=V(0, fl_y - fl_th, 0),
                    X=V(1, 0, 0), Y=V(0, 0, 1), Z=V(0, 1, 0))
    # breastwork: a wall round the front and sides, high at the front, sloping down toward the open back
    wall = []; nrm_w = []; hs = []
    for j in range(25):
        a = math.radians(-125 + 250 * j / 24)
        x = math.sin(a) * 0.044; z = math.cos(a) * 0.050 + 0.010
        if z < 0.010:
            z = 0.010 + (z - 0.010) * 0.72
        h = lerp(0.050, 0.118, (0.5 + 0.5 * math.cos(a)) ** 1.3)
        wall.append(V(x * 1.02, fl_y + h / 2, z * 1.02)); nrm_w.append(V(math.sin(a), 0, math.cos(a))); hs.append(h / 2)
    strip(cg, wall, nrm_w, hs, 0.0030, None, "chariot", 0)
    top_edge = [p + V(0, h, 0) + n * 0.0015 for p, h, n in zip(wall, hs, nrm_w)]
    tube(cg, top_edge, [0.0024] * len(top_edge), 6, None, "chariotTrim", 0, cap0=True, cap1=True)
    # red sun disc with a gold ring on the front
    sc_ = V(0, fl_y + 0.070, 0.0645)
    lathe_z(cg, sc_, [(0.0, 0.0), (0.0005, 0.0180), (0.0030, 0.0175), (0.0042, 0.0), ], 20, None,
            lambda a, b: "chariotTrim", 0)
    band_loop(cg, [sc_ + V(math.cos(2 * math.pi * j / 24) * 0.0195, math.sin(2 * math.pi * j / 24) * 0.0195, 0.0016)
                   for j in range(24)], [V(math.cos(2 * math.pi * j / 24), math.sin(2 * math.pi * j / 24), 0) for j in range(24)],
              [V(0, 0, 1)] * 24, 0.0020, 0.0016, None, "chariot", 0)
    # the pole: from under the front of the floor forward, rising, with a knob
    pp = [V(0, fl_y - 0.004, 0.040), V(0, fl_y - 0.002, 0.080), V(0, fl_y + 0.006, 0.120), V(0, fl_y + 0.016, 0.150)]
    tube(cg, [cr_open(pp, i / 8) for i in range(9)], [0.0034] * 9, 6, None, "chariot", 0, cap0=True, cap1=False)
    blob(cg, pp[-1] + V(0, 0.002, 0.003), 0.0055, 0.0055, 0.0055, None, "chariotTrim", 0, NU=8, NV=5)
    # axle under the floor
    tube(cg, [V(-wx - 0.004, ax_y, ax_z), V(wx + 0.004, ax_y, ax_z)], [0.0028, 0.0028], 6, None, "chariot", 0)

    def wheel(cg_, cx):
        c = V(cx, ax_y, ax_z)
        rim_pts = [c + V(0, math.sin(2 * math.pi * j / 28) * (wr - 0.003), math.cos(2 * math.pi * j / 28) * (wr - 0.003))
                   for j in range(28)]
        tube(cg_, rim_pts + [rim_pts[0]], [(0.0030, 0.0036)] * 29, 6, None, "chariot", 0, ref=V(1, 0, 0), cap0=False, cap1=False)
        for i in range(6):
            a = 2 * math.pi * i / 6 + 0.26
            d = V(0, math.sin(a), math.cos(a))
            tube(cg_, [c + d * 0.004, c + d * (wr * 0.55), c + d * (wr - 0.005)], [0.0016, 0.0014, 0.0016], 5, None,
                 "chariot", 0, cap0=False, cap1=False)
        tube(cg_, [c - V(0.0065, 0, 0), c - V(0.0035, 0, 0), c + V(0.0035, 0, 0), c + V(0.0065, 0, 0)],
             [0.0040, 0.0062, 0.0062, 0.0040], 10, None, "chariotTrim", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
    wheel(cg, -wx)
    C.add("chariot", cg, subdiv=0, rigid="chariot")
    C.B["chariot"] = (V(0, fl_y, 0), V(0, fl_y + 0.030, 0), "root")
    cg = Cage()
    wheel(cg, wx)
    C.add("wheelL", cg, subdiv=0, rigid="wheelL")
    C.B["wheelL"] = (V(wx, ax_y, ax_z), V(wx + 0.020, ax_y, ax_z), "chariot")


# =============================================================================================== Miriam
def build_miriam(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]
    rim = esther_like_rim(C, 0.37)
    C.hair_rim = rim
    skeleton(C)
    build_head(C, hair_cull(C, rim))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0030, 0.0042, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        t = lerp(t, 0.0036, smoothstep(0.10, 0.20, uu) * smoothstep(L["eye"], L["mouth"], y))
        if uu < 0.12:
            t = lerp(t, 0.0022, smoothstep(L["brow"] + 0.43 * H, L["brow"] + 0.34 * H, y))
        return t * S

    def plumb(uu):
        return smoothstep(0.12, 0.18, uu) * smoothstep(0.44, 0.30, uu)
    hair_shell(C, rim, thick, "hair", "hair", plumb=plumb, parting=True, waves=0.0007 * S, NU=32, NV=7)
    # ---- saffron dress, three-quarter sleeves with embroidered cuffs, embroidered hem border
    R = scale_rows(ESTHER_ROBE, k, kx)
    R = [(y, hw * (1.0 + 0.05 * smoothstep(0.20, 0.08, y)), zf, zb) for y, hw, zf, zb in R]
    sleeve = [(0.004, 0.0102), (0.012, 0.0100), (0.026, 0.0092), (0.040, 0.0088), (0.052, 0.0088), (0.062, 0.0094),
              (0.068, 0.0101), (0.071, 0.0104), (0.078, 0.0110), (0.082, 0.0112)]
    build_robe(C, R, sleeve, None, nf=16, fold_amp=0.0019, sleeve_fold=0.0010, bell_sag=0.0010 * S, reg="dress",
               name="dress")
    dpart = C.parts[-1]; cgd = dpart["cage"]
    hem = C.robe_rows[-1][0]; y_hb = hem + 0.0150 * S
    cuff = 0.0705 * S

    def dress_reg(c, n, r, k=0):
        sl = sleeve_sv(C, c)
        if k == 1:
            return "hem" if sl and sl[1] > cuff else "dress"
        return "hem" if c.y < y_hb else "dress"
    dpart["cuts"] = [(V(0, y_hb, 0), V(0, 1, 0))]; dpart["retag"] = dress_reg
    old = dpart["post"]

    def dpost(pts, nrm):                    # a little zig-zag embroidery relief in the border
        out = old(pts, nrm); res = []
        for p, q in zip(pts, out):
            if p.y < y_hb and p.y > hem + 0.002 * S and not sleeve_sv(C, p):
                a = math.atan2(p.x, p.z + 0.001)
                zz = abs(((a * 22 / math.pi) % 2) - 1)
                m = abs((p.y - hem - 0.002 * S) / (y_hb - hem - 0.002 * S) - zz)
                hn = V(p.x, 0, p.z).normalized()
                q = q + hn * 0.00045 * S * math.exp(-(m / 0.18) ** 2)
            res.append(q)
        return res
    dpart["post"] = dpost
    for side in "LR":
        build_forearm_hand(C, side, 0.022 * S)
        build_leg(C, side, 0.0, "skin")
    # ---- rust-red woven belt, tie with two tails on her right
    waist_band(C, "belt", "belt", wy - 0.0052 * S, wy + 0.0052 * S, 0.0009 * S, bulge=0.0010 * S)
    belt_tie(C, "beltTie", "belt", -0.0110 * S, wy, [(-0.0016, wy - 0.044 * S), (0.0014, wy - 0.054 * S)], 0.0019)
    # ---- coral bead necklace at the throat, lying on the dress neckline
    cg = Cage(); wn = C.w(["chest", ("neck", 0.010 * S)])
    for i in range(19):
        a = math.radians(-74 + 148 * i / 18)
        y = nb - 0.0040 * S - 0.0110 * S * math.cos(a) ** 2
        p = robe_point(C, y, a, 0.0016 * S)
        rb = 0.0016 * S if i % 2 == 0 else 0.0012 * S
        if i == 9:
            rb = 0.0022 * S
        blob(cg, p, rb, rb, rb * 0.9, wn, "necklace", 0, NU=6, NV=4)
    C.add("necklace", cg, subdiv=0)
    # ---- teal head-scarf over the head, ends on the shoulders, tail down the back (scarf1 / scarf2)
    zbh = C.head.at(0.5, L["chin"] + 0.15 * H).z
    zb_bl = table(C.robe_rows, chestY)[2]
    C.B["scarf1"] = (V(0, L["chin"] + 0.10 * H, zbh - 0.003 * S), V(0, chestY, zb_bl - 0.006 * S), "head")
    C.B["scarf2"] = (V(0, chestY, zb_bl - 0.006 * S), V(0, s["hipY"] + 0.004 * S, table(C.robe_rows, s["hipY"])[2] - 0.006 * S), "scarf1")

    def srim(u):
        uu = mirror_u(u)
        return table([(0.000, L["top"] - 0.040 * H), (0.050, L["top"] - 0.060 * H), (0.095, L["brow"] + 0.24 * H),
                      (0.135, L["eye"] + 0.04 * H), (0.165, L["nose"] - 0.06 * H), (0.185, L["mouth"] - 0.12 * H),
                      (0.195, L["chin"] - 0.20 * H), (0.205, shY - 0.004 * S), (0.215, chestY - 0.010 * S),
                      (0.235, chestY - 0.014 * S), (0.26, shY - 0.012 * S), (0.29, shY - 0.026 * S),
                      (0.34, chestY - 0.012 * S), (0.40, wy - 0.004 * S), (0.46, s["hipY"] + 0.004 * S),
                      (0.50, s["hipY"] - 0.006 * S)], uu)[0]

    def sthick(u, y):
        uu = mirror_u(u)
        return (0.0021 + 0.0013 * smoothstep(L["brow"], L["top"], y) + 0.0010 * smoothstep(0.15, 0.30, uu)) * S
    hood(C, "scarf", "scarf", srim, sthick, hood_weights(C, ["scarf1", "scarf2", ("chest", None)]), NU=50, NV=20,
         flare=0.07, body_off=0.0022, front_pull=0.40, folds=(13, 0.0019), hem_wave=0.0014, solid=0.0010)
    # ---- thick three-strand braid: from under the scarf beside her left cheek, over the scarf end, down to the waist
    ub = 0.205
    p_start = C.head.at(0.27, L["chin"] + 0.04 * H)
    ys = [nb - 0.002 * S, shY - 0.012 * S, chestY - 0.012 * S, wy + 0.004 * S]
    ctrl = [p_start]
    for y in ys:
        q = C.hood_pt(ub, y); c0 = V(0, y, (table(C.robe_rows, min(y, C.robe_rows[0][0]))[1] + table(C.robe_rows, min(y, C.robe_rows[0][0]))[2]) / 2)
        hn = hor(q - c0).normalized()
        q = q + hn * 0.0052 * S
        if y < chestY:
            q.x = lerp(q.x, 0.0150 * S, smoothstep(chestY, wy, y))
        ctrl.append(q)
    path = [cr_open(ctrl, i / 60) for i in range(61)]
    for _ in range(6):                                           # relax: no kinks
        path = [path[0]] + [(path[i - 1] + path[i] * 2 + path[i + 1]) / 4 for i in range(1, 60)] + [path[-1]]
    seg = []; acc = 0.0
    for p, q in zip(path, path[1:]):
        acc += (q - p).length; seg.append(acc)
    total = seg[-1]
    C.B["braid1"] = (path[6].copy(), path[30].copy(), "head")
    C.B["braid2"] = (path[30].copy(), path[-1].copy(), "braid1")
    wbr = C.w(["braid1", "braid2"], blend=0.010 * S)

    def wbraid(p):
        wt = smoothstep(nb - 0.004 * S, L["chin"] - 0.02 * H, p.y)
        return mixw(({"head": 1.0}, wt), (wbr(p), 1 - wt)) if wt > 0 else wbr(p)
    cg = Cage(); rb = 0.0040 * S
    step = 0.0066 * S; n_lobes = int((total - 0.010 * S) / step)
    for i in range(n_lobes):
        f = (0.004 * S + step * (i + 0.5)) / total
        p = cr_open(path, f); p2 = cr_open(path, min(1.0, f + 0.01))
        d = (p2 - p).normalized()
        out_ = hor(p - V(0, p.y, 0)).normalized()
        side = d.cross(out_).normalized()
        sg = 1 if i % 2 == 0 else -1
        ax = (d + side * 0.80 * sg).normalized()
        A_ = perp(out_, ax); B_ = ax.cross(A_)
        M = Matrix((A_, ax, B_)).transposed()
        taper = 1.0 - 0.30 * f
        blob(cg, p + side * (rb * 0.30 * sg), rb * 0.86 * taper, step * 0.95, rb * 0.78 * taper, wbraid, "hair", 0,
             NU=8, NV=5, ax=M)
    core = [cr_open(path, f) for f in [0.02 + 0.96 * i / 14 * (step * n_lobes) / total for i in range(15)]]
    tube(cg, core, [rb * 0.70 * (1 - 0.30 * i / 14) for i in range(15)], 8, wbraid, "hair", 0, cap0=True, cap1=False)
    pe = cr_open(path, (0.004 * S + step * n_lobes) / total)
    de = (path[-1] - path[-2]).normalized()
    tie_c = pe + de * 0.0010 * S
    lathe_pts = [tie_c + perp(V(1, 0, 0), de) * math.cos(2 * math.pi * j / 12) * rb * 0.62
                 + de.cross(perp(V(1, 0, 0), de)) * math.sin(2 * math.pi * j / 12) * rb * 0.62 for j in range(12)]
    band_loop(cg, lathe_pts, [(p - tie_c).normalized() for p in lathe_pts], [de] * 12, 0.0012 * S, 0.0009 * S, wbraid,
              "belt", 0)
    tube(cg, [tie_c + de * 0.0010 * S, tie_c + de * 0.0060 * S, tie_c + de * 0.0110 * S],
         [rb * 0.60, rb * 0.85, rb * 0.20], 8, wbraid, "hair", 0, cap0=True, cap1=True)
    C.add("braid", cg, subdiv=0)
    # ---- tambourine in the left hand (rigid, tambourine bone; hidden by default): wooden frame held by the rim,
    # a drum skin, four pairs of jingles, two ribbons
    A = C.arm["L"]; g = grip_point(C, "L", 0.0026)
    Rt = 0.024 * S; dep = 0.0042 * S
    cen = g + A["dh"] * (Rt + 0.0010 * S)
    U_ = -A["dh"]; W_ = A["Yh"]; Nax = U_.cross(W_).normalized()
    cg = Cage()
    circ = [cen + (U_ * math.cos(2 * math.pi * j / 32) + W_ * math.sin(2 * math.pi * j / 32)) * Rt for j in range(32)]
    band_loop(cg, circ, [(p - cen).normalized() for p in circ], [Nax] * 32, dep, 0.0016 * S, None, "tambourine", 0)
    skin = [cen + (p - cen) * 0.99 + Nax * (dep * 0.85) for p in circ]
    cg.fan(cg.ring(skin, None), cen + Nax * (dep * 0.85), None, "tambourine", 0)
    for j in (4, 12, 20, 28):
        a = 2 * math.pi * j / 32; rd = U_ * math.cos(a) + W_ * math.sin(a)
        c = cen + rd * (Rt + 0.0010 * S)
        M = Matrix((rd.cross(Nax).normalized(), rd, Nax)).transposed()
        for sz in (-1, 1):
            blob(cg, c + Nax * (sz * 0.0014 * S), 0.0028 * S, 0.0005 * S, 0.0028 * S, None, "tambourine", 0, NU=8, NV=3,
                 ax=Matrix((rd.cross(Nax).normalized(), Nax, rd)).transposed())
    for j, ln in ((15, 0.040), (17, 0.032)):
        a = 2 * math.pi * j / 32; rd = U_ * math.cos(a) + W_ * math.sin(a)
        p0 = cen + rd * (Rt + 0.0016 * S)
        pp = [p0 + V(0, -ln * S * t, 0) + rd * (0.004 * S * math.sin(t * 3.0)) + Nax * (0.003 * S * math.sin(t * 5.0 + j))
              for t in [i / 8 for i in range(9)]]
        strip(cg, pp, [Nax] * 9, [0.0022 * S * (1 - 0.3 * t) for t in [i / 8 for i in range(9)]], 0.0004 * S, None,
              "ribbons", 0)
    C.add("tambourine", cg, subdiv=0, rigid="tambourine")
    C.B["tambourine"] = (g.copy(), cen.copy(), "handL")
# =============================================================================================== Blender assembly
BUILDERS = {"moses": build_moses, "pharaoh": build_pharaoh, "miriam": build_miriam}
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
                hit = bvh.ray_cast(V(x, y, 0.2), V(0, 0, -1), 1.0)
                z = (hit[0].z if hit[0] else C.L["zc"] + 0.015) + 0.00055 * C.S
                col.append(V(x, y, z))
            cols.append(col)
        idx = [[cg.add(p, None) for p in col] for col in cols]
        for i in range(7):
            for j in range(3):
                cg.face((idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1]), "skin", 0)
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
    if pt.get("cuts") or pt.get("retag"):
        # clean region edges along planes (nemes stripes, apron bars, hem border): bisect, then re-tag faces by centroid
        bm = bmesh.new(); bm.from_mesh(o.data)
        for co, no in pt.get("cuts", []):
            geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
            bmesh.ops.bisect_plane(bm, geom=geom, plane_co=to_bl(co), plane_no=to_bl(no))
        lay = bm.faces.layers.int.get("st_region"); play = bm.faces.layers.int.get("st_piece")
        if pt.get("retag"):
            for f in bm.faces:
                c = to_design(f.calc_center_median()); n = to_design(f.normal)
                r = REGIONS[f[lay] - 1].split(".")[1]
                nr = pt["retag"](c, n, r, PIECES[f[play] - 1][2])      # piece k: 0 = garment body, 1 = sleeves
                if nr != r:
                    f[lay] = region_id(ch, nr)
        bm.to_mesh(o.data); bm.free(); o.data.update()
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
            if p.z < 0.0 or n.z < 0.3:
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
    (rigid props parented to bones keep their posed place). Used for Moses's stoop (as Ruth's Naomi)."""
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


REST_BAKE = {   # Moses: built straight (~0.38), then a slight stoop; arms hang plumb again, head tips back up
    "moses": [("chest", V(1, 0, 0), 8.0), ("neck", V(1, 0, 0), 8.0),
              ("head", V(1, 0, 0), -10.0), ("upperArmL", V(1, 0, 0), -8.0), ("upperArmR", V(1, 0, 0), -8.0)],
}


def is_hidden_prop(o):
    ch, _, part = o.name.partition("_")
    return PROPS.get(ch, {}).get(part) is False


def build_character(ch):
    C = Ctx(ch)
    BUILDERS[ch](C)
    order = CONTRACT_BONES + EXTRA_BONES[ch]
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
    baked = None
    if ch in REST_BAKE and not os.environ.get("EX_NOBAKE"):
        baked = bake_rest_pose(C, rig, bodyo, REST_BAKE[ch])
        for o in props:               # the stoop moved the fist a little: keep the staff foot on the page
            if o.name == f"{ch}_staff":
                ymin = min((to_design(o.matrix_world @ v.co)).y for v in o.data.vertices)
                dy = (0.0030 + sheet[1]) - ymin          # world y includes the sheet offset (rig at sheetY)
                for v in o.data.vertices:
                    v.co = v.co + o.matrix_world.inverted().to_3x3() @ to_bl(V(0, dy, 0))
                o.data.update()
                C.staff_foot_fix = dy
    vis = [bodyo] + [o for o in props if not is_hidden_prop(o)]
    stats = front_uv_with_occlusion([(o, o is not bodyo) for o in vis], sheet, ART_H, INSET,
                                    anchors=None, region_name=lambda r: REGIONS[r - 1].split(".")[1])
    if baked is not None:
        stats["restBakePropDrift"] = round(baked, 6)
    # regions / bbox report from the (final) rest pose; hidden props and eyelids do not count for the bbox
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
    m = bpy.data.materials.get("ex_page") or bpy.data.materials.new("ex_page")
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
    # ---- ID render (front ortho, 2x art rect, no AA): one colour per (piece, region); eyelids hidden
    setup_workbench((2000, round(2000 * ART_H)))
    s = sc(); s.render.film_transparent = True; s.display.render_aa = 'OFF'
    s.display.shading.light = 'FLAT'; s.display.shading.color_type = 'MATERIAL'
    front_ortho_camera()
    idmap = {}
    for o in all_meshes():
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)

        def mat_fn(k):
            if k not in idmap:
                idmap[k] = len(idmap) + 1
            n = idmap[k]
            return flat_mat(f"id_{n}", [c / 255 for c in id_colour(n)])
        set_face_materials(o, lambda p, r: (p, r), mat_fn)
    render(os.path.join(WORK, "id_2x.png"))
    ids = []
    for (p, r), n in sorted(idmap.items(), key=lambda kv: kv[1]):
        ch, pname, k = PIECES[p - 1]; rch, reg = REGIONS[r - 1].split(".")
        ids.append({"id": n, "rgb": id_colour(n), "char": ch, "part": pname, "piece": k, "region": reg,
                    "hex": PALETTE[ch].get(reg, "#cccccc")})
    json.dump({"note": "front-ortho ID render of the rest pose at sheet positions (2000 px = art width); background = "
                       "alpha 0; eyelids hidden", "size": [s.render.resolution_x, s.render.resolution_y], "ids": ids},
              open(os.path.join(WORK, "id_2x.json"), "w"), indent=1)
    for o in all_meshes():
        o.hide_render = False
    anchor_info = apply_pixel_anchors(os.path.join(WORK, "id_2x.png"), ids)
    fix_info = fix_uvs_by_id(os.path.join(WORK, "id_2x.png"), ids)
    report["uvFixByIdRender"] = fix_info
    # ---- regions_characters.json
    regions_out = {"version": 1, "generatedBy": "pipeline/ex_characters.py",
                   "note": "Per character: colourable regions (face attribute st_region), the mesh parts that carry "
                           "them, demo colour, bbox on the sheet (x, y in art units, y up from the art rect bottom), "
                           "and anchors (regions too small to colour take a constant UV inside a larger region). "
                           "ID render for the line art: id_characters_2x.png/.json (same scheme as D&G id_2x).",
                   "sheet": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in ONLY},
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
                         "parts": sorted(d["parts"]), "bboxSheet": bb if bb[0] < 9 else None}
            ai = anchor_info.get(ch, {})
            if reg in ai.get("anchors", {}):
                an = ai["anchors"][reg]
                regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
                regs[reg]["printNote"] = "too small to colour; print as detail line art, takes the colour at anchorUV"
            if reg in ai.get("propAnchors", {}):
                an = ai["propAnchors"][reg]
                regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
                regs[reg]["printNote"] = ("hidden-by-default prop, not printed with the figure; takes the colour at "
                                          "anchorUV (override: design.json characters.%s.propUV.%s = [u, v])" % (ch, reg))
        regions_out["characters"][ch] = {
            "height": CONTRACT_HEIGHT[ch], "bboxSheet": [round(v, 4) for v in allbb], "regions": regs,
            "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                          "files": {e: f"docs/exodus/design/faces/{ch}_{e}.png" for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z",
                         "bakedPose": [[b, d] for b, _, d in REST_BAKE.get(ch, [])],
                         "note": "Moses: the slight stoop (degrees about design X) is baked into the rest skeleton" if ch in REST_BAKE else ""},
            "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                      for b, v in PROPS[ch].items()},
            "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
    if SHEET_SRC == "defaults":
        json.dump({"note": "default sheet positions used by ex_characters.py (assets/exodus/design.json had none); the "
                           "Set + sheet role owns the real values in design.json characters.<id>.sheetX/sheetY",
                   "artHeightUnits": ART_H, "characters": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in CHARS}},
                  open(os.path.join(MODEL, "characters_layout.json"), "w"), indent=1)
    import shutil
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
    sc()["ex_regions"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({ch: {k: v for k, v in r.items() if k != "bones"} for ch, r in report["chars"].items()}))


GOLD = set()


def preview_material(ch, reg, decal_img):
    name = f"pv_{ch}_{reg}"
    m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree; nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial"); bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    nt.links.new(bsdf.outputs[0], out.inputs[0])
    col = [srgb_to_lin(c) for c in hex_rgb(PALETTE[ch].get(reg, "#cccccc"))] + [1.0]
    rgb = nt.nodes.new("ShaderNodeRGB"); rgb.outputs[0].default_value = col
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
        bsdf.inputs["Metallic"].default_value = 0.55; bsdf.inputs["Roughness"].default_value = 0.32
    else:
        bsdf.inputs["Roughness"].default_value = 0.72 if reg != "skin" else 0.55
        if reg == "skin":
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


def mode_preview():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    setup_eevee((640, 960)); preview_lights()
    imgs = {}
    for ch in CHARS:
        p = os.path.join(FACES, f"{ch}_{DEFAULT_EXPR[ch]}.png")
        if os.path.exists(p):
            imgs[ch] = bpy.data.images.load(p, check_existing=True)
    present = [ch for ch in CHARS if bpy.data.objects.get(f"{ch}_rig")]
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        set_face_materials(o, lambda p, r: r, lambda r: preview_material(ch, REGION_OF[r], imgs.get(ch)))
    cam = camera()

    def show(chs, props=False):
        for o in all_meshes():
            if o.name not in ("floor", "backdrop"):
                o.hide_render = o.name.split("_")[0] not in chs or (is_hidden_prop(o) and not props)
    for ch in [c for c in ONLY if c in present]:
        show([ch])
        rig = bpy.data.objects[f"{ch}_rig"]; x = rig.location.x; zb = rig.location.z
        Hh = SPEC[ch]["height"]; L = landmarks(ch)
        sc().render.resolution_x, sc().render.resolution_y = 640, 960
        for nm, yaw in (("front", 0), ("q34", 35), ("side", 90), ("back", 180)):
            turntable(cam, Vector((x, 0, zb + Hh * 0.50)), yaw, Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pv_{ch}_{nm}.png"))
        sc().render.resolution_x, sc().render.resolution_y = 640, 640
        hy = zb + (L["top"] + L["chin"]) / 2
        Hd = L["top"] - L["chin"]
        turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 30, Hd * 4.6, Hd * 0.25, 60); render(os.path.join(WORK, f"pv_{ch}_head.png"))
        turntable(cam, Vector((x, 0, hy - 0.05 * Hd)), 0, Hd * 4.6, Hd * 0.10, 60); render(os.path.join(WORK, f"pv_{ch}_headfront.png"))
        for s_ in "LR":
            pb = rig.pose.bones["fingers" + s_]; tgt = rig.matrix_world @ pb.head
            turntable(cam, tgt, 25 if s_ == "L" else -25, SPEC[ch]["hand"] * 4.6, SPEC[ch]["hand"] * 0.6, 60)
            render(os.path.join(WORK, f"pv_{ch}_hand{s_}.png"))
        show([ch], props=True)
        if ch == "pharaoh":         # the chariot stands on the page round his feet
            turntable(cam, Vector((x, 0, zb + Hh * 0.42)), 32, Hh * 2.7, Hh * 0.30, 60)
        else:
            turntable(cam, Vector((x, 0, zb + Hh * 0.62)), 28, Hh * 1.9, Hh * 0.10, 60)
        render(os.path.join(WORK, f"pv_{ch}_props.png"))
        show([ch])
        sc().render.resolution_x, sc().render.resolution_y = 420, 420
        for e in EXPRESSIONS[ch]:
            if not os.path.exists(os.path.join(FACES, f"{ch}_{e}.png")) or os.environ.get("EX_NO_EXPR"):
                continue
            img = bpy.data.images.load(os.path.join(FACES, f"{ch}_{e}.png"), check_existing=True)
            for m in bpy.data.materials:
                if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
                    m.node_tree.nodes["decal"].image = img
            turntable(cam, Vector((x, 0, hy - 0.08 * Hd)), 12, Hd * 3.6, Hd * 0.12, 60)
            render(os.path.join(WORK, f"pv_{ch}_expr_{e}.png"))
        for m in bpy.data.materials:
            if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal") and ch in imgs:
                m.node_tree.nodes["decal"].image = imgs[ch]
    if len(present) > 1:
        show(present)
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1000
        turntable(cam, Vector((0.0, 0, 0.19)), 10, 1.45, 0.16, 50); render(os.path.join(WORK, "pv_all.png"))
    print("PREVIEW done")


def _region_of():
    return {i + 1: k.split(".")[1] for i, k in enumerate(REGIONS)}


class _RegionLookup(dict):
    def __missing__(self, r):
        # regions are recorded in the blend as a custom property by mode_build
        tab = json.loads(sc().get("ex_regions", "[]"))
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


def pose_test(rig, ch):
    B = {b.name: (to_design(b.head_local), to_design(b.tail_local)) for b in rig.data.bones}
    for side, sg in (("L", 1), ("R", -1)):
        h, t = B["forearm" + side]; d = (t - h).normalized()
        bend(rig, "forearm" + side, d.cross(V(0, 0, 1)) * sg * -1, 65 if side == "L" else 35)
        h, t = B["hand" + side]; dh = (t - h).normalized()
        hz = dh.cross(V(0, 0, 1)).normalized()
        bend(rig, "fingers" + side, hz * (1 if side == "L" else -1), 75 if (ch, side) not in FIST else -40)
    bend(rig, "upperArmL", V(1, 0, 0), -45)
    bend(rig, "thighL", V(1, 0, 0), -30); bend(rig, "shinL", V(1, 0, 0), 50)
    bend(rig, "spine", V(1, 0, 0), 10); bend(rig, "head", V(0, 1, 0), 25); bend(rig, "jaw", V(1, 0, 0), 14)
    pb = rig.pose.bones["eyelids"]; pb.scale = (1, 6.0, 1)
    if ch == "moses":
        bend(rig, "mantleL", V(1, 0, 0), 25); bend(rig, "mantleBack", V(1, 0, 0), -20)
        bend(rig, "beard1", V(1, 0, 0), 12); bend(rig, "beard2", V(0, 0, 1), 20)
    if ch == "pharaoh":
        bend(rig, "nemes1L", V(1, 0, 0), 25); bend(rig, "nemesBack", V(1, 0, 0), -20)
    if ch == "miriam":
        bend(rig, "scarf2", V(1, 0, 0), -25); bend(rig, "braid1", V(0, 0, 1), 15); bend(rig, "braid2", V(1, 0, 0), 25)
    bpy.context.view_layer.update()


def mode_posetest():
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    setup_eevee((640, 960)); preview_lights()
    imgs = {ch: bpy.data.images.load(os.path.join(FACES, f"{ch}_{DEFAULT_EXPR[ch]}.png"), check_existing=True) for ch in CHARS}
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        set_face_materials(o, lambda p, r: r, lambda r: preview_material(ch, REGION_OF[r], imgs.get(ch)))
    cam = camera()
    present = [ch for ch in CHARS if bpy.data.objects.get(f"{ch}_rig")]
    for ch in present:
        pose_test(bpy.data.objects[f"{ch}_rig"], ch)
    for ch in present:
        for o in all_meshes():
            if o.name not in ("floor", "backdrop"):
                o.hide_render = o.name.split("_")[0] != ch or is_hidden_prop(o)
        rig = bpy.data.objects[f"{ch}_rig"]; Hh = SPEC[ch]["height"]
        for nm, yaw in (("a", 20), ("b", 70)):
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), yaw, Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pose_{ch}_{nm}.png"))
    print("POSETEST done")


def mode_uvcheck():
    """Models wearing $EX_WORK/uvproof.png (or $EX_UV_TEXTURE) through UV0: front ortho (must equal the sheet) and
    3/4 + back perspective (back of the cape / robe behind the braid take their own region's colour)."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get("EX_UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        o.data.materials.clear(); o.data.materials.append(m)
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    sc().view_settings.view_transform = 'Standard'
    cam = front_ortho_camera()
    for nm in ("backdrop",):
        bpy.data.objects[nm].hide_render = True
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = False
    bpy.data.objects["backdrop"].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc().render.resolution_x, sc().render.resolution_y = 1600, 900
    for nm, yaw in (("q34", 30), ("back", 180)):
        turntable(cam, Vector((0.0, 0, 0.19)), yaw, 1.45, 0.16, 50)
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
        want = sorted(CONTRACT_BONES + EXTRA_BONES[ch])
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
        h = max((o.matrix_world @ Vector(c)).z for o in meshes for c in o.bound_box)
        info["heightTop"] = round(h, 4)
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps(out))


if __name__ == "__main__":
    {"build": mode_build, "preview": mode_preview, "posetest": mode_posetest, "verify": mode_verify,
     "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), os.path.abspath(__file__), "all"],
                                                 check=True)}[MODE]()

