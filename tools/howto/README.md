# How-to-play video

`make_howto.py` builds `unity/Assets/StreamingAssets/howto/howto.mp4`, the demo video on the home page:
print the sheet, colour it in, scan it with the phone, and the story comes alive in 3D, seen from all sides.

```
python3 tools/howto/make_howto.py            # ~40 s on a MacBook; byte-identical output on every run
python3 tools/howto/make_howto.py --stills /tmp/howto_stills --keep   # also save a still per step, keep /tmp/howto_work
```

Needs Python 3 with pillow, numpy, scipy and fonttools, plus `ffmpeg` on PATH. The intermediates (the audio mix) go
to `/tmp/howto_work`, which is deleted at the end unless you pass `--keep`.

**Output:** 720x1280 portrait, 30 fps, 32.0 s, H.264 High yuv420p with faststart, AAC-LC 96 kbps stereo,
about 3.8 MB, -18 LUFS integrated.

| Time (s) | Step | What you see |
|---|---|---|
| 0-4 | 1 打印涂色纸 / Print the colouring sheet | The blank Ruth sheet (`print/ruth-A4.png`) slides onto a warm desk. |
| 4-12 | 2 涂上你喜欢的颜色 / Colour it in | A crayon fills the regions (`regions.png`) top to bottom with the demo colours. The 4 corner markers stay black. |
| 12-17 | 3 用手机扫一扫 / Scan it with the app | The sheet tips down onto the desk and a phone slides in. The 4 corners light up green one by one, then a "找到了！/ Found it!" bubble appears. A chip reads "四个黑角都拍进来 / Keep all 4 black corners in view". |
| 17-20 | 4 故事活起来了！/ Watch it come alive! | Stars burst and the 3D set (`textured_phone_play.png`) rises on the phone screen. Then the phone zooms in to fill the frame. |
| 20-30 | 4 前后左右看一看 / Move around, see it from every side | Three cross-faded clips from the Ruth recording on the device, at 5 s, 183.6 s and 213.4 s: the whole page, the wedding arch in orbit, and the golden rays in orbit. The recording's subtitles and UI are cropped out. |
| 30-32 | end | The DoodLive logo in crayon colours and a blue "开始吧！/ Let's go!" button. |

**Fonts:** ZCOOL KuaiLe (Chinese), Fredoka SemiBold (English) and Grandstander Black (logo), all from
`unity/Assets/DoodLive/Resources/Fonts`. The ZCOOL font is a subset. The script checks every caption glyph and stops if
one is missing. "转" is not in the subset, so "转着看" became "前后左右看一看". To change a caption, edit `CAPTIONS`, `HINT`,
`FOUND_TXT` or `END_TXT` at the top of the script. If a new glyph is missing, add it to the font subset with
`tools/make_fonts.py`, or reword the caption.

**Audio:** everything is synthesised in the script. There are no samples and no copyrighted music. The music is a kalimba
arpeggio over C-G-Am-F at 100 bpm with a pad and a bass. The sound effects are a page slide, a crayon scribble,
the phone whoosh, 4 corner beeps, a "found" chime, a magic shimmer while the set rises, a zoom whoosh, and pops with
a sparkle on the logo. A two-pass ffmpeg `loudnorm` sets the mix to -18 LUFS with a -1.5 dBTP ceiling.

**Timing** lives in the constants at the top: `T_*`, `CLIPS` (output start and end, source second, crop box) and
`CAPTIONS`. If the recording is replaced, choose new source seconds where the camera orbits.
Pick crop boxes with an aspect of 720:1020 that leave out the bottom subtitle card (source y > 1950).
