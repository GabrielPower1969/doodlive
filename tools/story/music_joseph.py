#!/usr/bin/env python3
"""Original score and sound effects for "Joseph the Dreamer" (story pack `joseph`; docs/joseph/CONTRACT.md section 7,
docs/joseph/DESIGN.md section 5, docs/joseph/MUSIC.md).

Built on the shared engine tools/story/music_kit.py (`import music_kit as me`): Score / Part / mel / groove / Ctx, the
FluidSynth renderer, the convolution hall, loudness and file helpers, the synthesis primitives, gm_notes, sfx_sparkle.
This script holds Joseph's cues, effects, paths and tables, plus the loop-section / build machinery that the kit does
not have yet (copied from music_jonah.py, see docs/joseph/MUSIC.md "Reuse").

Two original themes carry the score (both in G, written so that they fit together):
  * the JOSEPH theme: a clear, hopeful, rising tune (G B D E / D B A ...) on a shepherd's flute. It opens `home`,
    sneaks into `dream`, comes back in minor on a reed in `betrayal`, softly at "You are still with me" in `prison`,
    in a pompous march dress in `plenty`, answers the dream motif in `brothers`, is held back and then released in full
    strings at "I am Joseph" in `iam`, becomes a slow waltz in `reunion` and is stated in full in `finale`.
  * the DREAM motif: a rising harp glissando (G lydian, G3 to G6) and three bell notes D6-G6-B6. The `harp_gliss` SFX is
    exactly that, one file, identical every time it plays; the cues play the three-note bell figure around it, never on
    top of the glissando, and `pharaoh` bends it out of shape.
Every melody is original; nothing is taken from any film.

Every name and time comes from assets/joseph/timeline.json, read on every run (cue spans from the music events,
in-cue hits looked up by sfx / lines / fx events). After the voices re-time the play, rerun this script. Every cue
continues after its cadence into a quiet loop section on its final chord: cues.json has sample-exact loop points
(loopStart / loopEnd); each file is >= 1.3 x its span + 0.6 s.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/joseph/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated over the composed span, true peak <= -1 dBTP
  assets/joseph/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/joseph/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/joseph/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain, loop hints
  assets/joseph/audio/preview_mix.mp3        full-length mix at timeline times (zh voice clips, music ducked 7 dB)
  docs/joseph/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_joseph.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--tmp DIR] [--spec DIR]   (scratch default /tmp/joseph_music; --spec writes spectrogram PNGs of every output)
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg
"""
import argparse, atexit, json, math, os, re, shutil, subprocess, sys, tempfile
import numpy as np
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import music_kit as me                                                     # noqa: E402  (shared engine)
import music_polish as mp                                                  # noqa: E402  (speech pocket, underscore curve)
import voice_margin as vm                                                  # noqa: E402  (engine mix model, voice-vs-bed table)
from music_kit import (Score, Ctx, mel, groove, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB, DUCK_DB, TPB,  # noqa: E402
                       HARP, KOTO, NYLON, CELESTA, GLOCK, XYLO, TUBULAR, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                       CHOIR, OOHS, FLUTE, RECORDER, OBOE, BASSOON, CLARINET, SHANAI, TIMPANI, TRUMPET, TROMBONE, TUBA,
                       MUTED_TPT, HORN, DRUMS, BDRUM, TAMB, CRASH, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA,
                       HI_WOOD, LO_WOOD, SHAKER, TRIANGLE, SNARE, CRASH_HAND)

ROOT = me.ROOT
JO = f"{ROOT}/assets/joseph"
TIMELINE = f"{JO}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{JO}/audio/music", f"{JO}/audio/sfx", f"{JO}/audio/voice/zh"
PREVIEW = f"{JO}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/joseph/MUSIC.md"
STRETCH = 0.30                 # every cue survives its section being stretched by at least this much (re-timing)
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -4.5             # loop section loudness relative to the cue's composed span (was -3: quieter bed under voices)
SPAN_LUFS = -20.9              # composed span loudness (contract -20 +-1: 0.9 under it, check.py allows 1.0)
NO_SWELL = set()
# extra dips (file seconds, zh re-timed play, dB) where a cue sits under a line it cannot get out of the way of
DIPS = {"home": [(16.4, 23.9, -3.5)], "dream": [(13.2, 20.5, -3.5)], "betrayal": [(25.5, 30.5, -3.5)],
        "prison": [(18.4, 23.1, -2.5)], "reveal": [(10.3, 19.8, -2.0)], "brothers": [(8.6, 16.9, -2.0)],
        "reunion": [(5.6, 11.7, -2.5)]}
HIT_SFX = {'harp_gliss', 'coins', 'cell_door', 'moo', 'fanfare', 'soft_chime'}
HIT_FX = {'prayer_glow', 'heart_glow', 'confetti'}
TMP_PREFIX = "music_joseph_"

# extra GM programs (0-based)
VIOLA, ENGLISH_HORN, PAN_FLUTE, MUSIC_BOX = 41, 69, 75, 10

CH = dict(me.CH)
CH.update({"G": ["G2", "D3", "G3", "B3"], "Gm": ["G2", "D3", "G3", "Bb3"], "G5": ["G2", "D3", "G3", "D4"],
           "Gsus": ["G2", "D3", "G3", "C4"], "Gmaj7": ["G2", "D3", "F#3", "B3"], "G7": ["G2", "D3", "F3", "B3"],
           "C": ["C3", "G3", "C4", "E4"], "Cm": ["C3", "G3", "C4", "Eb4"], "Cmaj7": ["C3", "G3", "B3", "E4"],
           "D": ["D3", "A3", "D4", "F#4"], "D7": ["D3", "A3", "C4", "F#4"], "Dm": ["D3", "A3", "D4", "F4"],
           "Em": ["E3", "B3", "E4", "G4"], "Am": ["A2", "E3", "A3", "C4"], "Bm": ["B2", "F#3", "B3", "D4"],
           "Eb": ["Eb3", "Bb3", "Eb4", "G4"], "Bb": ["Bb2", "F3", "Bb3", "D4"], "F": ["F2", "C3", "F3", "A3"],
           "E": ["E3", "B3", "E4", "G#4"], "Edim": ["E3", "Bb3", "E4", "G4"], "Esus": ["E3", "B3", "E4", "A4"],
           "Ab": ["Ab2", "Eb3", "Ab3", "C4"], "Gb": ["Gb2", "Db3", "Gb3", "Bb3"], "Am7": ["A2", "E3", "G3", "C4"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def nm(m): return f"{NAMES[m % 12]}{m // 12 - 1}"


# =============================================================================================== the two themes
# The JOSEPH theme, G major, 8 bars of 4/4. Harmony: G | G D | C | D | Em | C G | Am D | G.
JOSEPH = {
    1: [("G4", 1), ("B4", 1), ("D5", 1.5), ("E5", .5)],              # up and up: a boy who looks at the sky
    2: [("D5", 2), ("B4", 1), ("A4", 1)],
    3: [("E4", 1), ("G4", 1), ("C5", 1), ("E5", 1)],                 # the same shape, a step lower
    4: [("F#5", 2), ("E5", 1), ("D5", 1)],                           # half cadence on D
    5: [("E5", 1.5), ("G5", .5), ("B5", 1), ("A5", 1)],              # the highest point
    6: [("G5", 1), ("E5", 1), ("D5", 1), ("B4", 1)],
    7: [("C5", 1), ("D5", 1), ("E5", 1), ("F#5", 1)],                # climbing to the tonic
    8: [("G5", 3), (None, 1)],
}
JOSEPH_HARM = {1: ["G"], 2: ["G", "D"], 3: ["C"], 4: ["D"], 5: ["Em"], 6: ["C", "G"], 7: ["Am", "D"], 8: ["G"]}
# the same tune in G minor (the pit and the betrayal): D7 and Cm chords, an empty fifth at the end
JOSEPH_MIN = {
    1: [("G4", 1), ("Bb4", 1), ("D5", 1.5), ("Eb5", .5)],
    2: [("D5", 2), ("Bb4", 1), ("A4", 1)],
    3: [("Eb4", 1), ("G4", 1), ("C5", 1), ("Eb5", 1)],
    4: [("F#5", 2), ("D5", 1), ("C5", 1)],
    5: [("Eb5", 1.5), ("G5", .5), ("Bb5", 1), ("G5", 1)],
    6: [("G5", 1), ("Eb5", 1), ("D5", 1), ("Bb4", 1)],
    7: [("C5", 1), ("D5", 1), ("Bb4", 1), ("A4", 1)],
    8: [("G4", 4)],
}
JOSEPH_MIN_HARM = {1: ["Gm"], 2: ["Gm", "D"], 3: ["Cm"], 4: ["D7"], 5: ["Eb"], 6: ["Cm", "Gm"], 7: ["Cm", "D7"], 8: ["Gm"]}
# 3/4 waltz form (6 bars)
JOSEPH_34 = {
    1: [("G4", 1), ("B4", 1), ("D5", .5), ("E5", .5)],
    2: [("D5", 1.5), ("B4", .5), ("A4", 1)],
    3: [("E4", 1), ("G4", 1), ("C5", .5), ("E5", .5)],
    4: [("F#5", 1.5), ("E5", .5), ("D5", 1)],
    5: [("E5", 1.5), ("G5", .5), ("B5", 1)],
    6: [("G5", 3)],
}
JOSEPH_34_HARM = {1: ["G"], 2: ["G", "D"], 3: ["C"], 4: ["D"], 5: ["Em"], 6: ["G"]}

# The DREAM motif: rising glissando over G lydian (G A B C# D E F#) + three bell notes
G_LYD = ["G", "A", "B", "C#", "D", "E", "F#"]
BELLS = [("D6", 1), ("G6", 1), ("B6", 2)]


def jos(bars, minor=False, scale=1.0):
    """Notes of the Joseph theme for the given bar numbers (1-8), laid end to end."""
    out = []
    for k in bars: out += [(p, d * scale) for p, d in (JOSEPH_MIN if minor else JOSEPH)[k]]
    return out


def theme_play(p, b0, bars, vel, minor=False, bpb=4, shift=0, vib=True, legato=.96, table=None):
    """Play whole theme bars one after another from beat b0 (each bar takes bpb beats); returns the end beat."""
    tab = table or (JOSEPH_MIN if minor else JOSEPH); b = b0
    for k in bars: mel(p, b, tab[k], vel, legato=legato, vib=vib, shift=shift); b += bpb
    return b


def theme_chords(b0, bars, fn, minor=False, bpb=4, table=None):
    """Call fn(beat, chord_name, beats) for every chord of the theme's bars (same layout as theme_play)."""
    tab = table or (JOSEPH_MIN_HARM if minor else JOSEPH_HARM)
    for i, k in enumerate(bars):
        for j, h in enumerate(tab[k]): fn(b0 + i * bpb + j * bpb / len(tab[k]), h, bpb / len(tab[k]))


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


def roll(p, b0, b1, pitch, v0, v1, step=.2):
    """Timpani / drum roll with a crescendo (or diminuendo) from beat b0 to b1."""
    k = max(2, int((b1 - b0) / step))
    for i in range(k): p.add(b0 + i * (b1 - b0) / k, pitch, step * 1.2, v0 + (v1 - v0) * i / k)


def run(p, b0, pitches, step, vel, dur=1.2):
    """Harp / glock run over a list of pitches (names or midi)."""
    for i, pt in enumerate(pitches): p.add(b0 + i * step, pt, dur, vel + 8 * i / max(1, len(pitches) - 1))
    return b0 + len(pitches) * step


def harp_arp(harp, b, name, beats, vel=48, step=.5, up=12):
    ps = chord(name)
    for j in range(int(beats / step)):
        harp.add(b + j * step, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + up, 1.4, vel + (8 if j == 0 else 0))


G_SCALE = ["G", "A", "B", "C", "D", "E", "F#"]
def scale_run(lo, hi, names=G_SCALE):
    pcs = {note(n + "4") % 12 for n in names}
    return [m for m in range(note(lo), note(hi) + 1) if m % 12 in pcs]


# Sustain fix (Ruth, measured 2026-11-14): the macOS DLS bank as FluidSynth loads it decays every instrument; winds,
# bowed strings, brass and voices get an NRPN offset on SoundFont gen 37 (volEnvSustain -1440 cB) so long notes hold.
SUSTAIN = {STRINGS, SLOW_STR, TREM_STR, CELLO, VIOLA, CBASS, CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, ENGLISH_HORN,
           HORN, PAN_FLUTE, TRUMPET, TROMBONE, TUBA, SHANAI, RECORDER, MUTED_TPT}


def sustain_ccs(p):
    d = 8192 - 1440
    p.cc(0, 99, 120); p.cc(0, 98, 37); p.cc(0, 6, d >> 7); p.cc(0, 38, d & 127)


class BPart(me.Part):
    """A Part that can also bend pitch (comic slides, sighs, wah-wah, whale calls). Bend range is 12 semitones."""

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


# Levels by measurement, not by feel: the macOS DLS bank plays instruments up to 20 dB apart at the same velocity (choir, ensemble
# strings, celesta, xylophone far quieter than cello / horn / bassoon: Jonah's music agent, measured 2026-11-15), so a part's
# gain_db here is NOT a fader: it is how loud the part is *while it plays*, in dB relative to REF_DB (-6 = a pad under the tune,
# -2 = the lead). render_split() measures every stem's RMS over its active stretches and scales it to that target.
REF_DB = -30.0


def P(s, name, program, gain_db=0.0, send=.3, *a, bend=False, **kw):
    p = (BPart if bend else me.Part)(s, name, program, 0.0, send, *a, **kw); s.parts.append(p)
    p.rel = gain_db
    if program in SUSTAIN: sustain_ccs(p)
    return p


def active_db(x):
    """RMS (dB) of the stretches where the stem is playing (50 ms envelope above -20 dB of its own maximum)."""
    e = np.sqrt(np.convolve(x.astype(np.float64) ** 2, np.ones(2205) / 2205, "same")); m = e.max()
    if m < 1e-6: return None
    act = e > m * .1
    return 20 * np.log10(np.sqrt(np.mean(x[act].astype(np.float64) ** 2)) + 1e-12)


def when(c, s, kind, default, nth=0, **match):
    """Beat (in the cue) of the nth matching timeline event, or `default` if the event is missing / outside the cue."""
    ts = sorted(c.all(kind, **match)); b = s.at(ts[nth]) if len(ts) > nth else None
    return default if b is None else b


def line_at(c, s, who, frac, nth=0, default=0.0):
    """Beat of a moment `frac` (0-1) into the nth line of `who` (estimated from the line's `dur`; a D-level estimate)."""
    ls = sorted((e for e in c.tl["lines"] if e["who"] == who and c.t - 1e-6 <= e["t"] <= c.t + c.span), key=lambda e: e["t"])
    if len(ls) <= nth: return default
    b = s.at(ls[nth]["t"] + frac * ls[nth].get("dur", ls[nth].get("maxSec", 4)))
    return default if b is None else b


def bed(strs, cb, b, name, beats, vel=48, swell=(70, 100), bassvel=52):
    pad(strs, b, name, beats, vel, swell); cb.add(b, low(chord(name)[0]), beats + .2, bassvel)


def nyl(part, b, name, beats, vel=48, pat=(0, 2, 3, 1, 3, 2, 3, 1), step=.5, up=0):
    ps = chord(name)
    for j in range(int(beats / step + 1e-6)): part.add(b + j * step, ps[pat[j % len(pat)]] + up, step * 2.2, vel - (8 if j % 4 else 0))


FRAME = {"D": (LO_CONGA, 84), "t": (MUTE_CONGA, 52), "k": (OPEN_CONGA, 34), "s": (TAMB, 26)}
MARCH = {"D": (LO_CONGA, 96), "T": (HI_BONGO, 72), "t": (LO_BONGO, 58), "k": (MUTE_CONGA, 46), "s": (TAMB, 40)}
DARB = {"D": (LO_CONGA, 98), "T": (OPEN_CONGA, 72), "k": (HI_BONGO, 56), "t": (MUTE_CONGA, 46), "s": (TAMB, 44),
        "S": (TRIANGLE, 40)}


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- home
def cue_home(c):
    """G major, pastoral. A flute calls over plucked strings, then plays the Joseph theme (bars 1-8); the frame drum, cello
    and violins join for the second half. A harp glint on the coat's sparkle; the brother's grumpy bassoon under his line."""
    s = Score(c, 88, 4); n = s.bars; E = end_beats(s)
    fl = P(s, "flute", FLUTE, -2, .4, lp=6500, human=.012)
    rec = P(s, "recorder", RECORDER, -9, .4, lp=5000, human=.012)
    ny = P(s, "nylon", NYLON, -5, .3)
    lyre = P(s, "lyre", KOTO, -10, .35)
    pz = P(s, "pizz", PIZZ, -6, .2, lp=1200)
    dr = P(s, "frame drum", DRUMS, -13, .25, lp=3500)
    strs = P(s, "strings", SLOW_STR, -6, .5, lp=3500)
    vc = P(s, "cello", CELLO, -5, .4, lp=3000)
    vln = P(s, "violins", STRINGS, -12, .5, lp=5000)
    harp = P(s, "harp", HARP, -8, .4)
    bsn = P(s, "bassoon", BASSOON, -6, .25)
    t0 = max(1, n - 8) * 4
    # intro: a shepherd's call on the flute over nylon arpeggios (G, D)
    for k in range(t0 // 4):
        nyl(ny, k * 4, "G" if k % 2 == 0 else "D", 4, 46); pz.add(k * 4, "G2" if k % 2 == 0 else "D3", .6, 56)
    mel(fl, .5, [("D5", 1), ("G5", .5), ("E5", .5), ("D5", 2), (None, .5), ("B4", .5), ("D5", .5), ("A4", .5), ("G4", 2)][:t0 * 2], 56, vib=True)
    lyre.add(t0 - 1, "D5", 1, 40); lyre.add(t0 - .5, "G5", 1, 42)
    # the theme
    theme_play(fl, t0, range(1, 9), 72); theme_play(rec, t0 + 16, range(5, 9), 46, vib=False)
    theme_play(lyre, t0 + 16, [5, 6], 42, vib=False, shift=12)

    def acc(b, h, beats):
        ps = chord(h)
        nyl(ny, b, h, beats, 46); pz.add(b, ps[0], .5, 62)
        if beats >= 2: pz.add(b + 2, ps[1], .4, 52)
        if b >= t0 + 16 - .01:
            strs.chord(b, ps[1:], beats + .25, 46, strum=.04); strs.ramp(b, b + beats, 11, 80, 105)
            vc.add(b, ps[0] + 12 if ps[0] < note("G2") else ps[0], beats * .95, 50)
    theme_chords(t0, range(1, 8), acc)
    for k in range(4, 8): groove(dr, t0 + 4 * k, "D..tD.t." if k < 7 else "D.k.t.k.", .5, FRAME, .8)
    vln.chord(t0 + 20, ["D5", "G5", "B5"], 7.5, 42, strum=.04); vln.ramp(t0 + 20, t0 + 28, 11, 60, 110)
    # last bar: the G chord rings, theme's G on flute; everything holds to the end
    b8 = t0 + 28
    pad(strs, b8, "G", E - b8, 52, (80, 108)); strs.chord(b8, ["G3", "D4", "B4"], E - b8 + .3, 46)
    vc.add(b8, "G2", E - b8, 54); pz.add(b8, "G2", .6, 60)
    harp.chord(b8, ["G3", "D4", "B4", "G5"], 3, 44, strum=.09)
    # hits: the coat's sparkle (harp glint) and the brother's grumpy bassoon
    sp = when(c, s, "sfx", 12.0, id="sparkle")
    for i, p_ in enumerate(("G5", "B5", "D6", "G6")): harp.add(sp + .2 + i * .12, p_, 1.5, 38 + 3 * i)
    hb = line_at(c, s, "brother", 0.05, default=n * 4 - 5)
    bsn.add(hb, "Eb3", .6, 58); bsn.add(hb + .75, "D3", 1.8, 54)
    return s


# ----------------------------------------------------------------------------------------------- dream
def cue_dream(c):
    """G lydian shimmer: a soft pad, the dream clouds' three bell notes on celesta in the gaps around the `harp_gliss` SFX
    (never over it), a playful clarinet / pizzicato / xylophone under the brother's outburst, then twinkles and the
    Joseph theme's first two bars very softly (flute) for the sun, moon and stars."""
    s = Score(c, 76, 4); n = s.bars; E = end_beats(s)
    padp = P(s, "pad", SLOW_STR, -5, .6, lp=3500)
    oohs = P(s, "oohs", OOHS, -12, .6, lp=4000)
    harp = P(s, "harp", HARP, -6, .5)
    cel = P(s, "celesta", CELESTA, -8, .6)
    glk = P(s, "glock", GLOCK, -10, .6)
    fl = P(s, "flute", FLUTE, -4, .45, human=.01)
    pz = P(s, "pizz", PIZZ, -5, .25)
    cl = P(s, "clarinet", CLARINET, -5, .3, human=.01)
    xy = P(s, "xylophone", XYLO, -8, .3)
    cb = P(s, "bass", CBASS, -8, .3, lp=1200)
    g1 = when(c, s, "sfx", 1.0, nth=0, id="harp_gliss"); g2 = when(c, s, "sfx", 16.0, nth=1, id="harp_gliss")
    tb = line_at(c, s, "brother", 0.0, default=10.0)
    g1e, g2e = g1 + s.beat(GLISS_SEC), g2 + s.beat(GLISS_SEC)
    # a floating pad, G major seventh, swelling up to the first cloud
    pad(padp, 0, "Gmaj7", max(4, g1e - 0 + 1), 40, (50, 96)); oohs.chord(0, ["B4", "D5", "F#5"], g1e + 1, 32); oohs.ramp(0, g1, 11, 40, 100)
    cb.add(0, "G2", g1e + 1, 44)
    # three bell notes answering the glissando (celesta + glock), then a second, quieter time
    mel(cel, g1e, BELLS, 62, legato=1.2); mel(glk, g1e + .02, BELLS, 44, legato=1.2)
    for i, p_ in enumerate(("D5", "G5", "B5")): harp.add(g1e + 4 + i * .5, p_, 2, 40)
    pad(padp, g1e + 1, "Cmaj7", max(2, tb - g1e - 1), 44, (70, 100)); cb.add(g1e + 1, "C3", max(2, tb - g1e - 1), 46)
    # the outburst: staccato, bouncy, a little comic (G major, I - IV - V - I)
    end_play = g2 - .4
    b = tb - .25; k = 0
    while b + 4 <= end_play + .01:
        h = ["G", "C", "D", "G"][k % 4]; ps = chord(h)
        pz.add(b, ps[0], .3, 64); pz.add(b + 1, ps[1], .3, 52); pz.add(b + 2, ps[0], .3, 60); pz.add(b + 3, ps[1], .3, 52)
        mel(cl, b, [(ps[3] and nm(ps[3] + 12) + ".", .5), (None, .5), (nm(ps[2]) + ".", .5), (nm(ps[3] + 12) + ".", .5),
                    (nm(ps[1] + 12) + ".", 1), (None, 1)], 62, legato=.5)
        xy.add(b + 2.5, nm(ps[2] + 12), .3, 48); xy.add(b + 3, nm(ps[3] + 12), .3, 52)
        padp.chord(b, ps[1:], 4.3, 36); padp.cc(b, 11, 92)
        b += 4; k += 1
    st = when(c, s, "fx", tb, id="steam")
    run(xy, st, scale_run("G5", "G6")[:6], .09, 52, .5)                 # the brother's ears go red: a little steam
    # second dream cloud (sun, moon, stars): quiet pad, then bells and the theme's first bars on the flute
    pad(padp, g2 - .3, "Gmaj7", max(2, g2e - g2 + .3), 44, (70, 100)); cb.add(g2 - .3, "G2", g2e - g2 + 1, 48)
    mel(cel, g2e, BELLS, 56, legato=1.2); mel(glk, g2e + .02, BELLS, 40, legato=1.2)
    ts = max(g2e + 1.5, E - 9)
    theme_play(fl, ts, [1, 2], 48)
    theme_chords(ts, [1, 2], lambda b, h, bt: (pad(padp, b, h, bt, 44, (70, 100)), cb.add(b, low(chord(h)[0]), bt, 46)))
    for j in range(int((E - ts) / .75)): harp.add(ts + j * .75, scale_run("G4", "G6")[(j * 2) % 12], 1.2, 38 + (j % 3) * 3)
    pad(padp, ts + 8, "G", max(1.5, E - ts - 8), 44, (70, 100)); cb.add(ts + 8, "G2", max(1.5, E - ts - 8), 48)
    return s


# ----------------------------------------------------------------------------------------------- betrayal
def cue_betrayal(c):
    """G minor, slow. Low strings and a soft heartbeat drum under the coat being taken; then, from the caravan, the Joseph
    theme in minor on a reed (English horn) with a cello answer; Jacob's weeping is the last bar: the theme's G alone on the
    horn over an empty fifth (D + G, no third)."""
    s = Score(c, 66, 4); n = s.bars; E = end_beats(s)
    cb = P(s, "contrabass", CBASS, -4, .3, lp=1000)
    vc = P(s, "cello", CELLO, -3, .4, lp=2600)
    vl = P(s, "viola", VIOLA, -6, .4, lp=3000)
    strs = P(s, "strings", SLOW_STR, -6, .5, lp=2800)
    eh = P(s, "english horn", ENGLISH_HORN, -2, .4, lp=3500, human=.01)
    tim = P(s, "timpani", TIMPANI, -9, .3, lp=2500)
    oohs = P(s, "oohs", OOHS, -14, .6, lp=3000)
    harp = P(s, "harp", HARP, -8, .45)
    pz = P(s, "pizz", PIZZ, -6, .25, lp=1500)
    tb = n * 4 - 6 * 4                                              # the theme's six bars end the cue
    sn = line_at(c, s, "narrator", 0.1, default=3.0)                # the brothers snatch the coat (first narrator line)
    # bars before the theme: a low pedal, a slow heartbeat, a sinking motif
    harm = ["Gm", "Cm", "Gm", "Cm"]
    for k in range(tb // 4):
        h = harm[k % 4]; bed(strs, cb, k * 4, h, 4, 42, (60, 96), 56)
        tim.add(k * 4, "G2", 1, 58); tim.add(k * 4 + 2, "G2", 1, 44)
    vc.add(0, "G2", 4, 50); vc.vibrato(0, 4, 20)
    mel(vc, sn, [("D4", 1), ("C4", 1), ("Bb3", 2)], 62, legato=.97, vib=True)
    mel(vl, sn + 4, [("G3", 2), ("F#3", 2)], 50, legato=.98, vib=True)
    tim.add(sn - .1, "G2", 1.5, 82); cb.add(sn - .1, "G2", 1.5, 70)
    # the theme in minor
    bars = [1, 2, 3, 4, 7, 8]
    theme_play(eh, tb, bars, 70, minor=True)
    def acc(b, h, beats):
        ps = chord(h)
        pad(strs, b, h, beats, 42, (70, 100)); cb.add(b, low(ps[0]), beats, 54)
        if beats >= 2: pz.add(b, ps[0] + 12, .5, 50)
    theme_chords(tb, bars[:-1], acc, minor=True)
    for i in range(5): tim.add(tb + 4 * i, "G2", 1, 52)
    mel(vc, tb + 16, [("G3", 1.5), ("Bb3", 1.5), ("D4", 1)], 56, legato=.97, vib=True)   # a cello sigh under bar 5 -> 6
    oohs.chord(tb + 4, ["D4", "Bb4"], 12, 30); oohs.ramp(tb + 4, tb + 16, 11, 50, 100)
    # the empty fifth: strings on D-G-D only, the horn's G alone
    bl = tb + 20
    strs.chord(bl, ["D3", "G3", "D4"], E - bl + .3, 46); strs.ramp(bl, E, 11, 85, 70)
    cb.add(bl, "G2", E - bl, 54); vc.add(bl, "D3", E - bl, 44)
    # coins: one soft harp tone, a muted pizzicato for the camel
    coin = when(c, s, "sfx", tb + 3, id="coins")
    harp.add(coin + .2, "D6", 1.5, 34); harp.add(coin + .5, "Bb5", 1.5, 30)
    return s


# ----------------------------------------------------------------------------------------------- prison
def cue_prison(c):
    """Very quiet: one cello in the dark (G minor), a soft low pad, a single harp note for the door's echo. At 'You are
    still with me' the pad turns to G major and a flute breathes the Joseph theme (bars 1-2, softly) with the cello under it."""
    s = Score(c, 60, 4); n = s.bars; E = end_beats(s)
    vc = P(s, "cello", CELLO, -1, .4, lp=2600, human=.012)
    vc2 = P(s, "cello low", CELLO, -5, .4, lp=1800)
    strs = P(s, "strings", SLOW_STR, -9, .6, lp=2500)
    harp = P(s, "harp", HARP, -7, .5)
    fl = P(s, "flute", FLUTE, -3, .5, lp=5000, human=.01)
    oohs = P(s, "oohs", OOHS, -15, .6, lp=3000)
    cb = P(s, "bass", CBASS, -9, .3, lp=800)
    ts = max(8.0, round(line_at(c, s, "joseph", .62, default=16.0) * 2) / 2)      # "...you are still with me"
    mel(vc, .5, [("G3", 2), ("D3", 1), ("Eb3", 1)], 54, legato=.98, vib=True)
    mel(vc, 4.5, [("D3", 1.5), ("C3", .5), ("Bb2", 2)], 52, legato=.98, vib=True)
    mel(vc, 8.5, [("A2", 2.5), ("Bb2", .5), ("A2", 1)], 50, legato=.98, vib=True)
    for k in range(int(ts // 4)): bed(strs, cb, k * 4, ["Gm", "Cm", "Gm"][k % 3], 4, 34, (50, 80), 40)
    door = when(c, s, "sfx", 9.0, id="cell_door"); harp.add(door + .5, "G4", 3, 30)
    glow = when(c, s, "fx", 11.0, id="prayer_glow"); harp.add(glow, "D5", 3, 28); harp.add(glow + 1.5, "Bb4", 3, 26)
    # "you are still with me": G major, the pad opens, the flute and cello remember the tune
    pad(strs, ts - .5, "G", 6, 44, (50, 100)); cb.add(ts - .5, "G2", 6, 44)
    mel(fl, ts, [("G4", 1), ("B4", 1), ("D5", 1.5), ("E5", .5)], 52, legato=.97, vib=True)
    mel(fl, ts + 4, [("D5", 2), ("B4", 1), ("G4", 1)], 48, legato=.97, vib=True)
    mel(vc, ts, [("G3", 1), ("B3", 1), ("D4", 1.5), ("E4", .5), ("D4", 2), ("B3", 1), ("G3", 1)], 50, legato=.98, vib=True)
    harp.chord(ts, ["G3", "D4", "B4"], 4, 34, strum=.1); harp.chord(ts + 4, ["G3", "D4", "G4"], 4, 30, strum=.1)
    oohs.chord(ts + 2, ["D4", "G4", "B4"], E - ts, 28); oohs.ramp(ts + 2, E, 11, 40, 90)
    pad(strs, ts + 5.5, "G", max(1.0, E - ts - 5.5), 40, (80, 100)); cb.add(ts + 5.5, "G2", max(1.0, E - ts - 5.5), 42)
    return s


# ----------------------------------------------------------------------------------------------- pharaoh
PH = {
    1: [("C5", 1), ("C5", .5), ("E5", .5), ("G5", 1), ("E5", 1)],
    2: [("F5", 1), ("F5", .5), ("A5", .5), ("G5", 2)],
    3: [("E5", 1), ("E5", .5), ("G5", .5), ("C6", 1), ("G5", 1)],
    4: [("F5", 1), ("E5", 1), ("D5", 2)],
    5: [("C5", .5), ("D5", .5), ("E5", .5), ("F5", .5), ("G5", 1), ("G5", 1)],
    6: [("A5", 1), ("G5", 1), ("E5", 1), ("C5", 1)],
}
PH_HARM = {1: ["C"], 2: ["F", "C"], 3: ["C"], 4: ["F", "G"], 5: ["C"], 6: ["F", "C"]}


def cue_pharaoh(c):
    """Pharaoh's palace: a pompous, slow, slightly silly march in C (tuba + bassoon oom-pah, sistrum and side drum, a muted
    trumpet and clarinet strutting the tune, the king's snore at the start). At the second dream cloud the march wobbles:
    the dream motif comes back warped (celesta bent flat, trombone sliding, whole-tone pad), and the cue ends on an open
    G-C-D chord, a question for the next scene."""
    s = Score(c, 82, 4); n = s.bars; E = end_beats(s)
    tuba = P(s, "tuba", TUBA, -3, .25, lp=900)
    bsn = P(s, "bassoon", BASSOON, -3, .25, human=.01)
    tpt = P(s, "muted trumpet", MUTED_TPT, -4, .3, lp=4500, human=.012)
    cl = P(s, "clarinet", CLARINET, -4, .3, human=.01)
    pz = P(s, "pizz", PIZZ, -7, .25)
    sis = P(s, "sistrum", DRUMS, -9, .3, lp=9000)
    dr = P(s, "drums", DRUMS, -11, .25, lp=3200)
    strs = P(s, "strings", SLOW_STR, -8, .5, lp=3200)
    harp = P(s, "harp", HARP, -8, .4)
    tim = P(s, "timpani", TIMPANI, -9, .3, lp=3000)
    cel = P(s, "celesta (warped)", CELESTA, -4, .6, bend=True)
    glk = P(s, "glock (warped)", GLOCK, -6, .6, bend=True)
    tbn = P(s, "trombone", TROMBONE, -2, .3, lp=2500, bend=True)
    bw = P(s, "bassoon (bent)", BASSOON, -2, .25, bend=True, human=.01)
    g = when(c, s, "sfx", 25.0, id="harp_gliss", nth=1)          # the second dream cloud (dream_grain)
    ss = max(12.0, 4 * math.floor(g / 4))                 # the warp starts on the bar line before the second cloud
    # intro: the king snores (bent bassoon + tuba), one bar
    bw.add(0, "G2", 1.6, 52); bw.glide(0, 1.4, 0, -1.5); bw.add(2, "G2", 1.6, 50); bw.glide(2, 3.4, 0, -1.8)
    # the march: tune A (bars 1-4) on the bassoon, then clarinet + muted trumpet; sistrum shake, side drum
    M0 = 4
    nb = int((ss - M0) // 4)
    def pump(b, h, beats):
        ps = chord(h); r = ps[0] if ps[0] >= note("C2") else ps[0] + 12
        for q in range(0, int(beats), 2): tuba.add(b + q, r - (12 if r > note("G2") else 0), .8, 66)
        for q in range(1, int(beats), 2):
            bsn.chord(b + q, [ps[1], ps[3]], .6, 48, strum=.01); pz.add(b + q, ps[1], .3, 46)
    for k in range(nb):
        bar = k % 6 + 1
        if k < 4: mel(bsn, M0 + 4 * k, PH[bar], 66, legato=.7)
        else:
            mel(tpt, M0 + 4 * k, PH[bar], 62, legato=.8, vib=False); mel(cl, M0 + 4 * k, PH[bar], 52, legato=.8, shift=-12)
        theme_chords(M0 + 4 * k, [bar], pump, table=PH_HARM)
        groove(dr, M0 + 4 * k, "D.sTD.sT" if k % 2 == 0 else "D.sTD.tt", .5, MARCH, .9)
        groove(sis, M0 + 4 * k, "ssssssss", .5, {"s": (TAMB, 34)}); groove(sis, M0 + 4 * k, "S.......", .5, {"S": (TRIANGLE, 44)})
        if k % 2 == 0: strs.chord(M0 + 4 * k, ["C4", "E4", "G4"], 4.2, 34); strs.ramp(M0 + 4 * k, M0 + 4 * k + 4, 11, 70, 95)
        else: strs.chord(M0 + 4 * k, ["C4", "F4", "A4"], 4.2, 34)
    tim.add(M0, "C3", 1.5, 70); tim.add(M0 + 4 * nb - 2, "G2", 1.5, 70)
    # warped dream motif: whole-tone pad, bent celesta / glock three notes, sliding trombone, wobbling bassoon
    cs = ss; wob = lambda p_, b0, b1, depth: [p_.bend(b0 + i * .1, depth * math.sin(i * .5) - .25) for i in range(int((b1 - b0) / .1))]
    for ch_, b_ in (("F", cs), ("Gb", cs + 4), ("Eb", cs + 8)):
        pad(strs, b_, ch_, 4.2, 40, (60, 100)); pz.add(b_, chord(ch_)[0], .5, 50)
    wob(cel, cs, E, .35); wob(glk, cs, E, .3)
    mel(cel, g + s.beat(GLISS_SEC) + .4, [("D6", 1), ("Ab6", 1), ("B6", 2.5)], 58, legato=1.2); mel(glk, g + s.beat(GLISS_SEC) + .42, [("D6", 1), ("Ab6", 1), ("B6", 2.5)], 40, legato=1.2)
    mel(cel, cs + 2, [("Gb5", 1.5), ("C6", 1.5)], 44, legato=1.2)
    tbn.add(cs + 1, "G3", 3, 60); tbn.glide(cs + 1, cs + 4, 0, -4)
    tbn.add(cs + 6, "Eb3", 3, 56); tbn.glide(cs + 6, cs + 9, 0, -3)
    bw.add(cs, "C3", 3, 54); bw.glide(cs, cs + 3, 0, 1.2); bw.add(cs + 4, "Gb2", 3, 50); bw.glide(cs + 4, cs + 7, 0, -1.6)
    tim.add(g + 2, "C3", 1, 60)
    for i in range(10): tim.add(E - 6 + i * .5, "G2", .5, 40 + 3 * i)                  # a puzzled roll into the question
    # the open question chord: G - D - C (suspended)
    qb = n * 4 - 4
    pad(strs, qb, "Gsus", E - qb, 46, (80, 100)); harp.chord(qb, ["G3", "D4", "C5"], 3, 38, strum=.12)
    tuba.add(qb, "G2", E - qb, 56)
    return s


# ----------------------------------------------------------------------------------------------- reveal
def cue_reveal(c):
    """Calm, clear harp: arpeggios over a quiet string bed, a celesta ripple and a long flute note (wisdom, no hurry).
    When Joseph explains the dream (the cows) the flute sings the Joseph theme's high bars (5, 6) and settles on G."""
    s = Score(c, 72, 4); n = s.bars; E = end_beats(s)
    harp = P(s, "harp", HARP, -3, .5)
    harp2 = P(s, "harp high", HARP, -9, .5)
    cel = P(s, "celesta", CELESTA, -10, .6)
    fl = P(s, "flute", FLUTE, -4, .45, lp=6000, human=.01)
    cl = P(s, "clarinet", CLARINET, -8, .35, human=.01)
    strs = P(s, "strings", SLOW_STR, -8, .5, lp=3500)
    vc = P(s, "cello", CELLO, -6, .4, lp=3000)
    cb = P(s, "bass", CBASS, -9, .3, lp=1000)
    pz = P(s, "pizz", PIZZ, -9, .25)
    ex = line_at(c, s, "joseph", 0.0, nth=1, default=12.0)             # "God will tell you" -> then the dream's meaning
    tt = 4 * round(ex / 4)                                             # the theme's bars start on the bar line
    tt = min(max(8, tt), n * 4 - 12)
    harm = ["G", "Em", "C", "D", "Em", "C", "G", "G"]
    for k in range(n):
        h = harm[k % len(harm)] if k * 4 < tt - .1 else ["Em", "C", "G"][min(2, k - int(tt // 4))]
        if k == 0: h = "Cmaj7"
        bed(strs, cb, k * 4, h, 4 if k < n - 1 else E - k * 4, 40, (60, 96), 46)
        ps = chord(h)
        for j in range(8): harp.add(k * 4 + j * .5, ps[[0, 1, 3, 2, 3, 2, 1, 3][j]] + (12 if j else 0), 2.2, 56 if j == 0 else 42 + (j % 3) * 3)
        harp2.add(k * 4 + 2, ps[3] + 24, 3, 36)
        if k % 2: cel.add(k * 4 + 3.5, ps[3] + 24, 2, 32)
    mel(fl, 1, [("D5", 3.5)], 50, vib=True); mel(cl, 4.5, [("B4", 3)], 38, vib=True)
    vc.add(0, "C3", 8, 46); vc.vibrato(0, 8, 20)
    for q in (2, 6): pz.add(q, "G3", .4, 40)
    theme_play(fl, tt, [5, 6], 62); mel(fl, tt + 8, [("G5", min(3.5, E - tt - 8)), ], 54, vib=True)
    theme_play(cel, tt, [5], 38, vib=False, shift=12)
    return s


# ----------------------------------------------------------------------------------------------- plenty
def cue_plenty(c):
    """Egypt's good years: while Pharaoh names Joseph governor the harp, sistrum and a hand drum build (roll, shimmer); on the
    `fanfare` SFX (G major, trumpets + timpani) the whole band comes in: the Joseph theme, bars 1-3 and 8, in a bright
    dance on trumpet + flute + shanai over darbuka, sistrum and tambourine, ending on G."""
    s = Score(c, 112, 4); n = s.bars; total = n * 4; E = end_beats(s)
    tpt = P(s, "trumpet", TRUMPET, -4, .3, lp=5500, human=.01)
    fl = P(s, "flute", FLUTE, -4, .4, lp=6500, human=.01)
    sh = P(s, "shanai", SHANAI, -10, .35, lp=3500, human=.01)
    ob = P(s, "oboe", OBOE, -7, .35, human=.01)
    hn = P(s, "horns", HORN, -5, .35, lp=3500)
    harp = P(s, "harp", HARP, -4, .45)
    pz = P(s, "pizz", PIZZ, -5, .25)
    strs = P(s, "strings", STRINGS, -9, .5, lp=4500)
    vc = P(s, "cello", CELLO, -6, .4, lp=2500)
    cb = P(s, "bass", CBASS, -7, .3, lp=1000)
    dr = P(s, "darbuka", DRUMS, -9, .25, lp=4000)
    sis = P(s, "sistrum", DRUMS, -9, .3, lp=9500)
    tim = P(s, "timpani", TIMPANI, -8, .3, lp=3000)
    cel = P(s, "celesta", CELESTA, -12, .6)
    f = when(c, s, "sfx", total * .4, id="fanfare"); f = round(f * 2) / 2
    f = min(max(f, 4), total - 12)
    # before the fanfare: harp arpeggios G - C - D, sistrum shimmer, a drum roll that grows
    pre = [("G", 0), ("C", 4), ("D", 8), ("D", 12)]
    for b_, h in [(b, h) for h, b in pre if b < f - .01]:
        ps = chord(h); d = min(4, f - b_)
        pad(strs, b_, h, d + .2, 36, (60, 100)); cb.add(b_, low(ps[0]), d, 50)
        for j in range(int(d * 2)): harp.add(b_ + j * .5, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.4, 50 if j == 0 else 40 + (j % 2) * 3)
        groove(sis, b_, "s.s.s.s.s.s.s.s.", .5, {"s": (TAMB, 26)}, until=f); groove(dr, b_, "D...t...", .5, DARB, .6, until=f)
    for i in range(int((f - (f - 4)) / .25)): tim.add(f - 4 + i * .25, "G2", .3, 30 + i * 3)
    # on the fanfare: tutti chord, crash, then the dance
    tpt.chord(f, ["D5", "G5", "B5"], 3, 78, strum=.01); hn.chord(f, ["G3", "D4", "B4", "G4"], 4, 62, strum=.02)
    strs.chord(f, ["G4", "D5", "G5", "B5"], 4, 58, strum=.03); strs.ramp(f, f + 4, 11, 90, 110)
    tim.add(f, "G2", 2, 96); dr.add(f, CRASH, 3, 70); cb.add(f, "G2", 4, 66)
    harp.chord(f, ["G3", "D4", "G4", "B4", "D5"], 3, 56, strum=.07)
    bars = [1, 2, 3, 8]
    g0 = f + 1.5
    seq = bars if total - g0 >= 16 else ([1, 2, 8] if total - g0 >= 12 else [1, 8])
    theme_play(tpt, g0, seq, 74, legato=.9, vib=False); theme_play(fl, g0, seq, 56, shift=12, vib=False)
    theme_play(sh, g0, seq, 52, vib=False, legato=.9); theme_play(ob, g0, seq, 40, vib=False)
    def acc(b, h, beats):
        ps = chord(h)
        pz.add(b, ps[0], .5, 66); pz.add(b + 1, ps[2], .3, 50); pz.add(b + 2, ps[1], .5, 60); pz.add(b + 3, ps[2], .3, 50)
        if beats >= 2:
            hn.chord(b + .5, [ps[1], ps[3]], 1, 44, strum=.01); hn.chord(b + 2.5, [ps[1], ps[3]], 1, 44, strum=.01)
            strs.chord(b, [ps[2] + 0, ps[3] + 12], beats + .1, 40); vc.add(b, ps[0] + 12 if ps[0] < note("G2") else ps[0], beats, 52)
        for j in range(int(beats * 2)): harp.add(b + j * .5, ps[[1, 2, 3, 2][j % 4]] + 12, 1.2, 44 + (j % 4 == 0) * 6)
    theme_chords(g0, seq, acc, table={1: ["G"], 2: ["G", "D"], 3: ["C"], 8: ["G"]})
    for i in range(len(seq)):
        groove(dr, g0 + 4 * i, "D.kTt.kT" if i % 2 == 0 else "D.kTD.kT", .5, DARB, .9)
        groove(sis, g0 + 4 * i, "ssssssssssssssss", .25, {"s": (TAMB, 30)}); groove(sis, g0 + 4 * i, "S.......", .5, {"S": (TRIANGLE, 50)})
        groove(sis, g0 + 4 * i, "..C...C.", .5, {"C": (39, 54)})
    cel.chord(g0 + 4 * len(seq) - 3, ["G6", "B6", "D7"], 2, 34, strum=.1)
    tim.add(g0 + 4 * len(seq) - 1.5, "G2", 1.5, 60)
    return s


# ----------------------------------------------------------------------------------------------- famine
def cue_famine(c):
    """Dry and sparse: no pad, no reverb tail to speak of. A lonely reed (oboe) in E minor, a woodblock tick on the off
    beats, single plucked bass notes, one cello harmonic. The `wind_desert` SFX carries the air."""
    s = Score(c, 58, 4); n = s.bars; E = end_beats(s)
    ob = P(s, "oboe", OBOE, -2, .15, lp=3500, human=.015)
    wb = P(s, "woodblock", DRUMS, -6, .1)
    pz = P(s, "pizz", PIZZ, -4, .15, lp=1200)
    vc = P(s, "cello", CELLO, -8, .2, lp=2000)
    hp_ = P(s, "harp", HARP, -10, .2)
    mel(ob, .5, [("E5", 2), ("D5", 1), ("B4", 1), ("C5", 1.5), ("B4", .5), ("A4", 2.5), (None, 1.5), ("B4", 2)], 56, legato=.97, vib=True)
    for b in range(0, n * 4, 4):
        wb.add(b + 1, HI_WOOD, .15, 44); wb.add(b + 3, LO_WOOD, .15, 38)
        pz.add(b, "E2", .4, 62); pz.add(b + 2, "B2", .3, 46)
    vc.add(0, "E3", E, 40); vc.vibrato(0, E, 14)
    hp_.add(n * 4 - 2, "B4", 3, 30); hp_.add(n * 4 - 1, "E5", 3, 26)
    return s


# ----------------------------------------------------------------------------------------------- brothers
def cue_brothers(c):
    """Tense but warm: E minor, a pizzicato / cello pulse and soft timpani under the brothers' plea. The dream motif's three
    bells (celesta) are answered by the first notes of the Joseph theme (flute), twice; the `harp_gliss` cloud opens the
    pad to C and G, and Joseph's recognition is the theme in G major on horn, cello and violins (bars 1-2)."""
    s = Score(c, 80, 4); n = s.bars; total = n * 4; E = end_beats(s)
    pz = P(s, "pizz", PIZZ, -4, .25)
    vc = P(s, "cello", CELLO, -4, .4, lp=3000)
    cb = P(s, "bass", CBASS, -7, .3, lp=1000)
    strs = P(s, "strings", SLOW_STR, -6, .5, lp=3500)
    vln = P(s, "violins", STRINGS, -10, .5, lp=5000)
    cl = P(s, "clarinet", CLARINET, -5, .3, human=.01)
    tim = P(s, "timpani", TIMPANI, -9, .3, lp=2500)
    cel = P(s, "celesta", CELESTA, -8, .6)
    glk = P(s, "glock", GLOCK, -10, .6)
    fl = P(s, "flute", FLUTE, -4, .45, lp=6000, human=.01)
    hn = P(s, "horn", HORN, -4, .35, lp=3500, human=.01)
    harp = P(s, "harp", HARP, -6, .45)
    oohs = P(s, "oohs", OOHS, -13, .6, lp=4000)
    g = when(c, s, "sfx", 10.9, id="harp_gliss"); ge = g + s.beat(GLISS_SEC)
    ta = round(min(ge + .2, total - 8) * 2) / 2
    # tension: Em pulse (pizz E-B), cello sustained, pad; bar line by bar line
    for k in range(int(ta // 4) + 1):
        b = k * 4
        if b >= ta - .01: break
        h = ["Em", "Em", "C"][min(k, 2)]; ps = chord(h)
        pad(strs, b, h, min(4, ta - b) + .2, 38, (60, 96)); cb.add(b, low(ps[0]), min(4, ta - b), 50)
        for q in range(8):
            if b + q * .5 < ta - .5: pz.add(b + q * .5, ps[0] + (12 if q % 2 else 0) if q % 4 else ps[1], .3, 52 if q % 4 == 0 else 40)
        tim.add(b, "E2", 1, 56); tim.add(b + 2, "E2", 1, 42)
    mel(vc, .5, [("E3", 2), ("G3", 1), ("F#3", 1), ("E3", 3)], 54, legato=.98, vib=True)
    # bells question ... theme answer, twice (before the glissando)
    for bq in (.5, 5.0):
        if bq > 1 and bq + 6.5 > g + .6: break
        mel(cel, bq, BELLS, 54, legato=1.2); mel(glk, bq + .02, BELLS, 38, legato=1.2)
        mel(fl, bq + 3.2, [("G4", .75), ("B4", .75), ("D5", 1.5)], 54, legato=.97, vib=True)
    mel(cl, 3.5, [("B3", 2), ("A3", 1), ("G3", 1)], 44, legato=.97, vib=True)
    # glissando window: the pad lifts to C then G (no melody), harp roots
    pad(strs, max(0, g - .5), "C", max(1, ta - g + .5), 42, (70, 104)); cb.add(max(0, g - .5), "C3", max(1, ta - g + .5), 52)
    # recognition: the theme, G major, warm
    theme_play(hn, ta, [1, 2], 66); theme_play(vc, ta, [1, 2], 62, shift=-12); theme_play(vln, ta, [1, 2], 48, shift=12, vib=True)
    theme_chords(ta, [1, 2], lambda b, h, bt: (pad(strs, b, h, bt, 48, (80, 108)), cb.add(b, low(chord(h)[0]), bt, 54),
                                                   [harp.add(b + j * .5, chord(h)[[1, 2, 3, 2][j % 4]] + 12, 1.3, 42) for j in range(int(bt * 2))]))
    for i in range(6): tim.add(ta + 4 * 2 - 3 + i * .5, "G2", .5, 34 + 5 * i)
    bl = ta + 8
    pad(strs, bl, "G", max(1, E - bl), 50, (80, 108)); cb.add(bl, "G2", max(1, E - bl), 56)
    oohs.chord(ta + 2, ["D4", "G4", "B4"], max(2, E - ta - 2), 32); oohs.ramp(ta + 2, E, 11, 50, 100)
    return s


# ----------------------------------------------------------------------------------------------- iam
def cue_iam(c):
    """The peak. Held back: a solo cello and a muted flute begin the Joseph theme and stop before it can finish (G B D ...
    and a breath), a pad and a heartbeat drum wait. On 'I am Joseph' the theme is released at full power: violins and flute
    on the tune, horns, cello and violas under it, choir, harp, a timpani roll into the downbeat; a second lift at the heart
    glow, a G chord at the end."""
    s = Score(c, 66, 4); n = s.bars; total = n * 4; E = end_beats(s)
    vln = P(s, "violins", STRINGS, -3, .5, lp=5500, human=.01)
    vla = P(s, "violas", VIOLA, -4, .45, lp=3500)
    vc = P(s, "cello", CELLO, -2, .4, lp=3000, human=.01)
    cb = P(s, "bass", CBASS, -5, .3, lp=1100)
    strs = P(s, "strings pad", SLOW_STR, -6, .5, lp=3500)
    hn = P(s, "horns", HORN, -3, .4, lp=3500, human=.01)
    fl = P(s, "flute", FLUTE, -4, .45, lp=6500, human=.01)
    ob = P(s, "oboe", OBOE, -9, .4, human=.01)
    oohs = P(s, "oohs", OOHS, -5, .6, lp=4500)
    ch = P(s, "choir", CHOIR, -8, .6, lp=4500)
    harp = P(s, "harp", HARP, -5, .45)
    tim = P(s, "timpani", TIMPANI, -6, .3, lp=3000)
    cel = P(s, "celesta", CELESTA, -10, .6)
    rb = 4 * round(line_at(c, s, "joseph", .55, nth=1, default=8.0) / 4)
    rb = min(max(rb, 4), total - 12)
    cnt = int((total - rb) // 4); seq = {6: [1, 2, 3, 4, 7, 8], 5: [1, 2, 4, 7, 8], 4: [1, 2, 7, 8], 3: [1, 2, 8]}.get(cnt, [1, 2, 8])
    rb = total - 4 * len(seq)
    # held back (G major, soft): the tune's first notes without its destination
    pad(strs, 0, "G", 4.5, 34, (50, 90)); cb.add(0, "G2", 4.5, 40)
    mel(vc, .5, [("G3", 1), ("B3", 1), ("D4", 2)], 52, legato=.98, vib=True)
    harm_pre = ["G", "Em", "C", "D"]
    for k in range(1, int(rb // 4)):
        h = harm_pre[min(k, 3)] if k < rb // 4 - 1 else "D"; pad(strs, k * 4, h, 4.2, 38 + 3 * k, (60, 100)); cb.add(k * 4, low(chord(h)[0]), 4.2, 44 + 3 * k)
    mel(fl, 4.5, [("G4", 1), ("B4", 1), ("D5", 2)], 46, legato=.98, vib=True)
    for k in range(int(rb // 2) - 1): tim.add(k * 2 + 2, "G2", .8, 36 + 2 * k)
    if rb > 8: mel(vc, 8.5, [("G3", 1), ("B3", 1), ("D4", 1), ("E4", 1)], 54, legato=.98, vib=True)
    for i in range(int(2 / .25)): tim.add(rb - 2 + i * .25, "G2", .3, 36 + i * 6)
    # the release
    theme_play(vln, rb, seq, 92, vib=True); theme_play(fl, rb, seq, 62, vib=True, shift=12); theme_play(ob, rb, seq, 50, vib=False)
    theme_play(hn, rb + 8, seq[2:], 72, vib=True)
    theme_play(vc, rb, seq, 76, vib=True, shift=-12); theme_play(vla, rb, seq, 62, vib=True, shift=-12)
    def acc(b, h, beats):
        ps = chord(h)
        pad(strs, b, h, beats, 58, (92, 118)); cb.add(b, low(ps[0]), beats, 66)
        hn.chord(b, [ps[1], ps[3]], beats, 58); hn.ramp(b, b + beats, 11, 92, 112)
        oohs.chord(b, [ps[2], ps[3] + 12], beats + .2, 44); oohs.ramp(b, b + beats, 11, 80, 110)
        ch.chord(b, ps[1:], beats + .2, 40)
        for j in range(int(beats * 2)): harp.add(b + j * .5, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.6, 54 if j == 0 else 42)
    theme_chords(rb, seq[:-1], acc, table={**JOSEPH_HARM, 8: ["G"]})
    # seq is a list of theme bar numbers, so harmony is read per bar number; the final bar rings out below
    tim.add(rb, "G2", 2, 100); tim.add(rb + 4, "G2", 1, 60)
    gl = when(c, s, "fx", rb + 9, id="heart_glow")
    for i in range(int(3 / .25)): tim.add(gl - 1 + i * .25, "G2", .3, 40 + i * 5)
    run(harp, gl, scale_run("G4", "G6"), .14, 56, 2); cel.chord(gl + 2, ["D6", "G6", "B6"], 3, 40, strum=.15)
    bl = total - 4
    pad(strs, bl, "G", E - bl, 60, (100, 110)); cb.add(bl, "G2", E - bl, 66); tim.add(bl, "G2", 3, 70)
    hn.chord(bl, ["D4", "G4", "B4"], E - bl, 60); oohs.chord(bl, ["D5", "G5", "B5"], E - bl, 46)
    return s


# ----------------------------------------------------------------------------------------------- reunion
def cue_reunion(c):
    """A slow waltz (3/4), tearful and happy at once: harp and pizzicato 'oom-pah-pah', the Joseph theme (waltz form, six
    bars) on violins + flute with a cello counter-melody and oboe sighs; Jacob's cry swells strings and horns; a celesta
    note of the dream motif at the golden rays; a held G."""
    s = Score(c, 76, 3); n = s.bars; total = n * 3; E = end_beats(s)
    vln = P(s, "violins", STRINGS, -5, .5, lp=5500, human=.01)
    fl = P(s, "flute", FLUTE, -5, .45, lp=6500, human=.01)
    vc = P(s, "cello", CELLO, -5, .4, lp=3000, human=.01)
    ob = P(s, "oboe", OBOE, -7, .4, human=.012)
    hp_ = P(s, "harp", HARP, -4, .45)
    pz = P(s, "pizz", PIZZ, -6, .25)
    strs = P(s, "strings", SLOW_STR, -7, .5, lp=3500)
    cb = P(s, "bass", CBASS, -8, .3, lp=1000)
    hn = P(s, "horn", HORN, -6, .35, lp=3500)
    cel = P(s, "celesta", CELESTA, -10, .6)
    oohs = P(s, "oohs", OOHS, -10, .6, lp=4000)
    tab, hab = JOSEPH_34, JOSEPH_34_HARM
    tb = total - 18 if total >= 18 else 0
    seq = list(range(1, 7))
    theme_play(vln, tb, seq, 70, bpb=3, table=tab); theme_play(fl, tb, seq, 54, bpb=3, table=tab, shift=12, vib=False)
    theme_play(vc, tb + 9, [4, 5], 56, bpb=3, table=tab, shift=-12)
    def acc(b, h, beats):
        ps = chord(h)
        hp_.add(b, ps[0], 3, 62); hp_.chord(b + 1, [ps[1] + 12, ps[2] + 12, ps[3] + 12], 1, 44, strum=.03); hp_.chord(b + 2, [ps[1] + 12, ps[2] + 12, ps[3] + 12], 1, 40, strum=.03)
        pz.add(b, low(ps[0]), .5, 60); cb.add(b, low(ps[0]), beats, 46)
        pad(strs, b, h, beats, 38, (60, 100))
    theme_chords(tb, seq, acc, bpb=3, table=hab)
    mel(ob, tb + 6, [("B4", 1), ("A4", 1), ("G4", 1)], 46, legato=.98, vib=True)
    jc = when(c, s, "lines", tb + 9, who="jacob")
    jb = 3 * math.floor((jc - 0.5) / 3) if jc > 0 else tb + 9
    hn.chord(jb, ["D4", "G4", "B4"], 9, 50); hn.ramp(jb, jb + 9, 11, 70, 105)
    oohs.chord(jb, ["D5", "G5", "B5"], 9, 38); oohs.ramp(jb, jb + 9, 11, 50, 100)
    gr = when(c, s, "fx", total - 4, id="golden_rays"); cel.add(gr, "G6", 3, 40); cel.add(gr + 1.5, "B6", 3, 34)
    bl = total - 3
    pad(strs, bl, "G", E - bl, 52, (90, 106)); strs.chord(bl, ["G3", "D4", "B4"], E - bl, 44); cb.add(bl, "G2", E - bl, 56)
    hp_.chord(bl, ["G3", "D4", "G4", "B4"], 3, 46, strum=.08)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """Full statement of the Joseph theme (eight bars) building from flute + harp to the whole orchestra, with the dream motif
    on top: bell notes at the start of each four-bar half, a harp glissando into the last bar and the three bells on the
    final held G major chord."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4; E = end_beats(s)
    fl = P(s, "flute", FLUTE, -3, .4, lp=6500, human=.01)
    tpt = P(s, "trumpet", TRUMPET, -7, .3, lp=5000, human=.01)
    vln = P(s, "violins", STRINGS, -3, .5, lp=5500, human=.01)
    vla = P(s, "violas", VIOLA, -5, .45, lp=3500)
    vc = P(s, "cello", CELLO, -4, .4, lp=3000)
    cb = P(s, "bass", CBASS, -6, .3, lp=1100)
    hn = P(s, "horns", HORN, -4, .35, lp=3500, human=.01)
    harp = P(s, "harp", HARP, -4, .45)
    pz = P(s, "pizz", PIZZ, -6, .25)
    strs = P(s, "strings pad", SLOW_STR, -6, .5, lp=3500)
    oohs = P(s, "oohs", OOHS, -6, .6, lp=4500)
    ch = P(s, "choir", CHOIR, -9, .6, lp=4500)
    tim = P(s, "timpani", TIMPANI, -7, .3, lp=3000)
    dr = P(s, "drums", DRUMS, -12, .25, lp=3500)
    cel = P(s, "celesta", CELESTA, -8, .6)
    glk = P(s, "glock", GLOCK, -10, .6)
    b0 = total - 32 if total >= 32 else 0
    seq = list(range(1, 9))
    theme_play(fl, b0, seq, 70, vib=True); theme_play(fl, b0 + 16, seq[4:], 62, vib=True, shift=12)
    theme_play(vln, b0 + 8, seq[2:], 80, vib=True); theme_play(tpt, b0 + 16, seq[4:], 76, vib=False, legato=.9)
    theme_play(hn, b0 + 16, seq[4:], 68, vib=True, shift=-12); theme_play(vc, b0 + 8, seq[2:], 62, vib=True, shift=-12)
    theme_play(vla, b0 + 16, seq[4:], 58, vib=True, shift=-12)
    def acc(b, h, beats):
        ps = chord(h); lvl = (b - b0) / 32
        nyl(harp, b, h, beats, 46 + int(10 * lvl), pat=(0, 2, 3, 1, 3, 2, 3, 1), up=12)
        pz.add(b, ps[0], .5, 62); pz.add(b + 2, ps[1], .4, 54)
        if lvl >= .25:
            pad(strs, b, h, beats, 44 + int(14 * lvl), (80, 112)); cb.add(b, low(ps[0]), beats, 56 + int(10 * lvl))
        if lvl >= .5:
            oohs.chord(b, [ps[2], ps[3] + 12], beats + .2, 40); oohs.ramp(b, b + beats, 11, 80, 112)
            ch.chord(b, ps[1:], beats + .2, 36)
        if lvl >= .5 and beats >= 2: hn.chord(b, [ps[1], ps[3]], beats, 52)
    theme_chords(b0, seq[:-1], acc)
    groove(dr, b0 + 8, "D...D.t." * 4, .5, FRAME, .9); groove(dr, b0 + 16, "D.kTD.kT" * 4, .5, DARB, .8)
    tim.add(b0 + 16, "G2", 2, 80); dr.add(b0 + 16, CRASH, 3, 64)
    for k in (b0 + 8, b0 + 24): tim.add(k, "G2", 1.5, 64)
    # the dream motif on top
    for bq, v in ((b0 + 2, 42), (b0 + 12, 52), (b0 + 20, 58)): mel(cel, bq, BELLS, v, legato=1.2); mel(glk, bq + .02, BELLS, v - 14, legato=1.2)
    gg = b0 + 28 - 3                                                                 # the glissando lands on the last bar
    run(harp, gg, scale_run("G3", "G6"), .1, 60, 2.5)
    bl = b0 + 28
    pad(strs, bl, "G", E - bl, 64, (100, 112)); strs.chord(bl, ["G3", "D4", "G4", "B4"], E - bl + .3, 52)
    cb.add(bl, "G2", E - bl, 70); tim.add(bl, "G2", 3, 78)
    hn.chord(bl, ["D4", "G4", "B4"], E - bl, 58); oohs.chord(bl, ["D5", "G5", "B5"], E - bl, 48); ch.chord(bl, ["G4", "D5", "G5"], E - bl, 42)
    mel(cel, bl + .5, BELLS, 62, legato=1.5); mel(glk, bl + .52, BELLS, 46, legato=1.5)
    harp.chord(bl, ["G3", "D4", "G4", "B4", "D5", "G5"], 3, 52, strum=.06)
    return s


# =============================================================================================== loop sections
VAMP = {"home": ("G", "pluck"), "dream": ("G", "bells"), "betrayal": ("G5", "bare"), "prison": ("G", "hush"),
        "pharaoh": ("Gsus", "hush"), "reveal": ("G", "bed"), "plenty": ("G", "dance"), "famine": ("Em", "dry"),
        "brothers": ("G", "bed"), "iam": ("G", "choir"), "reunion": ("G", "waltz"), "finale": ("G", "choir")}


def arp_steps(s): return (s.bpb * 2, .5) if s.bpb in (3, 4) else (s.bpb, 1.0)


def add_vamp(s, chord_name, style):
    """After the cadence: identical repeats of >= VAMP_MIN_SEC (whole bars, no humanising). See music_ruth.py."""
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    reps = max(4, math.ceil((STRETCH * s.span + XFADE + 2.5) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    quiet = style in ("hush", "bare", "dry")
    padp = P(s, "vamp pad", SLOW_STR, -6, .5, lp=3500 if not quiet else 2200, **v)
    cb = P(s, "vamp bass", CBASS, -10, .3, lp=1100, **v)
    harp = P(s, "vamp harp", HARP, -8, .45, **v)
    extra = {}
    if style == "pluck":
        extra["ny"] = P(s, "vamp nylon", NYLON, -9, .3, **v); extra["dr"] = P(s, "vamp frame drum", DRUMS, -15, .2, lp=3000, **v)
    if style == "dance":
        extra["pz"] = P(s, "vamp pizz", PIZZ, -7, .25, **v); extra["dr"] = P(s, "vamp darbuka", DRUMS, -13, .2, lp=3500, **v)
    if style == "waltz": extra["pz"] = P(s, "vamp pizz", PIZZ, -8, .25, **v)
    if style == "dry":
        extra["pz"] = P(s, "vamp pizz", PIZZ, -6, .2, **v); extra["wb"] = P(s, "vamp blocks", DRUMS, -10, .1, **v)
    if style == "bells": extra["cel"] = P(s, "vamp celesta", CELESTA, -16, .6, **v)
    if style == "choir":
        extra["oohs"] = P(s, "vamp oohs", OOHS, -14, .6, lp=4000, **v); extra["ch"] = P(s, "vamp choir", CHOIR, -17, .6, lp=3500, **v)
    for p_ in [padp, cb, harp] + list(extra.values()): p_.vamp = True
    ps = chord(chord_name); steps, st = arp_steps(s); b0 = s.bars * bpb
    for r in range(reps):
        b = b0 + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 34 if quiet else 46); padp.cc(b, 11, 92)
        cb.add(b, low(ps[0]), Lb + .2, 42 if quiet else 48)
        if style == "choir":
            extra["oohs"].chord(b, [ps[1] + 12, ps[3]], Lb + .3, 40); extra["oohs"].cc(b, 11, 92)
            extra["ch"].chord(b, ps[1:], Lb + .3, 34); extra["ch"].cc(b, 11, 92)
        for bar in range(nb):
            bb = b + bar * bpb
            if style in ("bed", "bells", "choir", "pluck", "dance"):
                for j in range(steps): harp.add(bb + j * st, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + 12, 1.4, 44 if j else 50)
            if style in ("hush", "bare"):
                harp.add(bb, ps[[3, 2, 1, 2][bar % 4]] + 12, 3, 30 if style == "hush" else 26); harp.add(bb + 2, ps[1] + 24, 3, 22)
            if style == "pluck":
                for j in range(int(bpb * 2)): extra["ny"].add(bb + j * .5, ps[[0, 2, 3, 1, 3, 2, 3, 1][j % 8]], 1.1, 44 if j % 4 == 0 else 34)
                groove(extra["dr"], bb, "D..tD.t.", .5, FRAME, .7)
            if style == "dance":
                for q in range(bpb): extra["pz"].add(bb + q, ps[0] if q % 2 == 0 else ps[1], .3, 54)
                groove(extra["dr"], bb, "D.kTt.kT", .5, DARB, .55)
            if style == "waltz":
                extra["pz"].add(bb, low(ps[0]), .4, 52)
                for q in (1, 2): harp.chord(bb + q, [ps[1] + 12, ps[2] + 12, ps[3] + 12], 1, 34, strum=.03)
            if style == "dry":
                extra["pz"].add(bb, ps[0], .4, 56); extra["pz"].add(bb + 2, ps[1], .3, 40)
                extra["wb"].add(bb + 1, HI_WOOD, .15, 36); extra["wb"].add(bb + 3, LO_WOOD, .15, 30)
        if style == "bells": extra["cel"].add(b + bpb, ps[3] + 24, 2, 34)
    s.secs = s.span + reps * L + 2.5
    s.vamp = dict(start=s.span, secs=L, reps=reps, bars=nb, chord=chord_name, style=style)


def render_split(s):
    """Score.render, but the cue and its loop section come back separately (each with its own hall send), every stem first
    levelled to its part's target (REF_DB + gain_db) over the stretches where it plays."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex: stems = list(ex.map(lambda p: p.render(), s.parts))
    n = max(len(x) for x in stems); out = {}
    for key in (False, True):
        dry = np.zeros(n); bus = np.zeros(n)
        for p_, x in zip(s.parts, stems):
            if getattr(p_, "vamp", False) != key: continue
            lv = active_db(x)
            if lv is None: continue
            x = x * 10 ** ((REF_DB + p_.rel - lv) / 20)
            dry[:len(x)] += x; bus[:len(x)] += x * p_.send
            if me.STEM_REPORT: print(f"    stem {p_.name:24s} playing {REF_DB + p_.rel:6.1f} dB   rms overall {20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9):6.1f} dB")
        out[key] = dry + signal.fftconvolve(bus, me.IRS["hall"]())[:n]
    return out[False], out[True]


def clean_tmp():
    """music_kit's renderer leaves one temp dir per stem: keep them in our run dir and empty it after each cue."""
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith(TMP_PREFIX):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


def lufs_of(x):
    tmp = tempfile.mkdtemp() + "/m.wav"; wavfile.write(tmp, SR, np.asarray(x, np.float32)); return me.measure(tmp)




MUSIC = {"home": cue_home, "dream": cue_dream, "betrayal": cue_betrayal, "prison": cue_prison, "pharaoh": cue_pharaoh,
         "reveal": cue_reveal, "plenty": cue_plenty, "famine": cue_famine, "brothers": cue_brothers, "iam": cue_iam,
         "reunion": cue_reunion, "finale": cue_finale}
METER = {"reunion": "3/4"}
KEYS = {"home": "G major", "dream": "G lydian / G major", "betrayal": "G minor, ends on an empty fifth", "prison": "G minor -> G major",
        "pharaoh": "C major, then whole-tone, ends G-D-C", "reveal": "G major", "plenty": "G major", "famine": "E minor",
        "brothers": "E minor -> G major", "iam": "G major", "reunion": "G major", "finale": "G major"}
CUE_NOTES = {
    "home": "Flute calls over nylon arpeggios, then plays the Joseph theme (bars 1-8); frame drum, cello, violins from bar 5 of the theme; harp glint on the coat sparkle, grumpy bassoon under the brother's line.",
    "dream": "G major seventh pad + oohs, three celesta / glock bells after each `harp_gliss` (never over it), playful clarinet / pizz / xylophone under the brother's outburst, flute breathes the theme's bars 1-2 for the sun, moon and stars.",
    "betrayal": "Low strings, viola, soft heartbeat timpani; from the caravan the Joseph theme in G minor on English horn (bars 1-4, 7, 8) with strings and a cello sigh; last bar: empty fifth (D-G-D) and the horn's lone G.",
    "prison": "One quiet cello in G minor, a thin pad, single harp notes at the door and the prayer glow; at 'You are still with me' the pad turns to G major, flute + cello breathe the theme's bars 1-2.",
    "pharaoh": "Slow pompous C major march: tuba + bassoon oom-pah, side drum, sistrum shake, bassoon then clarinet + muted trumpet on the march tune; snoring bent bassoon; from the second dream cloud: whole-tone pad, bent celesta / glock bells (D-Ab-B), sliding trombone, timpani roll, open G-D-C chord.",
    "reveal": "Clear harp arpeggios over a quiet string bed, celesta ripples, long flute and clarinet notes; flute sings the theme's high bars 5-6 when Joseph explains the dream, settles on G.",
    "plenty": "Harp arpeggios + sistrum + drum roll building to the `fanfare` SFX; then tutti G chord and the theme (bars 1-3, 8) on trumpet + flute + shanai + oboe over darbuka, sistrum, tambourine, claps.",
    "famine": "Dry and sparse: lone oboe in E minor, woodblock on the off-beats, plucked bass, one cello drone, two harp notes; the `wind_desert` SFX carries the air.",
    "brothers": "E minor pulse (pizz + timpani); celesta bells (dream motif) answered by flute fragments of the theme; the pad lifts to C around the `harp_gliss`; Joseph's recognition: theme bars 1-2 in G major on horn, cello, violins, choir.",
    "iam": "Theme held back (cello, flute stop at D, heartbeat drum, rising pad), released at 'I am Joseph' in full strings, flute, oboe, horns, choir, harp, timpani; second lift at the heart glow; G chord.",
    "reunion": "3/4 waltz: harp + pizz oom-pah-pah, theme (waltz form) on violins + flute, cello counter-line, oboe sighs, horns and oohs swell at Jacob's cry, celesta note at the golden rays; held G.",
    "finale": "Full theme (8 bars) building from flute + harp to the whole orchestra with timpani, drums, trumpet; dream-motif bells every four bars, a harp glissando into the last bar, three bells on the final held G chord.",
}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG
place_ = lambda dst, src, at: me.place(dst, src, at)
GLISS_SEC = 3.6                                           # length of harp_gliss.wav: cues leave this much room after it starts


def gm_render(events, secs):
    """A few GM notes from the DLS bank (like music_kit.gm_notes) with the sustain fix for winds / voices / brass.
    events: (t_sec, dur_sec, pitch, vel, program)."""
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
    roughness (irregular AM at ~rough_hz), breath noise, through moving formants (`scale` < 1 = bigger animal)."""
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




# ----------------------------------------------------------------------------------------------- sheep_baa
def sfx_sheep_baa(ctx):
    """A lamb's bleat: 'baa-aa-aa', a small animal's voice (high formants, 26 Hz flutter, a quick break up at the start)."""
    secs = 1.2; n = int(secs * SR)
    v = creature(.95, [(0, 360), (.06, 470), (.45, 440), (.95, 330)], [(0, "eh"), (.25, "a"), (.8, "eh")], 1.4, rough=.75, rough_hz=27,
                 breath=.2, jitter=.035, tilt=1.1, amp_pts=[(0, 0), (.04, 1), (.7, .85), (.95, 0)], lp_hz=5000)
    y = np.zeros(n); place_(y, v / (np.std(v) + 1e-9) * .5, .03)
    return me.fit(me.room(y, "room", .12), secs, fade_out=.15)


# ----------------------------------------------------------------------------------------------- harp_gliss
def sfx_harp_gliss(ctx):
    """The dream motif: a harp glissando up G lydian (G3 to G6, 22 notes, 45 ms apart, swelling) into three bell notes
    D6-G6-B6 (celesta + glockenspiel + a soft tubular bell), airy shimmer, hall. One file: identical every time."""
    secs = GLISS_SEC; ev = []
    pitches = scale_run("G3", "G6", G_LYD)
    for i, p_ in enumerate(pitches): ev.append((.02 + i * .045, 1.6, p_, 58 + 36 * i / (len(pitches) - 1), HARP))
    t0 = .02 + len(pitches) * .045 + .1
    for k, p_ in enumerate(("D6", "G6", "B6")):
        ev.append((t0 + k * .3, 2.0, p_, 84, CELESTA)); ev.append((t0 + k * .3, 2.0, p_, 70, GLOCK))
        ev.append((t0 + k * .3, 1.2, nm(note(p_) - 12), 46, TUBULAR))
    x = gm_render(ev, secs); n = len(x)
    t = np.arange(n) / SR
    x += me.hp(noise(n), 5500) * np.exp(-((t - t0 - .3) / .45) ** 2) * .004
    return me.fit(me.room(x, "hall", .38), secs, fade_out=.8)


# ----------------------------------------------------------------------------------------------- camel_grunt
def sfx_camel_grunt(ctx):
    """A camel's grumble: a low, rough 'brrruhh' (formant voice 110 to 60 Hz with a sub-octave), a lip flutter and a snort."""
    secs = 1.0; n = int(secs * SR)
    v = creature(.7, [(0, 100), (.1, 125), (.4, 92), (.7, 58)], [(0, "o"), (.35, "ah"), (1, "u")], .72, rough=.95, rough_hz=34,
                 breath=.4, sub=.5, amp_pts=[(0, 0), (.05, 1), (.45, .9), (.7, 0)], lp_hz=3000)
    y = np.zeros(n); place_(y, v / (np.std(v) + 1e-9) * .5, .04)
    sn = me.bp(noise(int(.25 * SR)), 400, 3000) * me.env_exp(int(.25 * SR), .06) * (1 + .6 * np.sin(2 * np.pi * 48 * np.arange(int(.25 * SR)) / SR))
    place_(y, sn * .35, .72)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.12)


# ----------------------------------------------------------------------------------------------- coins
def sfx_coins(ctx):
    """A handful of silver coins poured into a palm: bouncing clinks (inharmonic bell partials 2-3.6 kHz) that speed up and
    settle, with a soft leather purse thump underneath."""
    secs = 1.7; n = int(secs * SR); y = np.zeros(n)
    at = .02; gap = .16
    for i in range(14):
        f = R().uniform(2100, 3600)
        b = bell(.35, f, [1, 2.32, 4.25, 6.63], [1, .7, .45, .25], [.1, .06, .04, .02], strike=.5)
        place_(y, b * R().uniform(.4, 1.0) * (1 - i * .03), at)
        at += gap * R().uniform(.8, 1.2); gap *= .84
    th = me.lp(noise(int(.12 * SR)), 500) * me.env_exp(int(.12 * SR), .03); place_(y, th * .6, .02)
    for k in range(3): place_(y, bell(.5, R().uniform(2400, 3300), [1, 2.4, 5.0], [1, .5, .25], [.18, .1, .05], strike=.3) * .45, 1.0 + k * .12)
    return me.fit(me.room(y, "room", .2), secs, fade_out=.3)


# ----------------------------------------------------------------------------------------------- cell_door
def sfx_cell_door(ctx):
    """A wooden prison door: a slow rusty creak (formant voice, 80-140 Hz creaky) that swings shut with a dull thud, a metal
    latch click and a short iron ring. Heavy but not scary."""
    secs = 2.2; n = int(secs * SR)
    cr = creature(1.0, [(0, 85), (.3, 120), (.6, 150), (1.0, 105)], [(0, "i"), (.5, "e"), (1, "i")], .9, rough=1.0, rough_hz=17,
                  breath=.5, tilt=.9, amp_pts=[(0, 0), (.2, .7), (.7, 1), (1.0, 0)], lp_hz=3200)
    y = np.zeros(n); place_(y, cr / (np.std(cr) + 1e-9) * .3, .04)
    m = int(.5 * SR); tt = np.arange(m) / SR
    thud = np.sin(2 * np.pi * np.cumsum(120 * np.exp(-tt / .08) + 45) / SR) * np.exp(-tt / .12) + me.lp(noise(m), 800) * np.exp(-tt / .05) * .6
    place_(y, thud * 1.0, 1.1)
    k = int(.08 * SR); click = me.bp(noise(k), 1500, 5000) * me.env_exp(k, .008); place_(y, click * .5, 1.45)
    place_(y, bell(.9, 640, [1, 2.7, 5.1], [1, .35, .15], [.4, .15, .06], strike=.2) * .18, 1.47)
    return me.fit(me.room(y, "room", .22), secs, fade_out=.4)


# ----------------------------------------------------------------------------------------------- moo
def sfx_moo(ctx):
    """A comic cow: 'mooo-oo' (formant voice 150-180-120 Hz, o to u with a hint of ah, wobble, sub-octave), short."""
    secs = 1.5; n = int(secs * SR)
    v = creature(1.15, [(0, 140), (.18, 178), (.7, 168), (1.15, 112)], [(0, "u"), (.2, "o"), (.5, "ah"), (.9, "o"), (1, "u")], .78,
                 rough=.3, rough_hz=19, breath=.14, sub=.35, jitter=.02, amp_pts=[(0, 0), (.08, 1), (.8, .9), (1.15, 0)], lp_hz=3200)
    v *= 1 + .12 * np.sin(2 * np.pi * 5.5 * np.arange(len(v)) / SR)
    y = np.zeros(n); place_(y, v / (np.std(v) + 1e-9) * .5, .03)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.2)


# ----------------------------------------------------------------------------------------------- fanfare
def sfx_fanfare(ctx):
    """Pharaoh's herald: two trumpets and horns in G major, 'ta-ta-ta-TAAA' (D5 D5 G5 then B5 held, a third below), a
    timpani G, a cymbal wash, in the hall. The score's `plenty` cue arrives on its last chord."""
    secs = 3.4; ev = []
    for t_, d_, p_, v_ in ((0, .2, "D5", 100), (.24, .2, "D5", 100), (.48, .24, "G5", 104), (.8, 1.9, "B5", 110)):
        ev.append((t_, d_, p_, v_, TRUMPET))
    for t_, d_, p_, v_ in ((0, .2, "B4", 86), (.24, .2, "B4", 86), (.48, .24, "D5", 90), (.8, 1.9, "G5", 96)):
        ev.append((t_, d_, p_, v_, TRUMPET))
    for p_ in ("G3", "D4", "G4", "B4"): ev.append((.8, 2.0, p_, 80, HORN))
    ev += [(.8, 1.0, "G2", 110, TIMPANI), (0, .2, "G2", 80, TIMPANI), (.48, .3, "G2", 90, TIMPANI)]
    x = gm_render(ev, secs); n = len(x); t = np.arange(n) / SR
    cym = me.hp(noise(n), 3500) * np.exp(-np.maximum(t - .8, 0) / .7) * (t > .8) * .06
    return me.fit(me.room(x + cym, "hall", .3), secs, fade_out=.9)


# ----------------------------------------------------------------------------------------------- soft_chime
def sfx_soft_chime(ctx):
    """Joy: four soft warm chime notes G5-B5-D6-E6 (the Joseph theme's opening), felt strikes, a little air."""
    secs = 3.2; n = int(secs * SR); y = np.zeros(n)
    for i, p_ in enumerate(("G5", "B5", "D6", "E6")):
        f = 440 * 2 ** ((note(p_) - 69) / 12)
        b = bell(2.7, f, [1, 2.0, 2.76, 4.1], [1, .25, .18, .06], [1.3, .7, .5, .25])
        place_(y, b * (.8 + .06 * i), .02 + i * .22 + R().normal(0, .005))
    y += me.hp(noise(n), 5000) * np.exp(-((np.arange(n) / SR - .5) / .45) ** 2) * .03
    return me.fit(me.room(y, "hall", .4), secs, fade_out=.9)


# ----------------------------------------------------------------------------------------------- wind_desert
LOOP_SECS = {"wind_desert": 10.0}                       # whole-file seamless loop
WRAP = 0.6


def make_loop(y, secs):
    """y is secs + WRAP long; fold the overhang onto the start so the end flows into the beginning."""
    n, k = int(secs * SR), int(WRAP * SR); out = y[:n].copy(); w = np.linspace(0, 1, k)
    out[:k] = y[:k] * np.sqrt(w) + y[n:n + k] * np.sqrt(1 - w)
    return out


def wind_bed(secs):
    n = int(secs * SR); t = np.arange(n) / SR
    gust = np.clip(.55 + .45 * me.smooth_rand(n, .35), .1, 1.2)
    low = me.bp(noise(n), 110, 650) * 1.0 * gust
    mid = me.bp(noise(n), 650, 2400) * .25 * gust ** 2
    sand = me.hp(noise(n), 3500) * .1 * gust ** 3
    whistle = 0.0
    for fc, a in ((470, .07), (790, .04)):
        am = np.clip(.5 + .5 * me.smooth_rand(n, .5), 0, 1) ** 2
        whistle = whistle + me.bp(noise(n), fc * .97, fc * 1.03) * a * am * 6
    return low + mid + sand + whistle


def sfx_wind_desert(ctx):
    """10 s seamless desert wind: a low moan with slow gusts, a thin hiss of blown sand, two faint whistling tones; wrap-folded."""
    return make_loop(wind_bed(LOOP_SECS["wind_desert"] + WRAP), LOOP_SECS["wind_desert"])


SFX = {"sheep_baa": sfx_sheep_baa, "sparkle": lambda ctx: me.sfx_sparkle(), "harp_gliss": sfx_harp_gliss, "camel_grunt": sfx_camel_grunt,
       "coins": sfx_coins, "cell_door": sfx_cell_door, "moo": sfx_moo, "fanfare": sfx_fanfare, "wind_desert": sfx_wind_desert,
       "soft_chime": sfx_soft_chime}
SFX_SEED = {}
# SFX are not ducked by the engine (they play on top of speech at gainDb), so 2026-11-15: gains 2-4 dB lower, long tails
# shaped away (SFX_SHAPE = seconds kept, then decay time constant); the punchy front stays at the same peak.
SFX_GAIN = {"sheep_baa": -10, "sparkle": -12, "harp_gliss": -12, "camel_grunt": -11, "coins": -12, "cell_door": -11, "moo": -11,
            "fanfare": -7, "wind_desert": -20, "soft_chime": -13}
SFX_SHAPE = {"harp_gliss": (2.3, 0.9), "cell_door": (0.8, 0.7), "soft_chime": (0.9, 0.6), "sparkle": (0.7, 0.5),
             "coins": (0.6, 0.5)}
SFX_NOTES = {"sheep_baa": "comic lamb bleat: formant voice 330-470 Hz, 26 Hz flutter, 'eh-a-eh'; 1.2 s",
             "sparkle": "the kit's D major pentatonic bell shower (D E F# A B all lie in G major), hall",
             "harp_gliss": "THE dream motif: harp glissando G3-G6 on G lydian (22 notes) then celesta + glock + tubular bells D6-G6-B6; one file, identical at every cloud (5 uses)",
             "camel_grunt": "rough low 'brrruhh' (100-58 Hz formant voice + sub-octave), lip flutter, small snort; 1.0 s",
             "coins": "14 bouncing coin clinks (inharmonic partials 2.1-3.6 kHz) speeding up and settling, purse thump",
             "cell_door": "creaky formant-voice door swing, dull thud, latch click, short iron ring; same file for shut (93 s) and open (136 s)",
             "moo": "comic cow: formant voice 140-178-112 Hz, o-ah-u, 5.5 Hz wobble, sub-octave; 1.5 s",
             "fanfare": "two trumpets + horns + timpani, G major 'ta-ta-ta-TAAA', cymbal wash, hall; the `plenty` cue lands on it",
             "wind_desert": "seamless 10 s loop (wrap-folded): low moan with slow gusts, blown-sand hiss, two faint whistles; stops at `brothers`",
             "soft_chime": "four warm chime notes G5-B5-D6-E6 (the theme's opening), felt strikes, hall"}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3), secs=round(end - c["t"] + XFADE, 3),
                        last=i + 1 == len(cues)))
    return out


def cue_files(spans):
    """One file per cue name; a cue that plays more than once (call) is composed for its longest occurrence."""
    files = {}
    for c in spans: files.setdefault(c["cue"], dict(cue=c["cue"], occ=[]))["occ"].append(c)
    for f in files.values(): f["primary"] = max(f["occ"], key=lambda c: c["span"])
    return files


def render_cue(tl, name, c):
    me.seed("joseph/" + name); ctx = Ctx(tl, name, c["t"], c["span"], c["secs"], c["last"])
    sc = MUSIC[name](ctx)
    add_vamp(sc, *VAMP[name]); vp = sc.vamp
    main, vamp = render_split(sc)
    n = int(round(sc.secs * SR)); main = me.hp(me.fit(main, sc.secs, fade_out=0), 45); vamp = me.hp(me.fit(vamp, sc.secs, fade_out=0), 45)
    main, vamp = mp.pocket(main), mp.pocket(vamp)                         # speech pocket (900 Hz, 2.4 kHz)
    hits = [t - c["t"] for kind, ids in (("sfx", HIT_SFX), ("fx", HIT_FX)) for e in tl[kind] if e["id"] in ids
            for t in [e["t"]] if 0 <= t - c["t"] <= c["span"]]
    if name in NO_SWELL: hits = []                                        # cue is reused / hit lands under speech
    main = main * mp.underscore(len(main), hits)   # breathe under the story, swell on the hits
    if name in DIPS: main = main * mp.dips(len(main), DIPS[name])
    if c["t"] > 0.5: kf = int(.3 * SR); main[:kf] *= np.linspace(0, 1, kf) ** 1.5       # soft entry, no hard cut-in
    ns, ls, le = int(c["span"] * SR), int(round((vp["start"] + vp["secs"]) * SR)), int(round((vp["start"] + 2 * vp["secs"]) * SR))
    # loop tile = the second repeat as rendered (steady state), first 30 ms blended from the true continuation
    L = le - ls; kx = int(.03 * SR); w = np.linspace(0, 1, kx)
    T = vamp[ls:le].copy(); T[:kx] = vamp[le:le + kx] * (1 - w) + vamp[ls:ls + kx] * w
    vs = np.zeros(n); p0 = ls - L
    for j in range(0, (n - p0) // L + 1):
        q = p0 + j * L; m_ = min(L, n - q)
        if m_ > 0: vs[q:q + m_] = T[:m_]
    kf = int(.5 * SR); main[ls - kf:ls] *= np.linspace(1, 0, kf) ** 2; main[ls:] = 0
    gm = SPAN_LUFS - lufs_of(main[:ns])["lufs"]
    gv = SPAN_LUFS + VAMP_REL_DB - lufs_of(T)["lufs"]
    for _ in range(3):                                                   # soft-clip rare transients under -1 dBTP,
        x = main * 10 ** (gm / 20) + vs * 10 ** (gv / 20)                # then re-gain so the span stays at -20 LUFS
        if lufs_of(x)["truePeak"] <= -1.3: break
        cl = 10 ** (-1.6 / 20); x = np.tanh(x / cl) * cl
        err = SPAN_LUFS - lufs_of(x[:ns])["lufs"]
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
    r.update(loop_check(x, ls, le))
    clean_tmp()
    return r


def loop_check(x, ls, le):
    """Loop-join scan. seam: the largest sample step across the join (loopEnd -> loopStart) against the largest step
    anywhere inside the loop section (ratio <= 1 means the join is no rougher than the music itself); repeatDb: level
    difference between the first two repeats (RMS, dB); ticks: samples whose step exceeds 8x the local 10 ms RMS step."""
    L = le - ls; seam = np.concatenate([x[le - 64:le], x[ls:ls + 64]]); sd = np.abs(np.diff(seam)); inner = np.abs(np.diff(x[ls:le]))
    rep = [x[ls:le], x[le:le + L]]
    rms = lambda a: 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12)
    d = np.abs(np.diff(x[ls + 100:le + 2000])); k = 441; loc = np.sqrt(np.convolve(d ** 2, np.ones(k) / k, "same")) + 1e-6
    return dict(seamRatio=round(float(sd.max() / (inner.max() + 1e-12)), 3), repeatDb=round(float(rms(rep[1]) - rms(rep[0])), 3),
                ticks=int(np.sum(d > 8 * loc + 0.01)))


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
              f"I={r['loopLufs']:6.1f} TP={r['truePeak']:5.1f} dBTP seam x{r['seamRatio']} repeat {r['repeatDb']:+.2f} dB ticks {r['ticks']}" + (f" (plays {len(f['occ'])}x)" if len(f["occ"]) > 1 else ""))
    manifest = []
    for c in spans:
        r = rendered[c["cue"]]; need = c["span"] * (1 + STRETCH) + XFADE
        assert r["secs"] + 1e-3 >= need, f"{c['cue']} at t={c['t']} is {r['secs']}s, needs {need}s"
        e = dict(cue=c["cue"], t=c["t"], span=c["span"], secs=r["secs"], lastCue=c["last"], loop=False)
        for k in ("loopStart", "loopEnd", "loopStartSample", "loopEndSample", "loopFromSec", "key", "meter", "bars",
                  "bpm", "loopBars", "loopChord", "lufs", "loopLufs", "truePeak", "composedFor", "composedSpan", "seamRatio",
                  "repeatDb", "ticks"):
            e[k] = r[k]
        e["plainTailSec"] = round(r["secs"] - c["span"], 3)
        manifest.append(e)
    json.dump(dict(rule="Start each cue at its timeline t at full level and fade the previous cue out over 0.6 s from "
                        "that t. Each cue's composed music ends on its cadence at loopFromSec; after it the cue "
                        "continues into a quiet loop section on its final chord. If the section is stretched (longer "
                        "voice clips), either loop [loopStart, loopEnd) seamlessly (seconds, sample-accurate) until the "
                        "next cue, or just keep playing: every file is at least span x 1.3 + 0.6 s and fades out over "
                        "its last 2.5 s. A cue that plays more than once (call) uses the same file from its start each "
                        "time; composedFor / composedSpan name the occurrence it was timed to. The composed span sits at "
                        "-20 LUFS, the loop section ~3 dB under it. Duck music ~7 dB under voice lines. Rerun "
                        "tools/story/music_joseph.py after the timeline is re-timed so the in-cue hits follow.",
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
        me.seed(SFX_SEED.get(sid, "joseph/" + sid))
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
                        "seamless loop (loopStart 0, loopEnd = secs); start it at its t with a fadeInSec fade-in and "
                        "loop it until the music cue named in stopAtCue starts (fade out over fadeOutSec).",
                   peakDbfs=SFX_PEAK_DB, sfx=manifest), open(f"{SFX_DIR}/mix.json", "w"), indent=1, ensure_ascii=False)
    return manifest


def build_preview(tl):
    """Offline mix of the Chinese play as StoryDirector.cs mixes it (voice.Play at 1.0; music x 0.8 x duck 0.5 under a
    clip; SFX undocked at gainDb) -- see tools/story/voice_margin.py. Also returns the voice-vs-bed table."""
    mix = vm.engine_mix("joseph", tl, "zh", MUSIC_DIR, SFX_DIR); rows = vm.table(tl, mix)
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
    """One spectrogram PNG per cue / sfx (ffmpeg showspectrumpic), to eyeball instrument layers and loop seams."""
    os.makedirs(outdir, exist_ok=True)
    for d in (MUSIC_DIR, SFX_DIR):
        for f in sorted(os.listdir(d)):
            if f.endswith(".wav"):
                me.run(["ffmpeg", "-y", "-loglevel", "error", "-i", f"{d}/{f}", "-lavfi",
                        "showspectrumpic=s=1400x360:legend=0:scale=log:fscale=log:gain=3", f"{outdir}/{f[:-4]}.png"])
    print(f"spectrograms in {outdir}")


# voice over bed (dB, engine model, Chinese play) of the cues and SFX as they were before the 2026-11-15 pass: old files
# (composed for the pre-rework timeline) played at the re-timed times. Measured with tools/story/voice_margin.py.
BASELINE = {"js_01": 16.0, "js_02": 11.7, "js_03": 10.0, "js_04": 10.0, "js_05": 11.7, "js_06": 14.0, "js_07": 9.2, "js_08": 12.3, "js_09": 13.4, "js_10": 12.7, "js_11": 9.3, "js_12": 12.7, "js_13": 12.4, "js_14": 9.7, "js_15": 11.8, "js_16": 10.2, "js_17": 12.0, "js_18": 14.1, "js_19": 10.7, "js_20": 16.9, "js_21": 12.5, "js_22": 12.1, "js_23": 13.2, "js_24": 9.7, "js_25": 25.3, "js_26": 17.6, "js_27": 10.9, "js_28": 11.9, "js_29": 14.7, "js_30": 11.0, "js_31": 14.2}


def hit_rows(tl):
    """Where every SFX / glow lands inside its cue in the Chinese play and in the English play (same cue file, so the
    English offset is how far its hit drifts from the composed moment)."""
    en = vm.lang_timeline("joseph", "en"); rows = []
    def rel(T, e):
        cs = sorted(T["music"], key=lambda c: c["t"]); c = [c for c in cs if c["t"] <= e["t"] + 1e-6][-1]
        return c["cue"], e["t"] - c["t"]
    for k in ("sfx", "fx"):
        for e in tl[k]:
            if e["id"] not in (HIT_SFX if k == "sfx" else HIT_FX): continue
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
    if cues:
        rows = ["| Cue | Loop seam (step across join / largest step inside) | Level, repeat 2 vs 1 (dB) | Click-like steps in the loop section | Span LUFS | Loop LUFS |",
                "|---|---|---|---|---|---|"]
        for c in cues:
            rows.append(f"| `{c['cue']}` | x{c['seamRatio']} | {c['repeatDb']:+.2f} | {c['ticks']} | {c['lufs']:.1f} | {c['loopLufs']:.1f} |")
        swap("checks", "\n".join(rows) + "\n")
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
    if prev and prev.get("rows"):
        a = np.array([r["vs_bed"] for r in prev["rows"]]); w = sorted(prev["rows"], key=lambda r: r["vs_bed"])[:3]
        rows = ["| Line | Who | t (s) | Before (dB) | **After (dB)** | over music | over SFX |", "|---|---|---|---|---|---|---|"]
        rows += [f"| {r['id']} | {r['who']} | {r['t']:.1f} | {BASELINE.get(r['id'], float('nan')):.1f} | {r['vs_bed']:.1f} | {r['vs_mus']:.1f} | {min(r['vs_sfx'], 99):.0f} |" for r in prev["rows"]]
        b = np.array(list(BASELINE.values())); bw = sorted(BASELINE.items(), key=lambda kv: kv[1])[:3]
        rows.append(f"| **median** | | | {np.median(b):.1f} | **{np.median(a):.1f}** | | |")
        rows.append("| **worst 3** | | | " + ", ".join(f"{k} {v:.1f}" for k, v in bw) + " | **" + ", ".join(f"{r['id']} {r['vs_bed']:.1f}" for r in w) + "** | | |")
        swap("margin", "\n".join(rows) + "\n")
    hr = hit_rows(tl)
    if hr:
        rows = ["| Cue | Event | In-cue time zh (composed for) | English play | Drift |", "|---|---|---|---|---|"]
        rows += [f"| `{c}` | {k} `{i}` | {r:.2f} | {('%.2f' % e) if e is not None else 'n/a'} | {('%+.1f' % (e - r)) if e is not None else ''} |"
                 for c, i, k, r, e in hr]
        swap("hits", "\n".join(rows) + "\n")
    open(DOC, "w").write(txt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-music", action="store_true"); ap.add_argument("--skip-sfx", action="store_true")
    ap.add_argument("--skip-preview", action="store_true"); ap.add_argument("--only", default="")
    ap.add_argument("--stems", action="store_true", help="print per-stem levels while rendering")
    ap.add_argument("--tmp", default="/tmp/joseph_music", help="scratch dir (emptied per cue, removed at exit)")
    ap.add_argument("--spec", default="", help="also write spectrogram PNGs of every output into this dir")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    os.makedirs(a.tmp, exist_ok=True)
    tempfile.tempdir = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=a.tmp)
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    os.makedirs(MUSIC_DIR, exist_ok=True); os.makedirs(SFX_DIR, exist_ok=True)
    tl = vm.lang_timeline("joseph", "zh")      # the play as the phone runs it in Chinese (re-timed to the zh clips)
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
    if a.spec: spectrograms(a.spec)
