"""Ruth (story pack #3): characters ruth, naomi, boaz — meshes, rig, weights, UVs, face decals, previews, GLBs.

Contract: docs/ruth/CONTRACT.md §2-§3 (ids, heights, bone names, props), look: docs/ruth/DESIGN.md, notes:
docs/ruth/RIG.md. Started as a copy of pipeline/es_characters.py (Esther, pack #2) and keeps its method: procedural
quad cages (pipeline/story_mesh.py helpers, unchanged), heads mapped from the D&G base head by landmarks, box-modelled
hands, face decals on UV1 + an `eyelids` blink, UV0 = front page projection with occlusion + ID-render fixes.
New for Ruth:
  * `hood()`: one generic draped head-cloth surface (Ruth's scarf, Naomi's shawl, Boaz's head-cloth): it follows the
    hair/skull, hangs plumb from the widest part of the head, settles on the shoulders and falls down the back with
    folds that deepen toward a wavy hem; its back drape is skinned to a bone chain (scarf1/2, shawl1/2, headcloth);
  * Boaz's open outer robe: a second shell over the tunic with the front cut open and solidified, front panels
    skinned to cloakL / cloakR so they swing;
  * Naomi's stoop is a real rest pose: built straight (0.32), then spine / chest / neck bent forward, the head
    tipped back up and the arms hung plumb; that pose is baked into mesh and bones (`bake_rest_pose`), so the
    Animation role gets a stooped rest skeleton and the printed drawing shows the stoop;
  * props hidden by default (sheaf, stalks, baby) are left out of the printed ID render and take their UV0 from a
    point inside another printed region (PROP_ANCHORS; overridable by design.json characters.<id>.propUV);
  * faces: brows shaped per expression, a nose hint, cheek blush, lid creases, smile lines (Naomi, Boaz), mouths with
    a light rim, red interior and teeth so they read at phone distance (LESSONS L42); the baby's little face lives in
    a corner of every Naomi decal (UV1 of the baby's face points there).

Run (repo root):
  python3 pipeline/ru_characters.py all                                           # everything below, in order
  python3 pipeline/ru_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/ru_characters.py -- build        # models, rig, GLBs, blend, ID render
  python3 pipeline/ru_characters.py proof                                         # $RU_WORK/uvproof.png
  blender -b --factory-startup --python pipeline/ru_characters.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/ru_characters.py -- uvcheck      # models wearing uvproof.png
  blender -b --factory-startup --python pipeline/ru_characters.py -- posetest     # bend / blink / jaw / cloth bones
  blender -b --factory-startup --python pipeline/ru_characters.py -- verify       # re-import GLBs, check bones/budget
  python3 pipeline/ru_characters.py compose                                       # preview_*.png contact sheets
Intermediate renders go to $RU_WORK (default /tmp/ru_work). RU_ONLY=ruth (comma list) builds a subset.
"""
import sys, os, json, math, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/ruth/model")
FACES = os.path.join(ROOT, "docs/ruth/design/faces")
WORK = os.environ.get("RU_WORK", "/tmp/ru_work")
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/ruth/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("ruth", "naomi", "boaz")
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
EXTRA_BONES = {"ruth": ["scarf1", "scarf2", "sheaf", "stalks"],
               "naomi": ["shawl1", "shawl2", "staff", "baby"],
               "boaz": ["cloakL", "cloakR", "headcloth", "stalks"]}
PROPS = {"ruth": {"sheaf": False, "stalks": False}, "naomi": {"staff": True, "baby": False},
         "boaz": {"stalks": False}}                # prop bone -> shown by default (hidden ones are not printed)
CONTRACT_HEIGHT = {"ruth": 0.33, "naomi": 0.31, "boaz": 0.38}
DEFAULT_SHEET = {"naomi": (-0.34, 0.015), "ruth": (-0.02, 0.015), "boaz": (0.32, 0.015)}
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (as Esther)

# ---------------------------------------------------------------------------------------------- palette (DESIGN.md)
PALETTE = {
    "ruth": {"skin": "#F1C6A0", "hair": "#4A2E1F", "dress": "#9CC5A1", "scarf": "#F3E9D2", "belt": "#8A5A3B",
             "bracelet": "#3FB8AF", "sandals": "#A8743F", "sheaf": "#E2A93B", "stalks": "#E8B84A",
             "sheafTie": "#8A5A3B"},
    "naomi": {"skin": "#E9BC98", "hair": "#C9C4BE", "robe": "#B98A9E", "shawl": "#8FA3B8", "sash": "#D9A63A",
              "staff": "#9B6B43", "sandals": "#8A5A3B", "baby": "#F3E9D2", "babyFace": "#F1C6A0"},
    "boaz": {"skin": "#D9A27A", "beard": "#3A2418", "hair": "#3A2418", "robe": "#6E7F3A", "tunic": "#EFE3C8",
             "headcloth": "#EDE2C6", "cord": "#4B3A26", "sash": "#B5532E", "sandals": "#7A4E2E",
             "stalks": "#E8B84A"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发", "hair"), "dress": ("长裙", "dress"), "scarf": ("头巾", "head-scarf"),
    "belt": ("腰带", "belt"), "bracelet": ("手链", "bracelet"), "sandals": ("凉鞋", "sandals"),
    "sheaf": ("麦捆", "barley sheaf"), "stalks": ("麦穗", "barley stalks"), "sheafTie": ("麦捆绳", "sheaf tie"),
    "robe": ("长袍", "robe"), "shawl": ("披巾", "shawl"), "sash": ("腰带", "sash"), "staff": ("手杖", "staff"),
    "baby": ("襁褓", "baby's wrap"), "babyFace": ("宝宝的脸", "baby's face"), "beard": ("胡子", "beard"),
    "tunic": ("内袍", "tunic"), "headcloth": ("头巾", "head-cloth"), "cord": ("头箍", "head cord"),
}
# regions too small to colour on A4 (< ~2 mm across): constant UV deep inside a printed region ("char.region", or
# "char.FACE" = that character's face skin away from eyes / brows / nose / mouth)
ANCHORS = {
    "ruth": {"bracelet": "ruth.bracelet"},
    "naomi": {},
    "boaz": {"cord": "boaz.cord"},
}
# hidden-by-default props are not printed: their regions sample a printed region of similar colour. Defaults; the
# Set + sheet role can point them at the printed barley / a cradle drawing with design.json
# characters.<id>.propUV.<region> = [u, v] (page UV).
PROP_ANCHORS = {   # first target that exists wins; "set.<region>" = a region of the set's printed drawings
    "ruth": {"sheaf": ["set.sheaf", "set.barley", "naomi.sash"], "stalks": ["set.barley", "naomi.sash"],
             "sheafTie": ["set.sheafTie", "ruth.belt"]},
    "naomi": {"baby": ["ruth.scarf"], "babyFace": ["ruth.FACE"]},
    "boaz": {"stalks": ["set.barley", "naomi.sash"]},
}
# parts whose printed area is a sliver: every face of (part, region) takes one UV inside a larger region
PART_ANCHORS = {
    "ruth": {("handL", "skin"): "ruth.FACE", ("handR", "skin"): "ruth.FACE", ("legL", "skin"): "ruth.FACE",
             ("legR", "skin"): "ruth.FACE"},
    "naomi": {("handL", "skin"): "naomi.FACE", ("handR", "skin"): "naomi.FACE", ("legL", "skin"): "naomi.FACE",
              ("legR", "skin"): "naomi.FACE"},
    "boaz": {("handL", "skin"): "boaz.FACE", ("handR", "skin"): "boaz.FACE", ("legL", "skin"): "boaz.FACE",
             ("legR", "skin"): "boaz.FACE"},
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
    "ruth": scaled(ESTHER, 0.965, height=0.33, jaw=-0.14, cheek=0.12, chin_narrow=0.12, noseH=0.0017, nose_w=0.86,
                   lips=1.2, fr=dict(eye=0.470, brow=0.562, nose=0.262, mouth=0.160)),
    "naomi": scaled(ESTHER, 0.94, 0.97, height=0.32, depth=1.05, jaw=0.00, cheek=0.24, chin_narrow=0.02,
                    noseH=0.0019, nose_w=1.0, lips=0.75, brow=0.55, chinAmt=0.55, sockets=1.05, cheekbones=0.55,
                    fr=dict(eye=0.478, brow=0.566, nose=0.262, mouth=0.160)),
    "boaz": scaled(KING, 1.05, 1.09, height=0.38, jaw=0.08, cheek=0.06, noseH=0.0029, nose_w=1.10, brow=1.05,
                   fr=dict(eye=0.486, brow=0.578, nose=0.268, mouth=0.163)),
}
FIST = {("naomi", "R")}            # hands closed round a prop at rest (Naomi's staff)
FIST_BEND = {("naomi", "R"): 20.0}    # wrist cock of a fist (deg below horizontal); the staff then runs diagonally



def landmarks(ch):
    s = SPEC[ch]; H = s["top"] - s["chin"]
    L = dict(top=s["top"], chin=s["chin"], zc=s["zc"], hw=s["hw"])
    for k, f in FR.items():
        L[k] = s["chin"] + s.get("fr", {}).get(k, f) * H
    return L


EYE = {"ruth": (0.415, 0.305, 0.235), "naomi": (0.405, 0.270, 0.180), "boaz": (0.400, 0.250, 0.165)}


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


BABY_CORNER = (0.012, 0.012, 0.112, 0.112)     # where every naomi decal carries the baby's little face (UV1)
EXPRESSIONS = {"ruth": ["calm", "sad", "talk", "shy", "joy", "pray", "brave"],
               "naomi": ["tender", "sad", "tired", "talk", "surprised", "joy"],
               "boaz": ["smile", "talk", "curious", "kind", "sneaky", "laugh", "joy"]}
DEFAULT_EXPR = {"ruth": "calm", "naomi": "tender", "boaz": "smile"}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "ruth": {"idle": "calm", "walk": "calm", "talk": "talk", "sad": "sad", "shake_head": "brave",
             "hold_hands": "brave", "hug": "sad", "cheer_up": "joy", "glean": "calm", "stand_up": "calm",
             "bow_kneel": "pray", "shy": "shy", "carry_walk": "joy", "show_bundle": "joy", "joy": "joy",
             "ask_humble": "shy", "wave": "joy"},
    "naomi": {"idle": "tender", "walk_tired": "tired", "talk": "talk", "sad": "sad", "send_away": "sad",
              "listen_moved": "tender", "hug": "tender", "nod": "tender", "surprised": "surprised",
              "bless_up": "joy", "clap": "joy", "hold_baby": "tender", "joy": "joy"},
    "boaz": {"idle": "smile", "walk": "smile", "talk": "talk", "greet": "smile", "look_curious": "curious",
             "talk_kind": "kind", "hand_on_heart": "kind", "sneaky_drop": "sneaky", "chuckle": "laugh",
             "listen": "kind", "joy": "joy", "wave": "joy"},
}


def sheet_positions():
    """sheetX / sheetY per character: assets/ruth/design.json characters.<id> when present (Set + sheet role),
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

    def baby_face(img):
        """The swaddled baby's little face (Naomi's prop), drawn into BABY_CORNER of every naomi decal."""
        x0, y0, x1, y1 = BABY_CORNER; s = x1 - x0

        def Q(x, y): return (x0 + x * s, y0 + y * s)
        dr = ImageDraw.Draw(img)
        for sx in (-1, 1):                     # sleeping eyes
            stroke(dr, bez(Q(0.5 + sx * 0.30, 0.56), Q(0.5 + sx * 0.25, 0.48), Q(0.5 + sx * 0.12, 0.48),
                           Q(0.5 + sx * 0.07, 0.56), 16), 0.0045, 0.0045, col=(60, 40, 32, 255))
        stroke(dr, bez(Q(0.40, 0.30), Q(0.45, 0.24), Q(0.55, 0.24), Q(0.60, 0.30), 16), 0.004, 0.004,
               col=(150, 60, 60, 255))
        soft(img, lambda d: stroke(d, [Q(0.47, 0.40), Q(0.53, 0.40)], 0.004, 0.004, col=(170, 100, 80, 160)), 0.001)
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        for sx in (-1, 1):
            cxp, cyp = Q(0.5 + sx * 0.30, 0.36)
            r = 0.09 * s
            dl.ellipse((P(cxp - r, cyp + r * 0.7)[0], P(cxp - r, cyp + r * 0.7)[1], P(cxp + r, cyp - r * 0.7)[0],
                        P(cxp + r, cyp - r * 0.7)[1]), fill=(235, 120, 120, 150))
        img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(N * 0.006)))

    made = {}
    for ch in CHARS:
        F = face_layout(ch)
        eL, eR, half, by, my, ny_ = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"], F["nose"]
        hwN = F["hwN"]
        bcol = {"ruth": (70, 44, 30, 255), "naomi": (128, 118, 112, 255), "boaz": (42, 27, 18, 255)}[ch]
        iris = {"ruth": (110, 72, 40), "naomi": (96, 76, 56), "boaz": (88, 56, 32)}[ch]
        bw = {"ruth": 0.024, "naomi": 0.026, "boaz": 0.040}[ch]
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            E = dict(look=(0, 0), top=1.0, bot=1.0, tilt=0.15, lash=0, mode="open", lid=0.10, inner_up=0.0,
                     pupil=0.55, wet=False)
            Bp = dict(raise_=0.0, inner=0.0, arch=0.35, thick=1.0, outer=0.0)
            Bl, Br = {}, {}
            M = dict(kind="flat", wd=0.095, jaw=0.0, side=0.0)
            lipcol = None; rim = None; bl = 0; crow = 0; folds = 0.0; bags = False; crs = True
            if ch == "ruth":
                E.update(lash=3, tilt=0.16, lid=0.05); lipcol = (214, 110, 118, 160); M["wd"] = 0.088
                Bp.update(raise_=0.080, arch=0.32, thick=0.92); bl = 95
                if ex == "calm":
                    M.update(kind="soft"); E.update(look=(0.05, 0.05))
                elif ex == "sad":
                    E.update(top=0.92, look=(0, -0.45), tilt=-0.05, wet=True)
                    Bp.update(inner=0.042, raise_=0.088, arch=0.10, outer=-0.020); M.update(kind="frown", wd=0.068)
                    bl = 70
                elif ex == "talk":
                    M.update(kind="open", wd=0.076, jaw=0.06); Bp.update(raise_=0.086, arch=0.38)
                elif ex == "shy":
                    E.update(top=0.80, look=(0.55, -0.70), tilt=0.10); Bp.update(inner=0.020, raise_=0.088, arch=0.30)
                    M.update(kind="small", wd=0.080); bl = 175
                elif ex == "joy":
                    E.update(mode="happy"); Bp.update(raise_=0.098, arch=0.46); M.update(kind="grin", wd=0.094, jaw=0.08)
                    bl = 160
                elif ex == "pray":
                    E.update(mode="closed"); Bp.update(inner=0.016, raise_=0.082, arch=0.26); M.update(kind="soft", wd=0.072)
                    crs = False
                elif ex == "brave":
                    E.update(top=0.94, tilt=0.10, look=(0, 0.05)); Bp.update(inner=-0.016, raise_=0.070, arch=0.20, thick=1.05)
                    M.update(kind="small", wd=0.090); bl = 80
            elif ch == "naomi":
                E.update(lash=1, tilt=0.02, lid=0.16, top=0.86, bot=0.92, pupil=0.52); lipcol = (196, 112, 116, 140)
                M["wd"] = 0.080; Bp.update(raise_=0.072, arch=0.26, thick=0.95, outer=-0.010); bl = 70; crow = 2
                folds = 0.055; bags = True
                if ex == "tender":
                    E.update(top=0.78, bot=0.80, look=(0.1, -0.1)); Bp.update(inner=0.012, raise_=0.078)
                    M.update(kind="smile", wd=0.074); bl = 90; crow = 3
                elif ex == "sad":
                    E.update(top=0.74, look=(0, -0.55), tilt=-0.10, wet=True)
                    Bp.update(inner=0.040, raise_=0.084, arch=0.08, outer=-0.028); M.update(kind="frown", wd=0.066)
                elif ex == "tired":
                    E.update(top=0.58, bot=0.85, look=(0, -0.3), tilt=-0.12, lid=0.30)
                    Bp.update(inner=0.018, raise_=0.066, arch=0.10, outer=-0.030); M.update(kind="flat", wd=0.062)
                elif ex == "talk":
                    M.update(kind="open", wd=0.074, jaw=0.05); E.update(top=0.86)
                elif ex == "surprised":
                    E.update(top=1.22, bot=1.1, pupil=0.40, lid=0.08, tilt=0.0); Bp.update(raise_=0.110, arch=0.55, outer=0.0)
                    M.update(kind="o", wd=0.064, jaw=0.18); crow = 0
                elif ex == "joy":
                    E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.45, outer=0.0); M.update(kind="grin", wd=0.088, jaw=0.06)
                    bl = 120; crow = 3
            else:   # boaz
                E.update(lid=0.22, top=0.86, bot=0.86, tilt=0.06, pupil=0.54); M["wd"] = 0.090
                lipcol = (176, 98, 84, 220); rim = (214, 150, 132, 235)
                Bp.update(raise_=0.064, arch=0.28, thick=1.0); bl = 45; crow = 2
                if ex == "smile":
                    E.update(top=0.80, bot=0.70); Bp.update(raise_=0.068, arch=0.36); M.update(kind="smile", wd=0.088)
                    crow = 3
                elif ex == "talk":
                    M.update(kind="open", wd=0.082, jaw=0.08)
                elif ex == "curious":
                    E.update(top=0.96, look=(-0.55, 0.15)); Bl = dict(raise_=0.096, arch=0.55); Br = dict(raise_=0.056, inner=-0.012, arch=0.18)
                    M.update(kind="small", wd=0.066)
                elif ex == "kind":
                    E.update(top=0.78, bot=0.76, look=(0.1, -0.05)); Bp.update(inner=0.018, raise_=0.070, arch=0.24)
                    M.update(kind="soft", wd=0.084); crow = 3
                elif ex == "sneaky":
                    E.update(top=0.66, bot=0.78, look=(0.85, 0.0)); Bl = dict(raise_=0.100, arch=0.70); Br = dict(raise_=0.054, inner=-0.020, arch=0.18)
                    M.update(kind="smirk", wd=0.094, side=1); crow = 2
                elif ex == "laugh":
                    E.update(mode="happy"); Bp.update(raise_=0.084, arch=0.50); M.update(kind="grin", wd=0.100, jaw=0.25)
                    bl = 85; crow = 3
                elif ex == "joy":
                    E.update(top=1.04, bot=0.8, pupil=0.50); Bp.update(raise_=0.090, arch=0.52); M.update(kind="grin", wd=0.098, jaw=0.08)
                    bl = 70; crow = 3
            # ---- draw
            if bl:
                blush(img, 0.31 if ch != "boaz" else 0.32, ny_ - 0.035, 0.088, 0.046, bl)
            nose_hint(img, ny_ + 0.006, 0.030 if ch != "boaz" else 0.036,
                      strength={"ruth": 0.85, "naomi": 1.0, "boaz": 1.1}[ch])
            if folds:
                wide = M["kind"] in ("smile", "grin")
                cheek_lines(img, ny_ + 0.004, my + (0.000 if wide else 0.012), 0.092, M["wd"] * 1.25 + (0.040 if wide else 0.030),
                            col=(140, 82, 64, 95 if wide else 70))
            for side, c in ((1, eL), (-1, eR)):
                eye(img, c, half, side=side, iris=iris, line=0.019 if ch == "ruth" else 0.020, **E)
                if crs and E["mode"] == "open":
                    crease(img, c, half, side, lift=1.55 if ch != "naomi" else 1.45,
                           col=(140, 90, 72, 110 if ch != "naomi" else 150))
                if bags and E["mode"] == "open":
                    under_eye(img, c, half, side, drop=1.25 if E["bot"] < 0.9 else 1.35)
                if crow:
                    crows(img, c, half, side, n=crow, ln=1.0 if E["mode"] == "open" else 1.2,
                          col=(130, 80, 62, 110 if ch == "naomi" else 130))
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
            if ch == "naomi":
                baby_face(img)
            out = img.resize((PX, PX), Image.LANCZOS)
            path = os.path.join(FACES, f"{ch}_{ex}.png")
            out.save(path); made[f"{ch}_{ex}"] = os.path.relpath(path, ROOT)
    # overview sheet: every expression over a skin swatch, plus a 64 px "phone distance" row (LESSONS L42)
    cells = [(ch, ex) for ch in CHARS for ex in EXPRESSIONS[ch]]
    cols = 7; cw = 256
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
    """Contact sheets model/preview_<char>.png and preview_all.png from the $RU_WORK renders."""
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
        ex = grid(exprs, EXPRESSIONS[ch], 6, (320, 320), "face decals on the model (UV1)")
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
                 "scarf2 / shawl2 / cloakL + headcloth")
        g.save(os.path.join(MODEL, "preview_pose.png"))
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
ONLY = [c for c in os.environ.get("RU_ONLY", "").split(",") if c] or list(CHARS)
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


# =============================================================================================== Ruth
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


def build_ruth(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]
    rim = esther_like_rim(C, 0.37)
    C.hair_rim = rim
    skeleton(C)
    build_head(C, hair_cull(C, rim))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0030, 0.0040, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        t = lerp(t, 0.0034, smoothstep(0.10, 0.20, uu) * smoothstep(L["eye"], L["mouth"], y))
        if uu < 0.12:
            t = lerp(t, 0.0022, smoothstep(L["brow"] + 0.43 * H, L["brow"] + 0.34 * H, y))
        return t * S

    def plumb(uu):
        return smoothstep(0.12, 0.18, uu) * smoothstep(0.44, 0.30, uu)
    hair_shell(C, rim, thick, "hair", "hair", plumb=plumb, parting=True, waves=0.0006 * S, NU=32, NV=7)
    # ---- dress: sage green, gathered at the waist, three-quarter sleeves
    R = scale_rows(ESTHER_ROBE, k, kx)
    R = [(y, hw * (1.0 + 0.04 * smoothstep(0.20, 0.10, y)), zf, zb) for y, hw, zf, zb in R]
    sleeve = [(0.004, 0.0101), (0.012, 0.0099), (0.026, 0.0091), (0.040, 0.0087), (0.052, 0.0087), (0.062, 0.0092),
              (0.071, 0.0101), (0.078, 0.0108), (0.081, 0.0110)]
    build_robe(C, R, sleeve, None, nf=16, fold_amp=0.0019, sleeve_fold=0.0010, bell_sag=0.0010 * S, reg="dress",
               name="dress")
    for side in "LR":
        build_forearm_hand(C, side, 0.022 * S)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S))
    # ---- woven brown belt with a hanging tie on her left
    waist_band(C, "belt", "belt", wy - 0.0048 * S, wy + 0.0048 * S, 0.0009 * S, bulge=0.0010 * S)
    belt_tie(C, "beltTie", "belt", 0.0105 * S, wy, [(-0.0010, wy - 0.040 * S), (0.0020, wy - 0.052 * S)], 0.0017)
    # ---- bead bracelet on the left wrist
    A = C.arm["L"]; hd = s["handDims"]
    cg = Cage(); wbr = C.w(["forearmL", "handL"], blend=0.006 * S)
    c0 = A["W"] - A["d"] * (0.0040 * S)
    X0 = perp(V(0, 0, 1), A["d"]); Y0 = A["d"].cross(X0)
    rr = hd["wristW"] * 0.62
    for i in range(11):
        an = 2 * math.pi * i / 11
        p = c0 + X0 * (math.cos(an) * rr) + Y0 * (math.sin(an) * rr * 0.92)
        blob(cg, p, 0.0011 * S, 0.0011 * S, 0.0011 * S, wbr, "bracelet", 0, NU=6, NV=4)
    C.add("bracelet", cg, subdiv=0)
    # ---- head-scarf: cream, loosely over the head, over the shoulders, tail down the back (scarf1 / scarf2)
    zbh = C.head.at(0.5, L["chin"] + 0.15 * H).z
    zb_bl = table(C.robe_rows, s["chestY"])[2]
    C.B["scarf1"] = (V(0, L["chin"] + 0.10 * H, zbh - 0.003 * S), V(0, s["chestY"], zb_bl - 0.006 * S), "head")
    C.B["scarf2"] = (V(0, s["chestY"], zb_bl - 0.006 * S), V(0, wy - 0.018 * S, table(C.robe_rows, wy)[2] - 0.005 * S), "scarf1")

    def srim(u):
        uu = mirror_u(u)
        return table([(0.000, L["top"] - 0.020 * H), (0.050, L["top"] - 0.040 * H), (0.095, L["brow"] + 0.26 * H),
                      (0.135, L["eye"] + 0.02 * H), (0.165, L["nose"] - 0.06 * H), (0.185, L["mouth"] - 0.12 * H),
                      (0.195, L["chin"] - 0.20 * H), (0.205, shY - 0.004 * S), (0.215, s["chestY"] - 0.012 * S),
                      (0.235, s["chestY"] - 0.016 * S), (0.26, shY - 0.010 * S), (0.29, shY - 0.026 * S),
                      (0.34, s["chestY"] - 0.010 * S), (0.40, wy + 0.004 * S), (0.46, wy - 0.012 * S),
                      (0.50, wy - 0.020 * S)], uu)[0]

    def sthick(u, y):
        uu = mirror_u(u)
        return (0.0020 + 0.0012 * smoothstep(L["brow"], L["top"], y) + 0.0010 * smoothstep(0.15, 0.30, uu)) * S
    hood(C, "scarf", "scarf", srim, sthick, hood_weights(C, ["scarf1", "scarf2", ("chest", None)]), NU=50, NV=20,
         flare=0.06, body_off=0.0022, front_pull=0.40, folds=(13, 0.0018), hem_wave=0.0012, solid=0.0010)
    # ---- props: sheaf (chest, both arms) and a few stalks (right hand); hidden by default
    zf = table(C.robe_rows, s["chestY"] - 0.010 * S)[1]
    sc_ = V(0.002 * S, s["chestY"] - 0.016 * S, zf + 0.022 * S)
    ax = V(-0.45, 1.0, 0.18).normalized()
    cg = Cage()
    ln = 0.105 * S; rb = 0.0135 * S
    prof = [(-0.50, 0.92), (-0.40, 1.0), (-0.20, 0.86), (-0.05, 0.70), (0.05, 0.70), (0.18, 0.86), (0.30, 1.0)]
    Xa = perp(V(0, 0, 1), ax); Ya = ax.cross(Xa)
    rings = []
    for t, r in prof:
        c = sc_ + ax * (t * ln)
        rings.append(cg.ring([c + Xa * (math.cos(2 * math.pi * j / 14) * rb * r) + Ya * (math.sin(2 * math.pi * j / 14) * rb * r * 0.9)
                              for j in range(14)], None))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "sheaf", 0)
    cg.fan(list(reversed(rings[0])), sc_ + ax * (-0.52 * ln), None, "sheaf", 0)
    cg.fan(rings[-1], sc_ + ax * (0.34 * ln), None, "sheaf", 0)
    rnd = random.Random(7)
    for i in range(22):                                     # ears fanning out of the top, drooping outward
        an = 2 * math.pi * i / 22 + rnd.uniform(-0.15, 0.15)
        rad = rb * (0.35 + 0.65 * rnd.random())
        base = sc_ + ax * (0.26 * ln) + Xa * (math.cos(an) * rad) + Ya * (math.sin(an) * rad * 0.9)
        out_d = (Xa * math.cos(an) + Ya * math.sin(an))
        d = (ax * 1.0 + out_d * (0.45 + 0.35 * rnd.random())).normalized()
        barley_ear(cg, base, d, 0.019 * S * rnd.uniform(0.85, 1.1), 0.0019 * S, None, "sheaf", 0)
    for i in range(10):                                      # a few loose stalk ends at the bottom
        an = 2 * math.pi * i / 10 + 0.3
        base = sc_ + ax * (-0.46 * ln) + (Xa * math.cos(an) + Ya * math.sin(an)) * rb * 0.7
        d = (-ax + (Xa * math.cos(an) + Ya * math.sin(an)) * 0.25).normalized()
        tube(cg, [base, base + d * 0.010 * S], [0.0011 * S, 0.0010 * S], 4, None, "sheaf", 0, cap0=False, cap1=True)
    tc = sc_ + ax * (0.0 * ln)                                # tie
    tie = [tc + Xa * (math.cos(2 * math.pi * j / 20) * rb * 0.74) + Ya * (math.sin(2 * math.pi * j / 20) * rb * 0.68) for j in range(20)]
    band_loop(cg, tie, [(p - tc).normalized() for p in tie], [ax] * 20, 0.0028 * S, 0.0010 * S, None, "sheafTie", 1)
    C.add("sheaf", cg, subdiv=0, rigid="sheaf")
    C.B["sheaf"] = (sc_ - ax * (0.25 * ln), sc_ + ax * (0.25 * ln), "chest")
    g = grip_point(C, "R", 0.0024)
    A = C.arm["R"]; up = A["Yh"] if A["Yh"].y > 0 else -A["Yh"]
    cg = Cage()
    stalk_bunch(cg, g, (up + V(0, 0.3, 0)).normalized(), 6, 0.070 * S, 0.16, 0.00085 * S, 0.016 * S, 0.0016 * S,
                None, "stalks", 0, seed=3, below=0.30)
    C.add("stalks", cg, subdiv=0, rigid="stalks")
    C.B["stalks"] = (g.copy(), g + up * 0.02 * S, "handR")


# =============================================================================================== Naomi
def build_naomi(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]
    rim = esther_like_rim(C, 0.36)
    C.hair_rim = rim
    skeleton(C)
    build_head(C, hair_cull(C, rim))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0028, 0.0036, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        if uu < 0.12:
            t = lerp(t, 0.0020, smoothstep(L["brow"] + 0.42 * H, L["brow"] + 0.33 * H, y))
        return t * S

    def plumb(uu):
        return smoothstep(0.14, 0.20, uu) * smoothstep(0.44, 0.30, uu) * 0.6
    # grey hair parted in the middle and swept back in soft waves (shows at the temples under the shawl)
    hair_shell(C, rim, thick, "hair", "hair", plumb=plumb, parting=True, waves=0.0008 * S, NU=36, NV=8, grooves=44,
               groove_amp=0.00034)
    # ---- robe: dusty rose, fuller waist, long sleeves with a little bell
    R = scale_rows(ESTHER_ROBE, k, kx)
    R = [(y, hw + 0.0040 * math.exp(-((y - 0.205 * k) / 0.03) ** 2) + 0.0010, zf + 0.0020 * math.exp(-((y - 0.20 * k) / 0.03) ** 2)
          - 0.0015 * math.exp(-((y - 0.232 * k) / 0.012) ** 2), zb - 0.0006) for y, hw, zf, zb in R]
    sleeve = [(0.004, 0.0103), (0.012, 0.0101), (0.026, 0.0094), (0.042, 0.0090), (0.056, 0.0092), (0.068, 0.0100),
              (0.080, 0.0112), (0.089, 0.0122), (0.094, 0.0126)]
    build_robe(C, R, sleeve, None, nf=14, fold_amp=0.0021, sleeve_fold=0.0011, bell_sag=0.0012 * S, reg="robe",
               name="robe")
    for side in "LR":
        build_forearm_hand(C, side, 0.034 * S)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S))
    # ---- ochre sash, knotted at her left front, two tails
    waist_band(C, "sash", "sash", wy - 0.0068 * S, wy + 0.0060 * S, 0.0010 * S, bulge=0.0010 * S)
    belt_tie(C, "sashTie", "sash", 0.0120 * S, wy - 0.001 * S, [(-0.0012, wy - 0.050 * S), (0.0024, wy - 0.064 * S)], 0.0026)
    # ---- shawl: grey-blue, covers the head, wraps the shoulders and upper arms, long back drape (shawl1 / shawl2)
    zbh = C.head.at(0.5, L["chin"] + 0.15 * H).z
    zb_bl = table(C.robe_rows, s["chestY"])[2]
    C.B["shawl1"] = (V(0, L["chin"] + 0.10 * H, zbh - 0.004 * S), V(0, s["chestY"] - 0.004 * S, zb_bl - 0.008 * S), "head")
    C.B["shawl2"] = (V(0, s["chestY"] - 0.004 * S, zb_bl - 0.008 * S), V(0, s["hipY"] - 0.010 * S, table(C.robe_rows, s["hipY"])[2] - 0.006 * S), "shawl1")

    def srim(u):
        uu = mirror_u(u)
        return table([(0.000, L["top"] - 0.085 * H), (0.050, L["top"] - 0.110 * H), (0.090, L["brow"] + 0.20 * H),
                      (0.125, L["eye"] + 0.06 * H), (0.160, L["nose"] - 0.03 * H), (0.190, L["mouth"] - 0.08 * H),
                      (0.205, L["chin"] - 0.10 * H), (0.214, s["chestY"] - 0.010 * S), (0.225, wy + 0.010 * S),
                      (0.255, shY - 0.040 * S), (0.29, shY - 0.036 * S), (0.33, s["chestY"] - 0.032 * S), (0.38, s["hipY"] + 0.006 * S),
                      (0.45, s["hipY"] - 0.012 * S), (0.50, s["hipY"] - 0.020 * S)], uu)[0]

    def sthick(u, y):
        uu = mirror_u(u)
        return (0.0022 + 0.0012 * smoothstep(L["brow"], L["top"], y) + 0.0010 * smoothstep(0.15, 0.30, uu)) * S
    hood(C, "shawl", "shawl", srim, sthick, hood_weights(C, ["shawl1", "shawl2", ("chest", None)], arm_reach=0.016),
         NU=56, NV=24, flare=0.08, body_off=0.0026, front_pull=0.38, folds=(12, 0.0022), hem_wave=0.0014,
         solid=0.0011)
    # ---- walking staff in the right fist, planted on the ground (rigid, staff bone)
    A = C.arm["R"]; g = grip_point(C, "R", 0.0030)
    cg = Cage()
    top = g + V(0, 0.050 * S, 0)
    bot = V(g.x - 0.002 * S, 0.0030, g.z + 0.001 * S)
    path = []
    for i in range(13):
        t = i / 12
        p = bot.lerp(top, t)
        p += V(0.0012 * S * math.sin(t * 7.0), 0, 0.0008 * S * math.sin(t * 5.0 + 1.0))
        path.append(p)
    rads = [0.0027 * S + 0.0008 * S * (i / 12) for i in range(13)]
    tube(cg, path, rads, 8, None, "staff", 0, cap0=True, cap1=False, cap_len=0.4)
    blob(cg, top + V(0.0004 * S, 0.0030 * S, 0), 0.0046 * S, 0.0050 * S, 0.0044 * S, None, "staff", 0, NU=10, NV=6)
    for t in (0.22, 0.52, 0.78):                              # knots in the wood
        p = cr_open(path, t)
        blob(cg, p + V(0.0026 * S, 0, 0.0008 * S), 0.0011 * S, 0.0016 * S, 0.0011 * S, None, "staff", 0, NU=6, NV=4)
    C.add("staff", cg, subdiv=0, rigid="staff")
    C.B["staff"] = (g.copy(), top.copy(), "handR")
    # ---- baby Obed, swaddled, cradled at the chest (rigid, baby bone; hidden by default)
    zf = table(C.robe_rows, s["chestY"] - 0.014 * S)[1]
    bc = V(0.000, s["chestY"] - 0.020 * S, zf + 0.026 * S)
    cg = Cage()
    bl = 0.030 * S
    Mx = Matrix(((0, 1, 0), (1, 0, 0), (0, 0, 1))).transposed()        # long axis along x
    blob(cg, bc + V(-0.004 * S, 0, 0), 0.0135 * S, bl, 0.0130 * S, None, "baby", 0, NU=14, NV=10, ax=Mx)
    hc = bc + V(bl * 0.62, 0.006 * S, 0.004 * S); hr = 0.0108 * S
    head_cg_start = len(cg.f)
    blob(cg, hc, hr, hr * 1.02, hr, None, "baby", 0, NU=14, NV=10)
    for fi in range(head_cg_start, len(cg.f)):
        cen = sum((cg.v[i] for i in cg.f[fi]), V()) / len(cg.f[fi])
        n = (cen - hc).normalized()
        if n.z > 0.45 and n.x < 0.70 and abs(n.y) < 0.75:
            cg.reg[fi] = "babyFace"; cg.pc[fi] = 1
    # wrap fold around the head and a band across the body
    hood_ring = [hc + V(0, math.sin(2 * math.pi * j / 18) * hr * 1.08, math.cos(2 * math.pi * j / 18) * hr * 1.08)
                 + V(-0.002 * S, 0, 0) for j in range(18)]
    hood_ring = [hc + (p - hc) for p in hood_ring]
    band_loop(cg, hood_ring, [(p - hc).normalized() for p in hood_ring], [V(1, 0, 0)] * 18, 0.0020 * S, 0.0012 * S,
              None, "baby", 0)
    C.babyface = dict(centre=hc.copy(), r=hr)
    C.add("baby", cg, subdiv=0, rigid="baby", babyface=True)
    C.B["baby"] = (bc - V(bl * 0.6, 0, 0), bc + V(bl * 0.6, 0, 0), "chest")


# =============================================================================================== Boaz
def build_boaz(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]
    cb = L["brow"] + 0.26 * H

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb + 0.003 * S), (0.13, cb + 0.003 * S), (0.17, cb - 0.004 * S), (0.19, L["eye"] + 0.02 * H),
                      (0.215, L["nose"]), (0.25, L["mouth"]), (0.30, L["mouth"] - 0.02 * H), (0.36, L["chin"] - 0.06 * H),
                      (0.50, L["chin"] - 0.14 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return True
        return uu > 0.17 and p.y > rim(u) + 0.0045 * S
    skeleton(C)
    build_head(C, cull)

    def thick(u, y):
        return (0.0030 + 0.0008 * smoothstep(L["eye"], L["chin"], y)) * S

    def curls(u, y):
        rh = 0.0056 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0009 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh)) \
            * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 30 + ph)))
    hair_shell(C, rim, thick, "hair", "hair", plumb=lambda uu: smoothstep(0.26, 0.34, uu), tuck_front=0.17, grooves=0,
               curls=curls, NU=20, NV=4)
    # full short beard with curl rows + moustache
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.068 * H), (0.07, L["mouth"] + 0.005 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.01 * H), (0.20, L["eye"] - 0.15 * H), (0.245, L["eye"] - 0.04 * H)]
    bot = [(0.00, L["chin"] - 0.11 * H), (0.06, L["chin"] - 0.10 * H), (0.12, L["chin"] - 0.06 * H),
           (0.17, L["chin"] + 0.02 * H), (0.21, L["mouth"] - 0.04 * H), (0.245, L["nose"] - 0.04 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0050, 0.0030, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0050 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0010 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 34 + ph))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.11 * H)
    moustache(C, "moustache", L["mouth"] + 0.085 * H, 0.60 * s["hw"], 0.07 * H, 0.04 * H, 0.0021 * S, off=0.0016)
    # ---- cream tunic (inner), sleeves to the wrist
    RT = scale_rows(KING_ROBE, k, kx)
    RT = [(y, hw * (1 - 0.10 * smoothstep(0.17, 0.02, y)), zf, zb) for y, hw, zf, zb in RT]
    sleeve_t = [(0.004, 0.0128), (0.014, 0.0124), (0.030, 0.0112), (0.048, 0.0104), (0.062, 0.0102), (0.074, 0.0104),
                (0.082, 0.0108), (0.088, 0.0110)]
    build_robe(C, RT, sleeve_t, None, nf=12, fold_amp=0.0012, sleeve_fold=0.0007, reg="tunic", name="tunic",
               N=28, step=0.0090)
    C.tunic_rows = C.robe_rows
    for side in "LR":
        build_forearm_hand(C, side, 0.044)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.030)
    # brown-rust sash on the tunic (visible between the robe panels)
    waist_band(C, "sash", "sash", wy - 0.0062 * S, wy + 0.0058 * S, 0.0009 * S, bulge=0.0010 * S)
    belt_tie(C, "sashTie", "sash", -0.0080 * S, wy, [(-0.0016, wy - 0.034 * S), (0.0016, wy - 0.042 * S)], 0.0022)
    # ---- olive outer robe (abaya): bigger shell, open front, wide shorter sleeves
    RO = [(y, hw + 0.0026 * S + 0.0016 * S * smoothstep(0.20, 0.02, y), zf + 0.0030 * S + 0.0010 * S * smoothstep(0.20, 0.02, y),
           zb - 0.0030 * S - 0.0010 * S * smoothstep(0.20, 0.02, y)) for y, hw, zf, zb in RT]
    hemO = 0.018 * k
    RO = [r for r in RO if r[0] > hemO + 0.006] + [(hemO,) + tuple(table(RO, hemO))]
    RO[0] = (RO[0][0] - 0.0010 * S,) + RO[0][1:]
    sleeve_o = [(0.004, 0.0148), (0.014, 0.0145), (0.030, 0.0136), (0.046, 0.0132), (0.058, 0.0138), (0.068, 0.0150),
                (0.076, 0.0162), (0.080, 0.0166)]
    cg = build_robe(C, RO, sleeve_o, None, nf=10, fold_amp=0.0018, sleeve_fold=0.0011, bell_sag=0.0014 * S, reg="robe",
                    name="robe", solidify=0.0010, keep=True, N=32, step=0.0078)
    chestY = s["chestY"]

    def gap(y):         # half-angle of the front opening
        return math.radians(lerp(13.0, 30.0, smoothstep(nb, 0.03, y) ** 0.8))

    def opening_arm(c):
        for side in "LR":
            A_ = C.arm[side]; sv = (c - A_["S0"]).dot(A_["d"])
            if sv > 0.004 * S and (c - (A_["S0"] + A_["d"] * sv)).length < 0.03 * S:
                return True
        return False

    def opening(c):
        for side in "LR":
            A_ = C.arm[side]; sv = (c - A_["S0"]).dot(A_["d"])
            if sv > 0.004 * S and (c - (A_["S0"] + A_["d"] * sv)).length < 0.03 * S:
                return False
        return c.z > 0 and abs(math.atan2(c.x, c.z)) < gap(c.y) * 0.85
    # open the front cleanly: in superellipse angle space, push the centre column to +gap(y) and its left neighbour
    # to -gap(y) (fading out by 70 deg so the sleeve ports stay put), then drop the one face column between them
    N_ = 32; dlt = 2 * math.pi / N_; e_ = 2.5; fade = math.radians(70)
    for i, p in enumerate(cg.v):
        if opening_arm(p) or p.z < -0.002:
            continue
        hw_, zf_, zb_ = table(C.robe_rows, p.y); zc_ = (zf_ + zb_) / 2; rd_ = (zf_ - zb_) / 2
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
    drop_faces(cg, opening)
    # panel weights: the front of the robe below the chest follows cloakL / cloakR
    zfc = table(RO, chestY)[1]
    for side, sd in (("L", 1), ("R", -1)):
        x0 = sd * table(RO, chestY)[0] * 0.40
        C.B["cloak" + side] = (V(x0, chestY - 0.004 * S, zfc + 0.002 * S), V(sd * table(RO, 0.05)[0] * 0.45, 0.040 * k,
                                                                           table(RO, 0.05)[1] + 0.004 * S), "chest")
    for i, p in enumerate(cg.v):
        a = math.atan2(p.x, p.z + 0.001)
        tw = smoothstep(chestY + 0.004 * S, chestY - 0.040 * S, p.y) * smoothstep(math.radians(80), math.radians(30), abs(a))
        if tw <= 0 or p.z < 0:
            continue
        tw *= 0.85
        side = "L" if p.x > 0 else "R"
        cg.w[i] = mixw((cg.w[i], 1 - tw), ({"cloak" + side: 1.0}, tw))
    # ---- head-cloth (keffiyeh): cream, over the head to the shoulders, back drape (headcloth bone); dark cord ring
    zbh = C.head.at(0.5, L["chin"] + 0.15 * H).z
    zb_bl = table(C.robe_rows, chestY)[2]
    C.B["headcloth"] = (V(0, L["chin"] + 0.08 * H, zbh - 0.004 * S), V(0, chestY - 0.010 * S, zb_bl - 0.006 * S), "head")

    def hrim(u):
        uu = mirror_u(u)
        return table([(0.000, L["brow"] + 0.16 * H), (0.060, L["brow"] + 0.15 * H), (0.110, L["brow"] + 0.07 * H),
                      (0.150, L["eye"] - 0.02 * H), (0.180, L["nose"] - 0.06 * H), (0.205, L["mouth"] - 0.06 * H),
                      (0.218, L["chin"] - 0.10 * H), (0.228, chestY + 0.004 * S), (0.25, shY - 0.002 * S),
                      (0.29, shY + 0.002 * S), (0.34, shY - 0.012 * S), (0.40, chestY - 0.012 * S),
                      (0.50, chestY - 0.024 * S)], uu)[0]

    def hthick(u, y):
        uu = mirror_u(u)
        return (0.0018 + 0.0012 * smoothstep(L["brow"], L["top"], y) + 0.0012 * smoothstep(0.12, 0.30, uu)) * S
    wh = hood_weights(C, ["headcloth", ("chest", None)])
    hood(C, "headcloth", "headcloth", hrim, hthick, wh, NU=40, NV=16, flare=0.06, body_off=0.0024, front_pull=0.22,
         folds=(10, 0.0018), hem_wave=0.0010, solid=0.0010)
    # cord (agal): two thick rings round the crown, on the cloth
    cg = Cage(); wfn = C.w(["head"])
    for dy, rr in ((0.0, 0.0018), (0.0040 * S, 0.0017)):
        NB = 32; pts = []
        for j in range(NB):
            u = j / NB
            y = lerp(L["brow"] + 0.30 * H, L["top"] - 0.24 * H, (1 - math.cos(2 * math.pi * u)) / 2) + dy
            p = C.hood_pt(u, y); n = C.head.normal(u, min(y, L["top"] - 0.001))
            pts.append(p + n * (rr * S + 0.0003 * S))
        tube(cg, pts + [pts[0], pts[1]], [rr * S] * (NB + 2), 6, wfn, "cord", 0, cap0=False, cap1=False)
    C.add("cord", cg, subdiv=0)
    # ---- a big handful of stalks in the right hand (rigid, stalks bone; hidden by default)
    g = grip_point(C, "R", 0.0024)
    A = C.arm["R"]; up = A["Yh"] if A["Yh"].y > 0 else -A["Yh"]
    cg = Cage()
    stalk_bunch(cg, g, (up + V(0, 0.3, 0)).normalized(), 11, 0.080 * k, 0.22, 0.0010 * S, 0.017 * k, 0.0019 * S,
                None, "stalks", 0, seed=11, below=0.28)
    C.add("stalks", cg, subdiv=0, rigid="stalks")
    C.B["stalks"] = (g.copy(), g + up * 0.02 * S, "handR")
# =============================================================================================== Blender assembly
BUILDERS = {"ruth": build_ruth, "naomi": build_naomi, "boaz": build_boaz}
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
    if pt.get("babyface"):       # the baby's face samples BABY_CORNER of the naomi decal (front projection)
        bf = C.babyface; x0, y0, x1, y1 = BABY_CORNER
        rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
        for poly, r in zip(me.polygons, rid):
            if REGIONS[r - 1].split(".")[1] != "babyFace":
                continue
            for li in poly.loop_indices:
                q = vco[me.loops[li].vertex_index]
                fu = (q.x - bf["centre"].x) / (2.0 * bf["r"]) + 0.5; fv = (q.y - bf["centre"].y) / (2.0 * bf["r"]) + 0.5
                uv1.data[li].uv = (x0 + (x1 - x0) * fu, y0 + (y1 - y0) * fv)
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


REST_BAKE = {   # Naomi: built straight (0.32), then stooped; arms hang plumb again, head tips back up
    "naomi": [("chest", V(1, 0, 0), 15.0), ("neck", V(1, 0, 0), 14.0),
              ("head", V(1, 0, 0), -17.0), ("upperArmL", V(1, 0, 0), -15.0), ("upperArmR", V(1, 0, 0), -15.0)],
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
    if ch in REST_BAKE and not os.environ.get("RU_NOBAKE"):
        baked = bake_rest_pose(C, rig, bodyo, REST_BAKE[ch])
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
    m = bpy.data.materials.get("ru_page") or bpy.data.materials.new("ru_page")
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
    regions_out = {"version": 1, "generatedBy": "pipeline/ru_characters.py",
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
                          "files": {e: f"docs/ruth/design/faces/{ch}_{e}.png" for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z",
                         "bakedPose": [[b, d] for b, _, d in REST_BAKE.get(ch, [])],
                         "note": "Naomi: the stoop (degrees about design X) is baked into the rest skeleton" if ch in REST_BAKE else ""},
            "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                      for b, v in PROPS[ch].items()},
            "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
    if SHEET_SRC == "defaults":
        json.dump({"note": "default sheet positions used by ru_characters.py (assets/ruth/design.json had none); the "
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
    sc()["ru_regions"] = json.dumps(REGIONS)
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
        turntable(cam, Vector((x, 0, zb + Hh * 0.62)), 28, Hh * 1.9, Hh * 0.10, 60)
        render(os.path.join(WORK, f"pv_{ch}_props.png"))
        show([ch])
        sc().render.resolution_x, sc().render.resolution_y = 420, 420
        for e in EXPRESSIONS[ch]:
            img = bpy.data.images.load(os.path.join(FACES, f"{ch}_{e}.png"), check_existing=True)
            for m in bpy.data.materials:
                if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
                    m.node_tree.nodes["decal"].image = img
            turntable(cam, Vector((x, 0, hy - 0.08 * Hd)), 12, Hd * 3.6, Hd * 0.12, 60)
            render(os.path.join(WORK, f"pv_{ch}_expr_{e}.png"))
        for m in bpy.data.materials:
            if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
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
        tab = json.loads(sc().get("ru_regions", "[]"))
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
    if ch == "ruth":
        bend(rig, "scarf2", V(1, 0, 0), -25)
    if ch == "naomi":
        bend(rig, "shawl2", V(1, 0, 0), -25)
    if ch == "boaz":
        bend(rig, "cloakL", V(1, 0, 0), 25); bend(rig, "headcloth", V(1, 0, 0), -20)
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
    """Models wearing $RU_WORK/uvproof.png (or $RU_UV_TEXTURE) through UV0: front ortho (must equal the sheet) and
    3/4 + back perspective (back of the cape / robe behind the braid take their own region's colour)."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get("RU_UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
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

