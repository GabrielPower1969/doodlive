#!/usr/bin/env python3
"""Original score and sound effects for "Daniel" (story pack #4; docs/daniel/CONTRACT.md section 7, docs/daniel/MUSIC.md).

Same machinery as Ruth (tools/story/music_ruth.py, the template), shared rather than forked: this script imports
tools/story/music_esther.py as a library (Score / Part / mel / groove / Ctx, the FluidSynth renderer, the synthetic
hall, loudness and file helpers, the synthesis primitives) and never changes it, so Esther's and Ruth's output is
untouched. Ruth's loop-section machinery (vamp, sample-identical loop tiles, the sustain fix) is copied here and
generalised (more vamp styles, a cue that plays twice, pitch-bend parts for the comic slides).

The score is built around one original motif, the **Daniel theme** (DANIEL_THEME below): a calm, rising five-note
prayer motif (E F# A B C) that grows into a 5-bar melody. It is heard on a duduk-like reed in E minor over the
Babylon opening, as a flute hint in G major when Daniel says his wisdom comes from God, on a solo flute in E minor and
then E major in the prayer, on the reed ("God is with me") in the den with an E major glimmer, **glowing in E major**
with choir and harp when the angel comes, on horns when Daniel answers the king at dawn, **triumphant** with the full
ensemble in the rescue, and in a warm full statement in the finale. The fanfare sfx is the theme's head on trumpets.

Every name and time comes from assets/daniel/timeline.json, read on every run: cue lengths follow the music spans,
and every in-cue hit is looked up by event (see docs/daniel/MUSIC.md "Timeline hooks"), so after the voices re-time
the timeline, just rerun this script. Every cue continues after its cadence into a quiet loop section on its final
chord (seamless, sample-exact loop points in cues.json) and runs at least 30 % past its span as a plain tail.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/daniel/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated (span), true peak <= -1 dBTP
  assets/daniel/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/daniel/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/daniel/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain, ambience loop hints
  assets/daniel/audio/preview_mix.mp3        rough full-length mix at timeline times (zh voice clips when present;
                                             otherwise the music is ducked over the estimated line spans)
  docs/daniel/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_daniel.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--tmp DIR]   (scratch dir, default /tmp/daniel_music; emptied after every cue and removed at exit)
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg (as music_esther.py)
"""
import argparse, atexit, json, math, os, re, shutil, sys, tempfile
import numpy as np
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import music_esther as me                                                  # noqa: E402  (shared library)
from music_esther import (Score, Ctx, mel, groove, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB, DUCK_DB, TPB,  # noqa: E402
                          HARP, KOTO, NYLON, CELESTA, GLOCK, XYLO, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                          CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, TIMPANI, TRUMPET, TROMBONE, TUBA, HORN, DRUMS,
                          BDRUM, TAMB, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA, HI_WOOD, LO_WOOD,
                          SHAKER, SNARE)

ROOT = me.ROOT
DA = f"{ROOT}/assets/daniel"
TIMELINE = f"{DA}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{DA}/audio/music", f"{DA}/audio/sfx", f"{DA}/audio/voice/zh"
PREVIEW = f"{DA}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/daniel/MUSIC.md"
STRETCH = 0.30                 # every cue survives its section being stretched by at least this much (re-timing)
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -3.0             # loop section loudness relative to the cue's composed span
TMP_PREFIX = "music_daniel_"

# extra GM programs (0-based)
VIOLA, ENGLISH_HORN, PAN_FLUTE = 41, 69, 75
CRASH_SOFT = 52                # GM Chinese cymbal (unused), kept out on purpose: no crashes in a kids' mix

CH = dict(me.CH)
CH.update({"Em": ["E3", "B3", "E4", "G4"], "E": ["E3", "B3", "E4", "G#4"], "E7": ["E3", "B3", "D4", "G#4"],
           "B": ["B2", "F#3", "B3", "D#4"], "B7": ["B2", "F#3", "A3", "D#4"], "Bsus": ["B2", "F#3", "B3", "E4"],
           "C#m": ["C#3", "G#3", "C#4", "E4"], "F#m": ["F#2", "C#3", "F#3", "A3"], "G7": ["G2", "D3", "F3", "B3"],
           "Dm": ["D3", "A3", "D4", "F4"], "F": ["F2", "C3", "F3", "A3"], "Am": ["A2", "E3", "A3", "C4"],
           "C": ["C3", "G3", "C4", "E4"], "D": ["D3", "A3", "D4", "F#4"], "G": ["G2", "D3", "G3", "B3"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def nm(m): return f"{NAMES[m % 12]}{m // 12 - 1}"


# =============================================================================================== the Daniel theme
# Original. Bar 1 is the five-note rising prayer motif (1-2-4-5-6). Written in E minor; tmode(..., True) gives the
# E major form (G->G#, C->C#, D->D#).
DANIEL_THEME = {
    1: [("E4", 1), ("F#4", .5), ("A4", .5), ("B4", 1), ("C5", 1)],          # the motif: calm, rising
    2: [("B4", 1.5), ("A4", .5), ("G4", 1), ("F#4", 1)],
    3: [("A4", 1), ("B4", .5), ("D5", .5), ("E5", 1), ("F#5", 1)],          # the motif again, a fourth higher
    4: [("E5", 1.5), ("D5", .5), ("B4", 1), ("A4", .5), ("F#4", .5)],
    5: [("E4", 4)],                                                          # home
}
TH_MIN = {1: ["Em", "C"], 2: ["G", "D"], 3: ["Am", "D"], 4: ["C", "B7"], 5: ["Em"]}
TH_MAJ = {1: ["E", "A"], 2: ["E", "B"], 3: ["A", "B"], 4: ["A", "B7"], 5: ["E"]}
HIJAZ = ["E", "F", "G#", "A", "B", "C", "D"]                                 # E Phrygian dominant, for colour


def tmode(notes, major):
    """E minor spelling -> E major spelling (keeps rests, staccato suffixes and grace notes)."""
    if not major: return list(notes)
    def conv(p):
        if p is None: return None
        p = re.sub(r"G(?=\d)", "G#", p); p = re.sub(r"C(?=\d)", "C#", p); return re.sub(r"D(?=\d)", "D#", p)
    return [(conv(p), d) for p, d in notes]


def theme(bars, major, scale=1.0):
    out = []
    for k in bars: out += [(p, d * scale) for p, d in tmode(DANIEL_THEME[k], major)]
    return out


def theme_seq(k, close=True):
    """Which theme bars fit k bars. close: end on bar 5 (home); else stop open (bars 1-4)."""
    if k <= 0: return []
    if not close: return [1, 2, 3, 4][:k] if k <= 4 else [1, 2, 3, 4] + [None] * (k - 4)
    return {1: [5], 2: [1, 5], 3: [1, 4, 5], 4: [1, 2, 4, 5]}.get(k, [None] * (k - 5) + [1, 2, 3, 4, 5])


def harm_at(part_fn, b0, harm, beats):
    for i, h in enumerate(harm): part_fn(b0 + i * beats / len(harm), h, beats / len(harm))


def hijaz_run(p, b0, lo, hi, step, vel, down=False, dur=1.0):
    """Harp / qanun run through the E hijaz scale from midi `lo` to `hi`."""
    pcs = {(note(n + "4") % 12) for n in HIJAZ}
    ps = [m for m in range(lo, hi + 1) if m % 12 in pcs]
    if down: ps = ps[::-1]
    for i, m in enumerate(ps): p.add(b0 + i * step, m, dur, vel + 10 * i / max(1, len(ps)) * (-1 if down else 1))
    return b0 + len(ps) * step


# =============================================================================================== small helpers
def end_beats(s): return s.bars * s.bpb + 1.0


def bar_of(s, abs_t, default):
    b = s.at(abs_t)
    return default if b is None else int(b // s.bpb)


def pad(part, b, name, dur, vel=50, swell=(70, 105), voices=(1, 2, 3), strum=.03, curve=.8):
    """Sustained chord with an expression swell; overlaps the next chord; only a cue's first chord swells from low."""
    ps = chord(name); part.chord(b, [ps[i] for i in voices], dur + .25, vel, strum=strum)
    v0 = swell[0] if b < 0.5 else max(82, swell[0])
    part.ramp(b, b + max(.5, dur * .8), 11, v0, max(v0, swell[1]), curve)


# Sustain fix (Ruth, measured 2026-11-14): the macOS DLS bank as FluidSynth loads it decays every instrument; winds,
# bowed strings and voices get an NRPN offset on SoundFont gen 37 (volEnvSustain -1440 cB) so long notes hold.
SUSTAIN = {STRINGS, SLOW_STR, TREM_STR, CELLO, VIOLA, CBASS, CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, ENGLISH_HORN,
           HORN, PAN_FLUTE, TRUMPET, TROMBONE, TUBA}


def sustain_ccs(p):
    d = 8192 - 1440
    p.cc(0, 99, 120); p.cc(0, 98, 37); p.cc(0, 6, d >> 7); p.cc(0, 38, d & 127)


class BPart(me.Part):
    """A Part that can also bend pitch (comic slides, sighs, slide-whistle). Bend range is set to 12 semitones."""

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw); self.bends = []

    def bend(self, beat, semis): self.bends.append((self.s.sec(max(0, beat)), semis))

    def glide(self, b0, b1, s0, s1, curve=1.0):
        k = max(2, int(self.s.sec(b1 - b0) / 0.02))
        for i in range(k + 1):
            u = i / k; self.bend(b0 + (b1 - b0) * u, s0 + (s1 - s0) * u ** curve)

    def midi(self):
        mid = super().midi()
        tr = mid.tracks[1]; ev = []; t = 0
        for i, m in enumerate(tr):
            t += m.time
            if m.is_meta and m.type == "end_of_track": continue
            ev.append((t, 1 + i, m))
        for k, (num, val) in enumerate(((101, 0), (100, 0), (6, 12), (38, 0), (101, 127), (100, 127))):
            ev.append((0, -10 + k, Message("control_change", channel=self.ch, control=num, value=val)))
        for sec, semis in self.bends:
            ev.append((self.s.tick(sec), 0, Message("pitchwheel", channel=self.ch,
                                                     pitch=int(np.clip(semis / 12 * 8191, -8192, 8191)))))
        tr2 = MidiTrack(); last = 0
        for tick, _, m in sorted(ev, key=lambda e: (e[0], e[1])):
            tr2.append(m.copy(time=tick - last)); last = tick
        tr2.append(MetaMessage("end_of_track", time=0)); mid.tracks[1] = tr2
        return mid


def P(s, name, program, *a, bend=False, **kw):
    if bend:
        p = BPart(s, name, program, *a, **kw); s.parts.append(p)
    else:
        p = s.part(name, program, *a, **kw)
    if program in SUSTAIN: sustain_ccs(p)
    return p


FRAME = {"D": (LO_CONGA, 84), "t": (MUTE_CONGA, 52), "k": (OPEN_CONGA, 34), "s": (TAMB, 26)}
DARB = {"D": (LO_CONGA, 92), "T": (HI_BONGO, 80), "t": (LO_BONGO, 60), "k": (HI_BONGO, 40)}


def oud_riff(oud, b, harm, vel=1.0, beats=4):
    """Eighth-note oud ostinato over a bar, following the bar's chord list."""
    for i in range(int(beats * 2)):
        h = harm[min(int(i * len(harm) / (beats * 2)), len(harm) - 1)]; ps = chord(h)
        oud.add(b + i * .5, ps[[0, 1, 2, 1, 3, 1, 2, 1][i % 8]], .45, (76 if i % 4 == 0 else 56) * vel)


def harp_arp(harp, b, name, beats, vel=48, step=.5, up=12):
    ps = chord(name)
    for j in range(int(beats / step)):
        harp.add(b + j * step, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + up, 1.4, vel + (8 if j == 0 else 0))


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- babylon
def cue_babylon(c):
    """Grand opening, E minor with a hijaz colour. A frame-drum roll, a low brass E-F-E swell and a harp run up the
    E hijaz scale open the city; on the downbeat timpani, horns and strings arrive and the duduk-like reed (English
    horn + a breath of clarinet) sings the Daniel theme (bars 1, 2, 4, 5) over an oud ostinato and a stately
    frame-drum pulse; a qanun run answers half way; the cadence lands on E with a harp roll."""
    s = Score(c, 74, 4); n = s.bars; E = end_beats(s)
    reed = P(s, "reed (eng horn)", ENGLISH_HORN, -2, .42, lp=4200, human=.012)
    reed2 = P(s, "reed breath (clar)", CLARINET, -14, .4, lp=3000, human=.012)
    brass = P(s, "low brass", TROMBONE, -10, .45, lp=1600)
    hn = P(s, "horns", HORN, -9, .45, lp=3000)
    padp = P(s, "strings", SLOW_STR, -6, .5, lp=4000)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1200)
    harp = P(s, "harp", HARP, -6, .45, human=.006)
    oud = P(s, "oud (nylon)", NYLON, -9, .3, human=.007)
    qk = P(s, "qanun (koto)", KOTO, -11, .3, human=.006)
    dr = P(s, "frame drum", DRUMS, -6, .22, lp=3200, human=.005)
    timp = P(s, "timpani", TIMPANI, -9, .35)
    # bar 0: drum roll, low brass E-F-E, harp hijaz run, timpani roll into the downbeat
    for i in range(28): dr.add(i * .125 + .5, LO_CONGA if i % 2 == 0 else MUTE_CONGA, .1, 30 + 50 * i / 28)
    brass.add(0, "E2", 2, 60); brass.add(2, "F2", 1, 66); brass.add(3, "E2", 1.1, 70); brass.ramp(0, 4, 11, 50, 110)
    brass.add(0, "B2", 4.1, 52)
    hijaz_run(harp, .25, note("E3"), note("E6"), 3.6 / 22, 44)
    for i in range(16): timp.add(2 + i * .125, "E2", .12, 30 + 40 * i / 16)
    seq = theme_seq(n - 1)
    for j, k in enumerate(seq):
        bar = j + 1; b = bar * 4; final = bar == n - 1
        harm = TH_MIN[k] if k else ["Em"]
        if k: mel(reed, b, theme([k], False), 76, legato=.97, vib=True); mel(reed2, b, theme([k], False), 50, legato=.97)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); d = (E - hb) if final and i == len(harm) - 1 else 4 / len(harm); ps = chord(h)
            pad(padp, hb, h, d + .05, 50, (70, 104)); cb.add(hb, low(ps[0]), d, 58)
        if not final:
            oud_riff(oud, b, harm, .85)
            groove(dr, b, "D..tD.tk", .5, FRAME, .85)
        if bar == 1:
            timp.add(b, "E2", 2, 92); hn.chord(b, ["E3", "B3", "E4"], 4, 62); hn.ramp(b, b + 3, 11, 110, 70)
            dr.add(b, LO_CONGA, 1, 100)
        if bar == 2 and n > 4: hijaz_run(qk, b + 2.5, note("E5"), note("E6"), .125, 46, down=True, dur=.6)
        if final:
            ps = chord("Em"); hn.chord(b, ["E3", "B3", "G4"], E - b, 52); hn.ramp(b, b + 2, 11, 70, 100)
            harp.chord(b, ["E2", "B2", "E3", "G3", "B3", "E4", "G4", "B4"], E - b, 54, strum=.08)
            timp.add(b, "E2", 2, 76); oud.chord(b, ["E3", "B3", "E4"], 3, 60, strum=.04); cb.add(b, "E2", E - b, 60)
    return s


# ----------------------------------------------------------------------------------------------- king_friend (3/4)
K_TUNE = [[("D5", 1), ("B4", .5), ("C5", .5), ("D5", 1)], [("G5", 2), ("F#5", 1)],
          [("E5", 1), ("C5", .5), ("D5", .5), ("E5", 1)], [("D5", 2), (None, 1)],
          [("B4", 1), ("D5", .5), ("C5", .5), ("B4", 1)], [("A4", 1), ("B4", .5), ("A4", .5), ("G4", 1)],
          [("A4", 1), ("F#4", 1), ("A4", 1)], [("G4", 2), (None, 1)]]
K_HARM = ["G", "Em", "C", "G", "G", "D", "D", "G"]


def cue_king_friend(c):
    """The king's good friend: G major, stately 3/4 with a cheerful lilt. Violins sing a warm tune (original) over
    pizz bass on 1, viola off-beat chords on 2 and 3 and a light frame drum; an oud plucks colour. When Daniel
    answers ("my wisdom comes from God") the tune gives way to harp and soft strings and the flute plays the Daniel
    theme's opening in G major (bars 1, 2, 5), ending on G."""
    s = Score(c, 104, 3); n = s.bars; E = end_beats(s)
    vln = P(s, "violins tune", STRINGS, -3, .5, lp=6000, human=.008)
    va = P(s, "violas lilt", VIOLA, -9, .45, lp=4000)
    vc = P(s, "cello", CELLO, -9, .42, lp=3500)
    pz = P(s, "pizz bass", PIZZ, -5, .25)
    harp = P(s, "harp", HARP, -8, .45, human=.007)
    oud = P(s, "oud", NYLON, -12, .3, human=.007)
    fl = P(s, "flute", FLUTE, -4, .48, human=.008)
    padp = P(s, "strings pad", SLOW_STR, -9, .5, lp=4000)
    dr = P(s, "frame drum", DRUMS, -14, .2, lp=3000, human=.005)
    dan_t = c.first("lines", who="daniel"); dan_b = bar_of(s, dan_t, n)
    dan_b = int(np.clip(dan_b, 2, n - 1))
    seq = me.fill_phrase(dan_b, 8, 2) if dan_b > 0 else []
    for bar in range(dan_b):
        b = bar * 3; k = seq[bar]
        h = K_HARM[k] if k is not None else "G"; ps = chord(h)
        if k is not None: mel(vln, b, K_TUNE[k], 74 if k % 4 != 3 else 66, legato=.95, vib=True)
        pz.add(b, low(ps[0]), .6, 70)
        va.chord(b + 1, [ps[1] + 12, ps[3]], .55, 50); va.chord(b + 2, [ps[1] + 12, ps[3]], .55, 44)
        if bar % 2 == 0: oud.add(b + 1.5, ps[2], .4, 52); oud.add(b + 2.5, ps[3], .4, 46)
        vc.add(b, low(ps[0]) + 12, 3, 46)
        groove(dr, b, "D.t.k.", .5, FRAME, .75)
    # Daniel's answer: the theme in G major on flute (bars 1, 2 then home), harp + pad underneath
    b0 = dan_b * 3
    mel(fl, b0, theme([1, 2], True), 66, vib=True, shift=3)
    fl.add(b0 + 8, "G4", max(1, E - b0 - 8.5), 58); fl.vibrato(b0 + 8, max(1, E - b0 - 8.5), 30)
    for bt, h, d in ((0, "G", 2), (2, "C", 2), (4, "G", 2), (6, "D", 2), (8, "G", max(1, E - b0 - 8))):
        if b0 + bt >= E - .5: break
        pad(padp, b0 + bt, h, d, 48, (70, 100)); pz.add(b0 + bt, low(chord(h)[0]), .6, 58)
        harp_arp(harp, b0 + bt, h, min(d, 3), 46)
    harp.chord(E - 3, ["G3", "D4", "G4", "B4", "D5"], 3, 44, strum=.08)
    return s


# ----------------------------------------------------------------------------------------------- scheme
SCHEME = [[("E3.", .5), (None, .5), ("F3.", .5), ("E3.", .5), (None, .5), ("C4^B3", 1), (None, .5)],
          [("A3.", .5), ("G#3.", .5), ("A3.", .5), (None, .5), ("C4.", .5), ("B3.", .5), ("G#3.", .5), (None, .5)],
          [("E3.", .5), (None, .5), ("F3.", .5), ("E3.", .5), (None, .5), ("E4^D4", 1), (None, .5)],
          [("C4.", .5), ("B3.", .5), ("A3.", .5), ("G#3.", .5), ("F3", 1), ("E3.", .5), (None, .5)]]


def cue_scheme(c):
    """Comic-sneaky, E minor with a hijaz half-step (E-F). A sulky bassoon tune (original, staccato, grace-note
    'harrumphs') doubled by pizzicato, wood-block tiptoes on the off-beats, pizz bass. A grumpy trombone 'pfff'
    slide when the official steams. At the idea: everything stops, a slide-whistle flute zips up and a xylophone
    pings the light bulb; then the tune comes back sly on a low clarinet with a bassoon 'heh-heh-heh'. Ends on a
    'dun-DUN!' (pizz, bassoon, contrabass, timpani)."""
    s = Score(c, 118, 4); n = s.bars; total = n * 4; E = end_beats(s)
    bsn = P(s, "bassoon", BASSOON, -3, .25, human=.006)
    pz = P(s, "pizz tune", PIZZ, -6, .25, human=.006)
    pzb = P(s, "pizz bass", PIZZ, -8, .22)
    wb = P(s, "wood blocks", DRUMS, -9, .18, human=.004)
    cl = P(s, "clarinet sly", CLARINET, -5, .3)
    xy = P(s, "xylophone", XYLO, -8, .3)
    tbn = P(s, "trombone pfff", TROMBONE, -8, .3, lp=2500, bend=True)
    fl = P(s, "slide whistle (flute)", FLUTE, -9, .35, bend=True)
    timp = P(s, "timpani", TIMPANI, -5, .3)
    cb = P(s, "contrabass", CBASS, -5, .25, lp=1500)
    idea = s.at(c.first("sfx", id="idea_ding")); steam = s.at(c.first("fx", id="steam"))
    lines = sorted(c.all("lines", who="officer"))
    dun = total - 3                                       # "dun" on beat 2 of the last bar, "DUN!" on beat 3
    stop = idea - .5 if idea is not None and idea < dun - 4 else dun
    # --- sulky tune until the idea
    bar = 0
    while bar * 4 < stop - .01:
        b = bar * 4
        ph = [(p, d) for p, d in SCHEME[bar % 4]]
        acc, cut = 0, []
        for p, d in ph:
            if b + acc + d > stop + 1e-6: break
            cut.append((p, d)); acc += d
        mel(bsn, b, cut, 78 if bar % 2 == 0 else 72); mel(pz, b, cut, 66, shift=12)
        for q in range(4):
            if q in (0, 2) and b + q < stop: pzb.add(b + q, "E2" if q == 0 else "B1", .3, 62 if q == 0 else 50)
            if b + q + .5 < stop: wb.add(b + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 40)
        bar += 1
    if steam is not None and steam + 2 < stop:            # grumpy 'pfff'
        tbn.add(steam, "A2", 1.2, 74); tbn.bend(steam - .01, 0); tbn.glide(steam + .3, steam + 1.2, 0, -4, 1.5)
        tbn.bend(steam + 1.3, 0)
    # --- the idea: stop, slide whistle up, light-bulb pings
    if idea is not None and idea < dun - 4:
        fl.bend(idea - .02, -12); fl.add(idea, "E6", 1.1, 70); fl.glide(idea, idea + 1.0, -12, 0, .7)
        for i, p in enumerate(["E5", "G#5", "B5", "E6"]): xy.add(idea + 1.0 + i * .125, p, .4, 58 + 4 * i)
        b1 = math.ceil(idea + 2)
        # sly variation: low clarinet legato-ish, pizz tiptoes, bassoon chuckle
        bar2 = 0
        while b1 + bar2 * 4 < dun - .5:
            b = b1 + bar2 * 4; ph = SCHEME[(bar2 + 2) % 4]
            acc, cut = 0, []
            for p, d in ph:
                if b + acc + d > dun - .5: break
                cut.append((p.rstrip(".") if p else None, d)); acc += d
            mel(cl, b, cut, 64, legato=.6, shift=12)
            for q in range(4):
                if b + q + .5 < dun - .5: wb.add(b + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 32)
                if q in (0, 2) and b + q < dun - .5: pzb.add(b + q, "E2" if q == 0 else "B1", .3, 54)
            bar2 += 1
        heh_line = next((t for t in lines if t > c.t + (idea - 1) * 60 / s.bpm), None)
        if heh_line is not None:
            e = next((x for x in c.tl["lines"] if abs(x["t"] - heh_line) < 1e-6), {})
            heh = s.at(heh_line + .45 * e.get("maxSec", 5) * .85)
            if heh is not None and heh + 1.5 < dun:
                for i, p in enumerate(["B3.", "B3.", "G#3."]): mel(bsn, heh + i * .5, [(p, .5)], 72)
    # --- dun-DUN!
    for p_, pitch, v in ((pz, "B3", 84), (bsn, "B2", 82), (cb, "B2", 70)): p_.add(dun, pitch, .35, v)
    for p_, pitch, v in ((pz, "E3", 96), (bsn, "E2", 92), (cb, "E2", 84), (pzb, "E2", 90)): p_.add(dun + 1, pitch, .9, v)
    timp.add(dun, "B2", .4, 70); timp.add(dun + 1, "E2", 1.5, 100)
    return s


# ----------------------------------------------------------------------------------------------- decree
FLATTER = [[("E5^F5", 1), ("D5", .5), ("C5", .5), ("G4", 1.5), ("A4", .5)],
           [("Bb4", .5), ("A4", .5), ("G#4", .5), ("A4", .5), ("C5", 2)],
           [("F5^G5", 1), ("E5", .5), ("D5", .5), ("C5", 1), ("A4", 1)],
           [("G4", 1), ("B4", .5), ("D5", .5), ("C5", 2)]]
FLATTER_HARM = [["C"], ["F", "C"], ["F"], ["G", "C"]]


def cue_decree(c):
    """A new law: pompous and a little silly, C major. A snare roll swells into a trumpet fanfare (original) with
    timpani; the trombone answers with a pompous slide that sags flat. Under the official's oily flattery: a tiptoeing
    oom-pah (tuba + pizz) and a smarmy oboe with grace notes and a chromatic slither. The king's 'Hmm...' is a held
    G7 with a flute trill; a snare roll builds to the stamp, which lands on a trumpet + timpani + glockenspiel
    'ta-DAH!' and a trombone rip up."""
    s = Score(c, 96, 4); n = s.bars; total = n * 4; E = end_beats(s)
    tpt = P(s, "trumpet", TRUMPET, -7, .35, lp=6500, human=.005)
    tpt2 = P(s, "trumpet 2", TRUMPET, -12, .35, lp=5000, human=.005)
    tbn = P(s, "trombone", TROMBONE, -6, .35, lp=3000, bend=True)
    tuba = P(s, "tuba", TUBA, -2, .25, lp=1500)
    ob = P(s, "oboe (oily)", OBOE, -1, .35, lp=5000, bend=True)
    pz = P(s, "pizz", PIZZ, -4, .25)
    padp = P(s, "strings", SLOW_STR, -6, .5, lp=4000)
    sn = P(s, "snare", DRUMS, -11, .25, human=.003)
    timp = P(s, "timpani", TIMPANI, -7, .35)
    fl = P(s, "flute trill", FLUTE, -10, .4)
    glk = P(s, "glockenspiel", GLOCK, -14, .45)
    king_t = c.first("lines", who="king"); king_b = s.at(king_t)
    stamp = s.at(c.first("sfx", id="seal_stamp"))
    if stamp is None or stamp < 8: stamp = total - 1
    hmm = king_b if king_b is not None and king_b < stamp - 3 else stamp - 4
    # bar 0: snare roll -> bar 1: fanfare
    for i in range(30): sn.add(i * .125, SNARE, .1, 28 + 60 * i / 30)
    for i in range(16): timp.add(2 + i * .125, "G2", .12, 30 + 40 * i / 16)
    fan = [("G4", 1 / 3), ("G4", 1 / 3), ("G4", 1 / 3), ("C5", 1), ("E5", .5), ("G5", 1.5)]
    mel(tpt, 4, fan, 92, legato=.85); mel(tpt2, 4, [(p, d) for p, d in fan], 74, legato=.85, shift=-5)
    tuba.add(5, "C2", 1, 80); tuba.add(6.5, "G2", .5, 70); tuba.add(7, "C2", 1, 80)
    timp.add(5, "C2", .8, 86); timp.add(7, "G2", .4, 70); timp.add(7.5, "C2", 1, 90)
    tbn.add(8, "G3", 1.6, 74); tbn.bend(7.9, 0); tbn.glide(8.6, 9.6, 0, -1.2, 1.5); tbn.bend(9.8, 0)   # sags flat
    for q in range(4):                                                  # bar 2: the oom-pah starts under the sag
        if q % 2 == 0: tuba.add(8 + q, "C2" if q == 0 else "G2", .5, 66)
        else: pz.chord(8 + q, ["G3", "C4", "E4"], .3, 52, strum=.01)
    # flattery oom-pah until the king's "Hmm"
    k = 0; b = 12.0
    while b + 4 <= hmm + 1e-6:
        mel(ob, b, FLATTER[k % 4], 70, legato=.9, vib=True)
        pad(padp, b, FLATTER_HARM[k % 4][0], 4, 36, (55, 75))
        for q in range(4):
            h = FLATTER_HARM[k % 4][min(q * len(FLATTER_HARM[k % 4]) // 4, len(FLATTER_HARM[k % 4]) - 1)]; ps = chord(h)
            if q % 2 == 0: tuba.add(b + q, low(ps[0]) if q == 0 else low(ps[1]), .5, 70)
            else: pz.chord(b + q, [ps[1] + 12, ps[2] + 12, ps[3] + 12], .3, 54, strum=.01)
        if k % 2 == 1: sn.add(b + 3.5, SNARE, .1, 36)
        b += 4; k += 1
    if b < hmm:                                                          # fill to the "Hmm": a cut phrase + oom-pah
        acc, cut = 0, []
        for p_, d_ in FLATTER[k % 4]:
            if b + acc + d_ > hmm + .25: break
            cut.append((p_, d_)); acc += d_
        mel(ob, b, cut, 70, legato=.9, vib=True); pad(padp, b, "C", hmm - b, 36, (55, 75))
        for q in range(int(hmm - b)):
            if q % 2 == 0: tuba.add(b + q, "C2", .5, 64)
            else: pz.chord(b + q, ["G3", "C4", "E4"], .3, 50)
    # the king thinks: held G7 + flute trill
    pad(padp, hmm, "G7", stamp - hmm, 50, (70, 96))
    for i in range(int(2 / .125)): fl.add(hmm + .5 + i * .125, "D6" if i % 2 == 0 else "E6", .11, 46)
    tuba.add(hmm, "G1", 2, 56)
    # snare roll into the stamp
    r0 = max(hmm + 2.5, stamp - 3)
    m = int((stamp - r0) / .125)
    for i in range(m): sn.add(r0 + i * .125, SNARE, .1, 34 + 60 * i / max(1, m))
    for i in range(m): timp.add(r0 + i * .125, "G2", .1, 30 + 40 * i / max(1, m))
    # ta-DAH on the stamp
    tpt.add(stamp - .25, "G4", .2, 84); tpt.chord(stamp, ["C5", "E5", "G5"], E - stamp, 96, strum=.0)
    tpt2.chord(stamp, ["G4", "C5"], E - stamp, 84); tpt.ramp(stamp + .5, E, 11, 120, 60)
    tuba.add(stamp, "C2", E - stamp, 86); timp.add(stamp, "C2", 2, 104)
    for i, p in enumerate(["C6", "E6", "G6", "C7"]): glk.add(stamp + i * .08, p, 1.5, 70)
    tbn.add(stamp, "C3", E - stamp, 80); tbn.bend(stamp - .05, -5); tbn.glide(stamp, stamp + .35, -5, 0, .6)
    pad(padp, stamp, "C", E - stamp, 54, (80, 104))
    return s


# ----------------------------------------------------------------------------------------------- prayer
def cue_prayer(c):
    """Praying at the window: hushed. Harp alone, then a single flute sings the Daniel theme in E minor (bars 1-2)
    over a very soft string pad; when Daniel kneels (the prayer glow) the same melody returns in E major (bars 1, 2,
    4, 5) with soft oohs, and the cue rests on an E major chord. No percussion."""
    s = Score(c, 64, 4); n = s.bars; E = end_beats(s)
    fl = P(s, "flute", FLUTE, -3, .5, lp=6500, human=.009)
    harp = P(s, "harp", HARP, -3, .5, human=.007)
    padp = P(s, "strings", SLOW_STR, -10, .55, lp=3000)
    cb = P(s, "contrabass", CBASS, -13, .35, lp=1000)
    oohs = P(s, "oohs", OOHS, -20, .6, lp=3500)
    glow_b = bar_of(s, c.first("fx", id="prayer_glow"), n - 4)
    glow_b = int(np.clip(glow_b, 1, max(1, n - 2)))
    pre = n - (n - glow_b) - 1                    # minor bars between the intro bar and the glow
    seq = [("min", None)] + [("min", k) for k in theme_seq(pre, close=False)] + [("maj", k) for k in theme_seq(n - glow_b)]
    seq = seq[:n]
    for bar, (mode, k) in enumerate(seq):
        b = bar * 4; final = bar == n - 1; major = mode == "maj"
        harm = (TH_MAJ if major else TH_MIN)[k] if k else (["E"] if major and final else ["Em"])
        if k: mel(fl, b, theme([k], major), 64 if not major else 58, legato=.98, vib=True)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); d = (E - hb) if final and i == len(harm) - 1 else 4 / len(harm)
            pad(padp, hb, h, d + .05, 40, (55, 86)); cb.add(hb, low(chord(h)[0]), d, 44)
            harp_arp(harp, hb, h, min(d, 4 / len(harm)), 46 if bar else 52)
            if major: oohs.chord(hb, [chord(h)[1] + 12, chord(h)[3]], d, 34)
        if final:
            harp.chord(b + 1, ["E3", "B3", "E4", "G#4", "B4", "E5"], E - b - 1, 44, strum=.1)
    return s


# ----------------------------------------------------------------------------------------------- trouble
def cue_trouble(c):
    """The king is so sorry: tense but not scary. Low cellos rock E-F-E (the hijaz half-step) over contrabass and a
    dark pad, a soft slow heartbeat (bass drum lub-dub) underneath. When the stage dims a string tremolo creeps in
    and the harmony starts to move (Em-C-Am-B). The official's smug 'never be changed' gets a bassoon sneer. At the
    king's 'how foolish' the heartbeat stops and the cellos sing the Daniel theme's motif in E minor, slowly, sorry,
    to a held E minor chord."""
    s = Score(c, 60, 4); n = s.bars; E = end_beats(s)
    vc = P(s, "cellos", CELLO, -3, .4, lp=3000, human=.008)
    cb = P(s, "contrabass", CBASS, -6, .3, lp=1000)
    padp = P(s, "low strings", SLOW_STR, -8, .5, lp=2500)
    trem = P(s, "tremolo", TREM_STR, -15, .5, lp=3000)
    hb = P(s, "heartbeat", DRUMS, -5, .12, lp=500, human=.003)
    bsn = P(s, "bassoon sneer", BASSOON, -8, .3)
    cl = P(s, "clarinet", CLARINET, -12, .4, lp=3000)
    dim_b = bar_of(s, c.first("fx", id="tension_dim"), n // 2)
    smug = s.at(next((t for t in sorted(c.all("lines", who="officer"))[1:2]), None))
    sorry_b = bar_of(s, c.first("acting", who="king", clip="head_in_hands"), n - 2)
    sorry_b = int(np.clip(sorry_b, 1, n - 2))
    MOVE = ["Em", "C", "Am", "B"]
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        if bar < sorry_b:
            h = "Em" if bar < dim_b else MOVE[(bar - dim_b) % 4]; ps = chord(h)
            lo_ = low(ps[0]) + 12
            rock = [(nm(lo_), 1.5), (nm(lo_ + 1), .5), (nm(lo_), 2)] if h == "Em" else \
                   [(nm(ps[0]), 2), (nm(ps[0] - 1 if h != "B" else ps[0] + 1), 2)]
            mel(vc, b, rock, 62 + 3 * min(bar, 4), legato=.96)
            pad(padp, b, h, 4.1, 42, (55, 82)); cb.add(b, low(ps[0]), 4, 52)
            if bar >= dim_b: trem.chord(b, [ps[1] + 12, ps[3] + 12], 4.1, 40 + 4 * (bar - dim_b))
            for q in range(4):
                v = 60 + 6 * (bar >= dim_b)
                hb.add(b + q, BDRUM, .2, v); hb.add(b + q + .28, BDRUM, .2, v - 18)
        else:
            j = bar - sorry_b
            if j == 0:
                mel(vc, b, theme([1], False), 70, legato=.98, vib=True); mel(cl, b, theme([1], False), 44, legato=.98)
                harm_at(lambda bt, h, d: (pad(padp, bt, h, d + .05, 46, (60, 90)), cb.add(bt, low(chord(h)[0]), d, 50)), b, ["Em", "C"], 4)
            else:
                mel(vc, b, [("B3", 2), ("E3", max(.5, (E - b) - 2.2) if final else 2)], 64, legato=.98, vib=True)
                pad(padp, b, "Em" if final else "B", (E - b) if final else 4, 44, (60, 88)); cb.add(b, "E2" if final else "B1", (E - b) if final else 4, 50)
    if smug is not None and smug + 3 < sorry_b * 4:
        mel(bsn, smug + .5, [("B3", .5), ("G3", .5), ("B3", .5), ("G3^A3", 1)], 66, legato=.7)
    return s


# ----------------------------------------------------------------------------------------------- den
def cue_den(c):
    """The lions' den at sunset: dark low frame drums and timpani, a sustained string tremolo and low horns,
    building, never horror (consonant minor chords, no clusters, no screech). When Daniel says 'God is with me' the
    drums fall back and the reed plays the Daniel motif calmly, resolving to an E major glimmer. As he walks in, the
    build climbs Em-F-G with a timpani roll; on the roar everything stops (the sfx has the stage); after the stone
    rolls and the seal is stamped, one soft timpani stroke and a low E minor chord hold to the end."""
    s = Score(c, 72, 4); n = s.bars; total = n * 4; E = end_beats(s)
    trem = P(s, "string tremolo", TREM_STR, -8, .5, lp=3200)
    padp = P(s, "low strings", SLOW_STR, -9, .5, lp=2400)
    cb = P(s, "contrabass", CBASS, -6, .3, lp=900)
    timp = P(s, "timpani", TIMPANI, -8, .35)
    dr = P(s, "frame drums", DRUMS, -6, .2, lp=1800, human=.005)
    hn = P(s, "horns", HORN, -12, .45, lp=2500)
    reed = P(s, "reed", ENGLISH_HORN, -11, .45, lp=4000, human=.01)
    reed2 = P(s, "reed breath", CLARINET, -20, .4, lp=3000)
    harp = P(s, "harp", HARP, -10, .45)
    dan = s.at(c.first("lines", who="daniel")); walk = s.at(next((t for t in sorted(c.all("acting", who="daniel", clip="walk"))
                                                                 if dan is not None and s.at(t) is not None and s.at(t) > dan), None))
    roar = s.at(c.first("sfx", id="roar")); seal = s.at(next(iter(sorted(c.all("sfx", id="seal_stamp"))), None))
    roar = roar if roar is not None else total - 4
    dan = dan if dan is not None and dan < roar - 6 else None
    walk = walk if walk is not None and walk < roar else (roar - 4)
    calm0 = math.floor(dan / 4) * 4 if dan is not None else None
    # --- walking to the den: low pulse, tremolo growing (Em, Em, F/E, Em ...)
    WALK = ["Em", "Em", "F", "Em"]
    end1 = calm0 if calm0 is not None else math.floor(walk)
    for bar in range(int(end1 // 4)):
        b = bar * 4; h = WALK[bar % 4]; ps = chord(h)
        trem.chord(b, [note("E3"), ps[1], ps[3]] if h != "F" else [note("E3"), note("A3"), note("C4")], 4.1, 44 + 3 * bar)
        trem.ramp(b, b + 4, 11, 70 + 4 * bar, 82 + 4 * bar)
        pad(padp, b, h, 4.05, 40, (55, 80)); cb.add(b, "E2", 4, 54)
        groove(dr, b, "D...D.t.", .5, FRAME, .7 + .04 * bar); timp.add(b, "E2", .8, 44 + 4 * bar)
        if bar % 2 == 1: hn.chord(b, ["E3", "B3"], 4, 40); hn.ramp(b, b + 4, 11, 60, 96, 1)
    # --- "God is with me": calm
    if calm0 is not None:
        cend = math.floor(walk)
        mel(reed, dan, theme([1], False), 70, legato=.97, vib=True); mel(reed2, dan, theme([1], False), 44, legato=.97)
        reed.add(dan + 4, "E4", max(1, cend - dan - 4.5), 64); reed.vibrato(dan + 4, max(1, cend - dan - 4.5), 30)
        pad(padp, calm0, "Em", dan + 2 - calm0, 40, (60, 80)); pad(padp, dan + 2, "C", 2, 40, (60, 80))
        pad(padp, dan + 4, "E", max(1, cend - dan - 4), 38, (60, 84))                         # E major glimmer
        cb.add(calm0, "E2", cend - calm0, 46); trem.chord(calm0, ["E3", "B3"], cend - calm0, 30)
        harp_arp(harp, dan + 4, "E", max(1, min(4, cend - dan - 4)), 40)
    # --- the build: walk in -> roar
    b0 = math.floor(walk); L = max(1, roar - b0)
    for i, h in enumerate(["Em", "F", "G"]):
        bt = b0 + i * L / 3; ps = chord(h)
        trem.chord(bt, [ps[0], ps[1], ps[3]], L / 3 + .05, 50 + 5 * i); pad(padp, bt, h, L / 3, 46, (66, 88))
        cb.add(bt, low(ps[0]), L / 3, 58 + 3 * i); hn.chord(bt, [ps[1], ps[3]], L / 3, 44 + 4 * i)
    trem.ramp(b0, roar - .1, 11, 66, 90, 1.4)
    q = 0.0
    while b0 + q < roar - .3:
        dr.add(b0 + q, LO_CONGA, .4, 56 + 18 * q / L); dr.add(b0 + q + .5, MUTE_CONGA, .3, 38 + 12 * q / L); q += 1
    m = int(min(L, 4) / .125)
    for i in range(m): timp.add(roar - min(L, 4) + i * .125, "E2", .12, 28 + 24 * i / m)
    timp.add(roar - .02, "E2", .3, 60)                                    # the beat the roar lands on
    # --- after the roar: stone + seal, low E minor held
    after = seal if seal is not None and seal > roar else roar + 2
    cb.add(roar + .5, "E2", E - roar - .5, 40); padp.chord(roar + .5, [note("B2"), note("E3")], E - roar - .5, 34)
    timp.add(after, "E2", 2.5, 80); hn.chord(after, ["E3", "G3", "B3"], E - after, 56); pad(padp, after, "Em", E - after, 54, (75, 100))
    return s


# ----------------------------------------------------------------------------------------------- angel
def cue_angel(c):
    """Inside the den, night. First: soft pizzicato 'paws' prowling low in E minor, a dark pad, single harp notes.
    When the angel's light comes (angel_choir): a harp glissando up into E major, choir + oohs bloom, celesta
    sparkles, and the Daniel theme glows in E major on flute with violins below (bars 1-5 as they fit). After the
    lion rolls over a contented bassoon 'ho-hum'. Rests on E major."""
    s = Score(c, 66, 4); n = s.bars; E = end_beats(s)
    pzl = P(s, "pizz paws", PIZZ, 0, .3)
    drl = P(s, "soft drum", DRUMS, -6, .2, lp=900, human=.004)
    clo = P(s, "low clarinet", CLARINET, -8, .45, lp=2500)
    cb = P(s, "contrabass", CBASS, -11, .35, lp=900)
    padp = P(s, "pad", SLOW_STR, -10, .55, lp=2600)
    choir = P(s, "choir", CHOIR, -5, .65, lp=5000)
    oohs = P(s, "oohs", OOHS, -9, .65, lp=4500)
    harp = P(s, "harp", HARP, -4, .55, human=.006)
    cel = P(s, "celesta", CELESTA, -12, .7)
    fl = P(s, "flute", FLUTE, -3, .55, human=.008)
    vln = P(s, "violins", STRINGS, -9, .6, lp=6000)
    bsn = P(s, "bassoon ho-hum", BASSOON, -10, .4, bend=True)
    light = s.at(c.first("sfx", id="angel_choir")) or s.at(c.first("fx", id="angel_light"))
    light = light if light is not None else n * 2
    roll = s.at(c.first("acting", who="lion", clip="roll_over"))
    lb = int(math.ceil(light / 4))                       # first full bar of light
    # dark prowl
    PAW = [("E2", 1), ("G2", 1), ("F2", 1), ("E2", 1)]
    b = 0.0
    while b < light - .01:
        for i, (p, d) in enumerate(PAW):
            if b + i < light - .1: pzl.add(b + i, p, .4, 54 + (6 if i == 0 else 0))
        if int(b) % 8 == 0: harp.add(b + 2, "B4", 3, 44)
        else: clo.add(b, "B3", min(3.5, light - b - .2), 46)
        for q in (0, 2):
            if b + q < light - .2: drl.add(b + q, LO_CONGA, .5, 50); drl.add(b + q + .3, MUTE_CONGA, .3, 34)
        pad(padp, b, "Em", min(4, light - b), 46, (60, 86)); cb.add(b, "E2", min(4, light - b), 52)
        b += 4
    # the light
    ps_up = [m for m in range(note("E3"), note("E6") + 1) if m % 12 in {4, 6, 8, 9, 11, 1, 3}]
    for i, m in enumerate(ps_up): harp.add(light + i * (1.4 / len(ps_up)), m, 2.5, 40 + 20 * i / len(ps_up))
    for i, p in enumerate(["B6", "G#6", "E7", "B6"]): cel.add(light + 1.5 + i * .5, p, 2, 40)
    if lb * 4 > light + .5:
        choir.chord(light, ["E4", "G#4", "B4"], lb * 4 - light + .3, 46); choir.ramp(light, lb * 4, 11, 40, 100)
        pad(padp, light, "E", lb * 4 - light, 42, (50, 90))
    seq = theme_seq(n - lb)
    for j, k in enumerate(seq):
        bar = lb + j; b = bar * 4; final = bar == n - 1
        harm = TH_MAJ[k] if k else ["E"]
        if k:
            mel(fl, b, theme([k], True), 64, legato=.98, vib=True, shift=12 if k in (1, 2, 5) else 0)
            mel(vln, b, theme([k], True), 46, legato=.98)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); d = (E - hb) if final and i == len(harm) - 1 else 4 / len(harm); ps = chord(h)
            choir.chord(hb, [ps[1], ps[2], ps[3]], d + .2, 50); oohs.chord(hb, [ps[1] + 12, ps[3] + 12], d + .2, 40)
            if hb < .5 + lb * 4: choir.ramp(hb, hb + 1, 11, 90, 104)
            pad(padp, hb, h, d + .05, 44, (70, 96)); cb.add(hb, low(ps[0]), d, 46)
            harp_arp(harp, hb, h, min(d, 4 / len(harm)), 42)
        if bar % 2 == 0: cel.add(b + 2.5, ["E7", "B6", "G#6"][bar % 3], 2, 34)
        if final: harp.chord(b + 1, ["E3", "B3", "E4", "G#4", "B4", "E5", "G#5"], E - b - 1, 44, strum=.1)
    if roll is not None and roll + 3 < n * 4:
        bsn.add(roll + 1, "B2", 1, 60); bsn.add(roll + 2, "E2", 1.6, 58)
        bsn.bend(roll + 1.9, 0); bsn.glide(roll + 2.6, roll + 3.5, 0, -1, 1.2); bsn.bend(roll + 3.7, 0)
    return s


# ----------------------------------------------------------------------------------------------- sleepless
PLOD = [[("A2", 1), ("C3", 1), ("E3", 1), ("C3", 1)], [("D3", 1), ("F3", 1), ("E3", 1.5), (None, .5)],
        [("A2", 1), ("C3^D3", 1), ("B2", 1), ("G#2", 1)], [("A2", 2.5), (None, 1.5)]]
PLOD_HARM = ["Am", "Dm", "E", "Am"]


def cue_sleepless(c):
    """The king can't sleep: comic-sad, A minor. A plodding bassoon (original) on the beat, a clock going
    tick-tock on wood blocks all through, pizzicato off-beat chords, clarinet sighs that droop (pitch slides down a
    minor third) at phrase ends; on the king's toss-and-sigh a big trombone 'waaah' slide. Ends on a low A with the
    clock still ticking."""
    s = Score(c, 84, 4); n = s.bars; E = end_beats(s)
    bsn = P(s, "bassoon plod", BASSOON, -3, .3, human=.008)
    pz = P(s, "pizz", PIZZ, -8, .25)
    clock = P(s, "clock", DRUMS, -7, .12, human=0.0, vel_sd=1.0)
    cl = P(s, "clarinet sighs", CLARINET, -7, .35, bend=True)
    tbn = P(s, "trombone sigh", TROMBONE, -7, .35, lp=2500, bend=True)
    padp = P(s, "pad", SLOW_STR, -15, .5, lp=2500)
    sigh = s.at(c.first("acting", who="king", clip="toss_sigh"))
    for bar in range(n):
        b = bar * 4; final = bar == n - 1; k = bar % 4 if not final else 3
        h = PLOD_HARM[k]; ps = chord(h)
        mel(bsn, b, PLOD[k], 74, legato=.8)
        if final: bsn.add(b, "A2", E - b - .3, 70)
        for q in (1, 3):
            if not final or q == 1: pz.chord(b + q, [ps[1], ps[2], ps[3]], .3, 48, strum=.01)
        pad(padp, b, h, 4 if not final else E - b, 34, (50, 70))
        if bar % 2 == 1 and not final:                                   # droopy sigh
            cl.add(b + 2, "E4", 1.6, 60); cl.bend(b + 1.95, 0); cl.glide(b + 2.4, b + 3.6, 0, -3, 1.6); cl.bend(b + 3.8, 0)
    for q in range(int(E)):
        clock.add(q, HI_WOOD if q % 2 == 0 else LO_WOOD, .15, 46)
    if sigh is not None and sigh + 2.5 < E:
        tbn.add(sigh, "C4", 2.2, 70); tbn.bend(sigh - .05, 0); tbn.glide(sigh + .4, sigh + 2.2, 0, -5, 1.3); tbn.bend(sigh + 2.4, 0)
    return s


# ----------------------------------------------------------------------------------------------- dawn_run
RUN_HARM = ["E", "B", "C#m", "A"]


def cue_dawn_run(c):
    """First light: quick and bright, E major. Violins run in eighths over pizz bass and a running frame drum and
    shaker while the king hurries to the den. When he calls down the music holds its breath (B suspended tremolo, a
    soft timpani pulse). When Daniel answers, horns and flute sing the Daniel theme (bars 1-2, broadened) in E major
    over the running strings; at the king's joy the drums return and it runs home to E."""
    s = Score(c, 144, 4); n = s.bars; E = end_beats(s)
    vln = P(s, "violins run", STRINGS, -6, .4, lp=7000, human=.005)
    va = P(s, "violas", VIOLA, -12, .4)
    pz = P(s, "pizz bass", PIZZ, -6, .22)
    dr = P(s, "running drum", DRUMS, -8, .18, human=.004)
    hn = P(s, "horns", HORN, -4, .4, lp=3500)
    fl = P(s, "flute", FLUTE, -6, .4)
    trem = P(s, "tremolo", TREM_STR, -10, .45)
    padp = P(s, "strings pad", SLOW_STR, -11, .45)
    timp = P(s, "timpani", TIMPANI, -11, .35)
    harp = P(s, "harp", HARP, -10, .4)
    call_b = bar_of(s, c.first("acting", who="king", clip="call_out"), n // 4)
    ans_b = bar_of(s, c.first("lines", who="daniel"), n // 2)
    joy_b = bar_of(s, c.first("sfx", id="sparkle") or c.first("acting", who="king", clip="joy_jump"), n - 2)
    call_b = int(np.clip(call_b, 1, n - 3)); ans_b = int(np.clip(ans_b, call_b + 1, n - 2)); joy_b = int(np.clip(joy_b, ans_b, n - 1))
    th = theme([1, 2], True, scale=2.0); mel(fl, ans_b * 4, th, 66, legato=.97, vib=True, shift=12)
    mel(hn, ans_b * 4, th, 74, legato=.97)
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        if call_b <= bar < ans_b:                                        # holding its breath
            trem.chord(b, ["B3", "E4", "F#4", "A4"], 4.1, 52); pz.add(b, "B1", .5, 54); timp.add(b, "B2", .6, 44); timp.add(b + 2, "B2", .5, 36)
            continue
        if final:
            vln.chord(b, ["E4", "G#4", "B4", "E5"], E - b, 66); padp.chord(b, ["E3", "B3", "G#4"], E - b, 54)
            hn.chord(b, ["E3", "B3", "G#4"], E - b, 66); pz.add(b, "E2", 1, 80); timp.add(b, "E2", 2, 84)
            harp.chord(b, ["E3", "B3", "E4", "G#4", "B4", "E5"], E - b, 54, strum=.04); dr.add(b, LO_CONGA, .5, 80)
            continue
        if bar < call_b: h = RUN_HARM[bar % 4]
        else: h = ["E", "B", "A", "B"][(bar - ans_b) // 2 % 4] if bar < joy_b + 1 else ["A", "B"][bar % 2]
        ps = chord(h); soft = ans_b <= bar < joy_b
        for i in range(8): vln.add(b + i * .5, [ps[0] + 12, ps[3], ps[1] + 12, ps[3]][i % 4] + 12, .45, (62 if i % 2 == 0 else 50) - (8 if soft else 0))
        for q in range(4): pz.add(b + q, low(ps[0]) if q % 2 == 0 else low(ps[1]), .4, 66 if q == 0 else 54)
        va.chord(b, [ps[1], ps[3]], 4, 40)
        if not soft: groove(dr, b, "D.tkD.tkDktkD.tk", .25, {**FRAME, "s": (SHAKER, 30)}, .8)
        else: groove(dr, b, "D...D...", .5, FRAME, .55)
        if bar >= joy_b: hn.chord(b, [ps[1], ps[3]], 4, 56); padp.chord(b, ps[1:], 4, 44)
    return s


# ----------------------------------------------------------------------------------------------- rescue
def cue_rescue(c):
    """Not a scratch: joyful full ensemble, E major. As the stone rolls back the Daniel theme rings out
    triumphantly (violins + flute + horns, timpani, frame drum, harp), the hug blooming in the middle. Then the
    official tiptoes away to a quiet callback of his sneaky bassoon tune; the lion's roar gets silence (the sfx);
    his jump gets a xylophone 'boing' up, and as he runs off the page a flurry of flute/xylophone/pizz scurries away
    and fades, ending on a bright E major pluck."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4; E = end_beats(s)
    vln = P(s, "violins", STRINGS, -3, .55, lp=6500)
    fl = P(s, "flute", FLUTE, -4, .5)
    hn = P(s, "horns", HORN, -6, .45, lp=3200)
    padp = P(s, "pad", SLOW_STR, -6, .5, lp=4500)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1200)
    harp = P(s, "harp", HARP, -7, .45)
    timp = P(s, "timpani", TIMPANI, -9, .35)
    dr = P(s, "frame drum", DRUMS, -10, .2, lp=2800, human=.005)
    oud = P(s, "oud", NYLON, -11, .3)
    bsn = P(s, "bassoon (tiptoe)", BASSOON, -2, .25, human=.006)
    pzt = P(s, "pizz (tiptoe)", PIZZ, -3, .25)
    wb = P(s, "wood blocks", DRUMS, -11, .18)
    xy = P(s, "xylophone", XYLO, -7, .3)
    picc = P(s, "flute scurry", FLUTE, -8, .3)
    tip = s.at(c.first("acting", who="officer", clip="tiptoe")); roar = s.at(c.first("sfx", id="roar"))
    jump = s.at(c.first("acting", who="officer", clip="scared_jump")); run = s.at(c.first("acting", who="officer", clip="run_away"))
    tip = tip if tip is not None else total * .55
    roar = roar if roar is not None and roar > tip else min(total - 4, tip + 6)
    tb = max(1, int(tip // 4))
    for j, k in enumerate(theme_seq(tb)):
        b = j * 4; last = j == tb - 1
        harm = TH_MAJ[k] if k else ["E"]
        if k:
            mel(vln, b, theme([k], True), 80, legato=.97, vib=True, shift=12 if k != 3 and k != 4 else 0)
            mel(fl, b, theme([k], True), 70, vib=True, shift=12)
            mel(hn, b, theme([k], True), 60, legato=.97)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); d = (tip - hb) if last and i == len(harm) - 1 else 4 / len(harm); ps = chord(h)
            pad(padp, hb, h, d + .05, 60, (80, 118)); cb.add(hb, low(ps[0]), d, 62)
            harp_arp(harp, hb, h, min(d, 4 / len(harm)), 50)
            oud_riff(oud, hb, [h], .75, beats=min(d, 4 / len(harm)))
        if not last: groove(dr, b, "D.t.D.tk", .5, FRAME, .9)
        if j == 0: timp.add(0, "E2", 2, 90); [harp.add(i * .06, m, 2, 50) for i, m in enumerate(range(note("E3"), note("E6"), 3))]
        if last: timp.add(b, "B2", .5, 70); timp.add(b + 1, "E2", 2, 84)
    # tiptoe callback (the scheme tune, pp)
    b = tip; i = 0
    while b < roar - .5:
        ph = SCHEME[i % 4]; acc, cut = 0, []
        for p, d in ph:
            if b + acc + d > roar - .3: break
            cut.append((p, d)); acc += d
        mel(bsn, b, cut, 72); mel(pzt, b, cut, 64, shift=12)
        padp.chord(b, [note("B3"), note("E4")], min(4, roar - .3 - b), 30)
        for q in range(4):
            if b + q + .5 < roar - .3: wb.add(b + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 32)
        b += 4; i += 1
    # roar: silence. jump: xylophone boing up. run: scurry away, fading
    if jump is not None and jump > roar:
        for i, p in enumerate(["E4", "B4", "E5", "B5", "E6"]): xy.add(jump + i * .07, p, .3, 60 + 4 * i)
    if run is not None and run < total - 1:
        b = run; i = 0; end = total - 1.0
        SC = ["E6", "D#6", "C#6", "B5", "A5", "G#5", "F#5", "E5"]
        while b < end:
            v = 72 - 34 * (b - run) / max(1, end - run)
            picc.add(b, SC[i % 8], .2, v); xy.add(b, SC[(i + 3) % 8], .2, v - 8)
            if i % 2 == 0: pzt.add(b, ["E3", "B2"][i // 2 % 2], .2, v - 6); wb.add(b + .25, HI_WOOD, .1, v - 20)
            b += .25; i += 1
    pzt.chord(total - .5, ["E3", "B3", "E4", "G#4"], .5, 76, strum=.02); xy.chord(total - .5, ["E5", "G#5", "B5"], .6, 64)
    harp.chord(total - .5, ["E3", "B3", "E4", "G#4", "B4"], E - total + .5, 46, strum=.05)
    padp.chord(total - .5, ["B3", "E4", "G#4"], E - total + .5, 36)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """The living God: warm full statement of the Daniel theme in E major. A soft pad and harp leave room for the
    fanfare; cello + violas + harp + qanun carry bars 1-2 under the king's proclamation; from the golden rays the
    violins, flute and horns sing bars 3-5 with oohs, frame drum and a timpani roll into the cadence; the last bar is a
    held E major chord with celesta and a harp roll."""
    s = Score(c, 78, 4); n = s.bars; E = end_beats(s)
    seq = ([None] * max(0, n - 6) + [1, 2, 3, 4, 5, None])[-n:] if n >= 6 else ([None] + theme_seq(n - 1))[:n]
    vc = P(s, "cello", CELLO, -2, .42, lp=4500, human=.01)
    va = P(s, "viola", VIOLA, -9, .45, lp=4000)
    vln = P(s, "violins", STRINGS, -2, .55, lp=6500)
    fl = P(s, "flute", FLUTE, -4, .5)
    padp = P(s, "pad", SLOW_STR, -5, .5, lp=4500)
    hn = P(s, "horns", HORN, -9, .45, lp=3200)
    cb = P(s, "contrabass", CBASS, -8, .3, lp=1200)
    harp = P(s, "harp", HARP, -6, .45, human=.007)
    qk = P(s, "qanun", KOTO, -12, .3)
    oohs = P(s, "oohs", CHOIR, -15, .6, lp=4500)
    timp = P(s, "timpani", TIMPANI, -11, .35)
    dr = P(s, "frame drum", DRUMS, -12, .2, lp=2500, human=.005)
    cel = P(s, "celesta", CELESTA, -11, .6)
    rays_b = bar_of(s, c.first("fx", id="golden_rays"), n // 2)
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1; full = bar >= rays_b
        harm = TH_MAJ[k] if k else ["E"]
        if k:
            notes = theme([k], True)
            if full:
                mel(vln, b, notes, 78, legato=.98, vib=True, shift=12 if k in (1, 2, 5) else 0)
                mel(fl, b, notes, 70, vib=True, shift=12)
                mel(vc, b, notes, 54, legato=.98, shift=-12 if k in (3, 4) else 0)
            else:
                mel(vc, b, notes, 74, legato=.98, vib=True, shift=-12 if k in (3, 4) else 0)
                mel(va, b, notes, 50, legato=.98)
                for p_, d_ in notes:
                    if p_ and d_ >= 1.5: qk.tremolo(b + sum(dd for _, dd in notes[:notes.index((p_, d_))]), note(p_) + 12, d_, 40)
        for i, h in enumerate(harm):
            hb = b + i * 4 / len(harm); last = final and i == len(harm) - 1
            d = E - hb if last else 4 / len(harm); ps = chord(h)
            pad(padp, hb, h, d + .05, 50 if not full else 60, (60 if bar == 0 else 70, 115 if full else 100))
            cb.add(hb, low(ps[0]), d, 58)
            harp_arp(harp, hb, h, min(d, 4 / len(harm)), 48)
            if full: hn.chord(hb, [ps[1], ps[2], ps[3]], d, 48); oohs.chord(hb, [ps[1] + 12, ps[3]], d, 40)
        if full and not final and k != 4: groove(dr, b, "D...D.t.", .5, FRAME, .8)
        if k == 4:
            for i in range(32): timp.add(b + 2 + i * .0625, "B2", .1, 34 + 34 * i / 32)
            timp.add(b + 4, "E2", 3, 76)
        if final:
            vln.chord(b, ["E5", "G#5", "B5", "E6"], E - b, 60, strum=.04); vln.ramp(b, E, 11, 110, 70)
            for i, p in enumerate(["E6", "G#6", "B6", "E7"]): cel.add(b + 1 + i * .25, p, 3, 54 - i * 3)
            harp.chord(b + .5, ["E2", "B2", "E3", "G#3", "B3", "E4", "G#4", "B4", "E5"], E - b, 52, strum=.07)
    return s


# =============================================================================================== loop section
VAMP = {"babylon": ("Em", "pluck"), "king_friend": ("G", "bed"), "scheme": ("Em", "tiptoe"), "decree": ("C", "bed"),
        "prayer": ("E", "bed"), "trouble": ("Em", "heart"), "den": ("Em", "heart"), "angel": ("E", "choir"),
        "sleepless": ("Am", "tick"), "dawn_run": ("E", "pluck"), "rescue": ("E", "bells"), "finale": ("E", "bells")}


def arp_steps(s): return (s.bpb * 2, .5) if s.bpb in (3, 4) else (s.bpb, 1.0)


def add_vamp(s, chord_name, style):
    """After the cadence: identical repeats of >= VAMP_MIN_SEC (whole bars, no humanising). See music_ruth.py."""
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    reps = max(4, math.ceil((STRETCH * s.span + XFADE + 2.5) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    quiet = style in ("heart", "tiptoe", "tick")
    padp = P(s, "vamp pad", SLOW_STR, -6, .5, lp=3500 if style != "heart" else 2200, **v)
    cb = P(s, "vamp bass", CBASS, -10, .3, lp=1100, **v)
    harp = P(s, "vamp harp", HARP, -8, .45, **v)
    extra = {}
    if style == "pluck":
        extra["oud"] = P(s, "vamp oud", NYLON, -10, .3, **v); extra["dr"] = P(s, "vamp drum", DRUMS, -14, .2, lp=3000, **v)
    if style in ("tiptoe", "tick"):
        extra["pz"] = P(s, "vamp pizz", PIZZ, -6, .25, **v); extra["wb"] = P(s, "vamp blocks", DRUMS, -14, .18, **v)
    if style == "heart": extra["hb"] = P(s, "vamp heartbeat", DRUMS, -10, .12, lp=500, **v)
    if style == "bells": extra["cel"] = P(s, "vamp celesta", CELESTA, -16, .6, **v)
    if style == "choir": extra["oohs"] = P(s, "vamp oohs", OOHS, -14, .6, lp=4000, **v)
    for p_ in [padp, cb, harp] + list(extra.values()): p_.vamp = True
    ps = chord(chord_name); steps, st = arp_steps(s); b0 = s.bars * bpb
    for r in range(reps):
        b = b0 + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 34 if quiet else 46); padp.cc(b, 11, 92)
        cb.add(b, low(ps[0]), Lb + .2, 48)
        if style == "choir": extra["oohs"].chord(b, [ps[1] + 12, ps[3]], Lb + .3, 40); extra["oohs"].cc(b, 11, 92)
        for bar in range(nb):
            bb = b + bar * bpb
            if style in ("bed", "bells", "pluck", "choir"):
                for j in range(steps): harp.add(bb + j * st, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.4, 44 if j else 50)
            if style == "pluck":
                for j, idx in enumerate([0, 1, 2, 1, 3, 1, 2, 1]): extra["oud"].add(bb + j * .5, ps[idx], .45, 52 if j % 4 == 0 else 40)
                groove(extra["dr"], bb, "D...D.t.", .5, FRAME, .6)
            if style == "tiptoe":
                for q, idx in enumerate([0, 1, 3, 1]): extra["pz"].add(bb + q, ps[idx], .2, 54)
                for q in range(4): extra["wb"].add(bb + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 30)
            if style == "tick":
                extra["pz"].add(bb, low(ps[0]) + 12, .3, 52); extra["pz"].add(bb + 2, ps[1], .3, 44)
                for q in range(bpb): extra["wb"].add(bb + q, HI_WOOD if q % 2 == 0 else LO_WOOD, .15, 34)
            if style == "heart":
                for q in range(0, bpb, 2): extra["hb"].add(bb + q, BDRUM, .2, 52); extra["hb"].add(bb + q + .28, BDRUM, .2, 36)
                harp.add(bb, ps[3] + 12, 3, 32)
        if style == "bells": extra["cel"].add(b + bpb, ps[3] + 24, 2, 34)
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
            if me.STEM_REPORT: print(f"    stem {p_.name:22s} rms {20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9):6.1f} dB")
        out[key] = dry + signal.fftconvolve(bus, me.IRS["hall"]())[:n]
    return out[False], out[True]


def clean_tmp():
    """music_esther's renderer leaves one temp dir per stem: keep them in our run dir and empty it after each cue."""
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith(TMP_PREFIX):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def lufs_of(x):
    tmp = tempfile.mkdtemp() + "/m.wav"; wavfile.write(tmp, SR, np.asarray(x, np.float32)); return me.measure(tmp)


MUSIC = {"babylon": cue_babylon, "king_friend": cue_king_friend, "scheme": cue_scheme, "decree": cue_decree,
         "prayer": cue_prayer, "trouble": cue_trouble, "den": cue_den, "angel": cue_angel, "sleepless": cue_sleepless,
         "dawn_run": cue_dawn_run, "rescue": cue_rescue, "finale": cue_finale}
METER = {"king_friend": "3/4"}
KEYS = {"babylon": "E minor (hijaz colour)", "king_friend": "G major", "scheme": "E minor (hijaz)", "decree": "C major",
        "prayer": "E minor -> E major", "trouble": "E minor", "den": "E minor", "angel": "E minor -> E major",
        "sleepless": "A minor", "dawn_run": "E major", "rescue": "E major", "finale": "E major"}
CUE_NOTES = {
    "babylon": "Frame-drum roll, low brass E-F-E, harp hijaz run; downbeat timpani + horns; duduk-like reed (English horn + clarinet breath) sings the Daniel theme (bars 1, 2, 4, 5) over oud ostinato, frame drum, strings; qanun run; cadence on E.",
    "king_friend": "Stately 3/4 lilt: violin tune over pizz bass, viola off-beat chords, light frame drum, oud; at Daniel's answer harp + soft strings and the flute plays the Daniel theme's opening in G major, ending on G.",
    "scheme": "Sulky bassoon + pizz tune (staccato, grace-note harrumphs), wood-block tiptoes; trombone 'pfff' slide on the steam; at the idea a stop, slide-whistle zip up + xylophone pings; sly low clarinet with bassoon 'heh-heh-heh'; 'dun-DUN!' ending. Plays twice (S03, S06).",
    "decree": "Snare roll into a pompous trumpet fanfare; trombone answer sags flat; tuba + pizz oom-pah under a smarmy oboe (grace notes, chromatic slither); king's 'Hmm' = held G7 + flute trill; snare roll into a 'ta-DAH!' on the stamp (trumpets, timpani, glockenspiel, trombone rip).",
    "prayer": "Harp alone, then a single flute sings the Daniel theme in E minor (bars 1-2); at the prayer glow it returns in E major (bars 1, 2, 4, 5) with soft oohs; rests on E major. No percussion.",
    "trouble": "Low cellos rock E-F-E over contrabass and dark pad, soft lub-dub heartbeat; tremolo and moving harmony from the dim; bassoon sneer on the smug line; at 'how foolish' the heartbeat stops and the cellos sing the Daniel motif in E minor, slowly; E minor.",
    "den": "Low frame drums + timpani, string tremolo and low horns building (Em, F/E); reed plays the Daniel motif calmly on 'God is with me' with an E major glimmer; build Em-F-G with timpani roll; silence on the roar; soft timpani and low E minor after the seal.",
    "angel": "Night: pizz 'paws' prowl in E minor; at the angel light a harp glissando into E major, choir + oohs bloom, celesta; the Daniel theme glows in E major on flute over violins; contented bassoon 'ho-hum' after the roll-over; E major.",
    "sleepless": "Plodding bassoon in A minor, tick-tock wood-block clock throughout, pizz off-beats, droopy clarinet sighs (minor-third slides), a big trombone 'waaah' on the toss-and-sigh; ends on low A, clock still ticking.",
    "dawn_run": "Running violin eighths, pizz bass, frame drum + shaker; holds its breath on a suspended B tremolo while the king calls; horns + flute sing the Daniel theme (bars 1-2, broadened) in E major at Daniel's answer; full run home to E at the joy.",
    "rescue": "Triumphant Daniel theme (violins, flute, horns, timpani, frame drum, harp, oud) as the stone rolls back and through the hug; tiptoe callback of the scheme tune; silence for the roar; xylophone boing on the jump; flute/xylophone/pizz scurry fading as he runs off; bright E major pluck.",
    "finale": "Warm full Daniel theme in E major: soft pad + harp leave room for the fanfare; cello/viola/qanun carry bars 1-2 under the proclamation; violins/flute/horns/oohs sing bars 3-5 from the golden rays, timpani roll into the cadence; held E major chord, celesta, harp roll, then the loop bed.",
}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG


def tone(f_curve, amp=1.0, h2=0.0):
    ph = 2 * np.pi * np.cumsum(f_curve) / SR
    return amp * (np.sin(ph) + h2 * np.sin(2 * ph))


def bell(secs, *a, **kw):
    """me.partials with a 40 ms fade at the end of its buffer (a cut-off decay clicks)."""
    y = me.partials(secs, *a, **kw); k = min(len(y), int(.04 * SR)); y[-k:] *= np.linspace(1, 0, k); return y


def curve(n, pts):
    """Piecewise-linear curve over n samples from [(sec, value), ...]."""
    t = np.arange(n) / SR; xs, ys = zip(*pts); return np.interp(t, xs, ys)


def creature(secs, f0_pts, vowels, scale, rough=0.4, rough_hz=30.0, breath=0.2, sub=0.0, tilt=1.15, amp_pts=None,
             jitter=0.02, lp_hz=4000):
    """A big, friendly animal voice: jittered glottal source at f0 (with an optional sub-octave), amplitude
    roughness (the growl: irregular AM at ~rough_hz), breath noise, through moving formants (`scale` < 1 = bigger
    animal), low-passed warm."""
    n = int(secs * SR)
    f0 = curve(n, f0_pts) * (1 + jitter * me.smooth_rand(n, 20))
    src = me.glottal(f0, tilt)
    if sub: src += sub * me.glottal(f0 / 2, tilt + .2)
    rf = rough_hz * (1 + .25 * me.smooth_rand(n, 6))
    am = 1 + rough * np.sin(2 * np.pi * np.cumsum(rf) / SR) * (.6 + .4 * np.abs(me.smooth_rand(n, 9)))
    src = src / (np.std(src) + 1e-9) * am + breath * noise(n) * 2.0 * (.7 + .3 * am)
    y = me.formant_filter(src, vowels, scale)
    y = me.lp(y, lp_hz)
    if amp_pts: y *= curve(n, amp_pts)
    return y


def sfx_roar(ctx):
    """The lion's roar: big but warm, short, no horror. A low 'RAAH-ohh' (f0 105 -> 175 -> 95 Hz with a sub-octave
    for size), growly roughness at ~32 Hz, chest-deep formants, quick swell and a rounded decay, a little den room.
    Low-passed at 3.2 kHz (no snarl, no hiss)."""
    secs = 1.5
    amp = [(0, 0), (.07, .8), (.25, 1), (.8, .85), (1.25, .25), (1.5, 0)]
    y = creature(secs, [(0, 95), (.18, 160), (.5, 185), (.9, 135), (1.4, 80)],
                 [(0, "a"), (.35, "ah"), (.7, "o"), (1, "u")], .56, rough=.75, rough_hz=34, breath=.5, sub=.55,
                 amp_pts=amp, lp_hz=3200)
    n = len(y); t = np.arange(n) / SR
    y = y / (np.max(np.abs(y)) + 1e-9)
    rf = 34 * (1 + .3 * me.smooth_rand(n, 7))
    rasp = me.formant_filter(noise(n) * (1 + .8 * np.sin(2 * np.pi * np.cumsum(rf) / SR)), [(0, "a"), (.6, "o"), (1, "u")], .56)
    rasp = me.lp(rasp, 2600) * curve(n, amp)
    y = y + rasp / (np.max(np.abs(rasp)) + 1e-9) * .45
    body = np.sin(2 * np.pi * np.cumsum(curve(n, [(0, 52), (.3, 70), (1.2, 48)])) / SR) * curve(n, [(0, 0), (.1, .5), (.9, .4), (1.4, 0)])
    y = y / (np.max(np.abs(y)) + 1e-9) + body * .35
    return me.fit(me.room(y, "room", .18), secs, fade_out=.18)


def sfx_growl(ctx):
    """A low, rumbly lion growl, more grumble than threat: f0 ~ 70-85 Hz, heavy slow roughness, 'oh-uu' vowels,
    swells in and out (1.4 s)."""
    secs = 1.4
    y = creature(secs, [(0, 72), (.5, 86), (1.0, 78), (1.4, 66)], [(0, "o"), (.6, "u"), (1, "o")], .58,
                 rough=.85, rough_hz=21, breath=.3, sub=.3, amp_pts=[(0, 0), (.25, .9), (.7, 1), (1.2, .5), (1.4, 0)],
                 lp_hz=2200)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.2)


def sfx_purr(ctx):
    """The lion purrs like a giant kitty: a deep, funny motor rumble. ~26 Hz pulse train ('brrrr') through low 'oo'
    formants, alternating louder out-breaths and softer, lower in-breaths (like a little engine idling), with a
    slow engine wobble; it ends on a contented little 'mrrp?' chirp."""
    secs = 3.4; n = int(secs * SR); t = np.arange(n) / SR
    phase_f0 = [(0, 26), (.75, 28), (.85, 23), (1.55, 22), (1.65, 27), (2.4, 29), (2.5, 23), (2.95, 22), (3.0, 22)]
    f0 = curve(n, phase_f0) * (1 + .03 * np.sin(2 * np.pi * 1.7 * t))
    ph = np.cumsum(f0) / SR
    pulse = np.zeros(n)
    frac = ph % 1.0
    pulse += np.exp(-((frac - .5) / .09) ** 2)                               # one 'thrum' per cycle
    pulse += .35 * np.exp(-((frac - .2) / .05) ** 2)
    src = pulse - pulse.mean() + .15 * noise(n) * pulse
    breath = curve(n, [(0, 0), (.08, 1), (.72, 1), (.82, .45), (1.55, .45), (1.65, 1), (2.38, 1), (2.48, .45), (2.95, .4), (3.0, 0)])
    y = me.formant_filter(src, [(0, "u"), (.5, "o"), (1, "u")], .5)
    y = me.lp(y, 900) * breath + me.lp(src, 180) * .5 * breath
    mrrp = creature(.36, [(0, 170), (.2, 250), (.36, 280)], [(0, "u"), (.6, "a"), (1, "ah")], .9, rough=.3,
                    rough_hz=28, breath=.1, amp_pts=[(0, 0), (.05, 1), (.25, .9), (.36, 0)], lp_hz=3000)
    y = y / (np.max(np.abs(y)) + 1e-9)
    me.place(y, mrrp / (np.max(np.abs(mrrp)) + 1e-9) * .55, 3.0)
    return me.fit(me.room(y, "room", .12), secs, fade_out=.08)


def sfx_yawn_lion(ctx):
    """A huge comic lion yawn: a low 'aaah' that slides up into a squeaky falsetto 'eee-oo' at the top, drops to a
    deep 'ohhhmm', then a jaw smack and a satisfied little 'mm'."""
    secs = 2.4
    y = creature(1.8, [(0, 105), (.45, 150), (.8, 330), (1.0, 360), (1.25, 150), (1.6, 85), (1.8, 80)],
                 [(0, "ah"), (.4, "a"), (.5, "e"), (.62, "o"), (.8, "u"), (1, "u")], .75, rough=.25, rough_hz=26,
                 breath=.45, sub=.15, amp_pts=[(0, 0), (.15, .7), (.7, .9), (1.0, 1), (1.4, .6), (1.75, 0)], lp_hz=4500)
    out = np.zeros(int(secs * SR)); me.place(out, y / (np.max(np.abs(y)) + 1e-9), 0)
    m = int(.05 * SR); tt = np.arange(m) / SR
    att = np.minimum(1, tt / .003)
    smack = (me.lp(me.bp(noise(m), 300, 2200), 2500) * np.exp(-tt / .01) * .5 + np.sin(2 * np.pi * 140 * tt) * np.exp(-tt / .018) * .5) * att
    me.place(out, smack, 1.86)
    mm = creature(.4, [(0, 110), (.2, 125), (.4, 100)], [(0, "u"), (1, "u")], .8, rough=.1, breath=.05,
                  amp_pts=[(0, 0), (.06, 1), (.3, .7), (.4, 0)], lp_hz=700)
    me.place(out, mm / (np.max(np.abs(mm)) + 1e-9) * .35, 1.95)
    return me.fit(me.room(out, "room", .15), secs, fade_out=.1)


def sfx_rooster(ctx):
    """A rooster at dawn, a little way off: 'cock-a-doodle-doooo' as five raspy voiced syllables with rising then
    falling pitch, bright small-bird formants, outdoors."""
    secs = 2.0; out = np.zeros(int(secs * SR))
    syl = [(.0, .11, [(0, 560), (.11, 640)], "a"), (.14, .08, [(0, 620), (.08, 700)], "ah"),
           (.25, .16, [(0, 700), (.16, 780)], "u"), (.44, .1, [(0, 760), (.1, 820)], "e"),
           (.58, .75, [(0, 820), (.2, 900), (.5, 850), (.75, 640)], "u")]
    for at, d, f0, v in syl:
        y = creature(d, f0, [(0, v), (1, "o" if v == "u" else v)], 1.65, rough=.35, rough_hz=70, breath=.15,
                     tilt=1.0, amp_pts=[(0, 0), (.012, 1), (d * .7, .85), (d, 0)], lp_hz=6000, jitter=.03)
        me.place(out, y / (np.max(np.abs(y)) + 1e-9), at + .05)
    out = me.hp(out, 350)
    return me.fit(me.room(out, "room", .3), secs, fade_out=.3)


def sfx_stone_roll(ctx):
    """The big round stone rolls across the opening: a gravelly rolling rumble with a slow bump per turn, grinding
    grit, a heavy THUD as it settles into place (~0.45 s, where the prop swaps), then a small rock and a trickle of
    sand."""
    secs = 1.9; n = int(secs * SR); t = np.arange(n) / SR
    roll_env = curve(n, [(0, 0), (.08, .7), (.42, 1), (.5, .25), (.75, .12), (1.0, 0)])
    rumble = me.lp(noise(n), 160) * 3.0 * roll_env * (1 + .5 * np.abs(np.sin(2 * np.pi * 2.6 * t)))
    grind = me.bp(noise(n), 350, 1600) * .35 * roll_env * (.5 + .5 * np.abs(np.sin(2 * np.pi * 5.2 * t + 1)))
    y = rumble + grind
    for _ in range(140):                                                    # grit
        at = R().uniform(.02, .55) if R().uniform() < .8 else R().uniform(.55, 1.4)
        m = int(R().uniform(.002, .007) * SR)
        g = me.bp(noise(m + 64), 1200, 5000)[:m] * np.exp(-np.arange(m) / (m / 3))
        me.place(y, g * R().uniform(.1, .45) * (1 if at < .55 else .4), at)
    m = int(.5 * SR); tt = np.arange(m) / SR                                # the THUD
    thud = np.sin(2 * np.pi * np.cumsum(38 * np.exp(-tt / .06) + 50) / SR) * np.exp(-tt / .12) * 1.4
    thud += me.lp(noise(m), 500) * np.exp(-tt / .03) * .8
    me.place(y, thud, .45)
    for at, a in ((.72, .3), (.93, .15)):                                   # rocks back once or twice
        m = int(.2 * SR); tt = np.arange(m) / SR
        me.place(y, np.sin(2 * np.pi * 60 * tt) * np.exp(-tt / .05) * a + me.lp(noise(m), 400) * np.exp(-tt / .02) * a * .5, at)
    y += me.bp(noise(n), 2000, 7000) * .04 * curve(n, [(0, 0), (.5, 0), (.6, 1), (1.6, 0)])     # sand trickle
    return me.fit(me.room(y, "room", .18), secs, fade_out=.3)


def sfx_seal_stamp(ctx):
    """The king's ring presses the seal: a firm, satisfying 'thup' (low thump with a pitch drop), the squish of
    soft wax, a tiny bright 'tink' of the gold ring, and a little second press."""
    secs = 0.9; n = int(secs * SR); y = np.zeros(n)
    m = int(.2 * SR); tt = np.arange(m) / SR
    thump = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-tt / .02) + 85) / SR) * np.exp(-tt / .05)
    thump += me.lp(noise(m), 900) * np.exp(-tt / .012) * .5
    me.place(y, thump, .02)
    m = int(.16 * SR); tt = np.arange(m) / SR
    squish = me.bp(noise(m), 500, 2600) * np.sin(np.pi * tt / .16) ** 2 * (1 + .6 * np.sin(2 * np.pi * 38 * tt)) * .22
    me.place(y, squish, .05)
    me.place(y, bell(.7, 2350, [1, 2.71, 5.1], [1, .3, .1], [.18, .08, .04]) * .12, .035)
    m = int(.12 * SR); tt = np.arange(m) / SR
    me.place(y, (np.sin(2 * np.pi * 120 * tt) * np.exp(-tt / .03) + me.lp(noise(m), 700) * np.exp(-tt / .01) * .4) * .35, .26)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.2)


def sfx_idea_ding(ctx):
    """The light-bulb idea: a quick upward 'bwip' and a clear, bright cartoon 'ding!' (E6 bell with a little
    shimmer)."""
    secs = 1.5; n = int(secs * SR); y = np.zeros(n)
    m = int(.07 * SR); tt = np.arange(m) / SR
    me.place(y, tone(np.linspace(700, 1900, m), .35) * np.sin(np.pi * tt / .07), 0)
    f = 440 * 2 ** ((note("E6") - 69) / 12)
    me.place(y, bell(1.4, f, [1, 2.0, 3.01, 4.2, 5.4], [1, .35, .2, .1, .05], [1.0, .45, .25, .12, .08], strike=.12), .07)
    return me.fit(me.room(y, "hall", .25), secs, fade_out=.3)


def gm_render(events, secs):
    """A few GM notes from the DLS bank (like music_esther.gm_notes) with the sustain fix for winds / voices / brass."""
    mid = MidiFile(ticks_per_beat=TPB); meta = MidiTrack(); mid.tracks.append(meta)
    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(60), time=0))
    meta.append(MetaMessage("end_of_track", time=int((secs + 2) * TPB)))
    ev, chans = [], {}
    d = 8192 - 1440
    for t, du, p, v, prog in events:
        new = prog not in chans
        ch = chans.setdefault(prog, len(chans) % 9)
        if new:
            ev.append((0, 0, Message("program_change", channel=ch, program=prog)))
            for cc, val in ((7, 110), (11, 127), (91, 0), (93, 0)):
                ev.append((0, 1, Message("control_change", channel=ch, control=cc, value=val)))
            if prog in SUSTAIN:
                for cc, val in ((99, 120), (98, 37), (6, d >> 7), (38, d & 127)):
                    ev.append((0, 1, Message("control_change", channel=ch, control=cc, value=val)))
        ev.append((int(t * TPB), 2, Message("note_on", channel=ch, note=note(p), velocity=int(v))))
        ev.append((int((t + du) * TPB), 0, Message("note_off", channel=ch, note=note(p), velocity=0)))
    tr = MidiTrack(); mid.tracks.append(tr); last = 0
    for tick, _, m in sorted(ev, key=lambda e: (e[0], e[1])):
        tr.append(m.copy(time=tick - last)); last = tick
    return me.fit(me.render_midi(mid), secs, fade_out=0)


def sfx_angel_choir(ctx):
    """The angel: a soft heavenly choir 'aah' on E major (GM choir + oohs, sustained), swelling in over 1.2 s and
    fading over 1.6 s, with a sprinkle of high bells and air, in the hall."""
    secs = 4.6; ev = []
    for p, v in (("B3", 70), ("E4", 78), ("G#4", 74), ("B4", 76), ("E5", 70)):
        ev.append((0, 4.0, p, v, CHOIR)); ev.append((.05, 4.0, p, v - 14, OOHS))
    x = gm_render(ev, secs); n = len(x)
    x *= curve(n, [(0, 0), (1.2, 1), (2.8, 1), (4.4, 0), (4.6, 0)]) ** 1.5
    for i in range(12):
        pent = ["E6", "F#6", "G#6", "B6", "C#7", "E7"][int(R().integers(0, 6))]
        f = 440 * 2 ** ((note(pent) - 69) / 12)
        me.place(x, bell(1.2, f, [1, 2.76], [1, .2], [.5, .15]) * .05 * R().uniform(.5, 1), .6 + i * .22 + R().normal(0, .03))
    x += me.hp(noise(n), 6000) * .01 * curve(n, [(0, 0), (1.5, 1), (3.5, .5), (4.6, 0)])
    return me.fit(me.room(me.lp(x, 9000), "hall", .4), secs, fade_out=.5)


def sfx_fanfare(ctx):
    """The king's proclamation: a warm, bright fanfare on the Daniel theme's head in E major (E-F#-A-B, then a
    held E major chord), two trumpets a few ms apart over horns, a timpani roll into the last chord."""
    secs = 2.6; ev = []
    tune = [(0.0, .16, "E5", 100), (.2, .12, "F#5", 92), (.34, .12, "A5", 96), (.5, .5, "B5", 112), (1.05, 1.2, "B5", 116)]
    for dt, vs in ((0, 1.0), (.012, .85)):
        for t, d, p, v in tune: ev.append((t + dt + R().normal(0, .003), d, p, v * vs, TRUMPET))
    for p in ("E5", "G#5"): ev.append((1.05, 1.2, p, 98, TRUMPET))
    for p in ("E3", "B3", "E4", "G#4"): ev.append((1.05, 1.25, p, 92, HORN))
    ev.append((.5, .5, "E4", 80, HORN)); ev.append((.5, .5, "B3", 76, HORN))
    for i in range(8): ev.append((.62 + i * .05, .06, "B2", 50 + 6 * i, TIMPANI))
    ev.append((1.05, 1.0, "E2", 112, TIMPANI))
    x = gm_render(ev, secs); n = len(x)
    x *= curve(n, [(0, 1), (2.0, 1), (2.6, 0)])
    return me.fit(me.room(me.lp(x, 9000), "hall", .2), secs, fade_out=.35)


def sfx_sparkle(ctx):
    """Esther's shower of tiny bells (D major pentatonic), shared from music_esther (also used by Ruth)."""
    return me.sfx_sparkle()


LOOP_SECS = {"crickets_night": 20.0}
WRAP = 0.6


def make_loop(y, secs):
    """y is secs + WRAP long; fold the overhang onto the start so the end flows into the beginning."""
    n, k = int(secs * SR), int(WRAP * SR); out = y[:n].copy(); w = np.linspace(0, 1, k)
    out[:k] = y[:k] * np.sqrt(w) + y[n:n + k] * np.sqrt(1 - w)
    return out


def cricket(n, f, chirp_rate, pulses, level, start=0.0):
    y = np.zeros(n); t = start
    syl = int(.016 * SR); u = np.arange(syl) / SR
    s_env = np.sin(np.pi * np.arange(syl) / syl) ** 2
    while t < n / SR - .3:
        ff = f * R().uniform(.995, 1.005)
        for p in range(pulses):
            me.place(y, (np.sin(2 * np.pi * ff * u) + .15 * np.sin(4 * np.pi * ff * u)) * s_env * level * R().uniform(.8, 1), t + p * .03)
        t += 1 / chirp_rate * R().uniform(.85, 1.15)
    return y


def sfx_crickets_night(ctx):
    """Night in Babylon (seamless 20 s loop): four crickets at different distances, a faint warm night breeze,
    and a soft distant palm rustle twice. No owl (Ruth has one)."""
    secs = LOOP_SECS["crickets_night"]; tot = secs + WRAP; n = int(tot * SR); y = np.zeros(n)
    for f, rate, pulses, lvl, start in [(4200, 1.4, 3, .42, .3), (4600, 1.1, 4, .28, .9), (3950, .8, 3, .18, 1.6),
                                        (4850, 1.8, 2, .14, 2.3)]:
        y += me.lp(cricket(n, f, rate, pulses, lvl, start), 7000 if lvl > .3 else 4500)
    t = np.arange(n) / SR
    y += me.lp(noise(n), 350) * .012 * (1 + .5 * np.sin(2 * np.pi * t / tot * 2))
    for at in (6.5, 14.2):
        m = int(1.6 * SR); tt = np.arange(m) / SR
        me.place(y, me.bp(noise(m), 1500, 6000) * np.sin(np.pi * tt / 1.6) ** 2 * .025, at)
    return make_loop(me.room(y, "room", .15)[:n], secs)


SFX = {"idea_ding": sfx_idea_ding, "seal_stamp": sfx_seal_stamp, "roar": sfx_roar, "growl": sfx_growl,
       "stone_roll": sfx_stone_roll, "crickets_night": sfx_crickets_night, "angel_choir": sfx_angel_choir,
       "yawn_lion": sfx_yawn_lion, "purr": sfx_purr, "rooster": sfx_rooster, "sparkle": sfx_sparkle,
       "fanfare": sfx_fanfare}
SFX_SEED = {}
SFX_GAIN = {"idea_ding": -10, "seal_stamp": -8, "roar": -5, "growl": -8, "stone_roll": -7, "crickets_night": -18,
            "angel_choir": -9, "yawn_lion": -8, "purr": -7, "rooster": -13, "sparkle": -9, "fanfare": -8}
SFX_NOTES = {"idea_ding": "quick upward 'bwip' + bright cartoon E6 'ding!'",
             "seal_stamp": "firm low 'thup', wax squish, tiny gold-ring tink, second press",
             "roar": "warm low 'RAAH-ohh' (105-178-92 Hz + sub-octave), growly roughness, chest formants, low-passed 3.2 kHz, den room",
             "growl": "low rumbly grumble ~70-85 Hz, slow roughness, swells in and out",
             "stone_roll": "gravel rumble with a bump per turn, grit, heavy THUD at 0.45 s (prop swap), rocks back, sand trickle",
             "crickets_night": "seamless 20 s loop: 4 crickets, faint night breeze, two distant palm rustles",
             "angel_choir": "GM choir + oohs E major 'aah' (sustained), 1.2 s swell, high bells, hall",
             "yawn_lion": "comic yawn: low 'aaah' sliding up to a squeaky falsetto, down to 'ohhhmm', jaw smack, satisfied 'mm'",
             "purr": "deep funny motor rumble: ~26 Hz thrum, louder out-breaths / lower in-breaths, ends with a 'mrrp?' chirp",
             "rooster": "distant 'cock-a-doodle-doooo', five raspy syllables, outdoors",
             "sparkle": "Esther's D major pentatonic bell shower (shared synth)",
             "fanfare": "two trumpets + horns on the Daniel theme head E-F#-A-B, held E major chord, timpani roll"}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3), secs=round(end - c["t"] + XFADE, 3),
                        last=i + 1 == len(cues)))
    return out


def cue_files(spans):
    """One file per cue name; a cue that plays more than once (scheme) is composed for its longest occurrence."""
    files = {}
    for c in spans: files.setdefault(c["cue"], dict(cue=c["cue"], occ=[]))["occ"].append(c)
    for f in files.values(): f["primary"] = max(f["occ"], key=lambda c: c["span"])
    return files


def render_cue(tl, name, c):
    me.seed("daniel/" + name); ctx = Ctx(tl, name, c["t"], c["span"], c["secs"], c["last"])
    sc = MUSIC[name](ctx)
    add_vamp(sc, *VAMP[name]); vp = sc.vamp
    main, vamp = render_split(sc)
    n = int(round(sc.secs * SR)); main = me.hp(me.fit(main, sc.secs, fade_out=0), 28); vamp = me.hp(me.fit(vamp, sc.secs, fade_out=0), 28)
    ns, ls, le = int(c["span"] * SR), int(round((vp["start"] + vp["secs"]) * SR)), int(round((vp["start"] + 2 * vp["secs"]) * SR))
    # loop tile = the second repeat as rendered (steady state), first 30 ms blended from the true continuation
    L = le - ls; kx = int(.03 * SR); w = np.linspace(0, 1, kx)
    T = vamp[ls:le].copy(); T[:kx] = vamp[le:le + kx] * (1 - w) + vamp[ls:ls + kx] * w
    vs = np.zeros(n); p0 = ls - L
    for j in range(0, (n - p0) // L + 1):
        q = p0 + j * L; m_ = min(L, n - q)
        if m_ > 0: vs[q:q + m_] = T[:m_]
    kf = int(.5 * SR); main[ls - kf:ls] *= np.linspace(1, 0, kf) ** 2; main[ls:] = 0
    gm = MUSIC_LUFS - lufs_of(main[:ns])["lufs"]
    gv = MUSIC_LUFS + VAMP_REL_DB - lufs_of(T)["lufs"]
    for _ in range(3):                                                   # soft-clip rare transients under -1 dBTP,
        x = main * 10 ** (gm / 20) + vs * 10 ** (gv / 20)                # then re-gain so the span stays at -20 LUFS
        if lufs_of(x)["truePeak"] <= -1.3: break
        cl = 10 ** (-1.6 / 20); x = np.tanh(x / cl) * cl
        err = MUSIC_LUFS - lufs_of(x[:ns])["lufs"]
        if abs(err) < .1: break
        gm += err
    k = int(2.5 * SR); x[-k:] *= np.linspace(1, 0, k) ** 2
    path = f"{MUSIC_DIR}/{name}.wav"; me.write_wav(path, x); m = me.measure(path)
    m_span, m_loop = lufs_of(x[:ns]), lufs_of(x[ls:le])
    r = dict(secs=round(len(x) / SR, 3), loopStart=round(ls / SR, 6), loopEnd=round(le / SR, 6), loopStartSample=ls,
             loopEndSample=le, loopFromSec=round(vp["start"], 3), key=KEYS[name], meter=METER.get(name, "4/4"),
             bars=sc.bars, bpm=round(sc.bpm, 1), loopBars=vp["bars"], loopChord=vp["chord"],
             lufs=round(m_span["lufs"], 1), loopLufs=round(m_loop["lufs"], 1), truePeak=round(m["truePeak"], 1),
             composedFor=c["t"], composedSpan=c["span"])
    clean_tmp()
    return r


def build_music(tl, only=None):
    spans = cue_spans(tl)
    missing = sorted({c["cue"] for c in spans} - set(MUSIC)); assert not missing, f"no composer for cue(s) {missing}"
    path_json = f"{MUSIC_DIR}/cues.json"
    old = {}
    if only and os.path.exists(path_json):
        for e in json.load(open(path_json))["cues"]: old.setdefault(e["cue"], e)
    rendered = {}
    for name, f in cue_files(spans).items():
        if only and name not in only and name in old: rendered[name] = {k: v for k, v in old[name].items()}; continue
        rendered[name] = render_cue(tl, name, f["primary"]); r = rendered[name]
        print(f"music {name:11s} t={f['primary']['t']:7.2f} span={f['primary']['span']:6.2f} file={r['secs']:6.2f}s "
              f"bars={r['bars']:2d} bpm={r['bpm']:5.1f} span I={r['lufs']:6.1f} loop {r['loopStart']:.2f}-{r['loopEnd']:.2f}s "
              f"I={r['loopLufs']:6.1f} TP={r['truePeak']:5.1f} dBTP" + (f" (plays {len(f['occ'])}x)" if len(f["occ"]) > 1 else ""))
    manifest = []
    for c in spans:
        r = rendered[c["cue"]]; need = c["span"] * (1 + STRETCH) + XFADE
        assert r["secs"] + 1e-3 >= need, f"{c['cue']} at t={c['t']} is {r['secs']}s, needs {need}s"
        e = dict(cue=c["cue"], t=c["t"], span=c["span"], secs=r["secs"], lastCue=c["last"], loop=False)
        for k in ("loopStart", "loopEnd", "loopStartSample", "loopEndSample", "loopFromSec", "key", "meter", "bars",
                  "bpm", "loopBars", "loopChord", "lufs", "loopLufs", "truePeak", "composedFor", "composedSpan"):
            e[k] = r[k]
        e["plainTailSec"] = round(r["secs"] - c["span"], 3)
        manifest.append(e)
    json.dump(dict(rule="Start each cue at its timeline t at full level and fade the previous cue out over 0.6 s from "
                        "that t. Each cue's composed music ends on its cadence at loopFromSec; after it the cue "
                        "continues into a quiet loop section on its final chord. If the section is stretched (longer "
                        "voice clips), either loop [loopStart, loopEnd) seamlessly (seconds, sample-accurate) until the "
                        "next cue, or just keep playing: every file is at least span x 1.3 + 0.6 s and fades out over "
                        "its last 2.5 s. A cue that plays more than once (scheme) uses the same file from its start each "
                        "time; composedFor / composedSpan name the occurrence it was timed to. The composed span sits at "
                        "-20 LUFS, the loop section ~3 dB under it. Duck music ~7 dB under voice lines. Rerun "
                        "tools/story/music_daniel.py after the timeline is re-timed so the in-cue hits follow.",
                   crossfadeSec=XFADE, lufs=MUSIC_LUFS, stretchCovered=STRETCH, cues=manifest),
              open(path_json, "w"), indent=1, ensure_ascii=False)
    return manifest


def loop_stop(tl, sid):
    t0 = min(e["t"] for e in tl["sfx"] if e["id"] == sid)
    nxt = [m for m in sorted(tl["music"], key=lambda m: m["t"]) if m["t"] > t0 + 1.0]
    return nxt[0]["cue"] if nxt else None


def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]}); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in needed:
        me.seed(SFX_SEED.get(sid, "daniel/" + sid))
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
                        "loop it until the music cue named in stopAtCue starts (fade out over fadeOutSec).",
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
        if s["id"] in LOOP_SECS:
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
        if not hit:
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
    m = me.measure(PREVIEW); clean_tmp()
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
            plain = (c["secs"] - XFADE) / c["span"] - 1
            again = "" if abs(c["composedFor"] - c["t"]) < 1e-6 else f" (same file as at {c['composedFor']:.2f})"
            rows.append(f"| `{c['cue']}`{again} | {c['t']:.2f} | {c['span']:.2f} | {c['secs']:.2f} | {c['loopStart']:.2f}–{c['loopEnd']:.2f} "
                        f"({c['loopBars']} bar{'s' if c['loopBars'] > 1 else ''} on {c['loopChord']}) | loop: any; plain: +{plain * 100:.0f} % "
                        f"| {c['key']} | {c['bars']} × {c['bpm']} ({c['meter']}) | {c['lufs']:.1f} / {c['loopLufs']:.1f} "
                        f"| {c['truePeak']:.1f} | {CUE_NOTES[c['cue']] if not again else 'see above'} |")
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
    ap.add_argument("--tmp", default="/tmp/daniel_music", help="scratch dir (emptied per cue, removed at exit)")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    os.makedirs(a.tmp, exist_ok=True)
    tempfile.tempdir = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=a.tmp)
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    os.makedirs(MUSIC_DIR, exist_ok=True); os.makedirs(SFX_DIR, exist_ok=True)
    tl = json.load(open(TIMELINE))
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
