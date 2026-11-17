#!/usr/bin/env python3
"""Original score and sound effects for "Saul Meets Jesus" (story pack `saul`; docs/saul/CONTRACT.md section 7,
docs/saul/DESIGN.md section 5, docs/saul/MUSIC.md).

Built on the shared engine tools/story/music_kit.py (`import music_kit as me`) and the finishing helpers in
tools/story/music_polish.py; the loop-section / build machinery is copied from music_risen.py (same shape, same
cues.json / mix.json format). This script holds only this pack's cues, effects, paths and tables.

The warm acoustic band of the Jesus packs (oud = GM nylon guitar low-passed, flute, harp, strings, cello, frame drum,
a children's "ah" choir) with a low brass and snare colour for the soldier. Two themes:
  * SAUL'S MARCH (original, 4 bars): a stomping D-minor march (D-D-F-A-G / F-F-G-A / Bb-Bb-A-G-F / E-E-D) with a stern
    oud figure, tuba, snare and low strings: comic-stern, never scary. After Saul changes the SAME tune comes back in
    D MAJOR (F -> F#, Bb -> B), skipping, on flute, oud and pizzicato (brother's hint, new_saul), and in the finale the
    whole band plays it with the choir while the JESUS theme's bars 1-4 sing above it (the JOINT harmony idea of
    music_miracles.py): the same tune, a changed heart.
  * the JESUS theme is imported from music_miracles.py (JESUS, JESUS_HARM), unchanged, exactly as risen and lastsupper
    do: under the light and the voice (light), answering Ananias (ananias), in full at "Brother Saul" (brother), and
    its first bar left unresolved while Saul prays (three_days).
Every melody is original; nothing is taken from any film.

Every name and time comes from the timeline, read on every run: the cues are composed for the play as the phone runs
it in Chinese (voice_margin.lang_timeline, re-timed to the installed zh clips; the shortest play, so no cadence is cut
off), in-cue hits are looked up by line id / sfx / fx events. Every file is long enough for its section in the zh play,
the en play and assets/saul/timeline.json x 1.3 + 0.6 s, and after its cadence continues into a quiet loop section
with sample-exact loop points in cues.json. All sound effects are one-shots sized to their scene (StoryDirector
stops loops only at a music cue). Rerun after re-timing.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/saul/audio/music/<cue>.wav|.mp3   music, -20 LUFS (+-1) over the composed span, true peak <= -1 dBTP
  assets/saul/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/saul/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/saul/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain
  assets/saul/audio/preview_mix.mp3        full-length mix of the zh play as the engine mixes it
  docs/saul/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_saul.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--tmp DIR] [--spec DIR]   (scratch default /tmp/saul_music; --spec writes spectrogram PNGs)
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
from music_miracles import JESUS, JESUS_HARM, JOINT                        # noqa: E402  (the shared Jesus theme)
from music_kit import (Score, Ctx, mel, groove, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB,  # noqa: E402
                       HARP, NYLON, CELESTA, GLOCK, XYLO, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS,
                       CHOIR, OOHS, FLUTE, RECORDER, BASSOON, CLARINET, SHANAI, TIMPANI, TUBA, TRUMPET, HORN, DRUMS,
                       CLAP, TAMB, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA, HI_WOOD, LO_WOOD,
                       SHAKER, TRIANGLE, SNARE, BDRUM)

SID = "saul"
ROOT = me.ROOT
LS = f"{ROOT}/assets/{SID}"
MUSIC_DIR, SFX_DIR = f"{LS}/audio/music", f"{LS}/audio/sfx"
PREVIEW = f"{LS}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/{SID}/MUSIC.md"
STRETCH = 0.30                 # every file covers its longest section (zh / en / base timeline) x 1.3 + 0.6 s
VAMP_MIN_SEC = 4.0             # a loop section is at least this long (longer than the hall's audible tail)
VAMP_REL_DB = -4.5             # loop section loudness relative to the cue's composed span
SPAN_LUFS = -20.0              # composed span loudness (contract -20 +-1)
# a little range inside the contract's +-1 LU: the blind walk and the prayer sit lower, the new Saul and the finale higher
CUE_LUFS = {"dark_walk": -21.0, "three_days": -21.0, "road": -20.4, "ananias": -20.4, "basket": -20.4,
            "new_saul": -19.7, "finale": -19.5}
HIT_SFX = {"light_whoosh"}     # the road-light moment: the one place the underscore swells (clear of speech in zh)
HIT_FX = set()
NO_SWELL = set()
AFTER_LINE = {}
END_SWELL = {"finale"}         # the last cue swells back up on its final chord
# extra dips under lines the score cannot get out of the way of: cue -> [(line id, dB)], resolved from the zh play
DIPS = {"angry_march": [("sa_02", -2.5), ("sa_03", -3.0)], "light": [("sa_11", -2.0)], "ananias": [("sa_19", -2.0)],
        "brother": [("sa_24", -2.5), ("sa_25", -2.0)], "new_saul": [("sa_30", -2.0)], "basket": [("sa_34", -2.5)],
        "barnabas": [("sa_39", -3.0)]}
WHO_LINES = None
TMP_PREFIX = "music_saul_"


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



# =============================================================================================== Saul's march
# Four bars, D minor, 4/4. In major (F -> F#, Bb -> B) it is the "turned around" tune.
SAUL = {0: [("D4", 1), ("D4", .5), ("F4", 0.5), ("A4", 1.5), ("G4", .5)],
        1: [("F4", 1), ("F4", .5), ("G4", .5), ("A4", 2)],
        2: [("Bb4", 1), ("Bb4", .5), ("A4", .5), ("G4", 1), ("F4", 1)],
        3: [("E4", 1), ("E4", 1), ("D4", 2)]}
SAUL_HARM_MIN = {0: [("Dm", 4)], 1: [("Dm", 4)], 2: [("Gm", 4)], 3: [("A", 2), ("Dm", 2)]}
SAUL_HARM_MAJ = {0: [("D", 4)], 1: [("D", 4)], 2: [("G", 4)], 3: [("A", 2), ("D", 2)]}


def saul(bars, major=False, shift=0):
    """Saul's march as (pitch, beats) items; major raises F and Bb by a semitone."""
    out = []
    for k in bars:
        for p, d in SAUL[k]:
            m = note(p) + shift
            if major and (p.startswith("F") or p.startswith("Bb")): m += 1
            out.append((m, d))
    return out


def play(p, b0, notes, vel=70, legato=.92, swing=0.0, vib=False, stacc=False, accent=0):
    """Like mel() for integer-pitch items, with an optional skip (swing: off-beat eighths land `swing` beats late and the
    note before them is lengthened to meet them) and a velocity accent on the beat."""
    pos = []; b = b0
    for pitch, d in notes:
        late = swing if swing and abs((b % 1) - .5) < 1e-6 else 0.0
        pos.append([b + late, d - late, pitch]); b += d
    for i in range(len(pos) - 1):
        if abs((pos[i + 1][0] - pos[i][0]) - notes[i][1]) > 1e-6 and pos[i + 1][0] > pos[i][0]:
            pos[i][1] = pos[i + 1][0] - pos[i][0]
    for (bb, dd, pitch), (_, d0) in zip(pos, notes):
        if pitch is None: continue
        v = vel + (accent if abs(bb % 1) < 1e-6 else 0) + me.RNG.normal(0, 2)
        p.add(bb, pitch, dd * (.45 if stacc else legato), v)
        if vib and p.s.sec(dd) >= .55 and not stacc: p.vibrato(bb, dd)
    return b


def mode_harm(major): return SAUL_HARM_MAJ if major else SAUL_HARM_MIN


def snap(b, bpb=4): return math.floor(b / bpb + .5) * bpb


STOMP = {"k": (BDRUM, 66), "S": (SNARE, 62), "s": (SNARE, 36), "r": (SNARE, 50)}


# ----------------------------------------------------------------------------------------------- angry_march
def cue_angry_march(c):
    """Saul's march in D minor, comic-stern: the stern oud figure (the tune) doubled an octave down by cellos, a tuba
    stomping oom-pah (root on 1 and 3, fifth on 2 and 4), a bass drum and a stiff snare with a little roll at the end of
    each phrase. Nothing high or sharp; the tune is the same in every phrase."""
    s = Score(c, 104, 4); n = s.bars; total = n * 4
    oud = P(s, "oud (stern figure)", OUD, -4, .3, lp=4200, human=.004)
    vc = P(s, "cellos", CELLO, -7, .35, lp=2600, human=.005)
    tuba = P(s, "tuba", TUBA, -8, .25, lp=1300, human=.004)
    cb = P(s, "basses", CBASS, -13, .3, lp=900)
    sn = P(s, "snare + drum", DRUMS, -9, .15, lp=5200, human=.004)
    pz = P(s, "pizz", PIZZ, -9, .25)
    plan = me.fill_phrase(n, 4, 4, min_intro=0)
    for bar, k in enumerate(plan):
        b = bar * 4
        if k is None:
            for q in range(4): tuba.add(b + q, "D2" if q % 2 == 0 else "A2", .5, 52)
            continue
        play(oud, b, saul([k]), 66 + (6 if bar >= 4 else 0), legato=.85, accent=6)
        play(vc, b, saul([k], shift=-12), 46, legato=.95)
        def chordfn(bb, name, d):
            ps = chord(name)
            for q in range(int(d)):
                tuba.add(bb + q, low(ps[0]) if q % 2 == 0 else ps[1] - 12, .6, 62 if q % 2 == 0 else 46)
            cb.add(bb, low(ps[0]), d, 34); pz.add(bb + .5, ps[2], .2, 36)
        harm(b, SAUL_HARM_MIN, [k], chordfn)
        groove(sn, b, "k.S.k.S." if k != 3 else "k.S.SsSr", .5, STOMP, 1.0)
    return s


# ----------------------------------------------------------------------------------------------- road
def cue_road(c):
    """The same march at a hot, trudging pace (quieter, heavier steps): the tune on solo cello with a soft tuba oom-pah, a
    puffing bassoon (short breaths on the off-beats), and a heat shimmer, a high tremolo violin swelling and fading
    every bar. For the short guard's "my feet are flat!" the bassoon sighs down; the march ends on a stiff D minor."""
    s = Score(c, 84, 4); n = s.bars; total = n * 4
    vc = P(s, "cello (march)", CELLO, -5, .3, lp=2600, human=.005)
    tuba = P(s, "tuba", TUBA, -9, .25, lp=1200, human=.004)
    bsn = P(s, "bassoon puffs", BASSOON, -7, .3, lp=2400, bend=True, human=.004)
    sh = P(s, "heat shimmer", TREM_STR, -13, .55, lp=6500)
    fr = P(s, "frame drum", DRUMS, -12, .15, lp=3000, human=.005)
    cb = P(s, "basses", CBASS, -13, .3, lp=900)
    plan = me.fill_phrase(n, 4, 4, min_intro=1)
    sg = lbeat(s, c, "sa_05", "start", total * .3)
    for bar, k in enumerate(plan):
        b = bar * 4
        ps = chord("Dm")
        sh.chord(b, ["A5", "D6", "F6"], 4.3, 40); sh.ramp(b, b + 2, 11, 36, 84, .8); sh.ramp(b + 2, b + 4, 11, 84, 36, 1.2)
        if k is None:
            for q in (0, 2): tuba.add(b + q, "D2", .8, 52)
            for q in (.5, 1.5, 2.5, 3.5): bsn.add(b + q, "D3", .25, 40)
            cb.add(b, "D2", 4, 34); continue
        play(vc, b, saul([k], shift=-12), 56, legato=.9)
        def chordfn(bb, name, d):
            ps = chord(name)
            for q in range(int(d)):
                tuba.add(bb + q, low(ps[0]) if q % 2 == 0 else ps[1] - 12, .7, 54 if q % 2 == 0 else 40)
                if bb + q + .5 < sg - .1 or bb + q + .5 > sg + 2.6:
                    bsn.add(bb + q + .5, ps[1] - (12 if q % 2 else 0), .22, 44 + 4 * (q % 2))
            cb.add(bb, low(ps[0]), d, 34)
        harm(b, SAUL_HARM_MIN, [k], chordfn)
        for q in (0, 2): fr.add(b + q, LO_CONGA, .4, 46)
    bsn.add(sg, "D4", 1.6, 52); bsn.glide(sg + .5, sg + 1.6, 0, -4, 1.3); bsn.bend(sg + 1.9, 0)    # the sigh
    return s


# ----------------------------------------------------------------------------------------------- light
def cue_light(c):
    """The march breaks off and the light comes: a shimmering high tremolo chord (D add9) swells to the `light_whoosh`
    and holds, a harp glissando and celesta glints, the children's choir "ah" opens under it; no drums, no low rumble, no
    thunder. The harmony lifts G -> Dsus -> D under the narrator, then the JESUS theme (bars 1-4) on a slow, warm flute over
    strings and harp under Jesus' words, ending on a held D."""
    s = Score(c, 60, 4); n = s.bars; total = n * 4
    trem = P(s, "shimmer strings", TREM_STR, -11, .55, lp=6000)
    padp = P(s, "strings", SLOW_STR, -8, .55, lp=3500)
    oohs = P(s, "choir ah", OOHS, -12, .6, lp=4200)
    harp = P(s, "harp", HARP, -5, .5)
    cel = P(s, "celesta", CELESTA, -12, .6)
    fl = P(s, "flute (Jesus)", FLUTE, -5, .45, human=.008)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=900)
    plan = me.fill_phrase(n, 4, 4, min_intro=1)
    intro = plan.index(0) if 0 in plan else n
    wb = beat_of(s, c.first("sfx", id="light_whoosh"), 1.0)
    m0 = intro * 4
    trem.chord(0, ["D5", "F#5", "A5", "E6"], m0 + .5, 42); trem.ramp(0, wb + .3, 11, 34, 96, .8); trem.ramp(wb + .3, m0, 11, 96, 60, 1.0)
    run(harp, max(0, wb - .2), [note(p) for p in ("D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5", "B5", "D6")], .1, 48, 2.5)
    for k, p_ in enumerate(("A6", "D7", "F#6", "A6")): cel.add(wb + 1 + k * .8, p_, 2.5, 36 - 3 * k)
    oohs.chord(.5, ["A4", "D5"], m0 - .5, 30); oohs.ramp(.5, wb + 1.5, 11, 40, 90, .8)
    if intro > 0:
        cs = [("Dadd9", wb + 1.5), ("G", (m0 - wb - 1.5) / 2), ("Dsus", (m0 - wb - 1.5) / 2)]
        segs(0, cs, lambda bb, nme, d: (pad(padp, bb, nme, d, 38, (60, 84)), cb.add(bb, low(chord(nme)[0]), d, 34)))
    for bar, k in enumerate(plan):
        b = bar * 4
        if k is None: continue
        mel(fl, b, jesus([k + 1]), 56 if k < 2 else 62, legato=.97, vib=True)
        def chordfn(bb, name, d):
            pad(padp, bb, name, d, 40, (62, 86)); cb.add(bb, low(chord(name)[0]), d, 36); harp_arp(harp, bb, name, d, 38, step=1.0)
        harm(b, JESUS_HARM, [k + 1], chordfn)
        if k >= 2: oohs.chord(b, [chord("D")[2], chord("D")[3]], 4, 30)
    return s


# ----------------------------------------------------------------------------------------------- dark_walk
def cue_dark_walk(c):
    """Saul led by the hand, blind: slow and quiet. A solo cello plays the march figure in pieces, gently, broken off
    mid-bar (D-D-F-A ... F-F-G ... E ... D); a soft low drum walks beside it (one step a beat), a thin pad (Dm Gm A Dm)
    and a few harp notes. No snare, no tuba, nothing that stomps."""
    s = Score(c, 56, 4); n = s.bars; total = n * 4
    vc = P(s, "cello (solo)", CELLO, -3, .45, lp=2400, human=.007)
    padp = P(s, "pad", SLOW_STR, -10, .5, lp=2200)
    harp = P(s, "harp", HARP, -9, .5)
    dr = P(s, "soft footsteps", DRUMS, -10, .2, lp=900, human=.006)
    cb = P(s, "basses", CBASS, -15, .3, lp=700)
    frag = [[("D3", 1), ("D3", .5), ("F3", .5), ("A3", 2)], [("F3", 1), ("F3", .5), ("G3", .5), (None, 2)],
            [("E3", 1), (None, 1), ("D3", 2)]]
    hm = ["Dm", "Gm", "Dm"]
    for bar in range(n):
        b = bar * 4; nme = hm[min(bar, len(hm) - 1)]
        play(vc, b, [(note(p) if p else None, d) for p, d in frag[min(bar, 2)]], 46 if bar < n - 1 else 40, legato=.97, vib=True)
        pad(padp, b, "A" if bar == n - 2 else nme, 4, 30, (52, 72)); cb.add(b, low(chord(nme)[0]), 4, 30)
        for q in range(4): dr.add(b + q, LO_CONGA if q % 2 == 0 else MUTE_CONGA, .3, 30 if q % 2 == 0 else 22)
    harp.add(total - 4, "A5", 3, 26); harp.add(total - 2, "D5", 2.5, 24)
    return s


# ----------------------------------------------------------------------------------------------- three_days
def cue_three_days(c):
    """Three days of prayer: very soft harp (one note a beat) and a pad; for the last two bars the flute plays the first
    four notes of the Jesus theme slowly (A-B-D ... E, the PROMISE figure) and holds the E: unresolved, left hanging on Asus
    as Saul prays 'I was wrong, Lord'. No drums."""
    s = Score(c, 66, 4); n = s.bars; total = n * 4
    padp = P(s, "pad", SLOW_STR, -8, .55, lp=2400)
    harp = P(s, "harp", HARP, -7, .5)
    fl = P(s, "flute (prayer)", FLUTE, -8, .5, human=.008)
    vc = P(s, "cello", CELLO, -10, .4, lp=2000)
    cb = P(s, "basses", CBASS, -15, .3, lp=800)
    hm = ["D"] * (n - 1) + ["Asus"]
    pb = total - 8
    for bar, nme in enumerate(hm):
        b = bar * 4; ps = chord(nme)
        pad(padp, b, nme, 4, 34, (54, 78)); cb.add(b, low(ps[0]), 4, 30); harp_arp(harp, b, nme, 4, 34, step=1.0)
        if b < pb: vc.chord(b + .5, [ps[2] - 12], 3.4, 38)
    mel(fl, max(0, pb), promise(), 50, legato=.97, vib=True)
    harp.add(total - 1, "E6", 2.5, 30)
    return s


# ----------------------------------------------------------------------------------------------- ananias
def cue_ananias(c):
    """Ananias is afraid: a nervous comic tiptoe, a wobbling staccato bassoon and a pizzicato walk in D minor (Dm A),
    ticking wood blocks; every time Jesus speaks the Jesus theme answers warmly in D major (flute, strings, harp:
    bars 1-2 under "Ananias, go ..." and bars 3-4 under "Go! I chose him ..."). After Ananias's "Saul?! THE Saul?!" a woodblock and
    bassoon "gulp"; when he says "all right, Lord, I'll go" the tiptoe turns braver and ends on a plain D."""
    s = Score(c, 100, 4); n = s.bars; total = n * 4
    pz = P(s, "pizz walk", PIZZ, -4, .25, human=.004)
    bsn = P(s, "bassoon", BASSOON, -6, .3, lp=2400, bend=True, human=.004)
    wb = P(s, "wood blocks", DRUMS, -9, .2, human=.004)
    fl = P(s, "flute (Jesus)", FLUTE, -5, .45, human=.008)
    padp = P(s, "strings", SLOW_STR, -8, .55, lp=3200)
    harp = P(s, "harp", HARP, -6, .5)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=1000)
    a1 = 0.0
    a2 = float(snap(lbeat(s, c, "sa_19", "start", total * .6) - .5))
    gulp = lbeat(s, c, "sa_18", "end", total * .5) + .2
    ans = {a1: (1, 2), a2: (3, 4)}
    covered = set()
    for b0, (k1, k2) in ans.items():
        mel(fl, b0, jesus([k1, k2]), 58, legato=.97, vib=True)
        def chordfn(bb, name, d):
            pad(padp, bb, name, d, 40, (62, 86)); cb.add(bb, low(chord(name)[0]), d, 36); harp_arp(harp, bb, name, d, 38, step=1.0)
        harm(b0, JESUS_HARM, [k1, k2], chordfn)
        covered |= {b0 + j * 4 for j in range(2)}
    fear = [("D3", .5), (None, .5), ("F3", .5), ("E3", .5), ("D3", 1), (None, 1)]
    for bar in range(n):
        b = bar * 4
        if b in covered: continue
        late = b >= a2 + 8
        nme = "Dm" if (bar % 2 == 0 or late) else "A"
        if late and bar == n - 1: nme = "D"
        ps = chord(nme)
        for q in range(4):
            pz.add(b + q, ps[[0, 2, 1, 2][q]] + (12 if q % 2 else 0), .2, 54); pz.add(b + q + .5, ps[1] + 12, .15, 38)
            wb.add(b + q + .25, HI_WOOD if q % 2 == 0 else LO_WOOD, .15, 30)
        cb.add(b, low(ps[0]), 4, 32)
        if not late and bar < n - 1: play(bsn, b, [(note(p) if p else None, d) for p, d in fear], 46, stacc=True)
        elif late and bar < n - 1: padp.chord(b, ps[1:], 4.2, 36)
        else: pad(padp, b, "D", 4, 42, (64, 84)); fl.add(b, "D5", 4, 62)
    wb.add(gulp, LO_WOOD, .3, 66); wb.add(gulp + .35, HI_WOOD, .2, 52)
    bsn.add(gulp, "D3", .5, 54); bsn.glide(gulp, gulp + .5, 0, -3, 1.0); bsn.bend(gulp + .8, 0)
    return s


# ----------------------------------------------------------------------------------------------- brother
def cue_brother(c):
    """Ananias tiptoes to the house (pizzicato, hushed for the three `knock`s), then the JESUS theme in full on warm
    strings from just before "Brother Saul", with harp and the choir on the last four bars; a bright harp run and celesta on
    the `sparkle_up` when the scales fall; and for Saul's "You call me brother?" the first hint of Saul's march in D major
    (D-D-F#-A-G, soft oud and pizzicato). Ends on a long D."""
    s = Score(c, 90, 4); n = s.bars; total = n * 4
    pz = P(s, "pizz tiptoe", PIZZ, -5, .25, human=.004)
    vln = P(s, "strings (Jesus)", STRINGS, -7, .55, lp=5000, human=.006)
    vc = P(s, "cellos", CELLO, -10, .4, lp=2600)
    padp = P(s, "pad", SLOW_STR, -9, .55, lp=3400)
    harp = P(s, "harp", HARP, -6, .5)
    cel = P(s, "celesta", CELESTA, -12, .6)
    choir = P(s, "choir ah", CHOIR, -11, .6, lp=4400)
    oud = P(s, "oud (hint)", OUD, -7, .3, lp=4000, human=.004)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=1000)
    kb = beat_of(s, c.first("sfx", id="knock"), 6.0); sp = beat_of(s, c.first("sfx", id="sparkle_up"), total * .55)
    plan = me.fill_phrase(n, 8, 8, min_intro=2)
    for bar, k in enumerate(plan):
        b = bar * 4
        if k is None:
            ps = chord("Dm" if bar % 2 == 0 else "A")
            for q in range(4):
                if kb - .6 <= b + q <= kb + 1.8: continue          # hush for the three knocks
                pz.add(b + q, ps[[0, 2, 1, 2][q]] + (12 if q % 2 else 0), .2, 48)
            cb.add(b, low(ps[0]), 4, 30); continue
        mel(vln, b, jesus([k + 1]), 60 if k < 4 else 66, legato=.97, vib=True)
        mel(vc, b, jesus([k + 1]), 38, legato=.98, shift=-12)
        def chordfn(bb, name, d):
            pad(padp, bb, name, d, 42, (64, 88)); cb.add(bb, low(chord(name)[0]), d, 38)
            if k < 4: harp_arp(harp, bb, name, d, 40, step=1.0)
            else: harp_arp(harp, bb, name, d, 44, step=.5)
        harm(b, JESUS_HARM, [k + 1], chordfn)
        if k >= 4: mel(choir, b, jesus([k + 1]), 38, legato=.98)
    run(harp, sp - .1, [note(p) for p in ("D4", "E4", "F#4", "A4", "B4", "D5", "E5", "F#5", "A5", "B5", "D6")], .09, 56, 2.5)
    for j, p_ in enumerate(("A6", "D7", "F#6", "A6")): cel.add(sp + .8 + j * .6, p_, 2.5, 34 - 2 * j)
    hb = lbeat(s, c, "sa_24", "end", total * .8)
    hb = snap(hb) if hb < total - 8 else total - 8
    play(oud, hb, saul([0], major=True), 44, stacc=True)
    for q in range(4): pz.add(hb + q, chord("D")[0 if q % 2 == 0 else 1], .2, 40)
    return s


# ----------------------------------------------------------------------------------------------- baptism
BAPT = {0: [("D5", 1), ("F#5", .5), ("A5", .5), ("F#5", 1), ("E5", 1)],
        1: [("G5", 1), ("B5", .5), ("A5", .5), ("F#5", 1), ("D5", 1)],
        2: [("E5", 1), ("F#5", .5), ("G5", .5), ("F#5", 1), ("E5", 1)],
        3: [("D5", 4)]}
BAPT_HARM = [("D", 4), ("G", 4), ("A", 4), ("D", 4)]


def cue_baptism(c):
    """Fresh and happy: a bright little flute tune over harp arpeggios and pizzicato in D major (D G A D); a glockenspiel
    splash and a harp glissando on the `water_splash`; for the bread (`munch`) a chuckling two-note oud figure with a
    block pair. Original tune, 4 bars."""
    s = Score(c, 110, 4); n = s.bars; total = n * 4
    fl = P(s, "flute", FLUTE, -4, .4, human=.006)
    harp = P(s, "harp", HARP, -5, .45)
    pz = P(s, "pizz", PIZZ, -7, .25)
    padp = P(s, "pad", SLOW_STR, -11, .5, lp=3400)
    gl = P(s, "glock", GLOCK, -14, .5)
    oud = P(s, "oud (chuckle)", OUD, -5, .3, lp=4000, human=.004)
    wb = P(s, "wood blocks", DRUMS, -9, .2, human=.004)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=1000)
    sw = beat_of(s, c.first("sfx", id="water_splash"), 1.5); mb = beat_of(s, c.first("sfx", id="munch"), total * .7)
    for bar in range(n):
        b = bar * 4; nme = BAPT_HARM[min(bar, 3)][0]; ps = chord(nme)
        mel(fl, b, BAPT[min(bar, 3)], 58, legato=.93, vib=True)
        harp_arp(harp, b, nme, 4, 44, step=.5); cb.add(b, low(ps[0]), 4, 36); pad(padp, b, nme, 4, 34, (58, 80))
        for q in range(4): pz.add(b + q, low(ps[0]) + (12 if q % 2 else 0), .25, 52 if q % 2 == 0 else 40)
    run(harp, sw, [note(p) for p in ("D6", "B5", "A5", "F#5", "D5", "A5", "D6")], .07, 52, 1.2)
    for j, p_ in enumerate(("A6", "F#6", "D7", "A6", "D7")): gl.add(sw + .15 + j * .22, p_, 1.2, 46 - 3 * j)
    for j, p_ in enumerate(("A3", "D4", "A3", "D4")): oud.add(mb + j * .25, p_, .2, 66)       # the chuckle
    wb.add(mb, HI_WOOD, .2, 52); wb.add(mb + .5, LO_WOOD, .2, 44)
    return s


# ----------------------------------------------------------------------------------------------- new_saul
def cue_new_saul(c):
    """Saul's march in D MAJOR for the first time (the same tune, F# and B): skipping, on flute and oud with a hand drum
    and a bouncing pizzicato bass; the second time through the strings and a few claps join. The guards' double-take
    (rs 29-30) falls inside the second phrase; ends on D."""
    s = Score(c, 132, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (march)", FLUTE, -4, .4, human=.006)
    oud = P(s, "oud", OUD, -5, .3, lp=4200, human=.004)
    pz = P(s, "pizz bass", PIZZ, -5, .25)
    dr = P(s, "hand drum", DRUMS, -9, .2, lp=3800, human=.004)
    hands = P(s, "claps + tamb", DRUMS, -9, .25, human=.004)
    vln = P(s, "violins", STRINGS, -11, .5, lp=5000)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=1100)
    plan = me.fill_phrase(n, 4, 4, min_intro=0)
    for bar, k in enumerate(plan):
        b = bar * 4; second = bar >= 4
        if k is None:
            pad_ = chord("D")
            for q in range(4): pz.add(b + q, low(pad_[0]) + (12 if q % 2 else 0), .25, 52)
            continue
        play(fl, b, saul([k], major=True, shift=12), 64, legato=.85, swing=.17, accent=4)
        play(oud, b, saul([k], major=True), 56, legato=.8, swing=.17, stacc=True)
        if second: play(vln, b, saul([k], major=True, shift=12), 40, legato=.95, swing=.17)
        def chordfn(bb, name, d):
            ps = chord(name)
            for q in range(int(d)): pz.add(bb + q, low(ps[0]) + (0 if q % 2 == 0 else 7), .25, 56 if q % 2 == 0 else 44)
            cb.add(bb, low(ps[0]), d, 34)
        harm(b, SAUL_HARM_MAJ, [k], chordfn)
        groove(dr, b, "D..tD.k.D..tD.kt", .25, FRAME, .7, swing=.15)
        if second: groove(hands, b, "s...c.s.s...c.s.", .25, HANDS, .8)
    return s


# ----------------------------------------------------------------------------------------------- basket
def cue_basket(c):
    """Night: the guards watch the gate (a stiff pizzicato-and-tuba fragment of the march in minor), then a hushed night
    tiptoe, pizzicato and a muted horn in D minor; a small tuba answer after the `snore`; for the `rope_creak` a slow falling
    bassoon line (D4 ... D3, each step a little creak) over soft pizzicato; the `basket_land` is a soft pluck and the
    harmony turns to a warm D major under Saul's thanks; ends on D."""
    s = Score(c, 84, 4); n = s.bars; total = n * 4
    pz = P(s, "pizz", PIZZ, -5, .25, human=.004)
    horn = P(s, "muted horn", HORN, -9, .3, lp=1800, human=.005)
    tuba = P(s, "tuba", TUBA, -8, .25, lp=1200, bend=True)
    bsn = P(s, "bassoon (descent)", BASSOON, -6, .3, lp=2400, bend=True, human=.004)
    wb = P(s, "wood blocks", DRUMS, -10, .15, human=.004)
    harp = P(s, "harp", HARP, -7, .5)
    padp = P(s, "pad", SLOW_STR, -11, .5, lp=2400)
    cb = P(s, "contrabass", CBASS, -14, .3, lp=900)
    sn_ = c.first("sfx", id="snore"); sn = beat_of(s, sn_, total * .38)
    rc = beat_of(s, c.first("sfx", id="rope_creak"), total * .55); bl = beat_of(s, c.first("sfx", id="basket_land"), total * .8)
    gate = snap(lbeat(s, c, "sa_33", "start", 16.0))
    for bar in range(n):
        b = bar * 4; ps = chord("Dm" if bar % 2 == 0 else "A")
        major = b >= snap(bl) + 0.0
        if major: ps = chord("D")
        if b < gate:                                                # the guards on watch: stiff stomp, minor
            for q in (0, 2):
                if b + q < sn - .5: tuba.add(b + q, "D2" if q == 0 else "A2", .6, 56)
            for q in range(4): pz.add(b + q, ps[[0, 2, 1, 2][q]], .15, 50)
            if bar < 2: play(pz, b, saul([bar], shift=-12), 44, stacc=True)
        else:                                                       # night tiptoe
            for q in range(4):
                if b + q < rc - .5 or b + q > bl:
                    if not (sn - .3 < b + q < sn + 3.5): pz.add(b + q, ps[[0, 2, 1, 2][q]] + (12 if q % 2 else 0), .2, 40 if not major else 46)
            for q in (.5, 2.5): wb.add(b + q, HI_WOOD, .12, 26)
        cb.add(b, low(ps[0]), 4, 30)
        if gate <= b < rc - 2 or major: pad(padp, b, "D" if major else ("Dm" if bar % 2 == 0 else "A"), 4, 32, (54, 76))
        if b >= gate and b < rc - 2: horn.chord(b + .5, [ps[1] - 12, ps[2] - 12], 3.2, 42)
        if major: harp_arp(harp, b, "D", 4, 40, step=1.0)
    # a small tuba answer after the snore
    tb = sn + s.beat(3.0) + 0.2
    if tb < rc - 1: tuba.add(tb, "D2", .6, 52); tuba.glide(tb, tb + .6, 0, -2, 1.0); tuba.bend(tb + .8, 0); tuba.add(tb + 1, "A1", .5, 46)
    # the descent: eight falling steps from rope_creak to basket_land, each with a little creak (bend)
    steps = ["D4", "C4", "Bb3", "A3", "G3", "F3", "E3", "D3"]; span = max(4.0, bl - rc - .2)
    for i, p_ in enumerate(steps):
        t0 = rc + span * i / len(steps); d = span / len(steps)
        bsn.add(t0, p_, d * .95, 50 + 2 * i); bsn.bend(t0 - .02, .5); bsn.glide(t0, t0 + d * .8, .5, -.3, 1.0)
    bsn.bend(bl + .2, 0)
    harp.add(bl, "D4", 2.5, 44); harp.add(bl + .25, "A4", 2.5, 40); harp.add(bl + .5, "D5", 2.5, 40)   # relief
    pz.chord(bl, ["D3", "A3", "D4", "F#4"], .5, 54, strum=.02)
    return s


# ----------------------------------------------------------------------------------------------- barnabas
BARN_HARM = ["D", "A", "Bm", "G", "D", "A", "Bm", "G", "D", "A", "D"]


def cue_barnabas(c):
    """Warm rocking 6/8 (counted in eighths) in D major: oud and harp arpeggios, soft strings and a low flute for
    Barnabas. A worried clarinet in B minor plays a hesitant figure for Peter's fear ("Saul? He's come to arrest us!"); at
    "Welcome, Brother Saul!" the same figure turns major and joyful on flute with a harp run. Ends on D."""
    s = Score(c, 186, 6); n = s.bars; total = n * 6
    oud = P(s, "oud", OUD, -5, .3, lp=4000, human=.005)
    harp = P(s, "harp", HARP, -6, .45)
    padp = P(s, "strings", SLOW_STR, -9, .55, lp=3200)
    cl = P(s, "clarinet (Peter)", CLARINET, -6, .35, human=.008)
    fl = P(s, "flute", FLUTE, -6, .4, human=.008)
    cb = P(s, "contrabass", CBASS, -13, .3, lp=1000)
    dr = P(s, "frame drum", DRUMS, -12, .15, lp=3200, human=.005)
    pk = lbeat(s, c, "sa_37", "start", 12); pe = lbeat(s, c, "sa_37", "end", 18); wl = lbeat(s, c, "sa_39", "start", total * .7)
    WORRY = [("B4", 1.5), ("A4", .5), ("B4", 1), ("D5", 1.5), ("C#5", .5), ("B4", 1.0)]       # 6 beats = one bar of 6/8
    JOY = [("D5", 1.5), ("E5", .5), ("F#5", 1), ("A5", 1.5), ("G5", .5), ("F#5", 1.0)]
    for bar in range(n):
        b = bar * 6; nme = BARN_HARM[min(bar, len(BARN_HARM) - 1)]; ps = chord(nme)
        if bar == n - 1: nme = "D"; ps = chord("D")
        pad(padp, b, nme, 6, 38, (58, 84)); cb.add(b, low(ps[0]), 6, 36)
        for j in range(6): oud.add(b + j, ps[[0, 1, 2, 3, 2, 1][j]] + 12 * (j in (3, 4)), 1.0, 48 if j in (0, 3) else 38)
        harp_arp(harp, b, nme, 6, 36, step=1.0)
        dr.add(b, LO_CONGA, .5, 44); dr.add(b + 3, MUTE_CONGA, .4, 36)
    for bar in range(n - 1):
        b = bar * 6
        if pk - 1 <= b <= pe - 3 and wl > b + 6: play(cl, snap(b, 6), [(note(p), d) for p, d in WORRY], 54, legato=.95, vib=True)
        elif b >= snap(wl, 6) - 1 and b <= (n - 2) * 6: play(fl, b, [(note(p), d) for p, d in JOY], 60, legato=.95, vib=True)
    wj = snap(wl, 6)
    run(harp, wj, [note(p) for p in ("D5", "E5", "F#5", "A5", "B5", "D6")], .12, 54, 2.0)
    fl.add((n - 1) * 6, "D5", 6, 64); harp.add((n - 1) * 6, "D6", 3, 44)
    return s


# ----------------------------------------------------------------------------------------------- finale
def cue_finale(c):
    """Saul's march in D major with the whole band and the children's choir: four bars of the tune on flute, oud,
    pizzicato bass and hand drum (the "turned around" tune, skipping), then four bars where the JESUS theme's bars 1-4 sing
    above it on violins and choir over the JOINT harmony (D A7 Bm-A G-D), claps and tambourine joining; a final bright held
    D chord with a harp roll, glockenspiel and a soft timpani on the closing line (and the last `sparkle_up`)."""
    s = Score(c, 112, 4); n = s.bars; total = n * 4
    fl = P(s, "flute (march)", FLUTE, -3, .45, human=.006)
    vln = P(s, "violins (Jesus)", STRINGS, -9, .5, lp=5500, human=.006)
    oud = P(s, "oud", OUD, -5, .3, lp=4200, human=.004)
    choir = P(s, "children ah", CHOIR, -9, .6, lp=4500)
    padp = P(s, "strings", SLOW_STR, -9, .5, lp=3500)
    harp = P(s, "harp", HARP, -7, .45)
    pz = P(s, "pizz bass", PIZZ, -6, .25)
    cb = P(s, "contrabass", CBASS, -13, .3, lp=1100)
    dr = P(s, "hand drum", DRUMS, -9, .2, lp=3500, human=.004)
    hands = P(s, "claps+tamb", DRUMS, -6, .25, human=.004)
    gl = P(s, "glock", GLOCK, -14, .5)
    tim = P(s, "timpani", TIMPANI, -13, .4, lp=1000)
    plan = me.fill_phrase(n - 1, 8, 4, min_intro=0)
    for bar, k in enumerate(plan):
        b = bar * 4
        if k is None:
            pad(padp, b, "D", 4, 44, (60, 90)); harp_arp(harp, b, "D", 4, 44); cb.add(b, "D2", 4, 44); continue
        joint = k >= 4; j = k - 4 if joint else k
        play(fl, b, saul([j], major=True, shift=12), 70, legato=.9, swing=.12, accent=4)
        play(oud, b, saul([j], major=True), 56, legato=.8, swing=.12, stacc=True)
        if joint:
            mel(vln, b, jesus([j + 1], shift=12), 56, legato=.97, vib=True)
            mel(choir, b, jesus([j + 1]), 46, legato=.98)
        def chordfn(bb, name, d):
            ps = chord(name); pad(padp, bb, name, d, 46 if joint else 40, (74, 100)); cb.add(bb, low(ps[0]), d, 44)
            for q in range(int(d)): pz.add(bb + q, low(ps[0]) + (0 if q % 2 == 0 else 7), .3, 58 if q % 2 == 0 else 46)
            if not joint: harp_arp(harp, bb, name, d, 40, step=1.0)
        harm(b, JOINT, [j + 1], chordfn) if joint else harm(b, SAUL_HARM_MAJ, [j], chordfn)
        groove(dr, b, "D..tD.k.D..tD.kt", .25, FRAME, .7, swing=.1)
        if joint or k >= 2: groove(hands, b, "s...c.s.s...c.s.", .25, HANDS, .8)
    fe = total - 4; ps = chord("D")
    fl.add(fe, "D5", 4, 76); vln.chord(fe, [note("A5"), note("D6"), note("F#6")], 4, 48, strum=.04)
    padp.chord(fe, ps[1:] + [ps[3] + 12], 4, 58); choir.chord(fe, [ps[2], ps[3], ps[3] + 12], 4, 50)
    run(harp, fe, [ps[0], ps[1], ps[2], ps[3], ps[1] + 24, ps[2] + 24, ps[3] + 24], .1, 56, 4)
    for i, p_ in enumerate(["D6", "F#6", "A6", "D7"]): gl.add(fe + .25 + i * .3, p_, 3, 44)
    tim.add(fe, "D2", 3, 50); cb.add(fe, "D2", 4, 50); oud.chord(fe, ["D3", "A3", "D4", "F#4"], 3, 60, strum=.03)
    return s

# =============================================================================================== loop sections
VAMP = {"angry_march": ("Dm", "march"), "road": ("Dm", "march"), "light": ("D", "choir"), "dark_walk": ("Dm", "hush"),
        "three_days": ("Asus", "hush"), "ananias": ("D", "tiptoe"), "brother": ("D", "choir"), "baptism": ("D", "bed"),
        "new_saul": ("D", "march"), "basket": ("D", "hush"), "barnabas": ("D", "bed"), "finale": ("D", "choir")}


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

MUSIC = {"angry_march": cue_angry_march, "road": cue_road, "light": cue_light, "dark_walk": cue_dark_walk,
         "three_days": cue_three_days, "ananias": cue_ananias, "brother": cue_brother, "baptism": cue_baptism,
         "new_saul": cue_new_saul, "basket": cue_basket, "barnabas": cue_barnabas, "finale": cue_finale}
METER = {"barnabas": "6/8"}
KEYS = {"angry_march": "D minor", "road": "D minor", "light": "D add9 -> D major", "dark_walk": "D minor",
        "three_days": "D major -> Asus", "ananias": "D minor / A -> D major", "brother": "D minor -> D major",
        "baptism": "D major", "new_saul": "D major", "basket": "D minor -> D major", "barnabas": "D major",
        "finale": "D major"}
CUE_NOTES = {
    "angry_march": "SAUL'S MARCH in D minor (D-D-F-A-G / F-F-G-A / Bb-Bb-A-G-F / E-E-D): stern oud figure doubled by cellos, tuba oom-pah, bass drum + stiff snare with a roll at each phrase end. Comic-stern.",
    "road": "The march at a hot trudge: solo cello tune, soft tuba, puffing bassoon on the off-beats (sighs down under the short guard's 'my feet are flat'), a high tremolo violin 'heat shimmer' swelling every bar.",
    "light": "The march breaks off: shimmering high tremolo D add9 swelling to `light_whoosh`, harp glissando, celesta, choir 'ah'; no drums, no low rumble. Then the JESUS theme (bars 1-4) slow on flute over strings and harp under Jesus' words.",
    "dark_walk": "Blind and led by the hand: solo cello plays the march figure in pieces, broken off; soft low footsteps on a drum, a thin pad (Dm Gm A Dm).",
    "three_days": "Very soft harp (a note a beat) and pad; flute plays the JESUS theme's first four notes A-B-D ... E and holds the E: unresolved on Asus.",
    "ananias": "Nervous comic tiptoe (pizz, wobbling staccato bassoon, wood blocks) in D minor / A; the JESUS theme answers warmly in D major whenever Jesus speaks (bars 1-2, then 3-4); a woodblock + bassoon gulp after 'THE Saul?!'; braver and plain D at the end.",
    "brother": "Hushed pizz tiptoe (silent for the three knocks), then the JESUS theme in full (8 bars) on warm strings + cellos from just before 'Brother Saul', harp, choir on bars 5-8; bright harp run + celesta on `sparkle_up`; the first soft hint of Saul's march in D major (oud + pizz) for 'You call me brother?'.",
    "baptism": "Fresh and happy: original 4-bar flute tune over harp arpeggios and pizz (D G A D); glock splash + harp run on `water_splash`; chuckling oud figure and a block pair on `munch`.",
    "new_saul": "Saul's march in D MAJOR for the first time (F#, B): skipping on flute and oud, hand drum, bouncing pizz bass; violins and claps join the second time.",
    "basket": "Guards on watch: stiff pizz + tuba fragment of the march in minor; hushed night tiptoe with muted horn; a small tuba answer after the `snore`; a slow falling bassoon line (D4 ... D3) across `rope_creak`; soft pluck + warm D major on `basket_land`.",
    "barnabas": "Warm rocking 6/8 in D (oud + harp arpeggios, strings): worried clarinet in B minor for Peter, the same figure joyful on flute at the welcome, harp run.",
    "finale": "Saul's march in D major with the whole band (flute, oud, pizz, hand drum), then the JESUS theme bars 1-4 sing above it on violins + choir over the JOINT harmony, claps; bright held D chord, harp roll, glock, soft timpani.",
}


# =============================================================================================== sfx
noise = lambda n: me.noise(n)
R = lambda: me.RNG
place_ = lambda dst, src, at: me.place(dst, src, at)
LOOP_SECS = {}                 # no loops: every effect is a one-shot sized to its scene (CONTRACT 7)
LOOP_STOP_CUE = {}


def note_hz(p): return 440 * 2 ** ((note(p) - 69) / 12)


def bell(secs, *a, **kw):
    y = me.partials(secs, *a, **kw); k = min(len(y), int(.04 * SR)); y[-k:] *= np.linspace(1, 0, k); return y


def chirp(f0, f1, secs, amp=1.0, curve=1.0):
    """One soft sine sweep f0 -> f1 with a sin^2 envelope (a drop's plink, a whistle)."""
    m = int(secs * SR); t = np.arange(m) / SR; u = t / secs
    f = f0 + (f1 - f0) * u ** curve
    return amp * np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * u) ** 2


def thud(f_body=90, amp=1.0, secs=.45, knock=(160, 1100)):
    """A soft round thud: a falling low sine body plus a mid knock (the part a phone speaker plays)."""
    k = int(secs * SR); tk = np.arange(k) / SR
    th = np.sin(2 * np.pi * (f_body + 60 * np.exp(-tk / .025)) * tk) * np.exp(-tk / .1)
    th += me.bp(noise(k), *knock) * np.exp(-tk / .04) * .8
    return th * amp * np.minimum(1, tk / .002)


def boot(f_body, knock, amp, crunch=.5):
    """One boot step on a dry road: a resonant mid knock (phone-audible), a low body and a dusty crunch."""
    k = int(.2 * SR); tk = np.arange(k) / SR
    x = me.resonator(np.r_[1.0, np.zeros(k - 1)] + me.bp(noise(k), 200, 1500) * np.exp(-tk / .012) * .5, knock, 100)
    x = x / (np.max(np.abs(x)) + 1e-9) * .6
    x += np.sin(2 * np.pi * f_body * tk) * np.exp(-tk / .05) * .5
    x += me.bp(noise(k), 1200, 4500) * np.exp(-tk / .04) * crunch
    return x * amp


def sfx_march_steps(ctx):
    """Soldiers stomping on a dry road, 4.6 s: Saul and two guards, three pairs of boots a little out of step (2.0 steps a
    second, 240 / 330 / 400 Hz knocks, a firm low body, dust crunch), Saul's the loudest; the steps fade into the distance
    from 2.2 s."""
    secs = 4.6; n = int(secs * SR); y = np.zeros(n)
    for start, fb, kn, a in ((0.0, 95, 240, 1.0), (.09, 120, 330, .7), (.19, 130, 400, .65)):
        q = start; i = 0
        while q < secs - .25:
            fade = 1.0 if q < 2.2 else np.exp(-(q - 2.2) / .9)
            place_(y, boot(fb, kn * R().uniform(.96, 1.04), a * fade * (1 if i % 2 == 0 else .85)), q)
            q += .5 * R().uniform(.97, 1.03); i += 1
    return me.fit(me.room(y, "room", .15), secs, fade_out=.5)


def sfx_light_whoosh(ctx):
    """The light on the road, 1.5 s: a warm rising shimmer, not a bang: a D-major chord of soft sines (D5 F#5 A5 D6) sliding
    up a third while it swells with a slow tremolo, a rising band of air (300 -> 3000 Hz), a tiny bell at the top; the
    envelope grows for 1.0 s and glows out over 0.5 s. No low body, no attack, nothing sudden."""
    secs = 1.5; n = int(secs * SR); t = np.arange(n) / SR
    env = np.sin(np.pi / 2 * np.clip(t / 1.05, 0, 1)) ** 2.0 * np.clip((secs - t) / .5, 0, 1)
    glide = 1 + .26 * np.clip(t / 1.1, 0, 1)                                      # a major third up
    y = np.zeros(n)
    for p_, a in (("D5", 1.0), ("F#5", .8), ("A5", .7), ("D6", .5)):
        ph = np.cumsum(note_hz(p_) * glide) / SR
        y += a * np.sin(2 * np.pi * ph) * (.85 + .15 * np.sin(2 * np.pi * 7 * t))
    air = me.bp(noise(n), 300, 3200) * (.5 + .5 * np.clip(t / 1.1, 0, 1)) * .35
    sweep = np.sin(2 * np.pi * np.cumsum(300 + 2700 * np.clip(t / 1.1, 0, 1) ** 2) / SR) * .08
    y = (y * .25 + air + sweep) * env
    place_(y, bell(.8, note_hz("A6"), [1, 2.0, 3.0], [1, .2, .08], [.5, .3, .15], strike=.06) * .25, 1.0)
    return me.fit(me.room(y, "hall", .3), secs, fade_in=.05, fade_out=.45)


def sfx_sit_thud(ctx):
    """A soft comic bump, 0.4 s: Saul sits down in the dust: a round low thud (110 Hz falling) with a mid 'oof' knock and a
    puff of dust; no sharp attack."""
    secs = .4; n = int(secs * SR); y = np.zeros(n); tk = np.arange(n) / SR
    y += thud(110, 1.0, secs, (180, 900)) * .8
    y += me.bp(noise(n), 700, 3000) * np.exp(-tk / .06) * np.minimum(1, tk / .01) * .25
    return me.fit(me.room(y, "room", .15), secs, fade_in=.003, fade_out=.1)


def sfx_appear_chime(ctx):
    """A warm shimmer for the angel's light, as in risen: four soft bells D6 F#6 A6 D7 rising 60 ms apart, a soft A5 hum
    under them, a faint high air shimmer; 1.5 s, fading."""
    secs = 1.5; n = int(secs * SR); y = np.zeros(n); t = np.arange(n) / SR
    for i, p_ in enumerate(("D6", "F#6", "A6", "D7")):
        place_(y, bell(1.4, note_hz(p_), [1, 2.0, 3.0, 4.2], [1, .25, .12, .05], [.9, .45, .3, .15], strike=.1) * (1 - .12 * i), i * .06)
    y += np.sin(2 * np.pi * note_hz("A5") * t) * np.sin(np.pi * np.clip(t / 1.3, 0, 1)) * .12
    y += me.bp(noise(n), 5000, 9000) * (.5 + .5 * me.smooth_rand(n, 10)) * np.sin(np.pi * np.clip(t / 1.4, 0, 1)) * .02
    return me.fit(me.room(y, "hall", .35), secs, fade_out=.5)


def tok(f, amp, secs=.09, body=160):
    """One wooden knock: a damped resonant 'tok' (f Hz) with a low body and a short click."""
    k = int(secs * SR); tk = np.arange(k) / SR
    x = np.sin(2 * np.pi * f * tk) * np.exp(-tk / .018) + np.sin(2 * np.pi * body * tk) * np.exp(-tk / .03) * .6
    x += me.bp(noise(k), 1500, 5000) * np.exp(-tk / .004) * .25
    return x * amp * np.minimum(1, tk / .001)


def sfx_knock(ctx):
    """Three timid knocks on a wooden door, 0.8 s: tok ... tok ... tok, spaced 0, 0.28 and 0.6 s (hesitating), each a
    little softer and lower than the one before; a small room."""
    secs = .8; n = int(secs * SR); y = np.zeros(n)
    for at, f, a in ((0.0, 520, 1.0), (.28, 490, .8), (.6, 460, .65)): place_(y, tok(f * R().uniform(.98, 1.02), a), at)
    return me.fit(me.room(y, "room", .2), secs, fade_out=.15)


def sfx_sparkle_up(ctx):
    """Joy: a quick rising run of nine bell pings (D6 ... A7, 70 ms apart) over a rising soft air shimmer; 1.2 s."""
    secs = 1.2; n = int(secs * SR); y = np.zeros(n); t = np.arange(n) / SR
    for i, p_ in enumerate(("D6", "E6", "F#6", "A6", "B6", "D7", "E7", "F#7", "A7")):
        place_(y, bell(.7, note_hz(p_), [1, 2.0, 3.0], [1, .2, .08], [.35, .2, .1], strike=.08) * (.6 + .05 * i), i * .07)
    y += me.bp(noise(n), 4000, 10000) * np.clip(t / .7, 0, 1) * np.clip((secs - t) / .4, 0, 1) * .025
    return me.fit(me.room(y, "hall", .3), secs, fade_out=.35)


def sfx_water_splash(ctx):
    """A gentle pour and splash, 0.8 s: a soft stream of water (band noise 800-4000 Hz, bubbling amplitude) for 0.45 s, a
    small splash at 0.35 s (500-5000 Hz, 0.25 s decay) and five upward plinks (drops, 350 -> 900 Hz)."""
    secs = .8; n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    pour = me.bp(noise(n), 800, 4000) * (.5 + .5 * me.smooth_rand(n, 38)) * np.clip(t / .05, 0, 1) * np.clip((.5 - t) / .15, 0, 1) * .6
    y += pour
    k = int(.3 * SR); tk = np.arange(k) / SR
    place_(y, me.bp(noise(k), 500, 5000) * np.exp(-tk / .08) * np.minimum(1, tk / .01) * .8, .35)
    for j in range(5):
        f = R().uniform(350, 600); place_(y, chirp(f, f * 1.6, .07, R().uniform(.25, .5)), .1 + j * .11 + R().uniform(0, .04))
    return me.fit(me.room(y, "room", .2), secs, fade_out=.2)


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


def sfx_snore(ctx):
    """One comic snore and a whistle, 2.6 s: a rattling breath in (0.9 s: a 36 -> 48 Hz flutter of pulses through 330 and
    1100 Hz resonances, swelling), a beat of silence, then the breath out as a soft whistle (0.7 s, 1900 -> 1450 Hz with a
    little vibrato) over a puff of air; round and comic, never harsh."""
    secs = 2.6; n = int(secs * SR); y = np.zeros(n)
    m = int(.95 * SR); tt = np.arange(m) / SR; rate = np.interp(tt, [0, .95], [36, 50])
    ph = np.cumsum(rate) / SR; pulses = np.zeros(m); idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
    pulses[idx] = R().uniform(.7, 1.0, len(idx))
    x = me.resonator(pulses, 330, 120) + .6 * me.resonator(pulses, 1100, 300)
    x += me.bp(noise(m), 200, 1500) * .15
    env = np.sin(np.pi * np.clip(tt / .95, 0, 1)) ** 1.2
    place_(y, x / (np.max(np.abs(x)) + 1e-9) * env, .05)
    w = int(.75 * SR); tw = np.arange(w) / SR; u = tw / .75
    f = 1900 - 450 * u + 25 * np.sin(2 * np.pi * 6 * tw)
    wh = np.sin(2 * np.pi * np.cumsum(f) / SR) * np.sin(np.pi * u) ** 1.5 * .28
    wh += me.bp(noise(w), 1500, 4500) * np.sin(np.pi * u) * .06
    place_(y, wh, 1.25)
    return me.fit(me.room(y, "room", .15), secs, fade_out=.25)


def sfx_rope_creak(ctx):
    """A basket on a rope, 5.6 s: four slow creaks (0.7 s each, 1.3 s apart, a stick-slip pulse train at 14 -> 22 Hz
    through 700-1500 Hz resonances with a small pitch slide) and, under them, wicker rustle (soft 2-7 kHz crackle that
    follows the creaks) and a faint rope groan (120 Hz); soft, slow and even."""
    secs = 5.6; n = int(secs * SR); y = np.zeros(n)
    for i, at in enumerate((.2, 1.5, 2.8, 4.1)):
        m = int(.75 * SR); tt = np.arange(m) / SR; u = tt / .75
        rate = 14 + 8 * u + R().uniform(-1, 1)
        ph = np.cumsum(rate) / SR; pulses = np.zeros(m); idx = np.nonzero(np.diff(np.floor(ph)) > 0)[0]
        pulses[idx] = R().uniform(.6, 1.0, len(idx))
        fr = R().uniform(750, 950) * 1.1
        x = me.resonator(pulses, fr, 160) + .5 * me.resonator(pulses, fr * 1.7, 260)
        x = x / (np.max(np.abs(x)) + 1e-9) * np.sin(np.pi * u) ** 1.2 * (.8 - .08 * i)
        place_(y, x, at)
        k = int(.7 * SR); tk = np.arange(k) / SR
        cr = me.bp(noise(k), 2000, 7000) * (R().random(k) < .02) * np.sin(np.pi * tk / .7) * .5
        place_(y, cr, at)
        g = np.sin(2 * np.pi * 120 * tt) * np.sin(np.pi * u) * .12; place_(y, g, at)
    return me.fit(me.room(y, "room", .2), secs, fade_in=.1, fade_out=.5)


def sfx_basket_land(ctx):
    """A soft wicker bump, 0.4 s: a round low thud (130 Hz) with a mid knock and a little creak-rustle of wicker; gentle."""
    secs = .4; n = int(secs * SR); tk = np.arange(n) / SR; y = np.zeros(n)
    y += thud(130, 1.0, secs, (220, 1000)) * .7
    y += me.bp(noise(n), 1800, 6000) * np.exp(-tk / .07) * np.minimum(1, tk / .01) * (R().random(n) < .08) * .6
    return me.fit(me.room(y, "room", .15), secs, fade_in=.003, fade_out=.12)


SFX = {"march_steps": sfx_march_steps, "light_whoosh": sfx_light_whoosh, "sit_thud": sfx_sit_thud,
       "appear_chime": sfx_appear_chime, "knock": sfx_knock, "sparkle_up": sfx_sparkle_up,
       "water_splash": sfx_water_splash, "munch": sfx_munch, "snore": sfx_snore, "rope_creak": sfx_rope_creak,
       "basket_land": sfx_basket_land}
SFX_SEED = {}
# recommended playback gain (dB): every effect peaks at -3 dBFS in its file; the gains put each effect 4-10 dB under the
# music's RMS where it plays and at least 3 dB under the music's loudest peak
SFX_GAIN = {"march_steps": -9, "light_whoosh": -7, "sit_thud": -10, "appear_chime": -11, "knock": -12, "sparkle_up": -11,
            "water_splash": -11, "munch": -10, "snore": -9, "rope_creak": -6, "basket_land": -9}
SFX_SHAPE = {}
SFX_NOTES = {
    "march_steps": "three pairs of boots a little out of step (2 steps/s, 240/330/400 Hz knocks, low body, dust), Saul's loudest; fades from 2.2 s; 4.6 s",
    "light_whoosh": "warm rising shimmer: soft D-major sines gliding up a third with a slow tremolo + rising air band, a tiny bell at the top; grows for 1 s, glows out; no attack, no low body; 1.5 s",
    "sit_thud": "soft comic bump: round 110 Hz thud, mid 'oof' knock, puff of dust; 0.4 s",
    "appear_chime": "warm shimmer as in risen: bells D6 F#6 A6 D7 60 ms apart, soft A5 hum, faint air; 1.5 s",
    "knock": "three timid knocks on wood (0, 0.28, 0.6 s), each softer and lower; 0.8 s",
    "sparkle_up": "nine rising bell pings D6 -> A7 over a rising air shimmer; 1.2 s",
    "water_splash": "gentle pour (800-4000 Hz, bubbling), a small splash, five upward drop plinks; 0.8 s",
    "munch": "comic crunchy bite + two smaller chews; 0.6 s",
    "snore": "one comic snore (36 -> 48 Hz flutter through 330 / 1100 Hz resonances) and a soft whistle out (1900 -> 1450 Hz); 2.6 s",
    "rope_creak": "four slow stick-slip creaks (14 -> 22 Hz pulses through 750-950 Hz) + wicker rustle + faint rope groan; 5.6 s",
    "basket_land": "soft wicker bump: round 130 Hz thud + mid knock + a little wicker rustle; 0.4 s",
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
                        "Rerun tools/story/music_saul.py after the timeline is re-timed so the in-cue hits follow.",
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


HIT_ROWS_SFX = {"light_whoosh", "knock", "appear_chime", "water_splash", "munch", "snore", "rope_creak", "basket_land", "sparkle_up"}
HIT_ROWS_FX = {"road_light", "angel_light", "scales_fall", "golden_rays"}


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
