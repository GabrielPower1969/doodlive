#!/usr/bin/env python3
"""Original score and sound effects for "He Is Risen!" (story pack `risen`; docs/risen/CONTRACT.md section 7,
docs/risen/DESIGN.md section 5, docs/risen/MUSIC.md).

Built on the shared engine tools/story/music_kit.py (`import music_kit as me`) and the finishing helpers in
tools/story/music_polish.py; the loop-section / build machinery is copied from music_lastsupper.py (same shape, same
cues.json / mix.json format). This script holds only this pack's cues, effects, paths and tables.

The warm acoustic band of the Jesus packs: oud (GM nylon guitar, low-passed), flute, harp, strings, cello, frame drum,
a children's "ah" choir; plus pizzicato, tuba, slide whistle, clarinet, celesta and wood blocks for the comic and
the hushed moments. Two themes, one melody:
  * the JESUS theme is imported from music_miracles.py (JESUS, JESUS_HARM), so Real Miracles, The King Who Serves and
    this pack share one Jesus theme. Here it is the MORNING theme (the resurrection): risen, mary, thomas, finale.
  * the PROMISE figure is that theme's opening (A-B-D, then E): sad and unanswered on solo flute in sad_day, a hint
    in dawn, in minor on the cello (garden_tears) and clarinet (thomas), answered (E -> D) in empty.
Every melody is original; nothing is taken from any film.

Every name and time comes from the timeline, read on every run: the cues are composed for the play as the phone runs
it in Chinese (voice_margin.lang_timeline, re-timed to the installed zh clips; the shortest play, so no cadence is cut
off), in-cue hits are looked up by line id / sfx / fx events. Every file is long enough for its section in the zh play,
the en play and assets/risen/timeline.json x 1.3 + 0.6 s, and after its cadence continues into a quiet loop section
with sample-exact loop points in cues.json. All sound effects are one-shots sized to their scene (StoryDirector
stops loops only at a music cue). Rerun after re-timing.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/risen/audio/music/<cue>.wav|.mp3   music, -20 LUFS (+-1) over the composed span, true peak <= -1 dBTP
  assets/risen/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/risen/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/risen/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain
  assets/risen/audio/preview_mix.mp3        full-length mix of the zh play as the engine mixes it
  docs/risen/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_risen.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--tmp DIR] [--spec DIR]   (scratch default /tmp/risen_music; --spec writes spectrogram PNGs)
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

SID = "risen"
ROOT = me.ROOT
LS = f"{ROOT}/assets/{SID}"
MUSIC_DIR, SFX_DIR = f"{LS}/audio/music", f"{LS}/audio/sfx"
PREVIEW = f"{LS}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/{SID}/MUSIC.md"
STRETCH = 0.30                 # every file covers its longest section (zh / en / base timeline) x 1.3 + 0.6 s
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -4.5             # loop section loudness relative to the cue's composed span
SPAN_LUFS = -20.5              # composed span loudness (contract -20 +-1)
# a little range inside the contract's +-1 LU: the cross and the tears sit lower, the race, Mary and the finale higher
CUE_LUFS = {"sad_day": -21.0, "garden_tears": -21.0, "empty": -20.9, "race": -19.8, "mary": -20.0, "finale": -20.0}
HIT_SFX = {"stone_roll", "sparkle_up"}   # hits clear of speech in the zh play: the stone (before the narrator), "It's You!"
HIT_FX = set()
NO_SWELL = {("finale", "sparkle_up")}    # the last sparkle sits on the finale's end swell already
AFTER_LINE = {}
END_SWELL = {"finale"}         # the last cue swells back up on its final chord
# extra dips under lines the score cannot get out of the way of: cue -> [(line id, dB)], resolved from the zh play
# on every run (the line's start - 0.2 s to its end + 0.2 s, in file seconds)
DIPS = {"news": [("rs_15", -2.0)], "empty": [("rs_21", -3.0)], "thomas": [("rs_35", -3.0), ("rs_37", -3.0)]}
WHO_LINES = None
TMP_PREFIX = "music_risen_"

# extra GM programs (0-based)
VIOLA, WHISTLE = 41, 78
OUD = NYLON

CH = dict(me.CH)
CH.update({"D": ["D3", "A3", "D4", "F#4"], "Dadd9": ["D3", "A3", "E4", "F#4"], "Dm": ["D3", "A3", "D4", "F4"],
           "G": ["G2", "D3", "G3", "B3"], "Gadd9": ["G2", "D3", "A3", "B3"], "A": ["A2", "E3", "A3", "C#4"],
           "A7": ["A2", "E3", "G3", "C#4"], "Asus": ["A2", "E3", "A3", "D4"], "Bm": ["B2", "F#3", "B3", "D4"],
           "Em": ["E2", "B2", "E3", "G3"], "C": ["C3", "G3", "C4", "E4"], "Am": ["A2", "E3", "A3", "C4"],
           "D7": ["D3", "A3", "C4", "F#4"], "Bb": ["Bb2", "F3", "Bb3", "D4"], "Gm": ["G2", "D3", "G3", "Bb3"],
           "F": ["F2", "C3", "F3", "A3"], "Ebdim": ["Eb3", "A3", "C4", "F#4"], "Dsus": ["D3", "A3", "D4", "G4"],
           "F#": ["F#2", "C#3", "F#3", "A#3"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def nm(m): return f"{NAMES[m % 12]}{m // 12 - 1}"


# =============================================================================================== the themes
# The PROMISE figure is the opening of the shared JESUS theme (A-B-D, then E): a rising 4-note figure, first heard
# slow and unanswered on solo flute in sad_day; in minor (b6) on the cello in garden_tears and the clarinet in thomas;
# answered (E -> D) in empty. The MORNING theme is the JESUS theme itself (music_miracles.py), bright and full:
# risen, mary, thomas (slow), finale (all 8 bars).
PROMISE = [("A4", 2), ("B4", 1), ("D5", 1), ("E5", 4)]


def promise(shift=0, scale=1.0, minor=False, answer=False, last=None):
    """The promise figure; minor flattens the 6th (B -> Bb); answer = E then D (resolved); last = length of the last
    note in beats (before scaling)."""
    notes = PROMISE[:3] + ([("E5", 3), ("D5", 1)] if answer else [("E5", 4)])
    if last is not None: notes[-1] = (notes[-1][0], last)
    out = []
    for p, d in notes:
        m = note(p) + shift - (1 if minor and p.startswith("B") else 0)
        out.append((nm(m), d * scale))
    return out


def jesus(bars, shift=0, scale=1.0, stacc=False):
    out = []
    for k in bars: out += [(nm(note(p) + shift) + ("." if stacc else ""), d * scale) for p, d in JESUS[k]]
    return out


def harm(b0, harmd, bars, fn, scale=1.0):
    """Call fn(beat, chord, beats) for each chord of the given bars of a harmony table."""
    b = b0
    for k in bars:
        for name, d in harmd[k]: fn(b, name, d * scale); b += d * scale
    return b


def segs(b0, items, fn):
    """Call fn(beat, chord, beats) for a list of (chord, beats)."""
    b = b0
    for name, d in items:
        if d > 0: fn(b, name, d)
        b += d
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


def speech(c):
    """(t0, t1) of every line that sounds inside the cue span (absolute zh times)."""
    return sorted((l["t"], l["t"] + l["clip"]) for l in c.tl["lines"] if l["t"] < c.t + c.span and l["t"] + l["clip"] > c.t)


def gaps(s, c, min_sec=.35):
    """Speech-free windows inside the cue span, as (beat0, beat1)."""
    out = []; cur = c.t
    for a, b in speech(c):
        if a - cur >= min_sec: out.append((s.beat(cur - c.t), s.beat(a - c.t)))
        cur = max(cur, b)
    if c.t + c.span - cur >= min_sec: out.append((s.beat(cur - c.t), s.beat(c.span)))
    return out


def clip_pauses(c, lid, min_sec=.22):
    """Absolute (t0, t1) of the silent pauses inside a line's zh clip (20 ms RMS 35 dB under the loudest frame)."""
    l = next((l for l in c.tl["lines"] if l["id"] == lid), None)
    p = f"{LS}/audio/voice/zh/{lid}.wav"
    if l is None or not os.path.exists(p): return []
    x = vm.load(p); h = int(.02 * SR); k = len(x) // h
    db = 20 * np.log10(np.sqrt(np.mean(x[:k * h].reshape(k, h) ** 2, 1)) + 1e-9); q = db < db.max() - 35
    voiced = np.nonzero(~q)[0]
    if len(voiced) == 0: return []
    out = []; i = voiced[0]
    while i < voiced[-1]:
        if q[i]:
            j = i
            while j < voiced[-1] and q[j]: j += 1
            if (j - i) * .02 >= min_sec: out.append((l["t"] + i * .02, l["t"] + j * .02))
            i = j
        else: i += 1
    return out


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- sad_day
SAD_HARM = ["Dm", "Bb", "Gm", "A", "Dm", "Bb", "Gm", "A"]


def cue_sad_day(c):
    """The cross at dusk, gentle and short: low strings and a slow harp (one note a beat) in D minor (Dm Bb Gm A), a
    soft cello under the narrator; for "But Jesus had made a promise" the harmony lifts to G and the solo flute plays
    the PROMISE figure (A-B-D... E), left hanging on Asus. No drums, nothing low and heavy."""
    s = Score(c, 60, 4); n = s.bars; total = n * 4
    vc = P(s, "cello", CELLO, -7, .45, lp=2600, human=.006)
    padp = P(s, "low strings", SLOW_STR, -7, .55, lp=2400)
    cb = P(s, "basses", CBASS, -14, .4, lp=900)
    harp = P(s, "harp", HARP, -7, .5)
    fl = P(s, "flute (promise)", FLUTE, -8, .5, human=.008)
    hm = SAD_HARM[:n - 2] + ["G", "Asus"]
    for bar, name in enumerate(hm):
        b = bar * 4; ps = chord(name)
        pad(padp, b, name, 4, 38, (58, 82))
        cb.add(b, low(ps[0]), 4, 34)
        harp_arp(harp, b, name, 4, 38, step=1.0)
        if bar < n - 2:
            mel(vc, b, [(nm(ps[3] - 12), 2.5), (nm(ps[2] - 12), 1.5)], 44 + (4 if bar % 2 == 0 else 0), legato=.98)
    pb = (n - 2) * 4
    mel(fl, pb, promise(), 48, legato=.97, vib=True)            # A-B-D | E (held, unanswered)
    harp.add(total - 1, "E6", 2.5, 34)
    return s


# ----------------------------------------------------------------------------------------------- dawn
DAWN_HARM = ["G", "Em", "C", "D"]


def cue_dawn(c):
    """Very early, the women walking with their jars: soft harp arpeggios and a walking pizz in G (G Em C D); the
    flute's bird-like trills only in the gaps between the lines (`birds_dawn` sings too); after Mary's "I just want
    to be near Jesus" the flute hints the PROMISE figure in G (D-E-G-A) and it stops on D for the stone."""
    s = Score(c, 84, 4); n = s.bars; total = n * 4
    harp = P(s, "harp", HARP, -5, .45)
    pz = P(s, "walking pizz", PIZZ, -7, .25, human=.005)
    padp = P(s, "pad", SLOW_STR, -10, .5, lp=3000)
    fl = P(s, "flute (birds)", FLUTE, -9, .45, human=.006)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=1000)
    hm = [DAWN_HARM[i % 4] for i in range(n - 1)] + ["D"]
    for bar, name in enumerate(hm):
        b = bar * 4; ps = chord(name)
        harp_arp(harp, b, name, 4, 44, step=.5)
        pad(padp, b, name, 4, 34, (55, 78)); cb.add(b, low(ps[0]), 4, 34)
        for q in range(4): pz.add(b + q, [ps[0], ps[1], ps[2], ps[1]][q], .3, 48 + 3 * (q == 0))
    e6 = lbeat(s, c, "rs_06", "end", total - 3)
    hint = max(e6 + .25, total - 3.5)
    for g0, g1 in gaps(s, c, .45):
        if g0 >= hint - .5: continue
        q = math.ceil(g0 * 4) / 4
        if g1 - q < .6: continue
        tr = ["G6", "A6"] * 3 + ["B6"]                          # a little bird: trill and a flick up
        for i, p_ in enumerate(tr):
            if q + i * .125 < g1 - .1: fl.add(q + i * .125, p_, .14, 40 - 2 * (i % 2))
    mel(fl, hint, [("D5", .5), ("E5", .5), ("G5", .5), ("A5", 2)], 50, legato=.96, vib=True)
    return s


# ----------------------------------------------------------------------------------------------- stone
def cue_stone(c):
    """The ground shakes: a soft low timpani roll swells under the `rumble` (never a crash), one soft stroke as the
    stone rolls; the light: a shimmering tremolo string chord (D add9) and a bright harp glissando, celesta glints;
    the shimmer holds under the narrator (D, G/D, D) and turns to Asus -> A under Mary's "it's rolled away!"."""
    s = Score(c, 70, 4); n = s.bars; total = n * 4
    tim = P(s, "timpani", TIMPANI, -10, .4, lp=1200)
    low_tr = P(s, "low tremolo", TREM_STR, -12, .45, lp=1500)
    trem = P(s, "shimmer strings", TREM_STR, -11, .55, lp=6000)
    padp = P(s, "strings", SLOW_STR, -9, .55, lp=3500)
    harp = P(s, "harp", HARP, -5, .5)
    cel = P(s, "celesta", CELESTA, -12, .6)
    oohs = P(s, "oohs", OOHS, -14, .6, lp=4000)
    cb = P(s, "contrabass", CBASS, -14, .35, lp=900)
    rb = beat_of(s, c.first("sfx", id="rumble"), .7)
    sb = beat_of(s, c.first("sfx", id="stone_roll"), rb + 1)
    al = beat_of(s, c.first("fx", id="angel_light"), sb)
    m0 = lbeat(s, c, "rs_08", "start", total - 3)
    roll(tim, max(0, rb - .6), sb, "D2", 24, 44, .12); tim.add(sb, "D2", 2.5, 44)
    low_tr.chord(0, ["D3", "A3"], sb + .5, 40); low_tr.ramp(0, sb, 11, 50, 100, 1.2)
    # the light
    trem.chord(al, ["D5", "F#5", "A5", "E6"], m0 - al, 44); trem.ramp(al, al + 2, 11, 40, 96, .7)
    run(harp, al, [note(p) for p in ("D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5", "B5", "D6")], .09, 50, 2.5)
    for k, p_ in enumerate(("A6", "D7", "F#6", "A6")): cel.add(al + 1 + k * .75, p_, 2.5, 40 - 3 * k)
    span = m0 - al; d1 = span / 3
    segs(al, [("D", d1), ("Dsus", d1), ("D", m0 - al - 2 * d1)], lambda b, nme, d: (pad(padp, b, nme, d, 40, (64, 86)),
                                                                                cb.add(b, "D2", d, 36)))
    oohs.chord(al + 1, ["A4", "D5"], m0 - al - 1, 34)
    segs(m0, [("Asus", (total - m0) / 2), ("A", total - m0 - (total - m0) / 2)],
         lambda b, nme, d: (pad(padp, b, nme, d, 44, (80, 92)), cb.add(b, "A2", d, 38), harp.add(b, chord(nme)[3] + 12, 2.5, 42)))
    return s


# ----------------------------------------------------------------------------------------------- risen
def cue_risen(c):
    """The MORNING theme for the first time (the JESUS theme, bars 1-4), glowing and not loud: violins sing it over a
    harp and soft strings; the children's choir holds a high 'ah' glow and doubles the second half; warm under the
    angel's words; ends on D."""
    s = Score(c, 72, 4); n = s.bars; total = n * 4
    vln = P(s, "violins (morning)", STRINGS, -8, .55, lp=5000, human=.006)
    choir = P(s, "children ah", CHOIR, -11, .6, lp=4500)
    padp = P(s, "strings", SLOW_STR, -8, .55, lp=3200)
    harp = P(s, "harp", HARP, -6, .5)
    cb = P(s, "contrabass", CBASS, -14, .35, lp=900)
    gl = P(s, "glock", GLOCK, -18, .55)
    plan = me.fill_phrase(n, 4, 4, min_intro=1)
    for bar, k in enumerate(plan):
        b = bar * 4
        if k is None:
            pad(padp, b, "D", 4, 38, (55, 80)); harp_arp(harp, b, "D", 4, 44); cb.add(b, "D2", 4, 36)
            choir.chord(b + 1, ["A4", "D5"], 3.2, 34); gl.add(b, "A6", 2, 34); continue
        mel(vln, b, jesus([k + 1]), 58 if k < 2 else 62, legato=.97, vib=True)
        if k >= 2: mel(choir, b, jesus([k + 1]), 40, legato=.98)
        def chordfn(bb, name, d):
            pad(padp, bb, name, d, 42, (66, 88)); cb.add(bb, low(chord(name)[0]), d, 38); harp_arp(harp, bb, name, d, 42)
            if k < 2: choir.chord(bb, [chord(name)[2] + 12, chord(name)[3]], d + .2, 32)
        harm(b, JESUS_HARM, [k + 1], chordfn)
    return s


# ----------------------------------------------------------------------------------------------- news
def cue_news(c):
    """Breathless: Mary runs to Peter and John. A quick oud ostinato and hand drum in D, a pizz pulse, and the flute
    running up (the PROMISE figure, fast) in the gaps; under Peter's "Alive? That can't be true!" it stops to a held
    Bm with soft pizz; for John's "Let's go and see!" it starts up again and lands on A7 for the race."""
    s = Score(c, 132, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -5, .3, lp=4200, human=.004)
    dr = P(s, "hand drum", DRUMS, -9, .2, lp=4000, human=.004)
    pz = P(s, "pizz pulse", PIZZ, -7, .25)
    fl = P(s, "flute", FLUTE, -9, .4)
    padp = P(s, "pad", SLOW_STR, -11, .5, lp=3200)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=1000)
    p0, p1 = lbeat(s, c, "rs_14", "start", total * .5), lbeat(s, c, "rs_14", "end", total * .75)
    h0, h1 = math.floor(p0), math.ceil(p1)
    NEWS = ["D", "G", "D", "A"]
    for bar in range(n):
        b = bar * 4; name = NEWS[bar % 4] if bar < n - 1 else "A7"; ps = chord(name)
        for q in np.arange(0, 4, .5):
            bq = b + q
            if h0 <= bq < h1: continue
            oud.add(bq, ps[[1, 2, 3, 2][int(q * 2) % 4]] + 12, .3, 60 if q % 1 == 0 else 50)
        for q in range(4):
            if not (h0 <= b + q < h1): pz.add(b + q, low(ps[0]) + (12 if q % 2 else 0), .25, 52)
        if not (h0 <= b < h1 or h0 <= b + 2 < h1): groove(dr, b, "D.tkT.t.D.tkT.kk", .25, PARADE, .7)
        pad(padp, b, name, 4, 34, (55, 75)); cb.add(b, low(ps[0]), 4, 34)
    pad(padp, h0, "Bm", h1 - h0, 40, (70, 82))
    for q in np.arange(h0, h1, 1.0): pz.add(q, "B2" if (q - h0) % 2 == 0 else "F#3", .25, 40)
    for g0, g1 in gaps(s, c, .4):
        q = math.ceil(g0 * 2) / 2
        if g1 - q >= 1.0: run(fl, q, [note(p) for p in ("A4", "B4", "D5", "E5", "F#5", "A5")], .25, 44, .3)
    oud.chord(total - 2, ["A3", "E4", "G4", "C#5"], 1.8, 64, strum=.02)
    return s


# ----------------------------------------------------------------------------------------------- race
def cue_race(c):
    """Comic chase: John is a fast, light pizzicato scamper; Peter is a heavy tuba oom-pah one step behind; under
    Peter's "Wait for me!" the tuba drags (slower, bending down, puffing) and a slide whistle sighs up-and-down in
    the pause inside his line; a tuba plop and a pizz D chord as they arrive."""
    s = Score(c, 144, 4); n = s.bars; total = n * 4
    pz = P(s, "pizz (John)", PIZZ, -4, .25, human=.004)
    tuba = P(s, "tuba (Peter)", TUBA, -5, .25, lp=1500, bend=True)
    wh = P(s, "slide whistle", WHISTLE, -13, .3, lp=5000, bend=True)
    xy = P(s, "xylophone", XYLO, -12, .3)
    sh = P(s, "shaker", DRUMS, -10, .2, human=.004)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=1000)
    t0 = lbeat(s, c, "rs_18", "start", total * .55)
    RACE = ["D", "D", "G", "A"]
    SCAMPER = [0, 1, 2, 3, 2, 1, 2, 3]
    for bar in range(n - 1):
        b = bar * 4; name = RACE[bar % 4]; ps = chord(name)
        for i in range(8):
            pz.add(b + i * .5, ps[SCAMPER[i]] + 12, .2, 58 if i % 2 == 0 else 48)
        groove(sh, b, "h.hhh.hhh.hhh.hh", .25, HANDS, .6)
        cb.add(b, low(ps[0]), 4, 32)
        if b < math.floor(t0):          # oom-pah: heavy steps on 1 and 3, a lighter "pah" on 2 and 4
            for q, (p_, v) in enumerate(((low(ps[0]) - 12, 66), (ps[1] - 12, 50), (low(ps[0]) - 12 + 7, 62), (ps[1] - 12, 50))):
                tuba.add(b + q, p_, .55, v)
    # Peter drags: one heavy step a bar, bending down like a tired sigh
    q = math.floor(t0)
    while q < total - 4:
        tuba.add(q, low(chord(RACE[int(q // 4) % 4])[0]) - 12, 1.5, 62); tuba.glide(q + .6, q + 1.4, 0, -1.5, 1.4)
        tuba.bend(q + 1.9, 0); q += 2
    pauses = [p for p in clip_pauses(c, "rs_18") if p[1] - p[0] >= .25]
    if pauses: wt = max(pauses, key=lambda p: p[1] - p[0])[0]
    else: wt = line_t(c, "rs_18", "end") or (c.t + c.span - .6)
    wb = min(total - 1.5, s.beat(wt - c.t) + .05)
    wh.add(wb, "C5", 1.2, 62); wh.bend(wb - .05, -2); wh.glide(wb, wb + .5, -2, 7, .8); wh.glide(wb + .55, wb + 1.15, 7, -5, 1.2)
    wh.bend(wb + 1.3, 0)
    # they arrive
    e = total - 4
    run(xy, e, [note(p) for p in ("D5", "F#5", "A5", "D6")], .25, 44, .3)
    tuba.add(e + 2, "D2", .8, 70); tuba.bend(e + 1.95, 2); tuba.glide(e + 2.1, e + 2.7, 2, -3, 1.0); tuba.bend(e + 3.2, 0)
    pz.chord(e + 3, ["D3", "A3", "D4", "F#4"], .4, 64, strum=.015); cb.add(e + 3, "D2", 1, 40)
    return s


# ----------------------------------------------------------------------------------------------- empty
def cue_empty(c):
    """Hushed wonder in the empty tomb: celesta and harp over very soft high strings (D Bm G Em), celesta glimmers in
    the gaps; for John's "...and He did!" the flute and celesta play the PROMISE figure answered at last (A-B-D, E ->
    D), the D landing as his line ends."""
    s = Score(c, 66, 4); n = s.bars; total = n * 4
    harp = P(s, "harp", HARP, -6, .5)
    cel = P(s, "celesta", CELESTA, -12, .6)
    padp = P(s, "high strings", SLOW_STR, -10, .6, lp=3500)
    fl = P(s, "flute (answer)", FLUTE, -8, .5, human=.006)
    cb = P(s, "contrabass", CBASS, -15, .4, lp=800)
    je = lbeat(s, c, "rs_21", "end", total - 1)
    d_b = min(total - 1.0, je - s.beat(.15))
    ANS = [("A4", 1), ("B4", .5), ("D5", .5), ("E5", 1.5), ("D5", 2.5)]
    a_b = d_b - 3.5
    def chordfn(b, name, d):
        pad(padp, b, name, d, 34, (55, 76)); cb.add(b, low(chord(name)[0]), d, 30)
        harp_arp(harp, b, name, d, 36, step=1.0)
    items = []; b = 0; i = 0
    while b < a_b - .01:
        d = min(4, a_b - b); items.append((["D", "Bm", "G", "Em"][i % 4], d)); b += d; i += 1
    items += [("G", 2), ("A", 1.5), ("D", total - d_b)]
    segs(0, items, chordfn)
    for g0, g1 in gaps(s, c, .5):
        if g0 >= a_b - 1: continue
        q = math.ceil(g0 * 2) / 2
        for k, p_ in enumerate(("A6", "F#6", "D7")):
            if q + k * .5 < g1: cel.add(q + k * .5, p_, 2, 34 - 3 * k)
    mel(fl, a_b, ANS, 52, legato=.97, vib=True)
    mel(cel, a_b, [(p, d) for p, d in ANS], 34, legato=.9, shift=12)
    harp.add(d_b, "D6", 3, 40); harp.add(d_b + .25, "F#6", 3, 34)
    return s


# ----------------------------------------------------------------------------------------------- garden_tears
def cue_garden_tears(c):
    """Mary crying in the garden, very soft: solo cello sings the PROMISE figure in B minor (F#-G-B-C#, minor 6th),
    over a slow pad (Bm G Em F#) and a sparse harp; when Jesus is there (`angel_light`) the harmony warms (G D/F# Em)
    but stays quiet, the cello answering higher; under "Sir, are you the gardener?" it settles to Em -> Asus -> A,
    the note the next cue holds."""
    s = Score(c, 58, 4); n = s.bars; total = n * 4
    vc = P(s, "cello solo", CELLO, -5, .5, lp=2800, human=.008)
    padp = P(s, "pad", SLOW_STR, -9, .6, lp=2400)
    harp = P(s, "harp", HARP, -8, .5)
    cb = P(s, "contrabass", CBASS, -15, .4, lp=800)
    al = beat_of(s, c.first("fx", id="angel_light"), total * .45)
    m0 = lbeat(s, c, "rs_24", "start", total - 5)
    a_b = math.floor(al * 2) / 2
    def chordfn(b, name, d, vel=34):
        pad(padp, b, name, d, vel, (52, 74)); cb.add(b, low(chord(name)[0]), d, 30)
        for j in range(int(d // 2)): harp.add(b + 2 * j, chord(name)[[3, 2][j % 2]] + 12, 3, 32)
    items = []; b = 0; i = 0
    while b < a_b - .01:
        d = min(4, a_b - b); items.append((["Bm", "G", "Em", "F#"][i % 4], d)); b += d; i += 1
    w = max(1.0, (m0 - a_b) / 2)
    items += [("G", w), ("D", m0 - a_b - w)]
    tail = total - m0
    items += [("Em", tail * .4), ("Asus", tail * .3), ("A", tail - tail * .4 - tail * .3)]
    segs(0, items, chordfn)
    mel(vc, .5, promise(shift=-15, minor=True, last=3), 50, legato=.99, vib=True)        # F#3 G3 B3 C#4
    vc.add(m0 + .5, "A3", total - m0, 36)
    if a_b + 1 < m0:
        mel(vc, a_b + .5, [("B3", 1), ("D4", 1), ("F#4", 2), ("E4", max(1, m0 - a_b - 4.5))], 46, legato=.99, vib=True)
    return s


# ----------------------------------------------------------------------------------------------- mary
MARY_MEL = [("A4", 1.5), ("B4", .5), ("D5", 1), ("E5", 2.5), ("D5", .5), ("F#5", 1.5), ("E5", .5), ("D5", 1),
            ("B4", 1), ("A4", 1), ("B4", .5)]
MARY_HARM = [("D", 3), ("A", 1.5), ("G", 1.5), ("Bm", 2), ("G", 2), ("A", 1.5)]


def cue_mary(c):
    """The turn. One held A on the strings (soft, barely growing) until Jesus says "Mary."; then the MORNING theme
    bursts out tender and joyful on flute and violins over harp and strings, the choir joining; its high F# sits on
    the `sparkle_up` (the swell, clear of speech); it ends on a warm D."""
    s = Score(c, 80, 4); n = s.bars; total = n * 4
    held = P(s, "held A", STRINGS, -9, .55, lp=4000)
    fl = P(s, "flute (morning)", FLUTE, -4, .5, human=.008)
    vln = P(s, "violins (morning)", STRINGS, -9, .55, lp=5500)
    padp = P(s, "strings", SLOW_STR, -8, .55, lp=3500)
    harp = P(s, "harp", HARP, -5, .5)
    choir = P(s, "children ah", CHOIR, -10, .6, lp=4500)
    vc = P(s, "cellos", CELLO, -10, .45, lp=2500)
    cb = P(s, "contrabass", CBASS, -14, .35, lp=900)
    me_ = lbeat(s, c, "rs_25", "end", 2.0)
    b0 = math.ceil((me_ + s.beat(.12)) * 4) / 4
    held.add(0, "A4", b0 + .4, 52); held.add(0, "A5", b0 + .4, 40); held.ramp(0, b0, 11, 80, 96, 1.0)
    run(harp, b0 - .5, [note(p) for p in ("D4", "F#4", "A4", "D5", "F#5", "A5")], .08, 50, 2.5)
    end = mel(fl, b0, MARY_MEL, 66, legato=.96, vib=True)
    mel(vln, b0, MARY_MEL, 50, legato=.97)
    def chordfn(b, name, d):
        pad(padp, b, name, d, 44, (72, 96)); cb.add(b, low(chord(name)[0]), d, 38); harp_arp(harp, b, name, d, 42)
        vc.add(b, low(chord(name)[0]) + 12, d, 40)
    hb = segs(b0, MARY_HARM, chordfn)
    sp = beat_of(s, c.first("sfx", id="sparkle_up"), b0 + 8)
    choir.chord(max(b0 + 4.5, sp - 1.5), ["F#4", "A4", "D5"], 2.5, 42)
    rest = total - hb
    if rest > 0: chordfn(hb, "D", rest)
    fl.add(end, "D5", max(1.0, total - end), 62); vln.add(end, "D5", max(1.0, total - end), 46)
    choir.chord(hb, ["F#4", "A4", "D5"], max(1.0, rest), 36)
    return s


# ----------------------------------------------------------------------------------------------- peace
def cue_peace(c):
    """Evening, the locked room: warm strings and harp in G (G Em C D), a cello line; when Jesus appears the strings
    warm to D -> G under "Peace be with you!"; John's "A g-g-ghost?" gets a light pizzicato tiptoe (comic, not scary);
    Jesus' laugh resolves on warm G; then the fish: laughter-light wood blocks and xylophone giggles, a block pair on
    the `munch`, an oom-pah pizz under Peter's laugh; ends on G."""
    s = Score(c, 96, 4); n = s.bars; total = n * 4
    padp = P(s, "evening strings", SLOW_STR, -7, .55, lp=3200)
    harp = P(s, "harp", HARP, -6, .5)
    vc = P(s, "cello", CELLO, -9, .45, lp=2600, human=.006)
    pz = P(s, "pizz", PIZZ, -5, .25, human=.004)
    wb = P(s, "wood blocks", DRUMS, -2, .18, human=.003)
    xy = P(s, "xylophone", XYLO, -10, .3)
    cb = P(s, "contrabass", CBASS, -14, .35, lp=900)
    ch = beat_of(s, c.first("sfx", id="appear_chime"), total * .3)
    j30e = lbeat(s, c, "rs_30", "end", ch + 3)
    g0, g1 = lbeat(s, c, "rs_31", "start", j30e + .5), lbeat(s, c, "rs_31", "end", j30e + 3)
    j32e = lbeat(s, c, "rs_32", "end", g1 + 8)
    mb = beat_of(s, c.first("sfx", id="munch"), j32e + 3)
    def chordfn(b, name, d, vel=40):
        pad(padp, b, name, d, vel, (60, 84)); cb.add(b, low(chord(name)[0]), d, 34)
        harp_arp(harp, b, name, d, 38, step=1.0)
    c0 = math.floor(ch)
    items = []; b = 0; i = 0
    while b < c0 - .01:
        d = min(4, c0 - b); items.append((["G", "Em", "C", "D"][i % 4], d)); b += d; i += 1
    segs(0, items, chordfn)
    for k, (name, d) in enumerate(items):
        if d >= 4: mel(vc, sum(x[1] for x in items[:k]), [(nm(chord(name)[2] - 12), 2), (nm(chord(name)[3] - 12), 2)], 42, legato=.98)
    # Jesus appears: D -> G, warm
    t1 = math.ceil(j30e)
    segs(c0, [("D", max(1, (t1 - c0) / 2)), ("G", t1 - c0 - max(1, (t1 - c0) / 2))], lambda b, nme, d: chordfn(b, nme, d, 46))
    # the ghost: pizz tiptoe, chromatic and light, until the end of John's squeak
    gh1 = math.ceil(g1 * 2) / 2
    q = t1; TIP = ["E3", "F3", "F#3", "G3", "G#3", "A3", "G#3", "G3"]; i = 0
    while q < gh1:
        pz.add(q, TIP[i % 8], .2, 50 if q % 1 == 0 else 40); q += .5; i += 1
    padp.chord(t1, [note("B3"), note("D4")], gh1 - t1, 30)
    # Jesus laughs: warm G
    l1 = math.ceil(j32e)
    chordfn(gh1, "G", max(1, l1 - gh1), 44); run(harp, gh1, [note(p) for p in ("G3", "B3", "D4", "G4", "B4", "D5")], .1, 44, 2)
    # the fish: wood blocks, giggles, oom-pah
    q = l1; FISH = "H.l.H.lhH.l.HhLh"
    while q < total - 2:
        groove(wb, q, FISH, .25, HOOVES, .7); bar_c = "G" if int((q - l1) // 4) % 2 == 0 else "D"
        for k in range(4): pz.add(q + k, low(chord(bar_c)[0]) if k % 2 == 0 else chord(bar_c)[2], .25, 50)
        pad(padp, q, bar_c, 4, 36, (60, 76)); cb.add(q, low(chord(bar_c)[0]), 4, 32)
        q += 4
    wb.add(mb, HI_WOOD, .2, 70); wb.add(mb + .25, LO_WOOD, .2, 64)
    for g0_, g1_ in gaps(s, c, .4):
        if g0_ >= l1 - .5 and g1_ - g0_ >= .8: run(xy, math.ceil(g0_ * 4) / 4, [note(p) for p in ("B5", "D6", "B5", "D6", "G6")], .25, 44, .25)
    e = total - 2
    pz.chord(e, ["G3", "D4", "G4"], .4, 56, strum=.015); harp.add(e, "G5", 2, 40); cb.add(e, "G2", 2, 36)
    return s


# ----------------------------------------------------------------------------------------------- thomas
def cue_thomas(c):
    """A week later: Thomas doubts. A thoughtful clarinet asks the PROMISE figure in B minor (unanswered), twice, over
    a soft pad (Bm G Em F#, then A); when Jesus appears the MORNING theme comes slow and heartfelt on violins and a
    soft horn over harp (D | A G | A B D), its last D landing on "My Lord and my God!" with the children's choir."""
    s = Score(c, 66, 4); n = s.bars; total = n * 4
    cl = P(s, "clarinet (doubt)", CLARINET, -5, .45, lp=3200, human=.008)
    padp = P(s, "pad", SLOW_STR, -8, .55, lp=3000)
    vln = P(s, "violins (morning)", STRINGS, -8, .55, lp=5000)
    hn = P(s, "horn", HORN, -10, .5, lp=2600)
    harp = P(s, "harp", HARP, -6, .5)
    choir = P(s, "children ah", CHOIR, -10, .6, lp=4500)
    cb = P(s, "contrabass", CBASS, -14, .35, lp=900)
    ch = beat_of(s, c.first("sfx", id="appear_chime"), total - 13)
    tl_ = lbeat(s, c, "rs_37", "start", total - 3)
    c0 = math.floor(ch)
    def chordfn(b, name, d, vel=40):
        pad(padp, b, name, d, vel, (55, 80)); cb.add(b, low(chord(name)[0]), d, 32)
        harp_arp(harp, b, name, d, 38, step=1.0)
    items = []; b = 0; i = 0
    while b < c0 - 2 - .01:
        d = min(4, c0 - 2 - b); items.append((["Bm", "G", "Em", "F#"][i % 4], d)); b += d; i += 1
    items.append(("A", c0 - b))
    segs(0, items, chordfn)
    mel(cl, 1, promise(shift=-15, minor=True, last=3), 50, legato=.98, vib=True)           # F#3 G3 B3 C#4 ...
    if c0 - 2 >= 10: mel(cl, 8.5, promise(shift=-3, minor=True, last=2), 46, legato=.98, vib=True)       # F#4 G4 B4 C#5
    # the morning theme, slow: D lands on "My Lord and my God!"
    mt = [("A4", 2), ("B4", 1), ("D5", 1), ("E5", 3), ("D5", 1), ("A4", 1), ("B4", 1), ("D5", 2)]
    d_b = max(c0 + 8, tl_ - .25)
    m0 = d_b - 10
    mel(vln, m0, mt, 54, legato=.98, vib=True); mel(hn, m0, mt, 40, legato=.98, shift=-12)
    segs(c0, [("D", m0 - c0)], chordfn) if m0 - c0 > 0 else None
    segs(m0, [("D", 4), ("A", 2), ("G", 2), ("A", 2), ("D", total - d_b)], lambda b, nme, d: chordfn(b, nme, d, 44))
    choir.chord(d_b, ["F#4", "A4", "D5"], total - d_b + .5, 44)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """Easter morning, joyful: the MORNING theme in full (the JESUS theme, all 8 bars) on flute and violins with the
    oud, harp and pizz bass; frame drum from bar 3; the children's choir, hand claps and tambourine join on bars 5-8;
    a bright held D chord with harp roll, glock and a soft timpani."""
    s = Score(c, 108, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (morning)", FLUTE, -3, .45, human=.008)
    vln = P(s, "violins", STRINGS, -10, .5, lp=5500)
    oud = P(s, "oud", OUD, -6, .3, lp=4200, human=.005)
    choir = P(s, "children ah", CHOIR, -9, .6, lp=4500)
    padp = P(s, "strings", SLOW_STR, -9, .5, lp=3500)
    harp = P(s, "harp", HARP, -7, .45)
    pz = P(s, "pizz bass", PIZZ, -7, .25)
    cb = P(s, "contrabass", CBASS, -13, .3, lp=1100)
    dr = P(s, "frame drum", DRUMS, -9, .2, lp=3500, human=.005)
    hands = P(s, "claps+tamb", DRUMS, -6, .25, human=.004)
    gl = P(s, "glock", GLOCK, -14, .5)
    tim = P(s, "timpani", TIMPANI, -13, .4, lp=1000)
    plan = me.fill_phrase(n, 8, 8, min_intro=0)
    for bar, k in enumerate(plan):
        b = bar * 4; last = bar == n - 1
        if k is None:
            pad(padp, b, "D", 4, 44, (60, 90)); harp_arp(harp, b, "D", 4, 44); cb.add(b, "D2", 4, 44); continue
        full = k >= 4
        if not last:
            mel(fl, b, jesus([k + 1]), 74 if full else 68, legato=.93, vib=True)
            mel(vln, b, jesus([k + 1]), 46 if full else 38, legato=.96, shift=-12 if not full else 0)
            if full: mel(choir, b, jesus([k + 1]), 44, legato=.98)
        def chordfn(bb, name, d):
            ps = chord(name); pad(padp, bb, name, d, 46 if full else 40, (76, 100)); cb.add(bb, low(ps[0]), d, 44)
            for q in np.arange(0, d, 1.0):
                oud.chord(bb + q + .5, [ps[1], ps[2], ps[3]], .3, 44, strum=.012)
                pz.add(bb + q, low(ps[0]) + (12 if q % 2 else 0), .3, 56)
            if not full: harp_arp(harp, bb, name, d, 42)
        if not last: harm(b, JESUS_HARM, [k + 1], chordfn)
        if k >= 2 and not last: groove(dr, b, "D..tD.k.D..tD.kt", .25, FRAME, .7)
        if full and not last: groove(hands, b, "s...c.s.s...c.s.", .25, HANDS, .8)
    fe = total - 4; ps = chord("D")
    fl.add(fe, "D5", 4, 76); vln.chord(fe, [note("A5"), note("D6"), note("F#6")], 4, 48, strum=.04)
    padp.chord(fe, ps[1:] + [ps[3] + 12], 4, 58); choir.chord(fe, [ps[2], ps[3], ps[3] + 12], 4, 50)
    run(harp, fe, [ps[0], ps[1], ps[2], ps[3], ps[1] + 24, ps[2] + 24, ps[3] + 24], .1, 56, 4)
    for i, p_ in enumerate(["D6", "F#6", "A6", "D7"]): gl.add(fe + .25 + i * .3, p_, 3, 44)
    tim.add(fe, "D2", 3, 54); cb.add(fe, "D2", 4, 50); oud.chord(fe, ["D3", "A3", "D4", "F#4"], 3, 60, strum=.03)
    return s


# =============================================================================================== loop sections
VAMP = {"sad_day": ("Asus", "hush"), "dawn": ("D", "bed"), "stone": ("A", "hush"), "risen": ("D", "choir"),
        "news": ("A7", "march"), "race": ("D", "tiptoe"), "empty": ("D", "hush"), "garden_tears": ("A", "hush"),
        "mary": ("D", "choir"), "peace": ("G", "bed"), "thomas": ("D", "choir"), "finale": ("D", "choir")}


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


MUSIC = {"sad_day": cue_sad_day, "dawn": cue_dawn, "stone": cue_stone, "risen": cue_risen, "news": cue_news,
         "race": cue_race, "empty": cue_empty, "garden_tears": cue_garden_tears, "mary": cue_mary, "peace": cue_peace,
         "thomas": cue_thomas, "finale": cue_finale}
METER = {}
KEYS = {"sad_day": "D minor -> Asus", "dawn": "G major -> D", "stone": "D -> A", "risen": "D major",
        "news": "D major -> A7", "race": "D major", "empty": "D major", "garden_tears": "B minor -> A",
        "mary": "D major", "peace": "G major", "thomas": "B minor -> D major", "finale": "D major"}
CUE_NOTES = {
    "sad_day": "Low strings, slow harp (one note a beat) and a soft cello in D minor (Dm Bb Gm A); lifts to G for 'a promise': solo flute plays the PROMISE figure A-B-D...E, left hanging on Asus. No drums.",
    "dawn": "Harp arpeggios + walking pizz in G (G Em C D); flute bird trills only in the speech gaps; PROMISE hint in G (D-E-G-A) after Mary's line; stops on D.",
    "stone": "Soft timpani roll swelling under `rumble`, one soft stroke on `stone_roll`; at `angel_light` a shimmering tremolo D add9 chord, harp glissando, celesta glints, oohs; Asus -> A under Mary.",
    "risen": "MORNING theme (JESUS theme bars 1-4) first time on violins over harp + soft strings; choir glow, then doubling bars 3-4; warm, not loud; ends on D.",
    "news": "Quick oud ostinato, hand drum, pizz pulse in D; fast flute runs (PROMISE figure) in the gaps; stops to a held Bm under Peter's doubt; restarts for John, lands on A7.",
    "race": "Pizz scamper (John) over a heavy tuba oom-pah (Peter); the tuba drags and sighs under 'Wait for me!', slide whistle up-down in the pause inside his line; xylophone run, tuba plop, pizz D.",
    "empty": "Hushed: harp, celesta glimmers in the gaps, very soft high strings (D Bm G Em); flute + celesta play the PROMISE figure answered (A-B-D, E -> D) on 'and He did!'.",
    "garden_tears": "Solo cello: PROMISE figure in B minor (F#-G-B-C#), slow pad Bm G Em F#, sparse harp; warms to G - D when Jesus is there; Em - Asus - A under 'are you the gardener?'.",
    "mary": "One held A (strings) until 'Mary.'; harp sweep, then the MORNING theme bursts out on flute + violins over strings, harp, cellos; choir on the `sparkle_up` swell; warm D.",
    "peace": "Warm evening strings + harp + cello in G; D -> G under 'Peace be with you!'; light chromatic pizz tiptoe for 'A g-g-ghost?'; warm G for Jesus' laugh; wood blocks, xylophone giggles and oom-pah pizz for the fish; block pair on `munch`.",
    "thomas": "Thoughtful clarinet asks the PROMISE figure in B minor twice (Bm G Em F#, A); at `appear_chime` the MORNING theme slow on violins + soft horn over harp; the D lands on 'My Lord and my God!' with the choir.",
    "finale": "MORNING theme in full (JESUS theme, 8 bars) on flute + violins, oud strums, harp, pizz bass; frame drum from bar 3; choir, claps, tambourine on bars 5-8; bright held D, harp roll, glock, soft timpani.",
}


# =============================================================================================== sfx
# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG
place_ = lambda dst, src, at: me.place(dst, src, at)
LOOP_SECS = {}                 # no loops: every effect is a one-shot sized to its scene (CONTRACT 7)
LOOP_STOP_CUE = {}
WRAP = 0.6


def make_loop(y, secs):
    """y is secs + WRAP long; fold the overhang onto the start so the end flows into the beginning."""
    n, k = int(secs * SR), int(WRAP * SR); out = y[:n].copy(); w = np.linspace(0, 1, k)
    out[:k] = y[:k] * np.sqrt(w) + y[n:n + k] * np.sqrt(1 - w)
    return out


def note_hz(p): return 440 * 2 ** ((note(p) - 69) / 12)


def bell(secs, *a, **kw):
    y = me.partials(secs, *a, **kw); k = min(len(y), int(.04 * SR)); y[-k:] *= np.linspace(1, 0, k); return y


def chirp(f0, f1, secs, amp=1.0, curve=1.0):
    """One bird note: a sine sweeping f0 -> f1 with a soft sin^2 envelope."""
    m = int(secs * SR); t = np.arange(m) / SR; u = t / secs
    f = f0 + (f1 - f0) * u ** curve
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * u) ** 2


def thud(f_body=90, amp=1.0, secs=.45, knock=(160, 1100)):
    """A soft round thud: a falling low sine body plus a mid knock (the part a phone speaker plays)."""
    k = int(secs * SR); tk = np.arange(k) / SR
    th = np.sin(2 * np.pi * (f_body + 60 * np.exp(-tk / .025)) * tk) * np.exp(-tk / .1)
    th += me.bp(noise(k), *knock) * np.exp(-tk / .04) * .8
    return th * amp * np.minimum(1, tk / .002)


def sfx_birds_dawn(ctx):
    """Dawn birds, 11 s, thinning and fading out: one bird's 'tweet-tweet' up-chirps (3-4.2 kHz), a second's quick trill
    (3.2/3.6 kHz), a third's soft falling whistle (2.6 -> 1.8 kHz), far and light; dense for the first 6 s."""
    secs = 11.0; n = int(secs * SR); y = np.zeros(n)
    at = .1
    while at < secs - 1.5:
        kind = R().choice(["tweet", "trill", "whistle"], p=[.45, .3, .25]); a = R().uniform(.5, 1.0) * np.exp(-at / 7)
        if kind == "tweet":
            f = R().uniform(2900, 3400)
            for j in range(R().integers(2, 4)): place_(y, chirp(f, f * 1.35, .07, a), at + j * .13)
        elif kind == "trill":
            for j in range(R().integers(8, 14)): place_(y, chirp(3600 if j % 2 else 3200, 3400, .035, a * .7), at + j * .045)
        else:
            place_(y, chirp(2600, 1800, .32, a * .6, .7), at); place_(y, chirp(2200, 2500, .12, a * .5), at + .38)
        at += R().uniform(.35, .9) * (1 + at / 6)
    y += me.bp(noise(n), 2000, 6000) * .004 * np.exp(-np.arange(n) / SR / 6)
    return me.fit(me.room(y, "room", .15), secs, fade_in=.3, fade_out=3.0)      # a hall makes each chirp ring for seconds


def sfx_rumble(ctx):
    """The ground shakes, softly: 1.2 s of low noise (under 120 Hz) with a wobble, a 150-400 Hz rumble layer so a phone
    hears it, a few gravel ticks; rises over 0.3 s and fades; never a crash."""
    secs = 1.2; n = int(secs * SR); t = np.arange(n) / SR
    env = np.minimum(1, t / .3) * np.clip((secs - t) / .55, 0, 1)
    wob = .7 + .3 * np.sin(2 * np.pi * 9 * t + 1) * (.6 + .4 * me.smooth_rand(n, 12))
    y = (me.lp(noise(n), 120, 4) * 1.0 + me.bp(noise(n), 150, 400) * .35) * wob * env
    for _ in range(10):
        k = int(.03 * SR); place_(y, me.bp(noise(k), 800, 2500) * me.env_exp(k, .006) * R().uniform(.03, .08), R().uniform(.2, .9))
    return me.fit(me.room(y, "room", .2), secs, fade_out=.2)


def sfx_stone_roll(ctx):
    """The round stone rolls: 0.75 s of stone grinding (band noise 250-1800 Hz with a rough, slowing 30 -> 14 Hz
    scrape and a low 90 Hz roll) then a soft thud as it settles; 1.0 s."""
    secs = 1.0; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    m = int(.78 * SR); tt = np.arange(m) / SR
    rate = np.interp(tt, [0, .78], [30, 14]); ph = np.cumsum(rate) / SR
    am = (.55 + .45 * np.abs(np.sin(np.pi * ph))) * (.8 + .2 * me.smooth_rand(m, 40))
    env = np.minimum(1, tt / .08) * np.clip((.78 - tt) / .2, 0, 1)
    gr = me.bp(noise(m), 250, 1800) * am * env * .5 + np.sin(2 * np.pi * 90 * tt + 3 * np.sin(2 * np.pi * 4 * tt)) * env * .35
    place_(y, gr, 0.0)
    place_(y, thud(85, .9), .74)
    return me.fit(me.room(y, "room", .25), secs, fade_out=.12)


def sfx_appear_chime(ctx):
    """A warm shimmer for light / an appearance: four soft bells D6 F#6 A6 D7 rising 60 ms apart, a soft A5 hum under
    them, a faint high air shimmer; 1.5 s, fading."""
    secs = 1.5; n = int(secs * SR); y = np.zeros(n); t = np.arange(n) / SR
    for i, p_ in enumerate(("D6", "F#6", "A6", "D7")):
        place_(y, bell(1.4, note_hz(p_), [1, 2.0, 3.0, 4.2], [1, .25, .12, .05], [.9, .45, .3, .15], strike=.1) * (1 - .12 * i), i * .06)
    y += np.sin(2 * np.pi * note_hz("A5") * t) * np.sin(np.pi * np.clip(t / 1.3, 0, 1)) * .12
    y += me.bp(noise(n), 5000, 9000) * (.5 + .5 * me.smooth_rand(n, 10)) * np.sin(np.pi * np.clip(t / 1.4, 0, 1)) * .02
    return me.fit(me.room(y, "hall", .35), secs, fade_out=.5)


def step(f_body, knock, amp, crunch=.4):
    """One footstep on a garden path: a small mid knock (resonant, phone-audible), a low body and a gravel crunch."""
    k = int(.16 * SR); tk = np.arange(k) / SR
    x = me.resonator(np.r_[1.0, np.zeros(k - 1)] + me.bp(noise(k), 200, 1500) * np.exp(-tk / .01) * .5, knock, 90)
    x = x / (np.max(np.abs(x)) + 1e-9) * .6
    x += np.sin(2 * np.pi * f_body * tk) * np.exp(-tk / .04) * .5
    x += me.bp(noise(k), 1500, 5000) * np.exp(-tk / .03) * crunch
    return x * amp


def sfx_run_steps(ctx):
    """Two runners on a garden path, 6.5 s: John's quick light steps (3.6 a second, 650 Hz knock) and Peter's heavier,
    slower ones (2.7 a second, 280 Hz knock, louder low body), starting 0.3 s later; both fade into the distance from
    4 s."""
    secs = 6.5; n = int(secs * SR); y = np.zeros(n)
    for start, rate, fb, kn, a, cr in ((0.0, 3.6, 150, 650, .55, .35), (.3, 2.7, 95, 280, 1.0, .45)):
        q = start; i = 0
        while q < secs - .2:
            fade = 1.0 if q < 4 else np.exp(-(q - 4) / .9)
            place_(y, step(fb, kn * R().uniform(.95, 1.05), a * fade * (1 if i % 2 == 0 else .85), cr), q)
            q += 1 / rate * R().uniform(.95, 1.05); i += 1
    return me.fit(me.room(y, "room", .15), secs, fade_out=.6)


def sfx_munch(ctx):
    """A comic crunchy bite: a dense burst of crackles (1-5 kHz) with a small 220 Hz bite knock, then two smaller chews
    at 0.27 and 0.44 s; 0.6 s."""
    secs = .6; n = int(secs * SR); y = np.zeros(n)
    for at, cnt, a in ((.0, 26, 1.0), (.27, 10, .55), (.44, 8, .45)):
        k = int(.04 * SR); tk = np.arange(k) / SR
        place_(y, np.sin(2 * np.pi * 220 * tk) * np.exp(-tk / .02) * .4 * a, at)
        for _ in range(cnt):
            kk = int(.012 * SR); place_(y, me.bp(noise(kk), 1000, 5000) * me.env_exp(kk, .003) * R().uniform(.3, 1.0) * a,
                                         at + R().uniform(0, .12))
    return me.fit(me.room(y, "room", .1), secs, fade_out=.08)


def sfx_sparkle_up(ctx):
    """Joy: a quick rising run of nine bell pings (D6 ... A7, 70 ms apart) over a rising soft air shimmer; 1.2 s."""
    secs = 1.2; n = int(secs * SR); y = np.zeros(n); t = np.arange(n) / SR
    for i, p_ in enumerate(("D6", "E6", "F#6", "A6", "B6", "D7", "E7", "F#7", "A7")):
        place_(y, bell(.7, note_hz(p_), [1, 2.0, 3.0], [1, .2, .08], [.35, .2, .1], strike=.08) * (.6 + .05 * i), i * .07)
    y += me.bp(noise(n), 4000, 10000) * np.clip(t / .7, 0, 1) * np.clip((secs - t) / .4, 0, 1) * .025
    return me.fit(me.room(y, "hall", .3), secs, fade_out=.35)


SFX = {"birds_dawn": sfx_birds_dawn, "rumble": sfx_rumble, "stone_roll": sfx_stone_roll,
       "appear_chime": sfx_appear_chime, "run_steps": sfx_run_steps, "munch": sfx_munch, "sparkle_up": sfx_sparkle_up}
SFX_SEED = {}
SFX_GAIN = {"birds_dawn": -18, "rumble": -12, "stone_roll": -11, "appear_chime": -15, "run_steps": -14,
            "munch": -12, "sparkle_up": -15}
SFX_SHAPE = {}
SFX_NOTES = {
    "birds_dawn": "dawn birds: 'tweet-tweet' up-chirps, quick trills, a soft falling whistle; thinning, fades out over the last 3 s; 11 s",
    "rumble": "soft ground shake: low noise < 120 Hz with a 9 Hz wobble + 150-400 Hz layer for phones, gravel ticks; 1.2 s, never a crash",
    "stone_roll": "stone grinding (250-1800 Hz, rough scrape slowing 30 -> 14 Hz, 90 Hz roll) then a soft thud; 1.0 s",
    "appear_chime": "warm shimmer: bells D6 F#6 A6 D7 60 ms apart, soft A5 hum, faint air; 1.5 s",
    "run_steps": "two runners: light quick steps (3.6/s, 650 Hz knock) and heavier slower ones (2.7/s, 280 Hz knock), fading from 4 s; 6.5 s",
    "munch": "comic crunchy bite + two smaller chews; 0.6 s",
    "sparkle_up": "nine rising bell pings D6 -> A7 over a rising air shimmer; 1.2 s",
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
    if name in DIPS:
        sp = [(l["t"] - c["t"] - .2, l["t"] + l["clip"] - c["t"] + .2, db) for lid, db in DIPS[name]
              for l in tl["lines"] if l["id"] == lid]
        main = main * mp.dips(len(main), sp)
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
                        "Rerun tools/story/music_risen.py after the timeline is re-timed so the in-cue hits follow.",
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
                        "(recommended mix level). All effects are one-shots sized to their scene; none loops.",
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


HIT_ROWS_SFX = {"rumble", "stone_roll", "run_steps", "appear_chime", "munch", "sparkle_up"}
HIT_ROWS_FX = {"angel_light", "golden_rays", "heart_glow"}


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
