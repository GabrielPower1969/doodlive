#!/usr/bin/env python3
"""Original score and sound effects for "Esther" (story pack #2; docs/esther/CONTRACT.md section 7, MUSIC.md).

Music is composed here as MIDI (mido), one stem per instrument, rendered dry by FluidSynth with macOS's General MIDI
bank (gs_instruments.dls), then mixed in numpy: per-stem gain/EQ, one shared convolution reverb (a synthesised hall
impulse with frequency-dependent decay and early reflections), mono. Timing and velocity are humanised with a seed per
cue, so every rerun gives the same files. Sound effects are synthesised with numpy/scipy (no samples, no downloads);
the voices in `gasp` and `cheer` are source-filter voices with time-varying formants, layered and put in a room.

Every name and time comes from assets/esther/timeline.json, which is read on every run: each `music.cue` and `sfx.id`
must have a composer/synth here (asserted). Cue lengths follow the cue spans plus a 0.6 s crossfade tail (the David &
Goliath convention); each cue's tempo is stretched slightly so that a whole number of bars fills its span exactly and
cadences land on the next cue. Musical hits inside cues (Esther's crowning, Haman's stomps, the climb and bow, the
sceptre touch, the truth flash, the boing and scurry, the closing narration) are placed from the timeline too.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/esther/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated, true peak <= -1 dBTP
  assets/esther/audio/music/cues.json        cue lengths, spans, loudness, crossfade rule
  assets/esther/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/esther/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain
  assets/esther/audio/preview_mix.mp3        full-length rough mix at timeline times; zh voice clips from
                                             assets/esther/audio/voice/zh/<line id>.wav|.mp3 when present,
                                             music ducked under them
  docs/esther/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_esther.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg
"""
import argparse, json, math, os, re, subprocess, tempfile, warnings, zlib
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
from scipy import signal
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ES = f"{ROOT}/assets/esther"
TIMELINE = f"{ES}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{ES}/audio/music", f"{ES}/audio/sfx", f"{ES}/audio/voice/zh"
PREVIEW = f"{ES}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/esther/MUSIC.md"
DLS = "/System/Library/Components/CoreAudio.component/Contents/Resources/gs_instruments.dls"
SR = 44100
XFADE = 0.6            # s, crossfade tail (David & Goliath convention)
MUSIC_LUFS = -20.0     # CONTRACT section 7
SFX_PEAK_DB = -3.0     # CONTRACT section 7
DUCK_DB = -7.0         # preview: music under voice
warnings.filterwarnings("ignore", category=wavfile.WavFileWarning)
RNG = np.random.default_rng(0)
STEM_REPORT = False


def seed(name):
    """Each cue / sfx gets its own stable random stream, so changing one never changes another."""
    global RNG
    RNG = np.random.default_rng(zlib.crc32(name.encode()))


# =============================================================================================== MIDI composition
TPB = 960
N = dict(C=0, D=2, E=4, F=5, G=7, A=9, B=11)


def note(name):  # "F#4" -> 66, "Bb2" -> 46
    if not isinstance(name, str): return int(name)
    return 12 * (int(name[-1]) + 1) + N[name[0]] + (1 if "#" in name else -1 if "b" in name[1:] else 0)


# GM programs (0-based)
HARP, KOTO, NYLON, CELESTA, GLOCK, XYLO, TUBULAR = 46, 107, 24, 8, 9, 13, 14
STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS = 48, 49, 44, 45, 42, 43
CHOIR, OOHS, FLUTE, RECORDER, SHAKU, OBOE, BASSOON, CLARINET, SHANAI = 52, 53, 73, 74, 77, 68, 70, 71, 111
TIMPANI, TAIKO, ORCH_HIT = 47, 116, 55
DRUMS = None
# GM drum keys
BDRUM, CLAP, TAMB, CRASH, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA = 35, 39, 54, 49, 60, 61, 62, 63, 64
HI_WOOD, LO_WOOD, SHAKER, TRIANGLE = 76, 77, 70, 81

CH = {  # chord -> voicing (root position, low) ; [root, fifth, octave, third/top]
    "Dm": ["D3", "A3", "D4", "F4"], "D": ["D3", "A3", "D4", "F#4"], "G": ["G2", "D3", "G3", "B3"],
    "C": ["C3", "G3", "C4", "E4"], "F": ["F2", "C3", "F3", "A3"], "Am": ["A2", "E3", "A3", "C4"],
    "Bb": ["Bb2", "F3", "Bb3", "D4"], "Gm": ["G2", "D3", "G3", "Bb3"], "A": ["A2", "E3", "A3", "C#4"],
    "A7": ["A2", "E3", "G3", "C#4"], "Em": ["E2", "B2", "E3", "G3"], "Eb": ["Eb3", "Bb3", "Eb4", "G4"],
    "Cm": ["C3", "G3", "C4", "Eb4"], "Bm": ["B2", "F#3", "B3", "D4"],
}
def chord(name): return [note(p) for p in CH[name]]


class Part:
    """One instrument = one MIDI stem, rendered on its own so it can get its own gain, EQ and reverb send."""

    def __init__(self, score, name, program, gain_db=0.0, send=0.3, lp=None, hp=None, human=0.008, vel_sd=4.0):
        self.s, self.name, self.program = score, name, program
        self.gain, self.send, self.lp, self.hp, self.human, self.vel_sd = 10 ** (gain_db / 20), send, lp, hp, human, vel_sd
        self.notes, self.ccs = [], []
        self.ch = 9 if program is None else 0

    def add(self, beat, pitch, dur, vel=80, shift=0, human=True):
        if beat < 0 or dur <= 0: return
        p = note(pitch) + shift
        t = self.s.sec(beat) + (RNG.normal(0, self.human) if human else 0.0)
        v = vel + (RNG.normal(0, self.vel_sd) if human else 0.0)
        self.notes.append([max(0.0, t), max(0.0, t) + self.s.sec(dur), p, int(np.clip(round(v), 1, 127))])

    def chord(self, beat, pitches, dur, vel=70, strum=0.0, spread=0):
        for k, p in enumerate(pitches): self.add(beat + k * strum, p, dur, vel - k * spread)

    def cc(self, beat, num, val): self.ccs.append((self.s.sec(max(0, beat)), num, int(np.clip(val, 0, 127))))

    def ramp(self, b0, b1, num, v0, v1, curve=1.0):
        k = max(2, int(self.s.sec(b1 - b0) / 0.06))
        for i in range(k + 1):
            u = i / k; self.cc(b0 + (b1 - b0) * u, num, v0 + (v1 - v0) * u ** curve)

    def vibrato(self, beat, dur, depth=40):
        """Delayed vibrato on a long note via the mod wheel, like a player leaning into it."""
        self.cc(beat, 1, 0)
        onset = beat + min(dur * 0.35, self.s.beat(0.35))
        self.ramp(onset, beat + dur * 0.95, 1, 0, depth, 0.7)
        self.cc(beat + dur, 1, 0)

    def tremolo(self, beat, pitch, dur, vel, rate_hz=10.0):
        """Qanun/harp-style repeated plucks on a long note."""
        step = self.s.beat(1.0 / rate_hz); k = max(1, int(dur / step))
        for i in range(k):
            v = vel - 22 * i / k + (5 if i % 2 == 0 else -5)
            self.add(beat + i * step, pitch, step * 1.6, v)

    def midi(self):
        mid = MidiFile(ticks_per_beat=TPB); meta = MidiTrack(); mid.tracks.append(meta)
        meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(self.s.bpm), time=0))
        end = self.s.tick(self.s.secs + 3.0)
        meta.append(MetaMessage("end_of_track", time=end))
        tr = MidiTrack(); mid.tracks.append(tr)
        ev = []  # (tick, order, msg)
        if self.ch != 9: ev.append((0, 0, Message("program_change", channel=self.ch, program=self.program)))
        for cc, v in ((7, 100), (10, 64), (11, 127), (91, 0), (93, 0), (1, 0)):
            ev.append((0, 1, Message("control_change", channel=self.ch, control=cc, value=v)))
        for t, num, v in self.ccs:
            ev.append((self.s.tick(t), 1, Message("control_change", channel=self.ch, control=num, value=v)))
        by_pitch = {}
        for n in sorted(self.notes, key=lambda n: n[0]): by_pitch.setdefault(n[2], []).append(n)
        for p, ns in by_pitch.items():  # a repeated pitch must release before it re-strikes
            for a, b in zip(ns, ns[1:]):
                if a[1] > b[0] - 0.004: a[1] = max(a[0] + 0.01, b[0] - 0.004)
            for t0, t1, pitch, vel in ns:
                ev.append((self.s.tick(t0), 2, Message("note_on", channel=self.ch, note=pitch, velocity=vel)))
                ev.append((self.s.tick(t1), 0, Message("note_off", channel=self.ch, note=pitch, velocity=0)))
        last = 0
        for tick, _, m in sorted(ev, key=lambda e: (e[0], e[1])):
            tr.append(m.copy(time=tick - last)); last = tick
        tr.append(MetaMessage("end_of_track", time=0))
        return mid

    def render(self):
        if not self.notes: return np.zeros(int((self.s.secs + 3) * SR), np.float32)
        x = render_midi(self.midi())
        if self.hp: x = hp(x, self.hp)
        if self.lp: x = lp(x, self.lp)
        return (x * self.gain).astype(np.float32)


class Score:
    """A cue: tempo stretched so `bars` whole bars fill the span exactly; parts are stems."""

    def __init__(self, c, nominal_bpm, bpb, min_bars=1, max_stretch=0.13):
        self.c, self.bpb, self.span, self.secs = c, bpb, c.span, c.secs
        bars = max(min_bars, round(c.span * nominal_bpm / 60 / bpb))
        # prefer the bar count whose tempo is closest to the nominal one
        cands = [b for b in range(max(min_bars, bars - 1), bars + 2) if abs(b * bpb * 60 / c.span / nominal_bpm - 1) <= max_stretch]
        self.bars = min(cands or [bars], key=lambda b: abs(b * bpb * 60 / c.span - nominal_bpm))
        self.bpm = self.bars * bpb * 60 / c.span
        self.parts = []
        Score.last = self

    def beat(self, sec): return sec * self.bpm / 60
    def sec(self, beat): return beat * 60 / self.bpm
    def tick(self, sec): return int(round(sec * self.bpm / 60 * TPB))
    def at(self, abs_t):
        """Beat (in this cue) of an absolute timeline time, or None if it is outside the cue span."""
        if abs_t is None: return None
        r = abs_t - self.c.t
        return self.beat(r) if -1e-6 <= r <= self.span + 1e-6 else None

    def part(self, *a, **kw):
        p = Part(self, *a, **kw); self.parts.append(p); return p

    def render(self, ir="hall"):
        with ThreadPoolExecutor(max_workers=8) as ex: stems = list(ex.map(lambda p: p.render(), self.parts))
        n = max(len(x) for x in stems); dry = np.zeros(n); bus = np.zeros(n)
        for p, x in zip(self.parts, stems):
            dry[:len(x)] += x; bus[:len(x)] += x * p.send
            if STEM_REPORT: print(f"    stem {p.name:18s} rms {20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9):6.1f} dB")
        wet = signal.fftconvolve(bus, IRS[ir]())[:n]
        return (dry + wet).astype(np.float32)


def mel(p, b0, notes, vel=80, legato=0.94, vib=False, shift=0, trem_rate=10.0):
    """Monophonic line. Items (pitch, beats); pitch None = rest. Suffix '.' staccato, '*' qanun tremolo;
    'A4^Bb4' = A4 with a grace note Bb4 just before it."""
    b = b0
    for pitch, dur in notes:
        if pitch is None: b += dur; continue
        stacc, trem = pitch.endswith("."), pitch.endswith("*")
        core = pitch.rstrip(".*"); grace = None
        if "^" in core: core, grace = core.split("^")
        v = vel + RNG.normal(0, 3)
        if grace: p.add(b - 0.11, grace, 0.13, v - 12, shift)
        if trem: p.tremolo(b, note(core) + shift, dur, v, trem_rate)
        else: p.add(b, core, dur * (0.42 if stacc else legato), v, shift)
        if vib and p.s.sec(dur) >= 0.55 and not stacc: p.vibrato(b, dur)
        b += dur
    return b


def groove(p, b0, pat, step, kit, scale=1.0, until=None, swing=0.0):
    for i, ch in enumerate(pat):
        if ch not in kit: continue
        b = b0 + i * step + (swing * step if i % 2 else 0)
        if until is not None and b >= until - 1e-6: break
        key, v = kit[ch]; p.add(b, key, step * 0.9, v * scale)


def fill_phrase(n, L, unit, min_intro=0):
    """Bar plan for n bars of an L-bar phrase: None = intro bar, else phrase bar index. The cue always ends on the
    phrase's last bar, and the phrase starts on a `unit` boundary (so it never starts mid-sentence)."""
    for intro in range(min(min_intro, n - 1), n):
        play = n - intro
        if play > 0 and play % unit == 0: break
    return [None] * intro + [(k - play) % L for k in range(play)]


# ----------------------------------------------------------------------------------------------- cue context
class Ctx:
    def __init__(self, tl, name, t, span, secs, last):
        self.tl, self.name, self.t, self.span, self.secs, self.last = tl, name, t, span, secs, last

    def first(self, kind, **match):
        """Absolute time of the first `kind` event (sfx / fx / acting / lines) inside this cue that matches."""
        for e in sorted(self.tl.get(kind, []), key=lambda e: e["t"]):
            if self.t - 1e-6 <= e["t"] <= self.t + self.span + 1e-6 and all(e.get(k) == v for k, v in match.items()):
                return e["t"]
        return None

    def all(self, kind, **match):
        return [e["t"] for e in self.tl.get(kind, []) if self.t - 1e-6 <= e["t"] <= self.t + self.span + 1e-6
                and all(e.get(k) == v for k, v in match.items())]


# ----------------------------------------------------------------------------------------------- palace_theme
PAL_HARM = ["Dm", "G", "Dm", "C", "Dm", "G", "C", "Dm"]
PAL_MEL = [
    [("D5", 1), ("A4", 1), ("F4", .5), ("G4", .5)],
    [("B4", 1.5), ("A4", .5), ("G4", 1)],
    [("A4", 1), ("F4", .5), ("E4", .5), ("D4", 1)],
    [("E4", .5), ("F4", .5), ("G4*", 2)],
    [("D5", 1), ("A4", 1), ("C5", .5), ("B4", .5)],
    [("D5", 1.5), ("B4", .5), ("G4", 1)],
    [("G4", .5), ("C5", .5), ("E5", 1), ("D5", 1)],
    [("D5*", 2.6)],
]
PAL_COUNTER = {"Dm": "F5", "G": "D5", "C": "E5"}


def cue_palace(c):
    """D Dorian, 3/4. Qanun (koto + harp in octaves, tremolo on long notes) over harp arpeggios, frame drum,
    low strings and a whisper of choir. A flute counter-line enters when Esther is crowned (sparkle)."""
    s = Score(c, 96, 3)
    seq = fill_phrase(s.bars, 8, 4, min_intro=1)
    harp = s.part("harp arps", HARP, -3, .38, human=.007)
    qk = s.part("qanun koto", KOTO, -1, .32, human=.005)
    qh = s.part("qanun harp 8vb", HARP, -6, .32, human=.009)
    pad = s.part("low strings", SLOW_STR, -1, .45, lp=4500)
    cb = s.part("contrabass", CBASS, -10, .3)
    choir = s.part("choir", CHOIR, -18, .55, lp=5000)
    fl = s.part("flute", FLUTE, -4, .48)
    cel = s.part("celesta", CELESTA, -7, .55)
    dr = s.part("frame drum", DRUMS, -9, .22, lp=3200, human=.005)
    kit = {"D": (LO_CONGA, 88), "t": (MUTE_CONGA, 50), "k": (OPEN_CONGA, 32), "s": (TAMB, 26)}
    bright = s.at(c.first("sfx", id="sparkle")) or s.beat(c.span * 0.55)
    for bar, k in enumerate(seq):
        b = bar * 3; ch = "Dm" if k is None else PAL_HARM[k]; ps = chord(ch); final = bar == s.bars - 1
        for i, idx in enumerate([0, 1, 2, 3, 2, 1] if not final else [0, 1, 2, 3]):
            harp.add(b + i * .5, ps[idx], 1.4, (70 if i == 0 else 56) - (8 if k is None else 0))
        if final: harp.chord(b + 2, [ps[0] + 12, ps[1] + 12, ps[3] + 12], 2.5, 54, strum=.06)
        if bar % 2 == 0 or k is None or final:
            dur = 3 if final or (bar + 1 < s.bars and seq[bar + 1] is not None and PAL_HARM[seq[bar + 1]] != ch) else 6
            dur = min(dur, s.bars * 3 - b + 1.5)
            pad.chord(b, [ps[0], ps[1], ps[3]], dur, 52, strum=.03); pad.ramp(b, b + dur, 11, 70, 110 if not final else 85)
            choir.chord(b, [ps[1], ps[3]], dur, 42)
        cb.add(b, ps[0] - 12, 3, 62)
        if k is not None:
            mel(qk, b, PAL_MEL[k], 84); mel(qh, b, PAL_MEL[k], 70, shift=-12)
            if b >= bright - 1.5 and not final:
                fl.add(b, PAL_COUNTER[ch], 2.7, 50); fl.vibrato(b, 2.7, 35)
        if k is None: groove(dr, b, "D...k.", .5, kit, 0.8)
        elif final: groove(dr, b, "D.t...", .5, kit)
        else: groove(dr, b, "D.tkt." if bar % 4 != 3 else "D.tktk", .5, kit)
        if k is not None and bar % 2 == 1: dr.add(b + 2, TAMB, .2, 24)
    if bright < s.bars * 3:
        for i, p in enumerate(["A5", "D6", "F6", "A6"]): cel.add(bright + i * .17, p, 2, 58 - i * 4)
    return s.render()


# ----------------------------------------------------------------------------------------------- haman_theme
HAM_MEL = [
    [("D3.", .5), (None, .5), ("A2.", .5), (None, .5), ("Bb2", .25), ("A2", .25), ("G#2", .25), ("A2", .25), ("D3.", .5), (None, .5)],
    [("F3", .75), ("E3", .25), ("F3.", .5), ("G3.", .5), ("A3", 1), (None, .5), ("C#3.", .5)],
    [("D3.", .5), (None, .5), ("A2.", .5), (None, .5), ("Bb2", .25), ("A2", .25), ("G#2", .25), ("A2", .25), ("F3.", .5), (None, .5)],
    [("E3.", .5), ("C#3.", .5), ("A2.", .5), (None, .5), ("D3.", .25), ("D3.", .25), (None, .5), ("D2", 1)],
    [("A4.", .5), (None, .5), ("Bb4", .25), ("A4", .25), ("G#4", .25), ("A4", .25), ("E5", 1), (None, 1)],
    [("C#5.", .5), ("D5.", .5), ("E5.", .5), (None, .5), ("G4", 1), (None, 1)],
    [("Bb4.", .5), ("A4.", .5), ("G4.", .5), ("F4.", .5), ("E4.", .5), ("F4", .25), ("E4", .25), ("D4", 1)],
    [("C#4.", .5), ("E4.", .5), ("A4.", .5), (None, .5), ("D4.", .5), (None, 1.5)],
]
HAM_HARM = [["Dm"], ["Dm"], ["Dm"], ["A7", "Dm"], ["Dm"], ["A7"], ["Gm"], ["A7", "Dm"]]


def cue_haman(c):
    """Comic villain, D minor, staccato. Bassoon struts the motif (with a cheeky turn), clarinet answers;
    pizzicato oom-pah, tiptoe wood blocks; Haman's stomps are caught with timpani + pizz."""
    s = Score(c, 116, 4)
    seq = fill_phrase(s.bars, 8, 2)
    bsn = s.part("bassoon", BASSOON, 0, .22, human=.006)
    cl = s.part("clarinet", CLARINET, -1, .26, human=.006)
    pz = s.part("pizzicato", PIZZ, -4, .25, human=.006)
    xy = s.part("xylophone", XYLO, -5, .3)
    timp = s.part("timpani", TIMPANI, -6, .25)
    dr = s.part("wood blocks", DRUMS, -6, .15, human=.004)
    for bar, k in enumerate(seq):
        b = bar * 4; harm = HAM_HARM[k] if k is not None else ["Dm"]
        for half in range(2):
            ps = chord(harm[min(half, len(harm) - 1)]); hb = b + half * 2
            pz.add(hb, ps[0] - 12 if half == 0 else ps[1] - 12, .4, 84 if half == 0 else 72)
            pz.chord(hb + 1, [ps[1], ps[2], ps[3]], .3, 56)
        groove(dr, b, ".t.t.t.t" if (k is None or k < 4) else "w.t.w.t.", .5,
               {"t": (HI_WOOD, 40), "w": (LO_WOOD, 46)})
        if k in (0, 4): dr.add(b, BDRUM, .5, 70)
        if k is None:
            mel(bsn, b + 2, [("D2.", .5), (None, .5), ("D2", 1)], 76)
            continue
        if k < 4: mel(bsn, b, HAM_MEL[k], 92)
        else:
            mel(cl, b, HAM_MEL[k], 88)
            ps = chord(harm[-1])
            bsn.add(b + 1.5, ps[1] - 12, .22, 62); bsn.add(b + 3.5, ps[0] - 12, .22, 62)
        if k == 1: xy.add(b + 2, "A5", .5, 80); timp.add(b + 2, "A2", .6, 60)
        if k == 5: xy.add(b + 1, "E6", .4, 64)
    for st in c.all("sfx", id="stomp"):
        bt = s.at(st)
        if bt is not None: timp.add(bt, "D2", .6, 96); pz.add(bt, "D2", .3, 100)
    return s.render()


# ----------------------------------------------------------------------------------------------- tension (Hijaz)
HIJAZ_UP = {"D": ["D4", "F#4", "A4"], "Eb": ["Eb4", "G4", "Bb4"], "Gm": ["D4", "G4", "Bb4"], "Cm": ["C4", "Eb4", "G4"]}
TEN_HARM = ["D", "Eb", "D", "D", "Gm", "D", "Cm", "Eb"]
TEN_MEL = [
    [(None, 2), ("A4^Bb4", 1), ("G4", .5), ("F#4", .5)],
    [("Eb4", 2), ("D4", 2)],
    [(None, 1), ("D4", .5), ("Eb4", .5), ("F#4", 1), ("G4", 1)],
    [("A4^Bb4", 3), (None, 1)],
    [("Bb4", .5), ("A4", .5), ("G4", .5), ("F#4", .5), ("G4", 1), ("Eb4", 1)],
    [("D4", 3), (None, 1)],
    [(None, 2), ("C5", 1), ("Bb4", .5), ("A4", .5)],
    [("A4", 2), ("G4", .5), ("F#4", .5), ("Eb4", .5), ("F#4", .5)],
]
DARBUKA = {"D": (LO_CONGA, 96), "T": (HI_BONGO, 84), "t": (LO_BONGO, 62), "k": (HI_BONGO, 40)}


def cue_tension(c):
    """D Phrygian dominant (Hijaz), maqsum on darbuka, low string drone, a ney-like reed lead (shakuhachi + oboe)."""
    s = Score(c, 92, 4)
    seq = fill_phrase(s.bars, 8, 2)
    ney = s.part("ney (shakuhachi)", SHAKU, 0, .42, lp=6500, human=.01)
    ob = s.part("oboe double", OBOE, -11, .36, lp=4000, human=.01)
    vc = s.part("cello drone", CELLO, 1, .3)
    cb = s.part("contrabass", CBASS, -6, .25)
    trem = s.part("tremolo strings", TREM_STR, -1, .45, lp=5000)
    drb = s.part("darbuka", DRUMS, -6, .18, human=.004)
    taiko = s.part("taiko", TAIKO, -13, .3, lp=1500)
    for bar, k in enumerate(seq):
        b = bar * 4; ch = TEN_HARM[k] if k is not None else "D"
        if bar % 2 == 0:
            d = min(8, s.bars * 4 - b + 1)
            vc.add(b, "D2", d, 72); vc.add(b, "A2", d, 56); vc.ramp(b, b + d, 11, 85, 120, .8)
            taiko.add(b, "D2", 2, 72)
        cb.add(b, "D2", 4, 66)
        trem.chord(b, HIJAZ_UP[ch], 4, 50); trem.ramp(b, b + 2.2, 11, 45, 105); trem.ramp(b + 2.2, b + 4, 11, 105, 55)
        groove(drb, b, "D.T...T.D...T..." if bar % 2 == 0 else "D.Tk.kT.D.k.TkTk", .25, DARBUKA)
        if k is not None: mel(ney, b, TEN_MEL[k], 84, vib=True); mel(ob, b, TEN_MEL[k], 60)
    return s.render()


# ----------------------------------------------------------------------------------------------- mordecai
MOR_MINOR_HARM = ["Dm", "Bb", "Gm", "A"]
MOR_MINOR = [
    [("D4", 1.5), ("C4", .5), ("A3", 2)],
    [("Bb3", 1), ("A3", .5), ("G3", .5), ("F3", 2)],
    [("G3", 1), ("A3", 1), ("Bb3", 1), ("D4", 1)],
    [("C#4", 1.5), ("D4", .5), ("E4", 2)],
]
MOR_ANSWER = {1: [("F5", .5), ("E5", .5), ("D5", 1)], 3: [("A5", 1), ("G5", .5), ("E5", .5)]}
MOR_HOPE_HARM = [["F"], ["C"], ["Bb", "C"], ["D"]]
MOR_HOPE = [
    [("A4", 1), ("C5", 1), ("F5", 2)],
    [("E5", 1), ("D5", .5), ("C5", .5), ("G4", 2)],
    [("F5", 1), ("D5", 1), ("Bb4", .5), ("C5", .5), ("D5", 1)],
    [("F#5", 4)],
]
MOR_HOPE_CELLO = [[("C4", 2), ("A3", 2)], [("G3", 2), ("E3", 2)], [("D3", 2), ("E3", 2)], [("F#3", 4)]]


def cue_mordecai(c):
    """Tender: cello melody in D minor with flute answers over low strings; from the prayer (soft bell) the flute
    takes over and the harmony climbs F - C - Bb/C to a hopeful D major."""
    s = Score(c, 70, 4, min_bars=2)
    n = s.bars
    hope_t = c.first("sfx", id="soft_bell") or c.first("fx", id="prayer_glow")
    hb = s.at(hope_t)
    hope_bar = int(np.clip(math.floor(hb / 4) if hb is not None else round(n * 0.6), 1, n - 1))
    h = n - hope_bar
    pick = {1: [3], 2: [2, 3], 3: [0, 2, 3], 4: [0, 1, 2, 3]}.get(h) or ([0, 1] * h)[:h - 2] + [2, 3]
    vc = s.part("cello", CELLO, 0, .36, human=.01)
    fl = s.part("flute", FLUTE, -2, .45, human=.01)
    pad = s.part("slow strings", SLOW_STR, -2, .48, lp=5000)
    cb = s.part("contrabass", CBASS, -9, .3)
    harp = s.part("harp", HARP, -7, .42)
    choir = s.part("choir", OOHS, -12, .55, lp=5000)
    for bar in range(n):
        b = bar * 4
        if bar < hope_bar:
            k = bar % 4; ch = MOR_MINOR_HARM[k]; ps = chord(ch)
            mel(vc, b, MOR_MINOR[k], 80, vib=True)
            if k in MOR_ANSWER: mel(fl, b + 2, MOR_ANSWER[k], 56, vib=True)
            pad.chord(b, [ps[1], ps[2], ps[3] + 12 if ps[3] + 12 < 72 else ps[3]], 4, 46); pad.ramp(b, b + 4, 11, 75, 105, .7)
            cb.add(b, ps[0] - 12, 4, 56)
            harp.add(b, ps[0], 2, 52); harp.chord(b + 2, [ps[1], ps[3]], 2, 44, strum=.05)
        else:
            k = pick[bar - hope_bar]; harm = MOR_HOPE_HARM[k]; final = bar == n - 1
            mel(fl, b, MOR_HOPE[k], 74, vib=True); mel(vc, b, MOR_HOPE_CELLO[k], 64, vib=True)
            for half in range(2 if len(harm) == 2 else 1):
                ps = chord(harm[half]); hb_ = b + half * 2; d = 4 / len(harm)
                pad.chord(hb_, [ps[1], ps[2], ps[3]], d + (1 if final else 0), 54); pad.ramp(hb_, hb_ + d, 11, 85, 118, .7)
                cb.add(hb_, ps[0] - 12, d, 62)
                choir.chord(hb_, [ps[2], ps[3]], d, 46)
                for i in range(int(d * 2)):
                    harp.add(hb_ + i * .5, [ps[0], ps[1], ps[2], ps[3], ps[2] + 12, ps[3]][i % 6] + 12 * (i >= 6), 1.2, 52 + (8 if i == 0 else 0))
            if final:
                for i, p in enumerate(["D5", "F#5", "A5", "D6"]): harp.add(b + 2 + i * .25, p, 2, 58)
    return s.render()


# ----------------------------------------------------------------------------------------------- approach (Hijaz climb)
HIJAZ_STEPS = [0, 1, 4, 5, 7, 8, 10]


def cue_approach(c):
    """Esther climbs: the low strings walk up the Hijaz scale one step every two beats, a timpani heartbeat, darbuka
    getting denser, tremolo strings and a reed lead swelling; at her bow everything drops to a held breath."""
    s = Score(c, 100, 4)
    total = s.bars * 4
    bow = s.at(c.first("acting", who="esther", clip="bow"))
    cut = bow if bow is not None and 4 <= bow < total - 0.25 else total
    vc = s.part("cello steps", CELLO, -2, .3)
    cb = s.part("contrabass steps", CBASS, -6, .26)
    timp = s.part("timpani", TIMPANI, -9, .28)
    trem = s.part("tremolo strings", TREM_STR, 0, .45, lp=6000)
    reed = s.part("oboe lead", OBOE, -4, .38, lp=5000)
    shanai = s.part("shanai double", SHANAI, -15, .35, lp=3000)
    choir = s.part("choir", CHOIR, -3, .55, lp=5000)
    drb = s.part("darbuka", DRUMS, -5, .16, human=.004)
    nsteps = max(1, int(cut // 2))
    for i in range(nsteps):
        b = 2 * i; u = i / max(1, nsteps - 1)
        p = note("D2") + 12 * (i // 7) + HIJAZ_STEPS[i % 7]; v = 60 + 46 * u
        vc.add(b, p + 12, 1.85, v); cb.add(b, p, 1.85, v - 6)
        if b >= cut / 2: reed.add(b, p + 36 if p + 36 <= note("D6") else p + 24, 1.95, 62 + 30 * u); shanai.add(b, p + 24, 1.95, 50 + 30 * u)
    for bt in range(int(math.ceil(cut))):
        u = bt / max(1, cut); timp.add(bt, "D2", .45, 58 + 50 * u + (10 if bt % 2 == 0 else 0))
    bars_climb = int(math.ceil(cut / 4))
    for bar in range(bars_climb):
        u = bar / max(1, bars_climb - 1)
        pat = ["D...D...D...D...", "D.T.D.T.D.T.D.T.", "D.TkD.TkD.TkDkTk", "DkTkDkTkDkTkTkTk"][min(3, int(u * 3.99))]
        groove(drb, bar * 4, pat, .25, DARBUKA, 0.75 + 0.3 * u, until=cut)
    last_bar = max(0, (bars_climb - 1) * 4)
    trem.chord(0, ["D4", "F#4", "A4"], last_bar, 50); trem.chord(last_bar, ["Eb4", "G4", "Bb4"], cut - last_bar, 60)
    trem.ramp(0, cut, 11, 40, 127, 1.4)
    choir.chord(last_bar, ["D4", "A4"], cut - last_bar, 60); choir.ramp(last_bar, cut, 11, 50, 120)
    rest = s.beat(s.secs) - cut + 2
    trem.chord(cut, ["D5", "Eb5"], rest, 46); trem.ramp(cut, cut + rest, 11, 80, 40)
    cb.add(cut, "D2", rest, 44); timp.add(cut, "D2", .4, 50)
    return s.render()


# ----------------------------------------------------------------------------------------------- sceptre
SCE_MEL = {"G": [("D5", 1.5), ("B4", .5), ("A4", 1), ("G4", 1)], "EmA": [("G4", 1), ("F#4", 1), ("E4", 1), ("A4", 1)],
           "D": [("F#4", 2), ("A4", 1), ("D5", 1)], "Dlast": [("A4", 1), ("F#4", 3)]}
SCE_HARM = {"G": ["G"], "EmA": ["Em", "A"], "D": ["D"], "Dlast": ["D"]}


def cue_sceptre(c):
    """A suspended chord (Dsus2/4) swelling with harp and choir, resolving to D major the moment Esther touches the
    sceptre (bells + celesta sparkle); then a warm D-major passage with harp and flute."""
    s = Score(c, 76, 4, min_bars=2)
    total = s.bars * 4
    rt = c.first("acting", who="esther", clip="touch_sceptre")
    if rt is None and c.first("sfx", id="sceptre_chime") is not None: rt = c.first("sfx", id="sceptre_chime") + 0.7
    rb = s.at(rt)
    rb = float(np.clip(rb if rb is not None else 2.0, 1.0, max(1.0, total - 4)))
    strings = s.part("slow strings", SLOW_STR, -2, .5, lp=6000)
    choir = s.part("choir", CHOIR, -9, .58, lp=5500)
    harp = s.part("harp", HARP, -4, .45)
    cel = s.part("celesta", CELESTA, -6, .55)
    glock = s.part("glockenspiel", GLOCK, -8, .5)
    bells = s.part("tubular bell", TUBULAR, -8, .55)
    fl = s.part("flute", FLUTE, -3, .45, human=.01)
    cb = s.part("contrabass", CBASS, -9, .3)
    sus = ["D3", "A3", "D4", "E4", "G4", "A4"]; res = ["D3", "A3", "D4", "F#4", "A4", "D5"]
    strings.chord(0, sus, rb + .15, 64, strum=.04); strings.ramp(0, rb, 11, 40, 120, 1.3)
    choir.chord(0, ["D4", "G4", "A4"], rb + .1, 54); choir.ramp(0, rb, 11, 45, 115, 1.3)
    cb.add(0, "D2", rb, 50)
    gl = ["D4", "E4", "G4", "A4", "D5", "E5", "G5", "A5", "D6"]
    for i, p in enumerate(gl): harp.add(min(rb - .4, 1.6) * i / len(gl), p, 1.5, 50 + i * 3)
    b1 = math.ceil((rb + 2) / 4) * 4
    hold = min(b1, total) - rb
    strings.chord(rb, res, hold + (1.5 if b1 >= total else 0), 72); strings.ramp(rb, rb + hold, 11, 120, 100)
    choir.chord(rb, ["D4", "F#4", "A4"], hold, 58)
    cb.add(rb, "D2", hold, 60)
    bells.add(rb, "D5", 4, 84)
    for i, p in enumerate(["D6", "F#6", "A6", "D7", "F#7"]):
        cel.add(rb + i * .18, p, 2.5, 74 - i * 4); glock.add(rb + .05 + i * .18, p, 1.5, 60 - i * 4)
    harp.chord(rb, [note(p) + 12 for p in res[1:5]], 2, 62, strum=.07)
    for i in range(int((b1 - rb - 1) * 2)):
        harp.add(rb + 1 + i * .5, ["D4", "A4", "F#4", "A4"][i % 4], 1.2, 48)
    nb = int((total - b1) // 4) if b1 < total else 0
    plan = (["G", "EmA", "D"] * nb)[:max(0, nb - 1)] + (["Dlast"] if nb else [])
    for j, key in enumerate(plan):
        b = b1 + j * 4; harm = SCE_HARM[key]; final = key == "Dlast"
        mel(fl, b, SCE_MEL[key], 66, vib=True)
        for half, chn in enumerate(harm):
            ps = chord(chn); hb_ = b + half * 4 / len(harm); d = 4 / len(harm)
            strings.chord(hb_, [ps[1], ps[2], ps[3]], d + (1.5 if final else 0), 50)
            cb.add(hb_, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], d, 54)
            for i in range(int(d * 2)):
                harp.add(hb_ + i * .5, [ps[0], ps[1], ps[2], ps[3]][[0, 1, 2, 3, 2, 1, 2, 3][i % 8]] + 12, 1.2, 50 + (8 if i == 0 else 0))
        if final:
            for i, p in enumerate(["A5", "D6", "F#6"]): cel.add(b + 1 + i * .3, p, 2, 50)
    return s.render()


# ----------------------------------------------------------------------------------------------- banquet
BAN_HARM = ["D", "C", "G", "D"]
BAN_MEL = [
    [("A4", 2), ("B4", 1), ("A4", 2), ("F#4", 1)],
    [("G4", 1), ("A4", 1), ("G4", 1), ("E4", 3)],
    [("D4", 1), ("G4", 1), ("B4", 1), ("A4", 2), ("G4", 1)],
    [("F#4", 2), ("E4", 1), ("D4", 3)],
]


def cue_banquet(c):
    """Warm and light, D Mixolydian in 6/8: lute (nylon guitar) arpeggios and tune, tambourine and frame drum.
    When the first line after the table appears starts (Esther's accusation), the tune and tambourine drop out."""
    s = Score(c, 200, 6)       # beat = eighth note
    seq = fill_phrase(s.bars, 4, 1)
    lute = s.part("lute arps", NYLON, -3, .3, human=.007)
    tune = s.part("lute tune", NYLON, 0, .3, human=.006)
    harp = s.part("harp bass", HARP, -9, .35)
    tamb = s.part("tambourine", DRUMS, -1, .2, human=.004)
    frame = s.part("frame drum", DRUMS, -7, .2, lp=3000)
    pad = s.part("strings", SLOW_STR, -13, .45, lp=4500)
    lines = [t for t in c.all("lines") if t > c.t + 0.5]
    thin = s.at(min(lines)) if lines else None
    for bar, k in enumerate(seq):
        b = bar * 6; ch = BAN_HARM[k]; ps = chord(ch); final = bar == s.bars - 1
        quiet = thin is not None and b >= thin - 1
        for i, idx in enumerate([0, 1, 2, 3, 2, 1] if not final else [0, 1, 2, 3]):
            lute.add(b + i, ps[idx], 1.6, (72 if i == 0 else 58) - (14 if quiet else 0))
        harp.add(b, ps[0] - 12, 6, 58)
        pad.chord(b, [ps[1], ps[3]], 6, 40 if quiet else 34)
        if not quiet:
            mel(tune, b, BAN_MEL[k], 82)
            groove(tamb, b, "S..s..", 1, {"S": (TAMB, 62), "s": (TAMB, 44)})
            for i in (1, 2, 4, 5): tamb.add(b + i, SHAKER, .5, 30)
            groove(frame, b, "D..t..", 1, {"D": (LO_CONGA, 80), "t": (MUTE_CONGA, 52)})
        else:
            frame.add(b, LO_CONGA, 1, 56)
    return s.render()


# ----------------------------------------------------------------------------------------------- truth
TRUTH_PLEAD = [("A3", .75), ("G#3", .25), ("A3.", .5), (None, .5), ("G3", .75), ("F#3", .25), ("G3.", .5), (None, .5),
               ("F3", .75), ("E3", .25), ("F3.", .5), (None, .5), ("E3", 1), ("D3", 1)]


def cue_truth(c):
    """Hijaz again, angrier: 8th-note low-string ostinato, full maqsum, a reed cry; an orchestra stab on the truth
    flash; after the boing Haman's turn figure comes back as a drooping bassoon plea; a xylophone/pizz scurry away."""
    s = Score(c, 100, 4, min_bars=2)
    total = s.bars * 4
    fb = s.at(c.first("sfx", id="gasp") or c.first("fx", id="truth_flash"))
    fb = fb if fb is not None else total * 0.4
    bb = s.at(c.first("sfx", id="boing")); bb = bb if bb is not None and bb > fb else min(total - 2, fb + 3)
    sb = s.at(c.first("sfx", id="scurry")); sb = sb if sb is not None and sb > bb else max(bb + 1, total - 2)
    vc = s.part("cello ostinato", CELLO, -3, .28, human=.005)
    cb = s.part("contrabass", CBASS, -6, .25, human=.005)
    trem = s.part("tremolo strings", TREM_STR, -3, .45, lp=6000)
    ney = s.part("ney (shakuhachi)", SHAKU, -3, .42, lp=6500)
    shanai = s.part("shanai", SHANAI, -15, .35, lp=3200)
    drb = s.part("darbuka", DRUMS, -6, .16, human=.004)
    timp = s.part("timpani", TIMPANI, -5, .3)
    hit = s.part("orchestra hit", ORCH_HIT, -6, .4)
    cym = s.part("cymbal", DRUMS, -16, .5)
    bsn = s.part("bassoon", BASSOON, -1, .25, human=.008)
    pz = s.part("pizzicato", PIZZ, -5, .25)
    xy = s.part("xylophone", XYLO, -5, .3)
    ost = ["D2", "D2", "Eb2", "D2", "D2", "D2", "F#2", "Eb2"]
    i = 0
    while i * .5 < fb - .5:
        u = i * .5 / max(1, fb); v = 60 + 42 * u + (12 if i % 8 == 0 else 0)
        vc.add(i * .5, ost[i % 8], .45, v, 12); cb.add(i * .5, ost[i % 8], .45, v - 8); i += 1
    for bar in range(int(math.ceil(fb / 4))):
        u = bar * 4 / max(1, fb)
        groove(drb, bar * 4, "D.T...T.D...T..." if u < .5 else "D.TkD.kTD.TkTkTk", .25, DARBUKA, .8 + .3 * u, until=fb - .25)
    trem.chord(0, ["D4", "Eb4", "A4"], fb, 52); trem.ramp(0, fb, 11, 45, 125, 1.3)
    for b in range(0, int(fb) - 3, 8):
        mel(ney, b + .5, [("D5^Eb5", 1), ("C5", .5), ("Bb4", .5), ("A4", 2)], 86, vib=True)
        mel(shanai, b + .5, [("D5^Eb5", 1), ("C5", .5), ("Bb4", .5), ("A4", 2)], 64)
    if fb >= 2: timp.add(fb - 1, "D2", .25, 70); timp.add(fb - .5, "D2", .25, 84)
    hit.chord(fb, ["D3", "F#3", "A3", "D4"], 1.5, 112); timp.add(fb, "D2", 1.5, 118); cym.add(fb, CRASH, 2, 78)
    trem.chord(fb, ["D3", "Eb3", "A3"], bb - fb + .5, 72); trem.ramp(fb, bb, 11, 120, 50)
    cb.add(fb, "D2", bb - fb, 70)
    b = bb + .5; j = 0
    while b < sb - .2 and j < 200:
        p, d = TRUTH_PLEAD[j % len(TRUTH_PLEAD)]
        if p is not None and b + d <= sb: mel(bsn, b, [(p, d)], 82)
        b += d; j += 1
    for bt in np.arange(math.ceil(bb), sb - .2, 1.0):
        ps = chord("Dm"); pz.chord(bt, [ps[0] - 12] if int(bt) % 2 == 0 else [ps[1], ps[3]], .25, 56 if int(bt) % 2 == 0 else 44)
    run = ["D6", "C6", "Bb5", "A5", "G5", "F#5", "Eb5", "D5"]
    stepb = max(.12, min(.25, (total - sb - .3) / len(run)))
    for k, p in enumerate(run):
        xy.add(sb + k * stepb, p, .3, 78 - k * 3); pz.add(sb + k * stepb, p, .2, 70 - k * 3, -24)
    return s.render()


# ----------------------------------------------------------------------------------------------- celebration
CEL_HARM = ["D", "G", "A", "D"]
CEL_MEL = [
    [("F#5", .5), ("A5", .5), ("F#5", .5), ("D5", .5), ("E5", 1), ("F#5", 1)],
    [("G5", .5), ("F#5", .5), ("E5", .5), ("D5", .5), ("B4", 1), ("D5", 1)],
    [("C#5", .5), ("D5", .5), ("E5", .5), ("F#5", .5), ("E5", .5), ("D5", .5), ("C#5", .5), ("A4", .5)],
    [("D5", 1), ("A4", .5), ("D5", .5), ("F#5", 1), (None, 1)],
]
CALM_HARM = [["G"], ["D"], ["Em", "A"], ["D"]]
CALM_MEL = [[("B4", 4)], [("A4", 2), ("F#4", 2)], [("G4", 2), ("E4", 2)], [("D5", 4)]]
HAND = {"D": (LO_CONGA, 92), "O": (OPEN_CONGA, 78), "t": (MUTE_CONGA, 60), "k": (HI_BONGO, 56), "b": (LO_BONGO, 66)}


def cue_celebration(c):
    """D major party: quick congas/bongos, claps on 2 and 4, tambourine, flute tune doubled by the qanun, lute
    off-beats, bouncing pizz bass. At the closing narration (golden rays) it settles into harp, strings and a slow
    flute line, ending on D major."""
    s = Score(c, 134, 4, min_bars=2)
    n = s.bars
    calm_t = c.first("fx", id="golden_rays")
    lines_after = [t for t in c.all("lines", who="narrator") if t > c.t + 4]
    if calm_t is None and lines_after: calm_t = max(lines_after)
    cb_ = s.at(calm_t)
    calm_bar = int(np.clip(round(cb_ / 4) if cb_ is not None else round(n * .5), 1, n - 1))
    fl = s.part("flute", FLUTE, 0, .32, human=.006)
    qk = s.part("qanun koto", KOTO, -9, .3, human=.006)
    lute = s.part("lute offbeats", NYLON, -7, .28, human=.006)
    pz = s.part("pizz bass", PIZZ, -4, .22)
    cbass = s.part("contrabass", CBASS, -9, .3)
    pad = s.part("strings", SLOW_STR, -10, .48, lp=5000)
    harp = s.part("harp", HARP, -5, .42)
    hand = s.part("hand drums", DRUMS, -5, .16, human=.004)
    claps = s.part("claps", DRUMS, -3, .3, human=.009)
    cel = s.part("celesta", CELESTA, -11, .55)
    party = fill_phrase(calm_bar, 4, 1)
    for bar in range(calm_bar):
        b = bar * 4; k = party[bar]; ps = chord(CEL_HARM[k])
        mel(fl, b, CEL_MEL[k], 88); mel(qk, b, CEL_MEL[k], 62, shift=-12)
        for q in range(4):
            pz.add(b + q, (ps[0] if q % 2 == 0 else ps[1]) - 12, .4, 80 if q == 0 else 66)
            lute.chord(b + q + .5, [ps[1], ps[2], ps[3]], .35, 58, strum=.02)
        pad.chord(b, [ps[1], ps[2], ps[3]], 4, 40)
        groove(hand, b, "D.kOt.kOD.kOtkOk" if bar % 4 != 3 else "D.kOt.kObbOOtkkk", .25, HAND, swing=.08)
        for q in (1, 3):
            for _ in range(3): claps.add(b + q, CLAP, .3, 70)
        groove(hand, b, "SsSsSsSs", .5, {"S": (TAMB, 52), "s": (TAMB, 34)})
    calm = fill_phrase(n - calm_bar, 4, 1)
    for j, k in enumerate(calm):
        bar = calm_bar + j; b = bar * 4; harm = CALM_HARM[k]; final = bar == n - 1
        mel(fl, b, CALM_MEL[k], 64, vib=True)
        for half, chn in enumerate(harm):
            ps = chord(chn); hb_ = b + half * 4 / len(harm); d = 4 / len(harm)
            pad.chord(hb_, [ps[1], ps[2], ps[3]], d + (2 if final else 0), 54); pad.ramp(hb_, hb_ + d, 11, 85, 115, .7)
            cbass.add(hb_, ps[0] - 12 if ps[0] - 12 >= note("C2") else ps[0], d + (2 if final else 0), 58)
            for i in range(int(d * 2)):
                harp.add(hb_ + i * .5, [ps[0], ps[1], ps[2], ps[3]][[0, 1, 2, 3, 2, 3, 2, 1][i % 8]] + 12, 1.3, 50 + (8 if i == 0 else 0))
        hand.add(b, LO_CONGA, 1, 52)
        if j == 0: hand.add(b, TAMB, .5, 40)
        if final:
            for i, p in enumerate(["D6", "F#6", "A6", "D7"]): cel.add(b + 1 + i * .25, p, 3, 56 - i * 3)
    return s.render()


MUSIC = {"palace_theme": cue_palace, "haman_theme": cue_haman, "tension": cue_tension, "mordecai": cue_mordecai,
         "approach": cue_approach, "sceptre": cue_sceptre, "banquet": cue_banquet, "truth": cue_truth,
         "celebration": cue_celebration}
CUE_NOTES = {
    "palace_theme": "D Dorian 3/4. Qanun (koto + harp in octaves, tremolo on long notes) over harp arpeggios, frame drum, low strings; flute counter-line from Esther's crowning (sparkle); cadence on D.",
    "haman_theme": "Comic villain, D minor, staccato. Bassoon struts the motif with a cheeky turn, clarinet answers; pizz oom-pah, tiptoe wood blocks; timpani + pizz catch each stomp.",
    "tension": "D Hijaz. Maqsum on darbuka, cello/bass drone on D, tremolo strings swelling D / Eb / Gm / Cm over the drone, ney-like lead (shakuhachi + oboe) with grace notes.",
    "mordecai": "Tender. Cello tune in D minor with flute answers over low strings and harp; from the prayer (soft bell) the flute leads F - C - Bb/C up to a hopeful D major.",
    "approach": "Esther's climb: strings walk up the Hijaz scale one step every 2 beats with a timpani heartbeat, darbuka denser each bar, reed + tremolo + choir swell to Eb/D; at her bow all drop to a held D/Eb breath.",
    "sceptre": "Dsus2/4 swelling (strings, choir, harp glissando) resolving to D major at the sceptre touch with tubular bell + celesta/glockenspiel sparkle; then warm harp/flute D major.",
    "banquet": "Warm and light, D Mixolydian 6/8: lute (nylon guitar) tune and arpeggios, tambourine, frame drum; tune and tambourine drop out under Esther's accusation line.",
    "truth": "Hijaz, angry: 8th-note low-string ostinato, full darbuka, reed cry; orchestra stab + timpani + cymbal on the truth flash; drooping bassoon plea (Haman's turn figure) after the boing; xylophone/pizz scurry away.",
    "celebration": "D major party: congas/bongos, claps on 2 and 4, tambourine, flute tune doubled by qanun, lute off-beats, pizz bass; settles to harp/strings/slow flute at the closing narration; ends on D major.",
}


# =============================================================================================== audio helpers
def run(cmd): return subprocess.run(cmd, check=True, capture_output=True, text=True)


def render_midi(mid):
    """MIDI -> mono float32 at SR via FluidSynth, dry (its own reverb and chorus are off; we add our own)."""
    tmp = tempfile.mkdtemp(); midp, raw = f"{tmp}/x.mid", f"{tmp}/x.wav"; mid.save(midp)
    run(["fluidsynth", "-ni", "-g", "0.5", "-R", "0", "-C", "0", "-r", str(SR), "-O", "float", "-T", "wav",
         "-F", raw, DLS, midp])
    sr, x = wavfile.read(raw); assert sr == SR
    x = x.astype(np.float32); return x.mean(axis=1) if x.ndim == 2 else x


def resonator(x, f, bw):
    r = np.exp(-np.pi * bw / SR); c = np.cos(2 * np.pi * f / SR)
    return signal.lfilter([1 - r], [1, -2 * r * c, r * r], x)


def t_axis(secs): return np.arange(int(secs * SR)) / SR
def noise(n): return RNG.standard_normal(n)
def bp(x, lo, hi, order=2): return signal.sosfilt(signal.butter(order, [lo, hi], "bandpass", fs=SR, output="sos"), x)
def lp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, "lowpass", fs=SR, output="sos"), x)
def hp(x, f, order=2): return signal.sosfilt(signal.butter(order, f, "highpass", fs=SR, output="sos"), x)
def env_exp(n, tau, delay=0.0):
    t = np.arange(n) / SR - delay; return np.where(t >= 0, np.exp(-np.maximum(t, 0) / tau), 0.0)
def place(dst, src, at):
    i = int(round(at * SR)); n = min(len(src), len(dst) - i)
    if i >= 0 and n > 0: dst[i:i + n] += src[:n]


def make_ir(secs, rt_low, rt_mid, rt_high, predelay, n_early, seed_):
    """Synthetic room impulse: early reflections + diffuse tail whose decay is longer in the lows than in the highs."""
    rng = np.random.default_rng(seed_); n = int(secs * SR); t = np.arange(n) / SR
    nz = rng.standard_normal(n)
    tail = (lp(nz, 350) * np.exp(-6.91 * t / rt_low) + bp(nz, 350, 3500) * np.exp(-6.91 * t / rt_mid)
            + hp(nz, 3500) * 0.7 * np.exp(-6.91 * t / rt_high))
    tail *= 1 - np.exp(-t / 0.035)                                  # diffusion builds up instead of a hard onset
    ir = np.zeros(n + int(predelay * SR)); ir[int(predelay * SR):] += tail * 0.55
    for _ in range(n_early):
        d = rng.uniform(0.004, 0.06); g = 0.9 * np.exp(-d / 0.035) * rng.choice([-1, 1])
        k = int(d * SR); ir[k:k + 64] += g * np.hanning(64) / 8         # slightly smeared, not a sharp click
    ir = lp(ir, 9000)
    return ir / (np.sqrt(np.sum(ir ** 2)) + 1e-12)


_IR = {}
def _ir(key, *a):
    if key not in _IR: _IR[key] = make_ir(*a)
    return _IR[key]
IRS = {"hall": lambda: _ir("hall", 2.8, 2.3, 1.8, 0.9, 0.022, 12, 1),
       "room": lambda: _ir("room", 1.0, 0.7, 0.55, 0.3, 0.008, 14, 2)}


def room(x, kind="room", wet=0.25):
    ir = IRS[kind](); y = signal.fftconvolve(x, ir)
    out = np.zeros(len(y)); out[:len(x)] += x * (1 - wet); out += y * wet * 0.9
    return out


def fit(x, secs, fade_in=0.0, fade_out=0.3):
    n = int(round(secs * SR)); y = np.zeros(n, np.float64); y[:min(n, len(x))] = x[:n]
    if fade_in > 0: k = int(fade_in * SR); y[:k] *= np.linspace(0, 1, k)
    if fade_out > 0: k = int(fade_out * SR); y[-k:] *= np.linspace(1, 0, k) ** 2
    return y


def write_wav(path, x):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    wavfile.write(path, SR, (np.clip(x, -1, 1) * 32767).round().astype(np.int16))
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame",
         "-b:a", "96k", path[:-4] + ".mp3"])


def measure(path):
    """EBU R128 integrated loudness (LUFS), true peak (dBTP), sample peak (dBFS) via ffmpeg ebur128."""
    err = subprocess.run(["ffmpeg", "-nostats", "-i", path, "-af", "ebur128=peak=true+sample", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    summ = err[err.rfind("Summary:"):]
    def get(pat):
        m = re.search(pat, summ, re.S); v = m.group(1) if m else "-inf"
        return float("-inf") if "inf" in v else float(v)
    return dict(lufs=get(r"I:\s+(-?[\d.]+|-inf) LUFS"), truePeak=get(r"True peak:\s+Peak:\s+(-?[\d.]+|-inf)"),
                samplePeak=get(r"Sample peak:\s+Peak:\s+(-?[\d.]+|-inf)"))


def probe_secs(path):
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path]).stdout.strip())


def normalize_lufs(x, target, tp_ceiling=-1.0):
    """Gain to an integrated loudness target (ffmpeg, two passes); soft-clips rare transients over the TP ceiling."""
    tmp = tempfile.mkdtemp() + "/m.wav"
    for _ in range(3):
        wavfile.write(tmp, SR, x.astype(np.float32)); m = measure(tmp)
        g = target - m["lufs"]
        if abs(g) < 0.05 and m["truePeak"] <= tp_ceiling: break
        if m["truePeak"] + g > tp_ceiling - 0.3:
            c = 10 ** ((tp_ceiling - 0.6) / 20) / 10 ** (g / 20)
            x = np.tanh(x / c) * c
        x = x * 10 ** (g / 20)
    return x.astype(np.float32)


def peak_normalize(x, db):
    return (x / (np.max(np.abs(x)) + 1e-12) * 10 ** (db / 20)).astype(np.float32)


# =============================================================================================== sfx synthesis
def adsr(n, a, d_tau, hold=0.0):
    t = np.arange(n) / SR
    return np.where(t < a, t / max(a, 1e-4), np.where(t < a + hold, 1.0, np.exp(-(t - a - hold) / d_tau)))


def smooth_rand(n, rate_hz, lo=-1.0, hi=1.0):
    k = max(2, int(n / SR * rate_hz) + 2); pts = RNG.uniform(lo, hi, k)
    return np.interp(np.linspace(0, k - 1, n), np.arange(k), pts)


def partials(secs, f0, ratios, amps, taus, strike=0.0, detune=0.0015):
    """Sum of decaying sine partials (bells, glints, glass) with a touch of beating."""
    n = int(secs * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for r, a, tau in zip(ratios, amps, taus):
        f = f0 * r
        if f > SR * 0.45: continue
        ph = RNG.uniform(0, 2 * np.pi)
        y += a * (np.sin(2 * np.pi * f * t + ph) + 0.6 * np.sin(2 * np.pi * f * (1 + detune) * t)) * np.exp(-t / tau)
    if strike: y += strike * hp(noise(n), 3000) * env_exp(n, 0.002)
    return y * np.minimum(1, t / 0.0015)


def glottal(f0, tilt=1.25):
    """Band-limited glottal-like source for an f0 curve (Hz per sample), harmonics falling ~ 1/k^tilt."""
    ph = 2 * np.pi * np.cumsum(f0) / SR; y = np.zeros(len(f0)); fmin = max(60.0, float(np.min(f0)))
    for k in range(1, int(7000 / fmin) + 1):
        y += (k * f0 < 7500) * np.sin(k * ph) / k ** tilt
    return y


VOW = {  # (F1..F4) adult male; bandwidths
    "h": ([550, 1500, 2500, 3500], [300, 350, 400, 500]),
    "a": ([750, 1220, 2600, 3400], [90, 110, 160, 250]), "ah": ([680, 1100, 2450, 3300], [90, 110, 160, 250]),
    "e": ([480, 1950, 2650, 3500], [70, 110, 160, 250]), "i": ([300, 2250, 2950, 3600], [60, 110, 160, 250]),
    "u": ([330, 800, 2300, 3300], [60, 90, 150, 250]), "o": ([500, 870, 2500, 3300], [80, 100, 150, 250]),
    "eh": ([580, 1800, 2600, 3400], [80, 120, 160, 250]),
}


def formant_filter(x, keys, scale=1.0, gains=(0, -4, -10, -16), tilt_hz=None):
    """Time-varying formant filter via STFT. keys = [(u in 0..1, vowel), ...] across the length of x."""
    nper, hop = 1024, 128
    f, tt, Z = signal.stft(x, SR, nperseg=nper, noverlap=nper - hop, boundary="even")
    u = np.clip(tt / max(len(x) / SR, 1e-6), 0, 1); ku = [k[0] for k in keys]
    F = np.stack([np.interp(u, ku, [VOW[k[1]][0][i] for k in keys]) for i in range(4)]) * scale
    B = np.stack([np.interp(u, ku, [VOW[k[1]][1][i] for k in keys]) for i in range(4)]) * scale
    env = np.zeros((len(f), len(tt)))
    for i in range(4):
        env += 10 ** (gains[i] / 20) / (1 + ((f[:, None] - F[i][None, :]) / (B[i][None, :] / 2)) ** 2)
    env *= np.clip(f[:, None] / 150.0, 0, 1)                   # nothing below the voice
    _, y = signal.istft(Z * env, SR, nperseg=nper, noverlap=nper - hop, boundary=True)
    return y[:len(x)]


def voice(secs, f0_curve, keys, scale, breath=0.12, jitter=0.012, vib=(5.5, 0.012), amp_env=None):
    """One human-ish voiced syllable: jittered, vibrato'd glottal source + breath noise through moving formants."""
    n = int(secs * SR); t = np.arange(n) / SR
    f0 = f0_curve * (1 + jitter * smooth_rand(n, 25)) * (1 + vib[1] * np.sin(2 * np.pi * vib[0] * t + RNG.uniform(0, 6)))
    src = glottal(f0) * (1 + 0.08 * smooth_rand(n, 18))         # shimmer
    src = src / (np.std(src) + 1e-9) + breath * noise(n) * 2.2
    y = formant_filter(src, keys, scale)
    if amp_env is not None: y *= amp_env
    return y


def sfx_sparkle():
    """Crown sparkle: a rising shower of tiny bells in D major pentatonic plus airy shimmer."""
    secs = 1.8; n = int(secs * SR); y = np.zeros(n)
    pent = [note(p) for p in ["D6", "E6", "F#6", "A6", "B6", "D7", "E7", "F#7", "A7"]]
    for i in range(16):
        m = pent[min(len(pent) - 1, int(i / 16 * len(pent) + RNG.integers(0, 2)))]
        f = 440 * 2 ** ((m - 69) / 12)
        b = partials(1.0, f, [1, 2.76, 5.4], [1, .35, .12], [RNG.uniform(.25, .5), .15, .06], strike=.15)
        place(y, b * RNG.uniform(.5, 1.0), 0.02 + i * 0.055 + RNG.normal(0, .008))
    sh = hp(noise(n), 6000) * np.exp(-((np.arange(n) / SR - .45) / .35) ** 2) * .12
    y += sh
    return fit(room(y, "hall", .35), secs, fade_out=.4)


def sfx_stomp():
    """Haman's cartoon stomp: heel slap, boot thump with a short pitch drop, wooden floor knock."""
    secs = 0.6; n = int(secs * SR); t = np.arange(n) / SR
    f = 120 * np.exp(-t / .05) + 52
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * env_exp(n, .09)
    slap = bp(noise(n), 700, 4000) * env_exp(n, .008) * .7
    x = noise(n) * env_exp(n, .003)
    knock = resonator(x, 190, 40) * 1.2 + resonator(x, 430, 70) * .8
    y = thump * 1.0 + slap + knock
    return fit(room(y, "room", .18), secs, fade_out=.12)


def sfx_ring_glint():
    """The king's signet ring catches the light: a bright metallic 'ting' with a little shimmer tail."""
    secs = 1.2
    y = partials(secs, 2637, [1, 2.32, 4.25, 6.63], [1, .5, .25, .12], [.45, .25, .12, .07], strike=.2)
    n = len(y); sh = np.zeros(n)
    for _ in range(14):
        place(sh, partials(.3, RNG.uniform(5000, 9000), [1], [1], [.06]), RNG.uniform(.03, .5))
    y = y + sh * .25
    return fit(room(y, "hall", .3), secs, fade_out=.3)


def sfx_soft_bell():
    """A soft, warm handbell for the prayer: low hum, prime, minor-third tierce, quint, nominal; felt-mallet strike."""
    secs = 3.2; f0 = 587.3
    y = partials(secs, f0, [0.5, 1.0, 1.19, 1.5, 2.0, 2.52, 3.0], [.35, 1, .32, .2, .45, .12, .08],
                 [2.6, 2.0, 1.4, 1.0, 1.1, .6, .4])
    n = len(y); y *= np.minimum(1, np.arange(n) / SR / .006)     # soft mallet, no click
    y += lp(noise(n), 1500) * env_exp(n, .01) * .05
    return fit(room(y, "hall", .35), secs, fade_out=.6)


def sfx_sceptre_chime():
    """Golden sceptre: a quick bell arpeggio up D major over a warm low bell, with sparkle dust."""
    secs = 2.8; n = int(secs * SR); y = np.zeros(n)
    place(y, partials(2.6, 293.7, [0.5, 1, 2, 2.4, 3, 4.2], [.3, 1, .5, .2, .15, .08], [2.2, 1.8, 1.2, .8, .6, .4]) * .7, 0)
    for i, p in enumerate(["D6", "F#6", "A6", "D7", "F#7", "A7"]):
        f = 440 * 2 ** ((note(p) - 69) / 12)
        place(y, partials(1.6, f, [1, 2.76, 5.4], [1, .3, .1], [.7, .25, .08], strike=.1) * (.8 - i * .05), .02 + i * .07)
    for _ in range(40):
        place(y, partials(.25, RNG.uniform(6000, 10000), [1], [1], [.05]) * RNG.uniform(.05, .2), RNG.uniform(.3, 1.6))
    return fit(room(y, "hall", .35), secs, fade_out=.6)


def sfx_table_set():
    """The banquet table appears: a soft cloth whoosh, a few goblets and plates set down, a low wooden settle."""
    secs = 1.6; n = int(secs * SR); y = np.zeros(n); t = np.arange(n) / SR
    wh = bp(noise(n), 400, 3000) * np.exp(-((t - .18) / .12) ** 2) * .35
    y += wh
    for at, f0, kind in ((.25, 1850, "glass"), (.36, 2400, "glass"), (.48, 950, "plate"), (.6, 2150, "glass"),
                         (.72, 1250, "plate")):
        if kind == "glass": s = partials(.9, f0, [1, 2.3, 3.9, 5.6], [1, .45, .2, .1], [.35, .2, .1, .06], strike=.15)
        else: s = partials(.4, f0, [1, 1.6, 2.7, 3.9], [1, .7, .4, .2], [.08, .06, .04, .03], strike=.3)
        place(y, s * RNG.uniform(.35, .55), at + RNG.normal(0, .01))
    m = int(.4 * SR); tt = np.arange(m) / SR
    settle = np.sin(2 * np.pi * np.cumsum(90 * np.exp(-tt / .06) + 70) / SR) * env_exp(m, .07) * .5
    place(y, settle, .5)
    return fit(room(y, "room", .25), secs, fade_out=.3)


def gasp_voice(scale, f0, level, voiced=0.03):
    """One sharp inhaled 'hah!': turbulent breath through a mouth opening from 'h' to 'a', a breathy fricative top,
    and a whisper of ingressive voicing."""
    secs = .7; n = int(secs * SR); t = np.arange(n) / SR
    env = np.where(t < .035, (t / .035) ** 1.5, np.exp(-(t - .035) / .13)) * (1 + .25 * smooth_rand(n, 40))
    air = noise(n) * env
    body = formant_filter(air, [(0, "h"), (.08, "ah"), (.35, "a"), (1, "eh")], scale, gains=(0, -3, -8, -12))
    fric = bp(noise(n), 2500, 7000) * env * .08
    f0c = f0 * (1 + .12 * np.minimum(1, t / .15))
    vo = voice(secs, f0c, [(0, "ah"), (1, "a")], scale, breath=.6, vib=(0, 0), amp_env=env * np.minimum(1, t / .05)) * voiced
    y = body / (np.std(body) + 1e-9) * .3 + fric + vo
    return lp(y, 9000) * level


def sfx_gasp():
    """Court gasp at the truth flash: four people (two men, a woman, a child) catching their breath a few
    milliseconds apart, plus one soft 'oh!', in a small hall."""
    secs = 1.3; n = int(secs * SR); y = np.zeros(n)
    for at, scale, f0, lvl in ((0, .92, 120, 1.0), (.018, 1.0, 140, .8), (.04, 1.17, 230, .75), (.065, 1.3, 300, .55)):
        place(y, gasp_voice(scale, f0, lvl), at)
    m = int(.42 * SR); tt = np.arange(m) / SR
    oh_env = np.minimum(1, tt / .03) * np.exp(-np.maximum(0, tt - .08) / .12)
    oh = voice(.42, np.interp(tt, [0, .1, .42], [250, 290, 230]), [(0, "ah"), (.3, "o"), (1, "o")], 1.17,
               breath=.35, vib=(6, .01), amp_env=oh_env)
    place(y, oh / (np.max(np.abs(oh)) + 1e-9) * .18, .2)
    y = hp(y, 120)
    return fit(room(y, "room", .3), secs, fade_out=.3)


def sfx_boing():
    """Haman's cap slips: a jaw-harp-like spring boing with a wobbling, decaying pitch and a wah formant."""
    secs = 0.9; n = int(secs * SR); t = np.arange(n) / SR
    f0 = 155 * (1 + .18 * np.exp(-t / .25) * np.sin(2 * np.pi * 11 * t)) * (1 + .06 * np.exp(-t / .05))
    src = glottal(f0, tilt=.8)
    cut = 500 + 1500 * (.5 + .5 * np.sin(2 * np.pi * 11 * t + 1.2)) * np.exp(-t / .4)
    y = np.zeros(n); hop = 256                                     # block-wise moving resonance (the "wah")
    zi = None
    for i in range(0, n, hop):
        sos = signal.butter(2, [max(200, cut[i] * .6), min(8000, cut[i] * 1.6)], "bandpass", fs=SR, output="sos")
        if zi is None: zi = np.zeros((sos.shape[0], 2))
        y[i:i + hop], zi = signal.sosfilt(sos, src[i:i + hop], zi=zi)
    y = y * adsr(n, .004, .3, .05) + .3 * np.sin(2 * np.pi * np.cumsum(f0) / SR) * adsr(n, .004, .35, .05)
    return fit(room(y, "room", .15), secs, fade_out=.15)


def sfx_scurry():
    """Haman scurries off: quick light pattering feet with soft slipper scuffs and cloth flutter, running away."""
    secs = 1.3; n = int(secs * SR); y = np.zeros(n)
    k = 14
    for i in range(k):
        at = .02 + i * .075 + RNG.normal(0, .006); away = 1 - i / k * .75
        m = int(.08 * SR); tt = np.arange(m) / SR
        tap = np.sin(2 * np.pi * np.cumsum(260 * np.exp(-tt / .01) + 140) / SR) * env_exp(m, .018)
        tap += bp(noise(m), 1500, 6000) * env_exp(m, .006) * .5
        tap = lp(tap, 2000 + 5000 * away)
        place(y, tap * away * (1 if i % 2 == 0 else .8), at)
    t = np.arange(n) / SR
    flutter = bp(noise(n), 300, 2500) * (.5 + .5 * np.sin(2 * np.pi * 13 * t)) * np.exp(-t / .5) * .12
    y += flutter
    return fit(room(y, "room", .2), secs, fade_out=.25)


def sfx_cheer():
    """'Hooray!' from the court and children: 22 voices (men, women, kids) shouting 'yay' / 'wooo' / 'ah' with
    jittered rising pitch, breath and moving formants; a dozen clapping pairs of hands; glued in a hall."""
    secs = 4.0; n = int(secs * SR); vox = np.zeros(n)
    kinds = [("yay", [(0, "i"), (.12, "e"), (.7, "e"), (1, "i")]), ("wooo", [(0, "u"), (.35, "o"), (1, "o")]),
             ("ah", [(0, "h"), (.06, "a"), (1, "ah")])]
    for v in range(22):
        who = RNG.choice(["man", "woman", "child"], p=[.35, .35, .3])
        scale = {"man": RNG.uniform(.92, 1.02), "woman": RNG.uniform(1.12, 1.2), "child": RNG.uniform(1.25, 1.35)}[who]
        base = {"man": RNG.uniform(160, 220), "woman": RNG.uniform(290, 360), "child": RNG.uniform(340, 440)}[who]
        name, keys = kinds[int(RNG.integers(0, 3))]
        for rep in range(int(RNG.integers(1, 3))):
            d = RNG.uniform(.55, 1.1); m = int(d * SR); tt = np.arange(m) / SR
            rise = 1.25 if name == "wooo" else 1.12
            f0 = base * np.interp(tt, [0, d * .3, d * .75, d], [0.88, rise, rise * .97, 0.86])
            env = np.minimum(1, tt / .05) * np.where(tt > d - .2, np.maximum(0, (d - tt) / .2), 1.0)
            s = voice(d, f0, keys, scale, breath=RNG.uniform(.15, .35), jitter=.018, vib=(RNG.uniform(5, 7), .015), amp_env=env)
            s = s / (np.std(s) + 1e-9) * RNG.uniform(.4, 1.0)
            place(vox, s, RNG.uniform(.02, .45) + rep * RNG.uniform(.9, 1.3))
    claps = np.zeros(n)
    for _ in range(12):
        fc = RNG.uniform(900, 2400); rate = RNG.uniform(4.2, 6.0); at = RNG.uniform(.15, .5)
        while at < secs - .3:
            m = int(.06 * SR)
            c = bp(noise(m), fc * .55, min(fc * 1.9, 9000)) * env_exp(m, RNG.uniform(.006, .012))
            c += bp(noise(m), fc * .55, min(fc * 1.9, 9000)) * env_exp(m, .008, RNG.uniform(.002, .005)) * .5  # flam
            fade = 1.0 if at < 2.2 else max(0.0, 1 - (at - 2.2) / 1.6)
            place(claps, c * RNG.uniform(.5, 1.0) * fade, at)
            at += 1 / rate * RNG.uniform(.9, 1.1)
    vox = lp(hp(vox, 140), 6500)
    y = vox / (np.max(np.abs(vox)) + 1e-9) + claps / (np.max(np.abs(claps)) + 1e-9) * .45
    y *= np.minimum(1, np.arange(n) / SR / .04)
    return fit(room(y, "hall", .3), secs, fade_out=1.4)


SFX = {"sparkle": sfx_sparkle, "stomp": sfx_stomp, "ring_glint": sfx_ring_glint, "soft_bell": sfx_soft_bell,
       "sceptre_chime": sfx_sceptre_chime, "table_set": sfx_table_set, "gasp": sfx_gasp, "boing": sfx_boing,
       "scurry": sfx_scurry, "cheer": sfx_cheer}
# Recommended playback gain (dB) on top of the -3 dBFS-peak files, so effects sit under the voices.
SFX_GAIN = {"sparkle": -9, "stomp": -4, "ring_glint": -10, "soft_bell": -10, "sceptre_chime": -7, "table_set": -9,
            "gasp": -5, "boing": -7, "scurry": -9, "cheer": -6}
SFX_NOTES = {"sparkle": "rising shower of tiny bells (D major pentatonic) + air shimmer",
             "stomp": "cartoon boot stomp: heel slap, 170->52 Hz thump, floor knock",
             "ring_glint": "bright metallic 'ting' (E7) + shimmer",
             "soft_bell": "warm handbell on D5 (hum, tierce, quint, nominal), felt strike, long ring",
             "sceptre_chime": "bell arpeggio up D major over a low D bell, sparkle dust",
             "table_set": "cloth whoosh, three goblets + two plates set down, wooden settle",
             "gasp": "4 inhaled 'hah!' voices (2 men, woman, child) 0-65 ms apart + soft 'oh', small hall",
             "boing": "jaw-harp spring, 11 Hz pitch wobble, moving wah resonance",
             "scurry": "14 light running steps receding + cloth flutter",
             "cheer": "22 voices 'yay / wooo / ah' (men, women, kids) + 12 clappers, fades from 2.6 s"}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        last = i + 1 == len(cues)
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3),
                        secs=round(end - c["t"] + (0 if last else XFADE), 3), last=last))
    return out


def build_music(tl, only=None):
    spans = cue_spans(tl)
    missing = sorted({c["cue"] for c in spans} - set(MUSIC))
    assert not missing, f"no composer for cue(s) {missing}"
    path_json = f"{MUSIC_DIR}/cues.json"
    old = {c["cue"]: c for c in json.load(open(path_json))["cues"]} if only and os.path.exists(path_json) else {}
    manifest = []
    for c in spans:
        if only and c["cue"] not in only and c["cue"] in old:
            manifest.append(old[c["cue"]]); continue
        seed(c["cue"]); ctx = Ctx(tl, c["cue"], c["t"], c["span"], c["secs"], c["last"])
        x = MUSIC[c["cue"]](ctx)
        x = fit(x, c["secs"], fade_out=2.5 if c["last"] else 0.25)
        x = hp(x, 28)
        x = normalize_lufs(x, MUSIC_LUFS)
        path = f"{MUSIC_DIR}/{c['cue']}.wav"; write_wav(path, x); m = measure(path)
        secs = round(len(x) / SR, 3)
        need = c["span"] + (0 if c["last"] else XFADE)
        assert secs + 1e-3 >= need, f"{c['cue']} is {secs}s, needs {need}s"
        sc = Score.last
        manifest.append(dict(cue=c["cue"], t=c["t"], span=c["span"], secs=secs, lastCue=c["last"], loop=False,
                             bars=sc.bars, bpm=round(sc.bpm * (0.5 if c["cue"] == "banquet" else 1), 1),
                             lufs=round(m["lufs"], 1), truePeak=round(m["truePeak"], 1)))
        print(f"music {c['cue']:13s} t={c['t']:7.2f} span={c['span']:6.2f} file={secs:6.2f}s "
              f"bars={sc.bars:2d} bpm={manifest[-1]['bpm']:5.1f} I={m['lufs']:6.1f} LUFS TP={m['truePeak']:5.1f} dBTP")
    json.dump(dict(rule="Start each cue at its timeline t at full level and fade the previous cue out over 0.6 s from "
                        "that t. Every non-final cue is its span + 0.6 s long so the fade has music under it; the "
                        "final cue fades out by itself over its last 2.5 s. Music sits at -20 LUFS; duck it ~7 dB "
                        "under voice lines.", crossfadeSec=XFADE, lufs=MUSIC_LUFS, cues=manifest),
              open(path_json, "w"), indent=1, ensure_ascii=False)
    return manifest


def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]}); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in needed:
        seed(sid)
        x = hp(np.asarray(SFX[sid](), np.float64), 30)
        x = peak_normalize(x, SFX_PEAK_DB); path = f"{SFX_DIR}/{sid}.wav"; write_wav(path, x); m = measure(path)
        manifest.append(dict(id=sid, secs=round(len(x) / SR, 3), loop=False, gainDb=SFX_GAIN[sid],
                             samplePeak=round(m["samplePeak"], 1), truePeak=round(m["truePeak"], 1),
                             lufs=None if m["lufs"] == float("-inf") else round(m["lufs"], 1)))
        print(f"sfx   {sid:13s} {manifest[-1]['secs']:5.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f}")
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play each one-shot at its timeline t with gainDb "
                        "(recommended mix level).", peakDbfs=SFX_PEAK_DB, sfx=manifest),
              open(f"{SFX_DIR}/mix.json", "w"), indent=1, ensure_ascii=False)
    return manifest


def load_any(path):
    """Decode any audio file to mono float at SR through ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)


def build_preview(tl):
    n = int((tl["duration"] + 1.0) * SR); mus = np.zeros(n); fx = np.zeros(n); vo = np.zeros(n)
    for c in cue_spans(tl):
        x = load_any(f"{MUSIC_DIR}/{c['cue']}.wav")
        if not c["last"]:
            k0 = int(c["span"] * SR); k = int(XFADE * SR); seg = x[k0:k0 + k]
            x[k0:k0 + len(seg)] *= np.linspace(1, 0, len(seg)); x[k0 + k:] = 0
        place(mus, x, c["t"])
    for s in tl["sfx"]:
        place(fx, load_any(f"{SFX_DIR}/{s['id']}.wav") * 10 ** (SFX_GAIN[s["id"]] / 20), s["t"])
    used = 0
    for line in tl["lines"]:
        for ext in ("wav", "mp3"):
            p = f"{VOICE_DIR}/{line['id']}.{ext}"
            if os.path.exists(p): place(vo, load_any(p), line["t"]); used += 1; break
    if used:
        # Duck: voice envelope with 80 ms look-ahead, fast attack, 400 ms release.
        env = lp(np.abs(vo), 8) > 0.004; look = int(.08 * SR); env = np.r_[env[look:], np.zeros(look, bool)]
        g = np.where(env, 10 ** (DUCK_DB / 20), 1.0); out = np.empty(n); cur = 1.0
        a_att, a_rel = 1 - np.exp(-1 / (.05 * SR)), 1 - np.exp(-1 / (.4 * SR))
        for i in range(0, n, 64):  # block-rate smoothing is plenty for a duck
            tgt = g[i]; cur += (tgt - cur) * (1 - (1 - (a_att if tgt < cur else a_rel)) ** 64); out[i:i + 64] = cur
        mus *= out
    mix = (mus + fx + vo).astype(np.float32)
    tmp = tempfile.mkdtemp() + "/mix.wav"; wavfile.write(tmp, SR, mix)
    run(["ffmpeg", "-y", "-loglevel", "error", "-i", tmp, "-af", "alimiter=limit=0.89:level=false",
         "-ac", "1", "-ar", str(SR), "-c:a", "libmp3lame", "-b:a", "96k", PREVIEW])
    m = measure(PREVIEW)
    print(f"preview {probe_secs(PREVIEW):.2f}s I={m['lufs']:.1f} LUFS TP={m['truePeak']:.1f} dBTP, "
          f"zh voice clips included: {used}/{len(tl['lines'])}")
    return dict(secs=round(probe_secs(PREVIEW), 2), lufs=round(m["lufs"], 1), truePeak=round(m["truePeak"], 1),
                voices=used, lines=len(tl["lines"]))


def update_doc(tl, cues, sfx, prev):
    """Rewrite the generated tables in docs/esther/MUSIC.md (between markers); the prose around them is hand-written."""
    if not os.path.exists(DOC): return
    txt = open(DOC).read()
    def swap(tag, body):
        nonlocal txt
        txt = re.sub(rf"(<!-- {tag}:start -->\n).*?(<!-- {tag}:end -->)", lambda m: m.group(1) + body + m.group(2), txt, flags=re.S)
    if cues:
        rows = ["| Cue | t (s) | Span (s) | File (s) | Bars × bpm | LUFS | True peak (dBTP) | Content |",
                "|---|---|---|---|---|---|---|---|"]
        for c in cues:
            meter = "6/8, ♩. =" if c["cue"] == "banquet" else ("3/4" if c["cue"] == "palace_theme" else "4/4")
            rows.append(f"| `{c['cue']}` | {c['t']:.2f} | {c['span']:.2f} | {c['secs']:.2f} | {c['bars']} × {c['bpm']} ({meter}) "
                        f"| {c['lufs']:.1f} | {c['truePeak']:.1f} | {CUE_NOTES[c['cue']]} |")
        swap("cues", "\n".join(rows) + "\n")
    if sfx:
        rows = ["| Id | Length (s) | Sample peak (dBFS) | True peak (dBTP) | LUFS | gainDb | Notes |", "|---|---|---|---|---|---|---|"]
        for s in sfx:
            rows.append(f"| `{s['id']}` | {s['secs']:.2f} | {s['samplePeak']:.1f} | {s['truePeak']:.1f} | "
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
    a = ap.parse_args(); STEM_REPORT = a.stems
    assert os.path.exists(DLS), "GM bank not found at " + DLS
    tl = json.load(open(TIMELINE))
    only = set(filter(None, a.only.split(",")))
    cues = build_music(tl, only) if not a.skip_music else None
    sfx = build_sfx(tl) if not a.skip_sfx else None
    prev = build_preview(tl) if not a.skip_preview else None
    update_doc(tl, cues, sfx, prev)
