"""Joseph (story pack): characters joseph, brother, pharaoh, jacob — meshes, rig, weights, UVs, face decals, previews,
GLBs.

Contract: docs/joseph/CONTRACT.md §2-§3 (ids, heights, bone names, props), look: docs/joseph/DESIGN.md §1, §3, notes:
docs/joseph/RIG.md. On the shared kit (pipeline/story_kit/characters.py, Ruth's method: procedural quad cages from
pipeline/story_mesh.py, heads mapped from the D&G base head by landmarks, box-modelled hands, face decals on UV1 + an
`eyelids` blink, UV0 = front page projection with occlusion + ID-render fixes). New for Joseph:
  * one Joseph with three looks switched by props: the striped coat (`joseph_coat`) is a SKINNED prop mesh (body
    bones + coatL / coatR), shown by default and printed on the sheet; it is kept out of the body join, exported as its
    own skinned node and nested under the `coat` bone in the GLB so "joseph/coat" hides it. The head-cloth
    (`joseph_nemes`, rigid on `nemes`) and the broad collar (`joseph_collar`, rigid on `collar`) are hidden on the sheet
    and take their UV0 from the coat's printed stripes (PROP_ANCHORS): the stolen coat comes back as his crown;
  * the coat is closed over the chest (a broad centre stripe) and opens below the waist over the cream tunic; five
    stripe regions coat1..coat5 in viewer order: right sleeve + right back half / right panel / centre / left panel /
    left sleeve + left back half; stripe edges are bisect cuts (clean straight edges);
  * Jacob: long white beard, bushy white brows (decal), cream shawl over head and shoulders (shawl1 / shawl2), a
    walking stick in the right fist, the stoop baked into the rest pose (as Ruth's Naomi);
  * the brother: bare arms (a skin tube from the short tunic sleeve to the elbow), a shaggy-edged open sheepskin vest,
    a wide belt, a sling bag on the `bag` bone;
  * Pharaoh: bare round torso (belly on `belly`), the double crown (red + white, gold band), a broad collar, pleated
    kilt with a blue apron on `apron1`, kohl-lined eyes and a ceremonial chin beard.
Code copied from pipeline/ex_characters.py (Exodus, not on the kit): the face helpers with kohl / bushy brows, build_leg
with knee rows, open_front / sleeve_sv / retag / ring_rows_shell / shell_profile / at_arclen / rope, and
make_part_object with bisect cuts + retag.

Run (repo root):
  python3 pipeline/js_characters.py all                                           # everything below, in order
  python3 pipeline/js_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/js_characters.py -- build        # models, rig, GLBs, blend, ID render
  python3 pipeline/js_characters.py proof                                         # $JS_WORK/uvproof.png
  blender -b --factory-startup --python pipeline/js_characters.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/js_characters.py -- uvcheck      # models wearing uvproof.png
  blender -b --factory-startup --python pipeline/js_characters.py -- posetest     # bend / blink / jaw / cloth bones
  blender -b --factory-startup --python pipeline/js_characters.py -- verify       # re-import GLBs, check bones/budget
  python3 pipeline/js_characters.py compose                                       # preview_*.png contact sheets
  python3 pipeline/js_characters.py measure                                       # inscribed size of every region
Intermediate renders go to $JS_WORK (default /tmp/joseph_char/work). JS_ONLY=joseph (comma list) builds a subset.
"""
import sys, os, json, math, random

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/joseph/model")
FACES = os.path.join(ROOT, "docs/joseph/design/faces")
WORK = os.environ.get("JS_WORK", "/tmp/joseph_char/work")
ENV = "JS_"                      # env-var prefix the story_kit functions read (JS_NOBAKE, JS_UV_TEXTURE)
PAGE_MATERIAL = "js_page"         # material name of the scanned page
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/joseph/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("joseph", "brother", "pharaoh", "jacob")
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
EXTRA_BONES = {"joseph": ["coatL", "coatR", "coat", "nemes", "collar"],
               "jacob": ["shawl1", "shawl2", "stick"],
               "brother": ["bag"],
               "pharaoh": ["apron1", "belly"]}
PROPS = {"joseph": {"coat": True, "nemes": False, "collar": False},     # prop bone -> shown by default
         "jacob": {"stick": True}, "brother": {}, "pharaoh": {}}
SKINNED_PROPS = {"joseph": {"coat"}}        # props that deform with the body (separate skinned mesh, not rigid)
# 3D eyes pilot (2026-11-15, Joseph only): real eyeballs on bones eyeL / eyeR, sculpted sockets + nose, eyelids with
# thickness and lashes, brows as geometry, all driven by blend shapes and the runtime face (assets/joseph/model/
# face3d_joseph.json, DGFace3D.cs). The face decal then carries only the mouth, blush and tears.
# JS_EYES3D=0 builds the old decal-eyed Joseph; the other characters never change.
EYES3D = os.environ.get(ENV + "EYES3D", "1") != "0"
E3_CHARS = ("joseph",) if EYES3D else ()
if EYES3D:
    EXTRA_BONES["joseph"] = EXTRA_BONES["joseph"] + ["eyeL", "eyeR"]
CONTRACT_HEIGHT = {"joseph": 0.34, "brother": 0.38, "pharaoh": 0.40, "jacob": 0.33}
DEFAULT_SHEET = {"joseph": (-0.34, 0.015), "brother": (0.0, 0.015), "pharaoh": (0.34, 0.015), "jacob": (-0.34, 0.44)}
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (as Esther / Ruth / Exodus)

# ---------------------------------------------------------------------------------------------- palette (DESIGN §3)
COAT = {"coat1": "#D9463A", "coat2": "#F2C744", "coat3": "#4FA65A", "coat4": "#3B7FD0", "coat5": "#8A5CC2"}
PALETTE = {
    "joseph": dict(COAT, skin="#E9B88E", hair="#4A2E1F", tunic="#F1E7D0", belt="#6E4B30", sandals="#8A5A3B", trim="#E8B84A",
                   nemesA=COAT["coat2"], nemesB=COAT["coat4"], collar1=COAT["coat1"], collar3=COAT["coat3"],
                   collar5=COAT["coat5"]),
    "jacob": {"skin": "#E2AF8A", "hair": "#F4F1EA", "robe": "#8F7F6C", "shawl": "#EFE6D2", "belt": "#6E4B30",
              "stick": "#9B6B43", "sandals": "#6E4B30"},
    "brother": {"skin": "#C98E62", "hair": "#231A16", "tunic": "#A8562A", "vest": "#5E6B3A", "belt": "#6E4B30",
                "bag": "#C9A26A", "sandals": "#6E4B30", "cord": "#6E4B30"},
    "pharaoh": {"skin": "#C48A5E", "crownRed": "#C8423A", "crownWhite": "#FBF7EC", "collar": "#E8B84A",
                "kilt": "#FBF7EC", "apron": "#2E5FA8", "gold": "#E8B84A", "beard": "#2E5FA8", "inlay": "#2E5FA8",
                "nemesA": "#E8B84A", "nemesB": "#2E5FA8"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发和胡子", "hair and beard"), "tunic": ("内袍", "tunic"),
    "coat1": ("彩衣条纹 1", "coat stripe 1"), "coat2": ("彩衣条纹 2", "coat stripe 2"),
    "coat3": ("彩衣条纹 3", "coat stripe 3"), "coat4": ("彩衣条纹 4", "coat stripe 4"),
    "coat5": ("彩衣条纹 5", "coat stripe 5"), "belt": ("腰带", "belt"), "sandals": ("凉鞋", "sandals"),
    "nemesA": ("头巾条纹 A", "head-cloth stripe A"), "nemesB": ("头巾条纹 B", "head-cloth stripe B"),
    "collar1": ("项圈外环", "collar outer ring"), "collar3": ("项圈中环", "collar middle ring"),
    "collar5": ("项圈内环", "collar inner ring"),
    "robe": ("长袍", "robe"), "shawl": ("披巾", "shawl"), "stick": ("手杖", "walking stick"),
    "vest": ("羊皮背心", "sheepskin vest"), "bag": ("挎包", "sling bag"),
    "crownRed": ("王冠红色部分", "crown (red)"), "crownWhite": ("王冠白色部分", "crown (white)"),
    "collar": ("宽项圈", "collar"), "kilt": ("短裙", "kilt"), "apron": ("围裙", "apron"),
    "gold": ("金饰", "gold trim"), "beard": ("礼仪胡须", "ceremonial beard"),
    "trim": ("金色镶边", "gold edging"), "cord": ("系带", "lacing cord"), "inlay": ("青金石镶嵌", "lapis inlay"),
}
# regions too small to colour on A4: constant UV deep inside a printed region ("char.region", or "char.FACE" = that
# character's face skin away from eyes / brows / nose / mouth)
ANCHORS = {
    "joseph": {"belt": "joseph.hair", "sandals": "joseph.hair", "trim": "joseph.coat2"},
    "jacob": {"belt": "jacob.belt", "stick": "jacob.belt", "sandals": "jacob.belt"},
    "brother": {"belt": "brother.belt", "sandals": "brother.belt", "cord": "brother.belt"},
    "pharaoh": {"gold": "pharaoh.collar", "beard": "pharaoh.apron", "inlay": "pharaoh.apron",
                "nemesA": "pharaoh.collar", "nemesB": "pharaoh.apron"},
}
# hidden-by-default props are not printed: their regions sample a printed region. Joseph's head-cloth and collar wear
# the child's coat colours (DESIGN §1, intended: the stolen coat comes back as his crown). Override with design.json
# characters.<id>.propUV.<region> = [u, v] (page UV).
PROP_ANCHORS = {
    "joseph": {"nemesA": ["joseph.coat2"], "nemesB": ["joseph.coat4"], "collar1": ["joseph.coat1"],
               "collar3": ["joseph.coat3"], "collar5": ["joseph.coat5"]},
    "jacob": {}, "brother": {}, "pharaoh": {},
}
# parts whose printed area is a sliver: every face of (part, region) takes one UV inside a larger region
PART_ANCHORS = {ch: {("handL", "skin"): f"{ch}.FACE", ("handR", "skin"): f"{ch}.FACE"} for ch in CHARS}
for _ch in ("joseph", "brother", "pharaoh", "jacob"):
    PART_ANCHORS[_ch].update({("legL", "skin"): f"{_ch}.FACE", ("legR", "skin"): f"{_ch}.FACE"})
for _ch in ("joseph", "brother"):                 # bare upper arms (slivers on the sheet)
    PART_ANCHORS[_ch].update({("upperArmL", "skin"): f"{_ch}.FACE", ("upperArmR", "skin"): f"{_ch}.FACE"})

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
    # Joseph: seventeen, slim, open face; dark-brown hair to the jaw adds ~0.005 on top
    "joseph": scaled(KING, 0.945, 0.92, height=0.34, jaw=0.04, cheek=0.02, chin_narrow=0.03, noseH=0.0024,
                     nose_w=0.92, brow=0.70, lips=1.05, chinAmt=0.70, sockets=0.90, cheekbones=0.90, depth=1.03,
                     footScale=1.05, fr=dict(eye=0.478, brow=0.570, nose=0.264, mouth=0.160)),
    # the brother: about thirty, broad and heavy; strong jaw, heavy brow
    "brother": scaled(KING, 1.05, 1.13, height=0.38, jaw=0.18, cheek=0.04, chin_narrow=-0.04, noseH=0.0031,
                      nose_w=1.18, brow=1.30, lips=0.85, chinAmt=0.90, sockets=1.10, cheekbones=1.05,
                      fr=dict(eye=0.486, brow=0.578, nose=0.268, mouth=0.163)),
    # Pharaoh: forty, tall, round; the crown takes him to 0.45
    "pharaoh": scaled(KING, 1.105, 1.14, height=0.40, jaw=0.16, cheek=0.24, chin_narrow=-0.04, noseH=0.0030,
                      nose_w=1.02, nose_long=0.10, brow=0.95, lips=1.05, chinAmt=0.75, sockets=1.0, cheekbones=1.0,
                      depth=1.05, fr=dict(eye=0.486, brow=0.580, nose=0.266, mouth=0.163)),
    # Jacob: very old; built straight (~0.35), the baked stoop brings him to ~0.33
    "jacob": scaled(KING, 0.935, 0.95, height=0.34, jaw=0.00, cheek=0.02, chin_narrow=0.04, noseH=0.0034,
                    nose_w=1.15, nose_long=0.14, brow=1.25, lips=0.70, chinAmt=0.5, sockets=1.18, cheekbones=1.10,
                    fr=dict(eye=0.488, brow=0.580, nose=0.268, mouth=0.163)),
}
SPEC["joseph"]["neck"] = tuple(v * 1.14 for v in SPEC["joseph"]["neck"])      # 2026-11-15: less spindly neck
for _ch, _k in (("joseph", 1.12), ("brother", 1.16), ("pharaoh", 1.10)):     # bigger, sturdier hands
    SPEC[_ch]["handDims"] = {a: v * _k for a, v in SPEC[_ch]["handDims"].items()}
    SPEC[_ch]["hand"] *= 1.06
SPEC["brother"]["handDims"]["armR"] *= 1.30          # a working man's bare arms
SPEC["pharaoh"]["handDims"]["armR"] *= 1.30
SPEC["pharaoh"]["hw"] *= 1.10                          # a fuller face and a thicker neck for the king
SPEC["pharaoh"]["neck"] = tuple(v * 1.28 for v in SPEC["pharaoh"]["neck"])
FIST = {("jacob", "R")}             # Jacob's right hand closes round the stick
FIST_BEND = {("jacob", "R"): 22.0}

EYE = {"joseph": (0.410, 0.352, 0.262), "brother": (0.400, 0.298, 0.192), "pharaoh": (0.405, 0.328, 0.192),
       "jacob": (0.405, 0.292, 0.180)}     # 2026-11-15: ~8-11 % bigger eyes (friendlier at phone distance)
EXPRESSIONS = {"joseph": ["bright", "talk", "joy", "scared", "sad", "pray", "wise", "moved", "tears_joy"],
               "brother": ["sour", "talk", "angry", "greedy", "humble", "shock", "sorry", "relief"],
               "pharaoh": ["grand", "talk", "sleepy", "panic", "curious", "delighted"],
               "jacob": ["fond", "talk", "joy", "weep", "tears_joy"]}
DEFAULT_EXPR = {"joseph": "bright", "brother": "sour", "pharaoh": "grand", "jacob": "fond"}
# 3D eyes: sizes in head half-widths (hw) / eyeball radii (r), angles in degrees. Eye frame: x = outward, y up,
# z forward; alpha = horizontal angle (+ outward), beta = elevation. The opening is between the upper and lower lid
# margins; corners at alpha = -Ain (inner) / +Aout (outer), elevations cIn / cOut; U / D = upper / lower opening.
E3 = {"joseph": dict(r=0.245, ex=0.405, protrude=0.12, lidOut=1.10, lidMid=1.065, lidIn=1.03, yawOut=8.0,
                     Ain=50.0, Aout=55.0, cIn=-3.0, cOut=2.0, U=29.0, D=21.0, top=70.0, bot=-60.0, ext=32.0,
                     iris=33.0, pupil=0.40, cornea=0.05,
                     irisRGB=(120, 78, 44), browRGB=(64, 41, 28), lashRGB=(34, 23, 17), texPx=512)}
E3_TEX = {ch: os.path.join(MODEL, f"eyes_{ch}.png") for ch in E3}
E3_JSON = {ch: os.path.join(MODEL, f"face3d_{ch}.json") for ch in E3}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "joseph": {"idle": "bright", "talk": "talk", "walk": "bright", "run": "joy", "walk_sad": "sad", "twirl": "joy",
               "tell_dream": "talk", "in_pit": "scared", "carry_work": "bright", "sit_cell": "sad",
               "bow_point_up": "pray", "explain": "wise", "stand_proud": "wise", "recognise": "moved",
               "ask_gently": "wise", "reveal": "tears_joy", "lift_up": "moved", "hug": "tears_joy", "wave": "joy"},
    "jacob": {"idle": "fond", "talk": "talk", "give_coat": "joy", "weep": "weep", "walk_old": "fond",
              "hug": "tears_joy"},
    "brother": {"idle": "sour", "talk": "talk", "walk": "sour", "fold_arms": "sour", "grumble": "sour",
                "angry_point": "angry", "grab_coat": "angry", "take_coins": "greedy", "bow_low": "humble",
                "fall_back_scared": "shock", "stand_up": "sorry", "hug": "relief", "wave": "relief"},
    "pharaoh": {"idle": "grand", "talk": "talk", "doze": "sleepy", "wake_jump": "panic", "lean_ask": "curious",
                "delighted": "delighted", "crown_him": "delighted", "wave": "grand"},
}


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
        h1 = ir * 0.40; hx, hy = ix + ir * 0.36, iy + ir * 0.40
        dl.ellipse((P(hx - h1, hy + h1)[0], P(hx - h1, hy + h1)[1], P(hx + h1, hy - h1)[0], P(hx + h1, hy - h1)[1]),
                   fill=(255, 255, 255, 255))
        h2 = ir * 0.15; hx, hy = ix - ir * 0.40, iy - ir * 0.42
        dl.ellipse((P(hx - h2, hy + h2)[0], P(hx - h2, hy + h2)[1], P(hx + h2, hy - h2)[0], P(hx + h2, hy - h2)[1]),
                   fill=(255, 255, 255, 230))
        h3 = ir * 0.09; hx, hy = ix + ir * 0.05, iy + ir * 0.62           # a third tiny sparkle (2026-11-15)
        dl.ellipse((P(hx - h3, hy + h3)[0], P(hx - h3, hy + h3)[1], P(hx + h3, hy - h3)[0], P(hx + h3, hy - h3)[1]),
                   fill=(255, 255, 255, 200))
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


    def tear_streak(img, c, half, side, ln=1.0):
        """A wet track running from the lower lid down the cheek, ending in a drop."""
        cx, cy = c; ew, eh = half; o = side
        x0 = cx + o * ew * 0.10; y0 = cy - eh * 1.05
        pts = bez((x0, y0), (x0 + o * ew * 0.05, y0 - 0.05 * ln), (x0 - o * ew * 0.10, y0 - 0.09 * ln),
                  (x0 + o * ew * 0.02, y0 - 0.13 * ln), 20)
        soft(img, lambda d: stroke(d, pts, 0.012, 0.016, col=(170, 215, 245, 170)), 0.002)
        soft(img, lambda d: stroke(d, pts, 0.004, 0.005, col=(255, 255, 255, 200)), 0.001)
        drop(img, pts[-1][0], pts[-1][1] - 0.010, 0.017)

    made = {}
    for ch in CHARS:
        F = face_layout(ch)
        eL, eR, half, by, my, ny_ = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"], F["nose"]
        bcol = {"joseph": (58, 36, 24, 255), "brother": (30, 21, 17, 255), "pharaoh": (26, 18, 14, 255),
                "jacob": (246, 243, 236, 255)}[ch]
        iris = {"joseph": (78, 48, 28), "brother": (62, 40, 24), "pharaoh": (64, 40, 24), "jacob": (96, 76, 56)}[ch]
        bw = {"joseph": 0.036, "brother": 0.056, "pharaoh": 0.020, "jacob": 0.046}[ch]
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            E = dict(look=(0, 0), top=1.0, bot=1.0, tilt=0.15, lash=0, mode="open", lid=0.10, inner_up=0.0,
                     pupil=0.55, wet=False, kohl=0.0)
            Bp = dict(raise_=0.0, inner=0.0, arch=0.35, thick=1.0, outer=0.0)
            Bl, Br = {}, {}
            M = dict(kind="flat", wd=0.095, jaw=0.0, side=0.0)
            lipcol = None; rim = None; bl = 0; crow = 0; folds = 0.0; bags = False; crs = True
            fh = None; drops = []; sweat = False; streaks = 0
            if ch == "joseph":
                # seventeen, open and friendly: big dark eyes, soft brows; the same face carries him to thirty-seven
                E.update(lid=0.12, top=0.94, bot=0.92, tilt=0.08, pupil=0.56); M["wd"] = 0.088
                lipcol = (190, 108, 96, 120); Bp.update(raise_=0.078, arch=0.26, thick=1.08); bl = 30
                if ex == "bright":
                    E.update(look=(0.05, 0.06)); M.update(kind="smile", wd=0.090); Bp.update(arch=0.30); bl = 70
                elif ex == "talk":
                    M.update(kind="open", wd=0.078, jaw=0.07); Bp.update(raise_=0.090, arch=0.44)
                elif ex == "joy":
                    E.update(mode="happy"); Bp.update(raise_=0.100, arch=0.52); M.update(kind="grin", wd=0.100, jaw=0.14)
                    bl = 140
                elif ex == "scared":
                    E.update(top=1.30, bot=1.15, pupil=0.36, lid=0.05, tilt=0.0, look=(0, 0.10))
                    Bp.update(inner=0.046, raise_=0.122, arch=0.28, outer=-0.012)
                    M.update(kind="wobbly", wd=0.078, jaw=0.10); sweat = True; bl = 30
                elif ex == "sad":
                    E.update(top=0.86, look=(0, -0.50), tilt=-0.08, wet=True)
                    Bp.update(inner=0.044, raise_=0.094, arch=0.10, outer=-0.022); M.update(kind="frown", wd=0.068)
                    bl = 50
                elif ex == "pray":
                    E.update(mode="closed", lash=1); Bp.update(inner=0.016, raise_=0.086, arch=0.26)
                    M.update(kind="soft", wd=0.070); crs = False
                elif ex == "wise":
                    E.update(top=0.80, bot=0.80, look=(0.10, -0.05), lid=0.14); Bp.update(inner=0.006, raise_=0.080, arch=0.30)
                    M.update(kind="soft", wd=0.082); crow = 1; bl = 55
                elif ex == "moved":
                    E.update(top=0.92, look=(0, 0.12), tilt=-0.04, wet=True)
                    Bp.update(inner=0.036, raise_=0.098, arch=0.18, outer=-0.012); M.update(kind="soft", wd=0.072)
                    streaks = 1; bl = 95
                elif ex == "tears_joy":
                    E.update(mode="happy"); Bp.update(inner=0.022, raise_=0.098, arch=0.30)
                    M.update(kind="grin", wd=0.096, jaw=0.08); streaks = 2; bl = 125
            elif ch == "brother":
                # broad and heavy; the brows do the scowling; later the same face looks worn and sorry. The mouth sits
                # on a short black beard: a light lip rim / patch so it reads at phone distance (LESSONS L42)
                E.update(lid=0.20, top=0.84, bot=0.86, tilt=0.04, pupil=0.54); M["wd"] = 0.090
                lipcol = (176, 98, 84, 220); rim = (214, 150, 132, 235)
                Bp.update(raise_=0.064, arch=0.24, thick=1.0); bl = 0; crow = 1; folds = 0.030
                if ex == "sour":
                    E.update(top=0.74, bot=0.84, look=(0.40, -0.05), tilt=0.10)
                    Bp.update(inner=-0.022, raise_=0.062, arch=0.16, outer=0.008); M.update(kind="frown", wd=0.078)
                    bl = 25
                elif ex == "talk":
                    E.update(top=0.80); Bp.update(inner=-0.012, raise_=0.064, arch=0.20)
                    M.update(kind="open", wd=0.082, jaw=0.08)
                elif ex == "angry":
                    E.update(top=0.70, bot=0.80, tilt=0.30, pupil=0.48)
                    Bp.update(inner=-0.054, raise_=0.060, arch=0.10, outer=0.028, thick=1.25)
                    M.update(kind="shout", wd=0.090, jaw=0.12); bl = 110
                elif ex == "greedy":
                    E.update(top=0.58, bot=0.78, look=(0.85, -0.05)); Bl = dict(raise_=0.098, arch=0.70)
                    Br = dict(raise_=0.058, inner=-0.022, arch=0.16); M.update(kind="smirk", wd=0.094, side=1)
                elif ex == "humble":
                    E.update(top=0.70, look=(0, -0.60), tilt=-0.10)
                    Bp.update(inner=0.040, raise_=0.080, arch=0.10, outer=-0.024); M.update(kind="flat", wd=0.068)
                elif ex == "shock":
                    E.update(top=1.32, bot=1.20, pupil=0.32, lid=0.06, tilt=0.0)
                    Bp.update(raise_=0.120, arch=0.55, inner=0.010); M.update(kind="o", wd=0.072, jaw=0.24); sweat = True
                elif ex == "sorry":
                    E.update(top=0.80, look=(0, -0.40), tilt=-0.12, wet=True)
                    Bp.update(inner=0.052, raise_=0.090, arch=0.08, outer=-0.030)
                    M.update(kind="wobbly", wd=0.076, jaw=0.02); streaks = 2; folds = 0.045
                elif ex == "relief":
                    E.update(top=0.76, bot=0.70, look=(0, 0.05)); Bp.update(inner=0.024, raise_=0.078, arch=0.30)
                    M.update(kind="smile", wd=0.092); crow = 3; bl = 40
            elif ch == "pharaoh":
                # comic and generous: kohl-lined almond eyes with a wing, thin high arched brows, a big range
                E.update(kohl=0.6, lid=0.10, top=0.90, bot=0.90, tilt=0.20, pupil=0.56); M["wd"] = 0.090
                lipcol = (168, 92, 82, 170); Bp.update(raise_=0.100, arch=0.58, thick=1.0, outer=0.010)
                if ex == "grand":
                    E.update(top=0.86, bot=0.88, look=(0.12, 0.12), lid=0.12); Bp.update(raise_=0.110, arch=0.66)
                    M.update(kind="smile", wd=0.094); bl = 60
                elif ex == "talk":
                    M.update(kind="open", wd=0.088, jaw=0.10); Bp.update(raise_=0.106, arch=0.64)
                elif ex == "sleepy":
                    E.update(top=0.34, bot=0.80, look=(0, -0.40), tilt=-0.10, lid=0.34, kohl=0.40)
                    Bp.update(raise_=0.082, arch=0.30, outer=-0.020); M.update(kind="o", wd=0.050, jaw=0.04)
                elif ex == "panic":
                    E.update(top=1.40, bot=1.25, pupil=0.30, lid=0.06, tilt=0.05)
                    Bp.update(inner=0.050, raise_=0.140, arch=0.30, outer=-0.010)
                    M.update(kind="shout", wd=0.090, jaw=0.18); sweat = True
                elif ex == "curious":
                    E.update(top=1.02, look=(-0.50, 0.15)); Bl = dict(raise_=0.132, arch=0.82)
                    Br = dict(raise_=0.092, inner=-0.010, arch=0.40); M.update(kind="small", wd=0.060)
                elif ex == "delighted":
                    E.update(mode="happy"); Bp.update(raise_=0.118, arch=0.74); M.update(kind="grin", wd=0.110, jaw=0.30)
                    bl = 90
            else:   # jacob
                # very old and kind: crinkled eyes, bushy white brows carry the acting, forehead lines; the mouth sits
                # on the white beard / moustache (light lip patch)
                E.update(lid=0.22, top=0.80, bot=0.80, tilt=0.02, pupil=0.56); M["wd"] = 0.082
                lipcol = (176, 98, 84, 200); rim = (196, 132, 116, 210)
                Bp.update(raise_=0.070, arch=0.30, thick=1.0); bl = 55; crow = 3; folds = 0.050; bags = True
                fh = dict(y=by + 0.085, n=3, worry=0.0)
                if ex == "fond":
                    E.update(top=0.74, bot=0.70, look=(0.05, -0.02)); Bp.update(inner=0.012, raise_=0.072)
                    M.update(kind="smile", wd=0.082); bl = 70
                elif ex == "talk":
                    M.update(kind="open", wd=0.078, jaw=0.08); E.update(top=0.82); Bp.update(raise_=0.080, arch=0.36)
                elif ex == "joy":
                    E.update(mode="happy"); Bp.update(raise_=0.090, arch=0.50); M.update(kind="grin", wd=0.094, jaw=0.12)
                    bl = 85
                elif ex == "weep":
                    E.update(mode="closed"); Bp.update(inner=0.052, raise_=0.088, arch=0.06, outer=-0.030)
                    M.update(kind="wobbly", wd=0.074, jaw=0.04); fh.update(worry=0.016); streaks = 2; crs = False
                elif ex == "tears_joy":
                    E.update(mode="happy"); Bp.update(inner=0.024, raise_=0.090, arch=0.34)
                    M.update(kind="grin", wd=0.090, jaw=0.08); streaks = 2; bl = 85
            # ---- draw
            if bl:
                blush(img, 0.31, ny_ - 0.035, 0.088, 0.046, bl)
            e3 = ch in E3_CHARS              # 3D eyes / brows / nose: the decal keeps mouth, blush and tears only
            if not e3:
                nose_hint(img, ny_ + 0.006, {"joseph": 0.030, "brother": 0.038, "pharaoh": 0.034, "jacob": 0.040}[ch],
                          strength={"joseph": 0.85, "brother": 1.15, "pharaoh": 1.05, "jacob": 1.15}[ch])
            if folds:
                wide = M["kind"] in ("smile", "grin")
                cheek_lines(img, ny_ + 0.004, my + (0.000 if wide else 0.012), 0.100, M["wd"] * 1.25 + (0.040 if wide else 0.030),
                            col=(130, 74, 56, 105 if wide else 80))
            if fh:
                forehead(img, fh["y"], n=fh["n"], worry=fh["worry"])
            for side, c in (((1, eL), (-1, eR)) if not e3 else ()):
                eye(img, c, half, side=side, iris=iris, line=0.020 if ch != "pharaoh" else 0.019, **E)
                if crs and E["mode"] == "open":
                    crease(img, c, half, side, lift=1.55 if ch != "jacob" else 1.50,
                           col=(140, 90, 72, 110 if ch != "jacob" else 150))
                if bags and E["mode"] == "open":
                    under_eye(img, c, half, side, drop=1.25 if E["bot"] < 0.9 else 1.35, col=(140, 90, 76, 130))
                if crow:
                    crows(img, c, half, side, n=crow, ln=1.0 if E["mode"] == "open" else 1.2,
                          col=(130, 80, 62, 150 if ch == "jacob" else 90))
            dr = ImageDraw.Draw(img)
            for side, c in (((1, eL), (-1, eR)) if not e3 else ()):
                b = dict(Bp); b.update(Bl if side == 1 else Br)
                b["inner"] *= 1.45; b["outer"] *= 1.45               # brows act more clearly per expression
                b["arch"] = 0.30 + (b["arch"] - 0.30) * 1.35
                b["raise_"] = b["raise_"] + (b["raise_"] - 0.080) * 0.6
                if ch == "jacob":
                    bushy_brow(img, side, (c[0], by - 0.010), half, w=bw, **b)
                else:
                    brow(dr, side, (c[0], by - 0.015), half, w=bw, col=bcol,
                         length=1.18 if ch == "pharaoh" else (1.10 if ch == "brother" else 1.05), **b)
            if rim and M["kind"] in ("open", "grin", "o", "shout", "wobbly"):
                rim_mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, M["jaw"], rim)
            elif rim:                           # closed mouth on a beard: a light lip patch under the line
                rx, ry = M["wd"] * 1.30, M["wd"] * 0.42
                soft(img, lambda d: d.ellipse((P(0.5 - rx, my + ry * 0.5)[0], P(0.5 - rx, my + ry * 0.5)[1],
                                               P(0.5 + rx, my - ry * 1.3)[0], P(0.5 + rx, my - ry * 1.3)[1]),
                                              fill=rim), 0.004)
            mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, lipcol=lipcol, jaw=M["jaw"], side=M["side"])
            thalf = half
            if e3:   # tears start under the smaller 3D lower lid
                P3 = E3[ch]; wd_ = F["rect"][2] - F["rect"][0]; r_ = P3["r"] * SPEC[ch]["hw"]
                thalf = (0.9 * r_ / wd_, r_ * P3["lidOut"] * math.sin(math.radians(P3["D"] + 6)) / wd_ / 1.05)
            for k_, (side, c) in enumerate(((1, eL), (-1, eR))):
                if k_ < streaks:
                    tear_streak(img, c, thalf, side, ln=1.0 if k_ == 0 else 0.8)
            if sweat:
                drop(img, 0.88, by - 0.030, 0.020)
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
    for ch in E3:
        if ch in E3_CHARS:
            draw_eye_texture(ch)
        elif os.path.exists(E3_TEX[ch]):
            os.remove(E3_TEX[ch])              # JS_EYES3D=0: decal eyes again, no atlas
    return made


def draw_eye_texture(ch):
    """Atlas of the 3D eyes (E3): the front hemisphere of the eyeball as a disk (radius 0.5 = 90 deg from the gaze,
    uv radius = 0.5 sin(angle)): warm sclera shaded toward the sides, an iris with radial fibres, a light collarette,
    a dark limbal ring and the pupil. Outside the disk: brow colour (top right) and lash colour (top left), the
    constant texels of the brows / lash lines (E3_UV)."""
    import numpy as np
    from PIL import Image
    P3 = E3[ch]; n = P3["texPx"]
    yy, xx = np.mgrid[0:n, 0:n]
    u = (xx + 0.5) / n; v = 1.0 - (yy + 0.5) / n
    dx = (u - 0.5) / 0.5; dy = (v - 0.5) / 0.5
    rr = np.sqrt(dx * dx + dy * dy)
    rho = np.degrees(np.arcsin(np.clip(rr, 0, 1)))
    th = np.arctan2(dy, dx)

    def ss(a, b, x):
        t = np.clip((x - a) / (b - a), 0, 1)
        return t * t * (3 - 2 * t)

    def mix(a, b, t):
        return a * (1 - t[..., None]) + np.array(b, float) * t[..., None]
    img = np.zeros((n, n, 3), float)
    img[:] = (247, 243, 237)
    img = mix(img, (229, 219, 211), ss(48, 88, rho))                    # sclera darker toward the sides
    q = rho / P3["iris"]
    rnd = np.random.RandomState(7)
    fib = np.zeros_like(th)
    for k in range(18):                                                  # radial fibres
        f = rnd.randint(9, 60); ph = rnd.uniform(0, 6.283); a = rnd.uniform(0.3, 1.0) / (1 + k * 0.15)
        fib += a * np.sin(f * th + ph + 1.8 * q * rnd.uniform(-1, 1))
    fib = fib / np.abs(fib).max()
    base = np.array(P3["irisRGB"], float)
    inner = np.minimum(255, base * 1.45 + 18); outer = base * 0.62
    iris = mix(np.broadcast_to(inner, img.shape).copy(), base, ss(0.38, 0.62, q))
    iris = mix(iris, outer, ss(0.70, 0.98, q))
    iris *= (0.90 + 0.14 * (0.5 + 0.5 * fib))[..., None]
    col = 0.56 + 0.025 * np.sin(11 * th)                                 # collarette: a light wavy ring
    iris = mix(iris, np.minimum(255, base * 1.6 + 24), 0.20 * np.exp(-((q - col) / 0.06) ** 2))
    lim = ss(0.80, 0.97, q)                                              # limbal ring, soft into the sclera
    iris = mix(iris, (42, 27, 19), 0.85 * lim)
    a_iris = 1 - ss(0.99, 1.10, q)
    img = img * (1 - a_iris[..., None]) + iris * a_iris[..., None]
    img = mix(img, (52, 34, 24), 0.35 * np.exp(-((q - 1.04) / 0.05) ** 2))   # thin shadow just outside the limbus
    pupil = 1 - ss(P3["pupil"] - 0.035, P3["pupil"] + 0.02, q)
    img = mix(img, (15, 11, 9), pupil)
    out = rr > 1.04
    img[out & (v > 0.5) & (u >= 0.5)] = P3["browRGB"]
    img[out & (v > 0.5) & (u < 0.5)] = P3["lashRGB"]
    img[out & (v <= 0.5)] = (229, 219, 211)
    Image.fromarray(np.clip(img, 0, 255).astype(np.uint8), "RGB").save(E3_TEX[ch])
    print("eye texture ->", os.path.relpath(E3_TEX[ch], ROOT))


def compose():
    """Contact sheets model/preview_<char>.png, preview_all.png, preview_uvcheck.png, preview_pose.png from the
    $JS_WORK renders."""
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
        if not os.path.exists(files[0]):
            continue
        top = grid(files, [lb for _, lb in views], 4, (480, 720), f"{ch}: rest pose, demo palette + default face decal")
        det = [("head", "face 3/4"), ("headfront", "face front"), ("handL", "left hand"), ("handR", "right hand"),
               ("props", "hidden props shown" if ch != "joseph" else "governor look: coat off, head-cloth + collar on")]
        if ch == "joseph":
            det += [("plain", "plain look: coat off"), ("propsback", "governor look, back")]
        files2 = [os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det]
        bot = grid(files2, [lb for _, lb in det], 5, (384, 384), "close-ups")
        exprs = [os.path.join(WORK, f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]]
        ex = grid(exprs, EXPRESSIONS[ch], 5, (320, 320), "face decals on the model (UV1)")
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
        crop = (0, 400, 1000, top_a.height)                   # both rows (Jacob stands on the second row)
        r1 = [top_a.crop(crop), top_b.crop(crop)]
        r2 = [Image.open(uv[2]).convert("RGB").resize((1000, 562)), Image.open(uv[3]).convert("RGB").resize((1000, 562))]
        gov = [os.path.join(WORK, f) for f in ("uv_coat.png", "uv_governor.png", "uv_governor_back.png", "uv_plain.png")]
        r3 = [Image.open(f).convert("RGB").resize((500, 500)) if os.path.exists(f) else Image.new("RGB", (500, 500), bg)
              for f in gov]
        h1 = r1[0].height
        H_ = 34 + h1 + 26 + 562 + 26 + 30 + 500 + 26
        im = Image.new("RGB", (2000, H_), bg); d = ImageDraw.Draw(im)
        d.text((10, 10), "UV0 proof: a perfectly coloured sheet (ID render in demo colours, left) worn by the models "
                         "(front ortho = the sheet; 3/4 and back keep each region's colour)", fill=(40, 30, 20))
        im.paste(r1[0], (0, 34)); im.paste(r1[1], (1000, 34))
        d.text((8, 34 + h1 + 6), "sheet (texture)", fill=(60, 50, 40)); d.text((1008, 34 + h1 + 6), "models, front ortho", fill=(60, 50, 40))
        im.paste(r2[0], (0, 34 + h1 + 26)); im.paste(r2[1], (1000, 34 + h1 + 26))
        d.text((8, 34 + h1 + 26 + 568), "3/4", fill=(60, 50, 40)); d.text((1008, 34 + h1 + 26 + 568), "back", fill=(60, 50, 40))
        y3 = 34 + h1 + 26 + 562 + 26
        d.text((10, y3 + 6), "Joseph's colour hand-over through UV0: the coat as printed (1), the governor look (2, 3): "
                             "head-cloth stripes = coat2 / coat4, collar rings = coat1 / coat3 / coat5; plain tunic (4)",
               fill=(40, 30, 20))
        for i, t in enumerate(r3):
            im.paste(t, (i * 500, y3 + 30))
        im.save(os.path.join(MODEL, "preview_uvcheck.png"))
    pf = [os.path.join(WORK, f"pose_{ch}_{v}.png") for ch in CHARS for v in "ab"]
    if all(os.path.exists(f) for f in pf):
        g = grid(pf, [f"{ch} {v}" for ch in CHARS for v in ("front-ish", "side-ish")], 4, (320, 480),
                 "pose test: elbows, finger curl, thigh + knee, spine, head turn, jaw open, half blink (eyelids Y x6), "
                 "coatL / shawl2 / bag / apron1 / belly")
        g.save(os.path.join(MODEL, "preview_pose.png"))
    print("composed previews ->", MODEL)


def measure():
    """Largest inscribed circle per (char, region) in the ID render (2000 px = 1 art unit), in mm on the A4 sheet
    (art width 1000 px at 150 dpi = 169.3 mm). Region outlines are drawn ~3 px wide at 150 dpi; the sheet's check
    measures the cell inside the ink, so the effective size is about 0.5 mm smaller than reported here."""
    import numpy as np
    from PIL import Image
    from scipy import ndimage
    meta = json.load(open(os.path.join(MODEL, "id_characters_2x.json")))
    im = np.array(Image.open(os.path.join(MODEL, "id_characters_2x.png")).convert("RGBA"))
    key = im[..., 0].astype(np.int64) * 65536 + im[..., 1].astype(np.int64) * 256 + im[..., 2]
    alpha = im[..., 3] > 0
    mm_per_px = 169.33 / 2000.0
    lab = np.zeros(key.shape, np.int32); names = {}
    for e in meta["ids"]:
        k = (e["char"], e["region"])
        if k not in names:
            names[k] = len(names) + 1
        lab[(key == e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2]) & alpha] = names[k]
    out = {}
    for (ch, reg), L in names.items():
        m = lab == L
        comp, n = ndimage.label(m)
        if not n:
            continue
        dt = ndimage.distance_transform_edt(m)
        best = float(dt.max()) * 2 * mm_per_px
        out.setdefault(ch, {})[reg] = round(best, 1)
    for ch, d in out.items():
        print(ch, " ".join(f"{r}={v}" for r, v in sorted(d.items(), key=lambda kv: kv[1])))
    json.dump(out, open(os.path.join(WORK, "measure.json"), "w"), indent=1)
    return out


def eyes3d_compose():
    """preview_eyes3d_compare.png (old vs new: front, 3/4, profile) and preview_eyes3d_expressions.png (3 x 4) from
    the e3_* renders in $JS_WORK (Blender mode `eyes3d`, once with JS_E3_TAG=old on the old build)."""
    from PIL import Image, ImageDraw
    W = 600
    out = Image.new("RGB", (3 * W, 2 * W + 60), (250, 246, 238)); d = ImageDraw.Draw(out)
    for r_, tag in enumerate(("old", "new")):
        for c_, nm in enumerate(("front", "q34", "side")):
            p = os.path.join(WORK, f"e3_{tag}_{nm}.png")
            if os.path.exists(p):
                out.paste(Image.open(p).convert("RGB").resize((W, W)), (c_ * W, 30 + r_ * (W + 30)))
        d.text((10, 8 + r_ * (W + 30)), {"old": "OLD: decal eyes / brows / nose", "new": "NEW: 3D eyes, lids, brows, nose (JS_EYES3D=1)"}[tag],
               fill=(40, 30, 20))
    out.save(os.path.join(MODEL, "preview_eyes3d_compare.png"))
    labels = json.load(open(os.path.join(WORK, "e3_expr.json")))
    C_ = 420
    g = Image.new("RGB", (4 * C_, 3 * (C_ + 26)), (250, 246, 238)); d = ImageDraw.Draw(g)
    for i, lab in enumerate(labels[:12]):
        x, y = (i % 4) * C_, (i // 4) * (C_ + 26)
        g.paste(Image.open(os.path.join(WORK, f"e3_expr_{i:02d}.png")).convert("RGB"), (x, y + 26))
        d.text((x + 8, y + 7), lab, fill=(40, 30, 20))
    g.save(os.path.join(MODEL, "preview_eyes3d_expressions.png"))
    print("eyes3d previews ->", os.path.relpath(MODEL, ROOT))


if not IN_BLENDER:
    if __name__ == "__main__":
        mode = sys.argv[1] if len(sys.argv) > 1 else "faces"

        def run_all():
            import subprocess
            bl = os.environ.get("BLENDER", "/Applications/Blender.app/Contents/MacOS/Blender")
            me = os.path.abspath(__file__)
            draw_faces()
            subprocess.run(["nice", "-n", "10", bl, "-b", "--factory-startup", "--python", me, "--", "build"], check=True,
                           stdout=subprocess.DEVNULL)
            proof()
            for m in ("preview", "uvcheck", "posetest", "verify"):
                subprocess.run(["nice", "-n", "10", bl, "-b", "--factory-startup", "--python", me, "--", m], check=True,
                               stdout=subprocess.DEVNULL)
            compose()
            measure()
            v = json.load(open(os.path.join(WORK, "verify.json")))
            for ch, i in v.items():
                print(ch, "bonesMatch", i["bonesMatch"], "actions", i["actions"], "tris", i["tris"],
                      "uvOrderOK", i.get("uvOrderOK"), "top", i.get("heightTop"))
        {"faces": draw_faces, "compose": compose, "proof": proof, "all": run_all, "measure": measure,
         "eyes3d": eyes3d_compose}[mode]()
    raise SystemExit(0)
# =============================================================================================== Blender part
sys.path.insert(0, HERE)
from story_mesh import *                                  # noqa: E402,F401,F403
import bmesh                                               # noqa: E402
from mathutils import Vector, Matrix                       # noqa: E402
from mathutils.bvhtree import BVHTree                      # noqa: E402

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
MODE = argv[0] if argv else "build"
ONLY = [c for c in os.environ.get("JS_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()


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


ARM12 = [math.radians(75 - 30 * k) for k in range(12)]

# =============================================================================================== legs (from Exodus)
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
# leg rows extended above the knee for bare shins under a knee-length tunic / kilt (Exodus)
LEG_ROWS_KNEE = [(0.100, 0.0186, 0.0098, 0.0094, 0.0080, 0.0082, 0.0004), (0.0865, 0.0187, 0.0090, 0.0085, 0.0084, 0.0072, 0.0010),
                 (0.078, 0.0188, 0.0084, 0.0078, 0.0070, 0.0078, 0.0006), (0.070, 0.0189, 0.0092, 0.0086, 0.0062, 0.0092, 0.0004)] + LEG_ROWS


def build_leg(C, side, shoe_top, reg_shoe, pointy=0.0, top_y=0.050, regfn2=None, rows_in=None, rk=1.0):
    """Lower leg + foot from LEG_ROWS (or rows_in = LEG_ROWS_KNEE for bare shins); rk thins the leg above the ankle
    (copied from pipeline/ex_characters.py)."""
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


def sandals_as(reg, S):
    f = sandal_regfn(S)
    return lambda yy, dz: reg if f(yy, dz) == "sandals" else "skin"


# =============================================================================================== garments (Exodus)
KING_ROBE = [(0.2760, 0.0128, 0.0118, -0.0125), (0.2745, 0.0195, 0.0134, -0.0142), (0.2725, 0.0285, 0.0148, -0.0155),
             (0.2705, 0.0368, 0.0158, -0.0161), (0.2690, 0.0418, 0.0163, -0.0164), (0.2675, 0.0446, 0.0166, -0.0166),
             (0.2620, 0.0482, 0.0182, -0.0170), (0.2540, 0.0476, 0.0202, -0.0170), (0.2440, 0.0460, 0.0218, -0.0168),
             (0.2320, 0.0442, 0.0230, -0.0162), (0.2180, 0.0432, 0.0240, -0.0160), (0.2040, 0.0442, 0.0236, -0.0170),
             (0.1900, 0.0456, 0.0230, -0.0180), (0.1600, 0.0482, 0.0232, -0.0195), (0.1200, 0.0512, 0.0246, -0.0210),
             (0.0800, 0.0546, 0.0264, -0.0228), (0.0400, 0.0580, 0.0284, -0.0245), (0.0110, 0.0606, 0.0300, -0.0258)]
PHARAOH_TORSO = [(0.2760, 0.0110, 0.0100, -0.0108), (0.2745, 0.0175, 0.0112, -0.0122), (0.2725, 0.0262, 0.0124, -0.0134),
                 (0.2705, 0.0340, 0.0132, -0.0140), (0.2690, 0.0392, 0.0136, -0.0143), (0.2675, 0.0420, 0.0140, -0.0145),
                 (0.2620, 0.0436, 0.0152, -0.0148), (0.2540, 0.0414, 0.0166, -0.0150), (0.2440, 0.0372, 0.0168, -0.0146),
                 (0.2320, 0.0326, 0.0150, -0.0138), (0.2180, 0.0298, 0.0140, -0.0132), (0.2040, 0.0306, 0.0142, -0.0138),
                 (0.1900, 0.0326, 0.0148, -0.0146), (0.1780, 0.0330, 0.0150, -0.0148)]


def trim_rows(rows, hem, top_drop=0.0):
    """Garment rows cut at y = hem (a row exactly at the hem); the first row lowered by top_drop."""
    out = [r for r in rows if r[0] > hem + 0.006] + [(hem,) + tuple(table(rows, hem))]
    if top_drop:
        out[0] = (out[0][0] - top_drop,) + out[0][1:]
    return out


def open_front(C, cg, rows, gap, N_=32, e_=2.5, fade_deg=70.0, y_open=None, ramp=0.012):
    """Open a garment shell down the front (Boaz's abaya method, from Exodus): in superellipse angle space push the
    centre column to +gap(y) and its left neighbour to -gap(y), then drop the faces between them. New: y_open = the
    top of the opening (closed above; the push fades in over `ramp` below it, so the opening ends in a V)."""
    S = C.S; dlt = 2 * math.pi / N_; fade = math.radians(fade_deg)

    def on_arm(c):
        for side in "LR":
            A_ = C.arm[side]; sv = (c - A_["S0"]).dot(A_["d"])
            if sv > 0.004 * S and (c - (A_["S0"] + A_["d"] * sv)).length < 0.03 * S:
                return True
        return False

    def tt(y):
        return 1.0 if y_open is None else smoothstep(y_open, y_open - ramp * S, y)
    for i, p in enumerate(cg.v):
        if on_arm(p) or p.z < -0.002:
            continue
        t = tt(p.y)
        if t <= 0:
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
        a1 = a0 + (a1 - a0) * t
        cg.v[i] = V(se(math.sin(a1), e_) * hw_ * scl, p.y, zc_ + se(math.cos(a1), e_) * rd_ * scl)

    def opening(c):
        if on_arm(c):
            return False
        return c.z > 0 and abs(math.atan2(c.x, c.z)) < gap(c.y) * 0.85 * tt(c.y) and tt(c.y) > 0.25
    drop_faces(cg, opening)
    return on_arm


def front_edge(rows, gap, y, sd, e_=2.5, off=0.0):
    """Point on the opened front edge (side sd) at height y."""
    hw_, zf_, zb_ = table(rows, y); zc_ = (zf_ + zb_) / 2; rd_ = (zf_ - zb_) / 2
    a = sd * gap(y)
    return V(se(math.sin(a), e_) * (hw_ + off), y, zc_ + se(math.cos(a), e_) * (rd_ + off))


def sleeve_sv(C, p):
    """(side, distance along the arm, radial vector) when p lies in a sleeve tube, else None."""
    for side in "LR":
        A = C.arm[side]; sv = (p - A["S0"]).dot(A["d"])
        if sv > 0.004 * C.S:
            rv = p - (A["S0"] + A["d"] * sv)
            if rv.length < 0.030 * C.S:
                return side, sv, rv
    return None


def ring_rows_shell(C, rows, N, reg, wfn, nf=0, amp=0.0, e=2.5, hem_lip=True, pc=0, top_lip=False):
    """A plain closed garment shell (skirt / kilt) from rows (y, hw, zf, zb) top -> bottom, no sleeve ports, with
    optional radial pleats (nf folds, amp growing toward the hem) and a rolled hem (Exodus)."""
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
    """Points down a garment shell at angle a from y_from to y_to and their cumulative arc lengths (Exodus)."""
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
    """Twisted rope: `strands` thin tubes winding round the path (Exodus)."""
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


def knuckles(C, side, amp=0.00055, sig=0.0019):
    """Post step for the kit hand part: soft knuckle bumps on the back of the hand (finger roots + middle joints)."""
    A = C.arm[side]; S = C.S
    ks = []
    for fg in C.fingers[side]:
        ks.append((fg["path"][0], 1.0))
        ks.append((fg["joints"][0][1], 0.7))

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            back = max(0.0, n.dot(A["Xh"]))
            b = sum(w * math.exp(-((p - k).length / (sig * S)) ** 2) for k, w in ks)
            out.append(p + n * (amp * S * min(1.2, b) * back))
        return out
    return post


def hand_with_knuckles(C, side, s_from, amp=0.00055):
    build_forearm_hand(C, side, s_from)
    C.parts[-1]["post"] = knuckles(C, side, amp)


def bare_upper_arm(C, side, sv0, prof, name=None):
    """Bare upper arm: a skin tube along the arm from inside the short sleeve (sv0) to just past the elbow, with a
    deltoid / biceps profile prof = [(t 0..1, radius as a multiple of armR)]; build_forearm_hand continues it."""
    A = C.arm[side]; s = C.s; hd = s["handDims"]; S = C.S
    LU = s["upperArm"]; r0 = hd["armR"]
    X0 = perp(V(0, 0, 1), A["d"]); Y0 = A["d"].cross(X0)
    cg = Cage(); wfn = C.w(["shoulder" + side, "upperArm" + side, "forearm" + side], blend=0.010 * S)
    rings = []
    n = 9
    for i in range(n):
        t = i / (n - 1)
        sv = lerp(sv0 * S, LU + 0.004 * S, t)
        k = table(prof, t)[0]
        c = A["S0"] + A["d"] * sv
        rings.append(cg.ring([section(c, X0, Y0, (r0 * k * 1.06, r0 * k * 1.06, r0 * k * 0.98, r0 * k * 0.98), a, 2.1)
                              for a in ARM12], wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "skin")
    cg.fan(rings[-1], A["S0"] + A["d"] * (LU + 0.010 * S), wfn, "skin")
    C.add(name or ("upperArm" + side), cg, subdiv=0)


def blob_row(cg, pts, nrms, r, wfn, reg, seed=3, jitter=0.35):
    """Shaggy fleece edge: a pointed wool tuft at each path point, sticking out and down at random angles, plus a
    smaller one in between (4-sided tapered tubes: cheap and they read as shag at phone distance)."""
    rnd = random.Random(seed)
    for i, (p, n) in enumerate(zip(pts, nrms)):
        for kk in range(2):
            rr = r * (1 + jitter * (rnd.random() - 0.5)) * (1.0 if kk == 0 else 0.7)
            d = (n * (0.9 + 0.4 * rnd.random()) + V(rnd.uniform(-0.5, 0.5), -0.7 - 0.6 * rnd.random(), rnd.uniform(-0.3, 0.3))).normalized()
            base = p + V(rnd.uniform(-0.4, 0.4) * r, rnd.uniform(-0.3, 0.3) * r, 0)
            ln = rr * (2.2 + 1.4 * rnd.random())
            mid = base + d * ln * 0.5 + V(0, -0.15 * ln, 0)
            tube(cg, [base - d * rr * 0.4, mid, base + d * ln], [rr, rr * 0.75, rr * 0.12], 4, wfn, reg, 0,
                 cap0=True, cap1=True, cap_len=0.3)


# =============================================================================================== Joseph
def build_joseph(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; hipY = s["hipY"]

    # ---- dark-brown hair to the jaw, centre parting, covers the ears
    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, L["brow"] + 0.27 * H), (0.035, L["brow"] + 0.20 * H), (0.07, L["brow"] + 0.13 * H),
                      (0.10, L["brow"] + 0.12 * H), (0.13, L["brow"] + 0.02 * H), (0.155, L["eye"] - 0.06 * H),
                      (0.185, L["nose"] - 0.02 * H), (0.22, L["nose"] - 0.08 * H), (0.27, L["mouth"] - 0.02 * H),
                      (0.36, L["chin"] + 0.04 * H), (0.50, L["chin"] + 0.00 * H)], uu)[0]
    C.hair_rim = rim
    skeleton(C)
    build_head(C, hair_cull(C, rim))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0036, 0.0052, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        t = lerp(t, 0.0050, smoothstep(0.12, 0.22, uu) * smoothstep(L["eye"], L["mouth"], y))
        if uu < 0.12:                                   # the fringe: thinner at its edge, lifting off the forehead
            t = lerp(t, 0.0026, smoothstep(L["brow"] + 0.36 * H, L["brow"] + 0.20 * H, y))
        return t * S

    def plumb(uu):
        return smoothstep(0.11, 0.18, uu) * (1 - 0.30 * smoothstep(0.30, 0.50, uu))
    hair_shell(C, rim, thick, "hair", "hair", plumb=plumb, parting=True, waves=0.0004 * S, NU=30, NV=7, grooves=52,
               groove_amp=0.00034)
    # ---- cream tunic to the knee, sleeveless (a short cap over the shoulder)
    RT = trim_rows(scale_rows(KING_ROBE, k, kx), 0.064, top_drop=0.0052 * S)
    cap = [(0.004, 0.0116), (0.010, 0.0114), (0.018, 0.0110)]
    build_robe(C, RT, cap, None, nf=8, fold_amp=0.0018, sleeve_fold=0.0003, reg="tunic", name="tunic",
               N=24, step=0.0100, sleeve_lip=(0.92, 0.0002, 0.0022))
    C.tunic_rows = C.robe_rows
    for side in "LR":
        bare_upper_arm(C, side, 0.010, [(0.0, 1.20), (0.18, 1.26), (0.45, 1.20), (0.75, 1.08), (1.0, 1.02)])
        hand_with_knuckles(C, side, 0.002)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.101, rows_in=LEG_ROWS_KNEE, rk=0.85)
    # ---- thin brown cord belt (twisted), knot at his left front
    yb = wy - 0.002 * S
    wbelt = C.w(["hips", "spine"])
    cg = Cage()
    loop = [shell_point(C.tunic_rows, yb, 2 * math.pi * j / 40, 0.0006 * S) for j in range(40)]
    rope(cg, loop, 0.0015 * S, wbelt, "belt", closed=True, twist=0.0040 * S, N=3)
    kn = shell_point(C.tunic_rows, yb, math.radians(12), 0.0024 * S)
    blob(cg, kn, 0.0024 * S, 0.0022 * S, 0.0018 * S, wbelt, "belt", 0, NU=8, NV=5)
    wtail = C.w(["hips", ("thighL", 0.02 * S)], blend=0.02 * S)
    for da, ln in ((-0.08, 0.034), (0.06, 0.028)):
        path = [shell_point(C.tunic_rows, yb - 0.002 * S - ln * S * t, math.radians(12) + da * t,
                            (0.0024 + 0.0006 * math.sin(t * math.pi)) * S) for t in [i / 8 for i in range(9)]]
        rope(cg, path, 0.0014 * S, wtail, "belt", twist=0.0040 * S, N=4)
    C.add("belt", cg, subdiv=0)
    # ---- the coat (skinned prop, printed): closed over the chest, opens below the waist, A-line to the knee, wide
    # bell sleeves to mid-forearm; five stripe regions (see the module docstring)
    hemC = 0.068                                     # knee-length (just below the knee)
    base = scale_rows(KING_ROBE, k, kx)
    RO = []
    for y, hw, zf, zb in base:
        fl = smoothstep(wy + 0.004 * S, hemC, y)
        RO.append((y, hw + 0.0030 * S + 0.0150 * fl ** 1.2, zf + 0.0032 * S + 0.0050 * fl, zb - 0.0030 * S - 0.0060 * fl))
    RO = trim_rows(RO, hemC, top_drop=0.0040 * S)
    sleeve_o = [(0.004, 0.0142), (0.014, 0.0144), (0.030, 0.0146), (0.046, 0.0160), (0.058, 0.0182), (0.068, 0.0208),
                (0.076, 0.0226), (0.082, 0.0234)]
    cg = build_robe(C, RO, sleeve_o, None, nf=7, fold_amp=0.0026, sleeve_fold=0.0017, bell_sag=0.0030 * S,
                    reg="coat2", name="coat", solidify=0.0016, keep=True, N=24, step=0.0100)
    cpart = C.parts[-1]
    coat_rows = C.robe_rows
    C.coat_rows = coat_rows
    C.robe_rows = C.tunic_rows
    y_open = wy + 0.006 * S

    def gap(y):
        return math.radians(lerp(4.0, 17.0, smoothstep(y_open, hemC, y) ** 0.85))
    open_front(C, cg, coat_rows, gap, N_=24, y_open=y_open, ramp=0.014)
    # rolled edge (geometry, same stripe regions): up the left opening, round the hem, up the right opening; cuffs.
    # A separate part (not solidified) joined into joseph_coat by build_character.
    ecg = Cage()
    wt = skirt_weights(C); rr = 0.0019 * S
    yt = y_open - 0.016 * S
    ys = [lerp(yt, hemC + rr * 0.6, i / 10) for i in range(11)]
    edgeL = [front_edge(coat_rows, gap, y, 1, off=0.0004 * S) for y in ys]
    edgeR = [front_edge(coat_rows, gap, y, -1, off=0.0004 * S) for y in ys]
    g0 = gap(hemC)
    hemp = [shell_point(coat_rows, hemC + rr * 0.6, g0 + (2 * math.pi - 2 * g0) * j / 37, 0.0004 * S) for j in range(1, 37)]
    path = edgeL + hemp + list(reversed(edgeR))
    tube(ecg, path, [rr] * len(path), 5, wt, "coat2", 0, cap0=True, cap1=True)
    for side in "LR":
        A = C.arm[side]; sv = sleeve_o[-1][0] * S; r = sleeve_o[-1][1] * S
        X0 = perp(V(0, 0, 1), A["d"]); Y0 = A["d"].cross(X0); cc = A["S0"] + A["d"] * (sv - rr * 0.5)
        ring = [cc + (X0 * math.cos(2 * math.pi * j / 24) + Y0 * math.sin(2 * math.pi * j / 24)) * (r + rr * 0.2) for j in range(24)]
        tube(ecg, ring + [ring[0]], [rr] * 25, 5, C.w(["upperArm" + side, "forearm" + side]), "coat2", 0, cap0=False,
             cap1=False)
    # stripes: centre stripe |x| < b over the chest (split by the opening below the waist); panels; back halves +
    # sleeves. Cut planes give straight stripe edges.
    b = 0.0215
    zc0 = sum(table(coat_rows, y)[1] + table(coat_rows, y)[2] for y in (0.12, 0.16, 0.20)) / 6
    SB = 100.0
    C.coat_stripe = dict(b=b, zc0=zc0, SB=SB)

    def stripe(c, n, reg, k_=0):
        if k_ == 1:
            return "coat1" if c.x < 0 else "coat5"
        a = math.degrees(math.atan2(c.x, c.z - zc0))
        if abs(a) >= SB:
            return "coat1" if c.x < 0 else "coat5"
        if abs(c.x) < b and c.z > zc0:
            return "coat3"
        return "coat2" if c.x < 0 else "coat4"
    cpart["cuts"] = [(V(sx * b, 0, 0), V(1, 0, 0)) for sx in (-1, 1)] + [(V(0, 0, zc0), V(1, 0, 0))] + \
        [(V(0, 0, zc0), V(math.cos(math.radians(a)), 0, -math.sin(math.radians(a)))) for a in (SB, -SB)]
    cpart["retag"] = stripe
    cpart["skinprop"] = "coat"

    def edge_stripe(c, n, reg, k_=0):
        sl = sleeve_sv(C, c)
        if sl and sl[1] > 0.050 * S:
            return "coat1" if c.x < 0 else "coat5"
        return stripe(c, n, reg, 0)
    C.add("coatEdge", ecg, subdiv=0, piece_as="coat", skinprop="coat", retag=edge_stripe, cuts=cpart["cuts"],
          post=cpart["post"])
    # front panels below the waist on coatL / coatR
    zfw = table(coat_rows, wy)[1]
    for side, sd in (("L", 1), ("R", -1)):
        p0 = front_edge(coat_rows, gap, wy - 0.004 * S, sd)
        x0 = sd * max(abs(p0.x) + 0.010 * S, table(coat_rows, wy)[0] * 0.45)
        ph = table(coat_rows, hemC + 0.006)
        C.B["coat" + side] = (V(x0, wy - 0.002 * S, zfw + 0.001 * S), V(sd * ph[0] * 0.55, hemC + 0.004, ph[1] + 0.003 * S),
                              "chest")
    for cg_ in (cg, ecg):
        for i, p in enumerate(cg_.v):
            if sleeve_sv(C, p):
                continue
            a = math.atan2(p.x, p.z + 0.001)
            tw = smoothstep(wy + 0.002 * S, wy - 0.030 * S, p.y) * smoothstep(math.radians(88), math.radians(38), abs(a))
            if tw > 0 and p.z > 0:
                cg_.w[i] = mixw((cg_.w[i], 1 - 0.50 * tw), ({"coat" + ("L" if p.x > 0 else "R"): 1.0}, 0.50 * tw))
    C.B["coat"] = (V(0, chestY, zfw - 0.004 * S), V(0, chestY + 0.012 * S, zfw - 0.004 * S), "chest")
    # ---- governor look (hidden props): striped head-cloth (nemes bone) and broad collar (collar bone)
    build_joseph_nemes(C)
    build_joseph_collar(C)


def build_joseph_nemes(C):
    """The Egyptian head-cloth (Exodus' nemes method): hood() drape over the hair with flared wings and lappets on the
    chest, cut into horizontal stripes by planes; stripes alternate nemesA (takes coat2) / nemesB (coat4)."""
    s = C.s; L = C.L; H = C.H; S = C.S
    shY = s["shoulder"][1]; chestY = s["chestY"]
    y_band = L["brow"] + 0.22 * H

    def nrim(u):
        uu = mirror_u(u)
        return table([(0.000, y_band), (0.090, y_band - 0.010 * H), (0.125, L["brow"] + 0.02 * H),
                      (0.150, L["eye"] - 0.10 * H), (0.170, L["mouth"] - 0.10 * H), (0.185, chestY - 0.016 * S),
                      (0.245, chestY - 0.020 * S), (0.262, shY - 0.006 * S), (0.30, shY - 0.004 * S),
                      (0.38, shY - 0.010 * S), (0.44, chestY - 0.014 * S), (0.50, chestY - 0.024 * S)], uu)[0]

    def nthick(u, y):
        uu = mirror_u(u)
        return (0.0018 + 0.0014 * smoothstep(L["brow"], L["top"], y) + 0.0010 * smoothstep(0.15, 0.30, uu)) * S
    stripe_w = 0.0086 * S
    hood(C, "nemes", "nemesA", nrim, nthick, lambda p: {"head": 1.0}, NU=26, NV=8, flare=0.90, body_off=0.0030,
         back_settle=0.80, front_pull=0.36, folds=(14, 0.0004), hem_wave=0.0002, solid=0.0011, loose_top=0.0,
         settle=0.92)
    npart = C.parts[-1]
    lo = chestY - 0.040 * S; hi = L["top"] + 0.014 * S
    cuts = []
    yv = y_band
    while yv > lo:
        cuts.append(yv); yv -= stripe_w
    yv = y_band + stripe_w * 1.25
    while yv < hi:
        cuts.append(yv); yv += stripe_w

    def nemes_reg(c, n, r, k=0):
        if c.y >= y_band:
            i = int(math.floor((c.y - y_band) / stripe_w - 0.25))
            return "nemesB" if i <= 0 or i % 2 == 0 else "nemesA"
        i = int(math.floor((y_band - c.y) / stripe_w))
        return "nemesA" if i % 2 == 0 else "nemesB"
    npart["cuts"] = [(V(0, y, 0), V(0, 1, 0)) for y in cuts]; npart["retag"] = nemes_reg
    npart["rigid"] = "nemes"
    zc = L["zc"]
    C.B["nemes"] = (V(0, y_band, zc), V(0, L["top"] + 0.010 * S, zc), "head")


def build_joseph_collar(C):
    """Broad round collar laid on the tunic by arc length from the neck (Exodus' method): three rings collar1 / collar3
    / collar5 (inner to outer; they take coat1 / coat3 / coat5), raised cords between them, a beaded edge."""
    s = C.s; S = C.S; nb = s["neckBase"]; chestY = s["chestY"]
    rows = C.tunic_rows
    N_ = 32; NR = 6
    cg = Cage(); prof = []
    for j in range(N_):
        a = 2 * math.pi * j / N_
        pts, sl = shell_profile(rows, a, 0.0016 * S, rows[0][0], chestY - 0.045 * S)
        s0 = sl[min(range(len(pts)), key=lambda i: abs(pts[i].y - (nb - 0.0030 * S)))]
        ca = math.cos(a)
        wd = (0.025 * S if ca > 0 else 0.018 * S) * (0.55 + 0.45 * abs(ca)) + 0.004 * S * (1 - abs(ca))
        prof.append((pts, sl, s0, wd))
    rings = []
    for i in range(NR + 1):
        t = i / NR
        rings.append(cg.ring([at_arclen(pts, sl, s0 + wd * t) for pts, sl, s0, wd in prof], None))
    names = ["collar1", "collar1", "collar3", "collar3", "collar5", "collar5"]
    for i, (a, b) in enumerate(zip(rings, rings[1:])):
        cg.bridge(a, b, names[i], 0)
    tor_c = lambda p: V(0, p.y, (table(rows, p.y)[1] + table(rows, p.y)[2]) / 2)
    for t, reg in ((1 / 3, "collar3"), (2 / 3, "collar5")):
        loop = [at_arclen(pts, sl, s0 + wd * t) for pts, sl, s0, wd in prof]
        nrm = [(p - tor_c(p)).normalized() for p in loop]
        loop = [p + n * 0.0010 * S for p, n in zip(loop, nrm)]
        tube(cg, loop + [loop[0]], [0.0008 * S] * (len(loop) + 1), 3, None, reg, 0, cap0=False, cap1=False)
    C.add("collar", cg, subdiv=0, solidify=0.0010 * S, rigid="collar")
    zf = table(rows, chestY)[1]
    C.B["collar"] = (V(0, nb - 0.004 * S, zf), V(0, chestY - 0.016 * S, zf + 0.002 * S), "chest")


# =============================================================================================== the brother
def build_brother(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; hipY = s["hipY"]
    cb = L["brow"] + 0.30 * H

    # ---- short black curly hair (Boaz's method), ears show
    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb + 0.002 * S), (0.10, cb + 0.001 * S), (0.15, cb - 0.006 * S), (0.18, L["eye"] + 0.06 * H),
                      (0.205, L["eye"] - 0.02 * H), (0.24, L["eye"] + 0.10 * H), (0.30, L["eye"] - 0.02 * H),
                      (0.38, L["chin"] + 0.04 * H), (0.50, L["chin"] - 0.04 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S:
            return True
        return p.y > rim(u) + 0.0050 * S and (uu > 0.12 or p.y > cb + 0.006 * S)
    C.hair_rim = rim
    skeleton(C)
    build_head(C, cull, ears=ears_spec(C))

    def thick(u, y):
        return (0.0028 + 0.0008 * smoothstep(L["eye"], L["top"], y)) * S

    def curls(u, y):
        rh = 0.0050 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0009 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh)) \
            * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 30 + ph)))
    hair_shell(C, rim, thick, "hair", "hair", plumb=None, tuck_front=0.17, grooves=0, curls=curls, NU=26, NV=5)
    # short full black beard + moustache
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.068 * H), (0.07, L["mouth"] + 0.005 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.01 * H), (0.20, L["eye"] - 0.14 * H), (0.245, L["eye"] - 0.02 * H)]
    bot = [(0.00, L["chin"] - 0.10 * H), (0.06, L["chin"] - 0.09 * H), (0.12, L["chin"] - 0.05 * H),
           (0.17, L["chin"] + 0.02 * H), (0.21, L["mouth"] - 0.04 * H), (0.245, L["nose"] - 0.04 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0034, 0.0020, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0048 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0010 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 34 + ph))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.10 * H, reg="hair", solid=0.0030)
    moustache(C, "moustache", L["mouth"] + 0.085 * H, 0.62 * s["hw"], 0.07 * H, 0.03 * H, 0.0022 * S, reg="hair",
              off=0.0016)
    # ---- rough rust tunic to the knee, short sleeves; bare arms
    RT = trim_rows(scale_rows(KING_ROBE, k, kx), 0.098)
    RT = [(y, hw * (1 - 0.06 * smoothstep(0.17, 0.10, y)), zf, zb) for y, hw, zf, zb in RT]
    sl_t = [(0.004, 0.0128), (0.012, 0.0126), (0.022, 0.0120), (0.030, 0.0118)]
    build_robe(C, RT, sl_t, None, nf=7, fold_amp=0.0022, sleeve_fold=0.0012, reg="tunic", name="tunic", N=28,
               step=0.0090)
    C.tunic_rows = C.robe_rows
    for side in "LR":
        bare_upper_arm(C, side, 0.022, [(0.0, 1.50), (0.30, 1.40), (0.60, 1.30), (0.85, 1.12), (1.0, 1.02)])
        hand_with_knuckles(C, side, 0.002)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.101, rows_in=LEG_ROWS_KNEE, rk=0.95)
    # ---- wide leather belt on the tunic
    waist_band(C, "belt", "belt", wy - 0.0072 * S, wy + 0.0072 * S, 0.0010 * S, bulge=0.0010 * S)
    # ---- dark-olive sheepskin vest: sleeveless, open front, to the hip, shaggy edge
    RV = []
    for y, hw, zf, zb in RT:
        RV.append((y, hw + 0.0032 * S, zf + 0.0034 * S, zb - 0.0032 * S))
    hemV = hipY - 0.016 * S
    RV = trim_rows(RV, hemV, top_drop=0.0010 * S)
    stub = [(0.004, 0.0136), (0.008, 0.0136)]
    cg = build_robe(C, RV, stub, None, nf=8, fold_amp=0.0006, sleeve_fold=0.0, reg="vest", name="vest", solidify=0.0016,
                    keep=True, N=32, step=0.0080, sleeve_lip=None)
    vest_rows = C.robe_rows; C.robe_rows = C.tunic_rows
    keep = [i for i in range(len(cg.f)) if cg.pc[i] != 1]               # sleeveless: drop the sleeve stubs
    cg.f = [cg.f[i] for i in keep]; cg.reg = [cg.reg[i] for i in keep]; cg.pc = [cg.pc[i] for i in keep]

    def vgap(y):
        return math.radians(lerp(9.0, 17.0, smoothstep(nb, hemV, y) ** 0.8))
    open_front(C, cg, vest_rows, vgap)
    # fleece edge: lumps along both front edges and the hem
    cg2 = Cage(); wv = C.w(["chest", "spine", "hips", ("shoulderL", 0.012 * S), ("shoulderR", 0.012 * S)])
    for sd in (1, -1):
        ys = [lerp(vest_rows[0][0] - 0.006 * S, hemV + 0.001 * S, i / 26) for i in range(27)]
        pts = [front_edge(vest_rows, vgap, y, sd, off=0.0004 * S) for y in ys]
        nrm = [V(p.x, 0, p.z).normalized() for p in pts]
        blob_row(cg2, pts, nrm, 0.0018 * S, wv, "vest", seed=5 + sd, jitter=0.6)
    hw_, zf_, zb_ = table(vest_rows, hemV + 0.001 * S)
    pts = []; nrm = []
    for j in range(72):
        a = vgap(hemV) + (2 * math.pi - 2 * vgap(hemV)) * j / 71
        p = shell_point(vest_rows, hemV + 0.0016 * S, a, 0.0002 * S)
        pts.append(p); nrm.append(V(p.x, -0.012, p.z).normalized())
    blob_row(cg2, pts, nrm, 0.0018 * S, wv, "vest", seed=9, jitter=0.6)
    C.add("fleece", cg2, subdiv=0)
    # ---- sling bag: strap from his left shoulder across the chest to a pouch at his right hip (bag bone)
    zf_c = table(vest_rows, chestY)[1]
    yp = hipY - 0.006 * S; ap = math.radians(-30)
    ps = shell_point(C.tunic_rows, yp, ap, 0.0)
    zc_t = (table(C.tunic_rows, yp)[1] + table(C.tunic_rows, yp)[2]) / 2
    nn = V(ps.x, 0, ps.z - zc_t).normalized()
    pc_ = ps + nn * 0.0085 * S
    C.B["bag"] = (V(-0.010 * S, chestY - 0.010 * S, zf_c + 0.004 * S), pc_ + V(0, -0.010 * S, 0), "chest")
    wstrap = C.w(["chest", "spine", ("shoulderL", 0.012 * S)])
    wbag = C.w(["bag", "hips"], blend=0.020 * S)
    path = []
    for i in range(17):
        t = i / 16
        y = lerp(shY + 0.0010 * S, yp + 0.014 * S, t)
        ang = math.radians(lerp(78.0, -28.0, t))
        rows_ = vest_rows if y > hemV + 0.002 * S else C.tunic_rows
        path.append(shell_point(rows_, y, ang, (0.0034 if rows_ is vest_rows else 0.0040) * S))
    nrm = [V(p.x, 0, p.z - zc_t).normalized() for p in path]
    cg3 = Cage()
    strip(cg3, path, nrm, [0.0030 * S] * len(path), 0.0010 * S, wstrap, "bag", 0)
    tg = V(0, 1, 0).cross(nn).normalized()
    M = Matrix((tg, V(0, 1, 0), nn)).transposed()
    blob(cg3, pc_, 0.0240 * S, 0.0210 * S, 0.0068 * S, wbag, "bag", 0, NU=14, NV=9, ax=M)
    blob(cg3, pc_ + V(0, 0.0110 * S, 0) + nn * 0.0052 * S, 0.0236 * S, 0.0070 * S, 0.0030 * S, wbag, "bag", 0, NU=12,
         NV=6, ax=M)
    C.add("bag", cg3, subdiv=0)


# =============================================================================================== Pharaoh
def build_pharaoh(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; hipY = s["hipY"]
    tilt = math.radians(8.0)
    y_cb = L["brow"] + 0.16 * H                     # crown base low on the forehead

    def cull(p):
        if p.y < nb - 0.0060 * S:
            return True
        return p.y > y_cb + 0.006 * S + (p.z - L["zc"]) * math.tan(tilt)
    skeleton(C)
    build_head(C, cull, ears=ears_spec(C))
    # ---- bare torso with a round belly (a skin "robe" whose sleeves are the upper arms)
    RB = scale_rows(PHARAOH_TORSO, k, kx * 1.16)
    RB = resample_rows(RB, [RB[0][0] - (RB[0][0] - RB[-1][0]) * i / 18 for i in range(19)])
    yb0 = wy + 0.002 * S
    RB = [(y, hw + 0.0080 * S * math.exp(-((y - yb0) / (0.028 * S)) ** 2),
           zf + 0.0012 * S + 0.0190 * S * math.exp(-((y - yb0) / (0.024 * S)) ** 2),
           zb - 0.0012 * S - 0.0036 * S * math.exp(-((y - yb0) / (0.026 * S)) ** 2)) for y, hw, zf, zb in RB]
    arm = [(0.004, 0.0140), (0.012, 0.0140), (0.022, 0.0130), (0.032, 0.0118), (0.042, 0.0106), (0.050, 0.0098),
           (0.056, 0.0094), (0.062, 0.0092)]
    build_robe(C, RB, arm, None, nf=12, fold_amp=0.0, sleeve_fold=0.0, reg="skin", name="torso", sleeve_lip=None,
               N=36, step=0.0060)
    C.torso_rows = C.robe_rows
    tpart = C.parts[-1]
    for side in "LR":
        hand_with_knuckles(C, side, 0.004)
    old_post = tpart["post"]

    def tpost(pts, nrm):
        out = old_post(pts, nrm); res = []
        for p, q, n in zip(pts, out, nrm):
            if p.z > 0 and not sleeve_sv(C, p):
                for sx in (-1, 1):       # soft chest
                    q = q + n * 0.0008 * S * math.exp(-((p.x - sx * 0.016 * S) / (0.011 * S)) ** 2 - ((p.y - (chestY - 0.006 * S)) / (0.008 * S)) ** 2)
                q = q - n * 0.0006 * S * math.exp(-(p.x / (0.0020 * S)) ** 2 - ((p.y - (yb0 - 0.002 * S)) / (0.0020 * S)) ** 2)  # navel
            res.append(q)
        return res
    tpart["post"] = tpost
    # belly bone (jiggle): the front of the belly follows it
    zfb = table(C.torso_rows, yb0)[1]
    C.B["belly"] = (V(0, yb0 + 0.010 * S, zfb - 0.020 * S), V(0, yb0 + 0.010 * S, zfb - 0.002 * S), "spine")
    cgT = tpart["cage"]
    for i, p in enumerate(cgT.v):
        if sleeve_sv(C, p) or p.z < 0:
            continue
        wbl = 0.95 * math.exp(-((p.y - yb0) / (0.024 * S)) ** 2 - (p.x / (0.034 * S)) ** 2) * smoothstep(0.0, zfb, p.z)
        if wbl > 0.02:
            cgT.w[i] = mixw((cgT.w[i], 1 - wbl), ({"belly": 1.0}, wbl))
    # ---- pleated white kilt (sits under the belly), gold belt, blue apron with gold bars (apron1)
    hem = 0.098 * k + 0.004
    ytop = wy - 0.014 * S
    t0 = table(C.torso_rows, ytop)
    KR = [(ytop + 0.0030 * S, t0[0] + 0.0012 * S, t0[1] + 0.0010 * S, t0[2] - 0.0012 * S),
          (ytop, t0[0] + 0.0016 * S, t0[1] + 0.0016 * S, t0[2] - 0.0016 * S),
          (hipY, 0.0360 * kx, max(0.0176 * kx, table(C.torso_rows, min(hipY, C.torso_rows[0][0]))[1] + 0.002 * S), -0.0160 * kx),
          (hipY - 0.025, 0.0396 * kx, 0.0200 * kx, -0.0174 * kx),
          (lerp(hipY - 0.025, hem, 0.5), 0.0470 * kx, 0.0236 * kx, -0.0194 * kx), (hem, 0.0650 * kx, 0.0290 * kx, -0.0220 * kx)]
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
    waist_band(C, "belt", "gold", ytop - 0.0040 * S, ytop + 0.0030 * S, 0.0010 * S, bulge=0.0010 * S, N=48)
    y0a, y1a = ytop - 0.0040 * S, hem - 0.004
    zfa0 = table(KR, y0a)[1]
    C.B["apron1"] = (V(0, y0a, zfa0 + 0.001 * S), V(0, y1a, table(KR, y1a)[1] + 0.004 * S), "hips")
    wap = C.w(["hips", "apron1"], blend=0.010 * S)

    def wapron(p):
        t = smoothstep(y0a, y0a - 0.020 * S, p.y)
        return mixw(({"hips": 1.0}, 1 - t), ({"apron1": 1.0}, t)) if t < 1 else {"apron1": 1.0}
    cg = Cage(); NC = 6; NRa = 14
    grid = []
    for j in range(NRa + 1):
        y = lerp(y0a, y1a, j / NRa)
        hwA = lerp(0.0124, 0.0160, j / NRa) * S
        zf_ = table(KR, min(y, KR[0][0]))[1]
        row = []
        for i in range(NC + 1):
            x = lerp(-hwA, hwA, i / NC)
            row.append(V(x, y, zf_ + 0.0026 * S - 0.0008 * S * (x / (hwA + 1e-9)) ** 2 + 0.0012 * S * (j / NRa)))
        grid.append(cg.ring(row, wapron))
    for a, b in zip(grid, grid[1:]):
        cg.bridge(a, b, "apron", 0, closed=False)
    bars = [(lerp(y0a, y1a, 0.70), lerp(y0a, y1a, 0.76)), (lerp(y0a, y1a, 0.90), lerp(y0a, y1a, 0.96))]

    def apron_reg(c, n, r, k=0):
        return "gold" if any(b1 <= c.y <= b0 for b0, b1 in bars) else "apron"
    C.add("apron", cg, subdiv=0, solidify=0.0010 * S, cuts=[(V(0, y, 0), V(0, 1, 0)) for b in bars for y in b],
          retag=apron_reg)
    # ---- legs: bare shins, gold sandals
    for side in "LR":
        build_leg(C, side, 0.0, "gold", regfn2=sandals_as("gold", S), top_y=0.101, rows_in=LEG_ROWS_KNEE, rk=0.85)
    # ---- broad gold collar on the shoulders: bands, raised cords, beaded edge
    N_ = 48; NR = 7
    wcol = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S)])
    cg = Cage(); rings = []
    prof = []
    for j in range(N_):
        a = 2 * math.pi * j / N_
        pts, sl = shell_profile(C.torso_rows, a, 0.0012 * S, C.torso_rows[0][0], chestY - 0.045 * S)
        s0 = sl[min(range(len(pts)), key=lambda i: abs(pts[i].y - (nb - 0.0030 * S)))]
        ca = math.cos(a)
        wd = (0.032 * S if ca > 0 else 0.022 * S) * (0.55 + 0.45 * abs(ca)) + 0.004 * S * (1 - abs(ca))
        prof.append((pts, sl, s0, wd))
    for i in range(NR + 1):
        t = i / NR
        rings.append(cg.ring([at_arclen(pts, sl, s0 + wd * t) for pts, sl, s0, wd in prof], wcol))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "collar", 0)
    tor_c = lambda p: V(0, p.y, (table(C.torso_rows, p.y)[1] + table(C.torso_rows, p.y)[2]) / 2)
    C.add("collar", cg, subdiv=0, solidify=0.0022 * S)
    cg = Cage()                      # raised cords + beads: separate part so the plain band is solidified alone,
    for t in (0.36, 0.72):
        loop = [at_arclen(pts, sl, s0 + wd * t) for pts, sl, s0, wd in prof]
        nrm = [(p - tor_c(p)).normalized() for p in loop]
        loop = [p + n * 0.0022 * S for p, n in zip(loop, nrm)]
        tube(cg, loop + [loop[0]], [0.0012 * S] * (len(loop) + 1), 5, wcol, "collar", 0, cap0=False, cap1=False)
    for j, (pts, sl, s0, wd) in enumerate(prof):
        if j % 3:
            continue
        p = at_arclen(pts, sl, s0 + wd + 0.0016 * S)
        n = (p - tor_c(p)).normalized()
        blob(cg, p + n * 0.0010 * S, 0.0016 * S, 0.0020 * S, 0.0011 * S, wcol, "collar", 0, NU=6, NV=3)
    C.add("collarBeads", cg, subdiv=0, piece_as="collar")      # same printed piece as the band (no inner outlines)
    # ---- gold arm-bands and bracelets
    cg = Cage()
    for side in "LR":
        A = C.arm[side]; d = A["d"]; X0 = perp(V(0, 0, 1), d); Y0 = d.cross(X0)
        sv = 0.036 * S; r = table([(a * S, b * S) for a, b in arm], sv)[0] + 0.0004 * S
        c = A["S0"] + d * sv
        pts = [c + (X0 * math.cos(2 * math.pi * j / 20) + Y0 * math.sin(2 * math.pi * j / 20)) * r for j in range(20)]
        band_loop(cg, pts, [(p - c).normalized() for p in pts], [d] * 20, 0.0034 * S, 0.0022 * S, C.w(["upperArm" + side]),
                  "gold", 0)
        W = A["W"]; c = W - d * 0.0060 * S; hd = s["handDims"]; r = hd["wristW"] * 0.62
        pts = [c + (X0 * math.cos(2 * math.pi * j / 20) * 1.05 + Y0 * math.sin(2 * math.pi * j / 20) * 0.95) * r for j in range(20)]
        band_loop(cg, pts, [(p - c).normalized() for p in pts], [d] * 20, 0.0030 * S, 0.0020 * S,
                  C.w(["forearm" + side, "hand" + side], blend=0.006 * S), "gold", 0)
    C.add("bands", cg, subdiv=0)
    # ---- the double crown: a red cap round the head, a tall rounded white crown rising out of it, a gold band
    wh = C.w(["head"])
    cg = Cage()
    red = head_lathe(C, y_cb, [(0.0, 1.04), (0.005 * S, 1.08), (0.012 * S, 1.11), (0.019 * S, 1.12), (0.024 * S, 1.10),
                               (0.0275 * S, 1.05), (0.0298 * S, 0.97), (0.0312 * S, 0.88), (0.0318 * S, 0.80)], 32, wh, "crownRed", 0, cg,
                     extra_x=0.0016 * S, extra_f=0.0016 * S, extra_b=0.0020 * S, e=2.3, tilt=tilt)
    head_lathe(C, y_cb, [(0.024 * S, 0.88), (0.030 * S, 1.02), (0.035 * S, 1.09), (0.040 * S, 1.07), (0.044 * S, 0.98),
                         (0.048 * S, 0.82), (0.051 * S, 0.62), (0.053 * S, 0.46), (0.0548 * S, 0.40), (0.0566 * S, 0.40),
                         (0.0584 * S, 0.32), (0.0597 * S, 0.18), (0.0603 * S, 0.0)], 32, wh, "crownWhite", 0, cg,
               extra_x=0.0016 * S, extra_f=0.0016 * S, extra_b=0.0020 * S, e=2.3, tilt=tilt)
    C.add("crown", cg, subdiv=1)
    cg = Cage()
    piv = red["pivot"]; R = red["R"]
    pts = []
    for j in range(40):
        a = 2 * math.pi * j / 40
        q = V(se(math.sin(a), 2.3) * red["rx"] * 1.07, y_cb + 0.0030 * S, red["zc"] + se(math.cos(a), 2.3) * red["rz"] * 1.07)
        pts.append(piv + R @ (q - piv))
    cen = piv + R @ (V(0, y_cb + 0.0030 * S, red["zc"]) - piv)
    nrm = [(p - cen).normalized() for p in pts]
    band_loop(cg, pts, nrm, [R @ V(0, 1, 0)] * 40, 0.0024 * S, 0.0010 * S, wh, "gold", 0)
    # cobra on the front of the band
    fp = pts[0] + nrm[0] * 0.0010 * S
    path = [fp + V(0, -0.0016 * S, -0.0004 * S), fp + V(0, 0.0004 * S, 0.0012 * S), fp + V(0, 0.0018 * S, 0.0014 * S)]
    tube(cg, path, [0.0013 * S, 0.0012 * S, 0.0011 * S], 6, wh, "gold", 0, cap0=True, cap1=False)
    hc = path[-1] + V(0, 0.0006 * S, 0.0004 * S)
    blob(cg, hc, 0.0026 * S, 0.0020 * S, 0.0010 * S, wh, "gold", 0, NU=8, NV=5)
    blob(cg, hc + V(0, 0.0010 * S, 0.0014 * S), 0.0010 * S, 0.0008 * S, 0.0012 * S, wh, "gold", 0, NU=6, NV=4)
    C.add("crownBand", cg, subdiv=0)
    # ---- ceremonial chin beard (lapis blue, braided)
    cg = Cage(); wj = C.w(["jaw"])
    cz = C.head.at(0.0, L["chin"] + 0.04 * H).z
    path = [V(0, L["chin"] + 0.06 * H, cz - 0.0045 * S), V(0, L["chin"] - 0.10 * H, cz - 0.0010 * S),
            V(0, L["chin"] - 0.16 * H, cz + 0.0002 * S), V(0, L["chin"] - 0.22 * H, cz + 0.0024 * S)]
    path = [cr_open(path, i / 10) for i in range(11)]
    rr = [(0.0030 - 0.0006 * (i / 10) ** 1.5) * S * (1 + 0.12 * math.cos(i * math.pi)) for i in range(11)]
    tube(cg, path, rr, 8, wj, "beard", 0, cap0=True, cap1=True, cap_len=0.9)
    C.add("fbeard", cg, subdiv=0)


# =============================================================================================== Jacob
def build_jacob(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]; hipY = s["hipY"]

    # ---- thin white hair (shows at the temples under the shawl)
    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, L["brow"] + 0.42 * H), (0.06, L["brow"] + 0.40 * H), (0.10, L["brow"] + 0.28 * H),
                      (0.13, L["brow"] + 0.08 * H), (0.155, L["eye"] - 0.04 * H), (0.19, L["nose"] - 0.06 * H),
                      (0.23, L["chin"] - 0.16 * H), (0.30, nb + 0.002 * S), (0.40, nb - 0.004 * S),
                      (0.50, nb - 0.008 * S)], uu)[0]
    C.hair_rim = rim
    skeleton(C)
    build_head(C, hair_cull(C, rim))

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0030, 0.0040, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
        t = lerp(t, 0.0056, smoothstep(0.12, 0.24, uu) * smoothstep(L["brow"], L["mouth"], y))
        if uu < 0.12:
            t = lerp(t, 0.0016, smoothstep(L["brow"] + 0.46 * H, L["brow"] + 0.38 * H, y))
        return t * S
    hair_shell(C, rim, thick, "hair", "hair", plumb=lambda uu: smoothstep(0.12, 0.20, uu), parting=False,
               waves=0.0009 * S, NU=30, NV=7, grooves=60, groove_amp=0.00040)
    # ---- beard over the cheeks + a long white beard hanging over the chest, a drooping moustache
    top = [(0.00, L["mouth"] - 0.075 * H), (0.035, L["mouth"] - 0.060 * H), (0.07, L["mouth"] + 0.030 * H),
           (0.10, L["nose"] - 0.030 * H), (0.15, L["nose"] + 0.040 * H), (0.20, L["eye"] - 0.12 * H),
           (0.225, L["eye"] - 0.06 * H)]
    bot = [(0.00, L["chin"] - 0.22 * H), (0.08, L["chin"] - 0.20 * H), (0.14, L["chin"] - 0.10 * H),
           (0.19, L["chin"] + 0.06 * H), (0.21, L["mouth"] - 0.02 * H), (0.225, L["nose"] - 0.06 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0076, 0.0030, smoothstep(0.05, 0.225, uu)) * S
        t *= smoothstep(0.0, 0.18, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0006 * S

    def bcurls(u, y):
        return 0.0009 * S * math.cos(2 * math.pi * (u * 34)) * smoothstep(L["mouth"], L["chin"], y)
    build_beard(C, top, bot, bthick, bcurls, 0.225, L["chin"] - 0.22 * H, reg="hair")
    moustache(C, "moustache", L["mouth"] + 0.090 * H, 0.66 * s["hw"], 0.16 * H, -0.02 * H, 0.0027 * S, reg="hair",
              off=0.0016)
    # ---- grey-brown robe to the ankle, long sleeves
    RT = scale_rows(KING_ROBE, k, kx)
    RT = [(y, hw * (1 - 0.05 * smoothstep(0.17, 0.02, y)), zf, zb) for y, hw, zf, zb in RT]
    sleeve_t = [(0.004, 0.0130), (0.014, 0.0126), (0.030, 0.0116), (0.048, 0.0110), (0.062, 0.0110), (0.074, 0.0114),
                (0.082, 0.0118), (0.088, 0.0120)]
    build_robe(C, RT, sleeve_t, None, nf=8, fold_amp=0.0026, sleeve_fold=0.0015, bell_sag=0.0012 * S, reg="robe",
               name="robe", N=28, step=0.0090)
    C.tunic_rows = C.robe_rows
    for side in "LR":
        hand_with_knuckles(C, side, 0.026)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.030)
    # ---- brown cloth belt with a knot and tails
    waist_band(C, "belt", "belt", wy - 0.0070 * S, wy + 0.0064 * S, 0.0010 * S, bulge=0.0012 * S)
    belt_tie(C, "beltTie", "belt", 0.0110 * S, wy - 0.001 * S, [(-0.0014, wy - 0.046 * S), (0.0022, wy - 0.058 * S)], 0.0026)
    # ---- the long beard (Moses' method, skinned to jaw / head / chest instead of beard bones)
    zf_chin = C.head.at(0.0, L["chin"] + 0.02 * H).z
    y_top = L["chin"] + 0.05 * H; y_tip = chestY - 0.004 * S
    neck_zf = s["neck"][1]

    def zback(y):
        z = neck_zf + 0.0012 * S
        if y < C.tunic_rows[0][0]:
            z = max(z, table(C.tunic_rows, y)[1] + 0.0042 * S)
        return z

    def bt(y):
        return min(1.0, max(0.0, (y_top - y) / (y_top - y_tip)))

    def wbeard(p):
        t = bt(p.y); wt = smoothstep(0.30, 0.0, t)
        lo = {"head": 0.70, "neck": 0.15, "chest": 0.15}
        return mixw(({"jaw": 0.60, "head": 0.40}, wt), (lo, 1 - wt)) if wt > 0 else lo
    cg = Cage(); NB = 16; NR = 12
    W0 = 0.82 * s["hw"]
    for j in range(NR + 1):
        t = j / NR; y = lerp(y_top, y_tip, t ** 0.92)
        W = W0 * (1.0 + 0.10 * math.sin(math.pi * min(1.0, t * 1.3))) * max(0.0, 1 - t ** 2.4) ** 0.50
        W = max(W, 0.0010 * S)
        zb_ = zback(y); zf_ = lerp(zf_chin + 0.0060 * S, zb_ + 0.0052 * S, t ** 1.2) + 0.0024 * S * math.sin(math.pi * t)
        zc_ = (zf_ + zb_) / 2; rd = max(0.0008 * S, (zf_ - zb_) / 2)
        row = []
        for i in range(NB):
            a = 2 * math.pi * i / NB
            x = se(math.sin(a), 2.4) * W
            yy = y + (0.0026 * S * math.cos(2 * math.pi * x / (W0 * 1.1)) * smoothstep(0.75, 1.0, t))
            row.append(V(x, yy, zc_ + se(math.cos(a), 2.4) * rd))
        rows_ = cg.ring(row, wbeard)
        if j:
            cg.bridge(prev, rows_, "hair", 0)
        else:
            first = rows_
        prev = rows_
    cg.fan(list(reversed(first)), V(0, y_top + 0.004 * S, (zback(y_top) + zf_chin) / 2), wbeard, "hair", 0)
    cg.fan(prev, V(0, y_tip - 0.003 * S, zback(y_tip) + 0.003 * S), wbeard, "hair", 0)

    def bpost(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            t = bt(p.y)
            g = 0.00055 * S * math.cos(2 * math.pi * p.x / (0.0040 * S) + 3.0 * t) * smoothstep(0.02, 0.15, t)
            sway = 0.0008 * S * math.sin(t * 2.6 * math.pi) * t
            out.append(p + n * g + V(sway, 0, 0))
        return out
    C.add("beardLong", cg, post=bpost, subdiv=1)
    # ---- cream shawl over head and shoulders, back drape (shawl1 / shawl2), Naomi's method
    zbh = C.head.at(0.5, L["chin"] + 0.15 * H).z
    zb_bl = table(C.robe_rows, chestY)[2]
    C.B["shawl1"] = (V(0, L["chin"] + 0.10 * H, zbh - 0.004 * S), V(0, chestY - 0.004 * S, zb_bl - 0.008 * S), "head")
    C.B["shawl2"] = (V(0, chestY - 0.004 * S, zb_bl - 0.008 * S),
                     V(0, wy + 0.008 * S, table(C.robe_rows, wy)[2] - 0.006 * S), "shawl1")

    def srim(u):
        uu = mirror_u(u)
        return table([(0.000, L["brow"] + 0.26 * H), (0.050, L["brow"] + 0.24 * H), (0.090, L["brow"] + 0.16 * H),
                      (0.125, L["eye"] + 0.04 * H), (0.160, L["nose"] - 0.04 * H), (0.190, L["mouth"] - 0.10 * H),
                      (0.205, L["chin"] - 0.14 * H), (0.214, wy - 0.004 * S), (0.235, wy - 0.010 * S),
                      (0.262, wy + 0.004 * S), (0.29, chestY - 0.030 * S), (0.33, chestY - 0.034 * S),
                      (0.38, chestY - 0.030 * S), (0.45, wy + 0.012 * S), (0.50, wy + 0.008 * S)], uu)[0]

    def sthick(u, y):
        uu = mirror_u(u)
        return (0.0040 + 0.0018 * smoothstep(L["brow"], L["top"], y) + 0.0020 * smoothstep(0.15, 0.30, uu)) * S
    hood(C, "shawl", "shawl", srim, sthick, hood_weights(C, ["shawl1", "shawl2", ("chest", None)], arm_reach=0.016),
         NU=52, NV=22, flare=0.22, body_off=0.0030, front_pull=0.55, folds=(9, 0.0032), hem_wave=0.0018,
         solid=0.0024)
    # ---- walking stick in the right fist, planted on the ground (rigid, stick bone), a knob on top
    g = grip_point(C, "R", 0.0030)
    cg = Cage()
    top = g + V(0, 0.036 * S, 0.001 * S)
    bot = V(g.x - 0.004 * S, 0.0030, g.z + 0.010 * S)
    path = []
    for i in range(15):
        t = i / 14
        p = bot.lerp(top, t)
        p += V(0.0012 * S * math.sin(t * 7.0), 0, 0.0008 * S * math.sin(t * 5.0 + 1.0))
        path.append(p)
    rads = [0.0026 * S + 0.0008 * S * (i / 14) for i in range(15)]
    tube(cg, path, rads, 8, None, "stick", 0, cap0=True, cap1=False, cap_len=0.4)
    blob(cg, top + V(0.0004 * S, 0.0034 * S, 0), 0.0050 * S, 0.0054 * S, 0.0048 * S, None, "stick", 0, NU=10, NV=6)
    for t in (0.20, 0.46, 0.74):
        p = cr_open(path, t)
        blob(cg, p + V(0.0026 * S, 0, 0.0008 * S), 0.0011 * S, 0.0016 * S, 0.0011 * S, None, "stick", 0, NU=6, NV=4)
    C.add("stick", cg, subdiv=0, rigid="stick")
    C.B["stick"] = (g.copy(), top.copy(), "handR")


# =============================================================================================== sculpt polish
# 2026-11-15 owner pass "精致、多面、儿童喜爱、精修": detail on top of the builders above. Rules kept: no bone added,
# moved or renamed (the polish only adds geometry weighted to existing bones); every new part reuses an existing
# printed piece (piece_as) and an existing or anchored region, so the sheet gets no new colourable cell: small new
# parts print as detail lines inside their neighbour (make_sheet.py `detailOf`).
def sculpt_lock(cg, ctrl, w0, th, wfn, NS=12, N=8, reg="hair", pc=0, tip=0.15, root=0.60, flat=0.35, h0=0.60,
                hend=0.70):
    """One sculpted lock (Gabriel's method, pipeline/ga_character.py `lock`): a flattened tapering tube along
    ctrl = [(point, outward normal)]; w0 half width, th height above its base line; flat underside."""
    P = [c[0] for c in ctrl]; Nn = [c[1] for c in ctrl]
    rings = []
    for i in range(NS + 1):
        t = i / NS
        p = cr_open(P, t); n = cr_open(Nn, t).normalized()
        T = (cr_open(P, min(1.0, t + 0.02)) - cr_open(P, max(0.0, t - 0.02))).normalized()
        A = perp(n, T); Bv = T.cross(A)
        w = w0 * (root + (1 - root) * math.sin(math.pi / 2 * min(1.0, t / 0.30))) * (1 - (1 - tip) * smoothstep(0.60, 1.0, t))
        h = th * (h0 + (1 - h0) * math.sin(math.pi / 2 * min(1.0, t / 0.35))) * (1 - hend * smoothstep(0.70, 1.0, t))
        ring = []
        for k in range(N):
            a = 2 * math.pi * k / N
            sa = math.sin(a)
            ring.append(p + Bv * (math.cos(a) * w) + A * (sa * h if sa >= 0 else sa * h * flat))
        rings.append(cg.ring(ring, wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(list(reversed(rings[0])), P[0] - (P[1] - P[0]).normalized() * w0 * 0.3, wfn, reg, pc)
    cg.fan(rings[-1], P[-1] + (P[-1] - P[-2]).normalized() * w0 * (0.25 + 0.6 * tip), wfn, reg, pc)


def part_named(C, name):
    return next(p for p in C.parts if p["name"] == name)


def hair_point(C, uu, y, sd):
    """Point on the hair shell's outer surface (before grooves) at mirrored azimuth uu on side sd, + outward normal."""
    L = C.L
    u = uu if sd > 0 else (1.0 - uu) % 1.0
    y = max(y, C.hair_rim(u) + 0.0008 * C.S)
    p = C.hair_outer(u, min(y, L["top"] - 0.0004))
    c = V(0, min(p.y, L["eye"]), L["zc"])
    return p, (p - c).normalized()


def strap_rings(cg):
    """Constant-y rings of a build_leg cage (16 points each), bottom ring last: [(y, [indices])]."""
    out = []; i = 0
    while i + 16 <= len(cg.v):
        ys = [cg.v[i + k].y for k in range(16)]
        if max(ys) - min(ys) > 1e-7:
            break
        out.append((ys[0], list(range(i, i + 16)))); i += 16
    return out


def sandal_straps(C, reg):
    """Raised sandal straps exactly on the painted bands of sandal_regfn (ankle strap, instep strap, toe strap) and a
    sole rim: the sandals read as real straps at phone distance. Same printed piece as the leg."""
    S = C.S
    for side in "LR":
        pt = part_named(C, "leg" + side); lc = pt["cage"]
        rings = strap_rings(lc)
        if len(rings) < 4:
            continue
        ank = C.B["foot" + side][0]
        wleg = C.w(["shin" + side, "foot" + side, "toe" + side])
        cg = Cage()

        def ctr(idx):
            return sum((lc.v[k] for k in idx), V()) / len(idx)
        # ankle strap: the ring nearest y = 0.0168 S, pushed out
        y_a = 0.0168 * S
        ya, ia = min(rings, key=lambda r: abs(r[0] - y_a))
        if abs(ya - y_a) < 0.004 * S:
            c = ctr(ia)
            loop = [lc.v[k] + (lc.v[k] - c).normalized() * 0.0007 * S for k in ia]
            loop = [V(p.x, y_a, p.z) for p in loop]
            tube(cg, loop + [loop[0]], [(0.0016 * S, 0.0008 * S)] * 17, 6, wleg, reg, 0, cap0=False, cap1=False,
                 ref=V(0, 1, 0))
        # over-the-foot straps: where each foot ring crosses the plane z = ank.z + dz (both sides), up and over
        for dz, ymax in ((0.0195 * S, 0.0105 * S), (0.0085 * S, 0.0150 * S)):
            z0 = ank.z + dz
            sides = {1: [], -1: []}
            for y, idx in rings:
                if y > ymax or y < 0.0012 * S:
                    continue
                pts = [lc.v[k] for k in idx]
                c = ctr(idx)
                for a, b in zip(pts, pts[1:] + pts[:1]):
                    if (a.z - z0) * (b.z - z0) < 0:
                        t = (z0 - a.z) / (b.z - a.z); q = a.lerp(b, t)
                        sides[1 if q.x > c.x else -1].append((y, q, (q - V(c.x, y, c.z)).normalized()))
            if len(sides[1]) < 2 or len(sides[-1]) < 2:
                continue
            up = sorted(sides[1], key=lambda e: e[0]); dn = sorted(sides[-1], key=lambda e: -e[0])
            top_ = (up[-1][1] + dn[0][1]) / 2 + V(0, 0.0010 * S, 0)
            path = [q + n * 0.0006 * S for _, q, n in up] + [top_] + [q + n * 0.0006 * S for _, q, n in dn]
            path = [V(p.x, max(p.y, 0.0016 * S), p.z) for p in path]
            if len(path) >= 3:
                tube(cg, path, [(0.0015 * S, 0.0007 * S)] * len(path), 5, wleg, reg, 0, cap0=True, cap1=True,
                     ref=V(0, 0, 1))
        # sole rim: the lowest full ring, a little wider, from y 0.0004 to 0.0026 S (a sole you can see)
        low = [r for r in rings if r[0] < 0.0040 * S]
        if low:
            y0, idx = low[-1]
            c = ctr(idx)
            r0 = [V(c.x + (lc.v[k].x - c.x) * 1.07, 0.0005 * S, c.z + (lc.v[k].z - c.z) * 1.05) for k in idx]
            r1 = [V(c.x + (lc.v[k].x - c.x) * 1.08, 0.0026 * S, c.z + (lc.v[k].z - c.z) * 1.06) for k in idx]
            r2 = [V(c.x + (lc.v[k].x - c.x) * 1.02, 0.0030 * S, c.z + (lc.v[k].z - c.z) * 1.01) for k in idx]
            a_ = cg.ring(r0, wleg); b_ = cg.ring(r1, wleg); c_ = cg.ring(r2, wleg)
            cg.bridge(a_, b_, reg, 0); cg.bridge(b_, c_, reg, 0)
            cg.fan(list(reversed(a_)), V(c.x, 0.0005 * S, c.z), wleg, reg, 0)
        C.add("straps" + side, cg, subdiv=0, piece_as="leg" + side)


def curl_cover(C, cg, pts_nrms, r, wfn, reg, seed=11, flat=0.55):
    """Small round curls (flattened blobs) on a surface: [(point, normal)]."""
    rnd = random.Random(seed)
    for p, n in pts_nrms:
        t = perp(V(0, 1, 0), n) if abs(n.y) < 0.95 else V(1, 0, 0)
        b = n.cross(t).normalized()
        M = Matrix((t, b, n)).transposed()
        rr = r * (0.80 + 0.40 * rnd.random())
        blob(cg, p + n * rr * 0.10, rr, rr * 0.9, rr * flat, wfn, reg, 0, NU=9, NV=5, ax=M)


def beard_curls(C, name, r, step=1, keep=None, seed=5):
    """Curls over a build_beard surface (its cage rows), skipping the mouth so the decal mouth stays readable."""
    pt = part_named(C, name); bc = pt["cage"]; L = C.L; H = C.H; zc = L["zc"]
    out = []
    for i, p in enumerate(bc.v):
        if i % step:
            continue
        if keep and not keep(p):
            continue
        n = V(p.x, 0.0, p.z - zc)
        n = (n.normalized() + V(0, -0.25, 0)).normalized()
        out.append((p, n))
    cg = Cage()
    curl_cover(C, cg, out, r, C.w(["head", "jaw"], blend=0.006 * C.S), "hair", seed=seed)
    # same jaw weights as the beard itself: lower curls follow the jaw
    for i, p in enumerate(cg.v):
        wj = smoothstep(L["mouth"] - 0.02 * H, L["chin"] - 0.02 * H, p.y)
        cg.w[i] = mixw(({"head": 1.0}, 1 - 0.6 * wj), ({"jaw": 1.0}, 0.6 * wj))
    C.add(name + "Curls", cg, subdiv=0, piece_as=name)


def coat_panel_weights(C, cg_):
    """The coat's front-panel weighting of build_joseph (coatL / coatR below the waist) for added coat geometry."""
    S = C.S; wy = C.s["waistY"]
    for i, p in enumerate(cg_.v):
        if sleeve_sv(C, p):
            continue
        a = math.atan2(p.x, p.z + 0.001)
        tw = smoothstep(wy + 0.002 * S, wy - 0.030 * S, p.y) * smoothstep(math.radians(88), math.radians(38), abs(a))
        if tw > 0 and p.z > 0:
            cg_.w[i] = mixw((cg_.w[i], 1 - 0.50 * tw), ({"coat" + ("L" if p.x > 0 else "R"): 1.0}, 0.50 * tw))


# ---------------------------------------------------------------------------------------------- Joseph
def polish_joseph(C):
    s = C.s; L = C.L; H = C.H; S = C.S; wy = s["waistY"]
    # ---- jaw-length hair in sculpted locks combed from the centre parting: each lock starts on the parting line
    # (front hairline -> crown) and falls to the jaw, the ends tucked under; locks overlap so no scalp shows
    cg = Cage(); wfn = C.w(["head"])
    rim = C.hair_rim
    n_side = 11
    for sd in (1, -1):
        ends = [lerp(0.040, 0.490, k / (n_side - 1)) for k in range(n_side)]
        ep = [hair_point(C, uu, rim(uu) + 0.004 * S, sd)[0] for uu in ends]
        for k, ue in enumerate(ends):
            gap = min([(ep[k] - ep[j]).length for j in (k - 1, k + 1) if 0 <= j < n_side] or [0.006 * S])
            q = k / (n_side - 1)
            if q < 0.55:
                us = 0.010; ys = lerp(rim(0.0) + 0.02 * H, L["top"] - 0.004 * H, smoothstep(0.0, 0.55, q))
            else:
                us = 0.490; ys = lerp(L["top"] - 0.004 * H, L["brow"] + 0.34 * H, smoothstep(0.55, 1.0, q))
            ye = rim(ue) + 0.0024 * S
            th = 0.0023 * S
            ctrl = []
            NP = 8
            for i in range(NP):
                t = i / (NP - 1)
                uu = lerp(us, ue, smoothstep(0.0, 1.0, min(1.0, t * 1.25)))
                y = lerp(ys, ye, t ** 1.2)
                p, n = hair_point(C, uu, y, sd)
                ctrl.append((p - n * th * 0.50, n))
            p, n = ctrl[-1]
            hn = V(n.x, 0, n.z).normalized()
            ctrl.append((p - hn * 0.0020 * S + V(0, -0.0008 * S, 0), (hn + V(0, -1.4, 0)).normalized()))
            sculpt_lock(cg, ctrl, max(0.0034 * S, gap * 0.68), th, wfn, NS=9, N=6, tip=0.55, root=0.55,
                        h0=0.50, hend=0.45, flat=0.25)
    C.add("hairLocks", cg, subdiv=1, piece_as="hair")
    # the smooth shell under the locks: keep only a faint groove (the locks carry the relief now)
    # ---- the coat: gold edging (DESIGN §1 "a gold edging line"), an embroidered hem band with diamonds, cuff bands,
    # a neckline cord. Region `trim` is anchored to coat2 (it prints as detail lines)
    part_named(C, "coatEdge")["retag"] = lambda c, n, r, k=0: "trim"
    rows = C.coat_rows; hemC = rows[-1][0]
    y_open = wy + 0.006 * S

    def gap(y):
        return math.radians(lerp(4.0, 17.0, smoothstep(y_open, hemC, y) ** 0.85))
    cg = Cage(); wt = skirt_weights(C)
    for yb, rr in ((hemC + 0.0105 * S, 0.0010 * S), (hemC + 0.0190 * S, 0.0010 * S)):
        g0 = gap(yb) + math.radians(4.0)
        path = [shell_point(rows, yb, g0 + (2 * math.pi - 2 * g0) * j / 72, 0.0006 * S) for j in range(73)]
        tube(cg, path, [rr] * len(path), 5, wt, "trim", 0, cap0=True, cap1=True)
    yd = hemC + 0.0148 * S                               # little diamonds between the two cords
    g0 = gap(yd) + math.radians(7.0)
    for j in range(26):
        a = g0 + (2 * math.pi - 2 * g0) * (j + 0.5) / 26
        p = shell_point(rows, yd, a, 0.0004 * S)
        hw_, zf_, zb_ = table(rows, yd); n = V(p.x, 0, p.z - (zf_ + zb_) / 2).normalized()
        t = V(n.z, 0, -n.x)
        M = Matrix((t, V(0, 1, 0), n)).transposed()
        blob(cg, p, 0.0023 * S, 0.0030 * S, 0.0009 * S, wt, "trim", 0, NU=4, NV=4, ax=M)
    coat_panel_weights(C, cg)
    C.add("coatTrim", cg, subdiv=0, piece_as="coat", skinprop="coat")
    cg = Cage()
    sleeve_end = 0.082
    for side in "LR":
        A = C.arm[side]
        X0 = perp(V(0, 0, 1), A["d"]); Y0 = A["d"].cross(X0)
        for sv_, r_ in ((sleeve_end - 0.010, 0.0226), (sleeve_end - 0.016, 0.0216)):
            cc = A["S0"] + A["d"] * (sv_ * S)
            r = r_ * S + 0.0006 * S
            ring = [cc + (X0 * math.cos(2 * math.pi * j / 28) + Y0 * math.sin(2 * math.pi * j / 28)) * r for j in range(28)]
            tube(cg, ring + [ring[0]], [0.0009 * S] * 29, 5, C.w(["upperArm" + side, "forearm" + side]), "trim", 0,
                 cap0=False, cap1=False)
    C.add("coatCuffs", cg, subdiv=0, piece_as="coat", skinprop="coat")
    # ---- the tunic: a cord round the neckline (seen in the plain and governor looks)
    cg = Cage(); tr = C.tunic_rows
    y0 = tr[0][0] - 0.0006 * S
    neck = [shell_point(tr, y0, 2 * math.pi * j / 36, 0.0006 * S) for j in range(36)]
    rope(cg, neck, 0.0012 * S, C.w(["chest", ("neck", 0.006 * S)]), "belt", closed=True, twist=0.0040 * S, N=3)
    C.add("tunicCord", cg, subdiv=0, piece_as="tunic")
    sandal_straps(C, "sandals")


# ---------------------------------------------------------------------------------------------- the brother
def polish_brother(C):
    s = C.s; L = C.L; H = C.H; S = C.S; wy = s["waistY"]; nb = s["neckBase"]
    # ---- short black curls over the hair shell (rows of round curls)
    rim = C.hair_rim; cg = Cage(); pts = []
    rnd = random.Random(3)
    nrows = 7
    for j in range(nrows):
        t = (j + 0.5) / nrows
        nu = int(round(lerp(30, 12, t ** 1.4)))
        for i in range(nu):
            u = (i + 0.5 * (j % 2) + rnd.uniform(-0.15, 0.15)) / nu
            uu = mirror_u(u)
            y = lerp(rim(u) + 0.0030 * S, L["top"] - 0.0010 * S, t ** 0.9)
            if y < rim(u) + 0.0020 * S:
                continue
            p = C.hair_outer(u, min(y, L["top"] - 0.0006))
            n = (p - V(0, min(p.y, L["eye"]), L["zc"])).normalized()
            pts.append((p - n * 0.0006 * S, n))
    curl_cover(C, cg, pts, 0.0026 * S, C.w(["head"]), "hair", seed=4, flat=0.50)
    C.add("hairCurls", cg, subdiv=0, piece_as="hair")
    # ---- curls on the short beard (not over the mouth)
    hw = s["hw"]
    beard_curls(C, "beard", 0.0024 * S, step=2,
                keep=lambda p: p.z > L["zc"] and not (abs(p.x) < 0.52 * hw and p.y > L["mouth"] - 0.16 * H), seed=8)
    # ---- belt: a bronze ring buckle with a tongue (belt region), a stitched edge line
    cg = Cage(); wb = C.w(["hips", "spine"])
    tr = C.tunic_rows
    pf = shell_point(tr, wy, 0.0, 0.0020 * S)
    ring = [pf + V(0.0062 * S * math.cos(2 * math.pi * j / 20), 0.0058 * S * math.sin(2 * math.pi * j / 20), 0.0008 * S)
            for j in range(20)]
    tube(cg, ring + [ring[0]], [0.0013 * S] * 21, 6, wb, "belt", 0, cap0=False, cap1=False)
    tube(cg, [pf + V(-0.0062 * S, 0, 0.0012 * S), pf + V(0.0040 * S, 0, 0.0016 * S)], [0.0009 * S] * 2, 5, wb, "belt", 0)
    for yb in (wy - 0.0056 * S, wy + 0.0056 * S):
        st = [shell_point(tr, yb, 2 * math.pi * j / 64, 0.0021 * S) for j in range(64)]
        for j in range(0, 64, 2):
            a, b = st[j], st[j + 1]
            if (a.z + b.z) / 2 < 0 or abs(a.x + b.x) < 0.014 * S:
                continue
            tube(cg, [a, a.lerp(b, 0.6)], [0.00045 * S] * 2, 3, wb, "belt", 0)
    C.add("buckle", cg, subdiv=0, piece_as="belt")
    # ---- tunic neckline: a short laced slit
    cg = Cage(); wc = C.w(["chest", ("neck", 0.006 * S)])
    y0 = tr[0][0] - 0.0020 * S
    for k in range(3):
        ya = y0 - 0.0050 * S * k; yb_ = ya - 0.0050 * S
        for sx in (-1, 1):
            a = shell_point(tr, ya, math.radians(6 * sx), 0.0010 * S)
            b = shell_point(tr, yb_, math.radians(-6 * sx), 0.0010 * S)
            tube(cg, [a, (a + b) / 2 + V(0, 0, 0.0006 * S), b], [0.0006 * S] * 3, 4, wc, "cord", 0)
    C.add("lacing", cg, subdiv=0, piece_as="tunic")
    # ---- the bag: a toggle on the flap, a stitched seam round the flap, a buckle where the strap meets the bag
    bp = part_named(C, "bag"); cg = bp["cage"]
    hb = C.B["bag"][1]
    wbag = C.w(["bag", "hips"], blend=0.020 * S)
    ps = shell_point(C.tunic_rows, s["hipY"] - 0.006 * S, math.radians(-30), 0.0)
    zc_t = (table(C.tunic_rows, s["hipY"] - 0.006 * S)[1] + table(C.tunic_rows, s["hipY"] - 0.006 * S)[2]) / 2
    nn = V(ps.x, 0, ps.z - zc_t).normalized(); pc_ = ps + nn * 0.0085 * S
    tg = V(0, 1, 0).cross(nn).normalized()
    blob(cg, pc_ + V(0, 0.0040 * S, 0) + nn * 0.0090 * S, 0.0030 * S, 0.0022 * S, 0.0018 * S, wbag, "bag", 0, NU=8, NV=5)
    seam = [pc_ + V(0, 0.0110 * S, 0) + nn * 0.0072 * S + tg * (0.0200 * S * math.cos(math.pi * j / 18))
            + V(0, -0.0060 * S * math.sin(math.pi * j / 18), 0) for j in range(19)]
    for j in range(0, 18, 2):
        tube(cg, [seam[j], seam[j].lerp(seam[j + 1], 0.6)], [0.0005 * S] * 2, 3, wbag, "bag", 0)
    sandal_straps(C, "sandals")


# ---------------------------------------------------------------------------------------------- Pharaoh
def polish_pharaoh(C):
    s = C.s; L = C.L; H = C.H; S = C.S; wy = s["waistY"]; nb = s["neckBase"]; chestY = s["chestY"]
    shY = s["shoulder"][1]
    tilt = math.radians(8.0); y_cb = L["brow"] + 0.16 * H
    # ---- striped head-cloth (nemes) under the double crown: a band across the forehead below the crown, wings
    # behind the ears, two lappets resting on the collar, a tail at the back. Stripes alternate gold (nemesA -> the
    # collar's colour) and lapis (nemesB -> the apron's colour); both anchored (detail lines on the sheet).
    C.parts = [p for p in C.parts if p["name"] not in ("earL", "earR")]        # covered by the cloth
    keep_rows = C.robe_rows
    C.robe_rows = C.torso_rows

    def nrim(u):
        uu = mirror_u(u)
        return table([(0.000, y_cb - 0.0050 * S), (0.100, y_cb - 0.0060 * S), (0.128, L["eye"] + 0.02 * H),
                      (0.150, L["mouth"] - 0.04 * H), (0.170, chestY + 0.006 * S), (0.200, chestY + 0.002 * S),
                      (0.232, chestY + 0.004 * S), (0.250, nb + 0.004 * S), (0.30, nb + 0.008 * S),
                      (0.40, nb + 0.004 * S), (0.45, shY - 0.010 * S), (0.50, shY - 0.016 * S)], uu)[0]

    def nthick(u, y):
        uu = mirror_u(u)
        return (0.0020 + 0.0010 * smoothstep(0.13, 0.30, uu)) * S
    hood(C, "nemes", "nemesA", nrim, nthick, hood_weights(C, ["chest"], arm_reach=0.012), NU=40, NV=12, flare=0.30,
         body_off=0.0058, back_settle=0.80, front_pull=0.50, folds=(14, 0.0004), hem_wave=0.0002, solid=0.0011,
         settle=0.92)
    C.robe_rows = keep_rows
    npart = C.parts[-1]
    y_band = y_cb - 0.0005 * S
    sw = 0.0062 * S
    cuts = []
    yv = y_band
    while yv > chestY - 0.030 * S:
        cuts.append(yv); yv -= sw
    zc = L["zc"]
    npart["cull"] = lambda p: p.y > y_cb + 0.0010 * S + (p.z - zc) * math.tan(tilt)

    def nemes_reg(c, n, r, k=0):
        i = int(math.floor((y_band - c.y) / sw))
        return "nemesA" if i % 2 == 0 else "nemesB"
    npart["cuts"] = [(V(0, y, 0), V(0, 1, 0)) for y in cuts]; npart["retag"] = nemes_reg
    # ---- the broad collar (wesekh): three rows of beads (gold / lapis / gold), drop pendants all round the edge
    tor = C.torso_rows
    N_ = 48; prof = []
    for j in range(N_):
        a = 2 * math.pi * j / N_
        pts, sl = shell_profile(tor, a, 0.0012 * S, tor[0][0], chestY - 0.045 * S)
        s0 = sl[min(range(len(pts)), key=lambda i: abs(pts[i].y - (nb - 0.0030 * S)))]
        ca = math.cos(a)
        wd = (0.032 * S if ca > 0 else 0.022 * S) * (0.55 + 0.45 * abs(ca)) + 0.004 * S * (1 - abs(ca))
        prof.append((pts, sl, s0, wd))
    tor_c = lambda p: V(0, p.y, (table(tor, p.y)[1] + table(tor, p.y)[2]) / 2)
    wcol = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S)])
    cg = Cage()
    for t, reg, nb_ in ((0.18, "collar", 2), (0.54, "inlay", 2), (0.88, "collar", 2)):
        for j in range(N_ * nb_):
            jj = j / nb_
            i0 = int(jj) % N_; i1 = (i0 + 1) % N_; f = jj - int(jj)
            p0 = at_arclen(*prof[i0][:2], prof[i0][2] + prof[i0][3] * t)
            p1 = at_arclen(*prof[i1][:2], prof[i1][2] + prof[i1][3] * t)
            p = p0.lerp(p1, f); n = (p - tor_c(p)).normalized()
            if n.z < -0.2:
                continue
            blob(cg, p + n * 0.0026 * S, 0.0011 * S, 0.0011 * S, 0.0009 * S, wcol, reg, 0, NU=6, NV=4)
    for j in range(N_):
        pts, sl, s0, wd = prof[j]
        p = at_arclen(pts, sl, s0 + wd + 0.0030 * S)
        n = (p - tor_c(p)).normalized()
        if n.z < -0.3:
            continue
        reg = "inlay" if j % 2 else "collar"
        dn = (at_arclen(pts, sl, s0 + wd + 0.0050 * S) - p).normalized()
        tg = dn.cross(n).normalized()
        M = Matrix((tg, -dn, n)).transposed()
        blob(cg, p + n * 0.0012 * S + dn * 0.0006 * S, 0.0015 * S, 0.0026 * S, 0.0010 * S, wcol, reg, 0, NU=6, NV=5,
             ax=M)
    C.add("collarJewels", cg, subdiv=0, piece_as="collar")
    # ---- arm-bands: a lapis inlay between the gold rims; a cartouche buckle on the belt
    cg = Cage()
    arm = [(0.004, 0.0140), (0.012, 0.0140), (0.022, 0.0130), (0.032, 0.0118), (0.042, 0.0106), (0.050, 0.0098),
           (0.056, 0.0094), (0.062, 0.0092)]
    for side in "LR":
        A = C.arm[side]; d = A["d"]; X0 = perp(V(0, 0, 1), d); Y0 = d.cross(X0)
        sv = 0.036 * S; r = table([(a * S, b * S) for a, b in arm], sv)[0] + 0.0004 * S + 0.0022 * S
        c = A["S0"] + d * sv
        pts = [c + (X0 * math.cos(2 * math.pi * j / 24) + Y0 * math.sin(2 * math.pi * j / 24)) * r for j in range(24)]
        band_loop(cg, pts, [(p - c).normalized() for p in pts], [d] * 24, 0.0017 * S, 0.0005 * S,
                  C.w(["upperArm" + side]), "inlay", 0)
        for j in range(0, 24, 3):                 # gold studs on the inlay
            n = (pts[j] - c).normalized()
            blob(cg, pts[j] + n * 0.0007 * S, 0.0009 * S, 0.0009 * S, 0.0007 * S, C.w(["upperArm" + side]), "gold", 0,
                 NU=6, NV=4)
    kr = keep_rows
    ytop = wy - 0.014 * S
    pf = shell_point(kr, ytop - 0.0005 * S, 0.0, 0.0030 * S)
    wb = C.w(["hips", "spine"])
    blob(cg, pf + V(0, 0, 0.0010 * S), 0.0060 * S, 0.0056 * S, 0.0016 * S, wb, "gold", 0, NU=12, NV=6)
    blob(cg, pf + V(0, 0, 0.0026 * S), 0.0036 * S, 0.0032 * S, 0.0008 * S, wb, "inlay", 0, NU=10, NV=5)
    C.add("jewels", cg, subdiv=0, piece_as="bands")
    sandal_straps(C, "gold")


# ---------------------------------------------------------------------------------------------- Jacob
def polish_jacob(C):
    s = C.s; L = C.L; H = C.H; S = C.S; wy = s["waistY"]; chestY = s["chestY"]
    # ---- the long white beard: flowing strands down the front, wavy tips
    bp = part_named(C, "beardLong"); bc = bp["cage"]; NB = 16; NR = 12
    wbeard_src = [bc.w[j * NB] for j in range(NR + 1)]
    cg = Cage()

    def wb(p):
        # same as the beard: jaw / head at the top, head / neck / chest lower down
        t = min(1.0, max(0.0, (L["chin"] + 0.05 * H - p.y) / (L["chin"] + 0.05 * H - (chestY - 0.004 * S))))
        wt = smoothstep(0.30, 0.0, t)
        lo = {"head": 0.70, "neck": 0.15, "chest": 0.15}
        return mixw(({"jaw": 0.60, "head": 0.40}, wt), (lo, 1 - wt)) if wt > 0 else lo
    idx = (11, 12, 13, 14, 15, 0, 1, 2, 3, 4, 5)
    for k, i in enumerate(idx):
        ctrl = []
        for j in range(NR + 1):
            p = bc.v[j * NB + i]
            c = V(0, p.y, sum(bc.v[j * NB + q].z for q in range(NB)) / NB)
            n = (p - c); n = V(n.x, 0, n.z).normalized() if n.length > 1e-9 else V(0, 0, 1)
            sway = 0.0007 * S * math.sin(j / NR * math.pi * 2.0 + k * 0.9)
            ctrl.append((p - n * 0.0004 * S + V(sway, 0, 0), n))
        p, n = ctrl[-1]
        ctrl.append((p + V(0.0012 * S * (1 if k % 2 else -1), -0.0036 * S, 0.0006 * S), n))
        side = abs(k - 5) / 5
        sculpt_lock(cg, ctrl, 0.0042 * S * (1.0 - 0.30 * side), 0.0018 * S, wb, NS=14, N=6, tip=0.30,
                    root=0.70, h0=0.70, flat=0.25)
    C.add("beardStrands", cg, subdiv=1, piece_as="beardLong")
    # ---- the cheek beard and moustache area: soft wavy locks down each column of the beard (no curls: kinder)
    bp = part_named(C, "beard"); bcg = bp["cage"]; NU_ = 21; NV_ = 11
    cg = Cage(); zc = L["zc"]
    for i in range(1, NU_ - 1, 2):
        ctrl = []
        for j in range(NV_ + 1):
            p = bcg.v[j * NU_ + i]
            n = V(p.x, 0, p.z - zc).normalized()
            ctrl.append((p - n * 0.0003 * S, n))
        if ctrl[0][0].z < zc:
            continue
        sculpt_lock(cg, ctrl, 0.0036 * S, 0.0014 * S, C.w(["head"]), NS=10, N=6, tip=0.45, root=0.65, h0=0.70,
                    flat=0.25)
    for i, p in enumerate(cg.v):
        wj = smoothstep(L["mouth"] - 0.02 * H, L["chin"] - 0.02 * H, p.y)
        cg.w[i] = mixw(({"head": 1.0}, 1 - 0.6 * wj), ({"jaw": 1.0}, 0.6 * wj))
    C.add("beardLocks", cg, subdiv=1, piece_as="beard")
    # ---- the shawl: a woven border near the edge and a fringe of little tassels on the hem
    pt = C.hood_pt

    def srim(u):
        uu = mirror_u(u)
        return table([(0.000, L["brow"] + 0.26 * H), (0.050, L["brow"] + 0.24 * H), (0.090, L["brow"] + 0.16 * H),
                      (0.125, L["eye"] + 0.04 * H), (0.160, L["nose"] - 0.04 * H), (0.190, L["mouth"] - 0.10 * H),
                      (0.205, L["chin"] - 0.14 * H), (0.214, wy - 0.004 * S), (0.235, wy - 0.010 * S),
                      (0.262, wy + 0.004 * S), (0.29, chestY - 0.030 * S), (0.33, chestY - 0.034 * S),
                      (0.38, chestY - 0.030 * S), (0.45, wy + 0.012 * S), (0.50, wy + 0.008 * S)], uu)[0]
    wsh = hood_weights(C, ["shawl1", "shawl2", ("chest", None)], arm_reach=0.016)
    cg = Cage()
    for d_ in (0.0070 * S, 0.0110 * S):
        path = []
        for j in range(161):
            u = j / 160
            if mirror_u(u) < 0.212:
                continue
            p = pt(u, srim(u) + d_)
            c = V(0, p.y, L["zc"])
            path.append(p + V(p.x, 0, p.z - c.z).normalized() * 0.0007 * S)
        tube(cg, path, [0.0008 * S] * len(path), 4, wsh, "shawl", 0, cap0=True, cap1=True)
    for j in range(120):
        u = (j + 0.5) / 120
        uu = mirror_u(u)
        if uu < 0.209:
            continue
        p = pt(u, srim(u), edge=True)
        c = V(0, p.y, L["zc"]); n = V(p.x, 0, p.z - c.z).normalized()
        q0 = p + n * 0.0004 * S
        q1 = q0 + V(0, -0.0050 * S, 0) + n * 0.0004 * S
        q2 = q0 + V(0, -0.0090 * S, 0) + n * 0.0006 * S
        tube(cg, [q0, q1, q2], [0.0008 * S, 0.0007 * S, 0.0004 * S], 4, wsh, "shawl", 0, cap0=False, cap1=True)
    C.add("shawlFringe", cg, subdiv=0, piece_as="shawl")
    # ---- the staff: a leather grip wrap under the hand and a carved ring under the knob (same rigid prop)
    sp = part_named(C, "stick"); cg = sp["cage"]
    g = C.B["stick"][0]; top = C.B["stick"][1]
    bot = V(g.x - 0.004 * S, 0.0030, g.z + 0.010 * S)

    def stick_at(t):
        p = bot.lerp(top, t)
        return p + V(0.0012 * S * math.sin(t * 7.0), 0, 0.0008 * S * math.sin(t * 5.0 + 1.0))
    dirn = (top - bot).normalized(); X0 = perp(V(0, 0, 1), dirn); Y0 = dirn.cross(X0)
    t0 = 0.70; t1 = 0.86
    hel = []
    for i in range(61):
        f = i / 60; t = lerp(t0, t1, f); c = stick_at(t)
        r = 0.0026 * S + 0.0008 * S * t + 0.0007 * S
        a = 2 * math.pi * 6 * f
        hel.append(c + (X0 * math.cos(a) + Y0 * math.sin(a)) * r)
    tube(cg, hel, [0.0007 * S] * len(hel), 4, None, "stick", 0)
    c = stick_at(0.985)
    ring = [c + (X0 * math.cos(2 * math.pi * j / 16) + Y0 * math.sin(2 * math.pi * j / 16)) * 0.0040 * S for j in range(16)]
    tube(cg, ring + [ring[0]], [0.0008 * S] * 17, 4, None, "stick", 0, cap0=False, cap1=False)
    sandal_straps(C, "sandals")


POLISH = {"joseph": polish_joseph, "brother": polish_brother, "pharaoh": polish_pharaoh, "jacob": polish_jacob}


def _polished(ch):
    base = {"joseph": build_joseph, "brother": build_brother, "pharaoh": build_pharaoh, "jacob": build_jacob}[ch]

    def f(C):
        base(C)
        if not os.environ.get(ENV + "NOPOLISH"):
            POLISH[ch](C)
        if ch in E3_CHARS:
            e3_bones(C)
    return f


def e3_bones(C):
    """eyeL / eyeR (children of head) near the eyeball centres; eyes3d_apply moves them onto the exact centres."""
    P3 = E3[C.ch]; hw = C.s["hw"]; ex = P3["ex"] * hw; ey = C.L["eye"]; z = C.L["zc"] + 0.6 * hw
    for o, sd in ((1, "L"), (-1, "R")):
        C.B["eye" + sd] = (V(o * ex, ey, z), V(o * ex, ey, z + 0.004), "head")


REST_BAKE = {   # Jacob: built straight (~0.35), then stooped; arms hang plumb again, head tips back up (as Naomi)
    "jacob": [("spine", V(1, 0, 0), 6.0), ("chest", V(1, 0, 0), 16.0), ("neck", V(1, 0, 0), 14.0),
              ("head", V(1, 0, 0), -24.0), ("upperArmL", V(1, 0, 0), -20.0), ("upperArmR", V(1, 0, 0), -20.0)],
}


# =============================================================================================== Blender assembly
BUILDERS = {ch: _polished(ch) for ch in CHARS}     # builders + the sculpt polish (JS_NOPOLISH=1 skips it)
PIECES = []           # global piece id -> (char, part, piece); index 0 = background
REGIONS = []          # global region id -> "char.region"
PART_TRIS = {}


def make_part_object(C, ch, pt, sheet, rig):
    """Kit version + Exodus' bisect cuts and centroid re-tagging (clean straight stripe edges)."""
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


def build_character(ch):
    """Kit version + skinned props (pt["skinprop"]): kept out of the body join, own Armature modifier, exported as
    their own skinned node; printed (front UV with occlusion) when shown by default."""
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
    body = [o for o, pt in objs if not pt.get("rigid") and not pt.get("skinprop")]
    skinp = [o for o, pt in objs if pt.get("skinprop")]
    props = [o for o, pt in objs if pt.get("rigid")]
    bpy.ops.object.select_all(action='DESELECT')
    for o in body: o.select_set(True)
    bpy.context.view_layer.objects.active = body[0]
    bpy.ops.object.join()
    bodyo = bpy.context.view_layer.objects.active; bodyo.name = f"{ch}_body"; bodyo.data.name = f"{ch}_body"
    for o in [bodyo] + skinp:
        bpy.ops.object.select_all(action='DESELECT')
        o.select_set(True); bpy.context.view_layer.objects.active = o
        bpy.ops.object.vertex_group_limit_total(group_select_mode='ALL', limit=4)
        bpy.ops.object.vertex_group_normalize_all(group_select_mode='ALL', lock_active=False)
        am = o.modifiers.new("Armature", 'ARMATURE'); am.object = rig
    groups = {}
    for o, pt in objs:
        if pt.get("skinprop"):
            groups.setdefault(pt["skinprop"], []).append(o)
    skinp = []
    for name, lst in groups.items():
        bpy.ops.object.select_all(action='DESELECT')
        for o in lst: o.select_set(True)
        bpy.context.view_layer.objects.active = lst[0]
        if len(lst) > 1:
            for o in lst[1:]:
                for m in list(o.modifiers): o.modifiers.remove(m)
            bpy.ops.object.join()
        o = bpy.context.view_layer.objects.active; o.name = f"{ch}_{name}"; o.data.name = o.name
        skinp.append(o)
    baked = None
    if ch in REST_BAKE and not os.environ.get(ENV + "NOBAKE"):
        baked = bake_rest_pose(C, rig, bodyo, REST_BAKE[ch])
    props = skinp + props
    vis = [bodyo] + [o for o in props if not is_hidden_prop(o)]
    stats = front_uv_with_occlusion([(o, o is not bodyo and o not in skinp) for o in vis], sheet, ART_H, INSET,
                                    anchors=None, region_name=lambda r: REGIONS[r - 1].split(".")[1])
    if baked is not None:
        stats["restBakePropDrift"] = round(baked, 6)
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


def nest_skinned_props(glb, ch):
    """Move each skinned prop's mesh node (e.g. joseph_coat) under its prop joint (coat) in the GLB, so the engine's
    prop switch ("joseph/coat": every Renderer under that transform) reaches it. glTF ignores the transform of a
    skinned mesh node, so skinning is unchanged."""
    import struct
    names = SKINNED_PROPS.get(ch, set())
    if not names:
        return {}
    data = open(glb, "rb").read()
    magic, ver, total = struct.unpack_from("<III", data, 0)
    clen, ctype = struct.unpack_from("<II", data, 12)
    js = json.loads(data[20:20 + clen].decode("utf-8"))
    rest = data[20 + clen:]
    nodes = js["nodes"]
    idx = {n.get("name"): i for i, n in enumerate(nodes)}
    moved = {}
    for b in names:
        mi, bi = idx.get(f"{ch}_{b}"), idx.get(b)
        if mi is None or bi is None or mi in nodes[bi].get("children", []):
            continue
        for n in nodes:
            if mi in n.get("children", []):
                n["children"].remove(mi)
                if not n["children"]:
                    del n["children"]
        for sc_ in js.get("scenes", []):
            if mi in sc_.get("nodes", []):
                sc_["nodes"].remove(mi)
        nodes[bi].setdefault("children", []).append(mi)
        for key in ("translation", "rotation", "scale", "matrix"):
            nodes[mi].pop(key, None)
        moved[f"{ch}_{b}"] = b
    raw = json.dumps(js, separators=(",", ":")).encode("utf-8")
    raw += b" " * ((4 - len(raw) % 4) % 4)
    out = struct.pack("<III", magic, ver, 12 + 8 + len(raw) + len(rest)) + struct.pack("<II", len(raw), ctype) + raw + rest
    open(glb, "wb").write(out)
    return moved


# =============================================================================================== 3D eyes (pilot)
# Joseph only (E3_CHARS; JS_EYES3D=0 = the old decal eyes). Built after the ID render and the UV fixes, so the printed
# sheet and every page UV stay exactly as before. What it adds (all in the character's design frame):
#   * bones eyeL / eyeR (children of head) at the eyeball centres; rigid meshes <ch>_eyeL / <ch>_eyeR on them
#     (eyeball with a cornea bulge, material js_eye, UV0 = eyes_<ch>.png atlas);
#   * on the body: the face around the eyes and nose subdivided twice, a sculpted nose (bridge, tip, alae, nostrils),
#     brow ridge, eye sockets (the skin under the lids sinks behind the eyeball), and upper / lower eyelids with a
#     rounded margin (page material; their page UV = the face texel next to them, so they take the child's skin colour);
#   * <ch>_eyeLines (skinned to head, material js_eyeLines): brows and the upper lash line + lashes, fixed colours from
#     the same atlas;
#   * blend shapes on the body and the lines (same names): blinkL_a/_b blinkR_a/_b (two halves = an in-between, so a
#     half-closed lid stays on the sphere) lidsWide squint lidsSad cheekRaise smile frown browUpL browUpR browDown
#     browInnerUp;
#   * face3d_<ch>.json: controls -> blend shapes, face name -> control weights, gaze / blink settings (DGFace3D.cs).
E3_SHAPES = ["blinkL_a", "blinkL_b", "blinkR_a", "blinkR_b", "lidsWide", "squint", "lidsSad", "cheekRaise", "smile",
             "frown", "browUpL", "browUpR", "browDown", "browInnerUp"]
E3_UV = {"brow": (0.975, 0.975), "lash": (0.025, 0.975)}
E3_CREASE = (3.0, 4.0)       # lid creases: degrees beyond the wide-open upper / lower margin (lids dive under the skin)
E3_EXPR = {   # face name (faces.json) -> control weights; gaze offsets in degrees (pitch + = up, yaw + = his right)
    "joseph": {
        "bright": dict(smile=0.40, cheekRaise=0.25, browUpL=0.15, browUpR=0.15, squint=0.10),
        "talk": dict(smile=0.12, browUpL=0.22, browUpR=0.22),
        "joy": dict(smile=0.95, cheekRaise=0.90, squint=0.80, browUpL=0.45, browUpR=0.45),
        "scared": dict(lidsWide=0.95, browInnerUp=0.85, browUpL=0.40, browUpR=0.40, frown=0.35),
        "sad": dict(lidsSad=0.75, browInnerUp=0.90, frown=0.65, blinkL=0.12, blinkR=0.12, gazePitch=-10.0),
        "pray": dict(blinkL=1.0, blinkR=1.0, browInnerUp=0.30, smile=0.20, gazePitch=-12.0),
        "wise": dict(squint=0.35, smile=0.32, blinkL=0.18, blinkR=0.18, browDown=0.08),
        "moved": dict(browInnerUp=0.75, squint=0.25, smile=0.15, lidsSad=0.30, gazePitch=3.0),
        "tears_joy": dict(smile=0.85, cheekRaise=0.85, squint=0.85, browInnerUp=0.55),
    }}


def e3_bump(s, peak):
    """0 at s = 0 and 1, 1 at s = peak (an almond side)."""
    if s <= 0.0 or s >= 1.0:
        return 0.0
    return math.sin(math.pi * s ** (math.log(0.5) / math.log(peak))) ** 0.8


def e3_margins(P3, st):
    """Upper / lower lid margin elevation (deg) as functions of alpha (deg, + = outer) for a lid state
    st = {blink, wide, squint, sad, cheek} (0..1). Beyond the corners both are the corner line (the lids meet)."""
    g = st.get
    U = P3["U"] + 12.0 * g("wide", 0) - 6.0 * g("squint", 0) - 2.0 * g("cheek", 0)
    D = P3["D"] + 3.0 * g("wide", 0) - 12.0 * g("squint", 0) - 7.0 * g("cheek", 0)
    Ain, Aout = P3["Ain"], P3["Aout"]
    bl = g("blink", 0)

    def s_of(a):
        return (a + Ain) / (Ain + Aout)

    def base(a):
        return lerp(P3["cIn"], P3["cOut"], min(1.0, max(0.0, s_of(a))))

    def closed(a):
        return base(a) - 0.42 * D * e3_bump(s_of(a), 0.55)

    def up(a):
        s = s_of(a); b = e3_bump(s, 0.5) ** 0.3
        return lerp(base(a) + U * e3_bump(s, 0.44) - 9.0 * g("sad", 0) * e3_bump(s, 0.72), closed(a) + 0.35 * b, bl)

    def lo(a):
        s = s_of(a); b = e3_bump(s, 0.5) ** 0.3
        return lerp(base(a) - D * e3_bump(s, 0.56), closed(a) - 0.35 * b, bl)
    return up, lo, base


def e3_dir(a, b, o):
    a, b = math.radians(a), math.radians(b)
    return V(o * math.sin(a) * math.cos(b), math.sin(b), math.cos(a) * math.cos(b))


def e3_eyes(C, centres):
    """Eye frames: centre, side o (+1 = the character's left, +x), lid frame turned outward by yawOut."""
    P3 = E3[C.ch]; out = []
    for o, c in zip((1, -1), centres):
        a = math.radians(o * P3["yawOut"])
        R = Matrix(((math.cos(a), 0, math.sin(a)), (0, 1, 0), (-math.sin(a), 0, math.cos(a))))
        out.append(dict(c=c, o=o, R=R, side="L" if o > 0 else "R"))
    return out


def e3_pt(E, a, b, rad):
    return E["c"] + E["R"] @ (e3_dir(a, b, E["o"]) * rad)


def e3_lid_cols(P3):
    a0, a1 = -(P3["Ain"] + P3["ext"]), P3["Aout"] + P3["ext"]
    return [lerp(a0, a1, j / 37) for j in range(38)]


def e3_lids(E, P3, r, st):
    """Upper and lower lid sheets of one eye for lid state st: (verts, quads). Rows: inner lip (behind the margin,
    hugging the eyeball), mid lip (the rounded margin edge), then the outer surface from the margin to its buried
    edge (top / bot). Same topology for every state (shape keys)."""
    up, lo, base = e3_margins(P3, st)
    upw, low, _ = e3_margins(P3, {"wide": 1.0})
    cols = e3_lid_cols(P3)
    NR = 8
    vs, quads = [], []
    for lid, mf, sgn in (("up", up, 1), ("lo", lo, -1)):
        k0 = len(vs)
        rows = None
        for a in cols:
            m = mf(a)
            # the lid ends at its crease (a fixed line past the wide-open margin) and tucks steeply under the flat
            # skin band there, so lid and skin meet at a clean line
            crease = upw(a) + E3_CREASE[0] if sgn > 0 else low(a) - E3_CREASE[1]
            col = [e3_pt(E, a, m + sgn * 1.6, r * P3["lidIn"]), e3_pt(E, a, m - sgn * 0.9, r * P3["lidMid"])]
            for k in range(NR):
                t = k / (NR - 1)
                col.append(e3_pt(E, a, lerp(m, crease, t ** 1.2), r * P3["lidOut"] * (1 + 0.012 * math.sin(math.pi * t))))
            col.append(e3_pt(E, a, crease + sgn * 0.6, r * 1.035))
            col.append(e3_pt(E, a, crease + sgn * 1.2, r * 0.97))
            rows = len(col); vs += col
        nc = len(cols)
        for j in range(nc - 1):
            for i in range(rows - 1):
                quads.append([k0 + j * rows + i, k0 + (j + 1) * rows + i, k0 + (j + 1) * rows + i + 1, k0 + j * rows + i + 1])
    return vs, quads


def e3_orient(vs, quads, groups=None):
    """Consistent winding per connected strip: flip a whole strip when its summed normal faces away from +z."""
    out, i = [], 0
    strips = {}
    for q in quads:                          # strips = runs of quads sharing vertices (built in order)
        key = None
        for k, st in strips.items():
            if st["v"] & set(q):
                key = k; break
        if key is None:
            key = len(strips); strips[key] = {"v": set(), "q": []}
        strips[key]["v"] |= set(q); strips[key]["q"].append(q)
    for st in strips.values():
        n = Vector((0, 0, 0))
        for q in st["q"]:
            n += (vs[q[1]] - vs[q[0]]).cross(vs[q[2]] - vs[q[0]])
        out += [q if n.z >= 0 else q[::-1] for q in st["q"]]
    return out


def e3_lid_orient(E, vs, quads):
    """Wind every quad so its normal points away from the eyeball centre."""
    out = []
    for q in quads:
        a, b, c = vs[q[0]], vs[q[1]], vs[q[2]]
        n = (b - a).cross(c - a)
        ctr = (vs[q[0]] + vs[q[1]] + vs[q[2]] + vs[q[3]]) * 0.25
        out.append(q if n.dot(ctr - E["c"]) >= 0 else q[::-1])
    return out


def e3_eyeball(P3, r):
    """Eyeball around +Z (gaze), with a cornea bulge; returns local verts, faces, per-vertex uv (atlas disk)."""
    NS, NRg = 32, 24
    rc = math.radians(P3["iris"] + 7.0)
    vs, uvs, faces = [], [], []

    def rad(rho):
        t = min(1.0, rho / rc)
        return r * (1.0 + P3["cornea"] * math.cos(t * math.pi / 2) ** 2)
    vs.append(V(0, 0, rad(0.0))); uvs.append((0.5, 0.5))
    rings = []
    for k in range(1, NRg):
        rho = math.pi * (k / NRg) ** 1.35
        rr = 0.5 * math.sin(min(rho, math.pi / 2)) if rho <= math.pi / 2 else 0.495
        ring = []
        for j in range(NS):
            psi = 2 * math.pi * j / NS
            d = V(math.sin(rho) * math.cos(psi), math.sin(rho) * math.sin(psi), math.cos(rho))
            ring.append(len(vs)); vs.append(d * rad(rho)); uvs.append((0.5 + rr * math.cos(psi), 0.5 + rr * math.sin(psi)))
        rings.append(ring)
    vs.append(V(0, 0, -r)); uvs.append((0.5, 0.005)); back = len(vs) - 1
    for j in range(NS):
        faces.append([0, rings[0][j], rings[0][(j + 1) % NS]])
    for ra, rb in zip(rings, rings[1:]):
        for j in range(NS):
            faces.append([ra[j], rb[j], rb[(j + 1) % NS], ra[(j + 1) % NS]])
    for j in range(NS):
        faces.append([rings[-1][j], back, rings[-1][(j + 1) % NS]])
    return vs, faces, uvs


def e3_lash_geo(E, P3, r, st):
    """Upper lash line (a dark ribbon wrapping the lid margin, thicker toward the outer corner, a small flick past it)
    and five lashes on the outer half. Returns (verts, quads); same topology for every state."""
    up, lo, base = e3_margins(P3, st)
    Ain, Aout = P3["Ain"], P3["Aout"]
    vs, quads = [], []
    NL = 26
    alphas = [lerp(-Ain + 4.0, Aout + 7.0, k / (NL - 1)) for k in range(NL)]
    k0 = len(vs)
    for a in alphas:
        s = (a + Ain) / (Ain + Aout)
        if a <= Aout:
            m = up(a); w = (0.9 + 3.0 * min(1.0, s) ** 1.6) * min(1.0, (s - 0.035) / 0.12) ** 0.5
            lift = 0.0
        else:                                   # the flick: rises past the outer corner, tapering
            f = (a - Aout) / 7.0
            m = up(Aout) + 2.2 * f; w = lerp(3.9, 0.25, f ** 0.8); lift = f
        vs += [e3_pt(E, a, m - 1.0 + 0.6 * lift, r * P3["lidMid"] * 1.012),
               e3_pt(E, a, m + 0.2, r * P3["lidOut"] * 1.016),
               e3_pt(E, a, m + w, r * P3["lidOut"] * 1.010)]
    for j in range(NL - 1):
        for i in range(2):
            quads.append([k0 + j * 3 + i, k0 + (j + 1) * 3 + i, k0 + (j + 1) * 3 + i + 1, k0 + j * 3 + i + 1])
    for s in (0.66, 0.79, 0.90):
        a = lerp(-Ain, Aout, s); m = up(a) + 0.5
        root = e3_pt(E, a, m, r * P3["lidOut"] * 1.012)
        rad_ = (root - E["c"]).normalized()
        tb = (e3_pt(E, a, m + 1.0, r) - e3_pt(E, a, m - 1.0, r)).normalized()      # up the lid
        ta = (e3_pt(E, a + 1.0, m, r) - e3_pt(E, a - 1.0, m, r)).normalized()      # toward the outer corner
        d = (rad_ * 0.55 + tb * 0.70 + ta * (0.25 + 0.45 * s)).normalized()
        Ln = r * (0.13 + 0.07 * s)
        k1 = len(vs)
        for t in (0.0, 0.34, 0.67, 1.0):
            p = root + d * (Ln * t) + tb * (Ln * 0.30 * t * t)
            wv = ta * (r * 0.055 * (1 - t) + r * 0.006)
            vs += [p - wv, p + wv]
        for i in range(3):
            quads.append([k1 + 2 * i, k1 + 2 * i + 1, k1 + 2 * i + 3, k1 + 2 * i + 2])
    return vs, quads


def e3_brow_geo(C, P3, r, E, face_hit, st):
    """One brow as a soft tapered ribbon lying on the forehead (projected onto the face skin), rows across, columns
    from the inner to the outer end. st: up, down (angry), inner (sad). Returns (verts, quads)."""
    hw = C.s["hw"]; o = E["o"]; ey = E["c"].y
    NB = 26
    vs, quads = [], []
    up_, dn, inn = st.get("up", 0), st.get("down", 0), st.get("inner", 0)
    for j in range(NB):
        s = j / (NB - 1)
        x = o * (lerp(0.17, 0.82, s) * hw - 0.06 * hw * dn * (1 - s) ** 2)
        y = ey + r * (1.24 + 0.24 * math.sin(math.pi * s ** 0.85) - 0.14 * s)
        y += r * (0.42 * up_ * (1 + 0.15 * math.sin(math.pi * s)) + dn * (-0.40 * (1 - s) ** 1.5 + 0.12 * s * s)
                  + inn * (0.62 * (1 - s) ** 1.5 - 0.16 * s))
        w = r * 0.38 * (1 - 0.66 * s ** 1.2) * min(1.0, (s + 0.05) / 0.14) ** 0.5
        h = r * 0.08 * (w / (r * 0.38)) ** 0.5
        for v in (-1.0, -0.55, 0.0, 0.55, 1.0):
            p, n = face_hit(x, y + v * w * 0.5)
            vs.append(p + n * (0.00010 + h * max(0.0, 1 - v * v) ** 0.6))
    for j in range(NB - 1):
        for i in range(4):
            quads.append([j * 5 + i, (j + 1) * 5 + i, (j + 1) * 5 + i + 1, j * 5 + i + 1])
    return vs, quads


def e3_skin_field(C, p, key):
    """Displacement of a face-skin point (design, character-local) for a skin blend shape."""
    hw = C.s["hw"]; H = C.H; L = C.L; ey = L["eye"]; d = V(0, 0, 0)
    for sx in (-1, 1):
        if key == "cheekRaise":
            g = math.exp(-((p.x - sx * 0.52 * hw) / (0.30 * hw)) ** 2 - ((p.y - (ey - 0.19 * H)) / (0.11 * H)) ** 2)
            d += V(sx * 0.00008, 0.00065, 0.00040) * g
        elif key == "smile":
            g = math.exp(-((p.x - sx * 0.36 * hw) / (0.15 * hw)) ** 2 - ((p.y - L["mouth"]) / (0.06 * H)) ** 2)
            g2 = math.exp(-((p.x - sx * 0.44 * hw) / (0.22 * hw)) ** 2 - ((p.y - (L["mouth"] + 0.10 * H)) / (0.08 * H)) ** 2)
            d += V(sx * 0.00022, 0.00070, -0.00012) * g + V(sx * 0.00004, 0.00030, 0.00032) * g2
        elif key == "frown":
            g = math.exp(-((p.x - sx * 0.36 * hw) / (0.15 * hw)) ** 2 - ((p.y - L["mouth"]) / (0.06 * H)) ** 2)
            d += V(-sx * 0.00004, -0.00055, -0.00008) * g
    return d


def e3_lid_state(key, side):
    """Lid state of one eye (L / R) for a blend shape."""
    if key in ("blinkL_a", "blinkR_a"):
        return {"blink": 0.5} if key[5] == side else {}
    if key in ("blinkL_b", "blinkR_b"):
        return {"blink": 1.0} if key[5] == side else {}
    return {"lidsWide": {"wide": 1}, "squint": {"squint": 1}, "lidsSad": {"sad": 1}, "cheekRaise": {"cheek": 1}}.get(key, {})


def e3_brow_state(key, side):
    return {"browUpL": {"up": 1} if side == "L" else {}, "browUpR": {"up": 1} if side == "R" else {},
            "browDown": {"down": 1}, "browInnerUp": {"inner": 1}}.get(key, {})


def eyes3d_apply(ch, C, rig, body, props):
    """Build Joseph's 3D eyes on the finished body (see the section comment). Returns a report dict."""
    import numpy as np
    from mathutils.kdtree import KDTree
    P3 = E3[ch]; hw = C.s["hw"]; H = C.H; L = C.L; r = P3["r"] * hw
    sheet = SHEET[ch]; off = V(sheet[0], sheet[1], 0)
    MW = body.matrix_world.copy(); MWi = MW.inverted()

    def dsg(co):
        return to_design(MW @ co) - off

    def bl(p):
        return MWi @ to_bl(p + off)
    rep = {"trisBefore": tri_count([body] + props)}
    for o in list(props):                                   # the old lid cage goes: the bone stays (clips key it)
        if o.name == f"{ch}_eyelids":
            props.remove(o); bpy.data.objects.remove(o, do_unlink=True)
    fpid = piece_id((ch, "face", 0)); skin = region_id(ch, "skin")
    zc = L["zc"]

    # ---- 1. subdivide the face around the eyes, brows and nose (twice) so the sockets and nose can be sculpted
    def zone(c, grow=1.0):
        return abs(c.x) < 0.86 * hw * grow and L["nose"] - 0.07 * H < c.y < L["eye"] + 2.3 * r * grow and c.z > zc + 0.30 * hw
    me = body.data
    ex_, ey_ = P3["ex"] * hw, L["eye"]

    RING = (None, 1.85, 1.30)            # pass 2 / 3: only around the eyes and brows (pass 3: the lid creases)

    def eye_ring(c, k):
        return min(math.hypot(c.x - o * ex_, c.y - ey_) for o in (1, -1)) < RING[k] * r and c.z > zc + 0.30 * hw
    def ring_w(c, k):
        return smoothstep(RING[k] * r, (RING[k] - 0.4) * r, min(math.hypot(c.x - o * ex_, c.y - ey_) for o in (1, -1)))

    def zone_w(c):
        return smoothstep(0.86 * hw, 0.66 * hw, abs(c.x)) * smoothstep(L["nose"] - 0.07 * H, L["nose"] - 0.045 * H, c.y) \
            * smoothstep(L["eye"] + 2.3 * r, L["eye"] + 1.95 * r, c.y)
    for it in range(3):
        # the same subdivision twice, linear and smooth (identical topology); blended by a weight that is 1 inside
        # the zone and 0 at its edge: round inside (no facets), flat at the edge (no kinks where it meets old faces)
        res = []
        for smooth in (0.0, 1.0):
            bm = bmesh.new(); bm.from_mesh(me)
            play = bm.faces.layers.int.get("st_piece")
            fs = [f for f in bm.faces if f[play] == fpid and
                  (zone(dsg(f.calc_center_median())) if it == 0 else eye_ring(dsg(f.calc_center_median()), it))]
            es = list({e for f in fs for e in f.edges})
            bmesh.ops.subdivide_edges(bm, edges=es, cuts=1, use_grid_fill=True, smooth=smooth)
            res.append(bm)
        bl0, bl1 = res
        bl0.verts.ensure_lookup_table(); bl1.verts.ensure_lookup_table()
        assert len(bl0.verts) == len(bl1.verts)
        n_old = len(me.vertices)
        for i in range(n_old, len(bl0.verts)):
            c = dsg(bl0.verts[i].co)
            w = (zone_w(c) if it == 0 else ring_w(c, it)) * smoothstep(zc + 0.30 * hw, zc + 0.45 * hw, c.z)
            bl0.verts[i].co = bl0.verts[i].co.lerp(bl1.verts[i].co, w)
        ngons = [f for f in bl0.faces if len(f.verts) > 4]     # zone-edge faces with a split side: no slivers
        bmesh.ops.triangulate(bl0, faces=ngons, quad_method='BEAUTY', ngon_method='BEAUTY')
        bl0.to_mesh(me); bl0.free(); bl1.free()
    me.update()
    # round the new facets: Taubin smoothing (no shrink), weight 1 inside the zone, 0 at its edge (no seams)
    bm = bmesh.new(); bm.from_mesh(me)
    play = bm.faces.layers.int.get("st_piece")
    sv = [v for v in bm.verts if v.link_faces and all(f[play] == fpid for f in v.link_faces)]

    def zw(p):
        return smoothstep(0.86 * hw, 0.62 * hw, abs(p.x)) * smoothstep(L["nose"] - 0.07 * H, L["nose"] - 0.035 * H, p.y) \
            * smoothstep(L["eye"] + 2.3 * r, L["eye"] + 1.85 * r, p.y) * smoothstep(zc + 0.30 * hw, zc + 0.45 * hw, p.z)
    wts = [(v, 0.5 * zw(dsg(v.co)), [e.other_vert(v) for e in v.link_edges]) for v in sv]
    wts = [t for t in wts if t[1] > 0]
    for _ in range(6):
        for lam in (1.0, -1.04):
            new = [v.co + (sum((n.co for n in nb), Vector()) / len(nb) - v.co) * (w * lam) for v, w, nb in wts]
            for (v, _, _), c in zip(wts, new):
                v.co = c
    bm.to_mesh(me); bm.free(); me.update()

    # ---- 2. face-skin BVH (face piece only: rays must not land on the hair)
    pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
    fpolys = [p for p, k in zip(me.polygons, pid) if k == fpid]
    fverts = sorted({v for p in fpolys for v in p.vertices})

    def face_bvh():
        pts = [dsg(v.co) for v in me.vertices]
        return BVHTree.FromPolygons([tuple(p) for p in pts], [tuple(p.vertices) for p in fpolys]), pts
    bvh, pts = face_bvh()

    def surf_z(x, y):
        hit = bvh.ray_cast(V(x, y, 0.3), V(0, 0, -1), 1.0)
        return hit
    ex = P3["ex"] * hw; ey = L["eye"]
    centres = []
    for o in (1, -1):
        hit = surf_z(o * ex, ey)
        z = hit[0].z + P3["protrude"] * r - r
        centres.append(V(o * ex, ey, z))
    E2 = e3_eyes(C, centres)
    rep["eyeCentres"] = [[round(v, 5) for v in c] for c in centres]

    # ---- 3. eye bones to the eyeball centres (the bones have no weights; clips key them at rest)
    bpy.ops.object.select_all(action='DESELECT')
    bpy.context.view_layer.objects.active = rig; rig.select_set(True)
    bpy.ops.object.mode_set(mode='EDIT')
    for E in E2:
        eb = rig.data.edit_bones["eye" + E["side"]]
        eb.head = to_bl(E["c"]); eb.tail = to_bl(E["c"] + V(0, 0, 0.004)); eb.roll = 0.0
    bpy.ops.object.mode_set(mode='OBJECT')

    # ---- 4. sculpt: nose, brow ridge, sockets (skin under the lids sinks behind the eyeball)
    Ln = L["nose"]; tipY = Ln + 0.040 * H
    up_w, lo_w, base_w = e3_margins(P3, {"wide": 1.0})

    def sink_target(E, p):
        """Push face skin back along the eye's forward axis (x / y kept: no stretched slivers) so that, seen from
        the front, it hides behind the eyeball inside the widest opening and just under the lid sphere in the lid
        band, then rises past the crease. Classified by the lid-sphere point in front of it."""
        q = E["R"].transposed() @ (p - E["c"])
        RL = P3["lidOut"] * r; rho2 = q.x * q.x + q.y * q.y
        if rho2 >= (RL * 1.25) ** 2 or q.z < -0.3 * r:
            return None
        rho = math.sqrt(rho2)
        zl = math.sqrt(max(RL * RL - rho2, 0.0))
        a = math.degrees(math.atan2(E["o"] * q.x, zl)); b = math.degrees(math.atan2(q.y, math.hypot(q.x, zl)))
        A0, A1 = -P3["Ain"], P3["Aout"]
        ac = min(A1, max(A0, a))
        bu, bl_, bb = up_w(ac), lo_w(ac), base_w(ac)
        mv = (b - bu) if b >= bb else (bl_ - b)
        mh = max(0.0, A0 - a, a - A1)
        m = math.hypot(max(mv, 0.0), mh) if (mv > 0 or mh > 0) else mv
        if rho >= RL:
            m = max(m, 30.0)
        cr = (E3_CREASE[0] if b >= bb else E3_CREASE[1]) if mh <= 0 else E3_CREASE[0]

        def sph(R_):
            return math.sqrt(max(R_ * R_ - rho2, 0.0))
        if m < 0.5:
            zt = sph(0.9 * r)                              # in the widest opening: behind the eyeball
        elif m < cr:                                       # under the lid band: rises toward the lid's top edge
            zt = lerp(sph(0.9 * r), sph(r * lerp(1.04, 1.09, smoothstep(1.5, cr, m))), smoothstep(0.5, 1.5, m))
        else:                                              # past the crease (the lid tucks under here): skin out
            zt = sph(1.09 * r) + (m - cr) * 0.035 * r
        if zt >= q.z + 0.12 * r:
            return None
        k = 0.03 * r                                       # soft min
        nz = -k * math.log(math.exp(-q.z / k) + math.exp(-zt / k))
        return E["c"] + E["R"] @ V(q.x, q.y, nz), m < cr

    moved = 0
    sink = {}
    for i in fverts:
        p = pts[i]
        if p.z < zc:
            continue
        q = p.copy(); x, y = p.x, p.y
        g = math.exp(-(x / (0.085 * hw)) ** 2 - ((y - tipY) / (0.050 * H)) ** 2)            # round tip
        q.z += 0.00085 * g
        for sx in (-1, 1):                                                                  # slimmer bridge sides
            g = math.exp(-((x - sx * 0.15 * hw) / (0.07 * hw)) ** 2) * smoothstep(tipY + 0.01 * H, tipY + 0.06 * H, y) \
                * smoothstep(ey + 0.6 * r, ey - 0.3 * r, y)
            q.z -= 0.00022 * g
        for sx in (-1, 1):
            g = math.exp(-((x - sx * 0.13 * hw) / (0.065 * hw)) ** 2 - ((y - (Ln + 0.016 * H)) / (0.038 * H)) ** 2)
            q.z += 0.00028 * g; q.x += sx * 0.00005 * g                                    # alae
            g = math.exp(-((x - sx * 0.062 * hw) / (0.032 * hw)) ** 2 - ((y - (Ln + 0.003 * H)) / (0.016 * H)) ** 2)
            q.z -= 0.00020 * g                                                              # nostrils
        g = math.exp(-((y - (ey + 1.50 * r)) / (0.75 * r)) ** 2) * smoothstep(0.95 * hw, 0.45 * hw, abs(x)) \
            * (1 - 0.45 * math.exp(-(x / (0.13 * hw)) ** 2))
        q.z += 0.00042 * g                                                                  # brow ridge
        dsum, hard = V(0, 0, 0), False
        for E in E2:
            t = sink_target(E, q)
            if t is not None:
                dsum += t[0] - q; hard |= t[1]
        sink[i] = (q, dsum, hard)
    # the sink as a displacement field, smoothed over the mesh (no radial ripples), then hard under the lids again
    nbr = {i: [] for i in sink}
    for e in me.edges:
        a_, b_ = e.vertices
        if a_ in nbr and b_ in nbr:
            nbr[a_].append(b_); nbr[b_].append(a_)
    disp = {i: v[1] for i, v in sink.items()}
    for _ in range(6):
        disp = {i: (disp[i] * 0.5 + sum((disp[j] for j in nbr[i]), V(0, 0, 0)) * (0.5 / len(nbr[i]))) if nbr[i] else disp[i]
                for i in disp}
    newp = {}
    for i, (q, d0, hard) in sink.items():
        newp[i] = q + (d0 if hard else disp[i])
    # relax the skin around the lids (the radial pull leaves thin triangles that shade as streaks); the band under
    # the lids stays exactly where the sink put it
    soft = [i for i, (q, d0, hard) in sink.items() if not hard and (d0.length > 1e-7 or disp[i].length > 1e-7)]
    ring = set(soft)
    for i in list(soft):
        ring.update(j for j in nbr[i] if not sink[j][2])
    soft = [i for i in ring if nbr[i]]
    for _ in range(10):
        for lam in (0.55, -0.57):
            upd = {i: newp[i] + (sum((newp[j] for j in nbr[i]), V(0, 0, 0)) / len(nbr[i]) - newp[i]) * lam for i in soft}
            newp.update(upd)
    for i, q2 in newp.items():
        if (q2 - pts[i]).length > 1e-9:
            me.vertices[i].co = bl(q2); moved += 1
    me.update()
    rep["sculptedVerts"] = moved
    bvh, pts = face_bvh()

    def face_hit(x, y):
        hit = bvh.ray_cast(V(x, y, 0.3), V(0, 0, -1), 1.0)
        if hit[0] is None:
            return V(x, y, zc), V(0, 0, 1)
        n = hit[1].normalized()
        return hit[0], (n if n.z >= 0 else -n)

    # ---- 5. eyelids into the body (page material, skin of the face; UV0 = the nearest face texel)
    uv0 = me.uv_layers["UVMap"]; vuv = {}
    for p in fpolys:
        for li in p.loop_indices:
            vuv.setdefault(me.loops[li].vertex_index, tuple(uv0.data[li].uv))
    kd = KDTree(len(vuv))
    for i, vi in enumerate(vuv):
        kd.insert(V(pts[vi].x, pts[vi].y, 0.0), vi)
    kd.balance()
    lid_rest = {}
    lid_quads = {}
    for E in E2:
        vs, qs = e3_lids(E, P3, r, {})
        lid_rest[E["side"]] = vs; lid_quads[E["side"]] = e3_lid_orient(E, vs, qs)
    bm = bmesh.new(); bm.from_mesh(me)
    n0 = len(bm.verts)
    dl = bm.verts.layers.deform.verify(); gi = body.vertex_groups["head"].index
    l_uv = bm.loops.layers.uv["UVMap"]; l_dec = bm.loops.layers.uv["decal"]
    f_reg = bm.faces.layers.int.get("st_region"); f_pc = bm.faces.layers.int.get("st_piece")
    lid_index = {}
    for E in E2:
        base_i = len(bm.verts)
        nv = []
        for p in lid_rest[E["side"]]:
            v = bm.verts.new(bl(p)); v[dl][gi] = 1.0; nv.append(v)
        lid_index[E["side"]] = (base_i, len(nv))
        for q in lid_quads[E["side"]]:
            f = bm.faces.new([nv[i] for i in q]); f.smooth = True
            f[f_reg] = skin; f[f_pc] = fpid
            for lp, i in zip(f.loops, q):
                p = lid_rest[E["side"]][i]
                _, vi, _ = kd.find(V(p.x, p.y, 0.0))
                lp[l_uv].uv = vuv[vi]; lp[l_dec].uv = (-1.0, -1.0)
    bm.to_mesh(me); bm.free(); me.update()
    rep["lidVerts"] = len(me.vertices) - n0

    # ---- 6. blend shapes on the body: lids (recomputed per state) + skin fields
    body.shape_key_add(name="Basis", from_mix=False)
    basis = [v.co.copy() for v in me.vertices]
    skin_pts = [(i, pts[i]) for i in fverts if pts[i].z > zc and abs(pts[i].x) < 0.95 * hw
                and L["chin"] < pts[i].y < L["eye"]]
    for key in E3_SHAPES:
        kb = body.shape_key_add(name=key, from_mix=False); kb.value = 0.0     # Blender 5 starts new keys at 1.0
        co = [c.copy() for c in basis]
        if key.endswith("_b"):                   # second half of a blink, on top of the first half
            half = {E["side"]: e3_lids(E, P3, r, e3_lid_state(key[:-2] + "_a", E["side"]))[0] for E in E2}
        for E in E2:
            stt = e3_lid_state(key, E["side"])
            if not stt:
                continue
            vs, _ = e3_lids(E, P3, r, stt)
            b0, nl = lid_index[E["side"]]
            for k in range(nl):
                p = vs[k] if not key.endswith("_b") else lid_rest[E["side"]][k] + (vs[k] - half[E["side"]][k])
                co[b0 + k] = bl(p)
        if key in ("cheekRaise", "smile", "frown"):
            for i, p in skin_pts:
                dv = e3_skin_field(C, p, key)
                if dv.length > 1e-7:
                    co[i] = bl(p + dv)
        kb.data.foreach_set("co", [c for v in co for c in v])
    rep["bodyShapes"] = len(E3_SHAPES)

    # ---- 7. eyeballs: rigid on eyeL / eyeR
    eyeballs = []
    mat_eye = bpy.data.materials.get("js_eye") or bpy.data.materials.new("js_eye")
    mat_lines = bpy.data.materials.get("js_eyeLines") or bpy.data.materials.new("js_eyeLines")
    for E in E2:
        lv, lf, luv = e3_eyeball(P3, r)
        o = new_mesh_obj(f"{ch}_eye{E['side']}", [to_bl(E["c"] + p) for p in lv], lf)
        meo = o.data
        u0 = meo.uv_layers.new(name="UVMap"); u1 = meo.uv_layers.new(name="decal")
        for poly in meo.polygons:
            poly.use_smooth = True
            for li in poly.loop_indices:
                u0.data[li].uv = luv[meo.loops[li].vertex_index]; u1.data[li].uv = (-1.0, -1.0)
        a1 = meo.attributes.new("st_piece", 'INT', 'FACE'); a1.data.foreach_set("value", [piece_id((ch, "eyes", 0))] * len(meo.polygons))
        a2 = meo.attributes.new("st_region", 'INT', 'FACE'); a2.data.foreach_set("value", [region_id(ch, "eyes")] * len(meo.polygons))
        meo.materials.append(mat_eye)
        o.parent = rig; o.parent_type = 'BONE'; o.parent_bone = "eye" + E["side"]
        o.matrix_parent_inverse = Matrix.Identity(4)
        bpy.context.view_layer.update()
        o.matrix_world = Matrix.Translation((sheet[0], 0, sheet[1]))
        bpy.context.view_layer.update()
        eyeballs.append(o); props.append(o)

    # ---- 8. lines: brows + lash lines + lashes, skinned to head, same blend shapes
    def lines_geo(key):
        vs_all, qs_all, uv_all = [], [], []
        for E in E2:
            lst = e3_lid_state(key, E["side"]) if key else {}
            if key and key.endswith("_b"):
                v1, q1 = e3_lash_geo(E, P3, r, e3_lid_state(key, E["side"]))
                vh, _ = e3_lash_geo(E, P3, r, e3_lid_state(key[:-2] + "_a", E["side"]))
                v0, _ = e3_lash_geo(E, P3, r, {})
                v1 = [a + (b - c) for a, b, c in zip(v0, v1, vh)]
            else:
                v1, q1 = e3_lash_geo(E, P3, r, lst)
            k0 = len(vs_all); vs_all += v1; qs_all += [[k0 + i for i in q] for q in e3_orient(v1, q1)]
            uv_all += [E3_UV["lash"]] * len(v1)
            v2, q2 = e3_brow_geo(C, P3, r, E, face_hit, e3_brow_state(key, E["side"]) if key else {})
            k0 = len(vs_all); vs_all += v2; qs_all += [[k0 + i for i in q] for q in e3_orient(v2, q2)]
            uv_all += [E3_UV["brow"]] * len(v2)
        return vs_all, qs_all, uv_all
    vs0, qs0, uvl = lines_geo(None)
    lo_ = new_mesh_obj(f"{ch}_eyeLines", [to_bl(p) for p in vs0], qs0)
    mel = lo_.data
    u0 = mel.uv_layers.new(name="UVMap"); u1 = mel.uv_layers.new(name="decal")
    for poly in mel.polygons:
        poly.use_smooth = True
        for li in poly.loop_indices:
            u0.data[li].uv = uvl[mel.loops[li].vertex_index]; u1.data[li].uv = (-1.0, -1.0)
    a1 = mel.attributes.new("st_piece", 'INT', 'FACE'); a1.data.foreach_set("value", [piece_id((ch, "eyeLines", 0))] * len(mel.polygons))
    a2 = mel.attributes.new("st_region", 'INT', 'FACE'); a2.data.foreach_set("value", [region_id(ch, "eyeLines")] * len(mel.polygons))
    mel.materials.append(mat_lines)
    g = lo_.vertex_groups.new(name="head"); g.add(list(range(len(mel.vertices))), 1.0, 'REPLACE')
    lo_.parent = rig; lo_.matrix_parent_inverse = Matrix.Identity(4)
    bpy.context.view_layer.update()
    lo_.matrix_world = Matrix.Translation((sheet[0], 0, sheet[1])); bpy.context.view_layer.update()
    am = lo_.modifiers.new("Armature", 'ARMATURE'); am.object = rig
    lo_.shape_key_add(name="Basis", from_mix=False)
    for key in E3_SHAPES:
        kb = lo_.shape_key_add(name=key, from_mix=False); kb.value = 0.0
        vs, _, _ = lines_geo(key)
        kb.data.foreach_set("co", [c for p in vs for c in to_bl(p)])
    props.append(lo_)
    rep["lineVerts"] = len(mel.vertices)
    rep["trisAfter"] = tri_count([body] + props)
    PART_TRIS[f"{ch}_eyes3d"] = rep["trisAfter"] - rep["trisBefore"]
    rep["closedScale"] = C.lid["closedScale"]
    return rep


def e3_json(ch, rep):
    """face3d_<ch>.json for the runtime (DGFace3D.cs, JsonUtility shapes)."""
    def shapes(c):
        if c in ("blinkL", "blinkR"):
            return [{"shape": c + "_a", "from": 0.0, "to": 0.5}, {"shape": c + "_b", "from": 0.5, "to": 1.0}]
        return [{"shape": c, "from": 0.0, "to": 1.0}]
    controls = ["blinkL", "blinkR", "lidsWide", "squint", "lidsSad", "cheekRaise", "smile", "frown", "browUpL",
                "browUpR", "browDown", "browInnerUp"]
    ex = []
    for name, d in E3_EXPR[ch].items():
        ex.append({"name": name, "gazeYaw": d.get("gazeYaw", 0.0), "gazePitch": d.get("gazePitch", 0.0),
                   "weights": [{"c": k, "w": v} for k, v in d.items() if k in controls]})
    return {
        "_doc": "3D face of one actor (pipeline/js_characters.py eyes3d; runtime DGFace3D.cs). controls = named 0..1 "
                "inputs; each drives blend shapes (same names on every SkinnedMeshRenderer that has them), a range "
                "of the control mapped onto the shape (two halves = an in-between). expressions = face names of "
                "faces.json -> control weights; the runtime blends them over blendSec. Gaze in degrees.",
        "version": 1, "id": ch, "defaultFace": DEFAULT_EXPR[ch], "blendSec": 0.25,
        "headBone": "head", "eyeBones": ["eyeL", "eyeR"],
        "eyeMeshes": [f"{ch}_eyeL", f"{ch}_eyeR"], "lineMeshes": [f"{ch}_eyeLines"], "texture": f"eyes_{ch}.png",
        "gaze": {"yawMax": 24.0, "pitchUp": 13.0, "pitchDown": 16.0, "saccadeYaw": 2.2, "saccadePitch": 1.3,
                 "saccadeMin": 0.9, "saccadeMax": 2.8, "smooth": 0.05, "lidFollowDown": 0.30, "lidFollowUp": 0.30,
                 "lidFollowUpControl": "lidsWide"},
        "blink": {"left": "blinkL", "right": "blinkR", "minGap": 2.2, "maxGap": 5.5, "closeSec": 0.07,
                  "openSec": 0.13, "doubleChance": 0.15, "onGazeShift": 15.0,
                  "lidBone": "eyelids", "lidOpen": 1.0, "lidClosed": rep.get("closedScale", 12.78)},
        "suppressByBlink": ["lidsWide", "squint", "lidsSad"],
        "talkBrow": 0.30, "talkBrowControls": ["browUpL", "browUpR"],
        "controls": [{"name": c, "shapes": shapes(c)} for c in controls],
        "expressions": ex}


def e3_preview_materials():
    """Blender look-dev materials for the eyeballs and lines (EEVEE): the atlas, glossy eyeballs."""
    tex = None
    for ch in E3:
        if os.path.exists(E3_TEX[ch]):
            tex = bpy.data.images.load(E3_TEX[ch], check_existing=True)
    if tex is None:
        return

    def mk(name, rough, spec, coat):
        m = bpy.data.materials.get(name) or bpy.data.materials.new(name)
        m.use_nodes = True; nt = m.node_tree; nt.nodes.clear()
        out = nt.nodes.new("ShaderNodeOutputMaterial"); b = nt.nodes.new("ShaderNodeBsdfPrincipled")
        nt.links.new(b.outputs[0], out.inputs[0])
        t = nt.nodes.new("ShaderNodeTexImage"); t.image = tex; t.interpolation = 'Cubic'; t.extension = 'EXTEND'
        uv = nt.nodes.new("ShaderNodeUVMap"); uv.uv_map = "UVMap"
        nt.links.new(uv.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
        b.inputs["Roughness"].default_value = rough
        for k, v in (("Specular IOR Level", spec), ("Coat Weight", coat), ("Coat Roughness", 0.03)):
            try:
                b.inputs[k].default_value = v
            except Exception:
                pass
        return m
    me_ = mk("pv_e3_eye", 0.35, 0.5, 1.0); ml = mk("pv_e3_lines", 0.75, 0.2, 0.0)
    for o in all_meshes():
        if o.name.endswith(("_eyeL", "_eyeR")):
            o.data.materials.clear(); o.data.materials.append(me_)
        elif o.name.endswith("_eyeLines"):
            o.data.materials.clear(); o.data.materials.append(ml)


def e3_is_part(o):
    return o.name.endswith(("_eyeL", "_eyeR", "_eyeLines"))


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
    # ---- ID render (front ortho, 2x art rect, no AA): one colour per (piece, region); eyelids + hidden props hidden
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
                       "alpha 0; eyelids and hidden-by-default props hidden (Joseph's coat is shown: it is printed)",
               "size": [s.render.resolution_x, s.render.resolution_y], "ids": ids},
              open(os.path.join(WORK, "id_2x.json"), "w"), indent=1)
    for o in all_meshes():
        o.hide_render = False
    anchor_info = apply_pixel_anchors(os.path.join(WORK, "id_2x.png"), ids)
    fix_info = fix_uvs_by_id(os.path.join(WORK, "id_2x.png"), ids)
    report["uvFixByIdRender"] = fix_info
    for ch in E3_CHARS:                          # 3D eyes: after the ID render + UV fixes (the sheet is unchanged)
        if ch in built:
            C, rig, body, props, rep = built[ch]
            e3rep = eyes3d_apply(ch, C, rig, body, props)
            report["chars"][ch]["eyes3d"] = e3rep
            report["chars"][ch]["tris"] = tri_count([body] + props)
            report["chars"][ch]["props"] = {o.name: [o.parent_bone, tri_count([o])] for o in props}
            json.dump(e3_json(ch, e3rep), open(E3_JSON[ch], "w"), indent=1)
            print(f"[{ch}] eyes3d", json.dumps(e3rep))
    for ch in ONLY:
        if ch in E3 and ch not in E3_CHARS and os.path.exists(E3_JSON[ch]):
            os.remove(E3_JSON[ch])                # JS_EYES3D=0: the runtime falls back to the decal face
    # ---- regions_characters.json
    regions_out = {"version": 1, "generatedBy": "pipeline/js_characters.py",
                   "note": "Per character: colourable regions (face attribute st_region), the mesh parts that carry "
                           "them, demo colour, bbox on the sheet (x, y in art units, y up from the art rect bottom), "
                           "and anchors (regions too small to colour take a constant UV inside a larger region; hidden "
                           "props take theirs from a printed region). ID render for the line art: "
                           "id_characters_2x.png/.json (same scheme as D&G id_2x).",
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
        props_out = {}
        for b, v in PROPS[ch].items():
            props_out[b] = {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v,
                            "skinned": b in SKINNED_PROPS.get(ch, set())}
            if b in SKINNED_PROPS.get(ch, set()):
                props_out[b]["note"] = ("skinned to the body bones + coatL/R; its mesh node is nested under the '%s' "
                                        "joint in the GLB so '%s/%s' toggles it" % (b, ch, b))
        regions_out["characters"][ch] = {
            "height": CONTRACT_HEIGHT[ch], "bboxSheet": [round(v, 4) for v in allbb], "regions": regs,
            "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                          "files": {e: f"docs/joseph/design/faces/{ch}_{e}.png" for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z",
                         "bakedPose": [[b, d] for b, _, d in REST_BAKE.get(ch, [])],
                         "note": "Jacob: the stoop (degrees about design X) is baked into the rest skeleton" if ch in REST_BAKE else ""},
            "props": props_out,
            "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
    if os.path.exists(os.path.join(MODEL, "regions_characters.json")) and len(ONLY) < len(CHARS):
        old = json.load(open(os.path.join(MODEL, "regions_characters.json")))
        for ch, v in old.get("characters", {}).items():
            regions_out["characters"].setdefault(ch, v)
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
    if SHEET_SRC == "defaults":
        json.dump({"note": "default sheet positions used by js_characters.py (assets/joseph/design.json had none); the "
                           "Set + sheet role owns the real values in design.json characters.<id>.sheetX/sheetY",
                   "artHeightUnits": ART_H, "characters": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in CHARS}},
                  open(os.path.join(MODEL, "characters_layout.json"), "w"), indent=1)
    import shutil
    if len(ONLY) == len(CHARS):
        shutil.copy(os.path.join(WORK, "id_2x.png"), os.path.join(MODEL, "id_characters_2x.png"))
        shutil.copy(os.path.join(WORK, "id_2x.json"), os.path.join(MODEL, "id_characters_2x.json"))
    # ---- final material, export (character-local), blend
    page = page_material()
    for o in all_meshes():
        me = o.data; me.materials.clear()
        if e3_is_part(o):                          # 3D eyes: own materials (the engine assigns DGEye / lines)
            me.materials.append(bpy.data.materials.get("js_eyeLines" if o.name.endswith("_eyeLines") else "js_eye"))
        else:
            me.materials.append(page)
        me.polygons.foreach_set("material_index", [0] * len(me.polygons))
    for o in all_meshes():                       # TEXCOORD_0 = page (UVMap), TEXCOORD_1 = face decal
        assert [u.name for u in o.data.uv_layers][:2] == ["UVMap", "decal"], (o.name, [u.name for u in o.data.uv_layers])
        o.data.uv_layers.active_index = 0
        o.data.uv_layers["UVMap"].active_render = True
    nested = {}
    for ch in ONLY:
        C, rig, body, props, rep = built[ch]
        rig.location = (0, 0, 0); bpy.context.view_layer.update()
        bpy.ops.object.select_all(action='DESELECT')
        rig.select_set(True)
        for o in rig.children: o.select_set(True)
        bpy.context.view_layer.objects.active = rig
        path = os.path.join(MODEL, f"{ch}.glb")
        bpy.ops.export_scene.gltf(filepath=path, use_selection=True, export_yup=True,
                                  export_apply=False, export_skins=True, export_animations=False, export_def_bones=False,
                                  export_texcoords=True, export_materials='EXPORT', export_morph=ch in E3_CHARS)
        nested.update(nest_skinned_props(path, ch))
        rig.location = (SHEET[ch][0], 0, SHEET[ch][1])
    bpy.context.view_layer.update()
    report["nestedSkinnedProps"] = nested
    report["partTris"] = PART_TRIS
    json.dump(report, open(os.path.join(WORK, "build_report.json"), "w"), indent=1, default=str)
    sc()["js_regions"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    if len(ONLY) == len(CHARS):
        bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    else:
        bpy.ops.wm.save_as_mainfile(filepath=os.path.join(WORK, "characters_partial.blend"), compress=True)
    print("BUILD_REPORT", json.dumps({ch: {k: v for k, v in r.items() if k != "bones"} for ch, r in report["chars"].items()}))


GOLD = {"gold", "collar", "trim", "nemesA"}


class _RegionLookup(dict):
    def __missing__(self, r):
        tab = json.loads(sc().get("js_regions", "[]"))
        for i, k in enumerate(tab):
            self[i + 1] = k.split(".")[1]
        return dict.__getitem__(self, r)


REGION_OF = _RegionLookup()


def _open_built():
    p = BLEND if len(ONLY) == len(CHARS) or not os.path.exists(os.path.join(WORK, "characters_partial.blend")) \
        else os.path.join(WORK, "characters_partial.blend")
    bpy.ops.wm.open_mainfile(filepath=p)


def mode_preview():
    _open_built()
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
    e3_preview_materials()
    cam = camera()

    def show(chs, props=False, hide=()):
        for o in all_meshes():
            if o.name not in ("floor", "backdrop"):
                o.hide_render = o.name.split("_")[0] not in chs or (is_hidden_prop(o) and not props) or o.name in hide
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
        hide = (f"{ch}_coat",) if ch == "joseph" else ()
        show([ch], props=True, hide=hide)
        turntable(cam, Vector((x, 0, zb + Hh * 0.62)), 28, Hh * 1.9, Hh * 0.10, 60)
        render(os.path.join(WORK, f"pv_{ch}_props.png"))
        if ch == "joseph":
            turntable(cam, Vector((x, 0, zb + Hh * 0.62)), 160, Hh * 1.9, Hh * 0.10, 60)
            render(os.path.join(WORK, f"pv_{ch}_propsback.png"))
            show([ch], hide=hide)
            turntable(cam, Vector((x, 0, zb + Hh * 0.50)), 20, Hh * 2.6, Hh * 0.14, 60)
            render(os.path.join(WORK, f"pv_{ch}_plain.png"))
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
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1200
        turntable(cam, Vector((0.0, 0, 0.36)), 10, 1.75, 0.20, 50); render(os.path.join(WORK, "pv_all.png"))
    print("PREVIEW done")


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
    if ch == "joseph":
        bend(rig, "coatL", V(1, 0, 0), -22)
    if ch == "jacob":
        bend(rig, "shawl2", V(1, 0, 0), -25)
    if ch == "brother":
        bend(rig, "bag", V(0, 0, 1), 18)
    if ch == "pharaoh":
        bend(rig, "apron1", V(1, 0, 0), -20); bend(rig, "belly", V(1, 0, 0), -16)
    bpy.context.view_layer.update()


def mode_posetest():
    _open_built()
    setup_eevee((640, 960)); preview_lights()
    imgs = {ch: bpy.data.images.load(os.path.join(FACES, f"{ch}_{DEFAULT_EXPR[ch]}.png"), check_existing=True) for ch in CHARS}
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        ch = o.name.split("_")[0]
        set_face_materials(o, lambda p, r: r, lambda r: preview_material(ch, REGION_OF[r], imgs.get(ch)))
    e3_preview_materials()
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
    """Kit uvcheck (front ortho = the sheet, 3/4, back) + Joseph's colour hand-over: the printed coat, and the
    governor look (coat hidden, head-cloth + collar shown) wearing the same uvproof texture."""
    _open_built()
    tex_path = os.environ.get(ENV + "UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        o.data.materials.clear(); o.data.materials.append(m)
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o) or e3_is_part(o)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    sc().view_settings.view_transform = 'Standard'
    cam = front_ortho_camera()
    bpy.data.objects["backdrop"].hide_render = True
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L_ in ("key", "rim", "fill"):
        bpy.data.objects[L_].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    for L_ in ("key", "rim", "fill"):
        bpy.data.objects[L_].hide_render = False
    bpy.data.objects["backdrop"].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc().render.resolution_x, sc().render.resolution_y = 1600, 1200
    for nm, yaw in (("q34", 30), ("back", 180)):
        turntable(cam, Vector((0.0, 0, 0.36)), yaw, 1.75, 0.20, 50)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    rig = bpy.data.objects.get("joseph_rig")
    if rig:
        x = rig.location.x; zb = rig.location.z; Hh = SPEC["joseph"]["height"]
        sc().render.resolution_x, sc().render.resolution_y = 700, 700

        def look(coat, gov):
            for o in all_meshes():
                if o.name in ("backdrop",):
                    continue
                own = o.name.startswith("joseph_")
                o.hide_render = (not own) or o.name.endswith("_eyelids") or e3_is_part(o) or \
                    (o.name == "joseph_coat" and not coat) or (o.name in ("joseph_nemes", "joseph_collar") and not gov)
        look(True, False)
        turntable(cam, Vector((x, 0, zb + Hh * 0.52)), 20, Hh * 2.7, Hh * 0.12, 60); render(os.path.join(WORK, "uv_coat.png"))
        look(False, True)
        turntable(cam, Vector((x, 0, zb + Hh * 0.66)), 18, Hh * 1.8, Hh * 0.10, 60); render(os.path.join(WORK, "uv_governor.png"))
        turntable(cam, Vector((x, 0, zb + Hh * 0.66)), 150, Hh * 1.8, Hh * 0.10, 60)
        render(os.path.join(WORK, "uv_governor_back.png"))
        look(False, False)
        turntable(cam, Vector((x, 0, zb + Hh * 0.50)), 20, Hh * 2.7, Hh * 0.12, 60); render(os.path.join(WORK, "uv_plain.png"))
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
        parents = {b.name: (b.parent.name if b.parent else None) for b in arms[0].data.bones} if arms else {}
        info = {"armatures": len(arms), "bonesMatch": bones == want, "missing": sorted(set(want) - set(bones)),
                "extra": sorted(set(bones) - set(want)), "actions": len(bpy.data.actions), "meshes": {},
                "parents": {b: parents.get(b) for b in EXTRA_BONES[ch]}}
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
        vis = [o for o in meshes if not (o.name.endswith(("_nemes", "_collar")))]
        h = max((o.matrix_world @ Vector(c)).z for o in vis for c in o.bound_box)
        lo = min((o.matrix_world @ Vector(c)).z for o in vis for c in o.bound_box)
        info["heightTop"] = round(h, 4); info["lowest"] = round(lo, 4)
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps(out))


def mode_eyes3d():
    """Evidence renders of Joseph's head (3D eyes pilot): front / 3/4 / profile and the expression cells.
    JS_E3_BLEND / JS_E3_FACES / JS_E3_TAG render another build (e.g. the old one) the same way."""
    p = os.environ.get(ENV + "E3_BLEND") or BLEND
    faces = os.environ.get(ENV + "E3_FACES") or FACES
    tag = os.environ.get(ENV + "E3_TAG", "new")
    bpy.ops.wm.open_mainfile(filepath=p)
    ch = "joseph"
    setup_eevee((600, 600)); preview_lights()
    img = bpy.data.images.load(os.path.join(faces, f"{ch}_{DEFAULT_EXPR[ch]}.png"), check_existing=True)
    for o in all_meshes():
        if o.name in ("floor", "backdrop"):
            continue
        c_ = o.name.split("_")[0]
        set_face_materials(o, lambda p_, r: r, lambda r: preview_material(c_, REGION_OF[r], img if c_ == ch else None))
        o.hide_render = c_ != ch or is_hidden_prop(o) or o.name.endswith("_eyelids") and False
    e3_preview_materials()
    rig = bpy.data.objects[f"{ch}_rig"]
    body = bpy.data.objects[f"{ch}_body"]
    cam = camera()
    L = landmarks(ch); x = rig.location.x; zb = rig.location.z
    Hd = L["top"] - L["chin"]; hy = zb + (L["top"] + L["chin"]) / 2 - 0.06 * Hd
    keys = body.data.shape_keys.key_blocks if body.data.shape_keys else None
    lines = bpy.data.objects.get(f"{ch}_eyeLines")
    lkeys = lines.data.shape_keys.key_blocks if lines and lines.data.shape_keys else None

    def set_face(name, gyaw=0.0, gpitch=0.0, extra=None):
        w = dict(E3_EXPR[ch].get(name, {})) if name else {}
        gyaw += w.pop("gazeYaw", 0.0); gpitch += w.pop("gazePitch", 0.0)
        w.update(extra or {})
        vals = {}
        for c, v in w.items():
            if c in ("blinkL", "blinkR"):
                vals[c + "_a"] = min(1.0, 2 * v); vals[c + "_b"] = max(0.0, 2 * v - 1)
            else:
                vals[c] = v
        if vals.get("blinkL_a", 0) > 0 or vals.get("blinkR_a", 0) > 0:
            bk = max(vals.get("blinkL_a", 0), vals.get("blinkR_a", 0)) * 0.5 + max(vals.get("blinkL_b", 0), vals.get("blinkR_b", 0)) * 0.5
            for c in ("lidsWide", "squint", "lidsSad"):
                if c in vals:
                    vals[c] *= 1 - bk
        if gpitch < 0:
            f = min(1.0, -gpitch / 16.0) * 0.30
            for sd in "LR":
                vals["blink%s_a" % sd] = max(vals.get("blink%s_a" % sd, 0), min(1, 2 * f))
        for kb_ in ((keys or []), (lkeys or [])):
            for kb in kb_:
                if kb.name != "Basis":
                    kb.value = vals.get(kb.name, 0.0)
        for sd in "LR":
            pb = rig.pose.bones.get("eye" + sd)
            if pb is None:
                continue
            pb.rotation_mode = 'QUATERNION'
            qb = rig.data.bones["eye" + sd].matrix_local.to_quaternion()
            from mathutils import Euler
            qa = Euler((math.radians(gpitch), 0.0, math.radians(gyaw)), 'ZXY').to_quaternion()   # Blender X = pitch, Z = yaw
            pb.rotation_quaternion = qb.inverted() @ qa @ qb
        bpy.context.view_layer.update()

    def decal(name):
        im = bpy.data.images.load(os.path.join(faces, f"{ch}_{name}.png"), check_existing=True)
        for m in bpy.data.materials:
            if m.name.startswith(f"pv_{ch}_") and m.node_tree and m.node_tree.nodes.get("decal"):
                m.node_tree.nodes["decal"].image = im
    set_face(DEFAULT_EXPR[ch]); decal(DEFAULT_EXPR[ch])
    for nm, yaw, el in (("front", 0, 0.10), ("q34", 35, 0.12), ("side", 90, 0.08)):
        turntable(cam, Vector((x, 0, hy)), yaw, Hd * 3.0, Hd * el, 60)
        render(os.path.join(WORK, f"e3_{tag}_{nm}.png"))
    turntable(cam, Vector((x, 0, zb + L["eye"] - 0.02 * Hd)), 12, Hd * 1.25, Hd * 0.02, 60)
    render(os.path.join(WORK, f"e3_{tag}_close.png"))
    turntable(cam, Vector((x, 0, zb + L["eye"] - 0.12 * Hd)), 55, Hd * 1.6, Hd * 0.02, 60)
    render(os.path.join(WORK, f"e3_{tag}_q34close.png"))
    if tag != "new":
        print("EYES3D renders", tag); return
    sc().render.resolution_x, sc().render.resolution_y = 420, 420
    cells = [(e, e, 0, 0, None) for e in EXPRESSIONS[ch]]
    cells += [("blink 50 %", "bright", 0, 0, {"blinkL": 0.5, "blinkR": 0.5}), ("look left", "bright", 20, 0, None),
              ("look up right", "talk", -18, 10, None)]
    for i, (lab, e, gy, gp, ex_) in enumerate(cells):
        set_face(e, gy, gp, ex_); decal(e)
        turntable(cam, Vector((x, 0, hy)), 14, Hd * 2.6, Hd * 0.10, 60)
        render(os.path.join(WORK, f"e3_expr_{i:02d}.png"))
    json.dump([c[0] for c in cells], open(os.path.join(WORK, "e3_expr.json"), "w"))
    print("EYES3D renders", tag, len(cells))


if __name__ == "__main__":
    {"build": mode_build, "preview": mode_preview, "posetest": mode_posetest, "verify": mode_verify,
     "uvcheck": mode_uvcheck, "eyes3d": mode_eyes3d}[MODE]()
