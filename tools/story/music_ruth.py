#!/usr/bin/env python3
"""Original score and sound effects for "Ruth" (story pack #3; docs/ruth/CONTRACT.md section 7, docs/ruth/MUSIC.md).

Same machinery as Esther, shared rather than forked: this script imports tools/story/music_kit.py (moved out of music_esther.py)
(Score / Part / mel / groove / fill_phrase / Ctx, the FluidSynth renderer, the convolution hall, loudness and file
helpers, the synthesis primitives) and never changes it, so Esther's output is untouched. Only the Ruth cues, the
Ruth effects and the Ruth paths live here.

The score is built around one original melody, the **Ruth theme** (RUTH_THEME below, 8 bars). It is first heard in
D minor on a solo cello under Ruth's "Where you go, I will go" (S02) and resolves to D major on the hug; its opening
figure comes back as a hint when Ruth cheers Naomi up (journey), at Boaz's blessing (boaz) and his promise (night);
it is sung in D major by the strings at the golden-hour homecoming (home), becomes a 3/4 music-box lullaby (lullaby)
and gets its full, bright statement in the finale.

Every name and time comes from assets/ruth/timeline.json, read on every run: cue lengths follow the music spans,
and every in-cue hit (theme entry, hug, Boaz's greeting / curiosity / blessing, the sneaky drop and chuckle, the
blessing sparkle, the promise, the golden rays) is looked up by event, so after the voices re-time the timeline,
just rerun this script. Because the app also re-times the play at load (longer family recordings), every cue
continues after its cadence into a quiet loop section on its final chord: cues.json gives a sample-exact seamless
loop (loopStart / loopEnd) and the file runs at least 30 % past its span as a plain tail. Ambience beds (birds,
crickets) are whole-file seamless loops with a stopAtCue hint in mix.json.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/ruth/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated, true peak <= -1 dBTP
  assets/ruth/audio/music/cues.json        cue lengths, spans, loudness, crossfade rule
  assets/ruth/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/ruth/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain
  assets/ruth/audio/preview_mix.mp3        rough full-length mix at timeline times (zh voice clips when present;
                                           otherwise the music is ducked over the estimated line spans)
  docs/ruth/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_ruth.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg (as music_esther.py)
"""
import argparse, atexit, json, math, os, re, shutil, sys, tempfile
import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import music_kit as me                                                     # noqa: E402  (shared engine)
from music_kit import (Score, Ctx, mel, groove, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB, DUCK_DB,  # noqa: E402
                          HARP, KOTO, NYLON, CELESTA, GLOCK, XYLO, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                          CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, TIMPANI, HORN, DRUMS,
                          BDRUM, CLAP, TAMB, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA, HI_WOOD, LO_WOOD,
                          SHAKER, TRIANGLE)

ROOT = me.ROOT
RU = f"{ROOT}/assets/ruth"
TIMELINE = f"{RU}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{RU}/audio/music", f"{RU}/audio/sfx", f"{RU}/audio/voice/zh"
PREVIEW = f"{RU}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/ruth/MUSIC.md"
STRETCH = 0.30                 # every cue survives its section being stretched by at least this much (re-timing)
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -3.0             # loop section loudness relative to the cue's composed span

# extra GM programs (0-based)
VIOLA, ENGLISH_HORN, MUSIC_BOX, PAN_FLUTE = 41, 69, 10, 75

CH = dict(me.CH)
CH.update({"Bm": ["B2", "F#3", "B3", "D4"], "Em": ["E3", "B3", "E4", "G4"], "D/F#": ["F#2", "A3", "D4", "F#4"],
           "Gmaj7": ["G2", "D3", "F#3", "B3"], "Dmaj7": ["D3", "A3", "C#4", "F#4"], "Asus": ["A2", "E3", "A3", "D4"],
           "Cmaj7": ["C3", "G3", "B3", "E4"]})
def chord(name): return [note(p) for p in CH[name]]


# =============================================================================================== the Ruth theme
# Original. Written in D minor; tmode(..., major=True) gives the D major form (F->F#, C->C#, Bb->B).
RUTH_THEME = {
    1: [("A4", 1.5), ("D5", .5), ("E5", 1), ("F5", 1)],               # "where you go ..." (rising)
    2: [("E5", 1.5), ("D5", .5), ("C5", 1), ("A4", 1)],
    3: [("Bb4", 1), ("A4", .5), ("G4", .5), ("A4", 1), ("D5", 1)],
    4: [("E5", 2), ("A4", 2)],                                        # half cadence
    5: [("A4", 1.5), ("D5", .5), ("E5", 1), ("F5", 1)],
    6: [("G5", 1.5), ("F5", .5), ("E5", 1), ("D5", 1)],
    7: [("Bb4", 1), ("C5", 1), ("D5", .5), ("E5", .5), ("C#5", 1)],
    8: [("D5", 4)],
}
THEME_HARM_MINOR = {1: ["Dm"], 2: ["Am"], 3: ["Gm", "Dm"], 4: ["A"], 5: ["Dm"], 6: ["Gm", "Dm"], 7: ["Bb", "A"], 8: ["Dm"]}
THEME_HARM_MAJOR = {1: ["D"], 2: ["A"], 3: ["G", "D"], 4: ["A"], 5: ["D"], 6: ["G", "D"], 7: ["G", "A"], 8: ["D"]}
# 3/4 lullaby form (bars 1, 2, 7, 8 of the theme, re-barred)
THEME_34 = {1: [("A4", 1), ("D5", .5), ("E5", .5), ("F5", 1)], 2: [("E5", 1), ("D5", 1), ("A4", 1)],
            7: [("Bb4", .5), ("C5", .5), ("D5", .5), ("E5", .5), ("C#5", 1)], 8: [("D5", 3)]}
THEME_34_HARM = {1: ["D"], 2: ["A"], 7: ["G", "A"], 8: ["D"]}


def tmode(notes, major):
    """D minor spelling -> D major spelling (keeps rests, staccato / tremolo suffixes and grace notes)."""
    if not major: return list(notes)
    def conv(p):
        if p is None: return None
        p = re.sub(r"F(?=\d)", "F#", p); p = re.sub(r"C(?=\d)", "C#", p); return re.sub(r"Bb(?=\d)", "B", p)
    return [(conv(p), d) for p, d in notes]


def theme(bars, major, scale=1.0):
    out = []
    for k in bars: out += [(p, d * scale) for p, d in tmode(RUTH_THEME[k], major)]
    return out


def harm_at(part_fn, b0, harm, beats):
    """Call part_fn(beat, chord_name, dur) for a bar's chord list spread evenly over `beats`."""
    for i, h in enumerate(harm): part_fn(b0 + i * beats / len(harm), h, beats / len(harm))


# =============================================================================================== small helpers
def end_beats(s):
    """Beat where the composed cue's final chord stops: one beat past the span, overlapping the loop section."""
    return s.bars * s.bpb + 1.0


def bar_of(s, abs_t, default):
    b = s.at(abs_t)
    return default if b is None else int(b // s.bpb)


def lines_in(c, who=None):
    """(t, est. end) of the voice lines inside the cue (end from the timeline's maxSec estimate)."""
    out = []
    for e in c.tl.get("lines", []):
        if c.t - 1e-6 <= e["t"] <= c.t + c.span and (who is None or e["who"] == who):
            out.append((e["t"], e["t"] + e.get("maxSec", 4.0)))
    return sorted(out)


def pad(part, b, name, dur, vel=50, swell=(70, 105), voices=(1, 2, 3), strum=.03, curve=.8):
    """A sustained chord with an expression swell. Chords overlap the next one slightly so a pad never dips at a
    bar line, and only the first chord of a cue swells up from low (later ones start from >= 82)."""
    ps = chord(name); part.chord(b, [ps[i] for i in voices], dur + .25, vel, strum=strum)
    v0 = swell[0] if b < 0.5 else max(82, swell[0])
    part.ramp(b, b + max(.5, dur * .8), 11, v0, max(v0, swell[1]), curve)


# The macOS DLS bank, as FluidSynth loads it, gives every instrument a decaying volume envelope (sustain level 0):
# a held flute note is ~60 dB down after 2 s, a cello after 4 s (measured 2026-11-14). Real winds, bowed strings and
# voices sustain, so every such part gets an NRPN generator offset (SoundFont gen 37 volEnvSustain, -1440 cB) that
# restores a full sustain; phrasing then comes from note lengths, velocity and CC11, as a player would do it.
SUSTAIN = {STRINGS, SLOW_STR, TREM_STR, CELLO, VIOLA, CBASS, CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, ENGLISH_HORN,
           HORN, PAN_FLUTE}


def P(s, name, program, *a, **kw):
    p = s.part(name, program, *a, **kw)
    if program in SUSTAIN:
        d = 8192 - 1440                                     # NRPN data = 8192 + offset (scale 1 cB for gen 37)
        p.cc(0, 99, 120); p.cc(0, 98, 37); p.cc(0, 6, d >> 7); p.cc(0, 38, d & 127)
    return p


FRAME = {"D": (LO_CONGA, 84), "t": (MUTE_CONGA, 52), "k": (OPEN_CONGA, 34), "s": (TAMB, 26)}
HAND = {"D": (LO_CONGA, 92), "O": (OPEN_CONGA, 78), "t": (MUTE_CONGA, 60), "k": (HI_BONGO, 56), "b": (LO_BONGO, 66)}


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- road_sad
LAMENT = [
    [("A4^Bb4", 2), ("G4", 1), ("F4", 1), ("E4", 1.5), ("F4", .5), ("D4", 2)],
    [("F4", 1), ("G4", 1), ("A4^Bb4", 2.5), ("G4", .5), ("F4", .5), ("E4", .5), ("F4", 2)],
    [("D5^E5", 2), ("C#5", 1), ("Bb4", 1), ("A4", 3), (None, 1)],
    [("G4", 1), ("F4", .5), ("E4", .5), ("F4", 1), ("E4", 1), ("D4", 4)],
]
LAMENT_HARM = ["Dm", "Dm", "Bb", "A", "Gm", "Dm", "Bb", "A"]


def cue_road_sad(c):
    """D minor, very slow. A duduk-like reed (English horn + a breath of clarinet, grace notes, delayed vibrato) sings
    a lament over a low string pad, contrabass and sparse harp. From Ruth's line the reed falls silent and the solo
    cello introduces the Ruth theme (bars 1-3, rubato-scaled so its last note lands on the hug), the pad follows the
    theme's harmony and the hug resolves to D major (Picardy third) with a harp roll."""
    s = Score(c, 56, 4); total = s.bars * 4; E = end_beats(s)
    reed = P(s, "reed (eng horn)", ENGLISH_HORN, -1, .42, lp=4200, human=.012)
    reed2 = P(s, "reed breath (clar)", CLARINET, -13, .4, lp=3000, human=.012)
    vc = P(s, "cello theme", CELLO, -1, .4, lp=4500, human=.01)
    padp = P(s, "low strings", SLOW_STR, -3, .5, lp=3200)
    vln = P(s, "violins (hug)", STRINGS, -9, .55, lp=5000)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1200)
    harp = P(s, "harp", HARP, -10, .45, human=.008)
    oohs = P(s, "oohs", OOHS, -20, .6, lp=4000)
    ruth = c.first("lines", who="ruth"); hug = c.first("sfx", id="soft_chime") or c.first("acting", who="ruth", clip="hug")
    tb0 = s.at(ruth); te = s.at(hug)
    tb0 = math.floor(tb0 - 1) if tb0 is not None else total - 12
    te = te if te is not None and te > tb0 + 6 else total - 1
    # choose which theme bars fit between Ruth's line and the hug (scaled 0.8-1.25)
    best = None
    for bars in ([1, 2, 3], [1, 3], [1]):
        k = (te - tb0) / (4 * len(bars))
        if 0.8 <= k <= 1.25 or bars == [1]: best = (bars, min(1.25, max(0.6, k))); break
    tbars, k = best
    # --- lament (before the theme)
    b = 0.0; i = 0
    while b < tb0 - 1:
        ph = LAMENT[i % len(LAMENT)]; L = sum(d for _, d in ph)
        if b + L > tb0 + .5:                       # cut the phrase so it ends before the theme
            cut, acc = [], 0
            for p, d in ph:
                if acc + d > tb0 - b - .5: break
                cut.append((p, d)); acc += d
            ph = cut
        mel(reed, b, ph, 70 - 4 * (i % 2), legato=.97, vib=True); mel(reed2, b, ph, 50, legato=.97)
        b += L + (1 if i % 2 else 0); i += 1
    for bar in range(int(math.ceil(tb0 / 4))):
        h = LAMENT_HARM[bar % len(LAMENT_HARM)]; ps = chord(h); bb = bar * 4
        pad(padp, bb, h, min(4, tb0 - bb + .5), 46 + 4 * (bar % 2), (60, 96))
        cb.add(bb, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], 4, 54)
        harp.add(bb, ps[0], 3, 48); harp.add(bb + 1.5, ps[1] + 12, 2.5, 36)
        if bar % 2 == 0: oohs.chord(bb, [ps[1], ps[3]], 8, 36)
    # --- Ruth theme on cello (an octave below written), minor, rubato-scaled
    mel(vc, tb0, theme(tbars, False, k), 76, legato=.98, vib=True, shift=-12)
    for j, tb in enumerate(tbars):
        bb = tb0 + j * 4 * k
        harm_at(lambda bt, h, d: (pad(padp, bt, h, d + .1, 52, (75, 108)),
                                  cb.add(bt, chord(h)[0] - 12 if chord(h)[0] - 12 >= note("C2") else chord(h)[0], d, 58)),
                bb, THEME_HARM_MINOR[tb], 4 * k)
    # --- the hug: D major with a harp roll, held to the end of the file
    vc.add(te, "D4", E - te, 70); vc.vibrato(te, E - te, 30)
    pad(padp, te, "D", E - te, 58, (70, 112)); cb.add(te, "D2", E - te, 60)
    vln.chord(te, ["A4", "D5", "F#5"], E - te, 44, strum=.05); vln.ramp(te, te + 2, 11, 50, 100)
    for j, p in enumerate(["D3", "A3", "D4", "F#4", "A4", "D5", "F#5"]): harp.add(te + j * .12, p, 4, 58 - j * 2)
    return s


# ----------------------------------------------------------------------------------------------- journey
J_ANS = [[(None, 2), ("A5", .5), ("B5", .5), ("C6", .5), ("A5", .5)], [("G5", 1.5), ("E5", .5), ("D5", 2)],
         [(None, 2), ("F5", .5), ("G5", .5), ("A5", .5), ("C6", .5)], [("B5", 1), ("A5", 1), ("A5", 2)]]
WALK_HARM = ["Dm", "C", "Dm", "G"]
SAD_HARM = ["Bb", "Gm", "A", "A"]
HOPE_HARM = ["D", "G", "D", "A", "D"]


def oud_riff(oud, b, name, vel=1.0):
    ps = chord(name)
    for i, idx in enumerate([0, 1, 2, 1, 3, 1, 2, 1]):
        oud.add(b + i * .5, ps[idx], .45, (78 if i in (0, 4) else 58) * vel)


def cue_journey(c):
    """D Dorian walking: a plucked oud-like ostinato (nylon guitar + koto) and a frame drum walk, flute answers in the
    gaps. Naomi's "I came home with nothing" empties it to a soft pad and a cello sigh; when Ruth cheers her up the
    walk returns in D major and the flute hints the Ruth theme's opening, ending on D."""
    s = Score(c, 96, 4); n = s.bars; E = end_beats(s)
    oud = P(s, "oud (nylon)", NYLON, -3, .3, human=.007)
    qk = P(s, "qanun (koto)", KOTO, -5, .3, human=.006)
    fl = P(s, "flute", FLUTE, -4, .45, human=.008)
    padp = P(s, "strings", SLOW_STR, -8, .5, lp=4000)
    vc = P(s, "cello sigh", CELLO, -5, .42, lp=4000)
    pz = P(s, "pizz bass", PIZZ, -6, .25)
    dr = P(s, "frame drum", DRUMS, -9, .2, lp=3200, human=.005)
    sad_b = bar_of(s, c.first("lines", who="naomi"), n)
    hope_b = bar_of(s, c.first("acting", who="ruth", clip="cheer_up") or c.first("lines", who="ruth"), n)
    sad_b = min(sad_b, n - 1); hope_b = int(np.clip(hope_b, sad_b, n - 1))
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        if bar < sad_b:
            h = WALK_HARM[bar % 4]; oud_riff(oud, b, h, .9 if bar else .75)
            if bar % 2: qk.chord(b, [chord(h)[2] + 12, chord(h)[3] + 12], 1, 40)
            pz.add(b, chord(h)[0] - 12, .5, 70); pz.add(b + 2, chord(h)[1] - 12, .5, 60)
            groove(dr, b, "D.tkD.tk" if bar % 4 != 3 else "D.tkDktk", .5, FRAME, .85)
            if bar >= 1: mel(fl, b, J_ANS[(bar - 1) % 4], 62, vib=True)
            pad(padp, b, h, 4, 34, (55, 80))
        elif bar < hope_b:
            h = SAD_HARM[(bar - sad_b) % 4]
            pad(padp, b, h, 4.2, 46, (60, 100)); vc.add(b + 1, chord(h)[3] - 12, 2.5, 58); vc.vibrato(b + 1, 2.5, 30)
            if bar == sad_b: oud.add(b, "D3", 2, 50)
        else:
            j = bar - hope_b; h = "D" if final else HOPE_HARM[j % len(HOPE_HARM)]
            if not final:
                oud_riff(oud, b, h, .8 + .05 * min(j, 3))
                groove(dr, b, "D.tkD.tk", .5, FRAME, .8 + .05 * min(j, 3))
                pz.add(b, chord(h)[0] - 12, .5, 66); pz.add(b + 2, chord(h)[1] - 12, .5, 58)
                pad(padp, b, h, 4, 40, (60, 95))
            if j == 0: mel(fl, b, tmode(RUTH_THEME[1], True), 64, vib=True)
            elif j == 1 and not final: mel(fl, b, [("E5", 1.5), ("D5", .5), ("C#5", 1), ("A4", 1)], 58, vib=True)
            if final:
                ps = chord("D"); padp.chord(b, ps[1:], E - b, 46); padp.ramp(b, b + 3, 11, 70, 100)
                pz.add(b, "D2", 1, 70); oud.chord(b, ["D3", "A3", "D4", "F#4"], 3, 64, strum=.04)
                fl.add(b, "D5" if j else "F#5", E - b - .5, 56); fl.vibrato(b, E - b - .5, 30); dr.add(b, LO_CONGA, 1, 60)
    return s


# ----------------------------------------------------------------------------------------------- field (6/8)
FIELD_HARM = ["G", "C", "G", "D", "Em", "C", "D", "G"]
FIELD_TUNE = [[("B4", 2), ("C5", 1), ("D5", 2), ("G5", 1)], [("F#5", 2), ("E5", 1), ("D5", 3)],
              [("E5", 2), ("D5", 1), ("C5", 2), ("A4", 1)], [("B4", 2), ("A4", 1), ("G4", 3)]]


def cue_field(c):
    """G major pastoral in 6/8 (counted in eighths): harp + koto rocking arpeggios, light frame drum and shaker, a
    flute tune before the narration, then only long soft flute notes under it; the tune's ending comes back in the
    last two bars. Clarinet and strings hold the middle."""
    s = Score(c, 200, 6); n = s.bars; E = end_beats(s)
    harp = P(s, "harp", HARP, -4, .4, human=.007)
    qk = P(s, "koto", KOTO, -12, .35, human=.006)
    fl = P(s, "flute", FLUTE, -3, .45, human=.008)
    cl = P(s, "clarinet", CLARINET, -10, .4, lp=3500)
    padp = P(s, "strings", SLOW_STR, -10, .5, lp=4500)
    cb = P(s, "contrabass", CBASS, -11, .3, lp=1200)
    dr = P(s, "frame drum", DRUMS, -12, .2, lp=3000, human=.005)
    narr_b = bar_of(s, c.first("lines", who="narrator"), n)
    seq = me.fill_phrase(n, 8, 1)
    for bar in range(n):
        b = bar * 6; h = FIELD_HARM[seq[bar]] if not bar == n - 1 else "G"; ps = chord(h); final = bar == n - 1
        for i, idx in enumerate([0, 1, 2, 3, 2, 1] if not final else [0, 1, 2, 3]):
            harp.add(b + i, ps[idx] + 12, 2.2, 60 if i in (0, 3) else 46)
        if bar % 2 == 1: qk.add(b + 3, ps[3] + 12, 2, 42)
        cb.add(b, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], 6 if not final else E - b, 50)
        pad(padp, b, h, 6 if not final else E - b, 36, (55, 85))
        if bar < max(1, narr_b) or bar >= n - 2:
            k = bar if bar < narr_b else (2 + bar - (n - 2))
            mel(fl, b, FIELD_TUNE[k % 4], 70, vib=True)
        elif bar % 2 == 0:
            fl.add(b, ps[3] + 24 if ps[3] + 24 <= note("A5") else ps[3] + 12, 11, 44); fl.vibrato(b, 11, 25)
            cl.add(b + 3, ps[1], 8, 44)
        if not final: groove(dr, b, "D..t.k", 1, {**FRAME, "s": (SHAKER, 20)}, .8); dr.add(b + 4.5, SHAKER, .4, 22)
        else: dr.add(b, LO_CONGA, 1, 56)
    harp.chord((n - 1) * 6 + 3, ["G4", "B4", "D5", "G5"], E - (n - 1) * 6 - 3, 46, strum=.08)
    return s


# ----------------------------------------------------------------------------------------------- boaz
BOAZ_TUNE = [[("D4", 1), ("G4", 1), ("A4", .5), ("B4", .5), ("A4", 1)], [("G4", 1.5), ("E4", .5), ("D4", 2)],
             [("E4", 1), ("G4", 1), ("C5", 1), ("B4", .5), ("A4", .5)], [("B4", 1.5), ("A4", .5), ("G4", 2)]]
BOAZ_HARM = [["G"], ["C", "G"], ["C", "D"], ["D", "G"]]


def cue_boaz(c):
    """Boaz, G major, kind and steady. A low clarinet tune (original) over warm strings and a walking pizz bass;
    frame drum, tambourine and a horn swell join on his hearty greeting. On "Who's that?" it stops on a suspended
    Cmaj7 with a rising harp question. When he talks kindly the tune comes back softer with a cello counter-line;
    at his blessing (hand on heart) the strings swell and the flute sings the Ruth theme's opening in G, ending on G."""
    s = Score(c, 78, 4); n = s.bars; E = end_beats(s)
    cl = P(s, "clarinet tune", CLARINET, -1, .38, lp=4500, human=.009)
    bsn = P(s, "bassoon double", BASSOON, -15, .35, lp=2500)
    vc = P(s, "cello counter", CELLO, -6, .42, lp=4000)
    padp = P(s, "strings", SLOW_STR, -4, .5, lp=4500)
    hn = P(s, "horns", HORN, -12, .45, lp=3000)
    pz = P(s, "pizz bass", PIZZ, -5, .25)
    harp = P(s, "harp", HARP, -8, .45, human=.007)
    fl = P(s, "flute", FLUTE, -4, .48)
    dr = P(s, "frame drum", DRUMS, -6, .2, lp=3000, human=.005)
    greet_b = bar_of(s, c.first("acting", who="boaz", clip="greet"), n)
    cur_t = c.first("acting", who="boaz", clip="look_curious"); cur_b = bar_of(s, cur_t, n)
    kind_t = next((t for t in sorted(c.all("acting", who="boaz", clip="talk_kind")) if cur_t is None or t > cur_t), None)
    kind_b = bar_of(s, kind_t, n)
    if kind_b <= cur_b: kind_b = min(n, cur_b + 2)
    heart_b = bar_of(s, c.first("acting", who="boaz", clip="hand_on_heart"), n)
    heart_b = max(heart_b, kind_b)
    if heart_b >= n - 1: heart_b = max(kind_b, n - 3)
    tune_i = 0
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        if final:
            ps = chord("G"); padp.chord(b, ps[1:], E - b, 54); padp.ramp(b, b + 3, 11, 80, 110)
            pz.add(b, "G2", 1, 66); vc.add(b, "G2", E - b, 54)
            harp.chord(b, ["G3", "D4", "G4", "B4", "D5", "G5"], E - b, 52, strum=.09)
            fl.add(b, "G5", E - b - .5, 58); fl.vibrato(b, E - b - .5, 30); hn.chord(b, ["G3", "B3", "D4"], E - b, 44)
            continue
        if bar < cur_b or bar >= kind_b and bar < heart_b:
            soft = bar >= kind_b; k = tune_i % 4; tune_i += 1
            mel(cl, b, BOAZ_TUNE[k], 66 if soft else 74, vib=True)
            if not soft: mel(bsn, b, BOAZ_TUNE[k], 50, shift=-12)
            harm_at(lambda bt, h, d: pad(padp, bt, h, d, 44 if soft else 40, (65, 100)), b, BOAZ_HARM[k], 4)
            for q in range(4):
                h = BOAZ_HARM[k][min(q // 2, len(BOAZ_HARM[k]) - 1)]; ps = chord(h)
                pz.add(b + q, [ps[0], ps[1], ps[2], ps[1]][q] - 12, .6, 64 if q == 0 else 52)
            if soft:
                for i in range(8): harp.add(b + i * .5, chord(BOAZ_HARM[k][0])[[0, 1, 2, 3, 2, 3, 2, 1][i]] + 12, 1.2, 44)
                vc.add(b, chord(BOAZ_HARM[k][-1])[3] - 12, 4, 46); vc.vibrato(b, 4, 25)
            elif bar >= greet_b:
                groove(dr, b, "D.t.k.t.", .5, FRAME, .8); dr.add(b + 1, TAMB, .3, 34); dr.add(b + 3, TAMB, .3, 30)
                if bar == greet_b: hn.chord(b, ["G3", "B3", "D4"], 4, 52); hn.ramp(b, b + 3, 11, 50, 110)
        elif bar < kind_b:                                                         # "who's that?"
            pad(padp, b, "Cmaj7", 4.1, 52, (80, 96)); vc.add(b, "E3", 4.2, 44)
            if bar == cur_b:
                for i, p in enumerate(["C4", "E4", "G4", "B4", "D5"]): harp.add(b + .5 + i * .5, p, 2.5, 48 + i * 2)
                pz.add(b, "C3", .5, 54)
            else:
                pz.add(b, "D3", .5, 50); pz.add(b + 2, "A2", .5, 46); harp.add(b + 2, "F#4", 2, 42)
        else:                                                                      # blessing: theme hint in G
            j = bar - heart_b
            if j == 0: mel(fl, b, tmode(RUTH_THEME[1], True), 66, vib=True, shift=-7)
            elif j == 1: mel(fl, b, [("A4", 1.5), ("G4", .5), ("F#4", 1), ("D4", 1)], 60, vib=True, shift=0)
            h = ["G", "D", "C", "D"][j % 4]
            pad(padp, b, h, 4.1, 56, (70, 118)); vc.add(b, chord(h)[0], 4, 54)
            for i in range(8): harp.add(b + i * .5, chord(h)[[0, 1, 2, 3, 2, 3, 2, 1][i]] + 12, 1.2, 46)
            hn.chord(b, [chord(h)[1], chord(h)[3]], 4, 40); pz.add(b, chord(h)[0] - 12, .6, 56)
    return s


# ----------------------------------------------------------------------------------------------- sneaky
SNEAK = [[("D4.", .5), (None, .5), ("F4.", .5), (None, .5), ("A4.", .5), ("G#4.", .5), ("A4.", .5), (None, .5)],
         [("Bb4.", .5), (None, .5), ("A4.", .5), (None, .5), ("G4.", .5), ("F4.", .5), ("E4.", .5), (None, .5)],
         [("D4.", .5), (None, .5), ("F4.", .5), (None, .5), ("C5.", .5), ("B4.", .5), ("C5.", .5), (None, .5)],
         [("A4.", .5), ("F4.", .5), ("E4.", .5), ("C#4.", .5), ("D4.", .5), (None, 1.5)]]


def cue_sneaky(c):
    """Comic tiptoe in D minor: staccato pizzicato line doubled by a sneaky bassoon, wood-block tiptoes on the
    off-beats, pizz bass. Two clarinet "peeks" when Boaz glances left and right; a bassoon "heh-heh" on his chuckle;
    a xylophone tumble down when the stalks drop; a cheeky D major ta-da on the last beat."""
    s = Score(c, 116, 4); n = s.bars; total = n * 4; E = end_beats(s)
    pz = P(s, "pizz tune", PIZZ, -2, .25, human=.006)
    bsn = P(s, "bassoon", BASSOON, -5, .25, human=.006)
    cl = P(s, "clarinet peeks", CLARINET, -6, .3)
    pzb = P(s, "pizz bass", PIZZ, -7, .22)
    xy = P(s, "xylophone", XYLO, -6, .3)
    wb = P(s, "wood blocks", DRUMS, -7, .18, human=.004)
    peek = s.at(c.first("acting", who="boaz", clip="sneaky_drop"))
    chuck = s.at(c.first("acting", who="boaz", clip="chuckle"))
    drop = s.at(c.first("sfx", id="stalks_drop"))
    tada = total - 1
    for bar in range(n):
        b = bar * 4
        if b >= tada: break
        mel(pz, b, SNEAK[bar % 4], 76 if bar % 2 == 0 else 70)
        if bar % 2 == 0: mel(bsn, b, SNEAK[bar % 4], 56, shift=-12)
        pzb.add(b, "D2", .4, 66); pzb.add(b + 2, "A1", .4, 58)
        for q in range(4):
            if b + q + .5 < tada: wb.add(b + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 40)
    if peek is not None and peek + 1.5 < tada:
        cl.add(peek, "A5", .18, 58); cl.add(peek - .08, "G#5", .1, 44)
        cl.add(peek + 1, "F5", .18, 58); cl.add(peek + .92, "E5", .1, 44)
    if chuck is not None and chuck + 1 < tada:
        for i, p in enumerate(["A3.", "A3.", "F3."]): mel(bsn, chuck + i * .5, [(p, .5)], 70)
    if drop is not None and drop < tada:
        for i, p in enumerate(["D6", "C6", "A5", "G5", "F5", "E5", "D5", "A4"]): xy.add(drop + i * .125, p, .3, 70 - i * 3)
    pz.chord(tada, ["D3", "A3", "D4", "F#4"], .4, 82, strum=.02); xy.chord(tada, ["D5", "F#5", "A5"], .5, 66)
    pzb.add(tada, "D2", .5, 76); wb.add(tada, HI_WOOD, .2, 60); bsn.add(tada, "D3", .4, 60)
    return s


# ----------------------------------------------------------------------------------------------- home
def cue_home(c):
    """Golden hour, D major: the Ruth theme in major. Cello and violas sing it softly under the dialogue (bars
    1, 2, 5, 6) over harp arpeggios and a warm pad; at Naomi's blessing (the sparkle) the violins and flute take the
    cadence (bars 7, 8) with horns and a soft timpani roll into a held D major chord."""
    s = Score(c, 72, 4); n = s.bars; E = end_beats(s)
    tb = [1, 2, 5, 6, 7, 8] if n >= 7 else ([1, 2, 7, 8] if n >= 5 else [7, 8])
    seq = [None] * max(0, n - len(tb)) + tb[-n:]
    vc = P(s, "cello+viola theme", CELLO, -1, .42, lp=4500, human=.01)
    va = P(s, "viola double", VIOLA, -9, .45, lp=4000)
    vln = P(s, "violins", STRINGS, -4, .55, lp=6000)
    fl = P(s, "flute", FLUTE, -6, .5)
    padp = P(s, "pad", SLOW_STR, -6, .5, lp=4000)
    hn = P(s, "horns", HORN, -11, .45, lp=3000)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1200)
    harp = P(s, "harp", HARP, -7, .45, human=.007)
    timp = P(s, "timpani", TIMPANI, -14, .35)
    bless_b = bar_of(s, c.first("sfx", id="sparkle") or c.first("acting", who="naomi", clip="bless_up"), n)
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1
        harm = THEME_HARM_MAJOR[k] if k else ["D"]
        loud = k in (7, 8) and bar >= min(bless_b, n - 2)
        if k:
            notes = tmode(RUTH_THEME[k], True)
            if loud:
                mel(vln, b, notes, 74, legato=.98); mel(fl, b, notes, 66, vib=True, shift=12 if k == 7 else 0)
            else:
                mel(vc, b, notes, 72, legato=.98, vib=True, shift=-12); mel(va, b, notes, 52, legato=.98)
        d_last = (E - b) if final else 4
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); d = 4 / len(harm) if not (final and i == len(harm) - 1) else E - hb
            ps = chord(h)
            pad(padp, hb, h, d + .05, 50 if not loud else 58, (70, 112 if loud else 100))
            cb.add(hb, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], d, 56)
            for j in range(int(min(d, 4 / len(harm)) * 2)):
                harp.add(hb + j * .5, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.3, 48 + (8 if j == 0 else 0))
            if loud: hn.chord(hb, [ps[1], ps[3]], d, 46)
        if final:
            vln.chord(b, ["A4", "D5", "F#5", "A5"], d_last, 54, strum=.05); vln.ramp(b, b + 3, 11, 70, 110)
            harp.chord(b + 2, ["D4", "F#4", "A4", "D5", "F#5", "A5"], d_last - 2, 50, strum=.08)
        if k == 7 and loud:
            for i in range(int(4 / .125)): timp.add(b + 2 + i * .0625, "A2", .1, 30 + 30 * i / 32)
            timp.add(b + 4, "D2", 2, 70)
    return s


# ----------------------------------------------------------------------------------------------- night
NIGHT_HARM = ["D", "Bm", "G", "Asus", "D", "Bm", "Gmaj7", "A"]
NIGHT_FL = [[(None, 2), ("F#5", 2)], [("E5", 1), ("D5", 1), ("B4", 2)], [(None, 2), ("A5", 1.5), ("G5", .5)], [("F#5", 4)]]


def cue_night(c):
    """Night, hushed D major: slow harp arpeggios, a very soft low string pad and contrabass, rare celesta stars, a
    single flute line in the gaps. On Boaz's promise the flute plays the Ruth theme's opening and settles on D."""
    s = Score(c, 66, 4); n = s.bars; E = end_beats(s)
    harp = P(s, "harp", HARP, -3, .5, human=.008)
    padp = P(s, "pad", SLOW_STR, -5, .55, lp=2600)
    cb = P(s, "contrabass", CBASS, -12, .35, lp=1000)
    fl = P(s, "flute", FLUTE, -5, .55, human=.009)
    cel = P(s, "celesta stars", CELESTA, -17, .7)
    oohs = P(s, "oohs", OOHS, -22, .6, lp=3500)
    prom_b = bar_of(s, c.first("lines", who="boaz"), n)
    prom_b = min(prom_b, n - 2)
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        h = "D" if final else NIGHT_HARM[bar % 8]; ps = chord(h); d = 4 if not final else E - b
        for j in range(8 if not final else 4):
            harp.add(b + j * .5, ps[[0, 1, 2, 3, 2, 3, 2, 1][j]] + 12, 1.6, 50 + (6 if j == 0 else 0) - (4 if j % 2 else 0))
        pad(padp, b, h, d + .05, 38, (50, 82)); cb.add(b, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], d, 46)
        if bar % 2 == 0: oohs.chord(b, [ps[1], ps[3]], min(8, d + 4), 32)
        if bar < prom_b: mel(fl, b, NIGHT_FL[bar % 4], 54, vib=True)
        elif bar == prom_b: mel(fl, b, tmode(RUTH_THEME[1], True), 58, vib=True)
        elif not final: mel(fl, b, [("E5", 1.5), ("D5", .5), ("C#5", 1), ("A4", 1)], 52, vib=True)
        else: fl.add(b, "D5", d - .5, 50); fl.vibrato(b, d - .5, 25); harp.add(b + 2, "D6", 3, 40)
        if bar % 3 == 1: cel.add(b + 2.5, ["A6", "F#6", "D7"][bar % 3], 2, 34)
    return s


# ----------------------------------------------------------------------------------------------- wedding
WED_TUNE = [[("D5", .5), ("E5", .5), ("F#5", .5), ("A5", .5), ("G5", .5), ("F#5", .5), ("E5", 1)],
            [("F#5", .5), ("G5", .5), ("A5", .5), ("B5", .5), ("A5", 1), ("F#5", 1)],
            [("G5", .5), ("F#5", .5), ("E5", .5), ("D5", .5), ("C#5", .5), ("D5", .5), ("E5", .5), ("A4", .5)],
            [("D5", 1), ("F#5", .5), ("E5", .5), ("D5", 1), (None, 1)]]
WED_HARM = [["D"], ["D", "G"], ["G", "A"], ["D"]]


def cue_wedding(c):
    """D major wedding dance: congas/bongos, tambourine eighths, claps on 2 and 4, flute tune doubled by the qanun,
    oud off-beats, pizz bass; the flute steps back a little under the narration."""
    s = Score(c, 120, 4); n = s.bars; E = end_beats(s)
    fl = P(s, "flute", FLUTE, -3, .32, human=.006)
    qk = P(s, "qanun (koto)", KOTO, -9, .3, human=.006)
    oud = P(s, "oud offbeats", NYLON, -7, .28, human=.006)
    pz = P(s, "pizz bass", PIZZ, -4, .22)
    padp = P(s, "strings", SLOW_STR, -11, .48, lp=5000)
    hand = P(s, "hand drums", DRUMS, -5, .16, human=.004)
    claps = P(s, "claps", DRUMS, -4, .3, human=.009)
    narr = c.first("lines", who="narrator"); narr_b = s.at(narr) if narr else None
    seq = me.fill_phrase(n, 4, 1)
    for bar in range(n):
        b = bar * 4; k = seq[bar]; final = bar == n - 1
        v = 84 if narr_b is None or b + 4 <= narr_b else 72
        mel(fl, b, WED_TUNE[k], v); mel(qk, b, WED_TUNE[k], 58, shift=-12)
        for q in range(4):
            h = WED_HARM[k][min(q * len(WED_HARM[k]) // 4, len(WED_HARM[k]) - 1)]; ps = chord(h)
            pz.add(b + q, (ps[0] if q % 2 == 0 else ps[1]) - 12, .4, 80 if q == 0 else 64)
            oud.chord(b + q + .5, [ps[1], ps[2], ps[3]], .35, 56, strum=.02)
        padp.chord(b, chord(WED_HARM[k][0])[1:], 4 if not final else E - b, 40)
        groove(hand, b, "D.kOt.kOD.kOtkOk" if not final else "D.kOt.kObbOOtkkk", .25, HAND, swing=.08)
        for q in (1, 3):
            for _ in range(3): claps.add(b + q, CLAP, .3, 66)
        groove(hand, b, "SsSsSsSs", .5, {"S": (TAMB, 50), "s": (TAMB, 32)})
    b = n * 4; oud.chord(b, ["D3", "A3", "D4", "F#4"], E - b, 46, strum=.03)   # soft ring under the crossfade
    return s


# ----------------------------------------------------------------------------------------------- lullaby (3/4)
def cue_lullaby(c):
    """3/4 lullaby on the Ruth theme (bars 1, 2, 7, 8 re-barred): music box doubled by harp, the harp rocking
    root-chord-chord underneath, a soft string pad, a breath of flute on the last phrase."""
    s = Score(c, 80, 3); n = s.bars; E = end_beats(s)
    tb = [1, 2, 7, 8] if n >= 4 else [7, 8]
    seq = [None] * max(0, n - len(tb)) + tb[-n:]
    mb = P(s, "music box", MUSIC_BOX, -3, .5, human=.006)
    hm = P(s, "harp melody", HARP, -8, .45, human=.006)
    harp = P(s, "harp rocking", HARP, -7, .45, human=.008)
    padp = P(s, "pad", SLOW_STR, -11, .55, lp=3200)
    fl = P(s, "flute", FLUTE, -12, .55)
    for bar, k in enumerate(seq):
        b = bar * 3; final = bar == n - 1
        harm = THEME_34_HARM[k] if k else ["D"]
        if k:
            notes = tmode(THEME_34[k], True)
            mel(mb, b, notes, 68, shift=12); mel(hm, b, notes, 58)
            if k in (7, 8): mel(fl, b, notes, 46, vib=True)
        for i, h in enumerate(harm):
            ps = chord(h); hb = b + i * 2; d = (2 if len(harm) > 1 and i == 0 else 3 - 2 * i) if len(harm) > 1 else 3
            harp.add(hb, ps[0], 2, 52)
            for j in range(1, int(d)): harp.chord(hb + j, [ps[1] + 12, ps[3]], .9, 36, strum=.02)
            dd = d if not final else E - hb
            pad(padp, hb, h, dd + .05, 36, (50, 78))
        if final: harp.chord(b + 1, ["D4", "F#4", "A4", "D5"], E - b - 1, 40, strum=.1); mb.add(b + 1.5, "A6", 2, 40)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """The Ruth theme in full, D major (bars 1, 2, 5, 6, 7, 8) and a held final chord. Starts intimate (cello +
    harp + pad under the narrator's reveal), then at the golden rays the violins and flute take the tune with horns,
    oohs, a soft frame-drum heartbeat and a timpani roll into the cadence; celesta sparkle on the last D major chord,
    which fades by itself (last cue)."""
    s = Score(c, 82, 4); n = s.bars; E = end_beats(s)
    tb = [1, 2, 5, 6, 7, 8]
    seq = (tb + [None])[:n] if n >= 7 else tb[-n:]
    vc = P(s, "cello", CELLO, -2, .42, lp=4500, human=.01)
    vln = P(s, "violins", STRINGS, -2, .55, lp=6500)
    fl = P(s, "flute", FLUTE, -4, .5)
    padp = P(s, "pad", SLOW_STR, -5, .5, lp=4500)
    hn = P(s, "horns", HORN, -9, .45, lp=3200)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1200)
    harp = P(s, "harp", HARP, -6, .45, human=.007)
    oohs = P(s, "oohs", CHOIR, -16, .6, lp=4500)
    timp = P(s, "timpani", TIMPANI, -11, .35)
    dr = P(s, "frame drum", DRUMS, -13, .2, lp=2500, human=.005)
    cel = P(s, "celesta", CELESTA, -11, .6)
    rays_b = bar_of(s, c.first("fx", id="golden_rays"), n // 2)
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1; full = bar >= rays_b
        harm = THEME_HARM_MAJOR[k] if k else ["D"]
        if k:
            notes = tmode(RUTH_THEME[k], True)
            if full:
                mel(vln, b, notes, 76, legato=.98); mel(fl, b, notes, 70, vib=True, shift=12 if k in (5, 6) else 0)
                mel(vc, b, notes, 54, legato=.98, shift=-12)
            else:
                mel(vc, b, notes, 74, legato=.98, vib=True, shift=-12)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); last = final and i == len(harm) - 1
            d = E - hb if last else 4 / len(harm); ps = chord(h)
            pad(padp, hb, h, d + .05, 50 if not full else 60, (70, 115 if full else 100))
            cb.add(hb, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], d, 58)
            for j in range(int(min(d, 4 / len(harm)) * 2)):
                harp.add(hb + j * .5, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.3, 50 + (8 if j == 0 else 0))
            if full: hn.chord(hb, [ps[1], ps[2], ps[3]], d, 48); oohs.chord(hb, [ps[1] + 12, ps[3]], d, 40)
        if full and not final and k != 7: groove(dr, b, "D...D.t.", .5, FRAME, .8)
        if k == 7:
            for i in range(32): timp.add(b + 2 + i * .0625, "A2", .1, 34 + 34 * i / 32)
            timp.add(b + 4, "D2", 3, 76)
        if final:
            vln.chord(b, ["D5", "F#5", "A5", "D6"], E - b, 58, strum=.04); vln.ramp(b, E, 11, 110, 70)
            for i, p in enumerate(["D6", "F#6", "A6", "D7"]): cel.add(b + 1 + i * .25, p, 3, 54 - i * 3)
            harp.chord(b + .5, ["D3", "A3", "D4", "F#4", "A4", "D5", "F#5", "A5", "D6"], E - b, 52, strum=.07)
    return s


# =============================================================================================== loop section
# After its cadence at the span end every cue continues into a quiet "vamp" on its final chord: identical repeats of
# VAMP_MIN_SEC+ (whole bars, no humanising so the repeats are sample-identical apart from the first one, which carries
# the cadence's release and reverb). cues.json marks the second repeat as the seamless loop (loopStart / loopEnd); the
# repeats after it give at least +30 % of the span as a plain tail for players that cannot loop.
VAMP = {"road_sad": ("D", "bed"), "journey": ("D", "pluck"), "field": ("G", "bed"), "boaz": ("G", "bed"),
        "sneaky": ("Dm", "tiptoe"), "home": ("D", "bed"), "night": ("D", "bed"), "wedding": ("D", "dance"),
        "lullaby": ("D", "bed"), "finale": ("D", "bells")}


def arp_steps(s):
    return (s.bpb * 2, .5) if s.bpb in (3, 4) else (s.bpb, 1.0)


def add_vamp(s, chord_name, style):
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    reps = max(4, math.ceil((STRETCH * s.span + XFADE + 2.5) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    padp = P(s, "vamp pad", SLOW_STR, -6, .5, lp=3500, **v); cb = P(s, "vamp bass", CBASS, -10, .3, lp=1100, **v)
    harp = P(s, "vamp harp", HARP, -8, .45, **v)
    for p_ in (padp, cb, harp): p_.vamp = True
    extra = {}
    if style in ("pluck", "dance"):
        extra["oud"] = P(s, "vamp oud", NYLON, -10, .3, **v); extra["dr"] = P(s, "vamp drum", DRUMS, -14, .2, lp=3000, **v)
    if style == "dance": extra["pz"] = P(s, "vamp pizz", PIZZ, -8, .22, **v)
    if style == "tiptoe":
        extra["pz"] = P(s, "vamp pizz", PIZZ, -6, .25, **v); extra["wb"] = P(s, "vamp blocks", DRUMS, -14, .18, **v)
    if style == "bells": extra["cel"] = P(s, "vamp celesta", CELESTA, -16, .6, **v)
    for p_ in extra.values(): p_.vamp = True
    ps = chord(chord_name); steps, st = arp_steps(s); b0 = s.bars * bpb
    for r in range(reps):
        b = b0 + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 46 if style != "tiptoe" else 34); padp.cc(b, 11, 92)
        cb.add(b, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], Lb + .2, 48)
        for bar in range(nb):
            bb = b + bar * bpb
            if style in ("bed", "bells", "pluck"):
                for j in range(steps): harp.add(bb + j * st, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.4, 44 if j else 50)
            if style == "pluck":
                for j, idx in enumerate([0, 1, 2, 1, 3, 1, 2, 1]): extra["oud"].add(bb + j * .5, ps[idx], .45, 52 if j % 4 == 0 else 40)
                groove(extra["dr"], bb, "D...D.t.", .5, FRAME, .6)
            if style == "dance":
                for q in range(4):
                    extra["pz"].add(bb + q, (ps[0] if q % 2 == 0 else ps[1]) - 12, .4, 64)
                    extra["oud"].chord(bb + q + .5, ps[1:], .35, 46, strum=.02)
                groove(extra["dr"], bb, "D.kOt.kOD.kOtkOk", .25, HAND, .65); groove(extra["dr"], bb, "SsSsSsSs", .5, {"S": (TAMB, 36), "s": (TAMB, 24)})
            if style == "tiptoe":
                for q, pt in enumerate(["D3", "A3", "F3", "A3"]): extra["pz"].add(bb + q, pt, .2, 54)
                for q in range(4): extra["wb"].add(bb + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 30)
        if style == "bells": extra["cel"].add(b + bpb, "A6", 2, 34)
    s.secs = s.span + reps * L + 2.5
    s.vamp = dict(start=s.span, secs=L, reps=reps, bars=nb, chord=chord_name, style=style)


def render_split(s):
    """Score.render, but the cue and its loop section come back separately (each with its own hall send)."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex: stems = list(ex.map(lambda p: p.render(), s.parts))
    n = max(len(x) for x in stems); out = {}
    for key in (False, True):
        dry = np.zeros(n); bus = np.zeros(n)
        for p_, x in zip(s.parts, stems):
            if getattr(p_, "vamp", False) != key: continue
            dry[:len(x)] += x; bus[:len(x)] += x * p_.send
            if me.STEM_REPORT: print(f"    stem {p_.name:18s} rms {20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9):6.1f} dB")
        out[key] = dry + signal.fftconvolve(bus, me.IRS["hall"]())[:n]
    return out[False], out[True]


def clean_tmp():
    """music_kit's renderer leaves one temp dir per stem; keep ours in one run dir and empty it after each cue
    (a full unattended run otherwise leaks several GB)."""
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith("music_ruth_"):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def lufs_of(x):
    tmp = tempfile.mkdtemp() + "/m.wav"; wavfile.write(tmp, SR, np.asarray(x, np.float32)); return me.measure(tmp)


MUSIC = {"road_sad": cue_road_sad, "journey": cue_journey, "field": cue_field, "boaz": cue_boaz, "sneaky": cue_sneaky,
         "home": cue_home, "night": cue_night, "wedding": cue_wedding, "lullaby": cue_lullaby, "finale": cue_finale}
METER = {"field": "6/8, ♪ =", "lullaby": "3/4"}
KEYS = {"road_sad": "D minor -> D major", "journey": "D Dorian -> D major", "field": "G major", "boaz": "G major",
        "sneaky": "D minor -> D major ta-da", "home": "D major", "night": "D major", "wedding": "D major",
        "lullaby": "D major", "finale": "D major"}
CUE_NOTES = {
    "road_sad": "Duduk-like reed (English horn + clarinet breath, grace notes) laments over low strings, contrabass, sparse harp; from Ruth's line the solo cello introduces the Ruth theme (minor, bars 1-3 rubato-fitted to the hug); D major Picardy chord + harp roll on the hug.",
    "journey": "Plucked oud-like ostinato (nylon + koto) and frame-drum walk, flute answers; empties to pad + cello sigh under Naomi's 'nothing'; returns in D major from Ruth's cheer-up with the theme's opening on flute; ends on D.",
    "field": "6/8 pastoral: harp/koto rocking arpeggios, frame drum + shaker, flute tune before the narration, long flute/clarinet notes under it, tune's ending in the last bars.",
    "boaz": "Boaz's own tune (low clarinet + bassoon) over warm strings and walking pizz; drum, tambourine, horn swell at his greeting; suspended Cmaj7 + harp question at 'Who's that?'; softer tune + cello counter when kind; strings swell and the flute sings the Ruth theme's opening in G at his blessing.",
    "sneaky": "Staccato pizz tiptoe + bassoon, wood blocks; clarinet peeks at the glances, bassoon 'heh-heh' at the chuckle, xylophone tumble at the stalks drop, D major ta-da.",
    "home": "Ruth theme in D major: cello/viola under the dialogue over harp arpeggios; violins + flute + horns take the cadence at Naomi's blessing, timpani roll, held D chord.",
    "night": "Hushed: harp arpeggios, very soft pad and contrabass, celesta stars, flute in the gaps; flute plays the Ruth theme's opening on Boaz's promise and settles on D.",
    "wedding": "Wedding dance: congas/bongos, tambourine, claps on 2 and 4, flute + qanun tune, oud off-beats, pizz bass.",
    "lullaby": "Music box + harp sing the Ruth theme in 3/4 over a rocking harp and soft pad; flute breath on the last phrase.",
    "finale": "Full Ruth theme (bars 1, 2, 5, 6, 7, 8): cello + harp under the reveal, then violins/flute/horns/oohs from the golden rays, timpani roll into the cadence, celesta on the held D major chord, then the loop bed.",
}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG


def tone(secs, f_curve, amp, h2=0.0):
    ph = 2 * np.pi * np.cumsum(f_curve) / SR
    return amp * (np.sin(ph) + h2 * np.sin(2 * ph))


def sfx_soft_chime(ctx):
    """The hug: three soft, warm chime notes (A5, D6, F#6) with felt strikes and a little air."""
    secs = 2.8; n = int(secs * SR); y = np.zeros(n)
    for i, (p, a) in enumerate((("A5", 1.0), ("D6", .85), ("F#6", .7))):
        f = 440 * 2 ** ((note(p) - 69) / 12)
        b = me.partials(2.6, f, [1, 2.0, 2.76, 4.1], [1, .25, .18, .06], [1.4, .7, .5, .25])
        b *= np.minimum(1, np.arange(len(b)) / SR / .004)
        me.place(y, b * a, .02 + i * .16 + R().normal(0, .006))
    y += me.hp(noise(n), 5000) * np.exp(-((np.arange(n) / SR - .4) / .4) ** 2) * .03
    return me.fit(me.room(y, "hall", .35), secs, fade_out=.7)


def chirp(dur, f0, f1, curve=1.0, vib=(0, 0), amp=1.0):
    m = int(dur * SR); u = np.linspace(0, 1, m)
    f = f0 + (f1 - f0) * u ** curve
    if vib[1]: f = f * (1 + vib[1] * np.sin(2 * np.pi * vib[0] * np.arange(m) / SR))
    env = np.sin(np.pi * u) ** 1.5
    return tone(dur, f, amp, h2=.12) * env


LOOP_SECS = {"birds": 10.0, "crickets_dusk": 16.0, "crickets_night": 20.0}   # ambience beds = seamless loops
WRAP = 0.6                                                                        # s, loop wrap crossfade


def make_loop(y, secs):
    """y is secs + WRAP long; fold the overhang onto the start so the end flows into the beginning."""
    n, k = int(secs * SR), int(WRAP * SR); out = y[:n].copy(); w = np.linspace(0, 1, k)
    out[:k] = y[:k] * np.sqrt(w) + y[n:n + k] * np.sqrt(1 - w)
    return out


def sfx_birds(ctx):
    """Morning birds over the field (seamless 10 s loop): a warbler's bursts of descending whistles, a two-note
    'tee-oo' further off, a short trill, a breath of air; outdoors (almost no room)."""
    secs = LOOP_SECS["birds"]; tot = secs + WRAP; n = int(tot * SR); y = np.zeros(n)
    t = .15
    while t < tot - .4:                                    # warbler: bursts of 3-5 quick sweeps
        for k in range(int(R().integers(3, 6))):
            f0 = R().uniform(4200, 5600); me.place(y, chirp(R().uniform(.05, .08), f0, f0 * R().uniform(.55, .7), .7, amp=.8), t)
            t += R().uniform(.07, .1)
        t += R().uniform(.9, 1.6)
    for at in (0.9, 3.6, 7.2):                              # tee-oo, distant
        me.place(y, chirp(.16, 3300, 3500, amp=.35), at); me.place(y, chirp(.22, 2600, 2300, amp=.3), at + .2)
    for at in (2.4, 6.1): me.place(y, chirp(.5, 4800, 4600, vib=(28, .06), amp=.3), at)    # trill
    y = me.lp(y, 9000) + me.lp(noise(n), 400) * .01
    return make_loop(me.room(y, "room", .08)[:n], secs)


def straw_ticks(n, count, t0, t1, level, lo=1800, hi=8000):
    y = np.zeros(n)
    for _ in range(count):
        at = R().uniform(t0, t1); m = int(R().uniform(.002, .006) * SR)
        g = me.bp(noise(m + 64), lo, hi)[:m] * np.exp(-np.arange(m) / (m / 3))
        me.place(y, g * R().uniform(.3, 1.0) * level, at)
    return y


def sfx_rustle(ctx):
    """Ruth picks up stalks: a soft swish of dry barley and a crackle of straw grains."""
    secs = 1.3; n = int(secs * SR); t = np.arange(n) / SR
    sw = me.bp(noise(n), 700, 4500) * (np.exp(-((t - .35) / .18) ** 2) + .6 * np.exp(-((t - .75) / .15) ** 2)) * .25
    y = sw + straw_ticks(n, 90, .15, .95, .5)
    return me.fit(me.room(y, "room", .1), secs, fade_out=.3)


def sfx_stalks_drop(ctx):
    """A handful of barley stalks tumbles onto the stubble: short whoosh, a cascade of light straw taps, a soft
    bundle-on-earth thud."""
    secs = 1.4; n = int(secs * SR); t = np.arange(n) / SR
    wh = me.bp(noise(n), 500, 3500) * np.exp(-((t - .12) / .08) ** 2) * .3
    y = wh + straw_ticks(n, 70, .2, .5, .7) + straw_ticks(n, 30, .45, .9, .35, 1500, 6000)
    m = int(.25 * SR); tt = np.arange(m) / SR
    thud = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-tt / .04) + 70) / SR) * np.exp(-tt / .05) * .35
    me.place(y, thud + me.lp(noise(m), 600) * np.exp(-tt / .02) * .2, .24)
    return me.fit(me.room(y, "room", .12), secs, fade_out=.35)


def cricket(n, f, chirp_rate, pulses, level, start=0.0):
    """One field cricket: chirps of `pulses` short syllables (~16 ms at a 30 ms period) on a carrier `f`."""
    y = np.zeros(n); t = start
    syl = int(.016 * SR); u = np.arange(syl) / SR
    s_env = np.sin(np.pi * np.arange(syl) / syl) ** 2
    while t < n / SR - .3:
        ff = f * R().uniform(.995, 1.005)
        for p in range(pulses):
            me.place(y, (np.sin(2 * np.pi * ff * u) + .15 * np.sin(4 * np.pi * ff * u)) * s_env * level * R().uniform(.8, 1), t + p * .03)
        t += 1 / chirp_rate * R().uniform(.85, 1.15)
    return y


def crickets(sid, specs, air=.006, extra=None):
    secs = LOOP_SECS[sid]; tot = secs + WRAP; n = int(tot * SR); y = np.zeros(n)
    for f, rate, pulses, lvl, start in specs: y += me.lp(cricket(n, f, rate, pulses, lvl, start), 7000 if lvl > .3 else 4500)
    y += me.lp(noise(n), 300) * air
    if extra: extra(y)
    return make_loop(me.room(y, "room", .15)[:n], secs)


def sfx_crickets_dusk(ctx):
    """Evening (seamless 16 s loop): three crickets at different distances, sparse, warm still air."""
    return crickets("crickets_dusk", [(4400, 1.3, 3, .5, .4), (4750, 1.0, 4, .3, 1.1), (4100, .8, 3, .18, 2.0)])


def sfx_crickets_night(ctx):
    """Night (seamless 20 s loop): five crickets, denser and further off, and one soft distant owl."""
    def owl(y):
        for at in (9.0, 9.55):
            m = int(.4 * SR); tt = np.arange(m) / SR; f = 400 * (1 + .06 * np.sin(np.pi * tt / .4)) - 20 * tt
            h = tone(.4, f, 1.0, h2=.05) * np.sin(np.pi * tt / .4) ** 2 + me.lp(noise(m), 800) * .05
            me.place(y, me.lp(h, 1500) * .07, at)
    return crickets("crickets_night", [(4300, 1.6, 3, .4, .2), (4650, 1.2, 4, .3, .7), (4900, 2.0, 2, .2, 1.3),
                                       (4050, .9, 5, .16, 1.9), (4500, 1.4, 3, .12, 2.5)], air=.004, extra=owl)


def sfx_sparkle(ctx):
    """Naomi's blessing: Esther's shower of tiny bells (D major pentatonic), shared from music_kit."""
    return me.sfx_sparkle()


def sfx_cheer(ctx):
    """Wedding: Esther's crowd 'hooray' voices + clappers (shared synth, Ruth's own seed) with a few extra
    rhythmic claps on the dance beat."""
    y = me.sfx_cheer(); n = len(y)
    for k in range(10):
        at = .6 + k * .52
        for _ in range(4):
            m = int(.05 * SR); fc = R().uniform(1000, 2200)
            me.place(y, me.bp(noise(m), fc * .6, fc * 1.8) * me.env_exp(m, .009) * .12, at + R().normal(0, .012))
    return y[:n]


def jingle(level=1.0):
    m = int(.22 * SR); tt = np.arange(m) / SR; y = np.zeros(m)
    for _ in range(6):
        f = R().uniform(5200, 11000)
        y += np.sin(2 * np.pi * f * tt + R().uniform(0, 6)) * np.exp(-tt / R().uniform(.05, .12)) * R().uniform(.3, 1)
    y += me.hp(noise(m), 6000) * np.exp(-tt / .02) * .6
    return y * level


def sfx_tambourine(ctx):
    """A wedding tambourine flourish: a shake roll, a slap on the skin, then a trailing shake."""
    secs = 1.6; n = int(secs * SR); y = np.zeros(n)
    for i in range(9): me.place(y, jingle(.3 + .5 * i / 8), .02 + i * .04 + R().normal(0, .004))
    m = int(.12 * SR); tt = np.arange(m) / SR
    skin = np.sin(2 * np.pi * np.cumsum(260 * np.exp(-tt / .015) + 190) / SR) * np.exp(-tt / .04) * .6
    me.place(y, skin, .42); me.place(y, jingle(1.2), .42)
    for i in range(7): me.place(y, jingle(.6 * (1 - i / 7)), .62 + i * .06 + R().normal(0, .005))
    return me.fit(me.room(y, "room", .18), secs, fade_out=.4)


def sfx_baby_coo(ctx):
    """Soft twinkle for the baby (a synthetic baby voice sounded wrong): three music-box notes F#6 - A6 - D7 with a
    tiny shimmer."""
    secs = 2.4; n = int(secs * SR); y = np.zeros(n)
    for i, p in enumerate(["F#6", "A6", "D7"]):
        f = 440 * 2 ** ((note(p) - 69) / 12)
        b = me.partials(1.6, f, [1, 3.0, 5.2], [1, .18, .05], [.9, .3, .1], strike=.04)
        me.place(y, b * (.9 - i * .1), .03 + i * .2)
    for _ in range(14): me.place(y, me.partials(.25, R().uniform(7000, 10000), [1], [1], [.05]) * .08, R().uniform(.5, 1.4))
    return me.fit(me.room(y, "hall", .32), secs, fade_out=.6)


SFX = {"soft_chime": sfx_soft_chime, "birds": sfx_birds, "rustle": sfx_rustle, "stalks_drop": sfx_stalks_drop,
       "crickets_dusk": sfx_crickets_dusk, "crickets_night": sfx_crickets_night, "sparkle": sfx_sparkle,
       "cheer": sfx_cheer, "tambourine": sfx_tambourine, "baby_coo": sfx_baby_coo}
SFX_SEED = {"cheer": "ruth/cheer"}      # Ruth's crowd differs from Esther's
SFX_GAIN = {"soft_chime": -10, "birds": -16, "rustle": -12, "stalks_drop": -9, "crickets_dusk": -18,
            "crickets_night": -18, "sparkle": -9, "cheer": -7, "tambourine": -10, "baby_coo": -11}
SFX_NOTES = {"soft_chime": "three warm chime notes A5-D6-F#6, felt strikes, hall",
             "birds": "seamless 10 s loop: warbler sweeps, distant two-note 'tee-oo', trills; outdoors",
             "rustle": "dry barley swish + straw crackle",
             "stalks_drop": "whoosh, cascade of straw taps, soft thud on earth",
             "crickets_dusk": "seamless 16 s loop: 3 crickets, sparse, still air",
             "crickets_night": "seamless 20 s loop: 5 crickets + one distant owl",
             "sparkle": "Esther's D major pentatonic bell shower (shared synth)",
             "cheer": "Esther's crowd synth (own seed) + dance-beat claps",
             "tambourine": "shake roll, skin slap, trailing shake",
             "baby_coo": "soft music-box twinkle F#6-A6-D7 (no synthetic baby)"}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3), secs=round(end - c["t"] + XFADE, 3),
                        last=i + 1 == len(cues)))
    return out


def build_music(tl, only=None):
    spans = cue_spans(tl)
    names = [c["cue"] for c in spans]
    assert len(set(names)) == len(names), "a Ruth cue plays twice; add cue_files-style handling as in music_esther.py"
    missing = sorted(set(names) - set(MUSIC)); assert not missing, f"no composer for cue(s) {missing}"
    path_json = f"{MUSIC_DIR}/cues.json"
    old = {c["cue"]: c for c in json.load(open(path_json))["cues"]} if only and os.path.exists(path_json) else {}
    manifest = []
    for c in spans:
        if only and c["cue"] not in only and c["cue"] in old: manifest.append(old[c["cue"]]); continue
        me.seed("ruth/" + c["cue"]); ctx = Ctx(tl, c["cue"], c["t"], c["span"], c["secs"], c["last"])
        sc = MUSIC[c["cue"]](ctx)
        add_vamp(sc, *VAMP[c["cue"]]); vp = sc.vamp
        main, vamp = render_split(sc)
        n = int(round(sc.secs * SR)); main = me.hp(me.fit(main, sc.secs, fade_out=0), 28); vamp = me.hp(me.fit(vamp, sc.secs, fade_out=0), 28)
        ns, ls, le = int(c["span"] * SR), int(round((vp["start"] + vp["secs"]) * SR)), int(round((vp["start"] + 2 * vp["secs"]) * SR))
        # Loop tile: the second repeat as rendered (it already carries the first repeat's ringing tails, i.e. the
        # steady state), its first 30 ms blended from the third repeat's start (the true continuation of a repeat's
        # end). Tiling it from the span on makes every repeat sample-identical, so straight playback and a jump from
        # loopEnd to loopStart are the same continuous signal (FluidSynth's 64-sample event blocks otherwise shift
        # repeats by up to ~1 ms and click at the seam).
        L = le - ls; kx = int(.03 * SR); w = np.linspace(0, 1, kx)
        T = vamp[ls:le].copy(); T[:kx] = vamp[le:le + kx] * (1 - w) + vamp[ls:ls + kx] * w
        vs = np.zeros(n); p0 = ls - L
        for j in range(0, (n - p0) // L + 1):
            q = p0 + j * L; m_ = min(L, n - q)
            if m_ > 0: vs[q:q + m_] = T[:m_]
        kf = int(.5 * SR); main[ls - kf:ls] *= np.linspace(1, 0, kf) ** 2; main[ls:] = 0     # cue's ring ends before the loop
        gm = MUSIC_LUFS - lufs_of(main[:ns])["lufs"]                         # the composed span sits at -20 LUFS
        gv = MUSIC_LUFS + VAMP_REL_DB - lufs_of(T)["lufs"]                   # the loop section 3 dB under it
        x = main * 10 ** (gm / 20) + vs * 10 ** (gv / 20)
        if lufs_of(x)["truePeak"] > -1.3:                                    # rare transients: soft-clip under -1 dBTP
            cl = 10 ** (-1.6 / 20); x = np.tanh(x / cl) * cl                 # (memoryless, keeps the tiles identical)
        k = int(2.5 * SR); x[-k:] *= np.linspace(1, 0, k) ** 2                # end of the plain tail
        path = f"{MUSIC_DIR}/{c['cue']}.wav"; me.write_wav(path, x); m = me.measure(path)
        m_span, m_loop = lufs_of(x[:ns]), lufs_of(x[ls:le])
        secs = round(len(x) / SR, 3); need = c["span"] * (1 + STRETCH) + XFADE
        assert secs + 1e-3 >= need, f"{c['cue']} is {secs}s, needs {need}s (span +30 % + crossfade)"
        bpm = sc.bpm / (3 if c["cue"] == "field" else 1)                    # field: report the dotted-quarter pulse
        manifest.append(dict(cue=c["cue"], t=c["t"], span=c["span"], secs=secs, lastCue=c["last"], loop=False,
                             loopStart=round(ls / SR, 6), loopEnd=round(le / SR, 6), loopStartSample=ls, loopEndSample=le, loopFromSec=round(vp["start"], 3),
                             plainTailSec=round(secs - c["span"], 3), key=KEYS[c["cue"]],
                             meter=("6/8" if c["cue"] == "field" else "3/4" if c["cue"] == "lullaby" else "4/4"),
                             bars=sc.bars, bpm=round(bpm, 1), loopBars=vp["bars"], loopChord=vp["chord"],
                             lufs=round(m_span["lufs"], 1), loopLufs=round(m_loop["lufs"], 1),
                             truePeak=round(m["truePeak"], 1)))
        r = manifest[-1]; clean_tmp()
        print(f"music {c['cue']:9s} t={c['t']:7.2f} span={c['span']:6.2f} file={secs:6.2f}s bars={sc.bars:2d} "
              f"bpm={r['bpm']:5.1f} span I={r['lufs']:6.1f} loop {r['loopStart']:.2f}-{r['loopEnd']:.2f}s I={r['loopLufs']:6.1f} "
              f"TP={r['truePeak']:5.1f} dBTP")
    json.dump(dict(rule="Start each cue at its timeline t at full level and fade the previous cue out over 0.6 s from "
                        "that t. Each cue's composed music ends on its cadence at `span`; after it the cue continues "
                        "into a quiet loop section on its final chord. If the section is stretched (longer voice "
                        "clips), either loop [loopStart, loopEnd) seamlessly (seconds, sample-accurate) until the next "
                        "cue, or just keep playing: every file is at least span x 1.3 + 0.6 s (plainTailSec after the "
                        "span) and fades out over its last 2.5 s. The span sits at -20 LUFS, the loop section ~3 dB "
                        "under it. Duck music ~7 dB under voice lines. Rerun tools/story/music_ruth.py after the "
                        "timeline is re-timed so the in-cue hits follow the new times.",
                   crossfadeSec=XFADE, lufs=MUSIC_LUFS, stretchCovered=STRETCH, cues=manifest),
              open(path_json, "w"), indent=1, ensure_ascii=False)
    return manifest


def loop_stop(tl, sid):
    """Where an ambience loop should stop: the next music cue after it starts (the scene ends there)."""
    t0 = min(e["t"] for e in tl["sfx"] if e["id"] == sid)
    nxt = [m for m in sorted(tl["music"], key=lambda m: m["t"]) if m["t"] > t0 + 1.0]
    return nxt[0]["cue"] if nxt else None


def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]}); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in needed:
        me.seed(SFX_SEED.get(sid, "ruth/" + sid))
        t0 = min(s["t"] for s in tl["sfx"] if s["id"] == sid)
        x = me.hp(np.asarray(SFX[sid](dict(tl=tl, t=t0)), np.float64), 30)
        x = me.peak_normalize(x, SFX_PEAK_DB); path = f"{SFX_DIR}/{sid}.wav"; me.write_wav(path, x); m = me.measure(path)
        loop = sid in LOOP_SECS
        e = dict(id=sid, secs=round(len(x) / SR, 3), loop=loop, gainDb=SFX_GAIN[sid],
                 samplePeak=round(m["samplePeak"], 1), truePeak=round(m["truePeak"], 1),
                 lufs=None if m["lufs"] == float("-inf") else round(m["lufs"], 1))
        if loop: e.update(loopStart=0.0, loopEnd=e["secs"], stopAtCue=loop_stop(tl, sid), fadeInSec=1.0, fadeOutSec=1.5)
        manifest.append(e); clean_tmp()
        print(f"sfx   {sid:14s} {e['secs']:6.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f}"
              + (f" loop, stop at cue {e['stopAtCue']}" if loop else ""))
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play each one-shot at its timeline t with gainDb "
                        "(recommended mix level). Entries with loop: true are ambience beds: the whole file is a "
                        "seamless loop (loopStart 0, loopEnd = secs); start it at its t with a fadeInSec fade-in and "
                        "loop it until the music cue named in stopAtCue starts (fade out over fadeOutSec), so a "
                        "stretched scene stays covered and the bed never runs into the next scene.",
                   peakDbfs=SFX_PEAK_DB, sfx=manifest), open(f"{SFX_DIR}/mix.json", "w"), indent=1, ensure_ascii=False)
    return manifest


def build_preview(tl):
    n = int((tl["duration"] + 1.0) * SR); mus = np.zeros(n); fx = np.zeros(n); vo = np.zeros(n)
    for c in cue_spans(tl):
        x = me.load_any(f"{MUSIC_DIR}/{c['cue']}.wav")
        k0 = int(c["span"] * SR); k = int((XFADE if not c["last"] else 0.9) * SR); seg = x[k0:k0 + k]
        x[k0:k0 + len(seg)] *= np.linspace(1, 0, len(seg)); x[k0 + k:] = 0
        me.place(mus, x, c["t"])
    for s in tl["sfx"]:
        y = me.load_any(f"{SFX_DIR}/{s['id']}.wav") * 10 ** (SFX_GAIN[s["id"]] / 20)
        if s["id"] in LOOP_SECS:                                  # loop the bed until its stop cue, fade in / out
            stop = loop_stop(tl, s["id"]); t1 = next((m["t"] for m in tl["music"] if m["cue"] == stop), tl["duration"])
            m_ = int((t1 - s["t"] + 1.5) * SR); y = np.tile(y, m_ // len(y) + 1)[:m_]
            y[:SR] *= np.linspace(0, 1, SR); k = int(1.5 * SR); y[-k:] *= np.linspace(1, 0, k)
        me.place(fx, y, s["t"])
    used = 0; env = np.zeros(n, bool)
    for line in tl["lines"]:
        hit = False
        for ext in ("wav", "mp3"):
            p = f"{VOICE_DIR}/{line['id']}.{ext}"
            if os.path.exists(p): me.place(vo, me.load_any(p), line["t"]); used += 1; hit = True; break
        if not hit:      # no clip yet: duck over the estimated line span so the balance is still judged under speech
            i0 = int(line["t"] * SR); env[i0:i0 + int(line.get("maxSec", 4) * .85 * SR)] = True
    if used: env |= me.lp(np.abs(vo), 8) > 0.004
    look = int(.08 * SR); env = np.r_[env[look:], np.zeros(look, bool)]
    g = np.where(env, 10 ** (DUCK_DB / 20), 1.0); out = np.empty(n); cur = 1.0
    a_att, a_rel = 1 - np.exp(-1 / (.05 * SR)), 1 - np.exp(-1 / (.4 * SR))
    for i in range(0, n, 64):
        tgt = g[i]; cur += (tgt - cur) * (1 - (1 - (a_att if tgt < cur else a_rel)) ** 64); out[i:i + 64] = cur
    mus *= out
    mix = (mus + fx + vo).astype(np.float32)
    tmp = tempfile.mkdtemp() + "/mix.wav"; wavfile.write(tmp, SR, mix)
    me.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", "alimiter=limit=0.89:level=false",
            "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "96k", PREVIEW])
    m = me.measure(PREVIEW)
    print(f"preview {me.probe_secs(PREVIEW):.2f}s I={m['lufs']:.1f} LUFS TP={m['truePeak']:.1f} dBTP, "
          f"zh voice clips included: {used}/{len(tl['lines'])}")
    return dict(secs=round(me.probe_secs(PREVIEW), 2), lufs=round(m["lufs"], 1), truePeak=round(m["truePeak"], 1),
                voices=used, lines=len(tl["lines"]))


def update_doc(tl, cues, sfx, prev):
    if not os.path.exists(DOC): return
    txt = open(DOC).read()
    def swap(tag, body):
        nonlocal txt
        txt = re.sub(rf"(<!-- {tag}:start -->\n).*?(<!-- {tag}:end -->)", lambda m: m.group(1) + body + m.group(2), txt, flags=re.S)
    if cues:
        rows = ["| Cue | t (s) | Span (s) | File (s) | Loop (s) | Stretch covered | Key | Bars × bpm | LUFS span / loop | TP (dBTP) | Content |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for c in cues:
            meter = {"field": "6/8, ♩. =", "lullaby": "3/4"}.get(c["cue"], "4/4")
            plain = (c["secs"] - XFADE) / c["span"] - 1
            rows.append(f"| `{c['cue']}` | {c['t']:.2f} | {c['span']:.2f} | {c['secs']:.2f} | {c['loopStart']:.2f}–{c['loopEnd']:.2f} "
                        f"({c['loopBars']} bar{'s' if c['loopBars'] > 1 else ''} on {c['loopChord']}) | loop: any; plain: +{plain * 100:.0f} % "
                        f"| {KEYS[c['cue']]} | {c['bars']} × {c['bpm']} ({meter}) | {c['lufs']:.1f} / {c['loopLufs']:.1f} "
                        f"| {c['truePeak']:.1f} | {CUE_NOTES[c['cue']]} |")
        swap("cues", "\n".join(rows) + "\n")
    if sfx:
        rows = ["| Id | Length (s) | Loop | Sample peak (dBFS) | True peak (dBTP) | LUFS | gainDb | Notes |", "|---|---|---|---|---|---|---|---|"]
        for s in sfx:
            lp_ = f"whole file, stop at `{s['stopAtCue']}`" if s["loop"] else "one-shot"
            rows.append(f"| `{s['id']}` | {s['secs']:.2f} | {lp_} | {s['samplePeak']:.1f} | {s['truePeak']:.1f} | "
                        f"{s['lufs'] if s['lufs'] is not None else 'n/a'} | {s['gainDb']} | {SFX_NOTES[s['id']]} |")
        swap("sfx", "\n".join(rows) + "\n")
    if prev:
        swap("preview", f"Last run: {prev['secs']} s, {prev['lufs']} LUFS, {prev['truePeak']} dBTP; zh voice clips "
                        f"present: {prev['voices']}/{prev['lines']}; timeline `timedFrom`: {tl.get('timedFrom')}.\n")
    open(DOC, "w").write(txt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-music", action="store_true"); ap.add_argument("--skip-sfx", action="store_true")
    ap.add_argument("--skip-preview", action="store_true"); ap.add_argument("--only", default="")
    ap.add_argument("--stems", action="store_true", help="print per-stem levels while rendering")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    tempfile.tempdir = tempfile.mkdtemp(prefix="music_ruth_")
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    tl = json.load(open(TIMELINE))
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
