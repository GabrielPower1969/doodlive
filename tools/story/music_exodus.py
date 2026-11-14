#!/usr/bin/env python3
"""Original score and sound effects for "Exodus" (story pack #4; docs/exodus/CONTRACT.md section 7, docs/exodus/MUSIC.md).

Same machinery as Ruth and Esther, shared rather than forked: this script imports tools/story/music_esther.py
(Score / Part / mel / groove, the FluidSynth renderer, the synthetic hall, loudness and file helpers, the synthesis
primitives) and tools/story/music_ruth.py (the split render for loop sections, the loop wrap, the cricket synth) as
libraries and changes neither, so their outputs are untouched. Only the Exodus cues, effects and paths live here.

The score is built around one original melody, the **freedom theme** (FREEDOM below, 8 bars). Its head is a rising
5-note figure D-E-F#-A-D. It is first heard as a seed in D Phrygian dominant (E -> Eb, the "Egyptian" augmented
second Eb-F#) on the ney when Miriam prays in the brick yard (slavery), on horns when God says "bring my people out"
(bush) and slowly on the ney through the Passover night; it turns to D major when Moses says "I'll go" (bush), is
the walking tune of the exodus (S08), gets its full statement when the sea walls stand (sea, S11) and closes the
story (finale). Miriam's song (S13) opens with the same five notes in 6/8 at a fixed dotted-quarter = 112.

Every name and time comes from assets/exodus/timeline.json, read on every run: cue lengths follow the music spans,
and every in-cue hit (Pharaoh's lines, God's call, the snake, the plagues, the sea parting / standing / closing,
the wheel, the sneeze, the golden rays) is looked up by event, so after the voices re-time the timeline, just rerun
this script. Every cue continues after its cadence into a quiet loop section on its final chord (cues.json gives a
sample-exact seamless loop) and runs at least 30 % past its span as a plain tail, as Ruth.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/exodus/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated, true peak <= -1 dBTP
  assets/exodus/audio/music/cues.json        cue lengths, spans, loop points, loudness; `song` also its beat grid
  assets/exodus/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/exodus/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain
  assets/exodus/audio/preview_mix.mp3        rough full-length mix at timeline times (a check, not an app asset)
  docs/exodus/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_exodus.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       python3 tools/story/music_exodus.py --check      # loop seams, clipping, loudness, spectra of the outputs
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
                          CHOIR, OOHS, FLUTE, SHAKU, OBOE, BASSOON, CLARINET, TIMPANI, TAIKO, HORN, TRUMPET, TROMBONE,
                          TUBA, MUTED_TPT, DRUMS, BDRUM, CLAP, TAMB, CRASH, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA,
                          LO_CONGA, HI_WOOD, LO_WOOD, SHAKER, TRIANGLE, SNARE)
from music_ruth import end_beats, bar_of                                   # noqa: E402

ROOT = me.ROOT
EX = f"{ROOT}/assets/exodus"
TIMELINE = f"{EX}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{EX}/audio/music", f"{EX}/audio/sfx", f"{EX}/audio/voice/zh"
PREVIEW = f"{EX}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/exodus/MUSIC.md"
STRETCH = 0.30                 # every cue survives its section being stretched by at least this much (re-timing)
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -3.0             # loop section loudness relative to the cue's composed span
SONG_DQ_BPM = 112.0            # Miriam's song: 6/8, dotted quarter = 112 (fixed; the voice role chants on this grid)

VIOLA, CRYSTAL, BOWED_PAD, CHOIR_PAD, PICCOLO = 41, 98, 92, 91, 72
SIDE_STICK, RIDE, RIDE_BELL, CLAVES, LO_TOM, HI_TOM, CABASA, VIBRASLAP = 37, 51, 53, 75, 45, 50, 69, 58

CH = dict(me.CH)
CH.update({"Bm": ["B2", "F#3", "B3", "D4"], "Em": ["E3", "B3", "E4", "G4"], "E": ["E2", "B2", "E3", "G#3"],
           "Dsus": ["D3", "A3", "D4", "G4"], "Ddim": ["D3", "Ab3", "D4", "F4"], "Bbm": ["Bb2", "F3", "Bb3", "Db4"],
           "Dm/A": ["A2", "F3", "A3", "D4"], "Gm/D": ["D3", "G3", "Bb3", "D4"], "D5": ["D2", "A2", "D3", "A3"],
           "Dmaj9": ["D3", "A3", "E4", "F#4"], "Fm": ["F2", "C3", "F3", "Ab3"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p


# =============================================================================================== the freedom theme
# Original. Written in D major; pd(...) gives the D Phrygian-dominant form (E -> Eb, B -> Bb, C# -> C).
FREEDOM = {
    1: [("D4", 1.5), ("E4", .5), ("F#4", 1), ("A4", 1)],              # the rising 5-note figure (with bar 2's D5)
    2: [("D5", 2), ("C#5", 1), ("B4", 1)],
    3: [("A4", 1.5), ("G4", .5), ("F#4", 1), ("E4", 1)],
    4: [("F#4", 1), ("G4", .5), ("A4", .5), ("E4", 2)],                # half cadence
    5: [("D4", 1.5), ("E4", .5), ("F#4", 1), ("A4", 1)],
    6: [("D5", 1.5), ("E5", .5), ("F#5", 1), ("E5", 1)],               # climbs higher
    7: [("D5", 1), ("B4", 1), ("C#5", 1), ("E5", 1)],
    8: [("D5", 4)],
}
FREE_HARM = {1: ["D"], 2: ["Bm", "A"], 3: ["D", "A"], 4: ["D", "A"], 5: ["D"], 6: ["G", "A"], 7: ["G", "A"], 8: ["D"]}
PD_HARM = {1: ["D"], 2: ["Gm", "Eb"], 3: ["D"], 4: ["D", "Eb"], 5: ["D"], 6: ["Eb", "D"], 7: ["Gm", "Cm"], 8: ["D"]}
FIGURE = [("D4", 1.5), ("E4", .5), ("F#4", 1), ("A4", 1), ("D5", 4)]   # the head alone, resolved


def pd(notes):
    """D major spelling -> D Phrygian dominant (E->Eb, B->Bb, C#->C); keeps rests and suffixes."""
    def conv(p):
        if p is None: return None
        p = re.sub(r"C#(?=\d)", "C", p); p = re.sub(r"E(?=\d)", "Eb", p); return re.sub(r"B(?=\d)", "Bb", p)
    return [(conv(p), d) for p, d in notes]


def theme(bars, phrygian=False, scale=1.0):
    out = []
    for k in bars: out += [(p, d * scale) for p, d in (pd(FREEDOM[k]) if phrygian else FREEDOM[k])]
    return out


# =============================================================================================== small helpers
# Winds, bowed strings, brass and voices sustain (Ruth's fix for the DLS bank's decaying envelopes, music_ruth.P):
# an NRPN generator offset (SoundFont gen 37 volEnvSustain -1440 cB) restores a full sustain on every such part.
SUSTAIN = set(ru.SUSTAIN) | {SHAKU, TRUMPET, TROMBONE, TUBA, MUTED_TPT, BOWED_PAD, CHOIR_PAD, PICCOLO}


def P(s, name, program, *a, **kw):
    p = s.part(name, program, *a, **kw)
    if program in SUSTAIN:
        d = 8192 - 1440
        p.cc(0, 99, 120); p.cc(0, 98, 37); p.cc(0, 6, d >> 7); p.cc(0, 38, d & 127)
    return p


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


FRAME = {"D": (LO_CONGA, 84), "t": (MUTE_CONGA, 52), "k": (OPEN_CONGA, 34), "s": (TAMB, 26)}
DARB = {"D": (LO_CONGA, 96), "T": (HI_BONGO, 84), "t": (LO_BONGO, 62), "k": (HI_BONGO, 40), "s": (TAMB, 34)}
HAND = {"D": (LO_CONGA, 92), "O": (OPEN_CONGA, 78), "t": (MUTE_CONGA, 60), "k": (HI_BONGO, 56), "b": (LO_BONGO, 66)}
WAR = {"B": (TAIKO, 100), "b": (TAIKO, 70), "T": (LO_TOM, 84), "t": (HI_TOM, 60), "S": (SNARE, 70), "s": (SNARE, 40)}


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- slavery
NEY_SLAVE = [[("A4^Bb4", 2), ("G4", 1), ("F4", 1), ("E4", 1.5), ("F4", .5), ("D4", 2)],
             [("F4", 1), ("E4", .5), ("D4", .5), ("C#4^D4", 2), ("D4", 4)]]
SLAVE_HARM = ["Dm", "Dm", "Bb", "A", "Dm", "Gm/D", "Dm", "A"]


def cue_slavery(c):
    """D minor, heavy and slow. A work rhythm on low frame drum and taiko (beats 1 and 3), a hammer-on-stone accent at
    the top of every bar, low strings heaving on Dm-A, a sad ney (shakuhachi + flute breath) above in long notes.
    Pharaoh's 'Faster!' gets a pompous low-brass grunt (his own motif). For Miriam's prayer the drums stop and the ney
    plays the freedom figure for the first time, in D Phrygian dominant, over a bare open fifth."""
    s = Score(c, 60, 4); n = s.bars; total = n * 4; E = end_beats(s)
    ney = P(s, "ney (shakuhachi)", SHAKU, -2, .42, lp=5000, human=.012)
    ney2 = P(s, "ney breath (flute)", FLUTE, -15, .42, lp=3500, human=.012)
    vc = P(s, "low strings", CELLO, -4, .38, lp=3000)
    padp = P(s, "string pad", SLOW_STR, -7, .45, lp=2800)
    cb = P(s, "contrabass", CBASS, -6, .3, lp=900)
    dr = P(s, "frame drum", DRUMS, -6, .2, lp=2500, human=.006)
    hm = P(s, "hammer", DRUMS, -9, .25, lp=6000, human=.003)
    timp = P(s, "timpani", TIMPANI, -10, .3)
    tuba = P(s, "pharaoh tuba", TUBA, -6, .3, lp=2500)
    bsn = P(s, "pharaoh bassoon", BASSOON, -8, .3, lp=3000)
    ph_t = s.at(c.first("lines", who="pharaoh")); pr_t = s.at(c.first("lines", who="miriam"))
    pr_b = int(pr_t // 4) if pr_t is not None else n - 2
    pr_b = min(max(pr_b, 2), n - 1)
    # ney lament until the prayer bar
    b = 0.0; i = 0
    while b < pr_b * 4 - 3:
        ph = NEY_SLAVE[i % 2]; L = sum(d for _, d in ph)
        if b + L > pr_b * 4 - .5:
            cut, acc = [], 0
            for p_, d in ph:
                if acc + d > pr_b * 4 - b - .5: break
                cut.append((p_, d)); acc += d
            ph = cut
        mel(ney, b + .5, ph, 64, legato=.97, vib=True); mel(ney2, b + .5, ph, 44, legato=.97)
        b += L + 2; i += 1
    for bar in range(n):
        bb = bar * 4; work = bar < pr_b; final = bar == n - 1
        if work:
            h = SLAVE_HARM[bar % 8]; ps = chord(h)
            pad(padp, bb, h, 4, 40, (60, 92))
            vc.add(bb, low(ps[0]) + 12, 1.9, 66); vc.add(bb + 2, ps[1] - 12 if ps[1] - 12 >= note("C2") else ps[1], 1.9, 58)
            cb.add(bb, low(ps[0]), 2, 60); cb.add(bb + 2, low(ps[0]), 2, 50)
            groove(dr, bb, "D...t.k.D...t...", .25, FRAME, .95)
            dr.add(bb, TAIKO, .5, 74); dr.add(bb + 2, TAIKO, .5, 58)
            hm.add(bb, SIDE_STICK, .2, 92); hm.add(bb + .02, LO_WOOD, .2, 70); hm.add(bb, RIDE_BELL, .3, 40)
            timp.add(bb, "D2", 1.2, 58)
        else:                                                   # Miriam's prayer: drums stop, open fifth, ney figure
            d = 4 if not final else E - bb
            padp.chord(bb, ["D3", "A3", "D4"], d + .2, 44); padp.ramp(bb, bb + 2, 11, 70, 96)
            cb.add(bb, "D2", d, 52); vc.add(bb, "A2", d, 46)
    # Pharaoh's grunt: his motif, low and pompous, on his line
    if ph_t is not None and ph_t < pr_b * 4 - 2:
        mot = [("D3", .75), ("D3", .25), ("A3", 1), ("F#3.", .5), ("D3.", .5)]
        mel(tuba, ph_t, mot, 78, shift=-12); mel(bsn, ph_t, mot, 70)
    # the prayer: freedom figure in D Phrygian dominant, slow, ending on D5 into the file's end
    fb = pr_b * 4 + (0 if pr_t is None else max(0, min(1.0, pr_t + 1 - pr_b * 4)))
    fig = pd(FIGURE)[:4]; k = max(.55, min(1.0, (total - fb - 1.5) / 4))
    end = mel(ney, fb, [(p_, d * k) for p_, d in fig], 66, legato=.98, vib=True)
    mel(ney2, fb, [(p_, d * k) for p_, d in fig], 44, legato=.98)
    ney.add(end, "D5", E - end - .3, 62); ney.vibrato(end, E - end - .3, 30); ney2.add(end, "D5", E - end - .3, 40)
    harp = P(s, "harp", HARP, -10, .45)
    for j, p_ in enumerate(["D3", "A3", "D4", "A4"]): harp.add(end + j * .15, p_, 3, 44 - j * 2)
    return s


# ----------------------------------------------------------------------------------------------- desert
DES_TUNE = [[("E5", 2), ("D5", 1), ("C5", .5), ("B4", .5)], [("A4", 3), (None, 1)],
            [("C5", 1.5), ("D5", .5), ("E5", 1), ("G5", 1)], [("E5", 2), ("D5", 1), ("B4", 1)]]


def cue_desert(c):
    """A minor pastoral, wide and quiet: a drone (contrabass + cello on A-E, a breath of low pad), a solo ney/flute
    in long notes (a short phrase before the narrator, then long notes in his gaps), a lone harp now and then, soft
    triangle and glockenspiel 'sheep-bell' tinkles at irregular times."""
    s = Score(c, 72, 4); n = s.bars; E = end_beats(s)
    fl = P(s, "ney flute", FLUTE, -3, .5, lp=6000, human=.01)
    ney = P(s, "ney (shakuhachi)", SHAKU, -10, .5, lp=4500, human=.01)
    dr1 = P(s, "drone cello", CELLO, -6, .45, lp=2500)
    cb = P(s, "drone bass", CBASS, -8, .35, lp=900)
    padp = P(s, "air pad", SLOW_STR, -13, .55, lp=3000)
    harp = P(s, "harp", HARP, -10, .5, human=.008)
    bells = P(s, "bell tinkles", GLOCK, -24, .5, human=.02)
    tri = P(s, "triangle", DRUMS, -24, .5, human=.02)
    narr = s.at(c.first("lines", who="narrator"))
    dr1.add(0, "A2", E, 52); dr1.add(0, "E3", E, 40); cb.add(0, "A1", E, 50)
    dr1.ramp(0, 3, 11, 40, 100); cb.ramp(0, 3, 11, 40, 100)
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        h = ["Am", "Am", "G", "Am"][bar % 4] if not final else "Am"; d = 4 if not final else E - b
        padp.chord(b, chord(h)[1:], d + .2, 30)
        if bar % 2 == 0 or final: harp.add(b + 1, chord(h)[2], 3, 40); harp.add(b + 1.5, chord(h)[3] + 12, 2.5, 34)
        if bar == 0 or (narr is not None and b < narr - .5): mel(fl, b + .25, DES_TUNE[0], 64, vib=True)
        elif final: fl.add(b, "A4", d - .5, 46); fl.vibrato(b, d - .5, 25); ney.add(b, "E4", d - .5, 40)
        elif bar % 2 == 1: fl.add(b + 1, ["C5", "E5", "D5"][bar % 3], 2.5, 44); fl.vibrato(b + 1, 2.5, 25)
        else: ney.add(b + .5, ["E4", "A4"][bar % 2], 3, 46)
    for t in np.cumsum(me.RNG.uniform(.7, 2.2, 40)):
        if t > n * 4: break
        bells.add(t, ["A6", "E7", "B6", "C7"][int(me.RNG.integers(0, 4))], .5, 30 + me.RNG.uniform(0, 12))
        if me.RNG.random() < .4: tri.add(t + .1, TRIANGLE, .4, 24)
    return s


# ----------------------------------------------------------------------------------------------- bush
def cue_bush(c):
    """Awe, not fear; no beat. Tremolo high strings and a bowed glass pad shimmer on D, swaying to Eb over the D
    pedal (Phrygian-dominant colour); soft choir; crystal 'glass harmonic' pings. God's call swells the choir;
    under his speech warm low strings, and horns hum the freedom figure in Phrygian dominant at 'bring my people
    out'. Moses' doubt thins it to a timid clarinet; the snake gets a quick comic scramble (pizz + xylophone +
    bassoon jab); God's comfort brings the warm strings back, and on 'I'll go' the horn plays the figure in D major
    for the first time, ending on a shimmering D major chord."""
    s = Score(c, 62, 4); n = s.bars; total = n * 4; E = end_beats(s)
    trem = P(s, "tremolo strings", TREM_STR, -8, .55, lp=7000)
    glass = P(s, "bowed glass", BOWED_PAD, -10, .6, lp=6000)
    choir = P(s, "choir", CHOIR, -9, .6, lp=5000)
    padp = P(s, "low strings", SLOW_STR, -5, .5, lp=3500)
    vc = P(s, "cello", CELLO, -6, .45, lp=3500)
    cb = P(s, "contrabass", CBASS, -9, .35, lp=900)
    hn = P(s, "horns", HORN, -6, .5, lp=3000)
    cl = P(s, "timid clarinet", CLARINET, -6, .4, lp=4000)
    cry = P(s, "crystal", CRYSTAL, -20, .7)
    harp = P(s, "harp", HARP, -9, .5)
    pz = P(s, "pizz (snake)", PIZZ, -4, .25); xy = P(s, "xylophone", XYLO, -8, .3); bsn = P(s, "bassoon", BASSOON, -5, .3)
    t_call = s.at(c.first("lines", who="god"))
    gods = sorted(t for t in (s.at(x) for x in c.all("lines", who="god")) if t is not None)
    mos = sorted(t for t in (s.at(x) for x in c.all("lines", who="moses")) if t is not None)
    t_speech = gods[1] if len(gods) > 1 else total * .25
    t_doubt = next((t for t in mos if t > t_speech + 2), total * .45)
    t_hand = next((t for t in gods if t > t_doubt), total * .6)
    t_snake = s.at(c.first("sfx", id="hiss")) or s.at(c.first("acting", who="moses", clip="jump_back")) or total * .7
    t_comfort = next((t for t in gods if t > t_snake), t_snake + 4)
    t_go = s.at(c.first("sfx", id="sparkle")) or (mos[-1] if mos else total - 4)
    lines = [(s.at(x), s.at(x) + s.beat(m)) for x, m in
             ((e["t"], e.get("maxSec", 4)) for e in c.tl["lines"] if s.at(e["t"]) is not None)]
    sec = lambda b: ("awe" if b < t_speech else "speech" if b < t_doubt else "doubt" if b < t_snake
                     else "snake" if b < t_comfort else "comfort" if b < t_go else "go")
    D_EB = ["D", "D", "Eb", "D"]
    for bar in range(n):
        b = bar * 4; final = bar == n - 1; d = 4 if not final else E - b; sc = sec(b)
        h = "D" if sc in ("go", "comfort") or final else D_EB[bar % 4] if sc in ("awe", "speech") else ["Gm", "Eb"][bar % 2]
        if sc == "snake": h = "Dm"
        top = {"D": ["A4", "D5", "F#5"], "Eb": ["G4", "Bb4", "Eb5"], "Gm": ["G4", "Bb4", "D5"], "Dm": ["A4", "D5", "F5"]}[h]
        if sc != "snake":
            tv = {"awe": 46, "speech": 40, "doubt": 32, "comfort": 44, "go": 50}[sc]
            trem.chord(b, top, d + .3, tv, strum=.05); trem.ramp(b, b + 2, 11, 80 if b else 40, 100)
            glass.chord(b, [note(top[0]) + 12, top[2]], d + .3, 40 if sc != "doubt" else 30)
            cb.add(b, "D2", d, 46); padp.chord(b, chord(h)[1:], d + .2, 38 if sc != "doubt" else 30)
        if sc in ("awe", "speech", "comfort", "go") and bar % 2 == 0:
            choir.chord(b, [chord(h)[1], chord(h)[3]], min(8, d + 4), 36 if sc != "go" else 44)
        if sc in ("speech", "comfort"): vc.add(b, chord(h)[0] - 12 if chord(h)[0] - 12 >= note("C2") else chord(h)[0], d, 50); vc.vibrato(b, d, 20)
        if sc in ("comfort", "go"): arp(harp, b, h, 4 if not final else 2, .5, 40, up=12)
        if sc in ("awe", "go") or (sc == "speech" and bar % 2):
            for _ in range(2): cry.add(b + me.RNG.uniform(0, 3.5), ["A6", "D7", "F#6", "E7"][int(me.RNG.integers(0, 4))], 2, 30)
    # God's call: choir swell
    if t_call is not None:
        choir.chord(t_call, ["D4", "A4", "D5", "F#5"], 7, 52, strum=.08); choir.ramp(t_call, t_call + 3, 11, 60, 120)
        harp.chord(t_call, ["D3", "A3", "D4", "F#4", "A4", "D5"], 5, 46, strum=.1)
    # 'bring my people out' (end of God's speech): horns hum the figure in Phrygian dominant
    sp_end = next((e for t, e in lines if abs(t - t_speech) < 1e-6), t_speech + 12)
    hb = max(t_speech + 2, min(sp_end - 4, t_doubt - 6))
    mel(hn, hb, [(p_, d * .75) for p_, d in pd(FIGURE)[:4]] + [("D4", 2)], 58, legato=.97, vib=True)
    # doubt: a timid clarinet wandering low, in the gaps
    for j, t in enumerate(np.arange(t_doubt + .5, t_hand - 1, 4.0)):
        mel(cl, t, [[("D4", 1), ("Eb4", .5), ("D4", .5), ("C4", 2)], [("Bb3", 1), ("C4", 1), ("D4", 2)]][j % 2], 52, vib=True)
    # the snake: comic scramble (one bar) right on the hiss
    ts = t_snake
    for j, p_ in enumerate(["D4", "Eb4", "F4", "Gb4", "G4", "Ab4", "A4", "Bb4"]): pz.add(ts + j * .125, p_, .1, 74)
    for j, p_ in enumerate(["D6", "C#6", "C6", "B5", "Bb5", "A5"]): xy.add(ts + 1 + j * .1, p_, .2, 66)
    bsn.add(ts + .02, "D2", .25, 84); bsn.add(ts + 1.8, "A2", .2, 70); bsn.add(ts + 2.1, "D2", .3, 74)
    trem.chord(ts + .1, ["Ab4", "D5", "F5"], 2.5, 52); trem.ramp(ts, ts + 2.5, 11, 110, 50)
    # 'I'll go': the figure in D major on the horn (first time in major), then the bright held chord
    tg = min(t_go, total - 6)
    mel(hn, tg, [(p_, d * .7) for p_, d in FIGURE[:4]], 70, legato=.97, vib=True)
    hn.add(tg + 2.8, "D5", E - tg - 2.8, 64); hn.vibrato(tg + 2.8, E - tg - 3, 25)
    for j, p_ in enumerate(["D4", "F#4", "A4", "D5", "F#5", "A5", "D6"]): harp.add(tg + 2.8 + j * .1, p_, 4, 50 - j)
    for j, p_ in enumerate(["D7", "A6", "F#6", "D6"]): cry.add(tg + 3 + j * .3, p_, 2.5, 40)
    return s


# ----------------------------------------------------------------------------------------------- palace
PHARAOH = [[("D3", .75), ("D3", .25), ("A3", 1), ("F#3", .75), ("D3", .25), ("A2", 1)],
           [("G3", .75), ("F#3", .25), ("E3", .5), ("F#3", .5), ("Bb3", 1), ("A3", 1)],      # the cheeky Bb
           [("D4", .75), ("C#4", .25), ("B3", .5), ("A3", .5), ("G3", .75), ("E3", .25), ("C#3", 1)],
           [("D3.", .5), ("A2.", .5), ("D3.", .5), (None, .5), ("D2", 1), (None, 1)]]
PHARAOH_HARM = [["D"], ["G", "D"], ["G", "A"], ["D"]]


def oompah(tuba, pah, b, harm, vel=1.0, bd=None):
    for q in range(4):
        h = harm[min(q * len(harm) // 4, len(harm) - 1)]; ps = chord(h)
        if q % 2 == 0: tuba.add(b + q, low(ps[0]) if q == 0 else low(ps[1]), .5, 84 * vel)
        else: pah.chord(b + q, [ps[1], ps[2], ps[3]], .35, 60 * vel, strum=.01)
        if bd is not None and q % 2 == 0: bd.add(b + q, BDRUM, .3, 74 * vel)


def cue_palace(c):
    """Pharaoh's palace, pompous and slightly silly. A trumpet fanfare that is a bit too grand (with a cymbal and a
    big drum), then under Moses' brave 'Let my people go!' only a snare roll and a low pedal, with a horn answering
    the freedom figure (Phrygian dominant) at the end of his line. On Pharaoh's belly laugh: his own swaggering tune
    (bassoon + tuba + trombone, dotted rhythms and one cheeky flat sixth) over an oompah, a bassoon 'ho-ho-ho', and a
    deflating trombone tumble on the last beat."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4; E = end_beats(s)
    tp = P(s, "trumpets", TRUMPET, -5, .38, lp=7000, human=.006)
    tb = P(s, "trombone", TROMBONE, -6, .35, lp=4000)
    tuba = P(s, "tuba", TUBA, -3, .3, lp=2500)
    bsn = P(s, "bassoon (pharaoh)", BASSOON, -1, .32, lp=4500, human=.008)
    hn = P(s, "horns", HORN, -6, .45, lp=3500)
    pah = P(s, "pah strings", PIZZ, -6, .25)
    padp = P(s, "strings", SLOW_STR, -10, .5, lp=4000)
    perc = P(s, "big drum + cymbal", DRUMS, -5, .3, human=.004)
    timp = P(s, "timpani", TIMPANI, -8, .3)
    moses = s.at(c.first("lines", who="moses")); laugh = s.at(c.first("lines", who="pharaoh"))
    laugh = laugh if laugh is not None else total * .5
    lb = max(1, int(laugh // 4)) if laugh % 4 < 1.5 else int(math.ceil(laugh / 4 - .4))
    lb = min(max(lb, 2), n - 1)
    # fanfare (bar 0), ends with a grand cymbal + drum
    fan = [("A4", .25), ("A4", .25), ("A4", .25), ("D5", .75), ("A4", .5), ("D5", .5), ("F#5", .5), ("A5", 1.0)]
    mel(tp, 0, fan, 96, legato=.85); mel(tp, .01, [(p_ if p_ == "A5" else p_, d) for p_, d in fan], 70, shift=-12, legato=.85)
    tb.chord(2, ["D3", "A3", "D4"], 2, 82); tuba.add(2, "D2", 2, 90)
    perc.add(0, BDRUM, .3, 96); perc.add(3, BDRUM, .3, 110); perc.add(3, CRASH, 2, 92)
    timp.add(0, "D2", 1, 90); roll(timp, 2, 3, "A2", 50, 90); timp.add(3, "D2", 1.5, 110)
    pend = moses if moses is not None else 4.0
    for bar in range(1, lb):                                                  # under Moses' line
        b = bar * 4; padp.chord(b, ["D3", "A3", "D4", "F#4"], 4.2, 46); tuba.add(b, "D2", 3.5, 58)
        roll(perc, b, b + 4, SNARE, 22, 34 if bar < lb - 1 else 50, step=.125, dur=.1)
    m_line = next((e for e in c.tl["lines"] if moses is not None and e["t"] == c.first("lines", who="moses")), None)
    mt = s.at(m_line["t"] + m_line.get("maxSec", 4) * .85) if m_line else None      # end of 'Let my people go!'
    hb = min(mt if mt is not None else lb * 4 - 3, lb * 4 - 3.2)
    if hb > pend + 1: mel(hn, hb, [(p_, d * .5) for p_, d in pd(FIGURE)[:4]] + [("D4", 1)], 66, vib=True)
    # Pharaoh's laugh + his tune
    for i, p_ in enumerate(["A3", "F#3", "D3"]): bsn.add(laugh + i * .5, p_, .3, 84)
    for bar in range(lb, n):
        b = bar * 4; k = min(bar - lb, 3) if bar < n - 1 else 3; final = bar == n - 1
        mel(bsn, b, PHARAOH[k], 82); mel(tb, b, PHARAOH[k], 62, shift=-12); mel(tuba, b, PHARAOH[k], 52, shift=-12)
        if not final:
            oompah(tuba, pah, b, PHARAOH_HARM[k], 1.0, perc)
            if k == 1: tp.add(b + 2, "Bb4", .9, 70); tp.add(b + 3, "A4", .9, 66)          # the cheeky flat sixth
        else:
            perc.add(b + 2, BDRUM, .3, 92); perc.add(b + 2, CRASH, .8, 60); tp.chord(b + 2, ["D4", "F#4", "A4"], .5, 80)
            for i, p_ in enumerate(["A3", "G#3", "G3", "F#3", "F3", "E3"]): tb.add(b + 3 + i * .12, p_, .14, 70 - i * 4)
    return s


# ----------------------------------------------------------------------------------------------- plagues
PLAG = [[("D4.", .5), ("D4.", .5), ("Eb4.", .5), ("D4.", .5), ("F4.", .5), ("Eb4.", .5), ("D4.", .5), ("C4.", .5)],
        [("D4.", .5), ("A3.", .5), ("Bb3.", .5), ("A3.", .5), ("G3.", .5), ("A3.", .5), ("Bb3.", .5), ("C4.", .5)]]


def cue_plagues(c):
    """Comic-tense D Phrygian: staccato pizzicato ostinato doubled by bassoon, wood-block 'frog hops', pizz bass.
    A quick sting on every plague, looked up from the timeline: the river (trombone + timpani + tremolo swell), the
    frogs (xylophone hop-up + wood-block plop), the flies (flute/clarinet chromatic swirl), the hail (glockenspiel and
    xylophone clinks tumbling down), the frog on Pharaoh's crown (bassoon boing + piccolo whoop). Pharaoh's panic gets
    a 16th scramble with trumpet squeals; the narrator's tease drops to a tiptoe; Pharaoh's sly 'changed my mind' gets
    a bassoon 'heh-heh' and a muted-trumpet 'nyah-nyah', and the cue ends on a sour Eb-D Phrygian cadence."""
    s = Score(c, 118, 4); n = s.bars; total = n * 4; E = end_beats(s)
    pz = P(s, "pizz ostinato", PIZZ, -2, .25, human=.006)
    bsn = P(s, "bassoon", BASSOON, -5, .28, human=.006)
    pzb = P(s, "pizz bass", PIZZ, -6, .22)
    wb = P(s, "wood blocks", DRUMS, -7, .18, human=.004)
    tb = P(s, "trombones", TROMBONE, -4, .35, lp=4000); timp = P(s, "timpani", TIMPANI, -6, .3)
    trem = P(s, "tremolo strings", TREM_STR, -8, .45, lp=6000)
    xy = P(s, "xylophone", XYLO, -6, .3); gl = P(s, "glockenspiel", GLOCK, -12, .4)
    fl = P(s, "flute", FLUTE, -6, .35); cl = P(s, "clarinet", CLARINET, -7, .35)
    pic = P(s, "piccolo", PICCOLO, -12, .35); tp = P(s, "trumpet squeals", TRUMPET, -10, .35, lp=7000)
    mtp = P(s, "muted trumpet", MUTED_TPT, -4, .35)
    at = lambda kind, **m: s.at(c.first(kind, **m))
    river = at("fx", id="river_red") or at("sfx", id="sting")
    frogs = at("fx", id="frogs") or at("sfx", id="croak")
    flies = at("sfx", id="buzz"); hail = at("sfx", id="hail"); crown = at("fx", id="frog_on_head")
    ph = sorted(t for t in (s.at(x) for x in c.all("lines", who="pharaoh")) if t is not None)
    panic = ph[0] if ph else None; sly = ph[-1] if len(ph) > 1 else None
    tease = at("lines", who="narrator") if False else None
    for t in sorted(s.at(x) for x in c.all("lines", who="narrator") if s.at(x) is not None):
        if panic is not None and t > panic: tease = t; break
    tada = total - 1
    for bar in range(n):
        b = bar * 4
        if b >= tada: break
        mode = ("panic" if panic is not None and panic - .5 <= b < (tease or total) else
                "tiptoe" if tease is not None and b >= tease - .5 else "busy")
        k = bar % 2
        if mode == "panic":
            for j in range(16):
                p_ = ["D4", "Eb4", "D4", "C4", "D4", "Eb4", "F4", "Eb4"][j % 8]
                pz.add(b + j * .25, p_, .12, 70 if j % 4 else 82)
            pzb.add(b, "D2", .3, 74); pzb.add(b + 2, "A1", .3, 66)
            trem.chord(b, ["D4", "Eb4"], 4.1, 44)
            if bar % 2 == 0: tp.add(b + 1.5, "Eb6", .25, 70); tp.add(b + 3.5, "D6", .25, 64)
        else:
            vel = 74 if mode == "busy" else 62
            mel(pz, b, PLAG[k], vel)
            if mode == "busy" and k == 0: mel(bsn, b, PLAG[k], 54, shift=-12)
            pzb.add(b, "D2", .4, 66); pzb.add(b + 2, "A1" if k == 0 else "Bb1", .4, 58)
            for q in range(4):
                if b + q + .5 < tada: wb.add(b + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 40 if mode == "busy" else 32)
    # stings
    if river is not None:
        # the `sting` sfx plays the brass hit itself; the music only answers with a shiver and a soft timpani
        timp.add(river + .55, "D2", 1.0, 70); trem.chord(river + .5, ["D5", "Eb5"], 2.5, 56); trem.ramp(river + .5, river + 3, 11, 120, 40)
    if frogs is not None:
        for j in range(3):
            t = frogs + j * 1.0
            for i, p_ in enumerate(["G4", "C5", "G5"]): xy.add(t + i * .06, p_, .2, 70)
            wb.add(t + .3, LO_WOOD, .2, 66)
    if flies is not None:
        sw = ["D5", "Eb5", "E5", "F5", "E5", "Eb5", "D5", "C#5", "D5", "Eb5", "E5", "F5", "F#5", "F5", "E5", "Eb5"]
        for i, p_ in enumerate(sw): fl.add(flies + i * .125, p_, .14, 54); cl.add(flies + .06 + i * .125, p_, .14, 50, shift=-12)
    if hail is not None:
        for i in range(14):
            t = hail + i * .14 + me.RNG.uniform(-.03, .03); p_ = note("C7") - int(i * 1.5) - int(me.RNG.integers(0, 3))
            (gl if i % 2 else xy).add(t, p_, .2, 70 - i * 2)
    if crown is not None:
        bsn.add(crown, "D2", .2, 90); bsn.add(crown + .25, "D3", .25, 84)
        for i, p_ in enumerate(["D6", "F6", "A6", "D7"]): pic.add(crown + .55 + i * .07, p_, .1, 70)
    if sly is not None and sly + 2 < tada:
        for i, p_ in enumerate(["A3.", "A3.", "F3."]): mel(bsn, sly + .3 + i * .5, [(p_, .5)], 76)
        for i, (p_, d) in enumerate([("A4", .5), ("F#4", .5), ("B4", .5), ("A4", .5)]): mtp.add(sly + 2 + i * .5, p_, d * .8, 72)
    # sour Phrygian cadence (Eb -> D) on the last beat
    pz.chord(tada - .5, ["Eb3", "G3", "Bb3"], .3, 76); pz.chord(tada, ["D3", "A3", "D4", "F#4"], .4, 84)
    xy.chord(tada, ["D5", "A5"], .5, 64); pzb.add(tada, "D2", .5, 76); bsn.add(tada, "D3", .5, 60)
    return s


# ----------------------------------------------------------------------------------------------- passover
def cue_passover(c):
    """Hushed night, safe and expectant. Harp arpeggios in D Phrygian dominant (D, Eb, D, Gm), a soft low pad and
    contrabass, rare celesta glints for the glowing doors; the lone ney plays the freedom theme slowly (bars 1-2 at
    half speed, Phrygian dominant). Miriam's bustling whisper brings a soft frame-drum heartbeat and eighth-note
    harp; Pharaoh's defeated 'Go...' gets a falling cello sigh. Ends on a held, open D major chord (the Phrygian-
    dominant tonic), which the exodus then takes up."""
    s = Score(c, 66, 4); n = s.bars; E = end_beats(s)
    harp = P(s, "harp", HARP, -3, .5, human=.008)
    padp = P(s, "pad", SLOW_STR, -6, .55, lp=2600)
    cb = P(s, "contrabass", CBASS, -11, .35, lp=900)
    ney = P(s, "ney", SHAKU, -2, .55, lp=5000, human=.01)
    fl = P(s, "flute breath", FLUTE, -14, .55, lp=4000)
    cel = P(s, "celesta", CELESTA, -18, .7)
    dr = P(s, "heartbeat", DRUMS, -12, .25, lp=1500)
    pz = P(s, "pizz", PIZZ, -11, .3)
    vc = P(s, "cello sigh", CELLO, -4, .45, lp=3500)
    mir_b = bar_of(s, c.first("lines", who="miriam"), n - 3); mir_b = min(max(mir_b, 2), n - 2)
    ph_b = bar_of(s, c.first("lines", who="pharaoh"), n - 1); ph_b = min(max(ph_b, mir_b + 1), n - 1)
    HARM = ["D", "Eb", "D", "Gm", "D", "Eb", "Cm", "D"]
    tune = theme([1, 2], True, 2.0)                                           # 16 beats
    mel(ney, .5, [x for x in tune if True], 60, legato=.98, vib=True); mel(fl, .5, tune, 36, legato=.98)
    for bar in range(n):
        b = bar * 4; final = bar == n - 1; d = 4 if not final else E - b
        h = "D" if final or bar >= ph_b + 1 else ("Gm" if bar == ph_b else HARM[bar % 8])
        ps = chord(h)
        if bar < mir_b or bar >= ph_b:
            arp(harp, b, h, 4 if not final else 2, .5, 46, up=12, ring=1.7)
        else:
            arp(harp, b, h, 4, .25, 40, up=12, ring=.9)
            groove(dr, b, "D..tD...D..tD...", .25, {"D": (LO_CONGA, 56), "t": (MUTE_CONGA, 34)})
            for q in range(8): pz.add(b + q * .5, ps[[0, 2, 1, 2][q % 4]], .2, 40)
        pad(padp, b, h, d + .05, 36, (50, 82)); cb.add(b, low(ps[0]), d, 44)
        if bar % 3 == 1 and not final: cel.add(b + 2.5, ["A6", "D7", "F#6"][bar % 3], 2, 32)
        if mir_b <= bar < ph_b and bar > 4: mel(ney, b, [(None, 2), ("A4", 1), ("D5", 1)], 50, vib=True)
    tb = ph_b * 4 + 1
    mel(vc, tb, [("A3", 1.5), ("G3", .5), ("F#3", 1), ("Eb3", 1), ("D3", 3)], 60, legato=.98, vib=True)
    bf = (n - 1) * 4
    padp.chord(bf, ["F#3", "A3", "D4", "F#4"], E - bf, 42); harp.chord(bf + 1, ["D3", "A3", "D4", "F#4", "A4"], E - bf - 1, 44, strum=.12)
    return s


# ----------------------------------------------------------------------------------------------- exodus
def cue_exodus(c):
    """Joyful walking march in D major: frame drums and darbuka, handclaps on 2 and 4, an oud ostinato (nylon +
    koto), pizz bass; the freedom theme on flute + qanun (bars 1, 2, 6, 7, 8), a little softer under the narrator;
    horns on the cadence."""
    s = Score(c, 114, 4); n = s.bars; E = end_beats(s)
    fl = P(s, "flute", FLUTE, -3, .35, human=.006)
    qk = P(s, "qanun (koto)", KOTO, -8, .3, human=.006)
    oud = P(s, "oud (nylon)", NYLON, -4, .28, human=.006)
    pz = P(s, "pizz bass", PIZZ, -4, .22)
    padp = P(s, "strings", SLOW_STR, -10, .48, lp=5000)
    hn = P(s, "horns", HORN, -9, .45, lp=3500)
    hand = P(s, "frame drum + darbuka", DRUMS, -5, .16, human=.004)
    claps = P(s, "claps", DRUMS, -6, .3, human=.009)
    narr = s.at(c.first("lines", who="narrator"))
    tb = [1, 2, 6, 7, 8]; seq = [None] * max(0, n - len(tb)) + tb[-n:]
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1
        harm = FREE_HARM[k] if k else ["D"]
        soft = narr is not None and b + 2 > narr
        if k: mel(fl, b, FREEDOM[k], 72 if soft else 86, vib=True, shift=12 if k in (1, 5) else 0); mel(qk, b, FREEDOM[k], 54, shift=0)
        for q in range(4):
            h = harm[min(q * len(harm) // 4, len(harm) - 1)]; ps = chord(h)
            if not final or q == 0:
                pz.add(b + q, low(ps[0] if q % 2 == 0 else ps[1]), .4, 80 if q == 0 else 64)
                for e in (0, .5): oud.add(b + q + e, ps[[0, 2, 1, 3][(q * 2 + int(e * 2)) % 4]], .4, 64 if e == 0 else 50)
        padp.chord(b, chord(harm[0])[1:], 4 if not final else E - b, 40)
        if k in (7, 8): hn.chord(b, [chord(harm[-1])[1], chord(harm[-1])[3]], 4 if not final else E - b, 50)
        if not final:
            groove(hand, b, "D.tkD.tkDktkD.tk", .25, {**DARB, "k": (HI_BONGO, 34)}, .9)
            for q in (1, 3):
                for _ in range(3): claps.add(b + q, CLAP, .3, 62)
            if bar == 0: hand.add(b, TAMB, .3, 50)
        else:
            hand.add(b, LO_CONGA, .5, 90); hand.add(b, TAMB, .4, 60)
            oud.chord(b, ["D3", "A3", "D4", "F#4"], E - b, 60, strum=.03)
    return s


# ----------------------------------------------------------------------------------------------- chase
def cue_chase(c):
    """Pharaoh changes his mind: his tune twisted into D minor, frantic, on bassoon + tuba + trombone over stamping
    taiko and snare (the tantrum); from the chariot a driving low-string and taiko gallop ostinato with horn stabs,
    the harmony climbing (Dm, Dm, Eb, E dim) under Miriam's fear. On Moses' 'Don't be afraid! Stand still' it all
    stops: sustained strings and a horn holding D, calm and strong, a soft timpani pedal: the sea cue starts there."""
    s = Score(c, 128, 4); n = s.bars; total = n * 4; E = end_beats(s)
    bsn = P(s, "bassoon", BASSOON, -2, .28, human=.006)
    tb = P(s, "trombones", TROMBONE, -5, .3, lp=4000)
    tuba = P(s, "tuba", TUBA, -4, .3, lp=2500)
    vc = P(s, "low strings 8ths", CELLO, -2, .3, lp=4000, human=.004)
    cb = P(s, "contrabass", CBASS, -6, .3, lp=1000)
    hn = P(s, "horns", HORN, -4, .45, lp=3500)
    trem = P(s, "tremolo strings", TREM_STR, -9, .45, lp=6000)
    padp = P(s, "calm strings", SLOW_STR, -4, .55, lp=4500)
    war = P(s, "taiko + toms + snare", DRUMS, -4, .25, human=.004)
    timp = P(s, "timpani", TIMPANI, -8, .3)
    ch_b = bar_of(s, c.first("sfx", id="chariot"), 3); ch_b = min(max(1, ch_b), n - 3)
    mo_t = s.at(c.first("lines", who="moses")); mo_b = bar_of(s, c.first("lines", who="moses"), n - 2)
    mo_b = min(max(mo_b, ch_b + 1), n - 1)
    minor = lambda ns: [(None if p_ is None else re.sub(r"F#(?=\d)", "F", re.sub(r"C#(?=\d)", "C", p_)), d) for p_, d in ns]
    GAL = ["Dm", "Dm", "Eb", "Ddim"]
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        if bar < ch_b:                                                         # tantrum
            k = bar % 4; ph = minor(PHARAOH[k])
            mel(bsn, b, ph, 84); mel(tuba, b, ph, 64, shift=-12); mel(tb, b, ph, 56, shift=-12)
            groove(war, b, "B.S.B.S.", .5, WAR, .9); war.add(b + 3.5, SNARE, .2, 60)
            for q in range(4): vc.add(b + q, "D3", .3, 70)
        elif bar < mo_b:                                                       # the chase
            j = bar - ch_b; h = GAL[j % 4]; ps = chord(h)
            for e in range(8): vc.add(b + e * .5, [ps[0], ps[0], ps[3] - 12, ps[0], ps[1] - 12 + 12, ps[0], ps[3] - 12, ps[0]][e], .32, 82 if e % 4 == 0 else 66)
            cb.add(b, low(ps[0]), 2, 70); cb.add(b + 2, low(ps[0]), 2, 64)
            groove(war, b, "B.tTb.tTB.tTbtTT", .25, WAR, .85 + .05 * j)
            hn.chord(b + 1.5, [ps[1], ps[3]], .4, 86); hn.chord(b + 3.5, [ps[1], ps[3]], .4, 80)
            trem.chord(b, [ps[2] + 12, ps[3] + 12], 4.1, 40 + 6 * j)
            if j % 2 == 1: mel(tb, b, minor(PHARAOH[0]), 66, shift=-12)
        else:                                                                  # 'stand still'
            d = 4 if not final else E - b
            padp.chord(b, ["D3", "A3", "D4", "F#4"] if bar > mo_b else ["D3", "A3", "D4", "G4"], d + .2, 46)
            padp.ramp(b, b + 2, 11, 70 if bar == mo_b else 96, 100)
            cb.add(b, "D2", d, 54); timp.add(b, "D2", 1.5, 50)
            if bar == mo_b: hn.add(b, "D4", 4, 62); hn.vibrato(b, 4, 20)
            elif bar == mo_b + 1: hn.add(b, "A4", 2, 60); hn.add(b + 2, "D5", d - 2, 62); hn.vibrato(b + 2, d - 2, 25)
            else: hn.add(b, "D5", d, 56)
    if mo_t is not None and mo_t < mo_b * 4:                                   # stop right at his first word
        war.add(mo_t - .02, CRASH, 1, 50)
    return s


# ----------------------------------------------------------------------------------------------- sea
def cue_sea(c):
    """The hero moment. Over a D pedal the sea music builds for ~15 s: wind, a soft timpani roll, low choir; when
    the parting starts a rising tremolo string run, harp glissando and cymbal swell; then a rising string ostinato
    under the narrator with the harmony climbing D - Eb - D - Gm - Bb - C - A and horns calling the figure in
    Phrygian dominant, a timpani crescendo into the moment Miriam sees the walls. There the freedom theme gets its
    full statement in D major (bars 1, 2, 5, 6, 7, 8): violins + flute + horns + trumpets on the head, choir 'ah',
    harp, timpani and frame-drum heartbeat. Pharaoh's charge breaks in with his minor tune over the gallop; the wheel
    pop is a xylophone boing + bassoon squeak; the walls fall on a tutti crash (timpani, cymbal, low brass, falling
    strings); relief in warm D major with the figure on the horn under the narrator; a tiny pizz + bassoon button on
    Pharaoh's sneeze."""
    s = Score(c, 86, 4); n = s.bars; total = n * 4; E = end_beats(s)
    vln = P(s, "violins", STRINGS, -3, .55, lp=7000)
    trem = P(s, "tremolo strings", TREM_STR, -6, .5, lp=7000)
    ost = P(s, "string ostinato", STRINGS, -7, .4, lp=6000, human=.004)
    vc = P(s, "cellos", CELLO, -4, .45, lp=4000)
    cb = P(s, "contrabass", CBASS, -6, .35, lp=1000)
    padp = P(s, "pad", SLOW_STR, -6, .55, lp=4500)
    choir = P(s, "choir", CHOIR, -7, .65, lp=5500)
    fl = P(s, "flute", FLUTE, -5, .5)
    hn = P(s, "horns", HORN, -4, .5, lp=3800)
    tp = P(s, "trumpets", TRUMPET, -9, .45, lp=6500)
    tb = P(s, "trombones", TROMBONE, -7, .4, lp=3500)
    tuba = P(s, "tuba", TUBA, -9, .35, lp=2000)
    bsn = P(s, "bassoon", BASSOON, -4, .3)
    harp = P(s, "harp", HARP, -6, .5, human=.006)
    timp = P(s, "timpani", TIMPANI, -6, .35)
    cym = P(s, "cymbals", DRUMS, -12, .5)
    dr = P(s, "drums", DRUMS, -8, .25, lp=3000, human=.004)
    xy = P(s, "xylophone", XYLO, -8, .3); pz = P(s, "pizz", PIZZ, -5, .3); pic = P(s, "piccolo", PICCOLO, -12, .35)
    at = lambda kind, **m: s.at(c.first(kind, **m))
    part0 = at("fx", id="sea_part") or at("sfx", id="sea_rush") or 3.0
    part_d = s.beat(next((e.get("dur", 4.5) for e in c.tl["fx"] if e["id"] == "sea_part"), 4.5))
    wow = at("acting", who="miriam", clip="wow") or at("lines", who="miriam") or total * .3
    wb = int(round(wow / 4)) if abs(wow / 4 - round(wow / 4)) < .3 else int(wow // 4)
    wb = min(max(wb, 3), n - 6)
    ride = at("acting", who="pharaoh", clip="ride") or at("lines", who="pharaoh") or total * .6
    wheel = at("sfx", id="wheel_pop"); close = at("fx", id="sea_close"); splash = at("sfx", id="splash")
    crash = splash if splash is not None else (close + .6 if close is not None else ride + 6)
    relief = at("lines", who="narrator") if False else None
    for t in sorted(s.at(x) for x in c.all("lines", who="narrator") if s.at(x) is not None):
        if t > crash: relief = t; break
    relief = relief if relief is not None else crash + 3
    sneeze = None
    ph = sorted(t for t in (s.at(x) for x in c.all("lines", who="pharaoh")) if t is not None)
    if len(ph) > 1: sneeze = ph[-1]
    # ---------------------------------------------------------------- build (0 .. wow)
    B0 = wb * 4
    cb.add(0, "D2", B0, 50); vc.add(0, "D3", B0, 44); cb.ramp(0, B0, 11, 60, 115); vc.ramp(0, B0, 11, 50, 110)
    roll(timp, 0, part0, "D2", 28, 50, step=.125)
    choir.chord(0, ["D3", "A3"], part0 + 1, 34); choir.ramp(0, part0 + 1, 11, 50, 100)
    # the parting: rising tremolo run, harp glissando, cymbal swell
    run = ["D4", "Eb4", "F#4", "G4", "A4", "Bb4", "C5", "D5", "Eb5", "F#5", "G5", "A5", "D6"]
    st = part_d / len(run)
    for j, p_ in enumerate(run): trem.add(part0 + j * st, p_, st * 1.6, 40 + 3 * j)
    for j, p_ in enumerate(["D3", "F#3", "A3", "D4", "Eb4", "F#4", "A4", "D5", "Eb5", "F#5", "A5", "D6"]): harp.add(part0 + j * .14, p_, 2, 46 + j)
    roll(cym, part0, part0 + part_d, RIDE, 14, 54, step=.0625, dur=.08)
    pe = part0 + part_d
    cym.add(pe, CRASH, 3, 62); timp.add(pe, "D2", 2, 96)
    tb.chord(pe, ["D3", "A3"], 2.5, 70); tuba.add(pe, "D2", 2.5, 70)
    # climbing ostinato under the narrator
    CLIMB = ["D", "Eb", "D", "Gm", "Bb", "C", "A", "A"]
    b = math.ceil(pe); i = 0
    while b < B0:
        span = min(2, B0 - b); h = CLIMB[min(i, len(CLIMB) - 1) if b < B0 - 4 else -1]; ps = chord(h)
        grow = (b - pe) / max(1, B0 - pe)
        for e in range(int(span * 2)):
            ost.add(b + e * .5, [ps[2], ps[3], ps[2] + 12 if ps[2] + 12 < note("A5") else ps[2], ps[3]][e % 4], .45, 50 + 30 * grow)
        padp.chord(b, ps[1:], span + .2, 40 + 18 * grow); choir.chord(b, [ps[1], ps[3]], span + .2, 34 + 20 * grow)
        cb.add(b, low(ps[0]), span, 54 + 16 * grow)
        if i in (1, 4): mel(hn, b, [(p_, d * .5) for p_, d in pd(FIGURE)[:4]], 60 + 12 * grow, vib=True)
        b += span; i += 1
    roll(timp, max(pe + 2, B0 - 4), B0, "A2", 40, 104)
    roll(cym, B0 - 2, B0, RIDE, 20, 70, step=.0625, dur=.08)
    tp.chord(B0 - 1, ["A4", "C#5", "E5"], 1, 80); tb.chord(B0 - 1, ["A2", "E3", "A3"], 1, 84)
    # ---------------------------------------------------------------- full statement (wow .. ride)
    tbars = [1, 2, 5, 6, 7, 8]
    avail = max(1, int((ride - B0) // 4) + 1); tbars = tbars[-min(len(tbars), avail):] if avail < 6 else tbars
    cym.add(B0, CRASH, 4, 84); timp.add(B0, "D2", 2, 116); dr.add(B0, BDRUM, .5, 100)
    for j, k in enumerate(tbars):
        bb = B0 + j * 4; notes = FREEDOM[k]; stop = ride if j == len(tbars) - 1 else bb + 4
        if k == 8: notes = [("D5", max(.5, min(4, ride - bb - .1)))]
        mel(vln, bb, notes, 92, legato=.98); mel(fl, bb, notes, 80, vib=True, shift=12 if k in (1, 5) else 0)
        mel(hn, bb, notes, 82, legato=.98, shift=-12)
        if k in (1, 5, 6): mel(tp, bb, notes, 76 if k != 6 else 70, legato=.95)
        for hi, h in enumerate(FREE_HARM[k]):
            hb = bb + hi * 4 / len(FREE_HARM[k]); d = min(4 / len(FREE_HARM[k]), stop - hb); ps = chord(h)
            if d <= 0: continue
            padp.chord(hb, ps[1:], d + .1, 62); choir.chord(hb, [ps[1] + 12, ps[2] + 12, ps[3] + 12], d + .1, 58)
            vc.add(hb, ps[0], d, 74); cb.add(hb, low(ps[0]), d, 74); tb.chord(hb, [ps[0], ps[1]], d, 56); tuba.add(hb, low(ps[0]), d, 60)
            arp(harp, hb, h, d, .5, 50)
        if bb + 4 <= ride: groove(dr, bb, "D...D.t.D...D.t.", .25, FRAME, 1.0)
        if k == 7:
            roll(timp, bb + 2, bb + 4, "A2", 50, 100); timp.add(bb + 4, "D2", 1.5, 110)
    # ---------------------------------------------------------------- Pharaoh's charge (ride .. crash)
    minor = lambda ns: [(None if p_ is None else re.sub(r"F#(?=\d)", "F", re.sub(r"C#(?=\d)", "C", p_)), d) for p_, d in ns]
    t = ride
    while t < crash - .5:
        for e in range(8):
            if t + e * .5 >= crash - .2: break
            vc.add(t + e * .5, ["D3", "D3", "F3", "D3", "Eb3", "D3", "C3", "D3"][e], .32, 84)
        groove(dr, t, "B.tTb.tTB.tTbtTT", .25, WAR, .85, until=crash - .2)
        t += 4
    mel(bsn, ride, minor(PHARAOH[0]), 84); mel(tuba, ride, minor(PHARAOH[0]), 70, shift=-12)
    trem.chord(ride, ["D4", "Eb4"], max(.5, crash - ride), 46); trem.ramp(ride, crash, 11, 60, 120)
    if wheel is not None and wheel < crash:
        bsn.add(wheel + .3, "D4", .15, 84); bsn.add(wheel + .5, "C#4", .15, 76); bsn.add(wheel + .7, "C4", .25, 70)
        for j, p_ in enumerate(["A4", "Bb4", "B4", "C5", "C#5", "D5", "Eb5", "E5"]):
            if wheel + 1 + j * .25 < crash: trem.add(wheel + 1 + j * .25, p_, .3, 56 + 3 * j)
    # the walls fall
    cym.add(crash, CRASH, 4, 110); cym.add(crash + .02, CRASH, 3, 80); timp.add(crash, "D2", 3, 127)
    dr.add(crash, BDRUM, .5, 120); dr.add(crash, TAIKO, .8, 120)
    tb.chord(crash, ["D2", "A2", "D3", "F3"], 2.5, 104); tuba.add(crash, "D1", 2.5, 104)
    for j, p_ in enumerate(["D6", "A5", "F5", "D5", "A4", "F4", "D4", "A3", "F3", "D3"]): vln.add(crash + j * .09, p_, .4, 96 - 3 * j)
    padp.chord(crash, ["D3", "A3", "D4", "F4"], max(1, relief - crash), 60); padp.ramp(crash, relief, 11, 120, 50)
    for j, p_ in enumerate(["D6", "A5", "F5", "D5", "A4", "F4", "D4", "A3", "D3"]): harp.add(crash + 1.5 + j * .1, p_, 1.5, 50 - 2 * j)
    # ---------------------------------------------------------------- relief (narrator) .. sneeze .. end
    endb = total
    RELIEF = ["D", "G", "D", "A", "D", "Bm", "G", "A"]
    rb = relief; i = 0
    stop_r = sneeze if sneeze is not None and sneeze > relief + 4 else endb - 2
    while rb < stop_r - .5:
        d = min(4, stop_r - rb); h = RELIEF[i % 8]; ps = chord(h)
        pad(padp, rb, h, d + .1, 50, (70, 100)); cb.add(rb, low(ps[0]), d, 54); arp(harp, rb, h, d, .5, 44)
        if i % 2 == 0: choir.chord(rb, [ps[1], ps[3]], min(8, stop_r - rb), 36)
        rb += d; i += 1
    mel(hn, relief + 2, [(p_, d * .8) for p_, d in FIGURE[:4]] + [("D4", 3)], 60, legato=.97, vib=True)
    mel(fl, relief + 2 + 3.2 + 4, [("F#5", 1), ("E5", 1), ("D5", 2)], 52, vib=True)
    if sneeze is not None and sneeze < endb - 1:
        pz.add(sneeze + .9, "D5", .2, 78); pic.add(sneeze + .95, "A6", .1, 50); bsn.add(sneeze + 1.1, "D2", .4, 70)
        dr.add(sneeze + 1.1, LO_WOOD, .2, 60)
    fb = max(stop_r, endb - 2)
    padp.chord(fb, ["D3", "A3", "D4", "F#4"], E - fb, 46); cb.add(fb, "D2", E - fb, 50)
    harp.chord(fb + .5, ["D3", "A3", "D4", "F#4", "A4", "D5"], E - fb - .5, 44, strum=.08)
    return s


# ----------------------------------------------------------------------------------------------- song (6/8, fixed)
# Miriam's chant. 6/8 counted in eighths (1 = one eighth). Four 2-bar phrases + the people's echo; each phrase has
# 5 strong syllable slots, which fits both 唱歌吧，向上帝唱歌 / 他大大得胜 / 把马和兵车 / 都抛在海里 and "Sing to the
# Lord, sing! / He has won the victory! / Horse and chariot / he threw into the sea!". Phrase 1 is the freedom figure.
SONG = [[("D4", 2), ("E4", 1), ("F#4", 2), ("A4", 1)], [("D5", 4), (None, 2)],                  # 1-2
        [("B4", 2), ("B4", 1), ("A4", 2), ("F#4", 1)], [("G4", 2), ("E4", 1), ("A4", 3)],         # 3-4
        [("F#4", 2), ("A4", 1), ("D5", 2), ("D5", 1)], [("F#5", 2), ("E5", 1), ("D5", 3)],        # 5-6
        [("B4", 2), ("A4", 1), ("G4", 2), ("E4", 1)], [("D4", 4), (None, 2)]]                     # 7-8
SONG_HARM = [["D"], ["D"], ["G"], ["Em", "A"], ["D"], ["Bm", "A"], ["G", "A"], ["D"]]
SONG_ECHO = [[("D4", 2), ("E4", 1), ("F#4", 2), ("A4", 1)], [("D5", 6)]]                         # people: "唱歌吧！"


def song_grid(span):
    bar = 6 * 60 / (SONG_DQ_BPM * 3)
    return bar, max(4, int(span / bar + 1e-6))


def cue_song(c):
    """Miriam's dance, 6/8 at a fixed dotted quarter = 112 (the voice role chants on this grid; cues.json and
    MUSIC.md publish the bar starts). One bar of darbuka + tambourine pickup, then her singable tune on ney-flute
    doubled by qanun (4 two-bar phrases, the first is the freedom figure), oud strums, pizz bass, claps on both
    dotted beats, tambourine jingles; the people's echo (bars 9-10) adds oohs and horns; the last bar cadences on D."""
    s = Score(c, SONG_DQ_BPM * 3, 6)
    barsec, nb = song_grid(c.span); s.bars = nb; s.bpm = SONG_DQ_BPM * 3      # fixed tempo, whole bars <= span
    n = s.bars; E = n * 6 + 1.5
    fl = P(s, "ney-flute tune", FLUTE, -3, .35, human=.005)
    qk = P(s, "qanun (koto)", KOTO, -8, .3, human=.005)
    oud = P(s, "oud strum", NYLON, -5, .28, human=.005)
    pz = P(s, "pizz bass", PIZZ, -4, .22)
    padp = P(s, "strings", SLOW_STR, -12, .48, lp=5000)
    oohs = P(s, "people oohs", OOHS, -9, .6, lp=5000)
    hn = P(s, "horns", HORN, -10, .45, lp=3500)
    dr = P(s, "darbuka", DRUMS, -4, .16, human=.003)
    tam = P(s, "tambourine", DRUMS, -8, .25, human=.004)
    claps = P(s, "claps", DRUMS, -7, .3, human=.008)
    plan = [None] + list(range(8)) + ["e0", "e1"]
    plan = (plan + ["e1"] * n)[:n] if n >= len(plan) else ([None] + list(range(n - 3)) + ["e0", "e1"])[:n]
    for bar, k in enumerate(plan):
        b = bar * 6; final = bar == n - 1
        if k is None: harm = ["D"]; notes = None
        elif isinstance(k, str):
            j = int(k[1]); harm = ["D"] if j == 1 else ["G", "A"]; notes = SONG_ECHO[j]
        else: harm = SONG_HARM[k]; notes = SONG[k]
        if notes:
            echo = isinstance(k, str)
            mel(fl, b, notes, 84 if not echo else 76, vib=True, legato=.9); mel(qk, b, notes, 58, shift=0, legato=.9)
            if echo:
                mel(oohs, b, notes, 66, legato=.95); hn.chord(b, [chord(harm[0])[1], chord(harm[0])[3]], 6 if not final else E - b, 54)
        for hi, h in enumerate(harm):
            ps = chord(h); hb = b + hi * 6 / len(harm); L = 6 / len(harm)
            pz.add(hb, low(ps[0]), .9, 82); pz.add(hb + (3 if L == 6 else 2), low(ps[1]) if L == 6 else low(ps[0]), .9, 64)
            for e in (0, 3) if L == 6 else (0,):
                oud.chord(hb + e, [ps[1], ps[2], ps[3]], .8, 64, strum=.025); oud.chord(hb + e + 2, [ps[2], ps[3]], .5, 48, strum=.02)
            padp.chord(hb, ps[1:], L + .1 if not (final and hi == len(harm) - 1) else E - hb, 34)
        if not final:
            groove(dr, b, "D.tT.tD.TT.k" if bar % 2 == 0 else "D.tT.tD.TTkk", .5, DARB, .95)
            for e in (0, 3): claps.add(b + e, CLAP, .3, 70); claps.add(b + e + .02, CLAP, .3, 54)
            groove(tam, b, "Ssssss", 1, {"S": (TAMB, 62), "s": (TAMB, 40)})
        else:
            dr.add(b, LO_CONGA, .8, 100); tam.add(b, TAMB, .5, 70); claps.add(b, CLAP, .3, 80)
            oud.chord(b, ["D3", "A3", "D4", "F#4"], E - b, 66, strum=.03)
    s.song_plan = plan
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """The freedom theme, warm and full, D major (bars 1, 2, 5, 6, 7, 8) and a held final chord. Starts intimate
    (cello + ney + harp + pad under Moses' 'God heard us'), then at the golden rays violins, flute and horns take the
    tune with choir, a soft frame-drum heartbeat and a timpani roll into the cadence; oud and harp ring on the held D
    major chord with celesta sparkle; then the loop bed."""
    s = Score(c, 84, 4); n = s.bars; E = end_beats(s)
    tb = [1, 2, 5, 6, 7, 8]; seq = (tb + [None] * n)[:n] if n >= 6 else tb[-n:]
    vc = P(s, "cello", CELLO, -2, .42, lp=4500, human=.01)
    ney = P(s, "ney", SHAKU, -9, .5, lp=5000)
    vln = P(s, "violins", STRINGS, -2, .55, lp=6500)
    fl = P(s, "flute", FLUTE, -4, .5)
    padp = P(s, "pad", SLOW_STR, -5, .5, lp=4500)
    hn = P(s, "horns", HORN, -8, .45, lp=3200)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1000)
    harp = P(s, "harp", HARP, -6, .45, human=.007)
    oud = P(s, "oud", NYLON, -10, .35)
    choir = P(s, "choir", CHOIR, -14, .6, lp=4500)
    timp = P(s, "timpani", TIMPANI, -11, .35)
    dr = P(s, "frame drum", DRUMS, -13, .2, lp=2500, human=.005)
    cel = P(s, "celesta", CELESTA, -11, .6)
    rays_b = bar_of(s, c.first("fx", id="golden_rays"), n // 2)
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1; full = bar >= rays_b
        harm = FREE_HARM[k] if k else ["D"]
        if k:
            notes = FREEDOM[k]
            if full:
                mel(vln, b, notes, 78, legato=.98); mel(fl, b, notes, 70, vib=True, shift=12 if k in (1, 5) else 0)
                mel(vc, b, notes, 54, legato=.98, shift=-12)
            else:
                mel(vc, b, notes, 74, legato=.98, vib=True, shift=-12); mel(ney, b, notes, 46, legato=.98, vib=True)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); last = final and i == len(harm) - 1
            d = E - hb if last else 4 / len(harm); ps = chord(h)
            pad(padp, hb, h, d + .05, 50 if not full else 60, (70, 115 if full else 100))
            cb.add(hb, low(ps[0]), d, 58)
            arp(harp, hb, h, min(d, 4 / len(harm)), .5, 50)
            if full: hn.chord(hb, [ps[1], ps[2], ps[3]], d, 48); choir.chord(hb, [ps[1] + 12, ps[3]], d, 40)
        if full and not final and k != 7: groove(dr, b, "D...D.t.", .5, FRAME, .8)
        if k == 7:
            roll(timp, b + 2, b + 4, "A2", 34, 68); timp.add(b + 4, "D2", 3, 76)
        if final:
            vln.chord(b, ["D5", "F#5", "A5", "D6"], E - b, 58, strum=.04); vln.ramp(b, E, 11, 110, 70)
            for i, p_ in enumerate(["D6", "F#6", "A6", "D7"]): cel.add(b + 1 + i * .25, p_, 3, 54 - i * 3)
            oud.chord(b + .5, ["D3", "A3", "D4", "F#4", "A4"], E - b, 54, strum=.05)
    return s


# =============================================================================================== loop section
VAMP = {"slavery": ("Dm", "work"), "desert": ("Am", "drone"), "bush": ("D", "shimmer"), "palace": ("D", "march"),
        "plagues": ("Dm", "tiptoe"), "passover": ("D", "bed"), "exodus": ("D", "pluck"), "chase": ("D", "pulse"),
        "sea": ("D", "bed"), "song": ("D", "dance68"), "finale": ("D", "bells")}


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
    if style in ("pluck", "dance68"): mk("oud", NYLON, -10, .3); mk("dr", DRUMS, -14, .2, lp=3000)
    if style == "dance68": mk("pz", PIZZ, -8, .22)
    if style == "tiptoe": mk("pz", PIZZ, -6, .25); mk("wb", DRUMS, -14, .18)
    if style == "bells": mk("cel", CELESTA, -16, .6)
    if style == "work": mk("dr", DRUMS, -10, .2, lp=2500); mk("ney", SHAKU, -16, .5, lp=4000)
    if style == "drone": mk("vc", CELLO, -10, .45, lp=2500); mk("bell", GLOCK, -26, .5)
    if style == "shimmer": mk("trem", TREM_STR, -12, .55, lp=6500); mk("cry", CRYSTAL, -22, .7)
    if style == "march": mk("tuba", TUBA, -10, .3, lp=2500); mk("pah", PIZZ, -10, .25); mk("sn", DRUMS, -16, .3)
    if style == "pulse": mk("timp", TIMPANI, -12, .35); mk("hn", HORN, -14, .5, lp=3000)
    for p_ in [padp, cb, harp] + list(ex.values()): p_.vamp = True
    ps = chord(chord_name)
    for r in range(reps):
        b = start_b + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 46 if style not in ("tiptoe", "work") else 36); padp.cc(b, 11, 92)
        cb.add(b, low(ps[0]), Lb + .2, 48)
        for bar in range(nb):
            bb = b + bar * bpb
            if style in ("bed", "bells", "pluck", "shimmer"):
                if bpb == 4:
                    for j in range(8): harp.add(bb + j * .5, ps[[0, 1, 2, 3, 2, 3, 2, 1][j]] + 12, 1.4, 44 if j else 50)
            if style == "pluck":
                for j, idx in enumerate([0, 1, 2, 1, 3, 1, 2, 1]): ex["oud"].add(bb + j * .5, ps[idx], .45, 52 if j % 4 == 0 else 40)
                groove(ex["dr"], bb, "D...D.t.", .5, FRAME, .6)
            if style == "dance68":
                ex["pz"].add(bb, low(ps[0]), .9, 64); ex["pz"].add(bb + 3, low(ps[1]), .9, 52)
                for e in (0, 3): ex["oud"].chord(bb + e, ps[1:], .8, 46, strum=.02)
                groove(ex["dr"], bb, "D.tT.tD.TT.k", .5, DARB, .6)
                groove(ex["dr"], bb, "Ssssss", 1, {"S": (TAMB, 40), "s": (TAMB, 26)})
            if style == "tiptoe":
                for q, pt in enumerate(["D3", "A3", "Eb3", "A3"]): ex["pz"].add(bb + q, pt, .2, 54)
                for q in range(4): ex["wb"].add(bb + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 30)
            if style == "work":
                ex["dr"].add(bb, LO_CONGA, .5, 70); ex["dr"].add(bb + 2, MUTE_CONGA, .5, 50); ex["dr"].add(bb, SIDE_STICK, .2, 54)
            if style == "drone" and bar == 0: ex["vc"].add(bb, "E3", Lb + .2, 40)
            if style == "shimmer": ex["trem"].chord(bb, [ps[1] + 12, ps[3] + 12], bpb + .2, 34)
            if style == "march":
                for q in range(4):
                    if q % 2 == 0: ex["tuba"].add(bb + q, low(ps[0]) if q == 0 else low(ps[1]), .5, 60)
                    else: ex["pah"].chord(bb + q, ps[1:], .3, 44)
                ex["sn"].add(bb, BDRUM, .3, 50)
            if style == "pulse": ex["timp"].add(bb, "D2", 1.5, 46)
        if style == "work" and r % 1 == 0: ex["ney"].add(b + .5, "A4", Lb - 1, 40)
        if style == "drone": ex["bell"].add(b + Lb * .37, "A6", .5, 30)
        if style == "shimmer": ex["cry"].add(b + Lb * .5, "A6", 2, 30)
        if style == "bells": ex["cel"].add(b + bpb, "A6", 2, 34)
        if style == "pulse": ex["hn"].add(b, "D4", Lb, 40)
    s.secs = start + reps * L + 2.5
    s.vamp = dict(start=start, secs=L, reps=reps, bars=nb, chord=chord_name, style=style)


def clean_tmp():
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith("music_exodus_"):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


MUSIC = {"slavery": cue_slavery, "desert": cue_desert, "bush": cue_bush, "palace": cue_palace, "plagues": cue_plagues,
         "passover": cue_passover, "exodus": cue_exodus, "chase": cue_chase, "sea": cue_sea, "song": cue_song,
         "finale": cue_finale}
KEYS = {"slavery": "D minor (PD figure)", "desert": "A minor", "bush": "D / D Phrygian dominant -> D major",
        "palace": "D major (b6)", "plagues": "D Phrygian", "passover": "D Phrygian dominant -> D",
        "exodus": "D major", "chase": "D minor -> D", "sea": "D PD -> D major -> D minor -> D major",
        "song": "D major", "finale": "D major"}
CUE_NOTES = {k: " ".join(f.__doc__.split()) for k, f in MUSIC.items()}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG
place, lp, hp, bp, fit, room = me.place, me.lp, me.hp, me.bp, me.fit, me.room


def env(n, a, tau, hold=0.0): return me.adsr(n, a, tau, hold)


def sfx_bricks(ctx):
    """The brick yard: a wet mud slap into a mould, three clay bricks set down on a stack ('tock'), two mallet taps,
    a gravelly scrape."""
    secs = 2.2; n = int(secs * SR); y = np.zeros(n)
    m = int(.25 * SR); tt = np.arange(m) / SR
    slap = me.lp(noise(m), 700) * np.exp(-tt / .05) * .9 + np.sin(2 * np.pi * np.cumsum(140 * np.exp(-tt / .03) + 70) / SR) * np.exp(-tt / .06) * .5
    slap += me.bp(noise(m), 1500, 5000) * np.exp(-tt / .012) * .25
    place(y, slap, .04)
    for i, at in enumerate((.5, .88, 1.24)):
        f0 = R().uniform(780, 980)
        b = me.partials(.35, f0, [1, 1.62, 2.55, 3.4], [1, .6, .35, .2], [.03, .022, .015, .01]) * .6
        b += me.bp(noise(len(b)), 500, 3000) * me.env_exp(len(b), .012) * .7
        b += np.sin(2 * np.pi * 95 * np.arange(len(b)) / SR) * me.env_exp(len(b), .04) * .5
        place(y, b * (1 - .1 * i), at)
        place(y, me.bp(noise(int(.12 * SR)), 2000, 7000) * me.env_exp(int(.12 * SR), .03) * .12, at + .02)
    for at in (1.6, 1.78):
        k = me.partials(.2, 620, [1, 2.3, 3.9], [1, .4, .2], [.04, .02, .01], strike=.3)
        place(y, k * .55, at)
    m = int(.35 * SR); place(y, me.bp(noise(m), 1800, 7000) * np.sin(np.pi * np.arange(m) / m) * .12, 1.9 - .1)
    return fit(room(y, "room", .15), secs, fade_out=.25)


def sfx_sigh_crowd(ctx):
    """The slaves' tired sigh: eight breathy voices (men and women) sighing 'haaah... oh' on a falling pitch, a few
    ms apart, in the open air."""
    secs = 2.4; n = int(secs * SR); y = np.zeros(n)
    for v in range(8):
        man = v % 3 != 2; scale = R().uniform(.92, 1.0) if man else R().uniform(1.12, 1.2)
        base = R().uniform(130, 170) if man else R().uniform(220, 270)
        d = R().uniform(1.3, 1.8); m = int(d * SR); tt = np.arange(m) / SR
        f0 = base * np.interp(tt, [0, .2 * d, d], [1.08, 1.0, .78])
        e = np.minimum(1, tt / .18) * np.where(tt > d * .5, np.maximum(0, (d - tt) / (d * .5)), 1.0) ** 1.5
        sv = me.voice(d, f0, [(0, "h"), (.2, "ah"), (.75, "o"), (1, "u")], scale, breath=R().uniform(.6, .9), jitter=.02,
                      vib=(5, .006), amp_env=e)
        place(y, sv / (np.std(sv) + 1e-9) * R().uniform(.5, 1.0), R().uniform(0, .25))
    y = me.lp(me.hp(y, 110), 5000)
    return fit(room(y, "room", .12), secs, fade_out=.4)


def sfx_sheep_bells(ctx):
    """A flock moving at dusk: three small clunky copper bells (inharmonic partials, a wooden clapper knock) ringing
    in uneven little clusters, one further away; very quiet air."""
    secs = 4.0; n = int(secs * SR); y = np.zeros(n)
    for f0, lvl, dist in ((1180, 1.0, 0), (1420, .7, 0), (930, .45, 1)):
        t = R().uniform(.02, .3)
        while t < secs - .8:
            for k in range(int(R().integers(1, 4))):
                b = me.partials(.9, f0 * R().uniform(.995, 1.005), [1, 1.59, 2.31, 3.07, 4.2], [1, .55, .35, .2, .1],
                                [.35, .2, .12, .08, .05], strike=.05)
                b += me.bp(noise(len(b)), 600, 2500) * me.env_exp(len(b), .006) * .25
                if dist: b = me.lp(b, 3000)
                place(y, b * lvl * R().uniform(.6, 1.0), t); t += R().uniform(.12, .22)
            t += R().uniform(.5, 1.1)
    y += me.lp(noise(n), 300) * .004
    return fit(room(y, "room", .2), secs, fade_out=.6)


def sfx_bush_whoosh(ctx):
    """The bush catches fire without burning: a soft airy whoosh rising, a warm roar that flickers, a few crackles,
    and a high glassy shimmer (D-A-F#) blooming over it: wonder, not danger."""
    secs = 2.8; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    cut = 250 + 2600 * np.clip(t / .6, 0, 1) ** 1.5
    wh = me.wah_filter(noise(n), cut, .5, 1.6) * np.exp(-((t - .55) / .35) ** 2) * .9
    roar = me.lp(noise(n), 900) * np.clip((t - .3) / .4, 0, 1) * np.exp(-np.maximum(0, t - 1.2) / .7)
    roar *= 1 + .35 * me.smooth_rand(n, 9)
    y += wh + roar * .5 + ru.straw_ticks(n, 26, .4, 2.2, .35, 1500, 6000)
    for i, p_ in enumerate(["D6", "A6", "F#7"]):
        f = 440 * 2 ** ((note(p_) - 69) / 12)
        g = np.sin(2 * np.pi * f * t + i) * np.clip((t - .45 - i * .08) / .5, 0, 1) * np.exp(-np.maximum(0, t - 1.3) / .6)
        y += g * .06 * (1 + .2 * np.sin(2 * np.pi * 5 * t))
    return fit(room(y, "hall", .3), secs, fade_out=.5)


def sfx_hiss(ctx):
    """The staff becomes a snake: two cartoon hisses (a soft 'hhh' into a bright 'sss'), the second with a playful
    rattle flutter."""
    secs = 1.7; n = int(secs * SR); y = np.zeros(n)
    for at, d, flut in ((.02, .55, 0), (.75, .7, 1)):
        m = int(d * SR); tt = np.arange(m) / SR
        h = me.bp(noise(m), 3500, 9500) * np.minimum(1, tt / .06) * np.where(tt > d - .2, (d - tt) / .2, 1.0)
        h += me.bp(noise(m), 1200, 3000) * np.exp(-tt / .08) * .4
        if flut: h *= 1 - .45 * (np.sin(2 * np.pi * 28 * tt) > 0)
        place(y, h * (.8 if not flut else 1.0), at)
    return fit(room(y, "room", .1), secs, fade_out=.2)


def sfx_sting(ctx):
    """The river turns red: a comic-dramatic 'dun-dun-DUNNN' on low trombones (D-F, then the sour D-Eb-A cluster),
    timpani on each hit, a tremolo-string shiver after it."""
    secs = 2.0; ev = []
    for t, d, ps, v in ((0, .14, ["D3", "F3"], 100), (.24, .14, ["D3", "F3"], 104), (.5, 1.1, ["D3", "Eb3", "A3"], 118)):
        for p_ in ps: ev.append((t, d, p_, v, TROMBONE, None))
        ev.append((t, d + .3, "D2", v, TIMPANI, None))
    ev.append((.52, 1.3, "A4", 70, TREM_STR, None)); ev.append((.52, 1.3, "Bb4", 66, TREM_STR, None))
    x = me.gm_notes(ev, secs)
    return fit(room(lp(x, 8000), "hall", .2), secs, fade_out=.4)


def sfx_croak(ctx):
    """A frog's 'rib-bit': a low, gritty pulse-train voice (creaky 25 Hz gating) through moving formants, two
    syllables, the second higher, with a hollow throat resonance."""
    secs = .9; n = int(secs * SR); y = np.zeros(n)
    for at, d, f, keys in ((.03, .2, 115, [(0, "o"), (.6, "i"), (1, "i")]), (.33, .17, 150, [(0, "i"), (.5, "e"), (1, "eh")])):
        m = int(d * SR); tt = np.arange(m) / SR
        f0 = f * (1 + .15 * np.interp(tt, [0, d * .3, d], [0, 1, .2]))
        src = me.glottal(f0, tilt=.9) * (1 - .7 * (np.sin(2 * np.pi * 25 * tt) < 0))
        v = me.formant_filter(src, keys, .9)
        v *= np.minimum(1, tt / .01) * np.where(tt > d - .04, (d - tt) / .04, 1.0)
        place(y, v / (np.max(np.abs(v)) + 1e-9), at)
    y = y + me.resonator(y, 520, 120) * .6
    return fit(room(y, "room", .12), secs, fade_out=.12)


def sfx_buzz(ctx):
    """Flies: five buzzing flies (raspy wingbeats ~190-260 Hz with fast flutter) swooping near and away."""
    secs = 3.0; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for k in range(5):
        f0 = R().uniform(190, 260) * (1 + .07 * me.smooth_rand(n, 7)) * (1 + .03 * np.sin(2 * np.pi * R().uniform(8, 14) * t))
        src = me.glottal(f0, tilt=.7)
        amp = np.clip(.55 + .45 * me.smooth_rand(n, 1.3), 0, 1) ** 2
        y += me.bp(src, 250, 5000) * amp * R().uniform(.4, 1.0)
    y *= np.minimum(1, t / .25) * np.minimum(1, (secs - t) / .5)
    return fit(room(y, "room", .08), secs, fade_out=.2)


def sfx_hail(ctx):
    """Hail: a rattling shower of hard little stones on stone and wood (clicks with tiny bounces), building in,
    dense, then thinning; a low patter of the ground under it."""
    secs = 3.0; n = int(secs * SR); y = np.zeros(n); t = np.arange(n) / SR
    dens = np.interp(t, [0, .35, 2.0, 3.0], [5, 70, 60, 4])
    at = .02
    while at < secs - .1:
        lvl = R().uniform(.3, 1.0); f = R().uniform(2200, 5200)
        for b_ in range(int(R().integers(1, 3)) + 1):
            m = int(.03 * SR)
            c = me.bp(noise(m), 1500, 9000) * me.env_exp(m, R().uniform(.002, .005))
            c += me.partials(.03, f, [1, 1.7], [1, .4], [.012, .006]) * .5
            place(y, c * lvl * (.45 ** b_), at + b_ * R().uniform(.05, .11))
        at += R().exponential(1 / np.interp(at, t[::441], dens[::441]))
    y += me.lp(noise(n), 500) * .05 * np.interp(t, [0, .4, 2.2, 3], [0, 1, 1, 0])
    return fit(room(y, "room", .12), secs, fade_out=.35)


def sfx_crickets_night(ctx):
    """Passover night (seamless 20 s loop): Ruth's five-cricket night synth with Exodus's own seed."""
    return ru.sfx_crickets_night(ctx)


def sfx_sparkle(ctx):
    """Moses says yes / the sea's far shore: Esther's shower of tiny bells (D major pentatonic), shared synth."""
    return me.sfx_sparkle()


def sfx_cheer(ctx):
    """'We're free!' / the song's end: Esther's crowd synth (own seed) plus a few rhythmic claps."""
    y = me.sfx_cheer(); n = len(y)
    for k in range(10):
        at = .6 + k * .52
        for _ in range(4):
            m = int(.05 * SR); fc = R().uniform(1000, 2200)
            place(y, me.bp(noise(m), fc * .6, fc * 1.8) * me.env_exp(m, .009) * .12, at + R().normal(0, .012))
    return y[:n]


def sfx_chariot(ctx):
    """Pharaoh's chariot sets off: a galloping horse (three-beat da-da-DUM hooves on hard ground), wooden wheels
    rumbling and clacking over stones, a harness jingle, coming closer."""
    secs = 3.2; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    rum = me.lp(noise(n), 220) * (1 + .4 * me.smooth_rand(n, 12)) * .6
    y += rum
    at = .05
    while at < secs - .1:
        m = int(.03 * SR); place(y, me.bp(noise(m), 700, 3200) * me.env_exp(m, .006) * R().uniform(.15, .45), at)
        at += R().uniform(.03, .09)
    cyc = .46; at = .1
    while at < secs - .2:
        for dt, v in ((0, .7), (.09, .8), (.2, 1.0)):
            m = int(.12 * SR); tt = np.arange(m) / SR
            hoof = np.sin(2 * np.pi * np.cumsum(140 * np.exp(-tt / .015) + 70) / SR) * np.exp(-tt / .03)
            hoof += me.bp(noise(m), 900, 3500) * np.exp(-tt / .008) * .6
            place(y, hoof * v, at + dt + R().normal(0, .005))
        at += cyc * R().uniform(.97, 1.03)
    for at in np.arange(.3, secs - .3, .46): place(y, ru.jingle(.12), at + .2)
    y *= np.interp(t, [0, 2.4, secs], [.35, 1.0, 1.0])
    return fit(room(y, "room", .1), secs, fade_out=.5)


def sfx_wind(ctx):
    """The great east wind (9.5 s): a roaring broadband gust that builds over 2 s, swells and sighs in slow gusts,
    with a hollow howl gliding in two narrow bands, then eases off."""
    secs = 9.5; n = int(secs * SR); t = np.arange(n) / SR
    base = me.lp(noise(n), 1400) + me.bp(noise(n), 200, 3000) * .5
    gust = .55 + .45 * me.smooth_rand(n, .6)
    howl = (me.wah_filter(noise(n), 520 + 180 * me.smooth_rand(n, .4), .93, 1.07)
            + me.wah_filter(noise(n), 830 + 220 * me.smooth_rand(n, .35), .94, 1.06) * .7)
    y = base * gust + howl * 2.2 * gust ** 2
    y *= np.interp(t, [0, 2.0, 7.5, secs], [0, 1, 1, .2])
    return fit(y, secs, fade_out=1.5)


def sfx_sea_rush(ctx):
    """The sea parts (5.5 s): an in-drawn whoosh, a huge rising roar of water lifting, a deep boom as the walls stand,
    spray hiss, then a steady churning that settles."""
    secs = 5.5; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    cut = 200 + 3000 * np.clip(t / .9, 0, 1) ** 1.3
    y += me.wah_filter(noise(n), cut, .5, 1.6) * np.exp(-((t - .7) / .45) ** 2) * .8
    roar = (me.lp(noise(n), 700) + me.bp(noise(n), 300, 2200) * .6) * (1 + .3 * me.smooth_rand(n, 5))
    y += roar * np.interp(t, [0, .5, 1.8, 3.2, secs], [0, .3, 1.0, .55, .3])
    boom = np.sin(2 * np.pi * np.cumsum(62 * np.exp(-np.maximum(0, t - 1.4) / .8) + 40) / SR) * me.env_exp(n, .9, 1.4) * .9
    y += boom * (t > 1.4)
    y += me.hp(noise(n), 3500) * np.interp(t, [0, 1.2, 2.0, secs], [0, .5, .3, .08]) * (1 + .5 * me.smooth_rand(n, 20))
    return fit(room(y, "hall", .2), secs, fade_out=1.0)


def sfx_wheel_pop(ctx):
    """Pharaoh's wheel comes off: a wooden 'pok!', Esther's spring boing, and the wheel clattering away, wobbling
    to a stop."""
    secs = 1.8; n = int(secs * SR); y = np.zeros(n)
    k = me.partials(.25, 680, [1, 2.4, 4.1], [1, .5, .25], [.05, .02, .01], strike=.6)
    place(y, k, .01)
    place(y, me.sfx_boing() * .5, .08)
    at, gap = .55, .06
    while at < 1.55:
        m = int(.03 * SR); place(y, me.partials(.03, R().uniform(500, 800), [1, 2.2], [1, .4], [.01, .006]) * .5
                                + me.bp(noise(m), 800, 3000) * me.env_exp(m, .005) * .3, at)
        at += gap; gap *= 1.12
    return fit(room(y, "room", .12), secs, fade_out=.2)


def sfx_splash(ctx):
    """The walls of water fall: a deep boom, a huge white crash of water, sloshing waves, then droplets raining
    down and settling."""
    secs = 3.4; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    y += np.sin(2 * np.pi * np.cumsum(70 * np.exp(-t / .25) + 38) / SR) * me.env_exp(n, .45) * 1.0
    y += me.lp(noise(n), 5000) * me.env_exp(n, .35) * 1.1
    y += me.bp(noise(n), 200, 1300) * (.5 + .5 * np.sin(2 * np.pi * 6.5 * t)) * me.env_exp(n, .9, .2) * .7
    at = .4
    while at < secs - .2:
        f = R().uniform(1400, 3800); m = int(.05 * SR); tt = np.arange(m) / SR
        d = np.sin(2 * np.pi * np.cumsum(f * (1 + .6 * tt / .05)) / SR) * np.exp(-tt / .015)
        place(y, d * R().uniform(.05, .2) * max(.2, 1 - at / secs), at)
        at += R().exponential(.03 + .05 * at / secs)
    return fit(room(y, "hall", .22), secs, fade_out=.6)


def sfx_drip(ctx):
    """Soggy Pharaoh: water dripping off him (five 'plip's at uneven times, one 'plop'), and a small soggy squelch."""
    secs = 2.6; n = int(secs * SR); y = np.zeros(n)
    for at, f0, lvl in ((.05, 950, 1.0), (.5, 1150, .7), (.82, 800, .85), (1.45, 1300, .6), (2.05, 1000, .7)):
        m = int(.08 * SR); tt = np.arange(m) / SR
        f = f0 * (1 + 1.0 * np.clip(tt / .025, 0, 1))
        d = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-tt / .03) + me.hp(noise(m), 4000) * me.env_exp(m, .002) * .2
        place(y, d * lvl, at)
    m = int(.12 * SR); tt = np.arange(m) / SR
    place(y, np.sin(2 * np.pi * np.cumsum(420 * (1 + .8 * np.clip(tt / .04, 0, 1))) / SR) * np.exp(-tt / .04) * .8, 1.15)
    m = int(.3 * SR); tt = np.arange(m) / SR
    sq = me.bp(noise(m), 300, 1600) * (np.sin(2 * np.pi * 14 * tt) > 0) * np.sin(np.pi * tt / .3) * .35
    place(y, sq, 1.7)
    return fit(room(y, "room", .1), secs, fade_out=.3)


SFX = {"bricks": sfx_bricks, "sigh_crowd": sfx_sigh_crowd, "sheep_bells": sfx_sheep_bells, "bush_whoosh": sfx_bush_whoosh,
       "hiss": sfx_hiss, "sparkle": sfx_sparkle, "sting": sfx_sting, "croak": sfx_croak, "buzz": sfx_buzz,
       "hail": sfx_hail, "crickets_night": sfx_crickets_night, "cheer": sfx_cheer, "chariot": sfx_chariot,
       "wind": sfx_wind, "sea_rush": sfx_sea_rush, "wheel_pop": sfx_wheel_pop, "splash": sfx_splash, "drip": sfx_drip}
LOOP_SECS = {"crickets_night": 20.0}
SFX_GAIN = {"bricks": -10, "sigh_crowd": -11, "sheep_bells": -15, "bush_whoosh": -9, "hiss": -10, "sparkle": -9,
            "sting": -8, "croak": -8, "buzz": -13, "hail": -11, "crickets_night": -18, "cheer": -7, "chariot": -9,
            "wind": -11, "sea_rush": -6, "wheel_pop": -5, "splash": -5, "drip": -10}
SFX_NOTES = {k: " ".join(f.__doc__.split()) for k, f in SFX.items()}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3), secs=round(end - c["t"] + XFADE, 3),
                        last=i + 1 == len(cues)))
    return out


def song_beat_grid(c, sc):
    """Bar starts of `song` (cue-relative and absolute), plus what plays in each bar, for the voice role."""
    barsec = sc.sec(6); rows = []
    for k in range(sc.bars + 4):
        p = sc.song_plan[k] if k < sc.bars else "loop"
        what = ("pickup (drums)" if p is None else "loop bed (dance)" if p == "loop" else
                f"people echo {int(p[1]) + 1}/2" if isinstance(p, str) else f"tune bar {p + 1}/8")
        rows.append(dict(bar=k + 1, sec=round(k * barsec, 4), t=round(c["t"] + k * barsec, 3), what=what))
    return dict(meter="6/8", dottedQuarterBpm=SONG_DQ_BPM, eighthBpm=SONG_DQ_BPM * 3, barSec=round(barsec, 6),
                beatSec=round(barsec / 2, 6), eighthSec=round(barsec / 6, 6), barSamples=int(round(barsec * SR)),
                composedBars=sc.bars, bars=rows,
                tune="bars 2-9: D4 E4 F#4 A4 | D5 . | B4 B4 A4 F#4 | G4 E4 A4 | F#4 A4 D5 D5 | F#5 E5 D5 | B4 A4 G4 E4 | D4 ; "
                     "bars 10-11 (people): D4 E4 F#4 A4 | D5")


def build_music(tl, only=None):
    spans = cue_spans(tl)
    names = [c["cue"] for c in spans]
    assert len(set(names)) == len(names), "an Exodus cue plays twice"
    missing = sorted(set(names) - set(MUSIC)); assert not missing, f"no composer for cue(s) {missing}"
    path_json = f"{MUSIC_DIR}/cues.json"
    old = {c["cue"]: c for c in json.load(open(path_json))["cues"]} if only and os.path.exists(path_json) else {}
    manifest = []
    for c in spans:
        if only and c["cue"] not in only and c["cue"] in old: manifest.append(old[c["cue"]]); continue
        me.seed("exodus/" + c["cue"]); ctx = Ctx(tl, c["cue"], c["t"], c["span"], c["secs"], c["last"])
        sc = MUSIC[c["cue"]](ctx)
        add_vamp(sc, *VAMP[c["cue"]]); vp = sc.vamp
        main, vamp = ru.render_split(sc)
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
        six = c["cue"] == "song"
        e = dict(cue=c["cue"], t=c["t"], span=c["span"], secs=secs, lastCue=c["last"], loop=False,
                 loopStart=round(ls / SR, 6), loopEnd=round(le / SR, 6), loopStartSample=ls, loopEndSample=le,
                 loopFromSec=round(vp["start"], 3), plainTailSec=round(secs - c["span"], 3), key=KEYS[c["cue"]],
                 meter="6/8" if six else "4/4", bars=sc.bars, bpm=round(sc.bpm / 3 if six else sc.bpm, 1),
                 loopBars=vp["bars"], loopChord=vp["chord"], lufs=round(m_span["lufs"], 1),
                 loopLufs=round(m_loop["lufs"], 1), truePeak=round(m["truePeak"], 1))
        if six: e["beatGrid"] = song_beat_grid(c, sc)
        manifest.append(e); clean_tmp()
        print(f"music {c['cue']:9s} t={c['t']:7.2f} span={c['span']:6.2f} file={secs:6.2f}s bars={sc.bars:2d} "
              f"bpm={e['bpm']:5.1f} span I={e['lufs']:6.1f} loop {e['loopStart']:.2f}-{e['loopEnd']:.2f}s "
              f"I={e['loopLufs']:6.1f} TP={e['truePeak']:5.1f} dBTP", flush=True)
    json.dump(dict(rule="Start each cue at its timeline t at full level and fade the previous cue out over 0.6 s from "
                        "that t. Each cue's composed music ends on its cadence at loopFromSec (= span, except `song`, "
                        "whose fixed 6/8 tempo ends on a whole bar); after it the cue continues into a quiet loop "
                        "section on its final chord. If the section is stretched (longer voice clips), either loop "
                        "[loopStart, loopEnd) seamlessly (seconds, sample-accurate) until the next cue, or just keep "
                        "playing: every file is at least span x 1.3 + 0.6 s (plainTailSec after the span) and fades "
                        "out over its last 2.5 s. The span sits at -20 LUFS, the loop section ~3 dB under it. Duck "
                        "music ~7 dB under voice lines. `song.beatGrid` gives its bar starts for the chant. Rerun "
                        "tools/story/music_exodus.py after the timeline is re-timed so the in-cue hits follow.",
                   crossfadeSec=XFADE, lufs=MUSIC_LUFS, stretchCovered=STRETCH, cues=manifest),
              open(path_json, "w"), indent=1, ensure_ascii=False)
    return manifest


def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]}); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in needed:
        me.seed("exodus/" + sid)
        t0 = min(s["t"] for s in tl["sfx"] if s["id"] == sid)
        x = me.hp(np.asarray(SFX[sid](dict(tl=tl, t=t0)), np.float64), 30)
        x = me.peak_normalize(x, SFX_PEAK_DB); path = f"{SFX_DIR}/{sid}.wav"; me.write_wav(path, x); m = me.measure(path)
        loop = sid in LOOP_SECS
        e = dict(id=sid, secs=round(len(x) / SR, 3), loop=loop, gainDb=SFX_GAIN[sid],
                 samplePeak=round(m["samplePeak"], 1), truePeak=round(m["truePeak"], 1),
                 lufs=None if m["lufs"] == float("-inf") else round(m["lufs"], 1))
        if loop: e.update(loopStart=0.0, loopEnd=e["secs"], stopAtCue=ru.loop_stop(tl, sid), fadeInSec=1.0, fadeOutSec=1.5)
        manifest.append(e); clean_tmp()
        print(f"sfx   {sid:14s} {e['secs']:6.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f}"
              + (f" loop, stop at cue {e['stopAtCue']}" if loop else ""), flush=True)
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play each one-shot at its timeline t with gainDb "
                        "(recommended mix level). Entries with loop: true are ambience beds: the whole file is a "
                        "seamless loop (loopStart 0, loopEnd = secs); start it at its t with a fadeInSec fade-in and "
                        "loop it until the music cue named in stopAtCue starts (fade out over fadeOutSec).",
                   peakDbfs=SFX_PEAK_DB, sfx=manifest), open(f"{SFX_DIR}/mix.json", "w"), indent=1, ensure_ascii=False)
    return manifest


def build_preview(tl):
    n = int((tl["duration"] + 1.0) * SR); mus = np.zeros(n); fx = np.zeros(n); vo = np.zeros(n)
    for c in cue_spans(tl):
        x = me.load_any(f"{MUSIC_DIR}/{c['cue']}.wav")
        k0 = int(c["span"] * SR); k = int((XFADE if not c["last"] else 0.9) * SR); seg = x[k0:k0 + k]
        x[k0:k0 + len(seg)] *= np.linspace(1, 0, len(seg)); x[k0 + k:] = 0
        place(mus, x, c["t"])
    for s in tl["sfx"]:
        y = me.load_any(f"{SFX_DIR}/{s['id']}.wav") * 10 ** (SFX_GAIN[s["id"]] / 20)
        if s["id"] in LOOP_SECS:
            stop = ru.loop_stop(tl, s["id"]); t1 = next((m["t"] for m in tl["music"] if m["cue"] == stop), tl["duration"])
            m_ = int((t1 - s["t"] + 1.5) * SR); y = np.tile(y, m_ // len(y) + 1)[:m_]
            y[:SR] *= np.linspace(0, 1, SR); k = int(1.5 * SR); y[-k:] *= np.linspace(1, 0, k)
        place(fx, y, s["t"])
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
              f"(p99.9 step {normal:.4f}) clipped={clip} min0.5sRMS={min(rms):6.1f} dB  >2k={hi:4.1f}%  <150={lo:4.1f}%")
    mix = json.load(open(f"{SFX_DIR}/mix.json"))["sfx"]
    for s in mix:
        sr, x = wavfile.read(f"{SFX_DIR}/{s['id']}.wav"); x = x.astype(np.float64) / 32768
        extra = ""
        if s["loop"]: extra = f" wrapStep={abs(x[-1] - x[0]):.4f} (p99.9 {np.percentile(np.abs(np.diff(x)), 99.9):.4f})"
        print(f"check sfx {s['id']:14s} peak={20 * np.log10(np.max(np.abs(x))):5.2f} dBFS TP={s['truePeak']:5.1f}{extra}")
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
            meter = "6/8, ♩. =" if c["meter"] == "6/8" else "4/4"
            plain = (c["secs"] - XFADE) / c["span"] - 1
            rows.append(f"| `{c['cue']}` | {c['t']:.2f} | {c['span']:.2f} | {c['secs']:.2f} | {c['loopStart']:.3f}–{c['loopEnd']:.3f} "
                        f"({c['loopBars']} bar{'s' if c['loopBars'] > 1 else ''} on {c['loopChord']}) | loop: any; plain: +{plain * 100:.0f} % "
                        f"| {c['key']} | {c['bars']} × {c['bpm']} ({meter}) | {c['lufs']:.1f} / {c['loopLufs']:.1f} | {c['truePeak']:.1f} |")
        rows += ["", "| Cue | What it does (from the composer function's docstring) |", "|---|---|"]
        rows += [f"| `{c['cue']}` | {CUE_NOTES[c['cue']]} |" for c in cues]
        swap("cues", "\n".join(rows) + "\n")
        song = next((c for c in cues if c["cue"] == "song" and "beatGrid" in c), None)
        if song:
            g = song["beatGrid"]
            r = [f"6/8, dotted quarter = {g['dottedQuarterBpm']:g} (eighth = {g['eighthBpm']:g}); one bar = {g['barSec']:.6f} s "
                 f"= {g['barSamples']} samples; one dotted beat = {g['beatSec']:.6f} s; one eighth = {g['eighthSec']:.6f} s. "
                 f"Composed bars: {g['composedBars']} (then the loop bed keeps the same grid). Bar 1 starts at the cue start.", "",
                 "| Bar | Cue-relative (s) | Timeline t (s) | What plays |", "|---|---|---|---|"]
            r += [f"| {b['bar']} | {b['sec']:.4f} | {b['t']:.3f} | {b['what']} |" for b in g["bars"]]
            swap("grid", "\n".join(r) + "\n")
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
    ap.add_argument("--check", action="store_true", help="only measure the written files")
    ap.add_argument("--png", default="", help="with --check: write a spectrogram of every cue to this path")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    tl = json.load(open(TIMELINE))
    if a.check: check(tl, a.png or None); sys.exit(0)
    tempfile.tempdir = tempfile.mkdtemp(prefix="music_exodus_")
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
