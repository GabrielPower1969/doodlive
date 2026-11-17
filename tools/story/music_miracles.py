#!/usr/bin/env python3
"""Original score and sound effects for "The Friends on the Roof / Jesus Calms the Storm" (story pack `miracles`;
docs/miracles/CONTRACT.md section 7, docs/miracles/DESIGN.md section 5, docs/miracles/MUSIC.md).

Built on the shared engine tools/story/music_kit.py (`import music_kit as me`) and the finishing helpers in
tools/story/music_polish.py; the loop-section / build machinery is copied from music_jonah.py (same shape, same
cues.json / mix.json format). This script holds only this pack's cues, effects, paths and tables.

A warm acoustic band with Galilean colour: an "oud" (GM nylon guitar, low-passed, tremolo on long notes), frame drum
(congas / bongos), handclaps and tambourine, flute, strings, harp. Two original themes:
  * the FRIENDS theme: a bouncy, determined 4-bar tune in D mixolydian (the C natural in bar 3 is the folk colour),
    plucked oud over handclaps: four friends who will not give up. `friends(major=True)` turns the C into C# (joy).
  * the JESUS theme: a calm, warm rising melody in D major on flute and strings, 8 bars (bars 5-8 climb higher).
    The same in both acts: capernaum (end), heal (in full), evening (6/8, low flute), calm (very soft), finale.
  JOINT harmony lets the friends theme (major) and Jesus theme bars 1-4 sound together (joy, finale).
Every melody is original; nothing is taken from any film.

Every name and time comes from the timeline, read on every run: the cues are composed for the play as the phone runs
it in Chinese (voice_margin.lang_timeline, re-timed to the installed zh clips; the shortest play, so no cadence is cut
off), in-cue hits are looked up by sfx / fx / lines / shots events. Every file is long enough for its section in the
zh play, the en play and assets/miracles/timeline.json (the longer of both clips per line) x 1.3 + 0.6 s, and after
its cadence continues into a quiet loop section with sample-exact loop points in cues.json. Rerun after re-timing.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/miracles/audio/music/<cue>.wav|.mp3   music, -20 LUFS (+-1) over the composed span, true peak <= -1 dBTP
  assets/miracles/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/miracles/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/miracles/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain, loop hints
  assets/miracles/audio/preview_mix.mp3        full-length mix of the zh play as the engine mixes it
  docs/miracles/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_miracles.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--tmp DIR] [--spec DIR]   (scratch default /tmp/miracles_music; --spec writes spectrogram PNGs)
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
from music_kit import (Score, Ctx, mel, groove, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB, TPB,  # noqa: E402
                       HARP, NYLON, CELESTA, GLOCK, XYLO, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                       CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, TIMPANI, TUBA, DRUMS,
                       BDRUM, CLAP, TAMB, CRASH, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA, HI_WOOD, LO_WOOD,
                       SHAKER, TRIANGLE)

SID = "miracles"
ROOT = me.ROOT
MI = f"{ROOT}/assets/{SID}"
MUSIC_DIR, SFX_DIR = f"{MI}/audio/music", f"{MI}/audio/sfx"
PREVIEW = f"{MI}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/{SID}/MUSIC.md"
STRETCH = 0.30                 # every file covers its longest section (zh / en / base timeline) x 1.3 + 0.6 s
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -4.5             # loop section loudness relative to the cue's composed span
SPAN_LUFS = -20.5              # composed span loudness (contract -20 +-1; a little under it like jonah's -20.9)
# a little dynamic range between cues inside the contract's +-1 LU: the soft cues sit lower, the storm and dance higher
CUE_LUFS = {"lowering": -20.9, "calm": -20.9, "storm": -19.4, "joy": -19.6}
HIT_SFX = {"boing", "crumble", "sparkle", "thunder"}     # not `ding`: it lands on "I've got it!"
HIT_FX = {"heart_glow", "golden_rays"}
NO_SWELL = {("finale", "golden_rays"),     # finale's rays land 0.2 s before the narrator: no swell there
            ("heal", "golden_rays"), ("heal", "sparkle")}   # both land inside "Get up!": swell after the line instead
AFTER_LINE = {"heal": ["mi_19"]}           # extra swell hits at the end of these lines (the climax lands after the words)
END_SWELL = {"finale"}                     # the last cue swells back up on its final chord
# extra dips (file seconds, zh play, dB) where a cue sits under a line it cannot get out of the way of
DIPS = {"no_way": [(0.3, 2.4, -3.0), (9.6, 11.5, -4.5)], "storm": [(0.9, 3.2, -3.0)], "joy": [(8.4, 13.0, -3.0)]}
TMP_PREFIX = "music_miracles_"

# extra GM programs (0-based)
VIOLA, RIDE = 41, 51
OUD = NYLON

CH = dict(me.CH)
CH.update({"D": ["D3", "A3", "D4", "F#4"], "Dadd9": ["D3", "A3", "E4", "F#4"], "Dsus": ["D3", "A3", "D4", "G4"],
           "Dm": ["D3", "A3", "D4", "F4"], "Dm9": ["D3", "A3", "E4", "F4"], "G": ["G2", "D3", "G3", "B3"],
           "Gm": ["G2", "D3", "G3", "Bb3"], "A": ["A2", "E3", "A3", "C#4"], "A7": ["A2", "E3", "G3", "C#4"],
           "Asus": ["A2", "E3", "A3", "D4"], "Bm": ["B2", "F#3", "B3", "D4"], "Em": ["E2", "B2", "E3", "G3"],
           "E": ["E2", "B2", "E3", "G#3"], "C": ["C3", "G3", "C4", "E4"], "F": ["F2", "C3", "F3", "A3"],
           "Bb": ["Bb2", "F3", "Bb3", "D4"]})
def chord(name): return [note(p) for p in CH[name]]
def low(p): return p - 12 if p - 12 >= note("C2") else p
NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
def nm(m): return f"{NAMES[m % 12]}{m // 12 - 1}"


# =============================================================================================== the two themes
# The FRIENDS theme, D mixolydian, 4/4: "heave-ho" up to A, a step down home, a reach to D5 and the folk C natural,
# a run down to rest. Harmony as (chord, beats) per bar.
FRIENDS = {
    1: [("D4", .5), ("F#4", .5), ("A4", 1), ("A4", .5), ("B4", .5), ("A4", 1)],
    2: [("G4", .5), ("A4", .5), ("F#4", 1), ("E4", .5), ("F#4", .5), ("D4", 1)],
    3: [("D4", .5), ("F#4", .5), ("A4", .5), ("D5", .5), ("C5", 1), ("A4", 1)],
    4: [("B4", .5), ("A4", .5), ("G4", .5), ("E4", .5), ("D4", 2)],
}
FRIENDS_HARM = {1: [("D", 4)], 2: [("G", 2), ("D", 2)], 3: [("D", 2), ("C", 2)], 4: [("G", 2), ("D", 2)]}
FRIENDS_HARM_MAJOR = {1: [("D", 4)], 2: [("G", 2), ("D", 2)], 3: [("D", 2), ("A", 2)], 4: [("G", 2), ("D", 2)]}
# The JESUS theme, D major, 4/4: a calm rise A-B-D to E, home through F#; bars 5-8 climb to G5 and settle on D5.
JESUS = {
    1: [("A4", 2), ("B4", 1), ("D5", 1)],
    2: [("E5", 3), ("D5", 1)],
    3: [("F#5", 1.5), ("E5", .5), ("D5", 1), ("B4", 1)],
    4: [("A4", 1), ("B4", 1), ("D5", 2)],
    5: [("A4", 2), ("B4", 1), ("D5", 1)],
    6: [("G5", 3), ("F#5", 1)],
    7: [("E5", 1.5), ("D5", .5), ("E5", 1), ("F#5", 1)],
    8: [("D5", 4)],
}
JESUS_HARM = {1: [("D", 4)], 2: [("A", 2), ("G", 2)], 3: [("Bm", 2), ("G", 2)], 4: [("A", 2), ("D", 2)],
              5: [("D", 4)], 6: [("G", 3), ("D", 1)], 7: [("Em", 2), ("A7", 2)], 8: [("D", 4)]}
# friends (major) + Jesus bars 1-4 at the same time
JOINT = {1: [("D", 4)], 2: [("A7", 4)], 3: [("Bm", 2), ("A", 2)], 4: [("G", 2), ("D", 2)]}


def friends(bars, major=False, stacc=False, shift=0, scale=1.0):
    out = []
    for k in bars:
        for p, d in FRIENDS[k]:
            m = note(p) + shift + (1 if major and p.startswith("C") and "#" not in p else 0)
            out.append((nm(m) + ("." if stacc else ""), d * scale))
    return out


def jesus(bars, shift=0, scale=1.0):
    out = []
    for k in bars: out += [(nm(note(p) + shift), d * scale) for p, d in JESUS[k]]
    return out


def harm(b0, harmd, bars, fn, scale=1.0):
    """Call fn(beat, chord, beats) for each chord of the given bars of a harmony table."""
    b = b0
    for k in bars:
        for name, d in harmd[k]: fn(b, name, d * scale); b += d * scale
    return b


# =============================================================================================== small helpers
def bar_of(s, abs_t, default):
    b = s.at(abs_t)
    return default if b is None else int(b // s.bpb)


def beat_of(s, abs_t, default):
    b = s.at(abs_t)
    return default if b is None else b


def pad(part, b, name, dur, vel=50, swell=(70, 105), voices=(1, 2, 3), strum=.03, curve=.8, shift=0):
    """Sustained chord with an expression swell; overlaps the next chord; only a cue's first chord swells from low."""
    ps = chord(name); part.chord(b, [ps[i] + shift for i in voices], dur + .25, vel, strum=strum)
    v0 = swell[0] if b < 0.5 else max(82, swell[0])
    part.ramp(b, b + max(.5, dur * .8), 11, v0, max(v0, swell[1]), curve)


def roll(p, b0, b1, pitch, v0, v1, step=.2):
    """Timpani / drum / cymbal roll with a crescendo (or diminuendo) from beat b0 to b1."""
    k = max(2, int((b1 - b0) / step))
    for i in range(k): p.add(b0 + i * (b1 - b0) / k, pitch, step * 1.2, v0 + (v1 - v0) * i / k)


def run(p, b0, pitches, step, vel, dur=1.2):
    for i, pt in enumerate(pitches): p.add(b0 + i * step, pt, dur, vel + 8 * i / max(1, len(pitches) - 1))
    return b0 + len(pitches) * step


def harp_arp(harp, b, name, beats, vel=48, step=.5, up=12, shift=0):
    ps = chord(name)
    for j in range(int(round(beats / step))):
        harp.add(b + j * step, ps[[0, 1, 2, 3, 2, 3, 2, 1][j % 8]] + up + shift, 1.4, vel + (8 if j == 0 else 0))


D_SCALE = ["D", "E", "F#", "G", "A", "B", "C#"]
DM_SCALE = ["D", "E", "F", "G", "A", "Bb", "C"]
def scale_run(lo, hi, names=D_SCALE):
    pcs = {note(n + "4") % 12 for n in names}
    return [m for m in range(note(lo), note(hi) + 1) if m % 12 in pcs]


# Sustain fix (Ruth, measured 2026-11-14): the macOS DLS bank decays every instrument; winds, bowed strings, brass and
# voices get an NRPN offset on SoundFont gen 37 (volEnvSustain -1440 cB) so long notes hold.
SUSTAIN = {STRINGS, SLOW_STR, TREM_STR, CELLO, VIOLA, CBASS, CHOIR, OOHS, FLUTE, OBOE, BASSOON, CLARINET, TUBA}


def sustain_ccs(p):
    d = 8192 - 1440
    p.cc(0, 99, 120); p.cc(0, 98, 37); p.cc(0, 6, d >> 7); p.cc(0, 38, d & 127)


class BPart(me.Part):
    """A Part that can also bend pitch (comic tuba 'bonk', thinking clarinet). Bend range is 12 semitones."""

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


# Loudness trim per GM program (dB), from music_jonah.py (measured per stem 2026-11-15): the DLS bank plays choirs,
# ensemble strings, xylophone, celesta ... far quieter than cello / flute at the same velocity.
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
DANCE = {"D": (LO_CONGA, 92), "T": (HI_BONGO, 70), "t": (MUTE_CONGA, 56), "k": (OPEN_CONGA, 44), "b": (LO_BONGO, 60)}
HANDS = {"c": (CLAP, 72), "s": (TAMB, 46), "h": (SHAKER, 40)}


# =============================================================================================== cues
# ----------------------------------------------------------------------------------------------- capernaum
TOWN = [
    [("D4", .5), ("E4", .5), ("F#4", .5), ("G4", .5), ("A4", 1), ("G4", .5), ("F#4", .5)],
    [("E4", .5), ("F#4", .5), ("G4", .5), ("E4", .5), ("D4", 1), (None, 1)],
    [("A4", .5), ("B4", .5), ("C5", .5), ("B4", .5), ("A4", .5), ("G4", .5), ("F#4", 1)],
    [("G4", .5), ("F#4", .5), ("E4", .5), ("C4", .5), ("D4", 1), (None, 1)],
]
TOWN_HARM = ["D", "D", "C", "D"]


def cue_capernaum(c):
    """Busy little-town morning in D mixolydian: frame drum and tambourine, murmuring tremolo strings and pizzicato
    bass, the oud chatters a market tune; at Jesus' first line the busy texture thins and the flute sings the Jesus
    theme (bars 1-2) over a warm D major pad, ending on D with the cue."""
    s = Score(c, 104, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -3, .3, lp=4200, human=.006)
    dr = P(s, "frame drum", DRUMS, -9, .2, lp=3500, human=.005)
    hands = P(s, "tambourine/shaker", DRUMS, -4, .25, human=.005)
    trem = P(s, "murmur strings", TREM_STR, -11, .5, lp=3500)
    pz = P(s, "pizz bass", PIZZ, -7, .25)
    padp = P(s, "pad", SLOW_STR, -7, .5, lp=3500)
    fl = P(s, "flute (Jesus)", FLUTE, -5, .45, human=.01)
    harp = P(s, "harp", HARP, -9, .45)
    cb = P(s, "contrabass", CBASS, -10, .3, lp=1100)
    jt = s.at(c.first("lines", who="jesus"))
    js = total - 8 if jt is None else max(4, min(total - 8, round(jt / 4) * 4))     # theme start: a bar line, ends with the cue
    for bar in range(n):
        b = bar * 4
        if b < js:
            h = TOWN_HARM[bar % 4]; ps = chord(h)
            oud_line(oud, b, TOWN[bar % 4], 74 if bar % 2 == 0 else 68)
            groove(dr, b, "D..tk.t.D.tkt..k", .25, FRAME, .8)
            groove(hands, b, "h.h.s.h.h.h.s.hh", .25, HANDS, .7)
            trem.chord(b, [ps[1], ps[2]], 4.2, 40); trem.ramp(b, b + 4, 11, 70, 96 if bar % 2 else 80)
            pz.add(b, low(ps[0]), .4, 62); pz.add(b + 1.5, ps[1] - 12, .3, 50); pz.add(b + 2, low(ps[0]), .4, 58); pz.add(b + 3, ps[1] - 12, .3, 50)
    # the Jesus theme: calm flute, warm pad, the drum falls to a heartbeat
    def chordfn(b, name, d):
        pad(padp, b, name, d, 50, (70, 100)); cb.add(b, low(chord(name)[0]), d, 50); harp_arp(harp, b, name, d, 42)
    harm(js, JESUS_HARM, [1, 2], chordfn)
    notes = jesus([1, 2]); notes[-1] = ("D5", total - js - 7 + 1.2)
    mel(fl, js, notes, 70, legato=.97, vib=True)
    for q in range(js, total, 2): dr.add(q, LO_CONGA, .4, 40)
    oud.add(js, "D3", 1, 50); oud.add(js, "A3", 1, 44)
    return s


# ----------------------------------------------------------------------------------------------- friends
HEAVE = [("D3", 1.5), ("A2", .5), ("D3", 1), ("A2", 1)]


def cue_friends(c):
    """The friends theme at a walking pace with a 'heave-ho' lilt: cello + bass lean on beat 1 (heave) and kick on the
    'and' of 2 (ho), swung frame drum, handclaps on 2 and 4, the oud plays the theme (harp doubling for clarity), the
    flute joins an octave up on the second half; a short intro groove first so the theme ends on D with the cue."""
    s = Score(c, 96, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -2, .3, lp=4200, human=.006)
    harp = P(s, "harp (double)", HARP, -12, .4)
    fl = P(s, "flute", FLUTE, -9, .45, human=.008)
    vc = P(s, "cello heave", CELLO, -5, .3, lp=3000, human=.006)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1100)
    dr = P(s, "frame drum", DRUMS, -8, .2, lp=3500, human=.005)
    hands = P(s, "claps", DRUMS, -5, .25, human=.004)
    padp = P(s, "pad", SLOW_STR, -10, .5, lp=3500)
    plan = me.fill_phrase(n, 4, 4, min_intro=1)
    for bar, k in enumerate(plan):
        b = bar * 4
        groove(dr, b, "D..tD.k.D..tD.kt", .25, FRAME, .85, swing=.1)
        groove(hands, b, "....c.......c...", .25, HANDS, .9)
        if k is None:
            hv = HEAVE; root = "D"
            oud_line(oud, b, [("D4", .5), ("A3", .5), ("D4", .5), ("E4", .5), ("F#4", 1), ("E4", 1)], 64)
            pad(padp, b, "D", 4, 40, (60, 88))
        else:
            hv = None
            oud_line(oud, b, friends([k + 1]), 82)
            mel(harp, b, friends([k + 1]), 60)
            if bar >= n - 2: mel(fl, b, friends([k + 1], shift=12), 58)
            harm(b, FRIENDS_HARM, [k + 1], lambda bb, name, d: pad(padp, bb, name, d, 44, (70, 96)))
        # heave-ho: long-short on the chord roots
        roots = [("D", 4)] if k is None else FRIENDS_HARM[k + 1]
        bb = b
        for name, d in roots:
            r = low(chord(name)[0]); fifth = chord(name)[1] - 12
            vc.add(bb, r + 12 if r + 12 <= note("A3") else r, min(d, 1.5) * .9, 80); vc.add(bb + 1.5, fifth, .4, 66)
            cb.add(bb, r, d * .9, 56); bb += d
    vc.add(total - 2, "D3", 2, 72)
    return s


# ----------------------------------------------------------------------------------------------- no_way
THINK = [("A4", 1), (None, .5), ("B4", .5), ("A4", 1), ("G4", .5), ("E4", 1.5)]


def cue_no_way(c):
    """Comic stop-start: pizzicato tries the friends theme and stops dead; a tuba 'bonk' (pitch-bent down) on the
    `boing`; the pizz tries again and stops; then a clock-like tick-tock (wood blocks) under a thinking clarinet on an
    A7 pedal; at the `ding` a celesta + glock 'idea!' arpeggio and the oud lifts the friends theme's first bar up to D."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4
    pz = P(s, "pizz", PIZZ, -2, .25, human=.005)
    tuba = P(s, "tuba bonk", TUBA, -4, .25, lp=1200, bend=True)
    cl = P(s, "thinking clarinet", CLARINET, -6, .35, human=.01, bend=True)
    wb = P(s, "wood blocks", DRUMS, 5, .18, human=.003)
    cel = P(s, "celesta", CELESTA, -15, .5)
    gl = P(s, "glock", GLOCK, -8, .5)
    oud = P(s, "oud", OUD, -3, .3, lp=4200)
    padp = P(s, "pad", SLOW_STR, -11, .5, lp=3200)
    cb = P(s, "contrabass", CBASS, -10, .3, lp=1100)
    bo = beat_of(s, c.first("sfx", id="boing"), 2.5)
    th = beat_of(s, c.first("lines", who="friend2"), bo + 6)
    di = beat_of(s, c.first("sfx", id="ding"), total - 4)
    # try 1: the theme's first notes, stopped at the bonk
    mel(pz, 0, [(p + ".", d) for p, d in FRIENDS[1]][:4], 72)
    tuba.add(bo - .05, "D2", .9, 84); tuba.glide(bo + .15, bo + .8, 0, -5, .7)
    # try 2 after the bonk, stopped again
    t2 = math.ceil(bo + 1.0)
    if t2 + 2 < th: mel(pz, t2, [("D4.", .5), ("F#4.", .5), ("A4.", .5), (None, .5)], 64); pz.add(t2 + 2, "A3", .2, 70); pz.add(t2 + 2.1, "D3", .2, 70)
    # thinking: tick-tock (from right after the second stop), clarinet over an A7 pedal
    t0 = math.floor(th); tk = min(t0, t2 + 3)
    for q in np.arange(tk, di - .01, 1.0): wb.add(q, HI_WOOD if int(q) % 2 == 0 else LO_WOOD, .15, 44)
    pad(padp, tk, "A7", max(1, di - tk), 40, (60, 82)); cb.add(tk, "A2", max(1, di - tk), 46)
    for q in np.arange(tk + .5, t0, 2.0): pz.add(q, "E3", .2, 40); pz.add(q + 1, "C#3", .2, 38)   # shuffling feet
    b = mel(cl, t0 + .5, [x for x in THINK], 60, legato=.9, vib=True)
    cl.glide(t0 + .5 + 3.5, t0 + .5 + 4.4, 0, -.6, 1.0); cl.bend(t0 + .5 + 5.4, 0)
    # the idea: ding!
    run(cel, di, ["D6", "F#6", "A6", "D7"], .12, 60, 1.5); gl.add(di, "A6", 2, 50); gl.add(di + .5, "D7", 2, 46)
    pad(padp, di, "D", total - di + 1, 52, (80, 104)); cb.add(di, "D2", total - di + 1, 56)
    rest = total - (di + .5)
    if rest >= 1.5: oud_line(oud, di + .5, friends([1], scale=min(1.0, (rest - .3) / 4)), 80)
    for q in np.arange(math.ceil(di + .5), total, 1.0): pz.add(q, "D3" if int(q) % 2 == 0 else "A2", .2, 52)
    return s


# ----------------------------------------------------------------------------------------------- roof
CLIMB = [("D", 0), ("E", 2), ("G", 5), ("A", 7)]


def cue_roof(c):
    """The friends theme climbing up the stairs: its first bar played in a rising sequence D - E - G - A (oud + harp,
    pizz steps, a rising cello) while the narrator tells it; at `dig_loop` a digging rhythm (wood blocks dig-dig-dig,
    shaker, frame drum) under the theme's bars 3-4 on the oud; a xylophone tumble on `crumble`; Peter's "My roof!" stops
    the band on a tuba bonk; Jesus laughs on a flute giggle, and the flute starts the Jesus theme, ending on A
    (the lowering follows)."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -2, .3, lp=4200, human=.006)
    harp = P(s, "harp", HARP, -10, .4)
    pz = P(s, "pizz", PIZZ, -6, .25)
    vc = P(s, "cello", CELLO, -6, .35, lp=3200, human=.008)
    cb = P(s, "contrabass", CBASS, -10, .3, lp=1100)
    padp = P(s, "pad", SLOW_STR, -9, .5, lp=3500)
    wb = P(s, "dig blocks", DRUMS, 2, .18, human=.004)
    hands = P(s, "shaker", DRUMS, -2, .22, human=.004)
    dr = P(s, "frame drum", DRUMS, -10, .2, lp=3500, human=.005)
    xy = P(s, "xylophone", XYLO, -7, .3)
    tuba = P(s, "tuba bonk", TUBA, -6, .25, lp=1200, bend=True)
    fl = P(s, "flute", FLUTE, -6, .45, human=.01)
    dig = beat_of(s, c.first("sfx", id="dig_loop"), total * .45)
    cr = beat_of(s, c.first("sfx", id="crumble"), dig + 8)
    pe = beat_of(s, c.first("lines", who="peter"), cr + 2)
    la = beat_of(s, c.first("lines", who="jesus"), pe + 3.5)
    db = max(4, math.floor(dig / 4) * 4)              # digging starts on the bar line at / before the dig
    # the climb: one bar per step, the sequence repeats higher if there is room
    bar = 0
    while bar * 4 < db:
        name, sh = CLIMB[min(bar, len(CLIMB) - 1)]
        b = bar * 4
        oud_line(oud, b, friends([1], shift=sh), 76 + 2 * min(bar, 4)); mel(harp, b, friends([1], shift=sh), 54)
        pad(padp, b, name, 4, 42 + 3 * min(bar, 4), (70, 100)); cb.add(b, low(chord(name)[0]), 4, 52)
        for q in range(4): pz.add(b + q, chord(name)[[0, 1, 2, 1][q]] - (12 if q % 2 else 0), .25, 58 + 3 * q)
        vc.add(b, chord(name)[1], 3.8, 60)
        groove(dr, b, "D.......D...t...", .25, FRAME, .7)
        bar += 1
    # digging: dig-dig-dig on wood blocks, shaker, theme bars 3-4 (determined) until Peter shouts
    stop = math.floor(pe)
    b = db
    while b < stop:
        k = 3 if ((b - db) // 4) % 2 == 0 else 4
        for q in (0, .5, 1.0, 2, 2.5, 3.0):
            if b + q < stop: wb.add(b + q, HI_WOOD if q in (0, 2) else LO_WOOD, .15, 66 if q in (0, 2) else 52)
        groove(hands, b, "h.hhh.hhh.hhh.hh", .25, HANDS, .8, until=stop)
        groove(dr, b, "D...t.k.D...t.k.", .25, FRAME, .8, until=stop)
        if b + 4 <= stop + .01:
            oud_line(oud, b, friends([k]), 80)
            harm(b, FRIENDS_HARM, [k], lambda bb, name, d: (pad(padp, bb, name, d, 46, (80, 100)), cb.add(bb, low(chord(name)[0]), d, 52)))
        else:
            pad(padp, b, "D", stop - b, 46, (80, 96)); cb.add(b, "D2", stop - b, 52)
        b += 4
    run(xy, cr, ["A6", "F#6", "E6", "D6", "B5", "A5", "F#5", "D5"], .125, 60, .3)        # crumble
    # "My roof!": stop, bonk
    tuba.add(pe + .9, "A1", 1.0, 80); tuba.glide(pe + 1.1, pe + 1.8, 0, -4, .8)
    # Jesus laughs: a flute giggle, then the theme starts gently over D -> A
    mel(fl, la, [("A5.", .25), ("B5.", .25), ("A5.", .25), ("F#5.", .25), ("A5.", .25), ("B5.", .25), ("D6", .5)], 62)
    t3 = math.ceil(la + 2)
    if t3 < total:
        pad(padp, t3, "D", max(1, min(4, total - t3 - 2)), 44, (70, 92)); harp_arp(harp, t3, "D", max(1, min(4, total - t3 - 2)), 40)
        tail = total - t3
        if tail >= 6: mel(fl, t3, [("A4", 2), ("B4", 1), ("D5", 1), ("E5", tail - 4)], 58, vib=True)
        a0 = total - 2 if tail >= 2 else t3
        pad(padp, a0, "A", total - a0 + .5, 44, (80, 96)); cb.add(a0, "A2", total - a0 + .5, 50)
    return s


# ----------------------------------------------------------------------------------------------- lowering
DOWN = ["A5", "G5", "F5", "E5", "D5", "C5", "Bb4", "A4", "G4", "F4", "E4", "D4"]


def cue_lowering(c):
    """Suspense, very soft: held strings on a D minor (add 9) chord over a cello D pedal, a single harp note every two
    beats walking down the D minor scale like the mat coming down step by step on its ropes, a faint timpani pulse;
    the last bar turns to A (sus to major) so the healing can open in D major."""
    s = Score(c, 70, 4); n = s.bars; total = n * 4
    padp = P(s, "held strings", SLOW_STR, -6, .55, lp=2800)
    vln = P(s, "high strings", STRINGS, -16, .55, lp=4500)
    vc = P(s, "cello pedal", CELLO, -9, .45, lp=2000)
    harp = P(s, "harp steps", HARP, -5, .55)
    tim = P(s, "timpani pulse", TIMPANI, -10, .4, lp=500)
    cb = P(s, "contrabass", CBASS, -12, .4, lp=800)
    last = max(0, total - 4)
    pad(padp, 0, "Dm9", last, 38, (50, 78), voices=(1, 2, 3)); vc.add(0, "D3", last + .3, 46); cb.add(0, "D2", last + .3, 40)
    vln.chord(0, ["A4", "E5"], last + .3, 30); vln.ramp(0, last, 11, 40, 70)
    k = 0
    for b in np.arange(0, total - 1.99, 2.0):
        harp.add(b, DOWN[min(k, len(DOWN) - 1)], 3.0, 44 - (4 if k % 2 else 0)); k += 1
    for b in range(0, last, 4): tim.add(b, "D2", 2, 26)
    pad(padp, last, "Asus", 2, 40, (80, 88)); pad(padp, last + 2, "A", 2.5, 42, (88, 96))
    vc.add(last, "A2", 4.3, 44); cb.add(last, "A1", 4.3, 40); vln.chord(last, ["C#5", "E5"], 4.3, 30)
    return s


# ----------------------------------------------------------------------------------------------- heal
def cue_heal(c):
    """The Jesus theme, tender: solo flute over soft strings and harp (bars 1-4); a celesta glimmer on `heart_glow`;
    the cello answers with the theme's opening; then on "Get up!" everything swells (timpani roll in, harp glissando,
    violins and choir) and the flute climbs into the theme's high second half, ending on a full D chord."""
    s = Score(c, 72, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (Jesus)", FLUTE, -3, .45, human=.01)
    padp = P(s, "strings", SLOW_STR, -6, .5, lp=3500)
    vln = P(s, "violins", STRINGS, -11, .5, lp=5000)
    vc = P(s, "cello", CELLO, -6, .4, lp=3500, human=.01)
    harp = P(s, "harp", HARP, -8, .45)
    cel = P(s, "celesta", CELESTA, -14, .55)
    oohs = P(s, "choir oohs", OOHS, -13, .6, lp=4000)
    tim = P(s, "timpani", TIMPANI, -12, .4, lp=900)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1100)
    oud = P(s, "oud", OUD, -10, .35, lp=3800)
    hg = beat_of(s, c.first("fx", id="heart_glow"), 12)
    gl = [t for t in c.all("lines", who="jesus")]
    gu = s.at(gl[-1]) if gl else total * .7                     # the last Jesus line in this cue: "Get up!"
    sw = int(round(gu / 4)) * 4                                  # the swell bar
    rem = total - sw
    hi = [5, 6, 7, 8] if rem >= 16 else [5, 6, 8] if rem >= 12 else [6, 8] if rem >= 8 else [8]
    # intro + bars 1-4
    def chordfn(b, name, d, vel=46):
        pad(padp, b, name, d, vel, (70, 100)); cb.add(b, low(chord(name)[0]), d, 48); harp_arp(harp, b, name, d, 40)
    chordfn(0, "D", 2)
    t1 = 2
    b1 = min(t1 + 16, sw)
    nb = int((b1 - t1) // 4)
    if nb >= 1:
        harm(t1, JESUS_HARM, list(range(1, nb + 1)), chordfn)
        mel(fl, t1, jesus(list(range(1, nb + 1))), 70, legato=.97, vib=True)
    # between: the cello answers the opening over D - G - A
    b = t1 + nb * 4
    fill = [("D", 4), ("G", 4), ("Em", 4), ("A", 4)]; j = 0
    while b < sw:
        d = min(4, sw - b); name = fill[j % 4][0]; chordfn(b, name, d, 44)
        if j == 0 and sw - b >= 4: mel(vc, b, jesus([1], shift=-12), 62, legato=.98, vib=True)
        elif j == 1 and d >= 4: mel(vc, b, jesus([2], shift=-12), 60, legato=.98, vib=True)
        b += d; j += 1
    for p_, k in (("A6", 0), ("D7", 1), ("F#7", 2)): cel.add(hg + k * .5, p_, 2.5, 46)
    harp.add(hg, "D6", 2, 44)
    # the swell on "Get up!"
    roll(tim, max(0, sw - 2), sw, "D2", 30, 70, .2); tim.add(sw, "D2", 3, 74)
    run(harp, sw - .1, scale_run("D4", "D7")[::2], .08, 56, 2.5)
    def chordfn2(b, name, d):
        pad(padp, b, name, d, 60, (90, 116)); cb.add(b, low(chord(name)[0]), d, 58)
        ps = chord(name); vln.chord(b, [ps[1] + 12, ps[3] + 12], d + .2, 50); vln.ramp(b, b + d, 11, 80, 112)
        oohs.chord(b, [ps[2], ps[3]], d + .2, 44); oohs.ramp(b, b + d, 11, 70, 108)
        for q in range(0, int(d), 1): oud.add(b + q, ps[[0, 1, 2, 3][q % 4]] + 12, .9, 50)
    harm(sw, JESUS_HARM, hi, chordfn2)
    notes = jesus(hi); notes[-1] = (notes[-1][0], notes[-1][1] + 1)
    mel(fl, sw, notes, 82, legato=.97, vib=True)
    mel(vc, sw, jesus(hi, shift=-12), 66, legato=.98, vib=True)
    return s


# ----------------------------------------------------------------------------------------------- joy
DABKE = "D.t.k.D.D.t.k.t."


def cue_joy(c):
    """Dance: fast oud, handclaps, tambourine, frame drum and bongos, offbeat string chops; the friends theme in major,
    and on its last pass the Jesus theme (bars 1-4) on flute and violins at the same time over the JOINT harmony."""
    s = Score(c, 132, 4); n = s.bars; total = n * 4
    oud = P(s, "oud", OUD, -1, .3, lp=4500, human=.005)
    fl = P(s, "flute (Jesus)", FLUTE, -5, .4, human=.008)
    vln = P(s, "violins", STRINGS, -9, .45, lp=5000)
    chop = P(s, "string chops", STRINGS, -12, .35, lp=4500)
    pz = P(s, "pizz bass", PIZZ, -5, .25)
    cb = P(s, "contrabass", CBASS, -11, .3, lp=1100)
    dr = P(s, "frame drum", DRUMS, -6, .2, lp=4000, human=.004)
    hands = P(s, "claps+tamb", DRUMS, -3, .25, human=.004)
    cel = P(s, "glock", GLOCK, -8, .5)
    plan = me.fill_phrase(n, 4, 4, min_intro=0)
    last_pass = max(i for i, k in enumerate(plan) if k == 0) if 0 in plan else 0
    for bar, k in enumerate(plan):
        b = bar * 4
        groove(dr, b, DABKE, .25, DANCE, .9); groove(hands, b, "s.s.c.s.s.s.c.sc", .25, HANDS, .9)
        if k is None:
            oud_line(oud, b, [("D4", .5), ("F#4", .5), ("A4", .5), ("F#4", .5), ("G4", .5), ("F#4", .5), ("E4", .5), ("F#4", .5)], 70)
            hm = [("D", 4)]
        else:
            together = bar >= last_pass
            oud_line(oud, b, friends([k + 1], major=True), 86)
            hm = (JOINT if together else FRIENDS_HARM_MAJOR)[k + 1]
            if together:
                mel(fl, b, jesus([k + 1]), 74, legato=.95, vib=True)
                mel(vln, b, jesus([k + 1]), 50, legato=.98)
        bb = b
        for name, d in hm:
            ps = chord(name)
            for q in np.arange(0, d, 1.0):
                chop.chord(bb + q + .5, [ps[1] + 12, ps[3] + 12], .3, 54)
                pz.add(bb + q, low(ps[0]) + (12 if q % 2 else 0), .3, 70)
            cb.add(bb, low(ps[0]), d, 50); bb += d
    ps = chord("D"); chop.chord(total - 2, [ps[1] + 12, ps[2] + 12, ps[3] + 12], 2.2, 70); cel.add(total - 2, "D7", 2, 50)
    return s


# ----------------------------------------------------------------------------------------------- evening
EVE_HARM = ["G", "Em", "C", "D"]


def cue_evening(c):
    """Calm evening on the water in G major, slow 6/8 (bpb = 6 eighths): harp arpeggios, soft strings, a lapping
    rhythm (low pizz + soft conga on 1 and 4); a low flute sings the Jesus theme (bars 1-4, transposed to G, 6/8
    rhythm); when Jesus falls asleep (fx `zzz`) it thins to harp and pad; the last bar darkens to D minor with a soft
    timpani roll and a cello swell, so the storm can burst in."""
    s = Score(c, 126, 6); n = s.bars; total = n * 6
    harp = P(s, "harp", HARP, -5, .5)
    padp = P(s, "strings", SLOW_STR, -8, .55, lp=3200)
    fl = P(s, "flute (low)", FLUTE, -4, .5, human=.01)
    pz = P(s, "lapping pizz", PIZZ, -9, .3)
    lap = P(s, "lapping drum", DRUMS, -4, .3, lp=2500)
    vc = P(s, "cello", CELLO, -9, .45, lp=2500)
    tim = P(s, "timpani", TIMPANI, -12, .4, lp=700)
    cb = P(s, "contrabass", CBASS, -11, .35, lp=900)
    zz = bar_of(s, c.first("fx", id="zzz"), n - 2)
    last = n - 1
    jh = {1: [("G", 6)], 2: [("D", 3), ("C", 3)], 3: [("Em", 3), ("C", 3)], 4: [("D", 3), ("G", 3)]}
    theme_bars = min(4, max(0, min(zz, last)))
    for bar in range(n):
        b = bar * 6
        if bar == last:
            pad(padp, b, "Dm", 6, 42, (70, 96)); cb.add(b, "D2", 6.3, 50); vc.add(b, "D3", 6.3, 48); vc.ramp(b, b + 6, 11, 50, 110)
            roll(tim, b + 2, b + 6, "D2", 22, 60, .2)
            for j, p_ in enumerate(["D4", "F4", "A4", "D5"]): harp.add(b + j * 1.5, p_, 2.5, 40)
            continue
        if bar < theme_bars:
            def eve(bb, name, d):
                pad(padp, bb, name, d, 44, (70, 92)); cb.add(bb, low(chord(name)[0]), d, 46)
                for j in range(int(d)): harp.add(bb + j, chord(name)[[0, 1, 2, 3, 2, 1][j % 6]] + 12, 1.6, 44 + (8 if j == 0 else 0))
            harm(b, jh, [bar + 1], eve)
        else:
            name = EVE_HARM[bar % 4]; quiet = bar >= zz
            pad(padp, b, name, 6, 38 if quiet else 44, (60, 86)); cb.add(b, low(chord(name)[0]), 6, 42)
            for j in range(6): harp.add(b + j, chord(name)[[0, 1, 2, 3, 2, 1][j]] + 12, 1.6, (36 if quiet else 44) + (6 if j == 0 else 0))
        pz.add(b, "G2" if bar % 2 == 0 else "D2", .6, 50); pz.add(b + 3, "D3", .6, 42)
        lap.add(b + 3, MUTE_CONGA, .3, 30); lap.add(b + 5, OPEN_CONGA, .3, 18)
    if theme_bars:
        mel(fl, 0, jesus(list(range(1, theme_bars + 1)), shift=-7, scale=1.5), 62, legato=.97, vib=True)
    if zz < last:
        b = zz * 6 + 1.5
        mel(fl, b, [("D5", 1.5), ("B4", 1.5), ("A4", 3)], 46, vib=True)        # a lullaby sigh while He sleeps
    return s


# ----------------------------------------------------------------------------------------------- storm
OSTI = [["D3", "D3", "A2", "D3", "D3", "F3", "E3", "D3"], ["Bb2", "Bb2", "F3", "Bb2", "Bb2", "D3", "C3", "Bb2"],
        ["C3", "C3", "G2", "C3", "C3", "E3", "D3", "C3"], ["A2", "A2", "E3", "A2", "C#3", "A2", "E3", "A2"]]
STORM_HARM = ["Dm", "Bb", "C", "A"]


def wind_run(p, b, up=True, vel=60):
    """A flute 'wind' gust: a 16th-note D minor scale run up (or down) over two beats."""
    sc = scale_run("D5", "D6", DM_SCALE)
    sc = sc if up else sc[::-1]
    for i, m in enumerate(sc): p.add(b + i * .25, m, .3, vel + (i * 3 if up else -i * 2))


def cue_storm(c):
    """D minor, fast and exciting, never horror (an adventure gallop, not dissonance): cello / contrabass ostinato,
    tremolo violins, rising string waves, frame drum, timpani rolls and ride-cymbal swells into crashes, flute 'wind'
    runs; a timpani hit + crash on each `thunder`; "Teacher, wake up!" lifts it (violins up an octave, double-time
    drum); at Jesus' "Wind, stop!" the gallop stops and the band holds an A chord on tremolo and a soft roll to the
    end, so the `calm` cue arrives as a sudden hush."""
    s = Score(c, 144, 4); n = s.bars; total = n * 4
    vc = P(s, "cello gallop", CELLO, -2, .3, lp=3500, human=.006)
    cbp = P(s, "contrabass", CBASS, -5, .3, lp=1100, human=.006)
    tr = P(s, "tremolo violins", TREM_STR, -7, .5, lp=5500)
    wave = P(s, "string waves", STRINGS, -8, .4, lp=5500, human=.006)
    fl = P(s, "flute wind", FLUTE, -8, .45, human=.004)
    tim = P(s, "timpani", TIMPANI, -3, .35, lp=1800)
    cym = P(s, "cymbals", DRUMS, -9, .5, lp=8000)
    dr = P(s, "frame drum", DRUMS, -8, .2, lp=3500, human=.005)
    padp = P(s, "pad", SLOW_STR, -8, .5, lp=3000)
    th = [s.at(t) for t in c.all("sfx", id="thunder")]
    tw = beat_of(s, next((l for l in sorted(c.all("lines", who="peter"))[1:2]), None), total * .55)   # "Teacher, wake up!"
    js = c.all("lines", who="jesus"); cm = s.at(js[0]) if js else total - 10                            # "Wind, stop!"
    cmb = min(total - 2, math.floor(cm / 4) * 4 + (4 if cm % 4 > 1.5 else 0))   # the gallop stops at this bar line
    twb = round(tw / 4) * 4
    for bar in range(n):
        b = bar * 4; h = STORM_HARM[bar % 4]; ps = chord(h)
        if b >= cmb: break
        hot = b >= twb
        for i, p_ in enumerate(OSTI[bar % 4]):
            vc.add(b + i * .5, p_, .42, 80 if i % 4 == 0 else 64); cbp.add(b + i * .5, low(note(p_)) if note(p_) > note("E2") else p_, .42, 62)
        tr.chord(b, [ps[1] + (24 if hot else 12), ps[2] + 12], 4.2, 44); tr.ramp(b, b + 4, 11, 80, 112)
        if bar % 2 == 0:
            for k_, p_ in enumerate(scale_run("D4", "D6", DM_SCALE)[::2][:8]): wave.add(b + 2 + k_ * .25, p_ + (0 if h in ("Dm", "Bb") else 2), .5, 58 + 3 * k_)
        if bar % 4 in (1, 3): wind_run(fl, b + (2 if bar % 4 == 1 else 0), up=bar % 4 == 1, vel=58 + (8 if hot else 0))
        tim.add(b, low(ps[0]) if low(ps[0]) >= note("F2") else ps[0], 1.6, 84); tim.add(b + 2, ps[1] - 12, 1.4, 66)
        groove(dr, b, "D.tkD.tkD.tkDktk" if hot else "D.tkD.tkD.tkD.tk", .25, FRAME, .85)
        if bar % 4 == 3: roll(tim, b + 3, b + 4, "A2", 54, 86, .2)
        if bar % 4 == 2: roll(cym, b + 1, b + 4, RIDE, 24, 70, .125)
        if bar % 4 == 0 and bar > 0: cym.add(b, CRASH, 3, 50)
    for t_ in th:
        if t_ is not None and t_ < cmb - .5:
            tim.add(t_, "D2", 2, 110); cym.add(t_, CRASH, 3, 72); tr.chord(t_, [note("D5"), note("A5")], 1.0, 70)
    # "Wind, stop!": the gallop stops, a hit, then a held A chord (tremolo + soft roll) into the hush
    ps = chord("A"); tim.add(cmb, "A2", 2, 96); cym.add(cmb, CRASH, 3, 56)
    tr.chord(cmb, [ps[1] + 12, ps[3] + 12, ps[2] + 12], total - cmb + .5, 48); tr.ramp(cmb, total, 11, 100, 70)
    padp.chord(cmb, ps[1:], total - cmb + .5, 54); padp.ramp(cmb, total, 11, 100, 76)
    cbp.add(cmb, "A1", total - cmb + .5, 60); roll(tim, cmb + 1, total, "A2", 30, 46, .2)
    return s


# ----------------------------------------------------------------------------------------------- calm
def cue_calm(c):
    """The sudden hush: no attack, a still held D major (add 9) chord, very soft strings and choir 'oo' like still
    water, one harp note on the `sparkle`, and the Jesus theme (bars 1-2) very soft on a solo flute; settles on D."""
    s = Score(c, 66, 4); n = s.bars; total = n * 4
    padp = P(s, "still strings", SLOW_STR, 2, .6, lp=2600)
    oohs = P(s, "choir oo", OOHS, -8, .7, lp=3000)
    fl = P(s, "flute (Jesus)", FLUTE, -12, .55, human=.01)
    harp = P(s, "harp", HARP, -10, .6)
    cb = P(s, "contrabass", CBASS, -14, .4, lp=700)
    sp = beat_of(s, c.first("fx", id="sparkle"), .6)
    padp.chord(0, chord("Dadd9")[1:], total + .5, 36); padp.cc(0, 11, 40); padp.ramp(0.05, 2.5, 11, 40, 82)
    oohs.chord(.5, [note("A4"), note("D5")], total, 30); oohs.cc(0, 11, 40); oohs.ramp(.5, 3, 11, 40, 80)
    cb.add(.25, "D2", total + .3, 36)
    harp.add(sp, "A5", 4, 34); harp.add(sp + 2, "E6", 4, 26)
    tb = 1.5
    if total - tb >= 8:
        notes = jesus([1, 2]); notes[-1] = ("D5", total - tb - 7 + .5)
    else:
        notes = jesus([1])
    mel(fl, tb, notes, 52, legato=.98, vib=True)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """Morning: both themes together in full over the JOINT harmony: flute + violins sing the Jesus theme, the oud plays
    the friends theme (major) under it, harp, frame drum and claps join on the second pass; the cue ends on a bright
    held D chord with a harp roll, glock and a soft timpani stroke."""
    s = Score(c, 104, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (Jesus)", FLUTE, -3, .45, human=.01)
    vln = P(s, "violins", STRINGS, -9, .5, lp=5000)
    padp = P(s, "strings", SLOW_STR, -7, .5, lp=3500)
    oud = P(s, "oud (friends)", OUD, -4, .3, lp=4200, human=.006)
    harp = P(s, "harp", HARP, -8, .45)
    vc = P(s, "cello", CELLO, -7, .4, lp=3500)
    cb = P(s, "contrabass", CBASS, -9, .3, lp=1100)
    dr = P(s, "frame drum", DRUMS, -10, .2, lp=3500, human=.005)
    hands = P(s, "claps", DRUMS, -6, .25, human=.004)
    oohs = P(s, "choir oohs", OOHS, -14, .6, lp=4000)
    gl = P(s, "glock", GLOCK, -14, .5)
    tim = P(s, "timpani", TIMPANI, -12, .4, lp=900)
    plan = me.fill_phrase(n, 4, 4, min_intro=0)
    passes = sum(1 for k in plan if k == 0)
    p_i = -1
    for bar, k in enumerate(plan):
        b = bar * 4
        if k is None:
            pad(padp, b, "D", 4, 44, (60, 90)); harp_arp(harp, b, "D", 4, 44); cb.add(b, "D2", 4, 48); continue
        if k == 0: p_i += 1
        full = p_i >= 1
        last_bar = bar == n - 1
        if not last_bar:
            mel(fl, b, jesus([k + 1]), 76 if full else 68, legato=.97, vib=True)
            mel(vln, b, jesus([k + 1]), 54 if full else 40, legato=.98)
            oud_line(oud, b, friends([k + 1], major=True), 72 if full else 64)
        else:                                          # the final bar: A-B up to the bright held D
            mel(fl, b, [("A4", 1), ("B4", 1), ("D5", 4)], 80, legato=.97, vib=True)
            mel(vln, b, [("A4", 1), ("B4", 1), ("D5", 4)], 56, legato=.98)
            oud_line(oud, b, [("B4", .5), ("A4", .5), ("G4", .5), ("E4", .5)], 70)
        def chordfn(bb, name, d):
            pad(padp, bb, name, d, 52 if full else 46, (80, 104)); cb.add(bb, low(chord(name)[0]), d, 52)
            vc.add(bb, chord(name)[1] - 12 if chord(name)[1] - 12 >= note("C2") else chord(name)[1], d * .95, 56)
            if not full: harp_arp(harp, bb, name, d, 44)
            else: oohs.chord(bb, chord(name)[2:], d + .2, 40)
        harm(b, JOINT, [k + 1], chordfn)
        if full and not last_bar:
            groove(dr, b, "D..tD.k.D..tD.kt", .25, FRAME, .75); groove(hands, b, "....c.......c...", .25, HANDS, .8)
    # the bright held chord
    fe = total - 2
    ps = chord("D")
    padp.chord(fe, ps[1:] + [ps[3] + 12], 4, 60); oohs.chord(fe, [ps[2], ps[3], ps[3] + 12], 4, 46)
    vln.chord(fe, [note("A5"), note("D6"), note("F#6")], 4, 50, strum=.04)
    run(harp, fe, [ps[0], ps[1], ps[2], ps[3], ps[1] + 24, ps[2] + 24, ps[3] + 24], .1, 56, 4)
    for i, p_ in enumerate(["D6", "F#6", "A6", "D7"]): gl.add(fe + .25 + i * .3, p_, 3, 44)
    tim.add(fe, "D2", 3, 60); cb.add(fe, "D2", 4, 56)
    return s


# =============================================================================================== loop sections
VAMP = {"capernaum": ("D", "bed"), "friends": ("D", "march"), "no_way": ("D", "tiptoe"), "roof": ("A", "bed"),
        "lowering": ("A", "hush"), "heal": ("D", "choir"), "joy": ("D", "march"), "evening": ("Dm", "hush"),
        "storm": ("A", "rumble"), "calm": ("D", "hush"), "finale": ("D", "choir")}


def arp_steps(s): return (s.bpb * 2, .5) if s.bpb in (3, 4) else (s.bpb, 1.0)


def add_vamp(s, chord_name, style, need):
    """After the cadence: identical repeats of >= VAMP_MIN_SEC (whole bars, no humanising), enough of them that the file
    lasts `need` seconds plus the 2.5 s fade. See music_ruth.py / music_jonah.py."""
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    reps = max(4, math.ceil((need - s.span + 2.5) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    quiet = style in ("hush", "tiptoe", "rumble")
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
    if style == "rumble":
        extra["tr"] = P(s, "vamp tremolo", TREM_STR, -10, .5, lp=3500, **v); extra["tim"] = P(s, "vamp timpani", TIMPANI, -16, .4, lp=600, **v)
    for p_ in [padp, cb, harp] + list(extra.values()): p_.vamp = True
    ps = chord(chord_name); steps, st = arp_steps(s); b0 = s.bars * bpb
    for r in range(reps):
        b = b0 + r * Lb
        padp.chord(b, ps[1:], Lb + .3, 34 if quiet else 46); padp.cc(b, 11, 92)
        cb.add(b, low(ps[0]), Lb + .2, 44 if quiet else 48)
        if style == "choir":
            extra["oohs"].chord(b, [ps[1] + 12, ps[3]], Lb + .3, 40); extra["oohs"].cc(b, 11, 92)
        if style == "rumble":
            extra["tr"].chord(b, [ps[1] + 12, ps[2] + 12], Lb + .3, 36); extra["tr"].cc(b, 11, 90)
            for i in range(int(Lb / .25)): extra["tim"].add(b + i * .25, low(ps[0]) + 12 if low(ps[0]) + 12 <= note("D3") else low(ps[0]), .3, 30 + (6 if i % 4 == 0 else 0))
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


MUSIC = {"capernaum": cue_capernaum, "friends": cue_friends, "no_way": cue_no_way, "roof": cue_roof,
         "lowering": cue_lowering, "heal": cue_heal, "joy": cue_joy, "evening": cue_evening, "storm": cue_storm,
         "calm": cue_calm, "finale": cue_finale}
METER = {"evening": "6/8"}
KEYS = {"capernaum": "D mixolydian -> D major", "friends": "D mixolydian", "no_way": "D (A7 pedal)",
        "roof": "D rising (D-E-G-A) -> A", "lowering": "D minor -> A", "heal": "D major", "joy": "D major",
        "evening": "G major -> D minor", "storm": "D minor -> A", "calm": "D major", "finale": "D major"}
CUE_NOTES = {
    "capernaum": "Market morning: frame drum, tambourine, tremolo strings, pizz bass, oud market tune; at Jesus' line it thins and the flute sings the JESUS theme bars 1-2.",
    "friends": "FRIENDS theme on oud (harp double, flute an octave up at the end) with a heave-ho cello, swung frame drum, claps on 2 and 4.",
    "no_way": "Stop-start pizz, tuba 'bonk' (bent down) on `boing`, tick-tock blocks + thinking clarinet on A7, celesta/glock 'idea' on `ding`, oud lifts the theme.",
    "roof": "FRIENDS bar 1 climbing D-E-G-A; digging rhythm (blocks, shaker, drum) under theme bars 3-4 from `dig_loop`; xylophone tumble on `crumble`; tuba bonk at 'My roof!'; flute giggle at Jesus' laugh; ends on A.",
    "lowering": "Very soft: held D minor add9 strings, cello pedal, one harp note every 2 beats down the scale, faint timpani; turns to A.",
    "heal": "JESUS theme bars 1-4 on solo flute over strings + harp; celesta on `heart_glow`; cello answers; swell on 'Get up!' (timpani roll, harp gliss, violins, choir) into the high bars 5-8.",
    "joy": "Dance: fast oud FRIENDS theme in major, claps, tambourine, frame drum + bongos, offbeat string chops; last pass adds the JESUS theme on flute + violins (JOINT harmony).",
    "evening": "6/8 barcarolle in G: harp, soft strings, lapping pizz + conga; low flute JESUS theme in 6/8; thins at `zzz`; last bar darkens to D minor with a timpani roll.",
    "storm": "Adventure gallop in D minor: cello/bass ostinato, tremolo violins, string waves, flute wind runs, frame drum, timpani rolls, ride swells into crashes; hits on each `thunder`; lifts at 'Teacher, wake up!'; holds A on tremolo from 'Wind, stop!'.",
    "calm": "Sudden hush: held D add9 strings + choir 'oo', no attack; harp on `sparkle`; JESUS theme bars 1-2 very soft on solo flute.",
    "finale": "Both themes together (JOINT): JESUS theme on flute + violins, FRIENDS theme (major) on oud; drum + claps + choir on the second pass; bright held D chord, harp roll, glock, timpani.",
}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG
place_ = lambda dst, src, at: me.place(dst, src, at)
LOOP_SECS = {"wind_loop": 10.0}      # whole-file seamless loops (dig_loop is a one-shot sized to its scene, below)
WRAP = 0.6


def make_loop(y, secs):
    """y is secs + WRAP long; fold the overhang onto the start so the end flows into the beginning."""
    n, k = int(secs * SR), int(WRAP * SR); out = y[:n].copy(); w = np.linspace(0, 1, k)
    out[:k] = y[:k] * np.sqrt(w) + y[n:n + k] * np.sqrt(1 - w)
    return out


def bell(secs, *a, **kw):
    y = me.partials(secs, *a, **kw); k = min(len(y), int(.04 * SR)); y[-k:] *= np.linspace(1, 0, k); return y


def tone(f_curve, amp=1.0, h2=0.0):
    ph = 2 * np.pi * np.cumsum(f_curve) / SR
    return amp * (np.sin(ph) + h2 * np.sin(2 * ph))


def bubble(f0, secs=.12, rise=.5, amp=1.0):
    m = int(secs * SR); t = np.arange(m) / SR
    f = f0 * (1 + rise * np.minimum(1, t / (secs * .6)))
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-t / (secs * .35)) * np.minimum(1, t / .002)


def sfx_crowd_murmur(ctx):
    """A full house: ~70 short murmured syllables (men, women, two children) at talking pitch with moving vowels, low
    and blurred (low-passed, roomy), on a soft bed of shuffling; swells in, holds, fades. Words are not intelligible."""
    secs = 6.0; n = int(secs * SR); y = np.zeros(n)
    vowels = ["a", "e", "o", "u", "i", "ah", "eh"]
    for _ in range(72):
        who = R().choice(["man", "woman", "child"], p=[.45, .45, .1])
        scale = {"man": R().uniform(.92, 1.02), "woman": R().uniform(1.1, 1.2), "child": R().uniform(1.25, 1.35)}[who]
        f = {"man": R().uniform(100, 150), "woman": R().uniform(190, 250), "child": R().uniform(260, 330)}[who]
        d = R().uniform(.18, .5); m = int(d * SR); tt = np.arange(m) / SR
        f0 = f * np.interp(tt, [0, d * .5, d], [1.0, R().uniform(1.02, 1.15), R().uniform(.85, .95)])
        keys = [(0, "h"), (.15, str(R().choice(vowels))), (.7, str(R().choice(vowels))), (1, "h")]
        env = np.sin(np.pi * np.clip(tt / d, 0, 1)) ** .8
        v = me.voice(d, f0, keys, scale, breath=.3, jitter=.02, vib=(5, .01), amp_env=env)
        place_(y, v / (np.std(v) + 1e-9) * R().uniform(.15, .5), R().uniform(0, secs - d))
    y = me.lp(me.hp(y, 160), 2800)
    t = np.arange(n) / SR
    y += me.bp(noise(n), 300, 2500) * .03 * (1 + .5 * me.smooth_rand(n, 2))
    y *= np.minimum(1, t / .8) * np.minimum(1, (secs - t) / 2.0)
    return me.fit(me.room(y, "room", .35), secs, fade_out=.3)


def sfx_boing(ctx):
    """Comic bounce off the crowd: a springy 'boing' (pitch wobbling and falling, 9 Hz) on a soft body thump."""
    secs = .9; n = int(secs * SR); t = np.arange(n) / SR
    f = 260 + 120 * np.sin(2 * np.pi * 9 * t) * np.exp(-t / .3) + 260 * np.exp(-t / .06) - 60 * t
    y = tone(f, .7, .35) * np.exp(-t / .28) * np.minimum(1, t / .003)
    th = np.sin(2 * np.pi * (70 + 80 * np.exp(-t / .03)) * t) * np.exp(-t / .07) * .6
    return me.fit(me.room(y + th, "room", .12), secs, fade_out=.15)


def sfx_ding(ctx):
    """'I've got it!': a bright idea bell, D6 with a fifth above, warm partials, short shimmer."""
    secs = 1.8; n = int(secs * SR); y = np.zeros(n)
    for f, a, at in ((note_hz("D6"), 1.0, 0), (note_hz("A6"), .55, .07)):
        place_(y, bell(1.7, f, [1, 2.0, 2.76, 5.4], [1, .3, .2, .06], [.9, .5, .35, .12], strike=.15) * a, at)
    return me.fit(me.room(y, "hall", .3), secs, fade_out=.5)


def note_hz(p): return 440 * 2 ** ((note(p) - 69) / 12)


def dig_strokes(secs, rate=1.0):
    """Three diggers on a mud-and-branch roof: each stroke = a dull thud (low sine drop + low noise), a gritty scrape
    and a few clods; slightly irregular, each digger at its own pace and loudness."""
    n = int(secs * SR); y = np.zeros(n)
    for dg, (period, amp, tone_hz) in enumerate(((.72, 1.0, 190), (.9, .75, 230), (1.1, .6, 160))):
        at = R().uniform(0, period)
        while at < secs - .05:
            m = int(.35 * SR); tt = np.arange(m) / SR
            thud = np.sin(2 * np.pi * (tone_hz + 60 * np.exp(-tt / .02)) * tt) * np.exp(-tt / .05)
            thud += me.bp(noise(m), 200, 1200) * np.exp(-tt / .04) * .8
            scr = me.bp(noise(m), 1200, 4500) * np.exp(-((tt - .07) / .05) ** 2) * .7
            s_ = (thud + scr) * np.minimum(1, tt / .002)
            for _ in range(int(R().integers(2, 5))):
                k = int(.03 * SR); cl = me.bp(noise(k), 600, 3000) * me.env_exp(k, .006)
                place_(s_, cl * R().uniform(.2, .5), R().uniform(.05, .25))
            place_(y, s_ * amp * R().uniform(.8, 1.1), at)
            at += period * R().uniform(.85, 1.15) / rate
    return y


def sfx_dig_loop(ctx):
    """Three people digging through the roof, as a one-shot that ends at shot S05 (CONTRACT 7): StoryDirector can stop a
    loop only at a music cue, and `roof` runs on through S05, so the file itself is sized from its start to S05's start
    in the zh play (the shortest) + 0.5 s, fading out over the last 0.6 s. The id keeps its contract name."""
    s05 = next(s["t0"] for s in ctx["tl"]["shots"] if s["id"] == DIG_STOP_SHOT)
    secs = max(3.0, s05 - ctx["t"] + 0.5)
    y = me.room(dig_strokes(secs), "room", .15)[:int(secs * SR)]
    return me.fit(y, secs, fade_in=.3, fade_out=.6)


def sfx_crumble(ctx):
    """The roof gives way a little: a soft thump, a pour of dirt and dry grass (hundreds of grains thinning out), a few
    bigger clods landing, a last trickle."""
    secs = 2.6; n = int(secs * SR); t = np.arange(n) / SR
    y = np.sin(2 * np.pi * (60 + 50 * np.exp(-t / .04)) * t) * np.exp(-t / .12) * .7
    pour = me.bp(noise(n), 800, 6000) * np.exp(-t / .6) * np.minimum(1, t / .03) * .35
    y += pour * (1 + .6 * me.smooth_rand(n, 25))
    for _ in range(260):
        at = R().exponential(.45)
        if at > secs - .1: continue
        k = int(.01 * SR); g = me.bp(noise(k), 1500, 7000) * me.env_exp(k, .002)
        place_(y, g * R().uniform(.1, .5), at)
    for at in (.25, .5, .8, 1.3):
        k = int(.15 * SR); tt = np.arange(k) / SR
        place_(y, me.lp(noise(k), 900) * np.exp(-tt / .03) * .6, at + R().uniform(-.05, .05))
    return me.fit(me.room(y, "room", .2), secs, fade_out=.6)


def sfx_rope_creak(ctx):
    """Ropes taking the weight: three slow wooden creaks (stick-slip pulses at a wandering 25-70 Hz through wood
    resonances at 380 / 820 / 1650 Hz), the last one longest."""
    secs = 3.4; n = int(secs * SR); y = np.zeros(n)
    for at, d, f0, f1 in ((.05, .7, 30, 55), (1.0, .8, 45, 28), (2.0, 1.2, 28, 65)):
        m = int(d * SR); tt = np.arange(m) / SR
        rate = np.interp(tt, [0, d], [f0, f1]) * (1 + .25 * me.smooth_rand(m, 12))
        ph = np.cumsum(rate) / SR; pulses = np.zeros(m)
        idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
        pulses[idx] = R().uniform(.6, 1.0, len(idx))
        src = pulses + me.hp(noise(m), 2000) * .02
        z = sum(me.resonator(src, fr, bw) * g for fr, bw, g in ((380, 40, 1.0), (820, 60, .7), (1650, 90, .4)))
        env = np.sin(np.pi * tt / d) ** .6
        place_(y, z * env, at)
    y = y / (np.max(np.abs(y)) + 1e-9)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.3)


def sfx_sparkle(ctx): return me.sfx_sparkle()


def sfx_cheer(ctx): return me.sfx_cheer()


def lap_bed(secs):
    """Small waves against a boat: slow low-passed water swells (every ~1.6 s) with a little slap at each crest and a
    few drips, very gentle."""
    n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    at = R().uniform(0, .5)
    while at < secs:
        d = R().uniform(1.0, 1.6); m = int(d * SR); tt = np.arange(m) / SR
        sw = me.lp(noise(m), R().uniform(500, 900)) * np.sin(np.pi * tt / d) ** 2
        slap = me.bp(noise(m), 900, 3500) * me.env_exp(m, .04, d * .45) * .35
        place_(y, (sw + slap) * R().uniform(.6, 1.0), at); at += R().uniform(1.3, 1.9)
    for _ in range(int(secs * 2)):
        place_(y, bubble(R().uniform(900, 2200), R().uniform(.03, .07), .4, R().uniform(.05, .15)), R().uniform(0, secs - .1))
    return y


def sfx_lake_lap(ctx):
    """Evening lake: 7 s of gentle lapping against the boat, fades in and out (one-shot)."""
    secs = 7.0; n = int(secs * SR); t = np.arange(n) / SR
    y = lap_bed(secs) * np.minimum(1, t / 1.0) * np.minimum(1, (secs - t) / 2.0)
    return me.fit(me.room(y, "room", .2), secs, fade_out=.2)


def sfx_thunder(ctx):
    """A big, round rumble (not scary): a soft-edged crack, then a rolling low boom (from music_jonah.py)."""
    secs = 5.0; n = int(secs * SR); t = np.arange(n) / SR; nz = noise(n)
    crack = me.bp(nz, 600, 3500) * me.env_exp(n, .09) * np.minimum(1, t / .01) * .45
    rl = me.lp(noise(n), 140) * (1 + .6 * me.smooth_rand(n, 4)) * np.minimum(1, t / .06) * np.exp(-t / 1.5)
    mid = me.lp(noise(n), 420) * (1 + .5 * me.smooth_rand(n, 7)) * np.minimum(1, t / .05) * np.exp(-t / .75) * .6
    sub = np.sin(2 * np.pi * (52 - 14 * np.minimum(t, 2) / 2) * t) * np.minimum(1, t / .08) * np.exp(-t / 1.2) * .35
    y = crack + rl * 2.2 + mid + sub
    return me.fit(me.room(y, "hall", .3), secs, fade_out=1.0)


def wind_bed(secs, gust=1.0):
    """Storm wind: a broadband rush through a slowly moving band-pass (300-1400 Hz), gust swells, a low roar, a little
    airy whistle kept soft (exciting, not eerie), plus spray."""
    n = int(secs * SR); t = np.arange(n) / SR
    g = .6 + .4 * (.5 + .5 * me.smooth_rand(n, .35)) * gust
    cut = 300 * (1400 / 300) ** (.5 + .5 * me.smooth_rand(n, .5))
    rush = me.wah_filter(noise(n), cut, .5, 2.0) * g
    roar = me.lp(noise(n), 220) * (.7 + .3 * me.smooth_rand(n, .8)) * .8
    spray = me.hp(noise(n), 4000) * (.5 + .5 * me.smooth_rand(n, 3)) ** 2 * .12
    wh = me.bp(noise(n), 1800, 2400) * g ** 3 * .08
    return rush + roar + spray + wh


def sfx_wind_loop(ctx):
    """10 s seamless storm wind (wrap-folded); `wind_stop` ends it."""
    secs = LOOP_SECS["wind_loop"]
    return make_loop(wind_bed(secs + WRAP), secs)


def sfx_wind_stop(ctx):
    """'Wind, stop!': the wind collapses in ~1.2 s (the band falls, the roar drains), a last sigh of air, then still
    water: two soft laps and a drip."""
    secs = 4.0; n = int(secs * SR); t = np.arange(n) / SR
    y = wind_bed(secs) * np.exp(-t / .45) * np.clip(1.3 - t / 1.2, 0, 1)
    y += me.lp(noise(n), 600) * np.exp(-((t - .9) / .5) ** 2) * .08
    tail = lap_bed(3.0) * .25; place_(y, tail * np.minimum(1, np.arange(len(tail)) / SR / .6), 1.0)
    place_(y, bubble(1600, .06, .4, .3), 3.0)
    return me.fit(me.room(y, "room", .2), secs, fade_in=.01, fade_out=.6)


SFX = {"crowd_murmur": sfx_crowd_murmur, "boing": sfx_boing, "ding": sfx_ding, "dig_loop": sfx_dig_loop,
       "crumble": sfx_crumble, "rope_creak": sfx_rope_creak, "sparkle": sfx_sparkle, "cheer": sfx_cheer,
       "lake_lap": sfx_lake_lap, "thunder": sfx_thunder, "wind_loop": sfx_wind_loop, "wind_stop": sfx_wind_stop}
SFX_SEED = {}
SFX_GAIN = {"crowd_murmur": -16, "boing": -10, "ding": -16, "dig_loop": -17, "crumble": -12, "rope_creak": -14,
            "sparkle": -13, "cheer": -12, "lake_lap": -17, "thunder": -9, "wind_loop": -18, "wind_stop": -15}
SFX_SHAPE = {"ding": (0.6, 0.5), "thunder": (0.4, 0.9), "sparkle": (0.9, 0.6), "cheer": (1.6, 1.0)}
LOOP_STOP_SHOT = {}                       # loop id -> shot it should stop at (none: dig_loop became a one-shot)
DIG_STOP_SHOT = "S05"                     # CONTRACT 7: dig_loop ends at shot S05
SFX_NOTES = {
    "crowd_murmur": "~70 murmured formant syllables (men, women, kids), low-passed and roomy, shuffle bed; 6 s, swells in, fades",
    "boing": "springy comic 'boing' (9 Hz wobble, falling) on a soft body thump; 0.9 s",
    "ding": "bright idea bell D6 + A6, warm partials; 1.8 s",
    "dig_loop": "one-shot sized to end at S05 (fade 0.6 s): three diggers, thud (160-230 Hz, audible on a phone) + gritty scrape + clods, irregular pace",
    "crumble": "soft thump, a pour of dirt and grass (260 grains thinning), four clods, trickle; 2.6 s",
    "rope_creak": "three wooden creaks (stick-slip 25-70 Hz through 380 / 820 / 1650 Hz resonances); 3.4 s",
    "sparkle": "kit sparkle (music_kit.sfx_sparkle): rising D major pentatonic bell shower",
    "cheer": "kit cheer (music_kit.sfx_cheer): 22 'yay / wooo' voices and clapping",
    "lake_lap": "7 s of gentle lapping against the boat (low swells, small slaps, drips), fades in / out; one-shot",
    "thunder": "soft-edged crack, rolling 140 Hz boom, 52 Hz sub, 5 s hall decay; round, not scary (from jonah)",
    "wind_loop": "seamless 10 s storm wind (wrap-folded): moving band-pass rush, gusts, low roar, spray, soft whistle",
    "wind_stop": "the wind collapses in ~1.2 s, a sigh of air, then two soft laps and a drip",
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
    if c["t"] > 0.5 and name != "calm": kf = int(.3 * SR); main[:kf] *= np.linspace(0, 1, kf) ** 1.5
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
        print(f"music {name:10s} t={c['t']:7.2f} span={c['span']:6.2f} (longest {longest[name]:6.2f}) file={r['secs']:6.2f}s "
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
                        "Rerun tools/story/music_miracles.py after the timeline is re-timed so the in-cue hits follow.",
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
            if sid in LOOP_STOP_SHOT:
                sh = next((s for s in tl["shots"] if s["id"] == LOOP_STOP_SHOT[sid]), None)
                if sh: e.update(stopAtShot=sh["id"], stopAtSec=sh["t0"])
            sd = np.abs(np.diff(np.concatenate([x[-64:], x[:64]]))); inner = np.abs(np.diff(x[64:-64]))
            h = len(x) // 2; rms = lambda a: 20 * np.log10(np.sqrt(np.mean(a.astype(np.float64) ** 2)) + 1e-12)
            e.update(seamRatio=round(float(sd.max() / inner.max()), 3), halfDb=round(float(rms(x[h:2 * h]) - rms(x[:h])), 2))
        manifest.append(e); clean_tmp()
        print(f"sfx   {sid:13s} {e['secs']:6.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f}"
              + (f" loop, stop at cue {e['stopAtCue']}{(' / shot ' + e['stopAtShot']) if 'stopAtShot' in e else ''}, seam x{e['seamRatio']}, halves {e['halfDb']:+.2f} dB" if loop else ""))
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play each one-shot at its timeline t with gainDb "
                        "(recommended mix level). Entries with loop: true are ambience beds: the whole file is a "
                        "seamless loop (loopStart 0, loopEnd = secs); start it at its t with a fadeInSec fade-in and "
                        "loop it until the music cue named in stopAtCue starts (fade out over fadeOutSec). dig_loop "
                        "is a one-shot whose length ends it at shot S05.",
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


def hit_rows(tl):
    """Where every hit SFX / glow lands inside its cue in the zh play and in the en play (same cue file, so the en offset
    is how far its hit drifts from the composed moment)."""
    en = vm.lang_timeline(SID, "en"); rows = []
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
            if s["loop"]:
                lp_ = f"whole file (seam x{s['seamRatio']}, halves {s['halfDb']:+.2f} dB), stop at `{s['stopAtCue']}`" + (f" (wanted: shot {s['stopAtShot']} = {s['stopAtSec']:.2f} s)" if "stopAtShot" in s else "")
            else:
                lp_ = "one-shot"
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
    longest = max_spans([tl, vm.lang_timeline(SID, "en"), json.load(open(f"{MI}/timeline.json"))])
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, longest, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev)
    if a.spec: spectrograms(a.spec)
