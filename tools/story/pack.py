#!/usr/bin/env python3
"""Gather a story pack's integration facts into assets/<id>/pack.json for Unity's StorySetup (JsonUtility-friendly lists).

Reads assets/stories.json (titles, cast, set), assets/<id>/design.json (characters.<id>.height / sheetX, set unpainted
colour), assets/<id>/model/sheet_layout.json (Characters role defaults, if design.json has no placement yet) and
assets/<id>/faces.json (face decal per clip). Usage: python3 tools/story/pack.py <id>
"""
import json, os, sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load(p, default=None):
    p = os.path.join(ROOT, p)
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else default


def main(sid):
    reg = next(s for s in load("assets/stories.json")["stories"] if s["id"] == sid)
    design = load(f"assets/{sid}/design.json", {})
    layout = load(f"assets/{sid}/model/sheet_layout.json", {})
    faces = load(f"assets/{sid}/faces.json", {})
    chars = design.get("characters", {})
    cast = []
    for cid in reg["cast"]:
        c = chars.get(cid, {}); l = layout.get(cid, {}) if isinstance(layout, dict) else {}
        f = faces.get(cid, {})
        cast.append({"id": cid, "height": c.get("height", l.get("height", 0.35)), "sheetX": c.get("sheetX", l.get("sheetX", 0.0)),
                     "defaultFace": f.get("default", ""),
                     "clipFaces": [{"clip": k, "face": v} for k, v in f.get("clips", {}).items()]})
    out = {"id": sid, "set": reg.get("set", ""), "titleZh": reg["title_zh"], "titleEn": reg["title_en"],
           "sheets": reg["sheets"], "cast": cast,
           "setUnpainted": design.get("set", {}).get("unpaintedHex", "#EFE6D4")}
    json.dump(out, open(os.path.join(ROOT, f"assets/{sid}/pack.json"), "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"{sid}: pack.json with {len(cast)} cast, set '{out['set']}'")


if __name__ == "__main__":
    main(sys.argv[1])
