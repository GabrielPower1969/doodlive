#!/usr/bin/env python3
"""Original score and sound effects for "Gabriel" (the archangel pack; docs/gabriel/CONTRACT.md section 7,
docs/gabriel/DESIGN.md "Music direction", docs/gabriel/MUSIC.md).

Same machinery as Daniel / Ruth, shared rather than forked: this script imports tools/story/music_esther.py (Score /
Part / mel / Ctx, the FluidSynth renderer, loudness and file helpers, synthesis primitives) and
tools/story/music_daniel.py (the sustain fix `P`, `gm_render`, small helpers) as libraries and never changes them.

What is new here, because this score has to be the richest in the app (epic, warm, cinematic orchestra with choir):

* **Synth sections layered over the sampled (DLS) instruments** (`SynthPart`): a formant **choir** (several detuned
  singers per note, men and women filtered through separate "ah" / "oh" formant banks, breath, slow vibrato), a lush
  **string ensemble** (several players per note, each with its own detune, drift and delayed vibrato, body
  resonances), and a warm FM **brass section** under the sampled horns and trumpets. The DLS choir alone is thin;
  these give the pad its width. Plus a soft suspended-cymbal swell (`AudioPart`) and a longer hall ("heaven").
* One original motif, the **Gabriel theme** (THEME below): a noble rising herald call, A-D-A-B (up a fourth, up a
  fifth, one step higher), which grows into an 8-bar melody in D major. Hinted on horns in `heaven`, in the travel
  tune's horn call in `story` (in G), soft on flute in `gentle`, the trumpet states it in the `trumpet_call` effect
  (which `fanfare` is built around, in the same key and at the same times), and the full orchestra and choir sing it
  in `finale`. Every note is original; the reference in DESIGN.md only lends the mood.

Every name and time comes from assets/gabriel/timeline.json, read on every run: cue lengths follow the music spans
and every in-cue hit is looked up by event, so after the voices re-time the timeline, just rerun this script. Every
cue continues after its cadence into a quiet loop section on its final chord (seamless, sample-exact loop points in
cues.json) and runs at least 30 % past its span as a plain tail.

Outputs (44.1 kHz mono 16-bit WAV + 96 kbps mono MP3 copies):
  assets/gabriel/audio/music/<cue>.wav|.mp3   music, -20 LUFS integrated (span), true peak <= -1 dBTP
  assets/gabriel/audio/music/cues.json        cue lengths, spans, loop points, loudness, crossfade rule
  assets/gabriel/audio/sfx/<id>.wav|.mp3      sfx, sample peak -3 dBFS
  assets/gabriel/audio/sfx/mix.json           sfx lengths, peaks, recommended playback gain
  assets/gabriel/audio/preview_mix.mp3        rough full-length mix at timeline times (zh voice clips when present)
  docs/gabriel/MUSIC.md                       the tables between the <!-- ...:start/end --> markers are rewritten

Usage: python3 tools/story/music_gabriel.py [--skip-music] [--skip-sfx] [--skip-preview] [--only a,b] [--stems]
       [--check]  (measure the files on disk: loudness, loop seams, clicks; writes nothing but the report)
       [--tmp DIR]   (scratch dir, default /tmp/gabriel_audio/music; emptied after every cue and removed at exit)
Needs: pip install mido numpy scipy; brew install fluid-synth ffmpeg (as music_esther.py)
"""
import argparse, atexit, json, math, os, re, shutil, sys, tempfile, zlib
import numpy as np
from scipy import signal
from scipy.io import wavfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import music_esther as me                                                  # noqa: E402  (shared library, unchanged)
import music_daniel as md                                                  # noqa: E402  (shared library, unchanged)
from music_esther import (Score, Ctx, mel, note, SR, XFADE, MUSIC_LUFS, SFX_PEAK_DB, DUCK_DB,  # noqa: E402
                          HARP, CELESTA, GLOCK, STRINGS, SLOW_STR, TREM_STR, PIZZ, CELLO, CBASS, CHOIR, FLUTE,
                          CLARINET, TIMPANI, TRUMPET, HORN, DRUMS, SHAKER, TRIANGLE)
from music_daniel import P, end_beats, gm_render, curve, bell, lufs_of     # noqa: E402

ROOT = me.ROOT
GA = f"{ROOT}/assets/gabriel"
TIMELINE = f"{GA}/timeline.json"
MUSIC_DIR, SFX_DIR, VOICE_DIR = f"{GA}/audio/music", f"{GA}/audio/sfx", f"{GA}/audio/voice/zh"
PREVIEW = f"{GA}/audio/preview_mix.mp3"
DOC = f"{ROOT}/docs/gabriel/MUSIC.md"
STRETCH = 0.30                 # every cue survives its section being stretched by at least this much (re-timing)
VAMP_MIN_SEC = 4.0             # a loop section is at least this long
VAMP_REL_DB = -3.0             # loop section loudness relative to the cue's composed span
TMP_PREFIX = "music_gabriel_"
R = lambda: me.RNG

# a longer, warmer hall than the other packs' (added to this process's table only; nothing on disk changes)
me.IRS["heaven"] = lambda: me._ir("heaven", 3.6, 3.1, 2.6, 1.7, 0.030, 14, 7)
HALL = "heaven"


# =============================================================================================== harmony helpers
PC = {"C": 0, "C#": 1, "Db": 1, "D": 2, "Eb": 3, "E": 4, "F": 5, "F#": 6, "G": 7, "Ab": 8, "A": 9, "Bb": 10, "B": 11}
QUAL = {"": (0, 4, 7), "m": (0, 3, 7), "sus": (0, 5, 7), "7": (4, 7, 10), "add9": (2, 4, 7)}


def parse(name):
    m = re.match(r"^([A-G][#b]?)(m|sus|7|add9)?(?:/([A-G][#b]?))?$", name); assert m, name
    root = PC[m.group(1)]
    return root, [(root + i) % 12 for i in QUAL[m.group(2) or ""]], PC[m.group(3)] if m.group(3) else root


def near(pc, centre):
    """The midi note of pitch class `pc` nearest to `centre`."""
    return min((12 * o + pc for o in range(1, 9)), key=lambda p: abs(p - centre))


def voices(name, centre=64):
    """Close three-part voicing of a chord around `centre` (so chords move by the smallest steps)."""
    return sorted(near(pc, centre) for pc in parse(name)[1])


def bass(name, lo=38):
    """The chord's bass note, in the octave starting at `lo` (D2)."""
    b = parse(name)[2]; return lo + (b - lo) % 12


def hz(p): return 440.0 * 2 ** ((note(p) - 69) / 12)


# =============================================================================================== the Gabriel theme
# D major, 4/4. Bars 1-2: the herald call (A up a fourth to D, up a fifth to A, one step higher to B) and its
# settling; 3-4 the answer coming down to the dominant; 5-6 the call again, this time climbing B-C#-D to the high
# tonic over IV-vi; 7 a rising turn; 8 home.
THEME = {
    1: [("A4", 1.5), ("D5", .5), ("A5", 2)],
    2: [("B5", 1), ("A5", 1), ("F#5", 2)],
    3: [("G5", 1.5), ("F#5", .5), ("E5", 1), ("D5", 1)],
    4: [("E5", 3), (None, 1)],
    5: [("A4", 1.5), ("D5", .5), ("A5", 2)],
    6: [("B5", 1.5), ("C#6", .5), ("D6", 2)],
    7: [("B5", 1), ("G5", 1), ("A5", 1), ("C#6", 1)],
    8: [("D6", 4)],
}
HARM = {1: ["D"], 2: ["G", "D/F#"], 3: ["Em", "A"], 4: ["Asus", "A"], 5: ["D"], 6: ["G", "Bm"], 7: ["G", "A"], 8: ["D"]}
SEQ = {1: [8], 2: [1, 8], 3: [1, 6, 8], 4: [1, 2, 6, 8], 5: [1, 2, 6, 7, 8], 6: [1, 2, 5, 6, 7, 8],
       7: [1, 2, 3, 5, 6, 7, 8], 8: [1, 2, 3, 4, 5, 6, 7, 8]}
# the trumpet call (seconds from its start, length, pitch): the head of bar 1 and the climb of bar 6
CALL = [(0.00, .36, "A4"), (.36, .18, "D5"), (.54, .72, "A5"), (1.26, .27, "B5"), (1.53, .27, "C#6"), (1.80, 1.90, "D6")]
CALL_TUTTI = 1.80


def theme_seq(n):
    """Which theme bars to play in n bars (None = an intro bar before the theme); always ends on bar 8."""
    return [None] * max(0, n - 8) + SEQ[max(1, min(n, 8))]


# =============================================================================================== synth sections
_TAB = {}


def wtab(tilt, nh):
    """One band-limited period (harmonics 1..nh falling as 1/k^tilt), 2048 points + a wrap point."""
    key = (round(tilt, 2), nh)
    if key not in _TAB:
        x = np.arange(2048) / 2048 * 2 * np.pi; y = np.zeros(2048)
        for k in range(1, nh + 1): y += np.sin(k * x) / k ** tilt
        y /= np.max(np.abs(y)); _TAB[key] = np.r_[y, y[0]]
    return _TAB[key]


def osc(ph, tab):
    idx = (ph % 1.0) * 2048; i = idx.astype(np.int64); fr = idx - i
    return tab[i] * (1 - fr) + tab[i + 1] * fr


def ar_env(m, n_on, a, r):
    """Raised-cosine attack `a` s, hold until n_on samples, raised-cosine release `r` s."""
    t = np.arange(m) / SR; e = np.ones(m)
    k = t < a; e[k] = .5 - .5 * np.cos(np.pi * t[k] / a)
    t1 = n_on / SR; k = t >= t1; e[k] *= np.clip(.5 + .5 * np.cos(np.pi * np.clip((t[k] - t1) / r, 0, 1)), 0, 1)
    return e


def wander(m, rng, rate_hz):
    k = max(2, int(m / SR * rate_hz) + 2)
    return np.interp(np.linspace(0, k - 1, m), np.arange(k), rng.uniform(-1, 1, k))


def ensemble(notes, n, rng, players=5, tilt=1.1, attack=.18, release=.35, detune=7.0, vib=(5.8, .004), top_hz=6500):
    """Several players per note: own detune (cents), slow pitch wander, delayed vibrato, slightly different bowing."""
    y = np.zeros(n)
    for t0, t1, p, vel in notes:
        f = 440.0 * 2 ** ((p - 69) / 12); n_on = int((t1 - t0) * SR); m = n_on + int(release * SR) + 1
        tab = wtab(tilt, max(1, min(48, int(top_hz / f)))); t = np.arange(m) / SR; seg = np.zeros(m)
        for _ in range(players):
            det = 2 ** (rng.normal(0, detune) / 1200)
            v = vib[1] * rng.uniform(.6, 1.2) * np.clip((t - rng.uniform(.18, .4)) / .45, 0, 1) \
                * np.sin(2 * np.pi * vib[0] * rng.uniform(.92, 1.08) * t + rng.uniform(0, 6.28))
            fc = f * det * (1 + v + .0015 * wander(m, rng, 1.5))
            ph = rng.uniform() + np.cumsum(fc) / SR
            seg += osc(ph, tab) * ar_env(m, n_on, attack * rng.uniform(.75, 1.35), release) * (1 + .12 * wander(m, rng, 3))
        me.place(y, seg * (vel / 100.0) ** 1.4 / math.sqrt(players), t0)
    return y


def peaks(x, spec):
    """Parallel resonances: spec = [(hz, bandwidth_hz, gain_db)], each a unity-gain peak filter."""
    y = np.zeros(len(x))
    for f, bw, g in spec:
        b, a = signal.iirpeak(f, f / bw, fs=SR); y += 10 ** (g / 20) * signal.lfilter(b, a, x)
    return y


VOWEL = {"ah": ([700, 1150, 2600, 3300], (0, -4, -8, -12)), "o": ([480, 850, 2500, 3250], (0, -6, -13, -17)),
         "oo": ([340, 780, 2350, 3200], (0, -9, -18, -22))}


def syn_choir(notes, n, rng, vowel="ah", human=True, **kw):
    """A choir pad: men (below B3) and women through their own formant banks; many voices blur the formants a little."""
    out = np.zeros(n)
    for women in (False, True):
        ns = [x for x in notes if (x[2] >= 59) == women]
        if not ns: continue
        src = ensemble(ns, n, rng, players=6, tilt=1.15, attack=kw.get("attack", .32), release=.5, detune=9.0,
                       vib=(5.4 if women else 5.0, .0055))
        lvl = me.lp(np.abs(src), 12)
        src = src + .05 * rng.standard_normal(n) * lvl                      # breath, following the singing
        F, G = VOWEL[vowel]; sc = 1.17 if women else 1.0
        y = peaks(src, [(F[i] * sc, (130, 170, 260, 340)[i] * sc, G[i]) for i in range(4)])
        y += .22 * me.lp(src, 950 if women else 600)                         # the fundamental stays under high notes
        out += me.lp(y, 7000) * (1.0 if women else 1.25)
    return me.hp(out, 85) * 1.6


def syn_strings(notes, n, rng, **kw):
    """A string ensemble: 6 desks per note, bowed attack, body resonances, a breath of bow noise."""
    src = ensemble(notes, n, rng, players=6, tilt=kw.get("tilt", 1.08), attack=kw.get("attack", .16),
                   release=kw.get("release", .32), detune=6.0, vib=(5.9, .0038))
    src = src + .012 * me.bp(rng.standard_normal(n), 1500, 6000) * me.lp(np.abs(src), 15)
    y = src + peaks(src, [(290, 160, -4), (480, 220, -6), (1150, 500, -5), (2700, 900, -3)])
    return me.lp(y, kw.get("bright", 5800)) * .55


def syn_brass(notes, n, rng, index=1.6, players=3, **kw):
    """A warm FM brass section (carrier : modulator 1 : 1, the brightness follows the breath), with a small scoop."""
    y = np.zeros(n)
    for t0, t1, p, vel in notes:
        f = 440.0 * 2 ** ((p - 69) / 12); n_on = int((t1 - t0) * SR); m = n_on + int(.16 * SR) + 1
        t = np.arange(m) / SR; seg = np.zeros(m); vs = (vel / 100.0)
        for _ in range(players):
            e = ar_env(m, n_on, rng.uniform(.045, .075), .14) * (.82 + .18 * np.exp(-t / .35))
            scoop = 2 ** (-rng.uniform(15, 35) * np.exp(-t / .03) / 1200)
            v = .0035 * np.clip((t - .45) / .5, 0, 1) * np.sin(2 * np.pi * 5.3 * t + rng.uniform(0, 6.28))
            ph = 2 * np.pi * (rng.uniform() + np.cumsum(f * 2 ** (rng.normal(0, 4) / 1200) * scoop * (1 + v)) / SR)
            seg += np.sin(ph + index * vs * (.3 + .7 * e ** 1.5) * np.sin(ph)) * e
        me.place(y, seg * vs ** 1.3 / math.sqrt(players), t0)
    return y * .5


SYN = {"choir": syn_choir, "strings": syn_strings, "brass": syn_brass}
# level of each synth section against the DLS stems (FluidSynth renders those at -40..-60 dB rms), measured with --stems
SYN_TRIM = {"choir": -29.0, "strings": -26.0, "brass": -18.0}


class SynthPart(me.Part):
    """A stem that is synthesised here instead of played by the DLS bank; takes the same notes and CC 11 swells."""

    def __init__(self, score, name, kind, gain_db=0.0, send=0.5, lp=None, hp=None, human=0.010, vel_sd=3.0, **opt):
        super().__init__(score, name, 0, gain_db, send, lp, hp, human, vel_sd)
        self.kind, self.opt = kind, opt

    def render(self):
        n = int((self.s.secs + 3) * SR)
        if not self.notes: return np.zeros(n, np.float32)
        rng = np.random.default_rng(zlib.crc32(f"gabriel/{self.s.c.name}/{self.name}".encode()))
        y = SYN[self.kind](self.notes, n, rng, **self.opt)
        cc = sorted((t, v) for t, num, v in self.ccs if num == 11)
        if cc:
            e = np.interp(np.arange(n) / SR, [t for t, _ in cc], [v for _, v in cc]) / 110.0
            y = y * me.lp(e, 12) ** 1.6
        if self.hp: y = me.hp(y, self.hp)
        if self.lp: y = me.lp(y, self.lp)
        return (y * self.gain * 10 ** (SYN_TRIM[self.kind] / 20)).astype(np.float32)


class AudioPart(me.Part):
    """A stem of ready-made sounds (the cymbal swell) placed at times in the cue."""

    def __init__(self, score, name, gain_db=0.0, send=0.4):
        super().__init__(score, name, 0, gain_db, send); self.clips = []

    def put(self, sec, x): self.clips.append((sec, x)); self.notes.append([sec, sec + len(x) / SR, 0, 1])

    def render(self):
        y = np.zeros(int((self.s.secs + 3) * SR))
        for sec, x in self.clips: me.place(y, x, max(0.0, sec))
        return (y * self.gain * 10 ** (-26 / 20)).astype(np.float32)


def SP(s, name, kind, *a, **kw):
    p = SynthPart(s, name, kind, *a, **kw); s.parts.append(p); return p


def cym_swell(rise, fall, rng):
    """A soft suspended-cymbal swell: a cloud of high inharmonic partials and air; peaks at `rise` s, never a crash."""
    n = int((rise + fall) * SR); t = np.arange(n) / SR; y = np.zeros(n)
    for f in rng.uniform(2600, 10500, 70):
        y += np.sin(2 * np.pi * f * t + rng.uniform(0, 6.28)) * (1 + .7 * wander(n, rng, 6)) * (3000 / f) ** .6
    y = y / 70 * 4 + .25 * me.hp(rng.standard_normal(n), 5000)
    e = np.where(t < rise, (t / rise) ** 2.4, np.exp(-(t - rise) / (fall / 3.5)))
    k = int(.05 * SR); e[-k:] *= np.linspace(1, 0, k)
    return me.lp(y * e, 11000) * .5


# =============================================================================================== writing helpers
D_SCALE = {2, 4, 6, 7, 9, 11, 1}
D_PENT = {2, 4, 6, 9, 11}


def gliss(harp, b0, beats, lo, hi, vel=44, down=False, pcs=D_PENT, ring=2.0):
    ps = [m for m in range(note(lo), note(hi) + 1) if m % 12 in pcs]
    if down: ps = ps[::-1]
    for i, m in enumerate(ps):
        harp.add(b0 + beats * i / len(ps), m, ring, vel + 14 * (i / len(ps)) * (-1 if down else 1))


def roll(timp, b0, b1, pitch, v0, v1, rate_hz=15.0):
    step = timp.s.beat(1.0 / rate_hz); k = max(1, int((b1 - b0) / step))
    for i in range(k): timp.add(b0 + i * step, pitch, step * 1.5, v0 + (v1 - v0) * (i / k) ** 1.5)


def lay(b, name, dur, choir=None, strs=None, dstr=None, cb=None, vc=None, horn=None, cv=54, sv=52, top=True):
    """One chord across the pad sections, in close voicing with the smallest movement from the chord before."""
    mid = voices(name, 64); bs = bass(name)
    if choir is not None:
        choir.chord(b, [bs + 12, near(parse(name)[1][2], 55)], dur + .3, cv - 4)          # men
        choir.chord(b, mid + ([mid[-1] + 12] if top else []), dur + .3, cv)                # women
    if strs is not None: strs.chord(b, mid + [mid[0] + 12] + ([mid[1] + 12] if top else []), dur + .25, sv)
    if dstr is not None: dstr.chord(b, mid, dur + .25, sv - 6)
    if vc is not None: vc.add(b, bs + 12, dur + .1, sv - 2)
    if cb is not None: cb.add(b, bs, dur + .1, sv)
    if horn is not None: horn.chord(b, voices(name, 57), dur + .1, sv - 4)


def harp_arp(harp, b, name, beats, vel=46, step=.5, centre=64):
    ps = voices(name, centre); ps = [bass(name) + 12] + ps + [ps[0] + 12]
    for j in range(int(round(beats / step))):
        harp.add(b + j * step, ps[[0, 1, 2, 3, 4, 3, 2, 1][j % 8]], 1.6, vel + (8 if j == 0 else 0))


# =============================================================================================== cues
def cue_heaven(c):
    """The city of light: a choir 'ah' pad and slow strings on D, a harp shimmer falling like light, celesta
    glints; in the last two bars the horns hint the Gabriel call (A-D-A, then B-A-F#), an octave down, far away."""
    s = Score(c, 63, 4); n = s.bars; E = end_beats(s)
    choir = SP(s, "choir", "choir", -3, .75, vowel="ah", attack=.5)
    strs = SP(s, "strings", "strings", -7, .65, lp=4200, attack=.4)
    dstr = P(s, "slow strings", SLOW_STR, -11, .6, lp=5000)
    cb = P(s, "contrabass", CBASS, -11, .35, lp=900)
    harp = P(s, "harp", HARP, -2, .65, human=.006)
    cel = P(s, "celesta", CELESTA, -1, .75)
    horn = P(s, "horns", HORN, -7, .65, lp=3200)
    shorn = SP(s, "horn section", "brass", -13, .65, lp=2400, index=1.3)
    h0 = max(1, n - 2) if n >= 2 else n
    for p_ in (choir, strs): p_.ramp(0, 3, 11, 45, 100, .8)
    for bar in range(n):
        b = bar * 4; k = bar - h0 + 1 if bar >= h0 else None; final = bar == n - 1
        hs = HARM[k] if k else (["D"] if bar % 2 == 0 else ["G/D"])
        for i, h in enumerate(hs):
            hb = b + i * 4 / len(hs); d = (E - hb) if final and i == len(hs) - 1 else 4 / len(hs)
            lay(hb, h, d, choir, strs, dstr, cb)
            ps = voices(h, 78)                                                    # shimmer: falling triplets up high
            for j in range(int(round(min(d, 4 / len(hs)) * 3))):
                harp.add(hb + j / 3, ps[[2, 1, 0, 1][j % 4]] + (12 if j % 8 < 4 else 0), 1.2, 38 + (6 if j % 3 == 0 else 0))
        if k:
            for p_, v in ((horn, 62), (shorn, 58)): mel(p_, b, THEME[k], v, legato=.98, shift=-12)
        cel.add(b + 1.5, ["A6", "F#6", "D7"][bar % 3], 2, 36); cel.add(b + 3.25, ["D7", "A6", "F#6"][bar % 3], 2, 30)
    gliss(harp, 0, 2.0, "D3", "D6", 40)
    return s


def cue_descend(c):
    """Down from heaven: strings and choir swell over G - A, harp glissandi on each wing beat, a soft timpani roll
    growing; he lands on a warm D major chord (harp, soft timpani, celesta) that settles while he folds his wings."""
    s = Score(c, 72, 4); E = end_beats(s); B = s.beat
    tl_ = c.first("sfx", id="whoosh_land"); tL = (tl_ - c.t) if tl_ is not None else c.span * .66; bL = B(tL)
    choir = SP(s, "choir", "choir", -4, .75, vowel="ah", attack=.45)
    strs = SP(s, "strings", "strings", -5, .65, lp=5000, attack=.3)
    dstr = P(s, "slow strings", SLOW_STR, -10, .6, lp=5500)
    cb = P(s, "contrabass", CBASS, -9, .35, lp=900)
    harp = P(s, "harp", HARP, -4, .65, human=.006)
    cel = P(s, "celesta", CELESTA, -3, .75)
    timp = P(s, "timpani", TIMPANI, -4, .5, lp=1800)
    horn = P(s, "horns", HORN, -9, .65, lp=3000)
    half = bL * .5
    lay(0, "G", half, choir, strs, dstr, cb); lay(half, "A", bL - half, choir, strs, dstr, cb)
    for p_ in (choir, strs): p_.ramp(0, bL, 11, 42, 118, 1.3); p_.ramp(bL, bL + B(1.2), 11, 118, 92)
    flaps = [t - c.t for t in c.all("sfx", id="wing_flap")] or [tL * .1, tL * .4, tL * .7]
    for i, tf in enumerate(flaps):
        gliss(harp, B(tf), B(.75), "A3", "A6", 40 + 4 * i, down=i % 2 == 1, pcs=D_SCALE)
    roll(timp, max(0, bL - B(1.6)), bL, "A2", 26, 74)
    # the landing
    timp.add(bL, "D2", 2, 84); lay(bL, "D", E - bL, choir, strs, dstr, cb, horn=horn)
    harp.chord(bL, ["D3", "A3", "D4", "F#4", "A4", "D5", "F#5", "A5"], E - bL, 54, strum=.035)
    for i, p_ in enumerate(["A5", "D6", "F#6", "A6", "D7"]): cel.add(bL + .5 + i * .33, p_, 2, 44 - 2 * i)
    return s


def cue_gentle(c):
    """Kneeling to the child: warm strings, a celesta lullaby figure and harp; after one bar the flute sings the
    Gabriel theme softly, a cello underneath; a distant 'oh' from the choir. Rests on D. (Plays in S03 and S06.)"""
    s = Score(c, 69, 4); n = s.bars; E = end_beats(s)
    strs = SP(s, "strings", "strings", -5, .6, lp=3800, attack=.35)
    dstr = P(s, "slow strings", SLOW_STR, -13, .55, lp=4500)
    vc = P(s, "cello", CELLO, -5, .5, lp=2600)
    cb = P(s, "contrabass", CBASS, -13, .3, lp=800)
    cel = P(s, "celesta", CELESTA, -1, .65, human=.006)
    harp = P(s, "harp", HARP, -3, .55, human=.006)
    fl = P(s, "flute", FLUTE, -9, .55, human=.008)
    choir = SP(s, "choir", "choir", -9, .75, vowel="o", attack=.5)
    intro = 1 if n >= 4 else 0; seq = [None] * intro + theme_seq(n - intro)
    strs.ramp(0, 2, 11, 60, 96)
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1; hs = HARM[k] if k else ["D"]
        for i, h in enumerate(hs):
            hb = b + i * 4 / len(hs); d = (E - hb) if final and i == len(hs) - 1 else 4 / len(hs)
            lay(hb, h, d, choir if bar >= intro else None, strs, dstr, cb, vc, cv=46, sv=48, top=False)
            ps = voices(h, 76)
            for j in range(int(round(min(d, 4 / len(hs)) * 2))):
                cel.add(hb + j * .5, ps[[0, 2, 1, 2][j % 4]] + (12 if j % 4 == 3 else 0), 1.0, 48 if j % 4 == 0 else 38)
            harp.add(hb, bass(h) + 12, 3, 46); harp.chord(hb + 1, voices(h, 60), 2.5, 36, strum=.04)
        if k and not final: mel(fl, b, THEME[k], 60, legato=.98, vib=True)
        if final:
            if k: fl.add(b, THEME[k][0][0], E - b, 58); fl.vibrato(b, E - b, 30)
            for i, p_ in enumerate(["D6", "F#6", "A6", "D7"]): cel.add(b + 2 + i * .5, p_, 2, 40 - 2 * i)
    return s


S_TUNE = [[("B4", .5), ("D5", .5), ("G5", 1), ("F#5", .5), ("E5", .5), ("D5", 1)],
          [("E5", .5), ("G5", .5), ("C6", 1), ("B5", .5), ("A5", .5), ("G5", 1)],
          [("A5", 1), ("F#5", .5), ("D5", .5), ("E5", 1), ("F#5", 1)],
          [("G5", 2), ("D5", 1), (None, 1)]]
S_HARM = ["G", "C", "D", "G"]


def cue_story(c):
    """The messenger remembers: a light travelling tune in G major on clarinet, then flute, over pizzicato bass and
    off-beat violas, a quiet shaker, soft strings. When he points up to heaven (sparkle) the tune waits a bar and
    a horn plays the Gabriel call in G (D-G-D) with celesta sparks. Ends on G."""
    s = Score(c, 100, 4); n = s.bars; E = end_beats(s)
    pz = P(s, "pizz bass", PIZZ, -3, .3)
    pzv = P(s, "pizz violas", PIZZ, -4, .35)
    strs = SP(s, "strings", "strings", -15, .55, lp=3600, attack=.3)
    cl = P(s, "clarinet", CLARINET, -10, .45, human=.008)
    fl = P(s, "flute", FLUTE, -9, .5, human=.008)
    harp = P(s, "harp", HARP, -4, .5, human=.006)
    cel = P(s, "celesta", CELESTA, -3, .7)
    horn = P(s, "horn", HORN, -3, .6, lp=3200)
    shorn = SP(s, "horn section", "brass", -13, .6, lp=2400, index=1.3)
    sh = P(s, "shaker", DRUMS, -4, .2, lp=7000, human=.004)
    sp = s.at(c.first("sfx", id="sparkle"))
    hint = int(math.ceil(sp / 4 - .25)) if sp is not None else -1
    if hint >= n - 1: hint = -1
    k = 0
    for bar in range(n):
        b = bar * 4; final = bar == n - 1
        if bar == hint:
            h = "G"
            for p_, v in ((horn, 66), (shorn, 58)): mel(p_, b, [("D4", 1.5), ("G4", .5), ("D5", 2)], v, legato=.98)
            for i, p_ in enumerate(["B6", "D7", "G6", "D7"]): cel.add(b + .5 + i * .75, p_, 1.5, 44)
            harp.chord(b, ["G3", "D4", "G4", "B4", "D5"], 3.5, 50, strum=.04)
        elif final:
            h = "G"; lead = cl if (k // 4) % 2 == 0 else fl
            lead.add(b, "G5", E - b, 62); harp.chord(b, ["G2", "D3", "G3", "B3", "D4", "G4"], E - b, 52, strum=.04)
            cel.add(b + 1, "G6", 2, 38); cel.add(b + 1.5, "D7", 2, 34)
        else:
            h = S_HARM[k % 4]; lead = cl if (k // 4) % 2 == 0 else fl
            mel(lead, b, S_TUNE[k % 4], 66, legato=.92, vib=True); k += 1
            if bar % 2 == 0: harp.chord(b, voices(h, 62), 2, 40, strum=.03)
        bs = bass(h, 43)
        pz.add(b, bs, .5, 72); pz.add(b + 2, bs + 7 if not final else bs, .5, 60)
        if not final:
            pz.add(b + 3.5, bs + 7, .4, 50)
            for q in range(4):
                pzv.chord(b + q + .5, voices(h, 62)[1:], .25, 42)
                sh.add(b + q + .5, SHAKER, .2, 56); sh.add(b + q, SHAKER, .2, 38)
        strs.chord(b, voices(h, 62) + [voices(h, 62)[0] + 12], (E - b if final else 4) + .25, 46)
    return s


def cue_fanfare(c):
    """The best news of all. Under his line: a held breath on the dominant (tremolo strings, timpani pedal and roll,
    a harp run). Then the trumpet effect plays the Gabriel call alone over a quiet D; as it reaches its high D the
    whole orchestra answers: choir 'ah', strings, trumpets, a soft cymbal swell, timpani, bells, and the horns
    sing the call back underneath (A-D-A, B-A-F#). Joyful, not military. Built on the times of `trumpet_call`."""
    s = Score(c, 80, 4); E = end_beats(s); B = s.beat
    tc = c.first("sfx", id="trumpet_call"); t0 = (tc - c.t) if tc is not None else c.span * .45
    b0 = B(t0); bt = B(t0 + CALL_TUTTI)
    choir = SP(s, "choir", "choir", -2, .75, vowel="ah", attack=.25)
    strs = SP(s, "strings", "strings", -4, .65, lp=6000, attack=.2)
    trem = P(s, "tremolo strings", TREM_STR, 0, .55, lp=5000)
    dstr = P(s, "strings dls", STRINGS, -9, .6, lp=6500)
    cb = P(s, "contrabass", CBASS, -8, .35, lp=900)
    harp = P(s, "harp", HARP, -5, .6, human=.006)
    timp = P(s, "timpani", TIMPANI, -2, .5, lp=1800)
    tpt = P(s, "trumpets", TRUMPET, -4, .55, lp=7000)
    stpt = SP(s, "trumpet section", "brass", -14, .55, lp=5200, index=2.6)
    horn = P(s, "horns", HORN, -5, .6, lp=3600)
    shorn = SP(s, "horn section", "brass", -10, .6, lp=2800, index=1.7)
    glock = P(s, "glockenspiel", GLOCK, -4, .7)
    cym = AudioPart(s, "cymbal swell", -15, .5)
    # the held breath
    trem.chord(0, ["A3", "D4", "E4"], b0 * .6, 46); trem.chord(b0 * .6, ["A3", "E4", "G4"], b0 * .4 - .05, 50)
    trem.ramp(0, b0, 11, 48, 112, 1.4)
    strs.chord(0, ["A3", "E4", "A4"], b0, 44); strs.ramp(0, b0, 11, 40, 100, 1.4)
    cb.add(0, "A1", b0, 50); timp.add(0, "A2", 2, 58)
    if b0 > 5: timp.add(b0 * .5, "A2", 2, 54)
    roll(timp, max(0, b0 - B(1.8)), b0, "A2", 28, 80)
    gliss(harp, max(0, b0 - B(.9)), B(.85), "A2", "A5", 44, pcs=D_SCALE)
    # the call (the trumpet is the effect; the orchestra holds a quiet D under it)
    timp.add(b0, "D2", 2, 92); cb.add(b0, "D2", bt - b0, 54)
    strs.chord(b0, ["D3", "A3", "D4", "F#4"], bt - b0 + .2, 50); strs.ramp(b0, b0 + .1, 11, 100, 70); strs.ramp(b0 + .2, bt, 11, 70, 112)
    harp.chord(b0, ["D2", "A2", "D3", "F#3", "A3", "D4"], 3, 56, strum=.03)
    # the answer
    rng = np.random.default_rng(11)
    cym.put(t0 + CALL_TUTTI - 1.3, cym_swell(1.3, 2.6, rng))
    roll(timp, max(b0 + .2, bt - B(.55)), bt, "A2", 50, 96); timp.add(bt, "D2", 3, 112)
    gliss(harp, bt - B(.5), B(.45), "D3", "D6", 50, pcs=D_SCALE)
    secs_h = [(0.0, .36, "A3"), (.36, .18, "D4"), (.54, 1.2, "A4"), (1.74, .6, "B4"), (2.34, .6, "A4"), (2.94, None, "F#4")]
    for dt, du, p_ in secs_h:
        hb = bt + B(dt); d = B(du) if du else max(1.0, E - hb)
        for q_, v in ((horn, 96), (shorn, 90)):
            q_.add(hb, p_, d * .97, v); q_.add(hb, note(p_) - 12, d * .97, v - 14)
    plan = [("D", 0.0, 1.74), ("G", 1.74, .6), ("D/F#", 2.34, .6), ("D", 2.94, None)]
    for h, dt, du in plan:
        hb = bt + B(dt); d = B(du) if du else max(1.0, E - hb)
        lay(hb, h, d, choir, strs, dstr, cb, cv=74, sv=70)
        if dt: timp.add(hb, {"G": "G2", "D/F#": "A2", "D": "D2"}[h], 2, 84 if h == "D" else 70)
    for p_ in (choir, strs): p_.ramp(bt, bt + .2, 11, 96, 122)
    for p_, v in (("F#5", 92), ("A5", 96)):
        tpt.add(bt, p_, B(1.9), v); stpt.add(bt, p_, B(1.9), v); stpt.add(bt, "D5", B(1.9), v - 8)
    for i, p_ in enumerate(["D6", "F#6", "A6", "D7", "A6", "F#6", "D7"]): glock.add(bt + i * .25, p_, 1.5, 62 - 3 * i)
    harp.chord(bt, ["D3", "A3", "D4", "F#4", "A4", "D5", "F#5", "A5", "D6"], 4, 66, strum=.025)
    return s


def cue_finale(c):
    """Colour me in, and home: the full statement of the Gabriel theme in D major. Violins (synth ensemble + DLS)
    carry the tune, trumpets join for the climb, horns and choir fill the harmony, timpani and harp underneath, a
    soft cymbal swell into the climb and into the last chord: a bright held D major with bells and a harp roll."""
    s = Score(c, 84, 4); n = s.bars; E = end_beats(s)
    seq = theme_seq(n)
    vln = SP(s, "violins", "strings", -3, .65, lp=6200, attack=.14)
    dvln = P(s, "violins dls", STRINGS, -6, .6, lp=7000)
    strs = SP(s, "strings", "strings", -8, .6, lp=4200, attack=.25)
    vc = P(s, "cello", CELLO, -8, .5, lp=2800)
    cb = P(s, "contrabass", CBASS, -8, .35, lp=900)
    choir = SP(s, "choir", "choir", -4, .75, vowel="ah", attack=.25)
    dchoir = P(s, "choir dls", CHOIR, -13, .7, lp=5000)
    tpt = P(s, "trumpets", TRUMPET, -9, .55, lp=7000)
    stpt = SP(s, "trumpet section", "brass", -15, .55, lp=5200, index=2.6)
    horn = P(s, "horns", HORN, -9, .6, lp=3400)
    shorn = SP(s, "horn section", "brass", -11, .6, lp=2800, index=1.6)
    harp = P(s, "harp", HARP, -6, .6, human=.006)
    timp = P(s, "timpani", TIMPANI, -3, .5, lp=1800)
    glock = P(s, "glockenspiel", GLOCK, -5, .7)
    cym = AudioPart(s, "cymbal swell", -16, .5)
    rng = np.random.default_rng(23)
    climb = next((i for i, k in enumerate(seq) if k == 6), None)
    brass_from = climb if climb is not None else max(0, n - 2)
    for p_ in (choir, strs): p_.ramp(0, 2, 11, 70, 104)
    for bar, k in enumerate(seq):
        b = bar * 4; final = bar == n - 1; hs = HARM[k] if k else ["D"]; big = bar >= brass_from
        for i, h in enumerate(hs):
            hb = b + i * 4 / len(hs); d = (E - hb) if final and i == len(hs) - 1 else 4 / len(hs)
            lay(hb, h, d, choir, strs, None, cb, vc, cv=70 if big else 58, sv=62 if big else 54)
            dchoir.chord(hb, voices(h, 64), d + .2, 60)
            for q_, v in ((horn, 80 if big else 64), (shorn, 74 if big else 58)): q_.chord(hb, voices(h, 57), d * .98, v)
            if not final: harp_arp(harp, hb, h, 4 / len(hs), 50)
            tn = {2: "D2", 7: "G2", 9: "A2"}.get(parse(h)[2])
            if tn and (i == 0 or big): timp.add(hb, tn, 2, (96 if big else 70) if i == 0 else 78)
        if k is None:
            gliss(harp, b + 2, 1.8, "A3", "A6", 44, pcs=D_SCALE)
        elif not final:
            for q_, v in ((vln, 84 if big else 74), (dvln, 80 if big else 70)):
                mel(q_, b, THEME[k], v, legato=.99, vib=True); mel(q_, b, THEME[k], v - 12, legato=.99, shift=-12)
            if big:
                for q_, v in ((tpt, 92), (stpt, 88)): mel(q_, b, THEME[k], v, legato=.96)
        if bar + 1 < n and (bar + 1 == climb or bar + 1 == n - 1):
            cym.put(s.sec(b + 4) - 1.5, cym_swell(1.5, 2.8 if bar + 1 == n - 1 else 1.8, rng) * (1.0 if bar + 1 == n - 1 else .7))
            roll(timp, b + 2.5, b + 4, "A2", 40, 92)
        if final:
            d = E - b
            for q_, v in ((vln, 88), (dvln, 84)): q_.chord(b, ["D5", "A5", "D6"], d, v)
            for q_, v in ((tpt, 96), (stpt, 90)): q_.chord(b, ["F#5", "A5", "D6"] if q_ is stpt else ["A5", "D6"], d * .98, v)
            timp.add(b, "D2", 4, 110)
            harp.chord(b, ["D2", "A2", "D3", "F#3", "A3", "D4", "F#4", "A4", "D5", "F#5", "A5", "D6"], d, 68, strum=.03)
            for i, p_ in enumerate(["D6", "F#6", "A6", "D7", "F#7", "A6", "D7"]): glock.add(b + i * .33, p_, 2, 64 - 3 * i)
            gliss(harp, b + 1.5, 1.2, "D4", "D7", 40)
    return s


# ----------------------------------------------------------------------------------------------- loop sections
VAMP = {"heaven": ("D", "choir"), "descend": ("D", "choir"), "gentle": ("D", "bells"), "story": ("G", "travel"),
        "fanfare": ("D", "choir"), "finale": ("D", "bells")}


def add_vamp(s, chord_name, style):
    """After the cadence: repeats of >= VAMP_MIN_SEC (whole bars) on the final chord, in this score's own colours
    (synth strings and a far choir 'oh', harp, celesta). The file tiles one rendered repeat, see render_cue."""
    bpb = s.bpb; nb = max(1, math.ceil(VAMP_MIN_SEC / s.sec(bpb) - 1e-6)); Lb = nb * bpb; L = s.sec(Lb)
    reps = max(4, math.ceil((STRETCH * s.span + XFADE + 2.5) / L) + 2)
    v = dict(human=0.0, vel_sd=0.0)
    strs = SP(s, "vamp strings", "strings", -10, .6, lp=3400, attack=.3, **v)
    cb = P(s, "vamp bass", CBASS, -11, .3, lp=900, **v)
    harp = P(s, "vamp harp", HARP, -8, .55, **v)
    parts = [strs, cb, harp]; choir = cel = pz = None
    if style in ("choir", "bells"): choir = SP(s, "vamp choir", "choir", -9, .75, vowel="o", attack=.5, **v); parts.append(choir)
    if style in ("choir", "bells"): cel = P(s, "vamp celesta", CELESTA, -5, .7, **v); parts.append(cel)
    if style == "travel": pz = P(s, "vamp pizz", PIZZ, -7, .3, **v); parts.append(pz)
    for p_ in parts: p_.vamp = True
    mid = voices(chord_name, 64); bs = bass(chord_name); b0 = s.bars * bpb
    for r in range(reps):
        b = b0 + r * Lb
        strs.chord(b, mid + [mid[0] + 12], Lb + .3, 46); cb.add(b, bs, Lb + .2, 46)
        if choir is not None: choir.chord(b, [bs + 12] + mid, Lb + .3, 46)
        for bar in range(nb):
            bb = b + bar * bpb
            if style == "travel":
                pz.add(bb, bs + 12, .5, 56); pz.add(bb + 2, bs + 19, .5, 46)
                for j in range(4): harp.add(bb + j, (mid + [mid[0] + 12])[[0, 2, 1, 3][j]], 1.6, 42)
            else:
                ps = [bs + 12] + mid + [mid[0] + 12]
                for j in range(bpb * 2): harp.add(bb + j * .5, ps[[0, 1, 2, 3, 4, 3, 2, 1][j % 8]], 1.6, 44 if j else 50)
        if cel is not None: cel.add(b + bpb - 1, mid[-1] + 24, 2, 34); cel.add(b + bpb, mid[0] + 24, 2, 30)
    s.secs = s.span + reps * L + 2.5
    s.vamp = dict(start=s.span, secs=L, reps=reps, bars=nb, chord=chord_name, style=style)


def render_split(s):
    """The cue and its loop section, rendered separately (each with its own hall send)."""
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=8) as ex: stems = list(ex.map(lambda p: p.render(), s.parts))
    n = max(len(x) for x in stems); out = {}
    for key in (False, True):
        dry = np.zeros(n); bus = np.zeros(n)
        for p_, x in zip(s.parts, stems):
            if getattr(p_, "vamp", False) != key: continue
            dry[:len(x)] += x; bus[:len(x)] += x * p_.send
            if me.STEM_REPORT: print(f"    stem {p_.name:22s} rms {20 * np.log10(np.sqrt(np.mean(x ** 2)) + 1e-9):6.1f} dB")
        out[key] = dry + signal.fftconvolve(bus, me.IRS[HALL]())[:n] * .9
    return out[False], out[True]


def clean_tmp():
    root = tempfile.tempdir
    if root and os.path.basename(root).startswith(TMP_PREFIX):
        for d in os.listdir(root): shutil.rmtree(os.path.join(root, d), ignore_errors=True)


MUSIC = {"heaven": cue_heaven, "descend": cue_descend, "gentle": cue_gentle, "story": cue_story,
         "fanfare": cue_fanfare, "finale": cue_finale}
KEYS = {"heaven": "D major", "descend": "G - A - D major", "gentle": "D major", "story": "G major",
        "fanfare": "A (dominant) - D major", "finale": "D major"}
CUE_NOTES = {
    "heaven": "Choir 'ah' pad (formant choir) and slow strings on D / G over D, harp shimmer in falling triplets, celesta glints; the horns hint the Gabriel call (A-D-A, B-A-F#) an octave down in the last two bars.",
    "descend": "Strings and choir swell over G then A, a harp glissando on every wing beat, soft timpani roll growing; on the landing a warm D major (harp chord, soft timpani, horns, celesta run) that settles while he folds his wings.",
    "gentle": "Warm string ensemble, celesta lullaby figure, harp; after one bar the flute sings the Gabriel theme softly over a cello line, a far choir 'oh'; rests on D. Plays twice (S03, S06).",
    "story": "Light travelling tune in G on clarinet, then flute; pizzicato bass, off-beat violas, quiet shaker, soft strings; at the point-up sparkle the tune waits a bar and a horn plays the Gabriel call in G (D-G-D) with celesta sparks; ends on G.",
    "fanfare": "Held breath on the dominant under the line (tremolo strings, timpani pedal and roll, harp run); the trumpet effect plays the call over a quiet D; on its high D the orchestra answers: choir 'ah', strings, trumpets, soft cymbal swell, timpani, glockenspiel, the horns singing the call back (A-D-A, B-A-F#).",
    "finale": "Full Gabriel theme in D major: violins (ensemble + DLS, in octaves), trumpets from the climb (B-C#-D over IV-vi), horns and choir on the harmony, timpani, harp; cymbal swell and timpani roll into the last chord: a bright held D major with glockenspiel and a harp roll.",
}


# =============================================================================================== sfx
def noise(n): return R().standard_normal(n)


def sweep_noise(n, pts, width_oct):
    """Noise through a band that moves: pts = [(sec, centre Hz)], gaussian in log-frequency, `width_oct` wide."""
    f, tt, Z = signal.stft(noise(n), SR, nperseg=1024, noverlap=768, boundary="even")
    fc = np.interp(tt, [p[0] for p in pts], [p[1] for p in pts])
    mask = np.exp(-.5 * (np.log2((f[:, None] + 1.0) / fc[None, :]) / width_oct) ** 2)
    _, y = signal.istft(Z * mask, SR, nperseg=1024, noverlap=768, boundary=True)
    y = np.r_[y, np.zeros(max(0, n - len(y)))][:n]
    return y / (np.std(y) + 1e-9)


def sfx_wing_flap(ctx):
    """One beat of huge soft wings: a quiet lift (air sliding off the feathers), then the long down-stroke, a wide
    low 'whoomf' of pushed air (most of the energy under 300 Hz) with a soft pressure thump and a trace of feather
    hiss. Slow (the stroke lasts 0.6 s) and airy, nothing chirpy or fluttering: an archangel, not a bird."""
    secs = 1.35; n = int(secs * SR); t = np.arange(n) / SR
    up = sweep_noise(n, [(0, 500), (.3, 900), (secs, 900)], .9) * curve(n, [(0, 0), (.14, 1), (.3, .25), (.38, 0), (secs, 0)]) ** 1.5 * .16
    body = sweep_noise(n, [(0, 130), (.36, 130), (.55, 330), (.8, 180), (secs, 95)], 1.0)
    body *= curve(n, [(0, 0), (.34, 0), (.44, .35), (.58, 1), (.74, .6), (1.0, .18), (1.25, 0), (secs, 0)]) ** 1.3
    low = me.lp(noise(n), 110) * 9 * curve(n, [(0, 0), (.4, 0), (.56, 1), (.72, .45), (1.0, .08), (1.2, 0), (secs, 0)]) ** 1.4
    f = np.interp(t, [0, .45, .62, 1.0, secs], [52, 52, 58, 40, 36])
    thump = np.sin(2 * np.pi * np.cumsum(f) / SR) * curve(n, [(0, 0), (.44, 0), (.56, 1), (.7, .4), (.95, 0), (secs, 0)]) ** 2 * .5
    hiss = me.bp(noise(n), 2200, 6500) * (1 + .5 * me.smooth_rand(n, 22)) \
        * curve(n, [(0, 0), (.38, 0), (.52, 1), (.7, .4), (1.0, 0), (secs, 0)]) ** 1.5 * .035
    x = up * .8 + body * .7 + low * .75 + thump * 1.2 + hiss
    return me.fit(me.room(me.lp(x, 7000), "hall", .16), secs, fade_in=.01, fade_out=.25)


def grain(secs, lo, hi, level):
    n = int(secs * SR); return me.bp(noise(n), lo, hi) * np.hanning(n) ** 1.5 * level


def sfx_wing_fold(ctx):
    """The wings folding behind his back: a soft falling sweep of air, a run of feather rustles getting lower and
    quieter, a pillowy 'fwup' as they settle, then the little shake of the feathers (four tiny rustles)."""
    secs = 1.25; n = int(secs * SR); x = np.zeros(n)
    x += sweep_noise(n, [(0, 1400), (.5, 420), (secs, 300)], .9) * curve(n, [(0, 0), (.1, 1), (.4, .5), (.62, 0), (secs, 0)]) ** 1.4 * .22
    for i in range(7):
        c0 = 3200 - 300 * i
        me.place(x, grain(R().uniform(.07, .12), c0 * .55, c0 * 1.5, .5 * (1 - .09 * i)), .05 + i * .075 + R().normal(0, .008))
    k = int(.3 * SR); fw = me.lp(noise(k), 220) * 6 * (np.hanning(k) ** 2); me.place(x, fw * .5, .5)
    for i in range(4):
        me.place(x, grain(.05, 2400, 7000, .3 * (1 - .15 * i)), .86 + i * .07 + R().normal(0, .005))
    return me.fit(me.room(me.lp(x, 8000), "room", .12), secs, fade_in=.005, fade_out=.2)


def sfx_whoosh_land(ctx):
    """Landing on the clouds: a whoosh of air falling in pitch as the wings flare, a deep soft 'pomf' (a pillow, not
    a stomp: 80 -> 45 Hz, no click), and a puff of cloud rolling outwards."""
    secs = 1.7; n = int(secs * SR); t = np.arange(n) / SR
    wh = sweep_noise(n, [(0, 1300), (.5, 200), (.7, 140), (secs, 140)], 1.0) * curve(n, [(0, 0), (.3, .6), (.5, 1), (.62, .25), (.8, 0), (secs, 0)]) ** 1.4
    f = np.interp(t, [0, .5, .56, .9, secs], [80, 80, 72, 46, 44])
    th = np.sin(2 * np.pi * np.cumsum(f) / SR) * curve(n, [(0, 0), (.49, 0), (.535, 1), (.66, .5), (.95, .08), (1.15, 0), (secs, 0)]) ** 1.5
    pillow = me.lp(noise(n), 170) * 8 * curve(n, [(0, 0), (.5, 0), (.55, 1), (.72, .3), (1.0, 0), (secs, 0)]) ** 1.5
    puff = sweep_noise(n, [(0, 500), (.55, 500), (.8, 900), (secs, 500)], 1.1) * curve(n, [(0, 0), (.52, 0), (.66, 1), (1.0, .35), (1.5, 0), (secs, 0)]) ** 1.3
    x = wh * .45 + th * 1.0 + pillow * .7 + puff * .24
    return me.fit(me.room(me.lp(x, 7500), "hall", .18), secs, fade_in=.01, fade_out=.3)


def sfx_trumpet_call(ctx):
    """The Gabriel theme on a bright herald trumpet: A-D-A (up a fourth, up a fifth), then the climb B-C#-D to a
    held high D with vibrato. Two DLS trumpets a few ms apart for the bite, an FM brass voice inside them for the
    glow and the vibrato, in the hall. 4.8 s; `fanfare` answers on the high D (1.80 s in)."""
    secs = 4.8; n = int(secs * SR); ev = []
    for dt, vs in ((0, 1.0), (.011, .8)):
        for t0, d, p in CALL:
            ev.append((t0 + dt + (R().normal(0, .003) if dt else 0), d * (.9 if d < .3 else .97), p, (112 if p in ("A5", "D6") else 100) * vs, TRUMPET))
    x = gm_render(ev, secs)
    rng = np.random.default_rng(5)
    fm = syn_brass([[t0, t0 + d * .96, note(p), 104] for t0, d, p in CALL], n, rng, index=3.0, players=2)
    fm = me.lp(fm, 6500)
    x = x / (np.max(np.abs(x)) + 1e-9) + .32 * fm / (np.max(np.abs(fm)) + 1e-9)
    x *= curve(n, [(0, 1), (3.2, 1), (3.75, 0), (secs, 0)])
    return me.fit(me.room(me.lp(x, 9500), HALL, .26), secs, fade_out=.4)


def sfx_choir_ah(ctx):
    """Wings spread wide: a great warm choir 'ah' on D major (formant choir, men and women, with the DLS choir
    inside it), swelling over a second and fading over two, a few high bells, in the hall."""
    secs = 4.8; n = int(secs * SR); rng = np.random.default_rng(9)
    ns = [[0.0, 3.3, note(p), v] for p, v in (("D3", 84), ("A3", 80), ("D4", 86), ("F#4", 84), ("A4", 86), ("D5", 84), ("F#5", 74))]
    x = syn_choir(ns, n, rng, vowel="ah", attack=.9)
    g = gm_render([(0, 3.4, p, 76, CHOIR) for p in ("D4", "F#4", "A4", "D5")], secs)
    x = x / (np.max(np.abs(x)) + 1e-9) + .3 * g / (np.max(np.abs(g)) + 1e-9)
    x *= curve(n, [(0, 0), (1.0, 1), (2.6, 1), (4.4, 0), (secs, 0)]) ** 1.4
    for i in range(10):
        p = ["D6", "F#6", "A6", "B6", "D7", "E7"][int(R().integers(0, 6))]
        me.place(x, bell(1.2, hz(p), [1, 2.76], [1, .2], [.5, .15]) * .04 * R().uniform(.5, 1), .7 + i * .24 + R().normal(0, .03))
    return me.fit(me.room(me.lp(x, 9000), HALL, .4), secs, fade_out=.5)


def sfx_sparkle(ctx):
    """Esther's shower of tiny bells (D major pentatonic: this pack's key), shared from music_esther."""
    return me.sfx_sparkle()


SFX = {"wing_flap": sfx_wing_flap, "wing_fold": sfx_wing_fold, "whoosh_land": sfx_whoosh_land,
       "trumpet_call": sfx_trumpet_call, "choir_ah": sfx_choir_ah, "sparkle": sfx_sparkle}
SFX_GAIN = {"wing_flap": -5, "wing_fold": -10, "whoosh_land": -6, "trumpet_call": -5, "choir_ah": -8, "sparkle": -9}
SFX_NOTES = {"wing_flap": "huge soft wing beat: quiet lift, then a 0.6 s low airy 'whoomf' (most energy under 300 Hz), soft pressure thump, trace of feather hiss",
             "wing_fold": "falling sweep of air, seven feather rustles getting lower and quieter, pillowy 'fwup', a four-rustle shake",
             "whoosh_land": "whoosh falling in pitch, deep soft 'pomf' (80 -> 45 Hz, no click), puff of cloud rolling out",
             "trumpet_call": "the Gabriel theme: A-D-A, then B-C#-D held with vibrato; two DLS trumpets + FM brass glow, hall; `fanfare` answers at 1.80 s",
             "choir_ah": "formant choir 'ah' on D major (men + women, DLS choir inside), 1 s swell, 2 s fade, high bells, hall",
             "sparkle": "Esther's D major pentatonic bell shower (shared synth)"}


# =============================================================================================== build
def cue_spans(tl):
    cues = sorted(tl["music"], key=lambda c: c["t"]); out = []
    for i, c in enumerate(cues):
        end = cues[i + 1]["t"] if i + 1 < len(cues) else tl["duration"]
        out.append(dict(cue=c["cue"], t=c["t"], span=round(end - c["t"], 3), secs=round(end - c["t"] + XFADE, 3),
                        last=i + 1 == len(cues)))
    return out


def cue_files(spans):
    """One file per cue name; a cue that plays more than once (gentle) is composed for its longest occurrence."""
    files = {}
    for c in spans: files.setdefault(c["cue"], dict(cue=c["cue"], occ=[]))["occ"].append(c)
    for f in files.values(): f["primary"] = max(f["occ"], key=lambda c: c["span"])
    return files


def render_cue(tl, name, c):
    me.seed("gabriel/" + name); ctx = Ctx(tl, name, c["t"], c["span"], c["secs"], c["last"])
    sc = MUSIC[name](ctx)
    add_vamp(sc, *VAMP[name]); vp = sc.vamp
    main, vamp = render_split(sc)
    air = lambda z: z + .4 * me.hp(z, 5000)                                  # a little air on top (+3 dB above 5 kHz)
    n = int(round(sc.secs * SR)); main = air(me.hp(me.fit(main, sc.secs, fade_out=0), 28)); vamp = air(me.hp(me.fit(vamp, sc.secs, fade_out=0), 28))
    ns, ls, le = int(c["span"] * SR), int(round((vp["start"] + vp["secs"]) * SR)), int(round((vp["start"] + 2 * vp["secs"]) * SR))
    # loop tile = the second repeat as rendered (steady state), first 30 ms blended from the true continuation
    L = le - ls; kx = int(.03 * SR); w = np.linspace(0, 1, kx)
    T = vamp[ls:le].copy(); T[:kx] = vamp[le:le + kx] * (1 - w) + vamp[ls:ls + kx] * w
    vs = np.zeros(n); p0 = ls - L
    for j in range(0, (n - p0) // L + 1):
        q = p0 + j * L; m_ = min(L, n - q)
        if m_ > 0: vs[q:q + m_] = T[:m_]
    kv = int(.25 * SR); vs[p0:p0 + kv] *= np.linspace(0, 1, kv)             # the bed comes in under the cadence
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
             loopEndSample=le, loopFromSec=round(vp["start"], 3), key=KEYS[name], meter="4/4",
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
        print(f"music {name:8s} t={f['primary']['t']:7.2f} span={f['primary']['span']:6.2f} file={r['secs']:6.2f}s "
              f"bars={r['bars']:2d} bpm={r['bpm']:5.1f} span I={r['lufs']:6.1f} loop {r['loopStart']:.2f}-{r['loopEnd']:.2f}s "
              f"I={r['loopLufs']:6.1f} TP={r['truePeak']:5.1f} dBTP" + (f" (plays {len(f['occ'])}x)" if len(f["occ"]) > 1 else ""), flush=True)
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
                        "its last 2.5 s. A cue that plays more than once (gentle) uses the same file from its start each "
                        "time; composedFor / composedSpan name the occurrence it was timed to. The composed span sits at "
                        "-20 LUFS, the loop section ~3 dB under it. Duck music ~7 dB under voice lines. `fanfare` is "
                        "built around the sfx `trumpet_call` (same key, the orchestra answers 1.80 s into it): keep "
                        "them at their timeline times. Rerun tools/story/music_gabriel.py after the timeline is "
                        "re-timed so the in-cue hits follow.",
                   crossfadeSec=XFADE, lufs=MUSIC_LUFS, stretchCovered=STRETCH, cues=manifest),
              open(path_json, "w"), indent=1, ensure_ascii=False)
    return manifest


def build_sfx(tl):
    needed = sorted({s["id"] for s in tl["sfx"]}); missing = [i for i in needed if i not in SFX]
    assert not missing, f"no synth for sfx {missing}"
    manifest = []
    for sid in sorted(set(needed) | set(SFX)):
        me.seed("gabriel/" + sid)
        times = [s["t"] for s in tl["sfx"] if s["id"] == sid]
        x = me.hp(np.asarray(SFX[sid](dict(tl=tl, t=min(times) if times else 0.0)), np.float64), 30)
        x = me.peak_normalize(x, SFX_PEAK_DB); path = f"{SFX_DIR}/{sid}.wav"; me.write_wav(path, x); m = me.measure(path)
        e = dict(id=sid, secs=round(len(x) / SR, 3), loop=False, gainDb=SFX_GAIN[sid],
                 samplePeak=round(m["samplePeak"], 1), truePeak=round(m["truePeak"], 1),
                 lufs=None if m["lufs"] == float("-inf") else round(m["lufs"], 1), plays=len(times))
        manifest.append(e); clean_tmp()
        print(f"sfx   {sid:13s} {e['secs']:6.2f}s peak={m['samplePeak']:5.1f} dBFS TP={m['truePeak']:5.1f} I={m['lufs']:6.1f} plays {len(times)}x", flush=True)
    json.dump(dict(rule="Files peak at -3 dBFS (CONTRACT section 7). Play each one-shot at its timeline t with gainDb "
                        "(recommended mix level). `trumpet_call` and the music cue `fanfare` are one piece: keep both "
                        "at their timeline times.",
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
        me.place(fx, me.load_any(f"{SFX_DIR}/{s['id']}.wav") * 10 ** (SFX_GAIN[s["id"]] / 20), s["t"])
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


# =============================================================================================== verification
def band_share(x, lo, hi):
    f, p = signal.welch(x, SR, nperseg=4096); return float(p[(f >= lo) & (f < hi)].sum() / (p.sum() + 1e-20))


def click_score(x):
    """Largest sample-to-sample jump relative to the signal's own typical movement (99.9th percentile of |diff|).
    A hard click (a cut, a discontinuity) scores far above 10; music and noise stay in single figures."""
    d = np.abs(np.diff(x)); ref = np.percentile(d, 99.9) + 1e-9
    return float(d.max() / ref)


def check():
    """Measure what is on disk: loudness, peaks, loop seams (tile identity and the jump across the seam), clicks,
    and where the energy of the wing sounds sits. Prints a table; returns the rows (also used for MUSIC.md)."""
    cues = json.load(open(f"{MUSIC_DIR}/cues.json"))["cues"]; rows = []; seen = set(); ok = True
    print(f"\n{'cue':9s} {'span I':>7s} {'loop I':>7s} {'TP':>6s} {'tiles':>9s} {'seam':>6s} {'click':>6s} {'need':>7s} {'file':>7s}")
    for c in cues:
        if c["cue"] in seen: continue
        seen.add(c["cue"])
        x = me.load_any(f"{MUSIC_DIR}/{c['cue']}.wav"); ls, le = c["loopStartSample"], c["loopEndSample"]; L = le - ls
        ns = int(c["composedSpan"] * SR)
        tile = float(np.max(np.abs(x[ls:le] - x[le:le + L]))) if le + L <= len(x) - int(2.6 * SR) else float("nan")
        d = np.abs(np.diff(x[ls:le])); seam = abs(x[ls] - x[le - 1]) / (np.percentile(d, 99.9) + 1e-9)
        m_span, m_loop, m = lufs_of(x[:ns]), lufs_of(x[ls:le]), me.measure(f"{MUSIC_DIR}/{c['cue']}.wav")
        need = max(o["span"] for o in cues if o["cue"] == c["cue"]) * (1 + STRETCH) + XFADE
        r = dict(cue=c["cue"], lufs=round(m_span["lufs"], 1), loopLufs=round(m_loop["lufs"], 1), truePeak=round(m["truePeak"], 1),
                 bands=[round(band_share(x[:ns], lo, hi) * 100, 1) for lo, hi in ((0, 200), (200, 1000), (1000, 4000), (4000, 22050))],
                 tileMaxDiff=tile, seam=round(float(seam), 2), click=round(click_score(x), 1), need=round(need, 2), secs=round(len(x) / SR, 2))
        good = (abs(r["lufs"] - MUSIC_LUFS) <= .5 and r["truePeak"] <= -1.0 and (tile != tile or tile <= 1 / 32767 + 1e-9)
                and r["seam"] <= 1.5 and r["click"] < 12 and r["secs"] >= need)
        ok &= good; rows.append(r)
        print(f"{r['cue']:9s} {r['lufs']:7.1f} {r['loopLufs']:7.1f} {r['truePeak']:6.1f} {tile:9.2g} {r['seam']:6.2f} {r['click']:6.1f} "
              f"{need:7.2f} {r['secs']:7.2f}  {'ok' if good else 'CHECK'}  bands % {r['bands']}")
    srows = []
    print(f"\n{'sfx':13s} {'secs':>5s} {'peak':>6s} {'click':>6s} {'<300Hz':>7s} {'<400Hz':>7s} {'>2kHz':>6s} {'centroid':>9s}")
    for e in json.load(open(f"{SFX_DIR}/mix.json"))["sfx"]:
        x = me.load_any(f"{SFX_DIR}/{e['id']}.wav"); m = me.measure(f"{SFX_DIR}/{e['id']}.wav")
        f, p = signal.welch(x, SR, nperseg=4096); cen = float((f * p).sum() / p.sum())
        r = dict(id=e["id"], secs=e["secs"], samplePeak=round(m["samplePeak"], 1), click=round(click_score(x), 1),
                 low=round(band_share(x, 0, 300), 2), low400=round(band_share(x, 0, 400), 2), high=round(band_share(x, 2000, 22050), 3), centroid=round(cen))
        good = abs(r["samplePeak"] - SFX_PEAK_DB) <= .2 and r["click"] < 14 and abs(x[0]) < .01 and abs(x[-1]) < .01
        if e["id"] in ("wing_flap", "whoosh_land"): good &= r["low400"] >= .55 and r["high"] <= .03 and r["centroid"] <= 500
        if e["id"] == "trumpet_call": good &= r["secs"] <= 5.0
        ok &= good; srows.append(r)
        print(f"{r['id']:13s} {r['secs']:5.2f} {r['samplePeak']:6.1f} {r['click']:6.1f} {r['low']:7.2f} {r['low400']:7.2f} {r['high']:6.3f} {r['centroid']:9d}  {'ok' if good else 'CHECK'}")
    # the theme: is every note of the trumpet call at its written pitch?
    x = me.load_any(f"{SFX_DIR}/trumpet_call.wav"); theme = []
    for t0, d, p in CALL:
        seg = x[int((t0 + .04 + d * .25) * SR):int((t0 + .04 + d * .85) * SR)]; f0 = hz(p)
        sp = np.abs(np.fft.rfft(seg * np.hanning(len(seg)), 1 << 17)); fr = np.fft.rfftfreq(1 << 17, 1 / SR)
        k = (fr > f0 * .92) & (fr < f0 * 1.08); cents = 1200 * math.log2(fr[k][np.argmax(sp[k])] / f0)
        theme.append((p, round(cents))); ok &= abs(cents) <= 35
    print("\ntrumpet_call pitches (cents off the score): " + ", ".join(f"{p} {c:+d}" for p, c in theme))
    print("\nall checks passed" if ok else "\nSOME CHECKS FAILED")
    return rows, srows, ok, theme


def update_doc(tl, cues, sfx, prev, chk=None):
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
        rows = ["| Id | Length (s) | Plays | Sample peak (dBFS) | True peak (dBTP) | LUFS | gainDb | Notes |", "|---|---|---|---|---|---|---|---|"]
        for s in sfx:
            rows.append(f"| `{s['id']}` | {s['secs']:.2f} | {s['plays']}× | {s['samplePeak']:.1f} | {s['truePeak']:.1f} | "
                        f"{s['lufs'] if s['lufs'] is not None else 'n/a'} | {s['gainDb']} | {SFX_NOTES[s['id']]} |")
        swap("sfx", "\n".join(rows) + "\n")
    if prev:
        swap("preview", f"Last run: {prev['secs']} s, {prev['lufs']} LUFS, {prev['truePeak']} dBTP; zh voice clips "
                        f"present: {prev['voices']}/{prev['lines']}; timeline `timedFrom`: {tl.get('timedFrom')}.\n")
    if chk:
        rows = ["| Cue | LUFS span | LUFS loop | True peak | Loop tiles: max sample difference | Seam jump (× typical step) | Click score | Needed (s) | File (s) |",
                "|---|---|---|---|---|---|---|---|---|"]
        for r in chk[0]:
            rows.append(f"| `{r['cue']}` | {r['lufs']} | {r['loopLufs']} | {r['truePeak']} | {r['tileMaxDiff']:.2g} | {r['seam']} | {r['click']} | {r['need']} | {r['secs']} |")
        rows += ["", "| Effect | Length (s) | Sample peak (dBFS) | Click score | Energy under 400 Hz | Energy over 2 kHz | Spectral centroid (Hz) |", "|---|---|---|---|---|---|---|"]
        for r in chk[1]:
            rows.append(f"| `{r['id']}` | {r['secs']} | {r['samplePeak']} | {r['click']} | {r['low400'] * 100:.0f} % | {r['high'] * 100:.1f} % | {r['centroid']} |")
        rows.append("\nTheme in `trumpet_call` (cents off the written pitch): " + ", ".join(f"{p} {c:+d}" for p, c in chk[3]) + ".")
        rows.append(f"\nResult: **{'all checks passed' if chk[2] else 'some checks failed, see the CHECK rows in the console output'}**.")
        swap("check", "\n".join(rows) + "\n")
    open(DOC, "w").write(txt)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-music", action="store_true"); ap.add_argument("--skip-sfx", action="store_true")
    ap.add_argument("--skip-preview", action="store_true"); ap.add_argument("--only", default="")
    ap.add_argument("--stems", action="store_true", help="print per-stem levels while rendering")
    ap.add_argument("--check", action="store_true", help="only measure the files on disk")
    ap.add_argument("--tmp", default="/tmp/gabriel_audio/music", help="scratch dir (emptied per cue, removed at exit)")
    a = ap.parse_args(); me.STEM_REPORT = a.stems
    os.makedirs(a.tmp, exist_ok=True)
    tempfile.tempdir = tempfile.mkdtemp(prefix=TMP_PREFIX, dir=a.tmp)
    atexit.register(shutil.rmtree, tempfile.tempdir, True)
    os.makedirs(MUSIC_DIR, exist_ok=True); os.makedirs(SFX_DIR, exist_ok=True)
    tl = json.load(open(TIMELINE))
    if a.check:
        update_doc(tl, None, None, None, check()); sys.exit(0)
    only = set(x for x in a.only.split(",") if x)
    cues = None if a.skip_music else build_music(tl, only or None)
    sfx = None if a.skip_sfx else build_sfx(tl)
    prev = None if a.skip_preview else build_preview(tl)
    update_doc(tl, cues, sfx, prev, check())
