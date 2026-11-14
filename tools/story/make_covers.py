#!/usr/bin/env python3
"""Library covers: one 3:4 picture per story, cut from a real on-device demo recording (scripts/record-demo.sh).

Each cover is the frame at a chosen second, cropped to the stage (everything that is not the warm table colour,
ignoring the top bar and the subtitle card) and padded to 3:4. Output: assets/<id>/cover.png (600x800) and the copy
the app loads, unity/Assets/DoodLive/Resources/Covers/<id>.png. The choice of video and second lives in
assets/library.json ("cover": {"video": "<file in unity/Builds>", "t": 62}); the recordings themselves stay out of git.
Also writes unity/Assets/DoodLive/Resources/library.json: shelf order, titles, pinyin, blurbs, minutes and the shot
titles of each timeline (the chapter list), so the home screen needs no story loaded.
Usage: python3 tools/story/make_covers.py [id ...]
"""
import json, os, subprocess, sys, tempfile
from PIL import Image
import numpy as np

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
TABLE = np.array([0x9C, 0x6B, 0x45], float)   # NoArCamera() backdrop (ARColoringController.cs)
W, H = 600, 800


def frame(video, t):
    with tempfile.TemporaryDirectory() as d:
        out = os.path.join(d, "f.png")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", str(t), "-i", video, "-frames:v", "1", out], check=True)
        return Image.open(out).convert("RGB")


def boxed(img, box):
    """Hand-picked crop: [centre x, centre y, height] in source pixels (library.json cover.box), 3:4."""
    cx, cy, bh = box; bw = bh * W / H
    canvas = Image.new("RGB", (int(bw), int(bh)), tuple(int(v) for v in TABLE))
    x0, y0 = int(cx - bw / 2), int(cy - bh / 2)
    canvas.paste(img.crop((max(0, x0), max(0, y0), min(img.width, x0 + int(bw)), min(img.height, y0 + int(bh)))), (max(0, -x0), max(0, -y0)))
    return canvas.resize((W, H), Image.LANCZOS)


def cover(img, pad=0.06):
    a = np.asarray(img).astype(float); h, w, _ = a.shape
    a[: int(h * 0.11)] = TABLE; a[int(h * 0.80):] = TABLE   # UI chips / subtitles never appear on a cover
    img = Image.fromarray(a.astype(np.uint8))
    diff = np.abs(a - TABLE).sum(2) > 60
    diff[: int(h * 0.11)] = False          # top chips / chapter title
    diff[int(h * 0.80):] = False           # subtitle card, bottom chips
    ys, xs = np.nonzero(diff)
    x0, x1, y0, y1 = xs.min(), xs.max(), ys.min(), ys.max()
    # a wide stage would leave the frame half empty: crop its sides instead (keep ~62 % of its width), centred on
    # where the picture is busiest, so the characters fill the cover
    bw, bh = (x1 - x0) * (1 + 2 * pad), (y1 - y0) * (1 + 2 * pad)
    bh = max(bh, min(bw, w) * 0.5 * H / W); bw = bh * W / H
    cx = float(np.clip(xs.mean(), x0 + bw / 2 - (x1 - x0) * pad, x1 - bw / 2 + (x1 - x0) * pad)) if bw < (x1 - x0) else (x0 + x1) / 2
    cy = min((y0 + y1) / 2, y1 + (y1 - y0) * pad - bh / 2) if bh > (y1 - y0) * (1 + 2 * pad) else (y0 + y1) / 2   # stage at the bottom
    cy = max(cy, y0 - (y1 - y0) * pad + bh / 2 - bh * 0.35)
    box = [int(cx - bw / 2), int(cy - bh / 2), int(cx + bw / 2), int(cy + bh / 2)]
    canvas = Image.new("RGB", (box[2] - box[0], box[3] - box[1]), tuple(int(v) for v in TABLE))
    canvas.paste(img.crop((max(0, box[0]), max(0, box[1]), min(w, box[2]), min(h, box[3]))),
                 (max(0, -box[0]), max(0, -box[1])))
    return canvas.resize((W, H), Image.LANCZOS)


def main(ids):
    lib = json.load(open(os.path.join(ROOT, "assets/library.json"), encoding="utf-8"))
    reg = {s["id"]: s for s in json.load(open(os.path.join(ROOT, "assets/stories.json"), encoding="utf-8"))["stories"]}
    entries = [s for s in lib["books"] if "cover" in s and (not ids or s["id"] in ids)]
    res = os.path.join(ROOT, "unity/Assets/DoodLive/Resources/Covers"); os.makedirs(res, exist_ok=True)
    books = []
    for b in lib["books"]:
        r = reg.get(b["id"], {}); tl_path = os.path.join(ROOT, "assets", b["id"], "timeline.json")
        shots = []
        if os.path.exists(tl_path):
            tl = json.load(open(tl_path, encoding="utf-8"))
            shots = [{"zh": sh.get("title_zh", ""), "en": sh.get("title_en", "")} for sh in tl.get("shots", [])]
        books.append({"id": b["id"], "zh": b.get("title_zh", r.get("title_zh", "")), "en": b.get("title_en", r.get("title_en", "")),
                      "pinyin": b.get("pinyin", ""), "blurbZh": b["blurb_zh"], "blurbEn": b["blurb_en"],
                      "minutes": b.get("minutes", 0), "shots": shots})
    json.dump({"books": books}, open(os.path.join(ROOT, "unity/Assets/DoodLive/Resources/library.json"), "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print(f"library.json: {len(books)} books")
    for s in entries:
        c = s["cover"]; video = os.path.join(ROOT, "unity/Builds", c["video"])
        if not os.path.exists(video):
            print(f"{s['id']}: recording {c['video']} not found, keeping the existing cover"); continue
        f = frame(video, c["t"])
        img = boxed(f, c["box"]) if "box" in c else cover(f)
        dst = os.path.join(ROOT, "assets", s["id"], "cover.png"); os.makedirs(os.path.dirname(dst), exist_ok=True)
        img.save(dst, optimize=True); img.save(os.path.join(res, s["id"] + ".png"), optimize=True)
        print(f"{s['id']}: cover from {c['video']} @ {c['t']} s -> {os.path.relpath(dst, ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
