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
ENV = "RU_"                      # env-var prefix the story_kit functions read (RU_NOBAKE, RU_UV_TEXTURE)
PAGE_MATERIAL = "ru_page"         # material name of the scanned page
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


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))                      # noqa: E402
import story_kit                                                                     # noqa: E402
story_kit.include(globals(), "characters")   # shared characters functions: 61 defs (docs/STORY-KIT.md)


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



EYE = {"ruth": (0.415, 0.305, 0.235), "naomi": (0.405, 0.270, 0.180), "boaz": (0.400, 0.250, 0.165)}


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


# =============================================================================================== head
# =============================================================================================== hair shells
# =============================================================================================== hands
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


# =============================================================================================== robes
# =============================================================================================== Ruth pack: shared
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


# =============================================================================================== Ruth
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


REST_BAKE = {   # Naomi: built straight (0.32), then stooped; arms hang plumb again, head tips back up
    "naomi": [("chest", V(1, 0, 0), 15.0), ("neck", V(1, 0, 0), 14.0),
              ("head", V(1, 0, 0), -17.0), ("upperArmL", V(1, 0, 0), -15.0), ("upperArmR", V(1, 0, 0), -15.0)],
}


# =============================================================================================== shared costume bits
# =============================================================================================== render helpers
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


class _RegionLookup(dict):
    def __missing__(self, r):
        # regions are recorded in the blend as a custom property by mode_build
        tab = json.loads(sc().get("ru_regions", "[]"))
        for i, k in enumerate(tab):
            self[i + 1] = k.split(".")[1]
        return dict.__getitem__(self, r)


REGION_OF = _RegionLookup()


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


if __name__ == "__main__":
    {"build": mode_build, "preview": mode_preview, "posetest": mode_posetest, "verify": mode_verify,
     "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), os.path.abspath(__file__), "all"],
                                                 check=True)}[MODE]()

