"""Compose the Blender renders in $DG_WORK into the review images we ship, and measure the UV contract.

  assets/david-goliath/model/preview_<char>.png   row 1: demo-palette shading (front, 3/4, side, back)
                                                  row 2: wearing sheet/demo-colored.png through UV0 (same views)
  assets/david-goliath/model/preview_both.png     both characters, rest pose
  assets/david-goliath/model/pose_test.png        elbows 60, knees 60, spine+chest 60 (front, 3/4, side, joint close-ups)
  assets/david-goliath/model/uv_check.png         sheet | model rendered with the sheet as texture | difference,
                                                  then 3/4 textured views and the face decals through UV1
  assets/david-goliath/model/uv_check.json        pixel statistics of that comparison
  assets/david-goliath/model/preview_details.png  close-ups: heads, hands, feet (palette colours)
Run: python3 pipeline/dg_compose.py   (after dg_build.py build, make_dg_sheet.py, dg_build.py uvcheck)

UV proof without the Sheet role's outputs:
  python3 pipeline/dg_compose.py proof     -> $DG_WORK/uvproof.png: the build's own front-ortho ID render filled with the
                                              design.json palette (1000 px wide = the art rectangle), and uvproof_edges.png
  DG_UV_TEXTURE=$DG_WORK/uvproof.png blender ... dg_build.py -- uvcheck
  DG_UV_TEXTURE=$DG_WORK/uvproof.png python3 pipeline/dg_compose.py
The textured model must reproduce the texture it wears (UV0 = page projection), whatever the sheet looks like.
"""
import json, os, sys
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from scipy import ndimage

ROOT = Path(__file__).resolve().parent.parent
WORK = Path(os.environ.get("DG_WORK", "/tmp/dg_work"))
MODEL = ROOT / "assets/david-goliath/model"
SHEET = ROOT / "assets/david-goliath/sheet"
BG = (251, 245, 230)
try:
    FONT = ImageFont.truetype("/System/Library/Fonts/Helvetica.ttc", 22)
except OSError:
    FONT = ImageFont.load_default()


def flat(im, bg=BG):
    im = im.convert("RGBA"); out = Image.new("RGB", im.size, bg); out.paste(im, mask=im.split()[3]); return out


def grid(paths, cell, cols, labels=None, title=None):
    rows = (len(paths) + cols - 1) // cols; top = 40 if title else 0
    sheet = Image.new("RGB", (cols * cell, rows * (cell + 30) + top), "white"); d = ImageDraw.Draw(sheet)
    if title: d.text((10, 8), title, fill=(30, 30, 30), font=FONT)
    for i, p in enumerate(paths):
        im = flat(Image.open(p)); im.thumbnail((cell, cell))
        x, y = (i % cols) * cell, top + (i // cols) * (cell + 30)
        sheet.paste(im, (x + (cell - im.width) // 2, y))
        if labels: d.text((x + 8, y + cell + 2), labels[i], fill=(60, 60, 60), font=FONT)
    return sheet


def proof():
    """Palette fill of the build's ID render at 1x (the art rectangle), plus its region edges (stand-in for line art)."""
    table = json.load(open(WORK / "id_2x.json"))
    im = np.asarray(Image.open(WORK / "id_2x.png").convert("RGBA")).astype(int)
    key = im[..., 0] * 65536 + im[..., 1] * 256 + im[..., 2]
    out = np.full(im.shape[:2] + (3,), 255, np.uint8)
    lab = np.zeros(im.shape[:2], np.int32)
    for e in table["ids"]:
        r, g, b = e["rgb"]; m = (key == r * 65536 + g * 256 + b) & (im[..., 3] > 0)
        h = e["hex"].lstrip("#"); out[m] = [int(h[i:i + 2], 16) for i in (0, 2, 4)]; lab[m] = e["id"]
    small = Image.fromarray(out).resize((out.shape[1] // 2, out.shape[0] // 2), Image.NEAREST)
    small.save(WORK / "uvproof.png")
    l2 = lab[::2, ::2]
    edge = np.zeros(l2.shape, bool)
    edge[:-1] |= l2[:-1] != l2[1:]; edge[:, :-1] |= l2[:, :-1] != l2[:, 1:]
    Image.fromarray(np.where(edge, 0, 255).astype(np.uint8)).save(WORK / "uvproof_edges.png")
    print("proof texture", small.size)


def main():
    if len(sys.argv) > 1 and sys.argv[1] == "proof":
        return proof()
    tex = os.environ.get("DG_UV_TEXTURE")
    demo_path = Path(tex) if tex else SHEET / "demo-colored.png"
    line_path = (WORK / "uvproof_edges.png") if tex else SHEET / "lineart.png"
    views = (0, 35, 90, 180); names = ["front", "3/4", "side", "back"]
    for ch in ("david", "goliath"):
        paths = [WORK / f"prev_{ch}_{v}.png" for v in views] + [WORK / f"uv_{ch}_{v}.png" for v in views]
        labs = [f"{n} · palette" for n in names] + [f"{n} · {demo_path.name} via UV0" for n in names]
        grid(paths, 420, 4, labs, f"{ch}: rest A-pose (row 1 region colours, row 2 sheet texture)").save(MODEL / f"preview_{ch}.png")
    flat(Image.open(WORK / "prev_both.png")).save(MODEL / "preview_both.png")
    dp, dl = [], []
    for ch in ("david", "goliath"):
        for v in ("head", "headfront", "handL", "handR", "feet"):
            dp.append(WORK / f"prev_{ch}_{v}.png"); dl.append(f"{ch} · {v}")
    grid(dp, 380, 5, dl, "close-ups (rest pose, design palette)").save(MODEL / "preview_details.png")
    pp, pl = [], []
    for ch in ("david", "goliath"):
        for v in ("0", "60", "forearmL", "shinL", "spine", "fingersL", "fingersR"):
            pp.append(WORK / f"pose_{ch}_{v}.png"); pl.append(f"{ch} · {v}")
    grid(pp, 340, 7, pl, "pose test: forearms 60° fwd, shins 60° back, spine+chest 30°+30°, fingers 50°+50° (open hands curl, "
         "fists open), thumbs 25°").save(MODEL / "pose_test.png")

    # ---- UV contract: the model rendered front-ortho with the sheet as texture must reproduce the sheet
    demo = np.asarray(Image.open(demo_path).convert("RGB")).astype(float)
    line = np.asarray(Image.open(line_path).convert("L")).astype(float)
    rnd = np.asarray(Image.open(WORK / "uv_front.png").convert("RGBA")).astype(float)
    alpha = rnd[..., 3] / 255.0
    comp = rnd[..., :3] * alpha[..., None] + 255 * (1 - alpha[..., None])
    model = alpha > 0.99
    near_ink = ndimage.binary_dilation(line < 128, iterations=4)        # outlines: the UV inset samples inside them
    diff = np.abs(comp - demo).max(axis=-1)
    core = model & ~near_ink
    stats = {
        "modelPixels": int(model.sum()),
        "interiorPixels": int(core.sum()),
        "interiorMeanAbsDiff": round(float(diff[core].mean()), 3),
        "interiorPctOver24": round(float((diff[core] > 24).mean() * 100), 3),
        "allModelMeanAbsDiff": round(float(diff[model].mean()), 3),
        "allModelPctOver24": round(float((diff[model] > 24).mean() * 100), 3),
        "texture": demo_path.name,
        "note": "interior = model pixels farther than 4 px from any ink; near outlines the UV inset (4 px) deliberately "
                "samples the colour inside the line instead of the line itself",
    }
    heat = np.clip(diff * 4, 0, 255).astype(np.uint8)
    heat_img = Image.fromarray(np.stack([heat, np.zeros_like(heat), np.zeros_like(heat)], -1))
    W, H = demo.shape[1], demo.shape[0]
    top = Image.new("RGB", (W * 3, H + 40), "white"); d = ImageDraw.Draw(top)
    top.paste(Image.fromarray(demo.astype(np.uint8)), (0, 40))
    top.paste(Image.fromarray(comp.round().astype(np.uint8)), (W, 40))
    top.paste(heat_img, (2 * W, 40))
    d.text((10, 8), str(demo_path.name), fill=(0, 0, 0), font=FONT)
    d.text((W + 10, 8), "3D models, front ortho, textured through UV0", fill=(0, 0, 0), font=FONT)
    d.text((2 * W + 10, 8), f"|difference| x4  (interior mean {stats['interiorMeanAbsDiff']}, >24: {stats['interiorPctOver24']}%)",
           fill=(0, 0, 0), font=FONT)
    bottom = grid([WORK / "uv_david_35.png", WORK / "uv_goliath_35.png", WORK / "decal_david.png", WORK / "decal_goliath.png",
                   WORK / "decal_david_35.png", WORK / "decal_goliath_35.png"], W * 3 // 6, 6,
                  ["david 3/4", "goliath 3/4", "david decal UV1", "goliath decal UV1", "david decal 3/4", "goliath decal 3/4"])
    out = Image.new("RGB", (W * 3, top.height + bottom.height), "white"); out.paste(top, (0, 0)); out.paste(bottom, (0, top.height))
    out.save(MODEL / "uv_check.png")
    json.dump(stats, open(MODEL / "uv_check.json", "w"), indent=1)
    print(json.dumps(stats, indent=1))


if __name__ == "__main__":
    main()
