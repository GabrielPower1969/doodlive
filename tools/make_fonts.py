#!/usr/bin/env python3
"""Subset the five OFL fonts to the characters the app uses.
Sources: google/fonts on GitHub, downloaded into assets/fonts/src/ (git-ignored).
Outputs (committed): web/fonts/*.woff2 and unity/Assets/DoodLive/Resources/Fonts/*.ttf, plus each font's OFL licence.
Re-run after adding strings to tools/i18n/strings.json or changing a story timeline (assets/*/timeline.json)."""
import io, json, os, shutil, urllib.request
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools import subset

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = f"{ROOT}/assets/fonts/src"
GH = "https://raw.githubusercontent.com/google/fonts/main/ofl/"
FONTS = [  # out name, source file, google/fonts path, static axes, character set
    ("Grandstander-Black", "Grandstander[wght].ttf", "grandstander/Grandstander%5Bwght%5D.ttf", {"wght": 900}, "latin"),
    ("Fredoka-SemiBold", "Fredoka[wdth,wght].ttf", "fredoka/Fredoka%5Bwdth,wght%5D.ttf", {"wght": 600, "wdth": 100}, "latin"),
    ("Nunito-ExtraBold", "Nunito[wght].ttf", "nunito/Nunito%5Bwght%5D.ttf", {"wght": 800}, "latin"),
    ("ZCOOLKuaiLe-Regular", "ZCOOLKuaiLe-Regular.ttf", "zcoolkuaile/ZCOOLKuaiLe-Regular.ttf", None, "all"),
    ("MaShanZheng-Regular", "MaShanZheng-Regular.ttf", "mashanzheng/MaShanZheng-Regular.ttf", None, "learn"),
    # extra languages (docs/I18N.md): Japanese and Arabic need their own faces
    ("NotoSansJP-Bold", "NotoSansJP[wght].ttf", "notosansjp/NotoSansJP%5Bwght%5D.ttf", {"wght": 700}, "ja"),
    ("NotoSansArabic-Bold", "NotoSansArabic[wdth,wght].ttf", "notosansarabic/NotoSansArabic%5Bwdth,wght%5D.ttf", {"wght": 700, "wdth": 100}, "ar"),
]
LATIN = "".join(chr(c) for c in range(0x20, 0x7F)) + "".join(chr(c) for c in range(0xA0, 0x180)) + "„‚‹›¡¿" + "āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜüĀÁǍÀĒÉĚÈĪÍǏÌŌÓǑÒŪÚǓÙ…—–‘’“”·•×✓"
strings = json.load(open(f"{ROOT}/tools/i18n/strings.json", encoding="utf-8"))
ALL = LATIN + "".join(v[l] for k, v in strings.items() if not k.startswith("_") for l in ("zh", "en")) + "，。！？：；、（）《》「」中拼音"
# story text shown as subtitles / chapter titles (Unity DGDirector): every line and shot title of each timeline
import glob as _glob
for _st in json.load(open(f"{ROOT}/assets/stories.json", encoding="utf-8"))["stories"]:   # home-screen story titles
    extra_titles = globals().setdefault("extra_titles", []); extra_titles += [_st["title_zh"], _st["title_en"]]
for tl_path in sorted(_glob.glob(f"{ROOT}/assets/*/timeline.json")):
    if os.path.exists(tl_path):
        tl = json.load(open(tl_path, encoding="utf-8"))
        ALL += "".join(x.get(k, "") for x in tl.get("lines", []) + tl.get("shots", []) for k in ("zh", "en", "title_zh", "title_en"))
ALL += "".join(globals().get("extra_titles", []))
# the home-screen library (docs/LIBRARY.md): book titles, pinyin, blurbs and the screen's own words
if os.path.exists(f"{ROOT}/assets/library.json"):
    for _b in json.load(open(f"{ROOT}/assets/library.json", encoding="utf-8"))["books"]:
        ALL += "".join(str(_b.get(k, "")) for k in ("title_zh", "title_en", "pinyin", "blurb_zh", "blurb_en"))
_lib_cs = f"{ROOT}/unity/Assets/DoodLive/Scripts/ARColoringController.Library.cs"
if os.path.exists(_lib_cs):
    import re as _re
    ALL += "".join(_re.findall(r'"([^"\n]*)"', open(_lib_cs, encoding="utf-8").read())) + "▶"
LEARN = "天使炙热愤怒神圣大卫歌利亚"   # characters taught on the sheets (3D titles + word card)
# Japanese and Arabic: every UI string and story text in that language (strings.json, assets/*/i18n.json), plus Arabic's
# presentation forms (ArabicText.cs shapes letters into them, U+FE70-U+FEFF) and the language names of the picker
def _lang_text(lang):
    t = "".join(v.get(lang, "") for k, v in strings.items() if not k.startswith("_"))
    for ip in _glob.glob(f"{ROOT}/assets/*/i18n.json"):
        d = json.load(open(ip, encoding="utf-8"))
        t += "".join(d.get("title", {}).get(lang, "") + d.get("blurb", {}).get(lang, ""))
        t += "".join(m.get(lang, "") for kind in ("shots", "lines") for m in d.get(kind, {}).values())
    return t
NAMES = "中文EnglishFrançaisDeutsch日本語Españolالعربية Português▾▶·"
JA = LATIN + _lang_text("ja") + NAMES + "、。「」！？・ー〜…（）"
AR = LATIN + _lang_text("ar") + NAMES + "".join(chr(c) for c in range(0xFE70, 0xFEFF)) + "،؟؛«»"
ALL += _lang_text("zh") + NAMES
CHARS = {"latin": LATIN, "all": ALL, "learn": LEARN, "ja": JA, "ar": AR}

os.makedirs(SRC, exist_ok=True)
web_dir, unity_dir = f"{ROOT}/web/fonts", f"{ROOT}/unity/Assets/DoodLive/Resources/Fonts"
os.makedirs(web_dir, exist_ok=True); os.makedirs(unity_dir, exist_ok=True)
for name, src, gh, axes, charset in FONTS:
    path = f"{SRC}/{src}"
    if not os.path.exists(path):
        urllib.request.urlretrieve(GH + gh, path)
    font = TTFont(path)
    if axes:
        font = instancer.instantiateVariableFont(font, axes)
    opts = subset.Options(); opts.layout_features = ["*"]; opts.name_IDs = ["*"]; opts.notdef_outline = True
    sub = subset.Subsetter(opts); sub.populate(text="".join(sorted(set(CHARS[charset])))); sub.subset(font)
    font.save(f"{unity_dir}/{name}.ttf")
    font.flavor = "woff2"; font.save(f"{web_dir}/{name}.woff2")
    print(f"{name}: {os.path.getsize(f'{web_dir}/{name}.woff2') // 1024} KB woff2, {os.path.getsize(f'{unity_dir}/{name}.ttf') // 1024} KB ttf")
for name, src, gh, axes, charset in FONTS:   # each family ships its own OFL with its copyright line
    lic = f"{SRC}/OFL-{name.split('-')[0]}.txt"
    if not os.path.exists(lic):
        urllib.request.urlretrieve(GH + gh.split("/")[0] + "/OFL.txt", lic)
    shutil.copy(lic, f"{web_dir}/OFL-{name.split('-')[0]}.txt")
open(f"{web_dir}/README.md", "w").write("Subsets of Grandstander, Fredoka, Nunito, ZCOOL KuaiLe, Ma Shan Zheng, Noto Sans JP and Noto Sans Arabic from github.com/google/fonts, "
                                         "all under the SIL Open Font License 1.1 (each font's own OFL names its copyright holders). "
                                         "Generated by tools/make_fonts.py; the Unity copies live in unity/Assets/DoodLive/Resources/Fonts.\n")
