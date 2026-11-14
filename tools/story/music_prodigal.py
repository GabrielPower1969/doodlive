#!/usr/bin/env python3
"""Original score and sound effects for "The prodigal son" (story pack #6; docs/prodigal/CONTRACT.md section 7,
docs/prodigal/MUSIC.md).

Same machinery as Exodus, Ruth and Esther, shared rather than forked: this script imports tools/story/music_esther.py
(Score / Part / mel / groove, the FluidSynth renderer, the synthetic hall, loudness and file helpers, the synthesis
primitives, the wah-wah trombone) and tools/story/music_ruth.py (the split render for loop sections, the loop wrap,
the bird and cricket synths) as libraries and changes neither, so their outputs are untouched. Only the prodigal
cues, effects and paths live here.

The score is built around one original melody, the **father's theme** (FATHER below, 8 bars). Its head is six notes,
F#-G-A-D | B-A: a step up, an open-armed leap to the top, and a settling fall. It is heard on the ney-flute over oud
plucks at home (home), turns to D minor on the cello as the father gives away the money (home), hums faintly under
the son's cocky walk (leaving), is a single lonely flute in D minor in the pig pen (homesick), comes back tender on
the cello while the father watches the road (road_home), **bursts out on the whole string orchestra as he runs and
lands its high note on the hug** (run), turns into the feast dance (feast), is the father's gentle answer to the big
brother (brother) and closes the story warm and full (finale).

Feedback on Exodus applied here: no GM shakuhachi (the ney is flute + a breath of recorder), no trumpets and no
'aah' choir (they read as an old video game); the big moments are strings, horns kept soft and low-passed, harp,
timpani and frame drum, the warm palette that worked in Ruth.

Every name and time comes from assets/prodigal/timeline.json, read on every run: cue lengths follow the music spans,
and every in-cue hit (son / father / brother lines, the purse, the run, the hug, the servants, the stomp, the
outstretched hand) is looked up by event, so after the voices re-time the timeline, just rerun this script. Every
cue continues after its cadence into a quiet loop section on its final chord (cues.json gives a sample-exact seamless
loop) and runs at least 30 % past its span as a plain tail, as Ruth and Exodus.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/prodigal/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated, true peak <= -1 dBTP
  assets/prodigal/audio/music/cues.json        cue lengths, spans, loop points, loudness
  assets/prodigal/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/prodigal/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain, the cricket bed
  assets/prodigal/audio/preview_mix.mp3        rough full-length mix at timeline times (a check, not an app asset)
  docs/prodigal/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_prodigal.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       python3 tools/story/music_prodigal.py --check [--png x.png]   # loop seams, clipping, loudness, spectra
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg (as music_esther.py)
"""
import argparse, atexit, json, math, os, re, shutil, sys, tempfile
import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import music_esther as me                                                  # noqa: E402  (shared library)
import music_ruth as ru                                                    # noqa: E402  (shared library, unchanged)
from music_esther import (Score, Ctx, mel, groove, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB, DUCK_DB,  # noqa: E402
                          HARP, KOTO, NYLON, CELESTA, GLOCK, XYLO, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                          OOHS, FLUTE, RECORDER, OBOE, BASSOON, CLARINET, TIMPANI, HORN, TROMBONE, TUBA, MUTED_TPT,
                          DRUMS, BDRUM, CLAP, TAMB, CRASH, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA,
                          HI_WOOD, LO_WOOD, SHAKER, TRIANGLE)
from music_ruth import end_beats, bar_of, lines_in                         # noqa: E402

ROOT = me.ROOT
PR = f"{ROOT}/assets/prodigal"
TIMELINE = f"{PR}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{PR}/audio/music", f"{PR}/audio/sfx", f"{PR}/audio/voice/zh"
PREVIEW = f"{PR}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/prodigal/MUSIC.md"
STRETCH = 0.30                 # every cue survives its section being stretched by at least this much (re-timing)
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -3.0             # loop section loudness relative to the cue's composed span

VIOLA, BOWED_PAD, WHISTLE, FIDDLE, DULCIMER = 41, 92, 78, 110, 15
SIDE_STICK, RIDE, LO_TOM, HI_TOM, SHORT_GUIRO, LONG_GUIRO, VIBRASLAP, COWBELL = 37, 51, 45, 50, 73, 74, 58, 56

CH = dict(me.CH)
CH.update({"Asus": ["A2", "E3", "A3", "D4"], "A7": ["A2", "E3", "G3", "C#4"], "Dsus": ["D3", "A3", "D4", "G4"],
           "Gadd9": ["G2", "D3", "A3", "B3"], "Bbm": ["Bb2", "F3", "Bb3", "Db4"], "G/D": ["D3", "G3", "B3", "D4"],
           "Gm/D": ["D3", "G3", "Bb3", "D4"], "E": ["E2", "B2", "E3", "G#3"], "Bm": ["B2", "F#3", "B3", "D4"],
           "D7": ["D3", "A3", "C4", "F#4"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p


# =============================================================================================== the father's theme
# Original. Written in D major; minor(...) gives the D minor form (F# -> F, B -> Bb, C# -> C).
FATHER = {
    1: [("F#4", 1.5), ("G4", .5), ("A4", 1), ("D5", 1)],              # the head: F#-G-A-D | B-A (six notes)
    2: [("B4", 2), ("A4", 2)],
    3: [("G4", 1.5), ("F#4", .5), ("E4", 1), ("F#4", 1)],
    4: [("B3", 1), ("D4", 1), ("E4", 2)],                              # half cadence
    5: [("F#4", 1.5), ("G4", .5), ("A4", 1), ("D5", 1)],
    6: [("E5", 2), ("D5", 1), ("B4", 1)],                              # climbs higher
    7: [("A4", 1.5), ("B4", .5), ("G4", 1), ("E4", 1)],
    8: [("D4", 4)],
}
FA_HARM = {1: ["D"], 2: ["G", "D"], 3: ["Em", "D"], 4: ["G", "A"], 5: ["D"], 6: ["A", "G"], 7: ["D", "A7"], 8: ["D"]}
MIN_HARM = {1: ["Dm"], 2: ["Gm", "Dm"], 3: ["C", "Dm"], 4: ["Gm", "A"], 5: ["Dm"], 6: ["A", "Gm"], 7: ["Dm", "A"], 8: ["Dm"]}


def minor(notes):
    """D major spelling -> D minor (F# -> F, B -> Bb, C# -> C); keeps rests and suffixes."""
    def conv(p):
        if p is None: return None
        p = re.sub(r"F#(?=\d)", "F", p); p = re.sub(r"C#(?=\d)", "C", p); return re.sub(r"B(?=\d)", "Bb", p)
    return [(conv(p), d) for p, d in notes]


def theme(bars, minor_=False, scale=1.0):
    out = []
    for k in bars: out += [(p, d * scale) for p, d in (minor(FATHER[k]) if minor_ else FATHER[k])]
    return out


# =============================================================================================== small helpers
# Winds, bowed strings, brass and voices sustain (Ruth's fix for the DLS bank's decaying envelopes, music_ruth.P).
SUSTAIN = set(ru.SUSTAIN) | {RECORDER, WHISTLE, FIDDLE, TROMBONE, TUBA, MUTED_TPT, BOWED_PAD}


def P(s, name, program, *a, **kw):
    p = s.part(name, program, *a, **kw)
    if program in SUSTAIN:
        d = 8192 - 1440
        p.cc(0, 99, 120); p.cc(0, 98, 37); p.cc(0, 6, d >> 7); p.cc(0, 38, d & 127)
    return p


def ney(s, name="ney", gain=-3, send=.45, lp=4800):
    """The ney: a GM flute (breathy, low-passed, delayed vibrato) with a breath of recorder an octave-true under it.
    Not the shakuhachi (Exodus feedback: it reads as Japanese)."""
    return (P(s, f"{name} (flute)", FLUTE, gain, send, lp=lp, human=.01),
            P(s, f"{name} breath (recorder)", RECORDER, gain - 13, send, lp=3500, human=.01))


def nmel(pair, b, notes, vel, **kw):
    end = mel(pair[0], b, notes, vel, vib=True, **kw); mel(pair[1], b, notes, vel * .75, **kw); return end


def pad(part, b, name, dur, vel=50, swell=(70, 105), voices=(1, 2, 3), strum=.03, curve=.8):
    """Sustained chord with an expression swell; overlaps the next chord; only the cue's first chord swells from low."""
    ps = chord(name); part.chord(b, [ps[i] for i in voices], dur + .25, vel, strum=strum)
    v0 = swell[0] if b < 0.5 else max(82, swell[0])
    part.ramp(b, b + max(.5, dur * .8), 11, v0, max(v0, swell[1]), curve)


def harm_at(fn, b0, harm, beats):
    for i, h in enumerate(harm): fn(b0 + i * beats / len(harm), h, beats / len(harm))


def arp(part, b, name, beats, step=.5, vel=46, up=12, pat=(0, 1, 2, 3, 2, 3, 2, 1), ring=1.4):
    ps = chord(name)
    for j in range(int(round(beats / step))): part.add(b + j * step, ps[pat[j % len(pat)]] + up, ring, vel + (6 if j == 0 else 0))


def roll(part, b0, b1, key, v0, v1, step=.0625, dur=.1):
    """Timpani / cymbal roll from beat b0 to b1 with a velocity ramp."""
    k = max(1, int((b1 - b0) / step))
    for i in range(k): part.add(b0 + i * step, key, dur, v0 + (v1 - v0) * i / k)


def oud_riff(oud, b, name, beats=4, vel=1.0, pat=(0, 1, 2, 1, 3, 1, 2, 1)):
    ps = chord(name)
    for i in range(int(beats * 2)): oud.add(b + i * .5, ps[pat[i % len(pat)]], .45, (70 if i % 4 == 0 else 52) * vel)


def overlay(s, beat, audio, gain_db=0.0, wet=.25):
    """Synthesised audio (pig snorts, the wah-wah trombone) mixed into the cue at a beat, through the hall."""
    if not hasattr(s, "overlays"): s.overlays = []
    s.overlays.append((s.sec(beat), np.asarray(audio, np.float64) * 10 ** (gain_db / 20), wet))


def automate(s, b0, b1, db0, db1, ramp=.3):
    """Mix automation on the composed cue (not the loop bed): a gain in dB from db0 at beat b0 to db1 at beat b1,
    eased in and out over `ramp` seconds; used to shape a crescendo or lift a climax above the rest of the cue."""
    if not hasattr(s, "autom"): s.autom = []
    s.autom.append((s.sec(b0), s.sec(b1), db0, db1, ramp))


def apply_autom(x, autom):
    t = np.arange(len(x)) / SR; g = np.zeros(len(x))
    for t0, t1, d0, d1, r in autom:
        inside = np.interp(t, [t0, t1], [d0, d1]) * np.clip(np.minimum((t - t0 + r) / r, (t1 + r - t) / r), 0, 1)
        g += np.where((t > t0 - r) & (t < t1 + r), inside, 0)
    return x * 10 ** (g / 20)


def fit_notes(notes, beats):
    """Cut a phrase so it fits in `beats` (drops whole notes from the end)."""
    out, acc = [], 0.0
    for p, d in notes:
        if acc + d > beats + 1e-6: break
        out.append((p, d)); acc += d
    return out


FRAME = {"D": (LO_CONGA, 84), "t": (MUTE_CONGA, 52), "k": (OPEN_CONGA, 34), "s": (TAMB, 26)}
DARB = {"D": (LO_CONGA, 96), "T": (HI_BONGO, 84), "t": (LO_BONGO, 62), "k": (HI_BONGO, 40), "s": (TAMB, 34)}
HAND = {"D": (LO_CONGA, 92), "O": (OPEN_CONGA, 78), "t": (MUTE_CONGA, 60), "k": (HI_BONGO, 56), "b": (LO_BONGO, 66)}


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- home
CHEEKY = [[("A4.", .5), ("B4.", .5), ("A4.", .5), ("F#4.", .5), ("D5.", .5), (None, 1.5)],
          [("E5.", .5), ("D5.", .5), ("C#5.", .5), ("A4.", .5), ("B4", 1), (None, 1)]]
CHEEKY_HARM = [["D"], ["G", "A"], ["D"], ["A", "D"]]


def cue_home(c):
    """Pastoral morning in D major. Oud plucks (nylon + a breath of qanun), a soft string pad and harp; the father's
    theme on the ney-flute (bars 1-4) under the narrator. The son's cheeky request gets a staccato clarinet and pizz
    on the off-beats. When the father's face falls and he gives the money, the oud stops and the cello plays the
    theme's head in D minor, slowly, over Gm and Dm; it ends on a quiet D minor chord."""
    s = Score(c, 92, 4); n = s.bars; total = n * 4; E = end_beats(s)
    fl = ney(s, "ney", -2)
    oud = P(s, "oud (nylon)", NYLON, -4, .3, human=.006)
    qk = P(s, "qanun (koto)", KOTO, -15, .35, human=.006)
    harp = P(s, "harp", HARP, -10, .45, human=.007)
    padp = P(s, "strings", SLOW_STR, -9, .5, lp=4000)
    vc = P(s, "cello", CELLO, -3, .42, lp=4000, human=.01)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1000)
    cl = P(s, "clarinet", CLARINET, -6, .35, lp=4500, human=.006)
    pz = P(s, "pizz", PIZZ, -5, .25)
    dr = P(s, "frame drum", DRUMS, -15, .2, lp=2500, human=.005)
    son = s.at(c.first("lines", who="son"))
    give = s.at(c.first("acting", who="father", clip="sad_give")) or s.at(c.first("lines", who="father"))
    ts = 4.0                                                                   # theme from bar 1 (bar 0 = oud intro)
    nb = 4 if son is None else max(1, min(4, int((son - ts + 1.5) // 4)))
    ch0 = ts + 4 * nb                                                          # cheeky section starts
    sb = (total - 10) if give is None else math.floor(give / 2) * 2
    sb = min(max(sb, ch0 + 2), total - 4)                                       # sad section starts
    # pastoral bars (intro + theme)
    nmel(fl, ts, theme(range(1, nb + 1)), 74, legato=.97)
    for bar in range(int(ch0 // 4)):
        b = bar * 4; k = bar if 1 <= bar <= nb else None
        harm = FA_HARM[k] if k else ["D"]
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); d = 4 / len(harm); ps = chord(h)
            pad(padp, hb, h, d, 40, (65, 92)); cb.add(hb, low(ps[0]), d, 50)
            oud_riff(oud, hb, h, d, .95)
        if bar % 2 == 0: arp(harp, b, harm[0], 2, .5, 40)
        if bar >= 1: groove(dr, b, "D...t...", .5, FRAME, .7)
        if bar % 2 == 1: qk.add(b + 3.5, chord(harm[-1])[3] + 12, 1, 46)
    # cheeky section: the son asks for his share
    for j, b in enumerate(np.arange(ch0, sb, 4)):
        harm = CHEEKY_HARM[j % 4]
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); d = min(4 / len(harm), sb - hb); ps = chord(h)
            if d <= 0: continue
            pad(padp, hb, h, d, 36, (60, 85)); cb.add(hb, low(ps[0]), d, 46)
            for q in np.arange(.5, d, 1): pz.chord(hb + q, [ps[1], ps[3]], .3, 54)
            pz.add(hb, low(ps[0]) + 12, .3, 66)
        ph = fit_notes(CHEEKY[j % 2], sb - b - .5)
        mel(cl, b + .5, ph, 70)
        if j == 0: mel(oud, b, [("D4.", .5), (None, .5), ("A3.", .5)], 50)
    # sad: the father gives the money; theme head in D minor on the cello, slowly
    head = theme([1, 2], True)
    k = max(.6, min(1.25, (E - 1.5 - sb) / 8))
    mel(vc, sb, [(p, d * k) for p, d in head], 70, legato=.98, vib=True, shift=-12)
    for i, (h, d) in enumerate((("Dm", 4), ("Gm", 2), ("Dm", 2))):
        hb = sb + sum(x for _, x in (("Dm", 4), ("Gm", 2), ("Dm", 2))[:i]) * k
        last = i == 2
        dd = (E - hb) if last else d * k; ps = chord(h)
        pad(padp, hb, h, dd, 44, (70, 96)); cb.add(hb, low(ps[0]), dd, 50)
    harp.chord(E - 3.5, ["D3", "A3", "D4", "F4"], 3.5, 40, strum=.15)
    return s


# ----------------------------------------------------------------------------------------------- leaving
WALK_TUNE = [[("A4.", .5), ("A4.", .5), ("D5", 1), ("C#5.", .5), ("D5.", .5), ("E5", 1)],
             [("F#5", 1), ("E5.", .5), ("D5.", .5), ("B4", 1), ("A4", 1)],
             [("G4.", .5), ("A4.", .5), ("B4", 1), ("A4.", .5), ("G4.", .5), ("F#4", 1)],
             [("E4.", .5), ("F#4.", .5), ("G4.", .5), ("E4.", .5), ("D4", 2)]]
WALK_HARM = [["D", "A"], ["D", "G"], ["G", "D"], ["A", "D"]]


def cue_leaving(c):
    """A bouncy, cocky walking tune for the son in D major: whistle (doubled by a staccato clarinet an octave down),
    pizz bass on the beat, shaker eighths and a wood-block strut. Underneath, faint and slow on the strings, the
    father's theme head at half speed (he waves sadly). The brother's 'Hmph' gets a low bassoon grunt."""
    s = Score(c, 120, 4); n = s.bars; E = end_beats(s)
    wh = P(s, "whistle", WHISTLE, -6, .3, lp=6000, human=.005)
    cl = P(s, "clarinet", CLARINET, -8, .3, lp=4000, human=.005)
    pz = P(s, "pizz bass", PIZZ, -3, .22)
    oud = P(s, "oud", NYLON, -8, .28, human=.005)
    vln = P(s, "slow strings (father)", SLOW_STR, -13, .55, lp=3200)
    bsn = P(s, "bassoon", BASSOON, -6, .3, lp=3000)
    perc = P(s, "shaker + block", DRUMS, -12, .2, human=.004)
    br = s.at(c.first("lines", who="brother"))
    seq = [j % 4 for j in range(n - 1)] + [None]
    for bar in range(n):
        b = bar * 4; final = bar == n - 1; k = seq[bar]
        harm = WALK_HARM[k] if k is not None else ["D"]
        if k is not None and not final:
            mel(wh, b, WALK_TUNE[k], 84, legato=.9); mel(cl, b, WALK_TUNE[k], 56, shift=-12)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); ps = chord(h)
            for q in range(int(4 / len(harm))):
                if final and hb + q > b: break
                pz.add(hb + q, low(ps[0]) if q % 2 == 0 else ps[1] - 12, .4, 78 if q == 0 else 62)
                oud.chord(hb + q + .5, ps[1:], .3, 46, strum=.015)
        if not final:
            groove(perc, b, "SsSsSsSs", .5, {"S": (SHAKER, 54), "s": (SHAKER, 36)})
            for q in (1, 3): perc.add(b + q, HI_WOOD, .2, 52)
        else:
            pz.add(b, "D2", 1, 84); oud.chord(b, ["D3", "A3", "D4", "F#4"], E - b, 58, strum=.03)
            mel(wh, b, [("D5", E - b - .5)], 70)
    # the father's theme, faint, half speed
    head = [(p, d * 2) for p, d in theme([1, 2])]
    mel(vln, 0, fit_notes(head, n * 4 - 1), 54, legato=.99)
    if br is not None:
        mel(bsn, br + .5, [("A2", .6), ("D2", 1.2)], 76)
    return s


# ----------------------------------------------------------------------------------------------- party
PARTY = [[("D5.", .5), ("Eb5.", .5), ("F#5.", .5), ("G5.", .5), ("A5", 1), ("G5.", .5), ("F#5.", .5)],
         [("G5.", .5), ("F#5.", .5), ("Eb5.", .5), ("F#5.", .5), ("D5", 2)],
         [("A4.", .5), ("Bb4.", .5), ("C5.", .5), ("D5.", .5), ("Eb5.", .5), ("D5.", .5), ("C5.", .5), ("Bb4.", .5)],
         [("A4", .25), ("Bb4", .25), ("A4", .25), ("G4", .25), ("F#4.", .5), ("G4.", .5), ("A4", 2)]]
PARTY_RUN = [(p, .25) for p in ["D5", "Eb5", "F#5", "G5", "A5", "Bb5", "C6", "D6"]] + [("D6", 2)]
PARTY_HARM = [["D"], ["Gm", "D"], ["Cm", "Gm"], ["D"]]


def cue_party(c):
    """The far-country party, a lively comic dance in D Hijaz (D Eb F# G A Bb C) at ~134 bpm: a slightly too-fast
    fiddle (it rushes into 16th-note scale runs), tambourine eighths, claps on 2 and 4, darbuka, oud off-beat strums
    and an oom-pah pizz bass. The coin toss gets a xylophone run up; it ends on a tutti 'ta-da' D chord."""
    s = Score(c, 138, 4); n = s.bars; E = end_beats(s)
    fid = P(s, "fiddle", FIDDLE, -7, .3, lp=2400, human=.004)
    vln = P(s, "violin double", STRINGS, -12, .35, lp=3500, human=.004)
    oud = P(s, "oud", NYLON, -5, .25, human=.004)
    qk = P(s, "qanun", DULCIMER, -16, .3, lp=4000, human=.004)
    pz = P(s, "pizz bass", PIZZ, -3, .22)
    xy = P(s, "xylophone", XYLO, -9, .3, lp=5000)
    dr = P(s, "darbuka", DRUMS, -6, .16, lp=5000, human=.004)
    tb = P(s, "tambourine + claps", DRUMS, -15, .25, lp=4500, human=.006)
    coins = s.at(c.first("sfx", id="coins"))
    for bar in range(n):
        b = bar * 4; final = bar == n - 1; k = (bar - 1) % 4 if bar >= 1 else None
        harm = PARTY_HARM[k] if k is not None else ["D"]
        if k is not None and not final:
            ph = PARTY_RUN if (k == 3 and bar % 8 == 4) else PARTY[k]
            mel(fid, b, ph, 86, legato=.9); mel(vln, b, ph, 50, legato=.9)
            if bar % 2 == 0: mel(qk, b, ph, 48)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); ps = chord(h)
            for q in range(int(4 / len(harm))):
                if final and hb + q > b: break
                pz.add(hb + q, low(ps[0]) if q % 2 == 0 else ps[1] - 12, .3, 80 if q == 0 else 64)
                oud.chord(hb + q + .5, ps[1:], .25, 50, strum=.012)
        if not final:
            groove(dr, b, "D.tkT.tkD.tkT.kk", .25, DARB, .95)
            groove(tb, b, "SsSsSsSs", .5, {"S": (TAMB, 56), "s": (TAMB, 38)})
            for q in (1, 3):
                for _ in range(3): tb.add(b + q, CLAP, .3, 60)
        else:
            mel(fid, b - .5, [("A5.", .25), ("C#6.", .25)], 80)
            for p in (fid, vln): p.chord(b, ["D5", "F#5", "A5"], 1.2, 84)
            oud.chord(b, ["D3", "A3", "D4", "F#4"], 1.5, 76, strum=.02); pz.add(b, "D2", 1, 92)
            dr.add(b, LO_CONGA, .5, 100); tb.add(b, TAMB, .5, 76); tb.add(b, CRASH, 2, 52)
    if coins is not None:
        for j, p in enumerate(["D5", "F#5", "A5", "D6", "F#6", "A6", "D7"]): xy.add(coins + .1 + j * .125, p, .3, 60 + j * 3)
    return s


# ----------------------------------------------------------------------------------------------- broke
def cue_broke(c):
    """Deflating. Pizz plinks tiptoe down as he searches the purse, a bassoon 'huh?' rises on his line; the party
    fiddle drifts off in two fading fragments as the friends leave; then Esther's sliding wah-wah trombone (A - G# -
    G - a long wobbling F# that sags to F). The famine: thin, high tremolo strings on a bare D minor fifth, a low
    contrabass drone and a whisper of bowed glass, the harmony sinking Dm - Bb - Gm/D - Dm."""
    s = Score(c, 72, 4); n = s.bars; total = n * 4; E = end_beats(s)
    pz = P(s, "pizz", PIZZ, -4, .3)
    bsn = P(s, "bassoon", BASSOON, -6, .3, lp=3000)
    fid = P(s, "fiddle (fading)", FIDDLE, -9, .45, lp=4500, human=.006)
    trem = P(s, "thin tremolo strings", TREM_STR, -11, .55, lp=6000)
    padp = P(s, "low strings", SLOW_STR, -12, .5, lp=2500)
    cb = P(s, "contrabass", CBASS, -7, .35, lp=800)
    glass = P(s, "bowed glass", BOWED_PAD, -18, .6, lp=5000)
    son = s.at(c.first("lines", who="son"))
    fr = [(s.at(t0), s.at(min(t1, c.t + c.span))) for t0, t1 in lines_in(c, "friends")]
    fr = [(a, b) for a, b in fr if a is not None]
    fr0, fr1 = fr[0] if fr else (total * .35, total * .55)
    # the search: pizz tiptoe down
    for j, p in enumerate(["D5", "C5", "A4", "F4", "D4"]):
        if j * .75 < (son or 1.5) + 1.5: pz.add(j * .75, p, .2, 62 - j * 3)
    if son is not None: mel(bsn, son + 2.5, [("D3.", .5), ("Eb3", 1)], 58)
    padp.chord(0, ["D3", "A3", "D4"], fr0 + 1, 34); cb.add(0, "D2", fr0 + 1, 40)
    # friends drift off with two fading fiddle fragments
    for j, (p, v) in enumerate(((PARTY[0], 60), (PARTY[1], 44))):
        b = fr0 + .5 + j * 2.2
        if b < fr1: mel(fid, b, fit_notes(p, fr1 - b), v, legato=.9)
    fid.ramp(fr0, fr1, 11, 110, 40)
    # the wah-wah, at the end of the friends' line
    wb = max(fr1 - .7, (son or 0) + 4)
    overlay(s, wb, me.sfx_wah_wah(), -12, .25)
    # famine: thin strings from after the wah-wah
    fb = wb + s.beat(2.0)
    plan = [("Dm", 4), ("Bb", 4), ("Gm/D", 4), ("Dm", 99)]
    b = fb
    for h, d in plan:
        if b >= total: break
        dd = min(d, E - b); ps = chord(h)
        pad(padp, b, h, dd, 40, (55, 85)); trem.chord(b, [ps[1] + 24, ps[2] + 12], dd + .2, 34)
        b += d
    trem.ramp(fb, fb + 3, 11, 40, 100)
    cb.add(fb, "D2", E - fb, 52); cb.ramp(fb, fb + 2, 11, 50, 100)
    glass.add(fb + 2, "A5", E - fb - 2, 30)
    return s


# ----------------------------------------------------------------------------------------------- pigs
PIG = [[("D4.", .5), ("B3.", .5), ("G3.", .5), ("B3.", .5), ("D4", 1), (None, 1)],
       [("E4.", .5), ("C4.", .5), ("A3.", .5), ("C4.", .5), ("E4", 1), (None, 1)],
       [("D4.", .5), ("E4.", .5), ("F#4.", .5), ("G4.", .5), ("A4.", .5), ("F#4.", .5), ("D4", 1)],
       [("C4.", .5), ("A3.", .5), ("F#3.", .5), ("A3.", .5), ("G3", 1), (None, 1)]]
PIG_HARM = [["G"], ["C"], ["D"], ["D", "G"]]


def pig_grunt(d, f, up=1.3, keys=None, creak=30.0):
    """One pig grunt / 'oink': a creaky pulse-train voice (gated at `creak` Hz) through rounded formants, a nasal
    resonance and a breathy snort noise in the gaps."""
    m = int(d * SR); tt = np.arange(m) / SR
    f0 = f * (1 + (up - 1) * np.interp(tt, [0, d * .35, d], [0, 1, .15]))
    gate = (np.sin(2 * np.pi * creak * tt) < 0)
    src = me.glottal(f0, tilt=.85) * (1 - .55 * gate)
    v = me.formant_filter(src, keys or [(0, "u"), (.4, "o"), (1, "u")], .8)
    v = v / (np.max(np.abs(v)) + 1e-9)
    v = v + me.resonator(v, 280, 90) * .6
    v = v / (np.max(np.abs(v)) + 1e-9) + me.bp(me.noise(m), 400, 2500) * (~gate) * .18
    v *= np.minimum(1, tt / .012) * np.where(tt > d - .05, np.maximum(0, (d - tt) / .05), 1)
    return v / (np.max(np.abs(v)) + 1e-9)


def snuffle(d=.25, rate=38.0):
    """A pig rooting: fast nasal inhale-snorts (noise gated at `rate` Hz, band sweeping up)."""
    m = int(d * SR); tt = np.arange(m) / SR
    y = me.wah_filter(me.noise(m), np.interp(tt, [0, d], [700, 1500]), .5, 2.4) * ((np.sin(2 * np.pi * rate * tt) > -.2))
    y *= np.sin(np.pi * tt / d) ** .7
    return y / (np.max(np.abs(y)) + 1e-9)


def cue_pigs(c):
    """Comic oom-pah in G for the pig pen: tuba on 1 and 3, pizz + staccato bassoon chords on 2 and 4, a silly
    staccato tune on bassoon + clarinet, a guiro scrape now and then. Real (synthesised) pig snorts are mixed in
    rhythm into the tune's rests ('oom-pah, oink-oink'). When the hungry son speaks the band thins to the tuba and a
    slow, longing clarinet climb, a glockenspiel twinkle on 'yummy'; one last snort and a G chord end it."""
    s = Score(c, 112, 4); n = s.bars; E = end_beats(s)
    tuba = P(s, "tuba", TUBA, -3, .25, lp=2500)
    pah = P(s, "pizz pah", PIZZ, -6, .25)
    bsn = P(s, "bassoon tune", BASSOON, -3, .28, lp=3500, human=.005)
    cl = P(s, "clarinet tune", CLARINET, -9, .3, lp=4000, human=.005)
    bpah = P(s, "bassoon pah", BASSOON, -12, .25, lp=3000)
    gl = P(s, "glockenspiel", GLOCK, -16, .45)
    perc = P(s, "guiro + block", DRUMS, -12, .2, human=.004)
    son = s.at(c.first("lines", who="son"))
    sb = (n - 2) * 4 if son is None else max(4, round(son / 4) * 4)
    for bar in range(n):
        b = bar * 4; final = bar == n - 1; k = bar % 4
        harm = PIG_HARM[k] if b < sb else (["C", "G"] if not final else ["G"])
        hungry = b >= sb
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); ps = chord(h)
            for q in range(int(4 / len(harm))):
                if final and hb + q > b: break
                if q % 2 == 0: tuba.add(hb + q, low(ps[0]) if q == 0 else low(ps[1]), .5, 84 if not hungry else 64)
                elif not hungry:
                    pah.chord(hb + q, ps[1:], .25, 60); bpah.chord(hb + q, ps[1:3], .25, 52)
        if not hungry and not final:
            mel(bsn, b, PIG[k], 82); mel(cl, b, PIG[k], 56, shift=12)
            if k in (0, 1, 3):                                         # snorts in the tune's rests
                overlay(s, b + 3.0, pig_grunt(.17, 150, 1.45), -18, .15)
                overlay(s, b + 3.5, pig_grunt(.2, 128, 1.35), -17, .15)
            else:
                overlay(s, b + 3.5, snuffle(), -22, .15)
            if bar % 2 == 1: perc.add(b + 1.5, LONG_GUIRO, .4, 60)
            perc.add(b + 2, LO_WOOD, .2, 48)
        if final:
            tuba.add(b, "G1", 2, 88); pah.chord(b, ["G3", "B3", "D4"], 1.5, 66)
            bsn.chord(b, ["G2", "D3"], E - b, 60); cl.add(b, "B4", E - b - .5, 50)
            overlay(s, b + 1.5, pig_grunt(.24, 118, 1.3), -16, .15)
    if son is not None and son < (n - 1) * 4:
        mel(cl, son + .5, [("D4", 1.5), ("E4", 1.5), ("F#4", 1.5), ("G4", 3)], 64, legato=.98, vib=True)
        for j, p in enumerate(["G6", "B6", "D7"]): gl.add(son + 6.5 + j * .25, p, 1, 44)
    return s


# ----------------------------------------------------------------------------------------------- homesick
def cue_homesick(c):
    """Slow and lonely, D minor. A single ney-flute plays the father's theme head in D minor (F-G-A-D | Bb-A) over a
    low string pad and contrabass, with one harp note per bar. On the son's idea ('That's it! I'll go home!') a harp
    glissando and celesta lift it, the pad turns Bb -> D major and the flute rises A -> D, hopeful."""
    s = Score(c, 60, 4); n = s.bars; total = n * 4; E = end_beats(s)
    fl = ney(s, "ney", -2, .5)
    padp = P(s, "low strings", SLOW_STR, -6, .5, lp=2800)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=900)
    harp = P(s, "harp", HARP, -9, .5, human=.008)
    cel = P(s, "celesta", CELESTA, -13, .6)
    idea = s.at(c.first("acting", who="son", clip="idea_stand")) or s.at(c.first("sfx", id="sparkle"))
    ib = idea if idea is not None and idea > 4 else total - 3.5
    head = theme([1, 2], True); k = max(.6, min(1.0, (ib - .4) / 8))
    nmel(fl, 0.25, [(p, d * k) for p, d in head], 66, legato=.98)
    for h, b0, d in (("Dm", 0, 4 * k), ("Gm", 4 * k, 2 * k), ("Dm", 6 * k, ib - 6 * k)):
        if d <= 0: continue
        pad(padp, b0, h, d, 40, (50, 90)); cb.add(b0, low(chord(h)[0]), d, 50)
        harp.add(b0 + .5, chord(h)[2], 3, 40)
    # the idea: lift to D major
    for j, p in enumerate(["D3", "F3", "A3", "D4", "F#4", "A4", "D5", "F#5"]): harp.add(ib + j * .07, p, 3, 46 + j)
    for j, p in enumerate(["A5", "D6", "F#6"]): cel.add(ib + .6 + j * .2, p, 2, 50)
    pad(padp, ib, "Bb", .7, 46, (85, 100)); pad(padp, ib + .7, "D", E - ib - .7, 52, (85, 110))
    cb.add(ib + .7, "D2", E - ib - .7, 56)
    nmel(fl, ib + .7, [("A4", .6), ("D5", max(1.0, E - ib - 1.6))], 70, legato=.99)
    return s


# ----------------------------------------------------------------------------------------------- road_home
ROAD_HARM = ["D", "Bm", "G", "Asus", "D", "Bm", "G", "A"]
PRACTISE = [[(None, 1), ("A4", 1), ("B4", .5), ("A4", .5), ("F#4", 1)], [("G4", 2), (None, 2)],
            [(None, 1), ("A4", 1), ("D5", 1), ("C#5", .5), ("B4", .5)], [("A4", 3), (None, 1)]]


def cue_road_home(c):
    """Golden evening, the walk home: steady walking strings in D major (pizz bass in quarters, violas in legato
    eighths), hopeful but a little shaky (a suspended chord, a hesitant clarinet trying phrases with pauses while he
    rehearses). When the narrator tells how the father watched the road every day, the walk stops and the cello
    sings the father's theme head, tender. When the father sees him: tremolo strings, a timpani roll and a cymbal
    swell build on G -> A (the dominant) into the run."""
    s = Score(c, 88, 4); n = s.bars; total = n * 4; E = end_beats(s)
    pz = P(s, "pizz bass", PIZZ, -4, .25)
    vla = P(s, "violas", STRINGS, -9, .4, lp=4000, human=.006)
    padp = P(s, "strings", SLOW_STR, -9, .5, lp=4000)
    cl = P(s, "clarinet", CLARINET, -6, .4, lp=4000, human=.01)
    vc = P(s, "cello", CELLO, -8, .45, lp=4500, human=.01)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1000)
    harp = P(s, "harp", HARP, -9, .45, human=.007)
    trem = P(s, "tremolo strings", TREM_STR, -8, .55, lp=7000)
    timp = P(s, "timpani", TIMPANI, -8, .35)
    cym = P(s, "cymbal", DRUMS, -18, .5)
    hn = P(s, "horns", HORN, -14, .5, lp=2500)
    narr = s.at(c.first("lines", who="narrator")); look = s.at(c.first("acting", who="father", clip="look_far"))
    see = s.at(c.first("acting", who="father", clip="see_son")) or s.at(c.first("lines", who="father"))
    tf = math.floor(narr) if narr is not None else (look or total * .45)
    tf = max(4.0, tf); wb_end = math.floor(tf / 4) * 4 if tf % 4 < 2 else tf     # walking until here
    sb = see if see is not None and see > tf + 4 else max(tf + 4, total - 12)
    # walking
    for bar in range(int(math.ceil(wb_end / 4))):
        b = bar * 4; h = ROAD_HARM[bar % 8]; ps = chord(h); d = min(4, wb_end - b)
        pad(padp, b, h, d, 40, (65, 95)); cb.add(b, low(ps[0]), d, 48)
        for q in range(int(d)): pz.add(b + q, low(ps[[0, 1, 2, 1][q]]) if q != 2 else ps[1], .4, 72 if q == 0 else 60)
        for j in range(int(d * 2)): vla.add(b + j * .5, ps[[1, 2, 3, 2][j % 4]], .55, 48 + (6 if j % 4 == 0 else 0))
        if h == "Asus": vla.add(b + 2, "C#4", 2, 50)                                       # sus resolves: shaky hope
        if bar >= 1 and bar % 4 in (1, 3): mel(cl, b, fit_notes(PRACTISE[(bar // 2) % 4], d), 62)
    # the father waits: theme head on the cello, long chords
    k = max(.7, min(1.2, (sb - tf) / 8))
    mel(vc, tf, [(p, d * k) for p, d in theme([1, 2])], 72, legato=.98, vib=True, shift=-12)
    for h, o, d in (("D", 0, 4), ("G", 4, 2), ("D", 6, 2)):
        b0 = tf + o * k; dd = min(d * k, sb - b0)
        if dd > 0: pad(padp, b0, h, dd, 46, (70, 100)); cb.add(b0, low(chord(h)[0]), dd, 52); arp(harp, b0, h, dd, 1.0, 40)
    # he sees him: the build on G -> A into the run
    gb = sb; ab = sb + (total - sb) * .5
    for h, b0, b1 in (("G", gb, ab), ("A", ab, E)):
        ps = chord(h)
        pad(padp, b0, h, b1 - b0, 54, (70, 120)); cb.add(b0, low(ps[0]), b1 - b0, 60)
        trem.chord(b0, [ps[1] + 12, ps[2] + 12, ps[3] + 12], b1 - b0 + .1, 50)
        hn.chord(b0, [ps[1], ps[3]], b1 - b0, 46)
    trem.ramp(gb, total, 11, 45, 100, 1.6); hn.ramp(gb, total, 11, 40, 92, 1.6)
    automate(s, gb, total, -3.0, 1.0, .4)
    roll(timp, ab, total, "A2", 26, 74); roll(cym, total - 3, total, RIDE, 10, 60, .0625, .2)
    for j, p in enumerate(["A3", "C#4", "E4", "A4", "C#5", "E5", "A5"]): harp.add(total - 1 + j * .13, p, 2, 50 + j * 2)
    return s


# ----------------------------------------------------------------------------------------------- run
def cue_run(c):
    """The heart of the story. As the father runs, the father's theme bursts out on the whole string orchestra (violins,
    violas, cellos an octave down), flute and soft low-passed horns, over a galloping eighth-note string ostinato, a
    timpani stroke and a cymbal; its high note (B) lands exactly on the hug as a huge, warm G chord that settles onto
    a long held D major (strings, horns, harp roll, timpani). Under the son's whispered 'sorry' only the held strings
    and a slow harp remain. When the father calls 'Quick! The best robe!' the music bustles with joy: pizz eighths,
    frame drum and oud, and flute + clarinet sing theme bars 5-8, cadencing on D at the servants' 'Yes, master!'
    with a celesta glint for the robe and ring. No trumpets, no 'aah' choir."""
    s = Score(c, 96, 4); n = s.bars; total = n * 4; E = end_beats(s)
    vln = P(s, "violins", STRINGS, -2, .55, lp=6500, human=.005)
    vla = P(s, "violas + cellos", STRINGS, -6, .5, lp=4500, human=.005)
    vc = P(s, "cello", CELLO, -3, .45, lp=4500, human=.006)
    padp = P(s, "string pad", SLOW_STR, -4, .55, lp=5000)
    cb = P(s, "contrabass", CBASS, -6, .35, lp=1100)
    fl = P(s, "flute", FLUTE, -5, .5, lp=7000, human=.005)
    cl = P(s, "clarinet", CLARINET, -8, .4, lp=4500, human=.006)
    hn = P(s, "horns (soft)", HORN, -9, .5, lp=2400)
    harp = P(s, "harp", HARP, -6, .45, human=.006)
    timp = P(s, "timpani", TIMPANI, -7, .4)
    cym = P(s, "cymbal", DRUMS, -15, .6)
    pz = P(s, "pizz", PIZZ, -5, .25)
    oud = P(s, "oud", NYLON, -9, .3, human=.005)
    dr = P(s, "frame drum", DRUMS, -10, .2, lp=2500, human=.004)
    cel = P(s, "celesta", CELESTA, -12, .6)
    oohs = P(s, "oohs (faint)", OOHS, -22, .7, lp=3500)
    rb = s.at(c.first("acting", who="father", clip="run")); rb = .25 if rb is None else rb
    hb = s.at(c.first("acting", who="father", clip="hug")); hb = rb + 4 if hb is None or hb < rb + 1.5 else hb
    call = s.at(c.first("acting", who="father", clip="call_servants")) or s.at(c.first("lines", who="father"))
    jb = (total - 16) if call is None else call                                 # joy section
    jb = min(max(jb, hb + 6), total - 8)
    k = max(.6, min(1.6, (hb - rb) / 4))
    # --- the run: theme head bar 1 scaled so its 5th note lands on the hug
    run_notes = [(p, d * k) for p, d in FATHER[1]]
    mel(vln, rb, run_notes, 96, legato=.97, shift=12); mel(vla, rb, run_notes, 84, legato=.97)
    mel(vc, rb, run_notes, 82, legato=.97, shift=-12); mel(fl, rb, run_notes, 80, shift=12)
    hn.chord(rb, ["D4", "F#4", "A4"], hb - rb, 56); hn.ramp(rb, hb, 11, 70, 112)
    timp.add(rb, "D2", 1.5, 100); cym.add(rb, CRASH, 3, 70); cb.add(rb, "D2", hb - rb, 76); harp.chord(rb, ["D3", "A3", "D4"], 2, 70)
    for j in range(int((hb - rb) / .5)):                                         # galloping strings
        vla.add(rb + j * .5, ["D3", "A3", "F#3", "A3"][j % 4], .4, 66 + (8 if j % 2 == 0 else 0))
        cb.add(rb + j * .5, "D2" if j % 2 == 0 else "A2", .35, 64)
    roll(timp, hb - 1.5, hb, "A2", 50, 96)
    pad(padp, rb, "D", hb - rb, 60, (80, 120))
    automate(s, rb - .1, hb + 3, 4.5, 4.5, .25)
    # --- the hug: B over G (huge, warm), settling onto A over D, held
    hold = max(hb + 4, min(jb - .5, hb + 10))
    mel(vln, hb, [("B4", 2), ("A4", hold - hb - 2)], 104, legato=.99, shift=12)
    mel(fl, hb, [("B4", 2), ("A4", min(4, hold - hb - 2))], 82, shift=12, vib=True)
    mel(vc, hb, [("G3", 2), ("D3", hold - hb - 2)], 90, legato=.99)
    for h, b0, b1, v in (("Gadd9", hb, hb + 2, 74), ("D", hb + 2, hold, 66)):
        ps = chord(h)
        padp.chord(b0, ps[1:], b1 - b0 + .2, v); cb.add(b0, low(ps[0]), b1 - b0, 78)
        hn.chord(b0, [ps[1], ps[2], ps[3]], b1 - b0, 60)
        oohs.chord(b0, [ps[2], ps[3] + 12], b1 - b0, 46)
    padp.ramp(hb + 2, hold, 11, 120, 70, .6); hn.ramp(hb, hb + 1, 11, 112, 112); hn.ramp(hb + 2, hold, 11, 110, 50, .6)
    vln.ramp(hb + 2, hold, 11, 127, 70, .6)
    timp.add(hb, "G2", 2, 104); cym.add(hb, CRASH, 4, 76); roll(timp, hb + .1, hb + 2, "D2", 40, 20)
    for j, p in enumerate(["G2", "D3", "G3", "B3", "D4", "G4", "B4", "D5", "G5"]): harp.add(hb + j * .09, p, 3, 72 - j)
    for b0 in np.arange(hb + 4, hold - .5, 2): arp(harp, b0, "D", 2, 1.0, 40)                 # slow harp under 'sorry'
    # --- quiet between the hug and the call
    if jb - hold > .5:
        for h, b0 in (("Bm", hold), ("G", hold + (jb - hold) * .5)):
            dd = (jb - hold) * .5; pad(padp, b0, h, dd, 44, (70, 85)); cb.add(b0, low(chord(h)[0]), dd, 50)
            arp(harp, b0, h, dd, 1.0, 38)
        mel(vc, hold, [("D4", (jb - hold) * .5), ("B3", (jb - hold) * .5)], 60, legato=.99, shift=-12)
    # --- joy: theme bars 5-8, bustling
    jb0 = math.ceil(jb * 2) / 2
    kk = max(.8, min(1.25, (total - 1 - jb0) / 16))
    seq = [5, 6, 7, 8]
    for j, tbar in enumerate(seq):
        b = jb0 + j * 4 * kk; last = tbar == 8
        notes = [(p, d * kk) for p, d in FATHER[tbar]]
        if last: notes = [("D5", E - b - .3)]
        mel(fl, b, notes, 90, vib=True, shift=0 if tbar != 5 else 12); mel(cl, b, notes, 68, shift=-12 if tbar != 5 else 0)
        if tbar in (6, 7): mel(vln, b, notes, 72, legato=.96)
        harm = FA_HARM[tbar]
        for i, h in enumerate(harm):
            hbb = b + i * 4 * kk / len(harm); d = (E - hbb) if last else 4 * kk / len(harm); ps = chord(h)
            pad(padp, hbb, h, d, 50, (85, 105)); cb.add(hbb, low(ps[0]), d, 60)
            if not last:
                for q in range(int(round(d / (.5 * kk)))):
                    pz.add(hbb + q * .5 * kk, [ps[0], ps[1], ps[2], ps[1]][q % 4], .3, 64 if q % 2 == 0 else 52)
                    if q % 2 == 1: oud.chord(hbb + q * .5 * kk, ps[1:], .3, 46, strum=.012)
        if not last: groove(dr, b, "D.tkD.tk", .5 * kk, FRAME, 1.0)
        else:
            oud.chord(b, ["D3", "A3", "D4", "F#4", "A4"], E - b, 60, strum=.04); hn.chord(b, ["D4", "F#4", "A4"], E - b, 54)
            harp.chord(b, ["D3", "A3", "D4", "F#4"], 3, 56, strum=.1); timp.add(b, "D2", 2, 76); dr.add(b, LO_CONGA, .5, 80)
    sp = s.at(c.first("sfx", id="sparkle")) or (total - 1.5)
    for j, p in enumerate(["D6", "F#6", "A6", "D7"]): cel.add(sp + j * .18, p, 2, 52 - j * 2)
    return s


# ----------------------------------------------------------------------------------------------- feast
FEAST = [[("F#4", .5), ("G4", .5), ("A4", 1), ("D5", 1), ("B4", .5), ("A4", .5)],          # the father's head, dancing
         [("G4", .5), ("A4", .5), ("F#4", .5), ("E4", .5), ("D4", 2)],
         [("A4", .5), ("B4", .5), ("C5", 1), ("B4", .5), ("A4", .5), ("G4", 1)],               # C natural: Mixolydian
         [("F#4", .5), ("G4", .5), ("A4", .5), ("F#4", .5), ("E4", 1), ("D4", 1)]]
FEAST_HARM = [["D"], ["G", "D"], ["C", "G"], ["D", "A"]]


def cue_feast(c):
    """Night celebration in D Mixolydian: a darbuka + frame-drum dance groove, tambourine, claps on 2 and 4, an oud
    ostinato and pizz bass. The dance tune is the father's theme head in dancing eighths; flute + fiddle + qanun play
    it at the top, the qanun alone keeps it going softly under the father's 'lost and found' speech, and the whole
    band comes back on it as everyone dances, ending on a D chord stab."""
    s = Score(c, 116, 4); n = s.bars; E = end_beats(s)
    fl = P(s, "flute", FLUTE, -3, .35, human=.005)
    fid = P(s, "fiddle", FIDDLE, -9, .35, lp=6500, human=.005)
    qk = P(s, "qanun (koto + dulcimer)", KOTO, -6, .3, human=.005)
    dul = P(s, "dulcimer", DULCIMER, -14, .3, human=.005)
    oud = P(s, "oud", NYLON, -4, .28, human=.005)
    pz = P(s, "pizz bass", PIZZ, -4, .22)
    padp = P(s, "strings", SLOW_STR, -12, .45, lp=4500)
    dr = P(s, "darbuka + frame drum", DRUMS, -5, .16, human=.004)
    tb = P(s, "tambourine + claps", DRUMS, -9, .25, human=.006)
    fa = lines_in(c, "father"); f0, f1 = (s.at(fa[0][0]), s.at(min(fa[0][1], c.t + c.span))) if fa else (None, None)
    for bar in range(n):
        b = bar * 4; final = bar == n - 1; k = (bar - 1) % 4 if bar >= 1 else None
        harm = FEAST_HARM[k] if k is not None and not final else ["D"]
        talk = f0 is not None and f1 is not None and b + 2 > f0 and b < f1 - 1
        if k is not None and not final:
            if talk: mel(qk, b, FEAST[k], 52)
            else:
                mel(fl, b, FEAST[k], 84, shift=12 if k in (0, 2) else 0); mel(fid, b, FEAST[k], 60, shift=12)
                mel(qk, b, FEAST[k], 58); mel(dul, b, FEAST[k], 48, shift=12)
        if final:
            mel(fl, b, [("F#5", .5), ("G5", .5), ("A5", .5), ("D6", E - b - 2)], 84)
            mel(qk, b, [("F#4", .5), ("G4", .5), ("A4", .5), ("D5", 2)], 60)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); ps = chord(h); d = 4 / len(harm)
            for q in range(int(d)):
                if final and hb + q > b + 1.5: break
                pz.add(hb + q, low(ps[0]) if q % 2 == 0 else ps[1] - 12, .35, 78 if q == 0 else 62)
            if not final: oud_riff(oud, hb, h, d, .9 if not talk else .7)
            padp.chord(hb, ps[1:], (E - hb) if final else d + .2, 34 if talk else 40)
        if not final:
            groove(dr, b, "D.tkD.tkDktkD.tk", .25, DARB, .85 if talk else .95)
            groove(tb, b, "SsSsSsSs", .5, {"S": (TAMB, 48), "s": (TAMB, 30)}, .8 if talk else 1.0)
            for q in (1, 3):
                for _ in range(3): tb.add(b + q, CLAP, .3, 50 if talk else 62)
        else:
            dr.add(b + 1.5, LO_CONGA, .5, 104); tb.add(b + 1.5, TAMB, .5, 76)
            oud.chord(b + 1.5, ["D3", "A3", "D4", "F#4", "A4"], E - b - 1.5, 66, strum=.02); pz.add(b + 1.5, "D2", 1, 90)
            for _ in range(4): tb.add(b + 1.5, CLAP, .3, 72)
    return s


# ----------------------------------------------------------------------------------------------- brother
BRO_WALK = [[("D3", 1), ("A2", 1), ("D3.", .5), ("E3.", .5), ("F3", 1)],
            [("E3", 1), ("C3", 1), ("A2", 2)],
            [("D3", 1), ("F3", 1), ("E3.", .5), ("D3.", .5), ("C#3", 1)],
            [("D3", 1), ("A2", 1), ("D2", 2)]]
BRO_HARM = ["Dm", "A", "Dm", "Dm"]
COMPLAIN = [[("A3", 1.5), ("Bb3", .5), ("A3", 1), ("G3", 1)], [("F3", 2), ("E3", 2)],
            [("D4", 1.5), ("C4", .5), ("Bb3", 1), ("A3", 1)], [("G3", 1), ("A3", 1), ("D3", 2)]]
COMPLAIN_HARM = ["Dm", "A", "Bb", "Gm"]


def cue_brother(c):
    """Outside the wall at night. A grumpy D minor walk on bassoon + low pizz (stomping quarters) with the feast
    music faint and muffled behind the wall the whole time (its own darbuka, oud and dance tune, low-passed at
    ~600 Hz, mostly reverb). When he stops to listen, the walk stops and the muffled party grows; his two stamps get
    timpani + bass drum, his 'Hmph!' a low bassoon. Under his complaint a hurt cello line (D minor, falling) with the
    muffled party fading away. The father's gentle answer: his theme in D major on a soft clarinet and warm strings
    with harp; as the brother softens and takes his hand, the theme cadences on a warm D major chord."""
    s = Score(c, 96, 4); n = s.bars; total = n * 4; E = end_beats(s)
    bsn = P(s, "bassoon", BASSOON, -3, .3, lp=3000, human=.006)
    lpz = P(s, "low pizz", PIZZ, -5, .25)
    vc = P(s, "cello", CELLO, -3, .42, lp=4000, human=.01)
    padp = P(s, "strings", SLOW_STR, -10, .5, lp=3500)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=900)
    cl = P(s, "clarinet (father)", CLARINET, -7, .45, lp=4500, human=.01)
    harp = P(s, "harp", HARP, -9, .45, human=.007)
    hit = P(s, "stomp hits", DRUMS, -6, .3)
    timp = P(s, "timpani", TIMPANI, -8, .35)
    # the feast behind the wall: same tune, darbuka and oud, muffled (low-passed, mostly reverb)
    mdr = P(s, "muffled darbuka", DRUMS, -13, .8, lp=500)
    moud = P(s, "muffled oud", NYLON, -12, .8, lp=700)
    mfl = P(s, "muffled tune", FLUTE, -18, .85, lp=650)
    lis = s.at(c.first("acting", who="brother", clip="listen_music")); lis = 8.0 if lis is None else lis
    st = s.at(c.first("acting", who="brother", clip="stomp_cross")); st = lis + 10 if st is None else st
    bro = lines_in(c, "brother"); hmph = s.at(bro[1][0]) if len(bro) > 1 else st + 1
    comp = s.at(c.first("acting", who="brother", clip="complain")) or (st + 8)
    fa = s.at(c.first("lines", who="father")) or comp + 12
    th = s.at(c.first("acting", who="brother", clip="take_hand")); th = total - 1.5 if th is None or th < fa + 8 else th
    mute_end = fa + 2.0
    # muffled party: whole bars from 0 to mute_end, level by section via velocity
    def mlevel(b):
        if b < lis: return .6
        if b < st: return 1.0
        if b < comp: return .8
        return max(0.0, .7 * (1 - (b - comp) / max(4, mute_end - comp)))
    for bar in range(int(math.ceil(mute_end / 4))):
        b = bar * 4; k = bar % 4; lv = mlevel(b)
        if lv <= .05: continue
        groove(mdr, b, "D.tkD.tkDktkD.tk", .25, DARB, lv)
        for i, h in enumerate(FEAST_HARM[k]): oud_riff(moud, b + i * 4 / len(FEAST_HARM[k]), h, 4 / len(FEAST_HARM[k]), lv)
        mel(mfl, b, FEAST[k], 80 * lv, shift=12)
    # A: grumpy walk until he listens
    for bar in range(int(math.ceil(lis / 4))):
        b = bar * 4; ph = fit_notes(BRO_WALK[bar % 4], lis - b)
        mel(bsn, b, ph, 78, legato=.8); mel(lpz, b, ph, 70)
        h = BRO_HARM[bar % 4]; pad(padp, b, h, min(4, lis - b), 36, (55, 80))
    # B: listening: low held D minor, a cello tremble
    padp.chord(lis, ["D3", "A3", "F4"], st - lis, 40); cb.add(lis, "D2", st - lis, 46)
    vc.add(lis + 1, "A2", st - lis - 1, 44); vc.vibrato(lis + 1, st - lis - 1, 50)
    mel(bsn, lis + .5, [("A2", .5), ("D3", 1)], 60)                                  # 'huh?'
    # C: two stamps, then 'Hmph!' and a sulky held low note
    for j, b in enumerate((st, st + .75)):
        hit.add(b, BDRUM, .4, 110); timp.add(b, "D2", .8, 96 - 8 * j); lpz.add(b, "D2", .3, 96)
    mel(bsn, hmph + 1.0, [("A2.", .5), ("D2", 1.5)], 84)
    cb.add(st + 1.5, "D2", comp - st - 1.5, 50); padp.chord(st + 1.5, ["D3", "A3", "D4"], comp - st - 1.5, 34)
    # D: the complaint: hurt cello, D minor
    b = comp; j = 0
    while b < fa - 1:
        ph = fit_notes(COMPLAIN[j % 4], fa - b); h = COMPLAIN_HARM[j % 4]; d = min(4, fa - b)
        if not ph: break
        mel(vc, b, ph, 80, legato=.97, vib=True)
        pad(padp, b, h, d, 44, (66, 98)); cb.add(b, low(chord(h)[0]), d, 50)
        for q in (0, 2):
            if q < d: lpz.add(b + q, low(chord(h)[0]) + 12, .3, 52)
        b += 4; j += 1
    # E: the father's answer: his theme in D major, tender; it cadences on the hand-hold
    tb = math.ceil(fa - .25)
    avail = th - tb
    bars = [1, 2, 3, 4, 7] if avail >= 18 else [1, 2, 7] if avail >= 10 else [1, 7]
    kt = max(.7, min(1.3, avail / (4 * len(bars))))
    b = tb
    for tbar in bars:
        nts = [(p, d * kt) for p, d in FATHER[tbar]]
        mel(cl, b, nts, 70, legato=.97, vib=True)
        harm_at(lambda bt, h, d: (pad(padp, bt, h, d, 46, (70, 98)), cb.add(bt, low(chord(h)[0]), d, 50),
                                  arp(harp, bt, h, d, 1.0, 38)), b, FA_HARM[tbar], 4 * kt)
        b += 4 * kt
    vc.add(tb + 8 * kt, "D3", max(1, th - tb - 8 * kt), 48)
    # the hand: D major, warm
    mel(cl, th, [("D4", E - th - .2)], 66, vib=True)
    pad(padp, th, "D", E - th, 54, (80, 112)); cb.add(th, "D2", E - th, 56)
    for j, p in enumerate(["D3", "A3", "D4", "F#4", "A4", "D5", "F#5"]): harp.add(th + j * .11, p, 3, 54 - j)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """The father's theme, warm and full, D major (all eight bars when the span allows, else bars 1, 2, 5-8 after
    an intro bar) and a held final chord. Intimate at first (cello +
    ney-flute + harp + oud + string pad under the narrator), then from the golden rays the violins and flute take the
    tune over soft horns, a faint 'ooh', a frame-drum heartbeat and a timpani roll into the cadence; oud, harp and
    celesta ring on the held D major chord; then the loop bed."""
    s = Score(c, 84, 4); n = s.bars; E = end_beats(s)
    if n >= 8: seq = [None] * (n - 8) + list(range(1, 9))                     # intro bars, then all eight
    elif n == 7: seq = [None, 1, 2, 5, 6, 7, 8]
    elif n >= 4: seq = [1, 2, 5, 6, 7, 8][-n:] if n > 4 else [1, 2, 7, 8]
    else: seq = [1, 7, 8][-n:]                                                  # always keep the head and cadence
    vc = P(s, "cello", CELLO, -2, .42, lp=4500, human=.01)
    nf = ney(s, "ney", -8, .5)
    vln = P(s, "violins", STRINGS, -2, .55, lp=6500)
    fl = P(s, "flute", FLUTE, -5, .5)
    padp = P(s, "pad", SLOW_STR, -5, .5, lp=4500)
    hn = P(s, "horns (soft)", HORN, -10, .5, lp=2400)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1000)
    harp = P(s, "harp", HARP, -6, .45, human=.007)
    oud = P(s, "oud", NYLON, -9, .35, human=.006)
    oohs = P(s, "oohs (faint)", OOHS, -20, .7, lp=3500)
    timp = P(s, "timpani", TIMPANI, -11, .35)
    dr = P(s, "frame drum", DRUMS, -13, .2, lp=2500, human=.005)
    cel = P(s, "celesta", CELESTA, -11, .6)
    rays_b = bar_of(s, c.first("fx", id="golden_rays"), n // 2)
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1; full = bar >= rays_b
        harm = FA_HARM[k] if k else ["D"]
        if k:
            notes = FATHER[k] if not final else [("D4", E - b - .2)]
            if full:
                mel(vln, b, notes, 80, legato=.98, shift=12 if k in (1, 2, 3, 4, 8) else 0)
                mel(fl, b, notes, 66, vib=True, shift=12 if k in (1, 2, 3, 4, 8) else 0)
                mel(vc, b, notes, 56, legato=.98, shift=-12)
            else:
                mel(vc, b, notes, 74, legato=.98, vib=True, shift=-12); nmel(nf, b, notes, 50, legato=.98)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); last = final and i == len(harm) - 1
            d = E - hb if last else 4 / len(harm); ps = chord(h)
            pad(padp, hb, h, d + .05, 50 if not full else 60, (70, 115 if full else 100))
            cb.add(hb, low(ps[0]), d, 58)
            arp(harp, hb, h, min(d, 4 / len(harm)), .5, 48)
            if not full and bar % 2 == 0: oud_riff(oud, hb, h, min(d, 4 / len(harm)), .7)
            if full: hn.chord(hb, [ps[1], ps[2], ps[3]], d, 46); oohs.chord(hb, [ps[1] + 12, ps[3]], d, 40)
        if full and not final and k != 7: groove(dr, b, "D...D.t.", .5, FRAME, .8)
        if k == 7: roll(timp, b + 2, b + 4, "A2", 34, 70); timp.add(b + 4, "D2", 3, 78)
        if final:
            vln.chord(b, ["D5", "F#5", "A5", "D6"], E - b, 58, strum=.04); vln.ramp(b, E, 11, 110, 70)
            for i, p_ in enumerate(["D6", "F#6", "A6", "D7"]): cel.add(b + 1 + i * .25, p_, 3, 54 - i * 3)
            oud.chord(b + .5, ["D3", "A3", "D4", "F#4", "A4"], E - b, 54, strum=.05)
    return s


# =============================================================================================== loop section
VAMP = {"home": ("Dm", "bed"), "leaving": ("D", "pluck"), "party": ("D", "dance"), "broke": ("Dm", "drone"),
        "pigs": ("G", "oompah"), "homesick": ("D", "bed"), "road_home": ("A", "shimmer"), "run": ("D", "bed"),
        "feast": ("D", "dance"), "brother": ("D", "bed"), "finale": ("D", "bells")}


def add_vamp(s, chord_name, style):
    """After the composed cue, identical repeats (whole bars, >= VAMP_MIN_SEC, no humanising) of a quiet bed on the
    final chord; the second repeat becomes the sample-exact loop tile (see build_music)."""
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    start_b = s.bars * bpb; start = s.sec(start_b)
    reps = max(4, math.ceil((STRETCH * s.span + XFADE + 2.5 + max(0, s.span - start)) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    padp = P(s, "vamp pad", SLOW_STR, -6, .5, lp=3500, **v); cb = P(s, "vamp bass", CBASS, -10, .3, lp=1100, **v)
    harp = P(s, "vamp harp", HARP, -8, .45, **v)
    ex = {}
    mk = lambda key, *a, **kw: ex.setdefault(key, P(s, f"vamp {key}", *a, **{**v, **kw}))
    if style in ("pluck", "dance"): mk("oud", NYLON, -10, .3); mk("dr", DRUMS, -14, .2, lp=3000)
    if style == "dance": mk("pz", PIZZ, -8, .22)
    if style == "bells": mk("cel", CELESTA, -16, .6)
    if style == "drone": mk("trem", TREM_STR, -16, .55, lp=5000)
    if style == "shimmer": mk("trem", TREM_STR, -12, .55, lp=6500); mk("timp", TIMPANI, -16, .35)
    if style == "oompah": mk("tuba", TUBA, -10, .3, lp=2500); mk("pah", PIZZ, -10, .25)
    for p_ in [padp, cb, harp] + list(ex.values()): p_.vamp = True
    ps = chord(chord_name)
    for r in range(reps):
        b = start_b + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 46 if style not in ("drone",) else 36); padp.cc(b, 11, 92)
        cb.add(b, low(ps[0]), Lb + .2, 48)
        for bar in range(nb):
            bb = b + bar * bpb
            if style in ("bed", "bells", "pluck", "shimmer"):
                for j in range(8): harp.add(bb + j * .5, ps[[0, 1, 2, 3, 2, 3, 2, 1][j]] + 12, 1.4, 44 if j else 50)
            if style == "pluck":
                for j, idx in enumerate([0, 1, 2, 1, 3, 1, 2, 1]): ex["oud"].add(bb + j * .5, ps[idx], .45, 52 if j % 4 == 0 else 40)
                groove(ex["dr"], bb, "D...D.t.", .5, FRAME, .6)
            if style == "dance":
                for q in range(4):
                    ex["pz"].add(bb + q, low(ps[0] if q % 2 == 0 else ps[1]), .4, 64)
                    ex["oud"].chord(bb + q + .5, ps[1:], .35, 46, strum=.02)
                groove(ex["dr"], bb, "D.kOt.kOD.kOtkOk", .25, HAND, .65)
                groove(ex["dr"], bb, "SsSsSsSs", .5, {"S": (TAMB, 36), "s": (TAMB, 24)})
            if style == "drone": ex["trem"].chord(bb, [ps[1] + 24, ps[2] + 12], bpb + .2, 30)
            if style == "shimmer": ex["trem"].chord(bb, [ps[1] + 12, ps[3] + 12], bpb + .2, 34); ex["timp"].add(bb, "A2", 1.5, 40)
            if style == "oompah":
                for q in range(4):
                    if q % 2 == 0: ex["tuba"].add(bb + q, low(ps[0]) if q == 0 else low(ps[1]), .5, 60)
                    else: ex["pah"].chord(bb + q, ps[1:], .3, 44)
        if style == "bells": ex["cel"].add(b + bpb, "A6", 2, 34)
    s.secs = start + reps * L + 2.5
    s.vamp = dict(start=start, secs=L, reps=reps, bars=nb, chord=chord_name, style=style)


def clean_tmp():
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith("music_prodigal_"):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


MUSIC = {"home": cue_home, "leaving": cue_leaving, "party": cue_party, "broke": cue_broke, "pigs": cue_pigs,
         "homesick": cue_homesick, "road_home": cue_road_home, "run": cue_run, "feast": cue_feast,
         "brother": cue_brother, "finale": cue_finale}
KEYS = {"home": "D major -> D minor", "leaving": "D major", "party": "D Hijaz", "broke": "D minor",
        "pigs": "G major", "homesick": "D minor -> D major", "road_home": "D major -> A (dominant)",
        "run": "D major", "feast": "D Mixolydian", "brother": "D minor -> D major", "finale": "D major"}
CUE_NOTES = {k: " ".join(f.__doc__.split()) for k, f in MUSIC.items()}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG
place, fit, room = me.place, me.fit, me.room


def coin_clink(f0, secs=.35):
    """One small silver coin: bright inharmonic partials, a short ring."""
    return me.partials(secs, f0, [1, 1.51, 2.13, 2.71, 3.36], [1, .7, .5, .35, .2], [.09, .07, .05, .04, .03], strike=.4)


def sfx_coins(ctx):
    """A purse of coins: the leather bag's jingle as it changes hands (a dense cluster of small silver clinks and a
    leather rustle), then a handful flung up and landing, each coin bouncing two or three times with shrinking gaps,
    and one coin spinning down to a rattle."""
    secs = 2.6; n = int(secs * SR); y = np.zeros(n)
    m = int(.45 * SR); tt = np.arange(m) / SR
    place(y, me.bp(noise(m), 400, 3000) * np.sin(np.pi * tt / .45) ** 2 * .12, .0)
    for _ in range(16): place(y, coin_clink(R().uniform(3200, 5200), .25) * R().uniform(.2, .55), R().uniform(.03, .42))
    for _ in range(8):
        t = R().uniform(.75, 1.25); dt = R().uniform(.12, .2); lv = R().uniform(.45, .8); f0 = R().uniform(3000, 4800)
        for k in range(int(R().integers(2, 4))):
            place(y, coin_clink(f0 * R().uniform(.99, 1.01), .3) * lv, t)
            place(y, me.lp(noise(int(.01 * SR)), 1500) * me.env_exp(int(.01 * SR), .002) * lv * .3, t)
            t += dt; dt *= .6; lv *= .5
    t, gap, lv, f0 = 1.5, .07, .5, 3900                                            # a spinning coin
    while gap > .006 and t < secs - .2:
        place(y, coin_clink(f0, .08) * lv, t); t += gap; gap *= .88; lv *= .96
    return fit(room(y, "room", .12), secs, fade_out=.25)


def sfx_wind_dry(ctx):
    """The famine wind (7 s): a hot, dry broadband gust that builds over 1.5 s and sighs in slow gusts, a faint
    hollow whistle in two narrow bands, a dust-and-grit hiss of sand grains and a low rumble; eases off."""
    secs = 7.0; n = int(secs * SR); t = np.arange(n) / SR
    gust = .35 + .65 * me.smooth_rand(n, .5, 0, 1) ** 1.5
    y = me.bp(noise(n), 250, 2600) * gust
    w = noise(n); y += (me.resonator(w, 820, 35) + me.resonator(w, 1240, 45) * .7) * gust ** 2 * .05
    y += ru.straw_ticks(n, 260, .5, secs - 1, .35, 2500, 9000) * gust
    y += me.lp(noise(n), 120) * .5
    y *= np.minimum(1, t / 1.5)
    return fit(room(y, "room", .06), secs, fade_out=2.0)


def sfx_oink(ctx):
    """Pigs: one pig's comic 'oink-oink' (two creaky, nasal, rising grunts), a snuffly rooting snort, and a lower
    'hrrnk' from a second pig further off."""
    secs = 1.5; n = int(secs * SR); y = np.zeros(n)
    place(y, pig_grunt(.2, 150, 1.45), .02); place(y, pig_grunt(.22, 140, 1.4, [(0, "u"), (.5, "o"), (1, "o")]), .3)
    place(y, snuffle(.28) * .45, .65)
    place(y, me.lp(pig_grunt(.32, 95, 1.15, [(0, "o"), (.5, "u"), (1, "u")], 24), 2500) * .55, 1.0)
    return fit(room(y, "room", .1), secs, fade_out=.15)


def sfx_tummy(ctx):
    """A hungry tummy: a long, wobbling low growl (a buzzy 70-130 Hz voice, low-passed, with a gurgling flutter),
    then three bubbly 'blorp' gurgles rising in pitch."""
    secs = 1.8; n = int(secs * SR); t = np.arange(n) / SR
    m = int(1.25 * SR); tt = np.arange(m) / SR
    f = 95 + 25 * me.smooth_rand(m, 5) + 30 * np.sin(np.pi * tt / 1.25)
    g = me.lp(me.glottal(f, tilt=1.4), 450) * (.5 + .5 * me.smooth_rand(m, 22, 0, 1)) ** 2
    g *= np.sin(np.pi * tt / 1.25) ** .8
    y = np.zeros(n); place(y, g / (np.max(np.abs(g)) + 1e-9), .05)
    for at, f0, f1 in ((1.22, 180, 420), (1.38, 220, 520), (1.5, 160, 380)):
        k = int(.06 * SR); u = np.arange(k) / SR
        b = np.sin(2 * np.pi * np.cumsum(np.linspace(f0, f1, k)) / SR) * np.exp(-u / .025)
        place(y, b * .6, at)
    return fit(room(y, "room", .1), secs, fade_out=.2)


def sfx_footsteps_run(ctx):
    """The father runs (2.6 s): an old man's quick, joyful running steps on a dirt road coming closer (heel thud,
    sandal slap, a scuff of grit), his robe flapping every other step, a last skidding double step into the hug and
    a soft whump of cloth."""
    secs = 2.6; n = int(secs * SR); y = np.zeros(n)
    t = .05; i = 0
    while t < 2.2:
        u = t / 2.2; lv = .45 + .55 * u; side = 1.0 if i % 2 == 0 else .82
        m = int(.15 * SR); tt = np.arange(m) / SR
        thud = np.sin(2 * np.pi * np.cumsum(110 * np.exp(-tt / .02) + 60) / SR) * np.exp(-tt / .035) * .8
        thud += me.lp(noise(m), 500) * np.exp(-tt / .02) * .6
        slap = me.bp(noise(m), 1200, 5000) * me.env_exp(m, .012, .012) * (.25 + .2 * u)
        scuff = me.bp(noise(m), 2500, 8000) * np.exp(-((tt - .05) / .025) ** 2) * .08
        place(y, (thud + slap + scuff) * lv * side, t + R().normal(0, .008))
        if i % 2 == 1:
            k = int(.2 * SR); place(y, me.bp(noise(k), 300, 1800) * np.sin(np.pi * np.arange(k) / k) * .1 * lv, t - .05)
        t += .255 * R().uniform(.95, 1.05); i += 1
    for at, lv in ((2.22, 1.0), (2.36, .7)):                                        # skid into the hug
        m = int(.18 * SR); tt = np.arange(m) / SR
        sk = me.bp(noise(m), 1500, 7000) * np.sin(np.pi * tt / .18) * .25 + me.lp(noise(m), 400) * np.exp(-tt / .03) * .5
        place(y, sk * lv, at)
    k = int(.3 * SR); place(y, me.bp(noise(k), 200, 1500) * np.sin(np.pi * np.arange(k) / k) ** 2 * .25, 2.3)
    return fit(room(y, "room", .08), secs, fade_out=.15)


def sfx_birds(ctx):
    """Galilee morning (11 s, one-shot): Ruth's warbler / 'tee-oo' / trill bird synth (own seed), lengthened, plus a
    soft collared-dove 'coo-COO-coo' twice from a tree; fades out."""
    loop = ru.sfx_birds(ctx); y = np.concatenate([loop, loop])[:int(11 * SR)]
    for at in (2.0, 6.6):
        for j, (d, f, a) in enumerate(((.28, 520, .5), (.42, 560, .8), (.3, 500, .5))):
            m = int(d * SR); tt = np.arange(m) / SR
            co = ru.tone(d, f * (1 - .05 * tt / d), 1.0, h2=.06) * np.sin(np.pi * tt / d) ** 2 + me.lp(noise(m), 900) * .03
            place(y, me.lp(co, 1400) * a * .09, at + j * .36)
    return fit(y, 11.0, fade_in=.4, fade_out=2.5)


def sfx_crickets_night(ctx):
    """The feast night and the brother outside (seamless 20 s loop): Ruth's five-cricket night synth with the
    prodigal pack's own seed (one soft distant owl)."""
    return ru.sfx_crickets_night(ctx)


def sfx_sparkle(ctx):
    """The son's idea / the robe and ring: Esther's shower of tiny bells (D major pentatonic), shared synth."""
    return me.sfx_sparkle()


def sfx_cheer(ctx):
    """The friends' 'Yay!' at the party / the household at the feast: Esther's crowd synth (own seed) plus a few
    rhythmic claps."""
    y = me.sfx_cheer(); n = len(y)
    for k in range(10):
        at = .6 + k * .52
        for _ in range(4):
            m = int(.05 * SR); fc = R().uniform(1000, 2200)
            place(y, me.bp(noise(m), fc * .6, fc * 1.8) * me.env_exp(m, .009) * .12, at + R().normal(0, .012))
    return y[:n]


SFX = {"birds": sfx_birds, "coins": sfx_coins, "cheer": sfx_cheer, "wind_dry": sfx_wind_dry, "oink": sfx_oink,
       "tummy": sfx_tummy, "sparkle": sfx_sparkle, "footsteps_run": sfx_footsteps_run,
       "crickets_night": sfx_crickets_night}
LOOP_SECS = {"crickets_night": 20.0}
BEDS = {"crickets_night": dict(startAtCue="feast", stopAtCue="finale")}     # CONTRACT 7: from S11, stop at finale
SFX_GAIN = {"birds": -14, "coins": -9, "cheer": -8, "wind_dry": -12, "oink": -8, "tummy": -6, "sparkle": -9,
            "footsteps_run": -7, "crickets_night": -18}
SFX_NOTES = {k: " ".join(f.__doc__.split()) for k, f in SFX.items()}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3), secs=round(end - c["t"] + XFADE, 3),
                        last=i + 1 == len(cues)))
    return out


def bed_span(tl, sid):
    """(start t, stop t) of an ambience bed: from the start of BEDS[sid].startAtCue (or its timeline event if the
    lead adds one) to the start of stopAtCue."""
    ev = [e["t"] for e in tl["sfx"] if e["id"] == sid]
    mt = {m["cue"]: m["t"] for m in tl["music"]}
    t0 = min(ev) if ev else mt.get(BEDS[sid]["startAtCue"], 0.0)
    return t0, mt.get(BEDS[sid]["stopAtCue"], tl["duration"])


def build_music(tl, only=None):
    spans = cue_spans(tl)
    names = [c["cue"] for c in spans]
    assert len(set(names)) == len(names), "a prodigal cue plays twice"
    missing = sorted(set(names) - set(MUSIC)); assert not missing, f"no composer for cue(s) {missing}"
    path_json = f"{MUSIC_DIR}/cues.json"
    old = {c["cue"]: c for c in json.load(open(path_json))["cues"]} if only and os.path.exists(path_json) else {}
    manifest = []
    for c in spans:
        if only and c["cue"] not in only and c["cue"] in old: manifest.append(old[c["cue"]]); continue
        me.seed("prodigal/" + c["cue"]); ctx = Ctx(tl, c["cue"], c["t"], c["span"], c["secs"], c["last"])
        sc = MUSIC[c["cue"]](ctx)
        add_vamp(sc, *VAMP[c["cue"]]); vp = sc.vamp
        main, vamp = ru.render_split(sc)
        for sec, a, wet in getattr(sc, "overlays", []): place(main, room(a, "hall", wet), sec)
        if getattr(sc, "autom", None): main = apply_autom(main, sc.autom)
        n = int(round(sc.secs * SR)); main = me.hp(me.fit(main, sc.secs, fade_out=0), 28); vamp = me.hp(me.fit(vamp, sc.secs, fade_out=0), 28)
        ns, ls, le = int(c["span"] * SR), int(round((vp["start"] + vp["secs"]) * SR)), int(round((vp["start"] + 2 * vp["secs"]) * SR))
        # loop tile = the second repeat as rendered, its first 30 ms blended from the third repeat's start (Ruth)
        L = le - ls; kx = int(.03 * SR); w = np.linspace(0, 1, kx)
        T = vamp[ls:le].copy(); T[:kx] = vamp[le:le + kx] * (1 - w) + vamp[ls:ls + kx] * w
        vs = np.zeros(n); p0 = ls - L
        for j in range(0, (n - p0) // L + 1):
            q = p0 + j * L; m_ = min(L, n - q)
            if m_ > 0: vs[q:q + m_] = T[:m_]
        kf = int(.5 * SR); main[ls - kf:ls] *= np.linspace(1, 0, kf) ** 2; main[ls:] = 0
        gm = MUSIC_LUFS - ru.lufs_of(main[:ns])["lufs"]
        gv = MUSIC_LUFS + VAMP_REL_DB - ru.lufs_of(T)["lufs"]
        x = main * 10 ** (gm / 20) + vs * 10 ** (gv / 20)
        if ru.lufs_of(x)["truePeak"] > -1.3:
            cl = 10 ** (-1.6 / 20); x = np.tanh(x / cl) * cl
        k = int(2.5 * SR); x[-k:] *= np.linspace(1, 0, k) ** 2
        path = f"{MUSIC_DIR}/{c['cue']}.wav"; me.write_wav(path, x); m = me.measure(path)
        m_span, m_loop = ru.lufs_of(x[:ns]), ru.lufs_of(x[ls:le])
        secs = round(len(x) / SR, 3); need = c["span"] * (1 + STRETCH) + XFADE
        assert secs + 1e-3 >= need, f"{c['cue']} is {secs}s, needs {need}s (span +30 % + crossfade)"
        e = dict(cue=c["cue"], t=c["t"], span=c["span"], secs=secs, lastCue=c["last"], loop=False,
                 loopStart=round(ls / SR, 6), loopEnd=round(le / SR, 6), loopStartSample=ls, loopEndSample=le,
                 loopFromSec=round(vp["start"], 3), plainTailSec=round(secs - c["span"], 3), key=KEYS[c["cue"]],
                 meter="4/4", bars=sc.bars, bpm=round(sc.bpm, 1), loopBars=vp["bars"], loopChord=vp["chord"],
                 lufs=round(m_span["lufs"], 1), loopLufs=round(m_loop["lufs"], 1), truePeak=round(m["truePeak"], 1))
        manifest.append(e); clean_tmp()
        print(f"music {c['cue']:9s} t={c['t']:7.2f} span={c['span']:6.2f} file={secs:6.2f}s bars={sc.bars:2d} "
              f"bpm={e['bpm']:5.1f} span I={e['lufs']:6.1f} loop {e['loopStart']:.2f}-{e['loopEnd']:.2f}s "
              f"I={e['loopLufs']:6.1f} TP={e['truePeak']:5.1f} dBTP", flush=True)
    json.dump(dict(rule="Start each cue at its timeline t at full level and fade the previous cue out over 0.6 s from "
                        "that t. Each cue's composed music ends on its cadence at loopFromSec (= span); after it the "
                        "cue continues into a quiet loop section on its final chord. If the section is stretched "
                        "(longer voice clips), either loop [loopStart, loopEnd) seamlessly (seconds, sample-accurate) "
                        "until the next cue, or just keep playing: every file is at least span x 1.3 + 0.6 s "
                        "(plainTailSec after the span) and fades out over its last 2.5 s. The span sits at -20 LUFS, "
                        "the loop section ~3 dB under it. Duck music ~7 dB under voice lines. Rerun "
                        "tools/story/music_prodigal.py after the timeline is re-timed so the in-cue hits follow.",
                   crossfadeSec=XFADE, lufs=MUSIC_LUFS, stretchCovered=STRETCH, cues=manifest),
              open(path_json, "w"), indent=1, ensure_ascii=False)
    return manifest


def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]} | set(BEDS)); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in needed:
        me.seed("prodigal/" + sid)
        ev = [s["t"] for s in tl["sfx"] if s["id"] == sid]
        x = me.hp(np.asarray(SFX[sid](dict(tl=tl, t=min(ev) if ev else None)), np.float64), 30)
        x = me.peak_normalize(x, SFX_PEAK_DB); path = f"{SFX_DIR}/{sid}.wav"; me.write_wav(path, x); m = me.measure(path)
        loop = sid in LOOP_SECS
        e = dict(id=sid, secs=round(len(x) / SR, 3), loop=loop, gainDb=SFX_GAIN[sid],
                 samplePeak=round(m["samplePeak"], 1), truePeak=round(m["truePeak"], 1),
                 lufs=None if m["lufs"] == float("-inf") else round(m["lufs"], 1))
        if loop:
            t0, _ = bed_span(tl, sid)
            e.update(loopStart=0.0, loopEnd=e["secs"], fadeInSec=1.0, fadeOutSec=1.5, **BEDS[sid],
                     inTimeline=bool(ev), t=round(t0, 2))
        manifest.append(e); clean_tmp()
        print(f"sfx   {sid:14s} {e['secs']:6.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f}"
              + (f" loop, {BEDS[sid]['startAtCue']} -> {BEDS[sid]['stopAtCue']}" if loop else ""), flush=True)
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play each one-shot at its timeline t with gainDb "
                        "(recommended mix level). Entries with loop: true are ambience beds: the whole file is a "
                        "seamless loop (loopStart 0, loopEnd = secs); start it with a fadeInSec fade-in at its timeline "
                        "sfx event, or, if the timeline has none (inTimeline: false), when the music cue startAtCue "
                        "starts (t is that time in the current timeline), and loop it until the music cue named in "
                        "stopAtCue starts (fade out over fadeOutSec).",
                   peakDbfs=SFX_PEAK_DB, sfx=manifest), open(f"{SFX_DIR}/mix.json", "w"), indent=1, ensure_ascii=False)
    return manifest


def build_preview(tl):
    n = int((tl["duration"] + 1.0) * SR); mus = np.zeros(n); fx = np.zeros(n); vo = np.zeros(n)
    for c in cue_spans(tl):
        x = me.load_any(f"{MUSIC_DIR}/{c['cue']}.wav")
        k0 = int(c["span"] * SR); k = int((XFADE if not c["last"] else 0.9) * SR); seg = x[k0:k0 + k]
        x[k0:k0 + len(seg)] *= np.linspace(1, 0, len(seg)); x[k0 + k:] = 0
        place(mus, x, c["t"])
    events = [(s["t"], s["id"]) for s in tl["sfx"] if s["id"] not in BEDS]
    events += [(bed_span(tl, sid)[0], sid) for sid in BEDS]
    for t, sid in events:
        y = me.load_any(f"{SFX_DIR}/{sid}.wav") * 10 ** (SFX_GAIN[sid] / 20)
        if sid in LOOP_SECS:
            t0, t1 = bed_span(tl, sid)
            m_ = int((t1 - t0 + 1.5) * SR); y = np.tile(y, m_ // len(y) + 1)[:m_]
            y[:SR] *= np.linspace(0, 1, SR); k = int(1.5 * SR); y[-k:] *= np.linspace(1, 0, k)
        place(fx, y, t)
    used = 0; envv = np.zeros(n, bool)
    for line in tl["lines"]:
        hit = False
        for ext in ("wav", "mp3"):
            p = f"{VOICE_DIR}/{line['id']}.{ext}"
            if os.path.exists(p): place(vo, me.load_any(p), line["t"]); used += 1; hit = True; break
        if not hit:
            i0 = int(line["t"] * SR); envv[i0:i0 + int(line.get("maxSec", 4) * .85 * SR)] = True
    if used: envv |= me.lp(np.abs(vo), 8) > 0.004
    look = int(.08 * SR); envv = np.r_[envv[look:], np.zeros(look, bool)]
    g = np.where(envv, 10 ** (DUCK_DB / 20), 1.0); out = np.empty(n); cur = 1.0
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


# =============================================================================================== objective checks
def check(tl, png=None):
    """Measure the written files: loop seam continuity (jump loopEnd -> loopStart vs. playing straight on), tile
    identity, clipping, true peak, span loudness, 0.5 s level dips inside each span, energy above 2 kHz; sfx peaks;
    optionally a spectrogram of every cue (png)."""
    cues = json.load(open(f"{MUSIC_DIR}/cues.json"))["cues"]; rows = []
    for c in cues:
        sr, x = wavfile.read(f"{MUSIC_DIR}/{c['cue']}.wav"); x = x.astype(np.float64) / 32768
        a, b = c["loopStartSample"], c["loopEndSample"]; L = b - a
        tile_diff = float(np.max(np.abs(x[a:b] - x[b:b + L]))) if b + L <= len(x) - int(2.6 * SR) else float("nan")
        seam = abs(x[b - 1] - x[a]); normal = np.percentile(np.abs(np.diff(x[a:b])), 99.9)
        clip = int(np.sum(np.abs(x) >= 32767 / 32768))
        span = x[:int(c["span"] * SR)]; w = int(.5 * SR)
        rms = [20 * np.log10(np.sqrt(np.mean(span[i:i + w] ** 2)) + 1e-9) for i in range(0, len(span) - w, w)]
        f, P_ = signal.welch(span, SR, nperseg=8192); hi = float(np.sum(P_[f > 2000]) / np.sum(P_) * 100)
        lo = float(np.sum(P_[f < 150]) / np.sum(P_) * 100)
        rows.append((c["cue"], c["lufs"], c["truePeak"], tile_diff, seam, normal, clip, min(rms), hi, lo))
        print(f"check {c['cue']:9s} I={c['lufs']:6.1f} TP={c['truePeak']:5.1f} tileDiff={tile_diff:.1e} seamStep={seam:.4f} "
              f"(p99.9 step {normal:.4f}) clipped={clip} min0.5sRMS={min(rms):6.1f} max={max(rms):6.1f} dB  "
              f">2k={hi:4.1f}%  <150={lo:4.1f}%")
    mix = json.load(open(f"{SFX_DIR}/mix.json"))["sfx"]
    for s in mix:
        sr, x = wavfile.read(f"{SFX_DIR}/{s['id']}.wav"); x = x.astype(np.float64) / 32768
        extra = ""
        if s["loop"]: extra = f" wrapStep={abs(x[-1] - x[0]):.4f} (p99.9 {np.percentile(np.abs(np.diff(x)), 99.9):.4f})"
        clip = int(np.sum(np.abs(x) >= 32767 / 32768))
        print(f"check sfx {s['id']:14s} peak={20 * np.log10(np.max(np.abs(x))):5.2f} dBFS TP={s['truePeak']:5.1f} clipped={clip}{extra}")
    if png:
        import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
        fig, axs = plt.subplots(len(cues), 1, figsize=(14, 2.1 * len(cues)))
        for ax, c in zip(axs, cues):
            sr, x = wavfile.read(f"{MUSIC_DIR}/{c['cue']}.wav"); x = x.astype(np.float64) / 32768
            ax.specgram(x, NFFT=2048, Fs=SR, noverlap=1024, cmap="magma", vmin=-130, vmax=-30)
            ax.set_ylim(0, 6000); ax.axvline(c["span"], color="c"); ax.axvline(c["loopStart"], color="w", ls="--")
            ax.axvline(c["loopEnd"], color="w", ls="--"); ax.set_ylabel(c["cue"], rotation=0, ha="right")
        plt.tight_layout(); plt.savefig(png, dpi=70); print("spectrogram ->", png)
    return rows


def update_doc(tl, cues, sfx, prev):
    if not os.path.exists(DOC): return
    txt = open(DOC).read()
    def swap(tag, body):
        nonlocal txt
        txt = re.sub(rf"(<!-- {tag}:start -->\n).*?(<!-- {tag}:end -->)", lambda m: m.group(1) + body + m.group(2), txt, flags=re.S)
    if cues:
        rows = ["| Cue | t (s) | Span (s) | File (s) | Loop (s) | Stretch covered | Key | Bars × bpm | LUFS span / loop | TP (dBTP) |",
                "|---|---|---|---|---|---|---|---|---|---|"]
        for c in cues:
            plain = (c["secs"] - XFADE) / c["span"] - 1
            rows.append(f"| `{c['cue']}` | {c['t']:.2f} | {c['span']:.2f} | {c['secs']:.2f} | {c['loopStart']:.3f}–{c['loopEnd']:.3f} "
                        f"({c['loopBars']} bar{'s' if c['loopBars'] > 1 else ''} on {c['loopChord']}) | loop: any; plain: +{plain * 100:.0f} % "
                        f"| {c['key']} | {c['bars']} × {c['bpm']} (4/4) | {c['lufs']:.1f} / {c['loopLufs']:.1f} | {c['truePeak']:.1f} |")
        rows += ["", "| Cue | What it does (from the composer function's docstring) |", "|---|---|"]
        rows += [f"| `{c['cue']}` | {CUE_NOTES[c['cue']]} |" for c in cues]
        swap("cues", "\n".join(rows) + "\n")
    if sfx:
        rows = ["| Id | Length (s) | Loop | Sample peak (dBFS) | True peak (dBTP) | LUFS | gainDb | Notes |", "|---|---|---|---|---|---|---|---|"]
        for s in sfx:
            lp_ = f"whole file, from `{s['startAtCue']}` to `{s['stopAtCue']}`" if s["loop"] else "one-shot"
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
    ap.add_argument("--check", action="store_true", help="only measure the written files")
    ap.add_argument("--png", default="", help="with --check: write a spectrogram of every cue to this path")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    tl = json.load(open(TIMELINE))
    if a.check: check(tl, a.png or None); sys.exit(0)
    tempfile.tempdir = tempfile.mkdtemp(prefix="music_prodigal_")
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
