#!/usr/bin/env python3
"""Recording scripts for the family: every line of a story as a teleprompter segment, Chinese and English.

usage: make_recording_scripts.py <out-dir> [story ...]      (default: every story that has recording notes)

Writes <out-dir>/<story>/{zh,en}/lines.json + session.json in the format of the recording coach
(https://github.com/GabrielPower1969/recording-assistant): id = the story's line id, so a take's file name says
which line it is. Words come from assets/<id>/timeline.json; the delivery note and the picture to imagine come from
tools/voice/recording_notes/<id>.json. Existing folders keep their takes: only lines.json and session.json are rewritten.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTES = Path(__file__).resolve().parent / "recording_notes"
BOOKS = {"Genesis": "创世记", "Exodus": "出埃及记", "Ruth": "路得记", "1 Samuel": "撒母耳记上", "Esther": "以斯帖记",
         "Leviticus": "利未记", "Psalm": "诗篇", "Isaiah": "以赛亚书", "Romans": "罗马书", "Philippians": "腓立比书", "Psalms": "诗篇", "Daniel": "但以理书", "Jonah": "约拿书", "Matthew": "马太福音",
         "Luke": "路加福音", "John": "约翰福音", "Hebrews": "希伯来书", "Revelation": "启示录"}


def ref_zh(ref):
    out = []
    for r in re.split(r";\s*", ref):
        m = re.match(r"((?:\d )?[A-Za-z]+) (.+)$", r)
        out.append(f"{BOOKS[m.group(1)]} {m.group(2)}" if m and m.group(1) in BOOKS else r)
    return "；".join(out)


def build(story, out: Path):
    tl = json.loads((ROOT / "assets" / story / "timeline.json").read_text("utf-8"))
    notes = json.loads((NOTES / f"{story}.json").read_text("utf-8"))
    dur_path = ROOT / "assets" / story / "audio" / "voice" / "durations.json"
    durs = json.loads(dur_path.read_text("utf-8")) if dur_path.exists() else {}
    meta = next(s for s in json.loads((ROOT / "assets" / "stories.json").read_text("utf-8"))["stories"] if s["id"] == story)
    shots = tl["shots"]

    def shot_of(t):
        hit = [s for s in shots if s.get("t0", 0) <= t]
        return hit[-1] if hit else shots[0]

    for lang in ("zh", "en"):
        zh, lines = lang == "zh", []
        for n, l in enumerate(tl["lines"], 1):
            note, role, shot = notes["lines"][l["id"]], notes["roles"][l["who"]][lang], shot_of(l["t"])
            sec = durs.get(lang, {}).get(l["id"]) or l.get("dur") or l.get("maxSec")
            about = (f"约 {sec:.1f} 秒，长一点也没关系" if zh else f"about {sec:.1f} s, longer is fine") if sec else ""
            ref = l.get("ref", "")
            seg = {"id": l["id"], "order": n, "size": "mid", "anySize": True,
                   "chapter": f"{shot['id']} {shot['title_zh' if zh else 'title_en']} · {role}",
                   "t": l[lang],
                   "m": ("｜" if zh else " | ").join(x for x in (role, note[f"m_{lang}"], about) if x),
                   "d": note[f"d_{lang}"] + ((f"（{ref_zh(ref)}）" if zh else f" ({ref})") if ref else "")}
            if sec:
                seg["target"] = round(sec, 1)
            if zh:
                seg["lang"] = "zh"
            else:
                seg["zh"] = l["zh"]
            lines.append(seg)
        d = out / story / lang
        d.mkdir(parents=True, exist_ok=True)
        (d / "lines.json").write_text(json.dumps(lines, ensure_ascii=False, indent=1) + "\n", "utf-8")
        (d / "session.json").write_text(json.dumps({"name": "中文版" if zh else "英文版"}, ensure_ascii=False), "utf-8")
    return meta, len(tl["lines"])


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    stories = sys.argv[2:] or sorted(p.stem for p in NOTES.glob("*.json"))
    for s in stories:
        meta, n = build(s, out)
        print(f"{meta['order']}\t{s}\t{meta['title_zh']}\t{n} lines\t{out / s}")


if __name__ == "__main__":
    main()
