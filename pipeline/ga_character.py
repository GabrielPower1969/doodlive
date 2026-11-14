"""Gabriel (story pack, the archangel): the hero character `gabriel` — mesh, rig, weights, UVs, face decals, previews,
GLB.

Contract: docs/gabriel/CONTRACT.md §2-§3 (size, sheet slot, bone names incl. the wing bones, props), look:
docs/gabriel/DESIGN.md, notes: docs/gabriel/RIG.md. Built on the Daniel pack's method (pipeline/da_characters.py:
procedural quad cages from pipeline/story_mesh.py, a head mapped from the D&G base head by landmarks, box-modelled
hands with separate fingers, face decals on UV1 + an `eyelids` blink that lies on the eye surface, UV0 = front page
projection with occlusion + ID-render fixes); the shared helpers it needs are copied in here so the Daniel / Ruth /
Esther outputs cannot change. New for Gabriel (one hero, up to 90k triangles):
  * a full sculpted body: moulded cuirass (pectorals, sternum, centre seam, abdomen, rib arch), muscular arms and legs,
    all subdivided and smooth shaded;
  * plate armour with thickness and soft bevels: two overlapping pauldron plates with a round boss per shoulder, a
    V gorget with a pointed tab, vambraces and greaves with pointed edges and a keel, knee cops, a belt with a buckle;
  * a wound sash with a hanging front panel (`sash1 sash2`), hip skirt panels, a sheathed sword (`sword`), a herald
    trumpet (`trumpet`, hidden by default);
  * hair as layered sculpted locks swept back from a side parting to the shoulders (`hair1 hair2`);
  * wings of several hundred separate feather meshes per pair: tertials, secondaries, primaries (each with a raised
    shaft and a soft round tip) under three rows of coverts on the front and on the back, skinned feather by feather
    to `wingL1 wingL2 wingL3 wingL_prim` (and R) so the fan closes and the wing folds behind the back.

Run (repo root):
  python3 pipeline/ga_character.py all                                           # everything below, in order
  python3 pipeline/ga_character.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/ga_character.py -- build        # model, rig, GLB, blend, ID render
  python3 pipeline/ga_character.py proof                                         # $GA_WORK/uvproof.png
  blender -b --factory-startup --python pipeline/ga_character.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/ga_character.py -- uvcheck      # model wearing uvproof.png
  blender -b --factory-startup --python pipeline/ga_character.py -- posetest     # wings folded / flapping, kneel, trumpet
  blender -b --factory-startup --python pipeline/ga_character.py -- verify       # re-import the GLB, check bones/budget
  python3 pipeline/ga_character.py compose                                       # preview_*.png contact sheets
Blender: $BLENDER, else `blender` on PATH, else /Applications/Blender.app. Intermediate renders go to $GA_WORK
(default /tmp/gabriel_char/work).
"""
import sys, os, json, math, random, shutil

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/gabriel/model")
FACES = os.path.join(ROOT, "docs/gabriel/design/faces")
WORK = os.environ.get("GA_WORK", "/tmp/gabriel_char/work")
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/gabriel/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("gabriel",)
HUMANS = ("gabriel",)
LIONS = ()
ON_SHEET = ("gabriel",)
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
EXTRA_BONES = {"gabriel": ["wingL1", "wingL2", "wingL3", "wingL_prim", "wingR1", "wingR2", "wingR3", "wingR_prim",
                           "hair1", "hair2", "sash1", "sash2", "trumpet", "sword"]}


def bone_list(ch):
    return CONTRACT_BONES + EXTRA_BONES[ch]


PROPS = {"gabriel": {"trumpet": False, "sword": True}}      # bone -> shown by default
CONTRACT_HEIGHT = {"gabriel": 0.62}
DEFAULT_SHEET = {"gabriel": (0.0, 0.015)}
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (as Esther / Ruth / Daniel)

# ---------------------------------------------------------------------------------------------- palette (DESIGN.md)
PALETTE = {
    "gabriel": {"skin": "#F2C9A0", "hair": "#9A6533", "pauldrons": "#E6B23E", "collar": "#E6B23E",
                "cuirass": "#F1E7D2", "sleeves": "#F1E7D2", "vambraces": "#E6B23E", "sash": "#D9732C",
                "belt": "#E6B23E", "skirt": "#F1E7D2", "leggings": "#F1E7D2", "greaves": "#E6B23E",
                "hilt": "#E6B23E", "gem": "#3C8FD8", "scabbard": "#F1E7D2", "wingCoverts": "#FFFDF6",
                "wingFeathers": "#F3EAD6", "trumpet": "#E6B23E"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发", "hair"), "pauldrons": ("肩甲", "pauldrons"),
    "collar": ("金领", "gold collar"), "cuirass": ("胸甲", "cuirass"), "sleeves": ("袖子", "sleeves"),
    "vambraces": ("护臂", "vambraces"), "sash": ("腰带和前襟", "sash"), "belt": ("金腰带", "belt"),
    "skirt": ("短裙", "skirt"), "leggings": ("裤子", "leggings"), "greaves": ("护腿和靴子", "greaves and boots"),
    "hilt": ("剑柄", "sword hilt"), "gem": ("宝石", "sword gem"), "scabbard": ("剑鞘", "scabbard"),
    "wingCoverts": ("翅膀上层的短羽毛", "wing coverts"), "wingFeathers": ("翅膀的长羽毛", "long wing feathers"),
    "trumpet": ("号角", "trumpet"),
}
# regions too small to colour on A4: constant UV deep inside a printed region ("char.region", or "char.FACE" = the
# face skin away from eyes / brows / nose / mouth); a region anchored to itself = its own widest printed spot
ANCHORS = {"gabriel": {"gem": "gabriel.gem"}}
# hidden-by-default props are not printed: their regions sample a printed region of similar colour (first target that
# exists wins); design.json characters.<id>.propUV wins
PROP_ANCHORS = {"gabriel": {"trumpet": ["gabriel.pauldrons"]}}
# parts whose printed area is a sliver, or that must not pick up printed detail: one UV inside a larger region
PART_ANCHORS = {"gabriel": {("eyelidAnchor", "skin"): "gabriel.FACE"}}

# ---------------------------------------------------------------------------------------------- proportions
# About 7 heads tall, heroic: broad shoulders, narrow waist, long legs. Units = art width; feet on y = 0, crown 0.62.
FR = dict(mouth=0.186, nose=0.300, eye=0.495, brow=0.585)
SPEC = {
    "gabriel": dict(
        height=0.62, S=0.62 / 0.30, k=1.0, kx=1.0,
        top=0.6045, chin=0.5180, hw=0.0274, zc=0.0030, depth=1.10, jaw=0.15, cheek=-0.02, chin_narrow=0.14,
        crown=0.0, noseH=0.0096, nose_w=0.84, nose_long=0.0, brow=1.4, lips=0.50, chinAmt=1.5, sockets=0.80,
        cheekbones=0.95,
        neckBase=0.4880, neck=(0.0192, 0.0162, -0.0176), shoulder=(0.0860, 0.4780), chestY=0.4400,
        waistY=0.3850, hipY=0.3350, hipX=0.0360, kneeY=0.1700, ankleY=0.0350, footLen=0.0700, footScale=1.0,
        upperArm=0.1180, forearm=0.1020, hand=0.0660, palmFrac=0.52,
        handDims=dict(palmW=0.0308, palmH=0.0124, wristW=0.0218, wristH=0.0152, fingerW=0.0075,
                      fingerT=0.0069, thumbW=0.0080, thumbT=0.0071, armR=0.0140)),
}
FIST = set()
FIST_BEND = {}


def landmarks(ch):
    s = SPEC[ch]; H = s["top"] - s["chin"]
    L = dict(top=s["top"], chin=s["chin"], zc=s["zc"], hw=s["hw"])
    for k, f in FR.items():
        L[k] = s["chin"] + s.get("fr", {}).get(k, f) * H
    return L


EYE = {"gabriel": (0.430, 0.300, 0.202)}      # eye centre x, half width, half height (fractions of hw)


def face_layout(ch):
    """Decal rectangle (character-local x0 y0 x1 y1) and eye / brow / mouth placement in normalised decal space
    (0..1, y up): a square from just under the mouth, side max(1.76 hw, 0.72 H) (as Esther / Ruth / Daniel)."""
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


EXPRESSIONS = {"gabriel": ["calm", "smile", "talk", "kind", "joy", "announce", "blow", "wink"]}
DEFAULT_EXPR = {"gabriel": "smile"}
CLIP_EXPRESSION = {   # suggestion for Animation / Integration (clip -> decal), CONTRACT §4 clip names
    "gabriel": {"idle": "smile", "hover": "calm", "fly_down": "calm", "fold_wings": "smile", "walk": "calm",
                "kneel_talk": "kind", "stand_up": "smile", "talk": "talk", "point_up": "kind",
                "raise_trumpet": "joy", "blow_trumpet": "blow", "spread_wings": "announce", "bless": "kind",
                "wave": "joy", "fly_up": "joy"},
}


def sheet_positions():
    """sheetX / sheetY: assets/gabriel/design.json characters.gabriel when present (Set + sheet role), else the
    CONTRACT §2 slot."""
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
    made = {}
    for ch in CHARS:
        F = face_layout(ch)
        eL, eR, half, by, my, ny_ = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"], F["nose"]
        bcol = (98, 60, 30, 255); iris = (126, 86, 44); bw = 0.045
        lipcol = (196, 118, 100, 170)
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            E = dict(look=(0, 0.02), top=0.92, bot=0.90, tilt=0.10, lash=0, mode="open", lid=0.16, inner_up=0.0,
                     pupil=0.52, wet=False)
            El, Er = {}, {}
            Bp = dict(raise_=0.050, inner=-0.006, arch=0.16, thick=1.0, outer=0.006)
            Bl, Br = {}, {}
            M = dict(kind="soft", wd=0.086, jaw=0.0, side=0.0)
            bl = 26; folds = False; puff = False; crs = True
            if ex == "calm":
                E.update(top=0.88); M.update(kind="soft", wd=0.080)
            elif ex == "smile":
                E.update(top=0.84, bot=0.78); Bp.update(raise_=0.056, arch=0.26); M.update(kind="smile", wd=0.094)
                bl = 40
            elif ex == "talk":
                Bp.update(raise_=0.056, arch=0.24); M.update(kind="open", wd=0.078, jaw=0.06); bl = 30
            elif ex == "kind":
                E.update(top=0.80, bot=0.80, look=(0, -0.08)); Bp.update(raise_=0.064, inner=0.014, arch=0.22, outer=-0.006)
                M.update(kind="smile", wd=0.080); bl = 48
            elif ex == "joy":
                E.update(top=0.74, bot=0.58, tilt=0.14); Bp.update(raise_=0.068, arch=0.34)
                M.update(kind="grin", wd=0.100, jaw=0.06); bl = 60
            elif ex == "announce":
                E.update(top=1.10, bot=1.0, pupil=0.50, lid=0.12); Bp.update(raise_=0.080, arch=0.38)
                M.update(kind="open", wd=0.090, jaw=0.62); bl = 36
            elif ex == "blow":
                E.update(mode="closed"); Bp.update(raise_=0.062, inner=0.010, arch=0.26)
                M.update(kind="o", wd=0.040, jaw=-0.25); bl = 90; puff = True; crs = False
            elif ex == "wink":
                E.update(top=0.86, bot=0.74); Er = dict(mode="happy")
                Bp.update(raise_=0.060, arch=0.28); Br = dict(raise_=0.042, arch=0.16)
                M.update(kind="grin", wd=0.090, jaw=-0.02); bl = 50
            if bl:
                blush(img, 0.31 if not puff else 0.33, ny_ - 0.040, 0.085 if not puff else 0.105,
                      0.045 if not puff else 0.075, bl)
            nose_hint(img, ny_ - 0.004, 0.027, strength=0.80)
            for side, c in ((1, eL), (-1, eR)):
                e_ = dict(E); e_.update(El if side == 1 else Er)
                eye(img, c, half, side=side, iris=iris, line=0.019, **e_)
                if crs and e_["mode"] == "open":
                    crease(img, c, half, side, lift=1.52, col=(150, 96, 74, 105))
            dr = ImageDraw.Draw(img)
            for side, c in ((1, eL), (-1, eR)):
                b = dict(Bp); b.update(Bl if side == 1 else Br)
                brow(dr, side, (c[0], by + 0.003), half, w=bw, col=bcol, length=1.06, **b)
            if folds:
                cheek_lines(img, ny_ - 0.012, my + 0.012, 0.070, 0.150, col=(170, 104, 80, 80))
            if puff:
                for sx in (-1, 1):
                    pts = bez((0.5 + sx * 0.235, my + 0.105), (0.5 + sx * 0.300, my + 0.070),
                              (0.5 + sx * 0.300, my - 0.020), (0.5 + sx * 0.235, my - 0.055), 20)
                    lines(img, [pts], w=0.011, col=(170, 104, 80, 150))
            mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, lipcol=lipcol, jaw=M["jaw"], side=M["side"])
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
        base = PALETTE[ch]["skin"]
        bg = Image.new("RGBA", (cw, cw), tuple(int(base[k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        fc = Image.open(os.path.join(FACES, f"{ch}_{ex}.png")).resize((cw, cw), Image.LANCZOS)
        bg.alpha_composite(fc); sheet.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 8, y + cw + 4), f"{ch}_{ex}", fill=(40, 30, 20))
        small = bg.resize((64, 64), Image.LANCZOS)
        sheet.paste(small.convert("RGB"), (x + 8, y + cw + 22))
    sheet.save(os.path.join(FACES, "overview.png"))
    print("faces:", len(made), "->", FACES)
    return made


PREVIEW_VIEWS = [("front", "front"), ("q34", "3/4"), ("side", "side"), ("back", "back"), ("q34b", "3/4 back"),
                 ("phone", "phone-like high angle")]
PREVIEW_DETAILS = [("head", "face 3/4"), ("headfront", "face front"), ("headside", "head side"),
                   ("hairback", "hair, back"), ("hairtop", "hair from above"), ("chest", "cuirass + gorget"), ("pauldron", "pauldron"),
                   ("handL", "left hand"), ("handR", "right hand"), ("belt", "belt, sash, sword"),
                   ("legs", "greaves + boots"), ("wing", "wing, front"), ("wingclose", "feathers close"),
                   ("wingback", "wing, back"), ("props", "trumpet shown (rest pose)")]
POSES = [("fold", "wings folded"), ("half", "wings half open"), ("flapdown", "flap: down-stroke"),
         ("flapup", "flap: up-stroke"), ("kneel", "kneeling, wings folded"), ("trumpet", "trumpet at the lips"),
         ("bends", "limb bends, jaw, half blink, hair, sash")]
POSE_VIEWS = [("front", 0), ("q34", 40), ("side", 90), ("back", 180)]


def compose():
    """Contact sheets model/preview_gabriel.png, preview_details.png, preview_pose.png, preview_uvcheck.png from the
    $GA_WORK renders."""
    from PIL import Image, ImageDraw
    bg = (250, 246, 238)

    def grid(files, labels, cols, cell, title):
        files = [(f, lb) for f, lb in zip(files, labels) if os.path.exists(f)]
        rows = (len(files) + cols - 1) // cols
        im = Image.new("RGB", (cols * cell[0], rows * (cell[1] + 26) + 34), bg)
        d = ImageDraw.Draw(im)
        d.text((10, 10), title, fill=(40, 30, 20))
        for i, (f, lb) in enumerate(files):
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
    ch = "gabriel"
    top = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in PREVIEW_VIEWS], [lb for _, lb in PREVIEW_VIEWS], 3,
               (640, 640), "gabriel: rest pose (= sheet pose), demo palette + default face decal")
    ex = grid([os.path.join(WORK, f"pv_{ch}_expr_{e}.png") for e in EXPRESSIONS[ch]], EXPRESSIONS[ch], 4, (480, 480),
              "face decals on the model (UV1)")
    stack([top, ex], "preview_gabriel.png")
    det = grid([os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in PREVIEW_DETAILS], [lb for _, lb in PREVIEW_DETAILS],
               5, (480, 480), "gabriel: close-ups")
    stack([det], "preview_details.png")
    pf, lb = [], []
    for p, plb in POSES:
        for v, _ in POSE_VIEWS:
            pf.append(os.path.join(WORK, f"pose_{p}_{v}.png")); lb.append(f"{plb} · {v}")
    pf.append(os.path.join(WORK, "pose_trumpet_close.png")); lb.append("trumpet at the lips · close")
    pf.append(os.path.join(WORK, "pose_blink_close.png")); lb.append("eyelids closed · close")
    if any(os.path.exists(f) for f in pf):
        grid(pf, lb, 5, (384, 438), "pose tests (posed with the rig only, no shape keys)").save(
            os.path.join(MODEL, "preview_pose.png"))
    uv = [os.path.join(WORK, f) for f in ("uvproof.png", "uv_front.png", "uv_q34.png", "uv_back.png")]
    if all(os.path.exists(f) for f in uv):
        a = Image.open(uv[0]).convert("RGB"); b = Image.open(uv[1]).convert("RGBA")
        bgw = Image.new("RGBA", b.size, (255, 255, 255, 255)); bgw.alpha_composite(b); b = bgw.convert("RGB")
        h = round(a.height * 0.72)
        a = a.crop((0, a.height - h, a.width, a.height)); b = b.crop((0, b.height - h, b.width, b.height))
        c = Image.open(uv[2]).convert("RGB").resize((1000, h)); d_ = Image.open(uv[3]).convert("RGB").resize((1000, h))
        im = Image.new("RGB", (2000, 34 + 2 * (h + 26)), bg); d = ImageDraw.Draw(im)
        d.text((10, 10), "UV0 proof: a perfectly coloured sheet (ID render in demo colours, top left) worn by the model: "
                         "front ortho must equal the sheet; 3/4 and back keep each region's colour", fill=(40, 30, 20))
        im.paste(a, (0, 34)); im.paste(b, (1000, 34)); im.paste(c, (0, 34 + h + 26)); im.paste(d_, (1000, 34 + h + 26))
        for x, y, t in ((8, 34 + h + 6, "sheet (texture)"), (1008, 34 + h + 6, "model, front ortho"),
                        (8, 34 + 2 * h + 32, "3/4"), (1008, 34 + 2 * h + 32, "back")):
            d.text((x, y), t, fill=(60, 50, 40))
        im.save(os.path.join(MODEL, "preview_uvcheck.png"))
    print("composed previews ->", MODEL)


def proof():
    """$GA_WORK/uvproof.png: the ID render with every (piece, region) in its demo colour and a thin dark outline,
    i.e. a perfectly coloured sheet; uvcheck renders the model wearing it through UV0."""
    from PIL import Image, ImageFilter
    import numpy as np
    meta = json.load(open(os.path.join(MODEL, "id_characters_2x.json")))
    im = np.array(Image.open(os.path.join(MODEL, "id_characters_2x.png")).convert("RGBA"))
    out = np.zeros(im.shape[:2] + (3,), np.uint8); out[:] = (250, 248, 242)
    key = im[..., 0].astype(int) * 65536 + im[..., 1].astype(int) * 256 + im[..., 2]
    lab = np.zeros(im.shape[:2], np.int32)
    for e in meta["ids"]:
        r, g, b = e["rgb"]; h = e["hex"].lstrip("#")
        m = (key == r * 65536 + g * 256 + b) & (im[..., 3] > 0)
        out[m] = [int(h[i:i + 2], 16) for i in (0, 2, 4)]
        lab[m] = e["id"]
    e = np.zeros(lab.shape, bool)
    e[:-1, :] |= lab[:-1, :] != lab[1:, :]; e[:, :-1] |= lab[:, :-1] != lab[:, 1:]
    e = np.array(Image.fromarray((e * 255).astype(np.uint8)).filter(ImageFilter.MaxFilter(3))) > 0
    out[e] = (60, 45, 35)
    Image.fromarray(out).resize((1000, round(1000 * im.shape[0] / im.shape[1])), Image.LANCZOS).save(
        os.path.join(WORK, "uvproof.png"))
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
            subprocess.run([bl, "-b", "--factory-startup", "--python", me, "--", "build"], check=True,
                           stdout=subprocess.DEVNULL)
            proof()
            for m in ("preview", "uvcheck", "posetest", "verify"):
                subprocess.run([bl, "-b", "--factory-startup", "--python", me, "--", m], check=True,
                               stdout=subprocess.DEVNULL)
            compose()
            v = json.load(open(os.path.join(WORK, "verify.json")))
            for ch, i in v.items():
                print(ch, "bonesMatch", i["bonesMatch"], "actions", i["actions"], "tris", i["tris"],
                      "uvOrderOK", i.get("uvOrderOK"), "top", i["heightTop"], "minY", i["minY"], "span", i.get("span"))
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
ONLY = list(CHARS)
SHEET, ART_H, SHEET_SRC, PROP_UV = sheet_positions()


# =============================================================================================== context + skeleton
class Ctx:
    def __init__(self, ch):
        self.ch = ch; self.F = face_layout(ch)
        self.s = SPEC[ch]; self.L = landmarks(ch)
        self.H = self.L["top"] - self.L["chin"]; self.S = self.s["S"]
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


# ---------------------------------------------------------------------------------------------- wing layout
# Left wing (x > 0) in the sheet plane, spread (rest pose); the right wing is its mirror. S shoulder, E elbow,
# W wrist, T hand tip of the wing arm; TRAIL = the trailing outline the flight-feather tips reach (body -> wing tip).
WS, WE, WW, WT = (0.040, 0.455), (0.135, 0.515), (0.250, 0.562), (0.322, 0.603)
TRAIL = [(0.060, 0.092), (0.130, 0.110), (0.215, 0.165), (0.290, 0.232), (0.355, 0.308), (0.400, 0.382),
         (0.435, 0.450), (0.462, 0.520), (0.478, 0.590), (0.485, 0.660), (0.485, 0.730), (0.478, 0.795)]
N_TER, N_SEC, N_PRI = 6, 12, 12
PRIM_FAN_DEG = 96.0                 # angle between the innermost and the outermost primary at rest


def wing_z(x, y):
    """Depth of the wing surface behind the body: swept back toward the tip, slightly cupped forward at the bottom."""
    ax = abs(x)
    return (-0.070 - 0.062 * smoothstep(0.04, 0.50, ax) ** 1.2
            + 0.012 * smoothstep(0.45, 0.15, y) * smoothstep(0.05, 0.30, ax))


def W3(x, y, layer=0.0):
    return V(x, y, wing_z(x, y) + layer)


def wing_n(x, y):
    e = 1e-3
    return V(-(wing_z(x + e, y) - wing_z(x - e, y)) / (2 * e), -(wing_z(x, y + e) - wing_z(x, y - e)) / (2 * e), 1).normalized()


def arm_xy(s):
    """Wing arm line, s in [0, 3]: 0 shoulder, 1 elbow, 2 wrist, 3 hand tip."""
    return cr_open([V(p[0], p[1], 0) for p in (WS, WE, WW, WT)], min(3.0, max(0.0, s)) / 3.0)


def trail_xy(q):
    return cr_open([V(p[0], p[1], 0) for p in TRAIL], min(1.0, max(0.0, q)))


def flight_specs():
    """(kind, s root, q tip, fan index 0..1) of the flight feathers, body -> wing tip."""
    out = []
    for i in range(N_TER):
        out.append(("ter", 0.12 + 0.80 * i / (N_TER - 1), 0.155 * i / (N_TER - 1), 0.0))
    for i in range(N_SEC):
        out.append(("sec", 1.02 + 0.93 * i / (N_SEC - 1), 0.185 + 0.235 * i / (N_SEC - 1), 0.0))
    for i in range(N_PRI):
        f = i / (N_PRI - 1)
        out.append(("pri", 2.0 + 0.36 * f, 0.455 + 0.545 * f, f))
    return out


def q_of_s(s):
    """Trailing-edge parameter under a point of the wing arm (for the coverts)."""
    return table([(0.0, 0.0), (0.12, 0.0), (0.92, 0.155), (1.02, 0.185), (1.95, 0.42), (2.0, 0.455), (3.0, 1.0)], s)[0]


LID_CLOSED = 20.0                   # `eyelids` local-Y scale that closes the eyes


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
        B["thigh" + side] = (V(x, s["hipY"], 0), V(xk, s["kneeY"], 0.002), "hips")
        B["shin" + side] = (V(xk, s["kneeY"], 0.002), V(xk, s["ankleY"], -0.002), "thigh" + side)
        B["foot" + side] = (V(xk, s["ankleY"], -0.002), V(xk, 0.004 * S, 0.62 * s["footLen"]), "shin" + side)
        B["toe" + side] = (V(xk, 0.004 * S, 0.62 * s["footLen"]), V(xk, 0.0032 * S, 0.95 * s["footLen"]), "foot" + side)
        # wing arm: shoulder -> elbow -> wrist -> hand tip, behind the shoulder blade; `prim` fans the primaries
        pts = [W3(sd * p[0], p[1], 0.004) for p in (WS, WE, WW, WT)]
        B[f"wing{side}1"] = (pts[0], pts[1], "chest")
        B[f"wing{side}2"] = (pts[1], pts[2], f"wing{side}1")
        B[f"wing{side}3"] = (pts[2], pts[3], f"wing{side}2")
        a = math.radians(0.0)
        pt = V(WW[0] + 0.11 * math.cos(a), WW[1] + 0.11 * math.sin(a), 0)
        B[f"wing{side}_prim"] = (pts[2].copy(), W3(sd * pt.x, pt.y, 0.004), f"wing{side}3")
    ex, ey, ew, eh = C.F["eyeLocal"]
    zf = L["zc"] + 0.020 * s["hw"] / 0.0199
    C.lid = dict(top=ey + 1.14 * eh, closedScale=LID_CLOSED)
    B["eyelids"] = (V(0, C.lid["top"], zf), V(0, C.lid["top"] - 0.010 * S, zf), "head")
    C.B = B
    C.arm = {sd: arm_frames(C, sd) for sd in "LR"}
    C.Hc = V(0, L["eye"] + 0.10 * H, L["zc"] - 0.001)


# =============================================================================================== head
def ears_spec(C):
    L = C.L; H = C.H; k = H / 0.0535
    return (L["chin"] + 0.33 * H, L["chin"] + 0.56 * H, 0.0074 * k, 0.0026 * k)


def neck_rows(C):
    s = C.s; L = C.L; hx, zf, zb = s["neck"]; nb = s["neckBase"]; S = C.S
    return [ellipse_row(L["chin"] - 0.0045 * S, hx, zf, zb), ellipse_row(L["chin"] - 0.0095 * S, hx * 1.02, zf * 1.02, zb * 1.02),
            ellipse_row(nb + 0.0030 * S, hx * 1.10, zf * 1.05, zb * 1.08), ellipse_row(nb - 0.0020 * S, hx * 1.30, zf * 1.10, zb * 1.18),
            ellipse_row(nb - 0.0070 * S, hx * 1.55, zf * 1.14, zb * 1.25)]


def hairline(C):
    """rim(u) = lower edge of the hair round the head (u = 0 front, 0.25 his left ear, 0.5 back) and the cull test
    for skin faces that the hair covers."""
    L = C.L; H = C.H; S = C.S; nb = C.s["neckBase"]
    ey0, ey1, ew, et = ears_spec(C)
    top = L["brow"] + 0.165 * H

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, top), (0.07, top + 0.004 * H), (0.12, top - 0.03 * H), (0.16, L["brow"] + 0.12 * H),
                      (0.19, L["eye"] + 0.06 * H), (0.215, L["nose"] + 0.06 * H), (0.232, ey1 + 0.004),
                      (0.268, ey1 + 0.004), (0.30, L["mouth"] + 0.02 * H), (0.36, L["chin"] - 0.03 * H),
                      (0.50, L["chin"] - 0.08 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0090 * S:
            return True
        return p.y > rim(u) + 0.0050 * S and not (0.225 < uu < 0.275 and p.y < ey1)
    return rim, cull


def build_head(C, cull):
    s = C.s; L = C.L; H = C.H
    base = mapped_head_rows(L, s["hw"], s["depth"], s["jaw"], s["cheek"], s["chin_narrow"], s["crown"])
    C.head = HeadEval(base, L)
    flat = [(r[0], r[1], r[2][0], r[2][1], r[3][0], r[3][1], r[4][0], r[4][1], r[5]) for r in base]
    rows = [(f[0], f[1], (f[2], f[3]), (f[4], f[5]), (f[6], f[7]), f[8]) for f in densify(flat, 2)]
    rows = rows + neck_rows(C)
    us = front_dense(32, 0.45)
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
    post0 = face_post_fn(L, s["hw"], L["zc"], s["noseH"], 1.0, s["brow"], s["lips"], s["chinAmt"], s["nose_w"],
                         s["nose_long"], s["sockets"], s["cheekbones"])
    hw = s["hw"]

    def post(pts, nrm):
        out = []
        for q, p, n in zip(post0(pts, nrm), pts, nrm):
            if p.z > L["zc"] and n.z > -0.2:
                ax = abs(p.x) / hw
                # nose bridge a little narrower and straighter between the eyes
                q = q + V(0, 0, 0.018 * hw * math.exp(-(ax / 0.10) ** 2) * math.exp(-((p.y - (L["eye"] + 0.02 * H)) / (0.08 * H)) ** 2))
            out.append(q)
        return out
    C.add("face", cg, decal=True, jaw=True, post=post, cull=cull, smooth=(lambda p: p.z > L["zc"] and p.y > L["chin"] - 0.01, 1))
    ey0, ey1, ew, et = ears_spec(C)
    for sx in (-1, 1):
        C.add("ear" + ("L" if sx > 0 else "R"), ear_cage(C.head, L, sx, ey0, ey1, ew, et, C.w(["head"]), NA=10))


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
    lens = [1.00, 1.07, 1.00, 0.81]
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



# =============================================================================================== hair: sculpted locks
def skull(C, az, el, off=0.0):
    """Point `off` above the skull in the direction (azimuth az, 0 = front, + toward +X; elevation el) seen from the
    head centre C.Hc, and the outward direction there. Angles in radians."""
    L = C.L; Hc = C.Hc
    u = (az / (2 * math.pi)) % 1.0
    lo, hi = L["chin"] + 0.02 * C.H, L["top"] - 1e-4

    def elev(y):
        p = C.head.at(u, y)
        return math.atan2(p.y - Hc.y, math.hypot(p.x - Hc.x, p.z - Hc.z))
    e_hi = elev(hi)
    if el >= e_hi:
        t = min(1.0, (el - e_hi) / max(1e-6, math.pi / 2 - e_hi))
        p = C.head.at(u, hi).lerp(V(0, L["top"], L["zc"]), t)
    else:
        for _ in range(26):
            mid = (lo + hi) / 2
            if elev(mid) < el: lo = mid
            else: hi = mid
        p = C.head.at(u, (lo + hi) / 2)
    n = (p - Hc).normalized()
    return p + n * off, n


def sag(C, x, psi, off):
    """Skull point on the sagittal slice at lateral position x, psi = angle from straight ahead over the top
    (0 front, 90 up, 180 back) in degrees."""
    a = math.radians(psi)
    d = V(x / 0.033, math.sin(a), math.cos(a))
    az = math.atan2(d.x, d.z); el = math.asin(max(-1.0, min(1.0, d.y / d.length)))
    return skull(C, az, el, off)


def lock(cg, ctrl, w0, th, wfn, NS=14, N=8, reg="hair", pc=0, tip=0.12, root=0.55, flat=0.38, h0=0.65, hend=0.72):
    """One sculpted lock of hair: a flattened, tapering tube along ctrl = [(point, outward normal)], w0 = half width,
    th = height above its base line. The underside is flatter so the lock lies on the head."""
    P = [c[0] for c in ctrl]; Nn = [c[1] for c in ctrl]
    rings = []
    for i in range(NS + 1):
        t = i / NS
        p = cr_open(P, t); n = cr_open(Nn, t).normalized()
        T = (cr_open(P, min(1.0, t + 0.02)) - cr_open(P, max(0.0, t - 0.02))).normalized()
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
    cg.fan(list(reversed(rings[0])), P[0] - (P[1] - P[0]).normalized() * w0 * 0.3, wfn, reg, pc)
    cg.fan(rings[-1], P[-1] + (P[-1] - P[-2]).normalized() * w0 * (0.25 + 0.6 * tip), wfn, reg, pc)


def build_hair(C):
    """Thick, wavy hair swept back to the shoulders: a cap over the skull, then big sculpted locks with a consistent
    height over the skull (a clean silhouette from every side): seven top locks combed straight back from the
    hairline (a soft lift at the front) and fanning out over the crown down to the upper back, three side locks per
    side swept back from the temple over the top of the ear and down behind it onto the collar, three back locks under
    them to the nape. The ends flick out in waves. Everything below the nape follows `hair1` / `hair2`."""
    L = C.L; H = C.H; S = C.S; s = C.s
    rim, cull = hairline(C)

    def thick(u, y):
        return lerp(0.0040, 0.0074, smoothstep(L["brow"], L["top"] - 0.1 * H, y))
    hair_shell(C, rim, thick, "hair", "hair", plumb=None, tuck_front=0.13, grooves=0, groove_amp=0.0, NU=28, NV=8,
               top_extra=0.0030)
    zb = C.head.at(0.5, L["chin"] + 0.25 * H).z
    C.B["hair1"] = (V(0, 0.536, zb - 0.004), V(0, 0.520, -0.043), "head")
    C.B["hair2"] = (V(0, 0.520, -0.043), V(0, 0.505, -0.051), "hair1")

    def wfn(p):
        b = smoothstep(0.006, -0.014, p.z)
        t = smoothstep(0.538, 0.522, p.y) * b
        if t <= 0:
            return {"head": 1.0}
        t2 = smoothstep(0.521, 0.505, p.y)
        return {"head": 1 - t, "hair1": t * (1 - t2), "hair2": t * t2}
    cg = Cage()
    R = math.radians

    def free(x, y, z, n=None):
        n = n or V(x, 0, z - C.Hc.z)
        return (V(x, y, z), n.normalized() if n.length > 1e-6 else V(0, 0, -1))
    # --- top locks: hairline -> over the crown -> down the back onto the upper back, fanning out
    tops = [(-0.0235, -0.0330, 0.0124, 1), (-0.0155, -0.0215, 0.0132, -1), (-0.0075, -0.0100, 0.0136, 1),
            (0.0005, 0.0010, 0.0136, -1), (0.0085, 0.0120, 0.0136, 1), (0.0165, 0.0230, 0.0132, -1),
            (0.0245, 0.0340, 0.0124, 1)]
    prof = ((28, 0.0030), (40, 0.0108), (55, 0.0136), (76, 0.0132), (104, 0.0124), (134, 0.0118), (164, 0.0114),
            (192, 0.0112))
    for k, (x0, x1, w0, wv) in enumerate(tops):
        ctrl = []
        for psi, off in prof:
            t = smoothstep(28, 192, psi)
            ctrl.append(sag(C, lerp(x0, x1, t), psi, off + 0.0010 * math.sin(R(psi) * 3 + k)))
        p, n = ctrl[-1]
        xe = x1 * 1.06
        ctrl.append(free(xe + 0.0020 * wv, 0.5360, min(p.z - 0.0080, -0.0500), V(xe, 0.1, -1)))
        ctrl.append(free(xe * 1.10 - 0.0024 * wv, 0.5120, -0.0590, V(xe, 0.2, -1)))
        ctrl.append(free(xe * 1.24 + 0.0024 * wv, 0.4900 + 0.0060 * ((k * 2) % 3 - 1), -0.0650, V(xe * 2, 0.9, -1)))
        lock(cg, ctrl, w0 * 1.08, 0.0092, wfn, NS=18, N=10, tip=0.50, root=0.40, h0=0.30, hend=0.45)
    # --- side locks: temple -> swept back over the top of the ear -> down behind it onto the collar
    sides = (([(40, 41, 0.0040), (62, 47, 0.0105), (92, 43, 0.0120), (124, 33, 0.0120), (150, 16, 0.0114),
               (164, -10, 0.0110)], 0.0122),
             ([(44, 29, 0.0040), (66, 31, 0.0102), (94, 25, 0.0118), (124, 14, 0.0118), (146, -4, 0.0112),
               (156, -26, 0.0108)], 0.0124),
             ([(52, 17, 0.0036), (72, 16, 0.0094), (98, 9, 0.0110), (122, -3, 0.0112), (138, -20, 0.0110),
               (146, -36, 0.0104)], 0.0118))
    for sx in (-1, 1):
        for k, (path, w0) in enumerate(sides):
            ctrl = [skull(C, R(sx * az), R(el), off) for az, el, off in path]
            p, n = ctrl[-1]
            wv = 1 if k % 2 else -1
            ctrl += [free(p.x * 1.04 + sx * 0.0018 * wv, p.y - 0.0140, p.z - 0.0080),
                     free(p.x * 1.10 - sx * 0.0020 * wv, 0.5040, p.z - 0.0130),
                     free(p.x * 1.32 + sx * 0.0012, 0.4960 - 0.0035 * k, p.z - 0.0120, V(p.x * 3, 0.8, -0.6))]
            lock(cg, ctrl, w0 * 1.05, 0.0088, wfn, NS=18, N=10, tip=0.50, root=0.40, h0=0.30, hend=0.45)
    # --- back locks under the top fan: occiput -> nape -> upper back
    for k, az in enumerate((158, 180, 202)):
        ctrl = [skull(C, R(az), R(el), off) for el, off in ((22, 0.0080), (-2, 0.0096), (-24, 0.0100))]
        xs = math.sin(R(az)) * 0.032
        ctrl += [free(xs, 0.5240, -0.0520, V(xs, 0, -1)), free(xs * 1.15, 0.5040, -0.0580, V(xs, 0.2, -1)),
                 free(xs * 1.30, 0.4880, -0.0610, V(xs, 0.8, -1))]
        lock(cg, ctrl, 0.0150, 0.0082, wfn, NS=14, N=10, tip=0.50, root=0.40, h0=0.3, hend=0.45)
    C.add("locks", cg, subdiv=0)
    return cull


# =============================================================================================== body
TORSO = [  # (y, half width, z front, z back), top -> bottom; the cuirass is moulded onto this
    (0.5150, 0.0200, 0.0180, -0.0220), (0.5090, 0.0340, 0.0250, -0.0320), (0.5010, 0.0590, 0.0330, -0.0390),
    (0.4920, 0.0850, 0.0430, -0.0445), (0.4800, 0.0895, 0.0505, -0.0465), (0.4650, 0.0850, 0.0530, -0.0460),
    (0.4450, 0.0730, 0.0465, -0.0435), (0.4200, 0.0590, 0.0390, -0.0385), (0.3950, 0.0505, 0.0350, -0.0350),
    (0.3750, 0.0525, 0.0360, -0.0370), (0.3450, 0.0605, 0.0395, -0.0445), (0.3200, 0.0630, 0.0400, -0.0470),
    (0.3020, 0.0560, 0.0340, -0.0400)]
TORSO_E = 2.4
TY_K = 0.921                      # the chest is this much shorter than first drawn (lower shoulders, longer neck)


def TY(y):
    """Design height of a torso feature first placed at y (above the waist the chest is compressed by TY_K)."""
    return 0.395 + (y - 0.395) * TY_K if y > 0.395 else y


def TYi(y):
    return 0.395 + (y - 0.395) / TY_K if y > 0.395 else y


TORSO = [(TY(r[0]),) + tuple(r[1:]) for r in TORSO]
# leg: (y, x centre, out, in, front, back, z centre) for the left leg, hip -> sole
LEG = [
    (0.3250, 0.0360, 0.0345, 0.0300, 0.0420, 0.0440, 0.0000), (0.2900, 0.0368, 0.0350, 0.0305, 0.0440, 0.0415, 0.0012),
    (0.2500, 0.0378, 0.0330, 0.0285, 0.0420, 0.0370, 0.0022), (0.2100, 0.0386, 0.0295, 0.0268, 0.0365, 0.0315, 0.0024),
    (0.1820, 0.0389, 0.0258, 0.0250, 0.0318, 0.0272, 0.0030), (0.1650, 0.0389, 0.0240, 0.0222, 0.0292, 0.0260, 0.0026),
    (0.1480, 0.0390, 0.0236, 0.0214, 0.0262, 0.0285, 0.0004), (0.1250, 0.0392, 0.0272, 0.0236, 0.0242, 0.0355, -0.0024),
    (0.0950, 0.0393, 0.0236, 0.0204, 0.0214, 0.0300, -0.0034), (0.0650, 0.0393, 0.0172, 0.0150, 0.0182, 0.0206, -0.0030),
    (0.0450, 0.0392, 0.0146, 0.0134, 0.0170, 0.0174, -0.0022), (0.0350, 0.0390, 0.0146, 0.0136, 0.0180, 0.0176, -0.0016),
    (0.0260, 0.0389, 0.0150, 0.0140, 0.0270, 0.0186, 0.0010), (0.0170, 0.0389, 0.0164, 0.0154, 0.0390, 0.0204, 0.0050),
    (0.0095, 0.0389, 0.0178, 0.0168, 0.0450, 0.0216, 0.0090), (0.0045, 0.0389, 0.0184, 0.0174, 0.0472, 0.0220, 0.0115),
    (0.0006, 0.0389, 0.0178, 0.0168, 0.0460, 0.0212, 0.0125)]
FOOT_TOP = 0.0300
FOOTPRINT = [(-0.022, 0.76), (-0.008, 0.84), (0.010, 0.96), (0.030, 1.06), (0.042, 1.08), (0.052, 0.98), (0.060, 0.80)]
SKIRT = [(0.3700, 0.0570, 0.0400, -0.0410), (0.3400, 0.0680, 0.0455, -0.0495), (0.3050, 0.0760, 0.0505, -0.0555),
         (0.2700, 0.0800, 0.0530, -0.0580)]


def torso_pt(y, a, off=0.0):
    """Point on the torso target surface at height y, angle a (0 = front, + toward +X), pushed out by off."""
    return shell_point(TORSO, y, a, off, TORSO_E)


def tent(a, w):
    """1 at angle 0, falling linearly to 0 at +-w (angles wrapped to +-pi)."""
    a = (a + math.pi) % (2 * math.pi) - math.pi
    return max(0.0, 1.0 - abs(a) / w)


def gauss(x, s):
    return math.exp(-(x / s) ** 2)


def closed_shell(cg, pt, taus, N, th, wfn, reg, pc=0, taus_in=None):
    """Armour sleeve with thickness: outer rings pt(tau, a, 0) for tau in taus, then inner rings pt(tau, a, -th)
    back to the start, bridged into a closed ring-torus (both rims get a real edge)."""
    angs = [2 * math.pi * j / N for j in range(N)]
    rings = [cg.ring([pt(t, a, 0.0) for a in angs], wfn) for t in taus]
    rings += [cg.ring([pt(t, a, -th) for a in angs], wfn) for t in reversed(taus_in or taus)]
    for a, b in zip(rings, rings[1:] + rings[:1]):
        cg.bridge(a, b, reg, pc)
    return rings


def band(cg, pt, taus, N, wfn, reg, pc=0, tuck=0.006):
    """Band wrapped round the body: rings pt(tau, a, 0); the first and last ring are tucked inward."""
    angs = [2 * math.pi * j / N for j in range(N)]
    rings = [cg.ring([pt(taus[0], a, -tuck) for a in angs], wfn)]
    rings += [cg.ring([pt(t, a, 0.0) for a in angs], wfn) for t in taus]
    rings.append(cg.ring([pt(taus[-1], a, -tuck) for a in angs], wfn))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    return rings


def plate(cg, P, us, vs, th, wfn, reg, pc=0):
    """Armour plate with thickness: outer grid P(u, v, 0), inner grid P(u, v, -th), joined all round the border."""
    nu, nv = len(us), len(vs)
    out = [[cg.add(P(u, v, 0.0), wfn) for u in us] for v in vs]
    inn = [[cg.add(P(u, v, -th), wfn) for u in us] for v in vs]
    for j in range(nv - 1):
        for i in range(nu - 1):
            cg.face((out[j][i], out[j][i + 1], out[j + 1][i + 1], out[j + 1][i]), reg, pc)
            cg.face((inn[j][i], inn[j + 1][i], inn[j + 1][i + 1], inn[j][i + 1]), reg, pc)
    per = [(0, i) for i in range(nu)] + [(j, nu - 1) for j in range(1, nv)] \
        + [(nv - 1, i) for i in range(nu - 2, -1, -1)] + [(j, 0) for j in range(nv - 2, 0, -1)]
    for a, b in zip(per, per[1:] + per[:1]):
        cg.face((out[a[0]][a[1]], inn[a[0]][a[1]], inn[b[0]][b[1]], out[b[0]][b[1]]), reg, pc)
    return out


def dome(cg, c, n, prof, N, wfn, reg, pc=0):
    """Boss / stud: rings of radius r at height h above c along n for (h, r) in prof, closed with a pole."""
    X = perp(V(0, 1, 0) if abs(n.y) < 0.9 else V(1, 0, 0), n); Y = n.cross(X)
    rings = [cg.ring([c + n * h + X * (math.cos(2 * math.pi * j / N) * r) + Y * (math.sin(2 * math.pi * j / N) * r)
                      for j in range(N)], wfn) for h, r in prof]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, reg, pc)
    cg.fan(rings[-1], c + n * (prof[-1][0] + 0.35 * prof[-1][1]), wfn, reg, pc)
    return rings


def cuirass_h(x, y, nz):
    """Height of the moulded relief on the torso surface: pectorals with a clear lower edge, sternum, a centre seam,
    the rib arch, three pairs of abdominals, the flank line; on the back the spine channel, the shoulder blades and
    the lower back; below the waist the seat."""
    ax = abs(x); h = 0.0
    y = TYi(y)
    if y > 0.372:
        if nz > 0.0:
            f = smoothstep(0.0, 0.35, nz)
            dy = y - 0.4640
            pec = gauss(ax - 0.0370, 0.0310) * (gauss(dy, 0.0230) if dy > 0 else gauss(dy, 0.0165))
            h += 0.0094 * pec * f
            h -= 0.0030 * gauss(y - 0.4395, 0.0060) * smoothstep(0.074, 0.048, ax) * smoothstep(0.004, 0.016, ax) * f
            h -= 0.0042 * gauss(x, 0.0075) * smoothstep(0.436, 0.452, y) * smoothstep(0.502, 0.488, y) * f
            h -= 0.0016 * gauss(x, 0.0034) * smoothstep(0.380, 0.392, y) * smoothstep(0.500, 0.490, y) * f
            arch = 0.4370 - 0.62 * ax
            h -= 0.0026 * gauss(y - arch, 0.0048) * smoothstep(0.004, 0.012, ax) * smoothstep(0.058, 0.044, ax) * f
            for yc in (0.4245, 0.4060, 0.3880):
                h += 0.0038 * gauss(ax - 0.0152, 0.0108) * gauss(y - yc, 0.0074) * f
            h -= 0.0016 * gauss(ax - 0.0335, 0.0050) * smoothstep(0.380, 0.395, y) * smoothstep(0.436, 0.420, y) * f
        else:
            f = smoothstep(0.0, 0.35, -nz)
            h -= 0.0040 * gauss(x, 0.0085) * smoothstep(0.380, 0.400, y) * smoothstep(0.505, 0.490, y) * f
            h += 0.0035 * gauss(ax - 0.0380, 0.0220) * gauss(y - 0.4650, 0.0260) * f
            h += 0.0020 * gauss(ax - 0.0220, 0.0140) * gauss(y - 0.4100, 0.0220) * f
    elif nz < 0.0:
        h += 0.0030 * gauss(ax - 0.0300, 0.0230) * gauss(y - 0.3350, 0.0220)
    return h


def build_torso(C):
    s = C.s; S = C.S
    N = 36; k = kcomp(N)
    us = front_dense(N, 0.30)
    rows = densify(TORSO, 2)
    wt = C.w(["hips", "spine", "chest", ("neck", 0.008 * S), ("shoulderL", 0.012 * S), ("shoulderR", 0.012 * S)])
    cg = Cage(); rings = []
    for y, hw, zf, zb in rows:
        zc = (zf + zb) / 2; rd = (zf - zb) / 2
        rings.append(cg.ring([V(se(math.sin(2 * math.pi * u), TORSO_E) * hw * k, y, zc + se(math.cos(2 * math.pi * u), TORSO_E) * rd * k)
                              for u in us], wt))

    def regfn(q):
        return "cuirass" if sum(cg.v[i].y for i in q) / 4 > 0.372 else "leggings"
    cg.fan(rings[0], V(0, rows[0][0] + 0.003, -0.002), wt, "cuirass")
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, None, 0, regfn=regfn)
    cg.fan(rings[-1], V(0, rows[-1][0] - 0.006, -0.003), wt, "leggings")

    def post(pts, nrm):
        return [p + n * cuirass_h(p.x, p.y, n.z) for p, n in zip(pts, nrm)]
    C.add("torso", cg, post=post, subdiv=1)


def build_arm(C, side):
    """Upper arm and elbow in the ivory sleeve (the sleeve runs on under the vambrace)."""
    A = C.arm[side]; S0, d = A["S0"], A["d"]
    prof = [(-0.020, 0.0198, 0.0198), (-0.004, 0.0248, 0.0256), (0.018, 0.0266, 0.0270), (0.046, 0.0254, 0.0262),
            (0.076, 0.0226, 0.0222), (0.100, 0.0192, 0.0184), (0.118, 0.0180, 0.0172), (0.134, 0.0190, 0.0180),
            (0.152, 0.0182, 0.0170), (0.166, 0.0162, 0.0150)]
    cg = Cage()
    wa = C.w(["shoulder" + side, "upperArm" + side, "forearm" + side])
    tube(cg, [S0 + d * sv for sv, _, _ in prof], [(rz, rp) for _, rp, rz in prof], 12, wa, "sleeves", 0, ref=V(0, 0, 1),
         cap0=True, cap1=True)

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            sv = (p - S0).dot(d)
            h = 0.0007 * math.sin((sv - 0.086) / 0.0062 * math.pi) * smoothstep(0.080, 0.092, sv) * smoothstep(0.128, 0.116, sv)
            out.append(p + n * h)
        return out
    C.add("arm" + side, cg, post=post, subdiv=1)


EMBOSS = 0.0015                       # height of the embossed line that runs round vambraces and greaves inside the rims
EMBOSS_TAUS = [0.0, 0.03, 0.07, 0.105, 0.15, 0.195, 0.26, 0.50, 0.74, 0.805, 0.85, 0.895, 0.93, 0.97, 1.0]


def emboss(tau):
    """Raised line with a little groove either side, running round a shell parallel to both rims."""
    return EMBOSS * sum(gauss(tau - c, 0.022) - 0.45 * (gauss(tau - c + 0.045, 0.02) + gauss(tau - c - 0.045, 0.02))
                        for c in (0.15, 0.85))


def build_vambrace(C, side):
    """Gold vambrace from the wrist to below the elbow: pointed toward the elbow on the outside, a point over the back
    of the hand, a raised keel and rolled rims."""
    A = C.arm[side]; E, d = A["E"], A["d"]
    X0 = perp(A["Xh"], d); Y0 = d.cross(X0)
    rad = [(0.000, 0.0228), (0.030, 0.0214), (0.060, 0.0188), (0.090, 0.0158), (0.120, 0.0144)]

    def pt(tau, a, off):
        t0 = 0.0230 - 0.0210 * tent(a, 0.95) - 0.0070 * (tent(a - 2.1, 0.7) + tent(a + 2.1, 0.7))
        t1 = 0.0945 + 0.0200 * tent(a, 0.85)
        sv = lerp(t0, t1, tau)
        r = table(rad, sv)[0] + off + 0.0016 * (gauss(tau, 0.07) + gauss(1 - tau, 0.07)) + 0.0018 * tent(a, 0.42)
        r += emboss(tau) * (1.0 if off >= 0 else 0.0)
        return E + d * sv + X0 * (math.cos(a) * r) + Y0 * (math.sin(a) * r * 0.94)
    cg = Cage()
    closed_shell(cg, pt, EMBOSS_TAUS, 12, 0.0036, lambda p: {"forearm" + side: 1.0}, "vambraces",
                 taus_in=[0.0, 0.5, 1.0])
    C.add("vambrace" + side, cg, subdiv=1)


def leg_rows():
    return densify(LEG, 2)


def leg_pt(sd, y, a, off=0.0):
    """Point on the leg target surface at height y, angle a (0 = front, + toward the outside of that leg)."""
    xc, out, inn, fr, bk, zc = table(LEG, y)
    sa, ca = math.sin(a), math.cos(a)
    px = se(sa, 2.2) * ((out if sa >= 0 else inn) + off); pz = se(ca, 2.2) * ((fr if ca >= 0 else bk) + off)
    return V(sd * (xc + px), y, zc + pz)


def build_leg(C, side):
    sd = 1 if side == "L" else -1
    N = 14; us = front_dense(N, 0.40)
    angs = [math.pi / 2 - 2 * math.pi * u for u in us]
    X, Y = V(1, 0, 0), V(0, 0, 1)
    cg = Cage(); wleg = C.w(["hips", "thigh" + side, "shin" + side, "foot" + side, "toe" + side])
    ank = C.B["foot" + side][0]
    toe_out = math.radians(7.0) * sd
    rings = []; rows = leg_rows()
    for y, xc, out, inn, fr, bk, zc in rows:
        c = V(xc * sd, y, zc)
        ext = (out, inn, fr, bk) if sd > 0 else (inn, out, fr, bk)
        e = 2.2 if y > FOOT_TOP else 2.6
        pts = []
        for a in angs:
            p = section(c, X, Y, ext, a, e)
            if y < FOOT_TOP:
                tt = smoothstep(FOOT_TOP, FOOT_TOP * 0.5, y)
                q = rot_about(p - V(ank.x, 0, ank.z), V(0, 1, 0), toe_out * tt)
                p = q + V(ank.x, 0, ank.z)
                wprof = table(FOOTPRINT, p.z - ank.z)[0]
                p.x = ank.x + (p.x - ank.x) * lerp(1.0, wprof, tt)
            pts.append(p)
        rings.append(cg.ring(pts, wleg))
    top = rows[0]
    cg.fan(rings[0], V(top[1] * sd, top[0] + 0.006, top[6]), wleg, "leggings", 0)

    def regfn(q):
        return ("greaves", 1) if sum(cg.v[i].y for i in q) / 4 < 0.0400 else ("leggings", 0)
    for a, b in zip(rings, rings[1:]):
        n = len(a)
        for j in range(n):
            q = (a[j], a[(j + 1) % n], b[(j + 1) % n], b[j])
            rg, pc = regfn(q); cg.face(q, rg, pc)
    cg.grid_cap(rings[-1], wleg, "greaves", 1)

    def post(pts, nrm):
        out = []
        for p, n in zip(pts, nrm):
            q = p.copy()
            if q.y < 0.0012:
                q.y = 0.0004 if q.y < 0.0007 else q.y
            elif 0.0015 < q.y < 0.0062:                  # a sole welt round the boot
                q += V(n.x, 0, n.z) * 0.0011
            out.append(q)
        return out
    C.add("leg" + side, cg, post=post, subdiv=1, cull=lambda p: 0.056 < p.y < 0.136)   # hidden inside the greave


def build_greave(C, side):
    """Gold greave from the ankle to the knee with a pointed knee cop, a front keel and rolled rims."""
    sd = 1 if side == "L" else -1

    def pt(tau, a, off):
        ad = abs((a + math.pi) % (2 * math.pi) - math.pi)
        ytop = 0.1660 + 0.0560 * max(0.0, 1.0 - ad / 1.00) ** 1.25 - 0.0200 * smoothstep(1.5, 3.0, ad)
        ybot = 0.0420 - 0.0100 * tent(a, 0.8)
        y = lerp(ytop, ybot, tau)
        o = 0.0040 + off + 0.0015 * (gauss(tau, 0.06) + gauss(1 - tau, 0.06))
        o += 0.0022 * tent(a, 0.34) * (1 - 0.4 * tau)
        o += 0.0045 * gauss(y - 0.1800, 0.0240) * tent(a, 1.1)
        o += emboss(tau) * (1.0 if off >= 0 else 0.0)
        return leg_pt(sd, y, a, o)
    cg = Cage()
    closed_shell(cg, pt, EMBOSS_TAUS, 14, 0.0038, lambda p: {"shin" + side: 1.0}, "greaves",
                 taus_in=[0.0, 0.5, 1.0])
    C.add("greave" + side, cg, subdiv=1)


def skirt_pt(y, a, off=0.0):
    return shell_point(SKIRT, y, a, off, 2.3)


def build_skirt(C):
    """Short ivory skirt: seven overlapping tongue-shaped panels hanging from under the sash round the hips."""
    wb = C.w(["hips", "spine"])

    def wsk(p):
        t = smoothstep(0.345, 0.270, p.y) * 0.62 * smoothstep(0.004, 0.022, abs(p.x))
        if t <= 0:
            return wb(p)
        return mixw((wb(p), 1 - t), ({"thigh" + ("L" if p.x > 0 else "R"): 1.0}, t))
    cg = Cage()
    panels = [(math.radians(a), math.radians(w), yb, lay) for a, w, yb, lay in (
        (43, 23, 0.286, 1), (-43, 23, 0.286, 1), (84, 25, 0.291, 0), (-84, 25, 0.291, 0),
        (130, 27, 0.288, 1), (-130, 27, 0.288, 1), (180, 27, 0.284, 0))]
    us = [-1.0, -0.84, 0.0, 0.84, 1.0]; vs = [0.0, 0.14, 0.50, 0.80, 0.95, 1.0]
    for k, (ac, w0, yb, lay) in enumerate(panels):
        def P(u, v, off, ac=ac, w0=w0, yb=yb, lay=lay):
            y = lerp(0.3640, yb + 0.007 * u * u, v)
            wv = w0 * (1.0 + 0.10 * v) * (1.0 - 0.34 * smoothstep(0.55, 1.0, v) ** 2)
            o = (0.0008 + 0.0030 * lay) * smoothstep(0.0, 0.25, v) + 0.0012 + off + 0.0050 * v * v + 0.0012 * (1 - abs(u)) * math.sin(math.pi * v)
            return skirt_pt(y, ac + u * wv, o)
        plate(cg, P, us, vs, 0.0030, wsk, "skirt", k % 2)
    C.add("skirt", cg, subdiv=1)


def build_sash(C):
    """Burnt-orange sash wound twice round the waist, a narrow gold belt with a round buckle over it, and the long end
    of the sash hanging in front to the knees (`sash1` / `sash2`)."""
    wb = C.w(["hips", "spine"])
    cg = Cage()

    def pt(tau, a, off):
        y = lerp(0.4060, 0.3500, tau)
        o = 0.0072 + off + 0.0022 * math.sin(math.pi * tau) + 0.0009 * math.cos(2 * math.pi * 2.5 * tau + 1.5 * a)
        return torso_pt(y, a, o)
    band(cg, pt, [0.0, 0.14, 0.38, 0.62, 0.86, 1.0], 32, wb, "sash", tuck=0.009)
    C.add("sash", cg, subdiv=1)
    cg = Cage()

    def pb(tau, a, off):
        y = lerp(0.3920, 0.3660, tau)
        o = 0.0118 + off - 0.0016 * (gauss(tau, 0.05) + gauss(1 - tau, 0.05)) + 0.0006 * gauss(tau - 0.5, 0.2)
        return torso_pt(y, a, o)
    band(cg, pb, [0.0, 0.12, 0.50, 0.88, 1.0], 28, wb, "belt", tuck=0.005)
    c = torso_pt(0.3790, 0.0, 0.0118)
    lathe_z(cg, c, [(0.0, 0.0200), (0.0030, 0.0200), (0.0052, 0.0168), (0.0050, 0.0132), (0.0034, 0.0118),
                    (0.0058, 0.0088), (0.0072, 0.0)], 14, wb, lambda p0, p1: "belt", 1)
    C.add("belt", cg, subdiv=1)
    # hanging front panel
    C.B["sash1"] = (V(0, 0.362, 0.0490), V(0, 0.272, 0.0575), "hips")
    C.B["sash2"] = (V(0, 0.272, 0.0575), V(0, 0.184, 0.0590), "sash1")
    zt = [(0.3740, 0.0470), (0.3500, 0.0530), (0.3200, 0.0565), (0.2700, 0.0585), (0.1800, 0.0600)]

    def wtab(p):
        t1 = smoothstep(0.372, 0.338, p.y); t2 = smoothstep(0.292, 0.248, p.y)
        return mixw((wb(p), 1 - t1), ({"sash1": 1.0}, t1 * (1 - t2)), ({"sash2": 1.0}, t1 * t2))

    def P(u, v, off):
        hw = lerp(0.0290, 0.0365, v) * (1.0 - 0.06 * math.sin(math.pi * v))
        y = lerp(0.3740, 0.1800 + 0.0240 * abs(u), v)
        z = table(zt, y)[0] + off - 0.0045 * u * u + 0.0016 * math.cos(u * math.pi * 1.5) * smoothstep(0.1, 0.5, v)
        return V(u * hw, y, z)
    cg = Cage()
    plate(cg, P, [-1.0, -0.94, -0.60, -0.25, 0.0, 0.25, 0.60, 0.94, 1.0],
          [0.0, 0.07, 0.18, 0.31, 0.44, 0.57, 0.70, 0.82, 0.92, 0.975, 1.0], 0.0030, wtab, "sash", 1)
    C.add("tabard", cg, subdiv=1)


def build_gorget(C):
    """Gold V gorget: a collar standing round the base of the neck, lying on the shoulders and the upper chest, with
    a pointed front tab and a centre ridge. It follows the moulded chest, has a beaded rim and a real edge."""
    S = C.S
    wcol = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S)])
    yout = [(0.00, 0.4650), (0.030, 0.4755), (0.075, 0.4885), (0.14, 0.4965), (0.25, 0.5005), (0.36, 0.4965),
            (0.45, 0.4905), (0.50, 0.4875)]
    ytop = TY(0.5078)
    NU = 36; cg = Cage(); rings = []
    for v, do in ((0.0, -0.0050), (0.0, 0.0), (0.07, 0.0), (0.22, 0.0), (0.45, 0.0), (0.70, 0.0), (0.90, 0.0), (1.0, 0.0),
                  (0.96, -0.0034)):
        ring = []
        for i in range(NU):
            u = i / NU; uu = mirror_u(u); a = 2 * math.pi * u
            y = lerp(ytop, TY(table(yout, uu)[0]), v)
            p = torso_pt(y, a, 0.0); n = (torso_pt(y, a, 1e-3) - p).normalized()
            o = 0.0040 + do + 0.0018 * gauss(v, 0.09) + 0.0014 * gauss(1 - v, 0.08) + 0.0008 * math.sin(math.pi * v)
            o += cuirass_h(p.x, y, n.z) * (0.0 if do else 1.0)
            if n.z > 0:
                o += 0.0024 * gauss(p.x, 0.0060) * smoothstep(0.10, 0.60, v)
            p = p + n * o
            if v < 0.15:                                  # the standing collar: up and a little out
                p.y += (0.0050 if do == 0 else 0.0010) * (1 - v / 0.15)
            ring.append(p)
        rings.append(cg.ring(ring, wcol))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "collar", 0)
    C.add("gorget", cg, subdiv=1)


def build_pauldrons(C, side):
    """Layered gold pauldron per shoulder: the big top plate with a round boss lies on a second, slightly larger plate
    whose rim shows all round it (a stepped double edge); under them two lames step down the upper arm. Every plate
    is a curved shell with real thickness, a rolled bead along its rim and a bevelled edge."""
    sd = 1 if side == "L" else -1
    us9 = [-1.0, -0.95, -0.86, -0.48, 0.0, 0.48, 0.86, 0.95, 1.0]
    us7 = [-1.0, -0.92, -0.50, 0.0, 0.50, 0.92, 1.0]

    def shell(a0, a1, n0, n1, r0, r1, phim, bulge, lift=0.0, grow=1.0, bead=0.0020):
        def P(a, b, off):
            m = max(abs(a), abs(b))
            a *= grow; b *= grow
            u = a * math.sqrt(max(0.0, 1 - 0.42 * b * b)); v = (b * math.sqrt(max(0.0, 1 - 0.42 * a * a)) + 1) / 2
            c = a0.lerp(a1, v) + V(0, bulge * math.sin(math.pi * v), 0)
            n = n0.lerp(n1, v).normalized()
            r = lerp(r0, r1, v) + off + 0.0050 * smoothstep(0.55, 1.0, v) ** 2 + lift
            if off >= 0:                                        # bead along the rim, rolled down at the very edge
                r += bead * gauss(m - 0.90, 0.055) - 0.0010 * smoothstep(0.95, 1.0, m)
            phi = u * phim
            p = c + n * (math.cos(phi) * r) + V(0, 0, 1) * (math.sin(phi) * r * 1.04)
            return V(sd * p.x, p.y, p.z)
        return P
    cg = Cage()
    wtop = lambda p: {"shoulder" + side: 0.62, "upperArm" + side: 0.38}
    wlow = lambda p: {"upperArm" + side: 0.78, "shoulder" + side: 0.22}
    warm = lambda p: {"upperArm" + side: 1.0}
    Plow2 = shell(V(0.1250, 0.4200, 0.0), V(0.1510, 0.3850, 0.0), V(0.84, 0.54, 0), V(0.90, 0.44, 0), 0.0300, 0.0286,
                  math.radians(92), 0.0012, bead=0.0014)
    plate(cg, Plow2, us7, us7, 0.0036, warm, "pauldrons", 3)
    Plow = shell(V(0.1000, 0.4550, 0.0), V(0.1340, 0.4150, 0.0), V(0.80, 0.60, 0), V(0.87, 0.50, 0), 0.0330, 0.0312,
                 math.radians(96), 0.0020, bead=0.0016)
    plate(cg, Plow, us7, us7, 0.0038, wlow, "pauldrons", 1)
    top = (V(0.0590, 0.4705, 0.0), V(0.1220, 0.4530, 0.0), V(-0.12, 0.99, 0), V(0.90, 0.44, 0), 0.0425, 0.0405,
           math.radians(100), 0.0060)
    Punder = shell(*top, lift=-0.0044, grow=1.075, bead=0.0012)        # the second layer: its rim shows round the top
    plate(cg, Punder, [-1.0, -0.90, 0.0, 0.90, 1.0], [-1.0, -0.90, 0.0, 0.90, 1.0], 0.0030, wtop, "pauldrons", 4)
    Ptop = shell(*top)
    plate(cg, Ptop, us9, us9, 0.0044, wtop, "pauldrons", 0)
    # round boss on the front of the top plate
    c = Ptop(0.56, 0.12, 0.0); e = 0.02
    n = (Ptop(0.56 + e, 0.12, 0.0) - Ptop(0.56 - e, 0.12, 0.0)).cross(Ptop(0.56, 0.12 + e, 0.0) - Ptop(0.56, 0.12 - e, 0.0)).normalized()
    if n.dot(c - V(sd * 0.09, 0.46, 0)) < 0:
        n = -n
    dome(cg, c - n * 0.0010, n, [(0.0, 0.0140), (0.0024, 0.0140), (0.0046, 0.0118), (0.0040, 0.0096), (0.0062, 0.0074),
                                (0.0078, 0.0040)], 14, wtop, "pauldrons", 2)
    C.add("pauldron" + side, cg, subdiv=1)


# =============================================================================================== props
def build_sword(C):
    """Sheathed sword at the left hip (rigid on `sword`, a child of `hips`): ivory scabbard with a gold locket and
    chape, gold cross-guard with a round blue gem on both faces, ribbed grip, round pommel."""
    mouth = V(0.0800, 0.3700, 0.0240)
    T = V(0.085, -1.0, -0.30).normalized()
    C.B["sword"] = (mouth.copy(), mouth + T * 0.262, "hips")
    Wd = perp(V(0.80, 0, -0.60), T)
    Nf = T.cross(Wd).normalized()
    if Nf.dot(V(0.6, 0, 0.8)) < 0:
        Nf = -Nf
    cg = Cage()
    at = lambda sv: mouth + T * sv
    ss = [0.004, 0.030, 0.070, 0.115, 0.160, 0.205, 0.240, 0.258]
    tube(cg, [at(sv) for sv in ss], [(lerp(0.0058, 0.0040, sv / 0.262), lerp(0.0118, 0.0068, sv / 0.262)) for sv in ss], 14,
         None, "scabbard", 0, ref=Nf, cap0=True, cap1=True, e=2.3, cap_len=1.4)
    tube(cg, [at(-0.003), at(0.002), at(0.016), at(0.021)], [(0.0066, 0.0128), (0.0074, 0.0138), (0.0074, 0.0136), (0.0064, 0.0124)],
         14, None, "hilt", 1, ref=Nf, e=2.3)
    tube(cg, [at(0.228), at(0.236), at(0.252), at(0.264)], [(0.0052, 0.0088), (0.0056, 0.0092), (0.0046, 0.0070), (0.0028, 0.0038)],
         14, None, "hilt", 2, ref=Nf, e=2.3, cap_len=1.2)
    gc = at(-0.0075)
    xs = [-0.036, -0.030, -0.018, -0.006, 0.006, 0.018, 0.030, 0.036]
    tube(cg, [gc + Wd * x + T * (0.0075 * (x / 0.036) ** 2) for x in xs],
         [(0.0044 + 0.0016 * (abs(x) / 0.036) ** 3, 0.0050 + 0.0020 * (abs(x) / 0.036) ** 3) for x in xs], 12, None, "hilt", 3,
         ref=Nf, e=2.4)
    for sgn in (1, -1):
        dome(cg, gc + Nf * sgn * 0.0030, Nf * sgn, [(0.0, 0.0122), (0.0022, 0.0122), (0.0036, 0.0100)], 12, None, "hilt", 3)
        dome(cg, gc + Nf * sgn * 0.0060, Nf * sgn, [(0.0, 0.0090), (0.0016, 0.0086), (0.0034, 0.0064), (0.0044, 0.0034)], 12,
             None, "gem", 4)
    gs = [-0.012 - 0.0058 * k for k in range(9)]
    tube(cg, [at(sv) for sv in gs], [(0.0052 + 0.0008 * (k % 2), 0.0058 + 0.0008 * (k % 2)) for k in range(9)], 12, None, "hilt",
         5, ref=Nf, cap0=False, cap1=False)
    blob(cg, at(-0.0680), 0.0098, 0.0098, 0.0086, None, "hilt", 5, NU=14, NV=8)
    C.add("sword", cg, rigid="sword", subdiv=0)


TRUMPET_SHIFT = 0.034


def build_trumpet(C):
    """Long golden herald trumpet (rigid on `trumpet`, a child of `handR`; hidden by default). It lies across the palm:
    the mouthpiece comes out on the thumb side, the bell beyond the little finger."""
    A = C.arm["R"]; hd = C.s["handDims"]; LHp = C.s["hand"] * C.s["palmFrac"]
    G = A["W"] + A["dh"] * (0.66 * LHp) + A["Np"] * (hd["palmH"] / 2 + 0.0056)
    ax = (-A["thumb"]).normalized()
    C.B["trumpet"] = (G.copy(), G + ax * 0.10, "handR")
    C.trumpet = dict(G=G, ax=ax, mouth=G - ax * (0.078 + TRUMPET_SHIFT), bell=G + ax * (0.2255 - TRUMPET_SHIFT))
    X = perp(A["Np"], ax); Y = ax.cross(X)
    prof = [(-0.0770, 0.0030), (-0.0782, 0.0056), (-0.0770, 0.0070), (-0.0740, 0.0068), (-0.0700, 0.0040), (-0.0640, 0.0030),
            (-0.0300, 0.0031), (0.0220, 0.0033), (0.0245, 0.0056), (0.0305, 0.0056), (0.0330, 0.0035), (0.0900, 0.0039),
            (0.1120, 0.0041), (0.1145, 0.0062), (0.1205, 0.0062), (0.1230, 0.0044), (0.1500, 0.0054), (0.1750, 0.0074),
            (0.1950, 0.0110), (0.2100, 0.0170), (0.2195, 0.0245), (0.2240, 0.0308), (0.2256, 0.0318), (0.2244, 0.0300),
            (0.2150, 0.0200), (0.2000, 0.0115), (0.1850, 0.0070)]
    prof = [(sv - TRUMPET_SHIFT, r) for sv, r in prof]          # the hand grips it a third of the way along
    cg = Cage(); N = 16
    rings = [cg.ring([G + ax * sv + X * (math.cos(2 * math.pi * j / N) * r) + Y * (math.sin(2 * math.pi * j / N) * r)
                      for j in range(N)], None) for sv, r in prof]
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "trumpet", 0)
    cg.fan(list(reversed(rings[0])), G + ax * (-0.0745 - TRUMPET_SHIFT), None, "trumpet", 0)
    cg.fan(rings[-1], G + ax * (0.1800 - TRUMPET_SHIFT), None, "trumpet", 0)
    C.add("trumpet", cg, rigid="trumpet", subdiv=0)


# =============================================================================================== wings
def feather(cg, root, tip, n, hw, wts, reg, pc, lod=0, roll=0.0, arch=0.02, shaft_pc=None, tipk=0.66, th=1.0, xf=None):
    """One feather as a closed thin shell from root to tip, slightly cambered, a raised shaft along the middle of the
    side facing n. lod 3 = flight feather and 2 = greater covert: 6-point section, soft round tip, the shaft its own
    piece; lod 1 = median / lesser covert: 6-point section with a low ridge, a pointed (lancet) tip that tucks under
    the row in front; lod 0 = the same with fewer stations (back of the wing)."""
    d = tip - root; Lf = d.length; d = d / Lf
    n = perp(n, d); sdv = d.cross(n)
    if roll:
        n, sdv = (n * math.cos(roll) + sdv * math.sin(roll)).normalized(), (sdv * math.cos(roll) - n * math.sin(roll)).normalized()
    wf = lambda p: wts
    xf = xf or (lambda p: p)
    ts = {3: (0.0, 0.10, 0.25, 0.42, 0.58, 0.72, 0.83, 0.91, 0.965, 0.99), 2: (0.0, 0.22, 0.48, 0.72, 0.88, 0.96, 0.99),
          1: (0.0, 0.28, 0.55, 0.76, 0.92), 0: (0.0, 0.40, 0.72, 0.92)}[lod]
    pointed = lod <= 1
    rings = []
    for t in ts:
        c = root + d * (t * Lf) + n * (arch * Lf * 4 * t * (1 - t))
        if pointed:                                   # lancet: widest at 40 %, straight-ish sides to a soft point
            w = hw * (0.55 + 0.45 * smoothstep(0.0, 0.40, t)) * (1 - smoothstep(0.40, 1.0, t) ** 1.35)
            w = max(w, 0.0004)
        else:
            w = hw * min(1.0, 0.40 + 1.5 * t)
            if t > tipk:
                w *= max(0.0, 1 - ((t - tipk) / (1 - tipk)) ** 2) ** 0.5
        cam = 0.13 * w
        if not pointed:
            hr = 0.0030 * th * (1 - 0.55 * t); hv = 0.0010 * th; hb = 0.0010 * th; sw = 0.07 * w + 0.0011
        else:
            hr = 0.0022 * th * (1 - 0.6 * t); hv = 0.0012 * th * (1 - 0.5 * t); hb = 0.0008 * th; sw = 0.45 * w
        ring = [c + sdv * w - n * cam, c + sdv * sw + n * hv, c + n * hr, c - sdv * sw + n * hv, c - sdv * w - n * cam,
                c - n * hb]
        rings.append(cg.ring([xf(p) for p in ring], wf))
    m = len(rings[0])
    for a, b in zip(rings, rings[1:]):
        for j in range(m):
            cg.face((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]), reg,
                    shaft_pc if (not pointed and shaft_pc is not None and j in (1, 2)) else pc)
    tp = cg.add(xf(root + d * Lf), wf)
    for j in range(m):
        cg.face((rings[-1][j], rings[-1][(j + 1) % m], tp), reg, pc)
    cg.face(tuple(reversed(rings[0])), reg, pc)


def wing_weights(side, s, fan=0.0):
    """Weights of a whole feather rooted at wing-arm parameter s (0 shoulder .. 3 hand tip); fan = how far it swings
    with `prim` (0 innermost primary .. 1 outermost). One weight set per feather keeps each feather stiff."""
    b1, b2, b3, bp = f"wing{side}1", f"wing{side}2", f"wing{side}3", f"wing{side}_prim"
    t12 = smoothstep(0.78, 1.22, s); t23 = smoothstep(1.80, 2.15, s)
    w = {b1: 1 - t12, b2: t12 * (1 - t23), b3: t23 * (1 - fan), bp: t23 * fan}
    wc = 0.55 * max(0.0, 1 - s) ** 2
    if wc > 0:
        w = {k: v * (1 - wc) for k, v in w.items()}; w["chest"] = wc
    w = {k: v for k, v in w.items() if v > 0.02}
    t = sum(w.values())
    return {k: v / t for k, v in w.items()}


WING_FEATHERS = {}


def build_wing(C, side):
    """One wing: the feathered arm (leading edge), 30 flight feathers (tertials, secondaries, primaries) and three rows
    of coverts on the front and on the back, every feather its own mesh."""
    sd = 1 if side == "L" else -1
    M = lambda p: V(sd * p.x, p.y, p.z)
    cg = Cage(); count = 0
    clampf = lambda v, a, b: max(a, min(b, v))
    fl = flight_specs()
    tips = [trail_xy(q) for _, _, q, _ in fl]
    for i, (kind, s, q, fan) in enumerate(fl):
        r2 = arm_xy(s); t2 = tips[i]
        sp = min((tips[j] - t2).length for j in (i - 1, i + 1) if 0 <= j < len(tips))
        hw = clampf(0.66 * sp, 0.0130, 0.0250)
        mid = (r2 + t2) / 2
        if kind == "pri":
            wts = {f"wing{side}3": 1 - fan, f"wing{side}_prim": fan}
            wts = {k: v for k, v in wts.items() if v > 0.02}
            tt = sum(wts.values()); wts = {k: v / tt for k, v in wts.items()}
        else:
            wts = wing_weights(side, s)
        feather(cg, W3(r2.x, r2.y, 0.0), W3(t2.x, t2.y, 0.0), wing_n(mid.x, mid.y), hw, wts, "wingFeathers",
                (i % 4) if kind == "pri" else 4 + (i % 4), lod=3, roll=math.radians(-11), arch=0.018, shaft_pc=21,
                tipk=0.66 if kind == "pri" else 0.72, xf=M)
        count += 1

    def row(n, f, layer, front, lod, stagger=0.0, s0=0.04, s1=2.97, hwk=0.66, k0=0, th=1.0):
        nonlocal count
        for i in range(n):
            s = clampf(s0 + (s1 - s0) * (i + 0.5 + stagger) / n, 0.0, 3.0)
            ds = (s1 - s0) / n
            r2 = arm_xy(s); tip2 = r2 + (trail_xy(q_of_s(s)) - r2) * f
            rb = arm_xy(min(3.0, s + ds)); tb = rb + (trail_xy(q_of_s(min(3.0, s + ds))) - rb) * f
            hw = clampf(hwk * max((tb - tip2).length, (rb - r2).length), 0.0070, 0.0230)
            lay = layer if front else -layer
            mid = (r2 + tip2) / 2
            nn = wing_n(mid.x, mid.y) * (1 if front else -1)
            fan = clampf(s - 2.0, 0.0, 1.0)
            feather(cg, W3(r2.x, r2.y, lay * 1.25), W3(tip2.x, tip2.y, lay), nn, hw, wing_weights(side, s, fan), "wingCoverts",
                    8 + 4 * k0 + (i + int(2 * stagger + k0)) % 4 if k0 < 3 else 16 + (i + int(2 * stagger) + k0) % 4,
                    lod=lod, roll=math.radians(-9 if front else 9), arch=0.030, shaft_pc=22 if lod == 2 else None, th=th, xf=M)
            count += 1
    row(22, 0.50, 0.0050, True, 2, k0=0, hwk=0.80)                 # greater coverts
    row(22, 0.33, 0.0084, True, 1, stagger=0.5, k0=1, hwk=0.85)    # median coverts
    row(24, 0.235, 0.0114, True, 1, k0=3, hwk=1.08)                # lesser coverts, three staggered lines of
    row(24, 0.160, 0.0138, True, 1, stagger=0.5, k0=4, hwk=1.12)   # pointed overlapping feathers
    row(20, 0.095, 0.0158, True, 1, k0=5, hwk=1.18)
    row(17, 0.46, 0.0050, False, 0, k0=0, hwk=0.95)                # the back of the wing: three coarser rows
    row(18, 0.28, 0.0084, False, 0, stagger=0.5, k0=1, hwk=1.00)
    row(18, 0.130, 0.0114, False, 0, k0=3, hwk=1.10)
    # the feathered arm = the rounded leading edge of the wing
    ss = [-0.22 + 3.22 * k / 17 for k in range(18)]
    path = [M(W3(arm_xy(s).x, arm_xy(s).y, 0.0035)) if s >= 0 else M(W3(WS[0], WS[1], 0.0035) + V(-0.030 * (-s / 0.22), -0.020 * (-s / 0.22), 0.016 * (-s / 0.22)))
            for s in ss]

    def warm(p):
        k = min(range(len(path)), key=lambda i: (path[i] - p).length_squared)
        return wing_weights(side, max(0.0, ss[k]), max(0.0, min(1.0, ss[k] - 2.0)))
    tube(cg, path, [lerp(0.0190, 0.0090, max(0.0, s) / 3.0) for s in ss], 8, warm, "wingCoverts", 20, ref=V(0, 0, 1),
         cap0=True, cap1=True, cap_len=0.9)
    C.add("wing" + side, cg, subdiv=0)
    WING_FEATHERS[side] = count


# =============================================================================================== the character
def build_gabriel(C):
    skeleton(C)
    rim, cull = hairline(C)
    build_head(C, cull)
    build_hair(C)
    build_torso(C)
    for side in "LR":
        build_arm(C, side)
        build_vambrace(C, side)
        build_forearm_hand(C, side, 0.52 * C.s["forearm"])
        build_leg(C, side)
        build_greave(C, side)
        build_pauldrons(C, side)
    build_gorget(C)
    build_skirt(C)
    build_sash(C)
    build_sword(C)
    build_trumpet(C)
    for side in "LR":
        build_wing(C, side)


BUILDERS = {"gabriel": build_gabriel}


# =============================================================================================== Blender assembly
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
    pointing down) by closedScale closes them over the eyes. At rest each lid is a 1 / closedScale miniature of the
    closed, almond-shaped lid tucked under the brow, so the closed lid has the shape of the eye (not a visor). Every
    lid vertex sits on the most forward face point over its whole travel (rest -> closed), so a closed lid lies on
    the eye surface and never inside the brow or the cheek (the Daniel lion lesson)."""
    me = face_obj.data
    vs = [to_design(face_obj.matrix_world @ v.co) - V(sheet[0], sheet[1], 0) for v in me.vertices]
    bvh = BVHTree.FromPolygons([tuple(v) for v in vs], [tuple(p.vertices) for p in me.polygons])
    ex, ey, ew, eh = C.F["eyeLocal"]
    top = C.lid["top"]; k = C.lid["closedScale"]
    cg = Cage()
    NX = 11
    for sx in (-1, 1):
        cols = []
        for i in range(NX):
            t = (i / (NX - 1) - 0.5) * 2 * 0.975
            x = sx * ex + t * 1.14 * ew
            arc = math.sqrt(max(0.0, 1 - t * t))
            yu = ey + 1.10 * eh * arc ** 0.9; yl = ey - 1.02 * eh * arc ** 0.9
            col = []
            for j in range(4):
                yc = lerp(yu, yl, j / 3)                        # closed position
                yr = top - (top - yc) / k                       # rest position (scaled about the bone head)
                zs = []
                for q in range(9):
                    hit = bvh.ray_cast(V(x, lerp(yr, yc, q / 8), 0.3), V(0, 0, -1), 1.0)
                    if hit[0]:
                        zs.append(hit[0].z)
                col.append(V(x, yr, (max(zs) + 0.0004) if zs else 0.0))
            cols.append(col)
        good = [i for i, c in enumerate(cols) if all(abs(p.z) > 1e-9 for p in c)]
        for i, c in enumerate(cols):
            for j, p in enumerate(c):
                if abs(p.z) < 1e-9 and good:
                    p.z = cols[min(good, key=lambda g: abs(g - i))][j].z
        idx = [[cg.add(p, None) for p in col] for col in cols]
        for i in range(NX - 1):
            for j in range(3):
                cg.face((idx[i][j], idx[i + 1][j], idx[i + 1][j + 1], idx[i][j + 1]), C.lid_reg, 0)
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


def line_safe(key, px=4):
    """Mask of ID-render pixels at least px away from any outline (a change of piece / region id): constant UVs are
    placed there so they never sit on printed line art (LESSONS L51)."""
    import numpy as np
    b = np.zeros(key.shape, bool)
    dv = key[1:, :] != key[:-1, :]; dh = key[:, 1:] != key[:, :-1]
    b[1:, :] |= dv; b[:-1, :] |= dv; b[:, 1:] |= dh; b[:, :-1] |= dh
    for _ in range(px):
        d = b.copy(); d[1:, :] |= b[:-1, :]; d[:-1, :] |= b[1:, :]; d[:, 1:] |= b[:, :-1]; d[:, :-1] |= b[:, 1:]; b = d
    return ~b


def is_hidden_prop(o):
    ch, _, part = o.name.partition("_")
    return PROPS.get(ch, {}).get(part) is False


def front_uv_region(objs, sheet_xy, art_h, inset):
    """UV0 = front orthographic page projection u = x + sheetX + 0.5, v = (y + sheetY) / artH (character-local x, y),
    with an inward inset at silhouettes. A face corner whose vertex is hidden in the front view behind a DIFFERENT
    region (a ray toward the viewer hits one) samples the nearest visible vertex of its own region instead, so e.g. a
    thigh behind the hanging sash is not painted orange. Corners hidden behind their own region keep the projection
    (overlapping feathers, the back of the cuirass). story_mesh.front_uv_with_occlusion with the test relaxed from
    (part, piece, region) to region: Gabriel's feathers cycle through piece ids, which must not count as occluders."""
    from mathutils.kdtree import KDTree
    sX, sY = sheet_xy; off = V(sX, sY, 0)
    allv, allf, freg, per = [], [], [], []
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
    stats = {"hiddenCorners": 0, "corners": 0}
    zdir = V(0, 0, 1)
    for o, vco, vn, rid in per:
        me = o.data
        hits = [bvh.ray_cast(p + zdir * 0.00035 + n * 0.00012, zdir, 10.0)[2] for p, n in zip(vco, vn)]
        vis = {}
        for fi, poly in enumerate(me.polygons):
            for vi in poly.vertices:
                h = hits[vi]
                if (h is None or freg[h] == rid[fi]) and vn[vi].z > 0.05:
                    vis.setdefault(rid[fi], {})[vi] = vco[vi]
        kds = {}
        for r, d in vis.items():
            kd = KDTree(len(d))
            for vi, p in d.items():
                kd.insert(p, vi)
            kd.balance(); kds[r] = kd
        uv0 = me.uv_layers.get("UVMap") or me.uv_layers.new(name="UVMap")

        def proj(p, n):
            return (p.x + sX + 0.5 - n.x * inset, (p.y + sY - n.y * inset) / art_h)
        for fi, poly in enumerate(me.polygons):
            r = rid[fi]
            for li in poly.loop_indices:
                vi = me.loops[li].vertex_index
                stats["corners"] += 1
                h = hits[vi]
                if h is None or freg[h] == r or r not in kds:
                    uv0.data[li].uv = proj(vco[vi], vn[vi])
                else:
                    stats["hiddenCorners"] += 1
                    _, vj, _ = kds[r].find(vco[vi])
                    nq = vn[vj]
                    uv0.data[li].uv = proj(vco[vj], V(nq.x, nq.y, 0) * 2.0)
        me.uv_layers.active = uv0
    return stats


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
    for b in bone_list(ch):
        if not bodyo.vertex_groups.get(b) and b not in PROPS[ch] and b != "eyelids":
            bodyo.vertex_groups.new(name=b)
    vis = [bodyo] + [o for o in props if not is_hidden_prop(o)]
    stats = front_uv_region(vis, sheet, ART_H, INSET)
    for o in props:
        if is_hidden_prop(o) and not o.data.uv_layers.get("UVMap"):
            o.data.uv_layers.new(name="UVMap")
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
    m = bpy.data.materials.get("ga_page") or bpy.data.materials.new("ga_page")
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
    safe = line_safe(key)
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
        if (mask & safe).any():
            mask = mask & safe
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
    safe = line_safe(key)
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
        ys, xs = np.nonzero(e & safe if (e & safe).sum() >= 4 else e)      # targets of moved faces: off the outlines
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


# =============================================================================================== modes
def mode_build():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    ch = "gabriel"
    report = {"chars": {}, "sheet": {ch: SHEET[ch]}, "sheetSource": SHEET_SRC, "artHeight": ART_H}
    C, rig, body, props, rep = build_character(ch)
    tris = tri_count([body] + props)
    report["chars"][ch] = {"tris": tris, "bodyTris": tri_count([body]),
                           "props": {o.name: [o.parent_bone, tri_count([o])] for o in props},
                           "bones": [b.name for b in rig.data.bones], "uvStats": rep["uvStats"],
                           "feathers": dict(WING_FEATHERS)}
    print(f"[{ch}] tris={tris} body={tri_count([body])} props={[(o.name, tri_count([o])) for o in props]} "
          f"feathers={WING_FEATHERS}")
    # ---- sheet ID render (front ortho, 2x art rect, no AA): one colour per (piece, region); eyelids and the hidden
    # trumpet are not drawn
    setup_workbench((2000, round(2000 * ART_H)))
    s = sc(); s.render.film_transparent = True; s.display.render_aa = 'OFF'
    s.display.shading.light = 'FLAT'; s.display.shading.color_type = 'MATERIAL'
    front_ortho_camera()
    idmap = {}
    on = all_meshes()
    for o in on:
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    id_materials(on, idmap)
    render(os.path.join(WORK, "id_2x.png"))
    ids = id_list(idmap)
    json.dump({"note": "front-ortho ID render of the rest pose at the sheet slot (2000 px = art width); background = "
                       "alpha 0; eyelids and the hidden trumpet are not drawn. Feathers cycle through four piece ids "
                       "per row so that neighbours always differ (an outline between them); the shaft of each long "
                       "feather is its own thin piece",
               "size": [s.render.resolution_x, s.render.resolution_y], "ids": ids},
              open(os.path.join(WORK, "id_2x.json"), "w"), indent=1)
    for o in on:
        o.hide_render = False
    anchor_info = apply_pixel_anchors(os.path.join(WORK, "id_2x.png"), ids)
    fix_info = fix_uvs_by_id(os.path.join(WORK, "id_2x.png"), ids)
    report["uvFixByIdRender"] = fix_info
    # the eyelids take one clean texel of the face skin (they slide over the eye decal; no printed detail on them)
    lid_uv = anchor_info.get(ch, {}).get("partAnchors", {}).get("eyelidAnchor.skin", {}).get("uv")
    lo = bpy.data.objects.get(f"{ch}_eyelids")
    if lid_uv and lo:
        for l in lo.data.uv_layers["UVMap"].data:
            l.uv = lid_uv
    # ---- regions_characters.json
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
            regs[reg]["printNote"] = ("too small to colour; print as detail line art, takes the colour at anchorUV"
                                      if an["target"] != reg else "small region: takes the colour of its own widest printed spot")
        if reg in ai.get("propAnchors", {}):
            an = ai["propAnchors"][reg]
            regs[reg]["anchoredTo"] = an["target"]; regs[reg]["anchorUV"] = an["uv"]
            regs[reg]["printNote"] = ("hidden-by-default prop, not printed with the figure; takes the colour at "
                                      "anchorUV (override: design.json characters.%s.propUV.%s = [u, v])" % (ch, reg))
    entry = {
        "height": CONTRACT_HEIGHT[ch], "bboxSheet": [round(v, 4) for v in allbb], "regions": regs,
        "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                      "files": {e: f"docs/gabriel/design/faces/{ch}_{e}.png" for e in EXPRESSIONS[ch]},
                      "clipExpression": CLIP_EXPRESSION[ch]},
        "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                  "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
        "restPose": {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z", "wings": "spread (the sheet pose)"},
        "wings": {"feathersPerWing": WING_FEATHERS.get("L"), "bones": ["wing?1", "wing?2", "wing?3", "wing?_prim"],
                  "primFanDeg": PRIM_FAN_DEG, "note": "see docs/gabriel/RIG.md §4 for the fold / flap recipes"},
        "props": {b: {"bone": b, "mesh": f"{ch}_{b}", "node": f"{ch}/{b}", "shownByDefault": v}
                  for b, v in PROPS[ch].items()},
        "trumpet": {"mouthpieceLocal": [round(v, 4) for v in C.trumpet["mouth"]],
                    "bellLocal": [round(v, 4) for v in C.trumpet["bell"]],
                    "note": "rest-pose positions (character-local, design axes) of the two ends of the trumpet"},
        "partAnchors": anchor_info.get(ch, {}).get("partAnchors", {})}
    regions_out = {"version": 1, "generatedBy": "pipeline/ga_character.py",
                   "note": "Colourable regions (face attribute st_region), the mesh parts that carry them, demo colour, "
                           "bbox on the sheet (x, y in art units, y up from the art rect bottom), and anchors (regions "
                           "too small to colour take a constant UV inside a larger region). ID render for the line "
                           "art: id_characters_2x.png/.json (same scheme as Ruth / Daniel).",
                   "sheet": {ch: {"sheetX": SHEET[ch][0], "sheetY": SHEET[ch][1]}},
                   "sheetSource": SHEET_SRC, "artHeightUnits": ART_H, "characters": {ch: entry}}
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
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
    sc()["ga_regions"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({c: {k: v for k, v in r.items() if k != "bones"} for c, r in report["chars"].items()}))
    print("PART_TRIS", json.dumps(PART_TRIS))


GOLD = {"pauldrons", "collar", "vambraces", "greaves", "belt", "hilt", "trumpet"}


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


def preview_setup(res=(800, 800)):
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    setup_eevee(res); preview_lights()
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
    for m in bpy.data.materials:                  # feathers: soft, a little sheen; gems: glossy
        if m.name in ("pv_gabriel_wingCoverts", "pv_gabriel_wingFeathers"):
            b = m.node_tree.nodes.get("Principled BSDF")
            b.inputs["Roughness"].default_value = 0.62
        if m.name == "pv_gabriel_gem":
            b = m.node_tree.nodes.get("Principled BSDF")
            b.inputs["Roughness"].default_value = 0.18
    sc().view_settings.exposure = -0.42
    return imgs


def show(props=False):
    for o in all_meshes():
        if o.name not in ("floor", "backdrop"):
            o.hide_render = is_hidden_prop(o) and not props


def D(x, y, z):
    """Design point (character-local) -> Blender world point at the sheet slot."""
    sx, sy = SHEET["gabriel"]
    return Vector((x + sx, -z, y + sy))


def set_decal(ch, name):
    img = bpy.data.images.load(os.path.join(FACES, f"{ch}_{name}.png"), check_existing=True)
    for m in bpy.data.materials:
        if m.name.startswith(f"pv_{ch}_") and m.node_tree.nodes.get("decal"):
            m.node_tree.nodes["decal"].image = img


def shot(cam, name, target, yaw, dist, height, lens=60, res=(800, 800)):
    sc().render.resolution_x, sc().render.resolution_y = res
    turntable(cam, target, yaw, dist, height, lens)
    render(os.path.join(WORK, name + ".png"))


def mode_preview():
    preview_setup()
    ch = "gabriel"; cam = camera(); show()
    L = landmarks(ch); Hd = L["top"] - L["chin"]; hy = (L["top"] + L["chin"]) / 2
    only = os.environ.get("GA_VIEWS", "").split(",") if os.environ.get("GA_VIEWS") else None

    def want(n):
        return only is None or n in only
    full = D(0, 0.41, -0.03)
    for nm, yaw, h in (("front", 0, 0.10), ("q34", 35, 0.14), ("side", 90, 0.10), ("back", 180, 0.12), ("q34b", 145, 0.14)):
        if want(nm):
            shot(cam, f"pv_{ch}_{nm}", full, yaw, 1.74, h)
    if want("phone"):
        shot(cam, f"pv_{ch}_phone", D(0, 0.33, 0), 25, 1.75, 1.15)
    hd = D(0, hy - 0.05 * Hd, 0.0)
    for nm, tgt, yaw, dist, h in (
            ("head", hd, 30, Hd * 4.4, Hd * 0.25), ("headfront", hd, 0, Hd * 4.4, Hd * 0.10),
            ("headside", hd, 90, Hd * 4.8, Hd * 0.10), ("hairback", D(0, hy - 0.2 * Hd, 0), 180, Hd * 5.4, Hd * 0.6),
            ("hairtop", D(0, hy + 0.2 * Hd, 0), 20, Hd * 3.0, Hd * 4.2), ("hairq", hd, 135, Hd * 4.8, Hd * 0.5),
            ("chest", D(0, 0.455, 0), 18, 0.56, 0.05), ("pauldron", D(0.095, 0.482, 0), 38, 0.34, 0.06),
            ("belt", D(0.02, 0.345, 0), 28, 0.50, 0.05), ("legs", D(0, 0.105, 0), 28, 0.62, 0.07),
            ("wing", D(0.27, 0.47, -0.08), 8, 1.20, 0.05), ("wingclose", D(0.30, 0.56, -0.09), 12, 0.42, 0.03),
            ("wingback", D(-0.27, 0.47, -0.08), 172, 1.20, 0.05)):
        if want(nm):
            shot(cam, f"pv_{ch}_{nm}", tgt, yaw, dist, h)
    rig = bpy.data.objects[f"{ch}_rig"]
    for s_ in "LR":
        if want("hand" + s_):
            tgt = rig.matrix_world @ rig.pose.bones["fingers" + s_].head
            shot(cam, f"pv_{ch}_hand{s_}", tgt, 30 if s_ == "L" else -30, 0.30, 0.05)
    if want("props"):
        show(props=True)
        shot(cam, f"pv_{ch}_props", D(-0.20, 0.30, 0), -35, 0.80, 0.10)
        show()
    if want("expr"):
        for e in EXPRESSIONS[ch]:
            set_decal(ch, e)
            shot(cam, f"pv_{ch}_expr_{e}", D(0, hy - 0.08 * Hd, 0), 10, Hd * 3.5, Hd * 0.12, res=(600, 600))
        set_decal(ch, DEFAULT_EXPR[ch])
    print("PREVIEW done")


def _region_of():
    return {i + 1: k.split(".")[1] for i, k in enumerate(REGIONS)}


class _RegionLookup(dict):
    def __missing__(self, r):
        # regions are recorded in the blend as a custom property by mode_build
        tab = json.loads(sc().get("ga_regions", "[]"))
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


def rot(rig, bone, steps):
    """Pose a bone by rotations about design-space axes through its head, applied in order (first listed = applied
    first, in the frame its parent gives it)."""
    pb = rig.pose.bones[bone]
    rest = pb.bone.matrix_local; h = rest.translation.copy()
    R = Matrix.Identity(4)
    for axis, deg in steps:
        R = Matrix.Rotation(math.radians(deg), 4, to_bl(V(*axis)).normalized()) @ R
    pb.rotation_mode = 'QUATERNION'
    pb.matrix_basis = rest.inverted() @ Matrix.Translation(h) @ R @ Matrix.Translation(-h) @ rest
    bpy.context.view_layer.update()


X_, Y_, Z_ = (1, 0, 0), (0, 1, 0), (0, 0, 1)
# Wing recipes: per wing bone a list of (design axis, degrees) for the LEFT wing; the right wing mirrors (the Y and Z
# angles change sign). Checked by eye in preview_pose.png; docs/gabriel/RIG.md §4 lists them for Animation.
WING_POSES = {
    "fold": {"1": [(Y_, 35)], "2": [(Y_, 115)], "3": [(Z_, -40), (Y_, -130)], "_prim": [(Z_, -96)]},
    "half": {"1": [(Y_, 16), (Z_, -6)], "2": [(Y_, 38)], "3": [(Z_, -30), (Y_, -42)], "_prim": [(Z_, -60)]},
    "flapdown": {"1": [(Z_, -34), (Y_, -10)], "2": [(Z_, -14), (Y_, -8)], "3": [(Z_, -10)], "_prim": [(Z_, -8)]},
    "flapup": {"1": [(Z_, 24), (Y_, 8)], "2": [(Z_, 12)], "3": [(Z_, 10)], "_prim": [(Z_, 6)]},
}
# kneeling: the folded wings tilted back 50 deg at the shoulder so the bundle clears the floor and the back foot
WING_POSES["kneel_fold"] = dict(WING_POSES["fold"], **{"1": [(Y_, 35), (X_, 50)]})


def wing_pose(rig, name):
    env = os.environ.get("GA_WINGPOSE_" + name.upper())
    poses = {k: [(tuple(ax), d) for ax, d in v] for k, v in json.loads(env).items()} if env else WING_POSES[name]
    for side, sg in (("L", 1), ("R", -1)):
        for suf, steps in poses.items():
            rot(rig, f"wing{side}{suf}", [(ax, deg * (sg if tuple(ax) != X_ else 1)) for ax, deg in steps])


def reset_pose(rig):
    for pb in rig.pose.bones:
        pb.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()


def mesh_min_y(names=("gabriel_body",)):
    dg = bpy.context.evaluated_depsgraph_get(); lo = 9.0
    for nm in names:
        ob = bpy.data.objects[nm].evaluated_get(dg); me = ob.to_mesh()
        lo = min(lo, min((ob.matrix_world @ v.co).z for v in me.vertices)); ob.to_mesh_clear()
    return lo - SHEET["gabriel"][1]


def wing_stats():
    """Posed check of the wings: lowest feather point (character-local y) and how many feather vertices lie inside the
    rest of the body (closest non-wing surface faces away from them, within 0.03)."""
    dg = bpy.context.evaluated_depsgraph_get()
    body = bpy.data.objects["gabriel_body"]
    gi = {g.index: g.name for g in body.vertex_groups}
    wing = []
    for v in body.data.vertices:
        gs = sorted(((g.weight, gi[g.group]) for g in v.groups), reverse=True)
        wing.append(bool(gs) and gs[0][1].startswith("wing"))
    ob = body.evaluated_get(dg); me = ob.to_mesh()
    co = [ob.matrix_world @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons if not any(wing[i] for i in p.vertices)]
    bvh = BVHTree.FromPolygons([tuple(c) for c in co], faces)
    inside = 0; low = 9.0; lowest = None
    for i, c in enumerate(co):
        if not wing[i]:
            continue
        if c.z < low:
            low = c.z; lowest = c
        hit = bvh.find_nearest(c, 0.03)
        if hit[0] is not None and (c - hit[0]).dot(hit[1]) < 0:
            inside += 1
    ob.to_mesh_clear()
    return {"wingMinY": round(low - SHEET["gabriel"][1], 4), "wingInside": inside}


def solve_trumpet(rig):
    """Find arm angles that bring the trumpet's mouthpiece to the lips with the bell up and forward (random search +
    refinement on the forward kinematics of upperArmR -> forearmR -> handR). Returns the (bone, steps) list."""
    import random as _r
    B = {b.name: to_design(b.head_local) for b in rig.data.bones}
    tp = rig.pose.bones["trumpet"].bone
    G = to_design(tp.head_local); ax = (to_design(tp.tail_local) - G).normalized()
    mouth = G - ax * (0.078 + TRUMPET_SHIFT)
    L = landmarks("gabriel")
    target = V(0.0, L["mouth"] - 0.001, SPEC["gabriel"]["zc"] + 0.0445)
    want = V(-0.06, 0.26, 0.96).normalized()
    names = ["upperArmR", "forearmR", "handR"]
    axes = [[X_, Y_, Z_], [X_, Y_, Z_], [X_, Y_, Z_]]

    def fk(params):
        A = Matrix.Identity(4)
        for nm, k in zip(names, range(3)):
            h = B[nm]
            R = Matrix.Identity(4)
            for axs, deg in zip(axes[k], params[3 * k:3 * k + 3]):
                R = Matrix.Rotation(math.radians(deg), 4, V(*axs)) @ R
            A = A @ Matrix.Translation(h) @ R @ Matrix.Translation(-h)
        return A

    def cost(params):
        A = fk(params)
        m = A @ mouth; d = (A.to_3x3() @ ax).normalized()
        elbow = fk(list(params[:3]) + [0] * 6) @ B["forearmR"]
        c = (m - target).length * 40 + (1 - d.dot(want)) * 9
        c += 0.004 * sum(abs(p) for p in params[6:9]) + 0.002 * sum(abs(p) for p in params[3:6])
        c += max(0.0, abs(params[6]) - 45) * 0.05 + max(0.0, abs(params[7]) - 45) * 0.05 + max(0.0, abs(params[8]) - 45) * 0.05
        c += (elbow - V(-0.185, 0.455, 0.045)).length * 6                        # elbow out to the side, shoulder high
        return c
    _r.seed(7)
    best = None
    for _ in range(4000):
        p = [_r.uniform(-150, 150) for _ in range(6)] + [_r.uniform(-40, 40) for _ in range(3)]
        c = cost(p)
        if best is None or c < best[0]:
            best = (c, p)
    c, p = best
    step = 20.0
    while step > 0.05:
        improved = False
        for i in range(9):
            for sgn in (1, -1):
                q = list(p); q[i] += sgn * step
                cq = cost(q)
                if cq < c:
                    c, p, improved = cq, q, True
        if not improved:
            step *= 0.5
    A = fk(p)
    info = {"cost": round(c, 4), "mouthErr": round(((A @ mouth) - target).length, 4),
            "dir": [round(v, 3) for v in (A.to_3x3() @ ax).normalized()]}
    return [(nm, [(axes[k][j], round(p[3 * k + j], 1)) for j in range(3)]) for k, nm in enumerate(names)], info


def pose_named(rig, name):
    B = {b.name: (to_design(b.head_local), to_design(b.tail_local)) for b in rig.data.bones}
    info = {}

    def hinge(side, bone):
        h, t = B[bone + side]; d = (t - h).normalized()
        return tuple(d.cross(V(0, 0, 1)) * (-1 if side == "L" else 1))
    if name in WING_POSES:
        wing_pose(rig, name)
    elif name == "kneel":
        wing_pose(rig, "kneel_fold")
        rot(rig, "thighL", [(X_, -86)]); rot(rig, "shinL", [(X_, 88)])
        rot(rig, "thighR", [(X_, 6)]); rot(rig, "shinR", [(X_, 98)]); rot(rig, "footR", [(X_, 42)]); rot(rig, "toeR", [(X_, -58)])
        rot(rig, "spine", [(X_, 6)]); rot(rig, "head", [(X_, 10)])
        rot(rig, "upperArmR", [(X_, -38), (Z_, 10)]); rot(rig, "forearmR", [(hinge("R", "forearm"), -62)])
        rot(rig, "upperArmL", [(X_, -22)]); rot(rig, "forearmL", [(hinge("L", "forearm"), 40)])
        rot(rig, "sash1", [(X_, -62)]); rot(rig, "sash2", [(X_, 58)])
        lo = mesh_min_y()
        rig.pose.bones["root"].location = (0, -lo, 0); bpy.context.view_layer.update()
        info["rootDrop"] = round(-lo, 4); info["minYAfter"] = round(mesh_min_y(), 4)
    elif name == "trumpet":
        wing_pose(rig, "flapup")
        steps, inf = solve_trumpet(rig); info.update(inf); info["steps"] = steps
        for nm, st in steps:
            rot(rig, nm, st)
        rot(rig, "fingersR", [(hinge("R", "hand"), -72)])
        rot(rig, "head", [(X_, -8)]); rot(rig, "chest", [(X_, -6)])
        rot(rig, "upperArmL", [(Z_, 22), (X_, -10)])
    elif name == "bends":
        for side, sg in (("L", 1), ("R", -1)):
            rot(rig, "forearm" + side, [(hinge(side, "forearm"), (65 if side == "L" else 35) * sg)])
            rot(rig, "fingers" + side, [(hinge(side, "hand"), 75 * sg)])
        rot(rig, "upperArmL", [(X_, -45)]); rot(rig, "upperArmR", [(Z_, -60)])
        rot(rig, "thighL", [(X_, -32)]); rot(rig, "shinL", [(X_, 52)])
        rot(rig, "spine", [(X_, 8)]); rot(rig, "head", [(Y_, 28)]); rot(rig, "jaw", [(X_, 14)])
        rig.pose.bones["eyelids"].scale = (1, LID_CLOSED * 0.5, 1)
        rot(rig, "hair1", [(X_, -22)]); rot(rig, "hair2", [(X_, -18)]); rot(rig, "sash1", [(X_, -24)]); rot(rig, "sash2", [(X_, -22)])
        wing_pose(rig, "half")
    bpy.context.view_layer.update()
    return info


def mode_wingtry():
    """Dev aid: $GA_TRIES = JSON list of {"name": wing pose name or "kneel", "recipe": {...}}; prints wing_stats()."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    rig = bpy.data.objects["gabriel_rig"]
    for t in json.loads(os.environ["GA_TRIES"]):
        reset_pose(rig); rig.pose.bones["root"].location = (0, 0, 0)
        key = "GA_WINGPOSE_" + ("KNEEL_FOLD" if t["name"] == "kneel" else t["name"].upper())
        if t.get("recipe") is not None:
            os.environ[key] = json.dumps(t["recipe"])
        info = pose_named(rig, t["name"]); info.update(wing_stats())
        os.environ.pop(key, None)
        print("TRY", json.dumps(t.get("recipe")), json.dumps(info))


def mode_posetest():
    preview_setup((560, 640))
    ch = "gabriel"; cam = camera()
    rig = bpy.data.objects[f"{ch}_rig"]
    only = os.environ.get("GA_POSES", "").split(",") if os.environ.get("GA_POSES") else None
    out = {}
    L = landmarks(ch); Hd = L["top"] - L["chin"]; hy = (L["top"] + L["chin"]) / 2
    for name, _ in POSES:
        if only and name not in only:
            continue
        reset_pose(rig); rig.pose.bones["root"].location = (0, 0, 0)
        for pb in rig.pose.bones:
            pb.scale = (1, 1, 1)
        show(props=(name == "trumpet"))
        set_decal(ch, {"trumpet": "blow", "kneel": "kind", "flapdown": "calm", "flapup": "announce"}.get(name, DEFAULT_EXPR[ch]))
        out[name] = pose_named(rig, name)
        if name in ("fold", "half", "flapdown", "flapup", "kneel"):
            out[name].update(wing_stats())
        if os.environ.get("GA_NORENDER"):
            continue
        out[name]["quat"] = {pb.name: [round(v, 4) for v in pb.rotation_quaternion] for pb in rig.pose.bones
                             if pb.rotation_mode == 'QUATERNION' and abs(pb.rotation_quaternion.w) < 0.99995}
        tgt = D(0, 0.36 if name != "kneel" else 0.26, -0.03)
        dist = 2.05 if name in ("flapdown", "flapup", "half", "bends", "trumpet") else 1.55
        for v, yaw in POSE_VIEWS:
            shot(cam, f"pose_{name}_{v}", tgt, yaw, dist, 0.14, res=(560, 640))
        if os.environ.get("GA_TOP"):
            shot(cam, f"pose_{name}_top", D(0, 0.45, -0.03), 0, 0.2, 1.9, res=(640, 640))
        if name == "trumpet":
            shot(cam, "pose_trumpet_close", D(-0.03, hy - 0.2 * Hd, 0.05), -32, 0.62, 0.06, res=(560, 640))
    if (not only or "blink" in only) and not os.environ.get("GA_NORENDER"):
        reset_pose(rig); show(); set_decal(ch, DEFAULT_EXPR[ch])
        rig.pose.bones["eyelids"].scale = (1, LID_CLOSED, 1); bpy.context.view_layer.update()
        shot(cam, "pose_blink_close", D(0, hy - 0.05 * Hd, 0), 28, Hd * 4.4, Hd * 0.2, res=(560, 640))
    json.dump(out, open(os.path.join(WORK, "pose_info.json"), "w"), indent=1, default=str)
    print("POSETEST", json.dumps(out, default=str))


def mode_uvcheck():
    """The model wearing $GA_WORK/uvproof.png (or $GA_UV_TEXTURE) through UV0: front ortho (must equal the sheet) and
    3/4 + back perspective (each region keeps its colour all round)."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get("GA_UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        o.data.materials.clear(); o.data.materials.append(m)
    setup_eevee((1000, round(1000 * ART_H))); preview_lights()
    cam = front_ortho_camera()
    for o in all_meshes():
        o.hide_render = o.name.endswith("_eyelids") or is_hidden_prop(o)
    bpy.data.objects["backdrop"].hide_render = True
    sc().render.film_transparent = True; sc().render.image_settings.color_mode = 'RGBA'
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 1.6
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = True
    render(os.path.join(WORK, "uv_front.png"))
    sc().render.film_transparent = False; sc().render.image_settings.color_mode = 'RGB'
    for L in ("key", "rim", "fill"):
        bpy.data.objects[L].hide_render = False
    bpy.data.objects["backdrop"].hide_render = False
    sc().world.node_tree.nodes["Background"].inputs[1].default_value = 0.55
    for nm, yaw in (("q34", 35), ("back", 180)):
        shot(cam, f"uv_{nm}", D(0, 0.405, -0.03), yaw, 2.05, 0.12, res=(1000, 880))
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
                "extra": sorted(set(bones) - set(want)), "boneCount": len(bones), "actions": len(bpy.data.actions),
                "meshes": {}}
        tris = 0
        for o in meshes:
            t = sum(len(p.vertices) - 2 for p in o.data.polygons); tris += t
            maxinf = max((sum(1 for g in v.groups if g.weight > 0) for v in o.data.vertices), default=0)
            uvl = o.data.uv_layers
            n0 = len(uvl[0].data)
            u0 = [uvl[0].data[i].uv for i in range(0, n0, max(1, n0 // 4000))]
            u1 = [uvl[1].data[i].uv for i in range(0, n0, max(1, n0 // 4000))] if len(uvl) > 1 else []
            layer0_page = all(-0.01 <= a.x <= 1.01 and -0.01 <= a.y <= 1.01 for a in u0)
            layer1_decal = (len(u1) > 0 and any(a.x < -0.5 for a in u1))
            info.setdefault("uvOrderOK", True)
            info["uvOrderOK"] &= layer0_page and layer1_decal
            info["meshes"][o.name] = {"skinned": any(m.type == 'ARMATURE' for m in o.modifiers),
                                      "parentBone": o.parent_bone or None, "tris": t, "verts": len(o.data.vertices),
                                      "uvLayers": [u.name for u in o.data.uv_layers], "maxInfluences": maxinf,
                                      "materials": [m.name for m in o.data.materials if m]}
        info["tris"] = tris; info["trisUnder90k"] = tris <= 90000
        vis = [o for o in meshes if not o.name.endswith("_trumpet")]
        pts = [(o.matrix_world @ v.co) for o in vis for v in o.data.vertices]
        body = [o for o in meshes if o.name.endswith("_body")][0]
        gi = {g.index: g.name for g in body.vertex_groups}
        crown = 0.0
        for v in body.data.vertices:
            gs = sorted(((g.weight, gi[g.group]) for g in v.groups), reverse=True)
            if gs and gs[0][1] == "head":
                crown = max(crown, (body.matrix_world @ v.co).z)
        used = {gi[g.group] for v in body.data.vertices for g in v.groups if g.weight > 0}
        info["emptyGroups"] = sorted(set(gi.values()) - used)
        info["crown"] = round(crown, 4)
        info["heightTop"] = round(max(p.z for p in pts), 4); info["minY"] = round(min(p.z for p in pts), 4)
        info["span"] = round(max(p.x for p in pts) - min(p.x for p in pts), 4)
        info["depth"] = [round(min(-p.y for p in pts), 4), round(max(-p.y for p in pts), 4)]
        out[ch] = info
    json.dump(out, open(os.path.join(WORK, "verify.json"), "w"), indent=1)
    print("VERIFY", json.dumps({c: {k: v for k, v in i.items() if k != "meshes"} for c, i in out.items()}))


if __name__ == "__main__":
    {"build": mode_build, "preview": mode_preview, "posetest": mode_posetest, "wingtry": mode_wingtry, "verify": mode_verify,
     "uvcheck": mode_uvcheck}[MODE]()
