"""Jonah (story pack #8): characters jonah, captain, fish — meshes, rigs, weights, UVs, face decals, previews, GLBs.

Contract: docs/jonah/CONTRACT.md §2-§3 (ids, sizes, sheet slots, bone names, props), look: docs/jonah/DESIGN.md §1,
notes for Animation: docs/jonah/RIG.md. The two humans keep Ruth's method through the shared kit
(pipeline/story_kit/characters.py: procedural quad cages, heads mapped from the D&G base head by landmarks, box-modelled
hands, face decals on UV1 + an `eyelids` blink, UV0 = front page projection with occlusion + ID-render fixes).
New for Jonah:
  * the great fish, a new rig type (root body1 body2 body3 tail jaw finL finR dorsal eyelids): one plump body tube whose
    rings are cut along the mouth line in front of the mouth corner into an upper head and a lower jaw, each closed
    by an inner arc, so the jaw opens on a real cavity (roof, floor, throat, tongue, rounded teeth); round side fins,
    a low dorsal fin, a broad two-lobed tail, big round spots (own region, each its own shape); printed in SIDE view
    (nose to -X) like Daniel's lion: UV0 = mirrored side projection; face decal = side projection on both cheeks;
    eyelids lie on the cheek surface over their whole travel (Daniel's lion bug);
  * fixed colours through the face decal: every decal of a character carries small colour swatches in a corner that
    no surface of that character projects onto (Naomi's baby-face precedent); parts with a fixed colour point their
    UV1 there: the fish's mouth interior (pink -> dark throat), teeth (white), tongue; Jonah's grey temple streaks and
    leather sandals. Their UV0 is anchored to a printed region (they print as detail lines);
  * Jonah: long face, big nose, full short beard, hair to the nape with grey temple streaks, long cream tunic with a
    ragged hem, open brown coat with tan stripes (front panels on coatL / coatR), tan cloth belt wrapped twice over it
    with a hanging end (belt1), sandals, a hidden seaweed clump on the head (seaweed prop bone);
  * the captain: broad chest, big hands, bare forearms, short curly beard, sea-green head-wrap knotted at the back
    with a short tail (wrap1), cream tunic to the knee, wide rust sash with a hanging end (sash1), short navy wrap
    skirt, bare feet.

Run (repo root):
  python3 pipeline/jn_characters.py all                                           # everything below, in order
  python3 pipeline/jn_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/jn_characters.py -- build        # models, rig, GLBs, blend, ID render
  python3 pipeline/jn_characters.py proof                                         # $JN_WORK/uvproof.png
  blender -b --factory-startup --python pipeline/jn_characters.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/jn_characters.py -- uvcheck      # models wearing uvproof.png
  blender -b --factory-startup --python pipeline/jn_characters.py -- posetest     # bend / blink / jaw / cloth / fins
  blender -b --factory-startup --python pipeline/jn_characters.py -- verify       # re-import GLBs, check bones/budget
  python3 pipeline/jn_characters.py compose                                       # preview_*.png contact sheets
Blender: $BLENDER, else `blender` on PATH, else /Applications/Blender.app. Intermediate renders go to $JN_WORK
(default /tmp/jonah_char/work). JN_ONLY=fish (comma list) builds a subset (debug only; finish with a full build).
"""
import sys, os, json, math, random, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/jonah/model")
FACES = os.path.join(ROOT, "docs/jonah/design/faces")
WORK = os.environ.get("JN_WORK", "/tmp/jonah_char/work")
ENV = "JN_"
PAGE_MATERIAL = "jn_page"
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/jonah/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("jonah", "captain", "fish")
HUMANS = ("jonah", "captain")
FISH = ("fish",)
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
FISH_BONES = ["root", "body1", "body2", "body3", "tail", "jaw", "finL", "finR", "dorsal", "eyelids"]
EXTRA_BONES = {"jonah": ["coatL", "coatR", "belt1", "seaweed"], "captain": ["wrap1", "sash1"], "fish": []}


def bone_list(ch):
    return (FISH_BONES if ch in FISH else CONTRACT_BONES) + EXTRA_BONES[ch]


PROPS = {"jonah": {"seaweed": False}, "captain": {}, "fish": {}}     # prop bone -> shown by default
CONTRACT_HEIGHT = {"jonah": 0.36, "captain": 0.38, "fish": 0.20}
FISH_SIZE = dict(length=0.50, height=0.20, width=0.16)
DEFAULT_SHEET = {"jonah": (-0.32, 0.015), "captain": (0.32, 0.015), "fish": (0.0, 0.40)}
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (as Ruth / Daniel)

# ---------------------------------------------------------------------------------------------- palette (DESIGN §3)
PALETTE = {
    "jonah": {"skin": "#E0AE88", "hair": "#4A3526", "tunic": "#F1E7D0", "coat": "#8A5A3B", "stripes": "#D9B57A",
              "belt": "#C9A26A", "sandals": "#7A4E2E", "streaks": "#B9B4AE", "seaweed": "#4E9A3E"},
    "captain": {"skin": "#C98E66", "beard": "#231A16", "wrap": "#4FA58A", "tunic": "#EFE3C8", "sash": "#B5532E",
                "skirt": "#2F4F8A", "vest": "#E0A640", "rope": "#C8A472", "sandals": "#7A4E2E"},
    "fish": {"back": "#1F7F86", "belly": "#BFE9E2", "fins": "#17666C", "spots": "#6CC3BE", "mouth": "#E58A98"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发和胡子", "hair and beard"), "tunic": ("长袍", "tunic"),
    "coat": ("外衣", "coat"), "stripes": ("外衣条纹", "coat stripes"), "belt": ("腰带", "belt"),
    "sandals": ("凉鞋", "sandals"), "streaks": ("白发", "grey streaks"), "seaweed": ("海草", "seaweed"),
    "beard": ("胡子", "beard"), "wrap": ("头巾", "head-wrap"), "sash": ("腰带", "sash"), "skirt": ("短裙", "wrap skirt"),
    "vest": ("背心", "vest"), "rope": ("绳子", "rope"),
    "back": ("背", "back"), "belly": ("肚皮", "belly"), "fins": ("鳍", "fins"), "spots": ("斑点", "spots"),
    "mouth": ("嘴里", "mouth inside"),
}
# fixed-colour parts (DESIGN §1: "fixed-colour detail lines, not regions"): their UV1 points at a swatch in the corner
# of every decal of that character (SWATCHES, decal space 0..1, y up); their UV0 is anchored (ANCHORS) so they print as
# detail lines inside a neighbour
SWATCHES = {
    "jonah": {"streaks": (0.905, 0.925, 0.950, 0.995), "sandals": (0.955, 0.925, 0.995, 0.995)},
    "captain": {"rope": (0.905, 0.925, 0.950, 0.995), "sandals": (0.955, 0.925, 0.995, 0.995)},
    "fish": {"teeth": (0.015, 0.835, 0.115, 0.905), "tongue": (0.140, 0.835, 0.280, 0.905),
             "mouth": (0.015, 0.935, 0.280, 0.990)},      # mouth: a strip, throat (left) -> lips (right)
}
SWATCH_COL = {"streaks": (158, 152, 146), "sandals": (122, 78, 46), "teeth": (252, 250, 244), "tongue": (226, 100, 122),
              "rope": (200, 164, 114),
              "mouth": ((112, 30, 46), (238, 140, 156))}
# regions too small to colour on A4 (or fixed-colour detail): constant UV0 deep inside a printed region
ANCHORS = {
    "jonah": {"sandals": "jonah.tunic", "streaks": "jonah.hair"},   # sandals: fixed colour (decal); UV0 only needs a clean texel
    "captain": {"sandals": "captain.tunic", "rope": "captain.tunic"},   # fixed colours (decal swatches)
    "fish": {"mouth": "fish.belly"},
}
# hidden-by-default props are not printed: their regions sample a printed region of similar colour (first target that
# exists wins; "set.<region>" = a region of the set's printed drawings); design.json characters.<id>.propUV wins
PROP_ANCHORS = {
    "jonah": {"seaweed": ["set.leaves", "set.plantLeaves", "set.plant", "fish.fins"]},
}
# parts whose printed area is a sliver: every face of (part, region) takes one UV inside a larger region
PART_ANCHORS = {ch: {("handL", "skin"): f"{ch}.FACE", ("handR", "skin"): f"{ch}.FACE",
                     ("legL", "skin"): f"{ch}.FACE", ("legR", "skin"): f"{ch}.FACE"} for ch in HUMANS}
PART_ANCHORS["captain"].update({("armL", "skin"): "captain.FACE", ("armR", "skin"): "captain.FACE",
                                ("kneeL", "skin"): "captain.FACE", ("kneeR", "skin"): "captain.FACE"})
PART_ANCHORS["jonah"].update({("cuffs", "stripes"): "jonah.stripes",          # cuffs print as detail lines
                              ("coatTrim", "coat"): "jonah.coat",             # piping round the tan front bands
                              ("coatHem", "coat"): "jonah.coat",              # rolled hem under the tan bands
                              ("headband", "belt"): "jonah.belt",             # twisted head cloth (2026-11-15)
                              ("beltFringe", "belt"): "jonah.belt"})          # fringe on the hanging belt end

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
    # Jonah: about forty-five, a long face, a big nose, heavy brows, a full short beard (0.36 with the hair)
    "jonah": scaled(KING, 0.985, 1.0, height=0.36, top=0.353, chin=0.287, hw=0.0212, jaw=0.08, cheek=0.12,
                    chin_narrow=0.03, noseH=0.0038, nose_w=1.26, nose_long=0.28, brow=1.20, lips=0.85, chinAmt=0.6,
                    sockets=0.90, cheekbones=0.95, fr=dict(eye=0.500, brow=0.590, nose=0.282, mouth=0.168)),
    # the captain: fifty, weathered, round cheeks, broad chest, big hands (0.38 with the head-wrap)
    "captain": scaled(KING, 1.05, 1.16, height=0.38, jaw=0.20, cheek=0.56, noseH=0.0033, nose_w=1.25, brow=1.05,
                      lips=0.95, chinAmt=0.5, cheekbones=0.85, footScale=1.30,
                      fr=dict(eye=0.486, brow=0.578, nose=0.268, mouth=0.160)),
}
SPEC["captain"]["handDims"] = {k: v * 1.22 for k, v in SPEC["captain"]["handDims"].items()}
SPEC["captain"]["handDims"]["armR"] *= 1.15
SPEC["captain"]["hand"] *= 1.12
SPEC["jonah"]["handDims"] = {k: v * 1.15 for k, v in SPEC["jonah"]["handDims"].items()}
SPEC["jonah"]["hand"] *= 1.10
FIST = set()
FIST_BEND = {}
# polish 2026-11-15: bigger, rounder, warmer eyes (child appeal); the lid closes at the same eyelids.sy (12.78)
# because the kit's lid travel scales with the eye height
EYE = {"jonah": (0.405, 0.330, 0.228), "captain": (0.410, 0.300, 0.214)}

EXPRESSIONS = {"jonah": ["grumpy", "talk", "shock", "ashamed", "yuck", "pray", "sorry", "sulk", "happy", "wail", "soft"],
               "captain": ["jolly", "talk", "shout", "worried", "torn", "amazed"],
               "fish": ["calm", "hungry", "gulp", "oops", "happy"]}
DEFAULT_EXPR = {"jonah": "grumpy", "captain": "jolly", "fish": "calm"}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "jonah": {"idle": "grumpy", "talk": "talk", "walk": "grumpy", "tiptoe": "sorry", "stomp_walk": "sulk",
              "listen_up": "shock", "refuse": "sulk", "sleep_curl": "pray", "wake_startled": "shock",
              "ashamed": "ashamed", "fall_in": "shock", "sit_hold_nose": "yuck", "kneel_pray": "pray",
              "tumble_out": "shock", "sit_dazed": "sorry", "stand_up": "soft", "nod_ok": "soft", "proclaim": "talk",
              "surprised": "shock", "sit_sulk": "sulk", "relax_happy": "happy", "wail": "wail", "look_city": "soft",
              "wave": "soft"},
    "captain": {"idle": "jolly", "talk": "talk", "walk": "jolly", "greet": "jolly", "steer_hard": "worried",
                "shake_awake": "shout", "refuse_hands": "torn", "heave": "torn", "amazed": "amazed"},
    "fish": {"idle": "calm", "swim": "calm", "gulp": "gulp", "burp": "oops", "spit": "gulp", "wave_fin": "happy"},
}

# ---------------------------------------------------------------------------------------------- the great fish
# Model space: nose toward +Z, belly on y = 0, root under the middle of the length. Sections of the body tube, nose ->
# peduncle: (z, top y, bottom y, half width). The mouth line / belly line ym(z) cuts every ring into an upper arc
# (back) and a lower arc (belly, lower jaw); in front of the mouth corner FISH_MOUTH["zc"] the cut is open.
FISH_BODY = [
    (0.2500, 0.1080, 0.0660, 0.0160), (0.2465, 0.1240, 0.0490, 0.0340), (0.2405, 0.1390, 0.0340, 0.0470),
    (0.2320, 0.1520, 0.0220, 0.0570), (0.2210, 0.1620, 0.0130, 0.0650), (0.2060, 0.1700, 0.0070, 0.0705),
    (0.1860, 0.1765, 0.0035, 0.0745), (0.1630, 0.1800, -0.0002, 0.0770), (0.1350, 0.1820, -0.0006, 0.0785),
    (0.1000, 0.1822, -0.0006, 0.0790), (0.0600, 0.1806, 0.0005, 0.0780), (0.0200, 0.1770, 0.0045, 0.0750),
    (-0.0200, 0.1700, 0.0090, 0.0695), (-0.0600, 0.1595, 0.0190, 0.0595), (-0.0950, 0.1475, 0.0330, 0.0465),
    (-0.1250, 0.1360, 0.0490, 0.0335), (-0.1480, 0.1270, 0.0620, 0.0228), (-0.1630, 0.1215, 0.0710, 0.0162),
    (-0.1720, 0.1190, 0.0760, 0.0126)]
FISH_MOUTH = dict(zc=0.150, ym_nose=0.0860, ym_corner=0.0920, hinge=(0.0895, 0.1460))
FISH_EYE = dict(z=0.1840, y=0.1310, w=0.0236, h=0.0236)       # eye centre on the cheek and half width / height (bigger, 2026-11-15)
FISH_DECAL = (-0.262, 0.040, 0.160)                            # side rect: X0 (= -z), Y0, size


def fish_ym(z):
    """Mouth line in front of the corner, belly line behind it (y on the side of the body)."""
    m = FISH_MOUTH
    if z >= m["zc"]:
        t = (z - m["zc"]) / (0.250 - m["zc"])
        return lerp(m["ym_corner"], m["ym_nose"], t ** 0.75)
    return table([(0.150, 0.0920), (0.100, 0.0800), (0.040, 0.0720), (-0.030, 0.0700), (-0.080, 0.0760),
                  (-0.110, 0.0830), (-0.140, 0.0930), (-0.172, 0.0990)], z)[0]


def fish_face_layout():
    X0, Y0, w = FISH_DECAL
    e = FISH_EYE

    def nx(X): return (X - X0) / w

    def ny(y): return (y - Y0) / w
    return dict(rect=[X0, Y0, X0 + w, Y0 + w], eyeL=(nx(-e["z"]), ny(e["y"])), eyeR=(nx(-e["z"]), ny(e["y"])),
                eyeHalf=(e["w"] / w, e["h"] / w), brow=ny(e["y"] + 0.026), mouth=ny(FISH_MOUTH["ym_corner"]),
                corner=(nx(-FISH_MOUTH["zc"]), ny(FISH_MOUTH["ym_corner"])), nose=ny(0.09),
                lipNose=(nx(-0.248), ny(FISH_MOUTH["ym_nose"])),
                eyeLocal=(e["z"], e["y"], e["w"], e["h"]), hwN=0.078 / w, side=True)


def face_layout(ch):
    """Decal rectangle (character-local x0 y0 x1 y1) and eye / brow / mouth placement in normalised decal space (0..1,
    y up). Humans: square rect from just under the mouth, side max(1.76 hw, 0.72 H) (as Ruth). The fish: a side rect
    (X = -z, nose to the left) over the left cheek; the right cheek samples the same drawing."""
    if ch in FISH:
        return fish_face_layout()
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


def sheet_positions():
    """sheetX / sheetY per character: assets/jonah/design.json characters.<id> when present (Set + sheet role), else
    the CONTRACT §2 slots. The fish's slot is its root (belly line, middle of its length) in side view."""
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

    def fish_eye(img, c, r, mode="open", top=1.0, look=(-0.25, 0.0), pupil=0.62, line=0.016, wide=1.0):
        """A round, kind cartoon eye on the fish's cheek (decal space). mode: open | happy | shut | sleepy."""
        cx, cy = c
        dr = ImageDraw.Draw(img)
        if mode == "happy":
            pts = bez((cx - r * 1.05, cy - r * 0.15), (cx - r * 0.6, cy + r * 1.0), (cx + r * 0.6, cy + r * 1.0),
                      (cx + r * 1.05, cy - r * 0.15))
            stroke(dr, pts, line * 1.4, line * 1.4, wmid=line * 1.9)
            return
        if mode == "shut":                       # squeezed shut: a thick > < like crease with ticks
            for sgn in (1, -1):
                pass
            pts = bez((cx - r * 1.05, cy + r * 0.25), (cx - r * 0.4, cy - r * 0.35), (cx + r * 0.4, cy - r * 0.35),
                      (cx + r * 1.05, cy + r * 0.25))
            stroke(dr, pts, line * 1.5, line * 1.5, wmid=line * 2.0)
            for f, dy in ((0.15, 0.55), (0.5, 0.75), (0.85, 0.55)):
                x, y = pts[int(f * (len(pts) - 1))]
                stroke(dr, [(x, y + r * 0.22), (x + (f - 0.5) * r * 0.5, y + r * dy)], line * 0.8, line * 0.4)
            return
        rx, ry = r * 0.92 * wide, r * 1.05 * wide
        m = Image.new("L", img.size, 0); dm = ImageDraw.Draw(m)
        dm.ellipse((P(cx - rx, cy + ry)[0], P(cx - rx, cy + ry)[1], P(cx + rx, cy - ry)[0], P(cx + rx, cy - ry)[1]), fill=255)
        if top < 1.0:                            # upper lid lowered: cut the top of the white
            ytop = cy + ry * (2 * top - 1)
            dm.rectangle((0, 0, N, P(0, ytop)[1]), fill=0)
        lay = Image.new("RGBA", img.size, (255, 253, 248, 255)); dl = ImageDraw.Draw(lay)
        ix, iy = cx + look[0] * rx * 0.45, cy + look[1] * ry * 0.4 - 0.05 * ry
        ir = rx * 0.76
        dl.ellipse((P(ix - ir, iy + ir)[0], P(ix - ir, iy + ir)[1], P(ix + ir, iy - ir)[0], P(ix + ir, iy - ir)[1]),
                   fill=(40, 64, 92, 255))
        ir2 = ir * 0.86
        dl.chord((P(ix - ir2, iy + ir2)[0], P(ix - ir2, iy + ir2)[1], P(ix + ir2, iy - ir2)[0], P(ix + ir2, iy - ir2)[1]),
                 20, 160, fill=(78, 126, 160, 255))
        pr = ir * pupil
        dl.ellipse((P(ix - pr, iy + pr)[0], P(ix - pr, iy + pr)[1], P(ix + pr, iy - pr)[0], P(ix + pr, iy - pr)[1]),
                   fill=(18, 14, 20, 255))
        for hx, hy, hr, a in ((ix - ir * 0.28, iy + ir * 0.36, ir * 0.42, 255), (ix + ir * 0.36, iy - ir * 0.40, ir * 0.19, 235),
                              (ix + ir * 0.10, iy + ir * 0.62, ir * 0.09, 220)):
            dl.ellipse((P(hx - hr, hy + hr)[0], P(hx - hr, hy + hr)[1], P(hx + hr, hy - hr)[0], P(hx + hr, hy - hr)[1]),
                       fill=(255, 255, 255, a))
        img.paste(lay, (0, 0), m)
        dr = ImageDraw.Draw(img)
        ring = [(cx + rx * math.cos(2 * math.pi * k / 64), cy + ry * math.sin(2 * math.pi * k / 64)) for k in range(65)]
        if top < 1.0:
            ytop = cy + ry * (2 * top - 1)
            lowr = [p for p in ring if p[1] <= ytop + 1e-9]
            stroke(dr, sorted(lowr, key=lambda p: math.atan2(p[1] - cy, p[0] - cx)), line * 0.8, line * 0.8)
            xs = rx * math.sqrt(max(0.0, 1 - ((ytop - cy) / ry) ** 2))
            stroke(dr, [(cx - xs * 1.08, ytop - 0.002), (cx, ytop + 0.006), (cx + xs * 1.08, ytop - 0.002)], line * 1.5,
                   line * 1.5, wmid=line * 1.8)
        else:
            stroke(dr, ring, line * 0.9, line * 0.9)
            stroke(dr, ring[8:30], line * 1.5, line * 1.5)          # heavier upper lid line (top arc)

    def fish_brow(dr, c, r, raise_=0.0, tilt=0.0, arch=0.5, w=0.022, col=(22, 84, 90, 235), length=0.85):
        cx, cy = c
        y0 = cy + r * 1.62 + raise_
        a = (cx - r * 1.25 * length, y0 - tilt * r)
        b = (cx + r * 1.25 * length, y0 + tilt * r)
        pts = bez(a, (cx - r * 0.5, y0 + r * arch - tilt * r * 0.3), (cx + r * 0.5, y0 + r * arch + tilt * r * 0.3), b)
        stroke(dr, pts, w * 1.15, w * 0.55, wmid=w * 1.3, col=col)

    def fish_smile(img, F, kind="smile", amt=1.0):
        """The visible end of the mouth line at the corner: a curl that turns up (smile) or down (oops)."""
        cx, cy = F["corner"]
        dr = ImageDraw.Draw(img)
        if kind == "smile":
            pts = bez((cx - 0.10, cy - 0.004), (cx - 0.04, cy - 0.010 * amt), (cx - 0.004, cy + 0.000), (cx + 0.016, cy + 0.034 * amt))
        elif kind == "oops":
            pts = bez((cx - 0.10, cy - 0.004), (cx - 0.05, cy - 0.002), (cx - 0.01, cy - 0.012), (cx + 0.016, cy - 0.024))
        else:
            pts = bez((cx - 0.10, cy - 0.004), (cx - 0.05, cy - 0.006), (cx - 0.01, cy - 0.002), (cx + 0.012, cy + 0.006))
        stroke(dr, pts, 0.008, 0.016, wmid=0.016, col=(10, 50, 56, 255))
        if kind == "smile":
            ex, ey = pts[-1]
            soft(img, lambda d: stroke(d, bez((ex - 0.022, ey + 0.010), (ex - 0.010, ey + 0.020), (ex + 0.004, ey + 0.018),
                                              (ex + 0.012, ey + 0.008), 12), 0.008, 0.005, col=(14, 64, 70, 180)), 0.002)

    def fish_mouth_line(img, F, wide=1.0):
        """The shut mouth seen from the side: a long friendly line along the lip seam from the nose to the corner."""
        m = FISH_MOUTH; X0, Y0, w = FISH_DECAL
        pts = []
        for i in range(25):
            z = m["zc"] + (0.244 - m["zc"]) * i / 24
            t = (z - m["zc"]) / (0.250 - m["zc"])
            y = m["ym_corner"] + (m["ym_nose"] - m["ym_corner"]) * t ** 0.75
            pts.append(((-z - X0) / w, (y - Y0) / w - 0.004))
        dr = ImageDraw.Draw(img)
        stroke(dr, pts, 0.016 * wide, 0.007, wmid=0.017 * wide, col=(40, 26, 34, 255))

    def fish_tongue(img, F):
        """Hungry: the tongue tip licks out over the lip, near the front of the mouth."""
        x, y = F["lipNose"][0] + 0.09, F["lipNose"][1] + 0.004
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
        pts = bez((x - 0.040, y + 0.004), (x - 0.045, y - 0.050), (x + 0.040, y - 0.055), (x + 0.040, y + 0.004))
        dl.polygon([P(*p) for p in pts], fill=(232, 104, 126, 255))
        img.alpha_composite(lay)
        dr = ImageDraw.Draw(img)
        stroke(dr, pts, 0.008, 0.008, col=(120, 36, 52, 255))
        stroke(dr, [(x, y - 0.002), (x - 0.002, y - 0.030)], 0.006, 0.003, col=(170, 56, 76, 220))

    def sweat(img, x, y, s):
        drop(img, x, y, s)

    made = {}
    for ch in CHARS:
        F = face_layout(ch)
        if ch in FISH:
            e = FISH_EYE; X0, Y0, w = FISH_DECAL
            ec = F["eyeL"]; r = F["eyeHalf"][0]
            for ex in EXPRESSIONS[ch]:
                img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
                bl = 140; M = dict(mode="open", top=1.0, look=(-0.30, 0.05), pupil=0.58, wide=1.0)
                Bp = dict(raise_=-0.004, tilt=0.05, arch=0.55, length=0.85); smile = ("smile", 1.45); extra = []
                if ex == "calm":
                    M.update(top=0.94, look=(-0.35, -0.05))
                elif ex == "hungry":
                    M.update(wide=1.12, pupil=0.50, look=(-0.55, -0.25)); Bp.update(raise_=0.016, arch=0.75, tilt=-0.2)
                    smile = ("smile", 1.25); extra = ["tongue"]; bl = 90
                elif ex == "gulp":
                    M.update(mode="shut"); Bp.update(raise_=-0.006, arch=0.15, tilt=0.35); smile = ("flat", 1.0); bl = 70
                elif ex == "oops":
                    M.update(top=0.88, look=(0.55, -0.45), pupil=0.55); Bp.update(raise_=0.012, arch=0.35, tilt=0.45)
                    smile = ("oops", 1.0); bl = 210; extra = ["sweat"]
                elif ex == "happy":
                    M.update(mode="happy"); Bp.update(raise_=0.014, arch=0.80); smile = ("smile", 1.5); bl = 170
                if bl:                                   # cheek blush between the eye and the mouth corner
                    lay = Image.new("RGBA", img.size, (0, 0, 0, 0)); dl = ImageDraw.Draw(lay)
                    bx, by = (ec[0] + F["corner"][0]) / 2 + 0.03, (ec[1] + F["corner"][1]) / 2 - 0.035
                    dl.ellipse((P(bx - 0.075, by + 0.040)[0], P(bx - 0.075, by + 0.040)[1], P(bx + 0.075, by - 0.040)[0],
                                P(bx + 0.075, by - 0.040)[1]), fill=(240, 120, 140, bl))
                    img.alpha_composite(lay.filter(ImageFilter.GaussianBlur(N * 0.020)))
                # gill line: a soft curved crease behind the cheek
                gx = F["corner"][0] + 0.25
                soft(img, lambda d: stroke(d, bez((gx - 0.01, F["corner"][1] + 0.30), (gx + 0.05, F["corner"][1] + 0.18),
                                                 (gx + 0.05, F["corner"][1] + 0.02), (gx - 0.02, F["corner"][1] - 0.10), 24),
                                           0.008, 0.008, col=(14, 70, 78, 150), wmid=0.012), 0.002)
                fish_mouth_line(img, F, 1.15 if ex in ("happy", "hungry") else 1.0)
                fish_eye(img, ec, r, **M)
                fish_brow(ImageDraw.Draw(img), ec, r, **Bp)
                fish_smile(img, F, *smile)
                if "tongue" in extra:
                    fish_tongue(img, F)
                if "sweat" in extra:
                    sweat(img, ec[0] + r * 1.9, ec[1] + r * 1.6, 0.030)
                swatches(img, ch)
                out = img.resize((PX, PX), Image.LANCZOS)
                path = os.path.join(FACES, f"{ch}_{ex}.png")
                out.save(path); made[f"{ch}_{ex}"] = os.path.relpath(path, ROOT)
            continue
        eL, eR, half, by, my, ny_ = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"], F["nose"]
        bcol = {"jonah": (52, 34, 24, 255), "captain": (30, 22, 18, 255)}[ch]
        iris = {"jonah": (122, 80, 46), "captain": (104, 70, 42)}[ch]
        bw = {"jonah": 0.054, "captain": 0.060}[ch]
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            E = dict(look=(0, 0), top=1.0, bot=1.0, tilt=0.15, lash=0, mode="open", lid=0.10, inner_up=0.0,
                     pupil=0.55, wet=False)
            Bp = dict(raise_=0.0, inner=0.0, arch=0.35, thick=1.0, outer=0.0, length=0.86)
            Bl, Br = {}, {}
            M = dict(kind="flat", wd=0.095, jaw=0.0, side=0.0)
            lipcol = None; rim = None; bl = 0; crow = 0; folds = 0.0; bags = False; crs = True; special = []
            if ch == "jonah":
                E.update(lid=0.14, top=0.92, bot=0.92, tilt=-0.04, pupil=0.52)
                M["wd"] = 0.086; lipcol = (178, 96, 84, 220); rim = (220, 164, 142, 235)
                Bp.update(raise_=0.060, arch=0.22, thick=1.0); bl = 50; crow = 1; bags = False; folds = 0.0
                if ex == "grumpy":
                    E.update(top=0.66, look=(0.15, -0.05)); Bp.update(inner=-0.034, raise_=0.050, arch=0.10, outer=0.012)
                    M.update(kind="frown", wd=0.070)
                elif ex == "talk":
                    E.update(top=0.78); Bp.update(inner=-0.012, raise_=0.060, arch=0.18); M.update(kind="open", wd=0.078, jaw=0.08)
                elif ex == "shock":
                    E.update(top=1.30, bot=1.15, pupil=0.36, lid=0.06, tilt=0.0); Bp.update(raise_=0.125, arch=0.70, outer=0.02)
                    M.update(kind="o", wd=0.064, jaw=0.30); crs = True; crow = 0; bags = False
                elif ex == "ashamed":
                    E.update(top=0.62, look=(0.25, -0.85), tilt=-0.10); Bp.update(inner=0.050, raise_=0.072, arch=0.06, outer=-0.030)
                    M.update(kind="frown", wd=0.060); bl = 150
                elif ex == "yuck":
                    E.update(top=0.42, bot=0.70, look=(0.0, -0.1), tilt=0.05)
                    Bl = dict(inner=-0.040, raise_=0.040, arch=0.05, outer=0.020); Br = dict(inner=-0.020, raise_=0.068, arch=0.30)
                    special = ["wrinkles", "grimace"]
                elif ex == "pray":
                    E.update(mode="closed"); Bp.update(inner=0.016, raise_=0.062, arch=0.18); M.update(kind="soft", wd=0.066)
                    crs = False; bags = False
                elif ex == "sorry":
                    E.update(top=0.80, look=(0.0, -0.40), tilt=-0.12, wet=True)
                    Bp.update(inner=0.056, raise_=0.078, arch=0.04, outer=-0.034); M.update(kind="frown", wd=0.056)
                    bl = 70
                elif ex == "sulk":
                    E.update(top=0.55, look=(-0.6, -0.15)); Bp.update(inner=-0.046, raise_=0.044, arch=0.04, outer=0.018)
                    special = ["pout"]; bl = 60
                elif ex == "happy":
                    E.update(mode="happy"); Bp.update(raise_=0.088, arch=0.50); M.update(kind="grin", wd=0.090, jaw=0.10)
                    bl = 90; crow = 3; bags = False
                elif ex == "wail":
                    E.update(mode="closed"); Bp.update(inner=0.070, raise_=0.090, arch=0.02, outer=-0.040)
                    M.update(kind="shout", wd=0.090, jaw=0.45); special = ["tears"]; bl = 120; crs = False; bags = False
                elif ex == "soft":
                    E.update(top=0.74, bot=0.78, look=(0.1, -0.08)); Bp.update(inner=0.020, raise_=0.068, arch=0.24)
                    M.update(kind="soft", wd=0.076); crow = 3; bl = 45
            else:   # captain
                E.update(lid=0.14, top=0.92, bot=0.84, tilt=0.08, pupil=0.54)
                M["wd"] = 0.094; lipcol = (176, 90, 78, 230); rim = (218, 150, 128, 235)
                Bp.update(raise_=0.064, arch=0.32, thick=1.0); bl = 120; crow = 2; folds = 0.0
                if ex == "jolly":
                    E.update(top=0.74, bot=0.62, look=(0.05, 0.0)); Bp.update(raise_=0.070, arch=0.42)
                    M.update(kind="grin", wd=0.108, jaw=0.14); bl = 150
                elif ex == "talk":
                    M.update(kind="open", wd=0.088, jaw=0.10); Bp.update(raise_=0.070, arch=0.40)
                elif ex == "shout":
                    E.update(top=1.10, pupil=0.44, tilt=0.18); Bp.update(inner=-0.036, raise_=0.060, arch=0.10, outer=0.026)
                    M.update(kind="shout", wd=0.100, jaw=0.45); bl = 160
                elif ex == "worried":
                    E.update(top=1.00, look=(0.0, -0.1), tilt=-0.08); Bp.update(inner=0.052, raise_=0.082, arch=0.06, outer=-0.020)
                    M.update(kind="wobbly", wd=0.074, jaw=0.04); bl = 60; crow = 1
                elif ex == "torn":
                    E.update(top=0.90, look=(0.5, -0.1)); Bl = dict(inner=0.050, raise_=0.090, arch=0.10, outer=-0.010)
                    Br = dict(inner=0.020, raise_=0.072, arch=0.30); special = ["grimace"]; bl = 80; crow = 2
                elif ex == "amazed":
                    E.update(top=1.30, bot=1.10, pupil=0.36, lid=0.06, tilt=0.0); Bp.update(raise_=0.120, arch=0.66)
                    M.update(kind="o", wd=0.070, jaw=0.32); crow = 0; bl = 120
            # ---- bigger eyes (2026-11-15): open a little wider, lift the brows clear of the bigger eye
            if E["mode"] == "open":
                E["top"] = min(1.40, E["top"] * (1.12 if ch == "jonah" else 1.06))
            lift = 0.055 if ch == "jonah" else 0.030          # clear of the parked eyelid strip
            Bp["raise_"] = Bp["raise_"] + lift
            for d_ in (Bl, Br):
                if "raise_" in d_:
                    d_["raise_"] += lift
            # ---- draw
            if bl:
                blush(img, 0.30 if ch == "jonah" else 0.31, ny_ - 0.035, 0.090, 0.048, bl)
            nose_hint(img, ny_ + 0.006, 0.040 if ch == "jonah" else 0.038, strength=1.15)
            for side, c in ((1, eL), (-1, eR)):
                eye(img, c, half, side=side, iris=iris, line=0.021, **E)
                if crs and E["mode"] == "open":
                    crease(img, c, half, side, lift=1.55, col=(140, 90, 72, 120))
                if bags and E["mode"] == "open":
                    under_eye(img, c, half, side, drop=1.25 if E["bot"] < 0.9 else 1.35)
                if crow:
                    crows(img, c, half, side, n=crow, ln=1.0 if E["mode"] == "open" else 1.2, col=(130, 80, 62, 130))
                if "tears" in special:
                    tears(img, c, half, side)
            if "wrinkles" in special:
                nose_wrinkles(img, ny_, 0.036)
            dr = ImageDraw.Draw(img)
            for side, c in ((1, eL), (-1, eR)):
                b = dict(Bp); b.update(Bl if side == 1 else Br)
                brow(dr, side, (c[0], by - 0.015), half, w=bw, col=bcol, **b)
            wd = M["wd"] * (1.45 if M["kind"] in ("open", "grin", "o", "shout", "wobbly") else 1.30)
            if "pout" in special:
                soft(img, lambda d: d.ellipse((P(0.5 - wd * 1.1, my + wd * 0.5)[0], P(0.5 - wd * 1.1, my + wd * 0.5)[1],
                                               P(0.5 + wd * 1.1, my - wd * 0.8)[0], P(0.5 + wd * 1.1, my - wd * 0.8)[1]),
                                              fill=rim), 0.004)
                pout(img, 0.5, my, wd, lipcol)
            elif "grimace" in special:
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
            swatches(img, ch)
            out = img.resize((PX, PX), Image.LANCZOS)
            path = os.path.join(FACES, f"{ch}_{ex}.png")
            out.save(path); made[f"{ch}_{ex}"] = os.path.relpath(path, ROOT)
    # overview sheet: every expression over its base colour, plus a 64 px "phone distance" row (LESSONS L42)
    base = {"jonah": PALETTE["jonah"]["skin"], "captain": PALETTE["captain"]["skin"], "fish": PALETTE["fish"]["back"]}
    cells = [(ch, ex) for ch in CHARS for ex in EXPRESSIONS[ch]]
    cols = 8; cw = 256
    rows = (len(cells) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * cw, rows * (cw + 24 + 88)), (250, 246, 238))
    dr = ImageDraw.Draw(sheet)
    for i, (ch, ex) in enumerate(cells):
        x, y = (i % cols) * cw, (i // cols) * (cw + 24 + 88)
        bg = Image.new("RGBA", (cw, cw), tuple(int(base[ch][k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        if ch in FISH:          # belly colour below the mouth line, as on the model
            yb = int(cw * (1 - F_fish_ym_norm()))
            ImageDraw.Draw(bg).rectangle((0, yb, cw, cw), fill=tuple(int(PALETTE["fish"]["belly"][k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        fc = Image.open(os.path.join(FACES, f"{ch}_{ex}.png")).resize((cw, cw), Image.LANCZOS)
        bg.alpha_composite(fc); sheet.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 8, y + cw + 4), f"{ch}_{ex}", fill=(40, 30, 20))
        small = bg.resize((64, 64), Image.LANCZOS)
        sheet.paste(small.convert("RGB"), (x + 8, y + cw + 22))
    sheet.save(os.path.join(FACES, "overview.png"))
    print("faces:", len(made), "->", FACES)
    return made


def F_fish_ym_norm():
    return (FISH_MOUTH["ym_corner"] - FISH_DECAL[1]) / FISH_DECAL[2]


def compose():
    """Contact sheets model/preview_<char>.png, preview_all.png, preview_uvcheck.png, preview_pose.png from $JN_WORK."""
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
    for ch in CHARS:
        if ch in FISH:
            views = [("side", "side (its left: the sheet view)"), ("q34", "3/4 front"), ("front", "front"),
                     ("back", "back"), ("phone", "phone angle"), ("sideR", "right side")]
            top = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in views], [lb for _, lb in views], 3,
                       (640, 480), f"{ch}: rest pose, demo palette + default face decal")
            det = [("head", "head 3/4"), ("headside", "cheek"), ("mouth", "jaw open 55 deg"), ("mouthq", "jaw open, 3/4"),
                   ("under", "from below")]
            bot = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det], [lb for _, lb in det], 5, (384, 384),
                       "close-ups")
        else:
            views = [("front", "front"), ("q34", "3/4"), ("side", "side"), ("back", "back")]
            top = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in views], [lb for _, lb in views], 4,
                       (480, 720), f"{ch}: rest pose, demo palette + default face decal")
            det = [("head", "face 3/4"), ("headfront", "face front"), ("handL", "left hand"), ("handR", "right hand"),
                   ("props", "hidden props shown")]
            bot = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det], [lb for _, lb in det], 5, (384, 384),
                       "close-ups")
        ex = grid([os.path.join(WORK, f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]], EXPRESSIONS[ch], 6,
                  (320, 320), "face decals on the model (UV1)")
        stack([top, bot, ex]).save(os.path.join(MODEL, f"preview_{ch}.png"))
    al = [os.path.join(WORK, f) for f in ("pv_all.png", "pv_all_phone.png")]
    if all(os.path.exists(f) for f in al):
        stack([grid([al[0]], ["the cast at their sheet slots"], 1, (1600, 1000), "cast"),
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
        fishv = [os.path.join(WORK, f"uv_{n}.png") for n in ("fishL", "fishR", "fishTop", "fishFront")]
        r3 = Image.new("RGB", (2000, 350), bg)
        for i, f in enumerate(fishv):
            if os.path.exists(f):
                r3.paste(Image.open(f).convert("RGB").resize((500, 350)), (500 * i, 0))
        hd = Image.new("RGB", (2000, 30), bg)
        ImageDraw.Draw(hd).text((10, 8), "UV0 proof: left = a perfectly coloured sheet (ID render in demo colours), right = "
                                "the models wearing it, front ortho (fish turned to its side) = must equal the sheet; "
                                "then 3/4 + back; then the fish left / right / top / front", fill=(40, 30, 20))
        stack([hd, r1, r2, r3]).save(os.path.join(MODEL, "preview_uvcheck.png"))
    pf = [(os.path.join(WORK, f"pose_{ch}_{v}.png"), f"{ch} {v}") for ch in HUMANS for v in ("a", "b")]
    pf += [(os.path.join(WORK, f"pose_fish_{v}.png"), f"fish {v}") for v in ("gulp", "gulpq", "swim", "closed", "fins", "burp")]
    pf = [p for p in pf if os.path.exists(p[0])]
    if pf:
        grid([p[0] for p in pf], [p[1] for p in pf], 6, (320, 400),
             "pose test: humans a/b = elbows, fingers, thigh + knee, spine, head turn, jaw open, half blink, coat / "
             "belt / wrap / sash bones; fish = gulp (jaw 55 deg, body arch), swim wave, eyes closed, fins, burp").save(
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
                print(ch, "bonesMatch", i["bonesMatch"], "actions", i["actions"], "tris", i["tris"],
                      "uvOrderOK", i.get("uvOrderOK"), "maxInf", i.get("maxInfluences"))
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
ONLY = [c for c in os.environ.get("JN_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()


# =============================================================================================== context + skeleton


# =============================================================================================== context
class Ctx:
    def __init__(self, ch):
        self.ch = ch; self.F = face_layout(ch)
        if ch in FISH:                       # the fish: no human landmarks; S = 1, blend in art units
            self.s = {}; self.L = None; self.H = None; self.S = 1.0; self.blend = 0.03
        else:
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


# =============================================================================================== the great fish
FISH_E = 2.35                   # superellipse exponent of the body sections (a little boxy = plump)
FISH_NUP, FISH_NDN, FISH_K = 28, 16, 11    # ring points on the back arc, on the belly arc; inner mouth arc points
FISH_STATIONS = [0.2500, 0.2470, 0.2420, 0.2340, 0.2240, 0.2130, 0.2000, 0.1860, 0.1720, 0.1600, 0.1500, 0.1380,
                 0.1220, 0.1020, 0.0780, 0.0520, 0.0250, -0.0030, -0.0310, -0.0580, -0.0830, -0.1050, -0.1250,
                 -0.1420, -0.1560, -0.1660, -0.1720]
# 2026-11-15: twice as many stations (midpoints), smoother silhouette and room for the belly pleats
FISH_STATIONS = [z for a, b in zip(FISH_STATIONS, FISH_STATIONS[1:]) for z in (a, round((a + b) / 2, 5))] + [FISH_STATIONS[-1]]


def _crv(rows, z, k):
    """Catmull-Rom through the FISH_BODY rows (sorted by descending z), column k."""
    n = len(rows)
    for i in range(n - 1):
        a, b = rows[i][0], rows[i + 1][0]
        if b <= z <= a or (i == 0 and z > a) or (i == n - 2 and z < b):
            t = (z - a) / (b - a)
            t = min(1.0, max(0.0, t))
            p0 = rows[max(0, i - 1)][k]; p1 = rows[i][k]; p2 = rows[i + 1][k]; p3 = rows[min(n - 1, i + 2)][k]
            return cr(p0, p1, p2, p3, t)
    return rows[-1][k]


def fish_sec(z):
    top = _crv(FISH_BODY, z, 1); bot = _crv(FISH_BODY, z, 2); rx = _crv(FISH_BODY, z, 3)
    return top, bot, rx


def fish_lip_t(z):
    """Ring angle of the mouth / belly line at station z (the belly arc shrinks to the bottom near the tail)."""
    top, bot, rx = fish_sec(z)
    yc = (top + bot) / 2; ry = (top - bot) / 2
    ym = min(max(fish_ym(z), bot + 0.12 * ry), top - 0.15 * ry)
    v = (ym - yc) / ry
    tm = math.asin(max(-1.0, min(1.0, math.copysign(abs(v) ** (FISH_E / 2), v))))
    return lerp(tm, -math.pi / 2 + 0.05, smoothstep(-0.105, -0.170, z))


def fish_pt(z, t):
    top, bot, rx = fish_sec(z)
    yc = (top + bot) / 2; ry = (top - bot) / 2
    return V(rx * se(math.cos(t), FISH_E), yc + ry * se(math.sin(t), FISH_E), z)


def fish_normal(z, t, h=1e-4):
    p = fish_pt(z, t)
    dz = fish_pt(z + h, t) - fish_pt(z - h, t); dt = fish_pt(z, t + h) - fish_pt(z, t - h)
    n = dt.cross(dz).normalized()
    c = V(0, (fish_sec(z)[0] + fish_sec(z)[1]) / 2, z)
    return n if n.dot(p - c) > 0 else -n


def fish_t_at(z, y, side=1):
    """Ring angle of the point at height y on the left (+x) flank of station z."""
    top, bot, rx = fish_sec(z)
    yc = (top + bot) / 2; ry = (top - bot) / 2
    v = max(-0.999, min(0.999, (y - yc) / ry))
    t = math.asin(math.copysign(abs(v) ** (FISH_E / 2), v))
    return t if side > 0 else math.pi - t


def ends_dense(u, a=0.80):
    """0..1 -> 0..1 with short first and last steps (tight edge loops at the lips / the belly line keep them crisp
    under subdivision)."""
    return u - a * math.sin(2 * math.pi * u) / (2 * math.pi)


def fish_skeleton(C):
    m = FISH_MOUTH; e = FISH_EYE
    B = {}
    B["root"] = (V(0, 0, 0), V(0, 0.040, 0), None)
    B["body1"] = (V(0, 0.100, 0.115), V(0, 0.100, 0.035), "root")
    B["body2"] = (V(0, 0.100, 0.035), V(0, 0.100, -0.060), "body1")
    B["body3"] = (V(0, 0.100, -0.060), V(0, 0.104, -0.145), "body2")
    B["tail"] = (V(0, 0.104, -0.145), V(0, 0.104, -0.232), "body3")
    hy, hz = m["hinge"]
    B["jaw"] = (V(0, hy, hz), V(0, 0.050, 0.236), "body1")
    for side, sd in (("L", 1), ("R", -1)):
        base = V(sd * 0.064, 0.058, 0.090)
        d = V(sd * 0.42, -0.30, -1.0).normalized()
        B["fin" + side] = (base, base + d * 0.062, "body2")
    B["dorsal"] = (V(0, 0.172, 0.055), V(0, 0.184, -0.060), "body2")
    # the fish blinks with LOWER lids: parked as a thin strip under each eye, the bone points UP, so scaling its
    # local Y (the same `eyelids.sy` as the humans) raises them over the eye. Below the eye the cheek gets wider
    # downward, so each lid row taken at its widest point over the travel lies flush at rest (C1).
    C.lid = dict(top=e["y"] - 1.30 * e["h"], h0=0.18 * e["h"], closed=e["y"] + 1.05 * e["h"], up=True)
    B["eyelids"] = (V(0, C.lid["top"], e["z"]), V(0, C.lid["top"] + 0.010, e["z"]), "body1")
    C.B = B


def fish_lens_fin(cg, stations, wfn, reg, pc, thick, M=14, rays=0.0, nrays=7):
    """A thin rounded fin: stations [(base point, tip point, frame normal)] along its root; each station is a closed lens
    from base to tip (half thickness thick(s, v), s = station fraction, v = 0 base .. 1 tip) with soft ray grooves."""
    rings = []
    ns = len(stations)
    for i, (b, tp, nrm) in enumerate(stations):
        s = i / (ns - 1)
        ax = tp - b; ring = []
        for k in range(M):
            ph = 2 * math.pi * k / M
            v = 0.5 - 0.5 * math.cos(ph)                 # 0 at the base, 1 at the tip
            sgn = 1.0 if math.sin(ph) >= 0 else -1.0
            th = thick(s, v) * abs(math.sin(ph)) ** 0.85
            g = rays * math.cos(nrays * math.pi * s) * smoothstep(0.15, 0.6, v) if rays else 0.0
            ring.append(b + ax * v + nrm * (sgn * (th + g)))
        rings.append(cg.ring(ring, wfn))
    for a, bb in zip(rings, rings[1:]):
        cg.bridge(a, bb, reg, pc)
    b0, t0, _ = stations[0]; b1, t1, _ = stations[-1]
    d0 = (stations[0][0] - stations[1][0]); d1 = (stations[-1][0] - stations[-2][0])
    cg.fan(list(reversed(rings[0])), b0.lerp(t0, 0.45) + d0.normalized() * 0.002, wfn, reg, pc)
    cg.fan(rings[-1], b1.lerp(t1, 0.45) + d1.normalized() * 0.002, wfn, reg, pc)
    return rings


def build_fish(C):
    """The great fish (CONTRACT §2-§3, DESIGN §1): huge, plump, friendly. Body tube with a real mouth: in front of the
    corner every ring is cut along the mouth line; the upper head closes with a roof arc, the lower jaw with a floor
    arc; they meet at the throat line on the corner ring. Teeth and tongue inside; spots, side fins, dorsal, tail."""
    fish_skeleton(C)
    B = C.B; m = FISH_MOUTH; zc = m["zc"]
    NUP, NDN, K = FISH_NUP, FISH_NDN, FISH_K
    wbody = C.w(["body1", "body2", "body3", "tail"], blend=0.030)

    def wjaw_outer(p):
        t = smoothstep(zc - 0.030, zc + 0.040, p.z) * (1.0 if p.z > zc else smoothstep(m["ym_corner"], 0.050, p.y))
        return mixw((wbody(p), 1 - t), ({"jaw": 1.0}, t)) if t > 0 else wbody(p)

    def wjaw_inner(p):
        t = smoothstep(zc - 0.002, zc + 0.020, p.z)
        return mixw(({"body1": 1.0}, 1 - t), ({"jaw": 1.0}, t))
    cg = Cage()
    full = {}; up = {}; dn = {}
    mouth_depth = {}

    def ring_points(z):
        tm = fish_lip_t(z)
        upper = [fish_pt(z, tm + (math.pi - 2 * tm) * ends_dense(j / NUP)) for j in range(NUP + 1)]
        lower = [fish_pt(z, (math.pi - tm) + (math.pi + 2 * tm) * ends_dense(k / NDN)) for k in range(1, NDN)]
        return upper, lower

    def inner_arc(z, xl, ym, d, sign):
        """K points across the mouth from one lip to the other (sign +1: roof, R -> L; -1: floor, L -> R)."""
        pts = []
        for k in range(1, K + 1):
            s = math.pi * ends_dense(k / (K + 1))
            x = -xl * math.cos(s) * (1.0 - 0.10 * math.sin(s))
            y = ym + sign * d * math.sin(s) ** 0.65
            pts.append(V(x if sign > 0 else -x, y, z - 0.004 * math.sin(s) * smoothstep(zc, zc + 0.03, z)))
        return pts
    for z in FISH_STATIONS:
        upper, lower = ring_points(z)
        if z < zc - 1e-9:
            idx = [cg.add(p, wbody) for p in upper] + [cg.add(p, wbody) for p in lower]
            full[z] = idx
            continue
        top, bot, rx = fish_sec(z)
        ym = upper[0].y; xl = upper[0].x
        if abs(z - zc) < 1e-9:                    # the corner ring: closed, plus the throat line (shared)
            u_idx = [cg.add(p, wbody) for p in upper]
            l_idx = [cg.add(p, wjaw_outer) for p in lower]
            full[z] = u_idx + l_idx
            thr = [cg.add(p, lambda q: {"body1": 0.55, "jaw": 0.45}) for p in inner_arc(z, xl * 0.92, ym, 0.0, 1)]
            up[z] = u_idx + thr
            dn[z] = [u_idx[NUP]] + l_idx + [u_idx[0]] + list(reversed(thr))
            continue
        f_open = smoothstep(zc, zc + 0.045, z) * (1.0 - 0.85 * smoothstep(0.214, 0.249, z))
        droof = min(0.044 * f_open, 0.58 * (top - ym))
        dfloor = min(0.040 * f_open, 0.62 * (ym - bot))
        mouth_depth[z] = (droof, dfloor)
        u_idx = [cg.add(p, lambda q: {"body1": 1.0} if q.z > 0.118 else wbody(q)) for p in upper]
        roof = [cg.add(p, lambda q: {"body1": 1.0}) for p in inner_arc(z, xl, ym, droof, 1)]
        lipR = cg.add(upper[NUP], wjaw_outer); lipL = cg.add(upper[0], wjaw_outer)
        l_idx = [cg.add(p, wjaw_outer) for p in lower]
        floor = [cg.add(p, wjaw_inner) for p in inner_arc(z, xl, ym, dfloor, -1)]
        up[z] = u_idx + roof
        dn[z] = [lipR] + l_idx + [lipL] + floor
    zs = FISH_STATIONS

    def bridge_regs(r1, r2, regs, pc=0):
        n = len(r1)
        for j in range(n):
            cg.face((r1[j], r1[(j + 1) % n], r2[(j + 1) % n], r2[j]), regs(j), pc)
    for za, zb in zip(zs, zs[1:]):                # nose -> tail
        if za > zc + 1e-9:                         # mouth region (zb may be the corner)
            bridge_regs(up[zb], up[za], lambda j: "back" if j < NUP else "mouth")
            bridge_regs(dn[zb], dn[za], lambda j: "belly" if j < NDN else "mouth")
        else:
            bridge_regs(full[zb], full[za], lambda j: "back" if j < NUP else "belly")
    # nose caps: upper lip front and lower lip front
    z0 = zs[0]
    cu = sum((cg.v[i] for i in up[z0]), V()) / len(up[z0]) + V(0, 0, 0.0024)
    cg.fan(list(reversed(up[z0])), cu, lambda q: {"body1": 1.0}, "back", 0)
    cd = sum((cg.v[i] for i in dn[z0]), V()) / len(dn[z0]) + V(0, 0, 0.0024)
    cg.fan(list(reversed(dn[z0])), cd, lambda q: {"jaw": 1.0}, "belly", 0)
    # tail end of the body: close the last ring (the tail fin covers it)
    zl = zs[-1]
    cl = sum((cg.v[i] for i in full[zl]), V()) / len(full[zl]) - V(0, 0, 0.004)
    cg.fan(full[zl], cl, wbody, "back", 0)
    C.fish_rings = dict(full=full, up=up, dn=dn)
    C.mouth_depth = mouth_depth
    def lip_squeeze(pts, nrm):
        """Subdivision rounds the two lips apart; squeeze the band round the mouth line back together so the mouth is
        shut at rest (a hair line, no see-through slit). Also: soft lengthwise pleats on the throat and belly (the
        belly stripes, 2026-11-15)."""
        out = []
        for q, n in zip(pts, nrm):
            if -0.125 < q.z < 0.232:
                ylim = fish_ym(min(q.z, zc)) if q.z < zc else fish_ym(q.z)
                f = smoothstep(ylim - 0.008, ylim - 0.026, q.y) * smoothstep(-0.125, -0.080, q.z) * smoothstep(0.232, 0.200, q.z)
                if f > 0 and abs(q.x) < 0.07 and n.y < 0.15:
                    g = (0.5 + 0.5 * math.cos(2 * math.pi * q.x / 0.0140)) ** 3
                    q = q - n * 0.0020 * g * f
            if q.z > zc - 0.002:
                ym = fish_ym(q.z); dy = q.y - ym
                b = 0.0075; dl = 0.0024 * smoothstep(zc - 0.002, zc + 0.020, q.z)
                if abs(dy) < b and dl > 0:
                    t = abs(dy) / b
                    ny = math.copysign(b * max(0.0, (t - dl / b)) / (1 - dl / b), dy)
                    q = V(q.x, ym + lerp(ny, dy, t * t), q.z)
            out.append(q)
        return out
    C.add("body", cg, subdiv=1, decal=True, fishbody=True, post=lip_squeeze)
    # ---- teeth (soft, white, few) and the tongue
    cg = Cage()
    for zt, sign in ((0.178, 1), (0.202, 1), (0.224, 1), (0.190, -1), (0.214, -1)):
        tm = fish_lip_t(zt); lip = fish_pt(zt, tm)
        droof, dfloor = mouth_depth.get(min(mouth_depth, key=lambda z: abs(z - zt)))
        d = droof if sign > 0 else dfloor
        for sd in (1, -1):
            s = 0.42
            x = sd * lip.x * math.cos(s) * 0.90
            y = lip.y + sign * d * math.sin(s) ** 0.65
            c = V(x, y - sign * 0.0030, zt)
            wt = (lambda q: {"body1": 1.0}) if sign > 0 else (lambda q: {"jaw": 1.0})
            blob(cg, c, 0.0042, 0.0058, 0.0040, wt, "mouth", 0, NU=10, NV=6)
    C.add("teeth", cg, subdiv=0, swatch="teeth")
    cg = Cage()
    zt = 0.192; tm = fish_lip_t(zt); lip = fish_pt(zt, tm)
    droof, dfloor = mouth_depth.get(min(mouth_depth, key=lambda z: abs(z - zt)))
    blob(cg, V(0, lip.y - dfloor * 0.80 + 0.006, zt - 0.004), 0.020, 0.0065, 0.030, lambda q: {"jaw": 1.0}, "mouth", 0,
         NU=12, NV=6)
    C.add("tongue", cg, subdiv=1, swatch="tongue")
    # ---- spots: big round soft discs on both flanks (each its own printed shape, >= 6 mm)
    SPOTS = [(0.090, 0.150, 0.0240), (0.030, 0.157, 0.0255), (-0.032, 0.149, 0.0238), (-0.086, 0.132, 0.0205),
             (0.052, 0.108, 0.0190)]
    cg = Cage(); pc = 0
    NSEG = 28
    for zc_, yc_, r in SPOTS:
        for sd in (1, -1):
            pc += 1
            t0 = fish_t_at(zc_, yc_, 1)
            dt = (fish_pt(zc_, t0 + 1e-3) - fish_pt(zc_, t0 - 1e-3)).length / 2e-3

            def on(fr, a, h):
                z = zc_ + r * fr * math.cos(a); t = t0 + r * fr * math.sin(a) / dt
                q = fish_pt(z, t) + fish_normal(z, t) * h
                return V(sd * q.x, q.y, q.z)
            prof = [(0.22, 0.00150), (0.45, 0.00145), (0.66, 0.00130), (0.84, 0.00100), (0.95, 0.00055), (1.0, 0.00020)]
            rings = [cg.ring([on(fr, 2 * math.pi * k / NSEG, h) for k in range(NSEG)], wbody) for fr, h in prof]
            ctop = on(0.0, 0.0, 0.00140)
            cbot = on(0.0, 0.0, -0.0025)
            cg.fan(rings[0], ctop, wbody, "spots", pc)
            for a_, b_ in zip(rings, rings[1:]):
                cg.bridge(a_, b_, "spots", pc)
            cg.fan(list(reversed(rings[-1])), cbot, wbody, "spots", pc)
    C.add("spots", cg, subdiv=0)
    # ---- side fins: round paddles behind the cheeks, angled back and down, with soft ray grooves
    for side, sd in (("L", 1), ("R", -1)):
        b, tp, _ = B["fin" + side]
        d = (tp - b).normalized()
        nf = V(sd * 1.0, 0.40, 0.10); nf = (nf - d * nf.dot(d)).normalized()
        wv = d.cross(nf).normalized()
        L_ = 0.098; W_ = 0.037
        st = []
        NS = 15
        for i in range(NS):
            s = i / (NS - 1)
            a = -1 + 2 * s                                     # across the width
            half = math.sqrt(max(0.0, 1 - a * a)) ** 0.8
            root = b - d * 0.004 + wv * (a * W_ * 0.55) - nf * 0.003
            tip = b + d * (L_ * (0.30 + 0.70 * half)) + wv * (a * W_ * (0.75 + 0.35 * half))
            st.append((root, tip, nf))
        wf = (lambda q, side=side, b=b: mixw(({"body2": 1.0}, 1 - smoothstep(0.0, 0.012, (q - b).length)),
                                            ({"fin" + side: 1.0}, smoothstep(0.0, 0.012, (q - b).length))))
        cg = Cage()
        fish_lens_fin(cg, st, wf, "fins", 0, lambda s, v: (0.0068 - 0.0040 * v) * (0.55 + 0.45 * math.sin(math.pi * s)),
                      M=18, rays=0.0010, nrays=6)
        C.add("fin" + side, cg, subdiv=1)
    # ---- dorsal fin: low, rounded, leaning back
    cg = Cage(); NS = 17
    wd = lambda q: mixw(({"body2": 1.0}, 1 - smoothstep(0.172, 0.186, q.y)), ({"dorsal": 1.0}, smoothstep(0.172, 0.186, q.y)))
    st = []
    for i in range(NS):
        s = i / (NS - 1)
        z = lerp(0.062, -0.075, s)
        topy = fish_sec(z)[0]
        h = 0.033 * math.sin(math.pi * min(1.0, s * 1.08)) ** 0.75 + 0.004
        root = V(0, topy - 0.007, z)
        tip = V(0, topy + h, z - 0.020 * smoothstep(0.0, 1.0, s) - 0.006)
        st.append((root, tip, V(1, 0, 0)))
    fish_lens_fin(cg, st, wd, "fins", 0, lambda s, v: (0.0078 - 0.0042 * v), M=18, rays=0.0009, nrays=8)
    C.add("dorsal", cg, subdiv=1)
    # ---- tail: broad, two rounded lobes fanning from the peduncle (rays from a hub)
    cg = Cage()
    hub = V(0, 0.104, -0.150)
    wtl = lambda q: mixw(({"body3": 1.0}, 1 - smoothstep(-0.150, -0.168, q.z)), ({"tail": 1.0}, smoothstep(-0.150, -0.168, q.z)))
    st = []
    NS = 23
    for i in range(NS):
        s = i / (NS - 1)
        th = math.radians(lerp(-62, 62, s))             # angle from straight back, + = up
        lobe = 0.094 + 0.046 * math.exp(-((abs(th) - math.radians(40)) / math.radians(18)) ** 2) \
            - 0.012 * math.exp(-(th / math.radians(12)) ** 2)
        lobe *= 1.0 - 0.18 * smoothstep(math.radians(48), math.radians(62), abs(th))
        dirn = V(0, math.sin(th), -math.cos(th))
        root = hub + V(0, math.sin(th) * 0.010, 0.006)
        tip = hub + dirn * lobe
        st.append((root, tip, V(1, 0, 0)))
    fish_lens_fin(cg, st, wtl, "fins", 0, lambda s, v: (0.0098 - 0.0060 * v) * (0.7 + 0.3 * math.sin(math.pi * s)),
                  M=18, rays=0.0012, nrays=9)
    C.add("tailfin", cg, subdiv=1)
    # a longer, tapering body (reads as a fish, not a ball): stretch everything behind the head along z and slim the
    # rear a little; bones move with the geometry
    def zmap(p):
        if p.z >= 0.10:
            return p
        z = 0.10 + (p.z - 0.10) * 1.06
        k = 1.0 - 0.10 * smoothstep(0.04, -0.17, p.z)
        yc = 0.100
        return V(p.x * k, yc + (p.y - yc) * (1.0 - 0.04 * smoothstep(0.04, -0.17, p.z)), z)
    for pt in C.parts:
        cgp = pt["cage"]
        cgp.v = [zmap(v) for v in cgp.v]
    C.B = {b: (zmap(h), zmap(t), par) for b, (h, t, par) in C.B.items()}
    C.lid_part = "body"; C.lid_reg = "back"



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


def beard_curls(C, beard_part, pts, r, reg, piece, name="beardCurls"):
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
        blob(cg, hit[0] - n * rr * 0.05, rr, rr * 0.92, rr * 0.42, wfn, reg, 0, NU=10, NV=5, ax=M)
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
    NB = 40; rad = [0.0] * NB
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


# =============================================================================================== Jonah
def build_jonah(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]
    cb = L["brow"] + 0.31 * H                      # hairline, a little high (about forty-five)

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb), (0.08, cb - 0.01 * H), (0.13, L["brow"] + 0.18 * H), (0.17, L["eye"] + 0.02 * H),
                      (0.20, L["nose"] - 0.02 * H), (0.235, L["mouth"]), (0.30, L["chin"] + 0.02 * H),
                      (0.38, L["chin"] - 0.06 * H), (0.50, L["chin"] - 0.11 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return True
        return uu > 0.15 and p.y > rim(u) + 0.0045 * S
    skeleton(C)
    build_head(C, cull)
    C.parts[-1]["subdiv"] = 2                     # a smoother face for close-ups (2026-11-15)

    def thick(u, y):
        uu = mirror_u(u)
        t = 0.0032 + 0.0016 * smoothstep(L["eye"], L["top"], y) + 0.0010 * smoothstep(0.15, 0.40, uu)
        t *= 1.0 - 0.32 * smoothstep(L["top"] - 0.18 * H, L["top"], y)   # flatter crown: the locks give the volume
        return t * S

    def messy(u, y):                               # a little untidy: soft clumps that lift at the ends
        return 0.00085 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 13 + 0.35 * math.sin(y * 260)))) \
            * smoothstep(L["top"] - 0.05 * H, L["eye"], y)
    hair_shell(C, rim, thick, "hair", "hair", plumb=lambda uu: smoothstep(0.24, 0.34, uu), tuck_front=0.15, grooves=36,
               groove_amp=0.00040, waves=0.0006 * S, curls=messy, NU=44, NV=9, top_extra=0.0003)   # crown 1 mm lower: kneel_pray head top stays <= 0.249 (2026-11-15)
    # grey streaks at the temples: faces of the hair shell itself (they blend into the hair), two soft bands on each
    # side sweeping back from the temple; fixed colour from the decal swatch
    hc = C.parts[-1]["cage"]
    for fi, q in enumerate(hc.f):
        c = sum((hc.v[i] for i in q), V()) / len(q)
        uu = mirror_u(head_u(C, c))
        if not (L["eye"] - 0.02 * H < c.y < L["brow"] + 0.40 * H):
            continue
        if False:                                   # 2026-11-15: the grey is now one sculpted lock per temple
            hc.reg[fi] = "streaks"
    # sculpted locks combed from a centre parting down to the nape; the one over each temple is grey (2026-11-15)
    hair_locks(C, rim, [(0.015, 0.170, 1.00), (0.060, 0.215, 1.10), (0.110, 0.260, 1.20), (0.170, 0.310, 1.10),
                        (0.235, 0.360, 1.05), (0.305, 0.410, 1.05), (0.375, 0.455, 1.00), (0.440, 0.485, 1.00),
                        (0.500, 0.500, 1.05), (0.095, 0.188, 0.62)],
               0.0050, 0.0024, streak_ids=(9,), NS=18, N=10)
    # a twisted head cloth round the hair (tan, belt colour; prints as detail lines) knotted at the back
    cg = Cage(); wfn = C.w(["head"])
    NPB = 64; path = []
    Hd_ = C.head
    for i in range(NPB):
        u = i / NPB; uu = mirror_u(u)
        y = lerp(cb - 0.022 * H, L["eye"] + 0.10 * H, smoothstep(0.0, 0.5, uu) ** 0.9)
        ph, n = hair_pt(C, u, y, 0.0012 * S)               # pressed into the hair
        ps = Hd_.at(u, y) + Hd_.normal(u, y) * 0.0030 * S
        path.append(ps.lerp(ph, smoothstep(0.06, 0.16, uu)))
    twisted_ring(cg, path, 0.0026 * S, 0.0013 * S, wfn, "belt", 0, N=8, twist=0.55, ref=V(0, 1, 0))
    kp, kn = hair_pt(C, 0.5, L["eye"] + 0.10 * H, 0.0030 * S)   # low on the back of the head (kneel_pray head height)
    blob(cg, kp, 0.0040 * S, 0.0034 * S, 0.0022 * S, wfn, "belt", 0, NU=12, NV=6)
    for sd in (1, -1):
        pp, nn = [], []
        for t in [j / 6 for j in range(7)]:
            p, n = hair_pt(C, 0.5 + sd * (0.010 + 0.030 * t), L["eye"] + 0.08 * H - 0.30 * H * t, 0.0036 * S)
            pp.append(p); nn.append(n)
        strip(cg, pp, nn, [(0.0030 - 0.0008 * t) * S for t in [j / 6 for j in range(7)]], 0.0008 * S, wfn, "belt", 0)
    C.add("headband", cg, subdiv=0)
    # full short beard + moustache (one region with the hair)
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.068 * H), (0.07, L["mouth"] + 0.005 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.01 * H), (0.20, L["eye"] - 0.15 * H), (0.245, L["eye"] - 0.02 * H)]
    bot = [(0.00, L["chin"] - 0.20 * H), (0.06, L["chin"] - 0.19 * H), (0.12, L["chin"] - 0.13 * H),
           (0.17, L["chin"] - 0.03 * H), (0.21, L["mouth"] - 0.06 * H), (0.245, L["nose"] - 0.05 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0068, 0.0040, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0058 * S; row = math.floor((y - L["chin"]) / rh)
        return 0.0007 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 26 + 0.5 * (row % 2)))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.20 * H, reg="hair")
    moustache(C, "moustache", L["mouth"] + 0.100 * H, 0.62 * s["hw"], 0.07 * H, 0.0, 0.0019 * S, reg="hair", off=0.0016)
    C.parts[-1]["piece_as"] = "beard"
    hw_ = s["hw"]; yb0 = L["mouth"] - 0.12 * H
    beard_locks(C, "beard", [(sx * hw_ * f, yb0 - 0.02 * H * abs(f), sx * hw_ * f * 0.35, L["chin"] - 0.17 * H + 0.03 * H * abs(f))
                             for sx, f in ((1, 0.0), (1, 0.28), (-1, 0.28), (1, 0.56), (-1, 0.56), (1, 0.82), (-1, 0.82))]
                + [(sx * hw_ * 1.02, L["nose"] - 0.02 * H, sx * hw_ * 0.80, L["chin"] - 0.05 * H) for sx in (1, -1)],
                0.0030, 0.0011, "hair", "beard")
    # ---- cream tunic to the shins, ragged hem, sleeves to the wrist
    hemT = 0.052 * k
    RT = cut_rows(scale_rows(KING_ROBE, k, kx), hemT)
    RT[0] = (RT[0][0] - 0.0045 * S, RT[0][1] * 1.18) + RT[0][2:]       # a lower, wider neckline: a hint of a neck
    RT[1] = (RT[1][0] - 0.0030 * S, RT[1][1] * 1.08) + RT[1][2:]
    sleeve_t = [(0.004, 0.0122), (0.014, 0.0118), (0.030, 0.0108), (0.048, 0.0100), (0.062, 0.0098), (0.074, 0.0101),
                (0.082, 0.0106), (0.096, 0.0110), (0.104, 0.0112)]
    cg = build_robe(C, RT, sleeve_t, None, nf=12, fold_amp=0.0013, sleeve_fold=0.0008, reg="tunic", name="tunic",
                    N=40, step=0.0060)
    ragged_hem(cg, hemT, S)
    C.tunic_rows = C.robe_rows
    for side in "LR":
        build_forearm_hand(C, side, 0.040)
        build_leg(C, side, 0.0, "sandals", regfn2=sandal_regfn(S), top_y=0.062)
    # ---- open brown coat, knee length, wide elbow sleeves, tan stripes; front panels on coatL / coatR
    hemO = 0.094 * k
    RO = [(y, hw + 0.0032 * S + 0.0150 * S * smoothstep(0.215, 0.06, y), zf + 0.0032 * S + 0.0026 * S * smoothstep(0.20, 0.06, y),
           zb - 0.0032 * S - 0.0012 * S * smoothstep(0.20, 0.06, y)) for y, hw, zf, zb in scale_rows(KING_ROBE, k, kx)]
    RO = cut_rows(RO, hemO)
    RO[0] = (RO[0][0] - 0.0045 * S, RO[0][1] * 1.16) + RO[0][2:]
    sleeve_o = [(0.004, 0.0150), (0.014, 0.0146), (0.030, 0.0138), (0.046, 0.0134), (0.060, 0.0134), (0.074, 0.0138),
                (0.086, 0.0144), (0.094, 0.0148)]
    NCOAT = 44
    cg = build_robe(C, RO, sleeve_o, None, nf=10, fold_amp=0.0018, sleeve_fold=0.0011, bell_sag=0.0012 * S, reg="coat",
                    name="coat", solidify=0.0010, keep=True, N=NCOAT, step=0.0060)

    def gap(y):         # half-angle of the front opening
        return math.radians(lerp(6.5, 11.5, smoothstep(nb, 0.06, y) ** 0.8))

    def on_sleeve(c):
        for side in "LR":
            A_ = C.arm[side]; sv = (c - A_["S0"]).dot(A_["d"])
            if sv > 0.004 * S and (c - (A_["S0"] + A_["d"] * sv)).length < 0.03 * S:
                return True
        return False

    def opening(c):
        if on_sleeve(c):
            return False
        return c.z > 0 and abs(math.atan2(c.x, c.z)) < gap(c.y) * 0.85
    N_ = NCOAT; dlt = 2 * math.pi / N_; e_ = 2.5; fade = math.radians(70)
    for i, p in enumerate(cg.v):
        if on_sleeve(p) or p.z < -0.002:
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
    # stripes (2026-11-15): below the belt each front panel is one wide tan band from the opening to ~72 deg (the
    # printed one, >= 6 mm), framed by brown piping (coatTrim, detail lines); a narrower tan stripe at each side
    # seam and on the back. Above the belt the coat is plain brown (no thin tan island between belt and chest).
    bw = wy - 0.010 * S                             # the belt sits on the hips
    ys_top = bw + 0.008 * S
    for fi, q in enumerate(cg.f):
        c = sum((cg.v[i] for i in q), V()) / len(q)
        if on_sleeve(c):
            continue
        hw_, zf_, zb_ = table(C.robe_rows, c.y); zc_ = (zf_ + zb_) / 2
        a = abs(math.atan2(c.x, c.z - zc_))
        if c.y > ys_top:
            continue
        if a < math.radians(76) or math.radians(98) < a < math.radians(116) or math.radians(142) < a < math.radians(162):
            cg.reg[fi] = "stripes"
    zfc = table(RO, chestY)[1]
    for side, sd in (("L", 1), ("R", -1)):
        x0 = sd * table(RO, chestY)[0] * 0.42
        C.B["coat" + side] = (V(x0, chestY - 0.004 * S, zfc + 0.002 * S),
                              V(sd * table(RO, hemO + 0.01)[0] * 0.50, hemO + 0.004, table(RO, hemO + 0.01)[1] + 0.004 * S), "chest")
    for i, p in enumerate(cg.v):
        a = math.atan2(p.x, p.z + 0.001)
        tw = smoothstep(wy - 0.004 * S, wy - 0.030 * S, p.y) * smoothstep(math.radians(85), math.radians(35), abs(a))
        if tw <= 0 or p.z < 0:
            continue
        tw *= 0.90
        cg.w[i] = mixw((cg.w[i], 1 - tw), ({"coat" + ("L" if p.x > 0 else "R"): 1.0}, tw))
    # cuffs: a rolled tan band at the end of each coat sleeve; a rolled hem round the coat
    cg2 = Cage()
    for side in "LR":
        A_ = C.arm[side]; sv = sleeve_o[-1][0] * S - 0.002 * S; R_ = sleeve_o[-1][1] * S + 0.0010 * S
        c0 = A_["S0"] + A_["d"] * sv
        X0 = perp(V(0, 0, 1), A_["d"]); Y0 = A_["d"].cross(X0)
        pts = [c0 + (X0 * math.cos(2 * math.pi * j / 20) + Y0 * math.sin(2 * math.pi * j / 20)) * R_ for j in range(20)]
        band_loop(cg2, pts, [(q - c0).normalized() for q in pts], [A_["d"]] * 20, 0.0034 * S, 0.0014 * S,
                  C.w(["forearm" + side, "upperArm" + side]), "stripes", 3 if side == "L" else 4)
    C.add("cuffs", cg2, subdiv=1)
    bins = {}
    used = {i for q in cg.f for i in q}
    for vi, p in enumerate(cg.v):
        if vi in used and p.y < hemO + 0.0010 * S:
            hw_, zf_, zb_ = table(C.robe_rows, p.y); zc_ = (zf_ + zb_) / 2
            a_ = math.atan2(p.x, -(p.z - zc_)); r_ = math.hypot(p.x, p.z - zc_)
            kb = int((a_ + math.pi) / (2 * math.pi) * 40)
            if kb not in bins or r_ > bins[kb][0]:
                bins[kb] = (r_, a_, p, zc_)
    hem = [bins[kb] for kb in sorted(bins)]
    if len(hem) > 8:
        path = [p + V(p.x, 0, p.z - zc_).normalized() * 0.0005 * S + V(0, 0.0010 * S, 0) for r_, a_, p, zc_ in hem]
        cg3 = Cage()
        tube(cg3, path, [(0.0012 * S, 0.0017 * S)] * len(path), 6, skirt_weights(C), "coat", 0, ref=V(0, 1, 0))
        C.add("coatHem", cg3, subdiv=0)
    # brown piping round each tan front band (opening edge and the outer edge at 72 deg) and a rolled shawl collar
    # from the belt up round the back of the neck and down again (merges into the brown coat on the sheet)
    cgT = Cage(); wsk = skirt_weights(C)
    cgC = Cage(); wcol = C.w(["chest", "neck", ("shoulderL", 0.010 * S), ("shoulderR", 0.010 * S)])
    for sd in (1, -1):
        for kind in ("open", "outer"):
            pp = []
            for t in [j / 24 for j in range(25)]:
                y = lerp(hemO + 0.0016 * S, bw - 0.010 * S, t)
                a = (gap(y) + math.radians(0.6)) if kind == "open" else math.radians(76)
                pp.append(shell_point(C.robe_rows, y, sd * a, 0.0012 * S))
            tube(cgT, pp, [(0.0011 * S, 0.0011 * S)] * len(pp), 6, wsk, "coat", 0, ref=V(0, 0, 1))
    C.add("coatTrim", cgT, subdiv=0)
    yTop = C.robe_rows[0][0] - 0.0012 * S
    cpath = []
    for t in [j / 10 for j in range(11)]:                       # up the left opening edge
        y = lerp(bw + 0.010 * S, yTop, t)
        cpath.append(shell_point(C.robe_rows, y, gap(y) + math.radians(1.0), 0.0016 * S))
    for j in range(1, 24):                                       # round the back of the neck
        a = lerp(gap(yTop) + math.radians(1.0), 2 * math.pi - gap(yTop) - math.radians(1.0), j / 24)
        cpath.append(shell_point(C.robe_rows, yTop, a, 0.0016 * S))
    for t in [j / 10 for j in range(11)]:                       # down the right opening edge
        y = lerp(yTop, bw + 0.010 * S, t)
        cpath.append(shell_point(C.robe_rows, y, -(gap(y) + math.radians(1.0)), 0.0016 * S))
    tube(cgC, cpath, [(0.0020 * S, 0.0013 * S)] * len(cpath), 8, wcol, "coat", 0, ref=V(0, 1, 0))
    C.add("coatCollar", cgC, subdiv=0, piece_as="coat")
    # ---- tan cloth belt wrapped twice over the coat (diagonal folds, rolled edges), one fringed end hanging (belt1)
    wrap_band(C, "beltA", "belt", bw - 0.0150 * S, bw + 0.0005 * S, 0.0012, 0.0014, 0.0007, 1.6, phase=0.3)
    C.parts[-1]["piece_as"] = "belt"
    wrap_band(C, "beltB", "belt", bw - 0.0010 * S, bw + 0.0130 * S, 0.0024, 0.0014, 0.0007, 1.6, phase=2.1)
    C.parts[-1]["piece_as"] = "belt"
    hanging_end(C, "beltEnd", "belt", 0.0130 * S, bw - 0.004 * S, bw - 0.064 * S, 0.0046, "belt1", off=0.0046)
    C.parts[-1]["piece_as"] = "belt"
    rr_ = C.robe_rows; kx_ = 0.0130 * S; y_end = bw - 0.064 * S
    xe = kx_ + 0.0030 * S
    ae = math.asin(max(-1, min(1, xe / (table(rr_, y_end)[0] + 0.002))))
    pe = shell_point(rr_, y_end, ae, (0.0046 + 0.0004) * S) + V(0, -0.0018 * S, 0.0004 * S)
    cg = Cage(); wfr = C.w(["belt1"], blend=0.010 * S)
    for j in range(6):
        dx = (j - 2.5) / 2.5 * 0.0046 * S * 1.1
        ln = (0.0085 + 0.0020 * ((j * 3) % 4) / 3) * S
        pth = [pe + V(dx * (1 + 0.15 * t), -ln * t, 0.0004 * S * math.sin(t * 3 + j)) for t in [k / 5 for k in range(6)]]
        tube(cg, pth, [(0.00075 * S * (1 - 0.4 * t), 0.00065 * S * (1 - 0.4 * t)) for t in [k / 5 for k in range(6)]], 6, wfr,
             "belt", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
    C.add("beltFringe", cg, subdiv=0)
    for side in "LR":
        sandal_gear(C, side)
    # ---- seaweed clump on the head (rigid, seaweed bone; hidden by default)
    crown = V(0, L["top"] + 0.003 * S, L["zc"] - 0.004 * S)
    C.B["seaweed"] = (crown.copy(), crown + V(0, 0.020 * S, 0), "head")
    cg = Cage(); rnd = random.Random(5)
    blob(cg, crown + V(0, 0.002 * S, 0), 0.010 * S, 0.0055 * S, 0.010 * S, None, "seaweed", 0, NU=12, NV=6)
    for i in range(9):
        an = 2 * math.pi * i / 9 + rnd.uniform(-0.2, 0.2)
        d = V(math.sin(an), 0, math.cos(an))
        ln = (0.030 + 0.016 * rnd.random()) * S
        path = []
        for t in [j / 6 for j in range(7)]:
            r = 0.006 * S + ln * t
            yy = crown.y + 0.004 * S - (ln * 0.9) * t ** 1.6
            p = crown + d * r
            p.y = yy
            p += V(d.z, 0, -d.x) * (0.003 * S * math.sin(t * 6 + i))
            path.append(p)
        nn = [d.copy() for _ in path]
        strip(cg, path, nn, [0.0034 * S * (1 - 0.6 * t) + 0.0012 * S for t in [j / 6 for j in range(7)]], 0.0006 * S,
              None, "seaweed", 0)
    C.add("seaweed", cg, subdiv=0, rigid="seaweed")


# =============================================================================================== the captain
def build_captain(C):
    s = C.s; L = C.L; H = C.H; S = C.S; k = s["k"]; kx = s["kx"]
    shY = s["shoulder"][1]; nb = s["neckBase"]; wy = s["waistY"]; chestY = s["chestY"]
    cb = L["brow"] + 0.22 * H                      # front edge of the head-wrap on the forehead

    def wrim(u):
        uu = mirror_u(u)
        return table([(0.00, cb), (0.09, cb - 0.01 * H), (0.15, L["brow"] + 0.10 * H), (0.20, L["eye"] + 0.08 * H),
                      (0.26, L["eye"] + 0.02 * H), (0.34, L["nose"] - 0.04 * H), (0.42, L["mouth"] - 0.06 * H),
                      (0.50, L["mouth"] - 0.10 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p)
        if p.y < nb - 0.0060 * S:
            return True
        return p.y > wrim(u) + 0.0050 * S
    skeleton(C)
    build_head(C, cull)
    C.parts[-1]["subdiv"] = 2                     # a smoother face for close-ups (2026-11-15)

    def wthick(u, y):
        uu = mirror_u(u)
        return (0.0034 + 0.0012 * smoothstep(L["eye"], L["top"], y) + 0.0006 * smoothstep(0.2, 0.5, uu)) * S

    def folds(u, y):
        return 0.0007 * S * math.cos(2 * math.pi * (u * 9 + 0.8 * (y - L["chin"]) / H)) * smoothstep(L["top"], L["eye"], y)
    hair_shell(C, wrim, wthick, "wrap", "wrap", plumb=lambda uu: smoothstep(0.30, 0.40, uu) * 0.6, tuck_front=0.0,
               grooves=0, curls=folds, NU=36, NV=8, top_extra=0.0030)
    # knot at the back of the head and a short tail (wrap1)
    Hd = C.head
    ky = L["eye"] + 0.02 * H
    kc = C.hair_outer(0.5, ky) + Hd.normal(0.5, ky) * (0.0030 * S)
    C.B["wrap1"] = (kc.copy(), kc + V(0, -0.050 * S, -0.010 * S), "head")
    ww = C.w(["wrap1"], blend=0.006 * S)

    def wtail(p):
        t = smoothstep(kc.y - 0.004 * S, kc.y - 0.014 * S, p.y)
        return mixw(({"head": 1.0}, 1 - t), (ww(p), t)) if t > 0 else {"head": 1.0}
    cg = Cage()
    blob(cg, kc, 0.0060 * S, 0.0050 * S, 0.0040 * S, wtail, "wrap", 0, NU=12, NV=7)
    for sd in (1, -1):
        Mx = Matrix.Rotation(math.radians(sd * 50), 3, V(0, 0, 1))
        blob(cg, kc + V(sd * 0.0075 * S, 0.0030 * S, -0.0006 * S), 0.0065 * S, 0.0034 * S, 0.0030 * S, wtail, "wrap", 0,
             NU=10, NV=6, ax=Mx)
    for sd, ln in ((1, 0.064), (-1, 0.050)):
        pp = [kc + V(sd * (0.003 + 0.009 * t) * S, -ln * S * t, -(0.004 + 0.012 * t * t) * S) for t in [i / 7 for i in range(8)]]
        rad = [(0.0016 * S, (0.0060 * (1 - 0.35 * t) + 0.0012) * S) for t in [i / 7 for i in range(8)]]
        tube(cg, pp, rad, 8, wtail, "wrap", 0, ref=V(0, 0, 1), cap0=True, cap1=True)
    C.add("knot", cg, subdiv=0, piece_as="wrap")          # one printed shape with the wrap (was a 0.3 mm sliver)
    # a rolled hem all round the head-wrap's lower edge (2026-11-15)
    cg = Cage(); NPB = 72
    path = [hair_pt(C, i / NPB, wrim(i / NPB) + 0.0042 * S, 0.0004 * S)[0] for i in range(NPB)]
    twisted_ring(cg, path, 0.0022 * S, 0.0016 * S, C.w(["head"]), "wrap", 0, N=8, twist=0.0, ref=V(0, 1, 0))
    C.add("wrapHem", cg, subdiv=0, piece_as="wrap")
    # short curly black beard + moustache
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.068 * H), (0.07, L["mouth"] + 0.005 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.01 * H), (0.20, L["eye"] - 0.12 * H), (0.245, L["eye"] + 0.02 * H)]
    bot = [(0.00, L["chin"] - 0.10 * H), (0.06, L["chin"] - 0.09 * H), (0.12, L["chin"] - 0.05 * H),
           (0.17, L["chin"] + 0.03 * H), (0.21, L["mouth"] - 0.03 * H), (0.245, L["nose"] - 0.02 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0048, 0.0030, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0046 * S; row = math.floor((y - L["chin"]) / rh)
        return 0.0011 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 36 + 0.5 * (row % 2)))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.10 * H, reg="beard")
    moustache(C, "moustache", L["mouth"] + 0.092 * H, 0.60 * s["hw"], 0.04 * H, 0.05 * H, 0.0020 * S, reg="beard", off=0.0016)
    C.parts[-1]["piece_as"] = "beard"                       # one printed shape with the beard (was a 0.3 mm sliver)
    hw_ = s["hw"]; cp = []
    for j, yy in enumerate((L["mouth"] - 0.12 * H, L["mouth"] - 0.19 * H, L["chin"] + 0.02 * H)):
        n_ = 8 - j
        for i in range(n_):
            cp.append(((i - (n_ - 1) / 2) / max(1, n_ - 1) * hw_ * (1.70 - 0.30 * j) + (0.0 if j % 2 else 0.0010 * S), yy))
    for sx in (1, -1):
        for yy in (L["nose"] - 0.05 * H, L["mouth"] - 0.04 * H):
            cp.append((sx * hw_ * 0.90, yy))
    beard_curls(C, "beard", cp, 0.0021, "beard", "beard")
    # ---- cream sleeveless tunic to the knee
    hemT = 0.100 * k
    RT = cut_rows(scale_rows(KING_ROBE, k, kx), hemT)
    yb = wy - 0.012 * S                            # a broad chest and a round belly
    RT = [(y, hw * (1 + 0.05 * math.exp(-((y - chestY) / 0.025) ** 2)) + 0.0040 * S * math.exp(-((y - yb) / 0.028) ** 2),
           zf + 0.0030 * S * math.exp(-((y - chestY) / 0.02) ** 2) + 0.0160 * S * math.exp(-((y - yb) / 0.034) ** 2),
           zb - 0.0012 * S * math.exp(-((y - yb) / 0.03) ** 2)) for y, hw, zf, zb in RT]
    sleeve_t = [(0.004, 0.0136), (0.014, 0.0134), (0.026, 0.0129), (0.034, 0.0128)]
    build_robe(C, RT, sleeve_t, None, nf=12, fold_amp=0.0013, sleeve_fold=0.0004, reg="tunic", name="tunic", N=40,
               step=0.0060)
    C.tunic_rows = C.robe_rows
    # rolled hems on the cap sleeves
    cg = Cage()
    for side in "LR":
        A_ = C.arm[side]; sv = sleeve_t[-1][0] * S - 0.0015 * S; R_ = sleeve_t[-1][1] * S + 0.0006 * S
        c0 = A_["S0"] + A_["d"] * sv
        X0 = perp(V(0, 0, 1), A_["d"]); Y0 = A_["d"].cross(X0)
        pts = [c0 + (X0 * math.cos(2 * math.pi * j / 28) + Y0 * math.sin(2 * math.pi * j / 28)) * R_ for j in range(28)]
        twisted_ring(cg, pts, 0.0016 * S, 0.0012 * S, C.w(["upperArm" + side, "shoulder" + side]), "tunic", 0, N=6,
                     twist=0.0, ref=A_["d"])
    C.add("sleeveHem", cg, subdiv=0, piece_as="tunic")
    # ---- an open ochre vest over the tunic: sleeveless, V-neck, rolled edges, tucked under the sash (2026-11-15)
    sy0, sy1 = wy - 0.0185 * S, wy + 0.0125 * S
    vy0 = sy1 - 0.0080 * S; vy1 = C.robe_rows[0][0] - 0.0030 * S      # tucked under the sash's upper half
    wv = skirt_weights(C)

    def vgap(y):
        return math.radians(lerp(9.0, 24.0, smoothstep(chestY + 0.008 * S, vy1, y)))

    tbvh = cage_bvh([p for p in C.parts if p["name"] == "tunic"][-1]["cage"])

    def vpt(y, f, off):
        g = vgap(y); a = lerp(g, 2 * math.pi - g, f)
        p = push_out_of_sleeves(C, shell_point(C.robe_rows, y, a, off), off)
        row = table(C.robe_rows, y)
        d = V(-p.x, 0, (row[1] + row[2]) / 2 - p.z)          # inward, toward the body axis
        if d.length > 1e-9:                                  # sit on the real tunic surface (shoulder ports, smoothing)
            d.normalize()
            hit = tbvh.ray_cast(p - d * 0.03 * S, d, 0.06 * S)
            if hit[0] and (hit[0] - (p + d * off)).dot(-d) > 0:
                p = hit[0] - d * off
        return p
    def vpa(y, a, off):                                      # vest point at angle a (0 = front, + = his left)
        g = vgap(y)
        return vpt(y, (a - g) / (2 * math.pi - 2 * g), off)
    armpit = shY - 0.024 * S

    def arm_w(y):                                            # half-angle of the arm hole round 90 / 270 deg
        return math.radians(34.0) * smoothstep(armpit, armpit + 0.016 * S, y) ** 0.8
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
    grid(vy0, armpit, 10, [(lambda y: vgap(y), lambda y: 2 * math.pi - vgap(y), 64)])
    grid(armpit, vy1, 10, [(lambda y: vgap(y), lambda y: math.pi / 2 - arm_w(y), 14),
                           (lambda y: math.pi / 2 + arm_w(y), lambda y: 1.5 * math.pi - arm_w(y), 30),
                           (lambda y: 1.5 * math.pi + arm_w(y), lambda y: 2 * math.pi - vgap(y), 14)])
    C.add("vest", cg, subdiv=0, solidify=0.0009)
    cg = Cage()
    ve0 = sy1 + 0.0004 * S
    for fe in (0.0, 1.0):
        ep = [vpt(lerp(ve0, vy1, t), fe, 0.0024 * S) for t in [k / 18 for k in range(19)]]
        tube(cg, ep, [(0.0016 * S, 0.0012 * S)] * len(ep), 6, wv, "vest", 0, ref=V(0, 0, 1))
    C.add("vestEdge", cg, subdiv=0, piece_as="vest")
    # bare arms: upper arm from inside the cap sleeve to the elbow, then the kit forearm + big hand
    for side in "LR":
        A = C.arm[side]; hd = s["handDims"]
        cg = Cage()
        wa = C.w(["chest", "shoulder" + side, "upperArm" + side, "forearm" + side])
        path = [A["S0"] + A["d"] * (sv * S) for sv in (0.016, 0.024, 0.032, 0.040, 0.050)] + [A["E"] + A["d"] * 0.004 * S]
        rr = [0.0110 * S, 0.0114 * S, 0.0108 * S, 0.0098 * S, hd["armR"] * 1.06, hd["armR"]]
        tube(cg, path, [(r, r * 0.95) for r in rr], 12, wa, "skin", 0, ref=V(0, 0, 1), cap0=True, cap1=False)
        C.add("arm" + side, cg, subdiv=1)
        build_forearm_hand(C, side, 0.002)
    # bare legs and feet; a knee tube from inside the hem down to the kit's lower leg
    for side in "LR":
        sd = 1 if side == "L" else -1
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
        build_leg(C, side, -1.0, "sandals", regfn2=sandal_regfn(S), top_y=0.050)
        sandal_gear(C, side)
    # ---- wide rust sash wrapped round the belly: diagonal folds, rolled edges, a knot and a hanging end (sash1)
    cg = Cage(); wb = C.w(["hips", "spine"])
    NA = 96; rings = []
    rows = [0.0, 0.04, 0.10, 0.16, 0.23, 0.30, 0.37, 0.44, 0.51, 0.58, 0.65, 0.72, 0.79, 0.86, 0.92, 0.96, 1.0]
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
        cg.bridge(a_, b_, "sash", 0)
    C.add("sash", cg, subdiv=0)
    hanging_end(C, "sashEnd", "sash", -0.0150 * S, wy - 0.008 * S, wy - 0.070 * S, 0.0062, "sash1", off=0.0058)
    C.parts[-1]["piece_as"] = "sash"
    C.parts[-2]["piece_as"] = "sash"
    # ---- sailor's rope: a twisted rope belt along the lower edge of the sash, a coil hanging at his left hip, rope
    # bracelets on both wrists (fixed hemp colour from the decal swatch; prints as detail lines)
    cg = Cage(); wb = C.w(["hips", "spine"])
    yr = sy0 - 0.0006 * S                                    # just under the sash edge, on the skirt top
    twisted_ring(cg, [shell_point(C.robe_rows, yr, 2 * math.pi * i / 72, 0.0028 * S) for i in range(72)],
                 0.0013 * S, 0.0011 * S, wb, "rope", 0, N=6, twist=1.1, ref=V(0, 1, 0))
    ac = math.radians(64); cc = shell_point(C.robe_rows, yr - 0.0120 * S, ac, 0.0050 * S)
    nn_ = V(math.sin(ac), 0, math.cos(ac)); tt_ = V(math.cos(ac), 0, -math.sin(ac))
    wcoil = C.w(["hips", ("thighL", 0.02 * S)], blend=0.02 * S)
    coil = []
    for k in range(3 * 36 + 1):                              # three hanging loops, each a little lower and longer
        a = 2 * math.pi * k / 36; f = k / 36
        rv = V(0, 1, 0) * (math.cos(a) * (0.0105 + 0.0012 * f) * S) + tt_ * (math.sin(a) * 0.0062 * S)
        coil.append(cc + rv + V(0, -0.0018 * S * f, 0) + nn_ * (0.0013 * S * f))
    tube(cg, coil, [(0.0011 * S, 0.0011 * S)] * len(coil), 6, wcoil, "rope", 0, ref=nn_, twist=0.9, cap0=True, cap1=True)
    C.add("rope", cg, subdiv=0)
    cg = Cage()
    for side in "LR":
        A_ = C.arm[side]; hd = s["handDims"]
        c0 = A_["W"] - A_["d"] * 0.010 * S
        X0 = perp(V(0, 0, 1), A_["d"]); Y0 = A_["d"].cross(X0)
        rr_ = hd["armR"] * 1.02
        pts = [c0 + (X0 * math.cos(2 * math.pi * j / 24) + Y0 * math.sin(2 * math.pi * j / 24)) * rr_ for j in range(24)]
        twisted_ring(cg, pts, 0.0011 * S, 0.0010 * S, C.w(["forearm" + side]), "rope", 0, N=6, twist=1.1, ref=A_["d"])
    C.add("bracelets", cg, subdiv=0)
    # ---- short navy wrap skirt over the tunic, to mid-thigh: pleats deepening to the hem, an overlapping front flap
    # with a raised edge (slanting across his left front), a rolled hem
    y0, y1 = sy0 + 0.0020 * S, (s["hipY"] + s["kneeY"]) / 2 + 0.002 * S
    cg = Cage(); wsk = skirt_weights(C)
    NA = 108; rings = []
    nrow = 16
    for j in range(nrow + 2):
        t = min(1.0, j / (nrow - 1))
        y = lerp(y0, y1, t)
        ring = []
        for i in range(NA):
            a = 2 * math.pi * i / NA - math.pi                  # -pi..pi, 0 = front
            edge = math.radians(lerp(14.0, 30.0, t))              # the flap edge on his left front
            flap = 0.0020 * S * smoothstep(edge - 0.06, edge + 0.02, a) * smoothstep(math.radians(150), math.radians(100), a)
            pleat = 0.0026 * S * t ** 1.1 * math.cos(11 * a + 0.5)
            off = (0.0018 + 0.0115 * t ** 1.3) * S + flap + pleat
            yy = y
            if j == nrow:                                        # rolled hem: out and down a little
                off += 0.0011 * S; yy = y1 - 0.0012 * S
            elif j == nrow + 1:                                  # ... and back up inside
                off -= 0.0016 * S; yy = y1 + 0.0028 * S
            ring.append(shell_point(C.robe_rows, yy, a, off))
        rings.append(cg.ring(ring, wsk))
    for a_, b_ in zip(rings, rings[1:]):
        cg.bridge(a_, b_, "skirt", 0)
    C.add("skirt", cg, subdiv=0)

BUILDERS_H = {"jonah": build_jonah, "captain": build_captain}


# =============================================================================================== Blender assembly
BUILDERS = {"jonah": build_jonah, "captain": build_captain, "fish": build_fish}
PIECES = []           # global piece id -> (char, part, piece); index 0 = background
REGIONS = []          # global region id -> "char.region"
PART_TRIS = {}
REST_BAKE = {}


def swatch_uv(ch, nm, f=0.5):
    x0, y0, x1, y1 = SWATCHES[ch][nm]
    return (lerp(x0, x1, f), (y0 + y1) / 2)


def in_swatch(ch, du, dv, margin=0.02):
    for x0, y0, x1, y1 in SWATCHES.get(ch, {}).values():
        if x0 - margin <= du <= x1 + margin and y0 - margin <= dv <= y1 + margin:
            return True
    return False


def finish_uv1_and_jaw(C, ch, o, pt, sheet):
    """UV1 (decal): humans = front projection of the face rect (front-facing parts flagged decal); the fish = side
    projection of the cheek (both sides, mirrored). Fixed-colour parts / regions point at their swatch. Humans: the
    jaw weights of the face / beard, as Ruth."""
    me = o.data
    dec = C.F["rect"]
    vco = [to_design(o.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    vn = [to_design(o.matrix_world.to_3x3() @ v.normal).normalized() for v in me.vertices]
    if not me.uv_layers.get("UVMap"):                 # page UV must be layer 0 (TEXCOORD_0), decal layer 1
        me.uv_layers.new(name="UVMap")
    uv1 = me.uv_layers.get("decal") or me.uv_layers.new(name="decal")
    rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
    sw = SWATCHES.get(ch, {})
    zc = FISH_MOUTH["zc"]
    for poly, r in zip(me.polygons, rid):
        reg = REGIONS[r - 1].split(".")[1]
        if ch in FISH and pt.get("decal"):           # the fish decides per face: all corners projected or none
            fn = to_design(o.matrix_world.to_3x3() @ poly.normal).normalized()
            cen = sum((vco[i] for i in poly.vertices), V()) / len(poly.vertices)
            face_ok = (fn.x if cen.x >= 0 else -fn.x) > 0.18 and abs(cen.x) > 0.012
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index; p = vco[vi]; n = vn[vi]
            if pt.get("swatch"):
                uv = swatch_uv(ch, pt["swatch"])
            elif reg in sw:                                   # fixed-colour region (Jonah's sandals, streaks)
                uv = swatch_uv(ch, reg)
            elif ch in FISH and reg == "mouth":                # mouth inside: dark at the throat, pink at the lips
                uv = swatch_uv(ch, "mouth", 0.06 + 0.88 * smoothstep(zc, 0.232, p.z))
            elif pt.get("decal") and ch in FISH:
                du = (-p.z - dec[0]) / (dec[2] - dec[0]); dv = (p.y - dec[1]) / (dec[3] - dec[1])
                if not face_ok or in_swatch(ch, du, dv, 0.04):
                    du, dv = -3.0, -3.0
                uv = (du, dv)
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
    if ch in FISH:
        return
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


_kit_eyelid_cage = eyelid_cage


def eyelid_cage(C, face_obj, sheet):
    """Humans: the kit's lids. The fish: two thin lids on the cheeks above the eyes; each lid row sits on the most
    outward cheek point over its whole travel (rest -> closed), so a closed eye is visible (Daniel's lion bug, C1)."""
    if C.ch not in FISH:
        return _kit_eyelid_cage(C, face_obj, sheet)
    me = face_obj.data
    vs = [to_design(face_obj.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    bvh = BVHTree.FromPolygons([tuple(v) for v in vs], [tuple(p.vertices) for p in me.polygons])
    ez, ey, ew, eh = C.F["eyeLocal"]
    top, h0, closed = C.lid["top"], C.lid["h0"], C.lid["closed"]
    cg = Cage()
    for sx in (1, -1):
        cols = []
        for i in range(9):
            xi = (i / 8 - 0.5) * 2
            z = ez + xi * 1.36 * ew
            shp = 0.35 + 0.65 * math.sqrt(max(0.0, 1 - xi * xi))     # rounded lid edge: the middle travels furthest
            col = []
            for j in range(4):
                sg = 1.0 if C.lid.get("up") else -1.0
                y = top + sg * h0 * shp * j / 3
                d0 = h0 * shp * j / 3; d1 = max(d0, abs(closed - top) * shp * j / 3)
                xs = []
                for k in range(11):
                    hit = bvh.ray_cast(V(sx * 0.3, top + sg * lerp(d0, d1, k / 10), z), V(-sx, 0, 0), 1.0)
                    if hit[0]:
                        xs.append(abs(hit[0].x))
                col.append(V(sx * ((max(xs) + 0.0007) if xs else 0.07), y, z))
            cols.append(col)
        idx = [[cg.add(p, None) for p in col] for col in cols]
        for i in range(8):
            for j in range(3):
                q = (idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1])
                cg.face(q if sx > 0 else tuple(reversed(q)), C.lid_reg, 0)
    C.lid["closedScale"] = round(abs(C.lid["top"] - C.lid["closed"]) / C.lid["h0"], 2)
    return cg


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
    lid_part = getattr(C, "lid_part", "face")
    for pt in C.parts:
        o = make_part_object(C, ch, pt, sheet, rig)
        objs.append((o, pt))
        if pt["name"] == lid_part:
            face_obj = o
    lid = dict(name="eyelids", cage=eyelid_cage(C, face_obj, sheet), rigid="eyelids", subdiv=0, piece_as=lid_part)
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
    if ch in FISH:
        to_uv = lambda X, Y: (X + sheet[0] + 0.5, (Y + sheet[1]) / ART_H)
        stats = side_uv([bodyo] + props, sheet, to_uv, INSET)
    else:
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
                if ch in FISH:
                    p = V(sheet[0] - p.z, p.y, 0)
                bb = d["bb"]; bb[0] = min(bb[0], p.x); bb[1] = min(bb[1], p.y); bb[2] = max(bb[2], p.x); bb[3] = max(bb[3], p.y)
    return C, rig, bodyo, props, rep


def id_materials(objs, idmap):
    """One flat colour per (piece, region). The fish's mouth inside (only a hair line shows when shut) draws as the
    lower-jaw belly, so the sheet gets no sliver region there."""
    remap = {}
    if "fish.mouth" in REGIONS and "fish.belly" in REGIONS:
        remap[REGIONS.index("fish.mouth") + 1] = (piece_id(("fish", "body", 0)), REGIONS.index("fish.belly") + 1)

    def key_fn(p, r):
        return remap.get(r, (p, r))

    def mat_fn(k):
        if k not in idmap:
            idmap[k] = len(idmap) + 1
        n = idmap[k]
        return flat_mat(f"id_{n}", [c / 255 for c in id_colour(n)])
    for o in objs:
        set_face_materials(o, key_fn, mat_fn)


def id_list(idmap):
    ids = []
    for (p, r), n in sorted(idmap.items(), key=lambda kv: kv[1]):
        ch, pname, k = PIECES[p - 1]; rch, reg = REGIONS[r - 1].split(".")
        ids.append({"id": n, "rgb": id_colour(n), "char": ch, "part": pname, "piece": k, "region": reg,
                    "hex": PALETTE[ch].get(reg, "#cccccc")})
    return ids
def side_uv(objs, sheet, to_uv, inset):
    """Side-view characters (the fish; Daniel lion method): UV0 = SIDE projection of the left side (+X) at its slot: page X = -z (nose to -X),
    page Y = y. Every vertex is mirrored to the left side first (|x|), so the right side samples the drawing of the
    left side (a symmetric body matches). A face keeps the projection when all its (mirrored) corners face +X and a
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
    """Faces flagged st_hidden (side-view characters) take one texel: the deepest pixel of their own (character, region) in the
    given ID render (the printed sheet)."""
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
    # ---- sheet ID render (front ortho, 2x art rect, no AA): one colour per (piece, region); eyelids and hidden props
    # hidden; the fish turned to show its left side (nose to -X)
    setup_workbench((2000, round(2000 * ART_H)))
    s = sc(); s.render.film_transparent = True; s.display.render_aa = 'OFF'
    s.display.shading.light = 'FLAT'; s.display.shading.color_type = 'MATERIAL'
    front_ortho_camera()
    if "fish" in built:
        side_rotate(built["fish"][1], True)
    idmap = {}
    on = all_meshes()
    for o in on:
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    id_materials(on, idmap)
    render(os.path.join(WORK, "id_2x.png"))
    ids = id_list(idmap)
    json.dump({"note": "front-ortho ID render of the rest pose at sheet positions (2000 px = art width); background = "
                       "alpha 0; eyelids and hidden props hidden; the fish is drawn in side view (its left side, nose "
                       "to -X); its mouth inside draws as the lower-jaw belly",
               "size": [s.render.resolution_x, s.render.resolution_y], "ids": ids},
              open(os.path.join(WORK, "id_2x.json"), "w"), indent=1)
    for o in all_meshes():
        o.hide_render = False
    anchor_info = apply_pixel_anchors(os.path.join(WORK, "id_2x.png"), ids)
    report["fishTexels"] = side_texels(os.path.join(WORK, "id_2x.png"), ids, [c for c in FISH if c in built])
    fix_info = fix_uvs_by_id(os.path.join(WORK, "id_2x.png"), ids)
    report["uvFixByIdRender"] = fix_info
    if "fish" in built:
        side_rotate(built["fish"][1], False)
    # ---- regions_characters.json
    regions_out = {"version": 1, "generatedBy": "pipeline/jn_characters.py",
                   "note": "Per character: colourable regions (face attribute st_region), the mesh parts that carry "
                           "them, demo colour, bbox on the sheet (x, y in art units, y up from the art rect bottom; "
                           "the fish's in side view, nose to -X), and anchors (regions too small to colour, or with a "
                           "fixed colour, take a constant UV inside a larger region and print as detail lines). ID "
                           "render for the line art: id_characters_2x.png/.json (same scheme as Ruth / Daniel).",
                   "sheet": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]} for ch in ONLY},
                   "sheetSource": SHEET_SRC, "artHeightUnits": ART_H, "characters": {}}
    for ch in ONLY:
        C, rig, body, props, rep = built[ch]
        regs = {}
        allbb = [9, 9, -9, -9]
        for reg, d in rep["regions"].items():
            bb = [round(v, 4) for v in d["bb"]]
            if bb[0] < 9 and reg not in SWATCHES.get(ch, {}) and reg != "mouth":
                allbb = [min(allbb[0], bb[0]), min(allbb[1], bb[1]), max(allbb[2], bb[2]), max(allbb[3], bb[3])]
            zh, en = REGION_NAMES.get(reg, (reg, reg))
            regs[reg] = {"id": REGIONS.index(f"{ch}.{reg}") + 1, "hex": PALETTE[ch].get(reg), "zh": zh, "en": en,
                         "parts": sorted(d["parts"]), "bboxSheet": bb if bb[0] < 9 else None}
            if reg in SWATCHES.get(ch, {}) or (ch in FISH and reg == "mouth"):
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
        fish = ch in FISH
        entry = {
            ("size" if fish else "height"): (FISH_SIZE if fish else CONTRACT_HEIGHT[ch]),
            "bboxSheet": [round(v, 4) for v in allbb], "regions": regs,
            "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                          "projection": "side (X = -z, both cheeks)" if fish else "front",
                          "swatches": {k: [round(x, 3) for x in v] for k, v in SWATCHES.get(ch, {}).items()},
                          "files": {e: f"docs/jonah/design/faces/{ch}_{e}.png" for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": ("local Y (along the bone, pointing UP: lower lids rise over the eyes)"
                                                  if fish else "local Y (along the bone, pointing down)"), "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": ({"pose": "hovering level, belly on y = 0, mouth shut", "facing": "+Z (nose toward the viewer)",
                          "root": "on the ground under the middle of the length"} if fish else
                         {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z"}),
            "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                      for b, v in PROPS[ch].items()},
            "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
        if fish:
            entry["projection"] = {"kind": "side", "note": "UV0 = the fish's left side seen from +X: u = -z + sheetX + "
                                   "0.5, v = (y + sheetY) / artH (x mirrored to |x|, so both sides share the drawing); "
                                   "faces not seen from the side take one clean texel of their own region"}
            entry["jaw"] = {"bone": "jaw", "openDeg": 55, "axis": "about the hinge, design X", "hinge": list(FISH_MOUTH["hinge"])}
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
    sc()["jn_regions"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({ch: {k: v for k, v in r.items() if k != "bones"} for ch, r in report["chars"].items()}))


GOLD = set()


class _RegionLookup(dict):
    def __missing__(self, r):
        tab = json.loads(sc().get("jn_regions", "[]"))
        for i, k in enumerate(tab):
            self[i + 1] = k.split(".")[1]
        return dict.__getitem__(self, r)


REGION_OF = _RegionLookup()


def preview_material_jn(ch, reg, decal_img):
    """Kit preview material; the fish's mouth inside and the fixed-colour parts show their decal swatch colour."""
    m = preview_material(ch, reg, decal_img)
    return m


def char_frame(ch):
    """(height for framing, head centre y, head size) per character (character-local)."""
    if ch in FISH:
        return 0.20, FISH_EYE["y"], 0.10
    L = landmarks(ch); Hh = SPEC[ch]["height"]
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
        set_face_materials(o, lambda p, r: r, lambda r, ch=ch: preview_material_jn(ch, REGION_OF[r], imgs.get(ch)))
    return imgs


def show(chs, props=False):
    for o in all_meshes():
        if o.name not in ("floor", "backdrop"):
            o.hide_render = o.name.split("_")[0] not in chs or (is_hidden_prop(o) and not props)


def set_decal(ch, img):
    for m in bpy.data.materials:
        if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
            m.node_tree.nodes["decal"].image = img


def mode_preview():
    imgs = preview_setup()
    present = [ch for ch in CHARS if bpy.data.objects.get(f"{ch}_rig")]
    cam = camera()
    for ch in [c for c in ONLY if c in present]:
        show([ch])
        rig = bpy.data.objects[f"{ch}_rig"]; x = rig.location.x; zb = rig.location.z; yb = rig.location.y
        Hh, hy0, Hd = char_frame(ch)
        hy = zb + hy0
        if ch in FISH:
            sc().render.resolution_x, sc().render.resolution_y = 960, 720
            tgt = Vector((x, yb, zb + 0.095))
            for nm, yaw, h, dist in (("side", 90, 0.03, 1.20), ("q34", 35, 0.06, 1.15), ("front", 0, 0.04, 0.95),
                                     ("back", 200, 0.06, 1.15), ("phone", 60, 0.75, 1.30), ("sideR", -90, 0.03, 1.20)):
                turntable(cam, tgt, yaw, dist, h, 60)
                render(os.path.join(WORK, f"pv_{ch}_{nm}.png"))
            sc().render.resolution_x, sc().render.resolution_y = 640, 640
            ht = Vector((x, yb - 0.17, hy - 0.02))
            turntable(cam, ht, 40, 0.42, 0.04, 60); render(os.path.join(WORK, f"pv_{ch}_head.png"))
            turntable(cam, ht, 90, 0.40, 0.02, 60); render(os.path.join(WORK, f"pv_{ch}_headside.png"))
            turntable(cam, Vector((x, yb, zb + 0.06)), 20, 1.0, -0.45, 60); render(os.path.join(WORK, f"pv_{ch}_under.png"))
            # the jaw at 55 degrees
            bend(rig, "jaw", V(1, 0, 0), 55)
            set_decal(ch, bpy.data.images.load(os.path.join(FACES, f"{ch}_hungry.png"), check_existing=True))
            turntable(cam, ht + Vector((0, 0, -0.02)), 90, 0.46, 0.02, 60); render(os.path.join(WORK, f"pv_{ch}_mouth.png"))
            turntable(cam, ht + Vector((0, 0, -0.02)), 30, 0.46, 0.05, 60); render(os.path.join(WORK, f"pv_{ch}_mouthq.png"))
            rig.pose.bones["jaw"].matrix_basis = Matrix.Identity(4); bpy.context.view_layer.update()
            set_decal(ch, imgs[ch])
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
            turntable(cam, Vector((x, 0, zb + Hh * 0.70)), 28, Hh * 1.6, Hh * 0.20, 60)
            render(os.path.join(WORK, f"pv_{ch}_props.png"))
            show([ch])
        sc().render.resolution_x, sc().render.resolution_y = 420, 420
        for e in EXPRESSIONS[ch]:
            set_decal(ch, bpy.data.images.load(os.path.join(FACES, f"{ch}_{e}.png"), check_existing=True))
            if ch in FISH:
                turntable(cam, Vector((x, yb - 0.17, hy - 0.02)), 72, 0.36, 0.03, 60)
            else:
                turntable(cam, Vector((x, 0, hy - 0.08 * Hd)), 12, Hd * 3.6, Hd * 0.12, 60)
            render(os.path.join(WORK, f"pv_{ch}_expr_{e}.png"))
        set_decal(ch, imgs[ch])
    if len(present) > 1:
        show(present)
        sc().render.resolution_x, sc().render.resolution_y = 1600, 1000
        turntable(cam, Vector((0.0, 0.03, 0.30)), 10, 2.0, 0.20, 50); render(os.path.join(WORK, "pv_all.png"))
        turntable(cam, Vector((0.0, 0.03, 0.22)), 18, 1.75, 1.30, 50); render(os.path.join(WORK, "pv_all_phone.png"))
    print("PREVIEW done")


def pose_test(rig, ch, variant="a"):
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4); pb.scale = (1, 1, 1)
    if ch in FISH:
        if variant in ("gulp", "gulpq"):
            bend(rig, "body1", V(1, 0, 0), -10); bend(rig, "jaw", V(1, 0, 0), 55)
            bend(rig, "tail", V(1, 0, 0), 12); bend(rig, "finL", V(0, 0, 1), -25); bend(rig, "finR", V(0, 0, 1), 25)
            rig.pose.bones["eyelids"].scale = (1, C_LID_CLOSED.get(ch, 12.0) * 0.55, 1)
        elif variant == "swim":
            bend(rig, "body1", V(0, 1, 0), 8); bend(rig, "body2", V(0, 1, 0), -10); bend(rig, "body3", V(0, 1, 0), -14)
            bend(rig, "tail", V(0, 1, 0), -22); bend(rig, "dorsal", V(0, 0, 1), 10)
        elif variant == "closed":
            rig.pose.bones["eyelids"].scale = (1, C_LID_CLOSED.get(ch, 12.0), 1)
        elif variant == "fins":
            bend(rig, "finL", V(1, 0, 0), -40); bend(rig, "finL", V(0, 0, 1), 30); bend(rig, "finR", V(0, 0, 1), -30)
            bend(rig, "dorsal", V(1, 0, 0), 15); bend(rig, "tail", V(1, 0, 0), -20)
        elif variant == "burp":
            bend(rig, "jaw", V(1, 0, 0), 10); bend(rig, "body1", V(1, 0, 0), -5)
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
    if ch == "jonah":
        bend(rig, "coatL", V(1, 0, 0), 25); bend(rig, "coatR", V(0, 0, 1), -15); bend(rig, "belt1", V(1, 0, 0), 30)
    if ch == "captain":
        bend(rig, "wrap1", V(1, 0, 0), -30); bend(rig, "sash1", V(1, 0, 0), 30)
    bpy.context.view_layer.update()


C_LID_CLOSED = {}


def mode_posetest():
    imgs = preview_setup()
    cam = camera()
    present = [ch for ch in CHARS if bpy.data.objects.get(f"{ch}_rig")]
    try:
        rj = json.load(open(os.path.join(MODEL, "regions_characters.json")))["characters"]
        for ch in present:
            C_LID_CLOSED[ch] = rj[ch]["blink"]["closed"]
    except Exception:                                           # noqa: BLE001
        pass
    for ch in present:
        rig = bpy.data.objects[f"{ch}_rig"]
        show([ch])
        if ch in FISH:
            hd = rig.location + Vector((0, -0.17, FISH_EYE["y"] - 0.02))
            for var, img_e, view in (("gulp", "gulp", (90, 0.55, 0.02, Vector((0, 0.0, 0.08)))),
                                     ("gulpq", "gulp", (35, 0.50, 0.10, Vector((0, 0.0, 0.08)))),
                                     ("swim", "calm", (20, 1.0, 0.85, Vector((0, 0.17, 0.0)))),
                                     ("closed", "calm", (75, 0.30, 0.03, Vector((0, 0.0, 0.0)))),
                                     ("fins", "happy", (40, 1.0, 0.25, Vector((0, 0.17, -0.03)))),
                                     ("burp", "oops", (80, 0.50, 0.03, Vector((0, 0.0, 0.0))))):
                pose_test(rig, ch, var)
                set_decal(ch, bpy.data.images.load(os.path.join(FACES, f"{ch}_{img_e}.png"), check_existing=True))
                yaw, dist, h, off = view
                sc().render.resolution_x, sc().render.resolution_y = 640, 800
                turntable(cam, hd + off, yaw, dist, h, 60)
                render(os.path.join(WORK, f"pose_{ch}_{var}.png"))
            pose_test(rig, ch, "none")
            set_decal(ch, imgs[ch])
            continue
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
    print("POSETEST done")


def mode_uvcheck():
    """Models wearing $JN_WORK/uvproof.png (or $JN_UV_TEXTURE) through UV0: front ortho with the fish turned to its side
    (must equal the sheet) and 3/4 + back perspective (each region keeps its colour all round), the fish close."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get(ENV + "UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        o.data.materials.clear(); o.data.materials.append(m)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    sc().view_settings.view_transform = 'Standard'
    cam = front_ortho_camera()
    fr = bpy.data.objects.get("fish_rig")
    if fr:
        side_rotate(fr, True)
    for o in all_meshes():
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    bpy.data.objects["backdrop"].hide_render = True
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    if fr:
        side_rotate(fr, False)
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = False
    bpy.data.objects["backdrop"].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    sc().render.resolution_x, sc().render.resolution_y = 1600, 900
    for nm, yaw in (("q34", 30), ("back", 180)):
        turntable(cam, Vector((0.0, 0.03, 0.30)), yaw, 2.0, 0.16, 50)
        render(os.path.join(WORK, f"uv_{nm}.png"))
    sc().render.resolution_x, sc().render.resolution_y = 1000, 700
    for o in all_meshes():
        o.hide_render = o.hide_render or not o.name.startswith("fish_")
    if fr:
        for nm, yaw, h in (("fishL", 90, 0.03), ("fishR", -90, 0.03), ("fishTop", 30, 0.80), ("fishFront", 0, 0.05)):
            turntable(cam, Vector((fr.location.x, 0.0, fr.location.z + 0.10)), yaw, 1.15, h, 60)
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
        parents = {b.name: (b.parent.name if b.parent else None) for b in arms[0].data.bones} if arms else {}
        info = {"armatures": len(arms), "bonesMatch": bones == want, "missing": sorted(set(want) - set(bones)),
                "extra": sorted(set(bones) - set(want)), "parents": parents, "actions": len(bpy.data.actions),
                "meshes": {}}
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
        info["budget"] = 22000 if ch in FISH else 25000
        info["trisUnderBudget"] = tris <= info["budget"]
        pts = [(o.matrix_world @ v.co) for o in meshes if not o.name.endswith("_eyelids") and not
               (o.parent_bone and PROPS.get(ch, {}).get(o.parent_bone) is False) for v in o.data.vertices]
        info["heightTop"] = round(max(p.z for p in pts), 4)
        info["minY"] = round(min(p.z for p in pts), 4)
        if ch in FISH:
            info["length"] = round(max(-p.y for p in pts) - min(-p.y for p in pts), 4)   # design z = -Blender y
            info["noseZ"] = round(max(-p.y for p in pts), 4); info["tailZ"] = round(min(-p.y for p in pts), 4)
            info["width"] = round(max(p.x for p in pts) - min(p.x for p in pts), 4)
            info["height"] = round(info["heightTop"] - info["minY"], 4)
        else:
            info["heightErrPct"] = round(100 * (info["heightTop"] - CONTRACT_HEIGHT[ch]) / CONTRACT_HEIGHT[ch], 2)
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps({c: {k: v for k, v in i.items() if k not in ("meshes", "parents")} for c, i in out.items()}))


if __name__ == "__main__":
    {"build": mode_build, "preview": mode_preview, "posetest": mode_posetest, "verify": mode_verify,
     "uvcheck": mode_uvcheck,
     "all": lambda: __import__("subprocess").run([os.environ.get("PYTHON3", "python3"), os.path.abspath(__file__), "all"],
                                                 check=True)}[MODE]()
