#!/usr/bin/env python3
"""music_kit: the shared music + SFX engine of every story pack (docs/STORY-KIT.md, docs/esther/MUSIC.md).

Moved out of tools/story/music_esther.py unchanged: MIDI composition (Score / Part / mel / groove / fill_phrase / Ctx,
GM program and drum-key names, chord voicings CH), the FluidSynth renderer (macOS gs_instruments.dls), the synthetic
convolution rooms (IRS: hall / room ...), DSP helpers (bp / lp / hp / dip / place / fit / room), loudness (measure,
normalize_lufs to -20 LUFS, peak_normalize), synthesis primitives (partials, adsr, smooth_rand, glottal + formant
voices), file helpers (write_wav, load_any, probe_secs) and two library effects every pack may use (sfx_sparkle,
sfx_cheer). A pack's music script supplies only its score: cue functions, SFX functions, its paths and tables.

Two ways to use it, both supported:
  import music_kit as mk; from music_kit import Score, Ctx, mel, ...      (a pack: tools/story/music_ruth.py)
  exec'd into a module's own namespace (tools/story/music_esther.py does this so its existing code is unchanged)
seed(name) reseeds this module's RNG; every engine function draws from it, so a cue rendered twice is identical.
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg
"""
import argparse, json, math, os, re, subprocess, tempfile, warnings, zlib
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from mido import Message, MetaMessage, MidiFile, MidiTrack, bpm2tempo
from scipy import signal
from scipy.io import wavfile

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


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


TRUMPET, TROMBONE, TUBA, MUTED_TPT, HORN = 56, 57, 58, 59, 60


DRUMS = None


# GM drum keys
BDRUM, CLAP, TAMB, CRASH, HI_BONGO, LO_BONGO, MUTE_CONGA, OPEN_CONGA, LO_CONGA = 35, 39, 54, 49, 60, 61, 62, 63, 64


HI_WOOD, LO_WOOD, SHAKER, TRIANGLE = 76, 77, 70, 81


PEDAL_HAT, CRASH_HAND, SNARE = 44, 57, 38


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


def dip(x, f0, gain_db, q):
    """RBJ peaking EQ (here: a wide cut, to leave room for the voices around 1-4 kHz)."""
    A = 10 ** (gain_db / 40); w = 2 * np.pi * f0 / SR; al = np.sin(w) / (2 * q)
    b = [1 + al * A, -2 * np.cos(w), 1 - al * A]; a = [1 + al / A, -2 * np.cos(w), 1 - al / A]
    return signal.lfilter(np.array(b) / a[0], np.array(a) / a[0], x).astype(np.float32)


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


def gm_notes(events, secs):
    """Render a few GM notes (real instrument samples from the DLS bank) for an effect.
    events: (t_sec, dur_sec, pitch, vel, program, bends) with bends = [(t_sec, semitones), ...] relative to t."""
    mid = MidiFile(ticks_per_beat=TPB); meta = MidiTrack(); mid.tracks.append(meta)
    meta.append(MetaMessage("set_tempo", tempo=bpm2tempo(60), time=0))       # 1 beat = 1 s
    meta.append(MetaMessage("end_of_track", time=int((secs + 2) * TPB)))
    ev, chans = [], {}
    for k, (t, d, p, v, prog, bends) in enumerate(events):
        ch = chans.setdefault((prog, tuple(bends or ())), len(chans) % 9)  # same program + same bends share a channel
        ev.append((int(t * TPB), 0, Message("program_change", channel=ch, program=prog)))
        for cc, val in ((7, 110), (11, 127), (91, 0), (93, 0), (101, 0), (100, 0), (6, 2)):
            ev.append((int(t * TPB), 1, Message("control_change", channel=ch, control=cc, value=val)))
        ev.append((int(t * TPB), 2, Message("pitchwheel", channel=ch, pitch=0)))
        for bt, semi in bends or []:
            ev.append((int((t + bt) * TPB), 3, Message("pitchwheel", channel=ch, pitch=int(np.clip(semi / 2 * 8191, -8192, 8191)))))
        ev.append((int(t * TPB), 4, Message("note_on", channel=ch, note=note(p), velocity=int(v))))
        ev.append((int((t + d) * TPB), 0, Message("note_off", channel=ch, note=note(p), velocity=0)))
    tr = MidiTrack(); mid.tracks.append(tr); last = 0
    for tick, _, m in sorted(ev, key=lambda e: (e[0], e[1])):
        tr.append(m.copy(time=tick - last)); last = tick
    x = render_midi(mid)
    return fit(x, secs, fade_out=0)


def wah_filter(x, cut, q_lo=.55, q_hi=1.7, hop=128):
    """Block-wise moving band-pass ('wah' / plunger mute) following a cutoff curve in Hz (one value per sample)."""
    y = np.zeros(len(x)); zi = None
    for i in range(0, len(x), hop):
        f = float(cut[i]); sos = signal.butter(2, [max(80, f * q_lo), min(16000, f * q_hi)], "bandpass", fs=SR, output="sos")
        if zi is None: zi = np.zeros((sos.shape[0], 2))
        y[i:i + hop], zi = signal.sosfilt(sos, x[i:i + hop], zi=zi)
    return y


def load_any(path):
    """Decode any audio file to mono float at SR through ffmpeg."""
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32).astype(np.float64)
