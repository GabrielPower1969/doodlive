"""Esther (story pack #2): characters esther, king, haman — meshes, rig, weights, UVs, face decals, previews, GLBs.

Contract: docs/esther/CONTRACT.md §2-§3 (ids, heights, bone names), look: docs/esther/DESIGN.md. Same family and
method as David & Goliath (pipeline/dg_build.py, shared helpers in pipeline/story_mesh.py), finer:
  * heads mapped from the David & Goliath base head by landmarks (same head-to-body ratio and face style), modelled
    nose / brow / lips / chin, ears; face decals on UV1 (one PNG per expression) + an eyelid blink by the `eyelids` bone;
  * long robes with real volume: flared skirts with folds and wavy hems, bell or cuffed sleeves extruded from the body,
    rolled hems; Esther's cape drapes over the shoulders and hangs plumb from the shoulder blades with folds;
  * ornaments are separate meshes: diadem, necklace beads + star pendant, crown with bands and rosettes, collar, belt
    with medallion, sceptre with knob and wings, cap with rim, signet rings;
  * Esther's long braid is a chain of interlocking lobes over her right shoulder (braid1-3);
  * hands: palm, four fingers with three joints and a thumb, from palm ports (box-modelled), one `fingers` bone/hand.
  * UV0 = front orthographic page projection at the sheet position (like dg_build) + occlusion-aware fix: a corner
    hidden behind another part/region samples the nearest visible point of its own region (back of the cape, the robe
    behind the braid); tiny ornaments take a constant UV inside a larger region (anchors, regions_characters.json).

Run (repo root):
  python3 pipeline/es_characters.py faces                                         # face decal PNGs (needs Pillow)
  blender -b --factory-startup --python pipeline/es_characters.py -- build        # models, rig, GLBs, blend, ID render
  blender -b --factory-startup --python pipeline/es_characters.py -- preview      # lit demo-palette renders
  blender -b --factory-startup --python pipeline/es_characters.py -- verify       # re-import GLBs, check bones/budget
  python3 pipeline/es_characters.py compose                                       # preview_*.png contact sheets
Intermediate renders go to $ES_WORK (default /tmp/es_work).
"""
import sys, os, json, math

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
MODEL = os.path.join(ROOT, "assets/esther/model")
FACES = os.path.join(ROOT, "docs/esther/design/faces")
WORK = os.environ.get("ES_WORK", "/tmp/es_work")
BLEND = os.path.join(MODEL, "characters.blend")
DESIGN_JSON = os.path.join(ROOT, "assets/esther/design.json")
for d in (MODEL, FACES, WORK):
    os.makedirs(d, exist_ok=True)

try:
    import bpy
    IN_BLENDER = True
except ImportError:
    IN_BLENDER = False

CHARS = ("esther", "king", "haman")
CONTRACT_BONES = ["root", "hips", "spine", "chest", "neck", "head", "jaw",
                  "shoulderL", "upperArmL", "forearmL", "handL", "shoulderR", "upperArmR", "forearmR", "handR",
                  "thighL", "shinL", "footL", "toeL", "thighR", "shinR", "footR", "toeR",
                  "fingersL", "fingersR", "eyelids"]
EXTRA_BONES = {"esther": ["braid1", "braid2", "braid3", "cape1", "cape2", "diadem"],
               "king": ["crown", "sceptre", "sceptreTip", "ring"],
               "haman": ["cap", "ring"]}
DEFAULT_SHEET = {"esther": (-0.33, 0.015), "king": (0.02, 0.015), "haman": (0.34, 0.015)}
ART_H_DEFAULT = 1.227
INSET = 0.004
ARM_DEG = 55.0                      # rest pose: arms 55 deg below horizontal (three figures must fit side by side)

# ---------------------------------------------------------------------------------------------- palette (DESIGN.md)
PALETTE = {
    "esther": {"skin": "#F1C6A0", "hair": "#4A2E1F", "robe": "#F6EEDC", "cape": "#C8323F", "sash": "#F2C14E",
               "underSash": "#8CC8F0", "diadem": "#F2C14E", "necklace": "#F2C14E", "pendant": "#2F5FD0",
               "sandals": "#C9893F"},
    "king": {"skin": "#D9A27A", "beard": "#3A2418", "robe": "#6A3FB5", "collar": "#F2C14E", "belt": "#F2C14E",
             "crown": "#6A3FB5", "crownBands": "#F2C14E", "sceptre": "#F2C14E", "shoes": "#8A5A34", "ring": "#F2C14E"},
    "haman": {"skin": "#E2B48C", "beard": "#2A1C16", "robe": "#8E2B3A", "panels": "#D9A63A", "cap": "#1F5C66",
              "capRim": "#F2C14E", "ring": "#F2C14E", "shoes": "#5A3A28"},
}
REGION_NAMES = {   # zh / en for the sheet role
    "skin": ("皮肤", "skin"), "hair": ("头发", "hair"), "robe": ("长袍", "robe"), "cape": ("披肩", "cape"),
    "sash": ("金腰带", "gold sash"), "underSash": ("蓝腰巾", "blue under-sash"), "diadem": ("冠冕", "diadem"),
    "necklace": ("项链", "necklace"), "pendant": ("星形坠子", "star pendant"), "sandals": ("鞋", "sandals"),
    "beard": ("胡子和头发", "beard and hair"), "collar": ("金领", "gold collar"), "belt": ("腰带", "belt"),
    "crown": ("王冠", "crown"), "crownBands": ("王冠金边", "crown bands"), "sceptre": ("金杖", "sceptre"),
    "shoes": ("鞋", "shoes"), "panels": ("镶边", "panels and cuffs"), "cap": ("帽子", "cap"),
    "capRim": ("帽边", "cap rim"), "ring": ("戒指", "signet ring"),
}
# regions too small to colour on A4 (< ~2 mm across): constant UV deep inside a larger region of the same character
ANCHORS = {
    "esther": {"diadem": "sash", "necklace": "sash", "pendant": "underSash"},
    "king": {"crownBands": "collar", "ring": "collar", "sceptre": "sceptre"},
    "haman": {"ring": "panels", "capRim": "panels", "beard": "beard"},
}
# parts whose printed area is a sliver (< 6 px): every face of (part, region) takes one UV inside a larger region.
# "FACE" = the same character's face skin, deepest point away from the eyes / brows / nose / mouth (Integration
# 2026-11-14: hands rendered paper-white because their slivers stay unpainted on the sheet).
PART_ANCHORS = {
    "esther": {("handL", "skin"): "FACE", ("handR", "skin"): "FACE", ("braid", "sash"): "sash"},
    "king": {("handL", "skin"): "FACE", ("handR", "skin"): "FACE"},
    "haman": {("handL", "skin"): "FACE", ("handR", "skin"): "FACE"},
}

# ---------------------------------------------------------------------------------------------- proportions
# BASE_LAND fractions of the D&G base head (chin -> skull top): mouth 0.163, nose 0.273, eye 0.490, brow 0.583.
FR = dict(mouth=0.163, nose=0.273, eye=0.490, brow=0.583)
SPEC = {
    "esther": dict(height=0.34, top=0.330, chin=0.272, hw=0.0204, zc=-0.001, depth=1.02, jaw=-0.12, cheek=0.08,
                   fr=dict(eye=0.472, brow=0.565, nose=0.262, mouth=0.158),
                   chin_narrow=0.10, crown=0.0, noseH=0.0016, nose_w=0.82, nose_long=0.0, brow=0.45, lips=1.25,
                   chinAmt=0.8, sockets=0.85, cheekbones=0.9,
                   neckBase=0.257, neck=(0.0079, 0.0074, -0.0080), shoulder=(0.034, 0.250), chestY=0.230,
                   waistY=0.205, hipY=0.180, hipX=0.0165, kneeY=0.094, ankleY=0.018, footLen=0.038, footScale=1.0,
                   upperArm=0.058, forearm=0.049, hand=0.031, palmFrac=0.52,
                   handDims=dict(palmW=0.0132, palmH=0.0054, wristW=0.0094, wristH=0.0064, fingerW=0.0034,
                                 fingerT=0.0031, thumbW=0.0033, thumbT=0.0030, armR=0.0058)),
    "king": dict(height=0.40, top=0.354, chin=0.294, hw=0.0222, zc=-0.002, depth=1.06, jaw=0.10, cheek=0.04,
                 chin_narrow=0.0, crown=0.0, noseH=0.0028, nose_w=1.12, nose_long=0.0, brow=1.15, lips=0.9,
                 chinAmt=0.6, sockets=1.0, cheekbones=1.0,
                 neckBase=0.273, neck=(0.0108, 0.0098, -0.0108), shoulder=(0.046, 0.266), chestY=0.246,
                 waistY=0.218, hipY=0.190, hipX=0.0200, kneeY=0.100, ankleY=0.019, footLen=0.044, footScale=1.15,
                 upperArm=0.066, forearm=0.056, hand=0.037, palmFrac=0.52,
                 handDims=dict(palmW=0.0154, palmH=0.0064, wristW=0.0112, wristH=0.0078, fingerW=0.0039,
                               fingerT=0.0036, thumbW=0.0040, thumbT=0.0036, armR=0.0072)),
    "haman": dict(height=0.37, top=0.354, chin=0.297, hw=0.0188, zc=-0.001, depth=1.06, jaw=-0.02, cheek=-0.06,
                  chin_narrow=0.22, crown=0.0, noseH=0.0034, nose_w=0.92, nose_long=0.05, brow=1.3, lips=0.7,
                  chinAmt=1.2, sockets=1.1, cheekbones=1.25,
                  neckBase=0.276, neck=(0.0086, 0.0080, -0.0088), shoulder=(0.039, 0.270), chestY=0.250,
                  waistY=0.224, hipY=0.197, hipX=0.0175, kneeY=0.105, ankleY=0.019, footLen=0.042, footScale=1.1,
                  upperArm=0.065, forearm=0.055, hand=0.035, palmFrac=0.52,
                  handDims=dict(palmW=0.0140, palmH=0.0056, wristW=0.0100, wristH=0.0068, fingerW=0.0034,
                                fingerT=0.0032, thumbW=0.0035, thumbT=0.0032, armR=0.0062)),
}


def landmarks(ch):
    s = SPEC[ch]; H = s["top"] - s["chin"]
    L = dict(top=s["top"], chin=s["chin"], zc=s["zc"], hw=s["hw"])
    for k, f in FR.items():
        L[k] = s["chin"] + s.get("fr", {}).get(k, f) * H
    return L


def face_layout(ch):
    """Decal rectangle (character-local x0 y0 x1 y1) and eye / brow / mouth placement in normalised decal space
    (0..1, y up). Like D&G (square rect from just under the mouth), side max(1.76 hw, 0.72 H) so brows fit."""
    s = SPEC[ch]; L = landmarks(ch); H = L["top"] - L["chin"]; hw = s["hw"]
    w = max(1.76 * hw, 0.72 * H); x0 = -w / 2; y0 = L["mouth"] - 0.14 * H
    rect = [x0, y0, x0 + w, y0 + w]

    def nx(x): return (x - x0) / w

    def ny(y): return (y - y0) / w
    eyeX = {"esther": 0.415, "king": 0.40, "haman": 0.40}[ch] * hw
    ew, eh = {"esther": (0.300, 0.228), "king": (0.240, 0.155), "haman": (0.232, 0.142)}[ch]
    return dict(rect=rect, eyeL=(nx(eyeX), ny(L["eye"])), eyeR=(nx(-eyeX), ny(L["eye"])),
                eyeHalf=(ew * hw / w, eh * hw / w), brow=ny(L["brow"]), mouth=ny(L["mouth"]), nose=ny(L["nose"]),
                eyeLocal=(eyeX, L["eye"], ew * hw, eh * hw))


EXPRESSIONS = {"esther": ["calm", "worried", "pray", "brave", "talk", "joy"],
               "king": ["stern", "listen", "smile", "surprised", "angry"],
               "haman": ["smug", "sly", "shocked", "scared"]}
DEFAULT_EXPR = {"esther": "calm", "king": "stern", "haman": "smug"}
CLIP_EXPRESSION = {   # suggestion for the Animation / Integration roles (clip -> decal), CONTRACT §4 clip names
    "esther": {"idle": "calm", "walk": "calm", "talk": "talk", "worried": "worried", "pray": "pray",
               "rise_brave": "brave", "climb": "brave", "bow": "calm", "touch_sceptre": "brave", "invite": "calm",
               "point": "brave", "joy": "joy", "wave": "joy"},
    "king": {"sit_idle": "stern", "sit_talk": "stern", "sit_listen": "listen", "give_ring": "stern",
             "extend_sceptre": "smile", "sit_smile": "smile", "stand_angry": "angry", "angry_idle": "angry",
             "point_away": "angry", "celebrate": "smile"},
    "haman": {"idle": "smug", "strut": "smug", "talk": "sly", "demand": "smug", "whisper": "sly", "take_ring": "sly",
              "smug": "smug", "shock": "shocked", "cower": "scared", "led_away": "scared"},
}


def sheet_positions():
    """sheetX / sheetY per character: assets/esther/design.json characters.<id> when present (Set + sheet role),
    else the defaults; the defaults are also written to model/characters_layout.json."""
    out = {ch: list(DEFAULT_SHEET[ch]) for ch in CHARS}
    art_h = ART_H_DEFAULT; src = "defaults"
    if os.path.exists(DESIGN_JSON):
        try:
            d = json.load(open(DESIGN_JSON))
            art_h = d.get("artHeightUnits", art_h)
            for ch in CHARS:
                c = d.get("characters", {}).get(ch, {})
                if "sheetX" in c:
                    out[ch] = [c["sheetX"], c.get("sheetY", out[ch][1])]; src = "design.json"
        except Exception as e:                                   # noqa: BLE001
            print("design.json unreadable, using defaults:", e)
    return out, art_h, src


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

    made = {}
    for ch in CHARS:
        F = face_layout(ch)
        eL, eR, half, by, my = F["eyeL"], F["eyeR"], F["eyeHalf"], F["brow"], F["mouth"]
        bcol = {"esther": (58, 36, 26, 255), "king": (40, 26, 18, 255), "haman": (26, 18, 15, 255)}[ch]
        iris = {"esther": (104, 64, 38), "king": (82, 52, 34), "haman": (122, 96, 40)}[ch]
        bw = {"esther": 0.024, "king": 0.040, "haman": 0.044}[ch]
        for ex in EXPRESSIONS[ch]:
            img = Image.new("RGBA", (N, N), (0, 0, 0, 0))
            dr = ImageDraw.Draw(img)
            E = dict(look=(0, 0), top=1.0, bot=1.0, tilt=0.15, lash=0, mode="open", lid=0.10, inner_up=0.0, pupil=0.55,
                     wet=False)
            Bp = dict(raise_=0.0, inner=0.0, arch=0.35, thick=1.0, outer=0.0)
            Bl, Br = {}, {}
            M = dict(kind="flat", wd=0.095, jaw=0.0, side=0.0)
            lipcol = None
            if ch == "esther":
                E.update(lash=3, tilt=0.18, lid=0.05); lipcol = (214, 104, 118, 150); M["wd"] = 0.080
                Bp.update(raise_=0.075, arch=0.30, thick=0.95)
                if ex == "calm":
                    M.update(kind="soft")
                elif ex == "worried":
                    E.update(top=1.1, look=(0, 0.25), tilt=0.0); Bp.update(inner=0.040, raise_=0.085, arch=0.12, outer=-0.015)
                    M.update(kind="frown", wd=0.060)
                elif ex == "pray":
                    E.update(mode="closed"); Bp.update(inner=0.018, raise_=0.075); M.update(kind="soft", wd=0.065)
                elif ex == "brave":
                    E.update(top=0.92, tilt=0.12, look=(0, 0.1)); Bp.update(inner=-0.014, raise_=0.068, arch=0.22)
                    M.update(kind="small", wd=0.085)
                elif ex == "talk":
                    M.update(kind="open", wd=0.065, jaw=0.05)
                elif ex == "joy":
                    E.update(mode="happy"); Bp.update(raise_=0.095, arch=0.45); M.update(kind="grin", wd=0.090, jaw=0.05)
            elif ch == "king":
                E.update(lid=0.35, top=0.85, tilt=0.05); M["wd"] = 0.085; Bp.update(raise_=0.060, arch=0.25, thick=1.0)
                if ex == "stern":
                    E.update(top=0.72); Bp.update(inner=-0.012, raise_=0.052, arch=0.12); M.update(kind="flat")
                elif ex == "listen":
                    E.update(top=0.88, look=(0.25, 0.1)); Bl = dict(raise_=0.075, arch=0.4); Br = dict(raise_=0.058)
                    M.update(kind="small", wd=0.070)
                elif ex == "smile":
                    E.update(top=0.70, bot=0.65, tilt=0.0); Bp.update(raise_=0.068, arch=0.45); M.update(kind="grin", wd=0.095, jaw=-0.25)
                elif ex == "surprised":
                    E.update(top=1.25, bot=1.15, pupil=0.38, lid=0.10); Bp.update(raise_=0.100, arch=0.55)
                    M.update(kind="o", wd=0.070, jaw=0.15)
                elif ex == "angry":
                    E.update(top=0.62, tilt=-0.10, look=(0, -0.1)); Bp.update(inner=-0.040, raise_=0.050, arch=0.05, thick=1.15, outer=0.010)
                    M.update(kind="shout", wd=0.085, jaw=0.05)
            else:  # haman
                E.update(lid=0.30, top=0.80, tilt=0.20); M["wd"] = 0.085; Bp.update(raise_=0.065, arch=0.55, thick=1.0)
                if ex == "smug":
                    E.update(top=0.50, look=(0, -0.2)); Bl = dict(raise_=0.090, arch=0.75); Br = dict(raise_=0.062, arch=0.4)
                    M.update(kind="smirk", wd=0.085, side=1)
                elif ex == "sly":
                    E.update(top=0.55, bot=0.75, look=(-0.9, 0.0)); Bl = dict(raise_=0.098, arch=0.85); Br = dict(raise_=0.055, inner=-0.020, arch=0.2)
                    M.update(kind="smirk", wd=0.095, side=-1)
                elif ex == "shocked":
                    E.update(top=1.35, bot=1.25, pupil=0.30, lid=0.05, tilt=0.0); Bp.update(raise_=0.115, arch=0.70)
                    M.update(kind="o", wd=0.060, jaw=0.35)
                elif ex == "scared":
                    E.update(top=1.20, bot=1.10, pupil=0.36, look=(0.2, 0.3), wet=True, tilt=-0.05)
                    Bp.update(raise_=0.095, inner=0.040, arch=0.15, outer=-0.025); M.update(kind="wobbly", wd=0.085, jaw=0.05)
            for side, c in ((1, eL), (-1, eR)):
                eye(img, c, half, side=side, iris=iris, line=0.019 if ch == "esther" else 0.020, **E)
            dr = ImageDraw.Draw(img)
            for side, c in ((1, eL), (-1, eR)):
                b = dict(Bp); b.update(Bl if side == 1 else Br)
                brow(dr, side, (c[0], by - 0.015), half, w=bw, col=bcol, **b)
            mouth(img, M["kind"], 0.5, my, M["wd"] * 1.25, lipcol=lipcol, jaw=M["jaw"], side=M["side"])
            if ch == "esther":
                blush(img, 0.33, F["nose"] - 0.03, 0.085, 0.045, 140 if ex == "joy" else 85)
            if ch == "king" and ex == "smile":
                lines(img, [[(0.5 + s * (half[0] + eL[0] - 0.5 + 0.035), eL[1] - 0.01 + k * 0.022),
                             (0.5 + s * (half[0] + eL[0] - 0.5 + 0.075), eL[1] - 0.02 + k * 0.03)] for s in (-1, 1) for k in (0, 1)])
            if ch == "haman" and ex == "scared":
                drop(img, 0.86, eL[1] + 0.06, 0.035)
            if ch == "haman" and ex in ("smug", "sly"):       # cheek line on the smirk side
                s = 1 if ex == "smug" else -1
                pass
            out = img.resize((PX, PX), Image.LANCZOS)
            path = os.path.join(FACES, f"{ch}_{ex}.png")
            out.save(path); made[f"{ch}_{ex}"] = os.path.relpath(path, ROOT)
    # overview sheet: every expression over a skin swatch
    cells = [(ch, ex) for ch in CHARS for ex in EXPRESSIONS[ch]]
    cols = 6; cw = 256
    sheet = Image.new("RGB", (cols * cw, ((len(cells) + cols - 1) // cols) * (cw + 24)), (250, 246, 238))
    dr = ImageDraw.Draw(sheet)
    for i, (ch, ex) in enumerate(cells):
        x, y = (i % cols) * cw, (i // cols) * (cw + 24)
        bg = Image.new("RGBA", (cw, cw), tuple(int(PALETTE[ch]["skin"][k:k + 2], 16) for k in (1, 3, 5)) + (255,))
        fc = Image.open(os.path.join(FACES, f"{ch}_{ex}.png")).resize((cw, cw), Image.LANCZOS)
        bg.alpha_composite(fc); sheet.paste(bg.convert("RGB"), (x, y))
        dr.text((x + 8, y + cw + 4), f"{ch}_{ex}", fill=(40, 30, 20))
    sheet.save(os.path.join(FACES, "overview.png"))
    print("faces:", len(made), "->", FACES)
    return made


def compose():
    """Contact sheets model/preview_<char>.png and preview_all.png from the $ES_WORK renders."""
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
        det = [("head", "face 3/4"), ("headfront", "face front"), ("handL", "left hand"), ("handR", "right hand")]
        files2 = [os.path.join(WORK, f"pv_{ch}_{v}.png") for v, _ in det]
        bot = grid(files2, [lb for _, lb in det], 4, (480, 480), "close-ups")
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
                 "braid2 / cape2 (esther)")
        g.save(os.path.join(MODEL, "preview_pose.png"))
    print("composed previews ->", MODEL)


def proof():
    """$ES_WORK/uvproof.png: the ID render with every (piece, region) in its demo colour and a thin dark outline,
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
ONLY = [c for c in os.environ.get("ES_ONLY", "").split(",") if c] or list(CHARS)
SHEET, ART_H, SHEET_SRC = sheet_positions()


# =============================================================================================== context + skeleton
class Ctx:
    def __init__(self, ch):
        self.ch = ch; self.s = SPEC[ch]; self.L = landmarks(ch); self.F = face_layout(ch)
        self.H = self.L["top"] - self.L["chin"]; self.S = self.s["height"] / 0.30
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
    fist = (C.ch == "king" and side == "R")
    if fist:                                    # wrist cocked: hand points out nearly level, holds the sceptre upright
        b = math.radians(26.0)
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


def build_leg(C, side, shoe_top, reg_shoe, pointy=0.0, top_y=0.050):
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

    def wfn(p):
        w = wt0(p)
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
               regfn=None, sleeve_lip=(0.86, 0.0004, 0.0040), step=0.0052, N=44):
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
    cg = torso_shell(C, TT, N, port, math.radians(30), sleeves, wtorso, "robe", e=2.5,
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
    C.add("robe", cg, post=post, subdiv=0, smooth=(zone, 8))
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


# =============================================================================================== Esther
def build_esther(C):
    s = C.s; L = C.L; H = C.H; S = C.S
    shY = s["shoulder"][1]; nb = s["neckBase"]

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, L["brow"] + 0.40 * H), (0.05, L["brow"] + 0.37 * H), (0.09, L["brow"] + 0.25 * H),
                      (0.13, L["brow"] + 0.05 * H), (0.165, L["eye"] - 0.06 * H), (0.20, L["nose"] - 0.04 * H),
                      (0.24, L["mouth"] - 0.10 * H), (0.30, L["chin"] - 0.04 * H), (0.40, L["chin"] - 0.08 * H),
                      (0.50, L["chin"] - 0.10 * H)], uu)[0]
    C.hair_rim = rim

    def cull(p):
        u = head_u(C, p); ry = rim(u)
        if p.y < nb - 0.0060 * S:
            return True
        return (p.y > ry + 0.0045 * S and p.z < 0.70 * s["hw"]) or p.y > ry + 0.0080 * S
    skeleton(C)
    build_head(C, cull)

    def thick(u, y):
        uu = mirror_u(u)
        t = lerp(0.0030, 0.0042, smoothstep(L["brow"], L["top"] - 0.1 * H, y))           # volume on top
        t = lerp(t, 0.0034, smoothstep(0.10, 0.20, uu) * smoothstep(L["eye"], L["mouth"], y))
        if uu < 0.12:
            t = lerp(t, 0.0022, smoothstep(L["brow"] + 0.45 * H, L["brow"] + 0.36 * H, y))  # hairline sits close
        return t * S

    def plumb(uu):
        return smoothstep(0.12, 0.18, uu) * smoothstep(0.44, 0.30, uu)
    hair_shell(C, rim, thick, "hair", "hair", plumb=plumb, parting=True, waves=0.0005 * S, NU=40, NV=9)
    # ---- robe: ivory, bell sleeves
    R = [(0.2600, 0.0098, 0.0090, -0.0095), (0.2585, 0.0150, 0.0106, -0.0112), (0.2565, 0.0228, 0.0118, -0.0122),
         (0.2545, 0.0292, 0.0124, -0.0127), (0.2530, 0.0322, 0.0127, -0.0129), (0.2515, 0.0336, 0.0129, -0.0130), (0.2470, 0.0358, 0.0135, -0.0132), (0.2400, 0.0352, 0.0152, -0.0132),
         (0.2300, 0.0332, 0.0170, -0.0128), (0.2200, 0.0302, 0.0158, -0.0120), (0.2070, 0.0272, 0.0128, -0.0115),
         (0.1950, 0.0300, 0.0136, -0.0130), (0.1800, 0.0350, 0.0160, -0.0155), (0.1600, 0.0382, 0.0182, -0.0172),
         (0.1300, 0.0414, 0.0206, -0.0188), (0.0950, 0.0448, 0.0228, -0.0205), (0.0600, 0.0482, 0.0252, -0.0220),
         (0.0300, 0.0515, 0.0275, -0.0235), (0.0105, 0.0540, 0.0292, -0.0245)]
    sleeve = [(0.004, 0.0101), (0.012, 0.0099), (0.026, 0.0091), (0.042, 0.0087), (0.056, 0.0090), (0.068, 0.0106),
              (0.080, 0.0133), (0.091, 0.0162), (0.100, 0.0186), (0.104, 0.0195)]
    build_robe(C, R, sleeve, None, nf=14, fold_amp=0.0021, sleeve_fold=0.0012, bell_sag=0.0016 * S)
    for side in "LR":
        build_forearm_hand(C, side, s["upperArm"] * 0.0 + 0.010 * S)
        build_leg(C, side, 0.0110 * S, "sandals")
    # ---- under-sash (light blue, wide) + gold sash with knot and two tails
    wy = s["waistY"]
    waist_band(C, "underSash", "underSash", wy - 0.0085 * S, wy + 0.0080 * S, 0.0007 * S, bulge=0.0009 * S)
    waist_band(C, "sash", "sash", wy - 0.0024 * S, wy + 0.0024 * S, 0.0018 * S, bulge=0.0007 * S)
    cg = Cage(); wb = C.w(["hips", "spine"])
    kx = 0.0055 * S
    ka = math.asin(min(1.0, kx / table(C.robe_rows, wy)[0]))
    kc = robe_point(C, wy, ka, 0.0034 * S)
    lathe_y(cg, kc, [(-0.0026 * S, 0.0018 * S), (0.0, 0.0034 * S), (0.0026 * S, 0.0018 * S)], 8, wb, "sash", 1, e=2.6, zscale=0.6)
    for dx, y_end, wd in ((-0.0012, 0.150, 0.0022), (0.0022, 0.158, 0.0020)):
        pp, nn = [], []
        for t in [i / 6 for i in range(7)]:
            y = lerp(wy - 0.0020 * S, y_end * S / 1.133 if False else y_end, t)
            x = kx + dx * S + 0.0030 * S * t * (1 if dx > 0 else -0.4)
            a = math.asin(max(-1, min(1, x / (table(C.robe_rows, y)[0] + 0.002))))
            p = robe_point(C, y, a, (0.0030 + 0.0010 * math.sin(t * math.pi)) * S)
            pp.append(p); nn.append(V(p.x, 0, p.z).normalized())
        strip(cg, pp, nn, [wd * S * (1.0 + 0.25 * t) for t in [i / 6 for i in range(7)]], 0.0006 * S, wb, "sash", 1)
    C.add("sashKnot", cg, subdiv=0)
    # ---- cape (crimson): open at the front, over the shoulders, plumb from the shoulder blades, folds
    capebot = [(0.10, nb - 0.0075 * S), (0.14, nb - 0.0095 * S), (0.20, shY - 0.0035 * S), (0.25, shY - 0.0075 * S),
               (0.30, s["chestY"] - 0.0010 * S), (0.36, wy + 0.0000 * S), (0.42, wy - 0.0110 * S), (0.50, wy - 0.0150 * S)]
    u0, u1 = 0.10, 0.90; NU, NV = 42, 12
    cg = Cage()
    wcape = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.014 * S), ("shoulderR", 0.014 * S), ("cape1", 0.022 * S),
                 ("cape2", 0.022 * S)])
    ytop = nb + 0.0030 * S
    blade = s["chestY"] + 0.006 * S
    # cape bones: down the back from the shoulder line
    zb0 = table(C.robe_rows, blade)[2] - 0.0030 * S
    C.B["cape1"] = (V(0, shY + 0.002 * S, zb0 + 0.002 * S), V(0, s["chestY"] - 0.006 * S, zb0 - 0.0010 * S), "chest")
    C.B["cape2"] = (V(0, s["chestY"] - 0.006 * S, zb0 - 0.0010 * S), V(0, wy - 0.004 * S, zb0 - 0.0030 * S), "cape1")
    grid = []
    capebot = [(0.30, shY - 0.0080 * S), (0.34, s["chestY"] - 0.0020 * S), (0.39, wy + 0.0020 * S), (0.44, wy - 0.0090 * S),
               (0.50, wy - 0.0140 * S)]
    capetop = [(0.12, nb - 0.0030 * S), (0.20, nb - 0.0005 * S), (0.30, nb + 0.0015 * S), (0.50, nb + 0.0030 * S)]

    def ulo(v):
        return lerp(0.12, 0.30, smoothstep(0.0, 0.55, v))
    for i in range(NU + 1):
        t = i / NU
        yt = table(capetop, mirror_u(lerp(ulo(0), 1 - ulo(0), t)))[0]
        yb = table(capebot, mirror_u(lerp(ulo(1), 1 - ulo(1), t)))[0]
        col = []
        for j in range(NV + 1):
            v = j / NV
            u = lerp(ulo(v), 1 - ulo(v), t); uu = mirror_u(u)
            y = lerp(yt, yb, v ** 0.85)
            off = (0.0018 + 0.0010 * v) * S
            p = mantle_point(C, u, y, off, 0.0101 * S, plumb_y=blade, plumb_extra=0.0022 * S)
            if uu > 0.26:                       # back panel flares out sideways as it falls
                fl = smoothstep(blade, wy - 0.010 * S, y) * smoothstep(0.26, 0.40, uu)
                p.x *= 1.0 + 0.30 * fl
                p.z -= 0.0030 * S * fl
            col.append(push_out_of_sleeves(C, p, off))
        grid.append(col)
    C.cape_grid = grid
    idx = [[cg.add(p, wcape) for p in col] for col in grid]
    for i in range(NU):
        for j in range(NV):
            cg.face((idx[i][j], idx[i][j + 1], idx[i + 1][j + 1], idx[i + 1][j]), "cape", 0)

    def cape_post(pts, nrm):
        out = []
        for p in pts:
            q = p.copy()
            u = (math.atan2(p.x, p.z + 0.001) / (2 * math.pi)) % 1.0; uu = mirror_u(u)
            t = smoothstep(shY + 0.004 * S, wy, p.y) * smoothstep(0.22, 0.36, uu)
            hn = V(p.x, 0, p.z + 0.001).normalized()
            fa = 2 * math.pi * u
            q += hn * 0.0024 * S * t * (math.cos(14 * fa + 0.5) + 0.4 * math.cos(9 * fa + 1.3))
            if t > 0:
                q.y += 0.0016 * S * t * t * math.cos(14 * fa + 0.5)
            out.append(q)
        return out
    C.add("cape", cg, post=cape_post, subdiv=0, solidify=0.0009 * S)
    # ---- braid: chain of interlocking lobes from the nape over the right shoulder down the chest
    def surf_z(x, y, extra):
        hw = table(C.robe_rows, y)[0]
        a = math.asin(max(-1.0, min(1.0, x / (hw + 1e-6))))
        p = robe_point(C, y, a, 0.0)
        uu = mirror_u(a / (2 * math.pi))
        cape = 0.0029 * S if (uu > 0.12 and y > nb - 0.0035 * S - (uu - 0.12) * 0.06 * S) else 0.0
        return p.z + cape + extra
    r0 = 0.0046 * S
    hb = C.head.at(0.64, L["chin"] + 0.10 * H)
    # top of the shoulder near the neck at x
    xs = -0.0215 * S
    ysh = None
    for k in range(200):
        y = nb + 0.004 * S - k * 0.0001 * S
        if table(C.robe_rows, y)[0] >= abs(xs):
            ysh = y; break
    ysh = ysh or nb
    ctrl = [V(-0.0095 * S, L["chin"] + 0.08 * H, hb.z + 0.0010 * S),
            V(-0.0170 * S, L["chin"] - 0.03 * H, -0.0070 * S),
            V(xs, ysh + 0.0029 * S + r0 * 0.95, -0.0005 * S)]
    for x, y in ((-0.0232, 0.2450), (-0.0228, 0.2300), (-0.0215, 0.2160), (-0.0205, 0.2040)):
        x *= S / 1.0; y = y
        ctrl.append(V(x, y, surf_z(x, y, r0 * (0.95 - 0.25 * (0.245 - y) / 0.04))))
    path = [cr_open(ctrl, i / 160) for i in range(161)]
    seglen = [0.0]
    for a, b in zip(path, path[1:]):
        seglen.append(seglen[-1] + (b - a).length)
    tot = seglen[-1]

    def at(f):
        tgt = f * tot
        for i in range(len(seglen) - 1):
            if seglen[i + 1] >= tgt:
                t = (tgt - seglen[i]) / max(1e-9, seglen[i + 1] - seglen[i])
                return path[i].lerp(path[i + 1], t), (path[i + 1] - path[i]).normalized()
        return path[-1], (path[-1] - path[-2]).normalized()
    C.braid_at = at
    pB1 = at(0.10)[0]; pB2 = at(0.40)[0]; pB3 = at(0.70)[0]; pB4 = at(1.0)[0]
    C.B["braid1"] = (pB1, pB2, "head"); C.B["braid2"] = (pB2, pB3, "braid1"); C.B["braid3"] = (pB3, pB4, "braid2")
    wbr = C.w(["head", "braid1", "braid2", "braid3"], blend=0.010 * S)
    cg = Cage()
    nlobe = 15; f0, f1 = 0.10, 0.90
    sp = (f1 - f0) * tot / nlobe
    for k in range(nlobe):
        f = f0 + (f1 - f0) * (k + 0.5) / nlobe
        c, T = at(f)
        A_ = perp(V(0, 0, 1), T)
        if A_.length < 1e-6:
            A_ = perp(V(0, 1, 0), T)
        Bv = T.cross(A_).normalized()
        r = r0 * (1.0 - 0.30 * f)
        sgn = 1 if k % 2 == 0 else -1
        axis = rot_about(T, A_, math.radians(32 * sgn))
        side = axis.cross(A_).normalized()
        M = Matrix((side, axis, A_)).transposed()
        cc = c + Bv * (0.26 * r * sgn)
        blob(cg, cc, 0.70 * r, 0.98 * sp / math.cos(math.radians(32)), 0.86 * r, wbr, "hair", 1, NU=10, NV=6, ax=M)
    # bun at the nape where the braid starts, the tie and the tuft
    cb, Tb = at(0.06)
    blob(cg, cb + V(0.0025 * S, 0.0005 * S, -0.0005 * S), 0.0068 * S, 0.0062 * S, 0.0052 * S, wbr, "hair", 1, NU=10, NV=6)
    ct, Tt = at(0.915)
    Ft = frame_along([ct - Tt * 0.001, ct, ct + Tt * 0.001])
    tube(cg, [ct - Tt * 0.0016 * S, ct, ct + Tt * 0.0016 * S], [0.0026 * S, 0.0029 * S, 0.0026 * S], 10, wbr, "sash", 2,
         cap0=True, cap1=True)
    tuft = []
    for i in range(6):
        f = 0.93 + 0.07 * i / 5
        tuft.append(at(min(f, 1.0))[0] + at(min(f, 1.0))[1] * (0.004 * S * (i / 5) ** 1.5))
    tube(cg, tuft, [0.0022 * S, 0.0030 * S, 0.0036 * S, 0.0036 * S, 0.0028 * S, 0.0010 * S], 10, wbr, "hair", 1,
         cap0=True, cap1=True, cap_len=0.8)
    C.add("braid", cg, subdiv=0)
    # ---- necklace: two strands of gold beads and a lapis star pendant (rigid, chest)
    cg = Cage()

    def strand(yf, ysd, amax, n, rb, pc):
        pts = []
        for i in range(n):
            a = math.radians(-amax + 2 * amax * i / (n - 1))
            y = ysd + (yf - ysd) * (math.cos(a) - math.cos(math.radians(amax))) / (1 - math.cos(math.radians(amax)))
            uu = abs(a) / (2 * math.pi)
            covered = uu > 0.12 and y > nb - 0.0035 * S - (uu - 0.12) * 0.06 * S
            p = robe_point(C, y, a, (0.0029 * S if covered else 0.0004 * S) + rb)
            pts.append(p)
            blob(cg, p, rb, rb, rb * 0.9, None, "necklace", pc, NU=6, NV=3)
        return pts
    strand(nb - 0.0072 * S, nb + 0.0004 * S, 50, 21, 0.00100 * S, 0)
    st2 = strand(nb - 0.0122 * S, nb - 0.0010 * S, 54, 25, 0.00110 * S, 0)
    pc_ = st2[len(st2) // 2]
    star_c = pc_ + V(0, -0.0052 * S, 0.0004 * S)
    blob(cg, pc_ + V(0, -0.0018 * S, 0.0002 * S), 0.0007 * S, 0.0009 * S, 0.0007 * S, None, "necklace", 0, NU=6, NV=4)
    Ro, Ri = 0.0040 * S, 0.0018 * S
    outline = []
    for k in range(10):
        a = math.pi / 2 + k * math.pi / 5
        r = Ro if k % 2 == 0 else Ri
        outline.append((math.cos(a) * r, math.sin(a) * r))
    extrude_outline(cg, outline, 0.0012 * S, None, "pendant", 1, z0=-0.0006 * S, bevel=0.22, origin=star_c)
    C.add("necklace", cg, subdiv=0, rigid="chest")
    # ---- diadem: band on the hair + raised front point with a jewel (rigid, diadem bone)
    cg = Cage()
    yf_, yb_ = L["brow"] + 0.45 * H, L["top"] - 0.36 * H
    NB = 40; pts, nrm = [], []
    for k in range(NB):
        u = k / NB
        y = lerp(yf_, yb_, (1 - math.cos(2 * math.pi * u)) / 2)
        p = C.hair_outer(u, y); n = C.head.normal(u, min(y, L["top"] - 0.001))
        pts.append(p + n * 0.0006 * S); nrm.append(n)
    tang = [(pts[(i + 1) % NB] - pts[i - 1]).normalized() for i in range(NB)]
    wdir = [perp(V(0, 1, 0), t) for t in tang]
    band_loop(cg, pts, nrm, wdir, 0.0013 * S, 0.0006 * S, None, "diadem", 0)
    fp, fn = pts[0], nrm[0]
    up = perp(V(0, 1, 0), fn)
    outline = []
    for k in range(17):
        t = k / 16
        x = (t - 0.5) * 0.0140 * S
        hgt = 0.0125 * S * (1 - abs(2 * t - 1)) ** 1.4
        outline.append((x, hgt))
    outline += [(0.0070 * S * (1 - 2 * k / 6), -0.0013 * S) for k in range(1, 6)]
    extrude_outline(cg, outline, 0.0010 * S, None, "diadem", 0, z0=0.0002 * S, bevel=0.15, origin=fp, X=V(1, 0, 0), Y=up, Z=fn)
    blob(cg, fp + up * 0.0042 * S + fn * 0.0013 * S, 0.0018 * S, 0.0018 * S, 0.0011 * S, None, "diadem", 0, NU=8, NV=5)
    C.add("diadem", cg, subdiv=0, rigid="diadem")
    C.B["diadem"] = (fp - fn * 0.004 * S, fp - fn * 0.004 * S + V(0, 0.010 * S, 0), "head")


# =============================================================================================== Blender assembly
BUILDERS = {"esther": build_esther}
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
    stats = front_uv_with_occlusion([(o, bool(pt.get("rigid"))) for o, pt in objs], sheet, ART_H, INSET,
                                    anchors=None, region_name=lambda r: REGIONS[r - 1].split(".")[1])
    # regions / bbox report from the rest pose before joining
    rep = {"regions": {}, "parts": {}, "uvStats": stats}
    for o, pt in objs:
        me = o.data; rid = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rid)
        for poly, r in zip(me.polygons, rid):
            reg = REGIONS[r - 1].split(".")[1]
            d = rep["regions"].setdefault(reg, {"parts": set(), "bb": [9, 9, -9, -9]})
            d["parts"].add(pt["name"])
            if pt["name"] == "eyelids":
                continue
            for vi in poly.vertices:
                p = to_design(o.matrix_world @ me.vertices[vi].co)
                bb = d["bb"]; bb[0] = min(bb[0], p.x); bb[1] = min(bb[1], p.y); bb[2] = max(bb[2], p.x); bb[3] = max(bb[3], p.y)
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


# =============================================================================================== King
def build_king(C):
    s = C.s; L = C.L; H = C.H; S = C.S
    shY = s["shoulder"][1]; nb = s["neckBase"]
    cb = L["brow"] + 0.24 * H
    ey0, ey1, ew, et = ears_spec(C)

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, cb + 0.003 * S), (0.13, cb + 0.003 * S), (0.17, cb - 0.004 * S), (0.19, L["eye"] + 0.02 * H), (0.215, L["nose"]),
                      (0.232, ey1 + 0.003 * S), (0.268, ey1 + 0.003 * S), (0.30, L["mouth"]), (0.36, L["chin"] - 0.06 * H),
                      (0.50, L["chin"] - 0.14 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > cb + 0.004 * S:
            return True
        return uu > 0.17 and p.y > rim(u) + 0.0045 * S and not (0.225 < uu < 0.275 and p.y < ey1)
    skeleton(C)
    build_head(C, cull, ears=(ey0, ey1, ew, et))

    def thick(u, y):
        return (0.0034 + 0.0010 * smoothstep(L["eye"], L["chin"], y)) * S

    def curls(u, y):
        rh = 0.0058 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0011 * S * (0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh)) \
            * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 30 + ph)))

    def plumb(uu):
        return smoothstep(0.26, 0.34, uu)
    hair_shell(C, rim, thick, "hair", "beard", plumb=plumb, tuck_front=0.17, grooves=0, curls=curls, NU=40, NV=8)
    # beard (rounded, curl rows) + moustache
    top = [(0.00, L["mouth"] - 0.080 * H), (0.035, L["mouth"] - 0.065 * H), (0.07, L["mouth"] + 0.01 * H),
           (0.10, L["nose"] - 0.05 * H), (0.15, L["nose"] + 0.00 * H), (0.20, L["eye"] - 0.17 * H), (0.245, L["eye"] - 0.06 * H)]
    bot = [(0.00, L["chin"] - 0.15 * H), (0.06, L["chin"] - 0.14 * H), (0.12, L["chin"] - 0.09 * H),
           (0.17, L["chin"] + 0.00 * H), (0.21, L["mouth"] - 0.05 * H), (0.245, L["nose"] - 0.04 * H)]

    def bthick(uu, y, v):
        t = lerp(0.0058, 0.0032, smoothstep(0.05, 0.24, uu)) * S
        t *= smoothstep(0.0, 0.20, v)
        if uu < 0.06 and y > L["mouth"] - 0.10 * H:
            t *= 0.35
        return t + 0.0005 * S

    def bcurls(u, y):
        rh = 0.0055 * S; row = math.floor((y - L["chin"]) / rh)
        ph = 0.5 * (row % 2)
        return 0.0012 * S * ((0.5 + 0.5 * math.cos(2 * math.pi * (y - L["chin"]) / rh))
                             * (0.5 + 0.5 * math.cos(2 * math.pi * (u * 34 + ph))) - 0.25)
    build_beard(C, top, bot, bthick, bcurls, 0.245, L["chin"] - 0.15 * H)
    moustache(C, "moustache", L["mouth"] + 0.085 * H, 0.62 * s["hw"], 0.06 * H, 0.10 * H, 0.0022 * S, off=0.0016)
    # robe: royal purple, wide sleeves
    R = [(0.2760, 0.0128, 0.0118, -0.0125), (0.2745, 0.0195, 0.0134, -0.0142), (0.2725, 0.0285, 0.0148, -0.0155),
         (0.2705, 0.0368, 0.0158, -0.0161), (0.2690, 0.0418, 0.0163, -0.0164), (0.2675, 0.0446, 0.0166, -0.0166), (0.2620, 0.0482, 0.0182, -0.0170), (0.2540, 0.0476, 0.0202, -0.0170),
         (0.2440, 0.0460, 0.0218, -0.0168), (0.2320, 0.0442, 0.0230, -0.0162), (0.2180, 0.0432, 0.0240, -0.0160),
         (0.2040, 0.0442, 0.0236, -0.0170), (0.1900, 0.0456, 0.0230, -0.0180), (0.1600, 0.0482, 0.0232, -0.0195),
         (0.1200, 0.0512, 0.0246, -0.0210), (0.0800, 0.0546, 0.0264, -0.0228), (0.0400, 0.0580, 0.0284, -0.0245),
         (0.0110, 0.0606, 0.0300, -0.0258)]
    sleeve = [(0.004, 0.0132), (0.014, 0.0129), (0.030, 0.0119), (0.048, 0.0113), (0.062, 0.0115), (0.074, 0.0122),
              (0.085, 0.0131), (0.093, 0.0138), (0.098, 0.0141)]
    build_robe(C, [(y, hw, zf, zb) for y, hw, zf, zb in R], sleeve, None, nf=12, fold_amp=0.0025, sleeve_fold=0.0010)
    for side in "LR":
        build_forearm_hand(C, side, 0.040)
        build_leg(C, side, 0.0125 * S, "shoes")
    # gold collar (scalloped, two grooves), draped over the shoulders
    wcol = C.w(["chest", ("neck", 0.010 * S), ("shoulderL", 0.016 * S), ("shoulderR", 0.016 * S)])
    yout = [(0.00, s["chestY"] + 0.004 * S), (0.15, s["chestY"] + 0.009 * S), (0.25, shY - 0.006 * S),
            (0.35, s["chestY"] + 0.010 * S), (0.50, s["chestY"] + 0.007 * S)]
    vs = [(0.0, 0.0014), (0.06, 0.0022), (0.30, 0.0022), (0.34, 0.0016), (0.38, 0.0022), (0.64, 0.0022), (0.68, 0.0016),
          (0.72, 0.0022), (0.93, 0.0022), (1.0, 0.0016)]
    NU = 56; cg = Cage(); rings = []
    for v, off in vs:
        ring = []
        for i in range(NU):
            u = i / NU; uu = mirror_u(u)
            yo = table(yout, uu)[0] - 0.0030 * S * (0.5 + 0.5 * math.cos(2 * math.pi * 16 * u)) ** 0.7
            y = lerp(nb + 0.0030 * S, yo, v)
            ring.append(mantle_point(C, u, y, off * S, 0.0132 * S))
        rings.append(cg.ring(ring, wcol))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "collar", 0)
    C.add("collar", cg, subdiv=0, solidify=0.0010 * S, smooth=(lambda p: True, 2))
    # gold belt with a round medallion
    wy = s["waistY"]
    waist_band(C, "belt", "belt", wy - 0.0052 * S, wy + 0.0052 * S, 0.0010 * S, bulge=0.0008 * S)
    cg = Cage(); wb = C.w(["hips", "spine"])
    mc = robe_point(C, wy, 0.0, 0.0016 * S)
    lathe_z(cg, mc, [(0.0, 0.0066 * S), (0.0010 * S, 0.0070 * S), (0.0017 * S, 0.0062 * S), (0.0019 * S, 0.0046 * S),
                     (0.0016 * S, 0.0040 * S), (0.0022 * S, 0.0030 * S), (0.0028 * S, 0.0014 * S), (0.0030 * S, 0.0)],
            16, wb, lambda a, b: "belt", 1)
    C.add("medallion", cg, subdiv=0)
    # crown: tall flat-topped, three raised gold bands, rosettes on the middle band (rigid, crown bone)
    cg = Cage()
    Hc = s["height"] - cb - 0.0016 * S
    prof = [(-0.0020 * S, 0.965), (0.0, 1.0), (0.004 * S, 1.008), (0.25 * Hc, 1.035), (0.55 * Hc, 1.07), (0.85 * Hc, 1.10),
            (Hc - 0.0012 * S, 1.115), (Hc, 1.11), (Hc + 0.0008 * S, 1.02), (Hc + 0.0014 * S, 0.80), (Hc + 0.0016 * S, 0.45),
            (Hc + 0.0017 * S, 0)]
    cr = head_lathe(C, cb, prof, 32, None, "crown", 0, cg, extra_x=0.0040 * S, extra_f=0.0016 * S, extra_b=0.0050 * S)
    for dy, hgt in ((0.0042 * S, 0.0062 * S), (0.50 * Hc, 0.0066 * S), (Hc - 0.0042 * S, 0.0058 * S)):
        k = table([(p[0], p[1]) for p in prof if p[1] > 0], dy)[0]
        rings = []
        for yy, kk in ((-hgt / 2, k + 0.002), (-hgt / 2 + 0.0006 * S, k + 0.030), (hgt / 2 - 0.0006 * S, k + 0.030), (hgt / 2, k + 0.002)):
            rings.append(cg.ring([V(se(math.sin(2 * math.pi * j / 36), 2.3) * cr["rx"] * kk, cb + dy + yy,
                                    cr["zc"] + se(math.cos(2 * math.pi * j / 36), 2.3) * cr["rz"] * kk) for j in range(36)], None))
        for a, b in zip(rings, rings[1:]):
            cg.bridge(a, b, "crownBands", 1)
    dym = 0.50 * Hc; km = table([(p[0], p[1]) for p in prof if p[1] > 0], dym)[0] + 0.03
    for k in range(-3, 4):
        u = k * 0.085
        a = 2 * math.pi * u
        c = V(se(math.sin(a), 2.3) * cr["rx"] * km, cb + dym, cr["zc"] + se(math.cos(a), 2.3) * cr["rz"] * km)
        nrm = V(math.sin(a), 0, math.cos(a)).normalized()
        X = V(0, 1, 0).cross(nrm).normalized(); Y = V(0, 1, 0)
        outline = [(math.cos(2 * math.pi * j / 16) * 0.0034 * S * (0.62 + 0.38 * (j % 2 == 0)),
                    math.sin(2 * math.pi * j / 16) * 0.0034 * S * (0.62 + 0.38 * (j % 2 == 0))) for j in range(16)]
        extrude_outline(cg, outline, 0.0010 * S, None, "crownBands", 2, z0=0.0, bevel=0.0, origin=c, X=X, Y=Y, Z=nrm)
        blob(cg, c + nrm * 0.0012 * S, 0.0011 * S, 0.0011 * S, 0.0007 * S, None, "crownBands", 2, NU=8, NV=4,
             ax=Matrix((X, Y, nrm)).transposed())
    C.add("crown", cg, subdiv=0, rigid="crown")
    C.B["crown"] = (V(0, cb, cr["zc"]), V(0, s["height"], cr["zc"]), "head")
    # sceptre in the right fist: staff, collars, knob, small wings (rigid, sceptre bone; sceptreTip at the knob)
    A = C.arm["R"]; hd = s["handDims"]
    axis = A["Yh"] if A["Yh"].y > 0 else -A["Yh"]
    grip = A["K"] - A["dh"] * (0.18 * s["hand"] * s["palmFrac"]) + A["Np"] * (hd["palmH"] * 0.5 + 0.0034 * S)
    cg = Cage()
    prof = [(-0.046, 0.0), (-0.0455, 0.0022), (-0.0440, 0.0034), (-0.0415, 0.0030), (-0.0395, 0.0024), (-0.016, 0.0024),
            (-0.0145, 0.0031), (-0.0130, 0.0024), (0.0130, 0.0024), (0.0145, 0.0031), (0.0160, 0.0024), (0.0860, 0.0024),
            (0.0880, 0.0036), (0.0905, 0.0036), (0.0925, 0.0028), (0.0945, 0.0042), (0.0965, 0.0064), (0.0995, 0.0080),
            (0.1035, 0.0086), (0.1075, 0.0080), (0.1105, 0.0064), (0.1125, 0.0042), (0.1137, 0.0018), (0.1140, 0.0)]
    pts = [grip + axis * (t * S) for t, r in prof]
    rads = [max(r, 0.0004) * S for t, r in prof]
    tube(cg, pts[1:-1], rads[1:-1], 12, None, "sceptre", 0, ref=V(0, 0, 1), cap0=True, cap1=True, cap_len=0.3)
    side = axis.cross(V(0, 0, 1)).normalized()
    wing = [(0.0026, 0.0060), (0.0060, 0.0085), (0.0110, 0.0108), (0.0165, 0.0125), (0.0215, 0.0130), (0.0235, 0.0118),
            (0.0215, 0.0098), (0.0228, 0.0080), (0.0200, 0.0064), (0.0205, 0.0046), (0.0170, 0.0034), (0.0168, 0.0016),
            (0.0125, 0.0010), (0.0080, 0.0006), (0.0026, 0.0000)]
    base = grip + axis * (0.0815 * S)
    for sg in (1, -1):
        outline = [(sg * x * S, y * S) for x, y in wing]
        if sg < 0:
            outline = list(reversed(outline))
        extrude_outline(cg, outline, 0.0017 * S, None, "sceptre", 0, z0=-0.00085 * S, bevel=0.10, origin=base, X=side, Y=axis,
                        Z=side.cross(axis).normalized() * (1 if side.cross(axis).z > 0 else -1))
    C.add("sceptre", cg, subdiv=0, rigid="sceptre")
    knob = grip + axis * (0.1035 * S)
    C.B["sceptre"] = (grip.copy(), knob.copy(), "handR")
    C.B["sceptreTip"] = (knob.copy(), knob + axis * 0.012 * S, "sceptre")
    finger_ring(C, "R", "ring")


# =============================================================================================== Haman
def build_haman(C):
    s = C.s; L = C.L; H = C.H; S = C.S
    shY = s["shoulder"][1]; nb = s["neckBase"]
    capb = L["brow"] + 0.17 * H
    ey0, ey1, ew, et = ears_spec(C)

    def rim(u):
        uu = mirror_u(u)
        return table([(0.00, capb + 0.003 * S), (0.13, capb + 0.003 * S), (0.17, capb - 0.003 * S), (0.195, L["eye"] + 0.04 * H),
                      (0.215, L["nose"] + 0.06 * H), (0.232, ey1 + 0.003 * S), (0.268, ey1 + 0.003 * S),
                      (0.30, L["nose"]), (0.36, L["chin"] + 0.10 * H), (0.50, L["chin"] + 0.04 * H)], uu)[0]

    def cull(p):
        u = head_u(C, p); uu = mirror_u(u)
        if p.y < nb - 0.0060 * S or p.y > capb + 0.004 * S:
            return True
        return uu > 0.17 and p.y > rim(u) + 0.0040 * S and not (0.225 < uu < 0.275 and p.y < ey1)
    skeleton(C)
    build_head(C, cull, ears=(ey0, ey1, ew * 1.05, et))

    def thick(u, y):
        return 0.0022 * S
    hair_shell(C, rim, thick, "hair", "beard", plumb=None, tuck_front=0.17, grooves=48, groove_amp=0.00022, NU=36, NV=7)
    # pointed goatee + thin moustache with upturned tips
    zc = L["zc"]
    p0, n0 = head_surface(C, 0.0, L["mouth"] - 0.075 * H, 0.0008 * S)
    p1, n1 = head_surface(C, 0.0, L["chin"] + 0.10 * H, 0.0016 * S)
    p2, n2 = head_surface(C, 0.0, L["chin"] + 0.01 * H, 0.0020 * S)
    p3 = p2 + V(0, -0.0085 * S, 0.0030 * S); p4 = p2 + V(0, -0.0175 * S, 0.0062 * S)
    path = [cr_open([p0, p1, p2, p3, p4], t / 10) for t in range(11)]
    rad = [(lerp(0.0011, 0.0019, min(1, t / 3)) * S * (1 - 0.85 * smoothstep(0.55, 1.0, t / 10)),
            lerp(0.0040, 0.0048, min(1, t / 3)) * S * (1 - 0.90 * smoothstep(0.45, 1.0, t / 10))) for t in range(11)]
    cg = Cage()
    tube(cg, path, rad, 10, C.w(["head"]), "beard", 0, cap0=True, cap1=True, cap_len=0.8)
    C.add("goatee", cg, subdiv=0, decal=True, jaw=True, jawBelow=0.9, jawZ=-0.05)
    moustache(C, "moustache", L["mouth"] + 0.075 * H, 0.66 * s["hw"], 0.05 * H, 0.16 * H, 0.0012 * S, off=0.0012)
    # robe: wine red with mustard front panel, hem band and cuffs
    R = [(0.2790, 0.0105, 0.0095, -0.0100), (0.2775, 0.0158, 0.0110, -0.0118), (0.2755, 0.0236, 0.0122, -0.0128),
         (0.2738, 0.0306, 0.0128, -0.0132), (0.2724, 0.0350, 0.0131, -0.0134), (0.2712, 0.0372, 0.0133, -0.0135), (0.2650, 0.0400, 0.0140, -0.0138), (0.2560, 0.0385, 0.0150, -0.0136),
         (0.2480, 0.0365, 0.0155, -0.0132), (0.2360, 0.0330, 0.0150, -0.0125), (0.2240, 0.0305, 0.0142, -0.0120),
         (0.2100, 0.0320, 0.0150, -0.0135), (0.1960, 0.0345, 0.0165, -0.0155), (0.1600, 0.0375, 0.0185, -0.0172),
         (0.1200, 0.0405, 0.0205, -0.0190), (0.0800, 0.0440, 0.0228, -0.0208), (0.0400, 0.0475, 0.0252, -0.0225),
         (0.0110, 0.0500, 0.0270, -0.0238)]
    sleeve = [(0.004, 0.0113), (0.014, 0.0111), (0.030, 0.0101), (0.048, 0.0095), (0.064, 0.0098), (0.078, 0.0104),
              (0.092, 0.0111), (0.102, 0.0119), (0.108, 0.0123)]
    cg = build_robe(C, R, sleeve, None, nf=10, fold_amp=0.0021, sleeve_fold=0.0008)
    hem = R[-1][0]; LU, LF = s["upperArm"], s["forearm"]
    for fi, q in enumerate(cg.f):
        cen = sum((cg.v[i] for i in q), V()) / len(q)
        reg = cg.reg[fi]
        sl = None
        for side in "LR":
            A = C.arm[side]; sv = (cen - A["S0"]).dot(A["d"])
            if sv > 0.004 * S and (cen - (A["S0"] + A["d"] * sv)).length < 0.03 * S:
                sl = sv
        if sl is not None:
            if sl > 0.093 * S:
                cg.reg[fi] = "panels"; cg.pc[fi] = 2
        else:
            a = math.atan2(cen.x, cen.z + 0.001)
            if cen.y < hem + 0.0105 * S:
                cg.reg[fi] = "panels"; cg.pc[fi] = 3
            elif abs(a) < math.radians(12) and cen.z > 0 and cen.y < nb - 0.002 * S:
                cg.reg[fi] = "panels"; cg.pc[fi] = 4
    for side in "LR":
        build_forearm_hand(C, side, 0.040)
        build_leg(C, side, 0.0125 * S, "shoes", pointy=1.0)
    wy = s["waistY"]
    waist_band(C, "sash", "panels", wy - 0.0048 * S, wy + 0.0048 * S, 0.0011 * S, pc=5, bulge=0.0009 * S)
    # cap: dark teal round cap, gold rim (rigid, cap bone)
    cg = Cage()
    Hc = s["height"] - capb
    prof = [(-0.0015 * S, 0.97), (0.0, 1.0), (0.18 * Hc, 1.035), (0.45 * Hc, 1.05), (0.70 * Hc, 1.02), (0.86 * Hc, 0.92),
            (0.95 * Hc, 0.72), (0.99 * Hc, 0.40), (Hc, 0)]
    cp = head_lathe(C, capb, prof, 32, None, "cap", 0, cg, extra_x=0.0030 * S, extra_f=0.0012 * S, extra_b=0.0035 * S,
                    e=2.1, tilt=math.radians(8))
    rings = []
    for yy, kk in ((-0.0010 * S, 1.005), (-0.0004 * S, 1.040), (0.0044 * S, 1.040), (0.0050 * S, 1.010)):
        pts = [V(se(math.sin(2 * math.pi * j / 48), 2.1) * cp["rx"] * kk, capb + yy,
                 cp["zc"] + se(math.cos(2 * math.pi * j / 48), 2.1) * cp["rz"] * kk) for j in range(48)]
        rings.append(cg.ring([cp["pivot"] + cp["R"] @ (p - cp["pivot"]) for p in pts], None))
    for a, b in zip(rings, rings[1:]):
        cg.bridge(a, b, "capRim", 1)
    C.add("cap", cg, subdiv=0, rigid="cap")
    C.B["cap"] = (V(0, capb, cp["zc"]), V(0, s["height"], cp["zc"]), "head")
    finger_ring(C, "L", "ring")


BUILDERS.update({"king": build_king, "haman": build_haman})


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
    m = bpy.data.materials.get("es_page") or bpy.data.materials.new("es_page")
    m.diffuse_color = (1, 1, 1, 1)
    return m


def all_meshes():
    return [o for o in sc().objects if o.type == 'MESH']


def apply_pixel_anchors(id_png, ids):
    """Regions too small to colour (ANCHORS) get one constant UV0: the deepest pixel (farthest from any other
    region / the paper) of the target region in the front ID render, i.e. the middle of the widest printed patch."""
    import numpy as np
    img = bpy.data.images.load(id_png, check_existing=False)
    W, H = img.size
    px = np.array(img.pixels[:], dtype=np.float32).reshape(H, W, 4)          # rows bottom -> top
    rgb = np.round(px[..., :3] * 255).astype(np.int32)
    key = rgb[..., 0] * 65536 + rgb[..., 1] * 256 + rgb[..., 2]
    alpha = px[..., 3] > 0.5
    out = {}
    for ch, regs in ANCHORS.items():
        if ch not in ONLY:
            continue
        for reg, target in regs.items():
            keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids if e["char"] == ch and e["region"] == target]
            mask = np.isin(key, keys) & alpha
            if not mask.any():
                continue
            last = mask
            m = mask.copy()
            while m.any():
                last = m
                e = m.copy()
                e[1:, :] &= m[:-1, :]; e[:-1, :] &= m[1:, :]; e[:, 1:] &= m[:, :-1]; e[:, :-1] &= m[:, 1:]
                m = e
            ys, xs = np.nonzero(last)
            cy, cx = ys.mean(), xs.mean()
            k = int(np.argmin((ys - cy) ** 2 + (xs - cx) ** 2))
            uv = ((xs[k] + 0.5) / W, (ys[k] + 0.5) / H)
            out.setdefault(ch, {})[reg] = [round(uv[0], 5), round(uv[1], 5)]
            rid = REGIONS.index(f"{ch}.{reg}") + 1
            for o in all_meshes():
                if not o.name.startswith(ch + "_"):
                    continue
                me = o.data; rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
                uv0 = me.uv_layers["UVMap"]
                for poly, r in zip(me.polygons, rr):
                    if r == rid:
                        for li in poly.loop_indices:
                            uv0.data[li].uv = uv
    # ---- part anchors
    for ch, pa in PART_ANCHORS.items():
        if ch not in ONLY:
            continue
        F = face_layout(ch); L = landmarks(ch); Hh = L["top"] - L["chin"]; hw = SPEC[ch]["hw"]
        sX, sY = SHEET[ch]
        for (part, reg), target in pa.items():
            if target == "FACE":
                keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids
                        if e["char"] == ch and e["part"] == "face" and e["region"] == "skin"]
                mask = np.isin(key, keys) & alpha
                yy, xx = np.mgrid[0:H, 0:W]
                lx = (xx + 0.5) / W - 0.5 - sX; ly = (yy + 0.5) / H * ART_H - sY        # character-local
                ex, ey, ew, eh = F["eyeLocal"]
                feat = (np.abs(np.abs(lx) - ex) < ew * 1.7) & (ly > ey - eh * 2.2) & (ly < L["brow"] + 0.16 * Hh)
                feat |= (np.abs(lx) < 0.42 * hw) & (np.abs(ly - L["mouth"]) < 0.13 * Hh)
                feat |= (np.abs(lx) < 0.26 * hw) & (ly > L["nose"] - 0.07 * Hh) & (ly < ey)
                mask &= ~feat
            else:
                keys = [e["rgb"][0] * 65536 + e["rgb"][1] * 256 + e["rgb"][2] for e in ids
                        if e["char"] == ch and e["region"] == target]
                mask = np.isin(key, keys) & alpha
            if not mask.any():
                print("PART ANCHOR: empty target", ch, part, reg, target); continue
            last = mask; m = mask.copy()
            while m.any():
                last = m
                e = m.copy()
                e[1:, :] &= m[:-1, :]; e[:-1, :] &= m[1:, :]; e[:, 1:] &= m[:, :-1]; e[:, :-1] &= m[:, 1:]
                m = e
            ys, xs = np.nonzero(last)
            k = int(np.argmin((ys - ys.mean()) ** 2 + (xs - xs.mean()) ** 2))
            uv = ((xs[k] + 0.5) / W, (ys[k] + 0.5) / H)
            out.setdefault(ch, {})[f"{part}.{reg}"] = {"target": "face skin" if target == "FACE" else target,
                                                      "uv": [round(uv[0], 5), round(uv[1], 5)],
                                                      "local": [round(uv[0] - 0.5 - sX, 4), round(uv[1] * ART_H - sY, 4)]}
            rid = REGIONS.index(f"{ch}.{reg}") + 1
            for o in all_meshes():
                if not o.name.startswith(ch + "_"):
                    continue
                me = o.data; rr = [0] * len(me.polygons); me.attributes["st_region"].data.foreach_get("value", rr)
                pid = [0] * len(me.polygons); me.attributes["st_piece"].data.foreach_get("value", pid)
                uv0 = me.uv_layers["UVMap"]
                for poly, r, pp in zip(me.polygons, rr, pid):
                    if r == rid and PIECES[pp - 1][1] == part:
                        for li in poly.loop_indices:
                            uv0.data[li].uv = uv
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
        skip = set(ANCHORS.get(ch, {}).keys())
        pskip = set(PART_ANCHORS.get(ch, {}).keys())
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
        o.hide_render = o.name.endswith("_eyelids")

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
    regions_out = {"version": 1, "generatedBy": "pipeline/es_characters.py",
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
            an = ANCHORS.get(ch, {}).get(reg)
            if an:
                regs[reg]["anchoredTo"] = an
                regs[reg]["anchorUV"] = anchor_info.get(ch, {}).get(reg)
                regs[reg]["printNote"] = "too small to colour; print as detail line art, takes the colour of " + an
        regions_out["characters"][ch] = {
            "height": SPEC[ch]["height"], "bboxSheet": [round(v, 4) for v in allbb], "regions": regs,
            "faceDecal": {"rectLocal": [round(v, 5) for v in C.F["rect"]], "px": 512, "default": DEFAULT_EXPR[ch],
                          "files": {e: f"docs/esther/design/faces/{ch}_{e}.png" for e in EXPRESSIONS[ch]},
                          "clipExpression": CLIP_EXPRESSION[ch]},
            "blink": {"bone": "eyelids", "axis": "local Y (along the bone, pointing down)", "open": 1.0,
                      "closed": C.lid["closedScale"], "note": "scale the bone's Y; X/Z stay 1"},
            "restPose": {"armDegBelowHorizontal": ARM_DEG, "facing": "+Z"},
            "partAnchors": {k: v for k, v in anchor_info.get(ch, {}).items() if "." in k}}
    json.dump(regions_out, open(os.path.join(MODEL, "regions_characters.json"), "w"), indent=1, ensure_ascii=False)
    if SHEET_SRC == "defaults":
        json.dump({"note": "default sheet positions used by es_characters.py (assets/esther/design.json had none); the "
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
    sc()["es_regions"] = json.dumps(REGIONS)
    bpy.context.preferences.filepaths.save_version = 0
    bpy.ops.wm.save_as_mainfile(filepath=BLEND, compress=True)
    print("BUILD_REPORT", json.dumps({ch: {k: v for k, v in r.items() if k != "bones"} for ch, r in report["chars"].items()}))


GOLD = {"sash", "diadem", "necklace", "collar", "belt", "crownBands", "sceptre", "capRim", "ring"}


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

    def show(chs):
        for o in all_meshes():
            if o.name not in ("floor", "backdrop"):
                o.hide_render = o.name.split("_")[0] not in chs
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
        tab = json.loads(sc().get("es_regions", "[]"))
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
        bend(rig, "fingers" + side, hz * (1 if side == "L" else -1), 75 if not (ch == "king" and side == "R") else -55)
    bend(rig, "upperArmL", V(1, 0, 0), -45)
    bend(rig, "thighL", V(1, 0, 0), -30); bend(rig, "shinL", V(1, 0, 0), 50)
    bend(rig, "spine", V(1, 0, 0), 10); bend(rig, "head", V(0, 1, 0), 25); bend(rig, "jaw", V(1, 0, 0), 14)
    pb = rig.pose.bones["eyelids"]; pb.scale = (1, 6.0, 1)
    if ch == "esther":
        bend(rig, "braid2", V(0, 0, 1), 18); bend(rig, "cape2", V(1, 0, 0), -20)
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
                o.hide_render = o.name.split("_")[0] != ch
        rig = bpy.data.objects[f"{ch}_rig"]; Hh = SPEC[ch]["height"]
        for nm, yaw in (("a", 20), ("b", 70)):
            turntable(cam, Vector((rig.location.x, 0, rig.location.z + Hh * 0.5)), yaw, Hh * 3.1, Hh * 0.18, 60)
            render(os.path.join(WORK, f"pose_{ch}_{nm}.png"))
    print("POSETEST done")


def mode_uvcheck():
    """Models wearing $ES_WORK/uvproof.png (or $ES_UV_TEXTURE) through UV0: front ortho (must equal the sheet) and
    3/4 + back perspective (back of the cape / robe behind the braid take their own region's colour)."""
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    tex_path = os.environ.get("ES_UV_TEXTURE") or os.path.join(WORK, "uvproof.png")
    img = bpy.data.images.load(tex_path, check_existing=True)
    m = bpy.data.materials.new("uvproof"); m.use_nodes = True
    nt = m.node_tree; b = nt.nodes.get("Principled BSDF"); b.inputs["Roughness"].default_value = 0.8
    t = nt.nodes.new("ShaderNodeTexImage"); t.image = img; t.interpolation = 'Linear'
    uvn = nt.nodes.new("ShaderNodeUVMap"); uvn.uv_map = "UVMap"
    nt.links.new(uvn.outputs["UV"], t.inputs["Vector"]); nt.links.new(t.outputs["Color"], b.inputs["Base Color"])
    for o in all_meshes():
        o.data.materials.clear(); o.data.materials.append(m)
        o.hide_render = o.name.endswith("_eyelids")
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
