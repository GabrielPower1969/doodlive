#!/usr/bin/env python3
"""Build the "how to play" demo video shown on the DoodLive home page.

Story: blank sheet -> colour it in -> scan it with the phone -> the story comes alive in 3D, seen from many angles.
Material is the Ruth pack (read-only): print/ruth-A4.png, assets/ruth/sheet/{demo-colored,regions,textured_phone_play}.png,
assets/ruth/sheet/regions.json + template.json, and three short clips of the on-device recording
unity/Builds/demo-ruth-d0ecee9-dirty.20261114-0012.mp4.

Output: unity/Assets/StreamingAssets/howto/howto.mp4  (720x1280 portrait, 30 fps, H.264 yuv420p + faststart,
AAC 96 kbps, ~32 s, burned-in bilingual captions, music + sfx at -18 LUFS integrated).

Deterministic: every random choice uses a fixed seed; the music and sound effects are synthesised here (no samples).
Intermediates go to /tmp/howto_work (deleted at the end unless --keep).

Usage: python3 tools/howto/make_howto.py [--out PATH] [--keep] [--stills DIR]
Needs: python3 with pillow, numpy, scipy, fonttools; ffmpeg on PATH.
"""
import argparse, json, math, os, shutil, subprocess, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont
from scipy import signal
from scipy.io import wavfile

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SHEET = f"{ROOT}/assets/ruth/sheet"
REC = f"{ROOT}/unity/Builds/demo-ruth-d0ecee9-dirty.20261114-0012.mp4"
FONTS = f"{ROOT}/unity/Assets/DoodLive/Resources/Fonts"
OUT = f"{ROOT}/unity/Assets/StreamingAssets/howto/howto.mp4"
WORK = "/tmp/howto_work"

W, H, FPS = 720, 1280, 30
DUR = 32.0
SR = 44100
LUFS = -18.0

# Paper & Crayon tokens (docs/DESIGN-DIRECTION.md)
PAPER, SHADE, DEEP = (251, 245, 230), (241, 230, 204), (228, 211, 174)
INK, SOFT_INK = (43, 33, 24), (107, 91, 74)
CRAYONS = [(232, 85, 61), (245, 154, 47), (255, 201, 60), (77, 179, 122), (75, 163, 227), (244, 154, 193), (138, 111, 209)]
OK_GREEN, BRAND = (63, 179, 107), (0, 143, 255)

# ---------------------------------------------------------------- timeline (seconds)
T_COLOR = (4.3, 11.3)          # colouring sweep
T_TILT = (12.0, 12.8)          # flat sheet -> lying on the desk
T_PHONE_IN = (12.3, 13.3)
T_CORNERS = [13.7, 14.0, 14.3, 14.6]
T_FOUND = 15.0
T_RISE = (17.0, 19.0)
T_ZOOM = (19.0, 20.0)
CLIPS = [  # (out_start, out_end, src_start, crop x, y, w, h)  crop aspect = 720/1020
    (19.6, 23.6, 5.0, 0, 430, 1080, 1530),     # whole page, camera drifting round the front
    (23.2, 27.2, 183.6, 0, 400, 1080, 1530),   # wedding arch, strong orbit
    (26.8, 31.0, 213.4, 0, 330, 1080, 1530),   # golden rays, orbit to the side
]
XF = 0.4
T_END = 30.2                   # end card fades in
CAPTIONS = [  # (start, end, step, zh, en)
    (0.0, 4.0, 1, "打印涂色纸", "Print the colouring sheet"),
    (4.0, 12.0, 2, "涂上你喜欢的颜色", "Colour it in, any colours you like"),
    (12.0, 17.0, 3, "用手机扫一扫", "Scan it with the app"),
    (17.0, 20.0, 4, "故事活起来了！", "Watch it come alive!"),
    (20.0, T_END, 4, "前后左右看一看", "Move around, see it from every side"),
]
HINT = (12.9, 17.0, "四个黑角都拍进来", "Keep all 4 black corners in view")
FOUND_TXT = ("找到了！", "Found it!")
END_TXT = ("开始吧！", "Let's go!")


def ease_out(x):
    x = min(max(x, 0.0), 1.0)
    return 1 - (1 - x) ** 3


def ease_io(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3 - 2 * x)


def back_out(x, s=1.7):
    x = min(max(x, 0.0), 1.0) - 1
    return 1 + x * x * ((s + 1) * x + s)


def prog(t, a, b):
    return min(max((t - a) / (b - a), 0.0), 1.0)


def font(name, size):
    return ImageFont.truetype(f"{FONTS}/{name}", size)


def check_glyphs():
    """The bundled Chinese font is a subset: fail loudly if any caption glyph is missing."""
    from fontTools.ttLib import TTFont
    zh = "".join(c[3] for c in CAPTIONS) + HINT[2] + FOUND_TXT[0] + END_TXT[0]
    en = "".join(c[4] for c in CAPTIONS) + HINT[3] + FOUND_TXT[1] + END_TXT[1] + "DoodLive0123456789"
    for fname, text in (("ZCOOLKuaiLe-Regular.ttf", zh), ("Fredoka-SemiBold.ttf", en),
                        ("Grandstander-Black.ttf", "DoodLive")):
        cmap = TTFont(f"{FONTS}/{fname}").getBestCmap()
        missing = sorted({c for c in text if not c.isspace() and ord(c) not in cmap})
        if missing:
            sys.exit(f"{fname} lacks glyphs: {''.join(missing)}")


# ---------------------------------------------------------------- geometry helpers
def homography(src, dst):
    """3x3 H with dst ~ H @ src (4 point pairs)."""
    A, b = [], []
    for (x, y), (u, v) in zip(src, dst):
        A += [[x, y, 1, 0, 0, 0, -u * x, -u * y], [0, 0, 0, x, y, 1, -v * x, -v * y]]
        b += [u, v]
    h = np.linalg.solve(np.array(A, float), np.array(b, float))
    return np.append(h, 1).reshape(3, 3)


def apply_h(Hm, pts):
    out = []
    for x, y in pts:
        p = Hm @ np.array([x, y, 1.0])
        out.append((p[0] / p[2], p[1] / p[2]))
    return out


def warp(img, quad, size):
    """Warp an RGBA image so its corners land on quad (TL, TR, BR, BL) in a canvas of `size`."""
    w, h = img.size
    Hinv = homography(quad, [(0, 0), (w, 0), (w, h), (0, h)])
    coeffs = (Hinv / Hinv[2, 2]).flatten()[:8]
    return img.transform(size, Image.PERSPECTIVE, tuple(coeffs), Image.BICUBIC)


def rounded_mask(size, r, scale=3):
    m = Image.new("L", (size[0] * scale, size[1] * scale), 0)
    ImageDraw.Draw(m).rounded_rectangle([0, 0, m.width - 1, m.height - 1], r * scale, fill=255)
    return m.resize(size, Image.LANCZOS)


def star(draw, cx, cy, r, color, rot=0.0, outline=INK, width=2):
    pts = []
    for i in range(10):
        a = rot + i * math.pi / 5 - math.pi / 2
        rr = r if i % 2 == 0 else r * 0.45
        pts.append((cx + rr * math.cos(a), cy + rr * math.sin(a)))
    draw.polygon(pts, fill=color, outline=outline, width=width)


# ---------------------------------------------------------------- static art
def make_desk():
    rng = np.random.default_rng(7)
    y = np.linspace(0, 1, H)[:, None]
    base = np.array(DEEP, float) * (1 - 0.18 * y) + np.array(SHADE, float) * 0.18 * y
    img = np.repeat(base[:, None, :], W, axis=1).reshape(H, W, 3)
    # soft wood grain: horizontal low-frequency streaks
    streak = np.cumsum(rng.normal(0, 1, (H, 1)), axis=0)
    streak = (streak - streak.mean()) / (streak.std() + 1e-6)
    grain = signal.sosfiltfilt(signal.butter(2, 0.02, output="sos"), rng.normal(0, 1, (H, W)), axis=1)
    img += (streak * 3.0 + grain * 40.0)[..., None] * np.array([1.0, 0.85, 0.6])
    yy, xx = np.mgrid[0:H, 0:W]
    vig = 1 - 0.18 * (((xx - W / 2) / W) ** 2 + ((yy - H / 2) / H) ** 2) * 2
    img *= vig[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))


def make_pages(width):
    """Blank and coloured A4 page (RGBA) at display width, plus the region-id map and template info."""
    tpl = json.load(open(f"{SHEET}/template.json"))
    blank = Image.open(f"{ROOT}/print/ruth-A4.png").convert("RGB")
    col_art = np.array(Image.open(f"{SHEET}/demo-colored.png").convert("RGB"))
    reg_art = np.array(Image.open(f"{SHEET}/regions.png"))
    ax, ay, aw, ah = tpl["art"]
    page = np.array(blank)
    full_reg = np.zeros(page.shape[:2], np.uint8)
    full_reg[ay:ay + ah, ax:ax + aw] = reg_art
    colored = page.copy()
    sub = colored[ay:ay + ah, ax:ax + aw]
    sub[reg_art > 0] = col_art[reg_art > 0]
    PW, PH = tpl["page"]
    height = round(width * PH / PW)
    b = Image.fromarray(page).resize((width, height), Image.LANCZOS)
    c = Image.fromarray(colored).resize((width, height), Image.LANCZOS)
    r = np.array(Image.fromarray(full_reg).resize((width, height), Image.NEAREST))
    return b, c, r, tpl


def color_groups(reg, ids):
    """Group region ids by (character, drawing), order top-to-bottom; per group pixel indices and sweep coordinate."""
    meta = {d["id"]: d for d in ids}
    keys = {}
    for rid in np.unique(reg):
        if rid == 0 or rid not in meta:
            continue
        d = meta[rid]
        keys.setdefault((d["char"], d["part"]), []).append(int(rid))
    groups = []
    flat = reg.ravel()
    for key, rids in keys.items():
        idx = np.flatnonzero(np.isin(flat, rids))
        if idx.size < 30:
            continue
        ys, xs = np.divmod(idx, reg.shape[1])
        x0, x1 = xs.min(), xs.max()
        u = (xs - x0) / max(1, x1 - x0)
        hexc = meta[rids[0]]["hex"]
        color = tuple(int(hexc[i:i + 2], 16) for i in (1, 3, 5))
        groups.append(dict(idx=idx, u=u, x0=x0, x1=x1, cy=float(np.median(ys)), y0=ys.min(), y1=ys.max(),
                           color=color, n=idx.size))
    # merge tiny groups into neighbours by sorting; order by row band then x
    groups.sort(key=lambda g: (round(g["cy"] / 60), g["x0"]))
    return groups


def crayon_sprite(color, scale=3, angle=35):
    """Crayon leaning to the upper right; returns (sprite, tip offset from its top-left)."""
    w, h = 26 * scale, 120 * scale
    o = 4 * scale
    im = Image.new("RGBA", (w + 2 * o, h + 2 * o), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    tip = 26 * scale
    body = h - tip
    dark = tuple(int(c * 0.7) for c in color)
    d.rounded_rectangle([o, o, o + w, o + body], 5 * scale, fill=color, outline=INK, width=2 * scale)
    d.rectangle([o + 2 * scale, o + 18 * scale, o + w - 2 * scale, o + body - 22 * scale], fill=dark)
    d.rectangle([o + 2 * scale, o + 30 * scale, o + w - 2 * scale, o + body - 34 * scale], fill=PAPER)
    d.polygon([(o + w * 0.18, o + body), (o + w * 0.82, o + body), (o + w * 0.5, o + h)], fill=color, outline=INK, width=2 * scale)
    L = (o + h) - im.height / 2
    im = im.rotate(-angle, expand=True, resample=Image.BICUBIC)
    phi = math.radians(angle)
    tx, ty = im.width / 2 - L * math.sin(phi), im.height / 2 + L * math.cos(phi)
    im = im.resize((im.width // scale, im.height // scale), Image.LANCZOS)
    return im, (tx / scale, ty / scale)


def caption_card(step, zh, en):
    f_zh, f_en, f_num = font("ZCOOLKuaiLe-Regular.ttf", 58), font("Fredoka-SemiBold.ttf", 30), font("Fredoka-SemiBold.ttf", 44)
    cw, ch = 660, 168
    im = Image.new("RGBA", (cw + 12, ch + 14), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3, 9, cw + 3, ch + 9], 30, fill=INK)                       # lip
    d.rounded_rectangle([3, 3, cw + 3, ch + 3], 30, fill=PAPER, outline=INK, width=3)
    cx, cy, r = 70, ch // 2 + 3, 44
    d.ellipse([cx - r, cy - r + 4, cx + r, cy + r + 4], fill=INK)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=BRAND, outline=INK, width=3)
    d.text((cx, cy + 1), str(step), font=f_num, fill="white", anchor="mm")
    tx = 134
    zw = d.textlength(zh, font=f_zh)
    zh_size = 58 if zw <= cw - tx - 20 else int(58 * (cw - tx - 20) / zw)
    d.text((tx, 70), zh, font=font("ZCOOLKuaiLe-Regular.ttf", zh_size), fill=INK, anchor="ls")
    ew = d.textlength(en, font=f_en)
    en_font = f_en if ew <= cw - tx - 20 else font("Fredoka-SemiBold.ttf", int(30 * (cw - tx - 20) / ew))
    d.text((tx, 128), en, font=en_font, fill=SOFT_INK, anchor="ls")
    return im


def chip(zh, en, fill=PAPER, fg=INK, fg2=SOFT_INK, zh_size=34, en_size=22, pad=22):
    f_zh, f_en = font("ZCOOLKuaiLe-Regular.ttf", zh_size), font("Fredoka-SemiBold.ttf", en_size)
    tmp = ImageDraw.Draw(Image.new("RGB", (1, 1)))
    w = int(max(tmp.textlength(zh, font=f_zh), tmp.textlength(en, font=f_en))) + 2 * pad
    h = zh_size + en_size + 2 * pad - 4
    im = Image.new("RGBA", (w + 8, h + 12), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([3, 8, w + 3, h + 8], h // 3, fill=INK)
    d.rounded_rectangle([3, 3, w + 3, h + 3], h // 3, fill=fill, outline=INK, width=3)
    d.text((w // 2 + 3, pad + zh_size - 4), zh, font=f_zh, fill=fg, anchor="ms")
    d.text((w // 2 + 3, pad + zh_size + en_size + 2), en, font=f_en, fill=fg2, anchor="ms")
    return im


def logo():
    f = font("Grandstander-Black.ttf", 118)
    letters = "DoodLive"
    tiles = []
    rng = np.random.default_rng(3)
    for i, ch in enumerate(letters):
        col = CRAYONS[i % len(CRAYONS)]
        t = Image.new("RGBA", (150, 170), (0, 0, 0, 0))
        d = ImageDraw.Draw(t)
        d.text((75, 98), ch, font=f, fill=INK, anchor="mm", stroke_width=6, stroke_fill=INK)    # lip
        d.text((75, 90), ch, font=f, fill=col, anchor="mm", stroke_width=5, stroke_fill=INK)
        t = t.rotate(float(rng.uniform(-6, 6)), resample=Image.BICUBIC)
        adv = d.textlength(ch, font=f)
        tiles.append((t, adv))
    return tiles


def paste_center(base, im, cx, cy, scale=1.0, alpha=1.0):
    if scale <= 0.01 or alpha <= 0.01:
        return
    if abs(scale - 1) > 1e-3:
        im = im.resize((max(1, round(im.width * scale)), max(1, round(im.height * scale))), Image.BICUBIC)
    if alpha < 1:
        a = im.getchannel("A").point(lambda v: int(v * alpha))
        im = im.copy()
        im.putalpha(a)
    base.alpha_composite(im, (round(cx - im.width / 2), round(cy - im.height / 2)))


# ---------------------------------------------------------------- recording clips
class Clip:
    def __init__(self, spec):
        self.t0, self.t1, src, x, y, w, h = spec
        self.n = round((self.t1 - self.t0) * FPS) + 2
        self.proc = None
        self.src, self.crop = src, (x, y, w, h)
        self.last = None
        self.count = 0

    def frame(self):
        if self.proc is None:
            x, y, w, h = self.crop
            self.proc = subprocess.Popen(
                ["ffmpeg", "-v", "error", "-ss", f"{self.src}", "-i", REC, "-t", f"{self.t1 - self.t0 + 0.2}",
                 "-vf", f"fps={FPS},crop={w}:{h}:{x}:{y},scale=720:1020:flags=lanczos",
                 "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        buf = self.proc.stdout.read(720 * 1020 * 3)
        if len(buf) == 720 * 1020 * 3:
            self.last = Image.frombytes("RGB", (720, 1020), buf)
        elif self.last is None:
            sys.exit(f"could not decode {REC} at {self.src}s")
        self.count += 1
        return self.last

    def close(self):
        if self.proc:
            self.proc.kill()
            self.proc.stdout.close()
            self.proc.wait()


def clip_canvas(fr):
    """Full 720x1280 frame: footage at the bottom, the table colour extended upward behind the caption."""
    a = np.array(fr)
    top = np.median(a[:6].reshape(-1, 3), axis=0)
    out = np.empty((H, W, 3), np.float32)
    out[:] = top
    out[H - 1020:] = a
    ramp = np.linspace(0, 1, 50)[:, None, None]
    out[H - 1020:H - 970] = top * (1 - ramp) + a[:50] * ramp
    return Image.fromarray(out.astype(np.uint8))


# ---------------------------------------------------------------- video
def render(out_video_raw_pipe, stills_dir=None):
    check_glyphs()
    desk = make_desk().convert("RGBA")
    PWID = 600
    blank, colored, reg, tpl = make_pages(PWID)
    PHT = blank.height
    PX, PY = (W - PWID) // 2, 268
    groups = color_groups(reg, json.load(open(f"{SHEET}/regions.json"))["ids"])
    ng = len(groups)
    span = T_COLOR[1] - T_COLOR[0]
    gdur = 0.75
    starts = [T_COLOR[0] + i * (span - gdur) / max(1, ng - 1) for i in range(ng)]
    blank_a = np.array(blank, np.float32).reshape(-1, 3)
    col_a = np.array(colored, np.float32).reshape(-1, 3)
    shadow = Image.new("RGBA", (PWID + 60, PHT + 60), (0, 0, 0, 0))
    ImageDraw.Draw(shadow).rectangle([30, 34, PWID + 30, PHT + 34], fill=(60, 40, 20, 90))
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    crayons = {}

    # marker centres in display page coords
    s = PWID / tpl["page"][0]
    ms = tpl["markerSize"]
    markers = [((mx + ms / 2) * s, (my + ms / 2) * s) for mx, my in tpl["markers"]]
    page_rect = [(0, 0), (PWID, 0), (PWID, PHT), (0, PHT)]
    flat_quad = [(PX, PY), (PX + PWID, PY), (PX + PWID, PY + PHT), (PX, PY + PHT)]
    desk_quad = [(170, 290), (550, 290), (668, 770), (52, 770)]

    # phone
    PHW, PHH, BZ = 360, 668, 14
    SW, SH = PHW - 2 * BZ, PHH - 2 * BZ
    phone_shell = Image.new("RGBA", (PHW + 10, PHH + 14), (0, 0, 0, 0))
    dd = ImageDraw.Draw(phone_shell)
    dd.rounded_rectangle([5, 12, PHW + 5, PHH + 12], 54, fill=(20, 15, 10, 140))
    dd.rounded_rectangle([5, 5, PHW + 5, PHH + 5], 54, fill=(52, 44, 40), outline=INK, width=4)
    screen_mask = rounded_mask((SW, SH), 40)
    notch = (PHW // 2 + 5 - 50, 5 + BZ + 8, PHW // 2 + 5 + 50, 5 + BZ + 26)
    desk_screen = desk.resize((round(W * 0.55), round(H * 0.55))).crop((0, 60, SW, 60 + SH))
    screen_quad0 = [(64, 132), (268, 132), (316, 500), (16, 500)]
    play = Image.open(f"{SHEET}/textured_phone_play.png").convert("RGBA")
    sc = SH / play.height
    play = play.resize((round(play.width * sc), SH), Image.LANCZOS)
    play = play.crop(((play.width - SW) // 2, 0, (play.width - SW) // 2 + SW, SH))
    col_rgba = colored.convert("RGBA")

    cards = [caption_card(c[2], c[3], c[4]) for c in CAPTIONS]
    hint = chip(HINT[2], HINT[3])
    found = chip(FOUND_TXT[0], FOUND_TXT[1], fill=OK_GREEN, fg="white", fg2="white", zh_size=50, en_size=28)
    endbtn = chip(END_TXT[0], END_TXT[1], fill=BRAND, fg="white", fg2="white", zh_size=64, en_size=34, pad=30)
    logo_tiles = logo()
    clips = [Clip(c) for c in CLIPS]
    rng = np.random.default_rng(11)
    sparks = [(rng.uniform(0, 2 * math.pi), rng.uniform(60, 190), rng.uniform(7, 15), CRAYONS[i % 7], rng.uniform(0, 6))
              for i in range(26)]

    blurred_bg = None
    nframes = round(DUR * FPS)
    still_times = {1.0, 3.5, 6.0, 9.0, 11.8, 12.5, 14.5, 15.4, 17.8, 18.8, 19.5, 21.0, 25.0, 28.5, 30.4, 31.5}
    for fi in range(nframes):
        t = fi / FPS
        frame = desk.copy()

        # ---------- clips (read in order, so every clip advances exactly while it is visible)
        clip_layers = []
        for c in clips:
            if c.t0 <= t < c.t1 + 1e-6:
                fr = c.frame()
                clip_layers.append((fr, prog(t, c.t0, c.t0 + XF)))   # each clip fades in over the one before

        if t < T_TILT[1] + 0.6:
            # ---------- sheet: slide in, colour, tilt down onto the desk
            if t < T_COLOR[0]:
                A = None
            else:
                A = np.zeros(blank_a.shape[0], np.float32)
                for g, st in zip(groups, starts):
                    p = prog(t, st, st + gdur)
                    if p <= 0:
                        continue
                    soft = 0.35
                    A[g["idx"]] = np.maximum(A[g["idx"]], np.clip((p * (1 + soft) - g["u"]) / soft, 0, 1))
            if A is None:
                page = blank.convert("RGBA")
            else:
                mix = blank_a + (col_a - blank_a) * A[:, None]
                page = Image.fromarray(mix.reshape(PHT, PWID, 3).astype(np.uint8)).convert("RGBA")
            if t < T_TILT[0]:
                k = back_out(prog(t, 0.2, 1.4), 1.2)
                ang = 7 * (1 - ease_out(prog(t, 0.2, 1.6)))
                dy = (1 - k) * 1000
                sh = shadow.rotate(ang, resample=Image.BICUBIC, expand=False)
                pg = page.rotate(ang, resample=Image.BICUBIC, expand=True)
                frame.alpha_composite(sh, (PX - 30, round(PY - 30 + dy)))
                frame.alpha_composite(pg, (round(PX + PWID / 2 - pg.width / 2), round(PY + PHT / 2 - pg.height / 2 + dy)))
                # crayon
                if T_COLOR[0] - 0.4 <= t <= T_COLOR[1] + 0.5:
                    gi = 0
                    for i, st in enumerate(starts):
                        if t >= st:
                            gi = i
                    g = groups[gi]
                    p = prog(t, starts[gi], starts[gi] + gdur)
                    x = g["x0"] + p * (g["x1"] - g["x0"])
                    hgt = max(8, (g["y1"] - g["y0"]) * 0.32)
                    y = g["cy"] + math.sin(t * 2 * math.pi * 6.5) * hgt
                    enter = ease_out(prog(t, T_COLOR[0] - 0.4, T_COLOR[0])) * (1 - ease_io(prog(t, T_COLOR[1] + 0.1, T_COLOR[1] + 0.5)))
                    cs, (tx, ty) = crayons.setdefault(g["color"], crayon_sprite(g["color"]))
                    cx = PX + x + (1 - enter) * 300
                    cy = PY + y + (1 - enter) * 300
                    frame.alpha_composite(cs, (round(cx - tx), round(cy - ty)))
            else:
                k = ease_io(prog(t, *T_TILT))
                quad = [(fx + (dx - fx) * k, fy + (dy - fy) * k) for (fx, fy), (dx, dy) in zip(flat_quad, desk_quad)]
                sh = warp(Image.new("RGBA", page.size, (60, 40, 20, 90)), [(x + 6, y + 10) for x, y in quad], (W, H))
                frame.alpha_composite(sh.filter(ImageFilter.GaussianBlur(10)))
                frame.alpha_composite(warp(page, quad, (W, H)))
                if t >= T_TILT[1]:
                    if blurred_bg is None:
                        blurred_bg = frame.filter(ImageFilter.GaussianBlur(3))
                    b = ease_io(prog(t, T_TILT[1], T_TILT[1] + 0.5))
                    frame = Image.blend(frame, blurred_bg, b)
        elif t < T_ZOOM[1] + 0.5:
            frame = blurred_bg.copy()

        # ---------- phone (scan + rise + zoom)
        if T_PHONE_IN[0] <= t < T_ZOOM[1] + 0.5:
            sway = (math.sin(t * 1.7) * 6, math.sin(t * 1.3 + 1) * 5)
            scr = desk_screen.copy()
            q = [(x - sway[0] * 0.8, y - sway[1] * 0.8) for x, y in screen_quad0]
            sheet_on_screen = warp(col_rgba, q, (SW, SH))
            scr.alpha_composite(sheet_on_screen)
            Hm = homography(page_rect, q)
            mpts = apply_h(Hm, markers)
            d = ImageDraw.Draw(scr)
            # camera guide brackets
            for (gx, gy), (sx, sy) in zip([(22, 70), (SW - 22, 70), (SW - 22, SH - 70), (22, SH - 70)], [(1, 1), (-1, 1), (-1, -1), (1, -1)]):
                d.line([(gx, gy + 34 * sy), (gx, gy), (gx + 34 * sx, gy)], fill=(255, 255, 255, 200), width=4)
            for i, (mx, my) in enumerate(mpts):
                tc = T_CORNERS[i]
                if t >= tc:
                    pk = back_out(prog(t, tc, tc + 0.25))
                    pulse = 1 + 0.12 * math.sin((t - tc) * 10) * (1 - prog(t, tc, tc + 1.2))
                    r = 20 * pk * pulse
                    if r > 3:
                        d.rounded_rectangle([mx - r, my - r, mx + r, my + r], 6, outline=OK_GREEN, width=5)
            if T_FOUND <= t < T_RISE[0] + 0.3:
                fl = 1 - prog(t, T_FOUND, T_FOUND + 0.8)
                if fl > 0:
                    d.polygon(q, outline=(63, 179, 107, int(255 * fl)), width=6)
                    ov = Image.new("RGBA", (SW, SH), (63, 179, 107, int(70 * fl)))
                    scr.alpha_composite(ov)
            # 3D rises from the page
            if t >= T_RISE[0]:
                pr = prog(t, T_RISE[0], T_RISE[0] + 1.3)
                ys = 0.55 + 0.45 * back_out(pr, 1.4)
                ph = max(1, round(SH * ys))
                pl = play.resize((SW, ph), Image.BICUBIC)
                lay = Image.new("RGBA", (SW, SH), (0, 0, 0, 0))
                lay.alpha_composite(pl, (0, SH - ph))
                m = np.zeros((SH, 1), np.float32)
                edge = SH * (1 - ease_out(pr)) * 0.9
                yy = np.arange(SH)[:, None]
                m = np.clip((yy - edge + 60) / 120, 0, 1) * min(1, pr * 3)
                alpha = (np.array(lay.getchannel("A"), np.float32) / 255 * m * 255).astype(np.uint8)
                lay.putalpha(Image.fromarray(alpha))
                scr.alpha_composite(lay)
                sd = ImageDraw.Draw(scr)
                cxs, cys = SW / 2, SH * 0.55
                for ang, dist, rad, col, rot in sparks:
                    sp = prog(t, T_RISE[0], T_RISE[0] + 1.6)
                    if 0 < sp < 1:
                        dd_ = dist * ease_out(sp) * 1.2
                        star(sd, cxs + math.cos(ang) * dd_, cys + math.sin(ang) * dd_ * 0.8 - sp * 60, rad * (1 - sp * 0.6),
                             col, rot + sp * 4, width=2)
            ph_img = phone_shell.copy()
            sm = screen_mask
            ph_img.paste(scr.convert("RGB"), (5 + BZ, 5 + BZ), sm)
            ImageDraw.Draw(ph_img).rounded_rectangle(notch, 9, fill=(25, 20, 18))
            # placement
            enter = back_out(prog(t, *T_PHONE_IN), 1.1)
            cx, cy = W / 2 + sway[0], 600 + PHH / 2 + (1 - enter) * 900 + sway[1]
            z = ease_io(prog(t, *T_ZOOM))
            scale = 1 + z * (W / SW * 1.04 - 1)
            cx = cx + (W / 2 - cx) * z
            cy = cy + (H / 2 + 8 * scale - cy) * z
            paste_center(frame, ph_img, cx, cy, scale)
            if T_FOUND <= t < T_RISE[0] + 0.2:
                k = back_out(prog(t, T_FOUND, T_FOUND + 0.35), 2.2)
                a = 1 - prog(t, T_RISE[0] - 0.3, T_RISE[0] + 0.2)
                paste_center(frame, found, W / 2, 560, k, a)
            if HINT[0] <= t < HINT[1]:
                a = min(prog(t, HINT[0], HINT[0] + 0.3), 1 - prog(t, HINT[1] - 0.3, HINT[1]))
                paste_center(frame, hint, W / 2, 292, 0.9 + 0.1 * back_out(prog(t, HINT[0], HINT[0] + 0.3)), a)

        # ---------- clips
        for fr, a in clip_layers:
            cimg = clip_canvas(fr).convert("RGBA")
            frame = Image.blend(frame, cimg, a) if a < 1 else cimg

        # ---------- end card
        if t >= T_END:
            a = ease_io(prog(t, T_END, T_END + 0.5))
            card = Image.new("RGBA", (W, H), PAPER + (255,))
            dsk = desk.copy()
            card = Image.blend(dsk, card, 0.75)
            total = sum(adv for _, adv in logo_tiles)
            x = W / 2 - total / 2
            for i, (tile, adv) in enumerate(logo_tiles):
                lt = T_END + 0.25 + i * 0.07
                k = back_out(prog(t, lt, lt + 0.35), 2.0)
                bob = math.sin((t - lt) * 4 + i) * 4 * prog(t, lt + 0.4, lt + 0.8)
                paste_center(card, tile, x + adv / 2, 520 + bob, k)
                x += adv
            kb = back_out(prog(t, T_END + 0.9, T_END + 1.3), 2.0)
            pulse = 1 + 0.04 * math.sin((t - T_END - 1.3) * 6) * prog(t, T_END + 1.3, T_END + 1.6)
            paste_center(card, endbtn, W / 2, 780, kb * pulse)
            sd = ImageDraw.Draw(card)
            for i, (ang, dist, rad, col, rot) in enumerate(sparks[:12]):
                lt = T_END + 0.6 + i * 0.05
                sp = prog(t, lt, lt + 1.0)
                if 0 < sp < 1:
                    r = 210 + dist * 0.9 * ease_out(sp)
                    star(sd, W / 2 + math.cos(ang) * r * 1.2, 600 + math.sin(ang) * r * 0.9, rad * (1 - sp), col, rot + sp * 3)
            frame = Image.blend(frame, card, a) if a < 1 else card

        # ---------- caption card
        if t < T_END:
            for i, (c0, c1, *_r) in enumerate(CAPTIONS):
                if c0 <= t < c1:
                    k = back_out(prog(t, c0, c0 + 0.35), 1.6)
                    a = min(1.0, prog(t, c0, c0 + 0.2) if i else prog(t, 0, 0.3)) * (1 - prog(t, T_END - 0.3, T_END))
                    paste_center(frame, cards[i], W / 2, 36 + cards[i].height / 2, 0.85 + 0.15 * k, a)

        rgb = frame.convert("RGB")
        out_video_raw_pipe.write(rgb.tobytes())
        if stills_dir is not None:
            for st in still_times:
                if abs(t - st) < 0.5 / FPS:
                    rgb.save(f"{stills_dir}/still_{st:05.1f}.png")
    for c in clips:
        c.close()


# ---------------------------------------------------------------- audio
def env_adsr(n, a, r):
    e = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        e[:na] = np.linspace(0, 1, na)
    if nr:
        e[-nr:] *= np.linspace(1, 0, nr)
    return e


def pluck(f, dur, amp):
    t = np.arange(int(dur * SR)) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.25 * np.sin(2 * np.pi * 2 * f * t) * np.exp(-t * 9) + 0.12 * np.sin(2 * np.pi * 3.01 * f * t) * np.exp(-t * 14)
    return amp * tone * np.exp(-t * 3.2) * env_adsr(len(t), 0.004, 0.05)


def bell(f, dur, amp):
    t = np.arange(int(dur * SR)) / SR
    tone = np.sin(2 * np.pi * f * t) + 0.4 * np.sin(2 * np.pi * 2.76 * f * t) * np.exp(-t * 6) + 0.2 * np.sin(2 * np.pi * 5.4 * f * t) * np.exp(-t * 12)
    return amp * tone * np.exp(-t * 4) * env_adsr(len(t), 0.002, 0.05)


def midi(n):
    return 440.0 * 2 ** ((n - 69) / 12)


def add(buf, sig, t):
    i = int(t * SR)
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += sig[:j - i]


def make_audio(path):
    n = int(DUR * SR)
    rng = np.random.default_rng(5)
    music = np.zeros(n)
    bpm = 100
    beat = 60 / bpm
    bar = 4 * beat
    chords = [(60, 64, 67), (55, 59, 62, 67), (57, 60, 64), (53, 57, 60, 65)]     # C G/B-ish Am F, kalimba voicing
    pattern = [0, 2, 1, 2, 0, 2, 1, 3]
    music_end = T_END + 0.6
    nb = int(music_end / bar) + 1
    for b in range(nb):
        ch = chords[b % 4]
        t0 = b * bar
        # bass
        add(music, 0.32 * np.sin(2 * np.pi * midi(ch[0] - 24) * np.arange(int(bar * SR)) / SR) * np.exp(-np.arange(int(bar * SR)) / SR * 1.2) * env_adsr(int(bar * SR), 0.01, 0.2), t0)
        # pad
        pn = int(bar * SR)
        tt = np.arange(pn) / SR
        pad = sum(np.sin(2 * np.pi * midi(m) * tt) + 0.5 * np.sin(2 * np.pi * midi(m) * 1.003 * tt) for m in ch[:3])
        add(music, 0.035 * pad * env_adsr(pn, 0.6, 0.6), t0)
        # kalimba arpeggio, eighth notes; a little melody on top every other bar
        for k, p in enumerate(pattern):
            note_ = ch[p % len(ch)] + 12
            add(music, pluck(midi(note_), 1.0, 0.16 if k % 2 == 0 else 0.11), t0 + k * beat / 2)
        if b % 2 == 1:
            for k, step in enumerate([7, 4, 2, 0] if b % 4 == 1 else [5, 4, 2, 4]):
                add(music, bell(midi(72 + step), 1.2, 0.08), t0 + k * beat)
    music[int(music_end * SR):] *= 0
    # cut the arpeggio at the end card except the final chord: crossfade by envelope
    fade = np.ones(n)
    i0, i1 = int((T_END - 0.2) * SR), int((T_END + 0.25) * SR)
    fade[i0:i1] = np.linspace(1, 0.15, i1 - i0)
    fade[i1:] = 0.15
    music *= fade
    for m in (60, 64, 67, 72, 76):
        add(music, pluck(midi(m), 2.0, 0.16), T_END + 0.25)
    music = signal.sosfilt(signal.butter(2, 6000, "low", fs=SR, output="sos"), music)

    sfx = np.zeros(n)
    # page slide
    sn = int(0.9 * SR)
    nz = rng.normal(0, 1, sn)
    sw = signal.sosfilt(signal.butter(2, [400, 2500], "band", fs=SR, output="sos"), nz)
    add(sfx, 0.35 * sw * np.sin(np.linspace(0, np.pi, sn)) ** 2, 0.2)
    add(sfx, pluck(midi(48), 0.4, 0.25) * np.exp(-np.arange(int(0.4 * SR)) / SR * 8), 1.3)      # soft landing tap
    # crayon scribble while colouring
    cn = int((T_COLOR[1] - T_COLOR[0] + 0.3) * SR)
    nz = signal.sosfilt(signal.butter(2, [1800, 6000], "band", fs=SR, output="sos"), rng.normal(0, 1, cn))
    tt = np.arange(cn) / SR
    strokes = (0.5 + 0.5 * np.sin(2 * np.pi * 6.5 * 2 * tt + 0.3 * np.sin(2 * np.pi * 0.7 * tt))) ** 2
    grit = 0.6 + 0.4 * signal.sosfilt(signal.butter(1, 30, fs=SR, output="sos"), np.abs(rng.normal(0, 1, cn))) * 2
    add(sfx, 0.22 * nz * strokes * grit * env_adsr(cn, 0.2, 0.3), T_COLOR[0])
    # phone whoosh in
    wn = int(0.6 * SR)
    sw = signal.sosfilt(signal.butter(2, [300, 1500], "band", fs=SR, output="sos"), rng.normal(0, 1, wn))
    add(sfx, 0.25 * sw * np.sin(np.linspace(0, np.pi, wn)) ** 2, T_PHONE_IN[0])
    # corner beeps
    for i, tc in enumerate(T_CORNERS):
        bn = int(0.1 * SR)
        tt = np.arange(bn) / SR
        add(sfx, 0.18 * np.sin(2 * np.pi * midi(84 + [0, 2, 4, 7][i]) * tt) * env_adsr(bn, 0.003, 0.06), tc)
    # found chime
    for i, m in enumerate((84, 88, 91, 96)):
        add(sfx, bell(midi(m), 1.2, 0.18), T_FOUND + i * 0.07)
    # magic rise shimmer
    rn = int(2.0 * SR)
    tt = np.arange(rn) / SR
    gl = np.zeros(rn)
    for k, base in enumerate((72, 76, 79, 84)):
        f = midi(base) * (1 + 0.5 * tt / 2.0)
        gl += np.sin(2 * np.pi * np.cumsum(f) / SR + k) / 4
    add(sfx, 0.10 * gl * (0.6 + 0.4 * np.sin(2 * np.pi * 9 * tt)) * env_adsr(rn, 0.5, 0.6), T_RISE[0])
    for i in range(14):
        add(sfx, bell(midi(int(rng.choice([84, 86, 88, 91, 93, 96]))), 0.6, 0.06), T_RISE[0] + 0.2 + i * 0.11)
    # zoom whoosh
    wn = int(0.8 * SR)
    sw = signal.sosfilt(signal.butter(2, [200, 1200], "band", fs=SR, output="sos"), rng.normal(0, 1, wn))
    add(sfx, 0.22 * sw * np.sin(np.linspace(0, np.pi, wn)) ** 2, T_ZOOM[0])
    # soft transitions between clips
    for c in CLIPS[1:]:
        add(sfx, bell(midi(91), 0.8, 0.05), c[0] + 0.1)
    # end: letter pops + sparkle
    for i in range(8):
        pn = int(0.12 * SR)
        tt = np.arange(pn) / SR
        f = np.linspace(700 + i * 40, 250, pn)
        add(sfx, 0.12 * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt * 30), T_END + 0.25 + i * 0.07)
    for i in range(10):
        add(sfx, bell(midi(int(rng.choice([88, 91, 93, 96, 100]))), 0.7, 0.05), T_END + 0.7 + i * 0.09)

    mix = music + sfx
    tail = int(0.6 * SR)
    mix[-tail:] *= np.linspace(1, 0, tail)
    mix[:int(0.02 * SR)] *= np.linspace(0, 1, int(0.02 * SR))
    stereo = np.stack([mix, mix], 1)
    raw = f"{WORK}/mix_raw.wav"
    wavfile.write(raw, SR, (stereo / (np.abs(stereo).max() + 1e-9) * 0.5).astype(np.float32))
    # two-pass loudnorm to -18 LUFS
    p = subprocess.run(["ffmpeg", "-hide_banner", "-i", raw, "-af", f"loudnorm=I={LUFS}:TP=-1.5:LRA=11:print_format=json",
                        "-f", "null", "-"], capture_output=True, text=True)
    js = json.loads(p.stderr[p.stderr.rindex("{"):p.stderr.rindex("}") + 1])
    af = (f"loudnorm=I={LUFS}:TP=-1.5:LRA=11:measured_I={js['input_i']}:measured_TP={js['input_tp']}:"
          f"measured_LRA={js['input_lra']}:measured_thresh={js['input_thresh']}:offset={js['target_offset']}:linear=true")
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", raw, "-af", af, "-ar", str(SR), path], check=True)


# ---------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=OUT)
    ap.add_argument("--keep", action="store_true", help="keep /tmp/howto_work")
    ap.add_argument("--stills", help="also save stills of each step into this folder")
    args = ap.parse_args()
    os.makedirs(WORK, exist_ok=True)
    os.makedirs(os.path.dirname(args.out), exist_ok=True)
    if args.stills:
        os.makedirs(args.stills, exist_ok=True)
    audio = f"{WORK}/mix.wav"
    make_audio(audio)
    enc = subprocess.Popen(
        ["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}", "-r", str(FPS), "-i", "-",
         "-i", audio, "-map", "0:v", "-map", "1:a",
         "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-maxrate", "950k", "-bufsize", "1900k",
         "-pix_fmt", "yuv420p", "-profile:v", "high", "-level", "4.0", "-g", "60", "-threads", "1",
         "-c:a", "aac", "-b:a", "96k", "-ar", "44100", "-shortest",
         "-movflags", "+faststart", "-map_metadata", "-1", "-fflags", "+bitexact", "-flags:v", "+bitexact",
         "-flags:a", "+bitexact", args.out], stdin=subprocess.PIPE)
    render(enc.stdin, args.stills)
    enc.stdin.close()
    if enc.wait() != 0:
        sys.exit("ffmpeg encode failed")
    if not args.keep:
        shutil.rmtree(WORK, ignore_errors=True)
    print(f"wrote {args.out} ({os.path.getsize(args.out) / 1e6:.2f} MB)")


if __name__ == "__main__":
    main()
