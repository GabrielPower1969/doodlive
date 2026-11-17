#!/usr/bin/env python3
"""Original score and sound effects for "The King Who Serves" (story pack `lastsupper`; docs/lastsupper/CONTRACT.md
section 7, docs/lastsupper/DESIGN.md section 5, docs/lastsupper/MUSIC.md).

Built on the shared engine tools/story/music_kit.py (`import music_kit as me`) and the finishing helpers in
tools/story/music_polish.py; the loop-section / build machinery is copied from music_miracles.py (same shape, same
cues.json / mix.json format). This script holds only this pack's cues, effects, paths and tables.

A warm acoustic band with a Jerusalem colour: an "oud" (GM nylon guitar, low-passed, tremolo on long notes), frame drum
(congas / bongos), handclaps and tambourine, flute, harp, strings, a children's "ah" choir. One melody, two faces:
  * the JESUS theme is imported from music_miracles.py (JESUS, JESUS_HARM), so the two packs share one Jesus theme.
  * the KING theme: that melody as a bright 4-bar march (dotted rhythms) on flute + a soft trumpet over frame drum:
    the procession (road hint, hosanna, prayer_house in minor, finale).
  * the SERVANT theme: the same melody slowed, a fourth lower (G major), on solo flute and harp: the towel (towel,
    not_my_feet, serve, my_turn bouncy on the oud). The finale plays the King march with the servant melody
    augmented (twice as slow) under it (FINALE_HARM fits both).
Every melody is original; nothing is taken from any film.

Every name and time comes from the timeline, read on every run: the cues are composed for the play as the phone runs
it in Chinese (voice_margin.lang_timeline, re-timed to the installed zh clips; the shortest play, so no cadence is cut
off), in-cue hits are looked up by line id / sfx / fx events. Every file is long enough for its section in the zh play,
the en play and assets/lastsupper/timeline.json x 1.3 + 0.6 s, and after its cadence continues into a quiet loop
section with sample-exact loop points in cues.json. Rerun after re-timing.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/lastsupper/audio/music/<cue>.wav|.mp3   music, -20 LUFS (+-1) over the composed span, true peak <= -1 dBTP
  assets/lastsupper/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/lastsupper/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/lastsupper/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain, loop hints
  assets/lastsupper/audio/preview_mix.mp3        full-length mix of the zh play as the engine mixes it
  docs/lastsupper/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_lastsupper.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--tmp DIR] [--spec DIR]   (scratch default /tmp/lastsupper_music; --spec writes spectrogram PNGs)
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg
"""
import argparse, atexit, json, math, os, re, shutil, sys, tempfile
import numpy as np
from mido import Message, MetaMessage, MidiTrack
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import music_kit as me                                                     # noqa: E402  (shared engine)
import music_polish as mp                                                  # noqa: E402  (speech pocket, underscore curve)
import voice_margin as vm                                                  # noqa: E402  (engine mix model, voice-vs-bed table)
from music_miracles import JESUS, JESUS_HARM                               # noqa: E402  (the shared Jesus theme)
from music_kit import (Score, Ctx, mel, groove, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB,  # noqa: E402
                       HARP, NYLON, CELESTA, GLOCK, XYLO, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                       CHOIR, OOHS, FLUTE, RECORDER, BASSOON, CLARINET, SHANAI, TIMPANI, TUBA, TRUMPET, HORN, DRUMS,
                       CLAP, TAMB, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA, HI_WOOD, LO_WOOD,
                       SHAKER, TRIANGLE)

SID = "lastsupper"
ROOT = me.ROOT
LS = f"{ROOT}/assets/{SID}"
MUSIC_DIR, SFX_DIR = f"{LS}/audio/music", f"{LS}/audio/sfx"
PREVIEW = f"{LS}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/{SID}/MUSIC.md"
STRETCH = 0.30                 # every file covers its longest section (zh / en / base timeline) x 1.3 + 0.6 s
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -4.5             # loop section loudness relative to the cue's composed span
SPAN_LUFS = -20.5              # composed span loudness (contract -20 +-1)
# a little dynamic range between cues inside the contract's +-1 LU: the hush sits lower, the parade and market higher
CUE_LUFS = {"towel": -20.9, "supper": -21.0, "hosanna": -19.6, "market": -19.7, "finale": -20.0}
HIT_SFX = {"table_tip"}        # the only hit clear of speech (the others land inside lines)
HIT_FX = set()
NO_SWELL = set()
AFTER_LINE = {}
END_SWELL = {"finale"}         # the last cue swells back up on its final chord
# extra dips (file seconds, zh play, dB) where a cue sits under a line it cannot get out of the way of
DIPS = {"hosanna": [(12.0, 18.3, -2.5)], "not_my_feet": [(17.3, 20.5, -4.0)], "supper": [(8.9, 15.2, -2.0)]}
WHO_LINES = None               # filled per run: line id -> line dict (zh play)
TMP_PREFIX = "music_lastsupper_"

# extra GM programs (0-based)
VIOLA, WHISTLE = 41, 78
OUD = NYLON

CH = dict(me.CH)
CH.update({"D": ["D3", "A3", "D4", "F#4"], "Dadd9": ["D3", "A3", "E4", "F#4"], "Dm": ["D3", "A3", "D4", "F4"],
           "G": ["G2", "D3", "G3", "B3"], "Gadd9": ["G2", "D3", "A3", "B3"], "A": ["A2", "E3", "A3", "C#4"],
           "A7": ["A2", "E3", "G3", "C#4"], "Asus": ["A2", "E3", "A3", "D4"], "Bm": ["B2", "F#3", "B3", "D4"],
           "Em": ["E2", "B2", "E3", "G3"], "C": ["C3", "G3", "C4", "E4"], "Am": ["A2", "E3", "A3", "C4"],
           "D7": ["D3", "A3", "C4", "F#4"], "Bb": ["Bb2", "F3", "Bb3", "D4"], "Gm": ["G2", "D3", "G3", "Bb3"],
           "F": ["F2", "C3", "F3", "A3"], "Ebdim": ["Eb3", "A3", "C4", "F#4"], "Dsus": ["D3", "A3", "D4", "G4"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def nm(m): return f"{NAMES[m % 12]}{m // 12 - 1}"


# =============================================================================================== the themes
# The KING theme: the Jesus theme bars 1-4 as a bright march (dotted), D major, harmony JESUS_HARM bars 1-4.
KING = {
    1: [("A4", .75), ("A4", .25), ("B4", 1), ("D5", 1.5), ("D5", .5)],
    2: [("E5", 1.5), ("E5", .5), ("D5", 1), ("A4", 1)],
    3: [("F#5", .75), ("E5", .25), ("D5", .5), ("E5", .5), ("D5", .5), ("B4", .5), ("A4", 1)],
    4: [("A4", .75), ("B4", .25), ("D5", 2), (None, 1)],
}
KING_HARM = {k: JESUS_HARM[k] for k in (1, 2, 3, 4)}
# The finale: the King march with the servant melody (Jesus theme) augmented x2 under it; this harmony fits both.
FINALE_HARM = {1: [("D", 4)], 2: [("Em", 2), ("G", 2)], 3: [("Bm", 2), ("A", 2)], 4: [("A", 1), ("D", 3)]}
# The servant theme = the Jesus theme a fourth lower (G major), slowed by the tempo of its cue.
SERV_SHIFT = -7
SERV_MAP = {"D": "G", "A": "D", "G": "C", "Bm": "Em", "A7": "D7", "Em": "Am"}
SERV_HARM = {k: [(SERV_MAP[c], d) for c, d in v] for k, v in JESUS_HARM.items()}
MINOR = {"F#": "F", "C#": "C"}       # King theme "turned serious": D minor (and B -> Bb)


def king(bars, shift=0, scale=1.0, minor=False, stacc=False):
    out = []
    for k in bars:
        for p, d in KING[k]:
            if p is None: out.append((None, d * scale)); continue
            if minor and p[:2] in MINOR: p = MINOR[p[:2]] + p[2:]
            elif minor and p[0] == "B" and p[1].isdigit(): p = "Bb" + p[1:]            # aeolian 6th
            out.append((nm(note(p) + shift) + ("." if stacc else ""), d * scale))
    return out


def jesus(bars, shift=0, scale=1.0, stacc=False):
    out = []
    for k in bars: out += [(nm(note(p) + shift) + ("." if stacc else ""), d * scale) for p, d in JESUS[k]]
    return out


def servant(bars, scale=1.0, stacc=False, octave=0): return jesus(bars, SERV_SHIFT + 12 * octave, scale, stacc)


def harm(b0, harmd, bars, fn, scale=1.0):
    """Call fn(beat, chord, beats) for each chord of the given bars of a harmony table."""
    b = b0
    for k in bars:
        for name, d in harmd[k]: fn(b, name, d * scale); b += d * scale
    return b


# =============================================================================================== small helpers
def beat_of(s, abs_t, default):
    b = s.at(abs_t)
    return default if b is None else b


def line_t(c, lid, edge="start"):
    """Absolute time of a line's start / end in the cue's timeline (None if the line is not there)."""
    l = next((l for l in c.tl["lines"] if l["id"] == lid), None)
    if l is None: return None
    return l["t"] if edge == "start" else l["t"] + l.get("clip", l.get("dur", 3))


def lbeat(s, c, lid, edge="start", default=0.0):
    t = line_t(c, lid, edge)
    if t is None: return default
    return s.beat(t - c.t)


def pad(part, b, name, dur, vel=50, swell=(70, 105), voices=(1, 2, 3), strum=.03, curve=.8, shift=0):
    """Sustained chord with an expression swell; overlaps the next chord; only a cue's first chord swells from low."""
    ps = chord(name); part.chord(b, [ps[i] + shift for i in voices], dur + .25, vel, strum=strum)
    v0 = swell[0] if b < 0.5 else max(82, swell[0])
    part.ramp(b, b + max(.5, dur * .8), 11, v0, max(v0, swell[1]), curve)


def roll(p, b0, b1, pitch, v0, v1, step=.2):
    k = max(2, int((b1 - b0) / step))
    for i in range(k): p.add(b0 + i * (b1 - b0) / k, pitch, step * 1.2, v0 + (v1 - v0) * i / k)


def run(p, b0, pitches, step, vel, dur=1.2):
    for i, pt in enumerate(pitches): p.add(b0 + i * step, pt, dur, vel + 8 * i / max(1, len(pitches) - 1))
    return b0 + len(pitches) * step


def harp_arp(harp, b, name, beats, vel=48, step=.5, up=12, shift=0):
    ps = chord(name)
    for j in range(int(round(beats / step))):
        harp.add(b + j * step, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + up + shift, 1.4, vel + (8 if j == 0 else 0))


# Sustain fix (Ruth, measured 2026-11-14): the macOS DLS bank decays every instrument; winds, bowed strings, brass and
# voices get an NRPN offset on SoundFont gen 37 (volEnvSustain -1440 cB) so long notes hold.
SUSTAIN = {STRINGS, SLOW_STR, TREM_STR, CELLO, VIOLA, CBASS, CHOIR, OOHS, FLUTE, RECORDER, BASSOON, CLARINET, TUBA,
           TRUMPET, HORN, SHANAI, WHISTLE}


def sustain_ccs(p):
    d = 8192 - 1440
    p.cc(0, 99, 120); p.cc(0, 98, 37); p.cc(0, 6, d >> 7); p.cc(0, 38, d & 127)


class BPart(me.Part):
    """A Part that can also bend pitch (bassoon grumble, tuba stomp, slide whistle). Bend range is 12 semitones."""

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


# Loudness trim per GM program (dB), from music_miracles.py / music_jonah.py (measured per stem).
TRIM = {CHOIR: 9, OOHS: 10, STRINGS: 7, TREM_STR: 5, SLOW_STR: 3, TUBA: 6, XYLO: 5, CLARINET: 4, CELESTA: 12, GLOCK: 10,
        PIZZ: 3, HARP: 3, NYLON: 3}


def P(s, name, program, *a, bend=False, **kw):
    a = list(a)
    if len(a) > 0: a[0] = a[0] + TRIM.get(program, 0)
    elif "gain_db" in kw: kw["gain_db"] += TRIM.get(program, 0)
    if bend:
        p = BPart(s, name, program, *a, **kw); s.parts.append(p)
    else:
        p = s.part(name, program, *a, **kw)
    if program in SUSTAIN: sustain_ccs(p)
    return p


def oud_line(p, b0, notes, vel=78, trem_over=1.0):
    """The oud: plucked; notes of trem_over beats or more get a tremolo (risha strokes)."""
    out = [((n + "*") if n and d >= trem_over and not n.endswith(".") else n, d) for n, d in notes]
    return mel(p, b0, out, vel, legato=.9, trem_rate=7.0)


FRAME = {"D": (LO_CONGA, 84), "t": (MUTE_CONGA, 52), "k": (OPEN_CONGA, 34), "s": (TAMB, 26)}
PARADE = {"D": (LO_CONGA, 92), "T": (HI_BONGO, 66), "t": (MUTE_CONGA, 56), "k": (OPEN_CONGA, 44), "b": (LO_BONGO, 58)}
HANDS = {"c": (CLAP, 72), "s": (TAMB, 46), "h": (SHAKER, 40), "x": (TRIANGLE, 34)}
HOOVES = {"H": (HI_WOOD, 58), "L": (LO_WOOD, 50), "h": (HI_WOOD, 36), "l": (LO_WOOD, 30)}


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- road
def cue_road(c):
    """Morning journey up to Jerusalem: a donkey's clip-clop on wood blocks (a lazy trot), a light oud ostinato on a D
    drone, soft frame drum on 1; the recorder hints the King theme's first bar in the last bar; the band rests on the
    `hee_haw` beat so the bray pops, then a last pluck lands on D for the parade."""
    s = Score(c, 92, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -4, .3, lp=4000, human=.006)
    hv = P(s, "hooves", DRUMS, 2, .15, human=.004)
    dr = P(s, "frame drum", DRUMS, -11, .2, lp=3000, human=.005)
    rec = P(s, "recorder (King hint)", RECORDER, -8, .4, human=.008)
    padp = P(s, "pad", SLOW_STR, -12, .5, lp=3000)
    vc = P(s, "cello drone", CELLO, -12, .4, lp=2000)
    hh = beat_of(s, c.first("sfx", id="hee_haw"), total - 1.0)
    rest0, rest1 = hh - .25, hh + 1.0
    OST = [("D4", .5), ("A3", .5), ("D4", .5), ("E4", .5), ("F#4", .5), ("E4", .5), ("D4", .5), ("A3", .5)]
    for bar in range(n):
        b = bar * 4
        if bar < n - 1:
            oud_line(oud, b, OST, 62 if bar % 2 == 0 else 56)
        for i, ch in enumerate("H..LH..LH..LH..L"):
            q = b + i * .25
            if ch in HOOVES and not (rest0 <= q < rest1): hv.add(q, HOOVES[ch][0], .2, HOOVES[ch][1])
        if not (rest0 <= b < rest1): dr.add(b, LO_CONGA, .4, 52)
    pad(padp, 0, "D", total, 36, (50, 80)); vc.add(0, "D3", total + .3, 40)
    lb = (n - 1) * 4
    notes = [(p, d) for p, d in king([1])]
    end = mel(rec, lb, [(p, d) for p, d in notes if True][:3], 56, legato=.9, vib=True)     # A-A-B: a hint only
    oud.add(min(total - .5, rest1), "D3", 1.0, 58); oud.add(min(total - .5, rest1), "A3", 1.0, 50)
    return s


# ----------------------------------------------------------------------------------------------- hosanna
def cue_hosanna(c):
    """The King theme in full: a parade on frame drum + bongos, handclaps and tambourine, flute + a soft trumpet on the
    tune, oud strumming, pizz bass; the second pass adds the children's "ah" choir on the melody and violins; ends on
    a bright D."""
    s = Score(c, 116, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (King)", FLUTE, -3, .4, human=.008)
    tp = P(s, "trumpet (soft)", TRUMPET, -13, .4, lp=3200, human=.008)
    choir = P(s, "children ah", CHOIR, -8, .55, lp=4500)
    vln = P(s, "violins", STRINGS, -12, .45, lp=5000)
    oud = P(s, "oud", OUD, -5, .3, lp=4200, human=.005)
    pz = P(s, "pizz bass", PIZZ, -6, .25)
    cb = P(s, "contrabass", CBASS, -12, .3, lp=1100)
    dr = P(s, "parade drum", DRUMS, -6, .2, lp=4000, human=.004)
    hands = P(s, "claps+tamb", DRUMS, -4, .25, human=.004)
    padp = P(s, "pad", SLOW_STR, -10, .5, lp=3500)
    plan = me.fill_phrase(n, 4, 4, min_intro=1)
    first = next(i for i, k in enumerate(plan) if k is not None); p_i = -1
    for bar, k in enumerate(plan):
        b = bar * 4
        groove(dr, b, "D.tkD.T.D.tkT.bb", .25, PARADE, .85)
        groove(hands, b, "s.s.c.s.s.s.c.s.", .25, HANDS, .85)
        if k is None:
            hm = [("D", 4)]
            oud_line(oud, b, [("D4", .5), ("F#4", .5), ("A4", .5), ("F#4", .5), ("D4", .5), ("F#4", .5), ("A4", 1)], 66)
        else:
            if k == 0: p_i += 1
            full = p_i >= 1
            mel(fl, b, king([k + 1]), 76 if full else 70, legato=.92, vib=True)
            mel(tp, b, king([k + 1]), 56 if full else 48, legato=.9)
            if full:
                mel(choir, b, [(p, d) for p, d in king([k + 1]) if True], 52, legato=.98)
                mel(vln, b, king([k + 1], shift=-12), 44, legato=.95)
            hm = KING_HARM[k + 1]
        bb = b
        for name, d in hm:
            ps = chord(name)
            for q in np.arange(0, d, 1.0):
                oud.chord(bb + q + .5, [ps[1], ps[2], ps[3]], .3, 46, strum=.012)
                pz.add(bb + q, low(ps[0]) + (12 if q % 2 else 0), .3, 66)
            cb.add(bb, low(ps[0]), d, 46); pad(padp, bb, name, d, 40, (70, 92)); bb += d
    ps = chord("D"); padp.chord(total - 1, ps[1:], 1.4, 56); fl.add(total - 1, "D5", 1.2, 74)
    return s


# ----------------------------------------------------------------------------------------------- stones
def cue_stones(c):
    """Comic: a pizzicato tiptoe in D; a bassoon "hmm" (bent down) when the leaders grumble; the tiptoe holds still on
    a warm chord while Jesus answers; then it creeps back for Peter talking to a stone, wood blocks knock; one bright
    celesta chime answers the `ding`; a plink-plonk ends it on D."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4
    pz = P(s, "pizz tiptoe", PIZZ, -3, .25, human=.005)
    bsn = P(s, "bassoon hmm", BASSOON, -4, .3, lp=2500, bend=True)
    wb = P(s, "knock blocks", DRUMS, 2, .18, human=.003)
    cel = P(s, "celesta chime", CELESTA, -12, .55)
    gl = P(s, "glock", GLOCK, -12, .5)
    padp = P(s, "pad", SLOW_STR, -9, .5, lp=3200)
    harp = P(s, "harp", HARP, -10, .45)
    cb = P(s, "contrabass", CBASS, -11, .3, lp=1100)
    gr = lbeat(s, c, "ls_05", "start", .5) + s.beat(1.3)          # "grumbled"
    j0, j1 = lbeat(s, c, "ls_06", "start", 8), lbeat(s, c, "ls_06", "end", 14)
    di = beat_of(s, c.first("sfx", id="ding"), total - 6)
    TIP = ["D3", "F#3", "A3", "F#3", "E3", "G3", "B3", "G3"]
    def tiptoe(b0, b1, vel=58):
        q = math.ceil(b0 * 2) / 2; i = 0
        while q < b1 - .01:
            pz.add(q, TIP[i % 8] if (q % 1) == 0 else nm(note(TIP[i % 8]) + 12), .2, vel - (10 if q % 1 else 0)); q += .5; i += 1
    hold0 = math.floor(j0 * 2) / 2; hold1 = math.ceil(j1)
    tiptoe(0, hold0)
    bsn.add(gr, "A2", .6, 70); bsn.add(gr + .75, "F2", 1.3, 66); bsn.glide(gr + 1.2, gr + 2.0, 0, -2, 1.0); bsn.bend(gr + 2.2, 0)
    pad(padp, hold0, "G", hold1 - hold0, 44, (70, 92)); cb.add(hold0, "G2", hold1 - hold0, 44)
    for k, q in enumerate(np.arange(hold0, hold1 - .5, 2.0)): harp.add(q, ["D5", "B4", "G4", "B4"][k % 4], 2.5, 44)
    pad(padp, hold1 - 2 if hold1 - 2 > hold0 else hold0, "A7", 2, 40, (80, 90))
    tiptoe(hold1, total - 2, 54)
    for q in (hold1 + 2, hold1 + 2.5, hold1 + 6, hold1 + 6.5):       # Peter knocks on the stone
        if q < di - .5 and q < total - 2: wb.add(q, HI_WOOD, .15, 50)
    cel.add(di + .5, "A6", 2.5, 56); cel.add(di + .75, "D7", 2.5, 50); gl.add(di + .5, "D7", 2, 40)
    pz.add(total - 2, "A3", .3, 62); pz.add(total - 1, "D3", .4, 70); pz.chord(total - 1, ["A3", "D4"], .4, 54)
    return s


# ----------------------------------------------------------------------------------------------- market
HIJAZ = [  # D hijaz (D Eb F# G A Bb C), one bar each: a busy bazaar tune for the oud
    [("D4", .5), ("Eb4", .5), ("F#4", .5), ("G4", .5), ("A4", .5), ("G4", .5), ("F#4", .5), ("Eb4", .5)],
    [("D4", .5), ("F#4", .5), ("Eb4", .5), ("D4", .5), ("C4", .5), ("D4", .5), ("Eb4", .5), ("D4", .5)],
    [("A4", .5), ("Bb4", .5), ("A4", .5), ("G4", .5), ("F#4", .5), ("G4", .5), ("A4", .5), ("F#4", .5)],
    [("G4", .5), ("F#4", .5), ("Eb4", .5), ("F#4", .5), ("D4", 1), (None, 1)],
]


def cue_market(c):
    """Busy and a bit too loud: a fast oud bazaar tune in D hijaz, clinking finger-cymbal triangle and tambourine,
    darbuka-like drum, a pizz drone; a squawky shawm honks only in the gaps between the lines (start, the breath
    between the seller and the narrator, the end)."""
    s = Score(c, 132, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -3, .3, lp=4200, human=.004)
    dr = P(s, "darbuka", DRUMS, -6, .2, lp=4000, human=.004)
    hands = P(s, "tamb+triangle", DRUMS, -3, .22, human=.004)
    sh = P(s, "shawm", SHANAI, -10, .35, lp=3500)
    pz = P(s, "pizz drone", PIZZ, -6, .25)
    cb = P(s, "contrabass", CBASS, -12, .3, lp=1000)
    for bar in range(n):
        b = bar * 4
        oud_line(oud, b, HIJAZ[bar % 4], 72 if bar % 2 == 0 else 66, trem_over=2)
        groove(dr, b, "D.tkT.t.D.tkT.kk", .25, PARADE, .8)
        groove(hands, b, "sxs.sxs.sxs.sxsx", .25, HANDS, .8)
        for q in range(4): pz.add(b + q, "D3" if q % 2 == 0 else "A2", .3, 56)
        cb.add(b, "D2", 4, 40)
    gaps = [0.0]
    e8, s9 = lbeat(s, c, "ls_08", "end", None), lbeat(s, c, "ls_09", "start", None)
    if e8 is not None and s9 is not None and s9 - e8 > .3: gaps.append(e8 + .05)
    e9 = lbeat(s, c, "ls_09", "end", total - 1)
    if total - e9 > .3: gaps.append(e9 + .05)
    for g in gaps:
        if g < total - .2: sh.add(g, "A4", .4, 70); sh.add(g + .45, "Bb4", .3, 64) if g + .8 < total else None
    oud.add(total - 1, "D3", 1.0, 70); oud.add(total - 1, "A3", 1.0, 60)
    return s


# ----------------------------------------------------------------------------------------------- prayer_house
def cue_prayer_house(c):
    """A firm low string chord on the `table_tip` (cellos, basses, horns, a timpani stroke) held under Jesus' words;
    then the King theme turned serious (D minor) on horn + cello under the sellers' laments; from the golden rays it
    turns tender in D major and the children's choir sings the Jesus theme softly over harp; ends on D."""
    s = Score(c, 76, 4); n = s.bars; total = n * 4
    vc = P(s, "cellos", CELLO, -3, .4, lp=3000, human=.006)
    cb = P(s, "basses", CBASS, -8, .35, lp=1000)
    hn = P(s, "horn", HORN, -7, .45, lp=2800, human=.008)
    tim = P(s, "timpani", TIMPANI, -8, .4, lp=900)
    padp = P(s, "strings", SLOW_STR, -6, .5, lp=3200)
    choir = P(s, "children ah", CHOIR, -7, .6, lp=4500)
    harp = P(s, "harp", HARP, -7, .45)
    fl = P(s, "flute", FLUTE, -10, .45)
    trem = P(s, "tremolo strings", TREM_STR, -8, .45, lp=3500)
    tt = beat_of(s, c.first("sfx", id="table_tip"), 1.0)
    gr = beat_of(s, c.first("fx", id="golden_rays"), total - 10)
    tb = math.floor(gr / 4) * 4 if gr % 4 < 1.5 else math.ceil(gr / 4) * 4       # tender section: a bar line
    tb = min(max(8, tb), total - 8)
    # the firm chord
    vc.chord(tt, ["D2", "A2", "D3"], 4.0, 80); cb.add(tt, "D2", 7.5, 66); hn.chord(tt, ["D3", "A3", "D4"], 3.5, 78)
    trem.chord(tt, ["D4", "A4", "D5"], 4.0, 60); trem.ramp(tt, tt + 4, 11, 120, 60)
    tim.add(tt, "D2", 2.5, 78); roll(tim, tt - .6, tt, "A1", 40, 64, .1)
    hn.ramp(tt, tt + 3, 11, 120, 70)
    s8 = 8
    pad(padp, tt + 1, "Dm", s8 - tt - 1, 44, (90, 70)); vc.add(tt + 4, "D3", s8 - tt - 4, 60)
    # the King theme, serious (minor), bars 1, 2, 4 in tempo on horn, cello an octave down
    sb = list(range(1, 1 + (tb - s8) // 4))
    seq = [1, 2, 3, 4] if len(sb) >= 4 else [1, 2, 4] if len(sb) == 3 else [1, 4] if len(sb) == 2 else [4]
    SER = {1: [("Dm", 4)], 2: [("Gm", 2), ("Dm", 2)], 3: [("Bb", 2), ("Gm", 2)], 4: [("A", 2), ("Dm", 2)]}
    b = s8
    for k in seq[:len(sb)]:
        mel(hn, b, king([k], minor=True), 84, legato=.95, vib=True)
        mel(vc, b, king([k], shift=-12, minor=True), 70, legato=.95)
        harm(b, SER, [k], lambda bb, nmn, d: (pad(padp, bb, nmn, d, 52, (84, 100)), cb.add(bb, low(chord(nmn)[0]), d, 44),
                                             harp_arp(harp, bb, nmn, d, 40, step=1.0)))
        b += 4
    while b < tb:
        pad(padp, b, "A", tb - b, 42, (70, 88)); cb.add(b, "A1", tb - b, 46); b = tb
    # tender: D major, children's choir + flute sing the Jesus theme bars 1-2, harp
    nb = (total - tb) // 4
    bars = [1, 2] if nb >= 2 else [1]
    def chordfn(bb, nmn, d): pad(padp, bb, nmn, d, 46, (70, 96)); harp_arp(harp, bb, nmn, d, 44); cb.add(bb, low(chord(nmn)[0]), d, 42)
    e = harm(tb, JESUS_HARM, bars, chordfn)
    mel(choir, tb, jesus(bars), 56, legato=.98); mel(fl, tb, jesus(bars), 48, legato=.97, vib=True)
    if e < total:
        pad(padp, e, "D", total - e, 46, (80, 92)); harp_arp(harp, e, "D", total - e, 40)
        choir.chord(e, ["F#4", "A4", "D5"], total - e + .3, 50); cb.add(e, "D2", total - e, 42)
    return s


# ----------------------------------------------------------------------------------------------- argue
SQUAB = {  # who -> (instrument key, two-note "me! me!" motif, step beats)
    "james": ("cl", ["G3", "A3", "B3", "A3"], .5),
    "john": ("oud", ["B3", "C#4", "D4", "C#4"], .25),
    "peter": ("tuba", ["D2", "A1", "D2", "F#2"], 1.0),
    "andrew": ("cl_soft", ["E3", "D3"], 1.0),
}


def cue_argue(c):
    """Evening walk upstairs under the narrator (warm G, walking pizz, oud, a sunset pad); then the squabble: every
    disciple's line gets its own stubborn little motif (James: clarinet, John: quick oud, Peter: pompous tuba, Andrew:
    soft low clarinet), each one cutting in on the last (stop-start), and Peter's "doesn't count!" gets a tuba stomp;
    the three end together on a sour little stab, then silence for the towel."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -4, .3, lp=4000, human=.006)
    pz = P(s, "walking pizz", PIZZ, -5, .25)
    padp = P(s, "sunset pad", SLOW_STR, -9, .5, lp=3000)
    cl = P(s, "clarinet", CLARINET, -6, .3, lp=3200, human=.006, bend=True)
    tuba = P(s, "tuba", TUBA, -4, .25, lp=1400, bend=True)
    cb = P(s, "contrabass", CBASS, -12, .3, lp=1000)
    harp = P(s, "harp", HARP, -10, .45)
    lines = [l for l in c.tl["lines"] if c.t - 1e-6 <= l["t"] <= c.t + c.span and l["who"] in SQUAB]
    q0 = s.beat(lines[0]["t"] - c.t) if lines else total * .4
    walk_end = math.floor(q0)
    # the walk upstairs: G - Em - C - D, pizz steps up
    WALK = ["G", "Em", "C", "D"]
    b = 0; i = 0
    while b < walk_end:
        d = min(4, walk_end - b); name = WALK[i % 4]; ps = chord(name)
        pad(padp, b, name, d, 40, (60, 86)); cb.add(b, low(ps[0]), d, 42)
        for q in range(int(d)): pz.add(b + q, ps[[0, 1, 2, 1][q]] + (0 if q < 2 else 0), .3, 56 + 2 * q)
        if d >= 4: oud_line(oud, b, [(nm(ps[2] + 12), 1), (nm(ps[3] + 12), 1), (nm(ps[1] + 12), 1.5), (None, .5)], 56)
        harp.add(b, ps[3] + 12, 2.5, 38)
        b += d; i += 1
    # the squabble
    parts = {"cl": (cl, 62), "oud": (oud, 64), "tuba": (tuba, 70), "cl_soft": (cl, 46)}
    for j, l in enumerate(lines):
        key, motif, step = SQUAB[l["who"]]; p_, vel = parts[key]
        b0 = s.beat(l["t"] - c.t); nxt = s.beat(lines[j + 1]["t"] - c.t) if j + 1 < len(lines) else total - 1
        b1 = min(nxt, s.beat(l["t"] + l["clip"] - c.t) + .25)
        q = math.ceil(b0 / .25) * .25; k = 0
        while q < b1 - .05:
            dur = step * (.45 if key in ("oud", "cl") else .8)
            p_.add(q, motif[k % len(motif)], dur, vel - (6 if k % 2 else 0)); q += step; k += 1
        pz.add(b0, "D3" if l["who"] == "peter" else "G2", .3, 62)                          # the interruption bump
    # "That doesn't count!": tuba stomp at the end of Peter's last line, then the sour stab and silence
    last_peter = [l for l in lines if l["who"] == "peter"]
    if last_peter:
        e = s.beat(last_peter[-1]["t"] + last_peter[-1]["clip"] - c.t)
        st = min(e + .1, total - 1.2)
        tuba.add(st, "G1", .5, 80); tuba.glide(st + .1, st + .5, 0, -3, 1.0); tuba.bend(st + .7, 0)
        sb = min(st + 1.0, total - .6)
        cl.add(sb, "C#4", .35, 62); oud.chord(sb, ["G3", "C#4", "Eb4"], .35, 62); tuba.add(sb, "D2", .35, 66)
    return s


# ----------------------------------------------------------------------------------------------- towel
def cue_towel(c):
    """Hush: the servant theme (the Jesus theme a fourth lower, slow) on solo flute over held strings in G; a single harp
    note for every step; a held G to close."""
    s = Score(c, 58, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (servant)", FLUTE, -4, .5, human=.01)
    padp = P(s, "held strings", SLOW_STR, -6, .55, lp=2800)
    vla = P(s, "violas", VIOLA, -12, .5, lp=2600)
    harp = P(s, "harp steps", HARP, -5, .55)
    cb = P(s, "contrabass", CBASS, -13, .4, lp=800)
    tb = 4 if n >= 5 else 0
    nb = min(4, (total - tb) // 4)
    bars = list(range(1, nb + 1)) if nb < 4 else [1, 2, 3, 4]
    pad(padp, 0, "Gadd9", tb if tb else 1, 34, (45, 72)); cb.add(0, "G2", tb + .2, 36)
    def chordfn(b, name, d):
        pad(padp, b, name, d, 38, (70, 86)); cb.add(b, low(chord(name)[0]), d, 38)
        vla.chord(b, [chord(name)[1], chord(name)[2]], d + .2, 30)
    e = harm(tb, SERV_HARM, bars, chordfn)
    mel(fl, tb, servant(bars), 62, legato=.97, vib=True)
    if e < total: pad(padp, e, "G", total - e, 38, (80, 86)); cb.add(e, "G2", total - e, 36)
    STEP = ["G4", "B4", "D5", "B4", "A4", "D5", "G4", "D4"]
    for k, b in enumerate(np.arange(0, total - .99, 2.0)): harp.add(b, STEP[k % 8], 3.0, 42 if k % 2 == 0 else 36)
    return s


# ----------------------------------------------------------------------------------------------- not_my_feet
def cue_not_my_feet(c):
    """Comic, then tender, in G: pizz tiptoes the servant theme; Peter's "Never!" gets a quick pizz scurry up and a
    stab; Jesus' answer sits on a warm held chord with harp; Peter's "wash all of me!" builds bouncing pizz and ends on
    a slide whistle up; Jesus' laugh resolves warmly (strings + harp roll on G); under the narrator about Judas the cello
    sings the servant theme, tender, and it closes on G."""
    s = Score(c, 104, 4); n = s.bars; total = n * 4
    pz = P(s, "pizz", PIZZ, -3, .25, human=.005)
    wh = P(s, "slide whistle", WHISTLE, -12, .3, lp=5000, bend=True)
    padp = P(s, "strings", SLOW_STR, -7, .5, lp=3200)
    harp = P(s, "harp", HARP, -7, .45)
    vc = P(s, "cello", CELLO, -6, .4, lp=3000, human=.008)
    cb = P(s, "contrabass", CBASS, -12, .35, lp=900)
    xy = P(s, "xylophone", XYLO, -12, .3)
    n0 = lbeat(s, c, "ls_23", "start", 3); n1 = lbeat(s, c, "ls_23", "end", 12)
    j0, j1 = lbeat(s, c, "ls_24", "start", 13), lbeat(s, c, "ls_24", "end", 20)
    w0, w1 = lbeat(s, c, "ls_25", "start", 21), lbeat(s, c, "ls_25", "end", 30)
    h0 = lbeat(s, c, "ls_26", "start", 31)
    d0 = lbeat(s, c, "ls_27", "start", 38)
    # tiptoe the servant theme's first notes, staccato
    mel(pz, 0, servant([1], scale=.5, stacc=True) + [(None, 1)], 60)
    # "Never, ever!": scurries up under the line, a stab right after it
    q = math.ceil(n0)
    while q < n1 - 1.5:
        run(pz, q, ["G3", "A3", "B3", "C4", "D4"], .25, 46, .2); q += 2
    pz.chord(n1 + .1, ["G3", "D4", "G4"], .3, 74)
    # Jesus' answer: warm held chord, harp
    jb = math.floor(n1 + .5)
    pad(padp, jb, "Em", (w0 - jb) / 2, 40, (70, 90)); pad(padp, jb + (w0 - jb) / 2, "C", (w0 - jb) / 2, 40, (82, 92))
    cb.add(jb, "E2", (w0 - jb) / 2, 40); cb.add(jb + (w0 - jb) / 2, "C2", (w0 - jb) / 2, 40)
    for k, b in enumerate(np.arange(jb, w0 - .5, 2.0)): harp.add(b, ["B4", "G4", "E5", "C5"][k % 4], 2.5, 40)
    # "Then not just my feet!...": bouncing pizz, rising, then the slide whistle
    q = math.ceil(w0); k = 0
    BOUNCE = ["D3", "D4", "G3", "G4", "A3", "A4", "B3", "B4"]
    while q < w1 - .4:
        pz.add(q, BOUNCE[k % 8], .2, 44 + min(20, k)); q += .5; k += 1
    wh.add(w1 - 1.1, "C5", 1.4, 62); wh.bend(w1 - 1.1, 0); wh.glide(w1 - 1.0, w1 + .25, 0, 12, 1.4); wh.bend(w1 + .5, 0)
    # the laugh: warm resolve on G
    hb = max(w1 + .4, h0 - .1)
    pad(padp, hb, "G", d0 - hb, 50, (90, 100)); cb.add(hb, "G2", d0 - hb, 44)
    run(harp, hb, ["G3", "B3", "D4", "G4", "B4", "D5", "G5"], .1, 50, 2.5)
    xy.add(h0 + .5, "D6", .3, 40); xy.add(h0 + .75, "B5", .3, 36); xy.add(h0 + 1.0, "D6", .3, 40)
    # Judas: tender cello servant theme bars 1-2 under a soft pad; close on G
    db = math.floor(d0)
    rem = total - db
    sc = min(1.0, rem / 8.5)
    def chordfn(b, name, d): pad(padp, b, name, d, 38, (70, 84)); cb.add(b, low(chord(name)[0]), d, 36)
    e = harm(db, SERV_HARM, [1, 2], chordfn, scale=sc)
    mel(vc, db, servant([1, 2], scale=sc, octave=-1), 58, legato=.98, vib=True)
    if e < total: pad(padp, e, "G", total - e, 36, (78, 82)); cb.add(e, "G2", total - e, 34); harp.add(e, "G4", 3, 36)
    return s


# ----------------------------------------------------------------------------------------------- serve
def cue_serve(c):
    """The servant theme, warmer: flute with violins joining a sixth below, cello counter-line, harp; G major."""
    s = Score(c, 64, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (servant)", FLUTE, -4, .45, human=.01)
    vln = P(s, "violins", STRINGS, -10, .5, lp=4500)
    padp = P(s, "strings", SLOW_STR, -6, .5, lp=3200)
    vc = P(s, "cello", CELLO, -8, .4, lp=3000)
    harp = P(s, "harp", HARP, -8, .45)
    cb = P(s, "contrabass", CBASS, -12, .35, lp=900)
    bars = [1, 2, 4][:n] if n <= 3 else [1, 2, 3, 4][:n]
    def chordfn(b, name, d):
        pad(padp, b, name, d, 46, (80, 100)); cb.add(b, low(chord(name)[0]), d, 42); harp_arp(harp, b, name, d, 42)
        vc.add(b, chord(name)[1] - 12 if chord(name)[1] - 12 >= note("C2") else chord(name)[1], d * .95, 50)
    harm(0, SERV_HARM, bars, chordfn)
    notes = servant(bars); notes[-1] = (notes[-1][0], notes[-1][1] + .5)
    mel(fl, 0, notes, 68, legato=.97, vib=True)
    mel(vln, 1 if n > 1 else 0, servant(bars, octave=0)[2:], 40, legato=.98)      # strings join a little later
    return s


# ----------------------------------------------------------------------------------------------- supper
SUPPER_HARM = ["D", "G", "Bm", "A", "D"]


def cue_supper(c):
    """Very still and reverent: harp arpeggios and soft strings on a slow chorale (D G Bm A D); a high violin line
    breathes the Jesus theme at half speed; a celesta glimmer when the cup glows; no drums."""
    s = Score(c, 56, 4); n = s.bars; total = n * 4
    harp = P(s, "harp", HARP, -6, .5)
    padp = P(s, "soft strings", SLOW_STR, -6, .55, lp=2600)
    vln = P(s, "high violins", STRINGS, -14, .55, lp=4200)
    cb = P(s, "contrabass", CBASS, -13, .4, lp=800)
    cel = P(s, "celesta", CELESTA, -16, .6)
    hg = beat_of(s, c.first("fx", id="heart_glow"), total - 6)
    for bar in range(n):
        b = bar * 4; name = SUPPER_HARM[min(bar, len(SUPPER_HARM) - 1)] if bar < n - 1 else "D"
        pad(padp, b, name, 4, 36, (60, 80)); cb.add(b, low(chord(name)[0]), 4, 34)
        harp_arp(harp, b, name, 4, 36, step=.5)
    mel(vln, 0, jesus([1, 2], scale=2.0)[:min(5, 2 * n)], 34, legato=.99)
    for k, p_ in enumerate(["A6", "D7", "F#7"]): cel.add(hg + k * .5, p_, 3.0, 40)
    return s


# ----------------------------------------------------------------------------------------------- my_turn
def cue_my_turn(c):
    """Light and smiling: the servant theme played bouncy and staccato by the oud (G major), oom-pah pizz, shaker and
    a soft frame drum; a xylophone giggle on Andrew's "that tickles!"; it lands on D for the finale."""
    s = Score(c, 116, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -2, .3, lp=4200, human=.005)
    pz = P(s, "pizz oom-pah", PIZZ, -5, .25)
    dr = P(s, "frame drum", DRUMS, -10, .2, lp=3500, human=.004)
    hands = P(s, "shaker", DRUMS, -6, .22, human=.004)
    xy = P(s, "xylophone giggle", XYLO, -9, .3)
    fl = P(s, "flute", FLUTE, -10, .4)
    cb = P(s, "contrabass", CBASS, -13, .3, lp=1000)
    an = lbeat(s, c, "ls_34", "start", total * .55)
    plan = [None] + [1, 2, 3, 4] + ([1] if n >= 7 else []) + ["end"]
    plan = plan[:n - 1] + ["end"]
    for bar, k in enumerate(plan):
        b = bar * 4
        groove(dr, b, "D...t.k.D...t.k.", .25, FRAME, .7); groove(hands, b, "h.hhh.hhh.hhh.hh", .25, HANDS, .7)
        if k == "end":
            pz.add(b, "A2", .3, 60); pz.add(b + 1, "D3", .3, 60); oud.chord(b + 2, ["D3", "A3", "D4", "F#4"], 1.8, 70, strum=.02)
            fl.add(b + 2, "D5", 1.8, 56); cb.add(b + 2, "D2", 2, 46)
            continue
        if k is None:
            hm = [("G", 4)]
            oud_line(oud, b, [("G3.", .5), ("D4.", .5), ("B3.", .5), ("D4.", .5), ("G3.", .5), ("D4.", .5), ("B3.", 1)], 64)
        else:
            oud_line(oud, b, servant([k], stacc=True, octave=1 if bar >= 5 else 0), 78)
            hm = SERV_HARM[k]
        bb = b
        for name, d in hm:
            ps = chord(name)
            for q in np.arange(0, d, 1.0): pz.add(bb + q, low(ps[0]) if q % 2 == 0 else ps[1], .25, 58)
            cb.add(bb, low(ps[0]), d, 40); bb += d
    run(xy, an + .25, ["B5", "D6", "B5", "D6", "G6"], .25, 46, .25)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """Both themes together, warm and full: the King march on flute + soft trumpet with the oud, and the servant melody
    (the Jesus theme) augmented under it on horn and cellos (FINALE_HARM); harp and strings on the first pass; frame
    drum, claps, the children's choir and violins join on the second; a bright held D chord, harp roll, glock."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (King)", FLUTE, -3, .45, human=.01)
    tp = P(s, "trumpet (soft)", TRUMPET, -14, .4, lp=3200)
    oud = P(s, "oud", OUD, -6, .3, lp=4200, human=.006)
    hn = P(s, "horn (servant)", HORN, -6, .45, lp=2800, human=.008)
    vc = P(s, "cellos (servant)", CELLO, -8, .4, lp=3000)
    vln = P(s, "violins", STRINGS, -10, .5, lp=5000)
    choir = P(s, "children ah", CHOIR, -9, .6, lp=4500)
    padp = P(s, "strings", SLOW_STR, -8, .5, lp=3500)
    harp = P(s, "harp", HARP, -8, .45)
    cb = P(s, "contrabass", CBASS, -11, .3, lp=1100)
    dr = P(s, "frame drum", DRUMS, -9, .2, lp=3500, human=.005)
    hands = P(s, "claps", DRUMS, -6, .25, human=.004)
    gl = P(s, "glock", GLOCK, -14, .5)
    tim = P(s, "timpani", TIMPANI, -12, .4, lp=900)
    plan = me.fill_phrase(n, 4, 4, min_intro=0)
    starts = [i for i, k in enumerate(plan) if k == 0]
    p_i = -1
    for bar, k in enumerate(plan):
        b = bar * 4
        if k is None:
            pad(padp, b, "D", 4, 44, (60, 90)); harp_arp(harp, b, "D", 4, 44); cb.add(b, "D2", 4, 48); continue
        if k == 0:
            p_i += 1
            # the servant melody augmented: Jesus bars 1-2 on the first pass, bars 3-4 on the second (horn + cellos)
            aug = jesus([1, 2] if p_i % 2 == 0 else [3, 4], shift=-12, scale=2.0)
            last_pass = bar + 4 >= n
            if last_pass: aug = aug[:-1] + [(aug[-1][0], aug[-1][1] - 2)]
            mel(hn, b, aug, 60 if p_i == 0 else 66, legato=.98, vib=True)
            mel(vc, b, aug, 46, legato=.98, shift=-12 if p_i == 0 else 0)
        full = p_i >= 1
        last_bar = bar == n - 1
        if not last_bar:
            mel(fl, b, king([k + 1]), 76 if full else 70, legato=.92, vib=True)
            mel(tp, b, king([k + 1]), 52 if full else 44, legato=.9)
            if full: mel(vln, b, king([k + 1]), 46, legato=.95)
        else:
            mel(fl, b, [("A4", .75), ("B4", .25), ("D5", 3)], 80, legato=.97, vib=True)
            mel(tp, b, [("A4", .75), ("B4", .25), ("D5", 3)], 50, legato=.95)
        def chordfn(bb, name, d):
            pad(padp, bb, name, d, 50 if full else 44, (80, 104)); cb.add(bb, low(chord(name)[0]), d, 50)
            ps = chord(name)
            for q in np.arange(0, d, 1.0): oud.chord(bb + q + .5, [ps[1], ps[2], ps[3]], .3, 44, strum=.012)
            if not full: harp_arp(harp, bb, name, d, 42)
            else: choir.chord(bb, [ps[2], ps[3]], d + .2, 44)
        harm(b, FINALE_HARM, [k + 1], chordfn)
        if full and not last_bar:
            groove(dr, b, "D..tD.k.D..tD.kt", .25, FRAME, .75); groove(hands, b, "....c.......c...", .25, HANDS, .8)
    fe = total - 2; ps = chord("D")
    padp.chord(fe, ps[1:] + [ps[3] + 12], 4, 60); choir.chord(fe, [ps[2], ps[3], ps[3] + 12], 4, 50)
    vln.chord(fe, [note("A5"), note("D6"), note("F#6")], 4, 50, strum=.04)
    run(harp, fe, [ps[0], ps[1], ps[2], ps[3], ps[1] + 24, ps[2] + 24, ps[3] + 24], .1, 56, 4)
    for i, p_ in enumerate(["D6", "F#6", "A6", "D7"]): gl.add(fe + .25 + i * .3, p_, 3, 44)
    tim.add(fe, "D2", 3, 58); cb.add(fe, "D2", 4, 54); hn.chord(fe, ["D3", "A3"], 4, 56)
    return s


# =============================================================================================== loop sections
VAMP = {"road": ("D", "tiptoe"), "hosanna": ("D", "march"), "stones": ("D", "tiptoe"), "market": ("D", "march"),
        "prayer_house": ("D", "choir"), "argue": ("G", "hush"), "towel": ("G", "hush"), "not_my_feet": ("G", "hush"),
        "serve": ("G", "bed"), "supper": ("D", "hush"), "my_turn": ("D", "tiptoe"), "finale": ("D", "choir")}


def arp_steps(s): return (s.bpb * 2, .5) if s.bpb in (3, 4) else (s.bpb, 1.0)


def add_vamp(s, chord_name, style, need):
    """After the cadence: identical repeats of >= VAMP_MIN_SEC (whole bars, no humanising), enough of them that the file
    lasts `need` seconds plus the 2.5 s fade. Copied from music_miracles.py."""
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    reps = max(4, math.ceil((need - s.span + 2.5) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    quiet = style in ("hush", "tiptoe")
    padp = P(s, "vamp pad", SLOW_STR, -6, .5, lp=3500 if style != "hush" else 2200, **v)
    cb = P(s, "vamp bass", CBASS, -10, .3, lp=1100, **v)
    harp = P(s, "vamp harp", HARP, -8, .45, **v)
    extra = {}
    if style == "tiptoe":
        extra["pz"] = P(s, "vamp pizz", PIZZ, -6, .25, **v); extra["wb"] = P(s, "vamp blocks", DRUMS, -8, .18, **v)
    if style == "march":
        extra["dr"] = P(s, "vamp drum", DRUMS, -11, .2, lp=3200, **v); extra["pz"] = P(s, "vamp pizz", PIZZ, -8, .25, **v)
    if style == "choir":
        extra["oohs"] = P(s, "vamp oohs", OOHS, -14, .6, lp=4000, **v)
    for p_ in [padp, cb, harp] + list(extra.values()): p_.vamp = True
    ps = chord(chord_name); steps, st = arp_steps(s); b0 = s.bars * bpb
    for r in range(reps):
        b = b0 + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 34 if quiet else 46); padp.cc(b, 11, 92)
        cb.add(b, low(ps[0]), Lb + .2, 44 if quiet else 48)
        if style == "choir":
            extra["oohs"].chord(b, [ps[1] + 12, ps[3]], Lb + .3, 40); extra["oohs"].cc(b, 11, 92)
        for bar in range(nb):
            bb = b + bar * bpb
            if style in ("bed", "choir"):
                for j in range(steps): harp.add(bb + j * st, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.4, 44 if j else 50)
            if style == "hush":
                harp.add(bb, ps[[3, 2, 1, 2][bar % 4]] + 12, 3, 32); harp.add(bb + bpb / 2, ps[1] + 24, 3, 24)
            if style == "tiptoe":
                for q, idx in enumerate([0, 1, 3, 1]): extra["pz"].add(bb + q, ps[idx], .2, 50)
                for q in range(4): extra["wb"].add(bb + q + .5, HI_WOOD if q % 2 == 0 else LO_WOOD, .2, 28)
            if style == "march":
                groove(extra["dr"], bb, "D..tD.k.D..tD.k.", .25, FRAME, .6)
                for q in range(bpb): extra["pz"].add(bb + q, low(ps[0]) + (12 if q % 2 else 0), .25, 44)
                harp.add(bb, ps[3] + 12, 3, 32)
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
            if me.STEM_REPORT: print(f"    stem {p_.name:24s} rms {20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9):6.1f} dB")
        out[key] = dry + signal.fftconvolve(bus, me.IRS["hall"]())[:n]
    return out[False], out[True]


def clean_tmp():
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith(TMP_PREFIX):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def lufs_of(x):
    tmp = tempfile.mkdtemp() + "/m.wav"; wavfile.write(tmp, SR, np.asarray(x, np.float32)); return me.measure(tmp)


MUSIC = {"road": cue_road, "hosanna": cue_hosanna, "stones": cue_stones, "market": cue_market,
         "prayer_house": cue_prayer_house, "argue": cue_argue, "towel": cue_towel, "not_my_feet": cue_not_my_feet,
         "serve": cue_serve, "supper": cue_supper, "my_turn": cue_my_turn, "finale": cue_finale}
METER = {}
KEYS = {"road": "D", "hosanna": "D major", "stones": "D (G, A7 under Jesus)", "market": "D hijaz",
        "prayer_house": "D minor -> D major", "argue": "G -> squabble (D/G)", "towel": "G major",
        "not_my_feet": "G major", "serve": "G major", "supper": "D major", "my_turn": "G major -> D",
        "finale": "D major"}
CUE_NOTES = {
    "road": "Donkey clip-clop on wood blocks, light oud ostinato on a D drone, soft frame drum; recorder hints the KING theme (A-A-B); rests on the `hee_haw` beat.",
    "hosanna": "KING theme march: flute + soft trumpet, parade drum + bongos, claps, tambourine, oud strums, pizz bass; second pass adds the children's 'ah' choir and violins.",
    "stones": "Pizz tiptoe; bassoon 'hmm' (bent down) at 'grumbled'; holds still on G / A7 with harp under Jesus' line; creeps back, wood-block knocks; celesta chime answers `ding`; plink-plonk on D.",
    "market": "Fast oud bazaar tune in D hijaz, darbuka, tambourine + triangle 'clinks', pizz drone; squawky shawm honks only in the gaps between lines.",
    "prayer_house": "Firm low chord on `table_tip` (cellos, basses, horn, timpani); KING theme in D minor on horn + cello; turns tender at the golden rays: children's choir + flute sing the JESUS theme over harp.",
    "argue": "Walk upstairs in warm G (pizz, oud, pad); squabble: each speaker's own motif (James clarinet, John quick oud, Peter pompous tuba, Andrew soft low clarinet) cutting in; tuba stomp on 'doesn't count!'; sour stab, silence.",
    "towel": "SERVANT theme (Jesus theme a fourth lower, slow) on solo flute over held strings + violas; one harp note per step; held G.",
    "not_my_feet": "Pizz tiptoe; scurry + stab on 'Never!'; warm Em-C chord + harp under Jesus; bouncing pizz and slide whistle up on 'wash all of me!'; warm G resolve + harp roll on the laugh; cello SERVANT theme for Judas.",
    "serve": "SERVANT theme warmer: flute with violins joining, cello counter-line, harp arpeggios.",
    "supper": "Very still chorale D-G-Bm-A-D: harp arpeggios, soft strings, high violins breathe the JESUS theme at half speed; celesta on `heart_glow`; no drums.",
    "my_turn": "SERVANT theme bouncy and staccato on the oud, oom-pah pizz, shaker, frame drum; xylophone giggle on 'that tickles!'; lands on D.",
    "finale": "KING march (flute, soft trumpet, oud) with the SERVANT melody augmented under it (horn + cellos); second pass adds drum, claps, choir, violins; bright held D, harp roll, glock, timpani.",
}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG
place_ = lambda dst, src, at: me.place(dst, src, at)
LOOP_SECS = {"crowd_far": 8.0, "market_bustle": 10.0}      # whole-file seamless loops (CONTRACT 7)
LOOP_STOP_CUE = {"market_bustle": "argue"}                  # CONTRACT 7: stop market_bustle at S06 (= cue argue)
WRAP = 0.6


def make_loop(y, secs):
    """y is secs + WRAP long; fold the overhang onto the start so the end flows into the beginning."""
    n, k = int(secs * SR), int(WRAP * SR); out = y[:n].copy(); w = np.linspace(0, 1, k)
    out[:k] = y[:k] * np.sqrt(w) + y[n:n + k] * np.sqrt(1 - w)
    return out


def note_hz(p): return 440 * 2 ** ((note(p) - 69) / 12)


def bell(secs, *a, **kw):
    y = me.partials(secs, *a, **kw); k = min(len(y), int(.04 * SR)); y[-k:] *= np.linspace(1, 0, k); return y


def bubble(f0, secs=.12, rise=.5, amp=1.0):
    m = int(secs * SR); t = np.arange(m) / SR
    f = f0 * (1 + rise * np.minimum(1, t / (secs * .6)))
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (secs * .35)) * np.minimum(1, t / .002)


def murmur(secs, count, lp_hz, kinds=(.45, .45, .1), spread=1.0):
    """Murmured formant syllables (men, women, children), not intelligible, spread evenly over secs."""
    n = int(secs * SR); y = np.zeros(n)
    vowels = ["a", "e", "o", "u", "i", "ah", "eh"]
    for _ in range(count):
        who = R().choice(["man", "woman", "child"], p=list(kinds))
        scale = {"man": R().uniform(.92, 1.02), "woman": R().uniform(1.1, 1.2), "child": R().uniform(1.25, 1.35)}[who]
        f = {"man": R().uniform(100, 150), "woman": R().uniform(190, 250), "child": R().uniform(260, 330)}[who] * spread
        d = R().uniform(.18, .5); m = int(d * SR); tt = np.arange(m) / SR
        f0 = f * np.interp(tt, [0, d * .5, d], [1.0, R().uniform(1.02, 1.15), R().uniform(.85, .95)])
        keys = [(0, "h"), (.15, str(R().choice(vowels))), (.7, str(R().choice(vowels))), (1, "h")]
        env = np.sin(np.pi * np.clip(tt / d, 0, 1)) ** .8
        v = me.voice(d, f0, keys, scale, breath=.3, jitter=.02, vib=(5, .01), amp_env=env)
        place_(y, v / (np.std(v) + 1e-9) * R().uniform(.15, .5), R().uniform(0, secs - d))
    return me.lp(me.hp(y, 160), lp_hz)


def coin(f0=None, amp=1.0, secs=.5):
    """One small coin ping: inharmonic metal partials, quick decay."""
    f0 = f0 or R().uniform(2400, 4200)
    return bell(secs, f0, [1, 2.32, 3.86, 5.41], [1, .5, .3, .15], [R().uniform(.06, .16), .05, .03, .02], strike=.25) * amp


def sfx_crowd_far(ctx):
    """Seamless 8 s far-off festival crowd on the road (wrap-folded): ~90 murmured syllables low-passed and roomy, a few
    distant 'hey!' calls rising, faint clapping; even density so the loop never breathes."""
    secs = LOOP_SECS["crowd_far"]; tot = secs + WRAP; n = int(tot * SR)
    y = murmur(tot, 90, 1800, (.4, .4, .2))
    for _ in range(5):
        d = R().uniform(.35, .6); m = int(d * SR); tt = np.arange(m) / SR
        f0 = R().uniform(260, 380) * np.interp(tt, [0, d * .4, d], [.9, 1.2, 1.0])
        v = me.voice(d, f0, [(0, "h"), (.1, "e"), (1, "i")], 1.2, breath=.3, jitter=.02, vib=(6, .015),
                     amp_env=np.sin(np.pi * tt / d))
        place_(y, me.lp(v / (np.std(v) + 1e-9), 2200) * .25, R().uniform(0, tot - d))
    t = np.arange(n) / SR
    for _ in range(4):
        at = R().uniform(0, tot - .5); rate = R().uniform(4, 5.5)
        while at < tot - .1:
            k = int(.05 * SR); place_(y, me.bp(noise(k), 700, 2200) * me.env_exp(k, .01) * .08, at); at += 1 / rate
    y += me.lp(noise(n), 500) * .02
    y = me.room(y, "hall", .45)[:n]
    return make_loop(y, secs)


def sfx_crowd_cheer(ctx):
    """'Hosanna!': the kit cheer (music_kit.sfx_cheer), 22 'yay / wooo' voices and clapping."""
    return me.sfx_cheer()


def sfx_hee_haw(ctx):
    """A comic two-tone donkey bray, short: an airy squeaky 'hee' (inhale, ~900 Hz) and a buzzy falling 'haw' (exhale,
    ~260 -> 190 Hz, rough), 1.1 s, so the last one fits before the story ends."""
    secs = 1.1; n = int(secs * SR); y = np.zeros(n)
    d = .33; m = int(d * SR); tt = np.arange(m) / SR
    hee = me.voice(d, 880 * np.interp(tt, [0, d * .6, d], [.92, 1.05, 1.0]), [(0, "i"), (1, "i")], 1.35, breath=.55,
                   jitter=.03, vib=(9, .02), amp_env=np.minimum(1, tt / .03) * np.minimum(1, (d - tt) / .06))
    place_(y, hee / (np.std(hee) + 1e-9) * .6, .0)
    d = .58; m = int(d * SR); tt = np.arange(m) / SR
    f0 = np.interp(tt, [0, d * .3, d], [270, 250, 185]) * (1 + .04 * np.sin(2 * np.pi * 23 * tt))
    haw = me.voice(d, f0, [(0, "a"), (.6, "ah"), (1, "o")], 1.0, breath=.18, jitter=.06, vib=(7, .02),
                   amp_env=np.minimum(1, tt / .02) * np.minimum(1, (d - tt) / .12))
    place_(y, haw / (np.std(haw) + 1e-9), .36)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.12)


def sfx_ding(ctx):
    """The stones will shout: a bright little bell, D6 with a fifth above, warm partials, short shimmer."""
    secs = 1.8; n = int(secs * SR); y = np.zeros(n)
    for f, a, at in ((note_hz("D6"), 1.0, 0), (note_hz("A6"), .55, .07)):
        place_(y, bell(1.7, f, [1, 2.0, 2.76, 5.4], [1, .3, .2, .06], [.9, .5, .35, .12], strike=.15) * a, at)
    return me.fit(me.room(y, "hall", .3), secs, fade_out=.5)


def sfx_market_bustle(ctx):
    """Seamless 10 s temple market (wrap-folded): closer chatter, coin clinks, wooden crates knocked, a dove coo and a
    sheep 'baa' far back; even density. Loops until cue `argue` (S06)."""
    secs = LOOP_SECS["market_bustle"]; tot = secs + WRAP; n = int(tot * SR)
    y = murmur(tot, 110, 2600, (.45, .45, .1)) * 1.0
    for _ in range(14):
        place_(y, coin(amp=R().uniform(.08, .2), secs=.35), R().uniform(0, tot - .4))
    for _ in range(6):
        k = int(.12 * SR); tt = np.arange(k) / SR
        knock = me.resonator(np.r_[1.0, np.zeros(k - 1)] + me.bp(noise(k), 300, 1500) * np.exp(-tt / .01) * .3,
                             R().uniform(220, 420), 60)
        place_(y, knock / (np.max(np.abs(knock)) + 1e-9) * R().uniform(.15, .3), R().uniform(0, tot - .2))
    for at in (R().uniform(1, 4), R().uniform(6, 9)):          # dove coo: soft low "oo-oo"
        for j, (d, f) in enumerate(((.25, 470), (.45, 430))):
            m = int(d * SR); tt = np.arange(m) / SR
            co = np.sin(2 * np.pi * np.cumsum(f * (1 + .06 * np.sin(np.pi * tt / d))) / SR) * np.sin(np.pi * tt / d) ** 2
            place_(y, me.lp(co, 900) * .12, at + j * .32)
    d = .7; m = int(d * SR); tt = np.arange(m) / SR                 # a sheep, far back
    baa = me.voice(d, 330 * (1 + .05 * np.sin(2 * np.pi * 7 * tt)), [(0, "e"), (.3, "a"), (1, "a")], 1.15, breath=.3,
                   jitter=.04, vib=(7, .04), amp_env=np.sin(np.pi * tt / d) ** .7)
    place_(y, me.lp(baa / (np.std(baa) + 1e-9), 2200) * .12, R().uniform(3, 7))
    y = me.room(y, "room", .3)[:n]
    return make_loop(y, secs)


def sfx_coins_clink(ctx):
    """A few coins counted into a hand: five small clinks, slightly uneven, 1.1 s."""
    secs = 1.1; n = int(secs * SR); y = np.zeros(n)
    at = .02
    for i in range(5):
        place_(y, coin(amp=R().uniform(.6, 1.0)), at); at += R().uniform(.12, .2)
    return me.fit(me.room(y, "room", .12), secs, fade_out=.2)


def sfx_table_tip(ctx):
    """A market table tipped over: a short wooden creak, a heavy round wooden thud with a small bounce, a rattle of
    crates; round and comic-big, not scary. 1.8 s."""
    secs = 1.8; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    m = int(.28 * SR); tt = np.arange(m) / SR
    ph = np.cumsum(np.interp(tt, [0, .28], [35, 70])) / SR; pulses = np.zeros(m)
    idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]; pulses[idx] = R().uniform(.6, 1.0, len(idx))
    cr = sum(me.resonator(pulses, fr, bw) * g for fr, bw, g in ((420, 40, 1.0), (900, 60, .6)))
    place_(y, cr / (np.max(np.abs(cr)) + 1e-9) * .35 * np.sin(np.pi * np.clip(np.arange(len(cr)) / m, 0, 1)), 0.0)
    for at, amp in ((.3, 1.0), (.52, .45)):
        k = int(.5 * SR); tk = np.arange(k) / SR
        th = np.sin(2 * np.pi * (85 + 70 * np.exp(-tk / .025)) * tk) * np.exp(-tk / .11)
        th += me.bp(noise(k), 160, 1100) * np.exp(-tk / .05) * .7
        th += me.resonator(me.bp(noise(k), 200, 900) * np.exp(-tk / .02), 260, 40) * .02
        place_(y, th * amp * np.minimum(1, tk / .002), at)
    for _ in range(9):
        k = int(.08 * SR); place_(y, me.bp(noise(k), 500, 2500) * me.env_exp(k, .015) * R().uniform(.1, .3), R().uniform(.35, 1.0))
    return me.fit(me.room(y, "room", .22), secs, fade_out=.4)


def sfx_coins_scatter(ctx):
    """Coins pouring off the table: ~40 pings and bounces thinning out, two coins rolling and settling (a wobble that
    speeds up and stops). 2.8 s."""
    secs = 2.8; n = int(secs * SR); y = np.zeros(n)
    for i in range(40):
        at = R().exponential(.35)
        if at > secs - .5: continue
        place_(y, coin(amp=R().uniform(.3, 1.0) * np.exp(-at / 1.2), secs=.4), at)
        if R().uniform() < .5: place_(y, coin(amp=R().uniform(.1, .3), secs=.3), at + R().uniform(.06, .15))
    for st, d in ((.6, 1.9), (.9, 1.5)):                           # rolling, settling coins
        m = int(d * SR); tt = np.arange(m) / SR
        rate = 6 + 30 * (tt / d) ** 2; ph = np.cumsum(rate) / SR
        am = (.5 + .5 * np.sin(2 * np.pi * ph)) ** 4 * np.exp(-tt / (d * .6)) * np.minimum(1, (d - tt) / .05)
        ring = sum(np.sin(2 * np.pi * f * tt) * a for f, a in ((R().uniform(3000, 3800), 1.0), (6100, .3)))
        place_(y, ring * am * .25, st)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.4)


def sfx_dove_flutter(ctx):
    """Doves fly off: four birds, each a burst of wing claps (soft band-passed pulses at 9-12 per second), staggered,
    the flapping fading away. 2.4 s."""
    secs = 2.4; n = int(secs * SR); y = np.zeros(n)
    for b in range(4):
        at = .02 + b * R().uniform(.08, .18); d = R().uniform(1.1, 1.7); rate = R().uniform(9, 12); f = R().uniform(700, 1300)
        q = at
        while q < at + d and q < secs - .05:
            k = int(.035 * SR); tk = np.arange(k) / SR
            fl = me.bp(noise(k), f * .5, f * 3.0) * np.sin(np.pi * tk / (k / SR)) ** 2
            fade = np.exp(-(q - at) / (d * .55))
            place_(y, fl * fade * R().uniform(.6, 1.0), q); q += 1 / rate * R().uniform(.9, 1.1)
    return me.fit(me.room(y, "room", .25), secs, fade_out=.4)


def sfx_water_pour(ctx):
    """Water poured from a jug into a bowl: a soft stream with bubbles whose pitch rises as the bowl fills, a last few
    drips. 3.0 s."""
    secs = 3.0; n = int(secs * SR); t = np.arange(n) / SR
    env = np.minimum(1, t / .2) * np.clip((2.4 - t) / .4, 0, 1)
    y = me.bp(noise(n), 400, 3500) * (.6 + .4 * me.smooth_rand(n, 8)) * env * .12
    q = .1
    while q < 2.4:
        f = 500 + 600 * q / 2.4
        place_(y, bubble(f * R().uniform(.85, 1.2), R().uniform(.03, .07), .5, R().uniform(.2, .45)), q); q += R().uniform(.02, .06)
    for at in (2.55, 2.8):
        place_(y, bubble(R().uniform(1300, 1800), .05, .4, .25), at)
    return me.fit(me.room(y, "room", .2), secs, fade_out=.3)


def sfx_splash_small(ctx):
    """Feet into a bowl of water: a small splash burst, a few bubbles, a drip. 0.9 s."""
    secs = .9; n = int(secs * SR); t = np.arange(n) / SR
    y = me.bp(noise(n), 500, 5000) * np.exp(-t / .07) * np.minimum(1, t / .004) * .6
    for _ in range(7):
        place_(y, bubble(R().uniform(600, 1500), R().uniform(.03, .07), .5, R().uniform(.15, .35)), R().uniform(.02, .35))
    place_(y, bubble(1700, .05, .4, .2), .6)
    return me.fit(me.room(y, "room", .18), secs, fade_out=.15)


SFX = {"crowd_far": sfx_crowd_far, "crowd_cheer": sfx_crowd_cheer, "hee_haw": sfx_hee_haw, "ding": sfx_ding,
       "market_bustle": sfx_market_bustle, "coins_clink": sfx_coins_clink, "table_tip": sfx_table_tip,
       "coins_scatter": sfx_coins_scatter, "dove_flutter": sfx_dove_flutter, "water_pour": sfx_water_pour,
       "splash_small": sfx_splash_small}
SFX_SEED = {}
SFX_GAIN = {"crowd_far": -20, "crowd_cheer": -15, "hee_haw": -10, "ding": -16, "market_bustle": -21,
            "coins_clink": -14, "table_tip": -10, "coins_scatter": -13, "dove_flutter": -14, "water_pour": -17,
            "splash_small": -14}
SFX_SHAPE = {"ding": (0.6, 0.5), "crowd_cheer": (1.2, 0.8), "coins_scatter": (1.0, 0.9)}
SFX_NOTES = {
    "crowd_far": "seamless 8 s far-off festival crowd (wrap-folded): ~90 murmured syllables, distant 'hey!' calls, faint clapping, hall",
    "crowd_cheer": "kit cheer (music_kit.sfx_cheer): 22 'yay / wooo' voices and clapping, shaped short",
    "hee_haw": "comic two-tone bray: airy 'hee' (~880 Hz) + buzzy falling 'haw' (270 -> 185 Hz); 1.1 s (the last one sits 1.2 s before the end)",
    "ding": "bright little bell D6 + A6, warm partials; 1.8 s",
    "market_bustle": "seamless 10 s market (wrap-folded): chatter, coin clinks, crate knocks, two dove coos, a far sheep",
    "coins_clink": "five small coin clinks into a hand; 1.1 s",
    "table_tip": "short wood creak, round heavy thud + bounce (85 Hz body, 160-1100 Hz knock), crate rattle; 1.8 s",
    "coins_scatter": "~40 coin pings thinning out, two coins rolling and settling; 2.8 s",
    "dove_flutter": "four doves' wing claps (9-12 /s, band-passed), staggered, fading away; 2.4 s",
    "water_pour": "stream + bubbles rising in pitch as the bowl fills, two drips; 3.0 s",
    "splash_small": "small splash burst, bubbles, a drip; 0.9 s",
}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3), secs=round(end - c["t"] + XFADE, 3),
                        last=i + 1 == len(cues)))
    return out


def max_spans(tls):
    """Longest section of each cue over several timelines (zh play, en play, base timeline)."""
    out = {}
    for tl in tls:
        for c in cue_spans(tl): out[c["cue"]] = max(out.get(c["cue"], 0), c["span"])
    return out


def render_cue(tl, name, c, need):
    me.seed(f"{SID}/" + name); ctx = Ctx(tl, name, c["t"], c["span"], c["secs"], c["last"])
    sc = MUSIC[name](ctx)
    add_vamp(sc, *VAMP[name], need); vp = sc.vamp
    main, vamp = render_split(sc)
    main = me.hp(me.fit(main, sc.secs, fade_out=0), 45); vamp = me.hp(me.fit(vamp, sc.secs, fade_out=0), 45)
    main, vamp = mp.pocket(main), mp.pocket(vamp)                         # speech pocket (900 Hz, 2.4 kHz)
    hits = [t - c["t"] for kind, ids in (("sfx", HIT_SFX), ("fx", HIT_FX)) for e in tl[kind] if e["id"] in ids
            and (name, e["id"]) not in NO_SWELL for t in [e["t"]] if 0 <= t - c["t"] <= c["span"]]
    for lid in AFTER_LINE.get(name, []):
        l = next((l for l in tl["lines"] if l["id"] == lid), None)
        if l and 0 <= l["t"] + l["clip"] - c["t"] <= c["span"]: hits.append(l["t"] + l["clip"] - c["t"] + .5)
    end_at = None
    if name in END_SWELL: end_at = sc.sec(sc.bars * sc.bpb - 2)           # the final chord (2 beats before the span end)
    main = main * mp.underscore(len(main), hits, end_at=end_at)   # breathe under the story, swell on the hits
    if name in DIPS: main = main * mp.dips(len(main), DIPS[name])
    if c["t"] > 0.5: kf = int(.3 * SR); main[:kf] *= np.linspace(0, 1, kf) ** 1.5
    n = len(main)
    ns, ls, le = int(c["span"] * SR), int(round((vp["start"] + vp["secs"]) * SR)), int(round((vp["start"] + 2 * vp["secs"]) * SR))
    L = le - ls; kx = int(.03 * SR); w = np.linspace(0, 1, kx)
    T = vamp[ls:le].copy(); T[:kx] = vamp[le:le + kx] * (1 - w) + vamp[ls:ls + kx] * w
    vs = np.zeros(n); p0 = ls - L
    for j in range(0, (n - p0) // L + 1):
        q = p0 + j * L; m_ = min(L, n - q)
        if m_ > 0: vs[q:q + m_] = T[:m_]
    kf = int(.5 * SR); main[ls - kf:ls] *= np.linspace(1, 0, kf) ** 2; main[ls:] = 0
    target = CUE_LUFS.get(name, SPAN_LUFS)
    gm = target - lufs_of(main[:ns])["lufs"]
    gv = target + VAMP_REL_DB - lufs_of(T)["lufs"]
    for _ in range(3):
        x = main * 10 ** (gm / 20) + vs * 10 ** (gv / 20)
        if lufs_of(x)["truePeak"] <= -1.3: break
        cl = 10 ** (-1.6 / 20); x = np.tanh(x / cl) * cl
        err = target - lufs_of(x[:ns])["lufs"]
        if abs(err) < .1: break
        gm += err
    k = int(2.5 * SR); x[-k:] *= np.linspace(1, 0, k) ** 2
    path = f"{MUSIC_DIR}/{name}.wav"; me.write_wav(path, x); m = me.measure(path)
    m_span, m_loop = lufs_of(x[:ns]), lufs_of(x[ls:le])
    r = dict(secs=round(len(x) / SR, 3), loopStart=round(ls / SR, 6), loopEnd=round(le / SR, 6), loopStartSample=ls,
             loopEndSample=le, loopFromSec=round(vp["start"], 3), key=KEYS[name], meter=METER.get(name, "4/4"),
             bars=sc.bars, bpm=round(sc.bpm, 1), loopBars=vp["bars"], loopChord=vp["chord"],
             lufs=round(m_span["lufs"], 1), loopLufs=round(m_loop["lufs"], 1), truePeak=round(m["truePeak"], 1),
             samplePeak=round(m["samplePeak"], 1), composedFor=c["t"], composedSpan=c["span"])
    r.update(loop_check(x, ls, le))
    clean_tmp()
    return r


def loop_check(x, ls, le):
    """seamRatio: largest sample step across the join vs largest inside the loop (<= 1: join no rougher than the music);
    repeatDb: level difference between the first two repeats; ticks: steps over 8x the local 10 ms RMS step."""
    L = le - ls; seam = np.concatenate([x[le - 64:le], x[ls:ls + 64]]); sd = np.abs(np.diff(seam)); inner = np.abs(np.diff(x[ls:le]))
    rep = [x[ls:le], x[le:le + L]]
    rms = lambda a: 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12)
    d = np.abs(np.diff(x[ls + 100:le + 2000])); k = 441; loc = np.sqrt(np.convolve(d ** 2, np.ones(k) / k, "same")) + 1e-6
    return dict(seamRatio=round(float(sd.max() / (inner.max() + 1e-12)), 3), repeatDb=round(float(rms(rep[1]) - rms(rep[0])), 3),
                ticks=int(np.sum(d > 8 * loc + 0.01)))


def build_music(tl, longest, only=None):
    spans = cue_spans(tl)
    missing = sorted({c["cue"] for c in spans} - set(MUSIC)); assert not missing, f"no composer for cue(s) {missing}"
    path_json = f"{MUSIC_DIR}/cues.json"
    old = {}
    if only and os.path.exists(path_json):
        for e in json.load(open(path_json))["cues"]: old.setdefault(e["cue"], e)
    rendered = {}
    for c in spans:
        name = c["cue"]; need = longest[name] * (1 + STRETCH) + XFADE
        if only and name not in only and name in old: rendered[name] = dict(old[name]); continue
        rendered[name] = render_cue(tl, name, c, need); r = rendered[name]
        print(f"music {name:12s} t={c['t']:7.2f} span={c['span']:6.2f} (longest {longest[name]:6.2f}) file={r['secs']:6.2f}s "
              f"bars={r['bars']:2d} bpm={r['bpm']:5.1f} span I={r['lufs']:6.1f} loop I={r['loopLufs']:6.1f} "
              f"TP={r['truePeak']:5.1f} seam x{r['seamRatio']} repeat {r['repeatDb']:+.2f} dB ticks {r['ticks']}")
    manifest = []
    for c in spans:
        r = rendered[c["cue"]]; need = longest[c["cue"]] * (1 + STRETCH) + XFADE
        assert r["secs"] + 1e-3 >= need, f"{c['cue']} at t={c['t']} is {r['secs']}s, needs {need}s"
        e = dict(cue=c["cue"], t=c["t"], span=c["span"], longestSpan=longest[c["cue"]], secs=r["secs"], lastCue=c["last"], loop=False)
        for k in ("loopStart", "loopEnd", "loopStartSample", "loopEndSample", "loopFromSec", "key", "meter", "bars",
                  "bpm", "loopBars", "loopChord", "lufs", "loopLufs", "truePeak", "samplePeak", "composedFor",
                  "composedSpan", "seamRatio", "repeatDb", "ticks"):
            e[k] = r[k]
        e["plainTailSec"] = round(r["secs"] - c["span"], 3)
        manifest.append(e)
    json.dump(dict(rule="Start each cue at its timeline t at full level and fade the previous cue out over 0.6 s from "
                        "that t. Each cue is composed for its section in the zh play (composedSpan) and ends on its "
                        "cadence at loopFromSec; after it the cue continues into a quiet loop section on its final "
                        "chord. If the section is longer (en play, longer clips), either loop [loopStart, loopEnd) "
                        "seamlessly (seconds, sample-accurate) until the next cue, or just keep playing: every file is "
                        "at least longestSpan x 1.3 + 0.6 s and fades out over its last 2.5 s. The composed span sits "
                        "at -20 LUFS (+-1), the loop section ~4.5 dB under it. Duck music ~7 dB under voice lines. "
                        "Rerun tools/story/music_lastsupper.py after the timeline is re-timed so the in-cue hits follow.",
                   crossfadeSec=XFADE, lufs=MUSIC_LUFS, stretchCovered=STRETCH, cues=manifest),
              open(path_json, "w"), indent=1, ensure_ascii=False)
    return manifest


def loop_stop(tl, sid):
    if sid in LOOP_STOP_CUE: return LOOP_STOP_CUE[sid]
    t0 = min(e["t"] for e in tl["sfx"] if e["id"] == sid)
    nxt = [m for m in sorted(tl["music"], key=lambda m: m["t"]) if m["t"] > t0 + 1.0]
    return nxt[0]["cue"] if nxt else None


def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]}); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in needed:
        me.seed(SFX_SEED.get(sid, f"{SID}/" + sid))
        t0 = min(s["t"] for s in tl["sfx"] if s["id"] == sid)
        x = me.hp(np.asarray(SFX[sid](dict(tl=tl, t=t0)), np.float64), 30)
        if sid in SFX_SHAPE: x = mp.sfx_shape(x, *SFX_SHAPE[sid])
        x = me.peak_normalize(x, SFX_PEAK_DB); path = f"{SFX_DIR}/{sid}.wav"; me.write_wav(path, x); m = me.measure(path)
        loop = sid in LOOP_SECS
        e = dict(id=sid, secs=round(len(x) / SR, 3), loop=loop, gainDb=SFX_GAIN[sid],
                 samplePeak=round(m["samplePeak"], 1), truePeak=round(m["truePeak"], 1),
                 lufs=None if m["lufs"] == float("-inf") else round(m["lufs"], 1))
        if loop:
            e.update(loopStart=0.0, loopEnd=e["secs"], stopAtCue=loop_stop(tl, sid), fadeInSec=1.0, fadeOutSec=1.5)
            sd = np.abs(np.diff(np.concatenate([x[-64:], x[:64]]))); inner = np.abs(np.diff(x[64:-64]))
            h = len(x) // 2; rms = lambda a: 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12)
            e.update(seamRatio=round(float(sd.max() / inner.max()), 3), halfDb=round(float(rms(x[h:2 * h]) - rms(x[:h])), 2))
        manifest.append(e); clean_tmp()
        print(f"sfx   {sid:14s} {e['secs']:6.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f}"
              + (f" loop, stop at cue {e['stopAtCue']}, seam x{e['seamRatio']}, halves {e['halfDb']:+.2f} dB" if loop else ""))
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play each one-shot at its timeline t with gainDb "
                        "(recommended mix level). Entries with loop: true are ambience beds: the whole file is a "
                        "seamless loop (loopStart 0, loopEnd = secs); start it at its t and loop it until the music "
                        "cue named in stopAtCue starts (fade out over fadeOutSec). crowd_far stops at hosanna; "
                        "market_bustle stops at argue (= shot S06, CONTRACT 7).",
                   peakDbfs=SFX_PEAK_DB, sfx=manifest), open(f"{SFX_DIR}/mix.json", "w"), indent=1, ensure_ascii=False)
    return manifest


def build_preview(tl):
    """Offline mix of the Chinese play as StoryDirector.cs mixes it (tools/story/voice_margin.py)."""
    mix = vm.engine_mix(SID, tl, "zh", MUSIC_DIR, SFX_DIR); rows = vm.table(tl, mix)
    out = (mix["voice"] + mix["music"] + mix["sfx"]).astype(np.float32)
    tmp = tempfile.mkdtemp() + "/mix.wav"; wavfile.write(tmp, SR, out)
    me.run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", "alimiter=limit=0.89:level=false",
            "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "96k", PREVIEW])
    m = me.measure(PREVIEW); clean_tmp()
    med, worst = vm.summary(rows)
    print(f"preview {me.probe_secs(PREVIEW):.2f}s I={m['lufs']:.1f} LUFS TP={m['truePeak']:.1f} dBTP, "
          f"zh voice clips included: {len(tl['lines'])}/{len(tl['lines'])}; voice over bed: median {med:.1f} dB, worst {worst}")
    return dict(secs=round(me.probe_secs(PREVIEW), 2), lufs=round(m["lufs"], 1), truePeak=round(m["truePeak"], 1),
                voices=len(tl["lines"]), lines=len(tl["lines"]), rows=rows)


def spectrograms(outdir):
    os.makedirs(outdir, exist_ok=True)
    for d in (MUSIC_DIR, SFX_DIR):
        for f in sorted(os.listdir(d)):
            if f.endswith(".wav"):
                me.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{d}/{f}", "-lavfi",
                        "showspectrumpic=s=1400x360:legend=0:scale=log:fscale=log:gain=3", f"{outdir}/{f[:-4]}.png"])
    print(f"spectrograms in {outdir}")


HIT_ROWS_SFX = {"hee_haw", "crowd_cheer", "ding", "table_tip", "dove_flutter", "water_pour"}
HIT_ROWS_FX = {"golden_rays", "heart_glow"}


def hit_rows(tl):
    """Where each event the music answers lands inside its cue in the zh play and in the en play (same cue file, so the en
    offset is how far it drifts from the composed moment)."""
    en = vm.lang_timeline(SID, "en"); rows = []
    def rel(T, e):
        cs = sorted(T["music"], key=lambda c: c["t"]); c = [c for c in cs if c["t"] <= e["t"] + 1e-6][-1]
        return c["cue"], e["t"] - c["t"]
    for k in ("sfx", "fx"):
        for e in tl[k]:
            if e["id"] not in (HIT_ROWS_SFX if k == "sfx" else HIT_ROWS_FX): continue
            m = [x for x in en[k] if x["id"] == e["id"] and abs(x["anchor"]["dt"] - e["anchor"]["dt"]) < 1e-6 and x["anchor"]["line"] == e["anchor"]["line"]]
            c, r = rel(tl, e); r_en = rel(en, m[0])[1] if m else None
            rows.append((c, e["id"], k, r, r_en))
    return rows


def update_doc(tl, cues, sfx, prev):
    if not os.path.exists(DOC): return
    txt = open(DOC).read()
    def swap(tag, body):
        nonlocal txt
        txt = re.sub(rf"(<!-- {tag}:start -->\n).*?(<!-- {tag}:end -->)", lambda m: m.group(1) + body + m.group(2), txt, flags=re.S)
    if cues:
        rows = ["| Cue | t zh (s) | Span zh (s) | Longest span (s) | File (s) | Loop (s) | Key | Bars × bpm | LUFS span / loop | TP (dBTP) | Content |",
                "|---|---|---|---|---|---|---|---|---|---|---|"]
        for c in cues:
            rows.append(f"| `{c['cue']}` | {c['t']:.2f} | {c['span']:.2f} | {c['longestSpan']:.2f} | {c['secs']:.2f} | {c['loopStart']:.2f}–{c['loopEnd']:.2f} "
                        f"({c['loopBars']} bar{'s' if c['loopBars'] > 1 else ''} on {c['loopChord']}) "
                        f"| {c['key']} | {c['bars']} × {c['bpm']} ({c['meter']}) | {c['lufs']:.1f} / {c['loopLufs']:.1f} "
                        f"| {c['truePeak']:.1f} | {CUE_NOTES[c['cue']]} |")
        swap("cues", "\n".join(rows) + "\n")
        rows = ["| Cue | Loop seam (step across join / largest step inside) | Level, repeat 2 vs 1 (dB) | Click-like steps in the loop | File ≥ 1.3 × longest span + 0.6 s | Sample peak (dBFS) |",
                "|---|---|---|---|---|---|"]
        for c in cues:
            need = c["longestSpan"] * (1 + STRETCH) + XFADE
            rows.append(f"| `{c['cue']}` | x{c['seamRatio']} | {c['repeatDb']:+.2f} | {c['ticks']} | {c['secs']:.1f} ≥ {need:.1f} | {c['samplePeak']:.1f} |")
        swap("checks", "\n".join(rows) + "\n")
    if sfx:
        rows = ["| Id | Length (s) | Loop | Sample peak (dBFS) | True peak (dBTP) | LUFS | gainDb | Notes |", "|---|---|---|---|---|---|---|---|"]
        for s in sfx:
            lp_ = f"whole file (seam x{s['seamRatio']}, halves {s['halfDb']:+.2f} dB), stop at `{s['stopAtCue']}`" if s["loop"] else "one-shot"
            rows.append(f"| `{s['id']}` | {s['secs']:.2f} | {lp_} | {s['samplePeak']:.1f} | {s['truePeak']:.1f} | "
                        f"{s['lufs'] if s['lufs'] is not None else 'n/a'} | {s['gainDb']} | {SFX_NOTES[s['id']]} |")
        swap("sfx", "\n".join(rows) + "\n")
    if prev:
        swap("preview", f"Last run: {prev['secs']} s, {prev['lufs']} LUFS, {prev['truePeak']} dBTP; zh voice clips "
                        f"present: {prev['voices']}/{prev['lines']}; timeline `timedFrom`: {tl.get('timedFrom')}.\n")
        if prev.get("rows"):
            a = np.array([r["vs_bed"] for r in prev["rows"]]); w = sorted(prev["rows"], key=lambda r: r["vs_bed"])[:3]
            rows = ["| Line | Who | t zh (s) | Voice over bed (dB) | over music | over SFX |", "|---|---|---|---|---|---|"]
            rows += [f"| {r['id']} | {r['who']} | {r['t']:.1f} | {r['vs_bed']:.1f} | {r['vs_mus']:.1f} | {min(r['vs_sfx'], 99):.0f} |" for r in prev["rows"]]
            rows.append(f"| **median** | | | **{np.median(a):.1f}** | | |")
            rows.append("| **worst 3** | | | **" + ", ".join(f"{r['id']} {r['vs_bed']:.1f}" for r in w) + "** | | |")
            swap("margin", "\n".join(rows) + "\n")
    hr = hit_rows(tl)
    if hr:
        rows = ["| Cue | Event | In-cue time zh (composed for) | en play | Drift (s) |", "|---|---|---|---|---|"]
        rows += [f"| `{c}` | {k} `{i}` | {r:.2f} | {('%.2f' % e) if e is not None else 'n/a'} | {('%+.1f' % (e - r)) if e is not None else ''} |"
                 for c, i, k, r, e in hr]
        swap("hits", "\n".join(rows) + "\n")
    open(DOC, "w").write(txt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-music", action="store_true"); ap.add_argument("--skip-sfx", action="store_true")
    ap.add_argument("--skip-preview", action="store_true"); ap.add_argument("--only", default="")
    ap.add_argument("--stems", action="store_true", help="print per-stem levels while rendering")
    ap.add_argument("--tmp", default=f"/tmp/{SID}_music", help="scratch dir (emptied per cue, removed at exit)")
    ap.add_argument("--spec", default="", help="also write spectrogram PNGs of every output into this dir")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    os.makedirs(a.tmp, exist_ok=True)
    tempfile.tempdir = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=a.tmp)
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    os.makedirs(MUSIC_DIR, exist_ok=True); os.makedirs(SFX_DIR, exist_ok=True)
    tl = vm.lang_timeline(SID, "zh")          # the play as the phone runs it in Chinese (re-timed to the zh clips)
    longest = max_spans([tl, vm.lang_timeline(SID, "en"), json.load(open(f"{LS}/timeline.json"))])
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, longest, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
    if a.spec: spectrograms(a.spec)
